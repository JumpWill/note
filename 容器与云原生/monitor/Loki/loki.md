# Loki 笔记

## 一、Loki 简介

Loki 是 Grafana Labs 开源的 **云原生日志聚合系统**,由 Prometheus 团队(同款作者)打造。它的设计哲学与 Elasticsearch 等传统日志系统截然不同:

> **Loki: Like Prometheus, but for logs.**

### 核心设计理念

- **不索引日志内容,只索引标签**:Loki 不像 ELK 那样对全文建倒排索引,而是只对日志的 **labels**(标签)建立索引。日志内容则被压缩后按块(chunk)存储。
- **成本低**:因为不索引文本,存储和计算成本都远低于 ES。
- **与 Prometheus 统一**:同一套标签体系,可以在 Grafana 中无缝关联指标和日志。
- **水平扩展**:无状态组件 + 对象存储 + 一致性哈希,天然适合云原生环境。

### Loki vs ELK

| 维度 | Loki | ELK(Elasticsearch) |
| --- | --- | --- |
| 索引方式 | 只索引 label | 全文倒排索引 |
| 存储成本 | 低(对象存储 + 压缩) | 高(本地 SSD + 副本) |
| 全文检索 | 弱(需要 grep 风格过滤) | 强 |
| 适合场景 | 已结构化的日志(JSON、按行 k=v) | 非结构化全文检索 |
| 复杂度 | 较低(组件少) | 较高(JVM、索引调优) |

---

## 二、Loki 架构

Loki 采用 **读写分离** 的架构,主要由两大部分组成:

### 整体架构图(简化)

```text
┌──────────────┐    ┌──────────────────────────────────────────┐
│  Log Sources │    │               Loki Cluster               │
│ (Promtail /  │    │                                          │
│  Grafana     │──▶│  ┌────────────┐    ┌──────────────┐     │
│  Agent /     │    │  │ Distributor│───▶│   Ingester    │     │
│  Fluent Bit) │    │  └────────────┘    └──────────────┘     │
└──────────────┘    │                          │               │
                    │                          ▼               │
                    │                  ┌──────────────┐        │
                    │                  │ Object Store │        │
                    │                  │ (S3/GCS/...) │        │
                    │                  └──────────────┘        │
                    │                          ▲               │
                    │  ┌────────────┐    ┌──────────────┐     │
                    │  │ Querier /  │───▶│   Query      │     │
                    │  │ Query Frontend    │  Frontend    │     │
                    │  └────────────┘    └──────────────┘     │
                    └──────────────────────────────────────────┘
                                          │
                                          ▼
                                    ┌──────────┐
                                    │ Grafana  │
                                    └──────────┘
```

### 写路径(Write Path)

1. **客户端**(Promtail/Fluentbit/Agent)通过 HTTP/POST 把日志推送到 Loki。
2. **Distributor**(无状态):接收日志,根据一致性哈希 + 租户信息,把它路由到正确的 Ingester。
3. **Ingester**(有状态):把日志流 **组装成 chunk**(默认 4h 一个),写入临时存储(内存 + 后台 flush),并定期把 chunk 写入对象存储(S3/GCS/Azure Blob/本地文件系统)。
4. **Compactor**:后台任务,负责把 chunk 合并、去重、清理过期数据。

### 读路径(Read Path)

1. **Query Frontend**(可选):查询调度、并行切分、缓存、限流。
2. **Querier**(无状态):收到 LogQL 查询后,根据标签索引找到对应的 chunk,从对象存储拉取 chunk,执行 LogQL 表达式。
3. **结果合并**:多 Querier 节点的结果由 Query Frontend 合并后返回。

---

## 三、核心组件

| 组件 | 作用 | 是否无状态 | 是否必须 |
| --- | --- | --- | --- |
| Distributor | 写入路由、租户限流 | 是 | 是 |
| Ingester | 日志流聚合、chunk 写入 | 否(有 WAL) | 是 |
| Querier | LogQL 查询执行 | 是 | 是 |
| Query Frontend | 查询调度、并行、缓存 | 是 | 否(但强烈推荐) |
| Compactor | 索引合并、过期数据清理 | 否(单实例) | 否(单机部署可省略) |
| Index Gateway | 索引查询(在 simple scalable 中) | 否 | 否 |
| Query Scheduler | 查询队列调度 | 否 | 否 |
| Ruler | Loki 自身的告警/Recording 规则 | 否 | 否(可由 Grafana 替代) |
| Store Gateway | 读取 TSDB 索引 | 否 | 否(微服务模式) |

### 关键概念

- **Chunk**:Loki 存储日志的最小物理单位,默认 4 小时一个,采用 gzip 压缩。
- **Stream**:一组具有相同 label 集合的日志序列。
- **Tenant(租户)**:多租户隔离的基础,每个请求 header `X-Scope-OrgID` 区分。
- **Index**:Loki 用 BoltDB/TSDB 来索引 label→chunk 的映射关系。
- **WAL(Write-Ahead Log)**:Ingester 在 chunk 持久化前,本地 WAL 用于崩溃恢复。

---

## 四、部署模式

### 1. Single Binary(单机模式)

适合开发测试,所有组件跑在一个进程里:

```bash
./loki -config.file=loki-config.yaml
```

### 2. Simple Scalable(推荐入门)

读写分离,可水平扩展:

- **Read 路径**:Query Frontend + Querier + Index Gateway
- **Write 路径**:Distributor + Ingester
- **后端服务**:Compactor(单实例)+ Object Storage

### 3. Microservices(生产大规模)

按组件分别部署,适合百万级日志/秒的场景:

```yaml
# 伪 helm values
ingester:
  replicas: 3
querier:
  replicas: 5
distributor:
  replicas: 3
queryFrontend:
  replicas: 2
compactor:
  replicas: 1
```

---

## 五、存储后端

### 1. 对象存储(Chunks)

Loki 把压缩后的 chunk 写入对象存储,支持:

- AWS S3 / S3-compatible(MinIO、Ceph)
- Google Cloud Storage
- Azure Blob Storage
- 阿里云 OSS / 腾讯云 COS
- 本地文件系统(仅测试)

### 2. 索引存储

- **BoltDB**(单机模式):索引存本地文件
- **TSDB**(微服务模式):Loki 2.0+ 推荐,把索引也写入对象存储,Scalability 大幅提升

### 3. 推荐生产配置

```yaml
storage_config:
  aws:
    s3: s3://<region>.amazonaws.com/<bucket>
    s3forcepathstyle: true
  boltdb_shipper:
    active_index_directory: /data/loki/index
    cache_location: /data/loki/index_cache
    shared_store: s3
schema_config:
  configs:
    - from: 2024-01-01
      store: tsdb
      object_store: s3
      schema: v13
      index:
        prefix: index_
        period: 24h
```

---

## 六、关键配置详解

### 1. 限制并发与速率

```yaml
limits_config:
  # 每租户写入速率(B/s)
  ingestion_rate_mb: 10
  # 每租户最大并行查询数
  max_query_parallelism: 32
  # 单条日志最大长度
  max_line_size: 256KB
  # 单次查询返回最大行数
  max_entries_limit_per_query: 5000
  # 拒绝采样
  reject_old_samples: true
  reject_old_samples_max_age: 168h
```

### 2. 标签校验

```yaml
limits_config:
  # 强制 label 名称规范,避免 cardinality 爆炸
  allow_structured_metadata: true
  # 限制每条日志的结构化元数据 key 数量
  max_structured_metadata_entries_count: 128
```

### 3. 缓存(Redis/Memcached)

```yaml
query_range:
  results_cache:
    cache:
      redis:
        endpoint: redis:6379
        expiration: 1h
```

---

## 七、与采集端集成

### 1. Promtail(已弃用,推荐 Grafana Agent)

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

### 2. Grafana Agent(Flow 模式)

`river` 配置:

```river
loki.source.file "app" {
  targets = [
    {__path__ = "/var/log/app/*.log", job = "app"},
  ]
  forward_to = [loki.write.endpoint.receiver]
}

loki.write "endpoint" {
  endpoint {
    url = "http://loki:3100/loki/api/v1/push"
  }
}
```

### 3. Kubernetes 自动采集

用 Loki Helm Chart 自带的 `promtail` DaemonSet,自动打上 pod/container/node 标签:

```yaml
# 自动生成的 label 示例
{app="myapp", container="nginx", namespace="prod", pod="myapp-7d8f", instance="node-1"}
```

---

## 八、LogQL 查询示例

详见同目录下 [LogQL.md](./LogQL.md),下面给一些高级用法:

### 1. 计算 QPS + 错误率

```logql
sum(rate({job="nginx"}[5m]))
sum(rate({job="nginx"} | json | status=~"5.." [5m])) by (status)
```

### 2. 计算 P99 响应时间

```logql
quantile_over_time(0.99,
  {job="api"} | json | unwrap duration [5m]
) by (path)
```

### 3. 关联 TraceID 与日志

```logql
{app="checkout"} | json | trace_id="abc123"
```

---

## 九、运维与最佳实践

### 1. Label 规范(极其重要)

- ✅ 推荐的 label:`app`、`env`、`cluster`、`region`、`pod`、`container`
- ❌ 避免的 label:用户 ID、IP、URL、TraceID(应放结构化元数据或日志内容)
- 经验法则:**每条流每分钟写入日志 < 10 条**

### 2. Cardinality 控制

Loki 对标签 cardinality 极其敏感:

```yaml
# 限制每条流的标签 cardinality
limits_config:
  max_label_names_per_series: 30
  max_label_name_length: 64
  max_label_value_length: 2048
```

### 3. Retention(数据保留)

Loki 通过 **Compactor** 删除过期数据:

```yaml
compactor:
  working_directory: /data/loki/compactor
  compaction_interval: 10m
  retention_enabled: true
  retention_delete_delay: 2h
  delete_request_store: filesystem

limits_config:
  retention_period: 744h  # 31 天
```

### 4. 监控 Loki 自身

Loki 通过 `/metrics` 暴露 Prometheus 指标,关键指标:

| 指标 | 含义 |
| --- | --- |
| `loki_distributor_lines_received_total` | 接收日志行数 |
| `loki_ingester_chunks_created_total` | 生成的 chunk 数 |
| `loki_ingester_memory_streams` | 内存中的活跃流 |
| `loki_ingester_wal_bytes_flushed` | WAL flush 数据量 |
| `loki_request_duration_seconds_bucket` | 请求耗时分布 |
| `loki_query_frontend_queue_duration_seconds_bucket` | 查询队列等待时间 |

推荐使用 Grafana 官方 Dashboard `Loki / 编写日志 / 1.0`。

### 5. 故障排查

| 现象 | 可能原因 | 排查方向 |
| --- | --- | --- |
| 写入 429 | 超过 ingestion_rate_mb | 提高 limits,或优化日志量 |
| 查询超时 | chunk 过多或范围过大 | 缩小时间窗口,加大 max_query_parallelism |
| 内存 OOM | 流数过多 | 检查 label cardinality |
| 索引损坏 | 不正常关机 | 重启 Compactor 重建索引 |
| 时间戳错乱 | 客户端时间与服务器不一致 | 统一 NTP 同步 |

---

## 十、与 OpenTelemetry 集成

Loki 2.0+ 支持通过 OTLP 协议接收日志:

```yaml
# loki 配置
server:
  http_listen_port: 3100
  grpc_listen_port: 9096

# OpenTelemetry Collector 配置
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317

exporters:
  otlphttp/loki:
    endpoint: http://loki:3100/otlp
    tls:
      insecure: true
```

Loki 会自动把 OTLP `resource.attributes` 转成 label,把 `log.record.attributes` 转成结构化元数据。

---

## 十一、常见架构方案

### 1. 中小规模(< 50GB/天)

```text
Promtail → Loki(Simple Scalable) → Grafana
                ↓
            MinIO / S3
```

### 2. 大规模(> 500GB/天)

```text
应用/Pod
   ↓
Grafana Agent(Cluster 模式)
   ↓
Loki(Microservices)
 ├─ Distributor × N
 ├─ Ingester × N(挂载 NVMe WAL)
 ├─ Querier × N
 ├─ Query Frontend × N
 └─ Compactor × 1
       ↓
   S3/GCS + TSDB 索引
```

### 3. 混合云/多区域

- 每个区域部署独立 Loki
- 通过 Grafana 数据源 Federation 或 Mimir 统一展示
- 或使用 Loki 的 **multi-tenancy** 模式把不同业务当作不同租户

---

## 十二、参考资料

- [Loki 官方文档](https://grafana.com/docs/loki/latest/)
- [Loki 架构白皮书](https://grafana.com/docs/loki/latest/fundamentals/architecture/)
- [Loki Helm Chart](https://github.com/grafana/loki/tree/main/production/helm)
- [Awesome Loki](https://github.com/yingqiW/awesome-loki)
- [Loki 性能调优最佳实践](https://grafana.com/blog/2023/04/03/how-to-scale-loki/)
- 同目录 [LogQL.md](./LogQL.md) — LogQL 语法详解
