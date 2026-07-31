# Logto

Silverhand 团队维护的现代身份基础设施。TypeScript + Node.js 实现。定位是"现代、易用、轻量、对开发者友好"。

## 一、定位与特点

- 完整支持 OIDC / OAuth2
- 基于 PostgreSQL + Redis（比 Keycloak 轻量）
- 现代 UI（React）
- 内置 A/B 实验与多租户
- 自带无密码 / MFA / SSO
- 支持 Social Login / Enterprise SSO
- 多语言 SDK（`@logto/...`）

## 二、架构

```text
┌────────────────────────────────┐
│ Web Console / React SDK        │
└────────────┬───────────────────┘
             │ OIDC / Frontend SDK
             ▼
┌────────────────────────────────┐
│ Logto Core（Node.js）          │
│   - OAuth / OIDC Provider     │
│   - Authorization Server      │
│   - Sign-in Experience        │
│   - MFA / Passwordless        │
│   - Webhooks                  │
└────┬───────────────┬───────────┘
     │               │
     ▼               ▼
 PostgreSQL      Redis
 （主数据 + OIDC Tables）
```

- 核心是 Authorization Server
- 管理面 + Sign-in Experience 一站俱全

## 三、概念

| 概念 | 含义 |
| ---- | ---- |
| **Tenant** | 多租户，按租户隔离 user / app |
| **Application** | 注册的应用（SPA / WebApp / Native / M2M） |
| **Connector** | 邮件 / 短信 / 社交 IdP |
| **Resource** | 受保护 API（对应 audience） |
| **Scope** | 权限范围（openid / email / profile / custom） |
| **Role** | 角色（按 resource 划分） |
| **Organization** | 多租户下的组织，与 B2B 场景 |
| **Sign-in Experience** | 登录页/注册页配置 |

## 四、部署

### 1. Docker Compose（最简）

```bash
mkdir logto && cd logto
curl -O https://raw.githubusercontent.com/logto-io/logto/master/docker-compose.yml
docker compose up -d
```

核心环境变量：

```bash
TRUST_PROXY_HEADER=1
DB_URL=postgres://user:pass@db:5432/logto
REDIS_URL=redis://redis:6379
NODE_ENV=production
```

### 2. K8s

Helm Chart 来自 logto-io/charts：

```bash
helm repo add logto https://logto-io.github.io/charts
helm install logto logto/logto
```

### 3. Logto Cloud

开箱即用 SaaS：[https://cloud.logto.io](https://cloud.logto.io)

## 五、租户 + 应用

### 1. 创建租户

```text
Logto Console → Tenants → Create tenant
```

每个租户有自己的 OIDC issuer URL：

```text
https://<tenant>.logto.app
```

### 2. 创建 Application

```text
Applications → Create application
- Type: SPA / WebApp / Native / M2M
- Redirect URI: http://app/callback
```

获得：

- App ID: `app_xxx`
- App Secret: `secret_xxx`（仅 web/m2m）

## 六、SDK 集成

### 1. Web（JavaScript / TypeScript）

```bash
npm i @logto/react
```

```tsx
import { LogtoProvider, useLogto, LogtoConfig } from '@logto/react';
const config: LogtoConfig = {
  endpoint: 'https://<tenant>.logto.app',
  appId: '<your-app-id>',
};

function App() {
  return (
    <LogtoProvider config={config}>
      <Page />
    </LogtoProvider>
  );
}

function Page() {
  const { signIn, signOut, fetchUserInfo } = useLogto();
  ...
}
```

`@logto/vue`、`@logto/next`、`@logto/nuxt`、`@logto/angular` 等可用。

### 2. M2M

```javascript
import { createClient } from '@logto/api';

const client = createClient({
  endpoint: 'https://<tenant>.logto.app',
  appId: process.env.APP_ID,
  appSecret: process.env.APP_SECRET,
});

const { value: token } = await client.accessTokens.create({ type: 'Bearer' });
```

`client_credentials` 流程。

### 3. Spring Cloud / Spring Security

```yaml
spring:
  security:
    oauth2:
      client:
        registration:
          logto:
            client-id: <app-id>
            client-secret: <app-secret>
            scope: openid,profile,offline_access
            redirect-uri: "{baseUrl}/login/oauth2/code/{registrationId}"
        provider:
          logto:
            issuer-uri: https://<tenant>.logto.app/oidc
```

## 七、组织 (Organization) 与 B2B

### 1. 概念

- 多组织：每个组织独立用户与成员
- Multi-tenant SaaS 适用

### 2. 数据模型

```text
User <-> Organization (many-to-many)
User has Role in Organization
```

### 3. API

POST `/api/organizations/{id}/users/{userId}/roles`

## 八、连接器 (Connector)

| 类型 | 含义 |
| ---- | ---- |
| **Email** | 邮件密码 / 邮件 magic link |
| **Phone** | 短信验证码 |
| **Social** | Google / GitHub / Apple / WeChat |
| **SAML** | 企业 IdP |
| **OIDC** | OIDC 联邦 |

Webhooks 触发器：

- User 注册
- 社交登录
- 短信回执

## 九、登录体验 (Sign-in Experience)

- 多种方式组合：密码 + 验证码 / 仅社会登录 / 邮件 magic link
- 用户名 / 手机号 / 邮件
- 无密码（passkey）
- MFA：TOTP / WebAuthn

### 1. 注册即登录（Force Login）

```yaml
sign-in-experience:
  forgotPassword: enabled
  social-sign-in: enabled
  createAccount: enabled
```

### 2. 自定义体验

- 公司 Logo
- 自定义 CSS / 字体
- 路由 / 跳转策略
- 国际化多语言

## 十、OIDC 配置

Logto 端：

```text
GET https://<tenant>.logto.app/oidc/.well-known/openid-configuration
```

```json
{
  "issuer": "https://<tenant>.logto.app",
  "authorization_endpoint": "...",
  "token_endpoint": "...",
  "userinfo_endpoint": "...",
  "jwks_uri": "..."
}
```

应用通过 Authorization Code + PKCE 登录：

```text
GET /oidc/auth?client_id=...&response_type=code&scope=openid profile&redirect_uri=...
```

## 十一、Token

| 类型 | 用途 |
| ---- | ---- |
| Access Token | API Bearer |
| Refresh Token | offline_access |
| ID Token | OIDC 用户身份 |

- 默认 Access Token 是 JWT
- Refresh Token Rotation v1+
- Session Management（Back-Channel Logout 前置）

## 十二、RBAC

### 1. Resource

```json
{
  "name": "order",
  "scopes": ["read", "write"]
}
```

### 2. Role

```json
{
  "name": "ops",
  "scopes": [{ "resource": "order", "scopes": ["read", "write"] }]
}
```

### 3. 在 Token 中

```json
{
  "scope": "order:read order:write",
  "roles": ["ops"]
}
```

## 十三、Audit & Webhooks

- 登录、注册、密码重置、社交连接、token 撤销
- Webhook 推送到外部（Salesforce / Slack / 业务系统）
- 重试 + 签名校验

## 十四、多语言

| 字段 | 多语言 |
| ---- | -------- |
| UI | 自动（30+） |
| 邮件 | 多语言模板 |
| 短信 | 多语言模板 |

## 十五、与 Keycloak 对比

| 维度 | Logto | Keycloak |
| ---- | ----- | -------- |
| 实现栈 | Node.js / TS | Java / Quarkus |
| UI | 现代 / React | 经典 / Angular |
| 数据库 | PostgreSQL | Postgres / MariaDB / Oracle |
| 协议 | OIDC / OAuth2 | OIDC / SAML / OAuth2 |
| LDAP | ❌（开发中） | ✔ |
| SAML | ❌（开发中） | ✔ |
| Social | 一流 | 一流 |
| 多租户 | Tenant | Realm |
| 自部署 | ✔ Docker Compose / K8s | ✔ Operator |
| API | REST + GraphQL | Admin REST |
| 文档 | 中文好 | 中等 |

## 十六、最佳实践

- **应用选择类型正确**：SPA / Web / Native / M2M 各自类型
- **Refresh token 持久**：浏览器存 localStorage，做好 XSS 防护
- **PKCE**：SPA / Native 强制
- **Organizations**：B2B 场景使用
- **自定义 connector**：必要时自建 social connector
- **多语言**：确保每个语言邮件、短信文案检查
- **Webhook**：消费前用签名验证
- **审计**：开启 Audit Log，往 ELK 推送
