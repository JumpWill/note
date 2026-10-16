# GPU 笔记

> 分两部分：**Part 1 硬件与软件基础认知**（不懂硬件就没法排障），**Part 2 在 K8s 里的使用**（调度、共享、切分、监控）。
>
> K8s 侧的安装/配置细节另见 [`../整体/26-GPU使用.md`](../整体/26-GPU使用.md)，本文只讲原理和决策依据。

## 章节

### Part 1 基础认知

| 章节 | 标题 | 主要内容 |
|------|------|---------|
| [01](01-GPU硬件与体系结构.md) | GPU 硬件与体系结构 | CPU/GPU 对比、SM、warp、发散、CUDA Core vs Tensor Core、NVLink/PCIe |
| [02](02-显存与性能模型.md) | 显存与性能模型 | 显存层次、带宽估算、算术强度、Roofline、OOM 怎么算 |
| [03](03-CUDA生态与驱动兼容.md) | CUDA 生态与驱动兼容 | driver/runtime、nvcc、cuDNN/cuBLAS、驱动-CUDA-框架版本矩阵、镜像选型 |

### Part 2 K8s 中的使用

| 章节 | 标题 | 主要内容 |
|------|------|---------|
| [04](04-K8s申请与调度GPU.md) | K8s 申请与调度 GPU | device plugin、extended resource、NFD、requests/limits、拓扑调度 |
| [05](05-GPU共享切分与隔离.md) | GPU 共享、切分与隔离 | 时间片、MPS、MIG、vGPU，选型对比 |
| [06](06-监控运维与排障.md) | 监控、运维与排障 | GPU Operator、DCGM Exporter、常见故障决策树 |

## 一句话路线

```text
为什么 GPU 快           → 01 并行度与延迟隐藏
为什么我的模型跑不动     → 02 算术强度 / Roofline / 显存
为什么 CUDA 报错了       → 03 驱动-运行时-框架版本矩阵
为什么 Pod 起不来        → 04 resource name / device plugin / Node
一张卡多人怎么分         → 05 timeSlicing / MPS / MIG
为什么卡利用率是 0       → 06 DCGM + 排障决策树
```

## 核心速查

```text
vGPU    = 物理显卡；nvidia-smi -L 看到几张就是几张
CUDA    = 驱动之上的一套 API + 运行时，版本独立于驱动演进
NVML    = 唯一官方的管理接口，nvidia-smi 就是它写的，K8s 侧全部走 NVML
显存    = 不可超卖资源，超了就 OOM（不像 CPU 会 swap）
MIG     = 硬件级切分，物理隔离，唯一真正安全的多租户方案
```

## 阅读顺序建议

- 只做 K8s 运维：`01 → 04 → 06`
- 调模型性能：`01 → 02 → 03`
- 做平台/多租户：`01 → 05 → 06`
