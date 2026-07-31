# ZooKeeper

Apache 的分布式协调服务，把一套树形 znode + Watcher + ZAB 一致性协议封装在一起，是早期 Java 生态事实上的「注册中心 / 配置中心 / 分布式协调」基石。

## 一、定位与特性

- **数据模型**：树形 znode（类似文件系统），节点可存少量 data + stat
- **一致性**：ZAB（ZooKeeper Atomic Broadcast），写走 Leader 全局有序，读任意节点
- **协调原语**：Watcher、临时节点、顺序节点、session / lease
- **典型用法**：注册中心、配置中心（/config/{app}/{key}）、分布式锁、选主、集群元数据
- **历史方案**：百度 Disconf、淘宝 Diamond 都基于 ZK 实现早期分布式配置中心
- **现状**：Java/Hadoop 老牌项目仍在用（Dubbo / Kafka / HBase / Hadoop / Solr），新项目多被 Nacos/etcd/Consul 取代

```text
┌────────────────────────────────────────────┐
│              ZooKeeper ensemble             │
│                                             │
│  ┌────────┐  ┌────────┐  ┌────────┐        │
│  │ Leader │──│Follower│──│Follower│  ...    │
│  │ (2101) │  │(2101)  │  │(2101)  │         │
│  └────────┘  └────────┘  └────────┘         │
└────────────────────────────────────────────┘
```

## 二、ZAB 协议与角色

### 1. 角色

| 角色 | 任务 |
| ---- | ---- |
| **Leader** | 唯一接受写的节点，写入 Propose 到 ZXID，单一事务序号 |
| **Follower** | 投票 + 转发 proposal，写操作被代理到 Leader |
| **Observer** | 不参与投票，提升读扩展，可挂多节点横向扩读 |

```text
  client                                                   
    │                                                      
    ▼                                                      
  Follower ────propose──▶ Leader                            
                       │                                    
                       ▼                                    
                  zxid = 64                                 
   Sync（ack quorum）                                      
                       │                                    
              broadcast commit                              
                       ▼                                    
   所有 Follower 持久化 + apply                              
```

### 2. ZXID

```text
zxid = 64bit
 高 32 bit：epoch（Leader 变更 +1）
 低 32 bit：counter（每个事务 +1）

zxid 单调递增，事务全局有序
```

- 集群重启或 Leader 切换时 epoch +1，避免「脑裂 Leader 各用一份历史」

### 3. 恢复阶段

```text
选举 leader (FastLeaderElection)
   │
   ▼
恢复 + 同步 (所有 Follower 拉到自己的 lastZxid 与 Leader 对齐)
   │
   ▼
广播 (Broadcast，开始接受写)
```

崩溃恢复要求：**已被多数派 commit 的必须出现在新 Leader 的 history**，未 commit 的丢弃。

## 三、数据模型 znode

### 1. 类型

| 类型 | 生命周期 | 标志 |
| ---- | ---- | ---- |
| **PERSISTENT** | 持久，create 一直存在 |  |
| **PERSISTENT_SEQUENTIAL** | 持久 + 序号后缀 | 适合选主候选 |
| **EPHEMERAL** | 临时，session 断开自动删 | 适合服务注册 |
| **EPHEMERAL_SEQUENTIAL** | 临时 + 序号 | 适合分布式锁 |
| **Container** | 容器，最后一个 child 删除时自动删 | 不存 data，结构清晰 |
| **TTL** | 可附加 TTL（3.6+） |  |
| **TTL + Container** | 可组合 TTL |  |

### 2. Stat 字段

```text
cZxid            创建事务的 zxid
mZxid            最后修改事务的 zxid
pZxid            child 列表最后修改的 zxid（⚠ 不是节点的 pZxid）
ctime / mtime    创建 / 修改时间
version          data 版本（CAS 用，类型 int）
cversion         child 版本
aversion         ACL 版本
ephemeralOwner   session id（临时节点才非 0）
dataLength       data 字节数
numChildren      子节点数
```

### 3. 限额

| 项 | 默认 |
| ---- | ---- |
| 单节点 data | 推荐 ≤ 1 MB（默认 1 MB） |
| 节点 path | 字节长度受 `jute.maxbuffer` 限制 |

## 四、Watcher 机制

ZK 的订阅模型是「一次性、推完即焚」，与 etcd 长连接 stream 重放截然不同：

```text
client                          server
  │   exists(w, "/x/y")         │
  │────────────────────────────▶│
  │       WatcherEvent          │
  │◀───────────────────────────│
  │   Watcher 已失效            │
  │   需手动重设                 │
```

### 1. 特点

- **触发一次即失效**：Watcher 收到事件后自动注销，想再收新的事件必须重新注册
- **事件类型**：`None / NodeCreated / NodeDeleted / NodeDataChanged / NodeChildrenChanged`
- **事件源**：所有事件都序列化进 ZXID，client 可在断连恢复时同步到 ZXID 状态

### 2. 羊群效应（Herd Effect）

```text
getData(w, "/config/app")
   │
   ▼ 节点变更触发 watcher 通知
   │
   ▼
1000 个 client 同时收到事件，
各自重新 getData + 重新 setWatcher
瞬时风暴打到同一台 ZK
```

**常用缓解**：

- **Curator PathChildrenCache**：内部维护 cache + 自动复订阅，缓解但不完全消除
- **Curator TreeCache / NodeCache**：本地缓存 + 后台定期 resync
- **事件队列化**：客户端拿到事件后丢到一个队列，单线程处理
- **改用 etcd 的 stream**：根本性解决——etcd 服务端把多 client 合并成一条 stream 推，客户端不会全部同时竞争

### 3. ACK 保障

- ZK 保证「事件总能看到一次」或「在客户重连接上后会以 SZxid 重同步」

## 五、会话 Session

```text
client  connect
   │
   ▼
server 分配 sessionId（64-bit，base + counter）
   │
   ▼
双方心跳（默认 tick × 2 = 2 × 2 = 4 秒一次）
   │
   ▼
如果 client 在 session timeout（tick × timeout = 2 × 10 = 20s）内无心跳
   │
   ▼
server 关闭 session + 删除该 session 下的所有 ephemeral 节点
```

### 1. 时间配置

| 参数 | 默认 | 说明 |
| ---- | ---- | ---- |
| `tickTime` | 2s | 心跳单位 |
| `initLimit` | 10 × tickTime | follower 与 leader 建链最长时间 |
| `syncLimit` | 5 × tickTime | follower 与 leader 同步最长时间 |
| maxSessionTimeout | tickTime × 20 | 推荐也设大点，避免 GC pause 误杀 |

### 2. 跨数据中心

- ZK 集群强同步、追求低延迟，跨机房高 RTT 容易频繁 election
- 推荐：单机房 + 多 AZ；多机房之间只走应用层同步

## 六、ACL

ZK 的 ACL 是 `<scheme>:<id>:permissions`：

| scheme | 含义 |
| ---- | ---- |
| `world` | 任何用户 |
| `auth` | 显式 addauth 过的用户 |
| `digest` | `user:base64(sha1(pass))` |
| `ip`   | 客户端 IP prefix |
| `x509` / `sasl` | TLS / SASL 接入 |

```bash
setAcl /config/app world:anyone:cdr   # create+delete+read, 不写
addauth digest user:pwd
setAcl /config/app digest:user:base64secret:rw
```

## 七、Curator 客户端

Curator 是 Netflix 开源的 ZK Java 客户端，封装了大量「生产者级」常用模式。

### 1. 引入

```xml
<dependency>
  <groupId>org.apache.curator</groupId>
  <artifactId>curator-framework</artifactId>
  <version>5.6.0</version>
</dependency>
<dependency>
  <groupId>org.apache.curator</groupId>
  <artifactId>curator-recipes</artifactId>
  <version>5.6.0</version>
</dependency>
```

### 2. CuratorFramework

```java
RetryPolicy retry = new ExponentialBackoffRetry(1000, 3);
CuratorFramework client = CuratorFrameworkFactory.builder()
    .connectString("zk1:2181,zk2:2181,zk3:2181")
    .sessionTimeoutMs(15_000)
    .connectionTimeoutMs(5_000)
    .retryPolicy(retry)
    .namespace("myapp")        // 所有 path 加 namespace 前缀
    .build();
client.start();

client.create()
      .creatingParentsIfNeeded()
      .withMode(CreateMode.PERSISTENT)
      .forPath("/config/app", "v1".getBytes());

Stat stat = new Stat();
byte[] data = client.getData()
      .storingStatIn(stat)             // CAS 拿版本号
      .forPath("/config/app");
int version = stat.getVersion();       // 用 version 当 versionOfZnode
// CAS
client.setData()
      .withVersion(version)
      .forPath("/config/app", "v2".getBytes());
```

### 3. Cache 选择

| Cache | 监听 | 用法 |
| ---- | ---- | ---- |
| **NodeCache** | 单节点 data 变化 | 本地缓存一个节点的 value |
| **PathChildrenCache** | 子节点增删 + 子节点的 data 变化 | 服务列表场景 |
| **TreeCache** | 整子树 | 全路径配置树 |

```java
NodeCache nodeCache = new NodeCache(client, "/config/app", true);
nodeCache.getListenable().addListener(() -> {
    ChildData cd = nodeCache.getCurrentData();
    if (cd != null) {
        log.info("config changed: {}", new String(cd.getData()));
    }
});
nodeCache.start(PathChildrenCache.StartMode.POST_INITIALIZED_EVENT);

TreeCache treeCache = TreeCache.newBuilder(client, "/config").build();
treeCache.getListenable().addListener((_, event) -> {
    log.info("tree event: {}", event);
});
treeCache.start();
```

### 4. 分布式锁 InterProcessMutex

```java
InterProcessMutex lock = new InterProcessMutex(client, "/locks/order");

if (lock.acquire(10, TimeUnit.SECONDS)) {
    try {
        doBusinessWork();
    } finally {
        lock.release();
    }
}
```

- 临时顺序节点实现公平锁；自己写实现容易踩「羊群效应」

## 八、配置中心典型用法

```text
/config/
  myapp/
    prod/
      db.url = jdbc:mysql://...
      db.pool.size = 50
    gray/
      db.url = jdbc:mysql://...

命名约定：
  /{系统}/{应用}/{环境}/{key}      -> 简单平铺
  /c_onfig/{app}/{env}/{group}/{key} -> 二级 group
```

```bash
# 启动时拉全部配置
for key in $(getChildren "/config/myapp/prod"); do
    echo "$key=$(getData "/config/myapp/prod/$key")"
done > myapp.properties

# 结合 push 触发：Confd / scheduleryx / 自研 agent 拉 → file → reload
```

### 历史方案：Disconf / Diamond

| 方案 | 出处 | 模型 | 存储 |
| ---- | ---- | ---- | ---- |
| **Disconf** | 百度 | `app/environment/key=value`，实时推送 | MySQL + ZK（watch） |
| **Diamond** | 阿里 (历史) | group/dataId 多版本 | MySQL + 本地 + 长轮询 |

两者都是「MySQL 存配置 + ZK 推送变更通知」的组合；ZK 主要承担「集群通知 / 选举」职责，本身不直接存业务配置。

## 九、典型用户案例

| 系统 | 用 ZK 做什么 |
| ---- | ---- |
| **Dubbo** | 服务注册 + 订阅（`/dubbo/{service}/providers`） |
| **Kafka** | broker 注册、`__consumer_offsets`、`/controller` 选主 |
| **HBase** | RegionServer 注册、HMaster 选举 |
| **Hadoop YARN** | ResourceManager HA、各 service 元数据 |
| **Solr/Elasticsearch（老版）** | 集群发现 + 配置分发 |

## 十、性能与写扩展性瓶颈

| 维度 | 说明 |
| ---- | ---- |
| **写** | 必须经过 Leader，在内存 queue + fsync 后才能 ack |
| **事务** | 单 Leader → 单数 ops/s 量级上限，比 etcd 还低 |
| **读** | Follower/Observer 都可响应，扩读 OK |
| **网络** | 同步链路长（initLimit × tickTime），跨机房不可行 |
| **Watcher 风暴** | 一次性通知 → 高频事件时客户端被打爆 |
| **大 data** | 默认 1MB，缩小到 GB 是噩梦 |

**为什么现在多被 Nacos/etcd 取代**：

- Nacos 提供更友好的「namespace/group/dataId」模型 + 内置 UI
- etcd 提供强一致线性化写 + 长连接 Watch，无羊群效应
- ZK 的 Java 强绑定、Watcher 一次性、调参痛苦，运维上更繁

## 十一、优缺点

### 优点

- Java 生态深入骨髓，老牌项目首选
- Curator 提供分布式锁、Barrier、Queue、Leader Election 模板
- 状态机清晰：选举 / 同步 / 广播，对理解分布式一致性有帮助
- 数据强一致（ZAB 是 Paxos 系好实践）

### 缺点

- **写扩展性差**：单 Leader，所有写串行，量级上不去
- **Watcher 一次性**：要自己写 cache 框架，集群大时羊群严重
- **数据上限严**：1MB/node、节点数受限（推荐 < 10K）
- **运维繁**：tick、init、sync、JVM、调参多
- **跨机房**：ZK 同城才能稳

适用：Java 老栈改造、有 ZK 配套生态需求、配置规模数 GB 之内、读多写少、不追求极致 SLA。

## 十二、最佳实践

- **永远用 Curator 客户端**：不要裸用 Apache client，重连、retry、异常处理都帮你写过
- **chroot / namespace**：每个业务一棵树，规避全集群污染
- **SessionTimeout**：要给 JVM GC pause 留 margin，建议 30~60s；用 G1GC + ZGC
- **addauth + digest**：默认 `world:anyone` 是 demo 配置，生产必须 tighten
- **大配置项少、原子操作多**：配置粒度越细越好更新；避免一次塞 100KB JSON
- **多实例共用 znode 名**：watcher 拿出来前用 PathChildrenCache 配合本地 Map 用
- **部署**：3 / 5 节点，跨机架 / AZ，follower 配置相同
- **部署参数**：mirror 慎开、autopurge + snapRetainCount + purgeInterval 打开
- **监控**：四字命令 `mntr`，Prometheus exporter 可装 `mntr_exporter`
- **测试**：Curator 的 `TestingServer` 起单进程 ZK 做集成测试，不要共享线上 ZK
