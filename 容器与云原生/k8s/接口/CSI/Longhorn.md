## 概念

Longhorn 是 Rancher Labs（被 SUSE 收购）开发的 **K8s 原生分布式块存储**，2019 年 CNCF incubating。

* 设计：**每个 volume 是一个微服务**（replica 每个一个 pod），完全 K8s 化
* 数据面：**微服务 + iSCSI**（默认）/ NVMe-oF（实验）
* 复制：**默认 3 副本**，跨节点 / 跨 zone
* 部署：**一个 DaemonSet**，所有节点都跑 longhorn-engine

## 架构

```
┌────────────── K8s cluster ──────────────────┐
│                                             │
│  Longhorn Manager (Deployment ×3)            │
│   - 创建 / 删除 / 调度 volume                │
│   - 监控副本健康                             │
│                                             │
│  Longhorn Engine (DaemonSet, 每节点一个)       │
│   - 每个 replica 一个 longhorn engine 进程    │
│   - 通过 iSCSI 暴露块设备给 kubelet           │
│                                             │
│  Longhorn UI / CSI Driver (Deployment)        │
└──────────┬───────────────────────────────────┘
           ▼
  节点本地盘 / RAID0 / 整块裸盘
```

* **每个 volume** 在 K8s 里是一个 **PV + 多个 engine pod**（replica 数）
* 副本同步：write-back，先写主副本，异步同步到从副本
* 快照：CRUSH-style 的差分快照，存储在 Longhorn 自己盘上

## 关键能力

* **K8s 原生**：每个 volume 是 K8s 对象，kubectl 看得见
* **跨节点 / 跨 zone 副本**
* **增量快照 + 备份**：快照存 S3 / NFS / Azure Blob
* **在线扩容**：扩 PV 容量，Longhorn 自动扩底层文件系统
* **克隆**：从快照克隆 volume（秒级）
* **节点 / 盘故障自动恢复**
* **UI**：自带 web 控制台，可看所有 volume 状态
* **Backup**：定时备份到 S3（NFS 也行），跨集群恢复

## 部署

Helm：

```bash
helm repo add longhorn https://charts.longhorn.io
helm install longhorn longhorn/longhorn --namespace longhorn-system --create-namespace
```

StorageClass：

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: longhorn
provisioner: driver.longhorn.io
parameters:
  numberOfReplicas: "3"
  staleReplicaTimeout: "2880"   # 48 小时无心跳认为副本失效
volumeBindingMode: Immediate
```

## 优缺点

* ✅ **K8s 原生**：每个 volume 一组 pod，kubectl / prometheus / log 全可观测
* ✅ **部署简单**：一个 Helm 命令就能起
* ✅ 自带 UI
* ✅ 备份到 S3 简单
* ✅ 单 volume 性能不错（每副本一个引擎）
* ❌ 写延迟比物理盘高（多副本 + iSCSI）
* ❌ 默认 iSCSI 协议，需要节点支持（Linux 自带 iscsi-initiator-utils）
* ❌ 单个节点盘不能太多（每盘一个 longhorn engine）
* ❌ 不支持 RWX（除非用 Longhorn NFS，单独组件）
* ❌ 跨集群复制不原生

## 适用场景

* **K8s 上通用块存储**，**最常用替代 Rook / Ceph 之外的方案**
* 中小规模（<500 节点，<5PB）
* 不需要 RWX（除非用 NFS subdir）
* 想要 K8s 原生管理体验
* Rancher / SUSE 用户

## 监控 / 排查

```bash
# UI
kubectl -n longhorn-system port-forward svc/longhorn-frontend 8080:80

# CLI
kubectl -n longhorn-system exec -ti longhorn-manager-0 -- longhornctl

# 看 volume
kubectl get pv

# 看 engine
kubectl -n longhorn-system get pods -l app=longhorn-engine

# 关键 metrics
longhorn_volume_read_bytes_total
longhorn_volume_write_bytes_total
longhorn_volume_actual_size_bytes
```

## 一句话

**K8s 原生分布式块存储，部署最简单，体验最 K8s，中小规模首选**。