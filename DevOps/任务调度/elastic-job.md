# Elastic-Job

当当网开源、现进入 Apache 生态的分布式分片调度框架，由张亮主导。Elastic-Job = 调度 + 分布式分片 + 弹性扩缩。

## 一、组件

| 模块 | 作用 |
| ---- | ---- |
| **Elastic-Job-Lite** | 轻量去中心化，多实例通过 ZK 注册协调 |
| **Elastic-Job-Cloud** | Mesos + Mesh 容器化版（已不推荐，社区主推 Lite） |
| **Elastic-Job-Infra** | 通用基础设施（job-event / tracing / openjob） |

社区主线推荐 Lite 版 + Zookeeper。

## 二、核心概念

| 概念 | 含义 |
| ---- | ---- |
| **Job** | 任务抽象（SimpleJob / DataflowJob / ScriptJob） |
| **Sharding** | 任务分片（每片在不同执行器上） |
| **Sharding Item** | 分片项，对应一个作业子项 |
| **Sharding Strategy** | 轮询 / 自定义 |
| **JobConfig** | 命名空间、cron、分片数、failover、max time diff |
| **JobListener** | 任务前后事件回调 |
| **Zookeeper** | 注册中心，存储分片 / 主备 / 失效转移 |

## 三、架构

```text
        Zookeeper（注册中心）
        /elastic-job/jobname
        ├── config
        ├── instances
        │    ├── ip1
        │    └── ip2
        ├── sharding/0  (leader)
        ├── sharding/1  (leader)
        └── servers
             ├── ip1:status
             └── ip2:status

应用 A（分片 0、1）  应用 B（分片 2）
```

- 所有节点通过 ZK 注册
- 分片信息在 ZK 上分配
- 任意节点都可调用 `triggerOneJob` 触发全部分片

## 四、三种 Job 类型

### 1. SimpleJob

```java
@ElasticSimpleJob(jobName = "demoSimpleJob",
                  cron = "0/5 * * * * ?",
                  shardingTotalCount = 3,
                  shardingItemParameters = "0=Beijing,1=Shanghai,2=Guangzhou")
public class DemoSimpleJob implements SimpleJob {
    @Override
    public void execute(ShardingContext ctx) {
        int shardingItem = ctx.getShardingItem();
        switch (shardingItem) {
            case 0 -> System.out.println("bj");
            case 1 -> System.out.println("sh");
            case 2 -> System.out.println("gz");
        }
    }
}
```

### 2. DataflowJob（流式）

`fetchData` 与 `processData` 持续执行：

```java
public class DemoDataflowJob implements DataflowJob<Foo> {
    @Override
    public List<Foo> fetchData(ShardingContext ctx) {
        if (cursor >= end) return Collections.emptyList();
        return query(cursor, batchSize);
    }
    @Override
    public void processData(ShardingContext ctx, List<Foo> data) {
        data.forEach(process);
    }
}
```

- 数据为空时停止当前作业，发起下一轮（perpetual）
- 适合流式数据消费

### 3. ScriptJob

- 调用 Shell / Python / 自定义命令
- `scriptCommandLine`

## 五、注册中心（Zookeeper）

Elastic-Job 强依赖 ZK（也支持 Restful / IP 直连模式）。

```text
namespace             项目级隔离
config                YAML / Properties 上传配置
instances             在线实例
sharding/{item}       分片 leader 信息
servers/{ip}          节点状态
leader                主备选举
```

ZK 不能用时，Lite 启动失败；线上必须 ZK 集群。

## 六、高可用

### 1. 分片不变性

分片总数一旦创建，运行中不变。增加 / 删除实例时分片会重新分配。

### 2. Failover

某实例挂了，对应分片在其他实例临时跑完。

```yaml
failover: true
failoverInterval: 2000   # 检测间隔
```

### 3. 错过触发重跑

`maxTimeDiffSeconds`：cron 时间差 / 时钟差超过则不触发（容错）。

`monitorExecution`：已经存在的执行实例，新的不会并发起来。

### 4. 幂等 / 错过策略（misfire）

Elastic-Job 不支持直接 misfire 高级策略，需要在业务层处理。

## 七、运维与控制台

### 1. Console

Spring Boot Admin 风格控制台：

- 任务维度概览
- 历史执行记录
- 节点状态、ZNode 查看
- 触发、改分片

### 2. 一致性哈希

ShardingStrategy 自定义：

```java
public class HashShardingStrategy implements JobShardingStrategy {
    @Override
    public Map<JobInstance, List<Integer>> sharding(...) {
        ...
    }
}
```

按业务 key 做哈希，让相同 key 落到同一节点。

## 八、配置示例

```yaml
elasticjob:
  reg-center:
    server-lists: zk1:2181,zk2:2181,zk3:2181
    namespace: myproj
    base-sleep-time-milliseconds: 1000
    max-sleep-time-milliseconds: 3000
    max-retries: 3
  jobs:
    demoSimpleJob:
      elastic-simple-job:
        cron: 0/5 * * * * ?
        sharding-total-count: 3
        sharding-item-parameters: 0=A,1=B,2=C
        failover: true
        misfire: false
        overwrite: true
        job-sharding-strategy-class: com.x.sharding
```

## 九、Spring Boot 集成

```xml
<dependency>
  <groupId>com.dangdang</groupId>
  <artifactId>elastic-job-spring-boot-starter</artifactId>
</dependency>
```

需手写 ZK 注册中心 bean 和 Job 调度 bean。

## 十、与 XXL-JOB 对比

| 维度 | Elastic-Job | XXL-JOB |
| ---- | ----------- | ------- |
| 注册中心 | ZK 强依赖 | MySQL/AppName |
| 调度器 | 嵌入业务 | Admin 中心 |
| 分片 | 自动分片注册 | 业务手动按 shardingParam |
| UI | Lite Console | 内置 Admin |
| 任务量级 | 高（十万级任务） | 中（几千级） |
| DAG | ❌ | ❌ |
| 运维成本 | 需要 ZK | 部署中心节点 |

适用：超大批量任务，需要 ZK 协调的 Java 大型应用。

## 十一、当前状态

- Lite 主版本长期迭代：`elastic-job` 项目在 Apache 后续发展放缓
- 大量老项目仍在使用 `com.dangdang:elastic-job-*`
- 新项目可考虑：XXL-JOB（更易 UI 化）、PowerJob（Lite 思想 + 新架构）

## 十二、最佳实践

- **分片维度的选择**：按业务 key 哈希让局部数据落到单节点
- **幂等**：任务一定要可重入
- **看 ZK**：ZK 节点是监控重点
- **小批量排队**：monitorExecution = true 防止并发
- **脚本任务用 ScriptJob**：Python/Shell 不用嵌入应用
- **可视化**：对接 PowerJob Console 替代实现
