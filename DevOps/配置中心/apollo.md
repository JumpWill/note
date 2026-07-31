# Apollo

携程框架部门研发的分布式配置中心，开源已久，强调「一站式配置管理」，以完善的多环境/集群管理、灰度发布和审计著称，适合中大型企业。

## 一、定位与特性

- **统一配置中心**：配置集中管理，APP/ENV/CLUSTER 四层模型
- **配置变更秒级生效**：客户端长轮询 + 定时兜底拉取
- **完善的可视化**：Portal 自带 Web UI
- **完善的灰度**：按 IP / Label 灰度
- **审计**：所有发布可追溯、配置 diff 对比
- **权限管控**：部门-应用-环境多维度 RBAC
- **多语言**：Java/Go/.Net/Node/Python 均有客户端

## 二、四层模型

### 1. 层级关系

```text
应用 (App)
   │
   ├── 环境 (Env)
   │      │
   │      └── 集群 (Cluster)
   │             │
   │             └── 配置项 (Key) ── 命名空间 (Namespace)
   │                                    │
   │                                    ├── 私有 (private)
   │                                    ├── 公共 (public)
   │                                    └── 关联 (inherit)
   │
   └── 公共命名空间（跨应用共享）
```

| 层级 | 含义 | 示例 |
| ---- | ---- | ---- |
| **App（应用）** | 业务应用/微服务 | `order-service`、`user-service` |
| **Env（环境）** | 部署环境 | `DEV` / `FAT` / `UAT` / `PROD` |
| **Cluster（集群）** | 同环境下的集群划分 | `shanghai`、`beijing`、`default` |
| **Namespace（命名空间）** | 命名空间，私有 vs 公共 | `application`、`middleware.rocketmq` |

### 2. 命名空间类型

| 类型 | 说明 |
| ---- | ---- |
| **private（私有）** | 只有当前应用可访问 |
| **public（公共）** | 任何应用均可关联 |
| **关联继承** | 一个应用可「关联」多个公共命名空间，读但不可写 |

### 3. 配置项查找顺序

```text
1. 应用私有配置（覆盖同名）
2. 当前集群的私有配置
3. 应用的默认集群（default）私有配置
4. 关联的公共命名空间配置（按关联顺序）
```

> 后续覆盖前面，与 Spring `@PropertySource` 顺序相反，要注意。

## 三、架构

### 1. 总体架构

```text
                ┌──────────────────┐
                │   Portal (Web)   │ ← 运营/开发 UI
                │  Spring Boot MVC │
                └────────┬─────────┘
                         │
                         ▼
                ┌──────────────────┐
                │  AdminService    │ ← 配置管理 API
                │  Spring Boot     │
                └───┬──────────┬───┘
                    │          │
        Publish     │          │ Read
                    ▼          ▼
            ┌──────────────┐  ┌──────────────────┐
            │  ConfigDB    │  │  ConfigService    │ ← 配置读取 API
            │  PortalDB    │  │  Spring Boot      │
            └──────────────┘  └──────┬───────────┘
                                     │
                                     ▼
                              Client SDK
```

### 2. 模块职责

| 模块 | 职责 |
| ---- | ---- |
| **Portal** | Web UI、登录、权限、配置编辑、发布、审计 |
| **AdminService** | 配置写（写 PortalDB + 发布消息到 ConfigDB） |
| **ConfigService** | 配置读（meta server + 长轮询通知） |
| **MetaServer** | 部署在 ConfigService 同一进程，Eureka/Nacos 服务发现 |
| **Client SDK** | 长轮询 + 本地缓存 + 拉取 HTTP |
| **ConfigDB** | 客户端拉取、ReleaseMessage |
| **PortalDB** | Portal 元数据、审计、权限 |

### 3. 内部服务发现

| 方案 | 说明 |
| ---- | ---- |
| **Eureka**（默认） | MetaServer 把自己注册到 Eureka，Portal 通过域名 `config-service.xxx` 走 Eureka 解析 |
| **Nacos** | v1.10+ 支持，使用 Nacos 注册中心 |
| **K8s** | v2.x 原生支持 K8s Service |

> 客户端拉取配置不直接连 Eureka/Nacos，而走 MetaServer — 单节点即可提供 SLB，由其代为发现。

### 4. 数据库拆分

| 库 | 用途 |
| ---- | ---- |
| **PortalDB** | App/Env/Cluster/AppNamespace/User/Permission/Release/Audit 等元数据 |
| **ConfigDB** | `ReleaseMessage`（发布通知）、`ServerConfig`（集群自身配置）、`AccessKey` |

> 两库可同实例但分 schema，强烈推荐各自独立 DB 实例。

## 四、配置发布与推送原理

### 1. 发布流程

```text
Portal 点击「发布」
   │
   ▼
AdminService.publish() 接口
   │
   ├─ 1. 校验权限、灰度规则
   │
   ├─ 2. 写 PortalDB.Release（历史版本）
   │
   ├─ 3. 写 ConfigDB.ReleaseMessage（INSERT 一条新消息，message=appId+cluster+namespace）
   │
   ▼
返回成功
```

### 2. 推送流程

```text
ConfigService 节点 ──► 启动扫描线程 (100ms)
                         │
                         ▼
                    SELECT max(id) FROM ReleaseMessage
                    │
                    ▼
                 内存中对比上一次 id
                    │
            ┌───────┴───────┐
            ▼               ▼
        有新消息        无新消息
            │               │
            ▼               │（继续扫描）
    取得所有订阅了该 appId+cluster+namespace 的 DeferredResult
            │
            ▼
    setResult() 触发等待中的 HTTP 请求返回
            │
            ▼
    客户端收到通知 → 用 notificationId 重新 GET /configs/{appId}/{cluster}/{namespace} 拉取
```

### 3. 客户端长轮询

```text
Client → ConfigService
POST /notifications/v2
   { appId, cluster, namespaceName, notificationId }
   │
   ▼
服务端扫表线程检测到新 ReleaseMessage
   │
   ▼
匹配 → DeferredResult<APIVoid> setResult()
   │
   ▼
HTTP 长轮询立即返回 304 / 配置变更通知
   │
   ▼
客户端收到 → 比较 notificationId 不一样 → 触发拉取
   │
   ▼
GET /configs/{appId}/{cluster}/{namespaceName}?releaseKey=xxx
   │ Server 返回最新 key=value
   ▼
更新内存 + 持久化本地文件 + 触发监听器
```

- **长轮询超时**：默认 `longPollingTimeout=60s`（服务端）；`longPollinigTimeout=60s`（客户端）
- **兜底拉取**：客户端无论收到通知与否，每 5 分钟拉一次完整配置，防止漏单

### 4. 灰度与回滚机制

- 发布时可指定「灰度对象」：IP 列表 / Label 列表
- 生成灰度版本 Release，仅命中灰度的客户端拉得到
- 灰度没问题 → 一键「全量发布」
- 全量后任意时刻可「回滚」到历史 Release

## 五、客户端本地缓存

| 文件 | 位置 |
| ---- | ---- |
| `appId+cluster.properties` | `~/opt/data/{appId}/config-cache/`（Linux 默认 `${user.home}/opt/data/...`） |
| 编码 | UTF-8 明文 properties |
| 大小 | 全部 namespace 全量保存 |

```properties
# 示例缓存（合并所有 namespace 后）
order.dubbo.port=20880
order.dubbo.protocol=dubbo
mq.rocket.namesrv=10.0.0.1:9876
```

> 本地缓存是「灾备」+ 「冷启动加速」双角色。Server 不可用时直接读本地。

## 六、Java / Spring 集成

### 1. 引入依赖

```xml
<dependency>
  <groupId>com.ctrip.framework.apollo</groupId>
  <artifactId>apollo-client</artifactId>
  <version>2.2.0</version>
</dependency>
```

### 2. 基础配置（`application.yml` 或 `META-INF/app.properties`）

```properties
# app.properties
app.id=order-service
apollo.meta=http://apollo-config-service:8080
apollo.bootstrap.enabled=true
apollo.bootstrap.namespaces=application,middleware.rocketmq
apollo.cacheDir=/opt/apollo/cache
```

### 3. Spring `@ApolloConfig` / `@ApolloConfigChangeListener`

```java
@Configuration
public class ApolloConfig {

    @Bean
    public Config config() {
        return ConfigService.getAppConfig();
    }
}

@Component
public class FeatureWatcher {

    @ApolloConfig("application")
    private Config application;

    @ApolloConfigChangeListener(interestedKeyPrefixes = "order.")
    public void onChange(ConfigChangeEvent event) {
        for (String key : event.changedKeys()) {
            ConfigChange change = event.getChange(key);
            System.out.println("change: " + key + " " + change.getOldValue()
                + " → " + change.getNewValue());
        }
    }
}
```

### 4. `@Value` 自动更新原理

Apollo 通过自定义 `PropertySource`（`SpringValueProcessor`）注入到 Spring Environment，`@Value` 被替换成特殊 SPI 包装的字段，配置变更时调用 `update()`。

```text
@Value("${order.timeout:3000}")
   │
   ▼
扫描 SpringValueProcessor
   │
   ▼
替换为 SpringValue(field, bean, key)
   │
   ▼
配置变更 → ConfigChangeEvent → 扫描所有 SpringValue 匹配 key → 调用 set/new
```

> Apollo 客户端 **不需要** `@RefreshScope` 即让 `@Value` 生效（这是与 Spring Cloud Config / Nacos 重要差异）。

### 5. Spring Boot 集成

```xml
<dependency>
  <groupId>com.ctrip.framework.apollo</groupId>
  <artifactId>apollo-client</artifactId>
</dependency>
<dependency>
  <groupId>com.ctrip.framework.apollo</groupId>
  <artifactId>apollo-spring-boot-starter</artifactId>
</dependency>
```

```yaml
apollo:
  meta: http://apollo-config-service:8080
  bootstrap:
    enabled: true
    namespaces: application
```

## 七、灰度发布规则

| 维度 | 实现 |
| ---- | ---- |
| **IP 列表** | 客户端 SDK 上报 IP（`apollo.client.ip`），Portal 中勾选 |
| **Label** | 客户端通过 JVM 参数 `-Dapollo.labels=group=canary,region=shanghai` |

- 灰度规则落到 `Release` 表（`isGray=1` + `grayRules`）
- 客户端请求 `/notifications` 时按规则过滤
- 灰度全量：服务端切换 `isGray=0` 即可，无需二次发布

## 八、权限与审计

### 1. 内置角色

| 角色 | 权限 |
| ---- | ---- |
| `superAdmin` | 全量 |
| `appAdmin` | 单应用管理员 |
| `appUser` | 单应用普通用户（可读、可写已授权环境） |

### 2. 维度

- **部门（Org）** → **应用（App）** → **环境（Env）** 多维度
- 普通用户需被关联到部门并赋予角色

### 3. 审计

- PortalDB 记录所有：`Release` / `Publish` / `Rollback` / `ItemUpdate` / `ItemDelete`
- 「发布历史」可查询任一配置项的全部变更轨迹
- 支持按 user/app/时间检索

### 4. SSO / OIDC 接入

- v2 起 Portal 支持 LDAP / OIDC / SAML 认证
- 默认账号体系内置，可关闭

## 九、多环境多集群实践

### 1. 环境划分

| Env | 用途 |
| ---- | ---- |
| `DEV` | 本地开发 |
| `FAT` | Feature Acceptance Test，功能环境 |
| `UAT` | 用户验收 |
| `PRO` | 生产 |

> 每个环境一份独立 Portal + AdminService + ConfigService 集群，或统一一套（用 Env 隔离）。

### 2. 集群维度

- `shanghai` / `beijing` 同 PRO 下不同机房
- 不同 Cluster 可配置不同参数（如注册中心地址）
- Cluster 在「应用设置」中开启，配置项同 namespace 下按 cluster 分别存在

### 3. 配置共享

- 中间件配置（Redis、Kafka 连接）放 `public` namespace
- 业务独有配置放 `application` private

### 4. 客户端按需加载

```properties
# 同时加载多个 namespace
apollo.bootstrap.namespaces=application,middleware.rocketmq,middleware.mysql
```

## 十、优缺点

### 优点

- 四层模型 + 命名空间粒度细
- 灰度粒度（IP + Label），最贴近 CMDB
- 审计 + 权限强，企业级合规友好
- `@Value` 自动刷新（不需要 `@RefreshScope`）
- 多语言客户端齐备
- 配置格式统一 properties（YAML/JSON 通过 value 内容）

### 缺点

- 部署组件多（Portal / AdminService / ConfigService / MetaServer / DB），运维成本高
- 默认 properties，复杂配置不如 YAML 友好（YAML 需用 `@ApolloJsonValue` 等）
- 启动期有元数据拉取，启动略慢
- 单点 Portal（生产要 HA 集群）
- 客户端 jar 包依赖较多（9+ MB）

## 十一、与 Nacos 对比要点

| 维度 | Apollo | Nacos |
| ---- | ---- | ---- |
| **模型** | App/Env/Cluster/Namespace 四层 | Namespace/Group/DataId 三段 |
| **灰度** | IP + Label | 仅 IP (Beta) |
| **推送** | 长轮询 60s + 5min 兜底 | 长轮询 29.5s / v2 gRPC |
| **@Value 自动刷新** | 是 | 否（需 `@RefreshScope`） |
| **权限/审计** | 完善 | 基础 |
| **运维** | 组件多 | 组件少，可一站式 |
| **多语言** | Java/Go/.Net | Java/Go/Node/Py/CPP |
| **格式** | 主 properties | properties/YAML/JSON/XML |
| **与注册中心** | 二选一 | 一体 |

选型：

- **超大规模、强合规、多团队** → Apollo
- **小中型、追求一套搞定、Spring 体系** → Nacos
- **已用 Eureka/Nacos 作为服务发现，且要求统一** → Nacos 更省心

## 十二、最佳实践

- **环境分层**：DEV/FAT/UAT/PRO 严格隔离，禁止跨环境拷贝（用「灰度迁移」代替）
- **配置拆分**：基础（中间件）入 `public`，业务入 `private`
- **灰度规则统一**：所有发布先灰度，灰度规则落到 CMDB（IP 自动同步）
- **本地缓存清理**：`/opt/data/{appId}/config-cache` 不要跨实例互相拷贝（依赖 host 唯一）
- **监控**：长轮询超时、扫表线程延迟、ReleaseMessage backlog
- **审计合规**：所有发布必须带变更说明（Portal 强制）
- **多集群**：用 Cluster 隔离机房，避免统一修改跨集群污染
- **灾备**：Plan B — Portal 不可用时 client 用本地缓存；Portal 恢复后一致化靠下次扫描
- **结合 gitops**：通过 `apollo-portal-bridge` 等工具让 Git PR = 发布请求
