# PostgreSQL 事务与 MVCC (Transaction & Multi-Version Concurrency Control)

## 一、PostgreSQL 事务概述

### 1.1 什么是事务

**事务 (Transaction)** 是数据库系统中一组**不可分割**的逻辑操作单元,这组操作要么**全部成功提交 (COMMIT)**,要么**全部失败回滚 (ROLLBACK)**,不会出现"做了一半"的中间状态。

最经典的例子仍然是**银行转账**:

```text
张三给李四转账 1000 元

步骤 1: UPDATE account SET balance = balance - 1000 WHERE name = '张三';
步骤 2: UPDATE account SET balance = balance + 1000 WHERE name = '李四';

如果步骤 1 成功、步骤 2 失败(比如宕机):
  → 张三少了 1000,李四没收到 → 钱凭空消失!

事务保证:两步要么都成功,要么都不做。
```

PostgreSQL 作为一个**完全支持 ACID**的关系型数据库,把所有事务相关的保证都内建在存储引擎层,**不依赖应用层代码**。

### 1.2 ACID 四大特性

```text
┌──────────────────────────────────────────────────────────┐
│                  PostgreSQL ACID 四大特性                  │
├──────────────┬───────────────────────────────────────────┤
│ A 原子性      │ Atomicity   → 全做 or 全不做              │
│              │ 实现:ROLLBACK 时丢弃未提交的所有变更       │
│              │ (没有 undo log,靠行的 xmax 实现)         │
├──────────────┼───────────────────────────────────────────┤
│ C 一致性      │ Consistency → 数据从一个合法态到另一合法态 │
│              │ 实现:AID + 约束(主键/外键/CHECK/唯一索引)│
├──────────────┼───────────────────────────────────────────┤
│ I 隔离性      │ Isolation   → 并发事务互不干扰            │
│              │ 实现:MVCC(主要) + 锁(辅助)              │
├──────────────┼───────────────────────────────────────────┤
│ D 持久性      │ Durability  → 提交后永久生效,宕机不丢    │
│              │ 实现:WAL(Write-Ahead Log) + fsync       │
└──────────────┴───────────────────────────────────────────┘
```

#### 原子性 (Atomicity)

PostgreSQL 中,**事务的原子性**由两条机制共同保证:

- **COMMIT**:把当前事务所做的所有修改**永久化**到磁盘(WAL 刷盘)
- **ROLLBACK**:把事务所做的所有修改**丢弃**(注意:不是"撤销",而是"丢弃未提交的版本")

```text
注意:PostgreSQL 与 MySQL InnoDB 在"回滚"的实现上有本质差异:

  MySQL InnoDB:
    UPDATE 时拷贝旧值到 undo log
    ROLLBACK 时逆序执行 undo log 中的"反向操作"
    → 旧版本不消失,MVCC 后续还要用

  PostgreSQL:
    UPDATE 时并不"删除"旧行,而是把它标记为不可见(xmax = 当前事务)
    ROLLBACK 时把 xmax 重置为 0(或在事务结束时清掉)
    → 没有"反向操作"的概念,所谓"回滚"只是让那些行重新可见

  也就是说:
    MySQL:旧版本"还在",靠回滚"还原"
    PG  :旧版本"已在",靠"置无效"回滚
```

#### 一致性 (Consistency)

一致性是**最终目的**,由以下三部分共同保证:

- **数据库层约束**:PRIMARY KEY、UNIQUE、FOREIGN KEY、NOT NULL、CHECK、EXCLUSION
- **事务原子性、隔离性、持久性**(AID 三个手段共同支撑 C)
- **应用层业务约束**(由开发者在 SQL/代码中保证)

```sql
-- 一致性的部分来源
CREATE TABLE account (
    id      SERIAL PRIMARY KEY,          -- 实体完整性
    name    TEXT NOT NULL UNIQUE,        -- 唯一性
    balance NUMERIC(12,2) CHECK (balance >= 0),  -- 域完整性
    user_id INT REFERENCES app_user(id)  -- 参照完整性
);
```

#### 隔离性 (Isolation)

PostgreSQL 的隔离性主要由 **MVCC** 实现,**锁机制是辅助**手段。

```text
         PG 并发控制的两大支柱

       MVCC                          锁
  ┌──────────────┐             ┌──────────────────┐
  │  快照隔离     │             │  写写冲突解决     │
  │  读写不互斥   │             │  DDL 互斥         │
  │  历史版本保留 │             │  显式行锁         │
  │              │             │  Advisory Lock    │
  └──────────────┘             └──────────────────┘
        ↑                            ↑
   普通 SELECT                  UPDATE/DELETE
   走 MVCC                     仍然需要锁
```

#### 持久性 (Durability)

PostgreSQL 持久性靠 **WAL(Write-Ahead Logging,预写日志)** 实现:

```text
      修改数据流程 (WAL)

   ┌────────────────────────────────────┐
   │ 1. 在 Buffer 中修改数据页(内存)     │  ← 快
   │ 2. 把变更写入 WAL Buffer           │
   │ 3. COMMIT 时 fsync WAL 到磁盘       │  ← 顺序写,快
   │ 4. 返回客户端"提交成功"             │
   │ 5. 脏页由后台 checkpointer 异步刷盘 │  ← 随机写,慢,可延后
   └────────────────────────────────────┘

   崩溃恢复:重启后 replay WAL,
            把已提交但未刷盘的修改补上。
```

关键参数 `synchronous_commit`:

| 值 | 行为 | 安全性 | 性能 |
|----|------|--------|------|
| `on` | COMMIT 时 WAL 立即 fsync(**默认**) | 不丢数据 | 中等 |
| `off` | COMMIT 仅写 OS 缓存,后台刷 | OS 崩溃丢最近事务 | 最高(3-5 倍) |
| `remote_write` | 等备机写盘不等 fsync | 备机宕丢 | 折中 |
| `apply` | 等备机 apply | 备机宕仍丢 | 最慢 |

```sql
-- 查看
SHOW synchronous_commit;

-- 高吞吐场景可临时关闭(单实例、丢点数据无所谓)
SET LOCAL synchronous_commit = OFF;
```

### 1.3 PostgreSQL 事务与其他数据库的差异

| 特性 | PostgreSQL | MySQL InnoDB | Oracle |
|------|-----------|--------------|--------|
| 旧版本存放 | heap 表中(xmax 标记) | undo log 段 | 回滚段 |
| 默认隔离级别 | **READ COMMITTED** | REPEATABLE READ | READ COMMITTED |
| SERIALIZABLE 实现 | **SSI(谓词锁)** | 退化当前读+锁 | SERIALIZABLE |
| 快照粒度 | 语句级(RC) / 事务级(RR/Serializable) | 事务级(RR) | 语句级 |
| 是否需要 purge | 需 VACUUM 清理死元组 | 需 purge 清理 undo | 需回收回滚段 |
| 索引项版本 | 索引只指向最新 heap 位置,无版本 | 索引有版本 | 索引有版本 |

---

## 二、事务语法

PostgreSQL 提供**两套等价**的事务控制语法(SQL 标准和 PG 扩展),`COMMIT/ROLLBACK` 是核心。

### 2.1 开启事务

```sql
-- 方式 1: BEGIN(最常用,PG 扩展)
BEGIN;
-- 或
BEGIN WORK;
-- 或
BEGIN ISOLATION LEVEL SERIALIZABLE;  -- 同时指定隔离级别
-- 或
BEGIN TRANSACTION;       -- 标准 SQL 写法
```

| 写法 | 是否标准 SQL | 说明 |
|------|--------------|------|
| `BEGIN` | PG 扩展(等价 `BEGIN WORK`) | 简洁,最常用 |
| `BEGIN WORK` | PG 扩展 | 显式标注 WORK |
| `START TRANSACTION` | SQL 标准 | 标准 SQL 写法 |
| `BEGIN TRANSACTION` | PG 兼容 | 完整写法 |

**`BEGIN` 与 `START TRANSACTION` 的细微差异**:

```text
BEGIN:
  - 几乎无副作用,几乎不分配事务 ID
  - 第一条 SQL 执行时才真正分配 xid
  - 性能稍好(轻量)

START TRANSACTION:
  - 立即分配事务 ID(快照等)
  - 可以带事务模式子句(隔离级别、读写模式)
  - 兼容性更好
```

### 2.2 提交事务

```sql
-- 提交
COMMIT;
-- 或
COMMIT WORK;
-- 或
END;                  -- PG 特有的语法糖,等价 COMMIT
```

`END` 是 PostgreSQL 的"小个性":

```text
BEGIN;
UPDATE ...;
END;        -- 等价 COMMIT,PG 特有

为什么有 END?
  - 与 PL/pgSQL 的 BEGIN ... END 块区分(虽然同名但语境不同)
  - 历史包袱,与 Oracle 的 PL/SQL 风格有渊源
```

### 2.3 回滚事务

```sql
-- 全部回滚
ROLLBACK;
-- 或
ROLLBACK WORK;
-- 或
ABORT;                -- PG 9.8 引入,等价 ROLLBACK
```

### 2.4 自动提交模式

```sql
-- 查看/设置
SHOW autocommit;
SET autocommit = ON;     -- 默认,每条 SQL 独立事务
SET autocommit = OFF;    -- 关闭自动提交,需显式 COMMIT
```

**PostgreSQL 默认 autocommit = ON**,与 MySQL 行为一致。

```text
autocommit = ON 时:

  每条 SQL 自动包在 BEGIN ... COMMIT 之间
  UPDATE t SET x = 1;        -- 隐式事务,自动提交
  UPDATE t SET y = 2;        -- 另一个隐式事务,自动提交

autocommit = OFF 时:

  UPDATE t SET x = 1;        -- 显式开启事务
  UPDATE t SET y = 2;        -- 同一事务
  COMMIT;                    -- 一起提交

实际开发建议:
  永远保持 autocommit = ON
  用显式 BEGIN ... COMMIT 包裹需要的多语句事务
  不要在应用代码里依赖 autocommit = OFF
```

### 2.5 SAVEPOINT(保存点)

SAVEPOINT 提供了**事务内部的子事务**能力,可以部分回滚。

```sql
-- 基础语法
BEGIN;
  INSERT INTO log VALUES ('step 1');
  
  SAVEPOINT sp1;
  INSERT INTO log VALUES ('step 2');
  UPDATE account SET balance = balance - 1000 WHERE id = 1;
  UPDATE account SET balance = balance + 1000 WHERE id = 2;
  -- 假设发现 id=2 余额有问题
  
  ROLLBACK TO SAVEPOINT sp1;  -- 撤销 step 2 之后的所有操作
  -- 账户表回退,但 sp1 之前的 step 1 还在
  
  UPDATE account SET balance = balance + 1000 WHERE id = 3;
  -- 换个人收款
  
  RELEASE SAVEPOINT sp1;     -- 销毁保存点(无法再 ROLLBACK TO)
  
COMMIT;
```

**关键操作**:

| 操作 | 作用 |
|------|------|
| `SAVEPOINT name` | 在当前位置建立一个命名保存点 |
| `ROLLBACK TO SAVEPOINT name` | 回滚到指定保存点(其后操作全部撤销) |
| `RELEASE SAVEPOINT name` | 销毁保存点(其后操作保留,但无法再回滚到该点) |
| `SAVEPOINT name` 同名 | PG 8.0 起会隐式销毁同名旧保存点 |

```text
SAVEPOINT 嵌套结构示意:

  BEGIN
   ├── SQL1
   ├── SQL2
   ├── SAVEPOINT sp1
   │     ├── SQL3
   │     ├── SQL4
   │     ├── SAVEPOINT sp2
   │     │     ├── SQL5
   │     │     └── SQL6
   │     └── ROLLBACK TO sp1   ← SQL5、SQL6 撤销
   └── SQL7                    ← SQL3、SQL4 撤销,SQL1、SQL2 保留
  COMMIT
```

### 2.6 完整语法示例

```sql
-- 综合示例
BEGIN ISOLATION LEVEL REPEATABLE READ;
  -- 业务 1
  UPDATE inventory SET qty = qty - 10 WHERE sku = 'A001';
  
  -- 业务 2
  SAVEPOINT before_payment;
  INSERT INTO payment (order_id, amount) VALUES (1001, 99.00);
  
  -- 业务 3
  UPDATE order SET status = 'paid' WHERE id = 1001;
  
  -- 假设发生异常
  -- ROLLBACK TO SAVEPOINT before_payment;
  -- RELEASE SAVEPOINT before_payment;
  
COMMIT;   -- 全部提交

-- 或者:
-- ROLLBACK; -- 全部回滚
```

---

## 三、事务隔离级别

### 3.1 SQL 标准四级别

SQL 标准定义了 4 个隔离级别,用以解决并发事务中不同强度的"异常"问题。

| 隔离级别 | 脏读 | 不可重复读 | 幻读 | 序列化异常 |
|----------|------|-----------|------|-----------|
| READ UNCOMMITTED | 可能 | 可能 | 可能 | 可能 |
| READ COMMITTED | 不可能 | 可能 | 可能 | 可能 |
| REPEATABLE READ | 不可能 | 不可能 | 可能 | 可能 |
| SERIALIZABLE | 不可能 | 不可能 | 不可能 | 不可能 |

```text
隔离级别的"严格度":

   弱 ━━━━━━━━━━━━━━━━━━━━━━━━ 强
   RU      RC        RR         SERIALIZABLE
   │       │         │          │
   并发最高│         │          并发最低
   一致性最│         │          一致性最高
   差      │         │
          PG默认
```

### 3.2 PostgreSQL 四种隔离级别

```sql
-- 查看当前会话隔离级别
SHOW transaction_isolation;
-- 或
SELECT current_setting('transaction_isolation');

-- 设置当前会话隔离级别
SET transaction_isolation = 'READ COMMITTED';

-- 设置事务级隔离级别
BEGIN ISOLATION LEVEL REPEATABLE READ;
-- 或
BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE;
```

| 隔离级别 | PG 行为 | 快照时机 |
|----------|---------|----------|
| **READ UNCOMMITTED** | **降级为 READ COMMITTED** | 同 RC |
| **READ COMMITTED** | 默认,每个语句新建快照 | **语句级** |
| **REPEATABLE READ** | 事务第一个 SQL 创建快照 | **事务级** |
| **SERIALIZABLE** | 事务级快照 + SSI 检测 | **事务级** |

```text
PostgreSQL 为什么不真正实现 READ UNCOMMITTED?

  1. PG 的 MVCC 实现中,行级可见性靠 xmin/xmax 与快照
     → 即使你要"读未提交",实现上也只能读"已提交"
     → 因为未提交事务的 xmax 未设、行仍"存在"
     → 所以 READ UNCOMMITTED 等同 READ COMMITTED

  2. PostgreSQL 官方态度:
     "READ UNCOMMITTED 在 PG 中不可用,语义被当成 READ COMMITTED"

  3. 真要"读未提交"?
     → 没有合法的 PG API
     → 想脏读只能绕过数据库直接看 heap(用 pageinspect 扩展)
```

### 3.3 设置隔离级别的三种作用域

```sql
-- 1. 会话级(本次连接)
SET SESSION CHARACTERISTICS AS TRANSACTION ISOLATION LEVEL REPEATABLE READ;

-- 2. 当前事务(仅下一个事务)
SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY;
-- 必须放在 BEGIN 之后第一条 SQL 之前
-- 或作为 BEGIN 的参数:BEGIN ISOLATION LEVEL SERIALIZABLE;

-- 3. 配置文件(影响所有新建会话)
-- postgresql.conf:
-- default_transaction_isolation = 'read committed'
```

---

## 四、各隔离级别并发问题详解

### 4.1 脏读 (Dirty Read)

**定义**:一个事务读到另一个事务**尚未提交**的数据。

```text
                脏读示意

  时间 ─────────────────────────────────────►

  T1: BEGIN
  T1: UPDATE balance = 200  (原值 100)
                                                  ← 未提交!

                            T2: BEGIN
                            T2: SELECT balance    -- 读到 200
                                                  ← T2 以为 T1 已提交
  T1: ROLLBACK (回滚)
                                                  ← 实际 balance 仍是 100
                                                  ← T2 拿着假数据做了业务决策
```

**PG 行为**:在所有隔离级别下,脏读**都不可能发生**。即使设成 `READ UNCOMMITTED`,也只是等同 `READ COMMITTED`。

### 4.2 不可重复读 (Non-Repeatable Read)

**定义**:同一事务内,两次读同一行,得到不同结果(因为中间有别的事务修改并提交)。

```text
              不可重复读示意

  T1: BEGIN
  T1: SELECT balance → 100
                │
                │       T2: BEGIN
                │       T2: UPDATE balance = 200
                │       T2: COMMIT
                │
  T1: SELECT balance → 200  ← 同一个事务,结果不同!
  T1: COMMIT
```

**PG 行为**:

| 隔离级别 | 是否可能 |
|----------|----------|
| READ COMMITTED | **可能**(每次 SELECT 都新建快照) |
| REPEATABLE READ | 不可能 |
| SERIALIZABLE | 不可能 |

### 4.3 幻读 (Phantom Read)

**定义**:同一事务内,两次执行**相同范围查询**,第二次返回了第一次没有的行(中间有别的事务 INSERT/DELETE 并提交)。

```text
                幻读示意

  T1: BEGIN
  T1: SELECT COUNT(*) FROM user WHERE age > 20;  → 10
                │
                │       T2: BEGIN
                │       T2: INSERT INTO user(age) VALUES (30);
                │       T2: COMMIT
                │
  T1: SELECT COUNT(*) FROM user WHERE age > 20;  → 11
                                                   ← 多出来一行!
  T1: COMMIT
```

**PG 行为**:

| 隔离级别 | 是否可能(快照读) | 备注 |
|----------|------------------|------|
| READ COMMITTED | **可能** | 语句级快照 |
| REPEATABLE READ | **不可能** | 事务级快照 |
| SERIALIZABLE | 不可能 | 事务级快照 + SSI |

> **注意**:PG 的 REPEATABLE READ 严格意义上是 **Snapshot Isolation(SI)**,而**不是 SQL 标准**定义的 REPEATABLE READ。因为标准 RR 允许幻读、只禁止"针对单行"的不可重复读;PG 的实现彻底禁止幻读。

### 4.4 序列化异常 (Serialization Anomaly)

**定义**:事务并发执行的结果,与"某种串行执行"的结果都不一致。**只有 SERIALIZABLE 级别能完全避免**。

```text
          序列化异常经典案例

  数据: x = 0, y = 0

  T1: BEGIN                  T2: BEGIN
  T1: SELECT x → 0           T2: SELECT y → 0
  T1: UPDATE y = x + 1       T2: UPDATE x = y + 1
  T1: COMMIT                 T2: COMMIT

  最终:
    x = 1   (T2 把 y=0 读走)
    y = 1   (T1 把 x=0 读走)
  
  串行化期望:
    任何一种串行结果都应该是 (x=1,y=0) 或 (x=0,y=1)
    不会两个都 = 1
    → 这是 write skew(写偏序)
```

**PG 行为**:

| 隔离级别 | 是否可能 |
|----------|----------|
| RC, RR | 可能(因为只是 SI) |
| SERIALIZABLE | **不可能**(SSI 检测) |

### 4.5 各问题的对比演示

#### READ COMMITTED 演示

```text
-- Session A                          -- Session B
BEGIN;
SELECT balance FROM acct 
  WHERE id = 1;     →  100
                                      BEGIN;
                                      UPDATE acct 
                                        SET balance = 200 
                                        WHERE id = 1;
                                      COMMIT;  -- 已提交
SELECT balance FROM acct 
  WHERE id = 1;     →  200   ← 不可重复读!
COMMIT;
```

#### REPEATABLE READ 演示

```text
-- Session A                          -- Session B
BEGIN ISOLATION LEVEL RR;
SELECT balance FROM acct 
  WHERE id = 1;     →  100
                                      BEGIN;
                                      UPDATE acct 
                                        SET balance = 200 
                                        WHERE id = 1;
                                      COMMIT;  -- 已提交
SELECT balance FROM acct 
  WHERE id = 1;     →  100   ← 仍看到旧值!
COMMIT;
```

#### SERIALIZABLE 演示

```text
-- Session A                          -- Session B
BEGIN ISOLATION LEVEL SER;
SELECT SUM(balance) FROM acct 
  WHERE branch = 'B1';   →  5000
                                      BEGIN ISOLATION LEVEL SER;
                                      SELECT SUM(balance) FROM acct 
                                        WHERE branch = 'B1';   →  5000
                                      UPDATE acct 
                                        SET balance = 100 
                                        WHERE id = 7;  -- B1
                                      COMMIT;  ← OK
COMMIT;  ← ERROR: could not serialize
         ← 40001: serialization failure
         -- 应用层需捕获并重试
```

---

## 五、MVCC 多版本并发控制 (PostgreSQL 特色)

### 5.1 MVCC 核心思想

**MVCC (Multi-Version Concurrency Control,多版本并发控制)** 的核心承诺:

> **读不阻塞写,写不阻塞读**,通过保留数据的多个历史版本,让并发事务"看到各自应该看到的快照"。

```text
     没有 MVCC 时的"读写冲突"

  事务 T1 (写)             事务 T2 (读)
  ┌──────────┐            ┌──────────┐
  │ UPDATE   │            │ SELECT   │
  │   ...    │ ◄─ 锁 ─►  │  等待!   │
  │          │            │          │
  └──────────┘            └──────────┘
  
  → T2 一直在等 T1 释放锁
  → 即使 T2 只是想看一眼数据

  有 MVCC 后:

  事务 T1 (写)             事务 T2 (读)
  ┌──────────┐            ┌──────────┐
  │ UPDATE   │            │ SELECT   │  读走旧版本
  │ 写新版本  │            │ 不阻塞!  │  不需要锁
  └──────────┘            └──────────┘
  
  → 两者完全并行,互不阻塞
```

### 5.2 PostgreSQL MVCC 与 MySQL MVCC 的根本差异

```text
  ┌─────────────────────────────────────────────────────┐
  │       PG MVCC vs MySQL InnoDB MVCC                  │
  ├─────────────────────────────────────────────────────┤
  │                                                     │
  │  MySQL InnoDB:                                      │
  │    旧版本 ──► 写入 undo log(独立结构)                │
  │    当前行 ──► 聚簇索引 B+Tree 中                    │
  │    读时顺着 ROLL_PTR 找旧版本                        │
  │    purge 线程清理 undo                               │
  │                                                     │
  │  PostgreSQL:                                        │
  │    旧版本 ──► 仍放在 heap(原表)中!                  │
  │    当前行 ──► heap 中                                │
  │    索引项 ──► 只指向最新 heap 位置,无版本            │
  │    VACUUM 清理死元组                                 │
  │                                                     │
  └─────────────────────────────────────────────────────┘
```

| 维度 | PG MVCC | MySQL InnoDB MVCC |
|------|---------|-------------------|
| 旧版本存储 | **heap 中**(与新版本同一页或新页) | undo log 段(独立结构) |
| 回滚段 | **无** | 有 |
| 索引中的版本 | **没有** | 有(二级索引含 trx_id) |
| 清理机制 | VACUUM(autovacuum) | purge 线程 |
| 膨胀位置 | heap 本身膨胀(table bloat) | undo tablespace 膨胀 |
| 可见性字段 | `xmin`、`xmax`、`t_infomask` | `DB_TRX_ID`、`DB_ROLL_PTR` |

```text
为什么 PG 的"版本就在 heap 里"是特色?

  优点:
    ① 没有 undo log,实现更干净
    ② 行级可见性靠 xmin/xmax,无需遍历版本链
    ③ 索引不需要存储事务信息,更紧凑
    ④ VACUUM 是常规操作,概念清晰

  代价:
    ① 表会膨胀(dead tuple 堆积)
    ② 需要及时 VACUUM,否则性能崩塌
    ③ UPDATE 频繁的场景膨胀更严重
    ④ 索引项 → heap 的 ctid 一旦变化,需要 vacuum 同步
```

### 5.3 Tuple Header 详解(★ 重点)

PostgreSQL 每个**堆元组(heap tuple)** 的行头(HeapTupleHeaderData)都包含**多个系统字段**,用于 MVCC 可见性判断。

#### 整体结构

```text
┌────────────────────────────────────────────────────────────────────────┐
│                    HeapTupleHeaderData (23 字节)                       │
├────────┬────────┬────────┬────────┬────────┬────────┬────────┬────────┤
│ t_xmin │ t_xmax │ t_cid  │t_xvac  │ t_infomask1 │ t_infomask2 │t_hoff│
│  4B    │  4B    │  4B    │  4B    │    1B        │    1B        │ 1B  │
├────────┴────────┴────────┴────────┴────────┴────────┴────────┴────────┤
│                  可选: NULL bitmap + 用户数据列                        │
└────────────────────────────────────────────────────────────────┘
```

**所有系统字段**(`SELECT *` 看不到,需显式 `SELECT xmin, xmax, ...`):

| 字段 | 大小 | 含义 |
|------|------|------|
| `xmin` | 4B | **插入此行的事务 ID**(或更老事务) |
| `xmax` | 4B | **删除/更新此行的事务 ID**;0 表示未删除 |
| `cmin` | 2B | 插入命令 ID(同一事务内多 SQL 区分) |
| `cmax` | 2B | 删除命令 ID |
| `xvac` | 4B | VACUUM FULL 移动此行的事务 ID(已弃用,实际存 cmax) |
| `t_infomask` | 2B | 标志位集合(行状态) |
| `t_hoff` | 1B | 行头到用户数据的偏移 |
| `t_ctid` | 6B | 当前行的物理位置(块号 + 槽号),UPDATE 后指向新行 |

#### 字段详细解释

##### xmin(插入事务 ID)

```text
xmin = 0         ← 此行不属于正常事务,极特殊
xmin > 0         ← 插入此行的事务 ID

作用:
  - 可见性算法核心:读快照时,判断"xmin 这个事务对我可见吗"
  - 如果快照时 xmin 已提交 → 行可见
  - 如果快照时 xmin 还在活跃 → 行不可见
  - 如果 xmin 等于自己 → 一定可见
```

##### xmax(删除/更新事务 ID)

```text
xmax = 0         ← 未被删除/更新
xmax > 0         ← 删除/更新此行的事务 ID

UPDATE 时的 xmax 行为:
  - UPDATE 不真正删除旧行
  - 旧行的 xmax = 当前事务 ID
  - 同时插入新行,新行的 xmin = 当前事务 ID,新行 xmax = 0
  - 新行的 t_ctid 指向自身(它是"链头")
  - 旧行的 t_ctid 仍指向自己(但被认作死元组)
```

##### t_infomask 标志位(共 16 位)

```text
t_infomask 主要位含义:

  HEAP_HASNULL       (1 << 0)    有 NULL 列
  HEAP_HASVARWIDTH   (1 << 1)    有变长字段
  HEAP_HASEXTERNAL   (1 << 2)    有外部存储(TOAST)
  HEAP_HASOID        (1 << 3)    包含 OID(老特性)
  
  HEAP_XMIN_COMMITTED (1 << 8)   xmin 已提交(可避免查 CLOG)
  HEAP_XMIN_INVALID   (1 << 9)   xmin 无效(已 abort/被替换)
  HEAP_XMAX_COMMITTED (1 << 10)  xmax 已提交
  HEAP_XMAX_INVALID   (1 << 11)  xmax 无效
  HEAP_XMIN_FROZEN    (1 << 12)  xmin 永久冻结(等同已提交所有事务都可见)
  HEAP_UPDATED        (1 << 13)  被当前事务更新过(行级锁标志)
  HEAP_MOVED_OFF      (1 << 14)  被 VACUUM FULL 搬走
  HEAP_MOVED_IN       (1 << 15)  被 VACUUM FULL 搬入
```

**最常用的几个**:

| 位 | 简称 | 含义 |
|----|------|------|
| `XMIN_COMMITTED` | xc | xmin 已提交,快照判断时无需查 CLOG |
| `XMIN_INVALID` | xi | xmin 是已 abort 的事务,行不可见 |
| `XMAX_COMMITTED` | xc | xmax 已提交,行已被删除 |
| `XMIN_FROZEN` | xf | xmin 被冻结,视为"永远已提交"(避免事务 ID 回卷) |

```sql
-- 查看实际行的系统字段
SELECT xmin, xmax, 
       CASE WHEN (t_infomask & 256) > 0 THEN 'yes' ELSE 'no' END AS xmin_committed,
       CASE WHEN (t_infomask & 2048) > 0 THEN 'yes' ELSE 'no' END AS xmax_committed,
       ctid
FROM user LIMIT 5;

-- xmin/xmax 实际是 xmin::text::xid8 输出
SELECT xmin::text::xid8, xmax::text::xid8, * FROM user;
```

### 5.4 Heap-Only Tuples (HOT) 原理(★ 重要)

#### 什么是 HOT

**HOT (Heap-Only Tuples)** 是 PostgreSQL 的**索引更新优化**:当一次 UPDATE 没有修改**任何被索引覆盖的列**时,数据库可以在**同一 heap 页内**插入新行,**所有索引项**继续指向旧行的 ctid,通过 ctid 链找到新行。

#### 没有 HOT 时的问题

```text
  假设表有索引 idx_name:

  UPDATE user SET age = 30 WHERE id = 1;
  -- age 不在索引中,但 PG 默认仍会:
  ① 在原行位置标记死元组(xmax = 当前 xid)
  ② 插入新行(新 ctid)
  ③ 更新所有索引,使其 ctid 指向新行
  → 索引 I/O 开销巨大
  → 高频 UPDATE 表的索引膨胀严重
```

#### HOT 流程图

```text
       不带 HOT 的 UPDATE                    带 HOT 的 UPDATE
  ┌──────────────────────┐             ┌──────────────────────┐
  │ 1. 标记旧行 xmax      │             │ 1. 标记旧行 xmax      │
  │ 2. 在某页插入新行     │             │ 2. 在原页插入新行     │
  │ 3. 更新所有索引       │             │ 3. 不更新索引!        │
  │ 4. 返回              │             │ 4. 旧行 t_ctid→新行  │
  └──────────────────────┘             └──────────────────────┘
  索引 I/O: O(n_indexes)               索引 I/O: 0
  性能: 慢                              性能: 极快
```

#### HOT 触发条件(三个都必须满足)

1. UPDATE **没有修改任何被索引覆盖的列**
2. 新行能够**放入同一 heap 页**(即页有空间)
3. 表**没有**使用 `fillfactor=100`(满页)

```sql
-- 查看表的 fillfactor
SELECT relname, reloptions FROM pg_class WHERE relname = 'user';

-- 调整 fillfactor,给 HOT 留出页内空间
ALTER TABLE user SET (fillfactor = 80);
-- 留 20% 页空间给 HOT 链使用
```

#### HOT 链结构

```text
  索引 idx_name                heap 页(同一页)
  ┌──────────────┐            ┌────────────────────────────────┐
  │ name = 'A'   │            │ 槽1: xmin=100 xmax=200 ctid→3 │ ← 旧行
  │ ctid = 1 ────────►        │  name='A' age=20               │
  └──────────────┘            │                                │
                              │ 槽2: ...其他行...             │
                              │                                │
                              │ 槽3: xmin=200 xmax=0           │ ← 新行
                              │  name='A' age=30  (更新后)     │
                              └────────────────────────────────┘

  索引仍指向槽1(旧行),但槽1 的 t_ctid 指向槽3(新行)
  → 读时顺着 ctid 链找到最新版本
```

#### HOT 的好处与限制

| 好处 | 限制 |
|------|------|
| 索引无需更新,极快 | 仅限"被索引覆盖的列未变"的 UPDATE |
| 减少 WAL 量 | 新行必须能装入原页 |
| 减少索引膨胀 | 不会跨页,长链会影响读性能 |
| 配合 fillfactor 效果最佳 | VACUUM 时才能回收死元组空间 |

```sql
-- 查看某表是否"利用了"HOT
SELECT relname,
       n_tup_upd AS total_updates,
       n_tup_hot_upd AS hot_updates,
       CASE WHEN n_tup_upd > 0 
            THEN round(100.0 * n_tup_hot_upd / n_tup_upd, 2) 
            ELSE 0 END AS hot_ratio_pct
FROM pg_stat_user_tables
WHERE relname = 'user';
-- hot_ratio_pct 越高越好,接近 100% 最佳
```

---

## 六、PG 的 MVCC 实现

### 6.1 核心机制

PostgreSQL 的 MVCC 由以下要素共同协作:

```text
┌──────────────────────────────────────────────────────────┐
│                 PostgreSQL MVCC 五要素                    │
├──────────────────────────────────────────────────────────┤
│  1. 事务 ID(xid)                                        │
│     - 32 位无符号整数,全局递增                           │
│     - 由事务第一次"做事"时分配                           │
│     - 区分插入/删除/更新语义                            │
│                                                          │
│  2. Tuple Header(xmin/xmax/t_infomask)                  │
│     - 每行自带系统字段                                   │
│     - 不需要独立锁表或回滚段                            │
│                                                          │
│  3. CLOG(Commit Log)                                    │
│     - 记录事务最终状态(提交/中止/进行中)                 │
│     - 位于 shared_buffers 中                            │
│     - 用于快速判断 xmin/xmax 是否已提交                 │
│                                                          │
│  4. Snapshot(快照)                                       │
│     - 事务在某时刻的一致性视图                           │
│     - 包含 xmin/xmax/xip 列表                          │
│                                                          │
│  5. VACUUM(清理)                                         │
│     - 回收死元组,防止膨胀                                │
│     - autovacuum 自动运行                                │
└──────────────────────────────────────────────────────────┘
```

### 6.2 xmin(插入事务)

```text
语义:
  xmin = 创建此行的事务 ID
  也可能为 FrozenTransactionId(2),代表"已冻结"

INSERT 时:
  - 分配当前事务的 xid
  - 写入行的 xmin
  - xmax = 0(未删除)
  - t_infomask 标记 XMIN_COMMITTED 仅在提交后才置

示例:
  BEGIN;
  INSERT INTO user(name) VALUES ('alice');
  -- 此时: xmin = 9999(当前事务), xmax = 0
  
  COMMIT;
  -- 提交后: xmin 仍为 9999,但 CLOG[9999] = committed
  -- t_infomask 的 HEAP_XMIN_COMMITTED 位置 1
```

### 6.3 xmax(删除/更新事务)

```text
语义:
  xmax = 删除/更新此行的事务 ID
  xmax = 0 代表此行"还活着"

DELETE 时:
  - 找到目标行
  - 把它的 xmax 设为当前事务 ID
  - 注意:不真正删除,只是标记
  
UPDATE 时(关键):
  - 不删除原行
  - 把原行 xmax 设为当前事务 ID(原行变死元组)
  - 插入新行(同表或新表)
  - 新行 xmin = 当前事务 ID, xmax = 0
  - 新行 t_ctid 指向自身
```

### 6.4 时序图:xmin/xmax 全过程

```text
   事务 100 启动
   ─────────────────────────────────────────────────────►
   INSERT INTO user VALUES (1, 'alice', 20)
        │
        ├─► heap 中插入新行
        │   ┌────────────────────────────┐
        │   │ xmin = 100  xmax = 0       │
        │   │ id=1 name='alice' age=20   │
        │   │ t_ctid = (0,1)             │
        │   └────────────────────────────┘
        │
   COMMIT;
   ├─► CLOG[100] = committed
   ├─► 行的 t_infomask |= XMIN_COMMITTED

   ─────────── 时间线 ─────────────────────────────────►

   事务 200 启动
   UPDATE user SET age = 25 WHERE id = 1;
        │
        ├─► 找到原行(0,1)
        │
        ├─► 标记原行 xmax = 200
        │   ┌────────────────────────────┐
        │   │ xmin = 100  xmax = 200     │ ← 死元组
        │   │ id=1 name='alice' age=20   │
        │   │ t_ctid = (0,1)             │
        │   └────────────────────────────┘
        │
        ├─► 在某页(可能是同页/HOT)插入新行
        │   ┌────────────────────────────┐
        │   │ xmin = 200  xmax = 0       │ ← 当前行
        │   │ id=1 name='alice' age=25   │
        │   │ t_ctid = (0,5)             │
        │   └────────────────────────────┘
        │
        ├─► 更新所有涉及索引项(非 HOT 情况下)
        │   idx_name['alice']: ctid 从 (0,1) 改为 (0,5)
        │
   COMMIT;
   ├─► CLOG[200] = committed
   ├─► 死元组等待 VACUUM 回收

   ─────────── 时间线 ─────────────────────────────────►

   事务 300 启动
   DELETE FROM user WHERE id = 1;
        │
        ├─► 找到当前行(0,5)
        │
        ├─► 标记 xmax = 300
        │   ┌────────────────────────────┐
        │   │ xmin = 200  xmax = 300     │ ← 又一死元组
        │   │ id=1 name='alice' age=25   │
        │   └────────────────────────────┘
        │
   COMMIT;
   ├─► VACUUM 后这些死元组空间被回收
```

### 6.5 关键时序行为

```text
        ┌───────────────────────────────────────────────┐
        │         同一事务内,自己的 xmin 一定可见         │
        │         自己的 xmax 删除/更新也一定生效         │
        │         (但还没提交,别人看不到)                │
        └───────────────────────────────────────────────┘

具体表现:
  BEGIN;
  UPDATE user SET age = 99 WHERE id = 1;
  -- 此时 SELECT 看到 age=99(本事务可见)
  -- 别人 SELECT 仍看到 age=25(xmax=当前xid 未提交)
  ROLLBACK;
  -- 别人 SELECT 重新看到 age=25
  -- 自己的 SELECT 也看到 age=25(因为 xmax 失败)
```

### 6.6 事务 ID 回卷(XID Wraparound)

```text
32 位 xid:
  总数 2^32 ≈ 43 亿
  即使每秒 1000 个事务,跑 13 年才会耗尽

但 PG 不会真等耗尽:
  - xid 是循环使用的
  - "未来"事务的 xid 可能小于"过去"
  - 可见性算法靠"xmin < xid < xmax" 范围判断
  - 一旦 xid 回卷,可见性判断会出错

解决方案:
  - 引入 FrozenTransactionId(2)
  - xmin = 2 的行视为"对所有事务可见"
  - VACUUM 定期把"足够老"的 xmin 冻结为 2
  - autovacuum_freeze_max_age 控制触发冻结的年龄

监控:
  SELECT datname, age(datfrozenxid) FROM pg_database;
  -- age 接近 2^31 就要紧急 VACUUM
```

---

## 七、快照 (Snapshot)

### 7.1 什么是快照

**快照 (Snapshot)** 是事务在某个时刻拍下的**一致性视图**,记录了"在我开始读时,哪些事务是活跃的、版本边界在哪"。

有了快照,就能判断某行数据的**某个版本对我是否可见**。

### 7.2 pg_snapshot 数据结构

```c
typedef struct SnapshotData {
    TransactionId  xmin;       // 活跃事务中最小 ID
    TransactionId  xmax;       // 快照创建时已分配的下一个 ID
    TransactionId *xip;        // 活跃事务 ID 数组
    uint32         xcnt;       // 活跃事务个数
    ...
    CommandId      curcid;     // 当前命令 ID
} SnapshotData;
```

| 字段 | 含义 |
|------|------|
| `xmin` | 快照创建时**仍在活跃**的事务中**最小**的 ID;<此 ID 的事务**必提交** |
| `xmax` | 快照创建时**已分配但**所有小于它的要么已提交要么还活跃(边界) |
| `xip[]` | 快照创建时**仍在活跃**的事务 ID 列表(不包括自己) |
| `curcid` | 当前命令 ID(用于区分同事务内多 SQL) |

```text
  活跃事务:[100, 200, 300](都在跑)
  已提交事务:50, 80
  下一个将要分配的事务 ID:500

  此时创建的 Snapshot:
    xmin  = 100
    xmax  = 500
    xip[] = [100, 200, 300]

  含义:
    ① xid < 100 一定已提交 → 可见
    ② xid >= 500 一定还没启动 → 不可见
    ③ xid in [100, 200, 300] 不可见(还没提交)
    ④ xid in [301, 499] 看 CLOG:已提交就可见
```

### 7.3 可见性判断规则

对一个元组 `(xmin, xmax)`,在快照 `S` 中是否可见,规则如下:

```text
设快照 S 的 xmin=S.xmin, xmax=S.xmax, xip=S.xip

判断此行是否对 S 可见:

  1. 先看 xmax:
     如果 xmax != 0 且 xmax 已提交/未中止
        且 xmax != 自己的 xid
        且 (xmax == S.xmin 或 xmax in S.xip 或 xmax > S.xmax)
        → 行已被删除,不可见

  2. 再看 xmin:
     如果 xmin == 自己的 xid → 可见
     如果 xmin in S.xip → 不可见(别人还没提交)
     如果 xmin < S.xmin → 看 CLOG:已提交就可见
     如果 xmin >= S.xmax → 不可见
     如果 xmin 已提交(看 CLOG) → 可见
     否则 → 不可见
```

简化版规则(更直观):

```text
  xmin 对快照可见 ← → 满足下列之一:
    ① xmin == 自己(我插的,一定见)
    ② xmin 已提交 且 xmin < S.xmax
       且 (xmin < S.xmin 或 xmin 不在 S.xip)
    ③ xmin == FrozenTransactionId(2)

  xmax 对快照不可见 ← → 满足下列之一:
    ① xmax == 0
    ② xmax 未提交
    ③ xmax == 自己(我自己删的,还可见)
    ④ xmax 已中止
```

### 7.4 快照获取函数

```sql
-- 当前事务快照(实际获取的是 xmin::text::xid8 形式)
SELECT pg_current_snapshot();

-- 返回类似:1000:1010:1001,1002,1003
-- 含义: xmin=1000, xmax=1010, xip=[1001,1002,1003]

-- 解析快照
SELECT pg_snapshot_xmin(pg_current_snapshot()),     -- 1000
       pg_snapshot_xmax(pg_current_snapshot()),     -- 1010
       pg_snapshot_xip(pg_current_snapshot());      -- {1001,1002,1003}
```

### 7.5 快照的"级别"由谁决定

```text
  READ COMMITTED:
    - 每个语句开始时取新快照
    - PG 内部调用 GetSnapshotData() 在每条 SQL 之前

  REPEATABLE READ:
    - 事务第一个 SQL 时取快照
    - 整个事务复用

  SERIALIZABLE:
    - 同 RR,但增加 SSI 冲突检测

  注:严格来说,PG 的快照"复用"是基于"事务是否需要"决定。
     RC 下,每条 SQL 都新建;RR/Serial 下,事务级别只建一次。
```

---

## 八、Read Committed 隔离级别行为

### 8.1 核心特征

**READ COMMITTED** 是 PostgreSQL **默认**的隔离级别。

- 每条 SQL 语句**开始时**新建快照
- 能看到语句执行前**已提交**的修改
- 同事务内两条 SQL 可能看到不同数据
- UPDATE/DELETE 会"重新评估 WHERE"

### 8.2 行为细节

```text
  事务 A: SET TRANSACTION ISOLATION LEVEL READ COMMITTED;

  序列:
    1. SELECT ...     (快照1: t1 时刻)
    2. SELECT ...     (快照2: t2 时刻,与 t1 不同!)
    3. UPDATE ...     (会读到最新已提交数据后,再应用 WHERE)
    4. SELECT ...     (快照3: t3 时刻)
```

### 8.3 关键特性:UPDATE 看到新数据

**这是 PG 的 RC 与其他数据库不同的细节**:

```text
  -- Session A
  BEGIN ISOLATION LEVEL READ COMMITTED;
  SELECT balance FROM acct WHERE id = 1;  -- → 100

                                  -- Session B
                                  BEGIN;
                                  UPDATE acct SET balance = 200 WHERE id = 1;
                                  -- B 还未提交

  UPDATE acct SET balance = balance + 10 WHERE id = 1;
  -- 这条 UPDATE 会:
  -- ① 等待 Session B 提交或回滚
  -- ② 如果 B 提交:读到 200,SET balance = 210
  -- ③ 如果 B 回滚:读到 100,SET balance = 110

  -- 这是 RC 级别 UPDATE 的"读最新"语义,与 SELECT 的"读快照"不同!
```

```text
  时序图:

  时间 ──────────────────────────────────────►

  T1 (Session A):                          T2 (Session B):
  BEGIN ISOLATION RC
  SELECT balance → 100
                                           BEGIN
                                           UPDATE → 200(未提交)
                                           (B 的 xmax 设了)
  UPDATE balance = balance + 10
    │
    ├── 发现 id=1 行的 xmax 有效(未提交)
    │   → 等待 B 提交/回滚
    │
    ├── B COMMIT 后, B 的 xmax 被标 committed
    │   → A 重新读最新版本(200)
    │   → 计算: 200 + 10 = 210
    │   → 写入新版本 xmin = A.xid
    │
    └── COMMIT
```

### 8.4 适用场景

| 场景 | RC 是否适合 |
|------|------------|
| 短事务、OLTP | 适合,默认就好 |
| 报表统计 | 不适合,中间数据可能变 |
| 多次读需要一致快照 | 不适合,要用 RR |
| 高并发更新单行 | 适合,UPDATE 自动重试机制更优 |

---

## 九、Repeatable Read 隔离级别

### 9.1 核心特征

**REPEATABLE READ** 提供**事务级快照**:

- 事务**第一条 SQL** 时建立快照
- 整个事务**复用**此快照
- 同事务内多次读,结果一致
- **不解决**写偏序(只有 SERIALIZABLE 解决)

```sql
BEGIN ISOLATION LEVEL REPEATABLE READ;
  -- 此时不分配快照
  SELECT * FROM user WHERE id = 1;  -- 第一次 SQL,分配快照
  -- 后续所有 SQL 都用这个快照
  SELECT * FROM user WHERE id = 1;  -- 同一快照
COMMIT;
```

### 9.2 行为演示

```text
  -- Session A                        -- Session B
  BEGIN ISOLATION LEVEL RR;
                                      BEGIN;
                                      UPDATE user SET age = 30 WHERE id = 1;
                                      COMMIT;  -- 已提交
  SELECT age FROM user WHERE id = 1;  → 20
                                       ← 看不到 B 的修改!
  SELECT age FROM user WHERE id = 1;  → 20
                                       ← 仍然看不到
  COMMIT;
```

```text
  -- Session A                        -- Session B
  BEGIN ISOLATION LEVEL RR;
  SELECT * FROM user WHERE id = 1;
                                      UPDATE user SET age = 30 WHERE id = 1;
                                      -- 不阻塞,A 没锁住
                                      COMMIT;
  UPDATE user SET age = age + 1 
    WHERE id = 1;
  -- 这条 UPDATE 在 RR 下仍然能"读最新已提交"
  -- 然后基于最新数据 + 1
  -- ★ PG 的 UPDATE 在 RR 下不严格"基于快照"!
  -- 但 SELECT 仍然基于快照
  COMMIT;
```

### 9.3 与 MySQL RR 的关键差异

| 维度 | PG REPEATABLE READ | MySQL InnoDB RR |
|------|-------------------|-----------------|
| 实现 | **Snapshot Isolation** | Snapshot Isolation + Gap Lock |
| 幻读(快照读) | **不发生** | 不发生 |
| 幻读(当前读) | **可能**(因为无 Gap Lock) | 不发生(Next-Key Lock) |
| 写偏序 | 可能 | 可能 |
| 唯一键冲突 | 不阻塞,直接报错 | 可能 Gap Lock 阻塞 |

```text
  ★ 重要:
    PostgreSQL 的 REPEATABLE READ 是"加强版":
    - 比 SQL 标准 RR 更严(标准 RR 允许幻读)
    - 但比 SERIALIZABLE 弱(允许写偏序)
    
    PG 官方称:
      "REPEATABLE READ provides a stricter guarantee than SQL standard"
```

### 9.4 适用场景

```text
  适合 REPEATABLE READ 的场景:
    - 报表统计(确保同事务内多张表的数据一致)
    - 数据导出(导出的过程数据不被修改)
    - 复杂计算(基于同一快照算多步)
    - 测试场景(可重放)

  不适合 REPEATABLE READ 的场景:
    - 纯 OLTP 高并发写入(没有写偏序保护)
    - 业务上有"我要写,别人也要写"的需要(应用 SERIALIZABLE)
```

### 9.5 注意事项

```text
  REPEATABLE READ 下的 UPDATE:
    ① SELECT 仍然只看到快照
    ② 但 UPDATE 会"读最新已提交版本",再应用 WHERE
    ③ 这意味着 RR 下仍可能有"读后写"语义偏差
    ④ 如果 RR 下 UPDATE 没匹配到行,会返回 0 rows
       即使最新数据有匹配(因为 WHERE 用的是最新已提交数据)
       注意:这里"用最新已提交数据"与"用快照数据"行为不同
```

---

## 十、Serializable (SSI) 隔离级别

### 10.1 什么是 SSI

**SSI (Serializable Snapshot Isolation)** 是 PostgreSQL 9.1 引入的**真正可串行化**机制。

```text
  Snapshot Isolation (SI):
    - 事务读自己快照
    - 写时检测"first-updater-wins"(写写冲突)
    - 解决丢失更新
    - 但仍可能写偏序
    
  Serializable Snapshot Isolation (SSI):
    - 在 SI 基础上增加"序列化异常检测"
    - 检测写偏序、读偏序等异常
    - 违反时让其中一个事务 abort
    - 应用层需捕获错误并重试
```

### 10.2 为什么需要 SSI

**SI 的盲区:写偏序 (Write Skew)**

```text
  场景:医院值班表

  数据:doctor A、B,C 都在值班
  规则:值班至少要有 1 个医生

  -- Session A                  -- Session B
  BEGIN ISOLATION RR;            BEGIN ISOLATION RR;
  SELECT COUNT(*) WHERE 
    on_duty = true;  → 3        SELECT COUNT(*) WHERE 
                                   on_duty = true;  → 3
  UPDATE doc_A 
    SET on_duty = false;
                                 UPDATE doc_B 
                                   SET on_duty = false;
  COMMIT;                        COMMIT;
  
  最终: 0 个医生值班!
  串行化期望:至少 1 个
  
  → RR 下通过(因为是不同行,无写写冲突)
  → SSI 下被检测到,其中一个事务会 abort
```

### 10.3 SSI 的工作原理

**SSI 基于"谓词锁 (Predicate Lock)"** 的优化版本(**SI 谓词锁**),不真正锁定整张表,而是**追踪事务间的依赖关系**。

```text
  三大数据结构:
    ① rw-antidependency(读反依赖):T1 读 X,T2 写 X
       → T1 影响了 T2
    ② ww-antidependency(写反依赖):T1 写 X,T2 写 X
       → 已通过 first-updater-wins 检测
    ③ 序列化异常图(Serialization Conflict Graph):
       - 节点:事务
       - 有向边:rw-antidependency
       - 检测:是否形成环
       - 有环 → 一个事务必须 abort
```

```text
  检测简化逻辑:

       T1 ─rw-antidep──► T2
       ▲                    │
       └────rw-antidep──────┘
       
       环! → T1 和 T2 不可能都串行成功
            → 选一个 abort
```

### 10.4 SSI vs 2PL 对比

| 维度 | SSI (PG 实现) | 2PL (传统锁) |
|------|--------------|--------------|
| 读操作 | **不阻塞**(读不持锁) | 可能阻塞(共享锁) |
| 写操作 | 写时仍需行级锁 | 全程持锁 |
| 并发度 | **高**(读多写少优势明显) | 低 |
| 谓词锁 | **优化为 SI 谓词锁**(轻量) | 真谓词锁(重) |
| 死锁 | 概率小 | 概率高 |
| 异常检测 | 提交时检测 | 运行时阻止 |
| 失败重试 | 必须由应用重试 | 不需要(直接阻塞) |
| 实现复杂度 | 复杂 | 简单 |

```text
  形象对比:

  2PL:
    任何读写都要先拿锁
    冲突 → 等待
    高并发场景下"锁等待"严重
    像"单车道"靠信号灯管理

  SSI:
    读完全无锁
    写仍加行级锁
    并发跑完,提交时检查
    像"多车道"靠事后检查避免撞车
```

### 10.5 SSI 的代价

```text
  代价:
    ① 内存开销:PG 需为每个 SERIALIZABLE 事务保存谓词信息
    ② 误杀:可能 abort 实际"不冲突"的事务(保守)
    ③ 重试成本:应用必须实现自动重试逻辑
    ④ 性能:比 RR 慢 5-20%(取决于冲突率)
    ⑤ 监控:需要监控 serializable_conflicts 计数
```

### 10.6 SSI 配置与监控

```sql
-- 1. 设置事务级 SERIALIZABLE
BEGIN ISOLATION LEVEL SERIALIZABLE;
  -- 业务 SQL
COMMIT;

-- 2. 设置会话默认
SET SESSION CHARACTERISTICS AS TRANSACTION ISOLATION LEVEL SERIALIZABLE;

-- 3. 应用层必须捕获并重试
DO $$
BEGIN
  -- 业务
EXCEPTION
  WHEN serialization_failure THEN
    -- PG error code: 40001
    RAISE NOTICE 'serialization failure, retry...';
    -- 重试逻辑
END $$;

-- 4. 监控
SELECT datname, 
       confl_serializable AS serializable_conflicts,
       confl_deadlock     AS deadlocks
FROM pg_stat_database
WHERE datname = current_database();
```

### 10.7 适用场景

| 场景 | SSI 适合度 |
|------|----------|
| 金融账务(扣库存 + 扣款) | 强推荐 |
| 多步骤业务规则 | 强推荐 |
| 读写冲突高的并发业务 | 强推荐 |
| 简单 OLTP(无业务规则) | 不必,RC 即可 |
| 报表统计 | 不必,RR 即可 |
| 极高并发写 | 需评估,SSI 重试可能放大写冲突 |

---

## 十一、显式锁 (Explicit Locking)

### 11.1 行级锁四种模式

PostgreSQL 在 `SELECT` 时可以**显式加锁**,有四种模式:

| 模式 | 命令 | 锁含义 | 阻塞对象 |
|------|------|--------|----------|
| **FOR UPDATE** | `SELECT ... FOR UPDATE` | 排他锁 | 其它所有行锁 + 同事务可 UPDATE/DELETE |
| **FOR NO KEY UPDATE** | `SELECT ... FOR NO KEY UPDATE` | 弱排他 | 同 FOR UPDATE,但不阻塞 FK 检查 |
| **FOR SHARE** | `SELECT ... FOR SHARE` | 共享锁 | 其它 FOR UPDATE |
| **FOR KEY SHARE** | `SELECT ... FOR KEY SHARE` | 弱共享 | 其它 FOR UPDATE/FOR NO KEY UPDATE |

```sql
-- 1. FOR UPDATE:最强的行锁
SELECT * FROM user WHERE id = 1 FOR UPDATE;
-- 其它事务:不能 UPDATE/DELETE/SELECT FOR UPDATE/SELECT FOR NO KEY UPDATE
-- 其它事务:可以 SELECT FOR SHARE/SELECT FOR KEY SHARE

-- 2. FOR NO KEY UPDATE:不影响 FK 检查
SELECT * FROM user WHERE id = 1 FOR NO KEY UPDATE;
-- 其它事务:不能 UPDATE 本行(修改非键列)/FOR UPDATE/FOR NO KEY UPDATE
-- 其它事务:可以 UPDATE(只修改 FK 引用的键列) ← 关键!
-- 适用:不影响 FK 的列修改

-- 3. FOR SHARE:共享锁,可读但不能改
SELECT * FROM user WHERE id = 1 FOR SHARE;
-- 其它事务:可以 SELECT(快照读)
-- 其它事务:可以 SELECT FOR SHARE
-- 其它事务:不能 UPDATE/DELETE/SELECT FOR UPDATE

-- 4. FOR KEY SHARE:最弱,只保护键
SELECT * FROM user WHERE id = 1 FOR KEY SHARE;
-- 其它事务:可以 UPDATE 任何非键列
-- 其它事务:不能 UPDATE/DELETE 主键或被 FK 引用的列
-- 适用:FK 引用的父行保护
```

### 11.2 NOWAIT 与 SKIP LOCKED

```sql
-- NOWAIT:拿不到锁立即报错
SELECT * FROM user WHERE id = 1 FOR UPDATE NOWAIT;
-- ERROR: 55P03 could not obtain lock on row in relation "user"

-- SKIP LOCKED:跳过已锁定的行
SELECT * FROM job_queue
WHERE status = 'pending'
ORDER BY id
LIMIT 10
FOR UPDATE SKIP LOCKED;
-- 不等待,直接跳过别人正在处理的行
-- 典型应用:任务队列并发消费
```

### 11.3 行锁存在哪里(★ PG 特色)

```text
  PG 的行锁与 MVCC 巧妙结合:

  锁不在独立内存结构,而是"藏在行头里"。

  T1: SELECT * FROM user WHERE id = 1 FOR UPDATE;
  T1 在 (id=1) 行的 xmax 上设置 = T1.xid
  T1 的 infomask 上 HEAP_UPDATED 位置 1

  T2: SELECT * FROM user WHERE id = 1 FOR UPDATE;
  T2 看到 (id=1) 行的 xmax != 0 且未提交
  T2 阻塞,等待

  T1 COMMIT 后, xmax = committed
  T2 解锁,发现 xmax 已提交,转为"行已删除"判断
  T2 看到 T1 的修改(若 T1 改了字段)
  
  → 行锁本质是"我对这行的更新意图"
  → 可见性算法自然形成锁
```

### 11.4 表级显式锁

```sql
-- 显式加表锁
LOCK TABLE user IN ACCESS EXCLUSIVE MODE;
LOCK TABLE user IN SHARE MODE NOWAIT;

-- 应用场景:
-- 1. 批量维护:确保表结构/数据不被并发修改
-- 2. 跨事务的"独占窗口"
```

---

## 十二、子事务与 SAVEPOINT

### 12.1 子事务的本质

```text
  概念模型:
    BEGIN
    ├── 顶层事务
    │     ├── SQL
    │     ├── SAVEPOINT sp1
    │     │     ├── 子事务 1
    │     │     │     ├── SQL
    │     │     │     └── ROLLBACK TO sp1 ← 子事务 1 撤销
    │     │     └── 子事务结束(不写 COMMIT)
    │     └── SQL
    └── COMMIT ← 顶层事务提交
```

**SAVEPOINT 在 PG 内部映射为子事务 ID**,通过 `xid` 之外的 subxid 机制实现。

### 12.2 SAVEPOINT 与 ROLLBACK TO 的区别

```text
ROLLBACK;
  - 撤销整个事务的所有修改
  - 事务结束

ROLLBACK TO SAVEPOINT name;
  - 撤销该保存点之后的所有修改
  - 事务继续,可以继续做新 SQL
  - 释放该保存点之后的所有资源(锁、序列等)
```

### 12.3 应用场景

```sql
-- 复杂业务,部分失败不影响整体
BEGIN;
  INSERT INTO order_header (...) VALUES (...);
  
  SAVEPOINT before_items;
  INSERT INTO order_item (...) VALUES (item1);
  INSERT INTO order_item (...) VALUES (item2);
  -- item2 失败(比如违反约束)
  ROLLBACK TO SAVEPOINT before_items;
  -- order_item 表回退,但 order_header 仍保留
  
  INSERT INTO order_item (...) VALUES (item3);  -- 换一行
  RELEASE SAVEPOINT before_items;
COMMIT;

-- 另一个应用:错误处理
DO $$
BEGIN
  INSERT INTO log (msg) VALUES ('start');
  SAVEPOINT safe_point;
  PERFORM do_complex_business();
EXCEPTION
  WHEN OTHERS THEN
    ROLLBACK TO SAVEPOINT safe_point;
    INSERT INTO log (msg) VALUES ('failed: ' || SQLERRM);
END $$;
```

### 12.4 性能注意

```text
SAVEPOINT 的开销:
  - 分配 subxid
  - 写入 pg_subtrans(共享内存中,大小有限)
  - 频繁 SAVEPOINT 会消耗资源

不要做的事:
  - 在循环里频繁 SAVEPOINT/RELEASE(每次分配 subxid)
  - 依赖 SAVEPOINT 做"业务事务"边界(应拆成多个事务)
```

---

## 十三、客户端 Advisory Lock

### 13.1 什么是 Advisory Lock

**Advisory Lock(应用级锁)** 是 PG 提供的"由应用语义决定用途"的锁。它**不锁定任何数据库对象**,仅靠一个 **64 位整数 key** 区分,完全由应用决定它的含义。

```text
  应用场景:
    - 分布式锁(集群里多个应用协调)
    - 任务队列(防止重复消费)
    - 资源互斥(同一时刻只能一个任务跑)
    - 业务级排他(对某用户某资源)
```

### 13.2 Advisory Lock 函数

| 函数 | 粒度 | 释放时机 |
|------|------|----------|
| `pg_advisory_lock(key)` | 会话级 | 会话结束或显式释放 |
| `pg_advisory_lock(key1, key2)` | 会话级 | 同上 |
| `pg_try_advisory_lock(key)` | 会话级 | 立即返回(true/false) |
| `pg_advisory_xact_lock(key)` | 事务级 | 事务结束自动释放 |
| `pg_try_advisory_xact_lock(key)` | 事务级 | 立即返回 |
| `pg_advisory_unlock(key)` | - | 显式释放会话锁 |
| `pg_advisory_unlock_all()` | - | 释放当前会话所有 |

```sql
-- 1. 会话级锁(显式释放)
SELECT pg_advisory_lock(12345);
-- ... 业务 ...
SELECT pg_advisory_unlock(12345);

-- 2. 尝试锁(非阻塞)
SELECT pg_try_advisory_lock(12345);
-- 返回: true / false

-- 3. 事务级锁(自动释放)
BEGIN;
SELECT pg_advisory_xact_lock(12345);
-- 任何时刻只有一个事务能拿到
-- COMMIT/ROLLBACK 后自动释放
COMMIT;

-- 4. 双 key(更细粒度)
SELECT pg_advisory_lock(1, 1000);  -- (key1, key2)
```

### 13.3 实战:分布式任务锁

```sql
-- 场景:集群里多个 worker 抢同一任务
-- 任务 ID: 12345

-- Worker 1:
SELECT pg_try_advisory_lock(12345);
-- 返回: true(抢到)
-- 开始处理任务
-- ... 业务逻辑 ...
SELECT pg_advisory_unlock(12345);

-- Worker 2(同时):
SELECT pg_try_advisory_lock(12345);
-- 返回: false(没抢到)
-- 跳过这个任务,等下一轮
```

### 13.4 实战:跨表资源互斥

```sql
-- 场景:确保同一用户 ID 在同一时刻只能有一个业务流程
-- 用 (namespace, user_id) 作为 key

-- namespace = 1(订单业务)
SELECT pg_advisory_xact_lock(1, 100);  -- 锁定用户 100 的订单业务
INSERT INTO order (...) VALUES (...);
UPDATE inventory SET ...;
COMMIT;  -- 自动释放
```

### 13.5 Advisory Lock vs 传统锁

| 特性 | Advisory Lock | 行锁/表锁 |
|------|--------------|----------|
| 锁定对象 | 任意 64-bit key | 数据库对象(表/行) |
| 是否需要实际对象存在 | **否** | 是 |
| 释放时机 | 会话/事务结束 | 事务结束 |
| 在哪存储 | shared memory | 行头/锁表 |
| 能否跨数据库 | **否** | 否(行锁) |
| 自动清理 | 会话断开自动清理 | 会话断开自动清理 |

### 13.6 注意事项

```text
  陷阱 1: 死锁
    T1: pg_advisory_lock(1)
    T2: pg_advisory_lock(2)
    T1: pg_advisory_lock(2)  ← 等待 T2
    T2: pg_advisory_lock(1)  ← 等待 T1
    → 死锁
    解决:固定顺序获取锁

  陷阱 2: 会话断开未释放
    进程异常崩溃 → 锁未释放
    PG 会话结束会自动释放(共享内存中标记)
    但需要等 TCP 连接超时检测

  陷阱 3: 锁 key 冲突
    不同业务用同一个 key → 误锁
    解决:用 namespace(双 key)隔离
```

---

## 十四、事务最佳实践

### 14.1 避免长事务

```text
长事务的危害:
  ① 持有大量行级锁,阻塞其他事务
  ② PG 的快照变大,可见性判断变慢
  ③ 死元组无法被 VACUUM 回收(膨胀)
  ④ WAL 日志持续累积
  ⑤ autovacuum 无法处理"超过 freeze_max_age"的表

监控:
  SELECT pid, usename, state, query_start,
         xact_start, NOW() - xact_start AS duration
  FROM pg_stat_activity
  WHERE xact_start IS NOT NULL
  ORDER BY xact_start;
```

**经验法则**:

```text
  OLTP 事务: < 1s
  批量事务: < 10min,且分批提交
  数据迁移: 禁用 autocommit,每 1000 行 COMMIT
  报表: 拆成多个小事务,使用临时表
```

### 14.2 合理设置隔离级别

```text
决策树:

  你的业务是否有"写偏序"风险?
    ├─ 否 → RC(默认,最快)
    └─ 是
        │
        是否有"多次读需一致"需求?
          ├─ 否 → RC + 显式行锁(FOR UPDATE)
          └─ 是
              │
              业务上能否接受"重试"?
                ├─ 否 → 退回到 RC + 显式行锁
                └─ 是 → SERIALIZABLE(SSI)
```

### 14.3 错误处理与 SAVEPOINT

```sql
-- 业务级错误处理模板
DO $$
DECLARE
  v_retry_count INT := 0;
BEGIN
  LOOP
    BEGIN
      -- 业务逻辑
      INSERT INTO order (...) VALUES (...);
      UPDATE inventory SET qty = qty - 1 WHERE id = ?;
      EXIT;  -- 成功,退出循环
    EXCEPTION
      WHEN serialization_failure THEN  -- 40001
        v_retry_count := v_retry_count + 1;
        IF v_retry_count > 3 THEN
          RAISE;
        END IF;
        -- 短暂等待后重试
        PERFORM pg_sleep(0.1 * v_retry_count);
      WHEN deadlock_detected THEN  -- 40P01
        v_retry_count := v_retry_count + 1;
        IF v_retry_count > 3 THEN
          RAISE;
        END IF;
        PERFORM pg_sleep(0.1 * v_retry_count);
      WHEN OTHERS THEN
        RAISE;  -- 业务错误,不重试
    END;
  END LOOP;
END $$;
```

### 14.4 autocommit 与显式事务

```sql
-- 推荐:始终 autocommit = ON
-- 多语句时显式 BEGIN ... COMMIT

-- 反例:依赖 autocommit = OFF
-- 容易忘记 COMMIT,导致长事务
```

### 14.5 批处理最佳实践

```sql
-- 1. 分批提交(避免长事务)
DO $$
DECLARE
  v_batch INT := 1000;
  v_count INT;
BEGIN
  LOOP
    WITH del AS (
      DELETE FROM log 
      WHERE id IN (
        SELECT id FROM log 
        WHERE created_at < NOW() - INTERVAL '30 days'
        LIMIT v_batch
      )
      RETURNING 1
    )
    SELECT COUNT(*) INTO v_count FROM del;
    EXIT WHEN v_count = 0;
    COMMIT;  -- 每批一次提交
  END LOOP;
END $$;

-- 2. 使用 COPY(不要 INSERT INTO ... VALUES (...), (...))
COPY log FROM '/tmp/data.csv' WITH CSV;

-- 3. 关闭同步提交(可丢数据的场景)
SET LOCAL synchronous_commit = OFF;
-- 临时降低持久性换性能
```

### 14.6 监控与调优

```sql
-- 1. 事务统计
SELECT datname, 
       xact_commit,           -- 提交数
       xact_rollback,         -- 回滚数
       conflicts,             -- 序列化冲突
       deadlocks,             -- 死锁数
       blks_read, blks_hit
FROM pg_stat_database;

-- 2. 长事务告警
SELECT pid, query, NOW() - xact_start AS tx_duration
FROM pg_stat_activity
WHERE xact_start < NOW() - INTERVAL '5 minutes'
  AND state <> 'idle'
ORDER BY xact_start;

-- 3. 表膨胀监控
SELECT schemaname, relname, 
       n_dead_tup, n_live_tup,
       round(100.0 * n_dead_tup / NULLIF(n_live_tup + n_dead_tup, 0), 2) AS dead_ratio_pct
FROM pg_stat_user_tables
WHERE n_dead_tup > 10000
ORDER BY n_dead_tup DESC;
```

### 14.7 常见反模式

```text
反模式 1: 应用层做事务
  - 错误:在应用代码里"补偿"事务
  - 正确:用数据库事务 + SAVEPOINT
  
反模式 2: 一个事务做太多事
  - 错误:循环里 INSERT,100 万行一个事务
  - 正确:每 1000 行一个事务

反模式 3: 长事务 + 交互式
  - 错误:BEGIN ... 等用户输入 ... COMMIT
  - 正确:用户交互完再开事务

反模式 4: 误用 SERIALIZABLE
  - 错误:任何业务都 SERIALIZABLE
  - 正确:只为真正需要"防写偏序"的事务用

反模式 5: 不监控死元组
  - 错误:从不 VACUUM
  - 正确:autovacuum 调优 + 定期 VACUUM
```

---

## 十五、PG MVCC 与 MySQL MVCC 对比(总览)

### 15.1 核心差异

| 维度 | PostgreSQL | MySQL InnoDB |
|------|-----------|--------------|
| 旧版本存储 | heap 表中(同行存) | undo log 段 |
| 元组头 | `xmin/xmax/infomask` | `DB_TRX_ID/DB_ROLL_PTR` |
| 索引中的版本 | **无** | 有 |
| 索引项大小 | 较小 | 较大 |
| UPDATE 行为 | 标记旧行 + 插新行 | 标记旧行 + 插新行(但旧行在 undo) |
| 清理机制 | VACUUM(autovacuum) | purge 线程 |
| 表膨胀位置 | 表本身 | undo tablespace |
| 默认隔离 | READ COMMITTED | REPEATABLE READ |
| 可串行化实现 | SSI | 退化当前读+锁 |
| 索引覆盖列 | 不区分 | 影响锁类型(Next-Key) |

### 15.2 数据可见性算法对比

```text
  MySQL InnoDB (READ COMMITTED):
    1. 拿当前行 DB_TRX_ID
    2. 查 Read View(由 m_ids, min_id, max_id, creator_id 组成)
    3. 不可见 → 沿 DB_ROLL_PTR 跳到旧版本
    4. 重复 1-3,直到链尾或可见

  PostgreSQL (READ COMMITTED):
    1. 拿当前行 xmin, xmax
    2. 用快照(xmin, xmax, xip[])直接判断
    3. CLOG 加速判断(避免查 PG_XACT)
    4. 无版本链跳转(版本就在 heap 里)
```

### 15.3 性能与运维对比

| 维度 | PG | MySQL |
|------|-----|-------|
| UPDATE 性能 | 中等(heap 复制) | 略快(不复制数据) |
| 索引更新开销 | 较低(无版本) | 较高(二级索引含 trx_id) |
| 膨胀控制 | VACUUM 主动控制 | purge 自动 |
| 长事务影响 | 严重(膨胀+快照大) | 中等(undo 累积) |
| 空间回收 | VACUUM FULL 重写 | OPTIMIZE TABLE |
| 监控指标 | `pg_stat_user_tables.n_dead_tup` | `INFORMATION_SCHEMA.INNODB_TRX` |
| 调优参数 | `autovacuum_vacuum_scale_factor` 等 | `innodb_purge_threads` 等 |

### 15.4 故障场景对比

| 故障 | PG 表现 | MySQL 表现 |
|------|--------|-----------|
| 长事务未提交 | 死元组堆积,VACUUM 卡住 | undo 表空间暴涨 |
| 大量 UPDATE | 表膨胀(几十倍) | undo 段膨胀 |
| 主键冲突 | 立即报错 | 可能 Gap Lock 阻塞 |
| 索引热点页 | 普通等待 | 可能 next-key 死锁 |
| XID 回卷 | 紧急 VACUUM 防雪崩 | 无此问题 |

### 15.5 选型建议

```text
  选 PostgreSQL 的场景:
    - 复杂查询、JSON、GIS、全文检索
    - 业务规则复杂(需要 SERIALIZABLE 保护)
    - 标准 SQL 兼容要求高
    - 数据量中等(百亿级以下)
    - 可以做定期 VACUUM

  选 MySQL 的场景:
    - 纯 OLTP,简单业务
    - 极高 QPS(读写)
    - 数据量极大(配合分库分表)
    - 生态成熟,运维工具丰富
    - 不需要复杂事务保护
```

---

## 十六、核心要点速记

```text
  ┌──────────────────────────────────────────────────────────┐
  │           PostgreSQL 事务与 MVCC 核心要点                │
  ├──────────────────────────────────────────────────────────┤
  │                                                          │
  │  1. 事务语法                                              │
  │     - BEGIN / START TRANSACTION 开启                    │
  │     - COMMIT / END 提交                                 │
  │     - ROLLBACK / ABORT 回滚                             │
  │     - SAVEPOINT 子事务回滚点                            │
  │                                                          │
  │  2. 四种隔离级别                                          │
  │     - READ UNCOMMITTED: PG 中等同 RC                    │
  │     - READ COMMITTED: 默认,语句级快照                  │
  │     - REPEATABLE READ: 事务级快照,SI                  │
  │     - SERIALIZABLE: SSI,防写偏序                       │
  │                                                          │
  │  3. 并发问题                                              │
  │     - 脏读: PG 永不发生                                 │
  │     - 不可重复读: RC 可,RR 不可                       │
  │     - 幻读: RC 可,RR/Serial 不可                       │
  │     - 序列化异常: 仅 Serial 不可                        │
  │                                                          │
  │  4. MVCC 核心                                             │
  │     - 旧版本留在 heap,无 undo log                      │
  │     - 行头 xmin(插入事务) / xmax(删除/更新事务)         │
  │     - t_infomask 含 XMIN_COMMITTED 等标志位             │
  │     - CLOG 缓存事务状态                                  │
  │     - VACUUM 回收死元组                                  │
  │                                                          │
  │  5. UPDATE 行为(PG 特色)                                  │
  │     - 不删除旧行,只设 xmax                              │
  │     - 插入新行(xmin=当前事务, xmax=0)                  │
  │     - 索引项要么更新(普通),要么不变(HOT)               │
  │     - HOT 要求:索引列未变 + 同页 + fillfactor<100       │
  │                                                          │
  │  6. 快照                                                  │
  │     - xmin:活跃事务最小 ID                              │
  │     - xmax:快照时已分配的最大 ID+1                     │
  │     - xip[]:活跃事务 ID 列表                            │
  │     - 可见性算法:判断 xmin/xmax 与快照的关系            │
  │                                                          │
  │  7. RC vs RR vs Serial                                   │
  │     - RC:每条 SQL 新快照,UPDATE 读最新已提交            │
  │     - RR:事务级快照,SELECT 严格基于快照                 │
  │     - Serial:RR+SSI 谓词锁检测,失败 abort+重试         │
  │                                                          │
  │  8. 显式锁                                                │
  │     - FOR UPDATE / FOR NO KEY UPDATE                    │
  │     - FOR SHARE / FOR KEY SHARE                         │
  │     - NOWAIT / SKIP LOCKED                              │
  │     - 行锁存在行头 xmax(非独立锁表)                     │
  │                                                          │
  │  9. Advisory Lock                                         │
  │     - 64-bit key,应用级锁                               │
  │     - 会话级 / 事务级                                    │
  │     - 用作分布式锁、任务队列、跨表互斥                  │
  │                                                          │
  │  10. 最佳实践                                             │
  │      - 避免长事务(< 1s OLTP,< 10min 批量)              │
  │      - 启用 autovacuum,定期 VACUUM                     │
  │      - 业务层捕获 40001 并重试                          │
  │      - 监控 n_dead_tup,xact_start                      │
  │      - 合理用 SAVEPOINT 做部分回滚                      │
  │                                                          │
  │  11. PG vs MySQL MVCC 关键差异                           │
  │      - PG:旧版在 heap / MySQL:旧版在 undo              │
  │      - PG:索引无版本 / MySQL:索引有版本               │
  │      - PG:SSI 防写偏序 / MySQL:无                       │
  │      - PG:默认 RC / MySQL:默认 RR                      │
  │      - PG:VACUUM 控膨胀 / MySQL:purge 控膨胀           │
  │                                                          │
  └──────────────────────────────────────────────────────────┘
```

### 速记表

| 关注点 | PG 行为 | 关键 SQL/参数 |
|--------|---------|--------------|
| 启动事务 | `BEGIN` / `START TRANSACTION` | - |
| 提交 | `COMMIT` / `END` | - |
| 回滚 | `ROLLBACK` / `ROLLBACK TO sp` | - |
| 设置隔离级 | `SET TRANSACTION ISOLATION LEVEL ...` | - |
| 当前隔离级 | `SHOW transaction_isolation` | - |
| 拿快照 | 自动(语句/事务级) | `pg_current_snapshot()` |
| 行锁 | `SELECT ... FOR UPDATE` | - |
| 表锁 | `LOCK TABLE ... IN ... MODE` | - |
| 尝试锁 | `pg_try_advisory_lock(key)` | - |
| 事务级锁 | `pg_advisory_xact_lock(key)` | - |
| 序列化失败 | 错误码 40001 | 应用层捕获重试 |
| 死锁 | 错误码 40P01 | 应用层捕获重试 |
| 监控 | `pg_stat_activity` | `xact_start` |
| 表膨胀 | `n_dead_tup` | 触发 VACUUM |
| 长事务阈值 | 经验 < 5min 告警 | - |
| 清理 | `VACUUM` / `VACUUM FULL` | `autovacuum` |
| 同步提交 | `synchronous_commit` | ON 默认 |

### 关键命令速查

```sql
-- 事务控制
BEGIN [ISOLATION LEVEL ...] [READ WRITE|READ ONLY];
COMMIT [WORK] | END | ROLLBACK [WORK] | ABORT;
SAVEPOINT name; RELEASE SAVEPOINT name; ROLLBACK TO SAVEPOINT name;

-- 隔离级别
SET TRANSACTION ISOLATION LEVEL {SERIALIZABLE | REPEATABLE READ | READ COMMITTED | READ UNCOMMITTED};
SET TRANSACTION {READ WRITE | READ ONLY};
SET TRANSACTION DEFERRABLE;  -- 仅 SERIALIZABLE READ ONLY 有效

-- 锁
SELECT ... FOR UPDATE [NOWAIT | SKIP LOCKED];
SELECT ... FOR NO KEY UPDATE [NOWAIT | SKIP LOCKED];
SELECT ... FOR SHARE [NOWAIT | SKIP LOCKED];
SELECT ... FOR KEY SHARE [NOWAIT | SKIP LOCKED];
LOCK TABLE ... IN ... MODE [NOWAIT];

-- Advisory
SELECT pg_advisory_lock(key);          -- bigint
SELECT pg_advisory_lock(k1, k2);       -- 两个 int
SELECT pg_try_advisory_lock(key);
SELECT pg_advisory_xact_lock(key);
SELECT pg_advisory_unlock(key);
SELECT pg_advisory_unlock_all();

-- 监控
SELECT * FROM pg_stat_activity WHERE xact_start IS NOT NULL;
SELECT * FROM pg_locks;
SELECT * FROM pg_stat_user_tables;  -- n_dead_tup
SELECT datname, age(datfrozenxid) FROM pg_database;
SELECT pg_current_snapshot();
```

### 一句话总结

> **PostgreSQL 的事务与 MVCC 是一套"以行头 xmin/xmax 为核心、以快照为判断基准、以 VACUUM 为回收机制"的完整设计**,通过把版本直接放在 heap 中实现"读写无锁",通过 SSI 实现真正可串行化,代价是需要密切关注表膨胀与长事务。
