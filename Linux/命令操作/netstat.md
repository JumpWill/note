# netstat

`netstat` 用于显示本机的网络连接、路由表、接口状态、协议统计等。源自 BSD，是"网络排错入门命令"，几乎每个发行版都内置（来自 `net-tools`）。注意：

- 现代 Linux 中不少发行版（RHEL 8+、openSUSE、Arch 主线等）开始不预装 `net-tools`，**`ss`（iproute2）已成为推荐替代**
- macOS / 部分 BSD 仍以 netstat 为主
- 与 `route` / `ifconfig` 一起被新工具取代，但 netstat 在排错命令组合中仍是必看

## 作用

```text
netstat [--options] [-A protocol] [filter]
```

主要解决：

- 查看 TCP / UDP 连接与监听端口
- 查看路由表
- 查看网络接口收发数据
- 查看协议统计（IP / ICMP / TCP / UDP 各协议计数）

## 常见参数

### 1. 显示选项

| 参数 | 含义 |
| ---- | ---- |
| `-a` / `--all` | 显示所有 socket（含监听 / 非监听） |
| `-l` / `--listening` | 只显示 LISTEN 状态（监听端口） |
| `-n` / `--numeric` | 数字显示（不解析服务名 / DNS） |
| `-t` / `--tcp` | 只看 TCP |
| `-u` / `--udp` | 只看 UDP |
| `-x` / `--unix` | Unix 域 socket |
| `-w` / `--raw` | RAW socket |
| `-W` / `--wide` | 不截断 |
| `-p` / `--program` | 显示进程 PID / 程序名（要 root 才能看到别人） |
| `-s` / `--statistics` | 协议统计 |
| `-r` / `--route` | 路由表 |
| `-i` / `--interfaces` | 网络接口表 |
| `-g` / `--groups` | 多播组成员 |
| `-e` / `--extend` | 扩展信息（如 uid / inode） |
| `-c` / `--continuous` | 每秒刷新，连续显示 |
| `-o` | 显示计时器 |
| `--timers` | 计时器（部分版本） |

### 2. 输出过滤

| 参数 | 含义 |
| ---- | ---- |
| `-A <inet\|inet6\|unix\|all>` | 指定地址族 |
| `tcp` / `udp` / `raw` `lisp` | 直接接协议关键字 |

过滤语法（`grep` 替代），并非 netstat 自带：

```text
netstat -an | grep LISTEN              # LISTEN 行
netstat -anp | grep :80                # 80 端口
```

## 常用组合

### 1. 最常用：所有监听端口 + 进程

```bash
sudo netstat -tlnp
```

- `-t`：TCP
- `-l`：监听
- `-n`：数字
- `-p`：进程

输出：

```text
Proto Recv-Q Send-Q Local Address     Foreign Address   State       PID/Program
tcp        0      0 127.0.0.1:3306    0.0.0.0:*         LISTEN      1234/mysqld
tcp        0      0 0.0.0.0:80        0.0.0.0:*         LISTEN      5678/nginx
tcp6       0      0 :::22             :::*              LISTEN      901/sshd
```

### 2. 所有连接（含 udp）

```bash
netstat -a
```

### 3. 只看 TCP / UDP / Unix socket

```bash
netstat -t
netstat -u
netstat -x
```

### 4. 数字显示（更快）

```bash
netstat -tunlp
```

`n` 强制数字端口，避免解析服务名（极大加速）。

### 5. 路由表

```bash
netstat -rn
```

效果类似 `route -n`，显示：

```text
Kernel IP routing table
Destination   Gateway      Genmask         Flags MSS Window  irtt Iface
0.0.0.0       192.168.1.1  0.0.0.0         UG    0 0       0    eth0
192.168.1.0   0.0.0.0      255.255.255.0   U     0 0       0    eth0
10.0.0.0      192.168.1.1  255.0.0.0       UG    0 0       0    eth0
```

Flags 常见：

| 标志 | 含义 |
| ---- | ---- |
| U | 路由已启用 |
| G | 走网关（不是直接相连） |
| H | 主机路由（非网络） |
| D | 由 ICMP 重定向动态生成 |
| M | 由 ICMP 重定向动态修改 |

### 6. 接口收发

```bash
netstat -i
```

类似 `ifconfig`：

```text
Iface   MTU    RX-OK RX-ERR RX-DRP RX-OVR  TX-OK TX-ERR TX-DRP TX-OVR Flags
eth0   1500   12345   0      0      0     54321  0      0      0    BMRU
lo    65536       0   0      0      0        0  0      0      0    LRU
```

### 7. 协议统计

```bash
netstat -s
```

输出每个协议栈的统计（IP 收发 / 路由丢弃 / TCP 各状态 / UDP 入出 / ICMP 错误等）。

### 8. 多播组成员

```bash
netstat -g
```

### 9. 持续刷新

```bash
netstat -tlnpc 1
```

每秒刷新（`-c`）。

## Socket 状态

### 1. TCP（State 列）

| 状态 | 含义 |
| ---- | ---- |
| `LISTEN` | 正在监听 |
| `ESTABLISHED` | 已建立连接 |
| `TIME_WAIT` | 主动关闭方等待 2 MSL |
| `CLOSE_WAIT` | 被动关闭方等待应用关 |
| `SYN_SENT` | 已发送 SYN，等待响应 |
| `SYN_RECV` | 收到 SYN，等待 ACK |
| `FIN_WAIT_1` | 已发 FIN |
| `FIN_WAIT_2` | 对端确认，等待对端 FIN |
| `LAST_ACK` | 已发 FIN 等待 ACK |
| `CLOSING` | 双向同时关闭中 |
| `CLOSE` | socket 已关闭 |
| `NEW_SYN_RECV` (Linux) | fast open |

### 2. UDP

UDP 没有 connection，状态列展示 `UNCONN`，配合 `Recv-Q / Send-Q` 表示是否被读了 / 被排队。

## 工作原理

`netstat` 内核读的是：

- `/proc/net/tcp`、`/proc/net/udp`、`/proc/net/raw`、`/proc/net/unix` 等
- `/proc/net/dev`、`/proc/net/route`

也就是说，netstat 是 `/proc` 的"用户态翻译层"，这也是为什么"请 root"才能看到其他用户的进程名字（`-p` 时遍历 `/proc/[pid]/cmdline`）。

```text
proc → /proc/net/* → netstat → 表格
```

## 与 ss / ip 的对比

| 维度 | netstat | ss（iproute2） | ip |
| ---- | ------- | ------------- | --- |
| 来源 | net-tools | iproute2 | iproute2 |
| 安装 | 部分发行版已默认不装 | 主流默认 | 主流默认 |
| 速度 | 慢（解析大量连接） | 快（直接 netlink） | – |
| 过滤 | 用 grep / awk | 内置 `state FILTER` / `sport` / `dport` | – |
| 替代关系 | – | TCP / UDP / Unix 等常用功能 | 替代 ifconfig / route |
| 兼容 | BSD / 部分 macOS | Linux 主流 | Linux 主流 |

### 1. 常用 ss 替代

```bash
ss -tlnp                 # 类似 netstat -tlnp
ss -s                    # 统计
ss -t state established  # 已建立的连接
ss -t sport = :80        # 80 端口作为源
ss -dport ge :1024       # 目的端口 ≥ 1024
ss -K                   # 关闭 socket（-K 选项，root）
```

### 2. 常用 ip 替代

```bash
ip route                 # 替代 netstat -r
ip -s link               # 替代 netstat -i
ip addr                  # 替代 ifconfig
```

## 实用排错场景

### 1. 端口是否被监听

```bash
sudo netstat -tlnp | grep :3306
```

### 2. 哪些进程连到 8080

```bash
sudo netstat -tnp | grep ":8080" | grep ESTABLISHED
```

### 3. 大量 TIME_WAIT

```bash
netstat -ant | awk '/^tcp/ {print $NF}' | sort | uniq -c | sort -rn
```

`CLOSE_WAIT` 增多通常是应用未读 socket；`TIME_WAIT` 多是主动关闭方大量短连接。

### 4. 谁在连外部 IP

```bash
netstat -antp | grep ESTABLISHED | head
```

### 5. Unix 域套接字（Docker / Postgres / MySQL）

```bash
netstat -xnp | grep -i mysql
```

### 6. IPv6

```bash
netstat -6 -tlnp
```

## 退出码

| 退出码 | 含义 |
| ---- | ---- |
| 0 | 成功 |
| 1 | 命令无效 |
| 2 | 缺少权限（看 `-p`） |

## 注意

- 一定要 `-p` 才能看到 PID，普通用户仅能看到自己的进程；看别人的要 root
- `inet6`（IPv6 socket）也展示为 `tcp6`，不是 IPv4
- Unix 域 socket 路径无法在终端太长时显示完整，使用 `find /proc/*/fd -lname '<socket>'` 反查进程
- 巨量连接（10 万+）时 netstat 会非常慢，**首选 ss**

## 一句话总结

```text
netstat = 经典 / 跨发行版（除了现代 RHEL 系）
ss      = 现代 Linux 首选，性能好 / 内置过滤
ip      = 现代 Linux 用于替代 ifconfig / route
```

排错顺序建议：

1. `netstat -tlnp` 看监听（无 netstat 用 `ss -tlnp`）
2. `netstat -tnp | grep ESTABLISHED` 看活跃连接
3. `netstat -rn` 看路由（无 netstat 用 `ip route`）

## 参考

- `man netstat`
- `man ss`
- `man ip`
- [Bash 官网 - net-tools 已停止维护](https://github.com/ecki/net-tools)（建议过渡 iproute2）
- [Linux Foundation - iproute2 wiki](https://wiki.linuxfoundation.org/networking/iproute2)
