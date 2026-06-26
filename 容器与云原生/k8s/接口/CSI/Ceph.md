## 概念

Ceph 是 **统一存储系统**：块（RBD）、文件（CephFS）、对象（S3 兼容 RGW）三种接口一套集群。K8s 上用 **RBD 或 CephFS** 通过 CSI 暴露给 Pod。

* 项目起源：Sage Weil 2003 博士论文，2010s 走向成熟
* 治理：Ceph 基金会 → 已被 Red Hat 收购并入 OpenShift Data Foundation
* K8s CSI driver：`ceph-csi`（CNCF 官方，github.com/ceph/ceph-csi）

## 架构

```
┌────────────── K8s cluster ──────────────┐
│                                          │
│  ceph-csi (Deployment + DaemonSet)       │
│   ├─ external-provisioner sidecar       │
│   ├─ external-attacher sidecar          │
│   ├─ external-resizer sidecar           │
│   └─ external-snapshotter sidecar       │
│                                          │
└──────────────────┬───────────────────────┘
                   │ RADOS (librados)
                   ▼
┌─────────── Ceph cluster ────────────────┐
│  MON (集群元数据 / 选举) ×3+             │
│  MGR (集群状态 / dashboard) ×2+         │
│  OSD (数据存储, 每节点多个)              │
│  MDS (CephFS 元数据)                     │
│  RGW (S3 / Swift, 可选)                  │
│                                          │
│  副本: 3x 默认, EC 也可                  │
└─────────────────────────────────────────┘
```

* **MON**：保存 cluster map，paxos 选举
* **OSD**：每个 disk 一个进程，负责复制、恢复、回填
* **MGR**：manager，提供 dashboard / prometheus exporter
* **MDS**：CephFS 元数据服务
* **CRUSH 算法**：去中心化的数据分布（不查表，按权重 + 故障域）

## RBD vs CephFS

| 维度 | RBD | CephFS |
| --- | --- | --- |
| 接口 | 块设备 | 分布式文件系统（POSIX） |
| 协议 | librbd / kernel krbd | ceph-fuse / kernel cephfs |
| 共享 | ❌ ReadWriteOnce（单 Pod RW） | ✅ ReadWriteMany（多 Pod 共享） |
| 快照 | ✅ | ✅ |
| 克隆 | ✅ | ✅ |
| 性能 | 高（块直写） | 中（元数据开销） |
| 适用 | 数据库 / 单 Pod 块设备 | 共享数据 / AI 数据集 / 内容管理 |

## 部署

```bash
# 1. 用 Rook 部署 Ceph 集群（推荐,K8s 原生方式）
kubectl apply -f https://raw.githubusercontent.com/rook/rook/release-1.16/deploy/examples/crds.yaml
kubectl apply -f https://raw.githubusercontent.com/rook/rook/release-1.16/deploy/examples/operator.yaml
kubectl apply -f https://raw.githubusercontent.com/rook/rook/release-1.16/deploy/examples/cluster.yaml

# 2. 装 ceph-csi
kubectl apply -f https://raw.githubusercontent.com/ceph/ceph-csi/master/deploy/csi-driver-object.yaml  # 或 rbd.yaml

# 3. 建 StorageClass
```

StorageClass 示例（RBD）：

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: ceph-rbd
provisioner: rbd.csi.ceph.com
parameters:
  clusterID: <rook-ceph-cluster-id>
  pool: replicapool
  imageFormat: "2"
  imageFeatures: layering
  csi.storage.k8s.io/provisioner-secret-name: rook-csi-rbd-provisioner
  csi.storage.k8s.io/provisioner-secret-namespace: rook-ceph
  csi.storage.k8s.io/node-publish-secret-name: rook-csi-rbd-node
  csi.storage.k8s.io/node-publish-secret-namespace: rook-ceph
reclaimPolicy: Delete
volumeBindingMode: Immediate
```

## 优缺点

* ✅ **三合一**：块 / 文件 / 对象统一集群
* ✅ **成熟稳定**：15+ 年发展，大规模验证（EB 级）
* ✅ **去中心化**：无单点，CRUSH 算法可预测
* ✅ **生态完整**：Rook Operator 一键部署，OpenShift Data Foundation 集成
* ✅ 多协议互通（同一份数据 RBD / CephFS / RGW 都能访问）
* ❌ **运维复杂**：MON / OSD / MDS / MGR 都要懂
* ❌ 默认 3 副本，磁盘利用率 33%，要 EC 提高
* ❌ 故障恢复期（rebalance）IO 受影响
* ❌ 学习曲线陡
* ❌ 高性能场景（低延迟 DB）需要 NVMe / SPDK 调优

## 适用场景

* **大集群统一存储**（>10 节点，混合 workload）
* 既要块又要共享文件（CephFS）
* AI / 大数据（HDFS 替代）
* 自建对象存储（S3 替代）
* OpenShift 用户（ODF 集成）

## 监控 / 排查

```bash
# Ceph 状态
ceph -s
ceph health detail
ceph osd tree

# OSD 性能
ceph osd perf

# 看 Pool 用量
ceph df

# Dashboard
ceph mgr dashboard

# K8s 这边
kubectl -n rook-ceph get pods
kubectl -n rook-ceph logs -l app=csi-rbdplugin
```

## 一句话

**统一存储三件套（块 / 文件 / 对象），Rook + ceph-csi 一键起，运维复杂但能力全面**。