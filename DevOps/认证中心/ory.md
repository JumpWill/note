# ORY 套件

ORY 的开源身份基础设施由多个独立微服务构成。开发可任选组合：

- **Hydra**：OAuth2 / OIDC Provider
- **Kratos**：用户管理 / 注册流程 / 多因素
- **Keto**：权限引擎（Zanzibar-style）
- **Oathkeeper**：身份/授权代理（reverse proxy）
- **Hydra+Maester**：用 K8s CRD 管理 Hydra Clients

定位：组件化、API-First、企业级。

## 一、Hydra

### 1. 定位

OAuth2 / OIDC Provider，只负责 identity broker + token 颁发。
不存 user。

### 2. 架构

```text
Auth (Kratos)            Hydra                      App
  │                       │                         │
  │ login / consent       │                         │
  │──────────────────────▶│                         │
  │                       │  TTL Token 颁发         │
  │                       │────────────────────────▶│
  │                       │  /userinfo /logout      │
  │                       │◀────────────────────────│
  │ logout                │                         │
  │──────────────────────▶│                         │
  │                       │  revoke                 │
```

### 3. 部署

```bash
docker run -d --name hydra \
  -p 4444:4444 -p 4445:4445 \
  oryd/hydra:v1.11 serve all --config /etc/hydra/hydra.yml
```

Postgres + Redis 配套。

### 4. 主要 API

- `/oauth2/auth` / `/oauth2/token` / `/oauth2/revoke` / `/oauth2/introspect`
- `/userinfo`
- `/admin/clients` Client CRUD

### 5. 与 SPA / Mobile

PKCE + Front-/Back-Channel Logout 一流支持。

### 6. 优势 vs Keycloak

- API 优先（无 UI）
- 微服务（Oathkeeper / Keto / Kratos 组合）
- 性能强（Go 实现）
- 更可控的服务拆分

## 二、Kratos

### 1. 定位

用户身份与注册 / 登录会话。HTTP REST API + JS SDK。

### 2. 能力

- 注册 / 登录 / 登出
- 多种验证方式：密码 / 验证码 / 邮件 / TOTP / WebAuthn / OAuth / SAML
- 邮件和短信流
- 验证与恢复（忘记密码）
- 多端可编程 UI（BFE：Identity Flows UI）

### 3. 数据模型

```text
Identity
   └── Credentials
        ├── Password
        ├── WebAuthn
        ├── TOTP
        └── OIDC
   └── RecoveryAddress（用于密码找回）
   └── VerifiableAddress（用于邮件验证）
```

### 4. 部署

```yaml
# config.yaml
dsn: postgres://...
selfservice:
  flows:
    login:
      ui_url: http://app/login
    registration:
      ui_url: http://app/signup
smtp:
  host: smtp.example.com
```

### 5. Flow

- Browser Registration Flow
- Browser Login Flow
- Settings Flow
- Verification Flow
- Recovery Flow

## 三、Keto

### 1. 定位

Zanzibar-style 权限引擎。Google 内部使用的权限模型。

### 2. 关系模型

```text
namespace: object#relation@user
  - example: doc:read#writer@alice
```

- `namespace` 资源
- `object` 实例
- `relation` 关系
- `user` 主体（用户或组）

### 3. API

- `/check` 授权检查
- `/expand` 关系展开
- `/models` 配置

```bash
curl -X POST /relation-tuples \
  -d '{"namespace":"doc","object":"readme","relation":"viewer","subject_id":"alice"}'

curl -X POST /check \
  -d '{"namespace":"doc","object":"readme","relation":"viewer","subject_id":"alice"}'
```

### 4. 集成

应用每次调用 Keto /check 决定权限。日志可低延迟。

## 四、Oathkeeper

### 1. 定位

身份/授权反向代理。对所有请求：

- 检查 JWT
- 进行 Keto / 内置策略决定
- 注入自定义头（X-User-ID / X-Roles）

### 2. 配置

```yaml
# access_rules.yaml
- id: protected-app
  upstream_url: http://app
  match:
    url: http://gateway/<*>
    methods: [GET, POST]
  authenticators:
    - handler: jwt
      config:
        jwks_url: https://hydra/.well-known/jwks.json
  authorizer:
    handler: keto
    config:
      keto_url: http://keto
  mutators:
    - handler: id_token
```

挂载到 K8s Ingress / Traefik / Nginx。

## 五、整体架构（典型）

```text
   ┌─────────────────────┐
   │       App           │
   └──────────┬──────────┘
              │
   Gate   Oathkeeper (proxy)
              │
   AuthN  Hydra (OAuth2/OIDC)
              │
   User  Kratos
              │
   AuthZ  Keto
              │
   各组件独立水平扩展
```

## 六、SDK

- **Kratos**：JS、React Native、Swift、Kotlin
- **Hydra**：REST（任何语言）
- **Keto**：REST / gRPC
- **Oathkeeper**：配置文件驱动

```javascript
import { Configuration, V0alpha2Api } from '@ory/kratos-client';
const kratos = new V0alpha2Api(new Configuration({ basePath: 'http://kratos' }));
```

## 七、对接企业 / OIDC

### 1. Federate（Kratos）

Kratos 可注册其他 OIDC IdP 作为登录方式：

```yaml
selfservice.methods.oidc.config.providers:
  - id: hydra
    provider: generic
    client_id: ...
    client_secret: ...
    issuer_url: http://hydra
    mapper_url: http://hydra/.well-known/openid-configuration
```

用户 "Login with Okta" / "Login with Azure AD"。

## 八、K8s Operator

ORY 提供多个 operator：

```bash
helm install hydra ory/hydra
helm install kratos ory/kratos
helm install keto ory/keto
helm install oathkeeper ory/oathkeeper
```

```yaml
apiVersion: hydra.ory.sh/v1alpha1
kind: OAuth2Client
metadata:
  name: my-app
spec:
  grantTypes: ["authorization_code", "refresh_token"]
  responseTypes: ["code"]
  redirectUris:
    - http://app/cb
  scope: "openid profile email"
```

Maester / operator 让 Hydra Client 配置完全 GitOps。

## 九、案例

### 1. K8s multi-tenant SaaS

- 每个客户一个 OIDC Client
- Keto 表达跨租户权限
- Oathkeeper 在 ingress 注入用户身份

### 2. 微服务 + JWT

- App 客户端 → Kratos 注册登录
- Kratos 获取 access_token（通过 Hydra 颁发）
- App requests → Oathkeeper → 后端，带 token claims

## 十、与 Keycloak / Authing 对比

| 维度 | ORY | Keycloak | Authing |
| ---- | --- | -------- | ------- |
| 组件化 | ✔ | ❌（单元） | ❌ |
| OIDC | Hydra | ✔ | ✔ |
| 用户管理 | Kratos | ✔ | ✔ |
| 权限引擎 | Keto | UMA | 自带 |
| 反向代理 | Oathkeeper | Gatekeeper（已停止） | 无 |
| 自部署 | 多个微服务 | 单体（Quarkus） | SaaS |
| UI | 需自建 | 内置 | 内置 |
| 复杂 | 高 | 中 | 低 |

## 十一、优劣

### 1. 优势

- 组件灵活组合
- 云原生友好 + K8s Operator
- OAuth2 / OIDC / Zanzibar / mTLS 一应俱全
- 性能好（Go）

### 2. 劣势

- 没有统一 UI（每个组件有自己的后台）
- 学习曲线陡
- 社区相对 Keycloak 小
- 部分仍 0.x beta 状态
- 故障点多

## 十二、最佳实践

- **K8s 上 ORY Operator**：GitOps
- **OAuth Client 外部存储**：Hydra Client 用 DB
- **Keto 权限模型**：先正确建模再写代码
- **Oathkeeper 配置化**：通过 MAUI 路由
- **Back-Channel Logout**：BPFLog + push token revocation
- **Token 短期**：Hydra 颁发 access 5–15 min
- **审计**：每个组件都支持 hook log
