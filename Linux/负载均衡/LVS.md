# LVS

## 一、LVS 概述

### 什么是 LVS

**LVS**(Linux Virtual Server):基于 Linux 内核的 **L4 高性能负载均衡**

- 章文嵩博士 1998 年发起,中国国家项目
- GPL 协议,集成到 Linux 内核主分支
- 工作在内核态(`ip_vs` 模块),性能接近硬件 LB
- 占据国内 L4 LB 大半江山
- 关键口号:**"让 Linux 成为高性能 L4 LB"**

### 核心组件

| 组件                  | 说明                                |
|-----------------------|-------------------------------------|
| **ip_vs**             | 内核模块,核心调度器                 |
| **ipvsadm**           | 用户态管理工具                       |
| **keepalived**        | 健康检查 + 故障转移 + 配置文件管理    |
| **ldirectord**        | 健康检查(Heartbeat 配套)             |
| **piranha**           | Red Hat 的 LVS GUI 管理工具          |
| **ipvs virtual-server** | 内核态虚拟服务条目                |
| **ip_vs_***           | 各模式模块(NAT / DR / Tunnel / FULLNAT)|

### LVS vs 其他 LB

| 维度        | LVS                | HAProxy           | Nginx(stream) | F5 / A10          |
|-------------|--------------------|-------------------|---------------|-------------------|
| 模式        | L4 透传            | L4 + L7           | L4            | L4 + L7           |
| 实现        | **内核态**         | 用户态            | 用户态        | 硬件              |
| 性能        | **极高**(线速)     | 极高              | 高            | 极高              |
| 健康检查    | 弱(需外部 keepalived)| **强**           | 弱            | 强                |
| 配置        | ipvsadm 命令       | 配置文件          | 配置文件      | 配置 / GUI       |
| 灵活性      | 弱                 | 强                | 中            | **强**            |
| 适用        | 高 QPS L4 入口      | L4/L7 LB          | 轻量 L4       | 商业级入口        |

---

## 二、架构与运行机制

### 1. 整体架构

```text
Client
   │
   ▼
┌──────────────────────┐
│ Director(LVS LB)     │
│  ┌────────────────┐  │
│  │ ip_vs (内核态)  │  │   ← 调度 + 包转发
│  │ ipvsadm        │  │   ← 用户态配置
│  └────────────────┘  │
│  keepalived (HA)     │   ← 健康检查 + failover
└──────────────────────┘
   │           │
   ▼           ▼
Real Server 1   Real Server 2
```

### 2. 模块加载

```bash
# 检查模块
lsmod | grep ip_vs

# 加载内核模块
modprobe ip_vs
modprobe ip_vs_rr        # 调度算法模块
modprobe ip_vs_wrr
modprobe ip_vs_lc
modprobe ip_vs_wlc
modprobe ip_vs_sh
modprobe ip_vs_dh
modprobe ip_vs_sed
modprobe ip_vs_nq

# DR 模式需要的内核参数
sysctl -w net.ipv4.conf.all.forwarding=1
sysctl -w net.ipv4.conf.lo.arp_ignore=1
sysctl -w net.ipv4.conf.lo.arp_announce=2
```

### 3. 三层结构

```text
用户态:
  ipvsadm / keepalived              ← 配置 + 管理
     │
     ▼ (netlink)
内核态:
  ip_vs (netfilter HOOK)            ← 调度 + 包处理
  ip_vs_rr / ip_vs_sh               ← 调度算法
  nf_conntrack (五元组)             ← 连接跟踪
     │
     ▼
TCP/IP 协议栈
```

### 4. 控制平面与数据平面

- **控制平面**:ipvsadm / keepalived 写入规则
- **数据平面**:内核 ip_vs 在 netfilter HOOK 处理包

### 5. 进程模型

**LVS 是内核态,无 Master / Worker 概念**:

- Linux 内核网络栈自动并发
- 多核机器上,软中断分担到多核
- 不需要进程管理

---

## 三、调度算法

### 1. 算法总览

```text
ip_vs 内置算法
├── rr        # 轮询(round-robin)
├── wrr       # 加权轮询
├── lc        # 最少连接
├── wlc       # 加权最少连接(默认推荐)
├── lblc      # 基于局部性的最少连接
├── lblcr     # 带复制的基于局部性的最少连接
├── dh        # 目标地址哈希
├── sh        # 源地址哈希(粘性会话)
├── sed       # 最短期望延迟
├── nq        # 永不排队
└── mh        # 多种哈希(基于目的地址)
```

### 2. 算法详解

| 算法 | 公式 / 逻辑 | 适用 |
|------|-------------|------|
| **rr**   | 顺序循环 | 同等性能 server |
| **wrr**  | 加权循环 | 异构 server |
| **lc**   | 选择 activeconn + inactiveconn 最小的 server | 长连接 |
| **wlc**  | `(activeconn + inactiveconn) / weight` 最小的 server | **生产默认推荐** |
| **sh**   | `hash(src_ip)` → 固定 server | 粘性会话 / 会话保持 |
| **dh**   | `hash(dst_ip)` → 固定 server | 缓存亲和(Web/CDN) |
| **lblc** | 优先同 IP 目标,否则 lc | 缓存代理 |
| **lblcr**| 同 IP 目标加权 lc | 缓存代理高级 |
| **sed**  | `(activeconn + 1) * 256 / weight` 最小 | 短任务 |
| **mq**   | 永不排队 + sed | 短任务 |
| **mh**   | 多目标地址哈希 | 多目标 IP 主机 |

### 3. 算法选择

```text
同等配置 short connection: rr
异构配置:                wrr / wlc
长连接 (mysql / ssh):     wlc / lc
粘性会话:                sh
缓存亲和:                dh / lblc
短任务高并发:            sed / nq
```

### 4. 配置示例

```bash
# 加权轮询
ipvsadm -A -t 192.168.1.100:80 -s wrr

# 加权最少连接
ipvsadm -A -t 192.168.1.100:80 -s wlc

# 源地址哈希(粘性会话)
ipvsadm -A -t 192.168.1.100:80 -s sh
```

---

## 四、工作模式

### 1. 模式总览

| 模式         | 缩写     | 复杂度 | 性能 | 网络要求 |
|--------------|----------|--------|------|----------|
| **NAT**      | MASQ     | 低     | 中   | Director 与 RS 同网段 |
| **DR**       | Direct Routing | 中 | **极高** | 同网段 |
| **Tunnel**   | TUN / IPIP | 高  | 极高 | RS 可跨网段 |
| **FULLNAT**  | FNAT      | 高     | 高   | RS 任意网段 |

---

### 2. NAT 模式(改 IP,回程经 Director)

#### 网络拓扑

```text
公网段 / 客户端侧                内网段
┌─────────────────┐        ┌──────────────────────────────┐
│  client         │        │  Director                    │
│  1.1.1.100      │──>──>──│  eth0: 1.1.1.1 (公网 / VIP) │
│  MAC: AA:AA:AA  │        │  eth1: 10.0.0.254 (内网 GW)  │
└─────────────────┘        └──────────────┬───────────────┘
                                         │
                          ┌──────────────┼──────────────┐
                          ▼                              ▼
                    ┌──────────┐                  ┌──────────┐
                    │ RS-1     │                  │ RS-2     │
                    │ 10.0.0.1 │                  │ 10.0.0.2 │
                    └──────────┘                  └──────────┘
                    (gateway = 10.0.0.254 = Director)
```

- 客户端访问 `VIP:80`(真实是 Director 的 eth0 = 1.1.1.1)
- RS 在内网,网关必须设为 Director(`10.0.0.254`)
- Director **双向 NAT**:进站改 dst,出站改 src

#### 入站数据包(逐字段变化)

```text
① 客户发出
   src MAC: AA:AA:AA                  (client 网卡)
   dst MAC: BB:BB:BB                  (Director eth0 MAC,由 ARP 得)
   src IP:  1.1.1.100                 (client 公网 IP)
   dst IP:  1.1.1.1                   (Director VIP / 80)
   src Port: 50000
   dst Port: 80

② Director 接收(网卡层)
   ✓ dst MAC 是自己,接收
   ✓ IP 层收到,进入 netfilter / ip_vs hook
   ✓ conntrack 创建新条目:
     proto=tcp  state=SYN
     tuple: (1.1.1.100:50000) ↔ (1.1.1.1:80)
     reply tuple: (10.0.0.1:80) ↔ (1.1.1.100:50000)
     ※ ip_vs 已选定 RS-1(10.0.0.1),把 NAT 信息记入 conntrack

③ Director 转发(改 dst IP)
   src MAC: BB:BB:BB                  (Director eth1 MAC)
   dst MAC: CC:CC:CC                  (RS-1 eth0 MAC,ARP 缓存)
   src IP:  1.1.1.100                 (不变 — 不替换 src,NAT 模式不改 src)
   dst IP:  10.0.0.1                  (改! 原本 1.1.1.1 → 10.0.0.1)
   src Port: 50000
   dst Port: 80
   ※ NAT 模式关键:dst IP 从 VIP(1.1.1.1)变成 RS IP(10.0.0.1)
   ※ src IP 不变,RS 看到的是真实 client IP

④ RS-1 接收
   ✓ dst MAC 是自己,接收
   ✓ dst IP 是 10.0.0.1(自己),接受
   ✓ RS 看到:client = 1.1.1.100(真实)
   ✓ RS 回包:
     src IP:  10.0.0.1
     dst IP:  1.1.1.100
     ※ 回包目标 client,网关是 10.0.0.254 → 必须经 Director

⑤ RS-1 回包经过 Director
   ※ RS 默认网关是 10.0.0.254(Director)
   src MAC: DD:DD:DD                  (RS-1 eth0)
   dst MAC: EE:EE:EE                  (Director eth1)
   src IP:  10.0.0.1
   dst IP:  1.1.1.100
   ※ Director 收到后,根据 conntrack 反向 NAT:
     src IP:  10.0.0.1 → 1.1.1.1
     (改 src IP = VIP,客户端以为是 VIP 回的)

⑥ Director 发出
   src MAC: BB:BB:BB                  (Director eth0)
   dst MAC: AA:AA:AA                  (client MAC)
   src IP:  1.1.1.1                   (改! 10.0.0.1 → 1.1.1.1 = VIP)
   dst IP:  1.1.1.100

⑦ client 收到
   ✓ 看到 src IP = 1.1.1.1(VIP),符合预期
```

#### conntrack 条目

```text
nf_conntrack:
  tuple_original: proto=TCP src=1.1.1.100:50000 dst=1.1.1.1:80
  tuple_reply:    proto=TCP src=10.0.0.1:80   dst=1.1.1.100:50000
  master: 已绑定到 ip_vs virtual service
```

#### 瓶颈与限制

- **Director 是双向流必经之路**:进出都过 Director → Director 是瓶颈
- **Director 出站带宽 = 入站带宽**(回程也过 Director)
- **RS 必须把网关设为 Director**(否则回程路由不通)
- **进出都跨网段**:从公网到内网再回公网,**两次跨网**

#### 配置

```bash
# Director
sysctl -w net.ipv4.ip_forward=1
ipvsadm -A -t 1.1.1.1:80 -s wrr
ipvsadm -a -t 1.1.1.1:80 -r 10.0.0.1:80 -m   # -m = MASQ(NAT)
ipvsadm -a -t 1.1.1.1:80 -r 10.0.0.2:80 -m

# RS
ip route add default via 10.0.0.254 dev eth0   # 关键:网关是 Director
```

#### 优缺点

| 优点 | 缺点 |
| ---- | ---- |
| 配置简单(Director 改 IP,RS 改网关) | Director 是瓶颈(双向流量) |
| RS 不需要特殊配置(关闭 ARP 等) | RS 必须在同一 L3 网段 |
| RS 看真实 client IP | 带宽放大问题(进出 2x) |

---

### 3. DR 模式(改 MAC,回程不经 Director,生产最常用)

#### 网络拓扑

```text
同一 L2 网段(关键!)
┌─────────────────┐
│  client         │
│  1.1.1.100      │──>──>──>──>──>──>─┐
│  MAC: AA:AA:AA  │                   │
└─────────────────┘                   ▼
                              ┌──────────────┐
                              │ Director     │
                              │ IP: 1.1.1.1  │
                              │ VIP: 1.1.1.1 │
                              │ MAC: BB:BB   │
                              └──────┬───────┘
                                     │ 改 MAC 转发
                       ┌─────────────┴─────────────┐
                       ▼                           ▼
                ┌──────────┐               ┌──────────┐
                │ RS-1     │               │ RS-2     │
                │ IP: 1.0.0.11│             │ IP: 1.0.0.12│
                │ VIP/lo: 1.1.1.1│           │ VIP/lo: 1.1.1.1│
                │ (lo 上配 VIP,|             │ (lo 上配 VIP,│
                │  不响应 ARP)│             │  不响应 ARP)│
                │ MAC: CC:CC │               │ MAC: DD:DD │
                └─────┬──────┘               └─────┬──────┘
                      │  回包(直接到 client,不经 Director)
                      └──────────┬─────────┘
                                 ▼
                              client (1.1.1.100)
```

#### 核心思想

```text
✦ Director 只改 dst MAC,不动 IP
✦ dst IP 始终是 VIP(1.1.1.1)
✦ RS 在 lo 上配置 VIP,收到 dst=VIP 的包
✦ RS 回包时 src IP = VIP,直接给 client(不经 Director)
```

#### 入站数据包(逐字段变化)

```text
① 客户发出
   src MAC: AA:AA:AA                  (client)
   dst MAC: BB:BB:BB                  (Director,ARP → 谁持有 VIP 谁回应)
   src IP:  1.1.1.100
   dst IP:  1.1.1.1                   (VIP)
   src Port: 50000
   dst Port: 80

   ※ 谁持有 VIP 回应 ARP?
     - Director 在 eth0 上配 VIP,所以 ARP 回应是 Director
     - RS 在 lo 上配 VIP,但抑制 ARP,不应答
     - 结果:dst MAC = Director

② Director 接收
   ✓ dst MAC 是自己,接收
   ✓ ip_vs hook 选定 RS-1
   ★ 只改 MAC,不改 IP:
   src MAC: BB:BB:BB                  (Director eth0)
   dst MAC: CC:CC:CC                  (RS-1,关键!)
   src IP:  1.1.1.100                 (不变)
   dst IP:  1.1.1.1                   (不变,仍是 VIP)
   src Port: 50000
   dst Port: 80

   ※ DR 关键:dst MAC 从 BB 改成 CC,dst IP 永远是 1.1.1.1

③ RS-1 接收
   ✓ dst MAC 是自己,接收
   ✓ dst IP = 1.1.1.1
     - 自己 lo 接口配置了 1.1.1.1
     - 接收 → 由 lo 接口处理
   ※ RS 看真实 client IP:src IP = 1.1.1.100

④ RS-1 处理并回包
   ※ RS 直接给 client(无需 Director)
   src MAC: CC:CC:CC                  (RS-1 eth0)
   dst MAC: AA:AA:AA                  (client MAC,ARP 缓存)
   src IP:  1.1.1.1                   (回包 src = VIP)
   dst IP:  1.1.1.100
   src Port: 80
   dst Port: 50000

⑤ client 收到
   ✓ src IP = 1.1.1.1(VIP),符合预期
   ✓ src MAC = CC:CC:CC(RS-1),正常
   ✦ 整个回程完全不经 Director
```

#### conntrack 条目

```text
nf_conntrack:
  tuple_original: proto=TCP src=1.1.1.100:50000 dst=1.1.1.1:80
  tuple_reply:    proto=TCP src=1.1.1.1:80      dst=1.1.1.100:50000
  ※ 注意 reply tuple 的 src = VIP(因为 RS 回包 src 是 VIP)
  ※ conntrack 状态会跟踪,但 Director 出站不查 conntrack
    (Director 转发只改 MAC,内核允许)
```

#### 为什么 Director 不是瓶颈

```text
DR 模式:
  - 入站:client → Director → RS(包改 MAC,走一次 Director)
  - 回站:RS → client(直接走 RS → client,不经过 Director)

NAT 模式:
  - 入站:client → Director → RS(改 IP,Director 处理)
  - 回站:RS → Director → client(Director 改 src IP,反向 NAT)

DR 的 Director 只处理入站流量,回程零开销
NAT 的 Director 进出都处理,带宽放大 2x
```

#### 为什么 Director 与 RS 必须在同一 L2

```text
DR 模式只改 MAC,不改 IP:
  - 包从 Director eth0 出,dst MAC = RS
  - 交换机查 MAC 表,二层转发到 RS
  - RS 必须与 Director 在同一二层广播域
  - 跨网段(路由器)就转发不到
```

#### 为什么 RS 在 lo 上配 VIP

```text
RS 收到的包 dst IP = VIP(1.1.1.1)
  - 如果 RS 自己的 IP 中没有 1.1.1.1,会被丢弃(找不到路由接收方)
  - 把 VIP 配在 lo 接口 → RS 的本地路由包含 1.1.1.1 → 接收
  - 但 lo 配置 VIP 必须配 lo,不配 eth0(否则 ARP 冲突)
```

#### 为什么必须抑制 ARP

```text
问题:
  - 如果 RS 在 eth0 配 VIP,会响应 ARP(谁持有 VIP 谁能 ARP 回应)
  - 那 client 首次 ARP 时会直接拿到 RS 的 MAC
  - 包根本到不了 Director → 调度失效

解决:
  - RS 上只把 VIP 配在 lo(loopback)
  - 抑制 lo 回应 ARP(arp_ignore=1,arp_announce=2)
  - 所有 ARP 回应走 eth0 上的真实 IP,而 eth0 不持有 VIP
  - 只有 Director 的 eth0 持有 VIP → Director 抢到 ARP 回应
```

#### 配置

```bash
# Director
ip addr add 1.1.1.1/32 dev eth0           # VIP 在物理网卡
ipvsadm -A -t 1.1.1.1:80 -s wrr
ipvsadm -a -t 1.1.1.1:80 -r 1.0.0.11:80 -g   # -g = Gateway(DR)
ipvsadm -a -t 1.1.1.1:80 -r 1.0.0.12:80 -g

# RS(每台)
ip addr add 1.1.1.1/32 dev lo              # VIP 在 loopback
sysctl -w net.ipv4.conf.lo.arp_ignore=1    # 不响应 lo 上的 ARP
sysctl -w net.ipv4.conf.lo.arp_announce=2
sysctl -w net.ipv4.conf.all.arp_ignore=1
sysctl -w net.ipv4.conf.all.arp_announce=2
```

#### 优缺点

| 优点 | 缺点 |
| ---- | ---- |
| Director 不是瓶颈(回程不经过) | 必须同 L2 网段 |
| RS 看真实 client IP | RS 需配置 ARP 抑制 + lo VIP |
| 性能接近线速 | 跨网段不行 |
| 配置一次,长期稳定 | Director RS 都要配 VIP |

---

### 4. Tunnel 模式(IPIP 隧道,跨网段)

#### 网络拓扑

```text
client                       Director                                 RS
1.1.1.100                    1.1.1.1 / 10.0.0.1                     1.0.0.11 / 10.1.0.1
  │                              │                                       │
  └────────► VIP 1.1.1.1 ────►  │                                       │
                                 │ IPIP 隧道(dst=10.1.0.1)              │
                                 │  内层 dst=VIP(1.1.1.1)               │
                                 │───────────────────────────────────► │
                                 │                                       │
                                 │   RS 解 IPIP 隧道,看到 dst=VIP        │
                                 │   RS lo 上配 VIP,接收                 │
                                 │                                       │
                                 │◄──────────────────────────────────────│
                                       (回包 src=VIP,直接给 client)
```

#### 核心思想

```text
✦ Director 把原始 IP 包整体作为负载,外面再套一层 IPIP 头
✦ 外层 dst IP = RS 的真实 IP(可跨网段)
✦ 内层 dst IP = VIP
✦ RS 解 IPIP 隧道,看到内层 dst=VIP,接受
✦ RS 回包同样封装 IPIP,直接回 client(不经 Director)
```

#### 入站数据包(逐字段变化)

```text
① 客户发出(普通 IP 包)
   外层 src IP: 1.1.1.100
   外层 dst IP: 1.1.1.1
   src Port: 50000
   dst Port: 80
   ... TCP payload ...

② Director 接收
   ✓ dst IP = VIP,ip_vs hook 选定 RS-1(10.1.0.1)
   ★ 包一层 IPIP 头:
   ┌────────────────────────────────────────┐
   │ IPIP 隧道包:                           │
   │   外层 src IP: 10.0.0.1   (Director)   │
   │   外层 dst IP: 10.1.0.1   (RS-1 真实 IP)│
   │   protocol: 4 (IP-in-IP)               │
   │   ┌──────────────────────────────────┐ │
   │   │ 内层(原始包):                   │ │
   │   │   src IP: 1.1.1.100 (client)    │ │
   │   │   dst IP: 1.1.1.1   (VIP)       │ │
   │   │   src Port: 50000               │ │
   │   │   dst Port: 80                  │ │
   │   │   ... TCP ...                   │ │
   │   └──────────────────────────────────┘ │
   └────────────────────────────────────────┘

   ※ IPIP 协议号 = 4
   ※ 外层 20 字节 IP 头 + 内层原 IP 包

③ 网络传输
   路由器看外层 dst = 10.1.0.1,跨网段转发
   最终到达 RS-1(10.1.0.1)

④ RS-1 接收 + 解 IPIP
   ✓ RS-1 内核收到协议号 4(IPIP)
   ✓ ip_tunnel 模块解封装,剥离外层头
   ✓ 看到内层 dst IP = 1.1.1.1(VIP)
   ✓ 自己 lo 上配了 1.1.1.1,接收
   ✓ RS 处理:看到 src IP = 1.1.1.100(真实 client)

⑤ RS-1 回包(同样 IPIP 隧道)
   ※ RS 也可以封装 IPIP 回包(主动回 client,但通常 RS 是直接回普通 IP)
   ※ 更常见:RS 解隧道后,用 lo 接口(src=VIP)直接给 client 回普通包
   src IP:  1.1.1.1
   dst IP:  1.1.1.100
   src Port: 80
   dst Port: 50000

⑥ client 收到
   ✓ src IP = VIP,正常
```

#### 为什么可以跨网段

```text
DR 模式只改 MAC → 必须同 L2
TUN 模式包一层 IP 头 → 路由器按外层 dst IP 转发 → 可跨网段(广域网)
```

#### 为什么 RS 需要 IPIP 模块

```text
RS 收到 protocol=4(IPIP)的包
  - 内核必须识别 IPIP 协议
  - 通过 modprobe ipip 加载 ip_tunnel 模块
  - 隧道接口(tunl0)上配 VIP
  - 内核自动解封装,内层包进入正常 TCP/IP 栈处理
```

#### 配置

```bash
# Director
modprobe ipip
ipvsadm -A -t 1.1.1.1:80 -s wrr
ipvsadm -a -t 1.1.1.1:80 -r 10.1.0.1:80 -i   # -i = TUN

# RS
modprobe ipip
ip tunnel add tunl0 mode ipip local 10.1.0.1
ip addr add 1.1.1.1/32 dev tunl0
sysctl -w net.ipv4.conf.tunl0.arp_ignore=1
sysctl -w net.ipv4.conf.tunl0.arp_announce=2
```

#### 优缺点

| 优点 | 缺点 |
| ---- | ---- |
| 可跨网段(广域网) | RS 必须支持 IPIP(几乎所有 Linux 都行) |
| 回程不经 Director | 包头开销(+20 字节 IPIP) |
| RS 看真实 client IP | 性能略低于 DR(封装解封装开销) |
| 跨机房 / CDN 场景 | RS 需公网 IP(否则单向隧道不通) |

---

### 5. FULLNAT 模式(双向 NAT,跨网段,阿里云专利)

#### 核心思想

```text
✦ NAT 模式只改 dst IP,src IP 不变
✦ FULLNAT 同时改 src IP 和 dst IP
   - src 改 → Director 内网 IP
   - dst 改 → RS IP
✦ RS 看到 src = Director(不是 client),实现 IP 隐藏
✦ 双向 NAT 后,回程也必须经 Director(类似 NAT 模式)
✦ 跨网段可用,VIP 不需配置在 RS
```

#### 数据包变化

```text
① 客户发出
   src IP: 1.1.1.100                 (client)
   dst IP: 1.1.1.1                   (VIP)
   src Port: 50000
   dst Port: 80

② Director 接收
   ✓ ip_vs hook 选定 RS-1(10.0.0.1)
   ★ 双向 NAT:
   src IP:  1.1.1.1                  (改! Director 出口 IP,代替 client)
   dst IP:  10.0.0.1                 (改! 选中的 RS)
   src Port: 50000
   dst Port: 80
   ※ src IP 改成 Director 自己,而不是保留 client

③ RS-1 接收
   ✓ 看到 src = 1.1.1.1(Director),不是真实 client
   ✓ RS-1 处理,回包 src=10.0.0.1 → dst=1.1.1.1

④ Director 收 RS 回包
   ★ 反向 NAT(查 conntrack):
   src IP:  10.0.0.1                 (改! 1.0.0.1 → 1.1.1.1)
   dst IP:  1.1.1.100                (改! Director 内网 IP → client)
   ※ 把 Director 出口 IP 还原成真实 client IP
   ※ 把 RS IP 还原成 VIP

⑤ client 收到
   ✓ src IP = 1.1.1.1(VIP),正常
```

#### conntrack 条目

```text
nf_conntrack:
  tuple_original: proto=TCP src=1.1.1.100:50000 dst=1.1.1.1:80
  tuple_reply:    proto=TCP src=10.0.0.1:80      dst=1.1.1.1:50000
  ※ 注意 reply tuple 的 dst = Director 内网 IP
  ※ FULLNAT 内核模块自己维护这张表的反向映射
```

#### vs NAT 模式

| 维度 | NAT | FULLNAT |
| ---- | --- | ------- |
| src IP 改不改 | **不改**(RS 见真实 client) | **改**(RS 见 Director) |
| dst IP 改不改 | 改(VIP → RS) | 改(VIP → RS) |
| RS 配置 | 改网关为 Director | 无特殊要求 |
| RS 网段要求 | 必须同网段 | **可任意网段** |
| VIP 配置 | Director + RS 都要 | **仅 Director** |
| 性能 | 中 | 中(略低于 NAT) |
| 实现 | 标准内核 | 需要内核 patch(阿里云有) |

#### 优缺点

| 优点 | 缺点 |
| ---- | ---- |
| RS 不需要特殊配置 | 内核需 patch(标准内核无) |
| 可跨网段(RS 任意位置) | RS 看不到真实 client IP |
| VIP 不需在 RS | Director 仍是回程瓶颈 |
| 灵活部署(云环境常用) | 性能开销略大 |

#### 命令

```bash
# 标准内核无 FULLNAT
# 阿里云在 Linux 4.x 上有 ip_vs_fullnat 模块
ipvsadm -a -t 1.1.1.1:80 -r 10.0.0.1:80 -b   # -b = FULLNAT

# 验证内核支持
modinfo ip_vs_fullnat
```

---

### 6. 模式深度对比

#### 数据包转换矩阵

```text
┌─────────┬────────────────────┬────────────────────┬────────────────────┬────────────────────┐
│         │       NAT          │        DR          │       TUN          │      FULLNAT       │
├─────────┼────────────────────┼────────────────────┼────────────────────┼────────────────────┤
│ 改 IP   │ 仅改 dst           │ 改 MAC(不改 IP)    │ 整个包套 IPIP 头   │ 改 src + dst       │
│ 改 MAC  │ 不改               │ 改(关键!)          │ 不改(外层不改)    │ 不改                │
│ RS 网段 │ 必须同网段          │ 必须同 L2          │ 可跨网段(广域网)  │ 任意网段            │
│ RS 配置 │ 改网关为 Director  │ lo 配 VIP+抑制 ARP │ tunl0 配 VIP+IPIP │ 无特殊要求          │
│ 回程经  │ 经 Director        │ 不经 Director      │ 不经 Director      │ 经 Director        │
│ Director│                    │                    │                    │                    │
│ src IP  │ 不改(RS 见真实)    │ 不改(RS 见真实)    │ 不改(RS 见真实)    │ 改(RS 见 Director) │
│ 真实    │                    │                    │                    │                    │
│ 性能    │ 中(双向 NAT)       │ **极高**(只改 MAC) | 高(IPIP 封装开销)  | 中(双向 NAT)       │
│ VIP 配置│ Director + RS      │ Director + RS      │ Director + RS      │ 仅 Director        │
│ 实现    │ 标准内核            │ 标准内核            │ 标准内核           | 内核 patch(阿里)   │
└─────────┴────────────────────┴────────────────────┴────────────────────┴────────────────────┘
```

#### 拓扑对比

```text
NAT:
  client ──> [Director: NAT] ──> RS
              ←──────────────────
              (双向流量都经 Director)

DR:
  client ──> [Director: 改 MAC] ──> RS
              (回程不经 Director)

TUN:
  client ──> [Director: IPIP] ──> RS (跨网段)
                          ←───────
              (回程不经 Director)

FULLNAT:
  client ──> [Director: 双向 NAT] ──> RS (跨网段)
              ←─────────────────────
              (回程经 Director)
```

#### 选型决策树

```text
Q1: 同 L2 网段?
   ├── 是 ──→ Q2: 需要 RS 见真实 IP?
   │           ├── 是 ──→ DR(最常用)  ← 默认选
   │           └── 否 ──→ NAT
   └── 否 ──→ Q3: 内核支持 FULLNAT?
               ├── 是 ──→ FULLNAT(云上首选)
               └── 否 ──→ TUN(IPIP 隧道)
```

---

## 五、常用指令

### 1. ipvsadm 命令总览

```bash
ipvsadm -A -t <vip>:<port> -s <algo>      # 添加 virtual service
ipvsadm -a -t <vip>:<port> -r <rs>:<port> -g   # 添加 real server(DR)
ipvsadm -a -t <vip>:<port> -r <rs>:<port> -m   # 添加 real server(NAT)
ipvsadm -a -t <vip>:<port> -r <rs>:<port> -i   # 添加 real server(TUN)

ipvsadm -E -t <vip>:<port> -s <algo>      # 修改
ipvsadm -D -t <vip>:<port>                # 删除 virtual service
ipvsadm -d -t <vip>:<port> -r <rs>:<port> # 删除 real server

ipvsadm -L                                # 列出规则
ipvsadm -L -n -c                          # 连接
ipvsadm -L --rate                         # 速率统计
ipvsadm -L --stats                        # 累计统计

ipvsadm -S                                # 导出配置(类似 iptables-save)
ipvsadm -R                                # 导入配置(类似 iptables-restore)
ipvsadm -C                                # 清空所有规则
```

### 2. flag 速查

| flag | 含义 |
|------|------|
| `-A / -a` | 添加 virtual / real |
| `-E / -e` | 编辑 virtual / real |
| `-D / -d` | 删除 virtual / real |
| `-L / -l` | 列出 |
| `-C` | 清空 |
| `-S / -R` | 保存 / 恢复 |
| `-t` | TCP |
| `-u` | UDP |
| `-f` | fwmark(防火墙标记) |
| `-s` | 调度算法 |
| `-p` | 持久连接(秒) |
| `-m` | MASQ(NAT) |
| `-g` | Gatewaying(DR) |
| `-i` | IPIP(Tunnel) |
| `-b` | FULLNAT(补丁版) |
| `-w` | 权重 |
| `-n` | 数字 |
| `--stats` | 累计 |
| `--rate` | 速率 |

### 3. virtual server 配置

```bash
# TCP virtual server
ipvsadm -A -t 192.168.1.100:80 -s wlc

# UDP virtual server
ipvsadm -A -u 192.168.1.100:53 -s rr

# fwmark virtual server(防火墙标记)
ipvsadm -A -f 1 -s rr

# 持久连接(粘性会话)
ipvsadm -A -t 192.168.1.100:80 -s wlc -p 600     # 600 秒
```

### 4. real server 配置

```bash
# DR 模式,加权
ipvsadm -a -t 192.168.1.100:80 -r 10.0.0.1:80 -g -w 3
ipvsadm -a -t 192.168.1.100:80 -r 10.0.0.2:80 -g -w 1

# NAT 模式
ipvsadm -a -t 192.168.1.100:80 -r 10.0.0.1:80 -m -w 1

# 限制阈值(连接上限)
ipvsadm -a -t 192.168.1.100:80 -r 10.0.0.1:80 -g -w 1 --u-threshold 1000
```

### 5. 状态查看

```bash
# 基本列表
ipvsadm -L -n

# 详细信息
ipvsadm -L -n --stats

# 实时速率
ipvsadm -L -n --rate

# 当前连接
ipvsadm -L -n -c

# tcpfin / udp / icmp
ipvsadm -L -n --connection --timeout

# 时间戳
ipvsadm -L -n --timeout
```

输出示例:

```text
Prot LocalAddress:Port Scheduler   Flags
  -> RemoteAddress:Port           Forward Weight ActiveConn InActConn
TCP  192.168.1.100:80 wlc
  -> 10.0.0.1:80                  Route   3     100        50
  -> 10.0.0.2:80                  Route   1     80         40
```

### 6. 配置保存

```bash
# 保存到文件
ipvsadm -S > /etc/ipvsadm.rules

# 加载
ipvsadm -R < /etc/ipvsadm.rules

# 启动时自动加载
# /etc/rc.local 或 systemd
```

---

## 六、内核数据结构(共享内存)

### 1. 概述

**ip_vs 内核数据结构**:内核分配的共享内存,所有 CPU 可见

- 基于 hash table 存储虚拟服务与连接
- 锁粒度:per-bucket spinlock(早期 RCU)
- 适合大规模并发

### 2. 连接跟踪(Connection Hash Table)

```text
nf_conntrack
├── ip_vs_conn (per connection)
│   ├── client:port
│   ├── vip:port
│   ├── rs:port
│   ├── protocol
│   ├── state
│   └── timeout
└── hash by client_ip + port
```

### 3. 虚拟服务表

```text
ip_vs_service
├── virtual_ip:port
├── protocol
├── scheduler
├── flags (persistent / etc)
├── dests list
│   ├── ip_vs_dest (real server)
│   │   ├── address
│   │   ├── port
│   │   ├── weight
│   │   └── stats
│   └── ...
└── stats
```

### 4. 参数调优

```bash
# conntrack 表大小
sysctl -w net.netfilter.nf_conntrack_max=1048576

# ip_vs 连接超时
sysctl -w net.ipv4.vs.timeout_tcp=300
sysctl -w net.ipv4.vs.timeout_fin=30
sysctl -w net.ipv4.vs.timeout_udp=120
sysctl -w net.ipv4.vs.timeout_icmp=30

# TCP 连接跟踪
sysctl -w net.netfilter.nf_conntrack_tcp_timeout_established=600
sysctl -w net.netfilter.nf_conntrack_tcp_timeout_time_wait=60
sysctl -w net.netfilter.nf_conntrack_tcp_timeout_close_wait=60
```

### 5. 应用场景

| 场景         | 做法                              |
|--------------|-----------------------------------|
| 大并发       | 调大 `nf_conntrack_max`           |
| 长连接超时   | 调 `timeout_tcp`                  |
| 短连接风暴   | 调小 `timeout_tcp`                |
| 内存保护     | 监控 conntrack 表占用             |

---

## 七、网络 I/O

### 1. 数据流(NAT 模式)

```text
client
   │  SYN 192.168.1.100:80
   ▼
Director
   │ ip_vs hook
   │ 选 RS → 10.0.0.1
   │ 改 dst IP = 10.0.0.1
   ▼
Real Server (10.0.0.1)
   │ SYN
   │ SYN+ACK → client IP
   ▼
client              ※ 回程也经 Director(NAT 模式下)
   │ SYN+ACK(源 IP = Director, 因为 src 被改)
```

### 2. 数据流(DR 模式)

```text
client
   │  SYN dst=192.168.1.100 (MAC=Director)
   ▼
Director (192.168.1.100)
   │ ip_vs hook
   │ 选 RS → 10.0.0.1
   │ 改 dst MAC = RS, dst IP 不变
   │ (包从 eth0 出,目的 MAC=RS MAC,IP=VIP)
   ▼
Real Server (10.0.0.1)
   │ 接收(dst MAC=自己,dst IP=VIP,自己 lo 有 VIP)
   │ 处理 → 回包 src=VIP,dst=client
   ▼ ※ 直接回 client,不经过 Director
client
   │ SYN+ACK src=VIP → 客户端
```

### 3. 数据流(TUN 模式)

```text
client
   │  SYN dst=VIP
   ▼
Director
   │ 选 RS → 10.0.1.1
   │ 外面包 dst=10.0.1.1,内层包 dst=VIP(IPIP 隧道)
   ▼
Real Server (10.0.1.1)
   │ 解 IPIP 隧道,内层 dst=VIP,lo 有 VIP,接受
   │ 回包 src=VIP,dst=client(直接回)
   ▼
client
```

### 4. 连接表状态机

```text
client → Director        SYN →
Director → RS            SYN →  (new)
RS      → Director       SYN+ACK ←
Director → client         SYN+ACK ←  (syn+ack)
client  → Director        ACK →
Director → RS            ACK →  (established)
   ...  数据传输 ...
client  → Director        FIN →
Director → RS            FIN →  (fin)
RS      → Director       FIN+ACK ←
Director → client         FIN+ACK ←  (fin+ack)
client  → Director        ACK →
Director → RS            ACK →  (close)
```

### 5. 持久连接

```bash
# 600 秒持久连接(同一 client → 同一 RS)
ipvsadm -A -t 192.168.1.100:80 -s wlc -p 600

# 持久连接 + 防火墙标记
iptables -t mangle -A PREROUTING -d 192.168.1.100 -p tcp --dport 80 -j MARK --set-mark 1
ipvsadm -A -f 1 -s rr -p 600
```

**6. 关键性能**

- L4 透传,**不解析应用层**
- 单核可处理 ~100K+ CPS(L4 短包)
- DR 模式 Director **只收进站**,**回程不经过 Director** → Director 不成瓶颈

---

## 八、HA 与 Failover

### 1. 单点问题

LVS Director 本身是单点(主备模式才能 HA)。

### 2. keepalived 接管

```text
Active Director ─── keepalived ─── Standby Director
       │                                 │
       └── VRRP 心跳 ────────────────────┘
       (vrrp_script / vrrp_instance)
```

### 3. keepalived + LVS 配置

```conf
# /etc/keepalived/keepalived.conf

global_defs {
    router_id LVS_DEVEL
    enable_script_security
}

vrrp_script check_nginx {
    script "/usr/local/bin/check_nginx.sh"
    interval 2
    weight -10
    fall 3
    rise 2
}

vrrp_instance VI_1 {
    state MASTER
    interface eth0
    virtual_router_id 51
    priority 100
    advert_int 1

    authentication {
        auth_type PASS
        auth_pass 1111
    }

    virtual_ipaddress {
        192.168.1.100/24 dev eth0 label eth0:1
    }

    track_script {
        check_nginx
    }
}

virtual_server 192.168.1.100 80 {
    delay_loop 6
    lb_algo wlc
    lb_kind DR
    protocol TCP

    persistence_timeout 600
    persistence_granularity <NETMASK>

    real_server 10.0.0.1 80 {
        weight 3
        TCP_CHECK {
            connect_timeout 3
            nb_get_retry 3
            delay_before_retry 3
            connect_port 80
        }
    }

    real_server 10.0.0.2 80 {
        weight 1
        TCP_CHECK {
            connect_timeout 3
            connect_port 80
        }
    }
}
```

### 4. 健康检查

```conf
# TCP_CHECK - TCP 三次握手
TCP_CHECK { connect_timeout 3 connect_port 80 nb_get_retry 3 }

# HTTP_GET - 主动 GET
HTTP_GET {
    url { path /health status_code 200 }
    connect_timeout 3
    nb_get_retry 3
    delay_before_retry 3
}

# SSL_GET - HTTPS 健康检查
SSL_GET { url { path /health } }

# MISC_CHECK - 自定义脚本
MISC_CHECK {
    misc_path /usr/local/bin/check_app.sh
    misc_timeout 5
    misc_dynamic
}
```

### 5. 自动故障切换

```text
Director A(Master)
   │ 心跳中断
   ▼
VRRP 抢占 / 优先级
   │
   ▼
Director B(Backup) 接管 VIP
   │
   ▼
继续服务
```

---

## 九、调度与持久化(替换定时任务)

### 1. 内核定时器

ip_vs 内部使用 **内核 timer** 做连接超时回收:

- TCP:300s(可调)
- FIN_WAIT:30s
- UDP:120s
- ICMP:30s

### 2. 应用层定时

通过 `keepalived` / 自定义脚本轮询做健康检查(替代定时任务):

```bash
# 外部 cron 调用
*/1 * * * * /usr/local/bin/check_lvs.sh
```

### 3. keepalived 内部通知

```bash
# keepalived 进程通知(进程间通信,非定时)
kill -USR1 $(cat /var/run/keepalived.pid)   # dump stats
kill -HUP  $(cat /var/run/keepalived.pid)   # reload config
```

### 4. 注意事项

- **内核定时器触发回收**,无需用户态介入
- 长连接要调高 `timeout_tcp`,否则连接被误回收
- keepalived 自身是 daemon,故障切换时间 ~3-5s

---

## 十、fwmark 与持久连接规则(替换正则)

### 1. fwmark 防火墙标记

```bash
# iptables 标记
iptables -t mangle -A PREROUTING -d 192.168.1.100 -p tcp --dport 80 -j MARK --set-mark 1
iptables -t mangle -A PREROUTING -d 192.168.1.100 -p tcp --dport 443 -j MARK --set-mark 2

# LVS 接收标记
ipvsadm -A -f 1 -s wlc
ipvsadm -A -f 2 -s rr
```

### 2. 持久连接 granularity

```conf
virtual_server 192.168.1.100 80 {
    persistence_timeout 600
    persistence_granularity 255.255.255.0    # /24 粒度(同一 /24 → 同一 RS)
}
```

### 3. 防火墙标记的灵活性

```bash
# 同一 VIP 不同端口不同调度
iptables -t mangle -A PREROUTING -d 192.168.1.100 -p tcp --dport 80  -j MARK --set-mark 1
iptables -t mangle -A PREROUTING -d 192.168.1.100 -p tcp --dport 443 -j MARK --set-mark 2

ipvsadm -A -f 1 -s wlc   # HTTP 用 wlc
ipvsadm -A -f 2 -s rr    # HTTPS 用 rr
```

### 4. 与正则无关

LVS 不解析应用层,**无正则概念**;路由粒度 = 五元组(VIP + 端口 + 协议 + 客户端 IP)。

---

## 十一、内核模块开发 / sysctl 调优

### 1. 内核编译选项

```bash
# 内核需要开启
CONFIG_IP_VS=m
CONFIG_IP_VS_RR=m
CONFIG_IP_VS_WRR=m
CONFIG_IP_VS_LC=m
CONFIG_IP_VS_WLC=m
CONFIG_IP_VS_SH=m
CONFIG_IP_VS_DH=m
CONFIG_IP_VS_SED=m
CONFIG_IP_VS_NQ=m
CONFIG_IP_VS_TAB_BITS=22       # hash table 2^22 = 4M 条
```

### 2. 关键 sysctl

```bash
# 转发(LVS 必须)
net.ipv4.ip_forward = 1

# conntrack
net.netfilter.nf_conntrack_max = 1048576
net.nf_conntrack_max = 1048576

# ip_vs 超时
net.ipv4.vs.timeout_tcp = 300
net.ipv4.vs.timeout_fin = 30
net.ipv4.vs.timeout_udp = 120
net.ipv4.vs.timeout_icmp = 30

# RS DR 模式需要的内核参数(RS 端)
net.ipv4.conf.all.arp_ignore = 1
net.ipv4.conf.all.arp_announce = 2
net.ipv4.conf.lo.arp_ignore = 1
net.ipv4.conf.lo.arp_announce = 2

# 软中断 CPU 亲和
net.core.netdev_max_backlog = 16384
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
```

### 3. NF_INET_PRE_ROUTING hook

ip_vs 注册在 netfilter `NF_INET_PRE_ROUTING` 钩子,所有入站包都先经 ip_vs。

### 4. RPS / XPS 多核均衡

```bash
# 启用 RPS(软中断均衡)
echo f > /sys/class/net/eth0/queues/rx-0/rps_cpus
echo 4096 > /sys/class/net/eth0/queues/rx-0/rps_flow_cnt
```

---

## 十二、常用工具

### 1. ipvsadm(用户态管理)

```bash
ipvsadm -A -t 192.168.1.100:80 -s wlc
ipvsadm -a -t 192.168.1.100:80 -r 10.0.0.1:80 -g
ipvsadm -L -n --stats
```

### 2. keepalived(HA + 健康检查)

最主流的 LVS 配套工具。功能:VRRP + 健康检查 + 自动 ipvsadm 维护。

### 3. ldirectord

Heartbeat 项目的健康检查守护进程(老式)。

### 4. ipvs(内核)

```bash
cat /proc/net/ip_vs
cat /proc/net/ip_vs_conn
cat /proc/net/ip_vs_stats
```

### 5. perf / systemtap

```bash
# 抓 ip_vs 处理路径
perf record -e net:net_dev_xmit -a
systemtap -e 'probe kernel.function("ip_vs_in") { printf("%s\n", $$parms); }'
```

### 6. ipvs-exporter / Prometheus

```bash
# 通过 ipvsadm 解析输出
ipvsadm -L -n --rate | promtail

# 或 ipvs_exporter 项目(社区)
```

---

## 十三、持久连接与回话保持

### 1. 持久连接模式

```bash
# 同一 client IP → 同一 RS
ipvsadm -A -t 192.168.1.100:80 -s wlc -p 600
```

### 2. granularity

```conf
virtual_server 192.168.1.100 80 {
    persistence_timeout 600
    persistence_granularity 255.255.255.0    # /24 粒度
}
```

### 3. 持久连接 vs 调度算法

- `sh`(源地址哈希)是 L4 层粘性
- `-p timeout` 是基于时间窗口的粘性

两者可叠加,但生产上一般**只用一种**。

### 4. 缓存亲和

- `dh`(目标地址哈希):同一 URL → 同一 RS,适合 CDN 缓存代理
- 同一 RS 上的缓存命中率更高

### 5. 应用场景

| 场景         | 调度                       |
|--------------|----------------------------|
| 一般 Web     | wlc                        |
| 长连接(SSH) | wlc + -p 长超时            |
| 会话保持     | sh 或 -p + cookie 配合     |
| 缓存亲和     | dh / lblc                  |
| 短任务爆量   | sed / nq                   |

---

## 十四、性能优化

### 1. 网络栈调优

```bash
# 网卡多队列
ethtool -L eth0 combined 8

# 软中断均衡
echo f > /sys/class/net/eth0/queues/rx-0/rps_cpus

# 网卡 offload
ethtool -K eth0 gro on gso on tso on

# 大页(可选)
sysctl -w vm.nr_hugepages=1024
```

### 2. conntrack 调优

```bash
sysctl -w net.netfilter.nf_conntrack_max=1048576
sysctl -w net.netfilter.nf_conntrack_tcp_timeout_established=600
sysctl -w net.netfilter.nf_conntrack_tcp_timeout_time_wait=30
```

### 3. 内核网络缓冲

```bash
sysctl -w net.core.rmem_max=16777216
sysctl -w net.core.wmem_max=16777216
sysctl -w net.ipv4.tcp_rmem="4096 87380 16777216"
sysctl -w net.ipv4.tcp_wmem="4096 65536 16777216"
sysctl -w net.core.netdev_max_backlog=30000
```

### 4. 选择最优模式

```text
高 QPS 短连接:   DR 模式
长连接 / 文件:  NAT 或 DR
跨网段:          TUN 或 FULLNAT(阿里)
NAT 网关限制:    DR / TUN / FULLNAT
```

### 5. 多网卡 / 绑定

```bash
# 进出流量分离
# Director 一块网卡接收 client,一块网卡转发到 RS
# RS 回包直接出 client 网卡(不经过 Director)
```

### 6. 性能基准

| 操作                  | 量级(L4 短包) |
|-----------------------|---------------|
| DR 模式(短包)        | ~500K CPS     |
| NAT 模式              | ~200K CPS     |
| TUN 模式              | ~150K CPS     |
| conntrack 查找       | ~10M QPS      |

(随硬件不同)

---

## 十五、防火墙与 / 网关层应用

### 1. iptables 配合 LVS

```bash
# 标记 VIP 流量
iptables -t mangle -A PREROUTING -d 192.168.1.100 -p tcp --dport 80 -j MARK --set-mark 1

# 标记允许的源
iptables -t mangle -A PREROUTING -s 10.0.0.0/8 -j MARK --set-mark 1
iptables -t mangle -A PREROUTING ! -s 10.0.0.0/8 -j MARK --set-mark 2

# 不同 fwmark 走不同 virtual server
ipvsadm -A -f 1 -s wlc   # 内网
ipvsadm -A -f 2 -s rr    # 外网(可能限速)
```

### 2. 限流与连接限制

LVS 本身不实现应用层限流,但可通过 conntrack / iptables 间接实现:

```bash
# 单 IP 连接数限制
iptables -A INPUT -p tcp --dport 80 -m connlimit --connlimit-above 100 -j REJECT

# 单 IP 新建速率限制(每秒)
iptables -A INPUT -p tcp --dport 80 -m recent --set --name perip
iptables -A INPUT -p tcp --dport 80 -m recent --update --seconds 1 --hitcount 20 --name perip -j DROP
```

### 3. SYN 洪水防御

```bash
# 启用 SYN cookies
sysctl -w net.ipv4.tcp_syncookies=1

# 调大半连接队列
sysctl -w net.ipv4.tcp_max_syn_backlog=8192

# iptables 限制 SYN 速率
iptables -A INPUT -p tcp --syn -m limit --limit 100/s --limit-burst 200 -j ACCEPT
iptables -A INPUT -p tcp --syn -j DROP
```

### 4. 真实 IP 透传

DR 模式下,RS 看到 client 真实 IP。NAT 模式默认改 src IP(可用 `-m` + `--scheduler` 等保留)。

### 5. 不支持的应用层场景

- **HTTP 路由**:LVS 不解析 HTTP,**做不了按 URL 路由**
- **HTTPS 终止**:L4 透传 TLS,**不解析证书**
- **Header 改写**:做不到
- **WAF**:做不到,得用 Nginx / HAProxy 做

---

## 十六、调试与监控

### 1. 状态查看

```bash
ipvsadm -L -n
ipvsadm -L -n --stats
ipvsadm -L -n --rate
ipvsadm -L -n -c
```

### 2. 连接跟踪

```bash
cat /proc/net/ip_vs_conn
cat /proc/net/ip_vs
cat /proc/net/nf_conntrack
```

### 3. 关键指标

```text
ActiveConn  - 当前活跃连接
InActConn   - 非活跃连接
CPS         - 新建连接速率(per second)
InPPS/BPS   - 入包 / 入字节速率
OutPPS/BPS  - 出包 / 出字节速率
```

### 4. 监控导出

```bash
# 通过 node_exporter textfile collector
cat > /var/lib/node_exporter/textfile_collector/ipvs.prom <<EOF
ipvs_active_connections{vs="192.168.1.100:80"} 1000
ipvs_inactive_connections{vs="192.168.1.100:80"} 500
EOF

# 或 ipvs_exporter
```

### 5. 抓包诊断

```bash
# 看 client → Director → RS 包流
tcpdump -i eth0 -nn 'host 192.168.1.100'
tcpdump -i eth1 -nn 'host 10.0.0.1'
```

### 6. 内核日志

```bash
dmesg | grep -i ip_vs
journalctl -k | grep -i ip_vs
```

### 7. debug

```bash
# 临时打开 ip_vs debug
echo 1 > /proc/sys/net/ipv4/vs/debug_level
```

---

## 十七、常见陷阱

### 1. DR 模式 RS 没配 ARP 抑制

```bash
# 症状:client 直接连 RS,绕过 Director
# 解决:RS 必须
sysctl -w net.ipv4.conf.lo.arp_ignore=1
sysctl -w net.ipv4.conf.lo.arp_announce=2
sysctl -w net.ipv4.conf.all.arp_ignore=1
sysctl -w net.ipv4.conf.all.arp_announce=2
```

### 2. NAT 模式 RS 没改默认网关

```bash
# 症状:NAT 模式下 RS 回包找不到路
# 解决:RS 必须把网关设为 Director 的 IP(同网段)
route add default gw <Director_internal_ip>
```

### 3. ip_forward 没 启

```bash
# NAT 模式必需
sysctl -w net.ipv4.ip_forward=1
```

### 4. VIP 绑错接口

```bash
# DR 模式:VIP 在 Director 物理网卡(eth0)
ip addr add 192.168.1.100/32 dev eth0

# RS 端:VIP 在 lo(不响应 ARP)
ip addr add 192.168.1.100/32 dev lo
```

### 5. conntrack 满

```bash
# 症状:大量丢包或新建连接失败
# 解决:调大
net.netfilter.nf_conntrack_max=1048576
```

### 6. 持久连接与调度冲突

```bash
# -p 与 sh 一起用 → 双重粘性,可能 RS 负载不均
# 一般只用一种
ipvsadm -A -t 192.168.1.100:80 -s wlc -p 600
```

### 7. 健康检查不触发 failover

```bash
# keepalived 健康检查 fail 后,会 ipvsadm -d 摘掉 RS
# RS 本身进程挂 → TCP 三次握手失败 → failover 正常
# 但若 RS 还能握手但应用挂了 → TCP_CHECK 抓不到
# → 改用 HTTP_CHECK 或 MISC_CHECK
```

### 8. TUN 模式 RS 没开 IPIP

```bash
# 症状:TUN 模式下 RS 解不了包
# 解决:RS 必须加载 ipip 模块
modprobe ipip
```

### 9. 跨网段 DR 模式失败

DR 模式要求 Director 与 RS **同网段**(同 L2)。跨网段必须用 TUN 或 FULLNAT。

### 10. 单 Director 单点

生产必须 **双 Director + keepalived + VRRP**。

---

## 十八、LVS vs 其他 LB

| 维度        | LVS              | HAProxy           | Nginx(stream)    | F5 BIG-IP        |
|-------------|------------------|-------------------|------------------|------------------|
| 模式        | L4               | L4 + L7           | L4               | L4 + L7          |
| 实现层      | **内核态**        | 用户态            | 用户态           | 硬件             |
| 性能        | **极高**(线速)   | 高                | 中-高            | 极高             |
| 健康检查    | 弱(需 keepalived)| **强**           | 弱               | **强**           |
| 配置        | ipvsadm / keepalived | 配置文件         | 配置文件         | 配置 + GUI      |
| 灵活性      | 弱               | 强                | 中               | **强**           |
| L7 支持     | 无               | **有**           | 弱               | **有**           |
| 适用        | L4 高 QPS 入口   | L4/L7 LB          | 轻量 L4          | 商业入口         |
| 成本        | 开源             | 开源              | 开源             | 商业(昂贵)       |

**LVS 适用场景**:

- 高 QPS L4 入口(Web 集群入口)
- 长连接(mysql / ssh)
- 极致性能要求

**LVS 不适用**:

- HTTP / gRPC 路由(L4 不解析)
- HTTPS 终止(用 Nginx)
- 灰度 / 限流(用 Nginx / HAProxy)

**常见组合**:

```text
client → LVS(DR) → Nginx(L7 反代) → upstream
client → LVS(DR) → HAProxy(L7)    → upstream
```

---

## 十九、部署与运维

### 1. 安装

```bash
# RHEL/CentOS
yum install ipvsadm keepalived

# Debian/Ubuntu
apt install ipvsadm keepalived

# 检查内核模块
lsmod | grep ip_vs
```

### 2. 内核模块加载

```bash
# /etc/modules-load.d/ipvs.conf
ip_vs
ip_vs_rr
ip_vs_wrr
ip_vs_lc
ip_vs_wlc
ip_vs_sh
ip_vs_dh

# 或一次性 modprobe
modprobe ip_vs ip_vs_rr ip_vs_wrr ip_vs_lc ip_vs_wlc ip_vs_sh ip_vs_dh
```

### 3. 启动

```bash
# ipvsadm 规则
ipvsadm -A -t 192.168.1.100:80 -s wlc
ipvsadm -a -t 192.168.1.100:80 -r 10.0.0.1:80 -g
ipvsadm -a -t 192.168.1.100:80 -r 10.0.0.2:80 -g

# 保存
ipvsadm -S > /etc/ipvsadm.rules
ipvsadm -R < /etc/ipvsadm.rules

# keepalived
systemctl enable --now keepalived
```

### 4. 启动脚本 /etc/rc.local

```bash
#!/bin/bash
# 启动 ipvsadm
ipvsadm -R < /etc/ipvsadm.rules

# 启动 keepalived
systemctl start keepalived

# 启用转发
sysctl -w net.ipv4.ip_forward=1
```

### 5. 配置文件 /etc/keepalived/keepalived.conf

见 §八.3。

### 6. 常用命令

```bash
# 查看规则
ipvsadm -L -n

# 查看速率
ipvsadm -L -n --rate

# 查看连接
ipvsadm -L -n -c

# 手动添加 / 删除
ipvsadm -a -t 192.168.1.100:80 -r 10.0.0.3:80 -g
ipvsadm -d -t 192.168.1.100:80 -r 10.0.0.3:80

# 清空(慎用)
ipvsadm -C

# keepalived 控制
systemctl status keepalived
systemctl reload keepalived    # 等价 kill -HUP
```

### 7. 双 Director HA 部署

```text
              ┌──────────────┐
              │  VIP 192.168.1.100  │
              └──────────────┘
                │            │
        ┌───────┴──┐   ┌─────┴────────┐
        │ Master   │   │  Backup       │
        │ Director │   │  Director     │
        │          │   │               │
        └────┬─────┘   └────┬──────────┘
             │               │
             └── VRRP 心跳 ──┘

             │
             ▼
      Real Server 1
      Real Server 2
      Real Server 3
```

- 两个 Director 配同 VIP
- VRRP 心跳选主
- 健康检查摘除故障 RS
- 主备切换时间 ~3-5s

### 8. 监控告警

```bash
# Prometheus + node_exporter
node_exporter --collector.systemd
node_exporter --collector.nf_conntrack

# 自定义脚本(伪代码)
active=$(ipvsadm -L -n --stats | grep -A1 "192.168.1.100:80" | tail -1 | awk '{print $5}')
if [ "$active" -gt "$threshold" ]; then
    alert "LVS connection high"
fi
```

---

## 二十、核心要点速记

- **LVS = Linux 内核态 L4 LB**(`ip_vs` 模块),性能极高
- **用户态工具**:`ipvsadm`(配置)+ `keepalived`(HA)
- **4 大模式**:NAT(改 IP) / DR(改 MAC,同网段) / TUN(IPIP 隧道) / FULLNAT(改双向 IP)
- **DR 是生产最常用**:Director 只进站,RS 直接回 client
- **NAT 网关限制**:Director 与 RS 同网段,RS 网关设为 Director
- **调度算法**:`wlc` 默认推荐 / `wrr` 加权 / `sh` 粘性 / `dh` 缓存亲和
- **持久连接**:`-p timeout`,同 IP → 同 RS
- **防火墙标记 fwmark**:同一 VIP 不同端口不同调度
- **Director 必须配 VIP**:DR 在物理网卡,RS 在 lo(不响应 ARP)
- **DR 必须关 ARP 响应**:`arp_ignore=1, arp_announce=2`
- **必须开转发**:`net.ipv4.ip_forward=1`
- **conntrack 调优**:`nf_conntrack_max` + `timeout_tcp`
- **HA 必备 keepalived**:VRRP + 健康检查 + 自动维护 ipvsadm
- **TCP_CHECK / HTTP_GET / SSL_GET / MISC_CHECK**:keepalived 健康检查方式
- **`vrrp_script`** 自定义健康检查(本地服务)
- **告警指标**:ActiveConn / InActConn / CPS / PPS
- **`/proc/net/ip_vs_conn`** 查看连接
- **LVS 不解析 HTTP / HTTPS**:只能按 IP + Port 分层,做不了 L7 路由
- **L4 + L7 组合**:`client → LVS(DR) → Nginx(L7) → upstream`
- **NAT 模式不限制**:可跨网段,但 Director 成瓶颈(双向流量都过)
- **TUN 模式 RS 必须能解 IPIP**:跨网段需公网 IP
- **FULLNAT 是阿里云补丁**:标准内核无,跨网段最佳
- **生产 Director 双机**:主备 + VRRP + keepalived
- **`ipvsadm -L -n --rate`**:实时速率
- **`ipvsadm -L -n --stats`**:累计统计
- **`ipvsadm -S > /etc/ipvsadm.rules`**:保存规则,启动恢复
- **iptables + fwmark** 配合:灵活路由
- **RS 不能反向访问 client**(DR 模式除外)
- **debug**:`echo 1 > /proc/sys/net/ipv4/vs/debug_level`(慎用)
- **`conntrack` 是瓶颈**:高并发需调大 `nf_conntrack_max`
- **`arp_ignore`/`arp_announce`**:DR 模式必备
- **`vip` 配置位置很关键**:Director 物理网卡 / RS lo
- **`/proc/net/ip_vs_conn`** 是查看连接状态的关键
- **持久连接粒度**:`persistence_granularity` 控制
- **`sh`(源哈希)是 L4 粘性首选**,-p 是 fallback
- **`lblc` / `lblcr`** 缓存代理亲和
- **`lvs-nat` 与 `lvs-dr` 不可混用**:同一 VS 选一种模式
- **LVS vs HAProxy**:HAProxy 健康检查强 / L7 / 灵活;LVS 性能 / 内核
- **LVS vs Nginx(stream)**:LVS 性能远超 Nginx(stream),但 Nginx 配置灵活
- **`keepalived` vrrp_script** 自定义健康检查,业务层故障也能触发 failover
- **不解析 HTTP 是 LVS 的设计哲学**:**快 / 透传**;L7 用 HAProxy / Nginx
