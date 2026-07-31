# HashiCorp Vault

集中式密钥与敏感配置管理平台，存储 secret 而非普通配置的事实标准，重点解决「分散在 .env / Git / 配置文件里的口令、Token、证书该怎么管、谁可以拿、用了多久、作废是否及时」。

## 一、定位与特性

- **核心定位**：secret 管理（password / API key / token / 证书 / 数据库口令），不是 Nacos 那种业务配置中心
- **统一入口**：所有敏感数据从 Vault 颁发，进程不直连数据库 / 云 API
- **动态凭证**：DB 用户、AWS Access Key 都是「临时生成、租约到期自动收回」，几乎消除长期口令
- **加密即服务**：客户端把明文给 Vault，Vault 返回密文，业务不存密钥
- **审计与合规**：所有读写命中审计日志，可对接 SIEM
- **多云/多后端**：支持 Consul / Raft / S3 / MySQL / GCS / Azure 等 Storage Backend
- **场景全景**：合规（PCI-DSS、等保）、K8s 密钥、CI/CD 拉取、零信任落地

## 二、架构

```text
┌────────────────────────────────────────────────────────────┐
│                       Vault Server                          │
│                                                             │
│  ┌──────────────┐    ┌──────────────┐   ┌──────────────┐  │
│  │  HTTP API    │    │  Auth Methods │   │ Secret Engines│  │
│  │  (8200)      │    │  token / AppRole│ │ KV / DB / PKI│  │
│  │              │    │  k8s / OIDC     │ │ AWS / Transit│  │
│  └──────┬───────┘    └──────┬───────┘   └──────┬───────┘  │
│         │                   │                  │           │
│         └───────────┬───────┴──────────────────┘           │
│                     ▼                                       │
│         ┌──────────────────────────┐                       │
│         │  Request Forwarding /    │                       │
│         │  Router                   │                       │
│         └────────────┬─────────────┘                       │
│                      ▼                                     │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  Barrier（所有写都进 Barrier 后再落 Storage）         │  │
│  │   - 加密 / 解密                                        │  │
│  │   - Seal / Unseal 状态机                              │  │
│  └─────────────────────────┬───────────────────────────┘  │
│                            ▼                                │
│  ┌──────────────────────────────────────────────────┐    │
│  │  Storage Backend（物理存储）                       │    │
│  │   - Integrated Raft（v1.4+ 默认）                  │    │
│  │   - Consul / S3 / MySQL / GCS / Azure / File      │    │
│  └──────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────┘
```

### 1. Storage Backend

存放物理数据（已加密的键值）。选项：

| Backend | 用途 |
| ------- | ---- |
| **Integrated Raft** | v1.4+ 内置，推荐生产自建集群（3 或 5 节点） |
| **Consul** | 已有 Consul 集群可复用 |
| **S3 / GCS / Azure Blob** | 云原生，搭配 SSE 加密 |
| **MySQL / PostgreSQL** | 传统 DB 栈 |
| **File** | 仅 dev / 测试 |

### 2. Barrier

- 位于 Storage 之前，所有写入先过 Barrier 加密再落盘
- 加密密钥来自经过 Shamir 拆分后的 root key（Unseal Key）
- Barrier 状态：sealed / unsealed；sealed 状态下任何 request 都返回 503

### 3. Seal / Unseal

启动后默认是 sealed 状态，需要解封（unseal）才能服务：

```text
operator unseal  # 需提供 key shares
operator unseal  # 每执行一次提交一份 share
...
quorum 达到 → unsealed
```

#### Shamir 秘密分享

- root key 拆成 N 份，至少 M 份可恢复（默认 N=5, M=3）
- 任一份泄露都不足以解封
- 适合：5 个管理员各持一份，需 3 人到场

#### Auto-unseal（KMS / Cloud）

- 用 AWS KMS / GCP CKMS / Azure Key Vault / AliCloud KMS 等外部 KMS 加密 root key
- 节点重启后自动从 KMS 解封，免去人工凑 quorum
- 适合：K8s / 容器化部署，节点随时重启

```hcl
# config.hcl 片段
seal "awskms" {
  region     = "us-east-1"
  key_id     = "alias/vault-unseal-key"
  kms_key_id = "arn:aws:kms:us-east-1:111122223333:key/abcd-..."
}

storage "raft" {
  path    = "/vault/data"
  node_id = "vault-1"
}
```

## 三、核心概念

| 概念 | 含义 |
| ---- | ---- |
| **Path** | 资源的统一寻址路径，如 `secret/data/db/mysql`、`pki_int/issue/api` |
| **Secret Engine** | 一类「secret 后端」，逻辑插件，对外暴露自己的 API 路径前缀 |
| **Auth Method** | 验证「你是谁」：token / AppRole / K8s / OIDC / LDAP / TLS 证书 |
| **Policy** | HCL 描述的能力（ACL），挂到 token / role 上 |
| **Token** | 登录后的访问凭证，可挂多个 policy、可设 TTL |
| **Lease** | 动态 secret 的租约（默认 32d），到期回收，必须续约 |
| **Mount** | 把 engine / auth method 挂到某个路径前缀下 |

### 1. Path 与请求

```text
# KV v2 读
GET secret/data/myapp/db
# KV v1 读
GET secret/myapp/db
# 数据库动态凭证
POST database/creds/my-role
```

`mount` 把 `secret/`、`database/`、`pki/` 等前缀动态挂载。

### 2. Policy（HCL）

```hcl
# policy-app.hcl
path "secret/data/myapp/*" {
  capabilities = ["read", "list"]
}
path "database/creds/myapp-readonly" {
  capabilities = ["read"]
}
path "transit/encrypt/myapp" {
  capabilities = ["update"]
}
```

- `create / read / update / delete / list / sudo`
- `sudo` 可绕过 ACL 检查，慎用
- `path` 末段 `*` 表示前缀匹配

### 3. Token

- 一共两类：root（启动时初始化产生的 root token，超管）和 service token（登录后产生）
- Token 自身可挂 policy、TTL、可刷新次数、可设是否为 `orphan`（不随父 token 失效）

```bash
# 生成一个只读 1h 的 child token
vault token create -policy=app-readonly -ttl=1h
```

### 4. Lease / Renew / Revoke

对动态凭证（DB / AWS / Cloud）：

```bash
# 申请
CREDS=$(vault read database/creds/myapp-readonly)
# 查看 lease_id
vault read database/creds/myapp-readonly

# 续约
vault lease renew <lease_id>

# 主动撤销
vault lease revoke <lease_id>
```

Lease 过期 → Vault 主动调底层（revoke SQL 账号 / 关 IAM session），所以即使忘记 revoke 也安全。

## 四、Secret Engine 详解

### 1. KV（Key-Value）引擎

```text
┌──────────────┬──────────────────────────┐
│ KV v1        │ 静态 KV，覆盖写          │
│ KV v2（推荐）│ 版本化，可回滚、有元数据 │
└──────────────┴──────────────────────────┘
```

```bash
# 启 v2
vault secrets enable -path=secret -version=2 kv

# 写
vault kv put secret/myapp/db username=app password=xxx
# 读当前版本
vault kv get -mount=secret myapp/db
# 读 v1
vault kv get -mount=secret -version=1 myapp/db
# 删（保留历史）
vault kv delete -mount=secret myapp/db
# 销毁（彻底）
vault kv destroy -mount=secret -versions=2 myapp/db
```

**区别**：

| 特性 | KV v1 | KV v2 |
| ---- | ----- | ----- |
| 版本号 | 无 | 1, 2, 3… |
| 配置版本上限 | – | `max_versions` |
| 删除 | 删即无 | 软删，再 `destroy` |
| 元数据 | 无 | created/updated |

### 2. Database 动态凭证

```text
应用进程 ──POST database/creds/my-role──► Vault
                ▲                              │
                │                              ▼
              拿到用户名/口令          Vault 连 DB → CREATE USER 'app_xxx' 'pwd'
              （几小时后过期）            设置权限 → 写 ACL
                                          Lease 过期 → DROP USER
```

```hcl
# 1. 启 database engine
# vault secrets enable database

# 2. 配置 MySQL 连接
vault write database/config/myapp-mysql \
  plugin_name=mysql-database-plugin \
  connection_url="{{username}}:{{password}}@tcp(mysql:3306)/" \
  username="vault-admin" \
  password="xxx" \
  allowed_roles="myapp-readonly,myapp-readwrite"

# 3. 创建角色 + 凭据模板（动态 SQL）
vault write database/roles/myapp-readonly \
  db_name=myapp-mysql \
  creation_statements="CREATE USER '{{name}}'@'%' IDENTIFIED BY '{{password}}';
                      GRANT SELECT ON myapp.* TO '{{name}}'@'%';" \
  default_ttl="1h" \
  max_ttl="24h"

# 4. 申请
vault read database/creds/myapp-readonly
```

每次返回的用户名都不同，TTL 到期自动删 DB 账号。支持 MySQL / PostgreSQL / MongoDB / MSSQL / Oracle / Cassandra / Redis / Snowflake 等。

### 3. PKI 证书引擎

```bash
vault secrets enable pki

# 根 CA
vault write -field=certificate pki/root/generate/internal \
  common_name="myorg Root CA" ttl=87600h > ca.crt

# 中间 CA
vault secrets enable -path=pki_int pki
vault write -format=json pki_int/intermediate/generate/internal \
  common_name="myorg Intermediate CA" ttl=43800h > csr.json
vault write pki/root/sign-intermediate csr=@csr.json.csr \
  format=pem_bundle ttl=43800h > signed.json

# 颁发短证书
vault write pki_int/issue/api \
  common_name="api.svc" ttl="24h"
```

每次都签**只用一天**的证书，泄漏窗口极小。

### 4. Transit（加密即服务）

应用不持有密钥，把明文扔给 Vault，Vault 返回密文：

```bash
vault write transit/encrypt/myapp \
  plaintext=$(echo "hello" | base64)
```

应用只需 `permissions: ["update"]` 在 transit 路径上，无需读明文密钥。即使 Vault 数据库被偷，没有 root key 也解不开。

支持：encrypt / decrypt / rewrap / HMAC / sign / verify / hash / random / generate-data-key。

### 5. Cloud / AWS

```bash
vault secrets enable aws
vault write aws/roles/my-app \
  credential_type=assumed_role \
  role_arn=arn:aws:iam::111122223333:role/my-app \
  ttl=15m
# 申请临时 STS 凭证
vault read aws/creds/my-app
```

## 五、Auth Method

| 方法 | 适用 |
| ---- | ---- |
| **token** | 默认，bootstrap 用，慎用做生产认证 |
| **AppRole** | 机器对机器、CI/CD、老牌推荐 |
| **Kubernetes** | Pod 内 ServiceAccount JWT 自动登录 |
| **OIDC** | 人员走 SSO、Keycloak / Okta / 阿里云 IDaaS |
| **TLS 证书** | mTLS 客户端证书 |
| **LDAP / Userpass / GitHub** | 人员登录 |

### 1. AppRole

```bash
# 启
vault auth enable approle

# 绑定 policy
vault write auth/approle/role/myapp \
  token_policies="app-readonly" \
  token_ttl=1h \
  token_max_ttl=4h \
  secret_id_ttl=2h

# CI 流水线要拉 secret 时
vault read auth/approle/role/myapp/role-id   # role_id 长期不变
vault write -f auth/approle/role/myapp/secret-id  # 高敏感 secret_id，一次性
curl -X POST .../v1/auth/approle/login \
  -d '{"role_id":"...","secret_id":"..."}'  # 拿到 token
```

生产做法：role_id 注入配置文件，secret_id 部署时由 Vault 颁发到 CI 环境变量。

### 2. Kubernetes（ServiceAccount JWT）

```bash
vault auth enable kubernetes

vault write auth/kubernetes/config \
  kubernetes_host="https://kubernetes.default.svc.cluster.local"

vault write auth/kubernetes/role/myapp \
  bound_service_account_names=myapp-sa \
  bound_service_account_namespaces=prod \
  token_policies="app-readonly" \
  ttl=1h
```

Pod 启动时 `ServiceAccount` 注入 JWT，应用用 `.spec.containers[].volumeMounts` 拿 `/var/run/secrets/tokens/vault-token` 调 Vault 登录。

### 3. OIDC

```bash
vault auth enable oidc
vault write auth/oidc/config \
  oidc_discovery_url="https://login.example.com" \
  oidc_client_id="vault" \
  oidc_client_secret="..." \
  default_role="dev"
vault write auth/oidc/role/dev \
  user_claim="email" \
  policies="dev-readonly" \
  allowed_redirect_uris="http://localhost:8250/oidc/callback"
```

人员用浏览器登录后拿 token。Vault 自带 CLI 助手 `vault login -method=oidc`。

### 4. TLS 证书

```bash
vault auth enable cert
vault write auth/cert/certs/myapp \
  policies="app" \
  certificate=@./ca.pem \
  display_name="myapp"
```

## 六、Vault Agent

把 Vault 客户端逻辑（auto-auth、模板渲染、token 续约）抽到 sidecar 进程，简化业务代码。

```text
┌──────────────────────────────┐
│       App 容器                │
│                                │
│  /vault/secrets/config.ctmpl  │ ◄── 消费渲染后的文件
│  /vault/secrets/app.token     │ ◄── 消费 token
└──────┬───────────────────────┘
       │ file
┌──────▼───────────────────────┐
│   Vault Agent Sidecar          │
│  - auto-auth (auto 续约)      │
│  - cache (本地缓存 lease)     │
│  - template (渲染)             │
└──────┬───────────────────────┘
       │ HTTP
       ▼
     Vault Server
```

```hcl
# agent.hcl
auto_auth {
  method "approle" {
    config = {
      role_id_file_path   = "/etc/vault/role-id"
      secret_id_file_path = "/etc/vault/secret-id"
    }
  }
  sink "file" {
    config = { path = "/vault/secrets/app.token" }
  }
}

template {
  source      = "/etc/vault/config.ctmpl"
  destination = "/vault/secrets/config"
}

cache {
  use_auto_auth_token = true
}
```

```text
# /etc/vault/config.ctmpl
{{ with secret "secret/data/myapp/db" }}
DB_HOST={{ .Data.data.host }}
DB_USER={{ .Data.data.username }}
DB_PASS={{ .Data.data.password }}
{{ end }}
```

Pod 内其他容器只需 `volumeMount` 该目录，避免每个应用都集成 Vault SDK。

## 七、Spring Cloud Vault（Java 示例）

```xml
<dependency>
  <groupId>org.springframework.cloud</groupId>
  <artifactId>spring-cloud-starter-vault-config</artifactId>
</dependency>
```

```yaml
spring:
  application:
    name: myapp
  cloud:
    vault:
      uri: https://vault.svc:8200
      authentication: KUBERNETES
      kubernetes:
        role: myapp
        service-account-token-file: /var/run/secrets/kubernetes.io/serviceaccount/token
      kv:
        backend: secret
        default-context: myapp
      fail-fast: true
      config:
        order: -1  # 优先于 application.yml
```

启动后 `@Value("${db.password}")` 直接拿到 Vault 里的字段。K8s 部署时配合 ServiceAccount 即可。

## 八、K8s 集成

### 1. Vault Agent Injector（推荐）

Helm 安装 vault 仓库后开启 injector：

```bash
helm repo add hashicorp https://helm.releases.hashicorp.com
helm install vault hashicorp/vault --set "injector.enabled=true"
```

Pod 上加注解：

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
spec:
  template:
    metadata:
      annotations:
        vault.hashicorp.com/agent-inject: "true"
        vault.hashicorp.com/role: "myapp"
        vault.hashicorp.com/agent-inject-secret-config: "secret/data/myapp/config"
        vault.hashicorp.com/agent-inject-template-config: |
          {{- with secret "secret/data/myapp/config" -}}
          DB_PASS={{ .Data.data.password }}
          {{- end }}
    spec:
      serviceAccountName: myapp-sa
```

Injector 自动给 Pod 注入两个 sidecar：init 容器渲染 + agent 续约，应用内可直接 `cat /vault/secrets/config`。

### 2. CSI Secrets Store Driver

把 Vault 路径挂载成卷，由 CSI 驱动调用 Vault：

```yaml
apiVersion: secrets-store.csi.x-k8s.io/v1
kind: SecretProviderClass
metadata:
  name: vault-db
spec:
  provider: vault
  parameters:
    vaultAddress: "http://vault.vault:8200"
    roleName: "myapp"
    objects: |
      - objectName: "db-password"
        secretPath: "secret/data/myapp/db"
        secretKey: "password"
      - objectName: "api-key"
        secretPath: "secret/data/myapp/api"
        secretKey: "key"
```

```yaml
volumes:
  - name: secrets
    csi:
      driver: secrets-store.csi.k8s.io
      readOnly: true
      volumeAttributes:
        secretProviderClass: vault-db
volumeMounts:
  - name: secrets
    mountPath: /mnt/secrets
```

挂载为 **tmpfs**（内存文件系统），不落磁盘。

### 3. 对比

| 方式 | 优势 | 局限 |
| ---- | ---- | ---- |
| **Sidecar Injector** | 自动续约、模板灵活 | Pod 多两个容器 |
| **CSI Driver** | 不动业务、无 sidecar | 模板弱、轮转需触发 Sync |
| **External Secrets Operator** | GitOps 友好：与 ArgoCD / Flux 协作 | 拉取周期分钟级 |

## 九、审计日志

```hcl
# config.hcl
audit {
  file {
    path = "/vault/audit/audit.log"
  }
  socket {
    address = "tcp://siem:5140"
    type    = "tcp"
  }
}
```

输出格式是 JSON，每条记录含 `request / response / type / path / token_access` 等可对接 ELK / Splunk / Slunk 等。

生产建议：审计日志通过 stdout 落入 stdout 采集器（k8s），同时 socket 转发到 SIEM 双通道；备份用 `--log-level=info` 排查。

## 十、HA 与 Raft Integrated Storage

v1.4 起 Vault 自带 Raft 集成存储，**不再依赖 Consul**：

```hcl
storage "raft" {
  path    = "/vault/data"
  node_id = "vault-1"
}

listener "tcp" {
  address         = "0.0.0.0:8200"
  cluster_address = "0.0.0.0:8201"
  tls_disable     = false
  tls_cert_file   = "/vault/tls/tls.crt"
  tls_key_file    = "/vault/tls/tls.key"
}

api_addr     = "https://vault-1.vault.svc:8200"
cluster_addr = "https://vault-1.vault.svc:8201"
```

集群引导：

```bash
vault operator init      # 一次性，产生 root token + 5 个 unseal key
vault operator raft join https://vault-2.vault.svc:8200
vault operator unseal    # 各节点分别 unseal
```

性能瓶颈：Raft 是 CP 强一致，事务吞吐受共识影响；管理面都在 Vault 集群内，无外部依赖。

## 十一、优缺点

### 优点

- 业界事实标准，文档 / 生态 / 集群、SDK 完备
- 动态凭证 + 自动轮转，几乎消除长期口令
- 审计完备，合规友好
- 插件丰富（DB / PKI / Cloud / Transit / SSH）
- 与 K8s / Terraform / Consul / Nomad 集成成熟

### 缺点

- 运维较重：HA、Auto-unseal、备份、灾难恢复需成体系
- 性能瓶颈：动态凭证涉及外部 DB / IAM 调用，token 续约也走集群
- 强一致：Raft 故障期间不可写
- 备份就是 Storage Backend 的快照，需写演练
- Vault itself 是个高权限组件，root token 失窃就是 big problem

## 十二、最佳实践

- **Auto-unseal + 备份 root token 至 KMS**：避免 5 人凑 key
- **最小权限 Policy**：每个服务一个 role、一个 policy，禁止 `*`
- **动态凭证优先**：能用 DB / AWS / PKI 动态生成的，绝不用 KV v2 静态
- **短 TTL**：DB 凭证 1h、PKI 证书 24h、Token 1h
- **审计日志外发**：文件 + socket 至少两路，单独存
- **轮值 root token**：Operator 重新生成，定期 rotate
- **K8s 注入**：用 Vault Agent Injector，避免业务耦合 Vault SDK
- **版本与引擎审计**：定期 `vault secrets list` / `vault audit list` 清理过期 mount
- **异地灾备**：Raft 备集群 + `vault operator raft snapshot`，演练恢复
- **不可把 KV 当 Nacos 用**：业务热配置走 Nacos / Apollo，长明文密钥走 Vault
