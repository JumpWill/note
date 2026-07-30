# DNS 协议 (Domain Name System)

## 一、DNS 概述

### 什么是 DNS

**DNS (Domain Name System，域名系统)**：把便于人类记忆的域名转换为计算机通信使用的 IP 地址，并保存邮件服务器、别名、服务发现等信息。

```text
www.example.com
        ↓ DNS 查询
93.184.216.34
        ↓ 建立 TCP/QUIC 连接
访问目标服务
```

DNS 的主要作用：

- 域名解析为 IPv4 / IPv6 地址
- IP 地址反向查询域名
- 查找邮件服务器
- 服务发现和负载分配
- 发布域名所有权验证、证书策略等信息
- 通过缓存降低查询延迟和权威服务器压力

### DNS 的特点

- **分布式**：全球数据由不同组织分别管理
- **分层**：根域、顶级域、二级域逐级委派
- **高可用**：一个区域通常部署多个权威服务器
- **可缓存**：响应由 TTL 控制缓存时间
- **最终一致**：记录修改后需要等待各级缓存更新
- **大小写不敏感**：`Example.COM` 与 `example.com` 等价

### DNS 在协议栈中的位置

| 层次 | 协议 | 说明 |
| ---- | ---- | ---- |
| 应用层 | DNS | 域名与资源记录查询 |
| 传输层 | UDP / TCP / TLS / HTTPS / QUIC | 承载 DNS 报文 |
| 网络层 | IPv4 / IPv6 | 传输数据包 |
| 链路层 | Ethernet、Wi-Fi | 本地链路通信 |

---

## 二、DNS 名称空间

### 1. 域名层级

```text
                         .  根域
                         │
              ┌──────────┼──────────┐
             com        org        cn       顶级域
              │                     │
           example                 com       二级域
              │                     │
       ┌──────┼──────┐            baidu
      www    mail   api             │
                                  www
```

以 `www.example.com.` 为例：

| 部分 | 含义 |
| ---- | ---- |
| `.` | 根域 |
| `com` | 顶级域 TLD |
| `example` | 二级域/注册域 |
| `www` | 主机名或子域标签 |

### 2. FQDN

**FQDN (Fully Qualified Domain Name，完全限定域名)**：从主机名一直写到根域的完整名称。

```text
www.example.com.
```

末尾的 `.` 代表根域，日常使用时通常省略。

### 3. 域名长度限制

- 每个标签最长 63 字节
- DNS 线格式中的完整名称最长 255 字节，包含分隔信息和根标签
- 常见文本形式最多 253 个字符，不包含末尾根域点
- 标签之间使用 `.` 分隔
- DNS 本身允许的字符范围比常见主机名规则更广

### 4. 国际化域名

国际化域名通过 **IDNA** 转换为 ASCII 兼容形式：

```text
中文域名.example
        ↓ IDNA
xn--...example
```

以 `xn--` 开头的标签称为 **Punycode** 编码标签。

---

## 三、DNS 系统组成

### 1. Stub Resolver (存根解析器)

运行在客户端操作系统中：

- 接收应用程序的域名查询
- 查看本地缓存和 hosts 文件
- 把请求发送给配置的递归 DNS 服务器
- 通常不自行遍历整个 DNS 层级

### 2. Recursive Resolver (递归解析器)

也称**递归 DNS 服务器**或**缓存 DNS 服务器**：

- 代替客户端完成完整查询
- 依次访问根、TLD 和权威服务器
- 缓存查询结果
- 常见来源为 ISP、企业、路由器或公共 DNS 服务

常见公共递归 DNS：

| 服务 | IPv4 | IPv6 |
| ---- | ---- | ---- |
| Cloudflare | 1.1.1.1 | 2606:4700:4700::1111 |
| Google | 8.8.8.8 | 2001:4860:4860::8888 |
| Quad9 | 9.9.9.9 | 2620:fe::fe |
| 阿里公共 DNS | 223.5.5.5 | 2400:3200::1 |

### 3. Root Name Server (根名称服务器)

- 保存顶级域的委派信息
- 告诉解析器应向哪个 TLD 服务器查询
- 不直接保存普通网站的最终 IP
- 共有 A 到 M 十三个**逻辑根服务器标识**
- 每个逻辑根通过 Anycast 部署了许多全球实例

### 4. TLD Name Server (顶级域服务器)

管理顶级域的委派信息：

- `.com`
- `.org`
- `.net`
- `.cn`
- `.io`

TLD 服务器通常返回目标注册域的权威 DNS 服务器地址。

### 5. Authoritative Name Server (权威名称服务器)

- 保存某个 DNS 区域的正式数据
- 对区域内记录给出权威回答
- 不需要为客户端递归查询其他区域
- 一个区域通常至少有主、备两个权威服务器

### 6. 各角色对比

| 角色 | 保存内容 | 是否递归 | 是否缓存 |
| ---- | -------- | -------- | -------- |
| 客户端存根 | 本机少量数据 | 通常否 | 可以 |
| 递归解析器 | 查询缓存 | 是 | 是 |
| 根服务器 | TLD 委派 | 否 | 实现可缓存 |
| TLD 服务器 | 注册域委派 | 否 | 实现可缓存 |
| 权威服务器 | 区域正式记录 | 否 | 以权威数据为准 |

---

## 四、DNS 解析过程

### 1. 完整递归解析

客户端首次查询 `www.example.com`：

```text
客户端
  │ 1. www.example.com 是什么地址?
  ▼
递归 DNS
  │ 2. 询问根服务器
  ▼
根服务器
  │ 3. 返回 .com TLD 服务器
  ▼
.com TLD 服务器
  │ 4. 返回 example.com 权威服务器
  ▼
example.com 权威服务器
  │ 5. 返回 www.example.com 的 A/AAAA 记录
  ▼
递归 DNS
  │ 6. 缓存结果并返回客户端
  ▼
客户端访问目标 IP
```

### 2. 递归查询与迭代查询

| 类型 | 请求方期望 | 常见场景 |
| ---- | ---------- | -------- |
| **递归查询** | 服务器返回最终结果或错误 | 客户端 → 递归解析器 |
| **迭代查询** | 服务器返回自己知道的最佳答案或下一步委派 | 递归解析器 → 根/TLD/权威服务器 |

递归查询通常设置 DNS 头部的 **RD (Recursion Desired)** 标志。

### 3. 本机解析顺序

实际顺序由操作系统配置决定，Linux 常由 `/etc/nsswitch.conf` 控制：

```text
hosts: files dns
```

典型过程：

```text
1. 应用或浏览器内部缓存
2. 操作系统 DNS 缓存
3. hosts 文件
4. 配置的递归 DNS 服务器
```

不同系统和应用可能调整顺序，浏览器也可能直接使用 DoH。

### 4. 缓存命中

```text
第一次查询:
客户端 → 递归 DNS → 根 → TLD → 权威

TTL 有效期内再次查询:
客户端 → 递归 DNS → 直接返回缓存
```

缓存可以显著降低：

- 查询延迟
- 网络流量
- 根、TLD 和权威服务器压力

### 5. CNAME 查询链

```text
www.example.com CNAME web.cdn.example.net.
web.cdn.example.net A 203.0.113.20
```

解析器需要继续查询别名目标，最终获得 A 或 AAAA 记录。过长的 CNAME 链会增加查询延迟，也可能触发解析器限制。

---

## 五、DNS 资源记录

### 1. 记录基本格式

```text
NAME        TTL     CLASS   TYPE    RDATA
www         300     IN      A       192.0.2.10
```

| 字段 | 含义 |
| ---- | ---- |
| **NAME** | 记录名称 |
| **TTL** | 缓存有效时间，单位秒 |
| **CLASS** | 地址族，互联网通常为 IN |
| **TYPE** | 记录类型 |
| **RDATA** | 记录数据 |

### 2. 常用记录类型

| 类型 | 作用 | 示例 |
| ---- | ---- | ---- |
| **A** | 域名 → IPv4 | `www IN A 192.0.2.10` |
| **AAAA** | 域名 → IPv6 | `www IN AAAA 2001:db8::10` |
| **CNAME** | 别名 → 规范名称 | `www IN CNAME web.example.net.` |
| **MX** | 邮件服务器 | `@ IN MX 10 mail.example.com.` |
| **NS** | 区域的权威服务器 | `@ IN NS ns1.example.com.` |
| **TXT** | 文本、验证和策略 | `@ IN TXT "..."` |
| **PTR** | IP 反向解析为域名 | `10 IN PTR host.example.com.` |
| **SOA** | 区域起始授权信息 | 序列号、定时器等 |
| **SRV** | 服务位置和端口 | `_sip._tcp IN SRV ...` |
| **CAA** | 指定允许签发证书的 CA | `@ IN CAA 0 issue "letsencrypt.org"` |
| **NAPTR** | 基于规则的服务发现 | SIP、ENUM 等 |
| **HTTPS** | HTTPS 服务参数 | HTTP/3、ECH 等提示 |
| **SVCB** | 通用服务绑定 | 服务端点和连接参数 |

### 3. A 与 AAAA

```dns
www     300 IN A     192.0.2.10
www     300 IN AAAA  2001:db8::10
```

同一名称可以配置多个地址，用于：

- 简单负载分配
- 多机房部署
- 故障切换
- IPv4 / IPv6 双栈

### 4. CNAME

```dns
blog    300 IN CNAME pages.example.net.
```

注意：

- CNAME 指向的是域名，不能直接指向 IP
- 同一名称存在 CNAME 时，通常不能再配置 A、MX 等其他数据
- 区域顶点需要 SOA、NS 等记录，因此不能使用标准 CNAME
- 部分 DNS 服务商提供 ALIAS / ANAME 等非标准顶点别名功能

### 5. MX

```dns
@       3600 IN MX 10 mail1.example.com.
@       3600 IN MX 20 mail2.example.com.
mail1   3600 IN A     192.0.2.25
mail2   3600 IN A     192.0.2.26
```

- 数字越小，优先级越高
- MX 目标应为可解析的主机名
- 邮件服务器地址通常同时配置 SPF、DKIM、DMARC 相关 TXT 记录

### 6. TXT

常见用途：

```dns
# SPF
@               IN TXT "v=spf1 include:_spf.example.net -all"

# 域名所有权验证
_acme-challenge IN TXT "verification-token"

# DMARC
_dmarc          IN TXT "v=DMARC1; p=quarantine"
```

TXT 记录可以保存多段字符串，应用读取时通常把它们拼接处理。

### 7. SOA

```dns
@ IN SOA ns1.example.com. hostmaster.example.com. (
    2026073001 ; Serial
    3600       ; Refresh
    900        ; Retry
    1209600    ; Expire
    300        ; Negative Cache TTL
)
```

| 字段 | 含义 |
| ---- | ---- |
| **MNAME** | 主权威服务器 |
| **RNAME** | 管理员邮箱，首个 `.` 代表 `@` |
| **Serial** | 区域版本号 |
| **Refresh** | 辅服务器检查更新间隔 |
| **Retry** | 更新失败后的重试间隔 |
| **Expire** | 长期无法同步后停止提供区域数据的时间 |
| **Minimum** | 现代标准中用于否定缓存 TTL |

### 8. SRV

```dns
_sip._tcp.example.com. 3600 IN SRV 10 20 5060 sip1.example.com.
```

字段顺序：

```text
优先级 权重 端口 目标主机
```

SRV 常用于 LDAP、SIP、Kerberos、Minecraft 等服务发现。

---

## 六、正向解析与反向解析

### 1. 正向解析

```text
域名 → IP 地址
```

使用记录：

- A：IPv4
- AAAA：IPv6

### 2. IPv4 反向解析

IPv4 使用 `in-addr.arpa` 区域，并反转地址顺序：

```text
IP: 192.0.2.10
PTR 查询名:10.2.0.192.in-addr.arpa.
```

```dns
10 IN PTR host.example.com.
```

### 3. IPv6 反向解析

IPv6 使用 `ip6.arpa`，按十六进制半字节反转：

```text
2001:db8::1
        ↓
1.0.0.0....8.b.d.0.1.0.0.2.ip6.arpa.
```

### 4. 反向解析用途

- 邮件服务器信誉检查
- 日志显示主机名
- 网络排障
- 某些访问控制和审计系统

PTR 记录由 IP 地址所有者或上游网络服务商管理，不一定由域名的 DNS 服务商管理。

---

## 七、DNS 报文格式

### 1. DNS 报文结构

```text
+---------------------+
| Header              | 固定 12 字节
+---------------------+
| Question            | 查询问题
+---------------------+
| Answer              | 回答记录
+---------------------+
| Authority           | 权威/委派信息
+---------------------+
| Additional          | 附加信息
+---------------------+
```

### 2. Header

```text
0                   15                  31
+-------------------+-------------------+
| ID                | Flags             |
+-------------------+-------------------+
| QDCOUNT           | ANCOUNT           |
+-------------------+-------------------+
| NSCOUNT           | ARCOUNT           |
+-------------------+-------------------+
```

| 字段 | 含义 |
| ---- | ---- |
| **ID** | 查询标识，用于匹配请求与响应 |
| **Flags** | 查询类型、状态和能力标志 |
| **QDCOUNT** | Question 数量 |
| **ANCOUNT** | Answer 记录数量 |
| **NSCOUNT** | Authority 记录数量 |
| **ARCOUNT** | Additional 记录数量 |

### 3. 常见标志位

| 标志 | 含义 |
| ---- | ---- |
| **QR** | 0=查询，1=响应 |
| **Opcode** | 操作类型，通常为标准查询 |
| **AA** | 权威回答 |
| **TC** | 响应被截断 |
| **RD** | 请求递归 |
| **RA** | 服务器支持递归 |
| **AD** | DNSSEC 数据已通过验证 |
| **CD** | 客户端要求禁用 DNSSEC 检查 |
| **RCODE** | 响应状态码 |

### 4. 名称压缩

DNS 报文可以使用指针复用前面出现过的域名后缀：

- 减少重复名称占用的字节
- 指针最高两位为 `11`
- 常见于 Answer、Authority 和 Additional 区域

### 5. EDNS(0)

传统 UDP DNS 报文通常以 512 字节为基础限制。**EDNS(0)** 使用伪 OPT 记录扩展能力：

- 协商更大的 UDP 载荷
- 支持 DNSSEC 的 DO 标志
- 携带扩展选项
- 降低因响应过大而回退 TCP 的概率

为避免 IP 分片，实际部署常使用较保守的 UDP 载荷大小。

---

## 八、DNS 传输协议与端口

### 1. 传统 DNS

| 协议 | 端口 | 用途 |
| ---- | ---- | ---- |
| UDP | 53 | 普通查询的首选方式 |
| TCP | 53 | 响应截断后重试、区域传送、大型响应等 |

DNS 客户端和服务器都应支持 UDP 与 TCP 53。

### 2. UDP 查询

优点：

- 无需建立连接
- 报文开销小
- 查询延迟低

限制：

- 不保证到达和顺序
- 大响应可能被截断或分片
- 传统明文传输，可被路径上的设备观察和篡改

### 3. TCP 查询

```text
建立 TCP 连接
        ↓
发送 2 字节长度字段 + DNS 报文
        ↓
接收响应
```

常见使用场景：

- UDP 响应设置 TC 标志
- AXFR / IXFR 区域传送
- DNSSEC 等导致响应较大
- 网络策略要求使用 TCP

### 4. 加密 DNS

| 协议 | 端口 | 传输方式 | 特点 |
| ---- | ---- | -------- | ---- |
| **DoT** | TCP 853 | DNS over TLS | 独立端口，易识别 |
| **DoH** | TCP/QUIC 443 | DNS over HTTPS | 与 Web 流量融合 |
| **DoQ** | UDP 853 | DNS over QUIC | 低延迟、多路复用 |

加密 DNS 保护客户端到递归解析器之间的传输，但不会自动保证域名数据真实，也不会隐藏客户端随后连接的目标 IP。

### 5. DNSSEC 与加密 DNS 的区别

| 技术 | 解决的问题 | 是否加密查询内容 |
| ---- | ---------- | ---------------- |
| **DNSSEC** | 验证数据来源和完整性 | 否 |
| **DoT / DoH / DoQ** | 加密客户端到解析器的传输 | 是 |

两者可以同时使用，解决不同安全问题。

---

## 九、区域、委派与区域传送

### 1. Domain 与 Zone

- **Domain**：域名树中的一个节点及其后代
- **Zone**：由某组权威服务器实际管理的数据范围
- 子域被委派后，父区域只保留委派信息，不再管理子区域内部记录

### 2. 区域委派

父区域通过 NS 记录把子域管理权交给其他权威服务器：

```dns
sub.example.com. IN NS ns1.sub.example.com.
sub.example.com. IN NS ns2.provider.net.
```

### 3. Glue Record

如果权威服务器名称位于被委派的子域内部，会形成循环依赖：

```text
要解析 sub.example.com
需要找到 ns1.sub.example.com
但 ns1.sub.example.com 又属于 sub.example.com
```

父区域会附带权威服务器的 A / AAAA 地址，这些地址称为 **Glue Record**。

### 4. 主从权威服务器

```text
Primary/Master
      │ 区域传送
      ├──────────→ Secondary 1
      └──────────→ Secondary 2
```

- 主服务器维护区域原始数据
- 辅服务器复制区域数据并对外提供权威回答
- SOA Serial 变化用于判断是否需要更新

### 5. 区域传送

| 类型 | 说明 |
| ---- | ---- |
| **AXFR** | 完整区域传送 |
| **IXFR** | 增量区域传送 |
| **NOTIFY** | 主服务器通知辅服务器区域已更新 |

区域传送通常使用 TCP 53，并应通过 ACL、TSIG 等方式限制授权服务器访问。

---

## 十、DNS 缓存与 TTL

### 1. TTL

```dns
www 300 IN A 192.0.2.10
```

`300` 表示缓存可保存 300 秒。

| TTL | 优点 | 缺点 |
| --- | ---- | ---- |
| 较短 | 变更生效快、故障切换快 | 查询量和权威压力增加 |
| 较长 | 查询少、缓存命中率高 | 变更传播慢 |

### 2. 多级缓存

```text
浏览器缓存
    ↓
操作系统缓存
    ↓
本地路由器/企业 DNS
    ↓
ISP 或公共递归 DNS
```

任一级缓存命中都可能直接返回结果。

### 3. 否定缓存

不存在的名称或记录类型也可以缓存：

```text
NXDOMAIN:名称不存在
NODATA:名称存在，但请求的记录类型不存在
```

否定缓存时间通常由权威区域 SOA 数据决定，可避免反复查询不存在的名称。

### 4. DNS 修改的正确操作

```text
1. 变更前提前降低 TTL
2. 等待旧 TTL 过期
3. 修改 DNS 记录
4. 验证各权威服务器数据一致
5. 等待递归缓存更新
6. 稳定后恢复正常 TTL
```

临时降低 TTL 不能清除已经缓存的旧记录。

### 5. 缓存刷新命令

```text
# Linux(systemd-resolved)
resolvectl flush-caches

# Windows
ipconfig /flushdns

# macOS
sudo dscacheutil -flushcache
sudo killall -HUP mDNSResponder
```

刷新本机缓存不会清除递归 DNS 服务器上的缓存。

---

## 十一、DNSSEC

### 1. DNSSEC 解决的问题

**DNSSEC (DNS Security Extensions)** 为 DNS 数据提供：

- 来源认证
- 数据完整性验证
- 不存在性证明

DNSSEC **不提供查询内容加密**。

### 2. 主要记录

| 记录 | 作用 |
| ---- | ---- |
| **DNSKEY** | 发布区域公钥 |
| **RRSIG** | 对资源记录集合签名 |
| **DS** | 父区域保存对子区域密钥的摘要 |
| **NSEC / NSEC3** | 证明名称或记录不存在 |

### 3. 信任链

```text
根信任锚
   ↓ 验证
TLD 的 DS / DNSKEY
   ↓ 验证
example.com 的 DS / DNSKEY
   ↓ 验证
www.example.com 的 A / AAAA + RRSIG
```

### 4. 验证结果

| 状态 | 含义 |
| ---- | ---- |
| **Secure** | 签名和信任链验证成功 |
| **Insecure** | 区域未部署 DNSSEC，但委派状态合法 |
| **Bogus** | 应可验证但签名、时间或信任链错误 |
| **Indeterminate** | 无法确定验证状态 |

### 5. 常见故障

- RRSIG 过期
- DS 与子区域 DNSKEY 不匹配
- 密钥轮换顺序错误
- 服务器时间不准确
- 响应过大被防火墙丢弃
- TCP 53 被错误阻断

---

## 十二、DNS 安全

### 1. 缓存投毒

攻击者伪造 DNS 响应，使解析器缓存错误记录：

```text
www.bank.example → 攻击者 IP
```

常见防护：

- DNSSEC 验证
- 随机查询 ID
- 随机源端口
- 严格匹配查询名称、类型和响应来源
- 及时更新 DNS 软件

### 2. DNS 劫持

可能发生在：

- 恶意软件修改本机 DNS 配置
- 路由器被入侵
- 不可信网络篡改明文 DNS
- 递归 DNS 服务主动返回错误结果

防护措施：

- 保护路由器和终端管理密码
- 使用可信递归 DNS
- 使用 DoT / DoH / DoQ
- 使用 DNSSEC 验证
- 监控解析结果变化

### 3. DNS 放大攻击

攻击者伪造受害者源 IP，向开放递归服务器发送小查询，引导服务器向受害者返回大响应。

防护措施：

- 禁止向公网开放不受控递归
- 实施源地址验证 BCP 38
- 启用响应速率限制 RRL
- 限制 ANY 等高放大查询
- 监控异常查询和响应流量

### 4. DNS Rebinding

攻击域名先解析到公网地址，随后快速切换到内网地址，诱导浏览器访问内部服务。

防护措施：

- 浏览器和应用实施同源及目标校验
- 递归 DNS 启用 Rebinding Protection
- 内部服务验证 Host / Origin
- 管理接口要求身份认证，不依赖“仅内网可达”

### 5. 隧道与数据外传

DNS 查询名称可以携带编码数据：

```text
encoded-data.attacker.example
```

防护措施：

- 终端只允许访问指定企业 DNS
- 监控超长、高熵和高频子域查询
- 限制未知 DoH 服务
- 对异常 TXT、NULL 等查询告警

---

## 十三、DNS 部署与配置

### 1. Linux 客户端配置

```bash
# 查看当前 DNS 状态
resolvectl status

# 查询 resolv.conf
cat /etc/resolv.conf
```

典型配置：

```text
nameserver 192.168.1.1
nameserver 1.1.1.1
search example.com
```

现代 Linux 中 `/etc/resolv.conf` 可能由 NetworkManager、systemd-resolved 或 DHCP 自动管理，不应直接长期修改。

### 2. BIND 区域文件示例

```dns
$TTL 3600
@ IN SOA ns1.example.com. hostmaster.example.com. (
    2026073001
    3600
    900
    1209600
    300
)

@       IN NS    ns1.example.com.
@       IN NS    ns2.example.com.
ns1     IN A     192.0.2.53
ns2     IN A     192.0.2.54
@       IN A     192.0.2.10
www     IN A     192.0.2.10
mail    IN A     192.0.2.25
@       IN MX 10 mail.example.com.
```

区域文件中的相对名称会自动追加当前区域名，绝对域名应以 `.` 结尾。

### 3. 检查 BIND 配置

```bash
named-checkconf
named-checkzone example.com /etc/bind/db.example.com
```

### 4. Split DNS (分离 DNS)

同一名称对不同来源返回不同结果：

```text
内网客户端:
app.example.com → 10.0.0.20

公网客户端:
app.example.com → 203.0.113.20
```

适用场景：

- 内外网使用同一域名
- 内部服务发现
- 避免内网流量绕公网

需要注意内外记录一致性和排障复杂度。

### 5. Anycast DNS

多个地点使用同一个服务 IP，由路由协议把请求送到就近节点：

- 降低全球访问延迟
- 提高抗故障能力
- 分散查询压力
- 根服务器和大型公共 DNS 广泛使用

---

## 十四、DNS 查询工具

### 1. dig

```bash
# 查询 A 记录
dig www.example.com

# 查询指定类型
dig example.com MX
dig example.com TXT
dig example.com NS

# 使用指定 DNS 服务器
dig @1.1.1.1 www.example.com A

# 只显示简短答案
dig +short www.example.com

# 追踪委派链
dig +trace www.example.com

# 使用 TCP
dig +tcp www.example.com

# 请求 DNSSEC 数据
dig +dnssec example.com

# 反向查询
dig -x 192.0.2.10
```

### 2. dig 输出结构

```text
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 12345
;; flags: qr rd ra; QUERY: 1, ANSWER: 1

;; QUESTION SECTION:
;www.example.com.       IN A

;; ANSWER SECTION:
www.example.com. 300    IN A 192.0.2.10
```

重点字段：

- `status`：响应状态
- `flags`：AA、RD、RA、AD 等
- `ANSWER`：最终答案
- `AUTHORITY`：权威或委派信息
- `ADDITIONAL`：附加地址、OPT 等
- `Query time`：查询耗时
- `SERVER`：实际响应服务器

### 3. nslookup

```bash
nslookup www.example.com
nslookup -type=mx example.com
nslookup www.example.com 8.8.8.8
```

### 4. host

```bash
host www.example.com
host -t mx example.com
host 192.0.2.10
```

### 5. resolvectl

```bash
resolvectl query www.example.com
resolvectl status
resolvectl statistics
```

### 6. 抓包

```bash
# 抓取传统 DNS
sudo tcpdump -i any -n port 53

# 保存后用 Wireshark 分析
sudo tcpdump -i any -n port 53 -w dns.pcap
```

Wireshark 过滤器：

```text
dns
dns.flags.response == 0
dns.flags.response == 1
dns.qry.name == "www.example.com"
dns.flags.rcode != 0
```

DoH 内容位于加密的 HTTPS 流量中，普通链路抓包无法直接看到具体 DNS 查询。

---

## 十五、DNS 响应状态码

| RCODE | 名称 | 含义 |
| ----- | ---- | ---- |
| 0 | **NOERROR** | 查询成功，或名称存在但无所需类型 |
| 1 | **FORMERR** | 请求报文格式错误 |
| 2 | **SERVFAIL** | 服务器处理失败 |
| 3 | **NXDOMAIN** | 查询名称不存在 |
| 4 | **NOTIMP** | 不支持该操作 |
| 5 | **REFUSED** | 服务器拒绝查询 |

### NOERROR 但没有 Answer

这通常表示 **NODATA**：

```text
域名存在
但没有请求类型对应的记录
```

例如名称只有 A 记录，查询 MX 时可能返回 NOERROR 且 Answer 为空。

### SERVFAIL 常见原因

- 上游权威服务器不可达
- DNSSEC 验证失败
- 权威服务器配置错误
- 委派不一致
- 解析超时
- 循环依赖

### NXDOMAIN 常见原因

- 域名拼写错误
- 记录尚未创建
- 查询了错误的搜索域
- 域名已经过期或委派被删除
- 负缓存仍未过期

---

## 十六、DNS 故障排查

### 1. 排查流程

```text
1. 检查网络和默认路由
2. 检查当前使用的 DNS 服务器
3. 查询本机缓存和 hosts 文件
4. 使用指定递归 DNS 对比结果
5. 直接查询权威服务器
6. 检查 NS 委派和 Glue Record
7. 检查目标记录、TTL 和 SOA Serial
8. 检查 UDP/TCP 53、防火墙和 MTU
9. 检查 DNSSEC 信任链
10. 对比不同地区和不同解析器的结果
```

### 2. 判断是网络问题还是 DNS 问题

```bash
# 测试直接访问 IP
ping 1.1.1.1

# 测试域名解析
resolvectl query www.example.com
```

```text
IP 可访问，域名不能解析 → 优先检查 DNS
IP 也不可访问             → 优先检查网络、路由、防火墙
```

### 3. 对比不同解析器

```bash
dig @本地DNS www.example.com
dig @1.1.1.1 www.example.com
dig @8.8.8.8 www.example.com
```

如果只有某个解析器返回旧记录，通常是缓存、转发链或策略差异。

### 4. 直接查询权威服务器

```bash
# 找权威服务器
dig example.com NS +short

# 直接查询其中一台
dig @ns1.example.com www.example.com A +norecurse
```

这可以区分：

- 权威数据本身错误
- 递归解析器缓存旧数据
- 委派路径错误

### 5. 检查完整委派链

```bash
dig +trace www.example.com
```

重点观察：

- 根是否正确返回 TLD
- TLD 是否返回正确 NS
- Glue 地址是否正确
- 各权威服务器回答是否一致

### 6. 检查 DNSSEC

```bash
dig +dnssec example.com A
delv example.com A
```

重点检查：

- 是否存在 RRSIG
- 递归响应是否带 AD 标志
- DS 与 DNSKEY 是否匹配
- 签名是否过期
- 系统时间是否准确

### 7. 常见故障对照

| 现象 | 可能原因 | 排查重点 |
| ---- | -------- | -------- |
| 所有域名都失败 | DNS 地址错误、53 端口受阻 | resolv.conf、路由、防火墙 |
| 只有一个域名失败 | 权威记录或委派错误 | NS、SOA、权威查询 |
| 返回旧 IP | TTL 未过期、多级缓存 | dig 指定服务器、TTL |
| UDP 失败、TCP 成功 | 分片、MTU、防火墙 | EDNS、TCP 53、抓包 |
| SERVFAIL | DNSSEC、超时、配置错误 | delv、权威状态、日志 |
| NXDOMAIN | 拼写或名称不存在 | 查询名、搜索域、负缓存 |
| 内网正常，公网失败 | 公网区域漏配、委派错误 | 公共解析器、TLD 委派 |
| 公网正常，内网失败 | Split DNS、内部转发错误 | 企业 DNS、内部区域 |
| 部分地区失败 | 权威节点不同步、网络路由 | 各 NS、全球探测 |
| 邮件投递失败 | MX/PTR/SPF/DKIM/DMARC 错误 | 邮件 DNS 全链路 |

---

## 十七、常见 DNS 场景

### 1. 网站接入 CDN

```dns
www.example.com. 300 IN CNAME example.cdn-provider.net.
```

CDN 根据访问位置、节点健康和网络状况返回不同地址。

### 2. 简单 DNS 负载分配

```dns
www 60 IN A 192.0.2.10
www 60 IN A 192.0.2.11
www 60 IN A 192.0.2.12
```

限制：

- 客户端和递归 DNS 会缓存结果
- 不能保证均匀分配
- 单纯多 A 记录不一定自动剔除故障节点
- 需要结合健康检查和全局流量调度

### 3. 邮件域名配置

```dns
@               IN MX 10 mail.example.com.
mail            IN A     192.0.2.25
@               IN TXT   "v=spf1 ip4:192.0.2.25 -all"
default._domainkey IN TXT "v=DKIM1; k=rsa; p=..."
_dmarc          IN TXT   "v=DMARC1; p=quarantine"
```

邮件服务通常还需要为发送 IP 配置匹配的 PTR 记录。

### 4. 服务发现

```dns
_ldap._tcp.example.com. IN SRV 10 100 389 ldap1.example.com.
_ldap._tcp.example.com. IN SRV 20 100 389 ldap2.example.com.
```

客户端根据优先级和权重选择服务端点。

### 5. 内外网同名服务

使用 Split DNS：

```text
内网解析到私有 IP
公网解析到负载均衡器或公网 IP
```

应记录内外差异，避免运维人员因不同网络环境得到不同结果而误判。

---

## 十八、DNS 与相近协议

### 1. DNS 与 mDNS

| 维度 | DNS | mDNS |
| ---- | --- | ---- |
| 典型范围 | 全球或企业域名系统 | 本地链路 |
| 服务器 | 需要 DNS 服务器 | 无中心服务器 |
| 端口 | 53 | UDP 5353 |
| 地址 | 单播/Anycast | IPv4/IPv6 多播 |
| 常见后缀 | `.com`、`.cn` 等 | `.local` |
| 场景 | 网站、邮件、企业服务 | 打印机、AirPlay、局域网发现 |

### 2. DNS 与 LLMNR

- LLMNR 用于本地链路名称解析
- 使用 UDP/TCP 5355
- Windows 环境较常见
- 容易被本地网络中的伪造响应滥用
- 企业环境通常优先使用正规 DNS，并根据需要禁用 LLMNR

### 3. DNS 与 hosts 文件

| 项目 | DNS | hosts |
| ---- | --- | ----- |
| 管理方式 | 集中、分布式 | 每台主机本地维护 |
| 动态更新 | 支持 | 手动 |
| 规模 | 全球 | 少量固定映射 |
| 适用 | 正式解析 | 临时测试、引导、覆盖 |

Linux/macOS hosts 文件：

```text
/etc/hosts
```

Windows hosts 文件：

```text
C:\Windows\System32\drivers\etc\hosts
```

---

## 十九、核心要点速记

- **DNS = 域名系统，最常见用途是域名 → IP**
- **DNS 是分布式、分层、可缓存的应用层系统**
- **层级：根 → TLD → 权威服务器**
- **客户端通常把递归查询交给递归解析器**
- **递归解析器通过迭代查询访问根、TLD 和权威服务器**
- **根服务器有 13 个逻辑标识，通过 Anycast 部署大量实例**
- **A = IPv4，AAAA = IPv6**
- **CNAME = 别名，目标必须是域名**
- **MX = 邮件服务器，数字越小优先级越高**
- **NS = 权威服务器，SOA = 区域基础信息**
- **PTR = IP 反向解析域名**
- **TXT 常用于验证、SPF、DKIM、DMARC**
- **SRV = 服务发现，包含优先级、权重、端口和目标**
- **TTL 控制缓存时间，不代表记录本身的有效期**
- **NXDOMAIN = 名称不存在**
- **NOERROR 无 Answer 可能是 NODATA**
- **SERVFAIL 常见于超时、配置错误或 DNSSEC 验证失败**
- **传统 DNS 主要使用 UDP 53，也必须支持 TCP 53**
- **AXFR / IXFR 通常使用 TCP 53**
- **EDNS(0) 扩展 UDP 报文能力**
- **DoT = TCP 853，DoH = HTTPS 443，DoQ = QUIC 853**
- **DNSSEC 验证来源和完整性，但不加密查询**
- **DoT / DoH / DoQ 加密传输，但不代替 DNSSEC**
- **Glue Record 解决域内权威服务器名称的循环依赖**
- **修改记录前先降低 TTL，并等待旧 TTL 过期**
- **`dig +trace` 查看完整委派链**
- **`dig @服务器 域名 类型` 对比不同 DNS 的结果**
- **直接查询权威服务器可区分权威数据与递归缓存问题**
- **公网递归服务不应无控制地开放，避免被用于 DNS 放大攻击**
