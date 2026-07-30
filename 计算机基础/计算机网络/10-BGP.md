# BGP 协议 (Border Gateway Protocol)

## 一、BGP 概述

### 什么是 BGP

**BGP (Border Gateway Protocol，边界网关协议)**：一种基于路径向量的域间路由协议，是当前互联网唯一广泛使用的 EGP (Exterior Gateway Protocol)。

BGP 主要解决：

- 自治系统之间的可达性交换
- 大规模网络中的策略控制
- 跨运营商、跨国家的路由选择
- 灵活的路径属性过滤与操纵

```text
AS 100 ──── eBGP ──── AS 200 ──── eBGP ──── AS 300
   │                        │                        │
   │ iBGP                   │ iBGP                  │ iBGP
   ▼                        ▼                        ▼
 内部 IGP                 内部 IGP                 内部 IGP
```

### 为什么需要 BGP

如果没有 BGP：

```text
互联网由数十万个 AS 组成
每个 AS 包含数以万计的前缀
路径、策略、运营商关系千差万别
```

距离向量（RIP）和链路状态（OSPF/IS-IS）都难以胜任：

- 拓扑规模不足
- 策略表达力弱
- 不携带商业关系信息
- 收敛后仍无法反映策略

BGP 通过 AS_PATH 和丰富的路径属性承载策略，是事实上的互联网骨干协议。

### BGP 的特点

- 基于路径向量（Path Vector）
- 基于 TCP 179 可靠传输
- 增量更新 + 周期性刷新
- CIDR 支持（携带前缀 + 长度）
- 丰富的路径属性（Path Attributes）
- 以策略（Policy）而非单纯 metric 决策
- eBGP 防环使用 AS_PATH
- iBGP 防环需要全互联或反射器 / 联盟
- 不主动发现邻居，需手动指定 Peer
- 默认不做负载均衡，按策略选单一最优路径

### BGP 角色与术语

| 术语 | 作用 |
| ---- | ---- |
| **AS (Autonomous System)** | 一组被统一管理的 IP 前缀与路由策略 |
| **AS Number (ASN)** | 2 字节或 4 字节自治系统编号 |
| **BGP Speaker** | 运行 BGP 并参与对等体关系的路由器 |
| **BGP Peer / Neighbor** | 与本地 Speaker 建立 BGP 会话的远端 Speaker |
| **Speaker 角色** | 由 AS 内配置决定谁是 PE / CE / RR / 边界 |
| **IGP** | 内部网关协议（OSPF、IS-IS 等） |
| **EBGP / External BGP** | 不同 AS 之间的 BGP |
| **IBGP / Internal BGP** | 同一 AS 内部的 BGP |

---

## 二、BGP 端口与通信方式

### 1. 传输层

| 方向 | 本端端口 | 对端端口 |
| ---- | -------- | -------- |
| 任一端发起 | 任意端口 | TCP 179 |
| 建立后双向 | 179 或高端口 | 179 或高端口 |

BGP 通过 TCP 三次握手建立连接，因此：

- 依赖底层 IGP 或静态路由保证 Peer 之间 IP 可达
- 报文可靠传输，无需自己重传
- 默认不对等体报文做认证（除 TCP MD5 / GTSM）

### 2. Peer 类型

| 类型 | 说明 |
| ---- | ---- |
| **eBGP Peer** | 不同 AS 之间的 BGP 邻居，默认 TTL=1 |
| **iBGP Peer** | 同一 AS 之内的 BGP 邻居，默认 TTL=255 |
| **Confederation Peer** | 联盟内部的 BGP，行为类似 eBGP |
| **Route Reflector Client** | RR 与其客户机之间的 iBGP |
| **Confederation eBGP** | 跨子 AS 的 eBGP，类似 eBGP |

### 3. Peer 发现方式

- 静态指定：对端 IP 手工配置
- 不使用组播发现
- 不像 OSPF / IS-IS 自动发现邻居
- Peer 之间通常建立 BFD 或 KEEPALIVE 监控

### 4. 多跳 Peer

```text
R1 ── 链路 ── R2 ── 链路 ── R3
```

R1 与 R3 之间建立 BGP：

```text
neighbor 3.3.3.3 remote-as 200
neighbor 3.3.3.3 ebgp-multihop 2
```

需要：

- 双方相互可达的 IGP / 静态路由
- ebgp-multihop 大于实际跳数
- TTL 安全机制（GTSM）

### 5. AS Number

- 公有 ASN：2 字节 1–64511，4 字节 4200000000–4294967294（早期 4 字节）
- 私有 ASN：64512–65534（2 字节），需要约定或转换
- 4 字节 ASN：RFC 6793，ASPLAIN 与 ASDOT 两种格式

```text
ASPLAIN:  23456
ASDOT:    2.3.0.56   = 23456
```

私有 ASN 传递给运营商时通常会被剥离，需明确协商。

---

## 三、BGP 五种报文

### 1. 报文类型

| Type | 名称 | 作用 |
| ---- | ---- | ---- |
| **1** | OPEN | 建立邻居，协商参数 |
| **2** | UPDATE | 通告或撤销路由 |
| **3** | NOTIFICATION | 错误通知并拆链 |
| **4** | KEEPALIVE | 保活，防 Hold Timer 超时 |
| **5** | ROUTE-REFRESH | 请求对端重发指定 AFI/SAFI 的路由 |

### 2. OPEN

对端收到 OPEN 后校验参数，同意则回 KEEPALIVE 建立。

```text
BGP Speaker A                         BGP Speaker B
  │                                        │
  │ TCP 三次握手                           │
  ├───────────────────────────────────────→│
  │←───────────────────────────────────────┤
  │                                        │
  │ OPEN (AS, Router-ID, Hold Time...)     │
  ├───────────────────────────────────────→│
  │                                        │
  │ KEEPALIVE                              │
  │←───────────────────────────────────────┤
  │                                        │
  │ KEEPALIVE                              │
  ├───────────────────────────────────────→│
  │                                        │
  │              Established               │
```

常见字段：

- Version：当前为 4
- My AS：发送方 ASN
- Hold Time：双方取较小值
- BGP Identifier：发送方 Router-ID
- Optional Parameters：能力参数（MP-BGP、Route Refresh、Add-Path、4 字节 ASN 等）

### 3. KEEPALIVE

不携带路由信息，仅用于保活：

- 协商 Hold Time 的三分之一默认发送一次
- 实际频率可被 `timers` 调整
- 长时间无 UPDATE / KEEPALIVE 到达 Hold Time 内则拆链

### 4. UPDATE

携带：

- NLRI：新增或更新的路由
- 撤销路由（Withdrawn Routes）
- 路径属性（Path Attributes）

```text
┌────────────────────────────────────────┐
│ Withdrawn Routes Length                │
├────────────────────────────────────────┤
│ Withdrawn Routes                       │
├────────────────────────────────────────┤
│ Total Path Attribute Length            │
├────────────────────────────────────────┤
│ Path Attributes                        │
├────────────────────────────────────────┤
│ NLRI                                  │
└────────────────────────────────────────┘
```

一条 UPDATE 可同时包含撤销与新增属性/路由，但实现上常常分开发送。

### 5. NOTIFICATION

检测到错误后发送并拆链：

- Message Header Error
- OPEN Message Error
- UPDATE Message Error
- Hold Timer Expired
- Finite State Machine Error
- Cease（管理员主动拆链）

收到 Notification 后会话立即终止，需要重新建立。

### 6. ROUTE-REFRESH

不携带路由，用于触发对端重发全部指定 AFI/SAFI 路由，常发生在：

- 策略变更后
- 收到错误路由希望重新协商
- BGP RR 客户机做策略刷新

```text
Route Refresh (AFI=1, SAFI=1)
      ↓
对端重发整张 BGP 表
```

---

## 四、BGP 报文格式

### 1. 通用 Header

所有 BGP 报文都以 19 字节固定头开始：

```text
+---------------------------------------+
| Marker (16 bytes): all 1s             |
+---------------------------------------+
| Length (2 bytes)                      |
+---------------------------------------+
| Type (1 byte)                         |
+---------------------------------------+
```

| 字段 | 长度 | 含义 |
| ---- | ---- | ---- |
| **Marker** | 16 字节 | 全 1，用于鉴权场景历史 |
| **Length** | 2 字节 | 包含头在内的总长度，最小 19，最大 4096 |
| **Type** | 1 字节 | 1=OPEN，2=UPDATE，3=NOTIFICATION，4=KEEPALIVE，5=ROUTE-REFRESH |

### 2. OPEN 格式

```text
+---------------------------------------+
| Version (1)                           |
+---------------------------------------+
| My AS (2 or 4 bytes)                  |
+---------------------------------------+
| Hold Time (2 bytes)                   |
+---------------------------------------+
| BGP Identifier (4 bytes, Router-ID)   |
+---------------------------------------+
| Opt Parm Len (1)                      |
+---------------------------------------+
| Optional Parameters                   |
+---------------------------------------+
```

### 3. UPDATE 格式

```text
+---------------------------------------+
| Withdrawn Routes Length (2)           |
+---------------------------------------+
| Withdrawn Routes (variable)           |
+---------------------------------------+
| Total Path Attribute Length (2)       |
+---------------------------------------+
| Path Attributes                       |
|   Attr Flags + Type Code + Length     |
|   Attribute Value                     │
+---------------------------------------+
| NLRI                                  │
+---------------------------------------+
```

### 4. NOTIFICATION 格式

```text
+---------------------------------------+
| Error Code (1)                        |
+---------------------------------------+
| Error Subcode (1)                     │
+---------------------------------------+
| Data (variable)                       │
+---------------------------------------+
```

### 5. ROUTE-REFRESH 格式

```text
+---------------------------------------+
| AFI (2)                               |
+---------------------------------------+
| Reserved (1)                          |
+---------------------------------------+
| SAFI (1)                              │
+---------------------------------------+
```

---

## 五、BGP 路径属性

### 1. 属性分类

| 类别 | 含义 |
| ---- | ---- |
| **Well-known Mandatory** | 所有 BGP 实现必须识别且必须随路由通告 |
| **Well-known Discretionary** | 必须识别，但可选择是否通告 |
| **Optional Transitive** | 不识别也要传递给下一跳 |
| **Optional Non-transitive** | 不识别则丢弃 |

### 2. 常见属性一览

| 属性 | 类型代码 | 分类 | 说明 |
| ---- | -------- | ---- | ---- |
| **ORIGIN** | 1 | Well-known Mandatory | IGP / EGP / Incomplete |
| **AS_PATH** | 2 | Well-known Mandatory | 经过的 AS 序列 |
| **NEXT_HOP** | 3 | Well-known Mandatory | 下一跳 IP |
| **MULTI_EXIT_DISC (MED)** | 4 | Optional Non-transitive | 影响入向选路 |
| **LOCAL_PREF** | 5 | Well-known Discretionary | 影响出向选路（iBGP） |
| **ATOMIC_AGGREGATE** | 6 | Well-known Discretionary | 通告汇总时不携带明细 AS_SET |
| **AGGREGATOR** | 7 | Optional Transitive | 汇总路由器与 AS |
| **COMMUNITY** | 8 | Optional Transitive | 团体标识 |
| **ORIGINATOR_ID** | 9 | Optional Non-transitive | RR 起源 ID |
| **CLUSTER_LIST** | 10 | Optional Non-transitive | RR 反射路径 |
| **MP_REACH_NLRI** | 14 | Optional Non-transitive | 多协议可达 |
| **MP_UNREACH_NLRI** | 15 | Optional Non-transitive | 多协议撤销 |

### 3. ORIGIN

| 值 | 含义 |
| -- | ---- |
| **IGP** | 来自本 AS 内部（如 `network` 重发布） |
| **EGP** | 历史 EGP 协议，已不再使用 |
| **Incomplete** | 通过重发布学到，来源不明 |

ORIGIN 越具体越优先：IGP 优于 EGP 优于 Incomplete。

### 4. AS_PATH

```text
AS_PATH 类型
├── Sequence       正常顺序：100 200 300
├── Set            无序集合：{100, 200}
└── Confederation  联盟子 AS 序列
```

```text
AS 100 把路由发给 AS 200 时
原本 AS_PATH 为空
通告给 AS 200 后变成:
AS_PATH = [100]
AS 200 再通告给 AS 300
AS_PATH = [200 100]
```

AS_PATH 是 BGP 防环的基础：收到含自身 ASN 的路由即丢弃。

### 5. NEXT_HOP

| 场景 | NEXT_HOP 行为 |
| ---- | ------------- |
| **eBGP** | 默认是通告路由器的接口 IP |
| **iBGP** | 默认沿用 eBGP Peer 通告的下一跳 |
| **Next-Hop-Self** | 修改为 iBGP 本端地址，常用于 RR |
| **多跳 eBGP** | 通常需手工 Next-Hop-Self |

```text
AS 100 (R1) ── eBGP ── AS 200 (R2) ── iBGP ── AS 200 (R3)

R1 把 10.0.0.0/8 通告给 R2
NEXT_HOP = R1 的互联接口地址
R3 通过 iBGP 收到时 NEXT_HOP 仍为 R1 接口地址
R3 需要 IGP 可达 R1 才能递归查表
```

### 6. LOCAL_PREF

- 仅在 iBGP 内传递
- 默认值：100
- 数值越大越优先
- 用于决定本 AS 出向流量方向

```text
AS 200 内部：
R2 LOCAL_PREF=200
R4 LOCAL_PREF=150
去往 AS 300 优先选 R2 出口
```

### 7. MED

- 在 eBGP 之间传递
- 默认值：0
- 数值越小越优先
- 用于影响对端 AS 进本 AS 的入向流量

```text
AS 100 通过两条链路连接 AS 200
链路 1 通告 MED=10
链路 2 通告 MED=20
AS 200 内选路时偏向 MED 较小的链路 1
```

### 8. COMMUNITY

- 32 位整数标签
- 著名团体：

| 团体 | 含义 |
| ---- | ---- |
| **no-export** | 不通告给 eBGP Peer |
| **no-advertise** | 不通告给任何 Peer |
| **no-export-subconfed** | 不通告给联盟外 eBGP |
| **internet** | 不做特殊处理 |
| **graceful-shutdown** | 平滑退出 |

- 扩展团体（Extended Community）：8 字节，用于 VPN / MPLS 等
- 大团体（Large Community）：12 字节

---

## 六、BGP 选路原则

### 1. 总体顺序

BGP 选路严格按以下顺序比较，第一条不唯一即比较下一条：

```text
1.  Highest Weight             (Cisco 私有，Local)
2.  Highest LOCAL_PREF
3.  Locally Originated         (本 AS 内部产生)
4.  Shortest AS_PATH
5.  Lowest ORIGIN              (IGP < EGP < Incomplete)
6.  Lowest MED
7.  eBGP > iBGP
8.  Lowest IGP metric to NEXT_HOP
9.  Oldest eBGP Path
10. Lowest Router-ID
11. Lowest Peer IP (Cluster List Length)
12. Lowest Neighbor Address
```

不同厂商顺序略有差别，但核心一致：Weight → Local Pref → AS Path → Origin → MED → eBGP/iBGP → IGP Metric。

### 2. Weight

- Cisco 私有：本地有效，不可传递
- 默认值：本地产生路由 = 32768，其他学到的 = 0
- 通过 `weight`、route-map、邻居配置修改

### 3. LOCAL_PREF 优先级最高（厂商无关属性）

```text
R1 ─ AS 100 ─ R2
R3 ─ AS 100 ─ R4
LOCAL_PREF=300 → R1 出口
LOCAL_PREF=200 → R3 出口
```

### 4. AS_PATH 长度

```text
AS_PATH: 100 200 300
长度 = 3
```

运营商常通过 AS_PATH 预置（Prepend）控制流量方向。

### 5. 决策示例

| 路由 | Weight | LocalPref | AS_PATH | MED | 选择 |
| ---- | ------ | --------- | ------- | --- | ---- |
| A | 0 | 100 | 300 400 | 0 | ✓ |
| B | 0 | 100 | 200 500 | 0 | ✓ |

最终选择 AS_PATH 更短的 B。

### 6. ECMP 与 Add-Path

- 默认 BGP 不做等价负载均衡
- Add-Path 协商后允许通告多条等价路径
- 不同厂商名称略有差别（max-path、maximum-paths）

---

## 七、BGP 状态机

### 1. 六大状态

| 状态 | 含义 |
| ---- | ---- |
| **Idle** | 初始或停止状态，等待启动事件 |
| **Connect** | 等待 TCP 连接完成 |
| **Active** | TCP 连接失败，不断重试 |
| **OpenSent** | 已发送 OPEN，等待响应 |
| **OpenConfirm** | 已收到 OPEN，等待 KEEPALIVE |
| **Established** | 对等体已建立，可交换 UPDATE |

### 2. 状态转移

```text
Idle
 │ Start
 ▼
Connect ──────── TCP 失败/重置 ──→ Active
 │ TCP 建立成功                         │
 │ OPEN 发送                            │ TCP 成功
 ▼                                      ▼
OpenSent ─ OPEN 错误 ─→ Idle         OpenSent
 │ 收到 OPEN/Keepalive
 ▼
OpenConfirm ─ KEEPALIVE ─→ Established
   │ Notify / Hold Expired
   ▼
 Idle
```

### 3. 常见卡滞状态

| 卡滞 | 可能原因 |
| ---- | -------- |
| **Active** | 邻居 IP、AS 错；TCP 被 ACL 阻断；接口 down |
| **OpenSent** | Router-ID、Hold Time、能力协商失败 |
| **OpenConfirm** | Hold Time 不匹配；KEEPALIVE 未发 |
| **持续 Idle** | 配置未启用；启动事件缺失 |

### 4. Hold Timer 与 KEEPALIVE

| 参数 | 默认 |
| ---- | ---- |
| **Hold Time** | 180 秒 |
| **KEEPALIVE 间隔** | Hold Time / 3 = 60 秒 |
| **Connect Retry** | 120 秒 |
| **MinRouteAdvInterval** | 30 秒（eBGP） |
| **MinASOriginationInterval** | 15 秒 |

可在 Peer 视图修改，但两端最终取较小值。

---

## 八、BGP 路由通告规则

### 1. 基本原则

- eBGP：学到的路由可以通告给本 AS 内的 iBGP Peer
- iBGP：学到的路由默认不通告给其他 iBGP Peer
- eBGP Peer：通告路由时附加本 AS

### 2. iBGP 水平分割

```text
        iBGP Full-Mesh
  R1 ───── R2
   │  \    │
   │   \   │
  R3 ───── R4

不允许：
R2 从 R1 学到路由后再通告给 R3
（除非 R2 是 RR 或联盟边界）
```

iBGP 学到的路由不通告给其他 iBGP，原因是 AS 内部无 AS_PATH 防环机制，因此必须构建全互联或使用 RR / 联盟打破。

### 3. eBGP 防环

```text
R1 (AS 100) ── eBGP ── R2 (AS 200) ── eBGP ── R3 (AS 300)

R3 把 10.0.0.0/8 通告给 R2
AS_PATH = [300]
R2 通告给 R1
AS_PATH = [200 300]

R1 通告回 R2，AS_PATH = [100 200 300]
R2 看到自身 AS 200 已存在，丢弃
```

### 4. RR 反射例外

- RR 打破 iBGP 水平分割
- 使用 ORIGINATOR_ID / CLUSTER_LIST 防环

### 5. 联盟例外

- 联盟子 AS 之间如同 eBGP，使用 AS_PATH 防环
- 整个联盟对外表现为单一 AS

---

## 九、路由反射器 (Route Reflector) 与联盟

### 1. RR 角色

| 角色 | 关系 |
| ---- | ---- |
| **RR (Reflector)** | 反射路由 |
| **Client** | RR 的客户机，仅与 RR 形成 iBGP |
| **Non-Client** | RR 之间互连 |

### 2. 反射规则

```text
RR 收到路由来自：
├── Client        → 反射给 所有 Client + 所有 Non-Client
├── Non-Client    → 仅反射给 Client（不通告给其他 Non-Client）
└── eBGP Peer     → 通告给所有 Client + 所有 Non-Client
```

### 3. ORIGINATOR_ID & CLUSTER_LIST

```text
RR1 (Cluster A) 收到 client 路由
ORIGINATOR_ID = 客户端 Router-ID
CLUSTER_LIST  = [Cluster_A]

RR2 (Cluster B) 收到 RR1 反射的路由
增加自己的 Cluster_ID
CLUSTER_LIST = [Cluster_B, Cluster_A]

若 RR 收到 CLUSTER_LIST 包含自身 Cluster_ID 则丢弃
```

### 4. RR 设计原则

- 同一 Cluster 多个 RR 实现冗余
- 不同 Cluster 之间仍需 Full-Mesh 或多层 RR
- Client 与 RR 之间即可简化连接，不需全互联

### 5. 联盟 (Confederation)

```text
AS 200 (Confederation AS 65001)
   ├── Sub-AS 65001
   │    ├── R1
   │    └── R2
   └── Sub-AS 65002
        ├── R3
        └── R4

对外 AS_PATH 仅出现 [200]，内部使用 CONFED_AS_PATH
```

每个子 AS 内仍需 Full-Mesh 或 RR；子 AS 之间用类似 eBGP 的方式通告。

---

## 十、BGP 路由聚合

### 1. 聚合方式

| 类型 | 方式 |
| ---- | ---- |
| **Static Aggregate** | 手工通过 `aggregate-address` / `network` 通告汇总 |
| **Dynamic Aggregate** | 通过 IGP 重发布自动汇总（Cisco 自动汇总历史特性） |

### 2. aggregate-address 选项

| 选项 | 含义 |
| ---- | ---- |
| **summary-only** | 只通告汇总，明细被抑制 |
| **as-set** | AS_PATH 使用 AS_SET，包含明细 AS |
| **suppress-map** | 选择性抑制明细 |
| **attribute-map** | 修改汇总的属性 |
| **advertise-map** | 仅当条件前缀存在才通告汇总 |
| **route-map** | 过滤可被聚合的前缀 |

### 3. ATOMIC_AGGREGATE

- 当 `as-set` 缺失或聚合过程中丢失路径信息时设置
- 收到此属性的路由器不应再解聚合
- 用于告知下游聚合路径不完整

### 4. 聚合中的 AS_PATH

```text
明细：AS_PATH = [300]    10.1.0.0/16
明细：AS_PATH = [400]    10.2.0.0/16
汇总（as-set）：AS_PATH = [200] {300 400}    10.0.0.0/14
汇总（无 as-set）：AS_PATH = [200]                10.0.0.0/14 ATOMIC_AGGREGATE
```

`as-set` 能保留明细 AS 但引入 Set 与 Sequence 的复杂度，影响选路确定性，需根据场景选择。

---

## 十一、BGP 路由过滤与策略

### 1. 入向与出向

| 方向 | 作用 |
| ---- | ---- |
| **Inbound** | 控制本路由器从邻居接收哪些路由 |
| **Outbound** | 控制向邻居通告哪些路由 |

### 2. 常用工具

| 工具 | 用途 |
| ---- | ---- |
| **prefix-list** | 前缀与长度范围匹配 |
| **filter-list (AS_PATH ACL)** | AS_PATH 正则匹配 |
| **route-map** | 复杂策略与属性修改 |
| **community-list** | 团体匹配 |
| **extcommunity-list** | 扩展团体匹配 |
| **distribute-list** | 基于 ACL 的过滤 |

### 3. 正则表达式

AS_PATH 过滤常用正则：

```text
^100$        完全等于 100
^100_        以 100 开头
_100$        以 100 结尾
_100_        中间包含 100
^[0-9]+$     仅含数字
.*           任意
```

### 4. 常见过滤组合

```text
Inbound:
  route-map FROM_PEER permit 10
    match ip address prefix-list ALLOW_CUSTOMER
    set local-preference 200

Outbound:
  route-map TO_PEER deny 10
    match community BLACKHOLE
  route-map TO_PEER permit 20
```

### 5. 最大前缀限制

```text
neighbor 10.0.0.1 maximum-prefix 100000
```

超过上限后处理方式：

- warning-only：只警告
- restart N：N 分钟后重建会话
- 丢弃并停止会话

---

## 十二、BGP 团体属性

### 1. 标准团体

32 位，写成 `AA:NN`：

```text
65001:100
65001:200
```

### 2. 著名团体

| 团体 | 行为 |
| ---- | ---- |
| **no-export** | 不通告到 eBGP Peer |
| **no-advertise** | 不通告给任何 Peer |
| **no-export-subconfed** | 联盟内部不外传 |
| **internet** | 默认行为 |
| **graceful-shutdown** | GR 期间声明 graceful 退出 |

### 3. 扩展团体

用于 MPLS VPN、FlowSpec 等：

```text
Route Target: 65001:100
Site of Origin: 65001:50
```

格式：

```text
Type:2bytes Administrator:4bytes Assigned Number:2bytes
2bytes : 4bytes : 2bytes
```

### 4. 大团体 (RFC 8092)

12 字节：

```text
Global Administrator:4bytes Local Administrator:6bytes
4294967296:1
```

### 5. 团体传递规则

- 默认不向 eBGP 邻居通告标准团体（除非配置 `send-community`）
- iBGP 邻居默认传递
- 需根据厂商开启对应参数

---

## 十三、BGP 安全

### 1. 路由劫持 (Hijack)

```text
AS 65000 本应通告 10.0.0.0/8
AS 65500 冒充分配 10.0.0.0/8 给其他 Peer
其他 AS 选择更短的 AS_PATH 或 MOAS 接受
导致流量被错误引导
```

类型：

- **Prefix Hijack**：完全冒充分配
- **Sub-Prefix Hijack**：更具体的伪造（如 /24 冒充 /8）
- **Path Manipulation**：冒用其他 AS 的 AS_PATH

### 2. 路由泄漏 (Leak)

更具体或更优选的路由意外通告到非授权 Peer：

- 违反商业关系（Provider → Customer → Peer 错误方向）
- 通常因缺少 filter、route-map 或误操作

### 3. 安全防护

| 手段 | 作用 |
| ---- | ---- |
| **TCP MD5 / TCP-AO** | Peer 之间 TCP 报文认证 |
| **GTSM / TTL Security** | 限制 Peer 报文 TTL |
| **IPsec** | 链路或 Peer 加密 |
| **RPKI / ROA** | 验证 ASN 是否被授权通告该前缀 |
| **BGP Origin Validation** | 根据 ROA 标记 Valid / Invalid / NotFound |
| **IRR / RADB** | 维护 whois 注册信息 |
| **BGP Monitoring (BGPMon, RIPE RIS)** | 全球多 vantage point 监控 |

### 4. RPKI

```text
Prefix: 10.0.0.0/8
Origin AS: AS65000
ROA 通过 RPKI 验证 → 标记 Valid

未匹配 ROA → NotFound
匹配但 ASN 不同 → Invalid
```

### 5. MaxPrefix 与 Bogons

- `maximum-prefix` 抑制邻居通告过多前缀
- Bogon 前缀列表过滤未分配地址空间
- 应同时在入向 / 出向都过滤

### 6. MD5 / GTSM 示例

```text
neighbor 10.0.0.1 password BGPsecret123
neighbor 10.0.0.1 ttl-security hops 1
```

---

## 十四、BGP 收敛与震荡控制

### 1. 路由抖动 (Flapping)

- Peer / 链路频繁 UP / DOWN
- 每次状态变化触发大量 UPDATE
- 全网路由器都要重算

### 2. Dampening

| 参数 | 默认 |
| ---- | ---- |
| **Half-Life (分钟)** | 15 |
| **Reuse** | 750 |
| **Suppress** | 2000 |
| **Max-Suppress-Time (分钟)** | 60 |

```text
首次惩罚值 = 1000
每次重新抖动 × 2
到达 Suppress 阈值则抑制
Half-Life 时间惩罚减半
到 Reuse 阈值才再次通告
```

常用于：

- 客户 Peer 抖动
- 不稳定的 eBGP
- iBGP 不建议启用（影响收敛）

### 3. BFD

```text
neighbor 10.0.0.1 fall-over bfd
```

- 毫秒级故障检测
- 替代 KEEPALIVE + Hold Timer 的慢检测
- 链路层需支持或进程级实现

### 4. Peer Group / Peer Template

批量配置，减少策略变更同步风险：

```text
neighbor GROUP_PEERS peer-group
neighbor GROUP_PEERS remote-as 65001
neighbor GROUP_PEERS route-map SET_LP in
neighbor 10.0.0.1 peer-group GROUP_PEERS
neighbor 10.0.0.2 peer-group GROUP_PEERS
```

---

## 十五、IPv6 BGP (MP-BGP)

### 1. MP_REACH_NLRI / MP_UNREACH_NLRI

- 通过 AFI / SAFI 携带 IPv6、VPNv4、VPNv6、FlowSpec 等
- 使用属性 14 / 15 替代传统 NLRI

```text
AFI = 2   IPv6
SAFI = 1  Unicast
AFI = 1   IPv4
SAFI = 4  MPLS Labels
AFI = 1
SAFI = 128 MPLS-labeled VPN
```

### 2. IPv6 Peer 配置

```text
neighbor 2001:db8::1 remote-as 65001
address-family ipv6
 neighbor 2001:db8::1 activate
 neighbor 2001:db8::1 route-map IPv6-IN in
```

### 3. IPv6 AS_PATH 处理

- AS_PATH 与 IPv4 共用格式
- AS_CONFED_* 标识联盟子 AS
- AS4_PATH / AS4_AGGREGATOR 兼容 4 字节 ASN

### 4. Next Hop

- IPv6 邻居默认下一跳是链路本地地址（启用 `next-hop-self` 可改为全球地址）
- RR 场景下 iBGP 中常用 `next-hop-self`

---

## 十六、BGP 与 IGP 交互

### 1. 互操作问题

- BGP 依赖 IGP 提供 Next Hop 可达性
- iBGP 全互联或 RR 需要 IGP 内部互通
- 重发布 (Redistribution) 会引发路径选择与环路

### 2. 重发布场景

```text
OSPF → BGP
  network 命令
  redistribute ospf X route-map OSPF-to-BGP

BGP → OSPF
  redistribute bgp X route-map BGP-to-OSPF
```

应避免双向重发布不收敛造成环路，使用 Tag、Metric、Route-Map 控制。

### 3. 默认路由

| 方式 | 用途 |
| ---- | ---- |
| **default-information originate** | iBGP / eBGP 下发默认路由 |
| **neighbor default-originate** | 向特定邻居通告默认路由 |
| **静态默认路由 + network 0.0.0.0** | 本地产生默认路由 |
| **conditional default-originate** | 依赖条件（如另一路由存在） |

### 4. Next-Hop 递归

```text
BGP 路由：10.0.0.0/8  NEXT_HOP=192.168.1.1
        │
        ▼
需要 IGP 提供 192.168.1.1/32 或接口内路由
```

Next-Hop 不可达时，BGP 路由虽收到但不可用，应关注：

- IGP 是否覆盖了 Peer 的互联地址
- 是否需要使用 `next-hop-self`
- RR 上是否需要 `next-hop-self`

---

## 十七、常见默认值与调优

### 1. 定时器

| 参数 | 默认 |
| ---- | ---- |
| **Hold Time** | 180s |
| **KEEPALIVE** | 60s |
| **Connect Retry** | 120s |
| **Advertisement Interval** | eBGP 30s / iBGP 0 |
| **Originate Interval** | 15s |
| **MinASOrigination** | 15s |

`neighbor X timers 30 90` 可同时修改 KEEPALIVE 与 Hold Time（30/90）。

### 2. 自动汇总

- 部分厂商默认启用 Auto-Summary，但仅在 EIGRP / RIP 等 Classful 协议下显著
- 现代部署强烈建议关闭：`no auto-summary` / `no synchronization`

### 3. 同步 (Synchronization)

- 历史规则：iBGP 学到的路由不应在 IGP 同步前通告给 eBGP
- 现代网络中通过全互联或 RR 解决，默认关闭即可
- 早期 Cisco 平台默认开启，需手动关闭

### 4. 资源限制

| 限制 | 典型值 |
| ---- | ------ |
| **每 Peer 最大前缀** | 部署上限 80 万—200 万 |
| **全局 BGP 容量** | 平台 / IOS / 内存决定 |
| **Update 组** | 共享同一 out-policy 的 Peer |

---

## 十八、抓包分析

### 1. tcpdump

```bash
# 抓 BGP 报文
sudo tcpdump -i any -n -s 0 -w bgp.pcap 'tcp port 179'

# 同时显示内容
sudo tcpdump -i any -n -vvv 'tcp port 179'
```

### 2. Wireshark 过滤器

```text
bgp
bgp.type == 2                        UPDATE
bgp.type == 1                        OPEN
bgp.type == 4                        KEEPALIVE
bgp.type == 5                        ROUTE-REFRESH
bgp.type == 3                        NOTIFICATION
bgp.update.nlri                      NLRI
bgp.update.withdrawn                 Withdrawn Routes
bgp.as_path                                           AS_PATH
bgp.community                                        COMMUNITY
bgp.next_hop                                          NEXT_HOP
bgp.mp_reach_nlri_ipv6_prefix                        IPv6 NLRI
```

### 3. BGP 表导出

```text
R1# show ip bgp
R1# show ip bgp 10.0.0.0/8
R1# show ip bgp neighbors 10.0.0.1
R1# show ip bgp neighbors 10.0.0.1 routes
```

### 4. bgpdump / RIPE RIS

```bash
# RIPE RIS 数据
bgpdump -m rib.20250701.0000.gz
```

```bash
# BIRD show 协议
birdc show route
birdc show protocols all bgp1
```

### 5. 关键字段

| 字段 | 分析价值 |
| ---- | -------- |
| BGP Identifier | Router-ID 与预期是否一致 |
| AS_PATH | 是否包含预期 AS，是否回环 |
| NEXT_HOP | 是否被 next-hop-self 改写 |
| ORIGIN | 来源是否标注正确 |
| Community | 策略是否生效 |
| LocalPref | iBGP 内策略影响 |
| MED | 入向影响 |

---

## 十九、Linux 与开源工具

### 1. BIRD

```text
router id 1.2.3.4;

protocol bgp my_peer {
  local as 65001;
  neighbor 10.0.0.1 as 65002;
  hold time 90;
  keepalive time 30;
  ipv4 {
    import filter { ... };
    export filter { ... };
  };
}
```

常用命令：

```bash
birdc show route
birdc show route 10.0.0.0/8
birdc show protocols
birdc reload
```

### 2. FRR (Quagga 继任)

```text
router bgp 65001
 neighbor 10.0.0.1 remote-as 65002
 address-family ipv4 unicast
  network 10.10.0.0/16
  neighbor 10.0.0.1 activate
  neighbor 10.0.0.1 route-map AS65002-IN in
 exit-address-family
```

常用命令：

```bash
vtysh -c 'show ip bgp'
vtysh -c 'show ip bgp summary'
vtysh -c 'show ip bgp neighbors'
```

### 3. GoBGP / ExaBGP

- 用于控制平面测试、监控注入、Route Server
- ExaBGP 通过 JSON 配置注入路由，适合网络测试
- GoBGP 常用于 SDN 与编排系统

### 4. bgpq4 / bgpq3

```bash
bgpq4 -h whois.radb.net AS65001
```

根据 IRR 数据库自动生成 prefix-list / filter。

### 5. Looking Glass / Route Server

- 与 IRR / RPKI 集成
- 显示 ASN、AS-SET、ROA 等信息
- 常用工具：bgp.tools、RouteViews、PeeringDB

---

## 二十、设备命令

### 1. Cisco IOS / IOS-XE

```text
show ip bgp
show ip bgp summary
show ip bgp neighbors
show ip bgp neighbors 10.0.0.1
show ip bgp neighbors 10.0.0.1 advertised-routes
show ip bgp neighbors 10.0.0.1 received-routes
show ip bgp path 10.0.0.0 255.0.0.0
show ip bgp regexp _65001_
show ip bgp community no-export
show ip bgp dampening dampened-paths
show ip bgp update-group
debug ip bgp 10.0.0.1 updates
```

### 2. Cisco Nexus

```text
show bgp ipv4 unicast
show bgp ipv6 unicast
show bgp neighbors
show bgp community
```

### 3. 华为 VRP

```text
display bgp peer
display bgp routing-table
display bgp routing-table 10.0.0.0 8
display bgp path 10.0.0.0 255.0.0.0
display bgp community
display bgp network
display bgp update-peer
```

### 4. H3C

```text
display bgp peer
display bgp routing-table
display bgp routing-table statistic
```

### 5. Juniper JunOS

```text
show bgp summary
show route protocol bgp
show route protocol bgp 10.0.0.0/8
show bgp neighbor
show bgp neighbor 10.0.0.1
show bgp group
show policy
```

---

## 二十一、BGP 故障排查

### 1. 分层流程

```text
1. 物理层 / 链路 / 接口状态
2. IGP / Next Hop 可达性
3. TCP 179 可达性（ACL / 防火墙）
4. BGP 配置（AS 号、Peer IP、update-source）
5. 能力协商（Capability / NLRI）
6. 路由策略（route-map / prefix-list）
7. 资源与稳定（Dampening / BFD / MaxPrefix）
8. 跨厂商验证（抓包 / show 命令 / RPKI）
```

### 2. 邻居无法建立

- AS 配置不一致
- 邻居 IP 写错
- update-source 不一致
- TTL 不匹配（多跳 / ebgp-multihop）
- MD5 密码不一致
- ACL 阻挡 TCP 179
- Peer 两端能力不支持（4 字节 ASN、Add-Path）

### 3. Established 但未收到路由

- 对端没有 `network` 或重发布
- 出口策略过滤了
- 入口策略拒绝
- 最大前缀触发
- Dampening 抑制

### 4. Established 但未通告出去

- 本地策略过滤
- 对端 inbound 拒绝
- `next-hop-self` 未启用，IGP 不可达
- iBGP 全互联 / RR 配置缺失

### 5. 路由震荡

- 链路不稳定
- Peer 频繁重置
- 缺少 BFD
- Dampening 阈值过于敏感

### 6. 收到 AS_PATH 回环

- 自身 AS 出现：检查意外通告
- 联盟子 AS 出现：检查 Confederation Path
- 双向发布或配置错误

### 7. 选路不符合预期

- 检查 Weight / LocalPref
- 检查 AS_PATH / Prepend
- 检查 MED / Origin
- 检查 IGP Metric
- 检查 eBGP vs iBGP 优先级

### 8. 路由被 RPKI 判定为 Invalid

- 检查 ROA 与实际 Origin 是否一致
- 运营商或客户通告了不属于 AS 的前缀
- AS_PATH Manipulation 引发 Invalid

### 9. RR 故障

- CLUSTER_LIST 长度异常
- ORIGINATOR_ID 不一致
- 客户端 Full-Mesh 残留

### 10. 常见问题对照

| 现象 | 常见原因 | 排查重点 |
| ---- | -------- | -------- |
| 邻居 Active | IP/AS/TCP 问题 | show tcp, ACL, routing |
| 邻居 OpenSent | 参数不匹配 | Hold Time, Capability |
| 收到路由不优 | MED/LP/Origin | show ip bgp prefix |
| AS_PATH 回环 | 双向发布 | filter, RR 拓扑 |
| eBGP iBGP 选择不一致 | MED/LP/Weight | Inbound Policy |
| 路由延迟大 | IGP 收敛 / Dampening | Timers, BFD |
| 部分 Peer 不可达 | 单点路径 | IGP, BFD, 协议状态 |
| RPKI Invalid | ROA 不匹配 | RPKI 验证器 |
| 内存 / CPU 占用高 | Prefix 数量大 | Dampening, max-prefix |

---

## 二十二、BGP 设计建议

### 1. AS 编号规划

- 公有 / 私有 ASN 区分使用
- 客户 ASN 长度与可见性
- 4 字节 ASN 兼容
- 联盟子 AS 使用私有 ASN

### 2. iBGP 拓扑

| 场景 | 拓扑 |
| ---- | ---- |
| **小型网络** | iBGP Full-Mesh |
| **中等规模** | 路由反射器 RR + Client |
| **大规模** | RR Cluster + Hierarchical RR |
| **超大规模** | 联盟 + 多层 RR |

### 3. eBGP 接入

- 与多个 Transit Provider 多线接入
- 与多个 Peer 直连（IXP）
- 使用 Peer Group 降低复杂度
- 监控 AS_PATH / RPKI / BGP MON

### 4. 安全策略

- 强制 MD5 / TCP-AO
- TTL-Security 限制 eBGP Peer
- MaxPrefix 限制邻居通告数量
- 入口 / 出口双向过滤
- RPKI 验证部署 (Origin Validation)
- 定期检查 IRR 注册

### 5. 监控指标

| 指标 | 意义 |
| ---- | ---- |
| **BGP Peer 状态变化** | 稳定性 |
| **Prefix 数量** | 容量与威胁 |
| **UPDATE 速率** | 抖动检测 |
| **Dampening 命中** | 异常 Peer |
| **RPKI Invalid 数量** | 劫持 / 错误通告 |
| **Hold Time 接近超时** | 链路质量 |
| **CPU / 内存** | 控制平面负载 |
| **MaxPrefix 触发** | 邻居异常 |
| **路径属性变化** | 策略生效 |

### 6. 高可用设计

- 同一 Peer 多条链路（BFD）
- 同一 AS 多 RR Cluster
- 跨地理位置 iBGP 多路径
- eBGP 多 Transit 出口
- 必要时使用 Add-Path 提升多路径利用率

---

## 二十三、eBGP 与 iBGP 对比

| 维度 | eBGP | iBGP |
| ---- | ---- | ---- |
| 对端 AS | 不同 | 相同 |
| 默认 TTL | 1 | 255 |
| 默认 Next Hop | 发送方接口 | 沿用 / next-hop-self |
| AS_PATH 防环 | 是 | 否（水平分割） |
| LocalPref | 不携带 | 携带 |
| MED | 通告 | 在 AS 内部比较 |
| 需要全互联 | 否 | 默认需要（RR 例外） |
| Dampening | 常用 | 少见 |
| 主要场景 | AS 间互连 | AS 内部传递 |
| 大前缀限制 | 严格 | 较宽松 |

---

## 二十四、MP-BGP 与地址族扩展

### 1. 常见 AFI / SAFI

| AFI | SAFI | 含义 |
| --- | ---- | ---- |
| 1 | 1 | IPv4 Unicast |
| 1 | 2 | IPv4 Multicast |
| 1 | 4 | IPv4 Labeled (MPLS) |
| 1 | 128 | IPv4 VPN (VPNv4) |
| 1 | 132 | IPv4 FlowSpec |
| 2 | 1 | IPv6 Unicast |
| 2 | 4 | IPv6 Labeled |
| 2 | 128 | IPv6 VPN (VPNv6) |

### 2. 能力协商

OPEN 报文携带 Capability，常见：

| Capability | 作用 |
| ---------- | ---- |
| **Multiprotocol Extensions** | 启用 MP_REACH_NLRI |
| **Route Refresh** | 支持路由刷新 |
| **Outbound Route Filtering (ORF)** | 出口过滤前缀 |
| **4-byte ASN** | 4 字节 AS |
| **Add-Path** | 多条等价路径通告 |
| **Graceful Restart** | 控制平面重启数据不中断 |
| **Enhanced Route Refresh** | 增强路由刷新 |
| **Long-lived Graceful Restart (LLGR)** | 长时 GR |

### 3. 跨 AFI / SAFI 路由

VPNv4 路由格式：

```text
RD + IPv4 Prefix
例：65001:100 || 10.0.0.0/8
```

RT 与 SOO 等扩展团体携带在 MP_REACH_NLRI 路径属性中。

---

## 二十五、核心要点速记

- **BGP 是路径向量协议，基于 TCP 179**
- **eBGP 防环依靠 AS_PATH，iBGP 防环依靠水平分割**
- **OPEN 协商 AS、Hold Time、Router-ID 与 Capability**
- **KEEPALIVE 默认 60 秒发一次，Hold 默认 180 秒**
- **UPDATE 同时携带 NLRI、撤销路由和路径属性**
- **ROUTE-REFRESH 用于策略变更后刷新**
- **NOTIFICATION 表示错误并拆链**
- **Well-known Mandatory 属性必须识别且随路由传递**
- **ORIGIN 优先级：IGP > EGP > Incomplete**
- **LocalPref 影响 AS 内出向选路，默认 100，越大越优**
- **MED 影响 AS 间入向选路，默认 0，越小越优**
- **AS_PATH 长度是最常见策略工具，Prepend 可人为加长**
- **Weight 是 Cisco 私有的本地优先级**
- **选路顺序：Weight > LocalPref > 本地产生 > AS_PATH > Origin > MED > eBGP/iBGP > IGP Metric**
- **团体属性用于 AS 间协调，标准 32 位、扩展 8 字节、大 12 字节**
- **no-export/no-advertise/no-export-subconfed 控制通告范围**
- **iBGP 默认全互联，RR 用 ORIGINATOR_ID + CLUSTER_LIST 防环**
- **联盟使子 AS 之间使用类似 eBGP 的防环**
- **MaxPrefix 防止邻居通告过多导致资源耗尽**
- **Dampening 抑制路由抖动，常用于 eBGP**
- **BFD 提供毫秒级故障检测，替代慢 KEEPALIVE**
- **MP-BGP 通过 AFI/SAFI 扩展支持 IPv6 / VPN**
- **GTSM (TTL-Security) 防止远程伪造 eBGP 报文**
- **MD5 / TCP-AO 提供 TCP 完整性保护**
- **RPKI 用于 Origin Validation，可识别劫持**
- **BGP 不主动发现邻居，必须静态指定 Peer IP**
- **BGP 不依赖 IGP 收敛路径，但需 IGP 提供 Next Hop 可达**
- **IGP 与 BGP 之间重发布易形成环路，应使用 Tag**
- **常见故障：邻居 Active、OpenSent、Hold Expired、Invalid Origin、eBGP/iBGP 选路不一致**
- **排障先看 Peer 状态，再查 Capability、Policy、Next Hop 可达性**
- **RR / 联盟 / Add-Path 是扩展 iBGP 的关键手段**
- **生产环境建议部署 RPKI + MaxPrefix + Dampening + BFD**
- **运营商应双向过滤，配合 IRR 与 ROA 维持全球路由表健康**
