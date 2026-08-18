# RedPanda 与 Kafka 对比及迁移指南

> 本章系统对比 **RedPanda** 与 **Apache Kafka** 在性能、运维、资源、功能、生态、成本等十余个维度的差异,深度剖析 Kafka API 兼容性,梳理 RedPanda 独有特性与不足,并给出完整的迁移策略、实战步骤、兼容性清单,以及决策树。RedPanda 并不是"Kafka 的替代品",而是**用 C++ 重写、并简化架构、追求极致低延迟**的 Kafka 兼容流平台。理解二者的边界,等于掌握下一代流数据平台的选型依据。

---

## 一、为什么需要从 Kafka 迁移到 RedPanda(或反向)

### 1.1 典型的"迁移动机"

迁移不是非黑即白,真实世界里,**迁移方向常常是双向的**:

```text
┌─────────────────────────────────────────────────────────────────┐
│                  迁移决策的真实驱动力                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Kafka → RedPanda                                          │
│    • JVM GC 抖动导致 P99 延迟毛刺                                │
│    • 运维成本高(ZK/KRaft 控制器、Broker 调优)                  │
│    • 资源占用大,小规格集群 CPU/内存被吃光                       │
│    • 想要更简单的部署(单二进制、容器友好)                        │
│    • 想要内建 HTTP Proxy、Schema Registry、Wasm                 │
│    • 想要亚毫秒~5ms P99 延迟                                    │
│                                                                 │
│  RedPanda → Kafka                                          │
│    • 某些 Kafka 高级特性暂未支持 (Streams / Connect 内置)        │
│    • 生态兼容性深度问题(部分 connector、SASL/OAUTHBEARER 场景)  │
│    • 团队已深度绑定 Confluent 商业版                             │
│    • 需要更大规模的离线历史验证                                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 现实主义:大部分场景不需要迁移

> **重要提醒**:Kafka 已经在生产环境验证 13 年,生态成熟、文档丰富、招聘容易。**RedPanda 不是为了"否定"Kafka,而是为了解决 Kafka 在某些场景下的痛点**。如果当前 Kafka 集群运行良好,**没有显著痛点**,不必为了"赶时髦"迁移。

### 1.3 迁移决策的三大判断点

| 判断点 | 倾向 Kafka | 倾向 RedPanda |
|--------|-----------|---------------|
| **延迟敏感性** | P99 < 50ms 可接受 | P99 必须 < 10ms 甚至 < 5ms |
| **运维资源** | 有专职中间件团队 | 想要"少即是多"的运维体验 |
| **生态依赖** | 深度依赖 Kafka Streams / ksqlDB / 大量 Connect | 用 librdkafka 原生客户端、内置能力够用 |

### 1.4 历史背景与设计哲学的差异

理解两者的差异,必须回到它们的设计哲学原点。Kafka 由 LinkedIn 在 2010 年开发,当时的硬件环境是**多核大内存 + 多块普通磁盘 + 万兆网络刚刚兴起**,JVM 是企业 Java 团队最熟悉的技术栈。LinkedIn 的工程师们选择了 Scala/Java,是因为团队熟悉、生态成熟、招聘容易,并且当时对于"流处理"的概念还没有完全成型,Kafka 实际上是被当做一个**分布式持久化日志**来使用的。

RedPanda 由前 LinkedIn 工程师 Alexander Gallego(也曾在 Confluent 担任重要角色)于 2019 年创立。他在 Kafka 一线战斗中遇到了真实的工程痛点:JVM GC 让 P99 延迟无法稳定、ZK 集群是噩梦、运维一个 Kafka 集群需要协调太多组件。基于这些痛点,他选择**用 C++ 20 重写整个系统**,把 Raft 共识直接嵌入 broker,移除所有外部依赖,只留下**单一二进制文件**。这是一种典型的"对前一代系统的不满驱动的下一代架构"的演进,类似于 Elasticsearch → OpenSearch、Log4j → Logback。

这种哲学差异决定了:
- **Kafka 是"集成之王"**:生态深度优先,组件可插拔,Confluent 商业版让一切开箱即用
- **RedPanda 是"单体简化之王"**:把功能内聚到单一二进制,用架构简化换运维简单

### 1.5 行业采用现状

截至 2026 年,**RedPanda 的生产采用仍处于早期主流**。Kafka 在生产环境被广泛使用 13 年,几乎所有大型互联网公司、金融机构、电信运营商都有 Kafka 集群。RedPanda 的客户主要集中在:**金融科技(对延迟极敏感)、游戏行业(玩家操作需毫秒反馈)、SaaS 创业公司(运维人手少)、新型数据栈厂商(追求 Iceberg/数据湖原生集成)**。这并不意味着 RedPanda 不成熟,而是它解决的问题场景相对垂直。

---

## 二、全面对比

### 2.1 一张表看清十大维度

| 维度 | Apache Kafka 3.x | RedPanda 23.x/24.x | 优劣判定 |
|------|-----------------|---------------------|----------|
| **架构核心** | Scala/Java Broker + ZooKeeper 或 KRaft 控制器 | C++20 单二进制 + 内置 Raft 共识 | RedPanda 更简洁 |
| **JVM 依赖** | 必需(JVM + GC 调优) | 无 JVM,纯原生 | RedPanda 无 GC 抖动 |
| **最大吞吐(单节点)** | ~1 GB/s+ (取决于磁盘/网络) | 1+ GB/s,小消息更高 | 接近 |
| **P99 延迟** | 5~50ms(同机房) | < 5ms,典型 1~3ms | RedPanda 胜出 |
| **P999 尾部延迟** | 偶发毛刺明显(GC、ISR 抖动) | 平稳很多 | RedPanda 胜出 |
| **CPU 占用** | JVM + GC,空闲时也吃 CPU | 接近"按用量"计费 | RedPanda 显著省 CPU |
| **内存占用** | JVM Heap + PageCache + Off-Heap | 仅 PageCache + 进程 RSS | RedPanda 更省 |
| **运维复杂度** | 中(ZK 或 KRaft + 多组件) | 低(单二进制 + 内置 Raft) | RedPanda 显著简化 |
| **部署形态** | tarball + systemd / Helm | 单二进制 / Docker / Kubernetes Operator | RedPanda 更易容器化 |
| **Kafka API 兼容** | 原生 | **100% 兼容 Kafka wire protocol** | 平手 |
| **客户端兼容** | 原生 | librdkafka、Java client、Python、Go、Node 等均可直连 | 平手 |
| **Schema Registry** | 需独立部署 Confluent SR | 内置(可选启用) | RedPanda 更省事 |
| **HTTP Proxy** | 需独立部署 REST Proxy | 内置(Redpanda Console + Pandaproxy) | RedPanda 更省事 |
| **Tiered Storage** | KIP-405,3.6+ 逐步 GA,需配 S3 | **一等公民**,默认开启(可选 S3/Azure/GCS) | RedPanda 更成熟 |
| **集群间复制** | MirrorMaker 2(独立组件) | **Shadow Linking**(集群内置) | RedPanda 体验更好 |
| **Iceberg 集成** | 需 Connect + 第三方插件 | **内置**,直接写 Iceberg 表 | RedPanda 胜出 |
| **Wasm transforms** | 无原生,需 Kafka Streams / Flink | **内嵌 Wasm 引擎**,服务端 transform | RedPanda 胜出 |
| **Web UI** | 无官方(第三方 CMAK / AKHQ) | **Redpanda Console** 内置 | RedPanda 更省事 |
| **流处理** | Kafka Streams / ksqlDB / Flink | 无内置流处理引擎 | Kafka 胜出 |
| **数据集成(Connect)** | Kafka Connect,生态极成熟 | 无内置,需外部(Bezium/CDC 工具直连) | Kafka 胜出 |
| **多租户 / 配额** | 完善 | 完善(Kafka 兼容 API) | 平手 |
| **安全** | SASL/SSL/ACL/Kerberos | SASL/SSL/ACL/OAuthbearer,基本对齐 | 平手 |
| **事务 / EOS** | 完善,广泛使用 | 兼容(基于 Kafka 事务协议) | 平手 |
| **压缩算法** | lz4/zstd/gzip/snappy | lz4/zstd/snappy/gzip | 平手 |
| **生态成熟度** | 极高,13 年沉淀 | 中,4~5 年,快速增长 | Kafka 胜出 |
| **文档/社区** | 极丰富 | 较新但质量高 | Kafka 胜出 |
| **招聘市场** | 容易找到 Kafka 工程师 | 相对稀缺 | Kafka 胜出 |
| **商业支持** | Confluent / Cloudera / AWS MSK | Redpanda Data(自家) / 自建 | 平手 |
| **开源协议** | Apache 2.0 | BSL(商业源码许可,看版本)+ 部分组件 Apache | RedPanda 较新时 BSL,部分已改 |
| **TCO 总成本** | 中(硬件 + 运维人力) | 低(资源更省 + 运维更省) | RedPanda 胜出 |

### 2.2 性能对比详解

#### 2.2.1 吞吐量

```text
单节点 1KB 消息批量发送基准(典型值,因环境而异):

Apache Kafka 3.5 (3 节点 KRaft, NVMe, 万兆):
  Producer  吞吐: ~600 MB/s ~ 1 GB/s
  Consumer  吞吐: ~800 MB/s ~ 1.2 GB/s

RedPanda 23.x (3 节点, NVMe, 万兆):
  Producer  吞吐: ~700 MB/s ~ 1.1 GB/s
  Consumer  吞吐: ~900 MB/s ~ 1.4 GB/s
```

**结论**:在大消息(1KB+)批量发送场景,二者吞吐量接近;**小消息(< 200B)、低延迟场景**,RedPanda 优势明显。

#### 2.2.2 延迟

| 场景 | Kafka 3.5 P50 | Kafka 3.5 P99 | RedPanda P50 | RedPanda P99 |
|------|---------------|---------------|--------------|--------------|
| **同机房,1KB 消息,ack=all** | 3~8ms | 15~50ms | 1~3ms | **3~8ms** |
| **跨 AZ,1KB 消息,ack=all** | 8~20ms | 30~100ms | 5~10ms | **15~30ms** |
| **空闲期突刺** | 偶发 200ms+ | (GC、ISR 抖动) | 平滑,几乎无毛刺 | |

**关键洞察**:RedPanda 的**P99 与 P999 优势**远大于 P50 优势。这是**没有 GC** 带来的红利:JVM 在堆大小变更或 Full GC 时会出现长尾,而 C++ 的内存分配器延迟分布稳定得多。

#### 2.2.3 尾部延迟的工程意义

尾部延迟直接影响**用户体验与限流设计**:
- Kafka P99 = 50ms 时,设计 SLA 要按 50ms 留 buffer,长尾会"吃掉"系统容量
- RedPanda P99 = 5ms 时,同样 SLA 可以激进得多,资源利用率更高

### 2.3 资源占用对比

| 资源维度 | Kafka(典型) | RedPanda(典型) | 节省 |
|---------|------------|----------------|------|
| **空载 CPU** | 5~15%(JVM) | < 1% | ~90% |
| **空载内存** | 2~4 GB(JVM Heap + Metaspace) | 200~500 MB | ~85% |
| **满载 CPU** | 30~70% | 25~60% | ~10~20% |
| **满载内存** | 4~16 GB | 1~4 GB | ~60~75% |
| **磁盘 IO 模型** | 顺序写 + 零拷贝 sendfile | 同上 + 线程模型更优 | 类似 |
| **文件数** | 大量(index/log/timeindex 等) | 每个分区一个 segment 文件(简化) | RedPanda 更精简 |

> **运维铁律**:RedPanda 的"低资源占用"在小集群(< 10 节点)上感受最明显;大集群下 Kafka 经过调优后差距缩小,但运维成本仍低于 Kafka。

### 2.4 运维复杂度对比

```text
Kafka 最小生产集群组件:
  ┌─────────────────────────────────────────┐
  │  3 × Broker (KRaft 模式)                │
  │  或 3 × Broker + 3 × Zookeeper (旧)     │
  │  + Schema Registry (独立服务)           │
  │  + REST Proxy (可选)                    │
  │  + Connect Cluster (可选)               │
  │  + CMAK / AKHQ (运维 UI)                │
  │  + Prometheus + Grafana + JMX Exporter  │
  │  + 日志、告警、备份系统                  │
  └─────────────────────────────────────────┘
  → 至少 5~8 个独立服务/进程需要部署、监控、调优


RedPanda 最小生产集群组件:
  ┌─────────────────────────────────────────┐
  │  3 × redpanda (单二进制,内含 Raft 共识) │
  │  + 1 × redpanda-console (Web UI)        │
  │  + Prometheus 指标(内置暴露)             │
  │  + S3/Azure/GCS(Tiered Storage,可选)    │
  └─────────────────────────────────────────┘
  → 单一二进制 + 一个 Console,极大简化部署/扩缩容/升级
```

**运维对比要点**:

| 任务 | Kafka 操作复杂度 | RedPanda 操作复杂度 |
|------|----------------|--------------------|
| **集群扩容** | 改配置 + rebalance + ISR 调整 | rpk cluster grow 一行命令 |
| **版本升级** | 滚动升级 + 协议检查 + JMX 调优 | 滚动替换二进制(API 兼容) |
| **分区再平衡** | 复杂(Kafka 3.6+ 自平衡可缓解) | 内置 Controller 自动均衡 |
| **磁盘扩容** | 增加数据目录 | 支持在线扩容 |
| **节点替换** | 复杂流程 | rpk node decom 一键退役 |

### 2.5 成本对比(Total Cost of Ownership)

| 成本项 | Kafka | RedPanda | 说明 |
|-------|-------|----------|------|
| **硬件** | 高(CPU/内存占用大) | 低(可缩配) | RedPanda 通常可省 30~50% |
| **云资源** | 同上 | 同上 | 公有云上 RedPanda TCO 更低 |
| **运维人力** | 1~2 名 SRE | 0.3~0.5 名 SRE | RedPanda 显著省人力 |
| **培训成本** | 标准生态资料 | 略新,需补充 rpk 文档 | 短期 RedPanda 略高 |
| **商业 License** | Confluent 较贵 | Redpanda Enterprise 略低 | 看具体报价 |

#### 2.5.1 真实 TCO 案例

以一个**中等规模**生产集群为例:**3 节点,每天 500GB 数据流入,保留 7 天**:

```text
Kafka 3 年 TCO 估算:
  硬件(3 × 高配物理机 / 云 VM):  ¥600,000 三年
  运维人力(1 名 SRE 30% 时间):     ¥900,000 三年
  Confluent 商业版(可选):         ¥300,000 三年
  培训/招聘:                      ¥100,000 三年
  合计:                          ¥1,900,000

RedPanda 3 年 TCO 估算:
  硬件(3 × 中配,可缩配):          ¥360,000 三年(节省 40%)
  运维人力(0.3 名 SRE):           ¥270,000 三年(节省 70%)
  Redpanda Enterprise (可选):     ¥200,000 三年
  培训/招聘:                      ¥150,000 三年
  合计:                          ¥980,000

节省: ≈ ¥920,000 (约 48%)
```

> **重要声明**:上述数字为典型场景的粗略估算,实际数字受地区、人力成本、硬件配置、消息速率等因素影响很大,**仅作数量级参考**。

### 2.6 安全模型对比

| 安全维度 | Kafka | RedPanda |
|---------|-------|----------|
| **传输加密(TLS)** | SSL/SASL_SSL | 完整支持 |
| **PLAINTEXT** | 支持 | 支持 |
| **SASL/PLAIN** | 支持 | 支持 |
| **SASL/SCRAM-SHA-256** | 支持 | 支持 |
| **SASL/SCRAM-SHA-512** | 支持 | 支持 |
| **SASL/GSSAPI (Kerberos)** | 完整支持 | **部分支持**,需评估 |
| **SASL/OAUTHBEARER** | 支持 | 支持(23.2+) |
| **ACL** | 完整(基于资源 principal) | 完整,API 兼容 |
| **Quotas** | 完善 | 完善 |
| **审计日志** | 需外部组件 | 集成 Prometheus + 自定义 |
| **静态加密(KMS)** | Confluent 商业 | Redpanda Enterprise |
| **mTLS** | 部分支持 | 支持 |

### 2.7 高可用与灾备对比

| 维度 | Kafka | RedPanda |
|------|-------|----------|
| **副本机制** | Leader-Follower ISR | Raft(每个分区一组 Raft) |
| **最小集群** | 3 节点(Broker)+ 3 ZK 或 3 Controller | 3 节点(单二进制) |
| **故障切换时间** | 几秒到十几秒(Leader 选举) | 亚秒级(Raft 选举) |
| **数据丢失风险** | acks=all 时最小,RPO≈0 | acks=all 时最小,RPO≈0 |
| **跨集群灾备** | MirrorMaker 2 / Replicator | Shadow Linking |
| **跨地域复制** | 支持 | 支持 |
| **滚动升级可用性** | 需精确协议兼容矩阵 | 单二进制更简单 |
| **节点替换** | 复杂流程 | rpk decom 一键退役 |
| **脑裂风险** | KRaft 模式下极低 | 内置 Raft,极低 |

---

## 三、Kafka API 兼容性深度分析

### 3.1 兼容性原则

> **RedPanda 的核心承诺**:**100% 兼容 Kafka wire protocol(截至 Kafka 3.x 主要特性)**。
> 这意味着**几乎所有 Kafka 客户端、生产工具、运维工具都可以不改一行代码直连 RedPanda**。

### 3.2 Kafka 客户端版本兼容性矩阵

| 客户端 | Kafka 原生版本 | RedPanda 兼容性 | 备注 |
|--------|--------------|-----------------|------|
| **Java kafka-clients** 3.0~3.7 | 原生 | **完全兼容** | 主流场景,推荐 |
| **Java kafka-clients** 0.10~2.x | 原生 | **兼容** | 旧项目可直连 |
| **librdkafka**(C/C++/Python/Go/.NET/Rust) | 原生 | **完全兼容** | 性能最佳 |
| **confluent-kafka-python** | 原生 | **完全兼容** | librdkafka wrapper,推荐 |
| **kafka-python** | 原生 | **兼容(需注意兼容性)** | 纯 Python,功能较弱 |
| **Sarama (Go)** | 原生 | **完全兼容** | |
| **confluent-kafka-go** | 原生 | **完全兼容** | librdkafka wrapper |
| **kafka-go (segmentio)** | 原生 | **完全兼容** | 纯 Go |
| **node-rdkafka** | 原生 | **完全兼容** | librdkafka wrapper |
| **kafkajs (Node)** | 原生 | **兼容** | 纯 JS,功能有限 |
| **Spring Kafka** | 原生 | **兼容** | 只需改 bootstrap.servers |
| **Spring Cloud Stream Kafka** | 原生 | **兼容** | 同上 |

### 3.3 Kafka 协议层兼容性

| 协议特性 | Kafka | RedPanda | 兼容性 |
|---------|-------|----------|--------|
| **Produce/Fetch API** | 0~11 | 全部支持 | 完全兼容 |
| **JoinGroup / SyncGroup** | 0~9 | 支持 | 完全兼容 |
| **OffsetCommit / Fetch** | 0~8 | 支持 | 完全兼容 |
| **事务 API**(InitProducerId/AddPartitionsToTxn/EndTxn/TxnOffsetCommit) | 支持 | 支持 | 兼容 |
| **幂等 Producer** | 支持 | 支持 | 兼容 |
| **Admin API**(CreateTopics/DescribeConfigs 等) | 支持 | 支持 | 兼容 |
| **SASL: PLAIN** | 支持 | 支持 | 兼容 |
| **SASL: SCRAM-SHA-256/512** | 支持 | 支持 | 兼容 |
| **SASL: GSSAPI(Kerberos)** | 支持 | 部分支持 | 兼容性弱 |
| **SASL: OAUTHBEARER** | 支持 | 支持(23.2+) | 基本兼容 |
| **ACL API** | 支持 | 支持 | 兼容 |
| **KIP-848 新消费者协议** | 3.7+ 引入 | 跟进中 | 部分支持 |

### 3.4 工具兼容性

| 工具 | 兼容性 | 使用方式 |
|------|--------|---------|
| **kafka-console-producer.sh** | 兼容 | 直接改 bootstrap.servers |
| **kafka-console-consumer.sh** | 兼容 | 直接改 bootstrap.servers |
| **kafka-topics.sh** | 兼容 | 直接改 bootstrap.servers |
| **kcat (kafkacat)** | 兼容 | `-b <redpanda-bootstrap>:9092` |
| **kafkactl** | 兼容 | 同上 |
| **AKHQ** | 兼容 | 配 RedPanda bootstrap |
| **Confluent Control Center** | 部分兼容 | 需注意版本 |
| **KafkaCat (kcat) web UI** | 兼容 | 同上 |
| **Karapace (Schema Registry 替代)** | 完全兼容 | 可替代 Confluent SR |
| **Kafka Offset Explorer / Offset Browser** | 兼容 | 配 bootstrap 即可 |

### 3.5 关键不兼容特性清单

虽然协议层高度兼容,但仍有一些**已知差异**需要在迁移前评估:

| 特性 | Kafka | RedPanda | 影响 |
|------|-------|----------|------|
| **Kafka Streams(嵌入式流处理)** | 原生支持 | **不支持** | 若用 Streams 需保留 Kafka 或换 Flink |
| **Kafka Connect(分布式 ETL 框架)** | 原生支持 | **无内置**,但可独立部署 Connect 连 RedPanda | CDC / Sink 场景需评估 |
| **ksqlDB** | 原生支持 | 不支持 | 同上 |
| **Confluent 商业 Connector 生态** | 完善 | 部分可独立 Connect 集群复用 | 商业组件需许可 |
| **跨集群复制的源端限制** | MM2 可连任意 Kafka | Shadow Linking 源端需 RedPanda(部分版本开始支持从 Kafka 拉取) | 双向复制需注意 |
| **Scram/Mechanism 旧版本** | 0.10 | 略不同 | 老旧客户端需升级 |
| **某些 Confluent 专有格式** | 支持 | 部分不支持 | 极少见 |
| **KIP-848 新消费者协议** | GA | 跟进中 | 新特性暂不可用 |

---

## 四、RedPanda 独有特性

### 4.1 整体特性地图

```text
┌──────────────────────────────────────────────────────────────┐
│                    RedPanda 独有特性                          │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  架构层:                                                     │
│    ✓ 单二进制部署(无 JVM、无 ZK、无 Controller 拆分)         │
│    ✓ 内置 Raft 共识(无需外部协调服务)                        │
│    ✓ C++20 实现(线程模型 + 内存分配器可控)                   │
│                                                              │
│  性能层:                                                     │
│    ✓ P99 < 5ms 端到端延迟                                    │
│    ✓ 极低 CPU/内存占用                                       │
│                                                              │
│  功能层(开箱即用):                                            │
│    ✓ Tiered Storage 一等公民                                 │
│    ✓ Shadow Linking 集群间复制                               │
│    ✓ 内置 Schema Registry                                    │
│    ✓ 内置 HTTP Proxy (Pandaproxy)                            │
│    ✓ Redpanda Console (Web UI)                               │
│    ✓ Wasm transforms 服务端数据处理                          │
│    ✓ Iceberg 集成 (直接写数据湖)                             │
│                                                              │
│  运维层:                                                     │
│    ✓ rpk CLI(运维友好)                                       │
│    ✓ Kubernetes Operator                                     │
│    ✓ 内置 Prometheus 指标                                     │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 4.2 无 ZK / 无 KRaft 控制器:内置 Raft

```text
Kafka 架构(简化):
  ┌────────────┐  ┌────────────┐  ┌────────────┐
  │  Broker 1  │  │  Broker 2  │  │  Broker 3  │
  └────────────┘  └────────────┘  └────────────┘
        │                │               │
        └──── 副本同步 (ISR) ──────────┘
        ▲
        │
  ┌─────────────┐    ┌──────────────┐
  │ ZooKeeper   │ 或 │ KRaft 控制器 │
  │ (集群元数据)│    │ (3 节点)      │
  └─────────────┘    └──────────────┘


RedPanda 架构:
  ┌────────────┐  ┌────────────┐  ┌────────────┐
  │ Redpanda 1 │  │ Redpanda 2 │  │ Redpanda 3 │
  │  + Raft    │  │  + Raft    │  │  + Raft    │
  └────────────┘  └────────────┘  └────────────┘
        └──── 内置 Raft 共识层 ────┘
        (无需任何外部协调服务)
```

**核心优势**:
- 没有 ZooKeeper 集群的运维负担(配置、监控、升级、ZK 抖动)
- 没有 KRaft 控制器 quorum 的额外节点
- 单一部署单元,扩缩容更简单

### 4.3 单二进制部署:无 JVM

```bash
# RedPanda 单二进制部署
wget https://packages.redpanda.com/redpanda/redpanda-latest.repo
yum install redpanda    # 或 apt / docker / k8s operator

# 启动
systemctl start redpanda

# 一条命令搞定: 没有 JVM、没有 heap dump、没有 GC tuning
```

**对比 Kafka**:
- 需要安装 JDK
- 需要调优 GC(G1/ZGC/Shenandoah)
- 需要配 JVM Heap、Metaspace、GC 日志、JFR
- 需要重启时保留 heap dump

### 4.4 极低延迟(< 5ms P99)

**为什么能做到**:
1. **C++ 实现**:无 GC 暂停,内存分配延迟稳定
2. **线程模型优化**:每分区独立 actor,避免锁竞争
3. **io_uring / reactor**:Linux 最新异步 IO(部分场景)
4. **架构精简**:不经过 Controller → Broker 多跳
5. **零拷贝 sendfile**:与 Kafka 同

**典型场景**:
- 金融实时风控:P99 5ms 满足 SLA
- 在线广告竞价:P99 10ms 内必须出价
- 游戏状态同步:玩家操作需 50ms 内反馈
- 实时大屏:毫秒级延迟

### 4.5 内置 Schema Registry(可选)

```bash
# 启用 Schema Registry
rpk cluster config set schema_registry_enable=true

# 客户端使用(confluent-kafka-python 示例)
from confluent_kafka.schema_registry import SchemaRegistryClient
sr = SchemaRegistryClient({'url': 'http://redpanda:8081'})

# 体验与 Confluent SR 完全一致
```

**优势**:
- 无需额外部署 Confluent SR
- 支持 Avro / Protobuf / JSON Schema
- 与 Confluent SR API 完全兼容(可随时替换)

### 4.6 内置 HTTP Proxy

```bash
# 启用 Pandaproxy(HTTP Proxy)
rpk cluster config set pandaproxy_enable=true

# HTTP 端点
POST http://redpanda:8082/topics/my-topic  # 生产消息
GET  http://redpanda:8082/topics/my-topic  # 消费消息
```

**场景**:
- 浏览器/前端直连(避免暴露 Kafka 协议)
- 低吞吐集成场景
- 调试 / 测试

### 4.7 Tiered Storage 一等公民

```text
传统 Kafka:
  磁盘满了 → 删除旧 segment (retention.ms / retention.bytes)
  历史数据无法低成本保留
  Tiered Storage 是 3.6+ 才开始 GA 的特性


RedPanda Tiered Storage:
  热数据(最近 N 小时) → 本地 NVMe
  冷数据(历史数据)   → S3 / Azure Blob / GCS
  ↓
  客户端 Fetch 时自动按 offset 从本地或云端读取
  ↓
  用户视角:日志像无限长,但存储成本可控
```

```bash
# 启用 Tiered Storage
rpk cluster config set cloud_storage_enable=true
rpk cluster config set cloud_storage_bucket=redpanda-logs
rpk cluster config set cloud_storage_region=us-east-1
rpk cluster config set cloud_storage_access_key=...
rpk cluster config set cloud_storage_secret_key=...
```

**核心场景**:
- 法规要求保留 1~7 年
- 业务需要回溯 N 个月前的事件
- 数据湖场景(原始事件长保留)

### 4.8 Shadow Linking(集群间复制)

```text
RedPanda 集群 A                   RedPanda 集群 B
   ┌─────────┐                      ┌─────────┐
   │ Topic X │ ──── Shadow ────────► │ Topic X │
   │ Topic Y │ ──── Shadow ────────► │ Topic Y │
   └─────────┘                      └─────────┘
              ▲
              │ 内置,不需 MirrorMaker 2 独立部署
```

**特性**:
- 单条命令配置:`rpk cluster link create ...`
- 支持主动-被动(灾备)、主动-主动(双活)
- 内置 offset 同步、消费位点同步
- 跨可用区 / 跨地域 / 跨云

### 4.9 Iceberg 集成(数据湖)

```bash
# RedPanda 直接写 Iceberg 表(S3 / Azure)
rpk cluster config set iceberg_enable=true
rpk cluster config set iceberg_bucket=lakehouse
```

**架构**:

```text
业务事件 ─► RedPanda Topic ─► 自动写 Iceberg (S3) ─► Spark/Flink/Trino 即席查询
```

**优势**:
- 不需要 Flink / Spark 写 Iceberg 的中间层
- 流批一体:同一份 Iceberg 数据,流式(RedPanda)与批式(Spark)都可消费
- 节省 CDC 链路复杂度

### 4.10 Wasm Transforms(服务端数据处理)

```rust
// 示例:Wasm transform 处理消息(伪代码)
// 部署到 RedPanda broker 内的 Wasm 引擎
fn transform(event: &[u8]) -> Result<Vec<u8>> {
    let parsed: MyEvent = serde_json::from_slice(event)?;
    let filtered = MyEvent { amount: parsed.amount, .. };
    Ok(serde_json::to_vec(&filtered)?)
}
```

**场景**:
- 服务端过滤(减小下游负载)
- 服务端富化(补字段)
- 服务端脱敏(去掉 PII)
- 服务端聚合(窗口预计算)

### 4.11 Redpanda Console(Web UI)

```bash
# 启动 Redpanda Console
docker run -d -p 80:8080 \
  --name=redpanda-console \
  -e KAFKA_BROKERS=redpanda:9092 \
  docker.redpanda.com/redpandadata/console:latest
```

**功能**:
- Topic 浏览、生产、消费
- Schema Registry 浏览
- Kafka Connect 管理(若独立部署)
- 用户/ACL 管理
- 性能监控

---

## 五、RedPanda 不足

### 5.1 客观不足清单

| 不足 | 影响 | 应对 |
|------|------|------|
| **生态相对较新** | 文档、博客、最佳实践少于 Kafka | 参考官方文档 + 社区 |
| **部分 Kafka 高级特性暂不支持** | Streams / ksqlDB / 内置 Connect 缺失 | 用 Flink、外部 Connect |
| **招聘市场** | 熟悉 RedPanda 工程师少 | 培训现有 Kafka 工程师(2~3 周即可上手) |
| **历史案例** | 大厂生产案例少于 Kafka | 自建 PoC 验证 |
| **某些第三方组件兼容性** | 部分 connector 未经官方测试 | 逐个验证 |
| **商业许可(BSL)** | 早期版本 BSL,限制托管服务商转售 | 关注 License 变化 |
| **Kafka Streams / ksqlDB 替代** | 需用 Flink 或自写流处理 | 团队需有 Flink 能力 |
| **Connect 替代** | 需独立部署 Kafka Connect | 已有 Connect 可复用 |
| **某些 Confluent 商业组件** | Schema Registry Links、Stream Designer 等 | 评估替代方案 |

### 5.2 不适合 RedPanda 的场景

```text
不适合 RedPanda 的典型场景:
  ✗ 深度依赖 Kafka Streams / ksqlDB 的应用
  ✗ 已大规模使用 Confluent 商业版的组织
  ✗ 需要流式 SQL 平台(ksqlDB 风格)
  ✗ 团队对 rpk 不熟悉,且无学习时间
  ✗ 业务对"非 Kafka"的兼容性有强合规要求
```

### 5.3 适合 RedPanda 的场景

```text
适合 RedPanda 的典型场景:
  ✓ 低延迟(P99 < 10ms)实时计算
  ✓ 想要简化运维(无 ZK/Controller)
  ✓ 资源敏感(小集群、低配机器)
  ✓ 需要内置 Schema Registry / HTTP Proxy
  ✓ 需要 Iceberg / 数据湖原生集成
  ✓ 想要 Shadow Linking 简化跨集群复制
  ✓ 全新项目,不绑定历史 Confluent 生态
```

---

## 六、迁移策略

### 6.1 四大迁移策略总览

```text
┌─────────────────────────────────────────────────────────────┐
│                  Kafka ↔ RedPanda 迁移策略                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  策略一: 完全迁移(Replace)                                 │
│    Kafka → RedPanda,弃用 Kafka                             │
│    适用: 新项目、Kafka 痛点显著、团队愿意切换               │
│                                                             │
│  策略二: 共存(Coexistence)                                 │
│    Kafka + RedPanda 并行运行,各管各的 Topic                │
│    适用: 渐进迁移、混合场景                                 │
│                                                             │
│  策略三: 双写(Dual Write)                                  │
│    MirrorMaker2 / Redpanda Shadowing                       │
│    适用: 零停机迁移                                         │
│                                                             │
│  策略四: 临时使用(Adopt)                                   │
│    特定场景用 RedPanda(低延迟新业务),Kafka 保留             │
│    适用: 边缘场景验证                                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 策略一:完全迁移

```text
阶段:
  1. 评估 (1~2 周)
  2. PoC (2~4 周)
  3. 新业务上线 RedPanda (并行运行 1~2 月)
  4. 历史业务逐步迁移 (3~6 月)
  5. Kafka 下线
```

**适用**:新项目、Kafka 痛点显著、团队愿意切换。

### 6.3 策略二:共存

```text
架构:
  ┌─────────────┐         ┌─────────────┐
  │  Kafka      │         │  RedPanda   │
  │  旧业务     │         │  新业务     │
  │  Topic A/B  │         │  Topic X/Y  │
  └─────────────┘         └─────────────┘
         │                       │
         └──── 不互通 / 或双向 MM2 ────┘
```

**适用**:渐进迁移、混合场景。

### 6.4 策略三:双写(MirrorMaker2 + Redpanda Shadowing)

```text
  ┌─────────────┐         ┌─────────────┐
  │  Kafka      │ ──MM2─► │  RedPanda   │
  │  (源)       │ ◄──SL── │  (目标)     │
  └─────────────┘         └─────────────┘
         ▲                       │
         │                       │
         └────── 验证后切换 ──────┘
```

**适用**:零停机迁移、风险可控。

### 6.5 策略四:临时使用(特定场景)

```text
  ┌─────────────┐         ┌─────────────┐
  │  Kafka      │         │  RedPanda   │
  │  主力集群   │         │  低延迟试点 │
  └─────────────┘         └─────────────┘
        ▲                       ▲
        │                       │
     旧业务                  新低延迟业务
```

**适用**:边缘场景验证、PoC。

---

## 七、迁移实战步骤

### 7.1 七步迁移法

```text
  ┌──────────┐    ┌──────────┐    ┌──────────┐
  │ 1.环境评估│ → │ 2.应用改造│ → │ 3.数据迁移│
  └──────────┘    └──────────┘    └──────────┘
                                          │
                                          ▼
  ┌──────────┐    ┌──────────┐    ┌──────────┐
  │ 7.旧集群 │ ← │ 6.切换流量│ ← │ 5.双跑验证│
  │   下线   │    │          │    │          │
  └──────────┘    └──────────┘    └──────────┘
                  4. 验证 + 灰度
```

### 7.2 步骤 1:环境评估(1~2 周)

**评估维度**:

| 维度 | 评估内容 | 工具 |
|------|---------|------|
| **应用数量** | Producer / Consumer 个数 | 代码搜索 |
| **客户端版本** | kafka-clients / librdkafka 版本 | 依赖扫描 |
| **高级特性使用** | Streams / Connect / Transactions | 代码扫描 |
| **Topic规模** | Topic 数 / 分区数 / 消息速率 | JMX / Burrow |
| **数据规模** | 日均 GB / 保留时长 | Burrow / 自建监控 |
| **安全模型** | SASL / ACL / 加密配置 | 配置归档 |
| **跨集群复制** | MM2 / Replicator 配置 | 配置归档 |

**产出**:《迁移评估报告》,列出:
- 可直接迁移的应用(80%+)
- 需要小幅改动的应用
- 无法迁移或迁移成本高的应用(如深度 Streams)

### 7.3 步骤 2:应用改造(基本为零)

> **核心结论**:**Kafka 应用代码几乎零改动**。

```java
// 原 Kafka 配置
spring.kafka.bootstrap-servers=kafka1:9092,kafka2:9092

// 改 RedPanda 配置(只改 bootstrap 地址!)
spring.kafka.bootstrap-servers=redpanda1:9092,redpanda2:9092
```

```python
# confluent-kafka-python
# 原来
producer = Producer({'bootstrap.servers': 'kafka:9092'})
# 改 RedPanda
producer = Producer({'bootstrap.servers': 'redpanda:9092'})
# 其他完全不变
```

**需要改动的罕见场景**:
- SASL/OAUTHBEARER 认证细节
- Kerberos(若 RedPanda 暂不支持)
- 强依赖 Streams 的应用
- 强依赖 Confluent 专有 Connector 的应用

### 7.4 步骤 3:数据迁移

#### 方案 A:MirrorMaker 2(Kafka → RedPanda)

```properties
# mm2.properties
clusters=source,target
source.bootstrap.servers=kafka:9092
target.bootstrap.servers=redpanda:9092

source.client.id=mm2-source
target.client.id=mm2-target

source.security.protocol=SASL_PLAINTEXT
source.sasl.mechanism=SCRAM-SHA-512
source.sasl.jaas.config=...

# 复制哪些 topic
source->target.enabled=true
source->target.topics=.*
```

```bash
# 启动 MM2
kafka-mirror-maker --consumer.config mm2-source.properties \
                  --producer.config mm2-target.properties \
                  --num.streams 8
```

#### 方案 B:Redpanda Shadow Linking(RedPanda → RedPanda)

```bash
# 源集群
rpk cluster link create link-to-target \
  --local-topic '.*' \
  --remote-cluster redpanda-target:9092

# 目标集群
rpk cluster link create link-to-source \
  --local-topic '.*' \
  --remote-cluster redpanda-source:9092
```

#### 方案 C:Confluent Replicator(商业)

若已购买 Confluent 商业版,Replicator 可同时支持 Kafka → Kafka、Kafka → RedPanda、RedPanda → RedPanda。

#### 方案 D:自定义 ETL

```python
# 伪代码:用 Python 桥接
from confluent_kafka import Consumer, Producer

consumer = Consumer({'bootstrap.servers': 'kafka:9092', 'group.id': 'bridge'})
producer = Producer({'bootstrap.servers': 'redpanda:9092'})

consumer.subscribe(['topic-a', 'topic-b'])
while True:
    msg = consumer.poll(1.0)
    if msg:
        producer.produce(msg.topic(), value=msg.value(), key=msg.key())
```

### 7.5 步骤 4~5:双跑验证 + 切换流量

**双跑验证**:

```text
  ┌─────────────┐         ┌─────────────┐
  │  Kafka      │ ──MM2─► │  RedPanda   │
  │  (主)       │ ◄────── │  (备)       │
  └─────────────┘  只读   └─────────────┘
        ▲                       │
        │                       │
        ▼                       ▼
   旧消费者               新消费者(灰度 1% → 10% → 50% → 100%)
```

**验证维度**:
- 消息数量一致(对比 Kafka / RedPanda 消息数)
- 消息内容一致(对比 payload)
- 延迟对比(P50/P99)
- 错误率对比(消费失败率)

### 7.6 步骤 6:切换流量

**灰度切换**:
1. 1% 流量切到 RedPanda
2. 监控 1 天,看错误率、延迟、消息丢失
3. 10% → 50% → 100%
4. 每步观察 1~3 天

**回滚预案**:
- bootstrap.servers 改回 Kafka,5 分钟内回滚

### 7.7 步骤 7:旧集群下线

```text
  1. 确认无生产消费指向 Kafka
  2. 保留 Kafka 集群 7~30 天(观察期)
  3. 导出配置备份(以防审计)
  4. 关闭 Kafka 集群
  5. 释放资源(机器 / 云资源)
```

---

## 八、兼容性问题清单

### 8.1 已知兼容性差异与解决

| 差异 | 影响 | 解决方案 |
|------|------|---------|
| **JMX 指标命名不同** | 监控面板需调整 | RedPanda 暴露 Prometheus 指标,重写 dashboard |
| **Log4j 配置不适用** | 日志格式差异 | RedPanda 默认 yaml 配置,参考 rpk docs |
| **Kafka Streams 不支持** | 流处理代码需重写 | 用 Flink 替代或保留 Kafka 集群 |
| **Kafka Connect 不内置** | CDC 链路需调整 | 独立部署 Connect 集群,连 RedPanda |
| **KSqlDB 不支持** | SQL 流处理不可用 | 用 Flink SQL / 自建 |
| **某些 SASL mechanism 不支持** | 老认证系统需升级 | 升级到 SCRAM/OAUTHBEARER |
| **KIP-848 新消费者协议** | 新特性暂不可用 | 等待 RedPanda 跟进 |
| **Confluent 商业组件** | 商业 License 绑定 | 评估替代或继续付费 |
| **kafka-storage.sh 命令差异** | 运维脚本需调整 | 用 rpk equivalent |
| **特定第三方 connector** | 兼容性需逐个验证 | 参考 RedPanda 兼容性列表 |

### 8.2 迁移前必查清单

```text
  □ 所有 Kafka 客户端版本是否在 RedPanda 兼容列表?
  □ 是否使用了 Kafka Streams / ksqlDB?
  □ 是否使用了 Kafka Connect 内置?
  □ SASL/ACL 配置是否完全兼容?
  □ JMX 指标是否全部迁移到 Prometheus?
  □ 备份恢复流程是否测试?
  □ 跨数据中心复制方案?
  □ 监控告警阈值是否重新校准?
  □ 灾备方案?
  □ 团队培训是否到位(rpk 命令)?
```

---

## 九、Redpanda 数据导入 Kafka 的反向操作

> 反向迁移(Kafka → RedPanda 后再回 Kafka)虽然少见,但有现实场景:RedPanda 某些特性不再满足业务,或团队回归 Confluent 生态。

### 9.1 反向迁移策略

```text
RedPanda → Kafka:
  1. 使用 MirrorMaker 2 (RedPanda 作为 source,Kafka 作为 target)
  2. 使用 Confluent Replicator (支持 RedPanda → Kafka)
  3. 自定义 ETL(类似正向迁移)
```

### 9.2 关键差异

- RedPanda **不实现** Kafka 所有 Admin API(部分管理操作需通过 rpk)
- 部分 Confluent 专有特性一旦在 RedPanda 使用,**反向迁移时无法保留**(例如 Wasm transforms 的产物没有标准 Kafka 表达)
- RedPanda Console 配置需要重新设计

### 9.3 实战步骤

1. 评估 RedPanda 上的专有特性使用量(Wasm / Iceberg / Schema Registry 内置)
2. 评估哪些特性无法迁移到 Kafka
3. 用 MM2 / Replicator 同步数据
4. 灰度切换流量
5. RedPanda 集群保留观察期后下线

---

## 十、Shadow Linking vs MirrorMaker2 对比

### 10.1 功能对比

| 维度 | MirrorMaker 2 | Redpanda Shadow Linking |
|------|---------------|------------------------|
| **架构** | 独立 Connect-like 集群 | RedPanda 内置 |
| **部署复杂度** | 中(独立部署) | 低(rpk 命令) |
| **运维负担** | 中(Kafka Connect 集群) | 低(内置) |
| **配置方式** | properties 文件 | rpk CLI + Admin API |
| **双向复制** | 支持(主动-主动) | 支持 |
| **灾备(主动-被动)** | 支持 | 支持 |
| **跨地域** | 支持 | 支持 |
| **Offset 同步** | 支持 | 支持(更精细) |
| **Schema 同步** | 部分(Schema Registry 需独立) | 内置 Schema Registry |
| **ACL 同步** | 不支持 | 支持 |
| **Topic 配置同步** | 部分 | 更完整 |
| **监控** | JMX / Connect REST | rpk + Admin API |
| **回压** | 无 | 内置流控 |
| **License** | Apache 2.0 | RedPanda 自家(部分 BSL) |
| **成熟度** | 5+ 年 | 2+ 年,快速迭代 |

### 10.2 选型建议

```text
选 MirrorMaker 2 的场景:
  ✓ 已有 Kafka Connect 集群,运维能力强
  ✓ 需要 Apache 2.0 开源协议
  ✓ 跨 Kafka 集群(Kafka → Kafka)复制

选 Redpanda Shadow Linking 的场景:
  ✓ 全栈 RedPanda 部署
  ✓ 想要简化运维(不部署 Connect)
  ✓ 需要 ACL / Schema / Topic 配置同步
  ✓ 需要回压与流控
```

---

## 十一、选型决策树

### 11.1 决策树(ASCII)

```text
                            ┌─────────────────────┐
                            │   是否新项目 /      │
                            │   现有 Kafka 痛点?   │
                            └──────────┬──────────┘
                                       │
                  ┌────────────────────┼────────────────────┐
                  │ Yes                                     │ No
                  ▼                                         ▼
        ┌───────────────────┐                  ┌─────────────────────┐
        │ 是否强依赖        │                  │ 现有 Kafka 集群     │
        │ Streams / ksqlDB?│                  │ 健康、运维稳定       │
        └─────────┬─────────┘                  └──────────┬──────────┘
                  │                                      │
        ┌─────────┴──────────┐                          │
        │ Yes                │ No                       │
        ▼                    ▼                          │
  ┌──────────┐         ┌──────────────┐                  │
  │ 选 Kafka │         │ 评估延迟需求 │                  │
  │ (或 Kafka │         └──────┬───────┘                  │
  │  + Flink)│                │                          │
  └──────────┘         ┌──────┴──────────┐               │
                       │ P99 < 10ms?      │               │
                       └──────┬───────────┘               │
                              │                           │
                    ┌─────────┴─────────┐                 │
                    │ Yes               │ No              │
                    ▼                   ▼                 │
              ┌──────────┐         ┌────────────┐         │
              │ RedPanda │         │ 看运维成本 │         │
              │ 强候选    │         │ 容忍度     │         │
              └──────────┘         └──────┬─────┘         │
                                          │               │
                                ┌─────────┴─────────┐     │
                                │ 低(K8s/小团队)     │     │
                                │ 高(专职 SRE)       │     │
                                ▼                   ▼     │
                          ┌──────────┐         ┌────────┐ │
                          │ RedPanda │         │ Kafka  │ │
                          │ 强候选    │         │ 即可   │ │
                          └──────────┘         └────────┘ │
                                                          │
                                                  ┌───────┴───────┐
                                                  │ 保留 Kafka,    │
                                                  │ 不必迁移      │
                                                  └───────────────┘
```

### 11.2 速查决策矩阵

| 优先级 | 场景 | 建议 |
|--------|------|------|
| **P99 < 5ms 必须** | 金融、广告、游戏 | **RedPanda** |
| **小团队 / 少 SRE** | 创业公司、中小企业 | **RedPanda** |
| **强依赖 Streams / ksqlDB** | 实时计算 | **Kafka** (+ Flink) |
| **大规模 Connect 生态** | CDC、ETL 重度 | **Kafka** |
| **大量 Confluent 商业组件** | 已付费 | **Kafka** (或评估迁移 ROI) |
| **新项目、无历史负担** | 全新业务 | **RedPanda** (或 Kafka,看团队) |
| **云上 Serverless 体验** | 不想管集群 | **MSK / Confluent Cloud / Redpanda Cloud** |
| **资源极度敏感** | 边缘、嵌入式 | **RedPanda** |
| **跨云/混合云** | 多云部署 | **两者皆可**,看具体痛点 |

---

## 十二、核心要点速记

- **RedPanda 不是 Kafka 的替代品**,而是用 **C++ 重写、架构简化、追求低延迟**的 Kafka 兼容流平台;Kafka API 100% 兼容,客户端可零修改直连。
- **核心优势**:**单二进制(无 JVM)、内置 Raft(无 ZK/KRaft Controller)、P99 < 5ms 延迟、CPU/内存占用显著更低、运维极简**。
- **核心差异**:**无 Kafka Streams / ksqlDB / 内置 Connect**;若重度使用,需保留 Kafka 或换 Flink 替代。
- **独有特性**:**Tiered Storage 一等公民**、**Shadow Linking 集群间复制**、**内置 Schema Registry / HTTP Proxy**、**Wasm transforms**、**Iceberg 集成**、**Redpanda Console Web UI**。
- **性能对比**:**P99 延迟** RedPanda 显著胜(< 5ms vs 15~50ms);**P999 尾部** 因无 GC,RedPanda 更稳定;**吞吐量** 大消息批量场景接近。
- **资源对比**:**空载 CPU/内存** RedPanda 省 80~90%;**满载** 仍省 10~30%;小集群感受最明显。
- **迁移决策三大判断点**:**延迟敏感性、运维资源、生态依赖**;没有显著痛点不必迁移。
- **迁移策略四类**:**完全迁移、共存、双写(MM2 + Shadowing)、临时使用**;**零停机迁移首选双写**。
- **七步迁移法**:**环境评估 → 应用改造(基本为零) → 数据迁移(MM2/Shadowing/Replicator) → 双跑验证 → 切换流量(灰度) → 旧集群下线**。
- **兼容性问题关键**:**JMX 指标差异**、**Kafka Streams 不支持**、**Kafka Connect 不内置**、**某些 SASL mechanism 弱支持**、**KIP-848 新协议跟进中**。
- **MirrorMaker 2 vs Shadow Linking**:**MM2 成熟开源**、需独立 Connect 集群;**Shadow Linking 内置简化**、支持 ACL/Schema 同步、流控,但相对较新。
- **反向迁移(RedPanda → Kafka)** 可行但需评估专有特性(Wasm/Iceberg)无法保留;用 MM2 或 Replicator 同步数据。
- **选型铁律**:**P99 < 10ms / 资源敏感 / 想要少运维 → RedPanda**;**强依赖 Streams/ksqlDB/Connect 生态 → Kafka**;**新项目无历史负担 → 两者皆可,看团队偏好**。
- **典型成熟场景**:RedPanda 适合**低延迟实时计算(广告竞价、风控、游戏状态同步)、资源敏感部署(边缘、小集群)、数据湖原生集成(Iceberg)、跨集群复制(Shadow Linking)**。
- **不推荐 RedPanda 的场景**:**强依赖 Streams/ksqlDB、深度 Confluent 商业组件、要求 Apache 2.0 全开源、团队完全没接触过 RedPanda 且时间紧**。
- **最终建议**:**永远先 PoC 验证**;迁移是工程问题,不是信仰问题;**能用 Kafka 客户端直连**是 RedPanda 最大的诚意,也是迁移最大的底气。

> RedPanda 与 Kafka 的关系,类似于 **InnoDB 与 MySQL** —— 协议兼容,但内核重写、追求极致。理解二者边界,掌握迁移方法论,根据业务痛点做选择,而不是盲目跟风,才是工程上正确的姿势。