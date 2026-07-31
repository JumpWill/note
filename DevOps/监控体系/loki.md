# Loki + Promtail / Alloy

Grafana Labs 出品的云原生日志系统。核心思想：**不索引全文，只索引 label，让对象存储承担实际存储**，类似 Prometheus 的多维标签。

## 一、定位

- 横向扩展的日志聚合
- 低成本（对象存储）
- 与 Grafana 深度集成
- LogQL 查询语言（类 PromQL + 文本过滤）

## 二、架构

```text
                     ┌─────────────────────────────────────┐
                     │     Grafana（UI / LogQL / Explore）│
                     └──────────────┬──────────────────────┘
                                    │
                                    ▼
                     ┌─────────────────────────────────────┐
                     │   Loki（查询 / 索引 / 写入协调）       │
                     │   - Distributor                       │
                     │   - Ingester                          │
                     │   - Query Frontend                    │
                     │   - Querier / Query Scheduler         │
                     │   - Compactor                         │
                     └──────────────┬──────────────────────┘
                                    │ boltDB-shipper
                                    ▼
                     ┌─────────────────────────────────────┐
                     │   Object Storage                      │
                     │   - S3 / GCS / OSS / MinIO / Local FS │
                     └─────────────────────────────────────┘

 容器 / Pod / Node ──► Promtail / Grafana Alloy ──HTTP push──► Distributor
                                  │
                                  └─ 流处理 / 解析 / 富化
```

## 三、组件

| 组件 | 责任 |
| ---- | ---- |
| **Distributor** | 接收并校验日志，hash 流到多个 ingester |
| **Ingester** | 内存压缩（gzip+zstd），周期性 flush 到对象存储 |
| **Querier** | 查询使用 LogQL，拉 ingester + store |
| **Query Frontend** | 预查询 / 分片 / caching |
| **Query Scheduler** | 查询任务调度 |
| **Compactor** | 合并 tsdb / 处理 retention |
| **Index Gateway** | 索引 lazy load |
| **Ruler** | 告警规则执行 |
| **Boltdb Shipper** | 索引单机存储 |

## 四、采集

### 1. Promtail（旧）

```yaml
server:
  http_listen_port: 9080

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: system
    static_configs:
      - targets: [localhost]
        labels:
          job: syslog
          __path__: /var/log/*.log
```

### 2. Grafana Alloy（新）

```alloy
loki.source.file "system" {
  targets = [
    {__path__ = "/var/log/*.log", job = "syslog"},
  ]
  forward_to = [loki.write.api.receiver]
}

loki.write "api" {
  endpoint {
    url = "http://loki:3100/loki/api/v1/push"
  }
}
```

### 3. OpenTelemetry Collector

通过 OTLP → Loki exporter 上报。

### 4. Vector / Fluentd → Loki

Vector 配置：

```toml
[sinks.loki]
type = "loki"
inputs = ["parse_json"]
endpoint = "http://loki:3100"
encoding.codec = "json"
labels.service = "{{ service }}"
```

## 五、LogQL 查询

### 1. 过滤

```logql
{job="nginx"}
{job="nginx"} |= "error"
{job="nginx"} != "health"
{job="nginx"} |~ "error|warn"
```

### 2. 度量（类 PromQL）

```logql
count_over_time({job="nginx"}[5m])
rate({job="nginx"}[1m])
sum by (status) (rate({job="nginx"}[1m]))
```

### 3. 解析

```logql
{job="nginx"}
  | logfmt
  | latency > 100ms
  | sum_over_time(success_total) by (region)
```

解析器：`logfmt` / `json` / `regexp` / `pattern` / `unpack`

### 4. 指标化查询

```logql
quantile_over_time(0.95, {job="api"} | unwrap latency[5m])
```

`unwrap` 把某列变成数值用于计算。

## 六、存储

### 1. Index（索引）

- 单机 BoltDB + 对象存储
- 多机模式：TSDB Index（v2.4+，默认）+ 对象存储
- 索引中存 label / stream ID

### 2. Chunks

- Ingester 在内存压缩（content + structured metadata）
- 周期性 flush 到对象存储
- 压缩算法：gzip（默认）、snappy

### 3. Backend 配置

```yaml
storage_config:
  aws:
    s3: s3://access_key:secret_key@region/bucket
  tsdb_shipper:
    active_index_directory: /var/loki/tsdb-index
  filesystem:
    directory: /var/loki/storage
```

S3 / GCS / OSS / MinIO / Swift / 本地。

### 4. Compactor

后台将多个 chunks 文件合并、删除过期 label。

## 七、Retention

Loki 自 v2.0+：

- `retention_enabled: true`
- `retention_period: 744h`（31 天）
- 配置策略：根据 Stream label 决定删除

应用配置生效需要：

```yaml
limits_config:
  retention_period: 744h
  per_stream_rate_limit: 5MB
  max_query_length: 30d
```

## 八、高可用

### 1. Loki 微服务模式

```yaml
memberlist:
  join_members:
    - "loki-1:7946"
    - "loki-2:7946"
    - "loki-3:7946"
```

- Ingester 用一致性 hash 推/拉
- Compactor 单 active，hot standby

### 2. 多租户

```yaml
auth_enabled: true
multitenancy_enabled: true
```

Tenant X-Scope-OrgID 头。

## 九、Alerting

### 1. Ruler

```yaml
ruler:
  alertmanager_url: http://alertmanager:9093
  storage:
    type: local
    local:
      directory: /etc/loki/rules
```

### 2. Rule 例子

```yaml
groups:
  - name: example
    rules:
      - alert: HighErrorRate
        expr: |
          sum(rate({job="api"} |= "error" [5m])) > 1
        for: 10m
        labels:
          severity: critical
```

还可以用 `logfmt` 解析 + 阈值。

## 十、Cortex / Mimir 模式整合

Loki 引入 Cortex 设计：querier 横向扩展，store gateway 缓存，compactor 合并。

## 十一、与 ELK / ClickHouse 对比

| 维度 | Loki | ELK | ClickHouse |
| ---- | ---- | --- | ---------- |
| 索引全文 | ❌（仅 label） | ✔ | 部分 |
| 成本 | 低 | 高 | 低 |
| 规模 | 大 | 中 | 大 |
| 查询体验 | LogQL + label | DSL | SQL |
| 场景 | K8s / 大日志 | 复杂分析 | 低成本大规模 |

## 十二、典型用法

### 1. K8s 日志

```yaml
kubectl logs -n monitoring create -f loki-stack.yaml
```

LokiStack Helm：自动部署 Promtail。

### 2. 多行日志解析

```yaml
scrape_configs:
  - job_name: multiline
    pipeline_stages:
      - multiline:
          firstline: '^\d{4}-\d{2}-\d{2}'
      - regex:
          expression: '^(?P<ts>\d+) (?P<level>\w+) (?P<msg>.*)$'
    static_configs:
      - targets: [localhost]
        labels: {job: myapp}
```

### 3. 应用日志

通过 `fluent-bit` 集成应用日志输出：

```
[OUTPUT]
    Name              loki
    Match             *
    Host              loki
    Port              3100
    Labels            service=api
```

## 十三、性能调优

- **Ingester 数量**：与 ingest rate 适配
- **stream 数量控制**：label 不允许高基数
- **chunk 内存调优**：压缩算法、chunk size
- **查询长 query 限制**：`max_query_length`
- **Caching**：Query Frontend 缓存

## 十四、安全

- Auth + Multi-tenant
- RBAC
- 加密：HTTP / gRPC TLS + 对象存储 SSE
- 删除写入：基于 retention / 显式 delete

## 十五、最佳实践

- **label 卡控**：固定低基数（service, level, env, namespace）
- **不索引 request_id 等**
- **定期看板压测**
- **retention 合理**：法规要求决定长期保存
- **使用 Grafana Lab 的推荐 Helm chart**
- **监控 Loki 自身**（Stack / GELK / Grafana）
