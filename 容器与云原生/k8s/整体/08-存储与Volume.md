# 存储与 Volume (Storage & Volumes)

> 本章系统讲解 K8s 的存储体系:Volume、PV/PVC、StorageClass、CSI 与动态供给。

## 一、存储概述

### 1.1 为什么需要 Volume

```text
问题: 容器内数据是临时的
   - Pod 重启后,容器内数据丢失
   - 容器之间无法共享数据

Volume 解决:
   - Pod 重启数据保留
   - 多容器共享数据
   - 跨主机数据迁移
```

### 1.2 Volume 类型概览

```text
Volume 类型:

1. 本地存储 (Node 级别)
   - emptyDir       - Pod 临时目录
   - hostPath       - 节点目录
   - local          - 持久本地 (1.14+)

2. 网络存储 (远程)
   - nfs
   - iscsi
   - cephfs / rbd
   - glusterfs

3. 云存储 (云厂商)
   - awsElasticBlockStore (EBS)
   - azureDisk / azureFile
   - gcePersistentDisk
   - 阿里云 disk / NAS / OSS

4. K8s 资源
   - persistentVolumeClaim
   - configMap / secret

5. CSI (Container Storage Interface)
   - 通用存储接口,推荐使用
```

---

## 二、Volume 基础

### 2.1 Pod 中使用 Volume

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: my-pod
spec:
  containers:
  - name: app
    image: nginx:1.25
    volumeMounts:
    - name: cache-volume
      mountPath: /cache             # 容器内挂载点
    - name: config-volume
      mountPath: /etc/config
      readOnly: true

  volumes:
  - name: cache-volume
    emptyDir: {}                    # 临时目录

  - name: config-volume
    configMap:
      name: app-config
      items:
      - key: application.yml
        path: app.yml
```

### 2.2 Volume 生命周期

```text
1. Pod 创建时,Volume 被创建
2. Volume 挂载到容器
3. Pod 运行期间 Volume 保持
4. Pod 删除时,Volume 销毁 (除非是 PV/PVC)
```

---

## 三、emptyDir

### 3.1 概念

**emptyDir** 是一个 Pod 启动时创建的空目录,Pod 删除时数据消失。

```yaml
spec:
  containers:
  - name: writer
    image: alpine
    volumeMounts:
    - name: shared-data
      mountPath: /data
    command: ["sh", "-c", "echo hello > /data/file"]

  - name: reader
    image: alpine
    volumeMounts:
    - name: shared-data
      mountPath: /data
    command: ["cat", "/data/file"]
    # 输出: hello (共享数据)

  volumes:
  - name: shared-data
    emptyDir: {}
```

### 3.2 emptyDir 用途

```text
1. 容器间共享临时数据
2. 临时缓存
3. 共享配置文件
4. Sort/SPILL 临时文件
```

### 3.3 medium 选项 (1.28+)

```yaml
volumes:
- name: cache
  emptyDir:
    sizeLimit: 1Gi        # 限制大小
    medium: Memory        # 用 RAM (tmpfs),性能高
    # medium: "" (默认,磁盘)
```

---

## 四、hostPath

### 4.1 概念

**hostPath** 把节点上的目录挂载到 Pod 中。

```yaml
spec:
  containers:
  - name: app
    volumeMounts:
    - name: host-var-log
      mountPath: /var/log/pods
      readOnly: true

  volumes:
  - name: host-var-log
    hostPath:
      path: /var/log/pods
      type: Directory        # 必须是目录
      # type: File | DirectoryOrCreate | FileOrCreate
```

### 4.2 hostPath 用途

```text
1. DaemonSet 日志收集 (Fluent-bit)
   - 挂载 /var/log 到容器

2. 监控 agent
   - 挂载 /proc, /sys

3. 单节点调试 (生产慎用)

⚠️ 风险:
- Pod 漂移后访问不到数据 (新节点没有该路径)
- 节点故障导致数据丢失
- 安全风险 (容器逃逸可访问宿主机)
```

---

## 五、PV/PVC (核心)

### 5.1 概念

**PV (PersistentVolume)**: 集群级别的存储资源抽象(管理员创建)
**PVC (PersistentVolumeClaim)**: 用户对存储的请求(应用引用)

```text
关系:
  物理存储 → PV (集群级资源) → PVC (命名空间资源) → Pod volumeMount

PV 是"存储的实际提供者"
PVC 是"用户对存储的需求"
```

### 5.2 PV 定义

```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: pv-nfs-data
  labels:
    type: nfs
spec:
  # 容量
  capacity:
    storage: 100Gi

  # 访问模式
  accessModes:
  - ReadWriteOnce        # RWO - 单节点读写
  - ReadOnlyMany         # ROX - 多节点只读
  - ReadWriteMany        # RWX - 多节点读写

  # 回收策略
  persistentVolumeReclaimPolicy:
    - Retain             # 保留 (推荐生产)
    - Recycle            # 回收 (已废弃)
    - Delete             # 删除 (自动清理)

  # 存储类 (用于动态供给)
  storageClassName: nfs-storage

  # 访问模式匹配规则
  mountOptions:
  - hard
  - nfsvers=4.1

  # 底层存储
  nfs:
    server: 10.0.0.10
    path: "/exports/data"

  # 或 hostPath (本地)
  # hostPath:
  #   path: /data/nfs
  #   type: DirectoryOrCreate
```

### 5.3 PVC 定义

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: my-app-pvc
  namespace: production
spec:
  # 资源请求
  resources:
    requests:
      storage: 50Gi

  # 访问模式 (必须与 PV 匹配)
  accessModes:
  - ReadWriteOnce

  # 存储类 (重要: 触发动态供给)
  storageClassName: nfs-storage

  # 选择器 (可选,精确绑定特定 PV)
  selector:
    matchLabels:
      type: ssd
```

### 5.4 Pod 使用 PVC

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mysql
spec:
  template:
    spec:
      containers:
      - name: mysql
        image: mysql:8.0
        volumeMounts:
        - name: data
          mountPath: /var/lib/mysql

      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: my-app-pvc     # 引用 PVC
```

### 5.5 访问模式详解

| 模式 | 缩写 | 说明 |
|------|------|------|
| ReadWriteOnce | RWO | 单节点读写 (块存储) |
| ReadOnlyMany | ROX | 多节点只读 |
| ReadWriteMany | RWX | 多节点读写 (NFS、CEPHFS) |
| ReadWriteOncePod | RWOP | 单 Pod 读写 (1.22+) |

### 5.6 PV 生命周期

```text
Provisioning (供给)
   ↓ 静态: 管理员预创建 PV
   ↓ 动态: StorageClass 自动创建
Binding (绑定)
   ↓ PVC 自动匹配 PV
Using (使用)
   ↓ Pod 挂载 PVC
Releasing (释放)
   ↓ Pod 删除, PV 状态 → Released
Reclaiming (回收)
   ↓ Retain / Recycle / Delete
```

---

## 六、StorageClass 与动态供给

### 6.1 概念

**StorageClass** 是存储的"类",定义了如何动态创建 PV (无需管理员预创建)。

```text
动态供给流程:
   用户创建 PVC → StorageClass 自动创建 PV → 自动绑定 PVC/PV → Pod 使用
```

### 6.2 StorageClass 定义

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: fast-ssd
  annotations:
    storageclass.kubernetes.io/is-default-class: "true"
provisioner: kubernetes.io/aws-ebs    # 或 csi-driver
parameters:
  type: gp3
  iopsPerGB: "50"
  fsType: ext4
  encrypted: "true"
reclaimPolicy: Delete
volumeBindingMode: WaitForFirstConsumer
allowVolumeExpansion: true
mountOptions:
- debug
```

### 6.3 主流 provisioner

| Provisioner | 存储 |
|-------------|------|
| kubernetes.io/aws-ebs | AWS EBS |
| kubernetes.io/gce-pd | GCP PD |
| kubernetes.io/azure-disk | Azure Disk |
| kubernetes.io/nfs | NFS |
| ceph.com/csi | Ceph RBD |
| csi-driver-smb | SMB |
| 阿里云 CSI | 阿里云 NAS/OSS/Disk |

### 6.4 动态供给示例 (阿里云)

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: alicloud-disk-ssd
provisioner: diskplugin.csi.alibabacloud.com
parameters:
  type: cloud_ssd
  region: cn-hangzhou
  zoneId: cn-hangzhou-h
  fsType: ext4
  encrypted: "true"
reclaimPolicy: Delete
volumeBindingMode: WaitForFirstConsumer
```

```yaml
# PVC 自动触发 PV 创建
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: mysql-data
spec:
  accessModes:
  - ReadWriteOnce
  storageClassName: alicloud-disk-ssd
  resources:
    requests:
      storage: 100Gi
```

```yaml
# Pod 使用
spec:
  containers:
  - name: mysql
    volumeMounts:
    - name: data
      mountPath: /var/lib/mysql
  volumes:
  - name: data
    persistentVolumeClaim:
      claimName: mysql-data
```

### 6.5 常用参数

```text
provisioner:        必需,谁来创建 PV
reclaimPolicy:      Delete / Retain
volumeBindingMode:  Immediate / WaitForFirstConsumer
allowVolumeExpansion: true (允许扩容)
mountOptions:       文件系统挂载选项
parameters:         provisioner 特定参数
```

**WaitForFirstConsumer** (推荐):延迟绑定 PVC,直到 Pod 创建才创建 PV,实现拓扑感知。

---

## 七、Volume 类型详解

### 7.1 NFS

```yaml
# PV
apiVersion: v1
kind: PersistentVolume
metadata:
  name: pv-nfs
spec:
  capacity:
    storage: 100Gi
  accessModes:
  - ReadWriteMany             # NFS 支持多节点读写
  persistentVolumeReclaimPolicy: Retain
  storageClassName: ""
  nfs:
    server: 10.0.0.10
    path: "/exports/data"
```

### 7.2 cephRBD / cephFS

```yaml
# cephRBD PV
apiVersion: v1
kind: PersistentVolume
metadata:
  name: pv-ceph-rbd
spec:
  capacity:
    storage: 200Gi
  accessModes:
  - ReadWriteOnce
  persistentVolumeReclaimPolicy: Retain
  rbd:
    monitors:
    - 10.0.0.11:6789
    - 10.0.0.12:6789
    pool: rbd
    image: my-rbd-image
    user: admin
    keyring: /etc/ceph/keyring
    fsType: ext4
    readOnly: false
```

### 7.3 AWS EBS

```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: pv-aws-ebs
spec:
  capacity:
    storage: 500Gi
  accessModes:
  - ReadWriteOnce
  persistentVolumeReclaimPolicy: Delete
  storageClassName: gp3
  awsElasticBlockStore:
    volumeID: vol-0123456789abcdef0
    fsType: ext4
```

---

## 八、CSI (Container Storage Interface)

### 8.1 概念

**CSI** 是 K8s 与存储厂商的标准接口,使任何存储厂商只需实现 CSI 接口即可被 K8s 使用。

```text
CSI 架构:
  - CSI Driver (外部进程,不在 K8s 主进程内)
  - gRPC 接口与 kubelet 通信
  - 实现 CreateVolume / DeleteVolume / Attach / Detach 等
```

### 8.2 主流 CSI Driver

| Driver | 厂商 |
|--------|------|
| aws-ebs-csi-driver | AWS EBS |
| gcp-pd-csi-driver | GCP PD |
| azure-disk-csi-driver | Azure Disk |
| 阿里云 disk-csi-driver | 阿里云 Disk |
| ceph-csi-driver | Ceph |
| nfs-csi-driver | NFS |
| minio-csi-driver | MinIO S3 |

### 8.3 安装 CSI Driver (以 AWS EBS 为例)

```bash
# 1. 安装驱动
kubectl apply -k "github.com/kubernetes-sigs/aws-ebs-csi-driver/deploy/kubernetes/overlays/stable/?ref=release-1.20"

# 2. 创建 StorageClass
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: ebs-sc
provisioner: ebs.csi.aws.com
parameters:
  type: gp3
  fsType: ext4
reclaimPolicy: Delete
volumeBindingMode: WaitForFirstConsumer

# 3. 创建 PVC 测试
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: test-pvc
spec:
  accessModes: [ReadWriteOnce]
  storageClassName: ebs-sc
  resources:
    requests:
      storage: 10Gi
```

---

## 九、StatefulSet 中的存储

### 9.1 volumeClaimTemplates

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: mysql
spec:
  serviceName: mysql
  replicas: 3
  template:
    spec:
      containers:
      - name: mysql
        image: mysql:8.0
        volumeMounts:
        - name: data
          mountPath: /var/lib/mysql

  volumeClaimTemplates:          # 每个 Pod 自动创建独立 PVC
  - metadata:
      name: data
    spec:
      accessModes: [ReadWriteOnce]
      storageClassName: fast-ssd
      resources:
        requests:
          storage: 100Gi
```

自动创建:
- PVC: data-mysql-0, data-mysql-1, data-mysql-2
- 每个 Pod 独立绑定自己的 PVC
- Pod 删除后 PVC 保留 (Retain 策略)
- Pod 重新调度到其他节点,数据自动挂载

### 9.2 PVC 生命周期

```text
Pod 删除 → StatefulSet 不自动删除 PVC (数据保留)
Pod 重新调度 → 新 Pod 自动绑定同名 PVC → 数据恢复
手动清理 → kubectl delete pvc data-mysql-0
```

---

## 十、CSI 卷克隆与快照

### 10.1 卷快照 (Snapshot)

```yaml
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshot
metadata:
  name: mysql-snapshot
spec:
  volumeSnapshotClassName: csi-snapclass
  source:
    persistentVolumeClaimName: mysql-data
```

```yaml
# 从快照恢复
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: mysql-data-restored
spec:
  dataSourceRef:
    apiGroup: snapshot.storage.k8s.io
    kind: VolumeSnapshot
    name: mysql-snapshot
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 100Gi
```

### 10.2 卷克隆 (Clone)

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: mysql-data-clone
spec:
  dataSourceRef:
    apiVersion: v1
    kind: PersistentVolumeClaim
    name: mysql-data        # 从已有 PVC 克隆
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 100Gi
```

---

## 十一、Storage 实战

### 11.1 部署高可用 MySQL (StatefulSet + 持久化)

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: mysql
spec:
  serviceName: mysql-headless
  replicas: 3
  selector:
    matchLabels:
      app: mysql
  template:
    metadata:
      labels:
        app: mysql
    spec:
      containers:
      - name: mysql
        image: mysql:8.0
        env:
        - name: MYSQL_ROOT_PASSWORD
          valueFrom:
            secretKeyRef:
              name: mysql-secret
              key: password
        ports:
        - containerPort: 3306
        volumeMounts:
        - name: data
          mountPath: /var/lib/mysql
        resources:
          requests:
            cpu: 500m
            memory: 1Gi
          limits:
            cpu: 2000m
            memory: 4Gi
        readinessProbe:
          exec:
            command: ["mysqladmin", "ping"]
          initialDelaySeconds: 30
          periodSeconds: 10

  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: [ReadWriteOnce]
      storageClassName: fast-ssd
      resources:
        requests:
          storage: 100Gi
```

### 11.2 扩容 PVC

```bash
# 1. 修改 PVC spec.resources.requests.storage
kubectl edit pvc mysql-data-mysql-0
# storage: 100Gi → 200Gi

# 2. 验证 StorageClass 允许扩容
# allowVolumeExpansion: true (需在 SC 中设置)
```

### 11.3 数据迁移

```bash
# 1. 创建快照
kubectl create -f snapshot.yaml

# 2. 创建新 PVC 从快照恢复
kubectl create -f restored-pvc.yaml

# 3. 替换 StatefulSet 的 PVC
kubectl edit statefulset mysql
# 替换 volumeClaimTemplates 的 storageClassName 指向新 PVC
```

---

## 十二、存储最佳实践

### 12.1 选择存储类型

| 场景 | 推荐 |
|------|------|
| 数据库 | 块存储 (EBS, 云盘) - 高 IOPS |
| 文件存储 | NFS / 对象存储 |
| 多 Pod 共享 | RWX 存储 (NFS, cephFS) |
| 临时数据 | emptyDir (内存) |
| 日志 | hostPath + 专用日志存储 |

### 12.2 存储安全

```text
1. 启用 etcd 加密 (Secret 也加密)
2. PV/PVC 用 RBAC 控制
3. 敏感数据使用 External Secrets
4. 定期备份 (用 Velero)
5. 存储加密 (云厂商支持)
```

### 12.3 容量规划

```text
- 预留 20% 余量
- 监控磁盘使用率 (Prometheus + node_exporter)
- 启用 Volume 自动扩容 (云厂商)
- 定期清理无用数据
```

### 12.4 备份与恢复

```text
工具: Velero (Restic 集成)
  - 备份 K8s 资源 + PV 数据
  - 跨集群迁移
  - 灾难恢复

安装:
  velero install \
    --provider aws \
    --bucket my-bucket \
    --prefix backups \
    --secret-file ./credentials-velero
```

---

## 核心要点速记

### 存储三件套

```text
PV  (PersistentVolume):     集群级存储资源
PVC (PersistentVolumeClaim): 用户对存储的请求
StorageClass:                动态供给策略
```

### Volume 类型选择

```text
临时数据 (Pod 内共享)      → emptyDir
节点目录 (日志/调试)        → hostPath
数据库 (高 IOPS, RWO)       → 块存储 (EBS, 云盘)
文件共享 (多 Pod, RWX)      → NFS, cephFS
配置 / 密钥                 → ConfigMap / Secret 挂载
```

### 动态供给 vs 静态

```text
静态 (传统):
  管理员预创建 PV
  PVC 自动匹配 PV
  适合: 小集群 / 严格控制

动态 (推荐):
  创建 StorageClass
  PVC 触发自动创建 PV
  适合: 云环境 / 大规模
```

### StatefulSet 存储

```text
volumeClaimTemplates → 自动给每个 Pod 创建独立 PVC
数据跟随 Pod 生命周期 (Pod 漂移数据不丢)
删除 StatefulSet 不删除 PVC (Retain 策略)
手动删除 PVC 才真正删除数据
```

### 实战速记

```text
扩容 PVC: 修改 storage 字段 (需 SC 支持 allowVolumeExpansion)
快照: VolumeSnapshot CRD + SnapshotClass
克隆: dataSourceRef 指向源 PVC
备份: Velero (官方推荐)
```

### 访问模式匹配

```text
RWO (ReadWriteOnce):       块存储 (EBS, 云盘)
ROX (ReadOnlyMany):        文件存储
RWX (ReadWriteMany):       NFS, cephFS
RWOP (ReadWriteOncePod):   1.22+ 新模式

PVC 申请的 accessModes 必须与 PV 匹配
```

---

## 参考

- **PV/PVC**: https://kubernetes.io/docs/concepts/storage/persistent-volumes/
- **StorageClass**: https://kubernetes.io/docs/concepts/storage/storage-classes/
- **CSI**: https://kubernetes-csi.github.io/docs/
- **Velero**: https://velero.io/
