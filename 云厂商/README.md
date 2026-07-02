# 云厂商

按厂商分文件整理云资源概念：

- [AWS](./aws.md)
- [阿里云 Aliyun](./aliyun.md)
- [腾讯云 Tencent](./tencent.md)
- [华为云 Huawei](./huawei.md)
- [Azure](./azure.md)
- [GCP](./gcp.md)

## 通用概念对比

| 概念 | AWS | 阿里云 | 腾讯云 | 华为云 | Azure | GCP |
| --- | --- | --- | --- | --- | --- | --- |
| 虚拟机 | EC2 | ECS | CVM | ECS | VM | GCE |
| 对象存储 | S3 | OSS | COS | OBS | Blob | GCS |
| 块存储 | EBS | 云盘 | CBS | EVS | Disk | PD |
| 关系库 | RDS | RDS | CDB | RDS | SQL DB | Cloud SQL |
| 自研 DB | Aurora | PolarDB | TDSQL | GaussDB | - | AlloyDB |
| K8s | EKS | ACK | TKE | CCE | AKS | GKE |
| Serverless | Lambda | FC | SCF | FunctionGraph | Functions | Functions |
| VPC | VPC | VPC | VPC | VPC | VNet | VPC |
| 负载均衡 | ALB/NLB | SLB | CLB | ELB | LB | LB |
| 缓存 | ElastiCache | Redis/Tair | CRS | DCS | Cache | Memorystore |
| 消息 | SQS/SNS | RocketMQ/MNS | CKafka/TDMQ | DMS | Service Bus | Pub/Sub |
| 监控 | CloudWatch | CloudMonitor | CM | AOM | Monitor | Monitoring |
| IAM | IAM | RAM | CAM | IAM | Entra ID | IAM |
| 密钥 | KMS | KMS | KMS | KMS | Key Vault | KMS |
| CDN | CloudFront | CDN | CDN | CDN | CDN | CDN |