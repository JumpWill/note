## 概念

Calico 是 Tigera 公司主导的 CNI，**生产部署最广泛**（CNCF 毕业）。三大能力：

1. **L3 网络**：IPIP / VXLAN / 路由（无封装）
2. **NetworkPolicy**：K8s 原生 policy 的事实标准实现
3. **BGP**：跟 ToR / leaf-spine 路由器对接，把 Pod 路由广播到物理网络

数据面有三种实现：

* **iptables**（默认）：成熟，但规则多时性能下降
* **eBPF**（v3.13+）：替换 kube-proxy + iptables，性能更好
* **Windows HNS**：Windows 节点用

## 架构

```
┌─── node1 (bird/bgp) ───┐         ┌─── node2 (bird/bgp) ───┐
│ Felix                   │         │ Felix                   │
│  - 配置 veth / 路由      │         │                        │
│  - 配置 iptables / eBPF  │  BGP   │                        │
│                         │◀──────▶│                        │
│ typha (聚合 api server)  │         │                        │
└─────────────────────────┘         └────────────────────────┘
       ▲                                      ▲
       │                                      │
       └─── kube-apiserver (CRD: IPPool / BGPPeer / NetworkPolicy ...)
```

* **Felix**：每个节点的 agent，写路由 / iptables / eBPF
* **BIRD**：每个节点的 BGP 客户端，跟其他节点 / 物理路由器交换路由
* **Typha**：可选组件，聚合 apiserver 请求，缓解大规模集群性能

## 数据面模式

### IPIP（默认）

* `IPIP` 模式：跨子网时包封装在 IP 包里
* `IPIP cross-subnet`：只在跨子网时用 IPIP，同子网走 hostgw
* `Never`：完全不用 IPIP

### VXLAN

* 跟 Flannel 类似，UDP 4789 封装，**比 IPIP 多 8 字节**
* 在不能 IPIP 的环境（某些云）兜底用

### BGP（无封装）

* `BGP`：所有节点都跑 BGP，Pod 路由直接走 host 网络
* **性能最高**，但要求节点在同一 L2，或物理网络支持 BGP

### eBPF dataplane

* 装 `calico-cni` + `calico-kube-proxy`（v3.13+ 默认）
* 完全替代 kube-proxy 的 iptables / IPVS
* 性能比 iptables 高一个数量级（service 规则上万时尤其明显）

## NetworkPolicy

Calico 实现 K8s NetworkPolicy 全部 spec，扩展：

* **GlobalNetworkPolicy**：cluster-scoped
* **NetworkPolicy**：namespace-scoped
* **ApplicationLayer Policy**：L7 策略（基于 HTTP header）

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-frontend
spec:
  podSelector:
    matchLabels:
      app: backend
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: frontend
    ports:
    - protocol: TCP
      port: 8080
```

## BGP 模式（生产推荐）

大型集群让 Pod 路由直接进 ToR：

```yaml
# bgp-config
apiVersion: projectcalico.org/v3
kind: BGPConfiguration
metadata:
  name: default
spec:
  asNumber: 64512
  nodeToNodeMeshEnabled: true    # 节点全互联
  serviceClusterIPs:             # service IP 也广播
    - cidr: 10.96.0.0/12
```

## 部署

```bash
# 标准安装
kubectl apply -f https://raw.githubusercontent.com/projectcalico/calico/v3.27.0/manifests/calico.yaml

# Tigera Operator（推荐生产）
kubectl create -f https://raw.githubusercontent.com/tigera/operator/v1.32.0/manifests/tigera-operator.yaml
kubectl apply -f custom-resources.yaml
```

## 优劣

* ✅ **最成熟**：文档 / 案例 / 商业支持（Tigera Enterprise）最全
* ✅ **NetworkPolicy 完整**：K8s policy 的事实标准
* ✅ BGP 模式可对接物理网络，**大集群性能最好**
* ✅ eBPF data plane 替代 kube-proxy
* ❌ 配置复杂，BGP 学习曲线陡
* ❌ iptables 模式在大量 service 时性能差（一定要开 eBPF）
* ❌ VXLAN / IPIP 性能不如 Cilium 直接路由
* ❌ 监控数据相对少，没 Hubble 那种 service map

## 适用场景

* **生产首选**（特别是银行 / 运营商 / 政企）
* 大集群（>500 节点）有 BGP 网络
* 已经用了 K8s NetworkPolicy，必须严格隔离
* Tigera Enterprise 商业支持

## 监控 / 排查

```bash
# felix 状态
kubectl -n calico-system logs -l k8s-app=calico-kube-controllers

# 看 BGP peer
kubectl -n calico-system exec -ti calico-node-xxx -- calicoctl node status

# BGP 路由表
calicoctl ipam show
calicoctl bgp peer show

# 改用 eBPF
kubectl -n calico-system patch felixconfiguration default --type merge -p '{"spec":{"bpfEnabled":true}}'
```

## 一句话

**生产最常用，BGP / iptables / eBPF 三种数据面，NetworkPolicy 事实标准**。