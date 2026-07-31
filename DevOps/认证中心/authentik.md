# Authentik

现代开源身份提供商。Python + Go 混合实现（前端 React）。近年快速崛起，被视作 Keycloak 的现代化替代品，特点是 **UI 友好、Flow 可视化、声明式 API-First、K8s 友好**。

## 一、定位与特点

- 一体化 IDP：OIDC + SAML + OAuth2 + SCIM
- 内置 ForwardAuth，与 Nginx / Traefik / Envoy / Caddy 完美配合
- Flow Designer：可视化设计注册 / 登录 / 找回密码 / 邀请流程
- Provider → Application 解耦模型（一个 Provider 可挂多个 App）
- API 优先，可完全 GitOps 管理
- 多租户 + 企业 SSO + 社交登录

## 二、架构

```text
┌────────────────────────────────────┐
│ 用户浏览器 / App / SDK               │
└──────────────────┬─────────────────┘
                   │ OIDC / SAML / OAuth2
                   ▼
┌────────────────────────────────────┐
│ Authentik Server (Go + Python)      │
│   - outpost (proxy / forward_auth) │
│   - core (API + 数据库 + 流程)        │
│   - worker (后端任务)                  │
└──────┬────────────┬───────────────┘
       │            │
       ▼            ▼
   PostgreSQL   Outposts
  (主体存储)     (proxy / ldap / radius / ssh)
```

两个核心组件：

- **Core**：身份、用户、组、Provider、Application、Flow
- **Outpost**：可选的代理，提供 ForwardAuth、LDAP、Proxy、RADIUS、SSH

## 三、核心概念

| 概念 | 含义 |
| ---- | ---- |
| **User** | 终端用户 |
| **Group** | 分组 |
| **Provider** | 身份源/认证 Provider（OIDC / SAML / LDAP / Social） |
| **Application** | 受保护应用（一个 App 关联一个 Provider） |
| **Flow** | 注册 / 登录 / 找回 / 邀请等可编排的认证流程 |
| **Stage** | Flow 的步骤（识别、密码、MFA、consent） |
| **Policy** | 绑定到 Flow 的策略（密码策略、MFA 强制） |
| **Property Mapping** | 把 user attribute 映射到 claim / assertion |
| **Outpost** | 部署在外网环境的代理（Forward Auth / LDAP / Radius） |
| **Event** | 系统事件流 |
| **Tenant** | 多租户（企业版） |

## 四、Flow 与 Stage

### 1. 概念

Flow 是用户走的一段流程，由 Stage 数组组成：

```text
Identification → Password → MfaValidation → Session
```

每个 Stage 是一个原子步骤，可执行自己的逻辑。MFA、密码、captcha 都可作为 Stage。

### 2. 内置 Flow

| Flow | 用途 |
| ---- | ---- |
| `default-authentication-flow` | 主登录 |
| `default-invalidation-flow` | 登出 |
| `default-password-change-flow` | 改密 |
| `default-password-recovery-flow` | 找回 |
| `default-user-settings-flow` | 资料 |
| `default-enrollment-flow` | 邀请注册 |

### 3. 自定义 Flow

UI 中拖拽 Stage，构建自定义流程。例如：

```text
captcha → user-info → password → pause → totp → user-write
```

实用于 MFA / 风险场景。

### 4. Stage 类型

| Stage | 用途 |
| ---- | ---- |
| **identification** | 用户名/邮箱/手机号 |
| **password** | 密码登录 |
| **email** | magic link |
| **totp** | 时间令牌 |
| **webauthn** | Passkey |
| **duo** | Duo MFA |
| **captcha** | 验证码 |
| **consent** | OAuth2 consent |
| **prompt** | UI 中向用户展示提示 |
| **user-write** | 写用户属性 |
| **user-read** | 读用户属性 |
| **delete** | 删除账户 |
| **deny** | 拒绝 |
| **pause** | 暂停（验证邮件后回来） |

## 五、Provider 与 Application 解耦

### 1. Provider

```text
Provider 类型：
- OAuth2 (OIDC)
- SAML 2.0
- LDAP
- SCIM
- RADIUS
- Proxy (ForwardAuth)
- Radius
- Plex (Plex.tv OAuth)
- Social: GitHub / GitLab / Google / Microsoft / Discord / Twitter / Twitch / Apple ...
- Generic OIDC / SAML
```

### 2. Application

```text
Application: my-app
   ├── Slug: my-app
   ├── Provider: my-app-oidc
   ├── Launch URL: http://app.example.com
   ├── Policy: Default MFA
   └── UI Settings: 登录方式
```

- 一个 Application 可对多个 Provider
- 一个 Provider 也能给多个 Application

### 3. 关系

```text
   Provider                                Application
       │                                       │
       ├─ Identifier: oidc-provider-1            ├─ 关联 my-app-oidc
       │                                          │
       ├─ Provider -> JWT / SAML 响应            └─ 启用 Authentik Login
       │
       └─ Property Mappings: 怎么把 user attr 映射到 claim
```

## 六、Property Mapping（Claim 映射）

将用户属性 / 组映射到 Token claim：

```yaml
expression = |
  {
    "name": user.username,
    "email": user.email,
    "groups": [g.name for g in user.groups.all()],
    "department": user.attributes.get("department", "")
  }
```

- OIDC：映射到 Access Token / ID Token
- SAML：映射到 Assertion Attribute

## 七、Outpost 与 Forward Auth

### 1. Outpost 类型

| Outpost 类型 | 含义 |
| ---- | ---- |
| **Proxy** | 反向代理 + OIDC 认证 |
| **ForwardAuth** | 转发用户校验，反向代理侧打 set headers |
| **LDAP** | 把 Authentik 当 LDAP 服务器 |
| **Radius** | Radius 接入 |
| **SSH** | SSH 跳板 |

### 2. ForwardAuth 工作原理

```text
用户请求 http://app/secret
   │
   ▼ Nginx / Traefik
   │
   ▼ GET http://authentik:9000/outpost.goauthentik.io/start
   │ (通过 cookie / session 校验)
   │
   ├── 已登录 ──► 200 + X-Forwarded-User / X-Forwarded-Email → app
   │
   └── 未登录 ──► 302 redirect → Authentik 登录页 → /callback
```

### 3. Nginx 示例

```nginx
location /outpost.goauthentik.io {
    proxy_pass http://authentik-outpost:9000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
location / {
    # forward_auth 内部伪指令（auth_request）
    auth_request /outpost.goauthentik.io/auth/nginx;
    error_page 401 = /outpost.goauthentik.io/start?rd=$scheme://$http_host$request_uri;
    proxy_pass http://app;
    proxy_set_header X-Forwarded-User $upstream_http_x_forwarded_user;
    proxy_set_header X-Forwarded-Email $upstream_http_x_forwarded_email;
    proxy_set_header X-Forwarded-Groups $upstream_http_x_forwarded_groups;
}
```

### 4. Traefik 示例

```yaml
labels:
  - "traefik.http.middlewares.authentik.forwardauth.address=http://authentik-outpost:9000/outpost.goauthentik.io/auth/traefik"
  - "traefik.http.middlewares.authentik.forwardauth.trustForwardHeader=true"
  - "traefik.http.middlewares.authentik.forwardauth.authResponseHeaders=X-Forwarded-User,X-Forwarded-Email,X-Forwarded-Groups,X-Forwarded-Preferred-Username"
```

## 八、OIDC / SAML 接入

### 1. OIDC Provider 配置

```yaml
authentication_flow: default-authentication-flow
authorization_flow: default-provider-authorization-implicit-consent
invalidation_flow: default-invalidation-flow
property_mappings:
  - authentik-core-user-oidc-property-mapping
  - authentik-core-user-email-oidc-property-mapping
issuer_mode: per_provider
client_id: my-app
client_secret: xxxx
redirect_uris:
  - http://app.example.com/callback
```

应用端：

```javascript
const oidc = new OidcClient({
  authority: 'https://ak.example.com/application/o/my-app/',
  client_id: 'my-app',
  redirect_uri: 'http://app/callback',
  scope: 'openid profile email',
});
```

### 2. SAML Provider

```text
SP / IdP 元数据可下载
   - ACS URL: /application/saml/<slug>/sso/binding/redirect/
   - EntityID: https://ak.example.com/application/saml/<slug>/metadata/
```

## 九、API-First

所有内容可 GitOps：

```bash
curl -X POST https://ak.example.com/api/v3/core/users/ \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{"username":"alice","name":"Alice"}'
```

配套：

- **Terraform Provider**：rego
- **Ansible collection**
- **Python client**（`authentik-client`）

```yaml
resource "authentik_user" "alice" {
  username = "alice"
  name     = "Alice"
  email    = "alice@example.com"
}
```

支持 **Import / Export**：

```yaml
# export 配置以 YAML 为底
resources_user:
  - username: alice
    attributes:
      department: ops
```

## 十、Forward Auth 实战

### 1. K8s 部署

```bash
helm repo add authentik https://charts.goauthentik.io
helm install authentik authentik/authentik
```

Components:

- `authentik-server`
- `authentik-worker`
- `authentik-postgresql`
- Outpost（按需）
- Redis（按需）

### 2. K8s + Nginx Ingress

```yaml
metadata:
  annotations:
    nginx.ingress.kubernetes.io/auth-url: "https://ak.example.com/outpost.goauthentik.io/auth/nginx"
    nginx.ingress.kubernetes.io/auth-signin: "https://ak.example.com/outpost.goauthentik.io/start?rd=$scheme://$http_host$request_uri"
spec:
  rules:
    - host: app.example.com
```

## 十一、SCIM 用户置备

```yaml
SCIM Provider:
   - URL: https://ak.example.com/api/v3/providers/scim/...
   - token: ...
```

同步：企业 AD → Authentik → SaaS 应用。

## 十二、用户联邦

### 1. LDAP Provider

```text
Type: LDAP
URL: ldap://ldap
Base DN: ou=users,dc=corp,dc=com
Bind DN: cn=admin
Sync: 5 min
```

### 2. Social Provider

默认支持：

- GitHub / GitLab
- Google / Microsoft / Discord
- Apple / Facebook / Twitter / Twitch
- 微信 / 企业微信（社区扩展）

UI 即可启用。

### 3. Generic OIDC

反向接外部 OIDC 作为上游。

### 4. Federation → outgoing

Authentik 把用户联邦/同步到其他系统。

## 十三、Event 流

Event 流（类似 Keycloak admin event）：

- login.success / login.failure
- user.created / user.deleted
- token.revoke
- impersonation

```yaml
notification_transports:
  - type: webhook
    url: https://siem.example.com/webhook
```

可对接：

- Webhook
- Slack
- Discord
- Email
- Matrix

## 十四、RBAC 与 RBAC-with-Backstage

- 单个权限设置（高级）
- 业务上下文中通常使用 Group + Property Mappings 承担
- 应用从 claim /groups 取角色做 AuthZ

## 十五、API + 二次开发

详细 API 文档：

```text
/applications
/certificates
/email
/events
/flows
/groups
/providers
/roles
/service-accounts
/stages
/users
```

## 十六、与 Keycloak 对比

| 维度 | Authentik | Keycloak |
| ---- | --------- | -------- |
| 实现 | Python + Go | Quarkus (Java) |
| UI | 现代（React） | 经典 |
| Flow 可视化 | ✔ | 简单 |
| Property Mappings | Python 表达式 | HCL |
| OIDC | ✔ | ✔ |
| SAML | ✔ | ✔ |
| LDAP | ✔ provider | ✔ user federation |
| Outpost (Forward Auth) | 一等公民 | ✓（stop maintenance → 推 oauth2-proxy） |
| API | REST + Terraform | REST |
| 安装 | 简单 Docker Compose | 复杂 |
| 自带管理 UI | 现代 | 全功能 |
| 文档 | 强（中文 / 英文） | 强 |
| 社区 | 快速增长 | 老牌活跃 |
| SCIM | ✔ | 部分 |

## 十七、典型场景

### 1. 统一企业内部 SSO

```text
Authentik → 多应用（GitLab / Grafana / Jira / 自研）
   ↑
AD / LDAP 联邦
```

### 2. K8s Workload Identity

```text
K8s ServiceAccount JWT ──OIDC──► Authentik
                           ←──STS Token──
```

### 3. 客户登录

```text
消费者 → Authentik (social + email magic link)
                       │
                       └── 提供 JWT 给业务后端
```

### 4. Forward Auth 统一拦截

```text
Traefik / Nginx forward_auth ──► Authentik Outpost
                                │
                                └── 通过后注入 X-Forwarded-User / Roles
```

## 十八、版本演进

- v2022：诞生
- v2023：Flow UI 改进
- v2024：Outpost 取消部署门槛；Kubernetes Operator 实验
- v2025（current）：Property Mapping 复杂表达式 / SCP-like 权限 / 企业版 Terraform

## 十九、最佳实践

- **GitOps**：整套资源走 Terraform / API 管理
- **Outpost 部署位置**：与受保护应用同拓扑
- **Forward Auth** 比 Reverse Proxy 更轻
- **Flow 设计**：用 Stage 拆粒度
- **Property Mapping**：必备：name / email / groups
- **MFA**：为 Ops / Admin 强制
- **审计**：Event Stream 走 Webhook → ELK
- **SCIM**：与 AD / Okta / Entra 同步
- **Outpost 不允许直接暴露 /outpost.goauthentik.io/start**：用 nginx 内部代理
- **Session Cookie**：明确 lifetime / refresh 设置
- **重启验证**：高可用模式 + outpost 双实例
