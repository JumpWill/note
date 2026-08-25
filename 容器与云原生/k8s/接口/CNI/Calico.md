# Calico

## 一、概述

**Calico** 是 Tigera 公司主导的 CNI 插件，是 K8s 生态中**生产部署最广泛**的方案（CNCF 毕业项目）。

**核心定位**：

- 数据面：**IPIP / VXLAN / 无封装（BGP 路由）**
- 控制面：**BGP**（物理网络友好）+ **etcd**（可选）
- NetworkPolicy：**K8s 事实标准**
- IPAM：内置，支持多种 IP 池
- 规模：**生产验证最大集群**

**特点速记**：

- ✅ L3 网络，性能最优（无封装）
- ✅ NetworkPolicy 完整且是事实标准
- ✅ BGP 可对接物理网络
- ✅ 大规模集群验证（5000+ 节点）
- ✅ 多种数据面灵活切换
- ❌ 无 L7 策略（需 Cilium）
- ❌ 无内置服务网格

---

## 二、整体架构

```text
┌─────────────────────────────────────────────────────────────┐
│                   Calico 整体架构                              │
│                                                              │
│  ┌─────────────────────┐      ┌─────────────────────────┐ │
│  │  Master 节点         │      │  Worker 节点            │ │
│  │                     │      │                         │ │
│  │ ┌─────────────────┐ │      │ ┌─────────────────┐  │ │
│  │ │ kube-apiserver   │ │      │ │ kubelet          │  │ │
│  │ └─────────────────┘ │      │ └─────────────────┘  │ │
│  │         │              │      │         │             │ │
│  │ ┌──────▼──────┐       │      │ ┌───────▼──────┐    │ │
│  │ │ typha (可选) │◄──────┼──────┤ │ calico-node  │    │ │
│  │ │ (集群扩展)  │       │      │ │               │    │ │
│  │ └──────────────┘       │      │ ├───────────────┤    │ │
│  │                        │      │ │ Felix (策略) │    │ │
│  │ ┌──────▼──────┐       │      │ │ BIRD (BGP)    │    │ │
│  │ │ datastore   │       │      │ └───────┬───────┘    │ │
│  │ │ (etcd/k8s)  │◄──────┼──────┤         │             │ │
│  │ └──────────────┘       │      │ ┌───────▼──────┐    │ │
│  └────────────────────────┘      │ │  cbr0/cali... │    │ │
│                                  │ │  Pod 网桥     │    │ │
│                                  │ └──────────────┘    │ │
│                                  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘

架构组件：
  1. calico-node：每节点运行的 Pod（DaemonSet）
     - Felix：策略执行（iptables/eBPF）
     - BIRD：BGP 路由协议
     - confd：配置同步

  2. typha（可选）：集群扩展
     - 减轻 datastore 压力
     - 大集群使用

  3. datastore：配置存储
     - Kubernetes API（推荐）
     - 或独立的 etcd

  4. Pod 网络接口
     - caliXXXX：每个 Pod 的 veth 一端
     - cbr0：节点网桥
```

### Calico 与 K8s API 集成

```text
Calico 数据存储两种模式：

  1. K8s API datastore（推荐，3.0+）
     - Calico CRD 存储配置
     - 无需独立 etcd
     - 与 K8s 集成度高

     CRD 资源：
       - BGPConfiguration
       - BGPPeer
       - FelixConfiguration
       - GlobalNetworkPolicy
       - NetworkPolicy
       - IPPool

  2. etcd datastore（传统）
     - 独立 etcd 集群
     - 性能更好
     - 运维复杂

  推荐：
    现代集群 → K8s API datastore
    大型集群 → etcd + typha
```

---

## 三、数据面工作原理

### 3.0 Overlay vs Underlay 基础概念

```text
Overlay vs Underlay 网络对比：

  ┌─────────────────────────────────────────────────────────────┐
  │                    Overlay（覆盖网络）                          │
  │                                                              │
  │  特点：                                                      │
  │  - 在现有网络之上构建虚拟网络                                │
  │  - 原始数据包被封装（VXLAN/IPIP/Geneve）                      │
  │  - 对底层网络（Underlay）透明                              │
  │  - 跨子网、跨数据中心无需底层配合                          │
  │                                                              │
  │  ┌─────────────────┐    封装     ┌─────────────────┐         │
  │  │  Pod A           │ ───────→ │  Pod B           │         │
  │  │  10.244.1.5      │  UDP     │  10.244.2.8      │         │
  │  └─────────────────┘  4789   └─────────────────┘         │
  │         ↑                       ↑                         │
  │         │ Underlay 网络          │                         │
  │         │ 192.168.1.0/24         │                         │
  │                                                              │
  │  代表：VXLAN、IPIP、Geneve、Flannel                         │
  └─────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────┐
  │                    Underlay（底层网络）                        │
  │                                                              │
  │  特点：                                                      │
  │  - 直接使用物理网络路由                                        │
  │  - 不封装，开销最小                                            │
  │  - 性能最高（接近裸机）                                    │
  │  - 需要底层网络可达（L2 或 L3 路由）                      │
  │                                                              │
  │  ┌─────────────────┐    直接路由 ┌─────────────────┐       │
  │  │  Pod A           │ ───────→ │  Pod B           │       │
  │  │  10.244.1.5      │   BGP   │  10.244.2.8      │       │
  │  └─────────────────┘          └─────────────────┘       │
  │         ↑                       ↑                         │
  │         │ 物理交换机 BGP        │                         │
  │                                                              │
  │  代表：BGP 路由、原生路由                                     │
  └─────────────────────────────────────────────────────────────┘
```

### 3.0.1 Calico 的三种数据面对比

```text
Calico 支持三种数据面，本质是 Overlay 与 Underlay 的混合：

  ┌─────────────────────────────────────────────────────────────────┐
  │  Calico 数据面选择                                              │
  │                                                                 │
  │  1. 无封装（Default + CrossSubnet 模式）                       │
  │     - Underlay 直连路由                                        │
  │     - 性能最佳（无额外包头）                                  │
  │     - 要求：所有节点 L3 可达（同一 AS 内）                    │
  │     - 适合：裸金属 / 同一机房 / 私有云                        │
  │                                                                 │
  │  2. VXLAN（Overlay 模式）                                      │
  │     - UDP 4789 封装 VXLAN 头                                  │
  │     - 跨 L3 网络透明                                           │
  │     - 性能损失：~50 字节 + 一次 MTU 检查                     │
  │     - 适合：云环境 / 跨子网                                   │
  │                                                                 │
  │  3. IPIP（Overlay 模式，轻量）                                 │
  │     - IP-in-IP 封装（仅 20 字节）                            │
  │     - 性能介于无封装和 VXLAN 之间                              │
  │     - 适合：跨子网，但不需要 VXLAN 完整特性                    │
  └─────────────────────────────────────────────────────────────────┘
```

### 3.0.2 Overlay 模式详解（VXLAN/IPIP）

```text
Overlay 网络完整路径：

  Node 1 (10.0.0.10)                          Node 2 (10.0.0.20)
  ┌────────────────────────┐                ┌────────────────────────┐
  │  Pod A 10.244.1.5       │                │  Pod B 10.244.2.8       │
  │  ┌──────────────────┐  │                │  ┌──────────────────┐  │
  │  │  app 进程         │  │                │  │  app 进程         │  │
  │  └────────┬─────────┘  │                │  └────────┬─────────┘  │
  │  ┌────────▼─────────┐  │                │  ┌────────▼─────────┐  │
  │  │ eth0 @ Pod netns │  │                │  │ eth0 @ Pod netns │  │
  │  └────────┬─────────┘  │                │  └────────┬─────────┘  │
  │  ┌────────▼─────────┐  │                │  ┌────────▼─────────┐  │
  │  │ lxcXXXX (veth)  │  │                │  │ lxcXXXX (veth)  │  │
  │  └────────┬─────────┘  │                │  └────────┬─────────┘  │
  └─────────┼─────────────┘                └─────────┼─────────────┘
            │                                          │
  ┌─────────▼─────────────┐                ┌─────────▼─────────────┐
  │ Node 1 netns          │                │ Node 2 netns          │
  │ ┌──────────────────┐  │                │ ┌──────────────────┐  │
  │ │ cbr0 桥          │  │                │ │ cbr0 桥          │  │
  │ └────────┬─────────┘  │                │ └────────┬─────────┘  │
  │ ┌────────▼─────────┐  │                │ ┌────────▼─────────┐  │
  │ │ caliXXXX (主机) │  │                │ │ caliXXXX (主机) │  │
  │ └────────┬─────────┘  │                │ └────────┬─────────┘  │
  │ ┌────────▼─────────┐  │                │ ┌────────▼─────────┐  │
  │ │ eth0 (物理网卡) │  │                │ │ eth0 (物理网卡) │  │
  │ └────────┬─────────┘  │                │ └────────┬─────────┘  │
  └─────────┼─────────────┘                └─────────┼─────────────┘
            │                                          │
  ═══════════╪═══════════ Underlay 物理网络 ═════════╪══════════
            │                                          │
            └──────────┬───────────────────────────────┘
                            │
                      物理交换机/路由器
                     BGP / OSPF / Static

Overlay 模式特征：
  1. Pod 发包 → 主机 caliXXXX → cbr0
  2. 主机根据路由表判断目的 Pod 在另一节点
  3. 主机根据 encapsulation 选择 VXLAN/IPIP/Geneve
  4. 封装原始包（添加隧道头）
  5. 通过物理网络发送到目的节点
  6. 目的节点解封装
  7. 转发到目的 Pod
```

### 3.0.3 Underlay 模式详解（无封装）

```text
Underlay 网络完整路径：

  Node 1 (10.0.0.10)                          Node 2 (10.0.0.20)
  ┌────────────────────────┐                ┌────────────────────────┐
  │  Pod A 10.244.1.5       │                │  Pod B 10.244.2.8       │
  │  ┌──────────────────┐  │                │  ┌──────────────────┐  │
  │  │  app 进程         │  │                │  │  app 进程         │  │
  │  └────────┬─────────┘  │                │  └────────┬─────────┘  │
  │  ┌────────▼─────────┐  │                │  ┌────────▼─────────┘  │
  │  │ eth0 @ Pod netns │  │                │  │ eth0 @ Pod netns │  │
  │  └────────┬─────────┘  │                │  └────────┬─────────┘  │
  │  ┌────────▼─────────┐  │                │  ┌────────▼─────────┐  │
  │  │ lxcXXXX (veth)  │  │                │  │ lxcXXXX (veth)  │  │
  │  └────────┬─────────┘  │                │  └────────┬─────────┘  │
  └─────────┼─────────────┘                └─────────┼─────────────┘
            │                                          │
  ┌─────────▼─────────────┐                ┌─────────▼─────────────┐
  │ Node 1 netns          │                │ Node 2 netns          │
  │ ┌──────────────────┐  │                │ ┌──────────────────┐  │
  │ │ cbr0 桥          │  │                │ │ cbr0 桥          │  │
  │ └────────┬─────────┘  │                │ └────────┬─────────┘  │
  │ ┌────────▼─────────┐  │    直连路由      │ ┌────────▼─────────┐  │
  │ │ caliXXXX (主机) │  │ ──────────────► │ │ caliXXXX (主机) │  │
  │ └────────┬─────────┘  │                │ └────────┬─────────┘  │
  │ ┌────────▼─────────┐  │                │ ┌────────▼─────────┐  │
  │ │ eth0 (物理网卡) │  │                │ │ eth0 (物理网卡) │  │
  │ └────────┬─────────┘  │                │ └────────┬─────────┘  │
  └─────────┼─────────────┘                └─────────┼─────────────┘
            │                                          │
  ═══════════╪═══════════ Underlay 物理网络 ═════════╪══════════
            │            （BGP 已学习路由）             │
            │                                          │
            └────────────────┬─────────────────────────┘
                             │
                       物理交换机/路由器
                       BGP / OSPF / Static

Underlay 模式特征：
  1. Pod 发包 → 主机 caliXXXX → cbr0
  2. 主机根据路由表判断目的 Pod 在另一节点
  3. 主机直接转发（无封装）
  4. 目的节点直接接收
  5. 转发到目的 Pod

核心差异：
  - Overlay：每包额外封装（50-100 字节）
  - Underlay：0 额外开销，仅 IP 路由
```

### 3.1 无封装（路由模式 / BGP）

```text
Pod A 在 Node 1 (10.0.0.10)   Pod B 在 Node 2 (10.0.0.20)
IP: 10.244.1.5                 IP: 10.244.2.8

Pod A 发包到 Pod B（无封装）：

  Pod A (10.244.1.5)
      │ eth0
      ▼
  veth pair 一端
      │
      ▼ 宿主机网络命名空间
  cbr0 网桥
      │
      ▼ 查路由表
      │
  路由表（BIRD 注入）：
    10.244.2.0/24 via 10.0.0.20 dev eth0
    10.244.1.0/24 dev cbr0
    default via 网关 dev eth0
      │
      ▼ 直接转发
  Node 1 eth0 (10.0.0.10)
      │
      ▼
  物理网络（L3）
      │
      ▼ BGP 路由可达
  Node 2 eth0 (10.0.0.20)
      │
      ▼ 查路由表
      │
  路由表：
    10.244.2.0/24 dev cbr0
      │
      ▼
  cbr0 网桥
      │
      ▼
  Pod B (10.244.2.8)

优势：
  - 零封装开销，延迟最低（30-50μs）
  - 与传统物理网络无缝集成
  - 性能接近裸机

要求：
  - 所有节点 L3 可达（BGP 自动学习路由）
  - 或所有节点在同一 L2
```

### 3.2 IPIP 模式（IP-in-IP 封装）

#### 3.2.1 IPIP 协议原理

```text
IPIP（IP Encapsulation within IP）：

  IPIP 协议定义（RFC 2003）：
    - 将一个完整的 IP 包作为 payload
    - 添加新的外层 IP 头
    - 协议号：4（IPv4 中）

  ┌────────────────────────────────────────┐
  │  外层 IP 头（20 字节）              │  ← 新增
  │  - 协议号 = 4（IPIP）              │
  │  - 源 IP：Node 1 外网 IP          │
  │  - 目的 IP：Node 2 外网 IP        │
  │  - TTL = 原始 TTL - 1             │
  ├────────────────────────────────────────┤
  │  内层 IP 头（20 字节）              │  ← 原始包
  │  - 协议号 = TCP（6）              │
  │  - 源 IP：Pod A IP                │
  │  - 目的 IP：Pod B IP              │
  │  - TTL = 原始                     │
  ├────────────────────────────────────────┤
  │  TCP 头（20 字节）                  │
  ├────────────────────────────────────────┤
  │  Payload                              │
  └────────────────────────────────────────┘

  总开销：仅 20 字节（外层 IP 头）
  特点：
    - 不使用 UDP 端口
    - 内层 IP 包作为外层 payload
    - 路由器只需检查外层 IP
```

#### 3.2.2 Calico IPIP 完整数据流

```text
Pod A → 目标 IP 在另一节点 → IPIP 封装 → 物理网络 → 解封装 → Pod B

  Node 1 (10.0.0.10)                          Node 2 (10.0.0.20)
  ┌─────────────────────┐                ┌─────────────────────┐
  │ Pod A 10.244.1.5      │                │ Pod B 10.244.2.8      │
  │ ┌────────────────┐   │                │ ┌────────────────┐   │
  │ │ eth0           │   │                │ │ eth0           │   │
  │ └────────────────┘   │                │ └────────────────┘   │
  └─────────────────────┘                └─────────────────────┘
           │ 发包                              │
           ▼                                    ▲
  ┌────────────────────────┐                ┌────────────────────────┐
  │ cbr0 → vethXXXX         │                │ cbr0 → vethXXXX         │
  └────────────────────────┘                └────────────────────────┘
           │                                    ▲
           ▼                                    │
  ┌────────────────────────────────────────┐    │
  │ Felix 添加 IPIP 头：                    │    │
  │   原始包：[10.244.1.5 → 10.244.2.8] │    │
  │   ↓ IPIP 封装                          │    │
  │   [10.0.0.10 → 10.0.0.20]              │    │
  │   [10.244.1.5 → 10.244.2.8]           │    │
  │   协议号 4                              │    │
  └────────────────────────────────────────┘    │
           │                                    │
           ▼                                    │
  ┌────────────────────────────────────────┐    │
  │ Node 1 eth0 (10.0.0.10)                │    │
  └────────────────────────────────────────┘    │
           │                                    │
           └──────────── IPIP 隧道 ────────────┘
                                            │
                                            ▼
                          ┌────────────────────────────────┐
                          │ Node 2 eth0 (10.0.0.20)         │
                          └────────────────────────────────┘
                                            │
                                            ▼
                          ┌────────────────────────────────┐
                          │ Felix 识别 IPIP 包            │
                          │ - 协议号 = 4                   │
                          │ - 解封装                       │
                          │ - 提取内层包：[10.244.1.5 → 10.244.2.8] │
                          └────────────────────────────────┘
                                            │
                                            ▼
                          ┌────────────────────────────────┐
                          │ 内层包转发到 Pod B            │
                          └────────────────────────────────┘
```

#### 3.2.3 IPIP 模式适用场景

```text
适合 IPIP 的场景：
  ✓ 跨子网通信（如 10.0.0.0/24 与 10.1.0.0/24）
  ✓ 不需要 BGP 协议的环境
  ✓ 对性能要求中等（封装开销可接受）
  ✓ 简单 Overlay 需求

不适合 IPIP 的场景：
  ✗ 同一 L2 子网内通信（用无封装更优）
  ✗ 需要加密（IPIP 不支持）
  ✗ 大规模数据中心（VXLAN 更合适）
  ✗ 跨数据中心（需要更复杂方案）

IPIP 性能损耗：
  - 每个包额外 20 字节
  - 增加 ~10μs 延迟
  - 内核额外处理外层 IP 头
  - MTU 需要减少 20 字节
```

### 3.3 VXLAN 模式

#### 3.3.1 VXLAN 协议原理

```text
VXLAN（Virtual Extensible LAN）：

  VXLAN 协议定义（RFC 7348）：
    - 将完整的 L2 帧封装到 UDP 包中
    - 使用 UDP 端口 4789（IANA 分配）
    - 24 位 VNI（VXLAN Network Identifier）
    - 支持 1600 万个逻辑网络

  ┌────────────────────────────────────────┐
  │  外层 Ethernet 头（14 字节）        │
  ├────────────────────────────────────────┤
  │  外层 IP 头（20 字节）              │
  │  - 协议号 = 17（UDP）              │
  │  - 源 IP：Node 1 外网 IP          │
  │  - 目的 IP：Node 2 外网 IP        │
  ├────────────────────────────────────────┤
  │  UDP 头（8 字节）                    │
  │  - 源端口：随机                     │
  │  - 目的端口：4789（VXLAN 标准）     │
  ├────────────────────────────────────────┤
  │  VXLAN 头（8 字节）                  │
  │  - Flags：I 标志位（1 比特）       │
  │  - Reserved：30 比特               │
  │  - VNI：24 比特                     │
  │  - Reserved：16 比特               │
  ├────────────────────────────────────────┤
  │  内层 Ethernet 头（14 字节）        │
  ├────────────────────────────────────────┤
  │  内层 IP 头（20 字节）              │
  ├────────────────────────────────────────┤
  │  TCP/UDP 头                          │
  ├────────────────────────────────────────┤
  │  Payload                              │
  └────────────────────────────────────────┘

  总开销：约 50 字节（UDP + VXLAN）
  支持 VNI 数：约 1600 万
  端口：UDP 4789（标准 IANA 分配）
```

#### 3.3.2 Calico VXLAN 完整数据流

```text
Pod A → VXLAN 封装 → UDP 4789 → 物理网络 → 解封装 → Pod B

  Node 1 (10.0.0.10)                          Node 2 (10.0.0.20)
  ┌─────────────────────┐                ┌─────────────────────┐
  │ Pod A 10.244.1.5      │                │ Pod B 10.244.2.8      │
  │ ┌────────────────┐   │                │ ┌────────────────┐   │
  │ │ eth0           │   │                │ │ eth0           │   │
  │ └────────────────┘   │                │ └────────────────┘   │
  └─────────────────────┘                └─────────────────────┘
           │ 发包                              ▲
           ▼                                    │
  ┌──────────────────────────────────────┐    │
  │ Felix 添加 VXLAN 头：                  │    │
  │   原始包：[Eth][IP][TCP]              │    │
  │   ↓ VXLAN 封装                         │    │
  │   [Eth]                                │    │
  │   [IP: 10.0.0.10 → 10.0.0.20]          │    │
  │   [UDP: src=xxx, dst=4789]              │    │
  │   [VXLAN: VNI=1]                       │    │
  │   [Eth]                                │    │
  │   [IP: 10.244.1.5 → 10.244.2.8]        │    │
  │   [TCP]                                │    │
  └──────────────────────────────────────┘    │
           │                                    │
           ▼                                    │
  ┌──────────────────────────────────────┐    │
  │ Node 1 eth0 (10.0.0.10)              │    │
  └──────────────────────────────────────┘    │
           │                                    │
           └──────────── UDP 4789 ────────────┘
                                            │
                                            ▼
                          ┌────────────────────────────────┐
                          │ Node 2 eth0 (10.0.0.20)         │
                          └────────────────────────────────┘
                                            │
                                            ▼
                          ┌────────────────────────────────┐
                          │ 监听 UDP 4789                   │
                          │ - 识别 VXLAN 头                │
                          │ - 解封装                       │
                          │ - 提取内层包                   │
                          └────────────────────────────────┘
                                            │
                                            ▼
                          ┌────────────────────────────────┐
                          │ 内层包转发到 Pod B            │
                          └────────────────────────────────┘
```

#### 3.3.3 Calico VXLAN 配置选项

```yaml
# Calico VXLAN 完整配置
apiVersion: operator.tigera.io/v1
kind: Installation
metadata:
  name: default
spec:
  calicoNetwork:
    encapsulation: VXLAN  # 使用 VXLAN
    mtu: 1450              # 调整 MTU 避免分片
    # VXLAN 默认端口
    # VXLANPort: 4789
  # 可选：自定义 VNI
  # vxlanVNI: 4096
```

#### 3.3.4 VXLAN 模式适用场景

```text
适合 VXLAN 的场景：
  ✓ 云环境（AWS、Azure、GCP）
  ✓ 大规模数据中心
  ✓ 跨子网通信
  ✓ 需要高 VNI 数量（多租户）
  ✓ 不需要极致性能

不适合 VXLAN 的场景：
  ✗ 同一 L2 子网（用无封装）
  ✗ 性能极致要求（VXLAN 慢 ~20μs）
  ✗ 老内核（< 3.7 不支持 VXLAN）

VXLAN vs IPIP 对比：
  ┌────────────────┬──────────────┬──────────────┐
  │  特性          │  IPIP          │  VXLAN        │
  ├────────────────┼──────────────┼──────────────┤
  │  封装开销      │  20 字节       │  50 字节       │
  │  协议          │  协议号 4      │  UDP 4789      │
  │  嵌套层        │  L3 only       │  L2 over L3    │
  │  VNI 支持      │  无            │  24 位 VNI     │
  │  MTU 影响      │  -20 字节      │  -50 字节      │
  │  性能开销      │  ~10μs        │  ~20μs        │
  │  成熟度        │  高（老）      │  高（新）      │
  │  典型场景      │  简单跨子网    │  云/大规模     │
  └────────────────┴──────────────┴──────────────┘
```

### 3.4 BGP 路由详解

```text
BGP（Border Gateway Protocol）在 Calico 中的作用：

  ┌─────────────────────────────────────────────────────────────┐
  │  BGP 在 Calico 中的角色                                       │
  │                                                              │
  │  1. Pod CIDR 通告                                            │
  │     - 每个节点通告自己负责的 Pod CIDR                       │
  │     - 其他节点学习这些路由                                  │
  │     - 自动建立 Pod-to-Pod 路由                              │
  │                                                              │
  │  2. AS 号模型                                                │
  │     - 每个 Calico 集群一个 AS 号（如 64512）                │
  │     - 节点之间 iBGP（Internal BGP）                         │
  │     - 与物理网络 eBGP（External BGP）                       │
  │                                                              │
  │  3. 路由反射器（RR）                                        │
  │     - 大集群（> 100 节点）使用 RR                          │
  │     - 避免全网状 BGP 连接（n*(n-1)/2）                     │
  │     - RR 之间全网状，RR 与客户端星形                         │
  └─────────────────────────────────────────────────────────────┘

BGP 完整路由学习过程：

  启动阶段：
    1. 节点 1（AS 64512）启动
       - 创建 BGP peer 与其他节点
       - 通告 10.244.1.0/24（自己的 Pod CIDR）
       - 接收其他节点的 Pod CIDR 通告

    2. 节点 2（AS 64512）启动
       - 同上

  稳定阶段：
    1. Pod A 部署到节点 1（10.244.1.5）
    2. 节点 1 通过 BGP 通告路由：
       10.244.1.5/32 via 10.0.0.10 dev eth0
    3. 其他节点通过 BGP 学习此路由
    4. 节点 2 添加路由表项：
       10.244.1.5 via 10.0.0.10 dev eth0
    5. Pod B（10.244.2.8）发包到 Pod A
       → 节点 2 直接转发到节点 1（无封装）

  失败恢复：
    1. 节点 1 宕机
    2. BIRD 连接超时（默认 90s）
    3. 其他节点移除路由
    4. Pod A 重新调度到其他节点
    5. 新节点通告新路由
```

#### 3.4.1 BGP 配置详解

```yaml
# 1. 节点 AS 配置
apiVersion: crd.projectcalico.org/v1
kind: BGPConfiguration
metadata:
  name: default
spec:
  asNumber: 64512                    # 节点 AS 号
  logLevelScreen: Info
  nodeToNodeMeshEnabled: true        # 节点间全网状（默认）

# 2. 与物理网络路由器建立 peer
apiVersion: crd.projectcalico.org/v1
kind: BGPPeer
metadata:
  name: spine1
spec:
  peerIP: 10.0.0.1                    # 物理路由器 IP
  asNumber: 65001                    # 物理路由器 AS
  password: secret                    # TCP MD5 认证（可选）
  keepOriginalNextHop: true           # 保留原始下一跳（重要）

# 3. BGP Filter（控制通告哪些路由）
apiVersion: crd.projectcalico.org/v1
kind: BGPFilter
metadata:
  name: only-pod-cidr
spec:
  order: 10
  action: Accept
  nodeSelector: all()
  match:
    prefix:
      cidr: 10.244.0.0/16            # 仅通告 Pod CIDR

# 4. IP Pool 配置（指定通告哪些 CIDR）
apiVersion: crd.projectcalico.org/v1
kind: IPPool
metadata:
  name: default-pool
spec:
  cidr: 10.244.0.0/16
  blockSize: 26                       # 每个节点 /26 = 64 IP
  encapsulation: None                  # Underlay + BGP
```

#### 3.4.2 BGP 路由反射器（RR）

```text
大集群 BGP 部署：

  小集群（< 50 节点）：
    节点 1 ←─iBGP─→ 节点 2 ←─iBGP─→ 节点 3
        ↓               ↓               ↓
    Full Mesh: n*(n-1)/2 连接
    50 节点 = 1225 个 BGP 连接（OK）

  大集群（> 100 节点）：
    Full Mesh 不可行
    100 节点 = 4950 个 BGP 连接
    500 节点 = 124750 个 BGP 连接（崩溃）

  使用 Route Reflector：
    ┌─────────────────────┐
    │     RR-1              │ ◄── iBGP ──► RR-2
    │   (AS 64512)         │
    └──────────┬──────────┘
               │
       ┌───────┼────────┐
       │       │        │
      客户端客户端  客户端

    RR 之间 Full Mesh
    RR 与客户端 IBGP client
    路由规则：RR 只发送最优路由
```

### 3.4 三种数据面对比

```text
  ┌──────────┬──────────────┬──────────────┬──────────────┐
  │ 数据面   │ 性能         │ 适用场景      │ 配置复杂度    │
  ├──────────┼──────────────┼──────────────┼──────────────┤
  │ 无封装   │ ~30-50μs    │ 同子网 + BGP │ 中（需BGP）  │
  │ IPIP     │ ~50-80μs    │ 跨子网       │ 低          │
  │ VXLAN    │ ~60-100μs   │ 云环境       │ 低          │
  └──────────┴──────────────┴──────────────┴──────────────┘

  性能排序：无封装 > IPIP > VXLAN
  跨子网：IPIP = VXLAN > 无封装（需BGP）
```

---

## 四、控制面（BGP 与 K8s API）

### 4.1 BGP 路由协议

```text
BGP（Border Gateway Protocol）工作原理：

  Node 1 (10.0.0.10)                Node 2 (10.0.0.20)
  ┌─────────────────┐              ┌─────────────────┐
  │ BIRD            │              │ BIRD            │
  │ AS 64512        │◄───BGP──────►│ AS 64513        │
  │                 │   TCP 179     │                 │
  └────────┬────────┘              └────────┬────────┘
           │                                 │
           │ 通告：                           │ 通告：
           │ 10.244.1.0/24              │ 10.244.2.0/24
           │                                 │

  Calico BGP 模式：
    1. Node-to-Node BGP（默认）
       - 每节点通告自己的 Pod CIDR
       - 全网状 BGP（Full Mesh）
       - 适合 < 100 节点

    2. BGP Route Reflector（大规模）
       - 选 3 个 RR 节点
       - 其他节点只与 RR 建立 BGP
       - 适合 > 100 节点

    3. 与物理网络 BGP 对接
       - Calico AS 与 ToR 路由器 AS 建立 iBGP
       - Pod CIDR 通告到物理网络
       - 物理路由器直接转发到 K8s 节点
       - 性能最优（无隧道）
```

### 4.2 Calico CRD（K8s API 模式）

```yaml
# IPPool：IP 地址池
apiVersion: crd.projectcalico.org/v1
kind: IPPool
metadata:
  name: default-pool
spec:
  cidr: 10.244.0.0/16
  ipipMode: Always              # 跨子网用 IPIP
  vxlanMode: Never
  natOutgoing: true             # 出网 SNAT
  blockSize: 26                  # 每个节点 /26 = 64 IP

---
# BGPConfiguration：全局 BGP 配置
apiVersion: crd.projectcalico.org/v1
kind: BGPConfiguration
metadata:
  name: default
spec:
  asNumber: 64512
  logLevelScreen: Info
  nodeToNodeMeshEnabled: true    # 节点间全网状

---
# BGPPeer：与外部路由器建立 peer
apiVersion: crd.projectcalico.org/v1
kind: BGPPeer
metadata:
  name: spine1
spec:
  peerIP: 10.0.0.1
  asNumber: 65001
  password: secret
```

### 4.3 Felix 组件详解

```text
Felix 是 Calico 的策略执行组件，运行在每个节点：

  ┌────────────────────────────────────────┐
  │           Felix 进程                     │
  │                                          │
  │  核心职责：                               │
  │  ┌──────────────────────────────────┐   │
  │  │ 1. 接口管理                       │   │
  │  │    - 创建 veth pair                │   │
  │  │    - 配置 caliXXXX 接口            │   │
  │  │    - 设置路由                      │   │
  │  └──────────────────────────────────┘   │
  │  ┌──────────────────────────────────┐   │
  │  │ 2. 路由管理                        │   │
  │  │    - 维护节点路由表                │   │
  │  │    - 与 BIRD 通信                   │   │
  │  │    - 跨节点 Pod CIDR 同步          │   │
  │  └──────────────────────────────────┘   │
  │  ┌──────────────────────────────────┐   │
  │  │ 3. 策略执行（核心）                 │   │
  │  │    - 解析 NetworkPolicy            │   │
  │  │    - 生成 iptables / nftables 规则│   │
  │  │    - 或 eBPF maps                  │   │
  │  └──────────────────────────────────┘   │
  │  ┌──────────────────────────────────┐   │
  │  │ 4. 端点管理                        │   │
  │  │    - 监听 K8s API                  │   │
  │  │    - 跟踪 Pod 创建/删除            │   │
  │  │    - 同步 IP 分配                  │   │
  │  └──────────────────────────────────┘   │
  │  ┌──────────────────────────────────┐   │
  │  │ 5. 健康检查                        │   │
  │  │    - 报告节点状态                  │   │
  │  │    - 接口健康                      │   │
  │  │    - BGP peer 健康                 │   │
  │  └──────────────────────────────────┘   │
  └────────────────────────────────────────┘
```

---

## 五、关键技术原理

### 5.1 NetworkPolicy 实现原理

```text
Calico NetworkPolicy 是 K8s NetworkPolicy 的事实标准实现。

K8s NetworkPolicy：
  apiVersion: networking.k8s.io/v1
  kind: NetworkPolicy
  spec:
    podSelector:    # 选 Pod
      matchLabels:
        app: web
    policyTypes:
      - Ingress
      - Egress
    ingress:
      - from:
        - podSelector:
            matchLabels:
              app: api
        ports:
        - protocol: TCP
          port: 80

  Calico 转换流程：
    1. K8s API 创建 NetworkPolicy CRD
    2. Calico Controller 监听并转换为 Calico CRD
    3. Felix 监听 Calico NetworkPolicy CRD
    4. Felix 转换为 iptables 规则：

    iptables -A cali-tw-allow-eth0-IN
      -m comment --comment "Allow ingress from api"
      -m mark --mark 0x1000000/0x1000000
      -m set --match-set cali40all-src-workload-endpoints src
      -j MARK --set-xmark 0x1000000/0x1000000
    ...

    5. iptables 规则生效
    6. 流量被允许/拒绝
```

### 5.2 BGP 完整工作流

```text
完整 BGP 工作流（节点加入集群时）：

  ┌────────────────────────────────────┐
  │ 1. 新节点加入集群                    │
  │    kubelet 启动                      │
  └─────────┬──────────────────────────┘
            │
            ▼
  ┌────────────────────────────────────┐
  │ 2. Calico 启动                       │
  │    - calico-node Pod 启动           │
  │    - Felix 检测本机接口              │
  └─────────┬──────────────────────────┘
            │
            ▼
  ┌────────────────────────────────────┐
  │ 3. Felix 向 datastore 注册          │
  │    - 创建 IPAM Block                  │
  │    - 上报节点 BGP 信息                │
  └─────────┬──────────────────────────┘
            │
            ▼
  ┌────────────────────────────────────┐
  │ 4. BIRD 启动 BGP 协议                │
  │    - 与其他节点建立 BGP Peer          │
  │    - 通告本节点的 Pod CIDR           │
  └─────────┬──────────────────────────┘
            │
            ▼
  ┌────────────────────────────────────┐
  │ 5. 其他节点学习新路由                │
  │    - 添加路由：10.244.X.0/24 via 新节点│
  │    - 可以发包到新节点                  │
  └────────────────────────────────────┘

  故障处理：
    - 节点宕机 → BIRD 连接断开
    - 其他节点超时（hold time，默认 90s）
    - 自动从路由表移除
```

### 5.3 eBPF 数据面（Calico v3.13+）

```text
Calico 3.13+ 支持 eBPF 数据面（替代 iptables）：

  iptables 模式：
    - 规则匹配性能 O(n)
    - 大集群（service > 5k）性能下降
    - 大量 conntrack 表项

  eBPF 模式：
    - 规则匹配性能 O(1) hash 查找
    - service 5w+ 仍稳定
    - 减少 conntrack 占用

  eBPF 数据平面架构：

  ┌────────────────────────────────────────┐
  │  Linux Kernel                            │
  │                                          │
  │  ┌──────────────────────────────┐      │
  │  │  eBPF Program (Calico dataplane)│      │
  │  │  - tc 钩子（入口/出口）         │      │
  │  │  - 连接跟踪（替代 conntrack）    │      │
  │  │  - 策略匹配（哈希表）           │      │
  │  └──────────────────────────────┘      │
  │                                          │
  │  替代 iptables 链                          │
  └────────────────────────────────────────┘

  启用 eBPF：
    kubectl patch felixconfiguration default --type=merge -p '
      spec:
        bpfEnabled: true
      }'
```

### 5.4 IPAM（IP 地址管理）

```text
Calico IPAM 分配流程：

  ┌────────────────────────────────────┐
  │  Pod 创建请求 IP                     │
  └─────────┬──────────────────────────┘
            │
            ▼
  ┌────────────────────────────────────┐
  │ 1. Felix 接收 IPAM 请求             │
  │    - 检查本节点 Block                │
  └─────────┬──────────────────────────┘
            │
            ▼
  ┌────────────────────────────────────┐
  │ 2. 分配 IP                           │
  │    - 从 IPPool 取一个 /26 Block     │
  │    - 写入 IPAM Block CRD            │
  └─────────┬──────────────────────────┘
            │
            ▼
  ┌────────────────────────────────────┐
  │ 3. 返回 IP 给 kubelet                │
  └────────────────────────────────────┘

  IPAM 特性：
    - 块大小可配置（26, 27, 28 等）
    - 节点预分配 Block
    - 释放时延迟回收
    - 跨节点 Block 缓存
```

---

## 六、关键特性

### 6.1 NetworkPolicy 能力

```yaml
# Calico NetworkPolicy 比 K8s 标准更强大
apiVersion: projectcalico.org/v3
kind: NetworkPolicy
metadata:
  name: allow-api-only
spec:
  selector: app == 'web'
  ingress:
  - action: Allow
    source:
      selector: app == 'api'
    destination:
      ports:
      - 80
  - action: Deny
    source: {}    # 拒绝其他
  egress:
  - action: Allow
    destination:
      selector: app == 'db'
      ports:
      - 5432

# K8s 标准 NetworkPolicy 不支持的：
# - 拒绝规则（默认允许）
# - 命名空间选择
# - 服务账户选择
# - ICMP 控制
```

### 6.2 关键能力清单

| 能力 | 支持情况 |
|------|---------|
| 跨节点 Pod 通信 | ✅ |
| NetworkPolicy（完整） | ✅ K8s 事实标准 |
| GlobalNetworkPolicy | ✅ |
| BGP 物理网络 | ✅（生产推荐） |
| VXLAN 云环境 | ✅ |
| IPIP 跨子网 | ✅ |
| 替换 kube-proxy | ✅（eBPF 模式） |
| L7 策略 | ❌ |
| 服务网格 | ❌ |
| 可观测性 | ⚠️（Calico Cloud / Enterprise） |
| 主机网络集成 | ✅ |
| 双栈 IPv4/IPv6 | ✅ |
| eBPF 数据面 | ✅（3.13+） |
| WireGuard 加密 | ✅ |

### 6.3 资源占用

```text
Calico 资源占用：

  iptables 数据面：
    CPU：~50-200m
    内存：~100-300MB
    规则数：随 service/policy 数量增长

  eBPF 数据面：
    CPU：~30-100m
    内存：~150MB（BPF maps）
    性能更好

  对比 Flannel：Calico 更重
  对比 Cilium：Calico 中等
```

---

## 七、配置与部署

### 7.1 Operator 部署（推荐）

```bash
# 1. 安装 Operator
kubectl apply -f https://raw.githubusercontent.com/projectcalico/calico/v3.27.0/manifests/operator.yaml

# 2. 自定义资源
kubectl apply -f - <<'EOF'
apiVersion: operator.tigera.io/v1
kind: Installation
metadata:
  name: default
spec:
  # 数据面选择
  calicoNetwork:
    ipPools:
    - blockSize: 26
      cidr: 10.244.0.0/16
      encapsulation: VXLANCrossSubnet   # 或 IPIP / None
    nodeAddressAutodetection:
      firstFound: true
    # BGP 配置
    bgp: Enabled
    # eBPF 数据面
    linuxDataplane: BPF
  # 组件启用
  componentResources:
  - componentName: Typha
    resourceRequirements:
      requests:
        cpu: 100m
        memory: 100Mi
EOF

# 3. 验证
kubectl get pods -n calico-system
kubectl get nodes
```

### 7.2 Manifest 部署（传统）

```bash
# 1. 下载
curl -O https://raw.githubusercontent.com/projectcalico/calico/v3.27.0/manifests/calico.yaml

# 2. 修改 Pod CIDR
sed -i 's|192.168.0.0/16|10.244.0.0/16|g' calico.yaml

# 3. 应用
kubectl apply -f calico.yaml
```

### 7.3 选择数据面模式

```bash
# VXLAN 模式（默认，云环境友好）
kubectl patch installation default --type=merge -p '
  spec:
    calicoNetwork:
      encapsulation: VXLAN
    }'

# IPIP 模式（跨子网）
kubectl patch installation default --type=merge -p '
  spec:
    calicoNetwork:
      encapsulation: IPIP
    }'

# 无封装（性能最高，需 BGP）
kubectl patch installation default --type=merge -p '
  spec:
    calicoNetwork:
      encapsulation: None
    bgp: Enabled
    }'

# VXLAN with cross-subnet（推荐云环境）
kubectl patch installation default --type=merge -p '
  spec:
    calicoNetwork:
      encapsulation: VXLANCrossSubnet
    }'
```

### 7.4 启用 eBPF 数据面

```bash
# 1. 启用 eBPF
kubectl patch installation default --type=merge -p '
  spec:
    calicoNetwork:
      linuxDataplane: BPF
    }'

# 2. 重启 calico-node Pod
kubectl delete pods -n calico-system -l k8s-app=calico-node

# 3. 验证
kubectl exec -n calico-system <calico-node-pod> -- calicoctl node status
# 应显示 BPF dataplane
```

### 7.5 配置 BGP 与物理网络

```yaml
# 1. 节点配置 BGP peer
apiVersion: crd.projectcalico.org/v1
kind: BGPPeer
metadata:
  name: spine-switch-1
spec:
  peerIP: 10.0.0.1               # ToR 交换机 IP
  asNumber: 65001                # 交换机 AS 号
  password: secret
  keepOriginalNextHop: true      # 保留原始下一跳（重要）
---
# 2. 节点 BGP filter（只通告 Pod CIDR）
apiVersion: crd.projectcalico.org/v1
kind: BGPFilter
metadata:
  name: only-pod-cidr
spec:
  order: 10
  action: Accept
  matchOperator: In
  nodeSelector: all()
  match:
    prefix:
      cidr: 10.244.0.0/16       # 仅通告 Pod CIDR
```

---

## 八、性能数据

### 8.1 延迟基准

```text
跨节点 Pod-to-Pod 通信延迟（千兆网络）：

  ┌─────────────────┬──────────────┐
  │  数据面          │   延迟        │
  ├─────────────────┼──────────────┤
  │  无封装 + BGP   │   30-50μs   │
  │  IPIP           │   50-80μs   │
  │  VXLAN          │   60-100μs  │
  │  eBPF 数据面    │   25-50μs   │
  └─────────────────┴──────────────┘

  对比：
    Flannel host-gw：~40μs
    Calico 无封装：~40μs
    Cilium eBPF：~25μs（最快）

  Policy 引入的开销：
    iptables：~5-20μs
    eBPF：~2-5μs
```

### 8.2 大规模集群

```text
Calico 在大规模集群表现（生产验证）：

  ┌─────────────────┬──────────────────────┐
  │ 集群规模          │ 表现                 │
  ├─────────────────┼──────────────────────┤
  │ 100 节点         │ 优秀                  │
  │ 500 节点         │ 良好                  │
  │ 1000 节点        │ 良好（需 typha）      │
  │ 5000 节点        │ 可用（需架构优化）    │
  │ 10000 节点       │ 极大规模需特殊设计    │
  └─────────────────┴──────────────────────┘

  关键：
    - BGP Route Reflector 模式
    - typha 减轻 API Server 压力
    - Felix 横向扩展
    - eBPF 数据面提升性能
```

### 8.3 Policy 性能

```text
NetworkPolicy 数量对性能影响：

  iptables 数据面：
    1000 Policy：~5μs 额外延迟
    5000 Policy：~10-20μs 额外延迟
    10000 Policy：~50μs 额外延迟（性能下降）

  eBPF 数据面：
    1000 Policy：~2μs 额外延迟
    5000 Policy：~5μs 额外延迟
    10000 Policy：~10μs 额外延迟（性能平稳）

  建议：
    - Policy 数量 < 5000：用 iptables
    - Policy 数量 > 5000：切换 eBPF
```

---

## 九、适用场景

### 9.1 强烈推荐

```text
1. 生产 K8s 集群
   - NetworkPolicy 必备
   - 大规模验证

2. 裸金属 / 自建机房
   - 物理网络 BGP 接入
   - 性能最优

3. 多租户集群
   - NetworkPolicy 隔离租户
   - 细粒度安全

4. 严格安全要求
   - 完整 NetworkPolicy 实现
   - 合规友好

5. 大规模集群（500-2000 节点）
   - BGP 路由可扩展
   - typha 集群扩展
```

### 9.2 可选场景

```text
1. 混合云
   - VXLAN 模式适合
   - 但非最佳

2. 边缘计算
   - eBPF 数据面高效
   - 但需较新内核

3. 多集群管理
   - Calico ClusterMesh
   - 跨集群 NetworkPolicy
```

### 9.3 不推荐

```text
1. 学习测试
   - 配置复杂
   - 推荐 Flannel

2. L7 策略需求
   - Calico 不支持 L7
   - 推荐 Cilium

3. 服务网格
   - Calico 不是服务网格
   - 推荐 Istio + Cilium

4. 老内核（< 4.19）
   - eBPF 数据面不能用
   - iptables 数据面性能差
```

---

## 十、核心要点速记

### Calico 一句话定位

```text
Calico = Tigera 公司的 L3 网络 CNI
生产最稳、NetworkPolicy 事实标准
BGP + 无封装 + iptables/eBPF 数据面
适合生产 K8s，特别是裸金属环境
```

### 架构速记

```text
组件：
  calico-node（DaemonSet，每节点）
    - Felix（iptables/eBPF 策略）
    - BIRD（BGP 路由）
    - confd（配置同步）
  typha（集群扩展）
  datastore（K8s API / etcd）

数据流（无封装 + BGP）：
  Pod → veth → cbr0 → 路由表
       → 物理网络 → BGP 路由
       → 目标节点 → cbr0 → 目标 Pod
```

### 四种数据面对比

```text
无封装：性能最高，需 BGP / 同子网
IPIP：跨子网，封装 20 字节
VXLAN：云环境，封装 50 字节
eBPF：所有优势，性能最好（4.19+ 内核）
```

### NetworkPolicy 能力

```text
Calico NetworkPolicy（Calico CRD）：
  ✅ 拒绝规则（默认允许 → 可拒绝）
  ✅ 命名空间选择
  ✅ 服务账户选择
  ✅ ICMP / 协议控制
  ✅ GlobalNetworkPolicy（集群级）

K8s NetworkPolicy（标准）：
  ✅ 基本入站/出站规则
  ✅ Pod Selector
  ✅ Namespace Selector
  ❌ 默认拒绝（只能 Allow）
```

### 一句话总结

```text
Calico = 生产最稳 CNI
无封装 + BGP = 裸金属最佳
iptables/eBPF = 灵活选择
NetworkPolicy 完整 = 隔离能力最强
```

### 关键文件

```bash
# Calico 主配置
kubectl get installation default -o yaml
kubectl get ippools -o yaml
kubectl get bgpconfigurations -o yaml
kubectl get bgppeers -o yaml
kubectl get networkpolicies -A

# Felix 状态
kubectl exec -n calico-system <calico-node-pod> -- calicoctl node status
kubectl exec -n calico-system <calico-node-pod> -- calicoctl node diags

# BGP 状态
kubectl exec -n calico-system <calico-node-pod> -- calicoctl bgp peers
kubectl exec -n calico-system <calico-node-pod> -- calicoctl bgp routes

# 路由表
ip route show table all
```

---

## 十一、参考

```text
- Calico 官方文档: https://docs.tigera.io/calico/latest/
- Calico GitHub: https://github.com/projectcalico/calico
- CalicoCNCF: https://www.cncf.io/projects/calico/
- Project Calico 培训: https://archive.projectcalico.org/
- BGP 协议 RFC: https://tools.ietf.org/html/rfc4271
- IPIP 协议 RFC: https://tools.ietf.org/html/rfc1853
- VXLAN 协议 RFC: https://tools.ietf.org/html/rfc7348
- K8s NetworkPolicy: https://kubernetes.io/docs/concepts/services-networking/network-policies/
- 对比文档: ../对比.md
```
