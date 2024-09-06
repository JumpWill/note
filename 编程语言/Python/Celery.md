## 简介

Celery 是一个简单、灵活且可靠的分布式系统，用于处理大量消息，同时为运营提供维护此类系统所需的工具,它是一个专注于实时处理的任务队列，同时还支持任务调度。

### 使用

```python
# worker.py
from celery import Celery

celery = Celery("tasks", broker="redis://127.0.0.1:6379/0", backend="redis://127.0.0.1:6379/0")

@celery.task(max_retries=3)
def add_ai_tools_task(x: int):
    print(x)
# 启动worker
# celery -A worker worker --loglevel=info --concurrency=10

add_ai_tools_task.delay(1)
```

### 并发

#### 多个worker

多个worker实例

#### 单个worker的concurrency=10

```
celery -A worker worker --loglevel=info --concurrency=10
```

#### -P

##### Eventlet

CPU 密集型操作与 Eventlet 不兼容 ---->不推荐

```shell
celery -A proj worker -P eventlet -c 1000
```

##### gevent

异步，类似于Eventlet

```shell
celery -A proj worker -P gevent -c 1000
```

<https://docs.celeryq.dev/en/stable/userguide/concurrency/index.html>
<https://stackoverflow.com/questions/42948547/which-pool-class-should-i-use-prefork-eventlet-or-gevent-in-celery>

### WebUI/Monitor

WebUI:flower
<https://docs.celeryq.dev/en/stable/userguide/monitoring.html>

## 问题

### 内存泄漏

1. limit与quata
2. 使用jemalloc
<https://github.com/celery/celery/issues/4843>
3. 配置子进程的最大数量
<https://docs.celeryq.dev/en/stable/userguide/optimizing.html>
