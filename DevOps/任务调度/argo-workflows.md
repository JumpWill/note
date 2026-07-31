# Argo Workflows

K8s 原生工作流引擎，每个 Step 即一个 Pod，原生 CI/CD / 数据处理 / ML pipeline。

## 一、定位

- K8s Native：Workflow CRD + Controller
- Steps = Pods / Containers
- 强 DAG / 依赖 / 重试 / 暂停
- 适合 K8s 上跑 CI、ML、数据 pipeline、批处理
- 由 Intuit 开源，现 CNCF Incubating

## 二、核心概念

| 概念 | 含义 |
| ---- | ---- |
| **Workflow** | CRD 资源，定义 DAG |
| **WorkflowTemplate** | 可复用模板 |
| **Template** | 步骤模板（Container / Script / Resource / Step / DAG / Suspend） |
| **Step** | DAG 中的一对顺序依赖 |
| **DAG Task** | DAG 中的并行依赖节点 |
| **CronWorkflow** | 时间触发 CRD |
| **WorkflowEventBinding** | 事件触发 |
| **Artifact** | 步骤间的产物 (S3 / GCS / OSS) |
| **Parameter** | 入参 / 出参 |
| **WorkflowArchive** | 历史持久化 |
| **Retry / Backoff** | 重试策略 |
| **Sidecar / 资源限制** | Pod 资源 / 注入 |
| **Exit Hook / LifCycle Hook** | 工作流级回调 |

## 三、Hello World

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Workflow
metadata:
  generateName: hello-
spec:
  entrypoint: main
  templates:
    - name: main
      steps:
        - - name: echo
            template: echo
        - - name: process
            template: process
    - name: echo
      container:
        image: alpine:3.20
        command: [echo, "hello world"]
    - name: process
      script:
        image: python:3.12
        command: [python]
        source: |
          print("processing")
```

```bash
argo submit -n argo --watch hello.yaml
```

## 四、DAG 模板

```yaml
- name: main
  dag:
    tasks:
      - name: A
        template: extract
      - name: B
        template: transform
        dependencies: [A]
        arguments:
          parameters: [{name: data, value: "{{tasks.A.outputs.parameters.data}}"}]
      - name: C
        template: analyze
        dependencies: [B]
      - name: D
        template: report
        dependencies: [B, C]
```

依赖关系：

```text
A ── B ── C ── D
            │
            └────D
```

## 五、参数与产物

### 1. 参数

```yaml
arguments:
  parameters:
    - name: region
      value: cn-shanghai
```

引用：

```yaml
arguments:
  parameters:
    - name: region
      value: "{{workflow.parameters.region}}"
```

### 2. 输出参数

```yaml
- name: capture
  outputs:
    parameters:
      - name: commit
        valueFrom:
          path: /tmp/commit
```

### 3. Artifact

```yaml
- name: source
  inputs:
    artifacts:
      - name: src
        path: /workspace/src
        s3:
          key: data/source.tar.gz
          endpoint: minio:9000
          bucket: mybucket
          insecure: true
```

## 六、循环 / 条件 / 退出处理

### 1. Loop (withItems / withSequence)

```yaml
arguments:
  parameters:
    - name: id
      value: "{{item}}"
withItems:
  - 1
  - 2
  - 3
```

`withSequence: 1..10` 或 `from: "{{steps.A.outputs.parameters.next}}"`。

### 2. 条件

```yaml
when: "{{inputs.param.score > 0.8}}"
```

### 3. ContinueOn

```yaml
continueOn:
  failed: true
  error: false
```

### 4. 退出处理

```yaml
exitHandler: cleanup
onExit: cleanup
```

`cleanup` 在 workflow 退出时触发。

## 七、CronWorkflow

```yaml
apiVersion: argoproj.io/v1alpha1
kind: CronWorkflow
metadata:
  name: nightly-etl
spec:
  schedule: "0 3 * * *"
  timezone: "Asia/Shanghai"
  concurrencyPolicy: Replace
  startingDeadlineSeconds: 30
  workflowSpec:
    entrypoint: main
    templates:
      - name: main
        steps: [...]
```

- `Replace` / `Allow` / `Forbid` 并发策略
- 支持并发上限

## 八、WorkflowTemplate / ClusterWorkflowTemplate

- `WorkflowTemplate`：命名空间
- `ClusterWorkflowTemplate`：集群
- 通过 `submit` 时引用

```yaml
spec:
  workflowTemplateRef:
    name: night-etl-template
```

## 九、Artifact Repositories

```yaml
artifacts:
  - name: data
    path: /mnt/data
    s3:
      bucket: my-bucket
      key: data.tar.gz
      endpoint: minio:9000
      insecure: true
      accessKeySecret:
        name: my-secret
        key: access
      secretKeySecret:
        name: my-secret
        key: secret
```

支持 S3 / GCS / OSS / HTTP / Git / raw / OCI。

## 十、退出、重试、Saga

### 1. Retry Strategy

```yaml
retryStrategy:
  limit: 5
  backoff:
    duration: "30s"
    factor: 2
    maxDuration: "5m"
```

### 2. Retry 在 Pod 内 / 容错

- 节点级 retry 不消耗 K8s 资源
- 节点级 retry 不消耗 Workflow 状态（重启容器）— 默认行为

### 3. Resubmit / Retry Workflow

```bash
argo retry <name>
argo resubmit <name>
```

## 十一、触发方式

- CLI
- UI（Argo Workflows Server UI）
- Kubernetes API
- Argo Events：监听外部事件触发
- HTTP/Webhook
- Message Bus（Kafka / NATS）

## 十二、安全 / RBAC

- `ServiceAccount` + `Role`
- Workflow 不允许提权（控制器过滤）
- Workflow Artifact 凭证注入通过 Secret
- 审计 + 监控（标准 K8s metrics）

## 十三、与 Airflow 对比

| 维度 | Argo | Airflow |
| ---- | ---- | ------- |
| 描述 | K8s YAML | Python |
| 执行模型 | Pod / Container | Executor |
| 资源隔离 | 强（Pod） | 弱 |
| 启动 | 较快（镜像预热） | 较慢 |
| 适合团队 | SRE / DevOps | Data |

## 十四、典型用法

- **CI Pipeline**：push → build → test → image → deploy
- **Batch ETL**：定期 Spark / Flink step
- **ML Pipeline**：数据采集 → 训练 → 评估 → 上线
- **业务流式操作**：跨 K8s 集群 / 多云操作

## 十五、最佳实践

- **使用 WorkflowTemplate + CronWorkflow**
- **资源限定**：节点 pod 需要 `resources`
- **重试策略**：易失败步骤加 retry
- **Artifact**：用 S3 / MinIO 缓存产物
- **避免大步骤**：拆分到 DAG
- **取消**：用 `kubectl -n argo delete wf ...`

## 十六、Argo Events

事件驱动：

- EventBus (NATS)
- Sensor 监听 + Trigger workflow

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Sensor
metadata:
  name: webhook
spec:
  dependencies:
    - name: dep
      eventSourceName: webhook
      filters:
        data:
          - type: header
            value:
              - name: Authorization
                prefix: Bearer
  triggers:
    - template:
        name: run-workflow
        k8s:
          operation: create
          source:
            resource:
              apiVersion: argoproj.io/v1alpha1
              kind: Workflow
              metadata:
                generateName: webhook-triggered-
              spec: ...
```

## 十七、安装

### 1. Helm

```bash
helm repo add argo https://argoproj.github.io/argo-helm
helm install argo-workflows argo/argo-workflows
```

### 2. HA 模式

- 多副本 controller + 多副本 server
- 工作流存储在 K8s ETCD
- Artifact 在外部存储

## 十八、与 WorkflowTemplate 复用

```yaml
apiVersion: argoproj.io/v1alpha1
kind: WorkflowTemplate
metadata:
  name: train-model
spec:
  templates:
    - name: main
      steps:
        - - template: prepare
        - - template: train
          when: "{{workflow.parameters.do_train}}"
          arguments: {...}
    - name: prepare
      ...
```

提交：

```bash
argo submit --from workflowtemplate/train-model \
  --entrypoint main \
  -p do_train=true
```

## 十九、常见坑

- 镜像没传 Secret → 在 workflow.spec.podSpec 配置 imagePullSecrets
- Artifact 凭证错误 → 凭证在 Secret
- 时间触发停止：`kubectl patch cronwf x -p '{"spec":{"suspend":true}}'`
- 控制平面大 namespace 导致提交慢
- GC 设置：保持适当 history 以便复盘

## 二十、版本演进

- v3：v1 API K8s GA
- v4：新增 Plugin / Event-driven
- v5 (current)：优化 controller、API、UI

## 二十一、CI 工具链

- **Argo CD**：GitOps 部署
- **Argo Rollouts**：渐进式发布
- **Argo Events**：事件触发
- **Argo Workflows**：批处理 / CI

四件套构成 K8s-native 全栈 DevOps。
