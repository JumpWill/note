# Istio

最流行的开源 Service Mesh，基于 Envoy 数据面 + Istiod 控制面。提供 mTLS、流量管理、可观测、安全四大支柱，是云原生微服务的标准 Mesh。

## 一、定位与特点

- 完整 Service Mesh：流量 + 安全 + 可观测 + 策略
- 数据面：Envoy（Sidecar / Ambient）
- 控制面：Istiod（Pilot + Citadel + Galley）
- 多协议：HTTP / gRPC / TCP / WebSocket
- Ambient Mesh（无 Sidecar，新趋势）
- WASM 扩展（EnvoyFilter）
- 多集群、多云支持

## 二、架构

```text
┌────────────────────────────────────┐
│  Service A Pod                     │
│   ┌─────────────────┐              │
│   │ App Container   │              │
│   └────────┬────────┘              │
│            │                        │
│   ┌────────▼────────┐              │
│   │ Envoy Sidecar   │◄── mTLS ────┼──► Service B Pod
│   └────────┬────────┘              │   ┌─────────────────┐
└────────────┼───────────────────────┘   │ App Container   │
             │                            └────────┬────────┘
             │                                     │
             ▼                                     ▼
┌────────────────────────────────────────────────────────────┐
│                    Istiod (Control Plane)                   │
│   - Pilot (xDS)                                            │
│   - Citadel (证书 / mTLS)                                  │
│   - Galley (配置校验)                                       │
└──────┬──────────────────────────┬──────────────────────────┘
       │                          │
       ▼                          ▼
   K8s API Server           CA (证书签发)
```

两种模式：

- **Sidecar**：每个 Pod 一个 Envoy
- **Ambient**：ztunnel（节点级）+ waypoint（工作负载级）

## 三、核心概念

| 概念 | 含义 |
| --- | --- |
| **VirtualService** | 路由规则（类似 ingress + 流量切分） |
| **DestinationRule** | 上游流量策略（负载均衡、熔断、TLS） |
| **Gateway** | 入口网关 |
| **ServiceEntry** | 外部服务注册到 Mesh |
| **Sidecar** | Sidecar 资源（限定 Envoy 范围） |
| **AuthorizationPolicy** | 鉴权策略 |
| **PeerAuthentication** | mTLS 策略 |
| **RequestAuthentication** | JWT 验签 |
| **Telemetry** | 可观测配置 |

## 四、部署

### 1. istioctl 安装

```bash
# 下载
curl -L https://istio.io/downloadIstio | sh -
cd istio-*
export PATH=$PWD/bin:$PATH

# 安装（demo profile）
istioctl install --set profile=demo -y

# 安装（生产 profile）
istioctl install --set profile=production -y
```

### 2. Helm 安装

```bash
helm repo add istio https://istio-release.storage.googleapis.com/charts
helm install istio-base istio/base -n istio-system
helm install istiod istio/istiod -n istio-system --wait
helm install istio-ingress istio/gateway -n istio-ingress
```

### 3. 启用 Sidecar 注入

```bash
kubectl label namespace default istio-injection=enabled
```

新建 Pod 自动注入 Envoy。

### 4. Ambient Mesh

```bash
istioctl install --set profile=ambient -y
kubectl label namespace default istio.io/dataplane-mode=ambient
```

## 五、流量管理

### 1. VirtualService（路由）

```yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: my-app
spec:
  hosts:
    - my-app
  http:
    - match:
        - uri:
            prefix: /api
      route:
        - destination:
            host: my-app
            subset: v2
          weight: 90
        - destination:
            host: my-app
            subset: v1
          weight: 10
      retries:
        attempts: 3
        perTryTimeout: 2s
        retryOn: 5xx,reset
      fault:
        delay:
          percentage:
            value: 0.1
          fixedDelay: 5s
```

### 2. DestinationRule（流量策略）

```yaml
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: my-app
spec:
  host: my-app
  trafficPolicy:
    connectionPool:
      tcp:
        maxConnections: 100
      http:
        h2UpgradePolicy: UPGRADE
        maxRequestsPerConnection: 10
    outlierDetection:
      consecutive5xxErrors: 5
      interval: 30s
      baseEjectionTime: 30s
  subsets:
    - name: v1
      labels: { version: v1 }
    - name: v2
      labels: { version: v2 }
```

### 3. 灰度发布

```text
流量 100% ─┬─ v1: 90%
           └─ v2: 10%

逐步调整 → v1: 0%, v2: 100%
```

### 4. 流量镜像

```yaml
http:
  - route:
      - destination:
          host: my-app
          subset: v1
    mirror:
      host: my-app
      subset: debug
    mirrorPercentage:
      value: 100
```

真实流量镜像到 debug 版本，不影响响应。

### 5. 故障注入

```yaml
fault:
  abort:
    httpStatus: 503
    percentage: { value: 50 }
  delay:
    fixedDelay: 5s
    percentage: { value: 10 }
```

测试容错。

## 六、入口网关

### 1. Gateway

```yaml
apiVersion: networking.istio.io/v1beta1
kind: Gateway
metadata:
  name: my-gateway
spec:
  selector:
    istio: ingressgateway
  servers:
    - port:
        number: 443
        name: https
        protocol: HTTPS
      tls:
        mode: SIMPLE
        credentialName: my-cert
      hosts:
        - app.example.com
```

### 2. Gateway + VirtualService

```yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: my-app
spec:
  hosts:
    - app.example.com
  gateways:
    - my-gateway
  http:
    - route:
        - destination:
            host: my-app
            port: { number: 80 }
```

### 3. Gateway 类型

| 类型 | Selector |
| --- | --- |
| **Ingress** | `istio: ingressgateway` |
| **Egress** | `istio: egressgateway` |
| **Custom** | 自定义 label |

## 七、安全 (mTLS + AuthZ)

### 1. 全局 mTLS

```yaml
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default
  namespace: istio-system
spec:
  mtls:
    mode: STRICT
```

模式：

- **DISABLE**：明文
- **PERMISSIVE**：兼容
- **STRICT**：强制 mTLS

### 2. 命名空间级 mTLS

```yaml
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default
  namespace: ns-a
spec:
  mtls:
    mode: STRICT
```

### 3. AuthorizationPolicy

```yaml
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: allow-read
  namespace: ns-a
spec:
  selector:
    matchLabels:
      app: my-app
  rules:
    - from:
        - source:
            principals: ["cluster.local/ns-a/sa/reader"]
      to:
        - operation:
            methods: ["GET"]
```

### 4. JWT 验签

```yaml
apiVersion: security.istio.io/v1beta1
kind: RequestAuthentication
metadata:
  name: jwt-auth
spec:
  selector:
    matchLabels:
      app: my-app
  jwtRules:
    - issuer: "http://kc/realms/myrealm"
      jwksUri: "http://kc/realms/myrealm/protocol/openid-connect/certs"
```

### 5. RBAC 模型

| 维度 | 来源 |
| --- | --- |
| **主体** | K8s SA / JWT claims / request 属性 |
| **操作** | HTTP method / path / header |
| **目标** | selector 选中的 workload |

## 八、可观测

### 1. 内置指标

Envoy 自动暴露 Prometheus 指标：

```
istio_requests_total
istio_request_duration_milliseconds_bucket
istio_request_bytes_bucket
istio_response_bytes_bucket
istio_requests_total{response_code="500"}
```

### 2. 访问日志

```yaml
apiVersion: telemetry.istio.io/v1alpha1
kind: Telemetry
metadata:
  name: default
spec:
  accessLogging:
    - providers:
        - name: envoy
      filter:
        expression: 'response.code >= 400'
```

格式自定义：

```yaml
accessLogFormat: '[%START_TIME%] %REQ(:METHOD)% %REQ(X-ENVOY-ORIGINAL-PATH?:PATH)% %RESPONSE_CODE%\n'
```

### 3. Trace

支持 Zipkin / Jaeger / OpenTelemetry：

```yaml
apiVersion: telemetry.istio.io/v1alpha1
kind: Telemetry
metadata:
  name: default
spec:
  tracing:
    - randomSamplingPercentage: 100.0
      providers:
        - name: otel
```

### 4. Kiali

可视化工具：

```bash
kubectl apply -f https://raw.githubusercontent.com/istio-ecosystem/kiali/master/kiali.yaml
istioctl dashboard kiali
```

显示服务拓扑、流量、错误率。

## 九、外部服务（ServiceEntry）

```yaml
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

把外部 API 注册到 Mesh，可走 VirtualService 路由。

## 十、Sidecar 资源

```yaml
apiVersion: networking.istio.io/v1beta1
kind: Sidecar
metadata:
  name: default
  namespace: ns-a
spec:
  egress:
    - hosts:
        - "./*"
        - "istio-system/*"
  ingress:
    - defaultEndpoint: 0.0.0.0:80
```

限定 Sidecar 监听/转发范围，节省内存。

## 十一、WASM / EnvoyFilter

### 1. EnvoyFilter

```yaml
apiVersion: networking.istio.io/v1alpha1
kind: EnvoyFilter
metadata:
  name: add-header
spec:
  configPatches:
    - applyTo: HTTP_FILTER
      match:
        listener:
          filterChain:
            filter:
              name: envoy.filters.network.http_connection_manager
      patch:
        operation: INSERT_BEFORE
        value:
          name: envoy.filters.http.lua
          typed_config:
            "@type": type.googleapis.com/envoy.extensions.filters.http.lua.v3.Lua
            inlineCode: |
              function envoy_on_request(handle)
                handle:headers():add("x-istio-lua", "yes")
              end
```

### 2. WASM Filter

```bash
istioctl experimental install wasm-plugin ...
```

可用 `wasm-go` 框架编写：

```go
import "github.com/tetratelabs/proxy-wasm-go-sdk/proxywasm"

func main() {
    proxywasm.SetVMContext(&vmContext{})
}
```

## 十二、多集群

### 1. 多控制面（Multi-Primary）

每个集群独立 Istiod，相互发现：

```bash
istioctl install --set values.global.multiCluster.enabled=true \
  --set values.global.meshID=mesh1
```

### 2. 共享控制面（Primary-Remote）

一个集群的 Istiod 管理多个集群：

```bash
# Remote 集群
istioctl install --set profile=remote \
  --set values.global.remotePilotAddress=<pilot-ip>
```

## 十三、Ambient Mesh（无 Sidecar）

### 1. 架构

```text
Pod → ztunnel (节点级) → waypoint (负载级，可选) → upstream
```

- **ztunnel**：节点级 L4 代理（Rust 写，4MB）
- **waypoint**：可选 L7 代理（Envoy）

### 2. 优势

- 启动快（无 iptables 注入）
- 资源占用低
- 无 Sidecar 调试难

### 3. 现状

实验性（2024-2025），生产用 Sidecar 仍是主流。

## 十四、与 Linkerd 对比

| 维度 | Istio | Linkerd |
| --- | --- | --- |
| 数据面 | Envoy (C++) | linkerd2-proxy (Rust) |
| Sidecar | ✔ / Ambient | ✔ |
| 控制面 | Istiod | Controller |
| 性能 | 中-高 | **高** |
| 功能丰富度 | **极强** | 聚焦核心 |
| 协议 | 全 | HTTP/gRPC 优先 |
| WASM | ✔ | ❌ |
| 学习曲线 | 高 | 中 |
| mTLS | 默认开 | 默认开 |

## 十五、典型场景

- **大型微服务网格**：数百服务，需要复杂流量管理
- **多语言团队**：用 Mesh 做统一的熔断、追踪
- **多云**：跨云 Mesh 互通
- **零信任安全**：强制 mTLS + AuthZ
- **渐进式灰度**：基于 Header / 权重的精细切流

## 十六、最佳实践

- **Sidecar 注入**：命名空间级控制
- **mTLS 强制**：STRICT 模式
- **AuthorizationPolicy 渐进**：从 allowlist 开始
- **PeerAuthentication**：命名空间分级别
- **Telemetry 收敛**：避免采样 100%
- **Kiali 调试**：可视化流量
- **EnvoyFilter 谨慎**：影响所有 Pod
- **Sidecar 资源**：缩小 egress 范围
- **Gateway 单一入口**：减少攻击面
- **证书轮转**：Istiod 自动 24h 轮转
- **多集群**：从单 Primary-Remote 开始
