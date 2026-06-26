## 概念

Cilium 是 Isovalent（Cisco 子公司）开发的 eBPF-based CNI，**性能最强、可观测最好**。前身是公司同名开源项目，后成为 CNCF 毕业项目。

三大能力：

1. **CNI**：Pod 网络，IPv4 / IPv6 双栈
2. **kube-proxy replacement**：用 eBPF 替代 iptables / IPVS
3. **Hubble**：网络可观测（service map / flow log / DNS 观测）
4. **Tetragon**：runtime 安全（eBPF 内核拦截，可联动）
5. **服务网格**：基于 eBPF 的 L4/L7（Istio ambient 的底层）

## 架构

```
┌─── node1 ────────────────────────┐
│ cilium-agent (DaemonSet)         │
│  - eBPF programs:                │
│    bpf_netdev_eth0.c             │ ←  XDP / TC hook
│    bpf_lxc.c                     │ ←  pod-to-pod
│    bpf_overlay.c                 │ ←  跨节点 overlay
│    bpf_sock.c                    │ ←  socket-level (kube-proxy 替代)
│  - cilium-cli / hubble            │
└──────────────────────────────────┘
       ▲
       │ CRD: CiliumNetworkPolicy / CiliumClusterwideNetworkPolicy / ...
       │
   kube-apiserver
```

数据面走 **eBPF**，完全不走 iptables（除非 fallback）。

## 数据面模式

| 模式 | 封装 | 性能 | 要求 |
| --- | --- | --- | --- |
| `native-routing` | 无封装，直连路由 | 最高 | 节点在同一 L2 或可路由 |
| `overlay` (vxlan) | VTEP | 中 | 跨 L3 |
| `overlay` (geneve) | 更通用封装 | 中 | 同上 |

eBPF hooks：

* **XDP**：`BPF_PROG_TYPE_XDP`，最早到达
* **TC ingress / egress**：`BPF_PROG_TYPE_SCHED_CLS`
* **sock_ops / sk_msg**：socket 加速
* **connect / sendmsg**：用户态 socket hook，做 service 加速

## NetworkPolicy

支持 K8s 原生 + Cilium 扩展（L7）：

```yaml
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: l7-policy
spec:
  endpointSelector:
    matchLabels:
      app: api
  ingress:
  - fromEndpoints:
    - matchLabels:
        app: frontend
    toPorts:
    - ports:
      - port: "80"
        protocol: TCP
      rules:
        http:
        - method: "GET"
          path: "/api/v1/.*"
```

可以基于 **HTTP method / path / header** 做 L7 策略，这是 Calico 默认没有的能力。

## Hubble 可观测

Cilium 自带 Hubble：

```bash
# service map（拓扑图）
hubble ui

# 实时 flow
hubble observe -f --namespace default

# 看某 pod 的所有流量
hubble observe --from-pod default:foo-xxx --last 100
```

* L3/L4 流量全观测
* L7（HTTP / gRPC / Kafka / DNS）解析
* 配合 Grafana + Hubble UI 出 service map

## 部署

```bash
# cilium-cli（推荐）
cilium install --version 1.16.0 \
  --set kubeProxyReplacement=true \
  --set bpf.masquerade=true

# Helm
helm repo add cilium https://helm.cilium.io
helm install cilium cilium/cilium --version 1.16.0 \
  --namespace kube-system --create-namespace \
  --set kubeProxyReplacement=true
```

注意：**启用 kubeProxyReplacement=true** 后，集群里要删 kube-proxy。

## 与其他 CNI 区别

| 维度 | Cilium | Calico | Flannel |
| --- | --- | --- | --- |
| 数据面 | eBPF | iptables / eBPF / IPIP | vxlan / hostgw |
| kube-proxy 替换 | ✅ | ✅（eBPF 模式） | ❌ |
| L7 policy | ✅（CRD） | ✅（Calico Enterprise） | ❌ |
| 可观测 | Hubble（原生） | 较弱 | 弱 |
| Service map | ✅ | ❌ | ❌ |
| IPv6 | ✅ 原生 | ✅ | 部分 |
| 性能 | 最高 | 高 | 中 |

## 优劣

* ✅ **eBPF 性能最强**：大集群 service 上万时优势明显
* ✅ **L7 策略 + Hubble 可观测**，开箱即用
* ✅ 完全替代 kube-proxy，省一套组件
* ✅ Cilium Service Mesh：Istio ambient 底层，比 Envoy sidecar 性能好
* ❌ eBPF 内核版本要求高（4.19+ 起步，5.10+ 才有完整功能）
* ❌ BPF map 占用内存，大集群要算
* ❌ 调试复杂，eBPF 不易入门
* ❌ 跟某些 CNI / Multus 配合有边角案例

## 适用场景

* **追求性能 / 大规模集群**
* 需要 L7 policy / 可观测 / 服务网格（一体化方案）
* 能升级到新内核（5.10+）
* Kubernetes 1.24+

## 监控 / 排查

```bash
# agent 状态
cilium status

# connectivity test
cilium connectivity test

# 看 eBPF maps 占用
kubectl -n kube-system exec -ti cilium-xxx -- cilium bpf metrics

# Hubble 实时
hubble observe -t l7 -f
```

## 一句话

**eBPF-based、性能 / 可观测 / 安全一体化，CNI + kube-proxy 替代 + Hubble + 网格 一套全包**。