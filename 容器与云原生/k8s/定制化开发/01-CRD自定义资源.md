# CRD 自定义资源（CustomResourceDefinition）

## 一、为什么要做 CRD

### 1.1 业务背景

```text
现实场景：
  - 公司自研数据库 Operator，希望像内置资源一样管理
  - 业务团队有自己的 CRD（如 MySQLCluster、RedisCluster）
  - 云厂商抽象资源（如 ACK 的 CRD、AWS 的 CRD）
  - 中间件服务（如 Kafka、RabbitMQ）需要 K8s 原生管理

CRD 让 K8s 不再只是 "Pod 调度器"，而是 "可扩展的应用管理平台"。
```

### 1.2 核心价值

```text
1. 扩展 K8s API
   - 不修改 K8s 核心代码
   - 自定义资源类型（如 MySQLCluster）
   - 像内置资源一样使用 kubectl

2. 声明式管理
   - 用 YAML 描述期望状态
   - Controller 自动 reconcile
   - 类似内置 Deployment

3. 与 K8s 生态融合
   - kubectl get/list/watch/describe
   - RBAC 权限控制
   - 监控、告警、日志
```

### 1.3 适用场景

```text
适合 CRD 的场景：
  ✅ 自研中间件 Operator
  ✅ 数据库即服务（DBaaS）
  ✅ 复杂应用编排
  ✅ 多集群管理
  ✅ GitOps 工具

不适合：
  ❌ 简单配置（用 ConfigMap）
  ❌ 单实例资源
  ❌ 频繁变更
```

---

## 二、CRD 基本结构

### 2.1 CRD 定义示例

```yaml
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: mysqlclusters.database.example.com
spec:
  group: database.example.com
  scope: Namespaced            # Namespaced 或 Cluster
  names:
    plural: mysqlclusters
    singular: mysqlcluster
    shortNames: [mc]
    kind: MySQLCluster
    listKind: MySQLClusterList
  scope: Namespaced
  versions:
  - name: v1                  # 版本名
    served: true              # 是否启用
    storage: true             # 是否存储
    deprecated: false         # 是否弃用
    subresources:             # 子资源
      status: {}              # 启用 status 子资源
      scale:                   # 启用 scale 子资源（可选）
        specReplicasPath: .spec.replicas
        statusReplicasPath: .status.replicas
        labelSelectorPath: .status.labelSelector
    additionalPrinterColumns:  # kubectl get 显示的额外列
    - name: Version
      type: string
      jsonPath: .spec.version
    - name: Status
      type: string
      jsonPath: .status.phase
    - name: Age
      type: date
      jsonPath: .metadata.creationTimestamp
    schema:
      openAPIV3Schema:
        type: object
        properties:
          spec:
            type: object
            properties:
              version:
                type: string
                enum: ["5.7", "8.0"]
                default: "8.0"
              replicas:
                type: integer
                minimum: 1
                maximum: 10
                default: 3
              storage:
                type: object
                properties:
                  size:
                    type: string
                    pattern: '^[0-9]+[GTM]i$'
                  storageClass:
                    type: string
                    default: standard
                required: [size]
              resources:
                type: object
                properties:
                  cpu:
                    type: string
                  memory:
                    type: string
            required: [version, storage]
          status:
            type: object
            properties:
              phase:
                type: string
                enum: ["Pending", "Running", "Failed"]
              endpoints:
                type: array
                items:
                  type: object
                  properties:
                    name:
                      type: string
                    port:
                      type: integer
    validation:                  # 可选：高级验证
      openAPIV3Schema:
        x-kubernetes-validations:
        - rule: "self.spec.replicas <= 10"
          message: "replicas must not exceed 10"
```

### 2.2 CRD 自定义资源示例

```yaml
apiVersion: database.example.com/v1
kind: MySQLCluster
metadata:
  name: my-production-db
  namespace: production
  labels:
    app: mysql
    env: production
spec:
  version: "8.0"
  replicas: 3
  storage:
    size: 100Gi
    storageClass: ssd
  resources:
    cpu: "2"
    memory: 8Gi
```

```bash
# kubectl 操作（与内置资源一致）
kubectl get mysqlcluster
kubectl describe mysqlcluster my-production-db
kubectl edit mysqlcluster my-production-db
kubectl delete mysqlcluster my-production-db
kubectl get mysqlcluster -o yaml
```

---

## 三、CRD 版本管理

### 3.1 多版本支持

```yaml
spec:
  versions:
  - name: v1
    served: true
    storage: true
  - name: v1beta1
    served: true
    storage: false        # 不再存储
    deprecated: true      # 标记弃用
    deprecationWarning: |
      v1beta1 is deprecated, use v1
```

### 3.2 版本转换（Conversion Webhook）

```yaml
spec:
  conversion:
    strategy: Webhook
    webhook:
      clientConfig:
        service:
          name: my-conversion-webhook
          namespace: default
          port: 443
        caBundle: <base64-encoded-ca-cert>
      conversionReviewVersions: ["v1", "v1beta1"]
```

---

## 四、CRD 验证规则

### 4.1 OpenAPI v3 验证（内置）

```yaml
schema:
  openAPIV3Schema:
    type: object
    properties:
      spec:
        type: object
        properties:
          replicas:
            type: integer
            minimum: 1
            maximum: 100
          storage:
            type: object
            required: [size]
            properties:
              size:
                type: string
                pattern: '^[0-9]+[GTM]i$'
```

### 4.2 CEL 验证规则（推荐）

```yaml
schema:
  openAPIV3Schema:
    type: object
    x-kubernetes-validations:
    - rule: "self.spec.replicas >= 1"
      message: "replicas must be at least 1"
    - rule: "self.spec.version in ['5.7', '8.0']"
      message: "version must be 5.7 or 8.0"
    - rule: "self.metadata.name.size() <= 20"
      message: "name must not exceed 20 characters"
    - rule: "has(self.spec.storage.size)"
      message: "storage.size is required"
    - rule: "self.spec.replicas <= self.status.replicas + 5"
      message: "scale up limited to 5 replicas at a time"
  required: [spec]
```

### 4.3 完整 CRD 示例（含所有验证）

```yaml
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: applications.app.example.com
spec:
  group: app.example.com
  scope: Namespaced
  names:
    plural: applications
    singular: application
    shortNames: [app]
    kind: Application
    listKind: ApplicationList
    categories: [all]
  versions:
  - name: v1
    served: true
    storage: true
    subresources:
      status: {}
      scale:
        specReplicasPath: .spec.replicas
        statusReplicasPath: .status.replicas
    additionalPrinterColumns:
    - name: Image
      type: string
      jsonPath: .spec.image
    - name: Replicas
      type: integer
      jsonPath: .spec.replicas
    - name: Phase
      type: string
      jsonPath: .status.phase
    - name: Age
      type: date
      jsonPath: .metadata.creationTimestamp
    schema:
      openAPIV3Schema:
        type: object
        properties:
          spec:
            type: object
            required: [image, replicas]
            properties:
              image:
                type: string
                minLength: 1
              replicas:
                type: integer
                minimum: 1
                maximum: 50
                default: 3
              env:
                type: array
                items:
                  type: object
                  properties:
                    name: {type: string}
                    value: {type: string}
              resources:
                type: object
                properties:
                  cpu:    {type: string}
                  memory: {type: string}
          status:
            type: object
            properties:
              phase:
                type: string
                enum: [Pending, Creating, Running, Failed]
              replicas:
                type: integer
              conditions:
                type: array
                items:
                  type: object
                  properties:
                    type: {type: string}
                    status: {type: string}
                    reason: {type: string}
                    message: {type: string}
        x-kubernetes-validations:
        - rule: "self.spec.replicas >= 1"
          message: "replicas must be at least 1"
        - rule: "self.spec.replicas <= 50"
          message: "replicas must not exceed 50"
        - rule: "size(self.spec.env) <= 100"
          message: "env vars count must not exceed 100"
  additionalPrinterColumns:
  - name: URL
    type: string
    jsonPath: .status.url
```

---

## 五、CRD 高级特性

### 5.1 Finalizer（终结器）

```yaml
# 在 CR 中使用
apiVersion: database.example.com/v1
kind: MySQLCluster
metadata:
  finalizers:
  - database.example.com/finalizer
spec:
  # ...
```

```go
// Controller 中处理 Finalizer
func (r *MySQLClusterReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
    mc := &databasev1.MySQLCluster{}
    if err := r.Get(ctx, req.NamespacedName, mc); err != nil {
        return ctrl.Result{}, client.IgnoreNotFound(err)
    }

    // 检查是否被删除
    if !mc.DeletionTimestamp.IsZero() {
        if controllerutil.ContainsFinalizer(mc, finalizerName) {
            // 清理资源（删除数据库实例等）
            if err := r.cleanupExternalResources(ctx, mc); err != nil {
                return ctrl.Result{}, err
            }
            // 移除 Finalizer
            controllerutil.RemoveFinalizer(mc, finalizerName)
            return ctrl.Result{}, r.Update(ctx, mc)
        }
        return ctrl.Result{}, nil
    }

    // 添加 Finalizer
    if !controllerutil.ContainsFinalizer(mc, finalizerName) {
        controllerutil.AddFinalizer(mc, finalizerName)
        return ctrl.Result{}, r.Update(ctx, mc)
    }

    // 正常 reconcile 逻辑
    // ...
}
```

### 5.2 Status 子资源

```yaml
# CR 示例
apiVersion: database.example.com/v1
kind: MySQLCluster
metadata:
  name: my-db
spec:
  version: "8.0"
  replicas: 3
status:                      # 状态由 Controller 更新
  phase: Running
  endpoints:
  - name: primary
    port: 3306
  - name: replica
    port: 3306
  conditions:
  - type: Ready
    status: "True"
    reason: AllPodsReady
    message: "All MySQL pods are ready"
  observedGeneration: 2
```

### 5.3 Subresources

```yaml
versions:
- name: v1
  subresources:
    # status 子资源
    status: {}

    # scale 子资源
    scale:
      specReplicasPath: .spec.replicas
      statusReplicasPath: .status.replicas
      labelSelectorPath: .status.labelSelector
```

```bash
# status 子资源操作
kubectl get mysqlcluster -o jsonpath='{.status.phase}'

# scale 子资源操作（kubectl scale）
kubectl scale mysqlcluster my-db --replicas=5
```

### 5.4 Conversion Strategy（版本转换）

```yaml
spec:
  conversion:
    # 策略 1: None（同版本）
    strategy: None

    # 策略 2: Webhook（推荐）
    strategy: Webhook
    webhook:
      clientConfig:
        service:
          name: my-conversion-webhook
          namespace: default
          path: /convert
          port: 443
        caBundle: <base64>
      conversionReviewVersions: ["v1", "v1beta1"]
```

---

## 六、实战案例

### 6.1 完整 MySQL Cluster CRD

```yaml
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: mysqlclusters.mysql.example.com
spec:
  group: mysql.example.com
  scope: Namespaced
  names:
    plural: mysqlclusters
    singular: mysqlcluster
    shortNames: [mc]
    kind: MySQLCluster
    listKind: MySQLClusterList
  versions:
  - name: v1
    served: true
    storage: true
    subresources:
      status: {}
      scale:
        specReplicasPath: .spec.replicas
        statusReplicasPath: .status.readyReplicas
    additionalPrinterColumns:
    - {name: Version, type: string, jsonPath: .spec.version}
    - {name: Replicas, type: integer, jsonPath: .status.readyReplicas}
    - {name: Phase, type: string, jsonPath: .status.phase}
    schema:
      openAPIV3Schema:
        type: object
        properties:
          spec:
            type: object
            required: [version, storage]
            properties:
              version: {type: string, enum: ["5.7", "8.0"]}
              replicas: {type: integer, minimum: 1, maximum: 10, default: 3}
              storage:
                type: object
                required: [size]
                properties:
                  size: {type: string, pattern: '^[0-9]+[GTM]i$'}
                  storageClass: {type: string}
              resources:
                type: object
                properties:
                  cpu: {type: string}
                  memory: {type: string}
          status:
            type: object
            properties:
              phase: {type: string, enum: [Pending, Creating, Running, Failed]}
              readyReplicas: {type: integer}
              endpoints:
                type: array
                items:
                  type: object
                  properties:
                    name: {type: string}
                    port: {type: integer}
```

### 6.2 RBAC 配置

```yaml
# 1. ClusterRole 允许读取 CRD
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: mysqlcluster-viewer
rules:
- apiGroups: ["mysql.example.com"]
  resources: ["mysqlclusters"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["mysql.example.com"]
  resources: ["mysqlclusters/status"]
  verbs: ["get"]

---
# 2. ClusterRole 允许管理 CRD
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: mysqlcluster-admin
rules:
- apiGroups: ["mysql.example.com"]
  resources: ["mysqlclusters"]
  verbs: ["*"]
- apiGroups: ["mysql.example.com"]
  resources: ["mysqlclusters/status", "mysqlclusters/scale"]
  verbs: ["*"]
- apiGroups: [""]
  resources: ["pods", "services", "configmaps", "secrets", "persistentvolumeclaims"]
  verbs: ["*"]
```

### 6.3 Controller 编写骨架

```go
// controllers/mysqlcluster_controller.go
package controllers

import (
   "context"
    "fmt"
    "time"

    "k8s.io/apimachinery/pkg/runtime"
    ctrl "sigs.k8s.io/controller-runtime"
    "sigs.k8s.io/controller-runtime/pkg/client"
    "sigs.k8s.io/controller-runtime/pkg/log"

    mysqlv1 "github.com/example/mysql-operator/api/v1"
    "github.com/example/mysql-operator/pkg/constants"
)

type MySQLClusterReconciler struct {
    client.Client
    Scheme *runtime.Scheme
}

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
    if !controllerutil.ContainsFinalizer(mc, constants.MySQLClusterFinalizer) {
        controllerutil.AddFinalizer(mc, constants.MySQLClusterFinalizer)
        return ctrl.Result{}, r.Update(ctx, mc)
    }

    // 4. 业务 reconcile 逻辑
    return r.reconcileNormal(ctx, mc)
}

func (r *MySQLClusterReconciler) reconcileNormal(ctx context.Context, mc *mysqlv1.MySQLCluster) (ctrl.Result, error) {
    // 创建 StatefulSet
    // 创建 Service
    // 创建 Secret
    // 更新 status

    mc.Status.Phase = "Running"
    mc.Status.ReadyReplicas = mc.Spec.Replicas
    if err := r.Status().Update(ctx, mc); err != nil {
        return ctrl.Result{}, err
    }

    return ctrl.Result{RequeueAfter: 30 * time.Second}, nil
}

// SetupWithManager 注册 Controller
func (r *MySQLClusterReconciler) SetupWithManager(mgr ctrl.Manager) error {
    return ctrl.NewControllerManagedBy(mgr).
        For(&mysqlv1.MySQLCluster{}).
        WithOptions(controller.Options{MaxConcurrentReconciles: 3}).
        Complete(r)
}
```

---

## 七、CRD 设计原则

### 7.1 API 设计原则

```text
1. 声明式而非命令式
   - spec 描述期望状态
   - status 描述实际状态
   - 避免在 spec 中放置执行命令

2. 业务域独立
   - group 反映业务领域
   - 单个 group 内部高内聚
   - 多个 group 间低耦合

3. 向后兼容
   - 增加新字段用 optional
   - 避免重命名字段
   - 通过版本升级演进

4. 字段命名一致
   - spec/status/conditions 命名规范
   - 与 K8s 内置资源对齐
```

### 7.2 Spec vs Status 设计

```yaml
spec:                    # 用户写入（期望状态）
  replicas: 3            # 期望副本数
  image: mysql:8.0        # 期望镜像
  storage: 100Gi         # 期望存储

status:                  # Controller 写入（实际状态）
  phase: Running         # 当前阶段
  readyReplicas: 3       # 实际就绪副本
  conditions:            # 详细状态
  - type: Ready
    status: "True"
    reason: AllPodsReady
```

### 7.3 命名规范

```text
字段命名：
  - 使用 camelCase（K8s 惯例）
  - 复数形式表示列表（如 replicas, items）
  - Boolean 用前缀（isReady, hasStorage）
  - 时间戳用 suffix（creationTimestamp, lastUpdated）
  
避免：
  - 下划线（K8s 内部字段才用）
  - 缩写（用 storageClass 而非 storClass）
  - 模糊命名（如 data, info）
```

---

## 八、CRD 调试与最佳实践

### 8.1 调试 CRD

```bash
# 1. 查看 CRD 注册情况
kubectl get crd | grep example.com

# 2. 查看 CR 实例
kubectl get mysqlcluster -A
kubectl describe mysqlcluster my-db

# 3. 查看 CRD 定义
kubectl get crd mysqlclusters.mysql.example.com -o yaml

# 4. 验证 schema（如果怀疑）
kubectl get mysqlcluster my-db -o json | jq .

# 5. 触发 reconcile
# 加上 annotation 强制 reconcile
kubectl annotate mysqlcluster my-db force-reconcile=$(date +%s)
```

### 8.2 常见错误

```text
错误 1: CR 创建后立即消失
原因: admission webhook 拒绝 / 验证失败
排查: kubectl describe crd 查看事件

错误 2: status 字段不更新
原因: 没有声明 status 子资源 / RBAC 权限不足
排查: 检查 spec.subresources.status 是否设置

错误 3: 字段保存丢失
原因: 字段没在 schema 中声明
排查: 重新生成 CRD

错误 4: 字段类型报错
原因: 类型不匹配
排查: kubectl get crd -o yaml 查看 OpenAPI v3 schema
```

### 8.3 最佳实践速记

```text
1. 必填字段标记 required
2. 列表项提供 type + items
3. 枚举使用 enum 约束
4. 数值使用 minimum/maximum
5. 字符串使用 minLength + pattern
6. 状态使用 conditions 数组
7. 关键操作使用 finalizers
8. subresources 启用 status
9. CEL 验证放在 x-kubernetes-validations
10. additionalPrinterColumns 显示关键字段
```

---

## 九、参考资源

```text
- K8s 官方文档: https://kubernetes.io/docs/tasks/extend-kubernetes/custom-resources/custom-resource-definitions/
- OpenAPI v3 规范: https://swagger.io/specification/
- CEL 规范: https://github.com/google/cel-go
- kubebuilder 教程: https://book.kubebuilder.io/
- Operator SDK: https://sdk.operatorframework.io/
- controller-runtime: https://github.com/kubernetes-sigs/controller-runtime
- CRD 示例库: https://github.com/kubernetes-sigs/kubebuilder/tree/master/docs/book/src
```

## 速记卡

- **CRD** = K8s API 扩展
- **spec** = 期望状态（用户写）
- **status** = 实际状态（Controller 写）
- **conditions** = 详细状态数组
- **finalizer** = 清理钩子
- **subresources** = status / scale
- **conversion** = 多版本转换
- **validation** = OpenAPI v3 / CEL
- **shortNames** = kubectl 别名

```bash
apply CRD → kubectl get cr <资源>
kubectl get mysqlcluster -A  ← 像内置资源
```