# Prometheus

> 开源的**指标**（metrics）监控系统，CNCF 毕业项目。核心思路：**Pull 拉取 + 时序存储 + PromQL + 告警**，四件套整合在一个二进制里。
> 不擅长：日志（用 Loki）、链路（用 Jaeger/Tempo）、高基数明细（用 ClickHouse）。

---

## 一、架构

```text
┌────────────────────────────────────────────────────────────┐
│                       Prometheus Server                    │
│  ┌────────────┐  ┌──────────┐  ┌──────────────┐  ┌──────┐  │
│  │ Retrieval  │─►│ TSDB    │─►│ HTTP Server  │─►│ Prom │  │
│  │ (Scrape)   │  │ (存储)   │  │ /query /alerts│  │  UI  │  │
│  └────────────┘  └──────────┘  └──────┬───────┘  └──────┘  │
│         ▲                              │                   │
│         │ Pull                        ▼ Alert Rules       │
│  ┌──────┴────────┐              ┌──────────────┐           │
│  │ Targets       │              │ Alertmanager │──► 通道  │
│  │ (Exporter/SDK)│              └──────────────┘           │
│  └───────────────┘                                          │
└────────────────────────────────────────────────────────────┘
                              ▲
                              │ Remote Write（可选）
                  ┌───────────┴───────────┐
                  │  Thanos / Cortex / VM  │  ← 多副本 / 长期存储
                  └───────────────────────┘
```

五大组件：

| 组件 | 职责 |
| --- | --- |
| **Retrieval** | 拉取目标 HTTP `/metrics` 端点，支持多种服务发现 |
| **TSDB** | 本地时序库，LSM 风格的 Block 存储 + WAL |
| **HTTP Server** | PromQL 查询、API、UI |
| **Alert Rules** | 周期性评估，命中后发给 Alertmanager |
| **Pushgateway** | 补充：短命任务 / 防火墙内的主动 push |

---

## 二、数据模型

### 2.1 一条样本 = 名字 + 标签 + 时间戳 + 值

```text
http_requests_total{method="GET",code="200"} @ 1714579200  →  94355
└──── metric name ─────┘└────── labels ──────┘└─ ts ─┘      └ value ┘
```

- **Metric Name**：建议带单位后缀（`_bytes` / `_seconds` / `_total`）
- **Labels**：KV 维度，**决定基数**——小心高基数（user_id / order_id）
- **Sample**：`(timestamp, value)`，float64
- 唯一标识一条时序 = `metric_name + labels`

### 2.2 四种指标类型

| 类型 | 行为 | 典型场景 | 函数 |
| --- | --- | --- | --- |
| **Counter** | 只增不减（或重置） | 请求数、错误数、CPU 累计时间 | `rate()` / `increase()` |
| **Gauge** | 可增可减，反映瞬时值 | 内存、温度、并发连接数 | `delta()` / `deriv()` |
| **Histogram** | 分桶统计 + `_sum`/`_count` | 延迟、响应大小 | `histogram_quantile()` |
| **Summary** | 客户端算好分位数 | 同上但更准，不能跨实例聚合 | 直接读 quantile 字段 |

**Histogram vs Summary**：

```text
Histogram: 服务端按桶统计，可跨实例聚合 → 算 P95/P99
  http_request_duration_seconds_bucket{le="0.5"} 2400
  http_request_duration_seconds_bucket{le="1.0"} 2800
  http_request_duration_seconds_bucket{le="+Inf"} 3000
  → histogram_quantile(0.95, ...) = ?

Summary: 客户端算好分位数，单实例精确但不可聚合
  http_request_duration_seconds{quantile="0.95"} 0.234
```

生产**优先 Histogram**（可聚合、可重算 quantile），Summary 留作客户端资源受限场景。

---

## 三、PromQL 速查

### 3.1 即时 vs 范围

```promql
# 即时向量（瞬时值）
up == 0

# 范围向量（区间内所有点，必须再聚合）
up[5m]

# 子查询（高级）
rate(http_requests_total[5m])[10m:1m]   # 最近 10 分钟，每 1 分钟一个 rate
```

### 3.2 核心函数

```promql
# 速率 / 增长
rate(http_requests_total[5m])           # 每秒速率（推荐，Counter 用）
irate(http_requests_total[1m])          # 瞬时速率（抖动用，慎用长期）
increase(http_requests_total[1h])        # 时间段内的增量
deriv(node_load1[2h])                   # 导数（线性外推）

# 聚合
sum by (namespace) (kube_pod_info)      # 按 namespace 求和
count by (pod) (kube_pod_container_status_running)
topk(5, http_requests_total)            # 前 5
bottomk(5, latency)                     # 后 5

# 分位数
histogram_quantile(0.99,
  sum by (le, service) (rate(http_request_duration_seconds_bucket[5m]))
)

# 预测
predict_linear(node_filesystem_avail_bytes[6h], 24*3600)  # 24h 后值

# 数学
node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes
```

### 3.3 匹配符

```promql
method="GET"              # 完全等
method!="GET"             # 不等
method=~"GET|POST"        # 正则（RE2）
method!~"GET|POST"        # 反正则
```

---

## 四、配置（prometheus.yml）

### 4.1 最小可用版本

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels: { cluster: prod-1 }

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

rule_files:
  - /etc/prometheus/rules/*.yml

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']
```

### 4.2 服务发现（生产主流）

```yaml
scrape_configs:
  # 文件 SD（最稳，CI/CD 写文件）
  - job_name: 'file-sd'
    file_sd_configs:
      - files: ['/etc/prometheus/targets/*.json']
    refresh_interval: 30s

  # Kubernetes SD（Pod 维度）
  - job_name: 'kubernetes-pods'
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
        action: keep
        regex: "true"
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_port]
        action: replace
        regex: (\d+)
        target_label: __address__
        replacement: ${1}
      - source_labels: [__meta_kubernetes_namespace]
        target_label: namespace
      - source_labels: [__meta_kubernetes_pod_name]
        target_label: pod

  # Kubernetes SD（Service 维度，统一约定 monitoring=enabled）
  - job_name: 'k8s-endpoints'
    kubernetes_sd_configs:
      - role: endpoints
    relabel_configs:
      - source_labels: [__meta_kubernetes_service_label_monitoring]
        action: keep
        regex: enabled
      - source_labels: [__meta_kubernetes_endpoint_port_name]
        action: keep
        regex: metrics
      - source_labels: [__meta_kubernetes_endpoint_ready]
        action: keep
        regex: "true"
      - action: labelmap
        regex: __meta_kubernetes_service_label_(.+)
```

### 4.3 应用标准 annotation

```yaml
metadata:
  annotations:
    prometheus.io/scrape: "true"
    prometheus.io/port: "8080"
    prometheus.io/path: "/metrics"
```

### 4.4 远程写入（推荐生产开启）

```yaml
remote_write:
  - url: "http://thanos-receive:19291/api/v1/receive"
    write_relabel_configs:        # 写入前过滤，降低存储成本
      - source_labels: [__name__]
        regex: 'go_.*|process_.*'
        action: drop
    queue_config:
      capacity: 10000
      max_samples_per_send: 2000
```

---

## 五、告警规则

### 5.1 三种状态

```text
INACTIVE ──expr 命中──► PENDING ──持续 for 时间──► FIRING ──发给 AM
   ▲                       │                          │
   │                       │ 恢复                     │ 恢复
   └───────────────────────┴──────────────────────────┘
```

- `PENDING`：条件已满足但没到 `for` 时间——不发，仅 UI 可见
- `FIRING`：持续时间到阈值，发给 Alertmanager
- `INACTIVE`：完全恢复

### 5.2 规则文件

```yaml
groups:
- name: node.rules
  interval: 30s                # 这组规则的评估频率（覆盖全局）
  rules:
  - alert: NodeDiskWillFillIn24h
    expr: predict_linear(node_filesystem_avail_bytes[6h], 86400) < 0
    for: 1h
    labels:
      severity: P1
      team: sre
    annotations:
      summary: "节点 {{ $labels.instance }} 磁盘将满"
      description: "按当前速度，24h 后可用空间 < 0，请扩容"
      runbook_url: "https://wiki/runbooks/node-disk"

  - alert: InstanceDown
    expr: up == 0
    for: 3m
    labels: { severity: P0 }
    annotations:
      summary: "{{ $labels.instance }} 已宕机"
```

**好告警的标准**：每个告警都能回答"出事了我该找谁/做什么"——所以一定要有 `summary`、`description`、`runbook_url`、`owner team label`。

---

## 六、Recording Rules（预计算）

高频查询（dashboard、告警）走 recording rule，**避免每次实时算**：

```yaml
groups:
- name: aggregation.rules
  interval: 30s
  rules:
  - record: job:http_requests:rate5m
    expr: sum by (job) (rate(http_requests_total[5m]))

  - record: job:http_latency:p99
    expr: histogram_quantile(0.99,
        sum by (le, job) (rate(http_request_duration_seconds_bucket[5m])))

  - record: instance:node_cpu:rate5m
    expr: sum by (instance) (rate(node_cpu_seconds_total{mode!="idle"}[5m]))
```

约定 record name 格式：`<level>:<metric>:<operations>`（level 是 aggregation level）。

---

## 七、存储与生命周期

### 7.1 本地 TSDB 结构

```text
data/
├── chunks_head/        # 内存 + WAL，待写满 2h 切块
├── 01HMV9P8G3R8XYZ/    # 2h block 目录（不可变）
│   ├── chunks/
│   ├── index
│   └── meta.json
└── wal/
```

- 内存 2h 窗口 → 落盘成 block → 压缩/合并 → 删除过期 block
- 默认 `--storage.tsdb.retention.time=15d`（磁盘够大可拉长到 30–90d）
- `--storage.tsdb.retention.size` 限制最大字节数

### 7.2 长期存储方案

| 方案 | 特点 |
| --- | --- |
| **Thanos** | 对象存储（S3/OSS）+ 全局视图 + 下采样，主流 |
| **Cortex / Mimir** | 多租户，运维较重，但吞吐强 |
| **VictoriaMetrics** | 单二进制，**比 Prometheus 省 10× 存储**，兼容 PromQL/remote_write |
| **Grafana Cloud / Datadog** | 商业托管，省心 |

---

## 八、运维要点

### 8.1 热加载

```bash
# 启动时开启
prometheus --web.enable-lifecycle ...

# 热加载（仅 scrape_configs、rule_files、alerting）
curl -X POST http://localhost:9090/-/reload
```

⚠️ **不会**重新加载：`global`、`storage`、`remote_write`——这些改完得重启。

### 8.2 HA / 分片

- Prometheus **本身无 HA**——两个独立副本抓同样数据 → 写两个 remote_write
- **分片（sharding）**：用 Prometheus Agent 模式（`--enable-feature=agent`）或外部工具（`promxy`）按 target 切片
- **全局视图**：Thanos query / Grafana Mimir 做跨副本查询

### 8.3 启动参数

```bash
prometheus \
  --config.file=/etc/prometheus/prometheus.yml \
  --storage.tsdb.path=/prometheus \
  --storage.tsdb.retention.time=30d \
  --storage.tsdb.retention.size=200GB \
  --web.enable-lifecycle \
  --web.console.libraries=/usr/share/prometheus/console_libraries \
  --web.page-title="Prometheus (prod-1)" \
  --web.external-url=https://prom.example.com
```

---

## 九、最佳实践

1. **label 是双刃剑**：低基数（env, region, service, version, instance）OK；高基数（user_id, email, ip）必爆——drop 掉
2. **统一 scrape interval**：15s 是甜蜜点；高频（5s）烧磁盘，低频（60s）告警不灵敏
3. **PromQL 加 label filter**：所有查询带 `{cluster="prod"}`，避免误聚合到测试集群
4. **告警分级 + owner**：每条 rule 必有 `severity` + `team`，路由才有依据
5. **Recording rule + Alert rule 分文件**：聚合放一个 group，告警放另一个，方便 review
6. **别忘 `for`**：无 `for` 的告警 = 抖动即触发 = 噪音
7. **metrics_path 校验**：抓不到数据先看 `/api/v1/targets` 页面，**比看日志快 10 倍**
8. **remote_write 的 relabel 是省钱关键**：drop 掉 `go_*` / `process_*` / debug 指标，存储直接砍一半

---

## 十、踩过的坑

| 现象 | 根因 |
| --- | --- |
| 内存 OOM | label 基数爆炸 / scrape 频率太高 / TSDB block 太多 |
| 磁盘告警 | retention 过长 / block 没合并（升级到 2.x 后少见） |
| 告警风暴 | rule 没加 `for` / inhibit 没配 |
| 抓不到数据 | target page 看 `last error` —— 99% 是认证/路径/网络 |
| PromQL 慢 | 范围太大 + 没聚合 → 先 aggregate 再算 |
| 重复告警 | 多个 Prometheus 推同一个 Alertmanager → 上 hashmod shard |

---

## 十一、PromQL / 文档资源

- 官方：<https://prometheus.io/docs/prometheus/latest/querying/basics/>
- 函数索引：<https://prometheus.io/docs/prometheus/latest/functions/>
- 最佳实践：<https://prometheus.io/docs/practices/naming/>
- 实战 book：《Prometheus 监控实战》（James Turnbull）
