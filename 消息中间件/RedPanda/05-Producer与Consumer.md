# RedPanda Producer 与 Consumer

## 一、Producer / Consumer 概述

### 1.1 为什么 RedPanda 的客户端写法跟 Kafka 几乎一样

RedPanda 在协议层实现了 **Kafka API(REST/HTTP 之外的二进制协议 Kafka Wire Protocol)完全兼容**,因此任何 Kafka 客户端 SDK —— 不论是 `kafka-clients`、`kafka-python`、`librdkafka`、`sarama`,甚至 `spring-kafka` —— 都可以直接指向 RedPanda 集群,无需任何代码改造。

> RedPanda 官方明确承诺:**"100% Kafka API compatible"**。这意味着 RedPanda 不是"另一套消息中间件",而是一个**协议兼容、底层用 C++ 重写**(基于 Seastar 异步框架)的 Kafka 替代实现。

客户端视角的对比:

| 维度              | Kafka                                     | RedPanda                                |
|-------------------|-------------------------------------------|-----------------------------------------|
| Wire Protocol     | Kafka Protocol (KIP-0)                    | **完全相同**                             |
| Java 客户端       | `org.apache.kafka:kafka-clients`          | 同款 JAR,直接可用                        |
| Spring 集成       | `spring-kafka`                           | 同款 Starter,改 `bootstrap-servers` 即可 |
| C/C++             | `librdkafka`                              | 同款,推荐使用                            |
| Python            | `kafka-python` / `confluent-kafka-python` | 同款,推荐 `confluent-kafka-python`      |
| Go                | `sarama` / `confluent-kafka-go`           | 同款                                    |
| Schema Registry   | Confluent SR 或 Karapace                  | 内置 Schema Registry(亦兼容 Confluent SR) |

### 1.2 RedPanda 在客户端视角相对 Kafka 的"额外能力"

虽然 API 一致,但 RedPanda 在客户端可以使用的"附加特性"包括:

- **内置 Schema Registry**:无需额外部署 Confluent Schema Registry,RedPanda 自带,且 REST 接口与 Confluent SR 兼容。
- **WASM 转换**(Transform):可以在 Broker 端对消息进行 WASM 函数变换,客户端只需正常生产/消费即可享受。
- **Iceberg Topic**:将 Kafka Topic 直接映射成 Iceberg 表,客户端不需要关心存储。
- **Tiered Storage**(云端 S3 分层存储):客户端无需任何改动,即可享受无限历史回放。
- **更激进的默认压缩策略**(zstd 优先)。

### 1.3 客户端在 RedPanda 中的角色

```text
┌─────────────────────────────────────────────────────────────────────┐
│                        RedPanda 客户端全景                           │
│                                                                     │
│   ┌────────────────┐  send()/produce()   ┌────────────────────────┐ │
│   │   业务线程       │ ──────────────────►│   Producer             │         │
│   │                 │                    │  (KafkaProducer/       │         │
│   │                 │                    │   confluent_kafka…)    │         │
│   └────────────────┘                    └──────────┬─────────────┘         │
│                                                     │                    │
│                                  ┌──────────────────┼──────────────┐      │
│                                  ▼                  ▼              ▼      │
│                          ┌─────────────┐    ┌─────────────┐  ┌────────┐    │
│                          │ Serializer  │    │ Partitioner │  │ Compre-│    │
│                          │             │    │             │  │ ssion  │    │
│                          └─────────────┘    └─────────────┘  └────────┘    │
│                                                     │                    │
│                                                     ▼                    │
│                                           ┌──────────────────┐           │
│                                           │   批量/累加器      │           │
│                                           └─────────┬────────┘           │
│                                                     │                    │
│                                                     ▼                    │
│                  ┌──────────────────────────────────────────────┐         │
│                  │     Kafka Wire Protocol (TCP,9092/9093/TLS)   │         │
│                  └──────────────────────────────────────────────┘         │
│                                                     │                    │
└─────────────────────────────────────────────────────┼────────────────────┘
                                                      ▼
                                  ┌───────────────────────────────┐
                                  │      RedPanda 集群(Seastar)    │
                                  │   Topic-N → Partition 0..M    │
                                  │   Raft 共识 + 分区日志         │
                                  └───────────────────────────────┘
```

---

## 二、使用 Java Kafka 客户端

### 2.1 原生 `kafka-clients` 集成

#### 2.1.1 Maven 依赖

```xml
<dependency>
    <groupId>org.apache.kafka</groupId>
    <artifactId>kafka-clients</artifactId>
    <version>3.6.1</version>
</dependency>
```

> RedPanda 与 Kafka 客户端 0.10.x 起的所有版本兼容,但建议使用 **3.0+** 以获得最新的事务、幂等改进。

#### 2.1.2 Producer 完整代码

```java
import org.apache.kafka.clients.producer.*;
import org.apache.kafka.common.serialization.StringSerializer;

import java.util.Properties;
import java.util.concurrent.Future;

public class RedPandaProducerExample {

    public static void main(String[] args) throws Exception {
        Properties props = new Properties();

        // RedPanda bootstrap — 注意 RedPanda 默认 PLAINTEXT 监听 9092
        props.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG,
                "redpanda-1:9092,redpanda-2:9092,redpanda-3:9092");
        props.put(ProducerConfig.CLIENT_ID_CONFIG, "order-producer-001");

        props.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class);
        props.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, StringSerializer.class);

        // 可靠性:RedPanda 推荐 acks=all
        props.put(ProducerConfig.ACKS_CONFIG, "all");
        props.put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG, true);
        props.put(ProducerConfig.RETRIES_CONFIG, Integer.MAX_VALUE);
        props.put(ProducerConfig.MAX_IN_FLIGHT_REQUESTS_PER_CONNECTION, 5);

        // 吞吐优化
        props.put(ProducerConfig.BATCH_SIZE_CONFIG, 32 * 1024);
        props.put(ProducerConfig.LINGER_MS_CONFIG, 10);
        props.put(ProducerConfig.COMPRESSION_TYPE_CONFIG, "zstd");   // RedPanda 偏好
        props.put(ProducerConfig.BUFFER_MEMORY_CONFIG, 64L * 1024 * 1024);

        try (KafkaProducer<String, String> producer = new KafkaProducer<>(props)) {

            for (int i = 0; i < 1000; i++) {
                ProducerRecord<String, String> record = new ProducerRecord<>(
                        "order-topic",
                        "order-" + i,                                 // Key
                        "{\"id\":" + i + ",\"amount\":99.99}");       // Value

                Future<RecordMetadata> future = producer.send(record, (metadata, ex) -> {
                    if (ex != null) {
                        System.err.printf("发送失败: key=%s, err=%s%n",
                                record.key(), ex.getMessage());
                    } else {
                        System.out.printf("发送成功: topic=%s, partition=%d, offset=%d%n",
                                metadata.topic(), metadata.partition(), metadata.offset());
                    }
                });
            }

            producer.flush();
            producer.close();
        }
    }
}
```

#### 2.1.3 Consumer 完整代码

```java
import org.apache.kafka.clients.consumer.*;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.apache.kafka.common.TopicPartition;

import java.time.Duration;
import java.util.*;

public class RedPandaConsumerExample {

    public static void main(String[] args) {
        Properties props = new Properties();
        props.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG,
                "redpanda-1:9092,redpanda-2:9092,redpanda-3:9092");
        props.put(ConsumerConfig.GROUP_ID_CONFIG, "order-consumer-group");
        props.put(ConsumerConfig.CLIENT_ID_CONFIG, "order-consumer-001");

        props.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class);
        props.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class);

        // 消费语义
        props.put(ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG, false);            // 手动提交
        props.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "earliest");
        props.put(ConsumerConfig.ISOLATION_LEVEL_CONFIG, "read_committed");    // 仅消费已提交事务

        // 性能
        props.put(ConsumerConfig.FETCH_MIN_BYTES_CONFIG, 1024);
        props.put(ConsumerConfig.FETCH_MAX_WAIT_MS_CONFIG, 500);
        props.put(ConsumerConfig.MAX_POLL_RECORDS_CONFIG, 500);
        props.put(ConsumerConfig.MAX_PARTITION_FETCH_BYTES_CONFIG, 1024 * 1024);

        try (KafkaConsumer<String, String> consumer = new KafkaConsumer<>(props)) {
            consumer.subscribe(Collections.singletonList("order-topic"));

            while (true) {
                ConsumerRecords<String, String> records =
                        consumer.poll(Duration.ofMillis(500));
                for (ConsumerRecord<String, String> r : records) {
                    System.out.printf("offset=%d, key=%s, value=%s%n",
                            r.offset(), r.key(), r.value());
                    // 业务处理 …
                }
                consumer.commitSync();   // 处理完再提交
            }
        }
    }
}
```

#### 2.1.4 事务型 Producer

```java
public class TxProducerExample {
    public static void main(String[] args) {
        Properties props = new Properties();
        props.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, "redpanda-1:9092");
        props.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class);
        props.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, StringSerializer.class);
        props.put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG, true);
        props.put(ProducerConfig.TRANSACTIONAL_ID_CONFIG, "order-tx-producer");
        props.put(ProducerConfig.ACKS_CONFIG, "all");

        try (KafkaProducer<String, String> producer = new KafkaProducer<>(props)) {
            producer.initTransactions();
            try {
                producer.beginTransaction();
                producer.send(new ProducerRecord<>("order", "k1", "create"));
                producer.send(new ProducerRecord<>("audit", "k1", "log-create"));
                producer.send(new ProducerRecord<>("stock", "k1", "dec-stock"));
                producer.commitTransaction();
            } catch (Exception e) {
                producer.abortTransaction();
            }
        }
    }
}
```

> RedPanda 的事务模型与 Kafka 保持一致:`(transactional.id, producer.id, epoch)` 在 Broker 端做去重控制,Consumer 配 `read_committed` 仅读取已提交事务。

---

### 2.2 `spring-kafka` 集成(Spring Boot)

#### 2.2.1 Maven 依赖

```xml
<dependency>
    <groupId>org.springframework.kafka</groupId>
    <artifactId>spring-kafka</artifactId>
    <version>3.1.0</version>
</dependency>
```

#### 2.2.2 application.yml

```yaml
spring:
  kafka:
    bootstrap-servers: redpanda-1:9092,redpanda-2:9092,redpanda-3:9092

    producer:
      acks: all
      retries: 2147483647
      enable-idempotence: true
      batch-size: 32768
      linger-ms: 10
      compression-type: zstd            # RedPanda 偏好 zstd
      buffer-memory: 67108864           # 64MB
      max-in-flight-requests-per-connection: 5
      key-serializer: org.apache.kafka.common.serialization.StringSerializer
      value-serializer: org.apache.kafka.common.serialization.StringSerializer
      transaction-id-prefix: "order-tx-"   # 开启事务支持

    consumer:
      group-id: order-consumer-group
      enable-auto-commit: false
      auto-offset-reset: earliest
      isolation-level: read_committed
      fetch-min-bytes: 1024
      fetch-max-wait: 500
      max-poll-records: 500
      max-partition-fetch-bytes: 1048576
      key-deserializer: org.apache.kafka.common.serialization.StringDeserializer
      value-deserializer: org.apache.kafka.common.serialization.StringDeserializer

    listener:
      ack-mode: manual_immediate
      concurrency: 3                    # 与分区数匹配
      type: single

    properties:
      # 客户端连通性
      reconnect.backup: 1000
      reconnect.backup: 60000
      # 压缩协商:让客户端告诉 broker 支持的压缩算法
      compression: zstd
```

#### 2.2.3 Producer 服务

```java
@Service
@Slf4j
public class OrderProducer {

    @Autowired
    private KafkaTemplate<String, String> kafkaTemplate;

    /**
     * 异步发送
     */
    public void sendAsync(Order order) {
        String value = JSON.toJsonString(order);
        CompletableFuture<SendResult<String, String>> future =
                kafkaTemplate.send("order-topic", order.getId(), value);
        future.whenComplete((r, ex) -> {
            if (ex == null) {
                log.info("发送成功 offset={}", r.getRecordMetadata().offset());
            } else {
                log.error("发送失败", ex);
            }
        });
    }

    /**
     * 事务发送
     */
    public void sendInTx(Order order, AuditLog log) {
        kafkaTemplate.executeInTransaction(template -> {
            template.send("order-topic", order.getId(), JSON.toJsonString(order));
            template.send("audit-topic", log.getBizId(), JSON.toJsonString(log));
            return Boolean.TRUE;
        });
    }
}
```

#### 2.2.4 Consumer 服务

```java
@Service
@Slf4j
public class OrderConsumer {

    @KafkaListener(topics = "order-topic", groupId = "order-consumer-group")
    public void onMessage(ConsumerRecord<String, String> record,
                          Acknowledgment ack) {
        try {
            log.info("接收到消息 offset={}, key={}", record.offset(), record.key());
            // 业务处理 …
            ack.acknowledge();   // 手动提交
        } catch (Exception e) {
            log.error("处理失败", e);
            // 不 ack,下次 poll 仍会拿到同一条消息
        }
    }
}
```

#### 2.2.5 批量消费监听器

```java
@KafkaListener(topics = "order-topic",
               groupId = "batch-order-consumer",
               containerFactory = "batchFactory")
public void onBatch(List<Order> orders, Acknowledgment ack) {
    log.info("批量消费 {} 条", orders.size());
    orders.forEach(o -> processOne(o));
    ack.acknowledge();
}

// 配置 batchFactory
@Bean
public ConcurrentKafkaListenerContainerFactory<String, String> batchFactory(
        ConsumerFactory<String, String> cf) {
    ConcurrentKafkaListenerContainerFactory<String, String> f =
            new ConcurrentKafkaListenerContainerFactory<>();
    f.setConsumerFactory(cf);
    f.setBatchListener(true);
    f.getContainerProperties().setAckMode(ContainerProperties.AckMode.MANUAL_IMMEDIATE);
    return f;
}
```

#### 2.2.6 Spring Boot 测试(用 `spring-kafka-test` + RedPanda TestContainer)

```java
@SpringBootTest
@Testcontainers
class OrderProducerIT {

    @Container
    static GenericContainer<?> redpanda = new GenericContainer<>("redpandadata/redpanda:latest")
            .withCommand(
                "redpanda", "start",
                "--overprovisioned", "--smp", "1", "--memory", "1G",
                "--reserve-memory", "0M",
                "--node-id", "0",
                "--check=false",
                "--kafka-addr", "PLAINTEXT://0.0.0.0:9092",
                "--advertise-kafka-addr", "PLAINTEXT://localhost:9092")
            .withExposedPorts(9092);

    @DynamicPropertySource
    static void props(DynamicPropertyRegistry r) {
        r.add("spring.kafka.bootstrap-servers",
              () -> "localhost:" + redpanda.getMappedPort(9092));
    }

    @Autowired KafkaTemplate<String, String> template;

    @Test
    void shouldSendAndReceive() throws Exception {
        template.send("test-topic", "k1", "v1").get(5, TimeUnit.SECONDS);
        // 用 test-consumer-helper 验证 …
    }
}
```

---

## 三、使用 `librdkafka`(C/C++)

### 3.1 为什么推荐 `librdkafka`

`librdkafka` 是 Confluent 维护的高性能 C 库,Redpanda 官方文档明确推荐在 C/C++ 场景使用它。它的特性:

- **完全异步**、零拷贝、零阻塞。
- **跨平台**(Linux/macOS/Windows)。
- 内置 SASL/SSL/OAuthbearer 认证。
- 提供 C++ 包装 `rdkafkacpp.h`。

### 3.1.1 安装

```bash
# Ubuntu
apt-get install librdkafka-dev

# macOS
brew install librdkafka

# CentOS
yum install librdkafka-devel
```

### 3.2 Producer(C++)

```cpp
#include <librdkafka/rdkafkacpp.h>
#include <iostream>
#include <memory>

class DeliveryReportCb : public RdKafka::DeliveryReportCb {
    public:
        void dr_cb(RdKafka::Message& m) override {
            if (m.err())
                std::cerr << "发送失败: " << m.errstr() << std::endl;
            else
                std::cout << "发送成功: topic=" << m.topic_name()
                          << " partition=" << m.partition()
                          << " offset="  << m.offset() << std::endl;
        }
};

int main() {
    std::string err;
    std::unique_ptr<RdKafka::Conf> conf(
        RdKafka::Conf::create(RdKafka::Conf::CONF_GLOBAL));

    conf->set("bootstrap.servers", "redpanda-1:9092,redpanda-2:9092", err);
    conf->set("client.id", "cpp-producer-001", err);

    // 可靠性
    conf->set("acks", "all", err);
    conf->set("enable.idempotence", "true", err);
    conf->set("compression.type", "zstd", err);

    // 吞吐
    conf->set("batch.size", "32768", err);
    conf->set("linger.ms", "10", err);

    DeliveryReportCb dr;
    conf->set("dr_cb", &dr, err);

    auto producer = std::unique_ptr<RdKafka::Producer>(
        RdKafka::Producer::create(conf.get(), err));
    if (!producer) { std::cerr << err << std::endl; return 1; }

    for (int i = 0; i < 1000; ++i) {
        std::string key = "order-" + std::to_string(i);
        std::string val = R"({"id":)" + std::to_string(i) + R"(,"amount":99.99})";

        RdKafka::ErrorCode rc = producer->produce(
            "order-topic",
            RdKafka::Topic::PARTITION_UA,
            RdKafka::Producer::RK_MSG_COPY,
            const_cast<char*>(val.data()), val.size(),
            key.data(), key.size(),
            0, nullptr, nullptr);

        if (rc != RdKafka::ERR_NO_ERROR)
            std::cerr << "produce 失败: " << RdKafka::err2str(rc) << std::endl;

        producer->poll(0);   // 触发回调
    }

    producer->flush(5000);   // 等待所有消息发出
    return 0;
}
```

### 3.3 Consumer(C++)

```cpp
#include <librdkafka/rdkafkacpp.h>
#include <iostream>
#include <memory>
#include <string>

int main() {
    std::string err;
    std::unique_ptr<RdKafka::Conf> conf(
        RdKafka::Conf::create(RdKafka::Conf::CONF_GLOBAL));

    conf->set("bootstrap.servers", "redpanda-1:9092", err);
    conf->set("group.id", "order-consumer-group", err);
    conf->set("enable.auto.commit", "false", err);
    conf->set("auto.offset.reset", "earliest", err);

    auto consumer = std::unique_ptr<RdKafka::KafkaConsumer>(
        RdKafka::KafkaConsumer::create(conf.get(), err));
    if (!consumer) { std::cerr << err << std::endl; return 1; }

    consumer->subscribe({ "order-topic" });

    while (true) {
        std::unique_ptr<RdKafka::Message> msg(consumer->consume(1000));
        switch (msg->err()) {
            case RdKafka::ERR_NO_ERROR: {
                std::cout << "offset=" << msg->offset()
                          << " key="  << *msg->key()
                          << " val="  << static_cast<const char*>(msg->payload())
                          << std::endl;
                // 业务处理 …
                consumer->commitSync(msg.get());
                break;
            }
            case RdKafka::ERR__TIMED_OUT:
            case RdKafka::ERR__PARTITION_EOF:
                break;
            default:
                std::cerr << "consume 失败: " << msg->errstr() << std::endl;
        }
    }

    consumer->close();
    return 0;
}
```

### 3.4 C 库版本(纯 C)

```c
#include <librdkafka/rdkafka.h>
#include <stdio.h>
#include <string.h>

static void dr_cb(rd_kafka_t *rk, const rd_kafka_message_t *rkmessage, void *opaque) {
    if (rkmessage->err)
        fprintf(stderr, "%% 发送失败: %s\n", rd_kafka_err2str(rkmessage->err));
    else
        fprintf(stdout, "%% 发送成功: partition=%d offset=%ld\n",
                (int)rkmessage->partition, (long)rkmessage->offset);
}

int main() {
    char errstr[512];
    rd_kafka_conf_t *conf = rd_kafka_conf_new();

    rd_kafka_conf_set(conf, "bootstrap.servers", "redpanda-1:9092", errstr, sizeof(errstr));
    rd_kafka_conf_set(conf, "acks", "all", errstr, sizeof(errstr));
    rd_kafka_conf_set(conf, "enable.idempotence", "true", errstr, sizeof(errstr));
    rd_kafka_conf_set(conf, "compression.type", "zstd", errstr, sizeof(errstr));
    rd_kafka_conf_set(conf, "dr_cb", dr_cb, errstr, sizeof(errstr));

    rd_kafka_t *rk = rd_kafka_new(RD_KAFKA_PRODUCER, conf, errstr, sizeof(errstr));
    if (!rk) { fprintf(stderr, "%% %s\n", errstr); return 1; }

    for (int i = 0; i < 1000; ++i) {
        char key[32], val[128];
        snprintf(key, sizeof(key), "order-%d", i);
        snprintf(val, sizeof(val), "{\"id\":%d}", i);
        rd_kafka_producev(rk,
            RD_KAFKA_V_TOPIC("order-topic"),
            RD_KAFKA_V_VALUE(val, strlen(val)),
            RD_KAFKA_V_KEY(key, strlen(key)),
            RD_KAFKA_V_END);
        rd_kafka_poll(rk, 0);
    }

    rd_kafka_flush(rk, 5000);
    rd_kafka_destroy(rk);
    return 0;
}
```

---

## 四、使用 Python 客户端

### 4.1 `confluent-kafka-python`(推荐)

> 基于 `librdkafka` 的官方 Python 绑定,性能与 C/C++ 客户端一致,**生产首选**。

#### 4.1.1 安装

```bash
pip install confluent-kafka
```

#### 4.1.2 Producer

```python
from confluent_kafka import Producer
import time

conf = {
    'bootstrap.servers': 'redpanda-1:9092,redpanda-2:9092',
    'client.id': 'py-producer-001',

    # 可靠性
    'acks': 'all',
    'enable.idempotence': True,
    'compression.type': 'zstd',
    'max.in.flight.requests.per.connection': 5,

    # 吞吐
    'linger.ms': 10,
    'batch.size': 32768,
    'queue.buffering.max.kbytes': 65536,    # 64MB

    # 重试
    'retries': 2147483647,
    'retry.backoff.ms': 200,
}

def delivery_report(err, msg):
    if err is not None:
        print(f'发送失败: key={msg.key()} err={err}')
    else:
        print(f'发送成功: topic={msg.topic()} partition={msg.partition()} offset={msg.offset()}')

producer = Producer(conf)
for i in range(1000):
    producer.produce(
        topic='order-topic',
        key=f'order-{i}',
        value=f'{{"id":{i},"amount":99.99}}'.encode('utf-8'),
        callback=delivery_report,
    )
    producer.poll(0)   # 触发回调

producer.flush(30)     # 等待所有消息发出
```

#### 4.1.3 Consumer

```python
from confluent_kafka import Consumer, KafkaError, KafkaException
import time

conf = {
    'bootstrap.servers': 'redpanda-1:9092',
    'group.id': 'order-consumer-group',
    'client.id': 'py-consumer-001',
    'auto.offset.reset': 'earliest',
    'enable.auto.commit': False,
    'isolation.level': 'read_committed',

    # 吞吐
    'fetch.min.bytes': 1024,
    'fetch.wait.max.mjs': 500,
    'max.partition.fetch.bytes': 1048576,

    # 分区分配策略
    'partition.assignment.strategy': 'cooperative-sticky',
}

consumer = Consumer(conf)
consumer.subscribe(['order-topic'])

try:
    while True:
        msg = consumer.poll(timeout=1.0)
        if msg is None: continue
        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                continue
            else:
                raise KafkaException(msg.error())
        # 业务处理
        print(f'offset={msg.offset()} key={msg.key().decode()} '
              f'value={msg.value().decode()}')
        consumer.commit(msg, asynchronous=False)   # 同步提交
except KeyboardInterrupt:
    pass
finally:
    consumer.close()
```

#### 4.1.4 Avro + 内置 Schema Registry

```python
from confluent_kafka import Producer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer

sr_conf = {'url': 'http://redpanda:8081'}
sr = SchemaRegistryClient(sr_conf)

value_schema = """
{
  "type": "record",
  "name": "Order",
  "fields": [
    {"name": "id", "type": "string"},
    {"name": "amount", "type": "double"}
  ]
}
"""
avro_ser = AvroSerializer(sr, value_schema)

producer_conf = {
    'bootstrap.servers': 'redpanda-1:9092',
    'acks': 'all',
    'enable.idempotence': True,
    'compression.type': 'zstd',
}
producer = Producer(producer_conf)

producer.produce(
    topic='order-avro-topic',
    key='k1',
    value=avro_ser({'id': 'order-001', 'amount': 99.99}, ctx=None),
)
producer.flush(10)
```

### 4.2 `kafka-python`(纯 Python 实现)

> 不依赖 `librdkafka`,纯 Python,适合调试或轻量场景。性能比 `confluent-kafka` 差一个数量级。

```python
from kafka import KafkaProducer, KafkaConsumer
import json

producer = KafkaProducer(
    bootstrap_servers='redpanda-1:9092',
    acks='all',
    enable_idempotence=True,
    compression_type='zstd',
    linger_ms=10,
    batch_size=32 * 1024,
    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
    key_serializer=lambda k: k.encode('utf-8') if k else None,
)

future = producer.send('order-topic', key='order-1', value={'id': 1, 'amount': 99.99})
metadata = future.get(timeout=10)
print(f'offset={metadata.offset}')

consumer = KafkaConsumer(
    'order-topic',
    bootstrap_servers='redpanda-1:9092',
    group_id='py-consumer-group',
    enable_auto_commit=False,
    auto_offset_reset='earliest',
    isolation_level='read_committed',
    value_deserializer=lambda v: json.loads(v.decode('utf-8')),
)
for msg in consumer:
    print(msg.topic, msg.partition, msg.offset, msg.key, msg.value)
```

---

## 五、使用 Go 客户端

### 5.1 `sarama`(纯 Go,IBM/Spoolex 维护)

#### 5.1.1 安装

```bash
go get github.com/IBM/sarama
```

#### 5.1.2 Producer

```go
package main

import (
    "encoding/json"
    "fmt"
    "log"
    "github.com/IBM/sarama"
)

type Order struct {
    ID     string  `json:"id"`
    Amount float64 `json:"amount"`
}

func main() {
    cfg := sarama.NewConfig()
    cfg.Version = sarama.V3_6_0_0

    cfg.Producer.RequiredAcks = sarama.WaitForAll
    cfg.Producer.Idempotent = true
    cfg.Producer.Return.Successes = true
    cfg.Producer.Return.Errors = true
    cfg.Producer.Compression = sarama.CompressionZSTD
    cfg.Producer.Flutter.MaxMessages = 1000
    cfg.Net.MaxOpenRequests = 5
    cfg.Producer.Flush.Frequency = 10 * time.Millisecond

    brokers := []string{"redpanda-1:9092", "redpanda-2:9092"}
    producer, err := sarama.NewAsyncProducer(brokers, cfg)
    if err != nil { log.Fatal(err) }

    defer producer.Close()

    go func() {
        for {
            select {
            case s := <-producer.Successes():
                fmt.Printf("发送成功: partition=%d offset=%d\n",
                    s.Partition, s.Offset)
            case e := <-producer.Errors():
                fmt.Printf("发送失败: %v\n", e)
            }
        }
    }()

    for i := 0; i < 1000; i++ {
        order := Order{ID: fmt.Sprintf("order-%d", i), Amount: 99.99}
        b, _ := json.Marshal(order)
        msg := &sarama.ProducerMessage{
            Topic: "order-topic",
            Key:   sarama.StringEncoder(fmt.Sprintf("order-%d", i)),
            Value: sarama.ByteEncoder(b),
        }
        producer.Input() <- msg
    }
}
```

#### 5.1.3 Consumer

```go
package main

import (
    "fmt"
    "log"
    "github.com/IBM/sarama"
)

type ConsumerGroupHandler struct{}

func (h *ConsumerGroupHandler) Setup(_ sarama.ConsumerGroupSession) error   { return nil }
func (h *ConsumerGroupHandler) Cleanup(_ sarama.ConsumerGroupSession) error { return nil }
func (h *ConsumerGroupHandler) ConsumeClaim(
    session sarama.ConsumerGroupSession, claim sarama.ConsumerGroupClaim) error {
    for msg := range claim.Messages() {
        fmt.Printf("offset=%d key=%s value=%s\n",
            msg.Offset, string(msg.Key), string(msg.Value))
        session.MarkMessage(msg, "")
    }
    return nil
}

func main() {
    cfg := sarama.NewConfig()
    cfg.Version = sarama.V3_6_0_0
    cfg.Consumer.Offsets.Initial = sarama.OffsetOldest
    cfg.Consumer.Offsets.AutoCommit.Enable = false
    cfg.Consumer.IsolationLevel = sarama.ReadCommitted
    cfg.Consumer.Group.Rebalance.GroupStrategies =
        []sarama.BalanceStrategy{sarama.NewBalanceStrategyRange()}

    cg, err := sarama.NewConsumerGroup(
        []string{"redpanda-1:9092"}, "order-consumer-group", cfg)
    if err != nil { log.Fatal(err) }
    defer cg.Close()

    handler := ConsumerGroupHandler{}
    for {
        if err := cg.Consume(nil, []string{"order-topic"}, handler); err != nil {
            log.Fatal(err)
        }
    }
}
```

### 5.2 `confluent-kafka-go`(基于 librdkafka 的 cgo 绑定)

#### 5.2.1 安装

```bash
go get github.com/confluentinc/confluent-kafka-go/v2/kafka
```

#### 5.2.2 Producer

```go
package main

import (
    "fmt"
    "github.com/confluentinc/confluent-kafka-go/v2/kafka"
)

func main() {
    p, err := kafka.NewProducer(&kafka.ConfigMap{
        "bootstrap.servers":  "redpanda-1:9092",
        "acks":               "all",
        "enable.idempotence": true,
        "compression.type":   "zstd",
        "linger.ms":          10,
        "batch.size":         32768,
    })
    if err != nil { panic(err) }
    defer p.Close()

    deliveryChan := make(chan kafka.Event, 1000)
    for i := 0; i < 1000; i++ {
        key := fmt.Sprintf("order-%d", i)
        val := fmt.Sprintf(`{"id":%d,"amount":99.99}`, i)
        p.Produce(&kafka.Message{
            TopicPartition: kafka.TopicPartition{Topic: "order-topic", Partition: kafka.PartitionAny},
            Key:            []byte(key),
            Value:          []byte(val),
        }, deliveryChan)
    }

    for i := 0; i < 1000; i++ {
        ev := <-deliveryChan
        m := ev.(*kafka.Message)
        if m.TopicPartition.Error != nil {
            fmt.Printf("失败: %v\n", m.TopicPartition.Error)
        } else {
            fmt.Printf("成功: partition=%d offset=%v\n",
                m.TopicPartition.Partition, m.TopicPartition.Offset)
        }
    }
}
```

#### 5.2.3 Consumer

```go
package main

import (
    "fmt"
    "github.com/confluentinc/confluent-kafka-go/v2/kafka"
)

func main() {
    c, err := kafka.NewConsumer(&kafka.ConfigMap{
        "bootstrap.servers":  "redpanda-1:9092",
        "group.id":           "order-consumer-group",
        "auto.offset.reset":  "earliest",
        "enable.auto.commit": false,
        "isolation.level":    "read_committed",
    })
    if err != nil { panic(err) }
    defer c.Close()

    c.SubscribeTopics([]string{"order-topic"}, nil)
    for {
        msg, err := c.ReadMessage(-1)
        if err == nil {
            fmt.Printf("offset=%d key=%s value=%s\n",
                msg.TopicPartition.Offset, string(msg.Key), string(msg.Value))
        } else {
            fmt.Printf("err: %v\n", err)
        }
    }
}
```

---

## 六、与 Kafka 的差异(客户端视角)

RedPanda 在客户端 SDK 层面**几乎没有差异**,但有几个**高级特性**上的细微差别,值得注意:

| 特性                              | Kafka                                                | RedPanda                                              | 影响     |
|-----------------------------------|------------------------------------------------------|-------------------------------------------------------|----------|
| `min.insync.replicas`             | Topic 级别,必须显式设置                              | 默认 = 1,Topic 创建时若指定会被尊重                   | 客户端无感 |
| `unclean.leader.election.enable`  | 默认 `false`,可配置                                  | 默认 `false`                                           | 客户端无感 |
| `message.timestamp.type`         | CreateTime / LogAppendTime                            | 仅 CreateTime                                          | 客户端无感 |
| `__consumer_offsets` 压缩          | 默认 lz4                                              | 默认 zstd                                              | 客户端无感 |
| Idempotent Producer               | 完全支持                                              | **完全支持**(官方测试覆盖)                              | 无差异   |
| Transactional Producer            | 完全支持(KIP-98)                                    | **完全支持**(从 v22.x 起)                              | 无差异   |
| `transaction.state.log.replication.factor` | 默认 3                                      | 默认 = 集群节点数                                       | 客户端无感 |
| Exactly-Once Semantics            | 通过事务 + `read_committed`                          | 通过事务 + `read_committed`(同等语义)                  | 无差异   |
| Schema Registry                   | 需额外部署 Confluent SR / Karapace                  | **内置**,API 兼容 Confluent SR                       | 客户端可指向内置 SR |
| Consumer Group Rebalance 协议     | Eager / Cooperative(2.4+)                            | Cooperative(默认)+ Range/Sticky                       | 客户端无感 |
| KRaft vs ZooKeeper               | KRaft(KIP-500)                                       | 原生 KRaft                                             | 客户端无感 |
| 消息压缩算法                       | none/gzip/snappy/lz4/zstd                            | **none/gzip/snappy/lz4/zstd**(全支持)                 | 无差异   |

**总结**:客户端**几乎不需要修改任何代码**,只要把 `bootstrap.servers` 从 Kafka broker 切到 RedPanda broker 即可。

---

## 七、性能优化配置(客户端侧)

### 7.1 Producer 关键参数

| 参数                                 | Kafka 默认         | RedPanda 推荐              | 说明                                 |
|--------------------------------------|--------------------|----------------------------|--------------------------------------|
| `acks`                               | 1                  | **all**                    | RedPanda 推荐严格一致性               |
| `enable.idempotence`                 | false              | **true**                   | 开启幂等,防单分区重复                 |
| `compression.type`                   | none               | **zstd**                   | RedPanda 默认偏好 zstd               |
| `batch.size`                         | 16384(16 KB)       | 32768~131072               | 大批次提高吞吐                         |
| `linger.ms`                          | 0                  | 10~100                     | 增加延迟换吞吐                         |
| `buffer.memory`                      | 33554432(32 MB)    | 64~256 MB                  | 抗突发                |
| `max.in.flight.requests.per.connection` | 5               | 5                          | 配合幂等使用                |
| `retries`                            | 2147483647         | 2147483647                 | 配合幂等使用                |
| `delivery.timeout.ms`                | 120000             | 120000                     | 发送最长时间                |
| `request.timeout.ms`                 | 30000              | 30000                      | 单次请求超时                |
| `compression.level`                  | -                  | 3(默认)                    | zstd 压缩级别                |
| `partitioner.class`                   | DefaultPartitioner | 默认                       | 大多数场景够用                |

### 7.2 Consumer 关键参数

| 参数                                   | 默认                | 推荐值                      | 说明                |
|----------------------------------------|---------------------|-----------------------------|---------------------|
| `fetch.min.bytes`                      | 1                   | 1024~65536                  | 减少请求数          |
| `fetch.max.wait.ms`                    | 500                 | 100~500                     | 最大等待时间        |
| `max.partition.fetch.bytes`            | 1048576(1 MB)      | 1~10 MB                     | 单分区最大拉取      |
| `max.poll.records`                     | 500                 | 500~2000                    | 单次 poll 消息数    |
| `max.poll.interval.ms`                 | 300000              | 300000~600000               | 处理超时阈值        |
| `session.timeout.ms`                   | 45000               | 10000~30000                 | 心跳超时            |
| `heartbeat.interval.ms`                | 3000                | 1000~3000                   | 心跳频率            |
| `auto.offset.reset`                    | latest              | earliest(首次)/latest       | 位移重置策略        |
| `enable.auto.commit`                   | true                | **false**                   | 推荐手动提交        |
| `isolation.level`                      | read_uncommitted    | **read_committed**          | 配合事务使用        |
| `partition.assignment.strategy`        | Range+Cooperative   | **CooperativeSticky**       | 增量再平衡          |
| `client.rack`                          | 无                  | `region-a`                  | Rack 亲和(异构集群) |

### 7.3 场景化推荐模板

| 场景                | Producer 配置                                                                                                       | Consumer 配置                                                                                  |
|---------------------|---------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------|
| **日志采集**        | `acks=1`,`linger.ms=20`,`batch.size=64KB`,`compression=zstd`,**幂等可选**                                            | `fetch.min.bytes=64KB`,`max.poll.records=2000`,自动提交 OK                                       |
| **通用业务**        | `acks=all`,`linger.ms=10`,`batch.size=32KB`,`compression=zstd`,**幂等开**                                            | `enable.auto.commit=false`,手动提交,`read_committed`                                              |
| **金融 / 订单**     | `acks=all`,`linger.ms=5`,`batch.size=16KB`,`compression=zstd`,**幂等 + 事务必开**                                    | `isolation.level=read_committed`,**手动提交** + **业务幂等校验**                                  |
| **高吞吐聚合**      | `acks=1`,`linger.ms=100`,`batch.size=128KB`,`compression=zstd`,幂等可选                                                | `fetch.min.bytes=128KB`,`max.partition.fetch.bytes=10MB`                                         |
| **实时流(低延迟)**  | `acks=1`,`linger.ms=0`,`batch.size=16KB`,`compression=none`,幂等可选                                                  | `fetch.min.bytes=1`,`fetch.max.wait.ms=10`                                                       |
| **跨 IDC 灾备**     | `acks=all`,`compression=zstd`,**长连接 + 重试退避**                                                                  | `session.timeout.ms=60000`,`max.poll.interval.ms=600000`                                       |

### 7.4 监控与告警(客户端)

| 客户端指标(从客户端 Prometheus exporter 获取)        | 含义                          | 告警阈值示例                  |
|------------------------------------------------------|-------------------------------|-------------------------------|
| `producer_record_send_rate`                         | 每秒发送消息数                 | 异常下降                      |
| `producer_record_error_rate`                         | 发送失败速率                   | > 0                          |
| `producer_record_retry_rate`                         | 重试速率                       | 突增                          |
| `producer_record_queue_time_avg`                     | 累加器平均等待时间             | > 100ms                      |
| `producer_batch_size_avg`                            | 平均批次大小                   | 监控                          |
| `producer_request_latency_avg`                       | 请求平均延迟                   | > 业务容忍                    |
| `producer_buffer_available_bytes`                    | 累加器剩余字节                 | < 10%                         |
| `consumer_records_consumed_rate`                     | 消费速率                       | 与发送侧对比,应同步            |
| `consumer_fetch_latency_avg`                         | 拉取延迟                       | > 业务容忍                    |
| `consumer_coordinator_rebalance_rate`                | Rebalance 频率                 | 突增需关注                    |
| `consumer_lag`                                       | 各分区消费滞后                 | > 阈值触发告警                 |

> RedPanda 客户端的指标导出通常借助 `kafka_exporter`(JMX 走不通,因为 RedPanda 不暴露 JMX)、`prometheus-kafka-exporter`、`librdkafka_stats`(C/Python) 或 `sarama_metrics`(Go)。

---

## 八、Schema 与序列化

### 8.1 Avro + RedPanda 内置 Schema Registry

RedPanda 从 v22.3 起内置 **Schema Registry**,REST API 与 Confluent Schema Registry 完全兼容。

#### 8.1.1 启用 Schema Registry

```bash
rpk cluster config set enable_schema_registry true
```

默认监听 `http://<node>:8081`。

#### 8.1.2 注册 Schema

```bash
curl -X POST http://redpanda:8081/subjects/order-topic-value/versions \
  -H 'Content-Type: application/vnd.schemaregistry.v1+json' \
  -d '{"schema": "{\"type\":\"record\",\"name\":\"Order\",\"fields\":[{\"name\":\"id\",\"type\":\"string\"},{\"name\":\"amount\",\"type\":\"double\"}]}"}'
```

返回:

```json
{"id": 1}
```

#### 8.1.3 Producer 发送 Avro(Java)

```java
import io.confluent.kafka.serializers.KafkaAvroSerializer;
import io.confluent.kafka.serializers.AbstractKafkaSchemaRegistrySerDeConfig;

Properties props = new Properties();
props.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, "redpanda-1:9092");
props.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, KafkaAvroSerializer.class);
props.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, KafkaAvroSerializer.class);
props.put("schema.registry.url", "http://redpanda:8081");

KafkaProducer<String, GenericRecord> producer = new KafkaProducer<>(props);

String schema = """
    { "type": "record", "name": "Order",
      "fields": [ {"name":"id","type":"string"},
                  {"name":"amount","type":"double"} ] }
    """;
org.apache.avro.Schema.Parser parser = new org.apache.avro.Schema.Parser();
org.apache.avro.Schema avroSchema = parser.parse(schema);

GenericRecord order = new GenericData.Record(avroSchema);
order.put("id", "order-001");
order.put("amount", 99.99);

producer.send(new ProducerRecord<>("order-topic", "k1", order));
producer.flush();
```

#### 8.1.4 Consumer 读取 Avro(Java)

```java
Properties props = new Properties();
props.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, "redpanda-1:9092");
props.put(ConsumerConfig.GROUP_ID_CONFIG, "order-cg");
props.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class);
props.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, KafkaAvroDeserializer.class);
props.put("schema.registry.url", "http://redpanda:8081");

KafkaConsumer<String, GenericRecord> consumer = new KafkaConsumer<>(props);
consumer.subscribe(Collections.singletonList("order-topic"));
while (true) {
    ConsumerRecords<String, GenericRecord> records = consumer.poll(Duration.ofMillis(500));
    for (ConsumerRecord<String, GenericRecord> r : records) {
        GenericRecord v = r.value();
        System.out.printf("id=%s amount=%f%n", v.get("id"), v.get("amount"));
    }
}
```

### 8.2 Protobuf

RedPanda 不直接提供 Protobuf 序列化器,但 **Confluent 的 Protobuf Converter** 与 RedPanda 内置 SR 兼容。

```xml
<dependency>
    <groupId>io.confluent</groupId>
    <artifactId>kafka-protobuf-serializer</artifactId>
    <version>7.5.0</version>
</dependency>
```

```java
// 略,使用方式与 Avro 类似
```

### 8.3 JSON Schema

同理,使用 Confluent 的 `KafkaJSONSchemaSerializer`:

```xml
<dependency>
    <groupId>io.confluent</groupId>
    <artifactId>kafka-json-schema-serializer</artifactId>
    <version>7.5.0</version>
</dependency>
```

### 8.4 序列化方式对比

| 序列化方式      | 体积    | 性能 | Schema 演进 | 客户端复杂度 | RedPanda 支持 |
|-----------------|---------|------|-------------|--------------|---------------|
| **JSON**        | 大      | 中   | 弱(无强约束)| 低           | 完全兼容      |
| **Avro**        | 小      | 高   | 强          | 中(需 SR)  | **原生支持**  |
| **Protobuf**    | 小      | 高   | 强          | 中(需 SR)  | 兼容(用 Confluent SR) |
| **JSON Schema** | 中      | 中   | 强          | 中(需 SR)  | 兼容(用 Confluent SR) |
| **MessagePack** | 小      | 高   | 弱          | 低           | 完全兼容      |

---

## 九、事务消息

### 9.1 RedPanda 对事务的支持

RedPanda 在 v22.x 起完整实现了 **Kafka 事务协议(KIP-98)**:

- 支持 `initTransactions() / beginTransaction() / commitTransaction() / abortTransaction()` 全套 API。
- Consumer 通过 `isolation.level=read_committed` 只读取已提交事务。
- 通过 `__transaction_state` 内部 Topic 持久化事务状态。
- 支持 **跨 Topic、跨 Partition** 的原子写入。
- 与 Kafka 客户端 **API 完全兼容**。

### 9.2 事务配置

```properties
# Producer
enable.idempotence=true
transactional.id=order-tx-producer       # 必须唯一,用于故障恢复
acks=all
retries=2147483647
max.in.flight.requests.per.connection=5
transaction.timeout.ms=60000              # 默认 60s
```

### 9.3 Java 完整事务示例

```java
public class OrderTxService {

    private final KafkaProducer<String, String> producer;

    public OrderTxService() {
        Properties props = new Properties();
        props.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, "redpanda-1:9092");
        props.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class);
        props.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, StringSerializer.class);
        props.put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG, true);
        props.put(ProducerConfig.TRANSACTIONAL_ID_CONFIG, "order-tx-" + UUID.randomUUID());
        props.put(ProducerConfig.ACKS_CONFIG, "all");
        this.producer = new KafkaProducer<>(props);
        producer.initTransactions();
    }

    /**
     * 下单 + 扣库存 + 写日志,要么全成要么全失败
     */
    public void placeOrder(Order order) throws Exception {
        producer.beginTransaction();
        try {
            producer.send(new ProducerRecord<>(
                "order-topic", order.getId(),
                JSON.toJsonString(order)));
            producer.send(new ProducerRecord<>(
                "stock-topic", order.getSku(),
                String.format("{\"delta\":-1,\"orderId\":\"%s\"}", order.getId())));
            producer.send(new ProducerRecord<>(
                "audit-topic", order.getId(),
                JSON.toJsonString(new AuditLog("PLACE_ORDER", order))));

            producer.commitTransaction();
            log.info("事务提交成功: order={}", order.getId());
        } catch (Exception e) {
            producer.abortTransaction();
            log.error("事务回滚: order={}", order.getId(), e);
            throw e;
        }
    }

    public void close() { producer.close(); }
}
```

### 9.4 Consumer 读取事务消息

```properties
isolation.level=read_committed
enable.auto.commit=false
```

```java
KafkaConsumer<String, String> consumer = new KafkaConsumer<>(props);
consumer.subscribe(List.of("order-topic", "stock-topic"));
```

> **注意**:`read_committed` 下,事务被中止(`abortTransaction`)的消息对 Consumer **不可见**;事务未完成时的中间消息也 **不可见**。

### 9.5 事务与 Exactly-Once 语义

```text
┌──────────────┐
│   Producer    │ transactional.id = "order-tx"
│  幂等 PID     │  beginTransaction() → send()×N → commit/abort
└──────┬───────┘
       │
       ▼
┌────────────────────────────────────────┐
│  RedPanda: __transaction_state 内部 Topic │
│  记录事务状态 + 提交标记                     │
└──────┬─────────────────────────────────┘
       │
       ▼
┌──────────────┐                              ┌──────────────┐
│  Consumer A   │  isolation.level=read_committed │  仅读已提交事务  │
└──────────────┘                              └──────────────┘
```

---

## 十、实战代码示例

### 10.1 Spring Boot 完整应用(订单 + 库存)

#### 10.1.1 `pom.xml`

```xml
<dependencies>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-web</artifactId>
    </dependency>
    <dependency>
        <groupId>org.springframework.kafka</groupId>
        <artifactId>spring-kafka</artifactId>
    </dependency>
    <dependency>
        <groupId>io.confluent</groupId>
        <artifactId>kafka-avro-serializer</artifactId>
        <version>7.5.0</version>
        <exclusions>
            <exclusion>
                <groupId>org.apache.kafka</groupId>
                <artifactId>kafka-clients</artifactId>
            </exclusion>
        </exclusions>
    </dependency>
</dependencies>
```

#### 10.1.2 `application.yml`

```yaml
spring:
  kafka:
    bootstrap-servers: redpanda-1:9092,redpanda-2:9092,redpanda-3:9092

    producer:
      acks: all
      retries: 2147483647
      enable-idempotence: true
      compression-type: zstd
      batch-size: 32768
      linger-ms: 10
      buffer-memory: 67108864
      key-serializer: io.confluent.kafka.serializers.KafkaAvroSerializer
      value-serializer: io.confluent.kafka.serializers.KafkaAvroSerializer
      transaction-id-prefix: "order-tx-"

    consumer:
      group-id: order-app
      auto-offset-reset: earliest
      enable-auto-commit: false
      isolation-level: read_committed
      key-deserializer: io.confluent.kafka.serializers.KafkaAvroDeserializer
      value-deserializer: io.confluent.kafka.serializers.KafkaAvroDeserializer
      properties:
        schema.registry.url: http://redpanda:8081

    listener:
      ack-mode: manual_immediate

  application:
    name: order-app

schema:
  registry:
    url: http://redpanda:8081
```

#### 10.1.3 Avro Schema 文件(`src/main/avro/Order.avsc`)

```json
{
  "type": "record",
  "name": "Order",
  "namespace": "com.example.redpanda",
  "fields": [
    {"name": "id",     "type": "string"},
    {"name": "sku",    "type": "string"},
    {"name": "amount", "type": "double"},
    {"name": "ts",     "type": "long", "logicalType": "timestamp-millis"}
  ]
}
```

#### 10.1.4 Controller

```java
@RestController
@RequestMapping("/order")
@Slf4j
public class OrderController {

    @Autowired private OrderProducerService producer;

    @PostMapping
    public ResponseEntity<?> placeOrder(@RequestBody Order order) {
        producer.place(order);
        return ResponseEntity.ok(Map.of("status", "submitted", "id", order.getId()));
    }
}
```

#### 10.1.5 Service

```java
@Service
@Slf4j
public class OrderProducerService {

    @Autowired private KafkaTemplate<String, Order> kafkaTemplate;

    public void place(Order order) {
        kafkaTemplate.executeInTransaction(t -> {
            t.send("order-topic", order.getId(), order);
            t.send("stock-topic", order.getSku(),
                   StockDecrement.newBuilder()
                                .setOrderId(order.getId())
                                .setDelta(-1).build());
            t.send("audit-topic", order.getId(),
                   AuditLog.newBuilder()
                           .setAction("PLACE")
                           .setOrderId(order.getId()).build());
            return Boolean.TRUE;
        });
    }
}
```

#### 10.1.6 Listener

```java
@Service
@Slf4j
public class StockConsumer {

    @KafkaListener(topics = "stock-topic", groupId = "stock-app")
    public void onMessage(ConsumerRecord<String, StockDecrement> r,
                          Acknowledgment ack) {
        log.info("扣库存: orderId={}, delta={}",
                 r.value().getOrderId(), r.value().getDelta());
        // 业务处理 …
        ack.acknowledge();
    }
}
```

### 10.2 Python 完整示例(`confluent-kafka`)

```python
import json
import time
import uuid
from threading import Thread

from confluent_kafka import Producer, Consumer, KafkaError, KafkaException, TopicPartition


# ---------- Producer ----------
producer_conf = {
    'bootstrap.servers': 'redpanda-1:9092,redpanda-2:9092',
    'acks': 'all',
    'enable.idempotence': True,
    'compression.type': 'zstd',
    'linger.ms': 10,
    'batch.size': 32768,
}

def cb(err, msg):
    if err:
        print(f'FAILED: {err}')
    else:
        print(f'OK: {msg.topic()}[{msg.partition()}]@{msg.offset()}')


p = Producer(producer_conf)


def produce_loop():
    for i in range(100_000):
        order = {'id': f'order-{i}', 'amount': 99.99}
        p.produce('order-topic', key=order['id'],
                  value=json.dumps(order).encode(), callback=cb)
        p.poll(0)
    p.flush(30)


# ---------- Consumer ----------
consumer_conf = {
    'bootstrap.servers': 'redpanda-1:9092',
    'group.id': 'py-consumer',
    'auto.offset.reset': 'earliest',
    'enable.auto.commit': False,
    'isolation.level': 'read_committed',
}

c = Consumer(consumer_conf)
c.subscribe(['order-topic'])


def consume_loop():
    try:
        while True:
            m = c.poll(1.0)
            if m is None: continue
            if m.error():
                if m.error().code() == KafkaError._PARTITION_EOF:
                    continue
                raise KafkaException(m.error())
            order = json.loads(m.value().decode())
            print(f'CONSUMED: {order}')
            c.commit(message=m, asynchronous=False)
    finally:
        c.close()


Thread(target=produce_loop, daemon=True).start()
consume_loop()
```

### 10.3 Go 完整示例(`confluent-kafka-go` + Sarama 事务)

#### 10.3.1 Sarama 事务版

```go
package main

import (
    "encoding/json"
    "fmt"
    "log"
    "time"

    "github.com/IBM/sarama"
)

func main() {
    cfg := sarama.NewConfig()
    cfg.Version = sarama.V3_6_0_0
    cfg.Producer.Idempotent = true
    cfg.Producer.RequiredAcks = sarama.WaitForAll
    cfg.Producer.Transaction.ID = "order-tx-" + newUUID()
    cfg.Producer.Transaction.Retry.Max = 3
    cfg.Producer.Return.Successes = true
    cfg.Producer.Return.Errors = true
    cfg.Net.MaxOpenRequests = 1   // 事务模式下必须为 1

    brokers := []string{"redpanda-1:9092"}

    producer, err := sarama.NewSyncProducer(brokers, cfg)
    if err != nil { log.Fatal(err) }
    defer producer.Close()

    if err := producer.BeginTxn(); err != nil { log.Fatal(err) }

    for i := 0; i < 10; i++ {
        order := map[string]interface{}{
            "id":     fmt.Sprintf("order-%d", i),
            "amount": 99.99,
        }
        b, _ := json.Marshal(order)
        msg := &sarama.ProducerMessage{
            Topic: "order-topic",
            Key:   sarama.StringEncoder(fmt.Sprintf("order-%d", i)),
            Value: sarama.ByteEncoder(b),
        }
        if _, _, err := producer.SendMessage(msg); err != nil {
            producer.AbortTxn()
            log.Fatal(err)
        }
    }

    if err := producer.CommitTxn(); err != nil {
        log.Fatal(err)
    }
    log.Println("事务提交成功")
}

func newUUID() string {
    return fmt.Sprintf("%d", time.Now().UnixNano())
}
```

---

## 十一、性能对比:Kafka vs RedPanda(客户端视角)

> 以下数据基于公开 benchmark(Redpanda 官方与第三方实测),仅供**量级参考**。实际数字因硬件、消息大小、副本数而异。

### 11.1 同等配置下的吞吐量(MB/s, 1 KB 消息,3 节点,副本=3)

| 配置                                  | Kafka 3.6     | RedPanda v23.x | 提升 |
|---------------------------------------|---------------|----------------|------|
| `acks=1`,`compression=none`           | ~580 MB/s     | ~950 MB/s      | +64% |
| `acks=all`,`compression=zstd`         | ~420 MB/s     | ~860 MB/s      | +105%|
| `acks=all`,`compression=lz4`          | ~480 MB/s     | ~880 MB/s      | +83% |
| 64 KB 消息,`acks=all`,`zstd`          | ~3.2 GB/s     | ~5.5 GB/s      | +72% |
| 4 KB 消息,`acks=all`,`zstd`,3 副本    | ~700 MB/s     | ~1.4 GB/s      | +100%|

> RedPanda 优势来自:**单线程 Seastar 异步 + 零拷贝 + thread-per-core**,不依赖 Page Cache 副本同步。

### 11.2 P99 延迟(毫秒)

| 配置                                  | Kafka 3.6     | RedPanda v23.x | 改善 |
|---------------------------------------|---------------|----------------|------|
| `acks=1`,1 KB 消息                    | ~5 ms         | ~1.5 ms        | -70% |
| `acks=all`,1 KB 消息                  | ~12 ms        | ~4 ms          | -67% |
| `acks=all`,事务消息,1 KB              | ~25 ms        | ~7 ms          | -72% |
| `acks=all`,64 KB 消息                 | ~30 ms        | ~10 ms         | -67% |

### 11.3 关键结论

1. **同等配置下 RedPanda 通常吞吐高 50%~100%,P99 延迟低 50%~70%。**
2. 优势在大消息 / 高并发 / 严格一致性场景更明显。
3. CPU 占用 RedPanda 略高(因为自己做压缩、零拷贝),但延迟更低。
4. 客户端**不需要做任何修改**即可享受上述性能。

---

## 十二、客户端最佳实践

### 12.1 Producer 端

| 实践                                | 说明                                                                                  |
|-------------------------------------|---------------------------------------------------------------------------------------|
| **启用幂等**                        | `enable.idempotence=true`,防止单分区重复                                               |
| **`acks=all` + 副本 ≥ 3**           | 严格一致性必备                                                                         |
| **使用 `zstd` 压缩**                | RedPanda 默认压缩算法,平衡比最好                                                       |
| **`batch.size` + `linger.ms` 平衡** | 高吞吐场景用 32~128KB + 10~100ms;低延迟场景用 16KB + 0ms                              |
| **`buffer.memory` 适当调高**         | 64~256MB 抗突发                                                                        |
| **优雅关闭**                        | 调用 `close()` 或 `flush()` 避免丢消息                                                  |
| **Callback 必现**                   | 异步发送必带 callback,失败要在 callback 里处理                                         |
| **键控分区**                        | 业务上需要顺序的消息(如同一订单)用同一个 key                                          |
| **避免超大消息**                    | 默认 1MB,>1MB 消息会显著拖累性能,可考虑外部存储+消息存引用                            |
| **避免重复初始化**                  | 单例 Producer,频繁创建/关闭会丢消息且浪费资源                                          |

### 12.2 Consumer 端

| 实践                                    | 说明                                                                                  |
|-----------------------------------------|---------------------------------------------------------------------------------------|
| **手动提交位移**                        | 处理完业务再 ack,避免丢消息                                                            |
| **`enable.auto.commit=false`**          | 关闭自动提交                                                                            |
| **`isolation.level=read_committed`**   | 事务场景必设,避免读脏数据                                                              |
| **单条消息处理快**                      | `max.poll.interval.ms` 内必须调 `poll()`,否则会被踢出组                               |
| **幂等消费**                            | 业务侧必须做幂等,即使 ack 后失败重投也不会重复                                  |
| **优雅退出**                            | 调用 `close()` 或 `unsubscribe()`,避免 Rebalance                                       |
| **分配策略选 Cooperative**              | 减少 Rebalance 影响                                                                    |
| **背压控制**                            | 通过 `max.poll.records` + 队列长度限制反压                                              |
| **批量消费**                            | 高吞吐场景用 batch listener                                                            |

### 12.3 通用

| 实践                          | 说明                                                                                  |
|-------------------------------|---------------------------------------------------------------------------------------|
| **客户端版本 ≥ 3.0**          | Kafka 客户端 3.0+ 才完整支持新事务、增量 Rebalance                                     |
| **`bootstrap.servers` ≥ 2**   | 列出多个 broker,避免单点启动失败                                                      |
| **客户端 ID 唯一**            | 便于日志/指标定位                                                                      |
| **指标采集**                  | 通过 `kafka_exporter` / `librdkafka_stats` / 业务侧打点                                |
| **超时配置合理**              | `request.timeout.ms`、`delivery.timeout.ms`、`session.timeout.ms` 等根据业务设置        |
| **定期升级客户端**            | 跟随 RedPanda 服务端升级,获得最新 bug fix                                              |
| **TLS/SASL**                  | 生产环境必开 TLS,可选 SASL                                                            |

---

## 核心要点速记

| 要点                        | 关键内容                                                                                                                              |
|-----------------------------|---------------------------------------------------------------------------------------------------------------------------------------|
| **协议兼容**                | RedPanda **100% 兼容 Kafka Wire Protocol**,任何 Kafka 客户端 SDK(Java/Go/Python/C++/Rust)都可直接使用,无需修改业务代码               |
| **SDK 推荐**                | Java 用 `kafka-clients` 或 `spring-kafka`;C/C++ 用 `librdkafka`;Python 用 `confluent-kafka-python`;Go 用 `sarama` 或 `confluent-kafka-go` |
| **可靠性**                  | `acks=all` + `enable.idempotence=true` + `retries=MAX` + Broker 端 `min.insync.replicas≥2`                                                |
| **压缩**                    | **RedPanda 默认推荐 zstd**,比 lz4 压缩比更好、CPU 开销相近                                                                              |
| **事务**                    | RedPanda **完整支持 Kafka 事务 API**,`transactional.id` + `read_committed` 即可实现 Exactly-Once                                        |
| **Schema Registry**         | RedPanda **内置** Schema Registry,REST API 与 Confluent SR 兼容,Avro/Protobuf/JSON Schema 都可用                                       |
| **ISR 客户端无感**          | RedPanda 默认 `min.insync.replicas=1` 比 Kafka 宽松,但不影响客户端配置                                                                  |
| **批量 + linger**           | 高吞吐:`batch.size=32~128KB` + `linger.ms=10~100ms`;低延迟:`batch.size=16KB` + `linger.ms=0`                                            |
| **Spring Boot**             | 配置 `transaction-id-prefix` 自动开启事务;`executeInTransaction` 实现原子发送;`KafkaListener` 配合手动 ack                            |
| **性能优势**                | 同等配置下,RedPanda 通常 **吞吐高 50%~100%**,**P99 延迟低 50%~70%**(尤其大消息、严格一致性场景)                                       |
| **监控**                    | 通过 `kafka_exporter`、`librdkafka_stats`、客户端 Prometheus 指标采集                                                                       |
| **与 Kafka 差异(客户端)**   | 客户端层面**几乎无差异**;差异主要集中在服务端(`min.insync.replicas` 默认、`message.timestamp.type` 仅 CreateTime、内置 SR、默认压缩算法) |

> **一句话总结**:RedPanda 的客户端体验 = "**Kafka API + 更强的事务/SR/压缩默认值 + 更低的延迟**";迁移成本近乎为零,只需修改 `bootstrap.servers`,并把 `compression.type` 调成 `zstd`、把 `acks` 设为 `all` 即可立即获得性能与可靠性的双重提升。