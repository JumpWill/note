# Temporal

持久化执行（Durable Execution）框架，来自 Uber 的 Cadence 衍生的新一代方案。核心是"Workflow 代码本身可以长时间运行并跨越崩溃恢复"。

## 一、定位

- 解决微服务长流程的状态管理 / 重试 / 补偿
- 替代自己手写状态机 + DB 实现
- 把工作流逻辑写成像普通函数，由 Temporal 保证落地、恢复、可观测
- SDK 多语言：Go / Java / Python / TypeScript / .NET / PHP / Rust
- 部署方式：自建 Temporal Cluster / Temporal Cloud

## 二、核心概念

| 概念 | 含义 |
| ---- | ---- |
| **Workflow** | 业务逻辑入口，由代码定义（带确定性约束） |
| **Activity** | Workflow 中的可重试工作单元（外部副作用） |
| **Task** | Workflow 任务 / Activity 任务的最小调度单位 |
| **Worker** | 运行 Workflow / Activity 的进程 |
| **Task Queue** | Worker 监听队列 |
| **Namespace** | 多租户隔离 |
| **Workflow Execution** | Workflow 的一次运行 |
| **Event History** | 全部事件追加追加 |
| **Command** | Worker 向 Server 的命令（如 schedule Activity） |
| **Signal** | 外部向 Workflow 注入事件 |
| **Query** | 不修改状态地读 Workflow |
| **Schedule** | Server 端 cron / 间隔触发 |
| **ContinueAsNew** | 长时间 Workflow 定期重新开始，压缩历史 |
| **Retry Policy** | 退避策略 + 最大次数 |
| **Saga / Compensation** | 长流程的补偿动作 |

## 三、架构

```text
┌────────────────────────────────────┐
│ Temporal Server（包含持久化）        │
│   - Frontend Service                │
│   - History Service (event sourcing)│
│   - Matching Service (Task Queue)   │
│   - Worker Service                  │
│   - Persistence (Cassandra/PG/MySQL)│
└──────────────────┬─────────────────┘
                   │ gRPC
                   ▼
┌────────────────────────────────────┐
│ Worker (业务进程)                    │
│   - Workflow code                   │
│   - Activity code                   │
└────────────────────────────────────┘
```

- Workflow 状态完全由 Server 端 Event History 重建
- Worker 拉取 Task → 执行 → 上报结果
- Server 决定重试 / 取消 / 时间

## 四、Hello World（Go）

### 1. Activity

```go
func ChargeCustomer(ctx context.Context, amount int) error {
    // 调用外部支付服务
    return nil
}
```

### 2. Workflow

```go
func OrderWorkflow(ctx workflow.Context, oid string) error {
    amount := 1000
    err := workflow.ExecuteActivity(ctx, ChargeCustomer, amount).Get(ctx, nil)
    if err != nil {
        return err
    }
    return nil
}
```

### 3. 启动 Worker

```go
func main() {
    c, _ := client.Dial(client.Options{Namespace: "default"})
    defer c.Close()

    w := worker.New(c, "ORDER_TASK_QUEUE", worker.Options{})
    w.RegisterWorkflow(OrderWorkflow)
    w.RegisterActivity(ChargeCustomer)
    w.Start()
    defer w.Stop()

    // 触发一次
    c.ExecuteWorkflow(context.Background(), client.StartWorkflowOptions{
        ID:        "order-1",
        TaskQueue: "ORDER_TASK_QUEUE",
    }, OrderWorkflow, "order-1")
}
```

## 五、关键特性

### 1. 持久化执行 / 确定性

- Workflow 写代码像普通函数
- 实际是状态机：每次执行从历史重放
- **必须确定性**：不要在新 Workflow 中使用 rand / time.Now / 直接调 IO
- 想要的随机性 → 透过 Activity 或 SDK 提供的 `workflow.SideEffect`

```go
// 正确：用 workflow.Now() / workflow.Random()
t := workflow.Now(ctx)
```

### 2. Activity 重试

```go
ao := workflow.ActivityOptions{
    StartToCloseTimeout: time.Minute,
    RetryPolicy: &temporal.RetryPolicy{
        MaximumAttempts: 5,
        BackoffCoefficient: 2.0,
    },
}
ctx = workflow.WithActivityOptions(ctx, ao)
```

- 默认 Exponential Backoff
- 可配 `InitialInterval`、`MaximumInterval`、`NonRetryableErrorTypes`

### 3. 跨 Activity 状态

`workflow.Await`：

```go
workflow.Await(ctx, func() bool {
    return state.Approved
})
```

或等待 Signal：

```go
ch := workflow.GetSignalChannel(ctx, "approval")
selector := workflow.NewSelector(ctx)
selector.AddReceive(ch, func(c workflow.ReceiveChannel, more bool) {
    var msg string
    c.Receive(ctx, &msg)
    state.Approved = true
})
selector.Select(ctx)
```

外部触发：

```python
# Python client
handle.signal("approval", "yes")
```

### 4. 子 Workflow

```go
child := workflow.ExecuteChildWorkflow(ctx, ChildWorkflow, arg)
var result string
child.Get(ctx, &result)
```

- 独立 history / 独立 retry / 单独 cancel
- 可跨 namespace（多租户）

### 5. Saga / 补偿

```go
defer func() {
    if !succeed {
        workflow.ExecuteActivity(ctx, RefundOrder, amount).Get(ctx, nil)
    }
}()
```

- 业务代码内手动补偿
- 集成 `go.temporal.io/sdk/temporal` 的 Saga helper

### 6. 定时 / 调度

- Schedule（Cron）：Server 端按 cron 启动 Workflow
- Timer：Workflow 内 `workflow.Sleep`

```go
err := workflow.NewTimer(ctx, 24*time.Hour).Get(ctx, nil)
```

### 7. ContinueAsNew

长流程压缩历史：

```go
return workflow.NewContinueAsNewError(ctx, OrderWorkflow, nextInput)
```

### 8. Query / Update

外部查询 / 修改 Workflow 状态：

- Query：只读
- Update：原子读+写（带 Validator / Acceptor）

## 六、Task Queue

| 概念 | 含义 |
| ---- | ---- |
| **Default / Per-worker** | 默认一个 |
| **Multiple** | 一 Workflow 可调度到不同队列 |
| **Sticky Execution** | 同 Worker 处理 Workflow 的下一个命令 |

## 七、Search Attributes / Visibility

- 给 Workflow 加标签用于高级查询
- 默认存在 DB（Advanced Visibility 可配 ES / Cassandra）

```go
attributes := map[string]interface{}{
    "customerId": "u-123",
    "priority":   5,
}
c.StartWorkflow(..., attributes)
```

UI / tctl / Temporal CLI 可基于属性过滤。

## 八、Namespace / RBAC

- 多 Namespace 隔离
- RBAC / API Key
- Worker Service / Frontend Service 可独立扩展

## 九、失败回放 / 调试

- `tctl workflow describe` 列历史
- Replay 测试：版本升级时要保持兼容性
- `Worker.Ide` / Temporal Web UI 可视化

## 十、测试

- `testsuite.SetUp`: 启动内存 dev server
- `env.ExecuteWorkflow(...)` 直接运行

```go
var ts *testsuite.TestWorkflowEnvironment
func TestOrder(t *testing.T) {
    ts = testsuite.NewTestWorkflowEnvironment(t)
    ts.SetRegisterWorkflow(env.RegisterWorkflow(OrderWorkflow))
    ts.ExecuteWorkflow(OrderWorkflow, "order-1")
    ts.AssertExpectations(t)
}
```

## 十一、典型用法

### 1. 微服务 Saga

电商下单：

```text
Workflow: Order
  ├── reserveInventory
  ├── chargePayment
  ├── saveShippingInfo
  └── notifyUser

失败补偿 → releaseInventory / refund
```

### 2. 长审批流

```text
User Requests Approval
Workflow Await for Signal "approve" / "reject"
   └── approved → schedule downstream
   └── rejected → notify
ContinueAsNew every 100 events
```

### 3. 数据 ETL（替代部分 Airflow）

- 拉取 → 处理 → 入库，每个步骤 Activity
- 自动重试、可观测

### 4. AI Inference / GPU 工作

- 调用 GPU 异步 Result
- 大模型调用（OpenAI 等）的 Token / Rate Limit 重试天然好

## 十二、对比 Airflow / Argo

| 维度 | Temporal | Airflow | Argo |
| ---- | -------- | ------- | ---- |
| 模型 | 工作流执行机 | DAG 执行器 | Pod 编排 |
| 启动开销 | 低 | 中 | K8s Pod |
| 跨崩溃恢复 | 原生（强） | 部分 | K8s 重启 |
| 持久化 | Event Sourcing | DB 状态 | K8s object |
| 状态查询 | 强（Query） | 弱 | 弱 |
| 周期触发 | Schedule | Cron | CronWorkflow |
| 适合 | 长业务流 | 数据 ETL | CI / Data |

## 十三、运维

- **Schema 兼容**：Workflow Type 改了要 using Versioning
- **Worker 升级**：rolling restart；Replayer 验证
- **历史清理**：Retention 配置（默认几小时到几天）
- **资源限制**：Worker 内 Activity 线程池、concurrent Workflow Tasks
- **TLS**：Server / Client 双向认证
- **多 Namespace**：物理隔离团队

## 十四、版本

- 1.x 稳定 API
- Worker Versioning：sticky 版本路由
- Schedule TOID
- Workflow Update Protocol（带验证的事务式更新）
- Pinned / Worker Versioning

## 十五、最佳实践

- **Workflow 业务逻辑，Activity 副作用**
- **Workflow 短**：输出大于 10k event 用 `ContinueAsNew`
- **确定函数**：测试用 `Replayer`
- **Activity 幂等**：可重试
- **小颗粒 Activity**：便于超时控制
- **观察**：UI 配置 Search Attributes / Workflow Tags
- **测试**：本地 `dev server` + `testsuite`

## 十六、Temporal Cloud

托管服务：

- 跨地域 AWS
- 命名空间配额
- SOC2 / HIPAA
- 按 Action 计费
- 支持 mTLS / SSO
