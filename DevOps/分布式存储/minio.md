# MinIO

高性能、S3 兼容的开源**对象存储**，Go 编写，单二进制部署简单，是云原生时代的事实标准对象存储之一。常作为私有云的 S3 替代品，也广泛用于 AI / 大数据 / 备份场景。

## 一、定位与特性

- **纯对象存储**：S3 v4 API 100% 兼容
- **纠删码存储**：默认 EC:4（4 数据分片 + 4 校验，存储效率 50%）
- **极简部署**：单个二进制，分布式也是同一份二进制
- **强一致**：读取立即看到最近写入（与 AWS S3 最终一致不同）
- **云原生友好**：支持 K8s Operator、AIStor、多云复制
- **生态丰富**：与 Spark / Presto / Trino / Kafka / Velero 等深度集成

## 二、部署模式

### 1. 单节点单盘

- 用于开发测试
- 单点，**不推荐生产**

### 2. 单节点多盘

- 单实例多块盘
- 适合边缘节点或小规模

### 3. 分布式 (推荐)

- 至少 4 节点（纠删码 EC:4 最低 4 节点）
- 推荐 4 / 8 / 16 节点同构
- 所有节点跑同一份 `minio server` 进程
- 节点间通过**路径风格访问**  (`http://node1/data node2/data node3/data node4/data`)

```bash
minio server \
  http://minio-{1...4}.example.com/data{1...4} \
  --console-address ":9001"
```

- 默认 API 端口 9000，Console 端口 9001

## 三、纠删码 (Erasure Coding)

- 把对象切成 N 个数据块 + M 个校验块
- 任意 ≤M 个块丢失仍可恢复
- MinIO 默认 `EC:4`（N=4 M=4），最低 4 节点
- 也支持 `EC:2`（N=2 M=2）、`EC:N` 自定义

| EC 配置 | 数据分片 | 校验分片 | 最少节点 | 空间效率 |
| --- | --- | --- | --- | --- |
| EC:2 | 2 | 2 | 4 | 50% |
| EC:4 (默认) | 4 | 4 | 4 | 50% |
| EC:8 | 8 | 8 | 16 | 50% |
| 副本 | 1 | 0 | - | 100% (无副本概念) |

> 与 3 副本 33% 相比，EC:4 同样是 50%，但能容忍 4 节点故障。MinIO 强制纠删码，**没有传统多副本**。

## 四、核心架构

```text
┌────────────────────────────────────────────┐
│              S3 API Layer                   │ ← 签名 / 路由
├────────────────────────────────────────────┤
│            Object Layer                     │ ← 切片 / 重组 / 校验
├────────────────────────────────────────────┤
│         Erasure Coding Layer                │ ← Reed-Solomon 编解码
├────────────────────────────────────────────┤
│       Storage Layer (per Node/Disk)         │ ← bitrot 检测 / 修复
├────────────────────────────────────────────┤
│          Local FS (XFS 推荐)                 │
└────────────────────────────────────────────┘
```

- **bitrot 检测**：每个对象有 HighwayHash 校验，读取时校验，发现损坏自动从其他分片修复
- **写入路径**：客户端 PUT → 计算 EC 分片 → 并行写到多节点 → 多数确认后返回
- **读取路径**：客户端 GET → 找最近的节点读 → 失败时从其他分片重建

## 五、桶 (Bucket) 与对象 (Object)

- **Bucket**：扁平的命名空间，**没有目录**
- 目录是用 `/` 分隔的 key 前缀模拟
- 元数据：用户自定义、对象大小、ETag、内容类型等
- 版本控制：开启后可保留历史版本
- 对象锁 (Object Lock)：WORM 模式，**防止被覆盖/删除**，合规归档

## 六、核心特性

### 1. S3 兼容性

- 支持 S3 v4 签名
- 大部分 S3 API 兼容（S3 Select、Multipart Upload、Presigned URL）
- 与 AWS SDK 工具链无缝迁移
- 也支持 KMS 加密、IAM Policy

### 2. 多租户

- 通过 Access Key / Secret Key 隔离
- 支持 STS 临时凭证、OIDC / LDAP 联合身份
- 桶级 / 前缀级 Policy 细粒度权限

### 3. 事件通知

- 监听对象创建 / 删除 / 访问
- 支持 Kafka、NATS、AMQP、Redis、MySQL、PostgreSQL、Elasticsearch
- 用于异步处理、CDN 预热、审计

### 4. 生命周期 (Lifecycle)

- 规则：按前缀 / 标签 / 时间
- 动作：删除、转移到远程 tier（warm/cold）
- 与版本控制结合可管理历史版本

### 5. 复制 (Replication)

- **桶复制**：跨集群 / 跨区域异步复制
- 支持 Active-Active 双向（需版本控制）
- 用于异地容灾、跨云数据分发

### 6. 加密

- **传输加密**：TLS
- **服务端加密**：SSE-S3 (MinIO 托管)、SSE-KMS (外部 KMS)、SSE-C (客户提供)
- 每个对象独立加密密钥，主密钥通过 KMS 管理

## 七、Kubernetes 部署

- **官方 Operator**：管理 MinIO 租户、状态、扩容
- 推荐用**专用存储类**的 PV 挂载给 MinIO（避免依赖本地磁盘）
- 单租户单集群适合中小规模
- 大规模建议**多租户**拆分（一个 K8s namespace 跑一个 MinIO 租户）
- CSI 驱动：通过 S3 给 K8s Pod 提供块 / 文件存储

## 八、客户端与生态

| 客户端 / 工具 | 用途 |
| --- | --- |
| `mc` (MinIO Client) | 类似 `aws s3` 的命令行 |
| `aws-cli` | 配置 endpoint 即可使用 |
| `s3cmd`、`rclone` | 通用 S3 工具 |
| 各种语言 SDK | AWS SDK、MinIO Go SDK |
| **Velero** | K8s 备份到 MinIO |
| **Spark / Hive / Trino** | 直接读 S3 |
| **Vector / Loki / Prometheus** | 远程写后端 |
| **DuckDB / ClickHouse** | 查询 S3 上的 Parquet |
| **AI 训练** | 训练数据存 S3，配合 S3FS / Mountpoint |

## 九、运维与监控

### 1. 健康检查

- `/minio/health/live` (存活)
- `/minio/health/ready` (就绪)
- 节点掉线后集群**自动降级**：从 EC 重建提供读，但写会受影响

### 2. 关键指标

- 在线节点数 / 离线节点数
- 总容量 / 已用 / 剩余
- 请求 QPS / 错误率 / 延迟 P95/P99
- 每个盘的使用率、IO、延迟
- 后台 heal / rebalance 进度

### 3. 监控工具

- 内置 Prometheus metrics（`/minio/v2/metrics/cluster`）
- Grafana 官方 dashboard
- 告警建议：节点离线、磁盘快满、heal 卡住、延迟飙升

## 十、容量与扩容

- 加节点 → 现有对象**不会自动重平衡**
- 启动时用 `--rebalance` 或事后手动 `mc admin rebalance` 触发
- 扩容易，**节点规格建议同构**，避免大节点数据稀疏
- EC 比例变更需要新建 bucket

## 十一、典型架构

### 1. 单数据中心

```text
4 节点 MinIO，每节点 4 × 4TB HDD
  EC:4 → 实际容量 ≈ 4 × 16TB × 50% = 32TB
  可容忍 4 节点故障 / 16 块盘故障
```

### 2. 跨数据中心异步复制

```text
DC1 (主) ─── site-replication ──→ DC2 (备)
  Put → 异步复制到 DC2 → 用户读 DC1 优先
  故障时 DNS / 负载均衡切到 DC2
```

### 3. 与 K8s 配合

```text
K8s Pods
   ↓ PVC (动态供给)
StorageClass → Rook-Ceph / OpenEBS
   ↓
S3 API
   ↓
MinIO 集群
   ↓
S3 作为 Velero / Loki / 训练数据 后端
```

## 十二、MinIO vs AWS S3

| 维度 | MinIO | AWS S3 |
| --- | --- | --- |
| 一致性 | 强一致 | 最终一致（部分操作强一致） |
| 协议 | S3 | S3 |
| 计费 | 自建运维 | 按存储 + 请求 + 流量 |
| 规模 | 数百节点 / PB | 无限 |
| 生态 | 需自己集成 | AWS 生态全 |
| 部署 | K8s / 物理机 | 不可部署 |

> **本地 S3 替代品首选 MinIO**；要全球化规模、合规、原生 AWS 集成还是用 S3。

## 十三、典型使用场景

- 私有云 / IDC 的 S3 替代
- AI 训练数据湖（图片、视频、模型 checkpoint）
- 备份与归档（替代磁带 / NAS）
- K8s 备份（Velero）
- 大数据 / 湖仓一体的存储层
- 日志、监控数据后端
- 静态资源 CDN 源站
- 软件仓库（Helm、镜像）
