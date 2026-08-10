# JuiceFS

云原生时代诞生的**高性能 POSIX 分布式文件系统**，**元数据与数据分离**架构——元数据存独立数据库（Redis / TiKV 等），数据存对象存储（S3 / OSS / MinIO 等）。把"云上 S3"变成"高性能共享文件"。

## 一、定位与特性

- **元数据 / 数据分离**:元数据小而热，数据大而冷
- **POSIX 兼容**:FUSE 挂载，Hadoop SDK，CSI
- **强一致**:基于元数据库的强一致
- **多云友好**:底层数据用对象存储，**容量近乎无限**
- **云原生**:CSI、Operator、与 K8s 深度集成
- **小文件优化**:Chunk 切小，元数据紧凑
- **HDFS 替代**:很多大数据场景下可平替

## 二、核心架构

```text
┌──────────────────────────────────────┐
│           Client (FUSE / SDK)        │ ← 应用进程内
├──────────────────────────────────────┤
│         JuiceFS Meta Engine          │ ← 元数据 API
├──────────────┬───────────────────────┤
│   元数据库    │      对象存储          │
│  Redis /     │  S3 / OSS / MinIO    │
│  TiKV /      │  Ceph RGW / COS / ... │
│  MySQL / ... │                       │
└──────────────┴───────────────────────┘
```

- **元数据**:文件树、目录、权限、块到 Chunk 的映射（紧凑、高效）
- **数据**:Chunk 块存到对象存储
- **客户端**:把 FUSE 调用转为元数据 + 数据 IO

## 三、核心概念

| 概念 | 含义 |
| --- | --- |
| **Volume** | JuiceFS 实例，挂载到本地路径 |
| **Chunk** | 大文件切分块（默认 64MB），存到对象存储 |
| **Slice** | Chunk 内的写入块，存到对象存储 |
| **Meta** | 元数据库，记录文件 → Chunk → Object 映射 |
| **FUSE** | 用户态挂载 |
| **CSI** | K8s 容器存储接口 |

## 四、读写路径

### 1. 写入

```text
Client (FUSE)
   1. 元数据库：创建/更新文件元数据
   2. 数据：写入到一个新的 Slice 对象
   3. 异步：合并、压缩、上传到对象存储
   4. 元数据库：记录 Slice 位置
```

### 2. 读取

```text
Client
   1. 元数据库：查询文件 → Chunk → Slice 列表
   2. 对象存储：并发拉取 Slice
   3. 拼装返回
```

## 五、元数据库选型

| 元数据库 | 适用 | 性能 | 备注 |
| --- | --- | --- | --- |
| **Redis** | 中小规模 / 强一致 | 高 | 内存型，容量受限 |
| **TiKV** | 中大规模 / 分布式 | 高 | 分布式 KV，水平扩展 |
| **MySQL / Postgres** | 已有 DB 资源 | 中 | 强一致，可运维 |
| **FoundationDB** | 大规模 | 高 | 开源 / 商用 |
| **SQLite** | 单机测试 | - | 仅测试 |

> 元数据是 JuiceFS 的**性能核心**,元数据库选错会卡死整个集群。

## 六、对象存储后端

支持几乎所有 S3 兼容对象存储：

- AWS S3、阿里云 OSS、腾讯云 COS、华为云 OBS
- MinIO、Ceph RGW、SeaweedFS
- 自建 S3 兼容服务
- HDFS（部分版本）

> **数据存对象存储,容量近乎无限,成本极低**——这是 JuiceFS 的核心优势。

## 七、核心特性

### 1. 强一致

- 元数据事务保证
- 写后读一致
- 多客户端并发写有锁保护

### 2. 压缩与去重

- 写入时按对象压缩（lz4 / zstd）
- 同 Chunk 内多文件可能共享
- 节省对象存储费用

### 3. 配额与权限

- 支持 POSIX 权限
- 桶级别 / 目录级配额
- 加密（传输 + 静态）

### 4. 跨区域 / 跨云

- 元数据可跨区域同步
- 数据天然跨区域（取决于后端对象存储）
- 适合多云、灾备

### 5. Hadoop 兼容

- 提供 Hadoop FileSystem SDK
- Spark / Hive / Flink 直接读写
- 替代 HDFS，**底层用对象存储**

## 八、Kubernetes 部署

- **CSI Driver**:动态创建 PV / PVC
- **Operator**:简化运维
- 用法：
  ```yaml
  apiVersion: v1
  kind: PersistentVolumeClaim
  metadata:
    name: myapp-data
  spec:
    storageClassName: juicefs
    accessModes: [ReadWriteMany]
    resources:
      requests:
        storage: 100Gi
  ```
- **ReadWriteMany (RWX)**:多 Pod 同时挂载,JuiceFS 默认支持
- 比 CephFS / NFS 更适合 K8s 多 Pod 共享

## 九、典型使用场景

| 场景 | 适用度 |
| --- | --- |
| K8s 多 Pod 共享存储 (RWX) | ⭐⭐⭐⭐⭐ |
| AI 训练数据 (替代 HDFS) | ⭐⭐⭐⭐⭐ |
| 大数据计算 (Spark / Hive 替代 HDFS) | ⭐⭐⭐⭐ |
| 模型 / checkpoint 共享 | ⭐⭐⭐⭐ |
| 日志、监控后端 | ⭐⭐⭐ |
| 备份 / 归档 | ⭐⭐⭐ |
| 高频随机写 (数据库) | ⭐ 不适合 |
| 极致低延迟 | ⭐ 不适合 (依赖对象存储延迟) |

## 十、运维

### 1. 元数据库性能

- Redis：监控内存、QPS、慢命令
- TiKV：监控 region 分布、读写延迟、磁盘
- 元数据库挂了 → JuiceFS 整体不可用

### 2. 客户端

- FUSE 内核 / libfuse 选型
- 缓存：`--cache-dir`、`--cache-size`
- 预读：`--prefetch`
- 写缓冲：`--writeback`

### 3. 监控指标

- 元数据库 QPS / 延迟
- 对象存储请求 / 带宽
- 客户端挂载点
- FUSE IO 延迟

## 十一、JuiceFS vs HDFS / CephFS

| 维度 | JuiceFS | HDFS | CephFS |
| --- | --- | --- | --- |
| 元数据 | 外置元数据库 | NameNode 中心 | MDS 中心 |
| 数据存储 | 对象存储 | 节点本地 | OSD |
| 容量 | 无限 (对象) | 受限 | 受限 |
| 多云 | 优 | 弱 | 弱 |
| K8s 集成 | 优 | 一般 | 一般 (Rook) |
| 大数据兼容 | 优 (Hadoop SDK) | 优 | 一般 |
| 强一致 | 优 | 优 | 优 |
| 性能 | 高 (取决于对象) | 极高 | 高 |
| 成本 | 低 (对象存储) | 中 | 高 |

> **云原生 + 多云 + 大数据场景,JuiceFS 是当前最优解之一**;HDFS 适合超大规模离线集群。

## 十二、性能调优

- **Chunk 大小**:默认 64MB，大文件 → 大 Chunk；小文件 → 小 Chunk
- **写缓冲**:`--writeback` 异步写对象，提升写吞吐
- **元数据缓存**:`--attr-cache`、`--entry-cache`
- **预读**:`--prefetch` 提前读下一块
- **本地缓存**:`--cache-dir` 用本地 SSD 缓存热点
- **并发**:`--max-uploads`、`--max-deletes`

## 十三、安全

- 传输加密 (TLS)
- 静态加密（对象存储侧 SSE）
- POSIX 权限、ACL
- 客户端认证：token、RAM role
- 审计：可对接对象存储访问日志
