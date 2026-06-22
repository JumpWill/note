# OpenTelemetry Logs(日志)

OpenTelemetry Logs 提供对应用日志的**结构化采集**和**关联到 Trace** 的能力,是 APM "可观测性三大支柱"之一。

---

## 1. 基本概念

### 1.1 三大支柱

|支柱|回答什么问题|典型工具|
|---|---|---|
|**Metrics**|系统**整体趋势**怎么样?CPU 多高?QPS 多大?|Prometheus、Grafana|
|**Logs**|**具体发生了什么**?异常堆栈、调试信息|ELK、Loki|
|**Traces**|请求**经过了哪些环节**,哪里慢?|Jaeger、Zipkin|

### 1.2 Log 的关键概念

|术语|含义|
|---|---|
|**Log Record**|一条日志记录(原子单元)|
|**Logger**|创建 Log Record 的工具|
|**LoggerProvider**|全局 provider,管理 Logger 生命周期|
|**Log Record Body**|日志主体内容(string / 结构化数据)|
|**Severity**|严重等级(TRACE/DEBUG/INFO/WARN/ERROR/FATAL)|
|**Attribute**|键值对(标签),用于过滤和搜索|
|**Resource**|资源属性(service.name 等)|
|**Trace Context**|关联到 Trace 的 trace_id / span_id|
|**Event**|嵌入到 Span 中的事件日志(API 关联)|
|**Log Appender**|把现有日志框架(log4j/zap/logrus)对接 OTel|

### 1.3 Severity 等级

|等级|数值|用途|
|---|---|---|
|**TRACE**|1|最细粒度,调试级别|
|**DEBUG**|5|调试信息|
|**INFO**|9|关键业务事件|
|**WARN**|13|警告(可恢复)|
|**ERROR**|17|错误(需要关注)|
|**FATAL**|21|致命错误(系统级)|

---

## 2. 数据模型

### 2.1 Log Record 结构

```text
LogRecord
├── Timestamp        (时间戳)
├── ObservedTimestamp(采集时间)
├── TraceId          (关联 trace)
├── SpanId           (关联 span)
├── Severity         (INFO/WARN/ERROR)
├── SeverityText     ("INFO" / "WARN" / ...)
├── Body             (主体内容)
├── Resource         (服务身份)
│   ├── service.name
│   ├── service.version
│   └── ...
├── Attributes       (键值对标签)
│   ├── http.method
│   ├── user.id
│   └── ...
└── InstrumentationScope (库标识)
```

### 2.2 数据流

```text
应用日志 → Logger → LoggerProvider → Processor → Exporter → 后端
                                              (Filter/Batch)
```

---

## 3. Go 语言 OpenTelemetry Logs 完整示例

### 3.1 安装依赖

```bash
go get go.opentelemetry.io/otel \
       go.opentelemetry.io/otel/sdk \
       go.opentelemetry.io/otel/exporters/otlp/otlplog/otlploggrpc \
       go.opentelemetry.io/otel/log
```

### 3.2 初始化(直接用 OTel API)

```go
package main

import (
    "context"
    "time"

    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/exporters/otlp/otlplog/otlploggrpc"
    "go.opentelemetry.io/otel/log"
    sdklog "go.opentelemetry.io/otel/sdk/log"
    "go.opentelemetry.io/otel/sdk/resource"
    semconv "go.opentelemetry.io/otel/semconv/v1.21.0"
)

func setupLogs(ctx context.Context) (*sdklog.LoggerProvider, error) {
    // 1. Resource
    res, _ := resource.New(ctx,
        resource.WithAttributes(
            semconv.ServiceName("my-service"),
            semconv.ServiceVersion("1.0.0"),
        ),
    )

    // 2. Exporter:OTLP gRPC 发给 OTel Collector
    exporter, err := otlploggrpc.New(ctx,
        otlploggrpc.WithEndpoint("otel-collector:4317"),
        otlploggrpc.WithInsecure(),
    )
    if err != nil {
        return nil, err
    }

    // 3. LoggerProvider
    lp := sdklog.NewLoggerProvider(
        sdklog.WithResource(res),
        sdklog.WithProcessor(
            sdklog.NewBatchProcessor(exporter,
                sdklog.WithBatchTimeout(5*time.Second),
            ),
        ),
    )
    otel.SetLoggerProvider(lp)
    return lp, nil
}
```

### 3.3 业务使用

```go
import (
    "go.opentelemetry.io/otel/log"
)

func main() {
    ctx := context.Background()
    lp, _ := setupLogs(ctx)
    defer lp.Shutdown(ctx)

    // 获取 Logger
    logger := otel.Logger("my-service/main")

    // 记录不同级别日志
    var (
        trace  log.Value
        debug  log.Value
        info   log.Value
        warn   log.Value
        error_ log.Value
    )

    logger.Emit(ctx, log.Event{
        Severity: log.LevelInfo,
        Body:     log.StringValue("应用启动成功"),
    })

    logger.Emit(ctx, log.Event{
        Severity: log.LevelWarn,
        Body:     log.StringValue("数据库连接慢"),
        Attributes: []log.KeyValue{
            log.String("db.system", "postgresql"),
            log.Int("duration_ms", 1500),
        },
    })

    logger.Emit(ctx, log.Event{
        Severity: log.LevelError,
        Body:     log.StringValue("支付失败"),
        Attributes: []log.KeyValue{
            log.String("user.id", "u-12345"),
            log.String("order.id", "o-98765"),
            log.String("error.type", "timeout"),
        },
    })

    _ = trace; _ = debug; _ = info; _ = warn; _ = error_
}
```

### 3.4 与现有日志库(slog / logrus / zap)集成

**标准库 slog + OTel**:

```go
import (
    "log/slog"
    "os"
)

func main() {
    handler := slog.NewJSONHandler(os.Stdout, nil)
    logger := slog.New(handler)

    logger.Info("订单创建",
        slog.String("order_id", "o-12345"),
        slog.Int("amount", 9999),
    )
}
```

> **实战建议**:生产用 OTel 自动桥接(slog/logrus/zap)而不是直接用 OTel Logger API,这样既保留原生日志体验,又自动附加 trace_id / span_id。

---

## 4. Python 语言示例

### 4.1 安装依赖

```bash
pip install opentelemetry-api \
            opentelemetry-sdk \
            opentelemetry-exporter-otlp-proto-grpc
```

### 4.2 完整代码

```python
import logging
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes

# 1. 设置 TracerProvider(让日志能关联到 trace)
resource = Resource.create({
    ResourceAttributes.SERVICE_NAME: "my-python-service",
})
provider = TracerProvider(resource=resource)
processor = BatchSpanProcessor(OTLPSpanExporter(endpoint="otel-collector:4317", insecure=True))
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

# 2. 配置 logging 自动注入 trace_id / span_id
from opentelemetry.instrumentation.logging import LoggingInstrumentor
LoggingInstrumentor().instrument(set_logging_format=True)

# 3. 业务使用
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 简单日志
logger.info("应用启动")

# 带 trace context 的日志
tracer = trace.get_tracer(__name__)
with tracer.start_as_current_span("process-order"):
    logger.info("处理订单", extra={"order_id": "o-12345"})
    # 输出会包含 trace_id 和 span_id 字段
```

### 4.3 输出示例

```json
{
  "asctime": "2026-06-21T10:00:00",
  "name": "__main__",
  "levelname": "INFO",
  "message": "处理订单",
  "order_id": "o-12345",
  "otelSpanID": "abc123def456",
  "otelTraceID": "789xyz456abc",
  "otelServiceName": "my-python-service"
}
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
  <dependency>
    <groupId>io.opentelemetry.instrumentation</groupId>
    <artifactId>opentelemetry-logback-mdc-1.0</artifactId>
    <version>2.2.0</version>
  </dependency>
</dependencies>
```

### 5.2 配置(OpenTelemetry SDK)

```java
import io.opentelemetry.api.OpenTelemetry;
import io.opentelemetry.api.common.Attributes;
import io.opentelemetry.api.logs.Logger;
import io.opentelemetry.exporter.otlp.logs.OtlpGrpcLogExporter;
import io.opentelemetry.sdk.OpenTelemetrySdk;
import io.opentelemetry.sdk.logs.SdkLoggerProvider;
import io.opentelemetry.sdk.logs.export.BatchLogProcessor;
import io.opentelemetry.sdk.resources.Resource;
import io.opentelemetry.semconv.ResourceAttributes;

import java.time.Duration;

public class LogExample {
    public static void main(String[] args) {
        Resource resource = Resource.getDefault().merge(
            Resource.create(Attributes.of(
                ResourceAttributes.SERVICE_NAME, "my-java-service"
            ))
        );

        OtlpGrpcLogExporter exporter = OtlpGrpcLogExporter.builder()
            .setEndpoint("http://otel-collector:4317")
            .build();

        SdkLoggerProvider loggerProvider = SdkLoggerProvider.builder()
            .setResource(resource)
            .addLogProcessor(BatchLogProcessor.builder(exporter)
                .setScheduleDelay(Duration.ofSeconds(5))
                .build())
            .build();

        OpenTelemetry sdk = OpenTelemetrySdk.builder()
            .setLoggerProvider(loggerProvider)
            .build();

        // 获取 Logger
        Logger logger = sdk.getLogsBridge().get("my-service/main");

        // 业务日志
        logger.logRecordBuilder()
            .setSeverity(io.opentelemetry.api.logs.Severity.INFO)
            .setBody("应用启动成功")
            .emit();

        logger.logRecordBuilder()
            .setSeverity(io.opentelemetry.api.logs.Severity.ERROR)
            .setBody("支付失败")
            .setAttribute("user.id", "u-12345")
            .setAttribute("order.id", "o-98765")
            .emit();
    }
}
```

### 5.3 与 logback 集成(推荐)

`logback.xml`:

```xml
<configuration>
  <appender name="OTEL" class="io.opentelemetry.instrumentation.logback.mdc.v1_0.OpenTelemetryAppender">
    <appender-ref ref="CONSOLE"/>
  </appender>

  <appender name="CONSOLE" class="ch.qos.logback.core.ConsoleAppender">
    <encoder>
      <pattern>%d{yyyy-MM-dd HH:mm:ss} %-5level [%thread] %logger{36} traceId=%X{trace_id} spanId=%X{span_id} - %msg%n</pattern>
    </encoder>
  </appender>

  <root level="INFO">
    <appender-ref ref="OTEL"/>
  </root>
</configuration>
```

业务代码无需改动,logback 自动附加 trace_id / span_id 到 MDC。

---

## 6. 关联到 Trace(Logs ↔ Traces)

### 6.1 为什么关联?

排查问题时,可以从 **metric 异常 → trace 慢调用 → 日志详情** 逐层下钻。

```
[Grafana] HTTP P99 = 2s 异常
    ↓
[Tempo/Jaeger] 慢 trace: GET /api/order
    ↓
[Loki] 该 trace 下所有日志(含异常堆栈)
```

### 6.2 实现:在 Span 内打印日志

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

with tracer.start_as_current_span("process-order") as span:
    # span_id / trace_id 已经在 context 中
    logger.info("开始处理订单", extra={"order_id": "o-12345"})

    try:
        process_payment()
    except Exception as e:
        # 日志自动关联到当前 span
        logger.exception("支付失败", extra={"error": str(e)})
        span.record_exception(e)
        span.set_status(trace.Status(trace.StatusCode.ERROR))
```

### 6.3 实现:OTel Collector 关联配置

```yaml
# otel-collector-config.yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317

exporters:
  loki:
    endpoint: http://loki:3100/loki/api/v1/push
  otlp/tempo:
    endpoint: tempo:4317
    tls:
      insecure: true

service:
  pipelines:
    logs:
      receivers: [otlp]
      exporters: [loki]
    traces:
      receivers: [otlp]
      exporters: [otlp/tempo]
```

---

## 7. OpenTelemetry Collector 配置(接收 logs)

```yaml
# otel-collector-config.yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

  filelog:
    include:
      - /var/log/pods/*/*/*.log
    operators:
      - type: json_parser
      - type: time_parser
        parse_from: attributes.time

processors:
  batch:
    timeout: 5s
  memory_limiter:
    check_interval: 1s
    limit_percentage: 80
  resource:
    attributes:
      - key: deployment.environment
        value: production
        action: insert

exporters:
  loki:
    endpoint: http://loki:3100/loki/api/v1/push
  otlp:
    endpoint: http://backend-logs:4317

service:
  pipelines:
    logs:
      receivers: [otlp, filelog]
      processors: [memory_limiter, batch, resource]
      exporters: [loki, otlp]
```

---

## 8. 关键术语速查

|术语|含义|
|---|---|
|**LogRecord**|一条日志记录|
|**Logger**|创建 LogRecord 的工具|
|**LoggerProvider**|全局 provider|
|**Severity**|严重等级|
|**Body**|日志主体内容|
|**Attribute**|键值对标签|
|**Resource**|资源属性|
|**TraceId / SpanId**|关联到 trace|
|**OTLP**|OpenTelemetry 传输协议|
|**Log Appender**|把现有日志框架接入 OTel|
|**Mdc / Context**|跨调用栈的上下文传递(Java MDC / Python contextvars)|

---

## 9. 实战建议

1. **结构化日志**:用 JSON 格式,字段化(message、level、timestamp、trace_id、span_id)
2. **统一关联字段**:所有日志带 `trace_id` 和 `span_id`,从 Loki 一键跳到 Tempo
3. **避免高基数标签**:不要把 user_id、order_id 放 attribute
4. **日志级别规范**:ERROR 需要人工介入,WARN 关注但不阻塞,INFO 关键业务
5. **日志采样**:高 QPS 服务只采样 INFO,DEBUG 全量入库成本高
6. **错误日志必带堆栈**:用 `logger.exception()` 而不是 `logger.error()`
7. **生产用日志桥接**:用 slog/logrus/logback 配 OTel Appender,而不是直接用 OTel Logger API
8. **OTel Collector 收 log**:应用直发到 Collector,由 Collector 路由到 Loki/ES
9. **保留周期**:业务合规要求 vs 存储成本
10. **关联查询**:metric → trace → log,逐层下钻

---

## 10. 速记

- **数据模型**:LogRecord = Timestamp + Severity + Body + Attributes + Resource + TraceContext
- **Severity**:TRACE/DEBUG/INFO/WARN/ERROR/FATAL
- **关联 Trace**:日志带 trace_id / span_id,可从 trace 跳到 log
- **生产用日志桥接**:logback/logrus/slog 配 OTel Appender
- **结构化输出**:JSON 格式,字段化
- **数据流**:App → LoggerProvider → Processor(Batch) → Exporter(OTLP) → 后端(Loki/ES)
- **OTel Collector 统一收** log / trace / metric,分别路由
