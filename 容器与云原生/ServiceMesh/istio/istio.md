# Istio 详解

> Istio 是最主流的 **Service Mesh（服务网格）** 实现。
> 它把微服务间的通信（流量管理、安全、可观测）从应用层下沉到独立的"基础设施层"——由 Sidecar 代理（Envoy）代为处理。
> 这篇从架构 → 部署 → 核心资源 → 流量 / 安全 / 监控 → 高级特性 → 排坑，完整讲清楚。

---

## 目录

- [一、背景：什么是 Service Mesh](#一背景什么是-service-mesh)
- [二、Istio 架构](#二istio-架构)
- [三、安装部署](#三安装部署)
- [四、核心 CRD 资源总览](#四核心-crd-资源总览)
- [五、流量管理](#五流量管理)
- [六、安全（mTLS / AuthorizationPolicy）](#六安全mtls--authorizationpolicy)
- [七、可观测性](#七可观测性)
- [八、EnvoyFilter 与 WASM 扩展](#八envoyfilter-与-wasm-扩展)
- [九、多集群 / 多控制平面](#九多集群--多控制平面)
- [十、性能调优](#十性能调优)
- [十一、生产实践清单](#十一生产实践清单)
- [十二、常见问题](#十二常见问题)
- [十三、对比其他方案](#十三对比其他方案)
- [十四、一句话总结](#十四一句话总结)
- [十五、参考](#十五参考)

---

## 一、背景：什么是 Service Mesh

### 1.1 解决什么问题

```text
微服务架构带来的问题：
  1. 服务发现：服务多了找不到
  2. 流量管理：灰度 / 限流 / 熔断 / 重试
  3. 安全：服务间 mTLS 加密、访问控制
  4. 可观测：链路追踪、Metrics、日志
  5. 故障注入：测试容错能力

传统做法：每个语言都实现一遍（Spring Cloud / Dubbo / gRPC 各自一套）
  → 多语言要重复造轮子
  → 业务代码耦合基础设施

Service Mesh 思路：
  → 把这些能力从应用层抽出来
  → 放到独立的 Sidecar 代理（Envoy）
  → 应用无感知，业务代码不变
  → 控制平面统一管控（Istiod）
```

### 1.2 Sidecar 模式

```text
传统部署：
  Pod = 应用容器
  Pod 与 Pod 之间：直接走网络

Sidecar 部署：
  Pod = 应用容器 + Envoy Sidecar
  Pod 内：所有进出流量都过 Envoy
  Pod 与 Pod 之间：经过两次 Envoy（发送方 + 接收方）

  ┌────────────────────────┐
  │       Pod              │
  │  ┌──────┐  ┌────────┐  │
  │  │ App  │←→│ Envoy  │  │ ← Sidecar
  │  └──────┘  └────────┘  │
  └────────────┬───────────┘
               │
               ▼ (127.0.0.1:15001)
            [Envoy Sidecar]   ← 接收方 Pod 同理
               │
               ▼
           上游服务
```

### 1.3 为什么需要 Sidecar

```text
✅ 业务无侵入：所有能力在 Sidecar 实施
✅ 多语言统一：Java / Go / Python / Node 都能用
✅ 集中管控：在控制面统一下发策略
✅ 灰度发布：流量切分不用改业务代码
✅ mTLS：自动加密服务间通信

代价：
  ❌ 资源开销：每个 Pod 多 50-100m CPU、40-100M 内存
  ❌ 延迟增加：每跳 +1-3ms（sidecar 转发）
  ❌ 复杂度：运维一套新基础设施
  ❌ 调试：链路多一跳，排查更复杂
```

---

## 二、Istio 架构

### 2.1 整体架构图

```text
┌──────────────────────────────────────────────────────┐
│                  Istiod (控制平面)                    │
│                                                      │
│  ┌────────────┐  ┌────────────┐  ┌───────────────┐  │
│  │  Pilot     │  │  Citadel   │  │  Galley       │  │
│  │ 流量管理   │  │ 证书 / 安全│  │ 配置校验      │  │
│  └────────────┘  └────────────┘  └───────────────┘  │
│                                                      │
│  功能：xDS 协议下发配置到 Envoy                       │
└──────────────────┬───────────────────────────────────┘
                   │ xDS API (mTLS)
                   ▼
┌──────────────────────────────────────────────────────┐
│                  数据平面 (Data Plane)                │
│                                                      │
│   Pod A                Pod B                Pod C    │
│  ┌────────┐           ┌────────┐           ┌────────┐│
│  │App+Env │←───→     │App+Env │←───→     │App+Env ││
│  └────────┘           └────────┘           └────────┘│
│       ↑ mTLS 加密 + 流量策略 + 遥测                   │
└──────────────────────────────────────────────────────┘
```

### 2.2 核心组件

| 组件 | 角色 | 现状 |
| --- | --- | --- |
| **istiod** | 控制平面（v1.5+ 合并了 Pilot/Citadel/Galley） | 核心组件 |
| **Envoy** | 数据平面 Sidecar 代理 | C++ 写的高性能代理 |
| **Ingress Gateway** | 南北流量入口（替代 K8s Ingress） | 独立 Pod |
| **Egress Gateway** | 出网流量出口（可选） | 独立 Pod |
| **Operator** | 安装 / 升级 Istio 自身 | 可选 |

### 2.3 xDS 协议

```text
xDS = LDS / RDS / CDS / EDS / SDS 等一组配置发现协议
  LDS (Listener Discovery Service)    监听器配置
  RDS (Route Discovery Service)       路由配置
  CDS (Cluster Discovery Service)     上游集群配置
  EDS (Endpoint Discovery Service)    端点发现
  SDS (Secret Discovery Service)      TLS 证书

Istiod 通过 xDS 把配置实时推送到所有 Envoy
Envoy 热加载，无需重启
```

### 2.4 两种安装模式

```text
1. Sidecar 注入模式（默认）
   - 每个业务 Pod 注入 Envoy sidecar
   - 流量劫持通过 iptables / init container
   - 资源开销大但功能完整

2. Ambient 模式（v1.18+ 实验性）
   - 用 ztunnel (L4 代理) + waypoint (L7 代理) 替代 Sidecar
   - 不再每个 Pod 注入代理
   - 资源开销小（避免 100% sidecar 浪费）
   - 生产还不稳定
```

---

## 三、安装部署

### 3.1 前置要求

```text
K8s 版本：1.24+（v1.20+ 都行）
资源：
  - istiod：1C 1G 起
  - 每 Pod sidecar：50-100m CPU、40-100M 内存
  - 100 Pod 集群：额外预留 5-10C 4-8G
网络：
  - K8s CNI 正常（Calico / Cilium / Flannel 都行）
  - 不要用 NetworkPolicy 完全锁死（Istio 需要通信）
```

### 3.2 三种安装方式

#### 方式 1：istioctl（最常用）

```bash
# 1. 下载
curl -L https://istio.io/downloadIstio | sh -
cd istio-1.22.*
export PATH=$PWD/bin:$PATH

# 2. 安装（demo profile，包含所有组件）
istioctl install --set profile=demo -y

# 其他 profile：
#   default       生产推荐（核心组件）
#   demo          全功能（带 Prometheus / Grafana / Kiali / Jaeger）
#   minimal       最少（只有 istiod）
#   ambient       实验性 ambient 模式

# 3. 给 namespace 启用 sidecar 自动注入
kubectl label namespace default istio-injection=enabled

# 4. 验证
kubectl get pods -n istio-system
# 看到 istiod、ingressgateway 等
```

#### 方式 2：Helm

```bash
# 1. 加仓库
helm repo add istio https://istio-release.storage.googleapis.com/charts
helm repo update

# 2. 创建 istio-system namespace
kubectl create namespace istio-system

# 3. 装 base
helm install istio-base istio/base -n istio-system

# 4. 装 istiod
helm install istiod istio/istiod -n istio-system \
  --set meshConfig.accessLogFile=/dev/stdout

# 5. 装 ingress gateway
helm install istio-ingress istio/gateway -n istio-system

# 6. 启用 sidecar 注入
kubectl label namespace default istio-injection=enabled
```

#### 方式 3：Operator

```bash
# 装 istio-operator
kubectl apply -f https://github.com/istio-ecosystem/sail-operator/releases/latest/download/sail-operator.yaml

# 自定义 CR 安装
cat <<EOF | kubectl apply -f -
apiVersion: sailoperator.io/v1
kind: Istio
metadata:
  name: default
spec:
  version: v1.22.0
  namespace: istio-system
  profile: default
EOF
```

### 3.3 验证安装

```bash
# 1. 组件跑起来
kubectl get pods -n istio-system
# NAME                                READY   STATUS
# istiod-xxxx                         1/1     Running
# istio-ingressgateway-xxxx            1/1     Running

# 2. istioctl 分析
istioctl analyze

# 3. 部署一个测试应用
kubectl apply -f samples/httpbin/httpbin.yaml
kubectl apply -f samples/sleep/sleep.yaml

# 4. 测试
kubectl exec deploy/sleep -- curl httpbin:8000/get
# 应该有 200 响应 + X-Envoy-Peer-Metadata 等 Istio 注入的 header

# 5. 验证 sidecar 注入
kubectl get pod -l app=httpbin -o jsonpath='{.items[0].spec.containers[*].name}'
# 应该是 "httpbin istio-proxy"（两个容器）
```

### 3.4 升级

```bash
# 1. 下载新版本 istioctl
# 2. 验证升级兼容性
istioctl x precheck

# 3. 执行升级
istioctl upgrade --set profile=default

# 4. 验证
istioctl analyze
```

---

## 四、核心 CRD 资源总览

### 4.1 一张图看 Istio CRD

```text
┌──────────────────────────────────────────────────────────┐
│                    Istio CRD 体系                        │
│                                                          │
│  流量管理                                                │
│  ├─ VirtualService      路由规则（最常用）              │
│  ├─ DestinationRule     上游策略（负载均衡 / 熔断）      │
│  ├─ Gateway             网关入口                          │
│  ├─ ServiceEntry        网格外部服务                      │
│  └─ Sidecar             Sidecar 自定义（默认行为）        │
│                                                          │
│  安全                                                    │
│  ├─ PeerAuthentication  mTLS 模式（命名空间级）           │
│  ├─ AuthorizationPolicy 访问控制（RBAC 风格）             │
│  └─ RequestAuthentication JWT 校验                       │
│                                                          │
│  可观测性                                                │
│  └─ Telemetry           Metrics/Trace 配置               │
│                                                          │
│  高级                                                    │
│  └─ EnvoyFilter         自定义 Envoy 配置                 │
│      WasmPlugin         WASM 扩展插件                    │
└──────────────────────────────────────────────────────────┘
```

### 4.2 资源关系图

```text
                      Gateway (入口)
                          ↓
                  VirtualService (路由规则)
                          ↓
                   DestinationRule (上游策略)
                          ↓
                   Service (K8s Service)
                          ↓
                   Pod + Envoy sidecar

ServiceEntry:  网格外部服务（注册到网格里）
Sidecar:      限制 Sidecar 能看到的服务（默认全网格可见）
```

---

## 五、流量管理

### 5.1 VirtualService（最常用）

```yaml
# bookinfo 应用：reviews 服务有 3 个版本（v1/v2/v3）
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: reviews
  namespace: default
spec:
  hosts:
  - reviews                            # 匹配 Service 名
  http:
  - match:
    - headers:
        end-user:                      # 根据 header 路由
          exact: jason
    route:
    - destination:
        host: reviews
        subset: v2                      # jason 走 v2 版本
  - route:
    - destination:
        host: reviews
        subset: v1                      # 其他用户走 v1
      weight: 90
    - destination:
        host: reviews
        subset: v3
      weight: 10                        # 10% 走 v3（金丝雀）
```

**VirtualService 主要能力**：

```text
路由匹配（match）：
  - by URI（prefix / exact / regex）
  - by Header
  - by Query Param
  - by Source Label
  - by Source IP
  - by Method (GET / POST)

路由目标（route）：
  - weight：按权重分流（灰度发布核心）
  - destination：目标服务 + subset

流量行为（http 级别）：
  - retries：重试次数 + 超时 + 重试条件
  - timeout：超时时间
  - fault：注入故障（abort / delay，测试用）
  - mirror：流量镜像（不影响主链路）
  - corsPolicy：CORS 跨域
  - rewrite：URI 重写
```

### 5.2 DestinationRule

```yaml
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: reviews
spec:
  host: reviews
  trafficPolicy:                       # 默认策略
    connectionPool:
      tcp:
        maxConnections: 100            # 最大连接数
      http:
        h2UpgradePolicy: UPGRADE       # 升级到 HTTP/2
        maxRequestsPerConnection: 10
    outlierDetection:                  # 熔断 / 异常点检测
      consecutive5xxErrors: 5          # 连续 5xx 次数
      interval: 30s                    # 检测窗口
      baseEjectionTime: 30s            # 摘除时长
      maxEjectionPercent: 50           # 最多摘除 50%
    loadBalancer:
      simple: LEAST_CONN               # 负载均衡算法
      # RANDOM / LEAST_CONN / ROUND_ROBIN / PASSTHROUGH
  subsets:                             # 版本定义（按 label 选 Pod）
  - name: v1
    labels:
      version: v1
  - name: v2
    labels:
      version: v2
  - name: v3
    labels:
      version: v3
```

### 5.3 Gateway（南北流量入口）

```yaml
apiVersion: networking.istio.io/v1beta1
kind: Gateway
metadata:
  name: bookinfo-gateway
spec:
  selector:
    istio: ingressgateway                # 用哪个 gateway 实例
  servers:
  - port:
      number: 80
      name: http
      protocol: HTTP
    hosts:
    - bookinfo.example.com
  - port:
      number: 443
      name: https
      protocol: HTTPS
    tls:
      mode: SIMPLE
      credentialName: bookinfo-cert      # 证书 secret 名
    hosts:
    - bookinfo.example.com
---
# 绑定 VS 到 Gateway
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: bookinfo
spec:
  hosts:
  - bookinfo.example.com
  gateways:
  - bookinfo-gateway                    # 关联到上面那个 Gateway
  http:
  - match:
    - uri:
        prefix: /reviews
    route:
    - destination:
        host: reviews
        subset: v2
```

### 5.4 灰度发布完整示例

```text
阶段一：5% 流量给 v2
阶段二：50% 流量给 v2
阶段三：100% 流量给 v2
阶段四：v1 下线
```

```yaml
# VS + DR 配合
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: myapp
spec:
  hosts:
  - myapp
  http:
  - route:
    - destination:
        host: myapp
        subset: v1
      weight: 95                         # 95% v1
    - destination:
        host: myapp
        subset: v2
      weight: 5                          # 5% v2（金丝雀）
---
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: myapp
spec:
  host: myapp
  subsets:
  - name: v1
    labels: { version: v1 }
  - name: v2
    labels: { version: v2 }
```

### 5.5 流量镜像（不影响主链路）

```yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: mirror-test
spec:
  hosts:
  - httpbin
  http:
  - route:
    - destination:
        host: httpbin
        subset: v1
  mirror:
    host: httpbin
    subset: v2                          # 100% 流量镜像到 v2
  mirrorPercentage:
    value: 100.0
```

```text
用途：
  - 新版本上线前用真实流量验证（不发响应回客户端）
  - 性能 / 正确性测试
  - 数据回放
```

### 5.6 故障注入（测试用）

```yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: ratings
spec:
  hosts:
  - ratings
  http:
  - fault:
      delay:
        percentage:
          value: 10                      # 10% 概率
        fixedDelay: 5s                   # 延迟 5 秒
      abort:
        percentage:
          value: 5                       # 5% 概率
        httpStatus: 500                  # 直接 500
    route:
    - destination:
        host: ratings
```

```text
用途：
  - 测试应用的容错 / 重试 / 降级能力
  - 测试监控告警
  - 仅在测试环境开
```

### 5.7 超时 / 重试 / 限流

```yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: myapp
spec:
  hosts: [myapp]
  http:
  - timeout: 5s                          # 单请求超时
    retries:
      attempts: 3
      perTryTimeout: 1s                  # 单次重试超时
      retryOn: 5xx,reset,connect-failure
      retryRemoteLocalities: true
    route:
    - destination:
        host: myapp
---
# 限流（用 DestinationRule）
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: myapp
spec:
  host: myapp
  trafficPolicy:
    connectionPool:
      http:
        http1MaxPendingRequests: 100     # HTTP/1.1 最大等待数
        http2MaxRequests: 1000          # HTTP/2 最大请求数
        maxRequestsPerConnection: 10
        maxRetries: 3                    # 最大重试
      tcp:
        maxConnections: 100
        connectTimeout: 30ms
        tcpKeepalive:
          time: 60s
          interval: 30s
```

---

## 六、安全（mTLS / AuthorizationPolicy）

### 6.1 mTLS（mutual TLS）双向认证

```text
传统 TLS：客户端验证服务端证书（单向）
mTLS：客户端和服务端互相验证（双向）

Istio 里的 mTLS：
  - 服务间通信自动加密
  - 不需要应用感知（透明）
  - 基于 SPIFFE 身份标识（spiffe://cluster.local/ns/default/sa/sleep）
```

**PeerAuthentication（控制 mTLS 模式）**：

```yaml
# 整个网格开启 STRICT mTLS
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default
  namespace: istio-system
spec:
  mtls:
    mode: STRICT
---
# 某个 namespace 关闭 mTLS（兼容老服务）
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: legacy
  namespace: legacy-ns
spec:
  mtls:
    mode: PERMISSIVE                     # 允许明文 + mTLS
    # mode: DISABLE                     # 完全关闭
    # mode: STRICT                      # 强制 mTLS
```

**mTLS 三种模式**：

| 模式 | 行为 | 适用 |
| --- | --- | --- |
| DISABLE | 强制明文（拒绝 mTLS） | 调试 |
| PERMISSIVE | 既接受 mTLS 也接受明文 | 灰度迁移期 |
| STRICT | 强制 mTLS（拒绝明文） | 生产（默认推荐） |

### 6.2 AuthorizationPolicy（RBAC 访问控制）

```yaml
# 允许：reviews 服务被 productpage 访问
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: allow-reviews
  namespace: default
spec:
  selector:
    matchLabels:
      app: reviews                       # 作用在 reviews 服务
  action: ALLOW
  rules:
  - from:
    - source:
        principals:
        - cluster.local/ns/default/sa/bookinfo-productpage
    to:
    - operation:
        methods: ["GET"]
        paths: ["/api/v1/*"]
```

**更严格的策略（默认拒绝 + 显式允许）**：

```yaml
# 1. 默认拒绝所有
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: deny-all
  namespace: default
spec:
  {}                                    # 空 spec 表示拒绝所有
---
# 2. 显式允许某些
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: allow-frontend-to-api
spec:
  action: ALLOW
  rules:
  - from:
    - source:
        principals: ["cluster.local/ns/default/sa/frontend"]
    to:
    - operation:
        methods: ["GET", "POST"]
        paths: ["/api/*"]
```

### 6.3 RequestAuthentication（JWT 验证）

```yaml
apiVersion: security.istio.io/v1beta1
kind: RequestAuthentication
metadata:
  name: jwt-auth
  namespace: default
spec:
  selector:
    matchLabels:
      app: api
  jwtRules:
  - issuer: "https://auth.example.com"
    jwksUri: "https://auth.example.com/.well-known/jwks.json"
    forwardOriginalToken: true
```

---

## 七、可观测性

### 7.1 Kiali（服务网格可视化）

```bash
# demo profile 默认装 Kiali
istioctl install --set profile=demo -y

# 端口转发访问
kubectl port-forward -n istio-system svc/kiali 20001:20001
# 浏览器打开 http://localhost:20001
```

```text
Kiali 提供：
  - 服务拓扑图
  - 流量实时监控
  - 配置健康检查
  - 错误率 / 延迟可视化
```

### 7.2 Prometheus + Grafana（指标）

```bash
# demo profile 自带
istioctl install --set profile=demo -y

# 端口转发
kubectl port-forward -n istio-system svc/grafana 3000:3000
kubectl port-forward -n istio-system svc/prometheus 9090:9090
```

**关键 Istio 指标**：

```promql
# 请求总量
istio_requests_total{destination_service=~"myapp.*"}

# 错误率
sum(rate(istio_requests_total{response_code=~"5.."}[5m]))
/
sum(rate(istio_requests_total[5m]))

# P99 延迟
histogram_quantile(0.99,
  sum(rate(istio_request_duration_milliseconds_bucket[5m])) by (le, destination_service)
)

# mTLS 流量比例
sum(rate(istio_requests_total{context_protocol="grpc"}[5m])) by (response_code)
```

### 7.3 Jaeger / Zipkin（链路追踪）

```bash
# demo profile 自带 Jaeger
kubectl port-forward -n istio-system svc/tracing 16686:16686
# 浏览器打开 http://localhost:16686
```

```text
Istio 自动注入 trace header：
  - x-request-id
  - x-b3-traceid
  - x-b3-spanid
  - x-b3-parentspanid
  - x-b3-sampled
  - x-ot-span-context

无需应用代码改动
但应用要能传递这些 header（Spring Boot / Express 默认就传）
```

### 7.4 Envoy 访问日志

```yaml
# istiod 配置
apiVersion: v1
kind: ConfigMap
metadata:
  name: istio
  namespace: istio-system
data:
  mesh: |
    accessLogFile: "/dev/stdout"        # 开启访问日志
    accessLogFormat: |
      [%START_TIME%] "%REQ(:METHOD)% %REQ(PATH)% %PROTOCOL%"
      %RESPONSE_CODE% %RESPONSE_FLAGS% %BYTES_RECEIVED% %BYTES_SENT%
      %DURATION% %UPSTREAM_HOST%
```

### 7.5 Telemetry CRD（v1.20+）

```yaml
apiVersion: telemetry.istio.io/v1alpha1
kind: Telemetry
metadata:
  name: namespace-metrics
  namespace: istio-system
spec:
  selector:
    matchLabels:
      app: myapp
  metrics:
  - providers:
    - name: prometheus
    overrides:
    - match:
        metric: REQUEST_COUNT
      tagOverrides:
        request_host:
          value: "%%HOST%%"
```

---

## 八、EnvoyFilter 与 WASM 扩展

### 8.1 EnvoyFilter 概念

```text
EnvoyFilter = 直接给 Envoy 注入自定义配置
适用场景：
  - 标准 Istio CRD 表达不了的高级配置
  - 添加自定义 HTTP filter
  - 修改现有 filter 的参数
  - 注入 Lua 脚本做定制逻辑

⚠️ 危险：
  - 直接改 Envoy 配置，容易搞坏
  - 版本升级可能不兼容
  - 不推荐作为常规方案
```

### 8.2 EnvoyFilter 示例

```yaml
# 给 productpage 添加自定义 response header
apiVersion: networking.istio.io/v1alpha1
kind: EnvoyFilter
metadata:
  name: add-header
  namespace: default
spec:
  configPatches:
  - applyTo: HTTP_FILTER
    match:
      context: SIDECAR_OUTBOUND          # 出栈方向
      listener:
        filterChain:
          filter:
            name: envoy.filters.network.http_connection_manager
            subFilter:
              name: envoy.filters.http.router
    patch:
      operation: INSERT_BEFORE
      value:
        name: envoy.filters.http.lua
        typed_config:
          "@type": type.googleapis.com/envoy.extensions.filters.http.lua.v3.Lua
          inlineCode: |
            function envoy_on_response(response_handle)
              response_handle:headers():add("X-Custom-Header", "istio-custom")
            end
```

### 8.3 WasmPlugin（v1.18+ 推荐替代 EnvoyFilter）

```text
WasmPlugin = 用 WASM 写 Envoy 扩展
优势：
  - 性能更好（编译为 native）
  - 更安全（沙箱）
  - 多语言支持（Rust / AssemblyScript / C++ / Go）
  - 热加载（不用重启 Pod）
```

```yaml
apiVersion: extensions.istio.io/v1alpha1
kind: WasmPlugin
metadata:
  name: add-header
  namespace: default
spec:
  selector:
    matchLabels:
      app: myapp
  url: oci://registry.example.com/wasm-plugins/add-header:1.0.0
  phase: AUTHN
  priority: 1000
```

### 8.4 常用 Wasm 插件生态

```text
- HTTP Header 修改
- 自定义认证
- 自定义限流
- 业务级 Metrics
- 数据脱敏
- 请求 / 响应改写
```

---

## 九、多集群 / 多控制平面

### 9.1 多集群模式

```text
模式 1：单控制平面（Primary-Remote）
  - 一个 istiod 主集群，其他集群为 Remote
  - 所有集群共享同一个控制平面
  - 资源开销小，但单点故障

模式 2：多控制平面（Multi-Primary）
  - 每个集群独立 istiod
  - 跨集群通过 ServiceEntry / Gateway
  - 隔离好但运维复杂

模式 3：East-West Gateway
  - 集群间通过专门的 Gateway 通信
  - 跨集群 mTLS + 流量策略
  - 生产推荐
```

### 9.2 East-West Gateway 配置

```yaml
# 1. 在每个集群装一个 eastwest gateway
istioctl install \
  --set profile=demo \
  --set values.global.meshID=mesh1 \
  --set values.global.network=network1 \
  --set values.global.multiCluster.clusterName=cluster1

# 2. 暴露 eastwest gateway 服务
kubectl apply -f samples/multicluster/expose-services.yaml
```

### 9.3 外部服务接入（ServiceEntry）

```yaml
# 把外部 API 注册到网格里
apiVersion: networking.istio.io/v1beta1
kind: ServiceEntry
metadata:
  name: external-api
spec:
  hosts:
  - api.external.com
  ports:
  - number: 443
    name: https
    protocol: HTTPS
  resolution: DNS
  location: MESH_EXTERNAL
```

---

## 十、性能调优

### 10.1 sidecar 资源调整

```yaml
# 给 namespace 配默认值
apiVersion: v1
kind: ConfigMap
metadata:
  name: istio-sidecar-injector
  namespace: istio-system
data:
  values: |
    global:
      proxy:
        resources:
          requests:
            cpu: 50m
            memory: 64Mi
          limits:
            cpu: 200m
            memory: 256Mi
```

### 10.2 Sidecar 资源（按服务裁剪）

```yaml
# Sidecar 限制只看到需要的服务
apiVersion: networking.istio.io/v1beta1
kind: Sidecar
metadata:
  name: myapp-sidecar
  namespace: default
spec:
  egress:
  - hosts:
    - "./myapp"                          # 只允许访问同 namespace 的 myapp
    - "./redis/*"                        # 整个 redis namespace
    - "istio-system/*"                   # istio-system 所有服务
  ingress:
  - port:
      number: 8080
    defaultEndpoint: 127.0.0.1:8080
```

```text
效果：
  - Sidecar 配置减少 90%+
  - 启动加速
  - 内存占用减少
  - xDS 推送量减少
```

### 10.3 关闭访问日志（默认就是关闭）

```yaml
# mesh config
apiVersion: v1
kind: ConfigMap
metadata:
  name: istio
  namespace: istio-system
data:
  mesh: |
    accessLogFile: ""                    # 关闭访问日志
    enableAutoMtls: true
    defaultConfig:
      proxyStatsMatcher:
        inclusionRegexps:
        - .*                            # 全量 metrics
        - "tcp.*"
        - "http.*"
        exclusionRegexps:
        - "cluster\\..*outlier.*"
        - "cluster\\..*upstream_rq_retry.*"
```

### 10.4 流量路径优化

```text
优化前：App → Envoy(Same Pod) → Envoy(other Pod) → App
        2 次 Envoy 跳转，每跳 +1ms

优化（Ambient 模式）：
  App → ztunnel → App
  L4 直接转发，延迟更低

优化（Sidecar 模式）：
  - 业务不用 Envoy 转发时，可以 service mesh 在 Pod 内直连
  - 减少不必要的 outbound
```

### 10.5 调优清单

```text
✅ Sidecar 资源合理（按 namespace 调）
✅ 限制 Sidecar 能看到的服务（Sidecar CRD）
✅ 关闭不必要的访问日志
✅ metrics 采样率
✅ 减少 xDS 推送量
✅ 升级到最新版本（持续性能优化）
✅ Ambient 模式（v1.18+ 试点）
```

---

## 十一、生产实践清单

```text
部署前：
  ☐ K8s 版本 ≥ 1.24
  ☐ 计算资源预留（sidecar 开销）
  ☐ 镜像 / Helm 准备
  ☐ 选好 profile（default / demo）
  ☐ 网关节点规划（独立节点池）

部署中：
  ☐ 先小范围 namespace 试点
  ☐ 灰度注入：先 manual injection
  ☐ 关键服务加 DestinationRule
  ☐ 配 mTLS（先 PERMISSIVE，再 STRICT）
  ☐ 接 Prometheus / Grafana
  ☐ 配告警（5xx 率 / 延迟 / 错误注入）

部署后：
  ☐ 跑回归测试
  ☐ 观察 Sidecar 资源
  ☐ 调优 xDS 推送
  ☐ Sidecar 限制（Sidecar CRD）
  ☐ 文档化：哪些 namespace 启用了 mesh

日常：
  ☐ 升级 istioctl
  ☐ 检查 Kiali 健康状态
  ☐ 检查 mTLS 状态
  ☐ 监控控制平面（istiod）资源
```

---

## 十二、常见问题

### 12.1 Pod 起不来 / 没有 sidecar

```text
排查：
  1. namespace 标签对吗？
     kubectl get ns <ns> --show-labels | grep istio-injection
  2. 重启已有 Pod 才会注入
     kubectl rollout restart deploy -n <ns>
  3. webhook 配了吗？
     kubectl get mutatingwebhookconfigurations | grep istio
```

### 12.2 mTLS 通信失败

```text
症状：
  - 5xx 错误
  - "SSL handshake failed" 错误

排查：
  1. mTLS 模式配对吗？
     kubectl get peerauthentication -A
  2. 目标服务的端口协议是 HTTP/1.1 吗？
     mTLS 走 HTTP/2 最好
  3. 证书过期了吗？
     检查 istiod 日志
  4. 临时改 PERMISSIVE 验证
```

### 12.3 xDS 推送慢 / 配置不生效

```bash
# 看 envoy 配置
istioctl proxy-config routes <pod-name>
istioctl proxy-config clusters <pod-name>
istioctl proxy-config listeners <pod-name>

# 看 xDS 推送状态
istioctl proxy-status
```

### 12.4 性能问题

```text
1. 延迟增加？
   - 检查 sidecar 资源
   - 是不是 ambient 模式试点
   - 看 P99 分布

2. 资源占用高？
   - Sidecar CRD 限制可见服务
   - 关闭 access log
   - 调小 metrics 收集

3. 启动慢？
   - Sidecar 等控制平面下配置（xDS）
   - 加 readiness probe 不阻塞流量
```

### 12.5 升级后不兼容

```bash
# 1. 预检
istioctl x precheck

# 2. 看 CRD 是否过期
kubectl get crd | grep istio.io

# 3. 渐进升级：先升级 control plane，再重启 data plane
istioctl upgrade
kubectl rollout restart deploy -n <ns>
```

---

## 十三、对比其他方案

### 13.1 Service Mesh 选型对比

| 特性 | Istio | Linkerd | Consul Connect | Cilium Service Mesh |
| --- | --- | --- | --- | --- |
| 数据面 | Envoy | Linkerd2-proxy | Envoy | Envoy (无 sidecar) |
| 控制面 | istiod | controller | Consul Server | Cilium Agent |
| 性能 | 中 | 高（Rust 写的） | 中 | 高（eBPF） |
| 功能完整度 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| 易用性 | 中 | 高 | 中 | 中 |
| 社区 | 最大 | 中 | 中 | 大 |
| 多语言 | ✅ | ✅ | ✅ | ✅ |
| 多集群 | ✅ | ✅ | ✅ | ✅ |
| mTLS | ✅ | ✅ | ✅ | ✅ |
| WASM 扩展 | ✅ | ❌ | ❌ | ❌ |

### 13.2 Istio vs 应用层方案

| 维度 | Spring Cloud | Dubbo | Istio |
| --- | --- | --- | --- |
| 语言 | Java | Java | 任意 |
| 部署 | 代码集成 | 代码集成 | Sidecar 注入 |
| 升级 | 重打包 | 重打包 | 重启 Pod |
| 性能 | 高（无 sidecar） | 高 | 中（有 sidecar） |
| 多语言 | ❌ | ❌ | ✅ |
| 灰度 | 需要代码 | 需要代码 | 配置 |
| mTLS | 自己集成 | 自己集成 | 自动 |

### 13.3 什么时候用 / 不用 Istio

```text
✅ 用：
  - 微服务 ≥ 10 个
  - 多语言
  - 需要 mTLS / 零信任
  - 需要灰度 / 流量管理
  - 可观测性要求高
  - 大厂、有专门 SRE 团队

❌ 不用：
  - 微服务 ≤ 5 个
  - 单语言（用 Spring Cloud / Dubbo 更顺手）
  - 资源极度敏感（嵌入式 / 边缘）
  - 团队没 service mesh 经验
  - 业务很简单
```

---

## 十四、一句话总结

> **Istio = Envoy Sidecar（数据面）+ istiod（控制面）= 把服务间通信的流量 / 安全 / 观测统一接管**；
> 用 VirtualService + DestinationRule 配灰度、用 PeerAuthentication + AuthorizationPolicy 配 mTLS 和零信任；
> 资源开销 +1-3ms 延迟、每 Pod 多 50-100m CPU，但换来多语言统一 + 集中管控。

---

## 十五、参考

- [Istio 官方文档](https://istio.io/latest/docs/)
- [Istio 安装指南](https://istio.io/latest/docs/setup/install/)
- [VirtualService 详解](https://istio.io/latest/docs/reference/config/networking/virtual-service/)
- [DestinationRule 详解](https://istio.io/latest/docs/reference/config/networking/destination-rule/)
- [Authorization Policy](https://istio.io/latest/docs/reference/config/security/authorization-policy/)
- [Ambient Mesh（v1.18+）](https://istio.io/latest/docs/ambient/)
- [istioctl 命令参考](https://istio.io/latest/docs/reference/commands/istioctl/)
- [Kiali](https://kiali.io/)
- [WasmPlugin CRD](https://istio.io/latest/docs/reference/config/proxy_extensions/wasm_plugin/)
