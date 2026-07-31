# Casdoor

国产开源 IDP / IAM 平台。基于 Go + React。从 Casbin 团队演化，UI 国人友好，自带用户/组织/应用/角色模型。

## 一、定位

- 单二进制 / Docker 部署
- 内置用户、组织、应用、Provider、角色、权限
- 支持 OIDC / SAML / OAuth2 / LDAP
- 中文友好（含中文UI/中文文档）
- 自带 Webhook + 短信 / 邮件连接器

## 二、架构

```text
┌──────────────────────────────────┐
│ Web Console + 嵌入式登录页        │
└─────────────┬────────────────────┘
              │
              ▼
┌──────────────────────────────────┐
│ Casdoor Server (Go)              │
│   - OIDC / SAML / OAuth2        │
│   - 社交登录 connectors          │
│   - 用户/组织/应用管理            │
│   - 权限矩阵                      │
│   - Webhook / EventBus           │
└─────────┬─────────────┬─────────┘
          │             │
          ▼             ▼
   MySQL/Postgres/   第三方 IdP
   SQLServer/Mongo    (OIDC/SAML)
   (主数据)
```

## 三、概念

| 概念 | 含义 |
| ---- | ---- |
| **Organization** | 顶层租户 |
| **User** | 平台或组织下的用户 |
| **Application** | 受保护应用 |
| **Provider** | OAuth / SAML / 邮件 / 短信 / 密码 / 社交 |
| **Role** | 角色，全局或对应用 |
| **Permission** | 权限元数据，可关联资源/操作 |
| **Group** | 分组 |
| **Webhook** | 事件回调 |
| **Plan / Subscription** | 套餐（消费资源） |
| **Cert** | 证书管理 |

## 四、部署

### 1. Docker

```yaml
services:
  app:
    image: casbin/casdoor-all-in-one
    container_name: casdoor
    ports:
      - "8000:8000"
    environment:
      RUN_IN_DOCKER: "true"
    volumes:
      - ./conf:/conf
      - ./data:/data
```

启动后访问 `http://localhost:8000`，默认 admin / 123。

### 2. 二进制

```bash
go install github.com/casdoor/casdoor/cmd/casdoor
./casdoor server
```

### 3. K8s

Helm chart：`casdoor/casdoor-chart`。

## 五、用户 / 组织 / 应用

### 1. 创建组织

```text
Organization: acme
Owner: alice
```

### 2. 创建应用

```text
Application: my-app
Redirect URIs: http://app/cb
Cert: default
Signin: Email + Google
```

### 3. 用户登录

```bash
# 用户跳到 Casdoor
GET /login/oauth/authorize?client_id=...&response_type=code&scope=...&redirect_uri=...
```

## 六、Provider 类型

| 类型 | 用途 |
| ---- | ---- |
| **GitHub / GitLab / Google / WeChat / QQ / 钉钉 / 飞书 / 企业微信** | 社交登录 |
| **SAML 2.0** | 企业 IdP 联邦 |
| **OIDC** | Identity Brokering |
| **Email** | 邮件 magic link / 验证码 |
| **SMS** | 短信验证码 |
| **LDAP / Active Directory** | LDAP 联邦 |
| **OAuth 2.0** | 第三方 OAuth |
| **CAS 2.0 / 3.0** | 高校 / 政企 |

通过新建 Provider 并挂到 Application 即可生效。

## 七、OIDC 集成

### 1. 应用端配置

Application 详情中有：

- Client ID
- Client Secret
- Redirect URL
- Logo
- Signin method

接入：

```javascript
import { SDK } from "casdoor-js-sdk";

const sdk = new SDK({
  serverUrl: "https://casdoor.example.com",
  clientId: "my-app",
  organizationName: "acme",
  appName: "my-app",
  redirectPath: "/callback",
});

sdk.signIn();
sdk.getUserInfo();
sdk.getAccessToken();
```

### 2. Spring Security

```yaml
spring:
  security:
    oauth2:
      client:
        registration:
          casdoor:
            client-id: my-app
            client-secret: xxxx
            scope: openid,profile,offline_access
            redirect-uri: "{baseUrl}/login/oauth2/code/{registrationId}"
            authorization-grant-type: authorization_code
        provider:
          casdoor:
            issuer-uri: https://casdoor.example.com
```

### 3. Token 内省

```bash
curl -X POST https://casdoor/api/login/oauth/access_token \
  -d 'grant_type=authorization_code&code=...&client_id=...&client_secret=...&redirect_uri=...'
```

## 八、SAML 接入

### 1. 创建 SAML Provider

```yaml
type: SAML
metadata_url: https://client.example.com/saml/metadata
entity_id: client-id-from-sp
attributes:
  email: email
```

### 2. Service Provider metadata

```text
GET /application/<id>/saml/metadata
```

### 3. 应用侧

签名证书来自 Cert module 下颁发的证书。

## 九、权限模型

### 1. RBAC

```text
Permission: order:read, order:write
Role: ops (包含 order:read, order:write)
User: alice (绑定了 ops 角色)
Application: my-app (在 app 范围内启用 RBAC)
```

### 2. ACL / ABAC（基于 Casbin）

Casdoor 持久化 Casbin 模型配置：

```text
p, alice, order, read
p, ops, order, *
```

### 3. 在 Token 中携带

默认在 ID Token 中：

```json
{
  "sub": "alice",
  "email": "alice@example.com",
  "groups": ["ops"],
  "permissions": ["order:read", "order:write"]
}
```

## 十、Audit & Webhook

事件：

- 登录 / 退出
- 注册 / 邀请
- 修改角色
- Token 刷新

Webhook 推送到业务系统，HMAC 签名。

## 十一、SDK

| 语言 | SDK |
| ---- | --- |
| **JavaScript** | casdoor-js-sdk |
| **Go** | github.com/casdoor/casdoor-go-sdk |
| **Java** | casdoor-java-sdk |
| **Python** | casdoor-python-sdk |
| **Dart / Flutter** | casdoor-dart-sdk |
| **iOS / Android** | 各有 SDK |

## 十二、对比 Logto / Keycloak

| 维度 | Casdoor | Logto | Keycloak |
| ---- | ------- | ----- | -------- |
| UI | 中文友好 | 现代 | 经典 |
| 协议 | OIDC / SAML / OAuth2 / CAS / LDAP | OIDC / OAuth2 | OIDC / SAML / OAuth2 |
| 后端 | Go | Node.js | Java / Quarkus |
| 数据库 | MySQL / Postgres / SQLServer / Mongo | Postgres | 多 |
| 多租户 | Org + Application | Tenant | Realm |
| 自带登录页 | ✔ | ✔ | ✔ |
| 国产化功能 | 钉钉 / 微信 / 飞书 | （部分支持） | ❌ |
| SAML | ✔ | ❌（开发中） | ✔ |
| LDAP | ✔ | ❌ | ✔ |
| 自部署 | 单二进制 + Docker | Docker Compose | JVM |

## 十三、最佳实践

- **Organization + Application**：按客户分 Org，按产品分 App
- **Provider 复用**：相同 Provider 可被多个 Application 复用
- **权限细分**：通过 RBAC + Casbin ABAC 组合，避免全部塞角色
- **多因子**：登录策略里启用 WebAuthn / TOTP
- **审计**：开启 Audit Log + Webhook
- **API Token**：用 M2M 应用做 API 集成
- **Logo / 主题**：自定义企业登录页
