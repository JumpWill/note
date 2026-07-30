# DHCP 协议 (Dynamic Host Configuration Protocol)

## 一、DHCP 概述

### 什么是 DHCP

**DHCP (Dynamic Host Configuration Protocol，动态主机配置协议)**：为网络终端自动分配 IP 地址和其他网络参数的应用层协议。

DHCP 可以下发：

- IPv4 地址和子网掩码
- 默认网关
- DNS 服务器和搜索域
- 地址租期
- NTP、静态路由、PXE 启动等可选参数

```text
终端接入网络
    ↓
自动寻找 DHCP 服务器
    ↓
获得 IP、掩码、网关、DNS、租期
    ↓
开始正常通信
```

### 为什么需要 DHCP

如果没有 DHCP，每台设备都需要手动配置：

```text
IP 地址
子网掩码
默认网关
DNS 服务器
```

设备数量增加后容易出现：

- IP 地址冲突
- 网关或 DNS 配置错误
- 地址浪费
- 终端迁移后无法通信
- 运维成本过高

### DHCP 的特点

- 基于客户端—服务器模型
- IPv4 DHCP 使用 UDP 67/68
- 初始阶段可通过广播通信
- 地址具有租期，可回收复用
- 支持跨网段 Relay
- 基于 BOOTP 扩展而来
- 不提供强身份认证，需配合交换机安全机制

### DHCP 角色

| 角色 | 作用 |
| ---- | ---- |
| **DHCP Client** | 请求并使用网络配置 |
| **DHCP Server** | 管理地址池和下发配置 |
| **DHCP Relay Agent** | 在不同网段间转发 DHCP 报文 |
| **交换机安全功能** | DHCP Snooping、IP Source Guard 等 |

---

## 二、DHCP 端口与通信方式

### 1. IPv4 DHCP 端口

| 方向 | 源端口 | 目的端口 |
| ---- | ------ | -------- |
| 客户端 → 服务器 | UDP 68 | UDP 67 |
| 服务器 → 客户端 | UDP 67 | UDP 68 |
| Relay → 服务器 | UDP 67 | UDP 67 |

### 2. 初始广播

客户端刚接入网络时通常：

- 没有可用 IP 地址
- 不知道 DHCP 服务器地址
- 不一定知道自己所在子网

因此首次 Discover 常使用：

```text
源 IP:   0.0.0.0
目的 IP: 255.255.255.255
源端口:  UDP 68
目的端口:UDP 67
源 MAC:  客户端 MAC
目的 MAC:FF:FF:FF:FF:FF:FF
```

### 3. 广播与单播

DHCP 报文是否广播取决于：

- 客户端当前状态
- DHCP Header 的 Broadcast Flag
- 客户端是否已能接收单播
- Server 与 Relay 的实现
- 网络接口和操作系统能力

初始 Discover 和选择 Offer 的 Request 通常广播；续租时客户端通常直接单播给原 DHCP Server。

### 4. 广播不能跨路由器

路由器默认不会转发二层广播，因此：

```text
客户端 VLAN 10 ── 路由器 ── DHCP Server VLAN 100
```

需要在客户端网关接口配置 **DHCP Relay**，把广播转换为发往服务器的单播。

---

## 三、DORA 四步过程

### 1. DORA

客户端首次获取 IPv4 地址的典型过程：

```text
客户端                                      DHCP 服务器
  │                                             │
  │ DHCPDISCOVER                                │
  ├────────────────────────────────────────────→│
  │                                             │
  │ DHCPOFFER                                   │
  │←────────────────────────────────────────────┤
  │                                             │
  │ DHCPREQUEST                                 │
  ├────────────────────────────────────────────→│
  │                                             │
  │ DHCPACK                                     │
  │←────────────────────────────────────────────┤
  │                                             │
  │               地址租用成功                  │
```

```text
D = Discover
O = Offer
R = Request
A = Acknowledge
```

### 2. DHCPDISCOVER

客户端寻找可用服务器：

```text
客户端:“网络中有 DHCP Server 吗?”
```

常见内容：

- Transaction ID
- 客户端 MAC 或 Client Identifier
- Parameter Request List
- Host Name
- 客户端支持的最大报文大小
- 请求的 IP 地址（某些状态下）

### 3. DHCPOFFER

一台或多台服务器返回可用配置：

```text
服务器:“可以给你 192.168.1.100，租期 8 小时”
```

通常包含：

- Offered IP (`yiaddr`)
- Server Identifier
- Subnet Mask
- Router
- DNS Server
- Lease Time
- T1 / T2

Offer 只是提议，地址尚未最终确认给客户端使用。

### 4. DHCPREQUEST

客户端从一个或多个 Offer 中选择一个，并广播 Request：

```text
客户端:“我选择服务器 192.168.1.2 提供的 192.168.1.100”
```

常见 Option：

```text
Requested IP Address = 192.168.1.100
Server Identifier    = 192.168.1.2
```

广播 DHCPREQUEST 可以让其他 DHCP Server 知道自己的 Offer 未被选择，并释放预留资源。

### 5. DHCPACK

被选择的服务器确认租约：

```text
服务器:“192.168.1.100 正式租给你”
```

客户端收到 ACK 后通常会：

1. 保存租约
2. 检测地址冲突
3. 配置 IP 和路由
4. 发送 Gratuitous ARP / ARP Announcement
5. 开始使用地址

### 6. DHCPNAK

服务器发现客户端请求无效时返回 NAK：

- 地址不属于当前网段
- 租约已经失效
- 客户端从其他网络带来旧地址
- 请求地址不再可用

客户端收到 DHCPNAK 后应停止使用该地址，重新从 DHCPDISCOVER 开始。

---

## 四、DHCP 报文类型

### 1. 常见类型

| 类型 | 方向 | 作用 |
| ---- | ---- | ---- |
| **DHCPDISCOVER** | Client → Server | 发现服务器 |
| **DHCPOFFER** | Server → Client | 提供地址和配置 |
| **DHCPREQUEST** | Client → Server | 选择、确认或续租地址 |
| **DHCPACK** | Server → Client | 确认租约 |
| **DHCPNAK** | Server → Client | 拒绝请求，要求重新获取 |
| **DHCPDECLINE** | Client → Server | 客户端发现地址冲突 |
| **DHCPRELEASE** | Client → Server | 主动释放租约 |
| **DHCPINFORM** | Client → Server | 已有 IP，只请求其他参数 |
| **DHCPFORCERENEW** | Server → Client | 要求客户端立即续租 |

### 2. DHCPDECLINE

客户端发现服务器提供的地址已被使用：

```text
客户端 → DHCPDECLINE → 服务器
```

服务器通常会把该地址临时标记为冲突，不再立即分配，并等待管理员检查或探测恢复。

### 3. DHCPRELEASE

客户端主动释放地址：

```text
客户端 → 单播 DHCPRELEASE → Server
```

设备断电、拔线或异常退出时通常无法发送 Release，因此服务器仍需依靠租期回收地址。

### 4. DHCPINFORM

客户端已经通过静态配置等方式拥有 IP，只想获取：

- DNS
- NTP
- 域名
- 其他 DHCP Option

DHCPINFORM 不用于分配新的 IPv4 地址。

### 5. DHCPFORCERENEW

服务器通知客户端提前执行续租，常用于：

- 网关或 DNS 变更
- 网络策略更新
- 集中触发配置刷新

该机制需要客户端支持，并应考虑认证和伪造报文风险。

---

## 五、DHCP 报文格式

### 1. 基本结构

DHCP 沿用 BOOTP 固定头部，并增加 Magic Cookie 和可变 Options：

```text
+---------------------------------------+
| op | htype | hlen | hops              |
+---------------------------------------+
| xid                                   |
+---------------------------------------+
| secs              | flags             |
+---------------------------------------+
| ciaddr                                |
+---------------------------------------+
| yiaddr                                |
+---------------------------------------+
| siaddr                                |
+---------------------------------------+
| giaddr                                |
+---------------------------------------+
| chaddr (16 bytes)                     |
+---------------------------------------+
| sname (64 bytes)                      |
+---------------------------------------+
| file (128 bytes)                      |
+---------------------------------------+
| Magic Cookie: 99 130 83 99            |
+---------------------------------------+
| DHCP Options                          |
+---------------------------------------+
```

### 2. 固定字段

| 字段 | 长度 | 含义 |
| ---- | ---- | ---- |
| **op** | 1 字节 | 1=Request，2=Reply |
| **htype** | 1 字节 | 硬件类型，以太网为 1 |
| **hlen** | 1 字节 | 硬件地址长度，以太网为 6 |
| **hops** | 1 字节 | Relay 转发跳数 |
| **xid** | 4 字节 | Transaction ID，匹配请求和响应 |
| **secs** | 2 字节 | 客户端开始获取地址后的秒数 |
| **flags** | 2 字节 | 最高位为 Broadcast Flag |
| **ciaddr** | 4 字节 | 客户端当前 IP |
| **yiaddr** | 4 字节 | “Your IP”，分配给客户端的 IP |
| **siaddr** | 4 字节 | 下一服务器地址，常用于引导 |
| **giaddr** | 4 字节 | Relay Agent 地址 |
| **chaddr** | 16 字节 | 客户端硬件地址字段 |
| **sname** | 64 字节 | 可选服务器名称 |
| **file** | 128 字节 | 启动文件名等 |

### 3. Transaction ID

客户端为一次获取过程选择随机的 `xid`：

```text
Discover xid=0x12345678
Offer    xid=0x12345678
Request  xid=0x12345678
ACK      xid=0x12345678
```

客户端借此区分自己的响应和网络中其他客户端的 DHCP 报文。

### 4. Magic Cookie

```text
十进制:99 130 83 99
十六进制:63 82 53 63
```

用于标识后续内容为 DHCP Options。

### 5. Option 格式

大多数 Option：

```text
Code | Length | Value
```

特殊 Option：

- 0：Pad
- 255：End

---

## 六、常见 DHCP Option

| Option | 名称 | 作用 |
| ------ | ---- | ---- |
| **1** | Subnet Mask | 子网掩码 |
| **3** | Router | 默认网关 |
| **6** | Domain Name Server | DNS 服务器 |
| **12** | Host Name | 客户端主机名 |
| **15** | Domain Name | 本地域名 |
| **28** | Broadcast Address | 广播地址 |
| **42** | NTP Servers | NTP 服务器 |
| **43** | Vendor Specific | 厂商自定义参数 |
| **50** | Requested IP Address | 客户端请求的 IP |
| **51** | IP Address Lease Time | 租期 |
| **52** | Option Overload | Options 延伸到 sname/file |
| **53** | DHCP Message Type | Discover、Offer 等类型 |
| **54** | Server Identifier | DHCP Server 标识 |
| **55** | Parameter Request List | 客户端希望获得的 Option |
| **57** | Maximum DHCP Message Size | 客户端可接收的最大报文 |
| **58** | Renewal Time T1 | 续租时间 |
| **59** | Rebinding Time T2 | 重绑定时间 |
| **60** | Vendor Class Identifier | 客户端厂商类别 |
| **61** | Client Identifier | 客户端身份标识 |
| **66** | TFTP Server Name | TFTP 服务器名 |
| **67** | Bootfile Name | PXE 启动文件 |
| **81** | Client FQDN | 客户端完整域名和 DNS 更新信息 |
| **82** | Relay Agent Information | Relay 注入的接入位置信息 |
| **119** | Domain Search | DNS 搜索域列表 |
| **121** | Classless Static Route | 无类别静态路由 |

### Option 3 与 Option 121

客户端同时收到无类别静态路由时，路由处理应遵循相关标准和客户端实现。使用 Option 121 时应明确包含所需默认路由，避免只下发部分路由后默认网关行为与预期不同。

### PXE 启动

DHCP 可告诉客户端：

```text
下一服务器
启动文件名
厂商特定启动参数
```

真正的启动文件通常通过 TFTP、HTTP 等协议传输，DHCP 本身不负责传输操作系统镜像。

---

## 七、租约与客户端状态机

### 1. 租约

DHCP 地址不是永久分配，而是在一定时间内租给客户端：

```text
Address: 192.168.1.100
Lease:   8 hours
T1:      4 hours
T2:      7 hours
```

### 2. 主要状态

| 状态 | 含义 |
| ---- | ---- |
| **INIT** | 尚无地址，准备发送 Discover |
| **SELECTING** | 等待并选择 Offer |
| **REQUESTING** | 已选择 Offer，等待 ACK |
| **BOUND** | 地址租用成功 |
| **RENEWING** | 向原服务器续租 |
| **REBINDING** | 向任意服务器广播续租 |
| **INIT-REBOOT** | 重启后尝试确认之前的地址 |

### 3. T1 续租

若服务器未指定，T1 常默认为租期的 50%：

```text
到达 T1
  ↓
客户端单播 DHCPREQUEST 给原服务器
  ↓
收到 DHCPACK
  ↓
租期刷新，回到 BOUND
```

### 4. T2 重绑定

若服务器未指定，T2 常默认为租期的 87.5%：

```text
原服务器没有响应
  ↓
到达 T2
  ↓
客户端广播 DHCPREQUEST
  ↓
任意合适服务器可以响应
```

### 5. 租约到期

在到期前始终没有得到 ACK：

```text
客户端必须停止使用地址
        ↓
回到 INIT
        ↓
重新发送 DHCPDISCOVER
```

### 6. INIT-REBOOT

客户端重启后保存有旧租约时，可发送 DHCPREQUEST 询问旧地址是否仍可使用：

- 服务器 ACK：继续使用
- 服务器 NAK：重新 DORA
- 长时间无响应：按客户端策略重新发现或尝试使用仍有效的租约

---

## 八、地址分配方式

### 1. 动态分配

```text
客户端从地址池临时获得地址
租期到期后地址可回收
```

适合普通终端、无线客户端和访客设备。

### 2. 自动分配

服务器从地址池分配地址，并倾向长期保留给客户端。具体行为由服务端实现决定，现代部署更常使用动态租约或 Reservation。

### 3. Reservation / Static Mapping

根据客户端标识固定分配地址：

```text
MAC / Client ID → 固定 IP
```

适合：

- 打印机
- 服务器管理口
- 网络设备
- 需要地址稳定的终端

Reservation 仍通过 DHCP 下发参数，比在终端手工配置静态 IP 更便于集中管理。

### 4. 地址池规划

```text
网段:192.168.10.0/24
网关:192.168.10.1
静态保留:192.168.10.2-49
动态地址池:192.168.10.50-220
基础设施预留:192.168.10.221-254
```

应避免 DHCP 地址池与手工静态地址重叠。

### 5. 地址选择依据

服务器可能依据以下信息选择 Scope/Pool：

- 接收接口
- Relay 的 `giaddr`
- Option 82
- Client Identifier
- MAC 地址
- Vendor Class
- User Class
- 策略或租约数据库

---

## 九、DHCP Relay

### 1. 为什么需要 Relay

```text
VLAN 10 Client ── 三层网关 ── DHCP Server
VLAN 20 Client ── 三层网关 ── DHCP Server
```

每个 VLAN 不需要部署独立 DHCP Server，只需在网关配置 Relay。

### 2. Relay 工作过程

```text
1. 客户端广播 DHCPDISCOVER
2. Relay 收到广播
3. Relay 填写 giaddr
4. Relay 单播转发给 DHCP Server
5. Server 根据 giaddr 选择地址池
6. Server 回复 Relay
7. Relay 把响应送回客户端所在网段
```

### 3. giaddr

`giaddr` 通常设置为 Relay 面向客户端网段的接口地址：

```text
giaddr = 192.168.10.1
```

服务器据此判断客户端来自 `192.168.10.0/24`，并选择对应 Scope。

### 4. Cisco Relay 示例

```text
interface Vlan10
 ip address 192.168.10.1 255.255.255.0
 ip helper-address 10.0.0.10
```

`ip helper-address` 可能默认转发多种 UDP 广播协议，生产环境应理解设备行为并按需限制。

### 5. Linux Relay 示例

```bash
dhcrelay -4 -i eth-client -i eth-server 10.0.0.10
```

具体参数取决于所使用的 ISC DHCP Relay 或 Kea Relay 实现。

### 6. Relay 冗余

一个客户端网关可以配置多个 DHCP Server 地址：

```text
ip helper-address 10.0.0.10
ip helper-address 10.0.0.11
```

Relay 会向多个服务器转发，最终由客户端选择 Offer。服务器之间仍应正确协调地址池和租约状态。

---

## 十、Option 82

### 1. 什么是 Option 82

**Relay Agent Information Option**：由可信 Relay 或接入交换机加入，用于描述客户端接入位置。

常见子选项：

| 子选项 | 作用 |
| ------ | ---- |
| **Circuit ID** | 交换机端口、VLAN、逻辑电路 |
| **Remote ID** | 交换机、Relay 或用户标识 |

### 2. 应用场景

- 按端口或 VLAN 分配地址
- 宽带用户识别
- DHCP Snooping 绑定
- 审计客户端接入位置
- 防止客户端冒充其他接入点

### 3. 信任边界

客户端不应能任意伪造 Option 82。接入设备应：

- 在不可信端口丢弃或覆盖客户端自带 Option 82
- 仅信任上联和合法 Relay
- 保证插入与剥离策略一致
- 与 DHCP Server 的策略匹配

### 4. 配置错误的表现

- 所有客户端无法获得地址
- Server 没有匹配地址池
- 同一端口反复 NAK
- Relay 回复找不到原客户端
- 不同厂商对 Option 82 格式理解不一致

---

## 十一、DHCP Server 部署

### 1. 单服务器

```text
Client → DHCP Server
```

部署简单，但服务器或网络路径故障会影响新终端和续租。

### 2. Split Scope

两个服务器管理同一网段的不同地址范围：

```text
Server A:192.168.1.50-150
Server B:192.168.1.151-220
```

优点：实现简单。

限制：租约状态通常不同步，地址池利用率和故障恢复不如真正 HA。

### 3. DHCP Failover / HA

两台服务器同步租约状态：

- Load Balance
- Hot Standby
- 状态复制
- Partner Down 等故障状态

具体能力取决于 Kea、Windows DHCP、ISC DHCP 等实现，不同产品的 HA 协议并不完全相同。

### 4. 租约数据库

服务器应持久化：

- Client Identifier / MAC
- 分配地址
- 开始和到期时间
- 租约状态
- Relay/Option 82 信息
- 主机名和策略信息

丢失租约数据库可能导致地址重复分配。

### 5. 时间同步

DHCP Server 的时钟应正确同步。时间跳变可能影响：

- 租约到期判断
- HA 状态同步
- 日志关联
- 动态 DNS 更新

---

## 十二、DHCP 配置示例

### 1. dnsmasq

```text
interface=eth0
dhcp-range=192.168.10.50,192.168.10.200,255.255.255.0,8h
dhcp-option=option:router,192.168.10.1
dhcp-option=option:dns-server,192.168.10.1,1.1.1.1
dhcp-host=AA:BB:CC:DD:EE:FF,192.168.10.20,printer,infinite
```

适合实验、小型网络和嵌入式设备。

### 2. Kea DHCPv4

```json
{
  "Dhcp4": {
    "interfaces-config": {
      "interfaces": ["eth0"]
    },
    "lease-database": {
      "type": "memfile"
    },
    "subnet4": [
      {
        "subnet": "192.168.10.0/24",
        "pools": [
          {"pool": "192.168.10.50-192.168.10.200"}
        ],
        "option-data": [
          {"name": "routers", "data": "192.168.10.1"},
          {"name": "domain-name-servers", "data": "192.168.10.1, 1.1.1.1"}
        ]
      }
    ]
  }
}
```

应用配置前应使用对应版本的 Kea 配置检查工具验证语法。

### 3. Cisco DHCP Server

```text
ip dhcp excluded-address 192.168.10.1 192.168.10.49
!
ip dhcp pool VLAN10
 network 192.168.10.0 255.255.255.0
 default-router 192.168.10.1
 dns-server 192.168.10.2 1.1.1.1
 lease 0 8
```

### 4. Reservation

不同服务器可能使用：

- MAC 地址
- DHCP Client Identifier
- DUID
- Option 82

客户端实际发送 Client Identifier 时，服务器未必只按网卡 MAC 匹配，排障时应抓包确认识别键。

---

## 十三、DHCP Snooping

### 1. Rogue DHCP Server

未经授权的 DHCP Server 可能给客户端下发：

- 恶意默认网关
- 恶意 DNS
- 错误地址和掩码
- 极短租期

结果可能是中间人攻击或大面积断网。

### 2. DHCP Snooping 原理

交换机将端口分为：

| 端口 | 说明 |
| ---- | ---- |
| **Trusted** | 允许服务器方向的 Offer/ACK 等报文 |
| **Untrusted** | 普通客户端端口，不允许伪造服务器响应 |

工作过程：

```text
1. 客户端端口发送 Discover/Request
2. 交换机允许并记录交互
3. 只有 Trusted 端口可进入 Offer/ACK
4. 交换机建立 IP-MAC-VLAN-Port-Lease 绑定表
```

### 3. DHCP Snooping Binding

```text
MAC                IP              VLAN  Port       Lease
AA:BB:CC:DD:EE:FF  192.168.10.100  10    Gi1/0/5    28000
```

绑定表可供以下功能使用：

- Dynamic ARP Inspection
- IP Source Guard
- Option 82

### 4. Cisco 示例

```text
ip dhcp snooping
ip dhcp snooping vlan 10,20
!
interface GigabitEthernet1/0/48
 ip dhcp snooping trust
!
interface range GigabitEthernet1/0/1-47
 ip dhcp snooping limit rate 20
```

上联、合法 DHCP Server 或 Relay 所在端口通常设为 Trusted。信任错误的客户端端口会削弱防护。

### 5. 绑定表持久化

交换机重启后如果绑定表丢失，DAI 和 IP Source Guard 可能误丢弃合法流量。生产环境应按设备能力配置安全的数据库持久化和恢复机制。

---

## 十四、DHCP 安全

### 1. DHCP Starvation

攻击者伪造大量不同客户端标识请求租约，耗尽地址池。

防护：

- DHCP Snooping 速率限制
- Port Security
- 802.1X / NAC
- 每端口或每用户地址限制
- 监控异常租约增长
- 合理的租期与地址池容量

### 2. Rogue DHCP

防护：

- DHCP Snooping
- 只信任合法上联端口
- 网络准入控制
- 监控多个 Server Identifier
- 关闭或隔离私接路由器

### 3. Client Identifier 伪造

MAC 和传统 Client Identifier 容易伪造，不能作为强身份认证。需要身份绑定时应使用：

- 802.1X
- NAC
- 接入端口身份
- 证书
- 受信 Option 82

### 4. Option 82 注入

- 不可信端口不接受客户端自带 Option 82
- Relay 信息只应由受信设备添加
- Server 应只信任已知 Relay 来源

### 5. DHCP 不加密

DHCP 配置信息通常明文传输。不要通过自定义 Option 下发密码、Token 或其他敏感信息。

---

## 十五、IPv4 地址冲突检测

### 1. 客户端检测

收到 DHCPACK 后，客户端可能使用 ARP Probe 检查地址：

```text
Sender IP = 0.0.0.0
Target IP = 待使用地址
```

如果发现其他设备响应：

```text
发送 DHCPDECLINE
停止使用该地址
重新获取
```

### 2. Server Ping Check

部分 DHCP Server 在分配地址前通过 ICMP Echo 检查是否已被使用。

限制：

- 主机可能禁用 ICMP
- 检查与实际使用之间存在竞态
- 增加分配延迟
- 不能代替正确的地址管理

### 3. 常见冲突原因

- 静态地址落在动态地址池内
- 多台 DHCP Server 地址池重叠且未同步
- 租约数据库丢失
- 克隆虚拟机导致 Client Identifier 重复
- 客户端忽略 DHCPNAK
- Relay/Scope 选择错误

---

## 十六、DHCPv6

### 1. DHCPv6 端口

| 方向 | 源端口 | 目的端口 |
| ---- | ------ | -------- |
| Client → Server/Relay | UDP 546 | UDP 547 |
| Server/Relay → Client | UDP 547 | UDP 546 |
| Relay → Server | UDP 547 | UDP 547 |

### 2. DHCPv6 不使用广播

IPv6 没有广播，DHCPv6 使用组播和单播。

常见组播地址：

```text
ff02::1:2  All_DHCP_Relay_Agents_and_Servers（链路范围）
ff05::1:3  All_DHCP_Servers（站点范围）
```

### 3. 基本四步

```text
客户端                                      DHCPv6 Server
  │                                             │
  │ SOLICIT                                     │
  ├────────────────────────────────────────────→│
  │                                             │
  │ ADVERTISE                                   │
  │←────────────────────────────────────────────┤
  │                                             │
  │ REQUEST                                     │
  ├────────────────────────────────────────────→│
  │                                             │
  │ REPLY                                       │
  │←────────────────────────────────────────────┤
```

Rapid Commit 可在双方支持时简化为：

```text
SOLICIT → REPLY
```

### 4. 常见 DHCPv6 消息

| 消息 | 作用 |
| ---- | ---- |
| **SOLICIT** | 发现 Server |
| **ADVERTISE** | Server 提供配置 |
| **REQUEST** | 选择 Server 并请求配置 |
| **CONFIRM** | 确认地址是否仍适合当前链路 |
| **RENEW** | 向原 Server 续租 |
| **REBIND** | 向任意 Server 重绑定 |
| **REPLY** | Server 响应 |
| **RELEASE** | 释放地址/前缀 |
| **DECLINE** | 报告地址冲突 |
| **RECONFIGURE** | Server 要求客户端更新配置 |
| **INFORMATION-REQUEST** | 只请求无状态参数 |
| **RELAY-FORW / RELAY-REPL** | Relay 封装与回复 |

### 5. DUID 与 IAID

DHCPv6 通常使用：

- **DUID**：标识客户端或服务器
- **IAID**：标识客户端中的网络接口/身份关联
- **IA_NA**：非临时地址关联
- **IA_TA**：临时地址关联
- **IA_PD**：前缀委派

身份不再简单依赖 IPv6 接口的 MAC 地址。

### 6. DHCPv6 不下发默认网关

IPv6 默认路由通常通过 **Router Advertisement (RA)** 获得，而不是 DHCPv6 Option。

```text
RA → 默认网关、前缀、M/O 标志
DHCPv6 → 地址、DNS、域名、前缀委派等
```

这是 DHCPv4 与 DHCPv6 的重要区别。

---

## 十七、SLAAC、RA 与 DHCPv6

### 1. SLAAC

**SLAAC (Stateless Address Autoconfiguration)**：主机根据 RA 中的 IPv6 前缀自动生成地址。

```text
路由器发送 RA
      ↓
客户端获得前缀和默认网关
      ↓
生成 IPv6 地址并执行 DAD
```

### 2. RA 标志

| 标志 | 名称 | 常见含义 |
| ---- | ---- | -------- |
| **M** | Managed | 使用 DHCPv6 获取地址 |
| **O** | Other | 使用 DHCPv6 获取其他参数 |
| **A** | Autonomous（Prefix Option） | 允许用该前缀进行 SLAAC |

客户端具体行为还取决于操作系统策略，不能只看 M/O 标志推断所有实现。

### 3. 常见部署模式

| 模式 | 地址来源 | DNS 等参数 | 默认网关 |
| ---- | -------- | ---------- | -------- |
| SLAAC Only | RA/SLAAC | RA 的 RDNSS 等 | RA |
| Stateless DHCPv6 | RA/SLAAC | DHCPv6 | RA |
| Stateful DHCPv6 | DHCPv6 | DHCPv6 | RA |
| 混合模式 | SLAAC + DHCPv6 | RA/DHCPv6 | RA |

### 4. Prefix Delegation

**DHCPv6-PD** 用于向下游路由器分配 IPv6 前缀：

```text
ISP DHCPv6 Server
        ↓ IA_PD: 2001:db8:1234::/56
家庭路由器
        ├── LAN1 /64
        ├── LAN2 /64
        └── Guest /64
```

家庭宽带和分支网络常使用 DHCPv6-PD。

---

## 十八、APIPA 与地址获取失败

### 1. IPv4 Link-Local

客户端无法获得 DHCP 地址时，部分系统会自动配置：

```text
169.254.0.0/16
```

称为：

- IPv4 Link-Local
- APIPA（Windows 常用名称）

### 2. 特点

- 只适合本地链路通信
- 通常没有默认网关
- 不能正常访问其他网段或互联网
- 表示 DHCP 失败，但网卡和本地链路未必完全故障

### 3. IPv6 Link-Local

IPv6 接口通常总会拥有：

```text
fe80::/10
```

IPv6 Link-Local 是 IPv6 正常组成部分，不等同于 DHCPv6 故障。

### 4. 常见失败原因

- DHCP Server 不可用
- 地址池耗尽
- Relay 未配置或地址错误
- VLAN 配置错误
- UDP 67/68 被 ACL 阻断
- DHCP Snooping Trusted 端口错误
- Option 82 策略不匹配
- 客户端驱动或链路异常

---

## 十九、抓包分析

### 1. tcpdump

```bash
# 抓取 DHCPv4
sudo tcpdump -i any -n -e 'udp port 67 or udp port 68'

# 抓取 DHCPv6
sudo tcpdump -i any -n -e 'udp port 546 or udp port 547'

# 保存抓包
sudo tcpdump -i any -n -s 0 -w dhcp.pcap 'port 67 or port 68 or port 546 or port 547'
```

### 2. Wireshark 过滤器

```text
dhcp
dhcp.option.dhcp == 1
dhcp.option.dhcp == 2
dhcp.option.dhcp == 3
dhcp.option.dhcp == 5
dhcpv6
bootp
```

Wireshark 的字段名会随版本变化，`bootp` 常用于兼容 DHCPv4 解析。

### 3. DORA 抓包重点

| 报文 | 重点字段 |
| ---- | -------- |
| Discover | xid、chaddr/Client ID、Option 55 |
| Offer | yiaddr、Server ID、Lease、Router、DNS |
| Request | Requested IP、Server ID、ciaddr |
| ACK/NAK | yiaddr、Lease、T1/T2、Option 配置 |

### 4. Relay 抓包

应在两个位置同时观察：

```text
客户端 VLAN:广播 Discover
服务器网络:Relay 单播后的 Discover，检查 giaddr/Option 82
```

如果客户端侧有 Discover，服务器侧没有，问题通常在 Relay、路由或 ACL。

### 5. 多服务器

抓包中出现多个 Offer 不一定是故障。应检查：

- 是否都是授权服务器
- 地址池是否重叠
- 客户端最终选择了哪个 Server Identifier
- 未选择服务器是否正确撤销临时 Offer

---

## 二十、客户端命令

### 1. Linux

```bash
# 查看地址和路由
ip addr
ip route

# NetworkManager
nmcli device show
nmcli connection show

# systemd-networkd
networkctl status

# systemd 日志
journalctl -u NetworkManager
journalctl -u systemd-networkd
```

部分系统仍提供 `dhclient`：

```bash
sudo dhclient -v eth0
sudo dhclient -r eth0
```

实际环境可能使用 NetworkManager、systemd-networkd、dhcpcd 或其他客户端，不应同时启动多个 DHCP Client 管理同一接口。

### 2. Windows

```text
ipconfig /all
ipconfig /release
ipconfig /renew
Get-NetIPConfiguration
Get-DnsClientServerAddress
```

### 3. macOS

```bash
ipconfig getpacket en0
ipconfig getifaddr en0
networksetup -getinfo Wi-Fi
```

### 4. 查看租约

租约文件位置取决于客户端实现。排障时重点查看：

- 地址
- Server Identifier
- 开始/到期时间
- T1/T2
- Client Identifier
- 下发的 Router/DNS

---

## 二十一、服务器与网络设备命令

### 1. Cisco

```text
show ip dhcp binding
show ip dhcp pool
show ip dhcp conflict
show ip dhcp server statistics
show ip interface
show running-config | section dhcp
show ip dhcp snooping
show ip dhcp snooping binding
```

### 2. 华为

```text
display ip pool
display ip pool name VLAN10 used
display dhcp server statistics
display dhcp relay
display dhcp snooping user-bind all
```

### 3. Kea

检查：

- Kea 服务状态
- 配置校验结果
- 租约数据库连接
- Subnet/Pool 匹配
- Hook Library
- HA Partner 状态
- Server 日志中的分配原因

### 4. 交换机

```text
VLAN 和端口状态
Trunk Allowed VLAN
DHCP Snooping Trusted Port
Option 82
MAC 地址表
Snooping Binding
接口丢包和限速计数
```

---

## 二十二、DHCP 故障排查

### 1. 分层流程

```text
1. 物理层:链路、无线信号、接口状态
2. 二层:VLAN、Trunk、STP、广播是否到达
3. Relay:giaddr、helper-address、路由、ACL
4. Server:Scope、地址池、租约、策略、HA
5. 安全:DHCP Snooping、Option 82、NAC
6. 客户端:Client ID、旧租约、系统服务
7. 配置:IP、掩码、网关、DNS 是否正确
```

### 2. 没有 Discover

- 客户端 DHCP 服务未启动
- 接口未启用或链路未连接
- 客户端仍使用静态地址
- NetworkManager/networkd 配置错误
- 无线认证尚未完成

### 3. 有 Discover，没有 Offer

- DHCP Server 不可达或未启动
- Relay 未配置
- UDP 67 被 ACL 阻断
- Server 没有匹配 `giaddr` 的 Scope
- 地址池耗尽
- Server 策略拒绝 Client ID / Option 82
- Snooping 错误丢弃响应

### 4. 有 Offer，没有 Request

- Offer 没有到达客户端
- 客户端选择了另一台服务器
- Offer 参数无效
- 客户端网络栈异常
- Transaction ID 或 Client Identifier 不匹配

### 5. 有 Request，没有 ACK

- Server Identifier 错误
- 请求地址已被占用
- 租约状态冲突
- Request 没有到达被选择服务器
- ACK 被 ACL/Snooping 丢弃
- Server 返回了 DHCPNAK

### 6. 获取地址但不能上网

DHCP 成功不代表所有网络都正常，应检查：

- 子网掩码
- 默认网关
- DNS Server
- Option 121 路由
- 网关 ARP
- NAT 和防火墙
- 上游路由

### 7. 地址池耗尽

检查：

- 活跃租约是否真实存在
- 租期是否过长
- 是否有 Starvation 攻击
- 客户端是否频繁变化 Client Identifier
- 是否存在废弃设备租约
- Scope 是否需要扩容或重新划分

不要在未确认终端状态时直接删除全部租约，可能导致重复分配。

### 8. 客户端反复获得 NAK

- 客户端携带其他网段的旧地址
- Relay `giaddr` 错误
- Scope 配置错误
- 多台 Server 状态不一致
- Client Identifier 与 Reservation 不匹配

### 9. 间歇性故障

- 多台服务器中一台配置错误
- HA 同步异常
- Relay 到部分服务器路径不通
- 地址池接近耗尽
- Option 82 仅部分交换机配置
- 广播风暴或接口限速

### 10. 常见问题对照

| 现象 | 常见原因 | 排查重点 |
| ---- | -------- | -------- |
| 获得 169.254 地址 | DHCP 无响应 | DORA 抓包、Relay、Server |
| Discover 无 Offer | 池耗尽、Relay/ACL | Server Pool、giaddr |
| Offer 后失败 | 回程、Snooping、参数错误 | 双端抓包、Trusted Port |
| 一直 NAK | 旧地址、Scope 错误 | Requested IP、Server ID |
| 地址冲突 | 静态重叠、租约不同步 | ARP、Lease DB、地址规划 |
| 有 IP 无网关 | Option 3 缺失/策略错误 | ACK Options |
| 有 IP 无 DNS | Option 6 错误 | ACK、DNS 连通性 |
| 只有一个 VLAN 失败 | Relay/Scope/VLAN | SVI、helper、Trunk |
| 部分用户失败 | 地址池、Option 82、NAC | 端口位置和 Client ID |
| 续租失败 | 原 Server/HA 故障 | T1/T2、单播路径 |

---

## 二十三、DHCP 设计建议

### 1. 地址规划

- 每个 VLAN 对应清晰的 DHCP Scope
- 地址池不与静态地址重叠
- 网关、服务器和网络设备地址预留
- 记录 Scope、VLAN、Relay 和 Option 关系
- 为增长和故障预留容量

### 2. 租期选择

| 场景 | 倾向 |
| ---- | ---- |
| 稳定办公终端 | 较长租期 |
| 访客 Wi-Fi | 较短租期 |
| 地址充足、设备固定 | 较长租期 |
| 地址紧张、设备流动快 | 较短租期 |
| 大规模故障恢复 | 避免短到造成续租风暴 |

租期越短，配置变更传播越快，但 Server 和网络负载越高。

### 3. 高可用

- 部署至少两个 DHCP Server 或 HA 节点
- Relay 指向多个可用 Server
- 同步租约状态
- 监控 Partner 和数据库
- 定期验证故障切换
- 保证两条网络路径可达

### 4. 安全基线

- 接入交换机启用 DHCP Snooping
- 只把合法上联设为 Trusted
- 配合 DAI、IP Source Guard
- 控制客户端请求速率
- 使用 802.1X/NAC 做身份认证
- 监控 Rogue Server 和地址池异常

### 5. 监控指标

- 地址池使用率
- Discover/Offer/Request/ACK 比例
- NAK/Decline 数量
- 分配延迟
- 租约数据库错误
- HA 同步状态
- 每 VLAN/Relay 的失败率
- Snooping 丢弃计数

---

## 二十四、DHCPv4 与 DHCPv6 对比

| 维度 | DHCPv4 | DHCPv6 |
| ---- | ------ | ------ |
| 客户端端口 | UDP 68 | UDP 546 |
| 服务器端口 | UDP 67 | UDP 547 |
| 发现方式 | 广播 | 组播 |
| 客户端标识 | MAC / Client ID | DUID + IAID |
| 基本流程 | Discover/Offer/Request/ACK | Solicit/Advertise/Request/Reply |
| 默认网关 | Option 3 | 通过 RA，不由 DHCPv6 下发 |
| Relay 标识 | giaddr、Option 82 | Relay-Forward 层级和 Interface-ID 等 |
| 地址模式 | DHCP 分配 | 可与 SLAAC 并存 |
| 前缀委派 | 无标准等价机制 | IA_PD |
| 冲突检测 | ARP Probe | IPv6 DAD |

---

## 二十五、核心要点速记

- **DHCP = 自动分配 IP 和网络参数**
- **DHCPv4 客户端 UDP 68，服务器 UDP 67**
- **DORA = Discover → Offer → Request → ACK**
- **初始 Discover 通常从 0.0.0.0 广播到 255.255.255.255**
- **DHCPREQUEST 同时用于选择地址、续租和重绑定**
- **DHCPNAK 表示地址无效，客户端应停止使用并重新获取**
- **DHCPDECLINE 表示客户端检测到地址冲突**
- **DHCPRELEASE 主动释放租约，但异常离线时通常不会发送**
- **DHCPINFORM 表示已有 IP，只请求其他参数**
- **xid 用于匹配一次 DHCP 交互**
- **yiaddr 是服务器提供给客户端的地址**
- **giaddr 是 Relay 地址，用于选择客户端网段的 Scope**
- **Option 53 = DHCP Message Type**
- **Option 54 = Server Identifier**
- **Option 50 = Requested IP Address**
- **Option 51 = Lease Time**
- **Option 3 = Router，Option 6 = DNS**
- **Option 82 = Relay Agent Information**
- **T1 通常为租期 50%，客户端向原服务器续租**
- **T2 通常为租期 87.5%，客户端向任意服务器重绑定**
- **租约到期未续租成功，客户端必须停止使用地址**
- **广播不能跨路由器，跨网段需要 DHCP Relay**
- **Reservation 可集中固定地址，比终端手工静态配置更易管理**
- **地址池不能与静态地址范围重叠**
- **DHCP Snooping 阻止 Rogue DHCP 并建立 IP-MAC-Port 绑定**
- **只有合法 Server/Relay 上联端口应配置 Trusted**
- **DHCP Snooping Binding 可供 DAI 和 IP Source Guard 使用**
- **DHCP 不提供强身份认证，MAC/Client ID 可以伪造**
- **169.254.0.0/16 通常表示 IPv4 DHCP 获取失败后的 Link-Local 地址**
- **DHCPv6 使用 UDP 546/547 和组播，不使用广播**
- **DHCPv6 使用 DUID、IAID 和 IA_NA/IA_PD 等身份关联**
- **IPv6 默认网关通过 RA 获得，不由 DHCPv6 下发**
- **SLAAC、无状态 DHCPv6 和有状态 DHCPv6 可以按需组合**
- **DHCPv6-PD 用于向下游路由器委派 IPv6 前缀**
- **排障重点观察 DORA 在哪一步中断**
- **客户端 VLAN 有 Discover、服务器侧没有时优先检查 Relay、VLAN 和 ACL**
- **获取 IP 但不能上网时继续检查网关、DNS、路由、NAT 和防火墙**
