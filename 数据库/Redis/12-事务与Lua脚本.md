# Redis 事务与 Lua 脚本 (Transaction & Lua Script)

> 本章覆盖 Redis 事务体系与 Lua 脚本编程两大主题：MULTI/EXEC/DISCARD/WATCH 事务模型、Redis 事务与 ACID 的差异、乐观锁实现、WATCH 秒杀实战、Lua 脚本原子性原理、EVAL/EVALSHA 用法、限流器与分布式锁实战、Redis 7+ Function 新特性、Cluster 中 Lua 的限制、以及事务 vs Lua vs Pipeline 三者对比。理解事务与脚本是构建高并发安全业务（如库存扣减、票务秒杀、分布式锁）的基石。

---

## 一、Redis 事务概述

### 1. 什么是 Redis 事务

**Redis 事务** 是一组命令的集合，被一个**执行单元**（EXEC 或 DISCARD）包裹起来，事务中的命令要么**全部按序执行**，要么**全部不执行**。它提供了一种"批量命令打包送达服务端"的机制。

```text
┌──────────────────────────────────────────────────────────────┐
│                     Redis 事务的工作方式                      │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  客户端                       Redis 服务端                    │
│  ┌──────────┐                                                  │
│  │ MULTI    │ ──────►  标记事务开始，后续命令进入队列            │
│  │ SET k1 v1│ ──────►  入队 (queued)，不立即执行              │
│  │ INCR k2  │ ──────►  入队 (queued)                         │
│  │ EXEC     │ ──────►  原子执行整个队列，返回所有结果          │
│  └──────────┘                                                  │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 2. 与关系数据库事务的根本区别

Redis 事务**不是**传统意义上的 ACID 事务：

| 维度 | MySQL/InnoDB 事务 | Redis 事务 |
|------|-------------------|------------|
| 原子性 | 全部执行或全部回滚（undo log） | 全部执行或全部不执行（**无回滚**） |
| 一致性 | 由 AID + 约束共同保证 | 由业务代码保证 |
| 隔离性 | 由锁 + MVCC 提供多级隔离 | 单线程串行执行，天然隔离 |
| 持久性 | redo log 保证 | 依赖 RDB/AOF，事务本身不保证 |
| 错误处理 | 运行时错误回滚整个事务 | 语法错误放弃事务，运行错误继续执行 |
| 锁机制 | 行锁、间隙锁、意向锁 | 乐观锁 WATCH（CAS 风格） |
| 嵌套事务 | 支持 SAVEPOINT | 不支持 |

> **核心差异**：Redis 事务**不提供回滚机制**。如果你希望"出错就回滚"，必须通过 WATCH + 重试的方式由**客户端**实现。

### 3. Redis 事务的五大命令

```text
┌─────────────────────────────────────────────────────────────┐
│                Redis 事务命令三件套 + 监视/取消              │
├──────────────┬──────────────────────────────────────────────┤
│ MULTI        │ 开启事务，命令进入队列，不立即执行            │
│ EXEC         │ 原子执行队列中所有命令                        │
│ DISCARD      │ 取消事务，丢弃队列中所有命令                  │
│ WATCH key    │ 监视 key，被修改则 EXEC 失败（乐观锁）        │
│ UNWATCH      │ 取消所有 WATCH 监视                          │
└──────────────┴──────────────────────────────────────────────┘
```

---

## 二、事务命令详解

### 1. MULTI：开启事务

`MULTI` 标记事务开始。执行 `MULTI` 之后，客户端**所有**写入命令不会立即执行，而是被**入队**到事务队列中，服务端返回 `QUEUED` 表示已入队。

```bash
> MULTI
OK

> SET name "alice"
QUEUED

> INCR counter
QUEUED

> RPUSH list "a" "b"
QUEUED
```

**关键点**：
- `MULTI` 之后到 `EXEC` 之前，命令**不会真正执行**，仅入队
- `MULTI` 之后不能使用 `WATCH`（WATCH 应在 `MULTI` 之前）
- `MULTI` 不能嵌套，重复 `MULTI` 会报错
- 大多数**读命令**（GET、HGET 等）也可以在事务中入队，但很少使用

```text
┌─────────────────────────────────────────────────────────────┐
│               MULTI 之后的命令流转                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  客户端 COMMAND ──► 解析 ──► 处于事务中? ──yes─► 入队 QUEUED │
│                                │                            │
│                                │no                          │
│                                ▼                            │
│                            直接执行                          │
└─────────────────────────────────────────────────────────────┘
```

### 2. EXEC：执行事务

`EXEC` 触发事务中的所有命令按入队顺序**原子执行**，并返回所有命令的**结果数组**。

```bash
> MULTI
OK
> SET name "alice"
QUEUED
> INCR counter
QUEUED
> RPUSH list "a" "b"
QUEUED

> EXEC
1) OK
2) (integer) 1
3) (integer) 2
```

**关键点**：
- 队列中命令**按顺序**执行
- 客户端会收到一个**数组**，包含每条命令的执行结果
- 若使用了 `WATCH`，且被监视的 key 在 EXEC 前被修改，则 `EXEC` 返回 `nil`（整个事务被丢弃）

```text
┌─────────────────────────────────────────────────────────────┐
│                    EXEC 时序图                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  T0  客户端发 MULTI                                          │
│  T1  客户端发 SET k1 v1   →  QUEUED                        │
│  T2  客户端发 SET k2 v2   →  QUEUED                        │
│  T3  客户端发 EXEC                                          │
│  T4  ← 此时服务端按顺序执行                                  │
│       EXEC1: SET k1 v1  →  结果1                           │
│       EXEC2: SET k2 v2  →  结果2                           │
│  T5  返回 [结果1, 结果2] 给客户端                            │
│       (T4-T5 期间不会插入其他客户端的命令)                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3. DISCARD：取消事务

`DISCARD` 取消事务，**清空**事务队列中的所有命令，**撤销**所有已设置的 WATCH，事务结束。

```bash
> MULTI
OK
> SET name "bob"
QUEUED
> SET age 30
QUEUED

> DISCARD
OK

> GET name
"alice"          # 数据未改变
```

**关键点**：
- `DISCARD` 之后，事务状态被完全重置
- 等价于 `EXEC` 失败，但**不需要** `WATCH` 配合
- 适合"先组装命令，中途决定放弃"的场景

### 4. WATCH：监视 key（乐观锁）

`WATCH key [key ...]` 让客户端对若干 key 加**乐观锁**：从此刻起，任何**其他客户端**对这些 key 的修改都会被记录。当该客户端执行 `EXEC` 时：
- 若**所有**被 WATCH 的 key 都**未被修改** → EXEC 正常执行事务
- 若**任一**被 WATCH 的 key 被修改 → EXEC 返回 `nil`，事务不执行

```bash
# 客户端 A
> WATCH balance
OK
> GET balance
"100"
> MULTI
OK
> SET balance 50
QUEUED
> EXEC
(nil)              # ← 客户端 B 在 EXEC 前修改了 balance，事务被打断
```

**关键点**：
- `WATCH` 必须在 `MULTI` 之前
- 乐观锁机制：先读 → 计算 → 写，CAS 风格
- `EXEC` 失败后必须**重新** WATCH 整个流程（客户端需要重试）
- `WATCH` 与客户端连接绑定，连接断开时自动解除

```text
┌─────────────────────────────────────────────────────────────┐
│              WATCH 乐观锁执行流程                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  客户端 A                   Redis 客户端 B                  │
│  ┌──────────┐                ┌──────────┐                  │
│  │1. WATCH balance│          │          │                  │
│  │2. GET balance=100│       │          │                  │
│  │3. 计算新值 50   │          │          │                  │
│  │   ...           │          │ DECR balance  ←── 60       │
│  │4. MULTI         │          │          │                  │
│  │5. SET balance 50│          │          │                  │
│  │6. EXEC          │          │          │                  │
│  │   (nil) 失败!    │          │          │                  │
│  │   → 重新 WATCH  │          │          │                  │
│  └──────────┘                └──────────┘                  │
│                                                             │
│  关键:客户端 A 的 EXEC 在 B 改值之后执行 → 失败                          │
└─────────────────────────────────────────────────────────────┘
```

### 5. UNWATCH：取消所有监视

`UNWATCH` 在 `EXEC` 之前手动取消所有 WATCH，事务可继续（但若已 `MULTI`，还需要 `DISCARD` 取消）。

```bash
> WATCH balance
OK
> UNWATCH
OK
> MULTI
OK
> SET balance 100
QUEUED
> EXEC
1) OK
```

**关键点**：
- `UNWATCH` 总是释放所有 WATCH，与 key 数量无关
- `EXEC` 成功执行后也会自动释放 WATCH
- `DISCARD` 也会自动释放 WATCH

---

## 三、Redis 事务的 ACID 特性分析

### 1. 原子性（Atomicity）

Redis 事务的"原子性"是**有限**的：

```text
┌─────────────────────────────────────────────────────────────┐
│              Redis 事务原子性的边界                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  层面 1:命令入队阶段                                          │
│   - 语法错误(命令不存在、参数错)                              │
│   - 整个事务被放弃                                            │
│   - 类似 MySQL 的"语句级失败"                                │
│                                                             │
│  层面 2:EXEC 执行阶段                                        │
│   - 单条命令运行时错误(类型错、值越界等)                       │
│   - 该条命令失败,其他命令继续执行                              │
│   - 类似 MySQL 的"行级失败" + 不回滚                        │
│                                                             │
│  结论: 事务中所有命令均执行(或均不执行),                       │
│       但执行结果可能部分失败                                   │
└─────────────────────────────────────────────────────────────┘
```

**关键点**：
- Redis 事务**不提供回滚**机制
- 事务执行的命令序列**中间不会插入其他客户端的命令**，这是它提供的主要"原子性"
- 错误处理必须在**业务代码**中显式判断

### 2. 不支持回滚（No Rollback）

Redis 官网明确声明：**Redis 事务在执行过程中如果发生错误，事务不会回滚**。

```bash
# 案例：事务中部分命令失败
> MULTI
OK
> SET k1 v1
QUEUED
> INCR k2          # k2 是字符串，无法自增
QUEUED
> SET k3 v3
QUEUED

> EXEC
1) OK
2) (error) ERR value is not an integer or out of range
3) OK

# 结果:k1 成功、k3 成功,k2 失败
# 没有任何"回滚"
```

**为什么 Redis 不支持回滚？**

| 理由 | 说明 |
|------|------|
| 性能 | 回滚需要记录大量状态，影响 Redis 的高性能 |
| 简洁性 | 错误本质上由业务逻辑错误引起，客户端应自己处理 |
| AOF 兼容性 | AOF 日志只记录成功命令，无法回滚 |
| 实践哲学 | Redis 鼓励"开发期充分测试，运行时快速失败" |

### 3. 隔离性（Isolation）

Redis 是**单线程**事件循环模型，所有命令按顺序执行，**事务中的命令在执行时不可能被其他客户端的命令插入**。

```text
┌─────────────────────────────────────────────────────────────┐
│               Redis 单线程执行模型                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │           Redis 主线程 (单线程事件循环)               │   │
│  │  ┌──────┐ ┌──────┐ ┌──────────────────────┐ ┌──────┐│   │
│  │  │ SET  │ │ MULTI│ │ A SET │ B GET │ EXEC │ │ LPOP ││   │
│  │  └──────┘ └──────┘ └──────────────────────┘ └──────┘│   │
│  │                                                     │   │
│  │  事务执行期间:                                       │   │
│  │   - 事务队列的命令连续执行                            │   │
│  │   - 不会被其他客户端命令打断                          │   │
│  │   - 天然 SERIALIZABLE 隔离级别                      │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**关键点**：
- 单线程 → 天然串行化，无脏读、不可重复读、幻读问题
- 但：**EXEC 之前**的 WATCH 检查是原子检查，**EXEC 之后的命令**若有其他客户端可能读到部分写入的中间态（事务内写命令是连续执行的，所以中间态只发生在事务以外）
- Redis 6 引入了 I/O 多线程，但**命令执行仍是单线程**

### 4. 不支持持久性（No Durability）

Redis 事务**不保证**事务执行后数据立即写入磁盘。持久性由 RDB/AOF 机制决定：

```text
┌─────────────────────────────────────────────────────────────┐
│              Redis 持久性依赖关系                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│              事务执行成功                                     │
│                   │                                         │
│                   ▼                                         │
│              数据在内存中 ✓                                   │
│                   │                                         │
│        ┌──────────┼──────────┐                              │
│        ▼          ▼          ▼                               │
│      RDB 快照   AOF 日志   仅内存                            │
│      (定时)    (异步刷盘)   (宕机丢)                          │
│                                                             │
│  - 即使开启 AOF，appendfsync everysec 也可能丢 1 秒数据       │
│  - 事务持久性 = RDB/AOF 配置策略                             │
│  - 不像 MySQL，默认 commit 即刷盘                            │
└─────────────────────────────────────────────────────────────┘
```

**关键点**：
- Redis 事务执行完成后，**不立即**调用 fsync
- 宕机场景下事务可能丢失
- 需要强持久性场景应使用 `WAIT` 命令（同步复制到 N 个副本）

---

## 四、事务工作流程详解

### 1. 完整流程图

```text
┌──────────────────────────────────────────────────────────────────┐
│                  Redis 事务的完整工作流程                          │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────┐                                             │
│  │ 客户端连接服务器  │                                             │
│  └────────┬────────┘                                             │
│           ▼                                                       │
│  ┌─────────────────┐       是                                     │
│  │ 需要乐观锁?      │────────► WATCH key1 key2 ...                │
│  └────────┬────────┘                                             │
│           │ 否                                                    │
│           ▼                                                       │
│  ┌─────────────────┐                                             │
│  │ MULTI           │  ← 标记事务开始                              │
│  └────────┬────────┘                                             │
│           ▼                                                       │
│  ┌─────────────────┐                                             │
│  │ 循环发送命令      │  ← 每条命令返回 QUEUED                       │
│  │  ┌────────────┐ │                                             │
│  │  │COMMAND 1   │ │                                             │
│  │  │COMMAND 2   │ │                                             │
│  │  │...         │ │                                             │
│  │  └────────────┘ │                                             │
│  └────────┬────────┘                                             │
│           ▼                                                       │
│  ┌─────────────────┐                                             │
│  │ 触发执行条件      │                                             │
│  │  ┌──┐ ┌──┐ ┌──┐│                                             │
│  │  │EX│ │DI│ │错│ │                                             │
│  │  │EC│ │SC│ │误│ │                                             │
│  │  │  │ │AR│ │  │ │                                             │
│  │  │  │ │D │ │  │ │                                             │
│  │  └──┘ └──┘ └──┘│                                             │
│  └────────┬────────┘                                             │
│           ▼                                                       │
│  ┌─────────────────┐                                             │
│  │EXEC              │  ← 原子执行事务                              │
│  │ 1. 检查 WATCH   │                                             │
│  │ 2. 顺序执行队列  │                                             │
│  │ 3. 返回结果数组  │                                             │
│  └────────┬────────┘                                             │
│           ▼                                                       │
│  ┌─────────────────┐                                             │
│  │ 清除事务状态      │  ← 结束                                    │
│  └─────────────────┘                                             │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 2. 服务端事务状态

```text
┌─────────────────────────────────────────────────────────────┐
│        Redis 服务端事务状态机                                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  INITIAL ──MULTI──► MULTI_COMMAND ──EXEC──► EXEC_RUNNING  │
│                                                  │          │
│                                            ┌─────┴────┐    │
│                                            ▼          ▼    │
│                                         完成     DISCARD    │
│                                            │          │    │
│                                            ▼          ▼    │
│                                          INITIAL  INITIAL  │
│                                                             │
│  状态字段:                                                   │
│   - flags:客户端连接标志(CLIENT_MULTI)                       │
│   - mstate: 事务状态                                           │
│     - commands:命令队列(数组)                                │
│     - count:命令数量                                          │
│   - watched_keys:被 WATCH 的 keys                            │
└─────────────────────────────────────────────────────────────┘
```

### 3. 性能开销

Redis 事务**不提供性能优势**：它只是批量命令的"打包"，每条命令仍然走完整命令解析流程。

```text
┌─────────────────────────────────────────────────────────────┐
│          事务 vs 管道(Pipeline)的性能差异                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Pipeline:                                                  │
│   客户端发送:[CMD1][CMD2][CMD3]                             │
│   节省:RTT (网络往返时间)                                    │
│   服务端:各命令独立执行,可被其他客户端命令插入                  │
│   隔离性:✗                                                   │
│                                                             │
│  事务 (MULTI/EXEC):                                         │
│   客户端发送:[MULTI][CMD1][CMD2][EXEC]                      │
│   节省:RTT                                                  │
│   服务端:各命令先入队,EXEC 时原子执行                         │
│   隔离性:✓ (EXEC 执行期间)                                   │
│                                                             │
│  Lua 脚本:                                                  │
│   客户端发送:[EVAL "..." k1 k2 v1 v2]                       │
│   服务端:脚本整体作为一个命令执行,原子性最强                   │
│   隔离性:✓ (脚本执行期间)                                     │
│   额外:逻辑写在服务端,可读变量,无需往返                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 五、事务失败场景

### 1. 场景一：入队错误（语法错误）

**原因**：命令语法错误、命令不存在、参数数量错误。这种错误在 `EXEC` 之前就会被服务端检测到。

```bash
> MULTI
OK
> SET k1 v1
QUEUED
> SET k2                # ← 参数不足,语法错误
(error) ERR wrong number of arguments for 'set' command
> SET k3 v3
QUEUED
> EXEC
(error) EXECABORT Transaction discarded because of previous errors.

# 结果:整个事务被放弃,没有命令被执行
```

**关键点**：
- 入队时**立即返回错误**（不是 QUEUED）
- `EXEC` 时检测到队列中有错误，**整个事务被放弃**
- 即使其他命令语法正确，也**不会执行**

### 2. 场景二：执行错误（运行时错误）

**原因**：命令语法正确，但运行时报错（如对字符串执行 INCR、对集合执行 LPUSH 等）。

```bash
> MULTI
OK
> SET k1 v1
QUEUED
> INCR k1              # ← 运行时错误:String 不能自增
QUEUED
> SET k2 v2
QUEUED
> EXEC
1) OK
2) (error) ERR value is not an integer or out of range
3) OK

# 结果:SET k1 成功,INCR k1 失败但继续,SET k2 成功
```

**关键点**：
- 入队时**返回 QUEUED**（语法没问题）
- `EXEC` 执行时遇到错误，该命令失败，其他命令**继续执行**
- 整个事务**没有回滚**

### 3. 场景三：WATCH 失败

**原因**：被 WATCH 的 key 在 `EXEC` 之前被其他客户端修改。

```bash
# 客户端 A
> WATCH balance
OK
> GET balance
"100"

# 客户端 B 并发操作
> DECRBY balance 30
(integer) 70

# 客户端 A 继续
> MULTI
OK
> SET balance 50
QUEUED
> EXEC
(nil)              # ← 事务被放弃,返回 nil

> GET balance
"70"               # ← 是 B 设置的值,不是 A 事务执行的结果
```

**客户端正确处理：**

```python
import redis

def transfer_optimistic(r, src, dst, amount):
    while True:
        try:
            with r.pipeline() as pipe:
                # 在 MULTI 之前 WATCH
                pipe.watch(src)
                current = r.get(src)
                if current is None or int(current) < amount:
                    pipe.unwatch()
                    return False

                # MULTI 开始
                pipe.multi()
                pipe.decrby(src, amount)
                pipe.incrby(dst, amount)

                # EXEC,若返回 None 则重试
                result = pipe.execute()
                if result is None:
                    continue  # 乐观锁失败,重试
                return True
        except redis.exceptions.WatchError:
            continue
```

### 4. 失败场景对比表

| 场景 | 触发时机 | 错误表现 | 事务结果 | 客户端处理 |
|------|---------|---------|---------|-----------|
| 语法错误 | 入队时 | 入队命令本身返回 error | 整个事务被放弃 | 重新组装命令 |
| 运行时错误 | EXEC 时 | 结果数组中某项是 error | 错误的命令失败，其他继续 | 业务层校验 |
| WATCH 失败 | EXEC 时 | EXEC 返回 nil | 整个事务被放弃 | 重新 WATCH 并重试 |
| 客户端断开 | 任意时刻 | 连接关闭 | 事务队列丢弃 | 重新连接 |

---

## 六、WATCH 优化锁实现

### 1. 乐观锁原理

乐观锁（Optimistic Lock）是一种**并发控制**思想：

```text
┌─────────────────────────────────────────────────────────────┐
│              乐观锁 vs 悲观锁                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  悲观锁 (MySQL 的 SELECT FOR UPDATE):                       │
│   - 读取前先加锁,阻塞其他事务                                │
│   - 适合写多读少,冲突严重                                   │
│   - 性能开销大                                              │
│                                                             │
│  乐观锁 (Redis 的 WATCH):                                  │
│   - 读取不加锁,仅记录版本                                    │
│   - 提交时检查版本,若被修改则放弃                            │
│   - 适合读多写少,冲突概率低                                  │
│   - 性能开销小,失败需重试                                    │
│                                                             │
│  Redis WATCH 实现:                                          │
│   - WATCH key 记录该 key 的"版本"                            │
│   - 其他客户端修改 key → 版本变化                            │
│   - 本客户端 EXEC 时检查版本,若不一致 → 失败                 │
└─────────────────────────────────────────────────────────────┘
```

### 2. 核心算法

```text
┌─────────────────────────────────────────────────────────────┐
│            WATCH 乐观锁算法 (CAS-like)                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  LOOP:                                                      │
│    1. WATCH key1 key2                                       │
│    2. READ key1, key2                                       │
│    3. 检查业务规则 (key1 余额 >= 转账金额)                    │
│    4. 计算新值                                              │
│    5. MULTI                                                 │
│    6. WRITE key1, key2                                      │
│    7. EXEC                                                  │
│    8. IF EXEC 返回 nil THEN GOTO LOOP (重试)                 │
│       ELSE 结束,事务成功                                     │
│                                                             │
│  风险:ABA 问题 → Redis 通过版本号/唯一标识解决               │
│  重试上限:应设置重试次数上限,避免死循环                       │
└─────────────────────────────────────────────────────────────┘
```

### 3. 应用场景

| 场景 | WATCH 的 key | 业务逻辑 |
|------|-------------|---------|
| 库存扣减 | stock:{item_id} | 检查库存 > 0，扣减 |
| 余额转账 | balance:{user_id} | 检查余额 >= 金额，扣减 |
| 票务秒杀 | ticket:{event_id} | 检查余票 > 0，抢票 |
| 限流计数 | counter:{api_id} | 检查计数 < 阈值，自增 |
| 分布式锁 | lock:{resource} | 检查锁未持有，加锁 |

---

## 七、完整示例：秒杀库存扣减

### 1. 业务场景

模拟双十一秒杀活动，10 万人抢 100 件商品。库存 `stock:item100` 初始为 100，每个用户抢一次，扣减库存。

### 2. 方案一：纯 WATCH 乐观锁实现

```python
import redis
import time

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

# 初始化库存
r.set('stock:item100', 100)

def seckill_watch(user_id, item_id='item100', max_retries=3):
    """
    使用 WATCH 实现乐观锁扣减库存
    """
    stock_key = f'stock:{item_id}'
    user_key = f'seckill:user:{user_id}'

    for attempt in range(max_retries):
        try:
            # 1. WATCH 库存 key
            r.watch(stock_key)

            # 2. 读取当前库存
            stock = int(r.get(stock_key) or 0)

            # 3. 业务校验
            if stock <= 0:
                r.unwatch()
                return False, "已售罄"

            # 4. 检查用户是否已抢过 (业务约束)
            if r.exists(user_key):
                r.unwatch()
                return False, "已抢购过"

            # 5. MULTI 开始事务
            pipe = r.pipeline()
            pipe.multi()
            pipe.decr(stock_key)
            pipe.set(user_key, 1)

            # 6. EXEC 执行
            results = pipe.execute()

            if results is None:
                # 7. WATCH 失败,重试
                time.sleep(0.01 * (attempt + 1))  # 退避
                continue

            # 8. 成功
            return True, f"抢购成功,剩余 {stock - 1}"

        except redis.exceptions.WatchError:
            continue
        finally:
            r.unwatch()

    return False, "抢购失败,请重试"
```

### 3. 方案二：Lua 脚本实现（更优）

上面 WATCH 方案的问题：
- 重试机制可能在高并发下大量失败
- 多次往返网络，性能不佳

**Lua 脚本方案**（原子执行，零重试）：

```lua
-- seckill.lua
-- KEYS[1]: 库存 key
-- KEYS[2]: 用户抢购标记 key
-- ARGV[1]: 抢购数量 (一般 1)

local stock_key = KEYS[1]
local user_key = KEYS[2]
local qty = tonumber(ARGV[1])

-- 检查用户是否已抢过
if redis.call('EXISTS', user_key) == 1 then
    return {0, '已抢购过'}
end

-- 检查库存
local stock = tonumber(redis.call('GET', stock_key) or '0')
if stock < qty then
    return {0, '已售罄'}
end

-- 扣减库存 + 标记用户
redis.call('DECRBY', stock_key, qty)
redis.call('SET', user_key, 1)

return {1, '抢购成功'}
```

**Python 调用：**

```python
import redis

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

# 加载脚本
seckill_script = """
local stock_key = KEYS[1]
local user_key = KEYS[2]
local qty = tonumber(ARGV[1])

if redis.call('EXISTS', user_key) == 1 then
    return {0, '已抢购过'}
end

local stock = tonumber(redis.call('GET', stock_key) or '0')
if stock < qty then
    return {0, '已售罄'}
end

redis.call('DECRBY', stock_key, qty)
redis.call('SET', user_key, 1)

return {1, '抢购成功'}
"""

# 注册脚本
sha = r.script_load(seckill_script)

def seckill_lua(user_id, item_id='item100'):
    stock_key = f'stock:{item_id}'
    user_key = f'seckill:user:{user_id}'
    try:
        result = r.evalsha(sha, 2, stock_key, user_key, 1)
        code, msg = result
        return code == 1, msg
    except redis.exceptions.NoScriptError:
        # 脚本未加载,重新执行
        return seckill_lua(user_id, item_id)
```

### 4. 两种方案对比

```text
┌─────────────────────────────────────────────────────────────┐
│              WATCH vs Lua 秒杀方案对比                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  项        WATCH 方案              Lua 方案                  │
│  ─────────────────────────────────────────────────────────  │
│  原子性     EXEC 内原子               脚本原子性              │
│  网络往返   多次 (WATCH+GET+EXEC)    1 次 (EVAL/EVALSHA)     │
│  性能       10 万并发需多次重试       单次成功,极快            │
│  代码复杂度 较高 (重试+异常)          较低 (脚本封装)          │
│  适用场景   低并发、逻辑简单          高并发、本地化复杂逻辑     │
│  失败处理   自动重试 N 次            客户端处理返回结果         │
│                                                             │
│  结论: 秒杀场景强烈推荐 Lua 脚本                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 八、Redis 事务与 MySQL 事务对比

### 1. 核心差异总结

| 维度 | MySQL InnoDB | Redis |
|------|--------------|-------|
| 隔离级别 | 4 级（RU/RC/RR/SR） | 固定串行化（单线程） |
| 锁机制 | 行锁、间隙锁、意向锁 | 乐观锁 WATCH |
| 原子性 | 全做或全不做，undo 回滚 | 全做或全不做，**无回滚** |
| 持久性 | 提交即刷 redo log | 依赖 RDB/AOF 配置 |
| 性能 | 几万 TPS | 几十万~百万 TPS |
| 适用场景 | 强一致业务（金融、订单） | 高性能场景（缓存、计数、限流） |
| 错误处理 | 运行时错误回滚 | 运行时错误继续执行 |
| 嵌套 | 支持 SAVEPOINT | 不支持 |
| 容量 | 取决于磁盘 | 取决于内存 |

### 2. 选型指导

```text
┌─────────────────────────────────────────────────────────────┐
│              何时使用 Redis 事务 vs MySQL 事务                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  使用 Redis 事务 / Lua:                                      │
│   - 缓存一致性保证                                            │
│   - 计数器原子操作                                            │
│   - 限流、分布式锁                                            │
│   - 秒杀、抢票的库存扣减                                      │
│   - 排行榜、热度计算                                          │
│   - 不需要强一致,允许最终一致                                  │
│                                                             │
│  使用 MySQL 事务:                                            │
│   - 金融交易、转账、支付                                       │
│   - 订单创建、库存变更                                        │
│   - 强一致业务需求                                             │
│   - 复杂查询和事务并发                                        │
│   - 业务核心数据持久化                                        │
│                                                             │
│  混合方案:                                                   │
│   - Redis 做热点数据预扣                                     │
│   - MySQL 做最终落库                                         │
│   - 异步同步 + 补偿机制                                       │
└─────────────────────────────────────────────────────────────┘
```

---

## 九、Lua 脚本概述

### 1. 为什么需要 Lua 脚本

Redis 2.6 引入了 Lua 脚本支持，通过 `EVAL`/`EVALSHA` 命令执行。Lua 脚本可以在 Redis 服务端**原子执行**任意复杂逻辑。

```text
┌─────────────────────────────────────────────────────────────┐
│            Redis 嵌入 Lua 解释器的架构                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   客户端                Redis 服务端                         │
│  ┌────────┐          ┌───────────────────────────────┐     │
│  │        │  EVAL    │  ┌─────────────────────────┐  │     │
│  │ 脚本   │ ────────►│  │  Lua 解释器 (Lua 5.1)   │  │     │
│  │ 代码   │          │  │  ┌─────────────────────┐│  │     │
│  │        │          │  │  │ redis.call(...)     ││  │     │
│  │ KEYS   │          │  │  │ redis.pcall(...)    ││  │     │
│  │ ARGV   │          │  │  └─────────────────────┘│  │     │
│  │        │          │  │  ↓↓↓ 操作 Redis 数据 ↓  │  │     │
│  │        │          │  │  DB0: keys/values       │  │     │
│  └────────┘          │  │  DB1: keys/values       │  │     │
│                      │  └─────────────────────────┘  │     │
│                      │  整个脚本执行期间:              │     │
│                      │   - 不能插入其他客户端命令      │     │
│                      │   - 所有命令连续原子执行        │     │
│                      └───────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

### 2. Lua 脚本的三大特性

| 特性 | 说明 |
|------|------|
| **原子性** | 脚本执行期间不会插入其他客户端命令，相当于"事务+" |
| **减少网络往返** | 脚本逻辑在服务端执行，避免多次 GET/SET 往返 |
| **复杂逻辑服务端化** | 业务逻辑可以下沉到 Redis，降低应用层复杂度 |

### 3. 嵌入式 Lua 5.1

Redis 内嵌的是 **Lua 5.1** 解释器（不是最新版本），不支持：

- `goto` 关键字
- `bit32` 库（部分弃用）
- 协程的高级用法（Redis 单线程下没用）
- 跨脚本的全局变量共享

但**支持**：

- 基本语法（变量、循环、条件、函数）
- `string`、`table`、`math` 库
- Redis 提供的 `redis.call()` / `redis.pcall()` 全局函数
- `cjson` / `cmsgpack` 库（Redis 5+ 部分支持）

---

## 十、Lua 脚本的优势

### 1. 原子性保证

```text
┌─────────────────────────────────────────────────────────────┐
│           Lua 脚本执行期间的原子性                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  时刻 T0: 客户端 A 发送 EVAL "..."                          │
│  时刻 T1: Redis 开始执行脚本                                │
│  时刻 T2: 脚本调用 redis.call('INCR', 'counter')            │
│  时刻 T3: 脚本调用 redis.call('GET', 'counter')             │
│  时刻 T4: 脚本结束,Redis 返回结果                            │
│                                                             │
│  T1 - T4 期间:                                              │
│   - 任何其他客户端的命令都进入队列,等待执行                   │
│   - 脚本内的所有 redis.call 视为一个原子操作                 │
│   - 没有任何"中间态"被其他客户端看到                          │
│                                                             │
│  对比纯事务:                                                 │
│  MULTI/EXEC 内的命令虽然原子执行,                            │
│  但 WATCH 仍需多次往返,且原子性局限在 EXEC 瞬间                │
│  Lua 脚本的原子性更完整,且执行更高效                          │
└─────────────────────────────────────────────────────────────┘
```

### 2. 减少网络往返

```python
# 不用 Lua:多次往返
def transfer_no_lua(r, src, dst, amount):
    src_val = r.get(src)             # RTT 1
    if src_val is None or int(src_val) < amount:
        return False
    r.decrby(src, amount)            # RTT 2
    r.incrby(dst, amount)            # RTT 3
    return True

# 用 Lua:1 次往返
TRANSFER_LUA = """
local src_val = tonumber(redis.call('GET', KEYS[1]) or '0')
if src_val < tonumber(ARGV[1]) then
    return 0
end
redis.call('DECRBY', KEYS[1], ARGV[1])
redis.call('INCRBY', KEYS[2], ARGV[1])
return 1
"""

def transfer_lua(r, src, dst, amount):
    sha = r.script_load(TRANSFER_LUA)
    return r.evalsha(sha, 2, src, dst, amount)
```

**性能对比**（RTT 假设 1ms，业务逻辑 1ms）：

| 方案 | RTT 次数 | 总耗时 |
|------|---------|--------|
| 不用 Lua | 3 (读+改+改) | 3ms |
| 用 Lua | 1 | 1ms |

### 3. 复杂逻辑服务端化

```lua
-- 服务端计算用户积分等级
local score = tonumber(redis.call('ZSCORE', KEYS[1], ARGV[1]))
if not score then
    return {0, 'unknown'}
end

local level = 'bronze'
if score >= 1000 then
    level = 'gold'
elseif score >= 500 then
    level = 'silver'
end

redis.call('ZADD', KEYS[2], score, ARGV[1])

return {1, level, score}
```

这样，业务逻辑可以集中在 Redis 脚本中，应用层只需调用接口。

---

## 十一、EVAL 与 EVALSHA 命令

### 1. EVAL 命令

**语法**：

```text
EVAL script numkeys key [key ...] arg [arg ...]
```

**参数**：

| 参数 | 含义 |
|------|------|
| `script` | Lua 脚本代码 |
| `numkeys` | key 的数量 |
| `key ...` | 传递给脚本的 Redis keys（KEYS 表） |
| `arg ...` | 传递给脚本的参数（ARGV 表） |

**示例**：

```bash
# 简单示例：返回两个数之和
> EVAL "return ARGV[1] + ARGV[2]" 0 10 20
(integer) 30

# 复合示例：SET 加 GET
> EVAL "redis.call('SET', KEYS[1], ARGV[1]); return redis.call('GET', KEYS[1])" 1 foo bar
"bar"

# 多个 key 和 arg
> EVAL "return {KEYS[1], KEYS[2], ARGV[1], ARGV[2]}" 2 k1 k2 v1 v2
1) "k1"
2) "k2"
3) "v1"
4) "v2"
```

### 2. EVALSHA 命令（优化）

每次都用 `EVAL` 发送整个脚本代码会浪费带宽。Redis 在执行 `EVAL` 时会**缓存**脚本的 SHA1 摘要，后续可用 `EVALSHA` 通过摘要调用脚本。

```text
┌─────────────────────────────────────────────────────────────┐
│              EVAL 与 EVALSHA 的工作流                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  客户端                          Redis                       │
│  ┌──────────────┐                                          │
│  │ 1. 计算脚本SHA1│                                          │
│  │    SCRIPT LOAD │ ──────► SCRIPT LOAD "..." ──► 缓存SHA1 │
│  │               │                返回 sha1:abc123        │
│  │ 2. EVALSHA    │               已缓存                   │
│  │   abc123 k1 v1│ ──────► EVALSHA abc123 1 k1 v1 ──►  │
│  │               │                执行脚本                 │
│  │ 3. 收到结果   │ ◄────── 返回执行结果                  │
│  └──────────────┘                                          │
│                                                             │
│  优势: 后续调用只传 SHA1,节省网络带宽                        │
└─────────────────────────────────────────────────────────────┘
```

**完整示例**：

```bash
# 1. 直接 EVAL(会缓存)
> EVAL "return redis.call('GET', KEYS[1])" 1 mykey
"myvalue"

# 2. 计算 SHA1
> EVAL "return redis.call('GET', KEYS[1])" 1 mykey
# 假设返回 SHA1 是 "a42059b86..."

# 3. 后续用 EVALSHA
> EVALSHA a42059b86... 1 mykey
"myvalue"

# 或显式加载(不执行)
> SCRIPT LOAD "return redis.call('GET', KEYS[1])"
"a42059b86..."

# 4. 查询脚本是否存在
> SCRIPT EXISTS a42059b86...
1) (integer) 1

# 5. 删除脚本
> SCRIPT FLUSH
OK
```

### 3. NOSCRIPT 错误处理

当 Redis 找不到 SHA1 对应的脚本时（如重启后脚本缓存清空），`EVALSHA` 返回 `NOSCRIPT` 错误：

```bash
> EVALSHA abc123 1 k1
(error) NOSCRIPT No matching script. Please use EVAL.
```

**正确处理**：

```python
import redis

r = redis.Redis()

def safe_evalsha(r, script, num_keys, *args):
    """EVALSHA 失败时回退到 EVAL"""
    sha = r.script_load(script)
    try:
        return r.evalsha(sha, num_keys, *args)
    except redis.exceptions.NoScriptError:
        # 脚本未加载,可能是 Redis 重启过
        return r.eval(script, num_keys, *args)

# 或者先用 SCRIPT LOAD + EVALSHA,失败重试
def call_script(r, script, num_keys, *args):
    sha = r.script_load(script)
    try:
        return r.evalsha(sha, num_keys, *args)
    except redis.exceptions.NoScriptError:
        # 重新加载后再次尝试
        sha = r.script_load(script)
        return r.evalsha(sha, num_keys, *args)
```

### 4. 脚本管理命令

| 命令 | 说明 |
|------|------|
| `SCRIPT LOAD script` | 加载脚本到缓存，返回 SHA1 |
| `EVALSHA sha1 numkeys ...` | 通过 SHA1 执行脚本 |
| `SCRIPT EXISTS sha1 [sha1 ...]` | 检查脚本是否存在 |
| `SCRIPT FLUSH` | 清空所有缓存脚本 |
| `SCRIPT KILL` | 终止正在执行的脚本（需谨慎） |

---

## 十二、Lua 脚本的限制

### 1. 沙箱环境

Redis Lua 脚本运行在**沙箱**中，目的：保护 Redis 服务端不被脚本影响。

```text
┌─────────────────────────────────────────────────────────────┐
│              Redis Lua 沙箱限制                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ✗ 不允许:                                                  │
│   - 访问全局变量(除 redis.call / redis.pcall / redis.error_reply / redis.status_reply / redis.log 等)│
│   - 调用 OS 函数(io.open / os.execute 等)                  │
│   - 引用外部 Lua 库(require "socket")                       │
│   - 修改全局 Lua 表(debug.getinfo 等)                      │
│   - 使用 yield/coroutine (Redis 5 前不允许)                 │
│                                                             │
│  ✓ 允许:                                                    │
│   - redis.call('command', ...)                             │
│   - redis.pcall('command', ...)   (错误不抛)                │
│   - redis.error_reply(msg)  返回错误                        │
│   - redis.status_reply(msg)  返回状态                        │
│   - redis.log(level, msg)    写日志                         │
│   - redis.sha1hex(...)       计算 SHA1                      │
│   - redis.replicate_commands() (5.0+)                      │
│   - 基本 Lua 库(string, table, math, cjson, cmsgpack)    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2. 关键限制示例

```lua
-- 不允许:访问全局变量
print("hello")        -- 错误:attempt to call a nil value (global 'print')

-- 不允许:OS 函数
os.execute("rm -rf /")  -- 错误:attempt to call a nil value (global 'os')

-- 不允许:外部库
local socket = require("socket")  -- 错误:module 'socket' not found

-- 允许:redis.call
local val = redis.call('GET', KEYS[1])

-- 允许:数学运算
local sum = tonumber(ARGV[1]) + tonumber(ARGV[2])
```

### 3. 集群下的 key 限制

**Redis Cluster 中，Lua 脚本必须操作的 key 在同一个 slot**（除非开启 `redis.cluster` 模式或使用 hash tag）。

```bash
# 假设 slot 计算:
#   {user:1000}.profile -> slot 1234
#   {user:1000}.balance -> slot 1234   (同一 hash tag,同 slot)
#   user:2000.profile  -> slot 5678

# OK:同一 slot
> EVAL "..." 2 {user:1000}.profile {user:1000}.balance

# 错误:跨 slot
> EVAL "..." 2 user:1000.profile user:2000.balance
CROSSSLOT Keys in request don't hash to the same slot
```

**解决方案**：

```bash
# 使用 hash tag `{...}` 强制同 slot
> EVAL "..." 2 {user:1000}.profile {user:1000}.balance
```

### 4. 脚本执行时间限制

Redis 默认对 Lua 脚本的执行时间有限制（默认 5 秒），超时会被 `SCRIPT KILL` 终止。

```bash
# redis.conf
lua-time-limit 5000   # 单位毫秒
```

> **生产建议**：Lua 脚本必须快速执行，避免复杂循环和长耗时操作。

---

## 十三、常用 Lua 脚本实战

### 1. 限流器：令牌桶

```lua
-- token_bucket.lua
-- 实现令牌桶限流
-- KEYS[1]: 桶 key
-- ARGV[1]: 桶容量
-- ARGV[2]: 填充速率 (每秒)
-- ARGV[3]: 当前请求消耗的令牌数
-- 返回: 1 成功, 0 失败 (令牌不足)

local bucket_key = KEYS[1]
local capacity = tonumber(ARGV[1])
local rate = tonumber(ARGV[2])
local requested = tonumber(ARGV[3])

-- 读取当前桶状态
local bucket = redis.call('HMGET', bucket_key, 'tokens', 'last_refill')
local tokens = tonumber(bucket[1]) or capacity
local last_refill = tonumber(bucket[2]) or 0

-- 计算当前时间(秒)
local now = redis.call('TIME')[1]

-- 补充令牌
local elapsed = now - last_refill
local refill = elapsed * rate
tokens = math.min(capacity, tokens + refill)

-- 检查令牌是否足够
if tokens >= requested then
    tokens = tokens - requested
    redis.call('HMSET', bucket_key, 'tokens', tokens, 'last_refill', now)
    redis.call('EXPIRE', bucket_key, 3600)
    return 1
else
    redis.call('HMSET', bucket_key, 'tokens', tokens, 'last_refill', now)
    redis.call('EXPIRE', bucket_key, 3600)
    return 0
end
```

**Python 调用**：

```python
import redis

r = redis.Redis()
sha = r.script_load(open('token_bucket.lua').read())

def allow_request(user_id, capacity=100, rate=10, requested=1):
    """检查是否允许请求"""
    bucket_key = f'rate:{user_id}'
    return r.evalsha(sha, 1, bucket_key, capacity, rate, requested) == 1
```

### 2. 限流器：滑动窗口

```lua
-- sliding_window.lua
-- 滑动窗口限流
-- KEYS[1]: 窗口 key
-- ARGV[1]: 窗口大小 (秒)
-- ARGV[2]: 阈值 (窗口内最大请求数)
-- ARGV[3]: 当前时间戳 (秒)
-- 返回: 1 通过, 0 拒绝

local key = KEYS[1]
local window = tonumber(ARGV[1])
local threshold = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

-- 清理过期记录
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)

-- 当前窗口内请求数
local count = redis.call('ZCARD', key)

if count < threshold then
    -- 记录本次请求
    redis.call('ZADD', key, now, now .. ':' .. count)
    redis.call('EXPIRE', key, window + 1)
    return 1
else
    return 0
end
```

### 3. 分布式锁安全释放

**问题**：分布式锁的 `unlock` 操作必须是 `GET` + `DEL` 原子操作，否则可能误删别人的锁。

```lua
-- safe_unlock.lua
-- 安全释放分布式锁
-- 只有当 value 匹配时才删除
-- KEYS[1]: 锁 key
-- ARGV[1]: 锁的 value (唯一标识)
-- 返回: 1 释放成功, 0 锁不属于自己

local key = KEYS[1]
local expected_value = ARGV[1]

local current = redis.call('GET', key)
if current == expected_value then
    redis.call('DEL', key)
    return 1
else
    return 0
end
```

**Python 完整示例**：

```python
import redis
import uuid
import time

r = redis.Redis()

ACQUIRE_LUA = """
return redis.call('SET', KEYS[1], ARGV[1], 'NX', 'PX', ARGV[2])
"""

RELEASE_LUA = """
local current = redis.call('GET', KEYS[1])
if current == ARGV[1] then
    return redis.call('DEL', KEYS[1])
else
    return 0
end
"""

acquire_sha = r.script_load(ACQUIRE_LUA)
release_sha = r.script_load(RELEASE_LUA)

class DistributedLock:
    def __init__(self, key, expire_ms=30000):
        self.key = key
        self.expire_ms = expire_ms
        self.value = str(uuid.uuid4())

    def acquire(self):
        result = r.evalsha(acquire_sha, 1, self.key, self.value, self.expire_ms)
        return result is not None

    def release(self):
        return r.evalsha(release_sha, 1, self.key, self.value) == 1

# 使用
lock = DistributedLock('lock:order:123')
if lock.acquire():
    try:
        # 业务逻辑
        process_order()
    finally:
        lock.release()  # 只释放自己的锁
```

### 4. 自增限流

```lua
-- increment_limit.lua
-- 自增限流(简单计数)
-- KEYS[1]: 计数器 key
-- ARGV[1]: 阈值
-- ARGV[2]: 过期时间 (秒)
-- 返回: 1 允许, 0 拒绝

local key = KEYS[1]
local threshold = tonumber(ARGV[1])
local ttl = tonumber(ARGV[2])

local current = redis.call('INCR', key)
if current == 1 then
    redis.call('EXPIRE', key, ttl)
end

if current > threshold then
    return 0
end
return 1
```

### 5. 库存预扣减

```lua
-- presub_stock.lua
-- 库存预扣减(带版本号)
-- KEYS[1]: 库存 key
-- ARGV[1]: 扣减数量
-- ARGV[2]: 期望版本号 (可选,0 表示不检查)
-- 返回: {新库存, 错误码}
--   错误码: 0 成功, 1 库存不足, 2 版本过期

local stock_key = KEYS[1]
local qty = tonumber(ARGV[1])
local expected_version = tonumber(ARGV[2])

-- 读取库存和版本
local stock = tonumber(redis.call('GET', stock_key) or '0')
local version = tonumber(redis.call('GET', stock_key .. ':ver') or '0')

-- 检查版本
if expected_version > 0 and version ~= expected_version then
    return {stock, 2}
end

-- 检查库存
if stock < qty then
    return {stock, 1}
end

-- 扣减
local new_stock = redis.call('DECRBY', stock_key, qty)
redis.call('INCR', stock_key .. ':ver')

return {new_stock, 0}
```

---

## 十四、Function（Redis 7+ 新特性）

### 1. 什么是 Function

Redis 7.0 引入 **Function** 概念，允许用户定义**持久化的 Lua 脚本函数**，保存在 Redis 数据库中，可像普通命令一样调用。

```text
┌─────────────────────────────────────────────────────────────┐
│              Function  vs  Lua 脚本                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  传统 Lua 脚本 (EVAL):                                      │
│   - 每次调用都要传脚本内容(或 SHA1)                           │
│   - 脚本只在内存缓存,重启丢失                                 │
│   - 重启后第一次需要重新 LOAD                                 │
│                                                             │
│  Function (Redis 7+):                                       │
│   - 脚本持久化到 RDB/AOF                                    │
│   - 通过 FCALL 调用,无需 LOAD                              │
│   - 支持库管理(FUNCTION LOAD/DELETE/LIST)                  │
│   - 与集群集成更好                                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2. Function 生命周期

```bash
# 1. 创建函数库
FUNCTION LOAD "#!lua name=mylib
redis.register_function('myadd', function(keys, args)
    return tonumber(args[1]) + tonumber(args[2])
end)
"

# 2. 调用函数
> FCALL myadd 0 10 20
(integer) 30

# 3. 列出所有函数
> FUNCTION LIST
1) "name"

# 4. 删除函数
FUNCTION DELETE mylib

# 5. 替换函数
FUNCTION FLUSH
```

### 3. 完整示例

```lua
-- 用户自定义函数库,保存到 mylib.lua
redis.register_function('transfer', function(keys, args)
    local src = keys[1]
    local dst = keys[2]
    local amount = tonumber(args[1])

    local src_balance = tonumber(redis.call('GET', src) or '0')
    if src_balance < amount then
        return redis.error_reply('insufficient balance')
    end

    redis.call('DECRBY', src, amount)
    redis.call('INCRBY', dst, amount)
    return 'OK'
end)

redis.register_function('myrange', function(keys, args)
    local min = tonumber(args[1])
    local max = tonumber(args[2])
    local result = {}
    for i = min, max do
        table.insert(result, redis.call('GET', keys[1] .. ':' .. i))
    end
    return result
end)
```

```bash
# 加载
> FUNCTION LOAD "$(cat mylib.lua)"

# 调用
> FCALL transfer 2 user:1:balance user:2:balance 100
"OK"

> FCALL myrange 2 prefix 1 3
1) "a"
2) "b"
3) "c"
```

### 4. EVAL 与 Function 对比

| 维度 | EVAL/EVALSHA | FUNCTION |
|------|------|------|
| 引入版本 | 2.6 | 7.0 |
| 持久化 | 否（重启需重 LOAD） | 是（写入 RDB/AOF） |
| 加载方式 | SCRIPT LOAD | FUNCTION LOAD |
| 调用方式 | EVALSHA / EVAL | FCALL / FCALL_RO |
| 集群支持 | 受限（同 slot） | 更好 |
| 集群复制 | 不复制 | 可同步 |
| 库管理 | 无 | FUNCTION LIST/DELETE |

> **建议**：Redis 7+ 优先使用 Function 替代 EVAL。

---

## 十五、Cluster 中 Lua 脚本的限制

### 1. 单 key 限制

**Redis Cluster 中，Lua 脚本默认要求所有 key 在同一个 slot**。

```bash
# 假设 redis-cli --cluster 计算:
#   user:1000 -> slot 1234
#   user:2000 -> slot 5678

# 错误:跨 slot
> EVAL "redis.call('GET', KEYS[1]); return redis.call('GET', KEYS[2])" 2 user:1000 user:2000
CROSSSLOT Keys in request don't hash to the same slot
```

### 2. 解决方案：Hash Tag

使用 `{tag}` 强制多个 key 在同一 slot：

```bash
# 强制同 slot
> EVAL "..." 2 {user:1000}.name {user:1000}.balance

# 计算方法:CRC16('{user:1000}.name') = CRC16('user:1000') (只取 {} 第一个内部部分)
```

### 3. 节点路由

```text
┌─────────────────────────────────────────────────────────────┐
│         Cluster 中 Lua 脚本的执行路径                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  客户端              集群节点                                │
│  ┌────────┐         ┌──────────┐                            │
│  │ EVAL   │ ──────► │ 节点 A    │  ← 接收命令               │
│  │ script │         │ 解析     │                            │
│  │ 2 keys │         │ 检查 keys│                            │
│  └────────┘         │ 都在本  │                            │
│                    │ 节点?   │                              │
│                    │ ┌────┐  │                              │
│                    │ │是的│  │                              │
│                    │ └──┬─┘  │                              │
│                    │    ▼     │                              │
│                    │ 执行脚本 │                              │
│                    │ 返回结果 │                              │
│                    └──────────┘                              │
│                                                             │
│  问题: keys 跨节点怎么办?                                    │
│  答: 必须在客户端用 hash tag 强制同 slot,                     │
│     或在 Redis 7+ 使用 Redis OSS 7 的 *_RO 跨节点 *         │
└─────────────────────────────────────────────────────────────┘
```

### 4. 复制一致性

Redis Lua 脚本默认通过 **复制(replication)** 同步到从节点，但要注意：

```text
┌─────────────────────────────────────────────────────────────┐
│          脚本执行 vs 复制的原子性                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  默认行为 (Redis 5.0 前):                                    │
│   - 脚本执行后,以"单条命令"形式发送到从节点                   │
│   - 脚本与复制可能不一致                                      │
│                                                             │
│  Scripts effects replication (Redis 5.0+):                  │
│   - 脚本执行的影响被记录                                      │
│   - 由从节点重放,保证主从一致                                │
│   - 使用 redis.replicate_commands() 启用                    │
│                                                             │
│  集群下:                                                    │
│   - Function 默认会随集群配置同步                             │
│   - EVAL 脚本需要手动确保所有节点都有                         │
└─────────────────────────────────────────────────────────────┘
```

---

## 十六、事务 vs Lua vs Pipeline 对比

### 1. 三者特性对比

| 维度 | 事务 (MULTI/EXEC) | Lua 脚本 | Pipeline (管道) |
|------|-------------------|---------|----------------|
| 原子性 | EXEC 内原子 | 脚本整体原子 | 无 |
| 隔离性 | EXEC 期间串行 | 脚本期间串行 | 无 |
| 错误处理 | 运行时错误继续 | 脚本控制 | 各自独立 |
| 网络往返 | 4 次 (MULTI+命令+EXEC) | 1 次 | 1 次 |
| 复杂度 | 简单命令 | 复杂逻辑 | 批量命令 |
| 性能 | 中 | 高 | 高 |
| 适用场景 | 简单原子批操作 | 复杂原子逻辑 | 减少 RTT |
| 可读性 | 高 | 中 | 中 |
| 错误恢复 | 客户端重试 | 脚本返回错误 | 客户端判断 |

### 2. 详细对比表

```text
┌──────────────────────────────────────────────────────────────────┐
│              事务 vs Lua vs Pipeline 深度对比                      │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  特性              MULTI/EXEC       Lua 脚本       Pipeline     │
│  ─────────────────────────────────────────────────────────────  │
│  命令序列化        是(三段式)       是(单脚本)     是(批量)      │
│  服务端原子执行    是(EXEC 期间)   是(整个脚本)   否             │
│  命令间隔离        是              是              否             │
│  减少网络往返      中(3+1)         高(1)          高(1)         │
│  支持分支逻辑      否              是              否             │
│  错误回滚          否              脚本控制         否             │
│  性能(简单批)     中              高             高             │
│  性能(复杂逻辑)   低              高             低             │
│  集群兼容          跨 slot 受限    跨 slot 受限    跨节点 OK      │
│  维护成本          低              中             低             │
│  调试难度          低              中(无断点)      低             │
│                                                                  │
│  选型建议:                                                       │
│   - 简单批量原子 → MULTI/EXEC                                   │
│   - 复杂逻辑原子 → Lua 脚本                                     │
│   - 仅需减少 RTT → Pipeline                                     │
│   - 复杂场景 → Lua 脚本 (首选)                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 3. 性能基准参考

```text
┌─────────────────────────────────────────────────────────────┐
│            性能基准 (10 万次操作,RTT 1ms)                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  方案                        耗时       吞吐量               │
│  ─────────────────────────────────────────────────────────  │
│  普通 GET 1000 次          1000ms     1000 ops/s            │
│  Pipeline 1000 GET         100ms      10000 ops/s           │
│  MULTI/EXEC 1000 命令      120ms      8333 ops/s            │
│  Lua 脚本 (1000 次自增)    105ms      9524 ops/s            │
│  Lua 脚本 (复杂逻辑)        200ms      5000 ops/s            │
│                                                             │
│  结论:                                                       │
│   - 简单操作 Lua 与 Pipeline 接近                            │
│   - 复杂逻辑 Lua 优势明显                                     │
│   - 事务开销略高于 Pipeline                                   │
└─────────────────────────────────────────────────────────────┘
```

### 4. 选型决策树

```text
┌─────────────────────────────────────────────────────────────┐
│              事务/Lua/Pipeline 选型决策                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  需要服务端原子执行?                                          │
│  ├─ 否 → Pipeline                                           │
│  └─ 是                                                       │
│     ├─ 逻辑简单(2-3 个命令)                                  │
│     │  ├─ 不需要乐观锁 → MULTI/EXEC                          │
│     │  └─ 需要乐观锁 → WATCH + MULTI/EXEC                    │
│     ├─ 逻辑复杂(条件判断、循环)                              │
│     │  ├─ Redis 7+ → Function / FCALL                       │
│     │  ├─ Redis 6 及以下 → EVAL / EVALSHA                    │
│     └─ 性能要求极高 + 逻辑简单 → MULTI/EXEC                 │
│                                                             │
│  集群场景:                                                    │
│   - 所有方案均受 key 必须同 slot 限制                         │
│   - 使用 hash tag {xxx} 强制同 slot                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 十七、生产实践建议

### 1. 事务使用建议

```text
┌─────────────────────────────────────────────────────────────┐
│              Redis 事务生产实践                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. 优先使用 Lua 脚本                                        │
│     - 性能更好,原子性更强,代码更清晰                          │
│                                                             │
│  2. 谨慎使用 WATCH                                            │
│     - 高并发场景下重试率高                                     │
│     - 必须设置重试上限,避免死循环                              │
│     - 业务代码必须幂等                                        │
│                                                             │
│  3. 避免大事务                                                │
│     - 事务队列不宜过长(< 1000 条)                            │
│     - 大事务阻塞单线程,影响所有客户端                          │
│                                                             │
│  4. 关注错误处理                                              │
│     - 运行时错误不会回滚,客户端必须检测结果                     │
│     - 语法错误会导致整个事务放弃                                │
│                                                             │
│  5. 事务不替代关系数据库事务                                   │
│     - 核心业务(转账、支付)仍用 MySQL 事务                     │
│     - Redis 事务用于缓存、计数、限流等                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2. Lua 脚本使用建议

```text
┌─────────────────────────────────────────────────────────────┐
│              Lua 脚本生产实践                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. 脚本必须快速                                              │
│     - 复杂度: O(1) 或 O(log N)                              │
│     - 避免大循环 (lua-time-limit 默认 5s)                   │
│                                                             │
│  2. 优先使用 EVALSHA                                          │
│     - 节省网络带宽                                            │
│     - 处理 NOSCRIPT 错误                                     │
│                                                             │
│  3. 集中管理脚本                                              │
│     - 统一 SHA1 注册,便于版本管理                             │
│     - 部署时确保所有节点都有脚本                               │
│                                                             │
│  4. 监控脚本执行                                              │
│     - INFO commandstats 各命令计数                            │
│     - redis-cli --latency 检测延迟                            │
│                                                             │
│  5. 集群注意 hash tag                                        │
│     - 同业务 key 用相同 hash tag                              │
│     - 避免跨节点脚本                                          │
│                                                             │
│  6. Redis 7+ 优先用 Function                                │
│     - 持久化存储,自动同步                                     │
│     - 更好的库管理                                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3. 常见反模式

```text
┌─────────────────────────────────────────────────────────────┐
│              需要避免的反模式                                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ✗ 在 Lua 脚本中做长耗时操作                                  │
│     - 大量循环、复杂计算                                       │
│     - 网络 IO(Redis 7+ 有阻塞命令 cjson 等)                  │
│                                                             │
│  ✗ 用 Lua 脚本代替应用层逻辑                                  │
│     - 业务复杂时仍应在应用层                                   │
│     - Lua 适合简单原子操作                                    │
│                                                             │
│  ✗ 忽视 NOSCRIPT 错误                                        │
│     - 集群重启后 EVALSHA 失败                                │
│     - 必须实现回退机制                                        │
│                                                             │
│  ✗ 在事务中使用带有随机性/时间性的命令                        │
│     - Redis 5.0 后支持,但要小心                              │
│     - RANDOMKEY / TIME 等                                   │
│                                                             │
│  ✗ 滥用 WATCH                                                │
│     - 高并发下大部分请求会因为冲突失败                          │
│     - 改用 Lua 脚本或分布式锁                                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 十八、调试与监控

### 1. 调试 Lua 脚本

```bash
# 1. 使用 redis.log 记录日志
> EVAL "redis.log(redis.LOG_NOTICE, 'key value: ' .. ARGV[1]); return 1" 0 test
1
# 日志输出:/var/log/redis/redis.log

# 2. 使用 redis-cli --ldb 调试
redis-cli --ldb --eval test.lua key1 , arg1
# 进入 Lua 调试器,支持断点、单步

# 3. 返回调试信息
> EVAL "return {redis.call('GET', KEYS[1]), redis.call('TTL', KEYS[1])}" 1 mykey
```

### 2. 监控指标

```bash
# 1. 命令统计
> INFO commandstats
#cmdstat_evalsha:calls=10000,usec=500000,usec_per_call=50.00,rejected_calls=0,failed_calls=0

# 2. 慢查询
> SLOWLOG GET 10
# 显示最近 10 条慢查询

# 3. 内存使用
> INFO memory
# used_memory_lua:Lua 引擎占用的内存

# 4. 客户端连接
> CLIENT LIST
# 查看当前连接的客户端信息
```

### 3. 慢 Lua 脚本定位

```bash
# redis.conf
slowlog-log-slower-than 10000   # 10ms

# 找到慢脚本
> SLOWLOG GET
1) 1) (integer) 100
   2) (integer) 1234567890
   3) (integer) 50000
   4) 1) "EVAL"
      2) "for i=1,100000 do redis.call('GET', KEYS[1]) end"
      5) "127.0.0.1:54321"
```

---

## 十九、与其他机制的关系

### 1. 事务与持久化

```text
┌─────────────────────────────────────────────────────────────┐
│           事务与持久化的关系                                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  事务执行:                                                   │
│   - 数据写入内存 ✓                                           │
│   - 标记 AOF 缓冲 ✓                                          │
│   - 立即 fsync? ✗ (默认)                                    │
│                                                             │
│  是否持久化由 AOF 策略决定:                                   │
│   - appendfsync always:    每条命令都 fsync(慢)              │
│   - appendfsync everysec:  每秒 fsync(默认,可能丢 1s)        │
│   - appendfsync no:        OS 自行决定(可能丢更多)            │
│                                                             │
│  事务无法保证"提交即持久化"                                   │
│  强持久化需求:考虑 WAIT 命令                                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2. 事务与发布订阅

```text
┌─────────────────────────────────────────────────────────────┐
│           事务与 Pub/Sub 的关系                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  - 事务中的 PUBLISH 命令会在 EXEC 时执行                      │
│  - 订阅者会在 EXEC 之后收到消息                               │
│  - 与事务外的 PUBLISH 表现一致                                │
│                                                             │
│  注意: 事务不能用于"延迟发布"或"条件发布"                     │
│       事务中的命令全部原子执行,无中间状态                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3. 事务与 Stream

```text
┌─────────────────────────────────────────────────────────────┐
│           事务与 Stream 的关系                                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Stream 提供消费者组机制:                                     │
│   - 消息确认 (XACK) 可以放进事务中                            │
│   - 读取消息 (XREADGROUP) 也可以                             │
│                                                             │
│  但 Stream 已经有自己的"原子性":                              │
│   - XADD 写入原子                                           │
│   - XREADGROUP 读取原子                                     │
│                                                             │
│  实际场景:                                                   │
│   - 消费消息 + 业务处理 + 确认 → 通常用 Lua 脚本               │
│   - 简化: 只需 XREAD + XACK,可分两步                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 二十、核心要点速记

### 1. 事务核心要点

```text
┌─────────────────────────────────────────────────────────────┐
│              Redis 事务 5 大要点                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. 三大命令: MULTI 入队,EXEC 执行,DISCARD 取消              │
│  2. WATCH/UNWATCH 提供乐观锁,EXEC 失败需重试                  │
│  3. 不支持回滚:语法错误放弃事务,运行错误继续执行               │
│  4. 原子性局限:EXEC 时所有命令原子,但失败不会回滚             │
│  5. 单线程执行:天然串行隔离,不需要锁机制                       │
│                                                             │
│  适用: 简单原子批操作,无回滚需求的场景                         │
│  局限: 复杂逻辑不适合,高并发推荐 Lua 脚本                      │
└─────────────────────────────────────────────────────────────┘
```

### 2. Lua 脚本核心要点

```text
┌─────────────────────────────────────────────────────────────┐
│              Lua 脚本 8 大要点                                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. 原子性:脚本执行期间不可插入其他命令                        │
│  2. 减少网络往返:一次 EVAL/EVALSHA 解决复杂逻辑               │
│  3. SHA1 缓存:EVALSHA 节省带宽,处理 NOSCRIPT 错误            │
│  4. 沙箱限制:不能访问全局变量、OS、OS 库                      │
│  5. 集群限制:key 必须在同 slot,使用 hash tag {xxx}           │
│  6. 复杂度低:避免长循环,默认超时 5s                          │
│  7. Redis 7+:优先用 Function 替代 EVAL                      │
│  8. 集群复制:Function 同步,LUASCRIPT 需手动同步              │
│                                                             │
│  适用: 限流、分布式锁、库存扣减、计数器、复杂原子操作           │
└─────────────────────────────────────────────────────────────┘
```

### 3. 决策速查表

```text
┌─────────────────────────────────────────────────────────────┐
│              选型速查表                                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  场景                            推荐方案                  │
│  ─────────────────────────────────────────────────────────  │
│  简单批量 SET                    Pipeline                  │
│  原子计数(GET + INCR + EXPIRE)  Lua 脚本                  │
│  分布式锁释放                    Lua 脚本 (GET + DEL 原子)  │
│  限流                            Lua 脚本 (令牌桶/滑动窗口) │
│  库存扣减                        Lua 脚本 (CAS + 标记)     │
│  抢票秒杀                        Lua 脚本                  │
│  排行榜更新                      Lua 脚本 (ZADD 批量)      │
│  异步队列消费                    Lua 脚本 (XREADGROUP + XACK)│
│  简单原子批操作                  MULTI/EXEC                │
│  需要乐观锁(简单场景)            WATCH + MULTI/EXEC        │
│  Redis 7+ 持久化函数             Function / FCALL         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 4. 关键命令速查

| 命令 | 作用 | 备注 |
|------|------|------|
| `MULTI` | 开启事务 | 后续命令入队 |
| `EXEC` | 执行事务 | 返回结果数组 |
| `DISCARD` | 取消事务 | 清空队列 |
| `WATCH key` | 监视 key | 乐观锁 |
| `UNWATCH` | 取消监视 | |
| `EVAL script k a` | 执行 Lua | 完整脚本 |
| `EVALSHA sha k a` | 通过 SHA1 执行 | 需先加载 |
| `SCRIPT LOAD` | 加载脚本 | 返回 SHA1 |
| `SCRIPT EXISTS` | 检查脚本 | |
| `SCRIPT FLUSH` | 清空脚本 | |
| `FUNCTION LOAD` | 加载函数 (Redis 7+) | 持久化 |
| `FCALL fname k a` | 调用函数 (Redis 7+) | |

### 5. 关键参数

```bash
# redis.conf 关键参数
lua-time-limit 5000          # Lua 脚本最大执行时间 (ms)
slowlog-log-slower-than 10000 # 慢查询阈值 (μs, 10000 = 10ms)
```

### 6. 一句话总结

> **Redis 事务**是简单的原子批操作机制，但**不提供回滚**；**Lua 脚本**是更强大的原子性方案，几乎是生产环境的首选；**Pipeline** 只是减少 RTT，不提供原子性。集群场景下三者都需用 hash tag 保证 key 同 slot。Redis 7+ 的 Function 是 Lua 脚本的"升级版"，推荐优先使用。

---

## 附录：常见错误码

| 错误 | 含义 | 解决 |
|------|------|------|
| `NOSCRIPT` | 脚本未加载 | SCRIPT LOAD 或 fallback 到 EVAL |
| `EXECABORT Transaction discarded` | 事务因命令错误被放弃 | 重新组装命令 |
| `CROSSSLOT Keys in request don't hash to the same slot` | 跨 slot | 使用 hash tag |
| `BUSYKEY Redis is busy running a script` | 上一个脚本未结束 | 等待或 SCRIPT KILL |
| `TRYAGAIN` | Redis cluster 重试 | 客户端自动重试 |
| `MOVED` | key 在其他节点 | 客户端路由 |
| `WRONGTYPE` | key 类型错误 | 业务修正 |
| `OOM command not allowed when used memory > 'maxmemory'` | 内存满 | 清理或扩容 |

---

## 附录：参考资源

- Redis 官方文档: https://redis.io/docs/interact/programmability/
- Redis EVAL 文档: https://redis.io/commands/eval/
- Redis Functions 文档: https://redis.io/docs/manual/programmability/functions-intro/
- Redis 事务文档: https://redis.io/docs/manual/transactions/
- 《Redis 设计与实现》- 黄健宏
- 《Redis 深度历险：核心原理与应用实践》- 钱文品
