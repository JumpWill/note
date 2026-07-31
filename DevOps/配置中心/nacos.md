# Nacos Config

阿里开源的动态服务发现、配置管理和服务管理平台，配置中心领域的事实标准之一，社区活跃、Java/Spring 体系最丝滑。

## 一、定位与特性

- **一站式**：注册中心 + 配置中心 + DNS，合三为一
- **AP/CP 切换**：注册中心默认 AP（Distro 协议）、配置默认走 AP 模式但持久化到 MySQL
- **推送模型**：长轮询（v1）/ gRPC 长连接（v2），秒级生效
- **可视化**：自带控制台，开箱即用
- **多语言**：Java/Go/Node/Python/CPP/Sharp 官方客户端
- **生态完善**：Spring Cloud Alibaba、Dubbo、Cloud Native 友好
- **版本线**：1.x 稳定（推荐生产），2.x 重写通信层（gRPC + Protobuf）

## 二、架构

### 1. 总体架构

```text
┌──────────────────────────────────────────────────────┐
│                   Nacos Server 集群                   │
│  ┌────────┐  ┌────────┐  ┌────────┐                 │
│  │ Node 1 │  │ Node 2 │  │ Node 3 │                 │
│  │Consensus│ │Consensus│ │Consensus│  ← Raft/Distro │
│  └───┬────┘  └───┬────┘  └───┬────┘                 │
│      └───────────┼───────────┘                       │
│                  ▼                                    │
│       ┌─────────────────────┐                       │
│       │  Config Service      │ ← 配置读写            │
│       │  Naming Service      │ ← 服务发现            │
│       └─────────┬───────────┘                       │
│                 ▼                                    │
│        ┌────────────────────┐                        │
│        │ Derby (嵌入式) /    │ ← 配置持久化          │
│        │ MySQL (生产推荐)    │                        │
│        └────────────────────┘                        │
└──────────────────────────────────────────────────────┘
        ▲ HTTP（v1）/ gRPC（v2） ▲
        │                       │
┌───────┴──────┐         ┌──────┴────────┐
│  Client SDK  │  ……  ……  │  Admin Portal │
│  (Java/Go/…) │         │  (Web 控制台) │
└──────────────┘         └───────────────┘
```

- **Server 节点**：无状态（运维层面），有状态（数据层面）
- **Admin Portal**：内置 Web 控制台，也可独立部署

### 2. 一致性协议

| 协议 | 适用 | 说明 |
| ---- | ---- | ---- |
| **Distro**（自研 AP） | 注册中心、配置中心默认 | 最终一致性，简单快速，去中心化 |
| **Raft**（CP 模式） | 命名空间需强一致时启用 | 选举 Leader，过半写入，v2 起逐步引入 |

- 默认写入：先写本机内存，异步广播给其他节点（Distro）
- 配置数据最终落盘到 Derby/MySQL，提供宕机恢复能力
- 集群内 `ConfigChangeNotify` 事件总线广播变更，避免单机热点

### 3. 存储后端选型

| 后端 | 适用 | 优缺 |
| ---- | ---- | ---- |
| **Embedded Derby** | 单机测试 | 零依赖，**生产禁用**：无法横向扩展 |
| **MySQL 5.7+/8.0** | 生产集群 | 高可用、与原有 DBA 体系打通；需做主备 |
| **集群模式 + 外置 DB** | 生产 | 3 节点起步，单点 DB 不再是瓶颈 |

### 4. 集群部署示意

```text
Nacos 节点1（:8848） ──┐
Nacos 节点2（:8848） ──┼──► MySQL 主库（VIP/RDS）
Nacos 节点3（:8848） ──┘            │
                                    └► MySQL 从库（只读报表）
```

使用 Nginx/HAProxy 在前面做 SLB，节点 IP 列表通过 `cluster.conf` 互相告知：

```properties
# conf/cluster.conf（每行一个节点）
192.168.1.10:8848
192.168.1.11:8848
192.168.1.12:8848
```

## 三、数据模型

### 1. 三元组 + Group 维度

| 维度 | 说明 | 示例 |
| ---- | ---- | ---- |
| **Namespace** | 命名空间，隔离环境/租户 | `dev`、`prod`、`tenant-a` |
| **Group** | 分组，按业务/中间件类型分 | `DEFAULT_GROUP`、`ORDER_GROUP`、`MQ_GROUP` |
| **DataId** | 配置集 ID，按应用+用途拆分 | `order-service.yaml`、`db.properties` |

> 配置唯一键 = `Namespace + Group + DataId`。

### 2. 支持的配置格式

| 扩展名 | 解析 |
| ---- | ---- |
| `.properties` | `key=value` |
| `.yaml` / `.yml` | YAML |
| `.json` | JSON |
| `.xml` | XML |
| `.txt` | 纯文本（自定义解析） |
| 无扩展名或自定义 | 通过 SDK `ConfigType` 指定 |

## 四、配置推送原理

### 1. v1 默认：长轮询 + MD5 比对（29.5s）

```text
Client                                 Server
  │                                       │
  │─── LongPolling 请求 (timeout=30s) ────►│
  │    ┌── 29.5s 后挂起线程 ──────────────┐│
  │    │   Server 端:                      ││
  │    │   - 注册 ClientLongPullingWatch  ││
  │    │   - 同时启动定时器 29.5s 强制返回  ││
  │    │   - 配置变更发布 ConfigChangeEvent││
  │    │     → 命中 watch 立即返回         ││
  │    └─────────────────────────────────┘│
  │◄──── 变更的 DataId 列表 + 新 md5 ─────│
  │                                       │
  │─── 比较本地 md5，有变化则 GET 详情 ────►│
  │◄──── 推送最新配置内容 ────────────────┤│
```

- 客户端请求 `LongPolling 29.5s`：避免极端长连接无响应
- 触发条件：
  - 客户端订阅的 `DataId` 在挂起期间变更
  - 挂起满 29.5s（兜底轮询）
- 服务端通过本地缓存的 `ClientLongPullingWatch` 注册表，按 DataId 查找等待线程
- 多节点：服务 A 发布配置 → 写入 MySQL → 集群内 `ConfigChangeNotify` UDP/HTTP 广播 → 各节点收到后查本地缓存与 subscriber 列表，匹配则唤醒长轮询

### 2. v2 增量：gRPC 长连接推送

- v2.x 默认走 gRPC（端口 9848/9849）
- 长连接 + Stream，Server 主动 push，秒级更快（实测 50~200ms）
- 兼容长轮询：客户端按服务端版本自动降级
- 需要客户端引入 `nacos-client` 2.x（Spring Cloud Alibaba 2021+ 默认）

### 3. 节点间广播机制

```text
Publish (Admin 或 API)
      │
      ▼
持久化到 MySQL + 写本机 Cache
      │
      ▼
ConfigChangeNotify 事件（异步广播给其他 Nacos 节点）
      │
      ▼
各节点收到变更 → 检查本地 Subscriber → 命中触发 LongPolling 返回
```

> 节点间广播是 Nacos 配置「秒级推送」的关键，否则只会在故障节点切换后才能感知。

## 五、客户端 SDK

### 1. Java 原生 API

```java
// 1. 读取配置
String dataId = "order-service.yaml";
String group = "DEFAULT_GROUP";
String content = configService.getConfig(dataId, group, 5000);

// 2. 监听配置
configService.addListener(dataId, group, new Listener() {
    @Override
    public void receiveConfigInfo(String configInfo) {
        System.out.println("config changed: " + configInfo);
        // 重新初始化业务对象
    }
    @Override
    public Executor getExecutor() {
        return null; // null=默认单线程
    }
});

// 3. 发布配置（不推荐客户端发布，建议走 Portal/Admin API）
boolean ok = configService.publishConfig(dataId, group, "k=v\nk2=v2");
```

### 2. Spring Cloud Alibaba 集成

#### 依赖

```xml
<dependency>
  <groupId>com.alibaba.cloud</groupId>
  <artifactId>spring-cloud-starter-alibaba-nacos-config</artifactId>
</dependency>
<dependency>
  <groupId>org.springframework.boot</groupId>
  <artifactId>spring-boot-starter-actuator</artifactId>
</dependency>
```

#### `bootstrap.yml`（优先级高于 application.yml）

```yaml
spring:
  application:
    name: order-service
  profiles:
    active: prod
  cloud:
    nacos:
      server-addr: 127.0.0.1:8848
      username: nacos
      password: nacos
      namespace: dev-uuid-here          # 通过 Portal 复制 NS ID
      group: DEFAULT_GROUP
      file-extension: yaml
      refresh-enabled: true
      # 共享配置（优先级低 → 高）
      extension-configs:                # 业务扩展配置
        - dataId: common-db.yaml
          group: COMMON_GROUP
          refresh: true
        - dataId: redis.yaml
          group: COMMON_GROUP
          refresh: false
      shared-configs:                   # 基础设施共享配置
        - dataId: common.yaml
          group: COMMON_GROUP
```

> Spring Cloud 2020+ 用 `spring.config.import=nacos:order-service.yaml` 替代（详见第十节）。

### 3. 共享配置优先级

| 优先级（高 → 低） | 来源 |
| ---- | ---- |
| **1** | `${spring.application.name}-${profile}.${file-extension}`（应用专属配置） |
| **2** | `extension-configs`（业务扩展）— 按数组顺序后写的覆盖前写的 |
| **3** | `shared-configs`（基础共享）— 同上 |

> 多个 `extension-configs`/`shared-configs` 同名 key：按代码遍历顺序后者覆盖前者。

### 4. 配置刷新

#### `@RefreshScope`（最常见）

```java
@RestController
@RefreshScope
public class ConfigController {
    @Value("${order.timeout:3000}")
    private int timeout;

    @GetMapping("/timeout")
    public int timeout() { return timeout; }
}
```

> 不加 `@RefreshScope`：`@Value` 注入的字段在容器启动时被锁定，配置变更不会推送到该 Bean。

#### 主动触发刷新（HTTP 端点）

```bash
# 暴露 endpoint
management.endpoints.web.exposure.include=refresh

curl -X POST http://app:8080/actuator/refresh
```

或者在配置变更事件上自动刷新（推荐）：`spring.cloud.nacos.config.refresh-enabled=true` 时由 SDK 投递 `RefreshEvent`。

## 六、配置监听与回调

### 1. Java SDK 方式

```java
configService.addListener(dataId, group, new AbstractListener() {
    @Override
    public void receiveConfigInfo(String configInfo) {
        // 异步执行推荐使用自定义线程池
        reload(configInfo);
    }
});
```

### 2. Spring 事件方式

Nacos 自动发布 `RefreshEvent`，配合 `@RefreshScope` 或自定义监听器：

```java
@Component
public class FeatureFlagWatcher {
    @NacosConfigListener(dataId = "feature-flags.yaml")
    public void onChange(String newCfg) {
        // 重新解析，处理灰度 / 开关
    }
}
```

## 七、灰度 / Beta 发布

| 维度 | 实现 | 适用 |
| ---- | ---- | ---- |
| **灰度（Beta）** | 配置编辑页勾选「Beta 发布」，填目标 IP 列表 | 让指定机器先拉新配置 |
| **标签 + Namespace** | 通过不同 Namespace 隔离 | 多租户/多环境 |
| **Group** | 同一 DataId 不同 Group，客户端选择 | 多版本并行 |

- Beta 的配置仅勾选目标 IP 客户端可拉取（SDK 会检测自身 IP）
- 点击「发布」后 Beta → 正式灰度 → 全量
- 回滚直接选历史版本「回滚」

## 八、历史版本与回滚

- 每次发布生成一条历史版本（保留 30 天默认，可在服务端配置调整）
- 历史对比：Portal 支持两个版本 diff
- 一键回滚：选某条历史 → 「回滚此版本」→ 走全量广播
- 客户端拉取时可指定 `tag`/`version`（高级）

## 九、鉴权与命名空间隔离

### 1. 鉴权

```properties
# conf/application.properties 开启鉴权
nacos.core.auth.enabled=true
nacos.core.auth.server.identity.key=nacos
nacos.core.auth.server.identity.value=nacos
nacos.core.auth.plugin.nacos.token.secret.key=SecretKey012345678901234567890123456789012345678901234567890123456789
nacos.core.auth.enable.userAgentAuthWhite=true
```

| 角色 | 来源 |
| ---- | ---- |
| `ROLE_ADMIN` | 用户管理/命名空间/权限配置 |
| `ROLE_USER` | 配置读写（被授权的 NS） |
| 自定义角色 | 通过 `Permission` API |

### 2. 命名空间隔离

- 不同环境使用不同 Namespace UUID（dev/test/prod 完全隔离）
- 租户场景每个租户一个 Namespace，互不可见
- 客户端通过 `namespace` 字段指定，无值时落到默认 public

### 3. 密钥管理

- 推荐把 `nacos.core.auth.plugin.nacos.token.secret.key` 放到外部 secrets（K8s Secret/Vault）
- JWT 签名密钥变更需所有客户端重新登录，会引发 401 风暴

## 十、配置加密

### 1. jasypt 加密（应用侧）

```xml
<dependency>
  <groupId>com.github.ulisesbocchio</groupId>
  <artifactId>jasypt-spring-boot-starter</artifactId>
  <version>3.0.5</version>
</dependency>
```

```yaml
jasypt:
  encryptor:
    password: ${JASYPT_KEY}
spring:
  datasource:
    password: ENC(密文)
```

> 启动参数 `-Djasypt.encryptor.password=xxx` 或通过环境变量注入。

### 2. Nacos 自带「配置加密插件」（v2.1+）

- 内置 AES 自定义插件
- KMS 插件对接阿里云 KMS：服务端解密客户端拿明文，明文不出 KMS
- 通过 Server 间 filter 生效，对客户端透明

### 3. 客户端加解密（AES 自行实现）

- 启动时从配置获取 AES key，启动 CustomDataIdSourceFilter 拦截

## 十一、与注册中心一体的取舍

| 维度 | 一体化 | 拆开 |
| ---- | ---- | ---- |
| **运维成本** | 一套集群搞定 | 多套系统、多份运维脚本 |
| **功能弱耦合** | 配置和注册共享元数据 | 注册不关心配置 |
| **耦合风险** | 集群抖动影响两边 | 故障隔离 |
| **压测** | 命名/配置流量未隔离 | 分开压测 |
| **生态** | Spring Cloud Alibaba 默认 | Apollo/Consul 可替代 |

> 推荐**生产保持一体化**：简化运维、统一权限，同时按业务规模做集群隔离（命名集群独立部署）。

## 十二、常见坑

### 1. 本地快照缓存

- 默认路径：`${user.home}/nacos/config/{namespace}/{group}/{dataId}` 的加密文件
- Server 不可达时自动从本地加载（**灾备但易过期**）
- 坑：本地有旧配置，Server 恢复后未触发刷新 → 业务读到旧值
- 解：`spring.cloud.nacos.config.server-addr` 加健康检查 + 监控

### 2. 超时与失败

- 网络抖动时 `getConfig(timeout=5000)` 抛异常
- 默认重试：Java SDK 1 次；Spring 集成可配 `retry-count`
- 启动慢：`ConfigService` 初始化阻塞 bean 生命周期，启动时长 +0.5~3s

### 3. Group 混用

- 一个应用多环境的不同 group 切换没做好，CI 推错配置
- 解：统一约定 Group 命名 `APP_GROUP_{env}`，CI 强校验

### 4. `@Value` 不刷新

- 未加 `@RefreshScope`，值永远取启动期注入值
- 解：所有运行时变更的 `@Value` 都应放在 `@RefreshScope` 类中，或改用 `@ConfigurationProperties` + `@RefreshScope`+ `@ConfigurationPropertiesBindingPostProcessor`

### 5. 客户端 group 配置优先级

- `DEFAULT_GROUP` 与自定 group 混用时，订阅和发布 group 不一致静默失败

### 6. 集群脑裂

- 错误的 CLUSTER.conf 节点列表 + 网络分区，两组节点分别写入 → 配置漂移
- 解：时钟同步 + Raft CP 模式 + 健康探针

## 十三、优缺点

### 优点

- 一站式，配置 + 注册 + DNS，开箱即用
- 多语言 SDK 全
- 推送时效 v2 达 100ms 级
- 控制台友好，配置审计/权限/版本齐全
- 与 Spring Cloud Alibaba 深度集成

### 缺点

- 默认 Distro 是 AP，最终一致性极端场景短暂不一致
- Derby 内置存储生产不可用，需切换 MySQL 是隐藏步骤
- 客户端缓存目录散落（`~/nacos/config`），故障排查需要回收清理
- v1 长轮询 29.5s 偶尔被业务感知

适用：Java/Spring 体系、需同时解决服务发现 + 配置管理、中大规模（千级应用）、多语言接入。

## 十四、最佳实践

- **生产环境必须外置 MySQL**，禁用 Derby
- **集群至少 3 节点**，跨机房至少 2 节点 +1 节点本机房
- **客户端长轮询服务端版本固定**，避免滚动升级短暂不一致
- **配置变更必须走 Portal**，避免程序化发布带来的审计失控
- **敏感配置通过 KMS 插件或 jasypt 加密**，禁止明文
- **统一命名空间约定**：`prod-${tenant}`、`dev-${user}`
- **配置 Key 命名规范**：`模块.配置项`，例 `order.retry.max-attempts`
- **本地快照监控**：长周期不变的快照说明服务一直在用本地缓存，Server 状态需探活
- **灰度全流程**：Beta → 灰度 → 全量，每一步保留回滚点
- **CI 集成**：配置变更走 GitOps（`nacos-sync` / 配置导入导出脚本）
