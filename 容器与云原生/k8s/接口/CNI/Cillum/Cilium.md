# Cilium

## 一、概述

**Cilium** 是 Isovalent（已被 Cisco 收购）开发的 CNI 插件，是 K8s 生态中**性能最强、可观测最好**的方案（CNCF 毕业项目）。

**核心定位**：

- 数据面：**eBPF**（XDP / TC / sock_ops）
- 控制面：**Kubernetes CRD**（无独立 datastore）
- NetworkPolicy：**完整 K8s 标准 + 扩展 L7**
- 可观测：**Hubble**（service map + flow + L7 metrics）
- 规模：大规模集群验证

**特点速记**：

- ✅ 性能最强（eBPF 内核态）
- ✅ 替换 kube-proxy（透明集成）
- ✅ Hubble 可观测性业界最强
- ✅ L7 策略（HTTP/gRPC/Kafka）
- ✅ 服务网格集成（Cilium Service Mesh）
- ❌ 内核要求高（建议 5.10+）
- ❌ 学习曲线陡

---

## 二、整体架构

```text
┌─────────────────────────────────────────────────────────────┐
│                   Cilium 整体架构                              │
│                                                              │
│  ┌─────────────────────┐      ┌─────────────────────────┐ │
│  │  Master 节点         │      │  Worker 节点            │ │
│  │                     │      │                         │ │
│  │ ┌─────────────────┐ │      │ ┌─────────────────┐  │ │
│  │ │ kube-apiserver   │ │      │ │ kubelet          │  │ │
│  │ └─────────────────┘ │      │ └─────────────────┘  │ │
│  │         │              │      │         │             │ │
│  │ ┌──────▼──────┐       │      │ ┌───────▼──────┐    │ │
│  │ │ CRD 资源     │       │      │ │ cilium-agent  │    │ │
│  │ │ (CiliumNode- │       │      │ │               │    │ │
│  │ │  Policy...)  │       │      │ │ ┌───────────┐│    │ │
│  │ └──────────────┘       │      │ │ │ eBPF Map   ││    │ │
│  │                        │      │ │ │ (BPF FS)    ││    │ │
│  │                        │      │ │ └───────────┘│    │ │
│  │                        │      │ │ ┌───────────┐│    │ │
│  │                        │      │ │ │ Hubble     ││    │ │
│  │                        │      │ │ │ (可观测)   ││    │ │
│  │                        │      │ │ └───────────┘│    │ │
│  │                        │      │ │ ┌───────────┐│    │ │
│  │                        │      │ │ │ lxc/l7     ││    │ │
│  │                        │      │ │ │ proxy      ││    │ │
│  │                        │      │ │ └───────────┘│    │ │
│  └────────────────────────┘      │ │ ┌───────────┐│    │ │
│                                  │ │ │ CNI Plugin ││    │ │
│                                  │ │ │ (Cilium CNI)│    │ │
│                                  │ │ └───────────┘│    │ │
│                                  │ └───────┬───────┘    │ │
│                                  │         │             │ │
│                                  │ ┌───────▼──────┐    │ │
│                                  │ │  cilium_host │    │ │
│                                  │ │  (节点 veth)  │    │ │
│                                  │ └──────────────┘    │ │
│                                  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘

架构组件：
  1. cilium-agent（每节点 DaemonSet）
     - eBPF 程序加载到内核
     - 连接跟踪（替代 conntrack）
     - 策略执行（L3/L4/L7）
     - Hubble 集成
     - 可选：ClusterMesh 跨集群

  2. CRD 资源（控制平面）
     - CiliumNode
     - CiliumClusterwideNetworkPolicy
     - CiliumNetworkPolicy（CiliumNetworkPolicy 扩展）
     - CiliumL2Policy
     - 等等

  3. Hubble（可观测）
     - Hubble Relay（聚合）
     - Hubble UI（Web）
     - Hubble CLI（命令行）

  4. Cilium CNI Plugin
     - /opt/cni/bin/cilium-cni
     - 处理 Pod 网络配置
```

### eBPF 数据面架构

```text
┌─────────────────────────────────────────────────────────┐
│  Linux Kernel                                              │
│                                                            │
│  ┌──────────────────────────────────────────────────┐    │
│  │  eBPF 钩子点                                       │    │
│  │                                                    │    │
│  │  XDP（网卡驱动层）                                  │    │
│  │    ↓                                                │    │
│  │  TC（流量控制层）                                   │    │
│  │    ↓                                                │    │
│  │  Socket Layer                                       │    │
│  │    ↓                                                │    │
│  │  kprobe（内核探针）                                 │    │
│  │    ↓                                                │    │
│  │  eBPF Maps（共享数据结构）                          │    │
│  │    - cilium_lb（负载均衡）                          │    │
│  │    - cilium_policy（策略）                          │    │
│  │    - cilium_ct（连接跟踪）                          │    │
│  │    - cilium_ipcache（IP 缓存）                      │    │
│  └──────────────────────────────────────────────────┘    │
│                                                            │
│  Cilium 加载的 eBPF 程序：                                  │
│  ┌──────────────────────────────────────────────────┐    │
│  │  - bpf_lxc：容器网络入口                            │    │
│  │  - bpf_netdev_eth0：宿主机网络                     │    │
│  │  - bpf_lb：XDP 负载均衡                             │    │
│  │  - bpf_sock_conn：socket 连接跟踪                   │    │
│  │  - bpf_overlay：Overlay 网络                        │    │
│  │  - bpf_xdp：XDP 入口（最快）                       │    │
│  └──────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

---

## 三、数据面工作原理

### 3.1 eBPF 数据面（默认推荐）

```text
eBPF 是 Cilium 的核心优势：

  ┌─────────────────────────────────────────────────────┐
  │  Pod A 发包到 Pod B                                   │
  └─────────────────┬───────────────────────────────────┘
                    │
                    ▼
  ┌─────────────────────────────────────────────────────┐
  │  Pod A 内应用                                         │
  │  系统调用 send() / sendto()                          │
  └─────────────────┬───────────────────────────────────┘
                    │
                    ▼
  ┌─────────────────────────────────────────────────────┐
  │  Linux 内核                                          │
  │                                                      │
  │  1. eBPF 钩子：sock_ops（socket 层）                  │
  │     - 拦截 socket 系统调用                            │
  │     - 识别目的地址是 Pod IP                          │
  │     - 决定转发路径                                  │
  │                                                      │
  │  2. eBPF 钩子：tc（流量控制层）                        │
  │     - 网卡出口数据包                                  │
  │     - 应用策略匹配（NetworkPolicy）                  │
  │     - 允许/拒绝                                      │
  │                                                      │
  │  3. eBPF Map 查询                                    │
  │     - cilium_lb：负载均衡表                          │
  │     - cilium_policy：策略表                          │
  │     - cilium_ct：连接跟踪表                          │
  │                                                      │
  │  4. XDP（最快路径）                                  │
  │     - 网卡驱动层直接处理                            │
  │     - Service 负载均衡的最优路径                      │
  │     - 不经过 TCP/IP 协议栈                          │
  └─────────────────┬───────────────────────────────────┘
                    │
                    ▼
  ┌─────────────────────────────────────────────────────┐
  │  网卡 eth0 → 物理网络 → 目标节点                      │
  └─────────────────────────────────────────────────────┘

性能：
  - 完全在内核态执行（无用户态切换）
  - 哈希表查找 O(1)
  - 比 iptables 快 2-5 倍
```

### 3.2 Cilium 替代 kube-proxy

```text
传统 kube-proxy（iptables）：
  ┌────────────────────────────────────────┐
  │  用户请求                             │
  │  ↓                                    │
  │  iptables PREROUTING（DNAT）          │
  │  ↓                                    │
  │  iptables 规则匹配（O(n)）              │
  │  ↓                                    │
  │  后端 Pod                              │
  └────────────────────────────────────────┘

Cilium 替代 kube-proxy：
  ┌────────────────────────────────────────┐
  │  用户请求                             │
  │  ↓                                    │
  │  XDP（网卡驱动层）                     │
  │  ↓                                    │
  │  eBPF Map 查询（O(1) 哈希）            │
  │  ↓                                    │
  │  直接转发到后端 Pod                    │
  └────────────────────────────────────────┘

性能对比（service 10000 时）：
  iptables：~50μs P99
  Cilium eBPF：~5μs P99

性能对比（service 100 时）：
  iptables：~20μs P99
  Cilium eBPF：~3μs P99
```

### 3.3 加密通信（WireGuard）

```text
Cilium 默认支持 WireGuard 节点间加密：

  Node 1 (10.0.0.10)                 Node 2 (10.0.0.20)
  ┌─────────────────┐              ┌─────────────────┐
  │ cilium-agent     │              │ cilium-agent     │
  │ wg0 (WireGuard)  │   加密隧道    │ wg0 (WireGuard)  │
  │ IP: 10.10.0.1    │◄────────────►│ IP: 10.10.0.2    │
  └─────────────────┘              └─────────────────┘

  Pod 流量：
    Pod A (10.244.1.5)
    → cilium_host
    → wg0 加密（ChaCha20）
    → 物理网络
    → 目标节点 wg0 解密
    → Pod B

  启用：
    cilium install --set encryption.enabled=true --set encryption.type=wireguard

  性能损失：
    WireGuard：~5-10% 性能下降（加密解密）
    但安全性大幅提升
```

---

## 四、控制面（K8s CRD）

### 4.1 CRD 资源总览

```text
Cilium 使用 K8s CRD 作为控制面：

  核心 CRD：
    - CiliumNode        每节点状态
    - CiliumIdentity    安全身份
    - CiliumClusterwideNetworkPolicy
    - CiliumNetworkPolicy
    - CiliumClusterwideEnvoyConfig
    - CiliumEnvoyConfig

  辅助 CRD：
    - CiliumLocalRedirectPolicy
    - CiliumL2Policy
    - CiliumEgressGatewayPolicy
    - CiliumBGPPolicy
    - 等等
```

### 4.2 NetworkPolicy 完整支持

```yaml
# K8s 标准 NetworkPolicy（完整支持）
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: web-netpol
  namespace: production
spec:
  podSelector:
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
        - namespaceSelector:
            matchExpressions:
              - key: name
                operator: In
                values: ["production"]
      ports:
        - protocol: TCP
          port: 80
  egress:
    - to:
        - ipBlock:
            cidr: 10.0.0.0/8
      ports:
        - protocol: TCP
          port: 5432

---
# Cilium 扩展 CRD（支持 L7 策略）
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: api-l7-policy
  namespace: production
spec:
  endpointSelector:
    matchLabels:
      io.kubernetes.pod.namespace: production
      app: api
  ingress:
    - fromEndpoints:
        - matchLabels:
            app: web
      toPorts:
        - ports:
            - port: "8080"
              protocol: TCP
          rules:
            http:
              - method: "GET"
                path: "/api/v1/.*"
```

### 4.3 ClusterwideNetworkPolicy

```yaml
# 全局 NetworkPolicy（跨命名空间）
apiVersion: cilium.io/v2
kind: CiliumClusterwideNetworkPolicy
metadata:
  name: default-deny-ingress
spec:
  endpointSelector:
    matchLabels:
      app: web
  ingress:
    - fromEntities:
        - cluster
```

---

## 五、关键技术原理

### 5.1 eBPF 基础

```text
eBPF（Extended Berkeley Packet Filter）：

  ┌─────────────────────────────────────────┐
  │  用户态                                │
  │  ┌────────────────────┐               │
  │  │  cilium-agent       │               │
  │  │  (Go 程序)         │               │
  │  └────────┬───────────┘               │
  │           │ bpf() 系统调用               │
  └───────────┼─────────────────────────────┘
              ↓
  ┌─────────────────────────────────────────┐
  │  内核态                                │
  │  ┌─────────────────────────────────┐  │
  │  │  eBPF 验证器（安全性检查）         │  │
  │  └─────────────┬───────────────────┘  │
  │                ↓                        │
  │  ┌─────────────────────────────────┐  │
  │  │  eBPF JIT 编译器                │  │
  │  └─────────────┬───────────────────┘  │
  │                ↓                        │
  │  ┌─────────────────────────────────┐  │
  │  │  eBPF 程序（原生机器码）          │  │
  │  │  - bpf_lxc（容器网络）           │  │
  │  │  - bpf_sock_conn（socket）       │  │
  │  │  - bpf_xdp（网卡驱动）           │  │
  │  └─────────────────────────────────┘  │
  │                                          │
  │  eBPF Maps（共享数据）：                │
  │  - BPF_MAP_TYPE_HASH                   │
  │  - BPF_MAP_TYPE_ARRAY                  │
  │  - LRU 自动淘汰                         │
  └──────────────────────────────────────────┘

  eBPF 优势：
    - 内核态执行（无上下文切换）
    - JIT 编译（接近原生性能）
    - 验证器保证安全性
    - Map 提供共享数据
    - 几乎零拷贝
```

### 5.2 eBPF Map 数据结构

```text
Cilium 使用的核心 eBPF Maps：

  ┌────────────────────────────────────────┐
  │  cilium_lb4_map_v2                       │
  │  - 类型：BPF_MAP_TYPE_HASH              │
  │  - 用途：Service 负载均衡               │
  │  - Key：IP + Port                        │
  │  - Value：后端 Pod 列表                │
  └────────────────────────────────────────┘

  ┌────────────────────────────────────────┐
  │  cilium_policy_map                       │
  │  - 类型：BPF_MAP_TYPE_HASH              │
  │  - 用途：NetworkPolicy 决策             │
  │  - Key：身份 + 端口                      │
  │  - Value：Allow/Deny                     │
  └────────────────────────────────────────┘

  ┌────────────────────────────────────────┐
  │  cilium_ct4_global                       │
  │  - 类型：BPF_MAP_TYPE_HASH              │
  │  - 用途：连接跟踪（替代 conntrack）    │
  │  - Key：四元组（src/dst ip/port）         │
  │  - Value：连接状态                       │
  └────────────────────────────────────────┘

  ┌────────────────────────────────────────┐
  │  cilium_ipcache                          │
  │  - 类型：BPF_MAP_TYPE_LRU_HASH          │
  │  - 用途：IP → Identity 映射            │
  │  - Key：Pod IP                          │
  │  - Value：Security Identity              │
  └────────────────────────────────────────┘

  ┌────────────────────────────────────────┐
  │  cilium_sockmap                          │
  │  - 类型：BPF_MAP_TYPE_HASH              │
  │  - 用途：socket cookie（加速重定向）    │
  └────────────────────────────────────────┘
```

### 5.3 Cilium Identity 机制

```text
Cilium 使用基于标签的 Identity（区别于传统 IP-based）：

  K8s 标签：
    app=web, tier=frontend, env=prod

  ↓ 自动生成

  Cilium Identity（数字）：
    Identity: 12345

  策略匹配：
    fromEndpoints:
      - matchLabels:
          app: api
    # 自动转换为
    fromRequires:
      - identities: [67890]  # app=api 的 Identity

  优势：
    - Identity 在集群内全局唯一
    - Pod IP 变化不影响策略（基于身份）
    - 比 iptables IP 匹配更高效
```

### 5.4 Hubble 可观测性原理

```text
Hubble 架构：

  ┌────────────────────────────────────────────────┐
  │  Pod 内应用（发送 HTTP 请求）                  │
  └─────────────────┬──────────────────────────────┘
                    │
                    ▼
  ┌────────────────────────────────────────────────┐
  │  eBPF 钩子（cilium_monitor）                   │
  │  - 拦截 socket 操作                            │
  │  - 提取五元组 + 应用层信息                    │
  │  - 推送到 perf event ring buffer             │
  └─────────────────┬──────────────────────────────┘
                    │
                    ▼
  ┌────────────────────────────────────────────────┐
  │  cilium-agent（hubble server）                 │
  │  - 读取 perf events                           │
  │  - 解析为 Flow log                            │
  │  - 通过 gRPC 暴露                            │
  └─────────────────┬──────────────────────────────┘
                    │
                    ▼
  ┌────────────────────────────────────────────────┐
  │  Hubble Relay（聚合器，可选）                  │
  │  - 聚合多节点 Flow                            │
  │  - 提供全局视图                                │
  └─────────────────┬──────────────────────────────┘
                    │
                    ▼
  ┌────────────────────────────────────────────────┐
  │  Hubble UI / Hubble CLI                       │
  │  - 服务地图                                    │
  │  - Flow 列表（按 namespace/service 过滤）    │
  │  - HTTP/gRPC 可见性                          │
  │  - DNS 查询记录                              │
  └────────────────────────────────────────────────┘
```

---

## 五点五、请求通信流程详解

### 5.1 同节点 Pod-to-Pod 通信（eBPF sock_ops）

```text
场景：Node 1 上 Pod A (10.244.1.5) 与 Pod B (10.244.1.8) 通信

  Node 1
  ┌─────────────────────────────────────────────────────────────┐
  │                                                              │
  │  Pod A (10.244.1.5)              Pod B (10.244.1.8)         │
  │  ┌────────────────┐                ┌────────────────┐      │
  │  │  app 进程       │                │  app 进程       │      │
  │  └────────┬───────┘                └────────▲───────┘      │
  │           │                                  │              │
  │  ┌────────▼───────┐                ┌────────┴───────┐      │
  │  │ eth0           │                │ eth0           │      │
  │  └────────┬───────┘                └────────▲───────┘      │
  │           │                                  │              │
  │           ▼                                  │              │
  │  ┌───────────────┐                  ┌─────────┴────────┐   │
  │  │ lxcXXX (veth) │                  │  lxcYYY (veth) │   │
  │  └───────┬───────┘                  └─────────▲────────┘   │
  │          │                                   │             │
  │          └─────────┬─────────────────────────┘             │
  │                    │                                       │
  │            ┌───────▼───────┐                               │
  │            │  lxcBridge   │ ← 同节点二层桥              │
  │            └───────────────┘                               │
  │                                                              │
  └─────────────────────────────────────────────────────────────┘

  详细流程（eBPF 路径）：

  1. Pod A 应用发起 send() 系统调用
     - 数据包进入 socket 层

  2. eBPF sock_ops 钩子触发（内核态）
     - 拦截 socket 操作
     - 检查目的 IP 是否在同一节点
     - 发现 10.244.1.8 在同一节点
     - 决策：无需经过 cilium_host/veth

  3. eBPF sk_lookup 钩子（内核态）
     - 查询路由表（eBPF Map）
     - 找到目的 Pod 的 veth 接口

  4. eBPF redirect 钩子
     - 直接重定向 socket 到目标 veth
     - 完全跳过 Host 网络栈
     - 性能：跳过整个 Host TCP/IP 协议栈

  5. 数据包通过 veth 到达 Pod B
     - lxcXXX → lxcYYY（同一节点）
     - 内核态直接转发

  6. Pod B 接收
     - Pod B 应用进程收到数据

  关键优势：
    - 完全在内核态执行（无用户态切换）
    - 跳过 Host 网络协议栈（最大优化）
    - 延迟：~5μs（业界最快）
    - 不需要 iptables（eBPF 替代）
    - 不需要 conntrack（eBPF Map 替代）

  eBPF 与 iptables 对比：
    iptables 路径：
      Pod A → veth → cbr0 → iptables → caliXXXX → ... → Pod B
      （3-5 个 iptables 链匹配，每个 ~5μs）

    eBPF 路径：
      Pod A → sock_ops 拦截 → sk_lookup 查路由 → redirect 直接转发 → Pod B
      （2 个 eBPF 程序执行，每个 ~1μs）
```

### 5.2 跨节点 Pod-to-Pod 通信（eBPF XDP / TC）

```text
场景：Node 1 上 Pod A (10.244.1.5) 发包到 Node 2 上 Pod B (10.244.2.8)

  Node 1 (10.0.0.10)                         Node 2 (10.0.0.20)
  ┌──────────────────────────┐                ┌──────────────────────────┐
  │  Pod A 10.244.1.5         │                │  Pod B 10.244.2.8         │
  │  ┌────────────────┐      │                │  ┌────────────────┐      │
  │  │  app 进程       │      │                │  │  app 进程       │      │
  │  └────────┬───────┘      │                │  └────────▲───────┘      │
  │           │                    │                       │              │
  │  ┌────────▼───────┐      │                │  ┌────────┴───────┐      │
  │  │ eth0           │      │                │  │ eth0           │      │
  │  └────────┬───────┘      │                │  └────────▲───────┘      │
  │           │                    │                       │              │
  │           ▼                    │                       │              │
  │  ┌────────────────────┐  │                │  ┌────────────────────┐  │
  │  │ cilium_host       │  │                │  │ cilium_host       │  │
  │  │ (eBPF 接管)        │  │                │  │ (eBPF 接管)        │  │
  │  └────────┬───────────┘  │                │  └────────▲───────────┘  │
  │           │                    │                       │              │
  │  ┌────────▼───────────┐  │                │  ┌────────┴───────────┐  │
  │  │ eth0 (物理网卡)   │──┼────────────────┼──│ eth0 (物理网卡)   │  │
  │  │ 10.0.0.10         │  │   Overlay      │  │ 10.0.0.20         │  │
  │  └────────────────────┘  │   (VXLAN/Geneve)  └────────────────────┘  │
  └──────────────────────────┘                └──────────────────────────┘

  详细流程（eBPF Overlay 路径）：

  Pod A 发送包：
    1. Pod A 应用 → send() 系统调用
    2. eBPF sock_ops 钩子（内核态）
       - 检查目的 IP 10.244.2.8
       - 查询 eBPF Map（cilium_ipcache）
       - 找到目的节点 ID = 2
    3. eBPF sk_lookup 钩子
       - 查询 eBPF Map（cilium_lb4）
       - 标记为远程节点（需要 Overlay）
    4. 数据包通过 veth 到达 cilium_host

  cilium_host 上 eBPF 处理：
    5. TC ingress 钩子（eBPF）
       - 数据包进入 cilium_host
       - eBPF 程序 bpf_overlay 触发
    6. cilium-agent 检查 Overlay 配置
       - 判断是否需要 VXLAN 封装
       - Overlay 网络（如 ClusterwideCIDR）
    7. eBPF 注入 VXLAN 封装
       - 原始包：[10.244.1.5 → 10.244.2.8]
       - 封装后：[外层 IP: 10.0.0.10 → 10.0.0.20, UDP, VXLAN, 内层包]
    8. 封装包从 eth0 发出

  物理网络传输：
    9. eth0 发送 UDP 包
       物理交换机/路由器
       到达 Node 2 eth0

  Node 2 处理：
    10. eth0 接收 UDP 包
        TC egress 钩子（eBPF）
    11. eBPF 解封装
        - 去掉外层 UDP/IP
        - 提取内层 IP 包
    12. eBPF 查路由表
        - 10.244.2.0/24 → cilium_host（本地）
    13. 数据包转发到 cilium_host
    14. eBPF TC egress 钩子
        - 查询 cilium_ipcache
        - 找到目的 Pod 的 veth 接口
    15. 数据包通过 veth 到达 Pod B

  Pod B 接收：
    16. Pod B 应用进程收到数据
        完成跨节点通信

  延迟分析：
    - sock_ops 拦截：~1μs
    - eBPF Map 查询：~0.5μs/次
    - TC ingress：~1μs
    - TC egress：~1μs
    - VXLAN 封装：~5μs
    - 物理网络：1-10ms
    - 总延迟：~15-25μs（不含物理网络）

  与 Flannel VXLAN 对比：
    Flannel 用户态（flanneld）：~50-100μs
    Cilium eBPF（内核态）：~10-20μs
    性能提升：3-5 倍
```

### 5.3 eBPF 钩子点详解

```text
Cilium 使用的关键 eBPF 钩子点：

  ┌────────────────────────────────────────────────┐
  │  eBPF 钩子类型             用途                  │
  ├────────────────────────────────────────────────┤
  │  XDP（eXpress Data Path）网卡驱动入口          │
  │  - 在驱动层处理数据包                        │
  │  - 最早的处理点                                │
  │  - 性能最优                                    │
  │  - Cilium 用于：Service LB（XDP 模式）        │
  ├────────────────────────────────────────────────┤
  │  TC（Traffic Control）流量控制                │
  │  - ingress：进入网卡                          │
  │  - egress：离开网卡                          │
  │  - Cilium 用于：NetworkPolicy、Overlay       │
  ├────────────────────────────────────────────────┤
  │  Socket Layer                                │
  │  - sock_ops：socket 操作                     │
  │  - Cilium 用于：connect、sendmsg 重定向      │
  ├────────────────────────────────────────────────┤
  │  kprobe                                        │
  │  - 内核函数入口                                │
  │  - Cilium 用于：高级监控                       │
  ├────────────────────────────────────────────────┤
  │  cgroup                                        │
  │  - cgroup v2 hookpoint                        │
  │  - Cilium 用于：进程级监控                     │
  └────────────────────────────────────────────────┘

  eBPF 数据包处理流程：

  网卡驱动
       │ XDP 钩子
       ▼
  ┌─────────────────────────┐
  │  bpf_xdp（XDP 程序）    │ ← 最快路径
  │  - 转发 / DROP           │
  │  - LB                    │
  └──────────┬──────────────┘
             │
             ▼
  ┌─────────────────────────┐
  │  TC ingress              │ ← 网络栈入口
  │  - bpf_lxc（Pod 流量）  │
  │  - calico 策略检查       │
  └──────────┬──────────────┘
             │
             ▼
  ┌─────────────────────────┐
  │  IP 路由                │
  └──────────┬──────────────┘
             │
             ▼
  ┌─────────────────────────┐
  │  TC egress               │ ← 网络栈出口
  │  - bpf_lxc              │
  │  - 封装 / 路由           │
  └──────────┬──────────────┘
             │
             ▼
  网卡驱动
```

### 5.4 Service 流量完整路径（eBPF）

```text
Service ClusterIP 完整路径（eBPF）：

  ┌──────────────────────────────────────────────────┐
  │  Client Pod 应用                                │
  │  curl http://my-service:80                       │
  └────────────────────┬─────────────────────────────┘
                       │ 系统调用
                       ▼
  ┌──────────────────────────────────────────────────┐
  │  eBPF socket 层（sock_ops）                      │
  │  - 拦截 connect()、sendmsg()                   │
  │  - 查询 cilium_lb4 Map                           │
  │  - 找到 Service → 后端 Pod 映射                 │
  │  - 选择后端 Pod（负载均衡算法）                │
  │  - 重定向 socket 到后端 Pod                     │
  └────────────────────┬─────────────────────────────┘
                       │
                       ▼
  ┌──────────────────────────────────────────────────┐
  │  eBPF TC egress（Pod 出口）                      │
  │  - 应用 NetworkPolicy                          │
  │  - 检查源 IP 和目的 IP                          │
  └────────────────────┬─────────────────────────────┘
                       │
                       ▼
  ┌──────────────────────────────────────────────────┐
  │  直接转发到后端 Pod veth（不经 Host 协议栈）  │
  └──────────────────────────────────────────────────┘

  eBPF Service LB 关键优势：
    - 传统 iptables 需要遍历所有规则
    - eBPF Map 哈希查找 O(1)
    - 1000 个 Service 时性能差异巨大
    - iptables：~50μs P99（1000+ Service）
    - eBPF：~5μs P99（10000+ Service）
```

### 5.5 跨节点通信 vs 同节点通信对比

```text
Cilium 两种通信路径对比：

  ┌─────────────────┬──────────────────┬──────────────────┐
  │  维度          │  同节点          │  跨节点          │
  ├─────────────────┼──────────────────┼──────────────────┤
  │  钩子点        │  sock_ops        │  TC ingress/     │
  │                 │                  │  egress          │
  │  路径          │  Pod→veth→       │  Pod→veth→       │
  │                 │  sock_ops 拦截   │  cilium_host→   │
  │                 │  →直接转发      │  Overlay 封装→   │
  │                 │  Pod B veth      │  物理网络→       │
  │                 │                  │  Node 2→解封装→ │
  │                 │                  │  Pod B veth      │
  │  Host 网络栈   │  跳过            │  经过            │
  │  iptables      │  不需要          │  通过 TC eBPF    │
  │  conntrack     │  eBPF Map 替代   │  eBPF Map 替代   │
  │  封装          │  无              │  VXLAN/Geneve    │
  │  性能开销      │  ~5μs          │  ~15-25μs       │
  │  物理网络      │  不经过          │  经过            │
  └─────────────────┴──────────────────┴──────────────────┘
```

### 5.6 Cilium Hubble 完整观测路径

```text
Cilium Hubble 观测的数据流：

  Pod A 应用
       │ 系统调用
       ▼
  eBPF cilium_monitor 钩子
       │ 拦截 socket 操作
       ▼
  ┌─────────────────────────────────────────┐
  │  eBPF 程序（per-CPU Map）              │
  │  - 提取五元组（src/dst ip/port）      │
  │  - 应用层协议解析（HTTP/gRPC）        │
  │  - 写入 perf event ring buffer        │
  └────────────────┬────────────────────────┘
                   │
                   ▼
  ┌─────────────────────────────────────────┐
  │  cilium-agent（Hubble Server）         │
  │  - 订阅 perf events                    │
  │  - 解析为 Flow log                      │
  │  - 通过 gRPC 暴露                      │
  └────────────────┬────────────────────────┘
                   │
                   ▼
  ┌─────────────────────────────────────────┐
  │  Hubble Relay（可选聚合器）            │
  │  - 聚合多 cilium-agent                │
  │  - 提供全局网络视图                    │
  └────────────────┬────────────────────────┘
                   │
                   ▼
  ┌─────────────────────────────────────────┐
  │  Hubble UI / Hubble CLI                  │
  │  - Web 界面                              │
  │  - 服务地图                              │
  │  - Flow 列表                              │
  │  - HTTP/gRPC 详情                        │
  │  - DNS 记录                              │
  └─────────────────────────────────────────┘

  Hubble 关键功能：
    - 实时 L3/L4/L7 流量可视化
    - 服务依赖图
    - NetworkPolicy 决策日志
    - TCP 重传统计
    - DNS 查询记录
```

### 5.7 故障排查技巧

```bash
# 1. 查看 Cilium 整体状态
cilium status

# 2. 查看 eBPF Map
cilium bpf ct list | head
cilium bpf lb list | head
cilium bpf ipcache list | head

# 3. 查看 Hubble 状态
hubble status

# 4. 查看实时流量
hubble observe

# 5. 查看特定 Pod 流量
hubble observe --namespace production --pod my-app

# 6. 查看 L7 HTTP 流量
hubble observe --protocol http

# 7. 查看 DNS 查询
hubble observe --protocol dns

# 8. 查看 NetworkPolicy 决策
hubble observe --verdict DROPPED

# 9. 查看端点信息
kubectl exec -n kube-system <cilium-pod> -- cilium endpoint list

# 10. 查看服务地图
hubble ui

# 11. 抓包分析（高级）
mount -t bpf bpf /sys/fs/bpf /sys/fs/bpf
ls /sys/fs/bpf/tc/globals/cilium/
```

---

## 六、关键特性

### 6.1 eBPF 数据面能力

| 能力 | 支持情况 | 说明 |
|------|---------|------|
| 容器网络 | ✅ | 替代 bridge/cni |
| Service LB | ✅ | 替代 kube-proxy |
| NetworkPolicy L3/L4 | ✅ | K8s 标准 + 扩展 |
| NetworkPolicy L7 | ✅ | HTTP/gRPC/Kafka |
| 加密通信 | ✅ | WireGuard |
| 主机网络 | ✅ | HostPort 等 |
| 多集群 | ✅ | ClusterMesh |
| 双栈 IPv4/IPv6 | ✅ | 原生支持 |
| 替代 CNI | ✅ | 完全替代 |
| 替代 kube-proxy | ✅ | 推荐 |

### 6.2 可观测性能力

```text
Hubble 可观测的功能：

  ✅ 实时服务地图
  ✅ L3/L4 Flow 记录
  ✅ L7 协议解析（HTTP/gRPC/Kafka/MySQL/Redis/DNS）
  ✅ DNS 查询记录
  ✅ TCP 重传统计
  ✅ 策略决策日志
  ✅ 网络策略可视化
  ✅ 跨节点 Flow 聚合
  ✅ Hubble UI（Web 界面）
  ✅ Hubble CLI（命令行）
  ✅ Prometheus 指标集成
  ✅ Grafana Dashboard
```

### 6.3 资源占用

```text
Cilium 资源占用：

  ┌──────────────────┬──────────────┐
  │  场景            │  资源         │
  ├──────────────────┼──────────────┤
  │  小集群          │  CPU 100m    │
  │  (100 Pods)    │  内存 256MB   │
  ├──────────────────┼──────────────┤
  │  中集群          │  CPU 500m    │
  │  (1000 Pods)   │  内存 1GB     │
  ├──────────────────┼──────────────┤
  │  大集群          │  CPU 2-4     │
  │  (10000 Pods)  │  内存 4-8GB  │
  └──────────────────┴──────────────┘

  BPF Maps 占内存大头
  eBPF 程序本身很小（KB 级）
```

---

## 七、配置与部署

### 7.1 Helm 部署（推荐）

```bash
# 1. 添加 Helm 仓库
helm repo add cilium https://helm.cilium.io/

# 2. 安装（K3s 推荐参数）
helm install cilium cilium/cilium \
  --namespace kube-system \
  --set kubeProxyReplacement=true \
  --set hubble.enabled=true \
  --set hubble.relay.enabled=true \
  --set hubble.ui.enabled=true \
  --set ipam.mode=kubernetes \
  --set bpf.masquerade=true

# 3. K8s + Cilium 推荐参数
helm install cilium cilium/cilium \
  --namespace kube-system \
  --set kubeProxyReplacement=true \
  --set hubble.enabled=true \
  --set image.pullPolicy=IfNotPresent \
  --set operator.rollOutPods=true

# 4. 验证
kubectl get pods -n kube-system -l k8s-app=cilium
cilium status
```

### 7.2 K3s 一键启用

```bash
# K3s 安装时启用 Cilium
curl -sfL https://get.k3s.io | sh -s - \
  --flannel-backend=none \
  --disable-network-policy \
  --disable=traefik \
  --write-kubeconfig-mode=6443

# Cilium 通过 Helm 安装
helm install cilium cilium/cilium \
  --namespace kube-system \
  --set kubeProxyReplacement=true \
  --set k8sServiceHost=127.0.0.1 \
  --set k8sServicePort=6443
```

### 7.3 关键 Helm 参数

```yaml
# values.yaml
kubeProxyReplacement: true           # 替代 kube-proxy

hubble:
  enabled: true                       # 启用 Hubble
  relay:
    enabled: true                     # 启用 Relay（聚合）
  ui:
    enabled: true                     # 启用 UI
  metrics:
    enabled: true                     # 启用 Prometheus 指标

ipam:
  mode: kubernetes                    # K8s IPAM

bpf:
  masquerade: true                    # BPF 实现 SNAT
  clockProbe: true                    # 时钟校验

encryption:
  enabled: true                       # WireGuard 加密
  type: wireguard

l7Proxy: true                        # 启用 L7 代理
```

### 7.4 验证部署

```bash
# 1. 查看 Cilium 状态
cilium status

# 2. 查看 eBPF Map
cilium bpf ct list | head
cilium bpf lb list | head

# 3. 查看 Hubble 状态
hubble status

# 4. 查看服务地图
hubble observe --namespace kube-system

# 5. 性能验证
cilium connectivity test
```

---

## 八、性能数据

### 8.1 延迟基准

```text
Cilium 性能数据（基准测试）：

  ┌──────────────────────┬──────────────┐
  │  场景                 │  延迟         │
  ├──────────────────────┼──────────────┤
  │  同节点 Pod 通信      │  ~5μs       │
  │  跨节点 Pod 通信      │  ~25μs      │
  │  Service LB（100 service）│  ~3μs  │
  │  Service LB（10000 service）│ ~10μs│
  │  NetworkPolicy 匹配   │  ~1-2μs    │
  │  XDP 负载均衡          │  ~1μs      │
  └──────────────────────┴──────────────┘

  对比：
    Flannel vxlan：~70μs 跨节点
    Calico iptables：~50μs 跨节点
    Calico eBPF：~30μs 跨节点
    Cilium eBPF：~25μs 跨节点（最快）

  Service LB 大规模对比（10000 service）：
    iptables：~50μs P99（性能下降）
    IPVS：~10μs P99
    Cilium eBPF：~3μs P99（无下降）
```

### 8.2 吞吐量

```text
iperf3 跨节点测试（10 Gbps 网络）：

  ┌──────────────────────┬──────────────┐
  │  CNI                 │  吞吐         │
  ├──────────────────────┼──────────────┤
  │  Flannel vxlan       │  9.0 Gbps    │
  │  Calico vxlan        │  9.0 Gbps    │
  │  Calico 无封装       │  9.5 Gbps    │
  │  Cilium eBPF         │  9.4 Gbps    │
  └──────────────────────┴──────────────┘

  Cilium 几乎无性能损失
```

### 8.3 Policy 性能

```text
NetworkPolicy 数量对性能影响：

  ┌──────────────────┬──────────────────┐
  │  Policy 数        │  Cilium eBPF 延迟 │
  ├──────────────────┼──────────────────┤
  │  100              │  ~2μs            │
  │  1,000            │  ~3μs            │
  │  10,000           │  ~10μs           │
  │  50,000           │  ~30μs           │
  └──────────────────┴──────────────────┘

  对比 iptables：
    10,000 Policy：~50-100μs 延迟
    Cilium 性能优势：10x
```

---

## 九、适用场景

### 9.1 强烈推荐

```text
1. 现代生产集群
   - 内核 ≥ 5.10
   - 追求最佳性能

2. 大规模集群
   - 1000+ 节点
   - service 数万

3. 需要可观测性
   - Hubble 业界最强
   - 服务地图 + Flow + L7

4. 服务网格场景
   - Cilium Service Mesh
   - 替代 Istio（更轻量）

5. 高频策略场景
   - 大量 NetworkPolicy
   - eBPF 比 iptables 快 10x

6. 多集群管理
   - ClusterMesh
   - 跨集群 NetworkPolicy
```

### 9.2 不推荐

```text
1. 老内核（< 4.19）
   - eBPF 数据面不能用
   - 只能降级到 iptables

2. 学习 K8s 网络
   - 概念复杂
   - 推荐 Flannel

3. 简单小集群
   - 配置复杂
   - 推荐 Flannel

4. 资源极度受限
   - BPF Maps 占内存
   - 推荐 Flannel
```

---

## 十、核心要点速记

### Cilium 一句话定位

```text
Cilium = eBPF-based CNI
性能最强、可观测最好、L7 策略
替换 kube-proxy、Hubble 可观测业界第一
现代生产集群首选（内核 5.10+）
```

### 架构速记

```text
组件：
  cilium-agent（每节点 DaemonSet）
  CRD（CiliumNetworkPolicy 等）
  Hubble（可观测）
  eBPF Maps（共享数据）

数据流：
  Pod → socket → eBPF 钩子（sock_ops）
  → eBPF Map 查询（O(1) 哈希）
  → cilium_host → 物理网络 → 目标节点
```

### Cilium vs 其他 CNI 速记

```text
Flannel：极简，无策略
Calico：生产最稳，NetworkPolicy 完整
Cilium：性能最强，可观测最好，L7 策略
```

### 一句话总结

```text
Cilium = K8s 网络的未来
eBPF 数据面 = 性能与可观测性兼得
替换 kube-proxy = 简化部署
Hubble = 业界最强可观测性
```

### 关键文件

```bash
# Cilium Agent 配置
kubectl -n kube-system get cm cilium-config -o yaml

# eBPF Map
ls /sys/fs/bpf/tc/globals/cilium/

# Hubble 状态
hubble status

# Cilium 状态
cilium status

# Hubble UI 访问
kubectl port-forward -n kube-system svc/hubble-ui 12000:80
```

---

## 十一、参考

```text
- Cilium 官方文档: https://docs.cilium.io/
- Cilium GitHub: https://github.com/cilium/cilium
- eBPF 官方: https://ebpf.io/
- Cilium 培训: https://github.com/cilium/cilium-cli
- Hubble 文档: https://docs.cilium.io/en/stable/gettingstarted/hubble/
- CNCF 项目: https://www.cncf.io/projects/cilium/
- Isovalent 企业版: https://www.isovalent.com/
- 对比文档: ../对比.md
```
