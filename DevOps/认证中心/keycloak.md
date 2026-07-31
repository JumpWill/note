# Keycloak

Red Hat 主导的开源 IAM/SSO 平台。功能强大（OIDC + SAML + OAuth2 + LDAP + User Federation），是大多数企业自建 IDP 的首选。

## 一、定位与特点

- OIDC + OAuth2 + SAML2 协议合一
- 内置用户库 + Federation（LDAP / AD / 第三方 OIDC / SAML）
- 主题 / Realm 多租户
- 自带 Account 管理控制台
- 基于 Quarkus（v17+）构建，可基于 Quarkus 优化运行时
- 角色 + 组 + 客户端（client） + 角色映射
- 协议映射器（Claim Mappings）灵活

## 二、架构

```text
┌──────────────────────────────────┐
│      Browser / CLI / SDK        │
└─────────────┬────────────────────┘
              │ OIDC / SAML / OAuth2
              ▼
┌──────────────────────────────────┐
│  Keycloak Server (Quarkus)       │
│   - Authentication Server       │
│   - Login Flows                 │
│   - Consent / Brokered          │
│   - Token Provider              │
│   - Themes / Localize           │
│   - Account Console             │
└─────┬──────────────────┬────────┘
      │                  │
      ▼                  ▼
 Internal DB         External IdP
 (Postgres / MariaDB) (LDAP / SAML / OIDC)
```

### 1. Realm / User / Client / Role

| 概念 | 含义 |
| ---- | ---- |
| **Realm** | 命名空间，独立的用户/客户端/角色集合 |
| **User** | Realm 下的终端用户 |
| **Client** | 受 Keycloak 保护的应用程序 |
| **Role** | 一组权限（Realm 级或 Client 级） |
| **Group** | 用户的分组 |
| **Identity Provider** | 联邦外部身份 |
| **Authentication Flow** | 自定义认证流程（注册、忘记密码、MFA） |

### 2. 协议映射

Keycloak 提供了协议映射器（OIDC / SAML），可以将自定义 user attribute 映射到 token 中：

```text
user.attribute.tier -> id token.claims.tier
```

## 三、部署

### 1. 启动模式

```bash
bin/kc.sh start-dev      # 开发模式（HTTP，明文配置）
bin/kc.sh start          # 生产模式（要求 HTTPS + 显式 db）
```

### 2. 数据库

```bash
bin/kc.sh build \
  --db=postgres \
  --db-url=jdbc:postgresql://db/keystore \
  --db-username=kc \
  --db-password=xxx \
  --features=token-exchange
```

启动会自动 Flyway 迁移。

### 3. K8s / Operator

```bash
kubectl apply -f https://raw.githubusercontent.com/keycloak/keycloak/release/24.0/deploy/keycloak-operator.yaml
```

```yaml
apiVersion: k8s.keycloak.org/v2alpha1
kind: Keycloak
metadata:
  name: example
spec:
  instances: 3
  db:
    vendor: postgres
  http:
    tlsEnabled: true
  features:
    - token-exchange
    - admin-fine-grained-authz
```

## 四、客户端接入

### 1. OIDC Client 接入

```text
Keycloak /admin (administrative console)
Realm: master → 创建 client
Client ID: my-app
Client protocol: openid-connect
Access Type: confidential
Valid Redirect URIs: http://app/callback
Web Origins: http://app
Service Account: on (client_credentials)
```

应用侧配置：

```json
{
  "issuer": "http://kc/realms/myrealm",
  "client_id": "my-app",
  "client_secret": "xxxxx",
  "redirect_uri": "http://app/callback",
  "scope": "openid profile email"
}
```

### 2. PKCE（前端）

```javascript
// 建议使用 oidc-client-ts / next-auth / keycloak-js
import Keycloak from 'keycloak-js';
const kc = Keycloak({
  url: 'http://kc/',
  realm: 'myrealm',
  clientId: 'spa',
});

kc.init({ onLoad: 'login-required', checkLoginIframe: false })
  .then(authenticated => {});
```

Keycloak-js 提供 init / login / logout / token management。

### 3. 服务端（Node.js / Python）

各种语言官方或社区 SDK：

- `keycloak-nodejs-connect`（Express 中间件）
- `python-keycloak-client`
- `keycloak-admin-client`（管理 API）

```python
from keycloak import KeycloakOpenID
kc = KeycloakOpenID(
    server_url="http://kc/",
    realm_name="myrealm",
    client_id="my-app",
    client_secret_key="xxxxx",
)
tokens = kc.token("alice", "password")
userinfo = kc.userinfo(tokens["access_token"])
```

## 五、Token

### 1. 类型

| 类型 | 含义 |
| ---- | ---- |
| Access Token | API 访问凭证，JWT 或 opaque |
| Refresh Token | 换 Access Token |
| ID Token | 用户身份（OIDC） |

Keycloak 默认 Access Token 是 JWT（v22+ 默认 HS256/RS256 可选）。

### 2. JWT 验证

API 端用 `iss / aud / exp / kid / sig` 校验：

```python
import jwt
from keycloak import KeycloakOpenID

def decode_token(token):
    return kc.a_decode_token(token, key=kc.public_key())
```

### 3. Token Exchange（v17+）

`client_credentials` → 跟用户 token 交换；v24+ 内置稳定。

## 六、用户联邦 (Federation)

### 1. LDAP / Active Directory

```yaml
ldap:
  connection:
    url: ldap://ad:389
    bindDN: cn=kc,ou=users,dc=corp,dc=com
    bindCredential: xxx
  user:
    baseDn: ou=users,dc=corp,dc=com
    usernameLDAPAttribute: sAMAccountName
    rdnLDAPAttribute: cn
  sync:
    periodic: true
    interval: 86400
    pageSize: 1000
```

同步策略：周期 / 变更 / 仅按需

### 2. Identity Brokering（联邦其他 IdP）

```yaml
identityProviders:
  - alias: google
    providerId: google
    config:
      clientId: xxx
      clientSecret: xxx
  - alias: okta
    providerId: oidc
    config:
      authorizationUrl: ...
      tokenUrl: ...
```

Realm 用户可以「Link Google」或「Login with Google」。

### 3. SAML / OIDC 入站

```yaml
identityProviders:
  - alias: customer-portal
    providerId: saml
    config:
      idpEntityId: https://customer.com
      singleSignOnService.url: https://customer.com/sso
      singleSignOnService.binding: POST
      nameIDPolicyFormat: urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress
      signingCertificate: ...
```

## 七、角色 + 组 + 客户端角色

### 1. Realm Role

Realm 内全局：

```text
admin / dev / viewer
```

### 2. Client Role

绑定在 Client 上，Client 看到自己的角色：

```text
my-app:write / my-app:read
```

Client 可在 token 中包含 client roles（需 mapper）。

### 3. Group

把用户归到 group，把 role 赋给 group：

```text
group: devops
   members: alice, bob
   realm roles: dev
   client roles (my-app): write
```

### 4. 服务账号 Role

```yaml
client:
  serviceAccountsEnabled: true
  directAccessGrantsEnabled: false
  authorizationServicesEnabled: true
```

Authorization 资源服务器检查：

```bash
POST /realms/myrealm/protocol/openid-connect/token
Authorization: Basic <client>
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials
```

## 八、UMA / Fine-Grained Auth

### 1. AuthZ Services

```yaml
client:
  authorizationServicesEnabled: true
  authorizationSettings:
    allowRemoteResourceManagement: true
```

资源 / 权限 / 策略 / 决策：

```json
{
  "resources": [{"name": "order-1", "type": "order"}],
  "policies": [
    {"name": "owner-can-read", "type": "owner"},
    {"name": "role-admin-can-write", "type": "role", "roles": ["admin"]}
  ],
  "scopes": ["read", "write"]
}
```

应用调用 Keycloak 决定访问：

```bash
POST /realms/myrealm/authz/protect/resource-name
ticket: <UMA ticket>
```

### 2. UMA 2.0

适合「资源所有者委托他人访问」，例如客户数据授权。

## 九、Theming

Keycloak 提供 HTML / 主题：

- Login theme
- Account theme
- Admin theme
- Email theme

通过 `keycloak/themes/...` 文件系统或 jdbc 加载。

## 十、Events + Audit

- Login Events
- Admin Events

可在 Admin UI 查看：

```yaml
events:
  enabled: true
  listeners:
    - jboss-logging
    - email
  expiration: 720
```

外发到 Kafka / Logstash via `eventsConfigs`。

## 十一、自定义 SPI

Keycloak 通过 SPI 提供 User Storage / Authenticator / Protocol Mapper / Token Manager / Event Listener：

```java
public class CustomUserStorageProvider implements UserStorageProvider {
    ...
}
```

打包 → `kc.sh build` → 启动加载。

## 十二、账号自助服务

自带 `/realms/{realm}/account`：

- 改密码
- 多因子绑定（TOTP、WebAuthn）
- 应用授权管理（OAuth2 Consent）
- 查看登录历史

## 十三、密码学

- v26+ 默认 RS256 / RS384 / RS512
- 可换 ES256 / ES384 / EdDSA
- 密钥轮换通过 `keys` 接口
- HSM：使用 PKCS#11 模块加载（OpenSSL 调度）

## 十四、HA / Cluster

- 无状态节点 + DB 集群
- Cache：内置 Infinispan
- 索引 session / client state
- 多节点需要同步 Infinispan（JDBC / TCP）

```bash
bin/kc.sh start \
  --cache=ispn \
  --cache-stack=jdbc-ping \
  --db-url-host=pg \
  --cluster=kc
```

## 十五、与 Spring Boot / Spring Security

```xml
<dependency>
  <groupId>org.springframework.boot</groupId>
  <artifactId>spring-boot-starter-oauth2-resource-server</artifactId>
</dependency>
```

```yaml
spring:
  security:
    oauth2:
      resourceserver:
        jwt:
          issuer-uri: http://kc/realms/myrealm
```

`@PreAuthorize("hasRole('admin')")` 即生效。

## 十六、与 K8s 集成

### 1. Dex 作为中间

实际部署：K8s 集群级 OIDC 用 Dex，对接 Keycloak（Dex 是 connector）。

### 2. Keycloak Operator

直接用 Keycloak Operator 管理 K8s 内 Keycloak + 用户 `KeycloakRealmImport` CRD。

```yaml
apiVersion: k8s.keycloak.org/v2alpha1
kind: KeycloakRealmImport
metadata:
  name: my-realm
spec:
  realm:
    realm: myrealm
    clients:
      - clientId: my-app
        ...
```

### 3. Keycloak Gatekeeper / oauth2-proxy

外部反向代理（详见 oauth2-proxy.md）。

## 十七、CodeToCode 实战

### 1. 创建 Realm / Client / Role

```bash
kcadm.sh config credentials --server http://kc/ --realm master --user admin --password admin
kcadm.sh create realms -s realm=myrealm -s enabled=true
kcadm.sh create clients -r myrealm -s clientId=my-app -s 'redirectUris=["http://app/cb"]' -s publicClient=false -s secret=xxxx
kcadm.sh create roles -r myrealm -s name=admin
```

### 2. 用户登录

```text
GET /realms/myrealm/protocol/openid-connect/auth?
  client_id=my-app&response_type=code&scope=openid&redirect_uri=...&state=...
```

### 3. 取 Token

```bash
curl -X POST http://kc/realms/myrealm/protocol/openid-connect/token \
  -d grant_type=authorization_code \
  -d code=<auth_code> \
  -d client_id=my-app \
  -d client_secret=xxxx \
  -d redirect_uri=http://app/cb
```

## 十八、最佳实践

- **始终 HTTPS**：v18+ 不接受 HTTP for production，dev mode 例外
- **External DB**：PostgreSQL + 备份 + WAL 归档
- **Admin 控制台**：拆 admin realm 和 user realm（建议）
- **Token TTL**：Access 5–15 分钟，Refresh 7–30 天 + Rotation
- **Consent**：关闭对 first-party client
- **Brute force protection**：开启 bruteForceDetection
- **密码策略**：length / complexity / not username
- **MFA**：默认让 realm 启用 TOTP，UI 中引导
- **事件日志**：外置 ELK / SIEM
- **客户端 secret 轮转**：定期轮换
- **Realm 配置备份**：用 Realm Import CRD 化管理
