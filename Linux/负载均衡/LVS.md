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

### 2. NAT 模式

```text
client ─► Director ─► RS
       (改 dst)     (回程经 Director)

client_ip ───► Director ───► client_ip
                              ↓ (改 src)
                            RS sees: client_ip from Director_ip
                              ↓
                            RS ─► Director (改 src) ─► client
```

```bash
# Director
ipvsadm -A -t 192.168.1.100:80 -s wrr
ipvsadm -a -t 192.168.1.100:80 -r 10.0.0.1:80 -m   # -m = MASQ
ipvsadm -a -t 192.168.1.100:80 -r 10.0.0.2:80 -m

# 开启转发
sysctl -w net.ipv4.ip_forward=1

# RS 上把 Director IP 设为默认网关
```

**特点**:RS 看请求包源 IP 是真实 client(可选 `-m` 替换 / 不替换)

### 3. DR 模式(Direct Routing,最常用)

```text
client ─► Director ─► RS
              │
              └───► RS 直接回 client(不经过 Director)

client_ip ───► Director ───► client_ip
                              ↓
                            RS 接收(Director MAC + Director IP)
                            RS 改 src MAC = RS, dst MAC = client
                            client 直接收到 RS 的包
```

**Director 流程**:

1. 收到 client 包(MAC = Director IP,VIP)
2. ip_vs 改 dst MAC = RS, dst IP 不变(VIP)
3. 包从 Director 发出,到达 RS

**RS 流程**:

1. 接收包(MAC = 自己)
2. 看到 dst IP = VIP,本机 lo 配置了 VIP,接受
3. RS 直接回包给 client(src IP = VIP)

```bash
# Director
ipvsadm -A -t 192.168.1.100:80 -s wrr
ipvsadm -a -t 192.168.1.100:80 -r 10.0.0.1:80 -g   # -g = DR
ipvsadm -a -t 192.168.1.100:80 -r 10.0.0.2:80 -g

# Director 上 VIP 配置在物理接口(eth0)
ip addr add 192.168.1.100/32 dev eth0

# RS 上配置
# 1. lo 配置 VIP(不响应 ARP)
ip addr add 192.168.1.100/32 dev lo
# 2. 抑制 ARP 响应
sysctl -w net.ipv4.conf.lo.arp_ignore=1
sysctl -w net.ipv4.conf.lo.arp_announce=2
sysctl -w net.ipv4.conf.all.arp_ignore=1
sysctl -w net.ipv4.conf.all.arp_announce=2
```

**特点**:Director 只处理入站,RS 直接回 client → Director 不成为瓶颈

### 4. Tunnel 模式(IPIP)

```text
client ─► Director ─► RS (跨网段,IPIP 隧道)
client ─► RS ─► client (RS 直接回)
```

```bash
# Director
ipvsadm -A -t 192.168.1.100:80 -s wrr
ipvsadm -a -t 192.168.1.100:80 -r 10.0.1.1:80 -i   # -i = TUN

# Director 需开启 IPIP
modprobe ipip

# RS 需开启 IPIP 接收 + 隧道配置
ip tunnel add tunl0 mode ipip remote <director_ip> local <rs_ip>
ip addr add 192.168.1.100/32 dev tunl0
```

**特点**:Director 与 RS 可跨网段(广域网),但 RS 需要公网 IP

### 5. FULLNAT 模式(阿里云)

```text
client ─► Director (改 src + dst) ─► RS
client 看到 src = Director
RS 看到 src = Director(非 client)
```

```bash
# 需要内核 patch(标准内核无 FULLNAT)
# 阿里云在 Linux 4.x 上有 ip_vs_fullnat 模块
ipvsadm -a -t 192.168.1.100:80 -r 10.0.0.1:80 -b   # -b = FULLNAT
```

**特点**:RS 任意网段,不需 VIP,SNAT 网段不需一致(但回程问题需额外处理)

### 6. 模式对比

```text
NAT:   Director 改 src/dst,回程经 Director(压力)
DR:    Director 改 dst MAC,回程不经 Director(高效,要求同网段)
TUN:   Director 包 IP 隧道,RS 解隧道,跨网段
FULLNAT: Director 双向 NAT,跨网段,RS 无限制
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
