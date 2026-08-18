# RedPanda 知识体系

> 按照 [Kafka 文档](../Kafka/) 的章节组织方式编排。RedPanda 是 Kafka API 100% 兼容的高性能消息流平台,采用 C++ + Thread-per-core + 无 GC + 内置 Raft 实现。

## 章节目录

| 章节 | 标题 | 大小 | 主要内容 |
|------|------|------|---------|
| [01](01-RedPanda概述与安装.md) | RedPanda 概述与安装 | 68K | 历史、安装、redpanda.yaml、rpk CLI |
| [02](02-体系结构与核心概念.md) | 体系结构与核心概念 | 66K | Thread-per-core、Seastar 框架、Raft |
| [03](03-与Kafka对比与迁移.md) | 与 Kafka 对比与迁移 | 50K | 兼容性、迁移策略、Shadow Linking |
| [04](04-Topic与集群管理.md) | Topic 与集群管理 | 63K | rpk topic 命令、副本分配、配额 |
| [05](05-Producer与Consumer.md) | Producer 与 Consumer | 66K | 各语言客户端、性能调优、事务 |
| [06](06-存储机制与分层存储.md) | 存储机制与分层存储 | 75K | Segment、Tiered Storage(S3/Azure) |
| [07](07-Raft共识与一致性.md) | Raft 共识与一致性 | 96K | 选举、日志复制、配置变更 |
| [08](08-SchemaRegistry与Wasm.md) | Schema Registry 与 Wasm | 53K | Avro/Protobuf/Rust Wasm 实战 |
| [09](09-安全机制.md) | 安全机制 | 78K | SASL/SCRAM、ACL、mTLS、审计 |
| [10](10-集群部署与扩展.md) | 集群部署与扩展 | 53K | K8s Operator、Shadow Linking、扩容 |
| [11](11-监控与运维.md) | 监控与运维 | 36K | Prometheus、Grafana、告警、容量规划 |
| [12](12-性能调优与可靠性.md) | 性能调优与可靠性 | 53K | 全栈调优、百万 QPS 优化、可靠性 |
| [13](13-常见问题排查.md) | 常见问题排查 | 71K | 故障排查、5+ 实战案例、紧急 Checklist |
| [14](14-实战案例集.md) | 实战案例集 | 24K | 13 个真实场景:Kafka迁移、风控、IoT 等 |

## 知识地图

```text
入门                进阶                       高级                       实战
├─ 01 概述安装     ├─ 04 Topic 管理           ├─ 07 Raft 共识           ├─ 10 集群部署
├─ 02 体系结构     ├─ 05 Producer/Consumer    ├─ 08 SR + Wasm           ├─ 11 监控运维
└─ 03 Kafka对比    ├─ 06 存储与分层           ├─ 09 安全机制            └─ 13 排错
                                              └─ 12 性能调优           └─ 14 实战
```

## RedPanda 核心特色

### 与 Kafka 的核心差异

| 维度 | Kafka | RedPanda |
|------|-------|----------|
| 语言 | Java/Scala | **C++** |
| 模型 | 多线程 + GC | **Thread-per-core + 无 GC** |
| 一致性 | KRaft (3.x) | **内置 Raft (一直)** |
| 依赖 | JVM + ZK/KRaft | **单二进制** |
| 延迟 P99 | 10-100ms | **< 5ms** |
| 吞吐 (同硬件) | 1x | **3-10x** |
| Kafka API | 原生 | **100% 兼容** |
| 资源占用 | 高 (JVM) | **低 (C++)** |
| Tiered Storage | 商业版 (Confluent) | **开源内置** |
| Schema Registry | 商业版 | **开源内置** |
| 流处理 | Kafka Streams | **Wasm Transforms** |

### RedPanda 独有特性

```text
1. 单二进制部署: 无 JVM、无 ZK、无 KRaft 单独进程
2. Thread-per-core: 每个 CPU 核心一个线程,无锁通信
3. 内置 Tiered Storage: S3/Azure/GCS 自动分层
4. 内置 Schema Registry: Avro/Protobuf/JSON Schema
5. Wasm Transforms: 服务端数据处理(Rust/TinyGo)
6. Iceberg Topics: 直接输出 Iceberg 格式到数据湖
7. Shadow Linking: 集群间数据复制(替代 MirrorMaker2)
8. Redpanda Console: 官方 Web UI
9. BSL 许可证: 开源但商业功能受限(类似 Confluent)
```

## 学习路线建议

### 初学者 (1 周)

1. 阅读 01 了解 RedPanda 是什么、如何启动
2. 学习 02 掌握核心架构(thread-per-core、Seastar)
3. 阅读 03 了解与 Kafka 的差异
4. 实战 04 + 05 Topic 与 Producer/Consumer

### 进阶者 (2-3 周)

1. 深入 06 Tiered Storage 工作原理
2. 学习 07 Raft 共识(RedPanda 一致性核心)
3. 学习 08 Schema Registry + Wasm Transform
4. 实战 09 安全机制(SASL/ACL/mTLS)

### 高级者 (4-6 周)

1. 学习 10 集群部署、K8s Operator、Shadow Linking
2. 学习 11 监控运维、容量规划
3. 学习 12 性能调优、百万 QPS 实战
4. 学习 13 排错、14 实战案例

## 配套工具

| 工具 | 用途 | 链接 |
|------|------|------|
| **rpk** | 官方 CLI | Redpanda 自带 |
| **Redpanda Console** | Web UI | https://github.com/redpanda-data/console |
| **Redpanda Operator** | K8s Operator | https://github.com/redpanda-data/redpanda-operator |
| **Terraform Provider** | 基础设施即代码 | https://registry.terraform.io/providers/redpanda-data/redpanda |
| **Kafka Connect** | 数据集成 | Kafka Connect 兼容 |
| **Schema Registry** | Schema 管理 | Redpanda 内置 |

## 选型决策树

```text
你的项目:
├─ 需要超低延迟 (< 10ms P99)?
│   ├─ 是 → RedPanda ✅ (10x 优势)
│   └─ 否 → Q: 现有 Kafka 集群?
│
├─ 现有 Kafka,想平滑迁移?
│   ├─ 是 → RedPanda ✅ (100% API 兼容)
│   └─ 否 → Q: 是否需要内置 Wasm/Tiered Storage?
│
├─ 需要 Wasm Transforms / Tiered Storage?
│   ├─ 是 → RedPanda ✅ (开源内置)
│   └─ 否 → Kafka 也可
│
└─ 强依赖 Confluent 商业功能?
    ├─ 是 → 谨慎评估,部分有对应替代
    └─ 否 → RedPanda 推荐
```

## 版本说明

- 主要面向 **RedPanda v23.x / v24.x**
- BSL 许可证(类似 Confluent): 免费使用,但商业 SaaS 需授权
- 与 Kafka 客户端完全兼容(任何 Kafka 8+ 客户端都可直接连接)

## Kafka vs RedPanda 核心要点

```text
【客户端】
- Kafka 客户端代码无需改动即可连接 RedPanda
- Java spring-kafka、Go sarama、Python kafka-python 全部兼容
- 性能在 RedPanda 上通常 3-10x 提升

【运维】
- RedPanda 单二进制部署(无需 ZK/KRaft)
- 无 JVM,无 GC 调优烦恼
- C++ 进程内存占用稳定
- Thread-per-core 模型对 CPU 核数敏感

【功能】
- Tiered Storage: Kafka 商业版 vs RedPanda 开源
- Schema Registry: Kafka 商业版 vs RedPanda 开源
- 流处理: Kafka Streams vs RedPanda Wasm
- 集群复制: MirrorMaker2 vs Shadow Linking
```

## 贡献

发现错误或想补充内容,直接修改对应章节的 md 文件即可。
