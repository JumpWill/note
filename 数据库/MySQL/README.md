# MySQL 知识体系

> 按照 [操作系统](../../计算机基础/操作系统/) 的章节组织方式编排。涵盖 MySQL 从入门到精通的完整知识体系。

## 章节目录

| 章节 | 标题 | 大小 | 主要内容 |
|------|------|------|---------|
| [01](01-MySQL概述与安装.md) | MySQL 概述与安装 | 51K | 历史、安装、目录结构、my.cnf、连接管理 |
| [02](02-体系结构.md) | MySQL 体系结构 | 55K | 三层架构、SQL 执行流程、线程模型、内存结构 |
| [03](03-SQL基础与数据类型.md) | SQL 基础与数据类型 | 36K | SQL 分类、数值/字符串/日期/JSON 类型、字符集 |
| [04](04-数据库和表操作.md) | 数据库和表操作 | 39K | DDL、约束、AUTO_INCREMENT、ALTER TABLE、分区表 |
| [05](05-索引.md) | 索引 | 49K | B+Tree、聚簇/非聚簇、覆盖索引、最左前缀、ICP |
| [06](06-存储引擎.md) | 存储引擎 | 51K | InnoDB 数据页、行格式、MyISAM、Memory、Archive |
| [07](07-事务.md) | 事务 | 50K | ACID、隔离级别、快照读、XA 事务 |
| [08](08-锁机制.md) | 锁机制 | 54K | 全局锁、表锁、行锁、Next-Key Lock、死锁 |
| [09](09-日志系统.md) | 日志系统 | 79K | binlog、redo log、undo log、两阶段提交 |
| [10](10-MVCC.md) | MVCC | 49K | 版本链、Read View、可见性算法 |
| [11](11-查询优化与EXPLAIN.md) | 查询优化与 EXPLAIN | 55K | EXPLAIN 各字段、SQL 优化、JOIN 优化 |
| [12](12-备份与恢复.md) | 备份与恢复 | 42K | mysqldump、XtraBackup、时间点恢复 |
| [13](13-主从复制.md) | 主从复制 (异步/半同步) | 41K | binlog 复制、GTID、半同步、并行复制 |
| [14](14-MGR详解.md) | MGR 详解 (同步复制) | **63K** | Paxos、Flow Control、InnoDB Cluster |
| [15](15-高可用架构.md) | 高可用架构 | 36K | MHA、Orchestrator、ProxySQL、选型 |
| [16](16-分库分表.md) | 分库分表 | 62K | Sharding-JDBC、MyCat、分布式事务、雪花算法 |
| [17](17-性能监控与调优.md) | 性能监控与调优 | 51K | 监控指标、调优参数、my.cnf 模板 |
| [18](18-权限与安全.md) | 权限与安全 | 35K | 用户、权限、角色、SSL、加密、审计 |
| [19](19-常见问题排查.md) | 常见问题排查 | 25K | 连接/性能/锁/复制/空间问题处理 |

## 知识地图

```text
入门          进阶               高级              架构
├─ 01 安装   ├─ 05 索引         ├─ 09 日志系统    ├─ 13 主从复制
├─ 02 架构   ├─ 06 存储引擎     ├─ 10 MVCC        ├─ 14 MGR 详解
├─ 03 SQL    ├─ 07 事务         ├─ 11 查询优化    ├─ 15 高可用
└─ 04 DDL    └─ 08 锁机制       └─ 12 备份恢复    ├─ 16 分库分表
                                                └─ 17 性能调优
                                                    └─ 18 权限
                                                    └─ 19 排错
```

## 复制体系专题

MySQL 复制有三层结构,建议按以下顺序学习:

```text
13-主从复制 (异步/半同步)
  ├─ 异步复制     - 性能优先,可能丢数据
  ├─ 半同步复制   - 折中方案,RPO≈0
  └─ GTID         - 简化运维
         ↓
14-MGR 详解 (同步多主/单主)
  ├─ Paxos 协议   - 强一致,真正 RPO=0
  ├─ 单主模式     - 生产推荐
  ├─ 多主模式     - 异地多活
  └─ InnoDB Cluster - MGR + Router + Shell
         ↓
15-高可用架构 (选型)
  ├─ MHA        - 异步+ 自动切换
  ├─ Orchestrator - 拓扑感知切换
  └─ ProxySQL   - 读写分离 + 连接池
```

## 学习路线建议

### 初学者 (1-2 周)

1. 阅读 01 了解 MySQL 是什么、整体如何工作
2. 学习 02 掌握 SQL 语法和数据类型
3. 学习 03 学会建库建表
4. 实践 04 索引基础,能用 EXPLAIN 分析慢查询

### 进阶者 (2-4 周)

1. 深入 06 存储引擎,理解 InnoDB 数据页结构
2. 掌握 07 事务的 ACID 和隔离级别
3. 学习 08 锁机制,能排查死锁
4. 理解 09 日志系统,尤其是 redo/binlog 两阶段提交
5. 理解 10 MVCC 的实现原理

### 高级者 (4-8 周)

1. 精通 11 查询优化,EXPLAIN 各字段含义
2. 掌握 12 备份恢复,mysqldump + binlog 时间点恢复
3. **13 主从复制**: GTID、半同步、并行复制
4. **14 MGR**: Paxos 协议、Flow Control、生产部署
5. **15 高可用架构**: 各方案选型对比
6. 学习 16 分库分表,理解分布式事务

### 运维方向

- 重点:01 安装、12 备份、13 复制、14 MGR、15 高可用、17 调优、19 排查
- 必备:18 权限与安全

### 开发方向

- 重点:03 SQL、04 DDL、05 索引、11 查询优化
- 必备:07 事务、08 锁机制

## 配套工具推荐

| 工具 | 用途 | 链接 |
|------|------|------|
| mycli | 命令行智能提示 | https://www.mycli.net |
| XtraBackup | 热备份 | https://www.percona.com/software/mysql-database/percona-xtrabackup |
| Percona Toolkit | 运维工具集 | https://www.percona.com/software/database-tools/percona-toolkit |
| MySQL Shell | 高级客户端 + InnoDB Cluster | https://dev.mysql.com/doc/mysql-shell/8.0/en/ |
| MySQL Router | MGR 路由代理 | https://dev.mysql.com/doc/mysql-router/8.0/en/ |
| Prometheus + mysqld_exporter | 监控 | https://github.com/prometheus/mysqld_exporter |
| Orchestrator | 复制拓扑切换 | https://github.com/openarkcode/orchestrator |
| ProxySQL | 读写分离 + 连接池 | https://www.proxysql.com |
| ShardingSphere | 分库分表 | https://shardingsphere.apache.org |

## 版本说明

- 主要面向 **MySQL 5.7 / 8.0**
- MGR 章节需要 MySQL **5.7.17+ / 8.0+**
- 部分内容(角色、窗口函数、CTE 等)需要 **MySQL 8.0+**

## 贡献

发现错误或想补充内容,直接修改对应章节的 md 文件即可。
