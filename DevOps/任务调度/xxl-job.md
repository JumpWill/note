# XXL-JOB

分布式任务调度平台，许雪里（大众点评）开源，国产 Java 调度框架中社区最大、功能最易用的之一。

## 一、定位与特性

- 分布式任务调度中心 + 执行器（admin + executor）
- Cron 表达式 + 多种触发方式
- 内置 UI 调度中心
- 支持分片广播、故障转移、邮件告警
- 接入简单：业务代码写 `JobHandler`，框架负责调度
- 注册中心可选 MySQL / 自带轻 RPC / 其他

## 二、架构

```text
┌──────────────────────────────┐
│        Admin（调度中心）       │ ← Spring Boot Web
│   - 任务管理                   │
│   - 执行器管理                 │
│   - 调度线程 (Quartz)          │
│   - 监控告警                   │
│   - 日志查询                   │
└──────────────┬───────────────┘
               │ HTTP/RPC
               ▼
┌──────────────────────────────┐
│    Executor（执行器，业务 jar）│
│   - 内嵌在业务应用              │
│   - 注册到 Admin               │
│   - 调用 JobHandler.execute()  │
└──────────────────────────────┘
```

- Admin：调度中心，集群部署时使用 DB 行锁选举 leader，Quartz 触发
- Executor：嵌入业务进程，监听端口接收调度请求，启动线程池执行任务

## 三、核心概念

| 概念 | 含义 |
| ---- | ---- |
| **JobHandler** | 任务入口，注解 `@JobHandler` 或 `IJobHandler` 实现 |
| **Job** | 一个调度任务，含 cron / handler 名 / 路由策略 / 参数 |
| **Executor** | 执行器（一个应用），内部启动线程池执行任务 |
| **Router** | 路由策略：FIRST / LAST / ROUND / RANDOM / FAILOVER / BUSYOVER / SHARDING_BROADCAST |
| **Trigger** | 触发器：CRON / MANUAL / API / RETRY |
| **GLUE** | 在线写 Java / Shell / Python / DSL 等 |
| **Log** | 执行日志，Admin 可读 |
| **Callback** | 任务完成回调（Admin 记录执行状态） |

## 四、注册中心与通信

### 1. 注册中心

- 默认 MySQL（XXL-JOB-ADMIN 启动建表）
- 执行器 AppName 唯一标识，自动注册到 Admin
- 支持集群 Admin（以 MySQL 行锁实现 leader 选举）

### 2. RPC

- 自研轻量 RPC 协议；RESTful 也可
- Executor 在启动时注册 Token，Admin 用 token 鉴权
- 通信心跳：默认 30s

```properties
# xxl-job-admin 配置
xxl.job.admin.addresses=http://127.0.0.1:8080/xxl-job-admin
xxl.job.accessToken=default_token
```

## 五、Job 类型

### 1. Bean 模式（推荐）

业务 Java 任务，注解形式：

```java
@JobHandler("demoJobHandler")
@Component
public class DemoJobHandler extends IJobHandler {
    @Override
    public ReturnT<String> execute(String param) throws Exception {
        XxlJobHelper.log("start, param={}", param);
        // 业务
        return ReturnT.SUCCESS;
    }
}
```

- 由 Admin 通过 AppName 找到有 `@JobHandler` 注解的 Bean
- 支持参数动态传入

### 2. GLUE 模式（在线写代码）

- Java / Shell / Python / PHP / Node.js / PowerShell / DSL
- IDE 自动保存版本到 Admin
- 适合一次性脚本任务

### 3. 命令模式

通过命令行调用：

```text
admin -> executor -> python /opt/script.py
```

## 六、路由策略

| 策略 | 含义 |
| ---- | ---- |
| **FIRST** | 固定第一个 |
| **LAST** | 固定最后一个 |
| **ROUND** | 轮询 |
| **RANDOM** | 随机 |
| **CONSISTENT_HASH** | 按参数哈希，相同参数始终路由到同一节点 |
| **LEAST_FREQUENTLY_USED** | LFU |
| **LEAST_RECENTLY_USED** | LRU |
| **FAILOVER** | 故障转移 |
| **BUSYOVER** | 忙碌转移 |
| **SHARDING_BROADCAST** | 分片广播：所有节点都跑一次（每个节点不同片） |

## 七、分片广播

执行器数量动态扩展时最常用：

```text
Admin 触发 shardJob
   │
   ▼
向所有 Executor 发起分片广播
   │
   ▼
各 Executor 收到 shardingParam (0/1, 1/2, 2/3 等)
每个 Executor 处理自己分到的数据
```

```java
int shardIndex = XxlJobHelper.getShardIndex();
int shardTotal = XxlJobHelper.getShardTotal();
// 取余处理数据
List<Long> myPart = allData.stream()
    .filter(id -> id % shardTotal == shardIndex)
    .toList();
```

适合：

- 全量数据清洗
- 全表扫描迁移
- 大批量轮询检查

## 八、阻塞策略

线程池满时：

| 策略 | 含义 |
| ---- | ---- |
| **SERIAL_EXECUTION** | 串行：进队列等待 |
| **DISCARD_LATER** | 丢弃后续 |
| **COVER_EARLY** | 干掉旧的，覆盖为新的 |

## 九、故障转移

- 单节点失败 → 路由到其他 Executor
- 仅在 Router=FAILOVER 时启用
- 节点通过心跳检查在线状态

## 十、告警

- 邮件告警：默认
- 可扩展到钉钉 / 企业微信 / Slack 等
- 失败 / 超时阈值触发
- 告警接收人在 Admin 配置

## 十一、配置执行器

### 1. 引入依赖

```xml
<dependency>
  <groupId>com.xuxueli</groupId>
  <artifactId>xxl-job-core</artifactId>
  <version>2.4.0</version>
</dependency>
```

### 2. 配置

```properties
xxl.job.admin.addresses=http://admin:8080/xxl-job-admin
xxl.job.executor.appname=demo-app
xxl.job.executor.ip=           # 不填自动取网卡
xxl.job.executor.port=9999
xxl.job.executor.logpath=/data/applogs/xxl-job/jobhandler
xxl.job.executor.logretentiondays=30
xxl.job.accessToken=default_token
```

### 3. 容器化部署

- 启动时注册
- 多实例共享 Executor AppName，Admin 自动识别集群
- 注意 Serverless 环境（IP 不固定）可用 K8s 模式的新版（v3）

## 十二、v3 / v4 的变化

- K8s 原生支持：原生 K8s Executor（xxl-job v3 引入）
- 注册中心可选 Nacos / Etcd / Consul
- 任务支持 DAG（v4 起）
- 支持 ENJOY 容器化部署

## 十三、典型用法

### 1. 简单调度任务

```properties
# Admin 后台创建任务
AppName: demo-app
Cron: 0 0 3 * * ?
Executor JobHandler: demoJobHandler
参数: {"bizId":1}
```

### 2. 大批量数据处理（分片）

```java
@JobHandler("bigDataJobHandler")
public class BigDataJobHandler extends IJobHandler {
    @Override
    public ReturnT<String> execute(String param) {
        List<Long> allIds = db.queryAllIds();
        int total = allIds.size();
        int myIndex = XxlJobHelper.getShardIndex();
        int myTotal = XxlJobHelper.getShardTotal();
        for (int i = myIndex; i < total; i += myTotal) {
            process(allIds.get(i));
        }
        return ReturnT.SUCCESS;
    }
}
```

## 十四、优缺点

### 优点

- UI 完善，社区活跃
- Cron、并行、分片、告警齐全
- 接入简单，业务侧最少依赖
- 集群与故障转移

### 缺点

- 默认是单中心（Admin），需要 Admin HA
- 分片需要业务主动处理（不像 Spark 自动调度）
- 不支持 DAG（原版本）
- GLUE 模式可写代码但要有 ops 控制
- 监控告警默认邮件

适用：Java 应用、定时任务中心、可视化运维、Job 数量几百到几千级别。

## 十五、最佳实践

- **任务幂等**：用业务 ID / 状态判断避免重跑
- **分片利用 ROUND 模式或广播**
- **执行超时阈值**：按业务最长执行时间设置，避免长时间占用线程
- **报警收敛**：失败次数阈值 + 通知组
- **隔离**：不同 Executor 集群分开使用，避免互相影响
- **权限**：v2+ 支持 OIDC / LDAP 集成
- **观测**：通过 admin 自身 `/api/log`、`/api/jobInfo`
