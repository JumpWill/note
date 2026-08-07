# netfilter

netfilter 是 Linux 内核里的**网络数据包处理框架**：filter / NAT / mangle / raw 五大 hook 点 + 多个子系统（iptables / nftables / conntrack / nf_tables / bpfilter）。iptables 只是用户态工具之一。

```text
用户态：
  iptables  /  ip6tables   /  arptables   /  ebtables
  nft       /  iptables-translate
  conntrack-tools
  ebpf / tc  /  ss  /  ip route
        │
        ▼  netlink / setsockopt
内核态：
  netfilter 框架
  ├── 5 hook points
  ├── conntrack（连接跟踪）
  ├── nf_tables（新一代）
  ├── nf_nat
  ├── nf_queue
  ├── x_tables（match / target 库）
  └── 内核模块化加载：iptable_filter / nf_tables / nf_conntrack …
```

## 1. 5 个 hook 点

```text
网卡进来
   │
   ▼  NF_INET_PRE_ROUTING
raw.PREROUTING → conntrack / NAT 决策
   │
   ├─ dest 是自己 ──► mangle.INPUT → filter.INPUT → 本地进程
   │
   └─ dest 是别人 ──► mangle.FORWARD → filter.FORWARD → mangle.POSTROUTING
                                                       │
                                                       ▼
                                                     网卡发出
```

| Hook | 时机 | 常用表 |
| --- | --- | --- |
| **NF_INET_PRE_ROUTING** | 路由决策前 | raw / mangle / nat |
| **NF_INET_LOCAL_IN** | 路由决策后，本机接收 | mangle / filter / security |
| **NF_INET_FORWARD** | 路由决策后，本机转发 | mangle / filter / security |
| **NF_INET_LOCAL_OUT** | 本机发出，路由决策前 | raw / mangle / nat / filter / security |
| **NF_INET_POST_ROUTING** | 路由决策后，发出网卡前 | mangle / nat |

## 2. 内核模块

```text
netfilter/
├── core.c          netfilter 核心
├── nf_conntrack.c  连接跟踪
├── nf_nat.c        NAT 主体
├── nf_log.c        日志子系统
├── x_tables.c      match/target 框架
│   ├── ip_tables.c
│   └── arp_tables.c
├── xt_LOG.c        LOG target
├── iptable_filter.ko  filter 表
├── iptable_nat.ko     nat 表
├── iptable_mangle.ko  mangle 表
├── iptable_raw.ko    raw 表
├── nf_tables.ko    nftables
├── nf_conntrack_*.ko
│   ├── nf_conntrack_tcp
│   ├── nf_conntrack_udp
│   ├── nf_conntrack_ftp
│   └── nf_conntrack_amanda
└── ip_set*.ko      ipset 集合
```

## 3. iptables（用户态工具）

详见 [iptables.md](iptables.md)。iptables 通过 netlink 与内核通信，写入 netfilter 规则。

```bash
modprobe iptable_filter
modprobe iptable_nat
lsmod | grep nf
```

## 4. nftables（继任者）

v3.13+ 内核引入，nft 命令行替换 iptables。

```bash
nft list ruleset
nft add table inet filter
nft add chain inet filter input { type filter hook input priority 0; policy drop; }
nft add rule inet filter input iif lo accept
nft add rule inet filter input tcp dport 22 accept
```

**优势**：

- 单语法规则全部表
- 原生 set / map
- 流水线（更易读写）
- 性能（lookup O(1)）

迁移：

```bash
iptables-translate -A INPUT -p tcp --dport 80 -j ACCEPT
# → add rule ip filter INPUT tcp dport 80 accept
```

## 5. Connection Tracking (nf_conntrack)

跟踪"包是否属于已建连接"是 NAT 和状态防火墙的基础。

### 5.1 表项

```bash
cat /proc/net/nf_conntrack
# ipv4 2 tcp 6 431999 ESTABLISHED src=192.168.1.10 dst=8.8.8.8 sport=55555 dport=443 packets=42 bytes=8234
```

每个 conntrack 项包含：

| 字段 | 含义 |
| --- | --- |
| protocol | tcp / udp / icmp |
| state | NEW / ESTABLISHED / RELATED / INVALID |
| src/dst | 地址 + 端口 |
| packets / bytes | 累计 |
| timeout | 剩余时间 |

### 5.2 状态

```
NEW → ESTABLISHED → TIME_WAIT → CLOSE
RELATED（FTP data 等）
INVALID
```

### 5.3 调优

```bash
sysctl net.netfilter.nf_conntrack_max=262144        # 最大条目
sysctl net.netfilter.nf_conntrack_buckets=65536      # hash 大小
sysctl net.netfilter.nf_conntrack_tcp_timeout_established=7200
sysctl net.netfilter.nf_conntrack_tcp_timeout_time_wait=30
sysctl net.netfilter.nf_conntrack_tcp_timeout_close_wait=15
```

`nf_conntrack_max = total memory / hash_size / bucket_count`

### 5.4 conntrack 工具

```bash
conntrack -L                  # 列条目
conntrack -E                  # 实时事件
conntrack -D -s 10.0.0.1      # 删某 IP 的条目
conntrack -L -n               # 不解析端口
```

`/proc/net/ip_conntrack` 软链。

### 5.5 LRU + 满

```bash
dmesg | grep nf_conntrack
# nf_conntrack: table full, dropping packet
```

调整：

- 扩大 max + bucket
- 缩短超时
- 用 nf_conntrack / nft set 做白名单

## 6. NAT (Network Address Translation)

### 6.1 三种 NAT

```text
SNAT：  改源地址 → POSTROUTING
DNAT：  改目的地址 → PREROUTING
MASQUERADE：动态 SNAT（外网接口 IP 不固定时）
REDIRECT：本机端口重定向（透明代理）
```

### 6.2 全锥 / 受限 / 端口受限 / 对称

```text
Full Cone NAT       全映射（少见）
Restricted Cone     仅固定外部 IP 才能回连
Port Restricted     需要回连的 src port 也匹配
Symmetric NAT       每会话绑一对映射（4G 移动网常见）
```

`/proc/sys/net/netfilter/nf_conntrack_*` 影响 NAT 类型。

### 6.3 NAT 性能

- conntrack 是热点
- 启用 offload：
  - `iptables -t nat -A POSTROUTING -m conntrack --ctstate NEW -j MASQUERADE --random`
  - `nf_conntrack_helper` 内核帮忙处理

## 7. 路由与 netfilter

```text
ip_forward = 1 → 内核能 FORWARD
FORWARD chain  →  filter.FORWARD
POSTROUTING   →  nat.POSTROUTING（SNAT）
```

NAT 和 routing 紧密耦合：

```bash
iptables -t nat -A POSTROUTING -s 192.168.1.0/24 -o eth0 -j MASQUERADE
```

## 8. hook 注册

```c
nf_register_net_hook(&init_net, &nfho);
```

hook 结构体：

```c
struct nf_hook_ops {
    .hook     = my_hook,      // 处理函数
    .hooknum  = NF_INET_PRE_ROUTING,
    .pf       = NFPROTO_IPV4,
    .priority = NF_IP_PRI_FIRST;
};
```

模块化：

```c
module_init(register_hook);
module_exit(unregister_hook);
```

## 9. 表 / chain / rule 注册

```c
struct xt_table *ipt_register_table(
    &iptable_filter, t->table
);
```

内核中：

```c
iptable_filter.ko  注册到 NF_INET_LOCAL_IN/OUT/FORWARD
iptable_nat.ko     注册到 PRE_ROUTING/LOCAL_OUT/POST_ROUTING
```

链式调用：

```c
NF_HOOK(hooknum, net, skb, indev, outdev, okfn);
```

## 10. 调试与排错

### 10.1 日志

```bash
iptables -A INPUT -j LOG --log-prefix 'ipt-'
dmesg -w | grep ipt
# 或
tail -f /var/log/kern.log
```

### 10.2 TRACE

```bash
iptables -t raw -A PREROUTING -p icmp -j TRACE
```

### 10.3 nftrace

```bash
modprobe nf_log_ipv4
iptables -A INPUT -j NFLOG --nflog-group 1
ulogd -v -i nfnetlink_log
```

### 10.4 conntrack

```bash
conntrack -E
cat /proc/net/nf_conntrack
```

### 10.5 调试工具

```bash
# tc / nft debug
nft -d netlink,mnl,expr,stmt add rule inet filter output ...

# perf + netfilter
perf trace -e 'netfilter:*'
```

## 11. ebpf / XDP（现代替代）

eBPF 在内核里运行程序，绕开 iptables 直接挂钩网卡：

- **XDP**（eXpress Data Path）：网卡级 hook
- **TC**：流量控制
- **netfilter hook**：逐步支持 eBPF（kernel 5.10+）

Cilium 用 eBPF 实现 Kubernetes CNI：

```bash
# 看网卡 XDP
ip link show dev eth0

# XDP 卸载 iptables
iptables -I FORWARD -j ACCEPT   # 绕开
cilium replace -t netkit
```

## 12. 内核 API / 头文件

```c
#include <linux/netfilter.h>
#include <linux/netfilter_ipv4.h>
#include <linux/netfilter/nf_conntrack.h>
#include <linux/netfilter/xt_mark.h>
```

```c
// 注册 hook
struct nf_hook_ops nfho = {
    .hook     = my_hook,
    .hooknum  = NF_INET_PRE_ROUTING,
    .pf       = NFPROTO_IPV4,
    .priority = NF_IP_PRI_FIRST,
};

int my_hook(void *priv, struct sk_buff *skb,
            const struct nf_hook_state *state) {
    return NF_ACCEPT;
}
```

## 13. 内核模块加载

```bash
# 加载核心
modprobe nf_conntrack
modprobe nf_conntrack_ipv4
modprobe nf_conntrack_ipv6

# 加载 iptables 后端
modprobe iptable_filter
modprobe iptable_nat
modprobe iptable_mangle

# 加载 helpers
modprobe nf_conntrack_tcp
modprobe nf_conntrack_udp
modprobe nf_conntrack_ftp

# 加载 ipset
modprobe ip_set
```

看模块依赖：

```bash
lsmod | grep nf
```

## 14. 与 iptables / nftables 的关系

| 角度 | iptables | nftables |
| --- | --- | --- |
| 实现 | xtables / iptables kernel ABI | nf_tables ABI |
| 数据结构 | 多个表分别独立 | 单 backend (nf_tables) |
| 匹配 | `ipt_*` / `xt_*` modules | nft set / map / objref |
| 语法 | 4 表 / 5 链 | 任意 family + chain |
| 性能 | 老 | O(1) 查找 |
| 兼容性 | 老工具 | `iptables-nft` 兼容层 |
| 未来 | nft 替换 | 默认 |

迁移工具：

```bash
iptables-nft-save / iptables-nft-restore
iptables-translate
```

## 15. netfilter 编程实例

### 15.1 注册 NAT helper

```c
#include <linux/netfilter.h>
#include <net/netfilter/nf_conntrack_helper.h>

nf_conntrack_helper_register(&nf_conntrack_helper);
```

### 15.2 自定义 match

```c
struct xt_match my_match = {
    .name = "myrange",
    .family = NFPROTO_IPV4,
    .match = my_match_check,
    .matchsize = sizeof(struct my_match_info),
};
xt_register_match(&my_match);
```

### 15.3 自定义 target

```c
struct xt_target my_target = {
    .name = "mylog",
    .family = NFPROTO_IPV4,
    .target = my_target,
    .targetsize = 0,
};
xt_register_target(&my_target);
```

## 16. 与 TC / nftables / Cilium 的协同

```text
                         ingress
网卡 ─────► XDP ────► TC ingress ────► netfilter PREROUTING ──►
                                                  │
                                                  ▼
                                            IP routing
                                                  │
                                                  ▼
                                       ┌─────────┴────────┐
                                       ▼                  ▼
                                  INPUT            FORWARD
                                       │                  │
                                       ▼                  ▼
                                  本机进程           POSTROUTING
                                                          │
                                                          ▼
                                       TC egress ◄──── netfilter POSTROUTING
                                              │
                                              ▼
                                            网卡发出
```

## 17. /proc / /sys 接口

```bash
# 内核状态
/proc/net/ip_conntrack          # 老接口
/proc/net/nf_conntrack         # 新接口
/proc/net/ip_conntrack_expect

# sysctl
/sys/module/nf_conntrack/parameters/hashsize
/sys/module/ip_conntrack/parameters/hashsize

# conntrack 限额
/proc/sys/net/netfilter/nf_conntrack_max
/proc/sys/net/netfilter/nf_conntrack_tcp_loose
/proc/sys/net/netfilter/nf_conntrack_tcp_be_liberal
/proc/sys/net/netfilter/nf_conntrack_tcp_max_retrans

# helper 状态
/proc/sys/net/netfilter/nf_conntrack_helper
```

## 18. 性能调优

### 18.1 关闭不用的

```bash
modprobe -r nf_conntrack_ftp
modprobe -r nf_conntrack_h323
```

### 18.2 nft 代替 iptables

```bash
nftables 比 iptables 性能高 2-5 倍
```

### 18.3 表 / 链优化

- 长规则放前（fail-fast）
- ipset / nft set 替代大量 IP 单条规则
- 减少 match 组合

### 18.4 流量卸载

```bash
ethtool -K eth0 rx off tx off tso off gso off   # 关闭 offload
```

offload 开启时包可能"绕过" netfilter：

```bash
sysctl net.ipv4.conf.all.route_localnet=0
```

## 19. 经典案例

### 19.1 配置路由器

```bash
sysctl -w net.ipv4.ip_forward=1
iptables -t nat -A POSTROUTING -s 192.168.1.0/24 -o eth0 -j MASQUERADE
iptables -A FORWARD -i eth1 -o eth0 -j ACCEPT
iptables -A FORWARD -m state --state ESTABLISHED,RELATED -j ACCEPT
```

### 19.2 透明代理

```bash
iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-ports 8080
```

### 19.3 端口映射

```bash
iptables -t nat -A PREROUTING -d 1.2.3.4 -p tcp --dport 80 \
  -j DNAT --to-destination 192.168.1.10:80
iptables -t nat -A POSTROUTING -d 192.168.1.10 -j SNAT --to-source 1.2.3.4
```

### 19.4 防扫描

```bash
iptables -A INPUT -i eth0 -m recent --name scan --seconds 60 -j DROP
iptables -A INPUT -i eth0 -p tcp --tcp-flags ALL NONE -j DROP
```

## 20. 一句话总结

```text
netfilter = 内核网络包处理框架
5 hooks: PREROUTING / INPUT / FORWARD / OUTPUT / POSTROUTING
4 张 iptables 表: raw / mangle / nat / filter
        + security / conntrack / nf_tables / helpers
未来：nftables / eBPF / XDP
工具：iptables（老）/ nft（新）/ conntrack
调试：LOG / TRACE / ulogd / nftrace / bcc
```