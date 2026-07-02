# 阿里云 (Aliyun)

## 计算

- **ECS**：虚拟机，规格族 g (通用) / c (计算) / r (内存) / gpu / arm (倚天)
- **ECI**：Serverless 容器，ACK 的 Serverless 工作节点
- **函数计算 FC**：事件驱动 Serverless
- **裸金属**：物理机

## 存储

- **OSS**：对象存储，存储类型 标准 / 低频 / 归档 / 冷归档 / 深度冷归档
- **块存储**：ESSD (PL0/1/2/3) / SSD / 高效云盘
- **NAS**：NFS/SMB 文件存储
- **CPFS**：高性能并行文件系统
- **HBR**：混合云备份

## 数据库

- **RDS**：MySQL / PG / SQL Server / MariaDB
- **PolarDB**：MySQL/PG/Oracle 兼容，计算存储分离，集群架构
- **PolarDB-X**：分布式版（原 DRDS）
- **OceanBase**：原生分布式数据库，金融级
- **Redis / Tair**：社区版 vs 阿里自研 (Tair 持久化版本)
- **AnalyticDB (ADB)**：实时数仓，MySQL/PG 语法
- **Lindorm**：多模 (KV/宽表/时序/搜索)
- **MongoDB / Cassandra / ClickHouse**：托管版

## 网络

- **VPC**：私有网络 + 交换机 (Subnet)
- **SLB**：负载均衡 (ALB 七层 / NLB 四层 / CLB 传统型)
- **NAT 网关 / EIP**：公网出入口
- **CEN (云企业网)**：跨地域 / 跨账号 VPC 互通
- **云连接 / 智能接入网关**：混合云
- **CDN / DCDN (全站加速)**：动静一体
- **PrivateLink**：终端节点服务

## 容器

- **ACK**：托管 K8s (标准版 / Pro / 边缘)
- **ASK**：Serverless K8s
- **ACR**：镜像仓库 (企业版 EE / 个人版)
- **ASM**：服务网格 (Istio 兼容)

## 安全与身份

- **RAM**：资源访问管理 (对应 IAM)，角色 STS
- **KMS**：密钥管理
- **WAF**：Web 应用防火墙
- **Anti-DDoS Pro / 高级版**：DDoS 防护
- **ActionTrail**：操作审计
- **Secrets Manager**：密钥托管
- **堡垒机 / 云安全中心**：运维与主机安全

## 监控运维

- **CloudMonitor (云监控)**：指标 + 告警
- **SLS (日志服务)**：Logtail 采集 + 查询 + 分析
- **ARMS**：应用实时监控，含 Prometheus / 链路追踪 / 前端监控
- **XTrace**：链路追踪

## 消息

- **RocketMQ**：阿里自研，消息领域的事实标准之一
- **Kafka (Kafka 版)**：Confluent 兼容
- **MNS (消息服务)**：轻量队列 + 主题
- **EventBridge**：事件总线

## 通用云原生

- **ROS**：资源编排 (CloudFormation 替身)
- **Terraform**：跨云