# MySQL MGR 详解 (MySQL Group Replication)

> 本章系统讲解 MySQL 5.7.17+ 推出的官方同步复制方案 MGR。异步/半同步主从复制见 [第 13 章](13-主从复制.md);读写分离见 [第 15 章](15-读写分离.md);高可用方案选型见 [第 16 章](16-高可用架构.md)。

## 一、MGR 概述

### 1.1 什么是 MGR

**MGR (MySQL Group Replication)** 是 MySQL 官方在 **5.7.17 版本**正式推出的**同步多主/单主集群**方案,基于 **Paxos 变体协议 (XCOM + BFT)** 实现多节点间的强一致性复制。

**核心特点**:

| 特性 | 说明 |
|------|------|
| **同步复制** | 事务提交需多数节点确认,真正 RPO=0 |
| **高可用** | 任意节点故障自动选主,数秒完成 |
| **强一致** | 基于 Paxos 共识,所有节点最终看到一致数据 |
| **冲突检测** | 多主模式下自动检测并回滚冲突事务 |
| **容错性** | 容忍 ⌊N/2⌋ 个节点故障 (N 为集群大小) |
| **插件化** | 以 `group_replication` 插件形式提供,需显式加载 |
| **通信层** | 基于 XCOM (基于 Paxos 的原子广播) |

### 1.2 与传统复制的对比

| 维度 | 异步主从 | 半同步主从 | **MGR** |
|------|----------|------------|---------|
| RPO (数据丢失) | 可能丢 | 0 | **0** |
| 切换速度 | 分钟级 (MHA) | 分钟级 (MHA) | **秒级 (自动)** |
| 写性能 | 最佳 | 中 | 较低 (多数派 ACK) |
| 强一致性 | ✗ | ✗ | **✓ (Paxos)** |
| 冲突检测 | ✗ | ✗ | **✓ (certifier)** |
| 多主写入 | ✗ | ✗ | **✓ (多主模式)** |
| 节点数限制 | 任意 | 任意 | 最多 9 (推荐 ≤7) |
| 适用版本 | 任意 | 5.5+ | **5.7.17+ / 8.0+** |

### 1.3 模式选择

MGR 支持两种运行模式:

| 模式 | 写入节点 | 适用场景 |
|------|----------|----------|
| **单主模式 (Single-Primary)** | 仅一个主可写,其他自动只读 | **推荐生产**,绝大多数场景 |
| **多主模式 (Multi-Primary)** | 所有节点都可写,自带冲突检测 | 异地多活写入(需业务兼容冲突回滚) |

---

## 二、MGR 集群架构

### 2.1 整体架构图

```text
                  ┌─────────────────────────────────────────┐
                  │           MGR Cluster (3 / 5 / 7 节点)  │
                  └─────────────────────────────────────────┘

   ┌─────────────┐         ┌─────────────┐         ┌─────────────┐
   │  Node-1     │ <─────> │  Node-2     │ <─────> │  Node-3     │
   │ (PRIMARY)   │  GCS    │ (SECONDARY) │  GCS    │ (SECONDARY) │
   │             │ <─────> │             │ <─────> │             │
   │ ┌─────────┐ │         │ ┌─────────┐ │         │ ┌─────────┐ │
   │ │MySQL    │ │         │ │MySQL    │ │         │ │MySQL    │ │
   │ │+group_  │ │         │ │+group_  │ │         │ │+group_  │ │
   │ │replicat │ │         │ │replicat │ │         │ │replicat │ │
   │ │ion 插件 │ │         │ │ion 插件 │ │         │ │ion 插件 │ │
   │ └────┬────┘ │         │ └────┬────┘ │         │ └────┬────┘ │
   └──────┼──────┘         └──────┼──────┘         └──────┼──────┘
          │                       │                       │
          │     ┌─────────────────┴─────────────┐         │
          └─────│       Group Communication     │─────────┘
                │       (GCS, 基于 XCOM/Paxos)  │
                │    - 原子广播                  │
                │    - 故障检测                  │
                │    - 成员关系管理              │
                └───────────────────────────────┘
                            │
                ┌───────────┴───────────┐
                │  group_replication    │
                │  recovery 通道         │
                │  (新节点加入时使用)     │
                └───────────────────────┘
```

### 2.2 核心组件

```text
┌──────────────────────────────────────────────────────────────┐
│                      MySQL Server                            │
│                                                              │
│  ┌────────────┐   ┌──────────────┐   ┌──────────────────┐  │
│  │  SQL 层    │ → │  Optimizer   │ → │  Group Replication│  │
│  │            │   │              │   │  Plugin (MGR)     │  │
│  └────────────┘   └──────────────┘   └────────┬─────────┘  │
│                                               │             │
│  ┌────────────┐   ┌──────────────┐            ↓             │
│  │ InnoDB     │ ← │  binlog      │   ┌──────────────────┐  │
│  │ (含 WriteSet│  │  (ROW 模式)  │ ← │   applier        │  │
│  │  tracking) │   │              │   │  (回放远程事务)    │  │
│  └────────────┘   └──────────────┘   └────────┬─────────┘  │
│                                                │             │
│  ┌────────────┐                                │             │
│  │ GTID 执行 │ ───────────────────────────────┘             │
│  └────────────┘                                              │
└──────────────────────────────────────────────────────────────┘
                                ↓
                  ┌──────────────────────────┐
                  │     XCOM (Paxos 层)       │
                  │  - 节点间 UDP 通信         │
                  │  - 故障检测               │
                  │  - 共识协议               │
                  │  - 消息排序               │
                  └──────────────────────────┘
```

### 2.3 关键进程/线程

| 组件 | 作用 |
|------|------|
| **GCS (Group Communication System)** | 基于 XCOM (Paxos) 的组通信 |
| **applier** | 回放从其他节点接收的事务 |
| **certifier** | 事务冲突检测(多主模式) |
| **recovery** | 新节点加入时从 donor 同步数据 |
| **comms_threads** | XCOM 通信线程 (默认 10 个) |

---

## 三、MGR 工作原理

### 3.1 事务提交流程(单主模式)

```text
   Client
     │
     │ 1. 发送 INSERT
     ↓
┌──────────┐
│ Primary  │
│  Node-1  │
└──────────┘
     │
     │ 2. 本地事务执行 → 生成 WriteSet (行级哈希指纹)
     │
     │ 3. 触发 binlog (ROW 模式)
     │
     │ 4. group_replication 拦截 binlog → 打包成 GR 消息
     │
     │ 5. 通过 GCS (XCOM) 广播到所有节点
     ↓
   XCOM (Paxos)
     │
     │ 6. 各节点收到消息 → 排序
     │
     ├──> Node-2 收到 → certifier 校验 → applier 回放
     ├──> Node-3 收到 → certifier 校验 → applier 回放
     │
     │ 7. 多数节点确认 (2/3 或 3/5)
     ↓
   XCOM 返回 ACK
     │
     │ 8. Primary 收到多数派 ACK → 本地 commit
     ↓
   返回 Client OK
```

### 3.2 多数派确认

```text
┌─────────────────────────────────────────────────────────────┐
│ 集群规模    多数派    容忍故障    推荐                         │
├─────────────────────────────────────────────────────────────┤
│  1          1         0          ✗ (无高可用)                 │
│  3          2         1          ✓ 推荐入门                    │
│  5          3         2          ✓ 推荐生产                    │
│  7          4         3          ✓ 大规模 (性能略降)           │
│  9          5         4          ✗ 性能已明显下降, 不推荐      │
└─────────────────────────────────────────────────────────────┘

公式: 多数派 = ⌊N/2⌋ + 1
```

### 3.3 故障检测

```text
每个节点都向其他节点发送心跳:

   Node-1 → Node-2: ping (每 5s, 默认)
   Node-1 → Node-3: ping

若 Node-1 在 suspicion_timeout (默认 10s) 内
未收到 Node-2 心跳:

1. Node-1 标记 Node-2 为 SUSPECTED (可疑)
2. 广播 SUSPECT 消息给其他节点
3. 若多数派也认为 Node-2 不可达
4. 则 Node-2 被驱逐 (expel) 出集群
5. 触发视图变更 (view change)
6. 重新选举新主(单主模式)
```

### 3.4 WriteSet 与冲突检测(多主)

```text
多主模式下,所有节点都可写:

   Node-1:  UPDATE t SET c=10 WHERE id=1  ─┐
                                          │  并发执行
   Node-2:  UPDATE t SET c=20 WHERE id=1  ─┘

冲突检测机制:
1. Node-1 事务生成 WriteSet (主键哈希集):
   {hash('mydb.t1', 1)}
2. Node-2 事务同样生成:
   {hash('mydb.t1', 1)}
3. Node-1 先 commit,WriteSet 广播到 Node-2
4. Node-2 certifier 比对发现冲突
5. Node-2 事务回滚 → 客户端收到错误:
   "ERROR 1180: Got error 149 during COMMIT"
   "Lock wait timeout exceeded; try restarting transaction"
```

---

## 四、MGR 完整部署(单主模式)

### 4.1 环境规划

| 节点 | IP | 端口 | server_id | 角色 |
|------|-----|------|-----------|------|
| node-1 | 10.0.0.11 | 3306 | 1 | PRIMARY (启动后自动选) |
| node-2 | 10.0.0.12 | 3306 | 2 | SECONDARY |
| node-3 | 10.0.0.13 | 3306 | 3 | SECONDARY |

**前置要求**:
- 节点间 33061 (应用) + 33060 (XCOM) 端口互通
- 时间同步 (NTP, 偏差 ≤ 1s)
- 所有节点 MySQL 版本一致
- 单主模式至少 3 节点 (容忍 1 故障)

### 4.2 my.cnf 配置(三节点通用部分)

```ini
[mysqld]
# 基础配置
server_id          = 1             # 每节点不同
datadir            = /var/lib/mysql
socket             = /var/lib/mysql/mysql.sock
pid-file           = /var/run/mysqld/mysqld.pid
log_error          = /var/log/mysqld.log
port               = 3306

# GTID (MGR 必须)
gtid_mode                = ON
enforce_gtid_consistency = ON

# binlog 必须 ROW
log_bin                = /var/lib/mysql/mysql-bin
binlog_format          = ROW
binlog_checksum        = NONE        # MGR 推荐关闭,避免校验冲突
max_binlog_size        = 1G

# 主键 (MGR 必须每表有主键)
sql_require_primary_key = ON

# relay log
relay_log              = /var/lib/mysql/relay-bin
relay_log_info_repository = TABLE
master_info_repository = TABLE

# 复制配置
slave_parallel_type     = LOGICAL_CLOCK
slave_parallel_workers  = 8
slave_preserve_commit_order = ON
transaction_write_set_extraction = XXHASH64   # MGR 必需
```

### 4.3 MGR 插件配置(三节点)

```ini
[mysqld]
# 加载插件
plugin_load_add = 'group_replication.so'

# 集群配置
group_replication_group_name         = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"   # UUID, 每集群相同
group_replication_start_on_boot      = OFF       # 手动启动, 避免 boot 时竞争
group_replication_local_address      = "10.0.0.11:33061"     # 本节点 IP:PORT, 每节点不同
group_replication_group_seeds       = "10.0.0.11:33061,10.0.0.12:33061,10.0.0.13:33061"
group_replication_ip_whitelist      = "10.0.0.0/24,127.0.0.1/8"

# 单主模式(默认)
group_replication_single_primary_mode = ON

# 数据一致性 (强烈推荐)
group_replication_enforce_update_everywhere_checks = ON   # 多主时才生效

# Flow Control (流量控制)
group_replication_flow_control_mode         = QUOTA     # QUOTA / DISABLED
group_replication_flow_control_applier_threshold = 25000
group_replication_flow_control_certifier_threshold = 25000
```

### 4.4 节点 1 (种子节点) 引导

```bash
# 启动 MySQL
systemctl start mysqld

# 1. 设置复制账号
SET SQL_LOG_BIN = 0;
CREATE USER 'repl'@'%' IDENTIFIED WITH mysql_native_password BY 'Repl@12345';
GRANT REPLICATION SLAVE, BACKUP_ADMIN ON *.* TO 'repl'@'%';
FLUSH PRIVILEGES;
SET SQL_LOG_BIN = 1;

# 2. 配置复制通道 (CHANGE MASTER TO)
CHANGE MASTER TO MASTER_USER='repl',
                MASTER_PASSWORD='Repl@12345'
                FOR CHANNEL 'group_replication_recovery';

# 3. 启动 MGR (种子节点)
SET GLOBAL group_replication_bootstrap_group = ON;
START GROUP_REPLICATION;
SET GLOBAL group_replication_bootstrap_group = OFF;

# 4. 验证
SELECT * FROM performance_schema.replication_group_members;
SELECT * FROM performance_schema.replication_group_member_stats;
```

输出应类似:

```text
+---------------------------+--------------------------------------+--------------+-------------+--------------+
| CHANNEL_NAME              | MEMBER_ID                            | MEMBER_HOST  | MEMBER_PORT | MEMBER_STATE |
+---------------------------+--------------------------------------+--------------+-------------+--------------+
| group_replication_applier | 7d1f8a4e-bbbb-cccc-dddd-eeeeeeeeeeee | node-1       |        3306 | ONLINE       |
+---------------------------+--------------------------------------+--------------+-------------+--------------+
```

### 4.5 节点 2、3 加入集群

```bash
# 在 node-2 / node-3 上
SET SQL_LOG_BIN = 0;
CREATE USER 'repl'@'%' IDENTIFIED WITH mysql_native_password BY 'Repl@12345';
GRANT REPLICATION SLAVE, BACKUP_ADMIN ON *.* TO 'repl'@'%';
FLUSH PRIVILEGES;
SET SQL_LOG_BIN = 1;

CHANGE MASTER TO MASTER_USER='repl',
                MASTER_PASSWORD='Repl@12345'
                FOR CHANNEL 'group_replication_recovery';

START GROUP_REPLICATION;

# 验证
SELECT * FROM performance_schema.replication_group_members;
```

三节点 ONLINE 即成功。

### 4.6 验证集群状态

```sql
-- 集群成员
SELECT MEMBER_ID, MEMBER_HOST, MEMBER_PORT, MEMBER_STATE,
       MEMBER_ROLE, MEMBER_VERSION
FROM performance_schema.replication_group_members;

-- 单主模式下 PRIMARY 节点
SELECT MEMBER_ID, MEMBER_HOST, MEMBER_ROLE
FROM performance_schema.replication_group_members
WHERE MEMBER_ROLE = 'PRIMARY';

-- 集群统计
SELECT * FROM performance_schema.replication_group_member_stats\G
```

### 4.7 客户端连接 MGR

```yaml
# 推荐通过 MySQL Router 接入(自动路由)
spring:
  datasource:
    url: jdbc:mysql://mysql-router:6446/mydb?useSSL=false
    username: app_user
    password: app_pwd
```

或使用连接字符串直接指向 PRIMARY(单主):

```python
# 单主模式直接连 PRIMARY
dsn = "mysql://app:xxx@10.0.0.11:3306/mydb"
```

---

## 五、MGR 单主切换

### 5.1 自动切换

当 PRIMARY 节点故障时:

```text
1. 心跳超时 (默认 10s)
2. XCOM 触发视图变更 (view change)
3. 集群剔除故障节点
4. 按 group_replication_member_weight 选择新 PRIMARY
   (默认权重相同, UUID 字典序最小者胜出)
5. 旧 SECONDARY 自动晋升
6. 客户端通过 MySQL Router 自动重连
```

### 5.2 手动切换 (group_replication_set_as_primary)

```sql
-- 在任意 ONLINE 节点执行
SELECT group_replication_set_as_primary(
    '7d1f8a4e-bbbb-cccc-dddd-eeeeeeeeeeee'    -- 目标 PRIMARY 的 MEMBER_ID
);
```

### 5.3 设置节点权重 (8.0+)

```ini
# 优先级更高 → 更倾向成为 PRIMARY (主节点推荐 100, 备 50)
group_replication_member_weight = 100
```

```sql
-- 8.0.20+ 可动态设置
SET GLOBAL group_replication_member_weight = 100;
```

---

## 六、MGR 多主模式

### 6.1 开启多主

```sql
-- 先停 MGR
STOP GROUP_REPLICATION;

-- 修改配置
SET GLOBAL group_replication_single_primary_mode = OFF;
SET GLOBAL group_replication_enforce_update_everywhere_checks = ON;

-- 重启
START GROUP_REPLICATION;
```

### 6.2 多主模式约束(强烈重要)

```text
多主模式限制:

1. 表必须有主键 (否则冲突无法检测)
2. 不支持外键 (FOREIGN KEY, GTID + FK 冲突)
3. 不支持 SERIALIZABLE 隔离级别
4. 避免大事务跨多节点
5. 自增 ID 需配置步长:
   SET GLOBAL auto_increment_increment = 7;
   SET GLOBAL auto_increment_offset = <1..7>;
6. DDL 复制会阻塞所有节点, 慎用
```

### 6.3 多主 vs 单主选型

| 场景 | 推荐模式 | 原因 |
|------|---------|------|
| 传统 OLTP | 单主 | 简单,避免冲突 |
| 异地多活写入 | 多主 | 跨地域写入 |
| 读多写少 | 单主 + 多个 SECONDARY | 读路由简单 |
| 分片写入 (按 shard 路由) | 多主 | 业务已分片 |

---

## 七、MGR 监控

### 7.1 关键监控指标

```sql
-- 1. 集群成员健康
SELECT MEMBER_ID, MEMBER_STATE, MEMBER_ROLE
FROM performance_schema.replication_group_members;

-- MEMBER_STATE 取值:
--   ONLINE       - 正常
--   RECOVERING   - 同步中
--   OFFLINE      - 已停
--   ERROR        - 故障
--   UNREACHABLE  - 网络不可达

-- 2. 复制延迟(秒)
SELECT
  MEMBER_ID,
  COUNT_TRANSACTIONS_IN_QUEUE AS queue_trans,
  COUNT_TRANSACTIONS_CHECKED AS checked,
  COUNT_CONFLICTS_DETECTED AS conflicts
FROM performance_schema.replication_group_member_stats;

-- 3. 流量控制
SHOW STATUS LIKE 'group_replication_flow_control%';

-- 4. 应用线程延迟
SELECT CHANNEL_NAME, SERVICE_STATE, REMAINING_TRANSACTIONS
FROM performance_schema.replication_applier_status;

-- 5. 已应用事务
SELECT GTID_SUBTRACT(
  (SELECT RECEIVED_TRANSACTION_SET FROM performance_schema.replication_connection_status WHERE CHANNEL_NAME='group_replication_applier' LIMIT 1),
  (SELECT APPLIED_TRANSACTION_SET FROM performance_schema.replication_applier_status WHERE CHANNEL_NAME='group_replication_applier' LIMIT 1)
);
```

### 7.2 关键状态变量

| 变量 | 含义 | 告警阈值 |
|------|------|----------|
| `Flow_control_active` | 流量控制是否激活 | 频繁 > 0 需优化 |
| `Flow_control_time` | 处于流量控制的总时间 | > 50% 说明延迟严重 |
| `transactions_in_queue` | 待应用事务数 | > 100 需关注 |
| `conflicts_detected` | 冲突事务数(多主) | > 0 需业务排查 |

### 7.3 完整健康检查脚本

```sql
SELECT
  (SELECT COUNT(*) FROM performance_schema.replication_group_members
   WHERE MEMBER_STATE = 'ONLINE') AS online_members,
  (SELECT COUNT(*) FROM performance_schema.replication_group_members) AS total_members,
  (SELECT MAX(COUNT_TRANSACTIONS_IN_QUEUE)
   FROM performance_schema.replication_group_member_stats) AS max_queue,
  (SELECT SUM(COUNT_CONFLICTS_DETECTED)
   FROM performance_schema.replication_group_member_stats) AS total_conflicts;
```

---

## 八、MGR 故障处理

### 8.1 脑裂(Split-Brain)

**现象**: 网络分区后两侧都认为自己是合法集群。

```text
   ┌─── 旧集群 A ───┐         ┌─── 旧集群 B ───┐
   │  node-1 (PRIM) │         │  node-3 (PRIM) │
   │  node-2        │ ╳网络╳  │  node-4        │
   └────────────────┘         └────────────────┘
```

**MGR 自愈机制**:

- **少数派**自动拒绝写入 (Quorum 保护)
- 多数派继续接受写入
- 网络恢复后,**少数派自动重新加入**多数派
- 少数派的写入**全部丢失**

**避免脑裂的最佳实践**:

```ini
# 确保 quorum 一致
group_replication_unreachable_majority_timeout = 0   # 不擅自脱离集群
group_replication_member_expel_timeout = 5          # 5s 内多数确认才驱逐
```

### 8.2 节点离线修复后重新加入

```sql
-- 检查 ERROR 状态原因
SELECT * FROM performance_schema.replication_group_members
WHERE MEMBER_STATE != 'ONLINE';

-- 重启 MGR
STOP GROUP_REPLICATION;
START GROUP_REPLICATION;

-- 若数据差异过大,会自动触发 distributed recovery
```

### 8.3 Distributed Recovery (新节点加入)

```text
1. 新节点加入 → 触发 recovery
2. 集群选一个 ONLINE 节点作为 donor (默认: 最低 binlog 位点)
3. 新节点从 donor 通过异步复制追平
4. 追平后,新节点正式进入 ONLINE 状态
5. 后续同步通过 GCS (XCOM) 进行
```

**强制指定 donor** (8.0+):

```sql
SET GLOBAL group_replication_recovery_get_donor = 1;
START GROUP_REPLICATION;
```

### 8.4 大事务导致集群卡顿

**场景**:某个事务 100 万行 UPDATE,在多节点上同步缓慢。

```sql
-- 临时禁用 Flow Control
SET GLOBAL group_replication_flow_control_mode = 'DISABLED';

-- 等待大事务完成
SELECT * FROM performance_schema.replication_group_member_stats;

-- 恢复
SET GLOBAL group_replication_flow_control_mode = 'QUOTA';
```

### 8.5 误操作:全部节点被驱逐

```sql
-- 极端情况: 多数派都被驱逐 → 集群无法恢复

-- 唯一方法: 找一台有最新 GTID 的节点,强制重启集群
SET GLOBAL group_replication_bootstrap_group = ON;
START GROUP_REPLICATION;
SET GLOBAL group_replication_bootstrap_group = OFF;

-- 其他节点重新加入
STOP GROUP_REPLICATION;
CHANGE MASTER TO MASTER_USER='repl', MASTER_PASSWORD='Repl@12345'
                FOR CHANNEL 'group_replication_recovery';
START GROUP_REPLICATION;
```

---

## 九、MGR 性能调优

### 9.1 Flow Control (流量控制)

**原理**: 当某个节点延迟过大,自动限速 write,保证集群同步。

```ini
# 推荐配置 (5 节点)
group_replication_flow_control_mode = QUOTA
group_replication_flow_control_applier_threshold = 25000
group_replication_flow_control_certifier_threshold = 25000
group_replication_flow_control_min_quota = 0
group_replication_flow_control_min_recovery_quota = 0
group_replication_flow_control_period = 1
group_replication_flow_control_hold_percent = 10
group_replication_flow_control_release_percent = 50
```

**禁用 Flow Control** (性能优先,放弃保护):

```ini
group_replication_flow_control_mode = DISABLED
```

### 9.2 XCOM 通信线程

```ini
group_replication_communication_max_message_size = 10M
# 默认即可,网络大时调高
```

### 9.3 大事务拆分

```ini
# 限制单事务最大消息
group_replication_transaction_size_limit = 150000000   # ~150MB
```

### 9.4 写入集追踪

```ini
transaction_write_set_extraction = XXHASH64  # 必需
```

### 9.5 网络优化

```ini
# binlog 和 relay log 分离到不同磁盘
innodb_flush_log_at_trx_commit = 1
sync_binlog = 1
```

---

## 十、MGR 与 MySQL InnoDB Cluster

### 10.1 三件套

```text
MySQL InnoDB Cluster 是官方完整 HA 方案:

1. MySQL Group Replication (MGR)   - 数据节点集群
2. MySQL Router (Router)           - 路由代理, 自动读写分离 + 故障切换
3. MySQL Shell (Shell)             - 管理工具 (dba.* JS API)
```

### 10.2 部署 InnoDB Cluster

```javascript
// MySQL Shell
mysql-js> \connect app@node-1:3306
mysql-js> dba.configureInstance('app@node-1:3306')
mysql-js> dba.configureInstance('app@node-2:3306')
mysql-js> dba.configureInstance('app@node-3:3306')

// 创建集群
mysql-js> var cluster = dba.createCluster('myCluster')

// 添加节点
mysql-js> cluster.addInstance('app@node-2:3306')
mysql-js> cluster.addInstance('app@node-3:3306')

// 查看状态
mysql-js> cluster.status()

// 设置 Router 用户
mysql-js> cluster.setupRouterAccount('router_user')
```

### 10.3 MySQL Router 配置

```ini
# /etc/mysqlrouter/mysqlrouter.conf
[routing:mycluster_rw]
bind_address = 0.0.0.0
bind_port = 6446
destinations = 10.0.0.11:3306,10.0.0.12:3306,10.0.0.13:3306
mode = read-write
protocol = classic

[routing:mycluster_ro]
bind_address = 0.0.0.0
bind_port = 6447
destinations = 10.0.0.11:3306,10.0.0.12:3306,10.0.0.13:3306
mode = read-only
protocol = classic
```

应用连接 6446 (写) / 6447 (读),Router 自动检测主从。

---

## 十一、MGR 优缺点

### 11.1 优点

```text
✓ 官方原生,集成度高
✓ 真正的强一致 (RPO=0)
✓ 自动故障切换 (秒级)
✓ 自动成员管理 (新节点加入、退出)
✓ 多主写入能力
✓ 基于 Paxos 的成熟一致性协议
✓ 完整 GTID 集成
```

### 11.2 缺点

```text
✗ 写性能下降 (多数派 ACK)
✗ 节点数限制 (推荐 ≤7)
✗ 多主模式限制多 (无外键、无 SERIALIZABLE)
✗ 大事务性能差
✗ 网络抖动敏感
✗ 网络分区少数派丢写入
✗ 学习曲线陡 (Paxos、certifier 等)
```

### 11.3 适用与不适用

| 场景 | 是否适合 | 原因 |
|------|---------|------|
| 中小型 OLTP (< 100 QPS 写) | ✓ | 强一致 + 自动切换 |
| 金融核心库 | ✓ | RPO=0 |
| 异地多活写入 | ✓ (多主) | Paxos 保证一致 |
| 海量写 (万级 TPS) | ✗ | 同步复制延迟 |
| 已用 Galera/PXC | ✗ | 重复 |
| 表无主键 | ✗ | MGR 强制要求 |

---

## 十二、MGR 实战命令速查

### 12.1 启动/停止

```sql
-- 启动
START GROUP_REPLICATION;

-- 停止
STOP GROUP_REPLICATION;

-- 引导 (bootstrap) — 仅在新集群初始化时
SET GLOBAL group_replication_bootstrap_group = ON;
START GROUP_REPLICATION;
SET GLOBAL group_replication_bootstrap_group = OFF;
```

### 12.2 切换主(单主)

```sql
-- 查看当前主
SELECT MEMBER_HOST FROM performance_schema.replication_group_members
WHERE MEMBER_ROLE = 'PRIMARY';

-- 切到指定节点
SELECT group_replication_set_as_primary('MEMBER_ID');
```

### 12.3 节点操作

```sql
-- 设置权重 (8.0+)
SET GLOBAL group_replication_member_weight = 100;

-- 强制重新加入
STOP GROUP_REPLICATION;
CHANGE MASTER TO MASTER_USER='repl', MASTER_PASSWORD='Repl@12345'
                FOR CHANNEL 'group_replication_recovery';
START GROUP_REPLICATION;

-- 离开集群 (主动)
STOP GROUP_REPLICATION;
```

### 12.4 模式切换

```sql
-- 单主 → 多主
STOP GROUP_REPLICATION;
SET GLOBAL group_replication_single_primary_mode = OFF;
SET GLOBAL group_replication_enforce_update_everywhere_checks = ON;
START GROUP_REPLICATION;

-- 多主 → 单主
STOP GROUP_REPLICATION;
SET GLOBAL group_replication_single_primary_mode = ON;
SET GLOBAL group_replication_enforce_update_everywhere_checks = OFF;
START GROUP_REPLICATION;
```

---

## 十三、核心要点速记

- **MGR = MySQL Group Replication**, 5.7.17+ 官方同步复制方案
- **基于 Paxos 变体 (XCOM)**,真正强一致 (RPO=0)
- **两种模式**:单主 (生产推荐) / 多主 (异地多活)
- **推荐 3 或 5 节点**,最多 9,不推荐 ≥9
- **多数派 = ⌊N/2⌋+1**,少数派自动拒绝写入
- **单主模式自动选主**:按 `member_weight` + UUID 字典序
- **多主模式必须**:表有主键、无外键、避免大事务、ID 步长
- **binlog 必须 ROW**,且 `binlog_checksum=NONE`
- **GTID 必须开启**, `transaction_write_set_extraction=XXHASH64`
- **每张表必须有主键** (`sql_require_primary_key=ON`)
- **Flow Control**: 默认 QUOTA,延迟大时自动限速
- **脑裂自动修复**:少数派丢数据但集群继续可用
- **新节点加入**:自动选 donor → 异步复制追平 → 进入 ONLINE
- **MySQL Router**:自动读写分离 + 故障切换 (推荐生产部署)
- **MySQL Shell**: dba.createCluster() 一键部署
- **性能 vs 一致性**: 写性能下降 ~30%, 但换取强一致
- **网络分区敏感**: WAN 部署需谨慎,优先同城机房
- **生产推荐**: 单主 + 3/5 节点 + MySQL Router + HAProxy
- **不适合场景**: 海量写入 (万级 TPS)、跨地域强同步

---

## 十四、参考与延伸

- **MySQL 官方文档**: https://dev.mysql.com/doc/refman/8.0/en/group-replication.html
- **MySQL InnoDB Cluster**: https://dev.mysql.com/doc/mysql-shell/8.0/en/admin-api-userguide.html
- **MySQL Router**: https://dev.mysql.com/doc/mysql-router/8.0/en/
- **第 13 章**: [主从复制(异步/半同步)](13-主从复制.md)
- **第 15 章**: [读写分离](15-读写分离.md)
- **第 16 章**: [高可用架构选型](16-高可用架构.md)
- **第 18 章**: [性能监控与调优](18-性能监控与调优.md)
