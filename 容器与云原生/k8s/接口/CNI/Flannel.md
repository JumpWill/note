# Flannel

## 一、概述

**Flannel** 是 CoreOS（已被 Red Hat 收购）2014 年起维护的 CNI 插件，是 K8s 生态中**最简单**的 overlay 网络方案。

**核心定位**：

- 目标：**L3 overlay 网络**，不做 NetworkPolicy
- 数据面：VXLAN / host-gw / UDP / IPIP 四种 backend 可选
- 控制面：etcd 存储 Pod CIDR 分配
- IPAM：内置，从 `kube-flannel-cfg` ConfigMap 读 Pod CIDR
- 规模：常用于**小集群 / 开发环境 / 单 L2 数据中心**

**特点速记**：

- ✅ 简单：零策略、零配置即可用
- ✅ 稳定：成熟多年，生产可用
- ✅ 资源占用极低
- ❌ 不支持 NetworkPolicy（v0.10+ 雏形）
- ❌ 无可观测性
- ❌ 无服务网格集成

---

## 二、整体架构

```text
┌─────────────────────────────────────────────────────────────┐
│                  Flannel 整体架构                              │
│                                                              │
│  ┌─────────────────────┐      ┌─────────────────────────┐ │
│  │  Master 节点         │      │  Worker 节点            │ │
│  │                     │      │                         │ │
│  │ ┌─────────────────┐ │      │ ┌─────────────────┐  │ │
│  │ │ kube-apiserver   │ │      │ │ kubelet          │  │ │
│  │ └─────────────────┘ │      │ └─────────────────┘  │ │
│  │         │              │      │         │             │ │
│  │ ┌──────▼──────┐       │      │ ┌───────▼──────┐    │ │
│  │ │ etcd         │       │      │ │ flanneld      │    │ │
│  │ │ (存储子网分配)│◄─────┼──────┤ │ (后台守护)    │    │ │
│  │ └──────────────┘       │      │ └───────┬──────┘    │ │
│  │                        │      │         │             │ │
│  │                        │      │ ┌───────▼──────┐    │ │
│  │                        │      │ │ flannel.1    │    │ │
│  │                        │      │ │ (vxlan 设备)  │    │ │
│  │                        │      │ └──────────────┘    │ │
│  └────────────────────────┘      └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘

架构组件：
  1. flanneld：每节点运行的守护进程
     - 监听 etcd 中的子网分配
     - 维护本节点路由表
     - 处理 UDP/VXLAN 封装

  2. etcd：存储集群网络配置
     - Pod CIDR 分配信息
     - 每个节点的子网段
     - 全局配置

  3. flannel.X：网络设备
     - flannel.1 表示使用 VXLAN
     - flannel.0 表示 host-gw
     - 类似虚拟网卡
```

### Flanneld 与 CNI 插件交互

```text
Pod 创建时的 Flannel 调用链：

  kubelet
    ↓
  CNI 插件调用（/opt/cni/bin/flannel）
    ↓
  Flannel CNI 插件
    ├─ 读取 etcd 获取本节点子网
    ├─ 创建 veth pair（一端给 Pod）
    ├─ 将 veth 接入 cbr0 网桥
    ├─ 配置路由（指向 flannel.1）
    └─ 返回 Pod IP 给 kubelet
    ↓
  Pod 启动，IP 可达

详细流程：
  1. kubelet 创建 Pod 网络命名空间
  2. 调用 CNI 插件
  3. Flannel 插件：
     - 从 etcd 获取本节点子网（如 10.244.1.0/24）
     - 分配 Pod IP（如 10.244.1.5）
     - 创建 veth pair
     - 一端放入 Pod netns（eth0）
     - 另一端接入宿主机（cbr0 / flannel.1）
     - 添加路由（其他子网 → flannel.1）
  4. kubelet 启动容器进程
```

---

## 三、数据面工作原理

### 3.1 VXLAN backend（默认推荐）

```text
Pod A 在 Node 1 (10.0.0.10)   Pod B 在 Node 2 (10.0.0.20)
IP: 10.244.1.5                 IP: 10.244.2.8

Pod A 发包到 Pod B 的完整流程：

  Pod A (10.244.1.5)
      │ eth0 (容器内)
      ▼
  veth pair 一端
      │
      ▼ 宿主机网络命名空间
  cbr0 网桥
      │
      ▼
  flannel.1 (VXLAN 设备, VTEP)
      │
      │  封装过程:
      │  原始包: [10.244.1.5 → 10.244.2.8] [TCP]
      │  VXLAN 封装:
      │  [外层 UDP: 4789] [VNI=1]
      │  [外层 IP: 10.0.0.10 → 10.0.0.20]
      │  [内层 IP: 10.244.1.5 → 10.244.2.8]
      │  [TCP data]
      ▼
  物理网络（underlay）
      │
      ▼
  Node 2 eth0
      │
      ▼
  Node 2 flannel.1 (VTEP)
      │  解封装:
      │  - 去掉外层 UDP/IP
      │  - 提取内层包
      ▼
  Node 2 cbr0
      │
      ▼
  Pod B (10.244.2.8)
      │
      ▼
  eth0（容器内）

封装开销：
  - 50 字节（VXLAN header）
  - 增加 60-100μs 延迟
  - 但隔离性好（适合跨 L3 网络）
```

### 3.2 host-gw backend（性能优先）

```text
Pod A 在 Node 1 (10.0.0.10)   Pod B 在 Node 2 (10.0.0.20)
IP: 10.244.1.5                 IP: 10.244.2.8

Pod A 发包到 Pod B 的流程（无封装）：

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
  路由表:
    10.244.2.0/24 via 10.0.0.20 dev eth0
      │
      ▼ 直接转发
  Node 1 eth0 (10.0.0.10)
      │
      ▼
  物理网络（L2/L3）
      │
      ▼
  Node 2 eth0 (10.0.0.20)
      │
      ▼ 查路由表
      │
  路由表:
    10.244.2.0/24 dev cbr0
      │
      ▼
  cbr0 网桥
      │
      ▼
  Pod B (10.244.2.8)

优势：
  - 无封装，零额外字节
  - 延迟最低（30-50μs）
  - 与物理网络性能一致

限制：
  - 必须所有节点在同一 L2 网络
  - 不适合云环境（无法控制底层路由）
  - 需要 etcd 维护节点路由信息
```

### 3.3 UDP backend（兼容性好）

```text
最原始的封装方式，UDP 包封装：

  原始包（1500 字节以下）
       │
       ▼ 封装为 UDP
  UDP 头 + 原始包（最大 65535 字节）
       │
       ▼
  物理网络

  优点：兼容性最好
  缺点：性能最差，已不推荐
```

### 3.4 IPIP backend（IP-in-IP）

```text
类似 VXLAN 但更轻量：

  原始包: [10.244.1.5 → 10.244.2.8]
       │
       ▼ IPIP 封装
  外层 IP: [10.0.0.10 → 10.0.0.20]
  内层 IP: [10.244.1.5 → 10.244.2.8]

  开销：20 字节
  延迟：50-80μs
  适用于：跨子网但同区域的节点
```

---

## 四、控制面

### 4.1 etcd 中的网络配置

```text
Flannel 在 etcd 中存储的数据结构：

/atomic.io/network/config
  {
    "Network": "10.244.0.0/16",      # Pod CIDR
    "Backend": {
      "Type": "vxlan",               # backend 类型
      "VNI": 1,                       # VXLAN Network ID
      "Port": 4789                    # VXLAN UDP 端口
    }
  }

/atomic.io/network/subnets
  /10.244.1.0-24  →  节点信息
    {
      "PublicIP": "10.0.0.10",
      "BackendType": "vxlan",
      "BackendData": {
        "VtepMAC": "aa:bb:cc:dd:ee:ff"
      }
    }
  /10.244.2.0-24  →  节点信息
    {
      "PublicIP": "10.0.0.20",
      "BackendType": "vxlan",
      "BackendData": {
        "VtepMAC": "11:22:33:44:55:66"
      }
    }
```

### 4.2 子网分配流程

```text
Flannel 子网分配步骤：

  1. Flannel 启动（DaemonSet 部署）
       ↓
  2. 读取 kube-flannel-cfg ConfigMap
     - 获取 Pod CIDR（10.244.0.0/16）
     - 获取 backend 类型
       ↓
  3. 从 Pod CIDR 分配子网（默认 /24）
     - 例如 10.244.1.0/24 分配给当前节点
       ↓
  4. 注册到 etcd
     - /atomic.io/network/subnets/10.244.1.0-24
     - 包含节点 IP、VTEP MAC 等
       ↓
  5. 配置本机路由
     - 其他子网 via 目的节点 IP
     - dev flannel.1
       ↓
  6. 创建 cbr0 网桥
     - Pod veth 接入此网桥
       ↓
  7. 启动 UDP 监听端口（VXLAN）
     - 4789
```

### 4.3 网络变更处理

```text
Flannel 如何感知节点变化：

  1. 节点加入集群
     - Flannel 启动
     - 分配子网
     - 注册到 etcd
     - 其他节点订阅 etcd
     - 其他节点添加新路由

  2. 节点离开集群
     - 注册 lease 过期
     - etcd 自动清理
     - 其他节点更新路由表

  3. 节点 IP 变化
     - 重新注册到 etcd
     - 其他节点更新路由
```

---

## 五、关键技术原理

### 5.1 Flannel VXLAN 原理详解

```text
VXLAN（Virtual Extensible LAN）封装：

  ┌────────────────────────────────────────┐
  │  外层 Ethernet 头                        │  14 字节
  ├────────────────────────────────────────┤
  │  外层 IP 头（UDP src/dst + 协议号）      │  20 字节
  ├────────────────────────────────────────┤
  │  UDP 头（dst port 4789）                 │  8 字节
  ├────────────────────────────────────────┤
  │  VXLAN 头（VNI 24 位 + 标志位）         │  8 字节
  ├────────────────────────────────────────┤
  │  内层 Ethernet 头                        │  14 字节
  ├────────────────────────────────────────┤
  │  内层 IP 头（Pod src/dst）                │  20 字节
  ├────────────────────────────────────────┤
  │  TCP/UDP 头                              │  8 字节
  ├────────────────────────────────────────┤
  │  Payload                                  │  变长
  └────────────────────────────────────────┘

  总开销：约 50 字节
  最大支持：约 1600 万个 VNI（24 位）
```

### 5.2 VTEP（VXLAN Tunnel Endpoint）

```text
VTEP 是 VXLAN 的隧道端点：

  ┌──────────────────────────────────┐
  │  Node 1（VTEP）                   │
  │                                  │
  │  flannel.1 设备（VTEP）           │
  │  IP: 10.0.0.10                   │
  │  MAC: aa:bb:cc:dd:ee:ff        │
  │  VNI: 1                          │
  │                                  │
  │  功能：                           │
  │  - 接收 UDP 4789 包              │
  │  - 解封装 VXLAN                   │
  │  - 转发到本机 cbr0                │
  └──────────────────────────────────┘
           ▲
           │ VXLAN 隧道（UDP 4789）
           ▼
  ┌──────────────────────────────────┐
  │  Node 2（VTEP）                   │
  │                                  │
  │  flannel.1 设备（VTEP）           │
  │  IP: 10.0.0.20                   │
  │  MAC: 11:22:33:44:55:66        │
  └──────────────────────────────────┘
```

### 5.3 host-gw 工作原理

```text
host-gw（Host Gateway）利用 Linux 内核路由表：

  Node 1 (10.0.0.10)                Node 2 (10.0.0.20)
  ┌─────────────────┐              ┌─────────────────┐
  │ cbr0             │              │ cbr0             │
  │ 10.244.1.0/24    │              │ 10.244.2.0/24    │
  └────────┬─────────┘              └────────┬─────────┘
           │                                 │
  ┌────────▼─────────┐              ┌────────▼─────────┐
  │ eth0              │              │ eth0              │
  │ 10.0.0.10         │◄────────────►│ 10.0.0.20         │
  └──────────────────┘    L2/L3     └──────────────────┘
                                  网络

  Node 1 路由表：
    10.244.2.0/24 via 10.0.0.20 dev eth0
    10.244.1.0/24 dev cbr0
    default via 网关 dev eth0

  工作流程：
  Pod A (10.244.1.5) → cbr0 → 路由表
    → 10.244.2.0/24 via 10.0.0.20
    → eth0 → 物理网络 → Node 2 eth0
    → 路由表 → cbr0 → Pod B (10.244.2.8)

  优势：无封装，零开销
  限制：所有节点必须在同一 L2（或路由可达）
```

### 5.4 MTU 处理

```text
Flannel 的 MTU 处理：

  物理网络 MTU：1500 字节
  VXLAN 封装开销：50 字节
  Flannel 推荐 Pod MTU：1450 字节

  问题：
    Pod 默认 MTU = 1500
    VXLAN 封装后 = 1550
    超过物理网络 MTU → 分片 → 性能下降

  解决：
    1. Flannel 启动时设置 MTU
       ip link set flannel.1 mtu 1450
    2. CNI 插件写入 Pod 的 MTU
       通常 1450（1500 - 50）
    3. Pod 内应用自动使用此 MTU

  验证：
    docker exec pod ip link show eth0
    # mtu 1450
```

---

## 六、关键特性

### 6.1 四种 backend 对比

| Backend | 性能 | 封装开销 | 跨子网 | 云环境 | 复杂度 |
|---------|------|----------|--------|--------|--------|
| **vxlan** | 中（~70μs） | 50 字节 | ✅ | ✅ | 低 |
| **host-gw** | 高（~40μs） | 0 字节 | ❌（需 L2） | ❌ | 最低 |
| **udp** | 低 | 大量 | ✅ | ✅ | 最低 |
| **ipip** | 中（~60μs） | 20 字节 | ✅ | ✅ | 低 |

### 6.2 关键能力清单

| 能力 | 支持情况 |
|------|---------|
| 跨节点 Pod 通信 | ✅ |
| Pod CIDR 分配 | ✅（内置 IPAM） |
| Service ClusterIP | ✅（依赖 kube-proxy） |
| NetworkPolicy | ❌（v0.10+ 雏形） |
| IPv6 双栈 | 部分支持 |
| 主机网络集成 | ✅（host-gw 模式） |
| 跨子网通信 | ✅（VXLAN/IPIP） |
| 零信任安全 | ❌ |
| 可观测性 | ❌ |
| L7 策略 | ❌ |

### 6.3 资源占用

```text
Flannel 资源占用（极低）：

  CPU：~10-50m（idle）/ ~100m（peak）
  内存：~30-50MB
  磁盘：< 100MB
  网络：与 backend 相关

  对比 Cilium/Calico：
    Flannel：最轻量
    Calico：中等（eBPF 时更省）
    Cilium：较高（BPF maps 占用内存）
```

---

## 七、配置与部署

### 7.1 部署方式（推荐 Helm）

```bash
# 添加 helm 仓库
helm repo add flannel https://flannel-io.github.io/flannel

# 安装（自动检测 K8s 版本）
helm install flannel flannel/flannel \
  --namespace kube-flannel \
  --create-namespace
```

### 7.2 K8s 部署清单

```yaml
# kube-flannel-cfg ConfigMap
apiVersion: v1
kind: ConfigMap
metadata:
  name: kube-flannel-cfg
  namespace: kube-flannel
data:
  net-conf.json: |
    {
      "Network": "10.244.0.0/16",
      "Backend": {
        "Type": "vxlan",
        "VNI": 1,
        "Port": 4789
      }
    }
  cni-conf.json: |
    {
      "name": "cbr0",
      "cniVersion": "0.3.1",
      "plugins": [
        {
          "type": "flannel",
          "delegate": {
            "hairpinMode": true,
            "isDefaultGateway": true
          }
        },
        {
          "type": "portmap",
          "capabilities": {
            "portMappings": true
          }
        }
      ]
    }
```

### 7.3 切换 backend

```bash
# 方法 1：修改 ConfigMap 后重启 Pod
kubectl -n kube-flannel edit cm kube-flannel-cfg
# 修改 Backend.Type 为 "host-gw" / "ipip" / "udp"
kubectl -n kube-flannel delete pod -l app=flannel

# 方法 2：通过 Helm
helm upgrade flannel flannel/flannel \
  --set "configMap.net-conf.json=..." \
  --reuse-values

# 注意：切换 backend 需要重建所有 Pod 的网络
```

### 7.4 关键配置参数

```bash
# Flannel 启动参数
--iface=eth0                       # 指定网卡
--ip-masq=true                     # IP 伪装（出网时）
--public-ip=10.0.0.10              # 显式指定公网 IP
--subnet-file=/etc/flannel/subnet.env  # 子网文件位置
--kube-subnet-mgr=true              # 使用 K8s API 管理子网
--etcd-endpoints=https://10.0.0.1:2379  # etcd 地址

# Backend 特定参数（VXLAN）
--vni=1
--port=4789

# Backend 特定参数（host-gw）
# 无特殊参数
```

---

## 八、性能数据

### 8.1 延迟基准

```text
跨节点 Pod-to-Pod 通信延迟（千兆网络）：

  ┌─────────────────┬──────────────┐
  │  Backend         │   延迟        │
  ├─────────────────┼──────────────┤
  │  host-gw        │   30-50μs   │
  │  ipip           │   50-80μs   │
  │  vxlan          │   60-100μs  │
  │  udp            │   100-200μs │
  └─────────────────┴──────────────┘

  同节点 Pod 通信：~5-20μs（不经 CNI）

  对比：
    Flannel host-gw：~40μs（参考基准）
    Calico iptables：~50μs
    Calico eBPF：~30μs
    Cilium eBPF：~25μs
```

### 8.2 吞吐量

```text
iperf3 跨节点测试（千兆网络）：

  host-gw：~9.4 Gbps（接近物理极限）
  vxlan：~9.0 Gbps（轻微封装开销）
  ipip：~9.2 Gbps
  
  对比：
    Flannel vxlan：~9.0 Gbps
    Calico vxlan：~9.0 Gbps
    Calico bgp（裸机）：~9.5 Gbps
    Cilium eBPF：~9.4 Gbps
```

### 8.3 大规模集群表现

```text
集群规模：500 节点 / 5000 Pod

  Flannel：
    ✅ 正常工作
    ⚠️  etcd 成为瓶颈（频繁 watch）
    ⚠️  路由表巨大

  Calico：
    ✅ 优
    - 分布式 BGP，水平扩展
    - 大规模生产验证

  Cilium：
    ✅ 优
    - eBPF 高效
    - Hubble 可观测
```

---

## 九、适用场景

### 9.1 强烈推荐

```text
1. 开发测试环境
   - 简单即用，无策略需求

2. 小集群（< 200 节点）
   - 资源占用低
   - 维护简单

3. 学习 K8s
   - 容易理解 CNI 工作原理

4. 单 L2 数据中心
   - 用 host-gw 性能最佳

5. 与 Calico policy-only 模式配合
   - Flannel 做网络
   - Calico 做 NetworkPolicy
```

### 9.2 不推荐

```text
1. 大规模生产集群（> 500 节点）
   - etcd 压力大
   - 路由表过大

2. 需要 NetworkPolicy
   - Flannel 不支持

3. 多云环境
   - 跨区域网络复杂

4. 需要可观测性
   - Flannel 无内置可观测

5. 严格安全合规
   - 缺乏高级安全特性
```

---

## 十、核心要点速记

### Flannel 一句话定位

```text
Flannel = CoreOS 维护的极简 overlay CNI
无 NetworkPolicy、无可观测性
数据面可选 vxlan / host-gw / ipip / udp
适合小集群 / 开发 / 学习 / 与 Calico 配合
```

### 架构速记

```text
组件：
  flanneld（每节点 DaemonSet）
  etcd（存储子网分配）
  flannel.1（VXLAN 设备）
  cbr0（Pod 网桥）

数据流：
  Pod → veth → cbr0 → flannel.1
       → 物理网络 → 目标节点 flannel.1
       → cbr0 → veth → 目标 Pod
```

### 四种 Backend 对比

```text
host-gw：性能最高，需 L2
vxlan：通用，封装 50 字节
ipip：跨子网，封装 20 字节
udp：兼容好，性能差（已不用）
```

### 适用 vs 不适用

```text
适用：
  - 开发测试
  - 小集群（< 200 节点）
  - 单 L2 数据中心
  - 与 Calico 配合

不适用：
  - 大规模生产
  - 需要 NetworkPolicy
  - 多云
  - 需要可观测性
```

### 一句话总结

```text
Flannel = 最简单的 CNI，零策略
适合开发和小集群
生产用 NetworkPolicy 就选 Calico 或 Cilium
```

### 关键文件

```bash
# Flannel 配置文件
/etc/flannel/subnet.env
/etc/cni/net.d/10-flannel.conflist

# K8s ConfigMap
kubectl -n kube-flannel get cm kube-flannel-cfg -o yaml

# DaemonSet
kubectl -n kube-flannel get ds kube-flannel

# 日志
kubectl -n kube-flannel logs -l app=flannel
```

---

## 十一、参考

```text
- Flannel GitHub: https://github.com/flannel-io/flannel
- Flannel 官方文档: https://github.com/flannel-io/flannel/blob/master/Documentation/
- CNCF Sandbox 项目: https://www.cncf.io/projects/flannel/
- VXLAN 协议 RFC: https://tools.ietf.org/html/rfc7348
- K8s 网络模型: https://kubernetes.io/docs/concepts/cluster-administration/networking/
- 对比文档: ../对比.md
```
