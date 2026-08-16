# PostgreSQL Vacuum 与表膨胀

## 一、PG 表膨胀(Bloat)问题概述

### 1. 为什么有死元组(dead tuples)

PostgreSQL 的 MVCC(多版本并发控制)实现方式与 MySQL InnoDB 有本质区别。**InnoDB 把旧版本写入 undo log**,而 **PostgreSQL 直接把旧版本留在堆表(Heap)里**,只是用一个特殊的"墓碑"标记它已经"死了"。这些被标记但仍占据物理空间的行,就叫做**死元组(dead tuple)**。

当一行被 `DELETE` 或 `UPDATE` 时,PG 并不会立即从磁盘上抹掉它,而是:

- `DELETE`:在原 tuple 上设置 `t_xmax = 当前 xid`,标记为"已删除"
- `UPDATE`:在原 tuple 上设置 `t_xmax = 当前 xid`,再插入一个新 tuple(行地址 `t_ctid` 指向新位置)

旧的 tuple 还在文件里,等待后续 `VACUUM` 进程清理回收。如果长时间不 vacuum,**表会越来越膨胀**(table bloat),查询越来越慢,磁盘空间也会被白白占用。

### 2. 与 MySQL 的根本区别

| 维度              | PostgreSQL                                | MySQL InnoDB                                |
|-------------------|-------------------------------------------|---------------------------------------------|
| **旧版本存放**    | 直接留在 Heap 中(t_xmax 标记)            | 写入 Undo Log(独立表空间)                 |
| **清理机制**      | `VACUUM`(autovacuum 守护进程)            | Purge 线程(后台自动 purge)                |
| **回收空间方式**  | 普通 VACUUM 把空间放回 FSM 复用;`VACUUM FULL` 重写表 | 自动 purge 把空间归还 page,OPTIMIZE 重写 |
| **膨胀现象**      | **表膨胀(bloat)非常常见**,需要人工干预 | 一般不会膨胀(undo 独立空间)              |
| **锁特性**        | 普通 VACUUM 不阻塞读写                   | purge 与读不冲突                            |
| **XID 回卷风险**  | 有(必须定期 freeze)                     | 无(不用事务号)                            |

> **关键认知**:**PostgreSQL 的"表膨胀"是一个无法回避的问题**。只要表上有频繁的 `UPDATE`/`DELETE`,堆表就会慢慢长大,这是 MVCC 实现方式的"原罪"。因此 vacuum 不是可选项,而是**生产环境的必运维项**。

---

## 二、死元组产生场景

### 1. DELETE:标记 xmax,不删除

```sql
CREATE TABLE t (id INT PRIMARY KEY, val TEXT);
INSERT INTO t VALUES (1, 'a'), (2, 'b');

-- 在事务内 DELETE
BEGIN;
DELETE FROM t WHERE id = 1;
SELECT xmin, xmax, * FROM t;
--  id | val |  xmin  | xmax  |  ctid
--  ---+-----+--------+-------+--------
--   1 |  a  |   500  |  600  |  (0,1)   <- xmax=600,这条"看起来"还在
--   2 |  b  |   500  |  0    |  (0,2)

ROLLBACK;  -- 回滚,xmax 被清除,行恢复可见
```

行为:

- 立即把 `t_xmax` 设置为当前事务 id
- 立即把行标记为对其他事务"不可见"(依据可见性规则)
- **物理上不删除行**,磁盘上仍然存在
- 如果事务回滚,只需要清除 `t_xmax`,行"活过来"

### 2. UPDATE:实际是 delete + insert,旧行死掉

```sql
UPDATE t SET val = 'c' WHERE id = 1;

-- 内部发生了两步:
--  1. 原 tuple 上设置 t_xmax = 当前 xid(变成死元组)
--  2. 插入新 tuple,t_xmin = 当前 xid, t_ctid 指向新位置

SELECT xmin, xmax, ctid, * FROM t;
--  id | val |  xmin  | xmax  |  ctid
--  ---+-----+--------+-------+--------
--   1 |  a  |   500  |  700  |  (0,1)   <- 旧版本,已死(dead tuple)
--   1 |  c  |   700  |  0    |  (0,3)   <- 新版本
--   2 |  b  |   500  |  0    |  (0,2)
```

**Heap-Only Tuple(HOT)** 的优化:如果被更新的列**没有被任何索引覆盖**,PG 可以把新行放在**同一个页内**,而不更新索引。这是 PG 减少索引膨胀的关键机制。开启条件:

```sql
-- 满足以下两个条件才能走 HOT 链:
--  1. 被更新的列不包含任何索引列
--  2. 新行能放进同一个 page(不超出 fillfactor)
```

---

## 三、Vacuum 机制总览

PostgreSQL 提供四种 vacuum 相关命令,功能不同:

| 命令                                | 功能                                                         | 是否锁表     | 是否回收空间 |
|-------------------------------------|--------------------------------------------------------------|--------------|--------------|
| `VACUUM`                            | 扫描表,标记死元组为可重用,把空间登记到 FSM                  | 不锁表(允许读写)| 回收(放 FSM)|
| `VACUUM FULL`                       | **重写整张表**,把存活行紧凑写入新文件,删旧文件              | **AccessExclusiveLock**(锁全表) | 完全回收     |
| `ANALYZE`                           | 收集统计信息,**不清理死元组**                               | 不锁表(只 ShareUpdateExclusive) | 否           |
| `VACUUM (ANALYZE, VERBOSE) t`       | 一次性做 vacuum + analyze + 详细日志                         | 不锁表       | 回收         |

### 1. 普通 VACUUM

```sql
-- 清理单张表
VACUUM t;
VACUUM (VERBOSE) t;

-- 清理全库所有表
VACUUM;

-- 清空并更新统计信息
VACUUM (ANALYZE) t;
```

行为:

- 扫描表,找出 `xmax` 已提交或已回滚的死元组
- 把这些死元组所在的 slot **标记为可用**
- 在 FSM(Free Space Map)中更新这些页的可用空间
- 后续 INSERT/UPDATE 会优先用 FSM 中的"洞",减少表扩展
- **不锁表**:普通 DML(SELECT/INSERT/UPDATE/DELETE)不会被阻塞
- 占用大量 IO 和 CPU(可被 `cost_delay` 节流)

### 2. VACUUM FULL

```sql
VACUUM FULL t;
VACUUM (FULL, VERBOSE) t;
```

行为:

- 创建一份**新的表文件**,把存活行按顺序紧凑写入
- 旧表文件被删除,空间**立即归还操作系统**
- **需要 AccessExclusiveLock**,期间所有 DML 全部阻塞
- 表越大,锁表时间越长(几 GB 的表可能锁几分钟到几十分钟)
- 唯一能"瘦身"表到磁盘的方式

### 3. ANALYZE

```sql
ANALYZE t;
ANALYZE VERBOSE t;  -- 显示采样行数等
```

行为:

- 采样表数据,更新 `pg_statistic` 系统表
- 提供给优化器估算行数、选择性
- **与 vacuum 是两件事**,但 autovacuum 通常一起做
- 不锁表(只持有 ShareUpdateExclusiveLock,阻塞 vacuum 但不阻塞 DML)

### 4. VACUUM VERBOSE

```sql
VACUUM (VERBOSE, ANALYZE) t;
```

输出示例:

```
INFO: vacuuming "public.t"
INFO: scanned index "t_pkey" to remove 10000 row versions
       ... 0 dead item pointers in pages
INFO: "t": removed 10000 row versions in 5000 pages
INFO: "t": found 10000 removable, 50000 nonremovable row versions in 20000 total pages
INFO: "t": truncated 20000 to 15000 pages
INFO: analyzing "public.t"
INFO: "t": scanned 15000 of 15000 pages, containing 50000 live rows and 0 dead rows; 50000 rows in sample, 50000 estimated total rows
```

---

## 四、Vacuum 工作流程

普通 `VACUUM` 的内部步骤如下(以一张表为例):

```text
  ┌──────────────────────────────────────────────┐
  │  1. 获取表的 ShareUpdateExclusiveLock        │
  │     (允许 SELECT/INSERT/UPDATE/DELETE,       │
  │      禁止 VACUUM/ANALYZE/CREATE INDEX 等)    │
  └──────────────────┬───────────────────────────┘
                     ↓
  ┌──────────────────────────────────────────────┐
  │  2. 扫描所有页,识别死元组                    │
  │     - 检查 t_xmax 对应事务的状态              │
  │     - 若已提交 → 死元组                       │
  │     - 若已回滚 → 复活(清除 xmax 标记)        │
  │     - 若仍活跃 → 跳过,等下轮                 │
  └──────────────────┬───────────────────────────┘
                     ↓
  ┌──────────────────────────────────────────────┐
  │  3. 移除指向死元组的索引条目                  │
  │     (不重建索引,只删 dead index tuples)        │
  └──────────────────┬───────────────────────────┘
                     ↓
  ┌──────────────────────────────────────────────┐
  │  4. 更新 FSM (Free Space Map)                │
  │     把空闲空间登记到 FSM,后续 INSERT 复用     │
  └──────────────────┬───────────────────────────┘
                     ↓
  ┌──────────────────────────────────────────────┐
  │  5. 更新 Visibility Map                       │
  │     标记"所有行均可见"的页(用于 index-only scan) │
  └──────────────────┬───────────────────────────┘
                     ↓
  ┌──────────────────────────────────────────────┐
  │  6. (可选) Truncate 末尾空页                │
  │     表尾部全空的页可归还文件系统              │
  └──────────────────┬───────────────────────────┘
                     ↓
  ┌──────────────────────────────────────────────┐
  │  7. 释放锁                                    │
  └──────────────────────────────────────────────┘
```

**关键点**:

- 每一步都可能跨多轮:因为死元组对应的事务可能仍未结束,Vacuum 必须"绕开"它们
- HOT 链上的旧版本可以一并清理(不需要单独索引清理)
- Vacuum 是**事务安全的**:中途失败不会破坏数据一致性

---

## 五、Autovacuum(自动 Vacuum)

### 1. autovacuum 守护进程

PostgreSQL 默认开启自动 vacuum,由两个组件协同工作:

```text
  postmaster
       │
       ├── autovacuum launcher (1 个,常驻)
       │      │  每 autovacuum_naptime 秒醒来
       │      │  根据 pg_stat_user_tables 统计,决定哪些表需要 vacuum
       │      │  fork 出一个 worker
       │      ↓
       └── autovacuum worker (0~N 个)
              真正执行 VACUUM / ANALYZE
```

参数:

```ini
# postgresql.conf
autovacuum = on                      # 主开关
autovacuum_max_workers = 3           # 最多并行 worker 数
autovacuum_naptime = 15s             # launcher 唤醒间隔
```

### 2. 触发条件

PG 根据两套指标判断"是否需要 vacuum"。

**普通 vacuum 触发**:

```
当 n_dead_tup > autovacuum_vacuum_threshold
        + autovacuum_vacuum_scale_factor × n_live_tup
```

**Analyze 触发**:

```
当 n_mod_since_analyze > autovacuum_analyze_threshold
        + autovacuum_analyze_scale_factor × n_live_tup
```

默认参数:

| 参数                              | 默认值 | 含义                                |
|-----------------------------------|--------|-------------------------------------|
| `autovacuum_vacuum_scale_factor`  | 0.2    | 死元组 / 总行数 超过 20% 触发      |
| `autovacuum_vacuum_threshold`     | 50     | 至少 50 个死元组才触发              |
| `autovacuum_analyze_scale_factor` | 0.1    | 变化行 / 总行数 超过 10% 触发     |
| `autovacuum_analyze_threshold`    | 50     | 至少 50 行变化触发                  |
| `autovacuum_max_workers`          | 3      | 并发 worker 数                      |
| `autovacuum_naptime`              | 15s    | launcher 检查周期                  |

**举例**:100 万行的表,死元组超过 `50 + 0.2 × 1,000,000 = 200,050` 时触发 autovacuum。

### 3. cost delay 配置(避免 IO 风暴)

Vacuum 是个**重 IO 操作**,PG 用"成本模型"控制它的速度,避免打爆磁盘:

```ini
vacuum_cost_limit = 200              # 一个轮次内允许的"成本"上限
vacuum_cost_page_hit = 1            # 命中 shared_buffers 中的页
vacuum_cost_page_miss = 10          # 需要从磁盘读的页
vacuum_cost_page_dirty = 20         # 脏页(需要写盘)

# 当 vacuum 累计 cost 超过 vacuum_cost_limit,
# 就 sleep autovacuum_vacuum_cost_delay (默认 2ms)
autovacuum_vacuum_cost_delay = 2ms
```

调整建议:

- **IO 强的 SSD**:`vacuum_cost_limit = 1000~2000`,`cost_delay = 0`
- **IO 弱的 HDD / 共享存储**:`vacuum_cost_limit = 200`,`cost_delay = 10~20ms`

---

## 六、Visibility Map

### 1. 概念

**Visibility Map (VM)** 是每个表的一个**辅助文件**,记录"哪些页的所有元组对所有事务都可见"。

```text
Heap File (main fork)              Visibility Map (vm fork)
┌──────────────┐                  ┌──────────────┐
│  Page 0      │ ─── all-visible ─>│ bit 0 = 1   │
│  Page 1      │ ─── not yet ───>  │ bit 1 = 0   │
│  Page 2      │ ─── all-visible ─>│ bit 2 = 1   │
│  ...         │                  │              │
└──────────────┘                  └──────────────┘
```

每个 page 对应一个 bit:1 表示"所有行都对所有事务可见",0 表示"还有行需要通过 visibility check"。

### 2. 作用

| 作用                | 原理                                                                 |
|---------------------|----------------------------------------------------------------------|
| **Index-Only Scan** | 索引扫描时,如果 VM 标记页是 all-visible,可以直接返回结果,无需回表 |
| **VACUUM 加速**     | Vacuum 直接跳过 all-visible 的页(因为没有死元组),大幅减少扫描量  |
| **冻结判断**        | Vacuum 优先冻结(anti-wraparound)未冻结的页                        |

### 3. 谁更新 VM

- **VACUUM**:扫描过程中把全可见页置位
- **INSERT/UPDATE/DELETE**:涉及到的页会被清掉 all-visible 位(因为有新版本可能不可见)
- 注意:**索引页没有 VM**(只有 heap 表才有)

---

## 七、Free Space Map(FSM)

### 1. 概念

**Free Space Map (FSM)** 是记录"每个 page 有多少可用空间"的辅助结构,供后续 `INSERT`/`UPDATE` 选择插入页,避免每次都从表头开始找位置。

```text
FSM 结构:
┌────────────────────────────────────────┐
│  Fork: <relation>_fsm (每个表一个)    │
│  内容:每页可用字节数(精细度 ~ 1/256)  │
│  用途:INSERT 时优先插到有空间的页      │
└────────────────────────────────────────┘
```

### 2. 工作流程

```text
  INSERT 50 行新数据
        │
        ↓
  FSM 报告"Page 5 还有 200 字节"
        │
        ↓
  写到 Page 5(而不是新建页)
        │
        ↓
  更新 FSM(Page 5 剩余空间变小)
```

好处:

- 避免每次 INSERT 都去 fsync 一个新页
- 提升 INSERT 性能(SSD 上不明显,HDD 上很明显)
- VACUUM 把死元组"登记"到 FSM,后续 INSERT 可以直接用

### 3. 相关参数

```ini
# FSM 大小自动,但可调
max_fsm_pages = 200000        # (旧版参数,PG 9.0 前)
max_fsm_relations = 10000

# 实际上 PG 8.4+ 自动管理 FSM,无需手动设
```

---

## 八、表膨胀(Table Bloat)问题

### 1. bloat 产生原因

```text
  ┌────────────────────────────────────────────────────┐
  │   理想状态                                          │
  │   ┌────┐ ┌────┐ ┌────┐ ┌────┐                      │
  │   │ R1 │ │ R2 │ │ R3 │ │ R4 │   ← 全部是 live rows │
  │   └────┘ └────┘ └────┘ └────┘                      │
  └────────────────────────────────────────────────────┘

  ┌────────────────────────────────────────────────────┐
  │   大量 UPDATE/DELETE 后,VACUUM 没跟上的状态       │
  │   ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐       │
  │   │ R1 │ │ D2 │ │ R3 │ │ D4 │ │ R5 │ │ D6 │        │
  │   │    │ │ 死 │ │    │ │ 死 │ │    │ │ 死 │        │
  │   └────┘ └────┘ └────┘ └────┘ └────┘ └────┘       │
  │   实际只有 3 行,但占了 6 个槽位 → bloat = 50%      │
  └────────────────────────────────────────────────────┘
```

常见原因:

- **大量 UPDATE/DELETE + autovacuum 没跟上**:小表默认 scale_factor = 0.2 太宽容
- **长事务存在**:长事务"挡住" vacuum 的回收(老事务可能看到那些死元组)
- **`fillfactor` 设置不合理**:频繁更新的表如果 fillfactor=100,容易 page 满
- **关闭 autovacuum**:`autovacuum = off` 是最常见的坑

### 2. bloat 计算公式

最准确的方法是用 `pgstattuple` 扩展(后文给出 SQL),简单的估算公式是:

```text
dead_tuple_percent = n_dead_tup / (n_live_tup + n_dead_tup) × 100%
```

但这只能反映"已知的死元组",实际 bloat 可能更严重(因为 FSM 已经把一些空间复用,但表文件本身没缩小)。

### 3. 监控 bloat

```sql
-- 安装 pgstattuple 扩展
CREATE EXTENSION IF NOT EXISTS pgstattuple;

-- 查看单表的 bloat 详细数据
SELECT * FROM pgstattuple('public.t');
--  table_len        | 8192000     (表实际物理大小,字节)
--  tuple_count      | 10000       (live + dead 总行数)
--  tuple_len        | 500000      (live + dead 数据大小)
--  tuple_percent    | 6.10        (数据占比)
--  dead_tuple_count | 3000        (死元组数)
--  dead_tuple_len   | 150000
--  dead_tuple_percent | 1.83
--  free_space       | 6000000     (空闲空间)
--  free_percent     | 73.24       ← 这是真正的 bloat!
```

**free_percent > 50% 通常意味着严重膨胀**,需要 VACUUM FULL 或 pg_repack。

---

## 九、VACUUM FULL 与 pg_repack

### 1. VACUUM FULL 锁表问题

```sql
VACUUM FULL t;
```

- **AccessExclusiveLock**:锁期间禁止所有 DML(SELECT/INSERT/UPDATE/DELETE)
- 大表可能锁几十分钟
- 生产环境**慎用**,一般只能在维护窗口做

### 2. pg_repack 在线重组

`pg_repack` 是社区开源工具(类似 MySQL 的 `pt-online-schema-change`),可以**在线**完成表重组,不长时间锁表。

工作原理(类似 pt-osc):

```text
  1. 在原表上创建触发器(捕获后续 INSERT/UPDATE/DELETE)
  2. 创建一张临时新表,结构与原表一致
  3. 把原表数据批量复制到新表(此时 INSERT/UPDATE/DELETE 由触发器同步)
  4. 交换原表与新表(通过短暂锁表,但只需毫秒级)
  5. 删除旧表
```

特点:

- 整个过程只在一开始的"建立触发器"和最终的"交换"瞬间短暂锁表
- 大部分时间表可正常读写
- 支持处理膨胀表、索引膨胀
- 安装:`apt install postgresql-16-repack` 或 `yum install pg_repack_16`

### 3. 完整示例

```bash
# 安装
yum install -y pg_repack_16

# 重新打包(重组)一张膨胀的表
pg_repack -h 127.0.0.1 -p 5432 -U postgres -d mydb -t public.t

# 同时重组所有膨胀严重的表(配合脚本)
pg_repack -h 127.0.0.1 -U postgres -d mydb \
  --table-filter 'public.order|s.public.user' \
  --no-order
```

输出:

```
INFO: Dry run mode (no execute)
INFO: repack table "public.t"
INFO: create temporary log table
INFO: ... copying data
INFO: ... creating indexes
INFO: ... swap tables
INFO: repack completed successfully
```

---

## 十、表膨胀处理方案

按场景选择:

| 场景                                    | 推荐方案                | 说明                                  |
|-----------------------------------------|-------------------------|---------------------------------------|
| **小表(<1GB),离线可接受**              | `VACUUM FULL`           | 最简单,无需装扩展                    |
| **大表,需要在线**                       | `pg_repack`             | 推荐方案,几乎无锁                    |
| **想顺便按某个索引排序**                | `CLUSTER`               | 用索引顺序物理重排(也是锁表)        |
| **跨表空间迁移 + 顺手瘦身**             | `ALTER TABLE ... SET TABLESPACE` | 移动过程中顺带重写              |

### 1. VACUUM FULL(离线)

```sql
VACUUM FULL VERBOSE public.t;
```

### 2. pg_repack(在线)

```bash
pg_repack -d mydb -t public.t
```

### 3. CLUSTER(按索引重排)

```sql
-- 用某索引顺序物理重排(同时回收膨胀空间)
CLUSTER public.t USING t_pkey;

-- 之后 PG 会记住这个索引(写入 pg_class.relcluster)
-- 以后 CLUSTER 不指定索引时,沿用上次
```

注意:`CLUSTER` 也会短时间锁表,且**会丢失 H.O.T. 优化**(重排后行不在原 page)。

### 4. ALTER TABLE ... SET TABLESPACE

```sql
ALTER TABLE public.t SET TABLESPACE fast_ssd;
```

- 把表和索引移动到新表空间
- 移动过程相当于 VACUUM FULL,会锁表
- 适合"换盘 + 瘦身"二合一

---

## 十一、查看死元组

### 1. pg_stat_user_tables(轻量级)

```sql
-- 单表死元组数
SELECT
  schemaname, relname,
  n_live_tup, n_dead_tup,
  n_mod_since_analyze, last_vacuum, last_autovacuum
FROM pg_stat_user_tables
WHERE relname = 't';

-- 全库死元组 TOP 20
SELECT
  schemaname || '.' || relname AS table_name,
  n_live_tup, n_dead_tup,
  CASE WHEN n_live_tup = 0 THEN 0
       ELSE round(n_dead_tup::numeric / n_live_tup * 100, 2)
  END AS dead_pct,
  last_autovacuum
FROM pg_stat_user_tables
WHERE n_dead_tup > 1000
ORDER BY n_dead_tup DESC
LIMIT 20;
```

### 2. pgstattuple 扩展(精确)

```sql
-- 安装
CREATE EXTENSION pgstattuple;

-- 精确查看单表 bloat
SELECT
  pg_size_pretty(table_len)            AS total_size,
  tuple_count                          AS total_rows,
  dead_tuple_count                     AS dead_rows,
  round(dead_tuple_percent::numeric, 2) AS dead_pct,
  round(free_percent::numeric, 2)      AS bloat_pct
FROM pgstattuple('public.t');

-- 全库 bloat 报告(推荐!)
SELECT
  current_database() AS db,
  schemaname,
  tablename,
  pg_size_pretty(pg_relation_size(schemaname || '.' || tablename)) AS size,
  ROUND(100 * pct_free::numeric, 2) AS bloat_pct
FROM pgstattuple_approx(NULL::text)
ORDER BY pct_free DESC NULLS LAST
LIMIT 20;
```

### 3. 完整 SQL 示例:膨胀表清单

```sql
-- 综合查询:膨胀最严重的表 TOP 10
WITH bloat AS (
  SELECT
    schemaname || '.' || tablename AS fullname,
    pg_relation_size(schemaname || '.' || tablename) AS bytes,
    ROUND(100 * pct_free::numeric, 2) AS waste_pct
  FROM pgstattuple_approx(NULL::text)
)
SELECT
  fullname,
  pg_size_pretty(bytes)                            AS size,
  waste_pct || '%'                                 AS bloat_pct,
  pg_size_pretty(bytes * waste_pct / 100)          AS wasted_space
FROM bloat
WHERE waste_pct > 20
ORDER BY bytes * waste_pct DESC
LIMIT 10;
```

---

## 十二、Autovacuum 调优

### 1. 全局参数调优

```ini
# postgresql.conf
autovacuum_max_workers = 6                  # 提升 worker 数
autovacuum_naptime = 10s                    # 缩短唤醒间隔
autovacuum_vacuum_scale_factor = 0.05       # 默认 0.2 → 0.05(更激进)
autovacuum_analyze_scale_factor = 0.025     # 默认 0.1 → 0.025
autovacuum_vacuum_cost_limit = 2000         # SSD 上调大
autovacuum_vacuum_cost_delay = 0            # SSD 上设为 0
```

### 2. 单表配置(ALTER TABLE ... SET)

对特殊表单独调,不影响全局:

```sql
-- 对更新频繁的 user 表单独调
ALTER TABLE public.user SET (
  autovacuum_vacuum_scale_factor = 0.02,    -- 2% 就触发
  autovacuum_vacuum_threshold = 1000,
  autovacuum_analyze_scale_factor = 0.01,
  autovacuum_vacuum_cost_limit = 3000
);

-- 对静态字典表关掉 autovacuum(完全只读)
ALTER TABLE public.dict SET (
  autovacuum_enabled = false
);

-- 恢复默认
ALTER TABLE public.user RESET (
  autovacuum_vacuum_scale_factor,
  autovacuum_vacuum_threshold
);
```

### 3. 调优判断

```sql
-- 找出"应该被 vacuum 但很久没被 vacuum"的表
SELECT
  schemaname || '.' || relname AS table_name,
  n_live_tup, n_dead_tup,
  GREATEST(last_autovacuum, last_vacuum) AS last_vacuum,
  NOW() - GREATEST(last_autovacuum, last_vacuum, COALESCE(last_analyze, last_autoanalyze)) AS age
FROM pg_stat_user_tables
WHERE n_dead_tup > 10000
ORDER BY n_dead_tup DESC;
```

如果大量表 `n_dead_tup` 很高且 `last_autovacuum` 较老,说明 worker 不够或 cost_limit 太小。

---

## 十三、常见 Vacuum 问题

### 1. 长事务阻塞 vacuum

Vacuum 需要决定"哪些死元组可以被回收",判断标准是"**没有任何活跃事务还可能看到这些死元组**"。如果有**长事务**(例如跑了一小时没提交),它"挡住的"死元组都无法被回收。

```sql
-- 查看当前长事务(超过 1 分钟)
SELECT
  pid, usename, state,
  xact_start, NOW() - xact_start AS duration,
  query
FROM pg_stat_activity
WHERE state IS NOT NULL
  AND xact_start IS NOT NULL
  AND NOW() - xact_start > interval '1 minute'
ORDER BY xact_start;
```

```sql
-- 查看"挡住 vacuum 的事务"
SELECT
  pid, datname, usename,
  xact_start, NOW() - xact_start AS age,
  state, query
FROM pg_stat_activity
WHERE state IN ('idle in transaction', 'idle in transaction (aborted)')
ORDER BY xact_start;
```

**应对**:

- 监控 `idle in transaction` 的连接数,配置应用层超时
- 设置 `idle_in_transaction_session_timeout = 5min`(超过自动断开)

### 2. 事务 ID 回卷(XID wraparound)

PG 用 32-bit 事务号,**最大值 2³¹ - 1 = 2147483647**(为对称预留 1 个特殊值)。理论上事务号到顶后**会"绕回 0"**,导致过去的"新事务"看起来比"老事务"还早,**整个数据库会立即不可用**。

```text
  事务号轴(32 bit,2^31 个值):
  0 ──────────────────────── 2^31-1
  │                            │
  └─ 回到起点 ─────────────────┘
```

为防回卷,PG 引入了 **frozen tuple** 机制:Vacuum 把"非常老"的事务号冻结成一个特殊标记(等同 xmin = 2),表示"这条行永远可见,不需要再做事务号判断"。

### 3. freeze_age、autovacuum_freeze_max_age

| 参数                              | 默认值     | 含义                                       |
|-----------------------------------|------------|--------------------------------------------|
| `autovacuum_freeze_max_age`       | 200,000,000 | 表的最老事务号到这个值,强制触发 anti-wraparound vacuum |
| `vacuum_freeze_table_age`         | 150,000,000 | 何时把整表扫描冻结                          |
| `vacuum_freeze_min_age`           | 50,000,000  | 单个 tuple 多久可以被冻结                   |

```sql
-- 查看"距离回卷"还有多少事务
SELECT
  datname,
  age(datfrozenxid) AS xid_age,
  200000000 - age(datfrozenxid) AS remaining,
  current_setting('autovacuum_freeze_max_age')::int AS threshold
FROM pg_database
ORDER BY age(datfrozenxid) DESC;

-- 查看"最老的表"
SELECT
  schemaname || '.' || relname AS tbl,
  age(relfrozenxid) AS xid_age
FROM pg_class
JOIN pg_namespace n ON n.oid = relnamespace
WHERE relkind = 'r'
ORDER BY age(relfrozenxid) DESC
LIMIT 20;
```

如果 `age(relfrozenxid)` 接近 `autovacuum_freeze_max_age`,PG 会进入**紧急模式**:

```bash
# 告警日志
WARNING: database "mydb" must be vacuumed within 0 transactions
ERROR: database is not accepting commands to avoid wraparound data loss
```

### 4. 紧急处理

如果已经出现 wraparound 风险:

```sql
-- 1. 立即关闭 autovacuum(让手动 vacuum 独占 IO)
ALTER SYSTEM SET autovacuum = off;
SELECT pg_reload_conf();

-- 2. 在有问题的数据库上手动 vacuum freeze(强制冻结)
\c mydb
VACUUM (FREEZE, VERBOSE, ANALYZE);

-- 3. 处理完后,恢复 autovacuum
ALTER SYSTEM RESET autovacuum;
SELECT pg_reload_conf();
```

**预防措施**:

- 监控 `age(datfrozenxid)`,不要让它超过 2 亿
- 长事务是 XID 增长过快的头号杀手
- 大表建议主动定期 `VACUUM FREEZE`

---

## 十四、pg_stat_progress_vacuum 监控 vacuum 进度

PG 13+ 提供实时 vacuum 进度视图:

```sql
SELECT
  pid,
  datname,
  relid::regclass AS table_name,
  phase,                                           -- 当前阶段
  heap_blks_total, heap_blks_scanned,              -- heap 进度
  heap_blks_vacuumed,                              -- 已 vacuum 的页
  index_vacuum_count,                              -- 已 vacuum 的索引数
  num_dead_tuples,                                 -- 死元组数
  max_dead_tuples,
  progress = round(100.0 * heap_blks_scanned /
             NULLIF(heap_blks_total, 0), 2) AS pct
FROM pg_stat_progress_vacuum;
```

典型阶段(phase):

| phase                  | 含义                                          |
|------------------------|-----------------------------------------------|
| `initializing`         | 初始化                                        |
| `scanning heap`        | 扫描 heap 找死元组                            |
| `vacuuming indexes`    | 清理索引条目                                  |
| `vacuuming heap`       | 清理 heap                                     |
| `cleaning up indexes`  | 索引收尾                                      |
| `truncating heap`      | 截断末尾空页                                  |
| `performing final cleanup` | 收尾                                    |

实用查询:

```sql
-- 实时查看某个 vacuum 进程的进度
SELECT pid, relid::regclass, phase, pct
FROM pg_stat_progress_vacuum
WHERE relid = 'public.t'::regclass;
```

---

## 十五、索引膨胀(Index Bloat)

### 1. btree 索引也会膨胀

Heap 表膨胀时,索引也会膨胀——因为指向死元组的索引条目在 vacuum 前不会消失:

```sql
-- 查看索引 bloat(需要 pgstattuple 扩展)
SELECT
  current_database() AS db,
  schemaname,
  indexname,
  pg_size_pretty(pg_relation_size(indexname::regclass)) AS index_size,
  ROUND(100 * pct_free::numeric, 2) AS bloat_pct
FROM pgstattuple_approx(NULL::text);
```

### 2. REINDEX(重建索引)

```sql
-- 单索引重建(锁索引,阻塞该索引上的查询)
REINDEX INDEX idx_t_user_id;

-- 重建表的所有索引(锁表)
REINDEX TABLE t;

-- 不锁表的重建(9.5+,concurrent 创建新索引)
REINDEX INDEX CONCURRENTLY idx_t_user_id;
```

`CONCURRENTLY` 选项不锁表但耗时更长,且过程中需要额外磁盘空间。

### 3. pg_repack 处理索引膨胀

```bash
# 重建表的所有索引 + 整理膨胀
pg_repack -d mydb -t public.t
# 等价于 VACUUM FULL + REINDEX
```

也可以只重建部分索引(从 9.4 起):

```bash
pg_repack --index idx_t_user_id -d mydb -t public.t
```

---

## 十六、完整实战案例

### 案例 1:小电商网站,orders 表膨胀

**现象**:orders 表只有 500 万行,但占 80 GB,慢查询突增。

**诊断**:

```sql
CREATE EXTENSION pgstattuple;
SELECT * FROM pgstattuple('public.orders');
```

输出:

```
  table_len        | 80 GB
  dead_tuple_count | 12,000,000
  dead_tuple_percent | 18
  free_space       | 60 GB
  free_percent     | 75    ← 严重膨胀!
```

**原因**:

- 订单状态字段频繁 UPDATE(待付款 → 已付款 → 已发货 ...)
- autovacuum_scale_factor = 0.2,500 万行要 100 万死元组才触发,远超实际
- 触发频率太低

**处理**:

```sql
-- 1. 单表调参:更激进
ALTER TABLE orders SET (
  autovacuum_vacuum_scale_factor = 0.03,
  autovacuum_vacuum_threshold = 2000
);

-- 2. 临时手动 vacuum
VACUUM (VERBOSE, ANALYZE) orders;
-- 缩小后空间进入 FSM,但表大小不变

-- 3. 在线回收空间
pg_repack -d mydb -t orders
```

**结果**:80 GB → 15 GB,查询时间从 3s 降至 200ms。

### 案例 2:长事务堵死 autovacuum

**现象**:有一张大表 `event_log` 死元组一直不下降,已经堆到 5000 万,`pg_stat_user_tables` 显示 `n_dead_tup` 持续增长。

**诊断**:

```sql
SELECT pid, state, NOW() - xact_start AS duration, query
FROM pg_stat_activity
WHERE state LIKE '%transaction%'
ORDER BY xact_start;
```

发现有个 BI 报表任务跑了几小时,**`idle in transaction`** 状态。

**处理**:

```bash
# 1. 配置连接层超时
psql -c "ALTER SYSTEM SET idle_in_transaction_session_timeout = '5min';"
psql -c "SELECT pg_reload_conf();"

# 2. 杀掉阻塞事务
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle in transaction'
  AND NOW() - xact_start > interval '30 minutes';

# 3. 触发 vacuum
VACUUM (VERBOSE) event_log;
```

**预防**:

- 应用层事务使用超时控制
- PgBouncer 配置 `server_idle_timeout`
- 监控 `idle_in_transaction` 数量告警

### 案例 3:事务号接近回卷

**现象**:告警 `database "mydb" must be vacuumed within 100000 transactions`。

**诊断**:

```sql
SELECT datname, age(datfrozenxid),
       200000000 - age(datfrozenxid) AS remaining
FROM pg_database
WHERE datname = 'mydb';
-- remaining = 80,000,接近回卷
```

**原因**:大表 `event_log` 一直没被 vacuum(因为有长事务挡着)。

**处理**:

```sql
-- 1. 关掉 autovacuum,腾出 IO
ALTER SYSTEM SET autovacuum = off;
SELECT pg_reload_conf();

-- 2. 杀掉长事务
SELECT pg_terminate_backend(pid) FROM pg_stat_activity
WHERE state IN ('idle in transaction','idle in transaction (aborted)');

-- 3. 手动 freeze(分批,避免长时间锁)
\c mydb
VACUUM (FREEZE, VERBOSE) event_log;

-- 4. 检查是否回到安全范围
SELECT datname, age(datfrozenxid) FROM pg_database WHERE datname='mydb';

-- 5. 恢复 autovacuum
ALTER SYSTEM RESET autovacuum;
SELECT pg_reload_conf();
```

### 案例 4:索引膨胀导致慢查询

**现象**:某条 WHERE user_id = ? 的查询 30 秒,但有索引。

**诊断**:

```sql
SELECT pg_size_pretty(pg_relation_size('idx_user_id'));
-- 12 GB,但 user_id 只有 50 万行
```

**原因**:user_id 字段频繁 UPDATE,索引条目膨胀严重。

**处理**:

```sql
-- 1. 在线重建索引(不锁表)
REINDEX INDEX CONCURRENTLY idx_user_id;

-- 2. 验证索引大小
SELECT pg_size_pretty(pg_relation_size('idx_user_id'));
-- 12 GB → 800 MB

-- 3. 查询时间降到 200ms
```

### 案例 5:批量处理所有膨胀表(脚本)

```bash
#!/bin/bash
# repack_all_bloated.sh - 自动 repack 膨胀超过 30% 的表

PSQL="psql -h 127.0.0.1 -U postgres -d mydb -t -A"

# 1. 找出膨胀超过 30% 且大小 > 100MB 的表
TABLES=$($PSQL -c "
  SELECT schemaname || '.' || tablename
  FROM pgstattuple_approx(NULL::text)
  WHERE pct_free > 0.30
    AND pg_relation_size(schemaname || '.' || tablename) > 100*1024*1024
  ORDER BY pct_free DESC;
")

# 2. 逐张 pg_repack
for tbl in $TABLES; do
  echo "==> Repacking $tbl ..."
  pg_repack -h 127.0.0.1 -U postgres -d mydb -t "$tbl"
done
```

---

## 十七、核心要点速记

### 1. 死元组要点

- PG 的 MVCC 把旧版本**留在 Heap 中**,只是设置 `t_xmax` 标记——这是与 InnoDB undo log 的根本区别
- DELETE 是"标记删除",UPDATE 是"标记删除 + 插入新行"
- 死元组不立即回收,等 VACUUM 处理

### 2. Vacuum 命令要点

- **`VACUUM`**:在线,回收空间到 FSM(不锁表)
- **`VACUUM FULL`**:离线,重写表,**完全回收空间但锁表**
- **`ANALYZE`**:更新统计信息(不清理死元组)
- **`VACUUM FREEZE`**:紧急冻结,防 XID 回卷

### 3. Autovacuum 要点

- 默认开启,`autovacuum_max_workers = 3`,`naptime = 15s`
- 触发公式:`n_dead_tup > threshold + scale_factor × n_live_tup`
- 调优方向:大表改 scale_factor 0.2 → 0.02~0.05
- 成本控制:`vacuum_cost_limit` + `vacuum_cost_delay`

### 4. bloat 处理速查

| 场景               | 方案                  |
|--------------------|-----------------------|
| 在线大表           | **pg_repack**         |
| 离线小表           | `VACUUM FULL`         |
| 顺便按索引排序     | `CLUSTER USING 索引`  |
| 索引重建(不锁表)  | `REINDEX CONCURRENTLY` |
| 索引重建(锁表)    | `REINDEX`            |
| 想边换盘边瘦身     | `ALTER TABLE SET TABLESPACE` |

### 5. 监控 SQL 速查

```sql
-- 看死元组最多的表
SELECT relname, n_dead_tup FROM pg_stat_user_tables ORDER BY n_dead_tup DESC LIMIT 10;

-- 看膨胀率(pgstattuple 扩展)
SELECT * FROM pgstattuple('public.t');

-- 看 vacuum 进度
SELECT pid, relid::regclass, phase FROM pg_stat_progress_vacuum;

-- 看距离 XID 回卷
SELECT datname, age(datfrozenxid), 200000000 - age(datfrozenxid) AS remaining FROM pg_database;
```

### 6. 关键参数速查

| 参数                                | 推荐值          | 说明                          |
|-------------------------------------|-----------------|-------------------------------|
| `autovacuum`                        | on              | 主开关                        |
| `autovacuum_max_workers`            | 3~6             | 并发 worker                   |
| `autovacuum_vacuum_scale_factor`    | 0.05            | 触发更激进                    |
| `autovacuum_vacuum_cost_limit`      | 2000(SSD)/200   | 节流                          |
| `autovacuum_vacuum_cost_delay`      | 0(SSD)/10ms     | 节流                          |
| `autovacuum_freeze_max_age`         | 200,000,000     | 不要调大                       |
| `idle_in_transaction_session_timeout` | 5min          | 防长事务挡 vacuum             |

### 7. 致命风险清单

- **关闭 autovacuum**:大多数 bloat 问题都是这个原因
- **超长事务**:挡住 vacuum 回收 + 推高 XID
- **XID 接近 21 亿**:会"丢数据"回卷,必须冻结
- **大表 fillfactor=100**:频繁更新会立即 page 满
- **不监控 `n_dead_tup`**:出问题才察觉为时已晚

### 8. 一句话总结

> **PG 的"表膨胀"是 MVCC 实现方式的必然产物,autovacuum 是第一道防线,pg_repack 是终极武器,XID 回卷是悬在头上的剑。** 任何生产库都必须配置 autovacuum + 监控死元组 + 定期评估是否需要 pg_repack,缺一不可。