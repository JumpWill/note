# Kafka 知识体系

> 按照 [MySQL 文档](../../数据库/MySQL/) 的章节组织方式编排。涵盖 Kafka 从入门到精通的完整知识体系。
>
> Kafka 3.x 主推 **KRaft 模式**(取代 ZooKeeper),文档以 KRaft 模式为主,旧 ZK 模式作为补充。

## 章节目录

| 章节 | 标题 | 大小 | 主要内容 |
|------|------|------|---------|
| [01](01-Kafka概述与安装.md) | Kafka 概述与安装 | 79K | 历史、安装、KRaft 启动、server.properties、CLI 工具 |
| [02](02-体系结构.md) | 体系结构 | 59K | Broker/Topic/Partition、Replica、ISR、KRaft vs ZK |
| [03](03-Topic与分区.md) | Topic 与分区 | 50K | kafka-topics.sh、Segment、副本分配、扩容 |
| [04](04-Producer详解.md) | Producer 详解 | 52K | 发送流程、ACK、幂等、事务、分区器 |
| [05](05-Consumer详解.md) | Consumer 详解 | 70K | 消费组、Offset、Rebalance、订阅、并发 |
| [06](06-存储机制.md) | 存储机制 | 79K | Segment、索引、Zero Copy、Retention、压缩 |
| [07](07-副本机制与ISR.md) | 副本机制与 ISR | 59K | Leader/Follower、ISR、HW/LEO、Leader Epoch |
| [08](08-KRaft一致性协议.md) | KRaft 一致性协议 | 73K | Raft 选举、Controller Quorum、ZK 迁移 |
| [09](09-可靠性与一致性保证.md) | 可靠性与一致性 | 72K | 三种语义、幂等、事务、EOS 端到端 |
| [10](10-性能调优.md) | 性能调优 | 43K | Broker/Producer/Consumer/JVM/OS 全栈调优 |
| [11](11-安全机制.md) | 安全机制 | 61K | SASL/SCRAM、ACL、SSL、KRaft 安全 |
| [12](12-生态与集成.md) | 生态与集成 | 62K | Kafka Connect、Streams、Schema Registry、MM2 |
| [13](13-监控与运维.md) | 监控与运维 | 83K | kafka_exporter、Lag、Prometheus、运维操作 |
| [14](14-集群部署与扩展.md) | 集群部署与扩展 | 44K | KRaft 集群、扩容、跨 DC、ZK 迁移 |
| [15](15-常见问题排查.md) | 常见问题排查 | 62K | 各类故障排查、紧急 Checklist |
| [16](16-实战案例集.md) | 实战案例集 | 59K | 12 个真实场景:行为采集、订单、CDC 等 |

## 知识地图

```text
入门                进阶                       高级                       实战
├─ 01 概述安装     ├─ 04 Producer              ├─ 07 副本与 ISR           ├─ 10 性能调优
├─ 02 体系结构     ├─ 05 Consumer              ├─ 08 KRaft               ├─ 13 监控运维
└─ 03 Topic 分区   ├─ 06 存储机制              ├─ 09 可靠性 EOS           ├─ 15 排错
                                            └─ 11 安全                └─ 16 实战
                                            └─ 12 生态
                                            └─ 14 集群部署
```

## 核心架构

### Kafka 2.x vs 3.x

```text
Kafka 2.x:
   Producer/Consumer → Broker → ZooKeeper
                                ↑
                          元数据存储
                          Controller 选举

Kafka 3.x (KRaft):
   Producer/Consumer → Broker ⇄ KRaft Controller Quorum
                                ↑
                          内置元数据日志
                          无 ZK 依赖
                          性能更好,运维更简单
```

### 一条消息的生命周期

```text
1. Producer 创建 Record,经序列化/分区
2. Producer 批量发送到 Broker Leader
3. Leader 写入 Page Cache + 顺序写盘
4. Follower 从 Leader fetch 数据
5. ISR 全部同步后,消息被认为已提交
6. Consumer poll 拉取消息
7. Consumer 处理后提交 Offset
8. Offset 存储到 __consumer_offsets
```

## 学习路线建议

### 初学者 (1-2 周)

1. 阅读 01 了解 Kafka 是什么、如何启动 KRaft 集群
2. 学习 02 掌握核心架构 (Broker/Topic/Partition/Replica)
3. 学习 03 Topic/分区管理,会用 kafka-topics.sh
4. 实践 04 + 05 Producer 与 Consumer 基础使用

### 进阶者 (2-4 周)

1. 深入 06 存储机制,理解 Segment/索引/Zero Copy
2. 学习 07 副本机制,理解 ISR/HW/Leader Epoch
3. 学习 08 KRaft 协议原理与运维
4. 理解 09 三种消息传递语义,掌握幂等与事务

### 高级者 (4-8 周)

1. 学习 10 性能调优,掌握 Producer/Consumer/JVM/OS 全栈
2. 学习 11 安全机制,部署生产级安全
3. 学习 12 Kafka Streams/Connect,做流处理
4. 学习 13-14 监控告警、集群扩缩容、ZK 迁移

### 实战方向

- 重点:09 可靠性保证、10 性能调优
- 必备:13 监控运维、15 排错
- 进阶:14 集群部署、16 实战案例

## 配套工具推荐

| 工具 | 用途 | 链接 |
|------|------|------|
| **Apache Kafka** | 消息队列本体 | https://kafka.apache.org |
| **Confluent Platform** | 商业版增强 | https://www.confluent.io |
| **Kafka Connect** | 数据集成 (JDBC/Debezium) | https://docs.confluent.io/platform/current/connect |
| **Kafka Streams** | 轻量级流处理 | https://kafka.apache.org/documentation/streams |
| **Debezium** | CDC (MySQL/PG/Mongo → Kafka) | https://debezium.io |
| **Schema Registry** | Schema 管理 | https://docs.confluent.io/platform/current/schema-registry |
| **MirrorMaker 2** | 跨集群复制 | Kafka 内置 |
| **kafka_exporter** | Prometheus 监控 | https://github.com/danielqsj/kafka_exporter |
| **Burrow** | Consumer Lag 监控 | https://github.com/linkedin/Burrow |
| **AKHQ** | 集群管理 Web UI | https://github.com/tchiotludo/akhq |
| **KafkaUI** | 集群管理 Web UI | https://github.com/provectus/kafka-ui |

## Kafka 与其他消息队列对比

| 维度 | Kafka | RabbitMQ | RocketMQ | Pulsar |
|------|-------|----------|----------|--------|
| 吞吐 | **百万级/s** | 万级/s | 十万级/s | 百万级/s |
| 延迟 | 10-100ms | 微秒级 | 10-50ms | 10-50ms |
| 消息模型 | 拉模式 (Pull) | 推模式 (Push) | 推拉结合 | 推拉结合 |
| 顺序保证 | 分区内有序 | 队列内有序 | 队列内有序 | 分区有序 |
| 消息回溯 | ✅ Offset 任意位置 | ❌ 需插件 | ✅ 按时间 | ✅ |
| 多消费 | ✅ 消费组 | ❌ | ✅ | ✅ |
| 事务 | ✅ EOS | ✅ AMQP TX | ✅ | ✅ |
| 一致性协议 | KRaft/Raft | 镜像队列 | Raft | BookKeeper |
| 运维复杂度 | 中 | 低 | 中 | 高 |

## 版本说明

- 主要面向 **Kafka 3.x** (KRaft 模式生产可用,3.3+ GA)
- Kafka 4.x 已规划,继续强化 KRaft 取代 ZK
- 部分内容(Streams、Connect)Kafka 2.x 也适用

## 核心要点速记

- **Kafka** = 分布式、持久化、高吞吐的发布订阅消息系统
- **KRaft** (Kafka 3.x) = 取代 ZooKeeper,内部 Raft 协议管理元数据
- **Topic** = 消息分类,**Partition** = 物理分片,**Replica** = 副本
- **Producer** 三种 ACK:0 (丢) / 1 (Leader 写即返) / all (ISR 全同步)
- **Consumer Group**: 组内分区互斥,组间独立消费
- **ISR** (In-Sync Replicas): 与 Leader 保持同步的副本集合
- **幂等 Producer**: PID + Sequence Number 去重
- **事务 Producer**: 跨分区原子写,需配合 read_committed 消费者
- **EOS**: 端到端精确一次 = 幂等 + 事务 + 业务幂等
- **Offset**: 存储在 `__consumer_offsets` topic (内部 topic)
- **Segment**: log 文件按大小/时间滚动,稀疏索引二分查找
- **Zero Copy**: sendfile 系统调用,减少用户态-内核态数据拷贝
- **min.insync.replicas**: ISR 最少副本数,数据可靠性底线

## 贡献

发现错误或想补充内容,直接修改对应章节的 md 文件即可。
