# PostgreSQL 知识体系

> 按照 [操作系统](../../计算机基础/操作系统/) 的章节组织方式编排,与 [MySQL 文档](../MySQL/)、[Redis 文档](../Redis/) 同结构。涵盖 PostgreSQL 从入门到精通的完整知识体系。

## 章节目录

| 章节 | 标题 | 大小 | 主要内容 |
|------|------|------|---------|
| [01](01-PostgreSQL概述与安装.md) | PostgreSQL 概述与安装 | 79K | 历史、安装、postgresql.conf、pg_hba.conf、psql |
| [02](02-体系结构.md) | 体系结构 | 59K | 多进程架构、Tuple Header、TOAST、WAL buffer |
| [03](03-SQL基础与数据类型.md) | SQL 基础与数据类型 | 55K | 22 种内置类型、JSONB、数组、范围、UUID |
| [04](04-数据库和表操作.md) | 数据库和表操作 | 55K | DDL、IDENTITY、EXCLUDE、物化视图、表继承 |
| [05](05-索引体系.md) | 索引体系 | 63K | B-Tree/Hash/GiST/GIN/BRIN、表达式/部分/INCLUDE 索引 |
| [06](06-查询计划与EXPLAIN.md) | 查询计划与 EXPLAIN | 75K | Seq/Index/Bitmap 扫描、NL/Hash/Merge JOIN |
| [07](07-事务与MVCC.md) | 事务与 MVCC | 74K | ACID、xmin/xmax、HOT、SSI、行级锁 |
| [08](08-锁机制.md) | 锁机制 | 53K | 8 种表级锁、行锁、Advisory Lock、SKIP LOCKED |
| [09](09-WAL与日志.md) | WAL 与日志 | 118K | WAL 文件、Checkpoint、pg_stat_statements |
| [10](10-Vacuum与表膨胀.md) | Vacuum 与表膨胀 | 38K | Autovacuum、FSM/Visibility Map、XID 回卷 |
| [11](11-备份与恢复.md) | 备份与恢复 | 94K | pg_dump、pg_basebackup、PITR、pgBackRest |
| [12](12-复制.md) | 复制 | 58K | 流复制、逻辑复制、复制槽、跨版本 |
| [13](13-高可用架构.md) | 高可用架构 | 24K | Patroni、pg_auto_failover、Repmgr、HAProxy |
| [14](14-分区表.md) | 分区表 | 29K | RANGE/LIST/HASH、pg_partman、分区裁剪 |
| [15](15-性能调优.md) | 性能调优 | 66K | 调优金字塔、postgresql.conf 模板、监控 |
| [16](16-权限安全与扩展.md) | 权限安全与扩展 | 59K | RLS、SSL、扩展(PostGIS/pgvector/pg_trgm) |

## 知识地图

```text
入门              进阶                  高级                  实战
├─ 01 安装       ├─ 04 DDL             ├─ 09 WAL            ├─ 13 高可用
├─ 02 架构       ├─ 05 索引            ├─ 10 Vacuum         ├─ 14 分区表
└─ 03 SQL/类型   ├─ 06 EXPLAIN         ├─ 11 备份恢复        ├─ 15 性能调优
                 ├─ 07 事务/MVCC       └─ 12 复制           └─ 16 权限/扩展
                 └─ 08 锁机制
```

## PostgreSQL 特色

PG 区别于 MySQL 的独特能力:

| 特色 | 说明 |
|------|------|
| **MVCC 实现** | xmin/xmax 在 Heap 内, 无 undo log, 更新不删旧行 |
| **丰富类型** | JSONB、数组、范围、几何、网络地址、UUID、自定义类型 |
| **丰富索引** | B-Tree/Hash/GiST/GIN/BRIN/SP-GiST + 部分/表达式/INCLUDE |
| **高级约束** | EXCLUDE 排他约束、GENERATED 列、DEFERRABLE |
| **物化视图** | 持久存储结果, CONCURRENTLY 刷新 |
| **行级安全 RLS** | 数据库层多租户隔离 |
| **声明式分区** | PG 10+ 原生支持, RANGE/LIST/HASH |
| **逻辑复制** | publication/subscription 灵活同步 |
| **PITR** | 基于 WAL 归档的时间点恢复 |
| **扩展生态** | PostGIS、pgvector、pg_trgm、pgcrypto 等丰富扩展 |

## 学习路线建议

### 初学者 (1-2 周)

1. 阅读 01 了解 PG 是什么、如何安装
2. 学习 02 掌握多进程架构、Heap Tuple 结构
3. 学习 03 掌握丰富的数据类型 (JSONB、数组、范围)
4. 学习 04 学会 DDL (IDENTITY、EXCLUDE)

### 进阶者 (2-4 周)

1. 学习 05 索引体系, 重点 GIN/BRIN/部分索引
2. 学习 06 EXPLAIN 分析慢查询
3. 学习 07 MVCC 原理 (xmin/xmax、HOT)
4. 学习 08 锁机制 (8 种表锁、Advisory Lock)

### 高级者 (4-8 周)

1. 学习 09 WAL 工作机制
2. 学习 10 Vacuum 与表膨胀, 避免 XID 回卷
3. 学习 11 备份恢复, 重点 PITR
4. 学习 12 复制 (流复制 + 逻辑复制)

### 实战方向

- **运维 SRE**: 13 高可用 + 15 性能调优
- **架构师**: 14 分区表 + 16 扩展选型
- **DBA**: 09 WAL + 10 Vacuum + 11 备份

## 配套工具推荐

| 工具 | 用途 | 链接 |
|------|------|------|
| pgAdmin 4 | 官方 GUI | https://www.pgadmin.org |
| DBeaver | 通用客户端 | https://dbeaver.io |
| Patroni | HA 工具 (业界标准) | https://patroni.readthedocs.io |
| pgBackRest | 备份恢复 | https://pgbackrest.org |
| pg_repack | 在线重组表 | https://reorg.github.io/pg_repack |
| pg_partman | 自动分区 | https://github.com/pgpartman/pg_partman |
| pgBadger | 慢查询日志分析 | https://github.com/darold/pgbadger |
| PgBouncer | 连接池 | https://www.pgbouncer.org |
| PostGIS | 地理空间 | https://postgis.net |
| pgvector | AI 向量检索 | https://github.com/pgvector/pgvector |
| pgAudit | 审计 | https://github.com/pgaudit/pgaudit |

## 版本说明

- 主要面向 **PostgreSQL 15 / 16 / 17**
- 部分内容 (行级安全 RLS 增强、逻辑复制冲突改进) 需要 PG 12+
- pgvector、PostGIS 是当前热点扩展

## PostgreSQL vs MySQL vs Oracle 对比

| 维度 | PostgreSQL | MySQL | Oracle |
|------|-----------|-------|--------|
| 类型 | 对象关系型 | 关系型 | 关系型 |
| 开源 | 完全开源 BSD | GPL + 商业版 | 商业 |
| SQL 标准 | 最接近 SQL 标准 | 部分偏离 | 偏离较多 |
| 事务 | 完整 ACID | 完整 ACID (InnoDB) | 完整 ACID |
| MVCC | Heap 内 xmin/xmax | rollback segment + undo | undo 表空间 |
| JSON 支持 | JSONB (强) | JSON (弱) | JSON (Oracle 21c+) |
| 地理空间 | PostGIS (强) | 弱 | Oracle Spatial |
| 默认隔离 | Read Committed | Repeatable Read (InnoDB) | Read Committed |
| 索引类型 | 6+ 种 | 主要 B+Tree | B-Tree、Bitmap 等 |
| 扩展生态 | 极丰富 | 一般 | 闭源 |

## 贡献

发现错误或想补充内容,直接修改对应章节的 md 文件即可。
