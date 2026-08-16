# PostgreSQL 概述与安装

## 一、PostgreSQL 简介

### 1.1 什么是 PostgreSQL

**PostgreSQL**(通常简称 **PG**)是一个功能强大的**开源对象-关系型数据库管理系统(ORDBMS)**。它的名字读作 *post-gress-Q-L*。

**核心定位**:

- **OLTP + OLAP 兼顾**:既适合高并发事务,也擅长复杂分析查询
- 由 **加州大学伯克利分校(UC Berkeley)** 的 **Michael Stonebraker** 教授及其团队开发
- 采用 **BSD 风格许可证**(类似 MIT),可自由使用、商用、修改、闭源分发
- 历经 30+ 年持续迭代,被业界誉为 **"世界上最先进的开源数据库"**

### 1.2 发展历史

```text
┌──────────────────────────────────────────────────────────┐
│ 1973   Michael Stonebraker 启动 Ingres 项目(关系模型先驱)│
│   ↓                                                       │
│ 1986   Stonebraker 启动 POSTGRES(解决 Ingres 的不足)    │
│        引入"对象-关系"模型、用户自定义类型、规则系统    │
│   ↓                                                       │
│ 1994   Postgres95 发布,加入 SQL 解释器                   │
│   ↓                                                       │
│ 1996   正式更名为 PostgreSQL 6.0,确立开源路线           │
│   ↓                                                       │
│ 2005   8.0:Windows 原生支持、点阵、SAVEPOINT、Schema     │
│   ↓                                                       │
│ 2010   9.0:流复制、热备、流式复制、内置 binlog 同步     │
│   ↓                                                       │
│ 2014   9.4:JSONB 类型(引发 NoSQL 反击战)                │
│   ↓                                                       │
│ 2017   10:逻辑复制(Logical Replication)、表分区、并行  │
│   ↓                                                       │
│ 2020   13:增量排序、B-tree 去重、行级安全增强            │
│   ↓                                                       │
│ 2021   14:性能大幅提升(对标 MySQL 8.0)、SQL/JSON 标准   │
│   ↓                                                       │
│ 2023   16:逻辑复制订阅者端并行应用、pg_stat_io、        │
│        pg_buffercache 增强                                │
│   ↓                                                       │
│ 2024   17:大规模逻辑复制改进、内存/IO 优化、            │
│        增量备份合并、SQL/JSON 构造函数(JSON_TABLE)      │
│   ↓                                                       │
│ 2025+  18:持续演进(异步 I/O 子系统、列式索引探索)       │
└──────────────────────────────────────────────────────────┘
```

### 1.3 关键里程碑人物:Michael Stonebraker

| 年份     | 事件                                                       |
|----------|------------------------------------------------------------|
| 1973     | 启动 **Ingres**(使用查询语言 QUEL,关系数据库先驱)         |
| 1986     | 启动 POSTGRES(后继项目,引入抽象数据类型 ADT)              |
| 1992     | 启动 Mariposa(分布式数据库探索)                           |
| 2014     | 获得 **图灵奖**(数据库领域最高荣誉)                       |
| 持续至今 | 在 MIT 担任教授,推动数据库理论发展                        |

> **Ingres 启示**:Ingres 演变为商业产品(Ingres Corp → Actian),并启发了 Sybase、SQL Server、Informix 等后续产品。PostgreSQL 则坚持开源路线,成为 Ingres 精神最纯正的继承者。

### 1.4 版本演进

| 大版本 | 发布时间 | 主要特性                                                                | 状态       |
|--------|----------|-------------------------------------------------------------------------|------------|
| 7.x    | 2000-2005 | 早期版本,加入 PL/pgSQL、模式(Schema)、外连接                        | 历史       |
| 8.0    | 2005     | Windows 原生支持、点阵、嵌套事务                                        | 历史       |
| 8.4    | 2009     | 窗口函数、CTE、默认权限、列级权限                                       | 历史       |
| 9.0    | 2010     | 流复制、热备、内置 replication                                          | 历史       |
| 9.4    | 2014     | **JSONB 类型**(真正改变行业格局)                                       | 历史       |
| 9.6    | 2016     | 并行顺序扫描、并行 JOIN、phrase 全文检索                                | 历史       |
| 10     | 2017     | 逻辑复制、原生表分区、声明式分区、并行 btree 创建                       | 历史       |
| 11     | 2018     | 过程内事务、hash 分区、JIT 编译(表达式)                                | 历史       |
| 12     | 2019     | 内置生成列、CTE 物化控制、pluggable 存储接口                           | EOL        |
| 13     | 2020     | 增量排序、B-tree 去重、并行索引清理、逻辑复制订阅者并行                 | EOL        |
| 14     | 2021     | SQL/JSON 路径、range 聚合、性能提升(对标 MySQL 8.0)                  | 仍广泛使用 |
| 15     | 2022     | MERGE 语句(ANSI SQL 标准)、逻辑复制行过滤、`pg_basebackup` 增量       | 广泛使用   |
| 16     | 2023     | 逻辑复制并行应用、pg_stat_io、性能/IO 优化                             | 推荐生产   |
| 17     | 2024     | 大规模逻辑复制改进、增量备份合并、SQL/JSON 构造函数                    | 推荐生产   |
| 18     | 2025+    | 异步 I/O 子系统、列式索引、持续优化                                    | 新版本     |

> **版本支持策略**:PostgreSQL 由全球社区维护,**每个大版本支持 5 年**(每年一个 minor release)。生产推荐 **PG 16** 或 **PG 17**。

### 1.5 社区与生态

| 组件               | 说明                                                            |
|--------------------|-----------------------------------------------------------------|
| **postgresql.org** | 官方网站与文档中心(英文文档质量业内顶尖)                       |
| **PGCon / PGDay**  | 全球年度开发者大会                                               |
| **pgsql-hackers**  | 核心开发者邮件列表(提交 patch 都从这里发起)                    |
| **postgresql.org/list** | 邮件列表归档,问题排查第一站                                |
| **Stack Overflow** | 标签 `postgresql`,问答量超 10 万                                |
| **GitHub Mirror**  | git.postgresql.org 主仓,GitHub 自动镜像                          |
| **EnterpriseDB**   | 商业公司(被 Percona/Bridgecrew 收购历史中,提供 PG 商业发行版)   |
| **Citus / Hydra**  | 扩展厂商(水平扩展、列存储)                                     |
| **pgAdmin / DBeaver / Navicat** | 主流 GUI 客户端                                       |
| **Supabase / Neon / RDS** | 云厂商的 PG 服务                                       |

---

## 二、PostgreSQL 特点

PostgreSQL 之所以被誉为"最先进的开源数据库",源于其设计哲学:**标准优先、扩展为王、数据完整性第一**。

### 2.1 主要特性一览

| 维度         | 说明                                                                                  |
|--------------|---------------------------------------------------------------------------------------|
| **开源协议** | PostgreSQL License(BSD 风格),允许商用、修改、闭源分发,**无任何使用限制**           |
| **SQL 标准** | 业界最接近 SQL:2016 标准的实现,支持 CTE、窗口函数、递归查询、`MERGE`(15+)、LATERAL  |
| **ACID**     | 完整支持,**默认最高隔离级别为 Read Committed**,也提供 Serializable(SSI)              |
| **MVCC**     | 多版本并发控制,写不阻塞读、读不阻塞写,历史版本保留到 vacuum                           |
| **丰富类型** | 内置数组、JSONB、范围、几何、网络地址、UUID、XML、TSVECTOR、hstore、自定义类型         |
| **扩展机制** | `CREATE EXTENSION` 一键启用,**生态丰富**:PostGIS、pg_trgm、pg_cron、TimescaleDB、pgvector |
| **自定义函数** | PL/pgSQL、PL/Python、PL/Perl、PL/Tcl、C 函数,**支持 JIT 编译**                  |
| **索引丰富** | B-tree、Hash、GIN、GiST、BRIN、SP-GiST、bloom,多种索引适配不同场景                   |
| **分区表**   | 范围、列表、哈希分区,**支持分区裁剪**                                                |
| **逻辑复制** | 表级、跨版本复制,可构建 CDC 管道                                                       |
| **物理复制** | 流复制(WAL Shipping)+ 同步/异步备库 + 级联复制                                     |
| **可靠性**   | WAL 预写日志、CRC 校验、checksum 备份、流式备份、增量备份(PG17 增强)                  |
| **安全**     | 行级安全(RLS)、列级权限、SCRAM-SHA-256 认证、SSL/TLS、审计(pgaudit)                |
| **国际化**   | ICU 排序规则、字符集齐全、GB18030 / EUC_CN / UTF8                                    |

### 2.2 核心能力详解

#### 2.2.1 MVCC(多版本并发控制)

```text
事务 A 修改一行 ─→ 新版本(xmin=A)
                ↓
              旧版本保留(t_xmax = A)
                ↓
事务 B 读 → 看到事务 A 修改前的版本(快照隔离)
```

- **优点**:读写不阻塞,无锁读取
- **代价**:需要 **VACUUM** 清理死元组(dead tuples)

#### 2.2.2 扩展机制

```sql
-- 启用 PostGIS(地理信息)
CREATE EXTENSION postgis;

-- 启用向量检索(pgvector,AI 时代标配)
CREATE EXTENSION vector;

-- 启用定时任务(pg_cron)
CREATE EXTENSION pg_cron;
```

> 这是 PostgreSQL 与其他数据库最大的区别:**它的内核就是一个可编程平台**。

#### 2.2.3 自定义类型与函数

```sql
-- 创建复合类型
CREATE TYPE address AS (
  street TEXT,
  city   TEXT,
  zip    TEXT
);

-- PL/pgSQL 函数
CREATE FUNCTION add(a INT, b INT) RETURNS INT AS $$
BEGIN
  RETURN a + b;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- C 函数(性能极致)
-- 通过 PG_FUNCTION_INFO_V1 宏注册
```

### 2.3 不适合的场景(诚实告知)

| 场景                  | 原因                                    | 建议选型                |
|-----------------------|-----------------------------------------|-------------------------|
| 简单 KV 缓存          | 杀鸡用牛刀,Redis 更轻量                | Redis / KeyDB           |
| 超大规模宽列存储      | 列存压缩比、写入吞吐不及 ClickHouse     | ClickHouse / Doris      |
| 文档数据库强需求      | PG 虽支持 JSONB,但无 MongoDB 灵活      | MongoDB                 |
| 极致写入吞吐(>10万/s)| MVCC 元组维护成本高                    | Cassandra / ScyllaDB   |
| 单机嵌入式            | 进程模型重,不适合嵌入                  | SQLite                  |

---

## 三、PostgreSQL 与其他数据库对比

### 3.1 与 MySQL 对比

| 维度             | PostgreSQL 16/17                | MySQL 8.0/8.4              |
|------------------|--------------------------------|----------------------------|
| 许可证           | BSD 风格(完全自由)              | GPL v2(社区版)/商业       |
| 默认引擎         | 自研,无切换概念                | InnoDB                     |
| SQL 规范         | **强**(业界最贴近 SQL 标准)    | 弱                         |
| 复杂查询         | **强**(CTE/递归/物化视图/窗口) | 一般(8.0 后增强)          |
| JSON 支持        | JSONB(二级制、可索引 GIN)      | JSON 类型(文本优化)        |
| 并发控制         | MVCC(SSI 可序列化)            | MVCC(Next-Key Lock)        |
| 主从复制         | 流复制 + 逻辑复制              | 主从 + 组复制 + 半同步      |
| 分区             | 原生范围/列表/哈希分区          | 原生分区(8.0+)            |
| 扩展             | CREATE EXTENSION 丰富生态      | 插件式                     |
| 写入性能         | 中等                           | 简单写更快                 |
| 索引类型         | B-tree/Hash/GIN/GiST/BRIN/SP-GiST | B-tree/Hash/FullText/R-Tree |
| 全文搜索         | 内置 tsvector + GIN            | FULLTEXT                   |
| 物化视图         | **支持**(可定时刷新)           | 不支持                     |
| 适用场景         | 复杂业务、地理信息、BI、AI      | Web 后台、OLTP             |

### 3.2 与 Oracle 对比

| 维度         | PostgreSQL                  | Oracle                  |
|--------------|------------------------------|-------------------------|
| 许可证       | BSD(免费)                   | 商业(昂贵)             |
| SQL 兼容     | 高度兼容(PL/SQL 大部分可移植) | 原生                    |
| 性能         | 同等硬件上 80~90% 性能       | 极限调优后略胜          |
| RAC          | 无原生(需外部方案)          | RAC(集群)              |
| Data Guard   | 物理 + 逻辑复制可替代        | Data Guard              |
| AWR 报告     | pg_stat_statements 替代      | AWR                     |
| 学习曲线     | 较平缓                       | 陡峭                    |
| 总拥有成本   | **低**                      | **极高**                |

> **核心结论**:对于绝大多数企业级 OLTP + 报表需求,PostgreSQL 完全可以替代 Oracle,且成本接近零。

### 3.3 与 SQL Server 对比

| 维度         | PostgreSQL                | SQL Server                |
|--------------|----------------------------|---------------------------|
| 平台         | Linux/Windows/macOS        | 强绑定 Windows(2017+ 也支持 Linux) |
| 许可证       | BSD                        | 商业(Developer 免费)    |
| T-SQL 兼容   | 弱(需重写)               | 原生                     |
| SSIS/SSRS    | 无原生(ETL 工具外置)      | 原生 BI 平台             |
| 性能         | 复杂查询更优              | OLTP 略胜                |
| 管理工具     | pgAdmin / DBeaver         | SSMS(行业标杆)          |

### 3.4 与 MongoDB 对比

| 维度       | PostgreSQL                   | MongoDB                 |
|------------|------------------------------|-------------------------|
| 数据模型   | 关系表 + JSONB(混合)         | BSON 文档(Schema-less) |
| 事务       | ACID                         | 4.0+ 多文档事务         |
| 水平扩展   | 弱(扩展需 Citus)            | 原生分片(强)            |
| 查询语言   | SQL                          | MongoDB Query Language  |
| 适用       | 结构化 + 半结构化业务       | 海量文档、日志、灵活 schema |

---

## 四、PostgreSQL 安装方式

PostgreSQL 提供 **5 种主要安装方式**。生产环境推荐使用 **官方包管理器仓库**(yum/apt)或 **Docker**。

### 4.1 源码编译安装(高级用户)

#### 4.1.1 下载源码

```bash
# 官方镜像:https://www.postgresql.org/ftp/source/
wget https://ftp.postgresql.org/pub/source/v17.0/postgresql-17.0.tar.gz
```

#### 4.1.2 安装编译依赖

```bash
# RHEL/CentOS
sudo dnf install -y gcc make readline-devel zlib-devel \
    bison flex openssl-devel perl-devel \
    python3-devel libxml2-devel libxslt-devel \
    libicu-devel

# Debian/Ubuntu
sudo apt install -y build-essential libreadline-dev zlib1g-dev \
    bison flex libssl-dev libperl-dev \
    python3-dev libxml2-dev libxslt1-dev \
    libicu-dev
```

#### 4.1.3 编译与安装

```bash
tar -xzf postgresql-17.0.tar.gz
cd postgresql-17.0

# 配置
./configure --prefix=/usr/local/pgsql \
    --with-openssl \
    --with-python \
    --with-perl \
    --with-icu \
    --enable-nls=zh_CN

# 编译(使用所有 CPU)
make -j$(nproc)
# 注意:PostgreSQL 用 GNU make,某些平台需 gmake

# 安装
sudo make install
```

#### 4.1.4 创建用户与初始化

```bash
# 创建用户
useradd -r -d /var/lib/pgsql -s /bin/bash postgres

# 创建数据目录
mkdir -p /var/lib/pgsql/data
chown -R postgres:postgres /var/lib/pgsql

# 切换用户初始化
sudo -u postgres /usr/local/pgsql/bin/initdb -D /var/lib/pgsql/data
```

> **编译安装适用场景**:需要特定优化、嵌入自定义 patch、学习 PG 内部实现、内核开发者。

### 4.2 包管理器安装(推荐生产)

#### 4.2.1 Debian/Ubuntu(使用 apt)

```bash
# 1. 添加官方仓库(以 PG 17 为例)
sudo sh -c 'echo "deb https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'

# 2. 添加 GPG key
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo gpg --dearmor -o /etc/apt/trusted.gpg.d/postgresql.gpg

# 3. 更新索引
sudo apt update

# 4. 安装
sudo apt install postgresql-17 postgresql-client-17

# 5. 自动创建用户、数据库、systemd 服务
#    默认 postgres 用户、/etc/postgresql/17/main/、端口 5432

# 6. 服务管理
sudo systemctl status postgresql
sudo systemctl start postgresql
```

#### 4.2.2 RHEL/CentOS/Rocky/Alma(使用 yum/dnf)

```bash
# 1. 安装官方仓库
sudo dnf install -y https://download.postgresql.org/pub/repos/yum/reporpms/EL-9-x86_64/pgdg-redhat-repo-latest.noarch.rpm

# 2. 禁用系统默认的 postgres 模块(RHEL 8/9 自带较低版本)
sudo dnf -qy module disable postgresql

# 3. 安装
sudo dnf install -y postgresql17-server postgresql17-contrib

# 4. 初始化数据库(仅第一次)
sudo /usr/pgsql-17/bin/postgresql-17-setup initdb

# 5. 启动服务
sudo systemctl enable postgresql
sudo systemctl start postgresql
```

#### 4.2.3 包管理器安装的特点

- 自动创建 `postgres` 用户
- 自动生成数据目录(默认 `/var/lib/pgsql/16/data` 或 `/etc/postgresql/16/main/`)
- 自动注册 systemd 服务
- 自动安装 contrib 包(`pg_stat_statements`、`pg_trgm` 等常用扩展)

### 4.3 图形化安装(Windows)

#### 4.3.1 EnterpriseDB Installer

Windows 推荐使用 **EnterpriseDB(EDB)** 提供的图形化安装包:

```text
1. 下载:https://www.enterprisedb.com/downloads/postgres-postgresql-downloads
   选择 Windows x86-64,版本 16 或 17
2. 双击 .exe,选择安装路径(如 C:\PostgreSQL\17)
3. 选择安装组件:
   - PostgreSQL Server      (必选)
   - pgAdmin 4              (图形化客户端)
   - Stack Builder          (后续装扩展工具)
   - Command Line Tools     (psql 等)
4. 设置数据目录(如 D:\pgdata)
5. 设置 postgres 超级用户密码
6. 设置端口(默认 5432)
7. 设置 locale(Chinese (Simplified), China)
8. 完成安装
```

#### 4.3.2 安装后的目录

```text
C:\PostgreSQL\17\
├── bin\                       可执行文件(psql.exe、pg_ctl.exe 等)
├── data\                      数据目录(默认)
├── include\                   C 头文件
├── lib\                       动态库、扩展
├── share\                     文档、扩展 SQL 脚本
└── pgAdmin 4\                 pgAdmin 独立安装
```

### 4.4 Docker 安装(开发测试推荐)

#### 4.4.1 官方镜像

```bash
# 拉取
docker pull postgres:17

# 启动
docker run -d \
  --name pg17 \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_DB=appdb \
  -p 5432:5432 \
  -v /data/pgdata:/var/lib/postgresql/data \
  postgres:17

# 进入
docker exec -it pg17 psql -U postgres -d appdb

# 查看日志
docker logs -f pg17
```

> **环境变量说明**:
> - `POSTGRES_PASSWORD`:必填,设置 postgres 用户密码
> - `POSTGRES_USER`:可选,默认 `postgres`
> - `POSTGRES_DB`:可选,默认 `postgres`
> - `PGDATA`:可选,数据目录(默认 `/var/lib/postgresql/data`)

#### 4.4.2 Docker Compose

```yaml
# docker-compose.yml
services:
  postgres:
    image: postgres:17
    container_name: pg17
    environment:
      POSTGRES_PASSWORD: postgres
      POSTGRES_USER: postgres
      POSTGRES_DB: appdb
      TZ: Asia/Shanghai
    ports:
      - "5432:5432"
    volumes:
      - pg_data:/var/lib/postgresql/data
      - ./conf/postgresql.conf:/etc/postgresql/postgresql.conf
      - ./initdb.d:/docker-entrypoint-initdb.d
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  pg_data:
```

#### 4.4.3 带 PostGIS 的镜像

```bash
docker pull postgis/postgis:17-3.4
docker run -d --name pg-postgis -e POSTGRES_PASSWORD=postgres postgis/postgis:17-3.4
```

### 4.5 各发行版打包的 PG(了解即可)

| 发行版           | 默认 PG 版本           | 说明                       |
|------------------|------------------------|----------------------------|
| Debian 12        | 15                     | apt 直接装                 |
| Ubuntu 22.04 LTS | 14                     | apt 直接装                 |
| Ubuntu 24.04 LTS | 16                     | apt 直接装                 |
| CentOS 7         | 9.2                    | 较旧,需升级               |
| RHEL 8           | 10(module)/16(repo)   | 需切换                     |
| AlmaLinux 9      | 13(module)/16(repo)   | 需切换                     |

> **强烈建议**:不要使用发行版默认仓库的 PG(版本较老),而使用 **PEDB 官方仓库** 或 **postgresql.org 官方仓库**。

### 4.6 安装方式对比

| 方式           | 难度 | 升级 | 性能         | 适合场景         |
|----------------|------|------|--------------|------------------|
| apt/yum 官方源 | ★    | ★★★   | 一致         | 生产、桌面、CI    |
| 源码编译       | ★★★★ | ★    | 可调优       | 定制、内核开发    |
| 图形化(Windows)| ★    | ★★   | 一致         | Windows 桌面      |
| Docker         | ★    | ★★★   | 几乎无开销  | 开发、测试、CI    |

### 4.7 安装后验证

```bash
# 1. 查看版本
postgres --version
# postgres (PostgreSQL) 17.0

# 2. psql 连接测试
psql -U postgres -c "SELECT version();"

# 3. 查看数据目录
psql -U postgres -c "SHOW data_directory;"

# 4. 查看编译选项
pg_config --configure
# ' --prefix=/usr/local/pgsql' '--with-openssl' '--with-icu' ...

# 5. 检查所有扩展
psql -U postgres -c "SELECT * FROM pg_available_extensions ORDER BY name;"
```

---

## 五、PostgreSQL 目录结构

PostgreSQL 安装后主要分 **三类目录**:

- `prefix`(安装根):程序、二进制、库
- `PGDATA`(数据目录):数据库集群存储
- `config`(配置文件):`postgresql.conf`、`pg_hba.conf`、`pg_ident.conf`

### 5.1 默认路径总览

| 安装方式       | prefix                       | PGDATA(数据目录)               | 配置文件                       |
|----------------|------------------------------|--------------------------------|--------------------------------|
| Debian/Ubuntu  | /usr/lib/postgresql/17/      | /var/lib/postgresql/17/main/   | /etc/postgresql/17/main/       |
| RHEL/CentOS    | /usr/pgsql-17/               | /var/lib/pgsql/17/data/       | /var/lib/pgsql/17/data/        |
| 源码编译       | /usr/local/pgsql/            | 自定义                         | 自定义                         |
| Docker         | /usr/local/postgresql/       | /var/lib/postgresql/data/      | /var/lib/postgresql/data/      |
| Windows EDB    | C:\PostgreSQL\17\            | data\                          | data\                          |

### 5.2 prefix 目录结构

```text
/usr/local/pgsql/                          (prefix)
├── bin/                                   可执行文件
│   ├── postgres                           主服务进程(单用户也可)
│   ├── pg_ctl                             服务控制脚本
│   ├── initdb                             初始化数据库
│   ├── psql                               交互式客户端
│   ├── pg_dump / pg_dumpall               逻辑备份
│   ├── pg_restore                         逻辑恢复
│   ├── pg_basebackup                      物理备份
│   ├── pg_receivewal / pg_recvlogical     流接收
│   ├── createdb / dropdb / createuser     管理命令
│   ├── pg_isready                         检查服务
│   ├── pg_config                          查看编译选项
│   ├── pg_rewind                          时间线同步(从备升主)
│   ├── vacuumdb / reindexdb               维护命令
│   └── pg_upgrade                         大版本升级
├── lib/                                   动态库、扩展
│   └── postgresql/                        扩展 .so 文件
├── share/                                 文档、扩展 SQL
│   ├── postgresql/                        时区、字符集
│   ├── extension/                         扩展脚本
│   └── timezone/                          时区数据
├── include/                               C 头文件(postgresql.h 等)
├── doc/                                   HTML 文档
└── log/                                   日志(自定义)
```

### 5.3 PGDATA 目录结构

PGDATA 是 PostgreSQL 的 **数据库集群**(database cluster),不是单个数据库。

```text
/var/lib/pgsql/17/data/                    (PGDATA)
├── PG_VERSION                             版本标识(17)
├── postgresql.conf                        主配置文件
├── pg_hba.conf                            主机认证配置
├── pg_ident.conf                          ident 映射(可选)
├── postgresql.auto.conf                   ALTER SYSTEM 设置
├── postmaster.opts                        启动参数记录
├── postmaster.pid                         主进程 PID
├── global/                                全局系统表
│   ├── pg_authid                          用户/角色
│   ├── pg_database                        数据库
│   └── pg_tablespace                      表空间
├── base/                                  各数据库数据
│   ├── 1/                                 postgres 库(oid=1)
│   ├── 4/                                 template1 库(oid=4)
│   ├── 16384/                             template0 库(oid=4 → 改名)
│   └── 16385/                             用户数据库
│       ├── 1247                            表/索引文件
│       └── 1249
├── pg_wal/                                WAL 日志(原 pg_xlog)
│   ├── 000000010000000000000001            WAL 段文件(16MB)
│   └── ...
├── pg_xact/                               事务提交状态
│   └── 0000
├── pg_multixact/                          多事务状态
├── pg_subtrans/                           子事务状态
├── pg_stat/                               统计信息(临时)
├── pg_stat_tmp/                           统计临时文件
├── pg_logical/                            逻辑复制状态
│   └── mappings/
├── pg_replslot/                           复制槽
├── pg_snapshots/                          导出快照
├── pg_dynshmem/                           动态共享内存
├── pg_notify/                             LISTEN/NOTIFY 队列
├── pg_serial/                             序列
├── pg_twophase/                           两阶段提交
├── pg_commit_ts/                          提交时间戳
├── backups/                               pg_basebackup 输出
└── pg_wal_archive_status/                 已归档标记
```

### 5.4 关键文件详解

| 目录/文件             | 作用                                                  |
|-----------------------|-------------------------------------------------------|
| **PG_VERSION**        | 记录数据库主版本号(`17`)                             |
| **base/**             | 各数据库的数据文件,每个数据库一个 oid 子目录         |
| **global/**           | 全局共享的系统表(用户、角色等)                       |
| **pg_wal/**           | WAL(预写日志),支持 PITR、流复制                      |
| **pg_xact/**          | 事务提交状态,用于 MVCC 可见性判断                    |
| **pg_stat/**          | 统计信息(查询、I/O 等),重启会清空                    |
| **pg_logical/**       | 逻辑复制状态(订阅者重启恢复)                         |
| **pg_replslot/**      | 复制槽,防止备库断连导致 WAL 被回收                   |
| **pg_snapshots/**     | 导出快照(用于一致性备份)                             |
| **postmaster.pid**    | 主进程 PID + 监听端口,**PostgreSQL 启动时独占**      |
| **postgresql.auto.conf** | `ALTER SYSTEM` 写入,**会在 reload 时合并到主配置** |

### 5.5 postgresql.auto.conf 与配置合并

```sql
-- 动态配置持久化(写入 postgresql.auto.conf)
ALTER SYSTEM SET shared_buffers = '8GB';
SELECT pg_reload_conf();
```

> **配置加载优先级**:`postgresql.conf` → `postgresql.auto.conf`(后写者覆盖),→ 启动参数(命令行,最终优先级)。

### 5.6 查看实际路径

```sql
-- 进入 psql 后
SHOW data_directory;
SHOW config_file;
SHOW hba_file;
SHOW ident_file;
SHOW server_version;
SHOW shared_buffers;
```

---

## 六、PostgreSQL 启动与停止

### 6.1 启动方式选择流程

```text
┌───────────────────────────────────────────────────────┐
│              PostgreSQL 启动方式选择                  │
│                                                       │
│  systemd 服务? ──── Yes ───→ systemctl start postgresql│
│       │                                               │
│       No                                              │
│       ↓                                               │
│  SysV init? ──── Yes ───→ service postgresql start    │
│       │                                               │
│       No                                              │
│       ↓                                               │
│  pg_ctl start(通用,所有平台可用)                     │
│       │                                               │
│       No                                              │
│       ↓                                               │
│  直接 postgres -D PGDATA(调试)                       │
└───────────────────────────────────────────────────────┘
```

### 6.2 启动方式对比

| 方式                    | 适用平台            | 优点                       | 缺点                       |
|-------------------------|---------------------|----------------------------|----------------------------|
| `systemctl`             | systemd 发行版      | 标准化、日志集成、自启     | 不直接支持多实例           |
| `service`               | SysV 老系统         | 兼容性好                   | 已被 systemd 取代         |
| `pg_ctl`                | 通用                | 跨平台、支持多实例         | 无服务管理                 |
| 直接 `postgres`         | 调试                | 前台运行看日志             | 无守护进程化               |

### 6.3 systemctl 方式(主流发行版)

```bash
# 启动
sudo systemctl start postgresql

# 停止
sudo systemctl stop postgresql

# 重启
sudo systemctl restart postgresql

# 重新加载配置(部分参数)
sudo systemctl reload postgresql

# 状态
sudo systemctl status postgresql

# 开机自启
sudo systemctl enable postgresql

# 取消自启
sudo systemctl disable postgresql

# 查看日志
sudo journalctl -u postgresql -f
```

**systemd 单元文件位置**:

```bash
# Debian/Ubuntu
/lib/systemd/system/postgresql.service

# RHEL/CentOS
/usr/lib/systemd/system/postgresql-17.service
```

### 6.4 pg_ctl 方式(通用推荐)

`pg_ctl` 是 PostgreSQL **官方封装**的启动器,跨平台、简单可靠。

```bash
# 启动
pg_ctl -D /var/lib/pgsql/17/data start
# 或指定日志
pg_ctl -D /var/lib/pgsql/17/data -l /var/log/pgsql/server.log start

# 停止(优雅,等连接断开)
pg_ctl -D /var/lib/pgsql/17/data stop
# 默认等待 60s,超时发送 SIGINT,然后 SIGTERM

# 立即停止
pg_ctl -D /var/lib/pgsql/17/data stop -m fast   # 等当前查询完成(默认)
pg_ctl -D /var/lib/pgsql/17/data stop -m immediate  # 立即 abort

# 重启
pg_ctl -D /var/lib/pgsql/17/data restart

# 重载配置
pg_ctl -D /var/lib/pgsql/17/data reload

# 状态
pg_ctl -D /var/lib/pgsql/17/data status

# 查看版本
pg_ctl --version
```

**pg_ctl stop 三种模式**:

| 模式       | 行为                                       |
|------------|--------------------------------------------|
| `smart`    | 等所有连接断开(默认)                      |
| `fast`     | 断开所有连接,回滚未提交事务(推荐)        |
| `immediate`| 立即退出,未提交事务需启动时恢复           |

### 6.5 直接调用 postgres(调试模式)

```bash
# 前台启动,日志直接输出到终端
postgres -D /var/lib/pgsql/17/data

# 指定配置
postgres -D /var/lib/pgsql/17/data -c shared_buffers=2GB

# 单用户模式(故障恢复,无 socket 监听)
postgres --single -D /var/lib/pgsql/17/data postgres

# 检查配置合法性(不启动)
postgres -D /var/lib/pgsql/17/data --check
```

### 6.6 启动流程详解

```text
┌────────────────────────────────────────────────────────────┐
│                  PostgreSQL 启动流程                         │
│                                                            │
│  1. 读取 postgresql.conf + postgresql.auto.conf            │
│  2. 加载 pg_hba.conf、pg_ident.conf                        │
│  3. 分配 shared_buffers、启动后台进程                       │
│        (BG writer、checkpointer、walwriter、autovacuum等)   │
│  4. 恢复:回放 WAL(recovery.conf 旧版 / 16+ 在主配置)        │
│  5. 启动 walreceiver(若是备库)                            │
│  6. 监听 Unix socket(/var/run/postgresql/.s.PGSQL.5432)  │
│  7. 监听 TCP/IP(默认 localhost:5432)                      │
│  8. 创建 postmaster.pid 文件(独占)                          │
│  9. 接受客户端连接                                          │
└────────────────────────────────────────────────────────────┘
```

### 6.7 验证启动成功

```bash
# 1. 查看进程
ps -ef | grep postgres
# postgres  1234  ... /usr/pgsql-17/bin/postgres -D /var/lib/pgsql/17/data

# 2. 查看端口
ss -ltnp | grep 5432

# 3. pg_isready 检查
pg_isready -h localhost -p 5432
# localhost:5432 - accepting connections

# 4. 客户端验证
psql -U postgres -c "SELECT version(), now();"
```

```text
                                          version                                           |              now              
------------------------------------------------------------------------------------------+-------------------------------
 PostgreSQL 17.0 on x86_64-pc-linux-gnu, compiled by gcc ... | 2025-08-14 10:30:45.123456+08
```

### 6.8 启动失败排查清单

| 现象                                            | 排查方向                                           |
|-------------------------------------------------|----------------------------------------------------|
| `FATAL: data directory ... has wrong ownership` | `chown -R postgres:postgres /var/lib/pgsql/17/data` |
| `FATAL: could not open configuration file`      | 检查 `postgresql.conf` 路径与权限                  |
| `FATAL: could not create lock file`             | 删除残留的 `postmaster.pid`                        |
| `FATAL: could not bind socket`                  | 端口占用,`netstat -lnp | grep 5432`                |
| `FATAL: pre-existing shared memory block`       | 旧进程残留,kill 后清理 `pg_stat_tmp`               |
| `FATAL: WAL files not found`                    | 数据目录不完整或非 PG 初始化目录                    |

---

## 七、postgresql.conf 详解

`postgresql.conf` 是 PostgreSQL 的主配置文件,采用 **GUC(Grand Unified Configuration)** 框架,所有参数都可通过 `SET` 命令运行时调整。

### 7.1 配置文件加载顺序

```text
1. postgresql.conf(主配置文件)
2. postgresql.auto.conf(由 ALTER SYSTEM 写入,合并到主配置)
3. 命令行参数(c=config_name=value)
```

可使用 `pg_settings` 查看实际生效值:

```sql
SELECT name, setting, unit, source, sourcefile, sourceline
FROM pg_settings
WHERE name = 'shared_buffers';
```

### 7.2 参数类别

| 类别          | 修改方式                      | 示例                                |
|---------------|-------------------------------|-------------------------------------|
| **internal**  | 编译期固定,不可改              | `block_size`                         |
| **postmaster**| 需重启 postmaster(重启服务)  | `port`、`shared_buffers`、`wal_level` |
| **sighup**    | reload 即可                   | `listen_addresses`(有些)            |
| **superuser** | `SET` 即可                    | `log_min_duration_statement`         |
| **user`       | 会话内可改                     | `search_path`                        |

### 7.3 完整 postgresql.conf 示例

```ini
# ============================================================
# /var/lib/pgsql/17/data/postgresql.conf
# PostgreSQL 17 生产环境推荐配置
# ============================================================

# ==================== 连接与监听 ====================
listen_addresses = 'localhost,10.0.0.5'     # 监听 IP,'*' 表示全部
port              = 5432                    # 监听端口
max_connections    = 500                     # 最大并发连接
superuser_reserved_connections = 10          # 保留给 superuser 的连接
unix_socket_directories = '/var/run/postgresql,/tmp'   # Unix socket 目录
unix_socket_group  = ''                      # socket 文件所属组
tcp_keepalives_idle  = 60                    # TCP keepalive 空闲(秒)
tcp_keepalives_interval = 10                 # keepalive 探测间隔
tcp_user_timeout  = 0                        # TCP 用户超时
authentication_timeout = 60s                 # 认证超时
password_encryption = scram-sha-256          # 密码加密方式(推荐)

# ==================== 内存配置 ====================
shared_buffers      = 8GB                    # 共享缓冲(物理内存 25%)
                                       # PG 推荐 25%,MySQL 推荐 50-70%
huge_pages          = try                    # 尝试使用 huge pages
temp_buffers        = 32MB                   # 每个会话临时缓冲
max_prepared_transactions = 0                # 预处理事务上限
work_mem            = 64MB                   # 每个操作排序/哈希内存
                                       # 排序、哈希、bitmap heap
                                       # 注意:每个会话 × 每个操作都计费
maintenance_work_mem = 1GB                   # 维护操作内存(VACUUM、CREATE INDEX)
autovacuum_work_mem = 256MB                  # autovacuum 专用
max_stack_depth     = 2MB                    # 栈深度
dynamic_shared_memory_type = posix           # DSM 实现(sysv/posix/mmap)
shared_memory_type  = mmap                   # 共享内存实现(sysv/mmap)

# ==================== WAL 配置 ====================
wal_level           = replica                # WAL 级别:minimal/replica/logical
wal_buffers         = 64MB                   # WAL 缓冲(默认 -1,自动设为 shared_buffers 1/32)
wal_writer_delay    = 200ms                  # WAL writer 刷盘间隔
wal_compression     = on                     # 压缩 WAL(节省空间,小 CPU 开销)
wal_init_zero       = on                     # 初始化时 zero WAL
wal_recycle         = on                     # 重用 WAL 文件
wal_log_hints       = on                     # 写入 hint bit
wal_skip_threshold  = 2MB                    # 大于此值才 fsync
max_wal_size        = 16GB                   # 自动 checkpoint 触发上限
min_wal_size        = 1GB                    # 保留 WAL 下限

# ==================== Checkpoint ====================
checkpoint_timeout     = 15min               # checkpoint 最大间隔
checkpoint_completion_target = 0.9           # checkpoint 写入完成目标(0~1)
checkpoint_warning     = 30s                 # 写入超过此值告警
checkpoint_flush_after = 256                  # flush 后等待多少块

# ==================== 异步(autovacuum) ====================
autovacuum            = on                   # 启用 autovacuum
autovacuum_max_workers = 3                   # 后台 worker 数量
autovacuum_naptime    = 60s                  # 检查间隔
autovacuum_vacuum_threshold       = 50       # 触发 VACUUM 的死元组数
autovacuum_vacuum_insert_threshold = 1000    # 触发 VACUUM 的新增元组数
autovacuum_vacuum_scale_factor    = 0.1     # 触发比例(死元组/总元组)
autovacuum_analyze_threshold       = 50      # ANALYZE 触发
autovacuum_analyze_scale_factor    = 0.05
autovacuum_vacuum_cost_delay       = 10ms    # cost-based 节流延迟
autovacuum_vacuum_cost_limit       = 1000    # 节流上限
autovacuum_freeze_max_age         = 200000000
autovacuum_multixact_freeze_max_age = 400000000

# ==================== 日志配置 ====================
logging_collector    = on                    # 启用日志收集
log_destination      = 'stderr'              # 日志去向(stderr/ csvlog/ syslog/ eventlog)
log_directory        = 'log'                 # 日志目录(相对于 PGDATA)
log_filename         = 'postgresql-%Y-%m-%d_%H%M%S.log'   # 命名规则
log_file_mode        = 0640                  # 文件权限
log_rotation_age     = 1d                    # 轮转周期
log_rotation_size    = 100MB                 # 轮转大小
log_truncate_on_rotation = on                # 轮转时截断(覆盖同名)
log_min_messages     = warning               # 客户端消息级别
                                       # debug5/.../debug1/info/notice/warning/error/log/fatal/panic
log_min_error_statement = error              # 记录导致错误的语句
log_min_duration_statement = 500             # 慢查询阈值(毫秒),-1 禁用
log_checkpoints      = on                    # 记录 checkpoint
log_connections      = on                    # 记录连接
log_disconnections   = on                    # 记录断开
log_duration         = off                   # 记录每条 SQL 耗时(量大)
log_line_prefix      = '%m [%p] %q%u@%d from %h '   # 日志前缀格式
log_lock_waits       = on                    # 锁等待 > deadlock_timeout 记录
log_parameter_max_length = -1                # 记录参数最大长度
log_statement        = 'none'                # 记录语句: none/ddl/mod/all
log_replication_commands = on               # 记录复制命令
log_temp_files       = 0                     # 记录大于 N 字节的临时文件(0=全部)
log_timezone         = 'Asia/Shanghai'       # 日志时区

# ==================== 复制配置 ====================
wal_level            = replica               # 流复制需要 replica 或 logical
max_wal_senders      = 10                    # 最大 WAL sender 数
max_replication_slots = 10                   # 最大复制槽数
hot_standby          = on                    # 备库可读(11+ 默认 on)
wal_receiver_timeout = 60s                   # 备库接收超时
wal_retrieve_retry_interval = 5s             # 重试间隔
hot_standby_feedback = off                   # 备库反馈(开则主库 vacuum 可能延迟)
synchronous_commit   = on                    # 同步提交级别
synchronous_standby_names = ''                # 同步备库名(逗号分隔)
wal_sender_timeout   = 60s

# ==================== 查询规划 ====================
enable_bitmapscan   = on                     # bitmap 扫描
enable_hashagg      = on                     # hash 聚合
enable_hashjoin     = on                     # hash join
enable_indexscan    = on                     # 索引扫描
enable_indexonlyscan = on                    # index-only scan
enable_material     = on                     # 物化
enable_mergejoin    = on                     # merge join
enable_nestloop     = on                     # nested loop
enable_seqscan      = on                     # 顺序扫描
enable_parallel_append = on
enable_parallel_hash = on
enable_partition_pruning = on                # 分区裁剪
enable_partitionwise_aggregate = off
enable_partitionwise_join = off
max_parallel_workers_per_gather = 4          # 单个查询并行 worker
max_parallel_maintenance_workers = 4         # 维护并行
max_parallel_workers = 16                    # 全局并行 worker
random_page_cost    = 4                      # 随机页成本(SSD 建议 1.1)
effective_cache_size = 24GB                   # OS 缓存估算(物理内存 70%)

# ==================== 锁与超时 ====================
max_locks_per_transaction = 64               # 每事务锁数
max_pred_locks_per_transaction = 80          # 谓词锁数(SSI)
deadlock_timeout    = 1s                     # 死锁检测间隔
lock_timeout        = 0                      # 锁等待超时(0=无限)
statement_timeout   = 0                      # 语句超时(0=无限)
idle_in_transaction_session_timeout = 0      # 空闲事务超时
idle_session_timeout = 0                     # 空闲会话超时
vacuum_freeze_min_age = 50000000             # freeze 最小年龄
vacuum_freeze_table_age = 150000000

# ==================== 客户端连接默认值 ====================
timezone            = 'Asia/Shanghai'
client_encoding     = 'UTF8'
lc_messages         = 'en_US.UTF-8'          # 错误消息语言
lc_monetary         = 'en_US.UTF-8'
lc_numeric          = 'en_US.UTF-8'
lc_time             = 'en_US.UTF-8'
default_text_search_config = 'pg_catalog.simple'

# ==================== 统计信息 ====================
track_activities    = on                     # 跟踪活动会话
track_counts        = on                     # 跟踪统计计数
track_io_timing     = on                     # 跟踪 I/O 时延
track_functions     = none                   # 跟踪函数 PL
track_activity_query_size = 1024             # 显示 SQL 长度
update_process_title = on
stats_temp_directory = 'pg_stat_tmp'
```

### 7.4 关键参数详解

#### 7.4.1 连接参数

| 参数                          | 推荐值                          | 说明                                       |
|-------------------------------|--------------------------------|--------------------------------------------|
| `listen_addresses`            | `'localhost'` 或 `'*'`         | 默认仅 localhost;远程连接必须改            |
| `port`                        | 5432                            | PostgreSQL 默认端口                        |
| `max_connections`             | 100 ~ 500                       | 过大导致内存占用上升                       |
| `superuser_reserved_connections` | 3 ~ 10                       | 给超级用户预留(避免满连后无法管理)        |
| `authentication_timeout`      | 60s                             | 客户端认证超时                             |

#### 7.4.2 内存参数

| 参数                  | 推荐值                       | 说明                                              |
|-----------------------|-----------------------------|---------------------------------------------------|
| `shared_buffers`      | 物理内存 **25%**(8G ~ 32G)  | 数据缓存,**主要性能参数**                        |
| `work_mem`            | 64MB(默认 4MB 偏小)         | 排序、Hash Join、Bitmap Heap Scan **每次操作**    |
| `maintenance_work_mem`| 1GB(默认 64MB 偏小)         | VACUUM、CREATE INDEX、ALTER TABLE ADD FOREIGN KEY |
| `effective_cache_size`| 物理内存 **70%**             | 优化器估算,**不分配内存**,只是 hint             |
| `huge_pages`          | `try`                       | 大内存服务器可显著提升                           |

#### 7.4.3 WAL 与 Checkpoint

| 参数                       | 推荐值                | 说明                                              |
|----------------------------|----------------------|---------------------------------------------------|
| `wal_level`                | `replica` 或 `logical`| 流复制 / 逻辑复制                                 |
| `wal_buffers`              | 64MB(-1 自动)        | 默认值(`-1`)会自动设 shared_buffers 的 1/32      |
| `wal_compression`          | `on`                 | zstd 压缩,节省空间                                |
| `max_wal_size`             | 16GB ~ 64GB          | 触发 checkpoint 上限                              |
| `checkpoint_timeout`       | 15min ~ 30min        | checkpoint 最大间隔                               |
| `checkpoint_completion_target` | 0.9              | 平滑写入,降低 I/O 毛刺                           |

#### 7.4.4 autovacuum(必须启用)

| 参数                                  | 推荐值       | 说明                                            |
|---------------------------------------|-------------|-------------------------------------------------|
| `autovacuum`                          | `on`        | **必开**,否则事务 ID 回卷会导致停服            |
| `autovacuum_max_workers`              | 3 ~ 5       | 并行 worker 数                                  |
| `autovacuum_vacuum_scale_factor`      | 0.1         | 触发 VACUUM 的死元组比例(默认 0.2 偏大)        |
| `autovacuum_analyze_scale_factor`     | 0.05        | 触发 ANALYZE 比例                               |
| `autovacuum_vacuum_cost_limit`        | 1000        | cost-based 节流上限                             |

### 7.5 动态修改

```sql
-- 1. 会话级
SET work_mem = '128MB';

-- 2. 事务级
SET LOCAL statement_timeout = '10s';

-- 3. 全局级(当前生效)
SET shared_buffers = '8GB';   -- 报错:postmaster 级需 reload 或 restart

-- 4. ALTER SYSTEM 持久化(写入 postgresql.auto.conf)
ALTER SYSTEM SET log_min_duration_statement = '1s';
SELECT pg_reload_conf();

-- 5. 在函数内 SET(参数化)
ALTER FUNCTION foo() SET work_mem = '256MB';
```

### 7.6 配置错误排查

```bash
# 启动时如配置错误
postgres -D /data/pgsql --check   # 检查配置

# 通过日志查看生效值
psql -c "SELECT name, setting, source FROM pg_settings WHERE source NOT IN ('default', 'client');"
```

---

## 八、pg_hba.conf 主机认证详解

**pg_hba.conf**(Host-Based Authentication) 控制 **谁能连接到哪个数据库、用什么认证方式**。每条记录格式如下:

```text
TYPE    DATABASE    USER        ADDRESS          METHOD    [OPTIONS]
```

### 8.1 字段说明

| 字段       | 取值                                                                          |
|------------|-------------------------------------------------------------------------------|
| `TYPE`     | `local`(Unix socket)、`host`(TCP,SSL 或非 SSL)、`hostssl`、`hostnossl`        |
| `DATABASE` | `all`、数据库名、多个逗号分隔、`sameuser`、`samerole`、`replication`            |
| `USER`     | `all`、用户名、多个逗号分隔、`+group_name`(角色组)                            |
| `ADDRESS`  | CIDR(192.168.1.0/24)、IP(192.168.1.10)、`samehost`、`all`                    |
| `METHOD`   | 认证方式(见下表)                                                             |
| `OPTIONS`  | 附加参数,如 `clientcert=1`                                                    |

### 8.2 认证方式

| METHOD              | 说明                                                | 安全性     |
|---------------------|-----------------------------------------------------|------------|
| `trust`             | 无条件允许(**仅本机调试用**)                       | ★          |
| `reject`            | 无条件拒绝                                          | -          |
| `scram-sha-256`     | SCRAM-SHA-256 挑战-响应(**PG 10+ 推荐**)            | ★★★★★     |
| `md5`               | MD5 哈希(老方法,仍可用但不再推荐)                  | ★★★        |
| `password`          | 明文密码发送(**极不安全**)                          | ★          |
| `peer`              | OS 用户名必须与 PG 用户名一致(Unix socket)         | ★★★★      |
| `ident`             | 通过 ident 协议获取 OS 用户(TCP)                   | ★★        |
| `cert`              | SSL 客户端证书                                      | ★★★★★     |
| `ldap`              | LDAP 认证(需编译支持)                              | ★★★★      |
| `radius`            | RADIUS 认证                                         | ★★★★      |
| `pam`               | PAM 认证(需编译支持)                                | ★★★★      |
| `gss` / `sspi`      | GSSAPI / Kerberos                                   | ★★★★★     |

### 8.3 完整 pg_hba.conf 示例

```ini
# ============================================================
# /var/lib/pgsql/17/data/pg_hba.conf
# PostgreSQL 主机认证配置示例
# ============================================================

# TYPE  DATABASE        USER            ADDRESS                 METHOD

# === 本机 Unix socket:peer(OS 用户 = PG 用户) ===
#  postgres OS 用户用任何 PG 用户名连接任何数据库
local   all             postgres                                peer
#  其他 OS 用户只能连同名 PG 用户
local   all             all                                     peer

# === 本机 TCP:trust(仅调试用,生产禁止) ===
#  host    all             all             127.0.0.1/32            trust

# === 局域网应用段:SCRAM-SHA-256 ===
host    all             all             10.0.0.0/24             scram-sha-256

# === 特定应用账号:只允许 appdb 库 ===
host    appdb           appuser         10.0.0.0/24             scram-sha-256

# === 远程管理:DBA 段:scram-sha-256 ===
host    all             dba_admin       192.168.1.0/24          scram-sha-256

# === 复制账号(用于流复制) ===
host    replication     replicator      10.0.0.5/32             scram-sha-256

# === SSL 强制:cert 客户端证书 ===
hostssl all             all             10.0.0.0/24             cert clientcert=1

# === 拒绝其他所有连接 ===
host    all             all             0.0.0.0/0               reject
```

### 8.4 认证方式详解示例

#### 8.4.1 trust(无条件允许)

```ini
# 本机调试,无需密码
local   all             all                                     trust
```

> **风险**:任何能登入 OS 的用户都能连 PG,**仅用于调试或容器测试**。

#### 8.4.2 md5 / scram-sha-256

```ini
host    all             all             10.0.0.0/24             scram-sha-256
```

```sql
-- 创建用户(密码自动以 scram-sha-256 加密存储)
CREATE USER appuser WITH PASSWORD 'AppPass123!';
```

**scram-sha-256 vs md5**:

| 维度       | scram-sha-256              | md5                       |
|------------|-----------------------------|---------------------------|
| 存储       | 加盐、迭代 PBKDF2           | 加盐 md5                  |
| 传输       | 挑战-响应                  | challenge-response        |
| 离线破解   | 极难                        | 较难                      |
| 推荐       | **强烈推荐**(PG 10+ 默认)  | 兼容老客户端              |

#### 8.4.3 peer(OS 用户 = PG 用户)

```ini
local   all             all                                     peer
```

```bash
# OS 用户 postgres 可直连(无需密码)
sudo -u postgres psql

# 其他 OS 用户用同名 PG 用户
sudo -u appuser psql -d appdb
# 必须存在 appuser PG 角色
```

#### 8.4.4 ident(通过 ident 服务器)

```ini
host    all             all             192.168.1.0/24          ident map=omicron
```

`pg_ident.conf` 映射 OS 用户到 PG 用户:

```ini
# /var/lib/pgsql/17/data/pg_ident.conf
# MAPNAME    SYSTEM-USERNAME    PG-USERNAME
omicron      appuser            appuser
omicron      deploy             app_admin
```

#### 8.4.5 cert(SSL 客户端证书)

```ini
hostssl all             all             10.0.0.0/24             cert
```

需要在 `postgresql.conf` 中:

```ini
ssl = on
ssl_cert_file = 'server.crt'
ssl_key_file = 'server.key'
ssl_ca_file = 'ca.crt'
```

客户端需提供证书,并将 `username` 映射到 CN:

```bash
psql "host=db.example.com dbname=appdb user=appuser sslcert=client.crt sslkey=client.key sslrootcert=ca.crt"
```

### 8.5 修改 pg_hba.conf 后

```bash
# 必须 reload(无需重启)
pg_ctl reload
# 或
sudo systemctl reload postgresql
```

### 8.6 pg_hba.conf 调试技巧

```sql
-- 查看当前生效的认证规则
SELECT * FROM pg_hba_file_rules;

-- 查看当前连接
SELECT pid, usename, client_addr, application_name, state
FROM pg_stat_activity;
```

---

## 九、psql 客户端详解

`psql` 是 PostgreSQL 自带的 **命令行交互客户端**,功能强大,几乎所有管理任务都能完成。

### 9.1 基本连接

```bash
# 最简(本机,Unix socket,当前 OS 用户)
psql

# 指定用户名
psql -U postgres

# 指定主机与端口
psql -h 127.0.0.1 -p 5432 -U postgres -d appdb

# 一次性执行
psql -U postgres -c "SELECT version();"

# 执行 SQL 文件
psql -U postgres -f script.sql

# 进入数据库后切换
\c appdb
```

### 9.2 常用选项

| 选项                    | 说明                                       |
|-------------------------|--------------------------------------------|
| `-h / --host`           | 主机名                                     |
| `-p / --port`           | 端口                                       |
| `-U / --username`       | 用户名                                     |
| `-d / --dbname`         | 数据库名                                   |
| `-w`                    | 不提示密码(常用于脚本)                     |
| `-W`                    | 强制提示密码                               |
| `-f file`               | 执行 SQL 文件                              |
| `-c "SQL"`              | 执行单条 SQL                               |
| `-e`                    | 回显执行的 SQL                             |
| `-a`                    | 回显所有输入(含 `\set` 等元命令)           |
| `-q`                    | 安静模式                                   |
| `-v name=value`         | 传入变量,SQL 中用 `:name` 引用            |
| `-1` / `--single-transaction` | 整个文件包在一个事务       |
| `--pset`                | 临时改输出格式                             |
| `-t` / `--tuples-only`  | 仅显示数据                                 |
| `-A`                    | 不对齐(适合导出)                          |
| `-F`                    | 字段分隔符(配合导出)                       |

### 9.3 内部命令(元命令)

#### 9.3.1 帮助与基本信息

| 命令                | 作用                              |
|---------------------|-----------------------------------|
| `\?`                | 元命令帮助                        |
| `\h [command]`      | SQL 帮助(`\h SELECT`)             |
| `\g`                | 执行缓冲区中的 SQL                |
| `\q`                | 退出                              |
| `\password [user]`  | 修改密码                          |
| `\conninfo`         | 显示当前连接信息                  |

#### 9.3.2 数据库与连接

| 命令                       | 作用                              |
|----------------------------|-----------------------------------|
| `\l[+]`                    | 列出所有数据库(`+` 显示大小)      |
| `\c [dbname [username]]`   | 切换数据库/用户                   |
| `\dn[+] [pattern]`         | 列出模式(schema)                  |
| `\du[+] [pattern]`         | 列出角色/用户                     |
| `\dg[+] [pattern]`         | 同 `\du`(groups)                  |
| `\db[+] [pattern]`         | 列出表空间                        |
| `\dx[+] [pattern]`         | 列出已安装扩展                    |

#### 9.3.3 表与视图

| 命令                       | 作用                              |
|----------------------------|-----------------------------------|
| `\dt[+] [pattern]`         | 列出表                            |
| `\dv[+] [pattern]`         | 列出视图                          |
| `\dm[+] [pattern]`         | 列出物化视图                      |
| `\di[+] [pattern]`         | 列出索引                          |
| `\ds[+] [pattern]`         | 列出序列                          |
| `\d [pattern]`             | 描述对象(表、视图、索引、函数等) |
| `\d+ [pattern]`            | 详细描述(含注释等)               |
| `\d tablename`             | 查看表结构                        |
| `\d+ tablename`            | 查看表详细结构                    |
| `\dp [pattern]`            | 列出权限(同 `\z`)                 |
| `\dd [pattern]`            | 列出对象注释                      |
| `\dT[+] [pattern]`         | 列出数据类型                      |
| `\det[+] [pattern]`        | 列出外部表                        |
| `\des[+] [pattern]`        | 列出外部服务器                    |

#### 9.3.4 函数与过程

| 命令                       | 作用                              |
|----------------------------|-----------------------------------|
| `\df[+] [pattern]`         | 列出函数                          |
| `\df+ [pattern]`           | 列出函数(含定义)                 |
| `\sf function_name`        | 显示函数定义                      |
| `\do[+] [pattern]`         | 列出运算符                        |
| `\dRp[+] [pattern]`        | 列出复制发布                      |
| `\dRs[+] [pattern]`        | 列出复制订阅                      |

#### 9.3.5 输出格式

| 命令                       | 作用                              |
|----------------------------|-----------------------------------|
| `\pset format [unaligned]` | 切换输出格式(aligned/unaligned/html...) |
| `\pset null 'NULL'`        | 设置 NULL 显示                    |
| `\pset border 2`           | 边框样式(0/1/2)                  |
| `\pset pager on/off`       | 分页器开关                        |
| `\x`                       | 扩展显示(每行字段独立行)        |
| `\a`                       | 对齐/不对齐切换                   |
| `\t`                       | 仅显示元组/完整                   |
| `\H`                       | 切换 HTML 输出                    |

#### 9.3.6 输入/输出与脚本

| 命令                       | 作用                              |
|----------------------------|-----------------------------------|
| `\i filename`              | 执行文件                          |
| `\o filename`              | 输出重定向到文件                  |
| `\copy ...`                | 客户端 COPY(读写文件)            |
| `\echo text`               | 输出文本                          |
| `\set name value`          | 设置变量                          |
| `\unset name`              | 删除变量                          |
| `\timing`                  | 显示 SQL 执行时间                 |
| `\watch [sec]`             | 周期性重执行(监控用)            |
| `\! command`               | 执行 shell 命令                   |

### 9.4 实用示例

#### 9.4.1 查看表结构

```sql
-- 列出所有表
\dt

-- 列出 public 模式下所有表
\dt public.*

-- 详细列出(含大小)
\dt+

-- 查看单表结构
\d users
\d+ users

-- 输出
                          Table "public.users"
   Column   |          Type          | Collation | Nullable | Default 
------------+------------------------+-----------+----------+---------
 id         | bigint                 |           | not null | 
 username   | character varying(50)  |           | not null | 
 email      | character varying(100) |           |          | 
 created_at | timestamp with time zone |        |          | now()
Indexes:
    "users_pkey" PRIMARY KEY, btree (id)
    "users_username_key" UNIQUE CONSTRAINT, btree (username)
Check constraints:
    "users_email_check" CHECK (email ~~ '%@%'::text)
```

#### 9.4.2 切换显示格式

```sql
-- 扩展显示(每行一个字段)
\x
-- Expanded display is on.

SELECT * FROM users LIMIT 1;
-- [ RECORD 1 ]
-- id        | 1
-- username  | alice
-- email     | alice@example.com
-- created_at | 2025-08-14 10:00:00+08

-- 关闭扩展
\x
```

#### 9.4.3 导出数据(三种方式)

**方式 1:`\copy` 客户端命令**(推荐,无需 superuser):

```sql
-- 导出到 CSV
\copy (SELECT * FROM users WHERE created_at > '2025-01-01') TO '/tmp/users.csv' WITH CSV HEADER

-- 导入 CSV
\copy users(username, email) FROM '/tmp/users.csv' WITH CSV HEADER
```

**方式 2:`COPY` 服务端命令**(需 superuser):

```sql
COPY users TO '/tmp/users.csv' WITH CSV HEADER;
COPY users FROM '/tmp/users.csv' WITH CSV HEADER;
```

**方式 3:`pg_dump` 导出**(完整备份):

```bash
pg_dump -U postgres -t users appdb -f users.sql
```

#### 9.4.4 `\watch` 实时监控

```sql
-- 每 2 秒刷新
\watch 2
SELECT pid, usename, state, query_start, query
FROM pg_stat_activity
WHERE state != 'idle';
```

#### 9.4.5 `\timing` 看执行时间

```sql
\timing
Timing is on.

SELECT COUNT(*) FROM pg_class;
--  count 
-- -------
--   1245
-- (1 row)
-- Time: 12.456 ms
```

#### 9.4.6 `\set` 设置变量与 SQL 引用

```sql
\set user 'alice'
SELECT * FROM users WHERE username = :'user';

-- 也可以参数化
\set id 42
SELECT * FROM users WHERE id = :id;
```

#### 9.4.7 `\sf` 看函数定义

```sql
\sf add
-- CREATE OR REPLACE FUNCTION public.add(integer, integer)
--  RETURNS integer
--  LANGUAGE plpgsql
--  IMMUTABLE
-- AS $function$
-- BEGIN
--   RETURN $1 + $2;
-- END;
-- $function$
```

### 9.5 psql 配置文件 `.psqlrc`

```bash
# ~/.psqlrc
\set QUIET on
\pset null '¤'
\pset border 2
\pset linestyle unicode
\pset format aligned
\set ON_ERROR_ROLLBACK interactive
\set COMP_KEYWORD_CASE upper
\set HISTFILE ~/.psql_history- :DBNAME
\set HISTSIZE 5000
\encoding utf8
\x auto
\timing on

-- 自定义快捷查询
\set show_slow_queries 'SELECT pid, now() - query_start AS duration, query FROM pg_stat_activity WHERE state != \'idle\' ORDER BY duration DESC;'
```

```sql
-- 使用
:show_slow_queries
```

### 9.6 常见错误排查

| 错误                                              | 原因                                  |
|---------------------------------------------------|---------------------------------------|
| `psql: error: connection to server on socket ... failed: No such file or directory` | socket 路径错,检查 `unix_socket_directories` |
| `FATAL: Peer authentication failed for user ...` | `peer` 认证失败,OS 用户与 PG 用户不一致 |
| `FATAL: password authentication failed for user` | 密码错或 `pg_hba.conf` 不允许         |
| `FATAL: database "xxx" does not exist`             | 数据库名错                            |

---

## 十、PostgreSQL 客户端工具

### 10.1 GUI 客户端对比

| 工具       | 平台           | 开源 | 特点                                                       |
|------------|----------------|------|------------------------------------------------------------|
| **pgAdmin**| Win/Mac/Linux  | 是   | PostgreSQL 官方 GUI,**功能最全**(监控、备份、调试)        |
| **DBeaver**| Win/Mac/Linux  | 是   | 通用数据库客户端(支持 PG/MySQL/Oracle/...),**生态最广**   |
| **Navicat**| Win/Mac/Linux  | 否   | 商业,**颜值与易用性最佳**,支持 PG/MySQL/MongoDB 等       |
| **DataGrip**| Win/Mac/Linux | 否   | JetBrains 出品,智能补全、SQL 解析强,适合 Java 开发者      |
| **TablePlus**| Mac/Win      | 否   | 现代化 UI,Mac 体验极佳                                    |
| **Beekeeper Studio**| Win/Mac/Linux | 是 | 轻量、跨平台、Tabs + 暗色                            |

### 10.2 pgAdmin 4(官方推荐)

#### 10.2.1 安装

```bash
# Debian/Ubuntu
sudo apt install pgadmin4

# RHEL
sudo dnf install pgadmin4

# 或独立运行(pip)
pip install pgadmin4
pgadmin4
```

#### 10.2.2 主要功能

- 服务器连接管理
- 数据库/模式/表树形浏览
- SQL 编辑器(自动补全、语法高亮)
- ER 图生成
- 查询计划可视化
- 备份/恢复(`pg_dump` 包装)
- 监控仪表盘(I/O、锁、统计)
- 用户/角色管理

### 10.3 DBeaver(社区版免费)

#### 10.3.1 安装

```bash
# macOS
brew install --cask dbeaver-community

# Windows:从官网下载 .exe
# Linux:AppImage 或 .deb
```

#### 10.3.2 优势

- 支持所有主流数据库(切换数据库零成本)
- 强大的 ER 图、数据传输(异构)
- SSH 隧道、SSL 配置简单
- 活跃的社区版(开源)
- 丰富的可视化(图表、地理空间)

### 10.4 Navicat(商业)

#### 10.4.1 特点

- 颜值高、交互流畅
- 数据模型设计(逻辑 → 物理)
- 计划任务(定时备份)
- 数据同步、结构同步
- 表设计器、视图设计器

#### 10.4.2 价格

> 个人版约 $300,商业版约 $700(永久授权)。

### 10.5 选择建议

| 场景                     | 推荐                     |
|--------------------------|--------------------------|
| DBA 日常管理              | pgAdmin 4               |
| 跨数据库管理              | DBeaver                  |
| Mac 颜值党 + 偶尔用      | TablePlus / Navicat      |
| 写复杂 SQL / Java 开发者 | DataGrip                 |
| 团队协作 + 监控仪表盘    | pgAdmin 4 + 自建监控     |

---

## 十一、系统数据库

PostgreSQL 安装后默认有三个 **系统数据库**(template 数据库 + postgres):

```text
postgres       当前连接库,默认管理库
template1      默认模板(可定制)
template0      纯净模板(不可修改,用于恢复)
```

### 11.1 三个系统库的作用

| 库名          | OID  | 作用                                                            |
|---------------|------|-----------------------------------------------------------------|
| `postgres`    | 5    | 默认管理库,用户连接用的就是它                                |
| `template1`  | 4    | 默认模板,**可修改**(如装扩展),`CREATE DATABASE` 复制此库      |
| `template0`  | 1    | 纯净模板,**不可修改**,用于创建与 template1 字符集不同的库     |

### 11.2 模板机制

```sql
-- 默认从 template1 复制
CREATE DATABASE appdb;

-- 从 template0 复制(用于字符集不同的库)
CREATE DATABASE appdb_zh LC_COLLATE = 'zh_CN.UTF-8' TEMPLATE = template0;

-- 自定义 template(常用技巧:给 template1 装所有需要的扩展)
\c template1
CREATE EXTENSION pg_trgm;
CREATE EXTENSION btree_gin;
-- 之后所有 CREATE DATABASE 都会自动包含这些扩展
```

### 11.3 查看系统库

```sql
-- 列出所有数据库(看 oid 与属主)
SELECT oid, datname, datdba, daticulocale, datcollate, datctype, datistemplate, datallowconn
FROM pg_database;

-- 输出
--  oid  |   datname   | datdba | datistemplate | datallowconn
-- ------+-------------+--------+---------------+--------------
--     1 | template0   |     10 | t             | f
--     4 | template1   |     10 | t             | t
--     5 | postgres    |     10 | f             | t
```

### 11.4 不要删除系统库

```sql
-- 严禁
DROP DATABASE postgres;
DROP DATABASE template0;   -- 报错:不允许
DROP DATABASE template1;   -- 报错:有依赖
```

### 11.5 备份模板库

```bash
# template1 的修改是危险的,修改前先备份
pg_dump -U postgres -d template1 -f template1.backup.sql
```

---

## 十二、升级与迁移

### 12.1 升级方式

| 方式              | 适用场景                          | 风险 | 停机     |
|-------------------|-----------------------------------|------|----------|
| **pg_upgrade**    | 同一主机、跨大版本(16→17)       | 中   | 几分钟   |
| **逻辑备份恢复**  | 跨主机、跨版本、跨平台           | 低   | 较长     |
| **逻辑复制**      | 跨大版本在线迁移(15→17)         | 中   | 秒级切换 |
| **pg_dump/restore**| 小库,跨版本简单迁移            | 低   | 视库大小 |

### 12.2 pg_upgrade(同主机推荐)

#### 12.2.1 升级前检查

```bash
# 1. 备份(必须!)
pg_dumpall -U postgres -f all.sql

# 2. 检查升级兼容性
/usr/pgsql-17/bin/pg_upgrade --check \
    --old-datadir=/var/lib/pgsql/16/data \
    --new-datadir=/var/lib/pgsql/17/data \
    --old-bindir=/usr/pgsql-16/bin \
    --new-bindir=/usr/pgsql-17/bin
```

#### 12.2.2 升级步骤

```bash
# 1. 安装新版本(并存)
sudo dnf install postgresql17-server postgresql17-contrib

# 2. 初始化新版本数据目录
sudo /usr/pgsql-17/bin/postgresql-17-setup initdb
# (默认在 /var/lib/pgsql/17/data)

# 3. 停止旧版本
sudo systemctl stop postgresql-16

# 4. 执行升级(原地保留旧数据)
sudo -u postgres /usr/pgsql-17/bin/pg_upgrade \
    --old-datadir=/var/lib/pgsql/16/data \
    --new-datadir=/var/lib/pgsql/17/data \
    --old-bindir=/usr/pgsql-16/bin \
    --new-bindir=/usr/pgsql-17/bin \
    --link    # 硬链接(快,不占空间),不用 --link 则是拷贝(慢)
```

> **重要**:`--link` 模式仅创建硬链接,**升级后旧数据目录不能再用**,如升级失败需保留旧目录,慎用。

#### 12.2.3 升级后

```bash
# 5. 启动新版本
sudo systemctl start postgresql-17

# 6. 运行 analyze_new_cluster.sh
sudo -u postgres ./analyze_new_cluster.sh

# 7. 验证
psql -U postgres -c "SELECT version();"

# 8. 删除旧版本(确认无误后)
sudo dnf remove postgresql16-server
```

### 12.3 逻辑备份迁移(跨主机跨版本)

```bash
# === 源库(老版本) ===
pg_dumpall -U postgres -f all.sql

# === 目标库(新版本) ===
# 1. 初始化
initdb -D /var/lib/pgsql/17/data

# 2. 启动
pg_ctl -D /var/lib/pgsql/17/data -l logfile start

# 3. 恢复
psql -U postgres -f all.sql postgres
```

**单库迁移**:

```bash
# 导出
pg_dump -U postgres -d appdb -Fc -f appdb.dump
# -Fc 自定义格式(支持并行恢复)

# 导入
pg_restore -U postgres -d appdb -j 4 appdb.dump
# -j 4:并行恢复
```

### 12.4 逻辑复制在线迁移(最小停机)

```text
源库 15   ───→  目标库 17
        逻辑复制(logical replication)
        持续同步
        ↓
   短暂停服(秒级)
        ↓
   提升 17 为主库
        ↓
   业务切换连接
```

```sql
-- === 源库 ===
CREATE PUBLICATION pub_migration FOR ALL TABLES;

-- === 目标库 ===
CREATE SUBSCRIPTION sub_migration
CONNECTION 'host=src-db port=5432 user=replicator password=xxx dbname=appdb'
PUBLICATION pub_migration;

-- 同步完成后,源库停服,目标库提升
-- ALTER SUBSCRIPTION sub_migration DISABLE;
-- 业务切换连接
```

### 12.5 升级注意事项清单

| 注意项                                       | 说明                                       |
|----------------------------------------------|--------------------------------------------|
| **必先备份**                                 | 任何升级前 `pg_dumpall` 或 `pg_basebackup` |
| **检查扩展兼容性**                           | 某些扩展需重新编译                          |
| **测试自定义类型、函数**                     | PL/pgSQL 语法可能微调                       |
| **关注 release notes 中的 UPGRADE 章节**     | 官方文档会列出每个版本的破坏性变更         |
| **保留旧版本数据目录**                       | 升级失败可回滚                              |
| **先小版本升级到大版本的最后一个 release**   | 例如 16.0 → 16.x → 17                       |
| **运行 analyze_new_cluster.sh**              | pg_upgrade 后建议全表 ANALYZE              |

---

## 十三、卸载 PostgreSQL

### 13.1 包管理器安装的卸载

```bash
# === Debian/Ubuntu ===
sudo systemctl stop postgresql
sudo apt remove postgresql-17 postgresql-client-17
sudo apt autoremove
sudo apt purge postgresql-17
sudo rm -rf /etc/postgresql/17
sudo rm -rf /var/lib/postgresql/17
sudo userdel -r postgres

# === RHEL/CentOS ===
sudo systemctl stop postgresql-17
sudo dnf remove postgresql17-server postgresql17-contrib postgresql17
sudo rm -rf /var/lib/pgsql/17
sudo rm -rf /usr/pgsql-17
sudo userdel -r postgres
```

### 13.2 源码编译的卸载

```bash
# 停服
pg_ctl -D /var/lib/pgsql/17/data stop

# 删除安装目录
sudo rm -rf /usr/local/pgsql

# 删除数据目录(谨慎!)
sudo rm -rf /var/lib/pgsql/17

# 删除用户
sudo userdel -r postgres

# 清理 PATH
sed -i '/pgsql/d' /etc/profile
```

### 13.3 Docker 卸载

```bash
# 停掉并删除容器
docker stop pg17
docker rm pg17

# 删除镜像
docker rmi postgres:17

# 删除卷(可选,清数据)
docker volume ls | grep pg
docker volume rm project_pg_data
```

### 13.4 验证已彻底卸载

```bash
# 验证命令不存在
which postgres
which psql
which pg_ctl

# 验证没有进程
pgrep -af postgres

# 验证没有服务
systemctl list-unit-files | grep -i postgres

# 验证没有端口
ss -ltnp | grep 5432
```

```text
(无输出,即为彻底卸载)
```

---

## 十四、核心要点速记

- **PostgreSQL 是 Stonebraker 的 Ingres 精神继承者**,起源于 UC Berkeley,采用 BSD 协议(完全自由)
- **官方仓库每年一个大版本**(PG 16/17 是当前生产推荐),每个版本支持 5 年
- **核心定位**:**OLTP + OLAP 兼顾**,复杂查询与标准 SQL 遵从度业内第一
- **关键特性**:MVCC(写不阻塞读)、JSONB(可索引的二进制 JSON)、CTE/窗口函数/物化视图、`CREATE EXTENSION` 扩展生态(PostGIS、pgvector)
- **JSONB vs JSON**:JSONB 解析后存储、支持 GIN 索引、查询快;JSON 是文本、不索引
- **5 种安装方式**:**包管理器**(生产推荐)、**Docker**(开发推荐)、**源码**(深度定制)、**图形化**(Windows)、**发行版自带**(不推荐)
- **目录结构三类**:`prefix`(程序)、`PGDATA`(数据)、`config`(配置)
- **PGDATA 核心目录**:`base/`(数据)、`global/`(用户/角色)、`pg_wal/`(WAL 日志)、`pg_xact/`(事务状态)、`pg_stat/`(统计)、`pg_logical/`(逻辑复制)
- **配置文件**:`postgresql.conf`(主配置)、`postgresql.auto.conf`(ALTER SYSTEM 写入)、`pg_hba.conf`(认证)
- **启动方式**:`systemctl`(主流)、`pg_ctl`(跨平台推荐)、直接 `postgres`(调试)
- **`pg_ctl stop` 三种模式**:`smart`(默认,等连接)、`fast`(推荐)、`immediate`(立即)
- **`shared_buffers` 推荐物理内存 25%**(`effective_cache_size` 70%),与 MySQL 不同
- **`work_mem` 是每次操作**而非全局,大查询可能多次分配
- **`wal_level` 三档**:`minimal`(无复制)、`replica`(流复制)、`logical`(逻辑复制)
- **`autovacuum` 必开**,否则事务 ID 回卷导致停服
- **`pg_hba.conf` 五大认证**:`peer`(本机 socket 推荐)、`scram-sha-256`(TCP 远程推荐)、`md5`(老方法)、`cert`(SSL 证书)、`trust`(仅调试)
- **psql 核心元命令**:`\dt`(表)、`\d`(描述)、`\df`(函数)、`\dn`(模式)、`\du`(用户)、`\dx`(扩展)、`\copy`(导入导出)、`\x`(扩展显示)、`\timing`(计时)
- **`\copy` vs `COPY`**:`\copy` 走客户端(无需 superuser)、`COPY` 服务端(需 superuser)
- **三个系统库**:`postgres`(管理库)、`template1`(可改模板)、`template0`(纯净模板)
- **升级方式**:`pg_upgrade`(同主机快速)、`pg_dumpall`/`pg_restore`(跨主机跨版本)、`逻辑复制`(在线迁移)
- **逻辑复制在线迁移**:`CREATE PUBLICATION` + `CREATE SUBSCRIPTION` + 切换连接(秒级停机)
- **GUI 客户端**:**pgAdmin 4**(官方)、**DBeaver**(跨数据库)、**Navicat**(颜值党)、**DataGrip**(Java 开发者)
- **坑点提示**:`listen_addresses` 默认仅 localhost、远程连接必改;`work_mem` 是每次操作;`autovacuum` 关掉必出大事;`max_connections` 过大导致内存暴增;PG 12+ `recovery.conf` 已并入主配置