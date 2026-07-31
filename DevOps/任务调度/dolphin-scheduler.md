# Apache DolphinScheduler

海豚调度，国产开源大数据分布式 DAG 工作流调度系统，Apache 顶级项目，从易观（原大众点评团队）起源。在国产替代 Airflow 场景中最常用。

## 一、定位

- 分布式、易扩展的可视化 DAG 工作流调度系统
- 专为大数据场景设计（ETL、离线、实时）
- 强可视化：拖拉拽构建 DAG
- 中心化调度 + Worker 执行

## 二、架构

```text
┌──────────────────────────────────────┐
│                UI (Web)              │
├──────────────────────────────────────┤
│             API Gateway             │
├──────────────────────────────────────┤
│ Master（调度器集群，负责 DAG 解析）   │
│   ├ Scheduler                        │
│   ├ Dispatcher                       │
│   └ Executor (Task dispatch)        │
├──────────────────────────────────────┤
│ Worker（任务执行器集群）               │
│   ├ Task 执行                         │
│   └ 日志采集                          │
├──────────────────────────────────────┤
│ Alert Server（告警）                  │
├──────────────────────────────────────┤
│ 存储：MySQL / PostgreSQL / H2          │
│ 注册：Zookeeper / etcd                │
└──────────────────────────────────────┘
```

- Master 集群：无状态，依赖 ZK 选举主从或对等处理
- Worker 集群：执行具体 task
- UI 只与 API 通信

### 1. 角色（v3+）

| 角色 | 责任 |
| ---- | ---- |
| **Master** | 接收 DAG、解析依赖、调度 Task、容错 |
| **Worker** | 拉取任务、执行、回写状态 |
| **AlertServer** | 告警发布 |
| **ApiServer** | 对外 API |
| **UI** | 前端 |

## 三、核心概念

| 概念 | 含义 |
| ---- | ---- |
| **Tenant** | 租户（关联用户与 Worker 组） |
| **Tenant → WorkerGroup** | 调度关系 |
| **Project** | 项目，资源（流程、用户）隔离 |
| **Workflow / Process** | 工作流（一个 DAG） |
| **Task** | 任务节点（Shell / SQL / Spark / Flink / MR …） |
| **TaskInstance** | 任务实例，每次执行 |
| **ProcessInstance** | 工作流实例 |
| **Scheduling** | 时间触发（Cron） |
| **Sub-Process** | 子工作流 |
| **Conditions / Depend** | 依赖分支 |
| **Recovery / Rerun** | 重跑 / 容错 |
| **Priority** | 任务优先级 |
| **Global Param** | 全局参数 + 自定义变量 |
| **User Defined Function** | UDF |

## 四、Task 类型

DolphinScheduler 支持节点类型最丰富的调度器之一：

| 类型 | 含义 |
| ---- | ---- |
| **Shell** | 直接跑 Shell |
| **Python** | 调用 Python |
| **SQL** | Hive / MySQL / PG / Oracle / ClickHouse / SparkSQL / StarRocks / Doris / Presto |
| **Spark** | Spark 程序（Jar / PySpark） |
| **Flink** | Flink 程序（Jar / PyFlink） |
| **MR / Hive / Hook / SubProcess / PyDolphin / Kubernetes / SageMaker / SeaTunnel / DataX / Pigeon / Sqoop** | 大量集成 |
| **Conditions** | 分支 |
| **Switch** | 多分支 |
| **SubProcess** | 子流程 |
| **Dynamic** | 动态生成节点 |
| **Http** | HTTP 触发 |

## 五、依赖与分支

### 1. 依赖类型

- 上一节点成功 / 失败再走
- 多父亲 / 多孩子节点
- 跨流程依赖（依赖其他流程的某节点）

### 2. 分支

- Conditions：表达式控制分支
- Switch：枚举分支

### 3. DAG 例子

```text
start
  │
  ├── shell_extract
  │      │
  │      ├── sql_dim
  │      │      │
  │      └── sql_dwd
  │             │
  │             ├── sql_dws
  │             │
  │             ├── (condition: is_weekday)
  │             │       └── sql_weekly
  │             │
  │             └── sql_dm
  │
  └── sql_meta
         │
         └── (switch: region)
                ├── south  → shell_south
                └── north  → shell_north
end
```

## 六、调度策略

### 1. 调度方式

| 方式 | 含义 |
| ---- | ---- |
| **Cron** | 时间触发 |
| **Manual** | 手动触发 |
| **API** | 通过接口触发 |
| **补数（Run with Conditions）** | 补跑历史日期 |

### 2. 补数 (Backfill)

- 日期范围补数
- 失败重试
- 串行 / 并行补数

### 3. 优先级

- 任务优先级：HIGH / MEDIUM / LOW
- Worker 选择算法考虑优先级
- 队列里先取高优先级

### 4. Kill / Pause

- 实时终止某流程实例
- 暂停运行中实例
- 失败状态跳过

## 七、高可用

### 1. Master HA

- 多 Master 同时工作
- 通过 ZK 选主进行部分主备（Master 任务分发和心跳）
- Master 之间状态同步通过 DB

### 2. Worker HA

- Worker 是无状态的，执行完结束
- 任意 Worker 收到任务都能执行

### 3. 容错

- Task 超时回收
- Worker 失败 reschedule
- Master failover 让其他 Master 接手未完成任务

## 八、运行参数化

### 1. 全局参数

```text
${biz_date}     调度时间（默认昨天）
${system.biz.date}  系统日期
${global_params.user_id}
```

### 2. 自定义参数

- Spark/Flink 任务以 `--conf` 形式传入
- Shell/Sub-Process 通过环境变量 + 位置参数
- 文档级别传参

### 3. 资源

- 文件资源（jar / py / sh / conf）
- 租户内权限
- 任务引用时按 ID 解析

## 九、API

| API | 含义 |
| --- | ---- |
| `/projects/{code}/process/define` | 创建 |
| `/projects/{code}/process/release` | 发布 |
| `/projects/{code}/schedule/online-task` | 上线 |
| `/projects/{code}/executors/start` | 触发 |

API Token 管理在 UI 中创建。

## 十、K8s 部署

- 通过 Helm Chart 部署 Master / Worker / API / Alert
- 通过 `values.yaml` 配置资源、SVC
- 注册中心可选 Zookeeper（常用外部 ZK）
- 任务执行可在 Worker 内本地执行，也支持 K8s Worker 模式（Task 类型为 K8s 时拉起 Pod）

## 十一、对比 Airflow

| 维度 | DolphinScheduler | Airflow |
| ---- | ---------------- | ------- |
| 构建 DAG | Web 拖拉拽 | Python 代码 |
| 适合人员 | 业务 / 分析师 | 数据工程师 |
| 集群部署 | K8s / VM | VM / K8s (via Executor) |
| 任务类型 | 图形化配置多 | 需代码 Operator |
| 监控告警 | 内置 | 第三方集成 |
| 大数据 connector | 官方众多 | Operator 生态 |
| 中国本土化 | 中英文 | 英文为主 |

## 十二、典型场景

- 离线数据仓库 ETL（DIM/DWD/DWS/ADS）
- 实时任务提交（Flink / Spark Streaming）
- AI / ML pipeline
- 业务报表生成
- 数据库批量清理

## 十三、最佳实践

- **租户管理**：按业务 / 团队分 WorkerGroup
- **资源**：上传 jar 时按版本控制
- **参数化**：业务日期统一用 `${biz_date}`
- **依赖**：长链路 DAG 拆子流程
- **告警**：失败 / 超时 / 调度中断
- **版本升级**：测试环境验证，留升级备份
- **审计**：API 触发要走鉴权

## 十四、常见坑

- Master / Worker 时间不同步导致调度漂移 → 启用 NTP / chrony
- WorkerGroup 不一致导致任务积压 → 配置优先级 + 资源抢占
- 补数时一定要用 `${biz_date}` 不能用当前日期
- 大 jar 文件资源频繁上传会膨胀 → 升级

## 十五、v3 新特性

- 多 Master / 多 Worker 拆分角色
- 完善 Task 类型（Kubernetes、Dynamic、SageMaker）
- K8s 注册中心可选 etcd
- Workspace 隔离多租户

推荐新部署使用 `3.x`。

---

# 已合并在本文件：原理与使用详解。

参考：[Apache DolphinScheduler 官网](https://dolphinscheduler.apache.org/)。
