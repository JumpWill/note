# Rook

Ceph 在 Kubernetes 上的**云原生编排层**，由 CNCF 毕业。把 Ceph 的部署、配置、扩容、升级、监控、灾备**全部用 Operator 模式**在 K8s 上管理，是 K8s 跑 Ceph 的事实标准。

## 一、定位与特性

- **Ceph 的 K8s 编排器**:不重新发明存储，而是用 Operator 管 Ceph
- **CNCF 毕业项目**:生产级
- **自动化运维**:部署、扩容、升级、备份、监控
- **K8s 原生**:Ceph 跑成 Pod、用 K8s 调度和自愈
- **CSI 集成**:直接给 K8s 提供 RBD / CephFS 存储类
- **多存储后端**:除 Ceph 外还支持 EdgeFS / NFS / Cassandra(部分版本)
- **可观察性**:内置 Prometheus 指标、Operator Dashboard

## 二、核心组件

| 组件 | 角色 |
| --- | --- |
| **Rook Operator** | 协调者，监听 CRD 并调和集群状态 |
| **Ceph Cluster CRD** | Ceph 集群声明 |
| **Ceph Block Pool / Filesystem / Object Store CRD** | 资源声明 |
| **CSI Driver** | K8s 容器存储接口（rbd.csi / cephfs.csi） |
| **Rook Toolbox** | 调试工具 Pod |
| **OSD Pod** | 每块盘一个 OSD 容器 |
| **MON Pod** | Ceph Monitor 容器 |
| **MGR Pod** | Manager 容器 |
| **MDS / RGW Pod** | 按需部署 |

## 三、典型架构

```text
K8s Cluster
   │
   ├── rook-ceph namespace
   │     ├── rook-ceph-operator
   │     ├── rook-ceph-mon-a / b / c
   │     ├── rook-ceph-mgr-a / b
   │     ├── rook-ceph-osd-0 / 1 / 2 ...
   │     ├── rook-ceph-rgw-myobj
   │     ├── rook-ceph-mds-myfs
   │     └── csi-rbdplugin / csi-cephfsplugin
   │
   └── 应用 namespace
         ├── Pod 1 (挂 PVC)
         ├── Pod 2 (挂 PVC)
         └── Pod 3 (挂 PVC, RWO)
```

- Ceph 所有组件跑在 `rook-ceph` namespace
- OSD 复用宿主机裸盘（`/dev/sdb` 等）
- 应用 Pod 通过 PVC 挂载

## 四、CRD 体系

```yaml
# CephCluster: 声明整个集群
apiVersion: ceph.rook.io/v1
kind: CephCluster
metadata:
  name: rook-ceph
  namespace: rook-ceph
spec:
  cephVersion:
    image: quay.io/ceph/ceph:v18.2.0
  dataDirHostPath: /var/lib/rook
  mon:
    count: 3
  storage:
    useAllNodes: true
    useAllDevices: true
  dashboard:
    enabled: true
```

```yaml
# CephBlockPool: 块存储池
apiVersion: ceph.rook.io/v1
kind: CephBlockPool
metadata:
  name: replicapool
spec:
  replicated:
    size: 3
```

```yaml
# CephFilesystem: 文件存储
apiVersion: ceph.rook.io/v1
kind: CephFilesystem
metadata:
  name: myfs
spec:
  metadataPool:
    replicated:
      size: 3
  dataPools:
    - name: myfs-data
      replicated:
        size: 3
  metadataServer:
    activeCount: 2
```

```yaml
# CephObjectStore: 对象存储 (RGW)
apiVersion: ceph.rook.io/v1
kind: CephObjectStore
metadata:
  name: myobj
spec:
  dataPool:
    replicated:
      size: 3
  metadataPool:
    replicated:
      size: 3
  gateway:
    port: 80
```

## 五、存储类 (StorageClass)

```yaml
# RBD 块存储 (RWO)
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: rook-ceph-block
provisioner: rook-ceph.rbd.csi.ceph.com
parameters:
  clusterID: rook-ceph
  pool: replicapool
  imageFormat: "2"
  csi.storage.k8s.io/provisioner-secret-name: rook-csi-rbd-provisioner
  csi.storage.k8s.io/provisioner-secret-namespace: rook-ceph
  csi.storage.k8s.io/node-publish-secret-name: rook-csi-rbd-node
  csi.storage.k8s.io/node-publish-secret-namespace: rook-ceph
reclaimPolicy: Delete
```

```yaml
# CephFS 文件存储 (RWX)
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: rook-cephfs
provisioner: rook-ceph.cephfs.csi.ceph.com
parameters:
  clusterID: rook-ceph
  fsName: myfs
  pool: myfs-data0
  csi.storage.k8s.io/provisioner-secret-name: rook-csi-cephfs-provisioner
  csi.storage.k8s.io/provisioner-secret-namespace: rook-ceph
  csi.storage.k8s.io/node-publish-secret-name: rook-csi-cephfs-node
  csi.storage.k8s.io/node-publish-secret-namespace: rook-ceph
reclaimPolicy: Delete
```

## 六、典型使用

```yaml
# 块存储 PVC
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: mysql-data
spec:
  storageClassName: rook-ceph-block
  accessModes: [ReadWriteOnce]
  resources:
    requests:
      storage: 100Gi
```

```yaml
# 文件存储 PVC (多 Pod 共享)
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: shared-data
spec:
  storageClassName: rook-cephfs
  accessModes: [ReadWriteMany]
  resources:
    requests:
      storage: 1Ti
```

## 七、核心能力

### 1. 自动化部署

- 一次 `kubectl apply -f cluster.yaml` 部署完整 Ceph
- 自动选 MON / MGR / OSD 节点
- 自动配置 CRUSH、网络、认证

### 2. 自动扩容

- 加节点 → 自动加 OSD
- 扩 MON / MGR 通过修改 CephCluster spec
- 扩 RGW / MDS 同样修改 CR

### 3. 滚动升级

- Ceph 版本升级：改 `cephVersion.image`
- Operator 自动滚动升级 MON / MGR / OSD
- 支持跨大版本升级（需谨慎）

### 4. 自愈

- OSD 故障 → K8s 重启 Pod
- MON 故障 → Operator 调度新 Pod
- 网络分区 → 自动选主

### 5. 备份与恢复

- 内置 Ceph 快照 (RBD snapshot / CephFS snapshot)
- 集成外部备份（Velero + RBD、Ceph S3 API）
- 灾备：跨集群异步复制

## 八、监控

- 内置 Prometheus 抓取
- 服务发现：ServiceMonitor 自动生成
- 关键告警：
  - OSD down / OSD 满
  - MON down
  - PG 状态异常
  - 容量 near full / full
  - Ceph 健康 not OK

## 九、与裸金属部署对比

| 维度 | Rook-Ceph | 裸金属 Ceph |
| --- | --- | --- |
| 部署难度 | 极低 | 高 |
| 节点管理 | K8s | Ansible / cephadm |
| 升级 | Operator 滚动 | 手动滚动 |
| 监控 | K8s 原生 | 自建 |
| 资源开销 | 多一层（容器化） | 直接 |
| 故障域 | K8s 调度 | 物理拓扑 |
| 适合场景 | K8s 优先 | 物理 / 虚拟化 |

## 十、典型使用场景

- K8s 上的有状态应用（数据库、消息队列）
- 跨 Pod 共享存储（CI、媒资、模型）
- 私有云的统一存储（块 + 文件 + 对象）
- 替代 ceph-deploy / ceph-ansible

## 十一、常见问题与坑

- **OSD 设备选择**:`useAllDevices` 容易误用，先选好
- **资源消耗**:OSD 容器吃内存，节点内存要充足
- **网络**:OSD 之间流量大，节点间网络要好
- **升级**:跨大版本要按官方路径
- **数据安全**:生产环境**禁止单 MON**
- **生产实践**:OSD 节点加污点，让业务 Pod 不要调度到存储节点

## 十二、调优

- **PG 数**:集群建好就定好，扩 OSD 后调
- **副本数**:默认 3，按业务调整
- **网络**:分离 public / cluster 网络
- **crush 规则**:按机架 / 域分布
- **资源限制**:给 OSD / MON 设置 resources
