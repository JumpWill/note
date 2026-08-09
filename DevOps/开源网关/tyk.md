# Tyk

Go 编写的开源 API Gateway，单二进制部署，内置 Dashboard，GraphQL 原生支持。适合中小团队 / 单体网关 / GraphQL 优先场景。

## 一、定位与特点

- 纯 Go 实现，性能中等偏上
- 单二进制：`tyk` + `tyk-dashboard` + `tyk-pump`
- 内置 Dashboard（API 文档 + 监控）
- GraphQL 原生（一等公民）
- 配置存储：Redis
- 商业版 Tyk Enterprise（多云、联邦、审计）
- 支持 HTTP / HTTPS / TCP / gRPC / GraphQL

## 二、架构

```text
┌────────────────────────────────────┐
│  Client                            │
└─────────────┬──────────────────────┘
              │
              ▼
�────────────────────────────────────┐
│  Tyk Gateway (Go)                  │
│   - HTTP Router                    │
│   - Auth Middleware                │
│   - GraphQL Engine                 │
│   - Plugin (Go/Lua/JS)             │
└─────┬──────────────┬───────────────┘
      │              │
      ▼              ▼
  Upstream         Redis (config)
  Services          │
                    ▼
                  Tyk Dashboard
                  (管理 UI / 文档)
                    │
                    ▼
                  Tyk Pump
                  (analytics → ES / Kafka)
```

组件：

- **Tyk Gateway**：处理流量
- **Tyk Dashboard**：Web 管理
- **Tyk Pump**：分析日志 → ES / Kafka / Splunk
- **Redis**：配置存储 + 速率计数

## 三、核心概念

| 概念 | 含义 |
| --- | --- |
| **API** | 一个 API 定义（路由 + 上游 + 鉴权） |
| **Endpoint** | API 下的具体路径（可挂插件） |
| **Key** | 访问凭证（auth token） |
| **Policy** | 一组权限 + 限流策略（绑定 Key） |
| **Security Policy** | 认证方式（key / OAuth / JWT / OIDC） |
| **Custom Domain** | 多租户域名 |
| **Certificate** | TLS 证书 |
| **WebHook** | 事件通知 |

## 四、部署

### 1. Docker Compose（最快）

```yaml
services:
  redis:
    image: redis:7
  tyk-gateway:
    image: tykio/tyk-gateway:latest
    ports: ["8080:8080"]
    volumes:
      - ./tyk.conf:/etc/tyk/tyk.conf
  tyk-dashboard:
    image: tykio/tyk-dashboard:latest
    ports: ["3000:3000"]
  tyk-pump:
    image: tykio/tyk-pump:latest
```

### 2. 配置文件 `tyk.conf`

```json
{
  "listen_address": "0.0.0.0",
  "listen_port": 8080,
  "secret": "your-secret",
  "storage": {
    "type": "redis",
    "host": "redis",
    "port": 6379
  },
  "policies": {
    "policy_source": "service"
  },
  "use_db_app_configs": true,
  "enable_apis": true
}
```

### 3. K8s (Helm)

```bash
helm repo add tyk https://tykio.github.io/tyk-helm-chart
helm install tyk tyk/tyk-gateway
```

## 五、API 定义

### 1. REST API

```json
{
  "name": "my-app",
  "slug": "my-app",
  "api_id": "my-app-id",
  "org_id": "default",
  "use_keyless": false,
  "auth": {
    "auth_header_name": "Authorization"
  },
  "definition": {
    "location": "header",
    "key": "x-api-version"
  },
  "version_data": {
    "not_versioned": true,
    "versions": {
      "Default": {
        "name": "Default",
        "paths": {
          "ignored": ["/api/health"],
          "white_list": [],
          "black_list": []
        }
      }
    }
  },
  "proxy": {
    "listen_path": "/my-app/",
    "target_url": "http://my-app:80",
    "strip_listen_path": true
  },
  "active": true
}
```

通过 Dashboard 上传，或直接 POST 到 `/api/tyk/apis`。

### 2. GraphQL

```json
{
  "name": "graphql-app",
  "slug": "graphql-app",
  "graphql": {
    "enabled": true,
    "execution_mode": "proxy",
    "proxy": {
      "target_url": "http://upstream-graphql:4000/graphql"
    },
    "schema": "..."
  }
}
```

两种模式：

- **Proxy**：透传到上游
- **Supergraph**：聚合多个 subgraph

### 3. gRPC

Tyk 4.x 起支持 gRPC，可代理 gRPC 服务。

## 六、认证

### 1. Authentication Type

| Type | 用途 |
| --- | --- |
| **Auth Token** | 自管理 API Key |
| **JWT** | JWT 验签 |
| **OAuth 2.0** | OAuth2 流程 |
| **OIDC** | OpenID Connect |
| **Basic Auth** | 用户名密码 |
| **HMAC** | HMAC 签名 |
| **Mutual TLS** | 双向 TLS |
| **OpenID-Connect** | OIDC 完整流程 |

### 2. Auth Token 示例

```bash
# 创建 Key
curl -X POST http://tyk:8080/tyk/keys/create \
  -H "x-tyk-authorization: your-secret" \
  -d '{
    "allowance": 1000,
    "rate": 1000,
    "per": 60,
    "expires": -1,
    "quota_max": -1,
    "quota_renews": -1,
    "quota_remaining": -1,
    "quota_renewal_rate": 60,
    "apply_policy_id": "policy-1"
  }'
```

应用调用：

```bash
curl http://tyk:8080/my-app/api \
  -H "Authorization: alice-key"
```

### 3. JWT

```json
{
  "auth": {
    "auth_header_name": "Authorization",
    "use_jwt": true,
    "jwt_signing_method": "HMAC",
    "jwt_source": "your-secret",
    "jwt_identity_base_field": "sub"
  }
}
```

### 4. OIDC

```json
{
  "auth": {
    "use_oidc": true,
    "oidc_provider": {
      "issuer": "http://kc/realms/myrealm",
      "client_id": "tyk",
      "client_secret": "xxx",
      "scopes": ["openid"]
    }
  }
}
```

## 七、限流与配额

### 1. Rate Limit

```json
{
  "rate": 100,        // 100 次
  "per": 60,          // 60 秒
  "rate_limit": {
    "rate": 100,
    "per": 60
  }
}
```

### 2. Quota

```json
{
  "quota_max": 10000,        // 月配额
  "quota_renews": 2592000,    // 30 天
  "quota_remaining": 10000
}
```

### 3. Policy

```json
{
  "id": "policy-1",
  "name": "Premium",
  "rate": 1000,
  "per": 60,
  "quota_max": 1000000,
  "quota_renews": 2592000,
  "access_rights": {
    "my-app": {
      "api_id": "my-app",
      "api_name": "my-app",
      "versions": ["Default"]
    }
  },
  "per_api_per_key_limit": false
}
```

把 Policy 挂在 Key 上，Key 自动获得多 API 权限。

## 八、插件

### 1. 插件类型

- **Pre**：请求前
- **Post**：响应后
- **Post-Auth**：鉴权后
- **Response**：响应处理
- **Auth Check**：自定义鉴权

### 2. Go 插件

```go
// MyPlugin.go
func MyPlugin(response *http.Response, request *http.Request) {
    // 修改请求
    request.Header.Set("X-Plugin", "yes")
}
```

### 3. JS 插件

```javascript
// MyPlugin.js
var myPre = new TykJS.TykMiddleware.NewMiddleware({});
myPre.NewProcessRequest(function(request, session, config) {
    request.SetHeaders["X-Plugin"] = "yes";
    return myPre.ReturnData(request, {});
});
```

### 4. Lua

Tyk 也支持 Lua 插件（社区）。

## 九、可观测

### 1. 内置 Dashboard

- 实时流量图
- Top endpoints
- 错误率
- 延迟分布

### 2. Tyk Pump

分析数据外发：

```yaml
tyk-pump:
  backends:
    elasticsearch:
      type: "elasticsearch"
      enable: true
      host: "es"
      index_name: "tyk"
    kafka:
      type: "kafka"
      enable: true
      brokers: ["kafka:9092"]
      topic: "tyk-analytics"
```

支持：ElasticSearch / Kafka / Splunk / StatsD / Prometheus / InfluxDB。

### 3. Trace

Tyk 4.x+ 支持 OpenTelemetry，trace 数据可注入 OpenTelemetry collector。

### 4. Metrics

通过 Pump 输出到 Prometheus。

## 十、K8s Operator

### 1. ApiDefinition CRD

```yaml
apiVersion: tyk.tyk.io/v1alpha1
kind: ApiDefinition
metadata:
  name: my-app
spec:
  name: my-app
  use_keyless: false
  protocol: http
  active: true
  proxy:
    target_url: http://my-app.default.svc:80
    listen_path: /my-app/
    strip_listen_path: true
  auth:
    auth_header_name: Authorization
```

### 2. SecurityPolicy CRD

```yaml
apiVersion: tyk.tyk.io/v1alpha1
kind: SecurityPolicy
metadata:
  name: my-policy
spec:
  name: my-policy
  keyless: false
  auth_source:
    type: bearer
  access_rights:
    my-app:
      api_id: my-app
      versions: ["Default"]
  rate: 100
  per: 60
```

## 十一、Tyk vs Kong / APISIX

| 维度 | Tyk | Kong | APISIX |
| --- | --- | --- | --- |
| 语言 | Go | Lua + Go | Lua + Go |
| 存储 | Redis | Postgres / YAML | etcd |
| 性能 | 中 | 高 | 高 |
| GraphQL | **一等公民** | 插件 | 插件 |
| Dashboard | 内置 | 商业 | 内置 |
| 插件语言 | Go / JS / Lua | Lua / Go / Python | Lua + 4 外部语言 |
| 多协议 | HTTP/gRPC/GraphQL | 全 | 全 |
| 学习曲线 | 低 | 中 | 中 |

## 十二、典型场景

- **中小团队 API 平台**：Dashboard + 鉴权 + 限流
- **GraphQL 网关**：聚合多 subgraph
- **API 货币化**：配额 + 计费
- **多租户 API Marketplace**：每个租户一个 API

## 十三、最佳实践

- **Redis 必 HA**：单点 Redis = 单点网关
- **Pump 单独部署**：避免拖慢网关
- **Policy 优先**：用 Policy 复用配置，不要每个 Key 单独配
- **API 版本管理**：`version_data` 多版本并存
- **Dashboard 不要暴露公网**：绑内网或反代
- **审计**：商业版有审计，OSS 用 Pump 抓 admin 日志
- **GraphQL Schema 上传**：CI/CD 自动同步
- **K8s Operator**：GitOps 管理 API 定义
- **插件**：Go 性能最好，JS 调试最方便
