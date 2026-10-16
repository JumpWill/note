# GPU 硬件与体系结构

> 目标：解释「为什么 GPU 快」和「GPU 和 CPU 的编程模型差在哪」——这两点决定后面所有调度、切分、OOM 决策。

## 一、CPU vs GPU：不是同一种东西

| 维度 | CPU | GPU |
|------|-----|-----|
| 核心数量 | 8~128 个，复杂 | 数千~上万个，简单 |
| 每个核心 | 乱序执行、分支预测、大缓存 | SIMD，无分支预测、小缓存 |
| 擅长 | 单线程延迟、串行逻辑、IO | 大规模规则并行 |
| 内存 | 几百 MB，带宽 100GB/s 级 | 显存 24~141GB，带宽 1~3TB/s |
| 上下文切换 | ns | warp 之间无成本，kernel 之间 μs 级 |

一句话：**CPU 赌单线程跑得快，GPU 赌线程多到能掩盖延迟**。

### 为什么 GPU 适合矩阵运算

矩阵乘法是数据无关的规整计算：每个输出元素都做同样的操作，互不依赖，可以几万线程同时开工，且访存地址连续（coalesced）。这是 GPU 的舒适区。

不适合的：分支多、指针跳转（链表、虚函数）、小矩阵（launch 开销大于计算）。

## 二、核心执行单元：SM 与 warp

```text
GPU
 └─ GPC（图形处理集群）
     └─ SM（Streaming Multiprocessor）  ~80~132 个
         ├─ CUDA Core / Tensor Core    128 个（分 4 个 sub-partition）
         ├─ Register File             256KB
         ├─ Shared Memory + L1 Cache  128~228KB（同一块硬件，配置不同）
         ├─ Warp Scheduler × 4        每个 sub-partition 一个
         └─ Load/Store Unit
     └─ L2 Cache（几 MB~几十 MB，全卡共享）
 └─ 显存（GDDR6/GDDR6X/HBM2e/HBM3）
```

### warp

- 一个 warp = **32 个线程**，同属一个 sub-partition，由**同一个 warp scheduler 轮流发射指令**。
- 硬件的 SIMD 宽度就是 32，这是所有性能陷阱的根源。
- 一个 sub-partition 同一时刻只能执行 1 个 warp 的指令 → 多放几个 warp 才有流水线可填（这叫 **ILP/TLP 隐藏延迟**）。

### warp 发散（warp divergence）

```cuda
if (threadIdx.x % 2 == 0) { a = f(x); } else { a = g(x); }
// 一个 warp 里两种分支都有 → 两条路径串行执行各一遍 → 有效带宽减半
```

这是 GPU 编程第一大性能坑。**规律分支（`i < n/2` 而非 `i%2`）不会发散**。

```cuda
// ✗ 发散：每个 warp 两个分支
if (i & 1) out[i] = f(in[i]); else out[i] = g(in[i]);
// ✓ 改成算术或分两次调用
out[i] = (i & 1) ? f(in[i]) : g(in[i]);   // 仍然发散
```

## 三、CUDA Core vs Tensor Core

| 类型 | 算子类型 | 说明 |
|------|---------|------|
| CUDA Core (FP32/FP64) | 通用浮点、向量 | FP64 只有 1/2 甚至 1/32 速率，消费卡几乎没有 FP64 |
| Tensor Core | 矩阵乘加（FP16/BF16/TF32/FP8/INT8） | Ampere 起有，比 CUDA Core 快 8~16 倍 |

判断你的任务能不能吃到 Tensor Core：**必须以 16×16 或 8×8 的矩阵块矩阵乘形式**（GEMM / Conv）。写不成这种形状的算子，再多 CUDA Core 也白搭。

### 数据格式（模型选型和显存直接相关）

| 格式 | 位宽 | 精度 | 典型用途 |
|------|------|------|---------|
| FP32 | 32bit | 高 | 基准、某些数值敏感层 |
| TF32 | 19bit 存 | 中（尾数 10bit） | Ampere 默认加速 FP32 matmul |
| BF16 | 16bit | 中，动态范围同 FP32 | **训练首选**，不需要 loss scaling |
| FP16 | 16bit | 中，动态范围小 | 推理首选，需 loss scaling 训练 |
| FP8 | 8bit | 低 | Hopper/Ada 推理与训练，需分块缩放 |
| INT8 | 8bit | 量化 | INT8 Tensor Core，推理加速明显 |

范围换算：权重全 BF16 占 `参数量 × 2` 字节。7B 模型 ≈ 14GB，**放不进 16GB 卡的默认配置**。

## 四、架构代际

| 架构 | 年份 | 代表卡 | 关键能力 |
|------|------|--------|---------|
| Pascal | 2016 | P100 | 首次 NVLink、FP16 |
| Volta | 2017 | V100 | 第一代 Tensor Core、独立线程调度 |
| Turing | 2018 | T4 / RTX 2080 | INT8/FP16 Tensor Core |
| Ampere | 2020 | A100 / A30 | **MIG**、TF32、BFloat16、异步拷贝、NVLink3 |
| Hopper | 2022 | H100 / H200 | FP8 Tensor Core、Transformer Engine、NVLink4 |
| Ada | 2022 | L4 / L40S / RTX 4090 | FP8、大显存带宽（4090 1TB/s） |
| Blackwell | 2024 | B200 / GB200 | FP4、大幅提升 NVLink 域规模 |

> K8s 排障时看 `nvidia-smi` 的第一行就是架构，直接影响「为什么卡不支持某算子」。

## 五、卡间互联

```text
NVLink  >  NVSwitch  >  PCIe
A100:  NVLink3 600GB/s 双向    H100: NVLink4 1.8TB/s 双向
PCIe Gen4 x16 ≈ 32GB/s        PCIe Gen5 x16 ≈ 64GB/s
```

差一个数量级。**多卡训练如果通信走 PCIe，线性加速直接腰斩**。

```bash
# 看卡间拓扑：NV# 是 NVLink，SYS 是 PCIe 跨 CPU NUMA
nvidia-smi topo -m
```

常见坑：两张卡挂在不同 NUMA 节点上，CPU 内存到显存的拷贝跨了 UPI，带宽砍半。调度时要用 `nvidia.com/gpu` + NUMA 亲和绑住。

## 六、编程模型对照

| 概念 | CPU | GPU |
|------|-----|-----|
| 调度单元 | 线程 | thread（软件）+ warp（硬件） |
| 嵌套并行 | OpenMP / 线程池 | grid → block → thread，block 之间可无序 |
| 同步 | mutex / 原子 | `__syncthreads()`（block 内）、CUDA Stream / Event（设备间） |
| 数据局部性 | cache 命中 | **显式管理**：shared memory 手动搬 |
| 内存分配 | malloc | `cudaMalloc`，独立地址空间，显存不过虚拟内存透明扩展 |

GPU 是 **SIMT（Single Instruction Multiple Threads）**：软件上是线程，硬件上打包成 warp 执行。所以写 GPU 代码 = 写「一个线程做什么」，而不是写 SIMD intrinsics。

## 七、看硬件的命令

```bash
nvidia-smi                          # 卡、驱动、显存、进程
nvidia-smi -L                       # 卡 UUID 列表（和 K8s device plugin 同一套标识）
nvidia-smi topo -m                  # 卡间拓扑
nvidia-smi -q -d COMPUTE            # 计算模式：Default / Exclusive_Process / Prohibited
nvidia-smi --query-gpu=name,memory.total,compute_cap --format=csv
```

`compute_cap` 就是 SM 版本（8.0 = A100，9.0 = H100），编译时对应 `sm_80` / `sm_90`。

## 小结

- GPU 快靠并行度掩盖延迟，不是单核快。
- warp = 32 线程，发散会让有效吞吐打对折。
- Tensor Core 只吃矩阵块运算，格式决定精度和显存。
- 卡间通信速度差一个数量级，拓扑和 NUMA 亲和要在调度层解决。
