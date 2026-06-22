# OpenTelemetry Metrics(指标)

OpenTelemetry Metrics 提供对应用运行时**数值型数据**的采集、聚合和导出能力,是 APM "可观测性三大支柱"之一。

---

## 1. 基本概念

### 1.1 三大支柱

|支柱|回答什么问题|典型工具|
|---|---|---|
|**Metrics**|系统**整体趋势**怎么样?CPU 多高?QPS 多大?|Prometheus、Grafana|
|**Logs**|**具体发生了什么**?异常堆栈、调试信息|ELK、Loki|
|**Traces**|请求**经过了哪些环节**,哪里慢?|Jaeger、Zipkin|

### 1.2 Metric 的关键概念

|术语|含义|
|---|---|
|**Measurement**|一次测量点(原始数据)|
|**Instrument**|测量工具(计数器、仪表盘等)|
|**Meter**|工具的集合,管理所有 instrument|
|**MeterProvider**|全局 provider,管理 Meter 生命周期|
|**Metric Reader**|读取数据并导出|
|**Exporter**|导出到后端(OTLP/Prometheus)|
|**Resource**|资源属性(service.name、host 等)|
|**Instrumentation Scope**|库的标识(name、version)|
|**Attribute**|标签键值对,用于过滤/聚合(method=GET, status=200)|
|**Aggregation**|聚合方式(sum/lastValue/histogram)|
|**Time Series**|唯一 metric name + attribute 集合标识|

### 1.3 四种 Instrument 类型

|类型|行为|适用场景|
|---|---|---|
|**Counter**|单调递增|请求数、错误数、字节数|
|**UpDownCounter**|可增可减|当前连接数、队列长度、Goroutine 数|
|**Histogram**|分布统计|请求耗时、响应大小|
|**Gauge / ObservableGauge**|异步取值的瞬时值|CPU 使用率、内存占用、温度|

> OpenTelemetry 在 v1.0+ 已统一规范,Java/Go/Python 都已经支持 Counter、UpDownCounter、Histogram、ObservableGauge。

---

## 2. 数据模型

### 2.1 数据流

```text
数据流:App → Instrument → Aggregation → Reader → Exporter → 后端
+----------+    +-------------+    +-------------+    +------------+
|   App    |--->| Instrument  |--->| Aggregation |--->|   Reader   |
+----------+    |  (Counter,  |    | (sum, hist, |    |  (Periodic)|
                |  Histogram) |    |  lastValue) |    +------+-----+
                +-------------+    +-------------+           |
                                                            v
                                                  +-----------------+
                                                  |    Exporter     |
                                                  | (OTLP,Prom,etc) |
                                                  +-----------------+
                                                            |
                                                            v
                                                  Prometheus / OTel
                                                  Collector / 后端
```

### 2.2 关键属性

|属性|说明|
|---|---|
|`service.name`|服务名|
|`service.version`|服务版本|
|`deployment.environment`|环境(prod/staging)|
|`host.name`|主机名|
|`process.pid`|进程 ID|
|自定义 attribute|如 `http.method`、`http.status_code`|

---

## 3. Go 语言 OpenTelemetry Metrics 完整示例

### 3.1 初始化

```go
package main

import (
    "context"
    "time"

    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetricgrpc"
    "go.opentelemetry.io/otel/exporters/prometheus"
    "go.opentelemetry.io/otel/metric"
    sdkmetric "go.opentelemetry.io/otel/sdk/metric"
    "go.opentelemetry.io/otel/sdk/resource"
    semconv "go.opentelemetry.io/otel/semconv/v1.21.0"
)

func setupMetrics(ctx context.Context) (*sdkmetric.MeterProvider, error) {
    // 1. Resource:服务身份信息
    res, _ := resource.New(ctx,
        resource.WithAttributes(
            semconv.ServiceName("my-service"),
            semconv.ServiceVersion("1.0.0"),
            semconv.DeploymentEnvironment("production"),
        ),
    )

    // 2. Exporter:OTLP gRPC 发给 OTel Collector
    exporter, err := otlpmetricgrpc.New(ctx,
        otlpmetricgrpc.WithEndpoint("otel-collector:4317"),
        otlpmetricgrpc.WithInsecure(),
    )
    if err != nil {
        return nil, err
    }

    // 3. MeterProvider
    mp := sdkmetric.NewMeterProvider(
        sdkmetric.WithResource(res),
        sdkmetric.WithReader(
            sdkmetric.NewPeriodicReader(exporter,
                sdkmetric.WithInterval(10*time.Second),  // 10s 导出一次
            ),
        ),
    )
    otel.SetMeterProvider(mp)
    return mp, nil
}
```

### 3.2 启动时使用

```go
func main() {
    ctx := context.Background()
    mp, _ := setupMetrics(ctx)
    defer mp.Shutdown(ctx)

    // 获取 Meter
    meter := otel.Meter("my-service/metrics")

    // 创建 Counter
    requestCounter, _ := meter.Int64Counter(
        "http_requests_total",
        metric.WithDescription("HTTP 请求总数"),
    )

    // 创建 Histogram
    latencyHist, _ := meter.Float64Histogram(
        "http_request_duration_seconds",
        metric.WithDescription("HTTP 请求耗时(秒)"),
        metric.WithUnit("s"),
    )

    // 业务中使用
    for {
        time.Sleep(time.Second)
        requestCounter.Add(ctx, 1,
            metric.WithAttributes(
                attribute.String("method", "GET"),
                attribute.String("status", "200"),
            ),
        )
        latencyHist.Record(ctx, 0.123,
            metric.WithAttributes(
                attribute.String("method", "GET"),
                attribute.String("path", "/api/users"),
            ),
        )
    }
}
```

### 3.3 UpDownCounter 示例

```go
// 当前活跃连接数
activeConn, _ := meter.Int64UpDownCounter(
    "active_connections",
    metric.WithDescription("当前活跃连接数"),
)

// 连接建立时 +1
activeConn.Add(ctx, 1, metric.WithAttributes(
    attribute.String("protocol", "tcp"),
))

// 连接断开时 -1
activeConn.Add(ctx, -1, metric.WithAttributes(
    attribute.String("protocol", "tcp"),
))
```

### 3.4 ObservableGauge(异步取值)示例

```go
// 异步采集 CPU 温度,每次导出时调 callback
meter.Float64ObservableGauge(
    "cpu_temperature_celsius",
    metric.WithDescription("CPU 温度"),
    metric.WithFloat64Callback(func(ctx context.Context, o metric.Float64Observer) error {
        temp := readCPUTemp()  // 自定义函数
        o.Observe(temp)
        return nil
    }),
)
```

### 3.5 Histogram 显式桶配置

```go
hist, _ := meter.Float64Histogram(
    "http_request_duration_seconds",
    metric.WithExplicitBucketBoundaries(
        0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10,
    ),
)
```

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
from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes
import time

# 1. Resource
resource = Resource.create({
    ResourceAttributes.SERVICE_NAME: "my-python-service",
    ResourceAttributes.SERVICE_VERSION: "1.0.0",
})

# 2. Exporter
exporter = OTLPMetricExporter(endpoint="otel-collector:4317", insecure=True)
reader = PeriodicExportingMetricReader(exporter, export_interval_millis=10000)

# 3. MeterProvider
provider = MeterProvider(resource=resource, metric_readers=[reader])
metrics.set_meter_provider(provider)

# 4. 获取 Meter
meter = metrics.get_meter("my-service/metrics")

# 5. 创建 Counter
counter = meter.create_counter(
    name="http_requests_total",
    description="HTTP 请求总数",
    unit="1",
)

# 6. 创建 Histogram
histogram = meter.create_histogram(
    name="http_request_duration_seconds",
    description="HTTP 请求耗时",
    unit="s",
)

# 7. 业务使用
counter.add(1, {"method": "GET", "status": "200"})
histogram.record(0.123, {"method": "GET", "path": "/api/users"})

# 程序退出前
provider.shutdown()
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
import io.opentelemetry.api.metrics.LongCounter;
import io.opentelemetry.api.metrics.LongHistogram;
import io.opentelemetry.api.metrics.Meter;
import io.opentelemetry.exporter.otlp.metrics.OtlpGrpcMetricExporter;
import io.opentelemetry.sdk.OpenTelemetrySdk;
import io.opentelemetry.sdk.metrics.SdkMeterProvider;
import io.opentelemetry.sdk.metrics.export.PeriodicMetricReader;
import io.opentelemetry.sdk.resources.Resource;
import io.opentelemetry.semconv.ResourceAttributes;

import java.time.Duration;

public class MetricsExample {
    public static void main(String[] args) {
        // 1. Resource
        Resource resource = Resource.getDefault().merge(
            Resource.create(Attributes.of(
                ResourceAttributes.SERVICE_NAME, "my-java-service",
                ResourceAttributes.SERVICE_VERSION, "1.0.0"
            ))
        );

        // 2. Exporter
        OtlpGrpcMetricExporter exporter = OtlpGrpcMetricExporter.builder()
            .setEndpoint("http://otel-collector:4317")
            .build();

        // 3. MeterProvider
        SdkMeterProvider meterProvider = SdkMeterProvider.builder()
            .setResource(resource)
            .registerMetricReader(
                PeriodicMetricReader.builder(exporter)
                    .setInterval(Duration.ofSeconds(10))
                    .build()
            )
            .build();

        OpenTelemetry sdk = OpenTelemetrySdk.builder()
            .setMeterProvider(meterProvider)
            .build();

        // 4. 获取 Meter
        Meter meter = sdk.getMeter("my-service/metrics");

        // 5. Counter
        LongCounter requestCounter = meter
            .counterBuilder("http_requests_total")
            .setDescription("HTTP 请求总数")
            .build();

        // 6. Histogram
        LongHistogram latencyHist = meter
            .histogramBuilder("http_request_duration_seconds")
            .setDescription("HTTP 请求耗时(秒)")
            .ofLongs()
            .build();

        // 7. 业务使用
        requestCounter.add(1, Attributes.of(
            AttributeKey.stringKey("method"), "GET",
            AttributeKey.stringKey("status"), "200"
        ));
        latencyHist.record(123, Attributes.of(
            AttributeKey.stringKey("method"), "GET",
            AttributeKey.stringKey("path"), "/api/users"
        ));
    }
}
```

---

## 6. OpenTelemetry Collector 配置(接收 metrics)

```yaml
# otel-collector-config.yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

  prometheus:
    config:
      scrape_configs:
        - job_name: 'my-service'
          scrape_interval: 15s
          static_configs:
            - targets: ['my-service:8888']

processors:
  batch:
    timeout: 10s
    send_batch_size: 1024

  memory_limiter:
    check_interval: 1s
    limit_percentage: 80
    spike_limit_percentage: 25

exporters:
  prometheus:
    endpoint: "0.0.0.0:8889"
    resource_to_telemetry_conversion:
      enabled: true

  otlp:
    endpoint: tempo:4317
    tls:
      insecure: true

service:
  pipelines:
    metrics:
      receivers: [otlp, prometheus]
      processors: [memory_limiter, batch]
      exporters: [prometheus, otlp]
```

---

## 7. HTTP 中间件自动埋点(Web 框架集成)

### 7.1 Gin 框架

```go
import (
    "github.com/gin-gonic/gin"
    "go.opentelemetry.io/contrib/instrumentation/github.com/gin-gonic/gin/otelgin"
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/metric"
)

func main() {
    // ... 初始化 meter provider 略

    meter := otel.Meter("my-service/http")
    requestCounter, _ := meter.Int64Counter("http_requests_total")
    requestDuration, _ := meter.Float64Histogram("http_request_duration_seconds")

    r := gin.Default()
    r.Use(otelgin.Middleware("my-service"))   // 自动埋点

    r.GET("/api/users", func(c *gin.Context) {
        // 业务处理
        c.JSON(200, gin.H{"users": []string{}})
    })

    r.Run(":8080")
}
```

### 7.2 自动生成的标准指标

OpenTelemetry HTTP 语义约定自动产生:
- `http.server.request.duration` - Histogram
- `http.server.active_requests` - UpDownCounter
- `http.server.request.body.size` - Histogram
- `http.server.response.body.size` - Histogram

attributes 包含:`http.method`、`http.status_code`、`http.route` 等。

---

## 8. 关键术语速查

|术语|含义|
|---|---|
|**Counter**|单调递增计数|
|**UpDownCounter**|双向计数|
|**Histogram**|分布统计|
|**ObservableGauge**|异步瞬时值|
|**Meter**|工具容器|
|**MeterProvider**|全局 provider|
|**OTLP**|OpenTelemetry Protocol(数据格式)|
|**Semantic Conventions**|语义约定(标准 attribute 名)|
|**Cumulative / Delta**|累加 / 增量 临时性|
|**Exemplar**|指标点对应的 trace 样本|

---

## 9. 最佳实践

1. **命名规范**:`<namespace>_<subsystem>_<name>_<unit>`,如 `http_request_duration_seconds`
2. **单位用 UCUM**:`s`、`ms`、`By`、`1`(无量纲)
3. **使用语义约定**:标准 attribute 名(`http.method`、`http.status_code`)
4. **Histogram 桶要合理**:覆盖常见 p99 范围
5. **避免高基数标签**:不要把 user_id、request_id 放 attribute
6. **资源属性统一**:用 env/envsubst 注入 service.name
7. **导出间隔 10-15s**:太短增加负载,太长数据粒度粗
8. **生产用 OTLP 推模式**:主动 push 给 Collector
9. **Prometheus 用拉模式**:暴露 `/metrics` endpoint
10. **关联 trace**:通过 exemplar 在 metric 点上附 trace_id

---

## 10. 速记

- **四种 Instrument**:Counter(单调) / UpDownCounter(可增可减) / Histogram(分布) / ObservableGauge(异步瞬时)
- **数据流**:App → Instrument → Aggregation → Reader → Exporter → 后端
- **三种语言都支持**:Go / Python / Java,API 设计一致
- **标准 attribute 用语义约定**:`http.method`、`http.status_code` 等
- **OTLP 协议**:跨语言、跨厂商的统一传输
- **生产架构**:App + OTel SDK → OTel Collector(收/处/转) → Prometheus + Tempo + Loki
