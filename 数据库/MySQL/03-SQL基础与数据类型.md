# SQL 基础与数据类型 (SQL Basics & Data Types)

## 一、SQL 分类

SQL (Structured Query Language) 是操作关系型数据库的标准语言。按照功能,通常划分为五大类。

### 1. DDL (Data Definition Language) — 数据定义语言

用于定义/修改数据库对象结构,**操作对象是表、库、索引、视图**。

- `CREATE`:创建数据库、表、索引、视图
- `ALTER`:修改表结构(加列、改类型、建索引)
- `DROP`:删除库/表/视图
- `TRUNCATE`:清空表数据(保留结构,速度比 DELETE 快,不可回滚)
- `RENAME`:重命名表
- `COMMENT`:为对象添加注释

### 2. DML (Data Manipulation Language) — 数据操作语言

用于操作表中的**数据行**。

- `SELECT`(广义):查询数据(在 MySQL 中常被归为 DQL)
- `INSERT`:插入数据
- `UPDATE`:更新数据
- `DELETE`:删除数据
- `REPLACE`:插入或替换(主键/唯一键冲突则替换)
- `MERGE`:合并数据(MySQL 不直接支持,可用 `INSERT ... ON DUPLICATE KEY UPDATE`)

### 3. DQL (Data Query Language) — 数据查询语言

严格的说法,`SELECT` 单独成类,因为查询是数据库最常用的功能。

- `SELECT`:查询
- 子句:`FROM`、`WHERE`、`GROUP BY`、`HAVING`、`ORDER BY`、`LIMIT`

### 4. DCL (Data Control Language) — 数据控制语言

**权限管理**相关。

- `GRANT`:授予权限
- `REVOKE`:撤销权限
- `COMMIT`:提交事务(部分语境归 TCL)
- `ROLLBACK`:回滚事务(部分语境归 TCL)

### 5. TCL (Transaction Control Language) — 事务控制语言

**事务**的边界与控制。

- `START TRANSACTION` / `BEGIN`:开启事务
- `COMMIT`:提交事务
- `ROLLBACK`:回滚事务
- `SAVEPOINT`:设置保存点
- `SET TRANSACTION`:设置事务隔离级别

### 五大分类速查表

| 分类 | 全称                | 核心动词                                | 操作对象       | 是否需要 COMMIT |
|------|---------------------|-----------------------------------------|----------------|-----------------|
| DDL  | Data Definition     | CREATE / ALTER / DROP / TRUNCATE        | 表结构、库结构 | 自动提交        |
| DML  | Data Manipulation   | INSERT / UPDATE / DELETE / REPLACE      | 数据行         | 视存储引擎      |
| DQL  | Data Query          | SELECT                                   | 数据行         | 否              |
| DCL  | Data Control        | GRANT / REVOKE                          | 权限           | 自动提交        |
| TCL  | Transaction Control | BEGIN / COMMIT / ROLLBACK / SAVEPOINT   | 事务           | 是              |

**关键提醒**:InnoDB 引擎下,**DDL 在 MySQL 8.0 之前不参与事务**,8.0 开始原子 DDL 才支持回滚;DML 默认自动提交(autocommit=1),要手动控制事务需先 `SET autocommit=0` 或显式 `BEGIN`。

---

## 二、常用 MySQL 客户端和工具

### 命令行工具

#### 1. `mysql` — 官方 CLI 客户端

最基础、功能最全的客户端,几乎所有 DBA 都必备。

```bash
# 登录
mysql -u root -p
mysql -u root -p -h 127.0.0.1 -P 3306

# 指定数据库
mysql -u root -p mydb

# 执行单条 SQL
mysql -u root -p -e "SELECT VERSION();"

# 从文件执行
mysql -u root -p mydb < script.sql

# 常用内部命令
SHOW DATABASES;
USE mydb;
SHOW TABLES;
DESCRIBE users;
```

#### 2. `mysqladmin` — 管理工具

```bash
# 修改密码
mysqladmin -u root -p password 'newpass'

# 创建/删除数据库
mysqladmin -u root -p create mydb
mysqladmin -u root -p drop mydb

# 查看状态
mysqladmin -u root -p status
mysqladmin -u root -p processlist

# 优雅关闭
mysqladmin -u root -p shutdown

# 刷新权限/日志
mysqladmin -u root -p reload
```

#### 3. `mysqldump` — 逻辑备份

```bash
# 备份单个库
mysqldump -u root -p mydb > mydb.sql

# 备份多个库
mysqldump -u root -p --databases db1 db2 > dbs.sql

# 备份所有库
mysqldump -u root -p --all-databases > all.sql

# 只备份结构
mysqldump -u root -p --no-data mydb > schema.sql

# 恢复
mysql -u root -p mydb < mydb.sql
```

#### 4. `mycli` — 增强版 CLI(强烈推荐)

`mycli` 是 Python 写的 mysql 客户端增强版,提供:

- **语法高亮**
- **自动补全**(表名、列名、SQL 关键字)
- **多行编辑**(像编辑器一样编辑 SQL)
- **历史记录搜索**

```bash
# 安装
pip install mycli
brew install mycli

# 使用(完全兼容 mysql 的参数)
mycli -u root -p mydb
```

### GUI 客户端

| 工具           | 平台          | 特点                                          |
|----------------|---------------|-----------------------------------------------|
| **Navicat**    | Win/Mac/Linux | 老牌商业软件,功能全,UI 优秀,需付费          |
| **DBeaver**    | 跨平台        | 免费开源,功能极强,支持多种数据库            |
| **MySQL Workbench** | 跨平台   | 官方出品,建模能力强,EER 图                   |
| **DataGrip**   | 跨平台        | JetBrains 出品,智能补全顶级,需付费           |
| **Sequel Ace** | macOS         | Mac 原生,免费开源,原 Sequel Mac 继任者       |
| **TablePlus**  | Mac/Win       | 设计美观,响应快,付费                         |
| **phpMyAdmin** | Web           | 老牌 PHP 写的 Web 客户端,LAMP 经典搭配       |
| **Adminer**    | Web           | phpMyAdmin 的现代替代,单文件 PHP              |

**推荐组合**:

- 本地开发 + 终端党 → `mycli`
- 全功能管理 → `Navicat` 或 `DBeaver`
- 重度 JetBrains 用户 → `DataGrip`
- macOS 轻量 → `Sequel Ace` 或 `TablePlus`

---

## 三、数值类型 (Numeric Types)

MySQL 数值类型分为**整数**、**浮点**、**定点**、**位**四大类。

### 1. 整数类型

| 类型        | 存储 (字节) | 有符号范围                              | 无符号范围                       | 典型用途                  |
|-------------|-------------|-----------------------------------------|----------------------------------|---------------------------|
| `TINYINT`   | 1           | -128 ~ 127                              | 0 ~ 255                          | 状态(0/1)、布尔、年龄     |
| `SMALLINT`  | 2           | -32768 ~ 32767                          | 0 ~ 65535                        | 小计数器、端口            |
| `MEDIUMINT` | 3           | -8388608 ~ 8388607                      | 0 ~ 16777215                     | 中等大小 ID               |
| `INT`       | 4           | -2147483648 ~ 2147483647                | 0 ~ 4294967295                   | **最常用主键**            |
| `BIGINT`    | 8           | -9223372036854775808 ~ 9223372036854775807 | 0 ~ 18446744073709551615      | 大表主键、雪花 ID、金额分 |

**显示宽度 (M) 与 ZEROFILL**:

```sql
INT(11)            -- 显示宽度 11,不影响存储范围,只是客户端显示
INT(11) ZEROFILL  -- 用 0 补足宽度,如 00000000042
```

> **注意**:从 MySQL 8.0.17 开始,显示宽度属性已**被废弃**,整数类型的范围由类型本身决定。

**有符号 vs 无符号**:

```sql
age TINYINT UNSIGNED    -- 0~255,适合年龄(虽然 255 也用不到)
order_count INT UNSIGNED  -- 0~42 亿,适合订单计数
```

### 2. 浮点类型

| 类型          | 存储 (字节) | 范围                                              | 精度           |
|---------------|-------------|---------------------------------------------------|----------------|
| `FLOAT`       | 4           | ±3.402823466E+38                                  | 单精度,~7 位   |
| `DOUBLE`      | 8           | ±1.7976931348623157E+308                          | 双精度,~15 位  |

```sql
score FLOAT(7, 4)       -- 总共 7 位,小数 4 位: -999.9999 ~ 999.9999
weight DOUBLE(10, 2)    -- -99999999.99 ~ 99999999.99
```

> **注意**:`FLOAT` 和 `DOUBLE` 是**近似值**,存在精度丢失,**不要用于金额**。例如 `0.1 + 0.2 != 0.3`。

### 3. 定点数 `DECIMAL`

**精确小数**,内部以字符串存储,**金额计算首选**。

| 类型          | 存储         | 范围                          |
|---------------|--------------|-------------------------------|
| `DECIMAL(M,D)`| M+2 字节     | 与 M, D 相关                 |

- `M`:总位数(精度),最大 65
- `D`:小数位数(标度),最大 30

```sql
amount DECIMAL(10, 2)    -- 最大:99999999.99 (8 位整数 + 2 位小数)
price  DECIMAL(18, 4)    -- 金融场景常用
```

### 4. 位类型 `BIT`

```sql
flag BIT(8)    -- 8 位二进制,范围 0~255
```

插入时使用二进制或十进制数字均可:

```sql
INSERT INTO t (flag) VALUES (b'10101010');   -- 二进制字面量
INSERT INTO t (flag) VALUES (170);           -- 十进制,值同上
SELECT flag+0 FROM t;   -- 输出 170
SELECT BIN(flag) FROM t; -- 输出 10101010
```

### 数值类型典型建表示例

```sql
CREATE TABLE product (
    id           BIGINT UNSIGNED       NOT NULL AUTO_INCREMENT COMMENT '主键',
    sku          VARCHAR(32)           NOT NULL              COMMENT 'SKU 编码',
    name         VARCHAR(128)          NOT NULL              COMMENT '商品名称',
    price        DECIMAL(10, 2)        NOT NULL DEFAULT 0    COMMENT '售价(元)',
    cost         DECIMAL(10, 2)        NOT NULL DEFAULT 0    COMMENT '成本(元)',
    stock        INT UNSIGNED          NOT NULL DEFAULT 0    COMMENT '库存',
    sold         INT UNSIGNED          NOT NULL DEFAULT 0    COMMENT '已售',
    weight_kg    DECIMAL(8, 3)                             COMMENT '重量(kg)',
    score        FLOAT(5, 2)                               COMMENT '评分',
    on_sale      TINYINT(1)            NOT NULL DEFAULT 1   COMMENT '是否在售',
    status       TINYINT UNSIGNED      NOT NULL DEFAULT 0   COMMENT '状态:0=草稿,1=上架,2=下架',
    PRIMARY KEY (id),
    UNIQUE KEY uk_sku (sku)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '商品表';
```

---

## 四、字符串类型 (String Types)

### 1. CHAR 与 VARCHAR

| 类型       | 存储特性             | 最大长度      | 适用场景               |
|------------|----------------------|---------------|------------------------|
| `CHAR(M)`  | 定长,不足补空格      | 255 字符      | 长度固定:MD5、手机号、身份证 |
| `VARCHAR(M)` | 变长,加 1-2 字节长度前缀 | 65535 字节(实际受行大小限制) | 长度可变:姓名、标题、描述 |

**CHAR 的性能优势**:定长,磁盘 I/O 更快,适合主键短字段。

```sql
md5 CHAR(32)            -- MD5 固定 32 位
phone CHAR(11)          -- 中国手机号 11 位
id_card CHAR(18)        -- 身份证 18 位
username VARCHAR(64)    -- 用户名,变长
email VARCHAR(128)      -- 邮箱
```

**VARCHAR(N) 的 N 是字符数,不是字节数**(在 utf8mb4 下,一个字符最多占 4 字节)。

### 2. TEXT 系列(长文本)

| 类型        | 最大长度          | 存储特性                |
|-------------|-------------------|-------------------------|
| `TINYTEXT`  | 255 字节          | 小文本                  |
| `TEXT`      | 65535 字节 (~64KB) | 一般文章内容            |
| `MEDIUMTEXT`| 16 MB             | 中型文档                |
| `LONGTEXT`  | 4 GB              | 超大文本                |

> **TEXT 不支持默认值,且只能 `INLINE` 完整索引**(MySQL 5.6 之前需要前缀索引)。

### 3. BLOB 系列(二进制大对象)

| 类型        | 最大长度   |
|-------------|------------|
| `TINYBLOB`  | 255 字节   |
| `BLOB`      | 64 KB      |
| `MEDIUMBLOB`| 16 MB      |
| `LONGBLOB`  | 4 GB       |

**用途**:存储图片、PDF、音视频等二进制数据。但**生产环境强烈建议存对象存储 (OSS/S3) + URL**,不要直接塞数据库。

### 4. ENUM(枚举)

**单选枚举**,内部存储为整数(1 个或 2 个字节)。

```sql
status ENUM('draft', 'published', 'archived') DEFAULT 'draft'
gender ENUM('male', 'female', 'unknown')
```

- 内部按字符串排序顺序存: `'draft'=1`, `'published'=2`, `'archived'=3`
- 优点:数据紧凑、只能取定义的值,保证一致性
- 缺点:扩展麻烦(改字段要 ALTER 大表)

### 5. SET(集合)

**多选集合**,位运算存储。

```sql
permissions SET('read', 'write', 'execute', 'delete')
```

- `'read,write'` 存为二进制 `0011` = 3
- 查询某用户是否有某权限:

```sql
SELECT * FROM users WHERE FIND_IN_SET('write', permissions);
```

### 字符串类型典型建表示例

```sql
CREATE TABLE article (
    id           BIGINT UNSIGNED       NOT NULL AUTO_INCREMENT,
    title        VARCHAR(200)          NOT NULL              COMMENT '标题',
    summary      VARCHAR(500)                               COMMENT '摘要',
    content      LONGTEXT                                  COMMENT '正文',
    cover_url    VARCHAR(255)                               COMMENT '封面图 URL',
    author_name  VARCHAR(64)                                COMMENT '作者名',
    author_avatar VARCHAR(255)                              COMMENT '作者头像 URL',
    category     ENUM('tech', 'life', 'finance', 'other')   COMMENT '分类',
    tags         SET('hot', 'top', 'recommend', 'original') COMMENT '标签',
    view_count   INT UNSIGNED          NOT NULL DEFAULT 0,
    md5          CHAR(32)              NOT NULL              COMMENT '内容 MD5(防重复)',
    PRIMARY KEY (id),
    KEY idx_category (category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '文章表';
```

---

## 五、日期时间类型 (Date & Time Types)

| 类型          | 存储 (字节) | 范围                                       | 典型用途                |
|---------------|-------------|--------------------------------------------|-------------------------|
| `YEAR`        | 1           | 1901 ~ 2155 (YEAR(4)), 1970 ~ 2069 (YEAR(2),已废弃) | 年份,生日年           |
| `TIME`        | 3           | -838:59:59 ~ 838:59:59                     | 时长、时段              |
| `DATE`        | 3           | 1000-01-01 ~ 9999-12-31                    | 生日、纪念日            |
| `DATETIME`    | 8           | 1000-01-01 00:00:00 ~ 9999-12-31 23:59:59  | **业务时间(推荐)**     |
| `TIMESTAMP`   | 4           | 1970-01-01 00:00:01 UTC ~ 2038-01-19 03:14:07 UTC | 创建时间、更新时间,带时区 |

### 1. DATETIME vs TIMESTAMP

这是面试常考题:

| 维度        | DATETIME                          | TIMESTAMP                            |
|-------------|------------------------------------|---------------------------------------|
| 时区        | 不存储时区,存的就是字面值        | 存 UTC,读取时按会话时区转换          |
| 范围        | 1000-01-01 ~ 9999-12-31          | 1970-01-01 ~ 2038-01-19(**2038 问题**)|
| 占用        | 8 字节                            | 4 字节                                |
| 自动更新    | DEFAULT CURRENT_TIMESTAMP         | DEFAULT CURRENT_TIMESTAMP / ON UPDATE |
| 适用        | 业务发生时间、订单时间            | 数据更新时间、记录创建/修改时间        |

### 2. TIMESTAMP 自动初始化与更新

```sql
created_at DATETIME     DEFAULT CURRENT_TIMESTAMP                COMMENT '创建时间',
updated_at DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
```

`TIMESTAMP` 也是一样语法,但 8.0.16+ 已**不推荐**用作通用时间字段,因其有 2038 年问题。

### 3. 时间相关函数与字面量

```sql
-- 字面量
'2026-08-14'                 -- DATE
'14:30:00'                   -- TIME
'2026-08-14 14:30:00'        -- DATETIME

-- 常用函数
NOW()                  -- 当前 DATETIME
CURDATE()              -- 当前 DATE
CURTIME()              -- 当前 TIME
UNIX_TIMESTAMP('2026-08-14 14:30:00')  -- 转时间戳
FROM_UNIXTIME(1755000000)              -- 时间戳转 DATETIME
DATE_ADD(NOW(), INTERVAL 7 DAY)        -- 加 7 天
DATE_FORMAT(NOW(), '%Y-%m-%d %H:%i:%s')  -- 格式化
```

### 日期时间类型典型建表示例

```sql
CREATE TABLE user (
    id           BIGINT UNSIGNED       NOT NULL AUTO_INCREMENT,
    username     VARCHAR(64)           NOT NULL,
    birthday     DATE                                       COMMENT '生日',
    register_at  DATETIME              NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '注册时间',
    last_login   DATETIME                                   COMMENT '上次登录时间',
    created_at   DATETIME              NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME              NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '用户表';

CREATE TABLE session_log (
    id           BIGINT UNSIGNED       NOT NULL AUTO_INCREMENT,
    user_id      BIGINT UNSIGNED       NOT NULL,
    duration     TIME                                       COMMENT '会话时长',
    start_at     DATETIME              NOT NULL,
    PRIMARY KEY (id),
    KEY idx_user_start (user_id, start_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '会话日志';
```

---

## 六、JSON 类型 (MySQL 5.7+)

MySQL 从 5.7 开始原生支持 JSON 类型,内部以二进制格式存储,**支持自动校验、索引、函数操作**。

### 1. 建表与插入

```sql
CREATE TABLE user_profile (
    id        BIGINT UNSIGNED     NOT NULL AUTO_INCREMENT,
    name      VARCHAR(64)         NOT NULL,
    profile   JSON                                    COMMENT '用户画像',
    settings  JSON                                    COMMENT '用户设置',
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

插入 JSON 数据,有**字符串字面量**和**JSON 对象**两种形式:

```sql
-- 字符串字面量(自动校验 JSON 合法性)
INSERT INTO user_profile (name, profile, settings) VALUES
('张三', '{"age": 28, "city": "北京", "vip": true}', '{"theme": "dark", "lang": "zh-CN"}');

-- 非法 JSON 会报错
INSERT INTO user_profile (name, profile) VALUES ('李四', '{age: 28}');  -- ERROR 3140
```

### 2. JSON 查询(`->` 与 `->>`)

```sql
-- 提取某个字段(返回值还是 JSON)
SELECT profile->'$.age' FROM user_profile;
-- 结果: 28

-- 提取字段并 unquote(返回字符串/数字)
SELECT profile->>'$.city' FROM user_profile;
-- 结果: 北京

-- WHERE 中使用
SELECT * FROM user_profile WHERE profile->>'$.city' = '北京';

-- JSON 嵌套
SELECT profile->'$.address.city' FROM user_profile;

-- JSON 数组
INSERT INTO user_profile (name, profile) VALUES
('王五', '{"skills": ["MySQL", "Redis", "Go"]}');

-- 数组元素
SELECT profile->'$.skills[0]' FROM user_profile WHERE name = '王五';
-- 结果: "MySQL"

-- 数组长度
SELECT JSON_LENGTH(profile->'$.skills') FROM user_profile WHERE name = '王五';
```

### 3. JSON 函数

```sql
-- 提取所有键
SELECT JSON_KEYS(profile) FROM user_profile;

-- 判断路径是否存在
SELECT * FROM user_profile WHERE JSON_CONTAINS_PATH(profile, 'one', '$.age') = 1;

-- 修改 JSON
UPDATE user_profile
SET profile = JSON_SET(profile, '$.age', 29, '$.city', '上海')
WHERE name = '张三';

-- 插入字段(若不存在)
UPDATE user_profile
SET profile = JSON_INSERT(profile, '$.email', 'zs@example.com')
WHERE name = '张三';

-- 删除字段
UPDATE user_profile
SET profile = JSON_REMOVE(profile, '$.vip')
WHERE name = '张三';

-- 替换整个值
UPDATE user_profile
SET profile = JSON_REPLACE(profile, '$.age', 30)
WHERE name = '张三';

-- 合并对象
UPDATE user_profile
SET profile = JSON_MERGE_PRESERVE(profile, '{"level": "v2", "age": 31}')
WHERE name = '张三';

-- 展开为行(JSON_TABLE,MySQL 8.0+)
SELECT t.*, jt.skill
FROM user_profile t,
     JSON_TABLE(t.profile, '$.skills[*]' COLUMNS (skill VARCHAR(64) PATH '$')) AS jt;
```

### 4. JSON 索引

MySQL 8.0+ 支持对 JSON 字段建立**表达式索引**:

```sql
ALTER TABLE user_profile ADD INDEX idx_city ( (profile->>'$.city') );
ALTER TABLE user_profile ADD INDEX idx_age  ( (profile->>'$.age') );
```

这样 WHERE `profile->>'$.city' = '北京'` 就能走索引了。

### 5. JSON 适用与不适用

| 适用 JSON                                  | 不适用 JSON                                   |
|--------------------------------------------|-----------------------------------------------|
| 配置项、用户偏好                           | 需要复杂查询、聚合的核心数据                  |
| 表单动态字段                               | 需要频繁 JOIN 的关系数据                      |
| 第三方 API 返回的半结构化数据              | 需要强一致性的事务数据                        |
| 日志、事件属性                             | 全文搜索(虽然可以建索引,但不如专用列)        |

---

## 七、空间数据类型 (Spatial Data Types)

MySQL 支持 OpenGIS 标准的空间数据类型,**8.0 之前仅 MyISAM 支持,8.0 起 InnoDB 也支持**。

### 类型一览

| 类型           | 描述                              |
|----------------|-----------------------------------|
| `GEOMETRY`     | 任何空间类型的基类                |
| `POINT`        | 一个点(经纬度)                    |
| `LINESTRING`   | 一条线                            |
| `POLYGON`      | 一个多边形(区域)                 |
| `MULTIPOINT`   | 多个点                            |
| `MULTILINESTRING` | 多条线                         |
| `MULTIPOLYGON` | 多个多边形                        |
| `GEOMETRYCOLLECTION` | 任意组合                    |

### 简单示例

```sql
CREATE TABLE shop (
    id       BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    name     VARCHAR(64)     NOT NULL,
    location POINT           NOT NULL SRID 4326,    -- WGS84 经纬度
    PRIMARY KEY (id),
    SPATIAL INDEX sx_location (location)
) ENGINE=InnoDB;

-- 插入(经度,纬度)
INSERT INTO shop (name, location) VALUES
('北京店', ST_SRID(POINT(116.4074, 39.9042), 4326));

-- 查找 5 公里内的店铺
SET @point = ST_SRID(POINT(116.4074, 39.9042), 4326);
SELECT name, ST_Distance_Sphere(location, @point) AS distance_m
FROM shop
WHERE ST_Distance_Sphere(location, @point) < 5000
ORDER BY distance_m;
```

**注意**:生产中如果只是简单经纬度查询,**用两个 `DOUBLE` 列 + 普通 B-Tree 索引**往往够用,空间类型适合真正需要几何运算(包含、相交等)的场景。

---

## 八、类型选择最佳实践

### 1. 金额一律用 `DECIMAL`

```sql
-- 错误(浮点)
price FLOAT      -- 0.1 + 0.2 = 0.30000000000000004
-- 正确
price DECIMAL(10, 2)
```

**进阶**:也可以用 `BIGINT` 存**分**(整数),避免 DECIMAL 的计算开销:

```sql
amount_cents BIGINT UNSIGNED NOT NULL  -- 单位:分
-- 100.50 元 = 10050
```

### 2. 时间怎么选

| 场景                       | 推荐类型                     |
|----------------------------|------------------------------|
| 用户生日                   | `DATE`                       |
| 订单创建时间(业务时间)    | `DATETIME`                   |
| 记录创建/更新时间         | `DATETIME DEFAULT CURRENT_TIMESTAMP [ON UPDATE CURRENT_TIMESTAMP]` |
| 跨时区的国际化业务时间     | `DATETIME` + 单独存时区/UTC  |
| 需要时间戳进行高效比较     | `BIGINT UNSIGNED`(Unix 秒/毫秒) |

**避免 `TIMESTAMP`** 的场景:跨度超过 2038 年的历史数据、需要精确到毫秒级以上、需要独立于时区的纯时间戳。

### 3. 状态用 `TINYINT` 还是 `ENUM`

```sql
-- 小项目用 ENUM,简单清晰
status ENUM('pending', 'paid', 'shipped', 'completed', 'cancelled')

-- 大项目用 TINYINT + 注释,因为 ENUM 改起来 ALTER 表代价大
status TINYINT NOT NULL DEFAULT 0 COMMENT '0=待支付 1=已支付 2=已发货 3=已完成 4=已取消'
```

### 4. ID 怎么选

| 数据规模         | 推荐策略                                  |
|------------------|-------------------------------------------|
| 单库单表         | `BIGINT UNSIGNED AUTO_INCREMENT`          |
| 分库分表         | 雪花算法(`BIGINT`) / Leaf / `UUID_SHORT()` |
| 分布式全局唯一   | UUID v7(MySQL 8.0.34 内置 `UUID()` 函数生成 v1) / 雪花 ID |
| 业务标识         | `VARCHAR` + 应用层生成短码                |

**避免** `INT UNSIGNED` 做主键:43 亿上限在大型业务中会很快触达。

### 5. 主键类型选择

- 自增 ID:简单,有序,但**暴露业务量**(可推断订单数)
- UUID:分布式友好,无序导致 **InnoDB 主键索引频繁页分裂**,写性能差
- UUID v7 / 雪花 ID:**时间有序的 UUID 变种**,主键索引友好,推荐

### 6. 文本长度选择

```sql
-- 已知固定长度用 CHAR
country_code CHAR(2)         -- ISO 国家码
id_card      CHAR(18)        -- 身份证
-- 变长用 VARCHAR
username     VARCHAR(64)     -- 用户名
title        VARCHAR(200)    -- 标题
-- 超长文本用 TEXT
content      TEXT            -- 文章正文
description  MEDIUMTEXT      -- 产品详情
```

---

## 九、字符集与排序规则 (Charset & Collation)

### 1. 字符集对比

| 字符集    | 最大字节/字符 | 支持                                  | 推荐度      |
|-----------|---------------|---------------------------------------|-------------|
| `latin1`  | 1             | 西欧语言                              | 仅历史遗留  |
| `utf8`    | 3             | BMP 平面,**不支持 emoji 和部分汉字**  | **不要用**  |
| `utf8mb4` | 4             | 完整 Unicode,**支持 emoji**           | **推荐**    |
| `gbk`     | 2             | 简体中文                              | 中文老项目  |
| `big5`    | 2             | 繁体中文                              | 台湾项目    |

**关键提醒**:MySQL 的 `utf8` 是**阉割版**,最多 3 字节,**存不了 emoji 😄**。必须用 `utf8mb4`。

### 2. 排序规则 (Collation)

排序规则决定字符串如何**比较和排序**,常见:

| Collation                  | 特点                              | 性能 | 准确度 |
|----------------------------|-----------------------------------|------|--------|
| `utf8mb4_general_ci`       | 简单字符比较,速度快               | 快   | 低     |
| `utf8mb4_unicode_ci`       | Unicode 标准算法,准确             | 中   | 高     |
| `utf8mb4_bin`              | 按字节二进制比较,**区分大小写**   | 最快 | -      |
| `utf8mb4_0900_ai_ci`       | MySQL 8.0 默认,基于 UCA 9.0     | 中   | 高     |

- `ci`:Case Insensitive,大小写不敏感 (`'A' = 'a'`)
- `cs`:Case Sensitive,大小写敏感 (`'A' != 'a'`)
- `bin`:二进制比较

**推荐**:

- 一般业务:`utf8mb4_0900_ai_ci`(8.0 默认)或 `utf8mb4_unicode_ci`
- 密码字段、用户名(区分大小写):`utf8mb4_bin`
- 高性能读盘:`utf8mb4_general_ci`,但准确度稍差

### 3. emoji 完整示例

```sql
CREATE TABLE chat_message (
    id        BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id   BIGINT UNSIGNED NOT NULL,
    nickname  VARCHAR(64)     NOT NULL,
    content   VARCHAR(500)    NOT NULL,
    created_at DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='聊天消息';
```

```sql
INSERT INTO chat_message (user_id, nickname, content) VALUES
(1, '张三', '今天天气真好 😄☀️🌈'),
(2, '李四', '支持!👍 一起吃饭?🍚🍜'),
(3, '王五', '🚀🚀🚀 走起');

SELECT nickname, content FROM chat_message WHERE content LIKE '%😄%';
SELECT nickname, CHAR_LENGTH(content) AS chars, OCTET_LENGTH(content) AS bytes
FROM chat_message;
```

emoji 在 `utf8mb4` 下每个占 4 字节,所以 `VARCHAR(500)` 实际最大 2000 字节。

### 4. 字符集相关命令

```sql
-- 查看服务器字符集
SHOW VARIABLES LIKE 'character_set%';

-- 修改库字符集
ALTER DATABASE mydb CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 修改表字符集
ALTER TABLE mytable CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 修改列字符集
ALTER TABLE mytable MODIFY name VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 5. JDBC 连接串设置(避免编码坑)

```text
jdbc:mysql://host:3306/db?useUnicode=true&characterEncoding=utf8&useSSL=false
```

新版驱动推荐 `characterEncoding=UTF-8`,并与服务端字符集保持一致。

---

## 十、注释语法与 SQL 规范

### 1. 注释语法

```sql
-- 单行注释(两个连字符 + 空格)

# 单行注释(MySQL 特有,不是标准 SQL)

/*
   多行注释
   可以跨行
*/
```

### 2. 表与字段注释

```sql
CREATE TABLE order_info (
    id          BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT COMMENT '订单主键',
    order_no    VARCHAR(32)      NOT NULL             COMMENT '订单编号',
    amount      DECIMAL(12, 2)   NOT NULL DEFAULT 0   COMMENT '订单金额(元)',
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='订单表';
```

`SHOW CREATE TABLE order_info;` 会显示所有注释,文档化效果极佳。

### 3. 大小写规范

#### 关键字和函数名

**大写**(行业惯例,与官方文档一致):

```sql
SELECT id, name FROM users WHERE age > 18 ORDER BY id DESC;
```

#### 表名、列名

**小写 + 下划线**(Linux 下 MySQL 默认表名/库名区分大小写,Windows 不区分):

```sql
user_profile、order_item、create_time、is_deleted
```

**避免**:

- 驼峰:`userId` (Windows 开发、Linux 部署会出 bug)
- 全大写:`USERID` (难读)
- 拼音:`yonghu_id` (难懂)

#### 保留字

避免使用 `order`、`user`、`key`、`desc` 等保留字做列名。如果必须用,加反引号:

```sql
`order` VARCHAR(20)  -- 反引号转义
```

或者改名:`order_no`、`order_id`。

### 4. 命名规范示例

```text
表名:t_<业务>_<子模块>,如 t_mall_order、t_user_profile
库名:业务名,如 mall、user_center、log_service
索引名:idx_<列名>、uk_<列名>、pk_<表名>
视图名:v_<用途>
存储过程名:sp_<用途>
```

### 5. SQL 编写顺序 vs 执行顺序

编写 SQL 时,各子句有固定顺序,**执行顺序与编写顺序不同**:

| 顺序 | 子句              | 说明               |
|------|-------------------|--------------------|
| 1    | `FROM`            | 先选表             |
| 2    | `WHERE`           | 行过滤             |
| 3    | `GROUP BY`        | 分组               |
| 4    | `HAVING`          | 组过滤             |
| 5    | `SELECT`          | 选列               |
| 6    | `DISTINCT`        | 去重               |
| 7    | `ORDER BY`        | 排序               |
| 8    | `LIMIT`           | 限制条数           |

理解这一点能解释很多**奇怪的 SQL 错误**(如 `WHERE` 里不能用 `SELECT` 里的别名)。

---

## 十一、完整建表语句模板

下面给出一份**接近生产规范**的建表模板,涵盖上述所有要点。

```sql
CREATE TABLE `t_user` (
    `id`             BIGINT UNSIGNED      NOT NULL AUTO_INCREMENT                COMMENT '主键 ID',
    `user_no`        VARCHAR(32)          NOT NULL                                COMMENT '用户编号(对外)',
    `username`       VARCHAR(64)          NOT NULL                                COMMENT '用户名',
    `password_hash`  CHAR(64)             NOT NULL                                COMMENT '密码哈希(SHA-256)',
    `email`          VARCHAR(128)                                                 COMMENT '邮箱',
    `phone`          CHAR(11)                                                      COMMENT '手机号',
    `nickname`       VARCHAR(64)          NOT NULL DEFAULT ''                     COMMENT '昵称',
    `avatar`         VARCHAR(255)                                                 COMMENT '头像 URL',
    `gender`         TINYINT              NOT NULL DEFAULT 0                      COMMENT '0=未知 1=男 2=女',
    `birthday`       DATE                                                          COMMENT '生日',
    `balance_cents`  BIGINT UNSIGNED      NOT NULL DEFAULT 0                      COMMENT '账户余额(分)',
    `status`         TINYINT UNSIGNED     NOT NULL DEFAULT 0                      COMMENT '0=正常 1=禁用 2=注销',
    `profile`        JSON                                                          COMMENT '用户画像',
    `extra`          JSON                                                          COMMENT '扩展字段',
    `last_login_at`  DATETIME                                                      COMMENT '上次登录',
    `created_at`     DATETIME              NOT NULL DEFAULT CURRENT_TIMESTAMP      COMMENT '创建时间',
    `updated_at`     DATETIME              NOT NULL DEFAULT CURRENT_TIMESTAMP
                                              ON UPDATE CURRENT_TIMESTAMP          COMMENT '更新时间',
    `is_deleted`     TINYINT(1)            NOT NULL DEFAULT 0                      COMMENT '逻辑删除:0=否 1=是',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_user_no`   (`user_no`),
    UNIQUE KEY `uk_username`  (`username`),
    UNIQUE KEY `uk_phone`     (`phone`),
    KEY `idx_email`           (`email`),
    KEY `idx_status_created`  (`status`, `created_at`),
    KEY `idx_profile_city`    ((`profile`->>'$.city'))
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci
  COMMENT='用户表';
```

### 模板要点解析

| 字段             | 选型理由                                       |
|------------------|------------------------------------------------|
| `id BIGINT UNSIGNED AUTO_INCREMENT` | 主键足够大,无符号增加正数范围                  |
| `user_no VARCHAR(32)` | 对外暴露的编号,可以不用自增,避免暴露 ID 趋势 |
| `password_hash CHAR(64)` | 固定 64 位,CHAR 省空间                     |
| `phone CHAR(11)`  | 中国手机号固定长度                              |
| `balance_cents BIGINT UNSIGNED` | 用"分"做单位,避免 DECIMAL 计算开销           |
| `gender TINYINT`  | 0/1/2 三个值,小巧                              |
| `profile JSON`    | 灵活扩展                                        |
| `created_at/updated_at DATETIME` | 标准时间字段                            |
| `is_deleted TINYINT(1)` | 逻辑删除标记,不真删数据                   |
| `idx_profile_city` | JSON 表达式索引,常用查询走索引                |

### 配套的索引设计原则

1. **主键**:必有,通常是 `id`
2. **唯一键**:业务唯一字段(`user_no`、`username`、`phone`)
3. **普通索引**:`WHERE`、`JOIN`、`ORDER BY` 涉及的列
4. **联合索引**:遵循**最左前缀原则**,常用字段放左边
5. **索引数量**:单表不超过 5~6 个,过多会拖慢写入
6. **选择性低的字段**(如 `gender`、`status`)不单独建索引,但可作为联合索引前缀

---

## 十二、核心要点速记

- **SQL 五大分类**:DDL(结构) / DML(数据) / DQL(查询) / DCL(权限) / TCL(事务)
- **金额用 DECIMAL** 或 **BIGINT 存分**,绝不 FLOAT/DOUBLE
- **整数类型大小**:TINYINT(1B) < SMALLINT(2B) < MEDIUMINT(3B) < INT(4B) < BIGINT(8B)
- **VARCHAR(N) 的 N 是字符数**,不是字节数;实际最大 65535 字节,受行大小限制
- **CHAR 定长补空格**,适合 MD5、身份证等定长字段;VARCHAR 适合变长
- **TEXT/BLOB 不能有默认值**,且 MySQL 5.6 前只能前缀索引
- **时间类型选型**:业务时间用 `DATETIME`,记录更新时间用 `DATETIME + 自动维护`,跨时区业务存 UTC + 时区
- **TIMESTAMP 有 2038 问题**,趋势是用 `DATETIME` 替代
- **JSON 类型**:5.7+ 支持,可用 `->` `->>` 访问,8.0 支持 `JSON_TABLE` 和表达式索引
- **字符集永远用 utf8mb4**:MySQL 的 utf8 是阉割版,不支持 emoji
- **排序规则**:一般业务用 `utf8mb4_unicode_ci` 或 8.0 默认的 `utf8mb4_0900_ai_ci`,密码/区分大小写用 `utf8mb4_bin`
- **主键首选 BIGINT UNSIGNED 自增**;分布式场景用雪花 ID 或 UUID v7
- **逻辑删除**:用 `is_deleted TINYINT(1) DEFAULT 0` 字段,而不是物理 DELETE
- **注释三件套**:表注释、列注释、关键字段必须 `COMMENT '...'`
- **命名规范**:库表列小写下划线、关键字大写、避免保留字
- **索引最左前缀**:联合索引 `(a, b, c)` 可加速 `a`、`a+b`、`a+b+c`,不能跳过 a
- **DDL 在 8.0 之前不参与事务**,大表 ALTER 用 `pt-online-schema-change` 或 `gh-ost`
- **JDBC URL 务必**带 `useUnicode=true&characterEncoding=UTF-8`,和服务端字符集一致