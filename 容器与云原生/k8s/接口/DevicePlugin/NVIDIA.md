## 概念

NVIDIA Device Plugin for Kubernetes 是 **NVIDIA 官方 GPU 在 K8s 上的接入方案**。让 kubelet 识别 GPU、把 GPU 资源 `nvidia.com/gpu` 暴露给 Pod，配合 NVIDIA Container Toolkit 让容器能用 GPU。

* 项目：<https://github.com/NVIDIA/k8s-device-plugin>
* 配套：
  * **NVIDIA Driver**：host 装驱动（容器内不再装驱动）
  * **NVIDIA Container Toolkit**（nvidia-docker2）：让 Docker / containerd 知道怎么挂驱动
  * **NVIDIA CUDA**：应用镜像装

## 架构

```
┌────────── node ────────────────────────┐
│  nvidia-driver (host)                   │
│  nvidia-container-runtime (containerd)  │
│  ┌─ nvidia-device-plugin DaemonSet ─┐  │
│  │ - gRPC ListAndWatch              │  │
│  │ - 暴露 nvidia.com/gpu 资源        │  │
│  └──────────────────────────────────┘  │
│  ┌─ GFD (GPU Feature Discovery) ─────┐  │
│  │ - 节点打 label（GPU 型号 / 显存） │  │
│  └──────────────────────────────────┘  │
│                                         │
│  Pod 调度过来                            │
│   ↓                                     │
│  kubelet 通过 CDI / OCI hook 挂驱动     │
└─────────────────────────────────────────┘
```

* **device-plugin DaemonSet**：核心，注册 GPU 资源
* **GPU Feature Discovery（GFD）**：发现 GPU 型号，给节点打 label（如 `nvidia.com/gpu.product=A100`），配合 NodeSelector 用
* **DCGM**：监控 GPU 指标（DCGM-Exporter）

## 资源类型

```
nvidia.com/gpu          整张卡（如 8 表示 8 张卡）
nvidia.com/mig-1g.5gb   MIG 切分（A100/H100 支持，1 卡切 7 个实例）
```

K8s 1.27+ 支持 **TimeSlicing**（共享一张卡，多 Pod 复用，超分）和 **MIG** 切分（硬件隔离）。

## 部署

```bash
# 1. 装驱动 + Container Toolkit（host）
sudo apt install -y nvidia-driver-535 nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=containerd
sudo systemctl restart containerd

# 2. Helm 装 device plugin
helm repo add nvdp https://nvidia.github.io/k8s-device-plugin
helm install nvdp nvdp/nvidia-device-plugin \
  --namespace nvidia-device-plugin --create-namespace

# 3. 装 GFD（可选,推荐）
helm install nvidia-gfd nvdp/gpu-feature-discovery \
  --namespace nvidia-device-plugin

# 4. 装 DCGM-Exporter（监控）
helm install nvidia-dcgm nvdp/dcgm-exporter \
  --namespace nvidia-device-plugin
```

Pod 用：

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: cuda-test
spec:
  containers:
  - name: cuda
    image: nvidia/cuda:12.4.0-base-ubuntu22.04
    resources:
      limits:
        nvidia.com/gpu: 1     # 要 1 张卡
    command: ["nvidia-smi"]
```

## TimeSlicing 配置

configmap：

```yaml
version: v1
sharing:
  timeSlicingConfig:
    renameResource: "nvidia.com/gpu.shared"
    defaultRequests: 4    # 每张卡当 4 张用（超分 4 倍）
```

## 优缺点

* ✅ **官方方案**，生态最完整（GFD / DCGM / Helm chart 全有）
* ✅ 支持 MIG / TimeSlicing / MPS 多场景
* ✅ 监控完善（DCGM）
* ✅ Time-Slicing 让利用率从 ~30% 提到 ~80%
* ❌ 只支持 NVIDIA，不跨硬件
* ❌ GFD / DCGM / device-plugin 组件多，要点运维
* ❌ K8s 老版本（<1.27）TimeSlicing 不原生，要 configmap hack

## 适用场景

* **AI 训练 / 推理**（CUDA 必备）
* 大模型 / 深度学习集群
* 任何用到 CUDA 的 workload

## 监控

```bash
# device-plugin 状态
kubectl -n nvidia-device-plugin get pods

# 节点 GPU 状态
kubectl describe node <gpu-node> | grep nvidia.com

# GPU 利用率（DCGM exporter → Prometheus）
dcgm_gpu_utilization
dcgm_fb_used / dcgm_fb_total

# 集群级别
kubectl get nodes -o custom-columns=NAME:.metadata.name,GPU:.status.allocatable.'nvidia\.com/gpu'
```

## 一句话

**NVIDIA GPU on K8s 官方方案，CUDA 必选**。