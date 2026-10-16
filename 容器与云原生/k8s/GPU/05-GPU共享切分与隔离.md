# GPU 共享、切分与隔离

> 核心问题：**一张卡给几个 Pod 用？** 四种方案的隔离性和性能差别巨大，选错会串数据或白烧钱。

## 一、四种方案总览

| 方案 | 层 | 隔离 | 性能损失 | 并发上限 | 适用 |
|------|---|------|---------|---------|------|
| 原生独占 | 无 | 物理 | 0 | 1 Pod/卡 | 训练、大模型推理 |
| Time-Slicing | 调度器 | 无（靠 CUDA context 切换） | 20~40% | 副本数 | 开发测试、小模型 |
| MPS | CUDA 运行时 | 进程级 | 5~15% | 16~32 client | 多进程小模型推理 |
| MIG | 硬件 | **硬件级** | 0~5% | 7/8 个实例 | 多租户生产推理 |
| vGPU | 虚拟化 | 强 | 5~15% | 按时间分 | 强隔离多租户 |

一句话选择：

```text
要安全隔离、多租户      → MIG（vGPU 商业场景）
要一堆小模型并发推理     → MPS
只是想让开发环境能跑起来 → Time-Slicing
训练 / 单个大模型       → 独占，别切
```

## 二、Time-Slicing（最简单）

device plugin 配置里打开，让 `nvidia.com/gpu: 1` 支持多副本：

```yaml
# ConfigMap: time-slicing-config
apiVersion: v1
kind: ConfigMap
metadata:
  name: time-slicing-config
  namespace: gpu-operator
data:
  time-slicing-config.yaml: |
    version: v1
    timeSlicing:
      - resourceName: nvidia.com/gpu
        replicas: 4          # 4 个 Pod 共享 1 张卡
```

```bash
kubectl apply -f time-slicing-config.yaml
# 改完要重启 device plugin / operator
```

原理：多个 CUDA context 在**整张卡上轮转时间片**，类似 CPU 时间片。

问题：

- **显存按比例静态切分**，一个 Pod 崩了它那部分显存可能不释放
- 上下文切换有开销，**并发越高单 Pod 越慢**（4 个 Pod 不等于 4 倍吞吐，可能只有 1.5~2 倍）
- **完全没有隔离**：一个 Pod 越界/崩溃可能影响同卡其他 Pod
- 官方明确说 time-slicing 是过渡方案，不是生产多租户方案

```yaml
resources:
  limits:
    nvidia.com/gpu: 1     # 4 个这样的 Pod 会落在同一张卡上
```

## 三、MPS（Muda Multi-Process Service）

MPS 是 CUDA 自带的**真正的多进程服务**，所有 client 共享一个 CUDA context，避免 context 切换和显存重复映射。

```bash
# 1. 以 root 启动 mps daemon
nvidia-cuda-mps-control -d

# 2. 设置客户端环境变量后启动进程
export CUDA_MPS_ACTIVE_THREAD_PERCENTAGE=20   # 每个 client 拿 20% 显存
export CUDA_MPS_SERVER_LENGTH=1024
python app.py
```

显存按 `CUDA_MPS_ACTIVE_THREAD_PERCENTAGE` 分配，各 client 的 kernel 可以**真正并发执行**（靠硬件并发调度，不是轮转）。

| 优势 | 劣势 |
|------|------|
| 无切换开销，并发性能远好于 time-slicing | 需要常驻 daemon，运维复杂 |
| 每个 client 有独立进程空间 | 客户端之间仍无显存硬隔离 |
| 吞吐可扩展性好 | 需要固定方式部署，不如 device plugin 声明式 |

**MPS 与 K8s 的矛盾**：daemon 是节点级的，不是 Pod 级的。GPU Operator 有 `mps-daemon` 部署模式（hostPID + 挂载），但本质上是个绕过调度器的常驻进程。

实践：MPS 更适合**在一个大 Pod 里跑多个 worker 进程**，而不是多个 Pod 共享卡。

```yaml
containers:
  - name: vllm
    command: ["/bin/bash", "-c", "vllm serve ... --workers 4 --data-parallel-size 4"]
```

## 四、MIG（Multi-Instance GPU）

**硬件级切分**：A100 / H100 物理上把一颗 SM、一块显存、一套 L2 切成若干实例，每个实例是独立的 GPU，有独立的显存控制器带宽。

```bash
# 1. 查看支持的 profile
nvidia-smi mig -lgip

# ── MIG profiles example ──
# GPU instance  Profile  GPU Mem  Compute  SM  Enc  Dec
# 1            1g.10gb  10GB    14%      14   1    1
# 2            2g.20gb  20GB    28%      28   2    2
# 7            7g.40gb  40GB    98%      98   7    7
```

```bash
# 2. 在所有卡上应用（会销毁现有进程）
nvidia-smi mig -i 0 -CGI 1g.20gb+2g.20gb   # 切 3 个实例，大小不同
# GPU Operator 用 MIG Manager Daemon 自动做这件事

# 3. 看切分结果
nvidia-smi mig -lgip -i 0
nvidia-smi -L     # 切完后一个物理卡出现多个 UUID

# 4. 重启后默认重建 / 清空
nvidia-smi mig -rmi all      # 释放所有实例
```

### K8s 中的资源名变了

```yaml
resources:
  limits:
    nvidia.com/mig-1g.5gb: 1     # MIG 资源名 = <resource>-<profile>
```

启用：GPU Operator 配置 `nvidiaClusterConfig.migManager.enabled=true`，NFD 会打上 `nvidia.com/mig.capable=true` 的标签。

### MIG 的关键特性

| 特性 | 说明 |
|------|------|
| 隔离 | **硬件级**：一个实例崩溃不影响其他实例，无法访问别人的显存 |
| 性能 | 几乎无损失（各实例有独立 L2 和显存带宽配额） |
| 显存 | 静态划分，声明了 10GB 就用不了 11GB（碎片问题） |
| 切分后 | **不可扩容**，要换 profile 必须销毁重建 Pod |
| 限制 | 只在 A100 及以后、Ampere 及以后架构支持；L40S 支持 MIG 但不支持 1g.4gb 等小 profile |
| K8s 代价 | **只能整机统一切**，没法调度器粒度地按需切分 |

> **MIG 的调度痛点**：切了 7g.40gb 剩 40GB 不能给别人的 20GB 模型用。要么浪费，要么混切不同 profile。解决靠 MIG Manager 的 all-reduce/partition 策略。

GPU Operator 的策略：

```yaml
# mixed：允许不同 profile 混切（默认）
# single：所有实例用同一 profile，利用率更整齐
nvidiaClusterConfig:
  migManager:
    enabled: true
    migStrategy:
      shared:
        - MIG-enabled: true
          strategy: mixed      # or single
```

## 五、vGPU

NVIDIA vGPU 把物理卡虚拟成多个 vGPU profile（vCS 独占、vWS 半虚拟化），由 NVIDIA License Server 管理授权。

- 隔离强、粒度细、可动态调整
- **需要企业订阅 + License Server**，社区版不能随便用
- K8s 靠 NVIDIA vGPU Operator，配置比 device plugin 复杂

2026 年社区更推荐 MIG 或云厂商托管实例。

## 六、其他隔离手段

即使不切卡，多租户还需要：

```yaml
# 1. 显存硬限制：time-slicing 下配额
env:
  - name: CUDA_MPS_ACTIVE_THREAD_PERCENTAGE
    value: "30"
  # 时间片模式下无配额能力，只能靠 MPS

# 2. 计算模式（节点级，限制单进程用满卡）
nvidia-smi -c 0   # 0=Default 1=Exclusive_Process 2=Prohibited
# Exclusive_Process：一个 context 独占整卡，第二个进程直接失败
# 优点：显存天然隔离，缺点：独占，卡利用率低时浪费

# 3. 容器内 UID 隔离：NVML 只暴露授权 GPU
# device plugin 会自动把非授权设备从容器中隐藏

# 4. ResourceQuota + LimitRange
apiVersion: v1
kind: LimitRange
metadata:
  name: gpu-limits
spec:
  limits:
    - type: Container
      default:
        nvidia.com/gpu: "1"      # 租户默认只能 1 张
      defaultRequest:
        nvidia.com/gpu: "1"
```

## 七、决策流程

```text
问：这是训练还是推理？
├─ 训练 → 独占。显存不够就换卡或切模型并行，别切卡
└─ 推理
   ├─ 模型很大（> 半张卡）→ 独占，或 MIG 大 profile
   ├─ 多租户且互相不能影响 → MIG（A100+）或 vGPU（商业）
   ├─ 单租户多个小模型 → MPS 或多 Pod time-slicing
   └─ 纯开发测试 → time-slicing，replicas: 4 就够
```

性能经验值（MIG 1g.10gb × 4 vs 单进程独占 A100 40GB）：

| 场景 | 吞吐相对独占 |
|------|------------|
| MIG 4×1g.10gb 跑小模型 | ~70~80% |
| MPS 8 client | ~85~90% |
| Time-Slicing 4 副本 | ~40~60% |
| MIG 1g 跑大模型（放不下） | 直接 OOM |

## 小结

- Time-slicing 无隔离、有性能损失，只适合开发测试。
- MPS 是真正的多进程并发，吞吐好，但部署非声明式。
- MIG 是硬件隔离，性能损失最小，是生产多租户推理的首选（A100+）。
- 切分的代价是显存碎片和静态性，调度策略要一起设计。
