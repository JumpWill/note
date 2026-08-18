# Kafka 副本机制与 ISR

## 一、副本机制概述

### 1.1 为什么需要副本

Kafka 之所以能在生产环境承担关键消息流转的角色,核心就在于它的**副本机制 (Replica)**。单一 Broker 节点面临磁盘损坏、机器宕机、网络中断、机房断电等各类故障,没有任何一个分布式系统能仅靠单机保证可靠性。副本机制的本质是:**把同一份数据存放在多台机器上,即使部分机器故障,数据仍然可用**。

副本机制带来的收益可以总结为以下四点:

| 收益         | 说明                                                                         |
|--------------|------------------------------------------------------------------------------|
| **高可用**   | Leader 副本宕机时,可以从 Follower 中选举新 Leader,服务不中断                 |
| **数据持久** | 同一份消息在多个 Broker 上冗余存储,即使部分磁盘损坏也不丢失                 |
| **水平扩展** | 分区 (Partition) 是 Kafka 的并行单元,多副本配合多分区提升吞吐               |
| **就近读**   | 较新版本支持 Follower 读取(`replica.fetch.min.bytes` 配合),缓解 Leader 压力  |

### 1.2 分区与副本的关系

Kafka 的消息组织单位是 **Topic**,每个 Topic 在物理上被切分为若干 **Partition**,每个 Partition 又可以有多个 **Replica**。这三层关系可以用下表描述:

| 层级       | 含义                                                  |
|------------|-------------------------------------------------------|
| **Topic**  | 逻辑上的消息类别(订单、日志、用户行为)                |
| **Partition** | 物理上的可并行单元,每个 Partition 是一个有序日志     |
| **Replica** | Partition 的物理拷贝,分布在不同的 Broker 上          |

**重要原则**:

- 一个 Partition 的多个副本中,**只有一个对外提供服务**(读写),即 Leader Replica
- 其他副本称为 **Follower Replica**,只被动同步 Leader 的数据
- 同一个 Partition 的所有副本,内容在「同步完成」时必须完全一致

### 1.3 副本的存储视图

```text
Topic: order-topic          (3 个分区 × 3 个副本)

Broker-1                 Broker-2                 Broker-3
┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│ P0-Replica   │         │ P0-Replica   │         │ P0-Replica   │
│ (Follower)   │         │ (Leader)     │         │ (Follower)   │
├──────────────┤         ├──────────────┤         ├──────────────┤
│ P1-Replica   │         │ P1-Replica   │         │ P1-Replica   │
│ (Leader)     │         │ (Follower)   │         │ (Follower)   │
├──────────────┤         ├──────────────┤         ├──────────────┤
│ P2-Replica   │         │ P2-Replica   │         │ P2-Replica   │
│ (Follower)   │         │ (Follower)   │         │ (Leader)     │
└──────────────┘         └──────────────┘         └──────────────┘
```

每个 Broker 都会承担若干个分区的 Leader,同时也会担任其他分区的 Follower,这样在 Leader 切换时能够快速找到新 Leader。

---

## 二、副本角色

### 2.1 Leader Replica(主副本)

**Leader Replica** 是每个 Partition 在任意时刻**唯一对外**承担读写请求的副本。所有 Producer 写入和 Consumer 读取都会直接落到 Leader 上(早期版本;后续章节讨论 Follower 读)。

**Leader 的职责**:

| 职责           | 说明                                                                  |
|----------------|-----------------------------------------------------------------------|
| 处理 Produce   | 接收 Producer 的消息,写入本地 log,推进自己的 LEO(Log End Offset)     |
| 处理 Fetch     | 响应 Consumer 与 Follower 的拉取请求,告知 HW(High Watermark)         |
| 维护 ISR       | 跟踪哪些 Follower 与自己保持同步                                       |
| 参与选举       | 当自己宕机时不再参选;正常运行时是选举的发起者(配合 Controller)        |

**关键特性**:Leader 是「**强一致读写的锚点**」,所有数据同步的进度都以 Leader 为基准。

### 2.2 Follower Replica(从副本)

**Follower Replica** 是 Leader 的「影子」,它不直接对外服务,但**必须**持续追赶 Leader 的数据,以便 Leader 故障时能够顶上。

**Follower 的职责**:

| 职责         | 说明                                                                                                |
|--------------|-----------------------------------------------------------------------------------------------------|
| 拉取数据     | 通过 `FetchRequest` 向 Leader 拉取消息批次                                                          |
| 写入本地 log | 把拉到的消息追加到自己的 log 文件,推进自己的 LEO                                                    |
| 汇报进度     | 在 FetchResponse 中携带自己的 LEO,告诉 Leader 自己已经同步到哪里                                    |
| 同步 HW      | 定期将自己的 log 截断到 Leader 告知的 HW 之下(防止未同步消息被消费者读到)                          |

**关键特性**:Follower **只跟随 Leader**,从不主动接受 Producer 的写入请求。如果一个 Follower 收到了 Producer 的写入请求,它会拒绝并提示「Not Leader For Partition」。

### 2.3 角色关系图

```text
        Producer                Consumer
            │                       │
            │ 写消息                │ 读消息
            ▼                       ▼
        ┌─────────────────────────────────┐
        │           Leader                │
        │  - 接受写                       │
        │  - 接受读                       │
        │  - 推进 LEO / HW                │
        └─────────────────────────────────┘
            ▲           ▲           ▲
            │ 拉取      │ 拉取      │ 拉取
            │           │           │
        ┌───────┐   ┌───────┐   ┌───────┐
        │Follower│   │Follower│   │Follower│
        │  (F1)  │   │  (F2)  │   │  (F3)  │
        │ ISR ✓ │   │ ISR ✓ │   │ OSR ✗ │   ← 状态可能不同
        └───────┘   └───────┘   └───────┘
```

---

## 三、ISR 机制详解

### 3.1 ISR 的定义

**ISR (In-Sync Replicas)** 是 Kafka 中**与 Leader 保持同步**的所有副本的集合,包括 Leader 自己。换句话说,ISR 内的每一个副本,其 LEO 都「足够接近」Leader 的 LEO。

在 Kafka 的实现中,「同步」的判定标准并不是简单地比较 LEO 数值,而是基于 **replica.lag.time.max.ms**(默认 30000 毫秒):如果一个 Follower 在该时间窗口内成功地向 Leader 发送过 FetchRequest 并拉取过数据,就被认为是「同步的」。

**ISR 的关键特性**:

| 特性       | 说明                                                                |
|------------|---------------------------------------------------------------------|
| **包含 Leader** | Leader 永远在 ISR 内,这是设计前提                                |
| **动态变化**   | 跟随同步状态实时进出,无须人工干预                                |
| **决定写入安全** | `acks=all` 时,只有 ISR 内所有副本写入成功,Leader 才返回 ACK |
| **决定选举范围** | 新 Leader 只能从 ISR 内选举(默认配置下)                       |

### 3.2 OSR(Out-of-Sync Replicas)

**OSR** 是 ISR 的反面——即那些**当前没有与 Leader 保持同步**的副本。常见导致副本进入 OSR 的原因:

| 原因               | 说明                                                       |
|--------------------|------------------------------------------------------------|
| Follower 进程宕机  | 长时间未发送 FetchRequest,被 Leader 判定为「失联」        |
| 网络分区           | Follower 与 Leader 之间网络中断,Fetch 请求无法到达          |
| 磁盘满 / GC 停顿   | Follower 长时间卡住,无法及时消费 Leader 推送的数据         |
| 同步速度跟不上     | Follower 处理能力不足,LEO 落后 Leader 越来越多             |

OSR 中的副本**不会被选举为 Leader**(默认配置),也**不会参与 acks=all 的写入确认**。它的存在更多是为了故障恢复——一旦恢复同步,会自动重新加入 ISR。

### 3.3 ISR 的动态变化

ISR 不是静态配置,而是随着每个 Follower 的同步状态**实时变化**。状态流转如下图:

```text
                ┌─────────────────────┐
                │   启动 / 重启副本   │
                └──────────┬──────────┘
                           │ 创建 Replica,初始 LEO
                           ▼
                ┌─────────────────────┐
       ┌─────── │     OSR 状态        │ ←──────┐
       │        │ (未同步,刚启动)     │        │
       │        └──────────┬──────────┘        │
       │                   │                  │
       │   第一次成功 Fetch                   │
       │   (拉到数据,通知 Leader)             │ 长时间未 Fetch
       │                   │                  │ 超过 lag.time.max.ms
       │                   ▼                  │
       │        ┌─────────────────────┐        │
       │        │     ISR 状态        │ ───────┘
       └─────── │ (与 Leader 同步中)  │
                └─────────────────────┘
```

**状态变更的触发条件**:

| 进入 ISR              | 离开 ISR(进入 OSR)                |
|-----------------------|-----------------------------------|
| Follower 追上 Leader LEO | Follower 在 `replica.lag.time.max.ms` 内未拉取数据 |
| 重启后追上 Leader       | 网络中断 / Follower 进程崩溃        |
| 落后后恢复同步         | 长时间 GC 停顿                     |

**重要事实**:ISR 的状态由 **Leader 维护**。Leader 在每次收到 FetchRequest 时,会更新该 Follower 的「最后同步时间戳」;后台线程(`ReplicaManager.isrExpirator`)周期性扫描,超时未更新的就剔除出 ISR。

---

## 四、数据同步过程

### 4.1 Follower 拉取消息

Follower 通过 **`FetchRequest`** 主动向 Leader 拉取消息,而不是 Leader 主动推送。这种「拉模式」的好处是 Follower 可以根据自己的消费能力调整拉取节奏,不会因推送过快而崩溃。

**Fetch 请求的关键参数**:

| 参数                              | 含义                                                |
|-----------------------------------|-----------------------------------------------------|
| `replica.fetch.min.bytes`         | 每次拉取的最小字节数(默认 1)                       |
| `replica.fetch.max.bytes`         | 每次拉取的最大字节数(默认 1MB)                      |
| `fetch.min.bytes` (consumer)      | Consumer 拉取的最小字节数                           |
| `replica.lag.time.max.ms`         | Follower 落后多久就被踢出 ISR(默认 30000)          |
| `num.replica.fetchers`            | Follower 端拉取线程数,提升同步速度(默认 1)         |

### 4.2 LEO 与 HW

要理解 Kafka 的同步过程,必须先理解两个核心概念:

| 概念                          | 全称                | 含义                                                            |
|-------------------------------|---------------------|-----------------------------------------------------------------|
| **LEO (Log End Offset)**      | 日志结束偏移量       | 每个副本写入日志的**下一条**消息的 offset,即「当前末尾+1」     |
| **HW (High Watermark)**       | 高水位              | 已经**所有 ISR 副本同步完成**的最高 offset,小于此 offset 的消息可被消费 |

**LEO 与 HW 的关系**:

- 每个副本都有自己的 LEO 和 HW
- Leader 的 HW = ISR 中**最小**的 LEO(最慢的那个决定)
- Follower 的 HW ≤ Follower 的 LEO ≤ Leader 的 LEO
- 消费者只能读取 **< HW** 的消息,确保「读到的消息一定已被所有 ISR 副本同步」

### 4.3 LEO/HW 计算示意图

以 3 个副本 (Leader + F1 + F2) 为例,展示 LEO 与 HW 的关系:

```text
时刻 T1(初始状态,F1 已追上,F2 落后)
─────────────────────────────────────────────────────
Leader    [0 1 2 3 4 5 6 7]            LEO=8  HW=5
                ▲
                │ Leader HW = min(Leader.LEO, F1.LEO, F2.LEO)
                │             = min(8, 6, 4) = 4
                │
                │ 修正:F1.LEO=6,F2.LEO=4 → HW=4
                │

Leader    [0 1 2 3 4 5 6 7]            LEO=8  HW=4   ✓ 修正后
F1        [0 1 2 3 4 5]                 LEO=6  HW=4
F2        [0 1 2 3]                    LEO=4  HW=4

消费者能读:[0,1,2,3]  (offset < HW = 4)


时刻 T2(F2 继续追赶,F1 仍同步中)
─────────────────────────────────────────────────────
Leader    [0 1 2 3 4 5 6 7 8 9]         LEO=10  HW=6
F1        [0 1 2 3 4 5 6 7]            LEO=8   HW=6
F2        [0 1 2 3 4 5]                LEO=6   HW=6

HW = min(10, 8, 6) = 6
消费者能读:[0..5]


时刻 T3(F2 仍未追上,但 F1 已追上)
─────────────────────────────────────────────────────
Leader    [0 1 2 3 4 5 6 7 8 9 10 11]   LEO=12  HW=8
F1        [0 1 2 3 4 5 6 7 8 9]        LEO=10  HW=8
F2        [0 1 2 3 4 5]                LEO=6   HW=6   ← 落后,F2 在 ISR 内但 HW 不前进

HW = min(12, 10, 6) = 6   ← 注意:此时 Leader 的 HW 也只能等于 F2 的 LEO
消费者能读:[0..5]         ← 直到 F2 追上,HW 才会前进
```

**LEO/HW 的核心规则**:

1. **HW 由 ISR 中最小的 LEO 决定**——「木桶效应」
2. **Leader HW 是分区的真实 HW**,Follower HW 仅是参照
3. **Follower 收到 Leader HW 后会截断本地 log**,删除 HW 之后的消息(防止脏读)
4. 写入路径上,**Leader 先写本地 log → 推进自己的 LEO → 收到 Follower Fetch → 推进 HW → Producer 拿到 ACK**

### 4.4 完整同步时序图

下面展示一条消息从 Producer 到 Leader,再到 Follower,最终可被消费者消费的完整时序:

```text
  Producer              Leader                Follower(F1)             Consumer
     │                    │                       │                       │
     │ ① produce(msg=5)  │                       │                       │
     ├───────────────────>│                       │                       │
     │                    │                       │                       │
     │                    │ ② 写本地 log          │                       │
     │                    │    Leader.LEO = 6     │                       │
     │                    │                       │                       │
     │                    │ ③ 返回 ACK(取决于acks)│                       │
     │<───────────────────┤                       │                       │
     │                    │                       │                       │
     │                    │ ④ FetchRequest(F1)    │                       │
     │                    │<──────────────────────┤                       │
     │                    │                       │                       │
     │                    │ ⑤ 返回 msg 5          │                       │
     │                    ├──────────────────────>│                       │
     │                    │    (F1 写本地 log)    │                       │
     │                    │    F1.LEO = 6         │                       │
     │                    │                       │                       │
     │                    │ ⑥ 推进 HW             │                       │
     │                    │    HW = min(LEO) = 6  │                       │
     │                    │                       │                       │
     │                    │ ⑦ 下一次 FetchRequest │                       │
     │                    │<──────────────────────┤                       │
     │                    │  携带 Leader HW = 6   │                       │
     │                    │                       │                       │
     │                    │ ⑧ 截断 F1 HW=6       │                       │
     │                    ├──────────────────────>│                       │
     │                    │                       │                       │
     │                    │                       │    ⑨ Fetch(Consumer)  │
     │                    │<──────────────────────────────────────────────┤
     │                    │                       │                       │
     │                    │ ⑩ 返回 msg 0..5       │                       │
     │                    ├──────────────────────────────────────────────>│
     │                    │                       │                       │
```

**流程拆解**:

```text
1. Producer 发送 produce 请求,带 acks 参数
2. Leader 写入本地 log,推进自己的 LEO
3. 根据 acks 决定是否立刻返回:
   - acks=0:立刻返回
   - acks=1:本地写入即返回
   - acks=all:等所有 ISR 副本 LEO ≥ 当前 offset 才返回
4. Follower 异步(或准同步)拉取
5. Follower 写入本地 log,推进自己的 LEO
6. Leader 根据 ISR 内最小 LEO 推进 HW
7. Consumer 只能读到 HW 之前的消息
```

### 4.5 同步状态判断

Follower 副本是否「同步中」,由 Leader 通过两个维度判断:

| 维度         | 含义                                                       |
|--------------|------------------------------------------------------------|
| **时间维度** | Follower 是否在 `replica.lag.time.max.ms` 内发过 FetchRequest |
| **进度维度** | Follower 的 LEO 是否追到 Leader 的 LEO 附近(已被时间维度间接覆盖) |

**早期版本**(Kafka 0.9 之前)是基于「**进度差**」判断:Follower 落后 Leader 超过 `replica.lag.max.messages` 条消息就被踢出 ISR。但这种方式问题很多(批量写入时容易误判、网络抖动时易抖动),从 0.9 版本起改为基于 **时间维度**,稳定性和可预测性大幅提升。

---

## 五、ACK 三种模式详解

### 5.1 acks 参数的作用

Producer 在发送消息时可以指定 `acks` 参数,告诉 Leader 「这次写入需要多少副本确认才算成功」。这是**数据可靠性**与**写入吞吐**之间的核心权衡点。

### 5.2 三种 ACK 模式对比

| 模式 | 含义 | 可靠性 | 吞吐 | 适用场景 |
|------|------|--------|------|----------|
| **`acks=0`** | Producer 发出请求后立即返回,**不等待任何确认** | 最低 | 最高 | 日志收集、可容忍丢失的场景 |
| **`acks=1`** | Leader 写入本地 log 即返回,**不等 Follower** | 中等 | 中等 | 普通业务、可容忍 Leader 切换丢失少量消息 |
| **`acks=all`**(或 `-1`) | 等所有 **ISR** 副本写入完成才返回 | 最高 | 最低 | 金融、订单、不能丢消息的核心场景 |

### 5.3 三种模式的时序差异

```text
acks=0(发后即忘)
────────────────────
Producer                Leader
   │                      │
   │ ① send              │
   ├─────────────────────>│
   │                      │
   │ ② 立刻返回 success   │
   │<─────────────────────┤
   │ (不等任何确认)

   风险:Leader 还没写入,Producer 就认为成功 → 消息可能丢失


acks=1(Leader 写入即返回)
─────────────────────────────
Producer                Leader                Follower
   │                      │                      │
   │ ① send              │                      │
   ├─────────────────────>│                      │
   │                      │ ② 写本地 log         │
   │                      │ ③ 返回 ACK           │
   │<─────────────────────┤                      │
   │                      │                      │
   │                      │ ④ Follower 异步拉取  │
   │                      ├─────────────────────>│

   风险:Leader 写入后宕机,Follower 还没同步 → 新 Leader 上没这条消息


acks=all(所有 ISR 同步完成)
──────────────────────────────────
Producer                Leader                Follower-1     Follower-2
   │                      │                      │               │
   │ ① send              │                      │               │
   ├─────────────────────>│                      │               │
   │                      │ ② 写本地 log         │               │
   │                      │ ③ 推送数据           │               │
   │                      ├─────────────────────>│               │
   │                      ├─────────────────────────────────────>│
   │                      │                      │ 写本地 log    │ 写本地 log
   │                      │                      │ ④ ACK        │ ⑤ ACK
   │                      │<─────────────────────┤               │
   │                      │<─────────────────────────────────────┤
   │                      │ ⑥ 所有 ISR ACK 收到   │               │
   │                      │ ⑦ 推进 HW,返回 ACK    │               │
   │<─────────────────────┤                      │               │
   │                      │                      │               │

   风险:即使 Leader 宕机,只要 ISR 内至少有一个 Follower 存活,
        新 Leader 上仍保留该消息 → 不丢失
```

### 5.4 配合 `min.insync.replicas` 使用

仅设置 `acks=all` 还不够安全——如果 ISR 列表退化为只有 Leader 自己(其他 Follower 都掉线),`acks=all` 实际上退化为 `acks=1`。必须配合 **`min.insync.replicas`** 参数才能确保「至少 N 个副本都写入才返回成功」。

```bash
# Broker 端
min.insync.replicas = 2

# Producer 端
acks = all
```

只有 ISR 中的副本数 **≥** `min.insync.replicas` 时,Producer 的 `acks=all` 请求才会被处理;否则返回 `NotEnoughReplicasException`,Producer 端可以根据业务决定重试或丢弃。

### 5.5 实战建议

| 业务场景               | 推荐配置                              | 说明                           |
|------------------------|---------------------------------------|--------------------------------|
| **金融、订单、支付**   | `acks=all` + `min.insync.replicas=2` | 不允许任何丢失                  |
| **普通业务消息**       | `acks=1` + 3 副本                     | 允许 Leader 切换时少量丢失     |
| **日志、监控、统计**   | `acks=0` 或 `acks=1`                  | 性能优先,可容忍偶尔丢失       |
| **跨数据中心同步**     | `acks=all` + 异步镜像                 | 一致性优先                     |

---

## 六、副本同步异常处理

### 6.1 Follower 故障

**场景**:某个 Follower 副本长时间宕机或网络中断。

```text
时间线:

T1  正常状态:ISR = [Leader, F1, F2, F3]
T2  F1 进程崩溃,长时间未发送 Fetch
T3  Leader 的 isrExpirator 检测到 F1 超过 replica.lag.time.max.ms 未拉取
T4  Leader 将 F1 从 ISR 中移除
T5  此时 ISR = [Leader, F2, F3],F1 进入 OSR
T6  Producer 继续写入,Leader HW = min(LEO) = min(F2/F3 的 LEO)
T7  F1 进程恢复,从上一次记录的 offset 重新拉取
T8  F1 追上 Leader LEO,被重新加入 ISR
T9  ISR = [Leader, F1, F2, F3],恢复正常
```

**关键点**:

- Leader 的 HW 在 F1 故障期间可能**停滞不前**(取决于 F2/F3 的同步速度)
- F1 重启后**不会清空数据**,而是接着断点继续拉取
- 如果 F1 的 log 文件损坏,可能需要 `kafka-reassign-partitions` 重新分配

### 6.2 Leader 故障

**场景**:Leader 副本宕机,集群中只剩 Follower。

```text
时间线:

T1  正常状态:ISR = [Leader(L), F1, F2],HW = 100
T2  Leader 进程崩溃
T3  Controller(集群中一个 Broker)感知到 Leader 下线
T4  Controller 从 ISR 中选举新的 Leader:
    - 如果 ISR 中有 F1,选举 F1 为新 Leader
    - 如果 ISR 都不可用,看 unclean.leader.election.enable 配置
T5  新 Leader 通知其他 Broker 更新元数据
T6  Producer 重试写入(可能因元数据更新短暂失败)
T7  Consumer 重连到新 Leader 继续消费
```

**关键点**:

- 新 Leader 选举由 **Controller** 协调,**不依赖 ZK 临时节点**(新版本基于 KRaft)
- 选举过程中分区可能**短暂不可用**(几百毫秒)
- 新 Leader 的 HW = ISR 中最小的 LEO(可能比原 Leader HW 略低)

### 6.3 数据丢失与不一致

**场景 1**:`acks=1` 时 Leader 宕机

```text
T1  Producer 发送 msg=100,acks=1
T2  Leader 写入本地 log,LEO=101
T3  Leader 返回 ACK 给 Producer
T4  Leader 还没来得及把数据推给 Follower 就宕机
T5  Controller 从 F1(F1.LEO=99) 选举为新 Leader
T6  新 Leader 的 HW=99,msg=100 在新 Leader 上不存在
T7  Producer 认为 msg=100 已成功,实际丢失
```

**结论**:`acks=1` 不能保证消息不丢。

**场景 2**:`acks=all` 但 `min.insync.replicas=1`

```text
T1  ISR = [Leader, F1, F2]
T2  F1 和 F2 同时宕机,ISR 收缩为 [Leader]
T3  Producer 发送 msg,acks=all
T4  此时 min.insync.replicas=1,Leader 仅自己写入就 ACK
T5  Leader 宕机,新 Leader(F3 选举)LEO 落后 → 消息丢失
```

**结论**:必须同时设置 `acks=all` 和 `min.insync.replicas≥2` 才能可靠保证。

**场景 3**:`unclean.leader.election.enable=true` 下的丢失

```text
T1  ISR = [Leader, F1],OSR = [F2](F2 已落后很久)
T2  Leader 和 F1 同时宕机
T3  正常情况下 ISR 内无可用副本,无法选举
T4  但 unclean=true 时,F2(OSR 中的)被选举为新 Leader
T5  F2 的数据严重落后于原 Leader → 已经 ACK 的消息"丢失"
```

**结论**:`unclean=true` 会牺牲一致性换取可用性,生产环境**必须保持默认 false**。

---

## 七、Leader 选举(Kafka Controller)

### 7.1 Controller 的角色

**Controller** 是 Kafka 集群中一个特殊的 Broker,负责管理集群的元数据和协调 Leader 选举:

| 职责             | 说明                                                       |
|------------------|------------------------------------------------------------|
| **集群元数据**   | 维护 Topic、Partition、Replica 的元数据                     |
| **Leader 选举**  | 当 Leader 宕机时,从 ISR 中选出新 Leader                    |
| **副本管理**     | 处理新副本加入、副本下线、副本重分配等事件                  |
| **状态同步**     | 通过 ZK(或 KRaft)将变更广播给所有 Broker                   |

### 7.2 选举流程(基于 ZK 旧版本)

```text
   ┌─────────────────────────────────────────────┐
   │                  ZK                         │
   │  /controller 临时节点(只允许一个 Broker)    │
   └─────────────────────────────────────────────┘
                       ▲
                       │ 注册/监听
                       │
            ┌──────────┴──────────┐
            │   所有 Broker        │
            │  竞争创建 /controller│
            └──────────┬──────────┘
                       │
                       ▼
            ┌─────────────────────┐
            │  第一个成功创建的    │  ← Controller
            │  Broker 担任 Controller│
            └─────────────────────┘
                       │
                       │ 监听 /brokers/ids/<brokerId>
                       │
                       ▼
   Leader Broker 宕机
                       │
                       ▼
   Controller 收到 session 过期事件
                       │
                       ▼
   从 ISR 中选择第一个副本作为新 Leader
                       │
                       ▼
   更新 /brokers/topics/<topic>/partitions/<p>/state
                       │
                       ▼
   通知其他 Broker 更新元数据
```

### 7.3 选举流程(基于 KRaft 新版本,Kafka 2.8+)

```text
   ┌─────────────────────────────────────────────────────┐
   │  KRaft 集群(无 ZK)                                  │
   │  所有 Broker 都是 Raft 集群成员                      │
   │  - 部分 Broker 是 Active Controller                 │
   │  - 其余是 Follower Controller                       │
   └─────────────────────────────────────────────────────┘
                       │
                       │ Leader 副本宕机
                       ▼
   ┌─────────────────────────────────────────────┐
   │  Active Controller 监听 Replica 状态        │
   │  通过 __consumer_offsets 类似的内部 topic 协调│
   └─────────────────────────────────────────────┘
                       │
                       ▼
   从 ISR 中选择第一个副本作为新 Leader
                       │
                       ▼
   将变更写入 __cluster_metadata topic(Raft 日志)
                       │
                       ▼
   其他 Broker(包括 Follower Controller)应用变更
```

**KRaft 优势**:

- 不依赖 ZK,部署运维更简单
- 元数据变更走 Raft 协议,一致性更强
- Controller 故障恢复更快(几百毫秒)
- 支持更大规模集群(百万级 Partition)

### 7.4 选举的优先级

新 Leader 的选举不是随机的,而是有优先级的:

```text
优先级从高到低:

1. ISR 中的副本,按 Replica 列表顺序选第一个
2. (若 unclean=true)OSR 中的副本,按列表顺序选第一个
3. 没有可用副本时,抛 NoReplicaOnlineException
```

通过 `kafka-topics.sh --describe` 可以看到分区的 Leader、ISR、OSR 信息:

```bash
$ kafka-topics.sh --bootstrap-server localhost:9092 \
                   --describe --topic order-topic

Topic: order-topic   Partition: 0   Leader: 2   Replicas: 1,2,3   Isr: 2,3
Topic: order-topic   Partition: 1   Leader: 3   Replicas: 2,3,1   Isr: 3,1
Topic: order-topic   Partition: 2   Leader: 1   Replicas: 3,1,2   Isr: 1,2
```

---

## 八、最小 ISR 数量(min.insync.replicas)

### 8.1 数据可靠性保证

**`min.insync.replicas`** 是 Broker 端的关键配置,定义了「一次写入最少需要多少副本同步成功才算数」。它与 Producer 端的 `acks=all` 配合使用,共同保证数据的可靠性。

**核心规则**:

| 规则                                       | 说明                                                                 |
|--------------------------------------------|----------------------------------------------------------------------|
| `min.insync.replicas` 是**写入的最低门槛** | ISR 副本数 < 该值时,**拒绝**所有 `acks=all` 的写入请求             |
| Producer 端 `acks=all` 是**等待所有 ISR** | 配合 `min.insync.replicas` 才真正发挥作用                            |
| 默认值 `min.insync.replicas=1`             | 即只要求 Leader 自己写入(等于 `acks=1`,基本无保障)                 |

### 8.2 配置示例

```bash
# Broker 配置(server.properties)
default.replication.factor=3
min.insync.replicas=2

# Topic 创建时显式指定
kafka-topics.sh --create \
  --topic order-topic \
  --partitions 3 \
  --replication-factor 3 \
  --config min.insync.replicas=2
```

### 8.3 不可用场景

当 ISR 副本数小于 `min.insync.replicas` 时,集群进入**只读模式**:

```text
正常状态:
  ISR = [L, F1, F2]  (3 个副本)
  min.insync.replicas = 2
  Producer(acks=all) ✓ 可写入


降级状态(一个 Follower 长时间掉线):
  ISR = [L, F1]  (2 个副本,等于 min.insync.replicas)
  Producer(acks=all) ✓ 仍可写入(刚好满足)


不可用状态(两个 Follower 都掉线):
  ISR = [L]  (1 个副本,小于 min.insync.replicas=2)
  Producer(acks=all) ✗ 写入被拒绝
                   抛 NotEnoughReplicasException
  Consumer ✓ 仍可读(读取历史消息不受影响)


极端情况(Leader 自己也掉线):
  ISR = []
  Producer ✗ 写入被拒绝
  Consumer ✗ 读也被拒绝(无 Leader)
```

### 8.4 生产建议

| 副本数 | min.insync.replicas | 说明                                                  |
|--------|---------------------|-------------------------------------------------------|
| 3      | 2                   | 最常见的生产配置,允许 1 个副本故障,写入仍可靠        |
| 5      | 3                   | 高可靠性配置,允许 2 个副本故障                        |
| 3      | 3                   | 极端严格配置,任何副本掉线都无法写入(可用性差)       |

**经验法则**:

- `min.insync.replicas` ≤ `replication.factor - 1`
- 通常设置为 **`replication.factor - 1`**,这样允许最多 1 个副本掉线时仍能写入

---

## 九、unclean.leader.election.enable

### 9.1 严格模式(默认 false)

**`unclean.leader.election.enable`** 控制当 ISR 中没有可用副本时,**是否允许从 OSR 中选举 Leader**。

- **`false`(默认,严格模式)**:ISR 空 → 选举失败 → 分区不可用 → 优先保证**一致性**
- **`true`(允许模式)**:ISR 空 → 从 OSR 选举 → 牺牲数据一致性 → 优先保证**可用性**

### 9.2 严格模式行为

```text
正常情况:
  ISR = [L, F1, F2]
  L 宕机 → 从 [F1, F2] 中选举 → 成功


降级情况:
  ISR = [L, F1]
  L 宕机 → F1 提升为 Leader → 成功


极端情况(unclean=false):
  ISR = [L]
  L 宕机 → ISR 空 → 选举失败
         → 该分区停止服务
         → Producer 写入失败
         → Consumer 读取失败

  表现:集群会"宁可不可用,也不丢消息"
```

### 9.3 允许切换的风险

```text
unclean=true 时的极端情况:
  ISR = [L] (F1 已掉线很久,被踢到 OSR)
  OSR = [F1]  (F1 的 LEO 落后 L 很多,例如 L.LEO=1000,F1.LEO=500)
  L 宕机

  启用 unclean=true:
  → F1 被选为新 Leader
  → F1 的 HW=500
  → 500~1000 之间的消息(原 Leader 已 ACK 但 F1 没同步)全部"消失"
  → Producer 端:之前返回 ACK 的消息现在读不到了
  → 消费者:看到消息"凭空消失"

  数据一致性彻底被破坏
```

### 9.4 生产建议

| 业务场景             | 建议配置                                | 理由                           |
|----------------------|-----------------------------------------|--------------------------------|
| **金融、订单、计费** | `unclean.leader.election.enable=false`  | 优先保证数据,宁可短暂不可用    |
| **日志、监控**       | `unclean=true` 可考虑(但通常没必要)    | 允许少量丢失换取可用性         |
| **普通业务**         | 保持默认 `false`                         | 一致性永远比可用性重要         |

**绝大多数生产场景应保持默认 false**。如果你思考是否要开启它,先想清楚业务能否接受「已经 ACK 的消息凭空消失」。

---

## 十、副本同步延迟监控

### 10.1 replica.lag.time.max.ms

**`replica.lag.time.max.ms`**(默认 30000 毫秒)是 Kafka 中判断 Follower 是否同步的核心阈值。它的含义是:

> 如果一个 Follower 在该时间窗口内**没有成功向 Leader 发送 FetchRequest**,Leader 就认为这个 Follower 已经掉队,把它从 ISR 中移除。

这个机制比早期基于「落后消息数」的判断更稳定:

| 维度         | 时间维度(当前)                  | 进度维度(早期,已废弃)                |
|--------------|----------------------------------|---------------------------------------|
| **判断标准** | 落后时间                         | 落后消息数                            |
| **稳定性**   | 不受批量写入影响                  | 批量写入时容易抖动                    |
| **可预测性** | 与业务 QPS 无关,阈值固定         | 阈值难以合理设置                      |
| **网络敏感** | 对短暂网络抖动不敏感             | 网络抖动容易误判                      |

### 10.2 延迟检测机制

Kafka 内部使用一个后台线程 `ReplicaManager.isrExpirator` 来检测延迟:

```text
   Leader 维护每个 Follower 的「lastFetchTime」

   ┌──────────────────────────────────────────────┐
   │  isrExpirator 线程(周期性运行)               │
   │  间隔:replica.lag.time.max.ms / 2            │
   └──────────────────────────────────────────────┘
                       │
                       │ 每次执行:
                       ▼
   for each Follower in ISR:
       if (now - lastFetchTime > replica.lag.time.max.ms):
           从 ISR 中移除该 Follower
           加入 OSR
           触发 LeaderAndIsr 请求,通知 Controller
```

### 10.3 监控指标

通过 JMX 暴露的关键指标:

| 指标                                              | 含义                                                 |
|---------------------------------------------------|------------------------------------------------------|
| `kafka.server:type=ReplicaManager,name=UnderMinIsr` | ISR 数量低于 min.insync.replicas 的分区数           |
| `kafka.server:type=ReplicaManager,name=UnderReplicatedPartitions` | 副本数小于期望值的分区数                  |
| `kafka.server:type=ReplicaFetcherManager,name=MaxLag` | 所有副本中的最大 LEO 落后量                        |
| `kafka.controller:type=ControllerStats,name=UncleanLeaderElectionsPerSec` | unclean 选举的频率(应持续为 0) |

**Kafka 自带的监控脚本**:

```bash
# 查看消费组延迟
kafka-consumer-groups.sh --bootstrap-server localhost:9092 \
                          --describe --group my-group

# 查看 Topic 副本状态
kafka-topics.sh --bootstrap-server localhost:9092 \
                 --describe --topic order-topic

# 关注字段:
#   Leader: 当前 Leader Broker
#   Replicas: 所有副本列表
#   Isr: 当前 ISR 列表
#   如果 Isr ≠ Replicas,说明有副本掉队
```

### 10.4 延迟异常排查

```text
发现 Isr 收缩(副本掉队)
        │
        ├─> 检查 Follower 进程是否存活
        │       │
        │       ├─> 进程不存在 ──> 启动 Broker 进程
        │       └─> 进程存在 ──> 进一步排查
        │
        ├─> 检查网络连通性
        │       │
        │       ├─> ping / telnet Follower 端口
        │       └─> 检查防火墙 / 安全组
        │
        ├─> 检查磁盘 I/O
        │       │
        │       ├─> iostat 查看 %util 是否 100%
        │       └─> 是否存在磁盘故障预警
        │
        ├─> 检查 GC 情况
        │       │
        │       ├─> jstat -gcutil <pid>
        │       └─> 是否频繁 Full GC
        │
        └─> 检查 Follower 拉取线程
                │
                ├─> num.replica.fetchers 是否合理
                └─> replica.fetch.max.bytes 是否过小
```

---

## 十一、副本数据一致性保证

### 11.1 HW 高水位

HW(High Watermark)是 Kafka 数据一致性的基石,定义如下:

> **HW 是分区级别的「已经所有 ISR 副本写入成功」的最高 offset**,小于 HW 的消息可以被消费者读取,大于等于 HW 的消息不可以被消费。

**HW 的双重作用**:

| 作用         | 说明                                                              |
|--------------|-------------------------------------------------------------------|
| **消费可见性** | 消费者只能读到 < HW 的消息,保证读到的消息都已被所有 ISR 持久化 |
| **日志截断**   | Follower 收到 Leader HW 后,删除 HW 之后的本地消息,防止脏读     |

**HW 的不足**:

HW 机制虽然能保证消费者不读到「未同步完成」的消息,但**不能完全防止数据丢失**。考虑如下场景:

```text
T1  ISR = [L, F1, F2],HW = 100
T2  Producer 发送 msg=101,Leader 写入,Leader.LEO=102
T3  Leader 等 F1,F2 同步,F1,F2.LEO 都追到 102
T4  Leader HW = 102,返回 ACK
T5  Producer 收到 ACK
T6  Leader 准备把 HW 写到本地 log(异步操作)
T7  Leader 还没把 HW=102 写入本地,Leader 宕机
T8  F1 被选为新 Leader,F1.LEO=102(数据已同步)
T9  F1 提升为 Leader 时,F1 的 HW 仍是 100(没收到过 Leader 的新 HW)
T10 新 Leader 把 HW 设为 min(LEO) = 102(实际可能仍是 100,要看时机)
T11 msg=101 是否被消费取决于新 Leader 的最终 HW
```

这种边界情况下,即使消息已经 ACK,新 Leader 上 HW 可能暂时落后,**已被 ACK 但未在 HW 内的消息可能短暂不可见**。这就是 HW 机制的固有缺陷。

### 11.2 Leader Epoch(KIP-101)

为了解决 HW 机制的不足,Kafka 引入了 **Leader Epoch**(基于 KIP-101),从 0.11.0.0 版本开始提供。

**核心思想**:

> 每个 Leader 在任期内都有一个单调递增的 epoch 编号。新 Leader 选举时会自增 epoch,并把 epoch 与起始 offset 写入本地日志。Follower 通过比较 epoch 来判断 Leader 的新旧。

**Leader Epoch 的改进前后对比**:

| 维度         | 改进前(仅 HW)                          | 改进后(Leader Epoch + HW)                            |
|--------------|------------------------------------------|-------------------------------------------------------|
| **数据丢失场景** | Leader 已 ACK 但 HW 未持久化,切换后消息丢失 | 新 Leader 通过 epoch 找到上一个 Leader 最后的 offset,强制设 HW |
| **HW 起点判断** | Follower 不知道 HW 应该从哪里开始        | Follower 通过 epoch 知道 Leader 的截断位置             |
| **截断恢复**   | Follower 截断 log 后无依据恢复           | 通过 epoch 缓存可以恢复到精确位置                     |

**Leader Epoch 工作机制**:

```text
Leader L1(epoch=1):
   任期:term-1
   写入:offset 0..200
   任期结束时的 HW = 200
   缓存 epoch=1 → startOffset=200


Leader L1 宕机,L2 选举为新 Leader(epoch=2):
   L2 启动时:缓存 epoch=2 → startOffset=?
   L2 查询 epoch=1 的缓存,得知 L1 最后的 offset=200
   L2 的初始 HW = 200(从 epoch=1 的最后 offset 开始)


Producer 视角的对比:

改进前:
   L1 写入 msg=150,返回 ACK
   L1 宕机,L2 选举
   L2 的初始 HW 可能小于 150
   msg=150 在 L2 上"丢失"

改进后:
   L1 写入 msg=150,epoch=1,返回 ACK
   L1 宕机,L2 选举,epoch=2
   L2 通过 epoch 缓存找到 L1 最后 offset=200
   L2 把 HW 设为 200(向下兼容),不丢失
```

**关键数据结构**:`__leader_epoch_checkpoint`,记录每个 Leader 任期对应的起始 offset,保存在每个副本本地。

### 11.3 实际效果

**纯 HW 模式**(0.11 之前):

- 可能存在「ACK 后丢失」的情况(罕见但可能)
- 不保证 EOS(Exactly Once Semantics)

**HW + Leader Epoch 模式**(0.11+):

- 显著降低「ACK 后丢失」概率
- 为 Kafka 的 **EOS 事务**(幂等 Producer + 事务 Producer)打下基础
- 是 Kafka 2.x/3.x 推荐的部署配置

---

## 十二、增加副本因子

### 12.1 为什么需要增加副本

随着业务发展,可能需要调整副本数:

| 场景             | 原因                                                           |
|------------------|----------------------------------------------------------------|
| **可靠性升级**   | 从 2 副本升级到 3 副本,降低数据丢失风险                        |
| **机房扩展**     | 在新机房增加副本,做异地容灾                                    |
| **读取扩展**     | 增加 Follower 副本,分担读压力                                  |
| **负载均衡**     | 重新分配副本到不同的 Broker,平衡磁盘与网络                     |

### 12.2 kafka-reassign-partitions 工具

Kafka 提供了官方的 **`kafka-reassign-partitions.sh`** 工具来重新分配副本。

**步骤 1:生成 reassignment JSON**

```bash
# 方式 A:基于现有 Topic 自动生成建议
kafka-reassign-partitions.sh \
    --bootstrap-server localhost:9092 \
    --topics-to-move-json-file topics.json \
    --broker-list "1,2,3,4,5" \
    --generate
```

```json
// topics.json
{
  "topics": [
    { "topic": "order-topic" }
  ],
  "version": 1
}
```

```bash
# 方式 B:手写 JSON,精确指定每个分区的副本列表
cat > reassign.json <<EOF
{
  "version": 1,
  "partitions": [
    { "topic": "order-topic", "partition": 0, "replicas": [1,3,5] },
    { "topic": "order-topic", "partition": 1, "replicas": [2,4,1] },
    { "topic": "order-topic", "partition": 2, "replicas": [3,5,2] }
  ]
}
EOF
```

**步骤 2:执行 reassignment**

```bash
kafka-reassign-partitions.sh \
    --bootstrap-server localhost:9092 \
    --reassignment-json-file reassign.json \
    --execute
```

**步骤 3:查看进度**

```bash
kafka-reassign-partitions.sh \
    --bootstrap-server localhost:9092 \
    --reassignment-json-file reassign.json \
    --verify
```

### 12.3 数据迁移流程图

增加一个副本的过程,本质就是「把目标分区的数据从 Leader 复制到新 Broker」:

```text
初始状态:P0 副本分布在 [B1, B2],现在要增加到 [B1, B2, B3]

┌──────────┐         ┌──────────┐
│   B1     │         │   B2     │
│   L      │ ◄────── │   F1     │
│  [0..9]  │  拉取   │  [0..9]  │
└──────────┘         └──────────┘


执行 reassign:
   ┌─────────────────────────────────────────────────┐
   │  1. Controller 收到 reassignment 请求            │
   │  2. 更新内部状态:P0 新副本列表 = [B1, B2, B3]    │
   │  3. 在 B3 上创建 P0 的副本目录(空)               │
   │  4. B3 启动时发现自己是新副本,启动 Fetch          │
   └─────────────────────────────────────────────────┘

迁移过程:
   ┌──────────┐         ┌──────────┐         ┌──────────┐
   │   B1     │         │   B2     │         │   B3     │
   │   L      │ ──────> │   F1     │         │   F2     │
   │  [0..9]  │  拉取   │  [0..9]  │         │  [空]    │
   └──────────┘         └──────────┘         └──────────┘
                                                 │
                                                 │ 新副本拉取
                                                 ▼
                                          B3 开始从 B1 拉数据
                                          (可能先从最近 checkpoint 开始)


完成状态:
   ┌──────────┐         ┌──────────┐         ┌──────────┐
   │   B1     │         │   B2     │         │   B3     │
   │   L      │ ──────> │   F1     │ ──────> │   F2     │
   │  [0..9]  │  拉取   │  [0..9]  │  拉取   │  [0..9]  │
   └──────────┘         └──────────┘         └──────────┘
   ISR = [B1, B2, B3]
```

**关键点**:

- 数据迁移过程中,**不影响正常的读写**(读写仍由 Leader 处理)
- 新副本从 Leader 的最新 log 拉取,逐步追上
- 如果新副本所在 Broker 没有该分区的历史数据,会**全量拉取**(可能耗时较长)
- 迁移完成后,新副本自动加入 ISR

### 12.4 副本重分配的最佳实践

| 场景         | 建议                                                                      |
|--------------|---------------------------------------------------------------------------|
| **时间窗口** | 选择业务低峰期执行,避免影响写入                                           |
| **限速**     | 使用 `--throttle` 参数限制传输带宽,避免抢占业务带宽                       |
| **小步快跑** | 一次不要迁移太多分区,分批进行,每批观察再继续                              |
| **验证**     | 完成后用 `--verify` 确认所有分区 ISR 正常                                  |
| **回滚**     | 重分配过程中如有问题,可以再次执行把副本列表改回原样                        |

```bash
# 限速示例:每次最多 50MB/s
kafka-reassign-partitions.sh \
    --bootstrap-server localhost:9092 \
    --reassignment-json-file reassign.json \
    --execute \
    --throttle 52428800
```

---

## 十三、实战案例

### 13.1 副本数选择(3 副本 vs 5 副本)

**核心权衡**:副本数 = 可靠性 = 资源消耗,成正比。

| 副本数 | 可靠性                            | 资源消耗(磁盘/网络)         | 适用场景                  |
|--------|-----------------------------------|------------------------------|---------------------------|
| **1**  | 无冗余,Broker 故障即数据丢失    | 最低                        | 仅用于开发测试             |
| **2**  | 容忍 1 个 Broker 故障            | 2x 单副本                   | 不推荐生产                |
| **3**  | 容忍 1 个故障 + 1 个 ISR 收缩   | 3x 单副本                   | **绝大多数生产场景推荐** |
| **5**  | 容忍 2 个故障                    | 5x 单副本                   | 金融、关键订单业务        |
| **N**  | 容忍 N-1 故障(理论)             | Nx 单副本                   | 极少数极端场景            |

**3 副本的典型配置**:

```bash
# Broker 端
default.replication.factor = 3
min.insync.replicas = 2

# Producer 端
acks = all

# Topic 创建
kafka-topics.sh --create \
  --topic order-topic \
  --partitions 6 \
  --replication-factor 3
```

**5 副本的典型配置**:

```bash
# Broker 端
default.replication.factor = 5
min.insync.replicas = 3

# Producer 端
acks = all

# 写入路径:Leader + 至少 4 个 Follower 都写入才 ACK
# 容忍任意 2 个 Broker 同时宕机仍可读写
```

**决策矩阵**:

| 业务类型 | 数据量 | 推荐副本 | 理由                                       |
|----------|--------|----------|--------------------------------------------|
| 订单、支付 | GB/TB 级 | 3 副本 | 可靠性足够,成本合理                       |
| 金融、账务 | GB 级   | 5 副本 | 不容忍任何丢失                             |
| 日志、监控 | TB 级   | 2 副本 | 容忍偶尔丢失,成本敏感                     |
| 用户行为 | TB+ 级  | 3 副本 | 大数据量下成本与可靠性的平衡              |

### 13.2 机架感知副本分配

**目标**:把同一个 Partition 的不同副本**分配到不同的物理机架(Rack)**上,防止单个机架掉电导致整个分区不可用。

```text
假设有 2 个机架:
  Rack-A: Broker 1, 2, 3
  Rack-B: Broker 4, 5, 6

普通分配(同分区副本可能全在 Rack-A):
  Topic T:
    P0: [B1, B2, B3]  ← 全在 Rack-A,Rack-A 断电 → P0 不可用 ✗
    P1: [B4, B5, B6]  ← 全在 Rack-B,Rack-B 断电 → P1 不可用 ✗


机架感知分配(副本跨机架):
  Topic T:
    P0: [B1, B4, B2]  ← 2 个在 Rack-A,1 个在 Rack-B ✓
    P1: [B4, B1, B5]  ← 2 个在 Rack-B,1 个在 Rack-A ✓
    P2: [B2, B5, B3]  ← 2 个在 Rack-A,1 个在 Rack-B ✓

任何单个机架掉电,所有分区仍至少有 1 个副本可用 ✓
```

**配置方法**:

```bash
# 1. 在 Broker 配置中指定机架
# 在每个 Broker 的 server.properties 中:
broker.rack=Rack-A    # Rack-A 上的 Broker 配这个
broker.rack=Rack-B    # Rack-B 上的 Broker 配这个

# 2. 创建 Topic 时,默认会按机架感知分配
kafka-topics.sh --create --topic order-topic --partitions 3 --replication-factor 3
# 不需要额外参数,Kafka 自动按 broker.rack 打散

# 3. 验证副本分布
kafka-topics.sh --describe --topic order-topic
```

**关键参数**:

| 参数                | 默认值 | 说明                                                       |
|---------------------|--------|------------------------------------------------------------|
| `broker.rack`       | `null` | Broker 所在机架名,空表示不启用机架感知                     |
| `replica.assignor`  | 旧版默认 Range,新版默认 `CooperativeSticky` | 副本分配算法       |
| `rack.aware.assignment` | 取决于 broker.rack | 自动启用 |

### 13.3 跨数据中心副本

**场景**:在异地机房部署副本,防止机房级(地震、断电、光纤中断)灾难。

```text
数据中心 A(主):
   Broker 1, 2, 3

数据中心 B(备):
   Broker 4, 5, 6

跨数据中心副本分配:
   Topic T:
     P0: L=B1, F1=B4, F2=B2   ← 1 个在 B(机房),2 个在 A
     P1: L=B2, F1=B5, F2=B3   ← 1 个在 B(机房),2 个在 A
     P2: L=B3, F1=B6, F2=B1   ← 1 个在 B(机房),2 个在 A
```

**配置**:

```bash
# Broker 端
# 数据中心 A 的 Broker
broker.rack=DC-A

# 数据中心 B 的 Broker
broker.rack=DC-B

# 关键参数:跨机房延迟会影响副本同步
replica.socket.timeout.ms=60000     # 网络超时
replica.lag.time.max.ms=60000       # 同步判定窗口(跨机房适当放宽)
```

**两种跨机房模式**:

| 模式         | 描述                                                                  |
|--------------|-----------------------------------------------------------------------|
| **Active-Active** | 两地都承担读写,Kafka 原生支持(配合 `inter.broker.listener.name`) |
| **Active-Passive** | 一地承担读写,异地仅做备份,异地副本不算 ISR,通过 **MirrorMaker** 同步 |

**MirrorMaker 跨机房同步**(更常见):

```text
数据中心 A(主):                      数据中心 B(备):
   ┌────────────┐                      ┌────────────┐
   │  Producer  │                      │  Consumer  │
   └─────┬──────┘                      └─────▲──────┘
         │                                   │
         ▼                                   │
   ┌────────────┐    MirrorMaker    ┌────────────┐
   │ Kafka 集群 │ ──────────────>  │ Kafka 集群 │
   │  (DC-A)    │                  │  (DC-B)    │
   └────────────┘                  └────────────┘

MirrorMaker 配置:
   - 消费 DC-A 的 Topic
   - 写入 DC-B 的同名 Topic
   - 异步批量同步,可容忍秒级延迟
```

**注意事项**:

- 跨机房延迟通常 10~50ms,会显著影响 ISR 同步速度
- 不建议在跨机房用 `acks=all` + 大副本因子,会拖慢写入
- 跨机房副本的 `replica.lag.time.max.ms` 应适当放宽(30s → 60s)
- 推荐用 **MirrorMaker 2** 替代老版 MirrorMaker,支持更多功能

---

## 十四、核心要点速记

- **副本三角色**:Leader(读写) / Follower(同步) / OSR(掉队)
- **ISR 定义**:与 Leader 保持同步的副本集合,包括 Leader 本身
- **ISR 判定标准**:`replica.lag.time.max.ms`(默认 30s)内必须成功拉取
- **LEO**:每个副本的日志末尾 offset;**HW**:ISR 内最小 LEO
- **HW 计算**:`HW = min(所有 ISR 副本的 LEO)`,木桶效应
- **消费者规则**:只能读 **< HW** 的消息
- **acks=0**:发后即忘,最高吞吐,最低可靠性
- **acks=1**:Leader 写入即返回,有 Leader 切换丢消息风险
- **acks=all**:等所有 ISR 同步,最高可靠性,需配合 `min.insync.replicas`
- **`min.insync.replicas`**:写入的最低门槛,默认 1,生产推荐 2
- **`replica.lag.time.max.ms`**:30000ms 默认,超过则踢出 ISR
- **Follower 故障**:重启后从断点继续拉取,自动重入 ISR
- **Leader 故障**:Controller 从 ISR 选举新 Leader(默认配置)
- **数据丢失**:`acks=1` + Leader 故障、ISR 空时 Leader 切换都可能丢消息
- **`unclean.leader.election.enable=false`**:默认配置,严格模式,生产保持
- **Leader 选举**:由 Controller 协调,优先从 ISR 中选
- **HW 缺陷**:Leader ACK 后宕机、HW 未持久化,切换可能丢消息
- **Leader Epoch (KIP-101)**:0.11+ 引入,通过 epoch 缓存解决 HW 缺陷
- **`kafka-reassign-partitions.sh`**:官方副本重分配工具
- **重分配最佳实践**:低峰期 + 限速(`--throttle`) + 分批进行
- **机架感知**:`broker.rack` 配置,副本自动跨机架
- **副本数推荐**:3 副本 + `min.insync.replicas=2`(绝大多数生产场景)
- **跨数据中心**:用 MirrorMaker 2 异步同步,不建议跨机房做严格 ISR
- **监控指标**:`UnderMinIsr`、`UnderReplicatedPartitions`、`MaxLag`
- **健康标志**:`Isr == Replicas`,副本未掉队