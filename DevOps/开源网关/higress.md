# Higress

阿里开源的下一代云原生 API Gateway，基于 Envoy + Nginx + Istio 控制面。WASM 插件是一等公民，对阿里云生态（Nacos / SLS / 阿里云 IDaaS）深度集成。

## 一、定位与特点

- Envoy 数据面 + Istio 控制面（fork 自 Istio）
- WASM 插件一等公民（Go / Rust / C++）
- 多注册中心：Nacos / Consul / K8s Service
- 多协议：HTTP / HTTPS / gRPC / Dubbo / WebSocket / Redis / MQTT
- 阿里云生态深度集成（SLS / ARMS / IDaaS）
- Gateway API 支持（Ingress 上层标准）
- Dashboard：基于开源 Higress Console

## 二、架构

```text
┌────────────────────────────────────┐
│  Client                            │
└─────────────┬──────────────────────┘
              │
              ▼
┌────────────────────────────────────┐
│  Higress Gateway (Envoy + Nginx)   │
│   - Listener                       │
│   - WASM Filter                    │
│   - Lua Filter (Nginx 兼容)        │
│   - xDS Config                     │
└─────┬──────────────────┬───────────┘
      │                  │
      ▼                  ▼
  Backend          Pilot (fork 自 Istio)
  Services         (多注册中心适配)
```

核心：

- **Envoy**：数据面（与 Istio 共享）
- **Pilot fork**：控制面，支持 K8s / Nacos / Consul
- **WASM Plugin Server**：插件运行时
- **Nginx**：兼容传统 location 语法

## 三、核心概念

| 概念 | 含义 |
| --- | --- |
| **Ingress** | K8s Ingress（兼容） |
| **Gateway API** | K8s Gateway API（推荐） |
| **McpBridge** | 多注册中心（K8s/Nacos/Consul） |
| **WasmPlugin** | WASM 插件定义 |
| **ServiceSource** | 注册中心配置 |
| **RouteRule** | 路由规则 |
| **Upstream** | 上游服务 |

## 四、部署

### 1. Helm 安装

```bash
helm repo add higress https://higress.io/helm-charts
helm install higress higress/higress -n higress-system --create-namespace
```

### 2. Docker Compose（本地调试）

```bash
git clone https://github.com/alibaba/higress
cd higress
docker-compose up -d
```

### 3. 阿里云

直接用阿里云微服务引擎 MSE 中的 Higress 实例，一键开通。

## 五、Ingress 与 Gateway API

### 1. K8s Ingress（兼容）

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-app
spec:
  rules:
    - host: app.example.com
      http:
        paths:
          - path: /api
            pathType: Prefix
            backend:
              service:
                name: my-app
                port: { number: 80 }
```

### 2. K8s Gateway API（推荐）

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: my-app
spec:
  parentRefs:
    - name: higress-gateway
  hostnames: ["app.example.com"]
  rules:
    - matches:
        - path: { type: PathPrefix, value: /api }
      backendRefs:
        - name: my-app
          port: 80
```

### 3. Gateway 资源

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: higress-gateway
spec:
  gatewayClassName: higress
  listeners:
    - name: http
      port: 80
      protocol: HTTP
    - name: https
      port: 443
      protocol: HTTPS
      tls:
        mode: Terminate
        certificateRefs:
          - name: my-cert
```

## 六、WASM 插件

### 1. 概述

- WASM 是 Higress 一等公民
- 比 Envoy 原生 Filter 简单
- Go SDK：`github.com/higress-group/proxy-wasm-go-sdk`
- 热更新（无需重启）

### 2. 编写插件

```go
package main

import (
    "github.com/higress-group/proxy-wasm-go-sdk/proxywasm"
    "github.com/higress-group/proxy-wasm-go-sdk/proxywasm/types"
)

func main() {
    proxywasm.SetVMContext(&vmContext{})
}

type vmContext struct{ types.DefaultVMContext }

func (*vmContext) NewPluginContext(uint32) types.PluginContext {
    return &pluginContext{}
}

type pluginContext struct{ types.DefaultPluginContext }

func (p *pluginContext) OnPluginStart(int) types.Action {
    return types.ActionContinue
}

func (*pluginContext) NewHttpPluginContext(uint32) types.HttpPluginContext {
    return &httpContext{}
}

type httpContext struct{ types.DefaultHttpPluginContext }

func (*httpContext) OnHttpRequestHeaders(uint32, bool) types.Action {
    headers, _ := proxywasm.GetHttpRequestHeaders()
    proxywasm.AddHttpRequestHeader("x-higress", "yes")
    _ = headers
    return types.ActionContinue
}
```

### 3. 构建

```bash
docker build -t my-registry/my-plugin:v1 .
```

### 4. WasmPlugin 资源

```yaml
apiVersion: extensions.higress.io/v1alpha1
kind: WasmPlugin
metadata:
  name: my-plugin
spec:
  defaultConfig:
    my_field: "value"
  url: oci://my-registry/my-plugin:v1
  phase: AUTHN
  priority: 100
  matchRules:
    - config:
        my_field: "v2"
      ingress: ["my-app"]
```

### 5. 内置插件

Higress 自带：

- **auth**：JWT / OIDC / Key Auth / Basic Auth
- **cors**：跨域
- **rate-limit**：限流
- **rewrite**：路径 / Header 重写
- **redirect**：重定向
- **sentinel**：阿里 Sentinel 限流
- **key-rate-limit**：基于 Key 限流
- **gzip**：压缩
- **ai-proxy**：AI 网关（代理 LLM）
- **ai-statistics**：AI 用量统计

## 七、限流

### 1. 全局限流

```yaml
apiVersion: extensions.higress.io/v1alpha1
kind: WasmPlugin
metadata:
  name: rate-limit
spec:
  defaultConfig:
    limit_by_header: "x-user-id"
    limit_by_ip: true
    rules:
      - limit: 100
        window: 60s
        match:
          - path: /api
```

### 2. Sentinel 集成

```yaml
apiVersion: extensions.higress.io/v1alpha1
kind: WasmPlugin
metadata:
  name: sentinel
spec:
  defaultConfig:
    rules:
      - grade: 1     # 0=流量 1=并发
        threshold: 100
        resource: /api
```

## 八、AI 网关（Higress 杀手锏）

### 1. AI Proxy

代理 LLM（OpenAI / 通义千问 / 文心一言）：

```yaml
apiVersion: extensions.higress.io/v1alpha1
kind: WasmPlugin
metadata:
  name: ai-proxy
spec:
  defaultConfig:
    providers:
      - provider: openai
        apiKey: "sk-..."
        model: gpt-4
      - provider: qwen
        apiKey: "..."
        model: qwen-max
    fallback: openai
```

### 2. AI Statistics

记录 LLM 调用 token 消耗：

```yaml
apiVersion: extensions.higress.io/v1alpha1
kind: WasmPlugin
metadata:
  name: ai-statistics
spec:
  defaultConfig:
    metrics:
      - type: counter
        name: llm_tokens_total
```

### 3. AI Token Rate Limit

```yaml
apiVersion: extensions.higress.io/v1alpha1
kind: WasmPlugin
metadata:
  name: ai-token-rate-limit
spec:
  defaultConfig:
    limits:
      - by: user_id
        tokens_per_minute: 10000
```

## 九、多注册中心

### 1. McpBridge

```yaml
apiVersion: networking.higress.io/v1alpha1
kind: McpBridge
metadata:
  name: nacos-bridge
spec:
  registries:
    - name: nacos
      type: nacos
      nacos:
        server_addr: nacos:8848
        namespace: public
        group: DEFAULT_GROUP
    - name: consul
      type: consul
      consul:
        server_addr: consul:8500
```

### 2. ServiceSource

```yaml
apiVersion: networking.higress.io/v1alpha1
kind: ServiceSource
metadata:
  name: nacos-services
spec:
  source: nacos
  filter:
    service_names:
      - user-service
      - order-service
```

## 十、Dubbo / gRPC

### 1. gRPC 代理

```yaml
apiVersion: networking.higress.io/v1alpha1
kind: RouteRule
metadata:
  name: grpc-app
spec:
  target: grpc-app
  rules:
    - match:
        method: { service: "helloworld.Greeter", method: "SayHello" }
      redirect:
        target: grpc-app-v2
```

### 2. Dubbo 转 HTTP

通过 WASM 插件实现（社区提供）。

## 十一、可观测

### 1. Prometheus

Higress 暴露 `/metrics`（Prometheus 格式）。

### 2. SLS（阿里云日志）

```yaml
apiVersion: extensions.higress.io/v1alpha1
kind: WasmPlugin
metadata:
  name: sls-logger
spec:
  defaultConfig:
    endpoint: "cn-hangzhou.log.aliyuncs.com"
    project: "my-project"
    logstore: "my-logstore"
    access_key_id: "..."
    access_key_secret: "..."
```

### 3. ARMS（阿里云 APM）

自动接入 ARMS，提供调用链追踪。

## 十二、Higress vs APISIX / Kong / Envoy

| 维度 | Higress | APISIX | Kong | Envoy |
| --- | --- | --- | --- | --- |
| 数据面 | Envoy + Nginx | OpenResty | OpenResty | Envoy |
| 控制面 | Istio fork | 自研（etcd） | 自研（DB） | xDS |
| WASM | **一等公民** | 实验 | ❌ | ✔ |
| AI 网关 | **原生** | � | ❌ | 插件 |
| 多注册中心 | Nacos/Consul/K8s | K8s/Consul | Consul | K8s |
| 阿里云 | **深度集成** | 部分 | 部分 | 需自建 |
| 性能 | 高 | 极高 | 高 | 高 |
| Dashboard | 开源 | 内置 | 商业 | ❌ |

## 十三、典型场景

- **K8s 云原生网关**：Ingress / Gateway API
- **AI 网关**：代理 LLM，统一鉴权、限流、计费
- **多注册中心**：K8s + Nacos 混合环境
- **阿里云生态**：SLS / ARMS / IDaaS 一站式
- **WASM 插件扩展**：自定义 Filter 不需编 C++

## 十四、最佳实践

- **Gateway API 优先**：未来标准
- **WASM 插件复用**：把通用逻辑抽成插件
- **AI 场景用 ai-proxy**：减少多供应商切换
- **McpBridge**：解决跨注册中心服务发现
- **SLS 日志**：阿里云首选
- **限流分层**：全局 + 路由级
- **灰度**：用 Envoy Filter 权重路由
- **Dashboard 保护**：绑内网
- **证书**：cert-manager + DNS01
- **插件版本**：用 OCI tag 锁版本
