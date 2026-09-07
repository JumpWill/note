# K8s GPU 使用详解

> K8s 原生不支持 GPU，需要借助 **Device Plugin** 机制让 Pod 能"看到"节点上的 GPU。
> 这篇从硬件基础 → 设备插件 → 资源模型 → 调度 → 监控 → 优化，完整讲清楚 GPU 在 K8s 里怎么用。

---

## 一、背景：K8s 为什么需要 GPU 支持

```text
AI / 机器学习 / 深度学习训练与推理 → 几乎全跑在 NVIDIA GPU 上
传统 K8s 只调度 CPU / 内存
要让 Pod 用上 GPU → 需要：
  1. 节点装好 GPU 驱动
  2. K8s 知道这台节点有 GPU
  3. Pod 能"申请"GPU 资源
  4. Pod 内能"看到"GPU 设备（NVIDIA Container Toolkit）

K8s 1.10+ 通过 Device Plugin 机制（GA）原生支持
```

**典型使用场景**：

```text
✅ 深度学习训练（PyTorch / TensorFlow / JAX）
✅ 模型推理（Triton / vLLM / TensorRT）
✅ CUDA 加速的科学计算
✅ 视频编解码、图像处理
✅ 仿真 / 渲染

❌ 不适合：
  - 通用计算（CPU 够用）
  - 跨节点 GPU 任务（性能差）
```

---

## 二、硬件 / 软件基础

### 2.1 GPU 厂商现状（K8s 生态里几乎只有 NVIDIA）

```text
NVIDIA  ←  主流，K8s 生态最完善
  - 消费级：RTX 4090 / 3090 / 2080 Ti（推理 / 实验）
  - 数据中心：T4 / L4 / L40 / A10 / A100 / H100 / H200
  - 高端：H100 / B200（Blackwell，2025+）
  - 中国特供：A800 / H800 / H20（受出口管制）

AMD  ←  增长中
  - MI250 / MI300X
  - ROCm 软件栈（CUDA 兼容层）
  - K8s 设备插件：ROCm Device Plugin

华为 昇腾  ←  国内自研
  - Ascend 910 / 310
  - Ascend Device Plugin
  - CANN 软件栈

寒武纪 / 燧原  ←  小众，特定场景
```

### 2.2 软件栈层次

```text
┌─────────────────────────────────────┐
│         应用（PyTorch / CUDA）        │
├─────────────────────────────────────┤
│        CUDA Runtime / cuDNN          │
├─────────────────────────────────────┤
│     NVIDIA 驱动（内核态）            │  ← 节点装这个
├─────────────────────────────────────┤
│           GPU 硬件                  │  ← 物理卡
└─────────────────────────────────────┘

K8s 这边要装：
  1. 节点层：nvidia-driver（容器外、内核态）
  2. 节点层：nvidia-container-toolkit（容器运行时钩子）
  3. 集群层：nvidia-device-plugin（DaemonSet，让 K8s 知道有 GPU）
  4. 可选：GPU Operator（一键装上面所有）
  5. 可选：DCGM Exporter（监控）
```

### 2.3 CUDA / cuDNN 版本对应

```text
CUDA 是 NVIDIA 的并行计算平台
cuDNN 是深度学习加速库

应用版本 ↔ CUDA ↔ 驱动版本必须匹配（大致关系）：

  CUDA 12.x  →  驱动 ≥ 525
  CUDA 11.8  →  驱动 ≥ 520
  CUDA 11.0  →  驱动 ≥ 450

查看当前驱动支持的最高 CUDA：
  nvidia-smi 右上角显示 "CUDA Version: 12.x"
  → 这是驱动能支持的最高 CUDA
  → 实际应用可以用 ≤ 这个版本的 CUDA
```

---

## 三、设备插件（Device Plugin）机制

### 3.1 原理

```text
K8s Device Plugin = 节点上跑的 gRPC 服务

  节点启动
    ↓
  Device Plugin 启动（DaemonSet）
    ↓
  探测本地 GPU 设备
    ↓
  调 K8s Node API 注册 GPU 资源
    → 节点 status 出现 nvidia.com/gpu: N
    ↓
  Pod 申请 nvidia.com/gpu
    ↓
  scheduler 调度到有 GPU 的节点
    ↓
  kubelet 调 Device Plugin 的 Allocate
    → 拿到设备路径 / 环境变量
    ↓
  容器启动时通过 nvidia-container-toolkit
    → 把 GPU 设备挂到容器里
    → 注入驱动库（驱动可在镜像外注入）
```

### 3.2 安装 NVIDIA Device Plugin

**方式 1：手动部署（YAML）**

```bash
# NVIDIA 官方
kubectl apply -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.14.0/nvidia-device-plugin.yml

# 国内镜像（GPU Operator 同源）
kubectl apply -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.14.0/nvidia-device-plugin.yml
```

**方式 2：Helm**

```bash
helm repo add nvdp https://nvidia.github.io/k8s-device-plugin
helm install nvidia-device-plugin nvdp/nvidia-device-plugin \
  --namespace nvidia-device-plugin \
  --create-namespace
```

**方式 3：GPU Operator（推荐生产）**

```bash
# 一键装好：驱动 + 容器工具包 + 设备插件 + DCGM
kubectl create namespace gpu-operator
helm repo add nvidia https://helm.ngc.nvidia.com/nvidia
helm install gpu-operator nvidia/gpu-operator \
  -n gpu-operator \
  --set driver.enabled=true
```

### 3.3 验证安装

```bash
# 1. 节点有 GPU 资源
kubectl describe node <gpu-node> | grep -A 10 "Allocatable"
# 看到 nvidia.com/gpu: 8  ← 8 张 GPU

# 2. 设备插件 Pod 跑起来
kubectl -n nvidia-device-plugin get pods
# NAME                             READY   STATUS
# nvidia-device-plugin-xxxxx       1/1     Running

# 3. 用一个简单 Pod 验证
kubectl run gpu-test --rm -it --image=nvidia/cuda:12.2.0-base-ubuntu22.04 \
  --limits=nvidia.com/gpu=1 -- nvidia-smi
```

---

## 四、GPU 资源模型（5 种共享方式）

```text
┌────────────────────────────────────────────────────┐
│                  GPU 资源模型                        │
│                                                    │
│  ① 整卡  ──── 1 Pod 1 GPU（默认）                  │
│  ② 显存  ──── 1 GPU 切多份（按显存大小）            │
│  ③ MIG   ──── A100/H100 硬件分区                    │
│  ④ Time-slicing ── 时间分片（驱动级）                │
│  ⑤ MPS   ──── 多进程服务（Ampere+）                 │
│                                                    │
└────────────────────────────────────────────────────┘
```

### 4.1 整卡（最简单）

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: gpu-pod
spec:
  containers:
  - name: app
    image: my-app:cuda
    resources:
      limits:
        nvidia.com/gpu: 1     # ← 申请 1 张整卡
```

```text
特点：
  - 独占一张 GPU
  - 显存不共享
  - 推理 / 训练通用
  - 适合：独占式工作负载

资源：nvidia.com/gpu: N（整卡数）
```

### 4.2 按显存切分（Memory Slice）

```yaml
# 修改 device plugin ConfigMap
# 启用 memory-based sharing
apiVersion: v1
kind: ConfigMap
metadata:
  name: nvidia-device-plugin
  namespace: nvidia-device-plugin
data:
  config.yaml: |
    version: v1
    sharing:
      strategy: "memory"          # ← 按显存切
      devices:
      - "0":                      # GPU 0
        memory:
          size: 4096              # 切 4GB
      - "1":                      # GPU 1
        memory:
          size: 8192              # 切 8GB
```

```yaml
# Pod 申请 4GB 显存
resources:
  limits:
    nvidia.com/gpu.memory: 4096
```

```text
特点：
  - 同一张卡可被多个 Pod 同时用
  - 每个 Pod 看自己分到的显存
  - 但**计算单元（SM）共享**，会有争抢
  - 适合：多个轻量推理任务

注意：这是 v0.13+ 的新特性（v1 API）
旧版本是 nvidia.com/gpu: 1 + 时间片
```

### 4.3 MIG（MULTI-INSTANCE GPU，硬件分区）

```text
适用硬件：A100 / H100（支持 MIG）
          A30 / H200 也支持

原理：
  - 把一张 A100（80G）切成最多 7 个 MIG instance
  - 每个 MIG 是独立的"小 GPU"（独立 SM / 显存 / 编码器）
  - 硬件级隔离，性能稳定

常见切分（7-way）：
  - 1 个 5g.10gb（5/7 算力，10GB 显存）
  - 2 个 3g.20gb（3/7 算力，20GB 显存）
  - 3 个 2g.20gb（2/7 算力，20GB 显存）
  - 7 个 1g.10gb（1/7 算力，10GB 显存）
```

```bash
# 1. 节点上开启 MIG
nvidia-smi -mig 1

# 2. 创建 MIG instance
nvidia-smi mig -cgi 9,9,9,9,9,9,9 -C   # 7 个 1g.10gb

# 3. K8s 里申请 MIG
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: app
    resources:
      limits:
        nvidia.com/mig-1g.10gb: 1   # ← MIG profile 名作为资源
```

```text
特点：
  - 硬件隔离，性能稳定
  - 适合：多租户 / 多推理任务
  - 不支持：H100 的部分切分、训练（一般不超 1 个 MIG）
```

### 4.4 Time-Slicing（时间分片）

```yaml
# ConfigMap 配置
data:
  config.yaml: |
    version: v1
    sharing:
      strategy: "time-slicing"
      devices:
      - "0":
        time-slicing:
          replicas: 4           # ← 把这张卡虚拟成 4 份
      - "1":
        time-slicing:
          replicas: 2           # 另一张虚拟成 2 份
```

```text
特点：
  - 驱动级时间分片
  - 多 Pod 共享同一张卡，按时间轮转
  - 不是真"并行"，但用起来是并行的
  - 适合：调试 / 轻量推理（多个低 QPS 模型）
  - 不适合：训练 / 高负载推理（会互相挤占）

资源：节点上显示 nvidia.com/gpu: 6（原本 2 卡，扩成 4+2=6）
```

### 4.5 MPS（Multi-Process Service）

```text
适用硬件：Ampere 架构（A100 / A10 / A40 / RTX 30 系列）

原理：
  - 把一张 GPU 的计算资源（SM）按比例分给多个进程
  - 比 time-slicing 更高效（开销小）
  - 显存仍共享（需要自己限制）
  - 适合：CUDA kernel 密集但不是显存密集的场景

启用：
  1. 节点启动 nvidia-cuda-mps-control
  2. Pod 设置环境变量
     NVIDIA_MPS_ACTIVE_THREAD_PERCENTAGE=50
```

**5 种方式对比**：

| 方式 | 隔离性 | 性能损失 | 显存隔离 | 适用 |
| --- | --- | --- | --- | --- |
| **整卡** | 100% | 0% | 100% | 训练 / 独占推理 |
| **MIG** | 100% 硬件 | 0% | 100% | 多租户 / 隔离推理 |
| **显存切** | 弱 | 中（SM 争抢） | 强 | 多个轻量推理 |
| **Time-slicing** | 弱 | 中（轮转） | 弱 | 调试 / 演示 |
| **MPS** | 中 | 小 | 弱 | 计算密集 / 显存小 |

---

## 五、Pod 使用 GPU 实战

### 5.1 最小可用 Pod

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: cuda-test
spec:
  containers:
  - name: cuda
    image: nvidia/cuda:12.2.0-base-ubuntu22.04
    command: ["nvidia-smi"]
    resources:
      limits:
        nvidia.com/gpu: 1
```

### 5.2 申请多卡（训练任务）

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: ddp-training
spec:
  containers:
  - name: trainer
    image: my-training:v1
    command: ["python", "train.py", "--gpus", "4"]
    resources:
      limits:
        nvidia.com/gpu: 4       # ← 4 张卡
    env:
    - name: NCCL_DEBUG
      value: "INFO"
    - name: NCCL_IB_HCA
      value: "mlx5"             # ← 走 RDMA 网络
```

### 5.3 申请部分显存

```yaml
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: inference
    image: vllm:latest
    resources:
      limits:
        nvidia.com/gpu.memory: 8192   # ← 8GB 显存
```

### 5.4 MIG 申请

```yaml
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: inference
    image: triton:latest
    resources:
      limits:
        nvidia.com/mig-1g.10gb: 1
```

### 5.5 节点选择器 / 污点容忍

```yaml
# GPU 节点加污点
apiVersion: v1
kind: Node
metadata:
  name: gpu-node-1
spec:
  taints:
  - key: nvidia.com/gpu
    value: "present"
    effect: NoSchedule
---
# Pod 加容忍
spec:
  tolerations:
  - key: nvidia.com/gpu
    operator: Exists
    effect: NoSchedule
  nodeSelector:
    nvidia.com/gpu.product: NVIDIA-A100-SXM4-80GB   # 指定卡型
```

### 5.6 调试 / 工具 Pod

```bash
# 进入节点看 GPU
kubectl debug node/gpu-node-1 -it --image=nvidia/cuda:12.2.0-base-ubuntu22.04
# 在 Pod 里 nvidia-smi

# 或起一个带 GPU 的工具 Pod
kubectl run gpu-tools --rm -it \
  --image=nvidia/cuda:12.2.0-base-ubuntu22.04 \
  --limits=nvidia.com/gpu=1 \
  -- nvidia-smi
```

---

## 六、GPU 调度

### 6.1 默认调度行为

```text
K8s 默认：
  - 调度器认 nvidia.com/gpu: N
  - 找有空闲 GPU 的节点
  - 一张卡只能被一个 Pod 用（按整卡申请时）

问题：
  - 不会感知显存用量
  - 不会优先调度到空闲卡多的节点
  - 多任务争抢时容易 OOM
```

### 6.2 扩展调度器

```text
NVIDIA GPU Operator 装好之后会带：
  - Node Feature Discovery (NFD)：标签节点特性
  - GPU Feature Discovery (GFD)：给节点打 GPU 标签

可以基于这些标签调度：
  - gpu.product：卡型（A100 / H100 / T4）
  - gpu.memory：显存大小
  - gpu.count：卡数
```

### 6.3 高级调度方案

| 工具 | 能力 |
| --- | --- |
| **Volcano** | Gang scheduling（分布式训练一组 Pod 一起调度） |
| **Kueue** | 任务队列 / 资源配额 / 抢占 |
| **Koordinator** | GPU 拓扑感知 / 混部 |
| **Yunikorn** | 大数据 / AI 任务调度 |
| **K8s scheduler plugins** | 自定义插件扩展 |

**分布式训练调度示例（Volcano）**：

```yaml
apiVersion: scheduling.volcano.sh/v1beta1
kind: PodGroup
metadata:
  name: ddp-training
spec:
  minMember: 4                # 必须 4 个 Pod 都调度成功
  minResources:               # 总共要这么多资源
    cpu: "8"
    memory: "32Gi"
    nvidia.com/gpu: 4
  queue: default
```

---

## 七、GPU 监控

### 7.1 DCGM Exporter（推荐）

```bash
# GPU Operator 默认会装
# 监听 :9400 端口，暴露 Prometheus 指标

# 关键指标：
#   DCGM_FI_DEV_GPU_UTIL         GPU 利用率（%）
#   DCGM_FI_DEV_GMEM_USED        显存用量（MB）
#   DCGM_FI_DEV_GMEM_FREE        显存空闲
#   DCGM_FI_DEV_GMEM_TOTAL       显存总量
#   DCGM_FI_DEV_GPU_TEMP         温度
#   DCGM_FI_DEV_POWER_USAGE      功耗
#   DCGM_FI_DEV_SM_CLOCK         SM 时钟
#   DCGM_FI_DEV_ECC_DBE_VOL_TOTAL 显存 ECC 错误
```

### 7.2 ServiceMonitor

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: dcgm-exporter
  namespace: gpu-operator
spec:
  selector:
    matchLabels:
      app: nvidia-dcgm-exporter
  endpoints:
  - port: metrics
    interval: 15s
```

### 7.3 关键 PromQL

```promql
# 集群 GPU 利用率（按节点）
avg by (instance) (DCGM_FI_DEV_GPU_UTIL)

# 集群显存使用率
DCGM_FI_DEV_GMEM_USED / DCGM_FI_DEV_GMEM_TOTAL

# 集群 GPU 数量
count(DCGM_FI_DEV_GPU_UTIL)

# 整集群平均利用率
avg(DCGM_FI_DEV_GPU_UTIL)

# 空闲 GPU 数量（利用率 < 10%）
count(DCGM_FI_DEV_GPU_UTIL < 10)

# 温度告警
DCGM_FI_DEV_GPU_TEMP > 85
```

### 7.4 告警规则

```yaml
groups:
- name: gpu
  rules:
  - alert: GPUTemperatureHigh
    expr: DCGM_FI_DEV_GPU_TEMP > 85
    for: 5m
    labels: { severity: warning }
    annotations:
      summary: "GPU 温度过高"

  - alert: GPUMemoryHigh
    expr: DCGM_FI_DEV_GMEM_USED / DCGM_FI_DEV_GMEM_TOTAL > 0.95
    for: 5m
    labels: { severity: warning }
    annotations:
      summary: "GPU 显存几乎打满"

  - alert: GPUPowerHigh
    expr: DCGM_FI_DEV_POWER_USAGE > 350  # A100 上限 400W
    for: 10m
    labels: { severity: info }
    annotations:
      summary: "GPU 持续高功耗"

  - alert: GPULowUtilization
    expr: avg by (instance) (DCGM_FI_DEV_GPU_UTIL) < 10
    for: 30m
    labels: { severity: info }
    annotations:
      summary: "GPU 长时间低利用率（可能浪费）"
```

---

## 八、GPU 运维常见操作

### 8.1 驱动升级

```bash
# 用 GPU Operator 升级最方便
# 改 Helm values：
helm upgrade gpu-operator nvidia/gpu-operator -n gpu-operator \
  --set driver.version=550.54.15

# Operator 会自动：
#  1. 隔离节点（cordon）
#  2. 驱逐 Pod
#  3. 卸载旧驱动
#  4. 装新驱动
#  5. 恢复节点（uncordon）
```

### 8.2 节点故障处理

```bash
# 现象：节点 nvidia-smi 失败
ssh node1
$ nvidia-smi
# NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver

# 排查：
$ ls /proc/driver/nvidia/
# 不存在 → 驱动未加载

# 解决：
$ sudo nvidia-modprobe -u
# 或重启节点
```

### 8.3 XID 错误（GPU 硬件错误）

```bash
# XID = GPU 内核事件码
# dmesg | grep -i "NVRM: Xid"
# 常见 XID：
#   XID 31: GPU 挂起
#   XID 43: PCIe 总线错误
#   XID 48: 双比特 ECC 错误（不可恢复）
#   XID 63: 显存页退役
#   XID 74: NVLink 错误

# 严重错误（48 / 79）→ 立即 cordon 节点
```

### 8.4 MIG 重配置

```bash
# 删除所有 MIG instance
nvidia-smi mig -dci all -dgi all

# 创建新的 MIG 切分
nvidia-smi mig -cgi 9,9,9,9,9,9,9 -C

# 验证
nvidia-smi
# 应该看到 MIG 设备
```

---

## 九、GPU 优化

### 9.1 调度优化

```text
1. 拓扑感知（NUMA）
   - 节点是多 NUMA，GPU 在 NUMA 0
   - 调度器把 CPU 任务也放 NUMA 0
   - 减少跨 NUMA 访问

2. 节点亲和
   - A100 / H100 节点不混部 T4
   - 避免任务用错卡型

3. Pod 拓扑打散
   - topologySpreadConstraints 让多卡训练 Pod 分散到不同节点
   - 避免一个节点挂掉影响多任务
```

### 9.2 网络优化（分布式训练）

```text
多机训练 → 节点间通信（梯度同步）：

  ① 走 RDMA / InfiniBand（最佳）
     - 需要 Mellanox NIC
     - Pod 配 hostNetwork + SR-IOV
     - 用 NCCL 走 IB 协议

  ② 走 RoCE（RDMA over Converged Ethernet）
     - 普通以太网卡跑 RDMA
     - 性能接近 IB，部署简单

  ③ 走普通 TCP/IP（最差）
     - 默认行为
     - 训练慢 5-10x

关键环境变量：
  NCCL_IB_HCA=mlx5              # 用 Mellanox 5 网卡
  NCCL_SOCKET_IFNAME=eth0       # 走哪个网口
  NCCL_DEBUG=INFO               # 调试信息
```

### 9.3 存储优化（数据加载）

```text
训练时数据加载经常成为瓶颈：

1. 高吞吐分布式存储
   - Lustre / GPFS / CephFS
   - 挂到 Pod 里，避免镜像打包数据

2. 本地 NVMe 缓存
   - PV 用节点本地盘
   - 第一次拉数据到本地，后续走本地
   - DaemonSet 维护数据

3. 内存缓存
   - 数据集放内存 / tmpfs
   - 适合小数据集（< 100GB）

4. 数据并行加载
   - DataLoader 用多个 worker
   - 配合 prefetch
```

### 9.4 显存优化

```text
训练时显存容易爆：

1. 混合精度训练
   - 开启 AMP（autocast + GradScaler）
   - 显存减半，速度不变或更快

2. 梯度累积
   - 减小 batch size，增加累积步数
   - 显存减少 1/N

3. 梯度检查点
   - 牺牲计算换显存
   - 显存减少 60-70%，训练慢 30%

4. ZeRO（DeepSpeed）
   - 优化器状态分片
   - ZeRO-1/2/3 逐级优化

5. LoRA / QLoRA
   - 冻结大模型大部分参数
   - 只训少量 LoRA 适配器
   - 7B 模型训练只需 16GB 显存
```

---

## 十、常见问题

### 10.1 Pod 起不来：找不到 GPU 设备

```text
症状：
  Pod 一直 Pending
  Events: failed to allocate device plugin resource nvidia.com/gpu

排查：
  1. 节点有 GPU 资源吗？
     kubectl describe node <node> | grep nvidia.com/gpu
  2. 设备插件跑起来了吗？
     kubectl -n nvidia-device-plugin get pods
  3. 节点驱动装了吗？
     ssh node && nvidia-smi
  4. 容器运行时支持 nvidia 吗？
     /etc/docker/daemon.json 或 containerd 配置
     → 需要 nvidia-container-runtime
```

### 10.2 容器内 nvidia-smi 失败

```text
症状：
  Pod 起来了，但 nvidia-smi 报错

排查：
  1. 镜像里有没有 CUDA 库？
     docker run --runtime=nvidia <image> nvidia-smi
  2. 驱动版本支持应用 CUDA 版本吗？
     驱动支持的最高 CUDA ≥ 应用 CUDA
  3. 设备真的挂进来了吗？
     ls /dev/nvidia*  （容器内）
```

### 10.3 训练速度慢

```text
排查：
  1. GPU 利用率多少？
     nvidia-smi
     → < 50% 说明数据加载是瓶颈
  2. 显存使用情况？
     → 太低 → batch size 太小
     → 太高 → 可能 OOM
  3. 多卡通信？
     NCCL_DEBUG=INFO 看
     → 走 IB 还是 TCP
  4. 节点资源争抢？
     → 同一节点有别的任务挤占 CPU
```

### 10.4 OOM 错误

```text
症状：
  RuntimeError: CUDA out of memory
  或 Pod 被 OOM Kill

解决：
  1. 减小 batch size
  2. 混合精度训练
  3. 梯度累积
  4. 申请更大显存（换大卡 / MIG 切大份）
  5. 检查内存泄漏（rare but possible）
```

---

## 十一、生产部署清单

```text
部署前：
  ☐ 选 GPU 型号（A100 / H100 / L40 / T4 ...）
  ☐ 节点 BIOS 开启 SR-IOV / IOMMU
  ☐ 装好 NVIDIA 驱动（推荐用 GPU Operator 管）
  ☐ 装好 nvidia-container-toolkit
  ☐ 验证 nvidia-smi 正常
  ☐ 准备容器镜像（CUDA + cuDNN + 应用）

部署中：
  ☐ 装 GPU Operator
  ☐ 装 DCGM Exporter（监控）
  ☐ 配 Prometheus / Grafana
  ☐ 配告警规则
  ☐ 测试一个 GPU Pod 能起来

部署后：
  ☐ 验证利用率 dashboard
  ☐ 配置调度器特性（拓扑 / 亲和）
  ☐ 配置网络（RDMA / IB）
  ☐ 配置存储（高速 / 本地）
  ☐ 跑性能基准（vs 裸机）
```

---

## 十二、工具速查

| 工具 | 作用 | 部署方式 |
| --- | --- | --- |
| **nvidia-driver** | 驱动 | GPU Operator / 手动 |
| **nvidia-container-toolkit** | 容器运行时 | GPU Operator / 手动 |
| **nvidia-device-plugin** | K8s 设备插件 | DaemonSet |
| **GPU Operator** | 一键装上面所有 | Helm |
| **DCGM** | 监控 | GPU Operator 包含 |
| **DCGM Exporter** | Prometheus 指标 | GPU Operator 包含 |
| **Node Feature Discovery** | 节点特性发现 | GPU Operator 包含 |
| **GPU Feature Discovery** | GPU 标签 | GPU Operator 包含 |
| **Volcano** | 分布式训练调度 | Helm / Operator |
| **Kueue** | 任务队列 | Operator |
| **Run:ai** | AI 平台 | 商业 |

---

## 十三、一句话总结

> **K8s 用 GPU = 装 NVIDIA 驱动 + 装 Device Plugin（让 K8s 看到卡） + Pod 申请 nvidia.com/gpu**；
> 共享方式按场景选：**整卡训练 / MIG 切分多租户 / 显存切分轻量推理 / Time-slicing 调试**；
> 必装 **GPU Operator**（一键搞定驱动 + 工具包 + 插件）和 **DCGM Exporter**（监控）。

---

## 十四、参考

- [NVIDIA Device Plugin](https://github.com/NVIDIA/k8s-device-plugin)
- [NVIDIA GPU Operator](https://github.com/NVIDIA/gpu-operator)
- [Kubernetes 官方文档 - GPU](https://kubernetes.io/docs/tasks/manage-gpus/scheduling-gpus/)
- [DCGM Exporter](https://github.com/NVIDIA/dcgm-exporter)
- [Volcano](https://github.com/kubernetes-sigs/volcano)
- [Kueue](https://github.com/kubernetes-sigs/kueue)
- [K8s MIG 文档](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/mig-manager.html)
