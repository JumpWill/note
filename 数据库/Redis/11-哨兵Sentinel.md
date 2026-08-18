# 哨兵 Sentinel

> 本章覆盖 Redis Sentinel 的完整知识体系:为什么需要 Sentinel、Sentinel 的三大任务、Sentinel 集群架构、主观下线(SDOWN)与客观下线(ODOWN)的判定机制、Leader 选举与选主规则、完整故障转移时序、客户端如何连接 Sentinel、动态配置与 API 命令、常见的脑裂问题与应对、Docker Compose 部署实战,以及 Sentinel 与 Cluster 的对比取舍。

---

## 一、Sentinel 概述

### 1. 什么是 Sentinel

**Redis Sentinel**(哨兵)是 Redis **官方**自 2.8 版本开始提供的高可用(High Availability)解决方案。它在 Redis 主从复制(replication)的基础上,提供**自动故障检测、自动故障转移、自动配置推送**三大核心能力,使得客户端在主节点宕机时无需人工介入,自动切换到新的主节点继续对外服务。

```text
                      Sentinel 集群
                   ┌──────────────────────┐
                   │  Sentinel-1 (Leader) │
                   │  Sentinel-2          │
                   │  Sentinel-3          │
                   └──────────┬───────────┘
                              │ 监控 / 仲裁 / 切换
                              ▼
              ┌──────── Master ────────┐
              │      redis-6379        │
              └──────┬────────┬────────┘
              复制 ▲          ▲ 复制
                  │          │
              ┌───┴──┐    ┌───┴──┐
              │6378  │    │6377  │
              │ Slave│    │ Slave│
              └──────┘    └──────┘
```

### 2. 为什么需要 Sentinel

在"主从复制"模式下,主节点一旦宕机,从节点虽然可以继续提供**读**服务,但**写**操作只能人工切换 IP:

```text
  没有 Sentinel 时:
  Client ──写──► Master(6379) 挂了 ✗
                            │
                            ▼
              运维同学手动:把 Slave-6378 升级为新 Master
              通知所有 Client 改 IP ── 业务中断 5~30 分钟
```

引入 Sentinel 之后,这个过程被**自动化**了:检测、决策、切换、通知,**秒级完成**。

### 3. Sentinel 与主从复制的边界

| 能力 | 主从复制 | Sentinel |
|------|----------|----------|
| 数据冗余 | ✔ | ✔(继承自复制) |
| 读写分离 | ✔ | ✔ |
| **自动故障检测** | ✘ | ✔ |
| **自动故障转移** | ✘ | ✔ |
| **客户端配置发现** | ✘ | ✔ |
| 数据分片 | ✘ | ✘(Cluster 才行) |

> **重要边界**:Sentinel 只解决"**单组主从的高可用**",不解决"**数据水平扩展**"。当数据量 > 单机内存(几十 GB),仍需 Redis Cluster。

---

## 二、Sentinel 三大任务

Sentinel 在 Redis 官方文档中被概括为**三大任务**,也常被扩展为四大功能:

### 1. 监控(Monitoring)

Sentinel 以**每秒一次**的频率向所有被监控的主节点、从节点以及其他 Sentinel 发送 `PING` 命令,根据响应判断节点是否在线。

```text
   Sentinel-1 ──── PING ────► Master
             ◄─── PONG ────
             ──── PING ────► Slave-1
             ──── PING ────► Slave-2
             ──── PING ────► Sentinel-2
             ──── PING ────► Sentinel-3
```

### 2. 通知(Notification)

当被监控的 Redis 实例出现故障时,Sentinel 可以通过 **API**(如脚本、监控系统)向系统管理员或应用发送告警。Sentinel 自身不直接发邮件/短信,而是提供了 `notification-script` 钩子,由外部脚本完成报警动作。

```bash
# sentinel.conf
sentinel notification-script mymaster /usr/local/bin/sentinel_alert.sh
```

### 3. 自动故障转移(Automatic Failover)

这是 Sentinel **最核心**的能力:当主节点被判定客观下线后,Sentinel 集群会通过 Raft-like 算法选举出一个 **Leader Sentinel**,由 Leader 负责从从节点中挑选一个**最优**的提升为新主,完成切换。

### 4. 配置提供者(Configuration Provider)

客户端不再硬编码主节点地址,而是**先连 Sentinel**,Sentinel 告诉客户端"当前主是哪个"。客户端订阅 Sentinel 的 `+switch-master` 频道,实现**主节点变更的实时感知**。

```text
  Client ──► Sentinel: GET-MASTER-ADDR-BY-NAME mymaster
         ◄─ {192.168.1.10, 6379}
  Client ──► 192.168.1.10:6379 (读写)

  若发生切换:
  Sentinel: PUBLISH +switch-master mymaster 192.168.1.10:6379 192.168.1.11:6378
  Client 收到后自动重连到新主
```

---

## 三、Sentinel 架构

### 1. 部署建议

| 部署要求 | 说明 |
|----------|------|
| **至少 3 个 Sentinel** | 保证少数派机制有效,避免脑裂 |
| **奇数个节点** | 1/3/5/7,投票时可形成多数派 |
| **跨机器部署** | 不能都放同一台物理机,否则单点失效 |
| **客户端连所有 Sentinel** | 客户端任选其一即可,平时只读,故障时获取最新主 |
| **独立机器或容器** | 与 Redis 数据节点**错开部署**,避免资源争抢 |

### 2. 典型架构图

```text
                    ┌─────────────────────────────┐
                    │     Redis Sentinel 集群      │
                    │                              │
                    │  ┌───────────┐               │
                    │  │ Sentinel-1│ 192.168.1.20  │
                    │  └─────┬─────┘               │
                    │        │ PING / INFO / PUB   │
                    │  ┌─────┴─────┐               │
                    │  │ Sentinel-2│ 192.168.1.21  │
                    │  └─────┬─────┘               │
                    │        │                     │
                    │  ┌─────┴─────┐               │
                    │  │ Sentinel-3│ 192.168.1.22  │
                    │  └───────────┘               │
                    └──────────┬──────────────────┘
                               │ 监控
                               ▼
        ┌──────────────────────────────────────────────┐
        │                Redis 数据节点                 │
        │                                              │
        │   ┌──────────────┐                           │
        │   │   Master     │ 192.168.1.10:6379        │
        │   └──────┬───────┘                           │
        │          │ PSYNC / 命令传播                  │
        │   ┌──────┴───────┐    ┌──────────────┐       │
        │   │   Slave-1    │    │   Slave-2    │       │
        │   │ 1.11:6378    │    │ 1.12:6377    │       │
        │   └──────────────┘    └──────────────┘       │
        └──────────────────────────────────────────────┘
                               ▲
                               │ 连接(订阅 +switch-master)
        ┌──────────────────────┴───────────────────────┐
        │                  Client 集群                  │
        │   App-1, App-2, App-3 (各自连接任一 Sentinel) │
        └──────────────────────────────────────────────┘
```

### 3. Sentinel 进程本身

Sentinel 只是一个**特殊的 Redis 进程**,只不过它不存储业务数据,只跑 Sentinel 逻辑。可以使用 `redis-sentinel` 启动,也可以直接用 `redis-server --sentinel` 启动。

```bash
# 两种启动方式等价
redis-sentinel /path/to/sentinel.conf
redis-server /path/to/sentinel.conf --sentinel
```

---

## 四、Sentinel 启动与基础配置

### 1. 最简启动命令

```bash
# 前台启动(调试用)
redis-sentinel sentinel.conf

# 后台启动(推荐)
redis-sentinel sentinel.conf --daemonize yes
```

### 2. 最核心的配置项

```bash
# sentinel.conf —— 监控一个名为 mymaster 的主节点
# 192.168.1.10:6379 是主节点地址
# 2 是 quorum(至少 2 个 Sentinel 认为主下线,才触发客观下线)
sentinel monitor mymaster 192.168.1.10 6379 2
```

`sentinel monitor` 四要素:

| 参数 | 含义 |
|------|------|
| `mymaster` | 主节点逻辑名,客户端按此名发现主 |
| `192.168.1.10` | 主节点 IP |
| `6379` | 主节点端口 |
| `2` | quorum 阈值(至少 N 票才认为客观下线) |

### 3. 启动日志解读

```text
+monitor master mymaster 192.168.1.10 6379 quorum 2
+slave slave 192.168.1.11:6378 192.168.1.10 6379 @ mymaster
+slave slave 192.168.1.12:6377 192.168.1.10 6379 @ mymaster
+sentinel sentinel 192.168.1.21:26379 192.168.1.21 26379 @ mymaster
+sentinel sentinel 192.168.1.22:26379 192.168.1.22 26379 @ mymaster
```

---

## 五、主观下线 SDOWN 与客观下线 ODOWN

Sentinel 的下线判定分**两层**:SDOWN(Subjectively Down)由单个 Sentinel 独立判定;ODOWN(Objectively Down)由 Sentinel 集群**多数派**共同确认。

### 1. 主观下线 SDOWN(Subjectively Down)

- **判定主体**:单个 Sentinel
- **判定条件**:在 `down-after-milliseconds` 时间内(默认 30 秒)**未收到**该节点的有效回复(`PING` 超时或响应非法)
- **粒度**:仅 Sentinel 自己知道,**不影响**其他 Sentinel

```text
  Sentinel-1:
  ───► PING Master
       (等待 PONG 或 LOADING/MASTERDOWN 之外的有效响应)
       超时 30s ───► SDOWN
```

```bash
# 配置超时阈值
sentinel down-after-milliseconds mymaster 30000
```

### 2. 客观下线 ODOWN(Objectively Down)

- **判定主体**:Sentinel **集群**
- **判定条件**:有 **quorum 个** Sentinel 都认为该主节点 SDOWN
- **影响**:一旦 ODOWN,Sentinel 集群进入**故障转移流程**

```text
  Sentinel-1: SDOWN mymaster
  Sentinel-2: SDOWN mymaster
  Sentinel-3: OK    mymaster
  ────────
  quorum = 2,已达到 ──► ODOWN mymaster
  ────────
  Sentinel-1、2 准备推举 Leader
```

### 3. quorum 与 majority 的关系

```text
  Sentinel 数量 N = 3
  quorum      = 2   (配置值,sentinel monitor 中的最后一位)
  majority    = 2   (N/2 + 1,即 ⌊3/2⌋ + 1 = 2)

  Sentinel 数量 N = 5
  quorum      = 3
  majority    = 3

  Sentinel 数量 N = 2
  quorum      = 1
  majority    = 2   ⚠️ 不存在多数派,部署不可取!
```

> **关键陷阱**:N=2 时不存在多数派(任何 1 个 Sentinel 都无法独占多数),因此 **Sentinel 至少 3 个** 是官方强建议。

### 4. SDOWN/ODOWN 状态转换

```text
              PONG / INFO
  SDOWN ────────────────────► 正常
    ▲                            │
    │  超时 down-after-ms        │
    │                            ▼
  SDOWN ── quorum 票 ──► ODOWN ── 故障转移成功 ──► SDOWN 解除
```

---

## 六、故障转移完整流程

故障转移是 Sentinel 的**核心动作**,全过程涉及"**判定 → 选 Leader → 选从 → 切换 → 通知**"五个阶段。

### 1. 故障转移时序图(ASCII)

```text
     Sentinel-1     Sentinel-2     Sentinel-3       Master          Slave-1        Slave-2
        │               │               │              │                │              │
        │  PING 超时     │               │              │                │              │
        │ SDOWN          │               │              │                │              │
        ├───────────────►│               │              │                │              │
        │ is-master-down-by-addr         │              │                │              │
        ├───────────────►│               │              │                │              │
        │                │ SDOWN(投票)    │              │                │              │
        │                ├───────────────►│              │                │              │
        │                │ is-master-down-by-addr       │                │              │
        │                ├───────────────►│              │                │              │
        │                │               │ SDOWN(投票)  │                │              │
        │                │◄──────────────┤              │                │              │
        │◄───────────────┤               │              │                │              │
        │  quorum 已达 ───► ODOWN        │              │                │              │
        │                │               │              │                │              │
        │  选举 Leader(Raft 简化版)      │              │                │              │
        ├───────────────►│  投票给我      │              │                │              │
        │                ├───────────────►│  投票给我    │                │              │
        │◄───────────────┤               │              │                │              │
        │                │  获得多数票 →  │              │                │              │
        │                │  成为 Leader   │              │                │              │
        │                │               │              │                │              │
        │                │ SLAVES of mymaster            │                │              │
        │                ├─────────────────────────────►│                │              │
        │                │               │              │ INFO           │              │
        │                │               │              ├───────────────►│              │
        │                │               │              │◄─── role=slave,offset ────────►│
        │                │ 评估从节点    │              │                │              │
        │                │  1.replica-priority           │                │              │
        │                │  2.repl_offset                │                │              │
        │                │  3.runid 字典序               │                │              │
        │                │               │              │                │              │
        │                │ SLAVEOF NO ONE                │                │              │
        │                ├─────────────────────────────►│                │              │
        │                │               │              │ OK              │              │
        │                │               │              │ 提升为 Master   │              │
        │                │               │              │                │              │
        │                │ SLAVEOF <new-master>           │                │              │
        │                ├─────────────────────────────────────────────►│              │
        │                ├────────────────────────────────────────────────────────────►│
        │                │               │              │                │ PSYNC        │
        │                │               │              │                │              │
        │                │ PUBLISH +switch-master mymaster old:6379 new:6378              │
        │                ├────────────────────────────────────────────────────────────►Client
        │                │               │              │                │              │
        │                │ 故障转移完成,等待 next failover-timeout 才允许下次切换            │
```

### 2. 阶段详解

| 阶段 | 动作 | 关键配置 |
|------|------|----------|
| ① SDOWN | 单 Sentinel 探测 ping 超时 | `down-after-milliseconds` |
| ② ODOWN | quorum 个 Sentinel 达成共识 | `quorum` |
| ③ Leader 选举 | 各 Sentinel 发起 Raft 投票 | `failover-timeout` |
| ④ 选从 | 评估从节点的 priority / offset / runid | `replica-priority` |
| ⑤ 切换 | `SLAVEOF NO ONE` + `SLAVEOF new` | — |
| ⑥ 通知 | `PUBLISH +switch-master` | client subscribe |
| ⑦ 配置更新 | Leader 写新主配置到所有 Sentinel | — |

### 3. 关键命令时序

```text
Sentinel-1 (Leader) 与 Redis 节点的命令交互:

  1) Sentinel → Master: SUBSCRIBE +switch-master   (持续订阅)
  2) Sentinel → Master: SLAVEOF NO ONE            (让目标从升主)
  3) Sentinel → Master: CONFIG SET maxmemory-policy noeviction  (升主前临时禁止淘汰)
  4) Sentinel → Master: INFO replication          (确认 role=master)
  5) Sentinel → 其他 Slave: SLAVEOF <new-master>  (让它们指向新主)
  6) Sentinel → Master: PUBLISH +switch-master <name> <old> <new>
  7) Sentinel → 其他 Sentinel: 更新本地 master 配置
```

---

## 七、Leader 选举(Raft 算法简化版)

Sentinel 的 Leader 选举本质上是 **Raft 共识算法** 的简化实现,但又不完全等同 Raft。

### 1. 选举规则

```text
  1. 当一个 Sentinel 检测到主节点 ODOWN 后,该 Sentinel 成为 Candidate
  2. Candidate 向所有其他 Sentinel 发送:
     SENTINEL is-master-down-by-addr <ip> <port> <currentEpoch> <runid>
       - runid = "*"   :仅询问"是否同意下线"
       - runid = 自身  :发起投票,请求成为 Leader
  3. 收到请求的 Sentinel 在同一 epoch 内只能投一次,且先到先得
  4. Candidate 获得 quorum 票即成为 Leader
  5. 若一轮无结果,等待随机超时(类似 Raft),下一轮重新选举
```

### 2. epoch(配置纪元)的作用

- 每个 Sentinel 启动时 `currentEpoch = 0`
- 每次选举完成后,epoch **单调递增**
- 旧 epoch 的请求会被新 epoch 的 Sentinel 拒绝,避免"老僵尸消息"作乱
- 类比 Raft 的 **term(任期)**

```text
  epoch = 5   ──► 一次未选出 Leader
  epoch = 6   ──► Sentinel-2 当选 Leader
  epoch = 6 期间所有指令都带 epoch=6
```

### 3. Raft 与 Sentinel Leader 的差异

| 维度 | Raft | Sentinel |
|------|------|----------|
| 选举触发 | 心跳超时 | 主节点 ODOWN |
| 投票限制 | 同一 term 一票 | 同一 epoch 一票 |
| 日志复制 | 强一致日志同步 | **不复制**,仅推配置 |
| 数据安全 | 选主需日志最新 | 选主靠 replica-priority/offset |

---

## 八、选主规则(Slave Selection)

当 Leader Sentinel 决定开始故障转移,需要从从节点中**挑一个最好的**升为主。Redis 5.0 起该流程被详细记录于 Sentinel 源码 `selectSlaveOfMymasterForFailover()`。

### 1. 选主流程图

```text
            ┌────────────────────────────┐
            │ 候选从节点列表 SlaveList    │
            └─────────────┬──────────────┘
                          │
            ┌─────────────▼──────────────┐
            │ 步骤1:过滤不健康从节点      │
            │ - 已下线 / 主观下线         │
            │ - 最近 down-after * 10 ms  │
            │   内被判定下线过             │
            │ - 与主失联 > 一定时间       │
            └─────────────┬──────────────┘
                          │ 剩下健康从节点
                          ▼
            ┌────────────────────────────┐
            │ 步骤2:按 replica-priority │
            │ 升序排序,挑最小者           │
            │ (默认所有从节点都是 100)    │
            └─────────────┬──────────────┘
                          │ priority 相同?
                          ▼
            ┌────────────────────────────┐
            │ 步骤3:按 repl_offset 降序  │
            │ (复制偏移越大 = 数据越新)   │
            └─────────────┬──────────────┘
                          │ offset 相同?
                          ▼
            ┌────────────────────────────┐
            │ 步骤4:按 runid 字典序      │
            │ 挑最小者(runid 随机生成)    │
            └─────────────┬──────────────┘
                          │
                          ▼
            ┌────────────────────────────┐
            │ 选定新主:Sentinel 发送     │
            │ SLAVEOF NO ONE 命令         │
            └────────────────────────────┘
```

### 2. replica-priority 实战

```bash
# 在从节点的 redis.conf 中配置
replica-priority 100    # 默认值,数字越小优先级越高

# 把 192.168.1.11 设为"最优先升主"对象
# 在该从节点本机配置:
replica-priority 10

# 不希望某节点升主(比如专用于备份/BI)
replica-priority 0
```

> **注意**:`replica-priority 0` 表示 Sentinel **永远不会选它升主**,适合"只读副本"。

### 3. 三种选主依据对比

| 依据 | 含义 | 调整方式 |
|------|------|----------|
| `replica-priority` | 运维意图,人为指定优先级 | `replica-priority N` |
| `repl_offset` | 复制偏移量,数据新鲜度 | 取决于主从延迟,无法直接调整 |
| `runid` | 随机生成的 40 位 hex 串 | 每次重启变化 |

### 4. 健康检查窗口

```text
从节点在最近 down-after-milliseconds * 10 毫秒内
曾被 Sentinel 标记为下线 → 即使后续恢复,本次故障转移也不会选它。

  down-after-milliseconds = 30000
  健康窗口 = 300s
  在 300s 内下线的从节点 → 排除
```

---

## 九、Sentinel 配置文件详解

### 1. 完整 sentinel.conf 模板

```bash
# ============================================================
# Redis Sentinel 完整配置模板
# 适用版本:Redis 6.x / 7.x
# ============================================================

# Sentinel 工作端口(默认 26379,区别于 Redis 6379)
port 26379

# 是否后台运行
daemonize yes

# 日志文件
logfile "/var/log/redis/sentinel.log"

# 工作目录
dir "/var/lib/redis-sentinel"

# 启用保护模式(默认 yes,无密码时禁止外网访问)
protected-mode yes

# ============================================================
# 核心:监控主节点
# 格式: sentinel monitor <master-name> <ip> <port> <quorum>
# ============================================================
sentinel monitor mymaster 192.168.1.10 6379 2

# 主节点认证密码(若主从开启了 requirepass)
sentinel auth-pass mymaster your-strong-password

# ============================================================
# 健康判定与超时
# ============================================================

# 多少毫秒未响应 PING 即认为 SDOWN(默认 30000)
sentinel down-after-milliseconds mymaster 30000

# 故障转移超时,默认 180000ms(3 分钟)
# 在此时间内若转移未完成,会被认为失败
sentinel failover-timeout mymaster 180000

# ============================================================
# 并行同步
# ============================================================

# 同时对新主进行同步的从节点数(默认 1)
# 设为 1 = 一个一个同步,降低主压力
# 设为 N = N 个从并行同步,加速收敛但增加主压力
sentinel parallel-syncs mymaster 1

# ============================================================
# 通知脚本(主/从/哨兵告警时触发)
# ============================================================

# 实例故障/恢复时触发
sentinel notification-script mymaster /usr/local/bin/sentinel_alert.sh

# 故障转移结束后触发(可清理 VIP、摘流等)
sentinel client-reconfig-script mymaster /usr/local/bin/sentinel_reconfig.sh

# ============================================================
# 安全
# ============================================================
# Sentinel 自身的 requirepass(Redis 6.2+ 支持 ACL)
requirepass sentinel-strong-pass

# ============================================================
# 优化(可选)
# ============================================================

# 关闭 INFO 输出中部分字段,减小带宽
sentinel announce-ip "192.168.1.20"

# TCP 监听 backlog
tcp-backlog 511

# 客户端连接空闲超时
timeout 0

# 慢日志阈值
slowlog-log-slower-than 10000
slowlog-max-len 128
```

### 2. 动态配置:SENTINEL SET 命令

Sentinel 的所有参数都支持**运行时动态修改**——无需重启 Sentinel。

```bash
# 通过 Sentinel 本地连接修改
redis-cli -p 26379

# 修改 quorum
127.0.0.1:26379> SENTINEL SET mymaster quorum 3
OK

# 修改主节点认证密码(主节点刚改了密码)
127.0.0.1:26379> SENTINEL SET mymaster auth-password your-new-password
OK

# 修改 down-after-milliseconds
127.0.0.1:26379> SENTINEL SET mymaster down-after-milliseconds 5000
OK

# 主动触发一次故障转移(运维演练)
127.0.0.1:26379> SENTINEL FAILOVER mymaster
OK
```

> **生产建议**:绝大多数配置变更建议通过配置文件 + 重启,只有"主节点密码变更""紧急切换演练"等场景才用 `SENTINEL SET`。

---

## 十、客户端连接 Sentinel

业务侧必须正确感知 Sentinel 才能享受到高可用。常见三大 Java 客户端:**Jedis**、**Lettuce**、**Spring Data Redis**。

### 1. Jedis SentinelPool

```java
import redis.clients.jedis.JedisPoolConfig;
import redis.clients.jedis.JedisSentinelPool;

import java.util.HashSet;
import java.util.Set;

public class JedisSentinelExample {

    public static void main(String[] args) {
        // 1. Sentinel 地址集合(任写一个或全部都行)
        Set<String> sentinels = new HashSet<>();
        sentinels.add("192.168.1.20:26379");
        sentinels.add("192.168.1.21:26379");
        sentinels.add("192.168.1.22:26379");

        // 2. 连接池配置
        JedisPoolConfig poolConfig = new JedisPoolConfig();
        poolConfig.setMaxTotal(200);
        poolConfig.setMaxIdle(50);
        poolConfig.setMinIdle(10);
        poolConfig.setTestOnBorrow(true);

        // 3. 创建 Sentinel 连接池
        JedisSentinelPool pool = new JedisSentinelPool(
                "mymaster",      // 主节点逻辑名
                sentinels,       // Sentinel 列表
                poolConfig,
                2000,            // 连接超时 ms
                2000,            // 读写超时 ms
                "redis-pass",    // 主节点密码(可选)
                0                // database 默认 0
        );

        try (Jedis jedis = pool.getResource()) {
            jedis.set("user:1001", "{\"name\":\"will\"}");
            String value = jedis.get("user:1001");
            System.out.println("value = " + value);
        } finally {
            pool.close();
        }
    }
}
```

**底层流程**:

```text
  应用启动
     │
     ▼
  JedisSentinelPool 初始化:订阅 Sentinel 的 +switch-master 频道
     │
     ▼
  调用 pool.getResource():
     │
     ├──► 随机选一个 Sentinel 询问 GET-MASTER-ADDR-BY-NAME mymaster
     │   返回 192.168.1.10:6379
     │
     ▼
  建立到 192.168.1.10:6379 的连接(普通 JedisPool)
     │
     ▼
  若收到 +switch-master 消息:连接池内部销毁旧连接,下次 getResource() 自动连新主
```

### 2. Lettuce Sentinel 连接

```java
import io.lettuce.core.RedisClient;
import io.lettuce.core.RedisURI;
import io.lettuce.core.api.StatefulRedisConnection;

import java.time.Duration;

public class LettuceSentinelExample {

    public static void main(String[] args) {
        // Lettuce 用 RedisURI.builder 构造 Sentinel URI
        RedisURI uri = RedisURI.builder()
                .withSentinel("192.168.1.20", 26379)   // 任选一个 Sentinel
                .withSentinel("192.168.1.21", 26379)
                .withSentinel("192.168.1.22", 26379)
                .withSentinelMasterId("mymaster")
                .withPassword("redis-pass".toCharArray())
                .withTimeout(Duration.ofSeconds(2))
                .build();

        RedisClient client = RedisClient.create(uri);
        StatefulRedisConnection<String, String> conn = client.connect();

        // 测试
        conn.sync().set("k1", "v1");
        System.out.println(conn.sync().get("k1"));

        // Lettuce 内置拓扑刷新,故障切换时自动重连
        conn.close();
        client.shutdown();
    }
}
```

### 3. Spring Data Redis 集成

```yaml
# application.yml
spring:
  redis:
    password: redis-pass
    sentinel:
      master: mymaster
      nodes:
        - 192.168.1.20:26379
        - 192.168.1.21:26379
        - 192.168.1.22:26379
    lettuce:
      pool:
        max-active: 200
        max-idle: 50
        min-idle: 10
      shutdown-timeout: 100ms
```

```java
@Configuration
public class RedisConfig {

    @Bean
    public RedisTemplate<String, String> redisTemplate(
            RedisConnectionFactory factory) {
        RedisTemplate<String, String> template = new RedisTemplate<>();
        template.setConnectionFactory(factory);
        // 使用 String 序列化(生产更推荐 Jackson2JsonRedisSerializer)
        template.setKeySerializer(new StringRedisSerializer());
        template.setValueSerializer(new StringRedisSerializer());
        return template;
    }
}
```

### 4. 客户端重连与失败重试建议

| 建议 | 说明 |
|------|------|
| 短超时 + 重试 | 命令超时设 200~500ms,失败 2~3 次 |
| 幂等操作 | SET/DEL/INCR 安全;非幂等(LPUSH/RPUSH)需业务重试时去重 |
| 失败即降级 | 缓存层允许短暂不可用,DB 回源 |
| 监控切换耗时 | 应用记录 `+switch-master` 收到时间 vs 业务首次失败时间 |

---

## 十一、Sentinel API 命令

### 1. 常用命令速查

| 命令 | 作用 |
|------|------|
| `SENTINEL MASTERS` | 列出所有被监控的主节点及其完整配置 |
| `SENTINEL MASTER <name>` | 查看指定主节点详情 |
| `SENTINEL SLAVES <name>` | 列出指定主节点的所有从节点 |
| `SENTINEL REPLICAS <name>` | 同 SLAVES,Redis 5+ 推荐用法 |
| `SENTINEL SENTINELS <name>` | 列出监控同一主节点的其他 Sentinel |
| `SENTINEL GET-MASTER-ADDR-BY-NAME <name>` | **客户端最常用**,返回当前主地址 |
| `SENTINEL FAILOVER <name>` | 强制触发一次故障转移(演练用) |
| `SENTINEL SET <name> <option> <value>` | 动态修改配置 |
| `SENTINEL CKQUORUM <name>` | 检查当前 quorum 是否能达成多数派 |
| `SENTINEL FLUSHCONFIG` | 把内存中的 Sentinel 配置写回磁盘 |
| `SENTINEL REMOVE <name>` | 移除监控 |
| `SENTINEL MONITOR <name> <ip> <port> <quorum>` | 添加监控 |

### 2. 实操示例

```bash
$ redis-cli -p 26379

# 1. 查询所有主节点
127.0.0.1:26379> SENTINEL MASTERS
1)  1) "name"
    2) "mymaster"
    3) "ip"
    4) "192.168.1.10"
    5) "port"
    6) "6379"
    7) "down-after-milliseconds"
    8) "30000"
    ...

# 2. 查询当前主地址
127.0.0.1:26379> SENTINEL GET-MASTER-ADDR-BY-NAME mymaster
1) "192.168.1.10"
2) "6379"

# 3. 列出从节点
127.0.0.1:26379> SENTINEL SLAVES mymaster
1)  1) "name"
    2) "192.168.1.11:6378"
    3) "ip"
    4) "192.168.1.11"
    5) "port"
    6) "6378"
    7) "role-reported"
    8) "slave"
    9) "slave-priority"
   10) "100"
   11) "master-repl-offset"
   12) "1234567"
   ...

# 4. 检查 quorum 合法性
127.0.0.1:26379> SENTINEL CKQUORUM mymaster
OK 3 usable Sentinels. Quorum and failover authorization can be reached

# 5. 强制切换(慎用)
127.0.0.1:26379> SENTINEL FAILOVER mymaster
OK
```

### 3. Pub/Sub 频道

客户端可订阅以下频道以实时感知 Sentinel 状态:

| 频道 | 内容 |
|------|------|
| `+switch-master` | 主节点发生切换 |
| `+sdown` | 节点进入 SDOWN |
| `-sdown` | 节点退出 SDOWN |
| `+odown` | 节点进入 ODOWN |
| `-odown` | 节点退出 ODOWN |
| `+reboot` | 节点重启 |

```bash
# 客户端订阅切换消息
redis-cli -p 26379 SUBSCRIBE +switch-master
```

---

## 十二、Sentinel 脑裂问题

### 1. 什么是脑裂

**脑裂(Split-Brain)**:在网络分区时,**两个子网络都认为自己是"主"**,各自对外提供写服务,导致数据双写、数据丢失。

```text
  正常情况:
  Client ──► Master(10.10.1.10) ──► Slave

  网络分区(机房之间断网):
  机房 A: Master(10.10.1.10) ──► Client 还能写    (Sentinel 看不到)
  机房 B: Sentinel ──► 触发切换 ──► Slave 升主 ──► Client 写另一个主

  结果:两个 Master 同时接受写请求 → 数据冲突
```

### 2. Redis 主从的脑裂场景

```text
                网络分区
  ┌─────────── 机房 A ───────────┐    ┌──── 机房 B ────┐
  │                              │    │                │
  │   Master(旧主)               │    │  Sentinel      │
  │   (与 Sentinel 失联)         │    │  判定 ODOWN     │
  │   仍在接受 Client 写入       │    │  Slave 升主     │
  │                              │    │  Client 写入新主│
  └──────────────────────────────┘    └────────────────┘
        网络恢复后:
        - 旧主发现自己是 slave(被降级)
        - 但它在分区期间写的 N 条数据未复制到新主 → 丢失
```

### 3. 应对策略

| 配置 | 作用 | 推荐值 |
|------|------|--------|
| `min-replicas-to-write 1` | 主节点必须至少有 1 个从在线,否则**拒绝写入** | 1 |
| `min-replicas-max-lag 10` | 主从延迟超过 10 秒,也拒绝写入 | 10 |

```bash
# redis.conf(主节点配置)
min-replicas-to-write 1
min-replicas-max-lag 10
```

### 4. 工作原理

```text
  正常时:
  Master 有 2 个从,lag 都 < 1s → 满足 min-replicas 条件 → 允许写入 ✓

  网络分区时(主与所有从失联):
  Master 找不到任何从节点 → 不满足 min-replicas-to-write=1
  → 主拒绝写入
  → Client 写入失败(虽然主还活着,但已经"自我保护")
  → Sentinel 在另一侧完成切换 → 新主对外服务

  网络恢复后:
  旧主发现自己变成 slave,把分区期间未复制的写入清掉
  → 不会发生脑裂双写
```

> **代价**:这种"自我保护"会让分区期间的写入全部失败,**牺牲可用性换一致性**——经典的 **AP→CP** 妥协。

---

## 十三、Sentinel vs Cluster 对比

| 维度 | Sentinel | Redis Cluster |
|------|----------|---------------|
| **目的** | 高可用(自动故障转移) | 数据分片 + 高可用 |
| **数据分布** | 全量复制,1 主 N 从 | 16384 槽分布到 N 主 |
| **容量上限** | 单机内存 | 多机水平扩展,理论无上限 |
| **写入能力** | 单主写入,无法水平扩展 | 多主并行写入 |
| **客户端复杂度** | 简单 | 需支持 MOVED/ASK 重定向 |
| **最少节点** | 1 主 + 1 从 + 3 Sentinel | 3 主 3 从 |
| **运维难度** | 中等 | 较高(槽迁移、reshard) |
| **适用场景** | 数据量 < 几十 GB,业务对写不敏感 | 数据量 > 几十 GB,写并发高 |
| **故障转移** | 自动 | 自动(每主独立) |
| **脑裂防护** | 依赖 min-replicas-* | 内置多数派投票 |

> **实战经验**:数据量小于 50GB、QPS < 10W 优先选 Sentinel;超过则选 Cluster 或同时部署("Cluster + Sentinel"组合也是合法方案,但 Sentinel 主要用于监控,主切换由 Cluster 自己处理)。

---

## 十四、Sentinel 部署实战(Docker Compose)

### 1. 目录结构

```text
redis-sentinel/
├── docker-compose.yml
├── sentinel/
│   ├── sentinel1.conf
│   ├── sentinel2.conf
│   └── sentinel3.conf
├── master/
│   └── redis.conf
├── slave1/
│   └── redis.conf
└── slave2/
    └── redis.conf
```

### 2. docker-compose.yml

```yaml
version: "3.8"

services:
  redis-master:
    image: redis:7.2
    container_name: redis-master
    ports:
      - "6379:6379"
    volumes:
      - ./master/redis.conf:/usr/local/etc/redis/redis.conf
    command: ["redis-server", "/usr/local/etc/redis/redis.conf"]

  redis-slave1:
    image: redis:7.2
    container_name: redis-slave1
    ports:
      - "6378:6379"
    volumes:
      - ./slave1/redis.conf:/usr/local/etc/redis/redis.conf
    command: ["redis-server", "/usr/local/etc/redis/redis.conf"]
    depends_on:
      - redis-master

  redis-slave2:
    image: redis:7.2
    container_name: redis-slave2
    ports:
      - "6377:6379"
    volumes:
      - ./slave2/redis.conf:/usr/local/etc/redis/redis.conf
    command: ["redis-server", "/usr/local/etc/redis/redis.conf"]
    depends_on:
      - redis-master

  sentinel1:
    image: redis:7.2
    container_name: sentinel1
    ports:
      - "26379:26379"
    volumes:
      - ./sentinel/sentinel1.conf:/usr/local/etc/redis/sentinel.conf
    command: ["redis-sentinel", "/usr/local/etc/redis/sentinel.conf"]
    depends_on:
      - redis-master
      - redis-slave1
      - redis-slave2

  sentinel2:
    image: redis:7.2
    container_name: sentinel2
    ports:
      - "26380:26379"
    volumes:
      - ./sentinel/sentinel2.conf:/usr/local/etc/redis/sentinel.conf
    command: ["redis-sentinel", "/usr/local/etc/redis/sentinel.conf"]
    depends_on:
      - sentinel1

  sentinel3:
    image: redis:7.2
    container_name: sentinel3
    ports:
      - "26381:26379"
    volumes:
      - ./sentinel/sentinel3.conf:/usr/local/etc/redis/sentinel.conf
    command: ["redis-sentinel", "/usr/local/etc/redis/sentinel.conf"]
    depends_on:
      - sentinel2
```

### 3. master/redis.conf

```bash
port 6379
daemonize no
requirepass redis-pass
masterauth redis-pass
appendonly yes
protected-mode no
min-replicas-to-write 1
min-replicas-max-lag 10
```

### 4. slave1/redis.conf / slave2/redis.conf

```bash
port 6379
daemonize no
requirepass redis-pass
masterauth redis-pass
replicaof redis-master 6379
appendonly yes
protected-mode no
```

### 5. sentinel{1,2,3}.conf(三份仅 IP 不同)

```bash
port 26379
daemonize no
dir /tmp
protected-mode no

# 监控主节点,quorum=2
sentinel monitor mymaster redis-master 6379 2
sentinel auth-pass mymaster redis-pass
sentinel down-after-milliseconds mymaster 5000
sentinel parallel-syncs mymaster 1
sentinel failover-timeout mymaster 30000

# Sentinel1: announce-ip 192.168.1.20
# Sentinel2: announce-ip 192.168.1.21
# Sentinel3: announce-ip 192.168.1.22
```

### 6. 启动与验证

```bash
cd redis-sentinel
docker-compose up -d

# 1. 查看 Sentinel 状态
docker exec -it sentinel1 redis-cli -p 26379 SENTINEL MASTERS

# 2. 验证从节点
docker exec -it sentinel1 redis-cli -p 26379 SENTINEL SLAVES mymaster

# 3. 模拟主节点宕机
docker stop redis-master

# 4. 观察 Sentinel 日志(30 秒内自动切换)
docker logs -f sentinel1

# 5. 查看新主
docker exec -it sentinel2 redis-cli -p 26379 \
    SENTINEL GET-MASTER-ADDR-BY-NAME mymaster

# 6. 恢复旧主(可选)
docker start redis-master
# 旧主会以 slave 身份加入新主(若 replicaof 配置仍生效)
```

---

## 十五、故障演练与告警

### 1. 演练流程清单

| 步骤 | 命令/动作 | 期望结果 |
|------|-----------|----------|
| 1. 演练前确认 | `SENTINEL CKQUORUM mymaster` | OK,可达成多数派 |
| 2. 主库状态基线 | `INFO replication` 记录 role=master, connected_slaves | 基线快照 |
| 3. 模拟故障 | `redis-cli -p 6379 DEBUG sleep 60` 或 `kill -9` redis-server | 主失联 |
| 4. 观察日志 | `tail -f sentinel.log` | 看到 `+sdown` → `+odown` → `+failover` → `+switch-master` |
| 5. 记录耗时 | 从 kill 到 `+switch-master` 的时间 | RTO < 30s 为优 |
| 6. 验证客户端 | 应用读写新主是否成功 | 业务不感知 |
| 7. 恢复旧主 | 重启旧主 | 自动作为 slave 加入 |
| 8. 写演练报告 | 时间点 / 切换前后对比 / 客户端影响 | 归档备查 |

### 2. 告警脚本示例

```bash
#!/usr/local/bin/sentinel_alert.sh
# 用法:sentinel notification-script mymaster /usr/local/bin/sentinel_alert.sh
# 接收参数:Sentinel 传入 4 个参数
#   $1 = master-name
#   $2 = event-type(sdown/-sdown/odown/-odown/+switch-master)
#   $3 = subject(info 信息)
#   $4 = additional info

MASTER_NAME=$1
EVENT=$2
SUBJECT=$3
DETAIL=$4

TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")
MSG="[$TIMESTAMP] [Sentinel告警] master=$MASTER_NAME event=$EVENT subject=$SUBJECT detail=$DETAIL"

# 1. 写入日志
echo "$MSG" >> /var/log/redis-sentinel/alert.log

# 2. 发到企业 IM(以飞书 Webhook 为例)
curl -s -X POST "https://open.feishu.cn/open-apis/bot/v2/hook/XXXX" \
     -H "Content-Type: application/json" \
     -d "{\"msg_type\":\"text\",\"content\":{\"text\":\"$MSG\"}}"

# 3. 发邮件(可选)
echo "$MSG" | mail -s "Redis Sentinel Alert $EVENT" oncall@example.com

exit 0
```

### 3. 演练注意事项

- **低峰期演练**:深夜或业务低峰期
- **保留观察窗口**:演练后观察 30~60 分钟
- **数据校验**:对比演练前后 `INFO keyspace`、`DBSIZE`
- **客户端切换感知**:检查应用日志是否有"主节点变更"标记
- **回滚预案**:演练失败时如何快速恢复原状态(手动反向切换)

---

## 十六、Sentinel 限制

| 限制 | 说明 | 应对 |
|------|------|------|
| **不解决数据分片** | 数据全量复制,容量受限于单机内存 | 数据量大时用 Cluster |
| **写入仍是单点** | 1 主只能单点写入,无法水平扩展写 | 写并发高用 Cluster |
| **故障转移期间不可写** | RTO 通常 5~30s,这段时间主不可用 | 业务允许短时写失败/降级 |
| **脑裂需人工配置** | 必须显式设置 min-replicas-* | 上线 checklist 必检项 |
| **不支持多租户强隔离** | Sentinel 监控一组主从,业务间隔离差 | 业务分端口即可 |
| **Sentinel 自身无副本** | Sentinel 进程宕机需重启 | 容器编排自愈(K8s/Supervisor) |
| **复制延迟不可控** | 异步复制下,从可能丢数据 | 业务容忍 RPO 秒级 |
| **客户端需支持 Sentinel** | 旧客户端无法感知主切换 | 升级 Jedis/Lettuce |

---

## 十六点五、Sentinel 监控指标与 Prometheus 集成

### 1. INFO Sentinel 输出关键字段

```bash
$ redis-cli -p 26379 INFO sentinel
# Sentinel
sentinel_masters=1
sentinel_running_scripts=0
sentinel_scripts_queue_length=0
sentinel_simulate_failure_flags=0
master0=name=mymaster,status=ok,address=192.168.1.10:6379,
        slaves=2,sentinels=3
```

通过 `master0` 行可以一眼看出:

| 字段 | 含义 |
|------|------|
| `status=ok` | 主节点状态(ok / ok_down / down) |
| `address` | 当前主地址 |
| `slaves` | 从节点数量 |
| `sentinels` | 监控该主的 Sentinel 数量 |

### 2. 常用监控项与告警阈值

| 监控项 | 来源 | 告警阈值(建议) |
|--------|------|----------------|
| 主节点状态 | `status=ok` | 状态非 ok 立即告警 |
| 从节点数量 | `slaves` | < 期望值 - 1 |
| Sentinel 集群规模 | `sentinels` | < 3 立即告警 |
| 主从复制偏移 | `master_repl_offset` vs `slave_repl_offset` | 差值 > 1MB 告警 |
| Sentinel 最近一次 hello 间隔 | `last-ping-sent` | > 2s 异常 |
| 主观下线次数 | `+sdown` 计数 | 30 分钟内 > 0 告警 |
| 故障转移次数 | `+switch-master` 次数 | 1 小时内 > 0 告警 |

### 3. Prometheus Exporter 集成

```bash
# 推荐:oliver006/redis_exporter 支持 Sentinel 模式
docker run -d --name redis_exporter \
  -p 9121:9121 \
  oliver006/redis_exporter \
  --redis.addr redis://sentinel1:26379 \
  --redis.sentinel mymaster \
  --redis.password "redis-pass"
```

```yaml
# prometheus.yml 抓取配置
scrape_configs:
  - job_name: 'redis_sentinel'
    static_configs:
      - targets: ['redis_exporter:9121']
```

```promql
# 关键告警规则示例
groups:
- name: redis_sentinel
  rules:
  - alert: RedisSentinelDown
    expr: redis_sentinel_master_status != 1
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "Redis Sentinel 主节点异常 {{ $labels.instance }}"

  - alert: RedisSentinelSlaveLag
    expr: redis_connected_slaves < 2
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "Redis 主 {{ $labels.instance }} 从节点数过低"

  - alert: RedisSentinelLost
    expr: redis_sentinel_known_sentinels < 3
    for: 2m
    labels:
      severity: critical
    annotations:
      summary: "Sentinel 集群小于 3 节点,存在脑裂风险"
```

---

## 十六点七、Python/Go 客户端连接 Sentinel

### 1. Python redis-py

```python
import redis
from redis.sentinel import Sentinel

# 1. 创建 Sentinel 对象
sentinel = Sentinel(
    sentinels=[('192.168.1.20', 26379),
               ('192.168.1.21', 26379),
               ('192.168.1.22', 26379)],
    socket_timeout=2,
    password='redis-pass'  # 主节点密码
)

# 2. 获取主连接
master = sentinel.master_for('mymaster', socket_timeout=2)
master.set('user:1001', '{"name":"will"}')
print(master.get('user:1001'))

# 3. 获取从连接(读操作)
slave = sentinel.slave_for('mymaster', socket_timeout=2)
print(slave.get('user:1001'))

# 4. 获取原始地址
print(sentinel.discover_master('mymaster'))  # ('192.168.1.10', 6379)
print(sentinel.discover_slaves('mymaster'))  # [('192.168.1.11', 6378), ...]
```

### 2. Go go-redis

```go
package main

import (
    "context"
    "fmt"
    "github.com/redis/go-redis/v9"
)

func main() {
    rdb := redis.NewFailoverClient(&redis.FailoverOptions{
        MasterName:    "mymaster",
        SentinelAddrs: []string{
            "192.168.1.20:26379",
            "192.168.1.21:26379",
            "192.168.1.22:26379",
        },
        Password:     "redis-pass",
        DialTimeout:  2 * time.Second,
        ReadTimeout:  1 * time.Second,
        WriteTimeout: 1 * time.Second,
        PoolSize:     100,
    })

    ctx := context.Background()
    rdb.Set(ctx, "k1", "v1", 0)
    val, _ := rdb.Get(ctx, "k1").Result()
    fmt.Println("k1 =", val)
}
```

### 3. 不同客户端重连策略对比

| 客户端 | 故障切换感知 | 自动重连 | 推荐配置 |
|--------|--------------|----------|----------|
| **Jedis SentinelPool** | 订阅 `+switch-master` | ✔ | 连接超时 < 5s |
| **Lettuce Sentinel** | 拓扑动态刷新 | ✔ | 默认已开 |
| **Spring Data Redis** | 依赖底层 Lettuce/Jedis | ✔ | `lettuce.shutdown-timeout` |
| **redis-py (Python)** | 内部 sentinel 定时刷新 | ✔ | `socket_timeout` |
| **go-redis** | 内部 dial 失败时重试 | ✔ | `MaxRetries` |

---

## 十七、Sentinel 故障排查 Checklist

### 1. 故障转移没发生

```bash
# 1. 主是否真的挂了?
redis-cli -p 6379 PING             # 应用侧

# 2. Sentinel 看到的从节点数
redis-cli -p 26379 SENTINEL SLAVES mymaster

# 3. quorum 是否能达成
redis-cli -p 26379 SENTINEL CKQUORUM mymaster
# 期望:OK 3 usable Sentinels

# 4. Sentinel 之间的连通性(在 sentinel1 上测)
redis-cli -p 26379 -h 192.168.1.21 PING
redis-cli -p 26379 -h 192.168.1.22 PING

# 5. 看 Sentinel 日志
tail -f /var/log/redis/sentinel.log | grep -E "sdown|odown|failover"
```

**常见原因**:

| 现象 | 可能原因 |
|------|----------|
| `+sdown` 但无 `+odown` | quorum 太大或 Sentinel 间网络不通 |
| `+odown` 但无 `+failover` | 选举失败(投票分散),降低 quorum 重试 |
| `+failover` 但不结束 | `failover-timeout` 太短,补 binlog 慢 |

### 2. 故障转移后客户端没切

```bash
# 1. 客户端是否订阅 +switch-master
redis-cli -p 26379 SUBSCRIBE +switch-master &

# 2. 客户端是否调用 GET-MASTER-ADDR-BY-NAME 拉新地址
# Jedis:检查 PoolConfig.refreshPeriodOnFail

# 3. 客户端与 Sentinel 网络
redis-cli -h <sentinel_ip> -p 26379 PING
```

**常见原因**:

| 现象 | 可能原因 |
|------|----------|
| 客户端卡死 | 与所有 Sentinel 失联 |
| 部分客户端没切 | 客户端只连了一个 Sentinel,该 Sentinel 也挂了 |
| 切了但写入失败 | 新主尚未完成角色提升 |

### 3. Sentinel 频繁切换(flapping)

```text
  Master ─挂─► 切换到 Slave-A ──► Slave-A 也撑不住 ──► 又切换到 Slave-B ──► ...
```

**应对**:

| 措施 | 配置 |
|------|------|
| 提高 SDOWN 阈值 | `down-after-milliseconds 60000`(60s) |
| 提高故障转移超时 | `failover-timeout 600000`(10 分钟) |
| 检查网络抖动 | `MTR` 排查机房丢包 |
| 避免弱主机升主 | `replica-priority` 优先选高配 |

### 4. Sentinel 进程 OOM

```bash
# Sentinel 进程 RSS 默认不高(< 100MB)
# 若发现持续涨内存,常见原因:
#   1. INFO 输出被频繁打印(关闭调试日志)
#   2. notification-script 输出大量日志(把 stderr 重定向到 /dev/null)
#   3. Sentinel 在重连风暴中积压命令

# 排查 OOM
top -p $(pgrep -f redis-sentinel)
journalctl -u redis-sentinel | grep -i oom
```

---

## 十七点五、生产环境 Checklist

部署 Sentinel 上线前,务必逐项确认:

| # | 项目 | 检查命令 / 方法 |
|---|------|----------------|
| 1 | Sentinel 节点数 ≥ 3,奇数 | `SENTINEL SENTINELS mymaster` |
| 2 | Sentinel 分布在不同物理机 | `hostname` / `ip a` |
| 3 | `quorum` 设为 N/2 + 1(典型 2) | `cat sentinel.conf \| grep monitor` |
| 4 | `down-after-milliseconds` ≥ 网络最大 RTT × 5 | `ping <master>` |
| 5 | `failover-timeout` ≥ `parallel-syncs` × 全量同步时长 | 经验值 180s~600s |
| 6 | `min-replicas-to-write 1` 已配置 | `CONFIG GET min-replicas-to-write` |
| 7 | `min-replicas-max-lag 10` 已配置 | 同上 |
| 8 | `auth-pass` 配了,且 Redis 也 requirepass | `CONFIG GET requirepass` |
| 9 | notification-script 存在且可执行 | `ls -l /usr/local/bin/sentinel_alert.sh` |
| 10 | 告警已接入(企业 IM/邮件) | 模拟一次 `+sdown` 验证 |
| 11 | 客户端已升级 Jedis 3.x+ / Lettuce 5.x+ | `mvn dependency:tree` |
| 12 | 客户端连接超时 ≤ 5 秒 | `JedisPool.setTimeout` |
| 13 | Prometheus 监控已配 | `curl http://exporter:9121/metrics` |
| 14 | 季度演练计划已排 | 运维日历 |
| 15 | 切换脚本 client-reconfig-script 测试过 | `redis-cli -p 26379 SENTINEL FAILOVER mymaster` 演练 |

---

## 十七点七、Sentinel 与其他高可用方案对比

### 1. Sentinel vs MHA/MySQL Orchestrator

虽然 MHA、Orchestrator 是 MySQL 的 HA 方案,但 Redis Sentinel 的设计思想有相通之处,可作类比:

| 维度 | Redis Sentinel | MySQL MHA | MySQL Orchestrator |
|------|----------------|-----------|---------------------|
| 探测机制 | PING | SSH + ping | 直连探测 |
| 选主 | 自动(priority/offset/runid) | 补 binlog 最少者 | GTID 拓扑 |
| 配置推送 | 客户端订阅 | 写 conf + VIP 脚本 | 元数据库 |
| 脑裂防护 | min-replicas-* | MHA 自身不防 | 元数据库去重 |
| 复杂度 | 低 | 中(Perl) | 中(Golang) |

### 2. Sentinel vs Keepalived + VIP

```text
Keepalived + VIP 方案:

   ┌─── VIP: 192.168.1.100 ───┐
   │                           │
   ▼                           ▼
  Master-A               Master-B (备份)
  挂了 ─── VIP 飘移 ───►  Master-B 接管

  缺点:
   - 仅两节点,无多数派,脑裂时双方都抢 VIP
   - 切换粒度粗,只换 IP 不换角色
   - 应用依赖 VIP,Redis Cluster 无法用
```

Sentinel 的优势在于**多节点多数派**与**自动拓扑感知**,远胜 Keepalived 这类简单漂移方案。

### 3. Sentinel vs HAProxy + 健康检查

```text
HAProxy 方案:
   Client ──► HAProxy ──► Master / Slave

  HAProxy 监测 Redis 健康,但 HAProxy 本身需要 VIP/Keepalived 配合
  且不解决主从切换,只解决"读流量切到从"
```

Sentinel 是**主动**切换(改写从节点角色),HAProxy 是**被动**流量分配,二者可组合使用。

---

## 十七点九、Sentinel 性能与运维成本

### 1. Sentinel 自身资源消耗

| 资源 | 典型值 |
|------|--------|
| CPU | < 5%(仅每秒 PING) |
| 内存 | 50~200 MB(取决于被监控主从数量) |
| 网络 | 每 Sentinel 每秒 ~10 KB(PING + INFO) |
| 磁盘 | 几乎无 IO,工作目录占几 KB |

> 资源消耗极低,完全可以与业务应用混部(但仍建议独立部署,便于升级与监控)。

### 2. 大规模 Sentinel 注意事项

当被监控的主从组数量极大时(几十组以上),Sentinel 单进程可能成瓶颈:

| 现象 | 优化 |
|------|------|
| PING 延迟 | 多 Sentinel 实例分组管理 |
| INFO 解析慢 | `sentinel down-after-milliseconds` 调大(降低频率) |
| 日志爆炸 | `loglevel notice` 而非 `debug` |
| 网络抖动 | 把 Sentinel 部署在同机房 |

---

## 十八、核心要点速记

| 关键词 | 要点 |
|--------|------|
| **Sentinel** | Redis 官方高可用方案,2.8 起内置 |
| **三大任务** | 监控、通知、自动故障转移(+配置提供) |
| **至少 3 Sentinel** | 奇数部署,跨机器,避免脑裂 |
| **SDOWN** | 单 Sentinel 主观下线,ping 超时触发 |
| **ODOWN** | quorum 个 Sentinel 共识下线 |
| **quorum** | sentinel monitor 最后一个参数,如 2 |
| **majority** | N/2 + 1,Sentinel 总数决定 |
| **Raft-like 选举** | epoch + 投票,先到先得,同 epoch 一票 |
| **选主优先级** | replica-priority → repl_offset → runid |
| **replica-priority 0** | 永不被选升主,适合备份节点 |
| **SLAVEOF NO ONE** | 升主的关键命令 |
| **PUBLISH +switch-master** | Sentinel 通知客户端切换的频道 |
| **GET-MASTER-ADDR-BY-NAME** | 客户端最常用 API,获取当前主地址 |
| **SENTINEL SET** | 运行时动态修改配置 |
| **SENTINEL FAILOVER** | 强制触发故障转移,演练用 |
| **脑裂** | 网络分区导致双主,数据双写/丢失 |
| **min-replicas-to-write** | 主必须 N 个从在线才允许写入,防脑裂 |
| **min-replicas-max-lag** | 主从延迟阈值,防脑裂 |
| **failover-timeout** | 故障转移超时,默认 180s |
| **down-after-milliseconds** | SDOWN 阈值,默认 30s |
| **parallel-syncs** | 同时对新主同步的从节点数 |
| **Sentinel 端口** | 26379(区别于 Redis 6379) |
| **JedisSentinelPool** | Java 客户端连接 Sentinel 标准方式 |
| **Lettuce Sentinel** | 响应式 Redis 客户端,内置拓扑刷新 |
| **Spring Data Redis** | spring.redis.sentinel.nodes 配置即可 |
| **Sentinel vs Cluster** | 前者高可用、后者分片+高可用 |

---

## 十八、面试题速答

### 1. Sentinel 是如何工作的?

> Sentinel 通过 `PING` 探测主从与 Sentinel 集群健康,单个 Sentinel 判定 SDOWN 后发起投票,达成 quorum 票触发 ODOWN;随后进行 Raft-like 选举,Leader 按 priority/offset/runid 选最优从升主,并 PUBLISH `+switch-master` 通知客户端。

### 2. 为什么至少要 3 个 Sentinel?

> 2 个 Sentinel 不存在多数派(majority=2,但 1 票就过半,易产生脑裂);3 个 Sentinel 在挂 1 个时仍能正常决策,且 quorum=2 时容错性好。

### 3. 主节点挂了,客户端如何感知?

> 客户端通过订阅 Sentinel 的 `+switch-master` 频道,或在每次连池时调用 `GET-MASTER-ADDR-BY-NAME` 获取最新主地址;JedisSentinelPool / Lettuce 都自动处理。

### 4. 选主时怎么挑从节点?

> 三步优先级:① replica-priority 小的优先(可手动设);② repl_offset 大的优先(数据最新);③ runid 字典序小的优先(随机,保稳定)。

### 5. 脑裂是怎么产生的?怎么防?

> 网络分区时,旧主与 Sentinel 失联但仍接受客户端写入,新主在另一侧被选出,产生双写。**防御**:在主节点配置 `min-replicas-to-write 1` + `min-replicas-max-lag 10`,让旧主自我拒绝写入。

### 6. SDOWN 和 ODOWN 的区别?

> SDOWN 是单个 Sentinel 自己的判断(ping 超时);ODOWN 是 Sentinel 集群 quorum 票的共识,真正触发故障转移。

### 7. 故障转移期间客户端写入怎么办?

> 故障转移 RTO 通常 5~30 秒,这期间主不可写、客户端收到错误。建议业务做**幂等重试**或**降级回源 DB**;缓存层允许短暂不可用。

### 8. Sentinel 怎么和 Redis Cluster 一起用?

> Sentinel 主要监控 Cluster 中的每个 master(用 master-name 区分),但主切换由 Cluster 内部 gossip + 多数派完成,Sentinel 更像"外部观察者+通知者"。

### 9. 如何做 Sentinel 演练?

> 选低峰期,用 `SENTINEL FAILOVER mymaster` 或 kill 主进程,记录 `+sdown → +odown → +switch-master` 各阶段耗时,验证客户端是否自动切换。

### 10. Sentinel 配置修改后必须重启吗?

> 不必须,可用 `SENTINEL SET mymaster <option> <value>` 动态修改;但仍建议在配置文件 + 重启的标准化流程下做,避免运行时漂移。

---

> **实战建议**:Sentinel 是绝大多数中小规模 Redis 高可用的"够用就好"方案。部署前 checklist:3 节点 Sentinel + 跨机器 + 奇数、`min-replicas-*` 已配、Jedis/Lettuce 客户端已升级、告警脚本已部署、每季度至少演练一次。规模一旦超过单机内存或单主写入,果断迁 Cluster。