## 概念

Volcano 是 **CNCF incubating** 的 **批处理 / AI / 高性能计算调度器**，专门为 K8s 默认调度器不擅长的场景设计：AI 训练、Spark、HPC、基因计算、TensorFlow / PyTorch 分布式训练。

* 项目：<https://github.com/volcano-sh/volcano>
* 设计：**基于 kube-scheduler 框架**（Scheduler Plugin），扩展而不是替换
* 起源：华为云开源

## 默认调度器的问题

K8s 默认调度器是 **Pod-by-Pod**：

* 单 Pod 调度，不考虑 Pod 之间的关系
* 不懂 Gang（All-or-Nothing）语义
* 不懂优先级 / 抢占 / 队列 / 公平调度
* 不懂 GPU 拓扑 / NVLink

**Volcano 解决这些**。

## 核心概念

### 1. Job（VolcanoJob / VCJob）

```yaml
apiVersion: batch.volcano.sh/v1alpha1
kind: VolcanoJob
metadata:
  name: tf-training
spec:
  schedulerName: volcano
  minAvailable: 4            # Gang 语义:必须 4 个 Pod 同时调度成功才算 OK
  tasks:
  - replicas: 4
    name: worker
    template:
      spec:
        containers:
        - name: tf
          image: tensorflow/tensorflow:latest-gpu
          resources:
            limits:
              nvidia.com/gpu: 1
        restartPolicy: OnFailure
```

* **minAvailable** 决定 Gang：少一个就全部不调度，避免"集群卡一半"
* **tasks**：一个 Job 里可以有多个 task（如 ps / worker / evaluator）

### 2. Queue

```yaml
apiVersion: scheduling.volcano.sh/v1beta1
kind: Queue
metadata:
  name: research
spec:
  weight: 1
  reclaimable: false
  capability:
    cpu: "100"
    memory: "200Gi"
```

* 队列有**资源上限 + 权重**
* 超过 capacity 的 Job **排队等待**
* **抢占**：高优先级 Job 来了可以挤掉低优先级（reclaimable=true 才允许被抢占）

### 3. PriorityClass

```yaml
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: high
value: 1000
globalDefault: false
```

Job 可以指定 PriorityClass，决定**抢占顺序**。

## 关键插件

Volcano 自带的一组 Scheduler Plugin：

* **gang**：Gang 语义（all-or-nothing）
* **priority**：优先级 + 抢占
* **capacity / queue**：队列资源管理
* **nodeorder / binpack**：调度评分（节点选择）
* **DRF**（Dominant Resource Fairness）：多资源公平调度
* **predicates**：节点过滤
* **SLA**：deadline / 任务超时
* **topology / numa-aware**：GPU / NUMA 拓扑感知

## 部署

```bash
# 1. kubectl apply（默认）
kubectl apply -f https://raw.githubusercontent.com/volcano-sh/volcano/master/installer/volcano-development.yaml

# 2. 或 Helm
helm repo add volcano-sh https://volcano-sh.github.io/helm-charts
helm install volcano volcano-sh/volcano --namespace volcano-system --create-namespace
```

## 与 K8s 默认调度器共存

* 默认调度器继续管**普通 Pod**
* Volcano 调度器接管标了 `schedulerName: volcano` 的 Job / PodGroup

```yaml
spec:
  schedulerName: volcano
  ...
```

## 优缺点

* ✅ **批处理 / AI 训练 / HPC 标准方案**
* ✅ Gang 语义 + 队列 + 优先级 + 抢占 + DRF 全套
* ✅ 跟 KubeRay / Spark Operator / PyTorch Operator 集成
* ✅ 跟 DRA 配合可感知 GPU 拓扑
* ✅ 中文社区 + 文档强
* ❌ VolcanoJob 是新 CRD，老 Job 迁移要改 yaml
* ❌ 队列管理配置较复杂
* ❌ 跟 HPA / KEDA 集成要自己写
* ❌ 集群已有默认调度器时，**两套调度规则并存容易混乱**

## 适用场景

* **AI 训练**（PyTorch / TensorFlow 分布式）
* **Spark on K8s**（替代 spark-on-k8s-operator 的部分调度）
* **HPC / 基因计算 / 仿真**
* 任何需要 **Gang / 队列 / 抢占** 的批处理

## 监控 / 排查

```bash
# volcano-controller 状态
kubectl -n volcano-system get pods

# 队列
kubectl get queue
kubectl describe queue research

# Job
kubectl get vjobs
kubectl describe vjob tf-training

# 看 Pending 原因
kubectl describe pod <pending-pod> | grep Events
```

## 一句话

**AI 训练 / HPC / Spark 场景的批调度器，Gang + Queue + Priority 必备**。