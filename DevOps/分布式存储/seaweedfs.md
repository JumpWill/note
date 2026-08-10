# SeaweedFS

面向**海量小文件**优化的轻量级分布式对象 / 文件存储，Go 编写，Facebook Haystack 思路，单二进制部署，**特别适合图片、视频、备份、容器镜像、日志**等场景。

## 一、定位与特性

- **Haystack 思想**:把多个小文件打包成一个大 Needle 对象
- **极致小文件性能**:亿级文件也只占元数据几 GB
- **轻量**:Go 单二进制，资源占用低
- **多协议**:FUSE (POSIX)、S3 API、Hadoop FileSystem API、HTTP
- **去中心**:无强元数据服务，Master 极轻
- **自动压缩与去重**(可选)
- **Filer**:可选的元数据服务（实现目录树、POSIX）

## 二、核心组件

| 组件 | 角色 |
| --- | --- |
| **Master** | 集群大脑，分配 Volume ID → Volume Server，**轻量**（不存文件元数据） |
| **Volume Server** | 真正存 Needle 块 |
| **Filer** | 可选，提供目录 / 文件名 / 元数据 |
| **FUSE Mount** | 客户端挂载，POSIX 语义 |
| **S3 Gateway** | 兼容 S3 API |
| **Hadoop FS** | 兼容 HDFS API |
| **Mount** | FUSE 客户端 |

## 三、核心概念

| 概念 | 含义 |
| --- | --- |
| **Needle** | 海量小文件的存储单位，包含文件数据 + 元数据 |
| **Volume** | 一组 Needle 的容器，默认 32GB（可调） |
| **Collection** | 一组 Volume 的逻辑分组，隔离不同业务 |
| **Bucket** | Filer 下的目录概念 |
| **TTL** | 过期时间，自动清理 |

## 四、读写路径

### 1. 写入

```text
Client → Master：申请 File ID
Master → Client：返回 (Volume ID, Needle ID, Cookie)
Client → Volume Server：直传 Needle（按 File ID 路由）
   Volume Server 把 Needle 追加到 Volume 文件末尾
   写成功后返回
```

### 2. 读取

```text
Client → Volume Server：通过 (Volume ID, Needle ID) 直接定位
Volume Server 在 Volume 中二分查找 Needle
返回数据
```

- **无 NameNode 式元数据服务**，Master 只负责 Volume 分配
- 客户端直连 Volume Server，**元数据路径极短**

## 五、Filer

- 可选组件，提供**目录树 + 文件名 + 权限**
- 元数据可存：LevelDB / BoltDB / MySQL / Postgres / Redis / Cassandra / TiKV
- 没有 Filer：SeaweedFS 退化为**纯对象存储**，按 ID 访问
- 有 Filer：可挂载为 POSIX 文件系统

## 六、典型架构

```text
         ┌────────────┐
         │   Master   │ ← 集群协调
         └─────┬──────┘
               │ 分配 Volume
   ┌───────────┼───────────┐
   ▼           ▼           ▼
Volume Svr  Volume Svr  Volume Svr
(10 盘)     (10 盘)     (10 盘)
   ▲
   │ FUSE / S3 / HDFS API
   │
Clients
```

- Master 高可用：多 Master 节点 + Raft
- Volume Server 可线性扩展
- 单 Volume 写满自动滚动到新 Volume

## 七、核心特性

### 1. 自动压缩

- Needle 写入时按算法压缩（gzip / snappy 等）
- 节省磁盘，CPU 换 IO

### 2. 自动 TTL 清理

- 过期 Needle 自动标记 + 清理
- 适合日志、临时文件

### 3. EC (Erasure Coding)

- 类似 MinIO，Volume 数据 EC 编码
- k+m 策略，存储效率高

### 4. 跨数据中心同步

- Filer → Filer 异步复制
- Volume → Volume 远程同步
- 异地容灾

### 5. 数据局部性

- Volume 与数据生成位置就近
- 上传后默认读就近节点

## 八、典型使用场景

| 场景 | 适用度 |
| --- | --- |
| 海量小文件 (图片、头像、附件) | ⭐⭐⭐⭐⭐ |
| Docker / OCI 镜像存储 | ⭐⭐⭐⭐⭐ |
| 视频、媒资、监控录像 | ⭐⭐⭐⭐ |
| 日志、时序数据归档 | ⭐⭐⭐⭐ |
| S3 替代 (中小规模) | ⭐⭐⭐ |
| K8s 简易共享存储 | ⭐⭐⭐ |
| 训练数据存储 | ⭐⭐⭐ |
| 大数据离线计算 | ⭐ 不适合 |

## 九、客户端

### 1. FUSE Mount

```bash
weed mount -filer=localhost:8888 -dir=/mnt/seaweed
```

### 2. S3 API

```bash
# 启动 S3 gateway
weed s3
```

### 3. HDFS API

- 兼容 Hadoop FileSystem API
- Spark / Hive 直接读写

### 4. 各种语言 SDK

- Go / Java / Python / Rust / Node 等

## 十、运维

- **单 Master**:开发环境够用，**生产建议 Raft 多 Master**
- **监控**:Master metrics、Volume Server 状态、磁盘使用、读写 QPS
- **扩容**:加 Volume Server → Master 自动感知
- **数据平衡**:Master 自动调度

## 十一、调优

- **Volume 大小**:默认 32GB，太大 → 单 Volume 修复慢；太小 → Volume 数量爆炸
- **副本策略**:replication 参数，副本数 ≠ 机器数时用 placement
- **Collection 隔离**:不同业务不同 Collection
- **Filer 选型**:小规模用 BoltDB，大规模用 TiKV / Cassandra

## 十二、SeaweedFS vs 其他

| 维度 | SeaweedFS | MinIO | Ceph | HDFS |
| --- | --- | --- | --- | --- |
| 小文件 | 极优 | 一般 | 一般 | 差 |
| 大文件 | 优 | 优 | 优 | 极优 |
| POSIX | FUSE | 否 (s3fs 性能差) | CephFS | 是 |
| 元数据 | Master 轻 + Filer | 无中心 | MDS / OSD | NameNode 中心 |
| 复杂度 | 低 | 低 | 高 | 中 |
| 资源占用 | 极低 | 低 | 高 | 中 |
| 协议 | FUSE / S3 / HDFS | S3 | 块 / 文件 / 对象 | HDFS |
| 适用规模 | TB ~ 几十 PB | TB ~ 几百 PB | PB ~ EB | PB ~ EB |

> **海量小文件场景下,SeaweedFS 比 MinIO / HDFS / Ceph 都有显著优势**;是镜像仓库、CDN 源站、附件存储的优选。
