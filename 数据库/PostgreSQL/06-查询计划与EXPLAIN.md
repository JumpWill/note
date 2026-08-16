# PostgreSQL 查询计划与 EXPLAIN

> PostgreSQL 是高度可观测的数据库——它不仅告诉你执行计划,还会**真正执行 SQL 后告诉你实际耗时**。本章系统讲解 EXPLAIN 工具、节点类型、成本估算、统计信息、缓冲区分析,以及 10+ 个生产级 SQL 优化实战案例。

## 一、查询处理总览

### 1. 一条 SQL 的完整生命周期

PostgreSQL 处理一条 SQL 经历 5 个阶段,与 MySQL 大同小异,但**优化器能力更强**(基于成本的 GEQO + 遗传算法、遗传查询优化、CTE 内联等)。

```text
┌─────────────────────────────────────────────────────────────────────┐
│              PostgreSQL 一条 SQL 的完整处理流程                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   客户端                                                            │
│     │                                                               │
│     ▼                                                               │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐       │
│  │ 解析器   │───▶│ 重写器   │───▶│ 优化器   │───▶│ 执行器   │       │
│  │ Parser   │    │ Rewriter │    │ Planner  │    │ Executor │       │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘       │
│       │             │              │              │                │
│       ▼             ▼              ▼              ▼                │
│    语法树       规则改写后       执行计划        物理算子            │
│    parse tree   的 Query tree   (Plan Tree)   (节点迭代执行)        │
│                                                │                   │
│                                                ▼                   │
│                                            结果集                  │
└─────────────────────────────────────────────────────────────────────┘
```

### 2. 五个阶段详解

#### (1) 解析器(Parser)

基于 **Lex + Yacc**(词法 + 语法分析),生成 **parse tree**。

```sql
-- 示例 SQL
SELECT name FROM user WHERE age > 18;

-- parse tree(简化)
{
  stmt: SelectStmt
  targetList: [{ column_ref: name }]
  fromClause: [{ range_var: user }]
  whereClause: {
    a_expr: {
      expr: > (op)
      args: [column_ref(age), literal(18)]
    }
  }
}
```

#### (2) 重写器(Rewriter)

应用 **规则系统(Rule System)**,主要是 **视图展开**、**IN 子查询转半连接** 等。

```sql
-- 视图定义
CREATE VIEW active_user AS SELECT * FROM user WHERE status = 1;

-- 用户写
SELECT * FROM active_user WHERE age > 18;

-- 重写后等价于
SELECT * FROM user WHERE status = 1 AND age > 18;
```

#### (3) 优化器(Planner / Optimizer)★★

PostgreSQL 优化器是 **纯 CBO(Cost-Based Optimizer)**,无 RBO 兜底。

```text
优化器的核心工作:
  1. 逻辑优化(Logical Optimization)
     - 谓词下推(Predicate Pushdown)
     - 子查询提升 / 改写
     - 外连接消除
     - 等价谓词简化
     - CTE 内联(PG 12+)
     - 表达式预处理
  2. 物理优化(Physical Optimization)
     - 单表访问路径:Seq Scan / Index Scan / Index Only Scan / Bitmap Scan
     - 多表 JOIN 算法:Nested Loop / Hash Join / Merge Join
     - 排序:Sort Node / 索引有序读取
     - 聚合:HashAggregate / GroupAggregate
  3. 代价估算(Cost Estimation)
     - 基于 pg_stats 统计信息
     - 候选路径枚举 + 动态规划 / GEQO(遗传算法,表数 > 12 时)
     - 选 cost 最小的 plan
```

**PostgreSQL 与 MySQL 优化器差异**:

| 维度 | PostgreSQL | MySQL |
|------|------------|-------|
| 优化器类型 | **纯 CBO** | CBO + 部分 RBO |
| 遗传优化(GEQO) | **支持**(表数 ≥ 12 触发) | 不支持 |
| CTE 内联 | PG 12+ 自动 | 8.0 有限支持 |
| 部分索引 | 支持 | 不支持 |
| 表达式索引 | 支持 | 8.0+ 支持 |
| 自定义函数代价 | 提供接口 | 无 |
| 规划稳定性 | 不稳定(PREPARE 可缓解) | 较稳定 |

#### (4) 执行器(Executor)

PostgreSQL 采用 **火山模型(Volcano Model)**,每个节点实现三招:

```c
// 节点接口(三方法)
ExecInitNode()   // 初始化
ExecProcNode()   // 取下一行
ExecEndNode()    // 清理
```

```text
执行器流程:
   ┌──────────────────────┐
   │ Top Node (Limit/...) │
   └──────────┬───────────┘
              │ 拉一行
              ▼
   ┌──────────────────────┐
   │ 子节点 (Sort/...)     │  ← pull-based
   └──────────┬───────────┘
              │
              ▼
   ┌──────────────────────┐
   │ 叶子 (Seq/Index ...) │
   └──────────────────────┘
```

#### (5) 结果返回

- **Materialize 节点**:把子节点结果缓存,避免重复计算
- **GUC 缓冲**:`work_mem`、`shared_buffers` 控制
- **网络传输**:PG 协议(基于消息),批量发送

### 3. 性能问题的常见分布

```text
PostgreSQL 性能问题分布(经验值):

        应用代码问题       ███           5%
        架构设计问题       ██████        15%
        索引设计问题       ████████████  30%   ← ★ 高频
        SQL 写法问题       ██████████    25%   ← ★ 高频
        统计信息过期       ██████        15%   ← ★ PostgreSQL 特有
        参数配置问题       ███           5%
        硬件问题           ██            5%
```

**PostgreSQL 相比 MySQL 更常见的性能问题**:统计信息过期(因为 autovacuum 阈值需要调优)。

---

## 二、EXPLAIN 命令详解

### 1. EXPLAIN 的三种形式

```sql
-- 1. EXPLAIN:仅估算(不执行)
EXPLAIN SELECT * FROM user WHERE id = 100;

-- 2. EXPLAIN ANALYZE:真正执行,返回实际数据
EXPLAIN ANALYZE SELECT * FROM user WHERE id = 100;

-- 3. EXPLAIN (选项):定制输出
EXPLAIN (ANALYZE, BUFFERS, VERBOSE, FORMAT JSON)
SELECT * FROM user WHERE id = 100;
```

### 2. EXPLAIN 选项一览

| 选项 | 作用 | 默认 |
|------|------|------|
| **ANALYZE** | 真正执行,返回实际耗时和行数 | FALSE |
| **VERBOSE** | 显示额外列(每个节点输出列名等) | FALSE |
| **COSTS** | 显示启动/总成本 | TRUE |
| **BUFFERS** | 显示缓冲区(共享缓存、本地缓存) | FALSE |
| **TIMING** | 显示每个节点的耗时 | ANALYZE 时默认 TRUE |
| **SUMMARY** | 显示汇总信息(总耗时等) | TRUE |
| **FORMAT** | 输出格式(TEXT/JSON/YAML) | TEXT |
| **WAL** | 显示 WAL 写入(BUFFERS 附带) | FALSE |
| **SETTINGS** | 显示影响计划的非默认 GUC | FALSE |
| **GENERIC_PLAN** | 生成通用计划(不绑定参数) | FALSE |

```sql
-- 常用组合
EXPLAIN (ANALYZE, BUFFERS) SELECT ...;       -- 生产调试
EXPLAIN (ANALYZE, BUFFERS, VERBOSE) SELECT ...;  -- 深度排查
EXPLAIN (FORMAT JSON, ANALYZE) SELECT ...;   -- 程序化处理
EXPLAIN (FORMAT YAML) SELECT ...;            -- 配置工具
EXPLAIN (SETTINGS) SELECT ...;                -- PG 16+ 看哪些参数影响计划
```

### 3. EXPLAIN 输出的基本结构

```sql
EXPLAIN SELECT u.id, u.name, o.amount
FROM user u JOIN "order" o ON u.id = o.user_id
WHERE u.create_dt > '2025-01-01';
```

**输出(TEXT 格式,树形缩进)**:

```text
                                  QUERY PLAN
-------------------------------------------------------------------
 Hash Join  (cost=850.00..1250.00 rows=2000 width=68)
   Hash Cond: (o.user_id = u.id)
   ->  Seq Scan on "order" o  (cost=0.00..300.00 rows=10000 width=16)
   ->  Hash  (cost=620.00..620.00 rows=2000 width=56)
         ->  Bitmap Heap Scan on user u  (cost=120.00..620.00 rows=2000 width=56)
               Recheck Cond: (create_dt > '2025-01-01'::date)
               Filter: (create_dt > '2025-01-01'::date)
               ->  Bitmap Index Scan on idx_user_create_dt  (cost=0.00..115.00 rows=2000 width=0)
                     Index Cond: (create_dt > '2025-01-01'::date)
```

**结构解读**:

```text
每个节点一行(或多行子属性),缩进表示嵌套关系:
  - 父节点在上,子节点在下
  - 越底层(叶子)是数据源
  - 越上层是汇总/输出

执行顺序:
  - 后序遍历(post-order),即叶子先执行
  - 数据从下往上流
```

### 4. 三种 FORMAT 对比

#### (1) TEXT(默认)

适合人工阅读,树形缩进清晰。

```sql
EXPLAIN SELECT * FROM t WHERE id = 1;
```

```text
Index Scan using t_pkey on t  (cost=0.43..8.45 rows=1 width=42)
  Index Cond: (id = 1)
```

#### (2) JSON

适合程序化处理,可被各种 GUI 工具(pev、pgAdmin、explain.dalibo.com)解析。

```sql
EXPLAIN (FORMAT JSON) SELECT * FROM t WHERE id = 1;
```

```json
[
  {
    "Plan": {
      "Node Type": "Index Scan",
      "Index Name": "t_pkey",
      "Relation Name": "t",
      "Startup Cost": 0.43,
      "Total Cost": 8.45,
      "Plan Rows": 1,
      "Plan Width": 42,
      "Index Cond": "id = 1"
    }
  }
]
```

#### (3) YAML

```sql
EXPLAIN (FORMAT YAML) SELECT * FROM t WHERE id = 1;
```

```yaml
- Plan:
    Node Type: "Index Scan"
    Index Name: "t_pkey"
    Relation Name: "t"
    Startup Cost: 0.43
    Total Cost: 8.45
    Plan Rows: 1
    Plan Width: 42
    Index Cond: "id = 1"
```

**JSON 输出的高级字段**(ANALYZE 时):

```json
{
  "Node Type": "Index Scan",
  "Actual Startup Time": 0.025,
  "Actual Total Time": 0.045,
  "Actual Rows": 1,
  "Actual Loops": 1,
  "Shared Hit Blocks": 3,
  "Shared Read Blocks": 0,
  "Shared Dirtied Blocks": 0,
  "Shared Written Blocks": 0
}
```

---

## 三、EXPLAIN 输出解读

### 1. 节点类型总览

```text
PostgreSQL 节点类型分类:

扫描(Scan)
  ├─ Seq Scan                    全表扫描
  ├─ Index Scan                  索引扫描(需要回表)
  ├─ Index Only Scan             覆盖索引扫描
  ├─ Bitmap Index Scan           位图索引扫描(建位图)
  └─ Bitmap Heap Scan            位图堆扫描(按位图回表)
      └─ Tid Scan                CTID 扫描
      └─ Subquery Scan           子查询扫描
      └─ Function Scan           函数扫描
      └─ Values Scan             VALUES 扫描
      └─ CTE Scan                CTE 扫描
      └─ Foreign Scan            外部表扫描
      └─ Custom Scan             自定义扫描(FDW 等)

连接(Join)
  ├─ Nested Loop                 嵌套循环
  ├─ Hash Join                   哈希连接
  └─ Merge Join                  归并连接

排序/聚合
  ├─ Sort                        排序
  ├─ Incremental Sort            增量排序(PG 13+)
  ├─ Group                       GROUP BY
  ├─ HashAggregate               哈希聚合
  ├─ GroupAggregate              分组聚合
  └─ WindowAgg                   窗口函数

集合/输出
  ├─ Limit                       LIMIT
  ├─ Append                      UNION/分区追加
  ├─ MergeAppend                 已排序的合并
  ├─ Unique                      去重
  ├─ Materialize                 物化
  ├─ Memoize                     结果缓存(PG 14+)
  └─ Result                      常量结果
```

### 2. 节点属性详解

每个节点都有以下属性(部分可选):

| 属性 | 含义 | 来源 |
|------|------|------|
| **Node Type** | 节点类型 | EXPLAIN 必有 |
| **Startup Cost** | 启动成本(返回第一行前的成本) | 估算 |
| **Total Cost** | 总成本(返回所有行的成本) | 估算 |
| **Plan Rows** | 估算返回行数 | 估算 |
| **Plan Width** | 每行平均字节数 | 估算 |
| **Actual Startup Time** | 实际启动耗时(ms) | ANALYZE |
| **Actual Total Time** | 实际总耗时(ms) | ANALYZE |
| **Actual Rows** | 实际返回行数 | ANALYZE |
| **Actual Loops** | 节点被调用次数 | ANALYZE |
| **Shared Hit Blocks** | 共享缓存命中块数 | BUFFERS |
| **Shared Read Blocks** | 共享缓存未命中(读盘)块数 | BUFFERS |
| **Shared Dirtied/Written Blocks** | 弄脏/写出的块数 | BUFFERS |
| **Local** | 本地缓冲(临时表) | BUFFERS |
| **Temp Read/Written Blocks** | 临时文件读写 | BUFFERS |

```text
cost 的格式:

   (cost=启动成本..总成本 rows=估算行数 width=每行字节)
          ↑                  ↑         ↑
          │                  │         └─ 平均每行字节(基于 pg_type)
          │                  └─────────── 估算返回行数
          └────────────────────────────── 成本单位(基于 seq_page_cost=1.0)

示例:
   Seq Scan on user (cost=0.00..1500.00 rows=10000 width=42)
                     ^^^^^^^^^^^^^^^^   ^^^^^^   ^^^^^^
                     启动..总成本       10000 行  每行 42 字节
```

### 3. 完整 EXPLAIN ANALYZE 输出解读(案例)

```sql
EXPLAIN (ANALYZE, BUFFERS, VERBOSE, TIMING)
SELECT u.id, u.name, COUNT(o.id) AS order_cnt
FROM user u
LEFT JOIN "order" o ON u.id = o.user_id
WHERE u.create_dt >= '2025-01-01'
GROUP BY u.id, u.name
HAVING COUNT(o.id) > 5
ORDER BY order_cnt DESC
LIMIT 100;
```

```text
                                                                                  QUERY PLAN
──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
 Limit  (cost=1520.50..1520.75 rows=100 width=56) (actual time=85.123..85.234 rows=100 loops=1)
   Output: u.id, u.name, (count(o.id))
   Buffers: shared hit=3500 read=120
   ->  Sort  (cost=1520.50..1520.62 rows=50 width=56) (actual time=85.110..85.200 rows=100 loops=1)
         Output: u.id, u.name, (count(o.id))
         Sort Key: (count(o.id)) DESC
         Sort Method: top-N heapsort  Memory: 35kB
         Buffers: shared hit=3500 read=120
         ->  HashAggregate  (cost=1500.00..1519.00 rows=50 width=56) (actual time=80.500..84.000 rows=2000 loops=1)
               Output: u.id, u.name, count(o.id)
               Group Key: u.id, u.name
               Filter: (count(o.id) > 5)
               Rows Removed by Filter: 8000
               Batches: 1  Memory Usage: 4264kB
               Buffers: shared hit=3500 read=120
               ->  Hash Right Join  (cost=620.00..1450.00 rows=10000 width=24) (actual time=5.230..50.120 rows=25000 loops=1)
                     Output: u.id, u.name, o.id
                     Inner Unique: false
                     Hash Cond: (o.user_id = u.id)
                     Buffers: shared hit=3500 read=120
                     ->  Seq Scan on public."order" o  (cost=0.00..550.00 rows=10000 width=8) (actual time=0.012..20.500 rows=10000 loops=1)
                           Output: o.id, o.user_id
                           Buffers: shared hit=200 read=120
                     ->  Hash  (cost=500.00..500.00 rows=2000 width=20) (actual time=4.500..4.500 rows=2000 loops=1)
                           Output: u.id, u.name
                           Buckets: 4096  Batches: 1  Memory Usage: 195kB
                           Buffers: shared hit=200
                           ->  Bitmap Heap Scan on public.user u  (cost=120.00..500.00 rows=2000 width=20) (actual time=0.500..3.500 rows=2000 loops=1)
                                 Output: u.id, u.name
                                 Recheck Cond: (u.create_dt >= '2025-01-01'::date)
                                 Filter: (u.create_dt >= '2025-01-01'::date)
                                 Rows Removed by Filter: 1000
                                 Heap Blocks: exact=180
                                 Buffers: shared hit=200
                                 ->  Bitmap Index Scan on public.idx_user_create_dt  (cost=0.00..115.00 rows=2000 width=0) (actual time=0.300..0.300 rows=2000 loops=1)
                                       Index Cond: (u.create_dt >= '2025-01-01'::date)
                                       Buffers: shared hit=20
 Planning Time: 1.234 ms
 Execution Time: 85.456 ms
```

**关键字段速查**:

```text
★ Buffers: shared hit=N read=M  ← 缓存命中 N 块,读盘 M 块
★ actual time=X..Y              ← 启动到返回首行..返回所有行
★ rows=N loops=M                ← 每次返回 N 行,执行 M 次
★ Rows Removed by Filter: K     ← 过滤掉 K 行(可优化)
★ Sort Method: top-N heapsort   ← top-N 用堆排序(优于全排序)
★ Memory Usage: 4264kB          ← 哈希占用内存(超 work_mem 会落盘)
★ Planning Time / Execution Time ← 规划耗时 vs 执行耗时
```

### 4. 节点类型详解(对照表)

| 节点类型 | 用途 | 性能 | 何时触发 |
|---------|------|------|---------|
| **Seq Scan** | 全表扫描 | 差 | 无合适索引 / 数据占比大 / 小表 |
| **Index Scan** | 索引扫描(回表) | 较好 | 索引过滤后行数少 |
| **Index Only Scan** | 覆盖索引扫描 | **最优** | SELECT 列都在索引中(visibility map) |
| **Bitmap Index Scan** | 位图索引扫描 | 中 | 多索引 AND/OR / 范围查询 |
| **Bitmap Heap Scan** | 位图堆扫描 | 中 | Bitmap Index Scan 后回表 |
| **Nested Loop** | 嵌套循环 | 中 | 外表小 + 内表有索引 |
| **Hash Join** | 哈希连接 | **较优** | 等值 JOIN,数据量适中 |
| **Merge Join** | 归并连接 | 中 | 两表已排序,数据量大 |
| **Sort** | 排序节点 | 视内存 | 无索引有序时 |
| **HashAggregate** | 哈希聚合 | 优 | GROUP BY 无序输入 |
| **GroupAggregate** | 分组聚合 | **最优** | 输入已按 GROUP KEY 排序 |
| **Incremental Sort** | 增量排序 | 优 | 部分列已排序(PG 13+) |
| **Limit** | 限制返回行数 | 优 | LIMIT N |
| **Append** | 多结果集合并 | 视情况 | UNION / 分区表 / INHERITS |
| **MergeAppend** | 已排序合并 | 优 | 各子节点已排序 |
| **Materialize** | 物化子结果 | 视情况 | 多次扫描子结果时 |
| **Memoize** | 结果缓存 | **优** | 内表重复查询(PG 14+) |
| **Unique** | 去重 | 视情况 | DISTINCT / INTERSECT |
| **Subquery Scan** | 子查询封装 | - | 子查询未优化时 |
| **CTE Scan** | CTE 扫描 | - | 非内联 CTE(PG 11-) |
| **Result** | 常量结果 | **最优** | `SELECT 1`、`SELECT NOW()` |

---

## 四、成本估算(cost)

### 1. cost 是什么

PostgreSQL 的 **cost 是一个抽象单位**,代表**完成该操作消耗的代价**(IO + CPU + 内存)。**不是时间**。

```text
成本基准(默认值):
  seq_page_cost          = 1.0      顺序读一页
  random_page_cost       = 4.0      随机读一页(HDD 时代;SSD 应调低到 1.1)
  cpu_tuple_cost         = 0.01     处理一行
  cpu_index_tuple_cost   = 0.005    处理一个索引项
  cpu_operator_cost      = 0.0025   一个操作符或函数调用

示例:
  Seq Scan 10000 行:
    cost = (pages × 1.0) + (rows × 0.01)
         = 100 + 100   = 200
```

### 2. 启动成本 vs 总成本

```text
(cost=启动成本..总成本)
       ↑              ↑
       │              └── 返回所有行的成本
       └──────────────── 返回第一行的成本(节点特有的初始化开销)

例 1: 排序节点
   Sort (cost=100.00..300.00 rows=1000)
         ↑       ↑
         │       └─ 排完所有 1000 行的成本
         └───────── 第一行出来前的成本(把数据读入内存)

例 2: 嵌套循环
   Nested Loop (cost=0.00..5000.00 rows=1000)
         ↑       ↑
         │       └─ 跑完所有 1000 次循环的成本
         └───────── 第一次循环的成本(读取外表首行)
```

### 3. cost 与实际时间的关系

**cost 不是耗时**,但与耗时正相关。

```text
关系示意:

    估算 cost   =    实际 time   (在统计信息准确的前提下)
    ──────────       ─────────
    相对值          绝对值

PG 不保证 cost 与时间成正比,但如果:
  - 统计信息准(ANALYZE 过)
  - GUC 参数合理
  - 硬件稳定

那么 cost 比例 ≈ 时间比例。
```

**重要**:**cost 不可跨节点直接对比**,但**同节点类型内可对比**。比如"Hash Join cost=500"和"NL cost=500"哪个快?要看场景。

### 4. 估算 vs 实际的偏差

```sql
EXPLAIN ANALYZE SELECT * FROM big_table WHERE col > 1000;
```

```text
Seq Scan on big_table  (cost=0.00..15000.00 rows=100 width=20)
                       (actual time=0.100..850.000 rows=100000 loops=1)

★ 估算 100 行,实际 100000 行 → 偏差 1000 倍
→ 原因:统计信息过期(大量 INSERT 后未 ANALYZE)
→ 解决:ANALYZE big_table;
```

**偏差诊断流程**:

```text
EXPLAIN ANALYZE 输出
       │
       ▼
对比 rows 估算 vs Actual Rows
       │
       ├─ 偏差 < 5 倍   →  正常,继续看 time
       ├─ 偏差 5-50 倍  →  统计信息略有偏差,考虑 ANALYZE
       └─ 偏差 > 50 倍  →  统计信息严重过期,必须 ANALYZE
```

---

## 五、关键节点详解

### 1. Seq Scan(全表扫描)

逐页读表,**最朴素也最被低估的节点**。小表(几十页内)用 Seq Scan **比 Index Scan 快**。

```sql
EXPLAIN SELECT * FROM small_user WHERE id = 1;
```

```text
Seq Scan on small_user  (cost=0.00..1.04 rows=1 width=42)
  Filter: (id = 1)
```

**何时优化器选 Seq Scan**:

```text
1. 表很小(< 8 页)  → Seq 更快,索引反而慢
2. 查询返回大部分行 → 索引回表代价 > Seq
3. 无可用索引       → 唯一选择
4. 索引选择性差     → 优化器认为 Seq 更省
5. random_page_cost 太高(默认 4.0) → 优化器低估索引价值
```

**优化策略**:

```sql
-- 1. 加索引(若没有)
CREATE INDEX idx_user_id ON small_user(id);

-- 2. 强制走索引(测试)
SET enable_seqscan = OFF;  -- 临时关闭
EXPLAIN SELECT * FROM small_user WHERE id = 1;
SET enable_seqscan = ON;   -- 记得恢复

-- 3. 调优 random_page_cost(SSD)
ALTER SYSTEM SET random_page_cost = 1.1;
```

### 2. Index Scan(索引扫描 + 回表)

走索引找主键 / heap tid,**回表取完整行**。

```sql
CREATE INDEX idx_user_name ON user(name);

EXPLAIN SELECT * FROM user WHERE name = '张三';
```

```text
Index Scan using idx_user_name on user  (cost=0.43..8.45 rows=1 width=42)
  Index Cond: (name = '张三')
```

**执行流程**:

```text
       ┌──────────────────────┐
       │  Index Scan           │
       └──────────┬───────────┘
                  │
       ┌──────────▼───────────┐
       │ 1. 在索引树中定位     │  ← O(log N) 几次 IO
       │    name='张三' 的项   │
       └──────────┬───────────┘
                  │
       ┌──────────▼───────────┐
       │ 2. 拿到 heap TID      │
       └──────────┬───────────┘
                  │
       ┌──────────▼───────────┐
       │ 3. 按 TID 回表读完整行 │  ← ★ 一次随机 IO
       └──────────────────────┘
```

**关键开销**:

```text
★ 索引扫描 = 索引树 IO + 回表 IO
★ 回表 IO 是随机 IO(random_page_cost)
★ 行数多时,随机 IO 数量爆炸
```

### 3. Index Only Scan(覆盖索引扫描)

**不需回表**,直接从索引拿所有需要的列。

```sql
CREATE INDEX idx_user_name_age ON user(name, age, create_dt);

EXPLAIN SELECT name, age FROM user WHERE name = '张三';
```

```text
Index Only Scan using idx_user_name_age on user  (cost=0.43..4.45 rows=1 width=14)
  Index Cond: (name = '张三')
  Heap Fetches: 0   ← ★ 不回表
```

**Heap Fetches = 0 的条件**(理想):

```text
1. SELECT 的列都在索引中
2. 索引对应的 heap 行 visibility map 都是 "all visible"
3. VACUUM 跑过(更新 visibility map)
```

**实战**:

```sql
-- 测试是否触发 Heap Fetches
EXPLAIN (ANALYZE, BUFFERS)
SELECT name, age FROM user WHERE name = '张三';

-- 输出:
--   Heap Fetches: 0  ← 理想
--   Heap Fetches: N  ← 需要 VACUUM
```

**触发回表的常见原因**:

```sql
-- 1. SELECT 的列不在索引中
SELECT *, email FROM user WHERE name = '张三';
-- 即使有 idx_name,仍要回表取 * 和 email

-- 2. 索引创建后未 VACUUM
-- visibility map 没更新,Index Only Scan 退化为 Index Scan + Filter
```

### 4. Bitmap Index Scan + Bitmap Heap Scan(位图扫描)

**多条件 OR / AND 时**,PostgreSQL 引入位图机制。

```sql
CREATE INDEX idx_user_create_dt ON user(create_dt);
CREATE INDEX idx_user_status ON user(status);

EXPLAIN SELECT * FROM user WHERE create_dt > '2025-01-01' OR status = 1;
```

```text
Bitmap Heap Scan on user  (cost=120.00..620.00 rows=5000 width=42)
  Recheck Cond: ((create_dt > '2025-01-01'::date) OR (status = 1))
  Filter: ((create_dt > '2025-01-01'::date) OR (status = 1))
  ->  BitmapOr  (cost=0.00..115.00 rows=5000 width=0)
        ->  Bitmap Index Scan on idx_user_create_dt
              Index Cond: (create_dt > '2025-01-01'::date)
        ->  Bitmap Index Scan on idx_user_status
              Index Cond: (status = 1)
```

**位图扫描原理**:

```text
┌──────────────────────────────────────────────────────┐
│ Step 1: Bitmap Index Scan (建位图)                    │
│   - 扫描 idx_user_create_dt,对每个匹配的 heap 页置 1 │
│   - 扫描 idx_user_status,对每个匹配的 heap 页置 1   │
│   - 两者做 OR(放在内存里)                            │
└──────────────────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────┐
│ Step 2: Bitmap Heap Scan (按位图回表)               │
│   - 按位图顺序读取 heap 页(顺序 IO!)                 │
│   - Recheck Cond 验证(因为位图是按页粒度)           │
│   - Filter 应用其余条件                              │
└──────────────────────────────────────────────────────┘

★ 优势:把多次随机 IO 转化为顺序 IO
★ 适用:多条件 OR / 返回中等比例行(10%-30%)
```

**Bitmap Index Scan 的触发场景**:

```text
✓ OR 多个索引条件
✓ AND 多个索引条件(每个返回行多)
✓ 范围 + 等值的组合

✗ 单个等值条件 → 走 Index Scan
✗ 返回行数极少(≤ 1%) → 走 Index Scan
```

**三种扫描对比**:

| 节点 | 适用场景 | IO 模式 | 性能 |
|------|---------|--------|------|
| Seq Scan | 全表 / 小表 / 大范围 | 顺序 IO | 视表大小 |
| Index Scan | 单行 / 极少行(< 1%) | 随机 IO | 优秀 |
| Index Only Scan | SELECT 列都在索引 | 顺序(若 visibility 好) | **最优** |
| Bitmap Index + Heap | 中等多行(10-30%) | 混合(位图后顺序) | 良好 |

### 5. Nested Loop(嵌套循环连接)

**外表每行,触发一次内表查询**。

```sql
EXPLAIN SELECT * FROM user u JOIN "order" o ON u.id = o.user_id;
```

```text
Nested Loop  (cost=0.43..850.00 rows=10000 width=80)
  ->  Index Scan on user u  (cost=0.43..8.45 rows=1 width=42)
        Index Cond: (id = 1)
  ->  Index Scan on "order" o  (cost=0.43..8.45 rows=25 width=38)
        Index Cond: (user_id = 1)
```

**时序图**:

```text
外表(user)         内表(order)
┌─────────┐        ┌─────────────────────────────┐
│ Row 1   │──┐     │ idx_user_id: user_id=1 找  │
│ id=1    │  │     │ 到 25 行                   │
└─────────┘  │     └─────────────────────────────┘
             ▼
        ┌─────────────┐
        │ Join Output │  ← (u.*, o.*) × 25
        └─────────────┘
┌─────────┐
│ Row 2   │──┐
│ id=2    │  │   第二次循环
└─────────┘  ▼
        ┌─────────────┐
        │ Join Output │  ← (u.*, o.*) × N
        └─────────────┘
...
```

**性能公式**:

```text
NL cost = 外表行数 × (内表单行查找 cost)
        = M × N(若内表无索引,需扫全表)
        = M × log(N)(若内表有索引)

★ 外表小 + 内表有索引 → 最快
★ 外表大 + 内表无索引 → 灾难
```

**适用场景**:

```sql
✓ 外表很小(< 1000 行)
✓ 内表有高效索引(主键/唯一索引)
✓ JOIN 字段选择性高
✓ 等值或非等值 JOIN 都可以

✗ 外表很大,内表无索引 → 退化
```

### 6. Hash Join(哈希连接)★★

**对一侧建哈希表,另一侧探测**,O(M + N)。

```sql
EXPLAIN SELECT * FROM user u JOIN "order" o ON u.id = o.user_id;
```

```text
Hash Join  (cost=620.00..1500.00 rows=10000 width=80)
  Hash Cond: (o.user_id = u.id)
  ->  Seq Scan on "order" o  (cost=0.00..550.00 rows=10000 width=38)
  ->  Hash  (cost=500.00..500.00 rows=20000 width=42)
        ->  Seq Scan on user u  (cost=0.00..500.00 rows=20000 width=42)
```

**时序图**:

```text
Phase 1: Build(建哈希表)
┌──────────────────────────────────────────────────┐
│ 内存(work_mem 内)                                │
│ ┌──────────────────────────────────────────┐    │
│ │ Hash Table on user.id                    │    │
│ │ ┌───────┬───────┐                        │    │
│ │ │ id=1  │ u.*   │                        │    │
│ │ ├───────┼───────┤                        │    │
│ │ │ id=2  │ u.*   │                        │    │
│ │ ├───────┼───────┤                        │    │
│ │ │ ...   │ ...   │                        │    │
│ │ └───────┴───────┘                        │    │
│ └──────────────────────────────────────────┘    │
└──────────────────────────────────────────────────┘

Phase 2: Probe(探测)
对每一行 order:
  h = hash(o.user_id)
  if h matches user.id in Hash Table:
     output(u.*, o.*)
```

**内存不足时的多批处理**:

```text
Hash Join with Batch:
  - 哈希表超过 work_mem → 落盘分批
  - 内表也分批,逐批探测
  - 性能大幅下降(I/O 飙升)

★ 监控 "Batches: 1" → 内存够
★ 监控 "Batches: 4" → 落盘了,需增大 work_mem
```

**适用场景**:

```sql
✓ 等值 JOIN(必须)
✓ 一侧能装入内存
✓ 大表 JOIN(优于 NL)
✗ 非等值 JOIN(用 NL)
✗ 数据量极大,work_mem 不足
```

### 7. Merge Join(归并连接)

**两表都已排序**,类似归并排序的合并阶段。

```sql
EXPLAIN SELECT * FROM user u JOIN "order" o ON u.id = o.user_id
ORDER BY u.id;
```

```text
Merge Join  (cost=1500.00..2500.00 rows=10000 width=80)
  Merge Cond: (u.id = o.user_id)
  ->  Index Scan on user u
        (cost=0.43..500.00 rows=20000 width=42)
  ->  Index Scan on "order" o
        (cost=0.43..500.00 rows=10000 width=38)
```

**时序图**:

```text
user(id 排序)        order(user_id 排序)
   1 ◄──┐
   2    │      ┌─── 1
   3    ├──────┤
   4    │      ├─── 1
   5    │      ├─── 2
   6    │      ├─── 3
   ...  │      ├─── 4
        │      ├─── 5
        │      └─── ...

扫描两表,双指针推进:
  - u.id < o.user_id  → u 推进
  - u.id > o.user_id  → o 推进
  - 相等             → 输出 + 双推进

★ 复杂度 O(M + N)
★ 必须两表都已按 JOIN KEY 排序
```

**适用场景**:

```sql
✓ JOIN KEY 已有索引(免排序)
✓ 大表 + 大表
✓ 输出需要排序
✓ 数据已物理有序(刚 VACUUM FULL 后)

✗ 无合适索引,需先 Sort(代价大)
```

### 8. 三种 JOIN 算法对比

| 算法 | 时间复杂度 | 适用 | 内表需索引? | 内存 |
|------|----------|------|------------|------|
| **Nested Loop** | O(M × N) 或 O(M × logN) | 外表小 + 内表有索引 | 必须(否则灾难) | 极小 |
| **Hash Join** | O(M + N) | 等值 JOIN,一侧能装内存 | 否 | work_mem |
| **Merge Join** | O(M + N) | 两表已排序 / 大表 | 不需要(索引免排序) | 极小 |

**优化器选择规则**:

```text
等值 JOIN,大表 → Hash Join(默认)
等值 JOIN,内表有高效索引 → Nested Loop
JOIN KEY 有索引且两表大 → Merge Join
非等值 JOIN → Nested Loop
```

---

## 六、执行时间分析(actual time / rows / loops)

### 1. actual time 的含义

```text
(actual time=启动..总耗时 rows=实际行数 loops=执行次数)
              ↑      ↑         ↑             ↑
              │      │         │             └── 节点被重复执行的次数
              │      │         └──────────────── 实际返回的行数
              │      └─────────────────────────── 返回所有行的耗时(ms)
              └────────────────────────────────── 返回第一行的耗时(ms)
```

### 2. loops 的含义

```text
loops = 1:节点只执行一次(大多数节点)
loops = N:节点被重复执行 N 次(常出现在 Nested Loop 内层)

例:
  Nested Loop (actual time=0.05..10.5 rows=25 loops=1)
    -> Seq Scan on user (actual time=0.05..0.5 rows=1000 loops=1)
    -> Index Scan on order (actual time=0.005..0.05 rows=25 loops=1000)
                                              ↑                ↑
                                              │                └── order 内表被调用 1000 次
                                              └────────────────── 每次返回 25 行

总行数 = 25 × 1000 = 25000
```

### 3. 估算 vs 实际差异分析

```sql
EXPLAIN ANALYZE
SELECT * FROM big_table WHERE status = 1 AND create_dt > '2025-08-01';
```

```text
Bitmap Heap Scan on big_table  (cost=200.00..3000.00 rows=100 width=20)
                               (actual time=5.0..450.0 rows=50000 loops=1)

★ 估算 100 行,实际 50000 行
★ 偏差 500 倍 → 统计信息严重过期

原因可能:
  1. 大量 INSERT 后未 ANALYZE
  2. status 列分布变化大
  3. 复杂表达式让优化器估算不准

解决:
  ANALYZE big_table;  -- 更新统计信息
```

**诊断脚本**:

```sql
-- 找出估算与实际偏差最大的表
SELECT
  schemaname || '.' || relname AS table,
  seq_scan, seq_tup_read,
  idx_scan, idx_tup_fetch,
  n_live_tup,
  last_analyze, last_autoanalyze,
  n_mod_since_analyze
FROM pg_stat_user_tables
WHERE n_live_tup > 10000
ORDER BY n_mod_since_analyze DESC
LIMIT 20;
```

### 4. 找瓶颈节点

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT u.id, COUNT(*) FROM user u
JOIN "order" o ON u.id = o.user_id
GROUP BY u.id;
```

**输出节选**:

```text
HashAggregate  (actual time=80.000..84.000 rows=2000 loops=1)
               ↑              ↑  ↑                ↑
               │              │  │                └── 返回 2000 组
               │              │  └────────────────── 跑完所有聚合耗时
               │              └───────────────────── 启动(首行出来)耗时
               └───────────────────────────────────── 这是聚合节点

  ->  Hash Join  (actual time=4.000..50.000 rows=25000 loops=1)
                                              ↑
                                              └─ 整个 JOIN 耗时 46ms
                  ->  Seq Scan on order  (actual time=0.010..20.000 rows=10000 loops=1)
                                          ↑
                                          └─ order 表扫描 20ms
                  ->  Hash  (actual time=3.500..3.500 rows=2000 loops=1)
                            ↑
                            └─ 建哈希表 3.5ms
```

**瓶颈定位**:**actual total time 最大的节点就是瓶颈**。

```text
本例:
  HashAggregate        80..84    4 ms
  Hash Join            4..50     46 ms    ← ★ 瓶颈
    Seq Scan on order  0..20     20 ms
    Hash                3.5..3.5  0.1 ms

→ JOIN 是瓶颈,要 JOIN 优化
```

---

## 七、缓冲区使用(BUFFERS)

### 1. 开启 BUFFERS

```sql
EXPLAIN (ANALYZE, BUFFERS) SELECT ...;
```

### 2. BUFFERS 字段详解

```text
Buffers: shared hit=N read=M dirtied=X written=Y local hit=A temp read=B written=C
          ↑      ↑    ↑     ↑      ↑         ↑    ↑    ↑      ↑      ↑
          │      │    │     │      │         │    │    │      │      └─ 临时文件写
          │      │    │     │      │         │    │    │      └──────── 临时文件读
          │      │    │     │      │         │    │    └───────────── 本地缓存命中
          │      │    │     │      │         │    └─────────────────── (预留)
          │      │    │     │      │         └──────────────────────── (预留)
          │      │    │     │      └────────────────────────────────── 写盘(脏数据)
          │      │    │     └───────────────────────────────────────── 弄脏页
          │      │    └─────────────────────────────────────────────── 共享缓存未命中(读盘)
          │      └──────────────────────────────────────────────────── 共享缓存命中
          └─────────────────────────────────────────────────────────── 共享缓冲(shared_buffers)
```

### 3. 核心字段

| 字段 | 含义 | 优化意义 |
|------|------|---------|
| **shared hit** | 共享缓存命中(块数,8KB/块) | 越高越好 |
| **shared read** | 共享缓存未命中(读盘) | 越少越好 |
| **shared dirtied** | 修改脏页数 | 高 → 大量写 |
| **shared written** | 写入磁盘数 | 高 → checkpoint 频繁 |
| **temp read** | 临时文件读 | 高 → Hash/Sort 落盘 |
| **temp written** | 临时文件写 | 高 → work_mem 不足 |

### 4. 命中率计算

```sql
-- 命中率 = shared hit / (shared hit + shared read)
```

**单查询命中率**:

```text
EXPLAIN (ANALYZE, BUFFERS) SELECT ...;

Buffers: shared hit=3000 read=200
命中率 = 3000 / (3000 + 200) = 93.75%   ← 健康
```

**全库命中率**(系统级):

```sql
SELECT
  sum(heap_blks_hit) AS hit,
  sum(heap_blks_read) AS read,
  round(100.0 * sum(heap_blks_hit) /
    NULLIF(sum(heap_blks_hit) + sum(heap_blks_read), 0), 2) AS hit_rate
FROM pg_statio_user_tables;
```

**目标命中率**:**> 95%**(OLTP),**> 90%**(OLAP)。

### 5. temp read/written 的优化

```text
Hash Join with "Batches: 4"
Sort with "Sort Method: external merge Disk: 100MB"

→ 原因:work_mem 太小
→ 解决:
   SET work_mem = '64MB';        -- 会话级
   ALTER SYSTEM SET work_mem = '64MB';  -- 系统级
```

**查看当前 work_mem**:

```sql
SHOW work_mem;
SELECT name, setting, unit FROM pg_settings WHERE name = 'work_mem';
```

---

## 八、统计信息(ANALYZE)

### 1. 为什么统计信息重要

```text
PostgreSQL 优化器是纯 CBO,完全依赖统计信息做决策。
统计信息过期 → 估算偏差 → 选错计划 → 性能崩。

★ 统计信息是 PG 优化的灵魂
```

### 2. pg_stats 视图

```sql
SELECT * FROM pg_stats
WHERE tablename = 'user'
ORDER BY null_frac DESC;
```

**关键列**:

| 列 | 含义 | 用途 |
|----|------|------|
| **null_frac** | NULL 比例 | IS NULL 选择性 |
| **avg_width** | 平均字节数 | 估算 width |
| **n_distinct** | 唯一值数量(正数=绝对值,负数=比例) | 选择性 |
| **most_common_vals** | 高频值(MCV) | IN 列表选择性 |
| **most_common_freqs** | 高频值频率 | IN 选择性 |
| **histogram_bounds** | 直方图分桶 | 范围查询选择性 |
| **correlation** | 物理顺序与列顺序相关性 | 索引 vs 顺序扫描决策 |

**解读示例**:

```text
pg_stats 输出:
  null_frac = 0.1       ← 10% 是 NULL
  avg_width = 42        ← 平均 42 字节
  n_distinct = 200      ← 200 个不同值
  most_common_vals = ["北京","上海","广州"]  ← 高频城市
  most_common_freqs = [0.3, 0.2, 0.1]        ← 频率
  correlation = 0.85    ← 物理顺序与城市排序高度相关
```

### 3. 手动 ANALYZE

```sql
-- 单表
ANALYZE user;

-- 整个 schema
ANALYZE SCHEMA public;

-- 整个数据库
ANALYZE;

-- 仅统计指定列(加速)
ANALYZE user (city, age);

-- 查看 ANALYZE 时间
SELECT last_analyze, last_autoanalyze FROM pg_stat_user_tables WHERE relname = 'user';
```

**ANALYZE 的开销**:

```text
成本:
  - 读取表(可能 Sequential Scan)
  - 采样(默认 30000 行)
  - 计算统计信息

频率:
  - 大量写入后建议立即跑
  - autovacuum 也会触发,但有延迟
```

### 4. 自动 ANALYZE(autovacuum)

```sql
-- 查看配置
SELECT name, setting, short_desc
FROM pg_settings
WHERE name LIKE '%analyze%' OR name LIKE '%autovacuum%';
```

**关键参数**:

| 参数 | 默认 | 说明 |
|------|------|------|
| **autovacuum** | on | 总开关 |
| **autovacuum_analyze_scale_factor** | 0.1 | 表大小的 10% 变更触发 |
| **autovacuum_analyze_threshold** | 50 | 至少 50 行变更 |
| **autovacuum_naptime** | 60s | 检查间隔 |
| **default_statistics_target** | 100 | 直方图桶数 |

**触发条件**:

```text
触发 ANALYZE 条件:
  变更行数 ≥ autovacuum_analyze_threshold +
               autovacuum_analyze_scale_factor × 表行数
  或
  insert/update/delete 总数超过阈值

默认(表 10 万行):
  触发 = 50 + 0.1 × 100000 = 10050 行变更
```

**调优建议**:

```sql
-- 大表:提高阈值,避免频繁 analyze
ALTER TABLE big_table SET (
  autovacuum_analyze_scale_factor = 0.05,    -- 5% 变更触发
  autovacuum_analyze_threshold = 10000
);

-- 小表:降低阈值
ALTER TABLE small_table SET (
  autovacuum_analyze_scale_factor = 0.2,
  autovacuum_analyze_threshold = 100
);
```

### 5. statistics_target 调整

```text
默认 100 桶 → 估算精度有限
对关键列(JOIN KEY、WHERE 高频列),调高到 1000-10000
```

```sql
-- 提高指定列的统计精度
ALTER TABLE user ALTER COLUMN email SET STATISTICS 1000;
ALTER TABLE user ALTER COLUMN city SET STATISTICS 500;
ANALYZE user;

-- 列级调整
SELECT attname, attstattarget
FROM pg_attribute
WHERE attrelid = 'user'::regclass AND attnum > 0;
```

---

## 九、优化器参数

### 1. 成本参数

```sql
-- 查看所有成本参数
SELECT name, setting, unit, short_desc
FROM pg_settings
WHERE name LIKE '%cost%' OR name LIKE '%page%';
```

| 参数 | 默认 | 说明 | 调优建议 |
|------|------|------|---------|
| **seq_page_cost** | 1.0 | 顺序读一页成本 | 通常不改 |
| **random_page_cost** | 4.0 | 随机读一页成本 | **SSD 改 1.1**,NVMe 改 1.0 |
| **cpu_tuple_cost** | 0.01 | 处理一行 CPU | 通常不改 |
| **cpu_index_tuple_cost** | 0.005 | 处理索引项 | 通常不改 |
| **cpu_operator_cost** | 0.0025 | 操作符 | 通常不改 |
| **effective_cache_size** | 4GB | 优化器估计的 OS 缓存 | 设为物理内存的 75% |
| **jit_above_cost** | 100000 | 超过此 cost 启用 JIT | OLAP 可调低 |
| **jit_inline_above_cost** | 500000 | JIT 内联阈值 | 同上 |

### 2. random_page_cost 的影响

```text
random_page_cost 越高 → 优化器越倾向于 Seq Scan → 不用索引
random_page_cost 越低 → 优化器越倾向于 Index Scan → 用索引

机械硬盘:random_page_cost = 4.0(默认值合理)
SSD:random_page_cost = 1.1
NVMe:random_page_cost = 1.0

★ SSD 时代强烈建议把 random_page_cost 调到 1.1
```

```sql
ALTER SYSTEM SET random_page_cost = 1.1;
SELECT pg_reload_conf();
```

### 3. effective_cache_size

```text
对优化器的提示:操作系统缓存大概有多大
影响:优化器是否倾向于走索引

effective_cache_size 越大 → 越倾向 Index Scan
典型值:物理内存的 50-75%

例:128GB 内存服务器:
  effective_cache_size = 96GB
```

```sql
ALTER SYSTEM SET effective_cache_size = '96GB';
SELECT pg_reload_conf();
```

### 4. work_mem(影响排序/哈希)★★

```text
work_mem 用于:
  - Sort(ORDER BY / DISTINCT / Merge Join)
  - Hash Join / HashAggregate
  - Bitmap Heap Scan(位图)

每个会话/每个节点都可能用一份 work_mem
默认 4MB 太小,生产环境建议 64MB-256MB
```

```sql
-- 会话级
SET work_mem = '256MB';

-- 系统级(全局)
ALTER SYSTEM SET work_mem = '256MB';

-- 单查询级(不污染会话)
SELECT /*+ Set(work_mem '256MB') */ * FROM ...;
```

**配置建议**:

| 数据库规模 | work_mem |
|----------|---------|
| 小(< 10GB) | 64MB |
| 中(10-100GB) | 256MB |
| 大(> 100GB) | 1GB(谨慎) |

### 5. 其他关键 GUC

```sql
-- 共享缓冲(必须改)
shared_buffers = 25% of RAM   -- 128GB → 32GB

-- 查询规划
geqo_threshold = 12            -- ≥ 12 表用遗传算法
join_collapse_limit = 8        -- JOIN 重排上限
from_collapse_limit = 8        -- 子查询提升上限

-- 并行
max_parallel_workers_per_gather = 4
max_parallel_workers = 16

-- JIT(PG 11+,OLAP 推荐开启)
jit = on
jit_above_cost = 100000
```

---

## 十、SQL 优化实战

### 1. 慢查询定位工具

#### (1) pg_stat_statements(必装扩展)

```sql
-- 安装
CREATE EXTENSION pg_stat_statements;

-- 配置 postgresql.conf
shared_preload_libraries = 'pg_stat_statements'
pg_stat_statements.max = 10000
pg_stat_statements.track = top
```

**核心查询**:

```sql
-- 最耗时的 SQL(Total Time)
SELECT
  substring(query, 1, 80) AS sql,
  calls,
  round(total_exec_time::numeric, 2) AS total_ms,
  round(mean_exec_time::numeric, 2) AS mean_ms,
  round((100 * total_exec_time / sum(total_exec_time) OVER ())::numeric, 2) AS pct
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 20;
```

```text
输出解读:
  sql              SQL 前 80 字符
  calls            执行次数
  total_ms         总耗时(ms)
  mean_ms          平均耗时
  pct              占总耗时百分比
```

**输出节选**:

```text
                sql                 | calls | total_ms | mean_ms |  pct
─────────────────────────────────────┼───────┼──────────┼─────────┼───────
 SELECT * FROM "order" WHERE ...    | 12345 | 850000.5 |  68.85  | 32.5
 SELECT u.*, COUNT(o.id) FROM ...   |   234 | 250000.0 | 1068.38 |  9.6
 UPDATE user SET last_login = ...   |1000000| 180000.0 |   0.18  |  6.9
```

**其他维度**:

```sql
-- 平均最慢的 SQL
SELECT substring(query, 1, 80), calls, mean_exec_time
FROM pg_stat_statements
WHERE calls > 100
ORDER BY mean_exec_time DESC LIMIT 20;

-- 读盘最多的 SQL
SELECT substring(query, 1, 80), shared_blks_read
FROM pg_stat_statements
ORDER BY shared_blks_read DESC LIMIT 20;

-- 返回行数最多的 SQL
SELECT substring(query, 1, 80), rows
FROM pg_stat_statements
ORDER BY rows DESC LIMIT 20;

-- 临时 IO 最多的 SQL(work_mem 不足信号)
SELECT substring(query, 1, 80), temp_blks_written
FROM pg_stat_statements
WHERE temp_blks_written > 0
ORDER BY temp_blks_written DESC LIMIT 20;
```

#### (2) pg_stat_user_tables

```sql
-- 全表扫描最多的表(性能隐患)
SELECT
  relname, seq_scan, seq_tup_read,
  idx_scan, idx_tup_fetch,
  n_live_tup
FROM pg_stat_user_tables
WHERE seq_scan > 0
ORDER BY seq_tup_read DESC
LIMIT 20;
```

#### (3) auto_explain(自动 EXPLAIN)

```sql
-- postgresql.conf
shared_preload_libraries = 'auto_explain'
auto_explain.log_min_duration = '1s'   -- 超过 1s 自动记录 EXPLAIN
auto_explain.log_analyze = on
auto_explain.log_buffers = on
auto_explain.log_format = 'json'
auto_explain.sample_rate = 0.01        -- 采样 1%
```

### 2. 索引选择

```sql
-- 检查冗余/未使用的索引
SELECT
  s.schemaname, s.relname AS table,
  s.indexrelname AS index,
  s.idx_scan AS scans,
  pg_size_pretty(pg_relation_size(s.indexrelid)) AS size
FROM pg_stat_user_indexes s
WHERE s.idx_scan < 50             -- 几乎没用过
  AND s.schemaname NOT IN ('pg_catalog')
ORDER BY pg_relation_size(s.indexrelid) DESC;

-- 检查缺失索引(高频 Seq Scan 大表)
SELECT
  relname, seq_scan, seq_tup_read,
  n_live_tup, n_distinct
FROM pg_stat_user_tables
WHERE seq_scan > 1000
  AND n_live_tup > 10000
  AND seq_tup_read / seq_scan > 1000
ORDER BY seq_tup_read DESC;
```

### 3. JOIN 顺序与子查询改写

**反例:相关子查询**:
```sql
EXPLAIN SELECT u.* FROM user u
WHERE u.id IN (SELECT o.user_id FROM "order" o WHERE o.amount > 1000);
```
```text
Hash Semi Join  (cost=620.00..1500.00 rows=500 width=42)
  Hash Cond: (u.id = o.user_id)
  ->  Seq Scan on user u  (cost=0.00..500.00 rows=20000 width=42)
  ->  Hash  (cost=500.00..500.00 rows=5000 width=8)
        ->  Seq Scan on "order" o  (cost=0.00..500.00 rows=5000 width=8)
              Filter: (amount > 1000)
```

**正例:JOIN 改写**(PG 通常自动优化):

```sql
EXPLAIN SELECT DISTINCT u.* FROM user u
INNER JOIN "order" o ON u.id = o.user_id
WHERE o.amount > 1000;
```

### 4. EXISTS vs IN

```sql
-- 数据量大时 EXISTS 通常更优(可早停)
SELECT u.* FROM user u
WHERE EXISTS (SELECT 1 FROM "order" o WHERE o.user_id = u.id AND o.amount > 1000);
```

```text
EXPLAIN 输出:
Hash Semi Join (cost=...)
  ->  Seq Scan on user u
  ->  Hash
        ->  Seq Scan on "order" o
```

**PG 内部会自动把 IN/EXISTS 转成 Semi Join**,通常无需手动改写。

### 5. 优化 COUNT(*)

```sql
-- COUNT(*) 通常用 Seq Scan(更快),不必强行用索引

-- 近似计数(快速)
SELECT reltuples FROM pg_class WHERE relname = 'user';

-- 精确计数 + 条件(走索引)
CREATE INDEX idx_user_status ON user(status) WHERE status IS NOT NULL;
SELECT COUNT(*) FROM user WHERE status = 1;
```

### 6. 优化 LIKE

```sql
-- 前缀匹配:索引生效
EXPLAIN SELECT * FROM user WHERE name LIKE '张%';
-- Bitmap Index Scan on idx_user_name

-- 后缀匹配:索引失效
EXPLAIN SELECT * FROM user WHERE name LIKE '%张';
-- Seq Scan

-- 全字段模糊:全文搜索
CREATE EXTENSION pg_trgm;
CREATE INDEX idx_user_name_trgm ON user USING gin (name gin_trgm_ops);
SELECT * FROM user WHERE name ILIKE '%张%';
```

### 7. 优化 ORDER BY

```sql
-- 反例:filesort
EXPLAIN SELECT * FROM user ORDER BY age;

-- 正例:索引顺序
CREATE INDEX idx_user_age ON user(age);
EXPLAIN SELECT age FROM user ORDER BY age;
-- Index Only Scan
```

### 8. 优化 GROUP BY

```sql
-- PG 默认 HashAggregate(无需预排序)

-- 若 GROUP BY 列在最左前缀索引,可触发 GroupAggregate(更快)
CREATE INDEX idx_user_city ON user(city, status);
EXPLAIN SELECT city, count(*) FROM user GROUP BY city;
-- GroupAggregate  (cost=... rows=200 width=...)
```

### 9. CTE 优化(PG 12+ 内联)

```sql
-- PG 11 及之前:CTE 总是物化,可能慢
WITH active_user AS (
  SELECT * FROM user WHERE status = 1
)
SELECT * FROM active_user WHERE age > 18;

-- PG 12+:自动内联(等价于子查询)
-- 可用 EXPLAIN 验证是否物化
EXPLAIN WITH active_user AS (SELECT * FROM user WHERE status = 1)
SELECT * FROM active_user WHERE age > 18;

-- 强制物化(PG 12+)
WITH active_user AS MATERIALIZED (
  SELECT * FROM user WHERE status = 1
)
SELECT * FROM active_user WHERE age > 18;
```

### 10. 优化 UNION vs UNION ALL

```sql
-- UNION:去重,慢(要排序)
EXPLAIN SELECT id FROM a UNION SELECT id FROM b;
-- 有 Unique 节点

-- UNION ALL:不去重,快
EXPLAIN SELECT id FROM a UNION ALL SELECT id FROM b;
-- 只有 Append
```

---

## 十一、执行计划缓存(prepared statements)

### 1. 自定义计划 vs 通用计划

PostgreSQL 12+ 引入,**预编译语句**(Prepared Statements)的计划可以缓存。

```text
PG 12+ 的 PREPARE 行为:

  第一次执行:
    1. 用实际参数生成 Custom Plan(最优)
    2. 与 Generic Plan(参数无关)比较 cost
    3. 若 Custom Plan 不显著优于 Generic(默认 5 次后):
       → 采用 Generic Plan 缓存

  第 2-5 次:
    → Custom Plan

  第 6 次起:
    → Generic Plan(缓存)
```

### 2. 强制使用 Generic Plan

```sql
PREPARE my_query (int) AS
SELECT * FROM user WHERE age = $1;

-- 强制通用计划
SET plan_cache_mode = force_generic_plan;

EXECUTE my_query(20);
```

### 3. plan_cache_mode

| 取值 | 行为 |
|------|------|
| **auto**(默认) | 自动选择 |
| **force_custom_plan** | 总是用 Custom |
| **force_generic_plan** | 总是用 Generic |

### 4. 实战建议

```sql
-- OLTP 频繁相同参数:Custom Plan 更优
-- OLAP 参数差异大:Generic Plan 更稳定

-- 查看预编译语句命中
SELECT * FROM pg_prepared_statements;

-- 服务端预编译
PREPARE name (text, int) AS SELECT ...;
```

---

## 十二、查询改写技巧

### 1. 避免 SELECT *

```sql
-- 反例:触发回表
SELECT * FROM user WHERE id = 1;

-- 正例:覆盖索引(若有)
SELECT id, name, age FROM user WHERE id = 1;
```

### 2. 避免函数包装列

```sql
-- 反例:索引失效
EXPLAIN SELECT * FROM user WHERE date_trunc('day', create_dt) = '2025-01-01';

-- 正例:SARGable
EXPLAIN SELECT * FROM user
WHERE create_dt >= '2025-01-01' AND create_dt < '2025-01-02';
```

### 3. 拆分复杂 JOIN

```sql
-- 反例:5 表 JOIN
SELECT * FROM a JOIN b ... JOIN c ... JOIN d ... JOIN e ...;

-- 正例:逐步筛选
SELECT * FROM a WHERE create_dt > '2025-01-01';  -- 100 行
SELECT * FROM b WHERE id IN (...);  -- 1000 行
-- 应用层合并
```

### 4. EXISTS 替代 DISTINCT

```sql
-- 反例(返回大量数据再 DISTINCT)
SELECT DISTINCT u.* FROM user u
JOIN "order" o ON u.id = o.user_id;

-- 正例(SEMI JOIN)
SELECT u.* FROM user u
WHERE EXISTS (SELECT 1 FROM "order" o WHERE o.user_id = u.id);
```

### 5. 标量子查询改 LATERAL JOIN(PG 9.3+)

```sql
-- 反例:每行执行子查询
SELECT
  u.id, u.name,
  (SELECT COUNT(*) FROM "order" o WHERE o.user_id = u.id) AS cnt
FROM user u;

-- 正例:LATERAL JOIN
SELECT u.id, u.name, COALESCE(t.cnt, 0) AS cnt
FROM user u
LEFT JOIN LATERAL (
  SELECT COUNT(*) AS cnt FROM "order" o WHERE o.user_id = u.id
) t ON true;
```

---

## 十三、pg_stat_statements 详解

### 1. 安装

```sql
-- postgresql.conf
shared_preload_libraries = 'pg_stat_statements'

-- 重启后
CREATE EXTENSION pg_stat_statements;
```

### 2. 完整输出解读

```sql
SELECT * FROM pg_stat_statements LIMIT 1 \x
```

```text
-[ RECORD 1 ]--------+------------------------------------------------------------
userid              | 10
dbid                | 16384
queryid             | -9028472897855048515
query               | SELECT * FROM "user" WHERE id = $1
plans               | 5        ← 计划次数
total_plan_time     | 0.523    ← 规划总耗时
min_plan_time       | 0.05
max_plan_time       | 0.15
mean_plan_time      | 0.105
calls               | 1000     ← 调用次数
total_exec_time     | 85.234   ← 执行总耗时
min_exec_time       | 0.05
max_exec_time       | 1.20
mean_exec_time      | 0.085
stddev_exec_time    | 0.02
rows                | 1000     ← 总返回行数
shared_blks_hit     | 5000     ← 缓存命中
shared_blks_read    | 50       ← 读盘
shared_blks_dirtied | 0
shared_blks_written | 0
local_blks_hit      | 0
local_blks_read     | 0
local_blks_dirtied  | 0
local_blks_written  | 0
temp_blks_read      | 0
temp_blks_written   | 0
blk_read_time       | 0
blk_write_time      | 0
```

### 3. 实战查询模板

```sql
-- TOP 10 最慢 SQL(总耗时)
SELECT
  round((total_exec_time / 1000.0)::numeric, 2) AS total_sec,
  calls,
  round((mean_exec_time)::numeric, 2) AS mean_ms,
  round((100 * total_exec_time / sum(total_exec_time) OVER ())::numeric, 2) AS pct,
  shared_blks_read, temp_blks_written,
  substring(query, 1, 100) AS sql
FROM pg_stat_statements
ORDER BY total_exec_time DESC LIMIT 10;

-- 缓存命中率最低的 SQL
SELECT
  substring(query, 1, 100),
  calls,
  shared_blks_hit, shared_blks_read,
  round(100.0 * shared_blks_hit / NULLIF(shared_blks_hit + shared_blks_read, 0), 2) AS hit_rate
FROM pg_stat_statements
WHERE calls > 100
ORDER BY hit_rate ASC NULLS FIRST LIMIT 10;

-- work_mem 不足的 SQL(temp_blks_written > 0)
SELECT
  substring(query, 1, 100),
  calls, temp_blks_written, temp_blks_read
FROM pg_stat_statements
WHERE temp_blks_written > 0
ORDER BY temp_blks_written DESC LIMIT 10;
```

### 4. 重置统计

```sql
-- 重置所有
SELECT pg_stat_statements_reset();

-- 部分重置(PG 14+)
SELECT pg_stat_statements_reset(0, 0, 0);
```

---

## 十四、auto_explain 扩展

### 1. 安装与配置

```ini
# postgresql.conf
shared_preload_libraries = 'auto_explain'

auto_explain.log_min_duration = '1s'        # 超过 1s 自动记录
auto_explain.log_analyze = on               # 含 ANALYZE
auto_explain.log_buffers = on               # 含 BUFFERS
auto_explain.log_format = 'json'            # JSON 格式
auto_explain.log_nested_statements = on     # 含嵌套语句
auto_explain.sample_rate = 0.01             # 采样 1%
auto_explain.log_timing = on                # 含 timing
```

```bash
# 重启生效
pg_ctl restart
```

### 2. 效果

```text
# 日志输出(每条慢查询自动带 EXPLAIN ANALYZE)
LOG:  duration: 1523.456 ms  plan:
  Query Text: SELECT * FROM big_table WHERE ...
  Plan:
    Query Parameters: $1 = ...
    →  Hash Join  (cost=... rows=... width=...) (actual time=... rows=... loops=...)
       ...
```

### 3. 与 pg_stat_statements 配合

```text
工作流:

1. pg_stat_statements 定位慢 SQL(按 total_exec_time 排序)
2. 找到目标 SQL
3. auto_explain 自动记录 EXPLAIN
4. 针对性优化
5. 验证 pg_stat_statements 中 mean_exec_time 是否下降
```

---

## 十五、完整优化案例

### 案例 1:全表扫描(LIKE 后缀)

**问题 SQL**(8 秒):

```sql
SELECT * FROM article WHERE content LIKE '%PostgreSQL 优化%';
```

**EXPLAIN**:

```text
Seq Scan on article  (cost=0.00..50000.00 rows=100 width=200)
  Filter: (content ~~ '%PostgreSQL 优化%'::text)
```

**诊断**:后缀模糊 + 无索引。

**解决**:

```sql
-- 1. pg_trgm + GIN
CREATE EXTENSION pg_trgm;
CREATE INDEX idx_article_content_trgm ON article USING gin (content gin_trgm_ops);

-- 2. 改写(用 ILIKE 或 LIKE 都能走 trgm)
EXPLAIN (ANALYZE) SELECT * FROM article WHERE content LIKE '%PostgreSQL 优化%';
-- Bitmap Heap Scan on article  ...
--   ->  Bitmap Index Scan on idx_article_content_trgm
```

**效果**:8s → 80ms。

### 案例 2:函数破坏索引

**问题 SQL**(5 秒):

```sql
SELECT * FROM "order" WHERE date_trunc('day', create_dt) = '2025-01-01';
```

**EXPLAIN**:

```text
Seq Scan on "order"  (cost=0.00..25000.00 rows=1000 width=80)
  Filter: (date_trunc('day'::text, create_dt) = '2025-01-01'::date)
```

**解决**:

```sql
SELECT * FROM "order"
WHERE create_dt >= '2025-01-01' AND create_dt < '2025-01-02';
```

**改后**:

```text
Index Scan using idx_order_create_dt on "order"  (cost=0.43..500.00 rows=5000 width=80)
  Index Cond: ((create_dt >= '2025-01-01') AND (create_dt < '2025-01-02'))
```

### 案例 3:JOIN 字段无索引

**问题 SQL**(30 秒):

```sql
SELECT u.name, o.amount
FROM user u JOIN "order" o ON u.name = o.receiver_name
WHERE u.create_dt > '2025-01-01';
```

**EXPLAIN**:

```text
Hash Join  (cost=620.00..5000.00 rows=20000 width=80)
  Hash Cond: (u.name = o.receiver_name)
  ->  Seq Scan on user u  (cost=0.00..500.00 rows=2000 width=42)
        Filter: (create_dt > '2025-01-01')
  ->  Hash  (cost=1500.00..1500.00 rows=50000 width=38)
        ->  Seq Scan on "order" o  (cost=0.00..1500.00 rows=50000 width=38)
```

**解决**:

```sql
CREATE INDEX idx_order_receiver_name ON "order"(receiver_name);
```

**改后**:

```text
Hash Join  (cost=620.00..2500.00 rows=20000 width=80)
  Hash Cond: (u.name = o.receiver_name)
  ->  Seq Scan on user u  (cost=0.00..500.00 rows=2000 width=42)
  ->  Hash  (cost=1500.00..1500.00 rows=50000 width=38)
        ->  Index Scan on idx_order_receiver_name  (cost=0.43..1500.00 rows=50000 width=38)
```

**效果**:30s → 2s。

### 案例 4:深分页

**问题 SQL**(12 秒):

```sql
SELECT * FROM article ORDER BY create_dt DESC LIMIT 1000000, 20;
```

**EXPLAIN**:

```text
Limit  (cost=5000.00..5000.25 rows=20 width=200)
  ->  Index Scan Backward using idx_article_create_dt on article  (cost=0.43..250000.00 rows=1000000 width=200)
```

**解决**:

```sql
-- 方案 1:游标分页
SELECT * FROM article
WHERE create_dt < '2025-08-14 10:00:00'   -- 上次最后一条的 create_dt
ORDER BY create_dt DESC LIMIT 20;

-- 方案 2:延迟关联
SELECT a.*
FROM article a
JOIN (
  SELECT id FROM article
  ORDER BY create_dt DESC LIMIT 1000000, 20
) t USING (id);
```

### 案例 5:GROUP BY 触发 HashAggregate

**问题 SQL**(6 秒):

```sql
SELECT city, COUNT(*) FROM user GROUP BY city;
```

**EXPLAIN**:

```text
HashAggregate  (cost=500.00..520.00 rows=200 width=24)
  Group Key: city
  ->  Seq Scan on user  (cost=0.00..500.00 rows=20000 width=20)
```

**诊断**:无索引导致 Seq Scan。

**解决**:

```sql
CREATE INDEX idx_user_city ON user(city);

EXPLAIN SELECT city, COUNT(*) FROM user GROUP BY city;
-- Index Only Scan using idx_user_city on user
--   GroupAggregate
```

### 案例 6:ORDER BY 触发 Sort

**问题 SQL**(3 秒):

```sql
SELECT * FROM user WHERE age > 18 ORDER BY create_dt;
```

**EXPLAIN**:

```text
Sort  (cost=2000.00..2050.00 rows=800 width=42)
  Sort Key: create_dt
  ->  Seq Scan on user  (cost=0.00..1500.00 rows=800 width=42)
        Filter: (age > 18)
```

**解决**:

```sql
CREATE INDEX idx_user_age_create ON user(age, create_dt);

EXPLAIN SELECT * FROM user WHERE age > 18 ORDER BY create_dt;
-- Index Only Scan using idx_user_age_create on user
--   Index Cond: (age > 18)
```

### 案例 7:统计信息过期导致 Seq Scan

**问题 SQL**(本来应该秒级,实际 60 秒):

```sql
SELECT * FROM big_table WHERE status = 1;
```

**EXPLAIN**:

```text
Seq Scan on big_table  (cost=0.00..150000.00 rows=100 width=80)
  Filter: (status = 1)
```

**诊断**:

```sql
SELECT n_live_tup, last_analyze FROM pg_stat_user_tables WHERE relname = 'big_table';
-- n_live_tup = 10000000, last_analyze = 30 days ago
```

**解决**:

```sql
ANALYZE big_table;

EXPLAIN SELECT * FROM big_table WHERE status = 1;
-- Bitmap Heap Scan on big_table
--   ->  Bitmap Index Scan on idx_big_table_status
```

### 案例 8:IN 列表过大

**问题 SQL**(7 秒):

```sql
SELECT * FROM user WHERE id IN (1, 2, 3, ..., 10000);
```

**EXPLAIN**:

```text
Bitmap Heap Scan on user  (cost=500.00..2000.00 rows=10000 width=42)
  Recheck Cond: (id = ANY ('{1,2,3,...,10000}'::integer[]))
  ->  Bitmap Index Scan on user_pkey
```

**解决**:

```sql
-- 改为 JOIN 临时表
SELECT u.*
FROM user u
JOIN tmp_user_ids t ON u.id = t.id;
-- 或 VALUES 列表(有时更优)
SELECT u.*
FROM user u
JOIN (VALUES (1),(2),...) AS t(id) ON u.id = t.id;
```

### 案例 9:Hash Join 落盘(work_mem 不足)

**问题 SQL**(20 秒):

```sql
SELECT u.*, o.* FROM user u JOIN "order" o ON u.id = o.user_id;
```

**EXPLAIN**:

```text
Hash Join  (cost=...)
  Hash Cond: (o.user_id = u.id)
  ->  Seq Scan on "order" o
  ->  Hash  (cost=...)
        Batches: 64   ← ★ 落盘分 64 批
        Buckets: 131072  Batches: 64  Memory Usage: 4320kB
        Disk Usage: 524288 kB   ← ★ 临时磁盘 512MB
```

**解决**:

```sql
SET work_mem = '256MB';

EXPLAIN ...;
-- Hash  (cost=...)
--       Batches: 1   ← 单批,内存足够
```

### 案例 10:不当 IN 导致 Semi Join 慢

**问题 SQL**:

```sql
SELECT * FROM user
WHERE id IN (SELECT user_id FROM "order" WHERE amount > 1000);
```

**EXPLAIN**:

```text
Hash Semi Join  (cost=620.00..1500.00 rows=1000 width=42)
  Hash Cond: (u.id = "order".user_id)
  ->  Seq Scan on user u  (cost=0.00..500.00 rows=20000 width=42)
  ->  Hash  (cost=500.00..500.00 rows=5000 width=8)
        ->  Seq Scan on "order"  (cost=0.00..500.00 rows=5000 width=8)
              Filter: (amount > 1000)
```

**优化方向**:

```sql
-- 1. order 表加索引(若缺失)
CREATE INDEX idx_order_amount_user ON "order"(amount, user_id);

-- 2. 改写为显式 JOIN(若优化器选错)
SELECT DISTINCT u.* FROM user u
INNER JOIN "order" o ON u.id = o.user_id
WHERE o.amount > 1000;
```

### 案例 11:复杂 JOIN 优化

**问题 SQL**(25 秒):

```sql
SELECT u.name, COUNT(o.id), SUM(o.amount)
FROM user u
LEFT JOIN "order" o ON u.id = o.user_id
LEFT JOIN payment p ON o.id = p.order_id
WHERE u.create_dt > '2025-01-01'
  AND o.status = 1
GROUP BY u.id
HAVING COUNT(o.id) > 5
ORDER BY SUM(o.amount) DESC
LIMIT 100;
```

**EXPLAIN ANALYZE 节选**:

```text
Limit (actual time=1250..1250 rows=100 loops=1)
  Buffers: shared hit=30000 read=5000
  ->  Sort (actual time=1240..1245 rows=100 loops=1)
        Sort Key: (sum(o.amount)) DESC
        Sort Method: top-N heapsort  Memory: 35kB
        ->  HashAggregate (actual time=1100..1200 rows=2000 loops=1)
              Group Key: u.id
              Batches: 8  Memory Usage: 4264kB  Disk Usage: 10240 kB  ← 落盘
              ->  Hash Left Join (actual time=50..800 rows=25000 loops=1)
                    ...
```

**优化**:

```sql
-- 1. 加索引
CREATE INDEX idx_user_create_dt ON user(create_dt);
CREATE INDEX idx_order_user_status ON "order"(user_id, status);
CREATE INDEX idx_payment_order ON payment(order_id);

-- 2. 改写:先聚合再 JOIN
SELECT u.id, u.name, t.cnt, t.total
FROM user u
JOIN (
  SELECT user_id, COUNT(*) AS cnt, SUM(amount) AS total
  FROM "order"
  WHERE status = 1
    AND create_dt > '2025-01-01'
  GROUP BY user_id
  HAVING COUNT(*) > 5
  ORDER BY SUM(amount) DESC
  LIMIT 100
) t ON u.id = t.user_id;
```

### 案例 12:递归 CTE 优化

**问题 SQL**(40 秒):

```sql
WITH RECURSIVE org_tree AS (
  SELECT id, parent_id, 1 AS depth
  FROM org
  WHERE id = 1
  UNION ALL
  SELECT o.id, o.parent_id, t.depth + 1
  FROM org o
  JOIN org_tree t ON o.parent_id = t.id
)
SELECT * FROM org_tree;
```

**优化**:

```sql
-- 1. 加索引(parent_id 是 JOIN 字段,必须索引)
CREATE INDEX idx_org_parent_id ON org(parent_id);

-- 2. 加大 work_mem(递归 CTE 可能用 Sort)
SET work_mem = '128MB';

-- 3. CYCLE 关键字(PG 14+,防止循环)
WITH RECURSIVE org_tree AS (
  SELECT id, parent_id, 1 AS depth
  FROM org
  WHERE id = 1
  UNION ALL
  SELECT o.id, o.parent_id, t.depth + 1
  FROM org o
  JOIN org_tree t ON o.parent_id = t.id
) CYCLE id SET is_cycle USING path
SELECT * FROM org_tree WHERE NOT is_cycle;
```

### 案例 13:窗口函数慢

**问题 SQL**(15 秒):

```sql
SELECT
  user_id, amount, create_dt,
  ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY create_dt DESC) AS rn
FROM "order";
```

**EXPLAIN**:

```text
WindowAgg  (cost=50000.00..70000.00 rows=50000 width=80)
  ->  Sort  (cost=50000.00..51000.00 rows=50000 width=80)
        Sort Key: user_id, create_dt DESC
        ->  Seq Scan on "order"  (cost=0.00..3000.00 rows=50000 width=80)
```

**优化**:

```sql
-- 加复合索引(直接按 PARTITION BY + ORDER BY 排序)
CREATE INDEX idx_order_user_dt ON "order"(user_id, create_dt DESC);

EXPLAIN SELECT ...;
-- WindowAgg
--   ->  Index Scan using idx_order_user_dt on "order"
```

---

## 十六、SQL 优化 Checklist

### 排查流程

```text
□ 1. pg_stat_statements 找 TOP 慢 SQL
□ 2. EXPLAIN (ANALYZE, BUFFERS) 查看计划
□ 3. 对比 rows 估算 vs Actual Rows(是否需 ANALYZE)
□ 4. 检查节点类型(是否有 Seq Scan / Sort / Hash Join 落盘)
□ 5. 检查 Buffers(shared hit 命中率)
□ 6. 检查 actual time 最大节点
□ 7. 针对性优化(索引 / 改写 / 参数)
□ 8. 重新 EXPLAIN 验证
□ 9. 上线观察(再查 pg_stat_statements)
```

### 索引检查

```text
□ 10. WHERE 字段有索引?
□ 11. ORDER BY 字段能用索引?
□ 12. GROUP BY 字段能用索引?
□ 13. JOIN 字段有索引?
□ 14. 是否 SARGable(无函数包装)?
□ 15. 是否有冗余/未使用索引?
□ 16. 统计信息是否最新?
```

### SQL 写法

```text
□ 17. 避免 SELECT *
□ 18. 用 EXISTS 替代 DISTINCT ON
□ 19. UNION ALL 替代 UNION
□ 20. 深分页用游标
□ 21. 子查询改 LATERAL JOIN
□ 22. 拆分复杂 JOIN
□ 23. CTE 考虑 MATERIALIZED 强制物化
```

### 参数调优

```sql
-- /var/lib/postgresql/data/postgresql.conf
shared_buffers = 25% of RAM
effective_cache_size = 75% of RAM
work_mem = 256MB                       -- 大 OLAP 更大
random_page_cost = 1.1                 -- SSD
maintenance_work_mem = 1GB
wal_buffers = 64MB
max_parallel_workers_per_gather = 4    -- OLAP
```

---

## 十七、核心要点速记

### EXPLAIN 三种形式

```sql
EXPLAIN SELECT ...;                     -- 仅估算
EXPLAIN ANALYZE SELECT ...;             -- 真正执行(快查慢 SQL 用)
EXPLAIN (ANALYZE, BUFFERS, VERBOSE) SELECT ...;  -- 生产级排查
EXPLAIN (FORMAT JSON, ANALYZE) SELECT ...;      -- 程序化处理
```

### 节点性能速查

```text
扫描类(从优到劣):
  Index Only Scan > Index Scan > Bitmap Heap Scan > Seq Scan

连接类:
  外表小 + 内表有索引  → Nested Loop
  等值 JOIN,数据适中  → Hash Join
  两表已排序          → Merge Join

聚合类:
  输入已按 GROUP KEY 排序 → GroupAggregate(最优)
  其他情况             → HashAggregate

★ Bitmap 扫描:多条件 OR / 中等行数比例
```

### cost 解读

```text
cost=启动..总成本 rows=估算行数 width=字节数
       ↑              ↑        ↑
       │              │        └── 平均行宽
       │              └─────────── 估算行数(基于 pg_stats)
       └────────────────────────── 抽象单位(IO + CPU 加权)
                                     SSD 调 random_page_cost = 1.1
```

### actual time 解读

```text
(actual time=启动..总耗时 rows=实际行数 loops=次数)
              ↑     ↑         ↑         ↑
              │     │         │         └── 节点重复执行次数
              │     │         └──────────── 实际返回行数
              │     └────────────────────── 返回所有行的耗时(ms)
              └──────────────────────────── 返回首行的耗时(ms)

★ actual time 最大的节点就是瓶颈
```

### Buffers 解读

```text
shared hit   共享缓存命中(越多越好,目标 > 95%)
shared read  共享缓存未命中(读盘,越少越好)
temp written 临时文件写(高 → work_mem 不足,加大)

命中率 = hit / (hit + read)
```

### 统计信息

```sql
ANALYZE table_name;            -- 手动更新
SELECT * FROM pg_stats;        -- 查看列统计

autovacuum_analyze_scale_factor 默认 0.1
大表应调低到 0.02-0.05,小表可调高
```

### 优化器参数

```sql
random_page_cost = 1.1          -- SSD 必改
effective_cache_size = 75% RAM  -- 索引倾向
work_mem = 64MB-1GB             -- 影响排序/哈希
shared_buffers = 25% RAM        -- 必须改
```

### SQL 优化口诀

```text
        SELECT 别用 *    覆盖索引最优
        函数计算远离    SARGable 不失效
        统计信息要新    ANALYZE 不能忘
        小表驱动大表    NLJ 效率高
        深分页用游标    千万级无忧
        Hash Join 要内存    work_mem 给够
        索引设计三原则:等值在前,范围在后,覆盖查询
```

### pg_stat_statements 必备查询

```sql
-- 最慢 TOP 10
SELECT substring(query, 1, 80), calls, mean_exec_time, total_exec_time
FROM pg_stat_statements ORDER BY total_exec_time DESC LIMIT 10;

-- 缓存命中率最低
SELECT substring(query, 1, 80),
  round(100.0 * shared_blks_hit /
    NULLIF(shared_blks_hit + shared_blks_read, 0), 2) AS hit_rate
FROM pg_stat_statements WHERE calls > 100
ORDER BY hit_rate ASC LIMIT 10;

-- work_mem 不足
SELECT substring(query, 1, 80), temp_blks_written
FROM pg_stat_statements WHERE temp_blks_written > 0
ORDER BY temp_blks_written DESC LIMIT 10;
```

### 排查流程速记

```text
pg_stat_statements 找慢 SQL
        ↓
EXPLAIN ANALYZE 查看计划
        ↓
定位瓶颈:Seq Scan? Sort 落盘? Hash 落盘? 估算偏差?
        ↓
优化:加索引 / 改写 SQL / 调参数 / ANALYZE
        ↓
重新 EXPLAIN 验证
        ↓
上线观察 pg_stat_statements
```

### 三种扫描对比

```text
Seq Scan        全表扫描     顺序 IO      小表 / 无索引
Index Scan      索引+回表    随机 IO      单行查询
Index Only Scan 覆盖索引     几乎无 IO    SELECT 列都在索引
Bitmap Scan     位图回表     顺序 IO      多条件 OR / 中等比例行

★ 优先 Index Only Scan
★ 慎用 Seq Scan(大表)
```

### 三种 JOIN 对比

```text
Nested Loop  O(M×N)   外表小 + 内表有索引
Hash Join    O(M+N)   等值 JOIN,work_mem 够
Merge Join   O(M+N)   两表已排序 / 大表 + 大表

★ PG 默认会选最优,不需强制
```

### 索引失效常见场景

```text
1. 函数包装列     date_trunc(...) = X   →  范围查询
2. 类型转换       int_col = '123'       →  同类型比较
3. 前导模糊       LIKE '%xxx'           →  pg_trgm 全文索引
4. 表达式索引缺失  upper(col) = 'X'     →  CREATE INDEX ON t(upper(col))
5. 统计信息过期   大量变更后            →  ANALYZE
6. 索引选择性差   性别等二值列          →  部分索引 / 复合索引
```