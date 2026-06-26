## 概念

OpenEBS 是 MayaData（被 DataCore 收购）开发的 **K8s 原生存储**，**每个 volume 是独立微服务**（与 Longhorn 类似，但有多个存储引擎可选）。

* 设计哲学：**Containerized Storage**：把存储控制面打散到每个 volume 一个 pod
* 三个引擎可选：
  * **cStor**：传统副本模式，灵活
  * **Mayastor**：v1，io_uring + SPDK 高性能，**目前主推**
  * **Jiva**：轻量，**已不推荐**
* 备份：内置 Velero 集成 + OpenEBS Snapshots

## 三个引擎对比

| 引擎 | 架构 | 性能 | 状态 |
| --- | --- | --- | --- |
| **cStor** | cStor pool + volume replica pod | 中 | 稳定，主用 |
| **Mayastor** | io_uring + SPDK + NVMe-oF | 高 | v1，主推 |
| **Jiva** | 单 pod 副本 | 低 | **已不推荐** |
| **NFS** | 用别的 NFS server（如 Local Path Provisioner + nfs） | - | 共享文件场景 |

## 架构（Mayastor 为例）

```
┌──────── K8s cluster ────────────────┐
│                                       │
│  mayastor-control-plane (Deployment) │
│   - agent / etcd / rest / csi         │
│                                       │
│  mayastor-csi (Deployment)            │
│  mayastor-io-engine (DaemonSet, NVMe)│
│                                       │
│  每个 volume:                         │
│   - nexus (主)                        │
│   - replica × N (跨节点)              │
└───────────────────────────────────────┘
```

* **Nexus**：target，聚合 replicas，对外暴露块设备
* **Replica**：每个跨节点 pod，写一致（默认 synchronous，nexus 确认）
* **io_uring + SPDK**：用户态 IO 路径，**绕内核**

## 关键能力

* **Containerized**：每个 volume 一组 pod，跟 Longhorn 一样 K8s-native
* **Mayastor 高性能**：低延迟（io_uring）+ 高 IOPS（SPDK），对标本地 NVMe
* **快照 / 克隆**
* **备份**：内置 S3 备份（Mayastor CSI Snapshot + Velero）
* **自动发现**：cStor 自动发现裸盘 / 已有 LVM

## 部署

Helm：

```bash
helm repo add openebs https://openebs.github.io/charts
helm install openebs openebs/openebs --namespace openebs --create-namespace

# 或指定 Mayastor
helm install openebs openebs/openebs \
  --set mayastor.enabled=true \
  --set cstor.enabled=false
```

StorageClass（Mayastor）：

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: mayastor
provisioner: io.openebs.csi-mayastor
parameters:
  protocol: "nvmf"            # 或 "iscsi"
  repl: "3"
volumeBindingMode: WaitForFirstConsumer
```

## 优缺点

* ✅ **Mayastor 性能接近本地盘**（io_uring + SPDK）
* ✅ K8s 原生，运维友好
* ✅ 多引擎可选（cStor / Mayastor / Jiva）
* ✅ 主动开源，社区活跃（DataCore 接管后持续投入）
* ❌ Mayastor 比较新，生产案例相对少
* ❌ 集群必须满足节点要求：裸盘 + NVMe 驱动 + 较新内核
* ❌ cStor 性能比 Mayastor 差一截
* ❌ NFS / RWX 需配额外组件

## 适用场景

* **追求 K8s 原生 + 高性能**（Mayastor 跑 PostgreSQL / Redis / K8s 上的 DB）
* 数据库上 K8s 的项目
* 中小规模（<200 节点）
* 不方便自建 Ceph 但又嫌 Longhorn 慢

## 监控 / 排查

```bash
# 看 OpenEBS pods
kubectl -n openebs get pods

# Mayastor
kubectl -n mayastor get pods

# 资源池
kubectl get disks

# 监控
kubectl apply -f https://openebs.github.io/mayastor/docs/2.6.0/operations/monitoring/grafana/

# 性能查
kubectl exec -ti <mayastor-pod> -- mayastor client list
```

## 一句话

**K8s 原生 + Mayastor 用 io_uring/SPDK 高性能，对标本地 NVMe，中规模数据库上 K8s 首选**。