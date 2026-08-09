# Envoy

Lyft 开源的 L7 反向代理 + Service Mesh 数据面。C++ 实现，高性能 + xDS 动态配置 + WASM 扩展。是 Istio / Higress / Consul 的默认数据面。

## 一、定位与特点

- L7 反向代理 / Sidecar
- C++ 实现，高性能、低延迟
- xDS 协议：动态配置中心（CDS/EDS/LDS/RDS）
- HTTP/1.1、HTTP/2、HTTP/3、gRPC、TCP、UDP、Thrift
- WASM / Lua / Native（C++） Filter 扩展
- 服务发现：DNS / EDS / Consul / K8s
- 可独立部署，也可被 Istio / Consul 等控制面管理

## 二、架构

```text
┌────────────────────────────────────┐
│  Client                            │
└─────────────┬──────────────────────┘
              │
              ▼
┌────────────────────────────────────┐
│  Envoy                             │
│   - Listener (入口)                │
│   - Filter Chain                   │
│   - Router (L7)                    │
│   - Cluster (上游)                 │
│   - xDS (动态配置)                  │
│   - Health Check / Circuit Breaker│
└─────�──────────────────┬───────────�
      │                  │
      ▼                  ▼
  Upstream           xDS Control Plane
  Services          (Istio / Pilot / 自研)
```

核心组件：

- **Listener**：监听 + Filter Chain
- **Route**：路由配置
- **Cluster**：上游服务
- **Endpoint**：后端实例
- **xDS**：动态配置协议
- **Filter**：请求/响应处理链

## 三、xDS 协议

### 1. 协议族

| 类型 | 全称 | 含义 |
| --- | --- | --- |
| **LDS** | Listener Discovery | Listener 配置 |
| **RDS** | Route Discovery | 路由配置 |
| **CDS** | Cluster Discovery | Cluster 配置 |
| **EDS** | Endpoint Discovery | Endpoint 配置 |
| **SDS** | Secret Discovery | 证书 / Secret |
| **ADS** | Aggregated Discovery | 聚合推送 |

### 2. 数据交互

```text
Control Plane ──xDS──> Envoy
                       │
                       ▼
                  Listener
                       │
                       ▼
                  Filter Chain
                       │
                       ▼
                  Route
                       │
                       ▼
                  Cluster
                       │
                       ▼
                  Endpoint (动态更新)
```

### 3. xDS 特点

- **增量推送**：仅传变更
- **最终一致**：节点本地合并
- **强类型**：proto 定义

## 四、Filter（过滤器）

### 1. 类别

- **Network Filter**：L4（TCP / UDP）
- **HTTP Filter**：L7（HTTP / gRPC）

### 2. 内置 Filter

| 类别 | Filter |
| --- | --- |
| **路由** | `router`、`match_delegate` |
| **限流** | `local_ratelimit`、`ratelimit`（远程） |
| **熔断** | `circuit_breakers`、`outlier_detection` |
| **鉴权** | `ext_authz`（委托外部）、`jwt_authn` |
| **转换** | `lua`、`header_mutation`、`compression` |
| **可观测** | `access_log`、`stats`、`tap`（流量镜像） |
| **流量管理** | `fault`、`mirror`、`retry`、`cors` |
| **协议** | `grpc_json_transcoder`、`grpc_web` |

### 3. WASM Filter

Envoy 支持 WASM（WebAssembly）扩展：

- 用 Rust / C++ / AssemblyScript 编写
- 编译为 `.wasm`
- 运行时动态加载
- 可热更新

### 4. Lua Filter

```lua
function envoy_on_request(request_handle)
  request_handle:headers():add("X-Lua", "ran")
end

function envoy_on_response(response_handle)
  response_handle:headers():add("X-Powered-By", "envoy-lua")
end
```

## 五、配置

### 1. 静态配置 (YAML)

```yaml
admin:
  address:
    socket_address: { address: 0.0.0.0, port_value: 9901 }

static_resources:
  listeners:
    - name: listener_0
      address:
        socket_address: { address: 0.0.0.0, port_value: 8080 }
      filter_chains:
        - filters:
            - name: envoy.filters.network.http_connection_manager
              typed_config:
                "@type": type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
                stat_prefix: ingress
                route_config:
                  name: local_route
                  virtual_hosts:
                    - name: backend
                      domains: ["*"]
                      routes:
                        - match: { prefix: "/" }
                          route: { cluster: my_service }
                http_filters:
                  - name: envoy.filters.http.router
                    typed_config:
                      "@type": type.googleapis.com/envoy.extensions.filters.http.router.v3.Router
  clusters:
    - name: my_service
      type: STRICT_DNS
      load_assignment:
        cluster_name: my_service
        endpoints:
          - lb_endpoints:
              - endpoint:
                  address:
                    socket_address: { address: my-service, port_value: 80 }
```

### 2. 动态配置 (xDS)

```yaml
dynamic_resources:
  cds_config:
    api_config_source:
      api_type: GRPC
      grpc_services:
        - envoy_grpc: { cluster_name: xds_cluster }
  lds_config:
    api_config_source:
      api_type: GRPC
      grpc_services:
        - envoy_grpc: { cluster_name: xds_cluster }
```

### 3. 启动参数

```bash
envoy -c envoy.yaml --log-level info --service-cluster my-cluster
```

## 六、路由

### 1. 匹配规则

```yaml
routes:
  - match:
      prefix: /api/v1
      headers:
        - name: x-version
          string_match: { exact: "1.0" }
    route:
      cluster: api_v1
      timeout: 30s
      retry_policy:
        retry_on: "5xx,gateway-error"
        num_retries: 3
      request_mirror_policies:
        - cluster: api_v1_mirror
    typed_per_filter_config:
      envoy.filters.http.local_ratelimit:
        "@type": type.googleapis.com/envoy.extensions.filters.http.local_ratelimit.v3.LocalRateLimit
        token_bucket:
          max_tokens: 100
          tokens_per_fill: 100
          fill_interval: 60s
```

### 2. 高级路由

- **重试**：`retry_policy`
- **超时**：`timeout`
- **镜像**：`request_mirror_policies`
- **限速**：`typed_per_filter_config`
- **权重路由**：`weighted_clusters`

### 3. gRPC 路由

```yaml
routes:
  - match:
      grpc: {}
    route:
      cluster: grpc_service
```

## 七、流量管理

### 1. 熔断

```yaml
clusters:
  - name: my_service
    circuit_breakers:
      thresholds:
        - priority: DEFAULT
          max_connections: 1024
          max_pending_requests: 1024
          max_requests: 1024
          max_retries: 3
    outlier_detection:
      consecutive_5xx: 5
      interval: 30s
      base_ejection_time: 30s
```

### 2. 限速（本地）

```yaml
local_rate_limit:
  token_bucket:
    max_tokens: 1000
    tokens_per_fill: 1000
    fill_interval: 60s
  filter_enabled:
    runtime_key: rate_limit_enabled
    default_value: true
```

### 3. 限速（远程）

用 `rate_limit_service` 调外部 gRPC 服务（Envoy 自带 ratelimit 服务）。

### 4. 故障注入

```yaml
fault:
  abort:
    http_status: 503
    percentage:
      numerator: 5
      denominator: 100
  delay:
    fixed_delay: 5s
    percentage:
      numerator: 10
      denominator: 100
```

### 5. 流量镜像

```yaml
request_mirror_policies:
  - cluster: shadow_service
    runtime_fraction:
      default_value:
        numerator: 100
        denominator: 100
```

## 八、可观测

### 1. Access Log

```yaml
access_log:
  - name: envoy.access_loggers.stdout
    typed_config:
      "@type": type.googleapis.com/envoy.extensions.access_loggers.stream.v3.StdoutAccessLog
```

格式：

```yaml
access_log:
  - name: envoy.access_loggers.file
    typed_config:
      "@type": type.googleapis.com/envoy.extensions.access_loggers.file.v3.FileAccessLog
      path: /var/log/envoy/access.log
      access_log_format:
        text_format: "[%START_TIME%] %RESPONSE_CODE% %ROUTE_NAME%\n"
```

### 2. Stats（StatsD / Prometheus）

```yaml
stats_sinks:
  - name: envoy.stat_sinks.statsd
    typed_config:
      "@type": type.googleapis.com/envoy.config.stat_sinks.statsd.v3.StatsdSink
      address:
        socket_address: { address: statsd, port_value: 8125 }
```

或启用 Prometheus：

```yaml
stats_config:
  stats_matcher:
    inclusion_list:
      patterns:
        - "*"
```

Envoy 自动暴露 `/stats`。

### 3. Trace

支持：

- Zipkin
- Jaeger
- OpenTelemetry
- Datadog

```yaml
tracing:
  http:
    name: envoy.tracers.zipkin
    typed_config:
      "@type": type.googleapis.com/envoy.config.trace.v3.ZipkinConfig
      collector_cluster: zipkin
      collector_endpoint: "/api/v2/spans"
```

## 九、TLS / mTLS

### 1. SDS（动态证书）

```yaml
secrets:
  - name: server_cert
    tls_certificate:
      certificate_chain:
        filename: /etc/envoy/cert.pem
      private_key:
        filename: /etc/envoy/key.pem
```

### 2. mTLS

```yaml
transport_socket:
  name: envoy.transport_sockets.tls
  typed_config:
    "@type": type.googleapis.com/envoy.extensions.transport_sockets.tls.v3.DownstreamTlsContext
    common_tls_context:
      tls_certificate_sds_secret_configs:
        - name: server_cert
          sds_config: {...}
      validation_context:
        trusted_ca:
          filename: /etc/envoy/ca.pem
        require_client_certificate: true
```

## 十、Envoy 作为 Sidecar

### 1. K8s 中注入

通常由 Istio / Consul 自动注入 Sidecar。

### 2. 手动注入

```yaml
spec:
  containers:
    - name: app
      image: my-app
    - name: envoy
      image: envoyproxy/envoy:v1.30
      volumeMounts:
        - name: envoy-config
          mountPath: /etc/envoy
  volumes:
    - name: envoy-config
      configMap:
        name: envoy-config
```

### 3. iptables 透明拦截

```bash
iptables -t nat -A PREROUTING -p tcp -j REDIRECT --to-port 15001
```

应用发出的所有流量被拦截到 Envoy 15001，由 Envoy 路由。

## 十一、Admin API

```bash
# 查看 listener
curl localhost:9901/listeners

# 查看 cluster
curl localhost:9901/clusters

# 查看 config dump
curl localhost:9901/config_dump

# 改变日志级别
curl -X POST localhost:9901/logging?level=debug

# 健康检查
curl localhost:9901/ready
```

## 十二、Envoy vs Nginx / HAProxy

| 维度 | Envoy | NGINX | HAProxy |
| --- | --- | --- | --- |
| 配置方式 | xDS 动态 | 文件 | 文件 |
| 数据面 | Mesh 友好 | 反代为主 | 反代为主 |
| 性能 | 高 | **极高** | **极高** |
| L7 Filter | 丰富 | 模块 | 较少 |
| WASM | ✔ | 实验 | ❌ |
| 多协议 | 全 | HTTP/TCP | HTTP/TCP |
| 动态配置 | **核心特性** | 需 reload | 部分 |
| 学习曲线 | 高 | 中 | 中 |

## 十三、典型场景

- **Service Mesh 数据面**：Istio / Consul Connect
- **API Gateway**：自研控制面 + Envoy 数据面
- **边缘网关**：Envoy + 自研 xDS
- **多云代理**：跨云流量管理
- **流量镜像**：生产流量拷到测试环境

## 十四、最佳实践

- **优先动态配置**：xDS 比静态 YAML 灵活
- **Filter 精简**：每个 Listener 不超过 10 个
- **本地熔断必开**：保护下游
- **限速优先本地**：减少 RTT
- **mTLS 强制**：Mesh 内通信加密
- **Access Log 用 JSON**：ELK 友好
- **Stats 收敛**：tag 多会爆炸
- **Trace sampler**：全量采样太重
- **Admin API 保护**：绑 127.0.0.1
- **热更新**：配置变更无需重启
