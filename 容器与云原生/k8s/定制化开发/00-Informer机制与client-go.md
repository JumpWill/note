# 00 - client-go 与 Informer 机制（K8s 定制化开发基础）

> 本章是 K8s 定制化开发的**前置基础**。理解 client-go 的 Informer 机制、List-Watch 模式，才能真正理解 Controller、Operator、Webhook 等组件的内部机制。

## 一、为什么必须懂 client-go 与 Informer

### 1.1 K8s 定制化开发的本质

```text
所有 K8s 定制化组件都在做一件事：

  监听 K8s 资源变化 → 调谐资源状态

  ┌──────────────────────────────────┐
  │  K8s API Server                    │
  │  etcd（真实状态）                 │
  └────────────┬─────────────────────┘
               │  watch/list（HTTP）
               ↓
  ┌──────────────────────────────────┐
  │  我们的 Controller/Operator      │
  │  监听 spec.replicas = 3           │
  │  调谐创建 3 个 Pod                │
  └──────────────────────────────────┘

  关键问题：
    - 如何高效地"监听"资源变化？
    - 如何保证不漏事件、不重复处理？
    - 如何处理瞬时网络错误？
    - 如何处理大列表请求？
    - 如何优化重连和缓存？
    
  答案是 client-go + Informer + Workqueue
```

### 1.2 client-go 的地位

```text
client-go = K8s 官方 Go 客户端库

作用：
  1. 与 K8s API Server 通信（CRUD + Watch）
  2. 维护本地缓存（Informer）
  3. 提供 List-Watch 机制
  4. 触发事件回调

位置：
  - Kubernetes 核心：kubectl、kubelet、kube-controller-manager
  - 自研组件：所有 Operator、所有 Controller
  - 第三方：client-go 是事实标准

K8s/Controller/Operator 与 client-go：
  ┌────────────────────────────────────┐
  │  我们的 Controller 业务逻辑          │
  │  （Reconcile 函数）                 │
  └────────────┬───────────────────────┘
               │ 通过 client-go 调用
  ┌────────────▼───────────────────────┐
  │  client-go                          │
  │  - Lister / Getter                  │
  │  - Informer（本地缓存 + Watch）     │
  │  - Workqueue（去重、重试）         │
  │  - 各种资源类型的 Client           │
  └────────────┬───────────────────────┘
               │ HTTPS
  ┌────────────▼───────────────────────┐
  │  K8s API Server                    │
  └────────────────────────────────────┘
```

### 1.3 Operator 中的典型用法

```go
// 这是我们常写的代码
func (r *MyResourceReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
    // 1. 拿到 req 里的 key
    myCR := &myv1.MyResource{}
    r.Client.Get(ctx, req.NamespacedName, myCR)
    
    // 2. 创建/更新相关资源
    r.Client.Create(ctx, deploy)
    
    // 3. 返回
    return ctrl.Result{}, nil
}

// 这些代码底层依赖 client-go 的 Informer 和 Workqueue
// r.Client 实际是 controller-runtime 包装的 client-go Client
// 各种资源变更通过 Informer 的 Watch 流实时推送给 Controller
```

---

## 二、List-Watch 机制

### 2.1 什么是 List-Watch

```text
List-Watch = K8s 的事件订阅机制

两种操作：
  List  → 拉取：获取资源的当前完整状态
  Watch  → 推送：订阅资源的实时变化事件

核心思想：
  - 启动时 List 一次（拿到全量初始状态）
  - 启动后 Watch（订阅增量变化）
  - List + Watch = 完整的事件流

为什么需要 List-Watch？
  - List 用于初始化本地缓存
  - Watch 用于接收变化
  - 两者结合 = 可靠的状态同步
```

### 2.2 HTTP API 层

```text
List API：
  GET /api/v1/namespaces/default/pods
  → 返回全量 Pod 列表
  → 客户端构造本地缓存

Watch API：
  GET /api/v1/namespaces/default/pods?watch=true
  → 保持 HTTP 长连接
  → 推送增量事件流
  → 客户端处理事件更新本地缓存

Watch 事件数据格式：
  {
    "type": "ADDED" | "MODIFIED" | "DELETED" | "ERROR",
    "object": { /* 资源对象 */ }
  }
```

### 2.3 List-Watch 的挑战

```text
1. 长连接稳定性
   - HTTP 连接可能断开（超时、网络抖动）
   - 必须能自动重连
   - 重连后重新 List 全量

2. 书签（ResourceVersion）
   - API Server 用 RV 标识资源版本
   - Watch 携带 RV，断开后用 RV 继续
   - 类似 K8s 的乐观锁

3. 重连时事件丢失
   - 断连期间可能错过事件
   - 重新 List 全量 = 重建缓存
   - 这是最安全的策略

4. 多个组件监听
   - 多个 Controller 同时 Watch
   - API Server 支持多路 Watch 流
   - etcd Watch 底层支撑
```

---

## 三、Informer 机制详解

### 3.1 什么是 Informer

```text
Informer = List + Watch + Local Cache + Event Handlers

K8s 资源
    │
    ↓ List + Watch（client-go）
    │
Informer
    │
    ├── Local Cache（内存中的对象状态）
    │   - Pod 列表（indexed by namespace/name）
    │   - Deployment 列表
    │   - ...
    │
    └── Event Handlers
        - OnAdd(obj)
        - OnUpdate(old, new)
        - OnDelete(obj)
        - 回调函数触发

关键：
  - Informer 在 Controller 启动时启动
  - 后台 goroutine 持续 List + Watch
  - 事件触发回调函数
  - 回调函数中处理业务逻辑
```

### 3.2 Informer 架构

```text
┌────────────────────────────────────────────────┐
│              K8s API Server                       │
│         /api/v1/pods?...&watch=true             │
└────────────┬───────────────────────────────────┘
               │ HTTP 长连接
               ↓
┌────────────────────────────────────────────────┐
│              client-go Informer                   │
│                                                │
│  ┌────────────────────────────────────────┐   │
│  │  Reflector（反射器）                    │   │
│  │  - ListAndWatch 协程                  │   │
│  │  - 处理 410 Gone（重连）              │   │
│  │  - 维护 ResourceVersion              │   │
│  └────────────┬───────────────────────────┘   │
│               │ 推送事件                          │
│               ↓                                 │
│  ┌────────────────────────────────────────┐   │
│  │  DeltaFIFO（事件队列）                 │   │
│  │  - 事件去重                           │   │
│  │  - 排序（按 RV）                     │   │
│  │  - 同步机制                          │   │
│  └────────────┬───────────────────────────┘   │
│               │ 事件分发                          │
│               ↓                                 │
│  ┌────────────────────────────────────────┐   │
│  │  Indexer / ThreadSafeStore            │   │
│  │  - 本地缓存（in-memory cache）         │   │
│  │  - 按 namespace/name 索引             │   │
│  └────────────┬───────────────────────────┘   │
│               │ 查询时返回                        │
│               ↓                                 │
│  ┌────────────────────────────────────────┐   │
│  │  Event Handlers                        │   │
│  │  - OnAdd / OnUpdate / OnDelete         │   │
│  │  - 用户自定义回调函数                  │   │
│  └────────────────────────────────────────┘   │
└────────────────────────────────────────────────┘
```

### 3.3 Informer 核心组件

#### Reflector（反射器）

```go
// Reflector 负责 List + Watch
type Reflector struct {
    store Store
    listerWatcher ListerWatcher
    backoffManager wait.BackoffManager
    // ...
}

// 核心方法：ListAndWatch
func (r *Reflector) ListAndWatch(stopCh <-chan struct{}) error {
    // 1. 启动时 List 全量数据
    list, err := r.listerWatcher.List(...)
    
    // 2. 将全量数据 sync 到 Store
    r.syncWith(list, ...)
    
    // 3. 启动 Watch
    w, err := r.listerWatcher.Watch(...)
    
    // 4. 循环处理事件
    for {
        select {
        case <-stopCh:
            return nil
        case event, ok := <-w.ResultChan():
            // 5. 处理事件
            r.store.Update(event)
        }
    }
}
```

#### DeltaFIFO（事件队列）

```go
// DeltaFIFO 是 Informer 的核心数据结构
type DeltaFIFO struct {
    lock sync.Mutex
    cond sync.Cond
    items map[string]*Deltas
    queue []string
    // ...
}

// Delta = 单个事件
type Delta struct {
    Type DeltaType   // Added, Updated, Deleted, Sync
    Object interface{}
}

// 事件流转：
//   API Server → Reflector → DeltaFIFO → Pop() → Indexer + Handlers
```

#### Indexer / ThreadSafeStore（本地缓存）

```go
// Indexer 是线程安全的本地缓存
type Indexer interface {
    Store
    // Get, List, Add, Update, Delete
    // GetByKey, Update, Delete
    // Index (扩展索引)
}

// 默认实现：cache.threadSafeMap
type threadSafeMap struct {
    lock  sync.RWMutex
    items map[string]interface{}
    // 按 namespace/name 索引
}

// Lister 提供 List/Watch 接口
type lister struct {
    indexer Indexer
    // ...
}

// 使用示例
podLister corev1listers.PodLister
pod, err := podLister.Pods("default").Get("nginx")
// 从本地缓存读取，不调 API Server
```

#### Event Handlers（事件处理器）

```go
// 用户定义事件回调
type ResourceEventHandler interface {
    OnAdd(obj interface{})
    OnUpdate(oldObj, newObj interface{})
    OnDelete(obj interface{})
}

// 注册回调
informer.AddEventHandler(cache.ResourceEventHandlerFuncs{
    AddFunc:    func(obj interface{}) { /* 处理新增 */ },
    UpdateFunc: func(old, new interface{}) { /* 处理更新 */ },
    DeleteFunc: func(obj interface{}) { /* 处理删除 */ },
})
```

### 3.4 Informer 工作流程完整示例

```go
// 1. 创建 Informer 工厂
factory := informers.NewSharedInformerFactory(
    clientset,  // client-go 客户端
    30*time.Second,  // resync 周期
)

// 2. 获取 Pod Informer
podInformer := factory.Core().V1().Pods().Informer()

// 3. 注册事件回调
podInformer.AddEventHandler(cache.ResourceEventHandlerFuncs{
    AddFunc: func(obj interface{}) {
        fmt.Println("Pod added:", obj.(*corev1.Pod).Name)
    },
    UpdateFunc: func(old, new interface{}) {
        fmt.Println("Pod updated:", new.(*corev1.Pod).Name)
    },
    DeleteFunc: func(obj interface{}) {
        fmt.Println("Pod deleted:", obj.(*corev1.Pod).Name)
    },
})

// 4. 启动 List-Watch
factory.Start(wait.NeverStop)
// 等待缓存同步
factory.WaitForCacheSync(wait.NeverStop)

// 5. 业务使用（从本地缓存读）
podLister := factory.Core().V1().Pods().Lister()
pod, err := podLister.Pods("default").Get("nginx")
```

---

## 四、SharedInformerFactory 共享机制

### 4.1 共享 Informer

```text
问题：
  - 一个进程可能需要监听多种资源
  - Pod、Deployment、Service、ConfigMap...
  - 每种资源一个 Informer？开销大！

解决：
  - SharedInformerFactory
  - 同一资源类型只创建一份 Informer
  - 多个 Handler 共享同一份数据

┌────────────────────────────────────────────┐
│       SharedInformerFactory                  │
│       （一个进程一个）                    │
│                                            │
│  ┌──────────────┐  ┌──────────────┐        │
│  │ PodInformer  │  │ DeployInformer│        │
│  │  - 共享缓存  │  │  - 共享缓存  │        │
│  │  - 多 Handler │  │  - 多 Handler │        │
│  └──────┬───────┘  └──────┬───────┘        │
│         │                 │                │
│  ┌──────▼─────────────────▼────────┐      │
│  │ Pod 缓存     Deployment 缓存      │      │
│  │ （in-memory, indexed by name） │      │
│  └───────────────────────────────┘      │
│                                            │
│  优势：                                    │
│  - 减少 API Server 压力                  │
│  - 减少本地内存占用                      │
│  - 多个 Controller 共享最新状态        │
└────────────────────────────────────────────┘
```

### 4.2 SharedInformerFactory 使用

```go
// 创建共享 factory
factory := informers.NewSharedInformerFactory(
    clientset,
    0,  // 0 = 不自动 resync
)

// 获取所有资源类型的 Informer
podInformer := factory.Core().V1().Pods().Informer()
deployInformer := factory.Apps().V1().Deployments().Informer()
serviceInformer := factory.Core().V1().Services().Informer()
configMapInformer := factory.Core().V1().ConfigMaps().Informer()

// 启动所有 Informer
factory.Start(wait.NeverStop)
factory.WaitForCacheSync(wait.NeverStop)

// 注册所有 Handler
podInformer.AddEventHandler(podHandler)
deployInformer.AddEventHandler(deployHandler)
// ...
```

### 4.3 共享机制的优势

```text
1. 减少 API Server 压力
   - 多个 Controller 共享一份 List/Watch 流
   - 而不是每个 Controller 独立订阅

2. 减少本地内存
   - PodInformer 缓存一份
   - 多个 Handler 共享

3. 保证一致性
   - 所有 Handler 看到相同状态
   - 避免数据不一致问题

4. 简化代码
   - 一次创建，多处使用
   - 不需要管理多个 Informer
```

---

## 五、Workqueue（工作队列）

### 5.1 为什么需要 Workqueue

```text
Informer 收到事件后，需要传递给 Controller 处理。
但直接处理可能有问题：

  1. 一个 Pod 变化触发多个 Controller
  2. Controller 处理慢会阻塞 Informer
  3. 同一对象被多次修改需要去重
  4. 处理失败需要重试
  5. 处理成功需要 ACK

解决：引入 Workqueue
```

### 5.2 Workqueue 特性

```text
client-go Workqueue（client-go/util/workqueue）：

特性：
  1. 去重
     - 同一对象只入队一次
     - 避免重复处理

  2. 顺序保证
     - FIFO 顺序处理
     - 不会乱序

  3. 限流
     - 避免突发流量压垮 Controller
     - rate limiter

  4. 重试
     - 处理失败自动重试
     - 退避策略

  5. ACK 机制
     - Add → 处理 → Done
     - 失败 → requeue
```

### 5.3 Workqueue 核心方法

```go
type Interface interface {
    Add(item interface{})              // 入队（去重）
    Len() int                          // 队列长度
    Get() (item interface{}, shutdown bool)  // 出队
    Done(item interface{})             // 处理完成
    ShutDown()                         // 关闭
    ShutDownWithDrain()               // 排空关闭

    // 限流
    AddRateLimited(item interface{})   // 限流入队

    // 重试
    Forget(item interface{})            // 忘记（不重试）
}
```

### 5.4 Workqueue 使用模式

```go
func (r *MyReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
    // 1. 处理单个对象
    if err := r.syncMyResource(ctx, req); err != nil {
        // 2. 处理失败：入队重试
        return ctrl.Result{Requeue: true}, err
    }
    
    // 3. 处理成功
    return ctrl.Result{}, nil
}

func (r *MyReconciler) SetupWithManager(mgr ctrl.Manager) error {
    return ctrl.NewControllerManagedBy(mgr).
        For(&MyResource{}).
        // 1. 监听 MyResource 变化
        Watches(
            &source.Kind{Type: &MyResource{}},
            // 2. 把事件入队（带去重）
            handler.EnqueueRequestForObject(
                mgr.GetClient(),
                mgr.GetRESTMapper(),
            ),
        ).
        Complete(r)
}
```

---

## 六、完整数据流

### 6.1 Informer + Workqueue + Controller 完整流程

```text
时序图：

T0: Controller 启动
    ↓
T1: 创建 SharedInformerFactory
    创建 PodInformer
    注册 EventHandler
        OnAdd/OnUpdate/OnDelete → 入 Workqueue
    ↓
T2: 启动 ListAndWatch（Reflector 协程）
    ↓
T3: Reflector 调 API Server
    GET /api/v1/pods?...&watch=true
    ↓
T4: API Server 返回 Pod 全量列表
    → Reflector 将所有 Pod 推入 DeltaFIFO
    → 同步到本地缓存（Indexer）
    → 触发 AddEvent → 全部入队
    ↓
T5: Workqueue 收到 N 个 Key（Pod namespace/name）
    ↓
T6: 启动 worker goroutine
    不断 Get() 从队列取 Key
    → 通过 Key 构造 req
    → 调用 Reconcile(ctx, req)
    ↓
T7: Reconcile 执行
    - Get 资源
    - 业务处理
    - Create/Update 相关资源
    - Update Status
    ↓
T8: 成功 → Done(key)
    失败 → AddRateLimited(key) 重新入队
    ↓
T9: 后续 Pod 变化（Watch 收到新事件）
    → Reflector 收到事件
    → 推入 DeltaFIFO
    → 同步到缓存
    → 触发 UpdateEvent
    → 入队
    → 重新调谐
```

### 6.2 完整数据流图

```text
┌─────────────────────────────────────────────────────────┐
│                    K8s API Server                        │
│            /api/v1/pods?watch=true                      │
│                       ↓                                 │
│                  List + Watch                            │
└───────────────────────┬─────────────────────────────────┘
                        │
        ┌───────────────▼───────────────┐
        │       Reflector              │
        │  - 长连接保持                 │
        │  - 重连处理 410 Gone           │
        │  - RV 维护                    │
        └───────────────┬───────────────┘
                        │
        ┌───────────────▼───────────────┐
        │       DeltaFIFO               │
        │  - 事件缓冲                   │
        │  - 去重                       │
        │  - 排序                       │
        └───────┬───────────┬───────────┘
                │           │
        ┌───────▼────┐  ┌───▼────────────┐
        │  Indexer  │  │  Workqueue      │
        │  本地缓存  │  │  去重+重试      │
        └────┬──────┘  └────────┬───────┘
             │                │
        ┌────▼────────┐  ┌─────▼─────────┐
        │ Handlers   │  │ Reconciler   │
        │ OnAdd     │  │ Reconcile()  │
        │ OnUpdate  │  │ 业务逻辑     │
        │ OnDelete  │  └──────────────┘
        └───────────┘
```

---

## 七、Controller 与 Informer 关系

### 7.1 controller-runtime 简化封装

```go
// controller-runtime 是 Operator 的事实标准
// 它封装了 client-go + Informer + Workqueue

type Reconciler interface {
    Reconcile(context.Context, Request) (Result, error)
}

// SetupWithManager 自动完成：
// 1. 创建 Watches
// 2. 注入 Workqueue
// 3. 启动 Worker
// 4. 调用 Reconcile
```

### 7.2 完整初始化流程

```go
// cmd/main.go
func main() {
    // 1. 创建 manager（自动初始化 clientset、cache、controller）
    mgr, _ := ctrl.NewManager(ctrl.GetConfigOrDie(), ctrl.Options{
        Scheme: scheme,
        Port: 9443,
    })
    
    // 2. 注册 Reconciler
    //    - 自动创建 Watch on MyResource
    //    - 自动注入 Workqueue
    //    - 自动启动 worker
    _ = (&MyReconciler{
        Client: mgr.GetClient(),
        Scheme: mgr.GetScheme(),
    }).SetupWithManager(mgr)
    
    // 3. 启动（启动所有 Informer、controller、webhook）
    mgr.Start(ctrl.SetupSignalHandler())
}
```

### 7.3 启动后的事件流

```text
1. mgr.Start() 启动：
   - 创建 SharedInformerFactory
   - 为每个 CRD 启动 Informer
   - 启动 Reflector（List + Watch）
   - 启动 EventHandler
   - 启动 Workqueue
   - 启动 Worker goroutine

2. Watch 收到事件：
   Pod ADDED → 入 Workqueue

3. Worker.Get() 取出 Key：
   - 构造 Request{NamespacedName: ...}
   - 调用 Reconciler.Reconcile(ctx, req)

4. Reconciler 处理：
   - Get 当前 CR 状态
   - 业务逻辑（创建 Pod/Service/...）
   - Update Status
   - 返回 Result（成功 / 重试 / 不重试）

5. 处理完毕：
   - 成功：Worker.Done(Key)
   - 失败：Workqueue.AddRateLimited(Key)
   - 触发重试（带退避）
```

---

## 八、关键概念速记

### 8.1 List-Watch

```text
List = 拉取（拿全量初始数据）
Watch = 推送（订阅增量变化）
List+Watch = 可靠的事件流
Watch 断连 → 重新 List（用 RV 续接）
RV = ResourceVersion = 资源版本号 = 乐观锁
```

### 8.2 Informer

```text
Informer = List + Watch + Local Cache + EventHandlers
Reflector = 维护 List-Watch 长连接
DeltaFIFO = 事件队列（去重、排序）
Indexer = 本地缓存（线程安全）
EventHandler = OnAdd / OnUpdate / OnDelete 回调
SharedInformerFactory = 共享的多种资源 Informer
```

### 8.3 Workqueue

```text
Workqueue = 去重 + 顺序 + 限流 + 重试
Add/Get/Done = 基本操作
RateLimited = 限流入队
Forget = 忘记（不重试）
重要：Reconcile 失败时必须 requeue，不能 Forget
```

### 8.4 client-go 与 controller-runtime

```text
client-go = K8s 官方 Go 客户端（底层）
controller-runtime = Operator 框架（封装 client-go）
CRD 类型 → 自动生成 clientset+lister+informer
Manager 启动 → 自动初始化所有依赖
Reconcile = 业务逻辑（与 Informer 解耦）
```

### 8.5 一句话总结

```text
client-go + Informer = K8s 控制器开发的事实标准
  - List-Watch 提供可靠事件流
  - SharedInformerFactory 共享缓存
  - DeltaFIFO 处理事件去重
  - Workqueue 串行化处理
  - Reflector 维护长连接
  - Indexer 提供本地缓存

Controller 模式：
  Watch 事件 → 入队 → Worker 取出 → Reconcile → Done

为什么重要：
  - 理解 Controller 行为（事件驱动）
  - 优化性能（缓存、Watch 选择）
  - 调试问题（事件丢失、状态不一致）
  - 编写自定义组件（Operator、Scheduler、AA）
```

---

## 九、实战示例

### 9.1 最简 Informer 示例

```go
package main

import (
    "fmt"
    "time"
    
    "k8s.io/client-go/informers"
    "k8s.io/client-go/kubernetes"
    "k8s.io/client-go/tools/cache"
    "k8s.io/client-go/tools/clientcmd"
)

func main() {
    // 1. 创建 K8s 客户端
    config, _ := clientcmd.BuildConfigFromFlags("", clientcmd.RecommendedHomeFile)
    clientset, _ := kubernetes.NewForConfig(config)
    
    // 2. 创建 SharedInformerFactory
    factory := informers.NewSharedInformerFactory(clientset, 10*time.Second)
    
    // 3. 获取 PodInformer
    podInformer := factory.Core().V1().Pods().Informer()
    
    // 4. 注册 Handler
    podInformer.AddEventHandler(cache.ResourceEventHandlerFuncs{
        AddFunc: func(obj interface{}) {
            pod := obj.(*corev1.Pod)
            fmt.Printf("Pod ADDED: %s/%s\n", pod.Namespace, pod.Name)
        },
        UpdateFunc: func(old, new interface{}) {
            pod := new.(*corev1.Pod)
            fmt.Printf("Pod UPDATED: %s/%s\n", pod.Namespace, pod.Name)
        },
        DeleteFunc: func(obj interface{}) {
            pod := obj.(*corev1.Pod)
            fmt.Printf("Pod DELETED: %s/%s\n", pod.Namespace, pod.Name)
        },
    })
    
    // 5. 启动
    factory.Start(stopCh)
    factory.WaitForCacheSync(stopCh)
    
    // 6. 持续运行
    <-stopCh
}
```

### 9.2 使用 SharedInformerFactory + Workqueue

```go
type Controller struct {
    clientset    kubernetes.Interface
    podInformer  cache.SharedIndexInformer
    workqueue     workqueue.RateLimitingInterface
}

func NewController(clientset kubernetes.Interface) *Controller {
    c := &Controller{
        clientset: clientset,
        workqueue: workqueue.NewNamedRateLimitingQueue("pod", workqueue.DefaultControllerRateLimiter()),
    }
    
    factory := informers.NewSharedInformerFactory(clientset, 0)
    c.podInformer = factory.Core().V1().Pods().Informer()
    c.podInformer.AddEventHandler(cache.ResourceEventHandlerFuncs{
        AddFunc:    c.enqueuePod,
        UpdateFunc: func(old, new interface{}) {
            c.enqueuePod(new)
        },
        DeleteFunc: c.enqueuePod,
    })
    
    return c
}

func (c *Controller) enqueuePod(obj interface{}) {
    key, _ := cache.MetaNamespaceKeyFunc(obj)
    c.workqueue.Add(key)
}

func (c *Controller) Run(threadiness int, stopCh <-chan struct{}) {
    defer c.workqueue.ShutDown()
    c.podInformer.Run(stopCh)
    
    for i := 0; i < threadiness; i++ {
        go c.runWorker()
    }
    <-stopCh
}

func (c *Controller) runWorker() {
    for c.processNextItem() {}
}

func (c *Controller) processNextItem() bool {
    key, shutdown := c.workqueue.Get()
    if shutdown {
        return false
    }
    defer c.workqueue.Done(key)
    
    // 业务处理
    namespace, name, _ := cache.SplitMetaNamespaceKey(key)
    pod, _ := c.clientset.CoreV1().Pods(namespace).Get(context.TODO(), name, metav1.GetOptions{})
    fmt.Printf("Processing Pod: %s/%s\n", namespace, name)
    
    return true
}
```

### 9.3 controller-runtime 自定义 Informer

```go
func (r *MyReconciler) SetupWithManager(mgr ctrl.Manager) error {
    return ctrl.NewControllerManagedBy(mgr).
        // 1. 监听主资源
        For(&MyResource{}).
        // 2. 监听关联资源（Owner）
        Owns(&appsv1.Deployment{}).
        // 3. 监听第三方资源（通过 EnqueueRequestsFromMapFunc）
        Watches(
            &source.Kind{Type: &corev1.ConfigMap{}},
            handler.EnqueueRequestsFromMapFunc(r.findObjectsForConfigMap),
        ).
        // 4. 自定义谓词
        WithEventFilter(predicate.GenerationChangedPredicate{}).
        Complete(r)
}

// 自定义映射函数
func (r *MyReconciler) findObjectsForConfigMap(obj client.Object) []reconcile.Request {
    cm := obj.(*corev1.ConfigMap)
    // 找到使用此 ConfigMap 的所有 MyResource
    crs := &myv1.MyResourceList{}
    r.Client.List(context.TODO(), crs)
    
    requests := []reconcile.Request{}
    for _, cr := range crs.Items {
        if cr.Spec.ConfigMapName == cm.Name {
            requests = append(requests, reconcile.Request{
                NamespacedName: types.NamespacedName{
                    Name:      cr.Name,
                    Namespace: cr.Namespace,
                },
            })
        }
    }
    return requests
}
```

---

## 十、性能与最佳实践

### 10.1 Informer 性能调优

```go
// 1. 合理设置 resync 周期
factory := informers.NewSharedInformerFactory(
    clientset,
    10*time.Minute,  // 太小频繁刷新，太大可能错过
)

// 2. 只监听需要的资源
// 不要无脑监听全集群所有资源

// 3. 减少 Watch 范围
// 优先用单 namespace 而非全集群
factory.Apps().V1().Deployments().Informer()  // 全集群
// vs
factory.Apps().V1().Deployments().Namespace("default").Informer()  // 限于 default

// 4. 使用 Predicate 过滤事件
predicate := predicate.Funcs{
    UpdateFunc: func(e event.UpdateEvent) bool {
        // 只关心 spec 变化
        oldPod := e.ObjectOld.(*corev1.Pod)
        newPod := e.ObjectNew.(*corev1.Pod)
        return oldPod.Spec.NodeName != newPod.Spec.NodeName
    },
}
informer.AddEventHandler(handler.Funcs{
    UpdateFunc: func(u event.UpdateEvent) {
        // 处理节点变化
    },
})

// 5. 多 Informer 并行
factory := informers.NewSharedInformerFactory(clientset, 0)
podFactory := factory.Core().V1().Pods()
eventFactory := factory.Core().V1().Events()
// 不同资源的 Informer 完全独立
```

### 10.2 Workqueue 性能调优

```go
// 1. 限流参数调优
queue := workqueue.NewNamedRateLimitingQueue(
    "my-controller",
    workqueue.RateLimiterOptions{
        // 默认 5 qps，10 个并发
        // 大量变更时可提高
        qps: 100,
        burst: 200,
    },
)

// 2. 限流键
// 不同对象使用不同限流键
queue.AddRateLimited(Key)

// 3. Done 后立即 Forget
// 长期不需要重试的对象
queue.Forget(Key)

// 4. 限制队列长度（避免内存爆炸）
if queue.Len() > 10000 {
    log.Warnf("queue too long, dropping")
}
```

### 10.3 常见问题排查

```text
问题 1：Informer 收不到事件
排查：
  - 看 Reflector 日志
  - 检查 RBAC 权限（list/watch）
  - 检查 API Server 是否可访问
  - 检查 network policy

问题 2：事件丢失
排查：
  - 检查是否 410 Gone
  - 检查 RV 是否正确处理
  - 减少并发压力

问题 3：内存占用大
排查：
  - 检查 Indexer 大小
  - 减少监听范围
  - 减少 label selector

问题 4：Controller 频繁触发
排查：
  - Workqueue 是否正常 Done
  - 是否错误地每次 Reconcile 都 requeue
  - 是否有 status 频繁更新
```

---

## 十一、参考资源

```text
- client-go 源码: https://github.com/kubernetes/client-go
- sample-controller: https://github.com/kubernetes/sample-controller
- controller-runtime 文档: https://book.kubebuilder.io/cronjob-tutorial/controller-image.html
- Informer 设计文档: https://github.com/kubernetes/client-go/blob/master/tools/cache/shared_informer.go
- Workqueue 源码: https://github.com/kubernetes/client-go/blob/master/util/workqueue/
- K8s 官方教程: https://kubernetes.io/docs/concepts/architecture/controller/
- Operator SDK 文档: https://sdk.operatorframework.io/
- 深入理解 Informer: https://www.zeng.dev/post/2022-09-21-k8s-informer-deep-dive/
```

## 速记卡

- **client-go** = K8s 官方 Go 客户端
- **List-Watch** = 拉取 + 推送事件流
- **Informer** = List + Watch + 缓存 + Handler
- **Reflector** = 维护 List/Watch 长连接
- **DeltaFIFO** = 事件队列（去重、排序）
- **Indexer** = 本地缓存（线程安全）
- **Workqueue** = 去重 + 顺序 + 重试
- **SharedInformerFactory** = 共享多种资源 Informer
- **Reconcile** = 业务逻辑（与 Informer 解耦）
- **client-go vs controller-runtime**：client-go 是底层，controller-runtime 是封装
- **关键流程**：Watch → Handler → Workqueue → Worker → Reconcile → Done
- **List-Watch 断连处理**：重新 List 全量 + 用 RV 续接 Watch
- **ResourceVersion (RV)** = 资源版本号 = 乐观锁


## 一句话总结

```
K8s 控制器 = Reflector（长连接）+ DeltaFIFO（事件队列）
         + Indexer（本地缓存）+ Workqueue（去重重试）
         + Handlers（回调函数）+ Reconciler（业务逻辑）
核心思想：事件驱动 + 最终一致 + 主动重试 + 本地缓存
```