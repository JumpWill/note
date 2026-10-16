# CUDA 生态与驱动兼容

> 目标：搞清**驱动、CUDA Toolkit、cuDNN、框架、镜像**这五层谁决定谁，能一眼解决 `CUDA driver version is insufficient` / `no kernel image is available` 这类报错。

## 一、五层依赖关系

```text
┌─────────────────────────────────────┐
│ 你的应用 / PyTorch / TensorRT        │  决定 CUDA 版本与 cuDNN 版本
├─────────────────────────────────────┤
│ CUDA Runtime / cuDNN / cuBLAS       │  编译进镜像
├─────────────────────────────────────┤
│ libcuda.so (NVIDIA Driver)          │  在宿主机上，由内核模块提供
├─────────────────────────────────────┤
│ Kernel Module + GPU 硬件            │  宿主机，只装一次
└─────────────────────────────────────┘
```

关键结论：

> **CUDA Toolkit 不装在宿主机上，它在容器镜像里。** 宿主机只需要驱动。
> 宿主机装 toolkit 只是为了用 `nvidia-smi` 之外的东西（nvcc、D样例），生产上不需要。

## 二、Driver API vs Runtime API

| | Driver API | Runtime API |
|---|---|---|
| 前缀 | `cuda`/`cu` + `cuda.h` | `cuda` + `cuda_runtime.h` |
| 例子 | `cuInit` `cuDeviceGet` `cuMemAlloc` | `cudaMalloc` `cudaMemcpy` `cudaGetDeviceCount` |
| 依赖 | 直接 libcuda.so | libcuda.so + libcudart.so |
| 特点 | 细粒度、可多设备上下文、可与图形 API 混用 | 简化、隐式上下文、多线程不安全 |
| 谁在用 | PyTorch/JAX 底层、vLLM、多卡框架 | 绝大多数应用代码 |

**编译期决定运行期**：

```text
.cu 源码 --nvcc--> PTX (虚拟指令) --驱动 JIT--> SASS (当前 GPU 的机器码)
                     ↑ 可跨代兼容          ↑ 只对本代有效
```

`nvcc -arch=sm_80` 生成 SASS + PTX。运行时如果 GPU 代际更高，驱动会把 PTX **JIT 编译**成对应 SASS（要花几百毫秒，可用 `CUDA_CACHE` 缓存）。

## 三、编译目标与算力

```bash
nvidia-smi --query-gpu=compute_cap --format=csv   # 8.0 / 8.6 / 9.0

nvcc -gencode arch=compute_80,code=sm_80  \  # 只生成 A100 机器码
     -gencode arch=compute_90,code=sm_90  \  # 顺带给 H100
     -gencode arch=compute_80,code=compute_80  # 附 PTX，给未来卡 JIT
```

**`no kernel image is available for execution on the device`** = 二进制里没有这张卡的 SASS，也没有可 JIT 的 PTX。解法：

- 装 PyTorch 官方 wheel（预置了多种 arch，最省事）
- 或设环境变量应急：`export TORCH_CUDA_ARCH_LIST="9.0"`

## 四、版本兼容矩阵

### CUDA 与驱动

规则：**驱动版本号 ≥ 该 CUDA 版本要求的最小驱动**。

| CUDA | 最低 Linux 驱动 | 说明 |
|------|---------------|------|
| 11.8 | 520.61.05 | 最后一个支持 Pascal |
| 12.0 | 525.60.13 | 弃 Pascal，弃 Kepler |
| 12.4 | 550.54.14 | 主流版本 |
| 12.8 | 570.26 | Blackwell 支持 |
| 13.0 | 580.x | |

CUDA 的 **Minor Version Compatibility** 带来弹性：

```text
容器 CUDA 12.4  +  宿主机驱动 560  ✅（驱动支持 CUDA 12.x 全部 minor）
容器 CUDA 12.9  +  宿主机驱动 525  ❌
```

反向不兼容：老驱动跑不了新 CUDA。**宿主机驱动升级通常可以满足一切，容器里 CUDA 可以任意选。**

`CUDA_FORWARD_COMPATIBILITY` 可以在驱动略旧时向前兼容，但要额外挂载 compat 包，K8s 里少见。

### cuDNN

PyTorch 官方 wheel 已经**自带 cuDNN**。自己编译才需要单独装。cuDNN 版本和 CUDA 主次版本强绑定（cuDNN 8.x 配 CUDA 11/12）。

> **实践结论：K8s 上不要手动装 cuDNN/CUDA，用官方镜像或 PyTorch 官方 wheel。** 版本问题会少掉 90%。

### 框架版本对照

| PyTorch | CUDA | 默认 cuDNN |
|---------|------|-----------|
| 2.0~2.3 | 11.8 / 12.1 | 8.x |
| 2.4~2.7 | 12.1 / 12.4 / 12.6 | 8.9 / 9.x |
| 2.8+ | 12.6 / 12.8 | 9.x |

vLLM / SGLang 另有自己的兼容表，查它们的 release notes。

## 五、镜像选型

### NVIDIA 官方 CUDA 镜像 tag

```text
nvidia/cuda:<CUDA>-<distro>-<flavor>
            12.4.1  ubuntu22.04  devel
                             ^ base / runtime / devel
```

| flavor | 内容 | 大小 | 用途 |
|--------|------|------|------|
| `base` | 只有运行时最小依赖 | ~200MB | **只用 cuBLAS/cuDNN 预编译库时够用** |
| `runtime` | base + cuBLAS/cuFFT/cuDNN 等库 | ~2GB | 跑现成框架，**生产常用** |
| `devel` | runtime + nvcc + 头文件 | ~4GB | 要现场编译扩展 |

常见发行版：`ubuntu22.04`、`ubuntu24.04`、`debian12`。选发行版要对齐 glibc 和 Python 版本。

### PyTorch 镜像

```bash
docker pull pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime
docker pull nvcr.io/nvidia/pytorch:24.10-py3   # NGC，多卡/NCCL 调优过
```

### 验证镜像

```bash
nvidia-smi                          # 宿主机驱动版本
python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"
python -c "import torch; print(torch.cuda.get_device_capability())"
```

## 六、容器里到底发生了什么

K8s 创建容器时，nvidia-container-toolkit 的 hook 做了这几件事：

```text
1. 往容器注入 libcuda.so、libnvidia-ml.so 等驱动库（bind mount 宿主机文件）
2. 注入 /proc/driver/nvidia 目录
3. 设置环境变量：
     NVIDIA_VISIBLE_DEVICES=<分配的卡 UUID>
     NVIDIA_DRIVER_CAPABILITIES=compute,utility
4. 按请求挂载设备节点 /dev/nvidia0 /dev/nvidiactl /dev/nvidia-uvm
```

所以**容器内不需要任何 CUDA 库**（除了框架自己要用的），这正是「驱动在宿主机、CUDA 在镜像」的物理实现。

手工验证：

```bash
nvidia-container-cli info           # 看 toolkit 识别到的库
nvidia-container-cli list-gpus      # 列出可见 GPU
```

## 七、K8s 中的环境变量

| 变量 | 作用 |
|------|------|
| `NVIDIA_VISIBLE_DEVICES` | toolkit 注入，容器能看到哪些卡 |
| `NVIDIA_DRIVER_CAPABILITIES` | `compute,utility,graphics,video`，无则不注入对应库 |
| `NVIDIA_REQUIRE_CUDA` | 声明需要的 CUDA 版本（cudatoolkit flavor） |
| `CUDA_VISIBLE_DEVICES` | **框架自己用的**，在容器内把可见卡重新编号为 0..N-1 |
| `CUDA_MPS_*` | MPS 专用 |
| `TORCH_CUDA_ARCH_LIST` | 编译目标 |
| `NCCL_*` | 多卡通信，见第 04 章 |

**容易混的一点**：`CUDA_VISIBLE_DEVICES` 是进程自己设的，和 device plugin 的分配无关。两个都存在时，先过滤后分配。

## 八、常见报错速查

| 报错 | 原因 | 解法 |
|------|------|------|
| `CUDA driver version is insufficient for CUDA runtime version` | 驱动太旧 | 升宿主机驱动；`nvidia-smi` 看版本 |
| `no CUDA-capable device is detected` | 容器里没看到卡 | 查 device plugin、toolkit 配置、`NVIDIA_VISIBLE_DEVICES` |
| `no kernel image is available for execution` | 二进制无此卡 SASS | 换官方 wheel / 设 `TORCH_CUDA_ARCH_LIST` |
| `CUDA out of memory` | 显存不够 | 见第 02 章 |
| `libcudart.so.12: cannot open` | 镜像 CUDA 版本和框架不匹配 | 用官方 wheel，或对齐 CUDA 主版本 |
| `CUDA error: no kernel image` on H100 | 用 A100 编译的镜像直接跑 | 重装 H100 镜像 |
| `cudaErrorInsufficientDriver` at import torch | 容器 CUDA 高于驱动能支持的 | 降容器 CUDA 或升驱动 |

## 小结

- 宿主机只需驱动；CUDA/cuDNN 在镜像里，两者版本通过「最低驱动版本」关联。
- 用官方 PyTorch/NGC 镜像，别手动拼版本。
- 容器可见卡由 toolkit 注入，框架内部再用 `CUDA_VISIBLE_DEVICES` 二次过滤。
