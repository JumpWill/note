# Dex

CNCF 维护的轻量级 OIDC Provider。Kubernetes 团队早期使用，作为集群级 OIDC 入口。

## 一、定位

- 专注做 OIDC Provider
- 通过 Connector 接入多种身份源（LDAP / GitHub / SAML / OIDC / Password）
- 自身不存用户（密码），只做协议转换
- 适合 K8s / 自建系统 / DevOps 场景

## 二、架构

```text
用户登录
   │
   ▼
Dex（OIDC Provider）
   │ 通过 connectors 走 OAuth2 / LDAP / SAML 验证身份
   │
   ▼
OIDC Client（K8s API / Grafana / Argo / Vault ...）
```

无用户存储，角色信息走 `groups` claim，下游用它过滤权限。

## 三、核心概念

| 概念 | 含义 |
| ---- | ---- |
| **Issuer** | Dex 的 OIDC issuer URL |
| **Client / App** | 受保护应用 |
| **Connector** | 身份源插件（GitHub / Google / LDAP / OIDC / SAML / 密码） |
| **Storage** | 自身状态后端（SQLite / Postgres / MySQL / etcd / k8s） |
| **Static Passwords** | 简单密码 connector（仅 dev） |

## 四、部署

### 1. 二进制

```bash
./dex serve config.yaml
```

### 2. Docker

```bash
docker run -d -v /dex-config.yaml:/etc/dex/config.yaml \
  ghcr.io/dexidp/dex:v2.38 \
  dex serve /etc/dex/config.yaml
```

### 3. Helm（K8s）

```bash
helm repo add dex https://charts.dexidp.io
helm install dex dex/dex
```

## 五、配置示例

```yaml
issuer: https://dex.example.com
storage:
  type: postgres
  config:
    host: pg
    database: dex
    user: dex
    password: xxx
web:
  https: 0.0.0.0:5556
  tlsCert: /etc/dex/tls.crt
  tlsKey: /etc/dex/tls.key

staticConnectors:
  - type: oidc
    id: google
    name: Google
    config:
      issuer: https://accounts.google.com
      clientID: ...
      clientSecret: ...
      redirectURI: https://dex.example.com/callback
      scopes:
        - openid
        - profile
        - email

enablePasswordDB: true
staticPasswords:
  - email: "alice@example.com"
    # bcrypt hash
    hash: $2a$10$...
    username: alice
    userID: "0c2a3835-..."
```

核心结构：

- `issuer` 公开 OIDC URL
- `storage` 状态后端
- `connectors` / `staticConnectors` 多身份源
- `enablePasswordDB` 简易密码（dev only）
- `staticClients` 自家应用

## 六、Connector 列表

| Connector | 含义 |
| --------- | ---- |
| **github / gitlab / bitbucket** | OAuth2 |
| **google / azure / gitlab / aws** | OAuth2 |
| **mock** | Dev 测试 |
| **keystone** | OpenStack Keystone |
| **ldap** | 标准 LDAP / AD |
| **saml** | SAML Service Provider |
| **oauth / oidc** | 通用 OAuth2 / OIDC |
| **linkerD** | 链接 / 补充 |

## 七、Static Client

```yaml
staticClients:
  - id: my-app
    redirectURIs:
      - http://app/callback
    name: 'My App'
    secret: xxxx
```

## 八、K8s 集成

### 1. K8s API Server 用 Dex

`kubeadm` / kind / EKS 集群可通过 `--oidc-issuer-url=https://dex` / `--oidc-client-id=...` / `--oidc-username-claim=...` 接入：

```text
K8s API Server
   │
   ▼
Bearer (ID Token from Dex)
   │
   ▼
Kubernetes auth webhook → Dex verifying JWT signature
```

RBAC 里可以看 `oidc:sub` 字段：

```yaml
roleBindings:
  - name: devops
    subjects:
      - kind: Group
        name: devops
```

Dex 把 group claim 反映到 K8s Group。

### 2. Argo / Vault / Grafana

这些系统支持 OIDC 时全部可指向 Dex：

- Argo Workflows: `--oidc-issuer` / `--oidc-client-id`
- Vault: 看 vault.md 中 OIDC
- Grafana: OAuth 配置

## 九、多租户

Dex 通过 connector `id` 区分身份源，每个 RP client 可以限制可用 connector：

```yaml
staticClients:
  - id: my-app
    name: app
    redirectURIs: [...]
    allowedConnectors: [google, github]
```

### 1. Password Connector

```yaml
enablePasswordDB: true
```

dev 简单密码，prod 禁用。

## 十、Token

Dex 颁发 `id_token` / `access_token`：

- `id_token` 默认 JWT (RS256)
- `access_token` 默认 JWT
- `refresh_token` 默认 opaque，DB 存

```json
{
  "iss": "https://dex",
  "sub": "0c2a.../google/alice",
  "email": "alice@example.com",
  "email_verified": true,
  "groups": ["devops"],
  "name": "Alice"
}
```

## 十一、API / CLI

CLI：

```bash
dexctl all /dex-conf.yaml
```

无需 admin UI，Dex 用 `configmap + yaml` 配置文件化管理。

## 十二、与 Keycloak / Logto 对比

| 维度 | Dex | Keycloak | Logto |
| ---- | --- | -------- | ----- |
| UI | ❌ | ✔ | ✔ |
| 用户管理 | ❌（依赖 IdP） | ✔ | ✔ |
| 协议 | OIDC | OIDC / SAML | OIDC / OAuth2 |
| SAMl | ✔（作 connector） | ✔ | ❌ |
| 多角色 | 通过 groups claim | RBAC / Groups | RBAC |
| 自带 admin | 弱（Grafana / Kubelogin） | 强 | 强 |
| K8s | 友好 | 强 | 弱 |
| 多租户 | 弱 | Realm | Tenant |

## 十三、与 K8s Kubelogin

Kubelogin（Go-based）作为 K8s OIDC 客户端：

```yaml
- name: oidc
  type: oidc
  config:
    id-token: <dex login>
    refresh-token: <dex refresh>
```

实现 `kubectl --user oidc` 登录。

## 十四、典型用法

### 1. K8s 集群 + Dex

K8s 集群开启 OIDC，开发者用 Dex 登录 Developer Portal。

### 2. Argo + Vault

管理员通过 Dex 登录 Argo / Vault / Grafana，组权限走 RBAC。

### 3. CI/CD + Vault

Tekton Pipeline 通过 OIDC 拿到短期 Vault token：

```text
Workflow OIDC token → exchange → Vault Token (短期)
```

## 十五、限制

- 没有 admin UI，需要 GitOps
- 不直观管理用户 / 角色
- 只支持 OIDC，对 SAML / 自定义依赖 connector
- 不适合 C 端应用（需要 IdP 后端）

## 十六、最佳实践

- **K8s 集成**：通过 OIDC + RBAC 完成单点登录
- **HA**：3 实例 + Postgres
- **HTTPS**：强制，公网不接受 HTTP
- **静态 secret**：用 Service Account
- **短期 token**：Dex Refresh Token 短期 + refresh_token expire
- **Group 同步**：用 `groups` claim 映射业务角色
