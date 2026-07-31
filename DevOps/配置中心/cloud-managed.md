# 云厂商托管配置中心

主流云厂商的「配置 / 密钥 / 灰度发布」托管服务总览，解决自建 HA / 运维 / 备份成本，又引入了供应商绑定。选型时关注：版本、灰度、加密、推送、SDK、价格、自主可控。

## 一、AWS

### 1. SSM Parameter Store

```bash
# 写
aws ssm put-parameter \
  --name "/prod/myapp/db/password" \
  --value "secret123" \
  --type SecureString \
  --key-id "alias/aws/ssm"   # KMS 加密

# 读
aws ssm get-parameter --name "/prod/myapp/db/password" --with-decryption
```

| 层级 | 容量 | 价格 | 特性 |
| ---- | ---- | ---- | ---- |
| **Standard** | 4KB / 参数 | 免费 | 明文、string / stringlist |
| **Advanced** | 8KB / 参数 | $0.05/参数/月 | KMS 加密、参数策略（TTL 过期） |

特点：

- 与 IAM 深度集成：`ssm:GetParameter` 权限控制
- 路径层级 + label（`env=prod`）做环境隔离
- CloudFormation 友好：`AWS::SSM::Parameter`
- 与 Secrets Manager 区别：单纯凭据管理（**不自动轮转**），结合 Lambda 可做

### 2. AWS Secrets Manager

亮点：**自动轮转 Lambda 集成**。

```bash
aws secretsmanager create-secret \
  --name "prod/myapp/db" \
  --secret-string '{"username":"app","password":"old"}' \
  --kms-key-id "alias/secrets"

# 启用自动轮转
aws secretsmanager rotate-secret \
  --secret-id "prod/myapp/db" \
  --rotation-lambda-arn "arn:aws:lambda:...:myapp-rotation" \
  --rotation-rules "AutomaticallyAfterDays=14"
```

```python
import boto3, json
client = boto3.client('secretsmanager')
resp = client.get_secret_value(SecretId='prod/myapp/db')
secret = json.loads(resp['SecretString'])
db_pass = secret['password']
```

特点：

- 多版本（带 `AWSCURRENT` / `AWSPREVIOUS` 标记）
- 与 RDS 共享 RDS Master Password（简化旋转）
- CloudWatch 可观测
- 价格：$0.40/secret/月 + $0.05/10k API 调用

### 3. AWS AppConfig

配置 + 灰度发布 / Feature Flag 双栈。

```bash
# 应用 → AppConfig 配置 → 拉取
# 1. Application / Environment / Configuration Profile
# 2. Deployment Strategy：线性 50% / 1min
# 3. 配置 Source：SSM Parameter Document / S3 / CodePipeline
```

部署策略示例：

| 策略 | 描述 |
| ---- | ---- |
| **AppConfig.AllAtOnce** | 一次全部 |
| **AppConfig.Linear10PercentEvery30Seconds** | 30s 10% 线性 |
| **AppConfig.Canary10Percent20Minutes** | 10% 20min 后 100% |
| **自定义** | 自定义 step + 阶段 |

Lambda Extension 拉取：

```python
from urllib.request import urlopen
import os

# AmazonAppConfigAgent 已经把配置 / 特征标志写到 $HOME/.appconfig/ ...
# 进程只需读文件
with open('/opt/appconfig/feature.json') as f:
    features = json.load(f)
```

适合场景：Feature Flag、A/B、灰度发布、配置变更审计。

### 4. AWS Lambda Extension

```text
AmazonAppConfigAgent（Lambda Layer）
   │
   ▼
/opt/appconfig/feature.json  ←  进程轮询拉，最简调用
```

```bash
# Layer ARN
arn:aws:lambda:us-east-1:027255383542:layer:AWS-AppConfig-Extension:1
```

进程：cron 拉 → 内存 → 文件，监听本机 `localhost:2772` HTTP 端点也可。

## 二、阿里云

### 1. MSE Nacos

托管版 Nacos，开箱即用、免运维，Nacos 仍占国内 Spring Cloud 体系配置中心主流。

```yaml
spring:
  cloud:
    nacos:
      config:
        server-addr: mse-xxxxxx.nacos-ans.mse.aliyuncs.com:8848
        namespace: prod
        group: DEFAULT_GROUP
        file-extension: yaml
        access-key: ${RAM_AK}
        secret-key: ${RAM_SK}
```

支持：

- 公网 / VPC 内 双向 mTLS
- RAM 鉴权 + VPC 限速
- 兼容原生 Nacos SDK

### 2. ACM / 应用配置管理

```yaml
apiVersion: v1
kind: ConfigMap
# 实际由 acm-controller 同步
data:
  application.yaml: |
    server:
      port: 8080
```

- 阿里云传统配置中心
- 与 EDAS / 函数计算耦合
- 适合阿里云应用 PaaS 体系

### 3. KMS 凭据管家

```python
# Alibaba Cloud KMS SDK
from alibabacloud_kms20160120.client import Client
from alibabacloud_tea_openapi import models as open_api_models

client = Client(open_api_models.Config(access_key_id=..., access_key_secret=...))
resp = client.get_secret_value(secret_name='prod/myapp/db')
secret = resp.body.secret_data
```

集成：

- RDS / OSS / OTS 凭据自动轮转
- 与 RAM 角色结合应用访问
- 凭据管家支持自定义密钥（CreateSecret 时指定 KMS Key）

## 三、腾讯云 TSE

腾讯云微服务引擎（Tencent Service Engine）：

- 包括注册中心 Polaris / 配置中心 / 网关
- 一站式托管，开箱即用
- 兼容 Eureka / Nacos / Spring Cloud 协议
- 同 VPC 内免密访问

```yaml
spring:
  cloud:
    polaris:
      address: tse-xx.xx.tcloudbase.com:8091
```

适合：腾讯云原生 / 一站式 Spring Cloud 替代方案。

## 四、Azure

### 1. App Configuration

```bash
# 写
az appconfig kv set \
  --name "myapp-config" \
  --key "myapp/db/password" \
  --value "secret123" \
  --label "prod" \
  --content-type "text/plain"

# 读
az appconfig kv show \
  --name "myapp-config" \
  --key "myapp/db/password" \
  --label "prod"
```

亮点：

- **引用机制**：把 Key Vault 中的密钥作为 App Configuration 引用，KV 中心化、App Config 留只读副本
- **Feature Flag** 内建
- **Label 做环境隔离**（label=dev / staging / prod）
- **Snapshot**：抓取当前版本，能回滚
- 与 GitHub Actions / Azure DevOps 深度集成

Feature Flag：

```json
{
  "id": "Beta",
  "enabled": true,
  "conditions": {
    "client_filters": [
      { "name": "Microsoft.Percentage", "parameters": { "Value": 50 } }
    ]
  }
}
```

```java
// Spring 集成
@RefreshScope
@RestController
public class DemoController {
  @Value("${my.feature.beta:false}")
  private boolean beta;
}
```

### 2. Key Vault

```bash
az keyvault secret set \
  --vault-name "myapp-kv" \
  --name "db-password" \
  --value "secret123"
```

```java
// Java SDK DefaultAzureCredential
KeyClient keyClient = new KeyClientBuilder()
    .vaultUrl("https://myapp-kv.vault.azure.net/")
    .credential(new DefaultAzureCredential())
    .buildClient();
```

特点：

- HSM 防护（FIPS 140-2 Level 3）
- 与 AAD / Managed Identity 集成
- 软删除 + 清除保护

## 五、GCP

### 1. Secret Manager

```bash
echo -n "secret123" | gcloud secrets create db-password \
  --data-file=- \
  --replication-policy="automatic"

# 应用拉取
gcloud secrets versions access latest --secret="db-password"
```

```python
from google.cloud import secretmanager
client = secretmanager.SecretManagerServiceClient()
name = f"projects/{project}/secrets/db-password/versions/latest"
resp = client.access_secret_version(request={"name": name})
print(resp.payload.data.decode())
```

特点：

- IAM 细粒度 + 版本化
- Cloud Run / GKE / Cloud Functions 基于 Service Account 自动注入
- 自动复制多区域

### 2. Runtime Configurator

```bash
gcloud runtime-config configs create myapp-config
gcloud runtime-config configs variables set db.password secret123 \
  --config-name myapp-config
```

GCP 传统配置中心（CLI 类），未来被 **GKE ConfigMap / Config Connector** 占主流。注意：GCP 没有像 AppConfig 这样完整的灰度发布托管，靠自己的 GKE ConfigMap + Spanner / Firestore 替代。

## 六、厂商能力对比

| 能力 | AWS | 阿里云 | 腾讯云 | Azure | GCP |
| ---- | --- | ------ | ------ | ----- | --- |
| **通用 KV** | SSM Param | ACM | TSE | App Config | Runtime Config |
| **密钥管理** | Secrets Manager | KMS 凭据管家 | KMS | Key Vault | Secret Manager |
| **灰度发布** | AppConfig | MSE | TSE | App Config | 需自建 |
| **Feature Flag** | AppConfig + 第三方 | 第三方 | 第三方 | App Config 内建 | 第三方 |
| **自动轮转** | Secrets Manager | KMS 凭据 | – | Key Vault（部分） | 需自建 |
| **加密** | KMS | KMS | KMS | HSM / KMS | CMEK / HSM |
| **审计日志** | CloudTrail | 操作审计 | CloudAudit | Monitor + Log | Cloud Audit Logs |
| **推送方式** | API / Lambda | API / EDAS | API | API / Event Grid | API / Pub/Sub |
| **SDK** | boto3 / 多种 | java-python-go | go / java | JS / .NET / Java / Python | go / python / java |
| **价格模型** | 按 secret + API 调用 | 按规格 / QPS | 按量 | 按 store + 请求 | 按 secret + 访问 |
| **Spec** | 强 | 强 | 中 | 强 | 强 |

## 七、访问凭证方案（避免 AK 硬编码）

### 1. AWS IAM Role / IRSA

```yaml
# EKS
apiVersion: v1
kind: ServiceAccount
metadata:
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::111122223333:role/myapp-secrets
```

绑定 IRSA（IAM Role for Service Accounts）后，业务无需配置 AK，SDK 自动用 STS 拿临时凭证。

### 2. 阿里云 RRSA / RAM Role

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  annotations:
    aliyun.ram.role-arn: acs:ram::111122223333:role/myapp-secrets
```

- RRSA（RamRole for ServiceAccount）让 Pod 自动换 STS
- 私网 VPC 内免密 + ACK 上原生效

### 3. Workload Identity（GCP）

```bash
kubectl create serviceaccount --namespace prod myapp-sa
gcloud iam service-accounts add-iam-policy-binding \
  --role roles/secretmanager.secretAccessor \
  --member "serviceAccount:myproj.svc.id.goog[prod/myapp-sa]" \
  myapp-sa@myproj.iam.gserviceaccount.com
```

Pod 用 `myapp-sa` 自动具备 Secret Manager 访问权限。

### 4. Managed Identity（Azure）

```yaml
# AKS Pod Identity（已演进为 Workload Identity）
aadpodidentity:
  binding:
    name: myapp-mi
    selector: myapp-sa
```

过程无需 AK，靠 AAD 颁发。

## 八、典型接入示例

### 1. AWS SDK（Python）

```python
import boto3
from botocore.config import Config

session = boto3.Session()  # 自动从 IAM Role / env 选
client = session.client('secretsmanager', config=Config(retries={'max_attempts': 3}))

secret = client.get_secret_value(SecretId='prod/myapp/db')
import json
creds = json.loads(secret['SecretString'])
print(creds['password'])
```

### 2. Spring Cloud AWS

```yaml
spring:
  cloud:
    aws:
      region:
        static: us-east-1
        auto: true
      credentials:
        instance-profile: true   # 自动 EC2 / EKS IAM Role
  config:
    import: "aws-parameterstore:/config/myapp,aws-secretsmanager:/secret/myapp/db"
```

```java
@Value("${db.password}")
private String password;
```

### 3. Azure SDK（Java）

```java
SecretClient secretClient = new SecretClientBuilder()
    .vaultUrl("https://myapp-kv.vault.azure.net/")
    .credential(new DefaultAzureCredentialBuilder().build())
    .buildClient();

KeyVaultSecret secret = secretClient.getSecret("db-password");
String password = secret.getValue();
```

```properties
# application.properties
spring.cloud.azure.keyvault.secret.property-sources[0].endpoint=https://myapp-kv.vault.azure.net/
```

### 4. Alibaba Cloud ACM（Java）

```xml
<dependency>
  <groupId>com.alibaba.cloud</groupId>
  <artifactId>spring-cloud-starter-alicloud-acm</artifactId>
</dependency>
```

```properties
spring.application.name=myapp
spring.cloud.alicloud.acm.endpoint=acm.aliyun.com
spring.cloud.alicloud.acm.namespace=prod
spring.cloud.alicloud.acm.access-key=${RAM_AK}
spring.cloud.alicloud.acm.secret-key=${RAM_SK}
```

## 九、自建 vs 托管选型

| 维度 | 自建（Nacos / Consul / Vault） | 托管（AWS / Azure / Aliyun） |
| ---- | ------------------------------ | ---------------------------- |
| **初期成本** | 高（集群运维） | 低（按量付费） |
| **运维负担** | 高（备份、扩缩、版本升级） | 低 |
| **控制力** | 完全可控 | 受云厂商 API 限制 |
| **多云 / 迁移** | 友好 | 难迁移 |
| **合规** | 自己设计 | 合规资质好 |
| **学习曲线** | 概念多重 | 偏 SDK / IAM |
| **深度集成** | 需 SDK / 自己接 | 完美与云上其他服务联动 |
| **典型成本** | 3~5 人维护 | $0.05/secret + API 调用 |
| **适合场景** | 多云 / 自有 IDC / 强自主 | 上云 / 减少运维 |

## 十、优缺点

### 优点

- **省运维**：HA、备份、监控、扩缩云厂商搞定
- **开箱即用**：SDK 完善，权限模型与 IAM 集成
- **合规便利**：审计、KMS、HSM 认证齐全
- **弹性**：按量付费，灰度自适应
- **生态**：与本云其他服务联动（RDS 密码、ECS RAM Role）

### 缺点

- **供应商锁定**：API / 资源名 / 鉴权都跟云
- **跨云难**：GCP 业务想用 AWS Secrets Manager 需自建代理
- **价格随量上升**：高频调用的接口会超预算
- **部分功能受限**：高级特性（如 AppConfig 系）需要企业版
- **网络边界**：公网访问需 PrivateLink / VPCEP，配置不当易泄漏

## 十一、最佳实践

- **不存 AK**：始终用 IAM Role / Workload Identity / Managed Identity
- **加密**：所有敏感参数走 KMS / HSM，明文 Key 永远不出现在代码
- **版本与回滚**：所有配置中心启用版本化，配代码 CI 触发器
- **审计**：开 Audit Log，告警关键变更（删除 Secret、改 IAM）
- **限流**：客户端 SDK 启用本地缓存（如 AWS Secrets Manager `SecretsManagerCaching`），避免高频 API 调用
- **网络内连**：VPC / PrivateLink，避免公网暴露
- **服务网格联动**：同集群内服务间认证用 mTLS / Sidecar，避免应用直连凭据
- **金丝雀发布**：用 AppConfig 类灰度，先 10% → 50% → 100%
- **多环境隔离**：Label / namespace / 集群分环境，凭据不可重用
- **逃生计划**：定期演练「云厂商故障 → 切本地 Nacos / Vault」，避免全云单点
