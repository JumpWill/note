# Kong

老牌 API Gateway，基于 OpenResty（Nginx + LuaJIT）。插件生态丰富，企业级特性完整，是云原生之前的事实标准。

## 一、定位与特点

- 基于 OpenResty + Nginx 的高性能网关
- 插件化架构（认证、限流、日志、安全全覆盖）
- 双模式：传统（DB） / DB-less（声明式 YAML）
- K8s Ingress Controller（`kubernetes-ingress-controller`）
- Kong Mesh（Service Mesh，可选商业版）
- 商业版 Kong Enterprise（更多协议、审计、RBAC）

## 二、架构

```text
┌────────────────────────────────────┐
│  Client                            │
└─────────────┬──────────────────────┘
              │ HTTP/gRPC/TCP/UDP
              ▼
┌────────────────────────────────────┐
│  Kong (OpenResty)                  │
│   - Router                         │
│   - Plugins (Lua / Go / Python)    │
│   - Load Balancer                  │
└─────┬──────────────────┬───────────┘
      │                  │
      ▼                  ▼
  Upstream          Config Store
   Service        (Postgres / YAML)
```

核心组件：

- **Nginx**：底座
- **OpenResty / LuaJIT**：插件运行时
- **Kong PDK**：Lua/Go/Python 插件开发 SDK
- **Plugin Server**：Go / Python 插件独立进程
- **DB**：Postgres（DB 模式）或 YAML（DB-less）

## 三、核心概念

| 概念 | 含义 |
| --- | --- |
| **Service** | 上游服务抽象（如 `my-app`） |
| **Route** | 匹配规则（Path/Host/Header/Method） |
| **Upstream** | 后端目标（一组 target） |
| **Target** | 实际 IP:Port |
| **Consumer** | API 调用方（用户/应用） |
| **Plugin** | 钩入请求/响应周期的功能 |
| **Vault** | 密钥管理（DB / Env / AWS / GCP） |

关系：`Route → Service → Upstream → Targets`，`Plugin` 挂在 Service/Route/Consumer 上。

## 四、部署

### 1. Docker

```bash
docker run -d --name kong \
  -e "KONG_DATABASE=postgres" \
  -e "KONG_PG_HOST=postgres" \
  -e "KONG_PG_USER=kong" \
  -e "KONG_PG_PASSWORD=kong" \
  -e "KONG_PROXY_ACCESS_LOG=/dev/stdout" \
  -e "KONG_ADMIN_ACCESS_LOG=/dev/stdout" \
  -e "KONG_PROXY_LISTEN=0.0.0.0:8000" \
  -e "KONG_ADMIN_LISTEN=0.0.0.0:8001" \
  -p 8000:8000 \
  -p 8001:8001 \
  kong:latest
```

### 2. Docker Compose

```yaml
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: kong
      POSTGRES_PASSWORD: kong
      POSTGRES_DB: kong
  kong-migrations:
    image: kong:latest
    command: "kong migrations bootstrap"
    depends_on: [postgres]
  kong:
    image: kong:latest
    environment:
      KONG_DATABASE: postgres
      KONG_PG_HOST: postgres
      KONG_PROXY_LISTEN: "0.0.0.0:8000"
      KONG_ADMIN_LISTEN: "0.0.0.0:8001"
    ports: ["8000:8000", "8001:8001"]
    depends_on: [kong-migrations]
```

### 3. K8s (Helm)

```bash
helm repo add kong https://charts.konghq.com
helm install kong kong/kong --set ingressController.enabled=true
```

### 4. DB-less 模式

```bash
KONG_DATABASE=off \
KONG_DECLARATIVE_CONFIG=/etc/kong/kong.yml \
kong start
```

适合 CI/CD + GitOps。

## 五、路由与上游

### 1. Service + Route + Upstream

```bash
# 上游
curl -X POST localhost:8001/services \
  -d name=my-app \
  -d url=http://my-app.default.svc:80

# Upstream + Target（轮询）
curl -X POST localhost:8001/upstreams \
  -d name=my-app-upstream
curl -X POST localhost:8001/upstreams/my-app-upstream/targets \
  -d target=10.0.0.1:80
curl -X POST localhost:8001/upstreams/my-app-upstream/targets \
  -d target=10.0.0.2:80

# Route（path 匹配）
curl -X POST localhost:8001/services/my-app/routes \
  -d paths[]=/api \
  -d strip_path=true
```

### 2. 路由匹配优先级

| 字段 | 匹配 |
| --- | --- |
| `paths` | URL Path 前缀/精确 |
| `hosts` | Host 头 |
| `methods` | HTTP Method |
| `headers` | Header 键值 |
| `snis` | TLS SNI |
| `sources`/`destinations` | IP CIDR |

### 3. 高级路由

- **Regex path**：`paths~=^/api/v\d+/`
- **权重路由**：配合 `Upstream` + target weight
- **Header 路由**：A/B 测试
- **gRPC**：proto + method 路由

## 六、插件生态

### 1. 内置插件（官方）

| 类别 | 插件 |
| --- | --- |
| **认证** | `key-auth`、`basic-auth`、`oauth2`、`jwt`、`hmac-auth`、`ldap` |
| **安全** | `cors`、`ip-restriction`、`bot-detection`、`acl` |
| **流量控制** | `rate-limiting`、`response-ratelimiting`、`request-size-limiting`、`proxy-cache` |
| **可观测** | `prometheus`、`http-log`、`tcp-log`、`syslog`、`zipkin`、`opentelemetry` |
| **转换** | `request-transformer`、`response-transformer`、`correlation-id`、`grpc-web` |
| **服务端** | `grpc-gateway`、`upstream-timeout` |

### 2. 启用插件

```bash
# 全局
curl -X POST localhost:8001/plugins \
  -d name=rate-limiting \
  -d config.minute=100 \
  -d config.policy=local

# 挂到 Service
curl -X POST localhost:8001/services/my-app/plugins \
  -d name=jwt

# 挂到 Route
curl -X POST localhost:8001/routes/{route}/plugins \
  -d name=cors

# 挂到 Consumer
curl -X POST localhost:8001/consumers/alice/plugins \
  -d name=key-auth \
  -d config.key=alice-secret
```

### 3. 第三方插件

[Kong Hub](https://docs.konghq.com/hub) 上百款社区插件，覆盖企业 SSO、计费、API 货币化等。

### 4. 自定义插件

Lua：

```lua
-- kong/plugins/my-plugin/handler.lua
local BasePlugin = require "kong.plugins.base_plugin"
local MyPlugin = {
  PRIORITY = 1000,
  VERSION = "1.0.0",
}
function MyPlugin:access(conf)
  -- 自定义逻辑
  kong.log.inspect(conf)
end
return MyPlugin
```

Go（Plugin Server，需独立进程）：

```go
func main() {
    flag.StringVar(&configAddr, "config", "kong.conf", "config")
    // 监听 Kong 的 RPC
}
```

## 七、限流

### 1. 策略

| Policy | 后端 |
| --- | --- |
| `local` | 节点本地内存（精度低、性能高） |
| `cluster` | Postgres（精度高、性能差） |
| `redis` | Redis（精度高、性能好） |

### 2. 启用

```bash
curl -X POST localhost:8001/plugins \
  -d name=rate-limiting \
  -d config.minute=60 \
  -d config.hour=1000 \
  -d config.policy=redis \
  -d config.redis.host=redis \
  -d config.redis.port=6379
```

### 3. 维度

- Consumer
- Credential（API key）
- IP
- Service / Route
- Header

## 八、认证集成

### 1. JWT

```bash
curl -X POST localhost:8001/plugins \
  -d name=jwt \
  -d config.claims_to_verify=exp
```

应用侧：

```javascript
// 客户端生成 JWT
const jwt = require('jsonwebtoken');
const token = jwt.sign({ sub: 'alice' }, 'secret', { algorithm: 'HS256' });
fetch('/api', { headers: { Authorization: `Bearer ${token}` }});
```

### 2. OAuth2 / OIDC

```bash
curl -X POST localhost:8001/services/my-app/plugins \
  -d name=oauth2 \
  -d config.providers[1].name=keycloak \
  -d config.providers[1].client_id=my-app \
  -d config.providers[1].client_secret=xxx \
  -d config.providers[1].authorization_endpoint=http://kc/auth \
  -d config.providers[1].token_endpoint=http://kc/token
```

### 3. Key Auth

```bash
# 启用
curl -X POST localhost:8001/plugins -d name=key-auth
# 创建 Consumer
curl -X POST localhost:8001/consumers -d username=alice
# 签发 key
curl -X POST localhost:8001/consumers/alice/key-auth -d key=alice-key
```

## 九、可观测

### 1. Prometheus

```bash
curl -X POST localhost:8001/plugins \
  -d name=prometheus
# 访问 http://kong:8001/metrics
```

### 2. 日志

```bash
curl -X POST localhost:8001/plugins \
  -d name=http-log \
  -d config.http_endpoint=http://logstash:8080 \
  -d config.content_type=json
```

### 3. Trace

支持 OpenTelemetry / Zipkin / Jaeger：

```bash
curl -X POST localhost:8001/plugins \
  -d name=opentelemetry \
  -d config.tracing_endpoint=http://otel-collector:4318
```

## 十、DB-less 模式

### 1. 概述

- 无 Postgres
- 配置走 YAML/JSON
- 启动加载，Admin API 只读
- 适合 GitOps

### 2. 示例

```yaml
_format_version: "3.0"
services:
  - name: my-app
    url: http://my-app:80
    routes:
      - paths: ["/api"]
        strip_path: true
    plugins:
      - name: rate-limiting
        config:
          minute: 100
          policy: local
upstreams:
  - name: my-app-upstream
    targets:
      - target: 10.0.0.1:80
      - target: 10.0.0.2:80
consumers:
  - username: alice
    keyauth_credentials:
      - key: alice-key
```

启动：

```bash
KONG_DATABASE=off KONG_DECLARATIVE_CONFIG=kong.yml kong start
```

## 十一、K8s Ingress Controller

### 1. 安装

```bash
kubectl apply -f https://raw.githubusercontent.com/Kong/kubernetes-ingress-controller/main/deploy/single/all-in-one-postgres.yaml
```

### 2. CRD 路由

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-app
  annotations:
    konghq.com/plugins: "rate-limiting"
spec:
  ingressClassName: kong
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

### 3. KongPlugin CRD

```yaml
apiVersion: configuration.konghq.com/v1
kind: KongPlugin
metadata:
  name: rl
plugin: rate-limiting
config:
  minute: 100
  policy: local
```

## 十二、Kong vs APISIX

| 维度 | Kong | APISIX |
| --- | --- | --- |
| 配置中心 | Postgres / DB-less | etcd |
| 路由匹配 | 链式 / 优先级 | Radix Tree（更高效） |
| 插件语言 | Lua / Go / Python | Lua / Go / Java / Node |
| Dashboard | Kong Manager（Konnect） | 内置 |
| K8s CRD | 完善 | 完善 |
| 性能 | 高 | 略高 |
| 运维 | 需 DB 维护 | etcd 运维 |
| 商业版 | Kong Enterprise / Konnect | API7（API7 Cloud） |

## 十三、典型场景

- **API 统一入口**：所有微服务经 Kong，鉴权 + 限流 + 灰度
- **老牌企业集成**：已有 ESB / API 平台，Kong 提供 OAuth2 / 计量 / 文档
- **混合云**：Kong + Konnect 多云集群管理
- **API 货币化**：按调用次数 / 流量计费（商业版）
- **Service Mesh 边缘**：Kong Mesh 提供 mTLS

## 十四、最佳实践

- **DB-less 优先**：GitOps 友好，避免 Postgres 单点
- **插件最小化**：全局插件不要超过 10 个，性能会下降
- **限流用 Redis**：集群精度
- **证书管理**：用 cert-manager + Kong Vault
- **可观测**：Prometheus + OpenTelemetry
- **Admin API 不暴露公网**：绑 127.0.0.1 或内网
- **Consumer ID 来源**：统一用 `custom_id`，避免用户名敏感
- **缓存**：`proxy-cache` 插件缓存热点 GET
- **超时**：用 `upstream-timeout` + Nginx `proxy_*_timeout` 双重保障
- **审计**：商业版有审计日志；OSS 用 Admin API 变更告警
