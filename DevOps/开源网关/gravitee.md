# Gravitee

API 全生命周期管理平台，包含 API Gateway + API Management + API Designer + API Console。强调"治理 + 文档 + 订阅 + 计量"，是企业级 API 平台代表。

## 一、定位与特点

- API 全生命周期管理（设计 → 发布 → 调用 → 监控）
- Java + Netty 实现的数据面
- 内置 Dashboard + API 文档生成
- 订阅、计量、计费（plan / quota）
- 支持 OIDC / OAuth2 / API Key / JWT 鉴权
- 商业版 Gravitee Enterprise（更多协议、HA、审计）
- 包含：Cockpit（多环境管理）、Management Console、Developer Portal、Gateway、Access Management

## 二、架构

```text
┌────────────────────────────────────┐
│  Client                            │
└─────────────�──────────────────────┘
              │
              ▼
┌────────────────────────────────────┐
│  Gravitee Gateway (Java + Netty)   │
│   - Policy Chain                   │
│   - Rate Limit / Auth              │
│   - Load Balancer                  │
└─────┬──────────────────┬───────────�
      │                  │
      ▼                  ▼
  Backend         Management API
  Services         (MongoDB)
                     │
      ┌──────────────┴─────────────┐
      ▼                            ▼
  Developer Portal            Cockpit
  (API 文档 / 订阅)         (多环境管理)
```

组件：

- **Gateway**：数据面（Java + Vert.x）
- **Management API**：管理面（REST）
- **Portal**：开发者门户（API 文档、订阅）
- **Console**：管理员 UI
- **Cockpit**：多环境 / 多实例管理（商业版）

## 三、核心概念

| 概念 | 含义 |
| --- | --- |
| **Environment** | 环境（DEV / STAGING / PROD） |
| **Organization** | 组织（多租户） |
| **API** | 一个 API 定义（含多个 plan / flow） |
| **Plan** | 订阅计划（免费 / 付费 / 配额） |
| **Application** | 客户端应用 |
| **Subscription** | App 订阅 Plan |
| **API Key / OAuth2 Token** | 凭证 |
| **Flow** | 请求/响应/订阅的生命周期 |
| **Policy** | 钩入 Flow 的策略 |
| **Group** | 用户组 |
| **Role** | 权限 |

## 四、部署

### 1. Docker Compose（APIM 4.x）

参考 [gravitee-docker-compose](https://github.com/gravitee-io/gravitee-docker-compose)：

```yaml
services:
  mongodb:
    image: mongo:6
  gateway:
    image: graviteeio/apim-gateway:4
    ports: ["8082:8082"]
  management-api:
    image: graviteeio/apim-management-api:4
    ports: ["8083:8083"]
  portal:
    image: graviteeio/apim-portal:4
    ports: ["8085:8085"]
  console:
    image: graviteeio/apim-console:4
    ports: ["8088:8080"]
```

### 2. K8s

```bash
helm repo add gravitee https://helm.gravitee.io
helm install gravitee-apim gravitee/apim
```

### 3. Access Management

独立 IAM（OAuth2 / OIDC Server）：

```yaml
auth:
  image: graviteeio/am:4
  ports: ["8092:8092"]
```

可作为独立 OIDC Provider。

## 五、API 定义

### 1. 创建 API（GUI）

Console → APIs → Create：

- Name
- Version
- Type：Proxy / Mock
- Path：`/my-app`
- Upstream：目标 URL
- Plans：Keyless / API Key / OAuth2 / JWT

### 2. 创建 API（REST API）

```bash
curl -X POST http://localhost:8083/management/organizations/DEFAULT/environments/DEFAULT/apis \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-app",
    "version": "1.0",
    "type": "PROXY",
    "definitionVersion": "2.0.0",
    "paths": ["/my-app"],
    "proxy": {
      "groups": [
        {
          "name": "default",
          "endpoints": [
            {"name": "default", "target": "http://my-app:80"}
          ],
          "load_balancing": {"type": "ROUND_ROBIN"}
        }
      ]
    }
  }'
```

### 3. 部署 API

```bash
# 启动后必须部署
curl -X POST http://localhost:8083/management/.../apis/{apiId}/deploy \
  -H "Authorization: Bearer ${TOKEN}"
```

## 六、策略 (Policy)

### 1. 内置策略

| 类别 | 策略 |
| --- | --- |
| **认证** | API Key / OAuth2 / JWT / Basic Auth / OIDC |
| **限流** | Rate Limit / Quota / Spike Arrest / Cache |
| **安全** | CORS / IP Filtering / JSON Threat Protection / XML Threat Protection |
| **转换** | Request Transformer / Response Transformer / Header Transformer / Body to Header |
| **路由** | URL Rewriting / Redirect |
| **熔断** | Circuit Breaker / Retry / Timeout |
| **可观测** | Logging / Metrics / Tracing |
| **Mock** | Mock |

### 2. 启用策略（Flow）

GUI：API → Flows → 拖拽策略

REST：

```bash
curl -X POST http://localhost:8083/management/.../apis/{apiId}/plans/{planId}/flows \
  -d '{
    "name": "rate-limit",
    "type": "API",
    "methods": ["GET", "POST"],
    "policies": [
      {
        "name": "rate-limit",
        "configuration": {
          "rate": 100,
          "periodTime": 60,
          "periodTimeUnit": "SECONDS"
        }
      }
    ]
  }'
```

### 3. 策略阶段

- **On Request**：请求时
- **On Response**：响应时
- **On Request Content**：请求体
- **On Response Content**：响应体

## 七、Plan 与订阅

### 1. Plan

每个 API 有多个 Plan：

| Plan | 特点 |
| --- | --- |
| **Keyless** | 无需认证 |
| **API Key** | API Key |
| **OAuth2** | OAuth2 流程 |
| **JWT** | JWT 验签 |
| **Push** | 推送型（消息） |

### 2. Plan 配额

```json
{
  "name": "Gold",
  "type": "API",
  "security": "API_KEY",
  "validation": "AUTO",
  "characteristics": ["PRODUCTION"],
  "paths": {},
  "flows": [],
  "apiKey": {
    "propagateApiKey": true
  },
  "rate_limit": {
    "rate": 1000,
    "period_time": 60,
    "period_time_unit": "SECONDS"
  },
  "quota": {
    "quota": 1000000,
    "period_time": 2592000,
    "period_time_unit": "SECONDS"
  }
}
```

### 3. 订阅流程

```text
开发者 ──► Portal (注册 App) ──► 选择 Plan ──► 审批(可选) ──► 拿到 API Key
                                                         │
                                                         ▼
                                                  调用 API
```

## 八、认证

### 1. API Key

应用订阅 Plan → 拿到 key：

```bash
curl http://localhost:8082/my-app/api \
  -H "X-Gravitee-Api-Key: xxx"
```

### 2. OAuth2

Gateway 作为 OAuth2 Server：

```bash
# Token 端点
POST /oauth/token
  grant_type=client_credentials
  client_id=xxx
  client_secret=xxx
```

### 3. JWT

Gateway 验证 JWT：

```json
{
  "name": "jwt",
  "configuration": {
    "publicKeys": [{"key": "-----BEGIN PUBLIC KEY-----\n..."}]
  }
}
```

## 九、可观测

### 1. Prometheus

Gateway 暴露 `/metrics`（Prometheus 格式）。

### 2. Logging

集成 ELK / Loki / Fluentd。

### 3. Tracing

支持 OpenTelemetry / Jaeger。

### 4. 监控 Dashboard

Cockpit 提供：

- 实时流量
- 错误率
- 延迟
- Top consumers
- 健康状态

## 十、Access Management（独立 IAM）

### 1. 概述

- 完全独立的 OAuth2 / OIDC Server
- 可作为 Keycloak / Auth0 替代品
- 支持 SAML 2.0
- 支持多因子（MFA）

### 2. 部署

```yaml
auth:
  image: graviteeio/am:4
  management:
    type: "mongodb"
  security:
    domain: "auth.example.com"
  oauth2:
    scopes:
      - "openid"
      - "profile"
```

### 3. 与 APIM 集成

AM 管理用户 + 客户端，APIM 用 AM 颁发 Token。

## 十一、与 Kong / APISIX 对比

| 维度 | Gravitee | Kong | APISIX |
| --- | --- | --- | --- |
| API 治理 | **强**（Plan/订阅/审批） | 一般 | 一般 |
| 文档 | **自动生成** | 插件 | 插件 |
| 开发者门户 | **内置** | 商业 | ❌ |
| 数据面 | Java/Netty | OpenResty | OpenResty |
| 性能 | 中 | 高 | **极高** |
| 多环境 | ✔（Cockpit） | ❌ | ❌ |
| 协议 | HTTP | 全 | 全 |
| 商业生态 | ✔ | ✔ | ✔ |

## 十二、典型场景

- **API Marketplace**：开发者注册、订阅、计量
- **企业 API 治理**：审批 → 上线 → 监控
- **API 货币化**：付费订阅、计量计费
- **统一认证**：Access Management 独立 OIDC
- **B2B 合作伙伴门户**：自助订阅 + 文档

## 十三、最佳实践

- **多环境分离**：DEV / STAGING / PROD 用 Cockpit
- **Plan 必用**：不要 Keyless（除非真的公开）
- **订阅审批**：B2B 场景开启
- **配额 + 限流双层**：Quota 防滥用，Rate Limit 防瞬时冲击
- **API 文档**：用 OpenAPI 描述自动生成
- **Prometheus + Alert**：实时告警
- **审计日志**：商业版有，OSS 用 ELK 自建
- **MongoDB**：副本集 + 定期备份
- **JWT 轮转**：定期换签发 key
- **Portal 自定义**：logo / 域名 / 文档
