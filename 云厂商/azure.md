# Azure

## 计算

- **Virtual Machines**：虚拟机，Dv3/Ev3/Dasv5/Easv5 等系列，含 ARM (Ampere)
- **VMSS (Virtual Machine Scale Sets)**：伸缩集
- **App Service**：PaaS Web
- **Azure Functions**：Serverless
- **Container Apps**：Serverless 容器
- **Spring Apps**：Spring Boot 托管

## 存储

- **Blob Storage**：对象存储 (Hot / Cool / Cold / Archive)
- **Disk Storage**：托管磁盘 (Premium SSD / Standard SSD / HDD)
- **Azure Files**：SMB 文件共享
- **Azure NetApp Files / Azure HPC Cache**
- **Data Lake Storage**：基于 Blob 的数据湖

## 数据库

- **Azure SQL / SQL MI / SQL DB**：托管 SQL Server
- **Azure Database for MySQL / PostgreSQL / MariaDB**
- **Cosmos DB**：全球分布式多模 (SQL API / MongoDB / Cassandra / Gremlin / Table)
- **Azure Cache for Redis**
- **Synapse Analytics**：数据仓库
- **Database for MongoDB**

## 网络

- **VNet**：虚拟网络
- **Load Balancer**：四层
- **Application Gateway**：七层 + WAF
- **Front Door**：全局七层 LB + CDN
- **Traffic Manager**：DNS 级流量调度
- **ExpressRoute**：专线
- **VPN Gateway**
- **Private Link / Private Endpoint**
- **CDN**

## 容器

- **AKS**：托管 K8s
- **ACR**：镜像仓库
- **Container Apps**：Serverless 容器

## 安全与身份

- **Microsoft Entra ID** (原 Azure AD)：身份与 SSO
- **Azure RBAC**
- **Key Vault**：密钥 / 证书 / 密钥
- **DDoS Protection / WAF / Defender for Cloud**
- **Microsoft Defender**：威胁防护全家桶

## 监控运维

- **Azure Monitor**：指标 + 日志
- **Log Analytics**：KQL 查询
- **Application Insights**：APM
- **Activity Log**

## 消息

- **Service Bus**：企业消息
- **Event Grid**：事件路由
- **Event Hubs**：流数据 (Kafka 兼容)
- **Storage Queues / Queue Storage**

## IaC

- **ARM Templates / Bicep**
- **Terraform**