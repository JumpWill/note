# Redis 知识体系

> 按照 [操作系统](../../计算机基础/操作系统/) 的章节组织方式编排,与 [MySQL 文档](../MySQL/) 同结构。涵盖 Redis 从入门到精通的完整知识体系。

## 章节目录

| 章节 | 标题 | 大小 | 主要内容 |
|------|------|------|---------|
| [01](01-Redis概述与安装.md) | Redis 概述与安装 | 54K | 历史、安装、redis.conf、redis-cli、INFO |
| [02](02-数据结构与底层编码.md) | 数据结构与底层编码 | 45K | SDS、listpack、skiplist、dict、渐进式 rehash |
| [03](03-五大基础数据类型.md) | 五大基础数据类型 | 49K | String、Hash、List、Set、ZSet 命令与应用 |
| [04](04-高级数据类型.md) | 高级数据类型 | 43K | Bitmap、HyperLogLog、Geospatial、Stream、Bloom Filter |
| [05](05-键管理与通用命令.md) | 键管理与通用命令 | 62K | TTL、过期策略、SCAN、键空间通知 |
| [06](06-持久化.md) | 持久化 | 42K | RDB、AOF、混合持久化、MP-AOF |
| [07](07-内存管理与淘汰策略.md) | 内存管理与淘汰策略 | 57K | 8 种淘汰策略、LRU/LFU、内存碎片、大 Key |
| [08](08-大Key问题.md) | 大 Key 问题 | **41K** | 危害、发现、删除、拆分、预防 |
| [09](09-架构模式.md) | 架构模式 | 42K | 单机/主从/哨兵/Cluster 选型与决策 |
| [10](10-主从复制.md) | 主从复制 | 51K | 全量复制、部分复制、repl_backlog |
| [11](11-哨兵Sentinel.md) | 哨兵 Sentinel | 58K | 故障检测、选主、Raft 选举、自动故障转移 |
| [12](12-Cluster集群.md) | Cluster 集群 | 63K | 16384 slot、故障转移、客户端 MOVED/ASK |
| [13](13-事务与Lua脚本.md) | 事务与 Lua 脚本 | 97K | MULTI/EXEC、WATCH、Lua 原子性 |
| [14](14-缓存设计与常见问题.md) | 缓存设计与常见问题 | 128K | 雪崩/击穿/穿透、Cache Aside、延迟双删 |
| [15](15-分布式锁.md) | 分布式锁 | 80K | SET NX EX、RedLock、Redisson、看门狗 |
| [16](16-性能调优.md) | 性能调优 | 47K | 慢查询、Pipeline、IO 多线程、benchmark |
| [17](17-安全与监控.md) | 安全与监控 | 35K | ACL、TLS、Prometheus+Grafana、告警规则 |

## 知识地图

```text
入门              进阶                  高级                  实战
├─ 01 安装       ├─ 04 高级数据类型    ├─ 10 主从复制        ├─ 14 缓存设计
├─ 02 数据结构   ├─ 06 持久化          ├─ 11 哨兵           ├─ 15 分布式锁
└─ 03 基础类型   ├─ 07 内存管理        ├─ 12 Cluster        └─ 17 安全监控
                 └─ 08 大 Key 问题    ├─ 13 Lua 脚本
                 └─ 05 键管理          └─ 16 性能调优
                                      └─ 09 架构选型
```

## 学习路线建议

### 初学者 (1-2 周)

1. 阅读 01 了解 Redis 是什么、如何安装
2. 学习 02 掌握数据结构底层（SDS、dict、skiplist）
3. 学习 03 掌握五大基础类型的命令和应用
4. 实践 05 键管理与通用命令

### 进阶者 (2-4 周)

1. 学习 04 高级数据类型（Bitmap、Stream、Bloom Filter）
2. 深入 06 RDB/AOF 持久化机制
3. 掌握 07 内存管理与淘汰策略（面试重点）
4. **08 大 Key 问题**（生产必学，避免事故）
5. 理解 09 架构模式，能根据场景选型

### 高级者 (4-8 周)

1. 深入 10 主从复制原理（replid、offset、backlog）
2. 掌握 11 哨兵 Sentinel 故障转移流程
3. 学习 12 Redis Cluster 数据分片与客户端感知
4. 掌握 13 Lua 脚本实现原子操作

### 实战方向

- 重点:14 缓存设计（雪崩/击穿/穿透 + Cache Aside + 延迟双删）
- 必备:15 分布式锁（Redisson 看门狗机制）
- 调优:16 性能调优、17 安全与监控

### 后端开发必读

1. 03 五大基础类型 → 用熟
2. 05 键管理与过期 → 避免 KEYS 等坑
3. 06 持久化 → 理解 RDB/AOF 选型
4. **08 大 Key** → 避免 DEL 阻塞事故
5. 14 缓存设计 → 雪崩击穿穿透
6. 15 分布式锁 → 秒杀场景必备

### 运维 / SRE 必读

1. 01 安装、redis.conf
2. 06 持久化
3. 07 内存管理
4. **08 大 Key** → 紧急删除与监控
5. 09-12 架构（主从/哨兵/Cluster）
6. 16 性能调优
7. 17 安全与监控

## 配套工具推荐

| 工具 | 用途 | 链接 |
|------|------|------|
| RedisInsight | 官方 GUI | https://redis.io/redis-enterprise/redis-insight/ |
| RedisBloom | 布隆过滤器模块 | https://github.com/RedisBloom/RedisBloom |
| Redisson | Java 客户端（分布式锁） | https://redisson.org |
| Lettuce | Java 客户端（响应式） | https://lettuce.io |
| redis-cli | 官方 CLI | 自带 |
| redis_exporter | Prometheus 监控 | https://github.com/oliver006/redis_exporter |
| RedisShake | 数据迁移/同步 | https://github.com/tair-opensource/RedisShake |
| redis-rdb-tools | RDB 分析、大 Key 发现 | https://github.com/sripathikrishnan/redis-rdb-tools |
| Codis | 豌豆荚开源分片集群 | https://github.com/CodisLabs/codis |

## 版本说明

- 主要面向 **Redis 6.x / 7.x**
- 部分内容(ACL、TLS、IO 多线程、Function)需要 **Redis 6.0+**
- Cluster 增强(MP-AOF、自动修复 truncated)需要 **Redis 7.0+**

## Redis 与 MySQL 对照

| 维度 | Redis | MySQL |
|------|-------|-------|
| 类型 | KV 缓存/数据库 | 关系数据库 |
| 存储 | 内存 + 磁盘(持久化) | 磁盘 |
| 查询 | 简单 KV、有限命令 | SQL 完整查询 |
| 事务 | 弱事务 (MULTI/EXEC) | ACID 完整事务 |
| 索引 | 跳表 + 哈希 | B+Tree 多种 |
| 集群 | 原生 Cluster | MHA/MGR/ProxySQL |
| 适用 | 缓存、计数器、分布式锁 | 主业务数据存储 |

## 贡献

发现错误或想补充内容,直接修改对应章节的 md 文件即可。
