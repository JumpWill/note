# Kafka Producer 详解

## 一、Producer 概述

### 1.1 什么是 Kafka Producer

**Kafka Producer** 是 Kafka 客户端的核心组件之一,负责将业务数据(消息)发布到 Kafka 集群的指定 Topic 中。每一条发送到 Kafka 的消息都必须经过 Producer 完成序列化、分区决策、批量打包、网络发送等流程。

Producer 的核心定位:

- **数据入口**:所有进入 Kafka 集群的数据都来自 Producer,Consumer 只负责读取。
- **异步发送**:Producer 默认采用异步发送模式,通过累加器(Accumulator)和 Sender 线程解耦业务线程与网络 I/O。
- **可水平扩展**:Producer 实例无状态,可以通过并行启动多个实例提升整体吞吐。
- **可配置策略丰富**:序列化、分区、压缩、重试、幂等、事务、拦截器均可在客户端灵活定制。

### 1.2 Producer 的关键能力

| 能力           | 说明                                                                  |
|----------------|-----------------------------------------------------------------------|
| 批量发送       | 自动将多条消息合并为 RecordBatch,显著提升吞吐                          |
| 异步发送       | 基于 Future 与回调,不阻塞业务线程                                     |
| 分区路由       | 支持 Key Hash、轮询、自定义分区策略                                    |
| 压缩           | 支持 none / gzip / snappy / lz4 / zstd                                |
| 幂等           | enable.idempotence=true 防止单分区重复                                 |
| 事务           | transactional.id 实现跨分区、跨主题的原子写入                          |
| 拦截器扩展     | ProducerInterceptor 可在发送前后注入业务逻辑                          |
| 安全           | SSL/SASL 加密、PLAIN/SCRAM 认证                                        |

### 1.3 Producer 与其他组件的关系

```text
┌─────────────────────────────────────────────────────────────────────┐
│                          Kafka 客户端全景                            │
│                                                                     │
│   ┌──────────────┐    send()     ┌────────────────┐                 │
│   │   业务线程    │ ───────────► │   Producer     │                 │
│   └──────────────┘              │  (KafkaProducer)│                 │
│                                  └───────┬────────┘                 │
│                                          │                          │
│                          ┌───────────────┼───────────────┐          │
│                          ▼               ▼               ▼          │
│                  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐    │
│                  │ Interceptor │ │ Serializer  │ │ Partitioner │    │
│                  └─────────────┘ └─────────────┘ └─────────────┘    │
│                                          │                          │
│                                          ▼                          │
│                                  ┌──────────────────┐                │
│                                  │   Accumulator    │ RecordBatch    │
│                                  │  (32MB 默认)     │                │
│                                  └─────────┬────────┘                │
│                                            │                         │
│                                            ▼                         │
│                                  ┌──────────────────┐                │
│                                  │  Sender Thread   │                │
│                                  │  NetworkClient   │                │
│                                  └─────────┬────────┘                │
│                                            │                         │
└────────────────────────────────────┼────────────────────────────────────┘
                                     ▼
                       ┌──────────────────────────────┐
                       │       Kafka Broker 集群       │
                       │  Topic-A → Partition 0..N    │
                       └──────────────────────────────┘
```

---

## 二、Producer 完整发送流程

### 2.1 整体流程概览

一条消息从业务调用 `send()` 到真正写入 Broker,会经过以下完整链路:

```text
Producer.send(ProducerRecord)
       │
       ▼
[1] ProducerInterceptor.onSend()         ← 拦截器:可修改/增强消息
       │
       ▼
[2] Serializer.serialize(key, value)      ← 序列化:对象 → 字节数组
       │
       ▼
[3] Partitioner.partition(...)            ← 分区器:决定写入哪个 Partition
       │
       ▼
[4] Append to Accumulator(RecordBatch)   ← 累加器:按 (Topic-Partition) 缓存
       │
       ▼
[5] Sender Thread poll batches           ← 发送线程:批量拉取
       │
       ▼
[6] NetworkClient.send() → Broker         ← 网络 I/O:经 Selector 通道发出
       │
       ▼
[7] Broker 写入 → 副本同步 → 应答
       │
       ▼
[8] Client Response → MetadataResponse
       │
       ▼
[9] ProducerInterceptor.onAcknowledgement() ← 拦截器:服务端确认后回调
       │
       ▼
[10] Future / Callback 通知业务线程      ← 业务侧感知结果
```

### 2.2 详细时序图

```text
时序图(简化的 Producer 发送时序)

业务线程                KafkaProducer        Interceptor       Serializer       Partitioner       Accumulator       Sender Thread       Broker
   │                        │                     │               │                │                │                  │              │
   │  send(record)          │                     │               │                │                │                  │              │
   │ ─────────────────────► │                     │               │                │                │                  │              │
   │                        │  waitForMetadata     │               │                │                │                  │              │
   │                        │ (异步更新元数据)     │               │                │                │                  │              │
   │                        │                     │               │                │                │                  │              │
   │                        │  onSend(record)     │               │                │                │                  │              │
   │                        │ ──────────────────► │               │                │                │                  │              │
   │                        │                     │               │                │                │                  │              │
   │                        │  serialize(key)     │               │                │                │                  │              │
   │                        │ ──────────────────────────────────► │                │                │                  │              │
   │                        │                     │               │                │                │                  │              │
   │                        │  serialize(value)   │               │                │                │                  │              │
   │                        │ ──────────────────────────────────► │                │                │                  │              │
   │                        │                     │               │                │                │                  │              │
   │                        │  partition(topic, key, value, cluster)               │                │                  │              │
   │                        │ ─────────────────────────────────────────────────────►│                │                  │              │
   │                        │                     │               │                │  return partition                │              │
   │                        │                     │               │                │ ──────────────► │                  │              │
   │                        │                     │               │                │                │                  │              │
   │                        │  append(partition, RecordBatch)                       │                │                  │              │
   │                        │ ──────────────────────────────────────────────────────┼──────────────► │                  │              │
   │                        │                     │               │                │                │ 内存中缓存       │              │
   │                        │                     │               │                │                │ (按 TP 分组)     │              │
   │                        │  return Future                                                              │                  │              │
   │ ◄───────────────────── │                     │               │                │                │                  │              │
   │                        │                     │               │                │                │                  │              │
   │ (业务线程可继续 send)   │                     │               │                │                │                  │              │
   │                        │                     │               │                │                │  ready check     │              │
   │                        │                     │               │                │                │  (batch.size    │              │
   │                        │                     │               │                │                │   or linger.ms) │              │
   │                        │                     │               │                │                │ ──────────────► │              │
   │                        │                     │               │                │                │                  │              │
   │                        │                     │               │                │                │                  │  send batches │
   │                        │                     │               │                │                │                  │ ────────────►│
   │                        │                     │               │                │                │                  │              │
   │                        │                     │               │                │                │                  │  ack response │
   │                        │                     │               │                │                │                  │ ◄──────────── │
   │                        │                     │               │                │                │                  │              │
   │                        │  onAcknowledgement(record, exception)│               │                │                │                  │              │
   │                        │ ◄────────────────── │               │                │                │                  │              │
   │                        │                     │               │                │                │                  │              │
   │                        │  complete Future    │               │                │                │                  │              │
   │                        │ ──► 业务侧 get()/callback()         │               │                │                  │              │
```

### 2.3 各阶段职责说明

**一、拦截器 (Interceptor)**

- 客户端配置的 `interceptor.classes` 指定实现 `ProducerInterceptor` 接口的类。
- `onSend()` 在序列化前调用,可修改 Record 的 Topic、Header 等。
- `onAcknowledgement()` 在服务端确认后调用,可用于埋点、统计、链路追踪。
- 多个拦截器按配置顺序串行执行,异常不会中断后续拦截器(异常会被记录)。

**二、序列化器 (Serializer)**

- Kafka 不会序列化业务对象,必须由客户端提供 `Serializer<Key>` 与 `Serializer<Value>`。
- 默认提供 `StringSerializer`、`ByteArraySerializer`、`IntegerSerializer`、`LongSerializer` 等。
- 生产环境推荐 Avro / Protobuf + Schema Registry,保证前后兼容。

**三、分区器 (Partitioner)**

- 决定消息写入 `Topic-Partition` 中的哪一个 Partition。
- Kafka 内置 `DefaultPartitioner` 与 `UniformStickyPartitioner`(Kafka 2.5+)。
- 业务可通过实现 `Partitioner` 接口自定义分区逻辑(如按业务字段路由)。

**四、累加器 (Accumulator)**

- 本质是一个 `ConcurrentMap<TopicPartition, Deque<ProducerBatch>>`,按 (主题-分区) 分组缓存消息。
- 默认总大小 `buffer.memory=33554432` (32 MB)。
- 每个 `ProducerBatch` 默认大小 `batch.size=16384` (16 KB),超过会尝试压缩或拆批。

**五、发送线程 (Sender)**

- 单线程守护线程,从 Accumulator 中读取已就绪的批次发送到 Broker。
- 使用 `org.apache.kafka.clients.NetworkClient` 与 Java NIO `Selector` 实现非阻塞 I/O。
- 同时支持多个连接(每个 Node 一个),通过 `max.in.flight.requests.per.connection` 控制并发请求数。

---

## 三、Producer 核心配置详解

### 3.1 必填参数

| 参数              | 必填 | 说明                                                                |
|-------------------|------|---------------------------------------------------------------------|
| `bootstrap.servers` | 是   | Kafka Broker 集群地址,格式 `host1:9092,host2:9092,host3:9092`     |
| `key.serializer`    | 是   | Key 序列化器全限定类名,如 `org.apache.kafka.common.serialization.StringSerializer` |
| `value.serializer`  | 是   | Value 序列化器全限定类名                                            |
| `client.id`         | 否   | 客户端标识,便于日志和监控区分                                       |

### 3.2 可靠性参数

#### 3.2.1 `acks` (应答机制)

`acks` 决定 Producer 在认为消息"发送成功"前,需要等待多少副本的确认。这是消息可靠性最关键的参数之一。

| 取值      | 语义                                                                                    | 可靠性   | 延迟 | 吞吐 | 适用场景                  |
|-----------|-----------------------------------------------------------------------------------------|----------|------|------|---------------------------|
| `acks=0`  | Producer 不等任何 Broker 确认,发送即返回                                                | 最低     | 最低 | 最高 | 日志采集、可容忍少量丢失  |
| `acks=1`  | Producer 等 Leader 写入成功即返回(默认)                                                 | 中等     | 低   | 高   | 一般业务                  |
| `acks=all`(或 `-1`) | Producer 等所有 ISR(In-Sync Replicas)副本写入成功才返回                       | 最高     | 高   | 中   | 金融、订单、不能丢数据    |

**对比示意**:

```text
acks=0
Producer ─────► Broker(写内存) ─────► 立即返回
                                  可能丢失:Leader 未持久化即宕机

acks=1
Producer ─────► Broker Leader ──► 写入 ──► ACK ──► 返回
                                  可能丢失:Leader 写入后未同步即宕机,Follower 还没复制

acks=all
Producer ─────► Leader ──► Follower1 ──► Follower2 ──► 全部 ACK ──► 返回
                                  不丢失:只有全部 ISR 写入成功才确认
                                  注:`min.insync.replicas` 决定 ISR 最小数量
```

#### 3.2.2 `retries` (重试次数)

- 默认值:`Integer.MAX_VALUE` (实际配合 `delivery.timeout.ms` 终止)。
- 建议:配合 `acks=all` 设置较大值,例如 `retries=Integer.MAX_VALUE`。
- 配合 `retry.backoff.ms`(默认 100)控制重试间隔。

#### 3.2.3 `delivery.timeout.ms`

- 消息发送总超时(包括所有重试),默认 `120000` (2 分钟)。
- 一旦超过,即使重试也未成功,Callback 收到异常。

### 3.3 性能参数

#### 3.3.1 `batch.size`

- 每个 RecordBatch 的最大字节数,默认 `16384` (16 KB)。
- 调大可提升吞吐,但会增大单条消息延迟。
- 建议生产环境 `32 KB ~ 128 KB`,视单条消息大小调整。

#### 3.3.2 `linger.ms`

- 消息在 Producer 端等待批量打包的最长时间,默认 `0`(立即发送)。
- 调大(如 `5~100 ms`)可显著提升吞吐,但会增加端到端延迟。
- 推荐:`linger.ms=5` 或 `linger.ms=10` 作为起步,高吞吐场景可到 `50~100`。

#### 3.3.3 `compression.type`

- 压缩算法,可选 `none` / `gzip` / `snappy` / `lz4` / `zstd`,默认 `none`。
- 压缩发生在 Client 端,可减少带宽占用,但消耗 CPU。
- 推荐:`lz4`(CPU 与压缩比平衡)或 `zstd`(压缩比最佳,Kafka 2.1+)。

| 算法    | 压缩比 | CPU 占用 | 适用场景                       |
|---------|--------|----------|--------------------------------|
| none    | 1.0    | 无       | 内网、高带宽、低 CPU 机器      |
| gzip    | 高     | 高       | 日志归档、带宽极贵             |
| snappy  | 中     | 低       | Google 内部常用,CPU 敏感       |
| lz4     | 中高   | 低       | **推荐**:通用场景,速度快       |
| zstd    | 极高   | 中       | **推荐**:大消息、归档、Kafka 2.1+ |

#### 3.3.4 `buffer.memory`

- Producer 客户端缓冲区总大小,默认 `33554432` (32 MB)。
- 当缓冲区满,`send()` 会阻塞(`max.block.ms`,默认 60 秒)或抛 `BufferExhaustedException`。

#### 3.3.5 `max.in.flight.requests.per.connection`

- 每个连接最大未确认请求数,默认 `5`。
- **重要**:在非幂等模式下,该值 > 1 可能导致消息乱序(重试时)。
- 幂等模式下(Kafka 2.5+ 之前),官方建议为 `1` 以避免乱序;2.5+ 默认 `5` 也能保证顺序。

### 3.4 幂等与事务参数

| 参数                    | 默认值 | 说明                                                              |
|-------------------------|--------|-------------------------------------------------------------------|
| `enable.idempotence`    | false  | 是否开启幂等,需配合 `acks=all`、`retries>0`、`max.in.flight≤5`    |
| `transactional.id`      | null   | 事务 ID,设置后 Producer 自动开启事务支持,需幂等开启               |
| `transaction.timeout.ms`| 60000  | 事务超时时间,Broker 端超过此时间会主动中断事务                    |

> **推荐组合**:金融级业务 `enable.idempotence=true` + `acks=all` + `retries=Integer.MAX_VALUE`。

---

## 四、发送消息的三种方式

### 4.1 发送并忘记 (Fire-and-Forget)

```java
ProducerRecord<String, String> record = new ProducerRecord<>("order-topic", "order-001", "{\"id\":1}");
producer.send(record);  // 不获取 Future、不注册 Callback
```

**特点**:

- 性能最高,业务线程零等待。
- **消息可能丢失**(网络故障、Broker 宕机时)。
- 适用场景:日志、点击流、可容忍少量丢失的指标。

### 4.2 同步发送 (Get)

```java
ProducerRecord<String, String> record = new ProducerRecord<>("order-topic", "order-001", "{\"id\":1}");
try {
    RecordMetadata metadata = producer.send(record).get(5, TimeUnit.SECONDS);
    System.out.println("发送成功:topic=" + metadata.topic()
        + ", partition=" + metadata.partition()
        + ", offset=" + metadata.offset());
} catch (ExecutionException | TimeoutException | InterruptedException e) {
    System.err.println("发送失败:" + e.getMessage());
}
```

**特点**:

- 可靠性最高,业务侧完全感知结果。
- 同步阻塞,吞吐低(每条消息都要等 Server ACK)。
- 适用场景:订单、支付等关键业务,**强烈建议配合重试**。

### 4.3 异步发送 (Callback)

```java
ProducerRecord<String, String> record = new ProducerRecord<>("order-topic", "order-001", "{\"id\":1}");
producer.send(record, (metadata, exception) -> {
    if (exception == null) {
        System.out.println("异步发送成功:offset=" + metadata.offset());
    } else {
        System.err.println("异步发送失败:" + exception.getMessage());
        // 此处建议将失败消息写入本地重试队列或落库
    }
});
```

**特点**:

- 性能与可靠性兼顾,生产环境首选。
- Callback 在 Sender 线程执行,**不要在 Callback 中执行阻塞操作**。
- 适用场景:**绝大多数生产业务**(日志、订单、事件流)。

### 4.4 三种方式对比

| 维度     | 发送并忘记 | 同步发送 (get) | 异步发送 (Callback) |
|----------|------------|----------------|---------------------|
| 可靠性   | 最低       | 最高           | 高                  |
| 性能     | 最高       | 最低           | 高                  |
| 业务感知 | 无         | 同步阻塞       | 异步回调            |
| 阻塞业务 | 否         | 是             | 否                  |
| 异常处理 | 无法感知   | try/catch      | Callback 中处理    |
| 推荐度   | 一般       | 关键场景       | **生产首选**         |

---

## 五、分区器 Partitioner

### 5.1 分区的作用

Kafka Topic 是由多个 Partition 组成的逻辑结构,每个 Partition 是一个有序、不可变的消息序列。Producer 发送消息时,必须决定该消息写入哪个 Partition。

分区的好处:

- **水平扩展**:一个 Topic 的吞吐可分散到多个 Broker。
- **并行消费**:Consumer Group 内每个分区只被一个 Consumer 处理,可并行消费。
- **有序保证**:**单个 Partition 内有序**,跨分区不保证顺序。

### 5.2 默认分区器

Kafka 内置两种分区器:

| 分区器                    | 引入版本 | 策略                                                                                  |
|---------------------------|----------|---------------------------------------------------------------------------------------|
| `DefaultPartitioner`      | 0.10~2.4 | Key 为 null → 轮询;Key 非 null → `hash(key) % partitions`                            |
| `UniformStickyPartitioner`| 2.5+     | Key 为 null → 粘性分区(同一批用一个分区);Key 非 null → `hash(key) % partitions`(委托) |

> 通过 `partitioner.class` 参数指定,默认值为 `org.apache.kafka.clients.producer.internals.DefaultPartitioner`(Kafka 2.5+ 自动根据配置选择)。

### 5.3 Key 的 Hash 计算

```java
// Kafka 默认使用 murmur2 算法
public int partition(String topic, Object key, byte[] keyBytes,
                     Object value, byte[] valueBytes, Cluster cluster) {
    List<PartitionInfo> partitions = cluster.partitionsForTopic(topic);
    int numPartitions = partitions.size();
    if (keyBytes == null) {
        // 无 Key: 轮询或粘性
        return nextPartition(topic, key, valueBytes, cluster, partitions);
    }
    // 有 Key: 哈希取模
    return Utils.toPositive(Utils.murmur2(keyBytes)) % numPartitions;
}
```

**注意**:

- 相同的 Key 一定进入同一个 Partition(前提:Partition 数量不变)。
- 如果 Topic 扩容,Key 的分布会重新计算,可能造成乱序(在某些场景下需要谨慎扩容)。

### 5.4 自定义分区器

实现 `org.apache.kafka.clients.producer.Partitioner` 接口:

```java
public class OrderPartitioner implements Partitioner {

    @Override
    public int partition(String topic, Object key, byte[] keyBytes,
                         Object value, byte[] valueBytes, Cluster cluster) {
        // 业务示例:VIP 用户走专属分区,普通用户按地域分
        if (key == null) {
            return 0;  // 无 Key 默认分区 0
        }
        String orderId = key.toString();
        if (orderId.startsWith("VIP-")) {
            // VIP 订单固定进入最后一个分区
            return cluster.partitionsForTopic(topic).size() - 1;
        }
        // 普通订单按地域后缀分
        if (orderId.endsWith("-SH")) return 0;
        if (orderId.endsWith("-BJ")) return 1;
        if (orderId.endsWith("-GZ")) return 2;
        return Math.abs(orderId.hashCode() % cluster.partitionsForTopic(topic).size());
    }

    @Override
    public void close() {}

    @Override
    public void configure(Map<String, ?> configs) {}
}
```

配置:

```java
properties.put(ProducerConfig.PARTITIONER_CLASS_CONFIG, OrderPartitioner.class.getName());
```

---

## 六、序列化器 Serializer

### 6.1 内置序列化器

| 类                          | 类型      | 说明                       |
|-----------------------------|-----------|----------------------------|
| `StringSerializer`          | String    | UTF-8 编码                 |
| `ByteArraySerializer`       | byte[]    | 不做处理                   |
| `ByteBufferSerializer`      | ByteBuffer| NIO Buffer                 |
| `IntegerSerializer`         | Integer   | 4 字节大端                 |
| `LongSerializer`            | Long      | 8 字节大端                 |
| `FloatSerializer`           | Float     | 4 字节 IEEE 754            |
| `DoubleSerializer`          | Double    | 8 字节 IEEE 754            |
| `ShortSerializer`           | Short     | 2 字节大端                 |
| `UUIDSerializer`            | UUID      | 高低位 8 字节              |
| `VoidSerializer`            | null      | Tombstone 消息             |

### 6.2 自定义序列化

实现 `org.apache.kafka.common.serialization.Serializer<T>`:

```java
public class OrderSerializer implements PartialSerializer<Order> {

    private final ObjectMapper mapper = new ObjectMapper();

    @Override
    public byte[] serialize(String topic, Order data) {
        if (data == null) return null;
        try {
            return mapper.writeValueAsBytes(data);
        } catch (JsonProcessingException e) {
            throw new SerializationException("序列化失败", e);
        }
    }
}
```

### 6.3 推荐方案:Avro / Protobuf

JSON 序列化虽然简单,但存在三个问题:

- 体积大,浪费带宽。
- 没有强 Schema 约束,字段拼写错误难发现。
- 字段增删兼容性弱,需手工维护。

**推荐使用 Avro 或 Protobuf + Schema Registry**。

| 方案      | 体积 | 性能 | Schema 演化 | 跨语言 | 推荐度       |
|-----------|------|------|-------------|--------|--------------|
| JSON      | 大   | 一般 | 手工维护    | 强     | 调试期       |
| Avro      | 小   | 高   | 强(Schema Registry) | 强 | **首选**     |
| Protobuf  | 小   | 高   | 中          | 强     | 强类型语言   |
| Kryo      | 中   | 高   | 弱          | 弱     | 内部系统     |

---

## 七、拦截器 ProducerInterceptor

### 7.1 接口定义

```java
public interface ProducerInterceptor<K, V> extends Configurable, AutoCloseable {
    ProducerRecord<K, V> onSend(ProducerRecord<K, V> record);
    void onAcknowledgement(RecordMetadata metadata, Exception exception);
    default void close() {}
}
```

### 7.2 实现示例:链路追踪

```java
public class TraceIdInterceptor implements ProducerInterceptor<String, String> {

    @Override
    public ProducerRecord<String, String> onSend(ProducerRecord<String, String> record) {
        String traceId = MDC.get("traceId");
        if (traceId != null) {
            record.headers().add("X-Trace-Id", traceId.getBytes(StandardCharsets.UTF_8));
        }
        // 也可在此处统计发送量
        return record;
    }

    @Override
    public void onAcknowledgement(RecordMetadata metadata, Exception exception) {
        if (exception != null) {
            // 失败埋点:可用于监控告警
            Metrics.counter("kafka.send.failed", "topic", metadata.topic()).increment();
        } else {
            Metrics.counter("kafka.send.success", "topic", metadata.topic()).increment();
        }
    }

    @Override
    public void close() {}

    @Override
    public void configure(Map<String, ?> configs) {}
}
```

配置:

```java
properties.put(ProducerConfig.INTERCEPTOR_CLASSES_CONFIG,
    TraceIdInterceptor.class.getName() + "," + MetricsInterceptor.class.getName());
```

**注意**:

- 多个拦截器按配置顺序执行,异常不会影响后续,但会写入日志。
- `onAcknowledgement` 在 Sender 线程中调用,**不要阻塞**。

---

## 八、幂等性 Producer(Exactly-Once 基础)

### 8.1 为什么需要幂等

默认情况下,Producer 发送消息时可能因为重试导致 **同一条消息被写入多次**(例如 ACK 丢失导致重发)。在某些业务下,重复消息会造成业务错误(如重复扣款)。

幂等性保证:**在单个 Partition 内,消息不会重复**。

### 8.2 开启幂等

```java
properties.put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG, true);
```

Kafka 会自动:

- 启用 `acks=all`
- 启用 `retries=Integer.MAX_VALUE`
- 启用 `max.in.flight.requests.per.connection<=5`(Kafka 2.5+)

### 8.3 幂等原理:PID + Sequence Number

```text
幂等去重原理图

Producer 端                              Broker 端
┌────────────────────┐                  ┌──────────────────────────────┐
│                    │                  │   PID=12345                  │
│  PID=12345 首次启动│                  │   ┌───────┬───────┐          │
│  Sequence=0,1,2,3  │                  │   │ Seq=0 │ 写入 ✓│          │
│                    │                  │   │ Seq=1 │ 写入 ✓│          │
│  send(msg-1, seq=0)│ ──────────────► │   │ Seq=2 │ 写入 ✓│          │
│  send(msg-2, seq=1)│ ──────────────► │   │ Seq=3 │ 写入 ✓│          │
│  send(msg-3, seq=2)│ ──────────────► │   └───────┴───────┘          │
│                    │                  │                              │
│  ACK 丢失,重试     │                  │  去重逻辑:                    │
│  send(msg-2, seq=1)│ ──────────────► │  if Seq <= 已记录最大 Seq:    │
│                    │                  │     丢弃(视为重复)            │
│                    │ ◄────────────── │  else: 写入                   │
│                    │                  │                              │
│  客户端继续        │                  │   PID=12345                  │
│  send(msg-4, seq=3)│ ──────────────► │   ┌───────┬───────┐          │
│                    │                  │   │ Seq=3 │ 已存在│ ← 丢弃!  │
│                    │                  │   │ Seq=4 │ 写入 ✓│          │
│                    │                  │   └───────┴───────┘          │
└────────────────────┘                  └──────────────────────────────┘
```

**关键概念**:

| 概念               | 说明                                                                  |
|--------------------|-----------------------------------------------------------------------|
| **PID (Producer ID)** | Producer 启动时由 Broker 分配,全局唯一,标识一个 Producer 会话       |
| **Sequence Number**   | 每个 PID 内部、从 0 递增的序列号,与 (Topic-Partition) 绑定        |
| **Epoch**             | PID 的版本号,Producer 重启或切换时单调递增,防止旧 PID 的脏数据     |

### 8.4 去重原理详解

1. Producer 启动,向任意 Broker 请求分配一个唯一 **PID** 和当前 **Epoch**。
2. 每条消息携带 `(PID, Partition, Seq)` 三元组,Seq 在同一 (PID, Partition) 内单调递增。
3. Broker 在内存中维护 `(PID, Partition) → lastSeq` 映射。
4. 收到新消息时:
   - 如果 `Seq == lastSeq + 1`:写入,更新 `lastSeq`。
   - 如果 `Seq <= lastSeq`:视为重复,直接 ACK 丢弃。
   - 如果 `Seq > lastSeq + 1`:乱序/丢失,抛出 `OutOfOrderSequenceException`。
5. Producer 收到 `OutOfOrderSequenceException` 会终止会话并重新初始化。

**幂等的边界**:

- 仅保证 **单 Producer 会话 + 单分区** 不重复。
- 跨分区、跨 Topic 不保证(需事务)。
- Producer 重启后会重新分配 PID,旧的重复消息无法识别(需事务)。

---

## 九、事务型 Producer

### 9.1 为什么需要事务

幂等只能解决单分区的重复问题,但无法满足:

- **多分区原子写**:同时写 5 个分区,要么全部成功,要么全部失败。
- **读已提交(Read Committed)**:Consumer 只读到已提交的事务消息。
- **跨 Topic 原子写**:写 TopicA 同时写 TopicB,要求原子性。

### 9.2 事务 API

```java
properties.put(ProducerConfig.TRANSACTIONAL_ID_CONFIG, "order-tx-producer-001");
properties.put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG, true);

KafkaProducer<String, String> producer = new KafkaProducer<>(properties);

producer.initTransactions();          // 初始化事务
try {
    producer.beginTransaction();       // 开启事务
    producer.send(new ProducerRecord<>("order", "1", "create"));
    producer.send(new ProducerRecord<>("audit", "1", "log-create"));
    producer.send(new ProducerRecord<>("stock", "1", "dec-stock"));
    producer.commitTransaction();      // 提交
} catch (Exception e) {
    producer.abortTransaction();       // 中止
}
```

### 9.3 事务与幂等的区别

| 维度       | 幂等 Producer             | 事务 Producer                            |
|------------|----------------------------|------------------------------------------|
| 作用域     | 单分区                     | 跨分区、跨 Topic                         |
| 原子性     | 单条消息不重复             | 多条消息原子提交或回滚                   |
| 配置       | `enable.idempotence=true`  | `transactional.id` + `enable.idempotence` |
| Consumer   | 无特殊配置                 | `isolation.level=read_committed`         |
| 性能开销   | 极低                       | 中(需协调 Broker `__transaction_state`) |
| 典型场景   | 单条消息防重               | 订单 + 库存 + 审计 原子写入              |

### 9.4 Consumer 配合

```java
properties.put(ConsumerConfig.ISOLATION_LEVEL_CONFIG, "read_committed");
```

- `read_uncommitted`(默认):Consumer 可读到所有消息,包括未提交事务。
- `read_committed`:只读到已提交的事务消息,未提交消息对 Consumer 不可见。

### 9.5 事务的状态机

```text
┌─────────────────┐
│  UNINITIALIZED  │ ← Producer 刚创建
└────────┬────────┘
         │ initTransactions()
         ▼
┌─────────────────┐
│     READY       │ ← 空闲,可发送可开启事务
└────────┬────────┘
         │ beginTransaction()
         ▼
┌─────────────────┐
│ IN_TRANSACTION  │ ← 事务进行中,可 send() / sendOffsetsToTransaction()
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌────────┐ ┌────────┐
│COMMIT  │ │ ABORT  │
└────────┘ └────────┘
    │         │
    └────┬────┘
         ▼
┌─────────────────┐
│  READY (再次)   │ ← 可继续开启新事务
└─────────────────┘

任意阶段调用 close() 进入 CLOSED 状态,不可再使用
```

---

## 十、消息可靠性保证

### 10.1 可靠性等级划分

```text
可靠性金字塔(从低到高)

              ▲
             ╱ ╲
            ╱   ╲          Exactly-Once(幂等 + 事务)
           ╱  T  ╲
          ╱       ╲
         ╱─────────╲       At-Least-Once(acks=all + 重试)
        ╱           ╲
       ╱    A1+A     ╲
      ╱               ╲
     ╱─────────────────╲   At-Most-Once(无重试)
    ╱        A0         ╲
   ╱_____________________╲
```

| 等级            | 含义                         | 配置                                                  |
|-----------------|------------------------------|-------------------------------------------------------|
| At-Most-Once    | 至多一次,可能丢失            | `acks=0` / 不重试                                      |
| At-Least-Once   | 至少一次,可能重复            | `acks=all` + `retries>0`                              |
| Exactly-Once    | 恰好一次,不丢不重            | 幂等 + 事务 + Consumer `read_committed`              |

### 10.2 生产级可靠性配置模板

```java
Properties properties = new Properties();
properties.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, "broker1:9092,broker2:9092,broker3:9092");
properties.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
properties.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());

// === 可靠性 ===
properties.put(ProducerConfig.ACKS_CONFIG, "all");                       // 所有 ISR 确认
properties.put(ProducerConfig.RETRIES_CONFIG, Integer.MAX_VALUE);         // 无限重试
properties.put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG, true);          // 开启幂等
properties.put(ProducerConfig.MAX_IN_FLIGHT_REQUESTS_PER_CONNECTION, 5); // Kafka 2.5+ 安全

// === 超时 ===
properties.put(ProducerConfig.DELIVERY_TIMEOUT_MS_CONFIG, 120000);       // 2 分钟总超时
properties.put(ProducerConfig.REQUEST_TIMEOUT_MS_CONFIG, 30000);         // 单次请求超时
properties.put(ProducerConfig.RETRY_BACKOFF_MS_CONFIG, 100);             // 重试退避

// === 性能平衡 ===
properties.put(ProducerConfig.BATCH_SIZE_CONFIG, 32 * 1024);             // 32 KB
properties.put(ProducerConfig.LINGER_MS_CONFIG, 10);                     // 10ms 批量等待
properties.put(ProducerConfig.COMPRESSION_TYPE_CONFIG, "lz4");           // lz4 压缩
properties.put(ProducerConfig.BUFFER_MEMORY_CONFIG, 64 * 1024 * 1024);   // 64 MB 缓冲
```

### 10.3 Broker 端配合

```properties
# server.properties
default.replication.factor=3          # 默认副本数 3
min.insync.replicas=2                  # 最小 ISR 数 2,小于此值拒绝写入
unclean.leader.election.enable=false   # 禁止非 ISR 副本当选 Leader
```

### 10.4 可靠性检查清单

- [ ] `acks=all` 已设置
- [ ] `retries=Integer.MAX_VALUE`(配合 `delivery.timeout.ms` 终止)
- [ ] `enable.idempotence=true` 已开启
- [ ] Broker 端 `min.insync.replicas >= 2`
- [ ] `unclean.leader.election.enable=false`
- [ ] Topic 副本数 ≥ 3
- [ ] Callback 中处理失败并落库重试队列
- [ ] 监控发送失败率、有积压报警

---

## 十一、性能优化配置

### 11.1 吞吐优化

| 参数                                | 默认值              | 优化建议            | 影响                       |
|-------------------------------------|---------------------|---------------------|----------------------------|
| `batch.size`                        | 16384 (16 KB)       | 32768~131072        | 大 → 高吞吐、高延迟         |
| `linger.ms`                         | 0                   | 5~100               | 大 → 高吞吐、高延迟         |
| `compression.type`                  | none                | lz4 / zstd          | 节省带宽、增加 CPU          |
| `buffer.memory`                     | 33554432 (32 MB)    | 64~256 MB           | 大 → 抗突发                |
| `max.in.flight.requests.per.connection` | 5               | 5                   | 高 → 提升吞吐              |

### 11.2 延迟优化

- `linger.ms=0`(立即发送,不等批量)。
- `batch.size=16384`(小批次)。
- `acks=1`(不等全部 ISR,只等 Leader)。
- `compression.type=none`(压缩会消耗 CPU)。

### 11.3 关键参数推荐值速查

| 场景           | acks | retries  | linger.ms | batch.size | compression | 幂等 |
|----------------|------|----------|-----------|------------|-------------|------|
| 日志采集       | 0/1  | 3        | 20        | 64 KB      | lz4         | 否   |
| 通用业务       | all  | MAX      | 10        | 32 KB      | lz4         | 是   |
| 金融/订单     | all  | MAX      | 5         | 16 KB      | none/zstd   | 是(必开) |
| 高吞吐聚合     | 1    | 10       | 100       | 128 KB     | zstd        | 否   |
| 实时流(低延迟)| 1    | 3        | 0         | 16 KB      | none        | 否   |

### 11.4 监控指标

| 指标                         | 含义                          | 告警阈值                 |
|------------------------------|-------------------------------|--------------------------|
| `record-send-rate`           | 每秒发送消息数                | 异常下降                  |
| `record-queue-time-avg`      | 消息在累加器平均等待时间(ms) | > 100                    |
| `batch-size-avg`             | 平均批次大小(字节)            | 监控利用率                |
| `request-latency-avg`        | 请求平均延迟                  | > 业务容忍阈值            |
| `buffer-available-bytes`    | 累加器剩余可用字节            | < 10% 触发告警            |
| `record-error-rate`          | 发送失败速率                  | > 0 触发告警              |
| `record-retry-rate`          | 重试速率                      | 突增需关注                |

---

## 十二、实战代码示例

### 12.1 完整 Java 异步发送示例

```java
import org.apache.kafka.clients.producer.*;
import org.apache.kafka.common.serialization.StringSerializer;

import java.util.Properties;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;

public class KafkaProducerExample {

    public static void main(String[] args) {
        Properties properties = new Properties();
        properties.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, "broker1:9092,broker2:9092");
        properties.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class);
        properties.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, StringSerializer.class);
        properties.put(ProducerConfig.ACKS_CONFIG, "all");
        properties.put(ProducerConfig.RETRIES_CONFIG, Integer.MAX_VALUE);
        properties.put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG, true);
        properties.put(ProducerConfig.BATCH_SIZE_CONFIG, 32 * 1024);
        properties.put(ProducerConfig.LINGER_MS_CONFIG, 10);
        properties.put(ProducerConfig.COMPRESSION_TYPE_CONFIG, "lz4");
        properties.put(ProducerConfig.CLIENT_ID_CONFIG, "order-producer-001");

        try (KafkaProducer<String, String> producer = new KafkaProducer<>(properties)) {

            for (int i = 0; i < 1000; i++) {
                ProducerRecord<String, String> record = new ProducerRecord<>(
                        "order-topic",
                        "order-" + i,                              // Key: 同 Key 进同一分区
                        "{\"id\":" + i + ",\"amount\":99.99}");     // Value

                // 异步发送 + Callback
                Future<RecordMetadata> future = producer.send(record, (metadata, exception) -> {
                    if (exception != null) {
                        System.err.printf("发送失败: key=%s, error=%s%n",
                                record.key(), exception.getMessage());
                    } else {
                        System.out.printf("发送成功: topic=%s, partition=%d, offset=%d%n",
                                metadata.topic(), metadata.partition(), metadata.offset());
                    }
                });
            }
        }
    }
}
```

### 12.2 事务型发送示例

```java
public class TransactionalProducerExample {

    public static void main(String[] args) throws Exception {
        Properties properties = new Properties();
        properties.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, "broker1:9092");
        properties.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class);
        properties.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, StringSerializer.class);
        properties.put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG, true);
        properties.put(ProducerConfig.TRANSACTIONAL_ID_CONFIG, "order-tx-producer");
        properties.put(ProducerConfig.ACKS_CONFIG, "all");

        try (KafkaProducer<String, String> producer = new KafkaProducer<>(properties)) {
            producer.initTransactions();
            try {
                producer.beginTransaction();
                producer.send(new ProducerRecord<>("order", "order-001", "create"));
                producer.send(new ProducerRecord<>("audit", "order-001", "log-create"));
                producer.send(new ProducerRecord<>("stock", "stock-001", "dec-stock"));
                producer.commitTransaction();
                System.out.println("事务提交成功");
            } catch (Exception e) {
                producer.abortTransaction();
                System.err.println("事务中止:" + e.getMessage());
            }
        }
    }
}
```

### 12.3 Spring Boot 集成

#### 12.3.1 Maven 依赖

```xml
<dependency>
    <groupId>org.springframework.kafka</groupId>
    <artifactId>spring-kafka</artifactId>
    <version>3.1.0</version>
</dependency>
```

#### 12.3.2 application.yml

```yaml
spring:
  kafka:
    bootstrap-servers: broker1:9092,broker2:9092,broker3:9092
    producer:
      acks: all
      retries: 2147483647
      enable-idempotence: true
      batch-size: 32768
      linger-ms: 10
      compression-type: lz4
      buffer-memory: 67108864
      max-in-flight-requests-per-connection: 5
      key-serializer: org.apache.kafka.common.serialization.StringSerializer
      value-serializer: org.apache.kafka.common.serialization.StringSerializer
      transaction-id-prefix: "order-tx-"     # 自动开启事务支持
```

#### 12.3.3 发送代码

```java
@Service
public class OrderService {

    @Autowired
    private KafkaTemplate<String, String> kafkaTemplate;

    /**
     * 异步发送
     */
    public void sendOrderAsync(Order order) {
        String value = JSON.toJsonString(order);
        CompletableFuture<SendResult<String, String>> future =
                kafkaTemplate.send("order-topic", order.getId(), value);
        future.whenComplete((result, ex) -> {
            if (ex == null) {
                log.info("发送成功: offset={}",
                        result.getRecordMetadata().offset());
            } else {
                log.error("发送失败", ex);
            }
        });
    }

    /**
     * 事务发送
     */
    @Transactional
    public void sendOrderWithTx(Order order) {
        // Kafka 事务需配合 Spring 的 @Transactional 注解或 KafkaTemplate.executeInTransaction
        kafkaTemplate.executeInTransaction(template -> {
            template.send("order-topic", order.getId(), JSON.toJsonString(order));
            template.send("audit-topic", order.getId(), "create-order");
            return true;
        });
    }
}
```

#### 12.3.4 幂等 + 批量发送优化

```java
@Service
public class BatchOrderProducer {

    @Autowired
    private KafkaTemplate<String, String> kafkaTemplate;

    /**
     * 批量发送订单
     */
    public void sendBatch(List<Order> orders) {
        List<CompletableFuture<SendResult<String, String>>> futures = new ArrayList<>();
        for (Order order : orders) {
            CompletableFuture<SendResult<String, String>> future =
                    kafkaTemplate.send("order-topic", order.getId(), JSON.toJsonString(order));
            futures.add(future);
        }
        // 等待所有发送完成
        CompletableFuture.allOf(futures.toArray(new CompletableFuture[0]))
                .orTimeout(30, TimeUnit.SECONDS)
                .exceptionally(ex -> {
                    log.error("批量发送失败", ex);
                    return null;
                })
                .join();
    }
}
```

---

## 核心要点速记

| 要点       | 关键内容                                                                                                                              |
|-----------|---------------------------------------------------------------------------------------------------------------------------------------|
| **发送流程** | Interceptor → Serializer → Partitioner → Accumulator → Sender Thread → Broker,五阶段协作                                    |
| **核心参数** | `acks`(可靠性) + `batch.size`/`linger.ms`(吞吐) + `compression.type`(带宽) + `enable.idempotence`(去重)                        |
| **acks 选择** | 0=不保证,1=Leader 写入,all=全部 ISR,金融级必选 `all`                                                                              |
| **发送方式** | 生产首选 **异步 Callback**,失败必须在回调中处理                                                                                     |
| **分区策略** | 有 Key → 哈希取模;无 Key → 轮询或粘性;特殊业务可自定义                                                                              |
| **序列化**   | 生产推荐 **Avro / Protobuf + Schema Registry**,避免 JSON                                                                              |
| **幂等**     | 开启 `enable.idempotence=true`,通过 `(PID, Epoch, Seq)` 在 Broker 端去重,仅防单分区重复                                            |
| **事务**     | 设置 `transactional.id`,调用 `init/begin/commit/abortTransactions`,Consumer 配 `read_committed`                                  |
| **可靠性模板** | `acks=all` + `retries=MAX` + `enable.idempotence=true` + Broker 端 `min.insync.replicas≥2` + 副本数 ≥ 3                         |
| **性能调优** | 高吞吐:`linger.ms=10~100`、`batch.size=32~128KB`、`compression.type=lz4/zstd`;低延迟:`linger.ms=0`、`acks=1`、无压缩       |
| **监控**     | 必看 `record-error-rate`、`buffer-available-bytes`、`request-latency-avg`、`record-retry-rate`                                   |
| **Spring Boot** | 用 `KafkaTemplate`,配置 `transaction-id-prefix` 自动开启事务;`executeInTransaction` 实现原子发送                                    |

> **一句话总结**:Kafka Producer 是"异步 + 批量 + 可配置"的客户端引擎;可靠性 = `acks=all` + 幂等 + 事务;性能 = 批量 + 压缩 + 合理 linger;两者通过参数组合按需平衡。