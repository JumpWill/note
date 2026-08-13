# MySQL MVCC(多版本并发控制)

## 一、MVCC 概念

### 1. 什么是 MVCC

**MVCC (Multi-Version Concurrency Control,多版本并发控制)** 是一种**数据库并发控制**的经典思想。它的核心思路是:

> 对数据的**读**操作不会阻塞**写**操作,对数据的**写**操作也不会阻塞**读**操作,通过**保存数据的多个历史版本**来实现"读写不冲突、读写并行"。

可以把 MVCC 想象成一条数据的"时间机器":每次有事务修改它,系统不直接覆盖旧数据,而是**生成一份新的版本**,让旧版本继续保留在系统中,直到确认没人再需要它。读事务根据自己"出生的时间点",去匹配对自己**可见**的那个版本。

### 2. MVCC 的两个关键产物

| 产物 | 作用 |
|------|------|
| **undo log 版本链** | 记录一条记录的所有历史版本,通过回滚指针 `DB_ROLL_PTR` 连成链表 |
| **Read View (读视图)** | 事务在**读**的瞬间拍下的"快照",记录当前活跃事务、版本边界等元数据 |

把这两者结合,就能在不阻塞写入的前提下,让每个事务读到**它该看到的数据版本**。

### 3. MVCC 不是"读取旧数据"那么简单

- 它不是简单的"用时间戳过滤"
- 也不是"每个读都全表拷贝"
- 而是**只对一行数据保留多个版本**,通过**可见性算法**判断读哪个版本
- 写操作仍然产生新版本,但通过 undo log 留下旧版本,实现"读写并行"

---

## 二、为什么需要 MVCC

### 1. 没有 MVCC 时的困境

在没有 MVCC 的最朴素并发模型里,数据库只有两种做法:

```text
方案 A:读写互斥(读写都用锁)
  ┌──────────┐    ┌──────────┐
  │ 事务 T1  │    │ 事务 T2  │
  │  SELECT  │    │  UPDATE  │
  │  ──── 等待 T2 提交 ────  │
  └──────────┘    └──────────┘
  读阻塞写,写也阻塞读,性能极差。

方案 B:读写都不加锁
  - 写一半的数据被读走 → 脏读
  - 同一行两次读结果不同 → 不可重复读
  - 多读出来几行 → 幻读
  - 数据一致性全无。
```

MVCC 的目标就是**同时解决这两个问题**:

- **读写不互斥**:读不阻塞写,写不阻塞读
- **读到的数据是符合隔离级别要求的版本**:不会读到未提交的、不会读到不该看到的

### 2. MVCC 解决了哪些问题

| 现象 | 含义 | MVCC 是否解决 |
|------|------|---------------|
| **脏读 (Dirty Read)** | 读到其他事务**未提交**的数据 | 解决(REPEATABLE READ 以上) |
| **不可重复读 (Non-Repeatable Read)** | 同一行两次读结果不同 | 解决(REPEATABLE READ) |
| **幻读 (Phantom)** | 同一范围两次读行数不同 | 部分解决(快照读层面),当前读层面靠 Next-Key Lock |

### 3. MVCC 的代价

| 代价 | 说明 |
|------|------|
| **额外存储** | 每个被修改的行都要保留旧版本(undo log) |
| **清理成本** | 需要后台线程清理不再需要的旧版本(purge) |
| **事务可见性判断** | 每次读都需要计算 Read View、判断版本链 |
| **大事务影响** | 长事务会一直保留大量历史版本,导致空间膨胀 |

> **MVCC 的本质权衡**:**用空间换并发**,用额外的存储和清理成本,换读写并行的能力。

---

## 三、MVCC 在各数据库的实现

不同数据库对 MVCC 都有自己的实现方式,差别主要在**版本存储方式**、**快照生成时机**、**可见性算法**上。

### 1. 各数据库对比

| 数据库 | 版本存储 | 快照生成 | 回滚机制 | 特点 |
|--------|----------|----------|----------|------|
| **MySQL InnoDB** | undo log 链 | 第一次读时建 Read View | undo log | 隐藏字段 + Read View |
| **PostgreSQL** | 每行存 xmin/xmax 事务号 | 事务开始时拍快照 | 旧版本堆表 | 实现干净,无需 undo 链 |
| **Oracle** | 回滚段 (Rollback Segment) | 读一致性快照 | 回滚段 | 读一致性靠 SCN |
| **SQL Server** | tempdb 中的版本存储 | 快照隔离时启用 | 旧版本写 tempdb | 默认是锁,RCSI 才有 MVCC |
| **MongoDB** | WiredTiger MVCC | 操作时打快照 | 旧版本留 B 树 | 文档级别 |

### 2. PostgreSQL 的 MVCC(对比参照)

- 每行都有 `xmin`(插入此行的事务)和 `xmax`(删除此行的事务)系统列
- 事务开始时拍快照(`pg_snapshot`),记录活跃事务边界
- 旧版本不删除,堆积在堆表中,由 `VACUUM` 清理
- 优点:实现干净利落,没有 undo log 那种隐式链
- 缺点:`VACUUM` 不及时会膨胀 (`table bloat`)

### 3. Oracle 的 MVCC(对比参照)

- 使用**回滚段 (Rollback Segment)**,类似 MySQL 的 undo log
- 通过 **SCN (System Change Number)** 标识版本
- 读一致性:查询时生成 SCN,旧版本从回滚段取出
- 事务回滚也靠回滚段

### 4. InnoDB 的 MVCC(本章重点)

- 每个行有三个隐藏字段:`DB_TRX_ID`、`DB_ROLL_PTR`、`DB_ROW_ID`
- 修改数据时,旧版本写入 undo log,通过 `DB_ROLL_PTR` 串成链表
- 读时根据 **Read View + 可见性算法** 在版本链中找到目标版本
- `purge` 线程清理不再需要的旧版本

> **关键差异**:
> - InnoDB 的 MVCC 是**针对 RC 和 RR 两个隔离级别**的
> - RU (读未提交) 总是读最新,**不走 MVCC**
> - SR (可串行化) 把所有读变成当前读,**不走 MVCC**

---

## 四、InnoDB 的 MVCC 实现机制

### 1. 总览

InnoDB 的 MVCC 由以下几部分组成:

```text
┌──────────────────────────────────────────────────────┐
│                  InnoDB MVCC 机制                    │
├──────────────────────────────────────────────────────┤
│  1. 三个隐藏字段(每行记录自带)                       │
│     - DB_TRX_ID   最近修改此行的事务 ID              │
│     - DB_ROLL_PTR 回滚指针,指向 undo log 旧版本     │
│     - DB_ROW_ID   隐藏主键(无主键时 InnoDB 生成)    │
│                                                      │
│  2. undo log(回滚日志)                              │
│     - INSERT undo log:事务回滚时用,提交后可删除      │
│     - UPDATE undo log:MVCC 关键,提交后不能立即删除   │
│                                                      │
│  3. Read View(读视图)                               │
│     - m_ids          当前活跃事务 ID 集合            │
│     - min_trx_id     活跃事务中最小 ID              │
│     - max_trx_id     创建 Read View 时下一个 ID     │
│     - creator_trx_id 创建此 Read View 的事务 ID      │
│                                                      │
│  4. 可见性算法                                       │
│     根据 Read View 在版本链上找到可见版本             │
│                                                      │
│  5. purge 线程                                       │
│     清理不再需要的旧版本                              │
└──────────────────────────────────────────────────────┘
```

### 2. 一条 SQL 经历的 MVCC 过程

```text
事务 T1 开启,执行 SELECT * FROM user WHERE id = 1;
                              │
                              ▼
              ┌─────────────────────────────┐
              │ 1. 创建/获取 Read View     │
              │    (RC: 每次新建)          │
              │    (RR: 事务内只一个)      │
              └─────────────────────────────┘
                              │
                              ▼
              ┌─────────────────────────────┐
              │ 2. 从 B+Tree 找到 id=1 行  │
              │    拿到这行的 DB_TRX_ID    │
              │    和 DB_ROLL_PTR         │
              └─────────────────────────────┘
                              │
                              ▼
              ┌─────────────────────────────┐
              │ 3. 用可见性算法判断当前版本 │
              │    是否对当前事务可见       │
              │    - 可见 → 返回           │
              │    - 不可见 → 沿 ROLL_PTR  │
              │              找旧版本      │
              └─────────────────────────────┘
                              │
                              ▼
              ┌─────────────────────────────┐
              │ 4. 直到找到可见版本或链尾   │
              │    返回该版本数据           │
              └─────────────────────────────┘
```

### 3. 三个隔离级别的关系

| 隔离级别 | 是否使用 MVCC | 读方式 |
|----------|---------------|--------|
| **READ UNCOMMITTED** | 否 | 总是当前读(读最新版本,可能脏读) |
| **READ COMMITTED** | 是 | 每次 SELECT 都新建 Read View |
| **REPEATABLE READ** | 是 | 事务内只用一个 Read View(首次 SELECT 创建) |
| **SERIALIZABLE** | 否 | 退化为当前读 + 锁 |

---

## 五、三个关键隐藏字段

InnoDB 会给每行记录(不论聚簇索引还是二级索引,这里主要看聚簇索引)添加三个隐藏字段。可以用 `SHOW TABLE STATUS` 或 `INFORMATION_SCHEMA.INNODB_SYS_COLUMNS` 看到它们。

### 1. 整体结构

```text
┌───────────────────────────────────────────────────────────────────┐
│                     一条 InnoDB 记录的内部结构                    │
├──────────┬──────────┬──────────┬──────────┬──────────┬───────────┤
│ DB_ROW_ID│DB_TRX_ID │DB_ROLL_PTR│   列 1   │   列 2   │   ...    │
│  (6字节) │  (6字节) │  (7字节) │          │          │          │
│  隐藏主键 │事务ID   │回滚指针  │ 用户字段 │ 用户字段 │ 用户字段 │
└──────────┴──────────┴──────────┴──────────┴──────────┴───────────┘
```

### 2. DB_TRX_ID(事务 ID)

- **大小**:6 字节
- **含义**:最近一次**插入或更新**此行的事务 ID
- **何时更新**:
  - INSERT 时填入当前事务 ID
  - UPDATE 时填入新事务 ID(并产生旧版本到 undo log)
  - DELETE 时不立即删除,而是在行上打 delete flag,同样更新 DB_TRX_ID
- **作用**:可见性算法核心,用它判断"这行是谁改的、改的时候这个事务对我可见吗"

```text
DB_TRX_ID 来源:

  全局自增 → 由 InnoDB 在内存中维护 max_trx_id
  BEGIN / COMMIT 时分配(实际是事务第一次读写时分配)
  注意:不是 BEGIN 就分配,而是第一次"做事"时才分配
```

### 3. DB_ROLL_PTR(回滚指针)

- **大小**:7 字节
- **含义**:指向这条记录**的上一版本**在 undo log 中的位置
- **何时更新**:
  - INSERT 时为 NULL(没有旧版本)
  - UPDATE / DELETE 时指向刚写入 undo log 的旧版本
- **作用**:把一行记录的**所有历史版本**串成链表

```text
DB_ROLL_PTR 形成的版本链:

  当前行 ──DB_ROLL_PTR──→ undo 节点(v_n-1)
                            │
                            └──DB_ROLL_PTR──→ undo 节点(v_n-2)
                                              │
                                              └── ... ──→ 最早版本
```

### 4. DB_ROW_ID(隐藏主键)

- **大小**:6 字节
- **含义**:行 ID,InnoDB 自动生成的主键
- **何时存在**:当表**没有定义主键**且**没有唯一非空索引**时,InnoDB 会用 DB_ROW_ID 作为聚簇索引的 key
- **作用**:在没有显式主键时,给聚簇索引一个唯一标识

```text
什么情况下会出现 DB_ROW_ID 作为聚簇 key?
  1. 没有 PRIMARY KEY
  2. 没有 NOT NULL 的 UNIQUE KEY
  两个条件都满足 → InnoDB 自动生成 6 字节的 _rowid
  满足任一 → 用该列作为聚簇 key,不生成 DB_ROW_ID
```

> **建议**:永远显式定义主键,既能避免 DB_ROW_ID 副作用,也让聚簇索引更明确。

### 5. 三字段总结

| 字段 | 大小 | 作用 | 何时为关键 |
|------|------|------|------------|
| **DB_TRX_ID** | 6 B | 最近修改事务 ID | 可见性判断 |
| **DB_ROLL_PTR** | 7 B | 指向 undo log 旧版本 | 版本链遍历 |
| **DB_ROW_ID** | 6 B | 隐藏主键(无主键时) | 聚簇索引构造 |

---

## 六、undo log 版本链

### 1. 什么是 undo log

**undo log (回滚日志)** 记录的是**"数据修改前的状态"**,主要作用有两个:

1. **事务回滚**:事务 rollback 时,根据 undo log 把数据改回去
2. **MVCC**:快照读时,通过 undo log 拿到旧版本数据

undo log 分为两类:

| 类型 | 内容 | 何时可清理 |
|------|------|------------|
| **insert undo log** | 插入行产生的回滚信息(主键 + 行内容) | 事务提交后立即可清理 |
| **update undo log** | 更新/删除产生的回滚信息(主键 + 修改前各列值) | 不能立即清理,需 purge 线程处理 |

> **关键点**:
> - **insert undo log** 提交即可删(没有旧版本可读,事务提交了别人也读不到它的 insert)
> - **update undo log** 不能立即删(可能还有别的事务在快照读里需要这个旧版本)

### 2. 版本链的形成

每次 UPDATE 一行,InnoDB 都会做以下事情:

```text
步骤 1: 加排他锁(行锁)
步骤 2: 把原行数据拷贝到 undo log(产生新节点)
步骤 3: 修改目标行的数据
步骤 4: 更新目标行的 DB_TRX_ID = 当前事务 ID
步骤 5: 更新目标行的 DB_ROLL_PTR = 指向刚写入的 undo log 节点
步骤 6: 释放锁
```

这样就形成了一条"从新到旧"的链表。

### 3. 版本链的 ASCII 图

假设有一行 `name='张三'` 的记录,经过多次事务修改:

```text
                     当前行(在 B+Tree 叶子节点里)
                     ┌─────────────────────────────────────┐
                     │ DB_TRX_ID = 30                      │
                     │ DB_ROLL_PTR  ────────────┐         │
                     │ name = '王五'             │         │
                     │ age  = 25                 │         │
                     └───────────────────────────┼─────────┘
                                                 │
                                                 ▼
                     undo log 节点 1 (新版本之前)
                     ┌─────────────────────────────────────┐
                     │ DB_TRX_ID = 20                      │
                     │ DB_ROLL_PTR  ────────────┐         │
                     │ name = '李四'             │         │
                     │ age  = 22                 │         │
                     └───────────────────────────┼─────────┘
                                                 │
                                                 ▼
                     undo log 节点 2 (再之前)
                     ┌─────────────────────────────────────┐
                     │ DB_TRX_ID = 10                      │
                     │ DB_ROLL_PTR  ────────────┐         │
                     │ name = '张三'             │         │
                     │ age  = 20                 │         │
                     └───────────────────────────┼─────────┘
                                                 │
                                                 ▼ NULL(链尾,最早版本)
```

**关键观察**:

- 每个 undo log 节点自己也有 `DB_TRX_ID` 和 `DB_ROLL_PTR`
- 当前行上的 `DB_ROLL_PTR` 指向"再之前"的 undo 节点
- undo 节点上的 `DB_ROLL_PTR` 再指向"再之前"的 undo 节点
- 形成**单向链表**,从新到旧

### 4. 一次 UPDATE 的具体例子

```sql
-- 假设初始: trx_id=10, name='张三', age=20
-- 事务 20: UPDATE user SET age = 22 WHERE id = 1;
-- 事务 30: UPDATE user SET name='王五', age=25 WHERE id = 1;

事务 20 执行 UPDATE:
  ① 拷贝 '张三,20' 到 undo log 节点,DB_TRX_ID=10, DB_ROLL_PTR=NULL
  ② 修改当前行: age=22, DB_TRX_ID=20, DB_ROLL_PTR → 节点1

事务 30 执行 UPDATE:
  ① 拷贝 '李四,22' 到 undo log 节点,DB_TRX_ID=20, DB_ROLL_PTR → 节点1
  ② 修改当前行: name='王五', age=25, DB_TRX_ID=30, DB_ROLL_PTR → 节点2
```

最终形成的版本链(就如上面 ASCII 图所示)。

### 5. DELETE 在版本链上的体现

InnoDB 的 DELETE 不是立刻删除行,而是:

```text
1. 在原行上打 delete flag(标记位)
2. DB_TRX_ID 更新为当前事务 ID
3. DB_ROLL_PTR 指向旧版本
4. 行还在 B+Tree 里
5. purge 线程在确认没人需要这个版本时才真正删除
```

这样,删除前的版本仍然可以从 undo log 中读到,被并发事务通过快照读到。

---

## 七、Read View(读视图)

### 1. 概念

**Read View** 是事务在**执行快照读**时拍下的一个**一致性视图**,本质是一个数据结构,记录了"在我读的时候,哪些事务是活跃的、版本边界在哪里"。

有了它,就能判断某行数据的**某个版本对我是否可见**。

### 2. 四个核心字段

```c
class ReadView {
    // 1. 创建 Read View 时,所有未提交的事务 ID 列表
    ids_t        m_ids;          // 例如 [20, 30, 40]

    // 2. m_ids 中的最小值
    trx_id_t     m_low_limit_id; // 例如 20

    // 3. 创建 Read View 时,**下一个**将被分配的事务 ID
    trx_id_t     m_up_limit_id;  // 例如 50

    // 4. 创建此 Read View 的事务 ID
    trx_id_t     m_creator_trx_id; // 例如 25
};
```

### 3. 字段详解

#### (1) m_ids

- **含义**:创建 Read View 时,系统中**尚未提交**的事务 ID 列表
- **生成时机**:取当前 `trx_sys->trx_list` 中所有活跃事务的 ID
- **作用**:这些事务"正在改数据",它们的修改结果对当前 Read View **不可见**

```text
例如当前系统状态:
  T10  已提交
  T20  活跃(运行中)
  T30  活跃(运行中)
  T40  活跃(运行中)
  T50  还未启动

则 m_ids = [20, 30, 40]
```

#### (2) min_trx_id (m_low_limit_id)

- **含义**:`m_ids` 中的**最小**值
- **作用**:小于它的 ID 一定是**已提交**的(不在活跃列表中)

```text
上例: min_trx_id = 20
含义: < 20 的事务都已提交
```

#### (3) max_trx_id (m_up_limit_id)

- **含义**:创建 Read View 时,系统**下一个**要分配的事务 ID(不是当前最大值+1,而是当前最大值+1,即"下一个")
- **作用**:大于等于它的 ID 一定是**未来事务**,对当前 Read View **不可见**

```text
上例: 已分配到 T40,下一个是 T50
max_trx_id = 50
含义: ≥ 50 的事务都还没启动,对我不可见
```

#### (4) creator_trx_id

- **含义**:创建此 Read View 的事务自己的 ID
- **作用**:在可见性算法里,自己改的数据自己当然**可见**

```text
例: 事务 25 发起 SELECT,creator_trx_id = 25
```

### 4. 字段之间的关系

```text
假设系统事务分配情况:

         已分配 ID
  ─────────────────────────────→ 时间
  10  20  30  40  50
  ↑   ↑   ↑   ↑   ↑
 提交 活跃 活跃 活跃 下个
       (m_ids = [20, 30, 40])
       ↑                ↑
  min_trx_id = 20   max_trx_id = 50
```

```text
事务 ID 分布(对当前 Read View 而言):

  < min_trx_id     : 一定已提交      ← 可见
  ∈ m_ids          : 活跃中          ← 不可见
  ∈ (min_trx_id, max_trx_id) 但不在 m_ids : 已提交  ← 可见
  ≥ max_trx_id     : 还没启动        ← 不可见
  = creator_trx_id : 自己           ← 可见
```

### 5. Read View 创建时机

| 隔离级别 | 创建时机 |
|----------|----------|
| **READ COMMITTED** | **每次**执行 SELECT(快照读)时**新建**一个 Read View |
| **REPEATABLE READ** | 事务内**第一次**执行 SELECT(快照读)时创建,后续复用 |

```text
RC:
  SELECT 1 → Read View A
  UPDATE   → (不影响 Read View)
  SELECT 2 → Read View B(全新!可能看到不同的数据)

RR:
  SELECT 1 → Read View A
  UPDATE   → (不影响 Read View)
  SELECT 2 → Read View A(复用)
```

---

## 八、数据可见性算法

### 1. 算法核心思想

拿到一行记录后,从**当前版本**开始,沿 `DB_ROLL_PTR` 沿着版本链找第一个**对当前 Read View 可见**的版本。

判断一行记录的某个版本(`DB_TRX_ID = X`)是否可见,按以下顺序检查:

```text
判断 X(记录的某版本的事务 ID)是否对当前 Read View 可见:

┌──────────────────────────────────────────────────────────────┐
│ 步骤 1: X == creator_trx_id                                   │
│        YES → 可见(自己改的自己可见)                            │
│        NO  → 步骤 2                                           │
├──────────────────────────────────────────────────────────────┤
│ 步骤 2: X < min_trx_id                                        │
│        YES → 可见(它早已提交)                                  │
│        NO  → 步骤 3                                           │
├──────────────────────────────────────────────────────────────┤
│ 步骤 3: X >= max_trx_id                                       │
│        YES → 不可见(它在我读之后才启动)                        │
│        NO  → 步骤 4                                           │
├──────────────────────────────────────────────────────────────┤
│ 步骤 4: X ∈ m_ids(活跃事务列表)                               │
│        YES → 不可见(它还在跑,没提交)                           │
│        NO  → 步骤 5                                           │
├──────────────────────────────────────────────────────────────┤
│ 步骤 5: 不属于以上任何情况                                     │
│        → 可见(它在 (min_trx_id, max_trx_id) 之间,             │
│          但不在 m_ids 中 → 已提交)                             │
└──────────────────────────────────────────────────────────────┘
```

### 2. 简化版判断逻辑(常见表述)

业内常见的简化判断是 4 条规则:

```
1. trx_id == creator_trx_id          → 可见
2. trx_id < min_trx_id                → 可见(已提交)
3. trx_id >= max_trx_id               → 不可见(未来事务)
4. trx_id ∈ m_ids                     → 不可见(活跃中)
5. 其他情况(min_trx_id ≤ trx_id < max_trx_id, 但 ∉ m_ids) → 可见
```

### 3. 完整可见性流程图

```text
                拿到一行记录的某个版本 (trx_id = X)
                                │
                                ▼
            ┌───────────────────────────────────────┐
            │ X == creator_trx_id ?                 │
            └───────────┬───────────────────────────┘
                  ┌─────┴─────┐
                YES            NO
                  │             │
              可见 ✓    ┌────────┴──────────────────────┐
                        │ X < min_trx_id ?              │
                        └─────────┬─────────────────────┘
                            ┌─────┴─────┐
                          YES           NO
                            │            │
                        可见 ✓   ┌──────┴─────────────────────┐
                                  │ X >= max_trx_id ?           │
                                  └──────┬─────────────────────┘
                                       ┌─┴──┐
                                     YES    NO
                                       │     │
                                  不可见 ✗   ┌──────┴──────────────┐
                                            │ X ∈ m_ids ?         │
                                            └──────┬──────────────┘
                                                 ┌─┴──┐
                                               YES    NO
                                                 │     │
                                            不可见 ✗   │
                                                       ▼
                                                  可见 ✓
                                                  (已提交但在 m_ids 之外)

        ┌──────────────────────────────────────────────────────┐
        │ 注:如果当前版本不可见,沿 DB_ROLL_PTR 找旧版本,        │
        │   重复以上判断,直到找到可见版本或链尾(链尾也找不到     │
        │   → 该行对当前事务不可见)。                            │
        └──────────────────────────────────────────────────────┘
```

### 4. 版本链遍历完整流程

```text
执行 SELECT * FROM user WHERE id = 1;
                     │
                     ▼
        ┌────────────────────────┐
        │ 找到 id=1 的当前行     │
        │ 拿到 DB_TRX_ID, DB_ROLL_PTR
        └───────────┬────────────┘
                    ▼
        ┌────────────────────────┐
        │ 用 Read View 判断       │
        │ 当前行是否可见?         │
        └─────┬──────────┬───────┘
              │可见      │不可见
              ▼          ▼
         返回该版本     ┌──────────────────────────┐
                       │ DB_ROLL_PTR 是否为 NULL? │
                       └─────┬────────────┬───────┘
                             │非 NULL      │NULL
                             ▼             ▼
                  ┌─────────────────┐   ┌──────────────┐
                  │ 跳到旧版本       │   │ 没有可见版本  │
                  │ 回到上面的判断   │   │ 该行不可见    │
                  └─────────────────┘   └──────────────┘
```

### 5. 例子演示可见性

```text
系统状态:
  - T10 已提交
  - T20 活跃
  - T30 活跃
  - T40 下一个要分配
  - 事务 25 发起 SELECT (creator=25)
    → Read View: m_ids=[20,30], min=20, max=40

版本链:
  v3: trx_id=30, name='王五'     (最新)
  v2: trx_id=20, name='李四'
  v1: trx_id=10, name='张三'     (最早)

判断:
  v3 (trx_id=30):
    - != 25 ✓
    - < 20 ? ✗ (30 不 < 20)
    - >= 40 ? ✗ (30 不 >= 40)
    - ∈ m_ids [20,30]? ✓ → 不可见
    → 沿 ROLL_PTR 找 v2

  v2 (trx_id=20):
    - != 25 ✓
    - < 20 ? ✗ (20 不 < 20)
    - >= 40 ? ✗
    - ∈ m_ids [20,30]? ✓ → 不可见
    → 沿 ROLL_PTR 找 v1

  v1 (trx_id=10):
    - != 25 ✓
    - < 20 ? ✓ (10 < 20) → 可见 ✓
    → 返回 v1, 看到 name='张三'
```

事务 25 最终读到的是 **name='张三'**,而不是当前最新的 '王五',也避开了未提交的修改。

---

## 九、不同隔离级别下的快照读

### 1. READ COMMITTED(RC)

**特点:每次 SELECT 都新建 Read View**。

```text
事务 T1 (RR):
  BEGIN;
  SELECT * FROM user WHERE id = 1;  →  Read View A(可能看到 T2 未提交之前)
  -- 此时 T2 提交了更新
  SELECT * FROM user WHERE id = 1;  →  Read View B(可能看到 T2 已提交的新值)
COMMIT;
```

**RC 下的可见性表现**:

- 同一事务内,两次 SELECT 可能读到不同数据(因为 Read View 变了)
- 看不到"未提交"的数据(解决了脏读)
- 看得到"已提交"的最新数据(没解决不可重复读、幻读)

### 2. REPEATABLE READ(RR,InnoDB 默认)

**特点:事务内只用一个 Read View(首次 SELECT 创建)**。

```text
事务 T1 (RR):
  BEGIN;
  SELECT * FROM user WHERE id = 1;  →  Read View A(建立,事务内复用)
  -- 此时 T2 提交了更新
  SELECT * FROM user WHERE id = 1;  →  复用 Read View A(看不到 T2 的更新)
  SELECT * FROM user WHERE id = 1;  →  复用 Read View A(仍然看不到)
COMMIT;
```

**RR 下的可见性表现**:

- 同一事务内,多次 SELECT 看到的是**同一时刻的快照**
- 看不到"未提交"的数据(解决脏读)
- 看不到事务期间其他事务的"已提交"修改(解决不可重复读)
- 范围读时,部分解决幻读(MVCC 层面)+ Next-Key Lock(当前读层面)

### 3. 对比

| 维度 | READ COMMITTED | REPEATABLE READ |
|------|----------------|-----------------|
| **Read View 创建时机** | 每次 SELECT | 首次 SELECT |
| **同事务多次 SELECT** | 可能不同 | 完全一致 |
| **可重复读** | 否 | 是 |
| **不可重复读** | 可能发生 | 不发生 |
| **幻读(快照读)** | 可能 | 不发生(快照读层面) |
| **幻读(当前读)** | 可能 | 部分可能(配合 Next-Key Lock) |
| **InnoDB 默认** | 否 | **是** |

### 4. 时间线演示

```text
时间 → T1 ────────────────────────►
       BEGIN
       SELECT → RV_A(看到的是 T1 开始时已提交的数据)
                                          ↑
                       ──── T2 在此时提交 ────
                                          │
       SELECT → RV_A(不变,看不到 T2 修改)
       COMMIT

时间 → T1 ────────── RC 级别 ────────►
       BEGIN
       SELECT → RV_A
                                          ↑
                       ──── T2 在此时提交 ────
                                          │
       SELECT → RV_B(新建,能看到 T2 修改!)
       COMMIT
```

---

## 十、当前读 vs 快照读

### 1. 两种读的定义

| 类型 | 含义 | 实现 |
|------|------|------|
| **快照读 (Snapshot Read)** | 读取**历史版本**,不加锁 | 普通 SELECT,MVCC 实现 |
| **当前读 (Current Read / Locking Read)** | 读取**最新版本**,并加锁 | 特殊 SELECT、UPDATE、DELETE、INSERT |

### 2. 当前读语句列表

```sql
-- 1. 加共享锁的读(读最新版本)
SELECT * FROM user WHERE id = 1 LOCK IN SHARE MODE;
SELECT * FROM user WHERE id = 1 FOR SHARE;           -- MySQL 8.0+

-- 2. 加排他锁的读(读最新版本)
SELECT * FROM user WHERE id = 1 FOR UPDATE;

-- 3. 写操作本身就是当前读
UPDATE user SET name = 'xxx' WHERE id = 1;
DELETE FROM user WHERE id = 1;
INSERT INTO user VALUES (...);
```

### 3. 当前读 vs 快照读对比

| 维度 | 快照读 | 当前读 |
|------|--------|--------|
| **读哪个版本** | 可见性算法选版本(可能是历史) | 永远读最新版本 |
| **是否加锁** | 不加锁 | 加锁(行锁、间隙锁) |
| **能看到未提交数据** | 不能 | 能(但要拿到锁,未提交会阻塞) |
| **实现** | MVCC + undo log | 锁机制 |
| **典型 SQL** | `SELECT * FROM t WHERE ...` | `SELECT ... FOR UPDATE` |
| **影响** | 不阻塞其他读,可能阻塞写 | 阻塞其他读和写 |
| **RR 下幻读** | 不发生(MVCC) | 靠 Next-Key Lock 防幻读 |

### 4. 一个例子理解差异

```text
T1 (RR):
  BEGIN;
  SELECT * FROM user WHERE id = 1;  -- 快照读,name='张三'

T2:
  UPDATE user SET name='李四' WHERE id = 1;
  COMMIT;

T1:
  SELECT * FROM user WHERE id = 1;  -- 快照读,仍 name='张三'
  SELECT * FROM user WHERE id = 1 FOR UPDATE;  -- 当前读,name='李四'
```

> **记忆点**:快照读是**拍照**(快照),当前读是**看现场**(最新)。

---

## 十一、MVCC + Next-Key Lock 解决幻读

### 1. 什么是幻读

**幻读 (Phantom Read)**:同一个事务内,两次**相同范围**的查询返回的**行数不同**。

```sql
-- 事务 T1
BEGIN;
SELECT * FROM user WHERE age > 20;   -- 返回 3 行
-- 此时 T2 插入一行 age=25
SELECT * FROM user WHERE age > 20;   -- 返回 4 行(多出来的就是"幻影")
COMMIT;
```

### 2. MVCC 为什么不能完全解决幻读

MVCC 在**快照读**层面能解决幻读(快照不变),但在**当前读**层面会失效:

```sql
T1 (RR):
  BEGIN;
  SELECT COUNT(*) FROM user WHERE age > 20;  -- 快照读,得到 3
  -- 走当前读插入数据到范围里
  INSERT INTO user (age) VALUES (25);
  -- 这时如果再次 SELECT COUNT(*) ... 当前读,可能看到 4
```

### 3. Next-Key Lock 是什么

**Next-Key Lock = Record Lock + Gap Lock** 的组合,锁定的不仅是具体行,还有"行之间的间隙"。

```text
假设索引上有值: 10, 20, 30

Record Lock:   锁住具体的 10/20/30
Gap Lock:      锁住 (负无穷, 10), (10, 20), (20, 30), (30, 正无穷)
Next-Key Lock: Record Lock + 它前面的 Gap Lock
               例如锁 20 = 锁住 (10, 20] 区间
```

### 4. RR 下两种读如何协同防幻读

```text
快照读 (普通 SELECT):
  → 用 MVCC + 复用 Read View
  → 看到的是事务开始时的快照
  → 即使其他事务插入了新行,快照读也看不到
  → 不加锁,不阻塞

当前读 (SELECT FOR UPDATE / UPDATE / DELETE):
  → 用 Next-Key Lock
  → 锁住扫描到的范围 + 间隙
  → 其他事务的 INSERT 必须等待(因为间隙被锁)
  → 避免"读到幻影行"
```

### 5. 协同示意图

```text
T1: SELECT * FROM user WHERE age > 20 FOR UPDATE;
                    │
                    ▼
        ┌───────────────────────────────┐
        │ Next-Key Lock 锁住 (20, +∞)  │
        │ 任何 INSERT age>20 都要等      │
        └───────────────────────────────┘
                    │
                    ▼
T2: INSERT INTO user (age) VALUES (25);  -- 阻塞!
                                      │
                                      ▼
              等 T1 提交/回滚,释放锁
                                      │
                                      ▼
              T2 拿到锁,INSERT 成功
              但 T1 用快照读仍看不到
              T1 用当前读会看到(因为当前读拿最新)
```

### 6. 为什么需要两者结合

| 读类型 | MVCC 解决 | Next-Key Lock 解决 |
|--------|-----------|---------------------|
| 快照读 | 是 | (不需要) |
| 当前读 | (不能,会读到新行) | 是 |
| 综合效果 | 无锁的读不阻塞 | 加锁的写不幻读 |

> **一句话总结**:
> **MVCC 让快照读无锁且看到一致快照,Next-Key Lock 让当前读也能避免幻读**。两者协同,RR 才真正达到"读不幻"。

---

## 十二、完整示例演示 MVCC

下面通过两个 session 的完整操作,演示 MVCC 在 REPEATABLE READ 级别下的行为。

### 1. 准备

```sql
-- 创建表
CREATE TABLE account (
    id     INT PRIMARY KEY,
    name   VARCHAR(50),
    balance INT
) ENGINE=InnoDB;

INSERT INTO account VALUES (1, '张三', 100);

-- 设置隔离级别
SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ;
```

### 2. 完整 SQL 与时间线

```text
初始数据:
  id=1, name='张三', balance=100
```

| 时间 | Session A | Session B | 说明 |
|------|-----------|-----------|------|
| T1 | `BEGIN;` | | A 启动事务 |
| T2 | | `BEGIN;` | B 启动事务 |
| T3 | `SELECT * FROM account WHERE id = 1;`<br>→ 读到 `('张三', 100)` | | A 建 Read View(m_ids=[A,B], A=id?, B=id?) |
| T4 | | `UPDATE account SET balance = 200 WHERE id = 1;`<br>(B 改数据,产生 undo log) | B 改了数据,但未提交 |
| T5 | `SELECT * FROM account WHERE id = 1;`<br>→ 仍读到 `('张三', 100)` | | A 用 Read View 看不到 B 的修改 |
| T6 | | `COMMIT;` | B 提交 |
| T7 | `SELECT * FROM account WHERE id = 1;`<br>→ 仍读到 `('张三', 100)` | | A 复用 Read View,仍看不到 |
| T8 | `UPDATE account SET balance = balance + 50 WHERE id = 1;`<br>→ 修改成功(balance=250) | | A 修改时是当前读,读到 200 |
| T9 | `SELECT * FROM account WHERE id = 1;`<br>→ 读到 `balance=250` | | A 自己改的自己可见 |
| T10 | `COMMIT;` | | A 提交 |

### 3. 关键细节解读

#### T3:A 建 Read View

```text
假设事务 ID:
  A = 100
  B = 101

A 建 Read View 时:
  m_ids = [100, 101]   (两个事务都活跃)
  min_trx_id = 100
  max_trx_id = 102      (下一个要分配的)
  creator_trx_id = 100

当前行 version(DB_TRX_ID) = 1(系统初始 insert)
  1 < min_trx_id(100)? ✓ → 可见
  → A 看到 '张三', 100
```

#### T4:T5:B 修改但未提交,A 仍看不到

```text
B 修改后,行结构:
  当前行: DB_TRX_ID = 101, balance=200
  undo:   DB_TRX_ID = 1,  balance=100

A 用 Read View (m_ids=[100,101], min=100, max=102) 判断:
  当前行 DB_TRX_ID = 101
    - == creator(100)? ✗
    - < min(100)?  ✗
    - >= max(102)? ✗
    - ∈ m_ids? ✓ → 不可见

  → 沿 DB_ROLL_PTR 找旧版本(101 指向 trx_id=1)
  - == creator(100)? ✗
  - < min(100)? ✓ → 可见

A 仍读到 balance=100
```

#### T7:B 已提交,A 仍看不到

```text
B 提交后,系统 m_ids 变成 [100](B=101 已不在活跃列表)
但 A 的 Read View 是 T3 拍下的快照,m_ids 仍是 [100, 101]

A 看到的:
  仍然不可见(因为 A 的 Read View 没变)
```

#### T8:A 当前读,读到 B 提交后的最新值

```text
A 执行 UPDATE 时是当前读:
  - 直接读最新版本(101, balance=200)
  - 加排他锁
  - 在这个基础上 +50 → balance=250
  - 产生新的 undo log(指向 trx_id=101, balance=200)
  - DB_TRX_ID 变成 100
```

#### T9:A 看到自己改的 250

```text
  A 自己读自己改的:
    DB_TRX_ID = 100 = creator_trx_id → 可见 ✓
  → 看到 250
```

### 4. 版本链演化图

```text
T3 时(T3 之前,只有初始数据):
  当前行: DB_TRX_ID=1, balance=100

T4(B 修改未提交):
  当前行: DB_TRX_ID=101, balance=200
    └──ROLL_PTR──→ undo: DB_TRX_ID=1, balance=100

T6(B 提交):
  行数据不变,undo log 仍保留(因为 A 还在用 Read View)
  当前行: DB_TRX_ID=101, balance=200
    └──ROLL_PTR──→ undo: DB_TRX_ID=1, balance=100

T8(A 修改,基于当前读):
  当前行: DB_TRX_ID=100, balance=250
    └──ROLL_PTR──→ undo: DB_TRX_ID=101, balance=200
                  └──ROLL_PTR──→ undo: DB_TRX_ID=1, balance=100

T10(A 提交后):
  purge 线程清理:发现 m_ids 不再需要 1 和 101 的旧版本
  (取决于是否有别的事务还在用)
```

### 5. 完整读取流程图

```text
T3: SELECT (A)
  → 拍 Read View RV_A
  → 读当前行: trx_id=1, 可见 (1 < min=100)
  → 返回 (张三, 100) ✓

T5: SELECT (A)
  → 复用 RV_A
  → 读当前行: trx_id=101, 不可见 (∈ m_ids=[100,101])
  → 沿 ROLL_PTR: trx_id=1, 可见
  → 返回 (张三, 100) ✓

T7: SELECT (A)
  → 复用 RV_A
  → 同 T5 → 返回 (张三, 100) ✓

T8: UPDATE (A, 当前读)
  → 直接读最新: trx_id=101, balance=200
  → 写新版本: trx_id=100, balance=250
  → 旧的 trx_id=101 版本写 undo log

T9: SELECT (A)
  → 复用 RV_A
  → 读当前行: trx_id=100 = creator_trx_id, 可见
  → 返回 (张三, 250) ✓
```

---

## 十三、MVCC 与 undo log 的关系

### 1. 关系总览

MVCC **不是**独立于 undo log 的机制,而是**建立在 undo log 之上**的:

```text
┌─────────────────────────┐
│        undo log         │  ← 存储层(物理存储)
│  (回滚日志,记录旧版本)  │
└─────────────┬───────────┘
              │ 提供历史版本
              ▼
┌─────────────────────────┐
│   版本链(逻辑结构)      │  ← 数据结构(逻辑视图)
│  通过 DB_ROLL_PTR 串联  │
└─────────────┬───────────┘
              │ 提供版本链
              ▼
┌─────────────────────────┐
│    Read View + 算法     │  ← 决策层(选择版本)
│  判断哪个版本可见        │
└─────────────────────────┘
```

### 2. undo log 的双重身份

| 身份 | 用途 |
|------|------|
| **回滚日志** | 事务 ROLLBACK 时,反向执行,恢复数据 |
| **版本日志** | MVCC 快照读时,提供历史版本 |

> 同一个 undo log 段,既支持回滚,又支持 MVCC。

### 3. 何时生成、何时清理

| undo log 类型 | 生成时机 | 何时清理 |
|---------------|----------|----------|
| **INSERT undo log** | INSERT 时 | 事务提交后**立即可清理**(无 MVCC 价值) |
| **UPDATE undo log** | UPDATE / DELETE 时 | 需等所有需要该版本的事务结束,由 purge 线程清理 |

### 4. undo log 段的管理

```text
undo log 在 InnoDB 内部按"段 (segment)"管理:
  - 每个 undo log segment 属于一个事务
  - 事务结束后,该 segment 可能被复用
  - undo log 也会有自己的 undo log(rollover,InnoDB 内部维护)

重要配置:
  innodb_undo_tablespaces:undo 表空间数量(默认 2 个)
  innodb_undo_directory:undo 表空间存放目录
  innodb_max_undo_log_size:单个 undo 表空间上限
```

### 5. 长事务导致的 undo log 膨胀

```text
危险模式:
  BEGIN;
  UPDATE user SET name = 'x';  -- 产生 undo log v1
  -- 长事务不提交 ...
  -- 这段时间内,即使有其他事务提交,undo log 也不能清理
  COMMIT;

后果:
  - undo 表空间持续增长
  - ibdata1 / undo_001 变大
  - 可能触发 "undo log 太大" 警告

建议:
  - 避免长事务
  - 监控 INFORMATION_SCHEMA.INNODB_TRX,看 trx_started 早的
```

---

## 十四、purge 线程清理历史版本

### 1. 为什么需要 purge

```text
MVCC 的代价:每次修改都产生旧版本,undo log 不断累积。
如果不清理:
  - 磁盘空间耗尽
  - 版本链越长,查询越慢
  - 系统最终不可用
```

所以 InnoDB 有专门的 **purge 线程**,定期清理**已经没人需要的旧版本**。

### 2. 哪些 undo log 可以清理

判断一条 undo log 能否清理,核心是:**还有没有任何 Read View 需要它?**

```text
undo log 节点 X(某个旧版本):
  能清理 ⇔ 所有活跃事务的 Read View 都看不到 X

判断方法:
  找到当前所有活跃事务的 Read View,它们的 max_trx_id 各是多少
  如果 X 的 DB_TRX_ID < 所有活跃 Read View 的 min_trx_id:
    → 没有任何 Read View 会"回溯"到 X
    → X 可以清理
```

### 3. purge 流程

```text
purge 线程(后台运行):

1. 扫描 undo log
2. 找到 DB_TRX_ID < 所有活跃 Read View min_trx_id 的节点
3. 从版本链尾部开始删除
4. 释放 undo log 段
5. 在某些情况下,真正物理删除带 delete flag 的行

清理策略:
  - 物理删除: 行被 delete flag 标记,且没有事务会读它
  - 释放 undo 段: 该段的事务都提交,且无活跃事务需要
```

### 4. 与 purge 相关的视图维护

InnoDB 用一个特殊的数据结构 **trx_sys->purge_sys** 来跟踪:

```text
purge_sys 维护:
  - 已经处理到的 undo log 位置
  - 当前"可见边界"(已清理到哪里了)
  - 历史视图链表(所有活跃 Read View)
```

当新的 Read View 创建时,会被加入历史视图链表;当 Read View 所在事务结束,该视图从链表移除。

### 5. purge 触发时机

| 时机 | 说明 |
|------|------|
| **master thread 自动** | 后台循环 |
| **undo log 满** | 接近 `innodb_max_undo_log_size` 时 |
| **手动** | 某些运维场景 |
| **大事务提交后** | 可能触发大批量 purge |

### 6. 与 purge 相关的参数

| 参数 | 作用 |
|------|------|
| `innodb_purge_threads` | purge 线程数(默认 4,可调) |
| `innodb_purge_batch_size` | 每次 purge 处理 undo log 页数 |
| `innodb_max_undo_log_size` | 单个 undo 表空间上限 |
| `innodb_undo_log_truncate` | 是否启用 truncate |

### 7. 长事务对 purge 的影响

```text
典型问题:
  事务 T_long 在 9:00 开始,一直不提交
  → T_long 的 Read View 让所有相关 undo log 都不能 purge
  → 期间其他事务的修改产生的 undo log 不断堆积
  → 9:30 时,undo 表空间涨了 30GB

排查 SQL:
  SELECT * FROM information_schema.INNODB_TRX
  WHERE trx_started < NOW() - INTERVAL 60 SECOND
  ORDER BY trx_started;
  -- 找到 trx_started 最早的几个,往往是元凶
```

---

## 核心要点速记

- **MVCC = Multi-Version Concurrency Control**:多版本并发控制,读写不互斥
- **本质**:用空间(保留旧版本)换并发(读写并行)
- **三大支撑**:隐藏字段(DB_TRX_ID、DB_ROLL_PTR、DB_ROW_ID)、undo log 版本链、Read View
- **隐藏字段**:每行 3 个,DB_TRX_ID(6B)、DB_ROLL_PTR(7B)、DB_ROW_ID(6B,无主键时启用)
- **DB_TRX_ID**:最近修改此行的事务 ID,可见性算法核心
- **DB_ROLL_PTR**:指向旧版本 undo log 的指针,形成版本链
- **undo log 分类**:`insert undo`(提交即删) vs `update undo`(需 purge)
- **版本链**:每次 UPDATE 把旧版本写 undo log,用 DB_ROLL_PTR 串成单向链表
- **Read View 四字段**:`m_ids`(活跃事务列表)、`min_trx_id`(活跃最小)、`max_trx_id`(下一个 ID)、`creator_trx_id`(自己)
- **可见性算法**(5 步):
  1. `trx_id == creator` → 可见
  2. `trx_id < min_trx_id` → 可见
  3. `trx_id >= max_trx_id` → 不可见
  4. `trx_id ∈ m_ids` → 不可见
  5. 其他(`min ≤ trx_id < max`,但不在 m_ids)→ 可见
- **Read View 创建时机**:
  - **RC**:每次 SELECT 都新建
  - **RR**:事务内只用一个(首次 SELECT 创建)
- **隔离级别适用**:
  - **RU**:不走 MVCC(脏读)
  - **RC**:MVCC + 每次新 RV
  - **RR**:MVCC + 复用 RV + Next-Key Lock
  - **SR**:不走 MVCC(全部当前读)
- **快照读**:普通 SELECT,不加锁,MVCC 实现,可能读到历史版本
- **当前读**:`FOR UPDATE` / `FOR SHARE` / `UPDATE` / `DELETE` / `INSERT`,加锁,总是最新版本
- **幻读解决**:**快照读靠 MVCC,当前读靠 Next-Key Lock**
- **Next-Key Lock**:`Record Lock + Gap Lock`,锁行 + 锁间隙
- **MVCC 流程**:拿当前行 → 用 RV 判断可见 → 不可见则沿 ROLL_PTR 找旧版本 → 直到可见或链尾
- **MVCC 与 undo log**:MVCC 建立在 undo log 之上,undo log 同时承担"回滚"和"版本日志"两职
- **purge 线程**:后台清理不再需要的旧版本,避免 undo log 无限增长
- **长事务是 MVCC 的大敌**:让 undo log 无法 purge,导致空间膨胀
- **监控长事务**:`INFORMATION_SCHEMA.INNODB_TRX` 看 `trx_started` 早的
- **默认隔离级别**:InnoDB 是 **REPEATABLE READ**
- **建议**:业务层避免长事务,显式定义主键,善用 `READ COMMITTED`(根据场景)