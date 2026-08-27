# CSI 存储接口（Container Storage Interface）

## 一、为什么要做 CSI

### 1.1 业务背景

```text
现实场景：
  - 自研分布式存储系统（Ceph、MinIO、Longhorn 自研版本）
  - 公有云存储（AWS EBS、阿里云盘、Azure Disk）
  - 传统企业存储（NetApp、EMC、IBM）
  - 特殊硬件存储（NVMe-oF、PMem、磁带）
  - 块存储、文件存储、对象存储

K8s 原生存储方式（in-tree）的局限：
  - 代码与 K8s 核心耦合
  - 难以维护和升级
  - 云厂商特殊功能支持慢
  - 第三方存储厂商开发门槛高
```

### 1.2 CSI 核心价值

```text
1. 解耦
   - 存储驱动与 K8s 核心解耦
   - 独立开发、测试、发布
   - 不需 K8s 上游合并

2. 标准化
   - 统一的 gRPC 接口
   - 多语言 SDK
   - 一套接口适配所有存储

3. 加速生态
   - 存储厂商专注 CSI 实现
   - K8s 团队专注核心
   - 创新速度提升

4. 灵活部署
   - CSI 驱动作为 DaemonSet 或独立部署
   - 支持 in-tree 模式（K8s 节点）
   - 支持 out-of-tree 模式
```

### 1.3 适用场景

```text
适合 CSI 的场景：
  ✅ 自研存储系统接入 K8s
  ✅ 公有云块存储（CBS、EBS、Azure Disk）
  ✅ 分布式文件系统（CephFS、GlusterFS）
  ✅ 高性能存储（NVMe-oF、本地 SSD）
  ✅ 备份/快照系统

不适合：
  ❌ 已经使用 in-tree volume 的成熟方案（如 AWS EBS、GCE PD）
  ❌ 简单的 local-path / nfs
  ❌ 无存储需求
```

---

## 二、CSI 架构

### 2.1 三种组件

```text
CSI 系统三个核心组件：

  ┌─────────────────────────────────────────────────┐
  │  1. CSI Identity（身份服务）              │
  │     - GetPluginInfo()                       │
  │     - GetPluginCapabilities()               │
  │     - Probe()                               │
  │     作用：身份验证、能力声明、健康检查   │
  └─────────────────────────────────────────────────┘
                          ↓
  ┌─────────────────────────────────────────────────┐
  │  2. CSI Controller（控制面服务）          │
  │     - CreateVolume / DeleteVolume           │
  │     - ControllerPublish / Unpublish         │
  │     - CreateSnapshot / DeleteSnapshot       │
  │     - ControllerGetCapabilities            │
  │     作用：卷和快照的生命周期管理           │
  │     部署：Deployment（集群级）              │
  └─────────────────────────────────────────────────┘
                          ↓
  ┌─────────────────────────────────────────────────┐
  │  3. CSI Node（节点服务）                    │
  │     - NodeStageVolume / UnstageVolume         │
  │     - NodePublishVolume / UnpublishVolume     │
  │     - NodeGetCapabilities                   │
  │     作用：卷的挂载/卸载                    │
  │     部署：DaemonSet（每个节点）              │
  └─────────────────────────────────────────────────┘
```

### 2.2 CSI 与 K8s 集成

```text
┌─────────────────────────────────────────────────────┐
│                  K8s 节点                                │
│                                                      │
│  kubelet                                              │
│    ↓                                                  │
│  CSI Node Plugin (DaemonSet)                        │
│    - unix:///var/lib/kubelet/plugins_registry/...   │
│    - 与 kubelet 通过 Unix Socket 通信                │
│    ↓                                                  │
│  块设备                                               │
│                                                      │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│              K8s Control Plane                       │
│                                                      │
│  kube-controller-manager                            │
│    ↓                                                  │
│  CSI Sidecar (Deployment)                          │
│    - 与 kube-apiserver 通信                       │
│    - 调用 CSI Controller 的 gRPC 服务                │
│                                                      │
└─────────────────────────────────────────────────────┘
```

### 2.3 CSI 卷生命周期

```text
CSI 卷完整生命周期：

  ┌──────────────────────────────────────────────┐
  │  1. PVC 创建                                 │
  │     用户提交 PersistentVolumeClaim           │
  └──────────────────┬───────────────────────────┘
                     ↓
  ┌──────────────────────────────────────────────┐
  │  2. Provisioning（供应）                  │
  │     CSI Controller：CreateVolume()         │
  │     存储系统创建卷                           │
  └──────────────────┬───────────────────────────┘
                     ↓
  ┌──────────────────────────────────────────────┐
  │  3. PV 绑定                                  │
  │     创建 PersistentVolume 对象                │
  │     绑定到 PVC                                │
  └──────────────────┬───────────────────────────┘
                     ↓
  ┌──────────────────────────────────────────────┐
  │  4. Pod 创建                                 │
  │     kubelet watch 到 PVC 绑定                 │
  └──────────────────┬───────────────────────────┘
                     ↓
  ┌──────────────────────────────────────────────┐
  │  5. Staging（暂存）                          │
  │     CSI Node：NodeStageVolume()              │
  │     在节点上准备卷（如格式化）              │
  └──────────────────┬───────────────────────────┘
                     ↓
  ┌──────────────────────────────────────────────┐
  │  6. Publishing（发布）                       │
  │     CSI Controller：ControllerPublishVolume()│
  │     将卷附加到节点（如挂载 iSCSI）        │
  └──────────────────┬───────────────────────────┘
                     ↓
  ┌──────────────────────────────────────────────┐
  │  7. Mounting（挂载）                          │
  │     kubelet 等待卷可用                        │
  │     CSI Node：NodePublishVolume()            │
  │     在 Pod 中执行 mount 命令                 │
  └──────────────────┬───────────────────────────┘
                     ↓
  ┌──────────────────────────────────────────────┐
  │  8. 使用中                                  │
  │     Pod 运行，使用挂载的卷                │
  └──────────────────┬───────────────────────────┘
                     ↓
  ┌──────────────────────────────────────────────┐
  │  9. Unmounting / Unpublishing / Deleting  │
  │     Pod 终止时反向流程                      │
  └──────────────────────────────────────────────┘
```

---

## 三、CSI Protocol（gRPC）

### 3.1 核心 RPC 接口

```protobuf
// CSI 规范定义的核心服务

service Identity {
    rpc GetPluginInfo(GetPluginInfoRequest) returns (GetPluginInfoResponse);
    rpc GetPluginCapabilities(GetPluginCapabilitiesRequest) returns (GetPluginCapabilitiesResponse);
    rpc Probe(ProbeRequest) returns (ProbeResponse);
}

service Controller {
    rpc CreateVolume(CreateVolumeRequest) returns (CreateVolumeResponse);
    rpc DeleteVolume(DeleteVolumeRequest) returns (DeleteVolumeResponse);
    rpc ControllerPublishVolume(ControllerPublishVolumeRequest) returns (ControllerPublishVolumeResponse);
    rpc ControllerUnpublishVolume(ControllerUnpublishVolumeRequest) returns (ControllerUnpublishVolumeResponse);
    rpc ValidateVolumeCapabilities(ValidateVolumeCapabilitiesRequest) returns (ValidateVolumeCapabilitiesResponse);
    rpc ListVolumes(ListVolumesRequest) returns (ListVolumesResponse);
    rpc GetCapacity(GetCapacityRequest) returns (GetCapacityResponse);
    rpc ControllerGetCapabilities(ControllerGetCapabilitiesRequest) returns (ControllerGetCapabilitiesResponse);
    rpc CreateSnapshot(CreateSnapshotRequest) returns (CreateSnapshotResponse);
    rpc DeleteSnapshot(DeleteSnapshotRequest) returns (DeleteSnapshotResponse);
    rpc ListSnapshots(ListSnapshotsRequest) returns (ListSnapshotsResponse);
    rpc ControllerExpandVolume(ControllerExpandVolumeRequest) returns (ControllerExpandVolumeResponse);
    rpc ControllerGetVolume(ControllerGetVolumeRequest) returns (ControllerGetVolumeResponse);
    rpc ControllerModifyVolume(ControllerModifyVolumeRequest) returns (ControllerModifyVolumeResponse);
}

service Node {
    rpc NodeStageVolume(NodeStageVolumeRequest) returns (NodeStageVolumeResponse);
    rpc NodeUnstageVolume(NodeUnstageVolumeRequest) returns (NodeUnstageVolumeResponse);
    rpc NodePublishVolume(NodePublishVolumeRequest) returns (NodePublishVolumeResponse);
    rpc NodeUnpublishVolume(NodeUnpublishVolumeRequest) returns (NodeUnpublishVolumeResponse);
    rpc NodeGetVolumeStats(NodeGetVolumeStatsRequest) returns (NodeGetVolumeStatsResponse);
    rpc NodeExpandVolume(NodeExpandVolumeRequest) returns (NodeExpandVolumeResponse);
    rpc NodeGetCapabilities(NodeGetCapabilitiesRequest) returns (NodeGetCapabilitiesResponse);
    rpc NodeGetInfo(NodeGetInfoRequest) returns (NodeGetInfoResponse);
}
```

### 3.2 数据面 RPC（可选）

```protobuf
// 身份服务中的数据面（CSI 2.0）
service Identity {
    rpc GetPluginInfo(...) ...
    rpc GetPluginCapabilities(...) ...
    rpc Probe(...) ...
    
    // 数据面：提高块设备性能
    rpc NodeGetVolumeStats(...) ...
    rpc NodeExpandVolume(...) ...
}
```

---

## 四、CSI Sidecar 部署模式

### 4.1 External Provisioner Sidecar

```yaml
# 1. 部署 external-provisioner
apiVersion: apps/v1
kind: Deployment
metadata:
  name: csi-provisioner
  namespace: csi-system
spec:
  replicas: 1
  selector:
    matchLabels:
      app: csi-provisioner
  template:
    metadata:
      labels:
        app: csi-provisioner
    spec:
      serviceAccountName: csi-provisioner-sa
      containers:
      - name: csi-provisioner
        image: registry.k8s.io/sig-storage/csi-provisioner:v5.0.1
        args:
        - --v=2
        - --csi-address=/csi-provisioner/csi.sock
        - --leader-election=true
        - --leader-election-namespace=csi-system
        volumeMounts:
        - name: socket-dir
          mountPath: /csi-provisioner
      volumes:
      - name: socket-dir
        emptyDir: {}
```

### 4.2 Attacher Sidecar

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: csi-attacher
  namespace: csi-system
spec:
  replicas: 1
  template:
    spec:
      containers:
      - name: csi-attacher
        image: registry.k8s.io/sig-storage/csi-attacher:v4.5.0
        args:
        - --v=2
        - --csi-address=/csi-attacher/csi.sock
```

### 4.3 Resizer Sidecar

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: csi-resizer
  namespace: csi-system
spec:
  template:
    spec:
      containers:
      - name: csi-resizer
        image: registry.k8s.io/sig-storage/csi-resizer:v1.10.0
        args:
        - --v=2
        - --csi-address=/csi-resizer/csi.sock
```

---

## 五、CSI Driver 开发（实战示例）

### 5.1 简单 CSI Driver（块存储）

```go
// main.go
package main

import (
    "context"
    "log"
    "net"
    "os"
    "sync"

    "github.com/container-storage-interface/spec/lib/go/csi"
    "google.golang.org/grpc"
)

// server 实现 CSI Controller 和 Node 服务
type server struct {
    csi.UnimplementedControllerServer
    csi.UnimplementedNodeServer
    csi.UnimplementedIdentityServer

    // 模拟的卷存储
    volumes map[string]*Volume
    mu      sync.Mutex
}

type Volume struct {
    ID       string
    SizeBytes int64
    Path     string
}

func (s *server) GetPluginInfo(ctx context.Context, req *csi.GetPluginInfoRequest) (*csi.GetPluginInfoResponse, error) {
    return &csi.GetPluginInfoResponse{
        Name:          "my-csi-driver",
        VendorVersion: "1.0.0",
    }, nil
}

func (s *server) Probe(ctx context.Context, req *csi.ProbeRequest) (*csi.ProbeResponse, error) {
    return &csi.ProbeResponse{}, nil
}

func (s *server) GetPluginCapabilities(ctx context.Context, req *csi.GetPluginCapabilitiesRequest) (*csi.GetPluginCapabilitiesResponse, error) {
    return &csi.GetPluginCapabilitiesResponse{
        Capabilities: &csi.PluginCapabilities{
            Service: &csi.ServiceCapabilities{
                Type:  &controllerService,
                Type:  &nodeService,
                Type:  &volumeExpansionService,
            },
        },
    }, nil
}

// CreateVolume 创建卷
func (s *server) CreateVolume(ctx context.Context, req *csi.CreateVolumeRequest) (*csi.CreateVolumeResponse, error) {
    name := req.GetName()
    var size int64 = 10 * 1024 * 1024 * 1024  // 默认 10GB

    for _, cr := range req.GetCapacityRange() {
        if cr.GetRequiredBytes() > 0 {
            size = cr.GetRequiredBytes()
        }
    }

    s.mu.Lock()
    defer s.mu.Unlock()
    
    volume := &Volume{
        ID:       "vol-" + name,
        SizeBytes: size,
        Path:     "/var/lib/csi-volumes/" + name,
    }
    
    if s.volumes == nil {
        s.volumes = make(map[string]*Volume)
    }
    s.volumes[volume.ID] = volume
    
    // 实际场景中：调用存储系统 API 创建卷
    
    return &csi.CreateVolumeResponse{
        Volume: &csi.Volume{
            VolumeId:      volume.ID,
            CapacityBytes: size,
            VolumeContext: req.GetParameters(),
        },
    }, nil
}

// DeleteVolume 删除卷
func (s *server) DeleteVolume(ctx context.Context, req *csi.DeleteVolumeRequest) (*csi.DeleteVolumeResponse, error) {
    s.mu.Lock()
    defer s.mu.Unlock()
    
    delete(s.volumes, req.GetVolumeId())
    return &csi.DeleteVolumeResponse{}, nil
}

// NodeStageVolume 在节点上准备卷
func (s *server) NodeStageVolume(ctx context.Context, req *csi.NodeStageVolumeRequest) (*csi.NodeStageVolumeResponse, error) {
    volumeID := req.GetVolumeId()
    
    s.mu.Lock()
    volume, ok := s.volumes[volumeID]
    s.mu.Unlock()
    
    if !ok {
        return nil, status.Error(codes.NotFound, "volume not found")
    }
    
    // 实际场景中：创建块设备、格式化、挂载到 staging path
    // 例如：mkfs.xfs /dev/sdb /var/lib/kubelet/plugins/.../staging
    err := os.MkdirAll(volume.Path, 0755)
    if err != nil {
        return nil, status.Error(codes.Internal, err.Error())
    }
    
    return &csi.NodeStageVolumeResponse{}, nil
}

// NodePublishVolume 在 Pod 中挂载卷
func (s *server) NodePublishVolume(ctx context.Context, req *csi.NodePublishVolumeRequest) (*csi.NodePublishVolumeResponse, error) {
    volumeID := req.GetVolumeId()
    target := req.GetTargetPath()
    
    s.mu.Lock()
    volume, ok := s.volumes[volumeID]
    s.mu.Unlock()
    
    if !ok {
        return nil, status.Error(codes.NotFound, "volume not found")
    }
    
    // 实际场景中：mount --bind /staging /target
    return &csi.NodePublishVolumeResponse{}, nil
}

func main() {
    s := &server{}
    
    lis, err := net.Listen("tcp", ":50051")
    if err != nil {
        log.Fatal(err)
    }
    
    grpcServer := grpc.NewServer()
    csi.RegisterIdentityServer(grpcServer, s)
    csi.RegisterControllerServer(grpcServer, s)
    csi.RegisterNodeServer(grpcServer, s)
    
    log.Println("CSI driver listening on :50051")
    if err := grpcServer.Serve(lis); err != nil {
        log.Fatal(err)
    }
}
```

### 5.2 StorageClass 与 CSI 关联

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: my-csi-storage
  annotations:
    storageclass.kubernetes.io/is-default-class: "false"
provisioner: my-csi-driver                       # 与 CSI GetPluginInfo 返回的 name 一致
parameters:
  type: ssd                                         # 传递给 CSI driver
  fsType: ext4
reclaimPolicy: Delete
volumeBindingMode: WaitForFirstConsumer
allowVolumeExpansion: true
mountOptions:
  - discard
```

### 5.3 PVC 使用

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: my-data-pvc
spec:
  storageClassName: my-csi-storage
  accessModes: [ReadWriteOnce]
  resources:
    requests:
      storage: 10Gi
---
apiVersion: v1
kind: Pod
metadata:
  name: my-app
spec:
  containers:
  - name: app
    image: nginx
    volumeMounts:
    - name: data
      mountPath: /data
  volumes:
  - name: data
    persistentVolumeClaim:
      claimName: my-data-pvc
```

---

## 六、Volume Snapshot（快照）

### 6.1 创建 SnapshotClass

```yaml
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshotClass
metadata:
  name: my-csi-snapshot
driver: my-csi-driver
deletionPolicy: Delete
parameters:
  type: snapshot
```

### 6.2 创建 Snapshot

```yaml
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshot
metadata:
  name: my-data-snapshot
spec:
  volumeSnapshotClassName: my-csi-snapshot
  source:
    persistentVolumeClaimName: my-data-pvc
```

### 6.3 从 Snapshot 恢复

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: my-data-restored
spec:
  storageClassName: my-csi-storage
  dataSourceRef:
    apiGroup: snapshot.storage.k8s.io
    kind: VolumeSnapshot
    name: my-data-snapshot
  accessModes: [ReadWriteOnce]
  resources:
    requests:
      storage: 10Gi
```

### 6.4 VolumeExpansion（扩容）

```yaml
# 在线扩容 PVC
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: my-data-pvc
spec:
  storageClassName: my-csi-storage
  accessModes: [ReadWriteOnce]
  resources:
    requests:
      storage: 50Gi    # 从 10Gi 扩到 50Gi
```

```go
// CSI Driver 实现扩容
func (s *server) ControllerExpandVolume(ctx context.Context, req *csi.ControllerExpandVolumeRequest) (*csi.ControllerExpandVolumeResponse, error) {
    volumeID := req.GetVolumeId()
    newSize := req.GetCapacityRange().GetRequiredBytes()
    
    s.mu.Lock()
    volume, ok := s.volumes[volumeID]
    s.mu.Unlock()
    
    if !ok {
        return nil, status.Error(codes.NotFound, "volume not found")
    }
    
    if newSize <= volume.SizeBytes {
        return nil, status.Error(codes.OutOfRange, "new size must be larger")
    }
    
    // 实际场景中：调用存储系统扩容 API
    volume.SizeBytes = newSize
    
    return &csi.ControllerExpandVolumeResponse{
        CapacityBytes: newSize,
    }, nil
}
```

---

## 七、实战场景

### 7.1 场景 1：自研块存储接入 K8s

```yaml
# 1. StorageClass
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: myblock-storage
provisioner: com.example.csi
parameters:
  storageType: ssd
  iops: "5000"
reclaimPolicy: Delete
volumeBindingMode: WaitForFirstConsumer
allowVolumeExpansion: true
```

### 7.2 场景 2：对接 NFS（CSI 实现）

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: nfs-csi
provisioner: nfs.csi.k8s.io
parameters:
  server: nfs.example.com
  share: /exports/data
  csi.storage.k8s.io/provisioner-secret-name: nfs-creds
  csi.storage.k8s.io/provisioner-secret-namespace: default
reclaimPolicy: Retain
```

### 7.3 场景 3：使用快照备份

```bash
# 1. 创建快照
kubectl apply -f snapshot.yaml

# 2. 查看快照状态
kubectl get volumesnapshot
# NAME               READYTOUSE   SOURCEPVC      SOURCESNAPSHOTCONTENT
# my-data-snapshot   true         my-data-pvc

# 3. 从快照恢复（创建新 PVC）
kubectl apply -f restore-pvc.yaml

# 4. 在 Pod 中使用
kubectl apply -f pod-using-restored-pvc.yaml
```

### 7.4 场景 4：动态扩容

```bash
# 修改 PVC 大小
kubectl edit pvc my-data-pvc
# spec.resources.requests.storage: 100Gi

# 查看扩容状态
kubectl get pvc my-data-pvc
# NAME         STATUS   VOLUME                                     CAPACITY   ACCESS MODES
# my-data-pvc  Bound    pvc-xxx-yyy                                100Gi      RWO
```

---

## 八、CNI 与 K8s 集成方式

### 8.1 Sidecar 部署（推荐）

```text
CSI 驱动以 Sidecar 方式部署：
  - 与 K8s 解耦
  - 由 K8s 官方维护 sidecar 镜像
  - CSI 实现方只关心业务逻辑

优势：
  - 不修改 K8s 核心
  - 可以独立升级
  - 多个 CSI 可以同时运行

sidecar 类型：
  - external-provisioner：监听 PVC 并调用 CreateVolume
  - external-attacher：监听 VolumeAttachment 并处理 attach/detach
  - external-resizer：监听 PVC 扩容请求
  - external-snapshotter：处理 Snapshot 请求
  - livenessprobe：sidecar 健康检查
```

### 8.2 完整部署示例（自研 CSI 驱动）

```yaml
# 1. Namespace
apiVersion: v1
kind: Namespace
metadata:
  name: csi-system
---
# 2. ServiceAccount
apiVersion: v1
kind: ServiceAccount
metadata:
  name: my-csi
  namespace: csi-system
---
# 3. ClusterRole（K8s 内置权限）
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: my-csi
rules:
- apiGroups: [""]
  resources: ["persistentvolumes"]
  verbs: ["get", "list", "watch", "create", "delete", "patch", "update"]
- apiGroups: [""]
  resources: ["nodes"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["storage.k8s.io"]
  resources: ["volumeattachments", "csinodes"]
  verbs: ["get", "list", "watch", "update"]
- apiGroups: ["storage.k8s.io"]
  resources: ["csidrivers"]
  verbs: ["get", "list", "watch", "create", "update", "delete"]
- apiGroups: ["storage.k8s.io"]
  resources: ["storageclasses"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["storage.k8s.io"]
  resources: ["volumeattachments/status"]
  verbs: ["patch", "update"]
- apiGroups: [""]
  resources: ["events"]
  verbs: ["list", "watch", "create", "update", "patch"]
- apiGroups: ["snapshot.storage.k8s.io"]
  resources: ["volumesnapshotclasses", "volumesnapshotcontents", "volumesnapshots"]
  verbs: ["get", "list", "watch", "update", "patch", "create", "delete"]
---
# 4. ClusterRoleBinding
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: my-csi
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: my-csi
subjects:
- kind: ServiceAccount
  name: my-csi
  namespace: csi-system
---
# 5. CSIDriver 对象（注册 CSI 驱动）
apiVersion: storage.k8s.io/v1
kind: CSIDriver
metadata:
  name: my-csi-driver
spec:
  attachRequired: true
  podInfoOnMount: true
  fsGroupPolicy: File
  storageCapacity: false
  volumeLifecycleModes:
  - Persistent
  - Ephemeral
  tokenRequests:
  - audience: my-csi-token
  capabilities: ["Persistent", "Ephemeral"]
---
# 6. StorageClass
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: my-csi-storage
provisioner: my-csi-driver
parameters:
  type: ssd
reclaimPolicy: Delete
volumeBindingMode: Immediate
allowVolumeExpansion: true
```

### 8.3 部署自研 CSI 驱动

```yaml
# 1. Controller 部署
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-csi-controller
  namespace: csi-system
spec:
  replicas: 1
  selector:
    matchLabels:
      app: my-csi
      component: controller
  template:
    metadata:
      labels:
        app: my-csi
        component: controller
    spec:
      serviceAccountName: my-csi
      containers:
      - name: my-csi
        image: registry.example.com/my-csi:v1.0
        args:
        - --endpoint=tcp://0.0.0.0:50051
        ports:
        - containerPort: 50051
---
# 2. Node 部署（DaemonSet）
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: my-csi-node
  namespace: csi-system
spec:
  selector:
    matchLabels:
      app: my-csi
      component: node
  template:
    metadata:
      labels:
        app: my-csi
        component: node
    spec:
      serviceAccountName: my-csi
      hostNetwork: false
      containers:
      - name: my-csi
        image: registry.example.com/my-csi:v1.0
        args:
        - --endpoint=unix:///csi/csi.sock
        - --nodeid=$(NODE_NAME)
        env:
        - name: NODE_NAME
          valueFrom:
            fieldRef:
              fieldPath: spec.nodeName
        volumeMounts:
        - name: csi-sock
          mountPath: /csi
        - name: pods-mount-dir
          mountPath: /var/lib/kubelet/pods
          mountPropagation: Bidirectional
        - name: plugin-dir
          mountPath: /var/lib/kubelet/plugins_registry
        - name: mountpoint-dir
          mountPath: /var/lib/kubelet/mounts
        securityContext:
          privileged: true          # 需要特权访问宿主机
        ports:
        - containerPort: 50051
          hostPort: 50051
      volumes:
      - name: csi-sock
        hostPath:
          path: /var/lib/kubelet/plugins_registry
          type: DirectoryOrCreate
      - name: pods-mount-dir
        hostPath:
          path: /var/lib/kubelet/pods
          type: Directory
      - name: plugin-dir
        hostPath:
          path: /var/lib/kubelet/plugins_registry
          type: DirectoryOrCreate
      - name: mountpoint-dir
        hostPath:
          path: /var/lib/kubelet/mounts
          type: Directory
```

---

## 九、CSI 最佳实践

### 9.1 设计原则

```text
1. 遵循 CSI 规范
   - 严格实现 gRPC 接口
   - 通过 CSI sanity 测试
   - 遵循版本兼容性

2. 幂等性
   - 所有操作可重入
   - 支持重试
   - 不依赖执行次数

3. 性能
   - Controller/Node 分离部署
   - 支持快照和扩容
   - 异步处理大文件

4. 错误处理
   - 明确的错误码
   - 详细的错误信息
   - 支持优雅降级

5. 安全
   - TLS 加密通信
   - Token 认证
   - 最小权限
```

### 9.2 测试

```bash
# 1. CSI sanity 测试（官方）
go test -v ./pkg/...

# 2. 端到端测试（K8s）
kubectl apply -f test-pvc.yaml
kubectl get pvc

# 3. 性能测试
# 部署 fio benchmark pod
# 测试 IOPS、吞吐量、延迟

# 4. 兼容性测试
# 在多 K8s 版本测试
# 在多 Linux 发行版测试
# 在多容器运行时测试（Docker、containerd、CRI-O）
```

### 9.3 CSI Driver 选型建议

```text
1. 云厂商存储
   - AWS EBS CSI：成熟、稳定
   - 阿里云 CBS：云原生集成
   - 腾讯云 CBS：完整功能

2. 分布式存储
   - Ceph RBD/CSI：成熟
   - Longhorn：轻量
   - Rook：Kubernetes 原生

3. 本地存储
   - local-path-provisioner：简单
   - TopoLVM：本地 LVM
   - OpenEBS：易用

4. 自研存储
   - 完整 CSI 实现
   - 复用 K8s Sidecar
   - 复用社区工具
```

---

## 十、参考资源

```text
- CSI 规范: https://github.com/container-storage-interface/spec
- CSI Sidecar 镜像: https://kubernetes-csi.github.io/docs/
- K8s 存储文档: https://kubernetes.io/docs/concepts/storage/
- Rook: https://rook.io/
- Longhorn: https://longhorn.io/
- OpenEBS: https://openebs.io/
- CSI 实战教程: https://kubernetes-csi.github.io/docs/developing.html
- 官方 sample: https://github.com/kubernetes-csi/csi-driver-host-path
- 实战 demo: https://github.com/kubernetes-csi/examples
```
## 速记卡

CSI = Container Storage Interface
三组件：Identity + Controller + Node
三 RPC 服务：Identity、Controller、Node
生命周期：Provision → Attach → Mount → Use → Unmount → Detach → Delete
关键对象：CSIDriver、StorageClass、PVC、PV
sidecar 模式：external-provisioner/attacher/resizer/snapshotter
数据面 RPC：NodeGetVolumeStats、NodeExpandVolume
卷快照：VolumeSnapshotClass + VolumeSnapshot
卷扩容：StorageClass allowVolumeExpansion: true
部署：Controller（Deployment） + Node（DaemonSet，privileged）