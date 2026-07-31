# 观测类控制台

可观测性三大支柱（Metrics / Logs / Traces）在 K8s 上落地后，会自然形成一组「给运维 / SRE 看的控制台」。本文只讲这些工具作为「控制台 / 交互层」的角色与组合方式，深入原理参见同仓库 `/DevOps/监控体系/` 目录。

## 一、定位

- 指标 / 日志 / 追踪 / 事件 / 容量等数据需要一套可视化与告警界面
- 「事实上的运维控制台」通常是 Grafana + Prometheus + Alertmanager
- 服务网格场景下 Kiali 是必看控制台
- 单独看 trace 用 Jaeger UI / Tempo
- 单独看事件用 kubectl events / BotKube / Robusta
- 它们共同组成「控制台矩阵」，按角色分配入口

控制台 ≠ 收集器 / 存储：

- Prometheus 自身既是存储也是「数据端」控制台（PromQL）
- Grafana 仅做聚合视图
- Loki / Tempo 是数据后端，常以 Grafana Explore 作为查询界面
- Kiali / Jaeger 各自提供独立 UI

## 二、Grafana + Prometheus Operator（K8s 运维控制台）

### 1. 组合定位

```text
                    ┌────────────────────┐
                    │     Grafana         │  ← 统一 UI
                    │  (Dashboard /       │
                    │   Explore / Alert)  │
                    └──────┬─────────────┘
                           │
       ┌───────────────────┼───────────────────┐
       ▼                   ▼                   ▼
 Prometheus          Alertmanager         Loki / Tempo
 (metrics + alert   (route / inhibit       (logs / traces,
  rules via         / webhook)             Grafana Explore)
 Operator)
       │
       ▼
 kube-prometheus-stack
```

### 2. kube-prometheus-stack 组件

Helm chart：`prometheus-community/kube-prometheus-stack`

| 组件 | 作用 |
| ---- | ---- |
| **Prometheus** | 时序存储 + 抓取 + 规则评估 |
| **Alertmanager** | 告警分组 / 路由 / 抑制 |
| **Prometheus Operator** | CRD 控制器（ServiceMonitor / PodMonitor / PrometheusRule / AlertmanagerConfig） |
| **kube-state-metrics** | K8s 对象状态（Deployment / Pod Phase / Node Status） |
| **node-exporter** | 宿主机 / 内核指标 |
| **Grafana** | 仪表板 / Explore |
| **pushgateway** | 短任务上报（可选） |
| **admission webhook** | mutating / validating |

### 3. ServiceMonitor / PodMonitor

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: api
  namespace: monitoring
  labels:
    release: kube-prometheus-stack  # 与 Helm release 标签一致
spec:
  selector:
    matchLabels:
      app: api
  endpoints:
    - port: http
      path: /metrics
      interval: 30s
      scrapeTimeout: 10s
      honorLabels: true
```

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PodMonitor
metadata:
  name: api-pods
spec:
  selector:
    matchLabels:
      app: api
  podMetricsEndpoints:
    - port: http
      interval: 30s
```

Operator 监听到 CRD → 自动生成 prometheus 配置 → reload scrape。

### 4. PrometheusRule（告警规则）

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: api-alerts
  labels:
    release: kube-prometheus-stack
spec:
  groups:
    - name: api
      rules:
        - alert: ApiHighErrorRate
          expr: |
            sum(rate(http_requests_total{service="api",status=~"5.."}[5m]))
              / sum(rate(http_requests_total{service="api"}[5m])) > 0.05
          for: 10m
          labels:
            severity: critical
          annotations:
            summary: "API 错误率 > 5%"
            description: "{{ $labels.service }} 5xx 占比 > 5%，持续 10 分钟"
```

### 5. 常用 K8s 大盘 ID（grafana.com）

| Dashboard | ID | 用途 |
| --------- | -- | ---- |
| Kubernetes / Views / Cluster | 7249 | 集群总览 |
| Kubernetes / Views / Namespaces | 0N9Dz2vG | 命名空间 |
| Kubernetes / Views / Nodes | 3146 | 节点 |
| Kubernetes / Views / Pods | 6417 | Pod |
| Kubernetes / Compute Resources / Cluster | 0 | 资源总览 |
| Kubernetes / Compute Resources / Pod | 0 | Pod 资源 |
| Node Exporter Full | 1860 | 主机内核 |
| etcd | 3070 | K8s 数据面 |
| API Server | 0 / 14981 | 控制面 |
| Prometheus 2.0 Stats | 2 | Prometheus 自监控 |
| Alertmanager | 2 | 告警状态 |

> 这些 ID 可在 Grafana 中按 `ID` 导入。kube-prometheus-stack 默认带一份。

### 6. 告警到 Alertmanager 路由

```yaml
# AlertmanagerConfig
apiVersion: monitoring.coreos.com/v1alpha1
kind: AlertmanagerConfig
metadata:
  name: main
spec:
  route:
    receiver: default
    groupBy: [alertname, cluster]
    groupWait: 30s
    groupInterval: 5m
    repeatInterval: 4h
    routes:
      - matchers:
          - severity = critical
        receiver: pagerduty
      - matchers:
          - service = payments
        receiver: payments-team
  receivers:
    - name: default
      webhookConfigs:
        - url: http://bot:8080/alert
    - name: pagerduty
      pagerdutyConfigs:
        - serviceKey: <key>
    - name: payments-team
      slackConfigs:
        - apiURL: https://hooks.slack.com/XXX
          channel: '#payments-alerts'
```

## 三、Kiali（服务网格控制台）

### 1. 定位

Kiali 是 Istio / OSSM 服务网格的可视化与诊断控制台，主要解决：

- 网格拓扑（服务间调用关系）
- 配置是否生效（VirtualService / DestinationRule）
- 流量占比（按版本拆分）
- 错误率 / 延迟（结合 Prometheus + Jaeger）

### 2. 架构

```text
浏览器 ──► Kiali (Go) ──► Istiod (config)
                       ──► Prometheus (metrics)
                       ──► Jaeger / Tempo (traces)
                       ──► kube-apiserver (workload)
```

- Kiali 本身**不存数据**，只是个聚合视图层
- 部署通常随 Istio / OSSM 一起（`kiali-server`）
- 必装：Prometheus（Kiali 用来画错误率 / 流量）+ Tracing 后端

### 3. 关键视图

| 视图 | 用途 |
| ---- | ---- |
| Graph | 服务 / 版本 / 边应用拓扑，自动按 RPS / 错误率染色 |
| Applications | 服务列表与版本 |
| Workloads | Deployment / Pod 视角 |
| Services | Service + 关联 VS / DR |
| Istio Config | VirtualService / DestinationRule 等校验 |
| Distributed Tracing | 跳转 Jaeger / Tempo |

### 4. 与 Jaeger / Prometheus 关系

```text
Kiali 显示拓扑与错误率
   │
   ├── 从 Prometheus 拿：
   │     - istio_requests_total
   │     - istio_request_duration_milliseconds_bucket
   │     - istio_request_bytes_bucket
   │
   └── 从 Jaeger / Tempo 跳转：
         - 点 trace drilldown 跳转到对应 span
```

- Kiali 必须配 `prometheus.url`（Istio 自带的 Prometheus 即可）
- tracing 端可配多个（Jaeger / Tempo）

### 5. 部署

```bash
# Istio 集成 demo profile
istioctl manifest apply --set profile=demo
```

或在 OSSM：

```bash
maistra-install-kiali --namespace istio-system
```

```yaml
# kiali CR
apiVersion: kiali.io/v1alpha1
kind: Kiali
metadata:
  name: kiali
  namespace: istio-system
spec:
  auth:
    strategy: openid
  external_services:
    prometheus:
      url: http://prometheus.istio-system:9090
    tracing:
      url: http://jaeger.istio-system:16686
```

## 四、Jaeger UI 简述

### 1. 定位

- 分布式追踪的查询 UI（按 service / operation / tag / traceID）
- 后端存储用 ES / Cassandra / Kafka / Badger
- 与 K8s 集成：通过 OpenTelemetry / Jaeger Agent sidecar 抓取

### 2. 部署（Operator）

```yaml
apiVersion: jaegertracing.io/v1
kind: Jaeger
metadata:
  name: simplest
spec:
  storage:
    type: memory
```

```yaml
apiVersion: jaegertracing.io/v1
kind: Jaeger
metadata:
  name: prod
spec:
  strategy: production
  storage:
    type: elasticsearch
    options:
      es:
        server-urls: http://elasticsearch:9200
  ingress:
    enabled: true
    host: jaeger.example.com
```

### 3. 视图

- Search：按 service / operation / tag 拉 trace
- 单条 trace：span 时间线 + 火焰图
- Service / Dependencies：依赖关系（自动从 trace 汇聚）
- 比较 trace：性能回归对比

### 4. 与 Grafana Tempo / Kiali 关系

| 工具 | 角色 |
| ---- | ---- |
| Jaeger | 追踪采集 + 存储 + UI |
| Grafana Tempo | 追踪存储（接 OTLP） |
| Kiali | 依赖拓扑 + Jaeger 跳转 |
| Grafana Explore | 跨 metrics / logs / traces 的统一入口 |

实际生产中，几种搭配都常见：

- **Jaeger 全家桶**：Operator 部署 Jaeger，Kiali 跳它
- **Grafana 一统**：Tempo + Prometheus + Loki + Grafana Explore
- **SkyWalking**：自带 UI，不和 Kiali 系争

## 五、K8s Event 与事件告警

### 1. 什么是 K8s Event

集群事件，例如：

- `FailedScheduling`
- `BackOffLimitExceeded`
- `FailedMount`
- `NodeNotReady`
- `Pulling image`

它们写在 etcd 中，默认保留 1 小时，且不会被 kubectl 主动持久化。

### 2. kubectl events

```bash
kubectl get events -A --sort-by=.lastTimestamp
kubectl get events -n payments --watch
kubectl get events -A --field-selector type=Warning
```

便捷但保留时间短，正式场景需要收集：

- **Event Exporter**（Kubernetes Event Exporter）：把 events 翻译成 Prometheus metrics / Log
- **Vector / Fluent Bit**：从 apiserver / kubelet 收集

### 3. BotKube

```yaml
# Slack 通知
apiVersion: v1
kind: ConfigMap
metadata:
  name: botkube
data:
  config.yaml: |
    notifications:
      default:
        slack:
          channel: '#k8s-events'
          token: <xoxb-...>
    executors:
      kubectl:
        kubectl-image: "bitnami/kubectl:1.29"
    sources:
      k8s-recommendation-events:
        plugin:
          kubernetes:
            namespaces:
              include: [payments,orders]
```

特性：

- 实时把 events 推到 Slack / Teams / 钉钉
- 支持互动 kubectl（在频道里发命令）
- 报警配置灵活，可只取 `type=Warning` 或 `reason=Failed`

### 4. Robusta

- 商业 SaaS（开源版可用）
- 自动把关键事件 + 推测 + 修复建议推到 Slack
- 集成 alertmanager / Prometheus

### 5. 控制台层面看 events

- Headlamp / Rancher 都有 Events 标签页
- Grafana 通过 Loki 拉 events 也可做面板
- 团队级事件中心常见做法：Loki + Grafana

```yaml
# vector 收 events
sources:
  kubernetes_logs:
    type: kubernetes_logs
    extra_label_selector: "involvedObject.kind=Pod"
sinks:
  loki:
    type: loki
    inputs: [kubernetes_logs]
    endpoint: http://loki:3100
```

```logql
{job="kubernetes_logs"} | json | involvedObject_kind="Pod" | type="Warning"
```

## 六、容量 / 调度类（在控制台里看但不算控制台）

### 1. Karpenter

- AWS 主导的开源节点伸缩器（CNCF 孵化）
- 直接挂 EC2 Spot / OnDemand
- 自动化 binpacking / 合并 / 调度
- 控制台维度：看 `kubectl get nodeclaims`，看 Prometheus 面板

```yaml
apiVersion: karpenter.sh/v1beta1
kind: NodePool
metadata:
  name: default
spec:
  template:
    spec:
      requirements:
        - key: karpenter.sh/capacity-type
          operator: In
          values: [spot, on-demand]
      nodeClassRef:
        name: default
  limits:
    cpu: "100"
    memory: 1000Gi
```

观测：通过其自带的 Prometheus 指标 + Grafana 面板。

### 2. Descheduler

- 重平衡已有 Pod（e.g. 删除节点后剩余 Pod 重新分布）
- 不能扩容，与 Karpenter 互补
- 观测：在控制台看 `descheduler_duplicate_events` / `evictions`

### 3. Cluster Autoscaler

- 老牌节点伸缩（与云厂商 ASG 配合）
- 观测：在控制台看 `cluster_autoscaler_*` 指标

这些都**不是控制台**，但都在运维控制台里看。本仓库调度部分在 `/DevOps/任务调度/`，详细原理在那里。

## 七、Loki + Grafana Explore（LogQL 快速入门）

### 1. Loki 定位

- 日志聚合（CNCF 毕业）
- 不全文索引，只索引 label（成本低）
- 标配 Grafana Explore 查日志

### 2. 部署

```bash
helm repo add grafana https://grafana.github.io/loki
helm install loki grafana/loki --namespace loki --create-namespace
helm install promtail grafana/promtail --namespace loki
```

或用 Grafana All-in-One（PoC / 小集群）：

```bash
# docker-compose 起 All-in-One
```

### 3. 标签选择

Loki 不解析每条日志，靠 label 索引：

```text
{namespace="payments", app="api"}
{namespace="payments"} |= "error"
{namespace="payments"} |~ "timeout|deadline"
```

### 4. LogQL 实战

```logql
# 1. 简单过滤
{namespace="payments", app="api"} |= "5xx"

# 2. 过滤 + 提取
{namespace="payments"} | json | status="500"

# 3. 速率（每秒 5xx 条数）
sum(rate({namespace="payments"} |~ " 5[0-9]{2} " [5m]))

# 4. TopN 错误 service
topk(5,
  sum by (service) (
    rate({namespace="payments"} |~ " 5[0-9]{2} " [5m])
  )
)

# 5. 解析为 metrics
sum(
  rate(
    {app="api",namespace="payments"} | json | level="error" [1m]
  )
)
```

### 5. 探索流程

- 点 Grafana Explore → Data Source: Loki
- 选 Label（namespace, app, pod）
- 输入过滤表达式
- 命中行点击可跳转 Tempo / Prometheus

### 6. 演练

```logql
# 找一个订单创建失败的具体上下文
{namespace="orders", app="checkout"} 
  | json 
  | level="error" 
  | req_id="abc123"
```

更深入内容参见 `/DevOps/监控体系/loki.md`。

## 八、控制台矩阵：组合示例

### 1. 角色 × 工具

| 角色 | 主用控制台 | 用途 |
| ---- | ---------- | ---- |
| SRE / 运维 | Grafana + Prometheus / Loki / Tempo | 指标 / 日志 / trace / 告警 |
| 后端开发 | Jaeger / Tempo | 看自己服务的 trace |
| 平台工程师 | Headlamp / Rancher | 集群与节点 |
| 业务方 / 周报 | Grafana 公开大盘 | 看业务指标 |
| 安全 / 合规 | Kiali + RBAC 审计 | 流量策略 / 审计 |
| 业务运维 | BotKube / Robusta | 事件 → Slack |

### 2. 权限分层

```text
Admin Team
   └── Grafana Org: admin（读写所有 dashboard）
   └── Headlamp: cluster-admin
   └── kubeconfig: cluster-admin

App Team
   └── Grafana Org: 各应用团队（编辑自己的 dashboard）
   └── Headlamp: namespace 只读
   └── kubeconfig: 右 RBAC（CRUD 自己 namespace）

Viewer
   └── Grafana Public Dashboard
   └── Headlamp: 只读
   └── 无 kubeconfig
```

### 3. 典型告警升级链

```text
Prometheus 触发告警
   │
   ▼
Alertmanager
   │
   ├─ severity=info   →  Slack 频道
   ├─ severity=warning → 邮件 + Slack
   └─ severity=critical → PagerDuty / 值班
        │
        ▼
   oncall 排查
        │
        ▼
   Headlamp / kubectl / Grafana / Kiali 联动
```

### 4. Headlamp / Grafana / Kiali / Jaeger 联动示例

```text
投资者在 Grafana 看到 5xx 突增
   │
   ▼
点击 Dashboard 链接到 Headlamp（同名 Pod）
   │
   ▼
在 Headlamp 看到 Pod Phase / Event
   │
   ▼
点 Event 中的「Sentry / trace_id」tag
   │
   ▼
在 Jaeger / Tempo 查具体 trace
   │
   ▼
回到 Grafana 对照该 service 的 latency / error 面板
```

## 九、与 `/DevOps/监控体系/` 的分工

| 本文 | 监控体系目录 |
| ---- | ------------ |
| Grafana / Prometheus / Loki 在 K8s 上作为控制台的视角 | Grafana / Prometheus / Loki 各自的原理、PromQL、配置语言 |
| Kiali / Jaeger 做服务网格控制台 | OTel / Jaeger 的采集与协议 |
| BotKube / Robusta 事件告警 | 告警汇集原理 |
| 控制台矩阵组合 | 选型 / 长期存储 / 联邦 / 协议 |

详细原理（Prometheus 自己如何抓取、TSDB 怎么存、OTel Collector Pipeline）请翻到 `/DevOps/监控体系/`。

## 十、优缺点

### 优点

- 跨多种数据源统一体验（Grafana）
- 控制台矩阵按角色拆分清晰
- 与告警体系联动成熟（Alertmanager → Slack / PD）
- 服务网格拓扑可视化（Kiali）
- 事件 → IM 几乎零延迟（BotKube）

### 缺点

- 工具多，学习与运维成本高
- 控制台自身成为 SPOF（生产必须 HA）
- 公开 dashboard / 权限错配容易泄露数据
- 多集群 / 多命名空间过滤体验参差
- Alertmanager 路由配置复杂，团队需要治理
- Kiali 只是聚合视图，故障定位仍要回到原始数据源

### 适用

- 任何上规模 K8s 集群都应建立「控制台矩阵」
- 中小团队可以从「Grafana + Prometheus + Alertmanager」起步
- 多语言 / 服务网格场景加 Kiali / Jaeger
- 多集群场景加 Headlamp / Rancher（参见其他文档）

## 十一、最佳实践

- **统一入口**：所有面板放在同一 Grafana Org / Folders，方便 grep
- **权限矩阵**：Grafana Org / Team / Role 与 K8s RBAC 对齐
- **大盘标准 ID**：直接用社区维护的 Kubernetes 大盘（不用另起炉灶）
- **告警规范**：每条告警必须能链接到 Runbook（annotations.runbook_url）
- **聚合后再告**：5xx 比例 > 5% 才告，而不是单一 Pod 5xx > 0
- **Event 持久化**：生产必须把 K8s events 推到 Loki / ES（默认 1h 丢失）
- **Kiali + Prometheus 联动**：用 Istio 自身 metrics 即可，不必再起一套监控
- **BotKube 收口**：events 集中推 Slack，避免多个监控告警源
- **跨集群监控**：Thanos / Mimir / VictoriaMetrics 联邦 + Grafana 多数据源
- **链路统一**：traceId / requestId 贯穿日志与 trace
- **控制台自身监控**：用 Grafana 自己看 Grafana / Prometheus / Loki 健康
- **备份**：Grafana 数据源 / 仪表板 JSON 进 Git
- **限速**：事件告警做 dedup / group，避免风暴
- **避免公开 dashboard**：敏感数据用 RBAC + 内网 VPN 而不是 Public Dashboard
