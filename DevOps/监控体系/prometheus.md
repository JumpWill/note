# Prometheus

CNCF 毕业的开源时序数据库与监控系统。云原生时代事实上的监控标准。

## 一、定位与特点

- 多维时序数据模型（metric + label）
- PromQL 强大的查询语言
- Pull 模式采集 + Pushgateway 补充
- 告警规则与 Alertmanager 解耦
- 生态：Exporter / Operator / Recording Rules / Alerting Rules
- 局限：单实例不适合长期存储 / 多副本需要 Remote Write / Federation / Thanos / Cortex / Mimir

## 二、架构

```text
   ┌──────────────────┐
   │ Prometheus Server│
   │  - TSDB          │
   │  - PromQL eval   │
   │  - Rule manager  │
   └──────┬───────────┘
          │ pull
          │
   ┌──────┴───────────────────────┐
   │ Exporter (Node / App / DB ... │
   └───────────────────────────────┘

   Prometheus  ──HTTP──► Alertmanager ──► Email / Slack / PagerDuty
   Prometheus  ──remote_write──► Thanos / Cortex / Mimir / VictoriaMetrics
   Prometheus  ──/api/v1/query──► Grafana
```

## 三、数据模型

### 1. 时间序列

```text
{__name__="http_requests_total", method="GET", status="200", service="api"}
```

- Metric name + label set 唯一确定一条时间序列
- 数据点 = sample = (timestamp, value)
- 类型：

| 类型 | 含义 |
| ---- | ---- |
| Counter | 累加（请求数、错误数） |
| Gauge | 当前值（内存、温度） |
| Histogram | 分桶（响应时间） |
| Summary | 同上但可在客户端算分位数 |
| GaugeHistogram / Native Histogram（v2.47+） | 原生直方图 |

### 2. Label

- 标签控制维度
- 高基数 label（如 user-id、request-id）会爆 series 数，要避免
- Prometheus 默认限制 series 数量

## 四、PromQL

### 1. 基本查询

```promql
up                                      # 当前 1/0（采集目标存活）
rate(http_requests_total[5m])           # 5 分钟内每秒速率
increase(http_requests_total[1h])       # 1 小时增量
sum by (service) (rate(http_requests_total[5m]))
histogram_quantile(0.99, sum by (le) (rate(http_request_duration_seconds_bucket[5m])))
```

### 2. 常用函数

| 函数 | 用途 |
| ---- | ---- |
| `rate()` | 区间平均速率 |
| `irate()` | 瞬时（最后两个点）速率 |
| `increase()` | 区间增量 |
| `delta()` | 区间差值 |
| `histogram_quantile()` | 由 Histogram 算分位数 |
| `predict_linear()` | 线性预测 |
| `topk()` | 取 top k |
| `absent()` | 缺失 |

### 3. 变量

```promql
sum(rate(http_requests_total{status!~"5.."}[5m])) by (service)
  / on() group_left sum(rate(http_requests_total[5m])) by (service)
```

## 五、采集模式

### 1. Pull（默认）

```yaml
scrape_configs:
  - job_name: node
    static_configs:
      - targets: ['10.0.0.10:9100']
```

- Exporter 暴露 `/metrics`
- Prometheus 周期性 pull

### 2. Push Gateway（短任务 / 批任务）

```text
batch job  ──POST──►  Pushgateway  ──pull──► Prometheus
```

- 适合 cronjob、CI 任务
- 注意：实例是 pushgateway 不是真实 job

### 3. Remote Write / Read

```yaml
remote_write:
  - url: http://thanos-receive:19291/api/v1/receive
remote_read:
  - url: http://thanos-query:19290/api/v1/read
```

## 六、Exporter

| Exporter | 监控对象 |
| -------- | -------- |
| **node_exporter** | Linux 主机指标 |
| **cadvisor / kubelet** | 容器 |
| **blackbox_exporter** | HTTP / TCP / ICMP / DNS |
| **mysqld_exporter** | MySQL |
| **redis_exporter** | Redis |
| **nginxinc/nginx-prometheus-exporter** | NGINX Plus |
| **vts / nginx-vts-exporter** | NGINX |
| **rabbitmq_exporter** | RabbitMQ |
| **kafka_exporter** | Kafka |
| **etcd** | etcd |
| **snmp_exporter** | 网络设备 |
| **cAdvisor** | 容器 |
| **kube-state-metrics** | K8s 对象 |

## 七、Recording Rules & Alerting Rules

### 1. Recording Rule

```yaml
groups:
  - name: api
    rules:
      - record: job:http_requests:rate5m
        expr: sum by (job) (rate(http_requests_total[5m]))
```

- 预计算结果
- 提升查询性能

### 2. Alerting Rule

```yaml
groups:
  - name: alerts
    rules:
      - alert: HighErrorRate
        expr: |
          sum(rate(http_requests_total{status=~"5.."}[5m]))
            / sum(rate(http_requests_total[5m])) > 0.05
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: "Error rate > 5%"
```

- `for` 时间窗口避免抖动告警

## 八、Alertmanager

### 1. 架构

```text
Prometheus ──► Alertmanager
                   │
        ┌──────────┼──────────┐
        ▼          ▼          ▼
     group       route     inhibit
   (聚合)        (分发)    (抑制)
        │
        ▼
   receivers (Email / Slack / PagerDuty / Webhook)
```

### 2. 路由示例

```yaml
route:
  receiver: 'default'
  group_by: ['alertname', 'cluster']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  routes:
    - matchers:
        - severity="critical"
      receiver: 'pagerduty'
    - matchers:
        - service="payments"
      receiver: 'pagerduty-payments'
```

### 3. 抑制

```yaml
inhibit_rules:
  - source_matchers: [severity="critical"]
    target_matchers: [severity="warning"]
    equal: [alertname, cluster]
```

critical 抑制同 cluster 的 warning。

## 九、Prometheus Operator

K8s 上以 Operator 管理：

- 创建 `ServiceMonitor` / `PodMonitor` CRD
- Operator 自动注入 scrape config
- 版本升级 / 配置变更更简单
- Thanos / Cortex 等结合

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: my-app
spec:
  selector:
    matchLabels:
      app: my-app
  endpoints:
    - port: http
      interval: 30s
```

## 十、TSDB 与 Remote Storage

### 1. 本地存储

- 区块（block）持久化
- `--storage.tsdb.retention.time=15d`
- WAL + 2h 内存缓存

### 2. 长期方案

| 系统 | 架构 |
| ---- | ---- |
| **Thanos** | Store / Query / Receiver，多 Prometheus 联邦 + 对象存储 |
| **Cortex** | 分片 + 微服务架构，单据点查询 |
| **Mimir** | Cortex 后继（Grafana Labs 维护） |
| **VictoriaMetrics** | 单二进制高性能 |
| **OpenObserve** | 新兴一体化 |

## 十一、联邦

```yaml
# upstream
scrape_configs:
  - job_name: federate
    honor_labels: true
    metrics_path: /federate
    static_configs:
      - targets: ['downstream-prom:9090']
```

适合中心监控 + 多集群分层。

## 十二、SD（Service Discovery）

- static_configs（静态）
- file_sd_configs（文件）
- kubernetes_sd_configs（K8s）
- dns_sd_configs（DNS SRV）
- ec2_sd_configs / azure_sd_configs / gce_sd_configs（云）
- consul_sd_configs
- eureka_sd_configs

K8s SD：

```yaml
kubernetes_sd_configs:
  - role: pod
    namespaces:
      names: [default]
```

## 十三、SDK 集成

### 1. Go

```go
prometheus.NewCounterVec(...)
http.Handle("/metrics", promhttp.Handler())
```

### 2. Java / Micrometer

```java
MeterRegistry registry = new PrometheusMeterRegistry(PrometheusConfig.DEFAULT);
registry.counter("orders").increment();
```

### 3. Python

```python
from prometheus_client import Counter, start_http_server
c = Counter('requests_total', 'http')
c.inc()
start_http_server(8000)
```

## 十四、与 OpenTelemetry 关系

OTEL 已成为新的遥测标准。Prometheus 主要管 metrics，OTEL 统一三大支柱。两者兼容：

- OTEL Collector 提供 prometheus exporter（接收 OTLP 转为 Prometheus）
- Prometheus exporter 可以 `otlphttp` 上报给 OTEL Collector
- 长期趋势：OTEL 主导采集，Prometheus 仍主导 server 与 PromQL 兼容

## 十五、运维实践

- **scrape interval**：SLO 业务 15s～30s；基础设施 1m
- **retention**：本地 7～15 天；长期给 Thanos / VM
- **series 监控**：`prometheus_tsdb_head_series` 跟踪
- **WAL 修复**：`promtool tsdb` + 备份
- **规则预计算**：复杂 query 用 recording rule 缓存
- **告警分级**：`severity=info/warning/critical`
- **oncall 流程**：alert → chat → page，pd 升级策略
- **抓取超时**：`scrape_timeout` 与 interval 配合
