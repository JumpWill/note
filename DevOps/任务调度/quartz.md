# Quartz Scheduler

Java 生态最经典的进程内调度框架，由 OpenSymphony 维护后转 Terracotta，后移交 [Quartz GitHub](https://github.com/quartz-scheduler/quartz) 社区。

## 一、核心概念

| 概念 | 含义 |
| ---- | ---- |
| **Job** | 要执行的任务，实现 `Job` 接口 |
| **JobDetail** | Job 的配置（参数、是否持久化、并发策略） |
| **Trigger** | 触发器，决定何时触发（CronTrigger、SimpleTrigger、CalendarIntervalTrigger） |
| **Scheduler** | 调度器，负责绑定 Trigger 与 JobDetail 并按时间执行 |
| **JobStore** | Job / Trigger / 状态的存储（RAMJobStore / JDBCJobStore） |
| **ThreadPool** | 执行 Job 的线程池（SimpleThreadPool） |

```text
                ┌──────────────┐
   Trigger ──→  │  Scheduler   │ ──→ ThreadPool ──→ Job
   JobDetail ─→ │  (RAM/JDBC)  │
                └──────────────┘
```

### 关系

- 一个 JobDetail 可以绑定多个 Trigger
- 一个 Trigger 只能对应一个 JobDetail
- Job 每次执行都是 new 出来的实例（单次执行），状态放 `JobDataMap`

## 二、架构原理

### 1. 调度线程模型

```text
QuartzSchedulerThread（调度线程 ×1）
   │ 扫描即将触发的 Trigger
   │
   ▼
acquireNextTriggers (30s 默认 look-ahead)
   │
   ▼
fireTriggers
   │
   ▼
JobRunShell 提交到 ThreadPool.execute
```

- 调度线程从 JobStore 拉触发时间
- 在 Trigger 之前 N 毫秒（`idleWaitTime`）准备执行
- 通过 `JobRunShellFactory` 创建 `JobRunShell` 提交到线程池

### 2. 线程池

默认 `SimpleThreadPool`，可配置：

| 配置 | 默认 |
| ---- | ---- |
| `threadCount` | 10 |
| `threadPriority` | Thread.NORM_PRIORITY (5) |
| 线程名 | `Worker-N` |

线程池满时 JobRunShell 阻塞，直到线程空闲；可能导致堆积，需要监控。

### 3. 错过触发 (Misfire)

如果调度线程没及时触发到该跑的 Trigger，会按 misfireInstruction 策略补救：

| 策略 | 说明 |
| ---- | ---- |
| `MISFIRE_INSTRUCTION_FIRE_ONCE_NOW` | 立即跑一次 |
| `MISFIRE_INSTRUCTION_DO_NOTHING` | 跳过，等下一个周期 |
| `MISFIRE_INSTRUCTION_RESCHEDULE_NEXT_WITH_EXISTING_COUNT` | 用现频率再排 |
| `CRONMISFIRE_INSTRUCTION_DO_NOTHING` | cron 跳过 |
| `CRONMISFIRE_INSTRUCTION_FIRE_ONCE_NOW` | cron 立即跑一次 |

### 4. JobDataMap

- 存储 Job 状态
- 放入 `JobExecutionContext` 传给 `execute()`
- 可序列化存入 JDBCJobStore

```java
JobDataMap data = new JobDataMap();
data.put("userId", 123);
job.getJobDataMap().putAll(data);
```

注意并发：Job 状态应显式并发控制，JobDataMap 在 RAMJobStore 下不严格同步。

## 三、Trigger 类型

### 1. SimpleTrigger

- 一次性或固定次数
- 设定开始时间、结束时间、间隔
- 不支持复杂日历

```java
Trigger t = TriggerBuilder.newTrigger()
    .withIdentity("job1", "group1")
    .startNow()
    .withSchedule(SimpleScheduleBuilder.simpleSchedule()
        .withIntervalInSeconds(10)
        .withRepeatCount(5))
    .build();
```

### 2. CronTrigger

- 类 Unix cron 表达式
- 支持秒级粒度
- 可表达复杂日历（多时间、星期组合）

```java
CronTrigger t = TriggerBuilder.newTrigger()
    .withIdentity("cron1", "group1")
    .withSchedule(CronScheduleBuilder.cronSchedule("0 0/30 * * * ?"))
    .build();
```

表达式与 unix cron 类似但更灵活：

```text
秒 分 时 日 月 周 [年]
0  0  3  *  *  ?    每天 3 点
0  0  9  ?  *  MON-FRI  工作日 9 点
```

### 3. CalendarIntervalTrigger

每隔 N 秒/分/小时/天/月/年触发，适合业务日历周期。

```java
CalendarIntervalTriggerBuilder
  .withInterval(2, IntervalUnit.HOUR)
  .build();
```

## 四、JobStore

### 1. RAMJobStore（默认）

- 内存
- 速度快
- 应用重启丢失任务
- 不能集群

```properties
org.quartz.jobStore.class=org.quartz.simpl.RAMJobStore
```

### 2. JDBCJobStore

- 关系数据库
- 持久化
- 支持集群（多实例互斥）
- 需建表 `QRTZ_*`

```properties
org.quartz.jobStore.class=org.quartz.impl.jdbcjobstore.JobStoreTX
org.quartz.jobStore.dataSource=myDS
org.quartz.dataSource.myDS.driver=com.mysql.cj.jdbc.Driver
org.quartz.dataSource.myDS.URL=jdbc:mysql://...
org.quartz.dataSource.myDS.user=...
org.quartz.dataSource.myDS.password=...
org.quartz.jobStore.isClustered=true
org.quartz.jobStore.clusterCheckinInterval=20000
```

### 3. 集群原理

```text
各节点定期更新 LAST_CHECKIN_TIME
获取 LOCK_ROW（SELECT ... FOR UPDATE）
   │
   ▼
获得锁的节点扫描 Triggers
其他节点跳过 acquireNextTriggers
```

- 通过数据库行锁或表锁实现 leader 选举
- 一台失效后其余节点继续运行

## 五、Listener 机制

### 1. JobListener

监听 Job 生命周期：

```text
jobToBeExecuted
jobExecutionVetoed（被 TriggerListener / SchedulerListener 拒绝）
jobWasExecuted
```

### 2. TriggerListener

```text
triggerFired
vetoJobExecution
triggerComplete / triggerMisfired
```

### 3. SchedulerListener

调度器级事件：Job/Trigger 加入删除、调度错误等。

## 六、Spring 集成

### 1. Spring Boot starter

```xml
<dependency>
  <groupId>org.springframework.boot</groupId>
  <artifactId>spring-boot-starter-quartz</artifactId>
</dependency>
```

```properties
spring.quartz.job-store-type=jdbc
spring.quartz.properties.org.quartz.jobStore.isClustered=true
```

### 2. @Scheduled vs Quartz

| 维度 | @Scheduled | Quartz |
| ---- | ---------- | ------ |
| 集群 | 需 ShedLock / Quartz | JDBC JobStore 支持 |
| 持久化 | 不支持 | JDBC Store 支持 |
| 动态增删 | 否 | API 增删 Task |
| UI | 无 | Quartz-Scheduler UI |
| 复杂度 | 低 | 中 |

### 3. ShedLock

简单集群互斥：基于数据库 / Redis / ZooKeeper 的 row lock，与 cron 表达式搭配：

```java
@Scheduled(cron = "0 0 * * * *")
@SchedulerLock(name = "dailyJob", lockAtMostFor = "10m")
public void daily() { ... }
```

适用于 Spring `@Scheduled` 需要唯一执行的场景。

## 七、典型用法

### 1. 简单 Job

```java
public class HelloJob implements Job {
    @Override
    public void execute(JobExecutionContext ctx) {
        System.out.println("hello @ " + Instant.now());
    }
}
```

```java
SchedulerFactory sf = new StdSchedulerFactory();
Scheduler scheduler = sf.getScheduler();
scheduler.start();

JobDetail jd = JobBuilder.newJob(HelloJob.class)
    .withIdentity("hello", "g1")
    .build();

CronTrigger t = TriggerBuilder.newTrigger()
    .withIdentity("helloTrg", "g1")
    .withSchedule(CronScheduleBuilder.cronSchedule("0/5 * * * * ?"))
    .build();

scheduler.scheduleJob(jd, t);
```

### 2. 持久化集群

- 数据库表必须存在
- `clusterCheckinInterval` 一般 5–20 秒
- `misfireThreshold` 控制迟到容忍

## 八、Quartz 在分布式场景的局限

- 没有分布式分片（每个节点拿到所有 Trigger 自跑）
- 需要业务层做 Sharding（数据库分片 ID、Hash 分桶）
- 没有可视化的运维后台（需借助第三方 UI）
- 集群利用行锁，对数据库有压力

如需：

- 分布式分片 → [XXL-JOB](xxl-job.md) / [Elastic-Job](elastic-job.md)
- 任务中心 / UI → XXL-JOB
- DAG 编排 → [Airflow](airflow.md) / [DolphinScheduler](dolphin-scheduler.md)

## 九、最佳实践

- **任务幂等**：可重入，保证多次执行结果一致
- **Job 无状态**：状态外部化（DB / Redis），不要依赖成员变量
- **超时控制**：用 `JobExecutionContext.isInterrupt()` 检测，不要无限阻塞
- **依赖**：Job 之间减少依赖；需要编排用 DAG 工具
- **监控**：通过 JobListener / Micrometer 导出触发次数、运行耗时、失败数
- **关闭泄漏**：scheduler shutdown 必须调用 `shutdown(true)` 才能等待执行完
- **时区**：Cron 表达式使用业务期望时区，明示配置
