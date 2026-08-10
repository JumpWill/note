# OpenEBS

CNCF 沙箱项目，**K8s 原生的容器化存储 (Container Attached Storage, CAS)**。把存储引擎跑成 K8s Pod 挂载在每个节点上，**节点即存储**，简化存储管理。

## 一、定位与特性

- **容器化存储**：存储引擎是 K8s 部署的微服务
- **节点即存储**：用 K8s 节点本地盘做存储
- **CAS 理念**：存储引擎与业务 Pod 同样由 K8s 管理
- **多引擎**：cStor / Jiva / Mayastor / NDB
- **CSI 标准**：完整 CSI 1.x 支持
- **快照、克隆、备份**：通过 OpenEBS 或 Velero
- **云原生优**：与 K8s 调度、监控、自愈深度集成

## 二、核心组件

| 组件 | 角色 |
| --- | --- |
| **OpenEBS Operator** | 管理存储引擎、CRD |
| **NDM (Node Disk Manager)** | 发现节点磁盘、SMART 健康 |
| **cStor** | 高可靠存储引擎（副本 / 池化） |
| **Jiva** | 轻量存储引擎（仅本地副本） |
| **Mayastor** | 高性能 NVMe-oF 引擎 |
| **NDB** | 数据库专用（MySQL / Postgres 集群） |
| **CSI Plugin** | 给 K8s 提供块 / 文件接口 |

## 三、核心概念

| 概念 | 含义 |
| --- | --- |
| **StorageClass** | K8s 存储类，引用 OpenEBS provisioner |
| **Pool (SPC / CSP)** | 一组节点磁盘组成的池（cStor） |
| **Volume (PVC)** | 用户视角的卷 |
| **Replica** | 数据副本 |
| **Target** | 卷的 IO 端点（cStor pool pod / jiva replica pod） |

## 四、存储引擎对比

| 引擎 | 冗余 | 性能 | 复杂度 | 场景 |
| --- | --- | --- | --- | --- |
| **Jiva** | 3 副本 (在 Pod 中) | 中 | 极低 | 入门、测试、要求不高 |
| **cStor** | 副本 / 池化 / 压缩 | 中高 | 中 | 生产常见 |
| **Mayastor** | 单副本 + NVMe-oF 副本 | 极高 | 高 | 高性能数据库 |
| **NDB** | 自带数据库集群 | - | 中 | MySQL / Postgres 一站式 |

> **入门用 Jiva，生产用 cStor，极致性能用 Mayastor，数据库用 NDB**。

## 五、典型架构

### 1. cStor

```text
应用 Pod
   ↓ PVC (CSI)
cStor Target Pod (IO 入口)
   ├── 副本 1 → cStor Pool Pod → 节点本地盘
   ├── 副本 2 → cStor Pool Pod → 节点本地盘
   └── 副本 3 → cStor Pool Pod → 节点本地盘
```

- cStor Pool Pod 通常与 NodeDiskManager 配对
- 数据同步多副本，强一致
- 适合 ZFS / 快照 / 压缩能力诉求

### 2. Jiva

```text
应用 Pod
   ↓ PVC
Jiva Target Pod
   ├── 副本 1 (Jiva Replica Pod)
   ├── 副本 2 (Jiva Replica Pod)
   └── 副本 3 (Jiva Replica Pod)
```

- 直接用节点本地盘（无 Pool）
- 简单、可靠、性能一般
- 适合小规模 / 测试 / 单节点

### 3. Mayastor

```text
应用 Pod
   ↓ NVMe-oF / SPDK
Mayastor Replica Pod
   └── 节点本地 NVMe
```

- 单节点不复制，跨节点通过 NVMe-oF 拉取
- 性能接近裸盘
- 适合高端存储

## 六、典型部署

```bash
# 1. 安装 OpenEBS Operator
helm repo add openebs https://openebs.github.io/openebs
helm install openebs openebs/openebs --namespace openebs --create-namespace

# 2. 自动发现节点磁盘
kubectl get blockdevice -n openebs

# 3. 创建 StorageClass
kubectl apply -f - <<EOF
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: openebs-cstor
provisioner: openebs.io/provisioner-iscsi
parameters:
  poolType: striped
  replicaCount: "3"
  cstorPoolCluster: cstor-pool
EOF

# 4. 创建 PVC
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: my-data
spec:
  storageClassName: openebs-cstor
  accessModes: [ReadWriteOnce]
  resources:
    requests:
      storage: 100Gi
```

## 七、核心特性

### 1. 快照与克隆

- 支持 K8s VolumeSnapshot
- cStor 支持基于快照的克隆
- 适合数据库备份、CI 测试数据准备

### 2. 监控

- 内置 Prometheus metrics
- OpenEBS 暴露每个 Pool / Volume / Replica 指标
- 节点磁盘健康由 NDM 上报

### 3. 数据保护

- 跨节点副本（cStor）
- 加密（Mayastor）
- 与 Velero 集成做应用级备份

### 4. 资源管理

- 每个 Pool Pod 资源隔离
- QoS：可设置 IO 优先级

## 八、与 Rook-Ceph 对比

| 维度 | OpenEBS | Rook-Ceph |
| --- | --- | --- |
| 架构 | CAS (节点即存储) | 独立存储集群 |
| 复杂度 | 低 | 高 |
| 部署 | 轻 | 重 |
| 协议 | 块 (iSCSI / NVMe-oF) | 块 / 文件 / 对象 |
| 多节点复制 | 是 (cStor) | 是 (CRUSH) |
| 大规模 | 中 | 优 |
| 性能 | 取决于引擎 | 高 |
| 云原生 | 优 | 良 |
| 适合规模 | TB 级 | PB ~ EB |

> **小规模 / 单集群 K8s,OpenEBS 更轻**;大规模生产存储,Rook-Ceph 仍是首选。

## 九、典型使用场景

- K8s 上的有状态应用（数据库、消息队列）
- 单集群存储标准
- 边缘 / 边缘计算场景
- 数据库专用存储（NDB）
- 替代本地盘 / NFS
- 简单的 K8s 存储类供给

## 十、运维要点

- **节点选择**:存储节点 + 业务节点可分离（用污点）
- **资源预留**:给 Pool Pod / Replica Pod 预留内存、CPU
- **磁盘健康**:关注 NDM 报告的 SMART 状态
- **副本分布**:副本**不要**全在同一节点
- **升级**:Operator 升级时引擎版本兼容要确认

## 十一、选型建议

| 场景 | 推荐引擎 |
| --- | --- |
| 学习、测试 | Jiva |
| 普通生产（MySQL / MongoDB） | cStor |
| 高性能数据库（NVMe） | Mayastor |
| MySQL / Postgres 集群 | NDB |
| 单节点测试 | LocalPV / Hostpath |

## 十二、注意事项

- 节点故障 → 副本恢复依赖其他节点健康
- **不要把 OpenEBS 部署在少于 3 个节点的集群**（副本无法保障）
- 节点失联时复制数据有 IO 风暴风险
- 升级前**必读 release notes**,引擎兼容性常变
