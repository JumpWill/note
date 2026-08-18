# Topic 与分区 (Topic & Partition)

Topic 和 Partition 是 Kafka 中最核心的两个概念。Topic 是消息的逻辑分类,Partition 是 Topic 的物理分片,所有读写、并行、副本、扩展能力都建立在 Partition 之上。本章从概念到命令、从原理到实战,完整讲解 Topic 与 Partition 的全部细节。

---

## 一、Topic 概念详解

### 1. 什么是 Topic

在 Kafka 中,**Topic(主题)** 是消息的逻辑分类,等价于 MySQL 中"表"的概念,但是面向消息流。

- **生产端**:向 Topic 发送消息
- **消费端**:从 Topic 订阅消息
- **Broker**:实际存储 Topic 的物理数据
- **逻辑分层**:Topic 是逻辑层,Partition 是物理层,一个 Topic 由 N 个 Partition 组成

### 2. Topic 的本质

Topic 并不是一个文件或者一个目录。它是一组 Partition 的逻辑集合,每个 Partition 才是真实落在磁盘上的物理文件集合。

```text
Topic (逻辑)        Partition (物理)        磁盘文件
─────────────────────────────────────────────────────
order-topic         └── Partition 0         /kafka-logs/order-topic-0/
                    └── Partition 1         /kafka-logs/order-topic-1/
                    └── Partition 2         /kafka-logs/order-topic-2/
```

### 3. Topic 与消息系统的类比

| 概念         | MySQL              | Kafka                | RabbitMQ            |
|--------------|--------------------|----------------------|---------------------|
| 逻辑容器     | database + table   | topic                | exchange + queue    |
| 物理分片     | 数据文件 / 分区    | partition            | mirror queue        |
| 投递模型     | 拉(Pull)          | 拉(Pull)            | 推(Push) / 拉(Pull) |
| 消费模式     | 一次性查询         | 多消费者多次消费     | 一次性消费(可持久)  |
| 顺序保证     | 弱                 | 分区内强顺序         | 队列内强顺序        |

### 4. Topic 的特性

- **多订阅者**:一个 Topic 可以被多个消费者组独立消费,每个消费者组都消费到全量数据
- **持久化**:消息按 retention 策略持久化到磁盘(默认 7 天)
- **可扩展**:通过增加 Partition 提升并行度
- **可备份**:通过 replication.factor 配置副本数
- **顺序保证**:仅在**单个 Partition 内**保证消息顺序,跨 Partition 不保证

---

## 二、Topic 创建与管理(kafka-topics.sh 完整命令)

Kafka 提供 `kafka-topics.sh` 脚本(新版也叫 `kafka-topics.sh` 或 `kafka-topics`)统一管理 Topic,所有操作都通过该脚本完成。

### 1. 创建 Topic(--create)

```bash
# 最简形式:默认副本 1、分区 1
kafka-topics.sh --bootstrap-server localhost:9092 \
  --create --topic order-topic

# 完整形式:指定分区数、副本数、配置项
kafka-topics.sh --bootstrap-server localhost:9092 \
  --create --topic order-topic \
  --partitions 3 \
  --replication-factor 2 \
  --config retention.ms=604800000 \
  --config compression.type=producer \
  --config min.insync.replicas=2 \
  --config cleanup.policy=delete
```

参数说明:

| 参数                | 含义                              | 是否必填      |
|---------------------|-----------------------------------|---------------|
| `--bootstrap-server`| Kafka 集群地址                    | 必填          |
| `--topic`           | Topic 名称(非法字符:空格、`+`、`,`) | 必填          |
| `--partitions`      | 分区数,默认 1                     | 否            |
| `--replication-factor` | 副本数,默认 1                  | 否            |
| `--config`          | 自定义配置项,可写多个             | 否            |
| `--if-not-exists`   | 已存在则不报错(2.5+ 支持)         | 否            |

### 2. 查看 Topic 列表(--list)

```bash
# 列出所有 Topic
kafka-topics.sh --bootstrap-server localhost:9092 --list

# 列出匹配指定前缀的 Topic
kafka-topics.sh --bootstrap-server localhost:9092 --list \
  --exclude-internal

# 过滤 Topic
kafka-topics.sh --bootstrap-server localhost:9092 --list \
  | grep "^order"
```

输出示例:

```text
__consumer_offsets
__transaction_state
order-topic
payment-topic
user-topic
```

> 注意:以 `__` 双下划线开头的 Topic 是 Kafka 内部 Topic(`__consumer_offsets` 存储消费者位移、`__transaction_state` 存储事务状态),一般不要手动删除。

### 3. 查看 Topic 详情(--describe)

```bash
# 查看单个 Topic
kafka-topics.sh --bootstrap-server localhost:9092 \
  --describe --topic order-topic

# 查看所有 Topic
kafka-topics.sh --bootstrap-server localhost:9092 --describe

# 查看副本所在 broker
kafka-topics.sh --bootstrap-server localhost:9092 \
  --describe --topic order-topic --replication-factor 3
```

输出示例:

```text
Topic: order-topic    PartitionCount: 3    ReplicationFactor: 2    Configs:
    Topic: order-topic    Partition: 0    Leader: 1    Replicas: 1,2    Isr: 1,2
    Topic: order-topic    Partition: 2    Leader: 2    Replicas: 2,3    Isr: 2,3
    Topic: order-topic    Partition: 1    Leader: 3    Replicas: 3,1    Isr: 3,1
```

字段解读:

| 字段              | 含义                                                |
|-------------------|-----------------------------------------------------|
| `Topic`           | Topic 名称                                          |
| `PartitionCount`  | Partition 总数                                      |
| `ReplicationFactor`| 副本因子(配置,实际副本数看 Replicas)              |
| `Partition`       | 分区号                                              |
| `Leader`          | 该分区的 Leader 副本所在的 Broker id                |
| `Replicas`        | 该分区的所有副本所在 Broker id 列表(含 Leader)      |
| `Isr`             | In-Sync Replicas 同步副本集合(已追上 Leader 的副本) |

### 4. 修改 Topic(--alter)

```bash
# 修改分区数(只能增加,不能减少)
kafka-topics.sh --bootstrap-server localhost:9092 \
  --alter --topic order-topic --partitions 6

# 修改配置项
kafka-topics.sh --bootstrap-server localhost:9092 \
  --alter --topic order-topic \
  --config retention.ms=1209600000 \
  --config max.message.bytes=2097152

# 删除某个配置项(回退到 broker 配置)
kafka-topics.sh --bootstrap-server localhost:9092 \
  --alter --topic order-topic \
  --delete-config retention.ms
```

> 注意:partition 数**只能增加不能减少**,减少分区会丢数据,Kafka 直接不支持。

### 5. 删除 Topic(--delete)

```bash
# 删除 Topic(需要 broker 端 delete.topic.enable=true)
kafka-topics.sh --bootstrap-server localhost:9092 \
  --delete --topic order-topic

# 删除多个 Topic
kafka-topics.sh --bootstrap-server localhost:9092 \
  --delete --topic order-topic --topic payment-topic
```

底层流程:

```text
1. 客户端发起删除请求
2. Controller 在 __consumer_offsets 标记该 Topic 为删除状态
3. 关闭所有客户端连接
4. 向所有 broker 发送 StopReplica 请求
5. 删除 broker 磁盘上的 /kafka-logs/order-topic-* 目录
6. 从元数据中移除 Topic
```

> **生产警告**:删除 Topic 是一个**不可逆的高危操作**,务必先确认无业务依赖,或在低峰期执行。

### 6. 增加分区数(--alter --partitions)

```bash
kafka-topics.sh --bootstrap-server localhost:9092 \
  --alter --topic order-topic --partitions 12
```

增加分区的影响(详见第八节):

- **哈希分区键失效**:旧分区的消息不会重新分布,新消息按新分区数重新 hash
- **消费者重新分配**:新增分区的消费需要重新触发 Rebalance
- **消息顺序**:同一个 key 的消息可能从"一个分区"变成"两个分区",顺序保证失效

---

## 三、Topic 配置项详解

Topic 维度的配置优先级高于 Broker 全局配置,所有配置都可以通过 `--config` 在创建或修改时设定。

### 1. 必知配置项

| 配置项                     | 默认值              | 含义                                             |
|----------------------------|---------------------|--------------------------------------------------|
| `num.partitions`           | 1                   | 自动创建 Topic 时的默认分区数                    |
| `default.replication.factor` | 1                 | 自动创建 Topic 时的默认副本数                    |
| `retention.ms`             | 604800000 (7 天)    | 消息保留时间,超时删除                            |
| `retention.bytes`          | -1 (无限制)         | 单分区最大字节数,超过则删除旧消息                |
| `segment.ms`               | 604800000 (7 天)    | Segment 文件最大存活时间                         |
| `segment.bytes`            | 1073741824 (1G)     | Segment 文件最大字节数                           |
| `compression.type`         | producer            | 压缩类型:none / gzip / snappy / lz4 / zstd       |
| `cleanup.policy`           | delete              | 清理策略:delete / compact / delete,compact       |
| `min.insync.replicas`      | 1                   | 最小同步副本数(与 acks=all 配合)                |
| `max.message.bytes`        | 1048588 (~1MB)      | 单条消息最大字节数                               |
| `message.timestamp.type`   | CreateTime          | 消息时间戳类型                                   |
| `preallocate`              | false               | 是否预分配 Segment 文件                          |
| `index.interval.bytes`     | 4096                | 索引项间隔,越小查询越快,索引越大                 |

### 2. 关键配置详解

#### (1) retention.ms——消息保留时间

```bash
# 保留 1 小时
kafka-topics.sh --bootstrap-server localhost:9092 \
  --alter --topic order-topic --config retention.ms=3600000

# 保留 30 天
kafka-topics.sh --bootstrap-server localhost:9092 \
  --alter --topic order-topic --config retention.ms=2592000000
```

判断标准:

- **流式日志 / 监控埋点**:retention.ms 较短(几小时到几天)
- **业务事件 / 订单数据**:retention.ms 较长(7~30 天)
- **变更日志(CDC)**:配合 `cleanup.policy=compact` 做 key 合并

#### (2) cleanup.policy——清理策略

```bash
# 仅基于时间/大小删除
kafka-topics.sh --bootstrap-server localhost:9092 \
  --alter --topic order-topic --config cleanup.policy=delete

# 仅做 key 合并
kafka-topics.sh --bootstrap-server localhost:9092 \
  --alter --topic user-topic --config cleanup.policy=compact

# 两者都启用
kafka-topics.sh --bootstrap-server localhost:9092 \
  --alter --topic user-topic --config cleanup.policy=delete,compact
```

三种模式:

| 模式              | 适用场景         | 行为                                 |
|-------------------|------------------|--------------------------------------|
| `delete`          | 绝大多数业务     | 超时 / 超大就删                       |
| `compact`         | 维度表、配置表   | 同一个 key 只保留最新值              |
| `delete,compact`  | 混合场景         | 先 delete,后 compact                  |

#### (3) min.insync.replicas——最小同步副本

```bash
kafka-topics.sh --bootstrap-server localhost:9092 \
  --alter --topic order-topic --config min.insync.replicas=2
```

配合 `acks=all` 使用,保证至少有 2 个副本写入成功才算消息成功。这是**数据不丢的最低保障**。

```text
replication.factor=3
min.insync.replicas=2
acks=all

含义:3 个副本,写入时至少等 2 个副本同步成功,即使 Leader 挂掉,还有 1 个 ISR 能顶上。
```

#### (4) compression.type——压缩算法

| 算法    | 压缩比 | CPU 占用 | 适用场景                |
|---------|--------|----------|-------------------------|
| none    | 1.0    | 最低     | 默认,日志无需压缩       |
| gzip    | 高     | 高       | 文本 / JSON             |
| snappy  | 中     | 低       | Google 出品,通用首选    |
| lz4     | 中     | 极低     | 追求写入吞吐            |
| zstd    | 高     | 低       | Facebook 出品,新首选    |

推荐:线上通用选 `zstd` 或 `lz4`,既能省磁盘带宽又不会过多消耗 CPU。

#### (5) max.message.bytes——单条消息最大字节

```bash
# 允许单条消息最大 10MB
kafka-topics.sh --bootstrap-server localhost:9092 \
  --alter --topic order-topic --config max.message.bytes=10485760
```

> 注意:这个值需要与 Broker 端的 `message.max.bytes`(默认 1MB)保持协调,否则会被 Broker 拒收。

### 3. 完整配置示例

```bash
# 生产环境推荐配置
kafka-topics.sh --bootstrap-server localhost:9092 \
  --create --topic order-topic \
  --partitions 12 \
  --replication-factor 3 \
  --config retention.ms=604800000 \
  --config compression.type=zstd \
  --config cleanup.policy=delete \
  --config min.insync.replicas=2 \
  --config max.message.bytes=2097152 \
  --config segment.bytes=536870912 \
  --config segment.ms=604800000 \
  --config message.timestamp.type=CreateTime
```

---

## 四、Partition 分区详解

### 1. 什么是 Partition

**Partition(分区)** 是 Topic 的物理分片,一个 Topic 可以有多个 Partition,每个 Partition 是一个有序、不可变的消息队列。

- **顺序写**:新消息只能追加到 Partition 末尾
- **有序**:每条消息拥有一个单调递增的 Offset(偏移量)
- **不可变**:消息一旦写入,不能修改,只能删除(retention 到期)
- **物理独立**:每个 Partition 在磁盘上是一组独立文件

### 2. 分区的作用

#### (1) 并行(Parallelism)

不同 Partition 可以被不同 Consumer 同时消费,这是 Kafka 高吞吐的根源。

```text
Topic: order-topic (4 partitions)

Producer
   │
   ▼
┌──────┬──────┬──────┬──────┐
│ P0   │ P1   │ P2   │ P3   │
└─┬────┴─┬────┴─┬────┴─┬────┘
  │      │      │      │
  ▼      ▼      ▼      ▼
 C1     C2     C3     C4     ← 4 个消费者并行消费
```

#### (2) 扩展(Scalability)

单 Broker 的磁盘和带宽有限,Partition 数量越多,数据可以被分散到多个 Broker 上,提升整体 IO 吞吐。

#### (3) 故障隔离

单个 Partition 损坏不会影响其他 Partition 的读写。

#### (4) 顺序保证

**仅在单个 Partition 内保证消息顺序**。如果业务要求全局顺序,只能使用 1 个 Partition。

### 3. 分区与消费者的关系

| 消费者数 vs 分区数 | 行为                                       |
|--------------------|--------------------------------------------|
| 消费者 < 分区      | 部分消费者消费多个 Partition,空闲浪费     |
| 消费者 = 分区      | 一对一,最理想                             |
| 消费者 > 分区      | 多余消费者空闲(不会重复消费)             |

**关键原则**:单个 Partition 只能被同一个 Consumer Group 内的**一个消费者**消费。这是 Kafka 并行消费的硬约束。

```text
Consumer Group: order-group

8 partitions × 3 consumers

P0 ──► C1
P1 ──► C1
P2 ──► C2
P3 ──► C2
P4 ──► C3
P5 ──► C3
P6 ──► (空闲,会触发 Rebalance)
P7 ──► (空闲,会触发 Rebalance)
```

### 4. 分区数选择策略

分区数是 Topic 设计中最关键的决策,没有"标准答案",但有**计算公式**。

#### (1) 经验公式

```text
分区数 = max(生产者吞吐需求, 消费者吞吐需求) / 单分区吞吐上限
```

| 维度              | 参考值                                       |
|-------------------|----------------------------------------------|
| 单分区写入上限    | 10~30 MB/s (取决于硬件和压缩)              |
| 单分区消费上限    | 10~50 MB/s (取决于消费逻辑)                |
| 单分区消息 TPS    | 1万~5万/s                                    |

#### (2) 业务案例

```text
场景:订单 Topic,峰值 10 万 TPS,单分区上限 3 万 TPS

理论分区数 = 100000 / 30000 = 3.3  → 取 4

考虑未来 3 倍增长: 4 × 3 = 12
考虑消费者并行: 12 消费者容易凑齐,推荐 12

最终取: 12 个分区, 3 个副本
```

#### (3) 选择原则

| 原则                           | 说明                                              |
|--------------------------------|---------------------------------------------------|
| **宁多勿少,但不滥用**           | 增加分区相对简单,减少分区不可行                  |
| **预留 2~3 倍扩展空间**         | 业务增长后再扩容代价大                            |
| **分区数 ≤ Broker 数 × 100**    | 单机太多分区会影响 Controller 内存               |
| **保持均衡**                    | 各分区负载应尽量均衡,避免倾斜                    |
| **不能太多**                    | 太多分区 = 太多文件句柄 + Rebalance 慢            |

#### (4) 计算公式落地

```text
kafka_partition_size = (target_throughput_MB_per_sec × retention_days × 86400) / (replication_factor × disk_count)

其中:
  target_throughput_MB_per_sec: 业务峰值吞吐
  retention_days: 保留天数
  replication_factor: 副本数
  disk_count: 每台 broker 的磁盘数(SSD 算 1 块)

如果单分区 ≤ 1GB(理想),反推分区数 = total_size / 1GB
```

#### (5) 消费者角度补充

```text
分区数 = max(生产者所需, 消费者所需)

消费者所需 = 期望并行消费者数 × 1
例:业务希望 8 个消费者并行消费,分区数至少 8。
```

---

## 五、消息在分区中的存储

### 1. 顺序写盘(顺序 IO)

Kafka 之所以快,核心之一就是**顺序写盘**。

```text
传统数据库(随机写):
每次 INSERT / UPDATE 都要在 B+tree 中查找位置后写入
   ┌─────────────────┐
   │  Page 1   ●     │
   │  Page 2     ●   │   ← 多次随机寻道
   │  Page 3   ●     │
   │  Page 4     ●   │
   └─────────────────┘

Kafka(顺序写):
Producer 发出消息 → 全部追加到 Partition 末尾
   ┌─────────────────┐
   │  offset 0  message  │
   │  offset 1  message  │
   │  offset 2  message  │   ← 一次顺序追加
   │  offset 3  message  │
   │  offset 4  message  │   ← append only
   └─────────────────┘
```

性能对比:

| 写盘方式      | 寻道开销 | 典型吞吐       |
|---------------|----------|----------------|
| 4K 随机写     | 0.1ms    | 100 IOPS       |
| 顺序写        | 0        | 600 MB/s+      |
| 内存映射      | 0        | GB/s 级        |

即使 7200 转的机械硬盘,顺序写也能达到 600 MB/s,堪比 SSD 随机写。

### 2. Offset 概念

**Offset(偏移量)** 是消息在 Partition 内的唯一序号,从 0 开始单调递增。

```text
Topic: order-topic, Partition: 0

offset 0: { orderId: 1, amount: 100 }
offset 1: { orderId: 2, amount: 200 }
offset 2: { orderId: 3, amount: 300 }
offset 3: { orderId: 4, amount: 400 }
...
offset N: 最新消息
```

关键点:

- **Offset 是分区级别**的,不同 Partition 的 Offset 互相独立
- **Offset 不跨分区**,所以"全局第 N 条消息"没有意义
- **Offset 由 Producer 写入时分配**(即消费者看到的 Offset)
- **消费者通过提交 Offset** 告知 Kafka 自己的消费位置
- **Kafka 不会主动重置 Offset**,由消费者自己控制

### 3. 消息位移递增

- **新消息 Offset = 当前最大 Offset + 1**
- **删消息不会减少 Offset**(Offset 永远单调递增)
- **过期删除的消息 Offset 会形成"空洞"**,但消费者看不到这些空洞
- **Offset 与时间无关**(不要用 Offset 推算时间)

### 4. 消息结构

每条 Kafka 消息由以下字段组成:

```text
┌──────────────────────────────────────────────────────────┐
│ Offset (8B)  │ Size (4B)  │ CRC (4B)  │ Magic (1B)   │
│ Attributes (1B) │ Timestamp (8B/varint) │ Key Length (4B/varint) │
│ Key (var bytes) │ Value Length (4B/varint) │ Value (var bytes) │
│ Headers (array, optional)                                  │
└──────────────────────────────────────────────────────────┘
```

字段含义:

| 字段       | 含义                                       |
|------------|--------------------------------------------|
| Offset     | 消息在 Partition 内的偏移量                |
| Size       | 整条消息的字节数                           |
| CRC        | 校验码,防止消息损坏                       |
| Magic      | 协议版本号                                 |
| Attributes | 压缩标识、时间戳类型等                    |
| Timestamp  | 消息时间戳(毫秒)                          |
| Key        | 消息键,用于分区路由                       |
| Value      | 消息体,业务数据                           |
| Headers    | 用户自定义键值对(0.11+)                  |

---

## 六、分区分配策略

当 Consumer Group 订阅 Topic 时,Kafka 会把该 Topic 的所有 Partition 按照一定策略分配给组内的消费者。Kafka 提供了三种分配策略。

### 1. Range(范围分配)

**默认策略**。按 Topic 逐个分配,每个 Topic 内按范围均分。

```text
Topic A 有 8 个分区,订阅者 3 个消费者
  8 / 3 = 2 余 2 → 前 2 个消费者各 3 个分区,最后一个 2 个

  C0: P0, P1, P2
  C1: P3, P4, P5
  C2: P6, P7

特点:
  - 简单、平均
  - 缺点:多个 Topic 一起分配时,前面的消费者累积多分区,产生"倾斜"
```

多 Topic 下的倾斜:

```text
Topic A:  4 个分区,3 个消费者
  C0: P0, P1
  C1: P2
  C2: P3

Topic B:  4 个分区
  C0: P0, P1   ← C0 累计 4 个分区
  C1: P2       ← C1 累计 2 个
  C2: P3       ← C2 累计 2 个

问题:订阅的 Topic 越多,前面的消费者累积分区的"竞争劣势"越明显
```

### 2. RoundRobin(轮询分配)

将 Topic-Partition 列表打散后轮询分配给消费者。

```text
订阅 Topic A 和 B,各 4 个分区,共 8 个 partition,3 个消费者

按字典序排列: A-P0, A-P1, A-P2, A-P3, B-P0, B-P1, B-P2, B-P3

轮询:
  C0: A-P0, A-P3, B-P1, B-P2  (4)
  C1: A-P1, B-P0, B-P3         (3)
  C2: A-P2                     (1)

优点: 跨 Topic 均衡
缺点: Rebalance 时几乎所有消费者的分配都会变,迁移量大
```

### 3. Sticky(粘性分配,Kafka 0.11+)

**结合 RoundRobin 的均衡和保留 Rebalance 前的分配**。

```text
第一轮分配后:
  C0: A-P0, A-P3, B-P1, B-P2
  C1: A-P1, B-P0, B-P3
  C2: A-P2

新增 C3 后,触发 Rebalance:
  Sticky 策略目标:尽量保留原分配,只迁移必要部分

  C0: A-P0, B-P1  (保持)
  C1: A-P1, B-P0  (保持)
  C2: A-P2        (保持)
  C3: A-P3, B-P2, B-P3  (新分配)
```

优点:

- **Rebalance 改动最小**,减少不必要的分区迁移
- **保留原分配**,减少消费者冷启动
- **均衡度等同或优于 RoundRobin**

配置方式:

```properties
# consumer.properties
partition.assignment.strategy=org.apache.kafka.clients.consumer.StickyAssignor
```

多策略组合:

```properties
# 优先 RoundRobin,失败则使用 Sticky
partition.assignment.strategy=org.apache.kafka.clients.consumer.RoundRobinAssignor,org.apache.kafka.clients.consumer.StickyAssignor
```

---

## 七、副本分配算法

### 1. 什么是副本(Replica)

每个 Partition 可以配置多个副本,存放在不同的 Broker 上,实现高可用:

- **Leader Replica**:对外提供读写,所有请求只走 Leader
- **Follower Replica**:从 Leader 同步数据,常驻被动状态
- **ISR(In-Sync Replicas)**:与 Leader 同步的副本集合
- **OSR(Out-of-Sync Replicas)**:落后过多的副本

### 2. 副本分配的基本原则

Kafka 使用 `kafka-reassign-partitions.sh` 工具进行副本分配,核心原则:

1. **副本必须分布在不同的 Broker**
2. **优先保证 HA(高可用),即 Leader 均衡**
3. **支持机架感知(rack-aware)**

### 3. 普通副本分配算法

```text
集群:5 个 Broker,Broker.id = 1,2,3,4,5
Topic: order-topic, 8 个分区,3 个副本

分配过程中,Kafka 内部使用:
  起始 broker id = (随机起点) % broker_count
  副本 1: 起点
  副本 2: (起点 + 1) % broker_count
  副本 3: (起点 + 2) % broker_count
```

分配示意:

```text
Partition 0: Replicas = [1, 2, 3]
Partition 1: Replicas = [2, 3, 4]
Partition 2: Replicas = [3, 4, 5]
Partition 3: Replicas = [4, 5, 1]
Partition 4: Replicas = [5, 1, 2]
Partition 5: Replicas = [1, 3, 5]   ← 步长变化,避免聚集
Partition 6: Replicas = [2, 4, 1]
Partition 7: Replicas = [3, 5, 2]
```

### 4. 机架感知分配

Kafka 通过 `broker.rack` 参数支持机架感知,避免同一分区的多个副本集中在同一机架。

```text
# server.properties
broker.id=1
broker.rack=RACK-A

broker.id=2
broker.rack=RACK-A

broker.id=3
broker.rack=RACK-B

broker.id=4
broker.rack=RACK-B

broker.id=5
broker.rack=RACK-C
```

#### (1) 跨机架分配示意

```text
RACK-A          RACK-B          RACK-C
┌────────┐      ┌────────┐      ┌────────┐
│ B1 (L) │      │ B3 (F) │      │ B5 (F) │
└────────┘      └────────┘      └────────┘
┌────────┐      ┌────────┐      ┌────────┐
│ B2 (F) │      │ B4 (F) │      │        │
└────────┘      └────────┘      └────────┘

Partition 0:  [B1 (Leader), B3 (Follower), B5 (Follower)]
             ↑ RACK-A        ↑ RACK-B        ↑ RACK-C
```

#### (2) 机架感知的好处

- **避免机架级故障**:整个机架断电时,其他副本仍可服务
- **Leader 均衡**:Leader 会均匀分布到不同机架

### 5. 手工副本重分配

```bash
# 1. 生成 reassignment.json
cat > reassignment.json <<'EOF'
{
  "version": 1,
  "partitions": [
    {
      "topic": "order-topic",
      "partition": 0,
      "replicas": [1, 3, 5]
    },
    {
      "topic": "order-topic",
      "partition": 1,
      "replicas": [2, 4, 1]
    }
  ]
}
EOF

# 2. 执行分配
kafka-reassign-partitions.sh --bootstrap-server localhost:9092 \
  --reassignment-json-file reassignment.json \
  --execute

# 3. 验证进度
kafka-reassign-partitions.sh --bootstrap-server localhost:9092 \
  --reassignment-json-file reassignment.json \
  --verify
```

---

## 八、分区扩容

### 1. 为什么要扩容

- 业务增长导致单分区吞吐瓶颈
- 增加消费者并行度
- 退役老 Broker 时重平衡

### 2. 扩容命令

```bash
kafka-topics.sh --bootstrap-server localhost:9092 \
  --alter --topic order-topic --partitions 12
```

### 3. 扩容的影响

#### (1) Hash 分区键失效

如果消息按照 key 哈希分配分区,扩容后 key 的哈希值对应的分区数变了,会导致同一个 key 的消息分散到不同分区。

```text
扩容前: 4 个分区
  key="user_100" → hash % 4 = 2 → Partition 2

扩容后: 8 个分区
  key="user_100" → hash % 8 = 4 → Partition 4

结论:同一 key 的消息从 "Partition 2" 分散到 "Partition 2 和 4"(老消息不动,新消息走新分区)
```

#### (2) 消费者重新分配

新增分区后,需要触发 Rebalance 重新分配消费者:

```text
扩容前: 4 partitions × 2 consumers
  C0: P0, P1
  C1: P2, P3

扩容后: 8 partitions × 2 consumers
  C0: P0, P1, P4, P5
  C1: P2, P3, P6, P7
```

#### (3) 消息顺序破坏

- **扩容前**:同一 key 的所有消息都在同一分区,顺序保证
- **扩容后**:同一 key 的消息**可能**分散到两个分区,顺序保证失效(在两个分区之间)
- **业务影响**:如果业务依赖"同一 key 全局有序",扩容会破坏

```text
扩容前,key="order-1" 全部走 P2:
  offset 0: create
  offset 1: pay
  offset 2: ship

扩容后,key="order-1" 可能在 P2 和 P5:
  P2 offset 0: create
  P5 offset 0: pay     ← 顺序看起来反了
  P2 offset 1: ship
```

### 4. 扩容最佳实践

| 做法                                      | 说明                                                |
|-------------------------------------------|-----------------------------------------------------|
| **初期就给足分区数**                      | 避免频繁扩容                                        |
| **避免扩容跨整数倍**                      | 扩容时尽量使 ratio = 整数倍,减少 key 分散          |
| **业务接受临时不一致**                    | 扩容在业务低峰期执行,降低顺序敏感场景的影响        |
| **提前通知消费者**                        | Rebalance 会导致短时消费停滞,通知业务方            |
| **预留扩容比例**                          | 假设 30% 增长,直接给 1.5x 分区数,避免短期内再次扩容 |

---

## 九、分区副本同步

### 1. 同步流程

```text
Producer
   │
   ▼
[ Leader Broker ]
   │
   │  1. 写入本地 log
   │  2. 写入后等待 Follower 响应
   │
   ├──► [ Follower 1 ]
   │       │
   │       │   发起 Fetch 请求,拉取最新消息
   │       │
   │       └──► 写入本地 log
   │
   └──► [ Follower 2 ]
           │
           │   发起 Fetch 请求,拉取最新消息
           │
           └──► 写入本地 log
```

### 2. ISR 管理

```text
初始状态: ISR = [Leader, F1, F2]

F1 同步滞后或失效:
  → 超过 replica.lag.time.max.ms(默认 30s)未同步
  → Kafka 将 F1 从 ISR 中移除
  → ISR = [Leader, F2]

F1 恢复,数据追上:
  → Kafka 将 F1 重新加入 ISR
  → ISR = [Leader, F1, F2]
```

### 3. Leader 选举

Leader 故障时,Controller 从 ISR 中选举新 Leader:

```text
原状态: ISR = [1, 2, 3], Leader = 1

Broker 1 故障:
  Controller 监听 ZK / KRaft 感知到故障
  从 ISR = [2, 3] 中选一个新 Leader
  通常按优先级:replica.priority.broker.list,或选 ISR 中第一个

选举后: ISR = [2, 3], Leader = 2
```

### 4. 关键参数

```properties
# broker.properties
replication.factor=3            # 副本数
min.insync.replicas=2           # 最小 ISR 数
replica.lag.time.max.ms=30000    # 副本最大滞后时间
unclean.leader.election.enable=false  # 不允许从 OSR 选 Leader
```

### 5. 丢数据场景

```text
replication.factor=3, min.insync.replicas=2, acks=all

场景 1:正常
  Leader 收到消息,等 F1、F2 同步成功,返回 ACK
  结果: 3 副本都写入,丢不了

场景 2:Leader 写完,F1 同步成功,挂掉
  ISR = [F1, F2]
  Controller 选 F1 为新 Leader
  结果:数据还在,可能部分数据未消费

场景 3:Leader 收到但 F1、F2 还没同步,Leader 进程 crash
  ISR = [F2]
  如果此时 unclean.leader.election.enable=true
  → 可能选 F2(缺少最新数据) → 丢数据
```

设置 `unclean.leader.election.enable=false` 能避免脏选举,**但代价是分区短时不可用**。

---

## 十、Segment 文件结构

Kafka 在每个 Partition 内部并不直接读写一个超大的文件,而是将其切分为多个 **Segment**(段文件),每个 Segment 是一组相关文件。

### 1. 目录结构

```text
/kafka-logs/
  order-topic-0/
    ├── 00000000000000000000.log      # 数据文件
    ├── 00000000000000000000.index     # 偏移量索引
    ├── 00000000000000000000.timeindex # 时间戳索引
    ├── 00000000000000170400.log      # 下一个 Segment
    ├── 00000000000000170400.index
    ├── 00000000000000170400.timeindex
    ├── 00000000000000340800.log
    ├── 00000000000000340800.index
    ├── 00000000000000340800.timeindex
    ├── leader-epoch-checkpoint
    └── partition.metadata
```

### 2. 文件命名规则

```text
Segment 文件名 = 该 Segment 第一条消息的 Offset

例:
  00000000000000000000.log   # 包含 offset 0 ~ 170399
  00000000000000170400.log   # 包含 offset 170400 ~ 340799
  00000000000000340800.log   # 包含 offset 340800 ~ 511199
```

### 3. 文件结构详解

#### (1) .log 文件

存储消息的实际内容,顺序追加,内部由若干 RecordBatch 组成:

```text
┌─────────────────────────────────────────────────────────┐
│ Log Segment (例: 00000000000000000000.log)             │
├─────────────────────────────────────────────────────────┤
│                                                          │
│ RecordBatch 1                                            │
│ ┌──────────────────────────────────────────────────┐    │
│ │ Batch Base Offset (8B)    │ 4096                  │    │
│ │ Batch Length (4B)         │ 900                   │    │
│ │ Partition Leader Epoch (4B) │ 5                  │    │
│ │ Magic (1B)                │ 2                     │    │
│ │ CRC (4B)                  │ 0xAABBCCDD           │    │
│ │ Attributes (2B)           │ 0x0000 (no compress) │    │
│ │ Last Offset Delta (4B)    │ 99 (this batch has 100 records)│
│ │ First Timestamp (8B)      │ 1700000000000        │    │
│ │ Max Timestamp (8B)        │ 1700000099000        │    │
│ │ Producer ID (8B)          │ -1                   │    │
│ │ Producer Epoch (2B)       │ -1                   │    │
│ │ Base Sequence (4B)        │ -1                   │    │
│ │ Record Count (4B)         │ 100                  │    │
│ │ ─────────────────────────────────────────────    │    │
│ │ Record 1: Offset 0     │ Length 50 │ Key/Value  │    │
│ │ Record 2: Offset 1     │ Length 50 │ Key/Value  │    │
│ │ ...                                                  │    │
│ │ Record 100: Offset 99  │ Length 50 │ Key/Value  │    │
│ └──────────────────────────────────────────────────┘    │
│                                                          │
│ RecordBatch 2                                            │
│ ┌──────────────────────────────────────────────────┐    │
│ │ ... (同样的结构)                                  │    │
│ └──────────────────────────────────────────────────┘    │
│                                                          │
│ ...                                                      │
└─────────────────────────────────────────────────────────┘
```

#### (2) .index 文件(OffsetIndex)

保存"Offset → 物理位置"的稀疏索引,支持二分查找。

```text
.index 文件结构(每条 8B key + 4B value + 4B offset,共 8 字节):

┌────────────────┬────────────────┬────────────────────┐
│ relativeOffset │ physicalPos    │ description        │
│ (4B, varint)   │ (4B, varint)   │                    │
├────────────────┼────────────────┼────────────────────┤
│ 0              │ 0              │ 第 0 条消息在 log  │
│  (base offset) │  (文件起始)    │                      │
│ 4096           │ 4321           │ offset 4096 在 4321│
│ 8192           │ 8642           │ offset 8192 在 8642│
│ 12288          │ 12963          │ offset 12288 在 ...│
│ ...            │ ...            │                    │
└────────────────┴────────────────┴────────────────────┘

索引间隔由 index.interval.bytes(默认 4096 字节)控制
```

#### (3) .timeindex 文件

保存"Timestamp → Offset"的稀疏索引,支持按时间查找。

```text
┌────────────────┬────────────────┐
│ timestamp      │ relativeOffset  │
│ (8B)           │ (4B)            │
├────────────────┼────────────────┤
│ 1700000000000  │ 0               │
│ 1700000500000  │ 4096            │
│ 1700001000000  │ 8192            │
│ 1700001500000  │ 12288           │
│ ...            │ ...             │
└────────────────┴────────────────┘
```

### 4. 读取示例:查找 offset 6789

```text
1. 从最新的 .index 文件开始往前找,定位到 offset 4096 的索引项
2. 找到 "offset 4096 在物理位置 4321"
3. 从 4321 顺序扫描,找到 offset 6789
4. 读取完整消息
```

代价:`O(log N) + O(1)`,N 为 Segment 数,扫描范围是 1 个 Segment 内的 page cache 页。

### 5. Segment 滚动策略

满足任一条件即滚动:

- **segment.bytes**:当前 Segment 超过 1G(默认)
- **segment.ms**:当前 Segment 超过 7 天(默认,即使没满)
- **index.interval.bytes**:索引项间隔超过 4096 字节

---

## 十一、日志清理策略

Kafka 提供两种日志清理策略,所有清理发生在 Partition 级别。

### 1. delete(基于时间/大小)

最常用策略,过期或超大的消息被删除。

```text
清理逻辑:
  1. 定时任务 LogCleaner 检查所有 Partition
  2. 命中以下任一条件即触发删除:
     - 消息 timestamp + retention.ms < 当前时间
     - 当前 Segment 累计大小 > retention.bytes
  3. 删除满足条件的整个 Segment 文件
```

#### (1) 基于时间

```bash
kafka-topics.sh --bootstrap-server localhost:9092 \
  --alter --topic order-topic --config retention.ms=86400000
```

```text
retention.ms = 86400000 (1 天)

当前时间: 2026-08-18 12:00:00
所有 timestamp < 2026-08-17 12:00:00 的消息被删除
```

#### (2) 基于大小

```bash
kafka-topics.sh --bootstrap-server localhost:9092 \
  --alter --topic order-topic --config retention.bytes=1073741824
```

```text
retention.bytes = 1GB

当 Partition 累计数据 > 1GB,从最旧的 Segment 开始删除,直到 ≤ 1GB
```

#### (3) 实际例子

```text
order-topic-0
├── 00000000000000000000.log   (1GB, 即将被删除)
├── 00000000000000100000000.log (1GB, 即将被删除)
├── 00000000000000200000000.log (800MB, 保留)
└── 00000000000000280000000.log (active)

retention.bytes=2GB
总占用 = 1 + 1 + 0.8 = 2.8GB > 2GB
→ 删除最旧的 Segment 直到 ≤ 2GB
→ 保留 00000000000000100000000.log(1GB) 和 00000000000000200000000.log(0.8GB)
```

### 2. compact(基于 key 合并)

针对每个 key,只保留最新的 value,删除历史的相同 key 消息。

```text
场景:用户表变更 CDC
  key="user_100", 多次更新

原始日志:
  offset 0: user_100, name="Alice", age=25
  offset 1: user_100, name="Alice", age=26
  offset 2: user_100, name="Alice", age=27
  offset 3: user_200, name="Bob", age=30
  offset 4: user_100, name="Alice", age=28
  offset 5: user_100, tombstone       ← 删除标记

compact 后:
  offset 3: user_200, name="Bob", age=30
  offset 4: user_100, name="Alice", age=28
  offset 5: user_100, tombstone       ← 保留 ttl 时间后删除
```

#### (1) 启用 compact

```bash
kafka-topics.sh --bootstrap-server localhost:9092 \
  --create --topic user-topic \
  --partitions 3 \
  --replication-factor 3 \
  --config cleanup.policy=compact \
  --config min.cleanable.dirty.ratio=0.1 \
  --config segment.ms=3600000 \
  --config delete.retention.ms=86400000
```

#### (2) 关键配置

| 配置                         | 默认值 | 含义                                            |
|------------------------------|--------|-------------------------------------------------|
| `cleanup.policy`             | delete | 改为 compact 或 delete,compact                  |
| `min.cleanable.dirty.ratio`  | 0.5    | 脏数据(待压缩)占比超过此值触发压缩             |
| `segment.ms`                 | 7 天   | compact 模式下建议缩短,更频繁触发              |
| `delete.retention.ms`        | 24h    | tombstone(墓碑) 保留时间,过期后真正删除         |
| `min.compaction.lag.ms`      | 0      | 消息最小存活时间,小于此时间的不压缩            |

#### (3) compact 触发流程

```text
定时任务 (log.cleaner.thread)
   │
   ▼
1. 选择 dirty ratio > min.cleanable.dirty.ratio 的 Partition
   │
   ▼
2. 在 .log 末尾标 dirty 区域
   │
   ▼
3. 复制一份到"clean 副本"的 offsetMap
   │
   ▼
4. 扫描全部日志,丢弃 offsetMap 中已存在的旧版本
   │
   ▼
5. 写入新的 .log 文件
   │
   ▼
6. 替换原文件
```

#### (4) compact 适用场景

- **维度表同步**:mysql binlog → kafka → 多个下游系统
- **配置中心**:所有节点的最新配置只保留一份
- **状态快照**:支持"恢复到最后 N 次状态"的需求

### 3. 两种策略对比

| 维度           | delete                              | compact                              |
|----------------|-------------------------------------|--------------------------------------|
| 数据特征       | 时序数据,过期没价值                 | 状态数据,最新值最重要               |
| 清理单位       | Segment                             | 相同 key 历史消息                    |
| 清理时间       | 按 retention.ms / retention.bytes   | 按 dirty ratio                       |
| 典型场景       | 日志、埋点、消息事件                 | CDC、配置、状态同步                  |
| 磁盘占用       | 线性增长                           | 收敛到当前 key 数 × 1 条              |
| 消费者影响     | 消费者可能看不到历史消息             | 消费者看到的是"去重"后的最新状态     |

---

## 十二、实战案例

### 1. 创建合适 Topic

#### 场景:电商订单 Topic

```bash
kafka-topics.sh --bootstrap-server kafka1:9092 \
  --create --topic order-topic \
  --partitions 12 \
  --replication-factor 3 \
  --config retention.ms=2592000000 \
  --config compression.type=zstd \
  --config cleanup.policy=delete \
  --config min.insync.replicas=2 \
  --config max.message.bytes=2097152 \
  --config segment.bytes=536870912 \
  --config segment.ms=604800000
```

决策依据:

| 配置项      | 取值      | 决策依据                                    |
|-------------|-----------|---------------------------------------------|
| partitions  | 12        | 峰值 5 万 TPS,单分区 3 万 TPS,需 12 个       |
| rf          | 3         | 3 副本,容忍 1 个 Broker 故障                |
| retention   | 30 天     | 业务需要回溯 30 天订单                       |
| compression | zstd       | 高压缩比 + 低 CPU,节省带宽                  |
| min.isr     | 2         | 至少 2 副本同步,容忍 1 副本故障             |
| max.bytes   | 2 MB     | 订单详情可能包含较多字段,放宽限制           |
| segment     | 512 MB / 7 天 | 控制单文件大小,清理粒度细些               |

### 2. 计算合理的分区数

#### 场景:用户画像 Topic

```text
业务需求:
  - 峰值写入: 8 万 TPS
  - 峰值消费: 100 个消费者并行(每个消费 1 个)
  - 单分区写入上限: 3 万 TPS
  - 单分区消费上限: 5 MB/s

计算:
  生产所需 = 80000 / 30000 = 2.67 → ceil → 3
  消费所需 = 100 (100 个消费者期望并行)
  分区数 = max(3, 100) = 100

考虑 2 倍扩展: 100 × 2 = 200
最终: 200 个分区,3 副本

注意: 200 分区 + 3 副本 = 600 个副本
      假设 5 个 Broker,每个 Broker 跑 120 个副本
      单机管理 120 个副本,Controller 内存可控
      
推荐: 扩容到 6 个 Broker,每个 运行 100 个副本,更均衡
```

#### 场景:日志埋点 Topic

```text
业务需求:
  - 峰值写入: 5 万 TPS
  - 消费: 最多 10 个 Flink 并行
  - 保留 3 天

计算:
  分区数 = max(5万/3万, 10) = 10
  考虑 1.5 倍扩展: 10 × 1.5 = 15
  最终: 15 个分区,2 副本

注意: 2 副本 + 15 分区 = 30 个副本
      3 个 Broker,单机 10 个副本,适中
```

### 3. 调整配置的完整流程

#### 场景:延长订单 Topic 保留时间从 7 天到 30 天

```bash
# 1. 评估影响
#    30 天消息量 = 7 天 × 4.3 ≈ 4.3 倍磁盘占用
#    确认磁盘容量足够

# 2. 查看当前配置
kafka-topics.sh --bootstrap-server kafka1:9092 \
  --describe --topic order-topic

# 3. 调整保留时间
kafka-topics.sh --bootstrap-server kafka1:9092 \
  --alter --topic order-topic \
  --config retention.ms=2592000000

# 4. 验证配置生效
kafka-topics.sh --bootstrap-server kafka1:9092 \
  --describe --topic order-topic | grep retention.ms

# 5. 监控磁盘
#    监控 /kafka-logs 目录增长
#    监控 kafka.log.dir.usage 指标
```

### 4. 分区扩容实战

```bash
# 1. 当前配置: 4 分区
kafka-topics.sh --bootstrap-server kafka1:9092 \
  --describe --topic order-topic

# 2. 扩容到 12 分区
kafka-topics.sh --bootstrap-server kafka1:9092 \
  --alter --topic order-topic --partitions 12

# 3. 验证
kafka-topics.sh --bootstrap-server kafka1:9092 \
  --describe --topic order-topic | grep PartitionCount

# 4. 观察消费者 Rebalance
#    - 监控 consumer group lag
#    - 监控 consumer count
#    - 业务可能经历 1~10 秒的 STW

# 5. 验证 key 散列
#    使用 kafka-console-consumer 抽样查看 offset 分布
kafka-console-consumer.sh --bootstrap-server kafka1:9092 \
  --topic order-topic --from-beginning \
  --max-messages 10000 \
  --property print.partition=true
```

### 5. 启用 compact(配置中心场景)

```bash
# 1. 创建配置 Topic
kafka-topics.sh --bootstrap-server kafka1:9092 \
  --create --topic config-topic \
  --partitions 3 \
  --replication-factor 3 \
  --config cleanup.policy=compact \
  --config min.cleanable.dirty.ratio=0.1 \
  --config segment.ms=3600000 \
  --config delete.retention.ms=86400000

# 2. 生产配置变更(同一 key 多次更新)
kafka-console-producer.sh --bootstrap-server kafka1:9092 \
  --topic config-topic --property "parse.key=true" --property "key.separator=:"

> db.host:db1.local
> db.port:5432
> db.host:db2.local         ← 覆盖 db.host
> db.port:5433              ← 覆盖 db.port

# 3. 同一 key 只保留最新
kafka-console-consumer.sh --bootstrap-server kafka1:9092 \
  --topic config-topic --from-beginning \
  --property "print.key=true" --property "print.value=true"

# 输出:
db.host:db1.local    ← 旧版本
db.port:5432          ← 旧版本
db.host:db2.local    ← 最新
db.port:5433          ← 最新
```

### 6. 日常运维命令汇总

```bash
# 查看消费者组
kafka-consumer-groups.sh --bootstrap-server localhost:9092 --list

# 查看 lag(消费滞后)
kafka-consumer-groups.sh --bootstrap-server localhost:9092 \
  --describe --group order-consume

# 重置消费位置
kafka-consumer-groups.sh --bootstrap-server localhost:9092 \
  --group order-consume \
  --reset-offsets \
  --topic order-topic \
  --to-earliest \
  --execute

# 查看 topic 配置
kafka-configs.sh --bootstrap-server localhost:9092 \
  --describe --entity-type topics --entity-name order-topic

# 修改 broker 配置
kafka-configs.sh --bootstrap-server localhost:9092 \
  --alter --entity-type brokers --entity-name 1 \
  --add-config "log.retention.ms=604800000"
```

---

## 十三、核心要点速记

- **Topic 是逻辑概念,Partition 是物理分片**:Topic = N 个 Partition,所有 IO 都发生在 Partition 级别
- **kafka-topics.sh 是 Topic 管理的唯一入口**:`--create / --list / --describe / --alter / --delete` 五大操作
- **Partition 数只能增加,不能减少**:减少分区会丢数据,Kafka 直接不支持
- **Sortition 不可改**:已经确定 key 的旧消息不会重新分布,扩容后同一 key 可能跨多个分区
- **副本数 = `replication.factor`,建议生产环境 ≥ 3**:容忍 1 个 Broker 故障
- **min.insync.replicas 配合 `acks=all`**:是数据不丢的最低保障
- **unclean.leader.election.enable=false**:避免脏选举,宁可分区短暂不可用也不丢数据
- **分区数决策公式**:分区数 = max(生产者所需,消费者所需,未来扩展系数)
- **生产环境分区数估算**:峰值 TPS / 单分区 TPS 上限,再 × 1.5~2 扩展系数
- **单分区上限参考**:写入 1~5 万 TPS,吞吐 10~30 MB/s
- **顺序保证仅在 Partition 级别**:跨 Partition 无序,业务依赖全局顺序就只能 1 个 Partition
- **Consumer Group 内一个 Partition 只能被一个消费者消费**:消费者超过分区数则空闲
- **三种分区分配策略**:Range(默认,可能倾斜)、RoundRobin(均衡但 Rebalance 抖)、Sticky(均衡+稳定,推荐)
- **Segment 文件三件套**:`.log`(数据)/ `.index`(Offset 索引)/ `.timeindex`(时间戳索引)
- **Segment 命名 = 第一条消息 Offset**:00000000000000000000.log = 包含 offset 0
- **Segment 滚动条件**:超过 `segment.bytes`(默认 1G) 或 `segment.ms`(默认 7 天)
- **Offset 索引采用稀疏索引**:每 4096 字节 1 个索引项,查找复杂度 O(log N)
- **清理策略 `delete`**:按时间 / 大小清理过期数据,适合时序日志
- **清理策略 `compact`**:按 key 合并,只保留最新值,适合 CDC / 配置同步
- **compact + delete 组合**:先 delete 后 compact,既有时效性又有去重
- **机架感知配置**:通过 `broker.rack` 参数,避免分区的多个副本集中同一机架
- **副本分配算法**:Kafka 默认在 Broker 间均匀分布,支持机架感知
- **扩容前先评估影响**:哈希分区键失效、消费者 Rebalance、消息顺序破坏
- **副本同步走 Leader**:所有读写请求都先到 Leader,Follower 主动拉取
- **ISR 动态管理**:超过 `replica.lag.time.max.ms` 自动从 ISR 移除
- **Topic 核心配置项**:`retention.ms`、`cleanup.policy`、`min.insync.replicas`、`compression.type`、`max.message.bytes`
- **生产压缩推荐 zstd 或 lz4**:高压缩比 + 低 CPU,节省带宽
- **删除 Topic 不可逆**:执行前务必确认业务无依赖,需要在 broker 端 `delete.topic.enable=true`
