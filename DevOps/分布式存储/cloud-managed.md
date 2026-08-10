# 云厂商托管存储

各大云厂商提供的**块、文件、对象**存储服务，是**最省事**的选择——按量计费、弹性伸缩、免运维。私有云项目越来越少见，公有云上几乎都是首选。

## 一、为什么选云厂商托管

- **零运维**:硬件、网络、备份、扩容全交给云厂
- **高可用**:多 AZ / 多 Region 自动复制
- **弹性**:按需扩缩，按量计费
- **安全**:加密、ACL、审计、合规（等保 / GDPR / HIPAA）
- **生态**:与云上计算、网络、AI 深度集成
- **SLA**:99.9% ~ 99.999999999%（11 个 9 对象存储）

## 二、主流云厂商存储服务对照

| 维度 | AWS | 阿里云 | 腾讯云 | 华为云 | GCP |
| --- | --- | --- | --- | --- | --- |
| **块存储** | EBS | 云盘 / ESSD | CBS | EVS | Persistent Disk |
| **文件存储** | EFS / FSx | NAS / CPFS | CFS | SFS | Filestore |
| **对象存储** | S3 | OSS | COS | OBS | GCS |
| **冷归档** | S3 Glacier | 归档存储 | 归档存储 | 归档存储 | Coldline / Archive |
| **分布式文件系统** | FSx for Lustre | CPFS | GooseFS | SFS Turbo | Lustre |
| **K8s 集成** | EBS CSI / EFS CSI | disk-csi / nas-csi | CBS CSI | CSI | GCE PD CSI |
| **SLA** | 99.9%~99.99% | 99.95%~99.999% | 99.95%~99.99% | 99.95% | 99.9%~99.99% |

## 三、块存储 (Block Storage)

### 1. 典型特性

- **网络磁盘**:NVMe over Fabric 或 iSCSI
- **RWO (ReadWriteOnce)**:单实例挂载
- **快照**:秒级创建，跨 Region 复制
- **加密**:服务端加密 (KMS)
- **性能等级**:通用型、SSD、高性能 SSD、NVMe

### 2. 各家性能等级示例

| 厂商 | 等级 | IOPS / 吞吐 |
| --- | --- | --- |
| AWS | gp3 / io1 / io2 Block Express | 16K / 256K IOPS |
| 阿里云 | ESSD PL1 / PL2 / PL3 | 50K / 100K / 100W IOPS |
| 腾讯云 | CBS SSD 增强型 | 100K IOPS |
| 华为云 | EVS 极速 SSD | 128K IOPS |
| GCP | pd-balanced / pd-ssd / pd-extreme | 数十 K IOPS |

### 3. 使用场景

- 数据库（MySQL / Postgres / Oracle）
- 消息队列持久化
- 单实例有状态应用
- 操作系统盘

### 4. 注意事项

- 跨 AZ 不可挂载（除非用分布式存储）
- 性能等级切换通常需要停机或重建
- 容量调整：在线扩容 / 缩容（部分受限）

## 四、文件存储 (File Storage)

### 1. 典型特性

- **NFS / SMB 协议**
- **RWX (ReadWriteMany)**:多实例共享
- **POSIX 兼容**
- **按容量或按使用量计费**

### 2. 典型产品

| 厂商 | 服务 | 特点 |
| --- | --- | --- |
| AWS | EFS | NFS v4，弹性容量 |
| AWS | FSx (Lustre / Windows / ONTAP / OpenZFS) | 高性能 |
| 阿里云 | NAS | 通用 / 极速型 |
| 阿里云 | CPFS | 高性能并行文件系统 |
| 腾讯云 | CFS | 标准 / 增强型 |
| 华为云 | SFS / SFS Turbo | 通用 / 高吞吐 |
| GCP | Filestore | Basic / Enterprise |

### 3. 使用场景

- 共享文件系统（媒资、模型）
- K8s 多 Pod 共享 (替代 cephfs)
- 大数据 / HPC (Lustre)
- 传统应用迁移 (SMB)

### 4. 注意事项

- 跨区域访问需走传输层
- 性能等级与容量解耦，但价格梯度大
- 与 S3 互补：热数据 NAS / 冷数据 S3

## 五、对象存储 (Object Storage)

### 1. 典型特性

- **HTTP RESTful API** (S3 兼容)
- **EB 级容量**
- **11 个 9 持久性** (如 S3)
- **多版本、生命周期、跨区复制**
- **冷热分层**

### 2. 各家对象存储

| 厂商 | 服务 | S3 兼容 | 特色 |
| --- | --- | --- | --- |
| AWS | S3 | 100% | 全球生态 |
| 阿里云 | OSS | 100% | 阿里云生态 |
| 腾讯云 | COS | 100% | 腾讯云生态 |
| 华为云 | OBS | 100% | 华为云生态 |
| GCP | GCS | 兼容 | GCP 生态 |
| 微软 | Azure Blob | 兼容 | Azure 生态 |
| MinIO (自建) | MinIO | 100% | 私有云 |

### 3. 存储类型与价格梯度

| 类型 | 访问频率 | 典型价格 | 取回费用 |
| --- | --- | --- | --- |
| **标准** | 热 | 高 | 无 |
| **低频** | 周~月 | 中 | 略高 |
| **归档** | 月~年 | 低 | 高（且慢） |
| **深度归档** | 年 | 极低 | 极高（数小时） |

### 4. 典型使用场景

- 静态资源、媒体文件
- 备份与归档
- 数据湖底层
- 日志归档
- 训练数据 / 模型
- 软件包、镜像
- K8s 备份 (Velero)

### 5. 注意事项

- **公网出流量按 GB 计费**,CDN 是省钱关键
- 跨区复制需开启
- 大量小对象效率下降,考虑打包
- 命名规则与目录前缀设计

## 六、冷归档存储

- **S3 Glacier / 阿里归档 / COS 归档 / GCS Archive**
- 价格极低（几分钱 / GB / 月）
- **取回延迟高**(分钟 ~ 数小时)
- 适合合规归档、灾备

## 七、Kubernetes 集成

### 1. CSI 驱动

各云都提供 CSI 驱动:

```yaml
# 阿里云 disk-csi 示例
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: alicloud-disk-ssd
provisioner: diskplugin.csi.alibabacloud.com
parameters:
  type: cloud_essd
  regionId: cn-hangzhou
reclaimPolicy: Delete
```

### 2. 多 Pod 共享

- 块存储：CSI 支持 RWO，部分支持 RWX（需要 multi-attach）
- 文件存储：天然 RWX
- 对象存储：通过 S3 协议挂载（s3fs / goofys）

### 3. 跨集群 / 跨云

- 用对象存储做数据共享
- 用 CSI snapshot 做备份 / 恢复
- 用 Velero 备份到对象存储

## 八、成本优化

### 1. 容量成本

- **冷数据归档**:标准 → 低频 → 归档
- **删除无用数据**:快照、临时文件、孤儿资源
- **预留容量**:部分厂商有预留实例折扣

### 2. 流量成本

- **CDN 加速**:静态资源走 CDN
- **同 Region 内免费**:跨 AZ 跨 Region 计费
- **压缩与去重**:减少存储与流量

### 3. 性能成本

- **按业务等级选**:数据库用 SSD，日志用标准
- **避免过度配置**:IOPS 不必拉满
- **定时降配**:开发环境定时关

## 九、安全与合规

- **服务端加密**:SSE-S3 / SSE-KMS
- **传输加密**:TLS / HTTPS
- **访问控制**:IAM Policy / Bucket Policy
- **审计日志**:记录所有 API 调用
- **合规认证**:等保 / SOC2 / ISO27001 / GDPR

## 十、容灾与备份

### 1. 跨可用区

- 块存储：单 AZ，**AZ 故障会丢**
- 文件存储：部分支持跨 AZ
- 对象存储：默认跨 AZ 复制

### 2. 跨地域

- 快照跨 Region 复制
- 对象存储跨 Region 复制（CRR）
- 异地读 + 写主 Region

### 3. 备份策略

- 自动快照 + 跨 Region 复制
- 备份到对象存储归档层
- 定期恢复演练

## 十一、迁移与上云

- **在线迁移**:S3 兼容 API 之间迁移工具 (rclone、DataSync)
- **离线迁移**:快递硬盘 (Snowball / 闪电立方)
- **双写过渡**:业务层先双写，再切读
- **兼容性测试**:SDK 兼容性、API 差异

## 十二、典型组合

### 1. 通用 Web 应用

- 系统盘：云盘
- 数据库：云盘 SSD / 数据库服务
- 静态资源：OSS + CDN
- 备份：OSS 归档

### 2. 大数据

- 计算：EMR / DataWorks / 弹性 MapReduce
- 存储：对象存储（HDFS 接口）
- 协调：RDS / ZooKeeper
- 元数据：RDS

### 3. AI 训练

- 训练数据：对象存储 + 高速文件系统 (Lustre / CPFS)
- 模型：对象存储
- 推理：云盘
- 备份：对象存储

### 4. K8s 工作负载

- Pod 数据：CSI 块 / 文件
- 镜像：镜像仓库 (ACR / ECR)
- 备份：Velero + 对象存储
- 日志：对象存储归档

## 十三、选型建议

| 场景 | 推荐 |
| --- | --- |
| 普通应用 + 想要最省事 | 云厂商托管 |
| 多云 / 跨云 | 抽象 S3 兼容层 |
| 已有 K8s,接好 CSI | 各家 CSI |
| 大数据 + AI | 对象存储 + 高性能文件系统 |
| 极致成本 | 冷归档 + 生命周期 |
| 数据主权 / 私有 | MinIO / Ceph / Rook |
