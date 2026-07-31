# Rancher

多集群 Kubernetes 管理平台，SUSE 旗下开源（早期由 Rancher Labs 创建），被广泛用于统一纳管 EKS/AKS/GKE、自建 RKE2/K3s 集群以及导入已有集群。

## 一、定位与特性

- 单一控制面管理多套 K8s 集群（local + N 个 downstream）
- 通过 import agent 将任意 K8s 集群接入，无需重新部署
- 内置 GitOps（Fleet）、监控（Monitoring v2 / Prometheus Operator）、日志（Banzai Logging）、存储（Longhorn）、安全（NeuVector）
- 强多租户：Global / Cluster / Project / Namespace 四层 RBAC
- 支持 LDAP / SAML / OIDC 多种外部认证
- 提供 kubectl shell、API proxy、CLI（rancher-cli）

## 二、架构

```text
┌───────────────────────────────────────────────────────────┐
│              Rancher Server（Helm 部署在 local K8s）       │
│   ┌──────────────┐  ┌─────────────┐  ┌────────────────┐   │
│   │  rancher     │  │  fleet      │  │  monitoring    │   │
│   │  (UI/API)    │  │  (GitOps)   │  │  /logging/...  │   │
│   └──────┬───────┘  └──────┬──────┘  └────────┬───────┘   │
│          │                 │                 │           │
│          ▼                 ▼                 ▼           │
│   Steve API + Norman API  +  cluster API proxy             │
└──────────────┬────────────────────────────────────────────┘
               │ mTLS (Cattle 连接隧道)
   ┌───────────┼───────────┬───────────────┐
   ▼           ▼           ▼               ▼
Downstream Cluster A   B   C   ... (导入的 K8s)
   │           │           │
   ▼           ▼           ▼
cattle-cluster-agent  cattle-node-agent
```

- **Rancher Server**：核心服务，UI、API、controller、etcd backup operator 都跑在这里
- **Local 集群**：Rancher 自身安装所在的 K8s 集群（也叫 "local cluster"），可以被同时管理
- **Downstream 集群**：被纳管的业务 K8s 集群（EKS/ACK/自建 RKE2/导入的任意 K8s）
- **cattle-cluster-agent**：每个 downstream 集群部署的 agent，与 Server 建立 mTLS 长连接
- **cattle-node-agent**：每个节点上的 DaemonSet，负责节点级任务（label、污点同步等）
- **Steve API**：Norman API 的新一代实现，对接真实 K8s API（基于 dynamic client + unstructured）
- **Norman API**：Rancher 自身的资源模型抽象（Cluster、Project、User、GlobalRole 等）

## 三、Rancher API 作为 K8s API 代理

Rancher 把所有 downstream 集群的 K8s API 统一暴露在单一入口：

```text
https://<rancher-server>/k8s/clusters/<cluster-id>/v1/...
https://<rancher-server>/k8s/clusters/c-m-xxx/v1/namespaces
```

- Server 收到请求 → 找到对应 cluster-agent 通道 → 转发到下游 kube-apiserver
- 单一 kubeconfig 即可访问所有集群，仅切换 `--server` 与 cluster name
- UI 上点击集群后看到的 Deployment / Pod 全部走的这个通道

意义：用户无需每个集群单独保存 kubeconfig，所有访问通过 Rancher 鉴权 + 审计。

## 四、集群接入方式

### 1. 导入已有集群（Import Existing）

```bash
# 在 Rancher UI 上：Cluster Management → Import Existing
# 拿到 clusterRegistrationToken 的 manifests
# Apply 到目标集群
```

```yaml
# 在目标 K8s 上 apply
apiVersion: v1
kind: Namespace
metadata:
  name: cattle-system
---
# rancher-cluster-agent 来自 Rancher UI 提供的 curl 命令
```

- 适合已有 EKS / AKS / GKE / 自建 K8s
- 集群可设 External（仅通过 Rancher 访问）或 Imported
- 仅装 agent，不接管控制面

### 2. RKE2 / K3s Provisioning

- Rancher 直接 provision 出 RKE2 或 K3s 集群
- 节点注册由 Rancher 驱动（SSH / 云 API / vSphere / bare metal）
- v2.7 起 RKE1 弃用，RKE2 成为推荐

### 3. 托管集群接入（EKS / AKS / GKE）

- 在 Cluster Management → Create 中选择云厂商
- 输入凭证（AKSK / Service Account），Rancher 调用云 API 创建集群
- 创建完成后自动安装 cluster-agent

| 方式 | 适用 | 控制面归属 |
| ---- | ---- | ---------- |
| Import | 已有集群 | 用户原有 |
| RKE2/K3s Provision | 自建 | Rancher 创建 |
| 托管 K8s Provision | 云厂商 | 云厂商 |

## 五、认证与鉴权

### 1. 认证源

- **本地用户**：内置 Rancher 用户库
- **LDAP / Active Directory**：OpenLDAP / AD 集成，按 group 关联
- **SAML 2.0**：Okta / Azure AD / Keycloak 等
- **OIDC**：Keycloak / Dex / Auth0
- **Ping + Shibboleth**：学术场景

### 2. RBAC 模型

| 层级 | 作用范围 | 资源 |
| ---- | -------- | ---- |
| **Global** | 整个 Rancher | GlobalRole / GlobalRoleBinding |
| **Cluster** | 单个 downstream 集群 | ClusterRole / ClusterRoleBinding |
| **Project** | 一组 Namespace | ProjectRole / ProjectRoleBinding |
| **Namespace** | 单个 NS（标准 K8s） | Role / RoleBinding |

### 3. Project 概念（重点）

**Project 是 Rancher 独有的抽象**，对应一组 Namespace + 一组成员 + 资源配额：

```yaml
apiVersion: management.cattle.io/v3
kind: Project
metadata:
  name: dev-team
  namespace: c-m-abcde
spec:
  clusterName: c-m-abcde
  displayName: Dev Team
  description: Dev team workloads
  resourceQuota:
    limit:
      requestsCpu: "40"
      requestsMemory: 80Gi
  namespaceDefaultQuota:
    limit:
      requestsCpu: "2"
      requestsMemory: 4Gi
```

Project 会被翻译成下游集群的：

- 一组 Namespace
- 一组 Role / RoleBinding（ProjectRole 展开）
- ResourceQuota 对象

> Project 不属于 K8s 原生概念，仅存在于 Rancher 层；导出集群后不会保留。

## 六、多租户模型（Global / Cluster / Project / Namespace）

```text
Global (Rancher 全局)
  └── Cluster (一个 downstream K8s)
        └── Project (业务组 / 团队)
              └── Namespace (K8s 原生)
                    └── Deployment / Service / ...
```

- 一个用户可在 Global 层是 admin，在某 Cluster 仅是 viewer
- Project 内可设置成员角色（Owner / Member / Read-only / Custom）
- 资源配额可下放到 Project / Namespace 层级

## 七、内置能力

### 1. Fleet GitOps

- Rancher 内置的 GitOps 引擎，基于 GitRepository + Bundle + ClusterGroup
- 与 Argo CD 思路一致，但深度集成在 Rancher 中

```yaml
apiVersion: fleet.cattle.io/v1alpha1
kind: GitRepo
metadata:
  name: my-app
  namespace: fleet-default
spec:
  repo: https://github.com/org/repo
  branch: main
  paths:
    - overlays/prod
  targets:
    - clusterSelector:
        matchLabels:
          env: prod
```

### 2. Monitoring（基于 Prometheus Operator）

- Helm chart `rancher-monitoring`，部署 Prometheus + Alertmanager + Grafana
- 默认抓取 cluster-agent、etcd、ingress、节点 exporter
- UI 直接集成 Grafana 视图

### 3. Logging（基于 Banzai Logging / Logging v2）

- 引入 rancher-logging chart
- 后端可选 Elasticsearch / Splunk / Kafka / S3
- Pipeline: Fluent Bit → Banzai → 后端

### 4. Longhorn 存储

- 分布式块存储，Helm 部署 `rancher-longhorn`
- 适合自建集群作为默认 StorageClass

### 5. NeuVector 安全

- 镜像扫描 + 运行时安全 + 网络策略可视化
- 由 SUSE 维护，集成进 Rancher Prime

## 八、CLI 与 kubectl shell

### 1. kubectl shell（UI 内置）

- 浏览器内直接跑 kubectl，不需要本地 kubeconfig
- 走的也是 API 代理通道，受当前用户权限约束

### 2. rancher-cli（已 deprecated）

- 历史上提供 `rancher login`、`rancher context` 等命令
- 2.5+ 建议直接用 kubeconfig + Rancher API proxy

### 3. 直接使用 kubectl + kubeconfig

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: admin-token
  namespace: cattle-system
type: Opaque
data:
  # token from Rancher UI: Security → Users → API Keys
```

```bash
# kubeconfig 里 server 指向 Rancher
kubectl --context <cluster-name> get nodes
```

## 九、升级与备份

### 1. 升级

- Rancher Server 通过 Helm upgrade 升级
- 注意 chart version 与 K8s 版本兼容矩阵
- 升级前 disable 第三方 chart 再升级更安全

### 2. 备份（rancher-backup operator）

```bash
# 安装 backup-restore-operator
helm install rancher-backup-crd rancher-charts/rancher-backup-crd \
  -n cattle-resources-system --create-namespace

helm install rancher-backup rancher-charts/rancher-backup \
  -n cattle-resources-system
```

```yaml
apiVersion: resources.cattle.io/v1
kind: Backup
metadata:
  name: backup-2026-07-31
spec:
  timeout: 1h
  storageLocation:
    s3:
      endpoint: s3.amazonaws.com
      bucketName: rancher-backups
      region: us-east-1
      folder: backups
      credentialSecretName: s3-credential
      credentialSecretNamespace: cattle-resources-system
```

```bash
# 恢复
rancher-backup restore --restore backup-2026-07-31
```

- 备份包含：etcd 中的所有 Rancher 资源 + chart 状态
- 备份不包含 downstream 集群数据，需各自备份

## 十、优缺点

### 优点

- 多集群纳管能力极强，UI 体验成熟
- import 集群零侵入，对存量 K8s 友好
- Project + RBAC 多租户模型清晰
- 生态完善：Fleet / Monitoring / Logging / Longhorn / NeuVector 一站式
- 社区与商业版（Rancher Prime）双轨，SUSE 持续投入

### 缺点

- 架构复杂，agent 通道故障会放大影响面
- Project 是 Rancher 独有抽象，迁移 / 导出受限
- K8s 新版本跟进偶有滞后（特别是 GA 节点级特性）
- 大规模（数百集群）下 Server 调优需要经验
- 中文文档相对国产平台少

适用：多集群统一纳管、有现成 K8s 想补齐 UI、想要一站式运维栈的企业。

## 十一、最佳实践

- **生产必装 backup operator**：每天全量备份 + S3 异地
- **生产双实例 HA**：Rancher Server 至少 2 副本 + 外部 DB（PostgreSQL / MySQL）
- **外部数据库**：不要用内置 etcd 单点，生产用托管 RDS
- **TLS 证书**：cert-manager 自动签发，避免自签证书过期
- **Project 命名一致**：dev/test/prod 三个 Project 对应三套 Namespace 模板
- **import 集群注意 kube-apiserver 兼容**：版本跨度太大 agent 起不来
- **监控自身**：Rancher Server 也要装监控，看清楚谁卡了
- **批量操作谨慎**：UI 上的批量删除会经 API 代理，慎用
- **审计**：开启 Rancher 审计日志（`auditLog` 配置），所有动作落 S3 / syslog