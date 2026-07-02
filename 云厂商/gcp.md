# GCP (Google Cloud)

## 计算

- **Compute Engine (GCE)**：虚拟机，机器类型 N1/N2/N2D/E2/C2/M1/M2/A2/T2D/T2A
- **Spot VMs / Preemptible VMs**：抢占式
- **Cloud Run**：Serverless 容器 (HTTP/gRPC)
- **Cloud Functions**：事件驱动函数
- **App Engine**：PaaS (Standard / Flexible)
- **Bare Metal Solution**

## 存储

- **Cloud Storage (GCS)**：对象存储，Standard / Nearline / Coldline / Archive
- **Persistent Disk**：块存储 (HDD / SSD / Balanced / Extreme)
- **Filestore**：NFS 文件存储
- **Archive Storage**：超长归档

## 数据库

- **Cloud SQL**：MySQL / PG / SQL Server
- **AlloyDB**：PG 兼容，自研，号称比 Aurora for PG 强
- **Spanner**：全球强一致分布式关系库
- **Bigtable**：宽列 KV
- **Firestore**：文档型 (原 Datastore)
- **Memorystore**：托管 Redis / Memcached
- **BigQuery**：无服务数据仓库
- **Cloud Bigtable / Firestore / Spanner**

## 网络

- **VPC**：全球单 VPC，可跨区域子网
- **Cloud Load Balancing**：HTTP(S) / TCP / UDP / Internal，全球任播
- **Cloud CDN**：CDN
- **Cloud DNS**：DNS
- **Cloud Armor**：WAF + DDoS
- **Cloud Interconnect**：专线
- **Cloud VPN**
- **Private Service Connect / Private Google Access**
- **Cloud NAT**

## 容器

- **GKE (Google Kubernetes Engine)**：托管 K8s，业内标杆 (Standard / Autopilot)
- **Cloud Run**：Serverless 容器
- **Artifact Registry**：镜像仓库
- **Anthos**：混合云 / 多云 K8s 平台

## 安全与身份

- **Cloud IAM**：身份与权限
- **Cloud KMS**：密钥
- **Secret Manager**
- **Security Command Center (SCC)**：统一安全态势
- **Identity-Aware Proxy (IAP)**：零信任访问

## 监控运维

- **Cloud Monitoring (原 Stackdriver Monitoring)**
- **Cloud Logging (原 Stackdriver Logging)**
- **Cloud Trace / Profiler / Debugger**
- **Error Reporting**

## 消息

- **Pub/Sub**：全球消息
- **Eventarc**：事件路由
- **Dataflow**：流批一体 (基于 Apache Beam)
- **Dataproc**：托管 Hadoop / Spark

## 数据与 AI

- **BigQuery**：无服务数仓
- **Dataflow / Dataproc / Data Fusion / Pub/Sub**
- **Vertex AI**：统一 ML 平台
- **AutoML / Gemini API**

## IaC

- **Deployment Manager**：原生模板 (已逐渐让位)
- **Terraform**：事实标准