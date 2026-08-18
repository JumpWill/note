# RBAC 权限管理 (RBAC Authorization)

> 本章系统讲解 K8s 的 RBAC 权限体系:ServiceAccount、Role、RoleBinding、ClusterRole、ClusterRoleBinding。

## 一、RBAC 概述

### 1.1 为什么需要 RBAC

```text
默认 K8s: 所有认证过的用户都有完全权限 (不安全)

RBAC (Role-Based Access Control):
- 基于角色的访问控制
- 不同角色不同权限
- 最小权限原则
```

### 1.2 授权模式

```text
K8s 支持多种授权模式 (--authorization-mode):

1. Node     - 节点组件授权 (kubelet 用)
2. ABAC     - 基于属性 (1.6+ deprecated)
3. RBAC     - 基于角色 (推荐生产)
4. Webhook  - 外部授权 (如 OPA)
5. AlwaysDeny / AlwaysAllow

生产推荐:
  --authorization-mode=Node,RBAC
```

### 1.3 RBAC 核心对象

```text
4 个核心对象:

1. Role             - 命名空间级角色
2. RoleBinding      - 命名空间级绑定
3. ClusterRole      - 集群级角色
4. ClusterRoleBinding - 集群级绑定

关系:
   Role/ClusterRole 定义权限
   RoleBinding/ClusterRoleBinding 把权限赋予主体 (ServiceAccount/User/Group)
```

---

## 二、ServiceAccount (服务账号)

### 2.1 概念

**ServiceAccount** 是 K8s 中 Pod 使用的身份。

```text
User vs ServiceAccount:
- User: 给人用 (kubectl 客户端)
- ServiceAccount: 给 Pod/服务用

每个 Namespace 默认有 default ServiceAccount
Pod 默认使用 default SA
```

### 2.2 创建 ServiceAccount

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: my-app-sa
  namespace: production
  # 自动创建 Token (1.24+)
  annotations:
    # K8s 1.24+ 手动指定 SA Token 注解 (可选)
```

### 2.3 Pod 使用 ServiceAccount

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: my-pod
  namespace: production
spec:
  serviceAccountName: my-app-sa   # 使用指定 SA
  containers:
  - name: app
    image: my-app:1.0
    # Token 自动挂载到 /var/run/secrets/kubernetes.io/serviceaccount/
```

### 2.4 K8s 1.24+ 重要变更

```text
1.24 之前:
  - 创建 SA 自动生成长期 Token
  - 自动挂载到 Pod

1.24+ (推荐):
  - 创建 SA 不再自动生成 Token
  - 需手动用 TokenRequest API 申请短期 Token
  - 通过 BoundServiceAccountTokenVolume projection 挂载

迁移:
  - 旧 SA Token 仍在,但生产推荐用短期 Token
  - K8s 1.24+ 服务网格 (Istio) 自动兼容
```

### 2.5 创建长期 Token (1.24+)

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: my-app-sa-token
  namespace: production
  annotations:
    kubernetes.io/service-account.name: my-app-sa
type: kubernetes.io/service-account-token
```

---

## 三、Role 与 RoleBinding

### 3.1 Role (命名空间级角色)

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: production
  name: pod-reader
rules:
# verbs: get, list, watch, create, update, patch, delete
# resources: pods, services, deployments, configmaps, secrets, ...
# apiGroups: "" (核心组) / apps / batch / extensions / networking.k8s.io
- apiGroups: [""]                # 核心 API 组
  resources: ["pods"]
  verbs: ["get", "list", "watch"]

- apiGroups: [""]                # 另一个规则
  resources: ["pods/log"]
  verbs: ["get"]

- apiGroups: ["", "apps"]
  resources: ["pods", "deployments"]
  verbs: ["*"]                   # 所有操作

- apiGroups: ["batch"]
  resources: ["jobs", "cronjobs"]
  verbs: ["get", "list"]
```

### 3.2 RoleBinding (命名空间级绑定)

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: read-pods
  namespace: production
subjects:
# 主体类型:
# - User: 用户
# - Group: 用户组
# - ServiceAccount: 服务账号
- kind: User
  name: alice
  apiGroup: rbac.authorization.k8s.io
- kind: Group
  name: developers
  apiGroup: rbac.authorization.k8s.io
- kind: ServiceAccount
  name: my-app-sa
  namespace: production

roleRef:
  kind: Role
  name: pod-reader
  apiGroup: rbac.authorization.k8s.io
```

---

## 四、ClusterRole 与 ClusterRoleBinding

### 4.1 ClusterRole (集群级角色)

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: node-admin
rules:
- apiGroups: [""]
  resources: ["nodes"]
  verbs: ["get", "list", "watch"]

- apiGroups: [""]
  resources: ["pods", "services"]
  verbs: ["get", "list", "watch"]

- nonResourceURLs: ["/healthz", "/metrics"]
  verbs: ["get"]
```

### 4.2 K8s 内置 ClusterRole

```bash
# 查看所有内置 ClusterRole
kubectl get clusterroles

# 常用的:
# cluster-admin          - 超级管理员
# admin                  - 命名空间管理员
# edit                  - 读写权限 (不能修改角色/绑定)
# view                  - 只读权限
# system:node-proxier   - kubelet 用
# system:controller:*   - 各种 ControllerManager 用
```

### 4.3 ClusterRoleBinding (集群级绑定)

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: cluster-admins
subjects:
- kind: Group
  name: cluster-admins
  apiGroup: rbac.authorization.k8s.io
- kind: ServiceAccount
  name: my-admin-sa
  namespace: kube-system

roleRef:
  kind: ClusterRole
  name: cluster-admin          # 绑定到内置 cluster-admin
  apiGroup: rbac.authorization.k8s.io
```

---

## 五、RBAC 实战

### 5.1 创建只读用户

```bash
# 1. 创建用户证书 (基于证书认证)
# 或使用 OIDC / Webhook 认证

# 2. 创建 ClusterRoleBinding (只读权限)
kubectl create clusterrolebinding readonly-user \
  --clusterrole=view \
  --user=readonly-user

# 3. 验证
kubectl auth can-i get pods --as=readonly-user
# yes

kubectl auth can-i delete pods --as=readonly-user
# no
```

### 5.2 给 ServiceAccount 授权

```bash
# 1. 创建 SA
kubectl create sa my-app-sa -n production

# 2. 创建 Role
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: production
  name: app-role
rules:
- apiGroups: [""]
  resources: ["pods", "configmaps"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["apps"]
  resources: ["deployments"]
  verbs: ["get", "list", "watch"]

# 3. 绑定 SA 到 Role
kubectl create rolebinding app-sa-binding \
  --namespace=production \
  --role=app-role \
  --serviceaccount=production:my-app-sa

# 4. Pod 使用 SA
# spec.serviceAccountName: my-app-sa
```

### 5.3 高级:基于资源名的权限

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: production
  name: secrets-reader
rules:
# 只能访问特定 Secret
- apiGroups: [""]
  resources: ["secrets"]
  resourceNames: ["db-credentials", "api-key"]
  verbs: ["get"]
```

### 5.4 高级:基于条件的权限 (K8s 1.28+)

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: production
  name: deploy-time-restricted
rules:
- apiGroups: ["apps"]
  resources: ["deployments"]
  verbs: ["create", "update"]
  # 只允许工作时间部署
- apiGroups: ["apps"]
  resources: ["deployments"]
  verbs: ["create"]
  whenConditions:
  - name: RequestTime
    expression: "request.time >= '2026-01-01T00:00:00Z' && request.time <= '2026-12-31T23:59:59Z'"
```

---

## 六、RBAC 调试

### 6.1 查看权限

```bash
# 查看当前用户能做什么
kubectl auth can-i create pods
kubectl auth can-i delete nodes

# 查看指定用户能做什么
kubectl auth can-i create pods --as=alice
kubectl auth can-i create pods --as=system:serviceaccount:production:my-app-sa -n production

# 列出所有能做的操作
kubectl auth can-i --list --as=alice -n production

# 查看 Role / RoleBinding
kubectl get role,rolebinding -n production
kubectl get clusterrole,clusterrolebinding

# 详细查看
kubectl describe role app-role -n production
kubectl describe rolebinding app-sa-binding -n production
```

### 6.2 排查权限不足

```bash
# 模拟某用户的权限
kubectl auth can-i list pods -n production --as=alice

# 查看拒绝原因 (API Server 日志)
kubectl logs -n kube-system kube-apiserver-master | grep -i "forbidden"
```

### 6.3 RBAC 修复

```bash
# 用户无法 list pods
kubectl auth can-i list pods --as=alice -n production
# no

# 排查: 找 alice 在 production 的所有 RoleBinding
kubectl get rolebinding -n production -o json | \
  jq '.items[] | select(.subjects[].name=="alice")'

# 添加权限
kubectl create rolebinding alice-read \
  --namespace=production \
  --clusterrole=view \
  --user=alice
```

---

## 七、RBAC 最佳实践

### 7.1 最小权限原则

```text
1. 永远不授予 cluster-admin (除非必要)
2. 用 Role 不用 ClusterRole (除非跨命名空间)
3. 按业务拆分 SA,不同服务不同 SA
4. 定期 audit RBAC 配置
5. 删除不再需要的 ServiceAccount
```

### 7.2 命名空间隔离

```text
生产环境按业务拆分命名空间:
  - production-app
  - production-data
  - production-monitor

不同命名空间用不同 SA:
  - production-app-sa
  - production-data-sa
  - production-monitor-sa
```

### 7.3 用户与组管理

```text
生产推荐:
- 用 OIDC 集成企业 IDP (Okta、Auth0、企业 AD)
- 用组 (Group) 管理权限,不用单个用户
- 离职员工只需从组移除,无需手动清理 RBAC

K8s 配置:
  --oidc-issuer-url=https://accounts.google.com
  --oidc-client-id=xxx
  --oidc-username-claim=email
  --oidc-groups-claim=groups
```

### 7.4 ServiceAccount Token 安全

```text
1. K8s 1.24+: 使用短期 Token (BoundServiceAccountToken)
2. 不要在镜像中硬编码 Token
3. Secret 存长期 Token 时开启 etcd 加密
4. 限制 Token 权限 (最小权限)
5. 监控异常 Token 使用
```

### 7.5 服务网格 + RBAC

```text
服务网格 (Istio) 与 RBAC 集成:
  - RBAC 控制 K8s API 访问
  - 服务网格控制服务间调用

双层防护:
  - 入口: RBAC (K8s API)
  - 服务间: 服务网格 (mTLS + AuthorizationPolicy)
```

---

## 八、RBAC 实战案例

### 8.1 CI/CD 系统专用 SA

```yaml
# CI/CD SA - 只能管理 Deployments
apiVersion: v1
kind: ServiceAccount
metadata:
  name: ci-cd-sa
  namespace: production

---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: production
  name: ci-cd-role
rules:
- apiGroups: ["apps"]
  resources: ["deployments", "replicasets"]
  verbs: ["get", "list", "watch", "create", "update", "patch"]
- apiGroups: [""]
  resources: ["pods", "services"]
  verbs: ["get", "list", "watch"]
- apiGroups: [""]
  resources: ["pods/log"]
  verbs: ["get"]
- apiGroups: ["apps"]
  resources: ["deployments/scale"]
  verbs: ["update"]

---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: ci-cd-binding
  namespace: production
subjects:
- kind: ServiceAccount
  name: ci-cd-sa
  namespace: production
roleRef:
  kind: Role
  name: ci-cd-role
  apiGroup: rbac.authorization.k8s.io
```

### 8.2 监控组件 SA

```yaml
# Prometheus 监控 SA - 集群只读
apiVersion: v1
kind: ServiceAccount
metadata:
  name: prometheus
  namespace: monitoring

---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: prometheus-read
rules:
- apiGroups: [""]
  resources: ["pods", "nodes", "services", "endpoints"]
  verbs: ["get", "list", "watch"]
- nonResourceURLs: ["/metrics"]
  verbs: ["get"]

---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: prometheus-read
subjects:
- kind: ServiceAccount
  name: prometheus
  namespace: monitoring
roleRef:
  kind: ClusterRole
  name: prometheus-read
  apiGroup: rbac.authorization.k8s.io
```

---

## 核心要点速记

### RBAC 四件套

```text
Role / ClusterRole      → 定义权限
RoleBinding / ClusterRoleBinding → 绑定到主体

Role → 命名空间级
ClusterRole → 集群级
```

### 主体类型

```text
- User           (kubectl 用户)
- Group          (用户组)
- ServiceAccount (Pod/服务身份)
```

### 权限维度

```text
apiGroups: ["", "apps", "batch", ...]
resources: ["pods", "deployments", "services", ...]
verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
resourceNames: ["pod-name-1", ...] (可选,限制具体资源)
```

### 调试命令

```bash
kubectl auth can-i <verb> <resource> --as=<user>
kubectl auth can-i --list --as=<user>
kubectl get role,rolebinding -n <ns>
kubectl get clusterrole,clusterrolebinding
kubectl describe rolebinding <name> -n <ns>
```

### 最佳实践

```text
1. 最小权限原则
2. 用 Role 不用 ClusterRole (能 Role 就 Role)
3. 服务用独立 ServiceAccount
4. K8s 1.24+ 用短期 Token
5. 集成 OIDC (企业 IDP)
6. 定期 audit
```

### 常用内置 ClusterRole

```text
cluster-admin: 超级管理员
admin:        命名空间管理员 (但有 ResourceQuota 限制)
edit:         读写但不能修改 RBAC
view:         只读
system:*:     K8s 内部组件
```

---

## 参考

- **RBAC**: https://kubernetes.io/docs/reference/access-authn-authz/rbac/
- **ServiceAccount**: https://kubernetes.io/docs/concepts/configuration/service-accounts/
- **认证**: https://kubernetes.io/docs/reference/access-authn-authz/authentication/
- **授权模式**: https://kubernetes.io/docs/reference/access-authn-authz/authorization/
