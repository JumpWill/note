# Namespace 与资源管理 (Namespaces & Resource Quotas)

> 本章讲解 K8s 多租户管理:Namespace 隔离、ResourceQuota 资源配额、LimitRange 限制、节点选择。

## 一、Namespace 概述

### 1.1 概念

**Namespace (命名空间)** 是 K8s 中用于**多租户隔离**的虚拟集群。

```text
集群
├── ns: production
│   ├── Pod
│   ├── Service
│   ├── ConfigMap
│   └── Secret
├── ns: staging
│   ├── Pod
│   └── Service
└── ns: kube-system
    ├── Pod (kube-proxy)
    └── Pod (coredns)
```

### 1.2 Namespace 作用

```text
1. 资源隔离: 不同 namespace 的资源互不影响
2. 权限隔离: 不同 namespace 可设置不同 RBAC
3. 配额限制: ResourceQuota 控制资源使用
4. 网络隔离: NetworkPolicy 按 ns 隔离
5. 业务隔离: 不同环境/团队/项目分 ns
```

### 1.3 内置 Namespace

```text
default       - 默认 (无指定时的 namespace)
kube-system   - K8s 系统组件 (apiserver, etcd, dns...)
kube-public   - 公共资源 (所有用户可读)
kube-node-lease - 节点心跳 (K8s 1.13+)
```

---

## 二、Namespace 操作

### 2.1 创建

```bash
# 命令式
kubectl create namespace production
kubectl create ns dev      # 简写

# 声明式
apiVersion: v1
kind: Namespace
metadata:
  name: production
  labels:
    env: production
    team: platform
    # 推荐标签 (K8s 官方建议)
    kubernetes.io/metadata.name: production
    name: production
```

### 2.2 查看

```bash
# 列出所有 namespace
kubectl get namespaces
kubectl get ns

# 当前上下文 namespace
kubectl config view --minify | grep namespace

# 切换 namespace
kubectl config set-context --current --namespace=production

# 直接指定 namespace
kubectl get pods -n production
kubectl get pods --all-namespaces
kubectl get pods -A                # 简写
```

### 2.3 删除

```bash
kubectl delete namespace production

# 注意: 删除 ns 会同时删除 ns 内所有资源
# 注意: 删除前需检查是否还有资源
kubectl get all -n production
```

### 2.4 Namespace 配额 (Quota)

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: production-quota
  namespace: production
spec:
  hard:
    # 资源总量
    requests.cpu: "100"
    requests.memory: 200Gi
    limits.cpu: "200"
    limits.memory: 400Gi
    
    # 存储
    requests.storage: 1Ti
    persistentvolumeclaims: "10"
    
    # 对象数量
    pods: "100"
    services: "50"
    secrets: "100"
    configmaps: "100"
    deployments.apps: "30"
    replicasets.apps: "50"
    services.loadbalancers: "5"
    services.nodeports: "10"
    
    # 其他资源
    count/jobs.batch: "20"
    count/cronjobs.batch: "10"
```

### 2.5 Namespace 默认资源限制 (LimitRange)

```yaml
apiVersion: v1
kind: LimitRange
metadata:
  name: default-limits
  namespace: production
spec:
  limits:
  # 默认 (没设 resources 的 Pod)
  - type: Container
    default:
      cpu: 500m
      memory: 512Mi
    defaultRequest:
      cpu: 100m
      memory: 128Mi
    max:
      cpu: 1000m
      memory: 1Gi
    min:
      cpu: 50m
      memory: 64Mi
    maxLimitRequestRatio:
      cpu: 4
      memory: 4
```

---

## 三、ResourceQuota 详解

### 3.1 配额类型

```text
1. 计算资源 (Compute)
   - requests.cpu / limits.cpu
   - requests.memory / limits.memory
   - requests.ephemeral-storage

2. 存储资源 (Storage)
   - requests.storage
   - persistentvolumeclaims
   - <storage_class_name>.storageclass.storage.k8s.io/requests.storage

3. 对象数量 (Object Count)
   - pods, services, secrets, configmaps
   - deployments.apps, replicasets.apps
   - jobs.batch, cronjobs.batch
   - services.loadbalancers, services.nodeports

4. 其他
   - count/<resource>.<group>: 任意资源数量
```

### 3.2 配额作用域

```text
# 默认: 所有 Pod 共享配额
apiVersion: v1
kind: ResourceQuota
metadata:
  name: all-pods
spec:
  scopes: ["BestEffort", "NotBestEffort"]
  hard:
    pods: "10"

# 仅 BestEffort Pod
scopes: ["BestEffort"]

# 仅 Guaranteed / Burstable Pod
scopes: ["NotBestEffort"]

# 按 PriorityClass 区分
scopes: ["PriorityClass"]
scopeSelector:
  matchExpressions:
  - operator: In
    scopeName: PriorityClass
    values: ["high-priority"]
```

### 3.3 配额实战

```yaml
# 场景: 限制某个 namespace 的资源
apiVersion: v1
kind: ResourceQuota
metadata:
  name: compute-quota
  namespace: dev
spec:
  hard:
    requests.cpu: "20"           # 所有 Pod CPU 请求总和 ≤ 20 核
    requests.memory: 40Gi
    limits.cpu: "40"
    limits.memory: 80Gi
    pods: "30"
    services: "30"
```

```bash
# 查看配额使用
kubectl describe resourcequota -n dev
# 输出:
# Resource         Used  Hard
# --------         ----  ----
# limits.cpu       8     40
# limits.memory    16Gi  80Gi
# pods             10    30
```

---

## 四、LimitRange 详解

### 4.1 与 ResourceQuota 区别

```text
ResourceQuota:
- 限制整个 namespace 的资源总量
- 例如: 整个 ns CPU 不能超过 100 核

LimitRange:
- 限制单个 Pod/Container/PVC 的默认和最大最小值
- 例如: 每个 Pod 默认 CPU 500m,最大 1000m
```

### 4.2 LimitRange 类型

```yaml
apiVersion: v1
kind: LimitRange
metadata:
  name: all-limits
  namespace: production
spec:
  limits:
  # Container 级别 (最常用)
  - type: Container
    default:                    # 限制 (默认 limit)
      cpu: 500m
      memory: 512Mi
    defaultRequest:             # 请求 (默认 request)
      cpu: 100m
      memory: 128Mi
    max:                        # 单个容器最大
      cpu: 2000m
      memory: 4Gi
    min:                        # 单个容器最小
      cpu: 100m
      memory: 64Mi
    maxLimitRequestRatio:       # limit/request 比值上限
      cpu: 4
      memory: 2

  # Pod 级别
  - type: Pod
    max:
      cpu: 4000m
      memory: 8Gi

  # PersistentVolumeClaim 级别
  - type: PersistentVolumeClaim
    max:
      storage: 100Gi
    min:
      storage: 1Gi

  # 任何资源都需设 (强约束)
  - type: Container
    default:
      cpu: 100m
      memory: 64Mi
    defaultRequest:
      cpu: 100m
      memory: 64Mi
    min:
      cpu: 100m
      memory: 64Mi
    max:
      cpu: 500m
      memory: 256Mi
```

---

## 五、节点选择与调度

### 5.1 节点标签管理

```bash
# 节点标签 (Kubernetes 推荐格式)
kubectl label nodes node-1 kubernetes.io/role=worker
kubectl label nodes node-1 node.kubernetes.io/instance-type=m5.xlarge
kubectl label nodes node-1 topology.kubernetes.io/zone=us-east-1a
kubectl label nodes node-1 kubernetes.io/os=linux

# 自定义标签
kubectl label nodes node-1 team=platform
kubectl label nodes node-1 environment=production

# 查看
kubectl get nodes --show-labels
```

### 5.2 节点 Taints 隔离

```bash
# Master 节点禁调度业务 Pod (K8s 1.20+ 已默认)
kubectl taint nodes <master-node> node-role.kubernetes.io/control-plane=true:NoSchedule

# 专用节点
kubectl taint nodes node-gpu dedicated=gpu:NoSchedule

# 维护时
kubectl taint nodes node-1 maintenance=true:NoExecute
```

### 5.3 多团队节点池

```bash
# 标记节点属于不同团队
kubectl label nodes node-a team=frontend
kubectl label nodes node-b team=backend

# 通过 namespace + nodeSelector 隔离
# 配合 taints 强制隔离
kubectl taint nodes node-a dedicated=frontend:NoSchedule
kubectl taint nodes node-b dedicated=backend:NoSchedule

# Pod toleration
spec:
  tolerations:
  - key: dedicated
    operator: Equal
    value: frontend
    effect: NoSchedule
```

---

## 六、多租户管理

### 6.1 多租户架构

```text
集群
├── ns: team-a
│   ├── ResourceQuota: team-a-quota
│   ├── LimitRange: team-a-defaults
│   ├── RBAC: team-a-admins (RoleBinding)
│   └── NetworkPolicy: team-a-isolation
├── ns: team-b
│   ├── ResourceQuota: team-b-quota
│   ├── LimitRange: team-b-defaults
│   ├── RBAC: team-b-admins
│   └── NetworkPolicy: team-b-isolation
└── ns: monitoring
    └── ...
```

### 6.2 命名空间最佳实践

```text
1. 按环境划分
   - dev / staging / production

2. 按业务划分
   - user-service
   - order-service
   - payment-service

3. 按团队划分
   - team-frontend
   - team-backend
   - team-data

4. 不滥用
   - 不为每个用户创建 ns
   - 不为每个应用创建 ns (用 label)
```

### 6.3 命名空间标签规范

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: payment-prod
  labels:
    # K8s 推荐标签
    kubernetes.io/metadata.name: payment-prod
    name: payment-prod
    
    # 业务标签
    app.kubernetes.io/part-of: payment-platform
    app.kubernetes.io/managed-by: platform-team
    app.kubernetes.io/environment: production
    
    # 自定义
    team: payments
    cost-center: "1234"
    compliance: pci-dss
    data-classification: confidential
    
    # 工具管理
    istio-injection: enabled
    linkerd.io/inject: enabled
```

---

## 七、Namespace 实战

### 7.1 完整环境隔离配置

```bash
# 创建 dev namespace
kubectl create ns dev
kubectl label ns dev env=dev tier=development

# 创建 staging namespace
kubectl create ns staging
kubectl label ns staging env=staging tier=pre-production

# 创建 production namespace
kubectl create ns production
kubectl label ns production env=production tier=production
```

### 7.2 生产环境配置

```yaml
# production namespace 配置
apiVersion: v1
kind: Namespace
metadata:
  name: production
  labels:
    env: production
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/audit: restricted
---
# ResourceQuota: 限制总资源
apiVersion: v1
kind: ResourceQuota
metadata:
  name: prod-quota
  namespace: production
spec:
  hard:
    requests.cpu: "50"
    requests.memory: 100Gi
    limits.cpu: "100"
    limits.memory: 200Gi
    pods: "200"
    services: "50"
---
# LimitRange: 默认 + 限制
apiVersion: v1
kind: LimitRange
metadata:
  name: prod-defaults
  namespace: production
spec:
  limits:
  - type: Container
    default:
      cpu: 1000m
      memory: 1Gi
    defaultRequest:
      cpu: 100m
      memory: 128Mi
    max:
      cpu: 4000m
      memory: 8Gi
    min:
      cpu: 50m
      memory: 64Mi
---
# NetworkPolicy: 默认拒绝,显式允许
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny
  namespace: production
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
```

### 7.3 Namespace 删除清理

```bash
# 1. 查看资源 (确认可删除)
kubectl get all -n <namespace>

# 2. 删除整个 namespace (级联删除所有资源)
kubectl delete namespace <name>

# 3. 验证
kubectl get ns <name>
# Error from server (NotFound): namespaces "<name>" not found

# 注意: 删除是异步的,需等待
kubectl get ns
# 状态: Terminating
```

---

## 核心要点速记

### Namespace 核心

```text
- K8s 多租户隔离单元
- 默认 namespace: default
- 推荐标签: kubernetes.io/metadata.name
- 切换: kubectl config set-context --current --namespace=<ns>
```

### ResourceQuota vs LimitRange

```text
ResourceQuota:
  - 限制整个 namespace 资源总量
  - 例如: 总 CPU ≤ 100, 总 Pod ≤ 50

LimitRange:
  - 限制单个 Pod/Container/PVC 的默认值和最大/最小
  - 例如: 每个 Pod CPU 100m~2000m
```

### 最佳实践

```text
1. 按业务/环境划分 namespace
2. 每个 ns 配 ResourceQuota + LimitRange
3. 启用 PodSecurity admission (restricted)
4. 加 NetworkPolicy (默认拒绝)
5. 用 RBAC 限制 ns 访问
6. 加 labels (team, env, cost-center)
```

### 快速命令

```bash
# 创建
kubectl create ns <name>

# 切换
kubectl config set-context --current --namespace=<ns>

# 配额查看
kubectl describe resourcequota -n <ns>
kubectl describe limitrange -n <ns>

# 删除 (级联)
kubectl delete ns <name>
```

---

## 参考

- **Namespace**: https://kubernetes.io/docs/concepts/overview/working-with-objects/namespaces/
- **ResourceQuota**: https://kubernetes.io/docs/concepts/policy/resource-quotas/
- **LimitRange**: https://kubernetes.io/docs/concepts/policy/limit-range/
- **PodSecurity Standards**: https://kubernetes.io/docs/concepts/security/pod-security-admission/
