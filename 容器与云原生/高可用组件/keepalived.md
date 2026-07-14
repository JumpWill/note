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