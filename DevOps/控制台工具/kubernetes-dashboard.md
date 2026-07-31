# Kubernetes Dashboard

Kubernetes 官方 Web 控制台，提供基于浏览器的资源浏览、YAML 编辑、Pod 日志/终端访问与基础指标展示，自 v2.7/v3 起仅以 Helm Chart 多容器方式发布。

## 一、定位与特性

- 官方维护，SIG UI 主导
- 浏览器端管理集群：看资源、改 YAML、看日志、进容器
- 自带 metrics-scraper 抓 metrics-server 指标做 CPU/内存展示
- v3（v7+）重构为前后端分离（dashboard + api + kong + metrics-scraper），仅支持 Helm 部署
- 不是监控/告警/审计平台，能力边界在「日常排障 + 资源管理」

## 二、架构

### 1. 旧版单体架构（v2.6 及之前）

```text
┌──────────────────────────────────────┐
│        kubernetes-dashboard Pod      │
│   ┌────────────────────────────────┐ │
│   │   dashboard-web (Angular)      │ │
│   │   + dashboard-api (Go)         │ │
│   │   + sidecar metrics-scraper    │ │
│   └────────────────────────────────┘ │
└──────────────────────────────────────┘
```

- 一个 Pod 一个进程，前后端打包
- 通过 deployment 或 `kubectl apply -f recommended.yaml` 部署

### 2. 新版多容器架构（v3 / chart 7+）

```text
┌──────────┐    ┌────────────┐    ┌──────────────┐    ┌──────────────────┐
│  Browser │ -> │  Kong      │ -> │ dashboard    │ -> │ kube-apiserver   │
│          │    │  Gateway   │    │ (frontend)   │    │                  │
└──────────┘    │  (auth/    │    └──────────────┘    └──────────────────┘
                │   routing) │    ┌──────────────┐
                │            │ -> │ dashboard    │ -> metrics-server
                │            │    │ api          │    (via metrics-scraper)
                └────────────┘    └──────────────┘
```

- **dashboard**：静态前端（nginx + Angular）
- **dashboard-api**：后端 Go 服务，代理到 apiserver
- **kong**：API gateway，负责认证、路由、限流、CORS
- **metrics-scraper**：周期性调用 metrics-server `/apis/metrics.k8s.io`，缓存供前端展示

```bash
# 查看 Pod 内容器
kubectl -n kubernetes-dashboard get pod \
  -l app.kubernetes.io/name=kubernetes-dashboard \
  -o jsonpath='{.items[0].spec.containers[*].name}'
# dashboard metrics-scraper
```

## 三、部署方式

### 1. Helm（推荐，v7+ 唯一方式）

```bash
# 添加并更新 repo
helm repo add kubernetes-dashboard https://kubernetes.github.io/dashboard/
helm repo update

# 安装
helm upgrade --install kubernetes-dashboard kubernetes-dashboard/kubernetes-dashboard \
  --create-namespace \
  --namespace kubernetes-dashboard \
  --set kong.proxy.type=ClusterIP \
  --set metricsScraper.enabled=true \
  --set appVersion=v2.7.0
```

升级：

```bash
helm upgrade kubernetes-dashboard kubernetes-dashboard/kubernetes-dashboard \
  -n kubernetes-dashboard
```

### 2. 旧 manifest 方式（仅 v2.6）

```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/dashboard/v2.6.1/aio/deploy/recommended.yaml
```

新版本已不再提供 `recommended.yaml`，必须使用 Helm。

### 3. 关键 Helm 参数

| 参数 | 含义 | 常用值 |
| ---- | ---- | ---- |
| `kong.proxy.type` | Kong 服务类型 | `ClusterIP`（配合 Ingress）/ `NodePort` |
| `kong.proxy.http.enabled` | 是否启用 HTTP | 生产关闭，仅 HTTPS |
| `metricsScraper.enabled` | 是否启用指标抓取 | `true` |
| `appVersion` | dashboard 镜像 tag | 跟随 chart |
| `serviceAccount.create` | 是否自动建 SA | `true` |
| `ingress.enabled` | 是否启用 Ingress | `true` |
| `extraArgs` | dashboard-api 启动参数 | `--enable-skip-login=false` |

## 四、认证原理

### 1. 三种登录方式

| 方式 | 适用 | 说明 |
| ---- | ---- | ---- |
| **Token** | CI / 自动化 | ServiceAccount 的 Bearer Token |
| **kubeconfig** | 个人开发 | 上传 kubeconfig，前端解码后用 token 调 apiserver |
| **Skip（已弃用）** | 测试 | 不推荐，v2.7+ 默认禁用 |

### 2. Token 不再自动创建

老教程常见 `kubectl -n kube-system get secret` 取 `kubernetes-dashboard-token-xxxxx`，新版本**不再自动创建 long-lived Secret**，必须用 `kubectl create token` 拿短期 token（TTL 1h）：

```bash
# 创建只读 SA
kubectl create serviceaccount dashboard-readonly -n kubernetes-dashboard

# 生成 1 小时有效 token
kubectl create token dashboard-readonly -n kubernetes-dashboard --duration=1h
```

> 注意：TokenRequest 的 TTL 受 ServiceAccount `tokens.maximum-expected-lifetime`（kubelet/cluster 配置）约束，默认 1h，最大按 admission 限制。

### 3. kubeconfig 登录

```bash
# 把 SA token 灌进 kubeconfig
kubectl config set-credentials dashboard-sa \
  --token="$(kubectl create token dashboard-readonly -n kubernetes-dashboard --duration=24h)"

kubectl config set-context dashboard-ctx \
  --cluster=my-cluster --user=dashboard-sa

kubectl config use-context dashboard-ctx
```

把 `~/.kube/config` 上传到 dashboard 登录页，选 kubeconfig 方式。

### 4. Skip Login（已禁用）

v2.7+ 默认 `--enable-skip-login=false`，URL 也不能加 `?skip`。仅极少数本地 kind/minikube 场景手动开启，**绝不用于任何有数据的环境**。

## 五、RBAC 授权

Dashboard 本身不做 RBAC，完全透传到 apiserver。前端操作能成功与否取决于登录身份（SA token 对应的 SA）能做什么。

### 1. ClusterRole 模板

**只读**（推荐作为最低权限基线）：

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: dashboard-readonly
  namespace: kubernetes-dashboard
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: dashboard-readonly
rules:
# 允许看资源（针对 core 与 metrics.k8s.io）
- apiGroups: [""]
  resources: ["*"]
  verbs: ["get", "list", "watch"]
- apiGroups: [""]
  resources: ["pods/log", "pods/exec", "pods/portforward"]
  verbs: ["get", "list", "watch", "create"]
- apiGroups: ["apps", "batch", "networking.k8s.io", "policy", "rbac.authorization.k8s.io"]
  resources: ["*"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["metrics.k8s.io"]
  resources: ["pods", "nodes"]
  verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: dashboard-readonly
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: dashboard-readonly
subjects:
- kind: ServiceAccount
  name: dashboard-readonly
  namespace: kubernetes-dashboard
```

**管理员**（慎用）：

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: dashboard-admin
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: cluster-admin   # 注意：完整权限
subjects:
- kind: ServiceAccount
  name: dashboard-admin
  namespace: kubernetes-dashboard
```

### 2. 限定 namespace

不绑定 ClusterRole，改用 Role + RoleBinding（单 namespace）：

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: dashboard-dev
  namespace: dev
rules:
- apiGroups: [""]
  resources: ["pods", "pods/log", "pods/exec", "services", "configmaps", "secrets", "events"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["apps"]
  resources: ["deployments", "replicasets"]
  verbs: ["get", "list", "watch", "patch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: dashboard-dev
  namespace: dev
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: dashboard-dev
subjects:
- kind: ServiceAccount
  name: dashboard-dev
  namespace: kubernetes-dashboard
```

## 六、暴露方式

### 1. kubectl proxy（本地开发）

```bash
kubectl proxy
# 浏览器打开
# http://localhost:8001/api/v1/namespaces/kubernetes-dashboard/services/https:kubernetes-dashboard:https/proxy/
```

优点：apiserver 自身做认证代理，不暴露 dashboard 服务。缺点：仅本机。

### 2. kubectl port-forward（临时调试）

```bash
kubectl port-forward -n kubernetes-dashboard svc/kubernetes-dashboard 8443:443
# 浏览器 https://localhost:8443，忽略证书警告
```

适合本地临时看生产集群，不适合长期暴露。

### 3. Ingress + TLS（生产推荐）

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: kubernetes-dashboard
  namespace: kubernetes-dashboard
  annotations:
    nginx.ingress.kubernetes.io/backend-protocol: "HTTPS"
    nginx.ingress.kubernetes.io/configuration-snippet: |
      proxy_ssl_name "kubernetes-dashboard";
      proxy_ssl_server_name on;
spec:
  ingressClassName: nginx
  tls:
  - hosts: [k8s.example.com]
    secretName: dashboard-tls
  rules:
  - host: k8s.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: kubernetes-dashboard-kong-proxy
            port:
              number: 80
```

外加 OAuth2/OIDC 代理（如 oauth2-proxy + GitHub/Google），这是企业里最常见的生产方案。

### 4. 为什么不要裸暴露（NodePort / LoadBalancer 直连）

- 任何人只要知道 URL 就能看到登录页，暴力破解 token
- Kong 默认 80/443，但 dashboard 自身不做防爆破/审计
- 配合 `--enable-skip-login` 后等于公网 admin 入口（2020 年 CVE-2020-8559 即此类问题）
- 合规要求几乎都不允许

## 七、metrics-scraper 与 metrics-server

dashboard 看到 CPU/内存曲线不是因为它自己能监控，而是依赖 metrics-server。

```text
dashboard 前端
  │  GET /api/v1/dashboard-metrics-scraper/api/v1/metrics/pods?...
  ▼
metrics-scraper（dashboard sidecar）
  │  缓存 60s
  ▼
metrics-server（k8s-metrics-server Pod）
  │  kubelet /metrics/resource
  ▼
kubelet
```

部署 metrics-server（dashboard chart 默认不装）：

```bash
helm repo add metrics-server https://kubernetes-sigs.github.io/metrics-server/
helm install metrics-server metrics-server/metrics-server -n kube-system \
  --set args[0]="--kubelet-insecure-tls"   # 自签证书场景
```

- 没装 metrics-server：dashboard 显示「Metrics unavailable」
- metrics-scraper 是 dashboard 私有缓存层，可关闭（`metricsScraper.enabled=false`）
- 想要 Prometheus/Grafana 维度，需要额外接 Prometheus

## 八、功能范围

### 1. 能做

- 浏览/检索 Workload、Service、ConfigMap、Secret、PV、Node、Namespace
- 编辑 YAML、应用到集群
- 看 Pod 日志（含上一个容器、容器选择）
- `kubectl exec` 进容器 shell
- `kubectl port-forward` 起端口转发
- 看 events、metrics-server 基础 CPU/内存
- 创建/删除 Deployment、Job、Service、Ingress（按权限）

### 2. 不能做（典型痛点）

| 能力 | 现状 |
| ---- | ---- |
| **审计** | 无，谁/何时/做了什么查不到 |
| **告警** | 无 |
| **RBAC 编辑** | 看得到但复杂配置不便 |
| **多集群** | 一个 dashboard 服务对应一个 kubeconfig 上下文 |
| **审计/合规** | 无 SSO/审批流（需 OIDC 代理层） |
| **CRD** | 默认只认内置资源，CRD 视图有限 |
| **GitOps 工作流** | 不接 ArgoCD/Flux，编辑即落集群 |
| **Helm/Release 管理** | 7.x 起部分支持 `helm release` 视图 |

## 九、CVE 与安全加固

### 1. 已知高危 CVE

| CVE | 说明 |
| ---- | ---- |
| **CVE-2018-18264** | dashboard 1.10 之前 info disclosure（仅看 namespace，服务 token） |
| **CVE-2019-11247** | dashboard 2.0 之前，特殊 RBAC + dashboard token 可越权 |
| **CVE-2020-8559** | 配合 `--enable-skip-login=true`，匿名获得 cluster-admin |
| **CVE-2021-36742** | dashboard-api 2.0.0/2.0.1 auth bypass |

### 2. 部署期加固清单

```bash
# 1. 关闭 skip login（默认已关）
--enable-skip-login=false

# 2. 限制 namespace
kubectl label ns kube-system kubernetes.io/metadata.name=kube-system \
  --overwrite   # 防止有些 dashboard 视图误列出 kube-system

# 3. 不用 cluster-admin SA
kubectl create serviceaccount dashboard-readonly -n kubernetes-dashboard

# 4. 强制 HTTPS（Kong 默认走 HTTPS upstream）
```

### 3. NetworkPolicy

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: kubernetes-dashboard
  namespace: kubernetes-dashboard
spec:
  podSelector: {}
  policyTypes: ["Ingress", "Egress"]
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: ingress-nginx   # 限定 ingress controller
    - podSelector: {}                                # 自洽
    ports:
    - protocol: TCP
      port: 8443
  egress:
  - to:
    - namespaceSelector: {}    # 允许访问 apiserver（CNI 解析 kube-dns）
    ports:
    - protocol: TCP
      port: 443
```

### 4. token 生命周期

- 用 `kubectl create token` 而不是长期 Secret
- CI/CD 自动刷新，过期即失效
- 生产建议配合 Vault / ESO 动态签发

## 十、优缺点

### 优点

- 官方血统，跟 K8s 版本同步更新
- 多容器架构干净：Kong 接管横切关注点
- Helm 一行安装，支持 cert-manager、Ingress
- 登录方式标准化（token/kubeconfig）
- 国际化、多语言

### 缺点

- **安全心智负担高**：默认就开在集群里，必须加固
- 多集群、多团队体验差（要切 context）
- 监控、告警、审计 0 能力
- 容器终端在大集群上偶发断流
- CRD 视图对新 CR 经常识别不到
- UI 改动频繁，bookmark 经常失效

## 十一、最佳实践

- **永远不要绑 cluster-admin**：建多 SA，按团队/namespace 分权限
- **永远不开 skip login**：哪怕本地调试也走 kubeconfig
- **永远走 Ingress + OIDC**：oauth2-proxy / Keycloak / dex 之一
- **限制 ServiceAccount `automountServiceAccountToken`**：只 SA 自身 POD 能挂 token
- **NetworkPolicy 收敛**：只允许 ingress-nginx 进入
- **审计外置**：用 Falco + audit policy 监控 dashboard 的 apiserver 调用
- **定期轮转 token**：即便 token 短期，过期前重发
- **生产只读为主**：写操作通过 GitOps（ArgoCD/Flux）执行
- **多集群用统一入口**：Portainer / Rancher / headlamp 等套娃方案，而不是开 N 个 dashboard
- **Prometheus + Grafana 补监控盲区**：dashboard 只看 metrics-server 趋势，告警靠 Alertmanager