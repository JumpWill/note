# RedPanda Schema Registry 与 Wasm Transforms

> RedPanda 区别于 Kafka 的两大杀手锏,都集中在这一章:**内置的 Schema Registry**(与 Confluent 协议兼容,但和 Broker 同一进程、零额外运维)与 **Wasm Transforms**(在 Broker 进程内执行用户编写的 WebAssembly 函数,做数据脱敏、字段映射、过滤、协议转换,无需额外部署 Connect/Streams 集群)。这两件武器把 RedPanda 从"Kafka 的 C++ 替代品"拔高到了"边缘 + 云端都能跑的轻量流平台"。

---

## 一、RedPanda Schema Registry 概述

### 1.1 什么是 Schema Registry

**Schema Registry** 是消息中间件生态中的 **Schema 中心化管理层**:生产者、消费者不直接传输完整 Schema(Avro IDL / Protobuf `.proto` / JSON Schema 文档),而是在消息体里塞一个 **Schema ID**(整数),Consumer/Producer 通过 HTTP 调用 Registry 拿到真正的 Schema,再进行编解码。

```text
传统 JSON 消息 (无 Schema 管理):
   {"orderId":1001,"amount":99.5,"currency":"CNY"}
   ──► 字段名变更?消费者直接挂掉;类型错?运行期才暴露

引入 Schema Registry:
   ┌─────────┐         ┌──────────────────┐        ┌─────────┐
   │ Producer │  POST   │  Schema Registry │  GET   │ Consumer│
   │ 注册 Avro│ ───────►│  (保存 schema)   │ ◄────── │ 查 schema│
   └─────────┘         └──────────────────┘        └─────────┘
        │                                                ▲
        │  发送消息: [magic byte][schema id][payload]    │
        └────────────────────────────────────────────────►│
                                                          │
                                              用 schema id 拉取 schema,反序列化
```

### 1.2 RedPanda 内置 Schema Registry 的差异

RedPanda 把 Schema Registry **直接嵌入到 Broker 进程**,而不是像 Confluent 那样单独跑一个 Java 服务:

| 维度               | Confluent Schema Registry             | RedPanda Schema Registry                |
|------------------|--------------------------------------|----------------------------------------|
| 部署形态           | 独立 Java 进程 + Kafka 内部 topic `_schemas` 持久化 | 嵌入在 RedPanda Broker 进程,**无独立进程** |
| 持久化             | Kafka topic `_schemas`(运维门槛高)        | RedPanda 内部 `kafka_internal` topic |
| API 兼容           | 原始 Confluent REST 协议                  | 100% 兼容 Confluent REST API           |
| 高可用             | 需多实例 + 外部负载均衡                     | Broker 自带 Raft 共识,天然高可用          |
| 资源占用           | 每个 SR 实例 ≥ 1GB JVM 堆                  | 零额外进程,直接复用 Broker 资源            |
| 启用方式           | 下载/配置 docker-compose                 | `rpk cluster config set schema_registry.enabled=true` |
| 性能瓶颈           | JVM GC + 网络一跳                         | 本地 in-process 调用,**毫秒级**             |

### 1.3 三大格式支持

RedPanda Schema Registry 默认支持:

| 格式            | Schema 描述方式            | 编解码库                   | 典型场景                       |
|---------------|------------------------|------------------------|----------------------------|
| **Avro**      | JSON 格式的 Avro IDL       | avro-c / avro (Java/Python) | Hadoop 生态、大数据、CDC         |
| **Protobuf**  | `.proto` 文件二进制编译       | protobuf-c / protobuf    | gRPC、跨语言微服务、Android/iOS |
| **JSON Schema** | Draft 2020-12 JSON 规范   | jsonschema-cpp            | 前后端契约、配置即 Schema         |

---

## 二、与 Confluent Schema Registry 对比

### 2.1 API 兼容性

RedPanda 实现了 **Confluent Schema Registry 公开 REST API 100% 子集**,所有主流客户端 (Java/SrClient、Python/confluent-kafka-python、Go/schemaregistry) **零修改** 即可对接:

```text
Confluent SR REST 协议路径:
  POST   /subjects/{subject}/versions          注册新版本
  GET    /subjects/{subject}/versions          列出所有版本
  GET    /subjects/{subject}/versions/{id}     按 ID 查
  GET    /subjects/{subject}/versions/latest   最新版本
  POST   /compatibility/subjects/{subject}/versions 兼容性检查
  GET    /schemas/ids/{id}                     按 ID 查 schema 内容
  GET    /subjects                             列出所有 subject
  DELETE /subjects/{subject}/versions/{id}     删除版本 (软删)
  POST   /config/{subject}                     设置兼容性级别

RedPanda SR 100% 兼容以上所有路径
```

### 2.2 性能差异

| 指标                | Confluent SR (独立部署)        | RedPanda SR (内置)              | 倍数        |
|-------------------|------------------------------|--------------------------------|-----------|
| 注册 Schema 延迟      | 50~200ms (网络一跳)              | 1~5ms (本地 in-process)         | 10x+      |
| 查询 Schema 延迟      | 10~50ms                      | < 1ms (本地缓存命中)                | 10x+      |
| 启动时间             | 30s+ (JVM + Kafka 拉取 _schemas) | 0s (随 Broker 一起起来)            | ∞         |
| 内存占用             | 每个实例 ~1GB JVM                | 几乎 0 (复用 Broker 堆)             | -         |
| 高可用切换            | 手动 LB + 客户端重试               | 自动 Raft 跟随,无感                  | -         |

### 2.3 部署差异

```text
Confluent 部署 (经典 7 节点):
  ┌────────────────────────────────────────────────────────┐
  │ 3 × ZooKeeper (KRaft 后可省)                           │
  │ 3 × Kafka Broker                                      │
  │ 3 × Schema Registry (独立 JVM,配 LB)                    │
  │ 3 × Connect Worker (可选)                              │
  │ 3 × ksqlDB Server (可选)                               │
  └────────────────────────────────────────────────────────┘
  → 运维成本:极高,Java GC 调优、SR Leader 选举、LB 健康检查

RedPanda 部署 (等价能力,3 节点):
  ┌────────────────────────────────────────────────────────┐
  │ 3 × RedPanda (Broker + Schema Registry + Wasm 内置)      │
  └────────────────────────────────────────────────────────┘
  → 运维成本:极低,单二进制,C++ 无 GC 抖动,Raft 自治
```

**关键差异**:
- Confluent 需要单独维护 **Schema Registry 集群**;RedPanda 直接复用 Broker 的 Raft 共识,SR 元数据自动随集群复制
- Confluent 需要手动配置客户端 `schema.registry.url`;RedPanda 客户端可直接用 `redpanda://broker:9092` 引导地址,SR 地址自动发现 (通过 advertised listeners)
- Confluent SR Leader 故障时需要客户端刷新元数据 + 重新选主;RedPanda SR 跟随 Raft Leader,**切换无感**

---

## 三、启用 Schema Registry

### 3.1 通过 rpk 启用

最简单的方式是使用 `rpk` CLI:

```bash
# 启用 SR
rpk cluster config set schema_registry.enabled true

# 配置端口 (默认 8081)
rpk cluster config set schema_registry.port 8081

# 配置对外地址 (客户端访问入口)
rpk cluster config set schema_registry.advertised_listeners \
  {"Listeners":[{"Name"="default","Address":"redpanda.example.com","Port"=8081}]}

# 可选:限制 SR 只接受认证客户端
rpk cluster config set schema_registry.authentication_method http_basic
```

### 3.2 通过 redpanda.yaml 启用

传统配置文件方式 (`/etc/redpanda/redpanda.yaml`):

```yaml
redpanda:
  data_directory: /var/lib/redpanda/data
  rpc_server:
    address: 0.0.0.0
    port: 33145
  kafka_api:
    address: 0.0.0.0
    port: 9092
    advertised_kafka_api_listener:
      address: redpanda.example.com
      port: 9092

# Schema Registry 配置
schema_registry:
  enabled: true            # 启用 SR
  port: 8081               # HTTP 监听端口
  schema_registry_api:
    address: 0.0.0.0
    port: 8081
    advertised_listeners:
      - name: default
        address: redpanda.example.com
        port: 8081
  # 可选: 认证
  authentication_method: http_basic

# 可选: 配合 Pandaproxy (REST 接口)
pandaproxy:
  enabled: true
  port: 8082
```

修改后重启:

```bash
sudo systemctl restart redpanda
# 或容器环境
docker compose restart redpanda
```

### 3.3 验证 SR 已启动

```bash
# 健康检查
curl -s http://redpanda:8081/ | jq .
# { "schema_registry": "..." }

# 列出所有 subject
curl -s http://redpanda:8081/subjects
# []

# 查看全局配置 (兼容性级别)
curl -s http://redpanda:8081/config | jq .
# { "compatibilityLevel": "BACKWARD" }
```

---

## 四、Schema 注册

### 4.1 Avro Schema 注册流程

**Schema 注册的本质**:客户端把 Schema 文本 (Avro JSON / Protobuf 二进制 / JSON Schema 文本) 通过 HTTP POST 到 SR,SR 返回一个全局唯一的 **Schema ID**(整数);客户端后续发送消息时,把 `[magic byte][schema id][encoded payload]` 拼到一起。

```text
注册流程:
   ┌──────────┐                                  ┌──────────────┐
   │ Producer │  POST /subjects/orders-value/versions │                │
   │          │ ────────────────────────────────►│              │
   │          │  {                               │   Schema     │
   │          │   "schema": "{...avro json...}"  │   Registry   │
   │          │  }                               │              │
   └──────────┘                                  └──────┬───────┘
                                                       │
                                              ┌────────▼─────────┐
                                              │ 兼容性检查 (BACKWARD) │
                                              │ 保存到内部 topic     │
                                              │ 返回 id = 7        │
                                              └──────────────────┘
                                                       │
   ┌──────────┐                                          │
   │ Producer │ ◄────────────────────────────────────────┘
   │ 收到 id=7 │
   └──────────┘

消息格式:
   ┌─────────┬───────────┬──────────────────┐
   │ magic=0 │ schema id │ Avro encoded     │
   │ (1 byte)│ (4 bytes) │ payload (binary) │
   └─────────┴───────────┴──────────────────┘
```

### 4.2 注册 Avro Schema 示例

```bash
# 1. 准备 Avro Schema (订单 value)
cat > /tmp/order-value.avsc << 'EOF'
{
  "type": "record",
  "name": "Order",
  "namespace": "com.example.orders",
  "fields": [
    {"name": "orderId", "type": "string"},
    {"name": "userId",  "type": "string"},
    {"name": "amount",  "type": "double"},
    {"name": "currency","type": "string", "default": "CNY"},
    {"name": "createdAt","type": "long", "logicalType": "timestamp-millis"}
  ]
}
EOF

# 2. 注册到 Schema Registry
curl -X POST http://redpanda:8081/subjects/orders-value/versions \
  -H "Content-Type: application/vnd.schemaregistry.v1+json" \
  --data @<(jq -n --arg s "$(cat /tmp/order-value.avsc)" \
    '{schema: $s, schemaType: "AVRO"}')
# 返回: {"id": 1}

# 3. 查看该 subject 的所有版本
curl -s http://redpanda:8081/subjects/orders-value/versions
# [1]

# 4. 按 ID 查 Schema
curl -s http://redpanda:8081/schemas/ids/1 | jq .

# 5. 查最新版本
curl -s http://redpanda:8081/subjects/orders-value/versions/latest | jq .
```

### 4.3 注册 Protobuf Schema

```bash
# 1. 准备 .proto 文件
cat > /tmp/order.proto << 'EOF'
syntax = "proto3";
package ecommerce;
option java_package = "com.example.orders";
message Order {
  string order_id = 1;
  string user_id  = 2;
  double amount   = 3;
  string currency = 4;
  int64  created_at = 5;
}
EOF

# 2. 编译为 FileDescriptorSet 二进制
protoc --include_imports --descriptor_set_out=/tmp/order.desc /tmp/order.proto

# 3. 把二进制转 base64,注册到 SR
B64=$(base64 -w 0 /tmp/order.desc)
curl -X POST http://redpanda:8081/subjects/orders-proto-value/versions \
  -H "Content-Type: application/vnd.schemaregistry.v1+json" \
  --data @<(jq -n --arg s "$B64" \
    '{schema: $s, schemaType: "PROTOBUF", references: []}')
```

### 4.4 注册 JSON Schema

```bash
# 1. 准备 JSON Schema
cat > /tmp/order.schema.json << 'EOF'
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "properties": {
    "orderId":  {"type": "string"},
    "userId":   {"type": "string"},
    "amount":   {"type": "number"},
    "currency": {"type": "string", "default": "CNY"}
  },
  "required": ["orderId", "userId", "amount"]
}
EOF

# 2. 注册
curl -X POST http://redpanda:8081/subjects/orders-json-value/versions \
  -H "Content-Type: application/vnd.schemaregistry.v1+json" \
  --data @<(jq -n --arg s "$(cat /tmp/order.schema.json)" \
    '{schema: $s, schemaType: "JSON"}')
```

### 4.5 兼容性检查

在注册前,可以先做 **dry-run** 兼容性测试:

```bash
curl -X POST \
  http://redpanda:8081/compatibility/subjects/orders-value/versions/latest \
  -H "Content-Type: application/vnd.schemaregistry.v1+json" \
  --data @<(jq -n --arg s "$(cat /tmp/order-v2.avsc)" \
    '{schema: $s, schemaType: "AVRO"}')
# 返回: {"is_compatible": true} 或 false + 错误列表
```

---

## 五、生产者使用 Schema

### 5.1 Java:Avro + SchemaRegistry

**Maven 依赖**:

```xml
<dependency>
  <groupId>org.apache.kafka</groupId>
  <artifactId>kafka-clients</artifactId>
  <version>3.6.0</version>
</dependency>
<dependency>
  <groupId>io.confluent</groupId>
  <artifactId>kafka-avro-serializer</artifactId>
  <version>7.5.0</version>
</dependency>
<dependency>
  <groupId>io.confluent</groupId>
  <artifactId>kafka-schema-registry-client</artifactId>
  <version>7.5.0</version>
</dependency>
```

**Properties 配置**:

```java
Properties props = new Properties();
props.put("bootstrap.servers", "redpanda:9092");
props.put("key.serializer",
  "io.confluent.kafka.serializers.KafkaAvroSerializer");
props.put("value.serializer",
  "io.confluent.kafka.serializers.KafkaAvroSerializer");
// 指向 RedPanda 内置 SR (而非独立 Confluent SR)
props.put("schema.registry.url", "http://redpanda:8081");
// 可选:开启自动注册 (客户端启动时若 SR 无此 schema 自动注册)
props.put("auto.register.schemas", true);
// 可选:ID 兼容性检查
props.put("use.latest.version", false);

KafkaProducer<String, Order> producer =
    new KafkaProducer<>(props);
```

**使用**:

```java
// Order 由 Avro Maven Plugin 自动生成
Order order = Order.newBuilder()
    .setOrderId("O-1001")
    .setUserId("U-2002")
    .setAmount(99.5)
    .setCurrency("CNY")
    .setCreatedAt(System.currentTimeMillis())
    .build();

ProducerRecord<String, Order> record =
    new ProducerRecord<>("orders", order.getOrderId().toString(), order);

producer.send(record, (meta, ex) -> {
    if (ex == null) {
        log.info("Sent to {}-{} offset={}", meta.topic(), meta.partition(), meta.offset());
    } else {
        log.error("Send failed", ex);
    }
});
```

### 5.2 Python:confluent-kafka-python

```bash
pip install confluent-kafka[avro]
```

```python
from confluent_kafka import Producer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer

# SR 客户端
sr = SchemaRegistryClient({"url": "http://redpanda:8081"})

# Avro Serializer (自动注册)
avro_serializer = AvroSerializer(
    schema_registry_client=sr,
    schema_str="""{
        "type": "record",
        "name": "Order",
        "namespace": "ecommerce",
        "fields": [
            {"name": "order_id", "type": "string"},
            {"name": "user_id",  "type": "string"},
            {"name": "amount",   "type": "double"},
            {"name": "currency", "type": "string", "default": "CNY"},
            {"name": "created_at","type": "long"}
        ]
    }""",
    conf={"auto.register.schemas": True}
)

producer = Producer({
    "bootstrap.servers": "redpanda:9092",
    "key.serializer": lambda k, ctx: k.encode("utf-8") if k else None,
    "value.serializer": avro_serializer
})

# 发送
order = {
    "order_id": "O-1001",
    "user_id": "U-2002",
    "amount": 99.5,
    "currency": "CNY",
    "created_at": 1692000000000
}
producer.produce("orders", key="O-1001", value=order)
producer.flush()
```

---

## 六、消费者使用 Schema

### 6.1 Java Consumer

```java
Properties props = new Properties();
props.put("bootstrap.servers", "redpanda:9092");
props.put("group.id", "order-consumer");
props.put("key.deserializer",
  "io.confluent.kafka.serializers.KafkaAvroDeserializer");
props.put("value.deserializer",
  "io.confluent.kafka.serializers.KafkaAvroDeserializer");
props.put("schema.registry.url", "http://redpanda:8081");

KafkaConsumer<String, Order> consumer = new KafkaConsumer<>(props);
consumer.subscribe(Collections.singletonList("orders"));

while (true) {
    ConsumerRecords<String, Order> records = consumer.poll(Duration.ofMillis(500));
    for (ConsumerRecord<String, Order> r : records) {
        Order order = r.value();
        log.info("partition={} offset={} orderId={} amount={}",
            r.partition(), r.offset(), order.getOrderId(), order.getAmount());
        // 业务处理...
    }
}
```

### 6.2 Python Consumer

```python
from confluent_kafka import Consumer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroDeserializer

sr = SchemaRegistryClient({"url": "http://redpanda:8081"})
avro_deserializer = AvroDeserializer(schema_registry_client=sr)

consumer = Consumer({
    "bootstrap.servers": "redpanda:9092",
    "group.id": "order-consumer",
    "auto.offset.reset": "earliest",
    "key.deserializer": lambda k, ctx: k.decode("utf-8") if k else None,
    "value.deserializer": avro_deserializer
})

consumer.subscribe(["orders"])

while True:
    msg = consumer.poll(1.0)
    if msg is None: continue
    if msg.error():
        print("Error:", msg.error())
        continue
    order = msg.value()
    print(f"partition={msg.partition()} offset={msg.offset()} "
          f"orderId={order['order_id']} amount={order['amount']}")
```

---

## 七、Schema 演进

### 7.1 兼容性级别

Schema Registry 在注册新版本时,会根据设定的 **兼容性级别** 与历史版本做校验。级别分为四级:

| 级别                  | 含义                                                              | 适用场景              |
|---------------------|-----------------------------------------------------------------|-------------------|
| **BACKWARD** (默认)   | 新 Schema 能读**旧数据**(消费者先升级,生产者后升级)                              | 滚动升级最常用          |
| **BACKWARD_TRANSITIVE** | 严格 BACKWARD,与所有历史版本兼容                                          | 数据保留周期长的归档系统   |
| **FORWARD**         | 旧 Schema 能读**新数据**(生产者先升级,消费者后升级)                              | 反向场景较少           |
| **FORWARD_TRANSITIVE** | 严格 FORWARD                                                    | -                 |
| **FULL**            | 双向兼容 (BACKWARD + FORWARD)                                         | 不允许任何破坏性变更     |
| **FULL_TRANSITIVE** | 严格 FULL                                                         | 严格治理场景          |
| **NONE**            | 不做兼容性检查                                                        | 开发环境、临时 schema   |

**BACKWARD 的安全变更**(新 Schema 能读旧数据):
- ✅ 给 record 增加**带默认值**的字段
- ✅ 删除**带默认值**的字段(消费者用默认值填充)
- ✅ 调整字段顺序(编码后无影响)
- ✅ 修改字段默认值

**BACKWARD 的破坏性变更**(会导致旧 Consumer 无法解码旧数据):
- ❌ 删除**没有默认值**的字段
- ❌ 修改字段类型(int → long 算破坏性,即使兼容)
- ❌ 修改 union 的第一个非 null 类型
- ❌ 重命名 record / enum / field(兼容性依赖 `Aliases` 配置)

### 7.2 配置兼容性级别

```bash
# 全局默认级别
curl -X PUT http://redpanda:8081/config \
  -H "Content-Type: application/vnd.schemaregistry.v1+json" \
  -d '{"compatibilityLevel": "FULL"}'

# 针对单个 subject 覆盖
curl -X PUT http://redpanda:8081/config/orders-value \
  -H "Content-Type: application/vnd.schemaregistry.v1+json" \
  -d '{"compatibilityLevel": "BACKWARD"}'

# 查询当前配置
curl -s http://redpanda:8081/config/orders-value
```

### 7.3 Schema 演进策略

**策略一:扩展型演进 (推荐)**

只允许添加可选字段 + 修改默认值:

```text
v1 (2024-01):
  orderId, userId, amount, currency

v2 (2024-06)  ──► 添加 discount 字段 (default 0.0)
  orderId, userId, amount, currency, discount

v3 (2024-12)  ──► 添加 note 字段 (default "")
  orderId, userId, amount, currency, discount, note
```

**策略二:版本号管理 + Aliases**

允许重命名字段,使用 `Aliases` 保持向后兼容:

```json
{
  "type": "record",
  "name": "Order",
  "fields": [
    {
      "name": "userId",
      "type": "string",
      "aliases": ["customerId", "buyerId"]
    }
  ]
}
```

**策略三:Union 多版本共存**

通过 union 同时支持新旧结构(常用于大型迁移期):

```json
{
  "type": "record",
  "name": "Event",
  "fields": [
    {"name": "type", "type": "string"},
    {
      "name": "payload",
      "type": ["null", "OrderV1", "OrderV2"],
      "default": null
    }
  ]
}
```

---

## 八、实战案例:Schema 演进与跨语言共享

### 8.1 订单服务 Schema 演进

**场景**:订单服务从 v1 演进到 v3,全程不停服,新老 Consumer 并存 6 个月。

```text
时间 ─────────────────────────────────────────────────────────►

   v1 (BACKWARD)              v2 (BACKWARD)               v3 (FULL)
   ─────────────               ──────────────              ─────────────
   orderId                     orderId                     orderId
   userId                      userId                      userId
   amount                      amount                      amount
   currency                    currency                    currency
                               discount (default 0.0)       discount
                                                            note (default "")
                                                            v3MigrationTag

消费者部署:  旧 C1(v1) → C1' (v2) → C2 (v3)         全员 v3
生产者部署:  P1(v1) → P1'(v2) → P2(v3)              全员 v3
```

**步骤**:
1. **部署新消费者**(v2-aware),先消费 v1 数据
2. **生产者升级**开始发 v2(带 `discount` 字段)
3. 旧消费者忽略未知字段,无感知消费
4. **重复**添加 v3 的 `note` 字段
5. 6 个月后,旧消费者全部下线,清理 _schemas 中过期版本

### 8.2 跨语言 Schema 共享

同一份 Avro Schema,可被 Java / Python / Go / C++ 服务共享:

```text
   ┌────────────────────────────────────────────────────────────┐
   │  Schema Registry (RedPanda 内置)                              │
   │  /subjects/order-value/versions                              │
   │   - id=1: v1 (原始 Avro JSON)                                │
   │   - id=2: v2 (新增 discount)                                 │
   └────────────────────────────────────────────────────────────┘
        ▲          ▲             ▲              ▲
        │          │             │              │
   ┌────┴───┐ ┌────┴────┐ ┌──────┴─────┐ ┌─────┴─────┐
   │  Java  │ │ Python  │ │    Go      │ │   C++     │
   │ Avro   │ │ Avro    │ │ avro-go    │ │ avro-c    │
   │ Order  │ │ dict    │ │ struct     │ │ struct    │
   └────────┘ └─────────┘ └────────────┘ └───────────┘
   订单服务    数据分析     网关服务        嵌入式
```

**Go 示例**:

```go
package main

import (
    "github.com/confluentinc/confluent-kafka-go/v2/schemaregistry"
    "github.com/confluentinc/confluent-kafka-go/v2/schemaregistry/avro"
    "github.com/confluentinc/confluent-kafka-go/v2/kafka"
)

func main() {
    sr, _ := schemaregistry.NewClient(schemaregistry.NewConfig("http://redpanda:8081"))
    avroSerde, _ := avro.NewSerde(sr)

    p, _ := kafka.NewProducer(&kafka.ConfigMap{
        "bootstrap.servers": "redpanda:9092",
    })

    valueSerde, _ := avroSerde.NewSerde("orders-value", false)

    payload := map[string]interface{}{
        "order_id":   "O-1001",
        "user_id":    "U-2002",
        "amount":     99.5,
        "currency":   "CNY",
        "created_at": int64(1692000000000),
    }
    encoded, _ := valueSerde.Serialize("orders", payload)

    p.Produce(&kafka.Message{
        TopicPartition: kafka.TopicPartition{Topic: stringPtr("orders"), Partition: kafka.PartitionAny},
        Key:   []byte("O-1001"),
        Value: encoded,
    }, nil)
}
```

---

## 九、Wasm Transforms 概述(核心特色)

### 9.1 概念

**Wasm Transforms** 是 RedPanda 的 **杀手级特性**,允许用户在 **Broker 进程内** 执行用户编写的 **WebAssembly**(Wasm) 函数,对每条消息做转换:

```text
传统 Kafka 架构:
   Producer ──► Kafka Broker (只搬运) ──► Consumer
                                            │
                                            ▼
                                   在 Consumer 端做转换
                                   (意味着每条消息都要落到
                                    下游才处理)

RedPanda Wasm Transforms:
   Producer ──► RedPanda Broker (内置 Wasm 函数)
                              │
                              ▼
                       在 Broker 端即时转换
                       ── 脱敏 ── 映射 ── 过滤 ── 增强 ── 协议转换
                              │
                              ▼
                       写回目标 Topic
```

### 9.2 与 Kafka Connect、Streams 的对比

| 维度                | Kafka Connect           | Kafka Streams        | RedPanda Wasm Transforms  |
|-------------------|-------------------------|----------------------|--------------------------|
| **部署形态**        | 独立 Worker 集群          | 应用进程内 Java 库      | **嵌入 Broker 进程**         |
| **执行位置**        | 单独 JVM 进程             | 应用进程              | **Broker 内核线程**           |
| **运行延迟**        | 100ms~秒级                | 毫秒级                | **亚毫秒级**                  |
| **资源开销**        | 每 Worker ≥ 1GB JVM      | 复用应用 JVM          | 几乎 0 (复用 Broker)         |
| **运维复杂度**      | 极高 (Connector/Task/Offset) | 中 (需自己管理状态) | **极低 (一条 rpk 命令部署)**     |
| **语言支持**        | Java(SMT)+ 各种插件        | Java/Scala           | **Rust / TinyGo / AssemblyScript** |
| **状态管理**        | Offset                  | RocksDB              | **无状态**(每条独立处理)            |
| **可处理消息量**     | 万级/秒 (受 Worker 数限制)  | 取决于应用机器          | **百万级/秒**(Broker 旁路)         |
| **典型场景**        | 异构数据库 ETL            | 复杂流处理 (join/window) | **单条消息转换**(脱敏/过滤/格式转换) |

### 9.3 Wasm Transforms 适用场景

- ✅ **数据脱敏**:信用卡号、身份证号、手机号遮罩
- ✅ **字段映射**:把上游 camelCase 转成下游 snake_case
- ✅ **协议转换**:JSON → Avro,Protobuf → JSON
- ✅ **数据增强**:补字段、加时间戳、加地理位置
- ✅ **敏感词过滤**:实时过滤违规内容
- ✅ **路由分流**:根据 payload 写到不同 topic
- ✅ **压缩/解压**:消息级 gzip/zstd 处理
- ❌ **不适合**复杂 join/聚合/window(用 Kafka Streams/Flink)

---

## 十、Wasm Transforms 架构

### 10.1 处理流程

```text
┌─────────────────────────────────────────────────────────────────┐
│                      RedPanda Broker                            │
│                                                                 │
│   ┌──────────┐    ┌──────────────────────┐    ┌──────────┐     │
│   │ Producer │───►│  Partition Log       │    │ Consumer │     │
│   │ (上游)    │    │  (Kafka 协议入站)    │    │ (下游)   │     │
│   └──────────┘    └──────────┬───────────┘    └──────────┘     │
│                              │                                  │
│                              ▼                                  │
│                    ┌──────────────────────┐                    │
│                    │ Wasm Engine          │                    │
│                    │  (Wasmtime / Wasmer) │                    │
│                    │  ┌────────────────┐  │                    │
│                    │  │ transform.wasm │  │                    │
│                    │  │ (用户编写的函数) │  │                    │
│                    │  └────────────────┘  │                    │
│                    └──────────┬───────────┘                    │
│                              │                                  │
│                              ▼                                  │
│                    ┌──────────────────────┐                    │
│                    │ 写回另一 Topic       │                    │
│                    │ (或同 Topic 覆盖)     │                    │
│                    └──────────────────────┘                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**关键点**:
- Wasm 函数在 **Broker 进程内**运行,通过 Wasmtime (RedPanda 选用) 沙箱化执行
- 函数**无状态**:每条消息独立调用 transform(record, ...)
- 输出可以写入**任意 topic**(包括与输入同 topic,但需小心循环)
- 函数不能直接访问网络/文件系统(纯计算)

### 10.2 部署到 Broker

```text
   rpk wasm deploy                  Redpanda Cluster
   ┌──────────────────┐             ┌──────────────────┐
   │ transform.wasm   │ ──────────► │ 3 × Broker      │
   │ + meta.json      │  HTTP POST  │  (内部存储:       │
   └──────────────────┘  /admin/was│   /var/lib/redpan│
                                  │    da/wasm/)    │
                                  └──────────────────┘
```

部署后,Broker 自动把 transform 绑定到指定 topic:

```yaml
# 配置文件形式 (或通过 rpk cluster config)
wasm:
  enabled: true
  # 每个 topic 绑定一个 transform
  transforms:
    - name: mask-credit-card
      input_topic: payments.in
      output_topic: payments.out
      file: mask-cc.wasm
```

### 10.3 支持的语言

| 语言                 | 编译产物       | 推荐度       | 典型场景              |
|--------------------|------------|------------|-------------------|
| **Rust**           | `*.wasm`   | ⭐⭐⭐⭐⭐   | 高性能、生产首选          |
| **TinyGo**         | `*.wasm`   | ⭐⭐⭐⭐     | 已有 Go 代码库、习惯 Go 语法的 |
| **AssemblyScript** | `*.wasm`   | ⭐⭐⭐       | 偏前端 / JS 风格        |
| C/C++              | `*.wasm`   | ⭐⭐        | 需要极致控制            |

**RedPanda 官方仅官方支持 Rust**,其他语言可用但需自行验证 ABI 兼容。

---

## 十一、开发 Wasm Transform

### 11.1 完整 Rust 示例(数据脱敏)

**项目结构**:

```text
mask-pii/
├── Cargo.toml
└── src/
    └── lib.rs
```

**Cargo.toml**:

```toml
[package]
name = "mask-pii"
version = "0.1.0"
edition = "2021"

[lib]
crate-type = ["cdylib"]    # Wasm 产物必须 cdylib

[dependencies]
redpanda-transform-sdk = "1.0"
serde = { version = "1", features = ["derive"] }
serde_json = "1"

[profile.release]
opt-level = "z"            # 极致体积优化
lto = true                 # 链接时优化
codegen-units = 1          # 减少代码段
panic = "abort"            # 不要 unwinding
strip = true               # 去除符号表
```

**src/lib.rs**(信用卡号脱敏):

```rust
use redpanda_transform_sdk::{Record, Transform, async_trait};
use serde_json::{json, Value};

/// 主 transform 函数:把每条消息的 credit_card 字段前 12 位遮罩成 *
fn main() {
    // 注册 transform 入口
    let transform = Transform {
        on_record: Some(on_record),  // 单条消息回调
    };
    redpanda_transform_sdk::run(transform);
}

/// 单条消息处理回调
fn on_record(record: Record) -> Result<Record, Box<dyn std::error::Error>> {
    // 1. 解析 JSON payload
    let mut payload: Value = serde_json::from_slice(&record.value)?;

    // 2. 如果存在 credit_card 字段,做脱敏
    if let Some(cc) = payload.get_mut("credit_card") {
        if let Some(s) = cc.as_str() {
            let masked = mask_credit_card(s);
            *cc = Value::String(masked);
        }
    }

    // 3. 同样处理身份证
    if let Some(id) = payload.get_mut("id_card") {
        if let Some(s) = id.as_str() {
            let masked = mask_id_card(s);
            *id = Value::String(masked);
        }
    }

    // 4. 加处理时间戳
    payload["processed_at"] = json!(chrono_now_millis());

    // 5. 序列化并返回
    let new_value = serde_json::to_vec(&payload)?;
    Ok(Record::new(record.key, new_value))
}

/// 信用卡号脱敏:保留前 4 后 4,中间 12 位变 *
fn mask_credit_card(cc: &str) -> String {
    let cleaned: String = cc.chars().filter(|c| !c.is_whitespace()).collect();
    if cleaned.len() < 8 {
        return "*".repeat(cleaned.len());
    }
    let prefix = &cleaned[..4];
    let suffix = &cleaned[cleaned.len()-4..];
    format!("{}{}{}", prefix, "*".repeat(cleaned.len()-8), suffix)
}

/// 身份证脱敏:保留前 6 后 4
fn mask_id_card(id: &str) -> String {
    if id.len() < 10 { return id.to_string(); }
    let prefix = &id[..6];
    let suffix = &id[id.len()-4..];
    format!("{}{}{}", prefix, "*".repeat(id.len()-10), suffix)
}

fn chrono_now_millis() -> i64 {
    use std::time::{SystemTime, UNIX_EPOCH};
    SystemTime::now().duration_since(UNIX_EPOCH)
        .unwrap_or_default().as_millis() as i64
}
```

### 11.2 编译为 Wasm

```bash
# 安装 wasm32 目标
rustup target add wasm32-unknown-unknown

# 编译为 Wasm (Release)
cargo build --release --target wasm32-unknown-unknown

# 产物位置
ls target/wasm32-unknown-unknown/release/mask_pii.wasm
# 体积应小于 1MB(常见 100~300KB)
```

### 11.3 部署到 RedPanda

```bash
# 1. 准备 meta.json (声明输入/输出 topic)
cat > meta.json << 'EOF'
{
  "name": "mask-pii",
  "inputTopic":  "payments.raw",
  "outputTopic": "payments.masked",
  "keySchema":   null,
  "valueSchema": null
}
EOF

# 2. 用 rpk 部署
rpk transform deploy \
  --binary target/wasm32-unknown-unknown/release/mask_pii.wasm \
  --name mask-pii \
  --input-topic payments.raw \
  --output-topic payments.masked

# 3. 查看已部署的 transforms
rpk transform list

# 4. 查看某个 transform 详情
rpk transform describe mask-pii

# 5. 启用/禁用
rpk transform enable mask-pii
rpk transform disable mask-pii

# 6. 删除
rpk transform delete mask-pii
```

---

## 十二、Wasm Transform 实战场景

### 12.1 数据脱敏

最常见的 Wasm Transform 场景。函数从 `record.value` 解析 JSON,把敏感字段遮罩后再写出去。

```rust
// 处理前:
{"orderId":"O-1001","creditCard":"4111 1111 1111 1111","idCard":"110101199001011234"}
// 处理后:
{"orderId":"O-1001","creditCard":"4111************1111","idCard":"110101********1234","processedAt":1692000000000}
```

### 12.2 数据增强

补字段、加时间戳、加 IP 解析的地理位置:

```rust
fn on_record(record: Record) -> Result<Record, Box<dyn std::error::Error>> {
    let mut payload: Value = serde_json::from_slice(&record.value)?;

    // 添加服务端处理时间
    payload["server_timestamp"] = json!(now_millis());
    // 添加处理版本号 (用于灰度)
    payload["transform_version"] = json!("v1.2.0");
    // 从 record 的 header 里取出 IP 字段 (需在 Kafka 客户端配置)
    if let Some(ip) = record.headers.get("client-ip") {
        payload["client_ip"] = json!(String::from_utf8_lossy(ip));
    }
    // 补默认值 (上游漏字段时)
    if !payload.get("region").is_some() {
        payload["region"] = json!("unknown");
    }

    Ok(Record::new(record.key, serde_json::to_vec(&payload)?))
}
```

### 12.3 数据过滤

**整条丢弃**:把违规消息写到 DLQ topic。

```rust
fn on_record(record: Record) -> Result<Option<Record>, Box<dyn std::error::Error>> {
    let payload: Value = serde_json::from_slice(&record.value)?;

    // 敏感词过滤
    let text = payload["comment"].as_str().unwrap_or("");
    if contains_sensitive(text) {
        // 返回 None 表示丢弃
        // (实际生产中可配合 DLQ transform 写到 dlq topic)
        return Ok(None);
    }
    Ok(Some(record))
}

fn contains_sensitive(text: &str) -> bool {
    let banned = vec!["spam", "xxx", "违规词"];
    banned.iter().any(|w| text.contains(w))
}
```

### 12.4 格式转换(JSON → Avro)

把上游 JSON 转成下游 Avro(下游用 Schema Registry):

```rust
use apache_avro::{Schema, Writer, types::Value as AvroValue};

fn on_record(record: Record) -> Result<Record, Box<dyn std::error::Error>> {
    let json: serde_json::Value = serde_json::from_slice(&record.value)?;

    // 加载 Avro Schema (实际中可缓存)
    let schema_json = r#"
        {"type":"record","name":"Order","fields":[
            {"name":"order_id","type":"string"},
            {"name":"amount","type":"double"}
        ]}
    "#;
    let schema = Schema::parse_str(schema_json)?;

    // JSON → Avro Value
    let avro_value = AvroValue::Record(vec![
        ("order_id".into(), AvroValue::String(json["orderId"].as_str().unwrap_or("").into())),
        ("amount".into(), AvroValue::Double(json["amount"].as_f64().unwrap_or(0.0))),
    ]);

    // Avro Value → 二进制
    let mut writer = Writer::new(&schema, Vec::new());
    writer.append(avro_value)?;
    let bytes = writer.into_inner()?;

    Ok(Record::new(record.key, bytes))
}
```

### 12.5 协议转换(MQTT → Kafka)

边缘设备用 MQTT 上报,RedPanda 把 MQTT payload 转成 Kafka JSON:

```rust
fn on_record(record: Record) -> Result<Record, Box<dyn std::error::Error>> {
    // MQTT payload 是二进制 (二进制)
    let mqtt: serde_json::Value = serde_json::from_slice(&record.value)?;
    // 转成下游标准结构
    let kafka_msg = json!({
        "device_id": mqtt["deviceId"],
        "metric":    mqtt["metric"],
        "value":     mqtt["value"],
        "timestamp": mqtt["ts"],
        "protocol":  "mqtt-v5"
    });
    Ok(Record::new(record.key, serde_json::to_vec(&kafka_msg)?))
}
```

---

## 十三、Wasm Transform 性能

### 13.1 部署为 Broker 内置

Wasm Transform **直接嵌入 Broker 进程**,无需独立 Worker 集群:

```text
传统 Kafka Connect 处理 100 万条消息:
   Producer → Kafka → Connect Worker (独立 JVM, 反序列化 → 处理 → 序列化 → 投递)
            网络一跳    网络一跳
   延迟: ~50ms/条, 资源: 4 核 8GB × 3 Worker

RedPanda Wasm Transform 处理 100 万条消息:
   Producer → RedPanda Broker (Wasm 沙箱内)
            零网络一跳
   延迟: < 1ms/条, 资源: 复用 Broker, 几乎 0 额外
```

### 13.2 毫秒级处理

| 消息体大小          | 简单 map 字段 | JSON 解析 + 字段重命名 | 完整脱敏 + 增强 | 格式转换 (JSON→Avro) |
|---------------|----------|---------------|--------------|-----------------|
| 1 KB          | 50μs     | 200μs          | 500μs         | 1ms             |
| 10 KB         | 100μs    | 400μs          | 1ms           | 3ms             |
| 100 KB        | 500μs    | 2ms            | 5ms           | 15ms            |
| 1 MB          | 3ms      | 15ms           | 40ms          | 100ms           |

### 13.3 资源占用

```text
Wasm Transform 资源消耗(每 100 万条/秒):
   CPU:  单核 ~30% (简单 map)
        单核 ~80% (复杂 JSON 处理)
   内存: 单 transform 实例 ~10~50MB
   磁盘: 0 (无状态)
   网络: 0 (Broker 内核)

Broker 总开销: 几乎不可见
```

### 13.4 性能调优技巧

1. **避免 JSON 解析**:能用二进制字段提取就别 parse 整个 JSON
2. **缓存正则/Schema**:把常用正则、Avro Schema 放在 `OnceLock` 静态缓存
3. **最小化分配**:用 `String::with_capacity` 预分配
4. **release profile**:`opt-level = "z"`,`lto = true`
5. **关闭 Wasm GC**:选用 `wasm32-unknown-unknown` 而非 `wasi`(避免 GC 抖动)
6. **批处理优先**:能用 batch 接口就批处理,减少调用次数

---

## 十四、完整实战:部署 + 测试 + 监控

### 14.1 项目准备

```bash
mkdir mask-pii && cd mask-pii
cargo init --lib
# 替换 Cargo.toml 与 src/lib.rs (见 11.1 节)
cargo build --release --target wasm32-unknown-unknown
ls target/wasm32-unknown-unknown/release/mask_pii.wasm
```

### 14.2 本地启动 RedPanda

```bash
docker run -d --name redpanda \
  -p 9092:9092 -p 8081:8081 \
  redpandadata/redpanda:latest \
  redpanda start \
    --overprovisioned \
    --smp 1 \
    --memory 1G \
    --reserve-memory 0M \
    --node-id 0 \
    --check=false \
    --kafka-addr PLAINTEXT://0.0.0.0:9092 \
    --advertise-kafka-addr PLAINTEXT://localhost:9092 \
    --schema-registry-addr 0.0.0.0:8081
```

### 14.3 创建 Topic + 部署 Transform

```bash
# 创建 input/output topic
rpk topic create payments.raw
rpk topic create payments.masked

# 部署 transform
rpk transform deploy mask-pii \
  --binary target/wasm32-unknown-unknown/release/mask_pii.wasm \
  --input-topic payments.raw \
  --output-topic payments.masked
```

### 14.4 测试

```bash
# 发送测试消息 (带敏感数据)
echo '{"orderId":"O-1","creditCard":"4111 1111 1111 1111","idCard":"110101199001011234","amount":99.5}' \
  | rpk topic produce payments.raw

# 消费脱敏后的消息
rpk topic consume payments.masked --num 1
# 预期输出:
# {"orderId":"O-1","creditCard":"4111************1111","idCard":"110101********1234","amount":99.5,"processedAt":1692000000000}
```

### 14.5 监控

```bash
# 查看 transform 状态
rpk transform describe mask-pii
# {
#   "name": "mask-pii",
#   "status": "running",
#   "input_topic":  "payments.raw",
#   "output_topic": "payments.masked",
#   "records_processed": 12345,
#   "errors": 0
# }

# Prometheus 指标 (RedPanda 内置)
curl -s http://redpanda:9644/metrics | grep wasm_
# wasm_transform_records_processed_total
# wasm_transform_processing_latency_seconds_bucket
# wasm_transform_errors_total
```

---

## 十五、与 Kafka Connect / Streams 对比

### 15.1 功能矩阵

| 维度               | Kafka Connect       | Kafka Streams        | RedPanda Wasm Transform  |
|------------------|---------------------|----------------------|--------------------------|
| **数据集成 (DB/ES/S3)** | ✅ 生态丰富             | ❌                    | ❌ (需自己写)               |
| **CDC (Debezium)**  | ✅ Debezium Connector | ❌                    | ❌                        |
| **流处理 (join/aggregate)** | ❌ (SMT 单条转换) | ✅ 核心能力              | ❌                        |
| **单条消息转换**       | ✅ SMT               | ✅ map/flatMap         | ✅ (内核内,最快)             |
| **数据脱敏**         | ✅ MaskField SMT | ✅ 需自己实现            | ✅ (内置场景,代码友好)         |
| **格式转换**         | ✅ Converter        | ✅ 自定义                | ✅ (支持 Avro/Protobuf)    |
| **部署复杂度**        | 极高 (集群)            | 中 (应用进程)             | **极低 (一条 rpk 命令)**       |
| **运维成本**         | 高 (Connector/Task 管理) | 中 (状态/RocksDB 调优) | **低 (无状态、无外部依赖)**       |
| **延迟**           | 100ms~秒              | 毫秒                   | **亚毫秒**                  |
| **吞吐**           | 万级/秒/Worker        | 取决于应用                | **百万级/秒/Broker**         |
| **语言**           | Java (SMT)         | Java/Scala           | Rust/TinyGo/AssemblyScript |
| **适用规模**         | 巨型 ETL             | 大规模流处理              | **轻量消息路由/转换**            |

### 15.2 选型决策树

```text
需要做什么?
   │
   ├─ 把 MySQL/PG/MongoDB → Kafka (CDC) ───────► Debezium + Kafka Connect
   │
   ├─ 把 Kafka → ES/S3/HDFS ───────────────────► Kafka Connect Sink
   │
   ├─ 复杂流处理 (join/window/aggregate/状态)  ────► Kafka Streams / Flink
   │
   ├─ 单条消息轻量转换 (脱敏/映射/过滤/协议转换) ───► ⭐ RedPanda Wasm Transform
   │                                              (零运维、亚毫秒、内置)
   │
   └─ HTTP/REST 接入 ─────────────────────────► REST Proxy / Pandaproxy
```

### 15.3 与 Kafka Streams 的核心差异

| 维度               | Kafka Streams                              | RedPanda Wasm Transform          |
|------------------|---------------------------------------------|----------------------------------|
| **状态**          | 有状态 (RocksDB、Window、Join)               | **完全无状态**(每条独立)              |
| **时间语义**        | Event-time / Ingestion-time / Processing-time | 不感知时间(只在调用时拿到当前时间)   |
| **窗口**          | Tumbling/Hopping/Session                     | ❌ (无状态,无法聚合)                |
| **Join**         | KStream-KStream / KStream-KTable            | ❌ (无状态)                       |
| **Exactly-Once** | ✅ (EOS 全链路)                              | ❌ (无事务概念,但配合 idempotent producer 可保证 at-least-once) |
| **生命周期**        | 与应用进程同生共死                              | **与 Broker 同生共死**(集群级部署)  |
| **重启影响**        | 需重建 RocksDB 状态                          | 零状态,瞬间恢复                    |

**结论**:**Wasm Transforms ≠ Streams 替代品**,而是 **Connect/Streams 之外的第三条路**,专门做"消息级实时转换",把 Kafka Connect 的 SMT 单条转换能力搬到内核里,延迟降到亚毫秒级。复杂流处理仍需 Streams/Flink,CDC 仍需 Debezium。

---

## 十六、核心要点速记

- **RedPanda Schema Registry = Confluent 协议 100% 兼容 + 内置在 Broker**;零独立进程,零额外 JVM,直接复用 Broker 的 Raft 共识持久化,毫秒级注册/查询延迟。
- **启用方式**:`redpanda.yaml` 中 `schema_registry.enabled: true` + `port: 8081`,或 `rpk cluster config set schema_registry.enabled true`,生产环境务必配 `advertised_listeners` 让外部客户端可达。
- **三大格式**:Avro (大数据/CDC 首选)、Protobuf (跨语言/gRPC 首选)、JSON Schema (前端/配置首选);所有格式共享同一 REST API,通过 `schemaType` 字段区分。
- **REST API 核心路径**:`POST /subjects/{subject}/versions`(注册)、`GET /subjects/{subject}/versions`(列表)、`GET /schemas/ids/{id}`(按 ID 查)、`POST /compatibility/subjects/.../versions`(兼容性 dry-run)、`PUT /config`(设置全局/单 subject 兼容性级别)。
- **消息格式**:`[magic byte = 0][schema id = 4 字节大端][编码后 payload]`;生产者在 header 自动塞 schema id,消费者用 id 拉 schema 反序列化,**零业务侵入**。
- **客户端零修改**:Java 用 `KafkaAvroSerializer` + `kafka-schema-registry-client`;Go 用 `confluent-kafka-go`;Python 用 `confluent-kafka-python`;**所有主流客户端指向 RedPanda SR 地址即用**,无需任何适配层。
- **兼容性级别**:默认 BACKWARD(新 Schema 能读旧数据);BACKWARD 安全变更 = 加带默认值字段 / 删带默认值字段 / 改默认值;**破坏性变更** = 删无默认字段 / 改类型 / 重命名(需用 aliases);FULL = 双向兼容,适合严格治理;NONE = 仅开发环境。
- **演进铁律**:**永远只加可选字段、永远不删必填字段、新增字段必有默认值、类型变更要谨慎、union 顺序不能改**;跨大版本演进时用 union 多版本共存 + 6 个月新老 Consumer 并行期。
- **Wasm Transforms = RedPanda 杀手锏**:**在 Broker 进程内执行 WebAssembly 函数**,单条消息级实时转换,亚毫秒延迟,百万级/秒吞吐,无独立 Worker 集群,无状态。
- **处理流程**:Producer → Broker 内 Wasm 引擎 (Wasmtime 沙箱) → 转换 → 写入目标 topic;函数签名固定为 `fn on_record(record) -> Result<Option<Record>>`,返回 `None` 即丢弃。
- **支持语言**:**Rust 首选**(官方 SDK)、TinyGo(Go 风格)、AssemblyScript(JS 风格);**Cargo.toml 必须 `crate-type = ["cdylib"]`**,profile 用 `opt-level = "z"` + `lto = true` 控制体积。
- **典型场景**:数据脱敏 (信用卡/身份证遮罩)、字段映射 (camelCase → snake_case)、协议转换 (JSON → Avro)、数据增强 (补时间戳/IP)、敏感词过滤、MQTT/Protobuf/JSON 互转。
- **部署方式**:`rpk transform deploy --binary xxx.wasm --name xxx --output-topic xxx`;查看/启停/删除:`rpk transform list / describe / enable / disable / delete`;**与 broker 同生共死,无外部依赖**。
- **性能基线**:1KB 消息简单 map ~50μs、JSON 解析 + 脱敏 ~500μs、JSON → Avro ~1ms;**单 transform 实例 10~50MB 内存,几乎不占 CPU**(复用 Broker);百万级消息/秒不是瓶颈。
- **Wasm vs Connect**:Connect 是**独立 Worker 集群**做 ETL (异构数据库集成首选),Wasm 是**Broker 内沙箱**做单条消息转换;**Wasm 不能做 CDC、不能写 ES/S3**,但**延迟低两个数量级,运维成本低一个数量级**。
- **Wasm vs Streams**:Streams 是**有状态 Java 进程**做 join/window/aggregate(复杂流处理),Wasm 是**无状态 Wasm 函数**做单条消息转换;**两者互补,不互相替代**;复杂流处理仍需 Streams/Flink。
- **监控**:Prometheus 指标 `wasm_transform_records_processed_total` / `_processing_latency_seconds_bucket` / `_errors_total`;通过 `rpk transform describe <name>` 看运行状态与处理计数。
- **生产配置铁律**:`schema_registry.advertised_listeners` 必须配外部地址;SR 与 Kafka API 同启认证;每桶一个 input/output topic,**避免循环**(input = output 会死循环);批量消息场景优先用 batch 接口减少 Wasm 调用开销。
- **RedPanda 哲学**:**用一个 C++ 二进制 + Raft 协议替代 ZooKeeper + Kafka + Schema Registry + Connect + Streams 的整套 Java 栈**;**Schema Registry 与 Wasm Transforms 是这一哲学的两大支柱**——前者解决"契约与演进",后者解决"实时转换",共同让 RedPanda 成为边缘 + 云端都能跑的**轻量级流数据平台**。