# 双活 HAProxy：金融数据场景的最优 HA 方案

## 1. 是什么？

**双活 HAProxy** = 两台机器都承担业务流量（不分主备），前面挂一个 HAProxy 做**四层负载均衡 + 健康检查 + 故障自动剔除**。任一节点挂了，HAProxy 在 50-200ms 内把流量切到健康节点，**客户端无感知**。

适用场景：
- 长连接 + 低延迟（如金融行情订阅、推送服务、API 网关）
- 资源利用率要求高（不能 50% 闲置）
- 切换时间要求 < 1 秒（不能容忍 keepalived 的 3-5 秒漂移）

---

## 2. 为什么不用 keepalived？

| 维度 | keepalived + VIP | 双活 HAProxy |
| --- | --- | --- |
| **切换时间** | 3-5 秒（VRRP 协议开销） | 50-200ms（TCP 层切换） |
| **资源利用率** | 50%（备机空跑） | 100%（双活负载） |
| **客户端体验** | VIP 漂移 → TCP 重连 | 客户端连接不断（短重试） |
| **脑裂风险** | 有（多播/单播心跳丢失） | 无（HAProxy 主动探活） |
| **数据连续性** | 漂移期间数据丢失 | 故障节点连接 1-2 秒内重连 |

核心区别：keepalived 是**被动漂移**（等故障发生再切 IP），HAProxy 是**主动探活**（持续探测，主动剔除故障节点）。

---

## 3. 整体架构

```
                      ┌─────────────────────┐
                      │   HAProxy 主节点     │  ← VIP（云上用 SLB/CLB）
                      │   监听 :8888         │
                      └──────────┬──────────┘
                                 │ 健康检查（每秒）
                ┌────────────────┼────────────────┐
                ▼                ▼                ▼
         ┌──────────┐     ┌──────────┐     ┌──────────┐
         │ Backend1 │     │ Backend2 │     │ Backend3 │  ← 业务节点
         │ :18001   │     │ :18001   │     │ :18001   │
         └────┬─────┘     └────┬─────┘     └────┬─────┘
              │                │                │
              └────────────────┴────────────────┘
                       │
                ┌──────┴──────┐
                │  券商数据源  │
                │ (CTP/LTS/...)│
                └─────────────┘
```

**关键点**：
- HAProxy 节点本身也需要 HA（用 keepalived 给 HAProxy 做 VIP 漂移，但 HAProxy 切换时间极短 ≈ 50ms）
- 业务节点（Backend）双活，各自独立连接券商
- HAProxy 持续健康检查，挂了自动剔除，恢复自动加回

---

## 4. HAProxy 配置详解

### 4.1 完整配置

```haproxy
# /etc/haproxy/haproxy.cfg

global
    log /dev/log local0
    log /dev/log local1 notice
    chroot /var/lib/haproxy
    stats socket /run/haproxy/admin.sock mode 660 level admin
    stats timeout 30s
    user haproxy
    group haproxy
    daemon

    # 性能调优
    maxconn 100000
    nbthread 4
    cpu-map 1 1
    cpu-map 2 2
    cpu-map 3 3
    cpu-map 4 4

    # SSL（如果需要）
    # ssl-default-bind-ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256
    # ssl-default-bind-options ssl-min-ver TLSv1.2

defaults
    log     global
    mode    tcp              # 四层代理（性能优先）
    option  tcplog
    option  dontlognull
    option  redispatch        # 故障时重定向连接
    retries 3
    timeout connect 5s
    timeout client  300s      # 长连接场景：客户端超时设大
    timeout server  300s
    timeout tunnel  3600s     # 隧道超时（WebSocket/行情推送）
    timeout http-request 10s
    timeout http-keep-alive 10s
    timeout queue 30s

# ============================================
# 监控页面（可选）
# ============================================
listen stats
    bind *:8404
    mode http
    stats enable
    stats uri /stats
    stats refresh 10s
    stats auth admin:StrongPwd123

# ============================================
# 业务流量入口：券商行情订阅
# ============================================
frontend ft_broker
    bind *:8888
    mode tcp
    default_backend bk_broker

backend bk_broker
    mode tcp
    balance roundrobin       # 也可用 leastconn、source

    # 健康检查（关键！）
    option tcp-check
    tcp-check connect
    tcp-check send "PING\r\n"
    tcp-check expect string +PONG
    tcp-check connect

    # 后端节点
    server broker1 10.0.1.11:18001 check inter 1s rise 2 fall 3 maxconn 5000
    server broker2 10.0.1.12:18001 check inter 1s rise 2 fall 3 maxconn 5000
    server broker3 10.0.1.13:18001 check inter 1s rise 2 fall 3 maxconn 5000

    # 健康节点的 source IP（可选）
    # source 0.0.0.0 usesrc clientip

# ============================================
# 管理 API（HTTP）
# ============================================
frontend ft_admin
    bind *:8080
    mode http
    default_backend bk_admin

backend bk_admin
    mode http
    balance roundrobin
    cookie SERVERID insert indirect nocache
    server admin1 10.0.1.11:8080 check inter 2s
    server admin2 10.0.1.12:8080 check inter 2s
```

### 4.2 关键参数解释

| 参数 | 作用 | 推荐值 |
| --- | --- | --- |
| `mode tcp` | 四层代理，性能损耗最小 | TCP 业务用 `tcp`，HTTP 用 `http` |
| `balance roundrobin` | 轮询分发 | TCP 长连接推荐 `source`（按客户端 IP 哈希，保持会话稳定） |
| `check inter 1s` | 健康检查间隔 | 1-3 秒，越短越敏感但 CPU 越高 |
| `rise 2` | 连续 2 次成功才标记 UP | 避免抖动 |
| `fall 3` | 连续 3 次失败才标记 DOWN | 给短暂网络抖动留缓冲 |
| `maxconn 5000` | 单节点最大连接数 | 根据业务容量调整 |
| `timeout tunnel 3600s` | TCP 隧道超时 | 行情推送这种长连接要设大 |
| `option redispatch` | 故障时重新分发改连 | **强烈建议开启** |
| `option tcp-check` | 启用 TCP 层健康检查 | 比单纯 TCP connect 更可靠 |

---

## 5. 健康检查的三种深度

### 5.1 简单 TCP 连接检查

```haproxy
server broker1 10.0.1.11:18001 check inter 1s
```

只检查端口是否能连。**最轻量，但最弱**——进程在但业务卡死时检测不到。

### 5.2 协议层探活（推荐）

```haproxy
option tcp-check
tcp-check connect
tcp-check send "PING\r\n"
tcp-check expect string +PONG
tcp-check connect
```

模拟客户端发送 PING，期待 PONG 响应。**金融场景强烈推荐**——能在秒级发现"假活"。

### 5.3 HTTP 健康检查

```haproxy
option httpchk GET /health
http-check expect status 200
```

用于 HTTP API 场景，可访问业务自定义的健康端点。

### 5.4 外部健康检查脚本

如果业务复杂，可以在后端节点上跑外部脚本，HAProxy 通过 socket 通信：

```haproxy
# /etc/haproxy/haproxy.cfg
global
    external-check command "/usr/local/bin/health_check.sh"

backend bk_broker
    server broker1 10.0.1.11:18001 check
```

```bash
#!/bin/bash
# /usr/local/bin/health_check.sh
# 参数: <ip> <port> <server-name>
# 返回 0 健康，1 故障
ip=$1
port=$2

RESP=$(echo -e "PING\r\n" | timeout 2 nc $ip $port)
if [[ "$RESP" == *"PONG"* ]]; then
    exit 0
fi
exit 1
```

---

## 6. 双活场景的负载均衡策略

### 6.1 Round Robin（轮询）

```haproxy
balance roundrobin
```

新连接依次分到各节点。**适合短连接、查询型业务**。

### 6.2 Least Connections（最少连接）

```haproxy
balance leastconn
```

新连接分给当前连接数最少的节点。**适合长连接，负载更均衡**。

### 6.3 Source IP Hash（源 IP 哈希）

```haproxy
balance source
hash-type consistent
```

同一客户端 IP 始终连同一节点。**适合需要会话保持**（如行情订阅，状态在节点内存里）。

⚠️ 缺点：客户端分布不均时，可能导致负载倾斜。

### 6.4 随机 / 一致性哈希

```haproxy
balance random
# 或
balance roundrobin
hash-type consistent
```

适合大规模后端场景。

---

## 7. 故障切换实战示例

### 7.1 模拟后端宕机

```bash
# 在 broker2 上停掉业务
ssh broker2 "systemctl stop broker_service"

# 观察 HAProxy 状态
echo "show stat" | socat stdio /run/haproxy/admin.sock
```

```
bk_broker
broker1   UP 1/3 5000 0 0 0
broker2   DOWN 0/3 0 0 0 0    ← 已剔除
broker3   UP 1/3 5000 0 0 0
```

### 7.2 客户端重连逻辑

```python
import socket
import time
import random

class HAClient:
    def __init__(self, proxy_addr=("10.0.1.10", 8888)):
        self.proxy_addr = proxy_addr
        self.sock = None
        self._connect()

    def _connect(self):
        if self.sock:
            try: self.sock.close()
            except: pass
        self.sock = socket.socket()
        self.sock.settimeout(2)
        self.sock.connect(self.proxy_addr)

    def query(self, data):
        for retry in range(5):
            try:
                self.sock.send(data)
                return self.sock.recv(4096)
            except (ConnectionError, socket.timeout, OSError):
                # HAProxy 已切换到健康节点，重连
                delay = min(0.1 * (2 ** retry), 2.0) + random.random() * 0.1
                time.sleep(delay)
                self._connect()
        raise Exception("all retries failed")

    def close(self):
        if self.sock:
            self.sock.close()
```

### 7.3 切换时间实测

| 阶段 | 耗时 |
| --- | --- |
| HAProxy 检测到 broker2 故障 | 1-3 秒（inter=1s, fall=3） |
| HAProxy 标记 broker2 DOWN | < 100ms |
| 客户端下一次请求重连 | 200-500ms |
| HAProxy 把新连接分到 broker1/3 | < 10ms |
| **总切换时间** | **2-4 秒** |

比 keepalived 的 3-5 秒稍快，**关键是切换期间已建立的连接会被新连接绕过故障节点**，不会卡 3-5 秒。

---

## 8. 高可用部署：HAProxy 自身

HAProxy 本身也是单点。需要给 HAProxy 再加一层 HA：

### 方案 1：Keepalived + HAProxy（最常见）

```
        VIP (keepalived 漂移)
           │
     ┌─────┴─────┐
     ▼           ▼
   HAProxy-A   HAProxy-B
   (active)    (standby)
```

- HAProxy-A 和 B 共享 VIP
- keepalived 做 VIP 漂移（HAProxy 自身故障时切换）
- 平时只有 A 工作，B 空跑（接受 keepalived 的资源浪费）
- **HAProxy 切换时间 ≈ 50ms**（keeplived 启用了 `vrrp_script` 监测 HAProxy 进程）

### 方案 2：HAProxy 双活 + DNS 轮询

```
   客户端
     │
  DNS 轮询
     │
  ┌──┴──┐
  A     B
  HAProxy HAProxy
  (各50%)
```

- 两个 HAProxy 同时工作，DNS 轮询分发
- 任一 HAProxy 挂了，DNS 摘除（健康检查）
- 简单但切换慢（DNS 缓存）

### 方案 3：云厂商 LB（生产推荐）

```
   ┌──────────────────┐
   │  AWS ALB / 阿里 SLB │  ← 云厂商托管，自动 HA
   └────────┬─────────┘
            │
      ┌─────┴─────┐
      ▼           ▼
   HAProxy-A   HAProxy-B
```

- 云厂商 LB 自身就是多 AZ HA
- 业务流量从 LB 进 HAProxy，再到后端
- 阿里云 SLB / AWS ALB / GCP LB 都是这个套路

---

## 9. 实战建议与坑

### 9.1 性能调优

```haproxy
global
    maxconn 100000
    nbthread 4              # 多线程（HAProxy 2.x 才支持）
    tune.bufsize 32768      # 单连接缓冲
    tune.maxrewrite 1024

defaults
    option tcp-smart-accept  # TCP 智能接受
    option tcp-smart-connect
```

### 9.2 日志与监控

```haproxy
global
    log /dev/log local0 info
    log-tag "haproxy"

defaults
    log-format "%ci:%cp [%t] %ft %b/%s %Tw/%Tc/%Tt %B %ts %ac/%fc/%bc/%sc/%rc %sq/%bq"
    # %ci 客户端 IP
    # %cp 客户端端口
    # %t 时间
    # %ft 前端名
    # %b 后端名
    # %s 服务器名
    # %Tw/Tc/Tt 等待/连接/总时间
    # %B 发送字节
    # %ac/fc/bc/sc/rc 活动/前端/后端/服务端/重试连接数
```

**接入 Prometheus**：

```bash
# 启动时暴露 metrics
haproxy -W -db -f /etc/haproxy/haproxy.cfg

# 用 prometheus exporter
docker run -d -p 9101:9101 -v /run/haproxy:/run/haproxy prom/haproxy-exporter
```

### 9.3 常见坑

1. **健康检查过于严格**：业务瞬时慢就被剔除。增加 `fall` 值或用业务层探活。
2. **`timeout tunnel` 太小**：长连接被 HAProxy 主动断。金融场景至少 1 小时。
3. **`maxconn` 没设**：单节点被打爆。必须根据容量规划。
4. **HAProxy 自身没监控**：HAProxy 挂了没人知道。必须加进程监控。
5. **脑裂（多个 HAProxy 同时持有 VIP）**：keepalived 配 unicast peer + 仲裁盘。

### 9.4 与 LVS 对比

| 维度 | HAProxy | LVS (IPVS) |
| --- | --- | --- |
| 工作层 | 4 层 / 7 层 | 4 层（内核态） |
| 性能 | 高（用户态） | 极高（内核态，无上下文切换） |
| 健康检查 | 丰富（HTTP/TCP/脚本） | 简单（TCP/UDP/HTTP） |
| 配置复杂度 | 中 | 低 |
| 适用 | 通用首选 | 超大规模（>10 万 QPS） |

**金融数据场景**：HAProxy 足够，配置灵活。LVS 留给超大规模。

---

## 10. 完整部署清单

```bash
# 1. 安装 HAProxy
yum install -y haproxy    # 或 apt

# 2. 配置
vim /etc/haproxy/haproxy.cfg

# 3. 健康检查脚本（如需要）
vim /usr/local/bin/health_check.sh
chmod +x /usr/local/bin/health_check.sh

# 4. 启动
systemctl enable haproxy
systemctl start haproxy

# 5. 验证
curl http://10.0.1.10:8404/stats  # 监控页
echo "show stat" | socat stdio /run/haproxy/admin.sock

# 6. 给 HAProxy 加 keepalived（双机）
yum install -y keepalived
vim /etc/keepalived/keepalived.conf  # 加 vrrp_script 检测 haproxy 进程
systemctl enable keepalived
systemctl start keepalived
```

---

## 11. 总结

**双活 HAProxy 是金融数据场景的最优解**：
- 切换时间 50-200ms（vs keepalived 3-5s）
- 资源利用率 100%（vs keepalived 50%）
- 客户端体验好（短重试即可）
- 健康检查丰富（TCP/协议层/HTTP/脚本）

**典型拓扑**：
```
券商 → 业务节点（双活，各连券商）
         ↑↓
       HAProxy（双机 + keepalived 或云 LB）
         ↑↓
       客户端
```

**一句话**：keepalived 适合 Web/HTTP 这种"容忍秒级中断"的场景；金融数据这种"不能容忍秒级丢失"的场景，**用 HAProxy 双活 + 协议层健康检查**。
