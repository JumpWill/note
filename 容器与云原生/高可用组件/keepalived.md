# Keepalived 详解：高可用与负载均衡的瑞士军刀

## 1. 是什么？

**Keepalived** 是一款基于 **VRRP（Virtual Router Redundancy Protocol，虚拟路由冗余协议）** 实现的高可用（HA）软件，最初为 LVS 负载均衡器设计，现已广泛用于：

- **IP 漂移（VIP 漂移）**：在多台服务器之间共享一个虚拟 IP，主节点故障时 VIP 自动漂到备节点
- **健康检查**：对后端真实服务器（Real Server）做健康探测，失败则从 LVS 池中摘除
- **负载均衡**：与 LVS/IPVS 深度集成（注意：Keepalived 本身不直接做负载均衡调度，靠 IPVS；Nginx upstream 的 HA 场景也常用它）

本质上，Keepalived = **VRRP 协议实现** + **健康检查器** + **IPVS 管理器**。

---

## 2. 核心概念

### 2.1 VRRP 虚拟路由冗余协议

VRRP 解决的是**默认网关单点故障**问题。多个物理路由器组成一个**虚拟路由器**，对外只暴露一个 **VIP（Virtual IP）**。

```
        ┌──────────────┐
        │   VIP: 10.0.0.100   │  ← 客户端始终访问这个 IP
        └──────┬───────┘
               │
       ┌───────┴───────┐
       ▼               ▼
  ┌─────────┐     ┌─────────┐
  │ Master  │     │ Backup  │
  │10.0.0.1 │     │10.0.0.2 │
  └─────────┘     └─────────┘
       ▲               ▲
   优先级 100       优先级 90
```

- **虚拟路由器（Virtual Router）**：由一个 VRID 标识，同一组路由器 VRID 必须一致
- **VIP / VMAC**：虚拟 IP 和虚拟 MAC（MAC 格式为 `00-00-5E-00-01-XX`，最后两位是 VRID）
- **Master**：当前承担流量的节点（默认是优先级最高的）
- **Backup**：待命的节点，监听 Master 的心跳

### 2.2 优先级（Priority）

- 取值范围 **0-255**（0 和 255 是保留值）
- **255**：IP 地址拥有者（接口 IP == VIP），自动成为 Master
- 默认 **100**
- 数值越大，优先级越高，越容易成为 Master

### 2.3 抢占模式（Preemption）

- `nopreempt` 未配置：Backup 检测到 Master 故障时，即使原 Master 恢复，也不会自动抢占（除非原 Master 永久下线）
- `nopreempt` 配置：原 Master 恢复后会重新抢占回 VIP

### 2.4 状态机

Keepalived 内部有 6 个状态：

| 状态 | 说明 |
| --- | --- |
| **Init** | 初始状态，配置加载完成 |
| **Backup** | 备份状态，监听 Master 通告 |
| **Master** | 主状态，发送 VRRP 通告，持有 VIP |
| **Fault** | 故障状态，健康检查失败 |
| **Release** | 释放状态，主动放弃 Master 角色 |
| **Stopped** | 停止状态，进程退出 |

---

## 3. 工作原理

### 3.1 心跳与选举

1. **启动时**：所有节点进入 `Init` 状态
2. **优先级比较**：通过 VRRP 通告（多播地址 `224.0.0.18`）互相告知优先级
3. **选举 Master**：优先级最高的成为 Master，立即进入 `Master` 状态
4. **其他节点**：进入 `Backup` 状态，开始监听 Master 的通告

### 3.2 故障切换流程

```
Master 故障
    ↓
Backup 在 3 × advert_int 时间内未收到通告
    ↓
进入 Master 候选状态（等待 skew_time）
    ↓
skew_time = (256 - priority) / 256 × advert_int
    ↓
Backup 升级为 Master，发送免费 ARP 更新 VIP-MAC 映射
    ↓
客户端无感知，继续访问 VIP
```

**关键参数**：

- `advert_int`：VRRP 通告间隔（默认 1 秒）
- `preempt_delay`：抢占延迟（可选）
- `vrrp_garp_master_repeat`：故障切换后免费 ARP 发送次数（默认 5）

### 3.3 健康检查

Keepalived 支持三层健康检查：

#### TCP 检查

```nginx
# 简单 TCP 端口探测
TCP_CHECK {
    connect_timeout 3
    connect_port 3306
    retry 3
    delay_before_retry 3
}
```

#### HTTP 检查

```nginx
# 探测 URL 返回码
HTTP_GET {
    url {
        path /health
        status_code 200
    }
    connect_timeout 2
    retry 2
    delay_before_retry 2
}
```

#### 自定义脚本

```nginx
# 灵活但要注意：脚本必须有执行权限，且 exit 0 为健康
vrrp_script chk_nginx {
    script "/usr/local/bin/check_nginx.sh"
    interval 2
    weight -20        # 健康度降低时，priority -= 20
    fall 3            # 连续失败 3 次才认定故障
    rise 2            # 连续成功 2 次才认定恢复
    timeout 5
}
```

权重机制：
- `weight > 0`：健康时增加优先级（让该节点更可能成为 Master）
- `weight < 0`：故障时降低优先级（触发 VIP 漂移）
- 当 `priority + weight < 备用节点 priority` 时，主动让出

---

## 4. 安装与配置

### 4.1 安装

```bash
# CentOS/RHEL
yum install -y keepalived

# Ubuntu/Debian
apt install -y keepalived

# 验证版本
keepalived -v
```

### 4.2 完整配置示例

```nginx
# /etc/keepalived/keepalived.conf

# ===== 全局配置 =====
global_defs {
    notification_email {
        admin@example.com
    }
    notification_email_from keepalived@example.com
    smtp_server smtp.example.com
    smtp_connect_timeout 30
    router_id LVS_DEVEL          # 集群内唯一标识
    vrrp_skip_check_adv_addr
    vrrp_strict                   # 严格模式：未配置 VIP 报错
    vrrp_garp_interval 0
    vrrp_gna_interval 0
    script_user root
    enable_script_security
}

# ===== 健康检查脚本 =====
vrrp_script chk_nginx {
    script "/usr/local/bin/check_nginx.sh"
    interval 2
    weight -30
    fall 3
    rise 2
    timeout 5
}

vrrp_script chk_disk {
    script "df -h | awk '$5 > 90 {exit 1}'"
    interval 10
    weight -10
    fall 2
    rise 2
}

# ===== VRRP 实例 =====
vrrp_instance VI_1 {
    state MASTER                 # 初始状态（仅启动时生效）
    interface eth0              # 绑定的网卡
    virtual_router_id 51        # VRID，0-255，集群内一致
    priority 100                 # 优先级
    advert_int 1                 # 通告间隔（秒）

    authentication {
        auth_type PASS           # 简单密码认证
        auth_pass 1111          # 8 位以内
    }

    virtual_ipaddress {
        10.0.0.100/24 dev eth0   # VIP + 子网 + 网卡
        10.0.0.101/24 dev eth0   # 支持多 VIP
    }

    unicast_src_ip 10.0.0.1    # 单播源 IP（推荐，避开多播问题）
    unicast_peer {
        10.0.0.2                # 对端 IP
    }

    # preempt_delay 5             # 抢占延迟 5 秒（可选）

    track_script {
        chk_nginx
        chk_disk
    }

    notify_master "/usr/local/bin/notify.sh master"
    notify_backup "/usr/local/bin/notify.sh backup"
    notify_fault "/usr/local/bin/notify.sh fault"
    notify_stop "/usr/local/bin/notify.sh stop"

    smtp_alert                  # 启用邮件告警
}

# ===== 虚拟服务器（LVS 负载均衡，可选）=====
virtual_server 10.0.0.100 80 {
    delay_loop 6
    lb_algo rr                  # 轮询
    lb_kind DR                  # DR 模式（性能最好）
    persistence_timeout 0
    protocol TCP

    real_server 10.0.0.10 80 {
        weight 1
        TCP_CHECK {
            connect_timeout 3
            connect_port 80
        }
    }
    real_server 10.0.0.11 80 {
        weight 1
        TCP_CHECK {
            connect_timeout 3
            connect_port 80
        }
    }
}
```

### 4.3 健康检查脚本示例

```bash
#!/bin/bash
# /usr/local/bin/check_nginx.sh

# 检查 Nginx 进程
if ! pgrep -x nginx > /dev/null; then
    exit 1
fi

# 检查 80 端口
if ! ss -tln | grep -q ':80 '; then
    exit 1
fi

# 检查 HTTP 响应
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1/health)
if [ "$HTTP_CODE" != "200" ]; then
    exit 1
fi

exit 0
```

```bash
chmod +x /usr/local/bin/check_nginx.sh
```

### 4.4 启动与管理

```bash
systemctl enable keepalived
systemctl start keepalived
systemctl status keepalived

# 查看 VIP 漂移日志
journalctl -u keepalived -f
tail -f /var/log/messages | grep Keepalived
```

---

## 5. 工作模式与场景

### 5.1 双机主备（Active/Passive）

最经典模式：一主一备，故障时备机接管。

```
   正常                      故障后
  ┌───┐                    ┌───┐
  │ M ├──VIP──→ 客户端      │ B ├──VIP──→ 客户端
  └───┘                    └───┘
  ┌───┐                    ┌───┐
  │ B │ (待命)             │ M │ (已下线)
  └───┘                    └───┘
```

**特点**：资源浪费 50%，但配置简单、切换可靠。

### 5.2 双主互备（Active/Active）

两个 VIP 分别在两台机器上，互为备份。

```
  机器 A: VIP1（主）、VIP2（备）
  机器 B: VIP1（备）、VIP2（主）
```

**特点**：资源利用率高，但脑裂风险也高。

### 5.3 负载均衡 + 高可用（Keepalived + LVS）

```
                  ┌─── Real Server 1
   VIP ─→ LVS ───┼─── Real Server 2
                  └─── Real Server 3
```

**特点**：VIP 漂移保证入口高可用，IPVS 做后端负载均衡。

### 5.4 脑裂问题

**脑裂（Split Brain）**：Master 与 Backup 之间心跳中断，但 Master 实际并未宕机，导致 VIP 同时出现在两台机器上。

**根因**：
- 链路抖动 / 心跳超时设置过短
- 防火墙或 iptables 拦截了 VRRP 多播包
- vCPU 抢占或 GC 停顿

**预防措施**：
- 配置 `unicast_peer`（单播心跳），走独立的心跳网卡
- 备份链路（双心跳）
- 启用磁盘锁（`vrrp_garp_master_repeat` + 写盘）
- 仲裁机制（连接第三方存储判定主备）

---

## 6. 关键参数速查

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `priority` | 100 | 优先级，0-255 |
| `advert_int` | 1 | VRRP 通告间隔（秒） |
| `preempt_delay` | 0 | 抢占延迟（秒） |
| `garp_master_delay` | 5 | 升级为 Master 后多久发免费 ARP |
| `garp_master_repeat` | 5 | 免费 ARP 发送次数 |
| `virtual_router_id` | 必填 | VRID，0-255 |
| `weight` | 0 | 脚本健康度对优先级的影响 |
| `fall` | 3 | 连续失败次数判定故障 |
| `rise` | 2 | 连续成功次数判定恢复 |
| `interval` | 1 | 健康检查间隔（秒） |
| `vrrp_strict` | 关闭 | 严格模式，违反规范时报警 |

---

## 7. 实战建议与最佳实践

### 7.1 网络规划

1. **心跳链路分离**：VRRP 心跳与业务流量走不同物理网卡或 VLAN
2. **使用单播模式**（`unicast_peer`）：避免多播在跨网段时被路由丢弃
3. **预留 IP 段**：VIP 子网要预留足够 IP，避免地址冲突

### 7.2 故障检测

1. **不仅检测进程，更检测业务**：脚本要验证应用层是否正常（如 HTTP 200）
2. **设置合理的 `fall`/`rise`**：避免抖动切换
3. **加权降级而非直接宕机**：`weight` 设置为负值可让优先级下降但仍能恢复

### 7.3 切换时间

- 单播通告：默认 1 秒 × 3 + skew ≈ 3.x 秒
- 加上 `preempt_delay`：可延长到 5-10 秒
- 同步阻塞（`sync_group`）：组内实例联动切换

### 7.4 容器化注意

Keepalived 在容器内运行需注意：

- 需要 `NET_ADMIN` 能力添加 VIP
- 单播心跳在 K8s 网络下可能受阻
- 建议用 `hostNetwork: true` 或 macvlan
- 云厂商一般不允许多播/免费 ARP，可用云厂商 LB + API 调用代替

### 7.5 常见故障排查

```bash
# 查看 VRRP 状态
ip addr show eth0

# 抓包分析 VRRP 通告
tcpdump -i eth0 -n vrrp

# 查看详细日志
journalctl -u keepalived -n 100

# 检查配置文件
keepalived -t -f /etc/keepalived/keepalived.conf
```

---

## 8. 总结

| 维度 | 要点 |
| --- | --- |
| **协议** | VRRP（虚拟路由冗余协议） |
| **核心机制** | 优先级选举 + 状态通告 + 故障切换 |
| **检测方式** | TCP / HTTP / 自定义脚本 |
| **典型切换** | 3-5 秒内完成 VIP 漂移 |
| **搭配搭档** | LVS、Nginx upstream、HAProxy |
| **不擅长** | 应用层健康、长距离跨地域 HA（建议用 DNS/LB 替代） |

**一句话总结**：Keepalived 用 VRRP 协议把多台机器变成一个虚拟路由器，谁的优先级高谁当 Master；Master 挂了，备机接管 VIP，客户端无感知。这是中小规模高可用场景最简单可靠的方案。

---

## 9. 实战案例配置

### 9.1 单 VIP 主备(Nginx 高可用)

**场景**:两台 Nginx 节点,VIP 漂移;任一 Nginx 挂掉,VIP 立刻切到另一台。

#### 节点 A(Master)

```nginx
# /etc/keepalived/keepalived.conf
global_defs {
    router_id NGINX_HA_A
    enable_script_security
}

vrrp_script chk_nginx {
    script "/usr/local/bin/check_nginx.sh"
    interval 2
    weight -30
    fall 3
    rise 2
    timeout 5
}

vrrp_instance VI_NGINX {
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
        10.0.0.100/24 dev eth0 label eth0:1
    }

    unicast_src_ip 10.0.0.1
    unicast_peer {
        10.0.0.2
    }

    track_script {
        chk_nginx
    }

    notify_master "/usr/local/bin/notify.sh master"
    notify_backup "/usr/local/bin/notify.sh backup"
    notify_fault   "/usr/local/bin/notify.sh fault"
}
```

#### 节点 B(Backup)

```nginx
# 仅列差异
vrrp_instance VI_NGINX {
    state BACKUP               # 注意是 BACKUP,不是 MASTER
    interface eth0
    virtual_router_id 51       # 必须一致
    priority 90                # 低于 A
    unicast_src_ip 10.0.0.2
    unicast_peer {
        10.0.0.1
    }
}
```

#### 健康检查脚本

```bash
#!/bin/bash
# /usr/local/bin/check_nginx.sh
# 检查 nginx 进程 + 端口 + HTTP
pgrep -x nginx > /dev/null || exit 1
ss -tln | grep -q ':80 ' || exit 1
curl -sf http://127.0.0.1/health -o /dev/null || exit 1
exit 0
```

```bash
chmod +x /usr/local/bin/check_nginx.sh
```

---

### 9.2 双 VIP 双主互备(Active/Active)

**场景**:两台机器各持一个 VIP,互为备份,资源利用率 100%。

```text
机器 A:VIP-1(Master),VIP-2(Backup)
机器 B:VIP-1(Backup),VIP-2(Master)

DNS / LB 同时用 VIP-1 + VIP-2 轮询,任一节点故障不影响整体服务。
```

#### 节点 A

```nginx
vrrp_instance VI_1 {
    state MASTER
    interface eth0
    virtual_router_id 51
    priority 100
    virtual_ipaddress {
        10.0.0.100/24 dev eth0 label eth0:1   # VIP-1
    }
    unicast_peer { 10.0.0.2 }
}

vrrp_instance VI_2 {
    state BACKUP
    interface eth0
    virtual_router_id 52                    # VRID 必须不同
    priority 90
    virtual_ipaddress {
        10.0.0.200/24 dev eth0 label eth0:2  # VIP-2
    }
    unicast_peer { 10.0.0.2 }
}
```

#### 节点 B(对调 priority)

```nginx
vrrp_instance VI_1 {
    state BACKUP
    virtual_router_id 51
    priority 90
    virtual_ipaddress { 10.0.0.100/24 dev eth0 label eth0:1 }
}

vrrp_instance VI_2 {
    state MASTER
    virtual_router_id 52
    priority 100
    virtual_ipaddress { 10.0.0.200/24 dev eth0 label eth0:2 }
}
```

---

### 9.3 MySQL 主从自动切换(VIP 漂移)

**场景**:MySQL 主库挂时,VIP 自动漂到从库(从库晋升为新主)。

#### 主库节点 keepalived.conf

```nginx
vrrp_script chk_mysql {
    script "/usr/local/bin/check_mysql_master.sh"
    interval 2
    weight -50                  # 优先级大幅降级触发漂移
    fall 3
    rise 2
}

vrrp_instance VI_MYSQL {
    state MASTER
    interface eth0
    virtual_router_id 60
    priority 100
    advert_int 1

    virtual_ipaddress {
        10.0.0.150/24 dev eth0 label eth0:mysql
    }

    track_script {
        chk_mysql
    }

    notify_master "/usr/local/bin/mysql_handler.sh master"
    notify_backup "/usr/local/bin/mysql_handler.sh backup"
    notify_fault   "/usr/local/bin/mysql_handler.sh fault"
}
```

#### 健康检查脚本(检查读写能力)

```bash
#!/bin/bash
# /usr/local/bin/check_mysql_master.sh
# 写测试:在临时库创建表,失败说明权限或写入异常
mysql -uroot -p"$MYSQL_PASS" -e "CREATE DATABASE IF NOT EXISTS _keepalive_test; \
    CREATE TABLE IF NOT EXISTS _keepalive_test.t(id INT); \
    INSERT INTO _keepalive_test.t VALUES(1); \
    DROP TABLE _keepalive_test.t; \
    DROP DATABASE _keepalive_test;" 2>/dev/null || exit 1

# 从角色检查:不应在从库上跑写
SLAVE_STATUS=$(mysql -uroot -p"$MYSQL_PASS" -e "SHOW SLAVE STATUS\G" 2>/dev/null)
if echo "$SLAVE_STATUS" | grep -q "Slave_IO_Running: Yes"; then
    exit 1   # 当前是从库,不应作为 master
fi

exit 0
```

#### 状态变化处理脚本

```bash
#!/bin/bash
# /usr/local/bin/mysql_handler.sh
TYPE=$1
case "$TYPE" in
    master)
        # 升为主时:停止从同步,打开写
        mysql -uroot -p"$MYSQL_PASS" -e "STOP SLAVE; SET GLOBAL read_only = OFF;"
        logger "MySQL promoted to MASTER"
        ;;
    backup)
        # 降为备时:开启只读,启动从同步
        mysql -uroot -p"$MYSQL_PASS" -e "SET GLOBAL read_only = ON; CHANGE MASTER TO MASTER_HOST='10.0.0.1', MASTER_USER='repl', MASTER_PASSWORD='xxx', MASTER_LOG_FILE='$BINLOG', MASTER_LOG_POS=$POS; START SLAVE;"
        logger "MySQL demoted to BACKUP"
        ;;
    fault)
        logger "MySQL health check failed"
        ;;
esac
```

---

### 9.4 Keepalived + LVS 经典 DR 高可用

**场景**:LVS 入口双 Director,Keepalived 负责 VIP 漂移 + RS 健康检查。

```nginx
# 两台 Director 共用配置(差异仅 router_id 和 priority)

global_defs {
    router_id LVS_D1            # 另一台改 LVS_D2
    enable_script_security
}

vrrp_instance VI_LVS {
    state MASTER                # 另一台改 BACKUP
    interface eth0
    virtual_router_id 51
    priority 100                # 另一台改 90
    advert_int 1

    virtual_ipaddress {
        10.0.0.100/24 dev eth0 label eth0:1
    }
}

# LVS 虚拟服务器(由 keepalived 自动维护 IPVS 规则)
virtual_server 10.0.0.100 80 {
    delay_loop 6
    lb_algo wlc
    lb_kind DR                  # DR 模式
    persistence_timeout 50
    protocol TCP

    real_server 10.0.1.11 80 {
        weight 3
        TCP_CHECK {
            connect_timeout 3
            nb_get_retry 3
            delay_before_retry 3
            connect_port 80
        }
    }

    real_server 10.0.1.12 80 {
        weight 1
        TCP_CHECK {
            connect_timeout 3
            connect_port 80
        }
    }

    real_server 10.0.1.13 80 {
        weight 1
        MISC_CHECK {
            misc_path "/usr/local/bin/check_app.sh"
            misc_timeout 5
        }
    }
}
```

**RS 端配置**(每台 RS 都做):

```bash
# lo 配置 VIP,抑制 ARP
ip addr add 10.0.0.100/32 dev lo
sysctl -w net.ipv4.conf.lo.arp_ignore=1
sysctl -w net.ipv4.conf.lo.arp_announce=2
sysctl -w net.ipv4.conf.all.arp_ignore=1
sysctl -w net.ipv4.conf.all.arp_announce=2
```

**完整 HA 链路**:

```text
client → VIP (10.0.0.100)
            │
            ▼
   Director-1 (Master)
   ├─ LVS / IPVS 调度
   ├─ TCP_CHECK RS 健康
   └─ 失败则降级 + VIP 漂移
            │
            ▼ (Director 挂了)
   Director-2 (Backup) 自动接管 VIP
```

---

## 10. BFD 加速漂移检测

### 10.1 为什么需要 BFD

**VRRP 心跳的局限**:

- `advert_int` 默认 1 秒,3 次超时 ≈ 3 秒才认定故障
- 加上 `skew_time` + GARP,实际切换 3-5 秒
- 对**金融、游戏、VoIP** 等秒级敏感业务,**不可接受**

**BFD**(Bidirectional Forwarding Detection,双向转发检测):

- RFC 5880,毫秒级(10-50ms)链路检测
- 不依赖路由协议,**纯 L2/L3 探测**
- 与 VRRP / OSPF / BGP 配合,加速故障感知

### 10.2 BFD 原理

```text
两端周期性发送 BFD 控制包(UDP 3784)
       │
       ├─> 接收端收到 → 链路正常
       │       │
       │       └─ 没收到(N × 探测周期)
       │              │
       │              ▼
       │       链路故障 → 立刻通知上层协议
       │
       └─> 探测间隔可到 10ms,远快于 VRRP 默认 1s
```

```text
VRRP 心跳: 1000ms × 3 = ~3s 感知故障
BFD:        50ms × 3 = ~150ms 感知故障

差距 20 倍
```

### 10.3 Keepalived 集成 BFD

Keepalived 2.x 起支持通过 `notify` + 外部 BFD 联动:

#### 方案 A:Keepalived + 自定义 BFD 脚本(主流)

```bash
# /usr/local/bin/bfd_peer_check.sh
# BFD 会话断时,主动触发 Keepalived 降级
# 此脚本由 systemd timer / cron 触发,或被 bird/quagga 的 bfd hook 调用

BFD_PEER=10.0.0.2
if ! bfd_peer_status $BFD_PEER | grep -q "Up"; then
    # BFD 邻居 down → 触发自身 priority 降到 0
    # 通过 ipvsadm 接口或 keepalived notify 实现
    logger "BFD peer $BFD_PEER down, demoting Keepalived priority"
    # 调用 keepalived 的 notify_fault 脚本
    /usr/local/bin/notify.sh fault
fi
```

#### 方案 B:vrrp_script 探测 BFD

```bash
# /usr/local/bin/check_bfd.sh
# 探测 BFD 邻居状态

BFD_PEER=$1
STATE=$(birdc "show bfd session $BFD_PEER" 2>/dev/null | awk '/State:/ {print $2}')
if [ "$STATE" != "Up" ]; then
    exit 1
fi
exit 0
```

```nginx
vrrp_script chk_bfd {
    script "/usr/local/bin/check_bfd.sh 10.0.0.2"
    interval 1              # 1 秒探测(脚本内 BFD 是 50ms,但脚本本身 1s 跑一次)
    weight -100             # 触发立即降级
    fall 1                  # 一次失败就判定
    rise 1
}
```

#### 方案 C:直接用 BIRD / FRR 跑 BFD,BGP 联动(推荐,见 §11)

**BIRD BFD 配置**:

```
# /etc/bird/bird.conf
protocol bfd {
    interface "eth0" {
        min_rx_interval 50ms;
        min_tx_interval 50ms;
        multiplier 3;
    };
    neighbor 10.0.0.2;
}
```

### 10.4 BFD 部署建议

| 场景 | 推荐 |
| ---- | ---- |
| 延迟 < 50ms 敏感业务 | 必上 BFD |
| 普通 Web / API | VRRP 默认即可 |
| 跨数据中心 | **BFD + BGP**(见 §11) |
| 容器化 | BFD 需特权容器或 hostNetwork |

---

## 11. BGP Anycast + ECMP 方案

### 11.1 为什么需要替代 VRRP

VRRP / Keepalived 的局限:

- **VIP 是"单点"的**:同一时刻只有一台机器持有 VIP,**其他节点空闲**
- **切换有抖动**:即便毫秒级,流量仍会中断
- **不能跨地域**:VRRP 仅限同 L2 / L3 域
- **水平扩展差**:VIP 只能 1-2 个,扩到 5+ 节点难

### 11.2 Anycast + ECMP 原理

```text
        ┌─────────────────────────────────────────┐
        │  公网 / 客户端侧                        │
        │  DNS / 路由:目标 IP = 10.0.0.100        │
        └───────────────┬─────────────────────────┘
                        │  BGP 路由宣告
        ┌───────────────┴─────────────────────────┐
        │ 路由器(根据 BGP 选最优下一跳)        │
        └───────────────┬─────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
  ┌─────────┐     ┌─────────┐     ┌─────────┐
  │ Node-1  │     │ Node-2  │     │ Node-3  │
  │10.0.0.1 │     │10.0.0.2 │     │10.0.0.3 │
  │宣告VIP │     │宣告VIP │     │宣告VIP │
  │权重 100 │     │权重 100 │     │权重 100 │
  └─────────┘     └─────────┘     └─────────┘

  ※ 三台同时持有 VIP,各自 BGP 宣告
  ※ 路由器 ECMP 选路,流量分散到 3 台
  ※ 任一节点挂,BGP 路由收敛,自动绕开
```

**关键点**:

- **Anycast**:同一 IP 在多地同时宣告,客户端"最近"接入
- **ECMP**(Equal-Cost Multi-Path):路由器同时看到多条等价路由,**并发**分发流量
- **BGP**:动态宣告路由,节点挂时自动撤销
- **无单点**:3 节点同时服务,资源利用率 ≈ 100%

### 11.3 与 VRRP 对比

| 维度 | VRRP/Keepalived | BGP Anycast + ECMP |
|------|------------------|---------------------|
| 节点利用率 | 1 节点(主) | **N 节点同时** |
| 切换时间 | 3-5 秒 | **亚秒(BGP 收敛)** |
| 流量分发 | 主备,主独占 | **ECMP 并发** |
| 跨地域 | ❌ | **✅** |
| 配置复杂度 | 低 | 中(需路由协议基础) |
| 适用规模 | 2-10 节点 | **10-100+ 节点** |
| 适用场景 | 中小规模入口 | CDN / DNS / 边缘节点 |

### 11.4 BIRD 配置示例(节点侧)

```
# /etc/bird/bird.conf

router id 10.0.0.1;

protocol device {
    scan time 10;
}

protocol direct {
    interface "lo";
}

# BFD 加速
protocol bfd {
    interface "eth0" {
        min_rx_interval 50ms;
        min_tx_interval 50ms;
        multiplier 3;
    };
    neighbor 10.0.0.254 as 65001;   # 对端路由器 IP
}

# BGP 宣告 VIP
protocol bgp my_as {
    local as 65001;
    neighbor 10.0.0.254 as 65001;   # 与上游路由器建立 iBGP / eBGP
    bfd on;                          # 启用 BFD

    export where net ~ [ 10.0.0.100/32 ];

    import all;
}
```

**所有节点同一份配置**,只改 `router id` 与本机 IP。

### 11.5 上游路由器(ECMP 入口)

#### Cisco IOS

```
router bgp 65001
 neighbor 10.0.0.1 remote-as 65001
 neighbor 10.0.0.2 remote-as 65001
 neighbor 10.0.0.3 remote-as 65001
 maximum-paths 8                    ! 启用 ECMP(最多 8 条等价路径)
 !
 ip route 10.0.0.100 255.255.255.255 Null0   ! 黑洞路由防环路
```

#### FRR(开源路由套件)

```conf
! /etc/frr/frr.conf
router bgp 65001
 neighbor anycast peer-group
 neighbor anycast remote-as 65001
 neighbor 10.0.0.1 peer-group anycast
 neighbor 10.0.0.2 peer-group anycast
 neighbor 10.0.0.3 peer-group anycast
 !
 address-family ipv4 unicast
  maximum-paths 8
  network 10.0.0.100/32
 exit-address-family
```

### 11.6 健康检查与自动撤销

**节点自身的健康检查**:

```bash
#!/bin/bash
# /usr/local/bin/health_to_bgp.sh
# 节点健康时宣告 VIP,异常时撤销

VIP="10.0.0.100"

if check_app_is_healthy; then
    # 健康 → 宣告 VIP
    birdc "configure soft" <<EOF
        route $VIP/32 via "lo";
        protocol bgp my_as {
            export where net ~ [ $VIP/32 ];
        }
EOF
else
    # 异常 → 撤销
    birdc "configure soft" <<EOF
        route $VIP/32 via "lo" reject;
        protocol bgp my_as {
            export where net ~ [ 0.0.0.0/0 ];
        }
EOF
fi
```

**`systemd` 守护**:

```ini
# /etc/systemd/system/health-bgp.service
[Unit]
Description=Health check → BGP route announcement
After=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/health_to_bgp.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 11.7 典型部署架构

```text
                     ┌──────────┐
                     │  DNS     │
                     │ (anycast)│
                     └────┬─────┘
                          │
                          ▼
       ┌──────────────────────────────────┐
       │ 跨地域 PoP                       │
       │  ├─ 香港 PoP(Anycast VIP)       │
       │  │   ├─ Node-1, Node-2, Node-3  │
       │  ├─ 上海 PoP                    │
       │  │   ├─ Node-1, Node-2, Node-3  │
       │  └─ 东京 PoP                    │
       │      ├─ Node-1, Node-2, Node-3  │
       └──────────────────────────────────┘
```

- **同一 VIP**(e.g., 1.1.1.1)在多个 PoP 同时宣告
- DNS 解析 + BGP 路由,**客户端从最近 PoP 接入**
- 任一 PoP 任一节点挂,BGP 路由自动收敛

### 11.8 选型决策

| 场景 | 推荐方案 |
| ---- | -------- |
| 2-3 节点、同机房、Nginx HA | **Keepalived/VRRP** |
| 4-10 节点、内网入口 | Keepalived + unicast |
| 10+ 节点 / CDN / 跨地域 | **BGP Anycast + ECMP + BFD** |
| 极致低延迟(< 100ms 切换) | BGP Anycast + BFD 50ms |
| 公有云环境 | 云厂商 LB + API(Keepalived 受限) |

**两者结合**:Keepalived 负责**小集群 HA**,BGP Anycast 负责**跨集群流量调度**。

---

## 12. 三种方案切换速度对比

### 12.1 三种方案概述

| 方案 | 核心机制 | 关键组件 |
| ---- | -------- | -------- |
| **纯 Keepalived** | VRRP 协议 + 优先级选举 | keepalived + VIP |
| **Keepalived + BFD** | VRRP + 毫秒级链路检测 | keepalived + BFD 守护 |
| **BGP Anycast + ECMP** | 多节点同时宣告 + 路由收敛 | BIRD / FRR + 路由器 ECMP |

### 12.2 切换速度矩阵

| 维度 | 纯 Keepalived | Keepalived + BFD | BGP Anycast + ECMP |
|------|---------------|-------------------|---------------------|
| **检测周期** | advert_int 默认 **1s** | BFD 默认 **50ms**(可到 10ms) | BGP 5s keepalive / 15s hold |
| **检测次数** | 3 × advert_int | 3 × BFD interval | 3 × hold-time |
| **检测耗时** | **~3s** | **~150ms**(50ms×3) | **~45s**(15s×3 默认) |
| **检测可调到** | 200ms × 3 ≈ 600ms | **30-50ms**(生产经验值) | **BFD 50ms** 加速后可到亚秒 |
| **抢占有 skew** | skew_time(几十 ms)| 几乎无 skew | 不存在切换(路由刷新) |
| **VIP 转移** | GARP 广播(瞬间) | GARP 广播(瞬间) | 不需要(无 VIP 切换) |
| **客户端感知** | 切换窗口 **~3-5s** | **~200ms** | **~0**(流量被路由器分走) |
| **完整切换时间** | **3-5s** | **200-500ms** | **亚秒**(BFD 加速后)<br>**数秒-分钟**(纯 BGP) |
| **DNS / 缓存影响** | 无 | 无 | TTL 内有缓存 |
| **跨地域切换** | ❌ | ❌ | **✅(Anycast 自动就近)** |

### 12.3 时间线对比(节点 A 挂掉,A 停止响应 → 客户端恢复)

#### 纯 Keepalived

```text
T+0ms    节点 A 宕机(网卡 / 进程 / 整机)
T+0ms    B 仍在收 B 的 advert(每隔 1s)
T+3000ms B 连续 3 个 advert 周期没收到 A
T+3000ms+skew  B 升级为 Master
T+3000ms+skew+GARP  B 发送免费 ARP 更新 VIP-MAC
T+3000ms+skew+GARP+客户端刷新 ARP 客户端切到 B
                    ─────────────
                    客户端感知窗口: ~3-5s
                    ※ 中间流量的 TCP 连接全部超时重连
```

#### Keepalived + BFD

```text
T+0ms    节点 A 宕机
T+0ms    BFD 在 50ms 间隔探测 A(双向 UDP 3784)
T+150ms  BFD 判定 A 不可达(3 × 50ms)
T+150ms  vrrp_script 触发,priority -= 100 → 立即让出
T+200ms  B 升级 Master,发 GARP
T+300ms  客户端 ARP 刷新,切到 B
         ─────────────
         客户端感知窗口: ~200-500ms
         ※ 已有 TCP 连接半数能超时重连,不丢业务
```

#### BGP Anycast + ECMP(纯 BGP)

```text
T+0ms    节点 A 宕机
T+0ms    上游路由器 BGP keepalive 探测 A(默认 60s)
T+0ms    路由器没收到 A 的 BGP 路由更新,但 hold-time 还没到
T+45000ms 路由器 hold-time 到期(15s × 3)
T+45000ms 路由器从 FIB 删除 A 的下一跳
T+45000ms 流量自动转到剩余节点(B / C)
          ─────────────
          客户端感知窗口: 0(无感知)
          但路由器侧检测慢(~45s)
          ※ TCP 连接不会断,只是路由变了
```

#### BGP Anycast + ECMP + BFD(推荐)

```text
T+0ms    节点 A 宕机
T+150ms  BFD 50ms × 3 = 150ms 检测到 A 不可达
T+150ms  BIRD / FRR 撤销 A 的 BGP 路由
T+200ms  路由器 BGP 更新生效(IETF 厂商实现 100-500ms)
T+300ms  流量完全切走,客户端无感
         ─────────────
         客户端感知窗口: ~0
         切换时间: ~300ms
```

### 12.4 性能与资源开销

| 方案 | 切换速度 | 节点利用率 | 网络开销 | 配置复杂度 |
|------|----------|-----------|---------|------------|
| **纯 Keepalived** | 3-5s | 1/N(其余待命) | 多播 / 单播心跳 | **低** |
| **Keepalived + BFD** | 200-500ms | 1/N | 心跳 + BFD UDP | 中 |
| **BGP Anycast + ECMP** | 亚秒-数十秒 | **100%(全活)** | BGP 路由(5-15s) | 高(需路由协议) |
| **BGP + ECMP + BFD** | **~300ms** | **100%** | BGP + BFD UDP | **高** |

### 12.5 选型推荐

```text
                    切换速度需求
                 ┌──────────────────────────────────┐
                 │                                  │
              低 │  纯 Keepalived     │ Keepalived + BFD │
                 │   (Web / API)      │  (金融 / 实时)   │
                 │                                  │
                 ├──────────────────────────────────┤
                 │                                  │
              高 │       BGP Anycast + ECMP + BFD   │
                 │   (CDN / DNS / 边缘 PoP)         │
                 │                                  │
                 └──────────────────────────────────┘
                  2-3 节点          4-10 节点      10+ 节点
                              节点规模
```

### 12.6 决策速查表

| 你的需求 | 推荐 |
| -------- | ---- |
| 2-3 节点 Nginx HA,容忍 3-5s 中断 | **纯 Keepalived** |
| 4-10 节点内网,要求 < 500ms 切换 | **Keepalived + BFD** |
| 10+ 节点,要求无切换(亚秒) | **BGP Anycast + ECMP + BFD** |
| 跨地域多 PoP | **BGP Anycast + ECMP**(BFD 可选) |
| 公有云环境 | 云厂商 LB(自建受限) |

**核心权衡**:

- 切换越快 → 复杂度越高 / 依赖越多(路由协议 / 网络设备配合)
- 节点越多 → 单点切换越不合适 → Anycast + ECMP 优势越大
- 跨地域 → VRRP 无解,只能 BGP Anycast
