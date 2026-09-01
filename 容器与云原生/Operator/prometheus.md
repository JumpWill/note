# Prometheus Operator

> 把 Prometheus / Alertmanager / 抓取配置 / 告警规则全部**声明成 K8s CRD** 的 Operator。
> 本质是**用 kubectl apply 代替手写 prometheus.yml + rules + alertmanager.yml**——所有变更进 Git、可审计、可回滚。

---

## 一、它是什么 / 为什么需要

手写 `prometheus.yml` 在 K8s 上的痛点：

| 痛点 | Operator 怎么解 |
| --- | --- |
| 每加一个 ServiceMonitor 要 ssh 进 Pod 改 configmap 重启 Prometheus | `kubectl apply -f servicemonitor.yaml` |
| Alert rule 散落各处文件 | 全部进 `PrometheusRule` CR |
| 多 Prometheus 实例配置同步 | 用同一个 `Prometheus` CR，Operator 渲染成多个实例 |
| 抓取目标随 Service 增减要手动改 | `ServiceMonitor` 通过 label selector 自动发现 |
| 升级 / 配置漂移 / 谁改了什么 | 全在 GitOps 流程里 |

**两个项目要分清**：
- **Prometheus Operator**：只管理 Prometheus + Alertmanager + 一组 CRD
- **kube-prometheus-stack**（Helm chart）：基于 Operator + 预置了一整套 exporter + dashboard + 默认规则，**生产首选**

---

## 二、架构

```
┌──────────────────┐
│ Prometheus CR    │ ───┐
│ Alertmanager CR  │ ───┤
│ ServiceMonitor   │ ───┤  Operator watch
│ PodMonitor       │ ───┤        │
│ Probe            │ ───┤        ▼
│ PrometheusRule   │ ───┤  ┌──────────────────────────┐
│ ThanosRuler      │ ───┘  │ prometheus-operator Pod │
└──────────────────┘       └────────┬─────────────────┘
                                   │  reconcile
                                   ▼
        ┌─────────────────────────────────────────────┐
        │ StatefulSet (Prometheus) / Deployment (AM) │
        │  ConfigMap 由 Operator 生成，Pod 自动 reload │
        └─────────────────────────────────────────────┘
```

**工作流**：Operator 监听 CR 变更 → 渲染出实际的 K8s 对象（StatefulSet / ConfigMap / Service）+ 调用 Prometheus 的 `/-/reload` → 必要时滚动更新 Pod。

---

## 三、核心 CRD 一览

| CRD | 管什么 | 谁创建它 |
| --- | --- | --- |
| **Prometheus** | Prometheus 实例（镜像、版本、副本、retention、remote_write、storage…） | 运维 |
| **Alertmanager** | Alertmanager 实例（集群、存储、配置） | 运维 |
| **ServiceMonitor** | 抓取 **Service** 后端 `/metrics`（最常用） | 业务方 |
| **PodMonitor** | 抓取 **Pod** 直连 `/metrics`（不开 Service 的场景） | 业务方 |
| **Probe** | 黑盒探测（HTTP/TCP/ICMP/SSL 过期） | 运维 |
| **PrometheusRule** | 告警 / recording 规则 | 业务方 |
| **ThanosRuler** | Thanos 规则的独立评估器 | 高级 |
| **AlertmanagerConfig** | AM 路由 / receiver 的 K8s 化定义（替代手写 alertmanager.yml） | 运维 |

---

## 四、安装（kube-prometheus-stack）

> 90% 场景用这个 chart，不要裸装 Prometheus Operator。

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# 安装到 monitoring 命名空间
kubectl create namespace monitoring

helm install kube-prometheus-stack \
  prometheus-community/kube-prometheus-stack \
  -n monitoring \
  --set prometheusOperator.image.tag=v0.76.0 \
  --set prometheus.prometheusSpec.retention=30d \
  --set prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.resources.requests.storage=100Gi \
  --set grafana.adminPassword='change-me'
```

**自带的全家桶**：
- prometheus-operator
- prometheus（StatefulSet）
- alertmanager
- grafana
- kube-state-metrics
- node-exporter（DaemonSet）
- prometheus-adapter（给 HPA 用，自定义指标）
- 一堆默认 `PrometheusRule`（K8s 集群告警）

---

## 五、CRD 详解

### 5.1 `Prometheus` —— 实例定义

```yaml
apiVersion: monitoring.coreos.com/v1
kind: Prometheus
metadata:
  name: main
  namespace: monitoring
  labels:
    prometheus: kube-prometheus   # 关键，ServiceMonitor 用这个选
spec:
  replicas: 2                     # HA 副本数
  shards: 1                       # 分片数（> 1 时需配 hashmod）
  retention: 30d
  retentionSize: 100Gi
  storageSpec:
    volumeClaimTemplate:
      spec:
        storageClassName: ssd
        resources: { requests: { storage: 100Gi } }
  image: quay.io/prometheus/prometheus:v2.55.1
  version: v2.55.1
  resources:
    requests: { cpu: 500m, memory: 2Gi }
    limits:   { memory: 8Gi }
  serviceAccountName: prometheus
  securityContext: { runAsNonRoot: true, fsGroup: 2000 }

  serviceMonitorSelector: {}      # 空 = 选所有 SM（生产推荐给 namespace selector）
  serviceMonitorNamespaceSelector:
    matchNames: [monitoring, prod]
  ruleSelector: {}
  ruleNamespaceSelector:
    matchNames: [monitoring, prod]

  alerting:
    alertmanagers:
      - namespace: monitoring
        name: alertmanager-main
        port: web

  remoteWrite:
    - url: "http://thanos-receive:19291/api/v1/receive"
      writeRelabelConfigs:
        - sourceLabels: [__name__]
          regex: 'go_.*|process_.*|kubelet_pleg_relist_.*'
          action: drop
      queueConfig:
        capacity: 10000
        maxSamplesPerSend: 2000

  additionalScrapeConfigs:
    name: additional-scrape-configs
    key: prometheus-additional.yaml

  enableAdminAPI: true            # 慎用，给 admin UI / reloader 用
```

### 5.2 `ServiceMonitor` —— 抓 Service 后端

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: my-app
  namespace: prod                  # SM 在哪，Operator 就在哪查 Service
  labels:
    release: kube-prometheus       # 给 Prometheus CR 选
spec:
  jobLabel: app                    # 指标里 job= 标签的值，取自 Service label
  selector:
    matchLabels:
      monitoring: enabled          # 选打了这个 label 的 Service
  namespaceSelector:               # 空 = 任意 namespace 都能被选
    any: true
    # 或：
    # matchNames: [prod, staging]
  endpoints:
    - port: metrics                # Service 里端口的名字（不是 number！）
      path: /metrics
      interval: 15s
      scrapeTimeout: 10s
      scheme: http
      honorLabels: true            # 业务指标里的 label 优先（覆盖 Prometheus 注入的）
      relabelings:                 # 抓取前重写
        - sourceLabels: [__meta_kubernetes_pod_label_app_version]
          targetLabel: version
      metricRelabelings:           # 抓取后过滤
        - sourceLabels: [__name__]
          regex: 'go_gc_.*|process_.*'
          action: drop
      basicAuth:
        username:
          name: my-secret
          key: username
        password:
          name: my-secret
          key: password
```

**核心约定**：业务 Service 必须有 `monitoring: enabled` label + 一个名为 `metrics` 的端口。

### 5.3 `PodMonitor` —— 抓 Pod 直连

适合：
- 不希望暴露 Service 的批处理任务
- Sidecar 容器（Istio proxy / OTel collector）抓自身指标

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PodMonitor
metadata:
  name: istio-mesh
  namespace: istio-system
spec:
  selector:
    matchLabels:
      app: istio-proxy
  namespaceSelector: {}
  podMetricsEndpoints:
    - port: http-envoy-prom
      path: /stats/prometheus
      relabelings:
        - sourceLabels: [__meta_kubernetes_pod_container_name]
          action: replace
          targetLabel: container
```

### 5.4 `PrometheusRule` —— 告警 / recording 规则

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: my-app-rules
  namespace: prod
  labels:
    prometheus: kube-prometheus
    role: alert-rules
spec:
  groups:
    - name: my-app
      interval: 30s
      rules:
        - alert: HighErrorRate
          expr: |
            sum by (namespace) (
              rate(http_requests_total{status=~"5.."}[5m])
            ) / sum by (namespace) (rate(http_requests_total[5m])) > 0.05
          for: 5m
          labels:
            severity: P1
            team: payment
          annotations:
            summary: "{{ $labels.namespace }} 错误率 > 5%"
            runbook: "https://wiki/runbooks/high-error-rate"
```

**注意**：`metadata.labels` 必须含 `prometheus: kube-prometheus`（与 Prometheus CR 的 `serviceMonitorSelector` / `ruleSelector` 对应），否则不会被加载。

### 5.5 `Probe` —— 黑盒探测

```yaml
apiVersion: monitoring.coreos.com/v1
kind: Probe
metadata:
  name: blackbox-http
  namespace: monitoring
spec:
  jobName: blackbox-https
  interval: 30s
  module: http_2xx                # 在 blackbox-exporter ConfigMap 定义
  targets:
    staticConfig:
      static:
        - https://www.example.com/health
        - https://api.example.com/ping
  metricRelabelings:
    - sourceLabels: [__address__]
      targetLabel: target
```

### 5.6 `AlertmanagerConfig` —— AM 配置 K8s 化（v0.27+）

替代手写 `alertmanager.yml`，逐 receiver 配置：

```yaml
apiVersion: monitoring.coreos.com/v1alpha1
kind: AlertmanagerConfig
metadata:
  name: feishu-default
  namespace: monitoring
  labels:
    alertmanagerConfig: main
spec:
  route:
    receiver: feishu
    groupBy: [alertname, namespace]
    groupWait: 30s
    groupInterval: 5m
    repeatInterval: 4h
    routes:
      - matchers:
          - name: severity
            value: P0
        receiver: pager
  receivers:
    - name: feishu
      webhookConfigs:
        - url: 'http://prometheus-alert:8080/prometheusalert?type=fs&tpl=default'
          sendResolved: true
    - name: pager
      pagerdutyConfigs:
        - serviceKey: { name: pd-key, key: key }
```

---

## 六、Selector 匹配逻辑（最容易踩坑的点）

```
Prometheus CR ──ruleSelector──► PrometheusRule.metadata.labels
              ──serviceMonitorSelector──► ServiceMonitor.metadata.labels
              ──serviceMonitorNamespaceSelector──► 决定看哪些 namespace
                                │
                                ▼
            ServiceMonitor.spec.selector.matchLabels
                                │
                                ▼
                       Service.metadata.labels
                                │
                                ▼
                     Service.spec.ports[].name
```

**三层 selector 都要对**：

1. Prometheus CR 看哪些 namespace/label 的 SM 和 Rule
2. SM 看哪些 label 的 Service
3. Service 的端口名要匹配 SM 的 `endpoints[].port`

排查"抓不到数据"时按这个链从前往后查 → `/api/v1/targets` 页面。

---

## 七、常用操作

### 7.1 验证 ServiceMonitor 是否被加载

```bash
# 进 Prometheus Pod
kubectl exec -n monitoring prometheus-main-0 -c prometheus -- \
  wget -qO- http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.labels.job=="my-app")'

# 查规则
wget -qO- http://localhost:9090/api/v1/rules | jq '.data.groups[].rules[] | select(.name=="HighErrorRate")'
```

### 7.2 强制重载

```bash
# Operator 自动 reconcile 通常 30s 内生效
# 想立刻：删 Pod（StatefulSet 自动重建）或 curl /-/reload
kubectl exec -n monitoring prometheus-main-0 -c prometheus -- \
  wget --post-data='' http://localhost:9090/-/reload
```

### 7.3 升级 kube-prometheus-stack

```bash
helm repo update
# 先看 diff
helm diff upgrade kube-prometheus-stack prometheus-community/kube-prometheus-stack -n monitoring
# 再升
helm upgrade kube-prometheus-stack prometheus-community/kube-prometheus-stack -n monitoring
```

**重要**：先升 Operator，再升 Prometheus/AM 的 image tag，顺序反了可能 CRD schema 不识别。

### 7.4 添加自定义 scrape config

有些 target 不在 K8s 里（云上 RDS、外部 API），用 `additionalScrapeConfigs` 注入：

```yaml
# 1. 先建 secret
kubectl create secret generic additional-scrape-configs \
  --from-file=prometheus-additional.yaml \
  -n monitoring

# 2. Prometheus CR 引用
spec:
  additionalScrapeConfigs:
    name: additional-scrape-configs
    key: prometheus-additional.yaml
```

---

## 八、踩坑清单

| 现象 | 原因 |
| --- | --- |
| SM 创建了但 targets 看不到 | 三层 selector 任一不对；用 `kubectl describe prometheus` 看 events |
| 规则没生效 | `PrometheusRule` 缺 `prometheus: kube-prometheus` label，或 `ruleSelector` 配错 |
| 告警重复发 | 多个 `Prometheus` CR 同时跑且都配了 alerting；要么只留一个，要么启用 hashmod |
| PVC 撑爆 | 多个 Prometheus 副本 + PVC 模板里 storageClass 没共享；要么 RWO 各自 PVC 要算总容量 |
| 升级后 CRD schema 报错 | Operator 旧版本不识别新 CR 字段——先升 Operator |
| Pod 重启循环 | Operator 自动注入 hash annotation 触发了滚动；查 `kubectl logs prometheus-operator` |
| ServiceMonitor 修改没生效 | Operator 有 30s 缓存；SM annotation 没改 → Pod 滚动没触发；改 `spec` 才会触发 reconcile |

---

## 九、最佳实践

1. **业务 Service 一律加约定 label**：`monitoring: enabled` + `app: <name>` + 端口名 `metrics`
2. **每个 Service 一个 SM**：比把所有 endpoint 堆一个大 SM 好维护、好权限隔离
3. **`namespaceSelector` 收窄**：默认给 `any: false` 或 `matchNames`，避免误采
4. **`metricRelabelings` 过滤**：业务 SDK 默认吐的 `go_*` / `process_*` 在 SM 层 drop，省存储
5. **`honorLabels: true`**：业务指标里有 `job` / `instance` 时一定要开，否则被 Prometheus 注入覆盖
6. **HA 用 hashmod**：两个 Prometheus 实例时配 `prometheus.prometheusSpec.shardingStrategy` + 相同 AM 路由
7. **GitOps 化**：SM / Rule 全部进 ArgoCD / Flux 管理，**别用 Helm values 写业务规则**（耦合难维护）
8. **告警分级 + owner**：每条 rule 带 `severity` + `team`，AMConfig 才能路由到对的人

---

## 十、参考

- Operator 官方仓库：<https://github.com/prometheus-operator/prometheus-operator>
- CRD API 文档：<https://prometheus-operator.dev/docs/api-reference/>
- kube-prometheus-stack：<https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack>
- 升级指南：<https://prometheus-operator.dev/docs/operator/upgrade/>
