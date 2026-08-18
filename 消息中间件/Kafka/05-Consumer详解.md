# Kafka Consumer 详解

## 一、Consumer 概述

### 1.1 什么是 Kafka Consumer

**Kafka Consumer(消费者)** 是 Kafka 体系中负责**从 Topic 拉取(Pull)消息**并进行业务处理的客户端应用。与 Producer 的"生产"对应,Consumer 完成"消费"环节,二者共同构成 Kafka 消息流转的闭环。

Consumer 在 Kafka 中的核心定位:

- **消息使用方**:从 Topic 读取由 Producer 写入的消息记录(Record)
- **横向可扩展**:通过**增加 Consumer 实例**来提升消费吞吐能力(同组内分区互斥)
- **故障可恢复**:依赖 **Offset(位移)** 机制保证宕机后能从断点继续消费
- **多订阅模式**:支持订阅(subscribe)或手动分配(assign)两种模式

### 1.2 Consumer 在 Kafka 体系中的位置

```text
┌────────────────────────────────────────────────────────────────┐
│                       Kafka Cluster                            │
│                                                                │
│   Producer ──▶  Topic (由 Partition 组成)  ──▶  Consumer      │
│                       │                                        │
│                       │  /  |  \                                │
│                       P0  P1  P2   (Partition 内部有序)        │
│                       │   │   │                                │
│                       ▼   ▼   ▼                                │
│              __consumer_offsets (位移提交)                      │
└────────────────────────────────────────────────────────────────┘
```

### 1.3 Consumer 与其他组件的关系

| 组件            | 与 Consumer 的关系                                               |
|-----------------|------------------------------------------------------------------|
| Producer        | 上游,消息来源                                                    |
| Topic/Partition | Consumer 拉取数据的物理单元,**每个 Partition 只能被同组一个 Consumer 消费** |
| Broker          | Consumer 通过 `bootstrap.servers` 连接到任意 Broker,**再发现集群其余节点** |
| ConsumerGroup   | 多个 Consumer 组成一个组,**协同消费 Topic**;不同组**互不影响** |
| __consumer_offsets | Kafka 内部 Topic,**持久化 Consumer 提交的位移**                |
| Coordinator     | 每个 ConsumerGroup 选举一个 Broker 作为协调者,**管理组员与位移**  |

### 1.4 Consumer 的关键特征

- **拉模式(Pull)**:Consumer 主动从 Broker 拉取消息,**而非 Broker 主动推送**(与 RabbitMQ 的 Push 模型形成对照)
- **消费位点可控**:通过 Offset 控制从哪里开始读,**可回放、可重读**
- **水平扩展性**:同一 Group 内 Consumer **数量 ≤ Partition 数**;多余 Consumer 闲置
- **负载均衡自动**:Group 内 Partition 分配由 **PartitionAssignor** 自动完成
- **失败容忍**:Consumer 崩溃后,Coordinator 在 `session.timeout.ms` 后**自动再平衡(Rebalance)**

---

## 二、Consumer 核心配置详解

Kafka Consumer 客户端的配置位于 `org.apache.kafka.clients.consumer.ConsumerConfig` 中,所有配置项均有合理的默认值,但生产环境几乎都需要根据业务调优。

### 2.1 bootstrap.servers

```properties
# 指定 Consumer 连接 Kafka 集群的初始地址
# 只需要列出集群中部分 Broker(通常 ≥2),客户端启动后会**自动发现**其余 Broker
bootstrap.servers=hadoop102:9092,hadoop103:9092,hadoop104:9092
```

**关键说明**:
- 不必列出全部 Broker,**只要这些 Broker 至少有一个存活**就能启动
- 形式为 `host:port`,多个用逗号分隔
- 必须配置,无默认值
- 推荐值:`3 ~ 5` 个 Broker 地址,覆盖一个机架或可用区

### 2.2 group.id

```properties
# Consumer Group 标识,**字符串类型**
# 同 group.id 的 Consumer 视为**同一消费组**,协同消费
group.id=order-consumer-group
```

**关键说明**:
- 同一 Group 内:Partition **互斥分配**(一个 Partition 只能被一个 Consumer 消费)
- 不同 Group 间:**互相独立消费**(同一条消息可以被多个 Group 各自消费一次)
- 若**不设置 group.id**(`assign` 模式),则该 Consumer **不属于任何 Group**,无法使用自动位移管理

### 2.3 key.deserializer / value.deserializer

```properties
# 消息 key 和 value 的反序列化器,**必须实现 org.apache.kafka.common.serialization.Deserializer 接口**
key.deserializer=org.apache.kafka.common.serialization.StringDeserializer
value.deserializer=org.apache.kafka.common.serialization.StringDeserializer
```

**关键说明**:
- 必须配置,无默认值
- 与 Producer 端的 Serializer **必须成对**(Producer 用 StringSerializer,Consumer 就用 StringDeserializer)
- 常用反序列化器:
  - `StringDeserializer`
  - `IntegerDeserializer` / `LongDeserializer` / `DoubleDeserializer` / ...
  - `ByteArrayDeserializer`
  - `ByteBufferDeserializer`
  - 自定义实现 `Deserializer<T>` 接口

### 2.4 auto.offset.reset

```properties
# 当 Kafka 中没有初始 Offset 或当前 Offset 已失效时,该参数决定 Consumer 从何处开始读
# 可选值: earliest | latest | none
auto.offset.reset=earliest
```

| 取值       | 行为                                                                  | 适用场景                       |
|------------|----------------------------------------------------------------------|--------------------------------|
| **earliest**| 当无 Offset 时,从**最早**的位移开始消费                                  | **新 Group 上线第一次消费**   |
| **latest** | 当无 Offset 时,从**最新**(最新消息之后)的位移开始消费                  | **新 Group 上线丢弃历史数据** |
| **none**   | 当无初始 Offset 时,**抛出异常**;若 Topic 已有 Offset 则从提交点继续       | 对数据完整性要求极高           |

> **生产推荐**:大多数场景使用 `earliest`,确保不会因 Group 第一次启动而漏数据;严格"只处理新增"场景用 `latest` 配合人工观察。

### 2.5 enable.auto.commit

```properties
# 是否启用**自动提交 Offset**
enable.auto.commit=true
```

| 取值  | 行为                                                                                 |
|-------|--------------------------------------------------------------------------------------|
| true  | Consumer **后台线程**定时把已 poll 到的最大位移提交到 __consumer_offsets            |
| false | **关闭自动提交**,必须由业务代码显式调用 `commitSync()` 或 `commitAsync()`             |

> **生产推荐**:对**数据准确性要求高**的业务(订单、支付)关闭自动提交,改用手动提交;非关键场景保留自动提交以减少代码复杂度。

### 2.6 auto.commit.interval.ms

```properties
# 自动提交的时间间隔(单位 ms)
# 仅当 enable.auto.commit=true 时生效
auto.commit.interval.ms=5000
```

**关键说明**:
- 默认 `5000`(5 秒)
- 实际提交的是**当前 poll() 返回的所有消息中**最大的 offset,而非每条消息的 offset
- 自动提交存在**重复消费**风险:若提交后业务宕机,该批消息**会被重新消费**

### 2.7 max.poll.records / max.poll.interval.ms

```properties
# 单次 poll() 调用最多返回多少条记录
max.poll.records=500

# 两次 poll() 之间的最大时间间隔(单位 ms)
# 超过这个时间 Consumer 会认为自身"处理太慢",**被踢出 Group 触发 Rebalance**
max.poll.interval.ms=300000
```

| 参数                  | 默认值      | 推荐范围          | 说明                                 |
|-----------------------|-------------|-------------------|--------------------------------------|
| max.poll.records      | 500         | 100~1000          | 单批处理量,值大则吞吐高但单条慢影响时间 |
| max.poll.interval.ms  | 300000(5m) | 与业务处理时间匹配  | 处理耗时上限,需 ≫ 单批业务耗时           |

> **关键约束**:`max.poll.interval.ms` 实际是 **Consumer 主动让出 Group 的超时**。若你的业务逻辑很重(写库、调用下游),需要主动调大该值或缩短单批处理时长。

### 2.8 session.timeout.ms / heartbeat.interval.ms

```properties
# Consumer 被认为"死亡"前的最大空闲时间(单位 ms)
session.timeout.ms=45000  # Kafka 2.x+ 默认 45s,早期版本默认 10s

# 心跳线程发送心跳的频率(单位 ms)
heartbeat.interval.ms=3000
```

**关键机制**:

```text
   Consumer A 加入 Group
           │
           ▼
   每 heartbeat.interval.ms 发送一次心跳
           │
           ▼
   若 Coordinator 在 session.timeout.ms 内未收到心跳
           │
           ▼
   触发 Rebalance,A 被踢出 Group
```

**关系规则**:`heartbeat.interval.ms ≤ session.timeout.ms / 3`,推荐 `3000` (默认),最高不超过 `session.timeout.ms / 3`。

### 2.9 fetch.min.bytes / fetch.max.wait.ms

```properties
# Consumer 拉取时,Broker 端最少累积多少字节才返回
fetch.min.bytes=1
# 如果 fetch.min.bytes 未达到,Broker 最多等待 fetch.max.wait.ms 后**强制返回**
fetch.max.wait.ms=500
```

| 参数                | 默认值 | 建议                                |
|---------------------|--------|-------------------------------------|
| fetch.min.bytes     | 1      | 高吞吐调大(1KB~10KB);低延迟保持 1 |
| fetch.max.wait.ms   | 500    | 高吞吐可调大(1000~5000)             |

> **吞吐 vs 延迟权衡**:`fetch.min.bytes` 越大,平均延迟越高,但吞吐更高;反之亦然。

### 2.10 partition.assignment.strategy

```properties
# 分区分配策略
# 可选: org.apache.kafka.clients.consumer.RangeAssignor
#       org.apache.kafka.clients.consumer.RoundRobinAssignor
#       org.apache.kafka.clients.consumer.StickyAssignor
#       org.apache.kafka.clients.consumer.CooperativeStickyAssignor
partition.assignment.strategy=org.apache.kafka.clients.consumer.RangeAssignor
```

| 策略                    | 特点                                                            | 选型建议               |
|-------------------------|-----------------------------------------------------------------|------------------------|
| RangeAssignor(默认)     | 按 Topic 维度 range 分配,**可能不均衡**                          | 老版本默认,可保留     |
| RoundRobinAssignor      | 整个 Group 轮询分配,**更均衡但 Rebalance 时变动较大**            | 多 Topic 均衡场景     |
| StickyAssignor          | **两次分配结果尽可能一致**,减少 Rebalance 影响                    | **推荐生产**          |
| CooperativeStickyAssignor | 协作式增量 Rebalance,**不再需要 stop-the-world**             | **Kafka 2.4+ 推荐**   |

### 2.11 其他常用配置速查

| 配置                          | 默认值            | 说明                                                  |
|-------------------------------|-------------------|-------------------------------------------------------|
| `client.id`                   | ""                | Consumer 客户端标识,监控与日志用到                      |
| `client.dns.lookup`           | use_all_dns_ips   | DNS 解析策略                                            |
| `fetch.max.bytes`             | 52428800 (50MB)   | 单次 fetch 最大字节                                     |
| `isolation.level`             | read_uncommitted  | 消费事务消息时使用 read_committed                       |
| `interceptor.classes`         | ""                | ConsumerInterceptor 全限定类名                         |
| `request.timeout.ms`          | 30000             | 等待 Broker 响应的超时                                  |
| `receive.buffer.bytes`        | 65536             | TCP 接收缓冲区                                          |
| `send.buffer.bytes`           | 131072            | TCP 发送缓冲区                                          |
| `reconnect.backoff.ms`        | 50                | 断线重连的初始间隔                                      |
| `reconnect.backoff.max.ms`    | 1000              | 断线重连的最大间隔                                      |
| `partition.assignment.strategy` | RangeAssignor  | 分区分配策略                                            |

### 2.12 推荐配置模板(生产)

```properties
# ===== 基础配置 =====
bootstrap.servers=hadoop102:9092,hadoop103:9092,hadoop104:9092
group.id=order-consumer-group
client.id=order-consumer-1

# ===== 反序列化 =====
key.deserializer=org.apache.kafka.common.serialization.StringDeserializer
value.deserializer=org.apache.kafka.common.serialization.StringDeserializer

# ===== 消费位点 =====
auto.offset.reset=earliest
enable.auto.commit=false              # 推荐:关闭自动提交

# ===== 性能调优 =====
fetch.min.bytes=1024                  # 1KB
fetch.max.wait.ms=1000
max.poll.records=500
max.poll.interval.ms=600000           # 10 分钟,给慢消费留余量

# ===== 心跳与会话 =====
session.timeout.ms=30000              # 30s
heartbeat.interval.ms=10000           # 10s (≤ session / 3)

# ===== 分区分配 =====
partition.assignment.strategy=org.apache.kafka.clients.consumer.CooperativeStickyAssignor
```

---

## 三、Consumer 完整消费流程

### 3.1 完整消费时序图

```text
┌──────────┐           ┌────────────┐           ┌───────────┐           ┌──────────────────────┐
│ Consumer │           │ Coordinator│           │  Broker   │           │ __consumer_offsets   │
│  客户端  │           │  (Broker)  │           │  (Topic)  │           │       (位移)         │
└────┬─────┘           └─────┬──────┘           └─────┬─────┘           └──────────┬───────────┘
     │                       │                        │                            │
     │ 1. 创建 KafkaConsumer  │                        │                            │
     │───────────────────────▶                        │                            │
     │                       │                        │                            │
     │ 2. subscribe(topic)   │                        │                            │
     │───────────────────────▶                        │                            │
     │                       │                        │                            │
     │ 3. poll() 第一次      │                        │                            │
     │───────────────────────▶                        │                            │
     │                       │                        │                            │
     │ 4. 协调请求 → 加入 Group│                       │                            │
     │◀──────────────────────│                        │                            │
     │                       │                        │                            │
     │ 5. JoinGroup + SyncGroup(选 leader,分配分区)   │                            │
     │◀═════════════════════▶│                        │                            │
     │                       │                        │                            │
     │ 6. fetch(分区 offset) │                        │                            │
     │                       │───────────────────────▶│                            │
     │                       │                        │ 读 last_committed_offset   │
     │                       │                        │───────────────────────────▶│
     │                       │                        │◀───────────────────────────│
     │ 7. 返回 FetchResponse │                        │                            │
     │◀══════════════════════│◀═══════════════════════│                            │
     │                       │                        │                            │
     │ 8. poll() 返回消息    │                        │                            │
     │←←←←←←←←←←←←←←←←←←←←←←│                        │                            │
     │                       │                        │                            │
     │ 9. 业务处理            │                       │                            │
     │ (OrderService.handle) │                        │                            │
     │                       │                        │                            │
     │ 10. commitSync()      │                        │                            │
     │───────────────────────▶                        │                            │
     │                       │ OffsetCommit 写入    │                            │
     │                       │────────────────────────────────────────────────────▶│
     │                       │◀────────────────────────────────────────────────────│
     │                       │                        │                            │
     │ 11. poll() 下一次     │                        │                            │
     │◀══════════════════════│════════════════════════│═══════════════════════════│
     │                       │                        │                            │
```

### 3.2 消费流程详细文字描述

一次完整消费大致包含以下步骤:

1. **创建 KafkaConsumer**:配置基础参数后实例化 Consumer 对象(`new KafkaConsumer<>(props)`)
2. **订阅 Topic(s)**:`subscribe(Collection<String>)` 或 `assign(Collection<TopicPartition>)` 两种方式
3. **第一次 poll()**:此调用会**触发 Group 协调流程**,耗时较长(几百 ms~秒级)
4. **JoinGroup/SyncGroup**:Consumer 向 Group Coordinator 发送加入请求,Coordinator 选举一个 Consumer 作为 leader,**由 leader 决定分区分配方案**
5. **拉取消息**:Consumer 向对应分区的 Leader Broker 发起 **Fetch 请求**,Broker 返回消息批次
6. **业务处理**:遍历 `ConsumerRecord`,执行业务逻辑
7. **提交 Offset**:手动调用 `commitSync()` 或 `commitAsync()`,或后台自动提交线程触发
8. **循环 poll()**:回到第 5 步,持续消费

### 3.3 完整的 Java 代码骨架

```java
public class OrderConsumer {
    public static void main(String[] args) {
        // 1. 配置
        Properties props = new Properties();
        props.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, "hadoop102:9092,hadoop103:9092,hadoop104:9092");
        props.put(ConsumerConfig.GROUP_ID_CONFIG, "order-consumer-group");
        props.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());
        props.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());
        props.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "earliest");
        props.put(ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG, false);
        props.put(ConsumerConfig.MAX_POLL_RECORDS_CONFIG, 500);
        props.put(ConsumerConfig.SESSION_TIMEOUT_MS_CONFIG, 30000);

        // 2. 创建 Consumer
        KafkaConsumer<String, String> consumer = new KafkaConsumer<>(props);

        // 3. 订阅 Topic
        consumer.subscribe(Arrays.asList("order-topic"));

        try {
            // 4. 循环消费
            while (true) {
                ConsumerRecords<String, String> records = consumer.poll(Duration.ofMillis(1000));
                if (records.isEmpty()) {
                    continue;
                }
                for (ConsumerRecord<String, String> record : records) {
                    // 5. 业务处理
                    System.out.printf("offset = %d, key = %s, value = %s%n",
                            record.offset(), record.key(), record.value());
                    handleOrder(record.value());
                }

                // 6. 手动提交 Offset
                consumer.commitSync();
            }
        } finally {
            // 7. 关闭
            consumer.close();
        }
    }
}
```

### 3.4 消费过程中的关键状态

| 状态                | 触发条件                                  | 表现                                        |
|---------------------|-------------------------------------------|---------------------------------------------|
| Group 协调中        | 第一次 poll() 或 Rebalance                | poll() 阻塞几百毫秒至几秒                    |
| 正常消费            | 已分配分区,持续 poll                      | poll() 快速返回,通常 ≤10ms                 |
| Group Rebalancing   | 成员上下线、订阅变化                       | poll() 返回空集合,所有 Consumer 暂停消费    |
| 分区再分配完成       | Rebalance 结束                            | 重新开始消费,可能出现重复消息                |
| Heartbeat 超时       | 网络异常或 GC 停顿过长                     | 被踢出 Group,触发 Rebalance                  |

---

## 四、Consumer Group 消费组

### 4.1 消费组概念

**Consumer Group(消费组)** 是 Kafka 实现**单播与多播统一**的核心抽象:
- **组内**:消息只被一个 Consumer 处理(**单播**)
- **组间**:同一条消息可被多个 Group **各自完整消费**(**多播/订阅**)

```text
         Topic A (3 个分区)
      ┌─────────────────────────────┐
      │   P0       P1       P2       │
      └─────┬───────┬───────┬───────┘
            │       │       │
            ▼       ▼       ▼
    ┌───────────────────────────────┐
    │   Group "order-group"        │   ← 组内只消费一次
    │   C1 (P0, P1)  C2 (P2)       │
    └───────────────────────────────┘

    ┌───────────────────────────────┐
    │   Group "stats-group"        │   ← 与 order-group **互不干扰**
    │   C3 (P0)  C4 (P1)  C5 (P2) │
    └───────────────────────────────┘
```

### 4.2 多个消费组独立消费

**核心原则**:不同 `group.id` 的 Consumer 之间**互不影响**,每组都从头(或各自提交的 Offset)开始消费。

| Group               | 消费范围       | 用途                       |
|---------------------|----------------|----------------------------|
| `order-group`       | 完整 Topic     | 订单服务处理订单           |
| `stats-group`       | 完整 Topic     | 数据统计(独立消费)        |
| `audit-group`       | 完整 Topic     | 审计归档(独立消费)        |

**典型场景**:
- **Kafka Streams / Flink**:作为特殊 Group 消费消息,做实时计算
- **数据分发**:同一份数据需要被多个下游消费

### 4.3 同一消费组内分区互斥

**核心原则**:同一 Group 内,**一个 Partition 只能分配给一个 Consumer**,这就是**单播语义**。

```text
  Topic A 有 4 个分区 (P0, P1, P2, P3)
  Group "test" 有 3 个 Consumer

  ┌────────────────────────────────────────┐
  │  C1  →  P0, P1                        │
  │  C2  →  P2                            │
  │  C3  →  P3                            │
  └────────────────────────────────────────┘

  一个 Partition 只能由一个 Consumer 消费;
  一个 Consumer 可消费多个 Partition
```

**关键结论**:
- Group 内 Consumer **数量 ≤ Topic 的 Partition 数**
- 多余的 Consumer **不会被分配任何分区**,处于闲置状态
- 增加 Consumer **不一定提升吞吐**(达到 Partition 数量上限后无效)

### 4.4 Group 内的伸缩与 Rebalance

```text
   初始状态: 2 Consumer,3 Partition
   ┌─────────────────────────┐
   │  C1  →  P0, P1         │
   │  C2  →  P2             │
   └─────────────────────────┘

   增加 C3,触发 Rebalance
   ┌─────────────────────────┐
   │  C1  →  P0             │
   │  C2  →  P1             │
   │  C3  →  P2             │
   └─────────────────────────┘
```

**Rebalance 触发条件**:
- 新 Consumer 加入 Group
- 已有 Consumer 离开(主动 `close()` 或心跳超时)
- Consumer 订阅的 Topic 列表变更
- Partitions 数量变化
- 调用 `unsubscribe()`

### 4.5 Group 协调器 (Coordinator)

```text
   Consumer Group "test"
        │
        ▼
   ┌──────────────────────────────────┐
   │  Coordinator = __consumer_offsets │
   │  分区 hash(group.id) % 50 的     │
   │  leader broker                   │
   └──────────────┬───────────────────┘
                  │
                  │   管理:
                  │   - 成员关系(Member)
                  │   - 位移提交(__consumer_offsets)
                  │   - Rebalance 触发
                  ▼
   ┌──────────────────────────────────┐
   │  Consumer C1   Consumer C2  ...  │
   └──────────────────────────────────┘
```

**Coordinator 职责**:
- 管理 Group 成员(Member)
- 选举 Group leader
- 触发并协调 Rebalance
- 持久化 Offset 提交到 `__consumer_offsets`

---

## 五、Offset 位移

### 5.1 位移的本质

**Offset 是消息在分区中的编号**,每个分区从 0 开始单调递增,**表示分区中"已经消费到哪里"**。

```text
   Partition P0:
   ┌────┬────┬────┬────┬────┬────┐
   │ m0 │ m1 │ m2 │ m3 │ m4 │ m5 │  ...  ← messages
   └──┬─┴────┴────┴────┴────┴────┴────┘
      │   ▲            ▲
      │   │            │
      │   │   next offset = 5
      │   committed offset = 3
      │
   consumer position (not committed yet)
   ↓ next fetch position
```

### 5.2 位移存储位置

Kafka 把 Offset 提交到内部 Topic **`__consumer_offsets`** 中,该 Topic 默认 **50 个分区**,副本数 `offsets.topic.replication.factor` (默认 3)。

```text
   __consumer_offsets
   ┌──────────────────────────────────────────────────────────┐
   │  Key:  group.id + topic + partition                      │
   │  Value: offset + metadata                                │
   │                                                          │
   │  Partition by hash(group.id) % 50                        │
   └──────────────────────────────────────────────────────────┘
```

**查看 Offset(命令行)**:

```bash
# 查看消费进度
kafka-consumer-groups.sh --bootstrap-server hadoop102:9092 \
                         --group order-consumer-group \
                         --describe

# 输出示例
ORDER-TOPIC        0   123456        123456      1230       offset-consumer-1
ORDER-TOPIC        1   234567        234567      1231       offset-consumer-1
ORDER-TOPIC        2   345678        345678      1232       offset-consumer-1
```

字段含义:
- `CURRENT-OFFSET`:当前提交的 Offset
- `LOG-END-OFFSET`:最新消息位置
- `LAG`:`LOG-END-OFFSET - CURRENT-OFFSET`,**消费滞后量**
- `CLIENT-ID`:Consumer 标识

### 5.3 自动提交 vs 手动提交

```text
    ┌──────────────────────────────────────────────────────────┐
    │             自动提交 (enable.auto.commit=true)            │
    │   优点:零代码量,后台线程每 5s 自动提交当前 poll 最大 offset│
    │   缺点:                                                │
    │     1. 提交时机与业务完成时机不一致(提交了但业务失败)      │
    │     2. 提交失败不重试                                      │
    │     3. 提交成功但业务失败 → 重复消费                        │
    │     4. 提交时仍可能丢消息(提交前宕机)                      │
    └──────────────────────────────────────────────────────────┘

    ┌──────────────────────────────────────────────────────────┐
    │             手动提交 (enable.auto.commit=false)           │
    │   优点:业务完成后才提交,语义可控                            │
    │   缺点:需显式编写 commit 逻辑                              │
    │   API:                                                   │
    │     commitSync()   同步阻塞,有重试                         │
    │     commitAsync()  异步非阻塞,可注册回调                    │
    └──────────────────────────────────────────────────────────┘
```

### 5.4 提交 API 详解

#### 5.4.1 commitSync() 同步提交

```java
// 1. 提交当前 poll() 批次返回的最大 offset (最常用)
consumer.commitSync();

// 2. 提交指定 offset
Map<TopicPartition, OffsetAndMetadata> offsets = new HashMap<>();
offsets.put(new TopicPartition("order-topic", 0),
            new OffsetAndMetadata(record.offset() + 1));
consumer.commitSync(offsets);

// 3. 带超时
consumer.commitSync(offsets, Duration.ofSeconds(10));
```

**特性**:
- **同步阻塞**,直到提交成功或超时
- 失败时**会重试**(`retries` 次,可能无限次)
- 影响吞吐(主线在等提交结果)
- 通常配合 try-catch 处理失败逻辑

#### 5.4.2 commitAsync() 异步提交

```java
// 1. 异步提交当前 offset
consumer.commitAsync();

// 2. 带回调的异步提交
consumer.commitAsync((offsets, exception) -> {
    if (exception != null) {
        log.error("commit failed, offsets: {}", offsets, exception);
        // 可在此发送监控告警 / 重试
    } else {
        log.debug("commit success, offsets: {}", offsets);
    }
});
```

**特性**:
- **异步非阻塞**,主线立刻返回
- 失败时**不重试**(只在第一次失败时重试一次)
- 适合**对吞吐量敏感**的场景
- 通常配合回调发送监控/告警

#### 5.4.3 同步 + 异步混合模式(生产推荐)

```java
try {
    while (running) {
        ConsumerRecords<String, String> records = consumer.poll(Duration.ofMillis(1000));
        for (ConsumerRecord<String, String> record : records) {
            handleRecord(record);
        }
        // 异步提交,不让主线阻塞
        consumer.commitAsync();
    }
} catch (Exception e) {
    log.error("consume failed", e);
} finally {
    try {
        // 关闭前同步提交一次,确保最后一批数据落盘
        consumer.commitSync();
    } finally {
        consumer.close();
    }
}
```

### 5.5 指定 Offset 消费(seek)

```java
// 从头消费
consumer.seekToBeginning(consumer.assignment());

// 从当前位置开始消费
consumer.seekToEnd(consumer.assignment());

// 指定某个 TopicPartition 从 offset=100 开始
TopicPartition tp0 = new TopicPartition("order-topic", 0);
consumer.seek(tp0, 100L);
```

**典型场景**:
- 数据回放:重新消费某段时间的数据
- 跳过历史:从某个 Offset 之后开始
- 本地调试:从特定 offset 开始

> **注意**:`seek()` 必须在 `poll()` 内或之前调用,因为 seek 操作**只在分区首次拉取时生效**。

### 5.6 从特定时间消费(offsetsForTimes)

```java
// 查询某个时间戳对应的 offset
Map<TopicPartition, OffsetAndTimestamp> tsMap = consumer.offsetsForTimes(
    Collections.singletonMap(tp0, System.currentTimeMillis() - 3600_000L)  // 1小时前
);

// 然后 seek 到该 offset
tsMap.forEach((tp, ts) -> {
    if (ts != null) {
        consumer.seek(tp, ts.offset());
    }
});
```

**应用**:从昨天 0 点开始消费、近一小时增量同步等。

### 5.7 Offset 提交机制图

```text
  Consumer.poll() → 拿到的 records 内存中处理完
        │
        ▼
  ┌─────────────┐
  │ 业务处理成功? │
  └─────┬───────┘
        │ yes
        ▼
  ┌────────────────────┐
  │ 计算待提交的 Offset │(最后一条记录的 offset + 1)
  └─────┬──────────────┘
        │
        ▼
  ┌─────────────┐
  │ commitSync() │ 或 commitAsync()
  └─────┬───────┘
        │
        ▼
  ┌─────────────────────────────────┐
  │ OffsetCommitRequest              │
  │ key: group.id + topic + part     │
  │ value: offset + metadata         │
  └─────┬───────────────────────────┘
        │
        ▼
  ┌─────────────────────┐
  │ Coordinator 接收    │
  │ → 写入 __consumer_offsets │
  └─────────────────────┘
```

---

## 六、订阅方式

### 6.1 subscribe(订阅)自动分配

**特点**:由 Kafka 客户端**自动**完成 Group 内分区分配,适合常见业务场景。

```java
// 单个 Topic
consumer.subscribe(Collections.singletonList("order-topic"));

// 多个 Topic
consumer.subscribe(Arrays.asList("order-topic", "payment-topic"));

// 正则订阅多个 Topic(需配合 subscribe(Pattern))
Pattern pattern = Pattern.compile("order-.*");
consumer.subscribe(pattern);
```

**优势**:
- 自动 Rebalance,故障自动恢复
- 与 Group 协同,天然支持水平扩展
- 自动从 `__consumer_offsets` 恢复 Offset

**局限**:
- 无法精确控制哪些 Consumer 消费哪些 Partition(由 Assignor 决定)
- 多 Topic + 多 Group 时粒度较粗

### 6.2 assign(手动分配)手动指定

**特点**:由业务代码**显式**指定哪些 Consumer 消费哪些 Partition。

```java
List<TopicPartition> partitions = new ArrayList<>();
partitions.add(new TopicPartition("order-topic", 0));
partitions.add(new TopicPartition("order-topic", 1));
consumer.assign(partitions);
```

**优势**:
- 完全控制分区分配,**避免 Rebalance**
- 适合需要按特定规则定向消费的场景

**劣势**:
- **不会触发 Rebalance**:新增 Consumer 不会自动接管闲置 Partition
- **不属于任何 Group**:若不指定 group.id,**无法自动管理 Offset**,必须手动 seek + commit

**典型场景**:Kafka Connect、MirrorMaker 等需要"固定消费某些分区"的工具

### 6.3 两种订阅方式对比

| 维度           | subscribe                              | assign                              |
|----------------|----------------------------------------|-------------------------------------|
| 分区分配        | Group 内自动分配                        | 手动指定                            |
| Rebalance      | 自动触发                                | 不触发                              |
| Group          | 依赖 group.id 协同消费                  | 可不依赖 group.id                   |
| Offset 管理    | 可自动(或手动)                          | 通常手动                            |
| 适用场景        | 通用业务消费                            | 特定工具、定制分区消费              |
| 动态扩展        | 自动均衡                                | 需人工扩缩                          |
| 推荐程度        | **生产首选**                            | 仅特定场景                          |

---

## 七、分区分配策略(PartitionAssignor)

### 7.1 为什么需要分配策略

当 Group 内有 N 个 Consumer、Topic 有 M 个 Partition 时,**谁消费哪个 Partition** 由 **PartitionAssignor** 决定。

```text
  Group 内:
   Consumer C1, C2, C3 (n=3)

  Topic T1 有 5 个分区: P0~P4

  不同的 Assignor 会给出不同的分配方案
```

### 7.2 RangeAssignor(默认,范围分配)

**算法**:
1. 把所有 Consumer 按字典序排序
2. 把所有 Partition 按字典序排序
3. 平均分配,余数部分按 Consumer 顺序**优先分配**

```text
  Consumer: [C1, C2, C3]
  Topic T1 Partitions: [P0, P1, P2, P3, P4]  (5 个)

  每个 Consumer 平均分到 ⌊5/3⌋ = 1 个
  前 (5 mod 3)=2 个 Consumer 多 1 个

  C1 → P0, P1
  C2 → P2, P3
  C3 → P4

  多 Topic 时,每个 Topic 内独立计算
```

**特点**:
- 默认策略
- **多 Topic 时不均衡**:C1 在每个 Topic 都比其他 Consumer 多 1 个分区
- 算法简单,但 Rebalance 时**改动较大**

### 7.3 RoundRobinAssignor(轮询)

**算法**:
1. 把 Group 内所有 Topic 的所有 Partition **合并成一个列表**
2. 按 Hash 排序后,对 Consumer 列表做轮询(round-robin)分配

```text
  Consumer: [C1, C2, C3]

  Topic T1: P0, P1, P2, P3, P4
  Topic T2: Q0, Q1, Q2           (共 7 个分区)

  排序后整体轮询:
  C1 → T1:P0, T1:P3, T2:Q1
  C2 → T1:P1, T1:P4, T2:Q2
  C3 → T1:P2, T2:Q0
```

**特点**:
- 整体更均衡
- 缺点:Rebalance 时会**打散原有分配**,可能出现大范围数据迁移

### 7.4 StickyAssignor(粘性)

**目标**:两次分配结果**尽可能一致**,减少 Rebalance 时的迁移成本。

**算法**:
1. 首次按 RoundRobin 分配
2. **Rebalance 时优先保留原分配**,仅对新增/移除的 Partition 做微调

```text
  初始分配:
  C1 → T1:P0, T1:P1
  C2 → T1:P2
  C3 → T1:P3, T1:P4

  C2 离开,触发 Rebalance:
   ⇒ C1 仍保留 P0, P1 (粘性)
   ⇒ P2, P3 重新分配给 C1/C3
   ⇒ C3 仍保留 P4 (粘性)
```

**特点**:
- Rebalance 时**最小化分区迁移**,降低对业务的影响
- 适合大部分生产场景

### 7.5 CooperativeStickyAssignor(协作粘性,Kafka 2.4+)

**特点**:Sticky 的"升级版",支持**增量 Rebalance(Incremental Cooperative Rebalance)**。

```text
  传统 Rebalance (eager / stop-the-world):
  ┌────────────┐
  │ 1. 全部 Member revoke 分区 │
  │ 2. 暂停所有 Consumer      │
  │ 3. 重新分配                │
  │ 4. Resume                  │
  └────────────┘

  Cooperative Rebalance:
  ┌────────────┐
  │ 1. 只 revoke 需要移动的分区 │
  │ 2. 不需要移动的分区继续消费  │
  │ 3. 增量分配                │
  └────────────┘
```

**对比**:
- 传统策略:每次 Rebalance 全员暂停数百毫秒~秒级
- Cooperative:**只有受影响的分区暂停**,吞吐影响极小
- **Kafka 3.0+ 推荐的默认策略**

### 7.6 四种策略对比表

| 策略                  | 均衡性 | Rebalance 影响       | 算法复杂度 | 推荐场景                     |
|-----------------------|--------|----------------------|------------|------------------------------|
| RangeAssignor         | 多 Topic 不均 | 大,完全重新分配 | O(n) | 老项目兼容                  |
| RoundRobinAssignor    | 整体均匀      | 大,完全重新分配 | O(n log n) | 多 Topic 均衡分发         |
| StickyAssignor        | 均匀          | 小,粘性保留分配   | O(n²) | **生产推荐**            |
| CooperativeStickyAssignor | 均匀     | **极小,增量调整** | O(n²) | **Kafka 2.4+ 推荐**     |

### 7.7 自定义 Assignor(了解)

```java
// 实现 org.apache.kafka.clients.consumer.ConsumerPartitionAssignor 接口
public class MyAssignor implements ConsumerPartitionAssignor {
    @Override
    public Map<String, Subscription> assign(...) {
        // 自定义分配逻辑
    }
    @Override
    public String name() {
        return "my-custom-assignor";
    }
}
// 通过配置启用:
// partition.assignment.strategy=com.example.MyAssignor
```

### 7.8 分区分配演示代码

```java
// 查看当前 Group 的分区分配情况
Consumer<String, String> consumer = new KafkaConsumer<>(props);
consumer.subscribe(Arrays.asList("order-topic", "payment-topic"));

// poll 一次完成 Rebalance
consumer.poll(Duration.ofMillis(1000));

// 拿到当前 Consumer 被分配的 Partition
Set<TopicPartition> assignment = consumer.assignment();
System.out.println("Current assignment: " + assignment);
// 输出类似:[order-topic-0, order-topic-1, payment-topic-2]

// 查看每个分区的位点
Map<TopicPartition, Long> beginningOffsets = consumer.beginningOffsets(assignment);
Map<TopicPartition, Long> endOffsets = consumer.endOffsets(assignment);
System.out.println("End offsets: " + endOffsets);
```

---

## 八、反序列化器 Deserializer

### 8.1 反序列化的作用

Producer 用 **Serializer** 把 Java 对象转成字节,Consumer 端必须用对应的 **Deserializer** 把字节还原。

```text
Producer:
  Java Object ── Serializer ──▶ byte[] ──▶ Kafka Topic

Consumer:
  Kafka Topic ──▶ byte[] ── Deserializer ──▶ Java Object
```

### 8.2 Kafka 内置 Deserializer

| 反序列化器                       | 类型        | 用途                            |
|----------------------------------|-------------|---------------------------------|
| `StringDeserializer`             | String      | 字符串(最常用)                 |
| `ByteArrayDeserializer`          | byte[]      | 原始字节流                      |
| `ByteBufferDeserializer`         | ByteBuffer  | NIO ByteBuffer                 |
| `IntegerDeserializer`            | Integer     | 整型                            |
| `LongDeserializer`               | Long        | 长整型                          |
| `FloatDeserializer`              | Float       | 单精度浮点                      |
| `DoubleDeserializer`             | Double      | 双精度浮点                      |
| `ShortDeserializer`              | Short       | 短整型                          |
| `UUIDDeserializer`               | UUID        | UUID 类型                       |
| `VoidDeserializer`               | Void        | 仅取 null,丢弃 value            |

### 8.3 使用内置反序列化器

```java
Properties props = new Properties();
props.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, "hadoop102:9092");
props.put(ConsumerConfig.GROUP_ID_CONFIG, "my-group");
props.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class);
props.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, IntegerDeserializer.class);

KafkaConsumer<String, Integer> consumer = new KafkaConsumer<>(props);
```

### 8.4 自定义反序列化器

#### 8.4.1 实现 Deserializer 接口

```java
package com.example.kafka;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.kafka.common.serialization.Deserializer;

public class OrderDeserializer implements Deserializer<Order> {
    private ObjectMapper mapper = new ObjectMapper();

    @Override
    public Order deserialize(String topic, byte[] data) {
        if (data == null) {
            return null;
        }
        try {
            return mapper.readValue(data, Order.class);
        } catch (Exception e) {
            // 反序列化失败:返回 null 或抛异常
            throw new RuntimeException("deserialize failed: " + e.getMessage(), e);
        }
    }
}
```

#### 8.4.2 Kafka 2.7+ 推荐使用 Deserializer<T>

```java
// 推荐使用的泛型接口
public class OrderDeserializer implements Deserializer<Order> {
    // 与上面等价,泛型更明确
}

// 使用
props.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, OrderDeserializer.class);
consumer.subscribe(Collections.singletonList("order-topic"));

ConsumerRecords<String, Order> records = consumer.poll(Duration.ofMillis(1000));
for (ConsumerRecord<String, Order> record : records) {
    Order order = record.value();   // 直接拿到 Order 对象
    handle(order);
}
```

#### 8.4.3 使用 ErrorHandlingDeserializer 容错

Kafka 2.0+ 提供 `ErrorHandlingDeserializer`,可以在反序列化失败时不抛异常,而是**把坏数据转发到 DLT**。

```java
// 配置:先套一层 ErrorHandlingDeserializer
props.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, ErrorHandlingDeserializer.class);
props.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, ErrorHandlingDeserializer.class);
props.put("spring.deserializer.key.delegate.class", StringDeserializer.class);
props.put("spring.deserializer.value.delegate.class", OrderDeserializer.class);
```

### 8.5 反序列化失败的常见处理

```text
   接收 byte[]
        │
        ▼
  deserialize 抛异常?
        │
   ┌────┴────┐
   │ yes     │ no
   ▼         ▼
  抛异常   返回对象
  (整批失败) │
            ▼
       业务处理
```

**处理策略**:
1. **重试**:短暂故障可重试多次
2. **DLQ 转发**:把不能处理的消息转到死信队列
3. **跳过 + 告警**:丢弃 + 发送监控告警,**有丢失风险**
4. **整个 Poll 失败**:配置 `ErrorHandlingDeserializer`,避免单条失败整批阻塞

---

## 九、拦截器 ConsumerInterceptor

### 9.1 拦截器的作用

**ConsumerInterceptor** 在**消息到达业务代码之前/之后**插入自定义逻辑,类似 Web 的 Filter。

```text
  poll() 返回 ConsumerRecords
        │
        ▼
  ┌────────────────────────────┐
  │ onConsume(records)         │  ← 拦截器前置处理
  └──────────┬─────────────────┘
             ▼
  业务处理
             ▼
  ┌────────────────────────────┐
  │ onCommit(offsets)          │  ← 拦截器提交拦截
  └────────────────────────────┘
```

### 9.2 ConsumerInterceptor 接口

```java
package org.apache.kafka.clients.consumer;

public interface ConsumerInterceptor<K, V> extends Configurable, AutoCloseable {
    // 消息消费前
    ConsumerRecords<K, V> onConsume(ConsumerRecords<K, V> records);

    // 位移提交后
    void onCommit(Map<TopicPartition, OffsetAndMetadata> offsets);

    // 关闭资源
    void close();
}
```

### 9.3 自定义拦截器示例

```java
public class LatencyStatsInterceptor implements ConsumerInterceptor<String, String> {

    @Override
    public ConsumerRecords<String, String> onConsume(ConsumerRecords<String, String> records) {
        long now = System.currentTimeMillis();
        for (ConsumerRecord<String, String> record : records) {
            long latency = now - record.timestamp();
            Metrics.timer("kafka.consumer.latency")
                   .record(latency, TimeUnit.MILLISECONDS);
        }
        return records;  // 返回处理后的 records(也可以过滤)
    }

    @Override
    public void onCommit(Map<TopicPartition, OffsetAndMetadata> offsets) {
        // 记录提交行为
        log.info("committed offsets: {}", offsets);
    }

    @Override
    public void close() {
        // 释放资源
    }

    @Override
    public void configure(Map<String, ?> configs) {
        // 读取配置
    }
}
```

### 9.4 配置启用

```properties
interceptor.classes=com.example.kafka.LatencyStatsInterceptor,com.example.kafka.TraceIdInterceptor
```

**多个拦截器链式调用**:按配置顺序依次执行;`onConsume` 返回新的 records,**链上后一个收到前一个的输出**。

### 9.5 典型应用场景

| 场景               | 拦截器职责                                          |
|--------------------|----------------------------------------------------|
| 延迟监控           | 在 onConsume 记录 `now - record.timestamp()`        |
| Trace 链路追踪     | 从 header 提取 traceId 写入 MDC,实现端到端链路      |
| 业务前置过滤       | 在 onConsume 中按 topic / partition 过滤消息         |
| 提交审计           | 在 onCommit 写入审计日志                            |
| 数据脱敏           | 检测到敏感字段触发脱敏逻辑(注意 onConsume 返回新对象)|

---

## 十、多线程消费

### 10.1 Consumer 的线程模型

KafkaConsumer **不是线程安全的**,但有 3 种常用做法实现多线程消费:

```text
   ┌──────────────────────────────────────┐
   │ (1) 单 Consumer + 多线程处理         │   ← 最简单
   └──────────────────────────────────────┘

   ┌──────────────────────────────────────┐
   │ (2) 多 Consumer 实例                  │   ← 灵活,官方推荐
   │    (多 JVM / 多 Consumer)             │
   └──────────────────────────────────────┘

   ┌──────────────────────────────────────┐
   │ (3) Consumer 池                      │   ← 高阶
   │    (每线程一个 Consumer + 共享位移)   │
   └──────────────────────────────────────┘
```

### 10.2 单 Consumer 多线程(需保证线程安全)

**模式**:一个 Consumer 拉消息,**用线程池处理每条消息**。

```java
public class MultiThreadConsume {
    private final KafkaConsumer<String, String> consumer;
    private final ExecutorService executor = Executors.newFixedThreadPool(10);

    public void consume() {
        consumer.subscribe(Collections.singletonList("order-topic"));

        while (running) {
            ConsumerRecords<String, String> records = consumer.poll(Duration.ofMillis(100));
            for (final ConsumerRecord<String, String> record : records) {
                executor.submit(() -> handleRecord(record));
            }
        }
    }

    private void handleRecord(ConsumerRecord<String, String> record) {
        // 业务处理,**可并行**
        // 注意:commitOffset 与实际完成时间不一致,需谨慎
    }
}
```

**关键约束**:
- `KafkaConsumer` 本体**不能多线程访问**,只能在 poll 线程用
- 业务处理可并行
- Offset 提交不可与"业务完成"严格对齐 → **要么走自动提交(简化)**
- 处理顺序不保证 → **要求顺序时请保证消息带相同 key 并发度受限**

### 10.3 多 Consumer 实例(官方推荐)

**模式**:每个线程/进程创建独立的 KafkaConsumer,**各自负责一组分区**。

```java
public class MultiConsumer {
    public static void main(String[] args) {
        // 启动 3 个 Consumer 线程
        ExecutorService pool = Executors.newFixedThreadPool(3);
        for (int i = 0; i < 3; i++) {
            pool.execute(new ConsumerWorker("consumer-" + i));
        }
    }
}

class ConsumerWorker implements Runnable {
    private final KafkaConsumer<String, String> consumer;

    ConsumerWorker(String name) {
        Properties props = new Properties();
        props.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, "hadoop102:9092");
        props.put(ConsumerConfig.GROUP_ID_CONFIG, "order-group");
        props.put(ConsumerConfig.GROUP_INSTANCE_ID_CONFIG, name);  // 静态成员
        props.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class);
        props.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class);
        this.consumer = new KafkaConsumer<>(props);
    }

    @Override
    public void run() {
        try {
            consumer.subscribe(Collections.singletonList("order-topic"));
            while (running) {
                ConsumerRecords<String, String> records = consumer.poll(Duration.ofMillis(1000));
                for (ConsumerRecord<String, String> record : records) {
                    handle(record);
                }
                consumer.commitSync();
            }
        } finally {
            consumer.close();
        }
    }
}
```

**关键配置**:
- `group.instance.id` + `partition.assignment.strategy=CooperativeStickyAssignor`:**静态成员 + 协作式 Rebalance**,新增 Consumer 不需要全组停摆

### 10.4 三种模式对比

| 模式                         | 实现难度 | 顺序保证 | 位移精确控制 | 并发处理 | 推荐     |
|------------------------------|----------|----------|---------------|----------|----------|
| 单 Consumer 多线程处理       | 简单     | 乱序     | 受限          | 高       | 简单场景 |
| 多 Consumer 实例             | 中等     | 按分区   | 独立控制      | 高       | **生产推荐** |
| Consumer 池 + 共享 Offset    | 复杂     | 难       | 难            | 最高     | 极少见   |

---

## 十一、性能优化

### 11.1 性能优化全景

| 维度           | 优化点                                    |
|----------------|-------------------------------------------|
| **拉取效率**   | fetch.min.bytes / fetch.max.wait.ms        |
| **单批吞吐**   | max.poll.records                           |
| **消费间隔**   | max.poll.interval.ms                       |
| **提交频率**   | enable.auto.commit / 异步提交              |
| **反序列化**   | 批量反序列化,避免单条反复创建对象          |
| **业务处理**   | 异步化、批量化、并行化                       |
| **网络**       | receive/send buffer / 长时间连接复用       |
| **Group 协调** | group.instance.id + CooperativeSticky      |

### 11.2 fetch.min.bytes 调整

```properties
# 高吞吐场景:把 fetch.min.bytes 调大,让 Broker 等待数据累积再返回
# 但会增加延迟
fetch.min.bytes=10240        # 10KB
fetch.max.wait.ms=1000       # 最长等 1s
```

**权衡**:
- 大值:吞吐高,延迟高(适合**批量消费、离线处理**)
- 小值:延迟低,吞吐低(适合**实时处理、在线业务**)

### 11.3 max.poll.records 调整

```properties
# 单次 poll 返回的最大记录数
max.poll.records=1000
```

**权衡**:
- 大值:单批处理量大,批处理效率高,但单批耗时增加 → 触发 `max.poll.interval.ms` 超时
- 小值:每批轻量,业务响应及时,但 **Rebalance 次数增多,Broker IO 频率高**

### 11.4 批量消费模式

```java
// 接收一批 records → 批量处理
List<ConsumerRecord<String, Order>> batch = new ArrayList<>();
while (running) {
    ConsumerRecords<String, Order> records = consumer.poll(Duration.ofMillis(500));
    if (records.isEmpty()) {
        continue;
    }
    // 批量提交数据库等
    List<Order> orders = new ArrayList<>();
    for (ConsumerRecord<String, Order> record : records) {
        orders.add(record.value());
    }
    orderRepository.batchInsert(orders);  // 一次数据库事务处理一批
    consumer.commitSync();
}
```

### 11.5 异步消费与背压控制

```java
// 把 poll 结果放入有界队列,业务线程异步处理
BlockingQueue<ConsumerRecord<String, String>> queue = new LinkedBlockingQueue<>(10000);

// poll 线程
while (running) {
    ConsumerRecords<String, String> records = consumer.poll(Duration.ofMillis(200));
    for (ConsumerRecord<String, String> record : records) {
        queue.put(record);   // 队列满时阻塞,自动背压
    }
}

// 业务线程(可多个)
while (running) {
    ConsumerRecord<String, String> record = queue.take();
    handle(record);
}
```

### 11.6 TCP 网络参数优化

```properties
# 接收缓冲
receive.buffer.bytes=131072
# 发送缓冲
send.buffer.bytes=262144
# 请求超时
request.timeout.ms=40000
```

### 11.7 Group 静态成员(static membership)

```properties
# 静态成员:Group 内的"身份"固定
# 重启时若身份不变,**不会触发 Rebalance**
group.instance.id=order-consumer-1
session.timeout.ms=60000
heartbeat.interval.ms=20000
```

**优势**:
- 滚动重启时,**整个 Group 不需要 Rebalance**
- 与 `CooperativeSticky` 配合,**几乎零停机**

---

## 十二、实战代码示例

### 12.1 Java Consumer 完整代码(精确一次语义简化版)

```java
package com.example.kafka;

import org.apache.kafka.clients.consumer.*;
import org.apache.kafka.common.TopicPartition;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.time.Duration;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;

public class OrderConsumer implements AutoCloseable {
    private static final Logger log = LoggerFactory.getLogger(OrderConsumer.class);

    private final KafkaConsumer<String, String> consumer;
    private final AtomicBoolean running = new AtomicBoolean(true);

    public OrderConsumer(String bootstrapServers, String groupId, List<String> topics) {
        Properties props = new Properties();
        props.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
        props.put(ConsumerConfig.GROUP_ID_CONFIG, groupId);
        props.put(ConsumerConfig.CLIENT_ID_CONFIG, "order-consumer-" + UUID.randomUUID());

        // 反序列化
        props.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class);
        props.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class);

        // 位移与提交
        props.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "earliest");
        props.put(ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG, false);

        // 性能与心跳
        props.put(ConsumerConfig.MAX_POLL_RECORDS_CONFIG, 500);
        props.put(ConsumerConfig.MAX_POLL_INTERVAL_MS_CONFIG, 300000);
        props.put(ConsumerConfig.SESSION_TIMEOUT_MS_CONFIG, 30000);
        props.put(ConsumerConfig.HEARTBEAT_INTERVAL_MS_CONFIG, 10000);
        props.put(ConsumerConfig.FETCH_MIN_BYTES_CONFIG, 1024);
        props.put(ConsumerConfig.FETCH_MAX_WAIT_MS_CONFIG, 1000);

        // 分区分配
        props.put(ConsumerConfig.PARTITION_ASSIGNMENT_STRATEGY_CONFIG,
                  "org.apache.kafka.clients.consumer.CooperativeStickyAssignor");

        // 拦截器
        props.put(ConsumerConfig.INTERCEPTOR_CLASSES_CONFIG,
                  "com.example.kafka.LatencyStatsInterceptor");

        this.consumer = new KafkaConsumer<>(props);
        this.consumer.subscribe(topics);
    }

    public void run() {
        try {
            while (running.get()) {
                ConsumerRecords<String, String> records =
                        consumer.poll(Duration.ofMillis(1000));

                if (records.isEmpty()) {
                    continue;
                }

                for (ConsumerRecord<String, String> record : records) {
                    try {
                        handleRecord(record);
                    } catch (Exception e) {
                        log.warn("handle record failed, offset={}", record.offset(), e);
                        // 业务失败:重试 / DLT / 跳过(根据业务策略)
                    }
                }

                // 业务处理完毕后异步提交
                consumer.commitAsync((offsets, ex) -> {
                    if (ex != null) {
                        log.error("commit failed, offsets={}", offsets, ex);
                    }
                });
            }
        } catch (WakeupException e) {
            // 主动关闭触发的异常
            log.info("wake up exception, exiting...");
        } finally {
            close();
        }
    }

    private void handleRecord(ConsumerRecord<String, String> record) {
        log.info("partition={} offset={} key={} value={}",
                record.partition(), record.offset(), record.key(), record.value());
        // ... 实际业务处理 ...
    }

    public void shutdown() {
        running.set(false);
        consumer.wakeup();   // 让 poll() 退出阻塞
    }

    @Override
    public void close() {
        try {
            consumer.commitSync();  // 关闭前同步提交一次
        } finally {
            consumer.close();
            log.info("consumer closed");
        }
    }

    public static void main(String[] args) {
        OrderConsumer consumer = new OrderConsumer(
                "hadoop102:9092,hadoop103:9092,hadoop104:9092",
                "order-consumer-group",
                Arrays.asList("order-topic"));

        Runtime.getRuntime().addShutdownHook(new Thread(consumer::shutdown));
        consumer.run();
    }
}
```

### 12.2 Spring Boot @KafkaListener 完整示例

#### 12.2.1 Maven 依赖

```xml
<dependency>
    <groupId>org.springframework.kafka</groupId>
    <artifactId>spring-kafka</artifactId>
    <version>2.9.x</version>
</dependency>
```

#### 12.2.2 application.yml

```yaml
spring:
  kafka:
    bootstrap-servers: hadoop102:9092,hadoop103:9092,hadoop104:9092

    consumer:
      group-id: order-spring-group
      auto-offset-reset: earliest
      enable-auto-commit: false
      max-poll-records: 500
      key-deserializer: org.apache.kafka.common.serialization.StringDeserializer
      value-deserializer: org.springframework.kafka.support.serializer.JsonDeserializer

      properties:
        spring.json.trusted.packages: com.example.kafka.entity
        spring.json.use.type.headers: false
        spring.json.value.default.type: com.example.kafka.entity.Order
        session.timeout.ms: 30000
        heartbeat.interval.ms: 10000
        max.poll.interval.ms: 300000

    listener:
      ack-mode: manual_immediate    # 手动 ack
      concurrency: 3                 # 启动 3 个 Consumer 线程
      poll-timeout: 1000
```

#### 12.2.3 Java 代码

```java
package com.example.kafka;

import com.example.kafka.entity.Order;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.support.Acknowledgment;
import org.springframework.stereotype.Component;

@Component
public class OrderKafkaListener {
    private static final Logger log = LoggerFactory.getLogger(OrderKafkaListener.class);

    @KafkaListener(
        topics = "order-topic",
        groupId = "order-spring-group",
        concurrency = "3"
    )
    public void onMessage(ConsumerRecord<String, Order> record,
                          Acknowledgment ack) {
        try {
            log.info("Received: partition={} offset={} key={} value={}",
                    record.partition(), record.offset(), record.key(), record.value());

            // 1. 业务处理
            handleOrder(record.value());

            // 2. 手动 ack (提交 Offset)
            ack.acknowledge();
        } catch (Exception e) {
            log.error("handle order failed", e);
            // 不 ack → 下次 poll 重复消费
            // 或使用 @KafkaListener(errorHandler = ...)
        }
    }

    @KafkaListener(
        topics = "payment-topic",
        groupId = "payment-spring-group",
        topicPattern = ".*"
    )
    public void onPaymentMessage(ConsumerRecord<String, String> record,
                                  Acknowledgment ack) {
        // ... 支付消息处理 ...
        ack.acknowledge();
    }

    private void handleOrder(Order order) {
        // ... 调用业务服务 ...
    }
}
```

#### 12.2.4 配置类(可选,更灵活)

```java
@Configuration
@EnableKafka
public class KafkaConsumerConfig {

    @Bean
    public ConsumerFactory<String, Order> orderConsumerFactory() {
        Map<String, Object> props = new HashMap<>();
        props.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, "hadoop102:9092");
        props.put(ConsumerConfig.GROUP_ID_CONFIG, "order-group");
        props.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class);
        props.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, JsonDeserializer.class);
        props.put(ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG, false);
        props.put(JsonDeserializer.TRUSTED_PACKAGES, "com.example.kafka.entity");
        return new DefaultKafkaConsumerFactory<>(props);
    }

    @Bean
    public ConcurrentKafkaListenerContainerFactory<String, Order> orderListenerFactory(
            ConsumerFactory<String, Order> cf) {
        ConcurrentKafkaListenerContainerFactory<String, Order> factory =
                new ConcurrentKafkaListenerContainerFactory<>();
        factory.setConsumerFactory(cf);
        factory.getContainerProperties().setAckMode(AckMode.MANUAL_IMMEDIATE);
        factory.setConcurrency(3);
        factory.setBatchListener(true);
        return factory;
    }
}
```

### 12.3 常见生产配置参数速查表

| 参数                          | 推荐值         | 说明                                  |
|-------------------------------|----------------|---------------------------------------|
| bootstrap.servers             | 3~5 个地址     | 覆盖半个集群即可                      |
| group.id                      | 业务模块名     | 一类业务一个 group                    |
| auto.offset.reset             | earliest       | 大部分场景                            |
| enable.auto.commit            | false          | 严格场景手动控制                      |
| max.poll.records              | 200~1000       | 视业务处理速度                        |
| max.poll.interval.ms          | ≫ 单批耗时    | 至少 3 倍,推荐 5 倍以上               |
| session.timeout.ms            | 30000~45000    | 默认即可                              |
| heartbeat.interval.ms         | session/3      | 默认即可                              |
| fetch.min.bytes               | 1(低延迟)/10K(高吞吐)| 按场景调                          |
| fetch.max.wait.ms             | 500~2000       | 配合 fetch.min.bytes                  |
| partition.assignment.strategy | CooperativeSticky | Kafka 2.4+ 推荐                    |
| isolation.level               | read_committed | 读事务消息                            |
| group.instance.id             | 固定唯一       | 静态成员 + 滚动升级                   |

---

## 十三、核心要点速记

- **Kafka Consumer 采用 Pull 模型**,Consumer 主动从 Broker 拉取消息,与 RabbitMQ 的 Push 形成对照
- **核心配置三件套**:`bootstrap.servers`(连接入口)、`group.id`(组标识)、`key/value.deserializer`(反序列化)
- **auto.offset.reset**:有新 Group 上线时,`earliest`从最旧读、`latest`从最新读、`none`报错
- **enable.auto.commit 与数据准确性成反比**;生产关键业务**必须手动提交**,并按业务结果控制提交时机
- **commitSync 同步阻塞会重试**,**commitAsync 异步非阻塞不重试**,生产推荐"平时异步 + 关闭前同步"混合模式
- **Consumer Group 内单播、组间多播**:同组内 Partition 互斥、不同 Group 互相独立
- **Group 内 Consumer 数量 ≤ Partition 数**,多余的 Consumer 闲置
- **Rebalance 触发**:成员上下线、订阅变化、Partition 数变化,会引发短期"停止消费"
- **分区分配策略**:Range(默认)、RoundRobin、Sticky、CooperativeSticky(Kafka 2.4+ 推荐)
- **Offset 存储在 `__consumer_offsets`**;`__consumer_offsets` 默认 50 个分区,副本数由 `offsets.topic.replication.factor` 控制
- **seek/seekToBeginning/seekToEnd/offsetsForTimes** 四个 API 配套使用,实现精准 Offset 控制
- **KafkaConsumer 非线程安全**:单 Consumer 处理多线程需业务线程池;多 Consumer 实例是官方推荐的多线程方案
- **静态成员(`group.instance.id`) + CooperativeSticky** 是 Kafka 3.x 推荐的低 Rebalance 方案
- **max.poll.interval.ms 必须 ≫ 单批业务耗时**,否则会因"消费太慢"被踢出 Group
- **CooperativeStickyAssignor**:增量协作式 Rebalance,避免传统策略的 stop-the-world
- **`ErrorHandlingDeserializer`** 能让反序列化失败时放入 DLT,避免单条坏数据整批失败
- **`spring-kafka` 用 `@KafkaListener + ManualImmediate ack` 是 Spring 生态最常见的 Consumer 写法**
- **常见坑位**:group.id 写错导致从头消费;max.poll.interval.ms 太短被踢出;Consumer.run() 主线程没有 wakeup() 退出机制
- **Offset 提交时机**:自动提交在 poll 后定时跑,手动提交在业务成功后调用;**从业务完成到 Offset 提交之间存在重复消费窗口**
- **消费 lag 监控**:`kafka-consumer-groups.sh --describe --group <group>` 查看 `LAG` 字段
- **顺序保证:同一 Partition 内有序**,不同 Partition 间无序;如要全局顺序,要保证 1 Partition 配 1 Consumer
