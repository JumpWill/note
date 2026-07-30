# Linux 网络管理 (Linux Network Management)

## 一、网络基础

### 网络接口类型

- **物理接口**:eth0, enp0s3, ens33
- **虚拟接口**:lo, veth, br-, vlan, bond
- **隧道接口**:tun, tap, gre, ipip

### 接口命名

**传统**:eth0, eth1

**现代 (systemd, Predictable Interface Names)**:
- `en` + 适配器名: enp0s3
- `wl` + 无线: wlp3s0
- `ww` + WWAN: wwp0s20u7
- 板载:eno1
- USB: enx<MAC>

```bash
ip link show               # 看所有接口
ip -br link                # 简版
```

### 接口状态

```text
UP          接口启用
DOWN        接口禁用
LOWER_UP    网线插着
NO-CARRIER  无物理连接
RUNNING     在工作
```

---

## 二、ip 命令 (现代网络工具)

### 1. ip link (接口管理)

```bash
# 查看
ip link                   # 全部
ip link show eth0          # 特定
ip -s link show eth0       # 含统计

# 启用/禁用
ip link set eth0 up
ip link set eth0 down

# 改 MTU
ip link set eth0 mtu 9000         # Jumbo Frame

# 改 MAC (小心)
ip link set eth0 address 00:11:22:33:44:55

# 改 promisc 模式
ip link set eth0 promisc on

# 改名字
ip link set eth0 name eth0_new
```

### 2. ip addr (IP 地址)

```bash
# 查看
ip addr                    # 全部
ip addr show               # 同上
ip addr show dev eth0
ip -4 addr                  # 只 IPv4
ip -6 addr                  # 只 IPv6
ip -br addr                 # 简版

# 加 IP
ip addr add 192.168.1.100/24 dev eth0
ip addr add 192.168.1.100/24 dev eth0 brd +    # 自动 broadcast

# 删 IP
ip addr del 192.168.1.100/24 dev eth0

# 清空所有 IP
ip addr flush dev eth0
```

### 3. ip route (路由)

```bash
# 查看
ip route                   # 全部
ip route show              # 同上
ip route show default      # 默认路由
ip route get 8.8.8.8       # 看 8.8.8.8 走哪
ip route list table all    # 全部表

# 加路由
ip route add 10.0.0.0/8 via 192.168.1.1
ip route add default via 192.168.1.1
ip route add 192.168.1.0/24 dev eth0 src 192.168.1.100
ip route add 10.0.0.0/8 via 192.168.1.1 metric 100

# 删路由
ip route del 10.0.0.0/8
ip route del default
ip route flush cache        # 清路由缓存
```

### 4. ip neigh (ARP 表)

```bash
ip neigh                   # ARP 表
ip neigh show              # 同上
ip neigh show dev eth0

# 加静态
ip neigh add 192.168.1.1 lladdr 00:11:22:33:44:55 dev eth0

# 删
ip neigh del 192.168.1.1 dev eth0
```

### 5. ip rule (策略路由)

```bash
ip rule list                # 看策略
ip rule add from 192.168.1.0/24 table 100
ip rule add to 8.8.8.8 table 200
```

### 6. ip route 高级

```bash
# 多路径路由 ECMP
ip route add default nexthop via 192.168.1.1 dev eth0 weight 1 \
                          nexthop via 192.168.2.1 dev eth1 weight 1

# 黑洞路由
ip route add blackhole 10.0.0.0/8
ip route add unreachable 192.168.100.0/24

# 路由表
ip route add 10.0.0.0/8 via 192.168.1.1 table 100
ip route show table 100
echo "100 mytable" >> /etc/iproute2/rt_tables
```

---

## 三、传统命令 (ifconfig, route, netstat)

虽然已被 ip 命令取代,但仍常用。

### 1. ifconfig

```bash
ifconfig                   # 全部
ifconfig eth0              # 特定
ifconfig eth0 192.168.1.100/24
ifconfig eth0 up
ifconfig eth0 down
ifconfig eth0 mtu 9000
ifconfig eth0 promisc
```

### 2. route

```bash
route                      # 全部
route -n                   # 数字
route add default gw 192.168.1.1
route add -net 10.0.0.0/8 gw 192.168.1.1
route del default
```

### 3. netstat

```bash
netstat -a                 # 全部
netstat -t                 # TCP
netstat -u                 # UDP
netstat -l                 # 监听
netstat -p                 # 进程
netstat -n                 # 数字
netstat -r                 # 路由
netstat -s                 # 统计
netstat -tan               # 组合
netstat -lnp | grep 80      # 监听 80 端口的进程
```

---

## 四、网络连接 (ss)

### 1. ss 命令 (现代 netstat)

```bash
ss                         # 全部
ss -t                      # TCP
ss -u                      # UDP
ss -l                      # 监听
ss -a                      # 全部 (监听 + 非监听)
ss -p                      # 进程
ss -n                      # 数字
ss -e                      # 扩展
ss -m                      # 内存
ss -tan                    # TCP 数字

# 组合 (常用)
ss -tulnp                  # TCP+UDP 监听+进程+数字
ss -tan state established  # 已建立连接
ss -tan state time-wait     # TIME_WAIT
ss -tan state listening     # 监听
ss -tan state syn-recv      # SYN_RCVD

# 过滤
ss -tan dst 192.168.1.1
ss -tan src 192.168.1.0/24
ss -tan 'sport = :80'
ss -tan 'dport = :443'
ss -tan 'sport = :22-80'
ss -tin dst 1.2.3.4         # 含详细信息
ss -o state established     # 含 timer

# 统计
ss -s                      # 汇总
ss -i                      # TCP 内部信息

# Unix Domain Socket
ss -x                      # 列出 UDS
ss -xln                    # 监听
ss -xlnp                   # 监听 + 进程

# 内存
ss -m                      # 内存使用
```

### 2. ss vs netstat

| 维度     | ss              | netstat       |
|----------|-----------------|---------------|
| 速度     | 快 (用 netlink) | 慢 (读 /proc) |
| 信息     | 详细            | 较少          |
| 兼容性   | 新工具          | 传统          |
| 推荐     | ✅ 现代首选     | 兼容旧系统    |

---

## 五、DNS 配置

### 1. /etc/resolv.conf

```bash
# 临时修改
cat /etc/resolv.conf
nameserver 8.8.8.8
nameserver 114.114.114.114
search example.com
```

**注意**:
- 直接修改可能被 NetworkManager/systemd-resolved 覆盖
- 永久修改需禁用这些服务

### 2. systemd-resolved

```bash
# 看状态
resolvectl status

# 临时改
resolvectl dns eth0 8.8.8.8

# /etc/systemd/resolved.conf
[Resolve]
DNS=8.8.8.8 1.1.1.1
FallbackDNS=114.114.114.114
```

### 3. 本地 hosts

```bash
cat /etc/hosts
127.0.0.1   localhost
::1         localhost
192.168.1.100 myserver.local myserver
```

### 4. DNS 工具

```bash
dig example.com
dig @8.8.8.8 example.com
dig +short example.com     # 简版
dig +trace example.com     # 跟踪
nslookup example.com
host example.com
```

### 5. DNS 缓存

- **本地缓存**:`nscd`, `systemd-resolved`, `dnsmasq`
- **应用层**:浏览器、Java 缓存 DNS
- **TTL 控制**:`/etc/nsswitch.conf`

---

## 六、网卡配置

### 1. 配置工具

| 工具                 | 适用                                 |
|----------------------|--------------------------------------|
| **ifconfig**         | 传统,临时                            |
| **ip**               | 临时                                 |
| **NetworkManager**   | 桌面、便携                           |
| **systemd-networkd** | 服务器、容器                         |
| **netplan**          | Ubuntu 18+                           |
| **配置文件**         | RHEL /etc/sysconfig/network-scripts/ |

### 2. RHEL / CentOS 配置

```bash
# /etc/sysconfig/network-scripts/ifcfg-eth0
TYPE=Ethernet
BOOTPROTO=dhcp          # 或 static
NAME=eth0
DEVICE=eth0
ONBOOT=yes
IPADDR=192.168.1.100
PREFIX=24                # 或 NETMASK=255.255.255.0
GATEWAY=192.168.1.1
DNS1=8.8.8.8
DNS2=114.114.114.114

# 重启网络
systemctl restart NetworkManager
nmcli connection reload
```

### 3. Ubuntu (netplan)

```yaml
# /etc/netplan/01-netcfg.yaml
network:
  version: 2
  renderer: networkd     # 或 NetworkManager
  ethernets:
    eth0:
      dhcp4: no
      addresses:
        - 192.168.1.100/24
      gateway4: 192.168.1.1
      nameservers:
        addresses: [8.8.8.8, 1.1.1.1]
```

```bash
netplan apply
netplan try    # 测试,失败回滚
```

### 4. nmcli (NetworkManager 命令行)

```bash
# 状态
nmcli general status
nmcli connection show
nmcli device status

# 启停
nmcli connection up eth0
nmcli connection down eth0

# 配 IP
nmcli connection modify eth0 ipv4.addresses 192.168.1.100/24
nmcli connection modify eth0 ipv4.gateway 192.168.1.1
nmcli connection modify eth0 ipv4.dns "8.8.8.8 1.1.1.1"
nmcli connection modify eth0 ipv4.method manual
nmcli connection up eth0

# WiFi
nmcli device wifi list
nmcli device wifi connect SSID password PASSWORD

# 改主机名
nmcli general hostname newname
```

---

## 七、防火墙

### 1. iptables (传统)

**4 个表**:
- **filter**:过滤(默认)
- **nat**:地址转换
- **mangle**:修改包
- **raw**:跟踪

**5 个链**:
- **PREROUTING**:进入路由前
- **INPUT**:进入本机
- **FORWARD**:转发
- **OUTPUT**:本机发出
- **POSTROUTING**:发出后

```bash
# 查规则
iptables -L -n -v
iptables -t nat -L -n

# 默认策略
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT ACCEPT

# 允许本地回环
iptables -A INPUT -i lo -j ACCEPT

# 允许已建立的连接
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# 允许 SSH
iptables -A INPUT -p tcp --dport 22 -j ACCEPT

# 允许 HTTP
iptables -A INPUT -p tcp --dport 80 -j ACCEPT

# 允许特定 IP
iptables -A INPUT -s 192.168.1.0/24 -j ACCEPT

# 拒绝其他
iptables -A INPUT -j DROP

# 端口转发
iptables -t nat -A PREROUTING -d 1.2.3.4 -p tcp --dport 80 -j DNAT --to 192.168.1.10:80
iptables -t nat -A POSTROUTING -s 192.168.1.0/24 -j SNAT --to 1.2.3.4

# 保存
service iptables save
iptables-save > /etc/iptables.rules
```

### 2. nftables (现代,替代 iptables)

```bash
# nft list ruleset
# nft add table inet filter
# nft add chain inet filter input { type filter hook input priority 0 \; policy drop \; }
# nft add rule inet filter input iif lo accept
# nft add rule inet filter input tcp dport 22 accept
```

### 3. ufw (Ubuntu 简化)

```bash
ufw status
ufw enable
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow from 192.168.1.0/24
ufw deny 23
ufw delete allow 80
```

### 4. firewalld (RHEL)

```bash
# 看
firewall-cmd --list-all
firewall-cmd --get-zones
firewall-cmd --get-services

# 加规则
firewall-cmd --add-port=80/tcp
firewall-cmd --add-service=http
firewall-cmd --add-rich-rule='rule family=ipv4 source address=192.168.1.0/24 accept'
firewall-cmd --zone=public --add-port=80/tcp --permanent
firewall-cmd --reload

# 删
firewall-cmd --remove-port=80/tcp
firewall-cmd --remove-service=http

# 启用/禁用
firewall-cmd --enable
firewall-cmd --disable
```

### 5. nftables 语法 (现代推荐)

```bash
# 创建表
nft add table inet filter

# 创建链
nft add chain inet filter input { type filter hook input priority 0 \; policy drop \; }

# 加规则
nft add rule inet filter input iif lo accept
nft add rule inet filter input tcp dport 22 accept
nft add rule inet filter input ip saddr 192.168.1.0/24 accept

# NAT
nft add table ip nat
nft add chain ip nat prerouting { type nat hook prerouting priority -100 \; }
nft add rule ip nat prerouting tcp dport 80 dnat to 192.168.1.10:80

# 列出
nft list ruleset
```

### 6. 防火墙选型

| 工具          | 特点               |
|---------------|--------------------|
| **iptables**  | 传统,文档全        |
| **nftables**  | iptables 继任,推荐 |
| **firewalld** | RHEL 区域管理      |
| **ufw**       | Ubuntu 简化        |

---

## 八、网络调试与诊断

### 1. 连通性测试

```bash
ping host                          # ICMP
ping -c 4 host                     # 4 次
ping -i 0.2 host                   # 0.2 秒间隔
ping -s 1000 host                  # 大包
ping -M do host                    # 不分片
ping -W 1 host                     # 1 秒超时
ping6 host                         # IPv6

# 端口测试
nc -zv host 80                     # TCP 端口
nc -zvw3 host 1-1000               # 范围
telnet host 80                     # 旧
curl telnet://host:80              # 现代
```

### 2. 路径诊断

```bash
traceroute host
traceroute -T host                 # 用 TCP
traceroute -I host                 # 用 ICMP
tracepath host                     # 简单
mtr host                           # 实时
mtr -n host                        # 不解析
```

### 3. 抓包分析

```bash
# tcpdump
tcpdump -i eth0                    # 抓包
tcpdump -i eth0 -w file.pcap       # 保存
tcpdump -i eth0 -c 100             # 100 包
tcpdump -i eth0 port 80            # 端口
tcpdump -i eth0 host 1.2.3.4       # 主机
tcpdump -i eth0 'tcp and port 80'  # 表达式
tcpdump -i eth0 -A                 # ASCII
tcpdump -i eth0 -X                 # 16 进制
tcpdump -i eth0 -nN                # 数字,不解析
tcpdump -i eth0 -nn -s 0           # 完整包
tcpdump -r file.pcap               # 读
tcpdump -i eth0 -w file.pcap 'tcp[tcpflags] & (tcp-syn) != 0'  # SYN 包

# wireshark / tshark
tshark -i eth0
tshark -i eth0 -w file.pcap
wireshark file.pcap
```

### 4. DNS 诊断

```bash
dig example.com
dig @8.8.8.8 example.com
dig +trace example.com
dig -x 8.8.8.8                  # 反向
dig example.com MX
dig example.com NS
dig example.com ANY
host example.com
nslookup example.com
```

### 5. 路由诊断

```bash
ip route get 8.8.8.8
ip route show table all
traceroute 8.8.8.8
mtr 8.8.8.8
```

### 6. 网络质量测试

```bash
# 带宽
iperf3 -s                          # 服务端
iperf3 -c server                   # 客户端
iperf3 -c server -P 10 -t 30      # 10 线程 30 秒
iperf3 -c server -u -b 1G         # UDP 1G
iperf3 -c server -R                # 反向

# HTTP
curl -o /dev/null -w "%{speed_download}\n" URL
ab -n 1000 -c 100 URL
wrk -c 1000 -d 30s URL

# 延迟 / 丢包
ping -c 100 host
mtr -n host
```

---

## 九、网络性能调优

### 1. 关键调优参数

```bash
# 增大 TCP 缓冲区
sysctl -w net.ipv4.tcp_rmem="4096 87380 6291456"
sysctl -w net.ipv4.tcp_wmem="4096 65536 6291456"
sysctl -w net.core.rmem_max=16777216
sysctl -w net.core.wmem_max=16777216

# 增大连接队列
sysctl -w net.core.somaxconn=65535
sysctl -w net.ipv4.tcp_max_syn_backlog=65535
sysctl -w net.core.netdev_max_backlog=65535

# 端口范围
sysctl -w net.ipv4.ip_local_port_range="1024 65535"

# TIME_WAIT
sysctl -w net.ipv4.tcp_tw_reuse=1
sysctl -w net.ipv4.tcp_tw_recycle=0   # 慎用,已废弃
sysctl -w net.ipv4.tcp_fin_timeout=10

# 拥塞控制
sysctl -w net.ipv4.tcp_congestion_control=bbr
sysctl -w net.core.default_qdisc=fq

# TCP keepalive
sysctl -w net.ipv4.tcp_keepalive_time=300
sysctl -w net.ipv4.tcp_keepalive_intvl=30
sysctl -w net.ipv4.tcp_keepalive_probes=3

# 路由
sysctl -w net.ipv4.conf.all.rp_filter=1
sysctl -w net.ipv4.icmp_echo_ignore_broadcasts=1
```

### 2. 网卡调优

```bash
# 看网卡能力
ethtool eth0
ethtool -i eth0                    # 驱动信息
ethtool -k eth0                    # 特性
ethtool -g eth0                    # 环形缓冲区
ethtool -c eth0                    # coalesce

# 改 Ring Buffer
ethtool -G eth0 rx 4096 tx 4096

# 中断合并
ethtool -C eth0 rx-usecs 50
ethtool -C eth0 tx-usecs 50

# 关闭不用的特性
ethtool -K eth0 tso off gso off     # 调试时
ethtool -K eth0 rxvlan off txvlan off

# 多队列 (RSS)
ethtool -l eth0
ethtool -L eth0 combined 8

# 速度 / 双工
ethtool -s eth0 speed 1000 duplex full autoneg on
```

### 3. 中断亲和 (SMP IRQ Affinity)

```bash
# 看
cat /proc/irq/24/smp_affinity

# 把 IRQ 绑到特定 CPU
echo 0-3 > /proc/irq/24/smp_affinity
echo 0-3 > /proc/irq/24/smp_affinity_list

# 用脚本
for irq in /proc/irq/*; do
    if grep -q eth0 $irq/../local* 2>/dev/null; then
        echo 0 > $irq/smp_affinity
    fi
done

# 自动中断平衡守护进程
systemctl status irqbalance
```

### 4. RSS (Receive Side Scaling)

```bash
# 看队列
ethtool -l eth0
# 设多队列
ethtool -L eth0 combined 8

# 队列的 IRQ 自动平衡
echo 8 > /sys/class/net/eth0/real_num_rx_queues
```

### 5. TCP 优化 (更多)

```bash
# 缓冲区
sysctl -w net.ipv4.tcp_rmem="4096 87380 6291456"
sysctl -w net.ipv4.tcp_wmem="4096 65536 6291456"

# 拥塞
# BBR (Google,2016): 适合现代网络
sysctl -w net.ipv4.tcp_congestion_control=bbr
sysctl -w net.core.default_qdisc=fq

# cubic (Linux 默认)
sysctl -w net.ipv4.tcp_congestion_control=cubic

# SACK
sysctl -w net.ipv4.tcp_sack=1
sysctl -w net.ipv4.tcp_dsack=1

# Window Scale
sysctl -w net.ipv4.tcp_window_scaling=1

# Timestamps
sysctl -w net.ipv4.tcp_timestamps=1
```

### 6. 高频场景调优

#### (1) 高并发 Web 服务器

```bash
# 增大 fd
ulimit -n 1000000

# 短连接 (TIME_WAIT 多)
sysctl -w net.ipv4.tcp_tw_reuse=1
sysctl -w net.ipv4.tcp_tw_recycle=0

# 长连接
sysctl -w net.ipv4.tcp_keepalive_time=600
```

#### (2) 大文件传输

```bash
# 增大窗口
sysctl -w net.ipv4.tcp_window_scaling=1
sysctl -w net.ipv4.tcp_rmem="4096 87380 67108864"
```

#### (3) 低延迟

```bash
# BBR
sysctl -w net.ipv4.tcp_congestion_control=bbr
# 减少 Nagle
setsockopt TCP_NODELAY
```

#### (4) 高吞吐

```bash
# 缓冲区
sysctl -w net.core.rmem_max=134217728
sysctl -w net.core.wmem_max=134217728
# 多网卡聚合
# ip link add bond0 ...
```

---

## 十、网络高级特性

### 1. 桥接 (Bridge)

```bash
# 创桥
ip link add br0 type bridge
ip link set br0 up
ip link set eth0 master br0
ip link set eth1 master br0

# 加 IP
ip addr add 192.168.1.1/24 dev br0

# 看
brctl show                  # 旧
bridge link show            # 新
```

### 2. VLAN

```bash
# 创 VLAN 接口
ip link add link eth0 name eth0.100 type vlan id 100
ip link set eth0.100 up
ip addr add 192.168.100.1/24 dev eth0.100

# 看
ip -d link show eth0.100
```

### 3. 绑定 (Bonding / Teaming)

```bash
# 创 bond
ip link add bond0 type bond mode 802.3ad
ip link set eth0 master bond0
ip link set eth1 master bond0
ip link set bond0 up

# mode: balance-rr / active-backup / 802.3ad (LACP) / balance-xor 等
```

### 4. 网桥 + VLAN + 绑定 (生产)

```bash
# 复杂配置
ip link add bond0 type bond mode 802.3ad lacp_rate fast
ip link set eth0 master bond0
ip link set eth1 master bond0

ip link add br0 type bridge
ip link set bond0 master br0

ip link add link br0 name br0.100 type vlan id 100
ip addr add 10.100.0.1/24 dev br0.100
ip link set br0.100 up
```

### 5. 命名空间 (Network Namespace)

```bash
# 创命名空间
ip netns add myns

# 在命名空间内执行命令
ip netns exec myns ip addr
ip netns exec myns bash

# 创 veth pair
ip link add veth0 type veth peer name veth1
ip link set veth1 netns myns

# 配置
ip addr add 10.0.0.1/24 dev veth0
ip link set veth0 up
ip netns exec myns ip addr add 10.0.0.2/24 dev veth1
ip netns exec myns ip link set veth1 up
ip netns exec myns ip link set lo up

# 测试
ip netns exec myns ping 10.0.0.1
```

### 6. 虚拟专线 (VXLAN)

```bash
# 创 VXLAN
ip link add vxlan100 type vxlan id 100 dev eth0 remote 192.168.1.1 dstport 4789
ip addr add 10.100.0.1/24 dev vxlan100
ip link set vxlan100 up
```

### 7. 路由策略 (Policy Routing)

```bash
# 来源 IP 不同,走不同路由
ip rule add from 192.168.1.0/24 table 100
ip route add default via 192.168.1.1 table 100

ip rule add from 10.0.0.0/8 table 200
ip route add default via 10.0.0.1 table 200
```

### 8. GRE / IPIP 隧道

```bash
# GRE
ip tunnel add gre1 mode gre local 1.1.1.1 remote 2.2.2.2 ttl 255
ip link set gre1 up
ip addr add 10.0.0.1/30 dev gre1
```

---

## 十一、网络配置文件

### 1. /etc/hosts

```text
127.0.0.1   localhost
::1         localhost
192.168.1.100 server1
192.168.1.101 server2
```

### 2. /etc/resolv.conf

```text
nameserver 8.8.8.8
nameserver 114.114.114.114
search example.com
options timeout:2 attempts:3
```

### 3. /etc/nsswitch.conf

```text
passwd:    files systemd
group:     files systemd
shadow:    files
hosts:     files dns
networks:  files
protocols:  files
services:   files
ethers:     files
rpc:        files
```

### 4. /etc/services

```text
ssh  22/tcp
http 80/tcp
https 443/tcp
mysql 3306/tcp
```

### 5. /etc/hostname

```bash
hostname
# /etc/hostname
myserver
```

### 6. /etc/hosts.allow / hosts.deny

```bash
# /etc/hosts.allow
sshd: 192.168.1.0/24
in.telnetd: ALL

# /etc/hosts.deny
ALL: ALL
```

---

## 十二、网络监控

### 1. 工具

```bash
# 接口
ip -s link show eth0
sar -n DEV 1
nicstat -d eth0

# TCP
ss -s
ss -tan
netstat -s
nstat

# 进程级
nethogs eth0
iftop -i eth0

# 抓包
tcpdump -i eth0
wireshark
```

### 2. 实时监控

```bash
# 综合
glances
nload
bmon
iptraf-ng

# 高级
iftop -i eth0
nethogs eth0
```

---

## 十三、网络常见问题与故障排查

### 1. 排查步骤

```text
1. 物理层:网线插好?网卡灯亮?
2. 链路层:ifconfig / ip link 状态?
3. 网络层:ip addr 有 IP?ip route 有默认路由?
4. 传输层:ping 通?TCP 端口开?
5. 应用层:服务启动?配置对?权限够?
```

### 2. 常见问题

| 问题              | 排查                          |
|-------------------|-------------------------------|
| 网不通            | ip addr / ip route / ping     |
| 端口不通          | ss -tlnp / 防火墙             |
| DNS 不通          | /etc/resolv.conf / dig        |
| 网卡慢            | ethtool / 网卡驱动            |
| 网卡丢包          | ifconfig errors/dropped       |
| 路由不对          | ip route / traceroute         |
| 带宽不达          | ethtool / iperf3              |
| TCP 连接不上      | TIME_WAIT / 防火墙            |
| 间歇性断          | 网线 / 交换机 / IP 冲突       |
| 网卡 name 错      | udevadm / systemd             |
| 容器网络          | CNI / bridge / cgroup         |

### 3. 抓包调试

```bash
# 端口不通
tcpdump -i any port 80

# TCP 连接失败
tcpdump -i eth0 host 1.2.3.4 -w cap.pcap
# 看 SYN/SYN-ACK/ACK 是否正常

# 丢包
tcpdump -i eth0 -c 1000 -w cap.pcap
wireshark cap.pcap
# Statistics -> Conversations 看重传

# 延迟
tshark -r cap.pcap -T fields -e frame.time_delta
```

---

## 十四、网络服务 (服务端)

### 1. DHCP

```bash
# 客户端
dhclient eth0
dhclient -r eth0           # 释放

# 服务端
dnsmasq                   # 轻量
isc-dhcp-server           # 完整
```

### 2. DNS

```bash
# 服务
dnsmasq                   # 轻量
unbound                   # 高效
bind (named)              # 完整
coredns                   # K8s

# 配置示例 (dnsmasq)
cat /etc/dnsmasq.conf
port=53
resolv-file=/etc/resolv.dnsmasq.conf
address=/test.local/192.168.1.100
```

### 3. NTP

```bash
# chrony
chronyd
chronyc tracking
chronyc sources

# systemd-timesyncd
systemctl status systemd-timesyncd
timedatectl

# ntpdate (老)
ntpdate ntp.aliyun.com
```

### 4. SNMP

```bash
# 服务
snmpd
# 配置
cat /etc/snmp/snmpd.conf
# 客户端
snmpwalk -v2c -c public localhost 1.3.6.1.2.1.1.1
```

### 5. HTTP

- **nginx**:反向代理、Web 服务器
- **apache**:传统 Web
- **caddy**:自动 HTTPS
- **HAProxy**:负载均衡
- **Envoy**:服务网格

### 6. 负载均衡

- **LVS**:四层,内核
- **HAProxy**:四/七层
- **nginx**:七层
- **Envoy**:七层
- **云 SLB**:云厂商

---

## 十五、内核参数调优总览

### 网络相关

```bash
# 通用
net.core.somaxconn = 65535
net.core.netdev_max_backlog = 65535
net.core.rmem_default = 262144
net.core.wmem_default = 262144
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.core.optmem_max = 65536

# IPv4
net.ipv4.tcp_rmem = 4096 87380 6291456
net.ipv4.tcp_wmem = 4096 65536 6291456
net.ipv4.tcp_max_syn_backlog = 65535
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_fin_timeout = 10
net.ipv4.ip_local_port_range = 1024 65535
net.ipv4.tcp_congestion_control = bbr
net.ipv4.tcp_sack = 1
net.ipv4.tcp_window_scaling = 1
net.ipv4.tcp_timestamps = 1
net.ipv4.tcp_no_metrics_save = 1
net.ipv4.tcp_fastopen = 3
net.ipv4.tcp_mtu_probing = 1

# 路由
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1
net.ipv4.ip_forward = 1
net.ipv4.conf.all.accept_source_route = 0
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.all.secure_redirects = 0
net.ipv4.icmp_echo_ignore_broadcasts = 1
net.ipv4.icmp_ignore_bogus_error_responses = 1
```

---

## 十六、网络工具速查

| 任务          | 命令                                                   |
|---------------|--------------------------------------------------------|
| 看 IP         | `ip addr`                                              |
| 改 IP         | `ip addr add 192.168.1.1/24 dev eth0`                  |
| 看路由        | `ip route`                                             |
| 加默认路由    | `ip route add default via 1.1.1.1`                     |
| 看连接        | `ss -tan`                                              |
| 看 socket     | `ss -x`                                                |
| 抓包          | `tcpdump -i eth0 port 80`                              |
| 测带宽        | `iperf3 -c server`                                     |
| 测延迟        | `mtr host`                                             |
| 测 DNS        | `dig @8.8.8.8 example.com`                             |
| 看接口流量    | `sar -n DEV 1`                                         |
| 看网卡统计    | `ip -s link show eth0`                                 |
| 防火墙状态    | `iptables -L` / `firewall-cmd --list-all`              |
| 路由跟踪      | `traceroute host`                                      |
| 端口扫描      | `nmap host`                                            |
| 网卡设置      | `ethtool eth0`                                         |
| 中断亲和      | `echo 0-3 > /proc/irq/24/smp_affinity`                 |
| 多队列        | `ethtool -L eth0 combined 8`                           |
| 桥接          | `ip link add br0 type bridge`                          |
| VLAN          | `ip link add link eth0 name eth0.100 type vlan id 100` |
| 绑定          | `ip link add bond0 type bond`                          |
| 命名空间      | `ip netns add myns`                                    |
| GRE 隧道      | `ip tunnel add gre1 mode gre ...`                      |
| 路由策略      | `ip rule add from 192.168.1.0/24 table 100`            |

---

## 十七、核心要点速记

- **ip 命令** = 现代网络配置
- **ss 命令** = 现代 socket 查看
- **netplan** = Ubuntu 18+ 网络配置
- **NetworkManager + nmcli** = 桌面推荐
- **systemd-networkd** = 服务器推荐
- **nftables** = 现代防火墙
- **ufw** = Ubuntu 简化防火墙
- **firewalld** = RHEL 区域管理
- **BBR** = 现代 TCP 拥塞控制
- **TCP_NODELAY** = 关 Nagle,低延迟
- **ulimit -n 1000000** = 大 fd
- **ip netns** = 网络命名空间
- **Bridge** = 虚拟交换机
- **VLAN** = 虚拟 LAN
- **Bond** = 多网卡聚合
- **VXLAN** = 跨主机虚拟网络
- **ip rule + ip route** = 策略路由
- **ethtool -L** = 多队列
- **RSS** = 网卡多队列负载均衡
- **IRQ affinity** = 中断绑核
- **tcpdump -i any** = 抓所有接口
- **mtr -n** = 实时路径
- **iperf3 -P N** = 多线程带宽
