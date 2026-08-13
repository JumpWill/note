# MySQL 查询优化与 EXPLAIN

## 一、查询性能分析的整体思路

### 1. 为什么需要查询优化

MySQL 性能问题 80% 出在 SQL 层面。同一业务,**一个好的 SQL 和一个差的 SQL**,性能差距可能达到**数十倍甚至数百倍**。一个百万行的表,写得好可以 10 ms 响应,写得差要 10 s。

```text
性能问题的典型分布:

        应用代码问题       ███           5%
        架构设计问题       ██████        15%
        索引设计问题       ████████████  30%   ← ★ 高频
        SQL 写法问题       ██████████    25%   ← ★ 高频
        资源/配置问题      ██████        15%
        硬件问题           ██            5%
        其他               ███           5%
```

**性能问题的常见症状**:

| 症状 | 可能原因 |
|------|---------|
| 单条 SQL 慢 | 索引缺失 / 索引失效 / 复杂 JOIN |
| 数据库整体 QPS 低 | 慢 SQL 拖累 / 锁竞争 / IO 瓶颈 |
| CPU 高 | 复杂查询 / 排序 / 全表扫描 |
| 磁盘 IO 高 | 大量随机读 / 大范围扫描 |
| 连接数打满 | 长事务 / 慢查询占用连接 |
| 内存压力大 | 大排序 / 大临时表 |

### 2. 查询性能分析的五步法

```text
Step 1: 开启慢查询日志,定位慢 SQL
   ↓
Step 2: EXPLAIN / EXPLAIN ANALYZE 查看执行计划
   ↓
Step 3: 找到瓶颈(type / rows / Extra)
   ↓
Step 4: 针对性优化(改写 SQL / 加索引 / 改表结构)
   ↓
Step 5: 重新 EXPLAIN 验证,观察执行时间
```

**核心原则**:永远**先测量,后优化**。没看到 EXPLAIN 输出之前,不要凭直觉改 SQL。

**常见误区**:

```text
✗ 误区 1:看到 SQL 慢就加索引
  → 先 EXPLAIN,确认索引有效再加

✗ 误区 2:索引越多越好
  → 索引增加写入开销,占用磁盘

✗ 误区 3:看到 ALL 就一定全表扫描
  → 要看 type 和 Extra 综合判断

✗ 误区 4:优化后立刻上线
  → 必须 EXPLAIN 验证 + 压测对比

✗ 误区 5:只看 rows,不关注实际耗时
  → rows 是估算值,不准确;用 EXPLAIN ANALYZE 看 actual
```

### 3. 慢查询日志配置

```sql
-- 开启慢查询日志
SET GLOBAL slow_query_log = ON;
SET GLOBAL long_query_time = 1;                -- 超过 1 秒即记录(秒)
SET GLOBAL long_query_time = 0.5;              -- 更严格:0.5 秒
SET GLOBAL log_queries_not_using_indexes = ON;-- 记录未走索引的 SQL
SET GLOBAL slow_query_log_file = '/var/log/mysql/slow.log';

-- 查看当前配置
SHOW VARIABLES LIKE 'slow_query%';
SHOW VARIABLES LIKE 'long_query_time';

-- 永久生效(写入 my.cnf)
[mysqld]
slow_query_log = ON
long_query_time = 1
log_queries_not_using_indexes = ON
slow_query_log_file = /var/log/mysql/slow.log
```

**慢查询日志的输出格式**:

```text
# Time: 2025-08-14T10:00:00.123456Z
# User@Host: app[app] @ [192.168.1.100] Id: 12345
# Query_time: 8.523456  Lock_time: 0.000123 Rows_sent: 100  Rows_examined: 10000000
SET timestamp=1692000000;
SELECT * FROM order WHERE DATE(create_dt) = '2025-08-14';
```

| 字段 | 含义 |
|------|------|
| Query_time | SQL 执行总耗时 |
| Lock_time | 等待锁的时间 |
| Rows_sent | 返回给客户端的行数 |
| Rows_examined | 扫描的总行数 |

**关键指标**:Rows_examined / Rows_sent 比值越大,SQL 越差。

### 4. 慢查询分析工具 mysqldumpslow

```bash
# 查看最慢的 10 条 SQL
mysqldumpslow -s t -t 10 /var/log/mysql/slow.log

# 查看出现次数最多的 SQL
mysqldumpslow -s c -t 10 /var/log/mysql/slow.log

# 按执行时间排序,只看含 JOIN 的
mysqldumpslow -s t -t 10 -g "JOIN" /var/log/mysql/slow.log

# 常用参数:
#   -s t   按总时间排序
#   -s c   按次数排序
#   -s l   按平均耗时排序
#   -s r   按记录行数排序
#   -t N   取前 N 条
#   -g P   只看包含 P 的
```

### 5. performance_schema 与 sys schema

```sql
-- 8.0 默认开启 performance_schema
-- sys schema 提供友好视图

-- 查询执行次数最多、消耗最大的 SQL
SELECT * FROM sys.statement_analysis
ORDER BY total_latency DESC LIMIT 10;

-- 走全表扫描的表
SELECT * FROM sys.schema_tables_with_full_table_scans;

-- 未使用的索引
SELECT * FROM sys.schema_unused_indexes;

-- 冗余索引
SELECT * FROM sys.schema_redundant_indexes;

-- IO 最多的文件
SELECT * FROM sys.io_global_by_file_by_bytes
ORDER BY total DESC LIMIT 10;
```

---

## 二、EXPLAIN 命令详解

### 1. EXPLAIN 是什么

**EXPLAIN** 是 MySQL 提供的**查询执行计划查看工具**,它会**模拟优化器执行 SQL**,告诉你 MySQL **打算怎么执行这条 SQL**(访问顺序、用了什么索引、扫描多少行等)。

- **不会真正执行 SQL**(但 8.0.18+ 的 EXPLAIN ANALYZE 会)
- **核心列**:`type`、`key`、`rows`、`Extra`
- **5.6 之前只支持 SELECT**;5.6+ 支持 `INSERT/UPDATE/DELETE`;8.0+ 支持 `FOR CONNECTION`

```sql
-- 基本用法
EXPLAIN SELECT * FROM user WHERE id = 100;

-- 8.0.16+ 树形输出
EXPLAIN FORMAT=TREE SELECT * FROM user WHERE id = 100;

-- 8.0+ JSON 输出(含 cost 信息)
EXPLAIN FORMAT=JSON SELECT * FROM user WHERE id = 100;

-- 8.0.18+ 实际执行 + 统计
EXPLAIN ANALYZE SELECT * FROM user WHERE id = 100;
```

### 2. 三种输出格式详解

#### (1) TRADITIONAL 表格(默认)

```sql
EXPLAIN
SELECT u.id, u.name, o.amount
FROM user u JOIN order o ON u.id = o.user_id
WHERE u.create_dt > '2025-01-01';
```

输出:

```text
+----+-------------+-------+-------+---------+---------+---------+-----------------+------+----------+-----------------------+
| id | select_type | table | type  | key     | key_len | ref     | rows            | Extra                          |
+----+-------------+-------+-------+---------+---------+---------+-----------------+------+----------+-----------------------+
|  1 | SIMPLE      | u     | range | idx_dt  | 5       | NULL    |            2000 | Using where                    |
|  1 | SIMPLE      | o     | ref   | idx_uid | 9       | mydb.u.id |              25 | NULL                          |
+----+-------------+-------+-------+---------+---------+---------+-----------------+------+----------+-----------------------+
```

**特点**:简洁,但 join 顺序不直观,需要从上到下读。

#### (2) TREE 树形(8.0.16+)

```sql
EXPLAIN FORMAT=TREE
SELECT u.id, u.name, o.amount
FROM user u JOIN order o ON u.id = o.user_id
WHERE u.create_dt > '2025-01-01';
```

输出:

```text
-> Nested loop inner join  (cost=850 rows=5000)
    -> Filter: (u.create_dt > '2025-01-01')
        -> Index range scan on u using idx_create_dt  (cost=120 rows=2000)
    -> Index lookup on o using idx_user_id (user_id=u.id)  (cost=3.5 rows=25)
```

**特点**:**直观展示 JOIN 顺序和算法**,适合分析复杂 JOIN。

#### (3) JSON(8.0+)

```sql
EXPLAIN FORMAT=JSON
SELECT u.id, u.name, o.amount
FROM user u JOIN order o ON u.id = o.user_id
WHERE u.create_dt > '2025-01-01';
```

输出(简化):

```json
{
  "query_block": {
    "select_id": 1,
    "cost_info": {
      "query_cost": "850.00"
    },
    "nested_loop": [
      {
        "table": {
          "table_name": "u",
          "access_type": "range",
          "key": "idx_create_dt",
          "rows_examined_per_scan": 2000,
          "rows_produced_per_join": 2000,
          "filtered": "100.00",
          "cost_info": {
            "read_cost": "120.00",
            "eval_cost": "200.00",
            "prefix_cost": "320.00"
          }
        }
      },
      {
        "table": {
          "table_name": "o",
          "access_type": "ref",
          "key": "idx_user_id",
          "rows_examined_per_scan": 25,
          "cost_info": {
            "read_cost": "3.50",
            "eval_cost": "25.00"
          }
        }
      }
    ]
  }
}
```

**特点**:含详细 cost 信息,可程序化处理。

**三种格式适用场景**:

| 格式 | 适用 | 特点 |
|------|------|------|
| TRADITIONAL | 日常快速查看 | 简洁,但 join 顺序不直观 |
| TREE | 复杂 JOIN 分析 | 直观展示 join 顺序和算法 |
| JSON | 程序化分析、深度优化 | 含 cost、warnings,机器友好 |

### 3. EXPLAIN 输出列总览

```sql
EXPLAIN SELECT * FROM user WHERE id = 100;
```

输出列(12 列,MySQL 8.0):

```text
+----+-------------+-------+------------+-------+---------------+---------+---------+-------+------+----------+-------------+
| id | select_type | table | partitions | type  | possible_keys | key     | key_len | ref   | rows | filtered | Extra       |
+----+-------------+-------+------------+-------+---------------+---------+---------+-------+------+----------+-------------+
|  1 | SIMPLE      | user  | NULL       | const | PRIMARY       | PRIMARY | 4       | const |    1 |   100.00 | NULL        |
+----+-------------+-------+------------+-------+---------------+---------+---------+-------+------+----------+-------------+
```

---

## 三、EXPLAIN 输出列详解

### 1. id(查询序列号)

**含义**:SELECT 的**唯一标识符**,表示**执行顺序**。

| 规则 | 说明 |
|------|------|
| 数字相同 | 执行顺序**从上到下** |
| 数字越大 | 越**先执行**(子查询先执行) |
| NULL | 是 UNION 的结果合并行 |

```sql
-- 案例 1:id 相同
EXPLAIN
SELECT * FROM user u JOIN order o ON u.id = o.user_id;
-- id 都是 1,从上到下执行

-- 案例 2:id 不同(子查询)
EXPLAIN
SELECT * FROM user WHERE id IN (SELECT user_id FROM order WHERE amount > 1000);
-- id=1 是外层,id=2 是子查询
-- 先执行 id=2,再执行 id=1

-- 案例 3:UNION 的 id=NULL
EXPLAIN
SELECT id FROM user WHERE id = 1
UNION
SELECT id FROM order WHERE id = 2;
-- 第三个 id=NULL 的行是 UNION 的临时表合并
```

### 2. select_type(查询类型)

```sql
-- SIMPLE:简单查询(无子查询、无 UNION)
EXPLAIN SELECT * FROM user WHERE id = 1;

-- PRIMARY:外层查询(有子查询时,最外层是 PRIMARY)
EXPLAIN SELECT * FROM user WHERE id IN (SELECT user_id FROM order);

-- UNION:UNION 中的第二个及后续 SELECT
EXPLAIN
SELECT id FROM user WHERE id = 1
UNION
SELECT id FROM order WHERE id = 2;

-- SUBQUERY:子查询中的第一个 SELECT(不相关子查询)
EXPLAIN SELECT * FROM user WHERE id = (SELECT MAX(user_id) FROM order);

-- DEPENDENT SUBQUERY:依赖外层的子查询(相关子查询)
-- 性能差:每行都执行一次子查询
EXPLAIN SELECT * FROM user u
WHERE EXISTS (SELECT 1 FROM order o WHERE o.user_id = u.id);

-- DERIVED:派生表(FROM 子查询)
EXPLAIN SELECT * FROM (SELECT id, name FROM user WHERE age > 18) AS t;

-- MATERIALIZED:物化子查询(MySQL 8.0)
-- 子查询结果先物化为临时表,再与外层 JOIN
EXPLAIN SELECT * FROM user WHERE id IN
(SELECT user_id FROM order WHERE amount > 1000 GROUP BY user_id);
```

| select_type | 含义 | 性能影响 |
|-------------|------|---------|
| SIMPLE | 无子查询/UNION | 最优 |
| PRIMARY | 最外层查询 | - |
| UNION | UNION 后续 | - |
| SUBQUERY | 不相关子查询 | 中 |
| **DEPENDENT SUBQUERY** | 相关子查询 | **差** |
| DERIVED | 派生表 | 视情况 |
| MATERIALIZED | 物化子查询 | 较好(8.0+) |

### 3. table(表名)

| 显示 | 含义 |
|------|------|
| 表名 | 直接访问该表 |
| `<union M,N>` | UNION 合并后的临时表 |
| `<derived N>` | 派生表(N 是 id) |
| `<subquery N>` | 物化子查询 |
| `null` | 无表(如 `SELECT 1`) |

### 4. partitions(分区)

```sql
-- 分区表才有值
CREATE TABLE sale (
    id INT,
    sale_date DATE,
    amount DECIMAL(10,2)
) PARTITION BY RANGE (YEAR(sale_date)) (
    PARTITION p2023 VALUES LESS THAN (2024),
    PARTITION p2024 VALUES LESS THAN (2025),
    PARTITION p2025 VALUES LESS THAN (2026)
);

EXPLAIN SELECT * FROM sale WHERE sale_date = '2024-06-01';
-- partitions: p2024  ← ★ 命中分区,只扫一个分区

-- 非分区表显示 NULL
```

**意义**:分区剪裁(Partition Pruning)生效时,只扫描部分分区,大幅提升性能。

### 5. type(访问类型)★★★

**`type` 是 EXPLAIN 最重要的字段**,表示 MySQL 怎样访问表。**性能从最优到最差**:

```text
system  >  const  >  eq_ref  >  ref  >  range  >  index  >  ALL
        优 ───────────────────────────────────────────────────►  劣
```

#### (1) system

**表只有一行**(系统表)或 `COUNT(*)` 优化。理论最优,实际极少。

```sql
-- MyISAM 引擎下,COUNT(*) 直接返回,无需扫描
EXPLAIN SELECT * FROM (SELECT 1) AS t;
```

#### (2) const

**主键/唯一索引 + WHERE 常量等值**,最多一行。

```sql
CREATE TABLE user (id INT PRIMARY KEY, name VARCHAR(64));

EXPLAIN SELECT * FROM user WHERE id = 100;
-- type: const, rows: 1
```

**应用场景**:
- 主键等值查询
- 唯一索引等值查询
- 整型主键的范围查询也是 const(因为主键唯一)

```sql
-- 唯一索引等值
ALTER TABLE user ADD UNIQUE INDEX uk_email (email);
EXPLAIN SELECT * FROM user WHERE email = 'a@b.com';
-- type: const
```

#### (3) eq_ref

**JOIN 时,被驱动表用主键或唯一索引关联**,每行只匹配一行。**最佳 JOIN 类型**。

```sql
CREATE TABLE user (id INT PRIMARY KEY, name VARCHAR(64));
CREATE TABLE order (id INT PRIMARY KEY, user_id INT);

EXPLAIN SELECT * FROM user u JOIN order o ON u.id = o.user_id;
-- user 是 ALL 或 const,order 是 eq_ref(用 PRIMARY KEY)
```

**典型场景**:
- 主键关联的 JOIN
- 唯一索引关联的 JOIN

#### (4) ref

**非唯一索引等值查询**,可能匹配多行。

```sql
CREATE TABLE user (
    id INT PRIMARY KEY,
    name VARCHAR(64),
    INDEX idx_name (name)
);

EXPLAIN SELECT * FROM user WHERE name = '张三';
-- type: ref, key: idx_name, rows: N (匹配多行)
```

**典型场景**:
- 普通索引等值查询
- JOIN 字段有非唯一索引

#### (5) range

**索引范围查询**(BETWEEN、>、<、IN、LIKE 'xx%')。

```sql
EXPLAIN SELECT * FROM user WHERE id BETWEEN 100 AND 200;
-- type: range, key: PRIMARY

EXPLAIN SELECT * FROM user WHERE age > 20;
-- type: range, key: idx_age

EXPLAIN SELECT * FROM user WHERE id IN (1, 2, 3);
-- type: range

EXPLAIN SELECT * FROM user WHERE name LIKE '张%';
-- type: range
```

**特点**:**只在索引范围内扫描**,比 ALL 好,但比 ref 差。

#### (6) index

**全索引扫描**(扫整棵索引树,比 ALL 好,因为索引通常比数据小)。

```sql
EXPLAIN SELECT id FROM user;  -- SELECT 主键,只走聚簇索引
-- type: index
-- Extra: Using index

EXPLAIN SELECT name FROM user;  -- SELECT 索引列
-- type: index, key: idx_name
```

**典型场景**:
- `SELECT id FROM table`(只读主键)
- 覆盖索引的全索引扫描
- ORDER BY 主键的查询

#### (7) ALL

**全表扫描**(扫聚簇索引的叶子节点)。**最差,必须优化**。

```sql
EXPLAIN SELECT * FROM user WHERE name LIKE '%张%';
-- type: ALL (前导模糊,索引失效)
```

**实战标准**:
- ✅ `system/const/eq_ref/ref`:优秀
- ⚠️ `range`:可用
- ❌ `index`:尽量优化
- 🚫 `ALL`:必须优化

**type 与 rows 的关系**:

| type | rows 量级 | 性能 |
|------|----------|------|
| const | 1 | 最优 |
| eq_ref | 1 | 最优 |
| ref | 1~100 | 良好 |
| range | 100~10000 | 一般 |
| index | 全表行数 | 较差 |
| ALL | 全表行数 | 差 |

### 6. possible_keys / key / key_len

```sql
EXPLAIN SELECT * FROM user WHERE name = '张三' AND age = 20;
```

| 字段 | 含义 |
|------|------|
| **possible_keys** | MySQL **可能选择**的索引(候选列表) |
| **key** | MySQL **实际选择**的索引(`NULL` 表示没用索引) |
| **key_len** | 索引使用的**字节数**,反映命中了复合索引的多少列 |

**key_len 计算公式**:

```text
key_len = 索引列长度之和 + 是否为 NULL(是则 +1)

常见类型:
- INT          4 字节
- BIGINT       8 字节
- VARCHAR(N)   字符数 × 字符集字节数 + 2(长度前缀)
- DATETIME     8 字节
- TINYINT      1 字节
```

| 列类型 | key_len(非空) | key_len(可空) |
|--------|--------------|--------------|
| TINYINT | 1 | 1 |
| INT | 4 | 5 |
| BIGINT | 8 | 9 |
| VARCHAR(10) utf8mb4 | 42 | 43 |
| VARCHAR(10) utf8 | 32 | 33 |
| DATETIME | 8 | 8 |

```sql
CREATE TABLE t (a INT, b VARCHAR(10), c INT, INDEX idx_a_b (a, b));

EXPLAIN SELECT * FROM t WHERE a = 1;
-- key_len = 4  (只用 a)

EXPLAIN SELECT * FROM t WHERE a = 1 AND b = 'x';
-- key_len = 4 + 10*4 + 2 = 46 (用 a + b,utf8mb4,varchar 占 2 字节长度)
```

**key_len 的实战意义**:

```sql
CREATE TABLE t (a INT, b VARCHAR(10), c INT, INDEX idx_a_b_c (a, b, c));

-- 完全命中
EXPLAIN SELECT * FROM t WHERE a = 1 AND b = 'x' AND c = 5;
-- key_len = 4 + 42 + 4 = 50  ← 全部命中

-- 部分命中
EXPLAIN SELECT * FROM t WHERE a = 1 AND c = 5;
-- key_len = 4  ← 只命中 a

-- 范围后失效
EXPLAIN SELECT * FROM t WHERE a = 1 AND b > 'x' AND c = 5;
-- key_len = 4 + 42 = 46  ← c 不命中
```

### 7. ref(连接匹配条件)

显示**索引的哪一列或常量被使用**。

```sql
EXPLAIN SELECT * FROM user u JOIN order o ON u.id = o.user_id;
-- o.idx_user_id 的 ref = mydb.u.id

EXPLAIN SELECT * FROM user WHERE name = '张三';
-- ref = const
```

### 8. rows(预估扫描行数)★★★

**MySQL 估算的扫描行数**(不是真实行数,可能不准确,但趋势正确)。

```sql
EXPLAIN SELECT * FROM user WHERE name LIKE '张%';
-- rows = 1000   ← 估算要扫 1000 行

-- 行数越少越好。如果 rows 很大,大概率要加索引或改 SQL
```

**rows 与实际行数的差异**:

```text
rows 是基于统计信息估算的,可能:
- 远大于实际(优化器保守)
- 远小于实际(数据分布变了)
- 经常要 ANALYZE TABLE 更新统计信息
```

### 9. filtered(条件过滤百分比)

**Server 层过滤后剩余的行数比例**(估算,5.7+)。

```sql
EXPLAIN SELECT * FROM user WHERE name = '张三' AND age = 20;
-- rows = 100, filtered = 50.00  ← 过滤后剩 50 行

-- 实际返回行数 ≈ rows × filtered / 100
```

### 10. Extra(额外信息)★★★

**Extra 包含大量重要信息**,是优化的核心依据。

| Extra | 含义 | 优化建议 |
|-------|------|---------|
| **Using index** | **覆盖索引,无需回表** | ✅ 最优 |
| Using where | Server 层用 WHERE 过滤 | 一般 |
| **Using index condition** | **ICP 索引下推生效** | ✅ 良好 |
| **Using temporary** | **使用了临时表** | ❌ 需优化(常见于 GROUP BY 无索引) |
| **Using filesort** | **使用了文件排序** | ❌ 需优化 |
| Using MRR | MRR 优化生效 | ✅ |
| Using join buffer | JOIN 用了连接缓冲 | ⚠️ 取决于数据量 |
| Impossible WHERE | WHERE 永远 FALSE | - |
| Select tables optimized away | 优化器直接出结果(COUNT/MIN/MAX) | ✅ |
| Using union / Using sort_union | 索引合并 | ⚠️ 视情况 |

```sql
-- Using filesort 案例(需要优化)
EXPLAIN SELECT * FROM user ORDER BY age;
-- type: ALL, Extra: Using filesort  ← 没有 idx_age,需排序

-- 加索引后
ALTER TABLE user ADD INDEX idx_age (age);
EXPLAIN SELECT * FROM user ORDER BY age;
-- type: index, key: idx_age, Extra: Using index  ← 不再 filesort
```

**Extra 标志详解**:

```text
Using index        覆盖索引,直接从索引拿数据,无需回表
Using where        Server 层用 WHERE 过滤(可能在存储引擎外过滤)
Using index condition  索引下推 ICP,引擎层用索引列过滤
Using temporary    使用了临时表(常见于 GROUP BY、DISTINCT、UNION 无索引)
Using filesort     内存或磁盘排序(无合适索引)
Using MRR          MRR 优化生效(主键排序后回表)
Using join buffer  使用了 JOIN 缓冲(BNL 或 Hash Join)
Impossible WHERE   WHERE 永远为 FALSE
Select tables optimized away  优化器直接出结果(MIN/MAX/COUNT)
```

---

## 四、EXPLAIN ANALYZE(MySQL 8.0 实际执行统计)

### 1. 什么是 EXPLAIN ANALYZE

**MySQL 8.0.18+** 引入的新特性,**会真正执行 SQL**,并返回**实际**而非估算的执行信息。

```sql
EXPLAIN ANALYZE
SELECT * FROM user u JOIN order o ON u.id = o.user_id
WHERE u.create_dt > '2025-01-01';
```

输出示例:

```text
-> Nested loop inner join  (cost=850 rows=5000) (actual time=0.123..45.6 rows=4800)
    -> Index range scan on u using idx_create_dt  (cost=120 rows=200) (actual time=0.05..5.2 rows=180)
    -> Index lookup on o using idx_user_id (user_id=u.id)  (cost=3.5 rows=25) (actual time=0.08..0.2 rows=26.7)
```

### 2. 关键指标解读

| 字段 | 含义 |
|------|------|
| **cost** | 优化器估算的成本 |
| **rows** | 实际返回的行数(不是估算) |
| **actual time** | 实际耗时(开始..返回) |
| **loops** | 循环次数(NLJ 时驱动表每行触发一次) |
| **actual rows × loops** | 该步骤处理的总行数 |

```text
时间解读:
actual time = 0.123..45.6
            ↑   ↑
            │   └─ 平均返回时间(单位:ms)
            └─ 首次返回时间

示例:
-> Index range scan on u (actual time=0.05..5.2 rows=180)
表示:索引扫描从 0.05ms 开始,平均 5.2ms 返回 180 行
```

### 3. EXPLAIN vs EXPLAIN ANALYZE 对比

| 维度 | EXPLAIN | EXPLAIN ANALYZE |
|------|---------|-----------------|
| 是否真正执行 | 否 | **是** |
| rows | 估算 | **实际** |
| 耗时 | 无 | **实际** |
| 适用 | 任何 SQL | **不可用于会修改数据的 SQL** |
| 性能开销 | 几乎无 | 有实际开销 |

```sql
-- 注意:EXPLAIN ANALYZE 不能用于 INSERT/UPDATE/DELETE(8.0)
EXPLAIN ANALYZE UPDATE user SET age = 21 WHERE id = 1;  -- 错误
EXPLAIN ANALYZE DELETE FROM user WHERE id = 1;          -- 错误
```

### 4. 实战应用:用 EXPLAIN ANALYZE 找瓶颈

```sql
-- 一条复杂 JOIN,看每一步耗时
EXPLAIN ANALYZE
SELECT u.name, COUNT(o.id) AS order_cnt, SUM(o.amount) AS total
FROM user u
LEFT JOIN order o ON u.id = o.user_id
WHERE u.create_dt > '2025-01-01'
GROUP BY u.id
HAVING order_cnt > 5
ORDER BY total DESC
LIMIT 100;

-- 输出中,找到 actual time 最大的步骤 → 重点优化
```

**解读示例**:

```text
-> Limit: 100 row(s)  (actual time=125.3..125.4 rows=100)
    -> Sort: SUM(o.amount) DESC  (actual time=125.0..125.3 rows=5000)
        -> Stream results
            -> Group aggregate  (actual time=120.0..123.0 rows=5000)
                -> Nested loop left join  (actual time=2.0..80.0 rows=50000)
                    -> Index range scan on u using idx_create_dt  (actual time=0.05..5.2 rows=2000)
                    -> Index lookup on o using idx_user_id (user_id=u.id)  (actual time=0.02..0.05 rows=25)

★ Sort 步骤耗时 0.3ms(125.0-125.3)
★ Group aggregate 耗时 3ms(120.0-123.0)
★ Nested loop 耗时 78ms(2.0-80.0)  ← 主要耗时在 JOIN
→ 优化方向:减少 JOIN 数据量
```

### 5. EXPLAIN ANALYZE 的常见问题

```text
问题 1:实际行数 vs 估算行数差距大
→ 说明统计信息不准,执行 ANALYZE TABLE

问题 2:某步骤 actual time 远大于其他
→ 该步骤是瓶颈,优先优化

问题 3:loops 数字过大
→ 嵌套循环次数过多,驱动表过大

问题 4:total time 中 Sort 占比高
→ ORDER BY 字段加索引
```

---

## 五、OPTIMIZER_TRACE 优化器追踪

### 1. 什么是 OPTIMIZER_TRACE

**MySQL 5.6+** 提供,可以**记录优化器的完整决策过程**:`SQL 改写 → 候选计划 → 成本估算 → 最终选择`。

比 EXPLAIN 更详细,用于**深度优化**。

### 2. 开启与使用

```sql
-- 1. 开启
SET optimizer_trace = 'enabled=on';

-- 2. 执行 SQL
SELECT * FROM user WHERE name = '张三' AND age = 20;

-- 3. 查看追踪结果(JSON 格式)
SELECT * FROM INFORMATION_SCHEMA.OPTIMIZER_TRACE \G
```

输出结构(简化):

```json
{
  "steps": [
    {
      "join_preparation": {
        "select#": 1,
        "steps": [...]
      }
    },
    {
      "join_optimization": {
        "select#": 1,
        "steps": [
          {
            "condition_processing": {
              "condition": "WHERE name = '张三' AND age = 20",
              "transformation": "equality_propagation"
            }
          },
          {
            "ref_optimizer_key_uses": [
              { "key": "idx_name_age", "used_columns": ["name", "age"] }
            ]
          },
          {
            "considered_execution_plans": [
              {
                "plan_prefix": [...],
                "table": "user",
                "best_access_path": {
                  "considered_access_paths": [
                    { "access_type": "ref", "index": "idx_name_age", "rows": 1 }
                  ],
                  "chosen_access_path": { "access_type": "ref" }
                },
                "cost_for_plan": 1.2,
                "rows_for_plan": 1,
                "chosen": true
              }
            ]
          }
        ]
      }
    }
  ]
}
```

### 3. 核心字段含义

| 字段 | 含义 |
|------|------|
| `join_preparation` | 谓词规范化、等值传播等改写 |
| `ref_optimizer_key_uses` | 可用索引分析 |
| `considered_execution_plans` | 候选执行计划(多个) |
| `best_access_path` | 优化器为每张表选的访问路径 |
| `cost_for_plan` | 每个候选计划的成本 |
| `rows_for_plan` | 估算行数 |
| `chosen: true` | 最终被选中的计划 |

### 4. 实战:为什么优化器没选我的索引

```sql
-- 表结构
CREATE TABLE order (
    id BIGINT PRIMARY KEY,
    user_id BIGINT,
    status TINYINT,
    amount DECIMAL(10,2),
    INDEX idx_user (user_id),
    INDEX idx_status (status)
);

-- 查询
EXPLAIN SELECT * FROM order WHERE user_id = 100 AND status = 1;
-- 可能 key: idx_status(优化器认为 status 过滤更有效)

-- 用 OPTIMIZER_TRACE 找原因
SET optimizer_trace = 'enabled=on';
SELECT * FROM order WHERE user_id = 100 AND status = 1;
SELECT * FROM INFORMATION_SCHEMA.OPTIMIZER_TRACE \G

-- 查看 considered_execution_plans 部分的 cost_for_plan
-- 如果 idx_status 的 cost 更低,优化器就会选它

-- 解决方案:
-- 1) 强制走索引:FORCE INDEX(idx_user)
-- 2) 建联合索引:ADD INDEX idx_user_status (user_id, status)
```

### 5. 关闭 OPTIMIZER_TRACE

```sql
SET optimizer_trace = 'enabled=off';
SET optimizer_trace_max_mem_size = 16384;  -- 限制占用内存(KB)
```

### 6. OPTIMIZER_TRACE 实战解读

```json
{
  "considered_execution_plans": [
    {
      "plan_prefix": [],
      "table": "order",
      "best_access_path": {
        "considered_access_paths": [
          {
            "access_type": "ref",
            "index": "idx_user",
            "rows": 100,
            "cost": 120
          },
          {
            "access_type": "ref",
            "index": "idx_status",
            "rows": 3000000,
            "cost": 35000
          },
          {
            "access_type": "ALL",
            "rows": 10000000,
            "cost": 1000000
          }
        ]
      },
      "cost_for_plan": 120,
      "rows_for_plan": 100,
      "chosen": true
    }
  ]
}
```

**解读**:
- 三个候选路径:`idx_user`(cost=120)、`idx_status`(cost=35000)、`ALL`(cost=1000000)
- 优化器选 cost 最小的 `idx_user`
- 如果你想让 `idx_user` 优先,但实际选了别的,说明 cost 估算有偏差

---

## 六、SQL 优化的常见手法

### 1. 避免 SELECT *

**反例**:

```sql
SELECT * FROM user WHERE name = '张三';
-- 拉所有列,可能触发回表
```

**正例**:

```sql
SELECT id, name FROM user WHERE name = '张三';
-- 正好覆盖索引,无需回表
```

**理由**:
- 用不到字段也会被拉取,浪费 IO 和网络
- 无法使用覆盖索引
- 表结构变更时 `SELECT *` 容易出现莫名其妙的问题

**对比**:

```sql
-- 表结构
CREATE TABLE user (id INT PRIMARY KEY, name VARCHAR(64), age INT,
                   email VARCHAR(128), city VARCHAR(64), INDEX idx_name (name));

-- SELECT * 会触发回表
EXPLAIN SELECT * FROM user WHERE name = '张三';
-- type: ref, key: idx_name, Extra: (无 Using index)  ← 触发回表

-- 只查索引列 + 主键 = 覆盖索引
EXPLAIN SELECT id, name FROM user WHERE name = '张三';
-- type: ref, key: idx_name, Extra: Using index  ← ★ 覆盖索引,无需回表
```

### 2. 小表驱动大表

**原则**:**用小的结果集驱动大的结果集**(JOIN 中,数据量少的表放在前面)。

```sql
-- 案例:user 表 1 万行,order 表 1 亿行
-- 反例:大表驱动小表
SELECT * FROM order o LEFT JOIN user u ON o.user_id = u.id;

-- 正例:小表驱动大表(优化器通常会自动选择)
SELECT * FROM user u LEFT JOIN order o ON u.id = o.user_id;
```

**核心逻辑**:

```text
小表驱动大表:
  for each row in 小表:
      for each match in 大表 using index:  ← 大表有索引
          output

大表驱动小表:
  for each row in 大表:
      for each match in 小表:
          output

★ 前者:外层循环少(10000 次),每次内层走索引
★ 后者:外层循环多(1亿次),即使内层快,总开销也大
```

**强制小表驱动大表**:

```sql
-- STRAIGHT_JOIN 强制按声明顺序 JOIN(不优化)
SELECT STRAIGHT_JOIN u.*, o.*
FROM user u JOIN order o ON u.id = o.user_id;
```

### 3. 索引覆盖

```sql
CREATE TABLE user (id INT PRIMARY KEY, name VARCHAR(64), age INT,
                   INDEX idx_name_age (name, age));

-- 反例:触发回表
SELECT * FROM user WHERE name = '张三';
-- Extra: NULL(全字段,触发回表)

-- 正例:覆盖索引
SELECT id, name, age FROM user WHERE name = '张三';
-- Extra: Using index  ← ★ 覆盖索引
```

### 4. 用 UNION ALL 代替 UNION(允许重复时)

```sql
-- UNION 会去重,需要排序去重,代价大
SELECT id FROM user WHERE age = 20
UNION
SELECT id FROM user WHERE status = 1;

-- 改成 UNION ALL(不去重)
SELECT id FROM user WHERE age = 20
UNION ALL
SELECT id FROM user WHERE status = 1;
```

### 5. 拆分复杂 JOIN

```sql
-- 反例:5 张表 JOIN,中间结果爆炸
SELECT *
FROM a JOIN b ON a.id = b.aid
JOIN c ON b.id = c.bid
JOIN d ON c.id = d.cid
JOIN e ON d.id = e.did
WHERE a.create_dt > '2025-01-01';

-- 正例:拆成多次查询,应用层合并
SELECT * FROM a WHERE create_dt > '2025-01-01';  -- 100 行
-- → 应用层拿到 100 个 id,再查 b
SELECT * FROM b WHERE aid IN (...);  -- 100 个 id
-- → 应用层拿到,再查 c
-- ...
```

### 6. 避免 OR 改用 UNION

```sql
-- 反例:OR 可能导致索引失效
EXPLAIN SELECT * FROM user WHERE name = '张三' OR age = 20;
-- 可能 type: ALL(全表扫描)

-- 正例:UNION ALL 拆分
EXPLAIN
SELECT * FROM user WHERE name = '张三'
UNION ALL
SELECT * FROM user WHERE age = 20 AND name != '张三';
-- 两个查询各自走索引,再用 UNION ALL 合并
```

### 7. 避免函数操作字段

```sql
-- 反例:索引列用函数
SELECT * FROM user WHERE DATE(create_dt) = '2025-01-01';
-- type: ALL (函数破坏索引)

-- 正例:范围查询
SELECT * FROM user
WHERE create_dt >= '2025-01-01' AND create_dt < '2025-01-02';
-- type: range, key: idx_create_dt
```

### 8. 优化 LIKE(避免前缀%)

```sql
-- 反例:前导模糊,索引失效
EXPLAIN SELECT * FROM user WHERE name LIKE '%张%';
-- type: ALL

-- 正例:后缀模糊,索引生效
EXPLAIN SELECT * FROM user WHERE name LIKE '张%';
-- type: range, key: idx_name

-- 真的需要全字段模糊:用 FULLTEXT 全文索引
EXPLAIN SELECT * FROM user WHERE MATCH(name) AGAINST('张' IN BOOLEAN MODE);
```

### 9. 优化 ORDER BY(利用索引排序)

```sql
CREATE TABLE t (a INT, b INT, c INT, INDEX idx_a_b (a, b));

-- 反例:索引不能直接用
EXPLAIN SELECT * FROM t WHERE a = 1 ORDER BY c;
-- Extra: Using filesort

-- 正例:命中索引排序
EXPLAIN SELECT * FROM t WHERE a = 1 ORDER BY b;
-- Extra: Using index   (无需排序)
```

### 10. 优化 GROUP BY

**松散索引扫描(Loose Index Scan)**:优化器发现 GROUP BY 列在最左前缀就能直接分组。

```sql
CREATE TABLE t (a INT, b INT, c INT, INDEX idx_a_b_c (a, b, c));

-- ★ 松散索引扫描:无需扫描所有数据
EXPLAIN SELECT a, MIN(b) FROM t GROUP BY a;
-- type: range, Extra: Using index for group-by

-- ★ 反例:GROUP BY 不在最左前缀
EXPLAIN SELECT b, COUNT(*) FROM t GROUP BY b;
-- type: ALL, Extra: Using temporary; Using filesort
```

**紧凑索引扫描(Tight Index Scan)**:必须扫描整个范围内的数据。

```sql
-- a 范围查询 + GROUP BY a,b:无法松散扫描
EXPLAIN SELECT a, b, COUNT(*) FROM t WHERE a > 10 GROUP BY a, b;
-- Extra: Using index for group-by (紧凑扫描)
```

### 11. 优化 LIMIT 分页(延迟关联)

**问题场景**:深分页性能差。

```sql
-- 反例:LIMIT 1000000, 20 → 扫 100 万行
SELECT * FROM user ORDER BY id LIMIT 1000000, 20;

-- 正例 1:延迟关联(用索引覆盖,再回表)
SELECT u.*
FROM user u
INNER JOIN (SELECT id FROM user ORDER BY id LIMIT 1000000, 20) AS t
ON u.id = t.id;

-- ★ 延迟关联:子查询只查 id 走覆盖索引,再 JOIN 取全部列

-- 正例 2:记录上次位置(性能最优)
SELECT * FROM user WHERE id > 1000000 ORDER BY id LIMIT 20;
-- ★ 直接走主键索引,O(1)
```

**深度分页性能对比**:

| 方法 | 扫描行数 | 性能 |
|------|---------|------|
| `LIMIT 1000000, 20` | 1000020 | 极差 |
| 延迟关联 | 1000020(子查询)+ 20(JOIN) | 较好 |
| `WHERE id > X LIMIT 20` | 20 | **最优** |

### 12. 优化 IN / EXISTS / JOIN 顺序

```sql
-- IN:适合内表较小
SELECT * FROM user WHERE id IN (SELECT user_id FROM order WHERE amount > 1000);
-- 优化器会先执行子查询,得 user_id 列表,再去 user 表查

-- EXISTS:适合外表小
SELECT u.* FROM user u
WHERE EXISTS (SELECT 1 FROM order o WHERE o.user_id = u.id AND o.amount > 1000);
-- 外表每行,判断子查询是否有结果

-- 推荐:通常 IN 优于 EXISTS(MySQL 已做大量优化)
```

**三者的本质区别**:

```text
IN:        子查询结果集 → 物化 → 外表去匹配 → 半连接
EXISTS:    外表每行 → 子查询 → 是否存在 → 早停
JOIN:      直接合并两张表 → 在合并结果上过滤

★ 外表小 → EXISTS 更优(早停)
★ 内表小 → IN 更优(物化结果集小)
★ 需要去重 → JOIN
```

---

## 七、子查询优化

### 1. 子查询的痛点

**MySQL 5.5 之前**,子查询效率极低(每行都执行一次),5.6+ 引入**子查询优化**(物化、半连接)。

### 2. 相关子查询 → 改 JOIN

```sql
-- 反例:相关子查询(DEPENDENT SUBQUERY)
EXPLAIN SELECT u.* FROM user u
WHERE u.id IN (SELECT o.user_id FROM order o WHERE o.amount > 1000);
-- select_type: DEPENDENT SUBQUERY  ← 性能差

-- 正例:JOIN 改写
EXPLAIN SELECT DISTINCT u.* FROM user u
INNER JOIN order o ON u.id = o.user_id
WHERE o.amount > 1000;
-- join 类型:eq_ref,性能更优
```

### 3. IN → JOIN

```sql
-- 反例
SELECT * FROM user
WHERE id IN (SELECT user_id FROM order WHERE amount > 1000);

-- 正例
SELECT DISTINCT u.*
FROM user u
INNER JOIN order o ON u.id = o.user_id
WHERE o.amount > 1000;
```

### 4. 标量子查询优化

```sql
-- 反例:每行都执行一次子查询
SELECT
    u.id, u.name,
    (SELECT COUNT(*) FROM order o WHERE o.user_id = u.id) AS order_cnt
FROM user u;

-- 正例 1:JOIN + GROUP BY(更优)
SELECT u.id, u.name, COUNT(o.id) AS order_cnt
FROM user u
LEFT JOIN order o ON u.id = o.user_id
GROUP BY u.id;

-- 正例 2:用 LEFT JOIN + 子查询物化
SELECT u.id, u.name, COALESCE(t.cnt, 0) AS order_cnt
FROM user u
LEFT JOIN (
    SELECT user_id, COUNT(*) AS cnt FROM order GROUP BY user_id
) t ON u.id = t.user_id;
```

### 5. MySQL 8.0 子查询优化策略

| 策略 | 说明 |
|------|------|
| **Semi Join(半连接)** | `IN/EXISTS` 子查询转 JOIN,自动触发 |
| **Materialization(物化)** | 子查询结果存入临时表,8.0 默认开启 |
| **Subquery to JOIN** | 5.6+ 自动尝试将某些子查询改写为 JOIN |

```sql
-- 8.0 中查看是否用了物化
EXPLAIN SELECT * FROM user WHERE id IN
(SELECT user_id FROM order WHERE amount > 1000);
-- select_type: MATERIALIZED  ← 物化生效
```

**半连接适用条件**:

```text
半连接触发条件(全部满足):
1. IN / EXISTS 子查询
2. 子查询可以用 JOIN 改写
3. 子查询无聚合函数
4. 子查询无 LIMIT
5. 子查询无 UNION

否则会退化为 DEPENDENT SUBQUERY 或物化
```

---

## 八、JOIN 优化

### 1. 驱动表的选择

**驱动表(Driving Table)**:JOIN 时**第一张被访问**的表,**每行触发一次被驱动表的查找**。

```text
NLJ 流程:
for each row in 驱动表:
    for each match in 被驱动表 using index:
        output

★ 驱动表选小表,被驱动表必须能走索引
```

```sql
-- 优化器通常自动选择,但可手动干预
SELECT STRAIGHT_JOIN u.*, o.*
FROM user u JOIN order o ON u.id = o.user_id;
-- ★ STRAIGHT_JOIN:强制按声明顺序 JOIN(不优化)
```

**优化器选择驱动表的依据**:

```text
成本估算:
1. 每张表选最佳访问路径(根据索引)
2. 比较 NLJ 的总成本
3. 总成本最小的 JOIN 顺序作为最终计划

★ 通常:全表扫描的表作为驱动表(因为无需再用索引)
★ 通常:行数少的表作为驱动表
```

### 2. 三种 JOIN 算法

#### (1) NLJ(Nested Loop Join,嵌套循环)

**经典算法,MySQL 8.0 之前默认**。

```text
for row_a in 驱动表:                  ← 100 行
    for row_b in 被驱动表:            ← 1万行
        if row_a.join_key = row_b.join_key:
            output(row_a, row_b)
★ 总比较次数 = 100 × 1万 = 100万
```

```sql
-- EXPLAIN 输出:NLJ
EXPLAIN SELECT * FROM user u JOIN order o ON u.id = o.user_id;
-- Extra: (无 join buffer 字样)
```

#### (2) BNL(Block Nested Loop,块嵌套循环)

**被驱动表无索引时**,用 join buffer 减少比较次数。

```text
for block in 驱动表(每次读一批到 join buffer):
    for row_b in 被驱动表(全表):
        批量比较 join buffer 中的所有行
        (减少内层循环的驱动表行数访问)
```

```sql
-- EXPLAIN 输出:BNL
EXPLAIN SELECT * FROM user u JOIN order o ON u.name = o.user_name;
-- Extra: Using join buffer (block nested loop)
```

#### (3) Hash Join(MySQL 8.0.18+ 默认)

**MySQL 8.0.20+** 对**等值 JOIN 且无索引**时自动使用。

```text
Step 1: 对驱动表构建哈希表
Step 2: 扫描被驱动表,每行用哈希查找匹配
★ 时间复杂度 O(M + N),比 BNL 更快
```

```sql
-- 8.0.18+:Hash Join 默认开启
EXPLAIN SELECT * FROM user u JOIN order o ON u.name = o.user_name;
-- Extra: Using join buffer (hash join)   ← ★ 8.0 新特性

-- 控制开关(默认 ON)
SET optimizer_switch = 'hash_join=on';
SET optimizer_switch = 'hash_join=off';
SET optimizer_switch = 'block_nested_loop=on';
```

### 3. 三种 JOIN 算法对比

| 算法 | 时间复杂度 | 适用场景 | 特点 |
|------|----------|---------|------|
| NLJ | O(M × N) | **被驱动表有索引** | 最常用,MySQL 一直支持 |
| BNL | O(M × N/buf) | 被驱动表无索引,join buffer 优化 | 减少内层 IO |
| Hash Join | O(M + N) | 等值 JOIN,被驱动表无索引 | **8.0.18+ 最优** |

### 4. JOIN 优化建议

| 建议 | 说明 |
|------|------|
| **被驱动表必须有索引** | JOIN 字段建索引,否则退化为 BNL/全表 |
| 小表驱动大表 | 优化器自动选,可用 `STRAIGHT_JOIN` 强制 |
| 减少 JOIN 数量 | ≤ 3 张表,过多考虑反范式或拆分 |
| 优先使用 INNER JOIN | 性能优于 OUTER JOIN |
| 索引覆盖 SELECT 列 | 避免回表 |

```sql
-- 反例:JOIN 字段没索引
CREATE TABLE user (id INT PRIMARY KEY, name VARCHAR(64));
CREATE TABLE order (id INT PRIMARY KEY, user_name VARCHAR(64));  -- 没索引!

EXPLAIN SELECT * FROM user u JOIN order o ON u.name = o.user_name;
-- type: ALL, Extra: Using join buffer (block nested loop)  ← 性能差

-- 正例:加索引
ALTER TABLE order ADD INDEX idx_user_name (user_name);
EXPLAIN SELECT * FROM user u JOIN order o ON u.name = o.user_name;
-- order type: ref, key: idx_user_name   ← 性能大幅提升
```

### 5. JOIN 实战优化案例

```sql
-- 案例:统计每个用户的订单数和总金额

-- 反例(子查询,3 次扫描 user 表)
SELECT
    u.id, u.name,
    (SELECT COUNT(*) FROM order o WHERE o.user_id = u.id) AS cnt,
    (SELECT SUM(amount) FROM order o WHERE o.user_id = u.id) AS total
FROM user u;

-- 正例(JOIN,1 次扫描 user,1 次扫描 order)
SELECT u.id, u.name, COUNT(o.id) AS cnt, COALESCE(SUM(o.amount), 0) AS total
FROM user u
LEFT JOIN order o ON u.id = o.user_id
GROUP BY u.id, u.name;
```

---

## 九、ORDER BY 排序优化

### 1. 两种排序算法

**Using filesort** 不一定意味着"文件",MySQL 在内存不足时才用磁盘。

#### (1) 双路排序(回表排序)

**老版本算法(MySQL 4.1 之前)**。

```text
Step 1: 取出排序字段 + 主键 → 排序 → 得到有序的主键列表
Step 2: 按主键列表回表取其他列

特点:两次 IO(先取排序字段,再回表)
```

#### (2) 单路排序(不回表排序)

**MySQL 4.1+** 的优化,一次性取出所有列,在内存排序。

```text
Step 1: 一次性取出所有列 → 内存排序 → 返回

特点:一次 IO,但占用内存大(数据多时可能超过 sort_buffer)
```

### 2. filesort 触发条件

```sql
-- 触发 filesort(无合适索引)
EXPLAIN SELECT * FROM user ORDER BY age;
-- Extra: Using filesort

-- 不触发 filesort(索引有序)
EXPLAIN SELECT * FROM user ORDER BY id;
-- type: index, key: PRIMARY, Extra: (无 filesort)
```

### 3. filesort 优化建议

```sql
-- 1. 增加 sort_buffer_size(默认 256K)
SET GLOBAL sort_buffer_size = 2 * 1024 * 1024;  -- 2MB

-- 2. 增加 max_length_for_sort_data(超过则用双路)
SET max_length_for_sort_data = 4096;

-- 3. 减少 SELECT 字段(避免超过 sort_buffer_size 限制)
--    用覆盖索引避免排序

-- 4. 索引列顺序与 ORDER BY 一致
CREATE INDEX idx_a_b ON t(a, b);
SELECT * FROM t ORDER BY a, b;  -- 不 filesort

-- 5. WHERE + ORDER BY 一致
SELECT * FROM t WHERE a = 1 ORDER BY b;  -- 不 filesort
```

### 4. ORDER BY 索引命中规则

```sql
CREATE TABLE t (a INT, b INT, c INT, INDEX idx_a_b (a, b));

-- 命中
EXPLAIN SELECT * FROM t WHERE a = 1 ORDER BY b;  -- ✓

-- 部分命中(a)
EXPLAIN SELECT * FROM t WHERE a = 1 ORDER BY a, b;  -- ✓

-- 失效
EXPLAIN SELECT * FROM t ORDER BY b;  -- ✗ (跳 a)

-- 方向不一致失效
EXPLAIN SELECT * FROM t ORDER BY a ASC, b DESC;  -- ✗

-- 8.0+ 用 DESC 索引
ALTER TABLE t ADD INDEX idx_a_b_desc (a ASC, b DESC);
EXPLAIN SELECT * FROM t ORDER BY a ASC, b DESC;  -- ✓
```

### 5. GROUP BY 排序

```sql
-- GROUP BY 默认会排序
EXPLAIN SELECT city, COUNT(*) FROM user GROUP BY city;
-- Extra: Using filesort  ← 默认排序

-- 8.0+ 可关闭默认排序
EXPLAIN SELECT city, COUNT(*) FROM user GROUP BY city ORDER BY NULL;
-- Extra: (无 filesort)  ← 不排序,更快
```

---

## 十、慢查询排查实战案例

### 案例 1:全表扫描(LIKE 前缀%)

**问题 SQL**(执行 8 秒):

```sql
SELECT * FROM article WHERE content LIKE '%MySQL 优化%';
```

**EXPLAIN 输出**:

```text
id=1, type=ALL, key=NULL, rows=1000000, Extra=Using where
```

**诊断**:content 无全文索引,前导 `%` 导致全表扫描。

**解决**:

```sql
-- 加全文索引
ALTER TABLE article ADD FULLTEXT INDEX ft_content (content) WITH PARSER ngram;

-- 改写 SQL
SELECT * FROM article
WHERE MATCH(content) AGAINST('MySQL 优化' IN BOOLEAN MODE);
```

**改后 EXPLAIN**:

```text
type=fulltext, key=ft_content, rows=1
```

### 案例 2:函数破坏索引

**问题 SQL**(执行 5 秒):

```sql
SELECT * FROM order WHERE DATE(create_dt) = '2025-01-01';
```

**EXPLAIN 输出**:

```text
type=ALL, key=NULL, rows=10000000
```

**诊断**:`DATE()` 函数让索引失效。

**解决**:

```sql
SELECT * FROM order
WHERE create_dt >= '2025-01-01 00:00:00'
  AND create_dt < '2025-01-02 00:00:00';
```

**改后 EXPLAIN**:

```text
type=range, key=idx_create_dt, rows=50000
```

### 案例 3:JOIN 字段无索引

**问题 SQL**(执行 30 秒):

```sql
SELECT u.name, o.amount
FROM user u JOIN order o ON u.name = o.receiver_name
WHERE u.create_dt > '2025-01-01';
```

**EXPLAIN 输出**:

```text
user: type=range, key=idx_create_dt, rows=2000
order: type=ALL, key=NULL, rows=10000000, Extra=Using join buffer (block nested loop)
```

**诊断**:order 表的 receiver_name 无索引,BNL 性能差。

**解决**:

```sql
ALTER TABLE order ADD INDEX idx_receiver_name (receiver_name);
```

**改后 EXPLAIN**:

```text
user: type=range, rows=2000
order: type=ref, key=idx_receiver_name, rows=5  ← ★ 数量大幅减少
```

### 案例 4:深分页性能差

**问题 SQL**(执行 12 秒):

```sql
SELECT * FROM article ORDER BY create_dt DESC LIMIT 1000000, 20;
```

**EXPLAIN 输出**:

```text
type=index, key=idx_create_dt, rows=1000020, Extra=Using filesort
```

**诊断**:虽然走索引,但要扫 100 万行再 LIMIT。

**解决**:

```sql
-- 方案 1:延迟关联
SELECT a.*
FROM article a
INNER JOIN (SELECT id FROM article ORDER BY create_dt DESC LIMIT 1000000, 20) AS t
ON a.id = t.id;

-- 方案 2:记录上次位置(最优)
SELECT * FROM article
WHERE create_dt < '2025-08-14 10:00:00'  -- 上次最后一条的 create_dt
ORDER BY create_dt DESC LIMIT 20;
```

### 案例 5:ORDER BY 触发 filesort

**问题 SQL**(执行 3 秒):

```sql
SELECT * FROM user WHERE age > 18 ORDER BY create_dt;
```

**EXPLAIN 输出**:

```text
type=range, key=idx_age, rows=800000, Extra=Using where; Using filesort
```

**诊断**:age 走索引,但 ORDER BY create_dt 触发 filesort。

**解决**:

```sql
-- 建联合索引(把 WHERE 和 ORDER BY 都覆盖)
ALTER TABLE user ADD INDEX idx_age_create (age, create_dt);

-- 改后 EXPLAIN:
-- type=range, key=idx_age_create, Extra=Using where   ← ★ 无 filesort
```

### 案例 6:GROUP BY 临时表

**问题 SQL**(执行 6 秒):

```sql
SELECT city, COUNT(*) FROM user GROUP BY city;
```

**EXPLAIN 输出**:

```text
type=ALL, key=NULL, rows=1000000, Extra=Using temporary
```

**诊断**:无索引导致 GROUP BY 用临时表。

**解决**:

```sql
ALTER TABLE user ADD INDEX idx_city (city);

-- 改后 EXPLAIN:
-- type=index, key=idx_city, Extra=Using index   ← ★ 临时表消失
```

### 案例 7:慢查询排查完整流程

```text
Step 1: 慢查询日志发现
        slow.log: Query_time: 8.5  Lock_time: 0.0
        SELECT * FROM order WHERE DATE(create_dt) = '2025-08-14'

Step 2: 用 mysqldumpslow 找 TOP SQL
        mysqldumpslow -s t -t 10 slow.log

Step 3: EXPLAIN 分析
        EXPLAIN SELECT * FROM order WHERE DATE(create_dt) = '2025-08-14';
        → type: ALL, key: NULL  ← 全表扫描

Step 4: 定位原因
        DATE(create_dt) 函数破坏索引

Step 5: 优化
        SELECT * FROM order
        WHERE create_dt >= '2025-08-14' AND create_dt < '2025-08-15';

Step 6: 验证
        EXPLAIN ... → type: range, key: idx_create_dt
        实际执行时间: 0.02s  ← 从 8.5s 降到 0.02s

Step 7: 检查业务是否有其他类似 SQL
        grep "DATE(create_dt)" src/
        全部改写,提交 PR
```

### 案例 8:复杂 JOIN 优化

**问题 SQL**(执行 25 秒):

```sql
SELECT u.name, COUNT(o.id), SUM(o.amount)
FROM user u
LEFT JOIN order o ON u.id = o.user_id
LEFT JOIN payment p ON o.id = p.order_id
WHERE u.create_dt > '2025-01-01'
  AND o.status = 1
GROUP BY u.id
HAVING COUNT(o.id) > 5
ORDER BY SUM(o.amount) DESC
LIMIT 100;
```

**EXPLAIN ANALYZE 输出**:

```text
-> Limit: 100 row(s)
    -> Sort: SUM(o.amount) DESC
        -> Table scan on <temporary>
            -> Aggregate using temporary table
                -> Nested loop left join
                    -> Nested loop left join
                        -> Index range scan on u using idx_create_dt
                            (actual time=0.05..5.2 rows=2000)
                        -> Index lookup on o using idx_user_id
                            (actual time=0.08..0.2 rows=25)
                    -> Index lookup on p using idx_order_id
                        (actual time=0.05..0.15 rows=3)

→ 问题:最后 GROUP BY + HAVING + ORDER BY 全部在内存临时表里做,数据量大
```

**优化方案**:

```sql
-- 1. 建复合索引
ALTER TABLE order ADD INDEX idx_user_status (user_id, status);
ALTER TABLE payment ADD INDEX idx_order_id (order_id);

-- 2. 先过滤再 JOIN(应用层拆分)
-- 简化 SQL,只查需要的列
SELECT u.id, u.name, t.cnt, t.total
FROM user u
INNER JOIN (
    SELECT user_id, COUNT(*) AS cnt, SUM(amount) AS total
    FROM order
    WHERE status = 1
      AND create_dt > '2025-01-01'
    GROUP BY user_id
    HAVING cnt > 5
    ORDER BY total DESC
    LIMIT 100
) t ON u.id = t.user_id;

-- → 子查询先缩小数据,再 JOIN
```

### 案例 9:用 sys schema 找问题 SQL

```sql
-- 1. 找最耗时的 SQL
SELECT * FROM sys.statement_analysis
ORDER BY total_latency DESC LIMIT 10;

-- 2. 找全表扫描的表
SELECT * FROM sys.schema_tables_with_full_table_scans
WHERE rows_scanned > 1000000;

-- 3. 找 IO 最大的文件
SELECT file, total_read, total_write
FROM sys.io_global_by_file_by_bytes
ORDER BY total_read + total_write DESC LIMIT 10;

-- 4. 找有问题的索引使用
SELECT * FROM sys.schema_index_statistics
ORDER BY rows_selected DESC LIMIT 10;
```

### 案例 10:OR 导致索引失效

**问题 SQL**(执行 4 秒):

```sql
SELECT * FROM user WHERE name = '张三' OR age = 20;
```

**EXPLAIN 输出**:

```text
type=index_merge, key=idx_name,idx_age, Extra=Using union(idx_name,idx_age); Using where
```

**诊断**:用了 index_merge,但仍扫了 80 万行。

**解决**:

```sql
-- 用 UNION ALL 拆分
EXPLAIN
SELECT * FROM user WHERE name = '张三'
UNION ALL
SELECT * FROM user WHERE age = 20 AND name != '张三';

-- 改后:每个子查询都走 ref,行数大幅减少
```

### 案例 11:不当 IN 导致性能差

**问题 SQL**(执行 7 秒):

```sql
SELECT * FROM user
WHERE id IN (1, 2, 3, ..., 10000);
```

**EXPLAIN 输出**:

```text
type=range, key=PRIMARY, rows=10000
```

**诊断**:IN 列表太大,range 扫描 1 万行主键。

**解决**:

```sql
-- 方案 1:先确认是否真的需要这么多 ID(可能业务有 bug)
-- 方案 2:分批查询
-- 方案 3:改为 JOIN

SELECT u.*
FROM user u
INNER JOIN (
    SELECT id FROM tmp_user_ids  -- 临时表
) t ON u.id = t.id;
```

### 案例 12:COUNT(\*) 性能差

**问题 SQL**(执行 15 秒):

```sql
SELECT COUNT(*) FROM user WHERE status = 1;
```

**EXPLAIN 输出**:

```text
type=ALL, rows=10000000  ← 优化器认为全表扫描更快
```

**诊断**:status 选择性低(只有 3 个值),优化器放弃索引。

**解决**:

```sql
-- 方案 1:用近似值(8.0+)
SELECT TABLE_ROWS FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_NAME = 'user';  -- 不精确,但极快

-- 方案 2:用 Redis 计数器(精确,极快)

-- 方案 3:维护独立计数表

-- 方案 4:用 force index(不推荐)
EXPLAIN SELECT COUNT(*) FROM user FORCE INDEX (idx_status) WHERE status = 1;
```

---

## 十一、SQL 优化 Checklist

### 排查流程

```text
□ 1. 慢查询日志定位问题 SQL
□ 2. EXPLAIN 查看执行计划
□ 3. 检查 type 字段(是否 ALL/index)
□ 4. 检查 key 字段(是否走了索引)
□ 5. 检查 key_len(是否用上复合索引)
□ 6. 检查 rows(预估行数)
□ 7. 检查 Extra(Using filesort / temporary / index 等)
□ 8. 用 EXPLAIN ANALYZE 获取实际执行数据
□ 9. 用 OPTIMIZER_TRACE 找优化器决策原因
□ 10. 针对性优化(改写 / 加索引 / 拆分)
□ 11. 重新 EXPLAIN 验证
□ 12. 上线观察
```

### 索引相关

```text
□ 13. WHERE 字段是否有合适索引
□ 14. ORDER BY 字段能否用上索引
□ 15. GROUP BY 字段是否有索引
□ 16. JOIN 字段是否有索引
□ 17. 是否有索引失效(函数/类型转换/前导%)
□ 18. 是否有冗余/重复索引
□ 19. 索引选择性是否合理
```

### SQL 写法

```text
□ 20. 避免 SELECT *
□ 21. 小表驱动大表
□ 22. 避免函数操作字段
□ 23. UNION ALL 替代 UNION
□ 24. 深分页用延迟关联
□ 25. 子查询改 JOIN
□ 26. 拆分复杂 JOIN
□ 27. 避免 OR,改 UNION ALL
```

### 性能监控

```text
□ 28. 开启 slow_query_log
□ 29. 定期 ANALYZE TABLE 更新统计信息
□ 30. 监控 sys.statement_analysis
□ 31. 监控全表扫描表
□ 32. 监控未使用索引
```

### 配置参数调优

```ini
# /etc/my.cnf
[mysqld]
# 慢查询
slow_query_log = ON
long_query_time = 1
log_queries_not_using_indexes = ON

# 排序缓冲(单路排序优化)
sort_buffer_size = 2M
max_length_for_sort_data = 4096

# JOIN 缓冲(BNL/Hash Join)
join_buffer_size = 4M

# 统计信息
innodb_stats_persistent = ON
innodb_stats_persistent_sample_pages = 20
```

---

## 十二、核心要点速记

### EXPLAIN 核心字段

```text
★ id           执行顺序(相同从上到下,不同大先执行)
★ select_type  查询类型(SIMPLE / PRIMARY / SUBQUERY / MATERIALIZED)
★ type         访问类型(性能:system > const > eq_ref > ref > range > index > ALL)
★ possible_keys 候选索引
★ key          实际使用的索引
★ key_len      索引使用字节数(反映命中复合索引列数)
★ ref          索引匹配条件
★ rows         估算扫描行数
★ filtered     Server 层过滤百分比
★ Extra        额外信息(Using index / filesort / temporary / join buffer)
```

### type 性能排序(从优到劣)

```text
system > const > eq_ref > ref > range > index > ALL
                                      ↑
                                  尽量优化

★ const/eq_ref: 优秀,无需担心
★ ref: 良好
★ range: 可接受
★ index: 需考虑优化
★ ALL: 必须优化
```

### Extra 关键标志

```text
✅ Using index                  覆盖索引,无需回表
✅ Using index condition         ICP 索引下推
✅ Using MRR                     顺序 IO 优化
✅ Select tables optimized away  直接出结果(MIN/MAX/COUNT)
⚠️ Using where                  Server 层过滤
⚠️ Using join buffer            JOIN 缓冲(检查 JOIN 字段索引)
❌ Using temporary              临时表(常见 GROUP BY 无索引)
❌ Using filesort               文件排序(需 ORDER BY 索引)
```

### SQL 优化口诀

```text
        SELECT 别用 *    覆盖索引最优
        函数计算远离    索引才不失效
        小表驱动大表    NLJ 效率高
        OR 改 UNION    索引能走
        深分页用延迟    千万级无忧
        索引设计三原则:等值在前,范围在后,覆盖查询
```

### 工具速查

```sql
-- 慢查询日志
SET slow_query_log = ON;
SET long_query_time = 1;

-- EXPLAIN 三种格式
EXPLAIN SELECT ...;
EXPLAIN FORMAT=TREE SELECT ...;
EXPLAIN FORMAT=JSON SELECT ...;
EXPLAIN ANALYZE SELECT ...;          -- 8.0.18+ 实际执行

-- 优化器追踪
SET optimizer_trace = 'enabled=on';
SELECT * FROM INFORMATION_SCHEMA.OPTIMIZER_TRACE;

-- 强制/建议索引
SELECT * FROM t FORCE INDEX(idx_a) WHERE ...;
SELECT * FROM t USE INDEX(idx_a) WHERE ...;

-- 统计信息
ANALYZE TABLE t;
SHOW INDEX FROM t;
SELECT * FROM sys.statement_analysis;
SELECT * FROM sys.schema_unused_indexes;
SELECT * FROM sys.schema_redundant_indexes;

-- 慢查询分析
mysqldumpslow -s t -t 10 slow.log
```

### JOIN 算法演进

```text
NLJ          嵌套循环   MySQL 一直支持,被驱动表需有索引
BNL          块嵌套循环 被驱动表无索引时用(join buffer)
Hash Join    哈希连接   MySQL 8.0.18+ 默认(等值 JOIN,无索引)
                                  ↑ 推荐
```

### ORDER BY 优化要点

```text
1. 索引列排序 → 避免 filesort
2. 索引方向一致(全 ASC 或全 DESC)
3. 8.0+ 支持 DESC 索引
4. sort_buffer_size 不够会落盘
5. 减少 SELECT 字段,降低单路排序内存占用
```

### 排查流程速记

```text
慢查询日志 → mysqldumpslow 找 TOP SQL
        ↓
EXPLAIN 查看 type / key / rows / Extra
        ↓
定位瓶颈:全表扫描?filesort?temporary?
        ↓
优化:加索引 / 改写 SQL / 拆分 JOIN
        ↓
重新 EXPLAIN + EXPLAIN ANALYZE 验证
        ↓
上线观察,持续监控
```

### 索引失效 13 场景

```text
1. 违反最左前缀       WHERE b = ?      →  WHERE a = ? AND b = ?
2. 索引列用函数       YEAR(dt) = 2025  →  dt BETWEEN ...
3. 索引列计算        age + 1 = 30      →  age = 29
4. 隐式类型转换      phone = 13800...  →  phone = '13800...'
5. 前导模糊          LIKE '%x%'        →  LIKE 'x%' 或全文索引
6. OR 滥用           a = 1 OR b = 2    →  UNION ALL
7. 范围后列          a=1 AND b>10 AND c=2  → 调整顺序或拆索引
8. 排序方向不一致    ORDER BY a, b DESC → 统一方向或 DESC 索引
9. 不等号            name != 'x'       → 重新设计查询
10. IS NOT NULL     大概率失效        → 改写
11. 数据量过少      几十行            → 正常,无需优化
12. 统计信息过期    大批量写入后      →  ANALYZE TABLE
13. 字符集不一致    表 A utf8, B utf8mb4 → 统一字符集
```
