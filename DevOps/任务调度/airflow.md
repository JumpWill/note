# Apache Airflow

Python 编写的可编程工作流调度平台，Airbnb 起源，Apache 顶级项目。当前数据工程主流选择。

## 一、定位与特点

- 工作流即代码（Workflow as Code）：用 Python 定义 DAG
- 调度 + 监控 + 日志 + 告警全栈
- 插件/Operator 生态丰富（Hadoop / Spark / K8s / AWS / GCP / Aliyun）
- 适合数据工程师，能写 Python 即可
- 2.x 主要为 TaskFlow API，3.x 进一步改进

## 二、架构

```text
┌────────────────────────────────────┐
│ Web Server（DAG 显示 / 操作）        │
├────────────────────────────────────┤
│ Scheduler（调度器 / DAG 解析）      │
├────────────────────────────────────┤
│ Executor 池（决定 Task 怎么跑）     │
│   - SequentialExecutor             │
│   - LocalExecutor（多进程）         │
│   - CeleryExecutor（多机器）        │
│   - CeleryKubernetesExecutor        │
│   - KubernetesExecutor             │
│   - CeleryExecutor / DaskExecutor   │
├────────────────────────────────────┤
│ Worker（消费任务）                  │
├────────────────────────────────────┤
│ 数据库（Metadata DB）              │
│   - PostgreSQL / MySQL / SQLite    │
└────────────────────────────────────┘
```

- Scheduler 解析 DAG，根据 schedule + start_date + dependencies 决定是否要触发 TaskInstance
- 把 TaskInstance 推到 Executor
- Executor 通过对应后端（Celery/K8s/Local）分发执行

## 三、核心概念

| 概念 | 含义 |
| ---- | ---- |
| **DAG** | 一个工作流 |
| **Task** | 一个工作步骤 |
| **Operator** | Task 模板（PythonOperator / BashOperator / KubernetesPodOperator …） |
| **TaskInstance** | Task 的一次执行实例 |
| **DagRun** | DAG 的一次调度实例 |
| **Variable / Connection** | 全局配置 |
| **XCom** | Task 间传递参数 |
| **Pool** | 并发槽位 |
| **Priority Weight** | 优先级 |
| **Sensor** | 等待外部条件达成的 Operator |
| **Hook** | 与外部服务交互的封装 |
| **Trigger / Triggerer** | 异步触发器（3.x） |
| **Listener** | 事件监听（Task 失败 / 成功） |
| **Provider / Hooks** | 第三方集成 |

## 四、DAG 定义

```python
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

default_args = {
    "owner": "data",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=2),
}

with DAG(
    dag_id="etl_daily",
    default_args=default_args,
    schedule="0 3 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["etl", "daily"],
) as dag:
    extract = BashOperator(
        task_id="extract",
        bash_command="python /opt/jobs/extract.py {{ ds }}",
    )
    transform = PythonOperator(
        task_id="transform",
        python_callable=transform_fn,
        op_kwargs={"date": "{{ ds }}"},
    )
    load = BashOperator(
        task_id="load",
        bash_command="python /opt/jobs/load.py",
    )

    extract >> transform >> load
```

- `{{ ds }}`：模板变量，调度日期（默认前一日）
- `with DAG(...)` 自动把 task 收集进 DAG
- `>>` 定义依赖

## 五、TaskFlow API（2.0+）

```python
@dag(schedule="@daily", start_date=datetime(2024,1,1), catchup=False)
def etl_daily():
    @task
    def extract():
        return fetch()

    @task
    def transform(rows):
        return [r*2 for r in rows]

    @task
    def load(rows):
        save(rows)

    load(transform(extract()))

dag = etl_daily()
```

- 自动 XCom：返回值自动作为下一次输入
- 减少依赖显式声明

## 六、Executor

| Executor | 适用 |
| -------- | ---- |
| SequentialExecutor | 单线程，调试 |
| LocalExecutor | 单机多进程，并行跑同一个 DAG 中的多个 Task |
| CeleryExecutor | 多 Worker，分发到队列 |
| KubernetesExecutor | 每个 Task 启动一个 K8s Pod（隔离） |
| CeleryKubernetesExecutor | Hybrid，敏感 Task 走 K8s |
| KubernetesLocalExecutor | K8s Pod 内运行 Task |
| CeleryDaskExecutor | Dask 集群 |

### KubernetesExecutor 示例

```yaml
kubernetes_executor:
  namespace: airflow
  image: my-airflow:2.10.0
  pod_template_file: /etc/airflow/pod_template.yaml
  delete_worker_pods_on_failure: True
  delete_worker_pods_on_completion: True
```

- 每个 Task = 一个 Pod
- 资源 / Pod 模板可配置
- 适合 K8s 原生

## 七、Connection 与 Variable

```python
from airflow.models import Variable
Variable.set("slack_token", "xxx")

from airflow.hooks.base import BaseHook
conn = BaseHook.get_connection("my_postgres")
```

UI：`Admin -> Connections / Variables`

## 八、XCom

Task 之间传递参数：

```python
def push(**ctx):
    ctx["ti"].xcom_push(key="rows", value=[1, 2, 3])

def pull(**ctx):
    rows = ctx["ti"].xcom_pull(key="rows", task_ids="push_task")
```

注意事项：

- 默认存 Metadata DB（小数据）
- 大对象用 S3/GCS + XCom pointer（自定义 Backend）
- Airflow 2.x 后 XCom 的 backend 可改为 Object Storage

## 九、Sensor

等待外部条件，常用：

- `S3KeySensor`
- `ExternalTaskSensor`（等另一个 DAG 的 Task）
- `HttpSensor`
- `SqlSensor`
- `FileSensor`

```python
wait = S3KeySensor(
    task_id="wait_s3",
    bucket_name="mybucket",
    bucket_key="data/{{ ds }}/ready.flag",
    aws_conn_id="aws_default",
)
```

加 timeout / soft_fail / mode (reschedule / poke) / exponential_backoff。

## 十、Pools / Priority / Slots

- **Pool**：限制某类任务的并发
- **Priority Weight**：Scheduler 排队顺序
- **queue**：Celery/K8s 用，决定路由到哪个 Worker
- **max_active_tasks / max_active_runs**：数量限制

## 十一、回填（Backfill）

```bash
airflow dags backfill -s 2024-01-01 -e 2024-01-31 etl_daily
```

要求：`catchup=False` 时只会跑历史调度（不会自动 catchup）。

## 十二、调度测试

```bash
# 仅渲染 schedule
airflow dags schedule
# 列出下次执行日期
airflow dags next-execution etl_daily
```

## 十三、安全与多租户

- FAB RBAC / 团队权限
- `connections.add` / `users.create` API
- Audit log（3.x）
- 启用 Fernet Key 加密 Connection
- Secret Backend：`AWS Secrets Manager / Hashicorp Vault / GCP Secret Manager`

```ini
[secrets]
backend = airflow.providers.amazon.aws.secrets.ssm.AwsSsmSecretsBackend
backend_kwargs = {"connections_prefix": "/airflow/connections", "variables_prefix": "/airflow/variables"}
```

## 十四、UI

- DAGs View：列表，红绿黄状态
- Grid / Graph / Gantt：执行可视化
- Calendar：历史执行日历
- Browse / Task Instances：Task 状态
- Admin / Connections / Variables / Pools

## 十五、可观测性

- Prometheus + statsd_exporter
- OpenTelemetry 支持（2.7+）
- 自己的 metrics：

| Metric | 用途 |
| ------ | ---- |
| `dag_processing.total_parse_time` | DAG 文件解析时长 |
| `scheduler_heartbeat` | scheduler 心跳 |
| `executor.open_slots` | 槽位 |
| `task_instance.duration` | 任务耗时 |

## 十六、Airflow 3.x

- Task SDK：用独立 Task worker 进程
- API Server 与 Webserver 分离
- DagFileProcessor 用 Processor 服务
- Scheduler 性能 / 可扩展性提升
- Edge Executor：把 Task 推到边缘节点跑

## 十七、典型用法

### 1. ETL DAG

```python
extract >> transform >> [
    load_dw,
    send_alert
] >> done
```

### 2. Data Lake 同步

```python
s3_sensor >> glue_crawler_job >> dq_check >> redshift_copy
```

### 3. ML Pipeline

```python
train = KubernetesPodOperator(
    name="train",
    image="trainer:1.0",
    arguments=["--data", "{{ ds }}"],
    config_file="/etc/airflow/kubeconfig",
    in_cluster=False,
    cluster_context="eks-prod",
    task_id="train",
)
```

## 十八、最佳实践

- **DAG 即代码**：把 DAG 文件纳入 Git，做 code review
- **小 DAG**：避免一个 DAG 包含上千个 Task（Split to SubDAG）
- **池与并发**：使用 Pool 控制资源密集 DAG 的并发
- **幂等**：Task 设计要支持重试
- **回调**：`on_failure_callback` / `on_success_callback`
- **幂等 XCom**：避免大对象
- **测试**：`airflow dags test`, `airflow tasks test`, pytest + DAG 对象
- **时间表达式**：`execution_date` vs `logical_date`：注意在 Airflow 3.x 已经去除 execution_date

## 十九、自有 Operator / Hook

```python
from airflow.models.baseoperator import BaseOperator

class HelloOperator(BaseOperator):
    def __init__(self, name, **kwargs):
        super().__init__(**kwargs)
        self.name = name

    def execute(self, context):
        print(f"hi {self.name}")
```

## 二十、与 Argo / DolphinScheduler 对比

| 维度 | Airflow | Argo | DolphinScheduler |
| ---- | ------- | ---- | ---------------- |
| 描述 | Python DAG | K8s YAML | 拖拽 DAG |
| 执行模型 | Executor | Pod/PodSet | Worker 内跑任务 |
| 隔离 | 按 Executor | 每任务 Pod | WorkerGroup 物理隔离 |
| 入门 | 中 | K8s + yaml | 简单 |
| 适合团队 | 数据 | DevOps / SRE | 跨职能 |

## 二十一、运维经验

- **DB 性能**：TaskInstance 表膨胀 → 定期清理（`airflow db clean` 或保留 90 天）
- **Scheduler 卡顿**：DAG 文件过多，purge `dag_runs` 历史
- **Triggerer**：异步 Sensor 改为 reschedule 节省资源
- **HA**：Scheduler 用 HA（多 Scheduler 选举）
- **升级**：先在测试环境验证，再升级 Prod
