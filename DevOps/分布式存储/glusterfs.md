# GlusterFS

老牌的用户态**分布式文件系统**，去中心化、无元数据服务、模块化设计，曾经是 Linux 基金会旗下明星项目。优势是**简单、灵活、无单点**，缺点是**扩展性、性能、运维体验**在云原生时代被新方案反超。

## 一、定位与特性

- **用户态实现**：内核模块 fuse + glusterfsd 进程
- **无元数据服务 (Elastic Hash)**：通过 DHT 直接定位文件
- **模块化卷类型**：复制、条带、纠删码、地理复制等
- **POSIX 兼容**：通过 FUSE / NFS / SMB 暴露
- **横向扩展**：加 brick 节点即可
- **无中心**：理论上没有单点故障

## 二、核心概念

| 概念 | 含义 |
| --- | --- |
| **Brick** | 节点上一个目录（导出目录），最基础的存储单元 |
| **Volume** | 跨多个 Brick 的逻辑卷，对外提供挂载点 |
| **Translator** | 内部功能模块（DAH、AFR、DHT、EC 等），可堆叠 |
| **DHT (Distributed Hash Table)** | 弹性哈希分布文件，替代中心元数据 |
| **FUSE** | 用户态挂载到文件系统 |
| **Glusterd** | 集群管理进程，每节点一个 |

## 三、卷类型

| 类型 | 用途 | 空间效率 | 性能 | 容错 |
| --- | --- | --- | --- | --- |
| **Distributed**（默认） | 简单聚合容量 | 100% | 高 | 0（无副本） |
| **Replicated** | 高可用 | 1/N | 写延迟增加 | N-1 副本 |
| **Striped** | 大文件顺序读写 | 100% | 高吞吐 | 0（条带化） |
| **Distributed-Replicated** | 容量 + 副本 | 1/N | 中 | N-1 副本 |
| **Dispersed (Erasure Code)** | 节省容量 | k/(k+m) | 中（写慢） | 任意 ≤m 块可恢复 |
| **Distributed-Dispersed** | 容量 + EC | k/(k+m) | 中 | 任意 ≤m 块可恢复 |
| **Geo-Replication** | 跨站点复制 | 同源 | 中 | 站点级 |

```bash
# 创建复制卷
gluster volume create gv0 replica 3 \
  node1:/data/brick1 node2:/data/brick1 node3:/data/brick1

# 创建纠删码卷（k=4 m=2）
gluster volume create gv1 disperse 6 redundancy 2 \
  node1:/data/b1 node2:/data/b1 node3:/data/b1 \
  node4:/data/b1 node5:/data/b1 node6:/data/b1

# 启动
gluster volume start gv0
gluster volume info
```

## 四、数据分布：DHT (Distributed Hash Table)

- 文件名经过哈希 → 落到哈希环上某位置 → 找到负责该区间的 Brick
- 无 NameNode / MDS，**真正的去中心化**
- 扩容时 hash 范围重新划分，部分文件需要迁移
- 哈希分布相对均匀，但**目录级热点**仍可能存在

```text
文件名 hash → 取模 → 落在某 Brick
   abc.txt (hash=12345) → node2:/data/brick1
```

## 五、复制与自愈 (AFR / Self-Heal)

- Replicated 卷用 **AFR (Automatic File Replication)** 维护多副本
- 节点 / 磁盘故障时，**后台自动修复**
- 自愈过程：文件级 → 块级 → 索引级，逐步加速
- 修复中**可能阻塞前端**，需要规划

## 六、客户端挂载

### 1. FUSE (Native)

```bash
mount -t glusterfs node1:/gv0 /mnt/gv0
```

- 默认方式，POSIX 语义完整
- 性能受 FUSE 开销影响

### 2. NFS

- 兼容老 NFS 客户端
- Glusterd 内置 NFS 协议（`glusterfs-nfs`）
- 性能与稳定性比 FUSE 略差

### 3. SMB

- Windows / macOS 客户端
- 通过 `glusterfs-smb` 提供

### 4. libgfapi

- 应用程序直连（绕过 FUSE）
- QEMU / NFS-Ganesha / 自定义应用

## 七、扩容与重平衡

- 加 Brick：`gluster volume add-brick gv0 replica 4 node4:/data/brick1`
- **手动触发重平衡**：`gluster volume rebalance gv0 start`
- 旧文件**不会自动迁移**，需要 rebalance
- 大量数据 rebalance 期间**前端 IO 受影响**

## 八、典型使用场景

- 中小规模 NAS 替代
- 老 HPC / 媒资 / 渲染农场
- 容器 / K8s 中的简易共享存储
- 已经运行多年的存量系统

> **新项目首选 JuiceFS / Rook-Ceph / MinIO**,GlusterFS 主要服务存量场景。

## 九、运维要点

- **时间同步**:Glusterd 严重依赖 NTP，节点时间差会导致卷异常
- **网络**:存储网络最好独立，万兆起
- **brick 路径**:挂载点必须一致，建议专用盘
- **健康检查**:`gluster volume status`、`heal info`
- **后台扫描**:`gluster volume bitrot` 检测静默错误
- **监控**:Prometheus glusterfs_exporter、节点磁盘、卷状态

## 十、调优

- **网络 MTU**:9000 大帧
- **性能选项**:`performance.cache-size`、`performance.io-thread`
- **内存**:每个 translator 占用，影响并发
- **目录分裂**:超 100 万文件目录建议用 tier 2 卷
- **客户端**:用原生 FUSE 客户端而非 NFS

## 十一、GlusterFS vs 其他

| 维度 | GlusterFS | CephFS | HDFS | JuiceFS |
| --- | --- | --- | --- | --- |
| 元数据 | 无中心 (DHT) | MDS 中心 | NameNode 中心 | 元数据库中心 |
| 扩展性 | 中 | 优 | 优 (大文件) | 优 |
| 大文件 | 优 | 优 | 极优 | 优 |
| 小文件 | 中 | 中 | 差 | 优 |
| 运维 | 中 | 高 | 中 | 中 |
| 云原生 | 一般 | 一般 (Rook) | 一般 | 优 |
| 活跃度 | 下降 | 活跃 | 活跃 | 活跃 |

> **GlusterFS 仍在维护,但新项目少,生态逐渐被 JuiceFS / Ceph / MinIO 取代**。
