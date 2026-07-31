# ELK Stack

Elasticsearch + Logstash + Kibana（早期三件套），加 Beats（Filebeat / Metricbeat / Packetbeat / Auditbeat / Heartbeat）组成 Elastic Stack。

## 一、定位

- 全文检索 + 日志分析 + 业务监控 + APM
- Elasticsearch 是核心，组件高度解耦
- 商业能力：Security / Alerting / SIEM / Observability 等高级特性

## 二、组件

### 1. Elasticsearch

```text
Master node     ── 负责 Cluster State
Data node       ── 存数据 / 索引
Ingest node     ── 预处理
Coordinating    ── 接收请求并分发
ML node         ── 机器学习
Transform node  ── 数据聚合
```

特点：

- 分布式：自平衡 / 容错
- 数据模型：Index（DB）→ Document（JSON）→ Field
- 倒排索引 + segment
- 实时查询（refresh_interval 控制可见性）
- 可选 Cross-cluster search

### 2. Logstash / Beats

| 组件 | 用途 |
| ---- | ---- |
| **Logstash** | 服务端聚合、处理、转换、转发 |
| **Filebeat** | 轻量日志采集（替代 Logstash Forwarder） |
| **Metricbeat** | 主机 / 应用指标 |
| **Packetbeat** | 网络流量 |
| **Heartbeat** | 拨测 |
| **Auditbeat** | 审计日志 |
| **Winlogbeat** | Windows 日志 |

新版本倾向 Beats + Elasticsearch Ingest Pipeline，弱化 Logstash。

### 3. Kibana

可视化、仪表板、Canvas、Graph、APM、Security、Alerting、Dev Tools。

### 4. 数据流（Data Streams）

ES 7.10+ 新概念，为时序数据优化的存储方式：

- 自动 ILM（生命周期）
- 自动 rollover
- 区别于 Index API

## 三、数据模型

### 1. 文档

```json
{
  "@timestamp": "2024-01-01T00:00:00Z",
  "level": "INFO",
  "service": "api",
  "message": "request /orders 200",
  "trace_id": "abc..."
}
```

### 2. Mapping

```json
{
  "mappings": {
    "properties": {
      "level": {"type": "keyword"},
      "service": {"type": "keyword"},
      "message": {"type": "text"},
      "trace_id": {"type": "keyword"}
    }
  }
}
```

- `text` 全文索引 + 倒排
- `keyword` 不分词用于聚合
- `date` 字段 `@timestamp`
- 字段类型自动推断（dynamic mapping）

### 3. Index Template

```json
{
  "index_patterns": ["logs-*"],
  "template": {
    "settings": {...},
    "mappings": {...}
  }
}
```

按模式自动套用。

## 四、ILM（Index Lifecycle Management）

```text
Hot    ── 高性能索引，允许写入 / 查询
        ↓（达到阈值）
Warm   ── 不可写，少查询
        ↓（再次达到）
Cold   ── 不可写，更少查询（可挂对象存储）
        ↓
Delete ── 删除
```

策略：

```json
{
  "policy": {
    "phases": {
      "hot": {"min_age": "0ms", "actions": {"rollover": {"max_age": "1d"}}},
      "warm": {"min_age": "7d", "actions": {"shrink": {"number_of_shards": 1}, "forcemerge": {"max_num_segments": 1}}},
      "delete": {"min_age": "30d", "actions": {"delete": {}}}
    }
  }
}
```

## 五、查询

### 1. URI 查询

```text
GET /logs-*/_search?q=service:api
```

### 2. DSL（推荐）

```json
{
  "query": {
    "bool": {
      "must": [
        {"match": {"message": "error"}}
      ],
      "filter": [
        {"term": {"service": "api"}},
        {"range": {"@timestamp": {"gte": "now-1h"}}}
      ]
    }
  },
  "aggs": {
    "by_status": {"terms": {"field": "status"}}
  }
}
```

### 3. KQL（Kibana Query Language）

```text
service:api AND status:5*
```

## 六、聚合分析

```json
{
  "aggs": {
    "by_service": {
      "terms": {"field": "service", "size": 10},
      "aggs": {
        "errors": {"filter": {"term": {"level": "ERROR"}}}
      }
    },
    "p99": {
      "percentiles": {"field": "duration", "percents": [50, 95, 99]}
    }
  }
}
```

常用：date_histogram / terms / histogram / range / avg / sum / cardinality

## 七、Beats 部署

### 1. Filebeat

```yaml
filebeat.inputs:
  - type: log
    paths:
      - /var/log/app/*.log
    json.keys_under_root: true
    fields:
      service: api
output.elasticsearch:
  hosts: ["http://es:9200"]
  index: "logs-api-%{+yyyy.MM.dd}"
setup.ilm.enabled: false
setup.template.name: "logs"
setup.template.pattern: "logs-*"
```

### 2. Metricbeat

采集主机 / 应用指标，导入 ES，作为 metrics 替代方案。

### 3. Heartbeat（拨测）

配置 HTTP / TCP / ICMP 探测。

### 4. Logstash Pipeline

```text
input { beats { port => 5044 } }
filter {
  grok { match => { "message" => "%{COMMONAPACHELOG}" } }
  geoip { source => "client_ip" }
}
output { elasticsearch { ... } }
```

## 八、Logstash Pipeline 模式

```text
input
  ↓
filter
  ↓
output
```

- `grok`、`date`、`kv`、`json`、`ruby`、`mutate`
- 持久化队列：`queue.type: persisted`
- Pipeline-to-pipeline：分阶段 pipeline

## 九、Alerting / Anomaly Detection

- 内置 Alerting rule
- Threshold / Anomaly detection / Elasticsearch query
- 通知 Channel：Email / Slack / PagerDuty / Webhook
- Stack alerts：threshold breach、anomaly score

## 十、APM Server + Kibana APM

Kibana 内置 APM：

```text
App Agent (Node/Java/Python/Go/Ruby/.NET)
   │
   ▼
APM Server（聚合 + 校验）
   │
   ▼
Elasticsearch（apm-* 索引）
   │
   ▼
Kibana APM UI
```

- Distributed Tracing
- Service Map
- Service / Transaction / Span
- Metrics / 错误

## 十一、安全

- X-Pack Basic 默认免费
- Platinum / Enterprise 含 Security / Machine Learning / 跨集群
- 字段级 / 文档级 RBAC
- 加密：节点间 TLS、客户端 / 服务器端
- 跨集群设置 Cross-cluster replication

## 十二、Elastic Observability 套件（Stack Monitoring）

- Stack Monitoring module
- Log rate / 索引延迟 / JVM / GC
- APM / 主机 / 集群 / 索引状态

## 十三、集群架构

### 1. 节点角色

| 角色 | 责任 |
| ---- | ---- |
| master | 集群状态 |
| data | 存数据 |
| data_hot | hot tier |
| data_warm | warm tier |
| data_cold | cold tier |
| ingest | 预处理 |
| ml | 机器学习 |
| remote_cluster_client | 跨集群 |
| coordinating | 默认 |

### 2. 分片与副本

- Primary Shard：写主要
- Replica Shard：复制
- Shard 大小建议 10–50 GB

### 3. Snapshot / Restore

- S3 / OSS / HDFS / FS 仓库
- 定期 snapshot 备灾

## 十四、ILM + 数据流最佳实践

| 日志类型 | 保留 |
| -------- | ---- |
| 应用日志 | hot 3d / warm 30d / delete 90d |
| 业务日志 | hot 7d / warm 30d / delete 365d |
| 审计日志 | 长期，热冷分层，压缩 |
| Trace | 7~14d 后冷存或删 |

## 十五、典型痛点

- `mapping conflict`：动态 mapping 后字段类型不一致 → 用 index template 强制
- 写入瓶颈：bulk 过大 / refresh_interval 太频繁
- 查询慢：深分页（from+size），用 `search_after` / PIT 改造
- 内存压力：聚合 / text 高基数

## 十六、与 Loki / ClickHouse 对比

| 维度 | ELK | Loki | ClickHouse |
| ---- | --- | ---- | ---------- |
| 检索 | 强（全文 + 聚合） | 中（label + grep） | 强（SQL） |
| 容量成本 | 高 | 低 | 低 |
| 全文 | 强 | 中 | 中（ngram） |
| 聚合 | 强 | 中 | 极强 |
| 适合 | 复杂日志检索 | K8s 大规模 | 海量低成本 |

## 十七、最佳实践

- **Index Template 标准化**
- **Ingest Pipeline 减少 Logstash 依赖**
- **Beats + ES 直传 减少中间环节**
- **ILM 分层 控成本**
- **冷数据 走对象存储（Cold Tier）**
- **监控自身**：Stack Monitoring
- **避免 text 高基数**：keyword 化
- **定期 mapping review**
- **RBAC + 字段级安全**（商业）
