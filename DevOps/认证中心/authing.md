# Authing / 国产 IDaaS

国产身份云服务代表。覆盖 B2C / B2B / B2E 场景，对接企业账号 + 消费者 + 员工。

## 一、Authing 概览

- 国产 IDaaS（Identity as a Service）
- 域名：authing.cn
- 提供 SaaS 版 + 私有化版
- 多租户、用户池、组织、组
- 支持 OIDC / OAuth2 / SAML / LDAP / CAS
- 自带用户 Profile / MFA / 风控

## 二、产品线

| 产品 | 含义 |
| ---- | ---- |
| **Authing 登录** | 用户身份池（UserPool） |
| **Authing IDaaS** | 企业租户 |
| **Authing Guard** | 通用登录 UI 组件 |
| **Authing 权限** | 资源 / 角色 / 策略 |
| **Authing SSO** | 单点登录 |
| **Authing MFA** | 多因素 |
| **Authing 风控** | 行为审计 |

## 三、用户池 / 组织

### 1. 用户池

```text
UserPool: prod-pool
   ├── 应用：my-app-spa、my-app-admin
   ├── 用户：500万
   └── 邮箱 / 手机号 / 第三方账号
```

### 2. 组织

```text
Organization: acme-corp
   ├── 部门：研发 / 财务 / HR
   ├── 用户：alice（研发经理）
   └── 子组织：移动端组
```

## 四、SDK 集成

### 1. Web React

```bash
npm i @authing/react18-components
```

```jsx
import { UserProvider } from '@authing/react18-components';

<UserProvider
  appId="..."
  config={{...}}
>
  <App />
</UserProvider>
```

包含登录组件、useUser、Guard。

### 2. iOS / Android / Vue / Flutter / Node.js

各端都有 SDK，统一接口。

### 3. Spring Security / OAuth2 Resource Server

```yaml
spring:
  security:
    oauth2:
      resourceserver:
        jwt:
          jwk-set-uri: https://<tenant>.authing.cn/oidc/.well-known/jwks.json
          issuer-uri: https://<tenant>.authing.cn/oidc
```

## 五、OIDC 接入

```text
issuer: https://<tenant>.authing.cn/oidc
authorization_endpoint: /oidc/auth
token_endpoint: /oidc/token
jwks_uri: /oidc/.well-known/jwks.json
userinfo_endpoint: /oidc/userinfo
```

应用使用 PKCE / Authorization Code 流程。

## 六、MFA

支持的认证方式：

- 短信
- 邮件
- TOTP
- WebAuthn / Passkey
- 指纹
- 人脸

登录策略：

```yaml
policy:
  firstFactor: password
  secondFactor:
    - totp
    - sms
```

## 七、SSO

### 1. 标准 OAuth2 / OIDC

应用直接作为 OIDC client。

### 2. SAML 2.0

应用作为 SP，Authing 作为 IdP。

```yaml
sp:
  entity_id: urn:my-app
  acs_url: https://app/saml/acs
```

### 3. LDAP / AD Connector

```yaml
ldaps:
  server: ldap://xxx
  baseDn: dc=corp
```

把企业 AD 作为外部身份源。

## 八、权限模型

### 1. 角色 / 资源 / 策略

```text
角色: ops
资源: order
操作: read / write
策略: role:ops -> action:read/write -> resource:order
```

### 2. 授权 API

```bash
POST /authorization/check
{
  "user": "alice",
  "action": "order:read",
  "resource": "order:1"
}
```

或用 OPA / Casbin 后端。

## 九、组织管理

### 1. 多级组织

```text
集团 corp
├── 子公司 a
│     ├── 部门 aa / ab
└── 子公司 b
      ├── 部门 ba / bb
```

### 2. 同步

- 与企业 HR / CRM 同步
- 用户属性拉取定时任务
- SCIM 2.0

## 十、私有化

Authing 提供专有云版本：

- 容器化部署
- 100% 数据自己持有
- 版本一致性
- 自带 license 授权

适用：金融、电信、政企等合规场景。

## 十一、审计与合规

- 所有登录、token 颁发、权限变更走向审计日志
- 集成阿里云 / 腾讯云 / 华为云日志（Log Service）
- ISO 27001 / 等保三级

## 十二、与其他国产 IDaaS 对比

| 服务 | 公司 | 特色 |
| ---- | ---- | ---- |
| **Authing** | Authing.cn | 通用，To B 强 |
| **阿里云 IDaaS** | 阿里云 | 阿里云集成 |
| **腾讯云 TI 平台身份认证** | 腾讯云 | 微信生态集成 |
| **华为云 IAM** | 华为云 | 华为云集成 |
| **OnesLogin / IDaaS** | 国产 | 老牌 |
| **Casdoor** | 开源 | 自部署 |
| **Keycloak 自部署** | 开源 | 全功能 |

## 十三、与 Auth0 / Okta 对比

| 维度 | Authing | Auth0 | Okta |
| ---- | ------ | ----- | ---- |
| 国产化 | ✔ | ❌ | ❌ |
| 价格 | 中等 | 高 | 高 |
| 集成 | 国产云生态 | 全球服务 | 全球服务 |
| LDAP / SAML | ✔ | ✔ | ✔ |
| 自部署 | ✔ 私有化 | ✔（专有云） | ✔（专有云） |
| 安全 / 合规 | 等保三级 | SOC 2 / HIPAA | SOC 2 / FedRAMP |

## 十四、自定义认证能力

- 自定义 Pipeline
- Webhook
- 钩子函数（Pre-Login / Post-Login）
- 多租户用户池切换

## 十五、社交登录

支持的国内：

- 微信
- 钉钉
- 飞书 / Lark
- 企业微信
- 支付宝
- QQ
- 微博

国外：

- Google
- GitHub / GitLab
- Apple
- Facebook

## 十六、典型方案

### 1. SaaS B2C

```text
应用 ─► Authing (Pool)
            ├── 用户手机号 / 微信 / Apple
            ├── 风控：行为分析
            └── MFA
```

### 2. 大企业 B2E

```text
企业 AD (或 LDAP)
   │
   ▼ SCIM
Authing（中央 IDP）
   ├── Webmail / 飞书
   ├── SaaS Apps (Salesforce / Slack)
   └── 自研应用
```

### 3. 多 App SSO

```text
Authing（中心）
   ├── App 1
   ├── App 2
   └── App 3 (SAML)
```

## 十七、最佳实践

- **App + UserPool 设计**：一个 App 只看自己 Pool
- **MFA 强制**：管理后台强制
- **SCIM**：自动拉取组织 / 用户
- **私有化**：合规要求时
- **审计 / 监控**：对接到统一日志
- **Token TTL**：Access 15 min，Refresh Rotation
- **自定义 Pipeline**：调整注册 / 登录处理
