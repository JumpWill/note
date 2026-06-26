## 概念

DRA（Dynamic Resource Allocation）是 K8s 1.26+ 引入的 **Device Plugin 下一代架构**，用 **ResourceClaim / ResourceClaimTemplate** 取代旧的 `limits.nvidia.com/gpu` 静态分配方式。

* 起源：K8s SIG-Network + SIG-Node，参考了 KEP-3063
* 状态：1.30+ GA（GA 标志 `DynamicResourceAllocation=true`）

## 跟 Device Plugin 的区别

| 维度 | Device Plugin | DRA |
| --- | --- | --- |
| 资源声明 | Pod spec `resources.limits.nvidia.com/gpu: 1` | Pod spec `resourceClaims: my-claim` |
| 用户侧 | 静态字符串资源名 | 灵活的对象（带参数、约束） |
| 分配 | kubelet 跟 plugin gRPC 一次要资源 | 多个 ResourceClaim + 多次 allocate |
| 共享 / 拆分 | 靠 TimeSlicing / MIG | 内置 partial allocation / sharing |
| 参数化 | ❌ 只能整卡 | ✅ 可带 GPU 型号 / 显存 / 拓扑约束 |
| 调度 | kube-scheduler 不知 GPU 拓扑 | **调度器能感知**（通过 DRA scheduler plugin） |

## 核心 API

```yaml
# 1. DeviceClass（管理员定义资源池）
apiVersion: resource.k8s.io/v1
kind: DeviceClass
metadata:
  name: gpu
spec:
  selectors:
  - cel:
      expression: device.attributes["gpu.product"].value == "A100"

---
# 2. ResourceClaimTemplate（模板,Pod 用）
apiVersion: resource.k8s.io/v1
kind: ResourceClaimTemplate
metadata:
  name: gpu-a100
spec:
  spec:
    devices:
      requests:
      - name: gpu
        deviceClassName: gpu
        selectors:
        - cel:
            expression: device.attributes["memory"].value == "40Gi"

---
# 3. Pod 使用
apiVersion: v1
kind: Pod
metadata:
  name: train
spec:
  containers:
  - name: trainer
    image: my-training:latest
    resources:
      claims:
      - name: my-gpu
  resourceClaims:
  - name: my-gpu
    resourceClaimTemplateName: gpu-a100
```

## 架构

```
                  Pod
                   ↓ resourceClaims
       kube-scheduler（带 DRA plugin）
                   ↓ 决定 Pod 放哪、用哪个 Device
       DRA driver（如 gpu-dra-driver, NVIDIA 官方）
                   ↓ gRPC (ResourceSlice API)
       kubelet 注入 VF / GPU 到容器
```

* **ResourceSlice**：调度器看见的资源切片
* **DRA driver**：每个硬件厂商实现，Kubernetes-Resource-Allocator API
* **DRA scheduler plugin**：kube-scheduler 自带，不用单独装

## 主流 DRA driver

* **NVIDIA GPU DRA Driver**：NVIDIA 官方，1.30+ 可用
* **Intel QAT DRA**：Intel QuickAssist
* **Resource Claims Operator**：通用
* **cert-manager**：所有 CNCF 厂商都会出 DRA driver

## 启用

```bash
# kube-apiserver / kube-scheduler / kubelet / controller-manager 都加 feature gate
--feature-gates=DynamicResourceAllocation=true

# K8s 1.34+ 默认开启
```

## 优缺点

* ✅ **API 表达力强**：可声明 GPU 型号 / 显存 / 拓扑
* ✅ **调度感知**：scheduler 知道资源拓扑，比 DevicePlugin 灵活
* ✅ 支持 partial allocation（请求 2G 显存，给 4G 卡）
* ✅ 内置 sharing（多 Pod 共享卡）
* ✅ **K8s 原生 API**，未来 Device Plugin 会逐步退役
* ❌ **新特性**，生态在跟进（1.30 GA，1.34 默认）
* ❌ 老 DevicePlugin 短期内并存
* ❌ NVIDIA GPU DRA driver 仍在完善中
* ❌ 多卡拓扑（NVLink / NVSwitch）支持还在路上

## 适用场景

* **新集群 / 新硬件**，直接上 DRA
* AI 训练场景：要按型号 / 显存 / 拓扑选卡
* 复杂的资源请求（部分卡 / 共享卡）

## 一句话

**Device Plugin 的下一代，K8s 1.34+ 默认，新集群首选**。