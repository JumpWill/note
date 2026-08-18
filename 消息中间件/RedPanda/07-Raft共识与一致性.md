# RedPanda Raft 共识与一致性

> 本章系统讲解 RedPanda 内置的 Raft 共识层。RedPanda 从第一个版本起就把 Raft 作为系统级的一致性协议 —— 不仅用于元数据,还用于**每一条用户数据的副本**。理解 RedPanda Raft,既能看清它与 Kafka KRaft 的设计分野,也能体会它为什么能在不依赖 ZooKeeper 的同时,提供比 Kafka 更强的一致性保证。

## 一、RedPanda Raft 概述

### 1.1 什么是 RedPanda Raft

**RedPanda Raft** 是 RedPanda 内部实现的 **Raft 共识协议**。与 Kafka 在 2.8/3.3 阶段才补齐的 KRaft 不同,RedPanda 在诞生之初就把 Raft 写进了存储层和数据通路:

- **每一份数据分区 (Partition) 就是一个独立的 Raft Group**
- **集群元数据 (Cluster Metadata) 也是一个 Raft Group**(由 Controller 节点共同维护)
- **配置变更、成员变更、控制器选举**全部走 Raft
- **没有 ZooKeeper、没有 KRaft 的"过渡期",从 v1.0 起就是单一 Raft 控制平面**

> 一句话概括:**在 RedPanda 里,Raft 不是控制平面的补丁,而是数据平面的原生基石**。

### 1.2 RedPanda Raft 与 Kafka KRaft 的根本区别

这是理解 RedPanda 设计的入口。

| 维度                       | Kafka KRaft                                            | RedPanda Raft                                       |
|----------------------------|--------------------------------------------------------|-----------------------------------------------------|
| **首次引入**               | 2.8(实验)/ 3.3(生产),长期依赖 ZK                    | v1.0 起就内置,无 ZK 时代                          |
| **适用范围**               | **仅元数据**走 Raft                                     | **元数据 + 每条用户数据**都走 Raft                  |
| **用户数据副本协议**       | 主从复制 (Leader → Follower ISR)                       | **Raft 共识复制**(每条 record 走多数派确认)        |
| **数据一致性保证**         | acks=all 仅保证 ISR 副本收到,不保证持久化到多数派     | `acks=all` 即 Raft 已提交 = 多数派持久化           |
| **分区粒度**               | 一个分区 = 一个 ISR 集合(无独立 Raft 组)              | **一个分区 = 一个 Raft Group**                      |
| **集群成员**               | Controller Quorum 单独一组,Broker 仅拉元数据          | 每个分区都有自己 Raft 组,Controller 组单独存在    |
| **配置变更**               | Controller 写 __cluster_metadata 日志                 | Controller 走 Joint Consensus                      |
| **控制器**                 | 单独 KRaft quorum                                      | 单独 Raft group,但与数据通路同构                  |
| **故障切换**               | Controller 选举 + Broker 重连                          | Controller 选举 + **每分区可独立选举新 Leader**    |
| **运维负担**               | ZK → KRaft 过渡需迁移工具                              | 单系统,无迁移期                                    |

```text
�──────────────────────────────────────────────────────────────────────┐
│            Kafka vs RedPanda:Raft 的"用武之地"                       │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   Kafka KRaft           Raft 在哪?              ┌───────────────┐    │
│   ┌──────────────┐      仅元数据                │  __cluster_   │    │
│   │ Controller   │ ───────────────────────────▶ │  metadata     │    │
│   │ Quorum       │                             │  topic        │    │
│   └──────────────┘                             └───────────────┘    │
│                                                                      │
│   用户数据?                                                         │
│   ┌──────────────────────────────────────────────────────────┐      │
│   │  partition-p0  Leader ──pull──▶ Follower (主从复制)      │      │
│   │  partition-p1  Leader ──pull──▶ Follower (主从复制)      │      │
│   │  partition-p2  Leader ──pull──▶ Follower (主从复制)      │      │
│   └──────────────────────────────────────────────────────────┘      │
│                                                                      │
│   RedPanda Raft         Raft 在哪?                                  │
│   ┌──────────────┐      元数据 + 每个分区                           │
│   │ Controller   │ ───────────▶ metadata raft group                │
│   │ Group        │                                                  │
│   └──────────────┘                                                  │
│                                                                      │
│   用户数据?                                                         │
│   �──────────────────────────────────────────────────────────┐      │
│   │  partition-p0  ──── Raft Group ──── (3 副本共识)        │      │
│   │  partition-p1  ──── Raft Group ──── (3 副本共识)        │      │
│   │  partition-p2  ──── Raft Group ──── (3 副本共识)        │      │
│   └──────────────────────────────────────────────────────────┘      │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 1.3 内置共识,无需外部协调

RedPanda 从架构上彻底规避了"双系统"问题:

- **不依赖 ZooKeeper**:无外部进程、无独立 JVM、无双套监控
- **不依赖外部 KV 存储**:元数据走自己的 Raft group,数据走自己的 Raft group
- **不依赖第三方协调器**:成员变更、控制器选举、配置变更,全部由内置 Raft 完成
- **单二进制 `redpanda`**:一个进程同时承担 Broker、Controller、Raft 节点三种角色

```text
┌──────────────────────────────────────────────────────────────────┐
│                  RedPanda 单二进制多角色                          │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│   redpanda 进程 (Node-1)        redpanda 进程 (Node-2)         │
│   ┌──────────────────────┐      ┌──────────────────────┐         │
│   │ Broker 角色           │      │ Broker 角色           │        │
│   │ + Controller 角色     │      │ + Controller 角色     │        │
│   │ + Raft 节点           │      │ + Raft 节点           │        │
│   │   ├─ metadata group   │      │   ├─ metadata group   │        │
│   │   ├─ partition-p0     │      │   ├─ partition-p0     │        │
│   │   ├─ partition-p1     │      │   ├─ partition-p1     │        │
│   │   └─ ... (N 个组)     │      │   └─ ... (N 个组)     │        │
│   └──────────────────────┘      └──────────────────────┘         │
│                                                                  │
│   单进程,一份日志(分目录),一套配置(rp.yaml),一套监控           │
└──────────────────────────────────────────────────────────────────┘
```

---

## 二、Raft 在 RedPanda 中的应用

Raft 在 RedPanda 不是一个模块,而是横贯整个数据/控制平面的核心。三个层次都在用 Raft。

### 2.1 元数据共识

集群级元数据(Topic 列表、Partition 副本分配、ACL、配置变更)由 **Controller Group** 维护:

- Controller Group 是一个独立的 Raft Group
- 集群中部分节点扮演 Controller 角色(默认所有节点)
- 所有 Controller 节点通过 Raft 同步元数据
- 任何元数据变更必须经多数派 Controller 节点确认后才生效

```text
Controller Group (Raft Group: cluster-metadata)
   Node-1 (Controller) ◀──── AppendEntries ────▶ Node-3 (Controller)
        │                                                │
        └──────────────── AppendEntries ────────────────▶┘
                              │
                         Node-2 (Controller)

   - Topic 创建/删除 → Raft 日志条目
   - 分区重分配 → Raft 日志条目
   - ACL 变更 → Raft 日志条目
   - 配置变更 → Raft 日志条目
```

### 2.2 数据副本共识(Log Replication)

这是 RedPanda Raft 与 Kafka 最关键的差异:**每条用户数据走 Raft**。

- 一个 Partition = 一个 Raft Group
- Leader 接收生产请求,把 record 追加到 Raft 日志
- 通过 AppendEntries 复制给 Follower
- **多数派节点持久化后,Leader 才标记 commitIndex 并响应客户端**
- Follower 通过 `nextIndex` / `matchIndex` 维护复制状态

```text
Partition-p0 的 Raft Group:
   Node-A (Leader)  ──── AppendEntries ────▶  Node-B (Follower)
        │                                          │
        └────────── AppendEntries ────────────────▶│
                              │
                         Node-C (Follower)

   客户端写入 record:
     1. Leader 写入本地 log(未提交)
     2. 复制给 B、C
     3. 多数派 (含自己,2/3) 持久化成功
     4. Leader commitIndex++
     5. 响应客户端 OK
```

### 2.3 配置变更共识

集群成员变更、Topic 配置、副本因子调整都通过 Raft 日志条目落地:

- **添加节点**:产生 `add_node` 日志条目
- **移除节点**:产生 `remove_node` 日志条目
- **调整副本因子**:产生 `update_replicas` 日志条目
- **配置参数变更**:产生 `update_config` 日志条目

每条变更都要在对应 Raft Group 中走完"提出 → 多数派确认 → 提交 → 应用"的完整流程。

| 层级       | Raft Group 数量                  | 共识内容                               |
|------------|---------------------------------|----------------------------------------|
| 元数据层   | 1 个(Controller Group)         | Topic/Partition/ACL/Config 元数据     |
| 数据层     | N 个(每 Partition 一个)         | 用户记录的复制与提交                   |
| 配置层     | 嵌入到各 Raft Group              | 节点成员、副本集、配置参数             |

---

## 三、RedPanda Raft Group 概念

### 3.1 一个集群有多个 Raft Group

RedPanda 集群中,Raft Group 的数量等于**分区总数 + 1(Controller Group)**:

- **1 个 Controller Group**:管理整个集群的元数据
- **N 个 Partition Group**:每个 Partition 独立一个 Raft Group

```text
RedPanda 集群 (3 节点)
�──────────────────────────────────────────────────────────────────┐
│                                                                  │
│   Controller Group (Raft Group 0)                                │
│   ┌─────────┐   ┌─────────┐   ┌─────────┐                       │
│   │ Node-1  │   │ Node-2  │   │ Node-3  │                       │
│   │ (Leader)│   │         │   │         │                       │
│   └─────────┘   └─────────┘   └─────────┘                       │
│                                                                  │
│   Partition-p0 Raft Group (Raft Group 1)                         │
│   ┌─────────┐   ┌─────────┐   ┌─────────┐                       │
│   │ Node-1  │   │ Node-2  │   │ Node-3  │                       │
│   │         │   │ (Leader)│   │         │                       │
│   └─────────┘   └─────────┘   └─────────┘                       │
│                                                                  │
│   Partition-p1 Raft Group (Raft Group 2)                         │
│   ┌─────────┐   �─────────┐   ┌─────────┐                       │
│   │ Node-1  │   │ Node-2  │   │ Node-3  │                       │
│   │         │   │         │   │ (Leader)│                       │
│   └─────────┘   └─────────┘   └─────────┘                       │
│                                                                  │
│   Partition-p2 Raft Group (Raft Group 3)                         │
│   ┌─────────┐   ┌─────────┐   ┌─────────┐                       │
│   │ Node-1  │   │ Node-2  │   │ Node-3  │                       │
│   │ (Leader)│   │         │   │         │                       │
│   └─────────┘   └─────────┘   └─────────┘                       │
│                                                                  │
│   ... 还有几百到几千个 Raft Group                                │
└──────────────────────────────────────────────────────────────────┘
```

### 3.2 每个 Partition 一个 Group

这种"一 Partition 一 Group"的设计带来几个直接好处:

| 好处             | 说明                                                       |
|------------------|------------------------------------------------------------|
| **故障隔离**     | 一个分区的 Leader 故障,只影响该分区;其他分区继续服务      |
| **Leader 分散**  | 不同分区 Leader 分布在不同节点,负载更均衡                  |
| **扩展性**       | 节点增加 = 分区可被重新分配到新节点,Raft 自动复制          |
| **独立选举**     | 每个 Group 各自 Term,互不干扰                              |
| **并行复制**     | 不同 Group 之间完全独立,Leader 故障切换可并发进行          |

```text
为什么"一 Partition 一 Group"很关键?

   假设 Kafka 的做法 (一个 Broker 多分区 Leader):
     - Broker-1 挂了 → Broker-1 上的所有 Leader 都要切走
     - 切换期间这些分区都不可写 (元数据变更 + 主从切换)
     - 切到 Broker-2/Broker-3 后,新 Leader 接管

   RedPanda 的做法 (每分区独立 Raft Group):
     - Broker-1 挂了 → 该节点上每个分区 Group 独立触发选举
     - 每个 Group 选新 Leader,可能分散到不同节点
     - 单分区不可用时间仅几秒,影响面小
```

### 3.3 与 Kafka KRaft 的 Metadata Group 对比

| 维度               | Kafka KRaft                                 | RedPanda Raft                                |
|--------------------|---------------------------------------------|----------------------------------------------|
| **元数据组**       | 1 个 `__cluster_metadata` topic(单分区)   | 1 个 Controller Raft Group(逻辑组)         |
| **用户数据组**     | � 不存在(Kafka 用户数据走主从复制)         | ✅ N 个 Partition Raft Group               |
| **成员**           | 节点级:Controller Quorum                   | 分区级:每个 Partition 有自己的成员集        |
| **Leader 粒度**    | 整个集群 1 个 Controller Leader            | 每个 Partition 都有自己的 Leader            |
| **故障切换粒度**   | 整集群(Controller 切换影响所有元数据)     | 逐分区(单分区 Leader 切换不影响其他分区)   |
| **共识协议**       | 仅元数据走 Raft,数据走 ISR                | 元数据 + 数据都走 Raft                       |

---

## 四、选举流程

### 4.1 节点三种状态

每个 Raft Group 内的节点都遵循经典 Raft 的三态模型:

| 状态         | 行为                                                                                       |
|--------------|--------------------------------------------------------------------------------------------|
| **Follower** | 被动接收 Leader 的 AppendEntries/心跳;选举超时未收到心跳则变 Candidate                     |
| **Candidate**| 自增 Term,发起 RequestVote;获得多数票转 Leader,发现更高 Term 转 Follower                 |
| **Leader**   | 接收请求、追加日志、复制给 Follower、周期性发心跳;发现更高 Term 自动 stepDown 到 Follower |

```text
                election timeout 触发                收到多数派投票
   ┌─────────� ───────────────────▶ ┌─────────┐ ───────────────────▶ ┌─────────┐
   │Follower │                      │Candidate│                      │ Leader  │
   └─────────┘ ◀─────────────────── └─────────┘ ◀─────────────────── └─────────┘
       ▲            发现更高 Term         │            stepDown            │
       │                                  │            发现更高 Term        │
       │                                  └────────────────────────────────┘
       │                                          Term 递增
       │   收到 AppendEntries (心跳或日志)
       └─────────────────────────────────────────────
```

### 4.2 PreVote 优化

RedPanda 实现的是带 **PreVote** 优化的 Raft(也称为 Raft 论文 §9 的扩展)。PreVote 解决了经典 Raft 在网络分区恢复后的"无效选举风暴"问题。

```text
经典 Raft 的问题:
   1. Node-A 跟集群网络分区
   2. Node-A 收不到心跳,选举超时
   3. Node-A 自增 Term,发起 RequestVote
   4. 但多数派不可达,选举失败
   5. Term 已经增加 → Node-A 回到 Follower 后,
      会用更高的 Term 干扰集群(迫使合法 Leader stepDown)

PreVote 的解决:
   1. Node-A 选举超时,先发 PreVote(不增 Term)
   2. 询问其他节点:"如果我现在发起选举,你会投我吗?"
   3. 仅当获得多数 PreVote 同意,才真正自增 Term 并发起 RequestVote
   4. 网络分区中的 Node-A 拿不到 PreVote 多数 → 不真正增 Term → 不干扰集群
```

| 对比项     | 经典 Raft        | Raft + PreVote (RedPanda)         |
|------------|------------------|-----------------------------------|
| Term 增长  | 选举超时即增     | 仅在 PreVote 通过后才增           |
| 分区影响   | 反复增 Term      | 分区节点不污染集群 Term           |
| 选举开销   | 较高            | 略低(失败的 PreVote 不留痕)     |
| 集群收敛   | 慢              | 快                                |

### 4.3 选举超时随机化

为避免**Split Vote**(多节点同时发起选举,谁都拿不到多数票),RedPanda 把选举超时**随机化**:

```text
Follower 视角:

   t = 0                                  t = T_election (随机)
   │                                      │
   │  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ▶ │  election timeout 触发
   │                                      │
   │  若期间收到 Leader 心跳              │  自增 Term → Candidate
   │  ⟹ 重置超时,继续保持 Follower        │  发 RequestVote RPC
   │                                      │

   T_election 在 [election_timeout_base_ms, 2×election_timeout_base_ms] 之间随机
   典型默认:base = 1500ms → 实际范围 1500~3000ms
```

```text
为什么需要随机?

   假设所有节点超时都是 1500ms 整:
     t=0    A 收不到心跳
     t=0    B 收不到心跳
     t=0    C 收不到心跳
     → A、B、C 同时发起 Term=N 选举
     → 各自拿到 1 票(含自己)
     → 选举失败,再来一轮 Term=N+1 同时发起
     → 永远分票

   随机化后:
     t=0~3000ms 之间各自触发
     → 先触发的节点拿到多数票,当选 Leader
     → 其他节点收到新 Leader 心跳,放弃选举
```

### 4.4 Term 递增

**Term (任期)** 是 Raft 的逻辑时钟:

- 每次成功选举开始一个新 Term
- 同一 Term 内至多一个 Leader
- Term 单调递增,作为全局事件顺序标识

```text
Term 1              Term 2              Term 3
┌──────────────────┐ ┌──────────────────� ┌──────────────────┐
│  Leader: A       │ │  Leader: B       │ │  Leader: A       │
│  (稳定期)        │→│  (A 故障,B 胜出) │→│  (B 故障,A 回归) │
└──────────────────┘ └──────────────────┘ └──────────────────┘
       ↑                  ↑                     ↑
   election            election             election
   timeout 触发? no     timeout 触发? yes    timeout 触发? yes

每个 Term 内只能有一个 Leader;
Term 是单调递增的逻辑时钟,保证全局事件顺序。
```

Term 的语义:

- **单调递增**:每次选举 term 自增
- **去重过期请求**:旧 Term 的请求会被新 Term 拒绝
- **投票规则**:同一 Term 内每个节点最多投一票
- **Leader stepDown**:Follower 收到更高 Term 的请求时,Leader 自动 stepDown

### 4.5 投票规则

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

- **一 Term 一票**:同一 Term 内只能投一次,投过即记忆(`votedFor`)
- **日志新鲜度门槛**:候选人的日志必须 ≥ 自己,否则不投
- **保证 Leader Completeness**:从源头杜绝"丢已提交日志的 Leader 当选"
- **PreVote 阶段**:在真正增 Term 前先问一圈"能否当选"

### 4.6 Leader Lease vs 选举

RedPanda 在经典 Raft 的基础上,默认启用 **Leader Lease(Leader 租约)** 机制来减少不必要的选举:

```text
经典 Raft 的"读到旧 Leader"风险:

   1. Leader A 在 term=5 当选,继续接受写入
   2. 网络分区:A 与 B/C 断开
   3. B、C 在 term=6 选出 B 为新 Leader
   4. A 这边网络恢复前仍以为自己是 Leader,继续响应读请求
   5. 如果 A 不再写新日志,可能会响应"过期"的读
      → 客户端读到旧数据 (读到旧 Leader 的状态)

Leader Lease 的解决:

   1. Leader 上任后,在自己的 lease 期间内(远小于 election timeout)
      不允许发起选举、也不接受其他节点的 RequestVote
   2. A 在 lease 期间不会 stepDown,也不会参与投票
   3. lease 到期前必须续租(收到多数派心跳确认)
   4. 即使 A 短暂分区,lease 也能保证 A 在 lease 内不"误服务"
   5. 实际上 RedPanda 通过 "Read Index" + "Lease" 配合实现线性一致性读
```

Leader Lease 与选举的关系:

| 机制               | 作用                                       | 风险与代价                  |
|--------------------|--------------------------------------------|-----------------------------|
| **选举**           | 选新 Leader,接管写入                      | 短暂不可写                  |
| **Lease**          | 抑制不必要的 stepDown                      | 极端情况下延迟切换          |
| **Read Index**     | 保证读到最新提交的数据                     | 多一跳 RTT                  |
| **Follower Read**  | 允许 Follower 处理读,降低读延迟           | 一致性需配置                |

### 4.7 选举相关的常见误区

```text
误区 1:"网络慢 = 频繁选举"

   真相:election timeout 远大于典型 RTT
   - 默认 election_timeout_ms = 1500
   - 即使 RTT 200ms,也要经过 1500ms 才触发选举
   - 慢网络更多表现为 commit 慢,而不是选举多

误区 2:"PreVote 会让选举变慢"

   真相:PreVote 只在"选举失败"时增加一轮 RPC
   - 成功选举 PreVote 与经典 Raft 几乎无差
   - 网络分区节点不再"无效增 Term",整体更稳

误区 3:"Term 一直涨 = 集群不稳定"

   真相:Term 单调递增,只要不频繁大幅跳变就是健康的
   - Term 涨一次表示一次成功的选举周期
   - 长时间不涨说明没有新选举(可能意味着集群稳定)
   - 频繁大幅跳变(如 1 分钟涨 5 次)才是异常

误区 4:"节点越多选举越慢"

   真相:选举延迟主要取决于超时随机区间与网络 RTT
   - 多数派投票是并行发起的
   - 节点多反而可能更快达到多数派(容错更高)
   - 5 节点集群容忍 2 节点失效,选举速度并不比 3 节点慢
```

### 4.8 RedPanda Raft 选举完整时序图

```text
===========================================================================
        RedPanda Partition Raft Leader Election (含 PreVote)
===========================================================================

  Follower-A (Node-1)  Follower-B (Node-2)  Follower-C (Node-3)
        │                    │                    │
        │   (稳定期, Term = 5, Leader = A)       │
        │                    │                    │
        │ ←── heartbeat ─────│←───────────────────│
        │ ←── heartbeat ─────│←───────────────────│
        │ ←── heartbeat ─────│←───────────────────│
        │                    │                    │
        │     ✗ A 故障 / 网络分区                │
        │                    │                    │
   t1   │  election timeout  │  election timeout  │  election timeout
   t2   │  (随机)            │  (随机化)          │  (随机化)
        │                    │                    │
        │  -- PreVote ──────▶ │                   │
        │   term=5           │                   │
        │   (不增 Term)        │                   │
        │              B 收到 PreVote            │
        │              ├── term 检查 OK(5=5)     │
        │              ├── 日志新鲜度 OK         │
        │              └── grant pre-vote        │
        │                    │                   │
        │  ←── pre-vote ─────┤                   │
        │                    │                   │
        │  -- PreVote ─────────────────────▶    │
        │                    │                   │
        │                    │             C 收到 PreVote
        │                    │             ├── term 检查 OK
        │                    │             ├── 日志新鲜度 OK
        │                    │             └── grant pre-vote
        │                    │                   │
        │  ←─────── pre-vote ───────────────────┤
        │                    │                   │
        │  PreVote 多数 OK,真正发起 RequestVote │
        │  自增 Term 5 → 6                       │
        │                    │                   │
        │  -- RequestVote ──▶ │                   │
        │   term=6,          │                   │
        │   lastLogIndex/    │                   │
        │   lastLogTerm      │                   │
        │              B 收到 RequestVote        │
        │              ├── 6 > 5 ✓              │
        │              ├── 日志新鲜度 OK         │
        │              ├── votedFor=A           │
        │              └── grant vote           │
        │                    │                   │
        │  ←── vote granted ─┤                   │
        │                    │                   │
        │  -- RequestVote ─────────────────▶    │
        │                    │                   │
        │                    │             C 收到 RequestVote
        │                    │             ├── 6 > 5 ✓
        │                    │             ├── 日志新鲜度 OK
        │                    │             ├── votedFor=C
        │                    │             └── grant vote
        │                    │                   │
        │  ←─────── vote granted ───────────────┤
        │                    │                   │
   t3   │  A 收到 3 票 (B+C+自己) = 多数派     │
        │                    │                   │
        │              A 成为 Leader            │
        │              term = 6                 │
        │                    │                   │
        │  ── AppendEntries (heartbeat) ─────▶ │
        │  ── AppendEntries (heartbeat) ─────────▶
        │                    │                   │
        │              B/C 更新 term=6         │
        │              进入稳定期              │
===========================================================================
关键设计点:
  1. PreVote 避免网络分区节点干扰 Term
  2. 随机 timeout 避免 split vote
  3. 一 Term 一票 (votedFor 记忆)
  4. 日志新鲜度比较保证 Leader Completeness
  5. 多数派 = ⌊N/2⌋+1 = 2 (3 节点 quorum)
===========================================================================
```

---

## 五、日志复制

### 5.1 Leader 复制到 Follower

数据通路的核心:Leader 接收生产请求 → 写入本地日志 → 复制到 Follower → 多数派确认 → 提交。

```text
===========================================================================
              RedPanda 数据通路:AppendEntries 时序
===========================================================================

Client           Leader (Node-1)      Follower (Node-2)    Follower (Node-3)
   │                  │                      │                      │
   │  Produce req     │                      │                      │
   │  records=[r5]    │                      │                      │
   │ ─────────────▶   │                      │                      │
   │                  │  appendEntry         │                      │
   │                  │  index = 12          │                      │
   │                  │  term  = 6           │                      │
   │                  │                      │                      │
   │                  │ ─── AppendEntries ──▶ │                      │
   │                  │   prev=11,term=6     │                      │
   │                  │   entries=[r5]       │                      │
   │                  │                      │                      │
   │                  │                      │ 校验 prev 匹配      │
   │                  │                      │ 持久化到磁盘         │
   │                  │                      │ 更新 commit (待)    │
   │                  │ ◀──── success ───────│                      │
   │                  │     index=12         │                      │
   │                  │                      │                      │
   │                  │ ─── AppendEntries ──────────────────────▶    │
   │                  │                      │                      │
   │                  │                      │                      │ 校验 prev
   │                  │                      │                      │ 持久化
   │                  │ ◀────────── success ────────────────────────│
   │                  │          index=12    │                      │
   │                  │                      │                      │
   │                  │ 多数派 (1+2 或 1+3) 持久化成功               │
   │                  │ commitIndex = 12     │                      │
   │                  │ 应用到状态机         │                      │
   │                  │                      │                      │
   │ 响应 Client OK   │                      │                      │
   │ ◀───────────────│                      │                      │
   │                  │                      │                      │
   │                  │ 后续心跳 / 日志      │                      │
   │                  │ ── AppendEntries ──▶ │ (带 leaderCommit=12)│
   │                  │                      │ 应用 index=12        │
   │                  │ ── AppendEntries ──────────────────────▶    │
===========================================================================
```

### 5.2 心跳 + AppendEntries 复用

RedPanda 心跳并不是独立报文,而是与 AppendEntries 复用同一条通道:

```text
Leader → Follower 的 RPC 只有两种:

   1. AppendEntries(entries=[...], heartbeat=false)
        - 携带实际日志条目
        - Follower 必须持久化

   2. AppendEntries(entries=[], heartbeat=true)
        - 空 entries,纯心跳
        - Follower 仅刷新选举超时,无需写盘

两者的逻辑路径完全一致,Leader 只是用 entries 是否为空来切换用途。
这样实现的好处:
   - 一份网络收发代码
   - 心跳与日志复制同节拍,减少网络包数
   - 失败处理逻辑统一
```

### 5.3 Pipeline / Batch 优化

RedPanda 在经典 Raft 上叠加了几个工程优化,把日志复制推到接近网卡极限:

```text
┌──────────────────────────────────────────────────────────────────┐
│                 RedPanda 日志复制优化                            │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Pipeline(流水线)                                              │
│     Leader 不等 Follower 确认就发下一批                           │
│     ⇒ 网络 RTT 不再是关键路径                                    │
│                                                                  │
│  2. Batch(批量化)                                                 │
│     多条 record 打包成一个 AppendEntries                         │
│     ⇒ 摊薄每条 record 的 RPC 头开销                              │
│                                                                  │
│  3. Zero-Copy(零拷贝)                                            │
│     AppendEntries 直接指向 page cache,避免用户态拷贝             │
│     ⇒ 减少 CPU 与内存带宽消耗                                    │
│                                                                  │
│  4. 共享内存传输(节点内副本)                                     │
│     同一节点上不同 Raft Group 之间通过内存共享                   │
│     ⇒ 减少序列化/反序列化                                       │
│                                                                  │
│  5. 异步 fsync                                                    │
│     Leader 在写入 page cache 后即可响应客户端 ack                │
│     (commit 仍须等多数派持久化)                                  │
│     ⇒ 降低磁盘延迟对延迟的影响                                   │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 5.4 复制流程的状态机

Leader 维护每个 Follower 的两个关键游标:

```text
Leader 视角:

   For each Follower F:
     nextIndex[F]  ── 下一次要发给 F 的起始 index
     matchIndex[F] ── 已知 F 已确认的最高 index

   初始:
     matchIndex[F] = 0
     nextIndex[F]  = Leader.lastLogIndex + 1

   每次 AppendEntries 成功:
     matchIndex[F] = max(matchIndex[F], 返回的 index)
     nextIndex[F]  = matchIndex[F] + 1

   每次 AppendEntries 失败(日志不匹配):
     nextIndex[F] -= 1   (回退重试)

   commitIndex 推进:
     if ∃ N such that N > commitIndex and
        matchIndex[F] ≥ N for majority of followers:
        commitIndex = N
```

---

## 六、快照(Snapshot)

### 6.1 为什么需要快照

Raft 日志只增不减,长期运行的集群会累积:

- **大量已应用的状态机条目**(对 Raft 已无价值)
- **磁盘膨胀,启动时全量重放耗时长**
- **Follower 落后太多时,追赶成本高**

快照 = **把"已应用的状态"打成包,丢弃其前面的日志**。

### 6.2 何时触发快照

RedPanda 在每个 Raft Group 上按阈值触发本地快照:

| 触发条件 (默认)         | 说明                                              |
|------------------------|---------------------------------------------------|
| `raft_snapshot_max_size` | 快照文件最大字节数(默认 1 GB)                  |
| `raft_snapshot_period`   | 两次快照最短间隔(默认 60s)                     |
| 节点重启               | 启动时若发现日志不连续,优先用快照重建            |

```text
快照触发示意:

   日志累积增长:
   ─────────────────────────────────────────▶
   Index:  1   100   200   300   ...   50000   50001   50010
                                              │
                                          触发快照 (已应用 50000)
                                              │
                                              ▼
                                          快照文件:覆盖到 index=50000
                                          保留:50001~50010 增量日志

   后续写入从 50011 开始
```

### 6.3 快照传输给 Follower

当 Follower 落后过多(`nextIndex` 已经回退到 Leader 的快照点之前),Leader 会发快照代替日志:

```text
Leader 视角:
   Follower.nextIndex = 1000
   Leader.snapshot.lastIndex = 50000
   → 1000 < 50000,Follower 需要先接收快照

流程:
   1. Leader 调 InstallSnapshot RPC
   2. Follower 收到后写入本地快照文件
   3. Follower 用快照覆盖到本地状态机
   4. Follower 的 log 起点 = snapshot.lastIndex + 1
   5. Follower 继续从 Leader 拉取增量日志
```

```text
InstallSnapshot vs AppendEntries 的关系:

   AppendEntries(entries=...):
     适合差距小 → 一条条日志追

   InstallSnapshot(snapshot):
     适合差距大 → 先用快照重建,再追增量

   阈值由 Leader.nextIndex 与 Leader 的快照点决定
```

---

## 七、数据一致性保证

### 7.1 Raft 三大保证

RedPanda Raft 完整继承 Raft 的三大安全性保证。

#### 7.1.1 选举安全 (Election Safety)

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

#### 7.1.2 Leader 完整性 (Leader Completeness)

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

#### 7.1.3 日志匹配 (Log Matching)

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

### 7.2 已提交位点 (commitIndex)

```text
Log 状态:

  Leader 节点 (Node-1):
  Index:  1   2   3   4   5   6   7   8   9   10
  Term:   1   1   2   2   3   3   3   3   -   -
  Status: C   C   C   C   C   C   C   C   -   -
                                  ^commitIndex=8 (已提交)

  Follower-A (Node-2):
  Index:  1   2   3   4   5   6   7   8
  Term:   1   1   2   2   3   3   3   3
  Status: C   C   C   C   C   C   C   C ✓
                      已同步到 8

  Follower-B (Node-3, 落后):
  Index:  1   2   3   4   5   6   7
  Term:   1   1   2   2   3   3   3
  Status: C   C   C   C   C   C   C
            还需要 Index=8 才能 apply
            Leader 下次 AppendEntries 就会带过来
```

```text
注意:
   C = 已 commit 且已 apply 到状态机
   只有 commitIndex 之前的条目对消费者可见
   commitIndex 之后的条目,即使在 Leader 上存在,也不能视作"已确认"
```

### 7.3 已提交 ≠ 已复制到所有节点

| 状态           | 含义                                                    | 客户端可见 |
|----------------|--------------------------------------------------------|-----------|
| 未持久化       | Leader 内存中,未写盘                                   | ❌        |
| 已持久化       | Leader 磁盘上,未复制                                  | ❌        |
| **已提交**     | **多数派节点都已持久化**(包括 Leader)                | **✅**    |
| 已应用         | 已应用到本地状态机                                     | ✅(只读) |

```text
重要:RedPanda 与 Kafka 的关键区别

   Kafka acks=all:
     只保证 ISR 集合里的副本都收到了
     ISR 集合大小可配置(可能 < 多数派)
     若 ISR=2 而 RF=3,可能只写 2 副本就 ack,丢失时数据真的丢

   RedPanda acks=all (默认):
     等价于 Raft 已提交 = 多数派持久化
     真正符合"commit"的语义
     不会有"已 ack 但数据可能丢"的情况
```

### 7.4 线性一致性读 (Linearizable Read)

RedPanda 支持客户端的强一致性读,这是 Raft 协议相对主从复制的隐性优势:

```text
普通读流程 (Follower Read,可配置):
   1. 客户端向任一副本发读请求
   2. 副本返回当前本地日志中的最新数据
   3. 延迟低,但可能读到"旧数据"(其他 Follower 可能更落后)

线性一致性读 (默认行为,可配置):
   1. 客户端向 Leader 发读请求
   2. Leader 记录当前 commitIndex 作为 "read_index"
   3. Leader 向 Follower 发心跳确认自己仍是 Leader
       (确认多数派还认自己为 Leader)
   4. Leader 等待直到 lastApplied ≥ read_index
   5. 返回数据

为什么第 3 步重要?
   - 如果 Leader 已经 stepDown 但还不知道,
     它返回的"最新数据"可能已经被新 Leader 覆盖
   - 第 3 步确认"我仍是 Leader",保证读到的是真最新
   - 这相当于一次 RTT,但语义极强:任何时刻看到的写都"已生效"
```

客户端配置示例(Java Kafka 客户端):

```java
// 默认:isolation.level=read_uncommitted,客户端从 Leader 读
props.put("isolation.level", "read_committed");
props.put("max.poll.records", 500);
```

### 7.5 Follower Read 降低读延迟

```text
场景:读多写少,延迟敏感

   默认行为:所有读都走 Leader
     - 强一致,但读延迟 = Leader 节点往返
     - 热点 Leader 节点压力大

   Follower Read 开启:
     - 客户端可配置从 Follower 读
     - 延迟 = 离客户端最近的副本
     - 但可能读到略旧数据(数 ms ~ 数 s)

   RedPanda 配置:
     kafka_api: ...   # 无需修改
     admin: ...       # 无需修改
     # 客户端层面:
     # client.rack  + replication factor ≥ 3
     # 自然实现就近读
```

### 7.6 一致性级别对比

| 一致性级别                | 读延迟 | 数据新鲜度          | 适用场景                  |
|---------------------------|--------|---------------------|---------------------------|
| **Linearizable (默认)**   | 较高   | 100% 最新           | 金融交易、订单状态        |
| **Follower Read**         | 低     | 略旧(数 ms)        | 日志查询、监控指标        |
| **Snapshot Read (旧)**    | 极低   | 可能较旧(秒~分)    | 历史数据查询、报表        |

---

## 八、Controller 角色

---

## 八、Controller 角色

### 8.1 Controller 与 Metadata Raft Group

RedPanda 的 **Controller 角色**与 **Metadata Raft Group** 同源:

- 集群中部分节点是 Controller(默认所有节点)
- 这些 Controller 共同构成 Metadata Raft Group
- Group 内自动选主,选出 Controller Leader
- Controller Leader 处理所有集群级元数据变更

```text
Controller Raft Group:
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│   Node-1 (Controller+Leader) �── 集群元数据写入                  │
│   Node-2 (Controller+Follower)                                   │
│   Node-3 (Controller+Follower)                                   │
│                                                                  │
│   Node-4 (Controller+Follower)   ← 集群扩到 4 节点时             │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

   Controller Leader 责任:
     - 接收所有元数据变更请求 (create topic / alter partition / ...)
     - 把变更追加到 metadata Raft 日志
     - 多数派确认后 commit,应用到本地 metadata cache
     - 通知其他节点元数据更新
```

### 8.2 Controller 与 Kafka Controller 的对比

| 维度               | Kafka Controller                                  | RedPanda Controller                            |
|--------------------|---------------------------------------------------|------------------------------------------------|
| **节点**           | KRaft quorum(节点级)                            | 一组 Controller 节点(默认所有 redpanda 节点) |
| **选举**           | KRaft(基于 `__cluster_metadata` topic)         | 内置 Raft(基于 metadata group)                |
| **职责**           | 仅元数据                                         | 元数据 + 配置 + 集群成员                       |
| **数量**           | 3/5 个 Controller                                | 默认所有节点(可配置)                          |
| **Leader 切换**    | 影响元数据写入(数据写入不阻塞)                  | 影响元数据写入(数据写入不阻塞)                |

### 8.3 Controller Leader 故障转移

```text
正常情况:
   Node-1 (Controller Leader)
   Node-2 (Controller Follower)
   Node-3 (Controller Follower)

故障转移:
   t=0  Node-1 crash
   t=0~3s  Node-2、Node-3 election timeout (随机)
   t=3s  Node-2 先触发,PreVote → RequestVote
   t=3.5s  Node-3 投票给 Node-2
   t=3.5s  Node-2 拿到 2 票(自己+Node-3)=多数派 → 当选新 Leader
   t=4s   Node-2 开始处理元数据写入
   t=???  Node-1 重启,自动加入为 Follower,追平日志

   元数据写入中断窗口:典型 3~5s
   数据写入不受影响(每个 Partition 自己有 Leader)
```

```text
Controller Leader 切换 vs Partition Leader 切换:

   Controller Leader 切换:
     - 仅影响元数据写入(创建 topic、调整 partition 等)
     - 数据生产/消费不受影响
     - 切换期间元数据变更排队等候

   Partition Leader 切换:
     - 仅影响该 Partition 的写入
     - 其他 Partition 不受影响
     - 切换期间该分区不可写(通常 < 5s)

   两者完全解耦:集群可以同时有多个 Controller 切换 + 多个 Partition 切换并行进行
```

---

## 九、配置变更

### 9.1 联合共识(Joint Consensus)

RedPanda 在变更 Raft Group 成员时,使用 **Joint Consensus(联合共识)**。这个机制确保在成员变更期间不会同时出现两个 Leader:

```text
Joint Consensus 的两阶段:

阶段 1:C(old, new) (Joint Consensus / 联合配置)
   - 日志条目同时描述 old 和 new 成员集
   - 提交时,需要 old 多数派 ∩ new 多数派同时确认
   - 一旦提交,后续日志条目同时使用 C(old, new) 决策

阶段 2:C(new) (新配置)
   - 日志条目描述新成员集
   - 提交时,只需 new 多数派确认
   - 提交后,完全切换到 C(new)

为什么要两阶段?
   - 单步变更会导致"同一 Term 内两个 Leader"的可能
   - 比如:3 节点加 1 节点变 4 节点,单步切的话
     3 节点侧(2 多数派)与 4 节点侧(3 多数派)可能同时满足多数派
     → 两个 Leader 出现
   - Joint Consensus 保证任何时刻只有一套"当前生效"的配置
```

```text
Joint Consensus 时序:

   Old Config (C_old): {N1, N2, N3}
   New Config (C_new): {N1, N2, N3, N4}  (新增 N4)

   t0  Leader 提出 Joint Consensus 日志条目
       内容:C(old, new) = {N1, N2, N3, N4}
   t1  AppendEntries 给所有 4 节点
   t2  多数派 (old 多数:2/3 + new 多数:3/4 同时确认)
       → Joint Consensus 已提交
   t3  后续日志都在 C(old, new) 下决策
   t4  Leader 提出 C(new) 日志条目
       内容:C(new) = {N1, N2, N3, N4}
   t5  AppendEntries 给所有 4 节点
   t6  new 多数 (3/4) 确认
       → C(new) 提交,完全切换
```

### 9.2 添加/移除节点

#### 9.2.1 添加节点(扩容)

```text
RedPanda 添加新节点到 Partition:

   1. Controller Group 通过 Joint Consensus 把新节点加入目标 Partition 的成员集
   2. 该 Partition 的 Raft Group 走 Joint Consensus 两阶段
   3. 新节点加入后,会作为 Follower 开始追日志:
        a. 若差距小 → AppendEntries
        b. 若差距大 → InstallSnapshot
   4. 追平后正式参与投票
```

#### 9.2.2 移除节点(缩容/置换)

```text
RedPanda 移除节点:

   1. Controller 决定将某节点从 Partition 成员中移除
   2. Partition Group 走 Joint Consensus
   3. 被移除节点:
        - 收到新的成员配置后,自动转 "Learner" 或退出
        - 不再接收该 Partition 的 AppendEntries
   4. 副本数降低,磁盘占用下降

   注意:
     - 不可移除 Partition Leader(除非先转移 Leader 角色)
     - 移除期间该 Partition 的可用副本数临时减少
```

### 9.3 在线扩容

RedPanda 支持在不停止服务的前提下扩缩容,这是 Raft 协议的设计红利:

```text
在线扩容流程:

   1. 新节点启动 redpanda,配置 controller quorum 加入列表
   2. 新节点启动后,加入 Controller Group(走 Joint Consensus)
   3. Controller Leader 把新节点登记到集群
   4. rebalance 触发:某些 Partition 把新节点加入成员集
   5. 每个被影响的 Partition 走自己的 Joint Consensus
   6. 新节点在每个 Partition 上从 Follower 开始追日志
   7. 全部分区追平后,扩容完成

   整个过程不影响:
     - 已有 Partition 的生产消费
     - Controller Leader 的写入
     - 数据通路
```

---

## 十、集群成员变更流程

下面是 RedPanda 添加新节点的完整时序图(简化版):

```text
===========================================================================
             RedPanda 添加新节点时序(Cluster Member Change)
===========================================================================

  Operator     Node-1 (Leader)     Node-2     Node-3     Node-4 (新节点)
     │              │                │           │              │
     │              │                │           │              │  redpanda start
     │              │                │           │              │  (启动中)
     │              │                │           │              │
     │ rpk cluster add-node --node 4 │           │              │
     │ ────────────────────────────▶ │           │              │
     │              │                │           │              │
     │              │ Controller Group 内提议       │              │
     │              │ "把 Node-4 加入 Controller 集合"            │
     │              │ Joint Consensus               │              │
     │              │ ───── AppendEntries ────────▶ │              │
     │              │ ───── AppendEntries ───────────────────────▶
     │              │                │           │              │
     │              │ ◀──── 多数派确认 ──────────── │              │
     │              │                                                │
     │              │ Controller 配置变更已提交                     │
     │              │ Node-4 加入 Controller Group                  │
     │              │                │           │              │
     │              │ 开始 rebalance:把 Node-4 加入若干 Partition   │
     │              │ 每个被影响的 Partition Group 提议 Joint Consensus
     │              │ ───── AppendEntries (Partition-p0) ─────────▶│
     │              │                │           │              │
     │              │ ◀──── p0 Joint Consensus 多数派 ────────────│
     │              │ ───── AppendEntries (Partition-p1) ─────────▶│
     │              │                │           │              │
     │              │ ◀──── p1 Joint Consensus 多数派 ────────────│
     │              │                │           │              │
     │              │                                                │
     │              │ Node-4 在每个 Partition 追日志                 │
     │              │  - 差距小:AppendEntries                        │
     │              │  - 差距大:InstallSnapshot                      │
     │              │                │           │              │
     │              │  Node-4 追平后正式成为 Follower               │
     │              │                │           │              │
     │ ◀────────── 完成扩容 ─────────│           │              │
     │              │                │           │              │
===========================================================================
关键设计点:
  1. 两阶段 Joint Consensus 保证成员变更期间不出现双 Leader
  2. 每个 Partition 独立追日志,不影响其他分区
  3. 扩容全程数据通路不中断,仅部分分区有秒级延迟
  4. Controller 集合与 Partition 集合的变更完全解耦
===========================================================================
```

---

## 十一、与 Kafka KRaft 对比

### 11.1 核心差异对比表

| 维度                    | Kafka KRaft                                                | RedPanda Raft                                         |
|-------------------------|------------------------------------------------------------|-------------------------------------------------------|
| **Raft 用在哪里**       | 仅元数据 Controller Quorum                                 | 元数据 + 每条用户数据                                 |
| **数据一致性**          | 主从复制(Leader → Follower),acks=all 不保证多数派持久化 | Raft 共识,acks=all = 多数派持久化                    |
| **分区粒度**            | 分区有 Leader,但**不在独立 Raft 组**中                     | **每个分区就是一个 Raft Group**                       |
| **故障隔离**            | Broker 故障 = 该 Broker 上所有分区受影响                   | 分区级隔离,单分区 Leader 切换不影响其他分区          |
| **节点角色**            | Controller 节点 vs Broker 节点                             | 默认每个节点既 Controller 又 Broker                   |
| **数据通路延迟**        | acks=all 至少 1 RTT(到 ISR 多数)                          | Raft commit = 多数派 RTT                              |
| **脑裂保护**            | ISR 机制 + unclean.leader.election 可选                    | Raft Leader Completeness,**不允许数据丢失的脑裂**    |
| **快照**                | Controller Quorum 内部                                     | 每个 Raft Group 独立快照                              |
| **集群成员变更**        | Controller Quorum 内 Joint Consensus                       | 每个 Partition Group 独立 Joint Consensus            |
| **外部依赖**            | 无 ZK(已替代)                                            | 从来就没有 ZK                                         |
| **运维负担**            | 1 套系统,3 种角色(broker/controller/both)                  | 1 套系统,1 个二进制                                   |
| **协议成熟度**          | 2.8 起 ~6 年迭代                                           | v1.0 起 ~4 年迭代                                     |

### 11.2 语义上的关键差异

```text
Kafka 的 acks=all 与 RedPanda 的 acks=all:

   Kafka:
     acks=all → 等到所有 ISR 副本确认收到
     ISR 是动态集合,大小可小于"多数派"
     若 ISR=2 而 RF=3,可能丢失一条已 ack 的消息(若 2 副本同时丢)

   RedPanda:
     acks=all → 等到 Raft 多数派确认持久化
     "多数派"是固定的(⌊N/2⌋+1)
     一旦 ack,即使 Leader 立即故障,数据也不会丢(已被新 Leader 看到)
```

### 11.3 适用场景对比

| 场景                            | Kafka                                     | RedPanda                                  |
|---------------------------------|-------------------------------------------|-------------------------------------------|
| **超大吞吐(EB 级)**            | ✅ 数十年的工程打磨                        | ✅ 高吞吐,稍低于 Kafka(差距在缩小)       |
| **强一致 / 不能丢数据**         | ⚠️ 需仔细配置 unclean.election、min.insync.replicas | ✅ 默认就是 Raft commit,简单        |
| **复杂分区场景**                | ✅ 多年的运维经验                           | ✅ 一致性更可控                           |
| **低延迟(<10ms)**               | ✅ 优化空间大                               | ✅ Raft 单 RTT 即可确认                    |
| **运维简单**                    | ⚠️ 角色多,参数复杂                         | ✅ 单系统单二进制,配置简单                 |
| **多语言客户端兼容**            | ✅ Kafka 协议广泛兼容                       | ✅ 兼容 Kafka 协议,可直接替换             |
| **生态(Kafka Connect 等)**     | ✅ 生态最丰富                              | ⚠️ 生态较小但增长快                       |

---

## 十二、性能优势

### 12.1 单次 RTT 即可确认

RedPanda 数据写入的关键路径:

```text
经典 Raft 单条记录写入的 RTT:
   t=0    客户端 → Leader
   t=RTT  Leader → 多数派 Follower
   t=2RTT Leader 收到多数派确认
   t=2RTT Leader → 客户端 ack

但 RedPanda 用 Pipeline + Batch 优化:
   t=0    客户端 → Leader(record-1)
   t=α    Leader → Follower-1(record-1, 不等响应)
   t=α    Leader → Follower-2(record-1, 不等响应)
   t=α+β  客户端 → Leader(record-2)  ← Pipeline 已经启动
   t=α+γ  Leader → Follower-1(record-2)
   ...
   t=α+δ  Leader 收到 record-1 多数派确认
   t=α+δ  Leader ack 客户端 record-1

   ⇒ 在稳态下,record 的确认延迟接近"单 RTT"
```

### 12.2 无 ZK 间接

```text
Kafka (KRaft 之前):
   客户端 → Broker → Controller → (元数据走 KRaft)
   多了 Controller 这一跳

Kafka (KRaft):
   客户端 → Broker → Controller Quorum (元数据 Raft)
   数据通路独立,不依赖 Controller,但元数据有 1 RTT 额外开销

RedPanda:
   客户端 → Leader (Partition Leader) → Raft Follower
   没有"Controller 这一跳"
   元数据直接被 Leader 异步同步,无需额外 RTT
```

### 12.3 故障检测更快

| 故障                | Kafka 检测耗时       | RedPanda 检测耗时    |
|---------------------|----------------------|----------------------|
| Broker 失效         | 数秒 ~ 数十秒(session timeout) | 选举超时 1.5~3s     |
| Controller 切换     | 选举超时(秒级)      | 同上                 |
| 分区 Leader 切换    | 不存在(主从切换慢)  | 选举超时 1.5~3s      |
| 网络分区            | 取决于 session      | election timeout 直接触发 PreVote |

### 12.5 关键性能数字参考

```text
基准测试数据(来自 RedPanda 官方与社区,实际依环境而定):

                            单分区吞吐          P99 延迟
   RedPanda (acks=1):       ~1 GB/s+           < 5 ms
   RedPanda (acks=all):     ~700 MB/s+         < 15 ms
   Kafka (acks=1):          ~1 GB/s+           < 10 ms
   Kafka (acks=all):        ~500 MB/s          ~20-30 ms

   选举切换延迟:
   RedPanda:                1.5~3 s (PreVote + election timeout)
   Kafka (主从切换):        数秒 ~ 数十秒 (取决于 controller 与 ISR 状态)

   启动时间(3 节点集群):
   RedPanda:                ~3-10 s(无需加载 ZK 状态)
   Kafka KRaft:             ~10-30 s(加载元数据日志)
   Kafka ZK:                ~30-120 s(连接 ZK + 加载 znodes)
```

### 12.6 横向对比:经典共识协议

| 维度           | Raft (RedPanda)              | Paxos 家族              | Zab (ZooKeeper)        |
|----------------|------------------------------|-------------------------|------------------------|
| **理解难度**   | 中(论文清晰)               | 高(变体多)            | 中                     |
| **实现成熟**   | 高                           | 中                     | 极高(JK/ZK 用)       |
| **Leader 模型**| 强 Leader                   | 无固定 Leader          | 强 Leader              |
| **选举效率**   | 快(随机超时 + PreVote)     | 中                     | 快                     |
| **日志一致性** | 强(Leader Completeness)    | 强                     | 强                     |
| **变更支持**   | Joint Consensus             | 复杂                   | 自定义                 |
| **应用场景**   | 通用(etcd/Consul/RedPanda)| 部分 KV                | ZooKeeper              |

```text
RedPanda 选择 Raft 的原因:

   1. 易于理解与验证
      - Diego Ongaro 博士论文清晰
      - 状态机简单(3 状态)
      - 安全性证明相对容易

   2. 工程实现成熟
      - etcd / Consul 已大规模验证
      - 大量参考实现与最佳实践

   3. 故障恢复明确
      - 选举 + 日志追平 + 快照恢复
      - 行为可预测,便于运维

   4. 论文级别的安全性证明
      - Leader Completeness 等 5 大性质
      - 实现者只需遵循规则即可获得安全性
```

### 12.4 单二进制部署的隐性优势

```text
单二进制 redpanda 带来的好处:

   1. 部署简单
        一个 tarball,一个配置文件(rp.yaml),一个 systemd unit
   2. 资源隔离更可控
        没有"ZK JVM"和"Kafka JVM"互相影响 GC
   3. 监控统一
        一套 JMX/Prometheus exporter,一套告警
   4. 升级简单
        滚动重启一个进程,不涉及 ZK 兼容性
   5. 故障域更小
        ZK 集群故障 → Kafka 整个控制平面停摆(已修复但仍是历史痛点)
        RedPanda 单系统,故障域仅自己
```

---

## 十三、实战:配置 Raft 参数

### 13.1 核心 Raft 配置项

RedPanda 在 `rp.yaml` 中提供一系列 Raft 调优参数:

```yaml
# /etc/redpanda/redpanda.yaml

redpanda:
  # ==== 集群身份 ====
  cluster_id: "redpanda-cluster-1"
  node_id: 1   # 集群内唯一,1~N

  # ==== 数据目录 ====
  data_directory: /var/lib/redpanda/data

  # ==== 监听器 ====
  kafka_api:
    address: 0.0.0.0
    port: 9092
  admin:
    address: 0.0.0.0
    port: 9644
  rpc_server:
    address: 0.0.0.0
    port: 33145
```

### 13.2 Raft 相关 Tuning 参数

```yaml
redpanda:
  # ==== 选举相关 ====
  # 选举超时基线(ms),实际超时在 [base, 2*base] 随机
  election_timeout_ms: 1500

  # 心跳间隔(ms)
  heartbeat_interval: 250

  # ==== 快照相关 ====
  # 单个 Raft Group 快照最大尺寸
  raft_max_snapshot_size: 1073741824   # 1 GiB

  # 两次快照最短间隔
  raft_snapshot_interval: 60s

  # ==== 日志与复制 ====
  # append_entries 一次性最多携带的字节数
  raft_append_entries_batch_size: 327680   # 320 KiB

  # Follower 一次 Fetch 最多拉的字节数
  kafka_batch_max_bytes: 1048576            # 1 MiB

  # ==== 副本限流 ====
  # Follower 落后太多时限制 Fetch 大小(避免拖垮 Leader)
  target_fetch_min_bytes: 1
  target_fetch_max_bytes: 134217728

  # ==== 恢复相关 ====
  # 新加入节点恢复时,允许的传输速率
  recovery_throttle_bytes: 524288000        # 500 MiB/s
```

### 13.3 Controller 调优

```yaml
redpanda:
  # ==== Controller Group ====
  # Controller 选举超时
  controller_election_timeout_ms: 1500

  # Controller 心跳间隔
  controller_heartbeat_interval: 250

  # Controller 日志条目最大尺寸
  max_inflight_requests_per_connection: 256
```

### 13.4 调优建议

| 场景                     | 建议                                                         |
|--------------------------|--------------------------------------------------------------|
| **网络高延迟**           | `election_timeout_ms` 调到 3000~5000,避免误判超时           |
| **网络低延迟 + 抖动大**  | `heartbeat_interval` 缩短到 100ms,降低误判切换              |
| **大消息场景**           | `raft_append_entries_batch_size` 调到 1~4 MiB,提高吞吐     |
| **磁盘 IO 紧张**         | 启用 `recovery_throttle_bytes`,避免恢复时拖垮业务           |
| **超大规模集群**         | 调大 `raft_max_snapshot_size`,减少快照频率                  |

---

## 十四、实战:故障演练

### 14.1 Leader 故障演练

```bash
# 1. 查看当前 Partition Leader 分布
rpk cluster partitions list --detailed

# 输出(简化):
# TOPIC     PARTITION  LEADER  REPLICAS
# orders    0          1       [1, 2, 3]
# orders    1          2       [1, 2, 3]
# orders    2          3       [1, 2, 3]

# 2. 查看当前 Controller Leader
rpk cluster info

# 3. 选定要 kill 的节点(假设要 kill Leader of orders/p0,即 Node-1)
ssh node-1 "ps -ef | grep redpanda"

# 4. 模拟故障
ssh node-1 "sudo kill -9 <redpanda-pid>"

# 5. 观察 Leader 切换
# 在另一个终端持续跑:
watch -n 1 'rpk cluster partitions list --detailed | grep orders'

# 6. 预期:
#    - Node-1 上 orders/p0 的 Leader 在 1.5~3s 内切到 Node-2 或 Node-3
#    - 切换期间写入该分区的请求短暂失败/重试
#    - 其他分区不受影响

# 7. Node-1 启动后,自动加入并追平
ssh node-1 "sudo systemctl start redpanda"
```

### 14.2 网络分区演练

```bash
# 1. 在 Node-1 上模拟与 Node-2/3 的网络分区
#    (假设目标:让 Node-1 单独成为少数派)

# 方案 A:iptables 阻断(谨慎使用)
sudo iptables -A INPUT -s node-2 -j DROP
sudo iptables -A INPUT -s node-3 -j DROP
sudo iptables -A OUTPUT -d node-2 -j DROP
sudo iptables -A OUTPUT -d node-3 -j DROP

# 2. 观察 Node-1 的状态
#    - Node-1 上各 Partition Leader 会 election timeout
#    - Node-1 因拿不到多数派投票,自动 stepDown
#    - Node-1 上的所有 Partition 转为 Follower(或 Candidate → Follower)

# 3. 观察 Node-2/3 的状态
#    - 选举新的 Leader(从 Node-2/3 中选出)
#    - 多数派 (Node-2 + Node-3) 继续服务
#    - 数据写入不中断,仅 Node-1 上的 Leader 切走

# 4. 恢复网络
sudo iptables -D INPUT -s node-2 -j DROP
sudo iptables -D INPUT -s node-3 -j DROP
sudo iptables -D OUTPUT -d node-2 -j DROP
sudo iptables -D OUTPUT -d node-3 -j DROP

# 5. 观察 Node-1 重连
#    - Node-1 上的 Partition 走 Joint Consensus(若有成员变更)
#    - 或直接重新加入现有 Group(无成员变更时)
#    - 追日志 → 追上 → 重新参与投票
```

### 14.3 脑裂恢复演练

```text
脑裂恢复的本质:

   场景:
     Node-1 与 Node-2、Node-3 网络分区
     Node-1 自以为 Leader(选举超时触发)
     Node-2、Node-3 在另一边选出新 Leader

   写入情况:
     - 客户端连接到 Node-1 写入:Node-1 拿不到多数派确认,无法 commit
       → 客户端写入超时或失败
     - 客户端连接到 Node-2/3 写入:Node-2/3 拿到多数派,正常 commit

   网络恢复后:
     - Node-1 收到新 Leader (Node-2/3) 的心跳
     - Node-1 term 比新 Leader 旧 → 自动 stepDown
     - Node-1 用新 Leader 的日志覆盖自己的"未提交"日志
     - Node-1 重新加入为 Follower
     - 不会有"数据双写"或"脑裂写入"

   关键:
     - 任何写入必须多数派确认 = Raft commit
     - 网络分区中的少数派节点无法"假装 commit"
     - 脑裂期间不会出现"两个 Leader 都成功 commit"
```

### 14.4 演练清单

```text
[ ] 1. Kill current leader of a partition
       → 验证 1.5~3s 内新 leader 上任
[ ] 2. Kill current controller leader
       → 验证元数据写入 3~5s 内恢复,数据通路不受影响
[ ] 3. iptables 模拟网络分区(让 1 节点孤立)
       → 验证该节点 stepDown,多数派继续服务
[ ] 4. 同时 kill 两个节点(测试仅剩 1 节点时不可写)
       → 验证集群不可写但可读(取决于配置)
[ ] 5. 启动 1 个新节点加入集群
       → 验证自动加入 + 追日志 + 参与投票
[ ] 6. 长时间 kill 一个节点(数小时)再重启
       → 验证 InstallSnapshot 路径正常
[ ] 7. 滚动升级 redpanda 版本
       → 验证升级期间数据通路不中断
[ ] 8. 磁盘满演练
       → 验证节点行为(应触发告警并限流)
[ ] 9. 网络抖动(用 tc netem)
       → 验证 election timeout 不误判
[ ] 10. 监控告警触发验证
        → 验证告警链路通畅,值班可及时响应
```

---

## 十五、监控 Raft 状态

### 15.1 rpk 监控命令

`rpk` 是 RedPanda 的官方管理 CLI,内置大量 Raft 监控命令。

#### 15.1.1 集群整体健康

```bash
# 集群整体信息
rpk cluster info

# 输出示例:
# CLUSTER
# =======
# redpanda-cluster-1
#
# BROKERS
# =======
# ID    HOST       PORT
# 1*    node-1     9092
# 2     node-2     9092
# 3     node-3     9092
#
# * = 当前连接节点

# 集群健康检查
rpk cluster health

# 输出示例:
# CLUSTER HEALTH OVERVIEW
# =======================
# Healthy:        3 / 3
# Controller:     1 (Node-2)
# Unhealthy:      0
# Under-replicated: 0
```

#### 15.1.2 Controller 状态

```bash
# 查看 Controller Group 状态
rpk cluster controller status

# 输出示例:
# CONTROLLER
# ==========
# Node ID:    2
# Group ID:   1
# Term:       17
# Last committed offset: 12345

# 查看 Controller Group 成员
rpk cluster controller list

# 输出示例:
# ID    HOST     PORT
# 1     node-1   33145
# 2*    node-2   33145
# 3     node-3   33145
```

#### 15.1.3 Partition 与 Raft Group 状态

```bash
# 列出所有 Partition
rpk cluster partitions list

# 查看某个 Partition 的 Raft 详情
rpk cluster partitions list --detailed

# 输出示例:
# TOPIC    PARTITION  LEADER  REPLICAS         STATUS
# orders   0          1       [1, 2, 3]       OK
# orders   1          2       [1, 2, 3]       OK
# orders   2          3       [1, 2, 3]       OK
# payments 0          1       [1, 2, 3]       OK

# 查看某个 Partition 的 Raft Group 状态
rpk cluster partitions inspect orders -p 0

# 输出示例:
# PARTITION
# =========
# Topic:       orders
# Partition:   0
# Leader:      1
# Replicas:    [1, 2, 3]
#
# RAFT
# ====
# Group ID:         12345
# Term:             42
# Last committed:   67890
# Last applied:     67889
# High watermark:   67900
```

#### 15.1.4 副本与同步状态

```bash
# 查看副本详情
rpk cluster partitions list --replica-info

# 查看某个 Partition 的副本 Lag
rpk cluster partitions inspect orders -p 0 --replica-info

# 列出 under-replicated 分区
rpk cluster partitions list --under-replicated

# 列出无 Leader 的分区(严重告警)
rpk cluster partitions list --no-leader
```

#### 15.1.5 选举观察

```bash
# 持续观察 Partition Leader 变化
watch -n 1 'rpk cluster partitions list --detailed'

# 观察 Controller Leader 变化
watch -n 1 'rpk cluster controller status'
```

### 15.2 JMX / Prometheus 指标

RedPanda 暴露 JMX 指标,可被 Prometheus 抓取。关键 Raft 相关指标:

| 指标                                       | 含义                                       | 告警阈值             |
|--------------------------------------------|--------------------------------------------|----------------------|
| `redpanda_cluster_controller_id`            | 当前 Controller Leader 的 Node ID          | 必须 = 某个值       |
| `redpanda_cluster_unavailable_partitions`   | 无 Leader 的分区数                         | 必须 = 0             |
| `redpanda_cluster_under_replicated_partitions` | 副本欠同步的分区数                       | 应 = 0(容忍偶发)    |
| `vectorized_raft_group_status`             | Raft Group 状态(leader/follower/candidate)| -                    |
| `vectorized_raft_term`                     | 当前 Term                                  | 监控变化频率         |
| `vectorized_raft_commit_index`             | 当前 commitIndex                           | 与 last_applied 接近 |
| `vectorized_raft_last_applied_offset`      | 最近 apply 的 offset                       | 应紧跟 commit_index |
| `vectorized_raft_recovery_offset`          | 副本恢复进度                               | 0 表示追平           |

#### Prometheus 抓取配置

```yaml
# prometheus.yml 片段
scrape_configs:
  - job_name: redpanda
    static_configs:
      - targets:
          - node-1:9644
          - node-2:9644
          - node-3:9644
    metrics_path: /public_metrics
```

### 15.3 常用告警规则

```yaml
# alertmanager 规则示例

groups:
  - name: redpanda_raft
    rules:
      # Controller Leader 必须存在
      - alert: RedPandaNoControllerLeader
        expr: redpanda_cluster_controller_id == 0
        for: 30s
        severity: critical

      # 有分区无 Leader
      - alert: RedPandaUnavailablePartitions
        expr: redpanda_cluster_unavailable_partitions > 0
        for: 30s
        severity: critical

      # 副本欠同步
      - alert: RedPandaUnderReplicatedPartitions
        expr: redpanda_cluster_under_replicated_partitions > 0
        for: 5m
        severity: warning

      # Raft 选举频率过高
      - alert: RedPandaRaftFrequentElections
        expr: increase(vectorized_raft_leader_election_count[5m]) > 3
        for: 5m
        severity: warning

      # apply 落后 commit 过多
      - alert: RedPandaApplyLag
        expr: vectorized_raft_commit_index - vectorized_raft_last_applied_offset > 1000
        for: 5m
        severity: warning
```

### 15.4 健康检查脚本示例

```bash
#!/bin/bash
# redpanda_health_check.sh
# 定期巡检 RedPanda 集群 Raft 状态

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "===== RedPanda Raft 健康检查 ====="
echo "时间:$(date)"
echo

# 1. 集群整体健康
echo "[1] 集群整体健康"
HEALTH=$(rpk cluster health --exit-0-if-no-error 2>/dev/null || true)
if echo "$HEALTH" | grep -q "Healthy:.*3 / 3"; then
    echo -e "  ${GREEN}OK${NC}:3 节点全健康"
else
    echo -e "  ${RED}FAIL${NC}:集群不健康"
    echo "$HEALTH"
fi
echo

# 2. Controller Leader
echo "[2] Controller Leader"
CONTROLLER=$(rpk cluster controller status 2>/dev/null | grep "Node ID:" | awk '{print $3}')
if [ -n "$CONTROLLER" ] && [ "$CONTROLLER" != "0" ]; then
    echo -e "  ${GREEN}OK${NC}:Controller Leader = Node-$CONTROLLER"
else
    echo -e "  ${RED}FAIL${NC}:无 Controller Leader"
fi
echo

# 3. 无 Leader 分区
echo "[3] 无 Leader 分区"
NO_LEADER=$(rpk cluster partitions list --no-leader 2>/dev/null | wc -l)
if [ "$NO_LEADER" -le 1 ]; then
    echo -e "  ${GREEN}OK${NC}:无 Leader 分区数 = 0"
else
    echo -e "  ${RED}FAIL${NC}:有 $((NO_LEADER-1)) 个分区无 Leader"
    rpk cluster partitions list --no-leader
fi
echo

# 4. 欠同步分区
echo "[4] 欠同步分区"
UNDER=$(rpk cluster partitions list --under-replicated 2>/dev/null | wc -l)
if [ "$UNDER" -le 1 ]; then
    echo -e "  ${GREEN}OK${NC}:欠同步分区数 = 0"
else
    echo -e "  ${YELLOW}WARN${NC}:有 $((UNDER-1)) 个分区欠同步"
fi
echo

# 5. 磁盘空间
echo "[5] 磁盘空间"
DISK_USE=$(df -h /var/lib/redpanda | tail -1 | awk '{print $5}' | tr -d '%')
if [ "$DISK_USE" -lt 80 ]; then
    echo -e "  ${GREEN}OK${NC}:磁盘使用率 = ${DISK_USE}%"
elif [ "$DISK_USE" -lt 90 ]; then
    echo -e "  ${YELLOW}WARN${NC}:磁盘使用率 = ${DISK_USE}%"
else
    echo -e "  ${RED}FAIL${NC}:磁盘使用率 = ${DISK_USE}%"
fi
echo

echo "===== 检查完成 ====="
```

### 15.5 故障定位决策树

```text
问题:Producer 写入失败 / 超时
├── 检查:客户端连接到哪个 Broker?
│   └── rpk cluster info 看 advertised 地址
│
├── 检查:目标 Partition 是否有 Leader?
│   ├── rpk cluster partitions list --no-leader
│   └── 有 → Raft Group 选举中(等几秒)
│   └── 无 → 进入下一层
│
├── 检查:磁盘是否满?
│   └── df -h /var/lib/redpanda
│       └── 满 → 清理旧数据 / 扩容
│
├── 检查:网络是否可达 Leader?
│   └── nc -zv <broker-host> 9092
│       └── 不通 → 网络问题,等恢复
│
├── 检查:Producer 配置
│   └── acks、timeout、retries 设置
│
└── 检查:集群日志
    └── journalctl -u redpanda -n 200
```

```text
问题:Consumer 读不到新数据
├── 检查:Consumer Group 状态
│   └── rpk group describe <group-id>
│       └── lag 累积 → 可能 Consumer 慢
│
├── 检查:Partition Leader 是否切换过
│   └── rpk cluster partitions list --detailed
│       └── 切换过 → 等待消费追平
│
├── 检查:Consumer 偏移量
│   └── rpk group seek <group-id> --to end
│
└── 检查:auto.offset.reset 配置
    └── earliest / latest 选择
```

### 15.6 日志与排障

```bash
# 1. 查看 redpanda 日志
journalctl -u redpanda -f | grep -E "raft|election|controller"

# 关键日志关键字:
#   "raft - elected new leader" - 新 leader 上任
#   "raft - stepping down"      - 主动 stepDown
#   "raft - received vote"      - 收到投票
#   "controller - becoming leader" - controller 切换
#   "install_snapshot"          - 快照传输

# 2. 查看某个 Partition 的 Raft 状态
rpk cluster partitions inspect orders -p 0 --verbose

# 3. 查看 RPC 层指标
rpk debug metrics | grep raft

# 4. 重置 / 触发特定操作
rpk cluster partitions move-leader orders -p 0 --to 2
```

---

## 十六、核心要点速记

- **RedPanda Raft = 系统级共识**:从 v1.0 起,Raft 就是 RedPanda 的基石,不是补丁
- **元数据 + 数据都用 Raft**:这是与 Kafka KRaft 最根本的区别
  - Kafka:仅元数据走 Raft,数据走主从复制
  - RedPanda:每条用户数据都走 Raft,acks=all = 多数派持久化
- **每 Partition 一个 Raft Group**:故障隔离、负载分散、扩展性强
- **Controller 与数据通路解耦**:
  - Controller Group 管理元数据
  - 数据 Raft Group 管理用户数据
  - 两者独立,可并行切换
- **选举流程**:
  - **PreVote 优化**:避免分区节点污染 Term
  - **随机超时**:避免 split vote
  - **Term 递增**:逻辑时钟 + 去重
  - **投票规则**:一 Term 一票 + 日志新鲜度比较
- **日志复制**:
  - Leader 接收请求 → AppendEntries
  - **Pipeline + Batch** 优化,稳态接近单 RTT
  - **心跳与日志复用 AppendEntries RPC**
  - 多数派确认 = commitIndex 推进
- **快照机制**:
  - 触发:`raft_max_snapshot_size` / `raft_snapshot_interval`
  - 用途:Follower 落后大时 InstallSnapshot
- **数据一致性保证**:
  - **选举安全**(每 Term 最多一个 Leader)
  - **Leader 完整性**(不丢已提交日志)
  - **日志匹配**(相同 Index+Term 前缀相同)
  - **脑裂不可能**(少数派无法 commit)
- **配置变更**:
  - **Joint Consensus(联合共识)** 两阶段
  - 在线扩容/缩容不影响数据通路
- **性能优势**:
  - 单 RTT 确认(Pipeline 后稳态)
  - 无 ZK 间接,单二进制部署
  - 故障检测快(election timeout 1.5~3s)
- **实战配置**:
  - `election_timeout_ms` 基础超时
  - `heartbeat_interval` 心跳间隔
  - `raft_max_snapshot_size` 快照阈值
  - `raft_append_entries_batch_size` 批大小
- **故障演练**:Leader kill、网络分区、脑裂恢复、新节点加入、滚动升级
- **监控命令**:
  - `rpk cluster health` - 集群健康
  - `rpk cluster controller status` - Controller 状态
  - `rpk cluster partitions inspect <topic> -p <id>` - Partition Raft 状态
  - JMX / Prometheus 指标
- **关键告警**:Controller Leader 必须存在、unavailable_partitions = 0、under_replicated = 0
- **生产建议**:
  - 至少 3 节点(容忍 1 失效)
  - 网络延迟稳定时用默认配置
  - 大集群调快照阈值避免频繁触发
  - 定期演练 Leader 切换与网络分区

---

### 16.5 容量规划与 Raft 开销

```text
Raft 协议本身的开销:

   元数据:
     每条 Raft 日志条目 = (index + term + record_size) ≈ 几十字节头
     实际"有用"数据是 record_size
     开销比例通常 < 5%

   网络:
     AppendEntries RPC = 头 + entries
     头约 100~200 字节
     Pipeline + Batch 后摊薄到 < 1%

   磁盘:
     每条日志 = 完整序列化(含 Raft 头)
     写放大 ≈ 1(无压缩)
     压缩策略可显著降低磁盘占用

   CPU:
     Raft 状态机切换、RPC 序列化、快照
     通常不是 CPU 瓶颈(IO 才是)
```

容量规划参考:

| 集群规模          | 推荐配置                                       |
|------------------|-----------------------------------------------|
| 3 节点 / 数 TB    | 默认配置,snapshot 阈值 1 GB                  |
| 5 节点 / 数十 TB  | election_timeout 调到 3000ms,batch_size 调到 2 MiB |
| 10+ 节点 / PB 级 | 调大 snapshot(4 GB),开启 follow_fetch_recovery_rate 限制 |

### 16.6 常见问题 FAQ

**Q1:RedPanda Raft 与 etcd Raft 是一样的吗?**

答:核心算法一致(基于 Diego Ongaro 博士论文),但工程实现差异很大:
- etcd 面向 KV 存储,Raft 日志 = 操作日志
- RedPanda 面向流数据,Raft 日志 = record 流
- RedPanda 额外有 Pipeline / Batch / Zero-Copy 等优化
- 快照、恢复、配置变更的实现也不同

**Q2:为什么 RedPanda 不支持 unclean leader election?**

答:这是 Raft 协议的设计选择。`unclean.election.enable = false`(默认):
- 老 Leader 故障后,只有含全部已提交日志的节点能当选
- 不会因为"老 Leader 复活"导致数据丢失
- 可用性轻微下降(选举可能稍慢),换一致性大幅提升

**Q3:acks=1 与 acks=all 的差距多大?**

```text
实测差距(典型 3 节点,同机房):

   acks=1:  ~1-3 ms   (只等 Leader 自己持久化)
   acks=all: ~5-15 ms (等多数派持久化,Pipeline 后)

   跨机房场景:
     acks=1:  ~5-10 ms
     acks=all: ~15-50 ms (RTT 倍数)

   RedPanda 建议:
     强一致场景 → acks=all(默认)
     极致低延迟 → acks=1(可容忍 Leader 故障丢少量数据)
```

**Q4:为什么 Controller Leader 切换不影响数据写入?**

答:Controller Group 与 Partition Group 完全独立:
- 数据写入只走对应 Partition 的 Leader
- Controller 切换期间,数据 Leader 不变
- 仅元数据变更(create topic 等)受影响
- 这与 Kafka 完全不同(Kafka Controller 切换会暂缓一切元数据操作)

**Q5:RedPanda 集群最少几个节点?**

答:理论上 1 节点即可运行,但生产建议至少 3 节点:
- 1 节点:无容错,开发测试用
- 2 节点:无法形成 Raft 多数派,实际无法写入
- 3 节点:容忍 1 节点失效,生产推荐
- 5 节点:容忍 2 节点失效,适合关键场景

**Q6:Raft 日志会无限增长吗?**

答:不会。RedPanda 通过快照压缩日志:
- 每次快照覆盖到 snapshot.lastIndex
- 之前的日志可被删除(仅保留快照 + 增量)
- 默认 snapshot 间隔 60s,大小 1 GB
- 实际日志增长被严格控制在合理范围

**Q7:如何评估 Raft 健康度?**

答:看几个关键指标:
- `commit_index - last_applied` 应接近 0
- 各 Follower `recovery_offset` 应为 0
- Term 应缓慢上升,不大起大落
- 选举次数应在合理范围(天级别 1~10 次)

### 16.7 RedPanda 与 etcd / Consul Raft 对比

| 维度               | etcd Raft                  | Consul Raft               | RedPanda Raft               |
|--------------------|----------------------------|---------------------------|------------------------------|
| **应用场景**       | KV 存储                    | 服务发现 + KV              | 流数据 + 元数据              |
| **数据特征**       | 小 KV(几百字节)            | 服务条目                  | 大 record(可达 1 MiB+)      |
| **优化重点**       | 低延迟 KV                  | 多数据中心                | 高吞吐 + 低延迟             |
| **快照粒度**       | 整体 KV 快照               | 服务条目快照              | 每 Raft Group 独立快照       |
| **客户端**         | gRPC + KV API              | HTTP API                  | Kafka 协议兼容               |
| **外部依赖**       | 无                          | 无                        | 无                            |

---

## 十七、参考与延伸

- **RedPanda 官方文档 - Raft**: https://docs.redpanda.com/current/cluster-administration/raft/
- **RedPanda 官方文档 - Configuration**: https://docs.redpanda.com/current/reference/properties/
- **Ongaro, D. (2014). Consensus: Bridging Theory and Practice (Raft 论文)**: https://raft.github.io/raft.pdf
- **RedPanda 架构博客**: https://redpanda.com/blog/
- **Raft 算法可视化**: https://raft.github.io/
- **Kafka KRaft 模式参考**: 对比阅读本书第 8 章,理解两种 Raft 落地的差异

---

## 十八、术语表

为方便查阅,这里汇总本章涉及的关键术语:

| 术语                          | 含义                                                         |
|-------------------------------|--------------------------------------------------------------|
| **Raft**                      | 一种易于理解的分布式共识算法,D. Ongaro 2014 年提出          |
| **Term (任期)**               | Raft 的逻辑时钟,每次选举递增,标识 Leader 的"届"           |
| **Leader**                    | Raft Group 中负责处理写入与复制的节点                        |
| **Follower**                  | Raft Group 中被动接收 Leader 日志的节点                      |
| **Candidate**                 | 选举过程中的临时角色,发起 RequestVote                        |
| **PreVote**                   | 正式增 Term 前先探查能否当选,避免分区节点污染 Term           |
| **RequestVote RPC**           | 投票请求,Candidate → Follower                              |
| **AppendEntries RPC**         | 日志追加 + 心跳复用,Leader → Follower                       |
| **InstallSnapshot RPC**       | 快照传输,Follower 落后太多时使用                            |
| **Joint Consensus**           | 联合共识,两阶段成员变更协议                                  |
| **commitIndex**               | 已提交的最高日志索引                                          |
| **lastApplied**               | 已应用到状态机的最高日志索引                                  |
| **matchIndex**                | Leader 视角:Follower 已确认的最高日志索引                   |
| **nextIndex**                 | Leader 视角:下次要发给 Follower 的起始日志索引              |
| **Leader Completeness**       | 安全性属性:新 Leader 必包含所有已提交条目                   |
| **Log Matching**              | 安全性属性:相同 Index+Term 的条目前缀相同                    |
| **Election Safety**           | 安全性属性:每 Term 至多一个 Leader                          |
| **Linearizable Read**         | 线性一致性读,保证读到最新已提交数据                         |
| **Leader Lease**              | Leader 租约,抑制不必要的 stepDown                            |
| **Follower Read**             | 从 Follower 读,降低读延迟,牺牲一致性                       |
| **Pipeline**                  | Leader 不等确认就发下一批日志,摊薄 RTT                      |
| **Batch**                     | 多条日志打包成一个 AppendEntries,降低头开销                  |
| **Zero-Copy**                 | 网络传输避免用户态内存拷贝                                    |
| **Snapshot**                  | 日志压缩点,把已应用状态打包                                  |
| **Controller**                | 集群元数据管理者,由 Controller Raft Group 共同维护          |
| **Controller Group**          | 元数据 Raft Group,默认所有节点都是 Controller               |
| **Partition Group**           | 每个分区就是一个 Raft Group                                  |
| **majority**                  | 多数派,⌊N/2⌋+1                                              |
| **quorum**                    | 集群法定人数,典型为 3 或 5                                  |
| **fsync**                     | 将数据从 page cache 刷到磁盘                                 |
| **page cache**                | 操作系统管理的内存页缓存                                     |

---

## 十九、版本演进与里程碑

RedPanda 自 v1.0 起就把 Raft 作为系统基石,以下是几个重要的版本节点:

| 版本     | 时间       | Raft 相关变化                                                  |
|----------|------------|---------------------------------------------------------------|
| v21.x    | 2021       | 第一个 GA 版本,内置 Raft 已稳定                               |
| v22.1    | 2022       | Tiered Storage(分层存储)上线,日志可下沉到 S3               |
| v22.2    | 2022       | Controller 优化、Partition Balance 改进                       |
| v22.3    | 2022       | Raft 选举参数优化,默认 election_timeout_ms 调整              |
| v23.1    | 2023       | Redpanda Console GA,可视化监控                                |
| v23.2    | 2023       | Shadow Link、Read Replica 引入                                |
| v23.3    | 2023       | Raft 协议进一步优化,follower fetching 改进                   |
| v24.1    | 2024       | 大规模集群优化、千万级分区支持                                |
| v24.2    | 2024       | Iceberg 集成、长时运行稳定性                                  |
| v24.3    | 2024       | 自动恢复、运维工具增强                                         |

```text
版本选择建议:

   生产环境:
     - 选择最新稳定版(当前 GA 系列)
     - 至少落后一个 minor,确保 bug 已暴露

   大规模集群:
     - 选择有"可扩展性优化"的版本
     - 通常 minor 版本号 ≥ 第二个数字

   升级路径:
     - RedPanda 支持滚动升级,无停机
     - 一次升一个 minor 版本更安全
     - 升级期间 Raft 自动重连、追日志
```

---

## 二十、章节小结与下章预告

### 20.1 关键 takeaway

经过本章系统学习,你应该掌握:

1. **协议层**:RedPanda 从 v1.0 起就用 Raft,不仅是元数据,每条用户数据都走 Raft
2. **架构层**:Controller Group + N 个 Partition Group,完全解耦
3. **选举机制**:PreVote + 随机超时 + Term 递增 + 日志新鲜度比较
4. **复制机制**:Pipeline + Batch + Zero-Copy,稳态接近单 RTT
5. **一致性**:Leader Completeness + Log Matching + 已提交位点
6. **配置变更**:Joint Consensus 两阶段,在线扩缩容
7. **运维实践**:rpk 命令、JMX 指标、告警规则、故障演练

### 20.2 与下一章的衔接

RedPanda 的 Raft 协议解决了"一致性"问题,但要落地为生产级流平台,还需要:

- **存储层**:Segment、索引、压缩、保留策略 → 见后续章节
- **客户端协议**:Kafka API 兼容性、Produce/Consume → 见后续章节
- **Schema 管理**:Schema Registry 与 Raft 的关系 → 见后续章节
- **集群调优**:磁盘、网络、内存、JVM 参数 → 见后续章节
- **运维工具**:rpk 完整使用、Redpanda Console → 见后续章节

Raft 是这一切的底层基石。理解了 Raft,你就能更好地理解 RedPanda 其他模块的设计动机与限制。

---

> 本章覆盖了 RedPanda Raft 的全貌:从协议机制、选举流程、日志复制、快照、配置变更,到与 Kafka KRaft 的对比、参数调优、故障演练、监控告警、术语参考、版本演进。理解这些,你就能在生产环境自信地部署、调优与运维 RedPanda 集群。
