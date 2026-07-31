# Grafana Tempo

Grafana Labs 开源的分布式追踪后端，专为低成本、高可扩展、与 Grafana / Loki / Prometheus 深度集成设计。

## 一、定位

- 分布式追踪的存储和查询服务
- 不对 trace 内容建索引（默认）→ 极致低成本
- 与 Grafana / Loki / Prometheus 配套
- 与 Pyroscope 衔接：trace + profile
- OpenTelemetry 协议 + Jaeger / Zipkin 输入

## 二、架构

```text
Receivers（Jaeger / Zipkin / OTLP）
   │
   ▼
Distributor（多副本无状态，写入时 hash）
   │
   ├──► local trace ingester（memory ring）
   │
   └──► Object Storage backend
        (S3 / GCS / Azure Blob / MinIO)

   Compactor（后台清理）
   Querier（无状态，处理查询）
   Query Frontend（缓存 / 分片 / traceQL）

Query ──► Grafana (TraceQL / Trace 查询)
```

## 三、核心概念

| 概念 | 含义 |
| ---- | ---- |
| **Trace** | 一次调用链 |
| **TraceID** | 全局唯一 ID |
| **Distributor** | 接收 trace 数据 |
| **Ingester** | 写入到对象存储 |
| **Querier** | 读取 trace |
| **Compactor** | 合并 / 清理 |
| **Search** | 全文搜索（可选） |
| **TraceQL** | 查询语言 |

## 四、采样策略

Tempo 不做采样决策，依赖前端：

- **Head Sampling**：客户端 SDK 决定
- **Tail Sampling**：OTel Collector tail_sampling 后送到 Tempo
- **Adaptive**：通过 mesh / linkerd / envoy 配置

## 五、存储后端

| Backend | 适用 |
| ------- | ---- |
| **S3** | 主推（带 GCS / Azure Blob 同样支持） |
| **GCS** | Google Cloud |
| **Azure Blob** | Azure |
| **MinIO** | 自建 / 私有 |
| **local** | 试用 |
| **Cassandra** | 实验性 |

每个 block 默认 15–30 MB，单 trace 跨多个 block。TraceQL 检索时合并。

## 六、配置

### 1. 单体（开发）

```yaml
server:
  http_listen_port: 3200

distributor:
  receivers:
    jaeger:
      protocols:
        grpc:
          endpoint: 0.0.0.0:14250
        thrift_http:
          endpoint: 0.0.0.0:14268
    zipkin:
      endpoint: 0.0.0.0:9411
    otlp:
      protocols:
        grpc:
          endpoint: 0.0.0.0:4317

ingester:
  trace_idle_period: 10s
  max_block_duration: 30m

compactor:
  compaction:
    block_retention: 48h

storage:
  trace:
    backend: s3
    s3:
      bucket: tempo-traces
      endpoint: minio:9000
      access_key: ...
      secret_key: ...
      insecure: true

search_enabled: false   # 启用需要 search 外部索引
```

### 2. 微服务（生产）

```yaml
# Distributor
distributor:
  ring:
    kvstore:
      store: memberlist

# Ingester
ingester:
  lifecycler:
    ring:
      kvstore:
        store: memberlist
      replication_factor: 3

# Querier / Query Frontend
query_frontend:
  search:
    max_duration: 5m
  trace_by_id:
    max_duration: 5m
```

通常使用 HashiCorp Memberlist 进行 Gossip。

## 七、TraceQL（Tempo 查询语言）

```text
{ resource.service.name = "order-svc" && resource.kubernetes.namespace.name = "prod" }
{ span.http.status_code = 500 }
{ span.http.status_code = 500 && duration > 1s }
{ span.db.system = "mysql" && span.kind = "client" }
{ span.http.url = "/api/orders" }
```

- 基于结构化标签
- 支持算术、嵌套、聚合

## 八、与 Grafana 集成

### 1. 数据源

```yaml
type: tempo
url: http://tempo:3200
```

### 2. TraceID 跳转

Grafana:
- traceId derived 字段
- 支持 Loki → Tempo 跳转（标签）
- Prometheus exemplar：metric 上跳到 trace

### 3. Loki 跳转 Tempo

```yaml
# Grafana Loki datasource
derivedFields:
  - name: TraceID
    matcherRegex: '"trace_id":"(\w+)"'
    url: '$${__value.raw}/trace/$${__value.raw}'
    urlLabel: 'Trace'
    type: string
```

### 4. Service Map（节点图）

Grafana NodeGraph Panel：展示 trace 树与服务依赖。

## 九、Search 模式

Tempo 默认不开 search（极致便宜），开启需要：

```yaml
search_enabled: true

search:
  results:
    max_result_limit: 100
```

可通过 Elasticsearch / Loki 做 trace metadata 索引，但通常用 traceByID / ServiceGraph / Exemplar 即可。

### 1. 集成 Loki 作为 index

```yaml
search:
  external_backend:
    type: loki
    address: http://loki:3100
```

写一个 microservice 用于 trace 元数据存储到 Loki。

## 十、可视化

### 1. Trace 详情

Grafana Drilldown：完整 span 树、tags、process。

### 2. Trace → Profile 跳转

Pyroscope 中配置 exemplars，可在 trace 中跳转到 flamegraph。

### 3. 链路图

NodeGraph 自动构建跨服务 trace。

## 十一、Span Metrics

OTel Collector Connector：把 traces 转为 metrics：

```yaml
exporters:
  spanmetrics:
    metrics_flush_interval: 30s
    dimensions:
      - service.name
      - http.method
service:
  pipelines:
    traces/spanmetrics:
      receivers: [otlp]
      exporters: [spanmetrics, otlp/tempo]
    metrics:
      receivers: [spanmetrics]
      exporters: [prometheus]
```

在 Grafana 中创建基于 span 的 metrics（无需事先埋）。

## 十二、Tempo 与 Jaeger

| 维度 | Jaeger | Tempo |
| ---- | ------ | ----- |
| 索引 | Inverted（service/operation/tags） | 默认无索引 |
| 成本 | 中等存储 | 极低 |
| 查询 | 走 client SDK 与 span tags | traceID 优先 |
| 适合 | 跨服务拓扑 / 错误分布 | Grafana 全家桶 |

## 十三、K8s 部署

Helm chart：

```bash
helm install tempo grafana/tempo
```

Tempo Operator（K8s 原生）：

```yaml
apiVersion: tempo.grafana.com/v1alpha1
kind: TempoStack
metadata:
  name: tempo
spec:
  storage:
    trace:
      backend: s3
      s3:
        endpoint: minio:9000
        bucket: tempo
```

v2（tempo-operator）非常轻量。

## 十四、Tempo 与 Pyroscope

Grafana Phlare 是 Pyroscope 后续产品。

```text
Tempo trace ──span────► Pyroscope profile
```

- 应用同时上报 trace 和 profile
- 同一时间窗口相互跳转
- 用 `pyscope_flamegraph_link` 跳转

## 十五、性能调优

- `ingester.max_block_duration`：影响落盘频率
- `compactor.compaction.block_retention`：保留时长
- 调小 block 减小爆炸
- `query_frontend.cache`：缓存查询

## 十六、典型用法

### 1. Jaeger UI + Tempo 后端

不再有 Jaeger UI 需求时，把 Jaeger backend 替换为 Tempo。

### 2. Grafana Cloud

- Metrics → Prometheus / Mimir
- Logs → Loki
- Traces → Tempo
- 全栈 All-in-One

### 3. Pipeline

```text
SDK OTLP ► OTel Collector
   │
   ├── tail_sampling_processor
   │
   ├── exporter OTLP/Tempo (通过 OTLP)
   │
   ├── exporter Prometheus / spanmetrics
   │
   ▼
Tempo + Prometheus
   │
   ▼
Grafana
```

## 十七、最佳实践

- **tracing 客户端 + OTLP**：OTLP 优先于 Jaeger 老协议
- **Tail Sampling**：减少存储压力
- **trace ID 写在日志与 metric exemplars**：可关联
- **保留期**：30/45/90 天按需
- **对象存储**：生命周期 + 冷分层
- **memberlist**：Gossip 同步自动发现
- **数据量**：开启 search 时小 KV / ES / Loki
