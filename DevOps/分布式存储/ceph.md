# Ceph

开源的**统一分布式存储**，同时提供**块 (RBD)、文件 (CephFS)、对象 (RGW/S3)** 三种接口，规模化能力强（EB 级），是私有云与大规模存储的事实标准之一。复杂度高，运维门槛高。

## 一、定位与特性

- **统一存储**：一套集群同时服务块、文件、对象
- **无中心数据分布**：CRUSH 算法，客户端直接计算 OSD 位置
- **强一致**：副本写多数派后才返回成功
- **自愈**：故障 OSD 自动恢复、CRUSH 重新平衡
- **多副本 / 纠删码**：按 Pool 配置灵活选择
- **成熟生态**：与 OpenStack、K8s（Rook）、虚拟化深度集成

## 二、核心组件

| 组件 | 角色 |
| --- | --- |
| **MON (Monitor)** | 集群地图 (Cluster Map) 维护与一致性仲裁 (Paxos)，保存 OSD / PG / CRUSH 等元数据 |
| **OSD (Object Storage Daemon)** | 真正存数据、复制、恢复、回填，每个磁盘一个 OSD 进程 |
| **MDS (Metadata Server)** | CephFS 元数据服务，无 CephFS 不必部署 |
| **RGW (RADOS Gateway)** | 对象存储网关，对外提供 S3 / Swift 兼容接口 |
| **Manager (ceph-mgr)** | 集群状态、监控、PG 统计、仪表盘 |
| **RBD (RADOS Block Device)** | 内核模块 / librbd，提供块设备 |
| **CephFS** | POSIX 文件系统，基于 FUSE / 内核客户端 |

## 三、数据分布与读写路径

### 1. CRUSH 算法

- 不是传统一致性哈希，而是**伪随机映射**：把 object → PG → OSD
- 规则可以基于**机架、机房、域**做副本分布
- 客户端拿到 Cluster Map 后**本地计算** OSD 位置，无需中心调度
- 单 OSD 故障时**只影响其承载的 PG**，影响面可控

```text
object (e.g. 4MB) → hash → PG ID → CRUSH → [OSD.1, OSD.5, OSD.9] (副本)
```

### 2. PG (Placement Group)

- PG 是 object 的逻辑容器，**对象先映射到 PG，再映射到 OSD**
- 解决"百万对象直接映射 OSD"的管理复杂度
- PG 数量需要按集群规模调优，太多 → CPU 浪费，太少 → 分布不均

### 3. 写入路径

```text
Client → librados
   1. 计算 PG → OSD 列表（按 CRUSH rule）
   2. 向主 OSD (Acting Set[0]) 发起写
   3. 主 OSD 复制到 Replica OSDs
   4. 多数派 (size/2) 写入成功 → 主 OSD 提交 → 返回客户端
   5. 异步将 PGLog / OSDMap 同步给副本
```

- 写入是**强一致**的，但**写入延迟**取决于最慢的副本
- 副本数 3 + size 3 = 写 3 份、读最近副本

### 4. 读取路径

- 默认从主 OSD 读（强一致）
- 可配置 `read_from_replica` 分散读压力，但有读到旧数据的风险

## 四、存储后端 (BlueStore)

- 自 Luminous 起默认后端，取代 FileStore
- 直接管理裸盘，**不再经过文件系统**
- RocksDB 保存元数据，WAL/DB 在独立分区或 NVMe
- 数据直接写块设备，减少 double write

```text
[ Block Device ]
   ├── DB (RocksDB, 建议 NVMe/SSD)
   ├── WAL (Write-Ahead Log)
   └── Data (实际对象数据, HDD/SSD)
```

> DB 和 WAL 强烈建议用 SSD，单盘 OSD 用 NVMe 最佳；HDD 上的 OSD 性能差且恢复慢。

## 五、CRUSH Rule 与故障域

```text
rule replicated_ruleset {
    ruleset 0
    type replicated
    min_size 1
    max_size 10
    step take default
    step chooseleaf firstn 0 type rack   ← 跨机架
    step emit
}
```

- `type rack` 让副本分布在不同机架
- `type host` 单机多盘副本
- `type datacenter` 跨机房副本（异地容灾用）
- 同一故障域内**绝不**放多副本，否则机架掉电丢数据

## 六、纠删码 (Erasure Coding)

- 用 Reed-Solomon 等算法，存储效率高（如 k=4 m=2 → 1.5 倍空间）
- 适合**冷数据、备份、归档**
- 缺点：写入放大、恢复耗 CPU 和网络、PG 状态机复杂

```text
k=4 数据分片, m=2 校验分片
   存 4+2=6 个 OSD
   任意 ≤2 个 OSD 损坏可恢复
   空间利用率 = 4/6 = 66.7% （vs 3 副本 33%）
```

> 纠删码 + 故障期间**降级读**性能会显著下降，是常见性能抖动来源。

## 七、CephFS

- POSIX 文件系统，依赖 MDS 管理目录、文件名、权限
- 多 MDS 支持水平扩展元数据
- 客户端通过 FUSE / 内核模块挂载
- 注意：MDS 本身是**中心化**组件，故障期间元数据 IO 会卡

## 八、RGW (对象存储)

- 基于 librados，提供 S3 / Swift 兼容 API
- 适合图片、视频、备份、日志归档
- 多租户、Quota、Lifecycle、Replication、跨区同步
- 可与 nginx / haproxy 做无状态水平扩展

## 九、扩容与重平衡

- 加 OSD → CRUSH 自动重平衡
- 平衡过程中**有写放大和读慢**，建议分批进行
- 控制 `osd_recovery_max_active` / `osd_scrub_max_interval` 限速
- 观察 `recovery` / `backfill` 进度

## 十、运维与监控

- **ceph -s** / **ceph -w** / **ceph health detail**
- 关键指标：
  - `pg state`（active+clean 是健康）
  - `pg deep-scrub / repair`
  - OSD latency、apply / commit latency
  - recovery / backfill 速率
  - 容量使用率（nearfull 85%、full 90%、backfillfull 75%）
- 仪表盘：ceph-dash / mgr dashboard / Prometheus ceph_exporter

## 十一、典型部署架构

```text
                ┌──────────────┐
                │  MON × 3/5   │ ← 仲裁，奇数台
                └──────────────┘
   ┌──────────┐  ┌──────────┐  ┌──────────┐
   │ OSD Node │  │ OSD Node │  │ OSD Node │ ← 每节点多盘 OSD
   │ 12 × HDD │  │ 12 × HDD │  │ 12 × HDD │
   │ 1 × SSD  │  │ 1 × SSD  │  │ 1 × SSD  │ ← DB/WAL 分区
   └──────────┘  └──────────┘  └──────────┘
   ┌──────────┐  ┌──────────┐
   │  RGW × N │  │ MDS × 2  │ ← 按需
   └──────────┘  └──────────┘
```

- 至少 3 MON，OSD 节点推荐同构
- 网络：存储网络 10GbE+ 与业务网络分离
- 操作系统：CentOS Stream / Ubuntu LTS，内核版本与 Ceph 版本匹配

## 十二、调优要点

- **PG 数**：`pg_num = (OSDs × 100) / replica_count` 起，再按池微调
- **OSD 内存**：每 OSD ~4GB，PG 越多越耗内存
- **scrub**：定期 deep-scrub 发现副本不一致
- **网络 MTU**：9000 (Jumbo Frame) 减少开销
- **throttle**：写 / 读 / 恢复各自的并发与带宽上限
- **balance**：CRUSH weight 调整、冷热分层（Caching Pool）

## 十三、Ceph vs 其他

| 维度 | Ceph | MinIO | HDFS | GlusterFS |
| --- | --- | --- | --- | --- |
| 多协议 | 块+文件+对象 | 仅对象 | 仅 HDFS | 文件 |
| 元数据 | CephFS 有 MDS | 无中心 | NameNode | DHT |
| 扩展性 | EB | PB | EB | 中 |
| 运维难度 | 高 | 中 | 中 | 中 |
| 场景 | 通用 / 私有云 | 对象 / 云原生 | 大数据 | 老旧 POSIX |

> **Ceph 不是"装上就能用"**——要充分规划 PG、CRUSH rule、网络、硬件分层，否则后期坑很深。
