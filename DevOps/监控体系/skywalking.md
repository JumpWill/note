# Apache SkyWalking

Apache 顶级项目的应用性能监控 (APM) 平台，专为微服务 / 云原生 / 容器化设计。集 Metrics / Trace / Log / Topology / Alarm 于一体。

## 一、定位

- 一站式 APM：Metrics + Traces + Logs + Topology + Alerts
- 多语言探针：Java / .NET / Node.js / PHP / Python / Go（社区）
- 多数据源：ES / MySQL / TiDB / H2 / BanyanDB
- 易于 OAP（Observability Analysis Platform）扩展
- 兼容 OpenTelemetry / Zipkin 数据接入

## 二、架构

```text
┌─────────────────────────────────┐
│ Agent / SDK (Java/Go/Python/Node)│
└─────────────┬───────────────────┘
              │ gRPC / HTTP
              ▼
┌─────────────────────────────────┐
│ OAP（Observability Analysis Platform）│
│   Receivers                       │
│   Analysis Module                 │
│   ServiceMesh Module              │
│   Alarm Module                    │
│   Cluster Module                  │
│   Log Module                      │
│   Metrics Query                   │
└─────┬───────────────────┬────────┘
      │                   │
      ▼                   ▼
Storage                Backend
ES / H2 / MySQL / TiDB /  BanyanDB
(Storage Layer)

Web UI（Vue 单页）+ GraphQL

Log Appender  ──► Log Receiver  ──►  Index / Native log
```

## 三、数据流

1. **Agent** 通过字节码 / 自动埋点采集 Trace / Metrics
2. 上报到 OAP
3. OAP 在 Memory 中聚合、记录，周期性 flush 到存储
4. Web UI 通过 GraphQL 查询

## 四、核心概念

| 概念 | 含义 |
| ---- | ---- |
| **Service** | 一组相同业务的服务实例 |
| **ServiceInstance** | 一个 Pod / 进程 |
| **Endpoint** | 一个 URI / handler / RPC method |
| **Trace** | 一次调用的追踪 |
| **Span** | 一次调用片段 |
| **Segment** | 进程内多个 span 组成 |
| **Log** | 日志 |
| **Alarm** | 告警规则 |
| **ServiceMesh** | Mesh 数据（如 Envoy） |
| **Topology** | 拓扑自动构建 |
| **Event** | 自定义事件 |

## 五、Agent

### 1. Java Agent（最成熟）

```bash
java -javaagent:/path/skywalking-agent.jar \
  -Dskywalking.agent.service_name=order-svc \
  -Dskywalking.collector.backend_service=oap:11800 \
  -jar app.jar
```

框架支持：

- Spring Boot / Spring Cloud
- Dubbo / gRPC / Apache HttpClient / OkHttp
- Tomcat / Jetty
- JDBC / Druid / HikariCP
- Kafka / RocketMQ / Pulsar
- Async / Future / Vert.x
- Micronaut / Quarkus

### 2. 配置

```yaml
# agent/config/agent.config
agent.service_name=${SW_AGENT_NAME:order-svc}
collector.backend_service=${SW_AGENT_COLLECTOR_BACKEND_SERVICES:oap:11800}
sample.n_per_3_secs=${SW_SAMPLE:-1}
plugin.toolkit.log.grpc.reporter.server.host=${SW_GRPC_LOG_SERVER_HOST:oap}
plugin.toolkit.log.grpc.reporter.server.port=${SW_GRPC_LOG_SERVER_PORT:11800}
```

- 自定义 trace 段：`@Trace` / `ContextManager`
- 插件扩展：SPI 加载

### 3. 其他语言

| 语言 | 支持 |
| ---- | ---- |
| .NET Core | 官方 |
| Node.js | 官方 |
| PHP | 官方 |
| Python | 官方（旧版 0.x） |
| Go | go2sky 库，需要手动埋点 |
| Rust | 社区 |
| C++ | 社区 |

## 六、OAP 后端

### 1. 启动

```bash
bin/oapService.sh
```

### 2. 模块

- **Core**：基础分析
- **Storage**：ES / MySQL / BanyanDB / H2
- **Register**：实例注册
- **Cluster**：分布式 OAP 协调（基于 K8s / ZK / Standalone）
- **Configuration**：动态配置中心
- **Telemetry**：指标
- **Alarm**：告警
- **Log**：日志分析
- **Event**：事件
- **Service Mesh**：Istio / Envoy

### 3. 数据后端

| 后端 | 模型 |
| ---- | ---- |
| **Elasticsearch 7+** | 全文存储 |
| **H2** | 单机试用 |
| **MySQL / TiDB** | 关系型 |
| **BanyanDB** | 自研列存（v9+） |
| **InfluxDB（已弃用）** | 时序（不再支持） |

BanyanDB 是 v9+ 主力列存引擎，兼容 ES 系列。

## 七、Web UI

### 1. Dashboard

- 概览：服务 / 实例 / endpoint / 拓扑
- 慢端点
- 数据库访问
- JVM 性能
- 告警

### 2. Trace 查询

```text
Service: order-svc
Endpoint: /api/orders
Trace ID: abc...
Time Range
Errors
Duration
```

### 3. 拓扑

服务图，监控 metric 自动绘制。

### 4. 持续剖析（v9+）

- ebpf + Pyroscope
- CPU / Memory / 阻塞

## 八、告警

### 1. 规则

```yaml
service_resp_time_rule:
  name: service_resp_time
  metrics_name: service_resp_time
  op: ">"
  threshold: 1000
  period: 10
  count: 3
  tags:
    level: WARNING
  message: 服务响应时间超过 1000ms
```

### 2. Webhook / 钉钉 / Slack

- alarm 规则命中后触发
- 配置 Alarm Hook

## 九、Metric 体系

| Metric | 含义 |
| ------ | ---- |
| `service_resp_time` | 服务 P99 响应时间 |
| `service_sla` | 服务可达性 |
| `service_cpm` | 服务每分钟调用次数 |
| `service_p99` | P99 |
| `service_p95` | P95 |
| `service_p75` | P75 |
| `service_p50` | P50 |
| `instance_jvm_cpu` | JVM CPU |
| `instance_jvm_memory_heap` | 堆 |
| `instance_jvm_gc` | GC |
| `endpoint_avg` | endpoint 平均响应时间 |
| `endpoint_cpm` | endpoint 调用次数 |

## 十、Topology（拓扑）

- 自动构建：基于 trace 推断
- 服务依赖图
- 可指定服务关系

通过 `service_instance_rb` / `service_instance_call` / `topology` API。

## 十一、日志整合

三种整合方式：

1. **Java Logback Appender**：

```xml
<appender class="org.apache.skywalking.apm.toolkit.log.logback.v1.x.log.GRPCLogClientAppender">
  <serviceName>order-svc</serviceName>
</appender>
```

2. **Fluentd appender**：

```text
<source> @type tail ... </source>
<match> ...
  @type skywalking
  oap_server: oap:11800
  service_name: order-svc
</match>
```

3. **LogQL / ES** 上传：

```text
[INPUT]
   Name tail
   Path /var/log/*.log
[OUTPUT]
   Name es
   Match ...
```

## 十二、Profile（v9+）

- 内建 Continuous Profiling
- EBpf Cpu profiler / Pyroscope backend
- Span 上点击查看火焰图
- Python / Java / Node / Go

## 十三、K8s 部署

Helm：

```bash
helm repo add skywalking https://apache.jfrog.io/artifactory/skywalking-helm
helm install skywalking skywalking/skywalking --set oap.image.tag=9.4.0
```

Elasticsearch Chart：

```yaml
elasticsearch:
  enabled: true
```

或外置 Elasticsearch。

## 十四、与 OTel 互操作

- SkyWalking 9+ **接收 OTLP**（protocol v3+）
- 通过 OAP receiver：
  - `otel-receiver-plugin`
- 探针兼容性：
  - 支持 Zipkin
  - 支持 OpenTelemetry（仅 metrics/traces）
  - SkyWalking 自身 Trace 协议 (v2/v3)

## 十五、SDK 示例（Go go2sky）

```go
import (
    "github.com/SkyAPM/go2sky"
    "github.com/SkyAPM/go2sky/reporter"
)

rep, _ := reporter.NewGRPCReporter("oap:11800")
tracer, _ := go2sky.NewTracer("go-app", rep)
ctx, span, _ := tracer.StartSpan(ctx, "handle")
span.End()
```

## 十六、整体对比

| 维度 | SkyWalking | Jaeger | Tempo |
| ---- | ---------- | ------ | ----- |
| Metrics | ✔ 一等公民 | ❌ | ❌（靠 TraceQL 计算） |
| Trace | ✔ | ✔ | ✔ |
| Log | ✔ | ❌ | ❌ |
| Topology | ✔ 自动 | ❌ | ❌ |
| Profiling | ✔ | ❌ | ❌ |
| 数据库 | ES / MySQL / TiDB / BanyanDB | ES / Cassandra | 对象存储 |
| 适合 | 一体化 APM | Trace only | Trace + Grafana |

## 十七、最佳实践

- **采样策略**：先全量入库一段时间，随后开启筛选
- **服务命名**：带环境/区域前缀
- **业务错误**：自定义 Span Error
- **自定义 metric**：通过 SDK 上报业务指标
- **持续剖析**：开启 Profiling 找瓶颈
- **TraceID 关联日志**：日志记录 traceId，便于跨系统跳转
- **高可用 OAP**：cluster mode + 负载均衡
- **监控 OAP 自身**
