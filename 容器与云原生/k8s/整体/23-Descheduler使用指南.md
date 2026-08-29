# K8s Descheduler 使用指南

> 本章系统讲解 K8s Descheduler 的原理、策略、配置与实战场景。

## 一、为什么需要 Descheduler

### 1.1 K8s 默认调度的局限

```text
K8s 默认 scheduler 的特点：
  - Pod 创建时调度一次
  - 一旦调度，不会重新评估
  - 不主动重新平衡

  问题场景：
    1. 节点加入后，Pod 不会自动迁移
    2. 节点移除后，Pod 不会自动重调度
    3. 节点不均衡（如 node1 满，node2 空）
    4. 资源碎片化（无法合并到少数节点）
    5. PodAntiAffinity 失效（重新评估后需要迁移）
    6. 节点维护时 Pod 无法自动疏散
```

### 1.2 真实场景示例

```text
场景 1：节点宕机恢复
  现象：node1 恢复后，新 Pod 仍然在 node2/node3
  问题：node1 长期空闲，资源浪费
  解决：Descheduler 主动重新平衡

场景 2：新节点加入
  现象：3 节点扩到 5 节点
  问题：Pod 仍挤在原 3 个节点
  解决：Descheduler 主动重平衡到 5 节点

场景 3：节点维护
  现象：node2 需要升级
  问题：手动逐个 evict Pod
  解决：Descheduler 自动驱逐到其他节点

场景 4：镜像升级
  现象：所有 Pod 用旧镜像
  问题：滚动升级只能串行
  解决：Descheduler 驱逐所有 Pod → 滚动升级
```

### 1.3 Descheduler 解决的核心问题

```text
Descheduler = K8s 的重调度器
  - 定期扫描 Pod
  - 找出"应该重调度"的 Pod
  - 安全驱逐（Evict）
  - 触发 ReplicaSet 重新调度
  - 达到重新平衡目的

  与 K8s 默认 scheduler 的区别：
  ┌─────────────────┬────────────────────┐
  │  默认 Scheduler  │  Descheduler       │
  ├─────────────────┼────────────────────┤
  │  Pod 创建时调度  │  已有 Pod 重调度   │
  │  一次性决策      │  周期性重新评估   │
  │  接受请求时      │  主动驱逐并重调度  │
  │  不重调度已调度  │  持续优化集群状态  │
  └─────────────────┴────────────────────┘
```

---

## 二、Descheduler 原理

### 2.1 核心架构

```text
Descheduler 架构：

  ┌──────────────────────────────────────────────┐
  │  Descheduler Pod（kube-system）              │
  │                                              │
  │  ┌──────────────────────────┐              │
  │  │  Scheduler                │              │
  │  │  - 定期扫描集群          │              │
  │  │  - 收集节点信息          │              │
  │  │  - 收集 Pod 信息          │              │
  │  │  - 评估策略              │              │
  │  │  - 找出待驱逐 Pod       │              │
  │  └──────────────────────────┘              │
  │                  │                            │
  │                  ↓                            │
  │  ┌──────────────────────────┐              │
  │  │  Evictor                 │              │
  │  │  - 安全驱逐 Pod          │              │
  │  │  - 遵守 PDB              │              │
  │  │  - 触发 ReplicaSet 重调度│              │
  │  └──────────────────────────┘              │
  └──────────────────────────────┘
```

### 2.2 工作流程

```text
Descheduler 调度循环（默认 10 秒一次）：

  T0：定时器触发
  T1：列出所有节点
      - 节点列表、节点状态、节点资源
  T2：列出所有 Pod
      - 按 namespace、label 过滤
  T3：按策略评估
      - 应用所有启用策略
      - 计算每个 Pod 是否需要驱逐
  T4：决定驱逐
      - 模拟驱逐（不实际执行）
      - 确认符合 PDB
      - 排序驱逐列表
  T5：执行驱逐
      - 逐个驱逐（按优先级）
      - 调用 K8s API
      - K8s 重新调度（ReplicaSet 重建）
  T6：等待下一轮
```

### 2.3 与 K8s 组件关系

```text
Descheduler 与其他组件的交互：

  ┌────────────────────────────────────────┐
  │  K8s API Server                         │
  │  - Descheduler 通过 client-go 调用     │
  │  - 列出节点、Pod、PDB 等资源          │
  │  - 调用 Evict API                     │
  └──────────────┬─────────────────────────┘
                 │ HTTP
  ┌──────────────▼─────────────────────────┐
  │  Descheduler                           │
  │  - 读：get nodes, pods, pdb           │
  │  - 写：create Eviction               │
  │  - 不写 Scheduler                     │
  └─────────────────────────────────────────┘

  重要：
  - Descheduler 不替代 Scheduler
  - Descheduler 只驱逐 Pod
  - Pod 重建由 Deployment/ReplicaSet 处理
  - Scheduler 重新调度新 Pod
```

### 2.4 关键概念

```text
Eviction API：
  - K8s 1.22+ 引入
  - 取代 1.22 之前的 Pod Eviction Policy
  - 支持 PDB 检查
  - 支持 Grace Period
  - 是 Descheduler 调用的 API

PodDisruptionBudget（PDB）：
  - 限制同时驱逐的 Pod 数
  - minAvailable: 2（至少 2 个可用）
  - maxUnavailable: 1（最多 1 个不可用）
  - Descheduler 必须遵守 PDB
  - 违反 PDB 会跳过驱逐

Grace Period（宽限期）：
  - 驱逐时 Pod 的优雅关闭时间
  - 默认 30 秒
  - Descheduler 使用 0 秒（不优雅）
  - 与 PDB 冲突时回退

模拟模式（Dry Run）：
  - 列出将要驱逐的 Pod
  - 不实际驱逐
  - 用于测试和调试
```

---

## 三、部署安装

### 3.1 Helm 安装（推荐）

```bash
# 添加 Helm 仓库
helm repo add descheduler https://kubernetes-sigs.github.io/descheduler-helm
helm repo update

# 安装（默认策略）
helm install descheduler descheduler/descheduler \
  --namespace kube-system \
  --create-namespace \
  --set leaderElection.enabled=true

# 安装（自定义策略）
helm install descheduler descheduler/descheduler \
  --namespace kube-system \
  --create-namespace \
  --values descheduler-values.yaml
```

### 3.2 完整 values.yaml

```yaml
# descheduler-values.yaml
image:
  repository: registry.k8s.io/descheduler/descheduler
  tag: v0.29.1
  pullPolicy: IfNotPresent

replicas: 1
leaderElection:
  enabled: true
  # 选举命名空间（必须）
  namespace: kube-system
  # 租约时长
  leaseDuration: 15s
  renewDeadline: 10s
  retryPeriod: 5s

# 资源限制
resources:
  requests:
    cpu: 100m
    memory: 100Mi
  limits:
    cpu: 1000m
    memory: 500Mi

# 调度策略（核心）
profiles:
- name: default
  # 是否在节点故障时驱逐（生产建议关）
  disablePreemption: false
  # 调度间隔
  interval: 10s
  # 命名空间白名单
  namespaces:
    exclude:
    - kube-system
    - default
  # 排除系统 Pod
  excludeRef:
    - apiVersion: apps/v1
      kind: Deployment
      name: coredns
    - apiVersion: policy/v1
      kind: PodDisruptionBudget
  # 资源阈值
  resourceThresholds:
    cpu: 20
    memory: 25
    pods: 20
  # 启用的策略
  pluginConfig:
  - name: RemoveDuplicates
    enabled: true
    params:
      removeDuplicates:
        namespaces:
          exclude: []
        labelSelector:
          matchLabels: {}
  - name: RemovePodsViolatingInterPodAntiAffinity
    enabled: true
  - name: RemovePodsViolatingNodeAffinity
    enabled: true
    params:
      nodeAffinityType:
      - required
  - name: RemovePodsViolatingNodeTaints
    enabled: true
    params:
      labelSelector:
        matchLabels: {}
  - name: RemovePodsViolatingTopologySpreadConstraint
    enabled: true
  - name: RemovePodsViolatingMaxPodsPerNode
    enabled: true
    params:
      maxPodsPerNode: 10
  - name: RemovePodsViolatingSchedulingPolicy
    enabled: false
  - name: LowNodeUtilization
    enabled: true
    params:
      thresholds:
        cpu: 20
        memory: 25
      targetThresholds:
        cpu: 50
        memory: 50
  - name: RemoveFailedPods
    enabled: true
    params:
      failingPodsThreshold:
        - 1
        - 3
      intervals:
        - 1m
        - 5m
        - 30m
  - name: EvictDuplicatePods
    enabled: true
```

### 3.3 Kustomize 安装

```yaml
# kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
- github.com/kubernetes-sigs/descheduler/deploy/manifests/base?ref=v0.29.1

patches:
- target:
    group: apps
    version: v1
    kind: Deployment
    name: descheduler
  path: patch-replicas.yaml
- target:
    group: apps
    version: v1
    kind: Deployment
    name: descheduler
  path: patch-config.yaml
```

```yaml
# patch-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: descheduler
data:
  policy.yaml: |
    apiVersion: descheduler/v1alpha2
    kind: DeschedulerPolicy
    profiles:
    - name: default
      plugins:
        removeDuplicates:
          enabled: true
        removePodsViolatingNodeAffinity:
          enabled: true
        ...
```

### 3.4 验证安装

```bash
# 检查 Pod
kubectl get pod -n kube-system -l app=descheduler
# 输出：
# NAME                           READY   STATUS    RESTARTS   AGE
# descheduler-5d8b97f4cb-xxxxx   1/1     Running   0          1m

# 查看日志
kubectl logs -n kube-system -l app=descheduler -f

# 检查 leader
kubectl get lease -n kube-system descheduler-leader
```

---

## 四、核心策略详解

### 4.1 全部策略

```text
Descheduler 内置策略（v0.29）：

  1. RemoveDuplicates                # 去重
  2. RemovePodsViolatingInterPodAntiAffinity  # 违反反亲和
  3. RemovePodsViolatingNodeAffinity        # 违反节点亲和
  4. RemovePodsViolatingNodeTaints         # 违反污点容忍
  5. RemovePodsViolatingTopologySpreadConstraint  # 违反拓扑分布
  6. RemovePodsViolatingMaxPodsPerNode     # 违反单节点最大数
  7. RemovePodsViolatingSchedulingPolicy   # 自定义策略
  8. LowNodeUtilization                 # 低利用率节点平衡
  9. RemoveFailedPods                   # 驱逐失败 Pod
  10. EvictDuplicatePods                # 去重（eviction API）
```

### 4.2 RemoveDuplicates（去重）

```text
目的：
  同一 Deployment/StatefulSet 的 Pod 副本可能因历史原因
  调度到同一节点上，造成不均衡。
  移除多余的副本，触发重新调度到其他节点。

配置：
  plugins:
    removeDuplicates:
      enabled: true
      params:
        # 可选：限定命名空间
        namespaces:
          exclude:
          - kube-system
        # 可选：限定标签
        labelSelector:
          matchLabels:
            tier: frontend

场景：
  - 3 节点扩到 5 节点，旧 Pod 仍挤在 2 节点
  - 副本未充分分布
```

### 4.3 RemovePodsViolatingInterPodAntiAffinity

```text
目的：
  Pod 的 spec 中定义了 podAntiAffinity（反亲和）
  但实际调度未满足要求
  Descheduler 找出这些 Pod 并驱逐

配置：
  plugins:
    removePodsViolatingInterPodAntiAffinity:
      enabled: true

示例：
  Deployment 定义 podAntiAffinity required
  但有些 Pod 调度到同节点（违反规则）
  → Descheduler 驱逐 → 重新调度
```

### 4.4 RemovePodsViolatingNodeAffinity

```text
目的：
  Pod 定义了 nodeAffinity（节点亲和）
  但实际调度到不符合的节点
  Descheduler 找出并驱逐

配置：
  plugins:
    removePodsViolatingNodeAffinity:
      enabled: true
      params:
        nodeAffinityType:
        - required         # 仅 required 类型
        # - preferred      # preferred 类型也会检查

场景：
  Pod 定义了必须调度到 SSD 节点
  但某次调度到了非 SSD 节点
  → Descheduler 重新调度
```

### 4.5 RemovePodsViolatingNodeTaints

```text
目的：
  节点打了新污点
  但 Pod 没有对应 tolerance
  仍在该节点运行
  Descheduler 驱逐这些 Pod

配置：
  plugins:
    removePodsViolatingNodeTaints:
      enabled: true
      params:
        # 限定特定标签的 Pod
        labelSelector:
          matchLabels:
            app: web

场景：
  - 节点升级时打污点 maintenance=true:NoExecute
  - 但有些 Pod 没用 toleration
  - Descheduler 驱逐这些 Pod
```

### 4.6 RemovePodsViolatingTopologySpreadConstraint

```text
目的：
  Pod 定义了 topologySpreadConstraints（拓扑分布）
  但实际分布不均
  Descheduler 找出来驱逐重调度

配置：
  plugins:
    removePodsViolatingTopologySpreadConstraint:
      enabled: true

场景：
  Pod 定义了 zone 平均分布
  但因节点变化导致分布不均
  → Descheduler 重平衡
```

### 4.7 LowNodeUtilization（低利用率重平衡）

```text
目的：
  集群资源使用不均（部分节点满，部分空）
  Descheduler 找利用率低的节点，驱逐上面部分 Pod
  让它们被调度到利用率低的节点，实现平衡

配置：
  plugins:
    lowNodeUtilization:
      enabled: true
      params:
        # 节点利用率低阈值
        thresholds:
          cpu: 20         # CPU < 20% 视为低
          memory: 25      # 内存 < 25% 视为低
          pods: 20        # Pod 数 < 20% 视为低
        # 目标利用率（驱逐后）
        targetThresholds:
          cpu: 50         # 目标提到 50%
          memory: 50
        # 其他参数
        useDeviationThresholds: true
        # 排除某些节点
        nodeFit: true

场景：
  5 个节点，A/B 满载，C/D/E 空闲
  Descheduler 从 A/B 驱逐部分 Pod
  → ReplicaSet 重建到 C/D/E
  → 资源更均衡
```

### 4.8 RemoveFailedPods

```text
目的：
  清理一直处于 Failed 状态的 Pod
  避免资源浪费

配置：
  plugins:
    removeFailedPods:
      enabled: true
      params:
        # 失败次数阈值（与时间窗口配合）
        failingPodsThreshold:
          - 1              # 至少失败 1 次
          - 3              # 至少失败 3 次
        # 时间窗口
        intervals:
          - 1m            # 1 分钟
          - 5m            # 5 分钟
          - 30m           # 30 分钟

  含义：
    - 在 1m 内失败 1 次：驱逐
    - 在 5m 内失败 3 次：驱逐
    - 在 30m 内失败 5 次：驱逐
```

### 4.9 EvictDuplicatePods

```text
目的：
  通过 eviction API 去重
  与 RemoveDuplicates 区别：
    - RemoveDuplicates：分析节点分布
    - EvictDuplicatePods：基于 PDB 驱逐

配置：
  plugins:
    evictDuplicatePods:
      enabled: true

场景：
  多副本占满资源，主动驱逐让新 Pod 重调度
```

---

## 五、完整配置示例

### 5.1 生产推荐配置

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: descheduler
  namespace: kube-system
data:
  policy.yaml: |
    apiVersion: descheduler/v1alpha2
    kind: DeschedulerPolicy
    profiles:
    - name: default
      # 调度间隔（默认 10s）
      interval: 30s
      
      # 排除系统命名空间
      namespaces:
        exclude:
        - kube-system
        - default
      
      # 排除系统 Pod
      excludeRef:
      - apiVersion: apps/v1
        kind: Deployment
        name: coredns
      - apiVersion: apps/v1
        kind: Deployment
        name: local-path-provisioner
      - apiVersion: policy/v1
        kind: PodDisruptionBudget
      
      # 资源阈值（驱逐前确认）
      resourceThresholds:
        cpu: 30
        memory: 30
        pods: 30
      
      # 启用的策略
      plugins:
        # 1. 节点不均衡时驱逐
        removeDuplicates:
          enabled: true
        
        # 2. 违反反亲和驱逐
        removePodsViolatingInterPodAntiAffinity:
          enabled: true
        
        # 3. 违反节点亲和驱逐
        removePodsViolatingNodeAffinity:
          enabled: true
          params:
            nodeAffinityType:
            - required
        
        # 4. 违反污点驱逐
        removePodsViolatingNodeTaints:
          enabled: true
          params:
            labelSelector:
              matchLabels: {}
        
        # 5. 违反拓扑分布驱逐
        removePodsViolatingTopologySpreadConstraint:
          enabled: true
        
        # 6. 低利用率重平衡
        lowNodeUtilization:
          enabled: true
          params:
            thresholds:
              cpu: 25
              memory: 30
              pods: 30
            targetThresholds:
              cpu: 60
              memory: 60
        
        # 7. 失败 Pod 清理
        removeFailedPods:
          enabled: true
          params:
            failingPodsThreshold:
            - 1
            - 3
            - 5
            intervals:
            - 1m
            - 5m
            - 30m
```

### 5.2 自定义 ConfigMap 部署

```bash
# 1. 完整配置 ConfigMap
cat > descheduler-config.yaml <<'EOF'
apiVersion: v1
kind: ConfigMap
metadata:
  name: descheduler
  namespace: kube-system
data:
  policy.yaml: |
    apiVersion: descheduler/v1alpha2
    kind: DeschedulerPolicy
    profiles:
    - name: default
      interval: 30s
      plugins:
        removeDuplicates:
          enabled: true
        # ... 其他策略
EOF

# 2. 应用
kubectl apply -f descheduler-config.yaml

# 3. 重启 descheduler 让配置生效
kubectl rollout restart deployment/descheduler -n kube-system
```

---

## 六、实战场景

### 6.1 场景 1：新节点加入后重平衡

```text
场景：
  - 集群原本 3 节点
  - 加了一个节点
  - 希望新 Pod 调度到新节点
  - 已有的 Pod 不动（避免影响服务）

  解决：
    - 移除策略 removeDuplicates 不适用（只去重）
    - 移除策略 lowNodeUtilization 适用（找到低利用率节点驱逐）

  操作：
    - 启用 lowNodeUtilization
    - thresholds: cpu: 25（低于 25% 视为低）
    - 启动 descheduler
    - 几小时内重新平衡
```

### 6.2 场景 2：节点维护时主动疏散

```text
场景：
  - node1 需要升级
  - 想主动驱逐上面的 Pod 到其他节点
  - 避免升级时影响业务

  步骤：
    1. 给 node1 打污点
       kubectl taint nodes node1 maintenance=true:NoExecute
    2. Descheduler 自动驱逐无 toleration 的 Pod
    3. 业务 Pod 配置了 tolerationSeconds 优雅迁移
    4. 维护完成后
       kubectl taint nodes node1 maintenance-

  配置：
    plugins:
      removePodsViolatingNodeTaints:
        enabled: true
```

### 6.3 场景 3：镜像更新时批量重启

```text
场景：
  - 所有 Pod 用旧镜像
  - 想批量重启
  - 避免滚动升级的复杂配置

  解决：
    - Descheduler 驱逐所有 Pod
    - ReplicaSet 重新创建新镜像 Pod

  操作：
    1. 标记要被驱逐的 Pod
       kubectl label pods <pod-name> restart=true
    2. Descheduler 配置驱逐指定标签
       plugins:
         removePodsViolatingNodeTaints:
           enabled: true
           params:
             labelSelector:
               matchLabels:
                 restart: "true"
    3. 通过 PDB 触发驱逐
       kubectl delete pod <pod-name> --grace-period=0
```

### 6.4 场景 4：故障节点修复后重平衡

```text
场景：
  - node1 故障后恢复
  - 想把 Pod 从 node2/node3 重新分布到 node1
  - 避免资源浪费

  解决：
    - 启用 lowNodeUtilization
    - 配置目标利用率
    - 自动触发 Pod 重调度

  操作：
    - Descheduler 定期扫描
    - 检测到 node1 利用率 < 阈值
    - 主动驱逐 node2/node3 部分 Pod
    - Pod 重建到 node1
```

### 6.5 场景 5：多团队公平资源分配

```text
场景：
  - 多个团队共享集群
  - 团队 A 占资源多
  - 团队 B 占资源少
  - 希望按比例重新分配

  解决：
    - 启用 lowNodeUtilization
    - 配置目标利用率
    - Descheduler 自动平衡

  配置：
    plugins:
      lowNodeUtilization:
        enabled: true
        params:
          thresholds: {cpu: 40, memory: 50, pods: 40}
          targetThresholds: {cpu: 70, memory: 70}
```

---

## 七、调试与诊断

### 7.1 查看日志

```bash
# 实时日志
kubectl logs -n kube-system -l app=descheduler -f

# 最近 100 行
kubectl logs -n kube-system -l app=descheduler --tail=100

# 详细日志（修改启动参数）
# 在 deployment 中添加 --v=4
```

### 7.2 查看驱逐历史

```bash
# Descheduler 会在 K8s Event 中记录驱逐
kubectl get events -A --field-selector reason=Descheduled | head

# 查看 Pod 的驱逐原因
kubectl describe pod <pod-name> | grep -A 5 "Events"
```

### 7.3 Dry Run 测试

```yaml
# 启用 dry run 模式（不实际驱逐）
apiVersion: v1
kind: ConfigMap
metadata:
  name: descheduler
  namespace: kube-system
data:
  policy.yaml: |
    apiVersion: descheduler/v1alpha2
    kind: DeschedulerPolicy
    profiles:
    - name: dev
      dryRun: true                # 关键：dry run
      interval: 60s
      plugins:
        removeDuplicates:
          enabled: true
```

```bash
# 查看会驱逐哪些 Pod（dry run 不会实际驱逐）
kubectl logs -n kube-system -l app=descheduler --tail=200 | grep -i evict
```

### 7.4 常见问题

```text
Q1: Descheduler 一直在重启
A1: 检查 ConfigMap 格式
    kubectl get cm descheduler -n kube-system -o yaml
    用 yaml 验证器检查

Q2: Pod 没有被驱逐
A2: 检查是否被 PDB 限制
    kubectl get pdb -A
    检查 excludeRef 是否排除了所有 Pod
    启用 dry run 查看会驱逐哪些

Q3: 驱逐后 Pod 仍然不均衡
A3: 检查策略是否合理
    maxSkew 是否过大
    topologyKey 是否正确
    节点是否有足够资源

Q4: 误驱逐重要 Pod
A4: 严格配置 excludeRef
    使用 PDB 保护
    先 dry run 测试
    启用 graceful shutdown

Q5: 性能问题
A5: 调整 interval 间隔
    减少启用的策略数
    增加 resources.limits
```

---

## 八、最佳实践

### 8.1 部署最佳实践

```text
1. 高可用部署
   - replicas: 2（高可用）
   - leaderElection.enabled: true
   - 防止多实例同时驱逐冲突

2. 资源限制
   - resources.limits 必须设
   - 防止 Descheduler OOMKilled
   - 推荐：cpu: 500m, memory: 500Mi

3. 调度间隔
   - interval: 30s（推荐）
   - 太短：频繁扫描，影响 API Server
   - 太长：不能及时发现不均衡

4. 系统 Pod 排除
   - 必须排除 kube-system
   - 排除关键服务（coredns、监控等）
   - 防止误驱逐导致集群故障
```

### 8.2 策略选择最佳实践

```text
1. 推荐启用
   ✅ removeDuplicates                # 减少冗余
   ✅ removePodsViolatingNodeTaints  # 污点变化响应
   ✅ removeFailedPods               # 清理失败 Pod
   ✅ lowNodeUtilization              # 资源平衡（低风险）

2. 谨慎启用
   ⚠️ removePodsViolatingInterPodAntiAffinity
     （严格反亲和驱逐可能影响服务可用性）
   ⚠️ removePodsViolatingTopologySpreadConstraint
     （频繁驱逐会引发不稳定）

3. 不推荐
   ❌ removePodsViolatingNodeAffinity with required
     （修改 node 标签会触发大量驱逐）
```

### 8.3 安全防护最佳实践

```text
1. PodDisruptionBudget 必配
   - 关键服务必须配置 PDB
   - minAvailable: N
   - maxUnavailable: N
   - 否则 Descheduler 可能驱逐过多 Pod

2. excludeRef 必配
   - 排除所有系统级 Pod
   - 排除 coredns、kube-proxy、ingress 等
   - 排除重要业务 Pod

3. dry run 测试
   - 新策略上线前必须 dry run
   - 观察一周确认无问题
   - 再切到正式执行

4. 灰度策略
   - 先小范围启用（按 namespace）
   - 观察驱逐行为
   - 再全局启用
```

### 8.4 业务部署示例

```yaml
# 1. 应用 PDB（关键）
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: web-pdb
spec:
  minAvailable: 2          # 至少 2 个可用
  selector:
    matchLabels:
      app: web
---
# 2. 应用配置
apiVersion: v1
kind: ConfigMap
metadata:
  name: descheduler
  namespace: kube-system
data:
  policy.yaml: |
    apiVersion: descheduler/v1alpha2
    kind: DeschedulerPolicy
    profiles:
    - name: default
      interval: 30s
      namespaces:
        exclude:
        - kube-system
      excludeRef:
      - apiVersion: apps/v1
        kind: Deployment
        name: coredns
      - apiVersion: policy/v1
        kind: PodDisruptionBudget
      plugins:
        removeDuplicates:
          enabled: true
        removePodsViolatingNodeTaints:
          enabled: true
        lowNodeUtilization:
          enabled: true
          params:
            thresholds:
              cpu: 30
              memory: 30
              pods: 30
            targetThresholds:
              cpu: 60
              memory: 60
        removeFailedPods:
          enabled: true
          params:
            failingPodsThreshold: [1, 3]
            intervals: [1m, 5m, 30m]
```

---

## 九、与其他 K8s 组件对比

### 9.1 Descheduler vs Scheduler

| 维度 | Scheduler | Descheduler |
|------|------------|-------------|
| 作用时机 | Pod 创建时 | 已运行 Pod |
| 触发方式 | Pod Spec + 资源变化 | 定时器 |
| 决策依据 | 资源 + 约束 | 集群状态 |
| 输出 | 创建 Pod | Evict Pod |
| 影响范围 | 新 Pod | 已有 Pod |
| 频率 | 持续 | 周期（默认 10s） |
| 是否阻塞 | 阻塞 Pod 创建 | 不阻塞 |

### 9.2 Descheduler vs Cluster Autoscaler

| 维度 | Descheduler | Cluster Autoscaler |
|------|-------------|---------------------|
| 作用对象 | 已有 Pod | 节点 |
| 资源感知 | 节点利用率 | 整体资源 |
| 操作 | 驱逐 Pod | 增减节点 |
| 触发条件 | 不均衡 | 资源不够 |
| 时延 | 周期（10s+） | 较慢（30s+） |
| 配合 | 经常一起使用 | 经常一起使用 |

### 9.3 Descheduler vs VPA

| 维度 | Descheduler | VPA |
|------|-------------|-----|
| 作用对象 | Pod 位置 | Pod 资源 |
| 操作 | 驱逐 + 重调度 | 修改 requests/limits |
| 副作用 | 短暂中断 | 无中断（推荐） |
| 冲突 | 与 VPA 可能冲突 | 一般不冲突 |
| 配合 | 关闭 VPA eviction mode | 使用 VPA 而非 Descheduler |

---

## 十、核心要点速记

### Descheduler 三大特性

```
1. 周期性重调度
   - 定时扫描（默认 10s）
   - 自动驱逐
   - 触发 ReplicaSet 重建

2. 多种策略组合
   - 内置 10+ 策略
   - 灵活配置
   - 自定义排除规则

3. 持续优化
   - 主动平衡集群
   - 解决资源碎片化
   - 响应节点变化
```

### 核心配置速记

```yaml
apiVersion: descheduler/v1alpha2
kind: DeschedulerPolicy
profiles:
- name: default
  interval: 30s                    # 调度间隔
  namespaces:
    exclude: [kube-system]         # 排除命名空间
  excludeRef:                     # 排除 Pod
  - kind: Deployment
    name: coredns
  resourceThresholds:              # 资源阈值
    cpu: 30
    memory: 30
    pods: 30
  plugins:                        # 启用的策略
    removeDuplicates: {enabled: true}
    removePodsViolatingNodeTaints: {enabled: true}
    lowNodeUtilization: {enabled: true}
    removeFailedPods: {enabled: true}
```

### 8 大内置策略速记

```
1. RemoveDuplicates                    # 去重
2. RemovePodsViolatingInterPodAntiAffinity  # 反亲和
3. RemovePodsViolatingNodeAffinity    # 节点亲和
4. RemovePodsViolatingNodeTaints      # 污点
5. RemovePodsViolatingTopologySpreadConstraint  # 拓扑分布
6. RemovePodsViolatingMaxPodsPerNode  # 单节点最大数
7. RemovePodsViolatingSchedulingPolicy  # 自定义
8. LowNodeUtilization                # 资源平衡
9. RemoveFailedPods                  # 失败 Pod
10. EvictDuplicatePods               # 去重（eviction）
```

### 关键速记

```
- Descheduler = K8s 重调度器
- 通过 Eviction API 驱逐
- 必须遵守 PodDisruptionBudget
- 通过 leaderElection HA（必须）
- 必须排除系统 Pod（kube-system）
- 默认 interval: 10s（推荐 30s）
- 高可用 replicas: 2
- 生产必配 excludeRef
- 新策略上线必 dry run
```

### 一句话总结

```
Descheduler = K8s 集群重平衡器
核心：周期扫描 + 策略评估 + 安全驱逐 + 重新调度
关键：executorRef（排除系统） + PDB（防误驱） + dry run（防误配）
配合：与 K8s Scheduler、Cluster Autoscaler 协同
最佳：低风险启用 RemoveDuplicates、RemoveFailedPods、LowNodeUtilization
```