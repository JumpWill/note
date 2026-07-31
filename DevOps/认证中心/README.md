# 认证中心

按工具分文件整理认证中心 / IAM / 身份联邦 / 授权原理与使用。

## 分类与索引

| 分类 | 工具 |
| --- | --- |
| **开源 IDP** | [Keycloak](keycloak.md)、[Authentik](authentik.md)、[Logto](logto.md)、[Casdoor](casdoor.md)、[DEX](dex.md) |
| **一体化身份底座** | [ORY 套件](ory.md)（Hydra / Kratos / Keto / Oathkeeper） |
| **反向代理认证** | [oauth2-proxy](oauth2-proxy.md) |
| **授权 (AuthZ)** | [OPA / Casbin / Cerbos](authorization.md) |
| **国产 SaaS** | [Authing](authing.md) |
| **云厂商 IAM** | [AWS / 阿里云 / 腾讯云 / 华为云 / Azure / GCP](cloud-iam.md) |

## 选型速查

| 场景 | 建议 |
| --- | --- |
| Java 老旧系统 / 强需求（OIDC + SAML + LDAP + Admin UI） | Keycloak |
| 现代 IDP / Flow 可视化 / ForwardAuth + nginx | Authentik |
| 新项目 / 现代 UI / 易上手 | Logto |
| 国产 / 多租户 / SaaS 化 | Authing / Casdoor |
| K8s / GitHub 风格 OIDC | Dex |
| 只想在已有服务上挂登录 | oauth2-proxy / Traefik forward auth |
| Authorization 策略引擎 | OPA / Cerbos / Casbin |
| 多语言 / 自建身份层 | ORY Hydra + Kratos |
| 不想自建、SaaS | Auth0 / Authing / Workos |
| 单云、已经上某朵 | 云厂商 IAM/IDaaS |

## 概念对比

| 工具 | 协议 | 多租户 | UI | 社交登录 | OIDC | SAML | LDAP | Federation | 语言栈 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Keycloak** | OIDC / SAML / OAuth2 | ✔ Realm | ✔ Admin / Account | ✔ | ✔ | ✔ | ✔ | ✔ Identity Brokering | Java |
| **Authentik** | OIDC / SAML / OAuth2 / LDAP / SCIM | ✔ | ✔ 现代 React | ✔ | ✔ | ✔ | ✔ | ✔ | Python + Go |
| **Logto** | OIDC / OAuth2 | ✔ Tenant | ✔ 友好 | ✔ | ✔ | ❌（开发中） | ❌（开发中） | ❌ | TypeScript / Node |
| **Casdoor** | OIDC / SAML / OAuth2 | ✔ Org | ✔ | ✔ | ✔ | ✔ | ✔ | ❌ | Go |
| **DEX** | OIDC | ❌ | ❌（CLI） | ❌ | ✔ | ❌ | ✔ | ✔ Connector 多 | Go |
| **Auth0** | OIDC / SAML | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | SaaS |
| **Authing** | OIDC / SAML / OAuth2 / LDAP | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | SaaS / 国产 |
| **Okta** | OIDC / SAML | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | SaaS |
| **ORY Hydra** | OAuth2 / OIDC | ❌ | ❌ | ❌ | ✔ | ❌ | ❌ | ❌ | Go |
| **ORY Kratos** | 多协议 | ✔ Identity | ✔ 可视 | ✔ | ✔ | ❌ | ❌ | ✔ | Go |
| **oauth2-proxy** | OIDC reverse proxy | ❌ | ❌ | ❌ | ✔ | ❌ | ❌ | ✔ | Go |
| **OneLogin / JumpCloud** | OIDC/SAML | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | SaaS |

## 核心机制

- **认证 vs 授权**：AuthN（你是什么人） + AuthZ（你能做什么），认证由 IDP 解决，授权由 Policy 引擎解决
- **Token 三剑客**：
  - **Access Token**：短期，用于调用 API（JWT 多）
  - **Refresh Token**：长期，用于换 Access Token
  - **ID Token**：OpenID 专用，含用户身份声明
- **OIDC = OAuth2 + Identity**：在 OAuth2 之上加 `/userinfo` + ID Token，事实标准
- **SSO**：浏览器 Cookie + OIDC 统一身份，多应用共享登录态
- **Federation**：跨 IDP 互信（Google 登录接 Keycloak），通过 Identity Brokering
- **PKCE**：现代 SPA / Mobile 推荐使用 Authorization Code + PKCE
- **Zero Trust**：不要相信网络位置，每次请求都校验（短期 token + mTLS）

## 落地要点

- **认证分层**：客户端（PKCE） → IdP（OIDC） → API（Bearer Token） → 资源服务器（scope / role 校验）
- **Token 短+刷新**：Access Token 5–15 min，Refresh Token 7–30 天 + Rotation
- **撤销机制**：Token Introspection / Logout 端点（OIDC RP-Initiated Logout）
- **角色**：IdP 颁发 Realm 内角色；业务侧应再做 AuthZ 决策
- **多租户**：用 Keycloak Realm / Logto Tenant / Authing 用户池
- **密码学**：客户端不要自己写 auth 逻辑，集成成熟 SDK（如 oidc-client-js）
- **审计 / 合规**：登录、操作、token 撤销走向 SIEM
- **K8s**：Pod 加 OIDC 时优先 Dex + JWT
- **联邦身份**：员工用 SSO、消费者用社会化登录，融合到一个 IDP
