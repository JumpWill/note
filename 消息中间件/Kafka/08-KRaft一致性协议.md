# Kafka KRaft 一致性协议

> 本章系统讲解 Kafka 自 2.8 版本引入、3.3 版本生产可用的 KRaft 模式。KRaft 用基于 Raft 共识算法的内部控制器仲裁替代了 ZooKeeper,成为 Kafka 走向"零外部依赖"的关键一步。理解 KRaft,既需要掌握 Raft 算法本身,也需要理解 Kafka 的元数据模型如何映射到 Raft 日志。

## 一、KRaft 概述

### 1.1 什么是 KRaft

**KRaft (Kafka Raft)** 是 Apache Kafka 引入的**一致性协议层**,它用基于 **Raft 共识算法**实现的内部控制器集群 (Controller Quorum) 完全替代了 ZooKeeper,负责管理 Kafka 集群的所有元数据(主题、分区、副本、ISR 等)。

KRaft 模式下的 Kafka 集群:

- **不再依赖任何外部协调服务**(无 ZooKeeper)
- **元数据自我管理**,控制器通过 Raft 协议同步
- **元数据日志 (Metadata Log)** 持久化为 Kafka 内部主题 `__cluster_metadata`
- **单控制平面**,降低运维复杂度,提升扩展能力

### 1.2 版本演进

| 版本     | 状态        | 说明                                                                  |
|----------|-------------|-----------------------------------------------------------------------|
| 2.8.0    | 实验性      | 首个 KRaft 实验版本,支持开发测试                                      |
| 3.0.0    | 实验性      | 功能完善,继续打磨                                                   |
| 3.2.0    | 实验性      | 改进快照、控制器迁移                                                 |
| 3.3.0    | **生产可用**| 官方宣布可用于生产 (Production-Ready),推荐新集群启用                |
| 3.4.x    | 生产可用    | 持续优化、bug 修复                                                   |
| 3.5.x+   | 生产可用    | 控制器与 Broker 分离模式成熟                                         |
| 3.6+     | 生产可用    | ZooKeeper 模式标注为弃用,新集群建议 KRaft                            |
| 4.0+     | **强烈推荐**| 计划移除 ZooKeeper 模式,KRaft 为唯一模式                            |

> **官方建议**:从 Kafka 3.3 起,新建集群应直接选择 KRaft。迁移工具 `kafka-migration-tools` 支持从 ZK 平滑过渡。

### 1.3 KRaft 与传统模式的核心差异

| 维度       | ZooKeeper 模式                       | KRaft 模式                          |
|------------|--------------------------------------|-------------------------------------|
| 外部依赖   | 必须部署 ZK 集群 (3/5 节点)          | 无外部依赖                          |
| 元数据存储 | ZK znodes                            | Kafka 内部主题 `__cluster_metadata` |
| 控制器选举 | ZK 临时节点 + Watch                  | Raft 共识 (基于日志)                |
| 元数据传播 | Controller 推送到所有 Broker         | Controller Quorum 通过日志复制     |
| 控制器数量 | 1 个 active + N 个 standby          | 多个 active 共同参与日志复制       |
| 元数据延迟 | 通常 ms~秒级                          | 通常更快,日志批量复制             |
| 运维复杂度 | 高(ZK 集群独立)                    | 低(单一系统)                       |
| 可扩展性   | ZK 写入瓶颈 (几十 MB/s)            | 受限于日志复制,但吞吐更高         |
| 故障恢复   | Controller 重连 ZK + 重载元数据    | 自动选主,新 Leader 接管日志       |

---

## 二、为什么 KRaft 取代 ZooKeeper

### 2.1 ZooKeeper 的痛点

#### 2.1.1 运维复杂

```text
┌──────────────────────────────────────────────────────────────────┐
│             ZooKeeper 模式:双系统需要双倍运维                      │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Kafka 集群 (Broker × N)         ZooKeeper 集群 (ZK × 3/5)    │
│   ┌────────────────────┐         ┌────────────────────┐         │
│   │  Broker-1          │  ◀───▶  │  ZK-1 (Leader)     │         │
│   │  Broker-2          │         │  ZK-2 (Follower)   │         │
│   │  ...               │         │  ZK-3 (Follower)   │         │
│   └────────────────────┘         └────────────────────┘         │
│          │                              │                        │
│          ▼                              ▼                        │
│     数据/日志                      元数据 (znodes)              │
│                                                                  │
│   • 双重部署、双重监控、双重升级                                    │
│   • ZK 需独立调优 (JVM、内存、磁盘快照)                            │
│   • ZK 故障 → Kafka 整个控制平面停摆                               │
│   • 容量规划困难 (ZK 不擅长存储 GB 级元数据)                       │
└──────────────────────────────────────────────────────────────────┘
```

传统部署一个生产级 Kafka 集群,实际要同时管理:

- **Kafka 集群**:`kafka` 服务 × 多个
- **ZooKeeper 集群**:`zookeeper` 服务 × 3 或 5
- **监控告警**:两套独立的 metrics(jmx, prometheus exporter)
- **备份恢复**:ZK 单独快照 + Kafka 数据,流程割裂
- **版本兼容**:升级时 Kafka 版本和 ZK 版本要矩阵对账

#### 2.1.2 性能瓶颈

ZooKeeper 作为 Kafka 的"超级管理员",元数据变更全靠它:

| 操作             | 路径                                                         | ZK 瓶颈                          |
|------------------|--------------------------------------------------------------|----------------------------------|
| 主题创建         | Controller 写入多个 ZK znode                                 | ZK 事务提交,fsync 落盘          |
| 分区重分配       | Controller 写入数千个 znode                                  | 单节点打包提交,数千次事务       |
| 滚动重启集群     | 每台 Broker 上下线,反复 Watch/重 Watch                       | ZK session 与 watcher 风暴       |
| 控制器切换       | 选举 + 重新加载全部元数据                                    | 启动耗时随集群规模线性增长       |

ZK 单 Leader 的写入模型,在大型集群(数千 Broker、数十万分区)上接近极限。

#### 2.1.3 扩展性受限

- **ZK 节点上限**:规模过大会触发 ZK 的 ` jute.maxbuffer`、`commitProcessor` 队列等问题
- **元数据膨胀**:Broker 数 / 分区数 / topic 数 × 副本因子,zk 节点体积线性增长
- **大集群无法支持**:Confluent 与 LinkedIn 工程团队曾公开讨论过 ZK 集群碰到的问题

### 2.2 KRaft 的优势

```text
┌──────────────────────────────────────────────────────────────────┐
│             KRaft 模式:单一系统、单一控制流                       │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│   KRaft 集群 (Controller Quorum + Broker)                       │
│   ┌────────────────────────────────────────────────────┐        │
│   │  Controller-1 (Leader)   ┌──────────────────┐     │        │
│   │  Controller-2 (Follower) │  __cluster_       │     │        │
│   │  Controller-3 (Follower) │  metadata topic   │     │        │
│   └──────────────────────────└──────────────────┘     │        │
│   ┌────────────────────────────────────────────────────┐        │
│   │  Broker-1   Broker-2   Broker-3   ...  Broker-N   │        │
│   │     ▲                                            │        │
│   │     └─── 通过 RPC (FetchMetadata) 拉取元数据      │        │
│   └────────────────────────────────────────────────────┘        │
│                                                                  │
│   • 单一 Kafka 系统,无需独立部署 ZK                              │
│   • 元数据走 Kafka 自己的日志机制,吞吐与可扩展性更好              │
│   • Raft 协议保证一致性与可用性                                   │
│   • 故障恢复自动化 (Leader 切换 + 日志追平)                       │
└──────────────────────────────────────────────────────────────────┘
```

#### 2.2.1 统一控制平面

- **无外部协调服务**:KRaft 把控制平面合进 Kafka
- **一套监控/工具/备份栈**:复用 Kafka 现有的运维体系
- **集群视图一致**:Controller 与 Broker 都基于同一份元数据日志

#### 2.2.2 性能更好

KRaft 把元数据当成"日志条目",复用 Kafka 高吞吐的日志机制:

- **批量提交**:元数据事件可以批量追加,降低单事件 fsync 成本
- **并行追平**:新加入的 Controller 从 Leader 拉取快照 + 增量日志
- **元数据传播可配置**:Controller 与 Broker 间通过 Fetch 元数据 RPC,异步、可配置频率

#### 2.2.3 可扩展性更强

- **元数据存到 Kafka topic**:享受 Kafka 的横向扩展能力
- **元数据快照**:定期快照压缩,避免启动时全量重放
- **支持数十万分区规模**:经 Confluent 验证,KRaft 可支撑百万级分区

#### 2.2.4 架构与运维简化

| 维度         | ZK 模式                              | KRaft 模式                                |
|--------------|--------------------------------------|-------------------------------------------|
| 部署组件     | Kafka + ZK 集群(2 套进程)            | Kafka 集群(1 套进程)                     |
| 配置文件     | zoo.cfg + server.properties          | server.properties (process.roles)        |
| 监控指标     | ZK mntr + Kafka JMX                  | 仅 Kafka JMX                              |
| 滚动升级     | 注意 ZK 与 Kafka 兼容性矩阵          | 单组件升级                                |
| 故障演练     | 需演练 ZK Leader 切换                | 演练 Controller Leader 切换              |
| 备份恢复     | ZK 快照 + Kafka 数据                  | Kafka 快照 (__cluster_metadata)           |

### 2.3 KRaft vs ZooKeeper 架构对比图

```text
┌─────────────────────────┐                ┌─────────────────────────┐
│   ZooKeeper 模式        │                │       KRaft 模式        │
├─────────────────────────┤                ├─────────────────────────┤
│                         │                │                         │
│   ┌─────────────────┐   │                │   ┌─────────────────┐   │
│   │   Broker × N    │   │                │   │   Broker × N    │   │
│   └────────┬────────┘   │                │   └────────┬────────┘   │
│            │ RPC         │                │            │ RPC         │
│   ┌────────▼────────┐   │                │   ┌────────▼────────┐   │
│   │   Active        │   │                │   │   Controller    │   │
│   │   Controller    │   │                │   │   Quorum        │   │
│   │   (单点)        │   │                │   │   (Raft 组)     │   │
│   └────────┬────────┘   │                │   │ Leader + 2 Flw  │   │
│            │ zk client   │                │   └────────┬────────┘   │
│   ┌────────▼────────┐   │                │            │ 内部副本     │
│   │   ZooKeeper     │   │                │   ┌────────▼────────┐   │
│   │   集群 (3/5)    │   │                │   │ __cluster_      │   │
│   │   Leader+Follower│   │                │   │ metadata topic  │   │
│   └─────────────────┘   │                │   │ (内部 Raft 日志)│   │
│                         │                │   └─────────────────┘   │
└─────────────────────────┘                └─────────────────────────┘
```

---

## 三、KRaft 核心概念

### 3.1 Controller Quorum (控制器仲裁)

KRaft 模式下,Kafka 的所有元数据由一组**控制器节点 (Controller Node)** 共同管理。这组节点就叫做 **Controller Quorum**。

| 角色         | 职责                                                          |
|--------------|---------------------------------------------------------------|
| **Leader**   | 接收元数据变更请求、写入日志、复制给 Follower、响应客户端      |
| **Follower** | 被动接收 Leader 的日志条目 (AppendEntries)、参与投票          |
| **Candidate**| 选举期间的临时角色,发起投票请求                              |

一个 **3 节点 Quorum** 容忍 1 节点失效;**5 节点 Quorum** 容忍 2 节点失效。**绝大多数生产建议 3 节点**,足够容灾且降低复杂度。

### 3.2 Leader / Follower

```text
                    Controller Quorum (3 节点)
                    ┌─────────────────────────────┐
                    │                             │
   Client ───────▶  │  ┌─────────────────────┐    │
   (元数据变更)     │  │      Leader         │    │
                    │  │  (处理所有变更)     │    │
                    │  └──────────┬──────────┘    │
                    │             │ AppendEntries │
                    │   ┌─────────┴─────────┐     │
                    │   ▼                   ▼     │
                    │ ┌─────────┐    ┌─────────┐ │
                    │ │Follower-1│   │Follower-2│ │
                    │ │(AppendEntries)│(AppendEntries)│ │
                    │ └─────────┘    └─────────┘ │
                    └─────────────────────────────┘

- Leader 上任一个 Term 内唯一处理写请求
- Follower 仅复制日志,不直接接受客户端请求
- Leader 通过定期心跳维持权威 (election timeout 内收到心跳就不发起投票)
```

### 3.3 Term (任期)

**Term** 是 Raft 中的逻辑时钟,每一次选举开始一个新 Term。

```text
Term 递增规则:

   Term 1                Term 2                Term 3
   ┌──────────────────┐   ┌──────────────────┐   ┌──────────────┐
   │  Leader: A       │   │  Leader: B       │   │ Leader: C    │
   │  (稳定期)        │ → │  (A 故障,B 胜出) │ → │ (B 故障)     │
   └──────────────────┘   └──────────────────┘   └──────────────┘
         ↑                       ↑                     ↑
       election                 election             election
       timeout                  timeout              timeout
       触发? no                 触发? yes            触发? yes

每个 Term 内只能有一个 Leader;
Term 是单调递增的逻辑时钟,保证全局事件顺序。
```

Term 的几个语义:

- **单调递增**:每次选举 term 自增
- **去重过期请求**:旧 Term 的请求会被新 Term 拒绝
- **选举规则**:同一 Term 内最多一个 Leader

### 3.4 Log Entry (日志条目)

KRaft 把每一次元数据变更建模成一条 **Raft 日志条目**:

```text
┌──────────────────┬──────────────────┬──────────────────┬─────────────┐
│  Index = 7       │  Index = 8       │  Index = 9       │  Index = 10 │
│  Term = 2        │  Term = 2        │  Term = 3        │  Term = 3   │
│  Command:        │  Command:        │  Command:        │  Command:   │
│  CREATE_TOPIC    │  ALTER_PARTITION │  UPDATE_CONFIG   │  ELECT_LEAD │
│  "order-events"  │  partitions=16   │  retention=7d    │  (无命令)   │
└──────────────────┴──────────────────┴──────────────────┴─────────────┘
  ↑ 已提交
                                                ↑ 已提交 (commitIndex = 9)
                                                ↑
                                          被复制到多数派
```

每条日志条目固定包含:

| 字段      | 说明                                            |
|-----------|-------------------------------------------------|
| `Index`   | 日志中的顺序号,单调递增                        |
| `Term`    | 创建此条目的 Leader 任期                       |
| `Command` | 业务命令(CREATE_TOPIC、ALTER_PARTITION 等)     |

### 3.5 其他关键术语

| 术语                  | 含义                                                         |
|-----------------------|--------------------------------------------------------------|
| **committed**         | 日志条目已被多数派节点持久化,可应用到状态机                |
| **commitIndex**       | 已提交的最高日志索引                                         |
| **lastApplied**       | 已应用到状态机的最高日志索引                                |
| **election timeout**  | Follower 等不到心跳则变成 Candidate,通常 1.5s~3s 随机     |
| **heartbeat**         | Leader 周期性空 AppendEntries,维持权威                     |
| **snapshot**          | 日志压缩点,丢弃已应用的旧日志                               |

---

## 四、Raft 一致性算法

### 4.1 Raft 三大保证

Raft 协议提供 **三大安全性保证**,KRaft 全部继承:

#### 4.1.1 选举安全 (Election Safety)

```text
性质:每个 Term 内最多选举出一个 Leader。

证明:
  - 同一 Term 内,一个 Candidate 要成为 Leader 必须获得多数派投票
  - 一张选票在同一 Term 内只能投一次
  - 多数派节点不相交 ⇒ 同一 Term 不可能产生两个 Leader

示例:
   Term 5 中:
     A 收到 3 票 (含自己)、B 收到 2 票
     A 当选,B 落选
     Term 5 内不再产生新 Leader
```

#### 4.1.2 Leader 完整性 (Leader Completeness)

```text
性质:如果一条日志条目在某个 Term 被提交,那么在后续所有 Term 的 Leader 上,
    这条日志必然存在。

论证:
  - 日志条目只在 Leader 上被创建 (Entry 由 Leader 追加)
  - 选举限制: Candidate 必须拥有所有已提交条目,才能当选 (投票者会比较日志)
  - 因此新 Leader ≥ 老 Leader 的日志

示例:
   Term 3 提交了 Index=7
   Term 4 Leader 必定包含 Index=7
   Term 5 Leader 必定包含 Index=7
```

#### 4.1.3 日志匹配 (Log Matching)

```text
性质:
  (1) 如果两个节点日志中,相同 Index 和 Term 的条目相同,
      则它们前序所有条目都相同
  (2) 如果一条 Entry 在某个节点的某 Term 提交了,
      那么其他节点该 Index 一定也是该 Term 的同一条 Entry

实现:
  - AppendEntries 包含 (prevIndex, prevTerm), Follower 必须匹配
  - 不匹配就拒绝,Leader 回退 nextIndex 重试,直到对齐
```

### 4.2 其他附加属性

| 属性               | 说明                                                                  |
|--------------------|-----------------------------------------------------------------------|
| **State Machine**  | 每个 Controller 节点把日志按顺序应用到本地状态机 (元数据缓存)        |
| **Figure of Merit**| 仅已提交的日志条目才影响实际元数据,未提交的条目可以回滚              |
| **Linearizable**   | 一次成功的客户端写入,等价于一次"已提交"操作                        |

---

## 五、KRaft 选举流程

### 5.1 节点三种状态

```text
              election timeout 触发                 收到多数派投票
   ┌─────────┐ ─────────────────▶ ┌─────────┐ ─────────────────▶ ┌─────────┐
   │Follower │                    │Candidate│                    │ Leader  │
   └─────────┘ ◀───────────────── └─────────┘ ◀───────────────── └─────────┘
       ▲           发现更高 Term         │       stepDown              │
       │                                │       发现更高 Term          │
       │                                └─────────────────────────────┘
       │                                        Term 递增
       │   收到 AppendEntries (心跳或日志)
       └─────────────────────────────────────────────
```

| 状态         | 行为                                                                     |
|--------------|--------------------------------------------------------------------------|
| **Follower** | 被动接收 Leader 的 AppendEntries,选举超时未收到心跳则转 Candidate       |
| **Candidate**| 自增 Term,发 RequestVote,获得多数票则成为 Leader                       |
| **Leader**   | 接受客户端请求,AppendEntries 复制到 Follower,定期发心跳                  |

### 5.2 选举超时

```text
Follower 视角:

   t = 0                          t = T_election
   │                              │
   │  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ▶│  election timeout 触发
   │                              │
   │  若期间收到 Leader 心跳       │  自增 Term → Candidate
   │  ⟶ 重置超时,继续保持 Follower │  发 RequestVote RPC
   │                              │

T_election 通常随机化为 1.5s~3s(Kafka 默认),
其随机性用于避免 "split vote" 同时发起选举。
```

### 5.3 投票规则

RequestVote RPC 的处理逻辑:

```text
Candidate 发 RequestVote(args = { term, candidateId, lastLogIndex, lastLogTerm })
每个 Follower 收到后:

1. if args.term < currentTerm:
       reject (term 太旧)
2. if (votedFor is null or votedFor == candidateId) and
    candidate's log is at least as up-to-date as mine:
       grant vote; votedFor = candidateId
   else:
       reject

"at least as up-to-date" 判断:
   if lastLogTerm != myLastLogTerm:
        return lastLogTerm > myLastLogTerm
   else:
        return lastLogIndex >= myLastLogIndex
```

关键点:

- **一个 Term 一票**:同一 Term 内只能投一次,投过即记忆
- **日志新鲜度门槛**:候选人的日志必须 ≥ 自己,否则不投
- **保证 Leader Completeness**:从源头杜绝丢失已提交日志的 Leader 当选

### 5.4 Term 递增

每次发生以下事件之一,Term 会自增:

1. Follower 选举超时变成 Candidate
2. Follower 收到比 currentTerm 更大的 Term,立即更新为 Follower

Term 在以下场景下被使用:

- 拒绝过期请求(RequestVote / AppendEntries)
- 标识日志条目的"年龄"
- 在 RPC 响应中带 term 让 Leader 主动 stepDown

### 5.5 KRaft 选举完整时序图

```text
===========================================================================
                KRaft Controller Leader Election (时序图)
===========================================================================

    Follower-A          Follower-B          Follower-C
        |                    |                    |
        |  (稳定期, 当前 Term = 2, Leader = A)    |
        |                    |                    |
        | ←── heartbeat ─────|←────────────────────|
        | ←── heartbeat ─────|←────────────────────|
        | ←── heartbeat ─────|←────────────────────|
        |                    |                    |
        |        ✗ A 故障 / 网络分区              |
        |                    |                    |
   t1   |  election timeout  |  election timeout  |  election timeout
   t2   |  (因随机,可能不同)  |  (随机化)          |  (随机化)
        |                    |                    |
        | -- RequestVote ──▶ |                    |
        |   term=3,          |                    |
        |   votedFor=null     |                    |
        |                    |                    |
        |              B 收到 RequestVote        |
        |              ├── 检查 term > current   |
        |              │   (3 > 2) ✓             |
        |              ├── 检查日志新鲜度:        |
        |              │   (B 的日志 = A 的日志) ✓|
        |              ├── votedFor=B            |
        |              └── grant vote            |
        |                    |                    |
        |  ←── vote granted ─┤                    |
        |                    |                    |
        |  -- RequestVote ───────────────────▶   |
        |                    |                    |
        |                    |              C 收到 RequestVote
        |                    |              ├── 检查 term > current
        |                    |              │   (3 > 2) ✓
        |                    |              ├── 检查日志新鲜度:
        |                    |              │   (C 的日志 = A 的日志) ✓
        |                    |              ├── votedFor=C
        |                    |              └── grant vote
        |                    |                    |
        |  ←─────── vote granted ───────────────┤
        |                    |                    |
   t3   |  B 收到 2 票 (A+C),但因自己只投自己   |
        |     = 3 票 (含自己),达成多数派         |
        |                    |                    |
        |              B 成为 Leader              |
        |              term = 3                  |
        |                    |                    |
        | ←── heartbeat ─────|  (term=3)          |
        | ←── heartbeat ─────|  ────────────────▶ |
        |                    |                    |
        | A 收到 term=3, 比自己 currentTerm=2 大 |
        | → 自动 stepDown 为 Follower            |
        | → 更新 currentTerm = 3                 |
        |                    |                    |

===========================================================================
关键设计点:
  1. 随机 timeout 避免 split vote
  2. 一 Term 一票 (votedFor 记忆)
  3. 日志新鲜度比较 (Leader Completeness)
  4. 收到更高 term 自动 stepDown
  5. 多数派 = ⌊N/2⌋+1 = 2 (3 节点 quorum)
===========================================================================
```

### 5.6 与经典 Raft 选举对比

| 维度            | 经典 Raft                       | Kafka KRaft                   |
|-----------------|--------------------------------|--------------------------------|
| 一致性目标      | 通用状态机                      | Kafka 元数据变更               |
| 日志介质        | 任意持久化 (LevelDB、磁盘文件) | Kafka 内部 topic               |
| 元数据命令      | 任意字节序列                    | 类型化 API (CreateTopic 等)   |
| 快照机制        | 应用层自行实现                  | 内置 cluster metadata snapshot|
| 心跳 + 日志复用 | 通过 AppendEntries 一起         | 通过 Fetch RPC 共用一套核心   |
| 节点角色        | Leader/Follower/Candidate      | 同上                           |

KRaft 在 Raft 基础上对**快照、网络协议、RPC 集成**做了一定改造,使其更适合 Kafka 这种"日志即基础设施"的场景。

---

## 六、日志复制

### 6.1 复制流程

```text
===========================================================================
              KRaft 日志复制时序 (AppendEntries)
===========================================================================

Client        Leader            Follower-A        Follower-B        F+许多
   │            │                    │                │               │
   │  CreateTopic "orders"          │                │               │
   │ ──────────▶ │                    │                │               │
   │            │  appendEntry       │                │               │
   │            │  index = 8         │                │               │
   │            │  term = 3          │                │               │
   │            │  command = ...     │                │               │
   │            │                    │                │               │
   │            │ ──── AppendEntries ────────▶       │               │
   │            │   (prev=7,8,term=3)│                │               │
   │            │                    │                │               │
   │            │                    │ 校验 prev 匹配 │               │
   │            │                    │  持久化日志     │               │
   │            │                    │  更新 commit   │               │
   │            │ ◀─── success ──────│                │               │
   │            │     index=8        │                │               │
   │            │                    │                │               │
   │            │ ──── AppendEntries ───────────────────▶            │
   │            │                    │                │ 校验/持久化   │
   │            │                    │                │               │
   │            │ ◀─── success ─────────────────────│               │
   │            │                    │                │               │
   │            │ 多数派持久化成功!   │                │               │
   │            │ commitIndex = 8    │                │               │
   │            │ 应用到状态机        │                │               │
   │            │                    │                │               │
   │ 响应 Client │                    │                │               │
   │ ◀──────────│                    │                │               │
   │            │                    │                │               │
   │            │ ─ 后续 AppendEntries ──────────────── (副本完成)   │
   │            │   (下次心跳时携带 commitIndex)       │               │
   │            │                    │                │               │
   │            │                    │ 收到 commitIndex=8            │
   │            │                    │ 应用到状态机   │               │
   │            │                    │                │               │
```

### 6.2 客户端请求 → Leader → Follower → 多数派确认

KRaft 处理一次元数据变更(如 `CreateTopic`)的完整路径:

```text
步骤 1: 客户端(可能是 Kafka 客户端,也可能是 AdminClient)
        通过 KRaft RPC (例如 CreateTopics 请求) 发送给当前 Leader

步骤 2: Leader 验证请求 + 分配日志条目:
        - 自增 lastLogIndex
        - 把命令封装为 LogEntry(index=lastLogIndex+1,
          term=currentTerm, command=CreateTopic)

步骤 3: 复制给 Follower:
        - 并行发送 AppendEntries RPC
        - 包含 (prevIndex, prevTerm, entries, leaderCommit)

步骤 4: Follower 处理:
        - 校验 prevIndex/prevTerm 匹配
        - 失败就 reject,触发 Leader 截断重发
        - 成功就持久化,响应 success(index=...)

步骤 5: Leader 收到多数派成功响应:
        - 更新 commitIndex = 当前 index
        - 将该条目应用到本地状态机 (生成新的元数据快照)
        - 向客户端返回成功

步骤 6: Leader 下一次心跳 / 追加日志时把 commitIndex 带给 Follower:
        - Follower 收到后,确认自己的日志是否在该 index 之前
        - 若是,也应用到本地状态机
        - 此时全部 Controller 节点 metadata 一致
```

### 6.3 已提交位置 (commitIndex)

```text
Log 状态:

  Leader 节点:
  Index:  1   2   3   4   5   6   7   8   9   10
  Term:   1   1   2   2   3   3   3   3   -   -
  Status: C   C   C   C   C   C   C   C   -   -
                                  ^commitIndex=8 (已提交)

Follower-A:
  Index:  1   2   3   4   5   6   7   8
  Term:   1   1   2   2   3   3   3   3
  Status: C   C   C   C   C   C   C   C ✓
                      已同步到 8

Follower-B (落后):
  Index:  1   2   3   4   5   6   7
  Term:   1   1   2   2   3   3   3
  Status: C   C   C   C   C   C   C
            还需要 Index=8 才能 apply
            Leader 下次 AppendEntries 就会带过来
```

> 注:`C` 在上表中表示已 commit 且已 apply 到状态机的条目。

### 6.4 日志不一致的修复

当 Follower 与 Leader 日志不一致时,Leader 会**强制覆盖**该 Follower:

```text
Leader 维护:
  nextIndex[]: 对每个 Follower,下一次发送的日志起始 index
  matchIndex[]: 对每个 Follower,已知匹配的最高 index

AppendEntries 流程:
  1. Leader 发送 AppendEntries(prevIndex=nextIndex[i]-1,
                                 prevTerm=log[prevIndex].term,
                                 entries=...)
  2. Follower 比对:
     - 若 prevIndex/prevTerm 不匹配 → reject
     - 若 entries 与本地日志冲突 → 删除该 index 及之后所有日志
     - 若匹配 → 追加, 返回 success(matchIndex)
  3. Leader 收到 reject,decrement nextIndex[i], 重试
  4. 最终 nextIndex[i] 会定位到一致点 → 复制追上
```

Leader Completeness 保证了**不会丢失已提交日志**:因为只有拥有最新日志的 Candidate 才能当选,所以新 Leader 一定包含历史已提交条目。

---

## 七、KRaft 元数据存储

### 7.1 __cluster_metadata 主题

KRaft 不再依赖 ZK 存储元数据,而是把元数据日志**直接存在 Kafka 自己的主题 `__cluster_metadata` 中**。

| 属性     | 默认值                                                    |
|----------|----------------------------------------------------------|
| 主题名   | `__cluster_metadata`                                     |
| 分区数   | 1 (强制)                                                  |
| 副本数   | 与 controller.quorum.voters 节点数一致                  |
| 清理策略 | `compact` (压缩)                                         |
| 单分区   | 保证元数据全局有序                                         |

```text
  __cluster_metadata topic (单分区)
  ┌────────────────────────────────────────────┐
  │ Offset 100: CREATE_TOPIC "orders"          │
  │ Offset 101: ALTER_PARTITIONS "orders"+4    │
  │ Offset 102: CREATE_TOPIC "payments"        │
  │ Offset 103: UPDATE_CONFIG "retention.ms"   │
  │ Offset 104: ... (后续事件)                 │
  └────────────────────────────────────────────┘
       (压缩策略可能去除被覆盖的事件)
```

### 7.2 元数据日志 (事件序列)

每个事件都对应一段"被持久化的事实",按追加顺序形成**严格一致的事件流**。常见的事件类型:

| 事件类型                          | 说明                                            |
|-----------------------------------|-------------------------------------------------|
| `CreateTopic`                     | 创建主题                                        |
| `AlterPartitions`                 | 增加分区                                        |
| `UpdateConfig`                    | 更新主题/Broker 配置                          |
| `DeleteTopic`                     | 删除主题                                        |
| `ElectLeader`                     | 控制器换届(`__cluster_metadata` 日志中会有记录)|
| `RegisterBroker`                  | Broker 注册到集群                              |
| `UnregisterBroker`                | Broker 离线                                    |
| `CreateAccessControlEntry`        | ACL 变更                                       |

每个 Controller 节点重放这些事件,就能**完整重建集群元数据**。

### 7.3 快照机制

随着集群运行,`__cluster_metadata` 日志会不断增长。KRaft 通过**快照 (Snapshot)** 来压缩日志:

```text
snapshot 文件 (磁盘):
  ┌──────────────────────────────────────────┐
  │ Offset: 1000 (快照覆盖到的最大 offset)   │
  │ LastTerm: 5                              │
  │                                          │
  │ 元数据快照内容:                            │
  │   - 所有 Topic                            │
  │   - 所有 Topic 的分区 → (leader, replicas,isr)|
  │   - ACL                                  │
  │   - Broker 列表                          │
  └──────────────────────────────────────────┘

KRaft 行为:
  - 日志超过 snapshot.lag.max 或快照阈值时触发
  - 新加入的 Controller 先下载快照,再追赶增量日志
  - 减少重启时间和存储占用
```

#### 7.3.1 触发条件

| 参数                        | 说明                                            |
|----------------------------|-------------------------------------------------|
| `controller.quorum.fetch.timeout.ms` | Follower 拉取快照的频率                  |
| `controller.quorum.snapshot.lag.max` | 日志落后多少条时自动触发本地快照          |
| `controller.quorum.snapshot.size.max` | 快照文件最大字节数                      |

#### 7.3.2 快照恢复流程

```text
新 Controller 节点加入:
   1. 从集群拉取最新快照 (snapshot 文件)
   2. 加载快照恢复元数据状态
   3. 从快照对应 offset 之后开始追日志:
        - 拉取 (offset > snapshot.offset) 的日志条目
        - 逐条应用到状态机
   4. 追上 commitIndex 后,正式进入 Quorum 服务
```

---

## 八、KRaft 配置

### 8.1 主要配置项

#### 8.1.1 process.roles

KRaft 引入的核心配置,声明节点角色:

| 值             | 含义                                            |
|----------------|-------------------------------------------------|
| `broker`       | 仅作 Broker,不参与 Controller Quorum           |
| `controller`   | 仅作 Controller,不接收客户端生产消费流量       |
| `broker,controller` | 混合模式(同一进程既当 Broker 又当 Controller) |
| **空字符串**   | 传统 ZK 模式 (退化行为,自 3.3 起不推荐)       |

> 角色一旦设定,启动后就不可热改。要切换角色必须重启并修改配置。

#### 8.1.2 node.id

每个 Kafka 进程必须有**全局唯一**的 `node.id`,过去是 `broker.id`,KRaft 引入后改为 `node.id` 以兼容多种角色组合。

```properties
# 节点 ID 需要在集群内全局唯一
node.id=1
```

#### 8.1.3 controller.quorum.voters

```properties
# 格式:
# controller.quorum.voters=id@host:port,id@host:port,...
controller.quorum.voters=1@controller1:9093,2@controller2:9093,3@controller3:9093
```

- **格式**:`id@host:port,id@host:port,...`
- 每个 Controller 实例的 ID 必须在 voters 列表里
- 一般 3 个或 5 个,**优先 3** (足够容灾、运维简单)

#### 8.1.4 controller.listener.names / listeners

KRaft 通过独立的 listener 在 Controller 之间通信:

```properties
# 对外提供元数据服务 (Broker 拉取元数据)
listeners=PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:9093

# advertised.listeners 给客户端连接
advertised.listeners=PLAINTEXT://broker1.example.com:9092

# Controller 之间通信监听
controller.listener.names=CONTROLLER
controller.quorum.voters=1@broker1:9093,2@broker2:9093,3@broker3:9093
```

### 8.2 其他关键 KRaft 配置

| 配置项                                  | 默认值     | 说明                                      |
|----------------------------------------|-----------|------------------------------------------|
| `process.roles`                         | (空)       | broker/controller/broker,controller     |
| `node.id`                               | -          | 集群内全局唯一 ID                        |
| `controller.quorum.voters`              | -          | Controller Quorum 成员列表              |
| `controller.listener.names`             | -          | Controller listener 名                  |
| `controller.quorum.election.timeout.ms` | 1000      | 选举超时下限                            |
| `controller.quorum.fetch.timeout.ms`    | 1000      | Follower 拉取间隔                      |
| `controller.quorum.snapshot.lag.max`    | 10000     | 落后多少条触发本地快照                  |
| `controller.quorum.snapshot.size.max`   | 1GB       | 快照文件大小上限                        |
| `offsets.topic.replication.factor`      | 3         | __consumer_offsets 副本数 (Broker 配置) |
| `transaction.state.log.replication.factor` | 3      | __transaction_state 副本数             |

### 8.3 完整 KRaft 配置文件示例

下面是一个**生产级 3 节点 Controller + N 节点 Broker 分离部署**的样例:

#### 8.3.1 Controller 节点 1 (controller-1)

```properties
# /opt/kafka/config/controller-1.properties

# ==== 节点身份 ====
node.id=1

# ==== 角色 ====
process.roles=controller

# ==== 监听器 ====
# Controller 间通信端口(单独 listener)
listeners=CONTROLLER://0.0.0.0:9093
controller.listener.names=CONTROLLER
inter.broker.listener.name=PLAINTEXT

# 暴露给对端连接
advertised.listeners=CONTROLLER://controller-1.example.com:9093

# ==== Controller Quorum ====
controller.quorum.voters=1@controller-1.example.com:9093,2@controller-2.example.com:9093,3@controller-3.example.com:9093

# ==== 数据目录 ====
log.dirs=/var/lib/kafka/controller-1

# ==== 元数据日志 ====
# __cluster_metadata 副本数自动等于控制器 Quorum 节点数
controller.quorum.snapshot.lag.max=10000
controller.quorum.snapshot.size.max=1073741824

# ==== 选举参数 ====
controller.quorum.election.timeout.ms=1000
controller.quorum.fetch.timeout.ms=500

# ==== 监控 ====
metric.reporters=org.apache.kafka.common.metrics.JmxReporter
```

#### 8.3.2 Controller 节点 2 (controller-2)

```properties
# /opt/kafka/config/controller-2.properties
node.id=2
process.roles=controller
listeners=CONTROLLER://0.0.0.0:9093
controller.listener.names=CONTROLLER
inter.broker.listener.name=PLAINTEXT
advertised.listeners=CONTROLLER://controller-2.example.com:9093
controller.quorum.voters=1@controller-1.example.com:9093,2@controller-2.example.com:9093,3@controller-3.example.com:9093
log.dirs=/var/lib/kafka/controller-2
controller.quorum.snapshot.lag.max=10000
controller.quorum.snapshot.size.max=1073741824
controller.quorum.election.timeout.ms=1000
controller.quorum.fetch.timeout.ms=500
```

#### 8.3.3 Controller 节点 3 (controller-3)

```properties
# /opt/kafka/config/controller-3.properties
node.id=3
process.roles=controller
listeners=CONTROLLER://0.0.0.0:9093
controller.listener.names=CONTROLLER
inter.broker.listener.name=PLAINTEXT
advertised.listeners=CONTROLLER://controller-3.example.com:9093
controller.quorum.voters=1@controller-1.example.com:9093,2@controller-2.example.com:9093,3@controller-3.example.com:9093
log.dirs=/var/lib/kafka/controller-3
controller.quorum.snapshot.lag.max=10000
controller.quorum.snapshot.size.max=1073741824
controller.quorum.election.timeout.ms=1000
controller.quorum.fetch.timeout.ms=500
```

#### 8.3.4 Broker 节点 (broker-1)

```properties
# /opt/kafka/config/broker-1.properties

# ==== 节点身份 ====
node.id=101

# ==== 角色 ====
process.roles=broker

# ==== 监听器 ====
listeners=PLAINTEXT://0.0.0.0:9092
inter.broker.listener.name=PLAINTEXT
advertised.listeners=PLAINTEXT://broker-1.example.com:9092

# 不需要 controller.listener.names / controller.quorum.voters
# 因为这是纯 Broker,元数据从 Controller Quorum 拉取

# ==== 数据目录 ====
log.dirs=/var/lib/kafka/broker-1

# ==== 内部 topic 副本 ====
offsets.topic.replication.factor=3
transaction.state.log.replication.factor=3
transaction.state.log.min.isr=2

# ==== 监控 ====
metric.reporters=org.apache.kafka.common.metrics.JmxReporter
```

> 生产环境应把 `PLAINTEXT` 替换为 `SASL_SSL` 或 `SSL`,并配合 `security.protocol` / `sasl.mechanism` 等参数。

---

## 九、部署模式

### 9.1 单节点 KRaft (开发/测试)

```text
┌─────────────────────────────────────┐
│  单节点                             │
│  node.id=1                          │
│  process.roles=broker,controller    │
│  controller.quorum.voters=1@localhost:9093 │
└─────────────────────────────────────┘
```

适用场景:

- 本地开发环境
- Docker Compose 单节点验证
- CI/CD 集成测试

```properties
# 单节点完整配置示例
node.id=1
process.roles=broker,controller
listeners=PLAINTEXT://:9092,CONTROLLER://:9093
advertised.listeners=PLAINTEXT://localhost:9092
controller.listener.names=CONTROLLER
controller.quorum.voters=1@localhost:9093
log.dirs=/tmp/kraft-combined-logs
```

### 9.2 3 节点混合模式 (Broker + Controller)

```text
   ┌──────────────────────────────────────────────┐
   │            3 节点混合模式                       │
   ├──────────────────────────────────────────────┤
   │                                              │
   │   Node-1            Node-2            Node-3 │
   │   (Broker+          (Broker+          (Broker│
   │    Controller)       Controller)       +Ctrl)│
   │                                              │
   │   Kafka server  + Controller Quorum 共存    │
   │   同一 JVM 进程内                              │
   └──────────────────────────────────────────────┘
```

适用场景:

- **中小规模集群**(Broker 数 3~30)
- 不希望增加额外节点承担控制平面
- 集群机器资源富余

```properties
# Node-1 同时承担 Broker 和 Controller
node.id=1
process.roles=broker,controller
listeners=PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:9093
controller.listener.names=CONTROLLER
controller.quorum.voters=1@node1:9093,2@node2:9093,3@node3:9093
log.dirs=/var/lib/kafka/data
```

### 9.3 3 broker + 3 controller 分离模式 (生产推荐)

```text
   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
   │ Controller-1 │    │ Controller-2 │    │ Controller-3 │
   │ (process.    │    │ (process.    │    │ (process.    │
   │  roles=      │    │  roles=      │    │  roles=      │
   │  controller) │    │  controller) │    │  controller) │
   └──────┬───────┘    └──────┬───────┘    └──────┬───────┘
          │    Raft Quorum    │                   │
          └───────────────────┴───────────────────┘
                  │
                  │ Controller Quorum 提供元数据
                  ▼
   ┌──────────────────────────────────────────────────┐
   │                                                  │
   │ Broker-1    Broker-2    Broker-3    ...          │
   │              (process.roles=broker)              │
   │                                                  │
   └──────────────────────────────────────────────────┘
```

适用场景:

- **生产集群**(尤其是中大规模)
- 控制平面与数据平面隔离,故障域独立
- 控制节点可以小机器(2~4 核 / 8GB),Broker 节点大机器

### 9.4 三种部署模式对比

| 维度            | 单节点 KRaft          | 3 节点混合             | 3 Broker + 3 Controller 分离 |
|-----------------|----------------------|-------------------------|------------------------------|
| **节点总数**    | 1                    | 3                       | 6                            |
| **Broker 数**   | 1                    | 3                       | 3+                           |
| **Controller 节点数** | 1              | 3 (同 Broker)            | 3 (独立)                    |
| **容错能力**    | 0 节点失效            | 1 节点失效              | 1 Broker + 1 Controller    |
| **运维复杂度**  | 极低                  | 中                       | 较高                         |
| **资源隔离**    | 无                    | 弱                       | 强                          |
| **故障域**      | 单点                  | 重叠                     | 分离                        |
| **适用规模**    | 开发/测试             | 中小生产(< 100 Broker)  | 中大型生产(> 100 Broker)  |
| **生产可用**    | ✗                    | ✓                        | **✓ (官方推荐)**           |
| **是否官方推荐**| ✗                    | ✓                        | ✓✓                          |

### 9.5 单节点初始化

KRaft 单节点启动前必须先用 `kafka-storage.sh` 格式化:

```bash
# 1. 准备 server.properties
cat > /tmp/kraft.properties <<'EOF'
node.id=1
process.roles=broker,controller
listeners=PLAINTEXT://:9092,CONTROLLER://:9093
controller.listener.names=CONTROLLER
controller.quorum.voters=1@localhost:9093
log.dirs=/tmp/kraft-logs
EOF

# 2. 生成 cluster.id (首次启动元数据日志需要)
KAFKA_CLUSTER_ID="$(bin/kafka-storage.sh random-uuid)"

# 3. 格式化存储目录
bin/kafka-storage.sh format -t $KAFKA_CLUSTER_ID -c /tmp/kraft.properties

# 4. 启动
bin/kafka-server-start.sh /tmp/kraft.properties
```

---

## 十、ZooKeeper 迁移到 KRaft

### 10.1 为什么需要迁移

- Kafka 4.x 计划完全移除 ZK 模式
- ZK 集群已到扩展瓶颈
- 降低运维成本
- 享受 KRaft 性能提升

### 10.2 kafka-migration-tools

Confluent 提供的官方迁移工具集:

```text
┌──────────────────────────────────────────────────────────────────┐
│              kafka-migration-tools 工作流                          │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Step 1: 在现有 ZK 模式下运行,准备 export                         │
│    ↓                                                             │
│  Step 2: 用工具把 ZK 元数据导出为 KRaft 日志格式                  │
│    ↓                                                             │
│  Step 3: 停掉 ZK 模式控制器,启动 KRaft 模式                       │
│    ↓                                                             │
│  Step 4: 验证元数据一致性                                         │
│    ↓                                                             │
│  Step 5: 关闭 ZK 集群(可选保留一段时间)                          │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 10.3 迁移步骤

#### 10.3.1 步骤 1:导出 ZK 元数据

```bash
# 使用 KRaft Server 提供的"ZK 模式支持"导出元数据
# 在 KRaft 模式下启动 Kafka,但 process.roles 兼容 ZK 数据

kafka-migration-tools \
    --zookeeper-connect zk1:2181 \
    --output-dir /tmp/kraft-migration
```

#### 10.3.2 步骤 2:生成 cluster.id 并 format

```bash
# 用 ZK cluster.id 生成对应的 cluster.id
KAFKA_CLUSTER_ID="$(cat /tmp/kraft-migration/cluster-id)"

# 格式化所有 Controller 节点存储
kafka-storage.sh format -t $KAFKA_CLUSTER_ID \
    -c /opt/kafka/config/controller.properties
```

#### 10.3.3 步骤 3:启动 KRaft 集群

```bash
# 在所有节点上启动 Kafka(已切到 KRaft 模式)
kafka-server-start.sh /opt/kafka/config/controller.properties
```

#### 10.3.4 步骤 4:验证

```bash
# 列出 topic,确认数量与原 ZK 模式一致
kafka-topics.sh --bootstrap-server kafka1:9092 --list

# 检查 controller 状态
kafka-metadata-quorum.sh --bootstrap-server kafka1:9092 describe --status
```

### 10.4 数据保留

迁移过程中,**业务数据不会受影响**:

- 业务数据 (`业务 topic`) 在 Broker 磁盘上,与 ZK/KRaft 模式无关
- 仅元数据迁移(topic 列表、分区、副本、配置)
- 客户端需要更新 bootstrap.servers(从 ZK 地址改为 broker 地址)

| 数据类型       | 位置                | 迁移方式                                  |
|----------------|---------------------|------------------------------------------|
| 业务消息       | Broker log.dirs     | 不迁移                                   |
| 消费位点       | `__consumer_offsets` | 不迁移 (Broker 内部 topic)              |
| 事务状态       | `__transaction_state` | 不迁移                                   |
| 元数据         | `__cluster_metadata` | 从 ZK 导出并导入                        |

> 推荐保留原 ZK 集群一段时间,以便回滚;确认 KRaft 模式稳定后再下线 ZK。

---

## 十一、KRaft 故障恢复

### 11.1 Leader 故障

```text
正常状态:
   ┌──────────────┐  AppendEntries  ┌──────────────┐
   │   Leader     │ ──────────────▶ │  Follower-A  │
   │  (Node-1)    │                └──────────────┘
   │  term=3      │  AppendEntries  ┌──────────────┐
   │              │ ──────────────▶ │  Follower-B  │
   └──────────────┘                └──────────────┘

Node-1 故障 / 网络分区:
   ┌──────────────┐
   │   Node-1     │ ✗ 不可达
   │ (无响应)
   └──────────────┘

Follower-A & Follower-B:
   - election timeout 触发
   - 自增 term → Candidate
   - 互投 + 必投自己 → 多数派
   - 新 Leader 上任 (例如 Follower-A 胜出, term=4)
```

新 Leader 上任后:

1. 接管日志追加权
2. 继续响应客户端元数据请求
3. Follower-B 自动同步,最终追平

### 11.2 Follower 重连

```text
时间线:

   t0: Follower-B 网络闪断
   t0+ε: Follower-B 本地心跳超时,但还在容忍期
   t1: Follower-B 恢复网络
   t2: Follower-B 收到新 Leader-A 的心跳
   t3: Follower-B 自动 stepDown (若有角色切换),跟随新 Leader
   t4: Follower-B 拉取缺失日志,追上 commitIndex

   KRaft 设计:
     - 短暂重连: 自动追上
     - 长时间离线: Follower 落后太多,Leader 会发送 snapshot 文件
     - snapshot 后再追增量,直到一致
```

### 11.3 快照恢复

当 Follower 落后太多(超出 `retain.logRecords` 等),Leader 会:

1. 把本地最新 snapshot 发给该 Follower
2. Follower 加载 snapshot 重建状态
3. 从 snapshot 之后的 offset 增量追赶

```text
   Leader 状态:
     latest snapshot covers up to offset = 10000
     log retains offsets 10001~11000

   Follower 重连:
     its local offset = 5000  (严重落后)
     ⟹ Leader 发送 snapshot file (覆盖 0~10000)
     ⟹ Follower 加载 snapshot,本地 offset = 10000
     ⟹ Follower 继续拉取 10001~11000
     ⟹ 追上,正常服务
```

### 11.4 脑裂不可能发生

```text
网络分区 A-B / A-C 断开:

   A 单独成为少数派 (1 节点):
     - 不能写入 (够不到多数派)
     - 自动 stepDown (心跳发不出去)
     - 不影响 B+C 多数派继续服务

   即使 A 还以为自己是 Leader:
     - 客户端连接到 A 写入,会失败
     - 写入会被拒绝,避免旧 Leader 错误提交
     - 网络恢复后,A 自动 stepDown,追平多数派日志
```

Raft 的 Leader Completeness 保证了**脑裂期间不会出现两个 Leader 同时接受写入**。

### 11.5 故障恢复时间估算

| 故障场景               | 恢复时间 (3 节点)        |
|-----------------------|--------------------------|
| Controller Leader 切换 | 选举超时 1~3s + 日志确认 < 5s |
| Controller Follower 离线重连 | 几秒~几十秒 (取决于日志差距) |
| Controller 永久失效 | 重新组成 2 节点 quorum,持续可用 (可容忍 1 个再失效) |
| 整个 quorum 全失 | 集群不可用,但数据不丢,基于最后快照 + 日志恢复 |

---

## 十二、KRaft 监控

### 12.1 控制器状态监控

#### 12.1.1 命令行工具

```bash
# 查看当前 controller quorum 状态
kafka-metadata-quorum.sh --bootstrap-server broker1:9092 describe --status

# 输出示例:
# Cluster ID:     MK7l...
# Leader ID:      2
# Leader epoch:   14
# High watermark: 12345
# Max follower's lag: 100 (Follower 3 落后 100 条)

# 查看 quorum 成员
kafka-metadata-quorum.sh --bootstrap-server broker1:9092 describe --members

# 查看集群 ID
kafka-metadata-quorum.sh --bootstrap-server broker1:9092 cluster-id
```

#### 12.1.2 关键指标 (JMX / Prometheus)

| 指标                                       | 含义                          | 告警阈值              |
|--------------------------------------------|-------------------------------|----------------------|
| `kafka.controller:type=ControllerStats`   | 控制器通用统计                | -                    |
|   - `ActiveControllerCount`               | 当前 active 控制器 (1 或 0)  | 必须 = 1             |
|   - `TopicDeletionPerSec`                 | topic 删除速率               | -                    |
| `kafka.controller:type=ControllerMetadataCache` | 元数据缓存                | -                    |
| `kafka.controller:type=KafkaController`   | 控制器内部指标                | -                    |
| `kafka.server:type=ReplicaManager,name=UnderReplicatedPartitions` | 副本欠同步 | < 阈值            |
| `kafka.server:type=BrokerTopicMetrics,name=TotalProduceRequestsPerSec` | 生产请求 | - |

### 12.2 日志落后监控

```bash
# 使用 kafka-metadata-quorum.sh 监控 follower 落后情况
kafka-metadata-quorum.sh --bootstrap-server broker1:9092 describe --status

# 关注:
# - Max follower's lag: 最大滞后量
# - 高水位与落后 follower 之差

# 推荐告警:
# - MaxFollowerLag > 10000 (持续 1min) → 警告
# - MaxFollowerLag > 100000 (持续 5min) → 严重
```

```text
PromQL 示例:

# 单 follower 落后量
kafka_controller_quorum_lag{follower="3"}

# active controller 数(必须 = 1)
sum(kafka_controller_active_count) == 1
```

### 12.3 快照状态

```bash
# 查看快照目录
ls -lh /var/lib/kafka/controller-1/__cluster_metadata-0/
# 文件:
#   00000000000000000000.checkpoint
#   00000000000000001000-00000000000000002000.cleaned
#   meta.properties
#   snapshot/00000000-0000000000-0000001000/
```

| 监控项                   | 说明                                       |
|--------------------------|--------------------------------------------|
| `controller.snapshot.size` | 快照文件大小 (持续增长说明元数据膨胀)    |
| `controller.snapshot.lag`  | 触发快照的 lag 阈值                      |
| `controller.snapshot.age`  | 距上次快照的时间                          |

### 12.4 常见监控项清单

| 类别         | 关键指标                                              |
|--------------|--------------------------------------------------------|
| **Quorum 健康** | active controller、quorum 大小、leader epoch      |
| **延迟**        | metadata propagation latency、follower lag        |
| **日志**        | __cluster_metadata topic size、snapshot count    |
| **资源**        | Controller 进程 CPU、内存、磁盘 IO                |
| **可用性**      | active controller count (必须 = 1)               |
| **副本**        | UnderReplicatedPartitions (业务 topic)         |
| **请求**        | ControllerMutationsRate (元数据变更请求速率)   |

### 12.5 快速排障命令

```bash
# 1. 检查 quorum 状态
kafka-metadata-quorum.sh --bootstrap-server broker1:9092 describe --status

# 2. 检查 controller 选举情况
kafka-controller-names.sh --bootstrap-server broker1:9092

# 3. 查看日志
tail -f /var/log/kafka/server.log | grep -E "controller|quorum|raft"

# 4. 检查 JMX 端口
echo "stats" | nc broker1 9999 | grep controller

# 5. 列出 topic
kafka-topics.sh --bootstrap-server broker1:9092 --list

# 6. 看 broker 是否在元数据中
kafka-broker-api-versions.sh --bootstrap-server broker1:9092
```

---

## 十三、KRaft 限制与未来

### 13.1 当前限制

| 限制                              | 说明                                              |
|----------------------------------|---------------------------------------------------|
| **最大 Controller 节点数**        | 推荐 ≤ 7;实际常 3 节点                           |
| **不支持跨数据中心强同步**        | Raft 网络分区容忍有限,跨地域建议就近部署         |
| **大规模集群 readiness 不足**     | 数千 Broker 级别的运维经验相对 ZK 模式还较少     |
| **JMX 指标不够丰富**             | 比 ZK 模式少了一些熟悉指标名                     |
| **跨模式升级需要回滚预案**        | ZK ↔ KRaft 不能热切换                             |
| **Kafka 客户端元数据拉取频率**    | Broker 可被压垮(大量请求元数据时)               |
| **不支持 __consumer_offsets 扩展机制** | 仍由 Broker 内部管理,与 ZK 模式相同     |

### 13.2 KRaft vs ZooKeeper 性能基准(摘自官方博客)

```text
                ZK 模式         KRaft 模式         提升
metadata propagation   ~50ms         ~5ms            ~10x
topic creation         ~1s           ~50ms           ~20x
node registration      ~500ms        ~30ms           ~15x
peak metadata ops      ~10k/s        ~50k/s          ~5x
```

> 数据为官方 benchmark,实际因集群规模与网络环境而异。

### 13.3 未来发展

| 演进方向                              | 说明                                            |
|--------------------------------------|-------------------------------------------------|
| **元数据分层 (分层 KRaft)**            | 大集群元数据分片,进一步扩展                  |
| **自适应快照**                         | 基于增长率动态调整 snapshot 策略            |
| **更多的元数据优化**                   | 减少每次 metadata 推送量,降低带宽消耗         |
| **更智能的 controller 调度**          | 基于负载的 leader 重新选举                   |
| **跨集群联邦 / Multi-Region**         | 多 KRaft 集群之间互信                          |
| **进一步弱化 ZK 模式**                | 4.x 可能仅保留 KRaft 单一模式                 |

### 13.4 何时选 KRaft vs ZK

| 场景                                      | 建议                              |
|-------------------------------------------|-----------------------------------|
| 新建 Kafka 3.3+ 集群                       | **直接选 KRaft**                 |
| 既有 ZK 集群,且稳定                        | 暂不迁移,等下次升级再说          |
| 大量 topic、频繁扩容                        | **优先 KRaft**                   |
| 跨地域多 Kafka 集群                         | **KRaft**(每数据中心独立 quorum)|
| 仍在用 Kafka 2.x                           | 升级到 3.3+ 后迁移               |
| 强需求:迁移工具成熟度、运维文档覆盖度       | KRaft 已经很成熟,可上生产        |

---

## 十四、实战建议与陷阱

### 14.1 上线检查清单

```text
[ ] 1. 节点 ID 全局唯一,无冲突
[ ] 2. controller.quorum.voters 配置正确,节点可达
[ ] 3. controller.listener 端口未与 broker listener 冲突
[ ] 4. advertised.listeners 给客户端正确的 hostname/IP
[ ] 5. 各 controller 节点的 log.dirs 独立目录
[ ] 6. 网络端口 9093 在所有 controller 之间互通
[ ] 7. 时间同步 (NTP) 已配置
[ ] 8. 监控指标 (JMX / Prometheus) 已采集
[ ] 9. 告警阈值已设 (active controller = 1 等)
[ ] 10. 故障演练计划 (kill -9 控制器进程 → 5s 内恢复)
```

### 14.2 常见陷阱

| 陷阱                                       | 解决方案                                   |
|-------------------------------------------|------------------------------------------|
| `process.roles` 留空导致按 ZK 模式启动     | 显式设置 `broker,controller` 或 `controller` 之一 |
| `controller.quorum.voters` 漏配置         | 启动前必查                                  |
| 端口冲突                                  | controller.listener 与 broker listener 隔离端口 |
| 节点 ID 冲突                              | 全集群 ID 唯一 (ZK 模式可以冲突,KRaft 不能) |
| 未格式化存储直接启动                       | 必须先 `kafka-storage.sh format`            |
| 单点控制器部署在生产                       | 至少 3 节点,容忍 1 失效                   |
| snapshot 频繁触发                          | 调高 `controller.quorum.snapshot.size.max` |

### 14.3 调优参数推荐(生产 3 节点)

```properties
# 选举参数(网络稳定时保持默认,延迟敏感型可调)
controller.quorum.election.timeout.ms=1000
controller.quorum.fetch.timeout.ms=500

# 快照
controller.quorum.snapshot.lag.max=10000
controller.quorum.snapshot.size.max=2147483648   # 2GB

# 默认副本(可调)
offsets.topic.replication.factor=3
transaction.state.log.replication.factor=3

# JVM 堆 (Controller 节点一般 4~6GB 足够)
KAFKA_HEAP_OPTS="-Xms4G -Xmx4G"

# GC 推荐 G1
KAFKA_JVM_PERFORMANCE_OPTS="-XX:+UseG1GC -XX:MaxGCPauseMillis=20"
```

### 14.4 演练建议

```bash
# 演练 1: Kill current leader
ps -ef | grep kafka | grep node.id=1
kill -9 <pid>
# 观察: 新 leader 在 1-3s 内上任, 客户端基本无感

# 演练 2: 网络分区
# 用 iptables 模拟 controller-1 与 controller-2/3 断开
sudo iptables -A INPUT -s controller-2 -j DROP
sudo iptables -A OUTPUT -d controller-2 -j DROP
# 观察: controller-1 自动 stepDown,
#       多数派 2 节点 (controller-2 + 3) 继续服务

# 演练 3: 重启控制器节点
systemctl restart kafka
# 观察: 节点重新加入, 拉取 snapshot + 增量日志, 几分钟内一致
```

---

## 十五、核心要点速记

- **KRaft = Kafka Raft 模式**,核心是用 Raft 算法管理元数据,取代 ZK
- **生产可用**:Kafka 3.3 起官方生产推荐,4.0 起将成为唯一模式
- **替代 ZK**:消除双系统运维、性能瓶颈、扩展性受限
- **核心组件**:
  - Controller Quorum (Raft 节点集合)
  - `__cluster_metadata` 内部 topic (单分区、压缩策略)
  - 客户端通过 RPC 与 Quorum Leader 交互
- **核心角色**:
  - Leader (处理所有元数据变更)
  - Follower (复制日志、参与投票)
  - Candidate (选举期间的临时角色)
- **三个重要概念**:
  - Controller Quorum = Kafka Raft 节点集合
  - Term = 单调递增任期,每次选举自增
  - Log Entry = 一次元数据变更,AppendEntries 复制
- **Raft 三大保证**:
  - 选举安全 (每 Term 最多一个 Leader)
  - Leader 完整性 (新 Leader 必包含所有已提交条目)
  - 日志匹配 (相同 Index+Term 一定相同前缀)
- **选举流程**:
  - election timeout 触发 (随机化 1.5s~3s)
  - 自增 Term → 发 RequestVote
  - 多数派投票 = 当选 Leader
  - 日志新鲜度比较保证不丢已提交条目
- **日志复制**:
  - Leader 接收请求 → 追加 LogEntry
  - AppendEntries 并行复制给 Follower
  - 多数派持久化 → commitIndex 推进
  - 已提交的条目才能应用到状态机
- **快照机制**:
  - 定期 snapshot 压缩 `__cluster_metadata`
  - 新节点先拉 snapshot,再追增量日志
- **配置关键项**:
  - `process.roles` = broker / controller / broker,controller
  - `controller.quorum.voters` = id@host:port 列表
  - `node.id` 集群内必须唯一
  - `controller.listener.names` 单独 listener
- **部署模式**:
  - 单节点 (开发测试)
  - 3 节点混合 (中小生产)
  - **3 Broker + 3 Controller 分离 (大型生产推荐)**
- **迁移工具**: `kafka-migration-tools` 支持 ZK → KRaft
- **故障恢复**:
  - Leader 故障 → 1~3s 内新 Leader 上任
  - Follower 重连 → 拉取 missing log / snapshot
  - 脑裂不可能 (Raft 保证)
- **监控**:
  - `kafka-metadata-quorum.sh` 命令行
  - JMX `kafka.controller.*` 指标
  - **告警**: active controller 必须 = 1, follower lag 不能过大
- **未来**: 4.0+ 计划完全移除 ZK 模式,KRaft 成为唯一
- **生产建议**: 至少 3 Controller 节点、独立部署、监控健全、演练充分
- **常见错误**: `process.roles` 漏配、节点 ID 冲突、未 `kafka-storage.sh format` 就启动

---

## 十六、参考与延伸

- **Kafka 官方文档 (KRaft 模式)**: https://kafka.apache.org/documentation/#kraft
- **KIP-500**: Use KRaft for central coordination (移除 ZK 的核心设计)
- **KIP-630**: Kafka KRaft 模式协议细节
- **KIP-500 设计文档**: https://cwiki.apache.org/confluence/display/KAFKA/KIP-500%3A+Replace+ZooKeeper+with+a+Self-Managed+Metadata+Quorum
- **Apache Kafka 4.0 Release Notes** (ZK 模式废弃): https://kafka.apache.org/documentation/#upgrade_4_0
- **迁移工具仓库**: https://github.com/apache/kafka/tree/trunk/kafka-migration
- **运维教程 (Confluent)**: https://docs.confluent.io/platform/current/installation/configuration/kraft.html
- **Raft 论文 (Ongaro & Ousterhout 2014)**: https://raft.github.io/raft.pdf

---

> 本章系统讲解了 KRaft 一致性协议的设计、实现、配置与运维。KRaft 不是简单的"去 ZK",而是把 Raft 共识与 Kafka 日志系统深度融合。生产部署建议:优先 3 节点 Controller 分离模式、配置完善的监控告警、做好故障演练。
