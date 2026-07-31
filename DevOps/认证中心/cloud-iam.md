# 云厂商 IAM / IDaaS 对比

主要云厂商的身份与访问管理（IAM / IDaaS）服务对比。

## 一、阿里云 RAM / IDaaS / SSO

### 1. RAM (Resource Access Management)

阿里云的 IAM。提供：

- 用户 / 用户组 / 角色
- 权限策略（Action / Resource / Condition / Effect）
- AssumeRole（跨账号 / 临时凭证）
- STS（Security Token Service）短时 AccessKey

```json
{
  "Version": "1",
  "Statement": [{
    "Effect": "Allow",
    "Action": ["oss:GetObject", "oss:PutObject"],
    "Resource": "acs:oss:*:*:my-bucket/*"
  }]
}
```

支持 SSO 集成：

- SAML 2.0
- OIDC
- SCIM 用户同步

### 2. IDaaS（应用身份服务）

- 阿里云 IDaaS 是 PaaS 服务
- 与钉钉 / 飞书 / 应用 SSO 集成
- 应用账号管理
- OIDC / SAML / LDAP

### 3. 场景

- 跨账号 / 跨云资源治理
- SSO 集成（Okta / Keycloak）

## 二、腾讯云 CAM / CIAM / 企业 SSO

### 1. CAM (Cloud Access Management)

类似 AWS IAM：

- 用户 / 角色 / 策略
- 临时 STS
- 子账号 / 主账号

```yaml
version: 2.0
statement:
  - effect: allow
    action:
      - cos:GetObject
    resource:
      - qcs::cos:ap-shanghai:uid/125...:mybucket-125.../*
```

### 2. CIAM (Customer Identity Access Management)

- 消费者场景 IDaaS
- 用户池 / 多应用 / MFA / 社交登录
- 集成微信生态（微信登录 / 小程序登录）

### 3. 企业 SSO

- 接入企业 IdP
- 与其他 IdP 联邦（Ping / Okta / Authing）

## 三、华为云 IAM / IdentityCenter

### 1. IAM

- 用户 / 用户组 / 策略
- 委托 / 临时凭证（Agency）
- 跨账号 / 跨 Region

### 2. IdentityCenter (原 SSO)

- 多账号身份汇总
- 与企业 IdP 集成（OIDC / SAML）
- 权限集（Permission Set）

### 3. OneAccess

- 集中 IDaaS 服务
- 应用账号管理
- 与钉钉 / 飞书 / 企业微信集成

## 四、AWS IAM / IAM Identity Center

### 1. IAM

- User / Group / Role / Policy
- AssumeRole / STS（Temporary）
- Service Control Policy (SCP) 在 Organizations
- IAM Conditions / Permission Boundary

### 2. IAM Identity Center（前 SSO）

- 跨账号 SSO
- Active Directory / SAML 2.0 连接
- 自动 Provisioning

### 3. Cognito

- 消费者 / 移动端身份
- 用户池（User Pool）
- 身份池（Identity Pool）
- OIDC / SAML / 社交登录

## 五、Azure Entra ID（前 Azure AD）

### 1. Microsoft Entra ID

- 现代行业标准
- User / Group / Application / Service Principal
- Conditional Access
- MFA / Risk-Based

### 2. App Registration

```text
App Registration
   ├── Application (Client) ID
   ├── Tenant ID
   ├── Client Secret / Certificate
   └── Redirect URIs
```

### 3. Managed Identity

- 资源（VM / AKS / App Service）托管身份
- 自动获 access token

### 4. B2C

- 消费者场景
- 自定义 signup / signin flow

## 六、GCP Cloud IAM / Identity Platform / Workforce Identity Federation

### 1. Cloud IAM

- Service Account / Role / Binding
- Workload Identity Federation（跨云 / GHA 等免密访问）
- IAM Conditions

### 2. Identity Platform (Firebase Auth)

- 消费者场景
- OIDC / SAML / 社交登录
- 多租户

### 3. Workforce Identity Federation

- 员工用 SAML 联邦到 GCP
- 不需要 service account key file

## 七、横向对比

### 1. 核心模型

| 厂商 | 用户层 | 服务层 |
| ---- | ------ | ------ |
| **AWS** | IAM User / Role | Service Account / Instance Profile |
| **Azure** | Entra ID User / Group | Managed Identity / Service Principal |
| **GCP** | Cloud Identity User | Service Account |
| **阿里** | RAM User / Role | RAM Role（AssumeRole） |
| **腾讯** | CAM User | CAM Role |
| **华为** | IAM User | IAM Agency |

### 2. 临时凭证

| 厂商 | 服务 | 时长 |
| ---- | ---- | ---- |
| **AWS** | STS | 15min ~ 12h |
| **Azure** | OAuth2 Bearer | 1h ~ 24h |
| **GCP** | OAuth2 Bearer | 1h |
| **阿里** | STS AssumeRole | 15min ~ 12h |
| **腾讯** | STS / TKE OIDC | 1h |
| **华为** | STS Agency Token | 15min ~ 12h |

### 3. SSO 联邦

| 厂商 | 服务 |
| ---- | ---- |
| **AWS** | Identity Center / Cognito |
| **Azure** | Entra ID（含 SAML / OIDC） |
| **GCP** | Workforce Identity Federation |
| **阿里云** | RAM SSO（OIDC/SAML）+ IDaaS |
| **腾讯云** | 企业 SSO / CIAM |
| **华为云** | IdentityCenter / OneAccess |

### 4. 消费者场景

| 厂商 | 服务 |
| ---- | ---- |
| **AWS** | Cognito |
| **Azure** | Entra External ID |
| **GCP** | Identity Platform |
| **阿里云** | 阿里云 IDaaS（含 CIAM） |
| **腾讯云** | CIAM（消费者身份云） |

### 5. 联邦 IdP 兼容性

| 厂商 | AD/LDAP | SAML IdP | OIDC IdP |
| ---- | ------- | -------- | -------- |
| **AWS** | ✔ | ✔ | ✔ |
| **Azure** | ✔ | ✔ | ✔ |
| **GCP** | ✔ | ✔ | ✔ |
| **阿里** | ✔ | ✔ | ✔ |
| **腾讯** | ✔ | ✔ | ✔ |
| **华为** | ✔ | ✔ | ✔ |

## 八、K8s 集群 OIDC 集成

| 厂商 | 集群服务 | OIDC 配置 |
| ---- | -------- | --------- |
| AWS | EKS | `--oidc-issuer-url` |
| Azure | AKS | Entra ID OIDC |
| GCP | GKE | Workload Identity Federation |
| 阿里 | ACK | RRSA |
| 腾讯 | TKE | CAM IdP |
| 华为 | CCE | IAM Identity |

## 九、自建 IDP + 云厂商联邦

常见模式：使用 Dex / Keycloak 内部 IDP，连接云厂商。

### 1. AWS

```bash
aws iam create-saml-provider \
  --saml-metadata-document file://metadata.xml
```

Keycloak 作为 IdP + AWS STS AssumeRoleWithSAML。

### 2. GCP / Azure / 阿里 / 腾讯

类似 OIDC / SAML 联邦，按具体厂商文档。

## 十、托管服务中的认证体系

### 1. AWS Cognito User Pool

```yaml
cognito:
  user_pool:
    auto_verified_attributes: ["email"]
    mfa: optional
    password_policy:
      min_length: 12
```

### 2. Azure B2C

```text
User Flow：sign-up or sign-in
   ├── Identity providers：local / Google / Facebook
   ├── Multifactor authentication
   ├── Conditional Access
   └── Page layouts (custom)
```

### 3. 阿里云 IDaaS

```text
User Pool / Application
   ├── Social Providers：支付宝 / 微信
   ├── Enterprise：钉钉 / 飞书
   └── MFA
```

## 十一、安全与合规

### 1. 共同点

- 最小权限
- IAM Conditions / Conditional Access
- MFA 强制
- 操作审计 → KMS / Log Service
- Break-glass account

### 2. 各家差异化

- AWS：SCPs + GuardDuty + IAM Access Analyzer
- Azure：Conditional Access + PIM（Privileged Identity Management）
- GCP：IAM Recommender / Access Transparency
- 阿里云：ActionTrail + 配置审计
- 腾讯云：CloudAudit + 堡垒机
- 华为云：CTS / DBSS / IAM 实时检测

## 十二、选型

| 场景 | 建议 |
| ---- | ---- |
| 单云 + 私有用户 | 云原生 IAM |
| 单云 + 员工 | Identity Center / IdentityCenter / SSO |
| 单云 + C 端 | Cognito / B2C / IDaaS / CIAM |
| 多云 | Dex / Keycloak 中央 |
| 已有企业 AD | 各家都支持 |

## 十三、最佳实践

- **最小权限**：每个角色 / 服务独立 Policy
- **不长期凭证**：用 STS / Workload Identity
- **MFA 强制**：管理操作多重认证
- **审计**：操作日志入 SIEM
- **凭证轮转**：定期 Rotate AccessKey
- **权限边界**：SCP / Permission Boundary 防越界
- **跨账号**：用 AssumeRole 而非共享 key
- **Break-glass**：保留应急账号 + 监控
- **K8s Workload Identity**：IRSA / Workload Identity Federation / RRSA / TKE OIDC
