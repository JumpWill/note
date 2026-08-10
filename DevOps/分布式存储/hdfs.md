# HDFS (Hadoop Distributed File System)

Hadoop 生态的**分布式文件系统**，为大数据离线批处理而设计。写一次、读多次（write-once, read-many）模型，块级大文件、强一致、中心化元数据。仍然是大数据生态（Spark / Hive / Flink / HBase）的事实底座。

## 一、定位与特性

- **超大规模**：单集群万节点 / EB 级数据
- **流式数据访问**：高吞吐批量读写，非低延迟
- **简单一致性模型**：写一次，多次读；不支持随机写
- **块存储**：默认 128MB / 256MB 大块，适合大文件
- **容错**：3 副本机制，硬件故障自动恢复
- **生态绑定**：与 Hadoop / Spark / Hive 深度集成
- **不适合**：海量小文件、低延迟、随机写、对象语义

## 二、核心组件

| 组件 | 角色 |
| --- | --- |
| **NameNode (NN)** | 元数据服务：文件树、块位置、副本状态。**集群大脑** |
| **Secondary NameNode (SNN)** | 周期性合并 fsimage + edits，**不是热备**（HA 下被 Checkpoint Node / Backup Node 取代） |
| **DataNode (DN)** | 实际存数据块，定期向 NN 上报块状态 |
| **JournalNode (JN)** | HA 模式下共享编辑日志，仲裁元数据写入（典型 3 / 5 节点） |
| **ZKFC (ZKFailoverController)** | NameNode HA 切换控制器 |
| **Balancer** | 跨节点均衡块分布 |
| **HttpFS** | 暴露 HTTP REST 接口 |

## 三、架构与读写路径

### 1. 主从架构

```text
              ┌──────────────────┐
              │   NameNode × 2   │ ← Active / Standby
              │   (HA 模式)      │
              └────────┬─────────┘
                       │ 心跳 / 块报告
   ┌───────────┬───────┼───────┬───────────┐
   ▼           ▼       ▼       ▼           ▼
DataNode   DataNode  DataNode DataNode  DataNode
  ×N 节点   ×N 节点   ×N 节点  ×N 节点    ×N 节点
```

### 2. 写入路径

```text
Client
  1. 向 NameNode 询问：写入到哪些 DataNode？
     NN 根据副本策略（机架感知）返回 DN 列表（管道）
  2. Client → DN1 → DN2 → DN3 串行写入
     写入确认按管道反方向回传
  3. DN1 → DN2 → DN3 ACK
  4. Client 收到最终 ACK 后才认为成功
  5. NN 异步记录块位置（心跳时汇总）
```

### 3. 读取路径

```text
Client
  1. 向 NN 请求文件块位置
  2. NN 返回块到 DN 的映射
  3. Client 直接连最近的 DN 读
  4. 多块并行读
```

## 四、HA (高可用)

- 单 NN 是单点故障 → 必须 HA
- **Active / Standby NN** 共享编辑日志（通过 QJM / NFS）
- 客户端用 ZKFC 自动 failover
- 故障切换时间：~10~30 秒
- 仍存在 **NameNode 内存瓶颈**——所有元数据都在 NN 内存

## 五、副本策略与机架感知

```text
默认副本数 3
Block 1 → DN-A, DN-B, DN-C
   A 与 B 同机架
   C 不同机架（同机架放一个副本，跨机架放一个副本）
```

- **机架感知 (Rack Awareness)**:通过 `net.topology.script.file.name` 配置
- 副本分布规则：第 1 个副本客户端本地 / 随机，第 2 个副本同机架不同节点，第 3 个副本不同机架
- 保证**机架级故障不丢数据**

## 六、元数据

- 内存数据结构：目录树 + 文件 → 块列表 + 块 → DN 列表
- **fsimage**:元数据快照
- **edits**:增量编辑日志
- NN 启动时 = fsimage + edits 回放
- NameNode 内存 ≈ 文件数 × ~150~300 字节
- **海量小文件 → NN 内存爆炸**，是 HDFS 经典坑

## 七、HDFS Federation

- 单 NN 内存有限 → Federation 拆分命名空间
- 多个 NN 各自管一部分目录树，共享 DN 池
- 客户端挂载表路由到对应 NN
- 缓解元数据瓶颈，但**管理复杂度上升**

## 八、关键特性

### 1. 副本机制

- 默认 3 副本，可按文件 / 目录设置
- 副本损坏 / DN 失效 → NN 自动调度新副本
- 副本数 ≠ 3 时需谨慎（< 2 丢数据风险高，> 3 浪费空间）

### 2. 块报告与心跳

- DN 每 3 秒发心跳
- DN 每 6 小时发一次块报告（block report），列出自己所有块
- NN 据此重建块映射

### 3. 安全模式 (Safe Mode)

- NN 启动时进入安全模式，**只读不写**
- 等待足够多 DN 上报块后退出
- 集群启动时不可写入，要等几分钟

### 4. 快照 (Snapshot)

- 元数据快照，可用于恢复
- 块级快照（如 Ozone / HDFS-1604）更高效

### 5. 配额 (Quota)

- 命名空间配额 (ns quota)：文件数限制
- 存储空间配额 (ss quota)：字节数限制

## 九、典型工具与操作

```bash
# 常用 CLI
hdfs dfs -ls /path
hdfs dfs -put localfile /dst
hdfs dfs -get /hdfsfile local
hdfs dfs -rm /hdfsfile
hdfs dfs -du -h /path

# 管理员命令
hdfs dfsadmin -report
hdfs dfsadmin -safemode get/set
hdfs balancer -threshold 10
hdfs namenode -format       # 仅首次
hdfs namenode -fsck /       # 健康检查

# 查看块位置
hdfs fsck /path -files -blocks -locations
```

## 十、容量与扩容

- 加 DataNode → 自动加入集群
- 通过 balancer 跨节点均衡
- 扩容对客户端透明
- 受限于 NameNode 内存：~100M 文件 / 集群

## 十一、性能与调优

- **块大小**：128MB / 256MB，更大 → 减少 NN 内存压力、减少寻址
- **副本数**：影响读写
- **短回路 (Short-Circuit Read)**:客户端与 DN 同节点时绕过 RPC 直接读本地文件
- **零拷贝 (Zero-Copy)**:sendfile / splice
- **Codec**:压缩（Snappy / LZO / Zstd）
- **异构存储**:[ARCHIVE / DISK / SSD / RAM_DISK] 分层
- **Balancer**:避免数据倾斜

## 十二、监控与告警

- 关键指标：NN 堆内存、JVM GC、心跳丢失、块缺失、副本不足、安全模式、DN 磁盘使用率
- 工具：Cloudera Manager / Ambari / Apache Bigtop / 自建 Prometheus jmx_exporter
- 告警：DN 离线、磁盘满、副本不足、NN 切换、edits 堆积

## 十三、典型使用场景

| 场景 | 适用度 |
| --- | --- |
| 大数据离线计算 (Spark / Hive / MapReduce) | ⭐⭐⭐⭐⭐ |
| 海量日志归档 | ⭐⭐⭐⭐ |
| 冷数据 / 数据湖 (与 Iceberg / Hudi 结合) | ⭐⭐⭐⭐ |
| 视频 / 图片等大文件存储 | ⭐⭐⭐⭐ |
| 训练数据存储 (HDFS + TFRecord / Parquet) | ⭐⭐⭐⭐ |
| 海量小文件 | ⭐ 不适合 |
| 实时低延迟读取 | ⭐ 不适合 (延迟数十~百毫秒) |
| 事务 / 强一致 (ACID) | ⭐ 不适合 (用 HBase / Iceberg) |

## 十四、HDFS vs 其他

| 维度 | HDFS | CephFS | MinIO (S3) | JuiceFS |
| --- | --- | --- | --- | --- |
| 模型 | 写一次读多次 | POSIX | 对象 | POSIX over 对象 |
| 延迟 | 几十~百毫秒 | 毫秒级 | 毫秒级 | 取决于元数据 |
| 小文件 | 差 | 一般 | 一般 | 优 |
| 元数据 | NameNode 中心 | MDS 中心 | 无中心 | 中心元数据 (可拆分) |
| 大数据 | 优 | 中 | 中 | 中 |
| 生态 | Hadoop 绑定 | 通用 | 通用 + AI | AI / 通用 |

> **新项目首选对象存储 + 湖仓格式 (Iceberg / Hudi)**,传统 Hadoop 栈继续用 HDFS。
