# OpenTelemetry Traces(追踪)

OpenTelemetry Traces 用于追踪**分布式请求**在多个服务间的完整调用路径,回答"请求经过了哪些环节、哪里慢、哪里出错"。

---

## 1. 基本概念

### 1.1 三大支柱

|支柱|回答什么问题|典型工具|
|---|---|---|
|**Metrics**|系统**整体趋势**怎么样?CPU 多高?QPS 多大?|Prometheus、Grafana|
|**Logs**|**具体发生了什么**?异常堆栈、调试信息|ELK、Loki|
|**Traces**|请求**经过了哪些环节**,哪里慢?|Jaeger、Zipkin、Tempo|

### 1.2 Trace 的关键概念

|术语|含义|
|---|---|
|**Trace**|一次完整请求的调用链(由多个 Span 组成)|
|**Span**|一个独立工作单元(方法调用、RPC、DB 查询)|
|**SpanContext**|跨进程传递的 span 标识(trace_id + span_id)|
|**TraceId**|全局 trace 唯一 ID(128 bit)|
|**SpanId**|当前 span 唯一 ID(64 bit)|
|**ParentSpanId**|父 span ID(根 span 没有)|
|**Tracer**|创建 Span 的工具|
|**TracerProvider**|全局 provider,管理 Tracer 生命周期|
|**Operation Name**|Span 的操作名(如 `http.GET /api/users`)|
|**SpanKind**|Span 类型(INTERNAL/SERVER/CLIENT/PRODUCER/CONSUMER)|
|**Attribute**|键值对标签(可索引、可搜索)|
|**Event**|Span 内部的时间戳事件(异常堆栈、状态变更)|
|**Status**|Span 状态(Unset/Ok/Error)|
|**Link**|关联到其他 trace(异步批处理场景)|
|**Resource**|资源属性(service.name 等)|
|**Sampling**|采样策略,控制 trace 记录比例|
|**Context Propagation**|跨进程传播 trace context|

### 1.3 SpanKind 类型

|Kind|含义|场景|
|---|---|---|
|**INTERNAL**|内部操作|业务方法调用|
|**SERVER**|服务端处理请求|HTTP/gRPC handler|
|**CLIENT**|客户端发起请求|HTTP client、DB driver|
|**PRODUCER**|消息生产|Kafka publish|
|**CONSUMER**|消息消费|Kafka subscribe|

---

## 2. 数据模型

### 2.1 Trace 结构

```text
Trace (traceID = abc123)
│
├── Span A: HTTP POST /api/order
│   ├── SpanKind: SERVER
│   ├── Duration: 150ms
│   ├── Attributes: {http.method=POST, http.status_code=200}
│   ├── Events: [{time=10ms, "validation passed"}, {time=20ms, "saved to DB"}]
│   └── Children:
│       ├── Span B: SELECT * FROM products
│       │   ├── SpanKind: CLIENT
│       │   └── Duration: 30ms
│       ├── Span C: HTTP POST /payment/charge
│       │   ├── SpanKind: CLIENT
│       │   └── Duration: 80ms
│       └── Span D: kafka publish order.created
│           ├── SpanKind: PRODUCER
│           └── Duration: 10ms
```

### 2.2 数据流

```text
应用代码 → Tracer.StartSpan() → Span → Context(注入 header)
                                              ↓
                                  Exporter(OTLP) → OTel Collector → 后端
                                              ↓
                                  (Jaeger / Tempo / Zipkin)
```

### 2.3 Context Propagation(跨进程传播)

|协议|格式|Header 名|
|---|---|---|
|HTTP|`key1=value1,key2=value2`|`traceparent` / `tracestate`(W3C 标准)|
|gRPC|Metadata 字段|同 HTTP|
|Kafka|Header|同 HTTP|
|RabbitMQ|Headers|同 HTTP|

W3C `traceparent` 格式:

```text
traceparent: 00-{trace_id(32)}-{span_id(16)}-{flags(2)}
例:00-abc123def456-789xyz01-01
```

> v1.0+ OTel 统一使用 W3C Trace Context,旧的 `uber-trace-id`(Jaeger)仍兼容。

---

## 3. Go 语言 OpenTelemetry Traces 完整示例

### 3.1 安装依赖

```bash
go get go.opentelemetry.io/otel \
       go.opentelemetry.io/otel/sdk \
       go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc \
       go.opentelemetry.io/otel/trace
```

### 3.2 初始化

```go
package main

import (
    "context"

    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
    "go.opentelemetry.io/otel/propagation"
    "go.opentelemetry.io/otel/sdk/resource"
    sdktrace "go.opentelemetry.io/otel/sdk/trace"
    semconv "go.opentelemetry.io/otel/semconv/v1.21.0"
)

func setupTracing(ctx context.Context) (*sdktrace.TracerProvider, error) {
    // 1. Resource
    res, _ := resource.New(ctx,
        resource.WithAttributes(
            semconv.ServiceName("my-service"),
            semconv.ServiceVersion("1.0.0"),
        ),
    )

    // 2. Exporter
    exporter, err := otlptracegrpc.New(ctx,
        otlptracegrpc.WithEndpoint("otel-collector:4317"),
        otlptracegrpc.WithInsecure(),
    )
    if err != nil {
        return nil, err
    }

    // 3. TracerProvider
    tp := sdktrace.NewTracerProvider(
        sdktrace.WithBatcher(exporter),
        sdktrace.WithResource(res),
        sdktrace.WithSampler(sdktrace.AlwaysSample()),  // 全采样
    )
    otel.SetTracerProvider(tp)

    // 4. 设置全局 Propagator(W3C TraceContext)
    otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(
        propagation.TraceContext{},
        propagation.Baggage{},
    ))
    return tp, nil
}
```

### 3.3 业务使用

```go
import (
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/attribute"
    "go.opentelemetry.io/otel/codes"
    "go.opentelemetry.io/otel/trace"
)

func processOrder(ctx context.Context, orderID string) error {
    tracer := otel.Tracer("my-service/order")
    ctx, span := tracer.Start(ctx, "processOrder",
        trace.WithSpanKind(trace.SpanKindInternal),
        trace.WithAttributes(
            attribute.String("order.id", orderID),
        ),
    )
    defer span.End()

    // 调用子操作
    if err := validateOrder(ctx, orderID); err != nil {
        span.RecordException(err)                   // 记录异常
        span.SetStatus(codes.Error, "validate failed")
        return err
    }

    if err := chargePayment(ctx, orderID); err != nil {
        span.RecordException(err)
        span.SetStatus(codes.Error, "charge failed")
        return err
    }

    // 添加事件
    span.AddEvent("order completed", trace.WithAttributes(
        attribute.String("order.status", "success"),
    ))
    return nil
}

func validateOrder(ctx context.Context, orderID string) error {
    tracer := otel.Tracer("my-service/order")
    _, span := tracer.Start(ctx, "validateOrder",
        trace.WithSpanKind(trace.SpanKindInternal),
    )
    defer span.End()

    // 业务逻辑...
    return nil
}
```

### 3.4 跨进程传播(以 HTTP client 为例)

```go
import (
    "net/http"
    "go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"
)

// 自动埋点:自动提取请求头中的 traceparent
client := &http.Client{
    Transport: otelhttp.NewTransport(http.DefaultTransport),
}

req, _ := http.NewRequestWithContext(ctx, "GET", "http://downstream/api", nil)

// 注入当前 trace context 到请求头
otel.GetTextMapPropagator().Inject(ctx, propagation.HeaderCarrier(req.Header))

resp, err := client.Do(req)
```

### 3.5 Gin 服务端自动埋点

```go
import (
    "github.com/gin-gonic/gin"
    "go.opentelemetry.io/contrib/instrumentation/github.com/gin-gonic/gin/otelgin"
)

func main() {
    // ... 初始化 tracer 略

    r := gin.Default()
    r.Use(otelgin.Middleware("my-service"))   // 自动提取 + 创建 server span

    r.GET("/api/users/:id", func(c *gin.Context) {
        // c.Request.Context() 已经包含 trace context
        // 当前 span 会被设为 SERVER kind
        user := getUser(c.Request.Context(), c.Param("id"))
        c.JSON(200, user)
    })

    r.Run(":8080")
}
```

---

## 4. Python 语言示例

### 4.1 安装依赖

```bash
pip install opentelemetry-api \
            opentelemetry-sdk \
            opentelemetry-exporter-otlp-proto-grpc \
            opentelemetry-instrumentation-flask
```

### 4.2 完整代码

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.trace import Status, StatusCode

# 1. 设置 TracerProvider
resource = Resource.create({
    ResourceAttributes.SERVICE_NAME: "my-python-service",
})
provider = TracerProvider(resource=resource)
processor = BatchSpanProcessor(
    OTLPSpanExporter(endpoint="otel-collector:4317", insecure=True)
)
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

# 2. 获取 Tracer
tracer = trace.get_tracer(__name__)

# 3. 创建 Span
with tracer.start_as_current_span("process-order") as span:
    span.set_attribute("order.id", "o-12345")

    # 添加事件
    span.add_event("validation passed", {"items": 5})

    # 子 Span
    with tracer.start_as_current_span("validate-order") as child:
        child.set_attribute("items.count", 5)
        # 业务逻辑...

    # 异常处理
    try:
        with tracer.start_as_current_span("charge-payment") as payment_span:
            payment_span.set_attribute("payment.amount", 9999)
            # charge_payment()
    except Exception as e:
        span.record_exception(e)
        span.set_status(Status(StatusCode.ERROR, str(e)))
```

### 4.3 Flask 框架自动埋点

```python
from flask import Flask
from opentelemetry.instrumentation.flask import FlaskInstrumentor

app = Flask(__name__)
FlaskInstrumentor().instrument_app(app)  # 自动埋点

@app.route("/api/users/<id>")
def get_user(id):
    # 自动有 server span
    return {"id": id, "name": "Alice"}
```

---

## 5. Java 语言示例

### 5.1 Maven 依赖

```xml
<dependencies>
  <dependency>
    <groupId>io.opentelemetry</groupId>
    <artifactId>opentelemetry-api</artifactId>
    <version>1.36.0</version>
  </dependency>
  <dependency>
    <groupId>io.opentelemetry</groupId>
    <artifactId>opentelemetry-sdk</artifactId>
    <version>1.36.0</version>
  </dependency>
  <dependency>
    <groupId>io.opentelemetry</groupId>
    <artifactId>opentelemetry-exporter-otlp</artifactId>
    <version>1.36.0</version>
  </dependency>
</dependencies>
```

### 5.2 完整代码

```java
import io.opentelemetry.api.OpenTelemetry;
import io.opentelemetry.api.common.AttributeKey;
import io.opentelemetry.api.common.Attributes;
import io.opentelemetry.api.trace.Span;
import io.opentelemetry.api.trace.SpanKind;
import io.opentelemetry.api.trace.StatusCode;
import io.opentelemetry.api.trace.Tracer;
import io.opentelemetry.context.Scope;
import io.opentelemetry.exporter.otlp.trace.OtlpGrpcSpanExporter;
import io.opentelemetry.sdk.OpenTelemetrySdk;
import io.opentelemetry.sdk.resources.Resource;
import io.opentelemetry.sdk.trace.SdkTracerProvider;
import io.opentelemetry.sdk.trace.export.BatchSpanProcessor;
import io.opentelemetry.semconv.ResourceAttributes;

public class TraceExample {
    public static void main(String[] args) {
        Resource resource = Resource.getDefault().merge(
            Resource.create(Attributes.of(
                ResourceAttributes.SERVICE_NAME, "my-java-service"
            ))
        );

        OtlpGrpcSpanExporter exporter = OtlpGrpcSpanExporter.builder()
            .setEndpoint("http://otel-collector:4317")
            .build();

        SdkTracerProvider tracerProvider = SdkTracerProvider.builder()
            .addSpanProcessor(BatchSpanProcessor.builder(exporter).build())
            .setResource(resource)
            .build();

        OpenTelemetry sdk = OpenTelemetrySdk.builder()
            .setTracerProvider(tracerProvider)
            .build();

        // 获取 Tracer
        Tracer tracer = sdk.getTracer("my-service/order");

        // 创建 Span
        Span span = tracer.spanBuilder("processOrder")
            .setSpanKind(SpanKind.INTERNAL)
            .setAttribute("order.id", "o-12345")
            .startSpan();

        try (Scope scope = span.makeCurrent()) {
            // 子 Span
            Span child = tracer.spanBuilder("validateOrder")
                .setSpanKind(SpanKind.INTERNAL)
                .startSpan();
            try (Scope cs = child.makeCurrent()) {
                child.setAttribute("items.count", 5);
                // 业务逻辑...
            } finally {
                child.end();
            }

            // 添加事件
            span.addEvent("order completed");
        } catch (Exception e) {
            span.recordException(e);
            span.setStatus(StatusCode.ERROR, e.getMessage());
        } finally {
            span.end();
        }
    }
}
```

---

## 6. 采样(Sampling)

### 6.1 采样策略

|策略|含义|
|---|---|
|**AlwaysSample**|100% 采样(开发环境)|
|**NeverSample**|0% 采样(关闭 trace)|
|**TraceIDRatioBased**|按 trace_id 比例采样(0.1 = 10%)|
|**ParentBased**|跟随父 span 决策(生产推荐)|
|**Remote / Adaptive**|远程集中决策 / 自适应|

### 6.2 Go 采样配置

```go
// 全采样
sdktrace.WithSampler(sdktrace.AlwaysSample())

// 10% 概率采样
sdktrace.WithSampler(sdktrace.TraceIDRatioBased(0.1))

// 父决策优先,无父时 10%
sdktrace.WithSampler(
    sdktrace.ParentBased(sdktrace.TraceIDRatioBased(0.1)),
)
```

### 6.3 Python 采样配置

```python
from opentelemetry.sdk.trace.sampling import (
    TraceIdRatioBased, ParentBased, AlwaysOn
)

# 10% 概率采样
provider = TracerProvider(
    resource=resource,
    sampler=ParentBased(root=TraceIdRatioBased(0.1)),
)
```

---

## 7. 关键术语速查

|术语|含义|
|---|---|
|**Trace**|一次完整请求的调用链|
|**Span**|一个独立工作单元|
|**TraceId**|全局 trace 唯一 ID|
|**SpanId**|当前 span 唯一 ID|
|**ParentSpanId**|父 span ID|
|**SpanKind**|INTERNAL/SERVER/CLIENT/PRODUCER/CONSUMER|
|**Status**|Unset/Ok/Error|
|**Attribute**|键值对标签|
|**Event**|Span 内时间戳事件|
|**Link**|关联到其他 trace|
|**Sampling**|采样策略|
|**Context Propagation**|跨进程传播|
|**W3C TraceContext**|标准协议(traceparent header)|
|**OTLP**|OpenTelemetry 传输协议|
|**Baggage**|全链路透传业务键值|
|**Exemplar**|关联到 trace 样本(metric → trace 跳转)|

---

## 8. 实战建议

1. **统一使用 W3C TraceContext**(不要用老的 B3 / Jaeger 格式)
2. **SpanKind 必须正确**:HTTP handler 用 SERVER,client 调用用 CLIENT
3. **operationName 用语义约定**:`http.GET /api/users` 而不是 `handleRequest`
4. **关键 Span 加 Attribute**:`order.id`、`user.id`(低基数),便于过滤
5. **异常处理用 recordException + setStatus(Error)**
6. **添加 Event 标记关键节点**:`validation passed`、`db query completed`
7. **HTTP/gRPC 框架用自动埋点**:otelgin / otelhttp / FlaskInstrumentor
8. **生产 1-10% 采样**:ParentBased + TraceIDRatioBased(0.1)
9. **尾部采样**:TraceIDRatioBased 太随机,生产推荐 Tail-based Sampling(OTel Collector)
10. **关联日志和指标**:日志带 trace_id,metric 加 exemplar,实现 metric→trace→log 下钻

---

## 9. 速记

- **数据模型**:Trace = N 个 Span(树形),Span = 操作 + Attribute + Event + Status
- **跨进程传播**:W3C `traceparent` header,自动注入和提取
- **SpanKind**:INTERNAL / SERVER / CLIENT / PRODUCER / CONSUMER
- **采样**:ParentBased + TraceIDRatioBased(0.1) 是生产推荐
- **三种语言都支持**:Go / Python / Java,API 设计一致
- **OTel 统一协议**:OTLP 跨语言、跨厂商
- **生产架构**:App + OTel SDK → OTel Collector(采样/路由) → Jaeger / Tempo / Zipkin
