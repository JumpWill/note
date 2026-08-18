# RedPanda 概述与安装

## 一、RedPanda 简介

### 1.1 什么是 RedPanda

**Redpanda**(原名 Vectorized)是一个**开源的、实时流处理平台**,**完全兼容 Apache Kafka API**,但采用全新的**C++ 实现**,在架构、性能、运维上都对传统 Kafka 做了**颠覆性重构**。Redpanda 被称为 **"Kafka 的直接替代品"**——现有 Kafka 客户端、工具、Connect 几乎**零成本迁移**,这是 Redpanda 在短短几年内被众多企业采用的关键原因之一。

从本质上讲,Redpanda 并不是在 Kafka 之上做"优化",而是**重新思考流平台应该是什么样**:能否摆脱 JVM 的 GC 停顿?能否在不使用 ZooKeeper 的前提下实现可靠的分布式共识?能否把 broker、controller、Schema Registry、Connect 全部压缩到一个二进制里?这些问题的答案,就是 Redpanda。

**核心定位**:

- 100% **Kafka API 兼容**(Kafka 客户端协议、Kafka Connect、Kafka Streams 均可直接接入,无需任何业务代码改造)
- 采用 **C++ 实现**,基于 **Seastar 异步框架** + **thread-per-core 架构**,**充分利用现代多核 CPU 的 NUMA 亲和性**
- **无 JVM、无 ZooKeeper、无 KRaft**,单二进制即可启动整个集群,无需任何外部服务依赖
- 由 **Vectorized Inc.** 于 **2020 年开源**(公司同年成立),**2023 年**完成 C 轮融资并更名为 Redpanda Data
- **创始人 Alexander Gallego**(原 LinkedIn 资深工程师,曾深度参与 Kafka 内部优化,亲身经历过亿级流量下 GC 抖动的痛苦)
- 遵循 **Business Source License (BSL)**,源码开放,可自用、可商用,**云厂商再分发受限**(保护商业模式)

**为什么选择 Redpanda?** 简单的几个理由:
1. **极简部署**:单个二进制,5 分钟启动一个生产级集群,无需任何外部依赖
2. **超低延迟**:无 GC + thread-per-core,p99 延迟稳定 < 5ms,适合金融、游戏、实时竞价等场景
3. **资源高效**:相同吞吐量下,CPU/内存占用约为 Kafka 的 1/3,云上成本更低
4. **现代生态**:内置 Schema Registry、Connect、Console,**不再需要 Confluent 全家桶**

### 1.2 发展历史

```text
┌──────────────────────────────────────────────────────────────┐
│ 2019   Alexander Gallego 开始内部研发 Redpanda 原型            │
│        目标:用 C++ 重写 Kafka,解决 JVM GC 抖动问题           │
│   ↓                                                          │
│ 2020   Vectorized 公司成立,Redpanda 在 GitHub 开源           │
│        基于 Seastar 框架,首个公开版本                        │
│   ↓                                                          │
│ 2021   v21.x 系列,引入 Tiered Storage (S3 分层存储)           │
│        Redpanda Console (Web UI) 发布                        │
│   ↓                                                          │
│ 2022   v22.x 系列,Kafka API 兼容性大幅增强                   │
│        引入 rpk(原 rpk CLI)统一管理工具                       │
│        Schema Registry 内置(对比 Confluent 需独立部署)       │
│   ↓                                                          │
│ 2023   Vectorized 更名为 **Redpanda Data**                    │
│        完成 C 轮融资 1 亿美元                                  │
│   ↓                                                          │
│ 2024   v24.x 系列,Kafka Connect 全面 GA                     │
│        Iceberg/Parquet 集成,数据湖直写                        │
│   ↓                                                          │
│ 2025   v25.x 系列,无限保留 (Unlimited Retention)             │
│        Serverless 控制面 GA,BYOC (Bring Your Own Cloud)      │
│   ↓                                                          │
│ 2026   持续迭代,Serverless / Dedicated 全形态覆盖             │
└──────────────────────────────────────────────────────────────┘
```

### 1.3 创始人

| 创始人                       | 角色            | 背景                                                  |
| ---- | ---- | ---- |
| **Alexander Gallego**        | CEO / 首席架构师| 原 LinkedIn 资深工程师,深度参与 Kafka 内部优化        |
| **Alex & Meta-Team**        | 创始团队        | 多来自 ScyllaDB、Akamai、Confluent 等流式领域        |

> Redpanda 公司起源:**Alexander Gallego** 在 LinkedIn 任职期间,曾长期负责 Kafka 在公司内部的核心基础设施,亲眼目睹 JVM GC 在亿级流量下的尾延迟抖动问题,因此决定从底层重写一款"无 GC、高吞吐、低延迟"的流平台。

### 1.4 版本演进

| 版本      | 发布时间 | 主要特性                                                | 状态         |
| ---- | ---- | ---- | ---- |
| v20.x     | 2020     | 初始开源版本,核心 API                                  | 已淘汰      |
| v21.x     | 2021     | Tiered Storage (S3)                                    | 历史版本    |
| v22.x     | 2022     | Schema Registry 内置,rpk 工具完善                     | 历史版本    |
| v23.x     | 2023     | **Redpanda Console** GA、Kafka Connect 增强           | 历史版本    |
| **v24.x** | 2024     | **Iceberg 集成**、Parquet 数据湖直写                   | 推荐生产    |
| **v25.x** | 2025     | **Unlimited Retention**、Serverless 控制面            | **推荐生产**|
| v25.2+    | 2026     | BYOC Serverless GA、持续稳定性优化                    | 最新稳定    |

> **版本选择建议**:生产环境推荐 **v24.2+** 或 **v25.x**(架构稳定、生态完整)。新部署建议直接使用最新版,Redpanda 版本迭代比 Kafka 更激进,但**Kafka 协议兼容性**保持良好。

### 1.5 RedPanda 的特点

| 维度             | 说明                                                                            |
| ---- | ---- |
| **thread-per-core** | 每个 CPU 核心独占一个线程,**无锁、无上下文切换**,充分利用 NUMA 亲和性        |
| **无 GC**         | C++ 实现 + Seastar 框架,**无 JVM GC 停顿**,p99 延迟稳定                       |
| **单二进制**      | 启动文件 **就是 1 个 binary**,无需 ZooKeeper、JVM、外部服务依赖               |
| **Kafka 兼容**    | 100% 兼容 Kafka 协议,已有 Kafka 应用**零修改迁移**                            |
| **低延迟**        | p99 延迟 < 5ms,对比 Kafka 8-15ms 有数量级提升                                  |
| **高吞吐**        | 单节点可承载 **百万级 msg/s**(同配置下约为 Kafka 5-10 倍)                     |
| **持久化**        | 默认强制 `acks=all` + `raft`,写入即落盘                                       |
| **内置生态**      | 内置 **Schema Registry**、Admin API,**无需** Confluent 全家桶               |
| **运维简单**      | 无 ZK、无 JVM 调优、无 page cache 调优,**配置 + 重启** 即可                  |
| **资源效率**      | 相同吞吐量下,**CPU/内存占用约为 Kafka 的 1/3**                                |
| **Tiered Storage**| 原生支持 S3/GCS/Azure Blob 分层存储,**存储几乎无限**                        |
| **Iceberg**       | 直写 Apache Iceberg,**Kafka → 数据湖** 一键打通                              |

### 1.6 RedPanda 适用场景

```text
┌────────────────────────────────────────────────────────────────┐
│                      RedPanda 主要应用场景                      │
│                                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ 实时分析      │  │ 事件流       │  │ 低延迟交易   │         │
│  │ Real-time    │  │ Event Stream │  │ Trading /    │         │
│  │ Analytics    │  │              │  │ HFT          │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│                                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ IoT 边缘      │  │ CDC 变更捕获 │  │ 数据湖 ETL   │         │
│  │ IoT / Edge   │  │ CDC          │  │ Iceberg/Kafka│         │
│  │ Computing    │  │              │  │ → Lakehouse  │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└────────────────────────────────────────────────────────────────┘
```

- **实时分析**:金融行情、监控告警、风控决策,**毫秒级**响应
- **事件流 / 事件溯源**:微服务事件总线、领域事件,**无缝替换 Kafka**
- **低延迟交易**:证券、加密货币、游戏,**p99 < 5ms** 是核心优势
- **IoT / 边缘计算**:海量设备数据接入,**高吞吐** + **低资源占用** 适配边缘节点
- **CDC**:Debezium/MongoDB CDC → Redpanda → 数据仓库/数据湖
- **数据湖直写**:Redpanda → Iceberg/Parquet → S3,简化 ETL 链路
- **AI / LLM 实时管道**:向量流、模型推理日志、训练数据流式传输

---

## 二、与 Kafka 的核心差异对比

Redpanda **不是 Kafka 的简单升级**,而是从**底层架构**重做。这种重构不是为了"颠覆而颠覆",而是为了解决 Kafka 在大规模生产环境中**真实存在**的几个痛点:

1. **JVM GC 抖动**:Kafka 基于 Scala/Java,即使使用 G1/ZGC,在极端流量下仍可能出现几十毫秒甚至秒级的 stop-the-world,直接影响 p99/p999 延迟
2. **复杂的依赖拓扑**:KRaft 已经去掉了 ZooKeeper,但仍需独立 controller 进程、JDK、配置文件、Controller Quorum 等
3. **生态碎片化**:Schema Registry、Connect、REST Proxy 都是独立组件,由不同团队维护,部署复杂度高
4. **配置陈旧**:`server.properties`(Java Properties 格式)缺乏类型校验、嵌套结构、注释

Redpanda 的答案是:**用 C++ 重写一切,把生态组件内置,把配置现代化**。

| 维度 | Kafka (KRaft) | Redpanda | 差异说明 |
| ---- | ---- | ---- | ---- |
| **实现语言** | Scala / Java (JVM) | **C++** | Redpanda 摆脱 JVM GC |
| **线程模型** | 线程池 + 异步 | **thread-per-core** | Redpanda 每个核心一个线程,无锁 |
| **GC 行为** | **有 GC** (ZGC/G1 仍可能停顿) | **无 GC** | Redpanda p99 更稳定 |
| **元数据存储** | KRaft (内置 Raft) | **内置 Raft (RPK)** | 两者都去 ZK |
| **依赖服务** | 需 JDK 17+ | **无外部依赖** | Redpanda 单二进制即一切 |
| **配置文件** | `server.properties` | **YAML (`redpanda.yaml`)** | Redpanda 更现代化 |
| **管理工具** | `kafka-*.sh` 一堆脚本 | **`rpk`** (单一二进制) | rpk 体验远超 Kafka |
| **Schema Registry** | 需独立部署 (Confluent) | **内置** | Redpanda 开箱即用 |
| **Kafka Connect** | 独立部署 | **内置**(同二进制) | Redpanda 更轻量 |
| **Web UI** | 第三方 (AKHQ/Kafka UI) | **官方 Console** | 原生支持 |
| **单节点延迟** | p99 8-15ms | **p99 < 5ms** | 数量级提升 |
| **单节点吞吐** | 30-100 万 msg/s | **100-300 万 msg/s** | 5-10 倍 |
| **资源占用** | JVM 堆 + 页缓存 | **裸 C++** | Redpanda 占用更低 |
| **存储后端** | 本机磁盘 | 本机 + **Tiered Storage (S3)** | 内置分层 |
| **数据湖集成** | 间接 | **原生 Iceberg/Parquet** | 直写数据湖 |
| **客户端兼容** | 原生 | **100% Kafka 兼容** | Redpanda 客户端协议 |
| **License** | Apache 2.0 | **BSL (Business Source License)** | 自用/商用免费,云厂商分发受限 |

### 2.1 架构差异图

```text
┌─────────────────────────────┐    ┌─────────────────────────────┐
│      Apache Kafka           │    │        Redpanda             │
├─────────────────────────────┤    ├─────────────────────────────┤
│  ┌─────────────────────┐    │    │  ┌─────────────────────┐    │
│  │  Producer/Consumer  │    │    │  │  Producer/Consumer  │    │
│  │  (Kafka Protocol)   │    │    │  │  (Kafka Protocol)   │    │
│  └─────────────────────┘    │    │  └─────────────────────┘    │
│           ↕                 │    │           ↕                 │
│  ┌─────────────────────┐    │    │  ┌─────────────────────┐    │
│  │ Broker (JVM)        │    │    │  │ Redpanda (C++)       │    │
│  │  - NIO Threads      │    │    │  │  - thread-per-core   │    │
│  │  - Network Threads  │    │    │  │  - Seastar reactor   │    │
│  │  - IO Threads       │    │    │  │  - 内置 Raft         │    │
│  │  - GC 停顿           │    │    │  │  - 无 GC             │    │
│  └─────────────────────┘    │    │  └─────────────────────┘    │
│           ↕                 │    │           ↕                 │
│  ┌─────────────────────┐    │    │  ┌─────────────────────┐    │
│  │ KRaft Controller    │    │    │  │ 内置 RPK Consensus  │    │
│  │ (Raft)             │    │    │  │ (Raft,同进程)       │    │
│  └─────────────────────┘    │    │  └─────────────────────┘    │
│           ↕                 │    │           ↕                 │
│  ┌─────────────────────┐    │    │  ┌─────────────────────┐    │
│  │ 本机磁盘 (Page Cache)│    │    │  │ 本机 + S3 (Tiered)  │    │
│  └─────────────────────┘    │    │  └─────────────────────┘    │
└─────────────────────────────┘    └─────────────────────────────┘
```

### 2.2 性能差异(典型场景)

| 指标             | Kafka 3.7 (KRaft)        | Redpanda 25.x          |
| ---- | ---- | ---- |
| **p50 延迟**     | 2-5 ms                   | **0.5-2 ms**           |
| **p99 延迟**     | 8-15 ms                  | **< 5 ms**             |
| **p999 延迟**    | 50-100 ms                | **< 20 ms**            |
| **单节点吞吐**   | 50-100 万 msg/s          | **100-300 万 msg/s**   |
| **CPU 利用率**   | 中(JVM)                  | **高(thread-per-core)**|
| **内存占用**     | 4-8 GB (JVM 堆)          | **1-2 GB (无堆)**      |

> **结论**:Redpanda 是 **"对延迟敏感、对稳定性敏感、资源受限"** 场景的首选;若团队深度依赖 Kafka 生态(老版本 Kafka Streams、Confluent 商业组件),Kafka 仍是更稳妥的选择。

### 2.3 选型决策树

```text
┌──────────────────────────────────────────────────────────────┐
│              消息中间件选型决策树                              │
│                                                              │
│  你的场景是什么?                                             │
│  ├─ 业务消息、订单、复杂路由                                 │
│  │   └─→ RabbitMQ / RocketMQ                                │
│  ├─ 已有 Kafka 生态、深依赖 Confluent                        │
│  │   └─→ Kafka                                              │
│  ├─ 高吞吐 + 大数据 + 流处理 + CDC                           │
│  │   ├─ 团队熟悉 Kafka                                      │
│  │   │   └─→ Kafka                                          │
│  │   └─ 想要更简单 / 更低延迟 / 更少资源                     │
│  │       └─→ **Redpanda**                                   │
│  ├─ 强多租户 / 计算存储分离 / 跨地域                         │
│  │   └─→ Pulsar                                            │
│  └─ 延迟敏感(p99 < 5ms) / 边缘计算 / 资源受限              │
│      └─→ **Redpanda** (首选)                                │
└──────────────────────────────────────────────────────────────┘
```

### 2.4 迁移成本对比

| 迁移类型 | 工作量 | 风险 | 备注 |
| ---- | ---- | ---- | ---- |
| **Redpanda → Kafka** | ★★ | 低 | 协议兼容,客户端**几乎零改动** |
| **Kafka → Redpanda** | ★★ | 低 | 同上,客户端**几乎零改动** |
| **RabbitMQ → Kafka/Redpanda** | ★★★★ | 高 | 消息模型不同(Push → Pull),需业务改造 |
| **Pulsar → Kafka/Redpanda** | ★★★ | 中 | 协议差异,需调整客户端 |

> **好消息**:Kafka 与 Redpanda 之间**互相迁移成本极低**,因为 API 完全兼容。建议新项目直接用 Redpanda,已有 Kafka 项目**保留并评估**是否需要 Redpanda 的低延迟。

---

## 三、安装方式

Redpanda 安装方式比 Kafka **简洁得多**:**单二进制**,无 JVM、无 ZK。

### 3.1 安装前准备

#### 3.1.1 硬件要求

| 角色       | 最低     | 推荐生产      |
| ---- | ---- | ---- |
| CPU        | 2 核     | 8 核+ (推荐独立 NUMA) |
| 内存       | 2 GB     | 8 GB+        |
| 磁盘       | 50 GB    | NVMe SSD,TB 级 |
| 网络       | 1 Gbps   | 10 Gbps      |

> Redpanda 是 **CPU 密集型 + Disk 密集型** 应用,推荐使用 **NVMe SSD + 多核 CPU**,关闭超线程收益更大。

#### 3.1.2 软件要求

| 软件           | 要求                       | 说明                       |
| ---- | ---- | ---- |
| OS             | Linux (Ubuntu/RHEL/Debian) | macOS 仅供开发             |
| glibc          | 2.28+                      | CentOS 7 需升级 glibc      |
| 内核           | 4.18+                      | 支持 io_uring 更佳         |
| ulimit         | nofile ≥ 65536             | 文件描述符限制             |

```bash
# 查看 ulimit
ulimit -n
# 永久修改
echo "* soft nofile 65536" >> /etc/security/limits.conf
echo "* hard nofile 65536" >> /etc/security/limits.conf

# 查看 CPU 信息(确认 NUMA)
lscpu | grep -E 'NUMA|Core|Socket'
```

### 3.2 Linux 包安装 (apt/yum)

Redpanda 提供官方包,**一条命令**即可安装并启动。

#### 3.2.1 Ubuntu/Debian (apt)

```bash
# 1. 添加 Redpanda 仓库 GPG key
curl -1sLf 'https://packages.redpanda.com/gpg' | \
  gpg --dearmor -o /usr/share/keyrings/redpanda-keyring.gpg

# 2. 添加 apt 源
REPO="stable"
echo "deb [signed-by=/usr/share/keyrings/redpanda-keyring.gpg] \
  https://packages.redpanda.com/${REPO}/deb $(lsb_release -cs) main" | \
  tee /etc/apt/sources.list.d/redpanda.list

# 3. 更新源并安装
apt-get update
apt-get install -y redpanda

# 4. 验证安装
rpk version
# v25.x.y - 2026-xx-xx git_hash:xxx

# 5. 启动(后台模式)
systemctl start redpanda
systemctl enable redpanda
systemctl status redpanda
```

#### 3.2.2 RHEL/CentOS (yum/dnf)

```bash
# 1. 添加 yum 源
curl -1sLf 'https://packages.redpanda.com/gpg' | \
  gpg --dearmor -o /etc/pki/rpm-gpg/redpanda-keyring.gpg

cat > /etc/yum.repos.d/redpanda.repo <<EOF
[redpanda]
name=Redpanda
baseurl=https://packages.redpanda.com/stable/rpm
enabled=1
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/redpanda-keyring.gpg
repo_gpgcheck=0
EOF

# 2. 安装
dnf install -y redpanda

# 3. 启动
systemctl start redpanda
systemctl enable redpanda
```

### 3.3 Docker / Docker Compose

#### 3.3.1 Docker 单机

```bash
# 1. 拉取镜像
docker pull redpandadata/redpanda:v25.2.1

# 2. 启动容器(开发模式,自动创建集群)
docker run -d --name=redpanda \
  -p 9092:9092 -p 9644:9644 \
  -v /var/lib/redpanda:/var/lib/redpanda/data \
  redpandadata/redpanda:v25.2.1 \
  redpanda start \
    --overprovisioned \
    --smp 1 \
    --memory 1G \
    --reserve-memory 0 \
    --node-id 0 \
    --check=false

# 3. 测试
docker exec -it redpanda rpk topic create test
docker exec -it redpanda rpk topic produce test <<< "Hello Redpanda"
docker exec -it redpanda rpk topic consume test --num 1
```

#### 3.3.2 Docker Compose 集群部署

```yaml
# docker-compose.yml
# 3 节点 Redpanda 集群 + Console (Web UI)
version: '3.8'
services:
  redpanda-0:
    image: redpandadata/redpanda:v25.2.1
    container_name: redpanda-0
    command:
      - redpanda
      - start
      - --overprovisioned
      - --smp=1
      - --memory=1G
      - --reserve-memory=0
      - --node-id=0
      - --seeds= redpanda-0:33145, redpanda-1:33145, redpanda-2:33145
      - --rpc-addr=0.0.0.0:33145
      - --kafka-addr=PLAINTEXT://0.0.0.0:9092
      - --advertise-kafka-addr=PLAINTEXT://redpanda-0:9092
      - --advertise-rpc-addr=redpanda-0:33145
      - --check=false
    ports:
      - "9092:9092"   # Kafka API
      - "9644:9644"   # Admin API
    volumes:
      - redpanda0_data:/var/lib/redpanda/data
    healthcheck:
      test: ["CMD", "rpk", "cluster", "info"]
      interval: 5s
      timeout: 3s
      retries: 10

  redpanda-1:
    image: redpandadata/redpanda:v25.2.1
    container_name: redpanda-1
    command:
      - redpanda
      - start
      - --overprovisioned
      - --smp=1
      - --memory=1G
      - --reserve-memory=0
      - --node-id=1
      - --seeds= redpanda-0:33145, redpanda-1:33145, redpanda-2:33145
      - --rpc-addr=0.0.0.0:33145
      - --kafka-addr=PLAINTEXT://0.0.0.0:9092
      - --advertise-kafka-addr=PLAINTEXT://redpanda-1:9092
      - --advertise-rpc-addr=redpanda-1:33145
      - --check=false
    volumes:
      - redpanda1_data:/var/lib/redpanda/data

  redpanda-2:
    image: redpandadata/redpanda:v25.2.1
    container_name: redpanda-2
    command:
      - redpanda
      - start
      - --overprovisioned
      - --smp=1
      - --memory=1G
      - --reserve-memory=0
      - --node-id=2
      - --seeds= redpanda-0:33145, redpanda-1:33145, redpanda-2:33145
      - --rpc-addr=0.0.0.0:33145
      - --kafka-addr=PLAINTEXT://0.0.0.0:9092
      - --advertise-kafka-addr=PLAINTEXT://redpanda-2:9092
      - --advertise-rpc-addr=redpanda-2:33145
      - --check=false
    volumes:
      - redpanda2_data:/var/lib/redpanda/data

  console:
    image: redpandadata/console:v3.x.x
    container_name: redpanda-console
    depends_on:
      redpanda-0:
        condition: service_healthy
    ports:
      - "8080:8080"
    environment:
      CONFIG_FILEPATH: /etc/console/config.yml
    volumes:
      - ./console-config.yml:/etc/console/config.yml

volumes:
  redpanda0_data:
  redpanda1_data:
  redpanda2_data:
```

```yaml
# console-config.yml
console:
  kafka:
    brokers:
      - redpanda-0:9092
      - redpanda-1:9092
      - redpanda-2:9092
  schemaRegistry:
    enabled: true
    urls:
      - http://redpanda-0:8081
```

```bash
# 启动
docker compose up -d
docker compose logs -f redpanda-0

# 验证
docker exec -it redpanda-0 rpk cluster info

# 访问 Console: http://localhost:8080
```

### 3.4 Kubernetes Operator / Helm Chart

#### 3.4.1 Helm Chart 部署

```bash
# 1. 添加 Redpanda Helm 仓库
helm repo add redpanda https://charts.redpanda.com
helm repo update

# 2. 创建命名空间
kubectl create namespace redpanda

# 3. 安装(使用默认配置)
helm install redpanda redpanda/redpanda \
  --namespace redpanda \
  --set statefulset.replicas=3 \
  --set resources.cpu.cores=2 \
  --set resources.memory.container.max=4Gi

# 4. 查看状态
kubectl -n redpanda get pods
kubectl -n redpanda get svc
```

#### 3.4.2 Redpanda Operator (生产推荐)

```bash
# 1. 安装 Operator
kubectl apply -k 'https://github.com/redpanda-data/redpanda-operator/src/go/k8s/config/crd?ref=v2.3.x'

# 2. 创建 Redpanda Cluster CR
cat > redpanda-cluster.yaml <<EOF
apiVersion: cluster.redpanda.com/v1alpha2
kind: Redpanda
metadata:
  name: redpanda
  namespace: redpanda
spec:
  clusterSpec:
    image: redpandadata/redpanda:v25.2.1
    replicas: 3
    resources:
      cpu:
        cores: 4
      memory:
        container:
          max: 8Gi
    storage:
      capacity: 100Gi
      storageClassName: gp3
    config:
      kafka_api:
        - address: 0.0.0.0:9092
          port: 9092
          name: kafka
      rpc_api:
        - address: 0.0.0.0:33145
          port: 33145
          name: rpc
      admin:
        - address: 0.0.0.0:9644
          port: 9644
          name: admin
EOF

kubectl apply -f redpanda-cluster.yaml

# 3. 查看状态
kubectl -n redpanda get redpanda
kubectl -n redpanda get pods
```

### 3.5 macOS brew

```bash
# 1. 安装 brew tap
brew install redpanda-data/tap/redpanda

# 2. 启动(开发用,单节点)
rpk redpanda start --overprovisioned --smp 1 --memory 1G

# 3. 查看状态
rpk cluster info

# 4. 停止
rpk redpanda stop
```

### 3.6 安装方式对比

| 方式             | 难度 | 适用场景                       | 推荐度     |
| ---- | ---- | ---- | ---- |
| **apt/yum 包**   | ★    | **Linux 生产首选**             | ★★★★★      |
| **Docker**       | ★    | 开发、CI、测试                 | ★★★★       |
| **Docker Compose** | ★★  | 多节点开发、PoC                | ★★★★       |
| **Helm Chart**   | ★★★  | **K8s 部署**(中小规模)         | ★★★★       |
| **Operator**     | ★★★★  | **K8s 生产推荐**(大规模)       | ★★★★★      |
| **brew (macOS)** | ★    | 本地开发                       | ★★★        |

### 3.7 Kafka vs Redpanda 启动方式对比表

| 维度 | Kafka | Redpanda |
| ---- | ---- | ---- |
| **部署二进制数** | 1 个 broker + 1 个 controller(KRaft)| **1 个二进制**(同时承担 broker + controller) |
| **JVM 依赖** | 必须 JDK 17+ | **无** |
| **ZooKeeper** | 已废弃(KRaft 替代) | **无** |
| **KRaft** | 独立 controller 进程 | **内置** |
| **初始化步骤** | `kafka-storage.sh format` | **无需格式化** |
| **配置文件** | `server.properties`(properties 格式) | `redpanda.yaml`(YAML 格式) |
| **启动命令** | `bin/kafka-server-start.sh -daemon ...` | `rpk redpanda start` 或 `systemctl start redpanda` |
| **健康检查** | 依赖 JMX + ZK 心跳 | `rpk cluster health` / `curl :9644/public_metrics` |
| **管理工具** | `kafka-topics.sh` 等 20+ 个脚本 | **`rpk`(单一二进制,统一管理)** |
| **容器启动** | 需配置 KAFKA_* 环境变量 | **一行 `redpanda start --smp=1`** |
| **首次启动** | 必须指定 cluster.id | **自动生成 cluster.id** |
| **热加载配置** | 部分支持 | **部分支持** |
| **systemd** | 需自写 unit | **官方已提供 unit** |

---

## 四、单节点启动

### 4.1 最简启动 (开发模式)

```bash
# 1. 一行命令启动(单节点开发模式)
rpk redpanda start \
  --overprovisioned \
  --smp 1 \
  --memory 1G \
  --reserve-memory 0 \
  --node-id 0 \
  --check=false

# 参数说明:
# --overprovisioned      开发/容器环境用,关闭部分资源校验
# --smp 1                使用 1 个 CPU 核心
# --memory 1G            限制内存为 1 GB
# --reserve-memory 0     不预留系统内存
# --node-id 0            节点 ID(单机为 0)
# --check=false          跳过启动前校验
```

### 4.2 后台启动 (生产模式)

```bash
# 1. 创建配置文件
cat > /etc/redpanda/redpanda.yaml <<'EOF'
redpanda:
  data_directory: /var/lib/redpanda/data
  empty_seed_starts_cluster: true
  seed_servers:
    - host:
        address: 127.0.0.1
        port: 33145
      node_id: 0
  kafka_api:
    - address: 0.0.0.0
      port: 9092
      name: kafka
  rpc_api:
    - address: 0.0.0.0
      port: 33145
      name: rpc
  admin:
    - address: 0.0.0.0
      port: 9644
      name: admin
EOF

# 2. 启动
rpk redpanda start

# 或使用 systemd
systemctl start redpanda
systemctl status redpanda

# 3. 查看日志
journalctl -u redpanda -f
# 或
tail -f /var/log/redpanda/redpanda.log
```

### 4.3 启动流程

```text
┌──────────────────────────────────────────────────────────────┐
│                Redpanda 启动流程                              │
│                                                              │
│  1. 解析 redpanda.yaml(CLI 参数覆盖)                         │
│        ↓                                                      │
│  2. 初始化 thread-per-core reactor 线程池                     │
│        ↓                                                      │
│  3. 启动 RPC 服务(:33145) 节点间通信                         │
│        ↓                                                      │
│  4. 加入/创建 Raft 集群                                       │
│        ↓                                                      │
│  5. 启动 Admin API (:9644)                                   │
│        ↓                                                      │
│  6. 启动 Kafka API (:9092)                                   │
│        ↓                                                      │
│  7. 注册 Schema Registry (内置,可选)                         │
│        ↓                                                      │
│  8. 状态上报为 "alive"                                        │
└──────────────────────────────────────────────────────────────┘
```

### 4.4 验证启动

```bash
# 1. 查看集群信息
rpk cluster info
# 输出:
# CLUSTER
# =======
# redpanda.3195e893...    # cluster_id(自动生成)
#
# BROTHERS (1)
# ========
# 0: redpanda-0  127.0.0.1:9092

# 2. 健康检查
rpk cluster health
# 输出:
# CLUSTER HEALTH
# ==============
# Connected: true
# Controller: 0
# Healthy: 0
# Uptime: 1234

# 3. 创建 topic
rpk topic create test -p 1 -r 1
# TOPIC   PARTITIONS  REPLICAS
# test    1           1

# 4. 生产一条消息
echo "Hello Redpanda" | rpk topic produce test

# 5. 消费消息
rpk topic consume test --num 1
# Hello Redpanda
```

### 4.5 优雅停止

```bash
# 方式 1:systemctl(生产推荐)
systemctl stop redpanda

# 方式 2:rpk
rpk redpanda stop

# 方式 3:发送 SIGTERM(开发调试)
kill -TERM <pid>
```

---

## 五、集群部署

### 5.1 节点规划

```text
┌─────────────────────────────────────────────────────────────┐
│              Redpanda 集群 (3 节点)                          │
│                                                             │
│   节点 1                节点 2                节点 3        │
│   redpanda-1            redpanda-2            redpanda-3    │
│   10.0.0.11             10.0.0.12             10.0.0.13     │
│                                                             │
│   - Kafka API  :9092    - Kafka API  :9092    - Kafka API  :9092
│   - RPC API    :33145   - RPC API    :33145   - RPC API    :33145
│   - Admin API  :9644    - Admin API  :9644    - Admin API  :9644
│                                                             │
│   seed_servers:                                            │
│   - 0@10.0.0.11:33145                                     │
│   - 1@10.0.0.12:33145                                     │
│   - 2@10.0.0.13:33145                                     │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 准备节点

```bash
# 在所有节点执行
# 1. 安装 redpanda(参见 3.2 节)
apt-get install -y redpanda

# 2. 配置 ulimit
echo "* soft nofile 65536" >> /etc/security/limits.conf
echo "* hard nofile 65536" >> /etc/security/limits.conf

# 3. 创建数据目录
mkdir -p /var/lib/redpanda/data
chown -R redpanda:redpanda /var/lib/redpanda
```

### 5.3 配置 seed servers

#### 5.3.1 节点 1 (10.0.0.11)

```bash
cat > /etc/redpanda/redpanda.yaml <<'EOF'
redpanda:
  data_directory: /var/lib/redpanda/data
  empty_seed_starts_cluster: true        # 空集群允许自启(仅节点 1)
  seed_servers:
    - host:
        address: 10.0.0.11
        port: 33145
      node_id: 0
    - host:
        address: 10.0.0.12
        port: 33145
      node_id: 1
    - host:
        address: 10.0.0.13
        port: 33145
      node_id: 2
  kafka_api:
    - address: 0.0.0.0
      port: 9092
      name: kafka
      advertised_addresses:
        - 10.0.0.11:9092
  rpc_api:
    - address: 0.0.0.0
      port: 33145
      name: rpc
      advertised_addresses:
        - 10.0.0.11:33145
  admin:
    - address: 0.0.0.0
      port: 9644
      name: admin
EOF
```

#### 5.3.2 节点 2 (10.0.0.12)

```bash
cat > /etc/redpanda/redpanda.yaml <<'EOF'
redpanda:
  data_directory: /var/lib/redpanda/data
  empty_seed_starts_cluster: false        # 已有节点 1
  seed_servers:
    - host:
        address: 10.0.0.11
        port: 33145
      node_id: 0
    - host:
        address: 10.0.0.12
        port: 33145
      node_id: 1
    - host:
        address: 10.0.0.13
        port: 33145
      node_id: 2
  kafka_api:
    - address: 0.0.0.0
      port: 9092
      name: kafka
      advertised_addresses:
        - 10.0.0.12:9092
  rpc_api:
    - address: 0.0.0.0
      port: 33145
      name: rpc
      advertised_addresses:
        - 10.0.0.12:33145
  admin:
    - address: 0.0.0.0
      port: 9644
      name: admin
EOF
```

#### 5.3.3 节点 3 (10.0.0.13)

只需修改 `node_id: 2` 和 `advertised_addresses` 中的 IP,其余同节点 2。

### 5.4 启动集群

```bash
# 推荐顺序启动:节点 1(初始化集群)→ 节点 2 → 节点 3

# 节点 1(初始化)
ssh root@10.0.0.11 "systemctl start redpanda"
# 等待 30 秒,观察日志

# 节点 2
ssh root@10.0.0.12 "systemctl start redpanda"

# 节点 3
ssh root@10.0.0.13 "systemctl start redpanda"

# 在任一节点验证集群
rpk cluster info
# 输出:
# CLUSTER
# =======
# redpanda.3195e893...
#
# BROTHERS (3)
# ========
# 0: redpanda-1   10.0.0.11:9092
# 1: redpanda-2   10.0.0.12:9092
# 2: redpanda-3   10.0.0.13:9092

# 创建测试 topic(3 副本)
rpk topic create test -p 6 -r 3

# 验证分区分布
rpk topic describe test
```

### 5.5 集群扩容(增加节点)

集群运行一段时间后,需要扩容怎么办?Redpanda 的扩容**比 Kafka 更简单**——只需在 seed_servers 中加入新节点,然后启动它即可。

```bash
# 1. 在新节点(节点 4,10.0.0.14)上安装 redpanda
ssh root@10.0.0.14 "apt-get install -y redpanda"

# 2. 配置 redpanda.yaml
ssh root@10.0.0.14 "cat > /etc/redpanda/redpanda.yaml <<'EOF'
redpanda:
  data_directory: /var/lib/redpanda/data
  empty_seed_starts_cluster: false
  seed_servers:
    - host: { address: 10.0.0.11, port: 33145 }
      node_id: 0
    - host: { address: 10.0.0.12, port: 33145 }
      node_id: 1
    - host: { address: 10.0.0.13, port: 33145 }
      node_id: 2
    - host: { address: 10.0.0.14, port: 33145 }      # 新增
      node_id: 3                                       # 新增
  kafka_api:
    - address: 0.0.0.0
      port: 9092
      name: kafka
      advertised_addresses: [10.0.0.14:9092]
  rpc_api:
    - address: 0.0.0.0
      port: 33145
      name: rpc
      advertised_addresses: [10.0.0.14:33145]
  admin:
    - address: 0.0.0.0
      port: 9644
      name: admin
EOF"

# 3. 在所有现有节点上加入新 seed(以便重启后能感知到)
# (修改节点 1/2/3 的 redpanda.yaml,在末尾加入新节点 4)
# 然后滚动重启现有节点,或等待下次重启

# 4. 启动新节点
ssh root@10.0.0.14 "systemctl start redpanda"

# 5. 验证新节点已加入
rpk cluster info
# 输出 4 个 BROTHERS
```

> **注意**:**新节点加入后,Redpanda 会自动把现有分区重新平衡到新节点**(类似 Kafka 的 rebalance)。这个过程**无需人工介入**,且可以在线进行。

### 5.6 集群缩容(移除节点)

```bash
# 1. 优雅下线节点 3
ssh root@10.0.0.13 "systemctl stop redpanda"

# 2. Redpanda 会自动把该节点上的 partition leader 转移到其他节点
#    这个过程需要几秒到几分钟,取决于分区数

# 3. 验证节点已移除
rpk cluster info
# 应该显示 2 个 BROTHERS

# 4. (可选)清理数据目录
ssh root@10.0.0.13 "rm -rf /var/lib/redpanda/data/*"

# 5. 在其他节点的 redpanda.yaml 中删除该 seed
#    并滚动重启
```

### 5.7 集群部署最佳实践

| 实践 | 说明 |
| ---- | ---- |
| **3 节点起步** | 容忍 1 节点故障,最小生产配置 |
| **5 节点更佳** | 容忍 2 节点故障,适合关键业务 |
| **节点规格统一** | 避免大小节点混部,影响分区平衡 |
| **节点分布在不同 AZ** | 跨可用区部署,容忍机房故障 |
| **预留 25% 内存** | `reserve_memory: 25%`,留给系统缓存 |
| **开启 NUMA 感知** | `numa_aware: true`,减少跨 NUMA 内存访问 |
| **关闭超线程** | Redpanda 文档推荐关闭 HT,提升单核性能 |
| **使用 NVMe SSD** | 磁盘 IO 是常见瓶颈,NVMe 比 SATA 高 10 倍 |
| **升级内核** | 内核 5.x+ 性能更好,支持 io_uring |

---

## 六、rpk CLI 工具详解

**rpk**(Redpanda Keeper)是 Redpanda **统一的命令行管理工具**,**替代 Kafka 的 20+ 个 `kafka-*.sh` 脚本**。

### 6.1 rpk 总览

| 子命令              | 作用                                | 替代 Kafka 工具                  |
| ---- | ---- | ---- |
| `rpk cluster`       | 集群管理(info/health/...)          | `kafka-metadata-quorum.sh` 等   |
| `rpk topic`         | Topic 管理                          | `kafka-topics.sh`               |
| `rpk redpanda`      | Redpanda 服务启停                   | `kafka-server-start.sh`         |
| `rpk acl`           | ACL 权限管理                        | `kafka-acls.sh`                 |
| `rpk security`      | 安全相关(user/cert/SASL)            | `kafka-configs.sh` 等          |
| `rpk connect`       | Kafka Connect 管理                  | `connect-standalone.sh`        |
| `rpk group`         | 消费者组管理                        | `kafka-consumer-groups.sh`     |
| `rpk generate`      | 生成测试负载                        | `kafka-producer-perf-test.sh`  |
| `rpk plugin`        | 插件管理                            | (Kafka 无)                      |
| `rpk status`        | 集群状态总览                        | (Kafka 无)                      |

### 6.2 rpk cluster

```bash
# 1. 集群信息
rpk cluster info
# CLUSTER
# =======
# redpanda.3195e893...
# BROTHERS (3) ...

# 2. 集群健康
rpk cluster health
# Connected: true
# Controller: 0
# Healthy: 0/0/1/2

# 3. 集群元数据
rpk cluster metadata
# brokers, topics, controller 等

# 4. 集群配置
rpk cluster config get
rpk cluster config get log_segment_size

# 5. 修改配置(动态生效)
rpk cluster config set log_segment_size 134217728

# 6. 查看日志
rpk redpanda log --help
```

### 6.3 rpk topic

```bash
# 1. 创建 topic
rpk topic create my-topic --partitions 6 --replicas 3

# 2. 创建带配置 topic
rpk topic create my-topic \
  --partitions 6 --replicas 3 \
  --config retention.ms=604800000 \
  --config cleanup.policy=compact

# 3. 列出 topic
rpk topic list

# 4. 查看 topic 详情
rpk topic describe my-topic

# 5. 增加分区(只能增加)
rpk topic alter my-topic --partitions 12

# 6. 修改 topic 配置
rpk topic alter-config my-topic --set retention.ms=259200000

# 7. 删除 topic
rpk topic delete my-topic

# 8. 生产消息(交互式)
rpk topic produce my-topic
# 输入消息,Ctrl+D 退出
> hello
> redpanda
> [Ctrl+D]

# 9. 生产消息(管道)
echo "Hello Redpanda" | rpk topic produce my-topic
cat data.txt | rpk topic produce my-topic

# 10. 消费消息
rpk topic consume my-topic --num 10
# 默认从头开始消费(--offset start / --offset end)

# 11. 带 key 生产
rpk topic produce my-topic -k
# 输入格式: key<TAB>value

# 12. 消费指定 topic + group
rpk topic consume my-topic --group test-group --num 100

# 13. 带 Schema 验证(Schema Registry)
rpk topic produce my-topic --schema my-schema.proto
```

### 6.4 rpk redpanda

```bash
# 1. 启动 Redpanda(前台)
rpk redpanda start

# 2. 启动(后台模式)
rpk redpanda start --daemon

# 3. 停止
rpk redpanda stop

# 4. 重启
rpk redpanda restart

# 5. 查看版本
rpk redpanda version
# v25.2.1 - 2026-xx-xx

# 6. 查看配置
rpk redpanda config print
rpk redpanda config set redpanda.kafka_api.port 9092

# 7. 查看状态
rpk redpanda status

# 8. 升级检查
rpk redpanda upgrade --check
```

### 6.5 rpk acl

```bash
# 1. 创建 ACL
rpk acl create --allow-principal User:alice \
  --operation read,write \
  --topic my-topic

# 2. 列出 ACL
rpk acl list

# 3. 删除 ACL
rpk acl delete --allow-principal User:alice \
  --operation read,write \
  --topic my-topic

# 4. 创建 Service Account
rpk acl user create alice --password 'secret'

# 5. 查看权限
rpk acl user list
```

### 6.6 rpk security

```bash
# 1. 创建 SASL 用户
rpk security user create alice --password 'secret'

# 2. 启用 SASL
rpk cluster config set sasl_enabled_mechanisms SCRAM-SHA-256

# 3. 生成证书(内部 CA)
rpk security cert generate --self-signed

# 4. 列出证书
rpk security cert list
```

### 6.7 rpk connect

```bash
# 1. 创建 connector(从 YAML 配置)
rpk connect connector create --config <(echo '
name: my-connector
config:
  connector.class: PostgresSource
  database.hostname: postgres
  database.port: 5432
  database.user: postgres
  database.password: secret
  database.dbname: mydb
  table.whitelist: orders
  topic.prefix: cdc_
')

# 2. 列出 connector
rpk connect connector list

# 3. 查看状态
rpk connect connector status my-connector

# 4. 暂停/恢复
rpk connect connector pause my-connector
rpk connect connector resume my-connector

# 5. 删除 connector
rpk connect connector delete my-connector

# 6. 创建 Secret(SASL 凭证)
rpk connect secret create db-password --secret-secret secret
```

### 6.8 rpk group (消费者组)

```bash
# 1. 列出所有消费者组
rpk group list

# 2. 查看消费者组 lag
rpk group describe test-group
# 输出: partitions / lag / offset / log-end-offset

# 3. 重置 offset
rpk group seek test-group --to start
rpk group seek test-group --to end
rpk group seek test-group --to 1000
rpk group seek test-group --to 2024-01-01T00:00:00Z

# 4. 删除消费者组
rpk group delete test-group
```

### 6.9 rpk generate (压测)

```bash
# 1. 生产压测:100 万条,1KB
rpk generate produce \
  --topic perf-test \
  --num-records 1000000 \
  --record-size 1024 \
  --throughput 100000

# 2. 消费压测
rpk generate consume \
  --topic perf-test \
  --num-records 1000000
```

---

## 七、redpanda.yaml 配置文件详解

### 7.1 完整配置示例 (生产环境 3 节点)

```yaml
# ============================================
# /etc/redpanda/redpanda.yaml
# Redpanda v25.x 生产配置 (3 节点)
# ============================================

redpanda:
  # ==================== 节点标识 ====================
  # 数据目录(必须预先创建)
  data_directory: /var/lib/redpanda/data

  # 节点唯一 ID(集群内唯一,0~255)
  node_id: 0

  # 集群 ID(自动生成,首次启动后持久化到 data_directory)
  cluster_id: "redpanda.3195e8938e3b4f1c9a0b..."

  # 空集群自启(节点 1=true,其他=false)
  empty_seed_starts_cluster: true

  # ==================== Seed Servers ====================
  # 集群所有种子节点列表
  seed_servers:
    - host:
        address: 10.0.0.11
        port: 33145
      node_id: 0
    - host:
        address: 10.0.0.12
        port: 33145
      node_id: 1
    - host:
        address: 10.0.0.13
        port: 33145
      node_id: 2

  # ==================== Kafka API ====================
  # 对外提供 Kafka 协议服务(生产者/消费者连接)
  kafka_api:
    - address: 0.0.0.0
      port: 9092
      name: kafka
      advertised_addresses:
        - 10.0.0.11:9092       # 必须让客户端能访问到
      authentication_method: sasl               # 可选: none / sasl
      name: kafka

  # ==================== RPC API ====================
  # 内部 Raft 节点间通信
  rpc_api:
    - address: 0.0.0.0
      port: 33145
      name: rpc
      advertised_addresses:
        - 10.0.0.11:33145

  # ==================== Admin API ====================
  # 管理 API(HTTP,监控/管理用)
  admin:
    - address: 0.0.0.0
      port: 9644
      name: admin
      advertised_addresses:
        - 10.0.0.11:9644

  # ==================== Coprocessor API ====================
  # WASM coprocessor 接口(可选)
  coproc_api:
    - address: 0.0.0.0
      port: 43189
      name: coproc

  # ==================== Schema Registry ====================
  # 内置 Schema Registry(默认端口 8081)
  schema_registry_api:
    - address: 0.0.0.0
      port: 8081
      name: schema_registry
      advertised_addresses:
        - 10.0.0.11:8081

  # ==================== HTTP Proxy (Pandaproxy) ====================
  # REST Proxy + Admin API 兼容
  pandaproxy_api:
    - address: 0.0.0.0
      port: 8082
      name: pandaproxy
      advertised_addresses:
        - 10.0.0.11:8082

  # ==================== 资源限制 ====================
  # thread-per-core 调优
  resource_limits:
    # 期望每个 CPU 核心分配的内存
    memory_per_cpu: 2GB
    # 预留内存给系统(建议总内存的 25%)
    reserve_memory: 1073741824
    # 是否开启 NUMA 感知
    numa_aware: true
    # 协程调度队列深度
    cpu_quota: 1.0
    # 磁盘 IO 带宽限制(字节)
    disk_idle_timeout: 1000

  # ==================== 分区/副本 ====================
  # 默认分区数(自动创建 topic 时使用)
  default_topic_partitions: 3

  # 默认副本数
  default_topic_replications: 3

  # ==================== 日志 ====================
  # 单个日志段大小(默认 128 MB)
  log_segment_size: 134217728

  # 日志段删除检查间隔
  log_segment_ms: 600000000  # 默认 10 分钟

  # 消息保留时间(默认 7 天)
  log_retention_ms: 604800000

  # 分区最大字节数(默认 -1 不限)
  log_storage_max_size: -1

  # ==================== 复制/共识 ====================
  # 副本拉取超时
  raft_heartbeat_interval_ms: 150

  # 选举超时
  raft_election_timeout_ms: 1500

  # 副本拉取最大字节数
  raft_replicate_batch_window_size: 65536

  # ==================== 安全 ====================
  # 启用 SASL
  sasl_enabled_mechanisms: ["SCRAM-SHA-256", "SCRAM-SHA-512"]

  # TLS 配置(可选)
  kafka_api_tls:
    - name: kafka
      enabled: false
      cert_file: /etc/redpanda/certs/cert.pem
      key_file: /etc/redpanda/certs/key.pem
      require_client_auth: false

  # ==================== Tiered Storage ====================
  # 启用 S3 分层存储
  cloud_storage_enabled: true
  cloud_storage_bucket: redpanda-tiered-storage
  cloud_storage_region: us-east-1
  cloud_storage_access_key: YOUR_ACCESS_KEY
  cloud_storage_secret_key: YOUR_SECRET_KEY
  cloud_storage_api_endpoint: s3.amazonaws.com
  cloud_storage_trust_file: /etc/redpanda/certs/ca-cert.pem
  cloud_storage_reconciliation_interval_ms: 10000

  # 远程存储起始偏移(segment 滚动 N 个后才上传)
  cloud_storage_segment_size: 134217728
  cloud_storage_archive_max_segments: 5

  # ==================== 优化 ====================
  # 启用 Iceberg 集成
  iceberg_enabled: false

  # Admin API 限制
  admin_api_require_auth: false

  # 内核参数(自动调优)
  tune_aio_events: true
  tune_clocksource: true
  tune_cpu: true
  tune_disk_irq: true
  tune_disk_nomerges: true
  tune_disk_scheduler: true
  tune_disk_write_cache: true
  tune_ena: true
  tune_network: true
  tune_swappiness: true
  tune_transparent_hugepages: true
  tune_virtual_memory: true

  # 关闭自动调优(容器环境)
  tune_disk: false
```

### 7.2 关键参数详解

| 参数                              | 作用                          | 推荐值            |
| ---- | ---- | ---- |
| `data_directory`                  | 数据目录                      | `/var/lib/redpanda/data` |
| `node_id`                         | 节点 ID(集群内唯一)         | 0/1/2            |
| `empty_seed_starts_cluster`       | 空集群自启(仅种子节点)      | true (节点 1)     |
| `seed_servers`                    | 集群种子节点列表              | 3 个节点          |
| `kafka_api`                       | Kafka 协议服务端口            | 9092             |
| `rpc_api`                         | 内部 Raft 通信端口            | 33145            |
| `admin`                           | 管理 API                      | 9644             |
| `schema_registry_api`             | Schema Registry 端口          | 8081             |
| `pandaproxy_api`                  | REST Proxy                    | 8082             |
| `default_topic_partitions`        | 自动建 topic 默认分区数       | 3                |
| `default_topic_replications`      | 自动建 topic 默认副本数       | 3                |
| `log_segment_size`                | 日志段大小                    | 128 MB           |
| `log_retention_ms`                | 消息保留时间                  | 7 天(604800000)|
| `resource_limits.memory_per_cpu`  | 每核心内存                    | 2 GB             |
| `resource_limits.reserve_memory`  | 预留系统内存                  | 总内存 25%       |
| `cloud_storage_enabled`           | 启用分层存储                  | true (TB 级数据) |
| `sasl_enabled_mechanisms`         | SASL 机制                     | SCRAM-SHA-256    |

### 7.3 配置加载优先级

```text
┌────────────────────────────────────────┐
│ 配置优先级(高 → 低)                    │
├────────────────────────────────────────┤
│ 1. CLI 参数(如 rpk redpanda start --smp=4)│
│ 2. 环境变量(REDPANDA_* 前缀)            │
│ 3. /etc/redpanda/redpanda.yaml         │
│ 4. /etc/redpanda/config.yaml           │
│ 5. 默认值                              │
└────────────────────────────────────────┘
```

```bash
# 示例:CLI 覆盖
rpk redpanda start --node-id 0 --smp 4 --memory 4G

# 示例:环境变量
export REDPANDA_NODE_ID=0
export REDPANDA_DATA_DIRECTORY=/var/lib/redpanda/data
rpk redpanda start
```

### 7.4 关键参数调优建议

不同业务场景下,`redpanda.yaml` 的关键参数推荐值不同。下表给出几个常见场景的**推荐组合**:

#### 高吞吐场景(每秒百万级消息)

```yaml
redpanda:
  resource_limits:
    memory_per_cpu: 4GB          # 每核心 4GB 内存
    reserve_memory: 1073741824
    numa_aware: true
  log_segment_size: 268435456   # 256 MB 段,减少段切换
  kafka_batch_max_bytes: 1048576  # 1 MB 批量
  kafka_batch_min_bytes: 1024   # 最小批量 1KB
```

#### 低延迟场景(p99 < 5ms)

```yaml
redpanda:
  resource_limits:
    memory_per_cpu: 2GB
    numa_aware: true
  log_segment_size: 134217728   # 128 MB 段,适中
  raft_heartbeat_interval_ms: 100  # 更短心跳,更快响应
```

#### 大容量场景(TB 级数据)

```yaml
redpanda:
  cloud_storage_enabled: true
  cloud_storage_bucket: redpanda-tiered
  cloud_storage_segment_size: 268435456
  cloud_storage_archive_max_segments: 3
  log_storage_max_size: -1      # 不限制本地大小,数据主要在 S3
```

### 7.5 常见配置错误

| 错误配置 | 后果 | 正确做法 |
| ---- | ---- | ---- |
| `empty_seed_starts_cluster: true`(所有节点) | 集群初始化冲突 | 仅**首节点**为 true,其他为 false |
| `kafka_api.advertised_addresses` 填 `0.0.0.0` 或 `localhost` | 客户端连不上 | 填**实际可路由的 IP 或域名** |
| `seed_servers` 用 `localhost` | 多节点无法互联 | 填**真实 IP 地址** |
| `node_id` 重复 | 节点冲突,无法加入集群 | 集群内**严格唯一** |
| `data_directory` 权限不足 | 启动失败 | `chown redpanda:redpanda` |
| 容器内忘记加 `--overprovisioned` | 资源校验失败 | 容器环境**必须加** |

---

## 八、Redpanda Console (Web UI)

**Redpanda Console**(原 Redpanda Admin UI)是**官方提供的 Web 管理界面**,**无需额外安装**,功能远比第三方 Kafka UI 完善。

### 8.1 部署 Console

#### 8.1.1 Docker 部署

```bash
# 1. 拉取镜像
docker pull redpandadata/console:v3.x.x

# 2. 启动
docker run -d --name=redpanda-console \
  -p 8080:8080 \
  -e KAFKA_BROKERS=redpanda-1:9092,redpanda-2:9092,redpanda-3:9092 \
  -e KAFKA_SCHEMAREGISTRY_URL=http://redpanda-1:8081 \
  redpandadata/console:v3.x.x

# 3. 访问:http://localhost:8080
```

#### 8.1.2 Console 配置文件

```yaml
# config.yml
console:
  # Kafka 集群
  kafka:
    brokers:
      - redpanda-1:9092
      - redpanda-2:9092
      - redpanda-3:9092
    clientId: console
    rackId: us-east-1

  # Schema Registry(可选)
  schemaRegistry:
    enabled: true
    urls:
      - http://redpanda-1:8081

  # 启用登录认证(可选)
  login:
    enabled: false
    # jwtSecret: "..."

  # 启用 RBAC
  rbac:
    enabled: false

  # 启用 Kafka Connect 管理
  connect:
    enabled: true
    clusters:
      - name: local-connect
        url: http://redpanda-connect:8083

  # 审计日志
  audit:
    enabled: false
```

#### 8.1.3 Helm Chart 部署

```bash
helm install redpanda-console redpanda/console \
  --namespace redpanda \
  --set config.kafka.brokers[0]="redpanda.redpanda.svc:9092"
```

### 8.2 主要功能

| 功能                | 说明                                              |
| ---- | ---- |
| **Topic 管理**      | 创建/删除/修改 topic,查看分区分布、消息预览       |
| **消息查询**        | 按 offset、时间、key 查询,实时消费预览            |
| **消费者组**        | 查看 lag、重置 offset、查看消费进度               |
| **Schema 管理**     | 查看/上传/下载 Avro/JSON/Protobuf Schema          |
| **Kafka Connect**   | 管理 Connector 集群、查看任务状态                |
| **ACL 管理**        | 可视化权限管理(创建/删除 ACL)                    |
| **性能监控**        | 集群指标、broker 指标、topic 指标                |
| **数据流监控**      | 实时消息流量图、消费速度图                         |
| **Quick Start**     | 一键生成测试 producer/consumer,方便调试          |

---

## 九、健康检查与验证

### 9.1 健康检查命令

```bash
# 1. 集群整体健康
rpk cluster health
# 输出:
# CLUSTER HEALTH
# ==============
# Connected: true
# Controller: 0
# Healthy: 0 (all nodes healthy)
# Uptime: 1234

# 2. 集群信息(节点列表)
rpk cluster info

# 3. 集群元数据
rpk cluster metadata

# 4. Admin API 健康
curl -s http://localhost:9644/public_metrics | head
curl -s http://localhost:9644/ready
# 输出: ready

# 5. Kafka 协议兼容测试
kafkacat -b localhost:9092 -L
# 或
kcat -b localhost:9092 -L
```

### 9.2 关键指标

| 指标                              | 健康值              | 异常处理                          |
| ---- | ---- | ---- |
| `vectorized_cluster_partition_count` | 与规划一致        | 检查 topic 配置                   |
| `vectorized_storage_disk_free_bytes` | > 20% 总容量     | 扩容磁盘 / 启用 Tiered Storage    |
| `vectorized_storage_disk_free_space_alert` | 不告警      | 检查                          |
| `vectorized_cluster_unavailable_partitions` | 0            | 检查 broker 状态                  |
| `vectorized_cluster_under_replicated_partitions` | 0       | 检查 follower 同步                |
| `vectorized_kafka_request_latency_seconds` | < 0.01 s      | 检查 IO / CPU                      |
| `vectorized_io_queue_total`       | < 0.7               | 检查磁盘 IO 瓶颈                  |

### 9.3 端到端验证脚本

```bash
#!/bin/bash
# redpanda-health-check.sh
set -e

BROKER=${1:-localhost:9092}

echo "==> 1. 集群信息"
rpk cluster info

echo "==> 2. 健康检查"
rpk cluster health

echo "==> 3. Admin API"
curl -s http://localhost:9644/ready

echo "==> 4. 创建测试 topic"
rpk topic create smoke-test -p 3 -r 3 || true

echo "==> 5. 生产消息"
echo "smoke-$(date +%s)" | rpk topic produce smoke-test

echo "==> 6. 消费消息"
rpk topic consume smoke-test --num 1

echo "==> 7. 列出 topic"
rpk topic list

echo "==> 8. 删除测试 topic"
rpk topic delete smoke-test

echo "All checks passed!"
```

### 9.4 常见问题排查

| 现象 | 排查方向 | 修复方法 |
| ---- | -------- | -------- |
| `rpk cluster info` 报 `connection refused` | 客户端连不上 broker | 检查 `advertised_addresses` 是否正确 |
| `rpk cluster health` 显示 `Disconnected` | 节点间 RPC 故障 | 检查防火墙/安全组 33145 端口 |
| 消费 lag 持续增长 | 消费者处理慢 | 扩容消费者实例 / 优化消费逻辑 |
| 生产报 `NotEnoughReplicasException` | 副本不足 | 检查 broker 数量,确保 ≥ 副本数 |
| `vectorized_io_queue_total > 0.7` | 磁盘 IO 瓶颈 | 升级 SSD / 减少分区数 |
| 启动报 `cluster_id mismatch` | cluster_id 冲突 | 删除 `data_directory`,重新启动 |
| `node_id` 冲突 | 集群内重复 | 修改 `node_id`,清理数据目录 |
| Schema Registry 报错 | schema 文件不匹配 | 用 `rpk schema` 工具验证 |
| Console 无法访问 | 端口未开放 | 检查 8080 端口、安全组规则 |
| `rpk topic produce` 报错 `UnknownTopic` | topic 不存在 | `rpk topic create` 先创建 |

### 9.5 性能基准测试

生产环境部署完成后,建议用 `rpk generate` 做一次基础性能压测,作为后续优化的基线:

```bash
# 1. 创建压测 topic(注意:分区数越多,吞吐越高)
rpk topic create perf-test -p 12 -r 3

# 2. 生产压测(无 ack 等待,测极限吞吐)
rpk generate produce \
  --topic perf-test \
  --num-records 1000000 \
  --record-size 1024 \
  --throughput -1 \
  --producer-props \
    acks=1 \
    batch.size=65536 \
    linger.ms=5 \
    compression.type=lz4

# 3. 生产压测(acks=all,测一致性下的吞吐)
rpk generate produce \
  --topic perf-test \
  --num-records 100000 \
  --record-size 1024 \
  --throughput -1 \
  --producer-props \
    acks=all \
    enable.idempotence=true

# 4. 消费压测
rpk generate consume \
  --topic perf-test \
  --num-records 100000 \
  --consumer-props \
    fetch.min.bytes=1024 \
    fetch.max.bytes=1048576
```

### 9.6 Prometheus + Grafana 监控集成

Redpanda Admin API (`/public_metrics`) 暴露 Prometheus 格式指标,可直接接入 Prometheus + Grafana:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'redpanda'
    static_configs:
      - targets:
        - 'redpanda-1:9644'
        - 'redpanda-2:9644'
        - 'redpanda-3:9644'
```

官方提供 Grafana Dashboard 模板:[redpanda/grafana_dashboards](https://github.com/redpanda-data/redpanda/tree/dev/tools/grafana_dashboards)

---

## 十、升级与迁移

### 10.1 Redpanda 升级路径

| 升级方式       | 适用场景                | 停机     | 步骤                           |
| ---- | ---- | ---- | ---- |
| **滚动升级**   | 小版本 (v25.1 → v25.2) | **无停机** | 逐节点重启                     |
| **大版本升级** | v24.x → v25.x          | 短暂     | 全集群停机升级                 |
| **Kafka 迁移** | Kafka → Redpanda       | 视场景   | 工具迁移 / 双写                |

### 10.2 滚动升级

```bash
# 升级顺序:节点 3 → 节点 2 → 节点 1(最后升级 controller)
# (注意:Redpanda 自动选主,任意节点都可能成为 leader)

# ============ 节点 3 ============
# 1. 备份配置
ssh node3 "cp /etc/redpanda/redpanda.yaml /etc/redpanda/redpanda.yaml.bak"

# 2. 停止节点
ssh node3 "systemctl stop redpanda"

# 3. 升级包
ssh node3 "apt-get update && apt-get install --only-upgrade redpanda"

# 4. 启动节点
ssh node3 "systemctl start redpanda"

# 5. 等待健康
sleep 30
rpk cluster health

# ============ 节点 2 ============
# 同上

# ============ 节点 1 ============
# 同上(最后)
```

### 10.3 从 Kafka 迁移到 Redpanda

#### 10.3.1 Kafka MirrorMaker 2 (推荐)

Redpanda **完全兼容 Kafka 协议**,可直接复用 Kafka 的 MirrorMaker 2。

```bash
# 1. 启动 MirrorMaker 2(Kafka 集群侧)
# 在 Kafka 集群上启动,目标指向 Redpanda

# mm2.properties
clusters = source-kafka, target-redpanda
source-kafka.bootstrap.servers = kafka-1:9092,kafka-2:9092
target-redpanda.bootstrap.servers = redpanda-1:9092,redpanda-2:9092

source-kafka->target-redpanda.enabled = true
source-kafka->target-redpanda.topics = .*
```

#### 10.3.2 Redpanda Migrator (官方工具)

```bash
# 1. 安装 Redpanda Migrator
# 独立工具,见官方文档

# 2. 启动迁移(后台持续同步)
rpk migrator start \
  --source kafka-1:9092 \
  --target redpanda-1:9092 \
  --topics "*"
```

#### 10.3.3 双写模式(业务切换)

```text
┌─────────────────────────────────────────────────┐
│            双写迁移流程                           │
│                                                 │
│ 1. 生产端开始双写(Kafka + Redpanda)             │
│ 2. 消费端切到 Redpanda                          │
│ 3. 验证消息一致性                                │
│ 4. 生产端停止写 Kafka                           │
│ 5. 下线 Kafka 集群                               │
└─────────────────────────────────────────────────┘
```

### 10.4 升级注意事项

| 注意项                          | 说明                                              |
| ---- | ---- |
| 阅读 [Release Notes](https://github.com/redpanda-data/redpanda/releases) | 重点看 Breaking Changes           |
| **滚动升级前先验证**           | 在测试环境先做一遍                                  |
| 监控副本状态                   | 关注 `under_replicated_partitions` 指标           |
| 保留旧版本二进制                | 便于快速回滚                                       |
| 大版本升级需重启所有节点       | v24 → v25 这类跨度需短暂停机                       |
| Kafka 兼容性版本              | 确认 Redpanda 版本兼容的 Kafka 客户端版本         |

---

## 十一、卸载

### 11.1 包安装的卸载

```bash
# 1. 停止服务
systemctl stop redpanda
systemctl disable redpanda

# 2. 删除 systemd unit(自动随包卸载)
systemctl daemon-reload

# 3. 卸载包
apt-get purge -y redpanda
# 或
dnf remove -y redpanda

# 4. 删除残留配置
rm -rf /etc/redpanda
rm -rf /var/lib/redpanda
rm -rf /var/log/redpanda
rm -rf /var/cache/redpanda

# 5. 删除用户
userdel -r redpanda

# 6. 清理 ulimit
sed -i '/redpanda/d' /etc/security/limits.conf
```

### 11.2 Docker 卸载

```bash
# 1. 停掉容器
docker compose down -v
# 或
docker stop redpanda-0 redpanda-1 redpanda-2 console
docker rm redpanda-0 redpanda-1 redpanda-2 console

# 2. 删除镜像
docker rmi redpandadata/redpanda:v25.2.1
docker rmi redpandadata/console:v3.x.x

# 3. 删除数据卷
docker volume ls | grep redpanda
docker volume rm <project>_redpanda0_data \
              <project>_redpanda1_data \
              <project>_redpanda2_data
```

### 11.3 验证彻底卸载

```bash
# 验证命令不存在
which rpk
which redpanda

# 验证无进程
pgrep -af redpanda

# 验证无端口监听
ss -ltnp | grep -E '9092|33145|9644|8081'

# 验证无 systemd 服务
systemctl list-unit-files | grep redpanda

# 验证目录已清
ls /var/lib/redpanda 2>&1 | grep "No such file"
ls /etc/redpanda 2>&1 | grep "No such file"
```

---

## 十二、核心要点速记

- **Redpanda 定位**:**Kafka 的 C++ 重写版**,**单二进制、无 JVM、无 GC**,100% Kafka API 兼容
- **公司**:Vectorized(2020 成立)→ Redpanda Data(2023 更名),创始人 **Alexander Gallego**(原 LinkedIn Kafka 核心工程师)
- **核心架构**:**thread-per-core** + **Seastar 异步框架** + **内置 Raft (RPK)**
- **性能优势**:p99 延迟 **< 5ms**(Kafka 8-15ms),单节点吞吐 **100-300 万 msg/s**(Kafka 50-100 万)
- **资源占用**:相同吞吐下 **CPU/内存约为 Kafka 的 1/3**
- **内置生态**:**Schema Registry**、**Kafka Connect**、**HTTP Proxy** 全部内置,无需 Confluent 全家桶
- **配置格式**:`redpanda.yaml`(YAML,比 Kafka `properties` 更现代化)
- **管理工具**:**`rpk` 一把梭**,替代 Kafka 的 20+ 个 `kafka-*.sh` 脚本
- **端口规划**:
  - `9092` Kafka API(客户端接入)
  - `33145` RPC API(节点间 Raft 通信)
  - `9644` Admin API(管理/HTTP)
  - `8081` Schema Registry
  - `8082` HTTP Proxy (Pandaproxy)
- **安装方式**:
  - **apt/yum 包**(Linux 生产首选)
  - **Docker / Compose**(开发、PoC)
  - **Helm / Operator**(K8s 生产)
  - **brew**(macOS 开发)
- **启动命令**:
  - 开发:`rpk redpanda start --overprovisioned --smp 1`
  - 生产:`systemctl start redpanda`
  - 容器:`redpanda start --smp=1 --memory=1G`
- **集群部署**:**3 节点起步**,通过 `seed_servers` 配置种子节点,`empty_seed_starts_cluster` 仅首节点为 true
- **健康检查**:`rpk cluster health` / `rpk cluster info` / `curl :9644/ready`
- **分区/副本**:`default_topic_partitions=3`,`default_topic_replications=3`(同 Kafka)
- **资源调优**:`resource_limits.memory_per_cpu=2GB`、`reserve_memory=25% 总内存`,`numa_aware=true`(生产推荐)
- **日志配置**:`log_segment_size=128MB`、`log_retention_ms=7天`(默认)
- **分层存储**:**Tiered Storage** 内置支持 S3/GCS,`cloud_storage_enabled=true`
- **Iceberg 集成**:`iceberg_enabled=true`,原生直写数据湖
- **ACL 管理**:`rpk acl create/list/delete`,用户管理 `rpk security user create`
- **Connect 管理**:`rpk connect connector create/status/delete`,配置存于 Secret
- **Redpanda Console**:官方 Web UI,**Docker / Helm** 一行启动,功能覆盖 Topic + Consumer Group + Schema + Connect + ACL
- **升级**:滚动升级,**最后升级 controller leader 节点**,跨大版本需短暂停机
- **Kafka 迁移**:**MirrorMaker 2 / Redpanda Migrator / 双写** 三种方式,API 兼容,**零代码改造**
- **License**:**BSL (Business Source License)**,自用、卖软件 OK,云厂商再分发受限
- **Kafka vs Redpanda 选型口诀**:
  - **延迟敏感 / 资源受限 / 想要简化运维** → **Redpanda**
  - **生态丰富 / 已有 Kafka 工具链 / 团队熟悉** → **Kafka**
- **坑点提示**:
  - **首次启动无需 `format`**,Redpanda 自动初始化
  - **节点 1 的 `empty_seed_starts_cluster: true`**,其他节点必须为 `false`
  - **配置文件是 YAML**,Kafka 的 `server.properties` 不能直接用
  - **管理工具是 `rpk`**,Kafka 的 `kafka-topics.sh` 等不能直接用(虽然命令相似)
  - **`kafka_api.advertised_addresses` 必须能让客户端访问**,否则连接失败
  - **容器内启动**记得加 `--overprovisioned`,跳过资源校验
  - **生产环境**修改 `tune_disk: false`,否则容器内自动调优会失败
  - **Tiered Storage 启用**后,本地磁盘可大幅减少,几乎无限保留