# Argo CD

CNCF 毕业的 GitOps 控制台，把 Git 仓库作为应用期望状态的唯一来源，自动同步到 K8s 集群。与 Flux 并称 GitOps 双雄，但因 UI 完整、易上手，社区使用更广。

## 一、定位与特性

- GitOps 控制器：监控 Git 仓库，自动 sync 到 K8s
- 可视化 UI：应用拓扑、diff、sync 历史、回滚
- 多集群多租户：ApplicationSet + AppProject 支持跨集群模板化部署
- 配置渲染：Helm / Kustomize / Jsonnet 原生支持；CMP 扩展
- SSO + RBAC + 审计：完整企业级权限
- 通知：Notifications controller 接入 Slack / 钉钉 / Webhook

## 二、架构

```text
┌─────────────────────────────────────────────────────────────┐
│                  Argo CD (单 namespace: argocd)              │
│                                                             │
│  ┌────────────────┐  ┌────────────────┐  ┌───────────────┐  │
│  │   api-server   │  │  repo-server   │  │ application-  │  │
│  │  (gRPC + UI)   │  │  (Git 拉取+渲染)│  │  controller   │  │
│  └────────┬───────┘  └────────┬───────┘  └───────┬───────┘  │
│           │                  │                  │          │
│           ▼                  ▼                  ▼          │
│  ┌────────────────┐  ┌────────────────┐  ┌───────────────┐  │
│  │   dex (SSO)    │  │     redis      │  │  notifications│  │
│  │  (可选, SSO)   │  │  (缓存+缓存)    │  │  (可选)       │  │
│  └────────────────┘  └────────────────┘  └───────────────┘  │
│                                                             │
│  可选: ┌─────────────────┐  ┌────────────────────────┐        │
│        │ applicationset- │  │  image-updater         │        │
│        │ controller      │  │  (镜像自动更新)          │        │
│        └─────────────────┘  └────────────────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

- **api-server**：暴露 gRPC / REST / Web UI，与 repo-server / controller 通信
- **repo-server**：无状态组件，从 Git 拉取仓库，按 Helm/Kustomize/Jsonnet 渲染 manifest，缓存到 redis
- **application-controller**：核心 controller，对比 desired state 与 live state，触发 sync
- **redis**：缓存 manifest 渲染结果与集群列表
- **dex**：可选 SSO 集成（LDAP / SAML / OIDC）
- **applicationset-controller**：实现 ApplicationSet CRD，模板化多集群部署
- **notifications-controller**：订阅 Argo CD 事件，路由到 Slack / Webhook

## 三、核心 CRD

### 1. Application

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: my-app
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/org/repo.git
    targetRevision: HEAD
    path: overlays/prod
    helm:
      valueFiles:
        - values-prod.yaml
      parameters:
        - name: image.tag
          value: v1.2.3
  destination:
    server: https://kubernetes.default.svc
    namespace: my-app
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
      allowEmpty: false
    syncOptions:
      - CreateNamespace=true
      - PrunePropagationPolicy=foreground
      - PruneLast=true
    retry:
      limit: 5
      backoff:
        duration: 5s
        factor: 2
        maxDuration: 3m
```

### 2. AppProject（项目边界与 RBAC）

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: team-a
  namespace: argocd
spec:
  description: Team A applications
  sourceRepos:
    - https://github.com/org/team-a-*
    - git@github.com:org/team-a-private.git
  destinations:
    - namespace: 'team-a-*'
      server: https://kubernetes.default.svc
    - server: https://eks-prod.example.com
  clusterResourceWhitelist:
    - group: ""
      kind: Namespace
  namespaceResourceWhitelist:
    - group: ""
      kind: Deployment
    - group: ""
      kind: Service
    - group: ""
      kind: ConfigMap
  roles:
    - name: developer
      policies:
        - p, proj:team-a:developer, applications, get, team-a/*, allow
        - p, proj:team-a:developer, applications, sync, team-a/*, allow
      groups:
        - team-a-devs
```

### 3. ApplicationSet（多集群模板化）

```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: cluster-apps
  namespace: argocd
spec:
  generators:
    - list:
        elements:
          - cluster: dev
            url: https://dev.k8s.example.com
            valuesIndex: 0
          - cluster: prod
            url: https://prod.k8s.example.com
            valuesIndex: 1
    - clusters: {}                # 自动遍历所有 cluster secret
    - git:
        repoURL: https://github.com/org/gitops-repo.git
        revision: HEAD
        files:
          - path: clusters/*.yaml
  template:
    metadata:
      name: '{{cluster}}-guestbook'
    spec:
      project: default
      source:
        repoURL: https://github.com/org/repo.git
        targetRevision: HEAD
        path: guestbook/{{valuesIndex}}
      destination:
        server: '{{url}}'
        namespace: guestbook
```

| Generator | 用途 |
| --------- | ---- |
| **list** | 静态列表 |
| **clusters** | 遍历 argocd 中所有 cluster secret |
| **git** | 读取 Git 目录 / 文件生成 |
| **matrix** | 两个 generator 笛卡尔积 |
| **merge** | 合并多个 generator 输出 |
| **pullRequest** | 给 PR 自动创建 preview 环境 |

## 四、同步原理

### 1. 三方对比

```text
                Git Repository
                      │
                      │ repo-server 渲染
                      ▼
              desired state (manifest)
                      │
                      │              K8s cluster
                      │                   │
                      │                   │ kubectl get
                      ▼                   ▼
              last-applied            live state
              (annotation)
```

- **desired state**：来自 Git 仓库经渲染后的 manifest
- **live state**：当前集群实际状态（kubectl get）
- **last-applied**：上一次成功 sync 的内容，写在每个资源的 `kubectl.kubernetes.io/last-applied-configuration` annotation

对比逻辑：

1. 对比 desired vs live → diff 需要应用的部分
2. 对比 desired vs last-applied → diff 是否需要"回滚 / 撤销"外加修改
3. Sync 应用 = 把 desired 推到集群 + 更新 last-applied

### 2. Sync Waves（顺序控制）

```yaml
metadata:
  name: db
  annotations:
    argocd.argoproj.io/sync-wave: "0"     # 先部署
---
metadata:
  name: migration-job
  annotations:
    argocd.argoproj.io/sync-wave: "1"     # 再跑迁移
---
metadata:
  name: app
  annotations:
    argocd.argoproj.io/sync-wave: "2"     # 最后部署应用
```

- 数字越小越先 sync
- 同一 wave 内并行
- 用于：先 DB schema 再应用、CRD 先于 CR

### 3. Hooks（生命周期干预）

```yaml
metadata:
  name: db-migrate
  annotations:
    argocd.argoproj.io/hook: PreSync
    argocd.argoproj.io/hook-delete-policy: BeforeHookCreation
```

| Hook 类型 | 时机 | 用途 |
| --------- | ---- | ---- |
| PreSync | sync 开始前 | DB 迁移、CRD 安装 |
| Sync（默认） | 资源替换 | 部署 |
| PostSync | sync 完成后 | 通知、清理 |
| SyncFail | sync 失败 | 回滚 / 告警 |
| Skip | 不参与 sync | 临时手工资源 |

- Hook 可指定 delete policy：`BeforeHookCreation` / `HookSucceeded` / `HookFailed` / `Never`

### 4. 自动同步策略

```yaml
syncPolicy:
  automated:
    prune: true          # 删除 Git 中已移除的资源
    selfHeal: true       # 集群被改回去
    allowEmpty: false    # 防止 Git 空目录误删所有资源
```

- `selfHeal`：发现 live 与 desired 不一致（无论是不是 Argo CD 改的）就回滚
- `prune`：Git 删了就从集群删
- `applyOutOfSyncOnly`：只同步 out-of-sync 的资源（性能更好）

## 五、健康检查

### 1. 内置健康检查

Argo CD 内置了常见资源的健康检查规则：

- Deployment → 检查 `availableReplicas ≥ desiredReplicas`
- StatefulSet → 同上
- Service → 检查 Endpoints
- Ingress → 检查 status.loadBalancer
- PVC → 检查 Bound
- CRD → 由 CRD 自己定义（健康状态在 status.conditions）

### 2. 自定义 Lua health check

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-cm
  namespace: argocd
data:
  resource.customizations.health.argoproj.io_Application: |
    hs = {}
    if obj.status ~= nil then
      if obj.status.health ~= nil then
        hs.status = obj.status.health.status
        hs.message = obj.status.health.message
        return hs
      end
    end
    hs.status = "Progressing"
    hs.message = "Waiting for Application status"
    return hs
```

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-cm
  namespace: argocd
data:
  resource.customizations.health.<group>_<kind>: |
    -- Lua 脚本返回 { status = "Healthy"|"Progressing"|"Degraded", message = "..." }
```

## 六、多集群管理

### 1. 添加 cluster

```bash
argocd cluster add <context-name> \
  --name prod-cluster \
  --server https://prod.k8s.example.com \
  --in-cluster-context=false
```

实际是在 argocd namespace 创建 Secret：

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: prod-cluster
  namespace: argocd
  labels:
    argocd.argoproj.io/secret-type: cluster
type: Opaque
stringData:
  name: prod-cluster
  server: https://prod.k8s.example.com
  config: |
    {
      "bearerToken": "...",
      "tlsClientConfig": {
        "insecure": false,
        "caData": "..."
      }
    }
```

### 2. 跨集群部署

- `ApplicationSet` 用 `clusters` generator 遍历所有 cluster secret
- 适合多套环境（dev/stage/prod）、多 region

### 3. Hub-Spoke vs Multi-Hub

- **Hub-Spoke**：一个 Argo CD 控制面管理多个集群（最常见）
- **Multi-Hub**：每个集群独立 Argo CD，主 Argo CD 再管理子 Argo CD 的 ApplicationSet

## 七、配置管理插件（Configuration Management Plugins）

### 1. 内置支持

- Helm（v2/v3，含 OCI）
- Kustomize
- Jsonnet
- 自定义目录 / 文件

### 2. CMP（自定义）

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-cmp-cm
  namespace: argocd
data:
  plugin.yaml: |
    apiVersion: argoproj.io/v1alpha1
    kind: ConfigManagementPlugin
    metadata:
      name: my-plugin
    spec:
      version: v1.0
      generate:
        command: ["/bin/sh", "-c"]
        args: ["kustomize build overlays/$ARGOCD_ENV_APP_NAMESPACE"]
      discover:
        find:
          command: [sh, -c, echo "skipping discover"]
```

## 八、RBAC 与 SSO

### 1. SSO

- 内置 dex，支持 OIDC / SAML / LDAP / GitHub / GitLab / Microsoft / LinkedIn / Google
- 关闭 dex 直接对接外部 OIDC 也行（`oidc.config`）

### 2. policy.csv（细粒度）

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-rbac-cm
  namespace: argocd
data:
  policy.csv: |
    p, role:readonly, applications, get, */*, allow
    p, role:readonly, applications, list, */*, allow

    p, role:developer, applications, get, */*, allow
    p, role:developer, applications, sync, dev/*, allow

    p, role:admin, applications, *, */*, allow
    p, role:admin, clusters, *, *, allow
    p, role:admin, repositories, *, *, allow

    g, team-a-devs, role:developer
    g, team-a-admins, role:admin

    g, devops@company.com, role:admin
```

格式：`p, <role/sub>, <resource>, <action>, <project>/<object>, <effect>`

### 3. 项目级 RBAC（AppProject）

AppProject 内置 `roles`，更细的可叠加 `proj:<project>:<role>` 全局策略。

## 九、CLI 常用命令

```bash
# 登录
argocd login <argocd-server>

# 创建应用
argocd app create my-app \
  --repo https://github.com/org/repo.git \
  --path overlays/prod \
  --dest-server https://kubernetes.default.svc \
  --dest-namespace my-app \
  --helm-set image.tag=v1.2.3

# 手动同步
argocd app sync my-app

# 查看差异
argocd app diff my-app

# 查看历史与回滚
argocd app history my-app
argocd app rollback my-app

# 暂停 / 恢复自动同步
argocd app set my-app --self-heal=false
argocd app unset my-app --self-heal

# 看应用树
argocd app tree my-app

# 看 manifests
argocd app manifests my-app
```

## 十、Secrets 与镜像更新

### 1. Sealed Secret 配合

```yaml
# Git 仓库里只有 SealedSecret（加密）
apiVersion: bitnami.com/v1alpha1
kind: SealedSecret
metadata:
  name: db-cred
  namespace: my-app
spec:
  encryptedData:
    password: AgB...（密文）
  template:
    data:
      password: ""
```

- kubeseal 加密 → SealedSecret 提交到 Git → 集群内 sealed-secrets-controller 解密 → 生成原生 Secret
- Argo CD 只管 SealedSecret 是否进集群，不接触明文

### 2. SOPS 配合

- Mozilla SOPS + Kustomize 插件 / Helm secrets 插件
- Git 中是 `secret.enc.yaml` 加密文件
- Argo CD 通过 plugin sidecar 解密（需开启 SOPS sidecar）

### 3. Image Updater

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: my-app
  annotations:
    argocd-image-updater.argoproj.io/image-list: myapp=org/myapp:1.0
    argocd-image-updater.argoproj.io/myapp.update-strategy: latest
    argocd-image-updater.argoproj.io/write-back-method: git
spec:
  source:
    repoURL: https://github.com/org/repo.git
    targetRevision: HEAD
    path: overlays/prod
```

- 监控镜像仓库新 tag，写回 Git 仓库或更新 Application spec
- 完整工作流：Image Updater → Git commit → Argo CD sync

## 十一、与 Flux 对比

| 维度 | Argo CD | Flux |
| ---- | ------- | ---- |
| UI | 完整 Web UI | 仅 CLI / Web Dashboard（独立项目） |
| 架构 | 多组件（api/repo/controller） | 单二进制 operator + runner 拉取 |
| 多集群 | ApplicationSet 模板化 | HelmRelease / Kustomization 跨集群 |
| Helm | 原生支持 + values 覆盖 | 通过 HelmController |
| 学习曲线 | UI 友好，CLI 直观 | GitOps 理念更纯，配置即代码 |
| 通知 | Notifications controller | Notification Controller（同源） |
| Image 自动更新 | 独立项目 argocd-image-updater | 内置 image-automation |
| 适用 | 平台团队、需要 UI | GitOps 理念派、纯声明 |

> 选 Argo CD：UI、ApplicationSet 模板化、Helm values 灵活
> 选 Flux：纯 GitOps、Operator 一体化、与 Helm/Kustomize 单一来源

## 十二、优缺点

### 优点

- UI 完善，diff / 拓扑 / 历史 / 回滚所见即所得
- ApplicationSet 模板化部署非常强大
- RBAC / SSO / 审计企业级可用
- 多配置管理（Helm / Kustomize / Jsonnet / CMP）齐全
- CNCF 毕业项目，社区活跃

### 缺点

- 多组件（api/repo/controller/redis）运维复杂度
- 大规模集群（数百 Application）时 controller 内存需要调优
- ApplicationSet 模板调试信息不如 Helm chart 直观
- selfHeal 与某些运维临时操作冲突（如手动重启 Pod 立即被回滚）
- UI 一次性展示所有应用，大规模时筛选体验一般

适用：多 K8s 集群、GitOps 工作流、需要 UI 协作的 DevOps 团队。

## 十三、最佳实践

- **仓库结构**：一个 repo 一个环境（monorepo） 或 app-of-apps 模式
- **AppProject 必用**：每个团队一个 AppProject，限定 sourceRepos 与 destinations
- **Helm values**：用 `parameters` 注入环境差异，不要把 values 文件全推到 Git
- **sync wave 拆好**：CRD → CR → Job → Deployment → Service → Ingress
- **Hook 慎用**：PreSync/PostSync 失败会让 sync 状态卡住
- **prune 谨慎开启**：开前确认 webhook 不会误删生产资源
- **selfHeal 默认开**：与 webhook 配合确保集群始终收敛
- **资源保护**：`resource.exclusions` 排除某些资源，避免被 Argo CD 接管
- **Notifications**：接入 Slack / 钉钉，关键应用同步失败立刻告警
- **Secrets**：用 SealedSecret / SOPS，不要把明文推到 Git
- **镜像更新**：Image Updater 配合，CI 出 tag → 自动同步
- **备份 Argo CD**：Application CR 也存 Git，集群被重建可恢复
- **监控 Argo CD**：controller / repo-server 自身的 metrics 接 Prometheus