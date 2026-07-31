# 任务调度

按工具分文件整理任务调度原理与使用。

## 分类与索引

按场景分层：

| 分类 | 工具 |
| --- | --- |
| **OS 级** | [cron / systemd timers](cron-systemd.md) |
| **Java 进程内** | [Quartz](quartz.md) |
| **Java 分布式** | [XXL-JOB](xxl-job.md)、[Elastic-Job](elastic-job.md) |
| **DAG / 大数据** | [Apache Airflow](airflow.md)、[Prefect](prefect.md)、[Dagster](dagster.md)、[DolphinScheduler](dolphin-scheduler.md) |
| **持久化执行 / 工作流引擎** | [Temporal](temporal.md)、[Argo Workflows](argo-workflows.md)、[Tekton](tekton.md) |
| **K8s 批调度** | [Volcano](volcano.md) |
| **大数据 / 流处理内置调度** | [Spark](spark.md) |
| **云厂商托管** | [阿里云 SchedulerX](schedulerx.md)、AWS Step Functions、EventBridge Scheduler |

## 选型速查

| 场景 | 建议 |
| --- | --- |
| 单机 Linux 脚本 | cron / systemd timer |
| Spring 应用内调度 | @Scheduled + Quartz |
| Java 分布式定时任务，需可视化管理 | XXL-JOB |
| Java 大数据量分片 | Elastic-Job |
| 数据管道 DAG（ETL、ML） | Airflow / Prefect / Dagster |
| 国产大数据可视化 DAG | [DolphinScheduler](dolphin-scheduler.md) |
| 微服务长流程、状态机重试 | Temporal |
| K8s 原生工作流（CI、ML、批） | Argo Workflows / Tekton |
| K8s 上跑 AI / HPC 批作业 | Volcano |
| 不想运维 | 阿里云 SchedulerX / AWS EventBridge Scheduler |

## 概念对比

| 工具 | 调度模型 | 调度粒度 | DAG | 跨实例分片 | 长流程 / 状态 | 语言栈 | 自带 UI |
| --- | --- | --- | --- | --- | --- | --- | --- |
| cron | 时间触发 | cron 表达式 | ❌ | ❌ | ❌ | OS | ❌ |
| systemd timer | 时间 / 事件 | OnCalendar | ❌ | ❌ | ❌ | OS | ❌ |
| Quartz | 时间 + 链式触发 | Cron / Simple | ✔ (JobChains) | ❌ | ❌ | Java | 可视化插件 |
| XXL-JOB | 时间 / 手动 / API | Cron | ❌ | ✔ (分片广播) | 简易 | Java | ✔ |
| Elastic-Job | 时间 | Cron | ❌ | ✔ (Sharding) | ❌ | Java | ✔ (Console) |
| Airflow | 时间 / 外部触发 | Cron / dataset | ✔ | ✔ (Celery / K8s Executor) | TaskInstance 状态 | Python | ✔ |
| DolphinScheduler | 时间 / 上游 / 手动 | Cron + 依赖 | ✔ | ✔ (按 WorkerGroup) | ✔ 任务状态 | Java + YAML | ✔ 国产 |
| Prefect | 时间 / 事件 / 手动 | Cron / Interval | ✔ Flow | ✔ | ✔ (待办状态) | Python | ✔ Cloud / OSS UI |
| Dagster | 时间 / 资产 / 事件 | Cron / Sensor | ✔ Asset-aware | ✔ | ✔ | Python | ✔ |
| DolphinScheduler | 时间 / 上游 | Cron + 依赖 | ✔ | ✔ | Task 状态 | Java | ✔ 强 |
| Temporal | 事件驱动 | 工作流定义 | ✔ | ✔ | ✔ 持久化 | 语言 SDK | ✔ UI |
| Argo | 时间 / 事件 / 手动 | Cron | ✔ DAG / Step | ✔ | Workflow / Step 状态 | K8s YAML | ✔ |
| Tekton | 触发器 | 事件 | ✔ Task / Pipeline | ✔ | TaskRun 状态 | K8s YAML | ✔ Dashboard |
| Volcano | 调度器 | 队列 / PriorityClass | ✔ (含 gang) | ✔ (PodGroup gang scheduling) | Job 状态 | K8s CRD | ❌ 自带 / 用 Grafana |

## 选型要点

- **单机 vs 分布式**：单机任务直接 cron；需要高可用或横向扩容再上 Quartz / XXL-JOB
- **DAG 必要**：只用时间触发走简单调度；任务有依赖关系上 Airflow / DolphinScheduler / Argo / Temporal
- **分片必要**：数据量大需并行处理 → Elastic-Job / XXL-JOB 分片；K8s 上交给 Volcano gang scheduling
- **状态恢复**：长任务跨进程崩溃要恢复 → Temporal / Argo / Airflow（带 K8s executor 后）
- **可视化运维**：需要任务中心 / 监控告警 → XXL-JOB / DolphinScheduler / Airflow / Argo
- **语言栈**：Java 生态 → Quartz / XXL-JOB / Elastic-JOB / DolphinScheduler；Python → Airflow / Prefect / Dagster；K8s YAML → Argo / Tekton
- **托管优先**：不想自建 → 云厂商 SchedulerX / EventBridge Scheduler
