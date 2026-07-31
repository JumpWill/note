# 阿里云 SchedulerX / 云厂商托管调度

依托云厂商的托管分布式任务调度服务，免运维、自带 UI / 监控 / 告警 / 分级。

## 一、SchedulerX 概览（阿里云）

- 阿里云分布式任务调度平台
- 完全兼容 / 增强开源 XXL-JOB 模型
- 支持 Java / Python / Shell / K8s / Serverless（支持 HTTP / 金融 / 消息）
- 私有化版本：SchedulerX 2.0 商业版 + 阿里云 EDAS / SAE 集成

## 二、其他云厂商

| 厂商 | 服务 |
| ---- | ---- |
| **AWS** | EventBridge Scheduler / Step Functions / MWAA (Airflow) |
| **Azure** | Logic Apps / AKS + Data Factory / Durable Functions |
| **GCP** | Cloud Scheduler + Workflows + Cloud Composer (Airflow) |
| **阿里云** | SchedulerX / DataWorks / Function Compute 定时 |
| **腾讯云** | TSF Scheduler / EventBridge / TKE CronJob |
| **华为云** | FunctionGraph 定时 / AOM 任务 / Cafferay |

## 三、SchedulerX 核心概念

| 概念 | 含义 |
| ---- | ---- |
| **任务 (Job)** | 单个调度单元 |
| **任务组 (Group)** | 多个任务的批量管理 |
| **执行器 (Executor)** | 部署在业务机器上的客户端 |
| **路由策略** | 调度到具体 executor 的规则 |
| **分片** | 任务并行执行 |
| **依赖** | 上游任务依赖 |

## 四、典型用法

### 1. Java 任务（企业版）

```java
@JobHandler("demo")
public class DemoJob extends IJobHandler {
    @Override
    public ReturnT<String> execute(String param) throws Exception {
        // biz
        return ReturnT.SUCCESS;
    }
}
```

### 2. Python 任务

```python
import json

def handler(event, context):
    param = event.get("param")
    return {"result": "ok"}
```

### 3. HTTP 任务

- URL + Method + Headers + Body
- 支持鉴权

### 4. K8s 任务

```yaml
apiVersion: apps/v1
kind: Job
metadata:
  name: my-task
spec:
  template:
    spec:
      containers: [...]
      restartPolicy: Never
```

## 五、分片与广播

```java
int total = XxlJobHelper.getShardTotal();
int index = XxlJobHelper.getShardIndex();
List<Long> part = allIds.stream()
    .filter(id -> id % total == index)
    .collect(Collectors.toList());
```

或框架自动按数据源分区（数据库分片）。

## 六、调度与触发

- Cron
- 手动
- API
- 补数
- 事件触发（与 EventBridge）

## 七、告警与监控

- 失败重试 + 次数阈值
- 邮件 / 钉钉 / 企业微信
- 集成 ARMS 监控
- 任务日志集中查

## 八、对接 DataWorks

- DataWorks 节点即调度点
- 数据集成 / ODPS SQL / EMR / Shell
- 完整一站式大数据

## 九、AWS EventBridge Scheduler

无服务器 Cron：

```yaml
ScheduleExpression: rate(1 hour)
Target:
  Arn: arn:aws:lambda:...
  RoleArn: arn:...
```

- 毫秒级精度
- 与所有 AWS 服务集成
- 兼容 cron / rate / unix cron

### Lambda 任务示例

```python
import boto3

def handler(event, context):
    s3 = boto3.client("s3")
    s3.put_object(Bucket="mybucket", Key="daily.json",
                  Body=str(event))
    return "ok"
```

## 十、AWS Step Functions

状态机：

```text
JSON
```

- 多步工作流
- 可视化 UI
- 与 Lambda / ECS / SNS 集成
- Express vs Standard：不同 SLA 计费

## 十一、GCP Cloud Composer

- 托管 Airflow
- 自动扩缩
- 与 GCP 服务深度集成

## 十二、Azure Logic Apps

- 跨云集成触发
- 低代码工作流
- Microsoft 生态联动

## 十三、选型

| 需求 | 建议 |
| ---- | ---- |
| **简单定时** | 云厂商 Scheduled Function / Cloud Scheduler / SchedulerX HTTP 任务 |
| **Java 调度中心** | SchedulerX 私有 / 阿里云 / XXL-JOB 自建 |
| **跨云混合** | Temporal / Airflow 自建 |
| **AWS 体系** | EventBridge Scheduler + Step Functions |
| **Azure 体系** | Logic Apps / Durable Functions |
| **GCP 体系** | Cloud Scheduler + Composer |
| **国产** | SchedulerX（阿里云）+ DataWorks |

## 十四、托管 vs 自建

| 维度 | 托管 | 自建 |
| ---- | ---- | ---- |
| 运维 | 几乎零 | 自己搭集群 |
| 监控告警 | 内置 | 自己接 |
| 安全合规 | 厂商负责 | 自己审计 |
| 扩展性 | 调度中心不感知 | 自己排障 |
| 跨云 | 较弱 | 强 |
| 成本 | 调度实例 + 调用 | 服务器 + 数据库 |

## 十五、SchedulerX 商业化能力

- 命名空间隔离
- 多租户
- 大规模分片
- 自定义脚本 (Python / Shell)
- K8s Job 整合
- 大数据生态（ODPS / EMR）
- 容灾多活

## 十六、最佳实践

- **任务幂等**：分布式调度必然可能重跑
- **分片稳态**：用 Redis 等公共存储保持分片状态
- **告警收敛**：定时任务失败要做汇总
- **日志**：送集中式日志服务
- **依赖**：上游 schema 变更要更新
- **审计**：每年 review 任务列表
