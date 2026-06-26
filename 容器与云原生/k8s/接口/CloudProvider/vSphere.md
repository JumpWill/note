## 概念

vSphere Cloud Provider 是 K8s 在 **VMware vSphere**（私有云 / 传统虚拟化）上的集成。提供 VM 生命周期管理 + vSphere CSI（VMFS / vSAN / vVol）。

* 项目：
  * **cloud-provider-vsphere**：cloud-controller-manager 集成
  * **vSphere CSI Driver**：存储集成
* 适用：企业内私有云、传统 VMware 用户、vSAN 存储

## 集成的能力

| K8s 资源 | vSphere 资源 |
| --- | --- |
| Service type=LoadBalancer | **NSX-T / HAProxy（外部）** |
| Node lifecycle | VM lifecycle（**VM 创建 / 删除**） |
| PersistentVolume | **VMDK / vSAN / vVol** |
| StorageClass | 关联 datastore policy（vSAN 性能策略） |

## 两种部署模式

### 1. 外部 cloud-provider（cloud-controller-manager）

```bash
# 部署 cloud-controller-manager for vSphere
helm repo add vsphere-cpi https://kubernetes.github.io/cloud-provider-vsphere
helm install vsphere-cpi vsphere-cpi/vsphere-cpi \
  --set config.vcenter=<vcenter-host> \
  --set config.username=<user> \
  --set config.password=<pwd> \
  --set config.datacenter=<datacenter> \
  --set config.datastore=<datastore>
```

vSphere 7+ 用 govc / vCenter API 通信。

### 2. vSphere with Tanzu（TKGs）

VMware 自家产品，K8s 由 vCenter 直接创建，**K8s 跟 vSphere 完全集成**：
* Supervisor Cluster（命名空间级 K8s）
* Tanzu Kubernetes Grid Service（TKGs）
* vSphere Pod（用 vSphere 替代 container）

适合企业 VMware 现有用户，但**绑定 vSphere，迁移成本高**。

## vSphere CSI Driver

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: vsan
provisioner: csi.vsphere.vmware.com
parameters:
  storagepolicyname: "vSAN Default Storage Policy"
```

支持：

* **VMFS datastore**
* **vSAN**（分布式存储）
* **vVols**（Virtual Volumes，vSphere 6+）

## 优缺点

* ✅ 企业 VMware 现有环境零改造
* ✅ vSAN / vVols 性能稳定
* ✅ 跟 vCenter RBAC 集成
* ✅ Tanzu 提供完整 K8s-as-a-Service
* ❌ **绑定 VMware**，离开 vSphere 麻烦
* ❌ 配置复杂（vCenter 权限 / datastore / network）
* ❌ in-tree cloud-provider 1.28+ 已废弃，要迁 out-of-tree
* ❌ 跟云上 K8s 体验差距大（无 cloud LB / IAM）

## 适用场景

* **企业内 VMware 私有云**
* 已有 vCenter / vSAN 投资
* 严格内网 / 离线部署
* 银行 / 政府 / 制造业传统 IT

## 监控 / 排查

```bash
# vsphere-cpi 状态
kubectl -n vmware-system-cloud-provider get pods

# vSphere CSI
kubectl get csidriver
kubectl get csinode

# vCenter 侧
govc ls
govc vm.info <vm-name>

# 存储问题
kubectl describe pvc <pvc-name>
```

## 一句话

**vSphere / VMware 私有云 K8s 的标配，Tanzu 是上层封装**。