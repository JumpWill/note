# TCP 协议 (Transmission Control Protocol)

## 一、TCP 概述

### 什么是 TCP

**TCP (Transmission Control Protocol，传输控制协议)**：一种**面向连接、可靠、基于字节流**的传输层协议。

TCP 位于应用层和 IP 层之间：

```text
应用层: HTTP、HTTPS、SSH、SMTP、MySQL
                ↓
传输层: TCP —— 可靠传输、端口复用、流量控制、拥塞控制
                ↓
网络层: IP —— 寻址和路由
                ↓
链路层: Ethernet / Wi-Fi
```

### TCP 的核心特点

- **面向连接**：通信前需要建立连接
- **可靠传输**：确认、重传、校验、去重、排序
- **全双工**：双方可以同时发送和接收
- **字节流**：没有消息边界
- **有序交付**：应用按发送顺序读取数据
- **流量控制**：避免发送方压垮接收方
- **拥塞控制**：避免过多流量压垮网络
- **一对一通信**：一个 TCP 连接只连接两个端点

### TCP 连接的标识

一个 TCP 连接通常由四元组唯一标识：

```text
源 IP + 源端口 + 目的 IP + 目的端口
```

示例：

```text
192.168.1.10:53000 → 203.0.113.20:443
```

同一服务器端口可以同时服务大量客户端，因为每个客户端的源 IP 或源端口不同。

### 常见 TCP 应用

| 协议/应用 | 默认端口 | 说明 |
| --------- | -------- | ---- |
| HTTP | 80 | Web 明文传输 |
| HTTPS | 443 | HTTP over TLS |
| SSH | 22 | 安全远程登录 |
| FTP | 20/21 | 文件传输 |
| SMTP | 25/465/587 | 邮件发送 |
| IMAP | 143/993 | 邮件读取 |
| MySQL | 3306 | 数据库 |
| Redis | 6379 | 缓存数据库 |

---

## 二、TCP 报文格式

### 1. TCP 首部结构

```text
0                   15                  31
+-------------------+-------------------+
| Source Port       | Destination Port  |
+---------------------------------------+
| Sequence Number                       |
+---------------------------------------+
| Acknowledgment Number                 |
+----+---+----------------+--------------+
|DOFF|Res| Flags          | Window Size  |
+-------------------------+--------------+
| Checksum          | Urgent Pointer    |
+---------------------------------------+
| Options (可选，0~40 字节)              |
+---------------------------------------+
| Application Data                      |
+---------------------------------------+
```

TCP 固定首部为 **20 字节**，包含选项时最长为 **60 字节**。

### 2. 字段说明

| 字段 | 长度 | 作用 |
| ---- | ---- | ---- |
| **Source Port** | 16 bit | 源端口 |
| **Destination Port** | 16 bit | 目的端口 |
| **Sequence Number** | 32 bit | 本报文段第一个数据字节的序号 |
| **Acknowledgment Number** | 32 bit | 期望收到的下一个字节序号 |
| **Data Offset** | 4 bit | TCP 首部长度，单位为 4 字节 |
| **Flags** | 多个标志位 | 控制连接和数据传输 |
| **Window Size** | 16 bit | 接收窗口大小 |
| **Checksum** | 16 bit | 检查首部和数据是否损坏 |
| **Urgent Pointer** | 16 bit | 紧急数据位置，较少使用 |
| **Options** | 可变 | MSS、窗口缩放、SACK、时间戳等 |

### 3. TCP 标志位

| 标志 | 名称 | 作用 |
| ---- | ---- | ---- |
| **SYN** | Synchronize | 建立连接、同步初始序列号 |
| **ACK** | Acknowledgment | 确认号有效 |
| **FIN** | Finish | 发送方没有更多数据 |
| **RST** | Reset | 立即复位连接 |
| **PSH** | Push | 提示尽快把数据交给应用 |
| **URG** | Urgent | 紧急指针有效 |
| **ECE** | ECN Echo | 显式拥塞通知 |
| **CWR** | Congestion Window Reduced | 已降低拥塞窗口 |
| **NS** | Nonce Sum | 历史 ECN 扩展，较少使用 |

### 4. TCP 校验和

TCP 校验和覆盖：

```text
IP 伪首部 + TCP 首部 + TCP 数据
```

伪首部包含源 IP、目的 IP、协议号和 TCP 长度，可以发现部分错误投递。TCP 校验和在 IPv4 和 IPv6 中都必须使用。

抓包时看到本机发出的 TCP 校验和错误，不一定真的有问题，可能是网卡 **Checksum Offload** 在抓包点之后才计算校验和。

---

## 三、TCP 序列号与确认号

### 1. 字节序号

TCP 对传输的**每个字节**编号，而不是对报文段编号。

```text
发送 1000 字节:
第一个报文段: Seq=1000, Len=600
第二个报文段: Seq=1600, Len=400
```

### 2. 累积确认

```text
ACK=1600
```

表示：

```text
序号 1599 及以前的字节已经连续收到
下一步期望收到序号 1600
```

TCP 默认使用累积确认，一个 ACK 可以确认此前连续收到的全部数据。

### 3. SYN 与 FIN 占用序列号

- SYN 消耗一个序列号
- FIN 消耗一个序列号
- 纯 ACK 不消耗序列号
- 数据长度按实际字节数推进序列号

### 4. 初始序列号

连接双方分别选择自己的 **ISN (Initial Sequence Number)**：

```text
客户端 ISN = x
服务器 ISN = y
```

ISN 应难以预测，以降低旧报文干扰和序列号猜测攻击风险。

### 5. 序列号回绕

序列号为 32 bit，达到 `2^32 - 1` 后会回绕。TCP 通过窗口范围、时间戳等机制区分当前数据和旧报文。

---

## 四、TCP 三次握手

### 1. 建立连接过程

```text
客户端                                      服务器
  │                                            │
  │ SYN, Seq=x                                 │
  ├───────────────────────────────────────────→│
  │                                            │
  │ SYN+ACK, Seq=y, Ack=x+1                    │
  │←───────────────────────────────────────────┤
  │                                            │
  │ ACK, Seq=x+1, Ack=y+1                      │
  ├───────────────────────────────────────────→│
  │                                            │
  │              连接建立                      │
```

### 2. 每次握手的作用

| 步骤 | 报文 | 作用 |
| ---- | ---- | ---- |
| 第一次 | SYN | 客户端请求连接并发送自己的 ISN |
| 第二次 | SYN+ACK | 服务器确认客户端 ISN，并发送自己的 ISN |
| 第三次 | ACK | 客户端确认服务器 ISN |

### 3. 为什么是三次握手

三次握手至少要确认：

- 客户端能发送，服务器能接收
- 服务器能发送，客户端能接收
- 双方都知道对方已经收到自己的初始序列号
- 本次连接不是网络中滞留的旧 SYN 报文

两次握手无法让服务器确认客户端已经收到服务器的 SYN 和初始序列号。

### 4. 握手可以携带数据吗

- 普通 TCP 中，第三次握手 ACK 可以同时携带应用数据
- SYN 中携带数据需要 **TCP Fast Open (TFO)** 等扩展
- 是否启用和接受 TFO 取决于客户端、服务器和中间网络

### 5. 连接失败重传

SYN 没有得到响应时，客户端通常按递增间隔重传，达到系统重试次数后返回连接超时。

```text
SYN → 等待 → 重传 SYN → 等待更久 → ... → 超时
```

具体次数和超时时间由操作系统配置决定。

---

## 五、TCP 四次挥手

### 1. 正常关闭过程

假设客户端主动关闭：

```text
客户端                                      服务器
  │                                            │
  │ FIN, Seq=u                                 │
  ├───────────────────────────────────────────→│
  │                                            │
  │ ACK, Ack=u+1                               │
  │←───────────────────────────────────────────┤
  │                                            │
  │              服务器继续处理剩余数据        │
  │                                            │
  │ FIN, Seq=v                                 │
  │←───────────────────────────────────────────┤
  │                                            │
  │ ACK, Ack=v+1                               │
  ├───────────────────────────────────────────→│
  │                                            │
```

### 2. 为什么通常是四次

TCP 是全双工协议：

- 收到对方 FIN，只表示对方不再发送数据
- 本端仍可继续发送剩余数据
- 两个方向需要分别关闭

如果接收方没有剩余数据，ACK 和 FIN 可以合并，因此抓包中也可能只看到三个关闭报文。

### 3. 半关闭

一方调用 `shutdown(SHUT_WR)` 后：

```text
本端不再发送数据
但仍可以继续接收对方数据
```

这称为 **TCP Half-Close**，适合“请求发送完毕，但仍要读取完整响应”的场景。

### 4. RST 关闭

RST 表示异常或立即终止：

- 访问没有监听的端口
- 应用异常退出
- 对不存在的连接收到报文
- 使用 `SO_LINGER` 配置为立即复位
- 中间防火墙主动拒绝连接

RST 不执行正常的双向关闭流程，未读取的数据可能丢失。

---

## 六、TCP 状态机

### 1. 常见状态

| 状态 | 含义 |
| ---- | ---- |
| **CLOSED** | 没有连接 |
| **LISTEN** | 服务器等待连接 |
| **SYN_SENT** | 已发送 SYN，等待 SYN+ACK |
| **SYN_RECV** | 已收到 SYN 并回复 SYN+ACK |
| **ESTABLISHED** | 连接已建立 |
| **FIN_WAIT_1** | 主动关闭方已发送 FIN |
| **FIN_WAIT_2** | 已收到 FIN 的 ACK，等待对方 FIN |
| **CLOSE_WAIT** | 被动关闭方收到 FIN，等待应用关闭 |
| **LAST_ACK** | 被动关闭方已发送 FIN，等待最终 ACK |
| **CLOSING** | 双方几乎同时关闭 |
| **TIME_WAIT** | 主动关闭方等待旧报文过期 |

### 2. 客户端典型状态变化

```text
CLOSED
  ↓ connect()
SYN_SENT
  ↓ 收到 SYN+ACK，发送 ACK
ESTABLISHED
  ↓ 主动 close()，发送 FIN
FIN_WAIT_1
  ↓ 收到 ACK
FIN_WAIT_2
  ↓ 收到 FIN，发送 ACK
TIME_WAIT
  ↓ 等待 2MSL
CLOSED
```

### 3. 服务器典型状态变化

```text
CLOSED
  ↓ bind() + listen()
LISTEN
  ↓ 收到 SYN，发送 SYN+ACK
SYN_RECV
  ↓ 收到 ACK
ESTABLISHED
  ↓ 收到 FIN，发送 ACK
CLOSE_WAIT
  ↓ 应用 close()，发送 FIN
LAST_ACK
  ↓ 收到 ACK
CLOSED
```

### 4. TIME_WAIT

**TIME_WAIT** 通常由主动关闭连接的一方进入，持续约 `2MSL`。

作用：

- 确保最后一个 ACK 丢失时还能重发
- 让旧连接中的延迟报文在网络中消失
- 避免相同四元组的新连接误收旧报文

大量短连接可能产生许多 TIME_WAIT。优先使用连接复用和连接池，而不是盲目缩短 TIME_WAIT。

### 5. CLOSE_WAIT

CLOSE_WAIT 表示：

```text
对方已经关闭发送方向
本地应用尚未关闭 socket
```

大量长期存在的 CLOSE_WAIT 通常是应用没有正确执行 `close()`，应修复应用资源释放逻辑。

---

## 七、TCP 可靠传输

### 1. 可靠性的组成

TCP 通过以下机制实现可靠传输：

- 序列号
- 确认应答
- 超时重传
- 快速重传
- 校验和
- 接收端去重
- 乱序重组
- 滑动窗口

### 2. 超时重传

```text
发送 Seq=1000, Len=500
        ↓
等待 ACK=1500
        ↓ 超过 RTO 仍未收到
重传 Seq=1000, Len=500
```

**RTO (Retransmission Timeout)** 根据测量到的 RTT 和波动动态计算，不应简单设置为固定 RTT。

### 3. RTT 测量

- **RTT**：报文从发送到收到确认的往返时间
- **SRTT**：平滑后的 RTT
- **RTTVAR**：RTT 波动估计
- **RTO**：依据 SRTT 和 RTTVAR 计算的重传超时

发生超时后，RTO 通常指数退避，防止持续重传加重拥塞。

### 4. 快速重传

当接收方发现一个缺口，但继续收到后续数据时，会重复确认当前期望序号：

```text
收到:1000-1499
丢失:1500-1999
收到:2000-2499 → ACK=1500
收到:2500-2999 → ACK=1500
收到:3000-3499 → ACK=1500
```

经典 TCP 在收到多个重复 ACK 后，不等待 RTO 就重传疑似丢失的数据。

### 5. SACK

**SACK (Selective Acknowledgment)** 允许接收方告诉发送方哪些非连续区间已经收到：

```text
ACK=1500
SACK:2000-3500 已收到
```

发送方只需补发缺失的 `1500-1999`，而不是重复发送后续全部数据。

### 6. 乱序与重复

- 乱序数据可暂存在接收缓冲区
- 缺失数据到达后按顺序交给应用
- 重复报文根据序列号识别并丢弃
- TCP 不会把同一个字节重复交给应用

### 7. TCP 不能保证什么

TCP 保证连接内字节流的可靠、有序交付，但不保证：

- 对端应用已经处理数据
- 数据已经写入磁盘
- 一次 `write()` 对应一次 `read()`
- 连接永远不会中断
- 业务操作不会重复执行

需要应用层协议定义消息边界、业务确认、幂等和故障恢复。

---

## 八、滑动窗口与流量控制

### 1. 为什么需要窗口

如果每发送一个报文段都等待确认，链路利用率很低：

```text
发送 1 段 → 等 ACK → 发送 1 段 → 等 ACK
```

滑动窗口允许发送方在未收到确认前连续发送多个报文段：

```text
发送 1、2、3、4 → 接收累计 ACK → 窗口向前滑动
```

### 2. 接收窗口 rwnd

接收方通过 TCP Header 的 Window 字段通告可用缓冲空间：

```text
rwnd = 接收缓冲区剩余空间
```

发送方未确认的数据量不能超过接收窗口，从而避免接收方缓冲区溢出。

### 3. 窗口缩放

TCP 原始窗口字段只有 16 bit，最大 65535 字节。握手时协商 **Window Scale** 后，可把窗口左移最多 14 位，支持高带宽、高延迟链路。

```text
实际窗口 = Header Window × 2^scale
```

窗口缩放只能在 SYN 阶段协商。

### 4. 零窗口

接收缓冲区满时，接收方通告：

```text
Window = 0
```

发送方暂停普通数据，并周期性发送 **Zero Window Probe**，确认窗口是否重新打开，避免窗口更新报文丢失后双方永久等待。

### 5. 糊涂窗口综合征

如果接收方频繁开放很小的窗口，会产生大量小报文。常见缓解机制：

- 接收端 Clark 方案
- 发送端 Nagle 算法
- 合理设置缓冲区
- 应用批量读写

---

## 九、TCP 拥塞控制

### 1. 流量控制与拥塞控制

| 机制 | 保护对象 | 核心变量 |
| ---- | -------- | -------- |
| **流量控制** | 接收主机 | rwnd |
| **拥塞控制** | 网络链路和中间设备 | cwnd |

发送方实际可发送窗口近似为：

```text
send_window = min(rwnd, cwnd)
```

### 2. 拥塞窗口 cwnd

**cwnd (Congestion Window)** 是发送方根据网络状况维护的窗口。丢包、ECN 和延迟变化可作为拥塞信号。

### 3. 经典 Reno 阶段

| 阶段 | 行为 |
| ---- | ---- |
| **慢启动** | cwnd 每个 RTT 近似翻倍 |
| **拥塞避免** | cwnd 每个 RTT 近似线性增长 |
| **快速重传** | 重复 ACK 达到阈值后立即重传 |
| **快速恢复** | 降低 cwnd，但不完全回到初始状态 |

### 4. 慢启动

“慢”指从较小窗口开始，不代表线性增长：

```text
cwnd: 1 → 2 → 4 → 8 → 16 ...
```

达到慢启动阈值 `ssthresh` 或检测到拥塞后，进入拥塞避免。

现代 TCP 的初始窗口通常大于 1 MSS，具体由实现和标准决定。

### 5. 丢包后的处理

经典行为：

- **RTO 超时**：认为拥塞严重，大幅减小 cwnd
- **重复 ACK / SACK**：认为部分丢包，快速重传并适度减小 cwnd
- **ECN**：无需等待丢包即可通知拥塞

具体增长和退让方式取决于拥塞控制算法。

### 6. 常见拥塞控制算法

| 算法 | 特点 |
| ---- | ---- |
| **Reno/NewReno** | 经典基于丢包的算法 |
| **CUBIC** | Linux 常用，适合高速长距离网络 |
| **BBR** | 基于带宽和 RTT 模型，不只依赖丢包 |
| **DCTCP** | 利用 ECN，常用于数据中心 |

```bash
# Linux 查看可用算法
sysctl net.ipv4.tcp_available_congestion_control

# 查看当前算法
sysctl net.ipv4.tcp_congestion_control
```

---

## 十、MSS、MTU 与分段

### 1. MTU

**MTU (Maximum Transmission Unit)**：链路层一次可承载的最大网络层报文大小。普通以太网 MTU 常为 1500 字节。

### 2. MSS

**MSS (Maximum Segment Size)**：TCP 报文段中最大数据部分，不包含 IP 和 TCP 首部。

典型 IPv4：

```text
MTU 1500
- IPv4 首部 20
- TCP 首部 20
= MSS 1460
```

典型 IPv6：

```text
MTU 1500
- IPv6 首部 40
- TCP 首部 20
= MSS 1440
```

存在 TCP/IP 选项、隧道或额外封装时，可用 MSS 可能更小。

### 3. MSS 协商

双方在 SYN 报文中通告自己愿意接收的 MSS：

```text
客户端 SYN: MSS=1460
服务器 SYN+ACK: MSS=1440
```

MSS 是单方向的接收能力声明，双方值可以不同。

### 4. PMTUD

**Path MTU Discovery** 用于发现完整路径允许的最大 IP 包：

- IPv4 依赖 DF 标志和 ICMP Fragmentation Needed
- IPv6 路由器不分片，依赖 ICMPv6 Packet Too Big

如果网络错误丢弃这些 ICMP 报文，可能出现 **PMTUD Black Hole**：握手成功，但大数据传输卡住。

### 5. TSO/GSO/GRO

现代操作系统和网卡会使用卸载与聚合：

- **TSO/GSO**：发送端把大块数据交给内核或网卡再分段
- **GRO/LRO**：接收端把多个报文段聚合后交给协议栈

因此，在不同抓包位置看到的报文大小可能不同。

---

## 十一、TCP 选项

### 1. 常见选项

| 选项 | 作用 | 协商阶段 |
| ---- | ---- | -------- |
| **MSS** | 最大 TCP 数据段大小 | SYN |
| **Window Scale** | 扩大接收窗口 | SYN |
| **SACK Permitted** | 声明支持选择确认 | SYN |
| **SACK** | 报告已收到的数据区间 | 连接期间 |
| **Timestamps** | RTT 测量、旧报文保护 | SYN 协商后使用 |
| **TCP Fast Open** | 减少重复连接的握手延迟 | SYN/Cookie |

### 2. 时间戳

TCP Timestamp 包含：

- `TSval`：发送方时间戳值
- `TSecr`：回显对方时间戳

用途：

- 更精确地测量 RTT
- PAWS 防止高速连接中的旧序列号报文被接受

### 3. TCP Fast Open

TFO 允许已获得 Cookie 的客户端在 SYN 中携带数据，减少一次往返延迟。

限制：

- 首次连接仍需获取 Cookie
- 中间设备兼容性可能影响使用
- 应用必须考虑早期数据被重放的风险
- 只适合幂等或可安全重试的请求

---

## 十二、TCP 字节流与粘包

### 1. TCP 没有消息边界

发送方：

```text
write("hello")
write("world")
```

接收方可能读到：

```text
"helloworld"
```

也可能分成：

```text
"hel"
"lowor"
"ld"
```

这不是 TCP 错误，而是字节流协议的正常行为。

### 2. 应用层划分消息的方法

| 方法 | 示例 |
| ---- | ---- |
| 固定长度 | 每条消息固定 64 字节 |
| 分隔符 | HTTP Header 使用 CRLF |
| 长度前缀 | 前 4 字节表示消息长度 |
| 自描述格式 | HTTP Chunked、部分序列化协议 |
| 连接关闭 | HTTP/1.0 可用关闭表示消息结束 |

### 3. 正确读取方式

应用不能假设一次 `recv()` 就获得完整消息，应：

```text
1. 把收到的字节加入缓冲区
2. 按协议规则判断完整消息
3. 取出一条或多条完整消息
4. 保留不完整尾部，等待下次读取
```

---

## 十三、Socket 与服务器工作流程

### 1. TCP 服务器

```text
socket()
   ↓
bind()
   ↓
listen()
   ↓
accept()
   ↓
read()/write()
   ↓
close()
```

### 2. TCP 客户端

```text
socket()
   ↓
connect()
   ↓
read()/write()
   ↓
close()
```

### 3. 监听 socket 与连接 socket

- 监听 socket：处于 LISTEN，接收新连接
- 连接 socket：由 `accept()` 返回，对应具体四元组
- 一个监听 socket 可以派生很多连接 socket

### 4. 连接队列

服务器通常维护：

- 尚未完成握手的 SYN 队列
- 已完成握手、等待应用 `accept()` 的队列

队列已满、应用处理太慢或遭遇 SYN Flood 时，新连接可能超时或被拒绝。

### 5. 阻塞与非阻塞

| 模式 | 特点 |
| ---- | ---- |
| 阻塞 I/O | 调用等待完成，编程简单 |
| 非阻塞 I/O | 未就绪时立即返回，需要事件循环 |
| I/O 多路复用 | select/poll/epoll/kqueue 管理大量连接 |
| 异步 I/O | 完成后通知应用，模型依平台而异 |

---

## 十四、TCP 性能相关机制

### 1. Nagle 算法

Nagle 算法减少大量小报文：

```text
有未确认数据时，暂存新的小块数据
直到收到 ACK 或积累到一个 MSS
```

适合吞吐优先场景，但可能增加交互延迟。低延迟应用可按需启用 `TCP_NODELAY`，不应无条件关闭。

### 2. Delayed ACK

接收方可能短暂等待：

- 看能否把 ACK 搭载在反向数据上
- 看能否用一个 ACK 确认多个报文段

Delayed ACK 与 Nagle 组合不当可能造成额外延迟。

### 3. ACK Piggyback

全双工通信中，ACK 可以与反向发送的数据放在同一 TCP 报文段中，减少纯 ACK 数量。

### 4. 连接复用

减少反复握手和慢启动的方法：

- HTTP Keep-Alive
- 数据库连接池
- RPC 长连接
- HTTP/2 多路复用

连接池应设置：

- 最大连接数
- 空闲超时
- 连接最大寿命
- 健康检查
- 获取连接超时

### 5. 带宽时延积

```text
BDP = 带宽 × RTT
```

要充分利用高带宽、高延迟链路，发送窗口和接收窗口通常需要至少覆盖 BDP。

示例：

```text
带宽 1 Gbit/s
RTT 100 ms
BDP ≈ 12.5 MB
```

窗口过小会导致链路无法跑满。

---

## 十五、TCP 保活与应用心跳

### 1. TCP Keepalive

空闲连接启用 Keepalive 后，内核会周期性探测对端是否仍可达。

Linux 常见参数：

```bash
sysctl net.ipv4.tcp_keepalive_time
sysctl net.ipv4.tcp_keepalive_intvl
sysctl net.ipv4.tcp_keepalive_probes
```

### 2. Keepalive 的限制

- 默认探测间隔通常很长
- 只能判断连接层面是否可达
- 不能确认应用是否健康
- 中间 NAT、防火墙可能更早清理空闲连接

### 3. 应用层心跳

应用心跳可以携带协议语义：

```text
PING → PONG
```

适用于：

- 快速发现应用无响应
- 保持 NAT 映射
- 测量业务级延迟
- 触发故障切换

应避免所有连接在同一时刻发送心跳，可加入抖动并合理设置超时。

---

## 十六、TCP 安全

### 1. SYN Flood

攻击者发送大量 SYN，但不完成握手，使服务器半连接队列耗尽。

防护措施：

- SYN Cookies
- 增大合理的连接队列
- 限速和防火墙清洗
- 缩短异常半连接占用时间
- 上游 DDoS 防护

### 2. SYN Cookies

服务器不立即保存完整半连接状态，而把必要信息编码到 SYN+ACK 的序列号中。客户端返回合法 ACK 后再创建连接状态。

优点：减轻 SYN 队列耗尽。

限制：部分 TCP 选项信息可能受实现限制，且它不能替代完整的流量清洗。

### 3. TCP RST 注入

如果攻击者能够猜中连接四元组和有效序列号范围，可能伪造 RST 中断连接。

防护：

- 使用 TLS、IPsec 等保护上层数据或链路
- 使用不可预测的初始序列号
- 避免不可信网络中的明文管理协议
- 采用符合标准的 RST 校验策略

### 4. 会话劫持

TCP 本身不加密、不认证应用数据。能够观察并注入流量的攻击者可能劫持明文连接。

应使用：

- TLS / HTTPS
- SSH
- IPsec / WireGuard
- 强身份认证和证书校验

### 5. 端口扫描

常见 SYN 扫描结果：

```text
开放端口: SYN → SYN+ACK
关闭端口: SYN → RST
过滤端口: 无响应或 ICMP 错误
```

防护重点是减少不必要的监听服务、限制来源并持续更新服务，而不是仅隐藏端口。

---

## 十七、抓包分析

### 1. tcpdump

```bash
# 抓取某端口的 TCP 流量
sudo tcpdump -i any -n 'tcp port 443'

# 抓取指定主机
sudo tcpdump -i any -n 'tcp and host 192.0.2.10'

# 只看 SYN
sudo tcpdump -i any -n 'tcp[tcpflags] & tcp-syn != 0'

# 保存抓包
sudo tcpdump -i any -n tcp -w tcp.pcap
```

### 2. Wireshark 过滤器

```text
tcp
tcp.port == 443
tcp.stream eq 0
tcp.flags.syn == 1
tcp.flags.reset == 1
tcp.analysis.retransmission
tcp.analysis.fast_retransmission
tcp.analysis.duplicate_ack
tcp.analysis.zero_window
```

### 3. 握手抓包

```text
SYN       Seq=0  MSS=1460 SACK_PERM WS=7
SYN, ACK  Seq=0  Ack=1 MSS=1460 SACK_PERM WS=7
ACK       Seq=1  Ack=1
```

Wireshark 默认显示相对序列号，因此初始 SYN 常显示为 `Seq=0`。

### 4. 常见异常

| 抓包现象 | 可能原因 |
| -------- | -------- |
| SYN 重传，无响应 | 路由、防火墙、服务未到达 |
| 立即收到 RST | 端口未监听或主动拒绝 |
| SYN+ACK 重传 | 客户端 ACK 未到服务器 |
| 大量重传 | 丢包、拥塞、链路质量差 |
| Zero Window | 接收应用读取太慢 |
| Window Full | 发送量达到接收窗口 |
| Out-of-Order | 多路径、丢包或抓包位置影响 |
| 握手成功，大包卡住 | MTU/PMTUD、防火墙丢 ICMP |

---

## 十八、常用排查命令

### 1. 查看连接

```bash
# Linux
ss -tan
ss -ltnp
ss -s

# 查看某个目的端口
ss -tan dst :443

# 查看 TCP 详细信息
ss -ti
```

### 2. 测试端口

```bash
nc -vz example.com 443
curl -v https://example.com/
```

### 3. 查看内核统计

```bash
nstat -az
netstat -s
```

重点关注：

- 重传报文段
- 连接失败
- Listen 队列溢出
- RST 数量
- 超时数量

### 4. 查看进程和端口

```bash
ss -ltnp
lsof -nP -iTCP -sTCP:LISTEN
```

### 5. 路径和 MTU

```bash
tracepath example.com
ping -M do -s 1472 192.0.2.10   # Linux IPv4，测试 1500 MTU
```

---

## 十九、TCP 故障排查

### 1. 排查流程

```text
1. DNS:域名是否解析正确
2. 路由:目标 IP 是否可达
3. 端口:服务是否监听正确地址和端口
4. 防火墙:客户端、服务器和中间设备是否放行
5. 握手:SYN、SYN+ACK、ACK 在哪里丢失
6. 数据:是否重传、零窗口、RST、MTU 黑洞
7. 应用:是否及时 accept/read/write/close
8. 性能:RTT、丢包、窗口、拥塞控制、连接池
```

### 2. Connection Refused

```text
connect: Connection refused
```

通常表示目标主机返回 RST：

- 端口未监听
- 服务监听在错误地址
- 防火墙使用 REJECT
- 访问了错误 IP 或端口

### 3. Connection Timed Out

```text
connect: Connection timed out
```

通常表示 SYN 或响应被静默丢弃：

- 路由错误
- 防火墙 DROP
- 安全组未放行
- 目标主机离线
- 回程路由错误

### 4. Connection Reset

```text
Connection reset by peer
```

表示收到 RST，可能原因：

- 对端应用异常终止
- 协议或请求不符合预期
- 中间设备主动断开
- 向已关闭连接继续发送
- 应用未读取数据就强制关闭

### 5. 大量 TIME_WAIT

优先检查：

- 是否每次请求都新建连接
- 是否可使用 Keep-Alive 或连接池
- 上游是否主动要求关闭
- 负载是否确实需要这么多短连接

TIME_WAIT 本身是正常状态，不应只因数量大就修改内核参数。

### 6. 大量 CLOSE_WAIT

优先定位持有 socket 的进程和调用路径：

```text
对端已经关闭 → 本地应用没有 close()
```

通常应修复应用代码，而不是调低系统超时。

### 7. 吞吐低

检查：

- RTT 和丢包率
- 接收/发送窗口
- BDP 是否大于缓冲区
- 拥塞控制算法
- CPU、网卡和加密开销
- 应用是否小块同步读写
- 是否存在重传或 MTU 问题

### 8. 常见问题对照

| 问题 | 常见原因 | 重点检查 |
| ---- | -------- | -------- |
| 无法建立连接 | 路由、端口、防火墙 | SYN 流向、监听状态 |
| 建连很慢 | 丢包、SYN 重传、DNS | 抓包、RTT、解析时间 |
| 连接频繁断开 | 超时、RST、NAT 清理 | Keepalive、应用日志 |
| 传输卡住 | 零窗口、MTU 黑洞 | `ss -ti`、抓包 |
| 重传很多 | 拥塞、链路丢包 | 接口错误、路径质量 |
| CLOSE_WAIT 多 | 应用未关闭连接 | 文件描述符、代码路径 |
| TIME_WAIT 多 | 大量主动关闭短连接 | 连接池、Keep-Alive |
| 偶发数据重复 | 应用重试非幂等操作 | 业务请求 ID、幂等设计 |

---

## 二十、TCP 与 UDP 对比

| 维度 | TCP | UDP |
| ---- | --- | --- |
| 连接 | 面向连接 | 无连接 |
| 数据形式 | 字节流 | 数据报 |
| 可靠性 | 确认、重传、有序 | 不保证 |
| 消息边界 | 不保留 | 保留 |
| 流量控制 | 有 | 无 |
| 拥塞控制 | 有 | 协议/应用自行实现 |
| 首部 | 20~60 字节 | 固定 8 字节 |
| 广播/组播 | 不支持 | 支持 |
| 延迟 | 建连和控制开销较高 | 开销较低 |
| 典型应用 | HTTP/1.1、HTTP/2、SSH、数据库 | DNS、实时音视频、QUIC |

选择原则：

- 需要可靠、有序字节流：TCP
- 需要数据报、组播、低开销或自定义可靠性：UDP
- 不应只根据“速度快慢”选择，应根据应用语义和网络需求选择

---

## 二十一、核心要点速记

- **TCP = 面向连接、可靠、全双工、字节流协议**
- **TCP 连接由源 IP、源端口、目的 IP、目的端口标识**
- **TCP 固定首部 20 字节，最大 60 字节**
- **三次握手：SYN → SYN+ACK → ACK**
- **四次挥手：FIN → ACK → FIN → ACK**
- **SYN 和 FIN 各消耗一个序列号，纯 ACK 不消耗**
- **ACK 表示下一步期望收到的字节序号**
- **TCP 默认使用累积确认**
- **超时重传依据动态 RTO，不是固定时间**
- **SACK 允许只重传缺失区间**
- **rwnd 用于流量控制，保护接收方**
- **cwnd 用于拥塞控制，保护网络**
- **实际发送窗口约为 `min(rwnd, cwnd)`**
- **经典拥塞控制包括慢启动、拥塞避免、快速重传和快速恢复**
- **MSS 是 TCP 数据大小，MTU 是链路可承载的 IP 包大小**
- **普通 IPv4 以太网常见 MSS = 1460**
- **TCP 是字节流，不保留应用写入的消息边界**
- **应用必须自行设计定长、分隔符或长度前缀协议**
- **TIME_WAIT 通常在主动关闭方，作用是处理旧报文和最终 ACK 重传**
- **大量 CLOSE_WAIT 通常表示应用没有正确关闭 socket**
- **Nagle 减少小报文，`TCP_NODELAY` 可用于低延迟场景**
- **TCP Keepalive 不等于应用健康检查**
- **TCP 本身不加密，应使用 TLS、SSH、IPsec 等保护数据**
- **Connection Refused 通常对应 RST**
- **Connection Timed Out 通常对应报文被静默丢弃**
- **握手成功但大数据卡住，应检查 MTU、PMTUD 和 ICMP**
- **`ss -tan` 查看连接，`ss -ti` 查看 TCP 详细状态**
- **Wireshark 的 `tcp.analysis.retransmission` 可筛选重传**
