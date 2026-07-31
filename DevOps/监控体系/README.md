# 监控体系

按工具分文件整理监控 / 可观测性原理与使用。

## 分类与索引

按可观测性三大支柱加上扩展维度：

| 分类 | 工具 |
| --- | --- |
| **指标 (Metrics)** | [Prometheus](prometheus.md)、InfluxDB、VictoriaMetrics、OpenObserve |
| **可视化** | [Grafana](grafana.md) |
| **日志 (Logs)** | [ELK Stack](elk.md)、[Loki + Promtail/Alloy](loki.md)、ClickHouse+Vector |
| **追踪 (Traces / APM)** | [Jaeger / OpenTelemetry Collector](jaeger.md)、[Apache SkyWalking](skywalking.md)、[Grafana Tempo](tempo.md)、Zipkin |
| **遥测框架** | [OpenTelemetry](otel.md) |
| **持续剖析 (Profiling)** | [Pyroscope](pyroscope.md)、Parca、async-profiler |
| **错误监控 (RUM / Error)** | [Sentry](sentry.md) |
| **eBPF 内核观测** | [Pixie / Tetragon / Falco](ebpf.md) |
| **云厂商托管** | [阿里云 / AWS / GCP / Azure](cloud-monitoring.md) |

## 可观测性三大支柱

```text
        Logs（日志）
       /
  Metrics ── Traces
 (指标)      (追踪)
```

| 维度 | 内容 | 工具 |
| ---- | ---- | ---- |
| Metrics | 时间序列数值（CPU / Latency / QPS） | Prometheus / InfluxDB / CloudWatch |
| Logs | 离散文本事件 | Loki / Elasticsearch |
| Traces | 请求调用链 | Jaeger / SkyWalking / Tempo / OpenTelemetry |

现代系统增加：

- **Profiles**（连续剖析）：CPU / Memory 火焰图 → Pyroscope / Parca
- **RUM**（真实用户监控）：前端 / 移动端体验 → Sentry / DataDog RUM
- **eBPF**（内核观测）：syscall / 网络 / 安全 → Pixie / Tetragon / Falco
- **AIOps / RCA**：根因分析、日志聚类 → FlashDuty / Moogsoft

## 选型速查

| 场景 | 建议 |
| --- | --- |
| 容器化 K8s 监控 | Prometheus + Grafana + Loki + Tempo |
| 大数据离线分析 | ELK (Elasticsearch) |
| 持续剖析 | Pyroscope + Grafana |
| 前端报错捕获 | Sentry |
| 内核安全 / 网络观测 | Cilium Tetragon / Falco |
| 一体化 APM | SkyWalking / Pinpoint |
| 不想运维 | 云厂商托管（ARMS / Datadog / NewRelic） |
| 多云中立 | Grafana Cloud / OSS 工具链 |

## 概念对比

### 指标存储

| 工具 | 存储模型 | 写入方式 | 数据压缩 | 适合规模 |
| --- | --- | --- | --- | --- |
| **Prometheus** | 自研 TSDB（按 block） | Pull 为主，remote_write 写入 | Gorilla + Delta-of-delta | 中小集群（百万 series） |
| **InfluxDB** | TSM | Push / Line Protocol | TSM | 边缘 / IoT |
| **VictoriaMetrics** | 自研 TSDB（merge） | remote_write | 高压缩 | 超大规模（10 亿 series） |
| **TimescaleDB** | PostgreSQL 扩展 | SQL | Hypertable | 关系型混部 |
| **OpenObserve** | 自研列存 | Push | 高压缩 | 替代 ES/Loki 一体化 |

### 日志存储

| 工具 | 存储 | 检索 | 适合 |
| --- | --- | --- | --- |
| **Elasticsearch** | 倒排索引 | Lucene Query DSL、聚合 | 复杂日志分析 |
| **Loki** | 对象存储 + 索引 | LogQL | K8s 大规模低成本 |
| **ClickHouse** | 列存 OLAP | SQL | 海量低成本分析 |
| **Meilisearch** | 倒排索引 | 简单 | 搜索式 |

### 追踪后端

| 工具 | 协议 | 存储 | 采样 | 适合 |
| --- | --- | --- | --- | --- |
| **Jaeger** | OpenTelemetry / Zipkin | ES / Kafka / Cassandra | 自适应 | K8s 主流 |
| **Zipkin** | Zipkin 协议 | Cassandra / ES | 一致概率采样 | 老牌 |
| **SkyWalking** | SW 协议 + OTEL | ES / H2 / MySQL / TiDB | 多种策略 | 一体化 APM |
| **Tempo** | OTLP | 对象存储（GCS / S3） | 全量（但便宜） | Grafana 配套 |
| **Pinpoint** | Thrift | HBase | 树结构 | Java APM 深入 |

### 告警中心

| 工具 | 输入 | 通道 | 优势 |
| --- | --- | --- | --- |
| **Alertmanager** | Prometheus | 路由分组，Slack / PagerDuty | 开源主流 |
| **Grafana Alerting** | 任意数据源 | 通知渠道多 | 与面板共用 |
| **FlashDuty**（国产） | 多源 | 集成国产 IM | 中文运营 |
| **PagerDuty** / **OpsGenie** | 多源 | 国际 IM / 呼叫 | SaaS 强 |
| **PagerTree** | 多源 | 低代码 | 小团队 |

## 选型要点

- **Metrics 选型**：规模 < 100 万 series 用 Prometheus；超出选 VictoriaMetrics；IoT 边缘用 InfluxDB
- **Logs 选型**：复杂查询选 ES / ClickHouse；K8s、低成本选 Loki
- **Traces 选型**：语言异构 + K8s 选 Jaeger + OTEL；Java 深 APM 选 SkyWalking / Pinpoint；Grafana 全套选 Tempo
- **告警收敛**：避免告警风暴，要路由 + 分组 + 抑制
- **统一关联**：traceId / requestId 贯穿 Logs/Metrics/Traces
- **采集统一**：OpenTelemetry 一份 instrument，输出给多个后端
- **长期存储**：Prometheus TSDB 长期成本高 → 用 Thanos / Cortex / Mimir / VictoriaMetrics Cluster
- **APM 商业**：不想自建考虑 Datadog / NewRelic / 阿里云 ARMS
