# Kafka 概述与安装

## 一、Kafka 简介

### 1.1 什么是 Kafka

**Apache Kafka** 是一个开源的**分布式事件流平台 (Distributed Event Streaming Platform)**,最初由 LinkedIn 公司开发,后捐赠给 Apache 软件基金会,目前是 Apache 顶级项目 (TLP)。Kafka 以**高吞吐、低延迟、水平扩展**著称,被广泛用于消息队列、日志聚合、事件溯源、流式处理、CDC(变更数据捕获)等场景。

**核心定位**:

- 属于**分布式发布-订阅消息系统 (Pub/Sub)**,底层是**持久化、分布式的提交日志 (Commit Log)**
- 采用**生产者-消费者模型**,消息以**主题 (Topic)** 分类,按**分区 (Partition)** 顺序追加写
- 由 LinkedIn 的 **Jay Kreps、Neha Narkhede、Jun Rao** 三人于 2010 年开发
- 最初为解决 LinkedIn 内部**海量日志采集与传输**的需求
- 遵循 **Apache License 2.0** 协议,可自由用于商业
- 当前由 **Confluent** 公司(创始人 Jay Kreps 创立)主导贡献,社区非常活跃

### 1.2 发展历史

```text
┌──────────────────────────────────────────────────────────────┐
│ 2010   LinkedIn 的 Jay Kreps、Neha Narkhede、Jun Rao         │
│        开始内部开发,最初为解决日志管道问题                   │
│   ↓                                                          │
│ 2011   Kafka 在 GitHub 开源,Apache License 2.0              │
│   ↓                                                          │
│ 2012   成为 Apache 孵化器项目                                  │
│   ↓                                                          │
│ 2014   Jay Kreps 等三人离开 LinkedIn,创立 Confluent         │
│        Kafka 0.8.2 发布,引入副本机制                          │
│   ↓                                                          │
│ 2014   Kafka 0.9,推出新的消费者 API(替换 high-level)       │
│   ↓                                                          │
│ 2016   Kafka 0.10,引入 Kafka Streams(轻量流处理)            │
│   ↓                                                          │
│ 2017   Kafka 0.11,精确一次语义(EOS)、幂等生产者             │
│   ↓                                                          │
│ 2018   Kafka 1.0,稳定 API;Confluent 商业版成熟              │
│   ↓                                                          │
│ 2019   Kafka 2.0,Exactly-Once Streams、KIP-98(改进)        │
│   ↓                                                          │
│ 2020   Kafka 2.5,Kafka Connect 集群模式增强                 │
│   ↓                                                          │
│ 2021   Kafka 2.8,首次引入 **KRaft 模式**(替代 ZK 的早期)    │
│   ↓                                                          │
│ 2022   Kafka 3.0,**ZooKeeper 可选**,镜像 (MirrorMaker 2)  │
│   ↓                                                          │
│ 2023   Kafka 3.3,KRaft 生产就绪,Connector 优化              │
│   ↓                                                          │
│ 2023   Kafka 3.5,KRaft GA,**生产环境推荐**                  │
│   ↓                                                          │
│ 2024   Kafka 3.7,持续优化,Broker 全面 GA                    │
│   ↓                                                          │
│ 2025+  Kafka 4.x 路线图,完全弃用 ZK、Serverless 探索        │
└──────────────────────────────────────────────────────────────┘
```

### 1.3 创始人

Kafka 由 LinkedIn 的三位工程师在 2010 年开发:

| 创始人         | 角色              | 后续                                                |
|----------------|-------------------|-----------------------------------------------------|
| **Jay Kreps**  | 首席架构师        | 2014 年创立 **Confluent**,任 CEO                  |
| **Neha Narkhede** | 联合创始人    | Confluent 联合创始人,后于 2019 年创办 **Materialise** |
| **Jun Rao**    | 联合创始人        | 继续在 Confluent 担任技术高管                      |

> Kafka 名字的由来:作者 Jay Kreps 表示,Kafka 是为了致敬作家**弗朗茨·卡夫卡 (Franz Kafka)**,因为 Kafka 系统"适合用于书面系统",与卡夫卡的文学风格契合。

### 1.4 版本演进

| 版本        | 发布时间 | 主要特性                                                              | 状态            |
|-------------|----------|-----------------------------------------------------------------------|-----------------|
| 0.7         | 2011     | 最初开源版本,基础消息发布/订阅                                       | 已淘汰          |
| 0.8         | 2012     | 副本机制 (Replication),但仍不成熟                                   | 已淘汰          |
| 0.9         | 2014     | 新 Consumer API、Kafka Connect、安全认证                              | 历史版本        |
| 0.10        | 2016     | Kafka Streams、消息时间戳、压缩                                       | 历史版本        |
| 0.11        | 2017     | **幂等生产者**、**事务**、EOS 基础                                    | 历史版本        |
| 1.0         | 2018     | **API 稳定**,消息协议稳定                                            | 已 EOL          |
| 1.1 / 2.0   | 2018-2019 | EOS Streams、改进配额、磁盘配额                                       | 已 EOL          |
| 2.x         | 2020-2021 | MirrorMaker 2、KRaft 早期版本(2.8)                                  | 历史版本        |
| **3.0**     | 2022     | **ZooKeeper 可选**、自修复镜像                                       | 历史版本        |
| **3.3**     | 2023     | KRaft 生产就绪、自平衡                                                | 推荐生产        |
| **3.5**     | 2023     | **KRaft GA**,生产者插件化改进                                        | **推荐生产**    |
| **3.6**     | 2024     | KIP-848 新消费者组协议、Group 协议增强                               | 推荐生产        |
| **3.7**     | 2024     | 进一步稳定性优化、Broker 全面 KRaft                                  | 推荐生产        |
| 3.8 / 3.9   | 2025+    | KIP-405 Tiered Storage GA、更多 KRaft 改进                          | 较新生产版本    |
| 4.x         | 未来     | 完全弃用 ZK,Serverless 探索                                          | 路线图          |

> **版本选择建议**:生产环境推荐 **Kafka 3.5+** 或 **3.6+**(KRaft 模式 GA、稳定性高)。新部署**不再建议**使用 ZK 模式,KRaft 是未来方向。

### 1.5 Kafka 的特点

| 维度         | 说明                                                                            |
|--------------|---------------------------------------------------------------------------------|
| **高吞吐**   | 顺序写磁盘 + 零拷贝 (Zero-Copy) + 批量发送,单 broker 可达 100MB/s+              |
| **低延迟**   | 端到端毫秒级(同机房 < 5ms),Producer 异步、Consumer 批量拉取                     |
| **高扩展**   | Topic 可拆分多个 Partition,Broker 节点可线性扩展至上千台                         |
| **持久化**   | 消息默认**持久化到磁盘**,可配置保留时间(默认 7 天)或大小                         |
| **容错性**   | 多副本机制 (Replication),Leader/Follower 自动切换,容忍 N-1 节点故障             |
| **多语言**   | 官方支持 Java/Scala/Go/Python/Node.js/.NET/C/C++ 等近 30 种语言客户端          |
| **生态丰富** | Connect、Streams、KSQL(DB)、Schema Registry、Rest Proxy                        |
| **流处理**   | 集成 Kafka Streams(轻量)、可对接 Flink/Spark(重量)流处理框架                  |
| **精确语义** | **At Most Once**、**At Least Once**、**Exactly Once Semantics (EOS)** 三种     |
| **去 ZK 化** | KRaft 模式自带共识,无需 ZooKeeper,运维更简单                                    |

### 1.6 Kafka 适用场景

```text
┌────────────────────────────────────────────────────────────────┐
│                       Kafka 主要应用场景                        │
│                                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ 消息队列      │  │ 日志聚合      │  │ 事件溯源     │         │
│  │ Message Queue│  │ Log Pipeline │  │ Event Source │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│                                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ 流式处理      │  │ CDC 变更捕获 │  │ 指标监控     │         │
│  │ Stream       │  │ Change Data  │  │ Metrics/Trace│         │
│  │ Processing   │  │ Capture      │  │              │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└────────────────────────────────────────────────────────────────┘
```

- **消息队列**:异步解耦、削峰填谷(替代 RabbitMQ/RocketMQ 场景)
- **日志聚合**:集中采集各服务日志,投递到 ES/Loki/Splunk
- **事件溯源 (Event Sourcing)**:微服务架构下事件驱动
- **流式处理**:实时统计、推荐、风控,搭配 Kafka Streams/Flink
- **CDC (Change Data Capture)**:Debezium 把 MySQL/PG 变更同步到 Kafka
- **消息中台**:企业级统一消息通道,跨业务/跨系统对接
- **指标与链路追踪**:OpenTelemetry 通过 Kafka 推送 trace/metrics

---

## 二、Kafka 与其他 MQ 对比

### 2.1 主流消息中间件概览

| 维度         | Kafka                       | RabbitMQ                    | RocketMQ                    | Pulsar                        | ActiveMQ        |
|--------------|-----------------------------|------------------------------|------------------------------|-------------------------------|-----------------|
| **出身**     | LinkedIn → Apache           | Rabbit Tech (Erlang/OTP)     | 阿里巴巴 → Apache           | Yahoo → Apache                | Apache          |
| **语言**     | Scala/Java                  | Erlang                       | Java                         | Java                          | Java            |
| **协议**     | 自定义二进制                | AMQP 0-9-1、MQTT、STOMP      | 自定义(类 RocketMQ)         | 自定义 + Pulsar Protocol      | OpenWire/AMQP   |
| **消息模型** | 发布-订阅 (Pub/Sub) + 流    | 队列 + 主题 (Exchange)        | 队列 + 主题                  | 发布-订阅 + 流                | 队列 + 主题     |
| **吞吐量**   | 百万级/s                    | 万级/s                        | 十万级/s                     | 百万级/s                      | 万级/s          |
| **延迟**     | 毫秒级                      | 微秒级                        | 毫秒级                       | 毫秒级                        | 毫秒级          |
| **顺序性**   | 分区内有序                  | 队列有序                      | 队列/分区内有序              | 分区内有序                    | 队列有序        |
| **持久化**   | 磁盘(默认)                  | 内存/磁盘                      | 磁盘                         | 分布式 BookKeeper             | 内存/磁盘       |
| **消息回溯** | 支持(按 offset)            | 不支持                        | 支持(按时间)                | 支持                          | 不支持          |
| **事务**     | 0.11+ 支持                  | 不支持                        | 支持                         | 支持                          | 部分支持        |
| **消息优先级** | 不支持                    | 支持                          | 不支持                       | 不支持                        | 支持            |
| **多租户**   | 弱(多集群/标签)            | 弱(虚拟主机)                  | 弱                           | **强**(内置多租户)            | 弱              |
| **运维成本** | 中(KRaft 简化后较低)        | 低                            | 中                           | 高(需 ZK + BookKeeper)       | 低              |
| **生态**     | **最丰富** (Streams、Connect) | 丰富(插件)                  | 中(阿里系为主)              | 较强                          | 一般            |

### 2.2 vs RabbitMQ(传统消息队列)

| 维度           | Kafka                              | RabbitMQ                          |
|----------------|------------------------------------|-----------------------------------|
| **定位**       | 分布式事件流平台                    | 可靠消息代理 (Broker)             |
| **消费方式**   | **拉 (Pull)**                      | **推 (Push)**                     |
| **消息堆积**   | 强(磁盘无限堆积)                   | 弱(消费者必须实时消费)           |
| **延迟**       | 毫秒级                             | 微秒级                            |
| **吞吐量**     | 极高(顺序写 + 批处理)              | 中等(单队列)                     |
| **事务**       | 跨分区 EOS 复杂                    | 强(AMQP 事务)                    |
| **适用**       | **日志、流式、大数据、事件溯源**   | **业务消息、RPC、订单等业务场景** |

> **选型口诀**:
> - 业务消息、复杂路由、强事务 → **RabbitMQ**
> - 日志、大数据、流处理、消息量极大 → **Kafka**
> - 阿里系技术栈、双十一等高并发 → **RocketMQ**

### 2.3 vs RocketMQ(阿里系)

| 维度           | Kafka                          | RocketMQ                           |
|----------------|--------------------------------|-------------------------------------|
| **设计思路**   | 流式 + 日志                     | 业务消息(零丢失、严格顺序)         |
| **消息回溯**   | 任意 offset                    | 按时间回溯                          |
| **事务消息**   | 跨分区事务复杂                 | 原生支持事务消息                    |
| **顺序消息**   | 分区内                          | 全局/分区内                         |
| **定时消息**   | 不支持(可间接实现)            | 支持(18 个延迟级别)               |
| **活跃度**     | 国际化、生态最广                | 国内为主,阿里系深度集成             |
| **License**    | Apache 2.0                      | Apache 2.0                         |

### 2.4 vs Pulsar(新一代)

| 维度           | Kafka                            | Pulsar                              |
|----------------|----------------------------------|--------------------------------------|
| **架构**       | Broker + Log 存储(本机)          | Broker(无状态) + BookKeeper(存储层) |
| **计算存储分离** | 耦合(数据在 broker 磁盘)        | **天然分离**(可独立扩缩)            |
| **多租户**     | 弱                               | **强**(内置租户/命名空间)           |
| **跨地域**     | 较弱(MirrorMaker 2)              | 内置 Geo-Replication                 |
| **Function**   | Streams (Java/Scala)             | Pulsar Function (Go/Python/Java)     |
| **运维**       | KRaft 后较简单                   | 较复杂(需部署 ZK + BookKeeper)     |
| **成熟度**     | 极高(15+ 年)                     | 中等                                 |

### 2.5 vs Redis Pub/Sub(轻量发布订阅)

| 维度       | Kafka                  | Redis Pub/Sub             |
|------------|------------------------|---------------------------|
| **持久化** | 磁盘                   | 无(消息不落地)           |
| **消息堆积** | 强                  | 不支持(无消费者则丢)     |
| **回溯**   | 支持                   | 不支持                    |
| **吞吐**   | 百万级/s               | 万级/s                    |
| **适用**   | 重要业务、高可靠        | 实时通知、简单广播         |

### 2.6 总览对比表

| 消息中间件 | 类型       | 吞吐       | 延迟 | 持久化 | 消息回溯 | 适用场景                  |
|------------|------------|------------|------|--------|----------|---------------------------|
| **Kafka**  | 事件流     | **极高**   | 毫秒 | 强     | 强       | 日志、大数据、流处理、CDC |
| RabbitMQ   | 业务消息   | 中         | 微秒 | 中     | 弱       | 业务解耦、订单、RPC      |
| RocketMQ   | 业务消息   | 高         | 毫秒 | 强     | 中       | 阿里系、事务消息、双十一 |
| Pulsar     | 事件流     | 高         | 毫秒 | 强     | 强       | 多租户、跨地域、云原生    |
| ActiveMQ   | 业务消息   | 中         | 毫秒 | 弱     | 弱       | 老旧系统、传统企业        |
| Redis Pub/Sub | 通知   | 高         | 微秒 | 无     | 无       | 实时通知、广播            |

---

## 三、安装方式

Kafka 部署方式多样,生产环境主要三种:**单机 KRaft 模式**(推荐)、**KRaft 集群**、**Docker 容器化**。ZK 模式**仅作遗留**说明。

### 3.1 安装前准备

#### 3.1.1 硬件要求

| 角色       | 最低     | 推荐生产      |
|------------|----------|---------------|
| CPU        | 2 核     | 8 核+         |
| 内存       | 4 GB     | 16 GB+        |
| 磁盘       | 100 GB   | NVMe SSD,TB 级 |
| 网络       | 1 Gbps   | 10 Gbps       |

> Kafka 是**磁盘密集型**应用,推荐使用 **NVMe SSD** 以获得更高 IOPS。

#### 3.1.2 软件要求

| 软件     | 版本要求                  | 说明                          |
|----------|---------------------------|-------------------------------|
| JDK      | **JDK 17+(Kafka 3.6+)**  | Kafka 3.0+ 需 JDK 8+,3.6+ 推荐 17 |
| OS       | Linux 优先 (RHEL/Ubuntu)  | macOS 仅供开发                 |
| ZooKeeper | 3.6+ (仅 ZK 模式)        | KRaft 模式**无需** ZK          |
| ulimit   | nofile ≥ 65536           | 文件描述符限制                 |

```bash
# 查看 Java 版本
java -version
# openjdk version "17.0.x" 2024-xx-xx

# 查看 ulimit
ulimit -n
# 临时修改
ulimit -n 65536
# 永久修改 /etc/security/limits.conf
echo "* soft nofile 65536" >> /etc/security/limits.conf
echo "* hard nofile 65536" >> /etc/security/limits.conf
```

### 3.2 单机 KRaft 模式(推荐,Kafka 3.3+ 生产可用)

**KRaft (Kafka Raft)** 是 Kafka 3.3+ 推出的**自包含元数据共识机制**,**不再依赖 ZooKeeper**,简化了部署和运维。

#### 3.2.1 下载与解压

```bash
# 1. 下载 Kafka 3.7.0 二进制包
cd /opt
wget https://archive.apache.org/dist/kafka/3.7.0/kafka_2.13-3.7.0.tgz
# 清华镜像:https://mirrors.tuna.tsinghua.edu.cn/apache/kafka/3.7.0/

# 2. 解压
tar -xzf kafka_2.13-3.7.0.tgz
ln -s kafka_2.13-3.7.0 kafka
cd kafka

# 3. 查看目录
ls
# bin  config  libs  licenses  NOTICE  site-docs  src
```

> 命名规则:`kafka_<Scala 版本>-<Kafka 版本>.tgz`,如 `kafka_2.13-3.7.0` 表示 Kafka 3.7.0 跑在 Scala 2.13 上。

#### 3.2.2 配置 server.properties (KRaft 模式)

```bash
# 1. 复制配置(可选,默认即在 config/)
cp config/kraft/server.properties config/kraft/server.properties.bak

# 2. 编辑 config/kraft/server.properties
vi config/kraft/server.properties
```

**关键配置项**(KRaft 单机):

```properties
# ==================== 节点标识 ====================
# KRaft 节点 ID,集群内必须唯一
node.id=1

# 角色:单机既是 controller 又兼 broker
process.roles=broker,controller

# 控制器 quorum 投票地址
controller.quorum.voters=1@localhost:9093

# ==================== 监听器 ====================
# PLAINTEXT 对外(生产者/消费者),CONTROLLER 用于 KRaft 内部通信
listeners=PLAINTEXT://:9092,CONTROLLER://:9093

# 对外公布的地址(advertised.listeners 必须能让客户端访问)
advertised.listeners=PLAINTEXT://localhost:9092

# 控制器间通信监听
controller.listener.names=CONTROLLER
listener.security.protocol.map=CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT

# ==================== 日志 ========================
# 数据目录(KRaft 元数据 + 业务日志)
log.dirs=/var/lib/kafka-data

# ==================== 分区/副本 ====================
# 单机模式 1 个副本即可
num.partitions=1
default.replication.factor=1
offsets.topic.replication.factor=1
transaction.state.log.replication.factor=1
transaction.state.log.min.isr=1
```

#### 3.2.3 格式化存储目录

```bash
# 生成 cluster.id(只需执行一次)
KAFKA_CLUSTER_ID="$(bin/kafka-storage.sh random-uuid)"
echo $KAFKA_CLUSTER_ID
# 8字符以上,例如: MkU3OEVBNTcwNTJENDM2Qk

# 格式化日志目录
bin/kafka-storage.sh format -t $KAFKA_CLUSTER_ID -c config/kraft/server.properties
```

> 格式化操作是**不可逆**的,会清空数据目录,生产环境请谨慎。

#### 3.2.4 启动 Kafka

```bash
# 前台启动(调试用)
bin/kafka-server-start.sh config/kraft/server.properties

# 后台启动
bin/kafka-server-start.sh -daemon config/kraft/server.properties
# 或 nohup
nohup bin/kafka-server-start.sh config/kraft/server.properties > /var/log/kafka/kafka.log 2>&1 &
```

#### 3.2.5 验证

```bash
# 1. 查看进程
jps
# 看到 Kafka 进程

# 2. 端口监听
ss -ltnp | grep -E '9092|9093'
# LISTEN 0  50  *:9092  ...  Kafka
# LISTEN 0  50  *:9093  ...  Kafka

# 3. 创建 topic 测试
bin/kafka-topics.sh --bootstrap-server localhost:9092 --create \
  --topic test --partitions 1 --replication-factor 1

bin/kafka-topics.sh --bootstrap-server localhost:9092 --list
```

### 3.3 单机 ZK 模式(遗留,生产不推荐)

> ⚠️ **Kafka 4.x 将完全移除 ZK 模式**,新部署应使用 KRaft。

#### 3.3.1 安装 ZooKeeper

```bash
# Kafka 3.7 自带 ZK,启动即可
# 也可独立安装 ZK 3.8+
wget https://archive.apache.org/dist/zookeeper/zookeeper-3.8.4/apache-zookeeper-3.8.4-bin.tar.gz
tar -xzf apache-zookeeper-3.8.4-bin.tar.gz
cd apache-zookeeper-3.8.4-bin
cp conf/zoo_sample.cfg conf/zoo.cfg
# 编辑 dataDir
./bin/zkServer.sh start
```

#### 3.3.2 配置 server.properties (ZK 模式)

```bash
# 使用 config/server.properties(非 kraft 目录)
vi config/server.properties
```

```properties
# ==================== 基础 ====================
broker.id=0

# 监听器
listeners=PLAINTEXT://:9092
advertised.listeners=PLAINTEXT://localhost:9092

# 数据目录
log.dirs=/var/lib/kafka-data

# ==================== ZK 配置 ====================
zookeeper.connect=localhost:2181
zookeeper.connection.timeout.ms=18000

# ==================== 分区/副本 ====================
num.partitions=1
default.replication.factor=1
offsets.topic.replication.factor=1
```

#### 3.3.3 启动

```bash
# 1. 启动 ZK
./bin/zkServer.sh start

# 2. 启动 Kafka
bin/kafka-server-start.sh -daemon config/server.properties
```

### 3.4 Docker 安装(开发/测试推荐)

#### 3.4.1 KRaft 单机模式

```yaml
# docker-compose.yml
version: '3.8'
services:
  kafka:
    image: apache/kafka:3.7.0
    container_name: kafka
    ports:
      - "9092:9092"
    environment:
      # KRaft 模式配置
      KAFKA_CFG_NODE_ID: 1
      KAFKA_CFG_PROCESS_ROLES: 'broker,controller'
      KAFKA_CFG_CONTROLLER_QUORUM_VOTERS: '1@kafka:9093'
      KAFKA_CFG_LISTENERS: 'PLAINTEXT://:9092,CONTROLLER://:9093'
      KAFKA_CFG_ADVERTISED_LISTENERS: 'PLAINTEXT://localhost:9092'
      KAFKA_CFG_CONTROLLER_LISTENER_NAMES: 'CONTROLLER'
      KAFKA_CFG_LISTENER_SECURITY_PROTOCOL_MAP: 'CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT'
      KAFKA_CFG_AUTO_CREATE_TOPICS_ENABLE: 'true'
      # 启用 KRaft 模式(关键)
      CLUSTER_ID: 'MkU3OEVBNTcwNTJENDM2Qk'
    volumes:
      - kafka_data: /var/lib/kafka/data

volumes:
  kafka_data:
```

```bash
# 启动
docker compose up -d
docker compose logs -f kafka

# 测试
docker exec -it kafka /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server localhost:9092 --create --topic test
```

#### 3.4.2 完整 Stack (KRaft + AKHQ + Schema Registry)

```yaml
# docker-compose.yml - 全家桶
version: '3.8'
services:
  kafka:
    image: apache/kafka:3.7.0
    container_name: kafka
    ports:
      - "9092:9092"
    environment:
      KAFKA_CFG_NODE_ID: 1
      KAFKA_CFG_PROCESS_ROLES: 'broker,controller'
      KAFKA_CFG_CONTROLLER_QUORUM_VOTERS: '1@kafka:9093'
      KAFKA_CFG_LISTENERS: 'PLAINTEXT://:9092,CONTROLLER://:9093'
      KAFKA_CFG_ADVERTISED_LISTENERS: 'PLAINTEXT://localhost:9092'
      KAFKA_CFG_CONTROLLER_LISTENER_NAMES: 'CONTROLLER'
      KAFKA_CFG_LISTENER_SECURITY_PROTOCOL_MAP: 'CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT'
      KAFKA_CFG_AUTO_CREATE_TOPICS_ENABLE: 'true'
      CLUSTER_ID: 'MkU3OEVBNTcwNTJENDM2Qk'
    volumes:
      - kafka_data: /var/lib/kafka/data
    healthcheck:
      test: ["CMD-SHELL", "kafka-topics.sh --bootstrap-server localhost:9092 --list || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 5

  akhq:                                # Web UI 管理工具
    image: tchiotludo/akhq:latest
    container_name: akhq
    depends_on:
      kafka:
        condition: service_healthy
    ports:
      - "8080:8080"
    environment:
      AKHQ_CONFIGURATION: |
        akhq:
          connections:
            docker-kafka:
              bootstrap-servers: "kafka:9092"

volumes:
  kafka_data:
```

```bash
# 启动
docker compose up -d
# 访问 AKHQ: http://localhost:8080
```

#### 3.4.3 Bitnami 镜像(简化配置)

```bash
# Bitnami 提供环境变量包装好的镜像
docker run -d --name kafka \
  -p 9092:9092 \
  -e KAFKA_CFG_NODE_ID=0 \
  -e KAFKA_CFG_PROCESS_ROLES=controller,broker \
  -e KAFKA_CFG_LISTENERS=PLAINTEXT://:9092,CONTROLLER://:9093 \
  -e KAFKA_CFG_ADVERTISED_LISTENERS=PLAINTEXT://127.0.0.1:9092 \
  -e KAFKA_CFG_CONTROLLER_QUORUM_VOTERS=0@kafka:9093 \
  -e KAFKA_CFG_CONTROLLER_LISTENER_NAMES=CONTROLLER \
  -e KAFKA_CFG_LISTENER_SECURITY_PROTOCOL_MAP=CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT \
  -e ALLOW_PLAINTEXT_LISTENER=yes \
  -v kafka_data:/bitnami/kafka \
  bitnami/kafka:3.7
```

### 3.5 KRaft 集群模式(生产推荐)

#### 3.5.1 集群规划

```text
┌─────────────────────────────────────────────────────────────┐
│                Kafka KRaft 集群 (3 节点)                     │
│                                                             │
│   节点 1                节点 2                节点 3        │
│   10.0.0.11             10.0.0.12             10.0.0.13     │
│   broker,controller     broker,controller     broker,controller│
│   :9092, :9093          :9092, :9093          :9092, :9093  │
│                                                             │
│   controller.quorum.voters=1@10.0.0.11:9093,                │
│                          2@10.0.0.12:9093,                │
│                          3@10.0.0.13:9093                  │
└─────────────────────────────────────────────────────────────┘
```

#### 3.5.2 三节点配置

**节点 1** (`server.properties`):

```properties
node.id=1
process.roles=broker,controller
controller.quorum.voters=1@10.0.0.11:9093,2@10.0.0.12:9093,3@10.0.0.13:9093
listeners=PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:9093
advertised.listeners=PLAINTEXT://10.0.0.11:9092
controller.listener.names=CONTROLLER
listener.security.protocol.map=CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT
log.dirs=/var/lib/kafka-data
num.partitions=3
default.replication.factor=3
offsets.topic.replication.factor=3
transaction.state.log.replication.factor=3
transaction.state.log.min.isr=2
```

**节点 2** (`server.properties`):

```properties
node.id=2
# 相同 process.roles 和 quorum.voters
advertised.listeners=PLAINTEXT://10.0.0.12:9092
# 其他同节点 1
```

**节点 3** (`server.properties`):

```properties
node.id=3
advertised.listeners=PLAINTEXT://10.0.0.13:9092
```

#### 3.5.3 启动集群

```bash
# 在所有节点执行
# 1. 格式化(用同一个 cluster.id)
CLUSTER_ID="MkU3OEVBNTcwNTJENDM2Qk"
bin/kafka-storage.sh format -t $CLUSTER_ID -c config/kraft/server.properties

# 2. 启动
bin/kafka-server-start.sh -daemon config/kraft/server.properties

# 3. 在任一节点查看集群
bin/kafka-broker-api-versions.sh --bootstrap-server 10.0.0.11:9092
```

### 3.6 安装方式对比

| 方式             | 难度 | 适用场景                | 推荐度     |
|------------------|------|-------------------------|------------|
| **KRaft 单机**   | ★    | 开发、测试、学习         | ★★★★★      |
| **KRaft 集群**   | ★★★  | **生产环境**             | ★★★★★      |
| **ZK 模式**      | ★★   | 历史遗留系统(不再推荐) | ★          |
| **Docker 单机**  | ★    | 本地开发、CI            | ★★★★       |
| **Docker 集群**  | ★★★  | 中小规模生产            | ★★★★       |
| **Kubernetes**   | ★★★★  | 大规模生产、Operator  | ★★★★★     |

---

## 四、目录结构

Kafka 解压后主要有四大目录,各司其职。

### 4.1 顶层结构

```text
/opt/kafka/                       (Kafka 安装根目录)
├── bin/                          可执行脚本(启动/停止/管理)
│   ├── kafka-server-start.sh     启动 broker
│   ├── kafka-server-stop.sh      停止 broker
│   ├── kafka-topics.sh           Topic 管理
│   ├── kafka-console-producer.sh 控制台生产者
│   ├── kafka-console-consumer.sh 控制台消费者
│   ├── kafka-configs.sh          动态配置
│   ├── kafka-consumer-groups.sh  消费者组管理
│   ├── kafka-storage.sh          存储目录格式化
│   ├── kafka-broker-api-versions.sh 查看 API 版本
│   ├── kafka-log-dirs.sh         日志目录检查
│   ├── kafka-reassign-partitions.sh 分区重分配
│   ├── kafka-metadata-quorum.sh  KRaft 元数据检查
│   ├── zookeeper-server-start.sh (ZK 模式)启动 ZK
│   └── ...                      其他工具
├── config/                       配置文件
│   ├── server.properties         ZK 模式 broker 配置
│   ├── kraft/server.properties   KRaft 模式 broker 配置
│   ├── kraft/controller.properties  (可选)纯 controller 配置
│   ├── consumer.properties       消费者默认配置
│   ├── producer.properties       生产者默认配置
│   ├── tools-log4j2.properties   工具日志配置
│   ├── connect-*.properties      Connect 配置模板
│   └── log4j.properties          服务端日志(老版本)
├── libs/                         依赖 JAR 包(Scala/Kafka 自身)
├── licenses/                     许可证文件
├── logs/                         日志输出目录(默认)
│   ├── server.log                broker 启动日志
│   ├── controller.log            KRaft controller 日志
│   ├── state-change.log          状态变更日志
│   └── kafka-request.log         请求日志(可选)
├── site-docs/                    文档
├── bin-windows/                  Windows 下的 bat 脚本
└── src/                          源码(仅供参考)
```

### 4.2 数据目录结构 (log.dirs)

KRaft 模式下,数据目录中既有 KRaft 元数据,也有业务 topic 分区数据:

```text
/var/lib/kafka-data/                       (log.dirs)
├── meta.properties                         # 节点 ID、集群 ID(KRaft 模式)
├── @metadata-0/                            # KRaft 元数据分区(系统 topic)
│   ├── 00000000000000000000.log
│   └── 00000000000000000000.index
├── __consumer_offsets/                     # 消费者位移 topic(系统)
│   ├── 0/
│   │   ├── 00000000000000000000.log
│   │   ├── 00000000000000000000.index
│   │   └── 00000000000000000000.timeindex
│   └── ...
├── __transaction_state/                    # 事务状态 topic
└── <用户 topic>/
    ├── 0/                                  # partition 0
    │   ├── 00000000000000000000.log         # 实际数据(顺序追加写)
    │   ├── 00000000000000000000.index       # 偏移量索引
    │   ├── 00000000000000000000.timeindex   # 时间戳索引
    │   ├── 00000000000000000000.txnindex    # 事务索引(已删除)
    │   ├── leader-epoch-checkpoint
    │   └── partition.metadata
    ├── 1/                                  # partition 1
    └── ...
```

### 4.3 关键文件作用

| 文件/目录                      | 作用                                                    |
|--------------------------------|---------------------------------------------------------|
| `meta.properties`              | 节点标识、集群 ID                                       |
| `@metadata-0`                  | KRaft 元数据(替代 ZK)                                  |
| `__consumer_offsets`           | 消费者位移(替代 ZK 中的 `/consumers` 节点)             |
| `__transaction_state`          | 事务状态(事务消息)                                     |
| `*.log`                        | **消息实际数据**(顺序追加)                              |
| `*.index`                      | offset → 物理位置索引(稀疏索引)                        |
| `*.timeindex`                  | 时间戳 → offset 索引(按时间定位)                      |
| `*.snapshot`                   | KRaft 状态快照(加速启动)                               |
| `partition.metadata`           | 分区元数据(Leader/Replica 列表)                        |
| `leader-epoch-checkpoint`      | Leader epoch 检查点(防止脑裂)                         |

### 4.4 查看实际目录

```bash
# 1. 查看 log.dirs 配置
grep '^log.dirs' config/kraft/server.properties

# 2. 列出日志目录
bin/kafka-log-dirs.sh --bootstrap-server localhost:9092 --describe

# 3. 查看磁盘占用
du -sh /var/lib/kafka-data/*
du -sh /var/lib/kafka-data/test-*/
```

---

## 五、启动与停止

### 5.1 启动方式对比

| 启动方式        | 命令                                                                | 适用场景              | 优缺点                          |
|-----------------|---------------------------------------------------------------------|-----------------------|---------------------------------|
| **前台启动**    | `bin/kafka-server-start.sh config/kraft/server.properties`         | 调试、看实时日志      | 阻塞终端,Ctrl+C 关闭           |
| **-daemon**     | `bin/kafka-server-start.sh -daemon config/kraft/server.properties`  | 手动后台启动          | 简单,无 systemd 管理           |
| **nohup &**     | `nohup bin/kafka-server-start.sh ... > kafka.log 2>&1 &`           | 临时后台              | 日志重定向,无自启动           |
| **systemd**     | `systemctl start kafka`                                             | **生产环境推荐**      | 自动重启、开机自启、统一管理   |
| **Docker**      | `docker compose up -d`                                              | 容器化环境            | 隔离、易迁移                    |
| **Kubernetes**  | Strimzi / Confluent Operator                                       | 云原生                | 自动扩缩、滚动升级              |

### 5.2 KRaft 模式启动详解

#### 5.2.1 启动流程

```text
┌──────────────────────────────────────────────────────────────┐
│                  Kafka KRaft 启动流程                          │
│                                                              │
│  1. 加载 config/kraft/server.properties                      │
│        ↓                                                      │
│  2. 解析 node.id、process.roles、controller.quorum.voters     │
│        ↓                                                      │
│  3. 验证 cluster.id(目录中 meta.properties)                  │
│        ↓                                                      │
│  4. 启动 KafkaRaftClient,与 quorum 节点建立连接              │
│        ↓                                                      │
│  5. 选举 Leader(若首次启动,自己成为 Active controller)       │
│        ↓                                                      │
│  6. 加载 __cluster_metadata,初始化所有 topic                  │
│        ↓                                                      │
│  7. 启动 broker 端口(:9092) 监听客户端                       │
│        ↓                                                      │
│  8. 注册到 controller(若非首次,触发 metadata 同步)          │
└──────────────────────────────────────────────────────────────┘
```

#### 5.2.2 单节点启动

```bash
# 1. 准备(已完成,见 3.2 节)
ls /var/lib/kafka-data/meta.properties

# 2. 前台启动(调试)
cd /opt/kafka
bin/kafka-server-start.sh config/kraft/server.properties
# 看到 "KafkaServer id=1 started" 即成功

# 3. 后台启动
bin/kafka-server-start.sh -daemon config/kraft/server.properties

# 4. 查看启动日志
tail -f logs/server.log
# [2024-xx-xx 10:00:00,123] INFO KafkaServer id=1 started
```

#### 5.2.3 集群启动

```bash
# 在 3 个节点分别执行(建议顺序启动,避免脑裂)
# 节点 1
bin/kafka-server-start.sh -daemon config/kraft/server.properties

# 节点 2
bin/kafka-server-start.sh -daemon config/kraft/server.properties

# 节点 3
bin/kafka-server-start.sh -daemon config/kraft/server.properties

# 在任一节点验证集群
bin/kafka-broker-api-versions.sh --bootstrap-server 10.0.0.11:9092
bin/kafka-metadata-quorum.sh --bootstrap-server 10.0.0.11:9092 describe --status
```

#### 5.2.4 systemd 启动(生产推荐)

```bash
# 1. 创建 kafka 用户
useradd -r -s /bin/false kafka
chown -R kafka:kafka /opt/kafka
chown -R kafka:kafka /var/lib/kafka-data

# 2. 创建 systemd 单元文件
cat > /etc/systemd/system/kafka.service <<'EOF'
[Unit]
Description=Apache Kafka Server (KRaft mode)
Documentation=https://kafka.apache.org/documentation/
After=network.target

[Service]
Type=forking
User=kafka
Group=kafka
Environment="JAVA_HOME=/usr/lib/jvm/java-17-openjdk"
ExecStart=/opt/kafka/bin/kafka-server-start.sh -daemon /opt/kafka/config/kraft/server.properties
ExecStop=/opt/kafka/bin/kafka-server-stop.sh
Restart=on-failure
RestartSec=10
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF

# 3. 启动
systemctl daemon-reload
systemctl enable kafka
systemctl start kafka
systemctl status kafka
```

### 5.3 停止 Kafka

#### 5.3.1 优雅停止 (推荐)

```bash
# 1. kafka-server-stop.sh
bin/kafka-server-stop.sh
# 内部:先发 SIGTERM,等待 30 秒,再发 SIGKILL

# 2. systemd
systemctl stop kafka
```

#### 5.3.2 强制停止

```bash
# 找到 Kafka 主进程
jps
# 输出示例:
# 12345 Kafka

# 发送 SIGTERM
kill -TERM 12345

# 等待 30 秒,未退出再 SIGKILL
sleep 30
kill -9 12345
```

> **重要**:**不要**直接 `kill -9`,会导致未刷盘的日志丢失,可能产生数据不一致。

### 5.4 启动失败排查清单

| 现象                                            | 排查方向                                      |
|-------------------------------------------------|-----------------------------------------------|
| `Port already in use`                            | `lsof -i:9092` 查占用,kill 掉                |
| `Cluster ID mismatch`                            | 多个节点用不同 cluster.id 格式化,需重新格式化 |
| `No `meta.properties` found`                    | 未执行 `kafka-storage.sh format`              |
| `Insufficient number of voters`                 | `controller.quorum.voters` 配置错误           |
| `OutOfMemoryError`                               | JVM 堆内存不足,调大 KAFKA_HEAP_OPTS          |
| `Connection to node -1 could not be established` | `advertised.listeners` 客户端无法访问         |
| `Storage directory is not readable`             | 数据目录权限问题,`chown -R kafka:kafka`       |
| `Unable to load JAAS login`                    | 启用 SASL/SSL 时配置错误                      |

### 5.5 启动常用环境变量

```bash
# JVM 堆内存
export KAFKA_HEAP_OPTS="-Xms4G -Xmx4G"

# GC 配置
export KAFKA_JVM_PERFORMANCE_OPTS="-XX:+UseG1GC -XX:MaxGCPauseMillis=20"

# JMX 远程监控
export KAFKA_JMX_OPTS="-Dcom.sun.management.jmxremote \
  -Dcom.sun.management.jmxremote.port=9999 \
  -Dcom.sun.management.jmxremote.authenticate=false \
  -Dcom.sun.management.jmxremote.ssl=false"

# 日志目录
export KAFKA_LOG_DIR=/var/log/kafka
```

---

## 六、server.properties 完整配置详解

server.properties 是 Kafka broker 的**核心配置文件**,KRaft 模式位于 `config/kraft/server.properties`,ZK 模式位于 `config/server.properties`。

### 6.1 完整配置示例 (KRaft 模式)

```properties
# ============================================
# /opt/kafka/config/kraft/server.properties
# Kafka 3.7 KRaft 模式生产配置
# ============================================

# ==================== 基础标识 ====================
# 集群内唯一,1 ~ 2^31-1
node.id=1

# 角色:broker、controller,可同时承担
# 单机:broker,controller
# 分离部署:broker / controller
process.roles=broker,controller

# 控制器集群成员,奇数个(1, 3, 5 ...)
# 格式: <node_id>@<host>:<port>
controller.quorum.voters=1@node1:9093,2@node2:9093,3@node3:9093

# ==================== 监听器 ====================
# 内部监听(INTERNAL 用于节点间复制)、外部监听
listeners=PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:9093

# 对外公布地址(客户端实际连接的地址)
advertised.listeners=PLAINTEXT://node1.example.com:9092

# 控制器监听器名
controller.listener.names=CONTROLLER

# 监听器-协议映射
listener.security.protocol.map=CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT,SSL:SSL,SASL_PLAINTEXT:SASL_PLAINTEXT

# 内部节点间通信的监听器
inter.broker.listener.name=PLAINTEXT

# ==================== 网络/线程 ====================
num.network.threads=8
num.io.threads=16
socket.send.buffer.bytes=102400
socket.receive.buffer.bytes=102400
socket.request.max.bytes=104857600

# ==================== 日志 ====================
# 数据目录,多个用逗号分隔(可挂多盘)
log.dirs=/var/lib/kafka-data

# 默认分区数(自动创建 topic 时使用)
num.partitions=3

# 默认副本数
default.replication.factor=3

# 单个 partition 默认副本数下限(min.insync.replicas 副本数)
min.insync.replicas=2

# 单个日志段大小(默认 1GB)
log.segment.bytes=1073741824

# 日志段滚动时间
log.roll.hours=168

# 消息保留时间(默认 7 天)
log.retention.hours=168

# 消息保留大小(整个分区,默认 -1 不限)
log.retention.bytes=-1

# 日志段删除检查间隔
log.retention.check.interval.ms=300000

# ==================== 压缩/清理 ====================
# 日志清理策略:delete(按时间) / compact(按 key 压缩)
log.cleanup.policy=delete

# 压缩线程数
log.cleaner.threads=1

# ==================== 复制 ====================
# 默认副本数
default.replication.factor=3

# __consumer_offsets 副本数(自动建时)
offsets.topic.replication.factor=3

# 事务状态 topic 副本数
transaction.state.log.replication.factor=3
transaction.state.log.min.isr=2

# 副本拉取线程数
replica.fetch.min.bytes=1
replica.fetch.max.bytes=1048576
replica.fetch.wait.max.ms=500
replica.lag.time.max.ms=30000

# 副本同步模式:roundrobin / parent
# ==================== 系统 Topic 副本因子 ====================
# 必须 <= 集群节点数,且 >= min.insync.replicas
offsets.topic.replication.factor=3
offsets.topic.num.partitions=50

# ==================== 集群 ====================
# 自动创建 topic(开发可开,生产建议关)
auto.create.topics.enable=false

# topic 删除(默认开启)
delete.topic.enable=true

# 不存在的 topic 元数据缓存时间
group.initial.rebalance.delay.ms=3000

# ==================== ZK (遗留,KRaft 模式忽略) ====================
# zookeeper.connect=localhost:2181
# zookeeper.connection.timeout.ms=18000
```

### 6.2 关键参数详解

| 参数                                    | 作用                              | 推荐值              |
|-----------------------------------------|-----------------------------------|---------------------|
| `node.id`                               | 节点唯一 ID                       | 1,2,3...            |
| `process.roles`                         | 节点角色                          | broker,controller   |
| `controller.quorum.voters`              | 控制器集群成员                    | 3 个奇数节点        |
| `listeners`                             | 监听地址和端口                    | PLAINTEXT://:9092   |
| `advertised.listeners`                  | 对外公布地址                      | 实际 IP:9092        |
| `log.dirs`                              | 数据目录                          | /var/lib/kafka-data |
| `num.partitions`                        | 默认分区数                        | 3~6                 |
| `default.replication.factor`            | 默认副本因子                      | 3                   |
| `min.insync.replicas`                    | 最小 ISR 副本数                   | 2                   |
| `log.segment.bytes`                      | 日志段大小                        | 1 GB                |
| `log.retention.hours`                   | 消息保留时间                      | 168 (7 天)          |
| `log.cleanup.policy`                    | 清理策略                          | delete/compact      |
| `auto.create.topics.enable`             | 自动创建 topic                    | 生产建议 false      |
| `offsets.topic.replication.factor`      | 消费者位移副本数                  | 3                   |
| `transaction.state.log.replication.factor` | 事务状态副本数                 | 3                   |
| `num.network.threads`                   | 网络 IO 线程                      | CPU 核数 / 2        |
| `num.io.threads`                        | 磁盘 IO 线程                      | 磁盘数 × 2          |

### 6.3 配置修改生效方式

```bash
# 1. 大多数配置需要重启 broker 生效
systemctl restart kafka

# 2. 部分配置支持动态修改(主题级 / broker 级)
# 通过 kafka-configs.sh 动态调整
bin/kafka-configs.sh --bootstrap-server localhost:9092 \
  --entity-type brokers --entity-name 1 \
  --alter --add-config log.retention.hours=720
```

### 6.4 配置模板对比

| 配置项              | KRaft 单机        | KRaft 集群(3 节点) | ZK 模式(遗留)       |
|---------------------|-------------------|----------------------|----------------------|
| `node.id`           | 1                 | 1/2/3                | 0/1/2 (broker.id)    |
| `process.roles`     | broker,controller | broker,controller     | 仅 broker            |
| `controller.quorum.voters` | 1@localhost:9093 | 1/2/3@...:9093     | (无,需 ZK)           |
| `zookeeper.connect` | 不需要            | 不需要               | localhost:2181       |
| `default.replication.factor` | 1      | 3                    | 3                    |
| `offsets.topic.replication.factor` | 1 | 3                    | 3                    |
| `transaction.state.log.replication.factor` | 1 | 3                | 3                    |
| `inter.broker.listener.name` | PLAINTEXT | PLAINTEXT          | PLAINTEXT            |

---

## 七、Kafka CLI 工具

Kafka 自带大量管理工具,几乎所有运维操作都可通过 CLI 完成。

### 7.1 工具总览

| 工具                              | 作用                          | 常用场景                    |
|-----------------------------------|-------------------------------|-----------------------------|
| `kafka-topics.sh`                 | Topic 管理(创建/删除/查看)   | **最常用**                  |
| `kafka-console-producer.sh`       | 控制台生产者                  | 调试、发送测试消息          |
| `kafka-console-consumer.sh`       | 控制台消费者                  | 调试、消费测试消息          |
| `kafka-configs.sh`                | 动态配置                      | 调整保留时间、副本数等     |
| `kafka-consumer-groups.sh`        | 消费者组管理                  | 查看 lag、重置位移          |
| `kafka-storage.sh`                | 存储目录管理                  | KRaft 模式格式化            |
| `kafka-broker-api-versions.sh`    | 查看 broker API 版本          | 兼容性检查                  |
| `kafka-log-dirs.sh`               | 日志目录检查                  | 磁盘占用、异常 segment      |
| `kafka-reassign-partitions.sh`    | 分区重分配                    | 扩容、负载均衡              |
| `kafka-metadata-quorum.sh`        | KRaft 元数据集群管理          | 查看控制器状态              |
| `kafka-dump-log.sh`               | 解析日志段                    | 排查消息内容                |
| `kafka-acls.sh`                   | ACL 管理                      | 权限管理                    |
| `kafka-delegation-tokens.sh`      | Delegation Token 管理         | 临时凭证                    |
| `kafka-producer-perf-test.sh`     | 生产者压测                    | 性能测试                    |
| `kafka-consumer-perf-test.sh`     | 消费者压测                    | 性能测试                    |
| `kafka-verifiable-consumer.sh`    | 验证消费                      | 端到端测试                  |
| `kafka-verifiable-producer.sh`    | 验证生产                      | 端到端测试                  |
| `kafka-mirror-maker.sh`           | 镜像(集群间同步,旧)          | 多集群同步                  |
| `connect-*.sh`                    | Kafka Connect 管理             | 数据集成                    |
| `kafka-streams-application-reset.sh` | 重置 Streams 应用           | 状态清理                    |

### 7.2 通用参数

大部分 kafka-* 工具都支持以下通用参数:

```bash
# 必选:连接 broker
--bootstrap-server <host:port>           # 新版(推荐)
# 或 --bootstrap.servers
# 老版用 --zookeeper (ZK 模式)

# 可选
--command-config <file>                 # 额外的客户端配置(认证等)
--config <file>                         # 客户端配置文件
```

### 7.3 kafka-topics.sh (最常用)

详见第八节 "Topic 创建与管理"。

### 7.4 kafka-console-producer.sh / consumer.sh

```bash
# 生产者(交互式,Ctrl+D 退出)
bin/kafka-console-producer.sh \
  --bootstrap-server localhost:9092 \
  --topic test

# 生产者(发送指定 key/value)
bin/kafka-console-producer.sh \
  --bootstrap-server localhost:9092 \
  --topic test \
  --property "parse.key=true" \
  --property "key.separator=:"
# 输入: user1:hello kafka

# 消费者(从最新消息开始)
bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic test

# 消费者(从头开始)
bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic test \
  --from-beginning

# 消费者(显示 key 和时间戳)
bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic test \
  --property "print.key=true" \
  --property "print.timestamp=true" \
  --from-beginning

# 消费者(指定消费组)
bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic test \
  --group test-group \
  --from-beginning

# 消费者(读取某 partition)
bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic test \
  --partition 0 \
  --offset earliest

# 生产者(发送文件内容)
cat data.txt | bin/kafka-console-producer.sh \
  --bootstrap-server localhost:9092 \
  --topic test
```

### 7.5 kafka-configs.sh (动态配置)

```bash
# 1. 查看 broker 配置
bin/kafka-configs.sh --bootstrap-server localhost:9092 \
  --entity-type brokers --entity-name 1 --describe

# 2. 动态修改 broker 配置
bin/kafka-configs.sh --bootstrap-server localhost:9092 \
  --entity-type brokers --entity-name 1 \
  --alter --add-config log.retention.hours=720,num.partitions=6

# 3. 删除动态配置
bin/kafka-configs.sh --bootstrap-server localhost:9092 \
  --entity-type brokers --entity-name 1 \
  --alter --delete-config log.retention.hours

# 4. 查看 topic 配置
bin/kafka-configs.sh --bootstrap-server localhost:9092 \
  --entity-type topics --entity-name test --describe

# 5. 动态修改 topic 配置
bin/kafka-configs.sh --bootstrap-server localhost:9092 \
  --entity-type topics --entity-name test \
  --alter --add-config retention.ms=604800000

# 6. 查看客户端配额
bin/kafka-configs.sh --bootstrap-server localhost:9092 \
  --entity-type clients --entity-name test-client --describe
```

### 7.6 kafka-consumer-groups.sh

```bash
# 1. 列出所有消费者组
bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 --list

# 2. 查看消费者组详情
bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 \
  --group test-group --describe

# 输出:
# GROUP           TOPIC     PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG
# test-group      test      0          100             200             100

# 3. 查看所有组的状态
bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 --describe --all-groups

# 4. 重置 offset (--to-earliest / --to-latest / --to-offset / --to-datetime)
bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 \
  --group test-group \
  --topic test \
  --reset-offsets --to-earliest \
  --execute

# 5. 删除消费者组
bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 \
  --group test-group --delete
```

### 7.7 kafka-broker-api-versions.sh

```bash
# 查看 broker 支持的 API 版本
bin/kafka-broker-api-versions.sh --bootstrap-server localhost:9092
# 输出 broker 支持的 API 列表(用于兼容性检查)
```

### 7.8 kafka-log-dirs.sh

```bash
# 查看每个 broker 的日志目录占用
bin/kafka-log-dirs.sh --bootstrap-server localhost:9092 --describe
```

### 7.9 kafka-storage.sh (KRaft 模式)

```bash
# 1. 随机生成 cluster.id
bin/kafka-storage.sh random-uuid
# 输出: MkU3OEVBNTcwNTJENDM2Qk

# 2. 格式化日志目录
bin/kafka-storage.sh format -t <cluster-id> -c config/kraft/server.properties

# 3. 查看元数据状态(KRaft 集群)
bin/kafka-storage.sh info -c config/kraft/server.properties

# 4. KRaft 模式升级检查
bin/kafka-storage.sh upgrade -t <cluster-id> -c config/kraft/server.properties
```

### 7.10 kafka-metadata-quorum.sh (KRaft)

```bash
# 1. 查看控制器集群状态
bin/kafka-metadata-quorum.sh --bootstrap-server localhost:9092 describe --status

# 2. 查看控制器成员
bin/kafka-metadata-quorum.sh --bootstrap-server localhost:9092 describe --members

# 3. 控制器 leader 转移
bin/kafka-metadata-quorum.sh --bootstrap-server localhost:9092 remove-member
```

### 7.11 性能压测工具

```bash
# 生产者压测
bin/kafka-producer-perf-test.sh \
  --topic test-perf \
  --num-records 1000000 \
  --record-size 1024 \
  --throughput 100000 \
  --producer-props \
    bootstrap.servers=localhost:9092 \
    batch.size=65536 \
    linger.ms=10

# 消费者压测
bin/kafka-consumer-perf-test.sh \
  --topic test-perf \
  --messages 1000000 \
  --broker-list localhost:9092
```

---

## 八、Topic 创建与管理

Topic 是 Kafka 中**消息的逻辑分类**,每个 topic 由若干个 **partition** 组成,每个 partition 在集群的不同 broker 上有副本。

### 8.1 创建 Topic

#### 8.1.1 基本创建

```bash
# 创建最简 topic
bin/kafka-topics.sh --bootstrap-server localhost:9092 \
  --create --topic my-topic
# 默认 1 partition,1 replica(取决于 server.properties)

# 指定分区数和副本数
bin/kafka-topics.sh --bootstrap-server localhost:9092 \
  --create --topic my-topic \
  --partitions 3 \
  --replication-factor 3

# 指定副本分布
bin/kafka-topics.sh --bootstrap-server localhost:9092 \
  --create --topic my-topic \
  --partitions 3 \
  --replication-factor 2 \
  --replica-assignment 0:1,1:2,2:0
# partition0 -> broker1, broker2
# partition1 -> broker2, broker3
# partition2 -> broker3, broker1
```

#### 8.1.2 带配置创建

```bash
# 指定保留时间、压缩策略
bin/kafka-topics.sh --bootstrap-server localhost:9092 \
  --create --topic my-topic \
  --partitions 3 --replication-factor 2 \
  --config retention.ms=604800000 \
  --config cleanup.policy=compact \
  --config compression.type=producer

# 常用配置项
# retention.ms         消息保留时间(毫秒)
# retention.bytes      分区最大字节数
# cleanup.policy       delete / compact
# compression.type     producer / none / gzip / snappy / lz4 / zstd
# min.insync.replicas  最小 ISR
# segment.bytes        日志段大小
# segment.ms           日志段滚动时间
```

### 8.2 查看 Topic

```bash
# 1. 列出所有 topic
bin/kafka-topics.sh --bootstrap-server localhost:9092 --list

# 2. 排除内部 topic
bin/kafka-topics.sh --bootstrap-server localhost:9092 --list --exclude-internal

# 3. 查看 topic 详情
bin/kafka-topics.sh --bootstrap-server localhost:9092 \
  --describe --topic my-topic

# 4. 查看所有 topic 详情
bin/kafka-topics.sh --bootstrap-server localhost:9092 --describe

# 5. 查看指定 topic 的配置
bin/kafka-topics.sh --bootstrap-server localhost:9092 \
  --describe --topic my-topic --config
```

**describe 输出示例**:

```text
Topic: my-topic   TopicId: abc123   PartitionCount: 3   ReplicationFactor: 2
  Partition: 0   Leader: 1   Replicas: 1,2   Isr: 1,2
  Partition: 1   Leader: 2   Replicas: 2,3   Isr: 2,3
  Partition: 2   Leader: 3   Replicas: 3,1   Isr: 3,1
```

字段说明:

| 字段          | 含义                                      |
|---------------|-------------------------------------------|
| `TopicId`     | Topic 唯一 ID(2.8+ 引入)                |
| `Leader`      | 该 partition 的 Leader broker            |
| `Replicas`    | 副本所在的 broker 列表(包括 Leader)      |
| `Isr`         | In-Sync Replicas,与 Leader 同步的副本    |

### 8.3 修改 Topic

```bash
# 1. 增加分区(只能增加,不能减少)
bin/kafka-topics.sh --bootstrap-server localhost:9092 \
  --alter --topic my-topic --partitions 6

# 2. 修改 topic 配置
bin/kafka-topics.sh --bootstrap-server localhost:9092 \
  --alter --topic my-topic \
  --config retention.ms=259200000

# 3. 同时修改多个配置
bin/kafka-topics.sh --bootstrap-server localhost:9092 \
  --alter --topic my-topic \
  --config retention.ms=86400000 \
  --config max.message.bytes=1048576

# 4. 删除某个配置(恢复默认)
bin/kafka-topics.sh --bootstrap-server localhost:9092 \
  --alter --topic my-topic \
  --delete-config retention.ms
```

> ⚠️ **重要**:`--partitions` 只能**增加**,不能减少!如需减少,需创建新 topic 并迁移数据。

### 8.4 删除 Topic

```bash
# 1. 删除 topic(需 delete.topic.enable=true)
bin/kafka-topics.sh --bootstrap-server localhost:9092 \
  --delete --topic my-topic

# 2. 批量删除(配合 grep)
bin/kafka-topics.sh --bootstrap-server localhost:9092 --list | grep '^test-' | xargs -I {} \
  bin/kafka-topics.sh --bootstrap-server localhost:9092 --delete --topic {}

# 3. 删除后查看是否成功
bin/kafka-topics.sh --bootstrap-server localhost:9092 --list
# 内部 topic(__consumer_offsets 等)不会删除
```

### 8.5 分区重分配

```bash
# 1. 生成重分配方案(扩容后必备)
cat > reassign.json <<EOF
{
  "topics": [
    { "topic": "my-topic", "partition": 0 },
    { "topic": "my-topic", "partition": 1 },
    { "topic": "my-topic", "partition": 2 }
  ]
}
EOF

bin/kafka-reassign-partitions.sh \
  --bootstrap-server localhost:9092 \
  --generate \
  --topics-to-move-json-file reassign.json
# 输出: 候选方案 + 当前方案

# 2. 执行重分配
cat > execute-reassign.json <<EOF
{
  "version": 1,
  "partitions": [
    {"topic": "my-topic", "partition": 0, "replicas": [1,2,3]},
    {"topic": "my-topic", "partition": 1, "replicas": [2,3,1]},
    {"topic": "my-topic", "partition": 2, "replicas": [3,1,2]}
  ]
}
EOF

bin/kafka-reassign-partitions.sh \
  --bootstrap-server localhost:9092 \
  --execute \
  --reassignment-json-file execute-reassign.json

# 3. 查看进度
bin/kafka-reassign-partitions.sh \
  --bootstrap-server localhost:9092 \
  --verify \
  --reassignment-json-file execute-reassign.json
```

### 8.6 常用命令速查

| 操作           | 命令                                                                 |
|----------------|----------------------------------------------------------------------|
| 列出 topic     | `--list`                                                            |
| 创建 topic     | `--create --topic X --partitions N --replication-factor M`          |
| 查看 topic     | `--describe --topic X`                                              |
| 修改分区数     | `--alter --topic X --partitions N` (只能增加)                       |
| 修改配置       | `--alter --topic X --config k=v`                                    |
| 删除配置       | `--alter --topic X --delete-config k`                               |
| 删除 topic     | `--delete --topic X`                                                |
| 查看所有 topic | `--describe`                                                        |

### 8.7 Topic 设计最佳实践

```text
┌─────────────────────────────────────────────────────────────┐
│                   Topic 设计要点                             │
│                                                             │
│  1. 分区数:                                                │
│     - 不宜过多(单 broker 建议 1000 个分区以内)              │
│     - 预估未来流量,可适度冗余                              │
│     - 每个分区 <= 几十 MB/s                                │
│                                                             │
│  2. 副本数:                                                │
│     - 生产建议 RF=3,可容忍 2 节点故障                      │
│     - 关键业务可 RF=5                                      │
│                                                             │
│  3. 命名:                                                  │
│     - 业务前缀_子模块_用途,如 order_payment_request         │
│     - 避免使用下划线开头(易误认为内部 topic)              │
│                                                             │
│  4. 清理策略:                                              │
│     - 普通业务:delete(7~30 天)                             │
│     - 状态/配置:compact(只保留最新)                        │
│     - 大数据 + 长保留:delete + tiered storage              │
└─────────────────────────────────────────────────────────────┘
```

---

## 九、消息生产与消费测试

完成安装后,通过生产/消费测试验证集群可用性。

### 9.1 命令行生产/消费

```bash
# 1. 创建测试 topic
bin/kafka-topics.sh --bootstrap-server localhost:9092 \
  --create --topic hello-kafka --partitions 3 --replication-factor 1

# 2. 启动消费者(终端 A)
bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic hello-kafka \
  --from-beginning

# 3. 启动生产者(终端 B),输入消息
bin/kafka-console-producer.sh \
  --bootstrap-server localhost:9092 \
  --topic hello-kafka
> Hello World
> Kafka Test
> [Ctrl+D 退出]
```

终端 A 输出:

```text
Hello World
Kafka Test
```

### 9.2 带 Key 的消息

```bash
# 1. 生产者(每行格式: key:value)
bin/kafka-console-producer.sh \
  --bootstrap-server localhost:9092 \
  --topic hello-kafka \
  --property "parse.key=true" \
  --property "key.separator=:"
> user1:Hello
> user2:Kafka
> user1:World

# 2. 消费者(显示 key)
bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic hello-kafka \
  --property "print.key=true" \
  --property "print.timestamp=true" \
  --from-beginning

# 输出:
# user1  [2024-12-30 10:00:00,123] Hello
# user2  [2024-12-30 10:00:01,456] Kafka
# user1  [2024-12-30 10:00:02,789] World
```

### 9.3 性能压测

```bash
# 1. 创建压测 topic
bin/kafka-topics.sh --bootstrap-server localhost:9092 \
  --create --topic perf-test --partitions 6 --replication-factor 1

# 2. 生产者压测:100 万条,每条 1KB,吞吐 10 万/秒
bin/kafka-producer-perf-test.sh \
  --topic perf-test \
  --num-records 1000000 \
  --record-size 1024 \
  --throughput 100000 \
  --producer-props \
    bootstrap.servers=localhost:9092 \
    batch.size=65536 \
    linger.ms=10 \
    compression.type=lz4

# 输出示例:
# 1000000 records sent, 1024.5 MB/s (1024567.0 records/s), 100.20 ms avg latency, 150.30 ms max latency.

# 3. 消费者压测
bin/kafka-consumer-perf-test.sh \
  --topic perf-test \
  --messages 1000000 \
  --broker-list localhost:9092
```

### 9.4 Python 客户端测试

```python
# 安装:pip install kafka-python
from kafka import KafkaProducer, KafkaConsumer
import json
import time

# ============ 生产者 ============
producer = KafkaProducer(
    bootstrap_servers=['localhost:9092'],
    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
    key_serializer=lambda k: k.encode('utf-8') if k else None,
    acks='all',                      # 等待所有副本确认
    retries=3,
    linger_ms=10,                    # 批量发送延迟
    compression_type='lz4',
)

for i in range(100):
    future = producer.send(
        'hello-kafka',
        key=f'user-{i % 10}',
        value={'msg': f'Hello {i}', 'ts': time.time()}
    )
    # 阻塞等待(可异步)
    record_metadata = future.get(timeout=10)
    print(f'Sent to partition {record_metadata.partition} at offset {record_metadata.offset}')

producer.flush()
producer.close()

# ============ 消费者 ============
consumer = KafkaConsumer(
    'hello-kafka',
    bootstrap_servers=['localhost:9092'],
    group_id='my-group',
    auto_offset_reset='earliest',
    enable_auto_commit=True,
    value_deserializer=lambda v: json.loads(v.decode('utf-8')),
    key_deserializer=lambda k: k.decode('utf-8') if k else None,
)

for message in consumer:
    print(f'partition={message.partition} '
          f'offset={message.offset} '
          f'key={message.key} '
          f'value={message.value}')
```

### 9.5 Java 客户端测试

```java
// Maven 依赖
// <dependency>
//   <groupId>org.apache.kafka</groupId>
//   <artifactId>kafka-clients</artifactId>
//   <version>3.7.0</version>
// </dependency>

import org.apache.kafka.clients.producer.*;
import org.apache.kafka.clients.consumer.*;
import org.apache.kafka.common.serialization.*;
import java.time.Duration;
import java.util.*;

public class KafkaQuickStart {
    public static void main(String[] args) {
        // ============ 生产者 ============
        Properties producerProps = new Properties();
        producerProps.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        producerProps.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
        producerProps.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
        producerProps.put(ProducerConfig.ACKS_CONFIG, "all");
        producerProps.put(ProducerConfig.LINGER_MS_CONFIG, 10);

        try (KafkaProducer<String, String> producer = new KafkaProducer<>(producerProps)) {
            for (int i = 0; i < 100; i++) {
                ProducerRecord<String, String> record = new ProducerRecord<>(
                    "hello-kafka", "user-" + (i % 10), "Hello " + i);
                producer.send(record, (metadata, exception) -> {
                    if (exception == null) {
                        System.out.printf("Sent to partition=%d offset=%d%n",
                            metadata.partition(), metadata.offset());
                    } else {
                        exception.printStackTrace();
                    }
                });
            }
        }

        // ============ 消费者 ============
        Properties consumerProps = new Properties();
        consumerProps.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        consumerProps.put(ConsumerConfig.GROUP_ID_CONFIG, "java-consumer-group");
        consumerProps.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());
        consumerProps.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());
        consumerProps.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "earliest");

        try (KafkaConsumer<String, String> consumer = new KafkaConsumer<>(consumerProps)) {
            consumer.subscribe(Collections.singletonList("hello-kafka"));
            while (true) {
                ConsumerRecords<String, String> records = consumer.poll(Duration.ofMillis(1000));
                for (ConsumerRecord<String, String> record : records) {
                    System.out.printf("partition=%d offset=%d key=%s value=%s%n",
                        record.partition(), record.offset(), record.key(), record.value());
                }
            }
        }
    }
}
```

### 9.6 验证消息顺序性

```bash
# 1. 创建单分区 topic(保证全局顺序)
bin/kafka-topics.sh --bootstrap-server localhost:9092 \
  --create --topic ordered-test --partitions 1 --replication-factor 1

# 2. 生产 100 条带序号的 key
bin/kafka-console-producer.sh \
  --bootstrap-server localhost:9092 \
  --topic ordered-test \
  --property "parse.key=true" \
  --property "key.separator=|"
> 1|msg-1
> 2|msg-2
> 3|msg-3

# 3. 消费
bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic ordered-test \
  --property "print.key=true" \
  --from-beginning
```

> **顺序保证**:Kafka 仅保证**单个 partition 内**消息有序,跨 partition 不保证。需要全局顺序的业务,必须使用**单分区**(限制并发),或业务层额外处理。

---

## 十、升级与迁移

### 10.1 升级路径

| 升级方式         | 适用场景                                | 风险     | 停机     |
|------------------|-----------------------------------------|----------|----------|
| **滚动升级**     | 集群内 broker 逐个重启                  | 中       | **无停机** |
| **大版本升级**   | Kafka 2.x → 3.x、3.x → 4.x            | 中-高    | 短暂     |
| **ZK → KRaft**  | ZK 模式迁移到 KRaft 模式                | 中       | **短暂** |
| **跨集群迁移**   | 业务迁移到新 Kafka 集群                 | 中       | 视场景   |

### 10.2 升级前的检查

```bash
# 1. 当前版本检查
bin/kafka-server-start.sh --version
# 或
bin/kafka-broker-api-versions.sh --bootstrap-server localhost:9092 | head -5

# 2. 备份 server.properties
cp config/kraft/server.properties config/kraft/server.properties.bak

# 3. 备份 __consumer_offsets 数据(可选)
# 数据本身在 log.dirs 中,会随升级保留

# 4. 备份自定义工具脚本
ls bin/ > bin-list.txt
```

### 10.3 滚动升级 (3 节点集群)

```bash
# 升级顺序: 节点 3 → 节点 2 → 节点 1
# (先升级非 controller 节点,最后升级 controller leader)

# ============ 节点 3 ============
# 1. 停掉节点 3
ssh node3 "systemctl stop kafka"

# 2. 替换二进制
ssh node3 "cd /opt && rm -rf kafka.new && tar -xzf kafka_2.13-3.7.0.tgz && mv kafka_2.13-3.7.0 kafka.new"
ssh node3 "ln -sfn /opt/kafka.new /opt/kafka"

# 3. 启动节点 3
ssh node3 "systemctl start kafka"

# 4. 等待同步
sleep 60
bin/kafka-broker-api-versions.sh --bootstrap-server node3:9092 | head

# 5. 重复 节点 2、节点 1
```

> 滚动升级的**约束**:
> - 升级路径只能向前兼容(老 client → 新 broker 可以,新 client → 老 broker 需谨慎)
> - 跨大版本建议先到目标版本的**前一个版本**过渡一次
> - 升级时观察 `UnderReplicatedPartitions` 指标

### 10.4 ZK 模式迁移到 KRaft 模式

Kafka 3.3+ 提供 `kafka-storage.sh` 工具支持在线迁移。

```bash
# 步骤 1:在 ZK 模式集群上安装新版本 Kafka(3.3+)
# 步骤 2:停掉所有 broker
systemctl stop kafka

# 步骤 3:用 KRaft 配置启动(会自动迁移元数据)
bin/kafka-server-start.sh -daemon config/kraft/server.properties
# Kafka 3.3+ 会自动把 ZK 中的元数据导入 KRaft
```

> ⚠️ **必须**先在测试环境验证迁移过程,生产环境需有回滚方案(保留 ZK 集群的访问权限)。

### 10.5 数据迁移 (MirrorMaker 2)

跨集群数据同步,Kafka 3.0+ 推荐使用 **MirrorMaker 2 (MM2)**。

```bash
# MM2 配置文件 mm2.properties
clusters = source, target
source.bootstrap.servers = source-kafka:9092
target.bootstrap.servers = target-kafka:9092

source->target.enabled = true
source->target.topics = .*
```

```bash
# 启动 MM2
bin/connect-mirror-maker.sh mm2.properties
```

### 10.6 升级注意事项清单

| 注意项                                       | 说明                                            |
|---------------------------------------------|-------------------------------------------------|
| 阅读 [UPGRADE.md](https://kafka.apache.org/) | 官方升级文档,重点看 Breaking Changes            |
| 客户端先升级                                 | Producer/Consumer 升级到新版本再升级 broker     |
| 保留旧版本二进制                              | 便于回滚                                        |
| 检查 ZK → KRaft 兼容性                      | 3.3+ 才支持自动迁移,3.0~3.2 需手工迁移          |
| 单 broker 灰度                              | 先升级 1 个节点观察数小时,再滚动                |
| 升级时监控                                   | 关注 `UnderReplicatedPartitions`、消费者 lag     |

---

## 十一、卸载

### 11.1 二进制安装的卸载

```bash
# 1. 停止 Kafka
bin/kafka-server-stop.sh
# 或
systemctl stop kafka
systemctl disable kafka

# 2. 删除 systemd 服务
rm -f /etc/systemd/system/kafka.service
systemctl daemon-reload

# 3. 删除安装目录
rm -rf /opt/kafka
rm -rf /opt/kafka.new
rm -f /opt/kafka_2.13-3.7.0.tgz

# 4. 删除数据目录(谨慎,会丢失所有数据!)
rm -rf /var/lib/kafka-data

# 5. 删除日志目录
rm -rf /var/log/kafka

# 6. 删除 kafka 用户
userdel -r kafka
```

### 11.2 Docker 卸载

```bash
# 1. 停掉并删除容器
docker compose down
# 或
docker stop kafka && docker rm kafka

# 2. 删除镜像(可选)
docker rmi apache/kafka:3.7.0

# 3. 删除数据卷(清数据,谨慎)
docker volume ls | grep kafka
docker volume rm <project>_kafka_data
```

### 11.3 验证彻底卸载

```bash
# 验证命令不存在
which kafka-server-start.sh
which kafka-topics.sh

# 验证无进程
pgrep -af kafka

# 验证无端口监听
ss -ltnp | grep -E '9092|9093'

# 验证无 systemd 服务
systemctl list-unit-files | grep kafka
# 应无输出

# 验证目录已清
ls /opt/kafka 2>&1 | grep "No such file"
ls /var/lib/kafka-data 2>&1 | grep "No such file"
```

---

## 十二、核心要点速记

- **Kafka 是 Apache 顶级项目**,由 LinkedIn 的 Jay Kreps 等于 2010 年开发,2014 年成为 Apache TLP,Confluent 是主要贡献者
- **核心定位**:分布式事件流平台,**高吞吐、低延迟、水平扩展、持久化**
- **版本选择**:生产推荐 **Kafka 3.5+ 或 3.6+**,**优先 KRaft 模式**(3.3+ GA、3.5+ 完全稳定)
- **架构模型**:**发布-订阅**,数据以**主题 (Topic)** 组织,Topic 拆分为多个 **分区 (Partition)**,Partition 可有多个**副本 (Replica)**
- **消费模式**:**拉 (Pull) 模式**,消费者主动拉取,可批量处理、易于消息回溯
- **存储**:**顺序写磁盘** + **零拷贝** + **页缓存**,既保证持久化又有高性能
- **KRaft vs ZK**:**KRaft 是未来**,Kafka 4.x 将完全移除 ZK;新部署**不再使用 ZK 模式**
- **安装方式对比**:KRaft 单机(开发)→ KRaft 集群(生产)→ Docker(快速部署)→ Kubernetes(云原生)
- **目录结构四件套**:`bin/`(脚本)、`config/`(配置)、`libs/`(依赖)、`logs/`(日志)
- **数据目录**:KRaft 模式包含 `@metadata-0`(元数据)、`__consumer_offsets`(位移)、业务 topic 三部分
- **启动方式**:`-daemon` 临时后台、**systemd 生产推荐**、Docker/K8s 容器化
- **停止方式**:`kafka-server-stop.sh` 或 `systemctl stop kafka`,**避免 kill -9**
- **配置文件 `server.properties`**:KRaft 模式在 `config/kraft/`,关键参数为 `node.id`、`process.roles`、`controller.quorum.voters`、`listeners`、`log.dirs`
- **`process.roles`** 可为 `broker,controller` 或单独,单机模式两者同设
- **关键副本参数**:`default.replication.factor=3`、`min.insync.replicas=2`、`offsets.topic.replication.factor=3`
- **Topic 副本数**:**只能增加不能减少**;**单 broker 集群** `replication.factor` 只能为 1
- **CLI 工具**:`kafka-topics.sh`(Topic 管理)是最常用;`kafka-console-producer/consumer.sh` 是调试神器
- **`kafka-consumer-groups.sh --describe`**:看消费者 lag 的必备命令
- **Topic 设计**:分区数预估未来流量、副本数 RF=3、清理策略 `delete`/`compact`、命名规范 `业务_模块_用途`
- **消息顺序保证**:**仅分区内有序**,跨分区无序;全局顺序需单分区(牺牲并发)
- **生产消息保证**:`acks=all` + `min.insync.replicas=2` 是不丢消息的常用组合
- **零停机升级**:滚动升级 broker(从非 controller 节点开始),客户端先升
- **Kafka 4.x**:将完全弃用 ZK,新项目应直接基于 KRaft 模式
- **生态工具**:Kafka Connect(数据集成)、Kafka Streams(轻量流处理)、Schema Registry(Schema 管理)、AKHQ/Kafka UI(可视化)
- **典型应用**:消息队列、日志聚合、CDC、流处理、事件溯源、监控指标管道
- **坑点提示**:
  - 客户端访问失败:90% 是 `advertised.listeners` 没配对外网地址
  - 单节点集群:`replication.factor` 必须为 1,否则 topic 创建失败
  - KRaft 模式启动前**必须** `kafka-storage.sh format`
  - `kill -9` 会导致未刷盘消息丢失,务必用 `kafka-server-stop.sh` 或 `kill -TERM`
  - Topic 副本数**不能减少**,扩容/缩容需通过 `kafka-reassign-partitions.sh` 重新分配
  - 大量 topic 时注意文件描述符限制,`ulimit -n 65536+`
