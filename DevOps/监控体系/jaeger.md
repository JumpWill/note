# Jaeger

CNCF 毕业的分布式追踪系统，源自 Uber，已与 OpenTelemetry 生态深度融合。

## 一、定位

- 分布式 Trace 收集、存储、查询
- 多语言 Client / Library（与 OpenTelemetry 统一）
- UI 可视化调用链、服务依赖
- 后端存储可插拔：Cassandra / Elasticsearch / Kafka / Badger / Memory

## 二、架构

```text
Client / Agent
   │
   ▼
Collector
   │
   ▼
Storage (Cassandra / ES / Kafka / Tempo / ...)
   │
   ▼
Query
   │
   ▼
UI / API
```

### 1. 单体模式

```text
all-in-one binary：UI + Query + Collector + Badger + Memory
```

适合快速试用 / Demo / 开发。

### 2. 生产模式

```text
Collector（无状态）
   │
   ├──► Kafka（异步）──► Ingester ──► Cassandra / ES
   │
Query（无状态）──► ES / Cassandra
```

## 三、组件

| 组件 | 含义 |
| ---- | ---- |
| **Agent** | DaemonSet 部署在节点上，UDP 接收并转发 |
| **Collector** | 接收 / 处理 / 存储 / 转发 |
| **Storage** | Cassandra / Elasticsearch / Kafka + Ingester / Badger |
| **Query** | UI 后端查询服务 |
| **UI** | Jaeger Frontend（搜索 / 调用链 / 依赖） |

## 四、数据模型

### 1. Span / Trace

```text
Trace
   └─ Span Root
        └─ Span Child
             └─ Span Child
```

字段：

- `traceID` / `spanID`
- `operationName`
- `startTime` / `duration`
- `tags`（key/value）
- `logs`（带时间戳的事件）
- `references`（parent）

### 2. Process / Tags

Process 元数据：

- `service.name`
- `host`
- `process.tags`

## 五、采样

客户端多语言 SDK：

- `ConstSampler`
- `ProbabilisticSampler(probability)`
- `RateLimitingSampler(perSecond)`
- `AdaptiveSampler`（基于父决定子）

服务端：在 Collector 配置 sampling strategy：

```yaml
sampling:
  strategies:
    - type: probabilistic
      param: 0.1
```

## 六、Collector 配置

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
  zipkin:
    endpoint: 0.0.0.0:9411
  jaeger:
    protocols:
      grpc:
        endpoint: 0.0.0.0:14250
      thrift_http:
        endpoint: 0.0.0.0:14268

processors:
  batch: {}
  memory_limiter:
    limit_mib: 512

exporters:
  jaeger:
    endpoint: jaeger-collector:14250
  jaeger_thrift_http:
    endpoint: http://jaeger-collector:14268/api/traces
  elasticsearch:
    endpoint: http://es:9200
    index: jaeger
  kafka:
    topic: traces
    brokers: kafka:9092

service:
  pipelines:
    traces:
      receivers: [otlp, zipkin, jaeger]
      processors: [memory_limiter, batch]
      exporters: [kafka]
```

注意：实际生产中 collector 自身与 jaeger collector 是两件事。Jaeger vendor 通过 OTLP 输出到 Jaeger Collector 也可。

## 七、SDK 集成

### 1. OpenTelemetry（一线推荐）

```go
import "go.opentelemetry.io/otel"
import "go.opentelemetry.io/otel/exporters/jaeger"

exp, _ := jaeger.New(jaeger.WithCollectorEndpoint(
    jaeger.WithEndpoint("http://jaeger:14268/api/traces")))
provider := sdktrace.NewTracerProvider(
    sdktrace.WithBatcher(exp),
    sdktrace.WithResource(resource),
)
otel.SetTracerProvider(provider)
```

（也支持 OTLP exporter 直达 Jaeger）

### 2. 老 SDK

```java
io.opentracing.Tracer tracer = new io.jaegertracing.Configuration("order-svc")
  .withSampler(...) ... .getTracer();
```

## 八、依赖 UI 与 Tracing UI

### 1. Trace 搜索

- Service / Operation / Tags / Lookback
- minDuration / maxDuration
- 错误 / 慢 trace 过滤

### 2. Trace 详情

```text
root span (300ms)
├── auth (10ms)
├── db.find_order (15ms)
└── call payment.svc (200ms)
        ├── gateway (180ms)
        └── retry (5ms)
```

### 3. Service Map

- 服务依赖图
- 错误率 / RPS 概览

### 4. Span colors

按 service / error 高亮。

## 九、采样策略深入

### 1. Adaptive (Server-side)

```yaml
sampling:
  strategies:
    - type: adaptive
      param:
        maxTracesPerSecond: 10
        expectedNewTracesPerSecond: 1
```

- 默认 v1.27+
- 基于 LinkerD / Envoy 比例，保证采到错误率高的 trace

### 2. Tail Sampling

OTel Collector：Jaeger collector 在 v1.33+ 支持 tail sampling：

```yaml
processors:
  jaegerremotesampler:
    strategy:
      type: ratelimiting
      param: 5
```

## 十、Capacity & Storage

- Cassandra：默认存储 + 受 query 速度约束
- ES：分布式检索
- Kafka：用于异步批量
- Badger：单机 / 试用

## 十一、K8s 部署

Helm Chart：

```bash
helm repo add jaegertracing https://jaegertracing.github.io/helm-charts
helm install jaeger jaegertracing/jaeger --set storage.type=elasticsearch
```

Storage 选型：

- `cassandra`
- `elasticsearch`
- `kafka` + `kafka-ingester`
- `badger` (单实例)
- 自 v1.35 + 集成 OTEL 协议输入，后端可独立

## 十二、Jager 与 OpenTelemetry Collector

现代部署：

```text
App / SDK (OTel)
   │
   ▼ OTLP
OpenTelemetry Collector (Gateway)
   │
   ▼ OTLP 或 jaeger 格式
Jaeger Collector
   │
   ▼
ES / Cassandra
```

或直接 OTLP → Jaeger Collector（v1.32+ 支持）。

## 十三、Jager 与 Tempo / SkyWalking

| 维度 | Jaeger | Tempo | SkyWalking |
| ---- | ------ | ----- | ---------- |
| 主要语言生态 | 多语言 | Grafana 系 | Java 强 |
| 后端 | Cassandra / ES | 对象存储 | ES / H2 / MySQL / TiDB |
| 采样 | 客户端 + 服务端 | 全量 + head sample | 多种 |
| UI | 单 Trace 强 | TraceQL 强 | ServiceMap 强 |
| 扩展 | 多语言 | Grafana 全家桶 | Metric + Trace + Log |

## 十四、最佳实践

- **统一 OpenTelemetry** 优先：Jaeger 作为 Tracing Backend
- **服务命名**：service.name 强约束
- **资源属性**：标准 Resource Attributes
- **采样率**：全量采样的成本与价值权衡
- **错误加 tag**：如 `error.kind`、`exception.type`
- **慢 trace 标记**：`http.status_code=5xx`
- **关联到日志**：traceID 写入日志
- **Service Map**：定期导出供业务洞察
- **Tail sampling**：高质量错误 / 慢 trace 必采

## 十五、TraceQL / UI 升级

Grafana TraceQL / Jaeger UI 都在迭代，Grafana Explore 中整合能力上升：
