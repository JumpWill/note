# SQL 基础与数据类型 (SQL Basics & Data Types)

## 一、SQL 分类

SQL (Structured Query Language) 是操作关系型数据库的标准语言。PostgreSQL 严格遵循 SQL 标准,按照功能划分为五大类。

### 1. DDL (Data Definition Language) — 数据定义语言

用于定义/修改数据库对象结构,**操作对象是表、库、索引、视图、函数、类型、模式**。

- `CREATE`:创建数据库、表、索引、视图、模式、函数、类型
- `ALTER`:修改表结构(加列、改类型、建索引)
- `DROP`:删除库/表/视图
- `TRUNCATE`:清空表数据(保留结构,速度比 DELETE 快)
- `COMMENT`:为对象添加注释

### 2. DML (Data Manipulation Language) — 数据操作语言

用于操作表中的**数据行**。

- `SELECT`(广义):查询数据
- `INSERT`:插入数据(支持 `INSERT ... ON CONFLICT` 实现 upsert)
- `UPDATE`:更新数据
- `DELETE`:删除数据
- `MERGE`:合并数据(PG 15+ 原生支持)
- `COPY`:批量导入/导出(性能远超 INSERT)

### 3. DQL (Data Query Language) — 数据查询语言

严格的说法,`SELECT` 单独成类,因为查询是数据库最常用的功能。

- `SELECT`:查询
- 子句:`FROM`、`WHERE`、`GROUP BY`、`HAVING`、`ORDER BY`、`LIMIT`、`OFFSET`、`FETCH`、`WITH`(CTE)、`LATERAL`

### 4. DCL (Data Control Language) — 数据控制语言

**权限管理**相关。

- `GRANT`:授予权限
- `REVOKE`:撤销权限

### 5. TCL (Transaction Control Language) — 事务控制语言

**事务**的边界与控制。PostgreSQL 的事务实现是**全功能 MVCC**,DML/DDL 都在事务内。

- `BEGIN` / `START TRANSACTION`:开启事务
- `COMMIT` / `END`:提交事务
- `ROLLBACK` / `ABORT`:回滚事务
- `SAVEPOINT`:设置保存点
- `SET TRANSACTION`:设置事务隔离级别

### 五大分类速查表

| 分类 | 全称                | 核心动词                                                  | 操作对象           | 是否需要 COMMIT |
|------|---------------------|-----------------------------------------------------------|--------------------|-----------------|
| DDL  | Data Definition     | CREATE / ALTER / DROP / TRUNCATE                          | 表、库、模式、类型 | **事务内**(原子 DDL)|
| DML  | Data Manipulation   | INSERT / UPDATE / DELETE / COPY / MERGE                   | 数据行             | 视 autocommit    |
| DQL  | Data Query          | SELECT                                                    | 数据行             | 否              |
| DCL  | Data Control        | GRANT / REVOKE                                            | 权限               | 自动提交        |
| TCL  | Transaction Control | BEGIN / COMMIT / ROLLBACK / SAVEPOINT                     | 事务               | 是              |

**关键提醒**:PostgreSQL 与 MySQL 最大区别 — **所有 DDL 都参与事务**(`CREATE TABLE` / `ALTER TABLE` / `DROP TABLE` 都可以 `ROLLBACK`)。这是 PG 的强项,大表 DDL 修改建议在事务里加超时保护:`SET LOCAL lock_timeout = '5s';`。

---

## 二、psql 命令行工具详解

### 1. 连接数据库

```bash
# 本地连接(通过 Unix 套接字,需指定数据库)
psql -d mydb
psql mydb
psql -U postgres -d mydb

# 远程连接
psql -h 127.0.0.1 -p 5432 -U postgres -d mydb

# 指定密码(不推荐,会留在历史记录里)
PGPASSWORD=secret psql -U postgres -d mydb

# 连接 URL 形式
psql "postgresql://postgres:secret@127.0.0.1:5432/mydb?sslmode=require"

# 执行单条 SQL
psql -d mydb -c "SELECT version();"

# 从文件执行
psql -d mydb -f script.sql

# 输出格式:对齐/不展开/CSV/HTML/JSON
psql -d mydb -A -F, -c "SELECT * FROM users" > users.csv
```

### 2. psql 元命令(反斜杠命令)

psql 最大的特色是丰富的反斜杠元命令,熟练使用可告别 GUI。

#### 对象查看类

| 元命令          | 作用                                        |
|-----------------|---------------------------------------------|
| `\l` / `\l+`    | 列出所有数据库                              |
| `\dt`           | 列出当前 schema 下的所有表                  |
| `\dt *.*`       | 列出所有 schema 的所有表                    |
| `\dt my_*`      | 列出匹配名称的表                            |
| `\d <table>`    | 查看表结构(列、索引、约束)                 |
| `\d+ <table>`   | 查看表结构(含存储参数、注释)               |
| `\d <table>.*`  | 只看表的列                                  |
| `\di`           | 列出索引                                    |
| `\dv`           | 列出视图                                    |
| `\dm`           | 列出物化视图                                |
| `\ds`           | 列出序列                                    |
| `\df`           | 列出函数                                    |
| `\df+ <func>`   | 查看函数定义                                |
| `\do`           | 列出操作符                                  |
| `\dx`           | 列出已安装扩展                              |
| `\dn`           | 列出所有 schema                             |
| `\dT`           | 列出类型                                    |
| `\dT+`          | 列出类型详情                                |
| `\dL`           | 列出所有语言(PL/pgSQL 等)                  |
| `\db`           | 列出表空间                                  |
| `\dg` / `\du`   | 列出角色/用户                               |
| `\dp <table>`   | 查看表的权限分配                            |
| `\dd <obj>`     | 查看对象的注释                              |

#### 实用操作类

| 元命令          | 作用                                          |
|-----------------|-----------------------------------------------|
| `\c <db>`       | 切换数据库                                    |
| `\conninfo`     | 显示当前连接信息                              |
| `\timing`       | 显示 SQL 执行耗时(强烈推荐打开)              |
| `\x`            | 切换扩展显示(行变列)                         |
| `\e`            | 打开编辑器编辑当前缓冲区                      |
| `\i <file>`     | 执行 SQL 文件                                 |
| `\o <file>`     | 把输出重定向到文件                            |
| `\copy ...`     | 客户端 COPY(读写本地文件)                    |
| `\set`          | 查看/设置变量                                 |
| `\unset`        | 取消变量                                      |
| `\?`            | 查看所有元命令                                |
| `\h <command>`  | 查看 SQL 语法帮助(如 `\h ALTER TABLE`)        |
| `\q`            | 退出 psql                                     |

#### 示例

```sql
-- 查看所有数据库(带大小)
\l+

-- 切换到 mydb 数据库
\c mydb

-- 查看当前 schema 下所有表
\dt

-- 查看 public 模式下以 user 开头的所有表
\dt user*

-- 查看 users 表结构
\d users

-- 看 users 表的列定义
\d users.*

-- 看 users 表上的索引
\di users*

-- 查看存储过程/函数
\df

-- 查看具体的函数定义
\sf calculate_total(integer, integer)

-- 查看扩展
\dx

-- 安装扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 进入扩展显示模式(看 JSON/JSONB 字段更清晰)
\x

-- 看 SQL 帮助
\h CREATE TABLE
```

### 3. 客户端增强工具

| 工具            | 特点                                                      |
|-----------------|-----------------------------------------------------------|
| **pgcli**       | 类似 mycli,语法高亮、自动补全、多行编辑,终端党首选       |
| **psql**        | 官方客户端,功能全,配合 `\x` `\timing` 也很顺手           |
| **DBeaver**     | 跨平台免费 GUI,PG 支持完善                               |
| **DataGrip**    | JetBrains 出品,智能补全顶级                              |
| **Navicat**     | 老牌商业软件                                              |
| **TablePlus**   | Mac/Win 美观                                              |
| **pgAdmin**     | 官方出品 GUI,功能最强但界面老旧                          |

```bash
# 安装 pgcli
pip install pgcli

# 使用
pgcli -U postgres -d mydb
pgcli "postgresql://postgres@localhost/mydb"
```

---

## 三、数值类型 (Numeric Types)

PostgreSQL 数值类型非常丰富,分为整数、精确数值、浮点、序列四大类,**没有 MySQL 那种 `UNSIGNED` 无符号类型**。

### 1. 整数类型

| 类型           | 存储 | 范围                                        | 典型用途            |
|----------------|------|---------------------------------------------|---------------------|
| `smallint`     | 2 字节 | -32768 ~ 32767                            | 小计数器、状态码    |
| `integer`      | 4 字节 | -2147483648 ~ 2147483647                  | **最常用主键**      |
| `bigint`       | 8 字节 | -9223372036854775808 ~ 9223372036854775807| 大表主键、雪花 ID   |

```sql
age      SMALLINT                       -- 范围足够
id       INTEGER       GENERATED ALWAYS AS IDENTITY  -- 12+ 推荐主键自增
order_id BIGINT                            -- 大表用 bigint
```

**`GENERATED ... AS IDENTITY`** 是 SQL 标准语法,自增字段推荐写法(取代 SERIAL):

```sql
CREATE TABLE t_user (
    id   INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name TEXT NOT NULL
);

-- 也可以用 BY DEFAULT 允许手动指定
id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY
```

### 2. 精确数值 `numeric` / `decimal`

**任意精度精确小数**,内部以二进制编码存储,**金额计算首选**。`numeric` 和 `decimal` 是**完全等价的同义词**。

```sql
amount NUMERIC(10, 2)    -- 最大:99999999.99
price  NUMERIC(18, 4)    -- 金融场景
ratio  NUMERIC(5, 4)     -- 0.0001 ~ 9.9999
```

- `numeric(precision, scale)`:precision 最多 1000,scale 最多 precision
- `numeric` 不带参数:任意精度,实际存储到上限为止

```sql
SELECT 0.1::NUMERIC + 0.2::NUMERIC;       -- 0.3 (精确!)
SELECT 0.1::FLOAT8 + 0.2::FLOAT8;          -- 0.30000000000000004
```

### 3. 浮点类型

| 类型               | 存储 | 范围                          | 精度      |
|--------------------|------|-------------------------------|-----------|
| `real`             | 4 字节 | ±3.4E+38                    | 单精度,~6 位 |
| `double precision` | 8 字节 | ±1.7E+308                   | 双精度,~15 位 |

```sql
weight REAL                    -- 单精度
coordinate DOUBLE PRECISION    -- 双精度(等价于 float8)
```

> **注意**:`real` 和 `double precision` 是**近似值**,存在精度丢失,**不要用于金额**。PG 也支持 `float(p)` 语法,但官方不推荐。

### 4. 序列类型 SERIAL

PostgreSQL 没有 MySQL 的 `AUTO_INCREMENT`,传统做法是 `SERIAL`(实际是 `INTEGER` + 默认序列 + 默认值的封装)。

```sql
-- 三种 SERIAL
id SMALLSERIAL    -- SMALLINT + sequence
id SERIAL         -- INTEGER + sequence
id BIGSERIAL      -- BIGINT + sequence

CREATE TABLE t_product (
    id    SERIAL PRIMARY KEY,
    name  TEXT NOT NULL
);

-- 插入
INSERT INTO t_product (name) VALUES ('Apple') RETURNING id;  -- 自动得到 1
```

**底层等价于**:

```sql
CREATE SEQUENCE t_product_id_seq;
CREATE TABLE t_product (
    id   INTEGER NOT NULL DEFAULT nextval('t_product_id_seq'),
    name TEXT,
    PRIMARY KEY (id)
);
ALTER SEQUENCE t_product_id_seq OWNED BY t_product.id;
```

**PG 10+ 推荐**:用 **`IDENTITY`** 列代替 SERIAL(标准 SQL,语义更清晰):

```sql
id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY
```

### 5. 货币类型 `money`

PostgreSQL 独有的货币类型,内部以定点小数存储,**带 locale 相关的货币符号**。

```sql
amount MONEY

-- 默认输出会带符号
SET lc_monetary = 'zh_CN.UTF-8';   -- 设置 locale
SELECT 100::MONEY;                  -- 输出:￥100.00

-- 与 numeric 的转换(注意:可能丢精度)
SELECT '100.50'::MONEY::NUMERIC;    -- 100.50
```

> **警告**:`money` 类型**强烈不推荐**,因为精度依赖 `lc_monetary`,跨数据库/跨语言处理容易出问题。生产中用 `NUMERIC(19, 4)` 即可。

### 数值类型对比表

| 类型                       | 精确/近似 | 用途               | 注意事项                          |
|----------------------------|-----------|--------------------|-----------------------------------|
| `SMALLINT` / `INT` / `BIGINT` | 精确    | 整数计数           | 无 UNSIGNED,主键常用 BIGINT       |
| `NUMERIC(p, s)`            | 精确      | 金额、科学计算     | 计算慢,大金额仍推荐               |
| `REAL` / `DOUBLE PRECISION` | 近似    | 科学计算、坐标     | 不要用于金额                      |
| `SERIAL` / `BIGSERIAL`     | 精确      | 自增主键           | PG 10+ 推荐 IDENTITY              |
| `MONEY`                    | 精确      | 货币(不推荐)      | 受 locale 影响,易出坑            |

### 数值类型典型建表示例

```sql
CREATE TABLE product (
    id          BIGINT          GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sku         VARCHAR(32)     NOT NULL,
    name        VARCHAR(128)    NOT NULL,
    price       NUMERIC(10, 2)  NOT NULL DEFAULT 0,    -- 售价(元)
    cost        NUMERIC(10, 2)  NOT NULL DEFAULT 0,    -- 成本(元)
    stock       INTEGER         NOT NULL DEFAULT 0,
    sold        INTEGER         NOT NULL DEFAULT 0,
    weight_kg   NUMERIC(8, 3),
    score       REAL,
    on_sale     BOOLEAN         NOT NULL DEFAULT TRUE,
    status      SMALLINT        NOT NULL DEFAULT 0,   -- 0=草稿 1=上架 2=下架
    UNIQUE (sku),
    COMMENT ON COLUMN product.price IS '售价(元)';
);
```

---

## 四、字符串类型 (String Types)

PostgreSQL 字符串类型简洁:**没有 MySQL 那套 TINYTEXT/TEXT/MEDIUMTEXT/LONGTEXT 套娃**,也没有 `ENUM`/`SET` 字段类型(枚举用 `CREATE TYPE`)。

### 1. 三种字符串类型

| 类型                    | 存储特性                            | 最大长度          | 适用场景                          |
|-------------------------|-------------------------------------|-------------------|-----------------------------------|
| `character varying(n)`  | 变长,带长度前缀                    | 无上限(实际受行限制,约 1GB) | 几乎所有变长文本         |
| `character(n)`          | 定长,不足补空格(空格在比较时被忽略)| 约 1GB             | 极少用                            |
| `text`                  | 变长(等价 `varchar` 但无长度限制)  | 约 1GB             | **推荐默认**                      |

```sql
name        VARCHAR(64)         -- 变长,最长 64 字符
description TEXT                -- 不限长度,推荐
country     CHAR(2)             -- 固定 2 字符(国家码)
```

### 2. 与 MySQL 的关键区别

| 维度           | MySQL                              | PostgreSQL                          |
|----------------|------------------------------------|-------------------------------------|
| 文本类型       | VARCHAR/TINYTEXT/TEXT/MEDIUMTEXT/LONGTEXT | 三个:VARCHAR / CHAR / TEXT     |
| VARCHAR 上限   | 65535 字节(行大小限制)            | 约 1GB                              |
| TEXT 上限      | 64KB                               | 约 1GB                              |
| 字符集         | utf8mb4 推荐,4 字节/字符          | 内部 UTF-8,无需指定                 |
| 默认排序       | 受表字符集影响                     | 受数据库 cluster locale 影响         |
| 空格处理       | CHAR 末尾空格保留                  | CHAR 末尾空格比较时被忽略           |
| 大小写         | 默认 `utf8mb4_0900_ai_ci` 不敏感   | 默认区分大小写(操作符级)            |
| 大小写转换     | `UPPER()` / `LOWER()`             | 同上,加 `ILIKE` 不敏感匹配          |
| 模式匹配       | `LIKE`                             | `LIKE` / `ILIKE` / POSIX 正则       |
| 字符串连接     | `CONCAT(a, b)`                     | `a || b`(标准 SQL)                  |

### 3. 转义与字面量

PG 用**单引号**包裹字符串字面量,字符串内单引号用 `''`:

```sql
SELECT 'It''s a test';            -- It's a test
SELECT E'换行符\n制表符\t';          -- 用 E 前缀开启 C 风格转义
SELECT $$ ... $$;                  -- Dollar-Quoted 字符串,函数体内常用
```

### 4. 字符串函数精选

```sql
-- 长度
LENGTH('abc')                 -- 字符数
CHAR_LENGTH('你好')           -- 字符数
OCTET_LENGTH('你好')          -- 字节数(UTF-8 下 = 6)

-- 大小写
UPPER('hello'), LOWER('HELLO'), INITCAP('hello world')

-- 修剪
TRIM('  hi  '), BTRIM('xxhi', 'x'), LTRIM(), RTRIM()

-- 子串
SUBSTRING('hello world' FROM 1 FOR 5)   -- 'hello'
LEFT('hello', 3), RIGHT('hello', 3)

-- 拼接
'hello' || ' ' || 'world'      -- 'hello world'(标准 SQL)
CONCAT('a', 'b', 'c')            -- 同上

-- 替换
REPLACE('hello', 'l', 'L')       -- 'heLLo'
OVERLAY('hello' PLACING 'XX' FROM 2 FOR 3)  -- 'heXXo'

-- 正则匹配(,~ 区分大小写, ~* 不区分)
SELECT 'hello' ~ '^h.+o$';       -- true
SELECT 'Hello' ~* '^h.+o$';      -- true
SELECT REGEXP_REPLACE('abc123', '\d+', '*');  -- 'abc*'

-- 不区分大小写 LIKE
SELECT * FROM users WHERE name ILIKE '%zhang%';
```

### 字符串类型典型建表示例

```sql
CREATE TABLE article (
    id            BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title         VARCHAR(200) NOT NULL,
    summary       VARCHAR(500),
    content       TEXT,                          -- 不用 LONGTEXT,PG 的 TEXT 够用
    cover_url     VARCHAR(255),
    author_name   VARCHAR(64),
    author_avatar VARCHAR(255),
    md5           CHAR(32)     NOT NULL,
    UNIQUE (md5)
);
```

---

## 五、二进制类型 (Binary Types)

### 1. `bytea` 类型

PostgreSQL 用 **`bytea`** 类型存储二进制数据(MySQL 的 BLOB 系列)。

```sql
avatar BYTEA
file   BYTEA

-- 插入(十六进制或转义格式)
INSERT INTO files (name, data) VALUES
('a.txt', '\x48656c6c6f'),           -- 十六进制
('b.txt', 'Hello\\x00World');         -- 转义格式(空字节用 \\x00)
```

### 2. hex 编码输出

```sql
SELECT encode(data, 'hex')    FROM files;  -- 转 hex 字符串
SELECT decode('48656c6c6f', 'hex');          -- hex 字符串转 bytea
```

支持编码:`base64`、`hex`、`escape`。

### 3. 与 MySQL BLOB 的区别

| 维度       | MySQL BLOB 系列                | PostgreSQL bytea            |
|------------|--------------------------------|-----------------------------|
| 容量上限   | 64KB ~ 4GB(分四档)             | 约 1GB(单字段)              |
| 存储位置   | 单独表空间(对大字段优化)       | TOAST(自动溢出到次级存储)  |
| 索引       | 需要前缀                       | 不支持普通索引              |
| 用途       | 推荐存文件                     | **不推荐存文件**,用对象存储 |

> **生产建议**:PG 的 `bytea` 适合存**小图标、缩略图、加密后内容**。大文件(图片/视频/PDF)用**对象存储 (S3/OSS/MinIO)** + 数据库只存 URL。

---

## 六、日期时间类型 (Date & Time Types)

PostgreSQL 的时间类型设计非常完整,**内置时区支持是最大亮点**。

### 1. 类型一览

| 类型                                  | 存储      | 范围                                       | 特点                         |
|---------------------------------------|-----------|--------------------------------------------|------------------------------|
| `date`                                | 4 字节    | 4713 BC ~ 5874897 AD                       | 只到天                       |
| `time [without time zone]`            | 8 字节    | 00:00:00 ~ 24:00:00                        | 只到时分秒,不带时区          |
| `time with time zone` (`timetz`)      | 12 字节   | 00:00:00+1559 ~ 24:00:00-1559              | 带时区                       |
| `timestamp [without time zone]`       | 8 字节    | 4713 BC ~ 294276 AD                        | **业务时间常用**             |
| `timestamp with time zone` (`timestamptz`) | 8 字节 | 4713 BC ~ 294276 AD                  | **内部存 UTC,推荐**          |
| `interval`                            | 16 字节   | -178000000 年 ~ +178000000 年              | 时间间隔                     |

### 2. `timestamp` vs `timestamptz` 核心区别

| 维度           | `timestamp` (without time zone) | `timestamptz` (with time zone) |
|----------------|----------------------------------|---------------------------------|
| 存储内容       | 字面值原样存,不转时区            | **一律转 UTC 存储**            |
| 输入时         | 不带时区                         | 识别时区,转 UTC                |
| 输出时         | 原样输出                         | 按会话时区转换输出              |
| 推荐度         | 已知绝对时间(无时区概念)        | **绝大多数业务场景推荐**        |

```sql
-- 演示时区转换
SET TIME ZONE 'UTC';
SELECT now();                                    -- 2026-08-14 06:00:00+00

SET TIME ZONE 'Asia/Shanghai';
SELECT now();                                    -- 2026-08-14 14:00:00+08(同一时刻,显示不同)
```

### 3. 当前时间函数

```sql
-- 当前时间(全部返回 timestamptz)
now()                          -- 当前事务开始时间(推荐)
current_timestamp              -- 同 now()
statement_timestamp()          -- 当前语句开始时间
clock_timestamp()              -- 真正的当前时刻(每次调用都变)

-- 当前日期
current_date                   -- 2026-08-14

-- 当前时间(只到时分秒)
current_time                   -- 14:00:00+08
localtime                      -- 不带时区的当前时间

-- PostgreSQL 没有 now() 之外太多别名
```

### 4. 字面量与构造

```sql
SELECT DATE '2026-08-14';
SELECT TIME '14:30:00';
SELECT TIMESTAMP '2026-08-14 14:30:00';
SELECT TIMESTAMPTZ '2026-08-14 14:30:00+08';

-- 间隔
SELECT INTERVAL '1 day';
SELECT INTERVAL '2 hours 30 minutes';
SELECT INTERVAL '3 months';
SELECT DATE '2026-01-01' + INTERVAL '1 year';  -- 2027-01-01
```

### 5. 时区处理 `AT TIME ZONE`

```sql
-- timestamp 转 timestamptz(按指定时区解释)
SELECT TIMESTAMP '2026-08-14 14:30:00' AT TIME ZONE 'Asia/Shanghai';
-- 结果: 2026-08-14 06:30:00+00(按上海时间解释后转 UTC)

-- timestamptz 转 timestamp(按会话时区显示)
SELECT now() AT TIME ZONE 'Asia/Shanghai';

-- 切换会话时区
SET TIME ZONE 'America/New_York';

-- 查看当前时区
SHOW TIME ZONE;
SELECT current_setting('TIMEZONE');
```

### 6. `EXTRACT()` 与 `date_trunc()`

```sql
-- EXTRACT 提取字段
SELECT EXTRACT(YEAR  FROM now());               -- 2026
SELECT EXTRACT(MONTH FROM now());               -- 8
SELECT EXTRACT(DAY   FROM now());               -- 14
SELECT EXTRACT(HOUR  FROM now());               -- 14
SELECT EXTRACT(DOW   FROM now());               -- 星期几(0=周日)
SELECT EXTRACT(EPOCH FROM now());               -- Unix 时间戳(秒,带小数)
SELECT EXTRACT(DOY   FROM now());               -- 一年中第几天

-- date_trunc 截断到指定精度
SELECT date_trunc('day',    now());             -- 2026-08-14 00:00:00+08
SELECT date_trunc('hour',   now());             -- 2026-08-14 14:00:00+08
SELECT date_trunc('month',  now());             -- 2026-08-01 00:00:00+08
SELECT date_trunc('week',   now());             -- 本周一 00:00:00
SELECT date_trunc('year',   now());             -- 2026-01-01 00:00:00+08

-- 加减
SELECT now() + INTERVAL '7 days';
SELECT now() - INTERVAL '1 month';
SELECT now() + '1 day'::INTERVAL;
SELECT age(TIMESTAMP '2000-01-01', now());      -- 间隔年龄(年、月)
SELECT now() - TIMESTAMP '2026-01-01';          -- 间隔
```

### 7. 日期时间典型建表示例

```sql
CREATE TABLE event_log (
    id          BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id     BIGINT       NOT NULL,
    event_time  TIMESTAMPTZ  NOT NULL DEFAULT now(),         -- 业务时间
    birthday    DATE,                                         -- 生日
    duration    INTERVAL,                                     -- 时长
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- 插入示例
INSERT INTO event_log (user_id, event_time, birthday, duration)
VALUES (1, '2026-08-14 14:30:00+08', '1990-05-20', '2 hours 30 minutes')
RETURNING id, event_time;

-- 查询本月订单
SELECT * FROM orders
WHERE created_at >= date_trunc('month', now())
  AND created_at <  date_trunc('month', now()) + INTERVAL '1 month';
```

---

## 七、布尔类型 (Boolean)

PostgreSQL 有**原生 `boolean` 类型**,不像 MySQL 用 `TINYINT(1)` 模拟。

```sql
is_vip BOOLEAN DEFAULT FALSE

-- 有效值
TRUE  / 't'  / 'true'  / 'y'  / 'yes'  / 'on'  / '1'
FALSE / 'f'  / 'false' / 'n'  / 'no'   / 'off' / '0'
NULL                                            -- 三态逻辑

-- 查询
SELECT * FROM users WHERE is_vip IS TRUE;
SELECT * FROM users WHERE is_vip IS NOT FALSE;     -- 包括 NULL
```

---

## 八、枚举类型 (ENUM)

PostgreSQL 没有 MySQL 的字段级 `ENUM`,而是**用 `CREATE TYPE` 创建独立的枚举类型**。

```sql
-- 创建枚举类型
CREATE TYPE mood AS ENUM ('sad', 'ok', 'happy');

-- 用作字段类型
CREATE TABLE person (
    id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name  TEXT NOT NULL,
    m     mood NOT NULL DEFAULT 'ok'
);

-- 插入
INSERT INTO person (name, m) VALUES ('张三', 'happy');

-- 查询(按定义顺序排序,而非字母序)
SELECT * FROM person ORDER BY m;
-- sad < ok < happy

-- 查看枚举值
SELECT enumlabel FROM pg_enum
WHERE enumtypid = 'mood'::regtype
ORDER BY enumsortorder;

-- 修改枚举(添加新值)
ALTER TYPE mood ADD VALUE 'excited' AFTER 'happy';

-- 重建枚举(改/删除值需要重建)
-- 步骤:建新类型 → 数据迁移 → 改字段类型 → 删旧类型
```

> **生产建议**:枚举适合**极稳定**的取值(如星期、性别);经常变化的用 `VARCHAR` + `CHECK` 约束或单独的字典表更灵活。

---

## 九、几何类型 (Geometric Types)

PostgreSQL 原生支持一组几何类型,**比 MySQL 早很多年**。

| 类型       | 表示             | 示例字面量           |
|------------|------------------|----------------------|
| `point`    | 平面上的点       | `'(1, 2)'`           |
| `line`     | 无限直线         | `'{1, 2, 3}'`        |
| `lseg`     | 线段             | `'(1, 2), (3, 4)'`   |
| `box`      | 矩形             | `'(1, 2), (3, 4)'`   |
| `path`     | 路径(开/闭)     | `'[(1, 2), (3, 4)]'` |
| `polygon`  | 多边形           | `'((1, 2), (3, 4))'` |
| `circle`   | 圆               | `'<(1, 2), 5>'`      |

```sql
CREATE TABLE shop (
    id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name     TEXT NOT NULL,
    location POINT NOT NULL
);

INSERT INTO shop (name, location) VALUES
('北京店', POINT(116.4074, 39.9042)),
('上海店', POINT(121.4737, 31.2304));

-- 计算两点距离(欧氏距离,不是球面距离,简单几何场景够用)
SELECT name, location <-> POINT(116.4074, 39.9042) AS distance
FROM shop
ORDER BY location <-> POINT(116.4074, 39.9042)
LIMIT 5;

-- 计算球面距离(需 cube + earthdistance 扩展)
CREATE EXTENSION cube;
CREATE EXTENSION earthdistance;
SELECT name, location <@> POINT(116.4074, 39.9042) AS distance_m
FROM shop
ORDER BY distance_m
LIMIT 5;
```

> **生产建议**:复杂地理空间场景用 **`PostGIS`** 扩展,远超原生几何类型。

---

## 十、网络地址类型 (Network Address Types)

PostgreSQL 原生支持 IP/MAC 地址类型,**带合法性校验和专用操作符**。

| 类型            | 存储     | 描述                         |
|-----------------|----------|------------------------------|
| `inet`          | 7 或 19 字节 | IPv4 / IPv6 地址(可带子网)|
| `cidr`          | 7 或 19 字节 | IPv4 / IPv6 网络(必须带子网)|
| `macaddr`       | 6 字节   | MAC 地址(EUI-48)            |
| `macaddr8`      | 8 字节   | MAC 地址(EUI-64)            |

```sql
CREATE TABLE server (
    id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    hostname  TEXT,
    ip        INET NOT NULL,
    subnet    CIDR,
    mac       MACADDR
);

INSERT INTO server (hostname, ip, subnet, mac) VALUES
('web01', '192.168.1.10',   '192.168.1.0/24',   '08:00:2b:01:02:03'),
('web02', '10.0.0.5/32',    '10.0.0.0/8',       '08:00:2b:01:02:04'),
('web03', '2001:db8::1',    '2001:db8::/32',    '08:00:2b:01:02:05');

-- 查询
SELECT * FROM server WHERE ip << '192.168.1.0/24';   -- 在子网内
SELECT * FROM server WHERE ip << '10.0.0.0/8';        -- 同上

-- 包含关系
SELECT '192.168.1.10'::INET << '192.168.1.0/24';      -- true
SELECT '192.168.2.10'::INET << '192.168.1.0/24';      -- false
```

---

## 十一、位串类型 (Bit Strings)

存储固定长度或可变长度的 1/0 串,适合位掩码场景。

```sql
flag BIT(8)                -- 固定 8 位
flag BIT VARYING(16)       -- 变长,最多 16 位

INSERT INTO t (flag) VALUES (B'10101010');      -- 二进制字面量
SELECT flag FROM t;                                -- 10101010
SELECT (flag & B'00001111') FROM t;                -- 位运算
```

---

## 十二、文本搜索类型 (Full Text Search)

PostgreSQL 原生支持全文检索,无需 Elasticsearch(中小规模够用)。

| 类型        | 描述                                  |
|-------------|---------------------------------------|
| `tsvector`  | 文档的词素向量(标准化、去停用词)     |
| `tsquery`   | 搜索查询表达式                       |

```sql
-- 创建带全文索引的表
CREATE TABLE article (
    id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title TEXT NOT NULL,
    body  TEXT NOT NULL,
    tsv   TSVECTOR
);

CREATE INDEX idx_article_tsv ON article USING GIN (tsv);

-- 触发器:插入/更新时自动生成 tsv
CREATE FUNCTION article_tsv_update() RETURNS trigger AS $$
BEGIN
    NEW.tsv :=
        setweight(to_tsvector('pg_catalog.english', NEW.title), 'A') ||
        setweight(to_tsvector('pg_catalog.english', NEW.body),  'B');
    RETURN NEW;
END
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_article_tsv
BEFORE INSERT OR UPDATE ON article
FOR EACH ROW EXECUTE FUNCTION article_tsv_update();

-- 插入
INSERT INTO article (title, body) VALUES
('PostgreSQL Tutorial', 'PostgreSQL is a powerful open-source database.');

-- 全文检索
SELECT id, title
FROM article
WHERE tsv @@ to_tsquery('english', 'database & power');

-- 高亮
SELECT id,
       ts_headline(body, to_tsquery('english', 'database')) AS snippet
FROM article;
```

---

## 十三、JSON 类型 — 重要!

PostgreSQL 同时支持 `json` 和 `jsonb` 两种 JSON 类型,**`jsonb` 是绝大多数场景的选择**。

### 1. `json` vs `jsonb`

| 维度           | `json`                          | `jsonb`                                |
|----------------|---------------------------------|----------------------------------------|
| 存储格式       | 文本原文                        | **二进制解析后存储**                   |
| 输入开销       | 低(只校验合法)                 | 较高(解析一次)                        |
| 查询开销       | 每次解析                        | 极快(已解析好)                        |
| 索引           | 不支持                          | **支持 GIN 索引**                      |
| 保留空格/键顺序 | 是                             | 否(可能重排)                          |
| 保留重复键     | 是                              | 否(后者覆盖前者)                      |
| 操作符         | 子集                            | 完整(-> ->> #> @> ? ?| ?& 等)         |
| 推荐           | 只存只读、不查                  | **强烈推荐**                           |

### 2. 建表与插入

```sql
CREATE TABLE user_profile (
    id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name     TEXT NOT NULL,
    profile  JSONB NOT NULL DEFAULT '{}'::JSONB,
    settings JSONB NOT NULL DEFAULT '{}'::JSONB
);

-- 插入(支持多行语法)
INSERT INTO user_profile (name, profile, settings) VALUES
('张三', '{"age": 28, "city": "北京", "vip": true}', '{"theme": "dark", "lang": "zh-CN"}'),
('李四', '{"age": 35, "city": "上海", "skills": ["MySQL", "Redis", "Go"]}', '{"theme": "light"}');

-- 自动校验 JSON 合法性
INSERT INTO user_profile (name, profile) VALUES ('王五', '{age: 28}');  -- ERROR: invalid input syntax
```

### 3. JSON 操作符完整示例

```sql
-- 准备数据
INSERT INTO user_profile (name, profile) VALUES
('测试', '{
    "name": "测试用户",
    "age": 28,
    "address": {"city": "北京", "district": "朝阳"},
    "skills": ["MySQL", "PostgreSQL", "Redis"],
    "projects": [
        {"name": "项目A", "year": 2024},
        {"name": "项目B", "year": 2025}
    ]
}');

-- (1) -> 取字段(返回 JSON)
SELECT profile -> 'name' FROM user_profile;       -- "测试用户"
SELECT profile -> 'age'  FROM user_profile;       -- 28(还是 JSON)

-- (2) ->> 取字段并 unquote(返回 TEXT)
SELECT profile ->> 'name' FROM user_profile;      -- '测试用户'
SELECT (profile ->> 'age')::INTEGER AS age FROM user_profile;  -- 28(整型)

-- (3) #> 按路径取 JSON
SELECT profile #> '{address, city}' FROM user_profile;   -- "北京"

-- (4) #>> 按路径取 TEXT
SELECT profile #>> '{address, city}' FROM user_profile;  -- '北京'

-- (5) 嵌套数组
SELECT profile #>> '{skills, 0}' FROM user_profile;      -- 'MySQL'
SELECT jsonb_array_length(profile -> 'skills') FROM user_profile;  -- 3

-- (6) @> 包含(常用索引!)
SELECT * FROM user_profile WHERE profile @> '{"city": "北京"}';
SELECT * FROM user_profile WHERE profile @> '{"skills": ["MySQL"]}';

-- (7) ? 键存在
SELECT * FROM user_profile WHERE profile ? 'city';
SELECT * FROM user_profile WHERE profile ?| ARRAY['vip', 'skills'];  -- 任一存在
SELECT * FROM user_profile WHERE profile ?& ARRAY['city', 'age'];   -- 全部存在

-- (8) 修改 jsonb
UPDATE user_profile
SET profile = profile || '{"level": "v2", "age": 31}'::JSONB
WHERE name = '张三';

UPDATE user_profile
SET profile = jsonb_set(profile, '{age}', '29'::JSONB)
WHERE name = '张三';

UPDATE user_profile
SET profile = profile #- '{address, district}'    -- 删除字段
WHERE name = '张三';
```

### 4. JSONB 函数

```sql
-- jsonb_path_query(SQL/JSON Path,PG 12+)
SELECT jsonb_path_query(
    '{"a": {"b": [1, 2, 3]}}'::JSONB,
    '$.a.b[*] ? (@ > 1)'
);
-- 结果: 2, 3

-- jsonb_path_exists
SELECT jsonb_path_exists(
    '{"a": 1, "b": 2}'::JSONB,
    '$.* ? (@ > 1)'
);
-- true

-- 展开为记录
SELECT * FROM jsonb_to_record('{"a": 1, "b": "hello"}'::JSONB) AS x(a INT, b TEXT);

-- 展开为行集(jsonb_array_elements)
SELECT elem
FROM user_profile, jsonb_array_elements(profile -> 'skills') AS elem;

-- 聚合为 jsonb
SELECT jsonb_pretty(jsonb_agg(profile)) FROM user_profile;

-- 合并对象(jsonb_concat 或 ||)
SELECT '{"a": 1}'::JSONB || '{"b": 2}'::JSONB;        -- {"a": 1, "b": 2}
SELECT '{"a": {"x": 1}}'::JSONB || '{"a": {"y": 2}}';  -- {"a": {"x": 1, "y": 2}} 深度合并

-- 删除所有 null 字段(jsonb_strip_nulls)
SELECT jsonb_strip_nulls('{"a": 1, "b": null}'::JSONB);   -- {"a": 1}
```

### 5. JSONB 索引(重要!)

```sql
-- (1) GIN 索引(默认 ops):支持 @> ? ?| ?& 操作符
CREATE INDEX idx_profile_gin ON user_profile USING GIN (profile);

-- (2) jsonb_path_ops:仅支持 @>,索引更小、查询更快
CREATE INDEX idx_profile_path_ops ON user_profile USING GIN (profile jsonb_path_ops);

-- (3) 表达式索引:针对具体字段
CREATE INDEX idx_profile_city ON user_profile ((profile ->> 'city'));
CREATE INDEX idx_profile_age  ON user_profile (((profile ->> 'age')::INTEGER));

-- (4) 查询计划验证
EXPLAIN ANALYZE
SELECT * FROM user_profile WHERE profile @> '{"city": "北京"}';
-- 应能看到 Bitmap Index Scan on idx_profile_gin
```

### 6. JSONB 适用与不适用

| 适用 JSONB                                | 不适用 JSONB                              |
|-------------------------------------------|--------------------------------------------|
| 配置项、用户偏好                          | 需要复杂 JOIN 的关系数据                   |
| 表单动态字段                              | 需要频繁修改少量字段的高频写入场景         |
| 第三方 API 返回的半结构化数据             | 强一致性的金融交易数据                     |
| 日志、事件属性                            | 全文搜索(虽然可以,不如专用 tsvector)      |

---

## 十四、数组类型 (Array Types)

PostgreSQL **任意类型**都可以是数组(包括用户自定义类型)。

### 1. 一维与多维数组

```sql
-- 一维数组
tags    TEXT[]          -- 等价 TEXT ARRAY
scores  INTEGER[]
flags   BOOLEAN[]

-- 多维数组(2 维)
matrix  INTEGER[][]

-- 指定维度
matrix  INTEGER[3][3]   -- 3x3 矩阵

-- 创建带数组的表
CREATE TABLE article (
    id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title    TEXT NOT NULL,
    tags     TEXT[] NOT NULL DEFAULT '{}',
    scores   INTEGER[] DEFAULT '{}'
);

-- 插入
INSERT INTO article (title, tags, scores) VALUES
('PostgreSQL 入门', ARRAY['PostgreSQL', 'SQL', '数据库'], ARRAY[9, 9, 8, 10]),
('Redis 实战', '{"Redis", "缓存", "NoSQL"}', '{8, 9, 9}'),       -- 字符串字面量形式
('Go 语言', ARRAY['Go', '编程语言'], ARRAY[7, 8, 9]);
```

### 2. 数组查询

```sql
-- 包含某元素
SELECT * FROM article WHERE 'PostgreSQL' = ANY(tags);
SELECT * FROM article WHERE tags @> ARRAY['PostgreSQL'];

-- 被包含
SELECT * FROM article WHERE tags <@ ARRAY['PostgreSQL', 'SQL', '数据库', '事务'];

-- 交集(共享任一元素)
SELECT * FROM article WHERE tags && ARRAY['SQL', 'NoSQL'];

-- 数组长度
SELECT id, title, array_length(tags, 1) AS tag_count FROM article;

-- 元素访问(下标从 1 开始!)
SELECT tags[1] FROM article WHERE id = 1;            -- 'PostgreSQL'
SELECT tags[1:2] FROM article WHERE id = 1;          -- 数组切片

-- 展开为行(unnest)
SELECT id, unnest(tags) AS tag FROM article;

-- 数组中是否存在某值
SELECT id, 'PostgreSQL' = ANY(tags) AS has_pg FROM article;

-- GIN 索引加速数组查询
CREATE INDEX idx_article_tags ON article USING GIN (tags);
-- 这样 WHERE tags @> ARRAY['PostgreSQL'] 就能走索引
```

### 3. 数组函数

```sql
-- 追加元素
SELECT array_append(ARRAY[1, 2, 3], 4);             -- {1,2,3,4}

-- 前置
SELECT array_prepend(0, ARRAY[1, 2, 3]);              -- {0,1,2,3}

-- 拼接
SELECT ARRAY[1,2] || ARRAY[3,4];                      -- {1,2,3,4}
SELECT array_cat(ARRAY[1,2], ARRAY[3,4]);              -- {1,2,3,4}

-- 去重
SELECT array_agg(DISTINCT tag) FROM (
    SELECT unnest(tags) AS tag FROM article
) t;

-- 聚合(把多行合并成数组)
SELECT array_agg(title) FROM article;                  -- 所有标题
SELECT array_agg(title ORDER BY id) FROM article;      -- 带排序

-- 数组中某位置的元素
SELECT id, title, tags[1] FROM article;

-- 替换
SELECT ARRAY['a', 'b', 'c', 'd'][2:3] = ARRAY['X', 'Y'];  -- 切片替换
UPDATE article SET tags[2] = 'SQL 进阶' WHERE id = 1;     -- 元素替换
```

### 4. 数组典型建表示例

```sql
CREATE TABLE product (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        TEXT NOT NULL,
    tags        TEXT[] NOT NULL DEFAULT '{}',       -- 标签
    categories  TEXT[] NOT NULL DEFAULT '{}',       -- 多分类
    image_urls  TEXT[] NOT NULL DEFAULT '{}',       -- 多图
    UNIQUE (name),
    CONSTRAINT tags_min_length CHECK (array_length(tags, 1) >= 1)
);

CREATE INDEX idx_product_tags       ON product USING GIN (tags);
CREATE INDEX idx_product_categories ON product USING GIN (categories);
```

---

## 十五、范围类型 (Range Types)

PostgreSQL 范围类型表示某个区间,**适合时间段、数值区间等**。

### 1. 内置范围类型

| 类型          | 元素类型 | 字面量示例              |
|---------------|----------|-------------------------|
| `int4range`   | integer  | `'[1, 10)'`             |
| `int8range`   | bigint   | `'[1, 100)'`            |
| `numrange`    | numeric  | `'[1.5, 9.5]'`          |
| `tsrange`     | timestamp (without tz) | `'[2026-01-01, 2026-12-31]'` |
| `tstzrange`   | timestamp with tz      | `'[2026-01-01 00:00+08, 2027-01-01)'` |
| `daterange`   | date     | `'[2026-01-01, 2026-12-31]'` |

- `[` 表示包含边界
- `)` 表示不包含边界
- `(]` 表示不包含下界、包含上界

### 2. 范围操作示例

```sql
CREATE TABLE reservation (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    room_no     TEXT NOT NULL,
    during      DATERANGE NOT NULL,
    EXCLUDE USING GIST (room_no WITH =, during WITH &&)   -- 防止同一房间时间重叠
);

-- 插入
INSERT INTO reservation (room_no, during) VALUES
('Room-A', '[2026-08-14, 2026-08-16)'),
('Room-A', '[2026-08-20, 2026-08-22)'),
('Room-B', '[2026-08-14, 2026-08-20)');

-- 范围构造函数
SELECT int4range(1, 10);                  -- [1, 10)
SELECT int4range(1, 10, '[]');             -- [1, 10]
SELECT numrange(1.5, 9.5, '[)');           -- [1.5, 9.5)
SELECT daterange(CURRENT_DATE, CURRENT_DATE + 7, '[)');  -- 本周到下今天

-- 查询某日期是否在范围内
SELECT * FROM reservation WHERE during @> DATE '2026-08-15';

-- 查询重叠的房间(同一时间被多个预订)
SELECT a.room_no, a.during, b.during
FROM reservation a
JOIN reservation b ON a.room_no = b.room_no AND a.id < b.id
WHERE a.during && b.during;             -- && 重叠操作符

-- 包含关系
SELECT '[1, 10)'::INT4RANGE @> 5;          -- true(5 在范围里)
SELECT '[1, 10)'::INT4RANGE @> 10;         -- false(不包含上界)
SELECT '[1, 10)'::INT4RANGE @> '[3, 5)'::INT4RANGE;  -- true(子集)

-- 求交集
SELECT int4range(1, 10) * int4range(5, 15);   -- [5, 10)

-- 求并集(可能不连续)
SELECT int4range(1, 5) + int4range(8, 12);    -- [1, 5), [8, 12)

-- 边界
SELECT lower('[1, 10)'::INT4RANGE);       -- 1
SELECT upper('[1, 10)'::INT4RANGE);       -- 10
SELECT isempty('[1, 1)'::INT4RANGE);      -- true(空范围)
```

### 3. 范围类型典型场景

```sql
-- 价格区间
CREATE TABLE product_price_history (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    product_id BIGINT NOT NULL,
    price      NUMERIC(10, 2) NOT NULL,
    valid_at   DATERANGE NOT NULL DEFAULT daterange(CURRENT_DATE, NULL, '[)')
);

-- 查询某天生效的价格
SELECT * FROM product_price_history
WHERE product_id = 1 AND valid_at @> CURRENT_DATE;

-- 防止价格区间重叠
CREATE UNIQUE INDEX ON product_price_history (product_id, valid_at);
```

### 4. 范围类型对比表

| 类型          | 元素类型   | 常用场景                  |
|---------------|------------|---------------------------|
| `int4range`   | integer    | 年龄区间、层级范围        |
| `int8range`   | bigint     | 大数值范围                |
| `numrange`    | numeric    | 价格区间、坐标范围        |
| `daterange`   | date       | 有效期、生日区间          |
| `tsrange`     | timestamp  | 不带时区的时间段          |
| `tstzrange`   | timestamptz | 带时区的时间段(推荐)     |

---

## 十六、UUID 类型

PostgreSQL 原生支持 `uuid` 类型,需启用 `uuid-ossp` 或 `pgcrypto` 扩展来生成 UUID。

```sql
-- 启用扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- 也提供 gen_random_uuid()

-- 生成 UUID
SELECT uuid_generate_v1();          -- v1:基于时间 + MAC
SELECT uuid_generate_v4();          -- v4:纯随机
SELECT gen_random_uuid();           -- pgcrypto 提供,等价 v4

-- 字段定义
CREATE TABLE t_order (
    id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    no   VARCHAR(32) NOT NULL UNIQUE
);

-- 插入
INSERT INTO t_order (no) VALUES ('ORDER-001') RETURNING id;
-- id 类似: a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d
```

> **PG 13+ 内置** `gen_random_uuid()`(无需扩展,启用 pgcrypto 后即可),PG 14+ 部分版本默认可用。

---

## 十七、XML 类型

存储 XML 数据,带合法性校验,支持 XPath 查询。

```sql
CREATE TABLE doc (
    id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    data XML NOT NULL
);

INSERT INTO doc (data) VALUES (
    XMLPARSE(DOCUMENT '<?xml version="1.0"?><root><item>hello</item></root>')
);

-- XPath 查询
SELECT xpath('/root/item/text()', data) FROM doc;     -- {hello}

-- 转为文本
SELECT xmlserialize(CONTENT data AS TEXT) FROM doc;
```

> 现代应用很少用 PG 直接存 XML,推荐存 JSONB。

---

## 十八、自定义类型 (CREATE TYPE)

PostgreSQL 可以创建**多种自定义类型**。

### 1. 复合类型(行类型)

```sql
CREATE TYPE address_type AS (
    street TEXT,
    city   TEXT,
    zip    TEXT
);

CREATE TABLE users (
    id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name    TEXT NOT NULL,
    address address_type
);

INSERT INTO users (name, address) VALUES ('张三', ROW('朝阳路 1 号', '北京', '100000'));

SELECT (address).city FROM users;                      -- 北京
```

### 2. 枚举类型

见前文第八节。

### 3. 基础类型(用 C 写)

需要 C 扩展开发,这里不展开。

---

## 十九、复合类型 (Composite Types)

复合类型本质就是一张**无名表**,用作函数返回值或字段类型很方便。

```sql
-- 建表时隐式创建
CREATE TABLE inventory_item (
    name        TEXT,
    supplier_id INTEGER,
    price       NUMERIC
);
-- 自动创建 inventory_item 复合类型

-- 用作函数参数
CREATE FUNCTION price_extend(inventory_item) RETURNS NUMERIC AS $$
    SELECT $1.price * 1.13
$$ LANGUAGE SQL;

SELECT price_extend(inventory_item('手机', 1, 999.00));   -- 1128.87
```

---

## 二十、类型转换 (Type Casting)

PG 有**三种类型转换**写法,效果等价。

```sql
-- 1. :: 语法(PG 风格,简洁)
SELECT '100'::INTEGER;
SELECT 100::TEXT;
SELECT now()::DATE;
SELECT '2026-08-14'::TIMESTAMPTZ;

-- 2. CAST(标准 SQL)
SELECT CAST('100' AS INTEGER);
SELECT CAST(100 AS TEXT);

-- 3. 函数式(int4 是 integer 内部名)
SELECT int4('100');
SELECT text(100);
SELECT date(now());
```

### 注意事项

```sql
-- 隐式转换:某些类型会自动转
SELECT 1 + 2.5;          -- 3.5(int 自动转 numeric)
SELECT '1' || 2;         -- '12'(int 转 text)

-- 强转失败的报错
SELECT 'abc'::INTEGER;    -- ERROR: invalid input syntax for type integer

-- 处理转换错误
SELECT NULLIF('abc', '')::INTEGER;       -- 失败会抛错
SELECT 'abc'::INTEGER WHERE FALSE;       -- 不执行转换

-- 使用 CASE 处理
SELECT CASE WHEN x ~ '^\d+$' THEN x::INTEGER ELSE NULL END FROM ...
```

---

## 二十一、Schema 使用

PostgreSQL **Schema 是数据库和表之间的逻辑命名空间**,比 MySQL 的 database 二级结构更灵活。

### 1. 默认 schema `public`

```sql
SHOW search_path;     -- 默认: "$user", public

-- 创建 schema
CREATE SCHEMA app;
CREATE SCHEMA IF NOT EXISTS analytics AUTHORIZATION postgres;

-- 跨 schema 查询
SELECT * FROM app.users;
SELECT * FROM analytics.events;

-- 切换 search_path(只在当前会话生效)
SET search_path TO app, public;
```

### 2. Schema 最佳实践

```sql
-- 按业务模块分 schema
CREATE SCHEMA user_service;
CREATE SCHEMA order_service;
CREATE SCHEMA payment_service;
CREATE SCHEMA analytics;

-- 各 schema 独立权限
GRANT USAGE ON SCHEMA user_service TO user_service_role;
GRANT ALL ON ALL TABLES IN SCHEMA user_service TO user_service_role;

-- 跨 schema JOIN
SELECT u.name, o.amount
FROM user_service.users u
JOIN order_service.orders o ON o.user_id = u.id
WHERE u.id = 1;
```

### 3. Schema 实用元命令

```sql
-- 列出所有 schema
\dn

-- 查看某 schema 的所有表
\dt app.*

-- 删除 schema(及所有对象)
DROP SCHEMA app CASCADE;

-- 只删空 schema
DROP SCHEMA app;

-- 重命名
ALTER SCHEMA app RENAME TO app_v2;
```

---

## 二十二、类型选择对比表

| 场景              | 推荐类型                                | 理由                              |
|-------------------|----------------------------------------|-----------------------------------|
| 主键自增          | `BIGINT GENERATED ALWAYS AS IDENTITY`  | 12+ 标准语法,容量大              |
| 业务主键/分布式   | `UUID DEFAULT gen_random_uuid()`       | 分布式唯一,无序写性能稍差         |
| 金额              | `NUMERIC(19, 4)` 或 `BIGINT`(分)       | 精确,避免浮点                    |
| 浮点计算          | `DOUBLE PRECISION`                     | 科学计算                          |
| 文本(变长)        | `TEXT`(默认) 或 `VARCHAR(n)`           | PG 的 TEXT 不限长度,无需 MEDIUMTEXT |
| 文本(定长)        | `CHAR(n)`                               | 国家码、MD5、身份证               |
| 二进制小数据      | `BYTEA`                                 | 图标、加密内容                    |
| 大文件            | 对象存储 + URL                            | 不推荐 BYTEA 存大文件             |
| 业务时间(带时区) | `TIMESTAMPTZ`                           | **绝大多数场景首选**              |
| 业务时间(无时区) | `TIMESTAMP`                             | 已知绝对时间(如 UTC 时间戳)       |
| 日期(仅年月日)   | `DATE`                                  | 生日、纪念日                      |
| 时长              | `INTERVAL`                              | 时间间隔                          |
| 布尔              | `BOOLEAN`                               | 三态,比 MySQL 的 TINYINT(1) 严谨 |
| 枚举              | `CREATE TYPE ... AS ENUM`               | 类型安全的枚举                    |
| IP 地址           | `INET` / `CIDR`                        | 自动校验、操作符丰富              |
| MAC               | `MACADDR` / `MACADDR8`                 | 同上                              |
| JSON 半结构化     | `JSONB`                                 | **不要用 JSON**,用 JSONB         |
| 数组              | `<基类型>[]`                            | 任意类型可数组化                  |
| 区间              | `DATERANGE` / `TSTZRANGE` / `NUMRANGE`| 防重叠、空值上界等                |
| 全文检索          | `TSVECTOR` + GIN                        | 原生全文搜索                      |

---

## 二十三、完整建表语句模板

```sql
CREATE SCHEMA IF NOT EXISTS app;

CREATE TABLE app.t_user (
    id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_no         VARCHAR(32)  NOT NULL UNIQUE,
    username        VARCHAR(64)  NOT NULL UNIQUE,
    password_hash   CHAR(64)     NOT NULL,
    email           VARCHAR(128),
    phone           VARCHAR(20),
    nickname        VARCHAR(64)  NOT NULL DEFAULT '',
    avatar          VARCHAR(255),
    gender          SMALLINT     NOT NULL DEFAULT 0,             -- 0=未知 1=男 2=女
    birthday        DATE,
    balance_cents   BIGINT       NOT NULL DEFAULT 0,             -- 余额(分)
    status          SMALLINT     NOT NULL DEFAULT 0,             -- 0=正常 1=禁用 2=注销
    profile         JSONB        NOT NULL DEFAULT '{}'::JSONB,
    tags            TEXT[]       NOT NULL DEFAULT '{}',          -- 标签
    extra           JSONB        NOT NULL DEFAULT '{}'::JSONB,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    is_deleted      BOOLEAN      NOT NULL DEFAULT FALSE,
    CONSTRAINT ck_balance_non_negative CHECK (balance_cents >= 0),
    CONSTRAINT ck_gender_range        CHECK (gender BETWEEN 0 AND 2)
);

-- 索引
CREATE INDEX idx_user_status_created ON app.t_user (status, created_at);
CREATE INDEX idx_user_profile_gin    ON app.t_user USING GIN (profile);
CREATE INDEX idx_user_tags_gin       ON app.t_user USING GIN (tags);
CREATE INDEX idx_user_email          ON app.t_user (email) WHERE email IS NOT NULL;

-- 注释
COMMENT ON TABLE  app.t_user            IS '用户表';
COMMENT ON COLUMN app.t_user.user_no     IS '用户编号(对外)';
COMMENT ON COLUMN app.t_user.balance_cents IS '账户余额(分)';
COMMENT ON COLUMN app.t_user.profile     IS '用户画像(JSON)';
```

### 模板要点解析

| 字段                | 选型理由                                                  |
|---------------------|-----------------------------------------------------------|
| `id UUID`           | 分布式主键,无序避免自增 ID 暴露业务量                     |
| `user_no VARCHAR(32)`| 对外编号,可承载雪花 ID/业务码                            |
| `password_hash CHAR(64)` | SHA-256 固定 64 字符,CHAR 省空间                        |
| `balance_cents BIGINT` | 用"分"做单位,避免 NUMERIC 计算开销                     |
| `gender SMALLINT`    | 三态,小巧                                                |
| `profile JSONB`      | 灵活扩展,**默认空对象而非 NULL,简化应用层**              |
| `tags TEXT[]`        | PG 独有的数组字段,带 GIN 索引                            |
| `created_at TIMESTAMPTZ` | 带时区,**绝大多数业务场景首选**                       |
| `is_deleted BOOLEAN` | 逻辑删除                                                |
| `idx_user_profile_gin` | JSONB GIN 索引,加速 `@>` 查询                          |
| `idx_user_tags_gin`    | 数组 GIN 索引,加速数组包含查询                          |
| `WHERE email IS NOT NULL` | **部分索引**,减小索引体积                            |

---

## 二十四、核心要点速记

- **SQL 五大分类**:DDL(结构) / DML(数据) / DQL(查询) / DCL(权限) / TCL(事务)
- **PostgreSQL DDL 在事务内**,所有 CREATE/ALTER/DROP 都能 ROLLBACK — PG 的强项
- **psql 元命令**: `\dt`(表) `\d`(结构) `\df`(函数) `\dv`(视图) `\dn`(schema) `\do`(操作符) `\dx`(扩展) `\l`(数据库)
- **整数三档**:`smallint`(2B) / `integer`(4B) / `bigint`(8B),**无 UNSIGNED**
- **自增主键首选**:`BIGINT GENERATED ALWAYS AS IDENTITY`(PG 10+),取代 SERIAL
- **金额用 NUMERIC** 或 **BIGINT 存分**,绝不 FLOAT/DOUBLE;**绝不推荐 MONEY 类型**
- **字符串三种**:`VARCHAR(n)` / `CHAR(n)` / `TEXT`,`TEXT` 不限长度等价 VARCHAR(无 n),不必套娃
- **二进制用 BYTEA**,大文件走对象存储;MySQL 的 BLOB 系列在 PG 一个 BYTEA 搞定
- **时间类型**:业务时间**首选 `TIMESTAMPTZ`**(内部 UTC,显示按会话时区);`TIMESTAMP` 给已知绝对时间
- **`now()` 是事务开始时间**,`clock_timestamp()` 才是真正的"当前时刻"
- **时区转换**:`AT TIME ZONE 'Asia/Shanghai'`;`EXTRACT` 取字段,`date_trunc` 截断到精度
- **布尔用原生 `BOOLEAN`**,三态(TRUE/FALSE/NULL),不要用 SMALLINT 模拟
- **枚举用 `CREATE TYPE ... AS ENUM`**,按定义顺序排序而非字母序
- **JSON 必选 JSONB**:`jsonb` 二进制存储、支持 GIN 索引、操作符丰富;`json` 几乎没用
- **JSONB 操作符**:`->`(取 JSON)、`->>`(取 TEXT)、`#>` / `#>>`(路径)、`@>`(包含)、`?` / `?|` / `?&`(键存在)
- **JSONB 索引**:`USING GIN (col)` 或 `USING GIN (col jsonb_path_ops)`,表达式索引针对具体字段
- **数组任意类型**:`<type>[]`,`ANY()` `@>` `&&` 操作符,`array_agg` / `unnest` 聚合展开
- **数组 GIN 索引**:`CREATE INDEX ON t USING GIN (col)`,加速包含/重叠查询
- **范围类型**:`int4range` `int8range` `numrange` `tsrange` `tstzrange` `daterange`,带 `[]` / `[)` 边界
- **范围防重叠**:`EXCLUDE USING GIST (room_no WITH =, during WITH &&)`,典型的酒店预订防冲突
- **UUID**:`gen_random_uuid()`(PG 13+/pgcrypto),`uuid-ossp` 提供 v1/v4
- **Schema 比 MySQL 灵活**:`CREATE SCHEMA` 独立命名空间,`SET search_path TO app, public`
- **类型转换**:`::` / `CAST` / `func()` 三种等价,`::` 是 PG 风格
- **类型选择**:能 NUMERIC 别 FLOAT,能 TEXT 别 MEDIUMTEXT,能 TIMESTAMPTZ 别 TIMESTAMP,能 JSONB 别 JSON,能 BOOLEAN 别 SMALLINT
- **复合类型**:`CREATE TYPE ... AS (...)` 可作为函数参数或字段,函数返回 record 用
- **大文件不存数据库**,PG 的 BYTEA 上限约 1GB,且不推荐,统一走对象存储
- **enum 类型慎用**,经常变的取值用 VARCHAR + CHECK 约束或独立字典表
