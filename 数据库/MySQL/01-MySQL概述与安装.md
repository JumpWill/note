# MySQL 概述与安装

## 一、MySQL 简介

### 1.1 什么是 MySQL

**MySQL** 是当前最流行的开源关系型数据库管理系统(RDBMS)之一,采用 **客户端/服务器 (C/S)** 架构,使用 **SQL(Structured Query Language)** 作为数据访问语言。

**核心定位**:

- 属于 **OLTP(Online Transaction Processing)** 型数据库
- 底层存储引擎默认采用 **InnoDB**(自 5.5.5 版本起)
- 由瑞典 MySQL AB 公司开发,后被 Sun、Oracle 相继收购
- 遵循 **GPL v2** 协议(社区版),提供商业版和企业版

### 1.2 发展历史

```text
┌──────────────────────────────────────────────────────────┐
│ 1994   Michael Widenius (Monty) 与 David Axmark 创立     │
│        MySQL,最初为内部工具                              │
│   ↓                                                       │
│ 1995   第一版发布,面向 Web 开发                           │
│   ↓                                                       │
│ 2000   转为 GPL 开源,采用双授权模式                       │
│   ↓                                                       │
│ 2008   Sun Microsystems 以 10 亿美元收购 MySQL AB         │
│   ↓                                                       │
│ 2010   Oracle 收购 Sun,MySQL 归入 Oracle                 │
│   ↓                                                       │
│ 2010   Monty 创立 MariaDB 分支,对抗 Oracle 闭源倾向      │
│   ↓                                                       │
│ 2013   Percona Server 分支成熟,聚焦性能与监控            │
│   ↓                                                       │
│ 2018   MySQL 8.0 GA,跳级大版本(直追 PostgreSQL)         │
│   ↓                                                       │
│ 2023   MySQL 8.0.x LTS(长期支持),MySQL 8.4 LTS           │
│   ↓                                                       │
│ 2024+  MySQL 9.x 出现,持续迭代                          │
└──────────────────────────────────────────────────────────┘
```

### 1.3 版本演进

| 版本   | 发布时间 | 主要特性                                                    | 状态               |
|--------|----------|-------------------------------------------------------------|--------------------|
| 3.x    | 1996-2000 | 早期版本,多种引擎(MYISAM)                                | 已淘汰             |
| 4.0    | 2003     | InnoDB 成为可选,Unicode 支持,查询缓存                      | 已淘汰             |
| 4.1    | 2004     | 子查询、视图、UTF-8                                        | 已淘汰             |
| 5.0    | 2005     | 存储过程、游标、触发器、视图                                | 历史版本           |
| 5.1    | 2008     | 事件调度器、分区表、行级复制插件                            | 历史版本           |
| 5.5    | 2010     | **默认 InnoDB**,半同步复制                                  | EOL                |
| 5.6    | 2013     | GTID、多线程复制、Online DDL                                | EOL                |
| 5.7    | 2015     | JSON、原生 Generated Column、组复制                        | 仍广泛使用         |
| 8.0    | 2018     | **跳级大版本**:窗口函数、CTE、MGR、原子 DDL、降序索引    | 主线版本           |
| 8.4    | 2024     | LTS 长期支持版本(8.x LTS 模型切换)                          | 推荐生产           |
| 9.x    | 2024+    | JavaScript 程序化、新一代架构探索                           | 实验性             |

> **LTS 模型**:MySQL 自 8.4 起,部分版本标记为 LTS(长期支持,Premier/Extended 支持 8 年),其余为 Innovation 版本(只支持到下一 Innovation)。

### 1.4 三大主流分支

| 分支            | 维护方                | 兼容性        | 特色                                                                  |
|-----------------|-----------------------|---------------|-----------------------------------------------------------------------|
| **MySQL**       | Oracle                | 标准 MySQL    | 官方版本,生态最广                                                    |
| **MariaDB**     | MariaDB Foundation    | 高度兼容      | 蒙蒂主导,引入更多新特性(Galera、Aria、Spider),GPL 不变              |
| **Percona Server** | Percona             | 完全兼容      | 强化 InnoDB(XtraDB)、Percona Toolkit 工具集、性能监控更好             |

> 生产环境推荐 **MySQL 8.0 LTS** 或 **MySQL 8.4 LTS**;如需更多性能增强可考虑 Percona Server for MySQL。

### 1.5 MySQL 的特点

| 维度     | 说明                                                                            |
|----------|---------------------------------------------------------------------------------|
| 跨平台   | 支持 Linux、Windows、macOS、FreeBSD、Solaris 等                                |
| 多线程   | 多个连接共用进程,基于线程池,可处理数千并发连接                                  |
| 多引擎   | 单库可按表选用存储引擎(应用层透明)                                              |
| 事务     | InnoDB 完整支持 ACID、MVCC、行锁、间隙锁                                       |
| 复制     | 主从异步、半同步、组复制 (MGR)、异步 GTID                                       |
| 分区     | 水平分区(按范围、列表、哈希、键)                                                |
| 字符集   | utf8、utf8mb4(emoji)、latin1 等                                                |
| 安全     | SSL/TLS、密码验证、审计插件、角色管理                                            |
| 可扩展   | 插件式架构:认证、审计、密码、存储引擎皆可插拔                                    |

### 1.6 MySQL vs 其他数据库

#### 1.6.1 与 PostgreSQL 对比

| 维度       | MySQL 8.0+                 | PostgreSQL 16                  |
|------------|----------------------------|--------------------------------|
| 许可证     | GPL v2(社区版)             | BSD 类似                       |
| 默认引擎   | InnoDB                     | 自研,无引擎切换概念             |
| SQL 规范   | 弱                          | 强(更接近 SQL 标准)           |
| JSON 支持  | JSON 类型(2 进制优化)      | JSONB(更强大)                  |
| 并发控制   | MVCC + 行锁                | MVCC + 多种锁                  |
| 复杂查询   | 弱(无物化视图)            | 强(CTE、递归、物化视图)        |
| 复制       | 主从、组复制                | 流复制、逻辑复制               |
| 性能     | 简单读快                       | 复杂查询/分析强                |
| 适用       | Web 后台、OLTP              | 复杂业务、地理信息、BI         |

#### 1.6.2 与 SQLite 对比

| 维度       | MySQL            | SQLite                       |
|------------|------------------|------------------------------|
| 架构       | C/S              | 库式,嵌入式                  |
| 并发       | 高               | 单写多读(锁库)               |
| 适用规模   | GB ~ TB          | KB ~ 数百 MB                  |
| 网络访问   | 支持             | 不支持(文件直访)             |
| 典型场景   | Web、ERP、微服务 | 移动端、桌面、小工具           |

#### 1.6.3 与 NoSQL(以 MongoDB 为例)对比

| 维度     | MySQL              | MongoDB                    |
|----------|--------------------|----------------------------|
| 数据模型 | 关系表(Schema)     | 文档(BSON,Schema-less)     |
| 事务     | 强 ACID            | 4.0+ 多文档事务             |
| 水平扩展 | 较弱(分库分表)     | 原生分片,水平扩展强         |
| SQL 兼容 | 是                 | 否(自有查询语言)           |
| 适用     | 结构化业务         | 海量日志、灵活 schema 场景  |

---

## 二、MySQL 安装方式

MySQL 提供 **4 种主要安装方式**:包管理器、二进制包、源码编译、Docker。不同方式各有取舍。

### 2.1 包管理器安装(推荐初学者)

#### 2.1.1 Debian/Ubuntu(使用 apt)

```bash
# 1. 添加 MySQL 官方 APT 源 (以 8.0 为例)
wget https://dev.mysql.com/get/mysql-apt-config_0.8.32-1_all.deb
sudo dpkg -i mysql-apt-config_0.8.32-1_all.deb
# 弹出菜单选 MySQL 8.0 后 OK

# 2. 更新索引
sudo apt update

# 3. 安装 Server(会自动拉入客户端、依赖)
sudo apt install mysql-server

# 4. 安装完后查看版本
mysql --version
mysqld --version

# 5. 服务管理
sudo systemctl status mysql        # 查看状态
sudo systemctl start mysql         # 启动
sudo systemctl stop mysql          # 停止
```

**包管理器安装的特点**:

- 自动创建 `mysql` 用户和组
- 自动生成 `/etc/mysql/my.cnf`
- 自动注册 systemd 服务
- 默认数据目录 `/var/lib/mysql`

#### 2.1.2 RHEL/CentOS/Rocky/Alma(使用 yum/dnf)

```bash
# 1. 添加 MySQL 官方 YUM 源(以 EL9 为例)
sudo dnf install https://dev.mysql.com/get/mysql80-community-release-el9-1.noarch.rpm

# 2. 查看可用版本
dnf repolist enabled | grep mysql

# 3. 安装
sudo dnf install mysql-community-server

# 4. 启动
sudo systemctl start mysqld
sudo systemctl enable mysqld
```

#### 2.1.3 MariaDB(在 RHEL/Debian 默认)

```bash
# CentOS / RHEL 自带的 MariaDB
sudo yum install mariadb-server mariadb
sudo systemctl start mariadb
```

### 2.2 二进制包安装(推荐生产服务器)

不需要包管理器,下载压缩包直接解压即可。

#### 2.2.1 下载二进制包

```bash
# 官方下载:https://dev.mysql.com/downloads/mysql/
# 国内镜像:清华、阿里云、华为云镜像
wget https://cdn.mysql.com/Downloads/MySQL-8.0/mysql-8.0.40-linux-glibc2.28-x86_64.tar.xz
```

#### 2.2.2 解压与初始化

```bash
# 1. 添加用户
groupadd mysql
useradd -r -g mysql -s /bin/false mysql

# 2. 解压到 /usr/local
cd /usr/local
tar -xJf /root/mysql-8.0.40-linux-glibc2.28-x86_64.tar.xz
ln -s mysql-8.0.40-linux-glibc2.28-x86_64 mysql

# 3. 配置环境变量
export PATH=/usr/local/mysql/bin:$PATH
echo 'export PATH=/usr/local/mysql/bin:$PATH' >> /etc/profile
source /etc/profile

# 4. 创建数据目录
mkdir -p /data/mysql
chown -R mysql:mysql /data/mysql

# 5. 编辑 /etc/my.cnf
cat > /etc/my.cnf <<'EOF'
[mysqld]
basedir=/usr/local/mysql
datadir=/data/mysql
socket=/tmp/mysql.sock
log_error=/data/mysql/mysql.err
pid-file=/data/mysql/mysqld.pid
user=mysql
EOF

# 6. 初始化(mysqld --initialize)
mysqld --initialize-insecure --user=mysql --basedir=/usr/local/mysql --datadir=/data/mysql
# 初始化后会生成 root 的临时密码(写入 errlog)
# --initialize-insecure 不生成密码(空密码)

# 7. 启动
/usr/local/mysql/bin/mysqld --user=mysql &
# 或用 mysqld_safe
/usr/local/mysql/bin/mysqld_safe --user=mysql &
```

#### 2.2.3 二进制安装的特点

| 优点                            | 缺点                          |
|---------------------------------|-------------------------------|
| 一份包可装多版本,互不干扰      | 需要手动处理 systemd 服务    |
| 启动快,适合容器/精简基础镜像  | 升级需手动替换软链接         |
| 通用,适合多发行版              | 不带包管理器依赖检查         |

### 2.3 源码编译安装(高级用户/DBA 调优)

```bash
# 1. 下载源码
wget https://dev.mysql.com/get/Downloads/MySQL-8.0/mysql-boost-8.0.40.tar.gz

# 2. 安装依赖
yum install -y gcc gcc-c++ cmake bison openssl-devel ncurses-devel

# 3. 解压并配置
tar -xzf mysql-boost-8.0.40.tar.gz
cd mysql-8.0.40
mkdir build && cd build
cmake .. -DCMAKE_INSTALL_PREFIX=/usr/local/mysql \
         -DMYSQL_DATADIR=/data/mysql \
         -DSYSCONFDIR=/etc \
         -DWITH_BOOST=../boost \
         -DWITH_INNOBASE_STORAGE_ENGINE=1 \
         -DENABLE_DOWNLOADS=1

# 4. 编译 (耗时较长)
make -j$(nproc)

# 5. 安装
make install

# 6. 后续初始化同二进制安装
mysqld --initialize --user=mysql
```

**编译安装适用场景**:

- 需要针对特定 CPU/平台打优化
- 需要嵌入自定义补丁
- 学习 MySQL 内部实现

### 2.4 Docker 安装(开发与测试推荐)

#### 2.4.1 官方镜像

```bash
# 1. 拉取官方镜像
docker pull mysql:8.0

# 2. 启动容器(暴露端口、挂载数据)
docker run -d \
  --name mysql8 \
  -p 3306:3306 \
  -e MYSQL_ROOT_PASSWORD=rootpass \
  -v /data/mysql:/var/lib/mysql \
  -v /etc/my.cnf:/etc/mysql/conf.d/my.cnf \
  mysql:8.0

# 3. 进入容器
docker exec -it mysql8 bash
mysql -uroot -p

# 4. 查看日志
docker logs -f mysql8
```

#### 2.4.2 Docker Compose

```yaml
# docker-compose.yml
version: '3.8'
services:
  mysql:
    image: mysql:8.0
    container_name: mysql8
    environment:
      MYSQL_ROOT_PASSWORD: rootpass
      MYSQL_DATABASE: appdb
      MYSQL_USER: appuser
      MYSQL_PASSWORD: apppass
    ports:
      - "3306:3306"
    volumes:
      - mysql_data:/var/lib/mysql
      - ./conf/my.cnf:/etc/mysql/conf.d/custom.cnf
    command:
      - --character-set-server=utf8mb4
      - --collation-server=utf8mb4_unicode_ci
    restart: unless-stopped

volumes:
  mysql_data:
```

```bash
docker compose up -d
docker compose logs -f mysql
```

### 2.5 安装方式对比

| 方式           | 难度 | 升级 | 性能           | 适合场景         |
|----------------|------|------|----------------|------------------|
| apt/yum        | ★    | ★★★   | 一致           | 入门、桌面、CI  |
| 二进制         | ★★   | ★★   | 一致           | 生产服务器       |
| 源码编译       | ★★★★ | ★    | 可调优         | 定制、深度优化   |
| Docker         | ★    | ★★★   | 几乎无开销    | 开发、测试、CI  |

### 2.6 最小化安装后验证

```bash
# 查看所有内置变量
mysqld --print-defaults

# 查看默认存储引擎
mysqld --default-storage-engine=InnoDB --verbose --help | grep -A 1 'default-storage-engine'

# 编译选项
mysqld --verbose --help | grep -i "compiled"
# 输出示例:
# Compiled for Linux on x86_64 ... (glibc)
# Compiled using: GCC 11.3.0
# SSL support: Yes
# THREAD: YES
```

---

## 三、MySQL 目录结构

理解目录结构是运维 MySQL 的基础。MySQL 安装后主要有 **三类目录**:

- `basedir`:程序目录(bin、lib、share)
- `datadir`:数据目录(库、表、日志)
- `cnfdir`:配置文件目录(/etc/mysql 或 /etc)

### 3.1 默认路径总览

| 发行版       | basedir              | datadir              | 配置文件             |
|--------------|----------------------|----------------------|----------------------|
| Debian/Ubuntu| /usr                 | /var/lib/mysql       | /etc/mysql/my.cnf    |
| RHEL/CentOS  | /usr                 | /var/lib/mysql       | /etc/my.cnf          |
| 二进制安装   | /usr/local/mysql     | 自定义(/data/mysql)  | /etc/my.cnf          |

### 3.2 basedir 目录结构

```text
/usr/local/mysql/                       (basedir)
├── bin/                                可执行文件
│   ├── mysqld                          主服务进程
│   ├── mysql                           客户端
│   ├── mysqld_safe                     启动脚本
│   ├── mysqladmin                      管理工具
│   ├── mysqldump                       备份工具
│   ├── mysqlbinlog                     binlog 工具
│   ├── mysql_upgrade                   升级工具
│   ├── mysql_secure_installation       安全初始化
│   └── perror / replace / resolve-stack-symbol 等工具
├── lib/                                动态库、插件
│   └── plugin/                         插件目录(authentication_password.so 等)
├── share/                              字符集、错误信息、SQL 脚本
│   └── charsets/                       字符集定义
│   └── messages_to_clients.txt         错误码说明
├── include/                            C 头文件(开发用)
├── docs/                               CHANGELOG 等
├── man/                                man 手册
└── support-files/                      服务脚本模板
    ├── mysql.server                    SysV 启动脚本
    └── magic                           文件识别
```

### 3.3 datadir 目录结构

```text
/var/lib/mysql/                          (datadir)
├── ibdata1                              系统表空间(共享)
├── ib_logfile0 / ib_logfile1            InnoDB redo log
├── mysql/                               系统库(mysql 系统表)
│   ├── user.frm, user.ibd
│   ├── db.frm, db.ibd
│   └── ...
├── performance_schema/                  性能元数据库
├── sys/                                 sys schema 视图
├── your_database/                       用户库
│   ├── users.frm                        (8.0 起,表结构元信息)
│   ├── users.ibd                        (8.0 起,数据+索引)
│   ├── orders.sdi                       (序列化字典)
│   └── ...
├── binlog.000001                        二进制日志
├── mysqld-relay-bin.*                   中继日志
├── slow.log                             慢查询日志
├── error.log                            错误日志
├── mysqld.pid                           进程 ID
└── auto.cnf                             server-uuid
```

### 3.4 文件类型与作用

| 文件/目录              | 作用                                                  |
|------------------------|------------------------------------------------------|
| `*.frm`                | 5.7 及更早的表结构文件                               |
| `*.ibd`                | InnoDB 数据/索引文件(独立表空间)                    |
| `*.sdi`                | MySQL 8.0 表结构(JSON 格式,替代 .frm)              |
| `ibdata1`              | 系统表空间(8.0 默认独立表空间,ibdata1 仅 undo)      |
| `ib_logfile*`          | redo log                                             |
| `undo_001` / `undo_002`| MySQL 8.0 独立 undo 表空间                          |
| `binlog.*`             | 二进制日志,记录所有 DML 和 DDL                      |
| `slow.log`             | 慢查询日志                                           |
| `error.log`            | 错误日志                                             |
| `pid-file`             | 进程 ID 文件                                         |
| `auto.cnf`             | server-uuid,复制必备                                |

### 3.5 查看实际路径

```sql
-- 进入 mysql 客户端后查询
SHOW VARIABLES LIKE 'basedir';
SHOW VARIABLES LIKE 'datadir';
SHOW VARIABLES LIKE 'plugin_dir';
SHOW VARIABLES LIKE 'log_error';

SHOW VARIABLES LIKE 'general_log%';
SHOW VARIABLES LIKE 'slow_query_log%';
```

```text
+---------------+----------------+
| Variable_name | Value          |
+---------------+----------------+
| basedir       | /usr/local/mysql|
+---------------+----------------+
| datadir       | /data/mysql/   |
+---------------+----------------+
```

---

## 四、MySQL 启动与停止

### 4.1 三种启动方式

```text
┌───────────────────────────────────────────────────────┐
│                  启动方式选择流程                      │
│                                                       │
│  操作系统是 systemd? ───── Yes ─→ systemctl start mysqld│
│         │                                              │
│         No                                            │
│         ↓                                              │
│  SysV init? ────── Yes ─→ service mysqld start        │
│         │                                              │
│         No                                            │
│         ↓                                              │
│  mysqld_safe 或直接 mysqld (手动)                     │
└───────────────────────────────────────────────────────┘
```

### 4.2 systemd 方式(主流发行版默认)

```bash
# 启动
sudo systemctl start mysqld

# 停止
sudo systemctl stop mysqld

# 重启
sudo systemctl restart mysqld

# 重新加载配置(部分参数可热加载)
sudo systemctl reload mysqld

# 状态
sudo systemctl status mysqld

# 开机自启
sudo systemctl enable mysqld

# 取消自启
sudo systemctl disable mysqld

# 查看日志
journalctl -u mysqld -f
```

**systemd 单元文件位置**:

```bash
# RHEL/CentOS
/usr/lib/systemd/system/mysqld.service

# Ubuntu/Debian
/lib/systemd/system/mysql.service

# 自定义 override
/etc/systemd/system/mysqld.service.d/override.conf
```

### 4.3 SysV init(service)方式

部分老旧发行版仍在用 SysV 脚本:

```bash
service mysql start
service mysql stop
service mysql restart
service mysql status

# 直接调用脚本
/etc/init.d/mysql start
```

### 4.4 mysqld_safe(传统启动器,推荐调试用)

`mysqld_safe` 是一个**包装脚本**,会启动 `mysqld` 并自动重启(若异常退出),并把日志写到 errlog。

```bash
# 启动
mysqld_safe --user=mysql &

# 指定配置文件
mysqld_safe --defaults-file=/etc/my.cnf --user=mysql &

# 停止:用 mysqladmin 优雅关闭
mysqladmin -uroot -p shutdown

# 或 ps 杀进程(不推荐)
pgrep -f mysqld | xargs kill -TERM
```

**mysqld_safe 的特点**:

- 自动定位 basedir、datadir
- 出现严重错误时自动重启 mysqld
- 8.0 起已被标记为 deprecated,新部署应直接 systemd 启动

### 4.5 直接调用 mysqld(手动调试)

```bash
# 前台启动(日志直接输出到终端,调试时用)
mysqld --user=mysql --console

# 后台启动
mysqld --user=mysql &

# 指定配置
mysqld --defaults-file=/etc/my.cnf --user=mysql &

# 启动测试配置是否合法(--validate-config,8.0.16+)
mysqld --validate-config
```

### 4.6 启动流程详解

```text
┌────────────────────────────────────────────────────────────┐
│                     mysqld 启动流程                          │
│                                                            │
│  1. 参数解析(命令行 > my.cnf > 默认)                       │
│        ↓                                                    │
│  2. 初始化 InnoDB 数据字典(数据目录不存在)                  │
│        ↓                                                    │
│  3. 日志文件准备(redo、undo、binlog、errlog)               │
│        ↓                                                    │
│  4. 启动 IO threads、purge threads、page cleaner           │
│        ↓                                                    │
│  5. 监听 socket(默认 /tmp/mysql.sock 或 /var/run/mysqld) │
│        ↓                                                    │
│  6. 监听 TCP/IP(默认 0.0.0.0:3306)                       │
│        ↓                                                    │
│  7. 创建客户端连接线程                                       │
└────────────────────────────────────────────────────────────┘
```

### 4.7 验证启动成功

```bash
# 1. 查看进程
ps -ef | grep mysqld
# mysql    1234  ... /usr/local/mysql/bin/mysqld

# 2. 查看端口
ss -ltnp | grep 3306

# 3. 客户端验证
mysql -uroot -p -e "SELECT VERSION();"
```

```text
+-----------+
| VERSION() |
+-----------+
| 8.0.40    |
+-----------+
```

### 4.8 启动失败排查清单

| 现象                          | 排查方向                                |
|------------------------------|-----------------------------------------|
| `Failed to start mysqld.service` | `journalctl -xe -u mysqld`            |
| `Permission denied` on datadir | `chown -R mysql:mysql /data/mysql`     |
| `Can't start server: Bind on TCP/IP port` | 端口占用,`netstat -lnp | grep 3306` |
| `Unknown collation: utf8mb4_0900_ai_ci` | 字符集文件损坏,重装 mysql-common |
| `InnoDB: Operating system error number 13` | 权限或文件系统错误                |
| `Found ... with different paragraph sizes` | 默认配置变更,需显式设置 log file size |

---

## 五、配置文件 my.cnf 详解

### 5.1 配置文件加载顺序

```text
加载优先级(后面的覆盖前面的):
  /etc/my.cnf                          ← 全局
  /etc/mysql/my.cnf                    ← 全局(部分发行版)
  /etc/mysql/conf.d/                   ← Debian drop-in
  SYSCONFDIR/my.cnf                     ← 编译时定义(/etc)
  $MYSQL_HOME/my.cnf                   ← 环境变量指定
  defaults-extra-file                  ← 命令行指定
  ~/.my.cnf                             ← 用户个人
```

可使用 `mysqld --verbose --help` 查看实际加载:

```bash
mysqld --verbose --help 2>&1 | grep -A 1 "Default options"
# Default options are read from /etc/my.cnf /etc/mysql/my.cnf
```

### 5.2 配置段结构

`my.cnf` 由若干 **[group]** 段组成,不同程序读不同段:

```ini
[client]            # 所有客户端(mysql、mysqldump、mysqladmin 等)
[mysql]             # mysql 客户端专用
[mysqld]            # mysqld 服务端
[mysqld_safe]       # mysqld_safe 包装脚本
[mysqldump]         # mysqldump 备份工具
[mysql_upgrade]     # 升级工具
[embedded]          # 嵌入式服务器
```

> 不属于任何段的参数会被忽略。`!include` 和 `!includedir` 可引入子文件。

### 5.3 完整示例 my.cnf

```ini
# ============================================
# /etc/my.cnf - MySQL 8.0 主流配置示例
# ============================================

[client]
# 客户端通用
default-character-set = utf8mb4
socket             = /tmp/mysql.sock
port               = 3306

[mysql]
# mysql 交互式客户端
prompt             = "\\u@\\h:\\p> "
default-character-set = utf8mb4
auto-rehash

[mysqldump]
# 备份工具默认参数
quick
quote-names
max_allowed_packet = 64M

[mysqld]
# ===================== 基础 =====================
user                = mysql
basedir             = /usr/local/mysql
datadir             = /data/mysql
socket              = /tmp/mysql.sock
pid-file            = /data/mysql/mysqld.pid
port                = 3306
bind-address        = 0.0.0.0
server-id           = 1
character-set-server = utf8mb4
collation-server     = utf8mb4_0900_ai_ci
default-storage-engine = InnoDB
skip-name-resolve    # 跳过 DNS 反查,减少连接开销
default-authentication-plugin = caching_sha2_password

# ===================== 错误日志 =================
log_error           = /data/mysql/mysql.err
log_error_verbosity = 3

# ===================== 连接 =======================
max_connections        = 2000
max_user_connections   = 1980
thread_cache_size      = 64
table_open_cache       = 4096
table_definition_cache = 1024
open_files_limit       = 65535
wait_timeout           = 28800
interactive_timeout    = 28800
max_allowed_packet     = 64M

# ===================== InnoDB =====================
innodb_buffer_pool_size      = 8G          # 物理内存的 50%-70%
innodb_buffer_pool_instances = 8           # 每实例 1G
innodb_log_file_size         = 2G
innodb_log_buffer_size       = 64M
innodb_flush_log_at_trx_commit = 1          # 1 最安全,2 性能高
innodb_flush_method          = O_DIRECT
innodb_file_per_table         = ON
innodb_io_capacity           = 2000
innodb_io_capacity_max        = 4000
innodb_autoinc_lock_mode     = 2

# ===================== 二进制日志 =================
log_bin                = /data/mysql/binlog
binlog_format          = ROW
sync_binlog            = 1
expire_logs_days       = 7
max_binlog_size        = 1G
log_slave_updates      = ON
gtid_mode              = ON
enforce_gtid_consistency = ON

# ===================== 慢查询日志 =================
slow_query_log       = ON
slow_query_log_file  = /data/mysql/slow.log
long_query_time      = 1
log_queries_not_using_indexes = ON

# ===================== performance_schema ==========
performance_schema       = ON
performance-schema-instrument = 'memory/%=COUNTED'

[mysqld_safe]
# mysqld_safe 启动器
log_error       = /data/mysql/mysql.err
nice            = 0
malloc-lib      = /usr/lib/x86_64-linux-gnu/libtcmalloc.so.4   # 可选 TCMalloc
```

### 5.4 关键参数详解

| 参数                                  | 作用                  | 推荐值                          |
|---------------------------------------|-----------------------|---------------------------------|
| `basedir`                             | MySQL 安装根          | /usr/local/mysql                |
| `datadir`                             | 数据目录              | /data/mysql                     |
| `port`                                | 监听端口              | 3306(可改)                     |
| `socket`                              | Unix socket 路径      | /tmp/mysql.sock                 |
| `bind-address`                        | 监听 IP               | 0.0.0.0 或内网 IP               |
| `max_connections`                     | 最大连接数            | 1000 ~ 5000                    |
| `innodb_buffer_pool_size`             | 缓冲池                | 物理内存 50%-70%               |
| `innodb_log_file_size`                | redo log 单文件大小   | 1G ~ 4G                        |
| `innodb_flush_log_at_trx_commit`      | 日志刷盘策略          | 1 = 安全 / 0,2 = 性能          |
| `character-set-server`                | 默认字符集            | utf8mb4                        |
| `sql_mode`                            | SQL 模式              | ONLY_FULL_GROUP_BY 默认即可    |
| `lower_case_table_names`              | 表名大小写            | Linux 设为 1(库名不区分)       |
| `skip-grant-tables`                   | 跳过权限(恢复用)      | 出现忘记 root 时临时开          |
| `default-authentication-plugin`       | 认证插件              | caching_sha2_password           |

### 5.5 只读参数 vs 动态参数

| 类型       | 说明                            | 修改方式                                |
|------------|---------------------------------|-----------------------------------------|
| **static** | 启动时读取,运行时不可改        | 修改配置文件,重启 mysqld                |
| **dynamic** | 运行时可改                      | `SET GLOBAL xxx=value` 或在线 PERSIST   |
| **read-only** | 编译期决定                    | 不可能改                                |

```sql
-- 查看参数是否为动态
SELECT NAME, ISNULL(DOCUMENTATION) AS dynamic
FROM performance_schema.variables_info
WHERE NAME IN ('max_connections', 'innodb_buffer_pool_size');
```

```sql
-- 动态修改
SET GLOBAL max_connections = 3000;
SET PERSIST innodb_buffer_pool_size = 12 * 1024 * 1024 * 1024;   -- 写入 mysqld-auto.cnf
SET PERSIST_ONLY slow_query_log = ON;   -- 仅持久化,本次会话不生效
```

---

## 六、连接 MySQL

### 6.1 mysql 客户端启动

```bash
# 最简连接
mysql

# 用户密码
mysql -u root -p

# 指定完整参数
mysql -h 127.0.0.1 -P 3306 -u root -p'password' --ssl-mode=REQUIRED dbname
```

**常用选项**:

| 参数                | 说明                              |
|---------------------|-----------------------------------|
| `-h / --host`       | 主机名或 IP                      |
| `-P / --port`       | TCP 端口                         |
| `-u / --user`       | 用户名                           |
| `-p[password]`      | 密码(加空格则提示输入)          |
| `-S / --socket`     | socket 文件路径                 |
| `-D / --database`   | 连接后直接 use 的库              |
| `-A`                | 不用自动补全,启动更快           |
| `-e`                | 执行 SQL 后退出                 |
| `--execute`         | 同 -e                            |
| `--ssl-mode`        | SSL 模式                        |
| `--protocol`        | TCP / SOCKET / PIPE / MEMORY    |
| `-C`                | 压缩传输                         |
| `--default-character-set` | 客户端字符集              |

### 6.2 通过 Unix Socket 连接

仅本机可用,跳过 TCP:

```bash
mysql -u root -p -S /tmp/mysql.sock

# 或显式
mysql --protocol=SOCKET -u root -p
```

> **socket 路径根据安装方式不同**:
> - 包管理器:`/var/run/mysqld/mysqld.sock`(RHEL)、`/var/run/mysqld/mysqld.sock`(Debian)
> - 二进制安装:`/tmp/mysql.sock`(自定)

### 6.3 通过 TCP/IP 连接

```bash
# 本地 TCP
mysql -h 127.0.0.1 -P 3306 -u root -p

# 远程主机
mysql -h 10.0.0.5 -P 3306 -u app -p'AppPass123'

# 启用 SSL
mysql -h db.example.com -P 3306 -u app --ssl-mode=VERIFY_CA \
     --ssl-ca=/etc/ca.pem -p
```

**`--ssl-mode` 取值**:

| 值              | 含义                                          |
|-----------------|-----------------------------------------------|
| DISABLED         | 禁止 SSL                                      |
| PREFERRED        | 默认,优先尝试 SSL                            |
| REQUIRED         | 必须 SSL                                      |
| VERIFY_CA        | 必须 SSL,验证 CA                              |
| VERIFY_IDENTITY  | 必须 SSL,验证 CA + 主机名                     |

### 6.4 一次性执行 SQL

```bash
# 执行单条 SQL
mysql -uroot -p'pass' -e "SELECT NOW();"

# 批量执行
mysql -uroot -p'pass' < /tmp/script.sql

# 指定库执行
mysql -uroot -p'pass' appdb -e "SHOW TABLES;"
```

### 6.5 配置文件持久化连接参数

```bash
# ~/.my.cnf,避免每次敲密码
cat > ~/.my.cnf <<'EOF'
[client]
user=root
password='rootpass'
host=127.0.0.1
EOF
chmod 600 ~/.my.cnf
```

```bash
mysqladmin ping         # 直接测试连接
mysql -e "SELECT 1"
```

> 注意:对于需要交互输入的 root 密码,写文件有风险。生产环境推荐使用 `--login-path`(见下)。

### 6.6 mysql_config_editor(登录路径)

```bash
# 创建登录路径(仅存哈希,不存明文密码)
mysql_config_editor set --login-path=dev --host=127.0.0.1 \
                        --user=root --password
# 提示输入密码

# 查看保存的路径
mysql_config_editor print --all

# 使用
mysql --login-path=dev
mysqldump --login-path=dev dbname > backup.sql
```

### 6.7 各应用驱动连接字符串示例

| 语言/驱动         | 连接串示例                                                                                  |
|-------------------|---------------------------------------------------------------------------------------------|
| JDBC (Java)       | `jdbc:mysql://10.0.0.5:3306/appdb?useSSL=false&serverTimezone=UTC&characterEncoding=utf8`    |
| Python (PyMySQL)  | `pymysql.connect(host='10.0.0.5', port=3306, user='app', password='app', db='appdb')`        |
| Go (go-sql-driver)| `mysql,app:pwd@tcp(10.0.0.5:3306)/appdb?charset=utf8mb4&loc=Local&parseTime=true`            |
| Node.js (mysql2)  | `mysql.createConnection({host:'10.0.0.5', user:'app', password:'pwd', database:'appdb'})`    |

### 6.8 常见连接问题排查

| 错误                                       | 原因                              | 解决方案                         |
|--------------------------------------------|-----------------------------------|----------------------------------|
| `ERROR 2003 (HY000): Can't connect to MySQL server` | 端口未监听/IP 错/防火墙           | 检查 `bind-address`,端口,防火墙 |
| `ERROR 1045 (28000): Access denied`        | 用户/密码/host 不匹配             | 查 `mysql.user`,重置密码        |
| `ERROR 2013 (HY000): Lost connection`     | max_allowed_packet 过小或超时     | 调大 `max_allowed_packet`        |
| `Can't connect to local MySQL server through socket` | socket 路径错                | `-S` 指定正确路径               |
| `SSL connection error: certificate verify failed` | CA/证书问题                  | 配置 `ssl-ca` / `ssl-mode`        |

---

## 七、初始账号与密码管理

### 7.1 初次安装后的默认账户

| 用户                  | 密码                                 | 备注                                |
|-----------------------|--------------------------------------|-------------------------------------|
| `root@localhost`      | 随机初始密码(写入 errlog)            | MySQL 5.7、8.0 包管理器安装默认     |
| `root@localhost`      | 空密码(`--initialize-insecure`)      | 二进制安装使用 `initialize-insecure` |
| `mysql.session`       | 内置,不可登录                        | 系统内部用                          |
| `mysql.sys`           | 内置,不可登录                        | sys schema 用                       |
| `mysql.infoschema`    | 内置,不可登录                        | 性能模式用                          |

### 7.2 查看初始密码

```bash
# 5.7/8.0 在 errlog 中
grep 'temporary password' /var/log/mysqld.log
# 或 Debian:
grep 'temporary password' /var/log/mysql/error.log
```

### 7.3 mysql_secure_installation 安全初始化向导

```bash
sudo mysql_secure_installation
```

```text
1. 设置 root 密码强度
   - VALIDATE PASSWORD COMPONENT 策略
2. 设置 root 新密码
   - 强度至少 8 位
3. 是否删除匿名用户?  → Y
4. 是否禁止 root 远程登录? → Y(默认仅 localhost)
5. 是否删除 test 库?  → Y
6. 是否立即重载权限表? → Y
```

### 7.4 修改 root 密码

#### 7.4.1 ALTER USER(MySQL 5.7.6+ 推荐)

```sql
ALTER USER 'root'@'localhost' IDENTIFIED BY 'NewRootPass123!';
FLUSH PRIVILEGES;
```

#### 7.4.2 SET PASSWORD

```sql
SET PASSWORD FOR 'root'@'localhost' = 'NewRootPass123!';
```

#### 7.4.3 mysqladmin 命令行

```bash
mysqladmin -u root -p'OldPass' password 'NewPass'
```

#### 7.4.4 修改自己(不需要旧密码)

```sql
ALTER USER USER() IDENTIFIED BY 'NewPass123!';
```

### 7.5 忘记 root 密码的恢复

#### 方法一:`--skip-grant-tables` 模式

```bash
# 1. 停服
sudo systemctl stop mysqld

# 2. 以跳过权限模式启动
sudo mysqld --skip-grant-tables --skip-networking &

# 3. 无密码登录
mysql

# 4. 重置密码
FLUSH PRIVILEGES;
ALTER USER 'root'@'localhost' IDENTIFIED BY 'NewRootPass123!';

# 5. 重启服务
mysqladmin shutdown
sudo systemctl start mysqld
```

#### 方法二:`init-file` 重置文件

```bash
# 1. 准备 SQL
echo "ALTER USER 'root'@'localhost' IDENTIFIED BY 'NewRootPass123!';" > /tmp/init.sql

# 2. 启动时加载
sudo systemctl stop mysqld
sudo mysqld --init-file=/tmp/init.sql &

# 等待,登录验证
mysql -uroot -p'NewRootPass123!'
```

### 7.6 创建和删除用户

```sql
-- 创建
CREATE USER 'appuser'@'10.0.%.%' IDENTIFIED BY 'AppPass123!';

-- 创建并授权
CREATE USER 'appuser'@'%' IDENTIFIED BY 'AppPass123!';
GRANT SELECT, INSERT, UPDATE ON appdb.* TO 'appuser'@'%';

-- 取消授权
REVOKE INSERT ON appdb.* FROM 'appuser'@'%';

-- 修改密码
ALTER USER 'appuser'@'%' IDENTIFIED BY 'NewAppPass456@';

-- 删除
DROP USER 'appuser'@'%';
```

### 7.7 密码安全策略

| 参数                            | 作用                        | 推荐           |
|---------------------------------|-----------------------------|----------------|
| `validate_password.policy`      | 强度等级:0=低,1=中,2=强    | 2              |
| `validate_password.length`      | 密码最短长度                | 12             |
| `validate_password.mixed_case_count` | 大小写字母数量            | 1              |
| `validate_password.number_count`    | 数字数量                | 1              |
| `validate_password.special_char_count` | 特殊字符数量          | 1              |
| `default_password_lifetime`     | 密码生命周期(天)            | 90             |
| `password_reuse_interval`       | 多少天内不能重用            | 60             |
| `password_history`              | 历史密码记住 N 个           | 5              |

```sql
-- 配置强化密码策略
SET PERSIST validate_password.policy = 2;
SET PERSIST validate_password.length = 12;
SET PERSIST default_password_lifetime = 90;
SET PERSIST password_reuse_interval = 60;
SET PERSIST password_history = 5;
```

---

## 八、常用管理命令

### 8.1 查看服务器状态

#### 8.1.1 status(/s)

```sql
mysql> status
--------------
mysql  Ver 8.0.40 for Linux on x86_64 (MySQL Community Server - GPL)

Connection id:        12
Current database:     appdb
Current user:         root@localhost
SSL:                  Not in use
Using delimiter:      ;
Server version:       8.0.40 MySQL Community Server - GPL
Protocol version:     10
Connection:           127.0.0.1 via TCP/IP
Server characterset:  utf8mb4
Db     characterset:  utf8mb4
Client characterset:  utf8mb4
Conn.  characterset:  utf8mb4
Uptime:               3 days 08:12:45

Threads: 2  Questions: 4521  Slow queries: 0  Opens: 180  \
Flush tables: 1  Open tables: 120  Queries per second avg: 0.016
--------------
```

#### 8.1.2 mysqladmin extended-status

```bash
mysqladmin -uroot -p extended-status | head -20
```

输出类似 `SHOW GLOBAL STATUS` 的全部 Key-Value。

### 8.2 SHOW VARIABLES

```sql
-- 当前会话
SHOW VARIABLES LIKE 'innodb_buffer_pool_size';

-- 全局
SHOW GLOBAL VARIABLES LIKE '%innodb%';

-- 模糊搜索
SHOW VARIABLES LIKE '%timeout%';

-- 按 G 分列
SHOW GLOBAL VARIABLES LIKE 'max_connections'\G
```

**`SHOW VARIABLES` 与 `SHOW STATUS` 区别**:

| 项目        | 来源                          |
|-------------|-------------------------------|
| VARIABLES   | 配置参数(可写)                |
| STATUS      | 运行时计数器/统计(只读)      |

### 8.3 SHOW PROCESSLIST / 性能模式

```sql
-- 查看当前连接
SHOW PROCESSLIST;
SHOW FULL PROCESSLIST;   -- 显示完整 SQL

-- 输出
+----+-------+--------------------+------+---------+------+----------+------------------+
| Id | User  | Host               | db   | Command | Time | State    | Info             |
+----+-------+--------------------+------+---------+------+----------+------------------+
| 12 | root  | localhost          | NULL | Query   |    0 | starting | SHOW PROCESSLIST |
| 13 | app   | 10.0.0.1:54321     | appdb| Sleep   |   30 |          | NULL             |
| 14 | app   | 10.0.0.2:54322     | appdb| Query   |    1 | Sending data | SELECT * FROM ... |
+----+-------+--------------------+------+---------+------+----------+------------------+
```

```sql
-- 杀连接
KILL 13;
KILL CONNECTION 13;   -- 强杀
KILL QUERY 13;        -- 仅杀当前查询
```

### 8.4 SHOW ENGINE INNODB STATUS

```sql
SHOW ENGINE INNODB STATUS\G
```

输出含 BUFFER POOL、LOCK、TRANSACTION、FILE I/O 等段,是 InnoDB 调优的"诊断报告书"。

### 8.5 information_schema 与 performance_schema

```sql
-- 表占用空间
SELECT
  table_name,
  table_rows,
  ROUND(data_length/1024/1024, 2) AS data_mb,
  ROUND(index_length/1024/1024, 2) AS idx_mb
FROM information_schema.tables
WHERE table_schema='appdb';

-- 查索引
SHOW INDEX FROM users;

-- 查 Binlog
SHOW BINARY LOGS;
SHOW MASTER STATUS;

-- 查配置参数
SELECT NAME, DEFAULT_VALUE
FROM performance_schema.variables_info
WHERE DEFAULT_VALUE IS NOT NULL;
```

### 8.6 mysqladmin 工具集

| 命令                              | 作用                              |
|-----------------------------------|-----------------------------------|
| `mysqladmin ping`                 | ping 服务器                       |
| `mysqladmin processlist`          | 等价 `SHOW PROCESSLIST`           |
| `mysqladmin status`               | 显示 uptime、线程数等             |
| `mysqladmin shutdown`             | 优雅关闭                          |
| `mysqladmin reload`              | 重载权限和某些配置                |
| `mysqladmin kill id1,id2,...`    | 杀连接                            |
| `mysqladmin variables`           | 列出所有变量                      |
| `mysqladmin create dbname`       | 建库                              |
| `mysqladmin drop dbname`         | 删库                              |
| `mysqladmin password`            | 改密码                            |
| `mysqladmin debug`               | 调度 debug 信息(可能影响服务)   |
| `mysqladmin extended-status`     | 等价 `SHOW GLOBAL STATUS`         |

---

## 九、升级与迁移

### 9.1 升级路径

| 升级方式         | 适用场景                            | 风险     |
|------------------|-------------------------------------|----------|
| **in-place**     | 同架构、目录升级到高版本(5.7→8.0) | 中:不可直接回滚 |
| **logical**      | 用 mysqldump 重新导入               | 低       |
| **major skip**   | 跨大版本升级,建议先过渡一次         | 高       |

> MySQL 8.0 GA 之前(2018 年以前)发布版本不允许**跨大版本直跳**(如 5.5 → 8.0),必须逐次升级。

### 9.2 升级前的检查

```bash
# 1. mysql_upgrade 检查
mysql_upgrade --check

# 2. 查看过时特性
# /var/log/mysql/error.log
# /var/log/mysql/general.log

# 3. 备份(必须!)
mysqldump -uroot -p --all-databases --routines --triggers --events > all.sql
mysqldump -uroot -p --all-databases --routines --single-transaction --master-data=2 > all.sql
```

### 9.3 in-place 升级(同主机、目录替换)

```bash
# 1. 停服
sudo systemctl stop mysqld

# 2. 备份原 basedir / datadir / my.cnf
cp -a /usr/local/mysql /usr/local/mysql.bak
cp -a /data/mysql /data/mysql.bak
cp /etc/my.cnf /etc/my.cnf.bak

# 3. 解压新版本 binary
cd /usr/local
tar -xJf mysql-8.0.40-linux-glibc2.28-x86_64.tar.xz
rm mysql  # 旧的软链
ln -s mysql-8.0.40-linux-glibc2.28-x86_64 mysql

# 4. 重启 mysqld
sudo systemctl start mysqld

# 5. 升级数据字典
mysql_upgrade -uroot -p

# 6. 重启加载新元数据
sudo systemctl restart mysqld
```

### 9.4 逻辑迁移(logical,跨主机跨版本)

```bash
# 源库导出
mysqldump -u root -p \
  --single-transaction \
  --routines \
  --triggers \
  --events \
  --master-data=2 \
  --databases appdb > appdb.sql

# 目标库导入
mysql -u root -p < appdb.sql
```

#### 9.4.1 大数据量用管道

```bash
mysqldump -uroot -p'pass' --all-databases --triggers --routines \
  | mysql -h newhost -uroot -p'pass'
```

### 9.5 复制迁移(在线无感)

```text
     旧主            旧从
       ↓              ↑
       └──→ 新主 ←───┘
            ↑
            │
          新从(可接入)

step 1: 新主配置 server_id + GTID
step 2: 从旧主 dump,拿到一致位点
step 3: 新主执行 CHANGE MASTER TO 指向旧主
step 4: 追上后,停服,新主 promotion
step 5: 业务改写连接
```

### 9.6 升级注意事项清单

| 注意项                                        | 说明                                        |
|----------------------------------------------|---------------------------------------------|
| 先升级到当前版本的最后一个 release            | 例:5.7 → 5.7.44 → 8.0                       |
| 必须 `mysql_upgrade`                          | 否则元数据保留旧格式                        |
| 检查 `lower_case_table_names` 一致性          | 跨平台迁移尤其重要                          |
| 检查 `sql_mode`                                | 8.0 默认更严                                |
| 保留原 `my.cnf` 备份                           | 应对不兼容参数                              |
| 检查字符集和排序规则                           | utf8 → utf8mb4                              |
| 备份后,**演练一次恢复**                      | 验证备份可用                                |

---

## 十、卸载 MySQL

### 10.1 包管理器安装的卸载

```bash
# RHEL/CentOS
sudo systemctl stop mysqld
sudo yum remove mysql-server mysql mysql-common mysql-community-*

# Debian/Ubuntu
sudo systemctl stop mysql
sudo apt remove mysql-server mysql-common
sudo apt autoremove
sudo apt purge mysql-server mysql-common

# 清理残余目录(谨慎!)
sudo rm -rf /var/lib/mysql
sudo rm -rf /etc/mysql
sudo rm /etc/my.cnf
sudo rm -rf /var/log/mysql
sudo rm -rf /var/log/mysqld.log
sudo userdel -r mysql
```

### 10.2 二进制安装的卸载

```bash
# 停服
mysqladmin -uroot -p shutdown

# 删除
rm -rf /usr/local/mysql
rm -rf /usr/local/mysql-8.0.40*
rm /etc/my.cnf
rm -rf /data/mysql
sed -i '/export PATH=\/usr\/local\/mysql/d' /etc/profile
userdel -r mysql
```

### 10.3 Docker 卸载

```bash
# 停掉并删除容器
docker stop mysql8
docker rm mysql8

# 删除镜像(可选)
docker rmi mysql:8.0

# 删除卷(可选,清数据)
docker volume ls | grep mysql
docker volume rm mysql_mysql_data
```

### 10.4 验证已彻底卸载

```bash
# 验证命令不存在
which mysql
which mysqld

# 验证没有进程
pgrep -af mysqld

# 验证没有服务
systemctl list-unit-files | grep -i mysql
```

```text
(无输出,即为彻底卸载)
```

---

## 十一、核心要点速记

- **MySQL 由 Oracle 维护**,另有两分支 MariaDB、Percona,语法高度兼容
- **版本选择**:生产优先 MySQL 8.0 LTS 或 8.4 LTS,**避免 Innovation 版本**用于生产
- **存储引擎**:自 5.5.5 起 InnoDB 默认,支持事务、行锁、MVCC
- **三种安装方式选型**:包管理器(简单)、二进制(可控)、Docker(隔离)、源码(深度定制)
- **目录结构**:`basedir`(程序)、`datadir`(数据)、`/etc/my.cnf`(配置)三件套
- **启动方式**:`systemctl`(主流)、`service`(传统)、`mysqld_safe`(调试)、直接 `mysqld`(前台)
- **配置文件加载顺序**:`/etc/my.cnf` → `/etc/mysql/conf.d` → `~/.my.cnf`,后者覆盖前者
- **配置分段**:`[client]`/`[mysql]`/`[mysqld]`/`[mysqld_safe]`,**只有被对应程序读取才生效**
- **核心参数**:`innodb_buffer_pool_size` 设为内存 50-70%、`max_connections` 按业务设、`character-set-server=utf8mb4`
- **客户端连接**:socket(本机)、TCP(远程)、SSL(加密),可用 `mysql_config_editor` 保存登录路径
- **初始密码**:包管理器装在 errlog 中;二进制用 `--initialize-insecure` 则无密码
- **`mysql_secure_installation`** 是安装后必做的安全加固(改密码、删匿名、禁远程 root)
- **忘记 root 密码**:用 `skip-grant-tables` 启动或 `init-file` 重置,必先停服再操作
- **常用命令**:`status` 看会话信息、`SHOW VARIABLES` 看参数、`SHOW PROCESSLIST` 看连接、`KILL` 杀慢查询
- **SHOW 三件套**:VARIABLES(配置)、STATUS(计数)、PROCESSLIST(连接)
- **升级路径**:同版本小版本直接重启;跨大版本要先到该大版本最后一个 release;跨大版本可用 in-place 或逻辑备份恢复
- **逻辑迁移**:`mysqldump --single-transaction --master-data=2` 是最常用的在线导出组合
- **卸载**:包管理器 `remove/purge` → 清目录 → 删用户;二进制直接删 basedir/datadir 即可
- **MySQL 8.0 默认认证插件为 `caching_sha2_password`**,旧客户端需升级或换 `mysql_native_password`
- **坑点提示**:`skip-grant-tables` 启动后**禁用远程**,必须本地 socket;`lower_case_table_names` 一旦定就不能改
