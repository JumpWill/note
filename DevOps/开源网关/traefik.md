# Traefik

云原生时代的反向代理 + Ingress Controller。Go 单文件、自动服务发现、内置 Dashboard、自动 HTTPS（Let's Encrypt）。是 K8s Ingress 的主流选择之一。

## 一、定位与特点

- 云原生反向代理 + Load Balancer
- Go 单文件，配置即代码
- 自动服务发现（K8s / Docker / Consul / etcd）
- 自动 HTTPS（Let's Encrypt ACME）
- 内置 Dashboard + REST API
- 热重载（无需重启）
- 同时支持 HTTP / TCP / UDP
- 商业版：Traefik Hub / Maesh（Mesh）

## 二、架构

```text
┌────────────────────────────────────┐
│  Client                            │
└─────────────┬──────────────────────┘
              │
              ▼
┌────────────────────────────────────┐
│  Traefik (Go)                      │
│   - EntryPoints (80/443)           │
│   - Routers (规则)                  │
│   - Services (上游)                │
│   - Middlewares (插件)             │
│   - Providers (K8s/Docker/文件)    │
└─────┬──────────────────┬───────────�
      │                  │
      ▼                  ▼
  Upstream         Provider
  Services        (K8s/Docker)
```

核心组件：

- **EntryPoint**：监听端口
- **Router**：路由规则
- **Service**：上游服务
- **Middleware**：中间件（鉴权/限流/重写等）
- **Provider**：配置来源

## 三、核心概念

| 概念 | 含义 |
| --- | --- |
| **EntryPoint** | 监听端口（80/443） |
| **Router** | 路由规则（匹配 + 服务） |
| **Service** | 上游服务抽象（可负载均衡） |
| **Middleware** | 中间件（鉴权/限流/重写） |
| **Provider** | 配置来源（K8s/Docker/file） |
| **TLS** | 证书配置 |

关系：`EntryPoint → Router → [Middleware] → Service`

## 四、部署

### 1. Docker

```bash
docker run -d \
  -p 80:80 -p 443:443 -p 8080:8080 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v $PWD/traefik.toml:/etc/traefik/traefik.toml \
  traefik:v3
```

### 2. 静态配置 `traefik.toml`

```toml
[entryPoints]
  [entryPoints.web]
    address = ":80"
  [entryPoints.websecure]
    address = ":443"

[api]
  dashboard = true
  insecure = false

[providers.docker]
  endpoint = "unix:///var/run/docker.sock"
  watch = true

[providers.file]
  directory = "/etc/traefik/dynamic"
  watch = true

[certificatesResolvers.letsencrypt.acme]
  email = "you@example.com"
  storage = "/etc/traefik/acme.json"
  [certificatesResolvers.letsencrypt.acme.tlsChallenge]
```

### 3. K8s (Helm)

```bash
helm repo add traefik https://traefik.github.io/charts
helm install traefik traefik/traefik
```

values.yaml 关键项：

```yaml
ingressClass:
  enabled: true
  isDefaultClass: true
dashboard:
  enabled: true
certificatesResolvers:
  letsencrypt:
    enabled: true
    email: "you@example.com"
```

### 4. Dashboard

`http://traefik:8080/dashboard/`（K8s 中通过 Ingress 暴露）。

## 五、K8s Ingress

### 1. Ingress 资源

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-app
  annotations:
    traefik.ingress.kubernetes.io/router.entrypoints: websecure
    traefik.ingress.kubernetes.io/router.tls: "true"
    traefik.ingress.kubernetes.io/router.tls.certresolver: letsencrypt
spec:
  rules:
    - host: app.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: my-app
                port:
                  number: 80
```

### 2. IngressRoute（Traefik CRD，功能更强）

```yaml
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: my-app
spec:
  entryPoints:
    - websecure
  routes:
    - match: Host(`app.example.com`) && PathPrefix(`/api`)
      kind: Rule
      services:
        - name: my-app
          port: 80
      middlewares:
        - name: ratelimit
  tls:
    certResolver: letsencrypt
```

### 3. Middleware CRD

```yaml
apiVersion: traefik.io/v1alpha1
kind: Middleware
metadata:
  name: ratelimit
spec:
  rateLimit:
    average: 100
    burst: 200
---
apiVersion: traefik.io/v1alpha1
kind: Middleware
metadata:
  name: auth
spec:
  forwardAuth:
    address: http://authentik:9000/outpost.goauthentik.io/auth/traefik
    trustForwardHeader: true
    authResponseHeaders:
      - X-Forwarded-User
      - X-Forwarded-Groups
```

## 六、中间件 (Middleware)

### 1. 认证

| 类型 | 用途 |
| --- | --- |
| **BasicAuth** | HTTP Basic |
| **DigestAuth** | HTTP Digest |
| **ForwardAuth** | 委托给外部 IDP（Keycloak / Authentik） |
| **OAuth2** | OAuth2 Proxy |
| **JWT** | JWT 验签 |

### 2. ForwardAuth（最常用）

```yaml
apiVersion: traefik.io/v1alpha1
kind: Middleware
metadata:
  name: auth
spec:
  forwardAuth:
    address: http://authentik:9000/outpost.goauthentik.io/auth/traefik
    trustForwardHeader: true
    authResponseHeaders:
      - X-Forwarded-User
      - X-Forwarded-Email
      - X-Forwarded-Groups
```

### 3. 限流

```yaml
apiVersion: traefik.io/v1alpha1
kind: Middleware
metadata:
  name: ratelimit
spec:
  rateLimit:
    average: 100       # 平均速率/秒
    burst: 200         # 突发
    period: 1s
```

### 4. 重写

```yaml
apiVersion: traefik.io/v1alpha1
kind: Middleware
metadata:
  name: rewrite
spec:
  redirectRegex:
    regex: "^https://(.*)/old/(.*)"
    replacement: "https://${1}/new/${2}"
    permanent: true
```

### 5. Headers

```yaml
apiVersion: traefik.io/v1alpha1
kind: Middleware
metadata:
  name: headers
spec:
  headers:
    customRequestHeaders:
      X-Forwarded-Proto: "https"
    customResponseHeaders:
      X-Frame-Options: "DENY"
    browserXssFilter: true
    contentTypeNosniff: true
```

### 6. CORS

```yaml
apiVersion: traefik.io/v1alpha1
kind: Middleware
metadata:
  name: cors
spec:
  cors:
    allowOriginList:
      - "https://app.example.com"
    allowMethods:
      - GET
      - POST
    allowHeaders:
      - Authorization
      - Content-Type
    allowCredentials: true
```

## 七、TCP / UDP

### 1. TCP Service

```toml
[tcp.services.mysql]
  [tcp.services.mysql.loadBalancer]
    servers = [{ address = "mysql:3306" }]
[tcp.routers.mysql]
  service = "mysql"
  entryPoints = ["mysql"]
```

### 2. UDP Service

```toml
[udp.services.dns]
  [udp.services.dns.loadBalancer]
    servers = [{ address = "dns:53" }]
[udp.routers.dns]
  service = "dns"
  entryPoints = ["dns"]
```

## 八、自动 HTTPS

### 1. Let's Encrypt

```toml
[certificatesResolvers.letsencrypt.acme]
  email = "you@example.com"
  storage = "/etc/traefik/acme.json"
  [certificatesResolvers.letsencrypt.acme.tlsChallenge]
```

### 2. HTTP Challenge

```toml
[certificatesResolvers.letsencrypt.acme.httpChallenge]
  entryPoint = "web"
```

### 3. DNS Challenge

```toml
[certificatesResolvers.letsencrypt.acme.dnsChallenge]
  provider = "cloudflare"
  delayBeforeCheck = 0
```

支持 DNS provider：Cloudflare / Route53 / Aliyun / DNSPod 等。

### 4. 自动续签

证书 90 天前自动续签。

## 九、服务发现

### 1. Docker

```toml
[providers.docker]
  endpoint = "unix:///var/run/docker.sock"
```

容器自动注册，需加 label：

```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.myapp.rule=Host(`app.example.com`)"
  - "traefik.http.services.myapp.loadbalancer.server.port=80"
```

### 2. K8s

默认自动 watch 所有 Service / Ingress。

### 3. Consul / etcd

```toml
[providers.consul]
  address = "consul:8500"
  watch = true
```

### 4. 文件

```toml
[providers.file]
  directory = "/etc/traefik/dynamic"
  watch = true
```

文件热加载。

## 十、可观测

### 1. Dashboard

`/dashboard/`：

- 路由列表
- 健康状态
- 实时指标
- 中间件

### 2. Prometheus

```yaml
metrics:
  prometheus:
    entryPoint: metrics
```

访问 `/metrics` 取 Prometheus 格式。

### 3. OpenTelemetry

```yaml
tracing:
  otel:
    http:
      endpoint: "http://otel-collector:4318"
```

### 4. Access Log

```yaml
accessLog:
  filePath: "/var/log/traefik/access.log"
  format: json
  fields:
    defaultMode: keep
    headers:
      defaultMode: keep
```

## 十一、TLS / mTLS

### 1. TLS 证书

```toml
[tls.stores.default]
  [tls.stores.default.defaultCertificate]
    certFile = "/certs/cert.pem"
    keyFile = "/certs/key.pem"
```

### 2. mTLS（双向）

```toml
[[tls.certificates]]
  certFile = "/certs/cert.pem"
  keyFile = "/certs/key.pem"

[tls.configurations.mtls]
  [tls.configurations.mtls.clientAuth]
    caFiles = ["/certs/ca.pem"]
    required = true
```

## 十二、与其他 Ingress 对比

| 维度 | Traefik | NGINX Ingress | HAProxy Ingress | Envoy |
| --- | --- | --- | --- | --- |
| 配置方式 | 自动发现 | 注解/CRD | CRD | CRD |
| Dashboard | ✔ | ❌（外部） | ❌ | ❌ |
| 自动 HTTPS | ✔ | 需 cert-manager | 需 cert-manager | 需 cert-manager |
| TCP/UDP | ✔ | 部分 | ✔ | ✔ |
| 热重载 | ✔ | 部分 | ✔ | ✔ |
| 性能 | 中 | 高 | **极高** | 高 |
| 学习曲线 | 低 | 中 | 中 | 高 |
| 协议 | HTTP/TCP/UDP | HTTP/TCP | HTTP/TCP | 全 |

## 十三、典型场景

- **K8s Ingress**：最常见，自动发现 Service
- **Docker Swarm / Compose**：label 自动注册
- **边缘网关**：CDN 边缘节点，自动 HTTPS
- **多 Provider 混合**：K8s + Consul + 文件并存
- **TCP/UDP 代理**：数据库、Redis、MQTT

## 十四、最佳实践

- **自动 HTTPS 优先**：Let's Encrypt + DNS Challenge
- **ForwardAuth 统一鉴权**：与 Keycloak / Authentik 集成
- **Middleware 复用**：常用中间件定义为 CRD
- **Dashboard 保护**：绑内网或 basic auth
- **Access Log 用 JSON**：方便 ELK 解析
- **Metrics + Tracing**：OTel 一站式
- **多 Provider**：K8s + file 并存，file 放全局配置
- **Hot Reload**：改配置无需重启
- **Pilot TLS**：生产环境开启 TLS 1.3
- **Rate Limit**：按 IP 限，配合 IP 白名单
