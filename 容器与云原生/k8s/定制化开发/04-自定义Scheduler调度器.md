# 自定义 Scheduler（Custom Scheduler）

## 一、为什么要做自定义 Scheduler

### 1.1 业务背景

```text
K8s 默认 Scheduler 的局限：
  - 单 FIFO 队列
  - 资源调度为主（CPU/内存）
  - 不感知业务特征

业务场景需要更智能的调度：
  - AI 训练任务需要 GPU 节点，调度到有 GPU 的节点
  - 大数据任务需要高 IO 节点
  - 离线任务调度到空闲资源
  - 在线任务分散到不同节点（高可用）
  - 同业务 Pod 调度到同一节点（降低网络延迟）
  - 同业务 Pod 分散到不同节点（高可用）
  - 特定团队的资源隔离
  - Spot 实例的优先级调度
  - 自定义优先级（业务 VIP）
```

### 1.2 自定义 Scheduler 核心价值

```text
1. 业务感知调度
   - GPU/内存密集型任务调度到合适节点
   - 同业务 Pod 同节点（网络优化）
   - 同业务 Pod 异节点（高可用）

2. 多调度器并行
   - 多个 Scheduler 各管一类负载
   - AI Scheduler、大数据 Scheduler、在线 Scheduler
   - 避免单点

3. 调度策略灵活
   - 自定义打分算法
   - 自定义预选/优选
   - 业务优先级（VIP）

4. 资源优化
   - 离线任务调度到空闲资源
   - 在线任务优先资源
   - 资源利用率最大化
```

### 1.3 适用场景

```text
适合自定义 Scheduler 的场景：
  ✅ 异构工作负载（AI、大数据、在线、离线）
  ✅ GPU/特殊硬件调度
  ✅ 业务相关的调度策略（同业务同节点）
  ✅ 多团队资源隔离
  ✅ 高级调度需求（Spot、抢占等）

不适合：
  ❌ 简单资源调度（用默认 Scheduler）
  ❌ 单一负载类型（无需分类）
  ❌ K8s 新手（先熟悉默认）
```

---

## 二、Scheduler 架构

### 2.1 K8s 默认 Scheduler 架构

```text
┌─────────────────────────────────────────────┐
│           Scheduler 整体架构                  │
│                                              │
│  ┌──────────────────────────────────────┐  │
│  │         Scheduler Cache              │  │
│  │  - 缓存 Node 状态                     │  │
│  │  - 缓存 Pod 信息                       │  │
│  └──────────────┬───────────────────────┘  │
│                 │                              │
│  ┌──────────────▼───────────────────────┐  │
│  │           Scheduling Queue           │  │
│  │  - unschedulable Pod 队列             │  │
│  └──────────────┬───────────────────────┘  │
│                 │                              │
│  ┌──────────────▼───────────────────────┐  │
│  │        Scheduler Algorithm            │  │
│  │  1. PreFilter（前置过滤）             │  │
│  │  2. Filter（节点过滤）              │  │
│  │  3. PostFilter（过滤后处理）         │  │
│  │  4. PreScore（预打分）               │  │
│  │  5. Score（节点打分）                 │  │
│  │  6. NormalizeScore（归一化）          │  │
│  │  7. Reserve（预留）                   │  │
│  │  8. Permit（许可）                    │  │
│  │  9. PreBind（预绑定）                 │  │
│  │  10. Bind（绑定）                    │  │
│  │  11. PostBind（绑定后）               │  │
│  └──────────────────────────────────────┘  │
│                                              │
│  多 Scheduler 并行（SchedulerSharding）：    │
│  ┌──────┐ ┌──────┐ ┌──────┐                  │
│  │ S-1  │ │ S-2  │ │ S-3  │                  │
│  └──────┘ └──────┘ └──────┘                  │
│  默认 S-0（处理未分片）                       │
└─────────────────────────────────────────────┘
```

### 2.2 Scheduler 扩展点

```text
Scheduler 框架提供 11 个扩展点：

  PreEnqueue  ←─────────────────  Pod 进入队列前
       ↓
    Filter  ←──────────────────  节点过滤（排除）
       ↓
  PostFilter  ←────────────────  过滤后无节点
       ↓
   PreScore  ←──────────────────  打分前
       ↓
     Score  ←───────────────────  节点打分
       ↓
 NormalizeScore  ←─────────────  归一化
       ↓
     Reserve  ←──────────────────  资源预留
       ↓
     Permit  ←───────────────────  最终决定
       ↓
   PreBind  ←────────────────────  绑定前
       ↓
     Bind  ←─────────────────────  绑定
       ↓
  PostBind  ←───────────────────  绑定后

  还可以实现：
  - EnqueueExtension（控制入队）
  - QueueingHints（队列提示）
```

### 2.3 多 Scheduler 架构（SchedulerSharding）

```text
K8s v1.20+ 多 Scheduler 并行：

  ┌─────────────────────────────────────────────┐
  │            API Server                        │
  └──────────────┬──────────────────────────────┘
                 │
       ┌─────────┼─────────┐
       ↓         ↓         ↓
  ┌──────┐  ┌──────┐  ┌──────┐
  │ S-1  │  │ S-2  │  │ S-3  │
  │ns:a,b│  │ns:c,d│  │默认  │
  └──────┘  └──────┘  └──────┘

  SchedulerSharding 配置：
    - 给 Pod 分配 Scheduler
    - 通过 SchedulerName 字段
    - 多个 Scheduler 副本各管一类 Pod
```

---

## 三、Scheduler Profile（多策略并存）

### 3.1 什么是 Scheduler Profile

```text
K8s v1.18+ 引入 Scheduler Profile：
  - 同一集群可运行多种调度策略
  - Pod 通过 spec.schedulerName 选择 profile
  - 每个 Profile 是独立插件组合

  示例：
    - default-scheduler：内置
    - high-priority-scheduler：高优先级
    - spot-scheduler：Spot 实例调度
    - gpu-scheduler：GPU 节点调度
```

### 3.2 配置 Scheduler Profile

```yaml
# /etc/kubernetes/scheduler-config.yaml
apiVersion: kubescheduler.config.k8s.io/v1
kind: KubeSchedulerConfiguration
profiles:
- schedulerName: default-scheduler
  plugins:
    score:
      enabled:
      - name: NodeResourcesFit
      - name: NodeAffinity
      - name: PodTopologySpread
      - name: ImageLocality
      disabled:
      - name: NodeResourcesBalancedAllocation
    reserve:
      enabled:
      - name: VolumeBinding
- schedulerName: gpu-scheduler
  plugins:
    filter:
      enabled:
      - name: NodeResourcesFit
      - name: NodeAffinity
      - name: NodeSelector
      - name: PodTopologySpread
    score:
      enabled:
      - name: NodeResourcesFit
      - name: NodeAffinity
      - name: TaintToleration
      - name: PodTopologySpread
```

### 3.3 Pod 指定 Scheduler

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: ai-training-job
spec:
  schedulerName: gpu-scheduler    # 使用自定义 Scheduler
  nodeSelector:
    hardware-type: gpu
  containers:
  - name: trainer
    image: tensorflow/tensorflow:2.13
    resources:
      limits:
        nvidia.com/gpu: 1
```

---

## 四、自定义 Scheduler 完整开发

### 4.1 项目结构

```text
my-scheduler/
├── cmd/
│   └── scheduler/
│       └── main.go              # Scheduler 入口
├── pkg/
│   ├── scheduler/
│   │   ├── scheduler.go         # Scheduler 主体
│   │   ├── algorithm.go         # 调度算法
│   │   ├── predicate.go        # 预选（Filter）
│   │   ├── priority.go         # 优选（Score）
│   │   └── binding.go          # 绑定逻辑
│   └── cache/
│       └── cache.go              # 节点/Pod 缓存
├── deploy/
│   ├── rbac.yaml                 # RBAC 权限
│   ├── deployment.yaml           # Scheduler 部署
│   └── scheduler-config.yaml     # Scheduler 配置
├── Dockerfile
├── Makefile
└── go.mod
```

### 4.2 RBAC 配置

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: my-scheduler
  namespace: kube-system
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: system:kube-scheduler
rules:
- apiGroups: [""]
  resources: ["pods", "endpoints", "services"]
  verbs: ["create", "delete", "get", "list", "watch"]
- apiGroups: [""]
  resources: ["nodes"]
  verbs: ["get", "list", "watch"]
- apiGroups: [""]
  resources: ["pods/binding", "pods/status"]
  verbs: ["get", "patch", "update"]
- apiGroups: [""]
  resources: ["configmaps", "events"]
  verbs: ["get", "list", "watch", "create", "update", "patch"]
- apiGroups: ["coordination.k8s.io"]
  resources: ["leases"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
- apiGroups: ["events.k8s.io"]
  resources: ["events"]
  verbs: ["create", "patch", "update"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: my-scheduler
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: system:kube-scheduler
subjects:
- kind: ServiceAccount
  name: my-scheduler
  namespace: kube-system
```

### 4.3 Scheduler 主体（scheduler.go）

```go
// pkg/scheduler/scheduler.go
package scheduler

import (
    "context"
    "fmt"
    "time"

    "k8s.io/apimachinery/pkg/api/errors"
    "k8s.io/apimachinery/pkg/types"
    utilruntime "k8s.io/apimachinery/pkg/util/runtime"
    "k8s.io/client-go/informers"
    "k8s.io/client-go/kubernetes"
    "k8s.io/client-go/rest"
    "k8s.io/klog/v2"
)

type Scheduler struct {
    clientset   kubernetes.Interface
    informerFactory informers.SharedInformerFactory
    podQueue   *PodQueue
    schedulerName string
}

func NewScheduler(
    clientset kubernetes.Interface,
    schedulerName string,
) *Scheduler {
    factory := informers.NewSharedInformerFactory(clientset, 0)
    
    s := &Scheduler{
        clientset:   clientset,
        informerFactory: factory,
        podQueue:   NewPodQueue(schedulerName),
        schedulerName: schedulerName,
    }
    
    // 启动 Informer
    podInformer := factory.Core().V1().Pods().Informer()
    podInformer.AddEventHandler(cache.ResourceEventHandlerFuncs{
        AddFunc:    s.onPodAdd,
        UpdateFunc: s.onPodUpdate,
    })
    
    return s
}

// Run 启动 Scheduler
func (s *Scheduler) Run(ctx context.Context) error {
    s.informerFactory.Start(ctx.Done())
    s.informerFactory.WaitForCacheSync(ctx.Done())
    
    // 启动多个 Worker 并发调度
    workers := 5
    for i := 0; i < workers; i++ {
        go wait.UntilWithContext(ctx, s.scheduleOne, time.Second)
    }
    
    <-ctx.Done()
    return nil
}

// scheduleOne 调度一个 Pod
func (s *Scheduler) scheduleOne(ctx context.Context) {
    pod, err := s.podQueue.Pop()
    if err != nil {
        return
    }
    
    klog.InfoS("Scheduling pod", "pod", klog.KObj(pod))
    
    // 1. 预选节点（Filter）
    nodes, err := s.findNodesThatFit(pod)
    if err != nil {
        klog.ErrorS(err, "Failed to find nodes")
        return
    }
    
    if len(nodes) == 0 {
        klog.InfoS("No nodes fit", "pod", klog.KObj(pod))
        return
    }
    
    // 2. 优选节点（Score）
    scoredNodes := s.prioritizeNodes(pod, nodes)
    
    // 3. 选择最优节点
    selected := scoredNodes[0]
    
    // 4. 绑定
    err = s.bind(ctx, pod, selected)
    if err != nil {
        klog.ErrorS(err, "Failed to bind")
        return
    }
    
    // 5. 从队列移除
    s.podQueue.Remove(pod)
}
```

### 4.4 预选 Filter（algorithm.go）

```go
// pkg/scheduler/algorithm.go
package scheduler

import (
    "context"
    
    "k8s.io/api/core/v1"
)

// findNodesThatFit 预选节点（Filter）
func (s *Scheduler) findNodesThatFit(pod *corev1.Pod) ([]*corev1.Node, error) {
    allNodes, err := s.nodeLister.List(labels.Everything())
    if err != nil {
        return nil, err
    }
    
    feasible := []*corev1.Node{}
    for _, node := range allNodes {
        if s.nodeMatches(pod, node) {
            feasible = append(feasible, node)
        }
    }
    return feasible, nil
}

// nodeMatches 节点是否满足 Pod 要求
func (s *Scheduler) nodeMatches(pod *corev1.Pod, node *corev1.Node) bool {
    // 1. 检查节点选择器
    if !podFitsNodeSelector(pod, node) {
        return false
    }
    
    // 2. 检查污点容忍
    if !podToleratesTaints(pod, node) {
        return false
    }
    
    // 3. 检查资源可用性
    if !hasEnoughResources(pod, node) {
        return false
    }
    
    // 4. 检查节点亲和性
    if !podMatchesNodeAffinity(pod, node) {
        return false
    }
    
    // 5. 自定义业务规则
    if !customBusinessRules(pod, node) {
        return false
    }
    
    return true
}

// hasEnoughResources 检查资源是否足够
func hasEnoughResources(pod *corev1.Pod, node *corev1.Node) bool {
    allocatable := node.Status.Allocatable
    
    // 计算所有容器的总需求
    totalCPU := resource.NewQuantity(0, resource.DecimalSI)
    totalMem := resource.NewQuantity(0, resource.BinarySI)
    
    for _, container := range pod.Spec.Containers {
        if cpu, ok := container.Resources.Requests[corev1.ResourceCPU]; ok {
            totalCPU.Add(cpu)
        }
        if mem, ok := container.Resources.Requests[corev1.ResourceMemory]; ok {
            totalMem.Add(mem)
        }
    }
    
    return allocatable.Cpu().Cmp(*totalCPU) >= 0 &&
           allocatable.Memory().Cmp(*totalMem) >= 0
}

// customBusinessRules 自定义业务规则
func customBusinessRules(pod *corev1.Pod, node *corev1.Node) bool {
    // 示例 1：AI 训练任务调度到有 GPU 的节点
    if isAITrainingPod(pod) && !hasGPU(node) {
        return false
    }
    
    // 示例 2：高敏感任务调度到专属节点
    if isHighSecurityPod(pod) && !isSecurityHardened(node) {
        return false
    }
    
    // 示例 3：避免调度到不健康节点
    if !isNodeHealthy(node) {
        return false
    }
    
    return true
}
```

### 4.5 优选 Score（priority.go）

```go
// pkg/scheduler/priority.go
package scheduler

import (
    "k8s.io/api/core/v1"
)

// prioritizeNodes 优选节点
func (s *Scheduler) prioritizeNodes(
    pod *corev1.Pod, nodes []*corev1.Node,
) []ScoredNode {
    scored := make([]ScoredNode, len(nodes))
    
    for i, node := range nodes {
        score := s.calculateScore(pod, node)
        scored[i] = ScoredNode{
            Node:  node,
            Score: score,
        }
    }
    
    // 排序（从高到低）
    sort.Slice(scored, func(i, j int) bool {
        return scored[i].Score > scored[j].Score
    })
    
    return scored
}

// calculateScore 计算节点分数
func (s *Scheduler) calculateScore(pod *corev1.Pod, node *corev1.Node) int64 {
    var score int64 = 100  // 基础分
    
    // 1. 资源空闲度（空闲越多分越高）
    if cpu := node.Status.Allocatable.Cpu().MilliValue(); cpu > 0 {
        score += cpu / 100  // 每 100m CPU 加 1 分
    }
    
    // 2. 业务感知打分
    score += s.businessScore(pod, node)
    
    // 3. 节点偏好（通过 annotation 或 label）
    if preference, ok := node.Labels["scheduler.preference"]; ok {
        switch preference {
        case "high":
            score += 1000
        case "low":
            score -= 500
        }
    }
    
    // 4. 同业务 Pod 亲和性（同节点）
    if hasPodAffinity(pod, node, "preferred") {
        score += 500
    }
    
    // 5. 同业务 Pod 反亲和性（异节点）
    if hasPodAntiAffinity(pod, node, "preferred") {
        score += 300
    }
    
    return score
}

// businessScore 业务感知打分
func (s *Scheduler) businessScore(pod *corev1.Pod, node *corev1.Node) int64 {
    var score int64 = 0
    
    // AI 训练任务优先调度到 GPU 节点
    if isAITrainingPod(pod) && hasGPU(node) {
        score += 5000
    }
    
    // 大数据任务优先调度到高 IO 节点
    if isBigDataPod(pod) && hasHighIO(node) {
        score += 3000
    }
    
    // 在线任务优先调度到低负载节点
    if isOnlinePod(pod) {
        cpu := node.Status.Allocatable.Cpu().MilliValue()
        if cpu > 4000 {  // 4 核以上
            score += 1000
        }
    }
    
    // 同业务同节点（缓存亲和）
    if sameServiceExists(pod, node) {
        score += 500
    }
    
    return score
}
```

### 4.6 绑定（binding.go）

```go
// pkg/scheduler/binding.go
package scheduler

import (
    "context"
    "fmt"

    "k8s.io/api/core/v1"
    "k8s.io/apimachinery/pkg/api/errors"
    metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

// bind 绑定 Pod 到 Node
func (s *Scheduler) bind(
    ctx context.Context, pod *corev1.Pod, node *corev1.Node,
) error {
    binding := &corev1.Binding{
        ObjectMeta: metav1.ObjectMeta{
            Name:      pod.Name,
            Namespace: pod.Namespace,
            UID:       pod.UID,
        },
        Target: corev1.ObjectReference{
            Kind: "Node",
            Name: node.Name,
        },
    }
    
    err := s.clientset.CoreV1().Pods(pod.Namespace).Bind(ctx, binding, metav1.CreateOptions{})
    if err != nil {
        return fmt.Errorf("bind failed: %v", err)
    }
    
    klog.InfoS("Pod bound", "pod", klog.KObj(pod), "node", node.Name)
    return nil
}
```

### 4.7 部署

```yaml
# deploy/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-scheduler
  namespace: kube-system
  labels:
    app: my-scheduler
spec:
  replicas: 1
  selector:
    matchLabels:
      app: my-scheduler
  template:
    metadata:
      labels:
        app: my-scheduler
    spec:
      serviceAccountName: my-scheduler
      priorityClassName: system-cluster-critical
      containers:
      - name: scheduler
        image: registry.example.com/my-scheduler:v1.0
        command: ["/scheduler", "--config=/etc/kubernetes/scheduler-config.yaml"]
        args:
        - --v=4
        - --leader-elect=true
        - --leader-elect-resource-lock=endpoints
        - --leader-elect-resource-namespace=kube-system
        resources:
          requests:
            cpu: 100m
            memory: 64Mi
          limits:
            cpu: 500m
            memory: 256Mi
        livenessProbe:
          httpGet:
            path: /healthz
            port: 10259
        readinessProbe:
          httpGet:
            path: /healthz
            port: 10259
```

### 4.8 main.go 入口

```go
// cmd/scheduler/main.go
package main

import (
    "context"
    "flag"
    "os"

    "k8s.io/client-go/kubernetes"
    "k8s.io/client-go/rest"
    "k8s.io/client-go/tools/clientcmd"
    "k8s.io/klog/v2"

    "github.com/example/my-scheduler/pkg/scheduler"
)

var (
    schedulerName = flag.String("scheduler-name", "my-scheduler", "Scheduler name")
    leaderElect   = flag.Bool("leader-elect", false, "Enable leader election")
)

func main() {
    klog.InitFlags(nil)
    flag.Parse()
    
    // 1. 创建 Kubernetes 客户端
    config, err := rest.InClusterConfig()
    if err != nil {
        config, err = clientcmd.BuildConfigFromFlags("", os.Getenv("KUBECONFIG"))
        if err != nil {
            klog.Fatal(err)
        }
    }
    clientset, err := kubernetes.NewForConfig(config)
    if err != nil {
        klog.Fatal(err)
    }
    
    // 2. 创建 Scheduler
    sched := scheduler.NewScheduler(clientset, *schedulerName)
    
    // 3. 运行
    ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt)
    defer cancel()
    
    if err := sched.Run(ctx); err != nil {
        klog.Fatal(err)
    }
}
```

---

## 五、实战场景

### 5.1 场景 1：AI 训练任务调度到 GPU 节点

```go
// 过滤条件
if hasGPU(pod) {
    if !hasGPUNode(node) {
        return false
    }
}

// 优选：GPU 型号匹配
if hasGPU(pod) && nodeHasLabel(node, "gpu-type", podGPUType(pod)) {
    score += 5000
}
```

### 5.2 场景 2：在线业务分散到不同节点

```go
// Pod 反亲和性（不同节点）
if isOnlinePod(pod) {
    // 强制分散到不同节点
    for _, existing := range sameServicePodsOnNode(node) {
        if hasAntiAffinity(pod, existing) {
            score -= 10000  // 强反亲和
        }
    }
}
```

### 5.3 场景 3：离线任务调度到空闲资源

```go
// 检测节点空闲度
func isNodeUnderUtilized(node *corev1.Node) bool {
    // 假设获取节点指标
    cpuUsage := getNodeCPUUsage(node)  // 自定义获取
    if cpuUsage < 0.3 {  // 30% 以下
        return true
    }
    return false
}

// 优先调度到空闲节点
if isOfflineTask(pod) && isNodeUnderUtilized(node) {
    score += 3000
}
```

### 5.4 场景 4：业务组资源隔离

```go
// 根据 team 标签分配节点
team := pod.Labels["team"]
nodeTeam := node.Labels["team"]

if team != "" && team != nodeTeam {
    // 硬约束：不同团队不能混部
    return false
}
```

### 5.5 场景 5：Spot 实例优先调度

```go
// 优先使用 Spot 实例
if node.Labels["node.kubernetes.io/lifecycle"] == "spot" {
    score += 2000  // 优先调度
}

// 在线任务避免 Spot
if isOnlineCriticalPod(pod) && node.Labels["node.kubernetes.io/lifecycle"] == "spot" {
    score -= 5000  // 强烈不推荐
}
```

---

## 六、Scheduler Sharding（K8s v1.20+）

### 6.1 什么是 Sharding

```text
K8s v1.20+ 引入 SchedulerSharding：
  - 多个 Scheduler 实例
  - 每个实例只调度一部分 Pod
  - 提升调度吞吐

  示例：
    - Scheduler-1：调度 namespace=production
    - Scheduler-2：调度 namespace=staging
    - Scheduler-3：调度 namespace=dev
```

### 6.2 启用 Sharding

```bash
# kubelet 启动参数
--feature-gates=SchedulerSharding=true
```

### 6.3 通过 Profile 启用

```yaml
apiVersion: kubescheduler.config.k8s.io/v1
kind: KubeSchedulerConfiguration
profiles:
- schedulerName: my-scheduler
  plugins:
    queueSort:
      disabled: []    # 关闭默认排序
    preFilter:
      enabled: []    # 关闭默认 PreFilter
  # 自定义插件链
```

### 6.4 Pod 指定 Scheduler

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: my-pod
spec:
  schedulerName: my-scheduler    # 指定 Scheduler
  containers:
  - name: app
    image: nginx
```

---

## 七、Kube-Scheduler 源码（参考）

### 7.1 Scheduler 启动流程

```text
1. 加载 KubeSchedulerConfiguration
2. 创建 Scheduler 内部对象
3. 注册各扩展点（Filter/Scoring/Reserve）
4. 启动 Informer
5. 启动多个 Scheduler Worker
6. 进入调度循环：
   for {
       pod := podQueue.Pop()
       feasibleNodes := runFilter(pod)
       if len(feasibleNodes) == 0 { continue }
       scoredNodes := runScore(pod, feasibleNodes)
       selected := pickMax(scoredNodes)
       runReserve(pod, selected)
       runPermit(pod)
       bind(pod, selected)
   }
```

### 7.2 调度器扩展点对比

```text
┌─────────────────┬──────────────────────┐
│  扩展点          │  用途                │
├─────────────────┼──────────────────────┤
│  PreEnqueue     │  入队前检查           │
│  Filter         │  节点过滤（排除）    │
│  PostFilter     │  过滤后处理          │
│  PreScore       │  打分前预处理        │
│  Score          │  节点打分            │
│  NormalizeScore │  归一化（0-100）   │
│  Reserve        │  资源预留            │
│  Permit        │  最终决定            │
│  PreBind        │  绑定前处理          │
│  Bind           │  实际绑定（默认）    │
│  PostBind       │  绑定后处理          │
│  EnqueueExtension│ 控制入队逻辑        │
│  QueueingHints  │ 队列提示（v1.28+）│
└─────────────────┴──────────────────────┘
```

---

## 八、Scheduler 调试

### 8.1 调试工具

```bash
# 1. 查看 Scheduler 日志
kubectl logs -n kube-system deploy/my-scheduler -f

# 2. 启用 debug
# 在 main.go 添加：
# klog.SetLevel(klog.LevelDebug)

# 3. 查看 Pod 调度状态
kubectl describe pod <pod-name>
# 在 Events 中查看 "Scheduled" 事件

# 4. 强制重新调度
kubectl replace --force -f <pod-yaml>

# 5. 查看 Scheduler Profile
kubectl get pod <pod-name> -o jsonpath='{.spec.schedulerName}'

# 6. 查看默认 Scheduler 日志
kubectl logs -n kube-system deploy/kube-scheduler-<node-name>

# 7. Scheduler 指标
kubectl get --raw /metrics -n kube-system
kubectl get --raw /apis/metrics.k8s.io/v1beta1/pods
```

### 8.2 调度器性能监控

```yaml
# Prometheus 抓取 Scheduler 指标
apiVersion: v1
kind: Service
metadata:
  name: my-scheduler-metrics
  namespace: kube-system
  labels:
    app: my-scheduler
spec:
  selector:
    app: my-scheduler
  ports:
  - name: metrics
    port: 10259
    targetPort: 10259
---
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: my-scheduler
  namespace: monitoring
spec:
  selector:
    matchLabels:
      app: my-scheduler
  namespaceSelector:
    matchNames: [kube-system]
  endpoints:
  - port: metrics
    interval: 30s
    path: /metrics
```

---

## 九、最佳实践

### 9.1 设计原则

```text
1. 单一职责
   - 一个 Scheduler 处理一类工作负载
   - 不要试图做"万能 Scheduler"

2. 复用内置
   - 复用 K8s 内置 Filter（资源、亲和性等）
   - 仅添加自定义逻辑

3. 性能优先
   - Scheduler 必须快速
   - 100 个节点应在 1-2 秒完成
   - 异步 Informer 缓存

4. 可观测
   - 暴露 Prometheus 指标
   - 详细日志
   - 跟踪调度延迟

5. 测试覆盖
   - 单元测试
   - 集成测试
   - 性能测试
```

### 9.2 性能优化

```text
性能瓶颈：
  - 节点数量多（> 1000）
  - Pod 数量多（> 10K）
  - 自定义 Filter 复杂

优化策略：
  1. 使用 Inexpensive Scheduling（v1.21+ GA）
  2. 减少 Plugin 数量
  3. 缓存常用数据
  4. 并发控制
  5. SchedulerSharding 分片
```

### 9.3 与默认 Scheduler 协作

```text
1. 大集群：默认 + 多个自定义 Scheduler
2. 中集群：默认 + 1 个自定义 Scheduler（处理特殊 Pod）
3. 小集群：仅默认 Scheduler

典型架构：
  - 默认 Scheduler：处理通用 Pod
  - gpu-scheduler：处理 GPU Pod
  - high-priority-scheduler：处理 VIP 业务
  - spot-scheduler：处理 Spot 实例
```

---

## 十、参考资源

```text
- K8s Scheduler 官方文档: https://kubernetes.io/docs/concepts/scheduling-eviction/
- Scheduler Extender: https://github.com/kubernetes-retired/contrib/tree/master/cluster-autoscaler
- kube-scheduler 源码: https://github.com/kubernetes/kubernetes/tree/master/pkg/scheduler
- Scheduling Framework: https://kubernetes.io/docs/concepts/scheduling-eviction/scheduling-framework/
- Kube-Scheduler 配置: https://kubernetes.io/docs/reference/scheduling/config/
- Scheduler Profiles: https://kubernetes.io/docs/reference/scheduling/config/#profiles
- Scheduler Sharding: https://kubernetes.io/docs/concepts/scheduling-eviction/#scheduling-sharding
- Scheduler Extender 实战: https://medium.com/@muhammet.arslan/write-a-k8s-scheduler-extender-in-go-117f0ed0a1d5
```

## 速记卡

默认 Scheduler：3 个扩展点，11 个步骤
自定义 Scheduler：实现 filter + score + bind
多 Scheduler：每个 Pod 通过 schedulerName 选择
Scheduler Profile：同一集群多种策略
Scheduler Sharding：v1.20+，多副本并行调度
Scheduler Extender：通过 HTTP 调用外部服务
Scheduler Framework：11 个扩展点（k8s.io/kube-scheduler）
关键代码：prefilter → filter → postfilter → prescore → score → normalizescore → reserve → permit → prebind → bind → postbind
