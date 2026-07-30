# ARP 协议 (Address Resolution Protocol)

## 一、ARP 概述

### 什么是 ARP

**ARP (Address Resolution Protocol，地址解析协议)**：在 IPv4 局域网中，根据已知的 **IP 地址**查询对应的 **MAC 地址**。

- IP 地址负责网络层寻址
- MAC 地址负责链路层帧传输
- 主机发送以太网帧前，需要知道下一跳设备的 MAC 地址
- ARP 只在当前二层广播域内工作，不能跨路由器传播
- ARP 仅用于 IPv4；IPv6 使用 **NDP (Neighbor Discovery Protocol)**

### ARP 解决的问题

```text
应用要访问 192.168.1.20
        ↓
IP 层知道目标 IP
        ↓
以太网层需要目标 MAC
        ↓
ARP 查询:192.168.1.20 的 MAC 是什么?
        ↓
得到 00:11:22:33:44:55
        ↓
封装以太网帧并发送
```

### ARP 在协议栈中的位置

| 层次 | 主要协议 | 寻址依据 |
| ---- | -------- | -------- |
| 应用层 | HTTP、DNS、SSH | 域名、应用数据 |
| 传输层 | TCP、UDP | 端口号 |
| 网络层 | IPv4 | IP 地址 |
| 链路层 | Ethernet、ARP | MAC 地址 |
| 物理层 | 双绞线、光纤、无线 | 比特流 |

ARP 为网络层和链路层提供衔接，通常被视为**链路层辅助协议**。

---

## 二、ARP 工作原理

### 1. 基本过程

假设主机 A 要向同一网段的主机 B 发送数据：

```text
主机 A
IP:  192.168.1.10
MAC: AA:AA:AA:AA:AA:AA

主机 B
IP:  192.168.1.20
MAC: BB:BB:BB:BB:BB:BB
```

处理过程：

```text
1. A 判断 192.168.1.20 与自己在同一网段
2. A 查询本机 ARP 缓存
3. 缓存未命中，A 广播 ARP Request
4. 局域网内所有设备收到请求
5. 只有 B 发现目标 IP 是自己
6. B 通常单播返回 ARP Reply
7. A 将 IP 与 MAC 的映射写入 ARP 缓存
8. A 使用 B 的 MAC 封装并发送以太网帧
```

### 2. ARP 请求

```text
以太网目的 MAC: FF:FF:FF:FF:FF:FF  # 广播
以太网源 MAC:   AA:AA:AA:AA:AA:AA

ARP 内容:
  操作类型: Request (1)
  发送方 IP:  192.168.1.10
  发送方 MAC: AA:AA:AA:AA:AA:AA
  目标 IP:    192.168.1.20
  目标 MAC:   00:00:00:00:00:00

含义:谁是 192.168.1.20? 请告诉 192.168.1.10
```

ARP 请求必须广播，因为发送方还不知道目标设备的 MAC 地址。

### 3. ARP 响应

```text
以太网目的 MAC: AA:AA:AA:AA:AA:AA  # 通常单播
以太网源 MAC:   BB:BB:BB:BB:BB:BB

ARP 内容:
  操作类型: Reply (2)
  发送方 IP:  192.168.1.20
  发送方 MAC: BB:BB:BB:BB:BB:BB
  目标 IP:    192.168.1.10
  目标 MAC:   AA:AA:AA:AA:AA:AA

含义:192.168.1.20 的 MAC 是 BB:BB:BB:BB:BB:BB
```

### 4. ARP 缓存

为了避免每次发送数据都广播查询，系统会缓存 IP 与 MAC 的映射。

```bash
# Linux 查看邻居表
ip neigh

# 常见输出
192.168.1.1 dev eth0 lladdr 00:11:22:33:44:55 REACHABLE
192.168.1.20 dev eth0 lladdr BB:BB:BB:BB:BB:BB STALE
```

| 状态 | 含义 |
| ---- | ---- |
| **INCOMPLETE** | 正在解析，尚未得到 MAC |
| **REACHABLE** | 最近确认邻居可达 |
| **STALE** | 映射存在，但需要重新确认 |
| **DELAY** | 暂缓探测，等待上层确认 |
| **PROBE** | 正在单播探测邻居 |
| **FAILED** | 地址解析失败 |
| **PERMANENT** | 静态条目，不自动过期 |

动态 ARP 条目会老化，具体时间由操作系统和网络设备决定。

---

## 三、同网段与跨网段通信

### 1. 同网段通信

```text
A: 192.168.1.10/24
B: 192.168.1.20/24

A 计算:
  自己网络号 = 192.168.1.0
  目标网络号 = 192.168.1.0

结论:同网段
ARP 查询对象:192.168.1.20
以太网目的 MAC:B 的 MAC
IP 目的地址:192.168.1.20
```

### 2. 跨网段通信

```text
A:      192.168.1.10/24
网关:   192.168.1.1/24
目标 B: 10.0.0.20/24
```

A 判断目标不在本地网段，因此把数据交给默认网关：

```text
ARP 查询对象:192.168.1.1           # 网关，不是远端主机 B
以太网目的 MAC:网关接口的 MAC
IP 目的地址:10.0.0.20              # 始终是最终目标 B
```

路由器收到数据包后，在下一个直连网络中再次通过 ARP 查询下一跳 MAC。

### 3. 地址在转发过程中的变化

```text
A ───── 路由器 R ───── B

A 发给 R:
  源 MAC = A
  目的 MAC = R 左接口
  源 IP = A
  目的 IP = B

R 发给 B:
  源 MAC = R 右接口
  目的 MAC = B
  源 IP = A
  目的 IP = B
```

- 每经过一个路由器，链路层的源、目的 MAC 都会重写
- 未发生 NAT 时，源、目的 IP 保持不变
- ARP 解析的是**本链路下一跳 IP**，不是所有情况下的最终目标 IP

---

## 四、ARP 报文格式

### 1. ARP 报文结构

```text
0                   15                  31
+-------------------+-------------------+
| Hardware Type     | Protocol Type     |
+---------+---------+-------------------+
| HLEN    | PLEN    | Operation         |
+---------+---------+-------------------+
| Sender Hardware Address (SHA)         |
+---------------------------------------+
| Sender Protocol Address (SPA)         |
+---------------------------------------+
| Target Hardware Address (THA)         |
+---------------------------------------+
| Target Protocol Address (TPA)         |
+---------------------------------------+
```

### 2. 字段说明

| 字段 | 长度 | 常见值 | 含义 |
| ---- | ---- | ------ | ---- |
| **Hardware Type** | 16 bit | 1 | 以太网 |
| **Protocol Type** | 16 bit | 0x0800 | IPv4 |
| **HLEN** | 8 bit | 6 | MAC 地址长度 |
| **PLEN** | 8 bit | 4 | IPv4 地址长度 |
| **Operation** | 16 bit | 1 / 2 | Request / Reply |
| **SHA** | 可变 | 6 字节 | 发送方 MAC |
| **SPA** | 可变 | 4 字节 | 发送方 IP |
| **THA** | 可变 | 6 字节 | 目标 MAC |
| **TPA** | 可变 | 4 字节 | 目标 IP |

以太网帧中的 ARP **EtherType 为 0x0806**。

### 3. 报文大小

在以太网和 IPv4 环境中：

```text
ARP 报文:       28 字节
以太网头:      14 字节
以太网最小载荷:46 字节
```

ARP 报文不足以太网最小载荷时，会填充到 46 字节。

---

## 五、ARP 类型

### 1. 普通 ARP

- 已知目标 IPv4 地址，查询目标 MAC 地址
- Request 通常广播
- Reply 通常单播
- 是局域网 IPv4 通信的基础

### 2. Gratuitous ARP (免费 ARP)

设备主动发送关于**自己 IP 地址**的 ARP 请求或响应，并非为了查询其他设备。

常见用途：

- 检测 IP 地址冲突
- 更新其他设备的 ARP 缓存
- 主备切换后通告新的 MAC 地址
- VRRP、HA、集群漂移 IP
- 网卡绑定或虚拟机迁移

```text
发送方 IP = 192.168.1.10
目标 IP   = 192.168.1.10
```

免费 ARP 没有独立的新报文类型，仍使用标准 ARP Request 或 Reply。

### 3. Proxy ARP (代理 ARP)

路由器代替另一台设备响应 ARP 请求：

```text
主机 A 询问:谁是 10.0.0.20?
路由器回答:使用我的 MAC
主机 A 将帧发送给路由器
路由器再转发到 10.0.0.20
```

适用场景：

- 旧网络兼容
- 部分 VPN 或特殊路由场景
- 无法正确配置网关的主机

限制：

- 增加广播和 ARP 表规模
- 隐藏真实拓扑，排障困难
- 容易扩大二层故障影响
- 现代网络通常优先使用正确的子网和路由配置

### 4. Reverse ARP (RARP)

**RARP**：已知 MAC 地址，请求分配 IP 地址。

- 早期无盘工作站使用
- 功能单一，需要同一广播域的 RARP 服务器
- 已被 BOOTP 和 DHCP 取代

### 5. Inverse ARP (InARP)

**InARP**：在 Frame Relay、ATM 等网络中，根据已知的数据链路标识查询网络层地址。

- 与普通 ARP 的使用场景不同
- 主要用于传统广域网技术
- 现代以太网环境很少使用

### 6. ARP Probe 与 ARP Announcement

IPv4 地址冲突检测常使用 RFC 5227 定义的机制：

| 类型 | Sender IP | Target IP | 用途 |
| ---- | --------- | --------- | ---- |
| **ARP Probe** | 0.0.0.0 | 待使用地址 | 使用前检测冲突 |
| **ARP Announcement** | 自己的 IP | 自己的 IP | 声明已经使用该地址 |

---

## 六、ARP 缓存管理

### 1. 动态条目

- 通过 ARP 报文自动学习
- 有老化时间
- 网络变化后可自动更新
- 最常见

### 2. 静态条目

```bash
# Linux 添加静态邻居条目
sudo ip neigh replace 192.168.1.20 lladdr BB:BB:BB:BB:BB:BB nud permanent dev eth0

# 删除条目
sudo ip neigh del 192.168.1.20 dev eth0
```

特点：

- 不自动过期
- 可防止关键地址被动态篡改
- 维护成本高
- 设备更换 MAC 后必须手动更新

### 3. 清理 ARP 缓存

```bash
# 清理指定接口的动态邻居条目
sudo ip neigh flush dev eth0

# 清理指定 IP
sudo ip neigh flush to 192.168.1.20
```

清理后，下一次通信会重新发起 ARP 查询，短时间内出现一次延迟属于正常现象。

### 4. 各系统查看命令

```text
# Linux
ip neigh
arp -n

# Windows
arp -a
Get-NetNeighbor -AddressFamily IPv4

# macOS
arp -a

# Cisco
show ip arp

# 华为
display arp
```

---

## 七、ARP 安全

### 1. ARP 的安全缺陷

ARP 设计时默认局域网内设备可信：

- 没有身份认证
- 没有报文加密
- 主机通常会接受收到的 ARP 更新
- 请求与响应不一定严格配对

因此，攻击者可以发送伪造 ARP 报文污染缓存。

### 2. ARP 欺骗与 ARP 投毒

```text
正常:
主机 A → 网关 MAC = RR:RR:RR:RR:RR:RR

投毒后:
主机 A → 网关 MAC = XX:XX:XX:XX:XX:XX  # 攻击者
```

可能造成：

- 中间人攻击
- 流量监听或篡改
- 会话劫持
- 断网和流量黑洞
- 网关冒充

### 3. 防护措施

| 措施 | 说明 |
| ---- | ---- |
| **DAI** | Dynamic ARP Inspection，交换机检查 ARP 合法性 |
| **DHCP Snooping** | 建立可信的 IP-MAC-端口绑定表 |
| **IP Source Guard** | 限制端口可使用的源 IP |
| **Port Security** | 限制交换机端口允许的 MAC |
| **静态 ARP** | 保护少量关键设备，维护成本高 |
| **网络隔离** | VLAN、访客网络、零信任接入 |
| **加密协议** | HTTPS、SSH、VPN 降低被监听后的危害 |
| **监控告警** | 检测同一 IP 对应多个 MAC 等异常 |

### 4. DAI 工作过程

```text
1. DHCP Snooping 记录合法绑定:
   IP + MAC + VLAN + 交换机端口
2. ARP 报文进入不可信端口
3. 交换机与绑定表比较
4. 合法则转发，伪造则丢弃并告警
```

DAI 依赖正确的信任端口和绑定信息，静态地址设备通常需要额外配置 ARP ACL。

### 5. 不能只依赖 ARP 防护

ARP 防护只能保护本地二层网络。端到端安全仍应使用：

- TLS / HTTPS
- SSH
- IPsec / WireGuard
- 强身份认证
- 证书校验

---

## 八、ARP 与交换机、路由器

### 1. ARP 表与 MAC 地址表

| 表 | 所属设备 | 映射关系 | 用途 |
| -- | -------- | -------- | ---- |
| **ARP 表** | 主机、路由器、三层交换机 | IP → MAC | 找下一跳 MAC |
| **MAC 地址表** | 二层交换机 | MAC → 端口 | 转发以太网帧 |
| **路由表** | 主机、路由器、三层交换机 | 网络前缀 → 下一跳/接口 | 选择转发路径 |

三张表相互配合，但作用完全不同。

### 2. 完整转发示例

```text
主机 A 要访问 192.168.1.20

1. 查路由表:
   192.168.1.0/24 dev eth0
2. 判断目标为直连地址
3. 查 ARP 表:
   192.168.1.20 → BB:BB:BB:BB:BB:BB
4. 封装帧，目的 MAC 为 BB:BB:BB:BB:BB:BB
5. 交换机查 MAC 地址表:
   BB:BB:BB:BB:BB:BB → 端口 5
6. 从端口 5 转发
```

### 3. VLAN 对 ARP 的影响

- ARP 广播只在所属 VLAN 内传播
- 不同 VLAN 属于不同二层广播域
- 跨 VLAN 通信需要路由器或三层交换机
- 每个三层 VLAN 接口通常拥有自己的 IP 和 MAC

### 4. 大二层网络的问题

- ARP 广播数量增加
- 终端 ARP 表变大
- 故障影响范围扩大
- ARP 欺骗风险增加

常见优化方式：

- 合理划分 VLAN 和子网
- 使用三层边界缩小广播域
- 启用 ARP 抑制或代理功能
- 在 VXLAN EVPN 中通过控制平面分发邻居信息

---

## 九、ARP 抓包分析

### 1. tcpdump 抓取 ARP

```bash
# 抓取指定接口的 ARP 报文
sudo tcpdump -i eth0 -n -e arp

# 常见输出
ARP, Request who-has 192.168.1.20 tell 192.168.1.10, length 28
ARP, Reply 192.168.1.20 is-at bb:bb:bb:bb:bb:bb, length 28
```

参数含义：

- `-i eth0`：指定接口
- `-n`：不解析名称
- `-e`：显示以太网头
- `arp`：仅匹配 ARP 报文

### 2. Wireshark 过滤器

```text
arp
arp.opcode == 1
arp.opcode == 2
arp.src.proto_ipv4 == 192.168.1.20
arp.duplicate-address-detected
```

### 3. 正常抓包特征

```text
Request:广播，询问目标 IP
Reply:通常单播，返回目标 MAC
随后出现发往该 MAC 的 IPv4 数据帧
```

### 4. 异常抓包特征

- 同一个 IP 短时间内被多个 MAC 声明
- 大量无业务关联的免费 ARP
- ARP 请求持续重传但没有响应
- 网关 MAC 频繁变化
- 单台设备发送大量 ARP 扫描请求

---

## 十、ARP 配置与实验

### 1. 查看当前网络信息

```bash
ip addr show
ip route show
ip neigh show
```

### 2. 触发一次 ARP 解析

```bash
# 清理目标条目
sudo ip neigh flush to 192.168.1.20

# 访问目标
ping -c 1 192.168.1.20

# 查看新条目
ip neigh show 192.168.1.20
```

### 3. 使用 arping

```bash
# 在指定接口查询目标
sudo arping -I eth0 192.168.1.20

# 重复地址检测，不使用源 IP
sudo arping -D -I eth0 192.168.1.20

# 发送免费 ARP 通告
sudo arping -A -I eth0 192.168.1.10
```

### 4. 一个最小观察实验

终端 1：

```bash
sudo tcpdump -i eth0 -n -e arp
```

终端 2：

```bash
sudo ip neigh flush to 192.168.1.20
ping -c 1 192.168.1.20
```

预期顺序：

```text
ARP Request
ARP Reply
ICMP Echo Request
ICMP Echo Reply
```

如果目标 ARP 条目已经存在，ping 前可能看不到新的 ARP 报文。

---

## 十一、ARP 常见问题

### 1. ARP 请求无响应

可能原因：

- 目标主机离线
- IP 地址配置错误
- 子网掩码错误
- 目标不在当前 VLAN
- 交换机端口或链路故障
- 无线客户端隔离
- 安全策略丢弃 ARP
- IP 地址并不存在

### 2. ARP 条目为 INCOMPLETE 或 FAILED

```text
192.168.1.20 dev eth0 INCOMPLETE
```

表示系统已发送请求但未获得有效响应，应检查：

```text
本机接口 → VLAN → 二层链路 → 目标是否在线 → 地址配置
```

### 3. 可以 ping 网关，但不能访问外网

ARP 能解析网关只说明本机到网关的二层通信正常，还需要检查：

- 默认路由
- 网关转发
- NAT
- 防火墙
- 上游路由
- DNS

### 4. 修改 IP 或迁移虚拟机后通信异常

常见原因是其他设备仍缓存旧的 MAC 地址：

- 等待 ARP 条目老化
- 清理邻居缓存
- 发送免费 ARP
- 检查交换机 MAC 地址表是否同步更新

### 5. IP 地址冲突

常见现象：

- 网络时通时断
- 系统提示地址冲突
- 同一 IP 对应的 MAC 不断变化
- 抓包出现多个设备响应同一 ARP 请求

处理方式：

```text
1. 记录冲突 MAC
2. 通过交换机 MAC 表定位端口
3. 检查 DHCP 租约和静态地址
4. 修正重复配置
5. 清理相关 ARP 缓存
```

---

## 十二、ARP 故障排查

### 1. 排查流程

```text
1. 检查接口是否 UP
2. 检查本机 IP 和子网掩码
3. 检查路由表，确认下一跳是谁
4. 查看目标 ARP 条目状态
5. 抓取 ARP Request / Reply
6. 检查 VLAN、交换机端口和 MAC 表
7. 检查 DAI、端口安全等策略
8. 排查重复 IP 或错误静态 ARP
```

### 2. 常用命令

```bash
# Linux
ip link
ip addr
ip route get 192.168.1.20
ip neigh
ping 192.168.1.20
arping -I eth0 192.168.1.20
tcpdump -i eth0 -n -e arp
```

```text
# Cisco
show ip arp
show mac address-table
show interfaces status
show vlan brief
show ip route
show ip dhcp snooping binding
show ip arp inspection

# 华为
 display arp
 display mac-address
 display vlan
 display ip routing-table
```

### 3. 常见故障对照

| 现象 | 可能原因 | 排查重点 |
| ---- | -------- | -------- |
| ARP 一直 INCOMPLETE | 目标不可达、VLAN 错误 | 抓包、接口、VLAN |
| 网关 MAC 频繁变化 | IP 冲突、ARP 欺骗、主备切换 | 抓包、设备日志 |
| 只有部分主机不通 | 静态 ARP、端口安全、掩码错误 | 邻居表、端口策略 |
| 迁移后暂时不通 | 旧 ARP/MAC 缓存 | 免费 ARP、清缓存 |
| 广播很多 | 网段过大、扫描、环路 | VLAN 规划、STP、流量分析 |
| DAI 开启后断网 | 绑定表缺失、信任口错误 | DHCP Snooping、ARP ACL |

---

## 十三、ARP 与 IPv6 NDP 对比

| 维度 | ARP | NDP |
| ---- | --- | --- |
| 适用协议 | IPv4 | IPv6 |
| 基础协议 | 独立 ARP 报文 | ICMPv6 |
| 地址解析 | IP → MAC | IPv6 → 链路层地址 |
| 查询方式 | 广播 | 多播 |
| 路由器发现 | 不负责 | Router Solicitation / Advertisement |
| 邻居可达性检测 | 有限 | 内置 NUD |
| 重复地址检测 | ARP Probe | DAD |
| 安全扩展 | DAI 等设备能力 | SEND 等 |

IPv6 不使用 ARP，而是通过 NDP 的 **Neighbor Solicitation** 和 **Neighbor Advertisement** 完成邻居解析。

---

## 十四、核心要点速记

- **ARP = IPv4 地址解析协议，IP → MAC**
- **ARP 只在本地二层广播域内工作**
- **ARP Request 通常广播，ARP Reply 通常单播**
- **同网段查询目标主机 MAC**
- **跨网段查询默认网关 MAC**
- **IP 指向最终目标，MAC 指向本链路下一跳**
- **ARP EtherType = 0x0806**
- **Request 操作码 = 1，Reply 操作码 = 2**
- **ARP 缓存减少广播，动态条目会老化**
- **ARP 表是 IP → MAC**
- **交换机 MAC 表是 MAC → 端口**
- **路由表是网络前缀 → 下一跳/接口**
- **免费 ARP 用于冲突检测、缓存更新和主备切换**
- **代理 ARP由路由器代替其他设备响应**
- **RARP 已被 BOOTP / DHCP 取代**
- **ARP 无认证，容易遭受欺骗和投毒**
- **DAI 通常结合 DHCP Snooping 防护 ARP 欺骗**
- **静态 ARP 适合少量关键设备，不适合大规模维护**
- **INCOMPLETE 表示请求已发出但没有得到响应**
- **抓包过滤器：`arp`**
- **Linux 查看命令：`ip neigh`**
- **IPv6 使用 NDP，不使用 ARP**
