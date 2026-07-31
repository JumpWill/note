# Spring Cloud Config

Spring 官方推出的分布式配置中心，基于 Spring Boot，天然与 Spring 体系深度集成，以「Git 为后端的版本化配置」闻名。

## 一、定位与特性

- **Spring 生态原生**：与 Spring Boot 无缝拼接
- **后端统一**：Git / SVN / JDBC / Vault / native
- **版本化**：直接复用 Git 的 commit/tag/branch
- **轻量**：核心 server 是 Spring Boot Web 应用
- **加解密**：对称 / 非对称加密原生支持
- **配合 Spring Cloud Bus**：一次刷新广播所有实例
- **弱点**：无 UI、需要自建 / 引入 admin 后台、刷新机制需额外组件

## 二、架构

### 1. 总体架构

```text
┌──────────────────────┐         ┌─────────────────────┐
│   Git Repository     │◄────────│   Config Server     │
│  (config-repo)       │ pull    │  (Spring Boot)      │
└──────────────────────┘         └──────────┬──────────┘
                                            │
                                  /encrypt  /decrypt
                                  /{app}-{profile}
                                  /labelfeature
                                            │
                                  HTTP 拉取 + 主动推送
                                            │
┌──────────────────────────────────────────┐ │
│  Config Client (应用 A)                    │
│   /actuator/refresh（手动）                 │ │
│   ─► Spring Cloud Bus                    │◄┘
└────────┬─────────────────────────────────┘
         │ 监听 /bus-refresh 事件
         ▼
┌──────────────────────┐
│  RabbitMQ / Kafka    │ ← 事件总线
└──────────┬───────────┘
           │ 广播所有节点
┌──────────▼─────┐  ┌────────────┐  ┌────────────┐
│ Config Client 1│  │ Client 2   │  │ Client 3   │
│ (多实例)        │  │            │  │            │
└────────────────┘  └────────────┘  └────────────┘
```

### 2. 核心组件

| 组件 | 职责 |
| ---- | ---- |
| **Config Server** | 拉取 Git、解析配置文件、提供 HTTP 接口返回配置 |
| **Config Client** | 启动时拉取配置、`@RefreshScope` 接收刷新事件 |
| **Git / SVN** | 配置仓库、版本化 |
| **Spring Cloud Bus** | 广播刷新事件的中间件（RabbitMQ / Kafka） |

### 3. 部署示意

```text
GitLab / GitHub (config 仓库)
   │
   ▼ webhook（仓库 push 触发）
Config Server
   │
   ▼ 推送
RabbitMQ / Kafka
   │
   ▼ 每个客户端实例
Config Client（应用 N 节点）
```

## 三、后端存储

### 1. Git（推荐）

```yaml
spring:
  cloud:
    config:
      server:
        git:
          uri: https://github.com/myorg/config-repo
          default-label: main         # 对应 master/main/trunk
          search-paths: '{application}/*'
          username: deploy-bot
          password: ${GIT_TOKEN}
          clone-on-start: true        # 启动时浅克隆避免延迟
          # 不写则为 default profile: {application}.yml
```

仓库文件结构：

```text
config-repo/
├── order-service.yml              # 默认
├── order-service-prod.yml        # PRO 文件
├── user-service.yml
└── user-service-prod.yml
```

### 2. SVN

```yaml
spring:
  cloud:
    config:
      server:
        svn:
          uri: https://svn.example.com/svn/config
          default-label: trunk
          username: deploy
          password: ${SVN_PWD}
```

### 3. JDBC

```yaml
spring:
  cloud:
    config:
      server:
        jdbc:
          sql-queries:
            select: "SELECT KEY, VALUE FROM PROPERTIES WHERE APPLICATION=? AND PROFILE=? AND LABEL=?"
  datasource:
    url: jdbc:mysql://db:3306/config
```

> JDBC 需手动建表（`PROPERTIES` 表，列：`APPLICATION/PROFILE/LABEL/KEY/VALUE`）。

### 4. Vault

```yaml
spring:
  cloud:
    config:
      server:
        vault:
          host: vault.example.com
          port: 8200
          scheme: https
          token: ${VAULT_TOKEN}
          backend: secret
          default-context: application
          profiles:
            active: default
```

### 5. Native（本地文件系统）

```yaml
spring:
  cloud:
    config:
      server:
        native:
          search-locations: file:/opt/config/{application}/
```

> Native 适合单机开发，集群下不便共享。

## 四、配置文件解析规则

### 1. 文件命名

```text
{application}-{profile}.yml
{application}-{profile}.properties
{application}.yml   （无 profile）
{application}-{label}.yml   （指定 label，如 git 分支）
```

| 客户端请求 | 解析 |
| ---- | ---- |
| `GET /order-service/default/main` | `order-service.yml` + `order-service-default.yml` |
| `GET /order-service/prod/main` | 同上 + `order-service-prod.yml` |

### 2. `label` 参数

- 默认值：master（2.x 改默认 main）
- 实际代表 Git **分支 / Tag / commit**
- 通过 `spring.cloud.config.label=feature-x` 指定

```bash
curl http://config-server:8888/order-service/prod/feature-x
```

### 3. 占位符

```yaml
spring:
  cloud:
    config:
      server:
        git:
          uri: https://github.com/{org}/config-repo
          default-label: main
```

> `{application}` 可用作 search-paths 占位。

### 4. 拉取优先级（服务端合并）

```text
1. {application}.yml    （默认 label 默认 profile）
2. {application}-{profile}.yml
3. {application}-{label}.yml    （label 指定）
4. {application}-{profile}-{label}.yml
5. application.yml    （兜底，所有应用共用）
```

服务端按顺序合并，后续覆盖前。

## 五、客户端拉取时机

### 1. 启动阶段

- Spring Boot 启动时加载 `bootstrap.yml`（早于 `application.yml`）
- `spring-cloud-config-client` 在 `bootstrap` 阶段向 Server 拉取配置
- 拉到的配置合并到 `Environment`

```yaml
# bootstrap.yml
spring:
  application:
    name: order-service
  profiles:
    active: prod
  cloud:
    config:
      uri: http://config-server:8888
      label: main
      profile: prod
      fail-fast: true
      retry:
        initial-interval: 1000
        max-attempts: 6
        multiplier: 1.5
```

### 2. Spring Cloud 2020+ 风格：`spring.config.import`

```yaml
spring:
  config:
    import: configserver:http://config-server:8888
```

> 不再强制 bootstrap.yml（结合 Spring Boot 2.4+ 的 `ConfigDataEnvironmentPostProcessor`）。

### 3. `@RefreshScope` 之外的运行时变更

- 启动后拉取的配置默认缓存到 `Environment`
- 无 Bus 时配置变更不会推到正在运行的应用

## 六、刷新机制

### 1. `actuator/refresh`（手动）

```yaml
management:
  endpoints:
    web:
      exposure:
        include: refresh,health,info
```

调用端点后，仅触发当前实例 `RefreshEvent`：

```bash
curl -X POST http://app:8080/actuator/refresh
```

### 2. `@RefreshScope` 原理

```text
@RefreshScope 修饰的 Bean 由 CGLIB 代理
   │
   ▼
ContextRefreshedEvent 时不立即创建 Bean
   │
   ▼
首次访问时 BeanFactory 真正创建
   │
   ▼
RefreshEvent 触发 → scope 缓存清空
   │
   ▼
下次访问 → 重建 Bean（@Value 字段重新注入）
```

```java
@RestController
@RefreshScope
public class OrderController {
    @Value("${order.timeout:3000}")
    private int timeout;  // 重新创建实例时再次读取
}
```

### 3. Spring Cloud Bus + `/bus-refresh` 广播

#### 客户端依赖

```xml
<dependency>
  <groupId>org.springframework.cloud</groupId>
  <artifactId>spring-cloud-starter-bus-amqp</artifactId>
</dependency>
```

#### 配置（Config Server + 所有 Client）

```yaml
spring:
  rabbitmq:
    host: rabbitmq
    port: 5672
    username: guest
    password: guest

management:
  endpoints:
    web:
      exposure:
        include: busrefresh,refresh

spring:
  cloud:
    bus:
      refresh:
        enabled: true
      destination: config-bus
```

#### 触发（任一节点）

```bash
# 全部实例都刷新
curl -X POST http://config-server:8888/actuator/busrefresh

# 只刷指定服务
curl -X POST 'http://config-server:8888/actuator/busrefresh/order-service:8080'
```

#### 完整流程

```text
1. Git push 触发 webhook
2. Config Server 端 /monitor 接收 webhook（Git 用 GitHubPlugin/GitLabPlugin）
3. 触发自身 RefreshEvent
4. 通过 Bus 广播到所有节点
5. 各节点 Client 重新拉取配置
6. 销毁 @RefreshScope Bean
7. 下次访问 Bean 重建 + 注入新值
```

### 4. Git Webhook（自动刷新）

Config Server 启用 `/monitor` 端点：

```xml
<dependency>
  <groupId>org.springframework.cloud</groupId>
  <artifactId>spring-cloud-config-monitor</artifactId>
</dependency>
```

GitHub 设置 Webhook URL：

```text
Payload URL: http://config-server:8888/monitor?path=*
Content type: application/json
Events: push
```

> 必须配合 Bus，否则只刷 Server 自己。

### 5. 关闭自动刷新

```yaml
spring:
  cloud:
    bus:
      refresh:
        enabled: false
```

> 关闭后只能通过 `actuator/refresh` 手动刷新，**不推荐**用于多实例生产。

## 七、加解密

### 1. 对称加密（Config Server 端）

#### 配置密钥

```yaml
# application.yml（Config Server）
encrypt:
  key: abcdef1234567890     # 16/24/32 字节 AES 密钥
```

#### API 加密

```bash
curl http://config-server:8888/encrypt -d 'mypassword123'
# 返回 5c4b... 密文
```

#### 使用密文

```yaml
# config-repo/order-service.yml
spring:
  datasource:
    password: '{cipher}5c4b...'
```

客户端拉取时 Server 自动解密。

### 2. 非对称加密（RSA）

```yaml
encrypt:
  key-store:
    location: classpath:server.jks
    password: keystorepass
    alias: mykey
    secret: keypass
```

```bash
# 生成 keystore
keytool -genkeypair -alias mykey -keyalg RSA -dname "CN=Spring" \
  -keypass keypass -keystore server.jks -storepass keystorepass
```

### 3. JCE 限制

- Java 默认 JCE policy 限制 AES 加密 key 长度（≤128bit）
- 突破限制：替换 `${JAVA_HOME}/jre/lib/security/US_export_policy.jar` → 安装 `Java Cryptography Extension (JCE) Unlimited Strength` 包
- JDK 8u161+、JDK 9+ 默认 unlimited，无需替换

### 4. 客户端加密内容

```yaml
spring:
  cloud:
    config:
      override-system-properties: false
```

> 默认开启覆盖，客户端会被服务端推送的明文覆盖。

## 八、高可用与本地 Clone

### 1. Git Clone 缓存

```yaml
spring:
  cloud:
    config:
      server:
        git:
          uri: https://github.com/myorg/config-repo
          basedir: /var/cache/config-repo
          force-pull: true    # 强制每轮同步
```

- 首次 deep clone，后续 `git fetch`
- 节点间基于 `basedir` 共享（EBS/NFS）或各自本地

### 2. 多实例负载均衡

```text
                      ┌─ Config Server Node 1 ─┐
config-client ───────►├─ Config Server Node 2 ─┤
                      └─ Config Server Node 3 ─┘
                                 ▲
                                 │
                              Git 仓库
```

- Node 间不共享状态，纯无状态；实例可任意扩缩
- 配合 Nginx/HAProxy SLB

### 3. Git 仓库故障兜底

- 节点本地 `basedir` 缓存可兜底（最后一次成功拉取的快照）
- 建议仓库主备（S3 + 自有 Gitlab）

## 九、失败快速

```yaml
spring:
  cloud:
    config:
      fail-fast: true
      retry:
        initial-interval: 1000
        max-attempts: 6
        multiplier: 1.5
        max-interval: 2000
```

- `fail-fast: true` + 服务端不可达 → 应用启动失败（避免「启动 OK 但后续找不到配置」）
- 与 `spring.cloud.bus.enabled=true` 联动刷新

## 十、客户端使用注意点

### 1. `@Value` 必须 `@RefreshScope`

```java
@RefreshScope
@Component
public class OrderCfg {
    @Value("${order.timeout}")
    private int timeout;
}
```

### 2. `Environment` 方式（适合动态 key）

```java
@Component
public class EnvWatcher implements EnvironmentChangeListener {
    @Autowired private Environment env;

    // 配合监听 RefreshEvent
}
```

### 3. 注册到 Spring Cloud Bus

- 客户端必须包含 `bus-amqp` 或 `bus-kafka` 才能响应 `busrefresh`
- 通过环境变量区分执行环境：`spring.cloud.config.discovery.enabled=true`

### 4. Actuator 安全

```yaml
management:
  endpoint:
    refresh:
      enabled: true
  endpoints:
    web:
      exposure:
        include: refresh,health
spring:
  security:
    user:
      name: devops
      password: ${ACTUATOR_PWD}
```

## 十一、优缺点

### 优点

- 与 Spring 体系无缝
- Git 后端天然具备版本回滚
- 加密原生支持
- 配置中心组件极少（一个 Server jar）
- 多 Profile/多 Label

### 缺点

- 无内置 UI（需引入第三方如 Spring Cloud Console 或自研）
- 刷新需要 Bus + MQ 配合（额外基础设施）
- `git` 仓库频繁拉取（每次 fetch，量大时延迟明显）
- 配置变更不是「推送」而是「轮询」，时效差
- `@Value` 变更需 `@RefreshScope`，否则不生效
- 没有细粒度权限审计（依赖 Git 仓库 ACL）
- YAML/Properties 体验尚可，复杂嵌套 json/xml 支持弱

适用：Spring 系中小规模、有现成 GitOps 流水线、对 UI/审计不敏感、想复用 Git 版本/分支能力。

## 十二、迁移到 Nacos / Apollo 的取舍

### 1. 从 Spring Cloud Config 迁到 Nacos

| 维度 | 影响 |
| ---- | ---- |
| **去 Git** | 配置入 Nacos DB，丧失 commit 级版本（虽然 Nacos 也有版本） |
| **去 Bus** | SDK 内置推送 |
| **去 encrypt 自管** | jasypt / KMS 插件 |
| **去 Bus 客户端依赖** | 减少 jar 体量 |

迁移成本：低（替换 starter 即可），运维成本下降。

### 2. 迁到 Apollo

| 维度 | 影响 |
| ---- | ---- |
| **部署数量** | 2 → 3+（多组件） |
| **审计/灰度** | 显著增强 |
| **`@Value`** | 不再需 `@RefreshScope` |

迁移成本：中（数据模型不同 + 客户端 API 差异），收益是企业级配置治理。

### 3. 何时不需要迁移

- 极小规模、单团队、配置只读不写
- Git 仓库为唯一可信源（GitOps 流程已建）
- Spring 全栈、不愿引入额外组件

## 十三、最佳实践

- **配置仓库专用**：不要把业务代码放一个仓库，config-repo 独立
- **`bootstrap.yml` 与 `application.yml` 分清**：bootstrap 只放配置中心地址/认证
- **`fail-fast` + retry**：避免启动期歧义
- **WebHook + Bus 全链路**：一次 push 全员生效
- **密钥外部化**：`encrypt.key` 走环境变量 / Vault，不入库
- **限流与签名保护 `actuator`**：用 Spring Security + 白名单 /auth
- **配置审计**：走 Git PR + Review 流程（SCM 即审计）
- **多环境**：用 branch + profile 组合（`release/uat` + `uat` profile）
- **小粒度配置文件**：按业务拆，order-service/user-service 解耦，避免一份大文件所有人订阅
- **本地缓存兜底**：`basedir` 放到持久化卷（容器中挂载 PVC）
- **监控 Config Server 自身**：`/actuator/health`、`/actuator/info` 拉通，看 Git fetch 延迟
