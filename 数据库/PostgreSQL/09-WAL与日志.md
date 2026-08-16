# PostgreSQL WAL 与日志系统 (Write-Ahead Logging & Logs)

> 本章系统讲解 PostgreSQL 的预写日志(WAL)机制与日志系统。WAL 是 PostgreSQL 实现 **ACID 中 D (Durability,持久性)** 的核心,贯穿崩溃恢复、流复制、逻辑复制、时间点恢复(PITR) 等所有关键能力。同时,PostgreSQL 的错误日志、慢查询日志、通用日志以及 `pg_stat_statements`、`auto_explain` 等扩展构成完整的可观测性体系。本章从 WAL 概念、文件结构、LSN 机制、写盘流程、Checkpoint 入手,逐步深入到日志系统、调优与监控。

---

## 一、WAL 概述

### 1. 什么是 WAL

**WAL(Write-Ahead Logging,预写日志)** 是 PostgreSQL 保证 **持久性 (Durability)** 与 **崩溃恢复 (Crash Recovery)** 的核心机制。其核心思想可以一句话概括:

> **在修改数据页(脏页)刷盘之前,必须先把对应的日志记录持久化到磁盘。**

只要日志落盘,即使系统随后崩溃,数据页丢失,PostgreSQL 也能在启动时 **通过回放 WAL** 把数据恢复到一致状态。

```
┌────────────────────────────────────────────────────────────────┐
│                       WAL 三大作用                              │
├────────────────────────────────────────────────────────────────┤
│  1. 崩溃恢复 (Crash Recovery)                                  │
│     - 异常断电后,通过 REDO 把已提交事务"重做"到数据页          │
│     - 通过 UNDO 逻辑回滚未提交事务(基于 xid 可见性)            │
│                                                                │
│  2. 数据复制 (Replication)                                     │
│     - 流复制:备库持续接收主库的 WAL 记录并应用                  │
│     - 逻辑复制:基于 WAL 解码出逻辑变更 (INSERT/UPDATE/DELETE)  │
│                                                                │
│  3. 数据一致性 + 时间点恢复 (PITR)                              │
│     - 全量备份 + WAL 归档 → 可恢复到任意 LSN/时间点            │
│     - 由 wal_level 控制日志级别                                │
└────────────────────────────────────────────────────────────────┘
```

### 2. WAL 与 MySQL redo log 的核心差异

PostgreSQL 的 WAL 与 MySQL InnoDB 的 redo log 都属于"先写日志再写数据"思想,但实现细节差异巨大:

| 维度           | PostgreSQL WAL                       | MySQL InnoDB redo log             |
|----------------|--------------------------------------|-----------------------------------|
| 物理/逻辑      | **物理 + 逻辑混合**(Heap 页级为主)  | 物理(页级)                       |
| 记录内容       | Heap 元组变更、Clog、Subtrans、Hint  | 字节级页修改(物理)               |
| 复制支持       | **原生**(流复制、逻辑复制都基于 WAL)| redo 不参与复制,binlog 才参与    |
| 归档           | 内置 `archive_mode`/`archive_command`| binlog 归档                       |
| 段切换         | 自动 16MB 段切换                     | 按 `innodb_log_file_size` 循环写 |
| 历史回放       | 可重放到任意 LSN/PITR               | 主要 REDO(崩溃恢复)              |

> 关键区别:**PostgreSQL 用一份 WAL 同时支撑了崩溃恢复、流复制、逻辑复制、PITR 四大功能**;MySQL 则把崩溃恢复(redo log)与复制/恢复(binlog)拆成两个独立日志。

### 3. WAL 的"先写后改"原则

```text
┌─────────────────────────────────────────────────────────────────┐
│                     WAL 写入铁律                                 │
│                                                                 │
│  1. 修改 shared_buffers 中的数据页之前                          │
│     → 必须先把对应的 WAL 记录写入 wal_buffers                   │
│                                                                 │
│  2. wal_buffers 中的记录必须在事务提交前 fsync 到磁盘            │
│     (默认行为由 wal_writer_delay / wal_sync_method 控制)        │
│                                                                 │
│  3. 脏数据页的刷盘由 bgwriter / checkpointer 异步执行            │
│     → 即使脏页未落盘,只要 WAL 在,系统崩溃后能 REDO 出来        │
└─────────────────────────────────────────────────────────────────┘
```

这正是 WAL 把 **"随机写数据页"** 变成 **"顺序写日志"** 的精髓 —— WAL 始终是顺序追加,远快于数据页的随机写。

---

## 二、WAL 文件结构

### 1. pg_wal 目录

PostgreSQL 把所有 WAL 段文件存放在数据目录的 `pg_wal` 子目录下(PG 10 之前叫 `pg_xlog`)。

```text
$PGDATA/
├── pg_wal/                    # WAL 段文件目录(10 之前是 pg_xlog)
│   ├── 000000010000000000000001
│   ├── 000000010000000000000002
│   ├── 000000010000000000000003
│   ├── 000000010000000000000004
│   └── archive_status/        # 归档状态标记目录
│       ├── 000000010000000000000003.done
│       └── 000000010000000000000004.ready
├── base/                      # 表/索引数据(Heap)
├── global/                    # 集群级系统表
├── pg_xact/                   # 事务提交状态(CLOG)
├── pg_multixact/              # 多事务状态
├── pg_stat/                   # 统计信息
├── pg_control                 # 控制文件(关键元信息)
├── postgresql.conf            # 主配置
├── pg_hba.conf                # 认证配置
└── postmaster.pid             # postmaster 进程 PID
```

**`archive_status/` 子目录**:每段 WAL 有一个同名标记文件,`.ready` 表示该段已写满可被归档命令搬走,`.done` 表示归档已完成,等 `checkpoint` 推进后这些段就可以被回收。

### 2. WAL 段文件命名规则

WAL 段文件名由 **3 段 24 位十六进制数字** 组成,完整描述它在 **时间线 + 段号** 维度上的位置:

```text
TTTTTTTT XXXXXXXX YYYYYYYY
  │         │         │
  │         │         └─ 段内偏移/段序号(8 位 hex,实际是 WAL 段号)
  │         └─ 高位段号(8 位 hex)
  └─ 时间线 ID (TimelineID,8 位 hex)

示例:000000010000000000000001
      ─┬── ─┬── ─┬──
       │    │    │
       │    │    └─ 段号 1
       │    └─ 高位段号 0
       └─ 时间线 1
```

**关键点**:

- **时间线 (TimelineID, TLI)**:每次做 PITR 恢复时,PostgreSQL 会生成新时间线(2, 3, ...),避免分支数据互相覆盖
- **逻辑 ID (LogSegNo)**:高 8 位 + 低 8 位组成,标识 WAL 段在当前时间线上的逻辑位置
- **物理 ID (LogId + LogSegNo)**:实际映射到磁盘文件名
- **默认每段 16MB**(`initdb` 时通过 `--wal-segsize` 设置,运行时不可改)

### 3. WAL 段文件大小

```sql
-- 查看当前 WAL 段大小(必须在 initdb 时决定)
SHOW wal_segment_size;
-- 默认 16MB

-- PostgreSQL 11+ 也可以用
SELECT setting, unit FROM pg_settings WHERE name = 'wal_segment_size';
```

**段大小选型建议**:

| 段大小     | 适用场景                              | 优缺点                                |
|------------|---------------------------------------|---------------------------------------|
| **16MB**   | 默认,绝大多数场景                    | 单段小,归档/清理粒度细               |
| 64MB       | 写入量大、想减少段切换开销            | 单段恢复粒度变粗,定位更慢            |
| 1GB        | 极端高吞吐(数据仓库、批量导入)        | 恢复时浪费带宽,通常不推荐            |

### 4. 文件结构示意图

```
┌──────────────────────────────────────────────────────────────────────┐
│                       pg_wal/ 目录结构                                │
│                                                                      │
│   时间线 1                  时间线 2 (PITR 恢复后)                  │
│   ┌─────────────────────┐   ┌─────────────────────┐                  │
│   │ 00000001 00000000   │   │ 00000002 00000000   │                  │
│   │         00000001 ←─ │ ──│── 00000001  ← 恢复起点(交叉点)│       │
│   │         00000002    │   │         00000002    │                  │
│   │         00000003    │   │         00000003    │                  │
│   │         00000004    │   │         00000004    │                  │
│   │         ...         │   │         ...         │                  │
│   │         (当前段)    │   │                     │                  │
│   └─────────────────────┘   └─────────────────────┘                  │
│                                                                      │
│   每个段文件: 16MB,内部由 8KB 页(WAL_BLOCKS)组成                    │
│   ┌──────────────────────────────────────────────────────────┐        │
│   │  WAL Segment (16MB)                                      │        │
│   │  ┌──────┐┌──────┐┌──────┐┌──────┐ ... ┌──────────────┐  │        │
│   │  │ Page ││ Page ││ Page ││ Page │     │   Page       │  │        │
│   │  │  8K  ││  8K  ││  8K  ││  8K  │     │   (部分)     │  │        │
│   │  │ XLOG ││ XLOG ││ XLOG ││ XLOG │     │              │  │        │
│   │  │ 记录 ││ 记录 ││ 记录 ││ 记录 │     │              │  │        │
│   │  └──────┘└──────┘└──────┘└──────┘     └──────────────┘  │        │
│   └──────────────────────────────────────────────────────────┘        │
│                                                                      │
│   archive_status/ 目录(归档状态标记)                                 │
│   ┌──────────────────────────────────────────────────────────┐        │
│   │  000000010000000000000003.ready  ← 等待归档                │        │
│   │  000000010000000000000002.done   ← 归档完成,checkpoint后删除│       │
│   └──────────────────────────────────────────────────────────┘        │
└──────────────────────────────────────────────────────────────────────┘
```

### 5. 查看当前 WAL 文件

```sql
-- 当前正在写入的 WAL 段
SELECT pg_walfile_name(pg_current_wal_lsn());
--  '000000010000000000000042'

-- 所有 WAL 段
SELECT * FROM pg_ls_waldir() ORDER BY name;

-- 已归档的 WAL 段
SELECT * FROM pg_ls_archive_statusdir();
```

---

## 三、LSN (Log Sequence Number)

### 1. LSN 概念

**LSN (Log Sequence Number)** 是 WAL 流的 **逻辑地址**,每一字节 WAL 都有一个唯一的 64 位 LSN。它在以下场景被广泛引用:

- 数据页头(`pd_lsn`):记录该页最近一次被 WAL 保护的修改
- Checkpoint 位置(`pg_control` 中的 `lastCheckPoint`)
- 复制槽位置(`pg_replication_slot.confirmed_flush_lsn`)
- 备份基准备份点(`START WAL LSN`)

LSN 格式是 **"高位 32 位 / 低位 32 位"** 的 64 位整数,用十六进制表示:

```
0/16B3B50
└┬┘└───┬───┘
 │     └─ 偏移量(低 32 位):本段内字节偏移
 └─ 段号(高 32 位):LogSegNo = LogId << 32 | LogSegNo(文件级)
```

### 2. LSN 与 WAL 文件名的换算

```sql
-- 把 LSN 转换为对应的 WAL 段文件名
SELECT pg_walfile_name('0/16B3B50');
-- '000000010000000000000001'

-- 把 LSN 转换为偏移量(在段内的字节位置)
SELECT pg_walfile_name_offset('0/16B3B50');
-- ('000000010000000000000001', 1499984)  -- 偏移约 1.4MB

-- 反向:文件名 → LSN
SELECT '0/16000000'::pg_lsn;
```

### 3. 常用 LSN 函数

```sql
-- 当前最新 WAL 插入位置(最新已写入 wal_buffers 的位置)
SELECT pg_current_wal_lsn();
--  '0/16B3B50'

-- 当前 WAL 写盘位置(已 fsync 到磁盘的位置,≤ pg_current_wal_lsn)
SELECT pg_walfile_name_offset(pg_current_wal_flush_lsn());

-- 上一次 checkpoint 的 LSN
SELECT pg_control_checkpoint();
-- 返回结构体,含 checkpoint LSN、redo LSN 等

-- 两个 LSN 之间的字节差(用于计算"待 WAL flush 量")
SELECT pg_wal_lsn_diff('0/17B3B50', '0/16B3B50');
--  1179648  (约 1.1MB)
```

### 4. LSN 应用示例

#### 示例 1:恢复时定位起点

```bash
# 全量备份元数据文件 backup_label
$ cat $BACKUP/backup_label
START WAL LSN: 0/3000028   # 备份开始时的 LSN
CHECKPOINT LSN: 0/3000060
BACKUP METHOD: streamed
BACKUP FROM: primary
START TIME: 2026-08-14 10:00:00

# 恢复时,先从 START WAL LSN 处开始重放 WAL
```

#### 示例 2:流复制位置

```sql
-- 主库:已写入/已刷盘/已回送位置
SELECT pg_current_wal_lsn()        AS write_lsn,        -- 已写入 wal_buffers
       pg_current_wal_flush_lsn()  AS flush_lsn,        -- 已 fsync
       pg_current_wal_insert_lsn() AS insert_lsn;       -- 等价于 write_lsn

-- 备库:接收/回放位置
SELECT received_lsn,     -- walreceiver 已接收的 LSN
       last_msg_send_time,
       last_msg_receipt_time,
       last_replay_time,
       replay_lsn        -- startup 进程已应用的 LSN
FROM pg_stat_replication;
```

#### 示例 3:监控 WAL 积压

```sql
-- 待 flush 字节数(主库写盘速度跟不上时,该值会上升)
SELECT pg_wal_lsn_diff(pg_current_wal_lsn(), pg_current_wal_flush_lsn())
       AS pending_bytes;

-- 备库:复制延迟(字节)
SELECT client_addr,
       pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) AS replay_lag_bytes,
       replay_lag                                            -- 9.2+:时间维度
FROM pg_stat_replication;
```

---

## 四、WAL 写入流程

### 1. 三层缓冲:Backend → WAL Buffers → Disk

PostgreSQL 写 WAL 涉及 **三个层次**:

```
┌────────────────────────────────────────────────────────────────────┐
│                     WAL 写入三层结构                                │
│                                                                    │
│  ┌─────────────────┐                                               │
│  │ Backend 进程     │  在自己的内存里组装 WAL 记录(XLogRecData 链表)│
│  │ (每个连接一个)  │  通过 XLogInsert() 插入到 wal_buffers          │
│  └────────┬────────┘                                               │
│           │                                                        │
│           ▼                                                        │
│  ┌─────────────────┐    ┌──────────────────────────┐              │
│  │  wal_buffers    │ ──►│  WAL Writer 进程          │              │
│  │  (共享内存)     │    │  周期性把 wal_buffers    │              │
│  │  默认 16MB      │    │  flush 到磁盘(.wal)     │              │
│  └─────────────────┘    └──────────┬───────────────┘              │
│                                    │                                │
│                                    ▼                                │
│                          ┌────────────────────┐                    │
│                          │  WAL 段文件(.wal)  │                    │
│                          │  $PGDATA/pg_wal/   │                    │
│                          │  默认 16MB/段      │                    │
│                          └────────────────────┘                    │
└────────────────────────────────────────────────────────────────────┘
```

### 2. WAL 写入时序图(INSERT/UPDATE/COMMIT)

```text
┌────────────────────────────────────────────────────────────────────────┐
│                  WAL 写入完整时序图(以 INSERT+COMMIT 为例)             │
│                                                                        │
│  Client    Backend 进程        WAL Buffers      WAL Writer     磁盘     │
│    │           │                    │                │          │     │
│    │ INSERT    │                    │                │          │     │
│    │ ─────────►│                    │                │          │     │
│    │           │ 解析/重写/优化     │                │          │     │
│    │           │                    │                │          │     │
│    │           │ 1. 修改 Heap 页    │                │          │     │
│    │           │    (shared_buffer) │                │          │     │
│    │           │                    │                │          │     │
│    │           │ 2. 构造 XLogRec   │                │          │     │
│    │           │    (逻辑日志)     │                │          │     │
│    │           │                    │                │          │     │
│    │           │ 3. XLogInsert()  │                │          │     │
│    │           │  ──── 插入 ────► │                │          │     │
│    │           │    (含 XLOG HEAP  │                │          │     │
│    │           │     INSERT 记录)  │                │          │     │
│    │           │                    │                │          │     │
│    │           │ 4. 修改 CLOG      │                │          │     │
│    │           │    (事务状态)     │                │          │     │
│    │           │                    │                │          │     │
│    │ COMMIT    │                    │                │          │     │
│    │ ─────────►│                    │                │          │     │
│    │           │ 5. 写 COMMIT 记录 │                │          │     │
│    │           │    ──── 插入 ────►│                │          │     │
│    │           │                    │                │          │     │
│    │           │ 6. 等待 flush     │                │          │     │
│    │           │  ──── 等待 ──────►│ ── flush() ──►│          │     │
│    │           │                    │                │ write+fsync│    │
│    │           │                    │                │ ─────────►│     │
│    │           │                    │                │           │     │
│    │           │  ◄───── flush 完成 ─────────────────┘           │     │
│    │           │                                                    │
│    │ COMMIT OK │                                                    │
│    │ ◄─────────│                                                    │
│    │           │                                                    │
│                                                                        │
│  时间轴(关键点):                                                      │
│  T1: SQL 执行,改 Heap 页                                              │
│  T2: 构造 + 插入 XLogRec 到 wal_buffers                               │
│  T3: COMMIT 触发                                                    │
│  T4: walwriter 周期 / COMMIT 强制触发 flush                            │
│  T5: fsync() 落盘                                                    │
│  T6: 返回 COMMIT OK                                                  │
└────────────────────────────────────────────────────────────────────────┘
```

### 3. Backend 与 WAL Writer 协作机制

PostgreSQL 的 WAL 写入由 **Backend 进程插入 + WAL Writer 刷盘** 共同完成,但 COMMIT 时的"强制 fsync"由 backend 自身保证。

```sql
-- 关键参数
SHOW wal_buffers;            -- 默认 16MB,太小会频繁换出
SHOW wal_writer_delay;       -- walwriter 刷盘周期,默认 200ms
SHOW wal_writer_flush_after; -- 写满多少字节后立即刷,默认 1MB
SHOW wal_sync_method;        -- 刷盘方式,默认 fdatasync
```

**关键时序逻辑**:

1. **事务执行期间**:Backend 把 XLogRec 插入 `wal_buffers`,**不直接写盘**。WAL Writer 按 `wal_writer_delay` 周期(默认 200ms)或累积 `wal_writer_flush_after` 字节(默认 1MB)后把 `wal_buffers` flush 到磁盘。
2. **事务 COMMIT 时**:Backend 在 `wal_buffers` 写入 COMMIT 记录后,**主动调用 XLogFlush 等待** WAL Writer 把自己的 LSN 之前的所有记录刷盘,然后才返回客户端 COMMIT OK。
3. **同步复制特殊处理**:`synchronous_commit = on` 且有同步备库时,COMMIT 还要等备库确认。

> 核心要点:**COMMIT OK 意味着对应的 WAL 记录已落盘**,这是 D (Durability) 的真正实现。

### 4. fsync 的关键参数

| 参数                  | 默认值      | 作用                                        |
|-----------------------|-------------|---------------------------------------------|
| `wal_sync_method`     | `fdatasync` | 刷盘系统调用,可选 fsync/fdatasync/open_sync/open_datasync |
| `fsync`               | `on`        | 全局开关,关闭后会丢数据,**生产严禁关**     |
| `full_page_writes`    | `on`        | 首次修改页时是否写整页(防部分写)           |
| `synchronous_commit`  | `on`        | 事务提交是否等 WAL 落盘                     |
| `wal_writer_delay`    | 200ms       | WAL Writer 周期                             |
| `wal_writer_flush_after` | 1MB      | 累计多少字节后立即 flush                    |

---

## 五、Checkpoint (检查点)

### 1. Checkpoint 是什么

**Checkpoint** 是把 **shared_buffers 中的所有脏页** 强制刷到磁盘的事件。Checkpoint 完成后:

- 之前的所有 WAL 段理论上可以 **被回收**(只要它们已被归档或不需要 PITR)
- `pg_control` 中记录最新的 `lastCheckPoint` 位置
- 崩溃恢复时只需要从最近一次 Checkpoint 之后的 WAL 开始重放

### 2. Checkpoint 触发条件

| 触发源              | 参数                        | 默认值    | 说明                                |
|---------------------|-----------------------------|-----------|-------------------------------------|
| **时间触发**         | `checkpoint_timeout`        | 5min      | 上次 Checkpoint 距今超过该值        |
| **WAL 量触发**       | `max_wal_size`              | 1GB       | WAL 总量超过该值,触发"伸展" Checkpoint |
| **手动触发**         | `CHECKPOINT` 命令           | -         | SQL:`CHECKPOINT;`                  |
| **关闭触发**         | `pg_ctl stop` / `SIGTERM`   | -         | smart/shutdown 时必做                |
| **备份触发**         | `pg_basebackup`             | -         | 基准备份时强制做一次                |
| **pg_control 满**   | -                           | -         | 控制文件记录空间满                  |

```sql
-- 查看 Checkpoint 相关参数
SELECT name, setting, unit FROM pg_settings
WHERE name IN ('checkpoint_timeout', 'max_wal_size', 'min_wal_size',
               'checkpoint_completion_target', 'checkpoint_warning',
               'bgwriter_lru_maxpages', 'bgwriter_delay');
```

### 3. Checkpoint 完整流程

```
┌──────────────────────────────────────────────────────────────────────┐
│                     Checkpoint 完整流程                               │
│                                                                      │
│  Step 1: 触发                                                        │
│   ├─ checkpoint_timeout 到期                                        │
│   ├─ max_wal_size 触底                                              │
│   └─ 手动 CHECKPOINT                                                │
│                                                                      │
│  Step 2: 准备工作                                                    │
│   ├─ 计算 redo pointer(从上次 Checkpoint 后的最早脏页开始)            │
│   ├─ 估算 I/O 量,按 checkpoint_completion_target 平滑分布            │
│   └─ 写 Checkpoint 记录到 wal_buffers(XLOG_CHECKPOINT_SHUTDOWN/ONLINE)│
│                                                                      │
│  Step 3: 持久化 WAL                                                  │
│   └─ WAL Writer 把包含 Checkpoint 记录的 wal_buffers 刷盘             │
│                                                                      │
│  Step 4: 刷脏页 (与 bgwriter 协作)                                   │
│   ├─ 启动阶段:checkpointer 按完成目标"缓慢"刷脏页                    │
│   ├─ 收尾阶段(checkpoint_completion_target 接近 1.0):              │
│   │   → checkpointer 加快,可能阻塞新写入                            │
│   └─ 强制刷 fsync                                                    │
│                                                                      │
│  Step 5: 更新控制文件                                                │
│   ├─ 写 pg_control(新 redo LSN、Checkpoint 时间戳等)                 │
│   └─ pg_control 是关键状态文件,损坏将无法启动                       │
│                                                                      │
│  Step 6: 回收旧 WAL                                                  │
│   ├─ 删除所有"checkpoint 之前 + 已归档"的 WAL 段                     │
│   └─ 受 min_wal_size 保护,不能少于该值                              │
└──────────────────────────────────────────────────────────────────────┘
```

### 4. bgwriter 与 checkpointer 协作

PostgreSQL 把"刷脏页"职责拆分给两个进程:

| 进程          | 作用                                                                                |
|---------------|-------------------------------------------------------------------------------------|
| **bgwriter**  | 周期性把"不那么脏的页"刷盘,**主要服务于 LRU 列表底部**,减少 backend 刷脏页概率      |
| **checkpointer** | Checkpoint 时刷**所有**脏页,确保 redo LSN 推进,允许 WAL 回收                  |

**协作图**:

```text
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Backend 进程    │     │  bgwriter 进程   │     │ checkpointer    │
│  修改 shared_   │     │  周期刷 LRU     │     │ 进程            │
│  buffers       │     │  列表底部脏页   │     │                 │
│  (持续产生脏页) │     │  (持续刷)       │     │ (Checkpoint 时)│
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌──────────────────────────────────────────────────────────────────┐
│                  shared_buffers 中的脏页                          │
└──────────────────────────────────────────────────────────────────┘
         │                       │                       │
         └───────────────────────┴───────────────────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │  数据文件 base/xxxxx  │
                    │  (Heap/索引页刷盘)     │
                    └────────────────────────┘
```

### 5. FULL PAGE WRITES (FPW)

**问题场景**:一个 8KB 的数据页正在被写到一半时系统崩溃,页内是"旧的"和"新的"混合状态,WAL 中只有增量变更 —— 重放后无法恢复一致。

**解决方案**:**FULL PAGE WRITES**。对一个页的 **第一次修改** (Checkpoint 之后),无论改了哪个字节,WAL 都记录 **整个 8KB 完整页内容**。

```sql
SHOW full_page_writes;        -- 默认 on,推荐保持
SHOW wal_compression;         -- 默认 off(15+ 可开 zstd/lz4/pglz)
```

| 配置                       | 行为                                      | 代价                       |
|----------------------------|-------------------------------------------|----------------------------|
| `full_page_writes = on`   | 首次改页写整页,防部分写撕裂              | WAL 体积增加(尤其批量导入) |
| `full_page_writes = off`   | 不写整页,依赖 OS/硬件保证原子写          | 崩溃可能丢数据,**慎用**   |
| `wal_compression = on`    | FPW 整页压缩(默认 pglz)                 | 节省磁盘,略耗 CPU         |

---

## 六、WAL 相关配置参数

### 1. 核心参数速查

```ini
# postgresql.conf

# ============ WAL 级别(影响复制/PITR) ============
wal_level = replica                  # minimal / replica(默认) / logical
                                      # minimal: 崩溃恢复够用,不支持复制
                                      # replica: 支持流复制(默认)
                                      # logical: 支持逻辑复制 + 解码

# ============ WAL 缓冲 ============
wal_buffers = 16MB                   # 默认 16MB;高并发写可调大到 64MB+
                                      # 太小 → XLogInsert 等待,影响性能

# ============ WAL 刷盘节奏 ============
wal_writer_delay = 200ms             # walwriter 周期
wal_writer_flush_after = 1MB         # 累计 1MB 立即 flush

# ============ Checkpoint 调优 ============
checkpoint_timeout = 15min           # 缩短 → 恢复快,WAL 增长小,IO 频繁
checkpoint_completion_target = 0.9   # 0.0-1.0,越大越平滑(默认 0.9)
max_wal_size = 1GB                   # WAL 总容量上限(超出会触发 checkpoint)
min_wal_size = 80MB                  # WAL 保留下限(避免频繁切换)

# ============ 段大小 ============
# wal_segment_size = 16MB            # 只能在 initdb 时设置
# 切换命令:postgres --wal-segsize=64 ...

# ============ FPW 与压缩 ============
full_page_writes = on                # 推荐保持开启
wal_compression = on                 # 15+ 推荐开,显著节省空间
wal_init_zero = on                   # 新 WAL 段初始化时清零,避免泄露

# ============ 归档(后续章节详述) ============
archive_mode = on                    # on / off / always
archive_command = 'cp %p /backup/wal/%f'  # 归档命令
archive_timeout = 60                 # 强制触发归档的最长间隔
```

### 2. 重要参数详解

#### `wal_level`

| 值         | 崩溃恢复 | 流复制 | 逻辑复制/解码 | 用途                          |
|------------|----------|--------|----------------|-------------------------------|
| `minimal`  | 是       | 否     | 否             | 内部最小,非复制环境          |
| `replica`  | 是       | 是     | 否             | **生产默认**,流复制够用      |
| `logical`  | 是       | 是     | 是             | 需逻辑复制或 CDC 时用         |

> 注意:`wal_level` 是 **非动态参数**,修改后必须重启,且对每个新写入的 WAL 生效。

#### `max_wal_size` / `min_wal_size`

- **`max_wal_size`**:WAL 在 Checkpoint 之间允许增长的最大值。超出会 **触发主动 Checkpoint** 而非报错。
- **`min_wal_size`**:WAL 段回收的最低水位线,防止过于频繁的段创建/删除。

```sql
-- 当前 WAL 段总数
SELECT count(*) FROM pg_ls_waldir();

-- 估算 WAL 占用
SELECT pg_size_pretty(count(*) * 16 * 1024 * 1024::bigint) AS approx_wal_size
FROM pg_ls_waldir();
```

---

## 七、控制文件 (pg_control)

### 1. pg_control 概述

**`pg_control`** 是 PostgreSQL 数据目录中一个 **8KB 的二进制文件**,记录数据库集群的关键元数据。它是 PostgreSQL 启动与恢复的"信息中枢":

- 上一次 Checkpoint 的位置(LSN)
- 数据库状态(`in production` / `shut down` / `in archive recovery`)
- 系统标识符(`system identifier`)
- 当前时间线 ID (`timeline ID`)
- 最旧的未冻结事务 ID
- WAL 段大小

**pg_control 一旦损坏或丢失,PostgreSQL 将无法启动,且无法通过 pg_resetwal 之外的工具恢复**。因此必须备份。

### 2. 查看 pg_control 内容

```sql
-- 当前 Checkpoint 状态
SELECT * FROM pg_control_checkpoint();

-- 当前系统信息
SELECT * FROM pg_control_system();

-- 恢复相关
SELECT * FROM pg_control_recovery();
```

**`pg_control_checkpoint()` 输出示例**:

```
-[ RECORD 1 ]--------+------------------------------
checkpoint_lsn      | 0/16B3B50
redo_lsn            | 0/16B3B50
timeline_id         | 1
prev_timeline_id    | 0
full_page_writes    | t
next_xid            | 0:743
next_oid            | 24588
next_multixact_id   | 1
next_multi_offset   | 0
oldest_xid          | 727
oldest_xact         | 0/16B3B50
oldest_active_xid   | 0
oldest_multi_xid    | 1
oldest_multi_xact   |
oldest_commit_ts_xid| 0
newest_commit_ts_xid| 0
```

### 3. 用 pg_controldata 查看

```bash
# 命令行工具(更详细)
$ pg_controldata $PGDATA
pg_control version number:            1300
Catalog version number:               202307071
Database cluster state:               in production
pg_control last modified:             2026-08-14 10:23:45
Latest checkpoint location:           0/16B3B50
Latest checkpoint's REDO location:    0/16B3B50
Latest checkpoint's REDO WAL file:    000000010000000000000001
Latest checkpoint's TimeLineID:       1
Latest checkpoint's PrevTimeLineID:   0
Latest checkpoint's full_page_writes: on
Latest checkpoint's NextXID:          0:743
Latest checkpoint's NextOID:          24588
...
```

### 4. pg_resetwal 紧急恢复

当 `pg_control` 严重损坏,或需要"跳到"某个时间点后,可用 `pg_resetwal` 强制重置:

```bash
# 必须停库
pg_ctl stop -D $PGDATA

# 重置 WAL,设置新 timeline、next XID 等
pg_resetwal -n -D $PGDATA    # -n 仅显示,不实际执行
pg_resetwal -D $PGDATA -o 1000 -x 2000
```

> **警告**:`pg_resetwal` 会 **跳过一致性检查**,可能产生数据不一致(已提交事务被回滚),仅在万不得已时使用,并需立即做全量备份。

---

## 八、日志系统总览

PostgreSQL 的"日志"涉及三大类:

1. **WAL 日志**:本章核心(1-7 节)
2. **服务器日志**:`pg_log/`(旧)/ `log_directory` 下的 csvlog/stderr
3. **扩展统计日志**:`pg_stat_statements` / `auto_explain`

下面先看服务器日志。

### 1. 服务器日志文件

```sql
-- 默认位置
SHOW log_directory;        -- 通常是 $PGDATA/pg_log(11+ 已弃用,推荐外部目录)
SHOW data_directory;       -- /var/lib/postgresql/16/main

-- 关键配置
SHOW logging_collector;    -- 是否启用日志收集(默认 off;生产强烈建议 on)
SHOW log_destination;      -- stderr / csvlog / jsonlog / syslog
SHOW log_filename;         -- 默认 postgresql-%Y-%m-%d_%H%M%S.log
SHOW log_rotation_age;     -- 1 day
SHOW log_rotation_size;    -- 10MB
```

```text
$PGDATA/pg_log/  (旧版本,PG 10 之后默认未启用)
├── postgresql-2026-08-14_100000.log
├── postgresql-2026-08-14_110000.log
├── postgresql-2026-08-14_120000.log
├── postgresql-2026-08-14_130000.csv      # csvlog 格式
└── postgresql-2026-08-14_140000.csv

# 或者外部目录
/var/log/postgresql/
├── postgresql-16-main.log
├── postgresql-16-main.log.1.gz
└── ...
```

### 2. 错误日志 (Error Log)

错误日志是 PostgreSQL **默认始终开启** 的日志,记录启动、运行、关闭过程中的 **错误、警告、提示信息**。

```ini
# postgresql.conf
logging_collector = on                 # 必须先开这个才能独立控制其他日志
log_destination = 'stderr'             # 或 'csvlog' / 'jsonlog' / 'syslog'
log_directory = 'log'                  # 相对 PGDATA 或绝对路径
log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log'
log_file_mode = 0600
log_truncate_on_rotation = on          # 同名时是否覆盖
log_rotation_age = 1d
log_rotation_size = 10MB
log_min_messages = warning             # panic/fatal/error/warning/notice/log/debug
```

**`log_min_messages` 等级**(`DEBUG5` 最详细,`PANIC` 最严重):

```
DEBUG5 < DEBUG4 < DEBUG3 < DEBUG2 < DEBUG1 < LOG < NOTICE < WARNING < ERROR < FATAL < PANIC
```

**错误日志示例**:

```text
2026-08-14 10:23:45.123 CST [12345] LOG:  database system is ready to accept connections
2026-08-14 10:23:50.456 CST [12350] WARNING:  out of shared memory
2026-08-14 10:24:01.789 CST [12360] ERROR:  duplicate key value violates unique constraint "users_pkey"
2026-08-14 10:24:01.790 CST [12360] DETAIL:  Key (id)=(12345) already exists.
2026-08-14 10:24:01.791 CST [12360] STATEMENT:  INSERT INTO users (id, name) VALUES (12345, 'alice');
```

### 3. 慢查询日志

PostgreSQL 慢查询日志由 **`log_min_duration_statement`** 控制(注意不是单独的"slow log",所有"耗时 SQL"都写入主日志)。

```ini
# postgresql.conf
log_min_duration_statement = 1s        # 超过 1s 的语句记录;设为 -1 关闭
log_lock_waits = on                   # 锁等待超 deadlock_timeout 也记
log_temp_files = 0                    # 临时文件大小,0 = 所有都记
log_autovacuum_min_duration = 0       # autovacuum 耗时记录
log_statement = 'none'                # 关闭全量 SQL 记录(默认)
```

**示例输出**:

```text
2026-08-14 11:00:01.123 CST [12345] LOG:  duration: 2345.678 ms  statement: SELECT * FROM orders WHERE user_id = 12345;
2026-08-14 11:00:01.456 CST [12345] DETAIL:  parameters: $1 = '12345'
2026-08-14 11:00:02.001 CST [12350] LOG:  duration: 5678.901 ms  statement:
                UPDATE users SET last_login = NOW() WHERE id = $1;
```

### 4. 通用日志(全量 SQL)

```ini
log_statement = 'all'        # none(默认) / ddl / mod / all
                              # ddl: 仅 DDL(CREATE/DROP/ALTER)
                              # mod: DDL + DML
                              # all: 包含 SELECT(高负载生产慎用)
```

> **生产环境强烈建议 `log_statement = none`**,全量 SQL 性能开销巨大,只在调试时短暂打开。

### 5. 启动日志与连接日志

```ini
# 启动信息
log_destination = 'stderr'      # 同时写 stderr,通常被 systemd 捕获

# 连接/断开日志
log_connections = on
log_disconnections = on
log_hostname = on               # 是否记录客户端主机名(需反向 DNS,谨慎)
log_line_prefix = '%t [%p]: db=%d,user=%u,app=%a,client=%h '
                            # 默认 '%t [%p-%l] %q%u@%d/%a from %h '
                            # %t 时间, %p PID, %u 用户, %d 数据库, %a 应用, %h 客户端
```

**典型连接日志**:

```text
2026-08-14 12:00:00.123 CST [12345] LOG:  connection received: host=10.0.0.5 port=54321 user=app_user database=mydb
2026-08-14 12:00:05.456 CST [12345] LOG:  disconnection: session time: 0:00:05.333 user=app_user database=mydb host=10.0.0.5 port=54321
```

### 6. Checkpoint / Connection / Lock 专项日志

```ini
# Checkpoint
log_checkpoints = on                # 记录 checkpoint 触发与完成
# 输出:
# LOG:  checkpoint complete: wrote 1234 buffers (3.0%); 0 transaction log file(s) added, 0 removed, 1 recycled
# LOG:  checkpoint starting: time

# Lock 等待
log_lock_waits = on                 # 锁等待超时(> deadlock_timeout)记录
# 输出:
# LOG:  process 12345 still waiting for ShareLock on transaction 67890 after 1000.123 ms
# DETAIL:  Process holding the lock: 12340. Wait queue: 12345.

# autovacuum
log_autovacuum_min_duration = 1000  # 记录超过 1s 的 autovacuum

# 其他
log_replication_commands = on      # 记录所有 replication 相关命令
log_temp_files = 1024              # 记录大于 1KB 的临时文件
log_timezone = 'Asia/Shanghai'     # 日志时区(默认 UTC)
```

---

## 九、日志文件管理

### 1. 日志轮转策略

| 参数                  | 默认      | 说明                                    |
|-----------------------|-----------|-----------------------------------------|
| `logging_collector`   | off       | 总开关,off 时日志走 stderr              |
| `log_destination`     | stderr    | stderr / csvlog / jsonlog / syslog      |
| `log_filename`        | `postgresql-%Y-%m-%d_%H%M%S.log` | 支持 strftime 模式             |
| `log_rotation_age`    | 1d        | 时间触发轮转                            |
| `log_rotation_size`   | 10MB      | 大小触发轮转                            |
| `log_truncate_on_rotation` | off | 同名时是否覆盖(off=追加,on=清空)    |
| `log_file_mode`       | 0600      | 新日志文件权限                          |

```ini
# 生产推荐
logging_collector = on
log_destination = 'csvlog'                    # CSV 格式便于解析
log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log'
log_rotation_age = 1d
log_rotation_size = 100MB
log_truncate_on_rotation = on
log_min_messages = warning
log_min_error_statement = error
log_min_duration_statement = 1s
log_lock_waits = on
log_checkpoints = on
log_connections = off                          # 高并发场景关闭,只记断开
log_disconnections = on
log_line_prefix = '%t [%p]: db=%d,user=%u,app=%a,client=%h '
```

### 2. csvlog 解析

```bash
# 启动 CSV 日志后,可以用 COPY 导入数据库
COPY postgres_log FROM '/var/log/postgresql/postgresql-2026-08-14_100000.csv'
WITH (FORMAT csv, HEADER true, DELIMITER ',');

# 或用 csvkit 处理
python3 -c "
import csv
with open('postgresql-2026-08-14_100000.csv') as f:
    reader = csv.reader(f)
    for row in reader:
        print(row)
"
```

**csvlog 字段**:`log_time`, `user_name`, `database_name`, `process_id`, `connection_from`, `session_id`, `session_line_num`, `command_tag`, `session_start_time`, `virtual_transaction_id`, `trx_id`, `error_severity`, `sql_state_code`, `message`, `detail`, `hint`, `internal_query`, `internal_query_pos`, `context`, `statement`, `params`, `application_name`, `backend_type`, `leader_pid`, `query_id`。

### 3. JSON Log (PG 15+)

```ini
log_destination = 'jsonlog'
```

每行一个 JSON 对象,字段与 csvlog 类似但便于日志系统直接消费(Filebeat/Logstash/Vector):

```json
{"timestamp":"2026-08-14 12:00:00.123+08","user":"app_user","dbname":"mydb","pid":12345,"remote_host":"10.0.0.5","session_id":"64b2...","line_num":1,"ps":"","tag":"","session_start":"2026-08-14 12:00:00+08","vxid":"3/45","xid":0,"message":"duration: 1234.567 ms  statement: SELECT ...","statement":"SELECT ...","application_name":"myapp"}
```

### 4. 日志归档与清理

```bash
# /etc/logrotate.d/postgresql
/var/log/postgresql/*.log {
    daily
    rotate 30
    missingok
    notifempty
    compress
    delaycompress
    notifempty
    create 0640 postgres postgres
    sharedscripts
    postrotate
        # csvlog 时需要通知 PG 切日志
        # stderr / syslog 模式下不需要
        if [ -f /var/run/postgresql/.s.PGSQL.5432 ]; then
            su - postgres -c "/usr/bin/pg_ctl -D /var/lib/postgresql/16/main reload"
        fi
    endscript
}
```

---

## 十、pg_stat_statements (查询统计)

### 1. 作用与价值

**`pg_stat_statements`** 是 PostgreSQL **必备的查询统计扩展**,等价于 MySQL 的 `performance_schema.events_statements_summary_by_digest` + `sys.statements_with_runtimes_in_95th_percentile`。它能让你:

- 一眼看到 **TOP N 慢查询**(按总耗时/平均耗时/IO)
- 定位 **写热点**(按 shared_blks_written / temp_blks_written)
- 找出 **资源消耗异常** 的 SQL(如大对象返回过多)
- 提供 **queryid**,关联 `EXPLAIN` 和 `auto_explain`

### 2. 安装与配置

```sql
-- 1. 修改 postgresql.conf,加入 shared_preload_libraries
-- shared_preload_libraries = 'pg_stat_statements,auto_explain'
-- (必须重启生效)

-- 2. 重启 PG
pg_ctl restart -D $PGDATA

-- 3. 创建扩展
CREATE EXTENSION pg_stat_statements;

-- 4. 验证
SELECT * FROM pg_available_extensions WHERE name = 'pg_stat_statements';
```

```ini
# postgresql.conf 中的 pg_stat_statements 专属参数
pg_stat_statements.max = 10000          # 保留的 SQL 种类上限
pg_stat_statements.track = top          # top / all / none
pg_stat_statements.track_utility = on   # 是否跟踪 SELECT 以外的语句
pg_stat_statements.track_planning = on  # 是否跟踪规划阶段耗时(13+)
pg_stat_statements.save = on            # 服务关闭时是否保存统计
```

### 3. 字段完整解读

`pg_stat_statements` 视图字段丰富,完整列表如下:

| 字段                      | 含义                                          |
|---------------------------|-----------------------------------------------|
| `userid`                  | 用户 OID                                      |
| `dbid`                    | 数据库 OID                                    |
| `toplevel`                | 是否顶层语句(true/false)                      |
| `queryid`                 | SQL 的 hash,等价于 MySQL 的 digest            |
| `query`                   | SQL 文本(可被截断到 `track_activity_query_size`)|
| `plans`                   | 计划次数(13+ 区分规划与执行)                 |
| `total_plan_time`         | 总规划耗时,ms(13+)                           |
| `min_plan_time`           | 最小规划耗时,ms                               |
| `max_plan_time`           | 最大规划耗时,ms                               |
| `mean_plan_time`          | 平均规划耗时,ms                               |
| `stddev_plan_time`        | 规划耗时标准差                                 |
| `calls`                   | 执行次数                                      |
| `total_exec_time`         | 总执行耗时,ms(注意:PG 13 之前叫 `total_time`)|
| `min_exec_time`           | 最小执行耗时,ms                               |
| `max_exec_time`           | 最大执行耗时,ms                               |
| `mean_exec_time`          | 平均执行耗时,ms                               |
| `stddev_exec_time`        | 执行耗时标准差                                 |
| `rows`                    | 影响/返回的总行数                             |
| `shared_blks_hit`         | shared_buffer 命中块数                        |
| `shared_blks_read`        | shared_buffer 未命中,需要从磁盘读的块数       |
| `shared_blks_dirtied`     | 该语句弄脏的块数                              |
| `shared_blks_written`     | 该语句刷盘的块数                              |
| `local_blks_*`            | 本地缓冲的命中/读/脏/写                       |
| `temp_blks_read`          | 读临时块数(磁盘排序/哈希大量数据)             |
| `temp_blks_written`       | 写临时块数                                    |
| `blk_read_time`           | 读盘耗时,ms(需 `track_io_timing=on`)          |
| `blk_write_time`          | 写盘耗时,ms                                   |

### 4. 慢查询 TOP N 排查

#### TOP 1:按总耗时

```sql
-- 找出"最耗时"的 SQL(很可能调用次数 × 平均耗时)
SELECT substring(query, 1, 100) AS query,
       calls,
       round(total_exec_time::numeric, 2)  AS total_ms,
       round(mean_exec_time::numeric, 2)   AS mean_ms,
       round((100 * total_exec_time / sum(total_exec_time) over ())::numeric, 2) AS pct
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 10;
```

#### TOP 2:按平均耗时(单次最慢)

```sql
-- 单次最慢的 SQL(可能调用次数少但每次都慢)
SELECT substring(query, 1, 100) AS query,
       calls,
       round(mean_exec_time::numeric, 2) AS mean_ms,
       round(max_exec_time::numeric, 2)  AS max_ms
FROM pg_stat_statements
WHERE calls > 5                            -- 过滤掉偶然执行
ORDER BY mean_exec_time DESC
LIMIT 10;
```

#### TOP 3:写盘最多的 SQL

```sql
-- 写盘最多的 SQL(找 DML 热点、批量写)
SELECT substring(query, 1, 100) AS query,
       calls,
       shared_blks_dirtied,
       shared_blks_written,
       temp_blks_written
FROM pg_stat_statements
ORDER BY shared_blks_dirtied + shared_blks_written DESC
LIMIT 10;
```

#### TOP 4:缓存命中率最低

```sql
-- 缓存命中率(命中率 < 95% 通常意味着 shared_buffers 不够)
SELECT substring(query, 1, 80) AS query,
       calls,
       shared_blks_hit,
       shared_blks_read,
       round(100.0 * shared_blks_hit / NULLIF(shared_blks_hit + shared_blks_read, 0), 2) AS hit_pct
FROM pg_stat_statements
WHERE shared_blks_read > 0
ORDER BY shared_blks_read DESC
LIMIT 10;
```

#### TOP 5:临时文件最多的 SQL(磁盘排序)

```sql
-- 临时块多 = ORDER BY / DISTINCT / GROUP BY / JOIN 内存不够
SELECT substring(query, 1, 100) AS query,
       calls,
       temp_blks_read,
       temp_blks_written
FROM pg_stat_statements
ORDER BY temp_blks_written + temp_blks_read DESC
LIMIT 10;
```

#### TOP 6:重置统计

```sql
-- 重置统计(谨慎,会清空所有 pg_stat_statements 数据)
SELECT pg_stat_statements_reset();

-- 验证 queryid(用 EXPLAIN 对应同样的 SQL)
EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM users WHERE id = 12345;
-- 注意 EXPLAIN 输出里"Query Identifier: 1234567890"
-- 在 pg_stat_statements 中查找 queryid = 1234567890 的行
```

---

## 十一、auto_explain (自动 EXPLAIN 日志)

### 1. 作用

`auto_explain` 让你 **不必手动 EXPLAIN 慢查询**,PostgreSQL 会在 **后台自动把执行计划写入日志**。生产中排查偶发性慢 SQL 极为有用。

### 2. 启用方法

```ini
# 1. shared_preload_libraries 加入 auto_explain
shared_preload_libraries = 'pg_stat_statements,auto_explain'

# 2. postgresql.conf 配置
auto_explain.log_min_duration = '1s'      # 超过 1s 的语句输出 EXPLAIN
auto_explain.log_analyze = on              # 输出 ANALYZE(实际执行统计)
auto_explain.log_buffers = on              # 输出 BUFFERS(块命中)
auto_explain.log_format = 'text'           # text / json / yaml
auto_explain.log_nested_statements = on    # 嵌套语句也记
auto_explain.log_timing = on               # 输出每节点耗时
auto_explain.log_triggers = on             # 触发器执行也记
auto_explain.sample_rate = 1.0             # 采样率,1.0 = 全量(13+)
```

> 与 `pg_stat_statements` 不同,`auto_explain` **可以只载入而不创建扩展**,因为它通过 shared_preload_libraries 启动。

### 3. 输出示例

```text
2026-08-14 13:00:00.123 CST [12345] LOG:  duration: 2345.678 ms  plan:
  Query Text: SELECT * FROM orders WHERE user_id = 12345 ORDER BY created_at DESC LIMIT 100;
  Limit  (cost=123.45..125.67 rows=100 width=120) (actual time=2300.123..2340.456 rows=100 loops=1)
    ->  Sort  (cost=123.45..125.67 rows=234 width=120) (actual time=2300.001..2330.000 rows=100 loops=1)
          Sort Key: created_at DESC
          Sort Method: top-N heapsort  Memory: 32kB
          ->  Index Scan using idx_orders_user on orders  (cost=0.43..80.12 rows=234 width=120) (actual time=0.123..2200.000 rows=234 loops=1)
                Index Cond: (user_id = 12345)
  Planning Time: 0.234 ms
  Execution Time: 2340.567 ms
2026-08-14 13:00:00.123 CST [12345] LOG:  duration: 2345.678 ms  statement: ...
```

### 4. 与 pg_stat_statements 联动

```ini
# 同时启用,获得:pg_stat_statements 看统计 + auto_explain 看计划
shared_preload_libraries = 'pg_stat_statements,auto_explain'
pg_stat_statements.track = top
auto_explain.log_min_duration = '2s'
auto_explain.log_analyze = on
auto_explain.log_buffers = on
```

---

## 十二、WAL 与 MySQL redo log 对比

| 维度                | PostgreSQL WAL                                  | MySQL InnoDB redo log                      |
|---------------------|-------------------------------------------------|--------------------------------------------|
| **本质**            | 数据库核心结构,贯穿崩溃恢复/复制/归档           | InnoDB 引擎私有,仅用于崩溃恢复            |
| **作用范围**        | 崩溃恢复 + 流复制 + 逻辑复制 + PITR + MVCC 支持  | 崩溃恢复(部分支持 MVCC,通过 undo)         |
| **物理/逻辑**       | 物理 + 逻辑混合(Heap 元组级)                    | 物理(8KB 页级字节修改)                    |
| **段大小**          | 默认 16MB(initdb 时定)                          | 48MB(8.0+ 默认),循环写                    |
| **写入方式**        | 顺序追加,**循环与归档并存**                     | 循环覆盖(写完旧段被覆盖)                  |
| **归档**            | 原生支持 `archive_mode`/`archive_command`       | 由 binlog 承担归档责任                     |
| **复制支持**        | **WAL 直接支撑**流复制(物理/逻辑)              | 不直接支撑,需 binlog + relay log          |
| **Checkpoint**      | checkpointer 显式触发,有 fpw 保护              | 隐式推进(LSN),有 fpw 保护                 |
| **commit 等价**     | `pg_current_wal_lsn() >= commit_lsn` 即可      | redo log 已 fsync 即可                    |
| **sync 方式**       | wal_sync_method(fdatasync/fsync/open_sync)      | innodb_flush_method(O_DIRECT/fsync)        |
| **异步提交**        | `synchronous_commit = off`                      | `innodb_flush_log_at_trx_commit=0/2`       |
| **统计**            | `pg_stat_wal`/`pg_stat_bgwriter`/`pg_stat_replication` | `Innodb_log_*` / `SHOW SLAVE STATUS` |
| **磁盘满处理**      | stop/panic(必须保留 pg_wal)                     | 写 redo 失败时挂起                         |

> 总结:**PostgreSQL 把 WAL 做成"全功能主干"**,MySQL 把 redo log 仅做"持久性辅助"。

---

## 十三、WAL 在复制中的作用

### 1. 流复制(Streaming Replication)

PostgreSQL 流复制的核心是 **walreceiver**(备库)持续接收 **walsender**(主库)发送的 WAL 记录,并通过 **startup 进程** 应用到备库。

```
┌──────────────────────────────────────────────────────────────────────┐
│                       流复制架构                                      │
│                                                                      │
│  ┌─────────────────────┐           ┌─────────────────────┐          │
│  │      主库            │           │      备库            │          │
│  │  ┌───────────────┐  │  WAL 流   │  ┌───────────────┐  │          │
│  │  │  walsender    │  │ ────────► │  │  walreceiver  │  │          │
│  │  │  (后端进程)   │  │  TCP/SSL  │  │  (后端进程)   │  │          │
│  │  └───────┬───────┘  │           │  └───────┬───────┘  │          │
│  │          │          │           │          │          │          │
│  │          ▼          │           │          ▼          │          │
│  │  ┌───────────────┐  │           │  ┌───────────────┐  │          │
│  │  │   WAL 文件     │  │           │  │   WAL 文件     │  │          │
│  │  │  pg_wal/*.wal │  │           │  │  pg_wal/*.wal │  │          │
│  │  └───────────────┘  │           │  └───────┬───────┘  │          │
│  │                     │           │          │          │          │
│  │  ┌───────────────┐  │           │  ┌───────▼───────┐  │          │
│  │  │  Data Files   │  │           │  │  startup 进程 │  │          │
│  │  │  (基库)        │  │           │  │  (应用 WAL)  │  │          │
│  │  └───────────────┘  │           │  └───────┬───────┘  │          │
│  │                     │           │          │          │          │
│  │                     │           │  ┌───────▼───────┐  │          │
│  │                     │           │  │  Data Files   │  │          │
│  │                     │           │  │  (备库)        │  │          │
│  │                     │           │  └───────────────┘  │          │
│  └─────────────────────┘           └─────────────────────┘          │
└──────────────────────────────────────────────────────────────────────┘
```

**关键过程**:

1. **主库 walsender** 启动后,根据备库发来的 `START_REPLICATION` 槽位开始发送 WAL
2. 备库 **walreceiver** 把接收的 WAL 写入本地 `pg_wal`
3. 备库 **startup 进程** 持续读取并应用 WAL
4. 备库 `replay_lsn` 不断推进,主库 `pg_current_wal_lsn` 与之差 = 复制延迟字节

**主库关键配置**:

```ini
wal_level = replica
max_wal_senders = 10                         # 允许的最大 walsender 进程数
wal_keep_size = '1GB'                        # 备库断开时保留的 WAL(>=13)
                                              # 老版本是 wal_keep_segments
max_replication_slots = 10                   # 复制槽上限
synchronous_commit = on                      # 'on' / 'remote_apply' / 'remote_write' / 'off' / 'local'
synchronous_standby_names = 'standby1'       # 同步备库列表
```

**主库创建复制槽**(避免 WAL 被覆盖):

```sql
SELECT * FROM pg_create_physical_replication_slot('standby1_slot');
-- 返回:slot_name, lsn

SELECT slot_name, restart_lsn, active, active_pid FROM pg_replication_slots;
```

**监控复制延迟**:

```sql
-- 主库视角:每个备库的延迟
SELECT client_addr,
       state,
       sync_state,                                -- sync / async / potential
       pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) AS replay_lag_bytes,
       replay_lag,                                -- 时间维度(9.2+)
       write_lag, flush_lag                       -- 10+ 区分 write/flush/replay 延迟
FROM pg_stat_replication;

-- 主库视角:WAL 生成速率
SELECT pg_wal_lsn_diff(pg_stat_get_wal_lsn(), '0/0') AS total_wal_bytes,
       pg_size_pretty(pg_wal_lsn_diff(pg_stat_get_wal_lsn(), '0/0')) AS total_wal_size;
```

### 2. 逻辑复制(Logical Replication)

逻辑复制通过 `pgoutput` 插件把 WAL 解码为 **逻辑变更**(INSERT/UPDATE/DELETE),跨版本、跨大版本也能用。

```sql
-- 主库发布
CREATE PUBLICATION pub_orders FOR TABLE orders;

-- 备库订阅
CREATE SUBSCRIPTION sub_orders
    CONNECTION 'host=primary port=5432 dbname=mydb user=repl'
    PUBLICATION pub_orders;
```

**逻辑复制与物理流复制的关键差异**:

| 维度           | 物理流复制                    | 逻辑复制                            |
|----------------|-------------------------------|-------------------------------------|
| 复制粒度        | 整个集群(实例级)              | 表级(可筛选)                        |
| 版本要求        | 主备需同主版本                | 可跨大版本(13→16)                   |
| 写入目标        | 完整恢复(可读+可提升)         | 通常只读,行级更新                   |
| 底层依赖        | WAL 物理格式                  | WAL 解码(pgoutput)                 |
| 冲突处理        | 无冲突(主备二进制一致)         | 需处理主键冲突、UPDATE 丢失         |
| 性能开销        | 较低                          | 较高(解码 + 重新执行)               |
| 用途            | HA、读写分离、PITR            | 数据分发、跨库同步、CDC             |

---

## 十四、WAL 在 PITR (时间点恢复) 中的作用

### 1. PITR 原理

**PITR (Point-In-Time Recovery)** = 全量备份(`pg_basebackup`) + WAL 归档 + 恢复到指定时间点/LSN/事务 ID。

```text
  时间轴:  T0        T1        T2 (备份点)        T3 (恢复目标)
           │         │         │                 │
           ▼         ▼         ▼                 ▼
  basebackup:  ───────────────────────────────────┐
                                                 │
  WAL 归档:   ┌──────────────────────────────────┘
              │ 000000010000000000000001
              │ 000000010000000000000002
              │ ...
              │ 0000000100000000000000AB  (恢复到此处)
              ▼
        recovery.conf / postgresql.auto.conf
        recovery_target_time = '2026-08-14 12:00:00'
```

### 2. 配置 PITR

```ini
# postgresql.conf
wal_level = replica
archive_mode = on
archive_command = 'cp %p /backup/wal_archive/%f'      # 上线生产时
# 或用 pgbackrest / barman / wal-g

# 持续做基础备份
pg_basebackup -D /backup/base_20260814 -Fp -Xs -P
```

### 3. 恢复流程

```bash
# 1. 停库
pg_ctl stop -D $PGDATA

# 2. 恢复基础备份
rm -rf $PGDATA && cp -r /backup/base_20260814 $PGDATA
chown -R postgres:postgres $PGDATA

# 3. 创建恢复配置文件(postgresql.auto.conf)
cat >> $PGDATA/postgresql.auto.conf <<EOF
restore_command = 'cp /backup/wal_archive/%f %p'
recovery_target_time = '2026-08-14 11:30:00'
recovery_target_action = 'pause'  # 'pause' / 'promote' / 'shutdown'
EOF

# 4. 启动(进入恢复模式)
pg_ctl start -D $PGDATA
# PostgreSQL 启动后:
#   - 应用 restore_command 拉取归档的 WAL
#   - 按顺序重放,直到 recovery_target_time
#   - 暂停或自动提升为主库

# 5. 验证 + 提升
SELECT pg_is_in_recovery();        -- true 表示还在恢复
# 确认无误后:
SELECT pg_wal_replay_pause();      -- 暂停(若 recovery_target_action = 'pause')
# 检查无误后:
pg_ctl promote -D $PGDATA
# 或 SELECT pg_promote();
```

### 4. 新时间线 (Timeline)

PITR 恢复成功后,PostgreSQL 自动 **生成新时间线**,避免与原始时间线冲突:

```text
原始:00000001 00000000 00000042  (恢复起点)
新:  00000002 00000000 00000001  (恢复后第一个 WAL 段,TL=2)
```

> 每次 `pg_ctl promote` / `pg_promote()` / 新的 PITR 操作都会产生新时间线。`archive_command` 必须使用 `%f` 保持文件名完整,否则归档到同一目录会冲突。

### 5. PITR 高级选项

```ini
# 恢复到指定 LSN(更精确)
recovery_target_lsn = '0/16B3B50'

# 恢复到指定事务 ID
recovery_target_xid = '743'

# 恢复到指定命名恢复点(由 pg_create_restore_point 创建)
recovery_target_name = 'before_migration_20260814'

# 恢复后行为
recovery_target_action = 'promote'   # 默认 promote,可设 'pause' 或 'shutdown'
```

---

## 十五、监控 WAL 增长

### 1. 关键监控视图

#### `pg_stat_wal`(13+)

```sql
-- 当前 WAL 活动(13+)
SELECT * FROM pg_stat_wal;
-- 字段:wal_records, wal_fpi, wal_bytes, wal_buffers_full, wal_write,
--       wal_sync, wal_write_time, wal_sync_time, stats_reset

-- 计算 WAL 写入速率
SELECT wal_records,
       pg_size_pretty(wal_bytes) AS total_wal,
       wal_write,
       wal_write_time
FROM pg_stat_wal;
```

#### `pg_stat_bgwriter`

```sql
-- bgwriter 活动统计
SELECT * FROM pg_stat_bgwriter;
-- 关键字段:
-- checkpoints_timed     = 按时间触发的 checkpoint 次数
-- checkpoints_req       = 按请求触发的 checkpoint 次数(因 max_wal_size)
-- buffers_checkpoint    = checkpoint 刷脏页数
-- buffers_clean         = bgwriter 主动刷脏页数
-- buffers_backend       = backend 自己刷脏页数
-- buffers_backend_fsync = backend fsync 次数
-- maxwritten_clean      = bgwriter 写满多少轮
-- buffers_alloc         = 分配的缓冲数
```

#### `pg_stat_database`

```sql
-- 各数据库的 WAL 统计(13+)
SELECT datname,
       xact_commit,
       xact_rollback,
       blks_read,
       blks_hit,
       tup_inserted,
       tup_updated,
       tup_deleted,
       pg_size_pretty(temp_bytes) AS temp_size
FROM pg_stat_database
WHERE datname NOT IN ('template0', 'template1');
```

### 2. WAL 增长告警指标

```sql
-- 1. 监控 WAL 段数量
SELECT count(*) AS walseg_count,
       pg_size_pretty(count(*) * 16 * 1024 * 1024::bigint) AS approx_size
FROM pg_ls_waldir();

-- 2. 监控"待 flush 字节"(主库写盘跟不上时)
SELECT pg_wal_lsn_diff(pg_current_wal_lsn(), pg_current_wal_flush_lsn())
       AS pending_flush_bytes;

-- 3. 监控 Checkpoint 频率
SELECT checkpoints_timed, checkpoints_req,
       round(100.0 * checkpoints_req / NULLIF(checkpoints_timed + checkpoints_req, 0), 2) AS req_pct
FROM pg_stat_bgwriter;
-- 理想:checkpoints_req 占比 < 5%
-- 若高,说明 max_wal_size 太小,checkpoint 频繁

-- 4. 监控 checkpoint 距离
SELECT EXTRACT(EPOCH FROM (now() - stats_reset)) AS seconds_since_reset,
       checkpoints_timed,
       checkpoints_req
FROM pg_stat_bgwriter;
```

### 3. 告警阈值参考

| 指标                                    | 告警阈值       | 含义                          |
|----------------------------------------|----------------|-------------------------------|
| WAL 段数 (pg_ls_waldir 计数)          | > 100          | 接近 max_wal_size 上限        |
| `pending_flush_bytes`                  | > 100MB        | 写盘跟不上                    |
| `checkpoints_req / total`             | > 30%          | max_wal_size 触底频繁         |
| `buffers_backend` / `buffers_clean`    | > 50%          | bgwriter 没刷够,backend 自己刷 |
| `replay_lag` (备库)                    | > 30s          | 复制延迟过高                  |
| `wal_buffers_full` (13+)              | 持续 > 0       | wal_buffers 太小              |

---

## 十六、WAL 性能调优

### 1. SSD 上的 WAL 配置

```ini
# SSD 优化参数
wal_sync_method = fdatasync              # SSD 推荐 fdatasync(默认)
wal_buffers = 64MB                       # 高并发写可加大
wal_writer_delay = 100ms                 # 周期可缩短(默认 200ms)
wal_writer_flush_after = 4MB             # 每次 flush 字节加大(默认 1MB)
max_wal_size = 4GB                       # SSD 容量大,可放大
min_wal_size = 1GB
checkpoint_timeout = 30min              # 拉长 checkpoint 间隔
checkpoint_completion_target = 0.9       # 默认 0.9,保持
full_page_writes = on                    # 保持 on
wal_compression = on                     # 开启 zstd/lz4
```

### 2. 异步提交 `synchronous_commit`

| 值                 | COMMIT 等待                                | 性能影响          | 风险                       |
|--------------------|--------------------------------------------|-------------------|----------------------------|
| `on` (默认)        | WAL 本地 fsync                              | 基线              | 无(0 丢数据)              |
| `remote_apply`     | 本地 fsync + 备库 replay                    | 较慢              | 0 丢数据(备库 0 延迟)     |
| `remote_write`     | 本地 fsync + 备库 write                    | 中等              | 备库 0 延迟,主库可能丢     |
| `local`            | 仅本地 fsync                                | 同 on              | 异步复制无损(等价 on)     |
| `off`              | 仅写 wal_buffers,不等 fsync                | **最快**           | 丢 0~wal_writer_delay 窗口数据 |

```ini
# 异步复制场景:可用 on(local) + 异步备库,安全且高效
synchronous_commit = on
synchronous_standby_names = ''           # 关闭同步备库

# 强一致场景(金融):
synchronous_commit = remote_apply
synchronous_standby_names = 'standby1'

# 高性能场景(社交、feed,可容忍丢 200ms 数据):
synchronous_commit = off
wal_writer_delay = 50ms                   # 配合缩短,减小丢数据窗口
```

> 关键要点:`synchronous_commit = off` 时,数据库崩溃会丢 **最多 `wal_writer_delay + wal_writer_flush_after / write_throughput` 窗口** 的已提交事务,业务侧需自行接受该风险。

### 3. synchronous_commit vs local fsync 对比

```
┌────────────────────────────────────────────────────────────────────┐
│        synchronous_commit vs local fsync 关系图                     │
│                                                                    │
│   synchronous_commit = on                                          │
│     └─► COMMIT 必须等 WAL 落到本地磁盘(write+fsync)               │
│         ├─ 同步备库存在:还要等备库确认(remote_write/apply)         │
│         └─ 异步备库:不等,本地 fsync 后立即返回                     │
│                                                                    │
│   synchronous_commit = off                                         │
│     └─► COMMIT 不等本地 fsync,只等 wal_buffers 写入                │
│         └─ 实际落盘依赖 wal_writer 周期(默认 200ms)               │
│         └─ 性能最高,但 OS/DB 崩溃会丢数据                         │
│                                                                    │
│   local fsync(参数 fsync = on)                                     │
│     └─► 控制 PostgreSQL 是否调用 fsync 系统调用                   │
│     └─► = off 时 WAL 写入会绕过 fsync,可能丢更多数据               │
│     └─► 生产环境**绝不能**关闭 fsync                               │
│                                                                    │
│   关系:                                                            │
│   synchronous_commit = on 时,受 fsync 与 wal_sync_method 控制      │
│   synchronous_commit = off 时,只等写 wal_buffers,不等 fsync        │
└────────────────────────────────────────────────────────────────────┘
```

### 4. 实战调优清单

```ini
# 1. 高并发写 OLTP(电商订单、支付)
wal_buffers = 64MB
wal_writer_delay = 100ms
wal_writer_flush_after = 4MB
synchronous_commit = on                    # 强一致
max_wal_size = 4GB
checkpoint_timeout = 15min
wal_compression = on
full_page_writes = on

# 2. 批量导入 / 数据仓库
wal_buffers = 16MB                         # 批量写一般不需要大 wal_buffers
synchronous_commit = off                   # 批量可异步(配合业务策略)
max_wal_size = 8GB
checkpoint_timeout = 60min
wal_compression = on
# 导入前:SET maintenance_work_mem = '2GB';
# 导入前:ALTER TABLE xxx SET UNLOGGED; (导入完再 SET LOGGED)
# 导入前:SET synchronous_commit = off;
# 导入后:VACUUM ANALYZE;

# 3. 读多写少 / 高可用备库
wal_buffers = 16MB
synchronous_commit = on
synchronous_standby_names = 'standby1'     # 至少 1 同步备库
hot_standby = on
hot_standby_feedback = on                  # 防备库查询冲突

# 4. 极端性能 / 容忍少量丢
synchronous_commit = off
wal_writer_delay = 10ms
wal_writer_flush_after = 16MB
fsync = on                                 # 永远保持 on
full_page_writes = on                      # 永远保持 on
# 搭配异步备库
```

### 5. 调优效果验证

```sql
-- 1. 调优前:记录基线
CREATE TABLE wal_bench AS
SELECT pg_current_wal_lsn() AS start_lsn;

-- 2. 跑测试(典型业务负载)
-- ... do your load test ...

-- 3. 调优后:对比 WAL 增长量
SELECT pg_wal_lsn_diff(pg_current_wal_lsn(), (SELECT start_lsn FROM wal_bench)) AS wal_bytes;

-- 4. 调优前后:tps、延迟对比
-- 5. 持续观察:checkpoint_req 占比、wal_buffers_full 等
```

---

## 十七、核心要点速记

### 1. WAL 速记表

| 概念            | 关键点                                                  |
|-----------------|---------------------------------------------------------|
| **WAL**         | Write-Ahead Logging,**先写日志再写数据**                |
| **pg_wal**      | WAL 段文件目录(10 之前是 `pg_xlog`)                     |
| **WAL 段**      | 默认 16MB,文件名 `TTTTTTTT XXXXXXXX YYYYYYYY`          |
| **LSN**         | 64 位,标识 WAL 字节位置;`pg_current_wal_lsn()` 看最新 |
| **XLogRec**     | 单条 WAL 记录,含 XLOG_HEAP_INSERT / UPDATE / COMMIT 等 |
| **wal_buffers** | 共享内存中的 WAL 缓冲,默认 16MB                          |
| **WAL Writer**  | 后台进程,周期性把 wal_buffers 刷到磁盘                  |
| **Checkpoint**  | checkpointer 刷脏页,推进 redo LSN                       |
| **FPW**         | FULL PAGE WRITES,首次改页写整页(防部分写)               |
| **pg_control**  | 控制文件,记录最后 checkpoint LSN、状态等                |

### 2. LSN 函数速记

```sql
pg_current_wal_lsn()           -- 已写入 wal_buffers 的最新 LSN
pg_current_wal_flush_lsn()     -- 已 fsync 的最新 LSN
pg_current_wal_insert_lsn()    -- 已插入的 LSN(同 write)
pg_wal_lsn_diff(a, b)          -- 两个 LSN 的字节差
pg_walfile_name(lsn)           -- LSN → WAL 文件名
pg_walfile_name_offset(lsn)    -- LSN → (文件名, 段内偏移)
pg_control_checkpoint()        -- 看控制文件 Checkpoint 信息
```

### 3. Checkpoint 触发条件速记

```
- checkpoint_timeout  到期(默认 5min)
- max_wal_size        触底(默认 1GB)
- 手动 CHECKPOINT    命令
- 智能关闭/shutdown  时
- pg_basebackup       时
- pg_control          满
```

### 4. WAL vs MySQL redo log 速记

```
PostgreSQL WAL: 物理+逻辑混合,支撑崩溃恢复/流复制/逻辑复制/PITR 全功能
MySQL redo log: 纯物理,只支撑崩溃恢复;复制与归档走 binlog
PostgreSQL:    一份 WAL 打天下
MySQL:         redo(持久) + binlog(复制) 两份日志
```

### 5. 日志系统速记

```
错误日志:    log_min_messages = warning(始终记录)
慢查询日志:  log_min_duration_statement = 1s(写在主日志里)
通用日志:    log_statement = 'all'(生产慎用)
Checkpoint:  log_checkpoints = on
pg_stat_statements: SQL 统计(必备)
auto_explain: 自动 EXPLAIN 慢 SQL(必备)
```

### 6. 调优速记

```
OLTP:        wal_buffers=64MB, synchronous_commit=on, max_wal_size=4GB
批量导入:     synchronous_commit=off, 临时表+UNLOGGED
备库延迟大: 增大 wal_keep_size, 启用复制槽
WAL 增长快: 调大 max_wal_size, 延长 checkpoint_timeout
高一致性:    synchronous_commit=remote_apply + 同步备库
高吞吐:      synchronous_commit=off + wal_writer_delay 缩短
```

### 7. 监控速记

```sql
-- 关键监控 SQL 一句话
SELECT count(*) AS walsegs,
       pg_size_pretty(count(*) * 16 * 1024 * 1024::bigint) AS size,
       pg_wal_lsn_diff(pg_current_wal_lsn(), pg_current_wal_flush_lsn()) AS pending
FROM pg_ls_waldir();
```

### 8. 一句话总结

- **WAL = 顺序写日志换随机写数据页**,PostgreSQL 用一份 WAL 统一支撑崩溃恢复、流复制、逻辑复制、PITR 四大能力。
- **LSN 是 WAL 的"时间戳"**,贯穿所有相关视图(Checkpoint、复制槽、备份)。
- **Checkpoint 决定恢复起点**,`checkpoint_timeout` + `max_wal_size` 共同控制节奏。
- **pg_stat_statements + auto_explain** 是性能调优的"双剑",前者给统计,后者给计划。
- **生产标准**:`wal_level=replica`、`full_page_writes=on`、`wal_compression=on`、`synchronous_commit=on`、日志系统全开。
- **监控必看**:WAL 段数、pending flush、checkpoint req 占比、bgwriter 比例、备库 replay_lag。

---

## 十八、实战排查案例

### 案例 1:磁盘被 pg_wal 撑满

**现象**:监控告警磁盘使用率 95%,df 看到 `pg_wal` 占用 1.2TB(原本 200GB 数据库,异常增长 6 倍)。

**排查步骤**:

```bash
# 1. 查看 WAL 段数
psql -c "SELECT count(*) FROM pg_ls_waldir();"
-- count = 75000  (异常! 7.5 万段 ≈ 1.2TB)

# 2. 看 max_wal_size 设置
psql -c "SHOW max_wal_size;"
-- 1GB (正常,不该有这么多段)

# 3. 看归档是否健康
psql -c "SELECT archived_count, failed_count, last_archived_time, last_failed_time FROM pg_stat_archiver;"
-- failed_count = 234, last_failed_time = 2026-08-14 10:00
```

**根因**:归档命令 `archive_command = 'cp %p /backup/wal/%f'` 中 `/backup` 目录被运维误删,归档失败,但 WAL 段无法回收(因为未归档,可能仍被备库需要)。

**解决**:

```bash
# 1. 恢复归档目标
mkdir -p /backup/wal
chown postgres:postgres /backup/wal

# 2. 手动触发归档
psql -c "SELECT pg_switch_wal();"    -- 强制切换到下一段
psql -c "CHECKPOINT;"

# 3. 验证
psql -c "SELECT count(*) FROM pg_ls_waldir();"
-- 正常应回到 16~64 段

# 4. 长期监控
# 把 archive_command 加上告警:
archive_command = 'test ! -f /backup/wal/%f && cp %p /backup/wal/%f || (echo "WAL archive failed" | mail -s "PG ALERT" dba@company.com; exit 1)'
```

**预防**:

```ini
# 设置 min_wal_size 防止极端情况下 WAL 无限增长(无法完全防止)
min_wal_size = '512MB'

# 监控告警
SELECT count(*) > 1000 AS alarm FROM pg_ls_waldir();
```

### 案例 2:checkpoint_req 比例过高(IO 抖动)

**现象**:业务反馈数据库周期性卡顿,监控 `iostat` 看到每 5-10 分钟有 1-2 秒 100% util。

**排查**:

```sql
-- 1. 看 checkpoint 触发比例
SELECT checkpoints_timed, checkpoints_req,
       round(100.0 * checkpoints_req / NULLIF(checkpoints_timed + checkpoints_req, 0), 2) AS req_pct
FROM pg_stat_bgwriter;
-- timed=120, req=580, req_pct=82.86%   ← 异常!理想 < 5%

-- 2. 看 WAL 增长
SELECT count(*) AS walsegs FROM pg_ls_waldir();
-- count=64  (16MB × 64 = 1GB,正好等于 max_wal_size)

-- 3. 看 checkpoint 距离
SELECT now() - stats_reset, last_archived_time, last_archived_wal
FROM pg_stat_archiver;
```

**根因**:`max_wal_size=1GB` 在当前写入量下太容易触底,导致几乎所有 checkpoint 都是 req 类型,IO 突发。

**优化**:

```ini
# 调大 max_wal_size,让 timed checkpoint 主导
max_wal_size = '8GB'
min_wal_size = '2GB'
checkpoint_timeout = '30min'    # 配合延长
```

**验证**:

```sql
-- 等 1 小时后,再次检查
SELECT checkpoints_timed, checkpoints_req,
       round(100.0 * checkpoints_req / NULLIF(checkpoints_timed + checkpoints_req, 0), 2) AS req_pct
FROM pg_stat_bgwriter;
-- req_pct < 10%  ← 优化成功
```

### 案例 3:WAL 写入延迟引发 tps 抖动

**现象**:`tps` 监控偶尔从 5w 掉到 1w,持续 200ms 后恢复。`iostat` 看到 `w_await` 偶发飙升。

**排查**:

```sql
-- 1. 看 WAL 写入统计
SELECT * FROM pg_stat_wal;
-- wal_buffers_full = 23456   ← 异常! wal_buffers 太小
-- wal_write = 1200000
-- wal_write_time = 56789

-- 2. 看 wal_buffers
SHOW wal_buffers;
-- 16MB
```

**根因**:`wal_buffers=16MB` 在 tps 5w 时,backend 需要把 XLogRec 换出/换入,影响 tps。

**优化**:

```ini
wal_buffers = '64MB'              # 4 倍
wal_writer_flush_after = '4MB'    # walwriter 更频繁落盘,减少 wal_buffers 压力
```

**验证**:

```sql
-- 持续观察 30 分钟
SELECT wal_buffers_full FROM pg_stat_wal;
-- 应该是 0 或极小
```

### 案例 4:逻辑复制延迟

**现象**:逻辑复制 `sub_orders` 延迟 10 分钟。

**排查**:

```sql
-- 1. 看订阅状态
SELECT subname, subenabled, subslotname
FROM pg_subscription;

-- 2. 看逻辑复制 worker 状态
SELECT pid, state, write_lsn, flush_lsn, replay_lsn,
       pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) AS lag_bytes
FROM pg_stat_replication;

-- 3. 看订阅的表同步状态
SELECT relname, srsubstate, srsublsn
FROM pg_subscription_rel
WHERE srsubid = (SELECT oid FROM pg_subscription WHERE subname='sub_orders');
-- srsubstate: i=initialize, d=data sync, s=sync, r=ready
-- 若大量处于 'i' 或 'd',初次同步还没完
```

**常见原因与处理**:

| 原因                          | 处理方式                                            |
|-------------------------------|----------------------------------------------------|
| 订阅创建后大表初次同步未完成  | 等待同步完成;或用 `COPY ... FROM` 预热            |
| 订阅表无主键 / 无 REPLICA IDENTITY | 修改 `ALTER TABLE xxx REPLICA IDENTITY FULL;`  |
| 备库 DML 冲突                 | 设置 `sub_skip_lsn` 跳过冲突 LSN                  |
| 备库写入慢 / 长事务           | 检查备库长事务,关闭大量 UPDATE                   |
| 主库大事务                    | 主库改写为小批量,减少单事务 WAL 量                |
| 网络抖动                      | 调整 `wal_receiver_timeout`                       |

### 案例 5:崩溃后无法启动(pg_control 损坏)

**现象**:PG 异常断电,启动报错:

```text
FATAL: could not read from control file: Success
```

**排查与恢复**:

```bash
# 1. 先备份当前数据(防止二次损坏)
cp -r $PGDATA /backup/pgdata_damaged

# 2. 用 pg_resetwal 强制重置
pg_resetwal -D $PGDATA

# 3. 启动
pg_ctl start -D $PGDATA

# 4. 立即做全量备份(因为数据可能不一致)
pg_basebackup -D /backup/base_after_reset -Fp -Xs
```

**注意**:`pg_resetwal` 会 **跳过一致性检查**,部分已提交事务可能被丢弃,需立即用 `pg_dump` 全量导出,然后 `pg_dump` 恢复到新实例。

### 案例 6:WAL 归档爆满 / 归档清理

**现象**:`/backup/wal` 目录占 5TB 磁盘,实际只需要保留 7 天。

**解决**:

```bash
# 1. 写清理脚本
cat > /usr/local/bin/clean_wal.sh <<'EOF'
#!/bin/bash
# 保留 7 天的 WAL
find /backup/wal -name "*.gz" -mtime +7 -delete
find /backup/wal -type f -mtime +7 -delete
EOF
chmod +x /usr/local/bin/clean_wal.sh

# 2. crontab
0 3 * * * /usr/local/bin/clean_wal.sh
```

> 更好的方案:用 **pgbackrest** / **barman** / **wal-g**,它们有内置的 WAL 保留策略、加密、压缩,以及元数据管理。

### 案例 7:用 pg_stat_statements 抓出隐藏的慢 SQL

**现象**:应用整体 tps 没变化,但 P99 延迟升高。

**排查**:

```sql
-- 1. 先看 5 秒以上的 SQL
SELECT substring(query, 1, 100) AS query,
       calls,
       round(mean_exec_time::numeric, 2) AS mean_ms,
       round(max_exec_time::numeric, 2)  AS max_ms
FROM pg_stat_statements
WHERE calls > 5
ORDER BY mean_exec_time DESC
LIMIT 20;

-- 2. 找出"看似不慢但执行次数极多"的 SQL(对延迟贡献大)
SELECT substring(query, 1, 100) AS query,
       calls,
       round(total_exec_time::numeric, 2) AS total_ms,
       round(mean_exec_time::numeric, 2)  AS mean_ms
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 10;

-- 3. 找出"扫了很多块但返回行数少"的 SQL(索引缺失)
SELECT substring(query, 1, 100) AS query,
       calls,
       shared_blks_read,
       rows,
       round(shared_blks_read::numeric / NULLIF(rows, 0), 2) AS blocks_per_row
FROM pg_stat_statements
WHERE rows > 0 AND shared_blks_read > 1000
ORDER BY blocks_per_row DESC
LIMIT 10;
```

**典型发现**:

- 某 BI 报表 SQL 每天 1000 次,平均 50ms,但 `shared_blks_read=2.3M` —— 加索引后降到 0.5ms
- 某 ORM 的 N+1 查询,200ms/次,每天 5 万次 —— 修改 ORM 批量化

### 案例 8:auto_explain 排查偶发慢查询

**现象**:业务说"每天下午 3 点有个 5 秒查询",但白天不出现。

**排查**:

```ini
# 临时开启 auto_explain
shared_preload_libraries = 'pg_stat_statements,auto_explain'
auto_explain.log_min_duration = '3s'    # 3s 以上就记
auto_explain.log_analyze = on
auto_explain.log_buffers = on
auto_explain.log_nested_statements = on
auto_explain.log_timing = on
# 重启生效
pg_ctl restart -D $PGDATA
```

```bash
# 等下午 3 点后,grep 日志
grep "duration: " /var/log/postgresql/postgresql-2026-08-14_150000.log | head -20
```

**日志输出**(包含完整执行计划):

```text
LOG:  duration: 5234.567 ms  plan:
  Query Text: SELECT count(*) FROM orders WHERE created_at BETWEEN ...;
  Aggregate  (cost=123.45..125.67 rows=1 width=8) (actual time=5230.000..5230.001 rows=1 loops=1)
    ->  Index Scan using idx_orders_created on orders  (cost=0.43..80.12 rows=234 width=0) (actual time=10.123..4500.000 rows=89000 loops=1)
          Index Cond: (created_at >= '2026-08-14 00:00:00'::timestamp AND created_at < '2026-08-15 00:00:00'::timestamp)
          Rows Removed by Filter: 999100
  Planning Time: 0.234 ms
  Execution Time: 5234.567 ms
```

**根因**:`Rows Removed by Filter: 999100` —— 索引扫描了大量无关数据,索引选择性低。

**优化**:

```sql
-- 1. 联合索引,提升选择性
CREATE INDEX CONCURRENTLY idx_orders_created_user
    ON orders (created_at, user_id)
    WHERE status = 'paid';

-- 2. 重新跑测试,从 5s 降到 50ms
```

### 案例 9:synchronous_commit 性能与一致性权衡

**场景**:某 SaaS 应用,业务可容忍 1s 丢数据,但要求 tps 5000+。

**基线**(synchronous_commit=on):

```
tps: 3200
p99 延迟: 45ms
```

**调优**(synchronous_commit=off):

```ini
synchronous_commit = off
wal_writer_delay = '10ms'
wal_writer_flush_after = '8MB'
```

**效果**:

```
tps: 5800  (+81%)
p99 延迟: 18ms  (-60%)
```

**风险**:DB/OS 崩溃会丢 **最多约 10ms** 窗口的已提交事务数据,业务可接受(有业务侧数据校验)。

**对于"既想要一致性,又想减少延迟"**:

```ini
# 用同步备库 + local fsync
synchronous_commit = on                # 本地落盘
synchronous_standby_names = ''         # 关闭同步备库
# 异步备库自己跑,不影响主库
```

### 案例 10:WAL 段命名与时间线切换(恢复后复制槽失效)

**现象**:PITR 恢复后,原备库的复制槽无法继续工作。

**原因**:PITR 恢复成功后,主库时间线从 1 变为 2,原备库订阅的 slot 仍指向 timeline 1。

**解决**:

```sql
-- 在恢复后,删除旧 slot,创建新 slot
SELECT pg_drop_replication_slot('old_standby_slot');
SELECT pg_create_physical_replication_slot('new_standby_slot');

-- 备库需要重新 basebackup
pg_basebackup -h new_primary -D /var/lib/postgresql/16/main -Fp -Xs -P -U repl
# 修改 recovery.conf(postgresql.auto.conf)中的 primary_slot_name
primary_slot_name = 'new_standby_slot'
```

---

## 十九、附录:WAL 关键参数速查

### 1. 必知参数清单

```ini
# ---------- WAL 基础 ----------
wal_level                  = replica          # 核心
wal_buffers                = 16MB
wal_writer_delay           = 200ms
wal_writer_flush_after     = 1MB
wal_sync_method            = fdatasync
wal_segment_size           = 16MB             # 仅 initdb 时

# ---------- 段控制 ----------
max_wal_size               = 1GB
min_wal_size               = 80MB
wal_keep_size              = 0                # 无复制槽时保留
max_wal_senders            = 10
max_replication_slots      = 10

# ---------- 压缩与安全 ----------
full_page_writes           = on
wal_compression            = on
wal_init_zero              = on
wal_log_hints              = on               # 备库/重放优化

# ---------- Checkpoint ----------
checkpoint_timeout         = 5min
checkpoint_completion_target = 0.9
checkpoint_warning         = 30s

# ---------- bgwriter ----------
bgwriter_delay             = 50ms
bgwriter_lru_maxpages      = 100
bgwriter_lru_multiplier    = 2.0
bgwriter_flush_after       = 512 * 8KB

# ---------- 复制同步 ----------
synchronous_commit         = on
synchronous_standby_names  = ''
wal_receiver_timeout       = 60s
wal_receiver_create_temp_slot = off

# ---------- 归档 ----------
archive_mode               = off              # 启用 PITR 时设 on
archive_command            = ''
archive_timeout            = 0

# ---------- 同步控制 ----------
fsync                      = on               # 永远 on
synchronous_commit         = on
```

### 2. 参数动态性速查

| 参数                      | 动态修改 | 说明                                    |
|---------------------------|----------|-----------------------------------------|
| `wal_level`               | 否       | 需重启                                  |
| `wal_buffers`             | 否       | 需重启                                  |
| `wal_writer_delay`        | 是       | SET/Reload                              |
| `wal_writer_flush_after`  | 是       | Reload                                  |
| `max_wal_size`            | 是       | Reload                                  |
| `min_wal_size`            | 是       | Reload                                  |
| `checkpoint_timeout`      | 是       | Reload                                  |
| `checkpoint_completion_target` | 是   | Reload                                  |
| `synchronous_commit`      | 是       | 会话级/全局 SET                         |
| `archive_mode`            | 否       | 需重启                                  |
| `archive_command`         | 是       | Reload                                  |
| `full_page_writes`        | 是       | Reload                                  |
| `wal_compression`         | 是       | Reload                                  |
| `max_wal_senders`         | 否       | 需重启                                  |
| `max_replication_slots`   | 否       | 需重启                                  |

### 3. 关键监控指标(综合)

```sql
-- 综合健康度查询(汇总)
SELECT
    -- WAL 体积
    (SELECT count(*) FROM pg_ls_waldir()) AS walseg_count,
    pg_size_pretty((SELECT count(*) * 16 * 1024 * 1024 FROM pg_ls_waldir())::bigint) AS wal_size,
    -- Checkpoint 比例
    (SELECT round(100.0 * checkpoints_req / NULLIF(checkpoints_timed + checkpoints_req, 0), 2)
       FROM pg_stat_bgwriter) AS checkpoint_req_pct,
    -- bgwriter 效率
    (SELECT buffers_checkpoint FROM pg_stat_bgwriter) AS bufs_by_checkpoint,
    (SELECT buffers_clean FROM pg_stat_bgwriter) AS bufs_by_bgwriter,
    (SELECT buffers_backend FROM pg_stat_bgwriter) AS bufs_by_backend,
    -- 复制延迟(主库)
    (SELECT pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn)
       FROM pg_stat_replication LIMIT 1) AS replica_lag_bytes,
    -- 归档健康
    (SELECT failed_count FROM pg_stat_archiver) AS archive_failed_count;
```

### 4. 一句话总结(终极版)

> **PostgreSQL 的 WAL 是其"灵魂日志"**:一份 WAL 撑起崩溃恢复、流复制、逻辑复制、PITR 四大能力;LSN 是它的"时间戳",Checkpoint 是它的"里程碑",pg_stat_statements 是它的"显微镜"。掌握 WAL,就掌握了 PostgreSQL 的核心;玩转日志系统,就具备了生产 DBA 的基本能力。

---

## 二十、附录:常用工具与命令速查

### 1. WAL 工具全家福

PostgreSQL 自带与生态中关于 WAL/日志的工具非常丰富,按用途归类如下:

```text
┌──────────────────────────────────────────────────────────────────────┐
│                  WAL 与日志相关工具                                  │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  内置工具(postgresql 自带):                                          │
│  ├─ pg_basebackup           全量基础备份,产生新时间线               │
│  ├─ pg_waldump              解析 WAL 段内容(类似 mysqlbinlog)       │
│  ├─ pg_receivewal           持续接收 WAL 到本地/远程(用于归档)      │
│  ├─ pg_recvlogical          逻辑复制接收端                          │
│  ├─ pg_resetwal             强制重置 WAL(pg_control 损坏时)         │
│  ├─ pg_controldata          查看 pg_control 内容                    │
│  ├─ pg_waldump              转储 WAL 段为可读文本                    │
│  └─ pg_xlogdump             PG 10 之前叫这个,现已弃用               │
│                                                                      │
│  第三方备份/归档工具:                                                │
│  ├─ pgbackrest              最流行的 PG 备份工具,内置 WAL 管理      │
│  ├─ barman                  EnterpriseDB 出品,支持远程备份         │
│  ├─ wal-g                   现代备份工具,支持 S3/GCS/Azure          │
│  └─ pg_rman                  轻量级备份                             │
│                                                                      │
│  监控/分析:                                                          │
│  ├─ pg_stat_statements      SQL 统计(必备扩展)                     │
│  ├─ auto_explain            自动 EXPLAIN                            │
│  ├─ pg_stat_statements_reset() 重置统计                            │
│  ├─ pg_profile              基于 pg_stat_statements 的报告工具      │
│  ├─ pg_activity             实时活跃会话视图                       │
│  └─ pgmonitor / pganalyze   商业/开源监控                          │
│                                                                      │
│  日志解析:                                                            │
│  ├─ pg_badger               日志分析神器,生成 HTML 报告            │
│  └─ csvkit + grep           CSV 日志基本处理                        │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 2. pg_waldump 使用

**`pg_waldump`** 是 PostgreSQL 自带的 WAL 内容解析器,等价于 MySQL 的 `mysqlbinlog`,把二进制 WAL 记录转成可读文本:

```bash
# 解析指定 WAL 段
pg_waldump /var/lib/postgresql/16/main/pg_wal/000000010000000000000042

# 限制解析的 LSN 范围
pg_waldump -s 0/16B0000 -e 0/16C0000 /var/lib/postgresql/16/main/pg_wal/000000010000000000000042

# 跟随(类似 tail -f)
pg_waldump -f /var/lib/postgresql/16/main/pg_wal/000000010000000000000042

# 限制每个记录只显示前 N 字节
pg_waldump -n 64 /var/lib/postgresql/16/main/pg_wal/000000010000000000000042

# 仅显示某些资源管理器
pg_waldump -r Heap /var/lib/postgresql/16/main/pg_wal/000000010000000000000042
pg_waldump -r Transaction /var/lib/postgresql/16/main/pg_wal/000000010000000000000042
pg_waldump -r Btree /var/lib/postgresql/16/main/pg_wal/000000010000000000000042
```

**输出示例**:

```text
rmgr: Heap        len (rec/tot):     62/    62, tx:        743, lsn: 0/16B3B50, prev 0/16B3B10, desc: INSERT+INIT off 1, blkref #0: rel 1663/16384/24576 blk 0
rmgr: Transaction len (rec/tot):     34/    34, tx:        743, lsn: 0/16B3B90, prev 0/16B3B50, desc: COMMIT 2026-08-14 10:23:45.123456 CST
rmgr: Btree       len (rec/tot):     85/    85, tx:        744, lsn: 0/16B3BB4, prev 0/16B3B90, desc: INSERT_LEAF off 1, blkref #0: rel 1663/16384/24580 blk 12
```

字段说明:`rmgr`(资源管理器,代表变更类型)、`len`(记录长度)、`tx`(事务 ID)、`lsn`(记录位置)、`prev`(前一条 LSN)、`desc`(具体描述)。

### 3. pg_basebackup 备份工具

```bash
# 基础全量备份(默认 plain 格式)
pg_basebackup -h localhost -U repl -D /backup/base_20260814 -Fp -Xs -P -v
#   -Fp: plain 格式
#   -Xs: 流式 WAL(备份期间一并把 WAL 拉过来)
#   -P:  显示进度
#   -v:  详细

# 备份为 tar 格式
pg_basebackup -D /backup/base_20260814.tar -Ft -Xs -P

# 指定备份标签文件
pg_basebackup -D /backup/base_20260814 -Fp -Xs -P -l "full_backup_20260814"

# 从备库做备份(减少主库压力,11+)
pg_basebackup -h standby_host -U repl -D /backup/base_20260814 -Fp -Xs -P
# 需 standby 上 hot_standby = on,且备库有 replication 权限
```

**备份元数据**(关键文件):

```text
/backup/base_20260814/
├── base/                          # 数据文件
├── global/                        # 系统表
├── pg_wal/                        # 备份期间拉到的 WAL(若 -Xs stream)
├── backup_label                   # 备份元数据(START WAL LSN、备份方法、时间)
├── tablespace_map                 # 表空间映射(若有)
└── ...
```

`backup_label` 是恢复时的重要依据:

```text
START WAL LSN: 0/3000028
CHECKPOINT LSN: 0/3000060
BACKUP METHOD: streamed
BACKUP FROM: primary
START TIME: 2026-08-14 10:00:00
LABEL: full_backup_20260814
```

### 4. pg_receivewal 持续归档

当不想(或不能)用 `archive_command` 归档时,可以用 `pg_receivewal` 持续接收:

```bash
# 把远程 PG 的 WAL 持续拉到本地目录
pg_receivewal -h primary -U repl -D /backup/wal_streaming -n -S my_slot -v
#   -n: 不要在拉完后 fsync(由 -S 复制槽控制)
#   -S: 创建复制槽(避免 WAL 被覆盖)
#   -v: 详细

# 限速
pg_receivewal -h primary -D /backup/wal -S my_slot --max-rate=100M

# 用压缩槽(13+,需 wal_compression=on)
pg_receivewal -h primary -D /backup/wal -S my_slot --compress=zstd:1
```

### 5. pg_badger 日志分析

**`pg_badger`** 是 PostgreSQL 生态最强的日志分析工具,基于 csvlog 报告化,输出 HTML 报告(图表+统计)。

```bash
# 安装
apt install pgbadger
# 或从 GitHub 安装最新版
cpan App::pgbadger

# 生成报告
pgbadger /var/log/postgresql/postgresql-2026-08-14*.csv \
    -o /var/www/html/pg_report_20260814.html \
    --prefix '%t [%p]: db=%d,user=%u,app=%a,client=%h '

# 增量报告(每天执行,输出到同一文件)
pgbadger /var/log/postgresql/postgresql-2026-08-15*.csv \
    -o /var/www/html/pg_report.html \
    --incremental --samples 5

# 实时跟踪(从 stdin)
pg_ctl -D $PGDATA stop  # 假设有 pipe
pgbadger --watch-job=5 /var/log/postgresql/postgresql.csv
```

**报告内容**:

- SQL 统计(总查询数、慢查询、QPS 趋势)
- 锁等待、Checkpoint 频率
- 临时文件、autovacuum 统计
- 错误码分布、会话时长分布
- 主机/用户/应用名/数据库维度分析

### 6. pg_stat_statements 工具联动

**`pg_profile`** 是基于 `pg_stat_statements` 的报告工具,类似 Oracle 的 AWR:

```bash
# 安装
git clone https://github.com/zubkov-andrei/pg_profile
cd pg_profile
make install

# 创建扩展
psql -d mydb -c "CREATE EXTENSION pg_profile;"

# 采集快照
psql -d mydb -c "SELECT profile.take_sample();"

# 生成报告(需有两次及以上快照)
psql -d mydb -c "SELECT profile.get_report('1', '2');"
# 输出一个 HTML 报告到 /var/www/html/...
```

**报告内容**:连接、tps、负载、TOP SQL、Checkpoint、WAL、Buffer、锁、索引使用、对象统计等。

### 7. PostgreSQL 关键系统视图(WAL 相关)

| 视图                              | 主要内容                            |
|-----------------------------------|-------------------------------------|
| `pg_stat_wal` (13+)               | WAL 写入统计                        |
| `pg_stat_bgwriter`                | bgwriter/checkpoint 统计            |
| `pg_stat_database`                | 各数据库的 commit/rollback、块 I/O  |
| `pg_stat_replication`             | 流复制延迟/状态                     |
| `pg_stat_replication_slots`       | 复制槽状态                          |
| `pg_stat_archiver`                | 归档成功/失败次数                   |
| `pg_stat_activity`                | 当前活跃会话                        |
| `pg_stat_user_tables`             | 表级 I/O、扫描统计                  |
| `pg_stat_user_indexes`            | 索引使用统计                        |
| `pg_statio_user_tables`           | 表级块 I/O(更详细)                  |
| `pg_ls_waldir()`                  | pg_wal 目录文件列表                 |
| `pg_ls_archive_statusdir()`       | 归档状态文件列表                    |
| `pg_ls_dir()`                     | 任意目录文件列表                    |
| `pg_ls_tmpdir()`                  | 临时文件列表                        |
| `pg_stat_ssl`                     | SSL 连接统计                        |
| `pg_stat_gssapi`                  | GSSAPI 认证统计                     |

### 8. 常用诊断 SQL(综合)

```sql
-- ====== WAL 状态 ======
SELECT pg_current_wal_lsn(),
       pg_current_wal_flush_lsn(),
       pg_wal_lsn_diff(pg_current_wal_lsn(), '0/0') AS total_wal_bytes;

-- ====== 复制状态 ======
SELECT client_addr, state, sync_state,
       pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) AS lag_bytes,
       replay_lag
FROM pg_stat_replication;

-- ====== 检查点 ======
SELECT checkpoints_timed, checkpoints_req,
       buffers_checkpoint, buffers_clean, buffers_backend,
       round(100.0 * checkpoints_req /
             NULLIF(checkpoints_timed + checkpoints_req, 0), 2) AS req_pct
FROM pg_stat_bgwriter;

-- ====== 归档 ======
SELECT archived_count, failed_count,
       last_archived_time, last_failed_time, last_archived_wal
FROM pg_stat_archiver;

-- ====== TOP 5 慢查询 ======
SELECT substring(query, 1, 80) AS query,
       calls, total_exec_time, mean_exec_time
FROM pg_stat_statements
ORDER BY total_exec_time DESC LIMIT 5;

-- ====== 缓存命中率 ======
SELECT sum(blks_hit)::float / NULLIF(sum(blks_hit) + sum(blks_read), 0) AS hit_rate
FROM pg_stat_database;

-- ====== 长事务 ======
SELECT pid, state, query_start, xact_start,
       NOW() - xact_start AS xact_duration
FROM pg_stat_activity
WHERE xact_start IS NOT NULL
ORDER BY xact_start LIMIT 10;
```

### 9. 配置文件模板(可直接套用)

```ini
# ============ PostgreSQL WAL 生产配置模板 ============

# === WAL 基础 ===
wal_level = replica
wal_buffers = 64MB
wal_writer_delay = 200ms
wal_writer_flush_after = 1MB
wal_sync_method = fdatasync
wal_compression = on
full_page_writes = on
wal_init_zero = on
wal_log_hints = on
wal_skip_threshold = 2MB                  # 12+,小事务可跳过 FPW

# === Checkpoint ===
checkpoint_timeout = 15min
checkpoint_completion_target = 0.9
max_wal_size = 4GB
min_wal_size = 1GB
checkpoint_warning = 30s

# === bgwriter ===
bgwriter_delay = 50ms
bgwriter_lru_maxpages = 1000
bgwriter_lru_multiplier = 2.0
bgwriter_flush_after = 2MB

# === 复制(主库) ===
max_wal_senders = 10
max_replication_slots = 10
wal_keep_size = 1GB
hot_standby = on
hot_standby_feedback = off
wal_receiver_timeout = 60s
wal_receiver_create_temp_slot = off

# === 同步(可选) ===
synchronous_commit = on
synchronous_standby_names = ''             # 按需填写 'standby1'

# === 归档(启用 PITR 时) ===
archive_mode = on
archive_command = 'test ! -f /backup/wal/%f && cp %p /backup/wal/%f'  # 实际用 pgbackrest
archive_timeout = 60

# === 共享预加载 ===
shared_preload_libraries = 'pg_stat_statements,auto_explain'

# === pg_stat_statements ===
pg_stat_statements.max = 10000
pg_stat_statements.track = top
pg_stat_statements.track_utility = on
pg_stat_statements.track_planning = on
pg_stat_statements.save = on

# === auto_explain ===
auto_explain.log_min_duration = '3s'
auto_explain.log_analyze = on
auto_explain.log_buffers = on
auto_explain.log_timing = on
auto_explain.log_nested_statements = on
auto_explain.log_format = 'text'
auto_explain.sample_rate = 1.0

# === 日志 ===
logging_collector = on
log_destination = 'csvlog'
log_directory = 'log'
log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log'
log_rotation_age = 1d
log_rotation_size = 100MB
log_truncate_on_rotation = on
log_min_messages = warning
log_min_error_statement = error
log_min_duration_statement = 1s
log_lock_waits = on
log_checkpoints = on
log_temp_files = 10MB
log_autovacuum_min_duration = 1s
log_line_prefix = '%t [%p]: db=%d,user=%u,app=%a,client=%h '
log_timezone = 'Asia/Shanghai'

# === 关键开关 ===
fsync = on
synchronous_commit = on
full_page_writes = on
```

### 10. 性能基线指标(经验值)

| 指标                          | 健康范围                | 异常处理                                  |
|------------------------------|------------------------|-------------------------------------------|
| `cache hit ratio`            | > 99%                  | < 95% 需调大 `shared_buffers`             |
| `checkpoints_req / total`    | < 5%                   | 调大 `max_wal_size` / `checkpoint_timeout` |
| `buffers_backend / total`    | < 10%                  | bgwriter 调小 `bgwriter_delay`             |
| `replay_lag` (备库)          | < 1s                   | 网络 / 备库 IO 排查                        |
| `wal_buffers_full`           | 0                      | 调大 `wal_buffers`                        |
| `Innodb_log_waits` (MySQL 对比) | 0                   | 调大 `innodb_log_buffer_size`             |
| `archive_command failed`     | 0                      | 立即修复归档命令                            |
| `deadlocks / sec`            | < 0.1                  | 应用层事务顺序问题                          |
| `temp_blks_written`          | 趋势平稳               | 突增 = 大排序 / 哈希,调大 `work_mem`      |
| `pg_stat_activity idle`      | 比例合理               | 长时间 idle in transaction = 长事务        |

### 11. 与 MySQL 关键参数对照表

| 用途                  | PostgreSQL                | MySQL                              |
|-----------------------|---------------------------|-------------------------------------|
| 写日志到本地盘        | `wal_writer_delay`        | `innodb_flush_log_at_trx_commit`   |
| 日志缓冲大小          | `wal_buffers`             | `innodb_log_buffer_size`           |
| 单日志段大小          | `wal_segment_size`        | `innodb_log_file_size`             |
| 异步提交              | `synchronous_commit=off`  | `innodb_flush_log_at_trx_commit=2` |
| Checkpoint 触发时间   | `checkpoint_timeout`      | 隐式(由 redo log 推进)              |
| WAL 总量上限          | `max_wal_size`            | redo log 总大小(2 × log_file_size)  |
| 归档                  | `archive_command`         | binlog 归档                         |
| 慢查询阈值            | `log_min_duration_statement` | `long_query_time`                |
| 通用日志              | `log_statement='all'`     | `general_log=ON`                   |
| 错误日志              | `logging_collector`       | `log_error`                        |
| 自动清理              | autovacuum                | 自动 purge                          |
| 查询统计              | `pg_stat_statements`      | `performance_schema` + `sys`      |
| 自动 EXPLAIN          | `auto_explain`            | 无内置,需第三方(`pt-visual-explain`)|

### 12. 常见误区与最佳实践

| 误区                                     | 正确做法                                                    |
|------------------------------------------|-------------------------------------------------------------|
| "WAL 段越多越好,可以一直回放"            | WAL 段越多意味着恢复越慢,要平衡 `max_wal_size` 与 PITR 需求 |
| "`synchronous_commit=off` 永远不会丢数据" | OS/DB 崩溃仍会丢 0~wal_writer_delay 窗口数据                |
| "`fsync=off` 性能最高"                   | 关闭 fsync = 主动丢数据,生产绝对不允许                    |
| "checkpoint 越频繁越好"                  | 太频繁会刷脏页过多 IO;要平衡恢复时间和写入性能              |
| "关掉 full_page_writes 性能更好"         | 关闭后部分写损坏可能丢数据,**严禁生产关闭**                  |
| "WAL 文件越多磁盘越好"                   | 单段小(16MB)归档粒度细,单段大(1GB)切换开销小,选 16MB 足够  |
| "`wal_level=minimal` 性能最高"           | 不支持复制,只能在无复制场景用                               |
| "auto_explain 开小一点没事"               | `log_min_duration` 设太短会大量日志,先设 2-3s 调试          |
| "归档命令不用测试"                       | 归档命令必须 **真实可执行 + 监控告警**,生产第一道防线       |
| "备库延迟大无所谓"                       | 延迟大 = 备库可能已不健康,及时告警处理                      |

### 13. PostgreSQL 与 MySQL 选型建议

| 场景                        | 推荐        | 理由                                  |
|----------------------------|-------------|---------------------------------------|
| 复杂 SQL / OLAP / 报表     | PostgreSQL  | 优化器强、SQL 完整度高                |
| 简单 OLTP / 读多写少       | 都可         | 性能接近                              |
| 高吞吐写入                  | 视情况       | 都需要调优;PG 用 UNLOGGED 临时表优化批量 |
| 强一致 + 同步复制          | PostgreSQL  | 同步复制实现更原生,基于 LSN 简单可靠  |
| 跨库迁移 / 异构复制        | MySQL 较成熟 | binlog 生态丰富(MySQL → TiDB/ES)      |
| 严格 SQL 标准              | PostgreSQL  | 标准 SQL 兼容性更好                   |
| 简单运维 / 团队熟悉        | MySQL       | 学习成本低,工具丰富                  |
| 复杂扩展 / 自定义类型      | PostgreSQL  | 扩展机制强大                          |

### 14. 终极速记(运维/面试常用)

**问题 1:PostgreSQL 的 WAL 段默认多大?如何修改?**

答:默认 16MB。**只能在 `initdb` 时通过 `--wal-segsize` 修改**,运行时不可改。

**问题 2:COMMIT 是否一定等 WAL fsync?**

答:`synchronous_commit=on` 时,COMMIT 必须等 WAL 本地 fsync 成功才返回;`synchronous_commit=off` 时,COMMIT 只等 wal_buffers 写入,不等 fsync,可能丢 0~`wal_writer_delay` 窗口数据。

**问题 3:WAL 与 binlog 有什么区别?**

答:PostgreSQL 的 WAL 同时承担崩溃恢复、复制、归档、PITR;MySQL 的 binlog 仅做复制与恢复,崩溃恢复由 redo log 负责。PostgreSQL 一份日志走天下,MySQL 拆 redo+binlog 两份。

**问题 4:如何查看当前 LSN?**

```sql
SELECT pg_current_wal_lsn();
```

**问题 5:Checkpoint 触发的三种方式?**

答:1) `checkpoint_timeout` 到期;2) `max_wal_size` 触底;3) 手动 `CHECKPOINT` 或 `pg_basebackup` 等。

**问题 6:`full_page_writes` 是什么?为什么不能关?**

答:FPW 是"首次修改页时写整页",防止 OS 部分写导致页撕裂。关闭后崩溃可能无法恢复,生产 **必须保持 on**。

**问题 7:`pg_stat_statements` 与 `auto_explain` 区别?**

答:`pg_stat_statements` 提供 SQL 统计(总耗时、平均耗时、调用次数、IO 量);`auto_explain` 把执行计划(EXPLAIN ANALYZE)写入日志。两者互补,生产必备。

**问题 8:异步复制可能丢多少数据?**

答:主库已落盘但未传备库的数据,加上 `wal_receiver_timeout` 内的未确认数据。实际丢失量取决于网络和 wal_keep_size。

**问题 9:如何加快 PITR 恢复速度?**

答:1) 增大 `restore_command` 并行(用 `pgbackrest`);2) 减小 WAL 段大小(16MB 优于 1GB);3) 减少需要重放的 WAL 量(恢复到较近的备份点);4) SSD + 强 CPU。

**问题 10:`synchronous_commit=remote_apply` 是什么?**

答:不仅等本地 fsync,还要等备库把 WAL replay 到备库数据文件。比 `on` 慢(多一倍延迟),但能保证"主备查询结果一致"(读备库不延迟)。

### 15. 关键里程碑与版本特性

| 版本   | 关键特性                                                    |
|--------|-------------------------------------------------------------|
| PG 7.x | 引入流复制、流复制槽                                        |
| PG 8.3 | HOT(Heap-Only Tuples) 优化,减少 WAL 体积                  |
| PG 9.0 | 流复制(Streaming Replication) 正式版                       |
| PG 9.4 | `pg_stat_statements` 正式内置                               |
| PG 9.5 | `pg_rewind` 解决时间线重对齐                                |
| PG 9.6 | 并行顺序扫描、复制槽改进                                    |
| PG 10  | `pg_xlog` → `pg_wal` 重命名,逻辑复制 GA,声明式分区表       |
| PG 11  | `pg_waldump` 改进,`pg_basebackup` 支持备库,`wal_keep_size` 取代 `wal_keep_segments` |
| PG 12  | `recovery.conf` → `postgresql.auto.conf`,`wal_skip_threshold` |
| PG 13  | `pg_stat_wal` 视图,`pg_stat_statements` 区分 plan/exec 耗时,`wal_compression=zstd` |
| PG 14  | `pg_stat_replication_slots` 改进,`pg_log_backend_memory_contexts` |
| PG 15  | JSON log、`wal_compression` 多种算法,`pg_basebackup` 支持增量 |
| PG 16  | 逻辑复制 worker 池化,性能提升                              |
| PG 17  | 进一步优化逻辑复制,改进 pg_stat_statements                 |

### 16. 延伸阅读

**官方文档**:

- [PostgreSQL Documentation - WAL](https://www.postgresql.org/docs/current/wal.html)
- [PostgreSQL Documentation - pg_stat_statements](https://www.postgresql.org/docs/current/pgstatstatements.html)
- [PostgreSQL Documentation - Logging](https://www.postgresql.org/docs/current/runtime-config-logging.html)
- [PostgreSQL Documentation - Backup and Restore](https://www.postgresql.org/docs/current/backup.html)
- [PostgreSQL Documentation - High Availability](https://www.postgresql.org/docs/current/high-availability.html)

**社区资源**:

- [The Internals of PostgreSQL (interdb.jp)](https://www.interdb.jp/pg/) — 最深入的 PG 内核讲解
- [PostgreSQL Wiki - WAL](https://wiki.postgresql.org/wiki/WAL)
- [PostgreSQL Mailing List](https://www.postgresql.org/list/)
- [pgconf.org](https://pgconf.org/) — PG 大会
- [PostgreSQL 中国社区](https://postgres.cn/)

**书籍推荐**:

- 《PostgreSQL 修炼之道:从小工到专家》
- 《PostgreSQL 技术内幕:事务处理与恢复机制深度剖析》
- 《PostgreSQL 高可用实战:从入门到精通》
- 《PostgreSQL 实战》(Manning)
- 《PostgreSQL 9.0 High Performance》(Packt)

### 17. 写在最后

WAL 是 PostgreSQL 区别于 MySQL 的最核心架构差异之一,理解 WAL,等于理解了 PostgreSQL 的"灵魂":

- **WAL 让 PostgreSQL 拥有"时间机器"** —— PITR、逻辑复制、流复制都基于它
- **WAL 让 PostgreSQL 拥有"复制 + 恢复"** —— 一份日志撑起整个生态
- **WAL 让 PostgreSQL 拥有"可观测性"** —— LSN 是它的"时间戳",所有监控都围绕它
- **WAL 让 PostgreSQL 拥有"灵活性"** —— 不同 `wal_level` 满足不同场景

掌握 WAL,你就掌握了 PostgreSQL 性能调优、故障恢复、容量规划、架构设计的核心能力;玩转日志系统,你就具备了生产 DBA 的"第一性原理"。

> **记住一句核心话**:**PostgreSQL 的 WAL 永远先于数据页落盘,这是 ACID 中 D (Durability) 的真正实现。**

---

## 二十一、全章结束语

至此,PostgreSQL 的 WAL 与日志系统全部讲完。从 WAL 的基本概念、文件结构、LSN 机制,到写入流程、Checkpoint、配置参数;从控制文件到服务器日志,从 `pg_stat_statements` 到 `auto_explain`;从与 MySQL 的对比到复制与 PITR 的应用,从监控告警到性能调优与实战案例 —— 我们完整地建立了一个 PostgreSQL DBA 应该具备的 WAL 与日志知识体系。

**核心脉络回顾**:

```text
WAL 概念  →  文件结构  →  LSN 机制
   ↓
写入流程 (Backend + WAL Writer)
   ↓
Checkpoint (推进 redo LSN)
   ↓
控制文件 (pg_control 持久化)
   ↓
配置调优 (wal_level / buffers / sync)
   ↓
服务器日志 (错误 / 慢查询 / 通用)
   ↓
pg_stat_statements + auto_explain
   ↓
复制 / PITR 应用
   ↓
监控告警
   ↓
性能调优
```

**最后强调三件事**:

1. **生产必看监控**:WAL 段数、checkpoint_req 占比、bgwriter 比例、备库 replay_lag、`pg_stat_statements` TOP SQL、archive_failed_count
2. **生产严禁设置**:`fsync=off`、`full_page_writes=off`(在 PITR 场景)、`archive_command` 不可用
3. **生产推荐参数**:`wal_level=replica`、`synchronous_commit=on`、`wal_compression=on`、`shared_preload_libraries` 含 `pg_stat_statements` + `auto_explain`

PostgreSQL 的 WAL 体系设计精妙,既保证了 ACID 严格性,又支撑了灵活的可观测性、可恢复性、可扩展性。深入理解并掌握它,是每一位 PostgreSQL 工程师的"必修内功"。

> **愿你在 PostgreSQL 的学习之路上,行稳致远。**
