# Operator 开发（基于 Operator SDK）

## 一、为什么要做 Operator

### 1.1 业务背景

```text
Operator 是 K8s 扩展能力的核心模式。
本质：将运维领域知识（Operator 模式）编码到软件中。

现实场景：
  - 自研数据库：部署、扩缩容、备份、升级
  - 消息中间件：Kafka 集群、RocketMQ 集群
  - 缓存：Redis Cluster、Memcached
  - 存储：Ceph、MinIO
  - 监控：Prometheus 联邦集群
  - 大数据：Spark、Flink、Elasticsearch

Operator 让 K8s 不只是 "调度 Pod"，而是 "运维应用"。
```

### 1.2 Operator 核心价值

```text
1. 自动化运维
   - 部署、扩缩容、备份、升级
   - 故障自愈
   - 无人值守

2. 领域知识编码
   - DBA 的运维经验 → 代码
   - SRE 的故障处理 → 代码
   - 业务专家的部署流程 → 代码

3. 与 K8s 生态融合
   - kubectl get/apply/delete
   - 监控、告警、日志
   - 滚动升级、灰度发布

4. 标准化运维
   - 同一类应用统一管理
   - 减少运维错误
   - 提升效率
```

### 1.3 Operator vs 普通 Controller

```text
┌─────────────────┬────────────────────┐
│  普通 Controller │  Operator           │
├─────────────────┼────────────────────┤
│  通用逻辑        │  领域专业逻辑      │
│  Deployment     │  MySQL Operator   │
│  副本管理        │  部署+主从+备份  │
│                 │  +升级+故障恢复  │
│  通用         │  专业              │
│  单一          │  复杂              │
└─────────────────┴────────────────────┘
```

---

## 二、Operator 核心概念

### 2.1 Operator 模式

```text
Operator = CRD + Controller + 运维领域知识

  ┌─────────────────────────────────────────┐
  │  CRD（自定义资源）                     │
  │  - 定义资源 schema                     │
  │  - 用户的期望状态                      │
  └────────────────┬────────────────────────┘
                   │
                   ↓ reconcile
                   │
  ┌─────────────────────────────────────────┐
  │  Controller（自定义控制器）             │
  │  - watch CR                            │
  │  - 调谐 spec → status                 │
  │  - 管理相关 K8s 资源                    │
  └────────────────┬────────────────────────┘
                   │
                   ↓ operate
                   │
  ┌─────────────────────────────────────────┐
  │  K8s 资源（Pod/Service/ConfigMap...）  │
  │  业务资源（数据库实例/消息队列...）    │
  └─────────────────────────────────────────┘
```

### 2.2 Operator 核心循环

```text
Reconcile Loop（调谐循环）：

  ┌────────────────────────────────────┐
  │  1. Watch CR                        │
  │     （变更时触发）                  │
  └────────────┬───────────────────────┘
               │
               ▼
  ┌────────────────────────────────────┐
  │  2. Get 当前状态                    │
  │     - spec（期望）                  │
  │     - status（实际）                │
  │     - 关联资源                      │
  └────────────┬───────────────────────┘
               │
               ▼
  ┌────────────────────────────────────┐
  │  3. Diff 分析差异                   │
  │     - spec.replicas vs actual     │
  │     - spec.image vs deployment     │
  └────────────┬───────────────────────┘
               │
               ▼
  ┌────────────────────────────────────┐
  │  4. 调谐（Reconcile）               │
  │     - 创建缺失资源                  │
  │     - 更新不匹配资源                │
  │     - 删除多余资源                  │
  └────────────┬───────────────────────┘
               │
               ▼
  ┌────────────────────────────────────┐
  │  5. Update status                   │
  │     - phase                         │
  │     - conditions                   │
  │     - 业务状态                       │
  └────────────┬───────────────────────┘
               │
               ▼
  ┌────────────────────────────────────┐
  │  6. Requeue（再次调谐）             │
  │     - 定期同步                       │
  │     - 事件触发                       │
  └────────────────────────────────────┘
```

---

## 三、Operator SDK 与 Kubebuilder

### 3.1 工具对比与定位

```text
┌──────────────────┬──────────────────────────────────────────────────┐
│ 工具             │ 职责                                            │
├──────────────────┼──────────────────────────────────────────────────┤
│ Kubebuilder      │ K8s 官方脚手架，生成项目骨架、CRD、Controller    │
│                  │ 代码、Makefile、envtest、webhook 配置            │
│ Operator SDK     │ Operator Framework 的 CLI；包装 Kubebuilder +    │
│                  │ 提供 bundle（OLM）、scorecard、run --bundle 等   │
│ controller-      │ Go 运行时库，封装 client / cache / workqueue /  │
│ runtime          │ reconciler 等核心 API                         │
│ kustomize        │ 部署 Operator / CRD / RBAC / webhook             │
└──────────────────┴──────────────────────────────────────────────────┘
```

**两者的关系**（理解关键）：

```text
Operator Framework
   │
   ├─ Operator SDK (CLI) ── 包装 ──> Kubebuilder (CLI)
   │                                       │
   │                                       ▼
   │                              controller-runtime (Go 库)
   │
   └─ OLM / Catalog / Scorecard  ── 与 Kubebuilder 互补 ──> 走 OperatorHub
```

- **Kubebuilder 是底座**，Operator SDK 调用它来生成代码——`operator-sdk init` 在内部基本等价于 `kubebuilder init`
- **Operator SDK 多出的能力**：bundle 生成（走 OLM / OperatorHub）、scorecard 验证、`run --bundle` 模式
- **没有 Operator SDK，Kubebuilder 也能独立用**，只是不能直接打包发布到 OperatorHub

**生产选型**：

| 场景 | 推荐 |
| --- | --- |
| 学习、内部 Operator、单一项目 | **Kubebuilder**（轻量、文档好） |
| 自有 Operator + GitOps 部署 | **Kubebuilder**（不需要 OLM） |
| 要发到 **OperatorHub** | **Operator SDK**（自动生成 bundle/CSV） |
| 多语言 Operator（Ansible / Helm） | **Operator SDK**（Kubebuilder 只支持 Go） |
| 已有 Helm / Ansible Chart 想快速包装成 Operator | **Operator SDK**（`--plugins=helm` / `--plugins=ansible`） |
| Helm chart 想"声明式"管理 | **Operator SDK helm plugin**（无 controller 逻辑） |

> 💡 **一句话**：Operator SDK = Kubebuilder + OLM 周边。如果不上 OperatorHub，**只用 Kubebuilder 就够了**。

---

### 3.2 Kubebuilder 完整使用流程

#### 3.2.1 安装

```bash
# 1. 二进制安装（推荐）
curl -L -o kubebuilder https://go.kubebuilder.io/latest/linux/amd64
chmod +x kubebuilder && mv kubebuilder /usr/local/bin/
kubebuilder version

# 2. macOS
brew install kubebuilder

# 3. 指定版本（生产锁定）
curl -L -o kubebuilder https://github.com/kubernetes-sigs/kubebuilder/releases/download/v4.6.0/kubebuilder_linux_amd64
```

#### 3.2.2 初始化项目

```bash
# 1. 创建空目录
mkdir my-operator && cd my-operator

# 2. go.mod（kubebuilder init 会复用）
go mod init github.com/example/my-operator

# 3. 初始化（plugins=go/v4 是当前主流 layout）
kubebuilder init \
  --domain example.com \
  --repo github.com/example/my-operator \
  --project-name my-operator \
  --plugins=go/v4
```

**init 干了啥**：

| 文件 | 内容 |
| --- | --- |
| `PROJECT` | 项目元数据，kubebuilder 用它找类型 |
| `Makefile` | 完整构建 / 测试 / 部署流水线（`make help` 看 target） |
| `cmd/main.go` | Manager 入口，注册 Scheme / Reconciler / Webhook |
| `go.mod` + `go.sum` | 加 controller-runtime、k8s.io/api 等依赖 |
| `Dockerfile` | 多阶段构建镜像 |
| `.gitignore` / `.dockerignore` | 忽略二进制和临时文件 |
| `test/utils/` | envtest 工具（apiserver / etcd 路径解析） |

#### 3.2.3 创建 API（CRD + Controller 骨架）

```bash
# 标准：创建 Kind + Resource + Controller 骨架
kubebuilder create api \
  --group database \
  --version v1 \
  --kind MySQLCluster \
  --resource \
  --controller
```

**生成的文件**：

```text
api/v1/
├── groupversion_info.go      # GroupVersion 注册
├── mysqlcluster_types.go     # Spec / Status 结构体（你要改的）
└── zz_generated.deepcopy.go   # 深拷贝（make generate 生成）

internal/controller/
├── mysqlcluster_controller.go # Reconcile 骨架（你要写的核心逻辑）
└── suite_test.go             # envtest 入口
```

**关键 flag**：

| flag | 含义 |
| --- | --- |
| `--resource` | 生成 Resource（不带就是只生成 type alias，业务自定义） |
| `--controller` | 生成 Controller 骨架（不带 = 纯类型库） |
| `--namespaced` | Namespace 范围（默认 true；CRD 是 cluster scope 时用 `--namespaced=false`） |
| `--plural` | 自定义复数名 |
| `--crd` | 旧版生成 CRD（v3+ 默认 true，无需手写） |

#### 3.2.4 创建 Webhook

```bash
# admission webhook（defaulting + validating）
kubebuilder create webhook \
  --group database \
  --version v1 \
  --kind MySQLCluster \
  --defaulting \
  --programmatic-validation
```

**三种 webhook**：

| 类型 | 干啥 | 实现方法 |
| --- | --- | --- |
| `--defaulting` | 注入默认值 | `Default(ctx, obj)` |
| `--programmatic-validation` | 拒绝非法 CR | `ValidateCreate` / `ValidateUpdate` |
| `--conversion` | 多版本间转换 | `ConvertTo` / `ConvertFrom` |

> ⚠️ webhook 需要**证书**——`make deploy` 自动注入 cert-manager；`make run` 本地需要手动 `make webhook-cert`（v4 自带脚本）。

#### 3.2.5 Kubebuilder 项目完整目录

```text
my-operator/
├── api/                              # CRD 类型定义
│   └── v1/
│       ├── groupversion_info.go
│       ├── mysqlcluster_types.go     # Spec/Status + 注解
│       ├── mysqlcluster_webhook.go   # Webhook 实现
│       └── zz_generated.deepcopy.go  # 自动生成
├── cmd/
│   └── main.go                       # Manager 入口
├── internal/
│   └── controller/
│       ├── mysqlcluster_controller.go
│       └── suite_test.go             # envtest 入口
├── config/
│   ├── crd/bases/                    # CRD yaml（make manifests 生成）
│   ├── rbac/                         # role.yaml / role_binding.yaml
│   ├── manager/                      # Deployment
│   ├── webhook/                      # Service + MutatingWebhookConfiguration
│   ├── samples/                      # 示例 CR yaml
│   ├── certmanager/                  # cert-manager 证书
│   └── default/                      # kustomize 入口
├── test/                             # e2e 测试
├── Dockerfile
├── Makefile
├── PROJECT                           # kubebuilder 元数据
├── go.mod
└── go.sum
```

#### 3.2.6 Kubebuilder 日常命令

```bash
# 改了注解 / 类型后必跑
make manifests            # 重新生成 CRD / RBAC / webhook 配置
make generate             # 重新生成深拷贝函数

# 改完代码调试
make install                  # 装 CRD 到集群（kubectl apply -f config/crd/bases/）
make run                    # 本地跑 Operator（连 ~/.kube/config）

# 跑测试
make test                  # envtest：启 etcd + kube-apiserver，跑 controller 测试
KUBEBUILDER_ASSETS="$(setup-envtest use 1.30.x -p path)" make test

# 构建 + 部署
make docker-build docker-push IMG=registry.example.com/my-operator:v1.0.0
make deploy IMG=registry.example.com/my-operator:v1.0.0

# 加新 CRD
kubebuilder create api --group cache --version v1 --kind RedisCluster --resource --controller

# 加 webhook
kubebuilder create webhook --group database --version v1 --kind MySQLCluster \
  --defaulting --programmatic-validation

# 多 group（一个项目多个业务域）
kubebuilder edit --multigroup=true

# 看所有子命令
kubebuilder help
```

#### 3.2.7 Kubebuilder 的局限（明确）

| 局限 | 影响 | 解决 |
| --- | --- | --- |
| 不生成 OLM bundle | 无法直接上 OperatorHub | 用 Operator SDK 生成 bundle |
| 不支持 Helm/Ansible plugin | 只能用 Go 写 | 改用 Operator SDK |
| 不带 Ansible / Helm runtime | 不能用低代码方式写 reconcile | 同上 |
| 部署只用 kustomize | 不支持 terraform 等 | 同上 |

> 💡 **如果只需要写一个 Go Operator + 用 kustomize 部署**——**Kubebuilder 就够**，不用装 Operator SDK。

---

### 3.3 Operator SDK 完整使用流程

#### 3.3.1 安装

```bash
# 最新 release
curl -L -o operator-sdk \
  https://github.com/operator-framework/operator-sdk/releases/latest/download/operator-sdk_linux_amd64
chmod +x operator-sdk && mv operator-sdk /usr/local/bin/
operator-sdk version

# macOS
brew install operator-sdk

# 锁版本
export OPERATOR_SDK_VERSION=v1.36.0
curl -L -o operator-sdk \
  https://github.com/operator-framework/operator-sdk/releases/download/${OPERATOR_SDK_VERSION}/operator-sdk_linux_amd64
```

#### 3.3.2 初始化项目

```bash
# Go plugin（最常用，等价于 kubebuilder init）
operator-sdk init \
  --domain example.com \
  --repo github.com/example/my-operator \
  --project-name my-operator \
  --plugins=go/v4

# Helm plugin（把 Helm chart 包成 Operator）
operator-sdk init \
  --plugins=helm \
  --helm-chart=./my-chart \
  --domain example.com

# Ansible plugin（Ansible playbook 包成 Operator）
operator-sdk init \
  --plugins=ansible \
  --ansible-collection-path=./ansible-operator
```

**三种 plugin 对比**：

| plugin | 写 reconcile 的方式 | 适用 |
| --- | --- | --- |
| `go/v4` | Go 代码（controller-runtime） | 复杂业务逻辑 |
| `helm` | Helm chart + values 映射到 spec | 已有 Helm chart，复用 |
| `ansible` | Ansible playbook | 运维团队熟悉 Ansible |

#### 3.3.3 创建 API + Controller

```bash
# Go plugin（与 kubebuilder create api 等价）
operator-sdk create api \
  --group database \
  --version v1 \
  --kind MySQLCluster \
  --resource \
  --controller
```

#### 3.3.4 创建 Webhook

```bash
operator-sdk create webhook \
  --group database --version v1 --kind MySQLCluster \
  --defaulting --programmatic-validation
```

#### 3.3.5 创建 bundle（⭐ Operator SDK 独有的能力）

```bash
# 生成 OLM bundle（CSV + CRD + 部署清单打包）
make bundle

# 输出在 bundle/ 目录
#   bundle/manifests/
#     my-operator.clusterserviceversion.yaml
#     database.example.com_mysqlclusters.yaml
#   bundle/metadata/
#     annotations.yaml
#   bundle.Dockerfile

# 用 opm / podman 构建 bundle 镜像
make bundle-build BUNDLE_IMG=registry.example.com/my-operator-bundle:v1.0.0
make bundle-push BUNDLE_IMG=registry.example.com/my-operator-bundle:v1.0.0

# 在本地跑 bundle（验证）
operator-sdk run bundle registry.example.com/my-operator-bundle:v1.0.0 \
  --namespace my-operator-system \
  --install-mode OwnNamespace

# 卸载
operator-sdk cleanup my-operator
```

#### 3.3.6 Scorecard（Operator SDK 独有）

对 bundle 做合规 + 功能测试：

```bash
operator-sdk scorecard \
  --bundle=registry.example.com/my-operator-bundle:v1.0.0 \
  --selector=core=example.com/v1,name=mysql-operator \
  --output=text
```

#### 3.3.7 完整生命周期

```bash
# 1. 初始化
operator-sdk init --domain example.com --repo github.com/example/foo --plugins=go/v4

# 2. 创建 CRD
operator-sdk create api --group app --version v1 --kind Foo --resource --controller

# 3. 写 Spec/Status + Reconcile
# （手动写 api/v1/foo_types.go + internal/controller/foo_controller.go）

# 4. 生成代码 + 测试
make manifests generate fmt vet
make test

# 5. 构建 Operator 镜像
make docker-build docker-push IMG=registry.example.com/foo:v1.0.0

# 6. 生成 OLM bundle（要发 OperatorHub 必走）
make bundle
make bundle-build bundle-push BUNDLE_IMG=registry.example.com/foo-bundle:v1.0.0

# 7. 部署
make deploy IMG=registry.example.com/foo:v1.0.0
# 或在 OperatorHub 上传 bundle 后通过 catalog 安装

# 8. 验证
operator-sdk scorecard --bundle=...
```

#### 3.3.8 Operator SDK 独有的工具命令

| 命令 | 干啥 | |
| --- | --- | --- |
| `operator-sdk bundle` | 把现有部署清单打包成 OLM bundle | |
| `operator-sdk run bundle` | 本地装 bundle（替代 `make deploy`） | |
| `operator-sdk cleanup` | 卸载 bundle 部署的 Operator | |
| `operator-sdk scorecard` | bundle 合规 + e2e 测试 | |
| `operator-sdk generate` | 同 `kubebuilder create api` 的封装 | |
| `operator-sdk print-verbs` | 列出 Operator 用到的 K8s API 资源 | |
| `operator-sdk new-project` | 快速模板（含 git init、README 等） | |

---

### 3.4 选 Kubebuilder 还是 Operator SDK？

**两个核心问题**：

```text
Q1: 要发到 OperatorHub 吗？
    ├─ 是 → Operator SDK（生成 bundle/CSV）
    └─ 否 → Kubebuilder（足够）

Q2: 要用 Helm chart 或 Ansible 写 reconcile 吗？
    ├─ 是 → Operator SDK（helm / ansible plugin）
    └─ 否 → 都可以，Kubebuilder 更轻
```

**最常见的选择**：

```text
┌─────────────────────────────────────────────────────────────┐
│ 内部 Operator / 自研 CRD + GitOps 部署                       │
│     → 用 Kubebuilder（仅 Go）                               │
│                                                              │
│ 内部 Operator，但要打包给别人用 / 要走 OperatorHub            │
│     → 用 Operator SDK（生成 bundle）                         │
│                                                              │
│ 已有 Helm chart，想快速包装                                  │
│     → 用 Operator SDK + helm plugin                          │
└─────────────────────────────────────────────────────────────┘
```

> **底层代码 100% 一样**——生成的 controller-runtime 代码、CRD yaml、Makefile 全都通用。
> 切换工具不需要重写代码，只是不再生成 Operator SDK 特有的辅助文件。

#### 3.4.1 关键事实

- **Operator SDK 1.30+ 已经把脚手架部分全面外包给 Kubebuilder**——`operator-sdk init` 在底层调用 `kubebuilder init`
- **生成的 Go 代码、controller-runtime 依赖、Makefile 完全一致**
- **Operator SDK 唯一独有的**：bundle / CSV / scorecard / run --bundle
- **Kubebuilder 唯一独有的**：更轻的 CLI、`edit --multigroup` 用得更顺手

#### 3.4.2 推荐生产实践

1. **先用 Kubebuilder 起项目**，脚手架阶段保持简单
2. **要发布给外部用户**时再 `make bundle`（bundle 生成不需要 Operator SDK CLI，`make bundle` 用 kustomize + sed 拼 CSV）
3. **要在 OperatorHub 上架**才需要 Operator SDK CLI 做 scorecard + catalog 提交
4. **Ansible / Helm plugin** 只在已有 chart/ playbook 时用

---

## 四、Operator 开发完整流程

### 4.1 定义 CRD（types.go）

```go
// api/v1/mysqlcluster_types.go
package v1

import (
    "time"
    metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

// MySQLCluster 是 MySQL Cluster 资源的 Schema
type MySQLCluster struct {
    metav1.TypeMeta   `json:",inline"`
    metav1.ObjectMeta `json:"metadata,omitempty"`

    Spec   MySQLClusterSpec   `json:"spec,omitempty"`
    Status MySQLClusterStatus `json:"status,omitempty"`
}

// MySQLClusterSpec 定义期望状态
type MySQLClusterSpec struct {
    // 版本（必填）
    Version string `json:"version"`

    // 副本数（默认 3）
    Replicas *int32 `json:"replicas,omitempty"`

    // 存储配置（必填）
    Storage StorageSpec `json:"storage"`

    // 资源限制
    Resources ResourceRequirements `json:"resources,omitempty"`

    // 配置参数
    Config *MySQLConfig `json:"config,omitempty"`

    // 主从配置
    Replication *ReplicationConfig `json:"replication,omitempty"`

    // 备份策略
    Backup *BackupConfig `json:"backup,omitempty"`
}

// StorageSpec 存储配置
type StorageSpec struct {
    Size         string `json:"size"`
    StorageClass string `json:"storageClass,omitempty"`
}

// MySQLConfig MySQL 配置
type MySQLConfig struct {
    InnoDBBufferPoolSize string            `json:"innodbBufferPoolSize,omitempty"`
    MaxConnections       int32             `json:"maxConnections,omitempty"`
    SlowQueryLog         bool              `json:"slowQueryLog,omitempty"`
    CharacterSet         string            `json:"characterSet,omitempty"`
}

// ReplicationConfig 主从配置
type ReplicationConfig struct {
    Mode              string `json:"mode"`              // GTID/ROW
    SemiSync          bool   `json:"semiSync"`
    BackupTimeoutSec  int32  `json:"backupTimeoutSec,omitempty"`
}

// BackupConfig 备份配置
type BackupConfig struct {
    Enabled   bool          `json:"enabled"`
    Schedule  string        `json:"schedule,omitempty"`  // cron
    Retention string        `json:"retention,omitempty"`  // 7d
    Method    string        `json:"method,omitempty"`   // xtrabackup/mysqldump
}

// MySQLClusterStatus 定义实际状态
type MySQLClusterStatus struct {
    // 阶段：Pending/Creating/Running/Failed/Upgrading
    Phase string `json:"phase,omitempty"`

    // 已就绪副本数
    ReadyReplicas int32 `json:"readyReplicas"`

    // 服务入口
    Endpoints []Endpoint `json:"endpoints,omitempty"`

    // 当前主节点
    PrimaryPod string `json:"primaryPod,omitempty"`

    // 副本节点
    ReplicaPods []string `json:"replicaPods,omitempty"`

    // 备份状态
    LastBackup string `json:"lastBackup,omitempty"`

    // 观察到的 generation
    ObservedGeneration int64 `json:"observedGeneration,omitempty"`

    // 条件
    Conditions []metav1.Condition `json:"conditions,omitempty"`
}

type Endpoint struct {
    Name  string `json:"name"`
    Host string `json:"host"`
    Port int32  `json:"port"`
}

// +kubebuilder:object:root=true
// +kubebuilder:subresource:status
// +kubebuilder:subresource:scale:specReplicas=.spec.replicas,statusReplicas=.status.readyReplicas
// +kubebuilder:printcolumn:name="Version",type=string,JSONPath=`.spec.version`
// +kubebuilder:printcolumn:name="Replicas",type=integer,JSONPath=`.spec.replicas`
// +kubebuilder:printcolumn:name="Ready",type=integer,JSONPath=`.status.readyReplicas`
// +kubebuilder:printcolumn:name="Phase",type=string,JSONPath=`.status.phase`
// +kubebuilder:printcolumn:name="Age",type=date,JSONPath=`.metadata.creationTimestamp`
type MySQLCluster struct {
    metav1.TypeMeta   `json:",inline"`
    metav1.ObjectMeta `json:"metadata,omitempty"`

    Spec   MySQLClusterSpec   `json:"spec,omitempty"`
    Status MySQLClusterStatus `json:"status,omitempty"`
}

// +kubebuilder:object:root=true
type MySQLClusterList struct {
    metav1.TypeMeta `json:",inline"`
    metav1.ListMeta `json:"metadata,omitempty"`
    Items           []MySQLCluster `json:"items"`
}

func init() {
    SchemeBuilder.Register(&MySQLCluster{}, &MySQLClusterList{})
}
```

### 4.2 CRD 生成（Webhook）

```go
// api/v1/mysqlcluster_webhook.go
package v1

import (
    "fmt"

    "k8s.io/apimachinery/pkg/runtime"
    ctrl "sigs.k8s.io/controller-runtime"
    logf "sigs.k8s.io/controller-runtime/pkg/log"
    "sigs.k8s.io/controller-runtime/pkg/webhook"
    "sigs.k8s.io/controller-runtime/pkg/webhook/admission"

    apierrors "k8s.io/apimachinery/pkg/api/errors"
)

func (r *MySQLCluster) SetupWebhookWithManager(mgr ctrl.Manager) error {
    return ctrl.NewWebhookManagedBy(mgr).
        For(r).
        Complete()
}

// +kubebuilder:webhook:path=/mutate-database-example-com-v1-mysqlcluster,mutating=true,failurePolicy=fail,sideEffects=None,groups=database.example.com,resources=mysqlclusters,verbs=create;update,versions=v1,name=mmysqlcluster.kb.io,admissionReviewVersions=v1

var _ webhook.Validator = &MySQLClusterCustomValidator{}

// MySQLClusterCustomValidator 验证 webhook
type MySQLClusterCustomValidator struct{}

func (webhook *MySQLClusterCustomValidator) ValidateCreate(ctx context.Context, obj *MySQLCluster) (admission.Warnings, error) {
    return validate(obj)
}

func (webhook *MySQLClusterCustomValidator) ValidateUpdate(ctx context.Context, oldObj, newObj *MySQLCluster) (admission.Warnings, error) {
    return validate(newObj)
}

func validate(mc *MySQLCluster) (admission.Warnings, error) {
    var warnings admission.Warnings

    // 校验：副本数
    if mc.Spec.Replicas != nil {
        if *mc.Spec.Replicas < 1 {
            return warnings, apierrors.NewBadRequest(
                fmt.Sprintf("replicas must be >= 1, got %d", *mc.Spec.Replicas))
        }
        if *mc.Spec.Replicas > 10 {
            return warnings, apierrors.NewBadRequest(
                "replicas must be <= 10")
        }
    }

    // 校验：版本
    validVersions := map[string]bool{"5.7": true, "8.0": true}
    if !validVersions[mc.Spec.Version] {
        return warnings, apierrors.NewBadRequest(
            fmt.Sprintf("version must be 5.7 or 8.0, got %s", mc.Spec.Version))
    }

    return warnings, nil
}
```

### 4.3 Controller 主逻辑

```go
// internal/controller/mysqlcluster_controller.go
package controller

import (
    "context"
    "fmt"
    "time"

    appsv1 "k8s.io/api/apps/v1"
    corev1 "k8s.io/api/core/v1"
    "k8s.io/apimachinery/pkg/api/errors"
    "k8s.io/apimachinery/pkg/api/resource"
    metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
    "k8s.io/apimachinery/pkg/runtime"
    "k8s.io/apimachinery/pkg/types"
    ctrl "sigs.k8s.io/controller-runtime"
    "sigs.k8s.io/controller-runtime/pkg/client"
    "sigs.k8s.io/controller-runtime/pkg/controller/controllerutil"
    "sigs.k8s.io/controller-runtime/pkg/log"

    mysqlv1 "github.com/example/my-operator/api/v1"
)

const (
    finalizerName    = "mysql.example.com/finalizer"
    requeueAfterDelay = 30 * time.Second
)

type MySQLClusterReconciler struct {
    client.Client
    Scheme *runtime.Scheme
}

// +kubebuilder:rbac:groups=database.example.com,resources=mysqlclusters,verbs=get;list;watch;create;update;patch;delete
// +kubebuilder:rbac:groups=database.example.com,resources=mysqlclusters/status,verbs=get;update;patch
// +kubebuilder:rbac:groups=database.example.com,resources=mysqlclusters/finalizers,verbs=update
// +kubebuilder:rbac:groups=apps,resources=statefulsets,verbs=get;list;watch;create;update;patch;delete
// +kubebuilder:rbac:groups=core,resources=services,verbs=get;list;watch;create;update;patch;delete
// +kubebuilder:rbac:groups=core,resources=configmaps,verbs=get;list;watch;create;update;patch;delete
// +kubebuilder:rbac:groups=core,resources=secrets,verbs=get;list;watch;create;update;patch;delete
// +kubebuilder:rbac:groups=core,resources=pods,verbs=get;list;watch
// +kubebuilder:rbac:groups=core,resources=services,verbs=get;list;watch;create;update;patch;delete

func (r *MySQLClusterReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
    log := log.FromContext(ctx).WithValues("mysqlcluster", req.NamespacedName)

    // 1. 获取 CR
    mc := &mysqlv1.MySQLCluster{}
    if err := r.Get(ctx, req.NamespacedName, mc); err != nil {
        return ctrl.Result{}, client.IgnoreNotFound(err)
    }

    // 2. 处理删除
    if !mc.DeletionTimestamp.IsZero() {
        return r.reconcileDelete(ctx, mc)
    }

    // 3. 添加 Finalizer
    if !controllerutil.ContainsFinalizer(mc, finalizerName) {
        controllerutil.AddFinalizer(mc, finalizerName)
        return ctrl.Result{}, r.Update(ctx, mc)
    }

    // 4. 业务 reconcile 逻辑
    return r.reconcileNormal(ctx, mc, log)
}

func (r *MySQLClusterReconciler) reconcileNormal(
    ctx context.Context, mc *mysqlv1.MySQLCluster, log logr.Logger,
) (ctrl.Result, error) {

    // 1. 创建/更新 StatefulSet
    if err := r.reconcileStatefulSet(ctx, mc); err != nil {
        return ctrl.Result{}, err
    }

    // 2. 创建/更新 Service
    if err := r.reconcileService(ctx, mc); err != nil {
        return ctrl.Result{}, err
    }

    // 3. 创建/更新 ConfigMap
    if err := r.reconcileConfigMap(ctx, mc); err != nil {
        return ctrl.Result{}, err
    }

    // 4. 创建/更新 Secret
    if err := r.reconcileSecret(ctx, mc); err != nil {
        return ctrl.Result{}, err
    }

    // 5. 更新 status
    if err := r.updateStatus(ctx, mc); err != nil {
        return ctrl.Result{}, err
    }

    // 6. 定期 reconcile
    return ctrl.Result{RequeueAfter: requeueAfterDelay}, nil
}

func (r *MySQLClusterReconciler) reconcileStatefulSet(
    ctx context.Context, mc *mysqlv1.MySQLCluster,
) error {
    sts := &appsv1.StatefulSet{
        ObjectMeta: metav1.ObjectMeta{
            Name:      mc.Name,
            Namespace: mc.Namespace,
        },
        Spec: appsv1.StatefulSetSpec{
            Replicas: mc.Spec.Replicas,
            Selector: &metav1.LabelSelector{
                MatchLabels: r.labelsForMySQLCluster(mc.Name),
            },
            Template: corev1.PodTemplateSpec{
                ObjectMeta: metav1.ObjectMeta{
                    Labels: r.labelsForMySQLCluster(mc.Name),
                },
                Spec: corev1.PodSpec{
                    Containers: []corev1.Container{
                        {
                            Name:  "mysql",
                            Image: fmt.Sprintf("mysql:%s", mc.Spec.Version),
                            Ports: []corev1.ContainerPort{
                                {Name: "mysql", ContainerPort: 3306},
                            },
                            Env: []corev1.EnvVar{
                                {Name: "MYSQL_ROOT_PASSWORD",
                                    ValueFrom: &corev1.EnvVarSource{
                                        SecretKeyRef: &corev1.SecretKeySelector{
                                            LocalObjectReference: corev1.LocalObjectReference{Name: mc.Name + "-secret"},
                                            Key: "password",
                                        },
                                    },
                                },
                            },
                            Resources: r.resourceRequirements(mc),
                            VolumeMounts: r.volumeMounts(mc),
                        },
                    },
                },
            },
            VolumeClaimTemplates: r.volumeClaimTemplates(mc),
        },
    }

    // 应用 owner reference
    if err := controllerutil.SetControllerReference(mc, sts, r.Scheme); err != nil {
        return err
    }

    // 创建或更新
    found := &appsv1.StatefulSet{}
    err := r.Get(ctx, types.NamespacedName{Name: sts.Name, Namespace: sts.Namespace}, found)
    if err != nil && errors.IsNotFound(err) {
        return r.Create(ctx, sts)
    } else if err != nil {
        return err
    }
    found.Spec = sts.Spec
    return r.Update(ctx, found)
}

// 其他 reconcile 方法（reconcileService、reconcileConfigMap 等）类似
// 省略...

func (r *MySQLClusterReconciler) reconcileDelete(
    ctx context.Context, mc *mysqlv1.MySQLCluster,
) (ctrl.Result, error) {
    if controllerutil.ContainsFinalizer(mc, finalizerName) {
        // 清理外部资源（如调用 API 删除数据库实例）
        if err := r.cleanupExternalResources(ctx, mc); err != nil {
            return ctrl.Result{}, err
        }
        // 移除 Finalizer
        controllerutil.RemoveFinalizer(mc, finalizerName)
        return ctrl.Result{}, r.Update(ctx, mc)
    }
    return ctrl.Result{}, nil
}

func (r *MySQLClusterReconciler) SetupWithManager(mgr ctrl.Manager) error {
    return ctrl.NewControllerManagedBy(mgr).
        For(&mysqlv1.MySQLCluster{}).
        WithOptions(controller.Options{
            MaxConcurrentReconciles: 3,
            RateLimiter: workqueue.NewItemExponentialFailureRateLimiter(
                5*time.Second, 60*time.Second),
        }).
        Owns(&appsv1.StatefulSet{}).
        Owns(&corev1.Service{}).
        Owns(&corev1.ConfigMap{}).
        Owns(&corev1.Secret{}).
        Complete(r)
}

// labelsForMySQLCluster 生成标准标签
func (r *MySQLClusterReconciler) labelsForMySQLCluster(name string) map[string]string {
    return map[string]string{
        "app":      "mysql",
        "cluster": name,
    }
}
```

### 4.4 main.go 入口

```go
// cmd/main.go
package main

import (
    "flag"
    "os"

    "k8s.io/apimachinery/pkg/runtime"
    utilruntime "k8s.io/apimachinery/pkg/util/runtime"
    clientgoscheme "k8s.io/client-go/kubernetes/scheme"
    ctrl "sigs.k8s.io/controller-runtime"
    "sigs.k8s.io/controller-runtime/pkg/cache"
    "sigs.k8s.io/controller-runtime/pkg/healthz"
    "sigs.k8s.io/controller-runtime/pkg/log/zap"
    "sigs.k8s.io/controller-runtime/pkg/metrics/server"
    "sigs.k8s.io/controller-runtime/pkg/webhook"

    databasev1 "github.com/example/my-operator/api/v1"
    "github.com/example/my-operator/internal/controller"
)

var (
    scheme   = runtime.NewScheme()
    setupLog = ctrl.Log.WithName("setup")
)

func init() {
    utilruntime.Must(clientgoscheme.AddToScheme(scheme))
    utilruntime.Must(databasev1.AddToScheme(scheme))
}

func main() {
    var metricsAddr         string
    var enableLeaderElection bool
    var probeAddr            string

    flag.StringVar(&metricsAddr, "metrics-bind-address", ":8080", "...")
    flag.StringVar(&probeAddr, "health-probe-bind-address", ":8081", "...")
    flag.BoolVar(&enableLeaderElection, "leader-elect", false, "...")

    opts := ctrl.Options{
        Scheme:                 scheme,
        Metrics:                metricsserver.Options{BindAddress: metricsAddr},
        HealthProbeBindAddress: probeAddr,
        LeaderElection:         enableLeaderElection,
        LeaderElectionID:       "my-operator-leader",
    }

    mgr, err := ctrl.NewManager(ctrl.GetConfigOrDie(), opts)
    if err != nil {
        setupLog.Error(err, "unable to start manager")
        os.Exit(1)
    }

    if err = (&controller.MySQLClusterReconciler{
        Client: mgr.GetClient(),
        Scheme: mgr.GetScheme(),
    }).SetupWithManager(mgr); err != nil {
        setupLog.Error(err, "unable to create controller")
        os.Exit(1)
    }

    if err = (&databasev1.MySQLCluster{}).SetupWebhookWithManager(mgr); err != nil {
        setupLog.Error(err, "unable to create webhook")
        os.Exit(1)
    }

    if err := mgr.AddHealthzCheck("healthz", healthz.Ping); err != nil {
        setupLog.Error(err, "unable to set up health check")
        os.Exit(1)
    }
    if err := mgr.AddReadyzCheck("readyz", healthz.Ping); err != nil {
        setupLog.Error(err, "unable to set up ready check")
        os.Exit(1)
    }

    setupLog.Info("starting manager")
    if err := mgr.Start(ctrl.SetupSignalHandler()); err != nil {
        setupLog.Error(err, "problem running manager")
        os.Exit(1)
    }
}
```

---

## 五、Operator 部署与运维

### 5.1 构建镜像

```bash
# 1. 生成 CRD/部署清单
make manifests

# 2. 构建镜像
make docker-build IMG=registry.example.com/my-operator:v1.0.0

# 3. 推送镜像
make docker-push IMG=registry.example.com/my-operator:v1.0.0

# 4. 部署
make deploy IMG=registry.example.com/my-operator:v1.0.0
```

### 5.2 生成的部署清单

```yaml
# config/manager/manager.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: controller-manager
  namespace: system
  labels:
    app.kubernetes.io/name: my-operator
    app.kubernetes.io/managed-by: kustomize
spec:
  replicas: 1
  selector:
    matchLabels:
      control-plane: controller-manager
  template:
    metadata:
      labels:
        control-plane: controller-manager
    spec:
      containers:
      - args:
        - --secure-metrics-server
        - --health-probe-bind-address=:8081
        - --metrics-bind-address=:8080
        - --leader-elect
        command:
        - /manager
        image: registry.example.com/my-operator:v1.0.0
        env:
        - name: POD_NAMESPACE
          valueFrom:
            fieldRef:
              fieldPath: metadata.namespace
        livenessProbe:
          httpGet:
            path: /healthz
            port: 8081
        readinessProbe:
          httpGet:
            path: /readyz
            port: 8081
        resources:
          limits:
            cpu: 500m
            memory: 256Mi
          requests:
            cpu: 100m
            memory: 64Mi
      serviceAccountName: controller-manager
      terminationGracePeriodSeconds: 10
```

### 5.3 CRD 安装

```bash
# 安装 CRD
make install
# 等价于：
kubectl apply -f config/crd/bases/database.example.com_mysqlclusters.yaml
```

### 5.4 创建自定义资源

```bash
# 创建示例 CR
cat <<EOF | kubectl apply -f -
apiVersion: database.example.com/v1
kind: MySQLCluster
metadata:
  name: my-production-db
  namespace: production
spec:
  version: "8.0"
  replicas: 3
  storage:
    size: 100Gi
    storageClass: ssd
  resources:
    cpu: "2"
    memory: 8Gi
  config:
    innodbBufferPoolSize: 4G
    maxConnections: 1000
  replication:
    mode: GTID
    semiSync: true
EOF

# 查看状态
kubectl get mysqlcluster
# NAME              VERSION   REPLICAS   READY   PHASE     AGE
# my-production-db  8.0       3          3       Running   5m

kubectl describe mysqlcluster my-production-db
```

---

## 六、Operator 高级特性

### 6.1 Webhook

```go
// 默认 webhook（注入默认值）
func (r *MySQLCluster) Default() {
    if r.Spec.Replicas == nil {
        r.Spec.Replicas = new(int32)
        *r.Spec.Replicas = 3
    }
    if r.Spec.Storage.StorageClass == "" {
        r.Spec.Storage.StorageClass = "standard"
    }
}

// 验证 webhook（见前面代码）

// 转换 webhook（多版本）
func (r *MySQLCluster) ConvertTo(dst runtime.Object) error {
    switch dst.(type) {
    case *MySQLClusterv1beta1:
        // 从 v1 转换为 v1beta1
    case *MySQLCluster:
        // 同版本
    }
    return nil
}
```

### 6.2 Leader Election

```go
// 多副本 Operator 需要 Leader Election
opts := ctrl.Options{
    LeaderElection:          true,
    LeaderElectionID:        "my-operator-leader",
    LeaderElectionNamespace: "my-operator-system",
}

// 只有 Leader 才会执行 reconcile
// 其他副本在等待
```

### 6.3 高级 Reconcile 模式

```go
// Reconcile 时只关心自己拥有的资源
func (r *MySQLClusterReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
    mc := &mysqlv1.MySQLCluster{}
    if err := r.Get(ctx, req.NamespacedName, mc); err != nil {
        return ctrl.Result{}, client.IgnoreNotFound(err)
    }

    // 设置 owner reference（关键！）
    // 这样当 CR 删除时，所有者属资源会自动删除
    if err := controllerutil.SetControllerReference(mc, mc, r.Scheme); err != nil {
        return ctrl.Result{}, err
    }

    // 调谐各子资源
    return r.reconcile(ctx, mc)
}

// 使用 Owns() 自动 watch
func (r *MySQLClusterReconciler) SetupWithManager(mgr ctrl.Manager) error {
    return ctrl.NewControllerManagedBy(mgr).
        For(&mysqlv1.MySQLCluster{}).  // watch 主资源
        Owns(&appsv1.StatefulSet{}).     // 自动 watch 拥有者
        Owns(&corev1.Service{}).
        Complete(r)
}
```

### 6.4 优雅处理删除

```go
func (r *MySQLClusterReconciler) reconcileDelete(
    ctx context.Context, mc *mysqlv1.MySQLCluster,
) (ctrl.Result, error) {
    if !controllerutil.ContainsFinalizer(mc, finalizerName) {
        return ctrl.Result{}, nil
    }

    // 执行清理逻辑
    if err := r.cleanupExternalResources(ctx, mc); err != nil {
        return ctrl.Result{Requeue: true}, err
    }

    // 移除 Finalizer（必须在最后）
    controllerutil.RemoveFinalizer(mc, finalizerName)
    return ctrl.Result{}, r.Update(ctx, mc)
}
```

### 6.5 高级 Status 管理

```go
func (r *MySQLClusterReconciler) updateStatus(
    ctx context.Context, mc *mysqlv1.MySQLCluster,
) error {
    // 获取实际状态
    sts := &appsv1.StatefulSet{}
    err := r.Get(ctx, types.NamespacedName{
        Name:      mc.Name,
        Namespace: mc.Namespace,
    }, sts)
    if err != nil {
        return err
    }

    // 计算就绪副本数
    readyReplicas := sts.Status.ReadyReplicas

    // 设置 Phase
    if readyReplicas == *mc.Spec.Replicas {
        mc.Status.Phase = "Running"
    } else if readyReplicas > 0 {
        mc.Status.Phase = "Creating"
    } else {
        mc.Status.Phase = "Pending"
    }

    // 设置 Conditions
    mc.Status.Conditions = []metav1.Condition{
        {
            Type:               "Ready",
            Status:             metav1.ConditionTrue,
            LastTransitionTime: metav1.Now(),
            Reason:             "AllPodsReady",
            Message:            fmt.Sprintf("%d/%d pods ready", readyReplicas, *mc.Spec.Replicas),
        },
    }

    mc.Status.ReadyReplicas = readyReplicas
    mc.Status.ObservedGeneration = mc.Generation

    return r.Status().Update(ctx, mc)
}
```

---

## 七、实战案例

### 7.1 Redis Cluster Operator

```go
// RedisCluster API
type RedisClusterSpec struct {
    Replicas     int32  `json:"replicas"`        // 6, 9, 12...
    ClusterMode string `json:"clusterMode"`    // cluster/sentinel
    Resources    ResourceRequirements `json:"resources"`
    
    // Redis 配置
    RedisVersion string `json:"redisVersion"`  // 7.2, 7.0...
    MaxMemory    string `json:"maxMemory"`     // 1Gi, 4Gi
    
    // 集群配置
    Persistence *PersistenceConfig `json:"persistence,omitempty"`
    Sentinel    *SentinelConfig   `json:"sentinel,omitempty"`
}

// Controller 主要逻辑
// 1. 创建 Redis StatefulSet
// 2. 等待 Pod Ready
// 3. 执行 redis-cli --cluster create
// 4. 更新 status
```

### 7.2 Kafka Cluster Operator

```go
// KafkaCluster API
type KafkaClusterSpec struct {
    Brokers      int32  `json:"brokers"`         // 3, 5, 7...
    KafkaVersion string `json:"kafkaVersion"`   // 3.6
    Storage       StorageSpec `json:"storage"`
    
    // 关键配置
    Controller   *KafkaController `json:"controller,omitempty"`  // KRaft/ZK
    Listeners    *ListenersConfig `json:"listeners,omitempty"`
    Security     *SecurityConfig  `json:"security,omitempty"`
    
    // 高级特性
    MirrorMaker  *MirrorConfig `json:"mirrorMaker,omitempty"`
    TieredStorage *TieredStorageConfig `json:"tieredStorage,omitempty"`
}
```

### 7.3 Elasticsearch Operator

```go
// ElasticsearchCluster API
type ElasticsearchClusterSpec struct {
    Version  string `json:"version"`         // 8.x
    Nodes    []NodeSpec `json:"nodes"`        // master/data/ingest/coordinating
    
    // 每种节点角色单独配置
    Node NodeSpec `json:",inline"`
}

type NodeSpec struct {
    Replicas  int32             `json:"replicas"`
    Roles     []string          `json:"roles"`     // master, data, ingest
    Resources ResourceRequirements `json:"resources"`
    Storage   StorageSpec       `json:"storage"`
    NodeSelector map[string]string `json:"nodeSelector,omitempty"`
}
```

---

## 八、Operator 测试与调试

### 8.1 单元测试

```go
var _ = Describe("MySQLCluster Controller", func() {
    Context("When creating a new MySQLCluster", func() {
        It("Should create a StatefulSet", func() {
            By("Creating a new MySQLCluster")
            mc := &MySQLCluster{
                ObjectMeta: metav1.ObjectMeta{
                    Name:      "test-mysql",
                    Namespace: "default",
                },
                Spec: MySQLClusterSpec{
                    Version:  "8.0",
                    Replicas: ptr.To[int32](3),
                    Storage: StorageSpec{Size: "10Gi"},
                },
            }
            Expect(k8sClient.Create(ctx, mc)).Should(Succeed())

            By("Reconciling")
            controllerReconciler.Reconcile(ctx, reconcileRequest(mc))

            By("Checking the StatefulSet is created")
            sts := &appsv1.StatefulSet{}
            Eventually(func() error {
                return k8sClient.Get(ctx, types.NamespacedName{
                    Name: "test-mysql", Namespace: "default",
                }, sts)
            }).Should(Succeed())

            Expect(*sts.Spec.Replicas).Should(Equal(int32(3)))
        })
    })
})
```

### 8.2 本地调试

```bash
# 使用 envtest（推荐）
make test

# 或本地运行 Operator（连接真实集群）
make run
# INFO  starting manager
# INFO  MySQLCluster reconciled successfully

# 触发 reconcile
kubectl annotate mysqlcluster my-db force-reconcile=$(date +%s)
```

### 8.3 调试技巧

```bash
# 1. 查看 Operator 日志
kubectl logs -n my-operator-system deploy/my-operator-controller-manager -f

# 2. 查看 Operator 状态
kubectl get mysqlcluster -A
kubectl describe mysqlcluster my-db

# 3. 查看事件
kubectl get events --sort-by='.lastTimestamp' -A

# 4. 增加日志详细度
# 编辑 main.go：
#   opts := ctrl.Options{...}
#   ctrl.SetLogger(zap.New(zap.UseDevMode(true)))
make run

# 5. 远程调试 Operator
# 编辑 Makefile：
#   run: go run ./cmd/main.go
# 用 Delve：
dlv debug ./cmd/main.go -- --kubeconfig=~/.kube/config
```

---

## 九、Operator 最佳实践

### 9.1 设计原则

```text
1. 单一职责
   - 一个 Operator 对应一种资源
   - 不要做"万能 Operator"

2. 声明式 API
   - spec 是期望，status 是实际
   - 避免命令式操作

3. 幂等性
   - 同一 CR 多次 reconcile 结果相同
   - 不依赖 Reconcile 次数

4. 优雅升级
   - CR schema 版本化
   - Conversion Webhook 处理兼容

5. 优雅降级
   - 外部依赖失败时保持 CR 状态
   - 记录事件，不要 panic
```

### 9.2 性能与稳定性

```text
1. 限制并发
   - MaxConcurrentReconciles: 3
   - 避免 Controller OOM

2. 限流与重试
   - ExponentialBackoff
   - 限制最大重试次数

3. Owner Reference
   - 所有子资源必须设 owner
   - CR 删除时自动清理

4. Finalizer
   - 清理外部资源
   - 必须能完成清理才能删除 CR

5. Status 幂等
   - 只有变化才更新
   - 避免大量空更新
```

### 9.3 生产级检查清单

```text
- [ ] CRD 声明 status subresource
- [ ] Finalizer 处理完整
- [ ] Owner reference 设置
- [ ] Reconcile 幂等
- [ ] 错误处理（requeue 策略）
- [ ] 限流（RateLimiter）
- [ ] 监控指标（Prometheus）
- [ ] 健康检查（/healthz, /readyz）
- [ ] Webhook 高可用（多副本 + leader election）
- [ ] 优雅降级
- [ ] 日志结构化
- [ ] 文档（API、CR 字段说明）
- [ ] 测试覆盖（unit + e2e）
```

---

## 十、参考资源

```text
- Operator SDK: https://sdk.operatorframework.io/
- Kubebuilder: https://book.kubebuilder.io/
- Controller Runtime: https://github.com/kubernetes-sigs/controller-runtime
- Operator Hub: https://operatorhub.io/
- Operator Framework: https://github.com/operator-framework
- awesome-operators: https://github.com/operator-framework/awesome-operators
- 核心示例: https://github.com/operator-framework/samples
- 实践指南: https://sdk.operatorframework.io/docs/best-practices/

## 速记卡

Operator = CRD + Controller + 运维知识
工具链：Kubebuilder + controller-runtime + Operator SDK
核心循环：Watch → Diff → Reconcile → Update Status
关键 API：Reconcile() + SetupWithManager()
关键模式：Owner Reference + Finalizer + Status Subresource
Owner Reference → 删除 CR 自动清理子资源
Finalizer → 处理外部资源清理
Status Subresource → 分离期望/实际状态
```

## 速记

- **Operator** = CRD + Controller + 运维知识
- **工具链**：Kubebuilder + controller-runtime + Operator SDK
- **核心循环**：Watch → Get → Diff → Reconcile → Update Status
- **关键 API**：Reconcile() + SetupWithManager()
- **关键模式**：
  - Owner Reference：CR 删除自动清理
  - Finalizer：清理外部资源
  - Status Subresource：分离 spec/status
  - Webhook：验证、默认值、转换

```bash
kubectl apply -f cr.yaml
# → Controller watch
# → Reconcile
# → K8s 资源创建
# → status 更新
```

---

## 十一、Kubebuilder 命令速查与端到端开发流程

> 把散落在各节的 `kubebuilder` / `make` 命令汇总到一处，按**实际开发顺序**串成一条流水线。
> 本节读完 = 拿到一个完整 Operator 的工程流程图。

### 11.1 Kubebuilder 子命令速查（`kubebuilder --help`）

| 子命令 | 干啥 | 关键 flag |
| --- | --- | --- |
| `init` | 初始化项目（生成 go.mod / Makefile / PROJECT） | `--domain`、`--repo`、`--project-name`、`--plugins=go/v4` |
| `create api` | 创建 CRD 类型 + Controller 骨架 | `--group`、`--version`、`--kind`、`--resource`、`--controller` |
| `create webhook` | 给已有 Kind 加 webhook | `--defaulting`、`--programmatic-validation`、`--conversion` |
| `create config` | 不常用，多用于 bundle/OLM | `--name`、`--namespace` |
| `edit` | 修改 PROJECT 配置（多 group / 多版本） | `--multigroup` |
| `alpha` | 实验性（生成 envtest 等） | — |

**完整骨架示例**（一次性生成多 CRD）：

```bash
# 1. 项目初始化（go/v4 plugin = controller-runtime 最新）
kubebuilder init \
  --domain example.com \
  --repo github.com/example/my-operator \
  --plugins=go/v4

# 2. 启用多 group（一个项目多个业务域）
kubebuilder edit --multigroup=true

# 3. 生成 API（resource=true 才有 status subresource；controller=true 才生成 controller 骨架）
kubebuilder create api \
  --group database \
  --version v1 \
  --kind MySQLCluster \
  --resource \
  --controller

# 4. 多个 CRD
kubebuilder create api --group cache --version v1 --kind Redis --resource --controller
kubebuilder create api --group queue --version v1 --kind Kafka --resource --controller

# 5. 加 webhook
kubebuilder create webhook \
  --group database --version v1 --kind MySQLCluster \
  --defaulting --programmatic-validation

# 6. 多版本时加 conversion webhook
kubebuilder create webhook \
  --group database --version v1beta1 --kind MySQLCluster \
  --conversion
```

---

### 11.2 Make 命令清单（kubebuilder 生成的标准 Makefile）

`init` 后项目自带 `make help` 看所有 target。**最常用的 12 个**：

| 命令 | 干啥 | 何时用 |
| --- | --- | --- |
| `make manifests` | **生成 CRD / RBAC / webhook 配置** | 改 `+kubebuilder:` 注解 后必跑 |
| `make generate` | 生成 `zz_generated_deepcopy.go`（CRD 类型深拷贝） | 改 Go 类型后必跑 |
| `make fmt vet` | go fmt + go vet | 提交前 |
| `make test` | **单元 / envtest 测试** | CI、本地验证 |
| `make build` | 编译成二进制 | — |
| `make docker-build` | 打镜像 | `IMG=xxx` tag` |
| `make docker-push` | 推镜像 | `IMG=xxx` |
| `make deploy` | **用 kustomize 部署 Operator 到集群** | `IMG=xxx`（同时改镜像 + apply） |
| `make undeploy` | 卸载 Operator（**CRD 不删**） | 回滚 |
| `make install` | **只装 CRD**（不部署 Operator） | 调试 CRD / 跑 e2e 前 |
| `make uninstall` | 删 CRD | 清环境（**会删 CRD 下的所有 CR 实例**） |
| `make run` | **本地运行 Operator**（连真实集群） | 开发期热调试 |

**核心流水线**（改完代码到上线的最短路径）：

```bash
# 编辑完代码
make manifests generate fmt vet
make test
make docker-build docker-push IMG=registry.example.com/my-operator:dev
make deploy IMG=registry.example.com/my-operator:dev
```

---

### 11.3 端到端开发流程（从零到生产）

```text
┌──────────────┐
│ 0. 准备环境   │  Go 1.21+ / Docker / kubectl / envtest
└──────┬───────┘
       ▼
┌──────────────┐
│ 1. 项目初始化   │  kubebuilder init
└──────┬───────┘
       ▼
┌──────────────┐
│ 2. 设计 API    │  api/v1/<kind>_types.go（Spec / Status / 注解）
└──────┬───────┘
       ▼
┌──────────────┐
│ 3. 生成代码    │  make manifests generate
└──────┬───────┘
       ▼
┌──────────────┐
│ 4. 写 Reconcile│  internal/controller/<kind>_controller.go
└──────┬───────┘
       ▼
┌──────────────┐
│ 5. 本地调试    │  make install && make run
└──────┬───────┘
       ▼
┌──────────────┐
│ 6. 加测试      │  *_test.go（envtest）+ suite_test.go
└──────┬───────┘
       ▼
┌──────────────┐
│ 7. 加 Webhook │  kubebuilder create webhook → 改 *_webhook.go
└──────┬───────┘
       ▼
┌──────────────┐
│ 8. 构建+部署   │  make docker-build/push / deploy
└──────┬───────┘
       ▼
┌──────────────┐
│ 9. 生产化       │  Leader Election / RBAC / Metrics / 监控 / OLM bundle
└──────────────┘
```

#### 阶段 0：环境准备

```bash
# Go
go version           # ≥ 1.21
# Kubebuilder（手动装）
curl -L -o kubebuilder https://go.kubebuilder.io/latest/linux/amd64
chmod +x kubebuilder && mv kubebuilder /usr/local/bin/

# envtest 依赖（make test 用）
# 自动下载 kubebuilder 的 etcd / kube-apiserver 二进制到 ~/.local/share/kubebuilder-envtest
export KUBEBUILDER_ASSETS="$(setup-envtest use 2.15.x -p path)"

# Operator SDK（可选，做 bundle/OLM 时才用）
curl -L -o operator-sdk \
  https://github.com/operator-framework/operator-sdk/releases/latest/download/operator-sdk_linux_amd64
chmod +x operator-sdk && mv operator-sdk /usr/local/bin/
```

#### 阶段 1：项目初始化

```bash
mkdir my-operator && cd my-operator
go mod init github.com/example/my-operator

kubebuilder init \
  --domain example.com \
  --repo github.com/example/my-operator \
  --plugins=go/v4 \
  --skip-go-version-check
```

生成的关键文件：`PROJECT`（项目元数据）、`Makefile`、`cmd/main.go`、`go.mod`。

#### 阶段 2：定义 API（types.go）

参见上文 **四、4.1** 的 MySQLCluster 示例。要点：

- Spec = 用户期望，Status = 实际状态（加 `+kubebuilder:subresource:status`）
- 必填不加 `omitempty`，可选字段用指针或 `omitempty`
- **核心注解**（写完后 `make manifests` 生成 CRD yaml）：

| 注解 | 作用 |
| --- | --- |
| `+kubebuilder:object:root=true` | 标记 Root 类型 |
| `+kubebuilder:subresource:status` | 启用 status 子资源（spec/status 独立更新） |
| `+kubebuilder:subresource:scale` | 启用 scale 子资源（让 `kubectl scale` 工作） |
| `+kubebuilder:printcolumn` | `kubectl get` 多列展示 |
| `+kubebuilder:validation:...` | OpenAPI v3 schema 校验（required / pattern / enum / Maximum…） |
| `+kubebuilder:default:=` | 字段默认值 |

```go
// 注解示例
type MySQLClusterSpec struct {
    // +kubebuilder:validation:Required
    // +kubebuilder:validation:Enum=5.7;8.0
    Version string `json:"version"`

    // +kubebuilder:default:=3
    // +kubebuilder:validation:Minimum=1
    // +kubebuilder:validation:Maximum=10
    Replicas *int32 `json:"replicas,omitempty"`
```

#### 阶段 3：生成代码

```bash
make manifests    # → config/crd/bases/*.yaml
make generate     # → api/v1/zz_generated_deepcopy.go
```

**`make manifests` 后**检查 `config/crd/bases/` 下的 CRD 文件，确认字段、validation、printcolumn 都对。

#### 阶段 4：写 Reconcile 逻辑

参见上文 **四、4.3** 的完整示例。骨架套路：

```go
func (r *MyKindReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
    // 1. Get CR（找不到就忽略）
    obj := &MyKind{}
    if err := r.Get(ctx, req.NamespacedName, obj); err != nil {
        return ctrl.Result{}, client.IgnoreNotFound(err)
    }

    // 2. 处理删除（finalizer）
    if !obj.DeletionTimestamp.IsZero() {
        return r.reconcileDelete(ctx, obj)
    }

    // 3. 加 finalizer（首次）
    if !controllerutil.ContainsFinalizer(obj, finalizerName) {
        controllerutil.AddFinalizer(obj, finalizerName)
        return ctrl.Result{}, r.Update(ctx, obj)
    }

    // 4. 调谐子资源（StatefulSet / Service / ConfigMap / Secret ...）
    //    每个子资源独立小函数，幂等（不存在就建，存在就 patch）
    //    SetControllerReference 设 owner
    if err := r.reconcileXxx(ctx, obj); err != nil {
        return ctrl.Result{}, err        // 失败会重试
    }

    // 5. 更新 status
    if err := r.updateStatus(ctx, obj); err != nil {
        return ctrl.Result{}, err
    }

    // 6. 定期 reconcile（兜底，事件驱动之外的同步）
    return ctrl.Result{RequeueAfter: 30 * time.Second}, nil
}
```

**SetupWithManager 的关键选项**：

```go
func (r *Reconciler) SetupWithManager(mgr ctrl.Manager) error {
    return ctrl.NewControllerManagedBy(mgr).
        For(&MyKind{}).                            // 主 CR
        Owns(&appsv1.StatefulSet{}).               // 自动 watch owner 资源
        Owns(&corev1.Service{}).
        WithOptions(controller.Options{
            MaxConcurrentReconciles: 5,            // 并发上限
            RateLimiter: workqueue.NewItemExponentialFailureRateLimiter(
                5*time.Millisecond, 1000*time.Second),  // 指数退避
            RecoverPanic: ptr.To(true),             // panic 自愈
        }).
        Complete(r)
}
```

#### 阶段 5：本地调试（最快反馈循环）

```bash
# 一次性：装 CRD 到目标集群
make install

# 起 Operator（连 ~/.kube/config 指向的集群，热加载代码）
make run

# 另开终端：apply 一个 CR 看效果
kubectl apply -f config/samples/database_v1_mysqlcluster.yaml

# 看日志（实时）
kubectl logs -n my-operator-system deploy/my-operator-controller-manager -f

# 强制重 reconcile（更新 annotation）
kubectl annotate mysqlcluster my-db force-reconcile=$(date +%s)

# 改完代码 → Ctrl-C → make run 重新起
```

#### 阶段 6：测试

```bash
# 跑全套（envtest 起真实 etcd + kube-apiserver）
make test

# 只跑某个测试
go test ./internal/controller/... -run TestMySQLCluster -v

# 覆盖率
go test ./... -coverprofile=cover.out
go tool cover -html=cover.out
```

#### 阶段 7：加 Webhook

```bash
kubebuilder create webhook \
  --group database --version v1 --kind MySQLCluster \
  --defaulting --programmatic-validation
# 生成 api/v1/mysqlcluster_webhook.go
```

**关键修改点**：

- `api/v1/<kind>_webhook.go` 里实现 `Default()` / `ValidateCreate()` / `ValidateUpdate()`
- `cmd/main.go` 里注册 webhook（`SetupWebhookWithManager`）
- **webhook 需要证书**：`make deploy` 自动签发；本地跑 `make run` 需要手动：

```bash
# 本地 webhook 证书（开发用）
make manifests
kustomize build config/default > /tmp/webhook.yaml
# 或用 cert-manager
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/latest/download/cert-manager.yaml
```

#### 阶段 8：构建 + 部署

```bash
# 一行流水线
make manifests generate fmt vet \
  && make docker-build docker-push IMG=registry.example.com/my-operator:v1.0.0 \
  && make deploy IMG=registry.example.com/my-operator:v1.0.0

# 验证部署
kubectl get pods -n my-operator-system
kubectl get crd | grep example.com
```

#### 阶段 9：生产化

```bash
# 1. 多副本 + Leader Election（已默认开）
#    config/manager/manager.yaml 里 replicas: 2 + --leader-elect

# 2. Metrics（默认 :8080 暴露）
kubectl port-forward -n my-operator-system svc/my-operator-controller-manager-metrics 8080:8080
curl http://localhost:8080/metrics | grep controller_runtime_reconcile_total

# 3. 加 ServiceMonitor（给 Prometheus Operator）
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: my-operator
  namespace: my-operator-system
spec:
  selector:
    matchLabels:
      control-plane: controller-manager
  endpoints:
    - port: metrics

# 4. 升级流程（每次发版）
make manifests  # CRD 改了要跑
make deploy IMG=...:v1.1.0
```

---

### 11.4 常见任务流（速查）

| 任务 | 操作 |
| --- | --- |
| 加一个字段 | 改 `types.go` → `make manifests generate` |
| 加一个 CRD | `kubebuilder create api --group ... --version v1 --kind Xxx --resource --controller` |
| 加 webhook | `kubebuilder create webhook --group ... --version v1 --kind Xxx --defaulting --programmatic-validation` |
| 加 RBAC 权限 | 在 controller 文件里加 `// +kubebuilder:rbac:groups=...,resources=...,verbs=...` → `make manifests` |
| 加业务监控指标 | 在 reconcile 里用 `ctrl.Log.WithValues()` + 暴露到 metrics endpoint |
| 加 finalizer | `controllerutil.AddFinalizer(obj, finalizerName)` + `reconcileDelete` |
| 多版本 CRD | `kubebuilder create api --version v1beta1 ...` + 写 conversion webhook |
| 升级 Operator 镜像 | 改 `Makefile` 的 `IMG` → `make docker-build docker-push deploy` |
| 清理本地集群的 CRD | `make uninstall`（**慎用，会删所有实例**） |
| 本地热加载改 Go 代码 | Ctrl-C + `make run`（controller-runtime 支持 manager 内重启某些组件，但多数情况需重启进程） |
| 看 Operator 内部 metric | `make run` 起后访问 `:8080/metrics` |
| 加 e2e 测试 | 在 `test/e2e/` 写 Kind 集群 + Ginkgo 用例；`make test-e2e` 跑 |

---

### 11.5 关键文件 / 目录对照表

| 路径 | 内容 | 谁改 |
| --- | --- | --- |
| `api/v1/<kind>_types.go` | CRD Spec / Status 定义 + 注解 | **人**（业务定义） |
| `api/v1/zz_generated_deepcopy.go` | 深拷贝函数 | **自动**（`make generate`） |
| `internal/controller/<kind>_controller.go` | Reconcile 主逻辑 | **人**（核心逻辑） |
| `internal/controller/suite_test.go` | envtest 入口 | **自动**（脚手架），人补用例 |
| `config/crd/bases/*.yaml` | CRD 定义 | **自动**（`make manifests`） |
| `config/rbac/role.yaml` | Operator 需要的 RBAC 权限 | **自动**（`make manifests`） |
| `config/manager/manager.yaml` | Operator Deployment | **自动** + 人改（镜像 tag、replicas） |
| `config/webhook/...` | Webhook 配置 | **自动** |
| `cmd/main.go` | 入口（注册 Scheme / Reconciler / Webhook） | **人**（按需补） |
| `Makefile` | 流水线 | **自动**（脚手架），人改 IMG 等变量 |
| `PROJECT` | Kubebuilder 项目元数据 | **自动**（被 `kubebuilder edit` 改） |
| `bundle/` | OLM bundle（生成 OperatorHub 订阅资源） | **自动**（`make bundle`） |

---

### 11.6 常见坑（命令相关）

| 现象 | 原因 / 解决 |
| --- | --- |
| `make manifests` 改了字段没生效 | 没装 controller-gen；或 `Makefile` 里 `CONTROLLER_TOOLS_VERSION` 太旧 |
| `make generate` 报 `cannot find type X` | 注解写错（`+kubebuilder:object:root=true` 漏了） |
| `make test` 失败：`kubebuilder-envtest` 找不到 | `export KUBEBUILDER_ASSETS=...` |
| `make deploy` 找不到镜像 | 仓库没登录：`docker login registry.example.com` |
| Webhook 不生效 | 证书问题；查 `kubectl get mutatingwebhookconfiguration` |
| 升级 CRD schema 后老 CR 不能改 | 加 conversion webhook；或老 CR 重写 |
| `make run` 跑不起来 | RBAC 缺；用 `make deploy` 部署后看日志 |
| Operator watch 不触发 | `Owns()` 漏了关联资源；或 owner reference 没设 |
| 改了 CR 字段名，apply 报错 | **字段名变更是 breaking change**——只能新版本 + conversion |
| Controller OOM | `MaxConcurrentReconciles` 太大；或 reconcile 内同步 IO 多 |
