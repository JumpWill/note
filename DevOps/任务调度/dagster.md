# Dagster

以"资产 (Asset)"为中心的现代数据编排框架。来自 Elementl。强调"在数据编排上把数据本身作为一等公民"。

## 一、定位

- Asset-centric：按业务数据资产定义 pipeline
- 强类型 + Software-defined assets
- 用软件工程方法管理 data pipeline
- 适合 Analytics / ML pipeline

## 二、核心概念

| 概念 | 含义 |
| ---- | ---- |
| **Asset** | 数据资产（一张表、一个文件），有 Materialize 行为 |
| **Op** | 计算单元（旧版核心，新版中辅助） |
| **Job** | 一个执行单元，由 ops / assets 装配 |
| **Graph** | ops 的 DAG |
| **Source Asset** | 外部已存在的资产，仅注册 |
| **Partition** | 时间 / 枚举分区 |
| **Run** | Job / Asset 的一次执行 |
| **Sensor** | 监听外部条件 |
| **Schedule** | 时间触发 |
| **Resource** | 资源（DB 连接、IAM） |
| **IO Manager** | 资产持久化（File / Snowflake / S3） |
| **Repository** | 资产集合 |
| **Software-defined assets** | 用 Python 函数映射到数据资产 |

## 三、Asset 范式（Dagster 核心）

```python
from dagster import asset, job, Definitions

@asset
def orders_clean() -> pd.DataFrame:
    df = pd.read_csv("orders.csv")
    return df.dropna()

@asset
def orders_summary(orders_clean: pd.DataFrame) -> pd.DataFrame:
    return orders_clean.groupby("region").sum()

defs = Definitions(assets=[orders_clean, orders_summary])
```

`orders_summary` 接受 `orders_clean` 作为输入；Dagster 自动推断依赖。

## 四、分区

### 1. 静态分区

```python
from dagster import StaticPartitionsDefinition

@asset(partitions=StaticPartitionsDefinition(["us", "eu", "ap"]))
def regional_orders(region: str):
    return fetch_orders(region)
```

### 2. 时间分区

```python
from dagster import DailyPartitionsDefinition, asset

@asset(partitions=DailyPartitionsDefinition(start_date="2024-01-01"))
def daily_orders(context):
    date = context.partition_key
    ...
```

## 五、Job 与 Schedule

```python
from dagster import define_asset_job, AssetSelection, ScheduleDefinition

daily_job = define_asset_job(
    name="daily_orders_job",
    selection=AssetSelection.assets("orders_clean", "orders_summary"),
)

daily_schedule = ScheduleDefinition(
    job=daily_job,
    cron_schedule="0 3 * * *",
    execution_timezone="Asia/Shanghai",
)

defs = Definitions(
    assets=[orders_clean, orders_summary],
    jobs=[daily_job],
    schedules=[daily_schedule],
)
```

## 六、Resource & IO Manager

### 1. Resource

```python
from dagster import resource

@resource
def snowflake_conn():
    conn = sf.connect(...)
    yield conn
    conn.close()

@asset(required_resource_keys={"snowflake"})
def load_to_sf(...):
    conn = context.resources.snowflake
    ...
```

### 2. IO Manager

```python
from dagster import IOManager, io_manager
import pandas as pd

class MyIOManager(IOManager):
    def handle_output(self, context, obj: pd.DataFrame):
        path = f"s3://bucket/{context.asset_key.path}.parquet"
        obj.to_parquet(path)

    def load_input(self, context):
        return pd.read_parquet(...)

@io_manager
def my_io_manager(_):
    return MyIOManager()
```

Dagster 内置：

- `FilesystemIOManager`
- `S3PickleIOManager` / `S3ParquetIOManager`
- `BigQueryIOManager`
- `SnowflakeIOManager`
- `DuckDBIOManager`
- `DatabricksIOManager`
- `DuckDBPolarsIOManager`

## 七、Op（旧版）

```python
from dagster import op, job, In, Out

@op(ins={"data": In()}, out=Out())
def extract():
    return fetch()

@op
def transform(data):
    return process(data)

@op
def load(data):
    save(data)

@job
def etl():
    t = transform(extract())
    load(t)
```

新版推荐直接用 `@asset`。

## 八、Source Asset

外部已存在的数据，无需 Dagster 计算：

```python
from dagster import SourceAsset

orders_external = SourceAsset(
    key=AssetKey("orders_external"),
    io_manager_key="fs_io",
    description="raw orders from upstream",
)
```

用作下游 asset 的输入。

## 九、Sensor

```python
from dagster import sensor, RunRequest, SensorEvaluationContext

@sensor(job=orders_job)
def s3_file_sensor(context: SensorEvaluationContext):
    if file_exists("s3://bucket/ready.flag"):
        yield RunRequest(run_key="daily")
    return SkipReason("not ready")
```

- 周期扫描
- yield `RunRequest` 触发
- yield `SkipReason` 记录

## 十、Schedule

```python
from dagster import schedule, ScheduleEvaluationContext

@schedule(cron_schedule="0 3 * * *", job=etl, execution_timezone="Asia/Shanghai")
def daily_etl(context: ScheduleEvaluationContext):
    return RunRequest()
```

## 十一、运行和监控

### 1. Dagster Daemon / Dagster Webserver

```bash
dagster dev   # 开发，daemon + webserver
dagster job execute -j etl
```

### 2. CLI

```bash
dagster asset materialize -m my_module --select orders_clean --partition 2024-06-01
```

### 3. UI

- Assets：列表、分区、物化历史、lineage
- Runs：Run 历史
- Sensors / Schedules
- Code locations
- Resources
- Alerts

## 十二、Lineage

Dagster 自动跟踪 Asset 间的依赖：

```text
orders_external (SourceAsset)
    └── orders_clean
            └── orders_summary
            └── ml_feature
```

可视化上下游关系。

## 十三、Asset Materialization

```python
@asset
def orders_clean():
    df = pd.read_csv("orders.csv")
    return Output(df, metadata={"row_count": len(df)})
```

- Metadata 记录 metadata
- UI 上展示行数、schema 等

## 十四、资产策略

| 策略 | 含义 |
| ---- | ---- |
| **auto-materialize** | 自动根据依赖 / sensor 触发 |
| **Observability** | 仅读不写（Source / sensor） |
| **Partitioned / Time partitioned** | 时间窗口 |
| **Retries / Custom code** | Resource / Hook 自定义 |

## 十五、多进程执行

```python
from dagster import multiprocess_executor
@job(executor_def=multiprocess_executor)
```

或用 `dagster_celery`、`dagster_k8s` 的 Executor。

## 十六、Airflow / Prefect / Dagster 对比

| 维度 | Airflow | Prefect | Dagster |
| ---- | ------- | ------- | ------- |
| 模型 | DAG (Task chain) | Flow (函数) | Asset + Job |
| 抽象层 | Operator | Task | Asset |
| 静态 vs 动态 | 静态（DAG 文件） | 动态 | 动态 |
| Lineage | 弱 / 第三方 | 弱 | 原生 |
| 分区 | 弱（手动 DAG run） | 弱 | 原生 |
| 类型 | 弱 | Pydantic | 强（Type Hint） |
| 适合 | 数据 ETL | Python 团队 | 数据资产 / Analytics |

## 十七、最佳实践

- **Asset 颗粒度**：业务实体而非计算过程
- **分区分清楚**：时间窗 + 业务分区
- **Resource 注入**：DB 连接 / 凭据
- **IO Manager 选 S3 / Snowflake**：避免落本地
- **Auto Materialize**：用 `AutomationCondition` 自动触发
- **Code Location**：将 asset 拆到多个模块注册

## 十八、生态

- Cloud 版本：托管 UI
- 集成：`dagster-xxxxx` packages
- dbt / dbt-cloud integration：把 dbt 当 asset
- Dagster+：商业版
