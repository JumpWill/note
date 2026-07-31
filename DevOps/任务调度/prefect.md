# Prefect

现代 Python 工作流编排框架，Airflow 的"轻量化 + 强类型 + 易上手"替代品。两种部署模式：

| 模式 | 含义 |
| ---- | ---- |
| **Prefect OSS** | 开源，可本地部署 Server（单进程） |
| **Prefect Cloud** | 托管，提供 UI、团队、监控、计费 |

## 一、定位与思想

- "Negative engineering"：把数据流中的运维负担降到最低
- 以 Flow 为核心：函数即工作流
- 动态 DAG：可运行时条件决定下一步
- 强类型 + Pydantic 校验
- Worker / Flow Run 模型：与 Airflow 任务、Worker 类似

## 二、与 Airflow 的核心区别

| 维度 | Prefect | Airflow |
| ---- | ------ | ------- |
| DAG 模型 | 临时（任务执行时动态生成） | 静态（DAG 文件解析后固定） |
| 错误 | 默认 None / 跳过 | 默认 retry |
| 部署 | GitHub / Container / Cloud Run | DAG 文件 |
| UI | Web UI（OSS 也可用） | Web UI |
| 触发 | Decorator + Schedule | Operator 链 |
| 数据传递 | Flow → Task 入参 | XCom |
| 状态持久化 | DB（Postgres/SQLite） | DB |
| 学习曲线 | 中（Python） | 中（Python+Operator 生态） |

## 三、核心概念

| 概念 | 含义 |
| ---- | ---- |
| **Flow** | `@flow` 装饰的函数 |
| **Task** | `@task` 装饰的子单元（自动被 Flow 捕获） |
| **Flow Run** | Flow 的一次执行 |
| **Task Run** | Task 的一次执行 |
| **Schedule** | 时间、cron、间隔、Event |
| **Deployment** | Flow 的部署单元（包含仓库、镜像、执行入口） |
| **Worker** | 拉取 Flow Run 执行 |
| **Pool / Limit** | 并发约束 |
| **State** | Pending / Running / Completed / Failed / Cancelled / Crashed |
| **Result** | 数据传递方式（默认 in-memory / S3 / GCS / 自定义） |
| **Cache Policy** | Task 缓存，避免重算 |
| **Concurrency Limit** | 同一时刻运行数量限制 |

## 四、基本用法

### 1. 最简 Flow

```python
from prefect import flow, task

@task
def get_data():
    return [1, 2, 3]

@task
def process(items):
    return sum(items)

@flow(name="demo", log_prints=True)
def main():
    items = get_data()
    return process(items)

if __name__ == "__main__":
    main()
```

直接 `python demo.py` 即可运行（区别于 Airflow：Airflow DAG 文件必须由 Scheduler 调度）。

### 2. 参数化

```python
from prefect import flow
from datetime import timedelta

@flow
def daily(date: str):
    print(f"running for {date}")

if __name__ == "__main__":
    daily("2024-01-01")
```

### 3. Cron 调度

```python
from prefect import flow

@flow
def hourly_etl():
    ...

if __name__ == "__main__":
    hourly_etl.serve(
        name="hourly-etl",
        schedules=[
            {"cron": "0 * * * *", "timezone": "Asia/Shanghai"}
        ],
    )
```

`serve` 启动常驻进程，自动触发。

### 4. 部署到 Worker

```bash
prefect deployment build src/my_flow.py:daily -n prod -q default
prefect deployment apply daily-deployment.yaml
prefect worker start -p default
```

或从 GitHub Pull：

```bash
prefect deployment build src/my_flow.py:daily \
  --name prod \
  --storage github/jumpwill/etl
prefect deployment apply ...
```

## 五、Task 的高级特性

### 1. Retry

```python
from prefect import task

@task(retries=3, retry_delay_seconds=10, timeout_seconds=300)
def flaky():
    ...
```

### 2. Cache

```python
@task(cache_key_fn=task_input_hash, cache_expiration=timedelta(hours=1))
def slow():
    ...
```

缓存 key：相同输入即复用结果。

### 3. 并发

```python
from prefect import flow, task
from prefect.futures import wait

@task
def process(i):
    ...

@flow
def parallel():
    futures = [process.submit(i) for i in range(10)]
    wait(futures)
```

`submit` 返回 `PrefectFuture`，支持并发。

### 4. 异步 / 协程

```python
@task
async def task_a():
    await something()
```

### 5. 条件分支

Prefect 支持动态 DAG，运行时根据参数决定 Task 列表：

```python
@flow
def branching(env: str):
    a()
    if env == "prod":
        b()
    else:
        c()
    d()
```

## 六、State 与结果

### 1. 状态机

```text
Pending → Running → Completed
                  ↘ Failed → Retrying → Running
                  ↘ Cancelled
                  ↘ Crashed
```

### 2. 自定义状态

```python
from prefect.states import Failed, Completed

@task
def check():
    if bad:
        return Failed(message="...")
    return Completed(message="ok")
```

### 3. Result

```python
@task(result_serializer="json", result_storage="s3-bucket")
def task_a():
    return data
```

## 七、调度与触发

### 1. Schedule

```python
from prefect.schedules import Cron

@flow(schedule=Cron("0 3 * * *", timezone="Asia/Shanghai"))
def daily():
    ...
```

### 2. Event-based Trigger

```bash
prefect event-trigger create myflow --on-file-arrived my-bucket
```

### 3. Manual / API

```bash
prefect deployment run "flow-name/deployment-name"
```

或 HTTP API。

## 八、Work Pool / Worker

```text
Prefect Server (API + DB)
    │
    ▼
Work Pool / Queue
    │
    ▼
Worker（pull flow run）
    │
    ▼
Subprocess / Container / K8s
```

Work Pool 分类：

| Type | 用途 |
| ---- | ---- |
| **Process** | 本地子进程 |
| **Docker** | 容器 |
| **Kubernetes** | K8s Job |
| **ECS / Cloud Run** | 各云服务 |

### Kubernetes

```yaml
workPool:
  type: kubernetes
  baseJobTemplate:
    spec:
      imagePullSecrets:
        - name: my-secret
```

## 九、可观测

- UI：Flow Runs / Task Runs / Logs / Variables / Concurrency
- Events：Flow、Task、Resource 事件
- Profiles：API Key 存储
- Email / Slack Notifications

## 十、安全

- API Token / Service Account
- Work Pool RBAC（Cloud）
- Secret Manager Block：`AWS Secrets / Vault / Env / K8s Secret`

## 十一、最佳实践

- **每个 Flow 单一职责**
- **Task 命名**：业务含义清楚
- **使用 cache**：减少重算
- **result**：大对象走对象存储
- **serve vs worker**：临时调试用 serve，生产用 worker + deployment
- **监控**：关键 Flow 加通知、metrics
- **类型注解**：用 Pydantic `BaseModel` 作为参数
