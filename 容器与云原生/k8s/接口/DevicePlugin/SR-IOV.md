## 概念

SR-IOV（Single Root I/O Virtualization）是 **网卡硬件虚拟化** 技术，让一块物理网卡（PF）虚拟成多个虚拟网卡（VF），每个 VF 有独立的 PCI 资源。在 K8s 上通过 SR-IOV CNI + Device Plugin 让 Pod 直通 VF，**接近物理性能**。

* 关键概念：
  * **PF（Physical Function）**：物理网卡
  * **VF（Virtual Function）**：虚拟出来的"假网卡"，每个有独立 PCI 地址
  * **PF driver**：host 端，配置 PF
  * **VF driver**：guest 端（容器里），VF 看起来是独立 NIC

## 架构

```
┌──────── 物理网卡（如 Mellanox CX5）────────┐
│  PF (host driver)                         │
│   ├─ VF0 ──┐                              │
│   ├─ VF1 ──┤                              │
│   ├─ VF2 ──┼─ PCI passthrough / VFIO      │
│   └─ VF3 ──┘                              │
└───────────────────────────────────────────┘
       ↓ sriov-device-plugin
   kubelet 注册 intel.com/sriov_net_A / etc
       ↓ sriov-cni
   Pod 拿到 VF，挂在容器里直接用
```

* **sriov-device-plugin**（DaemonSet）：注册 VF 资源
* **sriov-cni**（CNI 插件）：把 VF 挂到 Pod 网络命名空间
* **multus-cni**：SRIOV 通常跟 Multus 配合，主 CNI + SRIOV 多网卡

## 部署

```bash
# 1. 启用 Intel/Mellanox 网卡的 SR-IOV
# 例: Intel X710
echo 8 > /sys/class/net/ens4f0/device/sriov_totalvfs
ip link set ens4f0 vf 0 mac aa:bb:cc:dd:ee:ff

# 2. 装 SR-IOV Network Device Plugin
kubectl apply -f https://raw.githubusercontent.com/k8snetworkplumbingwg/sriov-network-device-plugin/master/deployments/static-daemonset/manifests/sriovdp-ds.yaml

# 3. ConfigMap 配置（指定 PF / 资源名）
```

ConfigMap：

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: sriovdp-config
  namespace: kube-system
data:
  config.json: |
    {
      "resourceList": [{
        "resourceName": "intel_sriov_net_A",
        "selectors": {
          "vendors": ["8086"],
          "devices": ["1572"],
          "pfNames": ["ens4f0#0-7"]
        }
      }]
    }
```

Pod 用：

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: net-perf-pod
  annotations:
    k8s.v1.cni.cncf.io/networks: '[{"name": "sriov-net", "interface": "net1"}]'
spec:
  containers:
  - name: app
    resources:
      limits:
        intel.com/sriov_net_A: 1   # 用 1 个 VF
```

## 优缺点

* ✅ **性能接近裸机**（直通硬件，延迟 ~μs 级）
* ✅ 硬件隔离（VF 之间不互相影响）
* ✅ RDMA / DPDK / 高速包处理场景必备
* ❌ **需要硬件支持**（网卡 + BIOS）
* ❌ 需要 VF 数量足够，且要预先 enable
* ❌ 跟 NetworkPolicy 配合差（CNI 看不到 SRIOV 流量）
* ❌ VM 中需要 IOMMU + VT-d（云上多数不开）
* ❌ 配置复杂（PF / VF / CNI / Multus 一路配齐）

## 适用场景

* **NFV（vCPE / vBRAS）**：运营商虚拟化
* **高频交易**：低延迟网络
* **DPDK / 用户态协议栈**
* **RDMA**（如 Mellanox 的 RoCE）

## 适用环境

* 裸金属 + 支持 SR-IOV 的网卡（Mellanox ConnectX-5/6、Intel X710/XL710 等）
* BIOS 开启 VT-d / IOMMU
* 云上多数不开 nested virtualization，**要先确认**

## 监控 / 排查

```bash
# 看 VF 数
cat /sys/class/net/ens4f0/device/sriov_totalvfs
ip link show ens4f0

# 看 VF 分配
ip link show ens4f0 | grep vf

# 节点资源
kubectl describe node <node> | grep intel.com

# 性能测试（iperf3 / dpdk-pktgen）
```

## 一句话

**网卡硬件直通，NFV / 高频交易 / DPDK 必备，云上受限**。