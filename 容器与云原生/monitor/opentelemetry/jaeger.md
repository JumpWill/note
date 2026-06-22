# Jaeger 概念详解

Jaeger 是 Uber 开源的**分布式追踪系统**(Distributed Tracing System),受 OpenTracing 启发,后成为 CNCF 毕业项目。它用于监控和排查微服务架构中的调用链路。

---

## 1. 核心架构总览

```text
应用服务调用链
+----------+     +----------+     +----------+     +----------+
| ServiceA  | --> | ServiceB  | --> | ServiceC  | --> | ServiceD  |
+----------+     +----------+     +----------+     +----------+
     |                |                |                |
     v                v                v                v
+--------------------------------------------------------------+
|                  Client Library (SDK)                       |
|         - 创建 Span   - 设置 Tag/Log   - 批量上报            |
+--------------------------------------------------------------+
                              |
                              v
+--------------------------------------------------------------+
|                         Jaeger                              |
|  +-----------+    +-----------+    +-----------+            |
|  |  Agent    |--> | Collector |--> |  Storage  |            |
|  +-----------+    +-----------+    +-----------+            |
|         (可选)         校验/转换         ES/Cassandra       |
|                              ^                            |
|                              |                            |
|                         +----------+                      |
|                         |  Query   |<----- Jaeger UI      |
|                         +----------+                      |
+--------------------------------------------------------------+
                              |
                              v
                Kafka (可选,削峰填谷)
```

---

## 2. Jaeger 核心组件

### 2.1 Client Libraries(客户端库)

**作用**:在应用代码中**创建 Span、上报 Trace 数据**给 Collector。

|语言|包名|
|---|---|
|Go|`github.com/uber/jaeger-client-go`|
|Java|`io.jaegertracing:jaeger-client`|
|Python|`jaeger-client`|
|Node.js|`jaeger-client`|
|C++|`jaeger-client-cpp`|

**Go 初始化示例**:

```go
import (
    "github.com/uber/jaeger-client-go/config"
)

func InitTracer() (opentracing.Tracer, io.Closer, error) {
    cfg := config.Configuration{
        ServiceName: "my-service",
        Sampler: &config.SamplerConfig{
            Type:  "const",
            Param: 1,                    // 1 = 全采样
        },
        Reporter: &config.ReporterConfig{
            LogSpans:           true,
            BufferFlushInterval: 1 * time.Second,
            LocalAgentHostPort: "jaeger-agent:6831",
        },
    }
    return cfg.NewTracer()
}
```

### 2.2 Jaeger Agent(代理,**可选**)

**作用**:监听 UDP 端口,接收客户端发来的 span,**批量转发给 Collector**。

- 默认 UDP 端口:`6831`(compact Thrift)、`6832`(binary Thrift)
- 部署模型:**Sidecar / DaemonSet**
- **生产可选**:应用也可以直连 Collector,跳过 Agent

```yaml
# Kubernetes 部署
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: jaeger-agent
spec:
  template:
    spec:
      containers:
      - name: agent
        image: jaegertracing/jaeger-agent:1.55
        args:
          - "--reporter.grpc.host-port=jaeger-collector:14250"
          - "--reporter.type=grpc"
```

### 2.3 Jaeger Collector(收集器)

**作用**:接收 Agent(或客户端)发来的 span,做**校验、转换、写入存储**。

- 默认端口:`14250`(gRPC)、`14268`(HTTP)、`9411`(Zipkin 兼容)
- **无状态**,可水平扩展
- 写 Kafka / 写存储(ES/Cassandra)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: jaeger-collector
spec:
  replicas: 5
  template:
    spec:
      containers:
      - name: collector
        image: jaegertracing/jaeger-collector:1.55
        args:
          - "--es.server-urls=http://elasticsearch:9200"
          - "--kafka.brokers=kafka:9092"   # 走 Kafka 异步
          - "--sampling.server-url=http://jaeger-sampling:5778"
```

### 2.4 Storage(存储后端)

**作用**:持久化 span 数据。

|存储|推荐场景|注意事项|
|---|---|---|
|**Elasticsearch**|生产首选|集群运维成本高,但查询强|
|**Cassandra**|大规模写入|写性能好,查询弱|
|**Kafka + 上面任一**|削峰填谷|Collector 先写 Kafka,异步消费入库|
|**内存**|仅测试|重启数据丢失|
|**Badger**|简单部署|单机本地存储,适合 demo|

> 1.55+ 版本官方推荐 ES,默认配置已切换到 ES 存储。

### 2.5 Query(查询服务)

**作用**:提供**查询 API 和 UI**,从存储读 span 数据并展示。

- 默认端口:`16686`(UI)、`16685`(gRPC)、`14269`(HTTP)
- **无状态**,可水平扩展

```bash
# 查 Trace
curl "http://jaeger-query:16686/api/traces/<trace-id>"

# 查服务列表
curl "http://jaeger-query:16686/api/services"

# 查服务下的 operation
curl "http://jaeger-query:16686/api/services/<service>/operations"
```

### 2.6 Jaeger UI(可视化界面)

**作用**:Web UI,可视化 trace 调用链。

- 默认地址:`http://localhost:16686`
- 功能:服务列表、调用链瀑布图、依赖图、tag 过滤、耗时统计

界面五大区域:

1. **Search 面板**:按 service、operation、tag、duration、time range 过滤
2. **Trace 详情**:展示 trace 内所有 span 的瀑布图
3. **Span 详情**:tags、logs、process、references
4. **System Architecture**:服务依赖图(基于历史 trace 推断)
5. **Operations**:单服务的 operation 列表 + 耗时分布

---

## 3. 核心概念:Trace / Span / SpanContext

### 3.1 Trace(调用链)

**定义**:一次完整的请求在分布式系统中所经过的**所有节点和耗时**的集合。

```
Trace ID: abc123
├── Span A: HTTP POST /api/order (150ms)
│   ├── Span B: SELECT * FROM products (30ms)
│   ├── Span C: HTTP POST /payment/charge (80ms)
│   └── Span D: Kafka publish order.created (10ms)
```

### 3.2 Span(跨度)

**定义**:**一个独立的工作单元**,对应一次方法调用、一次 RPC、一次 DB 查询等。

**Span 关键字段**:

|字段|含义|示例|
|---|---|---|
|`traceID`|所属 trace 的全局 ID|`abc123...`|
|`spanID`|当前 span 的 ID|`def456`|
|`operationName`|操作名|`http.GET /api/users`|
|`startTime`|开始时间戳|`2026-06-21T10:00:00Z`|
|`duration`|持续时间(微秒)|`150000`|
|`tags`|索引化键值对,可搜索|`http.status_code=200`,`db.statement=SELECT...`|
|`logs`|时间戳+键值对,记录事件|异常堆栈、状态变更|
|`references`|与其他 span 的关系|ChildOf、FollowsFrom|
|`process`|生成 span 的服务信息|serviceName、host、ip|

### 3.3 SpanContext(Span 上下文)

**定义**:跨进程传递的 span 标识,用于**关联上下游**。

**包含字段**:

|字段|作用|
|---|---|
|`traceID`|全局 trace 标识|
|`spanID`|父 span 标识|
|`parentSpanID`|父 span 标识(在 span 内部)|
|`sampling.priority`|采样优先级(0=丢弃,>0=保留)|
|`baggage`|自定义透传键值对|

**跨进程传播方式**:

|协议|格式|
|---|---|
|HTTP|`uber-trace-id` 头|
|gRPC|Metadata 字段|
|Kafka|Header|
|RabbitMQ|Headers|

**HTTP 传播示例**:

```
# 客户端发送
uber-trace-id: abc123:def456:01:abcdef

# 格式: {traceID}:{spanID}:{parentSpanID}:{flags}
```

### 3.4 Span 之间的关系(References)

|关系|含义|场景|
|---|---|---|
|`ChildOf`|父-子因果关系|HTTP handler 调用下游 RPC|
|`FollowsFrom`|父-子非因果(异步)|消息发布|

```go
// ChildOf 例子
parentSpan := tracer.StartSpan("parent")
childSpan := tracer.StartSpan(
    "child",
    opentracing.ChildOf(parentSpan.Context()),
)
defer childSpan.Finish()
defer parentSpan.Finish()
```

### 3.5 Tags vs Logs vs Baggage

|维度|Tags|Logs|Baggage|
|---|---|---|---|
|数据类型|键值对|时间戳+键值对|键值对|
|索引化|是(可搜索)|否(只展示)|是(全链路透传)|
|跨进程|否|否|是|
|用途|搜索过滤、统计|记录事件、调试|业务上下文透传(用户ID、租户ID)|
|性能影响|中|低|高(全链路携带)|

**示例**:

```go
span.SetTag("http.status_code", 200)
span.SetTag("user.id", "12345")
span.LogFields(
    log.String("event", "soft_error"),
    log.String("type", "cache_miss"),
)
span.SetBaggageItem("tenant_id", "tenant-42")
```

---

## 4. 采样(Sampling)

**作用**:不记录所有 trace,降低存储压力和性能损耗。

### 4.1 采样策略

|策略|含义|
|---|---|
|`const`|全采样 / 全不采样(`param=1`/`param=0`)|
|`probabilistic`|概率采样(`param=0.1` = 10%)|
|`ratelimiting`|速率采样(`param=100` = 每秒 100 条)|
|`remote`|远程采样(从 Collector 拉策略)|
|`adaptive`|自适应采样(根据流量动态调整)|

### 4.2 客户端配置

```go
Sampler: &config.SamplerConfig{
    Type:              "remote",
    Param:             0.5,        // 客户端兜底 50%
    SamplingServerURL: "http://jaeger-collector:5778/sampling",
}
```

### 4.3 远程采样(生产推荐)

**Collector 集中决策采样率**,避免大量客户端各自采样导致漏数据。

```yaml
# jaeger-sampling 服务(在 Collector 中)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: jaeger-sampling
spec:
  template:
    spec:
      containers:
      - name: sampling
        image: jaegertracing/jaeger-collector:1.55
        args:
          - "--sampling.strategies-file=/etc/strategies.json"
        volumeMounts:
        - name: strategies
          mountPath: /etc
      volumes:
      - name: strategies
        configMap:
          name: sampling-strategies
```

```yaml
# sampling-strategies ConfigMap
apiVersion: v1
kind: ConfigMap
metadata:
  name: sampling-strategies
data:
  strategies.json: |
    {
      "service_strategies": [
        {
          "service": "my-service",
          "type": "probabilistic",
          "param": 0.1,
          "operation_strategies": [
            {
              "operation": "GET /healthz",
              "type": "probabilistic",
              "param": 0.001
            }
          ]
        }
      ],
      "default_strategy": {
        "type": "probabilistic",
        "param": 0.01
      }
    }
```

---

## 5. 部署模式

### 5.1 All-in-One(开发环境)

**单二进制包含所有组件**:Agent + Collector + Query + UI + 内存存储。

```bash
docker run -d --name jaeger \
  -p 16686:16686 \
  -p 6831:6831/udp \
  jaegertracing/all-in-one:1.55
```

镜像:`jaegertracing/all-in-one`

### 5.2 生产部署(分布式)

|组件|部署方式|副本数|
|---|---|---|
|Agent|DaemonSet / Sidecar|每节点一个|
|Collector|Deployment|3-10 个|
|Query|Deployment|2-5 个|
|Storage|独立集群(ES)|-|

### 5.3 Streaming(Collector 走 Kafka)

适合**大流量 + 需要削峰**的场景。

```
应用 -> Agent -> Collector (异步写) -> Kafka -> Ingester -> ES
```

### 5.4 与 OpenTelemetry Collector 集成

现代部署推荐用 **OTel Collector 替代 Jaeger Agent**,Jaeger 只保留 Collector/Query/Storage:

```
应用 -> OTel Collector (Agent 模式) -> Jaeger Collector -> ES
```

优势:统一处理 metrics/logs/traces,支持多种 exporter。

---

## 6. 关键术语速查

|术语|含义|
|---|---|
|**Trace**|一次完整请求的调用链|
|**Span**|调用链中的单个操作单元|
|**SpanContext**|跨进程传递的 trace+span 标识|
|**Operation**|Span 的操作名(如 `http.GET /api/users`)|
|**Tag**|Span 的索引化标签,可搜索|
|**Log**|Span 内部的时间戳事件|
|**Baggage**|全链路透传的业务键值|
|**References**|Span 间关系(ChildOf / FollowsFrom)|
|**TraceID**|Trace 全局唯一 ID|
|**SpanID**|Span 唯一 ID|
|**ParentSpanID**|父 Span 的 ID|
|**Sampling**|采样策略,控制 trace 记录比例|
|**Root Span**|调用链的起点 span|
|**Service**|产生 span 的应用服务名|
|**Process**|span 归属的服务进程元信息|

---

## 7. 数据写入流程

```
1. 应用代码调用 tracer.StartSpan("op")
2. tracer 生成 TraceID + SpanID,设置父 Span 引用
3. span 通过 SetTag/Log 附加元数据
4. span.Finish() 后,数据放入 client 缓冲区
5. client 定期批量通过 UDP/HTTP 发给 Agent(或直连 Collector)
6. Agent 转发给 Collector
7. Collector 校验后写入 Kafka(可选)或直接写存储
8. Kafka consumer 写入 ES
9. 用户通过 UI/Query 查询 trace
```

---

## 8. 性能与运维

### 8.1 客户端

- **batch 发送**:默认 1000 spans/batch,5s flush
- **采样**:生产环境 1-10% 即可
- **本地缓冲**:失败时 buffer 不丢失,但需关注内存

### 8.2 Collector

- **队列大小**:默认 1000,大流量调到 5000+
- **worker 数**:默认 50,根据 CPU 调整
- **写 Kafka + 异步消费**:抗流量峰值

### 8.3 存储(ES)

- **索引模板**:`jaeger-*`,按日期分索引
- **保留周期**:生产 7-14 天,日志型索引可压缩
- **冷热分层**:热数据 SSD,冷数据 HDD

### 8.4 容量估算

|流量|QPS|采样率|日 span 数|存储估算(15天)|
|---|---|---|---|---|
|小|100|10%|8.6亿|~500GB|
|中|1000|5%|43亿|~2.5TB|
|大|10000|1%|86亿|~5TB|

> 单 span 平均 ~500 bytes 文本,压缩后 ~100 bytes。

---

## 9. 实战建议

1. **生产用 ES 存储**,不要用 Cassandra
2. **大流量走 Kafka 削峰**,避免 Collector 成为瓶颈
3. **采样率 1-10%**,健康检查接口单独配置更低
4. **远程采样**:统一策略,避免漏数据
5. **业务透传 baggage**(user_id、tenant_id)便于排查
6. **结合 OpenTelemetry**:统一 metrics/traces/logs
7. **TraceID 关联日志**:日志里带 trace_id 字段,排查时直接跳转
8. **告警**:Trace 错误率、慢调用比例单独监控
9. **保留周期权衡**:业务合规 vs 存储成本
10. **多集群部署**:用 jaeger_query 聚合,storage 用跨集群 ES

---

## 10. 速记

- **核心组件**:Client → Agent → Collector → Storage ← Query/UI
- **数据模型**:Trace = N 个 Span(树形),Span = 操作+tags+logs
- **跨进程传播**:SpanContext 注入 HTTP header / gRPC metadata
- **采样**:远程采样是生产标配
- **存储**:ES > Cassandra > Kafka + 上面任一
- **现代演进**:用 OpenTelemetry Collector 替代 Jaeger Agent
