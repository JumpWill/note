# Linkerd

CNCF 毕业的轻量级 Service Mesh。数据面用 Rust 编写（linkerd2-proxy），比 Envoy 占用小、延迟低。聚焦"做好 Mesh 本职"，不过度设计。

## 一、定位与特点

- 轻量 Service Mesh（CNCF Graduated）
- 数据面：linkerd2-proxy（Rust）
- 控制面：Linkerd Controller（Go + Rust）
- 默认 mTLS（自动证书轮转）
- HTTP / gRPC / HTTP/2（优先）
- TCP 通过 Service Profile 支持
- 可视化：Linkerd Viz（Dashboard）
- 扩展：Buoyant Enterprise for Linkerd（多集群、策略）

## 二、架构

```text
┌────────────────────────────────────┐
│  Pod                              │
│   ┌─────────────────┐             │
│   │ App Container   │             │
│   └────────┬────────┘             │
│            │                       │
│   ┌────────▼────────┐             │
│   │ linkerd-proxy   │             │
│   │ (Rust, ~10MB)   │             │
│   └────────┬────────┘             │
└────────────┼──────────────────────┘
             │
             ▼
┌────────────────────────────────────┐
│  Linkerd Controller               │
│   - Destination (服务发现)         │
│   - Identity (证书 / mTLS)         │
│   - Proxy Injector (注入)         │
└──────┬──────────────────────────┬─┘
       │                          │
       ▼                          ▼
   K8s API                trust anchor / CA
```

组件：

- **linkerd2-proxy**：数据面（Rust，超轻量）
- **Controller**：控制面
- **Identity**：证书签发
- **Destination**：服务发现
- **Viz**：可观测（Dashboard + Prometheus）

## 三、核心概念

| 概念 | 含义 |
| --- | --- |
| **Mesh** | Mesh 范围（默认 cluster 级） |
| **Service Profile** | 服务路由定义（per Service） |
| **Server** | 鉴权目标（Linkerd 2.13+） |
| **AuthorizationPolicy** | 鉴权策略 |
| **TrafficSplit** | 流量切分（蓝绿 / 金丝雀） |
| **Link** | 多集群链路 |
| **Tap** | 实时流量观察 |
| **SMI** | Service Mesh Interface（被 Linkerd 实现） |

## 四、部署

### 1. CLI 安装

```bash
# 安装 linkerd CLI
curl --proto '=https' --tlsv1.2 -sSfL https://run.linkerd.io/install | sh
export PATH=$PATH:$HOME/.linkerd2/bin

# 预检
linkerd check --pre

# 安装 CRD
linkerd install --crds | kubectl apply -f -

# 安装控制面
linkerd install | kubectl apply -f -

# 安装 Viz（Dashboard）
linkerd viz install | kubectl apply -f -

# 安装 Jaeger（Trace）
linkerd jaeger install | kubectl apply -f -
```

### 2. Helm 安装

```bash
helm repo add linkerd https://helm.linkerd.io/stable
helm install linkerd-crds linkerd/linkerd-crds -n linkerd
helm install linkerd-control-plane linkerd/linkerd-control-plane -n linkerd
helm install linkerd-viz linkerd/linkerd-viz -n linkerd
```

### 3. 注入 Proxy

```bash
# Namespace 注入
kubectl annotate namespace default linkerd.io/injection=enabled

# Pod 级注入（注解）
kubectl get deploy my-app -o yaml | linkerd inject - | kubectl apply -f -
```

## 五、流量管理

### 1. 默认负载均衡

Linkerd 7 种负载均衡算法（远超 Envoy 默认）：

- **Ewma**：指数加权移动平均（默认，智能）
- **P2C** (Power of Two Choices)
- **Round Robin**
- **Least Loaded**
- **Latency-aware**
- **Heap**
- **Random**

### 2. 重试 / 超时（Service Profile）

```yaml
apiVersion: linkerd.io/v1alpha2
kind: ServiceProfile
metadata:
  name: my-app
  namespace: default
spec:
  routes:
    - name: get-user
      condition:
        method: GET
        pathRegex: /users/[^/]+
      isRetryable: true
      timeout: 500ms
      retries:
        budget:
          percentRetries: 20
          retriesPerSecond: 10
      responseClasses:
        - condition:
            status:
              min: 500
              max: 599
          isFailure: true
```

### 3. 灰度 / 流量切分

```yaml
apiVersion: linkerd.io/v1alpha2
kind: TrafficSplit
metadata:
  name: my-app-split
spec:
  service: my-app
  backends:
    - service: my-app-v1
      weight: 900
    - service: my-app-v2
      weight: 100
```

### 4. 灰度发布流程

```text
1. 部署 my-app-v2（带 mesh label）
2. 创建 TrafficSplit，10% 流量到 v2
3. 观察 metrics / errors
4. 调整 50/50
5. 调整 100/0
6. 移除 v1
```

## 六、安全 (mTLS)

### 1. 自动 mTLS

Linkerd 默认所有 Pod 间通信加密：

- 自动签发证书
- 24h 轮转
- 通过 Identity 组件

无需任何配置。

### 2. 信任锚轮换

```bash
linkerd upgrade --trust-root-certificate-file=ca.crt --identity-issuer-certificate-file=issuer.crt --identity-issuer-key-file=issuer.key
```

### 3. AuthorizationPolicy

```yaml
apiVersion: policy.linkerd.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: my-app
  namespace: default
spec:
  targetRef:
    group: policy.linkerd.io
    kind: Server
    name: my-app
  requiredAuthenticationRefs:
    - name: my-sa
      kind: ServiceAccount
      group: core
```

### 4. Server 资源

```yaml
apiVersion: policy.linkerd.io/v1beta1
kind: Server
metadata:
  name: my-app
  namespace: default
spec:
  selector:
    matchLabels:
      app: my-app
  port: 80
  protocol: http
```

## 七、可观测

### 1. 自动指标

Linkerd 自动从 Proxy 收集：

- 请求率
- 成功率
- 延迟 P50 / P95 / P99
- TCP 负载

每个 Pod 暴露 `:4191/metrics`（Prometheus 格式）。

### 2. Dashboard

```bash
linkerd viz dashboard
```

包含：

- Top deployments
- 实时流量
- 错误率
- 延迟分布

### 3. CLI

```bash
# Top
linkerd viz stat deploy

# 实时流量
linkerd viz top deploy/my-app

# 路径分析
linkerd viz routes deploy/my-app

# Tap（实时抓包）
linkerd viz tap deploy/my-app

# 单请求追踪
linkerd viz stat deploy/my-app --to deploy/mysql
```

### 4. 链路追踪 (Jaeger)

```bash
linkerd jaeger install | kubectl apply -f -
linkerd viz dashboard
```

Jaeger UI 集成到 viz dashboard。

### 5. Service Profile 自动生成

```bash
linkerd viz profile --tap deploy/my-app -o my-app-profile.yaml
```

## 八、Service Mesh Interface (SMI)

Linkerd 是 SMI 的参考实现：

- **TrafficSplit**：流量切分
- **TrafficTarget**：访问策略
- **HTTPRouteGroup**：路由定义
- **TCPRoute**：TCP 路由

SMI 是 CNCF 标准，可与其他 Mesh 互通。

## 九、多集群

### 1. 概念

```text
Cluster A ── Link ── Cluster B
   │                     │
   ▼                     ▼
my-app (A) ──proxy──► my-app (B)
```

Link 通过 Gateway 暴露端口，跨集群服务发现。

### 2. 配置

```bash
# Cluster A
linkerd multicluster install | kubectl apply -f -
linkerd multicluster link --cluster-name=cluster-b --api-server-address=... | kubectl apply -f -
```

## 十、与 Istio 对比

| 维度 | Linkerd | Istio |
| --- | --- | --- |
| 数据面 | linkerd2-proxy (Rust) | Envoy (C++) |
| 内存占用 | **小** (~10MB) | 大 (~50MB) |
| 启动延迟 | **低** | 中 |
| 协议 | HTTP/gRPC 优先 | 全 |
| 默认 mTLS | ✔ | ✔ |
| 负载均衡 | 7 种 | 几种 |
| 流量切分 | TrafficSplit | VirtualService |
| 鉴权 | Server + AuthZ | 多维 |
| 入口网关 | 部分 | **完整** |
| WASM | � | ✔ |
| 学习曲线 | **低** | 高 |
| 商业版 | Buoyant Enterprise | Tetrate / Solo.io |

## 十一、典型场景

- **K8s 微服务**：轻量 Mesh，专注 HTTP/gRPC
- **多语言团队**：无需语言特定 SDK
- **Rust 性能导向**：低延迟 + 低内存
- **小团队 / 中型规模**：不想被 Istio 复杂度淹没
- **可观测先行**：先 mesh 拿到 metrics，再加流量管理

## 十二、最佳实践

- **渐进启用**：从 critical namespace 开始
- **必装 Viz**：可视化是 Linkerd 强项
- **Service Profile 必做**：路由级 timeout / retry
- **TrafficSplit 灰度**：用 Linkerd 原生而非 kubectl scale
- **mTLS 默认**：不要禁用
- **多集群**：从 Gateway 开始
- **CI 注入**：linkerd inject 是 GitOps 一部分
- **版本升级**：Linkerd 升级友好，文档全
- **不要装 SMI CRD**：除非真的要用
- **Buoyant Enterprise**：多集群 + 复杂策略考虑商业版
