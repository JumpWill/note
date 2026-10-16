# K8s 申请与调度 GPU

> 原理为主：K8s 怎么把「物理卡」抽象成「可申请资源」、调度器怎么选卡、拓扑怎么绑。
> 安装与配置步骤见 [`../整体/26-GPU使用.md`](../整体/26-GPU使用.md)。

## 一、GPU 不是内置资源类型

K8s 内置的资源只有 `cpu` / `memory` / `ephemeral-storage`。GPU 走**扩展资源（Extended Resource）**机制：

- 资源名必须是 `vendor.com/resource` 形式 → NVIDIA 官方用 **`nvidia.com/gpu`**
- **只能是整数，不能是 0.5**
- 节点上必须有对应 Device Plugin 注册，kubelet 才会把它上报成节点 allocatable

```yaml
resources:
  limits:
    nvidia.com/gpu: 1     # ✅
    nvidia.com/gpu: 0.5   # ❌ 无效
```

`requests` 不写时默认等于 `limits`（对所有扩展资源都是这样，和 CPU 的行为不同）。想只声明不限制也要写成整数。

## 二、device plugin 机制

```text
kubelet                                    device plugin
  │                                              │
  │◄────── Register() 注册 /var/lib/kubelet/... ──┤  NVIDIA k8s-device-plugin
  │                                              │
  │  发现 GPU → 上报 Node Allocatable:            │
  │    Capacity:   nvidia.com/gpu: 8             │
  │    Allocatable: nvidia.com/gpu: 8            │
  │◄─────────── ListAndWatch() 返回可用卡 UUID ───┤
  │                                              │
  │  kubelet 发现 Pod 声明了 nvidia.com/gpu:2     │
  │  → 调 Allocate() 挑 2 张卡                   │
  │  → 写入 CDI 描述或注入环境变量 + 设备节点      │
  │                                              │
  ▼
容器启动（toolkit hook 注入驱动库）
```

要点：

- device plugin 是 **每节点一个进程**（DaemonSet），kubelet 主动 gRPC 拉取，不反向推送
- 分配单位是 **GPU UUID**，不是 index
- plugin 挂掉 → 该节点 GPU 容量变成 0，Pod 无法调度（但节点还在）
- 上报用 `nvidia-smi -L` 的 UUID，**nvidia-smi 看不到卡就是 plugin 看不到卡**

```bash
kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.allocatable.nvidia\.com/gpu}{"\n"}{end}'
# 应输出真实卡数，输出 <none> 说明 device plugin 没起来
```

## 三、Node Feature Discovery（NFD）

调度器需要标签来表达「节点有什么卡」：

```bash
nvidia-smi topo -m   # 找 GPU 的 PCIe 拓扑：0000:18:00.0

# NFD 或 GPU Feature Discovery (GFD) 打出的标签
nvidia.com/gpu.count: 8
nvidia.com/gpu.product: NVIDIA-H100-80GB-HBM3
nvidia.com/gpu.memory: 81559
nvidia.com/gpu.compute.major: "9"
nvidia.com/gpu.compute.minor: "0"
feature.node.kubernetes.io/pci-10de.present: "true"
feature.node.kubernetes.io/pci-10de.device-id.2330.present: "true"
```

价值：**跨机型混部时能把模型按卡的算力/显存调度到合适的机器上。**

```yaml
nodeSelector:
  nvidia.com/gpu.product: NVIDIA-A100-SXM4-80GB
```

## 四、拓扑感知调度

多卡任务（Tensor Parallel / NCCL）对卡间连接敏感。K8s 的 taint/toleration + label 组合来表达：

```bash
# 打标签：G1 表示 NVLink 互联的卡组
# nvlink topo 对比产生，一般由自动化脚本或 NFD topology 插件生成
kubectl label node gpu-node-1 nvidia.com/gpu.group=G1
```

```yaml
spec:
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
          - matchExpressions:
              - key: nvidia.com/gpu.group
                operator: In
                values: [G1]
  tolerations:
    - key: nvidia.com/gpu
      operator: Exists
      effect: NoSchedule
```

NUMA 绑定（跨 NUMA 节点会拖慢 H2D 拷贝）：

```yaml
# 拓扑管理器（Topology Manager）static 策略保证 Pod 内的 CPU/内存/GPU 同 NUMA
# kubelet 启动参数 --topology-manager-policy=restricted
```

## 五、完整的 GPU Deployment 示例

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: llm-inference
spec:
  replicas: 2
  template:
    metadata:
      labels:
        app: llm-inference
    spec:
      runtimeClassName: nvidia        # 若用 RuntimeClass 方式（不推荐，见 05 章）
      # priorityClassName: gpu-workload
      nodeSelector:
        nvidia.com/gpu.present: "true"
      tolerations:
        - key: nvidia.com/gpu
          operator: Exists
          effect: NoSchedule
      containers:
        - name: vllm
          image: vllm/vllm-openai:v0.6.2
          args:
            - --model=/models/Qwen2-7B-Instruct
            - --tensor-parallel-size=2
            - --gpu-memory-utilization=0.9
          env:
            # 容器内只有 2 张卡，重编号 0,1；NCCL 用它选卡
            - name: CUDA_VISIBLE_DEVICES
              value: "0,1"
            - name: NCCL_P2P_DISABLE
              value: "0"
          resources:
            limits:
              nvidia.com/gpu: "2"
              memory: 128Gi        # CPU 内存，不是显存，给够给 DALI/数据加载
              cpu: "16"
            requests:
              cpu: "8"
          ports:
            - containerPort: 8000
      # 优雅退出：NCCL 卡死时进程杀不掉
      terminationGracePeriodSeconds: 300
```

### 三个容易漏的点

1. **toleration 必写**：GPU 节点一般有 `nvidia.com/gpu:NoSchedule` taint。
2. **CPU memory 给够**：给 GPU 的是「数据喂进去」的能力，CPU 内存不足会导致 GPU 利用率上不去。
3. **`terminationGracePeriodSeconds` 拉长**：多卡 NCCL 通信中进程可能不响应 SIGTERM，要靠 SIGKILL 强杀，K8s 默认 30s 不够。

## 六、调度机制的坑

### GPU 不能超卖

```yaml
limits:
  nvidia.com/gpu: 1     # requests 隐式为 1 → CPU 无超卖，GPU 独占
```

想超卖必须靠 device plugin 的 timeSlicing 配置（见第 05 章），**不是改 requests/limits**。`nvidia.com/gpu: 1` 的两个 Pod 一定能同时排上去，说明 timeSlicing 开了。

### Init Container 也消耗 GPU

```yaml
initContainers:
  - name: download-model
    resources:
      limits:
        nvidia.com/gpu: 1     # 只为了用 nvidia-smi 也要占一张卡！
```

**常见浪费**：init container 只是下载模型却占卡，而且它是串行的，会阻塞主容器的 GPU 分配。整个 init 阶段卡是空闲被占着的。

### ResourceQuota 与 LimitRange

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: gpu-quota
spec:
  hard:
    requests.nvidia.com/gpu: "8"        # 租户 A 最多 8 张卡
    limits.nvidia.com/gpu: "8"
    pods: "50"
```

`limits.nvidia.com/gpu` 上限能防住「一个 Pod 要 8 张卡把整节点吃掉」。

### Device Plugin 挂了的表现

```text
Node Allocatable 变 0 → 所有 GPU Pod Pending
原因：daemonset 崩了 / toolkit 配置坏 / GPU 被 Exclusive_Process 模式独占 / nvidia-smi 权限
```

排查顺序见第 06 章。

## 七、传统 RuntimeClass vs device plugin

早期方案（不推荐）：

```yaml
runtimeClassName: nvidia
```

这让用户能自己指定 runtime，等于**每个用户都能操作驱动**（挂载 hostPath、改设备节点），是提权漏洞。当前 NVIDIA 官方只支持 **device plugin** 方案，`RuntimeClass` 已弃用。

如果集群里还有用 `runtimeClassName` 的 Pod，迁移掉它。

## 八、DRA（Dynamic Resource Allocation）

K8s 1.31+ 的新方向：资源以「claim」形式申请，driver 参与决策。对 GPU 的意义是可以做**比整数卡更细的粒度**（DRA 支持 fractional devices），且不需要写 device plugin 插件。

目前 NVIDIA/MIG 支持 DRA 的生产案例还少，2026 年新集群可以考虑，新集群直接上可能生态还不成熟。**存量集群不要动。**

## 小结

- `nvidia.com/gpu` 是扩展资源，只能整数，靠每节点的 device plugin 上报容量。
- 卡间拓扑和 NUMA 亲和用 label + taint 表达，不要指望调度器自动懂硬件拓扑。
- GPU 天然独占，超卖只能靠 timeSlicing/MPS 配置。
- init container 占卡是常见浪费。
