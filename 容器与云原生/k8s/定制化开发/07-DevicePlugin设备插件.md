# Device Plugin 设备插件

## 一、为什么要做 Device Plugin

### 1.1 业务背景

```text
K8s 原生资源只支持 CPU、内存、存储：
  - CPU、内存：内置
  - 存储：CSI 解决
  - 其他资源（GPU、FPGA、RDMA、TPU、NPU、高性能网卡）：
    - 早期：通过环境变量 + hostPath
    - 不优雅：kubelet 修改 pod spec
    - 标准化方案：Device Plugin

真实场景：
  - AI 训练需要 GPU（NVIDIA、AMD、寒武纪、昇腾）
  - HPC 需要 RDMA（InfiniBand、RoCE）
  - 5G 通信需要 FPGA
  - 高频交易需要低延迟网卡（Solarflare、Exablaze）
  - 机器学习需要 TPU（Google TPU）
  - 自动驾驶需要 NPU
  - 视频编码需要硬件编码器
  - 量子计算需要特殊硬件
```

### 1.2 Device Plugin 核心价值

```text
1. 标准化
   - 统一 gRPC 接口
   - kubelet 通过标准协议发现设备
   - 任何硬件可接入 K8s

2. 资源可见
   - 设备作为 K8s 资源（如 nvidia.com/gpu）
   - kubectl describe node 显示设备
   - 调度器感知设备

3. 设备隔离
   - kubelet 跟踪设备分配
   - 避免重复分配
   - 设备健康检查

4. 与 K8s 生态融合
   - Device Plugin + Scheduling
   - Device Plugin + DRA（Dynamic Resource Allocation）
   - Device Plugin + Monitoring
```

### 1.3 适用场景

```text
适合 Device Plugin 的场景：
  ✅ GPU 资源管理（NVIDIA、AMD、寒武纪等）
  ✅ FPGA 资源
  ✅ RDMA 网卡
  ✅ TPU、NPU 等 AI 芯片
  ✅ 高性能网卡
  ✅ 特殊硬件（USB、PCIe 设备）
  ✅ 加密卡

不适合：
  ❌ 简单资源（CPU、内存）
  ❌ 仅需环境变量
  ❌ 临时调试
```

---

## 二、Device Plugin 架构

### 2.1 整体架构

```text
┌────────────────────────────────────────────┐
│              K8s Node                          │
│                                              │
│  kubelet                                      │
│    ↓                                          │
│  gRPC (Registration/DevicePlugin)             │
│    ↓                                          │
│  Device Plugin Daemon (Pod)                  │
│    - 实现 DevicePluginServer gRPC 服务        │
│    - ListAndWatch：发现设备                │
│    - Allocate：分配设备                    │
│    - GetDevicePluginOptions：选项            │
│    - GetPreferredAllocation：优选分配       │
│    - PreStartContainer：容器启动前准备     │
│                                              │
│  底层硬件                                    │
│    ↓                                          │
│  GPU / FPGA / RDMA / ...                   │
│                                              │
└────────────────────────────────────────────┘
```

### 2.2 核心 gRPC 服务

```protobuf
service DevicePlugin {
    // 注册设备插件
    rpc GetDevicePluginOptions(GetDevicePluginOptionsRequest) returns (GetDevicePluginOptionsResponse);

    // 获取设备列表
    rpc ListAndWatch(Empty) returns (stream ListAndWatchResponse);

    // 分配设备
    rpc Allocate(AllocateRequest) returns (AllocateResponse);

    // 容器启动前准备
    rpc PreStartContainer(PreStartContainerRequest) returns (PreStartContainerResponse);

    // 优选分配
    rpc GetPreferredAllocation(PreferredAllocationRequest) returns (PreferredAllocationResponse);
}

service Registration {
    // 注册到 kubelet
    rpc Register(RegistrationRequest) returns (Empty);
}
```

### 2.3 设备生命周期

```text
Device Plugin 工作流程：

  1. 注册阶段
     Device Plugin → kubelet
     - Register(gRPC)
     - 提供 endpoint（Unix socket）
     - 提供资源名称（nvidia.com/gpu）
     - 提供版本

  2. 列出设备
     kubelet → Device Plugin
     - ListAndWatch(gRPC stream)
     - 返回设备列表：device1, device2...
     - 持续监听（流式）

  3. 分配设备
     Pod 调度到节点
     kubelet → Device Plugin
     - Allocate(gRPC, env, deviceIDs)
     - 返回设备信息（路径、环境变量等）

  4. 准备容器
     kubelet → Device Plugin
     - PreStartContainer(gRPC, deviceIDs)
     - 设备准备（设置权限、加载驱动）

  5. 容器运行
     Pod 启动，使用分配的设备

  6. 设备释放
     Pod 删除
     kubelet → Device Plugin
     - ListAndWatch 自动通知
     - 设备重新可用
```

---

## 三、Device Plugin 开发

### 3.1 Go Module 初始化

```bash
mkdir my-device-plugin && cd my-device-plugin
go mod init github.com/example/my-device-plugin

# 添加依赖
go get google.golang.org/grpc
go get k8s.io/kubelet/pkg/apis/deviceplugin/v1beta1
```

### 3.2 完整 Device Plugin 实现

```go
// main.go
package main

import (
    "context"
    "fmt"
    "log"
    "net"
    "os"
    "path/filepath"
    "time"

    "google.golang.org/grpc"
    "k8s.io/kubelet/pkg/apis/deviceplugin/v1beta1"
    "golang.org/x/sys/unix"
)

const (
    resourceName = "example.com/mydevice"
    socketDir    = "/var/lib/kubelet/device-plugins"
    socketName   = "mydevice.sock"
)

type devicePlugin struct {
    v1beta1.UnimplementedDevicePluginServer
    devices map[string]*v1beta1.Device
    mu      sync.Mutex
}

func newDevicePlugin() *devicePlugin {
    return &devicePlugin{
        devices: make(map[string]*v1beta1.Device),
    }
}

// GetDevicePluginOptions 返回插件选项
func (p *devicePlugin) GetDevicePluginOptions(
    ctx context.Context, req *v1beta1.GetDevicePluginOptionsRequest,
) (*v1beta1.GetDevicePluginOptionsResponse, error) {
    return &v1beta1.GetDevicePluginOptionsResponse{
        Options: &v1beta1.DevicePluginOptions{
            PreStartRequired: true,
        },
    }, nil
}

// ListAndWatch 列出设备（流式）
func (p *devicePlugin) ListAndWatch(
    req *v1beta1.ListAndWatchRequest,
    stream v1beta1.DevicePlugin_ListAndWatchServer,
) error {
    // 1. 发送初始设备列表
    p.mu.Lock()
    devices := make([]*v1beta1.Device, 0, len(p.devices))
    for _, d := range p.devices {
        devices = append(devices, d)
    }
    p.mu.Unlock()

    if err := stream.Send(&v1beta1.ListAndWatchResponse{Devices: devices}); err != nil {
        return err
    }

    // 2. 持续监听设备变化
    for {
        time.Sleep(10 * time.Second)
        p.mu.Lock()
        devices := make([]*v1beta1.Device, 0, len(p.devices))
        for _, d := range p.devices {
            devices = append(devices, d)
        }
        p.mu.Unlock()
        if err := stream.Send(&v1beta1.ListAndWatchResponse{Devices: devices}); err != nil {
            return err
        }
    }
}

// Allocate 分配设备
func (p *devicePlugin) Allocate(
    ctx context.Context, req *v1beta1.AllocateRequest,
) (*v1beta1.AllocateResponse, error) {
    responses := make([]*v1beta1.ContainerAllocateResponse, 0, len(req.ContainerRequests))

    for _, containerReq := range req.ContainerRequests {
        // 1. 检查请求的设备
        deviceIDs := containerReq.Devices
        if len(deviceIDs) == 0 {
            continue
        }

        // 2. 为容器准备环境变量、设备路径等
        envs := make(map[string]string)
        mounts := []*v1beta1.Mount{}
        devices := []*v1beta1.DeviceSpec{}

        for _, deviceID := range deviceIDs {
            // 实际场景：从硬件获取设备信息
            // 这里简化处理
            devices = append(devices, &v1beta1.DeviceSpec{
                ContainerPath: "/dev/mydevice" + deviceID,
                HostPath:      "/dev/mydevice" + deviceID,
                Permissions: "rw",
            })
            
            // 例如：GPU 场景下设置 NVIDIA_VISIBLE_DEVICES
            envs["NVIDIA_VISIBLE_DEVICES"] = strings.Join(deviceIDs, ",")
        }

        responses = append(responses, &v1beta1.ContainerAllocateResponse{
            Envs:    envs,
            Mounts:  mounts,
            Devices: devices,
        })
    }

    return &v1beta1.AllocateResponse{
        ContainerResponses: responses,
    }, nil
}

// PreStartContainer 容器启动前准备
func (p *devicePlugin) PreStartContainer(
    ctx context.Context, req *v1beta1.PreStartContainerRequest,
) (*v1beta1.PreStartContainerResponse, error) {
    // 实际场景：执行设备准备（设置权限、加载驱动等）
    for _, deviceID := range req.DevicesIDs {
        // 例如：设置设备权限
        devicePath := "/dev/mydevice" + deviceID
        if err := os.Chmod(devicePath, 0666); err != nil {
            log.Printf("chmod failed: %v", err)
        }
    }
    return &v1beta1.PreStartContainerResponse{}, nil
}

// GetPreferredAllocation 优选分配
func (p *devicePlugin) GetPreferredAllocation(
    ctx context.Context, req *v1beta1.PreferredAllocationRequest,
) (*v1beta1.PreferredAllocationResponse, error) {
    return &v1beta1.PreferredAllocationResponse{
        ContainerResponses: make([]*v1beta1.ContainerPreferredAllocationResponse, 0),
    }, nil
}

// registerToKubelet 向 kubelet 注册
func registerToKubelet(socket string, pluginEndpoint string, resourceName string) error {
    conn, err := grpc.Dial("unix://"+pluginEndpoint, grpc.WithInsecure())
    if err != nil {
        return err
    }
    defer conn.Close()

    client := v1beta1.NewRegistrationClient(conn)
    req := &v1beta1.RegisterRequest{
        Endpoint: socket,
        ResourceName: resourceName,
        Options: &v1beta1.DevicePluginOptions{
            PreStartRequired: true,
        },
    }
    _, err = client.Register(context.Background(), req)
    return err
}

func main() {
    // 1. 创建 socket 目录
    if err := os.MkdirAll(socketDir, 0750); err != nil {
        log.Fatal(err)
    }
    
    socketPath := filepath.Join(socketDir, socketName)
    
    // 2. 删除已存在的 socket
    if err := os.Remove(socketPath); err != nil && !os.IsNotExist(err) {
        log.Fatal(err)
    }
    
    // 3. 启动 gRPC server
    lis, err := net.Listen("unix", socketPath)
    if err != nil {
        log.Fatal(err)
    }
    
    // 4. 改变 socket 权限
    if err := os.Chmod(socketPath, 0660); err != nil {
        log.Fatal(err)
    }
    
    grpcServer := grpc.NewServer()
    plugin := newDevicePlugin()
    v1beta1.RegisterDevicePluginServer(grpcServer, plugin)
    
    // 模拟设备检测
    go func() {
        time.Sleep(2 * time.Second)
        plugin.mu.Lock()
        for i := 0; i < 4; i++ {
            plugin.devices[fmt.Sprintf("device-%d", i)] = &v1beta1.Device{
                ID:     fmt.Sprintf("device-%d", i),
                Health: v1beta1.Healthy,
            }
        }
        plugin.mu.Unlock()
    }()
    
    // 5. 注册到 kubelet
    go func() {
        time.Sleep(3 * time.Second)
        kubeletSocket := "/var/lib/kubelet/device-plugins/kubelet.sock"
        if err := registerToKubelet(socketPath, kubeletSocket, resourceName); err != nil {
            log.Printf("register failed: %v", err)
        } else {
            log.Printf("registered to kubelet")
        }
    }()
    
    log.Printf("device plugin listening on %s", socketPath)
    if err := grpcServer.Serve(lis); err != nil {
        log.Fatal(err)
    }
}
```

### 3.3 Device Plugin 部署

```yaml
# 1. RBAC
apiVersion: v1
kind: ServiceAccount
metadata:
  name: my-device-plugin
  namespace: kube-system
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: my-device-plugin
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: cluster-admin    # 实际生产应精细化
subjects:
- kind: ServiceAccount
  name: my-device-plugin
  namespace: kube-system

# 2. DaemonSet 部署
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: my-device-plugin
  namespace: kube-system
  labels:
    app: my-device-plugin
spec:
  selector:
    matchLabels:
      name: my-device-plugin
  template:
    metadata:
      labels:
        name: my-device-plugin
    spec:
      serviceAccountName: my-device-plugin
      hostNetwork: true
      containers:
      - name: my-device-plugin
        image: registry.example.com/my-device-plugin:v1.0
        command: ["/usr/local/bin/my-device-plugin"]
        env:
        - name: NODE_NAME
          valueFrom:
            fieldRef:
              fieldPath: spec.nodeName
        - name: POD_NAMESPACE
          valueFrom:
            fieldRef:
              fieldPath: metadata.namespace
        - name: DEVICE_NAME
          value: "mydevice"
        ports:
        - containerPort: 50051
          hostPort: 50051
        securityContext:
          privileged: true
        volumeMounts:
        - name: device-plugin
          mountPath: /var/lib/kubelet/device-plugins
        - name: dev
          mountPath: /dev
      volumes:
      - name: device-plugin
        hostPath:
          path: /var/lib/kubelet/device-plugins
          type: DirectoryOrCreate
      - name: dev
        hostPath:
          path: /dev
```

### 3.4 Pod 使用

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: my-app-with-device
spec:
  containers:
  - name: app
    image: my-app:1.0
    resources:
      limits:
        example.com/mydevice: 1    # 申请 1 个设备
    command: ["/app/start.sh"]
```

---

## 四、实战场景

### 4.1 场景 1：NVIDIA GPU Device Plugin

```yaml
# 1. 安装官方 NVIDIA Device Plugin
helm repo add nvdp https://nvidia.github.io/k8s-device-plugin
helm repo update

# 2. 部署
helm install nvdp nvdp/nvidia-device-plugin \
  --namespace nvidia-device-plugin \
  --create-namespace \
  --set gfd.enabled=true

# 3. 验证
kubectl get nodes -o json | jq '.items[].status.capacity."nvidia.com/gpu"'
# "4"

# 4. Pod 使用
apiVersion: v1
kind: Pod
metadata:
  name: gpu-pod
spec:
  containers:
  - name: cuda-container
    image: nvcr.io/nvidia/k8s/cuda-sample:nbody-cuda12.5.0
    resources:
      limits:
        nvidia.com/gpu: 1
```

### 4.2 场景 2：RDMA Device Plugin（InfiniBand）

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: rdma-pod
  annotations:
    k8s.v1.cni.cncf.io/networks: rdma-net
spec:
  containers:
  - name: hpc-app
    image: my-hpc-app:1.0
    resources:
      limits:
        rdma/rdma_shared_hca: 1
    securityContext:
      capabilities:
        add: ["IPC_LOCK", "SYS_RAWIO"]
```

### 4.3 场景 3：FPGA Device Plugin

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: fpga-pod
spec:
  containers:
  - name: fpga-app
    image: my-fpga-app:1.0
    resources:
      limits:
        vendor.com/fpga: 1
    volumeMounts:
    - name: fpga-bitstream
      mountPath: /opt/fpga
    - name: dev
      mountPath: /dev
  volumes:
  - name: fpga-bitstream
    configMap:
      name: fpga-bitstream
  - name: dev
    hostPath:
      path: /dev
```

### 4.4 场景 4：TPU Device Plugin

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: tpu-pod
spec:
  nodeSelector:
    cloud.google.com/gke-tpu-accelerator: tpu-v5-lite-podslice
  containers:
  - name: tpu-training
    image: my-tpu-app:1.0
    resources:
      limits:
        google.com/tpu: 4
```

### 4.5 场景 5：NPU Device Plugin（华为昇腾）

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: npu-pod
spec:
  containers:
  - name: npu-training
    image: ascendai/tensorflow:1.15
    resources:
      limits:
        huawei.com/Ascend310: 1
    securityContext:
      privileged: false
```

---

## 五、DRA（Dynamic Resource Allocation）

### 5.1 DRA 简介

```text
DRA = Dynamic Resource Allocation（动态资源分配）

K8s 1.26+ 引入，1.30 进入 Beta：

DRA 是 Device Plugin 的下一代：
  - 更灵活的 API
  - 支持结构化资源
  - 支持参数化请求
  - 统一所有资源类型

优势：
  - 不需要为每个设备写 DP
  - 设备可动态共享和分区
  - 调度器原生支持
  - 更丰富的拓扑感知
```

### 5.2 DRA 核心 API

```yaml
# 1. ResourceClass
apiVersion: resource.k8s.io/v1
kind: ResourceClass
metadata:
  name: shared-gpu
spec:
  driver: gpu.example.com
  parametersRef:
    apiGroup: gpu.example.com
    kind: GPUParameters
    name: shared-gpu-config
```

```yaml
# 2. ResourceClaimTemplate
apiVersion: resource.k8s.io/v1
kind: ResourceClaimTemplate
metadata:
  name: gpu-claim
spec:
  spec:
    resourceClassName: shared-gpu
    parametersRef:
      apiGroup: gpu.example.com
      kind: GPUParameters
      name: gpu-1gpu
```

```yaml
# 3. Pod 使用 DRA
apiVersion: v1
kind: Pod
metadata:
  name: my-pod
spec:
  containers:
  - name: app
    image: my-app:1.0
    resources:
      claims:
      - name: gpu
  resourceClaims:
  - name: gpu
    source:
      resourceClaimTemplateName: gpu-claim
```

### 5.3 DRA vs Device Plugin 对比

| 维度 | Device Plugin | DRA |
|------|---------------|-----|
| 成熟度 | 稳定（v1.0+） | Beta（1.30+） |
| 复杂度 | 中（要写 gRPC） | 高（要写 CDI、DRAPlugin） |
| 灵活性 | 中（资源粒度固定） | 高（结构化） |
| 拓扑感知 | 弱 | 强（结构化选择器） |
| 共享设备 | 弱 | 强（可分区） |
| 适用场景 | 简单设备分配 | 复杂设备（GPU MIG、MPS） |

---

## 六、Device Plugin 调试

### 6.1 调试工具

```bash
# 1. 查看节点资源
kubectl describe node <node-name>
# 在 Allocatable 字段查看设备：
#   example.com/mydevice:  4

# 2. 查看 Device Plugin Pod 日志
kubectl logs -n kube-system -l app=my-device-plugin

# 3. 查看 kubelet 日志
journalctl -u kubelet -f

# 4. 查看 Device Plugin 状态
ls /var/lib/kubelet/device-plugins/

# 5. 验证分配
kubectl describe pod <pod-name>
# 在 Events 字段查看设备分配情况

# 6. 进入 Pod 验证
kubectl exec -it <pod-name> -- ls /dev/mydevice*
```

### 6.2 常见问题

```text
Q1: Device Plugin 注册失败
A1: 检查：
    - socket 路径是否正确
    - 权限是否正确（0600）
    - 资源名称是否唯一
    - kubelet 日志查看错误详情

Q2: Pod 申请设备时 Pending
A2: 检查：
    - Device Plugin 是否在节点运行
    - 设备数量是否足够
    - 节点 label 是否正确
    - NodeSelector 是否匹配

Q3: 设备未出现在容器中
A3: 检查：
    - 设备路径是否挂载正确
    - 权限是否设置（PreStartContainer）
    - 驱动是否加载（lsmod）
```

---

## 七、Device Plugin 最佳实践

### 7.1 设计原则

```text
1. 健康检查
   - 实现真实健康检查（不只报 Healthy）
   - 失败时及时通知

2. 幂等性
   - ListAndWatch 多次调用结果一致
   - Allocate 重入安全

3. 资源粒度
   - 按需划分（GPU 整卡 vs MIG）
   - 避免过细导致调度性能问题

4. 错误处理
   - 清晰的错误信息
   - 优雅降级（设备故障时处理）
   - 重试机制

5. 性能
   - ListAndWatch 流式响应
   - 增量更新（避免全量重发）
   - 缓存常用数据
```

### 7.2 常见 Device Plugin 列表

| Device Plugin | 资源名 | 适用 |
|---------------|--------|------|
| NVIDIA GPU | nvidia.com/gpu | GPU 训练/推理 |
| AMD GPU | amd.com/gpu | GPU 训练/推理 |
| 寒武纪 MLU | cambricon.com/mlu | AI 芯片 |
| 华为昇腾 NPU | huawei.com/Ascend310 | AI 芯片 |
| 燧原 GCU | enflame.com/gcu | AI 芯片 |
| RDMA | rdma/rdma_shared_hca | 高性能网络 |
| SR-IOV | intel.com/sriov | 高性能网络 |
| FPGA | 各厂商不同 | 硬件加速 |
| TPU | google.com/tpu | 谷歌 TPU |
| GPU 内存 | nvidia.com/gpu（带 MIG） | GPU 切片 |

### 7.3 迁移到 DRA

```text
何时考虑迁移到 DRA：
  ✅ Device Plugin 维护复杂
  ✅ 需要结构化资源（拓扑、参数）
  ✅ 需要共享设备（MIG、MPS）
  ✅ K8s 版本 ≥ 1.30
  ✅ 有充分的测试时间

迁移策略：
  1. 保留 Device Plugin，逐步迁移
  2. DRA 与 DP 可以共存
  3. 先新业务用 DRA，旧业务继续 DP
  4. 全部迁移后，废弃 DP
```

---

## 八、参考资源

```text
- Device Plugin 规范: https://kubernetes.io/docs/concepts/extend-kubernetes/compute-storage-net/device-plugins/
- DRA 文档: https://kubernetes.io/docs/concepts/scheduling-eviction/dynamic-resource-allocation/
- NVIDIA Device Plugin: https://github.com/NVIDIA/k8s-device-plugin
- AMD GPU Device Plugin: https://github.com/RadeonOpenCompute/k8s-device-plugin
- Intel Device Plugins: https://github.com/inteldevice-plugins-for-kubernetes
- RDMA Device Plugin: https://github.com/Mellanox/k8s-rdma-shared-dev-plugin
- DRA 示例: https://github.com/kubernetes-sigs/dra-example-driver
- 官方示例 DP: https://github.com/kubernetes/sample-device-plugin

```
## 速记卡

Device Plugin = K8s 访问特殊硬件的标准接口
4 个 RPC：ListAndWatch / Allocate / PreStartContainer / GetPreferredAllocation
注册：Register 到 kubelet
部署：DaemonSet（特权模式）
挂载：/var/lib/kubelet/device-plugins/ + /dev
应用：spec.containers[].resources.limits[resourceName]
下一步：DRA（Dynamic Resource Allocation，K8s 1.30+ Beta）
