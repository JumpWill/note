# Loki —— Grafana 家的云原生日志系统

> **"Prometheus for logs"** —— 不建全文索引，**只索引标签**，日志内容压缩后存对象存储。
> 直接由 Grafana Labs 维护，与 Grafana / Prometheus / Tempo 天然集成。
> 适合：**K8s 日志 / 业务日志 / 容量大成本敏感** 的场景。

---

## 一、核心哲学：为什么不建索引

传统 ELK 痛点：

```text
全文索引（ES）
├─ 写入：分词 → 倒排表 → 占 60%+ 存储
├─ 索引膨胀 → 写入变慢
└─ 全文检索是真本事，但 80% 场景只要"按 pod/namespace/app 过滤"
```

Loki 的取舍：

```text
Loki：日志本体压缩进对象存储，只索引一组**标签 KV**
   {cluster="prod", namespace="pay", app="order", level="error"}
              │
              │ 按标签查 = O(标签集合)，极快
              │ 全文搜 = 拉对应 chunk 出来 grep，慢但能搜
```

**好处**：
- 存储成本降到 ELK 的 **1/5–1/10**
- 不用提前规划分片 / mapping，运维极简
- Grafana 直接查询（同一 UI 看指标 + 日志 + Trace）

**代价**：
- 没有"全文秒级搜索"——大文本 grep 会拉很多 chunk，慢
- 不擅长复杂聚合（ES aggregation 比 Loki 强）

---

## 二、架构组件

Loki 部署有两种模式：

| 模式 | 组件 | 适用 |
| --- | --- | --- |
| **单体（Monolithic）** | 一个进程跑所有角色 | 开发 / 测试 / 小集群 |
| **微服务（Microservices）** | 各角色独立扩缩容 | **生产** |

### 2.1 组件全景

```text
┌─────────────┐
│  Promtail / │ ── push (HTTP/gRPC)
│  Grafana    │         │
│  Alloy /    │         ▼
│  Vector     │   ┌─────────────┐
└─────────────┘   │ Distributor │  ── 分流到 Ingester
                  └─────────────┘         │
                                          ▼
                  ┌─────────────┐   ┌─────────────┐
                  │   Ingester  │──►│ Object Store│ (S3/OSS/MinIO)
                  │  (内存 + WAL)│   │  chunks     │
                  └─────────────┘   └─────────────┘
                                          │
                                          ▼
                  ┌─────────────┐   ┌─────────────┐
                  │   Querier   │◄──│ Index Store │ (TSDB/BoltDB)
                  └─────────────┘   └─────────────┘
                        │
                        ▼
                  ┌─────────────────┐
                  │ Query Frontend  │ ── 分片 / 缓存 / 并发
                  └─────────────────┘
                        │
                        ▼
                  ┌─────────────┐
                  │   Grafana   │ (查询 / 可视化)
                  └─────────────┘

其他角色：
  - Compactor          压缩老 chunk，合并 index
  - Index Gateway       缓存 index 查询
  - Ruler               告警 / recording rules（跟 Prometheus Alert 一样）
  - Querier / Query Frontend  读路径
```

### 2.2 各角色职责

| 组件 | 职责 | 关键参数 |
| --- | --- | --- |
| **Distributor** | 接收写入请求，按 tenant + hash 分流 | replicas ≥ 3 |
| **Ingester** | 写入日志（内存 + WAL），定期 flush 到对象存储 | `chunk_encoding` / `max_chunk_age` |
| **Querier** | 查路径：从 store 拉 chunk + 从 ingester 拉热数据 | 并发查 |
| **Query Frontend** | 查询分片 / 结果缓存 / 拆分大查询 | 必备，挡大查询炸 Querier |
| **Compactor** | 后台合并老 chunk + 索引去重 | 单实例即可 |
| **Index Gateway** | index 查询代理（替代 querier 自己读 index） | 推荐开 |
| **Ruler** | 评估 LogQL alert/recording rules → 触发告警 | 可选，但生产强烈推荐 |
| **Store** | 对象存储（S3 / OSS / GCS / Azure） | 必选 |
| **WAL** | Ingester 写盘防宕机丢数据 | 必开 |

---

## 三、安装（Grafana 全家桶）

### 方式 A：Loki Helm chart（⭐ 推荐）

```bash
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

# 一次性装齐：Loki + Promtail + Grafana
helm install loki grafana/loki-stack \
  --namespace logging --create-namespace \
  --set prometheus.enabled=true \
  --set grafana.enabled=true \
  --set loki.persistence.enabled=true \
  --set loki.persistence.size=50Gi
```

### 方式 B：loki-distro（官方一体化）

```bash
# 单二进制起单进程模式（开发用）
docker run -p 3100:3100 grafana/loki:3.3.0 \
  -config.file=/etc/loki/local-config.yaml
```

### 方式 C：生产微服务模式（values.yaml 关键项）

```yaml
# values.yaml 摘录
loki:
  auth_enabled: false                  # 多租户开关
  commonConfig:
    replication_factor: 3              # chunk 副本数
    ring:
      kvstore:
        store: memberlist              # 或 consul / etcd
  storage:
    type: s3
    s3:
      endpoint: oss-cn-hangzhou.aliyuncs.com
      bucketnames: loki-chunks
      access_key_id: xxx
      secret_access_key: yyy
    tsdb:
      store:                          # index 后端
        type: boltdb
        boltdb:
          directory: /data/loki/boltdb
  schemaConfig:
    configs:
      - from: "2024-01-01"
        store: tsdb                    # v11+ 用 TSDB 做 index
        object_store: s3
        schema: v13
  limits_config:
    retention_period: 744h             # 31 天
    ingestion_rate_mb: 10              # 每租户每秒 ingest 上限
    ingestion_burst_size_mb: 20
    max_query_parallelism: 32
    max_query_length: 30d              # 最长查 30 天
```

### 方式 D：Loki Operator（CRD 化）

```bash
helm install loki-operator grafana/loki-operator \
  -n logging --create-namespace
```

```yaml
apiVersion: loki.grafana.com/v1
kind: LokiStack
metadata:
  name: loki
  namespace: logging
spec:
  size: 1x.small                       # 预设规模：1x.demo / 1x.small / 1x.medium
  storage:
    secret:
      name: my-storage-secret
    type: s3
  tenants:
    mode: openshift-tenant            # 或 static、dynamic
  rules:
    enabled: true
  alerting:
    enabled: true
```

---

## 四、采集：Promtail / Grafana Alloy / 其他

### 4.1 Grafana Alloy（新项目首选）

Grafana 官方新一代采集器，**Promtail 已被标记 deprecated**（虽然还能用）。

```bash
helm install alloy grafana/alloy -n logging
```

ConfigMap（关键片段）：

```hcl
// alloy.river
local.file_match "/var/log/pods/**/*.log" {
  sync_period = "10s"
}

loki.source.kubernetes "k8s" {
  targets    = [local.file_match.targets]
  forward_to = [loki.write.endpoint.receiver]
}

loki.write "endpoint" {
  endpoint {
    url = "http://loki.logging.svc:3100/loki/api/v1/push"
    tenant_id = "default"
  }
}
```

### 4.2 Promtail（仍可用，但建议迁到 Alloy）

```yaml
# ConfigMap
server:
  http_listen_port: 9080

positions:
  filename: /var/lib/promtail/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: kubernetes
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_label_app]
        target_label: app
      - source_labels: [__meta_kubernetes_namespace]
        target_label: namespace
      - source_labels: [__meta_kubernetes_pod_name]
        target_label: pod
      - source_labels: [__meta_kubernetes_pod_container_name]
        target_label: container
    pipeline_stages:
      - match:
          selector: '{job="kubernetes"}'
          stages:
            - regex:
                expression: '.*level=(?P<level>\w+).*'
            - labels:
                level:

limits_config:
  retention_period: 744h
```

### 4.3 其他采集器

| Agent | 适配 |
| --- | --- |
| **Fluent Bit** | 内置 `loki` output，资源轻 |
| **Vector** | `loki` sink，性能最强 |
| **OpenTelemetry Collector** | `loki` exporter |

---

## 五、LogQL 查询语言（核心）

### 5.1 三种向量

```logql
# 即时（instant）：返回最新一刻的流
{job="order-api"} |= "error"

# 范围（range）：时间窗口内的流
{job="order-api"} |= "error" [5m]

# 聚合：log metric（可参与 Grafana 绘图）
rate({job="order-api"} |= "error" [5m])
```

### 5.2 过滤操作符

| 操作符 | 含义 |
| --- | --- |
| `\|= "str"` | 行**包含** str（不分大小写） |
| `!= "str"` | 行**不包含** str |
| `\|~ "regex"` | 行**匹配** RE2 正则 |
| `!~ "regex"` | 行**不匹配** 正则 |

例：

```logql
# 错误日志
{job="order-api"} |= "ERROR"

# 5xx 响应
{job="order-api"} |~ "HTTP/1.1\" 5[0-9]{2}"

# 排除健康检查
{job="order-api"} != "/health"

# 多个条件
{job="order-api"} |= "ERROR" |~ "user_id=\\d+"
```

### 5.3 解析（pipeline stages）

把文本日志转成可聚合字段（**类似 PromQL 的 label extraction**）：

```logql
{job="nginx"} | regex `(?P<ip>\d+\.\d+\.\d+\.\d+) .* (?P<status>\d{3}) .*`
```

或者在 Promtail / Alloy 端用 pipeline 提取，**效果一样**。Loki 端用 `| line_format` / `| json` / `| regex` / `| label_format`。

### 5.4 聚合函数（把日志变成指标）

```logql
# 错误率
sum(rate({job="order-api"} |= "ERROR" [5m]))
  / sum(rate({job="order-api"}[5m]))

# 95 分位延迟（histogram_quantile 需要业务先打 bucket 字段）
quantile_over_time(0.95,
  {job="order-api"} | unwrap response_time_ms [5m]
)

# Top 10 报错 pod
topk(10,
  sum by (pod) (rate({job="order-api"} |= "ERROR" [5m]))
)
```

---

## 六、标签设计（最重要的最佳实践）

Loki 的**性能、存储、查询都强依赖标签**——标签不对等于白搭。

### 6.1 黄金规则

```text
✅ 低基数（cardinality ≤ 几十）：cluster / namespace / app / level / env / region
❌ 高基数（cardinality > 几千）：user_id / ip / request_id / email
```

> ⚠️ Loki **默认限制**：每行 stream 的标签组合 ≤ 15 万（`max_label_names_per_series`）。一旦爆，全集群写入失败。

### 6.2 推荐标签清单

```yaml
# 必带
cluster:     "prod-1"          # 多集群区分
namespace:   "payment"
app:         "order-api"
pod:         "order-api-7c5d-xxx"   # 容器级别排障用
container:   "main"

# 可选（按需）
env:         "production"
region:      "cn-east-1"
level:       "error|warn|info"        # 业务侧打
component:   "api|worker|cron"
```

### 6.3 反例

```logql
# ❌ 高基数
{user_id="12345"}                          # 几百万用户 → OOM
{request_id="abc-def-ghi"}                  # 每次请求一个值 → 爆炸
{ip="1.2.3.4"}                              # IP 海量

# ✅ 这些字段放进日志正文，不做标签
{job="order-api"} |= "user_id=12345"        # 全文搜即可
```

---

## 七、存储后端

### 7.1 对象存储（chunk 用）

| 后端 | 备注 |
| --- | --- |
| **AWS S3** | 标准选择 |
| **阿里云 OSS** | 国内首选，兼容 S3 协议 |
| **腾讯云 COS** | 兼容 S3 |
| **MinIO** | 自建兼容 S3（开发 / 边缘场景） |
| **Azure Blob** | 微软云 |
| **GCS** | GCP |
| **本地文件系统** | 单机 / 测试用，**生产不推荐**（无副本） |

### 7.2 Index 存储

| 后端 | 备注 |
| --- | --- |
| **TSDB（boltdb ships with Loki）** | Loki 2.7+ 推荐 |
| **Cassandra** | 老版本支持 |
| **Bigtable** | GCP |
| **DynamoDB** | AWS |

生产**用 TSDB** 即可，简洁。

### 7.3 容量估算

```text
日 1TB 日志 → 压缩后 ~200GB 对象存储
            → TSDB index ~50GB（按 50 个标签算）
            → WAL ~20GB × N ingester

30 天保留 ≈ 7TB 对象存储 + 1.5TB index + WAL
```

---

## 八、多租户

Loki 原生支持 multi-tenant：

```yaml
# 启用
loki:
  auth_enabled: true

# 写入时带 X-Scope-OrgID header
# Promtail：
clients:
  - url: http://loki:3100/loki/api/v1/push
    headers:
      X-Scope-OrgID: "team-payment"

# 查询 Grafana datasource 配置 tenant
```

每个 tenant 独立：
- 限速（ingestion / query）
- 保留期
- 配额

**生产场景**：
- 一个团队 → 一个 tenant
- 业务方不可见其他 tenant 数据

---

## 九、查询性能优化

### 9.1 Query Frontend 必备

挡大查询 / 拆 query / 缓存结果，**生产必开**：

```yaml
query_range:
  results_cache:
    cache:
      embedded_cache:
        enabled: true
        max_size_mb: 500
  parallelisme:
    parallel_worker_pool_size: 10
  split_queries_by_interval: 24h
```

### 9.2 限速保护

```yaml
limits_config:
  # 全局
  ingestion_rate_mb: 100
  ingestion_burst_size_mb: 200
  per_stream_rate_limit: 10MB
  per_stream_rate_limit_burst: 20MB
  max_query_parallelism: 32
  split_queries_by_interval: 30m
  reject_old_samples: true
  reject_old_samples_max_age: 168h    # 7 天
  creation_grace_period: 10m
```

### 9.3 索引优化

```yaml
storage_config:
  tsdb:
    dir: /data/loki/tsdb
    shipper:
      active_index_directory: /data/loki/tsdb-index
```

---

## 十、告警（Loki Ruler）

Loki 内置 Ruler 跑 LogQL 告警规则：

```yaml
# Loki ruler 配置
ruler:
  alertmanager_url: http://alertmanager:9093
  storage:
    type: local
    local:
      directory: /etc/loki/rules
  rule_path: /tmp/loki/rules
```

```yaml
# 规则文件
groups:
  - name: log-alerts
    rules:
      - alert: HighErrorRate
        expr: |
          sum(rate({job="order-api"} |= "ERROR" [5m]))
          / sum(rate({job="order-api"}[5m])) > 0.05
        for: 5m
        labels:
          severity: P1
        annotations:
          summary: "错误率 > 5%"
```

> 也可以从 Prometheus 端触发：PromQL 算 `loki_query_result` 指标 → alert。

---

## 十一、生产最佳实践

1. **微服务模式**：上 1k QPS 就别用 monolith，每角色 ≥ 3 副本
2. **对象存储必备**：本地盘 = 单点故障，OSS/S3/MinIO 集群
3. **标签严控低基数**：超过 50 cardinality 必出问题
4. **WAL 必开**：Ingester 故障 → 重启能从 WAL 恢复未 flush 数据
5. **Query Frontend 必备**：保护 Querier 不被打爆
6. **compactor 单实例 + 副本 1**：不能开 HA（会冲突）
7. **限速按租户配**：业务方多时一定要分 tenant，配额隔离
8. **保留期按价值分层**：debug 日志 7d、access log 30d、audit 180d+
9. **业务日志 JSON 化**：用 `| json` 解析；比 regex 快、稳、可读
10. **Grafana 用 Explore 调 LogQL**：所见即所得，跟 Prometheus 一致

---

## 十二、运维常用命令

```bash
# 看集群状态
curl http://loki:3100/ready
curl http://loki:3100/config?mode=diff

# 看 ring 状态（成员）
curl http://loki:3100/ring

# 查 ingester 内存压力
curl http://loki-distributor:3100/metrics | grep loki_ingester

# 查 metric：Loki 自己也吐 PromQL 指标
curl http://loki:3100/metrics | grep -E "loki_(ingester|distributor)"

# 强制 flush ingester（升级前）
curl -X POST http://loki-ingester:3100/flush

# 用 logcli（官方 CLI）
logcli query '{job="order-api"} |= "error"' --since=1h
logcli labels job
logcli series '{cluster="prod-1"}'

# Grafana → Explore 直接写 LogQL 更直观
```

---

## 十三、踩坑清单

| 现象 | 原因 |
| --- | --- |
| 写入报 429 | 租户 ingestion_rate 满，加限速或分流 |
| 查询超时 | 大查询未拆分；查时间窗口太大；用 `=` `\|~` 不带 stream selector |
| 标签基数爆炸 | 把 user_id / request_id 做标签了；立即改 |
| Ingester OOM | chunk 默认 1.5MB × streams 数太多；调 `chunk_target_size` |
| Querier 慢 | 没 Query Frontend；cache 没开 |
| Index 文件超大 | 标签组合多；定期跑 compactor |
| WAL 撑爆磁盘 | 没配磁盘容量监控；调低 `max_chunk_age` 加速 flush |
| 看不到日志但 status 是 ok | 时间窗口不对 / 时区错（UTC vs 本地） |
| 多集群数据混在一起 | tenant 没分；加 `X-Scope-OrgID` |
| Promtail 重启丢日志 | positions 文件没挂 PVC |

---

## 十四、Loki vs ELK 选型

| 维度 | Loki | E(L\|F)K |
| --- | --- | --- |
| 全文检索 | ⚠️ 慢（拉 chunk grep） | ✅ 强 |
| 标签查询 | ✅ 极快 | 一般（索引大） |
| 存储成本 | ✅ 低 5–10× | ❌ 高 |
| 运维复杂度 | ✅ 低（单二进制 + 对象存储） | ❌ 高（分片 / mapping / ILM） |
| 实时聚合 | ✅ LogQL 够用 | ✅ 更强 |
| 扩展性 | ✅ 水平扩展天然（无状态） | ⚠️ 索引瓶颈 |
| Kibana vs Grafana | Grafana 看 Prometheus / Trace / Logs 一体 | Kibana ES 体系最强 |
| 合规审计 | ⚠️（不擅长长期复杂查询） | ✅ |
| 适合场景 | K8s 日志 / 业务日志 / 大容量 | 金融合规 / 深度分析 / 全文搜 |

**决策口诀**：
- 全文搜是刚需 → **ELK**
- 成本 / 容量是痛点 → **Loki**
- 已经在用 Grafana → **Loki**（自然集成）
- 已经在用 Elastic 栈 → **ELK**

---

## 十五、参考

- [Loki 官方文档](https://grafana.com/docs/loki/latest/)
- [LogQL 查询语法](https://grafana.com/docs/loki/latest/logql/)
- [Loki Helm chart](https://github.com/grafana/helm-charts/tree/main/charts/loki)
- [Grafana Alloy](https://grafana.com/docs/alloy/latest/)
- [Loki Operator](https://github.com/grafana/loki-operator)
- [Production Best Practices](https://grafana.com/docs/loki/latest/best-practices/)
