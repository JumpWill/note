# Topic 与集群管理 (Topic & Cluster Management)

Topic、Partition、副本机制是 Redpanda 集群管理的核心。Redpanda 在保持与 Kafka 完全兼容的 API 基础上,通过自研的 C++ 存储引擎和 Raft 共识协议,对 Topic 的创建、分区分配、副本摆放、日志清理等关键路径做了深度优化。本章从概念到命令、从原理到实战,完整讲解 Redpanda Topic 与集群管理的全部细节。

---

## 一、Topic 概念详解(与 Kafka 相同)

### 1. 什么是 Topic

在 Redpanda 中,**Topic(主题)** 是消息的逻辑分类,等价于 Kafka 中"表"的概念,但底层由 Redpanda 自研的 `cluster::topic_namespace` 结构维护。

- **生产端**:向 Topic 发送消息(通过 rpk topic produce 或 Kafka 兼容客户端)
- **消费端**:从 Topic 订阅消息(完全兼容 Kafka Consumer 协议)
- **Broker**:实际存储 Topic 的物理数据(Redpanda 单进程同时承担 Broker + Controller + Schema Registry 等多角色)
- **逻辑分层**:Topic 是逻辑层,Partition 是物理层,一个 Topic 由 N 个 Partition 组成

### 2. Topic 的本质

Topic 并不是一个文件或者一个目录。它是一组 Partition 的逻辑集合,每个 Partition 才是真实落在磁盘上的物理文件集合。Redpanda 默认数据目录是 `/var/lib/redpanda/data`,内部按 `<topic>-<partition>_<revision>` 形式组织目录。

```text
Topic (逻辑)        Partition (物理)        磁盘文件
─────────────────────────────────────────────────────────
order-topic         └── Partition 0         /var/lib/redpanda/data/order-topic-0_2/
                    └── Partition 1         /var/lib/redpanda/data/order-topic-1_2/
                    └── Partition 2         /var/lib/redpanda/data/order-topic-2_2/
```

> 与 Kafka 不同:Redpanda 的目录后缀带 `_revision`(`_2` 是 revision 编号),每次对 Topic 做不兼容操作(如增加分区、删除)都会递增 revision,用于支持 Time Travel 查询(Enterprise 特性)。

### 3. Topic 与消息系统的类比

| 概念         | MySQL              | Kafka                | Redpanda            | RabbitMQ            |
|--------------|--------------------|----------------------|---------------------|---------------------|
| 逻辑容器     | database + table   | topic                | topic               | exchange + queue    |
| 物理分片     | 数据文件 / 分区    | partition            | partition           | mirror queue        |
| 投递模型     | 拉(Pull)          | 拉(Pull)            | 拉(Pull)            | 推(Push) / 拉(Pull) |
| 消费模式     | 一次性查询         | 多消费者多次消费     | 多消费者多次消费     | 一次性消费(可持久)  |
| 顺序保证     | 弱                 | 分区内强顺序         | 分区内强顺序         | 队列内强顺序        |

### 4. Topic 的特性

- **完全兼容 Kafka**:Kafka Producer / Consumer 客户端代码无需修改即可连接 Redpanda
- **多订阅者**:一个 Topic 可以被多个消费者组独立消费,每个消费者组都消费到全量数据
- **持久化**:消息按 retention 策略持久化到磁盘(默认 7 天)
- **可扩展**:通过增加 Partition 提升并行度(同样只能增加,不能减少)
- **可备份**:通过 replication.factor 配置副本数(默认 1,生产建议 3)
- **顺序保证**:仅在**单个 Partition 内**保证消息顺序,跨 Partition 不保证

---

## 二、rpk topic 完整命令

Redpanda 提供官方 CLI 工具 **`rpk`**(原名 `redpanda-kafka-cli`),完全替代 Kafka 的 `kafka-topics.sh`。所有 Topic 操作都通过 `rpk topic <subcommand>` 完成。

### 1. 创建 Topic(rpk topic create)

```bash
# 最简形式:默认副本 1、分区 1
rpk topic create order-topic

# 完整形式:指定分区数、副本数、配置项
rpk topic create order-topic \
  -p 3 \
  -r 2 \
  --retention-ms 604800000 \
  --compression-type producer \
  --min.insync.replicas 2 \
  --cleanup-policy delete

# 输出:
# TOPIC       STATUS
# order-topic  OK
```

参数说明:

| 参数                    | 含义                              | 是否必填      |
|-------------------------|-----------------------------------|---------------|
| `<topic_name>`          | Topic 名称(非法字符:空格、`+`、`,`) | 必填          |
| `-p, --partitions`      | 分区数,默认 1                     | 否            |
| `-r, --replicas`        | 副本数,默认 1                     | 否            |
| `--retention-ms`        | 消息保留时间(毫秒)              | 否            |
| `--retention-bytes`     | 消息保留字节数                    | 否            |
| `--compression-type`    | 压缩类型:none / gzip / snappy / lz4 / zstd | 否     |
| `--cleanup-policy`      | 清理策略:delete / compact / delete,compact | 否 |
| `--min.insync.replicas` | 最小同步副本数                    | 否            |
| `--segment-ms`          | Segment 滚动时间                  | 否            |
| `--segment-bytes`       | Segment 滚动字节数                | 否            |
| `--max-message-bytes`   | 单条消息最大字节                  | 否            |
| `--config`              | 任意自定义配置 key=value,可写多个 | 否            |

### 2. 列出 Topic(rpk topic list)

```bash
# 列出所有 Topic
rpk topic list

# 输出(表格):
# NAME                    PARTITIONS  REPLICAS
# order-topic             3           2
# payment-topic           6           3
# user-topic              3           1

# 列出内部 Topic
rpk topic list --internal

# 输出:
# NAME                                PARTITIONS  REPLICAS
# __consumer_offsets                  50          3
# __redpanda_internal_topic             1          3
# __redpanda.cloud_storage            内部         1
```

> 注意:Redpanda 内部 Topic 以 `__redpanda_` 开头(`__consumer_offsets` 与 Kafka 一致),不要手动删除。Redpanda 23.x 后,内部 Topic 由系统自动管理。

### 3. 查看 Topic 详情(rpk topic describe)

```bash
# 查看单个 Topic
rpk topic describe order-topic

# 输出:
# NAME        PARTITIONS  REPLICAS  PARTITION  LEADERS  FOLLOWERS
# order-topic 3           2         -          -        -
#
# PARTITION  LEADER  REPLICAS  LOG-START-OFFSET  HIGH-WATERMARK
# 0          1       [1 2]     0                12345678
# 1          2       [2 3]     0                12340000
# 2          3       [3 1]     0                12345600

# 查看所有 Topic
rpk topic describe -A

# JSON 格式输出
rpk topic describe order-topic --format json
```

字段解读:

| 字段              | 含义                                                |
|-------------------|-----------------------------------------------------|
| `NAME`            | Topic 名称                                          |
| `PARTITIONS`      | Partition 总数                                      |
| `REPLICAS`        | 副本因子(配置,实际副本数看 REPLICAS 列)            |
| `PARTITION`       | 分区号                                              |
| `LEADER`          | 该分区的 Leader 副本所在的 Broker id                |
| `REPLICAS`        | 该分区的所有副本所在 Broker id 列表(含 Leader)      |
| `LOG-START-OFFSET`| 该分区最早可读 Offset(被压缩/删除后的起点)         |
| `HIGH-WATERMARK`  | 该分区下一条待写入消息的 Offset(= 已有消息数)       |

> 与 Kafka 不同:Redpanda 的 describe 输出自带 `LOG-START-OFFSET` 与 `HIGH-WATERMARK`,无需再调用 `kafka-get-offsets.sh`。

### 4. 删除 Topic(rpk topic delete)

```bash
# 删除 Topic
rpk topic delete order-topic

# 输出:
# TOPIC       STATUS
# order-topic  OK

# 强制删除(谨慎使用,跳过回收站逻辑)
rpk topic delete order-topic --no-confirm
```

底层流程:

```text
1. 客户端发起删除请求
2. Controller 在 __consumer_offsets 标记该 Topic 为删除状态
3. 关闭所有客户端连接
4. 向所有 broker 发送 StopReplica 请求
5. 删除 broker 磁盘上的 /var/lib/redpanda/data/<topic>-* 目录
6. 从元数据中移除 Topic
```

> **生产警告**:删除 Topic 是一个**不可逆的高危操作**,务必先确认无业务依赖。Redpanda 不像某些商业版有回收站机制,一旦删除就真的删除。

### 5. 增加分区(rpk topic add-partitions)

```bash
# 将 order-topic 从 3 分区扩到 6 分区
rpk topic add-partitions order-topic --num-to-add 3

# 输出:
# PARTITIONS
# 6
```

增加分区的影响(详见第八节):

- **哈希分区键失效**:旧分区的消息不会重新分布,新消息按新分区数重新 hash
- **消费者重新分配**:新增分区的消费需要重新触发 Rebalance
- **消息顺序**:同一个 key 的消息可能从"一个分区"变成"两个分区",顺序保证失效

> 注意:partition 数**只能增加不能减少**,减少分区会丢数据,Redpanda 直接不支持。

### 6. 修改配置(rpk topic alter-config)

```bash
# 修改分区数
rpk topic alter-config order-topic --set retention.ms=1209600000

# 同时修改多项配置
rpk topic alter-config order-topic \
  --set retention.ms=1209600000 \
  --set max.message.bytes=2097152 \
  --set compression.type=zstd

# 删除某个配置项(回退到 broker 全局配置)
rpk topic alter-config order-topic --delete retention.ms

# 同时设置和删除多个 key
rpk topic alter-config order-topic \
  --set compression.type=lz4 \
  --delete segment.bytes
```

### 7. 查看配置(rpk topic describe-config)

```bash
# 查看 Topic 的所有配置
rpk topic describe-config order-topic

# 输出:
# NAME                VALUE          SOURCE
# compression.type    producer       DEFAULT_CONFIG
# cleanup.policy      delete         DEFAULT_CONFIG
# min.insync.replicas 1              DEFAULT_CONFIG
# retention.ms        604800000      DYNAMIC_DEFAULT_CONFIG
# segment.bytes       134217728      DEFAULT_CONFIG
# ...

# 过滤关心的配置
rpk topic describe-config order-topic | grep -E "retention|cleanup|compress"
```

字段 `SOURCE` 说明:

| 取值                  | 含义                                          |
|-----------------------|-----------------------------------------------|
| `DEFAULT_CONFIG`      | Broker 全局默认值                              |
| `DYNAMIC_DEFAULT_CONFIG` | 集群动态默认值                              |
| `STATIC_BROKER_CONFIG` | 静态配置文件 redpanda.yaml 中的设置           |
| `TOPIC_CONFIG`        | Topic 自身设置的(优先级最高)                  |

### 8. 生产消息(rpk topic produce)

```bash
# 简单输入
rpk topic produce order-topic

# 进入交互模式后输入消息:
# > orderId=1001,amount=100
# > orderId=1002,amount=200
# > Ctrl+D 结束

# 直接管道输入
echo "hello redpanda" | rpk topic produce order-topic

# 带 key 的消息(--key)
rpk topic produce order-topic --key "user_100" --value "click button"

# 解析键值对输入(parse-key)
echo "user_100:click" | rpk topic produce order-topic \
  --parse-key --separator ":"

# 指定压缩算法
rpk topic produce order-topic --compression zstd < input.txt
```

### 9. 消费消息(rpk topic consume)

```bash
# 从最新开始消费
rpk topic consume order-topic

# 输出:
# PARTITION  OFFSET  KEY     VALUE                  TIMESTAMP
# 0          0       user_1  click                  1700000000000
# 1          0       user_2  view                   1700000000001
# ...

# 从头开始消费
rpk topic consume order-topic --offset start

# 指定消费者组
rpk topic consume order-topic --group my-group

# 消费指定分区
rpk topic consume order-topic --partition 0

# 限制消费条数
rpk topic consume order-topic --num 10

# 实时跟踪(默认就是 tail)
rpk topic consume order-topic --tail -1
```

常用参数:

| 参数               | 含义                                |
|--------------------|-------------------------------------|
| `--offset`         | 消费起始位置:`start` / `end` / `N`  |
| `--group`          | 加入指定消费者组                     |
| `--partition`      | 指定分区                            |
| `--num`            | 最多消费 N 条后退出                  |
| `--key`            | 仅消费指定 key 的消息               |
| `--regex`          | 仅消费 key 匹配正则的消息           |
| `--print-headers`  | 打印消息头                          |
| `--print-timestamp`| 打印时间戳(默认就打印)              |

---

## 三、Topic 配置项详解

Redpanda Topic 维度配置完全兼容 Kafka(API 层),但内部参数命名沿用 Kafka 规范(`retention.ms`、`cleanup.policy` 等)。Topic 配置优先级:**Topic 配置 > Cluster 配置 > 默认值**。

### 1. 必知配置项

| 配置项                        | 默认值              | 含义                                                |
|-------------------------------|---------------------|-----------------------------------------------------|
| `partition_count`             | 1                   | Topic 分区数(创建时确定,只能加不能减)             |
| `replication_factor`          | 1                   | 副本数(创建时确定)                                |
| `cleanup.policy`              | delete              | 清理策略:delete / compact / delete,compact         |
| `retention.ms`                | 604800000 (7 天)    | 消息保留时间(毫秒)                                |
| `retention.bytes`             | -1 (无限制)         | 单分区最大字节数,超过则删除旧消息                  |
| `segment.ms`                  | 604800000 (7 天)    | Segment 文件最大存活时间                            |
| `segment.bytes`               | 134217728 (128MB)   | Segment 文件最大字节数(Redpanda 默认 128MB,比 Kafka 小) |
| `compression.type`            | producer            | 压缩类型:none / gzip / snappy / lz4 / zstd / producer |
| `min.insync.replicas`         | 1                   | 最小同步副本数                                      |
| `max.message.bytes`           | 1048588 (~1MB)      | 单条消息最大字节数                                  |
| `message.timestamp.type`      | CreateTime          | 时间戳类型:CreateTime / LogAppendTime               |
| `retention.local.target.ms`   | -1                  | 本地存储保留时间(配合 Tiered Storage)               |
| `redpanda.remote.delete`      | true                | 是否允许从远端删除(配合 Tiered Storage)             |
| `redpanda.remote.write`       | false               | 是否启用远端写入(Tiered Storage)                   |
| `redpanda.remote.read`        | false               | 是否启用远端读取(Tiered Storage)                   |

> **与 Kafka 重要区别**:Redpanda 默认 `segment.bytes` 是 **128MB**,而 Kafka 是 **1GB**。Redpanda 设计上倾向于小 Segment,有利于快速清理与 compaction。Redpanda 还引入了 `redpanda.*` 前缀的私有参数,管理分层存储行为。

### 2. 关键配置详解

#### (1) partition_count 与 replication_factor——分区与副本

```bash
# 创建 12 分区、3 副本的 Topic
rpk topic create order-topic -p 12 -r 3

# 验证
rpk topic describe order-topic | head -5
```

推荐值:

| 场景                  | partition_count | replication_factor | 说明                              |
|-----------------------|-----------------|---------------------|-----------------------------------|
| 测试 / 本地开发       | 1~3             | 1                   | 节省磁盘                          |
| 小流量业务            | 3~6             | 3                   | 容忍 1 个 Broker 故障             |
| 中等流量              | 6~12            | 3                   | 平衡并行度与运维复杂度             |
| 高吞吐业务            | 12~50           | 3                   | 提前预留扩展空间                   |
| 超大规模 / CDC        | 50~200          | 3                   | 需要合理规划 Broker 数             |

#### (2) cleanup.policy——清理策略

```bash
# 仅基于时间/大小删除
rpk topic alter-config order-topic --set cleanup.policy=delete

# 仅做 key 合并
rpk topic alter-config user-topic --set cleanup.policy=compact

# 两者都启用
rpk topic alter-config user-topic --set cleanup.policy=delete,compact
```

三种模式:

| 模式              | 适用场景         | 行为                                 |
|-------------------|------------------|--------------------------------------|
| `delete`          | 绝大多数业务     | 超时 / 超大就删                       |
| `compact`         | 维度表、配置表   | 同一个 key 只保留最新值              |
| `delete,compact`  | 混合场景         | 先 delete,后 compact                  |

#### (3) retention.ms / retention.bytes——消息保留

```bash
# 保留 1 小时
rpk topic alter-config order-topic --set retention.ms=3600000

# 保留 30 天
rpk topic alter-config order-topic --set retention.ms=2592000000

# 单分区最大 10GB
rpk topic alter-config order-topic --set retention.bytes=10737418240
```

判断标准:

- **流式日志 / 监控埋点**:retention.ms 较短(几小时到几天)
- **业务事件 / 订单数据**:retention.ms 较长(7~30 天)
- **变更日志(CDC)**:配合 `cleanup.policy=compact` 做 key 合并
- **配合 Tiered Storage**:本地保留 `retention.local.target.ms`,云端保留 `retention.ms`(详见第十一节)

#### (4) segment.ms / segment.bytes——Segment 滚动

```bash
# 30 天滚动一次 Segment
rpk topic alter-config order-topic --set segment.ms=2592000000

# 256MB 滚动一次 Segment
rpk topic alter-config order-topic --set segment.bytes=268435456
```

> Redpanda 默认 segment.bytes 是 128MB(Kafka 默认 1GB)。小 Segment 有利于频繁 compaction,但会增多文件数量,生产环境一般上调到 256MB~512MB。

#### (5) compression.type——压缩算法

| 算法    | 压缩比 | CPU 占用 | 适用场景                |
|---------|--------|----------|-------------------------|
| none    | 1.0    | 最低     | 默认,日志无需压缩       |
| gzip    | 高     | 高       | 文本 / JSON             |
| snappy  | 中     | 低       | Google 出品,通用首选    |
| lz4     | 中     | 极低     | 追求写入吞吐            |
| zstd    | 高     | 低       | Facebook 出品,新首选    |
| producer| -      | -        | 跟随 Producer 端设置    |

推荐:线上通用选 `zstd` 或 `lz4`,既能省磁盘带宽又不会过多消耗 CPU。Redpanda 的 C++ 实现对 lz4 和 zstd 都有极致的 SIMD 优化,压缩/解压性能优于 Kafka 的 JVM 实现。

#### (6) message.timestamp.type——时间戳类型

```bash
# 创建事件时间
rpk topic alter-config order-topic --set message.timestamp.type=CreateTime

# 日志追加时间
rpk topic alter-config log-topic --set message.timestamp.type=LogAppendTime
```

两种模式:

| 模式              | 含义                                            |
|-------------------|-------------------------------------------------|
| `CreateTime`(默认)| 时间戳由 Producer 创建消息时指定                |
| `LogAppendTime`   | 时间戳由 Broker 写入消息时打上(追加时间)       |

### 3. 完整配置示例(生产级 Topic)

```bash
rpk topic create order-topic \
  -p 12 \
  -r 3 \
  --retention-ms 2592000000 \
  --compression-type zstd \
  --cleanup-policy delete \
  --min.insync.replicas 2 \
  --max-message-bytes 2097152 \
  --segment-bytes 536870912 \
  --segment-ms 604800000 \
  --message-timestamp-type CreateTime
```

---

## 四、分区分配算法(Redpanda 与 Kafka 不同)

### 1. 共同点与不同点

Redpanda 和 Kafka 都使用 `hash(key) % partition_count` 来计算消息的目标分区。但是,Redpanda 在**分区到 Broker 的分配算法**上做了独特优化。

| 维度           | Kafka                                     | Redpanda                                       |
|----------------|-------------------------------------------|------------------------------------------------|
| 消息→分区      | `hash(key) % partition_count`             | `hash(key) % partition_count`(完全一致)        |
| 分区→副本      | 自带分配器,随机起点 + 步进                | `partition_allocator` 策略                    |
| 副本摆放       | Round-Robin,支持 rack-aware               | 优化版算法,默认 rack-aware                    |
| 扩容一致性     | 哈希重分布,旧分区不动                    | 哈希重分布,旧分区不动(完全兼容)              |

### 2. Redpanda partition_allocator 策略

Redpanda 使用 `cluster::partition_allocator` 来决定每个分区的副本分布在哪些 Broker 上。它会考虑多个约束:

```text
输入:
  - 待分配分区: Topic T 的 8 个分区,每个分区需要 3 个副本
  - 集群状态: 5 个 Broker,各 Broker 的磁盘使用率、partition 数
  - 约束: 不同分区(同 Topic)的副本不能在同一个 Broker

目标:
  - 各 Broker 上 partition 数大致均衡
  - 各 Broker 上 leader 数大致均衡
  - 满足机架感知约束(若配置)
  - 单 broker 上副本数不超过 high_watermark

输出:
  Topic T 的 8 个分区 → 5 个 Broker 的分配方案
```

### 3. 分配算法核心逻辑

Redpanda 的 partition_allocator 采用 **贪心 + 局部搜索** 的策略:

```text
  1. 初始化:按当前负载对 Broker 排序(partition 数少的优先)
  2. 对每个待分配分区:
     a. 选择 partition 数最少的 Broker 作为第一个副本
     b. 选择次少的 Broker 作为第二个副本
     c. 选择再次的 Broker 作为第三个副本(若 rf=3)
     d. 检查副本分散约束(同分区不能同 Broker)
     e. 检查机架感知约束(若配置)
     f. 检查 disk 高水位约束
  3. 输出分配方案,提交到 controller
```

### 4. 分区到 Broker 的示意

```text
集群:5 个 Broker,Broker.id = 1,2,3,4,5
Topic: order-topic, 8 个分区,3 副本

分配方案(partition_allocator 输出):
Partition 0: Replicas = [1, 2, 3]
Partition 1: Replicas = [2, 3, 4]
Partition 2: Replicas = [3, 4, 5]
Partition 3: Replicas = [4, 5, 1]
Partition 4: Replicas = [5, 1, 2]
Partition 5: Replicas = [1, 3, 5]   ← 步长变化,避免聚集
Partition 6: Replicas = [2, 4, 1]
Partition 7: Replicas = [3, 5, 2]
```

> 与 Kafka 区别:Redpanda 默认所有副本都参与投票(没有 ISR/OSR 概念),副本同步延迟由 Raft 的 heartbeats 精确控制。副本摆放算法在每次新增/移除 Broker 时都会重跑,自动重平衡。

---

## 五、副本因子

### 1. replication_factor 配置

```bash
# 创建 3 副本的 Topic
rpk topic create order-topic -p 12 -r 3

# 修改副本数(只能改更大的值,且需要足够的 Broker)
rpk topic alter-config order-topic --set replication.factor=5
```

> 注意:`replication.factor` 不是动态可改的常规配置项。修改副本数实际是触发**副本再分配**,Redpanda 内部走的是 `replication_reconfiguration` 协议,可能需要数分钟到数小时。

### 2. 副本分配算法(rack-aware)

Redpanda 默认开启机架感知,通过 `redpanda.yaml` 中的 `rack` 字段配置:

```yaml
# redpanda.yaml
redpanda:
  data_directory: /var/lib/redpanda/data
  empty_seed_starts_cluster: true
  seed_servers:
    - host: { address: 10.0.0.1, port: 33145 }
    - host: { address: 10.0.0.2, port: 33145 }
    - host: { address: 10.0.0.3, port: 33145 }
```

在 Kubernetes 部署中,通过 `redpanda-operator` 的 `NodeAffinity` 或 `PodTopologySpreadConstraints` 自动注入:

```yaml
# RedpandaNodePool CR 示例
apiVersion: redpanda.vectorized.io/v1alpha1
kind: NodePool
metadata:
  name: redpanda
spec:
  replicas: 3
  topologySpreadConstraints:
    - maxSkew: 1
      topologyKey: topology.kubernetes.io/zone
      whenUnsatisfiable: DoNotSchedule
      labelSelector:
        matchLabels:
          app: redpanda
```

#### (1) 跨机架分配示意

```text
ZONE-A                ZONE-B                ZONE-C
┌────────┐            ┌────────┐            ┌────────┐
│ B1 (L) │            │ B3 (F) │            │ B5 (F) │
└────────┘            └────────┘            └────────┘
┌────────┐            ┌────────┐            ┌────────┐
│ B2 (F) │            │ B4 (F) │            │        │
└────────┘            └────────┘            └────────┘

Partition 0:  [B1 (Leader), B3 (Follower), B5 (Follower)]
             ↑ ZONE-A        ↑ ZONE-B        ↑ ZONE-C
```

#### (2) 机架感知的好处

- **避免机架级故障**:整个机架断电时,其他副本仍可服务
- **Leader 均衡**:Leader 会均匀分布到不同机架
- **Redpanda 默认开启**:相比 Kafka 需要手动配置 `broker.rack`,Redpanda 通过 topology spread 自动分配

### 3. 手工副本重分配

```bash
# 1. 列出当前副本分布
rpk topic describe order-topic

# 2. 修改副本数(触发再分配)
rpk topic alter-config order-topic --set replication.factor=5

# 3. 验证进度
rpk topic describe order-topic | grep REPLICAS
```

> Redpanda 没有像 Kafka `kafka-reassign-partitions.sh` 那样灵活的"按分区细粒度指定副本"工具。副本再分配由 partition_allocator 自动决策,运维上无法手工指定副本位置。这是有意为之的设计:简化运维,但牺牲了定制能力。

---

## 六、自动创建 Topic(auto.create.topics.enable)

### 1. Kafka 与 Redpanda 的差异

| 维度                 | Kafka                                  | Redpanda                                    |
|----------------------|----------------------------------------|---------------------------------------------|
| 是否支持自动创建      | 是(`auto.create.topics.enable=true`)   | **是,且强制开启**(默认 `true`)             |
| 默认行为              | Producer / Consumer 写入未知 Topic 自动创建 | Producer 写入未知 Topic 自动创建         |
| 默认副本数            | `default.replication.factor`(默认 1)   | `default_topic_replications`(默认 1)        |
| 默认分区数            | `num.partitions`(默认 1)               | `default_topic_partitions`(默认 1)          |
| 是否可关闭            | 可关闭                                 | **可关闭(`--set` 调整)**                  |

> **重要区别**:Kafka 默认就开启了自动创建;Redpanda 同样默认开启,但提供了更细粒度的控制。

### 2. Redpanda 自动创建相关配置

```bash
# 关闭自动创建
rpk cluster config set auto_create_topics_enabled=false

# 设置自动创建时的默认副本数
rpk cluster config set default_topic_replications=3

# 设置自动创建时的默认分区数
rpk cluster config set default_topic_partitions=12

# 设置自动创建时的默认保留时间
rpk cluster config set default_topic_retention_ms=604800000

# 设置自动创建时的默认压缩
rpk cluster config set default_topic_compression=zstd
```

### 3. 自动创建实战演示

```bash
# 1. Producer 写入一个未创建的 Topic
echo "test message" | rpk topic produce auto-created-topic

# 输出:
# Producing to 'auto-created-topic'
# Message produced (offset 0)

# 2. 验证 Topic 已自动创建
rpk topic list | grep auto-created-topic

# 输出:
# auto-created-topic  1  1   ← 1 分区,1 副本
```

### 4. 生产建议

| 场景            | 推荐做法                                                    |
|-----------------|-------------------------------------------------------------|
| 测试环境        | 保持自动创建开启,方便调试                                  |
| 生产环境        | **强烈建议关闭**自动创建,所有 Topic 必须显式创建           |
| 受限环境        | 自动创建 + 默认副本数 ≥ 3,避免出现单副本 Topic             |
| 多租户环境      | 关闭自动创建,Topic 由平台统一管理                          |

```bash
# 生产环境初始化推荐配置
rpk cluster config set auto_create_topics_enabled=false
rpk cluster config set default_topic_replications=3
rpk cluster config set default_topic_partitions=12
```

---

## 七、Topic 配额(kafka_quota)

### 1. 配额类型

Redpanda 兼容 Kafka 的配额机制,通过 `kafka_quota` 机制限制客户端流量:

| 配额维度       | 配置键                              | 单位            |
|----------------|--------------------------------------|-----------------|
| 生产带宽       | `kafka_produce_bytes_per_second`     | byte/s          |
| 消费带宽       | `kafka_fetch_bytes_per_second`       | byte/s          |
| 请求数         | `kafka_request_percent`              | 0~100 (%)       |

### 2. 客户端配额(按 client_id)

```bash
# 设置某个 client_id 的生产带宽上限为 10MB/s
rpk cluster config set kafka_client_group_byte_rate_quota=10485760

# 设置某个 client_id 的请求数上限为 50%
rpk cluster config set kafka_client_group_request_percent_quota=50
```

### 3. 用户配额(基于 SASL)

```bash
# 为特定 SASL 用户设置生产配额
rpk cluster config set kafka_user_group_byte_rate_quota=5242880
```

### 4. 配额生效流程

```text
Client 发送 Produce 请求
       │
       ▼
Broker 检查 quota
       │
       ├── 未超限 ──► 正常处理
       │
       └── 超限 ──► 等待令牌桶 / 拒绝请求
              │
              └── 返回 THROTTLED 响应
```

### 5. 监控配额命中

```bash
# 监控指标: kafka_request_quota_rejected_total
# 监控指标: kafka_request_quota_throttle_time_total

# 通过 Prometheus 暴露
rpk cluster config set enable_metrics_reporter=true

# 查看当前配置
rpk cluster config get | grep -i quota
```

---

## 八、分区扩容

### 1. 为什么要扩容

- 业务增长导致单分区吞吐瓶颈
- 增加消费者并行度
- 退役老 Broker 时重平衡

### 2. 扩容命令

```bash
# 将 order-topic 从 3 分区扩到 6 分区
rpk topic add-partitions order-topic --num-to-add 3

# 输出:
# PARTITIONS
# 6
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

#### (4) Kafka 兼容性

Redpanda 的扩容行为**与 Kafka 完全一致**:

| 行为                         | Kafka | Redpanda |
|------------------------------|-------|----------|
| 旧分区数据保留                | 是    | 是       |
| 旧消息不重新分布              | 是    | 是       |
| 新消息按新分区数 hash         | 是    | 是       |
| 顺序破坏(同 key 跨分区)     | 是    | 是       |
| 消费者需要 Rebalance          | 是    | 是       |

> 因此:**任何从 Kafka 迁移到 Redpanda 的应用,扩容行为无需调整代码**。

### 4. 分区再分配

新增分区后,新分区需要被分配到 Broker 上。Redpanda 通过 partition_allocator 自动完成:

```text
1. Controller 收到 add-partitions 请求
2. 对每个新分区,调用 partition_allocator 选择副本 Broker
3. 在新分区的副本上创建 Raft group
4. 新副本从空 offset 开始,等待 Producer 写入
5. 客户端拉取到新的元数据,后续消息按新分区数 hash
```

### 5. 扩容流程图

```text
Producer                 Controller                 Brokers
   │                        │                         │
   │ add-partitions 请求    │                         │
   ├───────────────────────►│                         │
   │                        │ partition_allocator 选择 │
   │                        ├────────────────────────►│
   │                        │                         │
   │                        │ 创建 Raft group         │
   │                        ├────────────────────────►│
   │                        │                         │
   │                        │ 更新集群元数据           │
   │                        │◄────────────────────────┤
   │                        │                         │
   │ 返回新分区信息         │                         │
   │◄───────────────────────┤                         │
   │                        │                         │
   │ 按新分区数 hash 写入  │                         │
   ├─────────────────────────────────────────────────────►│
   │                        │                         │
   │ Consumer 收到新元数据  │                         │
   │◄──────────────────────────────────────────────────┤
   │                        │                         │
   │ 触发 Rebalance         │                         │
```

### 6. 扩容最佳实践

| 做法                                      | 说明                                                |
|-------------------------------------------|-----------------------------------------------------|
| **初期就给足分区数**                      | 避免频繁扩容                                        |
| **避免扩容跨整数倍**                      | 扩容时尽量使 ratio = 整数倍,减少 key 分散          |
| **业务接受临时不一致**                    | 扩容在业务低峰期执行,降低顺序敏感场景的影响        |
| **提前通知消费者**                        | Rebalance 会导致短时消费停滞,通知业务方            |
| **预留扩容比例**                          | 假设 30% 增长,直接给 1.5x 分区数,避免短期内再次扩容 |

---

## 九、Segment 文件管理

### 1. Redpanda 的存储目录

Redpanda 默认数据目录是 `/var/lib/redpanda/data`,内部按 Topic-Partition 组织:

```text
/var/lib/redpanda/data/
  └── redpanda/
      └── kafka/
          └── 0_2_1/                                  ← namespace 目录
              ├── order-topic-0_2/                   ← partition 目录(带 revision)
              │   ├── 0-1-1-0.log                     ← Segment 数据文件
              │   ├── 0-1-1-0.index                  ← Offset 索引
              │   ├── 0-1-1-0.timeindex              ← 时间戳索引
              │   ├── 0-1-2-1048576.log              ← 下一个 Segment
              │   ├── 0-1-2-1048576.index
              │   └── 0-1-2-1048576.timeindex
              ├── order-topic-1_2/
              │   ├── 0-1-1-0.log
              │   └── ...
              ├── __consumer_offsets/
              │   └── ...
              └── __redpanda_internal_topic/
                  └── ...
```

> **文件命名规则**:`<base-offset>-1-<last-byte>-1.log`,如 `0-1-1-0.log` 表示该 Segment 第一条消息 Offset 是 0,当前文件大小 0 字节。

### 2. Segment 文件结构

每个 Segment 由三件套组成:

```text
0-1-1-0.log          # 数据文件(顺序追加的 record batch)
0-1-1-0.index        # Offset 索引(Offset → 物理位置)
0-1-1-0.timeindex    # 时间戳索引(Timestamp → Offset)
```

### 3. Segment 文件详解

#### (1) .log 文件

存储消息的实际内容,内部由若干 RecordBatch 组成,格式与 Kafka 兼容:

```text
┌─────────────────────────────────────────────────────────┐
│ Log Segment (例: 0-1-1-0.log)                            │
├─────────────────────────────────────────────────────────┤
│                                                          │
│ RecordBatch 1                                            │
│ ┌──────────────────────────────────────────────────┐    │
│ │ Batch Base Offset (8B)    │ 0                    │    │
│ │ Batch Length (4B)         │ 900                   │    │
│ │ Partition Leader Epoch (4B) │ 1                  │    │
│ │ Magic (1B)                │ 2                     │    │
│ │ CRC (4B)                  │ 0xAABBCCDD           │    │
│ │ Attributes (2B)           │ 0x0000 (no compress) │    │
│ │ Last Offset Delta (4B)    │ 99                    │    │
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
│ ...                                                      │
└─────────────────────────────────────────────────────────┘
```

#### (2) .index 文件(OffsetIndex)

保存"Offset → 物理位置"的稀疏索引,支持二分查找。

```text
┌────────────────┬────────────────┬────────────────────┐
│ relativeOffset │ physicalPos    │ description        │
│ (4B, varint)   │ (4B, varint)   │                    │
├────────────────┼────────────────┼────────────────────┤
│ 0              │ 0              │ 第 0 条消息在 log  │
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
│ 1700001500000  │ 12288            │
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

- **segment.bytes**:当前 Segment 超过配置大小(Redpanda 默认 128MB)
- **segment.ms**:当前 Segment 超过配置时间(默认 7 天)
- **index.interval.bytes**:索引项间隔超过 4096 字节

```bash
# 修改 Segment 滚动大小为 256MB
rpk topic alter-config order-topic --set segment.bytes=268435456

# 修改 Segment 滚动时间为 30 天
rpk topic alter-config order-topic --set segment.ms=2592000000
```

### 6. 与 Kafka 索引的差异

| 维度           | Kafka                          | Redpanda                            |
|----------------|--------------------------------|-------------------------------------|
| Offset 索引    | 紧凑索引(sparkly,4096 字节一项)| 同 Kafka(完全兼容)                  |
| 时间戳索引     | 紧凑索引                       | 同 Kafka                            |
| 索引文件结构   | `.index` / `.timeindex`       | `.index` / `.timeindex`             |
| 默认 segment.bytes | 1GB                        | 128MB(更激进)                       |

---

## 十、日志清理策略

Redpanda 提供与 Kafka 兼容的两种日志清理策略:**delete**(基于时间/大小)和 **compact**(基于 key 合并)。

### 1. delete(基于时间/大小)

最常用策略,过期或超大的消息被删除。

```text
清理逻辑:
  1. 后台 compaction 任务检查所有 Partition
  2. 命中以下任一条件即触发删除:
     - 消息 timestamp + retention.ms < 当前时间
     - 当前 Partition 累计大小 > retention.bytes
  3. 删除满足条件的整个 Segment 文件
```

#### (1) 基于时间

```bash
rpk topic alter-config order-topic --set retention.ms=86400000

# 含义:仅保留 1 天内的消息
# 行为:每分钟检查一次,删除 timestamp + 86400000ms < 当前时间的消息
```

#### (2) 基于大小

```bash
rpk topic alter-config order-topic --set retention.bytes=1073741824

# 含义:单分区最大 1GB
# 行为:超过 1GB 后,从最旧的 Segment 开始删除,直到 ≤ 1GB
```

#### (3) 实际例子

```text
order-topic-0
├── 0-1-1-0.log              (1GB, 即将被删除)
├── 1048576-1-1-1048576.log  (1GB, 即将被删除)
├── 2097152-1-1-2097152.log  (800MB, 保留)
└── active_segment             (active)

retention.bytes=2GB
总占用 = 1 + 1 + 0.8 = 2.8GB > 2GB
→ 删除最旧的 Segment 直到 ≤ 2GB
→ 保留 1048576-1-1-1048576.log(1GB) 和 2097152-1-1-2097152.log(0.8GB)
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
rpk topic create user-topic \
  -p 3 \
  -r 3 \
  --cleanup-policy compact \
  --segment-ms 3600000 \
  --delete-retention-ms 86400000
```

#### (2) 关键配置

| 配置                         | 默认值 | 含义                                            |
|------------------------------|--------|-------------------------------------------------|
| `cleanup.policy`             | delete | 改为 compact 或 delete,compact                  |
| `min.cleanable.dirty.ratio`  | 0.2    | 脏数据(待压缩)占比超过此值触发压缩             |
| `segment.ms`                 | 7 天   | compact 模式下建议缩短,更频繁触发              |
| `delete.retention.ms`        | 24h    | tombstone(墓碑) 保留时间,过期后真正删除         |
| `min.compaction.lag.ms`      | 0      | 消息最小存活时间,小于此时间的不压缩            |

#### (3) compact 触发流程

```text
后台 compaction 任务 (housekeeping_loop)
   │
   ▼
1. 选择 dirty ratio > min.cleanable.dirty.ratio 的 Partition
   │
   ▼
2. 标记 .log 末尾的 dirty 区域
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

## 十一、Tiered Storage 集成(Redpanda 核心亮点)

Tiered Storage(分层存储)是 Redpanda 的标志性特性,允许把历史数据卸载到云对象存储(S3 / Azure Blob / GCS),本地只保留热数据,**磁盘用量与保留时间解耦**。

### 1. 为什么需要 Tiered Storage

```text
传统架构(只有本地磁盘):
  磁盘容量 = 峰值吞吐 × 保留时间
  例:1 GB/s × 7 天 = 605 TB(磁盘需求)

分层存储架构:
  本地磁盘 = 峰值吞吐 × 热数据保留时间(几小时)
  云存储   = 峰值吞吐 × 冷数据保留时间(任意)
  例:1 GB/s × 1 小时 = 3.6 TB(本地) + 605 TB(云)
```

### 2. 支持的云存储后端

| 云厂商       | 后端类型              | 协议                          |
|--------------|------------------------|-------------------------------|
| AWS          | S3 / S3-compatible    | S3 API                        |
| Azure        | Blob Storage           | Azure Blob API                |
| GCP          | Cloud Storage          | GCS API                       |
| MinIO        | S3-compatible         | S3 API                        |
| Ceph RGW     | S3-compatible         | S3 API                        |
| 阿里云 OSS   | S3-compatible         | S3 API                        |

### 3. Tiered Storage 核心配置

```yaml
# redpanda.yaml
redpanda:
  # 启用 Tiered Storage
  cloud_storage_enabled: true
  cloud_storage_bucket: "redpanda-prod-data"
  cloud_storage_region: "us-east-1"
  cloud_storage_access_key: "AKIAIOSFODNN7EXAMPLE"
  cloud_storage_secret_key: "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"

  # S3 endpoint(自定义 S3 兼容服务时)
  cloud_storage_api_endpoint: "https://s3.amazonaws.com"
  cloud_storage_api_endpoint_port: 443

  # 性能调优
  cloud_storage_max_segment_size: 268435456    # 256MB,大于此值的 Segment 直接上传
  cloud_storage_segment_upload_timeout: 30000  # Segment 上传超时
  cloud_storage_manifest_segment_upload_timeout: 10000
  cloud_storage_idle_timeout_ms: 10000          # 空闲多久触发上传

  # 上传限速
  cloud_storage_upload_ctrl_max_shards: 20
  cloud_storage_upload_ctrl_min_shares: 100
  cloud_storage_upload_ctrl_max_shares: 1000

  # 读取缓存
  cloud_storage_cache_size: 10737418240        # 10GB 本地缓存
  cloud_storage_cache_directory: /var/lib/redpanda/cache

  # 回收控制
  cloud_storage_recovery_timeout: 30000
```

### 4. Topic 维度配置

```bash
# 启用远端写入
rpk topic alter-config order-topic --set redpanda.remote.write=true

# 启用远端读取(允许消费历史数据)
rpk topic alter-config order-topic --set redpanda.remote.read=true

# 启用远端删除(允许 Topic 删除时清理云端数据)
rpk topic alter-config order-topic --set redpanda.remote.delete=true

# 设置本地保留时间(本地最多保留 1 天)
rpk topic alter-config order-topic --set retention.local.target.ms=86400000

# 设置本地保留字节(本地最多保留 100GB)
rpk topic alter-config order-topic --set retention.local.target.bytes=107374182400
```

### 5. 分层上传与下载流程

#### (1) 分层上传流程

```text
Producer 写入消息
       │
       ▼
本地 Segment 滚动
       │
       ▼
housekeeping_loop 检测
       │
       ▼
满足上传条件 ──► 上传到云存储
       │
       ├──► 序列化为 manifest(元数据)
       ├──► 压缩(可选 zstd)
       ├──► 加密(可选 AES-256)
       ├──► 写入 S3
       │
       ▼
更新本地 manifest
       │
       ▼
下次 compaction 删除本地旧 Segment
```

#### (2) 分层下载流程

```text
Consumer 请求 offset X
       │
       ▼
本地查找 ──► 命中 ──► 直接读取
       │
       └─► 未命中
              │
              ▼
       查询 manifest
              │
              ▼
       从云存储下载 Segment
              │
              ▼
       写入本地缓存目录
              │
              ▼
       返回 Consumer
```

### 7. 完整配置示例(S3 + Tiered Storage)

```yaml
# /etc/redpanda/redpanda.yaml
redpanda:
  data_directory: /var/lib/redpanda/data
  empty_seed_starts_cluster: true
  seed_servers:
    - host: { address: 10.0.0.1, port: 33145 }
    - host: { address: 10.0.0.2, port: 33145 }
    - host: { address: 10.0.0.3, port: 33145 }

  # 启用 Tiered Storage
  cloud_storage_enabled: true
  cloud_storage_bucket: "company-redpanda-prod"
  cloud_storage_region: "cn-north-1"
  cloud_storage_api_endpoint: "https://s3.cn-north-1.amazonaws.com.cn"
  cloud_storage_access_key: "AKIA_REDACTED"
  cloud_storage_secret_key: "SECRET_REDACTED"

  # 性能调优
  cloud_storage_cache_size: 21474836480       # 20GB 本地缓存
  cloud_storage_cache_directory: /var/lib/redpanda/cache
  cloud_storage_max_segment_size: 536870912   # 512MB
  cloud_storage_idle_timeout_ms: 5000         # 5 秒空闲后上传
  cloud_storage_upload_ctrl_min_shares: 200
  cloud_storage_upload_ctrl_max_shares: 2000

rpk:
  coredump_dir: /var/lib/redpanda/coredump
  enable_memory_locking: true
  overprovisioned: false
  tune_aio_events: true
  tune_clocksource: true
  tune_cpu: true
  tune_disk_irq: true
  tune_disk_nomerges: true
  tune_disk_scheduler: true
  tune_disk_write_cache: true
  tune_network: true
  tune_swappiness: true
  tune_transparent_hugepages: true
```

对应的 Topic 配置:

```bash
# 创建 Topic 时直接启用 Tiered Storage
rpk topic create order-topic \
  -p 12 \
  -r 3 \
  --set redpanda.remote.write=true \
  --set redpanda.remote.read=true \
  --set redpanda.remote.delete=true \
  --set retention.local.target.ms=86400000 \
  --set retention.ms=2592000000 \
  --compression-type zstd

# 验证配置
rpk topic describe-config order-topic | grep remote
rpk topic describe-config order-topic | grep retention
```

---

## 十二、实战案例

### 1. 创建生产级 Topic(订单场景)

```bash
rpk topic create order-topic \
  -p 12 \
  -r 3 \
  --retention-ms 2592000000 \
  --compression-type zstd \
  --cleanup-policy delete \
  --min-insync-replicas 2 \
  --max-message-bytes 2097152 \
  --segment-bytes 536870912 \
  --segment-ms 604800000

# 验证
rpk topic describe order-topic
rpk topic describe-config order-topic
```

决策依据:

| 配置项        | 取值      | 决策依据                                                |
|----------------|-----------|------------------------------------------------------|
| partitions     | 12        | 峰值 5 万 TPS,单分区 3 万 TPS,需 12 个               |
| rf             | 3         | 3 副本,容忍 1 个 Broker 故障                         |
| retention      | 30 天     | 业务需要回溯 30 天订单                               |
| compression    | zstd      | 高压缩比 + 低 CPU,节省带宽                           |
| min.isr        | 2         | 至少 2 副本同步,容忍 1 副本故障                      |
| max.bytes      | 2 MB      | 订单详情可能包含较多字段,放宽限制                    |
| segment        | 512MB / 7 天 | 控制单文件大小,清理粒度细些                       |

### 2. 完整 Docker Compose 集群示例

#### (1) docker-compose.yml

```yaml
version: '3.8'

services:
  redpanda-0:
    image: docker.redpanda.com/redpandadata/redpanda:v23.3.1
    container_name: redpanda-0
    hostname: redpanda-0
    command:
      - redpanda
      - start
      - --overprovisioned
      - --smp=1
      - --memory=1G
      - --reserve-memory=0M
      - --node-id=0
      - --check=false
      - --mode=dev-container
    ports:
      - "9092:9092"
      - "9644:9644"
    volumes:
      - redpanda-0-data:/var/lib/redpanda/data
    healthcheck:
      test: ["CMD", "rpk", "cluster", "health"]
      interval: 5s
      timeout: 10s
      retries: 5
    networks:
      - redpanda-net

  redpanda-1:
    image: docker.redpanda.com/redpandadata/redpanda:v23.3.1
    container_name: redpanda-1
    hostname: redpanda-1
    command:
      - redpanda
      - start
      - --overprovisioned
      - --smp=1
      - --memory=1G
      - --reserve-memory=0M
      - --node-id=1
      - --check=false
      - --seeds=redpanda-0:33145
      - --mode=dev-container
    ports:
      - "9093:9092"
      - "9645:9644"
    volumes:
      - redpanda-1-data:/var/lib/redpanda/data
    depends_on:
      - redpanda-0
    networks:
      - redpanda-net

  redpanda-2:
    image: docker.redpanda.com/redpandadata/redpanda:v23.3.1
    container_name: redpanda-2
    hostname: redpanda-2
    command:
      - redpanda
      - start
      - --overprovisioned
      - --smp=1
      - --memory=1G
      - --reserve-memory=0M
      - --node-id=2
      - --check=false
      - --seeds=redpanda-0:33145
      - --mode=dev-container
    ports:
      - "9094:9092"
      - "9646:9644"
    volumes:
      - redpanda-2-data:/var/lib/redpanda/data
    depends_on:
      - redpanda-0
    networks:
      - redpanda-net

  console:
    image: docker.redpanda.com/redpandadata/console:v2.3.4
    container_name: redpanda-console
    depends_on:
      - redpanda-0
    environment:
      CONFIG_FILEPATH: /etc/redpanda-console/config.yaml
    volumes:
      - ./console-config.yaml:/etc/redpanda-console/config.yaml
    ports:
      - "8080:8080"
    networks:
      - redpanda-net

volumes:
  redpanda-0-data:
  redpanda-1-data:
  redpanda-2-data:

networks:
  redpanda-net:
    driver: bridge
```

#### (2) console-config.yaml

```yaml
kafka:
  brokers:
    - redpanda-0:9092
    - redpanda-1:9092
    - redpanda-2:9092
  schemaRegistry:
    enabled: false

redpanda:
  adminApi:
    enabled: true
    urls:
      - http://redpanda-0:9644
      - http://redpanda-1:9644
      - http://redpanda-2:9644
```

#### (3) 启动集群

```bash
docker-compose up -d

# 等待健康检查通过(约 10~30 秒)
docker-compose ps

# 验证集群状态
docker exec -it redpanda-0 rpk cluster info

# 输出:
# CLUSTER
# =======
# redpanda.5d2e3c1b
#
# BROKERS
# =======
# ID    HOST          PORT
# 0*    redpanda-0    9092
# 1     redpanda-1    9092
# 2     redpanda-2    9092
```

### 3. 创建带 Tiered Storage 的 Topic

```bash
# 1. 创建 Topic
rpk topic create orders-ts \
  -p 12 \
  -r 3 \
  --set redpanda.remote.write=true \
  --set redpanda.remote.read=true \
  --set redpanda.remote.delete=true \
  --set retention.local.target.ms=86400000 \
  --set retention.ms=2592000000 \
  --compression-type zstd

# 2. 验证 Tiered Storage 状态
rpk topic describe-config orders-ts | grep -E "remote|retention"

# 输出:
# NAME                              VALUE      SOURCE
# redpanda.remote.delete            true       TOPIC_CONFIG
# redpanda.remote.read              true       TOPIC_CONFIG
# redpanda.remote.write             true       TOPIC_CONFIG
# retention.local.target.bytes      -1         DEFAULT_CONFIG
# retention.local.target.ms         86400000   TOPIC_CONFIG
# retention.ms                      2592000000 TOPIC_CONFIG
# retention.bytes                   -1         DEFAULT_CONFIG
```

### 4. 配额管理实战

```bash
# 1. 设置默认生产带宽上限(每个 client_id)
rpk cluster config set kafka_client_group_byte_rate_quota=10485760

# 2. 设置默认消费带宽上限
rpk cluster config set kafka_client_group_fetch_byte_rate_quota=20971520

# 3. 设置请求数占比上限
rpk cluster config set kafka_client_group_request_percent_quota=50

# 4. 查看当前所有配额配置
rpk cluster config get | grep -i quota

# 5. 验证:用 rpk 压测观察是否触发限流
rpk topic produce order-topic < big-input.txt &
rpk topic consume order-topic --num 1000000
```

### 5. 分区扩容实战

```bash
# 1. 当前配置: 4 分区
rpk topic describe order-topic | head -5

# 2. 扩容到 12 分区
rpk topic add-partitions order-topic --num-to-add 8

# 输出:
# PARTITIONS
# 12

# 3. 验证
rpk topic describe order-topic | head -5

# 输出:
# NAME        PARTITIONS  REPLICAS
# order-topic 12          3

# 4. 观察消费者 Rebalance
#    - 监控 consumer group lag
#    - 监控 consumer count
#    - 业务可能经历 1~10 秒的 STW

# 5. 验证 key 散列
#    使用 rpk consume 抽样查看 offset 分布
rpk topic consume order-topic --num 10000 --print-key
```

### 6. compact 模式实战(配置中心场景)

```bash
# 1. 创建配置 Topic
rpk topic create config-topic \
  -p 3 \
  -r 3 \
  --cleanup-policy compact \
  --segment-ms 3600000 \
  --delete-retention-ms 86400000

# 2. 生产配置变更(同一 key 多次更新)
echo "db.host:db1.local" | rpk topic produce config-topic --parse-key --separator ":"
echo "db.port:5432" | rpk topic produce config-topic --parse-key --separator ":"
echo "db.host:db2.local" | rpk topic produce config-topic --parse-key --separator ":"  ← 覆盖 db.host
echo "db.port:5433" | rpk topic produce config-topic --parse-key --separator ":"  ← 覆盖 db.port

# 3. 同一 key 只保留最新
rpk topic consume config-topic --offset start --print-key

# 输出:
# KEY        VALUE
# db.host    db1.local    ← 旧版本
# db.port    5432          ← 旧版本
# db.host    db2.local    ← 最新
# db.port    5433          ← 最新
```

### 7. 日常运维命令汇总

```bash
# 查看集群整体状态
rpk cluster info
rpk cluster health

# 查看所有 Topic 摘要
rpk topic list

# 查看所有 Topic 详情
rpk topic describe -A

# 查看消费者组
rpk group list

# 查看 lag(消费滞后)
rpk group describe order-consume

# 重置消费位置
rpk group offset-reset order-consume --topic order-topic --to earliest

# 查看 Topic 配置
rpk topic describe-config order-topic

# 修改 broker 全局配置
rpk cluster config set log_segment_size=268435456

# 查看 broker 配置
rpk cluster config get | grep -i segment

# 查看监控指标
rpk cluster config get | grep -i metrics
```

---

## 十三、核心要点速记

- **Topic 是逻辑概念,Partition 是物理分片**:Topic = N 个 Partition,所有 IO 都发生在 Partition 级别
- **rpk topic 是 Redpanda Topic 管理的入口**:`create / list / describe / delete / add-partitions / alter-config / describe-config / produce / consume` 九大操作
- **Partition 数只能增加,不能减少**:减少分区会丢数据,Redpanda 直接不支持
- **消息路由算法与 Kafka 完全一致**:`hash(key) % partition_count`,扩容后旧消息不动,新消息按新分区数重 hash
- **副本分配算法 partition_allocator**:Redpanda 自研,默认开启机架感知,通过 topology spread 自动分布
- **默认副本数**:生产环境强烈建议 ≥ 3,容忍 1 个 Broker 故障
- **min.insync.replicas 配合 `acks=all`**:是数据不丢的最低保障
- **Redpanda 默认 segment.bytes 是 128MB**(Kafka 是 1GB):小 Segment 有利于快速清理与 compaction
- **三种清理策略**:`delete`(时序数据)、`compact`(状态数据)、`delete,compact`(组合)
- **Tiered Storage 是 Redpanda 的标志性特性**:允许把历史数据卸载到 S3 / Azure Blob / GCS,本地只保留热数据
- **Tiered Storage Topic 维度配置**:`redpanda.remote.write / read / delete`、`retention.local.target.ms / bytes`
- **自动创建 Topic** 默认开启,生产环境**强烈建议关闭**:`rpk cluster config set auto_create_topics_enabled=false`
- **配额管理** 通过 `kafka_client_group_byte_rate_quota` 限制客户端流量
- **扩容前先评估影响**:哈希分区键失效、消费者 Rebalance、消息顺序破坏
- **扩容行为与 Kafka 完全兼容**:任何从 Kafka 迁移的应用,扩容行为无需调整代码
- **Topic 核心配置项**:`retention.ms`、`cleanup.policy`、`min.insync.replicas`、`compression.type`、`max.message.bytes`
- **生产压缩推荐 zstd 或 lz4**:Redpanda 的 C++ 实现对 lz4/zstd 有极致 SIMD 优化,压缩/解压性能优于 Kafka
- **删除 Topic 不可逆**:执行前务必确认业务无依赖
- **rpk topic describe 输出自带 LOG-START-OFFSET 与 HIGH-WATERMARK**:无需额外命令,比 Kafka 更方便
- **副本同步走 Raft**:所有读写请求都先到 Leader,Follower 通过 Raft 协议同步,Redpanda 没有 ISR/OSR 概念
- **段文件命名规则**:`<base-offset>-1-<last-byte>-1.log`,如 `0-1-1-0.log` 表示该 Segment 第一条消息 Offset 是 0
- **扩容最佳实践**:初期给足分区数、避免扩容跨非整数倍、业务低峰期执行、提前通知消费者
- **rpk 调试三件套**:`rpk cluster info`(集群状态)、`rpk cluster health`(健康检查)、`rpk topic describe`(Topic 详情)