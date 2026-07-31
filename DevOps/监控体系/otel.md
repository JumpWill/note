# OpenTelemetry (OTel)

CNCF 主导的统一遥测框架。覆盖 metrics / traces / logs，统一 API / SDK / Protocol / Collector，是云原生可观测性的基础。

## 一、定位

- API / SDK 标准：让"一次埋点，多端导出"成为可能
- 协议 OTLP（gRPC / HTTP）
- Collector：vendor-neutral 的中转/处理/转发
- 与已有后端兼容：Prometheus / Jaeger / Zipkin / Tempo / SkyWalking / Loki / Vendor（Datadog / NewRelic）

## 二、组件

```text
┌──────────────────────────────────────┐
│ 应用 / 服务                            │
│   - OTel SDK                          │
│     - TracerProvider                  │
│     - MeterProvider                   │
│     - LoggerProvider                  │
│   - 自动 / 手动埋点                      │
└──────────────┬───────────────────────┘
               │ OTLP (gRPC/HTTP)
               ▼
┌──────────────────────────────────────┐
│ OpenTelemetry Collector               │
│   Receivers (OTLP, Zipkin, Prom...)   │
│   Processors (batch, filter, k8sattr) │
│   Exporters (Jaeger, Prometheus, ...) │
└──────┬───────────────┬───────────────┘
       │               │
       ▼               ▼
   后端 1              后端 2
   (Jaeger)          (Vendor)
```

## 三、OTLP 协议

### 1. 定义

OTLP（OpenTelemetry Protocol）：基于 Protobuf 的协议，覆盖三种 signal：

- `trace` (traces)
- `metric` (metrics)
- `log` (logs)

### 2. 传输

- gRPC（默认）：4317
- HTTP：4318（protobuf / JSON）
- 端口可改

### 3. 资源 / Span / Metric

```text
Resource   ─ 全局描述（service.name / host / k8s.pod.name）
Instrumentation Library
   └── Tracer
        └── Span (TraceID, ParentSpanID, ...)
        └── SpanEvent
   └── Meter
        └── Counter / Gauge / Histogram
   └── Logger
        └── LogRecord（带 trace context）
```

## 四、Collector

### 1. 组件

| 组件 | 作用 |
| ---- | ---- |
| **Receiver** | 接收遥测数据 |
| **Processor** | 处理 / 转换 / 富化 |
| **Exporter** | 发送到后端 |
| **Extension** | 健康 / pprof / zpages |
| **Connector** | 把一种 signal 转另一 signal |

### 2. 配置

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318
  prometheus:
    config:
      scrape_configs: [...]
  jaeger:
    protocols:
      grpc:
        endpoint: 0.0.0.0:14250

processors:
  batch: {}
  memory_limiter:
    limit_mib: 512
  attributes:
    actions:
      - key: env
        value: prod
        action: insert
  k8sattributes:
    extract:
      metadata:
        - k8s.pod.name
        - k8s.namespace.name

exporters:
  otlp/jaeger:
    endpoint: jaeger:4317
    tls:
      insecure: true
  prometheus:
    endpoint: 0.0.0.0:8889
  prometheusremotewrite:
    endpoint: http://cortex:9009/api/v1/push
  loki:
    endpoint: http://loki:3100/loki/api/v1/push

service:
  pipelines:
    traces:
      receivers: [otlp, jaeger]
      processors: [memory_limiter, batch, k8sattributes]
      exporters: [otlp/jaeger, otlp/vendorsaas]
    metrics:
      receivers: [otlp, prometheus]
      processors: [batch]
      exporters: [prometheus, prometheusremotewrite]
    logs:
      receivers: [otlp]
      processors: [batch]
      exporters: [loki]
```

### 3. 部署模式

- **Agent**：每节点一个 sidecar / DaemonSet
- **Gateway**：中央集群，分离采集与出口
- **混合**

K8s 上常用 DaemonSet + Gateway tier。

## 五、SDK 集成

### 1. Java

```java
Resource resource = Resource.getDefault().merge(
    Resource.create(Attributes.of(
        ResourceAttributes.SERVICE_NAME, "billing",
        ResourceAttributes.SERVICE_VERSION, "1.0.0")));

SdkTracerProvider tracerProvider = SdkTracerProvider.builder()
    .addSpanProcessor(SimpleSpanProcessor.create(jaegerExporter))
    .setResource(resource)
    .build();
```

- 主流 Java 框架集成：Spring Boot / Quarkus / Helidon
- 自动埋点：JDBC / Servlet / R2DBC / Kafka client / gRPC

### 2. Go

```go
import "go.opentelemetry.io/otel"
tracer := otel.Tracer("myapp")
ctx, span := tracer.Start(ctx, "process_order")
defer span.End()
```

自动埋点：net/http / database/sql / gin / grpc / sarama

### 3. Python

```python
from opentelemetry import trace
tracer = trace.get_tracer(__name__)
with tracer.start_as_current_span("process_order"):
    ...
```

自动：requests / django / flask / sqlalchemy / celery / grpc

### 4. Node.js / Browser

```js
const { trace } = require('@opentelemetry/api');
const tracer = trace.getTracer('web');
tracer.startActiveSpan('click', span => {...; span.end()});
```

## 六、Context Propagation

```http
traceparent: 00-{traceId}-{spanId}-{flags}
tracestate: ...
```

W3C TraceContext 是事实标准。Baggage 用于跨服务上下文传递。

## 七、自动埋点 (Zero-code) 模式

语言相关注入：

### Java

```bash
-javaagent:opentelemetry-javaagent.jar \
  -Dotel.service.name=app \
  -Dotel.exporter.otlp.endpoint=collector:4317 \
  -jar app.jar
```

### Python

```bash
opentelemetry-instrument <script.py>
```

## 八、Sampling

| 模式 | 含义 |
| ---- | ---- |
| **AlwaysOn / AlwaysOff** | 全部 / 不采 |
| **Probabilistic** | 概率 |
| **Rate Limiting** | 每秒 N 条 |
| **Tail-based** | 全量采集存储，按错误 / 慢决定上报 |
| **ParentBased** | 跟随父 span |

```yaml
processors:
  tail_sampling:
    decision_wait: 10s
    num_traces: 50000
    policies:
      - name: errors
        type: status_code
      - name: latency
        type: latency
        latency: 200ms
      - name: probabilistic
        type: probabilistic
        probabilistic: { sampling_percentage: 10 }
```

## 九、Metrics 语义约定

OpenTelemetry 强调语义约定（Semantic Conventions）：

| 指标 | 单位 | 类型 |
| ---- | ---- | ---- |
| `http.server.duration` | s | Histogram |
| `http.client.duration` | s | Histogram |
| `db.client.operation.duration` | s | Histogram |
| `process.runtime.cpu.utilization` | ratio | Gauge |

K8s 属性约定：

- `service.name`
- `k8s.namespace.name`
- `k8s.pod.name`
- `k8s.container.name`
- `k8s.deployment.name`

## 十、Collector + Prometheus 无缝

- OTel Collector 作为 scrape target
- Application 通过 OTLP 输出 Prometheus 格式
- 多套后端共用

## 十一、性能与可靠性

- 内存限制：`memory_limiter` processor
- 队列：`sending_queue`
- 重试：`retry_on_failure`
- gRPC 压缩：默认 gzip
- TLS：`tls` 设置
- 速率控制：`rate_limiter`

## 十二、Collector Connectors

新特性，把一种信号在流水线之间转换：

```yaml
connectors:
  spanmetrics:
    metrics:
      - name: tracestate.latency
        dimensions:
          - name: status.code

service:
  pipelines:
    traces/spanmetrics:
      receivers: [otlp]
      exporters: [spanmetrics]
    metrics:
      receivers: [spanmetrics]
      exporters: [prometheus]
```

把 trace 转为 span metrics 接口，给 Prometheus 采集。

## 十三、Logs 与 Traces 的关联

OTel 日志模型：

```json
{
  "Timestamp": "...",
  "SeverityText": "ERROR",
  "TraceId": "...",
  "SpanId": "...",
  "TraceFlags": "01",
  "Body": "..."
}
```

Loki / ES 等支持按 traceID 检索。

## 十四、最佳实践

- **统一 API / SDK**：避免 vendor lock-in
- **生产环境 Collector** 作为 gateway + tail_sampling
- **Resource attributes** 标准化
- **Zero-code**：Java agent 走 javaagent，Python 用 auto-instrumentation
- **服务命名**：service.name 强制标准
- **不要上报 PII** / 高基数 label
- **Semantic Conventions** 跟随版本升级
- **OTLP over gRPC** 优先，比 HTTP/JSON 省字节
