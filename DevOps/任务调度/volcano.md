# Volcano

K8s 上面向 AI / 大数据 / HPC 场景的批调度系统（Batch Scheduler）。增强 K8s 默认调度器，引入作业队列 / Gang / 优先级 / 公平调度等批系统语义。

## 一、定位

- 补足 K8s 调度器对"批作业 / 分布式作业"的不足
- 解决 PodGroup（Job 多 Pod 同时调度）问题
- Volcano = Volcano Scheduler + Volcano Controller + Webhook
- 适合 Spark on K8s / Tensorflow on K8s / MPI / Ray / Horovod / AI / Gene

## 二、核心 CRD

| CRD | 含义 |
| --- | ---- |
| **Queue** | 资源池（占集群容量权重） |
| **PriorityClass** | K8s 原生 |
| **PodGroup** | 一组必须同时调度的 Pod（all-or-nothing） |
| **Job (vcjob)** | Volcano 自定义 Job（编排一组 PodGroup） |
| **SchedulerConfig** | Scheduler 行为配置（动作 / 缓存 / Plugin） |
| **Nodeorder** / TaskOrder | 自定义排序插件参数 |
| **SLA / MinAvailable** | Job 级别最低可用 Pod 数量 |

## 三、PodGroup（Gang Scheduling）

### 1. 为什么要 Gang

分布式作业（Tensorflow Parameter Server）：

```text
Worker 0/8 已经跑
Worker 6/8 等不到资源
Parameter Server 0/2 已经跑

最终只跑了一半，无法收敛
```

K8s 默认调度器不知道需要 8 个 worker 都齐才能跑。

### 2. PodGroup

```yaml
apiVersion: scheduling.volcano.sh/v1beta1
kind: PodGroup
metadata:
  name: my-training
spec:
  minMember: 8
  scheduleTimeoutSeconds: 600
  priorityClassName: high
  queue: ai-training
```

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: worker-0
  annotations:
    scheduling.volcano.sh/group-name: my-training
spec:
  container:
    - name: train
      image: tensorflow
```

所有 8 个 Pod 必须在 `scheduleTimeoutSeconds` 内同时调度，否则不调度（rollback）。

### 3. minMember

- 必须 ≥ minMember 个 Pod 才能跑
- 低于 minMember 就 Pending

## 四、Queue

```yaml
apiVersion: scheduling.volcano.sh/v1beta1
kind: Queue
metadata:
  name: ai-training
spec:
  weight: 100
  capability:
    cpu: "200"
    memory: 1024Gi
  reclaimable: false
```

- 集群资源分配维度
- `weight`：多个 queue 分配比例
- `capability`：上限
- `reclaimable`：能否回收分配给它的资源

## 五、Priority / Preemption

- 与 K8s PriorityClass 配合
- 高优先级作业抢占低优先级资源
- 通过 Volcano Plugin `priority` 启用

## 六、Job (vcjob) - 编排

```yaml
apiVersion: batch.volcano.sh/v1alpha1
kind: Job
metadata:
  name: spark-job
spec:
  minAvailable: 4
  schedulerName: volcano
  queue: default
  policies:
    - event: PodEvicted
      action: RestartJob
    - event: PodFailed
      action: TerminateJob
  tasks:
    - name: driver
      replicas: 1
      template: {spec: {...}}
    - name: executor
      replicas: 3
      template: {spec: {...}}
```

- `tasks`：声明 Pod 角色（driver / executor）
- `minAvailable`：必须齐的 Pod 数
- `policies`：失败事件响应

### vs Spark Operator vs SparkApplication

- Volcano Job 提供更通用的并行模型
- Spark Operator 用 Volcano CRD 直接拉起 Spark Driver + Executor
- SparkApplication 进一步定制 spark-submit 参数

## 七、Scheduler Plugin

Volcano scheduler 通过插件扩展：

| Plugin | 含义 |
| ------ | ---- |
| **drf** | Dominant Resource Fairness（默认） |
| **fairness** | 公平分配 |
| **gang** | Gang 调度 |
| **priority** | 抢占 |
| **capacity** | 容量队列 |
| **nodeorder** | 节点打分 |
| **taskorder** | 任务打分 |
| **preempt** | 抢占策略 |
| **backfill** | 集群空闲时调度小作业 |
| **numa** | NUMA-aware |
| **topology** | 拓扑感知 |
| **reservation** | 资源预留 |
| **overcommit** | 超分 |
| **sla** | 服务等级策略 |
| **binpack** | 紧凑打包 |
| **proportion** | 资源比例分配 |

### 启用 / 配置

```yaml
apiVersion: scheduling.volcano.sh/v1beta1
kind: SchedulerConfig
plugins:
  - name: gang
  - name: drf
  - name: priority
  - name: capacity
  - name: binpack
config:
  - name: drf
    arguments:
      - masterDisable=false
```

## 八、Volcano Workflow

- v1.6+：Volcano Workflow（基于 Tekton 提供 workflow 风格）
- 也可使用 Argo + Volcano Scheduler 组合

## 九、Queue vs Namespace

Queue 不替代 Namespace；Queue 是资源分配单位，Namespace 是 API 配额单位。

```text
Namespace     业务边界
Queue         资源边界
PriorityClass 重要性优先级
PodGroup     作业整体性
```

## 十、安装

```bash
# 离线
kubectl apply -f volcano-scheduler.yaml
kubectl apply -f volcano-controller.yaml

# helm
helm repo add volcano-sh https://volcano-sh.github.io/helm-charts
helm install volcano volcano-sh/volcano -n volcano-system --create-namespace
```

## 十一、与默认调度器 / Other

| 维度 | K8s default | Volcano | YARN |
| ---- | ----------- | ------- | ---- |
| Gang | ❌ | ✔ PodGroup | ✔ Application |
| Queue | ❌ | ✔ | ✔ |
| Fairness | partial | DRF / Proportion | Capacity / Fair Scheduler |
| Priority | ✔ | ✔ | ✔ |
| 适合 | 微服务 | 批 / AI / HPC | 大数据 |

## 十二、典型用法

### 1. Tensorflow 分布式

- 多个 worker + parameter server
- gang scheduling
- priority 高

### 2. Spark on K8s

- Spark Operator + PodGroup
- 极简模式

### 3. AI 训练

- 8 张 GPU 机，作业至少 8 个 Pod
- 全局调度避开单点

### 4. HPC / MPI

- 多节点同网络约束
- topology plugin
- 队列独占

## 十三、最佳实践

- **minMember 要准确**：包括 driver + executor
- **Queue 设置**：分组别 / Team 设置 weight
- **timeout**：合理避免死锁
- **优先级分层**：实验 / 在线 / 紧急
- **资源 reclaim**：reclaimable=true 给在线，让批处理可回收
- **DRF 调度**：合理设置 CPU / Memory 的份额
- **metrics**：PodGroup Wait / Schedule 延迟

## 十四、监控

- Volcano Controller / Scheduler metrics endpoint
- Prometheus + Grafana：`volcano_*` 指标
- queue / podgroup status / gang-scheduled count

## 十五、生态结合

- KubeRay
- Spark Operator
- Kubeflow Training Operator
- TFOperator
- MPIOperator
- Argo Workflows

## 十六、版本演进

- v1.6：引入 DRF 主力与 Action
- v1.7+：Webhooks + Job 状态集成
- v1.9 (current)：加入 reservation / proportion
