# 云厂商监控体系对比

主要云厂商监控 / APM / 可观测性服务横向对比。

## 一、阿里云

### 1. 阿里云 ARMS（Application Real-Time Monitoring Service）

| 类别 | 组件 |
| ---- | ---- |
| **应用监控** | ARMS Application Monitoring（基于探针） |
| **前端监控** | ARMS 前端监控 / 浏览器 / 微信小程序 |
| **Prometheus 监控** | ARMS Prometheus / Alertmanager |
| **链路追踪** | ARMS Tracing（自研 + OpenTelemetry） |
| **业务监控** | 业务自定义事件 |
| **Grafana 数据源** | ARMS 自带 / 外接 Prometheus |

- **特点**：托管探针 / 集成阿里云生态（EDAS / SAE / ACK / 函数计算）
- **存储**：自研时序 + ES + Lindorm
- **告警**：短信 / 钉钉 / 邮件 / Webhook
- **集成**：PaaS 资源自动接入

### 2. 阿里云 CloudMonitor（云监控）

- 阿里云资源指标（ECS / RDS / OSS...）
- 站点 / 域名可用性拨测
- 跨账号 / 跨 Region 监控

### 3. 日志服务（SLS）

- 实时日志 / 阿里云生态（Logtail 采集）
- 全文索引 + 时序索引
- 在 SLS 与 ARMS 联通

## 二、腾讯云

### 1. CAT（Cloud Application Tracing）

- 腾讯云 APM
- 自动 / 手动埋点
- 业务监控 + 拓扑

### 2. CM（Cloud Monitor）

- 基础资源监控
- 服务可用性
- 拨测 / 告警

### 3. CLS（Cloud Log Service）

- 实时日志
- 与 CKafka、CDB 集成

### 4. Prometheus 监控服务

- 兼容开源 Prometheus
- 存放在腾讯云 TKE / 黑石
- 与 Grafana 集成

## 三、华为云

### 1. AOM（Application Operations Management）

- 应用运维监控
- 主机 / 容器 / 应用 / 中间件统一
- 业务告警

### 2. APM（Application Performance Monitoring）

- 应用性能
- 链路追踪
- 多语言探针

### 3. LTS（Log Tank Service）

- 日志服务
- 实时检索

### 4. CES（Cloud Eye Service）

- 资源监控
- 告警

## 四、AWS

### 1. CloudWatch（核心）

- 指标 / 日志 / 告警 / 仪表板
- Lambda 自动接入
- 部分代理指标需 CloudWatch Agent

### 2. X-Ray（Tracing）

- 链路追踪
- 服务图
- Lambda / ECS / API Gateway 自动接入

### 3. CloudTrail

- API 审计
- 安全事件

### 4. Managed Prometheus

- 兼容开源 Prometheus
- 集成 Grafana / Alertmanager
- 基于 Amazon Managed Service for Prometheus (AMP)

### 5. Managed Grafana

- Grafana 托管
- 集成 CloudWatch / X-Ray / AMP

### 6. OpenSearch Service

- Elasticsearch 替代
- 日志分析 / 仪表板
- 与 CloudWatch Logs 集成

### 7. Datadog（合作伙伴）

- SaaS APM
- 与 CloudWatch 集成
- 三方：Sumo Logic / New Relic / Splunk

## 五、GCP

### 1. Cloud Monitoring（前 Stackdriver）

- 指标 / 仪表板 / 告警
- 自动上报 GCP 资源
- 自定义 metric API

### 2. Cloud Logging

- 日志采集 / 检索
- Log Router → BigQuery / GCS / Pub/Sub

### 3. Cloud Trace

- 链路追踪
- 关联日志、错误报告

### 4. Cloud Profiler / Debugger

- 持续剖析 / 调试
- 对 Java / Go / Python / Node.js 原生

### 5. Cloud Composer

- 托管 Airflow
- 适合 GCP 上跑 ETL

### 6. Error Reporting

- 错误聚合
- 集成 Cloud Logging

### 7. Managed Service for Prometheus

- 托管 Prometheus

## 六、Azure

### 1. Azure Monitor（核心）

- Metric / Log Analytics
- 告警
- 与 Log Analytics Workspace 集成

### 2. Application Insights

- APM
- Distributed Tracing
- Web Test / Snapshot Debugger

### 3. Log Analytics

- KQL 查询
- Log Retention Policy

### 4. Container Insights

- AKS 监控

### 5. Network Watcher

- 网络诊断

### 6. Managed Prometheus / Grafana

- 集成 Azure Monitor

## 七、横向对比

### 1. 实时指标

| 厂商 | 服务 | 兼容性 |
| ---- | ---- | ------ |
| AWS | CloudWatch / Managed Prometheus | CW 标准 / Prometheus API |
| GCP | Cloud Monitoring | GCP Metric + 自定义 |
| Azure | Azure Monitor | KQL / 自定义 |
| 阿里云 | CloudMonitor / ARMS Prometheus | Prometheus API |
| 腾讯云 | CM / Prometheus 监控服务 | Prometheus API |
| 华为云 | CES / AOM | OpenMetrics |

### 2. 链路追踪

| 厂商 | 服务 | 协议 |
| ---- | ---- | ---- |
| AWS | X-Ray | X-Ray + OTLP |
| GCP | Cloud Trace | OTLP |
| Azure | App Insights | AppInsights + OTLP |
| 阿里云 | ARMS Tracing | ARMS 自定义 + OTLP |
| 腾讯云 | CAT | 自定义 + OTLP |
| 华为云 | APM | 自定义 + OTLP |

### 3. 日志

| 厂商 | 服务 | 特点 |
| ---- | ---- | ---- |
| AWS | CloudWatch Logs / OpenSearch | 内置 / ELK 替代 |
| GCP | Cloud Logging | 与 BigQuery 集成 |
| Azure | Log Analytics | KQL 强 |
| 阿里云 | SLS | Logtail 强 |
| 腾讯云 | CLS | 与 Kafka 集成 |
| 华为云 | LTS | 适配应用日志 |

### 4. APM / RUM

| 厂商 | 服务 |
| ---- | ---- |
| AWS | CloudWatch RUM / X-Ray / RDS |
| GCP | Error Reporting / Browser RUM |
| Azure | App Insights（前端 + 后端） |
| 阿里云 | ARMS 前端 + 应用监控 |
| 腾讯云 | CAT / RUM |
| 华为云 | APM |

### 5. 持续剖析

| 厂商 | 服务 |
| ---- | ---- |
| GCP | Cloud Profiler |
| AWS | CodeGuru Profiler |
| Azure | Snapshot Debugger |
| 阿里云 | ARMS Profiling（v10+） |
| 其余 | 借助 Pyroscope OSS |

### 6. Synthetics / 拨测

| 厂商 | 服务 |
| ---- | ---- |
| 阿里云 | CloudMonitor 拨测 |
| AWS | CloudWatch Synthetics |
| GCP | Uptime Checks |
| Azure | Web Test |

## 八、托管 vs 自建的边界

| 场景 | 建议 |
| ---- | ---- |
| 上云业务 vs 云资源使用 | 完全托管（CloudWatch / Cloud Monitor） |
| 多云或混合云 | 自建 OpenTelemetry + Grafana + Prometheus + Loki + Tempo |
| 跨云分析 | 统一走自建 OLAP / 国产 FlashDuty 等 SaaS |
| 国产合规 | 阿里 / 腾讯 / 华为 私有化部署 |

## 九、自托管开源 + 云厂商采集

常见组合：

- **OTel SDK** → 厂商收集端 / 自建 OTLP Collector
- **Prometheus Exporter** → 厂商 Managed Prometheus
- **Trace** → 商业 Trace 平台（保留 Secret 数据）
- **Log** → CloudWatch / SLS / Log Analytics

## 十、混合架构建议

```text
                          ┌───────────────┐
                          │ SaaS 仪表板   │
                          └─────┬─────────┘
                                │
        ┌───────────────────────┼─────────────────────────┐
        │                       │                         │
   Vendor A            Vendor B  （双云）            Open Telemetry Server
 CloudWatch             CloudMonitor             Prometheus + Loki + Tempo
 AppInsights            ARMS / CAT / AOM
        ▲                       ▲                         ▲
        │ OTLP / SDK / API / SDK / Agent              OTLP
        │                       │
      业务服务 A                业务服务 B
   （跨厂商部署）             （跨厂商部署）
```

- 一次埋点，多云上报
- 用 OpenTelemetry Collector 做中转

## 十一、各云厂商 APM 商业化深度对比

| 服务 | 优点 | 缺点 |
| ---- | ---- | ---- |
| **AWS CloudWatch + X-Ray** | 与 AWS 集成深 | 锁定 AWS |
| **GCP Cloud Operations** | 与 GCP 集成深 | 锁定 GCP |
| **Azure App Insights** | 易用，.NET 集成 | KQL 学习成本 |
| **阿里云 ARMS** | 中文友好 / 阿里生态 | 锁定阿里云 |
| **Datadog / New Relic** | 多云 / 多语言 | 贵 |

## 十二、国产替代

- **闪测 (FlashDuty)**：告警中心 + APM
- **博睿 / Bonree**、听云：APM
- **听云 Network**、**听云 Server**、**听云 App**、**听云 Browser**：全栈 APM
- **OneAPM**：APM
- **华为 AOM / APM / LTS**：华为系
- **虎符 IM / 钉钉 IM**：作为告警通道

## 十三、选择策略

| 维度 | 建议 |
| ---- | ---- |
| 单云 + 主力云 | 直接用云厂商监控 |
| 多云 | 抽象一层 OpenTelemetry + 自建 |
| 国产替代 / 安全 | 闪测 + 阿里 / 腾讯 / 华为 |
| 高合规 / 自建 | OSS: Prometheus / Loki / Tempo + Grafana |

## 十四、常见误区

- 误把 CloudWatch 当 RUM → 需要用 RUM 专用服务
- 把 OpenTelemetry 当 vendor 库 → 它是标准
- 用云厂商 + 自建混合不互通 → 用 OTLP 统一
- 跨云追踪 → trace context (W3C) 必须贯穿
- 时序业务指标 → 通常用云厂商托管 Prometheus

## 十五、未来趋势

- **大模型 AIOps**：异常检测（阿里云 / Datadog / BigPanda / FlashDuty AI）
- **一体化 APM**：让云厂商监控 + AI = 全栈洞察
- **统一 OpenTelemetry**：标准最终统一各家
- **SaaS 走向多云**：Datadog / Grafana Cloud 跨云观测
- **商业 + Open Source**：开源保持性能 / 商业提供集成
