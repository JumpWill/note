# Kubernetes ConfigMap & Secret

K8s 原生配置方案，把配置/密钥以一等资源注入 Pod。所有非 K8s 接入的配置中心（Vault / Nacos / Apollo）最终都要落地到 ConfigMap / Secret，所以理解这层是构建 K8s 应用配置的根。

## 一、定位与特性

- **ConfigMap**：非敏感配置，明文 KV，base64 不加密
- **Secret**：敏感配置，value 自动 base64（**不等于加密**）
- 与 Pod / Deployment 同生命周期，etcd 持久化
- 可挂卷 / 注入环境变量 / 由 args 引用
- 配套机制：immutable、热更新、EnvFrom、Checksum 触发滚动
- 限制：单 Secret 1MB（etcd 限制），高敏感场景应走 Vault / KMS

## 二、架构与生命周期

```text
┌──────────────────────────────────────────────────────┐
│                  Kubernetes API Server                │
│       ┌──────────────┐    ┌──────────────┐            │
│       │ ConfigMap    │    │   Secret     │   资源 ──┐ │
│       └──────┬───────┘    └──────┬───────┘         │ │
│              └────────┬─────────┘                  │ │
│                       ▼                            │ │
│                    etcd（持久化）                   │ │
└────────────────────────┬───────────────────────────┘ │
                         ▼                              │
┌──────────────────────────────────────────────────────┐
│                    kubelet                             │
│   - 监听 ConfigMap / Secret 变更                       │
│   - 周期 60s 全量 sync + inotify 立即触发               │
│                  ↓                                     │
│   - env 注入：更新 Pod spec.revision 才生效，需重启      │
│   - volume 挂载：节点文件更新到 /var/lib/kubelet/pods/ │
│                   通过 symlink 暴露到容器                │
│                  ↓                                     │
│              容器内配置文件 (~1min 内更新)               │
└──────────────────────────────────────────────────────┘
```

```text
   ConfigMap/Secret 变更
           │
           ▼
   kubelet 周期 sync + inotify
           │
   ┌───────┴──────────┐
   ▼                  ▼
volume 挂载         env 注入
自动更新（容器内     不会更新
文件最终一致）      （进程读的是旧 env）
   ▼
   容器内文件 ~1min 一致
```

## 三、ConfigMap 三种消费方式

### 1. 环境变量

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: myapp
spec:
  containers:
  - name: app
    image: myapp:1.0
    env:
    - name: DB_HOST
      valueFrom:
        configMapKeyRef:
          name: myapp-config
          key: db.host
    - name: DB_PORT
      valueFrom:
        configMapKeyRef:
          name: myapp-config
          key: db.port
```

- **进程启动时读取 env，运行时改 env 不会生效**
- 必须重启 Pod
- 触发滚动更新的方式见第七节

### 2. envFrom（整批喂进去）

```yaml
envFrom:
- configMapRef:
    name: myapp-config
- configMapRef:
    name: myapp-config-extra
    optional: true  # 不存在也不报错
```

- 一次性把 ConfigMap 全部 key 注入为 env
- key 名称直接作为 env 名称（如 `db.host` → `db.host`；K8s 不允许 `.` 写入 env 名，会原样保留）
- 同样不自动生效

### 3. volume 挂载

```yaml
volumes:
- name: config
  configMap:
    name: myapp-config
    items:
    - key: application.yaml
      path: app.yaml
    - key: log.properties
      path: log.properties
containers:
- name: app
  volumeMounts:
  - name: config
    mountPath: /etc/myapp
```

- **会自动更新**（受 kubelet sync 周期 + 时延影响）
- 通常 30~60s 内一致；inotify 触发可秒级
- 注意 `subPath` 不会更新（见第四节）

### 4. 三种方式对比

| 方式 | 自动更新 | 适合配置 | 限制 |
| ---- | -------- | -------- | ---- |
| env | 否 | 启动期常量、URL、SPI | 改完需重启 |
| envFrom | 否 | 一次喂大批量 | 同上 |
| volume 挂载 | 是 | 配置文件、证书、动态配置 | 单文件不能太大 |

> **核心原理**：volume 挂载靠 kubelet 周期性 sync（默认 60s）+ inotify 实时通知。文件内容变更，**但容器内进程要不要重新加载**取决于应用自身（如 Spring Cloud Config 客户端 / nginx -s reload / 自定义 file watcher）。

## 四、subPath 的坑

```yaml
volumeMounts:
- name: config
  mountPath: /etc/myapp/app.yaml
  subPath: app.yaml   # ← 单文件挂载
```

`subPath` 把 ConfigMap 单个 key 挂成指定路径。**坑**：subPath 挂载是个软链到固定目录，**ConfigMap 更新时该文件不会自动更新**（subPath 不参与 inotify 同步）。

解决：

```yaml
# 方案 1：把整目录挂载，只读文件
volumeMounts:
- name: config
  mountPath: /etc/myapp
  readOnly: true
# 容器内读 /etc/myapp/app.yaml

# 方案 2：项目目录为非共享目录，可以共用 mountPath，免去 subPath
```

## 五、immutable ConfigMap（强烈推荐）

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: myapp-config
data:
  application.yaml: |
    server:
      port: 8080
binaryData:
  ...
immutable: true   # v1.21+
```

效果：

- 创建后禁止 update，只能删除重建
- API 服务直接用 hash 索引，不再 watch 变更
- **大量 ConfigMap 时kube-apiserver 性能提升明显**（实测 10x QPS）
- 配合 GitOps / Helm / Kustomize 流水线，配置变更即资源重建

代价：应用必须能响应挂载文件变化（重启、reload），或者用滚动更新。

## 六、Secret 类型

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: myapp-secret
type: Opaque    # 默认
data:
  username: YWRtaW4=        # base64
  password: c3VjY2Vzcw==
```

| type | 用途 |
| ---- | ---- |
| **Opaque**（默认） | 任意键值，base64 包装 |
| **kubernetes.io/dockerconfigjson** | 镜像仓库 dockercfg |
| **kubernetes.io/tls** | TLS 证书（tls.crt / tls.key） |
| **kubernetes.io/service-account-token** | SA 绑定的 token |
| **bootstrap.kubernetes.io/token** | 节点引导 token |
| **Opaque + annotations `kubernetes.io/credential-provider`** | 镜像拉取 |

> **关键警告**：`Secret` 的 value 在 etcd 中只是 base64，不是加密。任何人能 `kubectl get secret` 拿到原文。结合 RBAC 限制 + etcd 静态加密 + KMS 才是正确解。

## 七、触发滚动更新

### 1. checksum annotation

```yaml
spec:
  template:
    metadata:
      annotations:
        checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}
    spec:
      containers:
      - name: app
        envFrom:
        - configMapRef:
            name: myapp-config
```

Helm 模板渲染时把 ConfigMap 数据计算 hash 注入 annotation，ConfigMap 变 → hash 变 → Annotation 变 → Deployment 滚动。

### 2. Reloader（Stakater）

```bash
# 部署
helm repo add stakater https://stakater.github.io/stakater-charts
helm install reloader stakater/reloader
```

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  annotations:
    reloader.stakater.com/auto: "true"        # 自动发现关联 ConfigMap
    reloader.stakater.com/match: "true"        # 匹配同名前缀
spec:
  ...
```

部署同名的 ConfigMap/Secret 变更时，自动触发滚动，比手写 hash 省心。

### 3. K8s 1.28+ 原生滚动

```yaml
spec:
  template:
    spec:
      containers:
      - name: app
        env:
        - name: DB_HOST
          valueFrom:
            configMapKeyRef:
              name: myapp-config
              key: db.host
```

不再需要手工 hash；K8s 检测到 ConfigMap 引用，变更自动触发滚动（需要 kubelet 启用 `--feature-gates=ConfigMapAndSecretChangeDetection=true`，1.28 起默认开启）。

## 八、Helm 与 Kustomize

### 1. Helm values → ConfigMap

```yaml
{{- $configMap := .Values.configMap }}
apiVersion: v1
kind: ConfigMap
metadata:
  name: myapp-config
data:
  application.yaml: |
    server:
      port: {{ .Values.configMap.server.port }}
    db:
      host: {{ .Values.configMap.db.host }}
```

配合 checksum annotation 触发滚动。

### 2. Kustomize configMapGenerator

```yaml
# kustomization.yaml
configMapGenerator:
- name: myapp-config
  files:
  - application.yaml
  - log.properties=log.dev.properties
secretGenerator:
- name: myapp-secret
  commands:
    "password.txt": "echo -n $DB_PASSWORD"
envs:
- .env.dev
generatorOptions:
  disableNameSuffixHash: false
```

**Hash 后缀机制**：`name: myapp-config` 在编译后变成 `myapp-config-8c3a4b`，Deployment 引用的是带 hash 的版本 → ConfigMap 内容变 → hash 变 → Deployment 模板里 Pod 引用的 ConfigMap 名变 → 触发新 Pod 创建 → 老 Pod 销毁。

优点：天然幂等、GitOps 友好；缺点：滚动期间新 Pod 用新 ConfigMap，老 Pod 持老 ConfigMap 同时存在。

## 九、External Secrets Operator（ESO）

把 Vault / AWS Secrets Manager / 阿里云 KMS 同步成 K8s Secret，对应用屏蔽云细节。

```bash
helm install external-secrets external-secrets/external-secrets
```

```yaml
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: vault-backend
  namespace: prod
spec:
  provider:
    vault:
      server: "http://vault.vault:8200"
      path: "secret"
      version: "v2"
      auth:
        kubernetes:
          mountPath: "kubernetes"
          role: "myapp"
          serviceAccountRef:
            name: "myapp-sa"
---
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: myapp-db
  namespace: prod
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: vault-backend
    kind: SecretStore
  target:
    name: myapp-db-secret
    creationPolicy: Owner
  data:
  - secretKey: password
    remoteRef:
      key: myapp/db
      property: password
  - secretKey: username
    remoteRef:
      key: myapp/db
      property: username
```

- `SecretStore` 描述远端凭证源
- `ExternalSecret` 描述拉取映射
- 默认 1h 同步（`refreshInterval`），也可 `event` 模式由 Vault 推送

> 责任划分：Vault 管原始凭据，ESO 在 K8s 侧同步，Pod 正常引用 K8s Secret。云端凭据轮转 → ESO 同步 → 配合 reloader 触发滚动。

## 十、Sealed Secrets

适用：希望在 Git 里安全管理 K8s Secret（public repo 也能放）。

```bash
# 安装 controller
helm install sealed-secrets sealed-secrets/sealed-secrets

# 客户端工具
brew install kubeseal
```

```bash
# 加密（离线用 controller 公钥）
echo -n mypassword | kubectl create secret generic my-secret \
  --dry-run=client --from-file=password=/dev/stdin -o yaml \
  | kubeseal -o yaml > my-secret-sealed.yaml

# 推到 Git，CI/ArgoCD 部署
kubectl apply -f my-secret-sealed.yaml
# controller 用私钥自动解密成普通 Secret
```

- 强场景：GitOps + 私密镜像仓库 / 简单静态密钥
- 弱场景：凭据需要动态生成、私钥失窃影响范围大

## 十一、SOPS + age / KMS

适用：GitOps 加密配置文件（整个 YAML 加密）。

```bash
# 1. 生成 age 密钥对
age-keygen -o key.age
# key.age.pub 放在 Git

# 2. 加解密
sops --age $(cat key.age.pub) --encrypt -i secret.yaml
sops --decrypt secret.yaml
```

```yaml
# secret.yaml（加密后提交到 Git）
apiVersion: v1
kind: Secret
metadata:
  name: myapp-secret
stringData:
  password: ENC[AES256_GCM,data:xxx,tag:yyy,type:str]
sops:
  age:
  - recipient: age1xxxxxxxxxxxxxxxxxxxxxxxx
    enc: |
      -----BEGIN AGE ENCRYPTED FILE-----
      ...
      -----END AGE ENCRYPTED FILE-----
```

CI / ArgoCD 部署时用私钥解（如仓库级 Secret 或 `--decryption-sops-recipient`）。

云版本：SOPS + KMS（AWS KMS / GCP KMS / AliCloud KMS），密钥由云端托管。

```bash
sops --kms arn:aws:kms:us-east-1:111122223333:key/abcd --encrypt secret.yaml
```

## 十二、CSI Secrets Store Driver

类似 Vault Agent 注入，但走 CSI 卷：

```yaml
apiVersion: secrets-store.csi.x-k8s.io/v1
kind: SecretProviderClass
metadata:
  name: myapp-vault
spec:
  provider: vault
  parameters:
    vaultAddress: "http://vault.vault:8200"
    roleName: "myapp"
    objects: |
      - objectName: "db-password"
        secretPath: "secret/data/myapp/db"
        secretKey: "password"
  secretObjects:
  - data:
    - key: password
      objectName: db-password
    secretName: myapp-db-secret
    type: Opaque
```

```yaml
volumes:
- name: secrets
  csi:
    driver: secrets-store.csi.k8s.io
    readOnly: true
    volumeAttributes:
      secretProviderClass: myapp-vault
      # sync 周期 CSI 1.0+ 起支持
      rotationPollInterval: "60s"
```

优势：Pod 内文件 + 同时同步成 K8s Secret（`secretObjects` 部分），其他 Pod 直接引用。

## 十三、etcd 静态加密

K8s 数据落 etcd，但默认 **ConfigMap 是明文、Secret 也只是 base64**。加密方案：

```yaml
# /etc/kubernetes/encryption-config.yaml
apiVersion: apiserver.config.k8s.io/v1
kind: EncryptionConfiguration
resources:
  - resources:
    - secrets
    - configmaps
    providers:
    - aescbc:
        keys:
        - name: key1
          secret: <base64-encoded-32-byte-key>
    - identity: {}
```

```yaml
# kube-apiserver 启动参数
--encryption-provider-config=/etc/kubernetes/encryption-config.yaml
```

密钥可以用 KMS（AWS KMS / AliCloud KMS）托管：

```yaml
providers:
  - kms:
      name: vault-kms
      endpoint: unix:///var/run/vault/secrets/vault.sock
      keys:
        - name: vault-kms-prod
          # 由 KMS 自动生成
```

> 实践：必须两套配合 — KMS 静态加密 etcd + RBAC 限制 Secret 读取 + Audit 日志，三件套缺一不可。

## 十四、RBAC 限制 Secret

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: prod
  name: secret-reader
rules:
- apiGroups: [""]
  resources: ["secrets"]
  resourceNames: ["myapp-secret"]   # 限定具体 Secret
  verbs: ["get", "watch"]            # 不能 list
```

- 让开发只能看自己的 Secret
- 所有生产 Secret 启用 audit log：kubectl get secret → API audit
- `kubectl get secrets -A` 权限收紧，普通运维只能 `list` 而非 `get`

## 十五、优缺点

### 优点

- 原生资源，无需额外组件
- 控制器模式 + RBAC + 审计天然集成
- 工具链完备：Helm / Kustomize / Sealed Secrets / SOPS / ESO
- 滚动更新 / 健康检查 / 配置回滚都已收敛

### 缺点

- Secret 仅 base64，靠 KMS + RBAC 加强
- 多 Secret 列表影响 kube-apiserver 性能（用 immutable）
- 多集群 / 多云分发不便
- 数量受 1MB 限制（Secret），大证书 / 镜像配置需外置
- subPath 不更新、env 不更新：仍是高频踩坑点

## 十六、最佳实践

- **immutable ConfigMap 是默认**：配合 Helm/Kustomize 哈希滚动
- **Secret 默认走 Vault / KMS + ESO 同步**，原生 Secret 仅作最后一道
- **避免 subPath**：把整目录挂载，文件自己选
- **卷挂载 + 进程主动 reload**：文件更新不重启 应用就应识别
- **checksum annotation / Reloader** 触发 env 变更后的滚动
- **etcd 静态加密 + KMS 是底线**：高敏感场景必须
- **RBAC 限定 resourceNames + verbs**，禁止开发 list 全部 Secret
- **Secret 大小**：拆分多 Secret，避免单 Secret 过大
- **限频和设备审计**：开启 API audit、Secret 读取审计
- **多环境**：用命名空间隔离 + 不同 RBAC，不依赖配置文件本身区分
- **可观测**：结合 Reloader / Flux ImageUpdate 等，确保配置变更留痕
