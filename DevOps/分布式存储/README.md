# 分布式存储

按存储形态与代表系统整理分布式存储的原理、选型与落地。

## 分类与索引

| 分类 | 代表系统 |
| --- | --- |
| **统一存储 (块/文件/对象)** | [Ceph](ceph.md)、[MinIO](minio.md) |
| **分布式文件系统** | [HDFS](hdfs.md)、[GlusterFS](glusterfs.md)、[SeaweedFS](seaweedfs.md)、[JuiceFS](juicefs.md) |
| **K8s 原生 / 存储编排** | [Rook](rook.md) (Ceph on K8s)、[OpenEBS](openebs.md) |
| **云厂商托管** | [AWS / 阿里云 / 腾讯云 / Azure / GCP](cloud-managed.md) |

## 选型速查

| 场景 | 建议 |
| --- | --- |
| 块、文件、对象一站式，自建 IDC 规模集群 | [Ceph](ceph.md) + [Rook](rook.md) |
| 纯对象存储、S3 兼容、容量大、单机到上百节点 | [MinIO](minio.md) |
| 大数据离线计算、批处理、流式历史数据 | [HDFS](hdfs.md) |
| 轻量文件存储、POSIX、海量小文件 | [SeaweedFS](seaweedfs.md) |
| 跨云、对象存储做后端、POSIX 语义、元数据高性能 | [JuiceFS](juicefs.md) |
| K8s 上的有状态应用，需要 PVC 动态供给 | [Rook-Ceph](rook.md) 或 [OpenEBS](openebs.md) |
| 不想运维、已在某朵云上 | [云厂商托管](cloud-managed.md) |
| 老 HPC / 渲染 / 媒资，简单聚合本地盘 | [GlusterFS](glusterfs.md) |

## 核心概念对比

| 维度 | Ceph | MinIO | HDFS | SeaweedFS | JuiceFS | GlusterFS |
| --- | --- | --- | --- | --- | --- | --- |
| **存储形态** | 块/文件/对象 | 对象 | 文件 (HDFS) | 文件/对象 | 文件 (POSIX) | 文件 (POSIX) |
| **协议** | RBD、CephFS、S3/Swift | S3 | HDFS RPC | FUSE / S3 / HTTP | FUSE / S3 / HDFS | FUSE / NFS / SMB |
| **数据冗余** | 多副本 / 纠删码 | 纠删码 | 3 副本 | 多副本 | 后端对象 + 元数据 | 多副本 / 纠删码 |
| **一致性** | 强一致 (CRUSH + PG) | 强一致 (写入 quorum) | 强一致 (NameNode) | 强一致 | 强一致 (元数据) | 最终一致 |
| **元数据** | OSD 内嵌 / CephFS MDS | 无中心 (对象) | 中心 NameNode | 中心 Master | 中心元数据 (Redis/TiKV) | 弹性哈希 |
| **扩容** | 加 OSD，自动重平衡 | 加节点，自动 rehash | 加 DataNode | 加 Volume Server | 加 chunk server | 加 brick |
| **典型规模** | 数千 OSD / EB 级 | 数百节点 / PB 级 | 万节点 / EB 级 | 海量 Volume | 云上任意 | 中小规模 |
| **小文件性能** | 一般 | 一般 | 差 (NameNode 压力) | 优 (Chunk 切小) | 优 | 一般 |
| **大数据场景** | 通用 | 对象语义 | 优 | 中 | 中 | 弱 |
| **运维复杂度** | 高 | 中 | 中 | 低 | 中 | 中 |
| **K8s 友好** | 一般 (建议 Rook) | 一般 | 一般 | 中 | 优 | 一般 |
| **主语言栈** | C++ | Go | Java | Go | Go | C |

## 核心机制

- **数据分布**：Ceph 用 CRUSH 算法（一致性哈希变体），无中心调度，按权重均匀分布；HDFS 由 NameNode 维护块到节点的映射；GlusterFS 用 DHT 弹性哈希；SeaweedFS 用 Volume ID 路由
- **冗余策略**：副本（3 副本最常见，简单可靠）和纠删码（Reed-Solomon 为主，存储效率高但恢复成本高）的取舍决定成本与可靠性
- **一致性协议**：Ceph 用 Paxos 变种（MON 选举）+ PG log；HDFS 用 JournalNode 仲裁；元数据是否中心化决定了扩展上限
- **写入路径**：客户端先写主副本/主 OSD，再异步复制到副本；纠删码系统会先计算分片再分发
- **故障恢复**：副本方式下自动补副本；纠删码需要从其他分片恢复，CPU 和网络开销大
- **元数据热点**：HDFS NameNode、GlusterFS 哈希冲突、CephFS MDS 都是常见的元数据瓶颈

## 落地要点

- **容量规划**：副本 / 副本数 / 纠删码比例决定实际可用容量，对外容量 ≈ 物理容量 × 副本系数
- **节点规划**：JBOD + 单盘 OSD 比 RAID 更适合分布式存储；监控盘故障率、慢盘、SMART
- **网络规划**：存储网络最好与业务网络分离，10GbE 起；副本写入会放大流量（写 1 份 = 网卡 2~3 份流量）
- **故障域**：按机架 / 机柜 / 副本域划分，CRUSH rule / 机架感知避免单机架故障
- **监控指标**：容量、IOPS、延迟、PG 状态、慢请求、副本数、降级状态、恢复进度
- **备份与恢复**：分布式存储本身是高可用，但**不替代备份**——勒索病毒、误删、逻辑错误仍可能毁数据
- **硬件生命周期**：存储系统寿命长于服务器，要规划磁盘淘汰、节点换代、跨代兼容
