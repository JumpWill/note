# AWS

## 计算

- **EC2**：虚拟机，丰富的实例族 (M/C/R/X/P/G/Inf/T 系列)
- **Lambda**：Serverless 函数，最长 15 分钟
- **Fargate**：EKS/ECS 的 Serverless 工作节点
- **Lightsail**：轻量 VPS
- **Batch**：批量计算调度

## 存储

- **S3**：对象存储，支持标准 / IA / Glacier / Deep Archive
- **EBS**：块存储，gp3 / io2 类型
- **EFS**：NFS 文件存储
- **FSx**：Windows / Lustre / NetApp ONTAP
- **Storage Gateway**：本地 ↔ S3 混合存储

## 数据库

- **RDS**：托管 MySQL / PG / MariaDB / Oracle / SQL Server
- **Aurora**：兼容 MySQL/PG，6 副本存算分离
- **DynamoDB**：KV / 文档型，全球表
- **ElastiCache**：托管 Redis / Memcached
- **Redshift**：数据仓库
- **Neptune**：图数据库
- **Timestream / QLDB**：时序 / 账本

## 网络

- **VPC**：私有网络，含 Subnet / Route Table / IGW / NAT GW
- **ALB**：七层 LB，支持路径/Header/Host 路由
- **NLB**：四层 LB，超高吞吐
- **GLB**：网关负载均衡器，透明插入第三方设备
- **CloudFront**：CDN
- **Route 53**：DNS
- **Direct Connect**：物理专线
- **Transit Gateway**：VPC / DC 中转枢纽
- **PrivateLink**：私有连接托管服务

## 容器

- **EKS**：托管 K8s
- **ECS**：自研容器编排
- **ECR**：镜像仓库

## 安全与身份

- **IAM**：User / Role / Group / Policy，跨账号靠 Role + AssumeRole
- **KMS**：密钥托管
- **WAF / Shield**：Web 防火墙与 DDoS 防护
- **Secrets Manager / Parameter Store**：密钥/配置
- **Cognito**：身份认证
- **GuardDuty**：威胁检测

## 监控运维

- **CloudWatch**：指标 + 日志 + 告警
- **X-Ray**：链路追踪
- **CloudTrail**：API 审计
- **Trusted Advisor / Compute Optimizer**：成本 / 性能建议

## 消息

- **SQS**：标准队列 + FIFO
- **SNS**：Pub/Sub 主题
- **EventBridge**：跨服务事件总线
- **Kinesis**：实时流数据 (Data Streams / Firehose / Analytics)
- **MSK**：托管 Kafka

## IaC

- **CloudFormation**：原生模板 (JSON/YAML)
- **CDK**：用代码生成 CFN
- **Terraform**：跨云通用