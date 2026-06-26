## 概念

YuniKorn（Apache 顶级项目）是 **大数据 / 多租户** 场景的 K8s 调度器前身是 Apache Submarine + YARN，统一调度。

* 项目：<https://github.com/apache/yunikorn-core>（Apache TLP）
* 起源：Yahoo 内部大数据调度 → 捐给 Apache
* 定位：**YARN 的统一调度能力带到 K8s**

## 跟 Volcano 的区别

| 维度 | YuniKorn | Volcano |
| --- | --- | --- |
| 起源 | 大数据（YARN） | 批处理 / AI |
| 核心场景 | **多租户公平调度** | **Gang + 抢占** |
| 队列模型 | 嵌套队列（树状） | 平面队列 |
| 公平策略 | Fair / FIFO / Capacity | FIFO / Priority |
| Gang | 通过 task-group 支持 | **原生** |
| 大数据集成 | Spark / Flink / Hive 原生 | 通过 Operator |
| K8s 集成 | sidecar（**不替换 scheduler**） | 替换 scheduler（schedulerName=volcano） |
| 多租户 | **强** | 中 |

## 关键概念

### 队列（嵌套树）

```yaml
apiVersion: yunikorn.apache.org/v1alpha1
kind: Queue
metadata:
  name: root
spec:
  queues:
  - name: production
    queues:
    - name: ads
      resources:
        cpu: "100"
        memory: "200Gi"
    - name: search
      resources:
        cpu: "200"
        memory: "500Gi"
  - name: research
    resources:
      cpu: "50"
      memory: "100Gi"
```

* 嵌套（生产 → ads / search）
* 每层可设资源上限
* **Guaranteed + Maximum** 双限制

### 公平调度

* **Fair Scheduler**：空闲资源按权重分配
* **Capacity Scheduler**：按比例分配 + 借调
* **FIFO**：先进先出（默认）

### Placement Rules

```yaml
placementRules:
  - name: tag
    value: "namespace"
    create: true
  - name: user
    value: "user.name"
```

根据 namespace / user 自动建队列。

## 部署

```bash
# Helm
helm repo add yunikorn https://apache.github.io/yunikorn-release
helm install yunikorn yunikorn/yunikorn --namespace yunikorn --create-namespace

# K8s 默认 scheduler 不替换,YuniKorn 通过 webhook + admission controller 工作
```

## 架构

```
┌─── K8s apiserver ───────────┐
│  webhook (validation)        │
│  admission (queue 注入)       │
└──────────┬──────────────────┘
           ▼
┌─── YuniKorn Scheduler ──────┐
│  yunikorn-core (Go)          │
│  - 队列调度                   │
│  - 公平 / 容量算法             │
│  - 跟 K8s scheduler 协调      │
└──────────┬──────────────────┘
           ▼
   K8s 默认 scheduler 实际绑 Pod
```

* **不替换** K8s 默认 scheduler
* 通过 admission controller 给 Pod 注入 queue label
* 跟 K8s scheduler 协调完成绑定

## Spark on K8s

YuniKorn 自带 **Spark Operator + Spark on K8s** 集成：

```yaml
# spark-submit 配 queue 参数
spark-submit --conf spark.yunikorn.queue=production.ads ...
```

Spark executor pod 自动按队列调度，**比 Volcano 更适合大数据 workload**。

## 优缺点

* ✅ **多租户 / 公平调度最强**
* ✅ 嵌套队列 + Fair / Capacity 算法
* ✅ 不替换 K8s scheduler，**共存容易**
* ✅ Spark / Flink / Hive 原生集成
* ✅ Apache 治理，版本稳定
* ❌ Gang / 抢占比 Volcano 弱
* ❌ 学习曲线（队列模型）
* ❌ AI 训练场景不如 Volcano 直接

## 适用场景

* **大数据平台**（Spark on K8s / Flink）
* 多团队 / 多业务**资源公平共享**
* 已经有 YARN 经验，想迁 K8s
* 多租户 SaaS 平台

## 监控 / 排查

```bash
# UI（自带 web）
kubectl -n yunikorn port-forward svc/yunikorn-service 9889 9889

# 队列
kubectl get queues
kubectl describe queue root.production.ads

# 应用队列查看
# UI 上看树状队列 + 各队列资源使用
```

## 一句话

**多租户 / 大数据场景的公平调度器，队列模型完整，Spark / Flink 原生支持**。