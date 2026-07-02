# 腾讯云 (Tencent Cloud)

## 计算

- **CVM**：云服务器，规格族 S (标准) / SA / C / CN / M / GPU
- **裸金属 / 黑石**：物理机
- **SCF (云函数)**：Serverless
- **轻量应用服务器 Lighthouse**：入门级 VPS

## 存储

- **COS**：对象存储，标准 / 低频 / 归档 / 深度归档
- **CBS**：云硬盘，增强 SSD / SSD / 高性能云盘
- **CFS**：NFS 文件存储
- **COSFS / COSCMD**：把 COS 挂成文件系统或 CLI 工具
- **CSG**：存储网关

## 数据库

- **CDB / CynosDB (TDSQL-C)**：托管 MySQL，CynosDB 是计算存储分离
- **TDSQL (MySQL/PG 版)**：分布式版，强同步
- **TDSQL-A**：分析型 (PG 兼容)
- **Redis (CRS)**：托管 Redis
- **MongoDB**：托管
- **TcaplusDB**：游戏级 KV
- **ClickHouse / Doris**：托管 OLAP

## 网络

- **VPC**：私有网络，含子网 / 路由表 / NAT / EIP
- **CLB**：负载均衡 (七层 / 四层)
- **CCN (云联网)**：跨地域/账号 VPC 互通
- **对等连接 / VPN / 专线接入**
- **CDN / ECDN (全站加速)**
- **PrivateLink**：终端连接

## 容器

- **TKE**：托管 K8s (标准 / 集群 / Serverless)
- **EKS**：弹性 K8s (Serverless)
- **TCR**：镜像仓库 (个人版 / 企业版)
- **TCM**：服务网格

## 安全与身份

- **CAM**：访问管理 (对应 IAM)，角色 + STS
- **KMS / SSM**：密钥与配置
- **WAF / 大禹 Anti-DDoS**：防护
- **堡垒机 / 云镜**：运维安全
- **Secrets Manager**

## 监控运维

- **CM (云监控)**：指标 + 告警
- **CLS (日志服务)**：采集 + 检索 + 分析
- **CAT (云拨测) / Prometheus 监控**

## 消息

- **CKafka**：托管 Kafka
- **TDMQ**：RocketMQ / Pulsar / RabbitMQ 多种引擎
- **CMQ**：队列服务 (已较少推荐)
- **EventBridge**：事件总线

## IaC

- **TAT / TIC**：编排与 IaC
- **Terraform**：跨云