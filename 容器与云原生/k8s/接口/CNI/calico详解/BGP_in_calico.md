# Calico BGP 详解

> Calico 在数据面用 **BGP** 在节点 / ToR / Spine 之间同步 Pod 路由。
> 这篇文档围绕一张典型数据中心 Spine-Leaf 拓扑，讲清 **iBGP / eBGP** 的区别、Calico 怎么落地、配置怎么写。

---

## 零、基础概念（先把名词搞清）

> 这一节只讲**名词本身**，不讲 Calico。看不懂 BGP 全靠死记硬背，先把这一节看完。

### 0.1 AS（Autonomous System，自治系统）

```text
AS（Autonomous System）= 一片**由单一组织管理、对外有统一路由策略**的网络

现实类比：
  - 一个 AS ≈ 一个独立的国家
  - 国家之间要通信 → 要有"国与国"之间的协议（eBGP）
  - 国家内部要通信 → 要有"国内"的路网（iBGP / OSPF / IS-IS）

互联网层面：
  - 全球互联网就是由几万个 AS 互联组成的
  - 每个 AS 有全球唯一的编号：ASN（Autonomous System Number）
  - 像邮编一样，每个国家的邮编体系独立，但全球唯一编号
```

**ASN 编码规则**：

| 范围 | 位数 | 用途 |
| --- | --- | --- |
| 1–64511 | 16 bit | 公有 ASN（互联网可见，需要向 IANA / RIR 申请） |
| 64512–65534 | 16 bit | **私有 ASN**（私有网络内部用，Calico 默认就用这个范围） |
| 65535 | 16 bit | 保留 |
| 4200000000–4294967294 | 32 bit | 私有 ASN 扩展（Calico 3.20+ 支持） |

```text
Calico 默认私有 ASN：64512
  → 自己 AS 内部可以随便用 64512~65534
  → 不会跟互联网 ASN 冲突（互联网路由器收到也不认这些 ASN）
```

### 0.2 BGP（Border Gateway Protocol）

```text
BGP = 互联网的"路由协议之王"
  - 唯一在用的**外部网关协议**（EGP）
  - 设计目的：在 AS 之间交换"我能到达哪些 IP 段"
  - 路径向量协议（Path Vector）：路由里带 AS-PATH，记录"经过哪些 AS"

类比：
  - BGP 路由条目 ≈ 一张快递单：起点 → 经过哪些转运中心（AS） → 终点
  - AS-PATH 防环：看到自己 AS 出现两次就丢（环路检测）
  - 路由器之间传递"我能到哪"的"可达性信息"，不转发用户数据
```

**BGP 主要做的事**：

```text
1. 建邻居（Neighbor / Peer）
   - 两台 BGP 路由器 TCP 179 端口建立会话
   - 互相通报"我知道的路由"

2. 同步路由表
   - 收到邻居通告后写入自己的 BGP 表
   - 优选最优路径写入 FIB（转发信息表）→ 真正用来转发

3. 防环
   - eBGP：靠 AS-PATH
   - iBGP：靠水平分割（iBGP 学到的不再通告给其他 iBGP 邻居）

4. 策略控制
   - 路由过滤（filter-list / prefix-list / community）
   - 路径选择（local-pref / MED / weight）
```

### 0.3 邻居（Neighbor / Peer）

```text
邻居 = 两台 BGP 路由器之间的 TCP 会话（端口 179）

两个邻居要建立连接，必须：
  1. 彼此能 TCP 通（IP 可达）
  2. AS 号配置正确（eBGP 不同 / iBGP 相同）
  3. 互相认证（可选，BGP MD5 / TCP-AO）

邻居状态机：
  Idle → Connect → Active → OpenSent → OpenConfirm → Established
  ↑ 平时停留在 Established（已建立）

Calico 默认邻居建立用 `calicoctl node status` 可以看到 State 列。
```

### 0.4 eBGP vs iBGP（先记一张总表）

| 维度 | eBGP（External） | iBGP（Internal） |
| --- | --- | --- |
| AS 号 | **不同** | **相同** |
| 一句话 | 跨 AS 传路由 | AS 内部同步路由 |
| 典型场景 | ToR ↔ Spine、Node ↔ ToR | 节点之间、Leaf 之间 |
| AS-PATH | 传出去时**追加**本 AS | 传出去时**不修改** |
| 防环 | AS-PATH 检测 | 水平分割 |
| 下一跳 | 改成自己的接口 IP | 默认不改（iBGP 内部需要 next-hop-self） |
| 邻居关系 | 一般直连 | 可跨多跳（loopback 建邻） |
| 拓扑 | 简单，点对点 | 多，**节点多了用 RR 避免 n² 爆炸** |

### 0.5 RR（Route Reflector，路由反射器）

```text
iBGP 的"水平分割"原则：
  → 从一个 iBGP 邻居学到的路由，**不能**再通告给其他 iBGP 邻居

带来的问题：
  - n 个节点两两建邻居 = n(n-1)/2 条会话
  - 100 个节点 = 4950 对邻居，根本不现实

RR 怎么解决：
  - 挑 1~2 个节点当 RR（特殊配置）
  - 其他节点（client）只跟 RR 建邻居
  - RR 把从 client A 学到的路由**反射**给其他 client
  - Client 之间不直连
  - RR 之间可以互连（同 cluster ID）做高可用

Calico 的实现：
  - routeReflectorClusterID 字段标记谁是 RR
  - 选个独立 Cluster ID（IPv4 格式，如 244.0.0.1）
```

### 0.6 几种 ASN 的现实类比

```text
公网 ASN (1–64511)：
  - 像国家的国际区号（+86 中国、+1 美国）
  - 全球唯一，互联网路由器认
  - 申请：向 RIR（亚太 APNIC / 美洲 ARIN / 欧洲 RIPE）

私有 ASN (64512–65534)：
  - 像企业内部的分机号（8001、8002...）
  - 内部随便用，外部不认
  - Calico / 数据中心内部组网就用这个

图里的 ASN：
  - 64512 / 64513  → 私有 ASN，K8s 节点内部
  - 65009 / 65010  → 私有 ASN，Leaf 交换机
  - 65008         → 私有 ASN，Spine 交换机

Calico 默认起手 ASN = 64512，因为这是私有 ASN 的起点。
```

### 0.7 ToR / Spine / Leaf（数据中心拓扑名词）

```text
传统三层数据中心：
  Core → Aggregation（汇聚）→ Access（接入 / ToR）

现代 Spine-Leaf（Clos 网络）：
  Spine（脊）    = 核心层，全互联到所有 Leaf
  Leaf（叶）    = 接入层，每个机柜一个，接服务器
  ToR（Top of Rack）= 跟 Leaf 一个意思，就是机柜顶上的交换机

Calico BGP 拓扑里：
  - Node ↔ Leaf   → eBGP（节点属于不同 ASN）
  - Leaf ↔ Spine  → eBGP
  - Node ↔ Node   → iBGP（同一 ASN，用 RR）

为什么用 Spine-Leaf 而不是传统三层：
  - 任意两点最多跨 2 个交换机（低延迟）
  - 带宽可水平扩展（加 Leaf / 加 Spine）
  - ECMP 路径多，负载均衡好
```

### 0.8 看图之前的术语速查表

| 术语 | 全称 | 含义 |
| --- | --- | --- |
| AS | Autonomous System | 自治系统，一组统一管理的网络 |
| ASN | AS Number | AS 的编号（16 bit 或 32 bit） |
| BGP | Border Gateway Protocol | 边界网关协议 |
| eBGP | External BGP | 不同 AS 之间的 BGP |
| iBGP | Internal BGP | 同一 AS 内部的 BGP |
| RR | Route Reflector | iBGP 路由反射器，解决 n² 问题 |
| ToR | Top of Rack | 机柜顶交换机 |
| Spine | - | 数据中心核心交换机 |
| Leaf | - | 数据中心接入交换机 |
| ECMP | Equal-Cost Multi-Path | 等价多路径，可同时用多条路径转发 |
| AS-PATH | - | BGP 路由属性，记录经过的 AS 列表 |
| next-hop-self | - | 让 iBGP 邻居把下一跳改成自己（不然跨路由器不通） |
| Pod CIDR | - | Pod IP 地址段 |

---

## 一、整体拓扑

```text
                         ┌─────────────────────────────────┐
                         │           spine 交换机           │
                         │   100.0.0.1/30   100.0.0.5/30   │
                         │             ASN: 65008           │
                         └──────────────┬──────────────────┘
                                        │ EBGP
                          ┌─────────────┴─────────────┐
                          │ EBGP                       │ EBGP
                          ▼                           ▼
        ┌────────────────────────────┐   ┌────────────────────────────┐
        │      leaf 交换机 01         │   │      leaf 交换机 02         │
        │   100.0.0.2/30              │   │   100.0.0.6/30              │
        │   172.20.0.254              │   │   173.20.0.254              │
        │         ASN: 65009          │   │         ASN: 65010          │
        └──┬──────────┬──────────┬────┘   └──┬──────────┬──────────┬────┘
           │ EBGP     │ EBGP     │ EBGP      │ EBGP     │ EBGP     │ EBGP
           ▼          ▼          ▼           ▼          ▼          ▼
        ┌──────┐  ┌──────┐  ┌──────┐    ┌──────┐  ┌──────┐  ┌──────┐
        │node1 │  │node2 │  │node3 │    │node4 │  │node5 │  │node6 │
        │.11   │  │.12   │  │.13   │    │.11   │  │.12   │  │.13   │
        │64512 │  │64512 │  │64512 │    │64513 │  │64513 │  │64513 │
        └──┬───┘  └──┬───┘  └──────┘    └──┬───┘  └──┬───┘  └──────┘
           │  Calico RR         ▲           │  Calico RR         ▲
           └──────────┐         │           └──────────┐         │
                  iBGP           └──────────     iBGP           ┘
                  同 ASN 内部全互联               同 ASN 内部全互联
```

**关键角色**：

| 角色 | ASN | 数量 | 互联协议 |
| --- | --- | --- | --- |
| Spine 交换机 | 65008 | 1 | ↔ Leaf 走 eBGP |
| Leaf 交换机 | 65009 / 65010 | 2 | ↔ Spine 走 eBGP，↔ Node 走 eBGP |
| K8s 节点（左机柜） | 64512 | 3 | 节点之间走 iBGP，由 Calico RR 中转 |
| K8s 节点（右机柜） | 64513 | 3 | 节点之间走 iBGP，由 Calico RR 中转 |

---

## 二、iBGP vs eBGP

### 2.1 一句话区别

```text
eBGP（External BGP）  不同 AS 之间，建立邻居 → 跨域传路由
iBGP（Internal BGP）  同一 AS 内部，建立邻居 → 把路由在 AS 内扩散
```

### 2.2 详细对比

| 维度 | eBGP | iBGP |
| --- | --- | --- |
| 邻居所在 AS | **不同** AS | **同一** AS |
| 典型场景 | ToR ↔ Spine、Node ↔ ToR | 同 AS 内的全互联或 RR 中转 |
| 建邻条件 | 一般直连 / 同子网 | 可跨多跳（loopback 建邻） |
| AS-PATH | 收路由时**追加**本 AS 号 | 收路由时**不修改** AS-PATH（防环） |
| 防环机制 | AS-PATH 检测：见到自己 AS 就丢 | 水平分割：从 iBGP 邻居学到的路由**不再通告给其他 iBGP 邻居** |
| 路由下一跳 | 改为建邻居时的接口 IP（默认） | 默认**不修改**下一跳（IBGP 收到 eBGP 路由后下一跳仍是对端 Leaf IP） |
| 邻居数量 | 跟物理口数相关，量少 | 节点多时全互联（n²）会爆炸，必须用 RR |

### 2.3 为什么 Calico 用 BGP 而不是直接路由同步

```text
1. 多路径（ECMP）
   BGP 支持等价多路径 → 同一 Pod CIDR 在多条链路上同时可达，带宽叠加
   静态路由只能选一条

2. 自动收敛
   节点增减、BGP 邻居抖动 → 路由自动刷新
   不用手工写脚本同步

3. 跨域互通
   K8s 节点 ↔ Leaf ↔ Spine 全是 BGP → 不需要单独跑路由协议

4. 与现有网络共生
   数据中心 ToR/Spine 大概率已经跑 BGP → Calico 直接接入就行
```

---

## 三、Calico BGP 模式选型

### 3.1 三种模式

> **参数说明**：
> - `n` = K8s 节点总数
> - `k` = Route Reflector 数量（同 cluster 内）
> - `t` = 每个节点接入的 ToR 数（多 ToR 时一般是 2）

| 模式 | 节点间协议 | 节点 ↔ ToR | 连接数公式 | n=6 | n=50 | n=200 | 适用 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **None**（默认） | 不跑 BGP，纯 vxlan/IPIP/felix | 不需要 | `0` | 0 | 0 | 0 | 简单集群、overlay only |
| **Full-Mesh iBGP** | 节点两两 iBGP 全互联 | 不需要 | `n(n-1)/2` | **15** | **1225** | **19900** | 节点数 ≤ 20，扁平 |
| **Route Reflector (RR)** | 节点 ↔ RR 走 iBGP | 可选 | `(n-k)×k + k(k-1)/2`（可选 + n×t） | 12（k=2） | 147（k=3） | 597（k=3） | 节点数 > 20 / 多 ToR 接入 |
| **eBGP to ToR** | 节点 ↔ ToR 走 eBGP | ToR 即 iBGP RR | `n×t` | 12（t=2） | 100（t=2） | 400（t=2） | 大规模生产、Spine-Leaf |
| **混合模式（本图）** | 节点 ↔ RR 走 iBGP | 节点 ↔ ToR 走 eBGP | `n×t + (n-k)×k + k(k-1)/2` | **12**（iBGP 6 + eBGP 6） | ~ 数十 | 数百 | 数据中心多 ASN、多机柜 |

**公式拆解**：

```text
Full-Mesh iBGP：n(n-1)/2
  → C(n,2) = 节点两两组合数
  → n=20: 190 条；n=50: 1225 条；n=100: 4950 条

RR（核心解法）：(n-k)×k + k(k-1)/2
  → client → RR：(n-k) 个 client 各连 k 个 RR
  → RR ↔ RR（同 cluster 内 k 个 RR 两两互联）
  → k=2, n=50: 48×2 + 1 = 97 条（比 Full-Mesh 1225 少 92%）

eBGP to ToR：n×t
  → 每个节点连 t 个 ToR
  → 节点之间不直连，靠 ToR 中转
  → t=2（双 ToR 高可用）, n=100: 200 条

混合模式（本图）：n×t + (n-k)×k + k(k-1)/2
  → 节点 ↔ Leaf（eBGP）：n×t
  → 节点 ↔ RR（iBGP）：(n-k)×k
  → RR ↔ RR（iBGP，可选）：k(k-1)/2
```

**连接数计算示例**（n=6，参考本图）：

```text
Full-Mesh iBGP：
  C(6,2) = 6×5/2 = 15 条
  ↑ 节点数一上来就爆炸，n=20 已经 190 条

Route Reflector（k=2 个 RR，n-k=4 个 client）：
  client → RR：4×2 = 8 条
  RR ↔ RR（同 cluster）：C(2,2) = 1 条
  合计：9 条 iBGP（AS 内）
  + 可选 eBGP 到 ToR（如果开）：6×t 条
  总：9 + 6t 条（t=1 时 15 条，t=2 时 21 条）

eBGP to ToR（每节点接 t=2 个 ToR）：
  节点 ↔ ToR：6×2 = 12 条 eBGP
  ↑ ToR 之间 iBGP 由交换机自己跑，不算 Calico

混合模式（本图，n=6，k=2，t=1）：
  节点 ↔ Leaf（eBGP）：6×1 = 6 条
  节点 ↔ RR（iBGP，64512 内部）：
    client (node3) → 2 RR (node1, node2) = 2 条
    RR1 (node1) ↔ RR2 (node2) = 1 条
    小计 3 条
  节点 ↔ RR（iBGP，64513 内部）：同上 3 条
  合计：6 + 3 + 3 = 12 条
```

**为什么连这个数这么重要**：

```text
- 每条 BGP 邻居 = 一个 TCP 179 会话 + 路由同步开销
- 节点多到一定规模，控制平面会被邻居数拖垮
- 邻居握手 / 路由刷新都要 CPU 算，连接数 ≈ CPU 占用
- 经验值：单节点邻居数 < 50 比较健康，> 100 要警惕
```

### 3.2 本图对应模式

```text
本图 = 混合模式：

  节点 ↔ Leaf 交换机 走 eBGP（不同 ASN：64512 vs 65009，64513 vs 65010）
  节点内部        走 iBGP（Calico RR 模式，64512 / 64513 各 2 个 RR）

理由：
  - 数据中心 ToR 已经按 ASN 隔离机柜，节点必须用 eBGP 接入
  - 节点多了全互联 iBGP 不现实（6 个节点就是 15 对邻居），用 Calico RR 中转
  - 左右两机柜 ASN 不同，物理上隔离，RR 也各管各的
```

---

## 四、Calico 配置

### 4.1 节点 ASN 配置

```yaml
# node1.yaml —— 用 node label 区分机柜和 ASN
apiVersion: projectcalico.org/v3
kind: Node
metadata:
  name: node1
  labels:
    rack: "left"
spec:
  bgp:
    asNumber: 64512                       # 左机柜 ASN
    ipv4Address: 172.20.0.11/24           # 本机节点 IP
  routeReflectorClusterID: 244.0.0.1      # 标记为 RR（可选，见 4.3）
---
# node4.yaml —— 右机柜节点
apiVersion: projectcalico.org/v3
kind: Node
metadata:
  name: node4
  labels:
    rack: "right"
spec:
  bgp:
    asNumber: 64513                       # 右机柜 ASN
    ipv4Address: 173.20.0.11/24
  routeReflectorClusterID: 244.0.0.2
```

### 4.2 IP Pool（Pod CIDR）

```yaml
apiVersion: projectcalico.org/v3
kind: IPPool
metadata:
  name: left-pool
spec:
  cidr: 10.244.0.0/16
  ipipMode: Never                         # 物理 BGP 已通，不用 IPIP
  vxlanMode: Never
  natOutgoing: true
  nodeSelector: rack == "left"            # 只给左机柜节点分配
---
apiVersion: projectcalico.org/v3
kind: IPPool
metadata:
  name: right-pool
spec:
  cidr: 10.245.0.0/16                     # 不同机柜用不同 CIDR，路由好算
  ipipMode: Never
  vxlanMode: Never
  natOutgoing: true
  nodeSelector: rack == "right"
```

### 4.3 BGP Peer 配置（节点 ↔ Leaf 交换机）

```yaml
# 让节点跟 leaf 交换机建 eBGP 邻居
apiVersion: projectcalico.org/v3
kind: BGPPeer
metadata:
  name: leaf01-to-left-rack
spec:
  nodeSelector: rack == "left"            # 64512 的所有节点
  peerIP: 172.20.0.254                    # leaf01 的互联 IP
  peerASNumber: 65009                     # leaf01 ASN
  asNumber: 64512                         # 自己的 ASN
  passwords:
    secret: "leaf-secret"                 # 选配
  keepOriginalNextHop: false              # 关键：让 leaf 收到路由时下一跳改成节点 IP
---
apiVersion: projectcalico.org/v3
kind: BGPPeer
metadata:
  name: leaf02-to-right-rack
spec:
  nodeSelector: rack == "right"
  peerIP: 173.20.0.254
  peerASNumber: 65010
  asNumber: 64513
```

### 4.4 Calico RR 配置（节点内部 iBGP）

```yaml
# node1 / node4 上启用 RR（也可单独挑两台做 RR）
# node1 是 64512 的 RR
apiVersion: projectcalico.org/v3
kind: Node
metadata:
  name: node1
  labels:
    rack: "left"
spec:
  bgp:
    asNumber: 64512
    ipv4Address: 172.20.0.11/24
  routeReflectorClusterID: 244.0.0.1       # 64512 的 RR cluster
---
# 其他节点（node2/node3）作为 RR Client，连 node1
apiVersion: projectcalico.org/v3
kind: BGPPeer
metadata:
  name: left-rack-rr-client
spec:
  nodeSelector: rack == "left" && name != "node1"
  peerIP: 172.20.0.11                       # RR 是 node1
  peerASNumber: 64512
  asNumber: 64512
```

> **RR 关键点**：
>
> 1. 同 cluster ID 的 RR 之间互相连（多 RR 高可用）
> 2. Client 只连 RR，**Client 之间不连**（这就是 RR 解决 iBGP n² 爆炸的核心）
> 3. RR 默认遵守"收到 iBGP 路由不再通告给同 AS 的其他 iBGP 邻居"——它**主动打破**这条规则，把路由反射给所有 client，所以叫"路由反射器"

---

## 五、BGP 邻居状态 / 路由表验证

### 5.1 节点上查 BGP 状态

```bash
# Calico 自带的 bird / felix 视图
calicoctl node status

# 输出示例
Bird 4.15
  Router ID: 172.20.0.11
  AS Number: 64512
  Cluster ID: 244.0.0.1
  Router ID: 172.20.0.11

  Neighbor        AS   State   PfxIn   PfxOut
  172.20.0.254   65009   Up      12       25     # leaf01
  172.20.0.12    64512   Up      22       25     # node2 (RR client)
  172.20.0.13    64512   Up      22       25     # node3 (RR client)
  172.20.0.11    64512   Up       -       -      # 自己（RR）

  Established   3   Dropped   0
```

### 5.2 节点查学到的路由

```bash
# 进 bird 控制台
calicoctl node bird

# 看 IPv4 BGP 路由表
> show route

# 看 IPv4 协议邻居
> show protocols

# 看 BGP 邻居详细状态
> show protocols all bgp1

# 看从某邻居收到的路由
> show route where bgp.path ~ "65009"
```

### 5.3 节点路由表

```bash
ip route | grep -E "10\.24[45]"
# 预期看到：
# 10.244.0.0/16 dev cali... proto bird  ← 本机 Pod 路由
# 10.244.1.0/24 via 172.20.0.12 dev eth0 proto bird   ← 对端节点 Pod，下一跳是节点 IP
```

### 5.4 端到端连通性

```bash
# node1 Pod → node4 Pod（跨机柜、跨 ASN、跨 RR）
kubectl exec -ti pod-on-node1 -- ping 10.245.0.10

# 抓包验证走的 BGP 路由（不是 tunnel）
tcpdump -i eth0 -nn host 10.245.0.10
```

---

## 六、常见问题排查

### 6.1 邻居起不来（State = Active / Connect）

```text
检查项：
  1. 节点 IP 能 ping 通 Leaf 的 peerIP？
       ping 172.20.0.254
  2. AS Number 是否两端匹配？
       node 上 64512，leaf 上 65009 — 必须不同（eBGP）
  3. TCP 179 端口是否通？
       telnet 172.20.0.254 179
  4. Leaf 上的 eBGP 配置里有没有 allowas-in / peer 限制？
  5. 防火墙 / 安全组放通了吗？
```

### 6.2 邻居起来了但没有路由（PfxIn = 0）

```text
检查项：
  1. IP Pool 是否给该节点分配了 Pod？
       calicoctl ipam show
  2. routeReflectorClusterID 在 RR 上配了吗？
  3. client 是否连的是 RR（peerIP 写错了）？
  4. bird 的 import / export filter 是否限制了协议族？
  5. 看 bird 日志：
       calicoctl node bird
       > show log
```

### 6.3 跨机柜 Pod 不通

```text
检查项：
  1. 节点路由表有没有对端机柜的 CIDR？
       ip route | grep 10.245
       # 没有 → leaf02 没收到 64512 的路由 → leaf02 缺 eBGP peer
  2. ASN 配置是否覆盖完整（左右机柜 ASN 不同但都配了）？
  3. IP Pool 的 nodeSelector 是否冲突？
       节点 rack 标签打对了吗？
```

### 6.4 路由数量爆炸（每节点 10000+ 条）

```text
原因：
  - 节点规模上来后，节点本地 Pod 路由都被广播出去
  - 集群 Pod 数 /24 切分太多

优化：
  1. 切大网段：每个节点用 /24 改成 /16 聚合
  2. 开 BGP aggregate-address（路由聚合）
  3. 大集群直接上 BGP unnumbered + 路由聚合
```

---

## 七、RR vs Full-Mesh vs eBGP-to-ToR 怎么选

| 场景 | 选这个 | 理由 |
| --- | --- | --- |
| 节点 ≤ 20，集群内部 | Full-Mesh iBGP | 简单，邻居少，配置直接 |
| 节点 20–200，单 ASN | Calico RR | RR cluster 1–2 个就够，避开 n² 爆炸 |
| 多机柜 / 多 ASN 接入 ToR | eBGP to ToR + 节点内 iBGP RR | 本图方案 |
| 已有数据中心 BGP 路由策略 | eBGP 完整方案 | Calico 直接作为 AS 之一接入 |
| 灰度试水 / 学习 | None 或 RR | RR 最容易上手，配置最少 |

---

## 八、一句话总结

> **eBGP 跨 AS 传路由（节点 ↔ ToR），iBGP 同一 AS 内同步（节点之间用 RR 中转）**——
> Calico 让 K8s 节点成为 BGP 路由器的一员，直接接入数据中心的路由平面，
> 既省了 overlay 隧道，又天然支持 ECMP 和多路径。

---

## 九、参考

- [Calico 官方文档 - BGP](https://docs.tigera.io/calico/latest/networking/configuring/bgp)
- [Calico 官方文档 - Route Reflectors](https://docs.tigera.io/calico/latest/networking/configuring/bgp#route-reflector)
- RFC 4271 — A Border Gateway Protocol 4 (BGP-4)
- RFC 4456 — BGP Route Reflection
- RFC 5065 — Autonomous System Confederations for BGP
