## 概念

Flannel 是 CoreOS（被 Red Hat 收购）2014 年起维护的 **最简单 CNI 插件**，专门做 **L3 overlay 网络**，不实现 NetworkPolicy（v0.10+ 也只是雏形，主流还是搭配 Calico policy）。

* 数据面：**vxlan / host-gw / udp / ipip** 四种 backend
* 控制面：etcd 存储 Pod CIDR 分配
* IPAM：内置，从 kube-flannel-cfg 读 Pod CIDR
* 规模：常用于 **小集群 / 开发环境 / 单 L2 数据中心**

## 架构

```
┌─── node1 ───┐         ┌─── node2 ───┐
│ cni0 (桥)    │         │ cni0 (桥)    │
│ flannel.1    │         │ flannel.1    │
│ (vxlan/hostgw│         │              │
└──────┬───────┘         └──────┬───────┘
       │ udp/vxlan             │
       └───────── 跨节点隧道 ───┘
       路由: 10.244.x.0/24 via 10.244.x.0 dev flannel.1
```

每个节点分到一段 `/24`（默认配置），flannel.1 是 VTEP（vxlan 时）或虚拟路由设备（host-gw 时）。

## Backend 选择

| Backend | 模式 | 性能 | 要求 |
| --- | --- | --- | --- |
| `host-gw` | 写 host 路由表 | 最高（无封装） | **节点必须在同 L2**，否则不通 |
| `vxlan` | VTEP 封装，UDP 4789 | 中（要加 50 字节头） | 跨 L3 也行，最常用 |
| `ipip` | IP-in-IP 封装 | 中 | 跨 L3，需要 inner ip 地址可路由 |
| `udp` | 用户态封装 | 最差 | 只剩 debug 用，生产禁用 |

## 部署

最简：

```bash
kubectl apply -f https://raw.githubusercontent.com/flannel-io/flannel/master/Documentation/kube-flannel.yml
```

或者 Helm：

```bash
helm repo add flannel https://flannel-io.github.io/flannel/
helm install flannel flannel/flannel
```

## 优劣

* ✅ **最简单**：单 DaemonSet + ConfigMap，10 分钟搭起来
* ✅ 资源占用极低，~50MB
* ✅ 跨 L3 可用（vxlan backend）
* ❌ **没 NetworkPolicy**，要 policy 得配 Calico policy-only
* ❌ 性能比 Calico eBPF / Cilium 差（vxlan 多了封装开销）
* ❌ 不支持 IPv6 单栈（仍以 IPv4 为主）
* ❌ 大集群（>500 节点）路由表项多，性能不如 BGP-based 方案

## 适用场景

* 开发 / 测试集群
* 小规模生产（<100 节点）
* 不想碰 NetworkPolicy 的极简场景
* 教学 / 学习 CNI 原理

## 监控 / 排查

```bash
# 看 flannel DaemonSet 状态
kubectl -n kube-flannel get ds

# 看 flannel.1 接口
ip -d link show flannel.1

# 看路由（vxlan/host-gw 不同）
ip route | grep flannel

# 抓包
tcpdump -i flannel.1 -n
```

## 一句话

**最简 CNI，没有 policy，性能中等，适合开发 / 小集群 / 不想碰安全的场景**。