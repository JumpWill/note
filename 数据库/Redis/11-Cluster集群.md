# Redis Cluster 集群

## 一、Redis Cluster 概述

### 1. 什么是 Redis Cluster

**Redis Cluster** 是 Redis **官方**在 3.0 版本推出的**分布式解决方案**,用于解决**单机 Redis** 在**数据量、并发量、高可用**三个维度上的瓶颈:

- **数据量**:单机内存有上限(通常几十 GB 到几百 GB),Cluster 把数据分片到多机
- **并发量**:单实例 QPS 上限约 10w 左右,Cluster 通过水平扩展承接更高吞吐
- **可用性**:单点故障导致全站不可用,Cluster 内置**故障自动转移**

与 **Sentinel**(只解决高可用、不解决数据量)相比,Cluster 同时提供**水平扩展 + 高可用**,是 Redis 在大规模场景下的**默认选型**。

### 2. Redis Cluster 核心能力

| 能力 | 说明 |
|------|------|
| **数据自动分片** | 16384 个 slot 分布在多个 master,客户端按 CRC16 算法路由 |
| **自动故障转移** | master 故障后,replica 自动选举升主,业务无感知(或短暂感知) |
| **去中心化** | 无 Proxy/Coordinator,所有节点平等,通过 **Gossip 协议**同步状态 |
| **客户端智能路由** | 客户端本地缓存 slot -> node 映射,支持 **MOVED / ASK 重定向** |
| **水平扩展** | 在线添加节点 + `cluster reshard` 在线迁移 slot,无需停服 |
| **副本机制** | 每个 master 可挂 1 ~ N 个 replica,数据冗余 + 读写分离 |

### 3. Cluster 与其他方案对比

| 方案 | 解决数据量 | 解决高可用 | 数据分片方式 | 运维复杂度 | 适用场景 |
|------|------------|------------|--------------|------------|----------|
| **单机 Redis** | 否 | 否 | 无 | 最低 | 开发测试、小型缓存 |
| **主从复制** | 否 | 需 Sentinel | 无 | 低 | 中小型业务读扩展 |
| **Sentinel** | 否 | 是 | 无 | 中 | 中小型业务高可用 |
| **Redis Cluster** | 是 | 是 | **16384 slot 哈希分片** | 中 | **中大型生产,推荐** |
| **Twemproxy** | 是 | 否(需配合 Sentinel) | 一致性哈希 | 中 | 客户端无改造的代理方案 |
| **Codis** | 是 | 是 | 自定义 slot | 高 | 早期国产大规模方案 |
| **云 Redis (Tair)** | 是 | 是 | Proxy + 后端分片 | 低 | 上云首选 |

> **官方建议**:Redis Cluster 是 Redis 团队**长期主推**的方案,Sentinel 仅作为小型部署兜底。Twemproxy/Codis 偏中间件路线,运维成本高且社区活跃度下降。

---

## 二、核心概念

### 1. 哈希槽 (Hash Slot)

Redis Cluster 把全部**键空间**切分成 **16384 (2^14) 个 slot**,每个 key 通过固定算法映射到某一个 slot:

```text
key          ─►  CRC16(key) mod 16384  ─►  slot 号 (0 ~ 16383)
"user:1001"          0xA3F2 % 16384         12176
"order:202401"       0xBC11 % 16384         5021
```

每个 master 节点负责**一部分 slot**,把 16384 个 slot 摊派到 N 个 master 上,实现**水平扩展**:

```text
16384 slots
 ┌────────┬─────────────┬────────┬─────────┐
 │  0–5460│  5461–10922 │10923– │ 13107–  │
 │ (5461) │   (5462)    │13106  │ 16383   │
 │        │             │(2184) │ (3277)  │
 └────────┴─────────────┴────────┴─────────┘
   M1          M2           M3       M4
 (master)   (master)     (master)  (master)
   │           │            │         │
   ↓           ↓            ↓         ↓
   S1          S2           S3        S4
 (replica)  (replica)    (replica)  (replica)
```

> **为什么是 16384 而不是 65536**?
> 1. 心跳包中携带节点 slot 信息,如果用 65536 (2^16) 则单包 8KB,16384 仅 **2KB**,Gossip 消息体小、带宽省
> 2. Redis 主节点一般不超过 1000 个,16384 个 slot 足够均衡
> 3. 集群规模扩张时,16384 个 slot 在 master 间分配仍有不错的粒度(每个 master 几十 ~ 几百个 slot)

### 2. CRC16 算法

Redis 使用 **CRC16-CCITT** (多项式 `0x1021`)对 key 做哈希,然后取模:

```python
# Python 伪代码,实际 Redis 源码在 cluster.c
def key_to_slot(key):
    # 1. 提取 hashtag(花括号包裹部分)
    hashtag = extract_hashtag(key)
    if hashtag:
        target = hashtag
    else:
        target = key

    # 2. CRC16 计算
    crc = crc16_xmodem(target) & 0x3FFF  # 取低 14 位,等价于 mod 16384
    return crc
```

```bash
# redis-cli 直接查看 key 落在哪个 slot
> CLUSTER KEYSLOT "user:1001"
(integer) 12176

> CLUSTER KEYSLOT "{user:1000}.profile"
(integer) 2417

> CLUSTER KEYSLOT "{user:1000}.order"
(integer) 2417     # hashtag 强制同 slot
```

### 3. Gossip 协议 (节点间通信)

Cluster 节点之间通过 **Gossip(流言)** 协议交换状态,**最终一致**地维护集群拓扑:

```text
   ┌──────┐  ping   ┌──────┐  ping   ┌──────┐
   │  M1  │ ──────► │  M2  │ ──────► │  M3  │
   │      │ ◄────── │      │ ◄────── │      │
   └──┬───┘  pong   └──┬───┘  pong   └──┬───┘
      │                │                │
      ▼                ▼                ▼
   ┌──────┐         ┌──────┐         ┌──────┐
   │  S1  │         │  S2  │         │  S3  │
   └──────┘         └──────┘         └──────┘

每节点每秒随机选 1~5 个节点发送 ping
被 ping 节点回复 pong (附带自己已知其他节点的状态)
```

**消息类型**:

| 类型 | 方向 | 用途 |
|------|------|------|
| **MEET** | A → B | 把 B 加入集群(已知 IP/Port 即可) |
| **PING** | A → B | 探活 + 同步 B 的节点状态 |
| **PONG** | B → A | 回应 MEET/PING |
| **FAIL** | A → ALL | 广播某节点被认定下线 |
| **PUBLISH** | A → ALL | 广播某 channel 的 pubsub 消息 |

### 4. 副本与高可用

Cluster 默认采用 **master-replica** 模型:

```text
最小高可用集群: 3 master + 3 replica = 6 节点

  M1 ──► S1
  M2 ──► S2
  M3 ──► S3
```

- **每个 master 至少 1 个 replica**(生产建议至少 2 个,跨机房更好)
- replica 通过异步复制同步 master 数据
- master 故障时,**该 master 的 replica** 参与选举,胜出者升为新 master
- 若某 master 全部 replica 故障,该 master 仍可服务(但失去 HA)

> **最严苛的部署**:3 master + 3 replica = 6 节点,允许 **1 master + 其 replica 同时故障**(前提是剩下 2 master 中还有可用 replica)。生产推荐 **3 master + 6 replica**(每个 master 2 副本,容忍 1 master + 1 副本失效)。

---

## 三、数据分片

### 1. 普通 key 的分片

所有 key 在写入前,通过 `CRC16(key) mod 16384` 计算 slot,由 cluster 决定写到哪个 master:

```bash
# 例子:key 经过计算后落在不同 master
SET user:1001    "alice"  → slot 12176 → M2
SET user:1002    "bob"    → slot  8732 → M2
SET order:202401 "data"   → slot  5021 → M1
SET product:88   "phone"  → slot 15623 → M3
```

### 2. hashtag {} 强制同 slot

实际业务中常常需要**多个 key 一起操作**(事务、Lua、`MGET` 等),但默认 CRC16 把它们分散到不同 slot,会报错 `CROSSSLOT`。

**hashtag** 用 `{}` 包裹一段字符串,只对花括号内的内容计算 CRC16,实现**强制同 slot**:

```bash
# 普通 key:分散
SET user:1000.profile  "..."  → slot 12176
SET user:1000.order    "..."  → slot  8732     # 不同 slot

# hashtag 强制同 slot
SET {user:1000}.profile  "..."  → slot  2417
SET {user:1000}.order    "..."  → slot  2417     # 同 slot

# MSET / 事务 / Lua 都可工作
MSET {user:1000}.profile "alice" {user:1000}.order "ORD-001"   # OK
```

**hashtag 实战模式**:

| 业务场景 | hashtag 设计 | 说明 |
|----------|--------------|------|
| 用户维度聚合 | `{user:1000}.profile` / `{user:1000}.order` | 单用户全部数据同 slot |
| 订单-订单项 | `{order:20240101}.info` / `{order:20240101}.item:1` | 父子数据同 slot |
| 购物车 | `{cart:user:1000}` 整体一个 key | 简单粗暴 |
| 分布式锁 | `{lock:order:pay}:202401` | 锁粒度合理 |

> **hashtag 风险**:如果所有用户都用 `{user:userId}` 当 hashtag,数据确实聚合了,**但写入热点会集中到某个 master**。要么 hashtag 后面多挂点随机数 `{user:1000}:profile`、`{user:1000}:rand1.order`;要么按业务显式选择 hashtag 维度。

### 3. 分片重定向: MOVED vs ASK

客户端向错误的节点发送命令时,节点会返回**重定向错误**,客户端据此更新本地路由:

```text
client → M1: SET user:1001 "alice"     # 假设该 key 实际在 M2
M1  ────► client: -MOVED 12176 10.0.0.12:6379
                                          ↑     ↑
                                        slot  真正的 master
```

- **MOVED (永久重定向)**:slot 已经搬到目标节点,客户端应**更新本地 slot 表**,后续请求直接发到目标节点
- **ASK (临时重定向)**:slot **正在迁移**过程中,源节点请客户端**本次**去目标节点尝试,但**不更新本地 slot 表**(因为迁移完成后归属可能又变)

---

## 四、集群架构

### 1. 拓扑总览 (6 节点 3 主 3 从)

```text
                    ┌─────────────────────────────────────────┐
                    │         客户端 (Jedis / Lettuce)        │
                    │   本地缓存 slot → node 路由表           │
                    └─────────────┬───────────────────────────┘
                                  │
            ┌─────────────────────┼─────────────────────┐
            │                     │                     │
       ┌────┴────┐            ┌───┴────┐            ┌───┴────┐
       │  M1     │ ──Gossip──►│  M2    │◄──Gossip──│  M3    │
       │ master  │            │ master │            │ master │
       │ :6379   │            │ :6379  │            │ :6379  │
       │ +bus    │            │ +bus   │            │ +bus   │
       │ :16379  │            │ :16379 │            │ :16379 │
       └────┬────┘            └────────┘            └────────┘
            │ slot 0–5460        slot 5461–10922      slot 10923–16383
            │ (5461 个)          (5462 个)            (5463 个)
            │
       ┌────┴────┐
       │  S1     │ (replica of M1,异步复制)
       │ :6379   │
       │ +bus    │
       │ :16379  │
       └─────────┘
```

每个节点对外开**两个端口**:

| 端口 | 用途 |
|------|------|
| **6379** | 客户端服务端口 (命令 / 数据读写) |
| **+16379** | Cluster Bus (Gossip 协议、故障检测、槽迁移协调) |

> **端口偏移量约定**:服务端口 + 10000 = cluster bus 端口。`cluster-port` 配置项可改偏移量,但 10000 是 Redis 默认也是社区普遍使用。

### 2. 客户端视角

```text
                 客户端维护的 slot 表
  ┌──────────────────────────────────────────────┐
  │ slot 0     → 10.0.0.11:6379  (M1)           │
  │ slot 1     → 10.0.0.11:6379  (M1)           │
  │ ...                                           │
  │ slot 5461  → 10.0.0.12:6379  (M2)           │
  │ ...                                           │
  │ slot 10923 → 10.0.0.13:6379  (M3)           │
  │ ...                                           │
  └──────────────────────────────────────────────┘
```

- 启动时连接**任一节点**,执行 `CLUSTER SLOTS` 拿到完整 slot 表
- 计算 key 的 slot,直接发往对应 master
- 收到 `-MOVED`,**永久更新本地路由**
- 收到 `-ASK`,**本次转发**,不更新路由

### 3. 节点间数据流

```text
   Client write ──► M1 (master)
                       │
                       │  异步复制 (replication stream)
                       ↓
                    S1 (replica)
                       │
                       │  psync / full sync
                       │
                    (故障时 S1 升主)
```

每个 master 持有**完整 slot 区间内**的数据;replica 是该数据的**只读副本**,正常情况接收客户端**读请求**(需开启 `READONLY` 命令)。

---

## 五、部署实战

### 1. 环境规划

| 角色 | IP | 端口 | 配置 |
|------|----|------|------|
| M1 (master) | 10.0.0.11 | 6379 + 16379 | 2C4G |
| S1 (replica) | 10.0.0.14 | 6379 + 16379 | 2C4G |
| M2 (master) | 10.0.0.12 | 6379 + 16379 | 2C4G |
| S2 (replica) | 10.0.0.15 | 6379 + 16379 | 2C4G |
| M3 (master) | 10.0.0.13 | 6379 + 16379 | 2C4G |
| S3 (replica) | 10.0.0.16 | 6379 + 16379 | 2C4G |

> **3 master + 3 replica** 是最小生产集群:允许 1 个 master 故障,replica 自动升主。若允许 1 个 master + 1 replica **同时**故障,需每个 master 至少 2 副本(共 3M + 6S)。

### 2. redis.conf 集群配置

每个节点的 `redis.conf` 中,集群相关最小配置:

```ini
# /etc/redis/redis.conf

# 基础
bind 0.0.0.0
port 6379
daemonize yes
pidfile /var/run/redis_6379.pid
logfile /var/log/redis/redis_6379.log
dir /var/lib/redis/6379

# 集群核心 (只要这 5 行就够了)
cluster-enabled yes
cluster-config-file nodes-6379.conf           # 集群状态文件,自动维护
cluster-node-timeout 15000                    # 节点失联超时 (ms),默认 15000
cluster-announce-ip 10.0.0.11                 # 节点对外 IP (多网卡时必须配)
cluster-announce-port 6379                    # 节点对外服务端口
cluster-announce-bus-port 16379               # 节点对外 cluster bus 端口

# replica 服务 (可选,7.x)
replica-serve-stale-data yes
replica-read-only yes

# 持久化 (推荐)
appendonly yes
appendfilename "appendonly.aof"
appendfsync everysec
```

**关键参数详解**:

| 参数 | 默认 | 推荐 | 说明 |
|------|------|------|------|
| `cluster-enabled` | no | **yes** | 必须开启,否则节点是单机模式 |
| `cluster-config-file` | nodes.conf | `nodes-{port}.conf` | 集群节点信息持久化文件,**不要手工改** |
| `cluster-node-timeout` | 15000ms | 15000~20000ms | 超过该时长未响应,标 PFAIL |
| `cluster-announce-ip` | 自动 | 写死 | 容器化部署必须配,否则节点 IP 错乱 |
| `cluster-require-full-coverage` | yes | **no** | 部分 slot 不可用时,是否拒服务。生产建议 no |
| `cluster-replica-validity-factor` | 10 | 10 | replica 落后太久不能参加选举 |
| `cluster-migration-barrier` | 1 | 1 | replica 迁移到其他 master 的最小剩余数 |
| `cluster-slots-yes-confirmations` | 1 | 2 | 槽迁移要求多数节点确认 |

### 3. 启动所有节点

```bash
# 6 台机器分别执行
redis-server /etc/redis/redis.conf

# 验证
redis-cli -p 6379 PING
# PONG

redis-cli -p 6379 CLUSTER INFO
# cluster_enabled:1
# cluster_known_nodes:1
# cluster_size:0
```

### 4. 自动创建集群 (推荐)

```bash
# 用 redis-cli --cluster create 一键创建
# replicas 1 = 每个 master 一个 replica
redis-cli --cluster create \
    10.0.0.11:6379 \
    10.0.0.12:6379 \
    10.0.0.13:6379 \
    10.0.0.14:6379 \
    10.0.0.15:6379 \
    10.0.0.16:6379 \
    --cluster-replicas 1

# 输出示意:
>>> Performing hash slots allocation on 6 nodes...
Master[0] -> Slots 0 - 5460
Master[1] -> Slots 5461 - 10922
Master[2] -> Slots 10923 - 16383
Adding replica 10.0.0.14:6379 to 10.0.0.11:6379
Adding replica 10.0.0.15:6379 to 10.0.0.12:6379
Adding replica 10.0.0.16:6379 to 10.0.0.13:6379
>>> Trying to optimize slaves allocation...
[OK] All nodes agree about slots configuration.
>>> Check for open slots...
>>> Check slots coverage...
[OK] All 16384 slots covered.
```

执行过程会询问 `Can I set the above configuration? (type 'yes' to accept)`,输入 `yes` 接受。

### 5. 手动创建集群

适合**精细控制**(比如要双副本,或读写分离的 replica 指向特定 master):

```bash
# 第 1 步:让 6 个节点彼此 meet,组成集群
redis-cli -p 6379 -h 10.0.0.11 CLUSTER MEET 10.0.0.12 6379
redis-cli -p 6379 -h 10.0.0.11 CLUSTER MEET 10.0.0.13 6379
redis-cli -p 6379 -h 10.0.0.11 CLUSTER MEET 10.0.0.14 6379
redis-cli -p 6379 -h 10.0.0.11 CLUSTER MEET 10.0.0.15 6379
redis-cli -p 6379 -h 10.0.0.11 CLUSTER MEET 10.0.0.16 6379

# 第 2 步:查看 cluster 节点列表
redis-cli -p 6379 -h 10.0.0.11 CLUSTER NODES
# 6 个节点都显示,但尚未分配 slot

# 第 3 步:给 3 个 master 分配 slot
# M1: 0 – 5460
redis-cli -p 6379 -h 10.0.0.11 CLUSTER ADDSLOTS {0..5460}
# M2: 5461 – 10922
redis-cli -p 6379 -h 10.0.0.12 CLUSTER ADDSLOTS {5461..10922}
# M3: 10923 – 16383
redis-cli -p 6379 -h 10.0.0.13 CLUSTER ADDSLOTS {10923..16383}

# 第 4 步:把 3 个 replica 分别 replicate 到 3 个 master
redis-cli -p 6379 -h 10.0.0.14 CLUSTER REPLICATE <M1-node-id>
redis-cli -p 6379 -h 10.0.0.15 CLUSTER REPLICATE <M2-node-id>
redis-cli -p 6379 -h 10.0.0.16 CLUSTER REPLICATE <M3-node-id>

# 验证
redis-cli -p 6379 -h 10.0.0.11 CLUSTER INFO
# cluster_state:ok
# cluster_slots_assigned:16384
# cluster_size:3
```

> `<M1-node-id>` 在 `CLUSTER NODES` 输出中,每行第一列是 40 位十六进制 ID(类似 `07c37dfeb235213a872192d90877d0cd55635b91`)。

### 6. Docker Compose 部署示例

```yaml
# docker-compose.yml
version: "3.8"

services:
  redis-m1:
    image: redis:7.4
    container_name: redis-m1
    command: >
      redis-server
        --cluster-enabled yes
        --cluster-config-file nodes.conf
        --cluster-node-timeout 15000
        --cluster-announce-ip 10.0.0.11
        --cluster-announce-port 6379
        --cluster-announce-bus-port 16379
        --appendonly yes
    ports:
      - "6379:6379"
      - "16379:16379"
    networks:
      redis-net:
        ipv4_address: 10.0.0.11

  redis-m2:
    image: redis:7.4
    container_name: redis-m2
    command: >
      redis-server
        --cluster-enabled yes
        --cluster-config-file nodes.conf
        --cluster-node-timeout 15000
        --cluster-announce-ip 10.0.0.12
        --cluster-announce-port 6379
        --cluster-announce-bus-port 16379
        --appendonly yes
    ports:
      - "6380:6379"
      - "16380:16379"
    networks:
      redis-net:
        ipv4_address: 10.0.0.12

  redis-m3:
    image: redis:7.4
    container_name: redis-m3
    command: >
      redis-server
        --cluster-enabled yes
        --cluster-config-file nodes.conf
        --cluster-node-timeout 15000
        --cluster-announce-ip 10.0.0.13
        --cluster-announce-port 6379
        --cluster-announce-bus-port 16379
        --appendonly yes
    ports:
      - "6381:6379"
      - "16381:16379"
    networks:
      redis-net:
        ipv4_address: 10.0.0.13

  redis-s1:
    image: redis:7.4
    container_name: redis-s1
    command: >
      redis-server
        --cluster-enabled yes
        --cluster-config-file nodes.conf
        --cluster-node-timeout 15000
        --cluster-announce-ip 10.0.0.14
        --cluster-announce-port 6379
        --cluster-announce-bus-port 16379
        --appendonly yes
    networks:
      redis-net:
        ipv4_address: 10.0.0.14

  redis-s2:
    image: redis:7.4
    container_name: redis-s2
    command: >
      redis-server
        --cluster-enabled yes
        --cluster-config-file nodes.conf
        --cluster-node-timeout 15000
        --cluster-announce-ip 10.0.0.15
        --cluster-announce-port 6379
        --cluster-announce-bus-port 16379
        --appendonly yes
    networks:
      redis-net:
        ipv4_address: 10.0.0.15

  redis-s3:
    image: redis:7.4
    container_name: redis-s3
    command: >
      redis-server
        --cluster-enabled yes
        --cluster-config-file nodes.conf
        --cluster-node-timeout 15000
        --cluster-announce-ip 10.0.0.16
        --cluster-announce-port 6379
        --cluster-announce-bus-port 16379
        --appendonly yes
    networks:
      redis-net:
        ipv4_address: 10.0.0.16

networks:
  redis-net:
    driver: bridge
    ipam:
      config:
        - subnet: 10.0.0.0/24
```

启动并初始化:

```bash
docker-compose up -d

# 任意一个节点容器内执行
docker exec -it redis-m1 redis-cli --cluster create \
  10.0.0.11:6379 10.0.0.12:6379 10.0.0.13:6379 \
  10.0.0.14:6379 10.0.0.15:6379 10.0.0.16:6379 \
  --cluster-replicas 1
```

---

## 六、集群扩缩容

### 1. 添加节点

**场景**:从 3 master 扩到 4 master,需要新增一对节点(新 master + 新 replica)。

```bash
# 第 1 步:启动新节点 (10.0.0.17 + 10.0.0.18)
redis-server /etc/redis/redis.conf

# 第 2 步:加入集群 (cluster meet)
redis-cli -p 6379 -h 10.0.0.11 CLUSTER MEET 10.0.0.17 6379
redis-cli -p 6379 -h 10.0.0.11 CLUSTER MEET 10.0.0.18 6379

# 验证
redis-cli -p 6379 -h 10.0.0.11 CLUSTER NODES
# 此时 10.0.0.17 角色为 master,但没有分配 slot (空 master)
# 10.0.0.18 角色为 master,需后续让它成为 10.0.0.17 的 replica

# 第 3 步:把 10.0.0.18 设为 10.0.0.17 的 replica
redis-cli -p 6379 -h 10.0.0.18 CLUSTER REPLICATE <10.0.0.17-node-id>
```

### 2. 在线迁移 slot (reshard)

把部分 slot 从老 master 搬到新 master,需要搬数据,生产中耗时**分钟 ~ 小时**级别,业务可能有短暂延迟。

```bash
# redis-cli --cluster reshard 交互式
redis-cli --cluster reshard 10.0.0.11:6379

# 交互问答:
# How many slots do you want to move (from 1 to 16384)? 4096     # 搬 1/4 给新 master
# What is the receiving node ID? <10.0.0.17-node-id>             # 目标 master
# Source node #1: <10.0.0.11-node-id>                            # 从 M1 搬
# Source node #2: done
# Do you want to proceed with the proposed plan? yes

# 非交互式
redis-cli --cluster reshard 10.0.0.11:6379 \
    --cluster-from <M1-node-id> \
    --cluster-to <M4-node-id> \
    --cluster-slots 4096 \
    --cluster-yes
```

迁移后 slot 分布:

```text
原本:
  M1: 0–5460
  M2: 5461–10922
  M3: 10923–16383

迁移 4096 slot 后 (从 M1 搬给 M4):
  M1: 1365–5460            (4096 个 slot 被搬走)
  M4: 0–1364, 5461–6820    (共 2724 个)
  M2: 6821–10922
  M3: 10923–16383
```

### 3. 槽迁移过程 (核心机制)

`reshard` 内部按 slot 逐个迁移,每个 slot 迁移流程:

```text
源 M1                    目标 M4                   client
   │                         │                       │
   │  1. CLUSTER SETSLOT <slot> IMPORTING <M4-id>  │
   │ ◄────────────────────────────────────────────── │
   │                         │                       │
   │                         │  2. CLUSTER SETSLOT <slot> MIGRATING <M1-id> │
   │ ──────────────────────────────────────────────► │
   │                         │                       │
   │  3. MIGRATE host port "" 0 <keys> timeout       │
   │ ──────────────────────────────────────────────► │
   │       (原子地把 keys 一个个 RENAME + DUMP+RESTORE)│
   │                         │                       │
   │                         │  4. cluster bus 通知所有节点:slot 由 M1 → M4
   │                         │                       │
   │  期间若有 client 写该 slot 的 key:              │
   │     - 命中 M1 已经迁走的 key → -ASK <slot> M4   │
   │     - 客户端先 ASKING 再发往 M4                 │
   │     - 不更新本地 slot 表 (ASK 是临时重定向)      │
   │                         │                       │
   │  5. CLUSTER SETSLOT <slot> NODE <M4-id> (稳定)  │
   │                         │                       │
   │  此后 client 写该 slot → -MOVED <slot> M4       │
   │  (客户端更新本地 slot 表,MOVED 是永久重定向)      │
```

`MIGRATE` 命令的细节(简化版):
- 源节点遍历该 slot 内所有 key
- 对每个 key:序列化(DUMP)→发到目标节点(RESTORE)→本地删除
- 整个过程**对单个 key 是原子的**

### 4. 删除节点

```bash
# 第 1 步:把要删除节点上的 slot 全部迁走
redis-cli --cluster reshard 10.0.0.11:6379 \
    --cluster-from <要删除节点-node-id> \
    --cluster-to <目标master-node-id> \
    --cluster-slots 16384   # 该节点上的 slot 数量
    --cluster-yes

# 第 2 步:如果是 master,先迁走 slot;replica 不需要
# 第 3 步:从集群中"忘记"该节点 (需在所有其他节点上执行)
redis-cli -p 6379 -h 10.0.0.11 CLUSTER FORGET <要删除节点-node-id>
redis-cli -p 6379 -h 10.0.0.12 CLUSTER FORGET <要删除节点-node-id>
... (每个节点都要 forget)

# 第 4 步:关闭 redis 进程
redis-cli -p 6379 -h 10.0.0.17 SHUTDOWN NOSAVE
```

> **坑点**:`CLUSTER FORGET` 是**有时效**的(默认 60 秒),如果节点 A 在 60 秒内收到 Gossip 又"看到"该节点,会自动把它加回。所以删除后应**立即 SHUTDOWN**,或者用 `redis-cli --cluster del-node` 工具化操作。

```bash
# 工具化删除(更安全)
redis-cli --cluster del-node 10.0.0.11:6379 <要删除节点-node-id>
```

---

## 七、故障转移

### 1. 故障检测的两层判定

Redis Cluster 故障检测分**主观下线 (PFAIL)** 和**客观下线 (FAIL)** 两步:

```text
   M1 (master) ──ping──► M2 (master) ──ping──► M3 (master)
      ▲                     ▲                     ▲
      │  超时未响应          │  超时未响应          │  超时未响应
      │ (cluster-node-timeout)                    │
      │                     │                     │
      ▼                     ▼                     ▼
   ┌──────────────────────────────────────────────┐
   │  各节点本地标记某节点为 PFAIL (Possible Fail)  │
   │  只是"我"觉得它挂了,不一定真挂                 │
   └──────────────────────────────────────────────┘

   当**大多数 master** 都认为 X 是 PFAIL 时:
   X 被标记为 FAIL (客观下线),全集群广播

   ┌──────────────────────────────────────────────┐
   │  FAIL → 触发 replica 选举 → 新 master 接管    │
   └──────────────────────────────────────────────┘
```

### 2. 副本选举 (Replica Election)

FAIL 触发后,该 master 的 replica 发起选举:

```text
1. replica 把自己的 epoch (选举期号) 加 1
   并广播 CLUSTERMSG_TYPE_FAILOVER_AUTH_REQUEST

2. 所有 master 收到请求,基于以下规则投票:
   - 每个 epoch 内,一个 master 只能投一票
   - replica 数据越新(对比 replication offset),越有优势
   - 多数 master 同意 (cluster_size / 2 + 1) 即当选

3. replica 收到多数票 → 把自己切换为 master
   - 执行 CLUSTER REPLICATE NO ONE
   - 更新本地 clusterState
   - 广播 pong 通知其他节点

4. 其他节点更新 slot 表:该 master 已更换
```

**选举条件**(replica 必须满足才能成为候选):

| 条件 | 说明 |
|------|------|
| replica 在线 | 与大多数 master 保持心跳 |
| 数据不能太旧 | `last_io_time` 在 `(now - node-timeout * replica-validity-factor)` 内 |
| 未在迁移 | `cluster-migration-barrier` 剩余要求满足 |

### 3. 故障转移时序图

```text
时间   节点           动作
────────────────────────────────────────────────────────────────
T0     M1 正常服务, S1 持续复制
       │
T1     M1 机器宕机 (断网/进程崩溃)
       │
T2     S1 发现与 M1 心跳超时
       S1 把 M1 标为 PFAIL (主观下线)
       │
T3     S1 收到来自其他 master 的 ping/pong,
       得知 M1 在其他节点也已 PFAIL
       │
T4     当大多数 master (≥ 2 of 3) 都认为 M1 PFAIL
       → M1 被标记为 FAIL,集群广播 -failover
       │
T5     S1 自增 epoch,广播 FAILOVER_AUTH_REQUEST
       │
T6     M2、M3 收到请求,投票
       (M2 同意, M3 同意 → 2/3 多数)
       │
T7     S1 收到 2 张同意票,达到多数
       S1 执行 SLAVEOF NO ONE → 切换为 master
       │
T8     S1 把 M1 负责的 slot (假设 0–5460) 接管
       S1 通过 Gossip 广播新拓扑
       │
T9     客户端收到新拓扑 (或通过 MOVED 重定向)
       写入请求转到新 master (S1)
       │
T10    M1 故障恢复后 (如重启)
       M1 检测到自己不再是 master,自动降级为 replica
       尝试 replicate 当前 master (S1)
       │
T11    集群恢复正常 (S1 是新 master, M1 是新 replica)
────────────────────────────────────────────────────────────────
```

**总耗时**:通常 **15 ~ 30 秒**(取决于 `cluster-node-timeout` 默认 15s)。

### 4. cluster-node-timeout 的影响

| 配置 | 含义 | 调小效果 | 调大效果 |
|------|------|----------|----------|
| `cluster-node-timeout` | 节点失联多久算 PFAIL | 故障检测更快,但**误判率高**(网络抖动会被误切) | 故障检测慢,但稳定 |

> **生产建议**:**15 ~ 20 秒**是经验值。如果网络环境差(跨机房),建议放到 **20 ~ 30 秒**。

### 5. 脑裂避免

**Cluster 不会脑裂**。原因:

- 选举必须获得**大多数 master 同意**(quorum)
- 老 master 如果未下线,会持续向其他 master 发心跳,新 replica 无法获得多数票
- 即使老 master 真复活,发现自己 slot 已被接管,**自动降级**为 replica

```text
      假设 M1 网络分区 (与 M2、M3 断开)
   ┌──────────┐                ┌──────────────┐
   │  M1      │   分区隔离      │  M2, M3      │
   │  (孤立)  │ ◄────────────► │              │
   └──────────┘                └──────────────┘
         │                            │
         │  M1 收不到 M2/M3 心跳     │
         │  但 M1 也无法广播 FAIL     │
         ▼                            ▼
   S1 仍在 M2 那边,             M2/M3 多数派认定 M1 FAIL
   所以 S1 升主,                S1 成为新 master
   M1 此时降级为 replica       M1 不再接收客户端写
```

---

## 八、客户端接入

### 1. 客户端对比

| 客户端 | 语言 | 智能路由 | 多 key | Spring 集成 |
|--------|------|----------|--------|-------------|
| **Jedis** | Java | 客户端模式 (JedisCluster) | 支持(hashtag) | spring-data-redis |
| **Lettuce** | Java | Netty 异步 | 支持(hashtag) | spring-data-redis (默认) |
| **redis-py Cluster** | Python | 客户端模式 | 支持(hashtag) | - |
| **go-redis Cluster** | Go | 客户端模式 | 支持(hashtag) | - |
| **ioredis** | Node.js | 客户端模式 | 支持(hashtag) | - |

### 2. JedisCluster

```java
import redis.clients.jedis.HostAndPort;
import redis.clients.jedis.JedisCluster;
import redis.clients.jedis.JedisPoolConfig;

public class RedisClusterDemo {
    public static void main(String[] args) {
        // 1. 配置连接池
        JedisPoolConfig poolConfig = new JedisPoolConfig();
        poolConfig.setMaxTotal(100);
        poolConfig.setMaxIdle(20);
        poolConfig.setMinIdle(5);
        poolConfig.setTestOnBorrow(true);

        // 2. 至少给一个节点,客户端会 CLUSTER SLOTS 拿到全拓扑
        Set<HostAndPort> nodes = new HashSet<>();
        nodes.add(new HostAndPort("10.0.0.11", 6379));
        nodes.add(new HostAndPort("10.0.0.12", 6379));
        nodes.add(new HostAndPort("10.0.0.13", 6379));

        // 3. 创建 JedisCluster
        JedisCluster cluster = new JedisCluster(
            nodes,
            2000,                  // connection timeout
            2000,                  // so timeout
            5,                     // max attempts (重定向)
            "Redis@123",           // password (可选)
            poolConfig
        );

        // 4. 使用 (与单机 Jedis 几乎一致)
        cluster.set("user:1001", "alice");
        String value = cluster.get("user:1001");
        System.out.println(value);

        // 5. hashtag 强制同 slot
        cluster.set("{user:1000}.profile", "alice");
        cluster.set("{user:1000}.order",   "ORD-001");
        cluster.mset("{user:1000}.age", "25", "{user:1000}.city", "Beijing");

        cluster.close();
    }
}
```

### 3. Lettuce Cluster

```java
import io.lettuce.core.RedisURI;
import io.lettuce.core.cluster.RedisClusterClient;
import io.lettuce.core.cluster.api.StatefulRedisClusterConnection;
import io.lettuce.core.cluster.api.sync.RedisAdvancedClusterCommands;

public class LettuceClusterDemo {
    public static void main(String[] args) {
        // 1. 构造 URI (可以只填一个种子节点)
        RedisURI uri = RedisURI.builder()
            .withHost("10.0.0.11")
            .withPort(6379)
            .withPassword("Redis@123".toCharArray())
            .build();

        // 2. 创建 ClusterClient
        RedisClusterClient client = RedisClusterClient.create(uri);

        // 3. 获取连接 (线程安全,可复用)
        StatefulRedisClusterConnection<String, String> conn = client.connect();

        // 4. 同步 API
        RedisAdvancedClusterCommands<String, String> sync = conn.sync();
        sync.set("user:1001", "alice");
        String v = sync.get("user:1001");
        System.out.println(v);

        // 5. 异步 API (Netty,高性能)
        conn.async().set("user:1002", "bob")
                    .thenAccept(rst -> System.out.println("OK: " + rst));

        // 6. hashtag 强制同 slot
        sync.mset("{user:1000}.profile", "alice",
                  "{user:1000}.order",   "ORD-001");

        client.shutdown();
    }
}
```

### 4. Spring Data Redis 集群配置

**application.yml**:

```yaml
spring:
  redis:
    cluster:
      nodes:
        - 10.0.0.11:6379
        - 10.0.0.12:6379
        - 10.0.0.13:6379
      max-redirects: 3               # MOVED 重定向最多尝试次数
      # password: Redis@123          # 如果有密码
    timeout: 2000
    lettuce:
      pool:
        max-active: 100
        max-idle: 20
        min-idle: 5
      shutdown-timeout: 200
```

**Java Config**:

```java
@Configuration
public class RedisClusterConfig {

    @Bean
    public RedisClusterConfiguration redisClusterConfiguration() {
        RedisClusterConfiguration cfg = new RedisClusterConfiguration(
            List.of("10.0.0.11:6379", "10.0.0.12:6379", "10.0.0.13:6379")
        );
        cfg.setMaxRedirects(3);
        cfg.setPassword("Redis@123");
        return cfg;
    }

    @Bean
    public LettuceConnectionFactory lettuceConnectionFactory(
            RedisClusterConfiguration cfg) {
        return new LettuceConnectionFactory(cfg);
    }

    @Bean
    public RedisTemplate<String, String> redisTemplate(
            LettuceConnectionFactory factory) {
        RedisTemplate<String, String> tpl = new RedisTemplate<>();
        tpl.setConnectionFactory(factory);
        tpl.setKeySerializer(new StringRedisSerializer());
        tpl.setValueSerializer(new StringRedisSerializer());
        return tpl;
    }
}
```

使用:

```java
@Service
public class OrderService {
    @Autowired
    private RedisTemplate<String, String> redisTemplate;

    public void saveOrder(String userId, String orderId, String data) {
        // 用 hashtag 强制同 slot,事务/MGET 才不会报 CROSSSLOT
        String key = "{user:" + userId + "}.order:" + orderId;
        redisTemplate.opsForValue().set(key, data);
    }
}
```

### 5. MOVED 重定向流程

```text
Client (本地 slot 表)               M1                  M3 (真正的 master)
────────────────────────────────────────────────────────────────────────
1. 计算 slot
   SET user:1001 "alice"
   CRC16("user:1001") % 16384 = 12176
   查本地 slot 表: 12176 → M1 (本地缓存认为)
        │
        ▼
2. 发往 M1
   SET user:1001 "alice"  ──────────────► M1
                                            │
                                            │ slot 12176 不归我
                                            │ 真正属于 M3
                                            ▼
3. M1 返回
   -MOVED 12176 10.0.0.13:6379
        ◄──────────────────────────────────
        │
        ▼
4. 客户端更新本地 slot 表:
   slot 12176 → 10.0.0.13:6379 (M3)
        │
        ▼
5. 重试 SET user:1001 "alice"
        ───────────────────────────────► M3 (master,实际处理)
                                            │
                                            ▼
                                          +OK
        ◄──────────────────────────────────
        │
        ▼
6. 客户端返回成功
```

### 6. ASK 重定向流程 (迁移中)

```text
Client (本地 slot 表)            M1 (源)             M4 (目标,正在迁入 slot 100)
─────────────────────────────────────────────────────────────────────────
1. SET user:5000 "bob"
   slot 100 → 本地表: M1
        │
        ▼
2. 发往 M1
   SET user:5000 "bob"  ──────────────► M1
                                            │
                                            │ slot 100 正在迁给 M4
                                            │ user:5000 还没迁走
                                            │ 但 import 一条新 key
                                            ▼
3. M1 返回
   -ASK 100 10.0.0.17:6379
        ◄──────────────────────────────────
        │
        ▼
4. 客户端**不更新**本地 slot 表 (ASK 是临时)
   但先发一条 ASKING 命令到 M4
        │
        ▼
5. 发往 M4
   ASKING
   SET user:5000 "bob"  ───────────────► M4
                                            │
                                            │ M4 接收,写入 slot 100
                                            ▼
                                          +OK
        ◄──────────────────────────────────
```

---

## 九、集群命令

### 1. 集群状态查询

```bash
# 集群基本信息 (一句话总结)
> CLUSTER INFO
cluster_state:ok                                  # 集群状态:ok / fail
cluster_slots_assigned:16384                      # 已分配 slot 数
cluster_slots_ok:16384                            # 正常 slot 数
cluster_slots_pfail:0                             # 疑似故障
cluster_slots_fail:0                              # 已故障
cluster_known_nodes:6                             # 集群节点数
cluster_size:3                                    # master 数
cluster_current_epoch:6                           # 当前选举 epoch
cluster_my_epoch:1                                # 当前节点 epoch
cluster_stats_messages_sent:18923                 # 累计发出 Gossip
cluster_stats_messages_received:18912             # 累计接收 Gossip

# 节点列表 (一行一节点)
> CLUSTER NODES
07c37dfeb235213a872192d90877d0cd55635b91 10.0.0.11:6379@16379 myself,master - 0 1700000000000 1 connected 0-5460
67ed2db8d677e59ec4a4cefb06858cf2a1a89fa1 10.0.0.12:6379@16379 master - 0 1700000000100 2 connected 5461-10922
292f8b365bb7edb5e285caf0b7e6ddc7265d2f4f 10.0.0.13:6379@16379 master - 0 1700000000200 3 connected 10923-16383
e7d1eecce10fd6bb5eb35b9f99a514335d9ba9ca 10.0.0.14:6379@16379 slave 07c37dfeb235213a872192d90877d0cd55635b91 0 1700000000300 1 connected
...
# 字段含义:
#   <id> <ip:port@bus-port> <flags> <master-id> <ping-sent> <pong-recv> <config-epoch> <link-state> <slot>

# slot 分布
> CLUSTER SLOTS
1) 1) (integer) 0
   2) (integer) 5460
   3) 1) "10.0.0.11"
      2) (integer) 6379
   4) 1) "10.0.0.14"      # 该 master 的 replica
      2) (integer) 6379
2) 1) (integer) 5461
   2) (integer) 10922
   3) 1) "10.0.0.12"
      2) (integer) 6379
   ...

# 某个 key 落在哪个 slot
> CLUSTER KEYSLOT "user:1001"
(integer) 12176

# slot 内 key 数量
> CLUSTER COUNTKEYSINSLOT 12176
(integer) 17
```

### 2. 集群运维命令

```bash
# 节点加入
CLUSTER MEET <ip> <port>
# 节点离开 (从集群中"忘记"该节点)
CLUSTER FORGET <node-id>
# replica 关联 master
CLUSTER REPLICATE <master-node-id>
# 自降为 master (选举成功后执行)
CLUSTER REPLICATE NO ONE

# 手工故障转移 (无故障演练 / 数据中心切换)
CLUSTER FAILOVER                # 在 replica 上执行,正常切换
CLUSTER FAILOVER FORCE          # 强制,即使 master 还活着
CLUSTER FAILOVER TAKEOVER       # (7.x) 强制接管,无需其他 master 同意

# slot 操作
CLUSTER ADDSLOTS <slot> [slot ...]               # 把 slot 分配给本节点
CLUSTER DELSLOTS <slot> [slot ...]               # 取消本节点 slot 持有
CLUSTER SETSLOT <slot> NODE <node-id>            # 把 slot 交给指定节点
CLUSTER SETSLOT <slot> MIGRATING <node-id>       # 把 slot 迁出到指定节点
CLUSTER SETSLOT <slot> IMPORTING <node-id>       # 从指定节点迁入 slot

# 迁移 key
MIGRATE <host> <port> "" 0 <keys> <timeout>      # 原子迁移 key
```

### 3. redis-cli --cluster 工具集

```bash
# 创建集群
redis-cli --cluster create <ip:port>... --cluster-replicas 1

# 检查集群健康
redis-cli --cluster check 10.0.0.11:6379

# 查看集群信息 (汇总)
redis-cli --cluster info 10.0.0.11:6379

# 重新分配 slot (均衡)
redis-cli --cluster rebalance 10.0.0.11:6379

# 添加节点
redis-cli --cluster add-node <new-ip:port> <existing-ip:port>
# (默认作为 master 加入,不带 slot)

# 添加为 replica
redis-cli --cluster add-node <new-ip:port> <existing-ip:port> \
    --cluster-slave --cluster-master-id <master-node-id>

# 重新分片
redis-cli --cluster reshard <ip:port>

# 删除节点
redis-cli --cluster del-node <ip:port> <node-id>

# 修复 (尝试把失败 replica 重新加入)
redis-cli --cluster fix <ip:port>

# 设置超时
redis-cli --cluster call <ip:port> <command>
# 例:在所有节点上 CONFIG GET maxmemory
redis-cli --cluster call 10.0.0.11:6379 CONFIG GET maxmemory
```

---

## 十、集群限制

### 1. 多 key 操作必须同 slot

```bash
# 错误:CROSSSLOT
> MSET user:1 "alice" user:2 "bob"
(error) CROSSSLOT Keys in request don't hash to the same slot

# 解决:hashtag
> MSET {user}:1 "alice" {user}:2 "bob"
OK
```

### 2. 不支持多数据库

Cluster 模式下,**只能使用 db 0**:

```bash
> SELECT 1
(error) ERR SELECT is not allowed in cluster mode
```

如果需要"逻辑库"隔离,用 **key 前缀** 或 **独立 Cluster**。

### 3. 不支持跨 slot 事务

```bash
# MULTI / EXEC 不允许跨 slot
> MULTI
> SET user:1 "alice"          # slot 12176
> SET order:1 "data"          # slot  8732
> EXEC
(error) CROSSSLOT ...
```

> **解决**:
> 1. hashtag 强制同 slot
> 2. 改用 Lua 脚本(单线程原子执行)
> 3. 应用层两阶段提交(性能差,慎用)

### 4. KEYS / FLUSHDB 等危险命令

```bash
# 在某 master 上 KEYS *,只能看到本 master 的 key,看不到其他 master
> KEYS *
1) "user:1001"
2) "user:1002"

# 在所有节点执行 (工具)
redis-cli --cluster call 10.0.0.11:6379 KEYS "user:*"
```

**生产禁止直接用 `KEYS *` / `FLUSHDB`**,会阻塞整个节点,推荐用 `SCAN`。

### 5. 其他限制

| 操作 | 限制 | 解决 |
|------|------|------|
| `MGET/MSET` 跨 slot | 报错 CROSSSLOT | hashtag |
| `RENAME` 跨 slot | 报错 CROSSSLOT | hashtag |
| `KEYS` | 单节点可见性 | `SCAN` + 遍历所有节点 |
| `FLUSHDB/FLUSHALL` | 单节点 | `redis-cli --cluster call ... FLUSHDB` |
| `SELECT n` | 不支持 | key 前缀 |
| 多 key Lua | CROSSSLOT | hashtag 强制同 slot |
| 事务 `MULTI/EXEC` | 跨 slot 报错 | hashtag 或改 Lua |
| Pub/Sub | 集群模式下只能订阅**所在节点**的 channel | 用 `redis-py` ClusterPubSub 或自己广播 |

---

## 十一、集群的优缺点

### 1. 优点

| 维度 | 描述 |
|------|------|
| **数据分片** | 16384 slot 哈希分片,水平扩展,突破单机内存瓶颈 |
| **去中心化** | 无 Proxy,所有节点平等,故障无单点 |
| **自动故障转移** | master 故障,replica 自动选举升主,业务影响小 |
| **客户端智能路由** | 客户端本地缓存 slot 表,绝大部分请求**直连**目标节点,无中间代理延迟 |
| **在线扩缩容** | `cluster reshard` 在线迁移 slot,不停服 |
| **官方支持** | Redis 团队长期维护,生态完善,文档丰富 |
| **Gossip 协议** | 节点间状态最终一致,无需中心协调 |
| **副本可读** | replica 开启 `READONLY` 后可承担读流量,提升读吞吐 |

### 2. 缺点

| 维度 | 描述 |
|------|------|
| **多 key 限制** | 事务、Lua、`MGET` 等必须 hashtag 强制同 slot,业务改造 |
| **不能 SELECT** | 只能 db 0,逻辑隔离靠 key 前缀 |
| **不支持多 key 查询** | 没有类似 SQL 的跨 shard JOIN / 聚合 |
| **跨 slot 性能** | hashtag 设计不当会导致单 master 热点 |
| **运维复杂度** | 节点、slot、reshard、failover 都要懂 |
| **批量操作复杂度** | `pipeline` 在 cluster 下需客户端把同 slot 的命令合并 |
| **小规模不划算** | 1 ~ 2 个 master 的 Cluster,运维成本反超收益 |
| **大 key 风险** | 单 key 过大影响 slot 迁移(需逐个 key MIGRATE) |
| **迁移不透明** | reshard 期间部分请求会 -ASK 重定向,客户端需正确处理 |

---

## 十二、集群监控

### 1. redis-cli --cluster check

```bash
redis-cli --cluster check 10.0.0.11:6379

# 输出:
# [OK] All nodes agree about slots configuration.
# [OK] All 16384 slots covered.
# Master[0] -> Slots 0 - 5460
# Master[1] -> Slots 5461 - 10922
# Master[2] -> Slots 10923 - 16383
# M: 07c37dfe... 10.0.0.11:6379
#    slots:[0-5460] (5461 slots) master
#    1 additional replica(s)
# S: e7d1eecc... 10.0.0.14:6379
#    slots: (0 slots) slave
#    replicates 07c37dfe... (M1)
# [OK] All nodes agree about slots configuration.
# [OK] All 16384 slots covered.
# [OK] All nodes agree about master-slave mapping.
# [OK] No hash slots in FAIL state.
```

### 2. redis-cli --cluster info

```bash
redis-cli --cluster info 10.0.0.11:6379

# 输出 (每节点一行):
# 10.0.0.11:6379 (07c37dfe...) -> 0 keys | 5461 slots | 1 slaves
# 10.0.0.12:6379 (67ed2db8...) -> 0 keys | 5462 slots | 1 slaves
# 10.0.0.13:6379 (292f8b36...) -> 0 keys | 5464 slots | 1 slaves
# 10.0.0.14:6379 (e7d1eecc...) -> 0 keys | 0 slots | 0 slaves
# ...
# [OK] 0 keys in 3 masters.
# 0.00 keys per slot on average.
```

### 3. redis-cli --cluster rebalance

slot 在 master 间分配不均时(比如后续业务增长,M1 的 slot 区间挤了太多 key),可执行 rebalance:

```bash
redis-cli --cluster rebalance 10.0.0.11:6379

# 询问:
# How many slots do you want to move? (自动计算)
# 或指定权重:
# --cluster-weight <node-id>=<weight>

# 自动模式 (推荐):
redis-cli --cluster rebalance 10.0.0.11:6379 \
    --cluster-auto                  # 自动权重 (按内存使用率)

# 限制某些 master 不参与再平衡:
redis-cli --cluster rebalance 10.0.0.11:6379 \
    --cluster-unreachable-master <node-id>
```

### 4. 关键监控指标

```bash
# 集群状态 (应用层打点)
redis-cli -p 6379 CLUSTER INFO | grep cluster_state

# slot 完整度
redis-cli -p 6379 CLUSTER INFO | grep cluster_slots_ok

# Gossip 流量 (异常高说明节点可能不稳)
redis-cli -p 6379 CLUSTER INFO | grep cluster_stats_messages_sent
redis-cli -p 6379 CLUSTER INFO | grep cluster_stats_messages_received

# 已知节点数 (应为实际节点数)
redis-cli -p 6379 CLUSTER INFO | grep cluster_known_nodes

# 当前 epoch (频繁变化说明频繁 failover)
redis-cli -p 6379 CLUSTER INFO | grep cluster_current_epoch

# replica 延迟 (重要)
redis-cli -p 6379 -h 10.0.0.14 INFO replication | grep master_last_io_seconds

# 节点内存
redis-cli -p 6379 INFO memory | grep used_memory_human

# 客户端连接数
redis-cli -p 6379 INFO clients | grep connected_clients

# 慢查询
redis-cli -p 6379 SLOWLOG GET 10
```

**告警阈值建议**:

| 指标 | 告警阈值 | 说明 |
|------|----------|------|
| `cluster_state` | != ok | 集群故障,立刻告警 |
| `cluster_slots_ok` | < 16384 | 有 slot 不可用 |
| `cluster_known_nodes` | 实际节点数 ±1 | 节点意外增减 |
| `master_last_io_seconds` | > 30 | replica 同步延迟 |
| `connected_clients` | > 80% maxclients | 连接接近上限 |
| `used_memory` | > 70% maxmemory | 内存接近上限 |

---

## 十三、数据迁移 (在线扩缩容)

### 1. 完整流程回顾

```text
                  扩缩容前的 3 master
   ┌────────────────────────────────────┐
   │ M1 (0–5460)    M2 (5461–10922)   M3 (10923–16383)
   └────────────────────────────────────┘
                       │
                       │ 业务增长,加 1 master (M4)
                       ▼
   ┌──────────────────────────────────────────────┐
   │ 1. 新节点 10.0.0.17 启动 cluster-enabled      │
   │ 2. CLUSTER MEET 加入集群 (空 master)           │
   │ 3. (可选) 10.0.0.18 作为 replica 加入          │
   │ 4. CLUSTER REPLICATE 关联                     │
   │ 5. redis-cli --cluster reshard 搬 4096 slot   │
   │ 6. (可选) rebalance 让 slot 更均衡              │
   └──────────────────────────────────────────────┘
                       │
                       ▼
                  扩缩容后的 4 master
   ┌─────────────────────────────────────────────────────┐
   │ M1 (1365–5460)  M4 (0–1364, 5461–6820)             │
   │ M2 (6821–10922) M3 (10923–16383)                   │
   └─────────────────────────────────────────────────────┘
```

### 2. 客户端感知 (ASK vs MOVED)

迁移过程中,客户端要正确区分两种重定向:

| 重定向 | 含义 | 客户端行为 | 是否更新本地 slot 表 |
|--------|------|-----------|----------------------|
| **-MOVED slot ip:port** | slot 已稳定在新节点 | **永久更新**,后续直连新节点 | **是** |
| **-ASK slot ip:port** | slot 正在迁移中,临时请到目标节点试 | **本次** ASKING + 转交 | **否** |

```text
         迁移前        迁移中            迁移后
        ┌─────────┐  ┌──────────┐  ┌──────────┐
slot 100│   M1    │  │  M1 ──►  │  │   M4     │
        └─────────┘  │  M4      │  └──────────┘
                     │  (ing)   │
                     └──────────┘

迁移中:
  client 写 slot 100 的 key
    ↓
  发往 M1 (本地 slot 表仍是 M1)
    ↓
  M1 判断:这个 key 我这没有,正在迁往 M4
    ↓
  -ASK 100 M4:port   ← 临时
    ↓
  客户端:
    1. 记下 M4 是临时目标
    2. 发 ASKING 告诉 M4 "我不是乱发的"
    3. 重发原命令
    ↓
  M4 处理 + 返回 OK
    ↓
  客户端:不更新本地 slot 表 (因为迁移没完成)

迁移完成后:
  客户端写 slot 100
    ↓
  发往 M1
    ↓
  M1 判断:这个 slot 不归我了 (已迁完)
    ↓
  -MOVED 100 M4:port  ← 永久
    ↓
  客户端:更新本地 slot 表 (slot 100 → M4)
    ↓
  后续请求直接发 M4
```

### 3. 迁移过程业务影响

| 维度 | 影响 |
|------|------|
| **可用性** | 不停服,迁移过程正常服务 |
| **延迟** | 迁移中的 slot 内 key 第一次写会 -ASK,客户端重试,延迟略增 |
| **吞吐量** | MIGRATE 是阻塞命令,源节点迁移期间 IO 略降 |
| **数据一致性** | 单 key 原子迁,不会丢;但迁移过程中并发写的 key 要靠业务幂等 |
| **回滚** | 迁移不可逆,需提前评估;迁移失败只能重新 reshard |

**减小业务影响**:

```bash
# 1. 限制单次迁移的 key 数 (减少单次 MIGRATE 的阻塞时间)
#    通过 --pipeline 参数
redis-cli --cluster reshard 10.0.0.11:6379 \
    --cluster-from <src-id> \
    --cluster-to <dst-id> \
    --cluster-slots 100 \         # 一次只迁 100 个 slot
    --cluster-pipeline 10         # 每批 10 个 key,降低单次阻塞
    --cluster-yes

# 2. 低峰期迁移 (业务凌晨执行)

# 3. 客户端开启 -ASK 自动重试 (Lettuce/Jedis 默认都支持)
```

### 4. 跨集群数据迁移 (Redis Cluster -> Redis Cluster)

场景:从老集群迁移到新集群(不同机房/版本/规模):

```bash
# 工具1:redis-cli --cluster import (Redis 7+ 不直接支持,但可用以下方式)

# 工具2:RedisShake (阿里开源)
wget https://github.com/tair-opensource/RedisShake/releases/latest/download/redis-shake.linux-amd64.tar.gz
tar -xzf redis-shake.linux-amd64.tar.gz

# 配置 shake.toml
[source]
type = "cluster"
cluster = { addresses = [10.0.0.11:6379, 10.0.0.12:6379, 10.0.0.13:6379] }
password = "Redis@123"

[target]
type = "cluster"
cluster = { addresses = [10.1.0.11:6379, 10.1.0.12:6379, 10.1.0.13:6379, 10.1.0.14:6379] }
password = "Redis@456"

# 启动
./redis-shake shake.toml

# 工具3:redis-migrate-tool (唯品会开源,已不维护但仍可用)
# 工具4:自研脚本 + RENAME (适合小数据量)
```

---

## 十四、集群最佳实践

### 1. 避免大 key

**大 key 风险**:
- 单个 key 过大 (例如 > 100 KB) 阻塞 cluster bus,影响 Gossip
- `MIGRATE` 一次只能迁一个 key,大 key 迁移极慢
- 客户端一次读取大 key 阻塞网络

**检测大 key**:

```bash
# redis-cli --cluster bigkeys (扫描所有节点)
redis-cli --cluster bigkeys 10.0.0.11:6379 -i 0.01

# 输出:
# Biggest string found '"user:1000:big-data"' has 5242880 bytes
# Biggest list found '"queue:emails"' has 1000000 items

# rdb-tools 离线分析 RDB
pip install rdbtools
rdb -c memory /var/lib/redis/dump.rdb > memory.csv
```

**解决大 key**:

```bash
# 拆分 (大 Hash → 小 Hash)
# 原:HSET user:1000 profile "..." order "..." cart "..."
# 拆:
HSET user:1000:profile "..." 
HSET user:1000:order "..."
HSET user:1000:cart "..."

# 分桶 (大 List → 多 List)
# 原:LPUSH queue:emails "..."
# 拆:
LPUSH queue:emails:0 "..."
LPUSH queue:emails:1 "..."    # 业务按 hash % N 选桶

# 删除大 key (避免阻塞)
# 错误:DEL user:1000:big-data     (阻塞)
# 正确:UNLINK user:1000:big-data  (异步释放)
```

### 2. 避免热点 key

**热点 key 风险**:所有请求集中到某个 master,即使有副本也都在同一节点,集群资源浪费。

**检测热点 key**:

```bash
# 1. monitor (短暂采样,生产慎用)
redis-cli -p 6379 MONITOR | head -1000

# 2. INFO commandstats (推荐,生产可用)
redis-cli -p 6379 INFO commandstats | grep cmdstat_get
# cmdstat_get:calls=1234567,usec=12345678,usec_per_call=10.0,rejected_calls=0,failed_calls=0

# 3. 客户端埋点 (业务层统计)
# 在 Java 客户端拦截高频 key
```

**解决热点**:

```bash
# 1. 复制多份 (读写分离 + 多副本)
SET hot:key:1 "data"
SET hot:key:2 "data"
SET hot:key:3 "data"
# 客户端随机选一个读

# 2. 用 hashtag 但加随机后缀,把数据分散到多个 slot
# 原:{user:1000}.cart (全部读请求落到一个 master)
# 改:{user:1000}:cart:0, {user:1000}:cart:1, ... (多 slot)

# 3. 业务层本地缓存 (Caffeine/Guava),减轻 Redis 压力
```

### 3. hashtag 合理使用

```text
hashtag 原则:

✅ DO:
  - hashtag 维度选**查询热点**维度
    例:{orderId} → 让"按订单聚合"的数据同 slot
  - hashtag 后面挂业务 id,保证足够分散
    例:{userId}:profile, {userId}:order 而不是 {userId}.profile

❌ DON'T:
  - hashtag 只挂固定字符串(所有人同 slot)
    例:{ALL_USERS}:profile  ← 全集群热点
  - hashtag 维度太细 (1 个 key 1 个 slot,失去聚合)
    例:{userId}:{orderId}:item   ← 退化成无 hashtag
  - hashtag 维度太粗 (把所有数据塞 1 个 slot)
    例:{tenantId}:all            ← 1 个 slot,无扩展
```

### 4. 客户端配置建议

```yaml
spring:
  redis:
    timeout: 2000                       # 命令超时 ≤ 3s
    cluster:
      max-redirects: 3                  # MOVED/ASK 重定向最多 3 次
    lettuce:
      pool:
        max-active: 100                 # 连接池上限
        max-idle: 20
        min-idle: 5
        max-wait: 1000                  # 获取连接超时
      shutdown-timeout: 200
```

**Jedis 客户端建议**:

```java
JedisPoolConfig poolConfig = new JedisPoolConfig();
poolConfig.setMaxTotal(200);            // 总连接数
poolConfig.setMaxIdle(50);              // 最大空闲
poolConfig.setMinIdle(10);              // 最小空闲
poolConfig.setTestOnBorrow(true);       // 借出前 PING,避免拿到死连接
poolConfig.setTestWhileIdle(true);      // 空闲时定期 PING
```

### 5. 运维 SOP

| 操作 | 步骤 |
|------|------|
| **新增 master** | 启动新节点 → `CLUSTER MEET` → `redis-cli --cluster reshard` 搬 slot |
| **新增 replica** | 启动新节点 → `CLUSTER MEET` → `CLUSTER REPLICATE <master-id>` |
| **下线 master** | `reshard` 把 slot 全部迁走 → `CLUSTER FORGET` → `SHUTDOWN` |
| **下线 replica** | 直接 `SHUTDOWN`(主会自动找新 replica 或保持无副本) |
| **手动故障转移** | `CLUSTER FAILOVER` (在 replica 上执行,优雅切换) |
| **强制故障转移** | `CLUSTER FAILOVER FORCE` (master 活着但要切换) |
| **数据修复** | `redis-cli --cluster fix` 自动尝试修复副本关联 |
| **备份** | `BGSAVE` 在每个 master 上分别执行,上传 RDB 到异地 |
| **监控告警** | `cluster_state`、`cluster_slots_ok`、`master_last_io_seconds` |

### 6. 安全建议

```ini
# 1. 开启密码
requirepass YourStrongPass@123

# 2. 开启 ACL (Redis 6+)
# 创建用户,只给必要权限
ACL SETUSER appuser on ">App@123" ~app:* &* +@read +@write -@dangerous

# 3. 加密通信 (Redis 6+ TLS)
tls-port 6380
tls-cert-file /etc/redis/redis.crt
tls-key-file /etc/redis/redis.key
tls-ca-cert-file /etc/redis/ca.crt

# 4. 集群 bus 也启用 TLS
tls-cluster yes
tls-cluster-cert-file /etc/redis/cluster.crt
tls-cluster-key-file /etc/redis/cluster.key

# 5. 防火墙
iptables -A INPUT -p tcp --dport 6379 -s 10.0.0.0/24 -j ACCEPT
iptables -A INPUT -p tcp --dport 6379 -j DROP
iptables -A INPUT -p tcp --dport 16379 -s 10.0.0.0/24 -j ACCEPT
iptables -A INPUT -p tcp --dport 16379 -j DROP
```

---

## 十五、核心要点速记

| 关键词 | 要点 |
|--------|------|
| **Cluster** | Redis 3.0+ 官方分布式方案,数据分片 + 高可用 |
| **16384 slot** | 全部 key 哈希到 16384 个槽位,均匀分摊给 master |
| **CRC16** | `CRC16(key) & 0x3FFF` 计算 slot 号 |
| **hashtag** | `{xxx}` 强制同 slot,解决多 key 操作 |
| **Gossip** | 节点间流言协议,最终一致,带宽小 |
| **MOVED** | 永久重定向,客户端应更新本地 slot 表 |
| **ASK** | 临时重定向,迁移中,客户端不更新 slot 表 |
| **PFAIL** | 主观下线,单节点认为某节点挂了 |
| **FAIL** | 客观下线,大多数 master 认定 |
| **Replica Election** | replica 自增 epoch,广播投票请求,获多数票升主 |
| **cluster-node-timeout** | 默认 15s,失联这么久算 PFAIL |
| **cluster-require-full-coverage** | 默认 yes,部分 slot 不可用时整体拒服务,生产建议 no |
| **CLUSTER MEET** | 加入集群 |
| **CLUSTER REPLICATE** | replica 关联 master |
| **CLUSTER ADDSLOTS** | 给本节点分配 slot |
| **CLUSTER SETSLOT** | 槽迁移命令对 (MIGRATING / IMPORTING) |
| **redis-cli --cluster create** | 一键创建集群,生产推荐 |
| **redis-cli --cluster reshard** | 在线迁移 slot |
| **redis-cli --cluster rebalance** | slot 自动均衡 |
| **redis-cli --cluster check** | 检查集群健康 |
| **redis-cli --cluster info** | 集群汇总信息 |
| **redis-cli --cluster bigkeys** | 扫描大 key |
| **JedisCluster** | Java 客户端,智能路由 + 连接池 |
| **Lettuce** | Netty 异步客户端,线程安全,推荐 |
| **CROSSSLOT** | 多 key 跨 slot 报错,用 hashtag 解决 |
| **大 key** | 阻塞 MIGRATE,拆分或 UNLINK |
| **热点 key** | 多副本或 hashtag 加随机后缀 |
| **脑裂** | Cluster 不会脑裂,选举需多数票 |
| **reshard 流程** | SETSLOT MIGRATING/IMPORTING → MIGRATE key → SETSLOT NODE |
| **客户端重连** | 收到 MOVED 后应刷新 slot 表,连错节点会重定向 |

---

## 十六、面试题速答

### 1. Redis Cluster 如何做数据分片?

> 用 `CRC16(key) & 0x3FFF` (等价于 `CRC16(key) % 16384`) 计算 slot 号,16384 个 slot 摊派给 N 个 master。可用 `{hashtag}` 强制多个 key 落到同一 slot,解决多 key 操作限制。

### 2. 为什么是 16384 个 slot?

> 1) Gossip 消息携带节点 slot 信息,2KB (16384) vs 8KB (65536),带宽友好;2) Redis 集群主节点一般不超过 1000,16384 个 slot 已足够均衡;3) 16384 = 2^14,位运算快。

### 3. Redis Cluster 故障转移过程?

> master 失联 → 其他节点本地标记 PFAIL → 大多数 master 认定 PFAIL → 标记 FAIL 并广播 → 该 master 的 replica 自增 epoch 发起选举 → 获得多数票 → 升主并广播。

### 4. MOVED 和 ASK 的区别?

> MOVED 是**永久**重定向,slot 已稳定在新节点,客户端应更新本地 slot 表;ASK 是**临时**重定向,slot 正在迁移中,客户端先 ASKING 再发命令,但**不更新** slot 表。

### 5. Cluster 模式下事务需要注意什么?

> MULTI/EXEC 不允许跨 slot,要么用 hashtag 强制同 slot,要么改用 Lua 脚本(单线程原子)。

### 6. 为什么不推荐 SELECT?

> Cluster 模式只支持 db 0,跨 db 是单机 Redis 概念。Cluster 通过 key 前缀做"逻辑库",或直接部署多个 Cluster。

### 7. 如何平滑扩缩容?

> 1. 新节点启动并 `CLUSTER MEET` 加入;2. `redis-cli --cluster reshard` 在线迁移 slot;3. 客户端会收到 -ASK 重定向,自动重试;4. 迁移完成后收到 -MOVED,更新本地 slot 表。整个过程不停服。

### 8. 大 key 在 Cluster 下有什么风险?

> 1. slot 迁移时 `MIGRATE` 单 key 原子,大 key 极慢;2. 客户端读取阻塞;3. cluster bus 带宽压力。解决:拆 key (按 hash 分桶) 或 `UNLINK` 替代 `DEL`。

### 9. hashtag 怎么用最合理?

> 选择**业务查询维度**作 hashtag,既保证事务/Lua 能跨 key,又避免单 master 热点。例:`{orderId}:item:1`、`{userId}:cart:0`。

### 10. Redis Cluster vs Codis vs Twemproxy?

> Cluster 是 Redis 官方方案,无中心 Proxy,客户端智能路由;Codis 是国产代理方案,有中心 Proxy;Twemproxy 是 Twitter 开源,只分片无 HA。Cluster 是 Redis 团队长期主推,生态最完善。
