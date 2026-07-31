# Tekton

CNCF 毕业的 K8s 原生 CI/CD 框架，本质是 K8s CRD + Controller，原则：每个 Pipeline Step = 一个 Pod。原 [Knative Build] 演化而来。

## 一、定位

- Cloud-native CI / CD
- 由独立 Task / Pipeline 装配，可重用的 build block
- 不绑定 Git / Docker / Jenkins 模型
- 适合多语言、多云、K8s 上的 CI 平台
- 与 Jenkins 集成友好（Jenkins Tekton Plugin）

## 二、核心 CRD

| CRD | 含义 |
| --- | ---- |
| **Task** | 一组有序 Step |
| **Step** | 一个 Container |
| **Pipeline** | 一组有序 Task |
| **PipelineRun** | Pipeline 的一次执行 |
| **TaskRun** | Task 的一次执行 |
| **PipelineResource** (Deprecated) | 资源（Git / Image / Storage），v1 后被替代 |
| **Workspace** | Task 间共享目录 |
| **Results** | Step / Task 的输出 |
| **Params** | 参数 |
| **Conditions** | 跳过 Task 的条件（v1） |
| **Resolvers** | Hub / Git / Cluster Resolver 拉取 Pipeline |
| **Triggers** | Tekton Triggers（独立项目） |
| **Dashboard** | Web UI |

## 三、Task 示例

```yaml
apiVersion: tekton.dev/v1
kind: Task
metadata:
  name: buildah
spec:
  params:
    - name: IMAGE
      type: string
    - name: CONTEXT
      type: string
  steps:
    - name: build
      image: quay.io/buildah/stable
      args: ["bud", "--context", "$(params.CONTEXT)", "-t", "$(params.IMAGE)"]
```

## 四、Pipeline 示例

```yaml
apiVersion: tekton.dev/v1
kind: Pipeline
metadata:
  name: build-and-push
spec:
  workspaces:
    - name: source
  params:
    - name: image
      type: string
    - name: git-rev
      type: string
      default: main
  tasks:
    - name: fetch
      taskRef:
        name: git-clone
      workspaces:
        - name: output
          workspace: source
      params:
        - name: url
          value: https://github.com/example/repo
        - name: revision
          value: $(params.git-rev)
    - name: build
      runAfter: [fetch]
      taskRef:
        name: buildah
      workspaces:
        - name: source
          workspace: source
      params:
        - name: IMAGE
          value: $(params.image)
```

## 五、PipelineRun

```yaml
apiVersion: tekton.dev/v1
kind: PipelineRun
metadata:
  generateName: build-run-
spec:
  pipelineRef:
    name: build-and-push
  params:
    - name: image
      value: ghcr.io/example/app
    - name: git-rev
      value: main
  workspaces:
    - name: source
      persistentVolumeClaim:
        claimName: source-pvc
```

```bash
kubectl create -f run.yaml
tkn pipelinerun logs build-run-xxx -f
```

## 六、Workspace

- Task / Pipeline 间共享目录
- 类型：

| Type | 含义 |
| ---- | ---- |
| `emptyDir` | 临时 |
| `pvc` | 持久化卷 |
| `configMap` | 配置 |
| `secret` | 秘密 |
| `volumeClaimTemplate` | 动态 PVC |

适合：源代码拉取 → 构建 → 测试 → 镜像构建 / 推送。

## 七、Results

代替 XCom：

```yaml
results:
  - name: digest
    description: image digest
```

步骤中：

```yaml
args: ["buildah","push",...]
script: |
  #!/bin/sh
  echo -n "$(buildah push --digestfile /tmp/d ...)" > /tekton/results/digest
```

下游 Task 使用 `$(tasks.<name>.results.<name>)`。

## 八、Conditions

跳过 Task：

```yaml
when:
  - input: "$(tasks.fetch.results.commit)"
    operator: notin
    values: ["skip-build"]
```

## 九、Resolvers（v1 重点）

允许 Pipeline / Task 从其他位置拉取：

```yaml
spec:
  pipelineRef:
    resolver: hub
    params:
      - name: name
        value: golang-build
      - name: version
        value: "0.5"
```

Resolvers：

- **Hub**：Tekton Hub
- **Git**：Git Repo
- **Cluster**：集群内 ClusterTask
- **Bundle**：OCI 镜像

## 十、Tekton Triggers

事件驱动：

- EventListener（CRD）
- TriggerBinding / TriggerTemplate
- Interceptors（验证 / 富化）

```yaml
apiVersion: triggers.tekton.dev/v1beta1
kind: EventListener
metadata:
  name: github-pr
spec:
  triggers:
    - name: pr-trigger
      interceptors:
        - ref:
            name: github
          params:
            - name: eventTypes
              value: ["pull_request"]
      bindings:
        - ref: github-pr-binding
      template:
        ref: pipeline-template
```

GitHub / GitLab / Bitbucket 集成。

## 十一、安全

- Secret 通过 ServiceAccount 注入
- TaskRun / PipelineRun ServiceAccount 字段
- 单独 RBAC
- TaskRun pod 内凭据仍然在 secret 内

## 十二、监控 / Tracing

- 默认 metrics：`tekton.dev/v1` Tasks / Pipelines / TaskRuns 自带 metrics
- OpenTelemetry 已支持
- Grafana + Prometheus

## 十三、tektoncd CLI

```bash
tkn pipeline list
tkn task list
tkn pipelinerun logs <run>
tkn pipelinerun cancel <run>
```

## 十四、Tekton 与 Argo 对比

| 维度 | Tekton | Argo Workflows |
| ---- | ------ | -------------- |
| 主要场景 | CI / CD | 通用 Workflow / 批 / ML |
| 模型 | Pipeline=Task | Workflow=Template DAG/Step |
| DAG 表达 | runAfter / when | dependencies DAG |
| 触发 | Triggers / Sink | Argo Events |
| UI | Tekton Dashboard | Argo Server UI |
| Resolver | Hub / Git / Bundle | Templates / Cluster |
| 学习曲线 | 中 | 中 |
| 集成 | Jenkins / GitLab / Knative | Argo CD / Events |
| 适合 | CI/CD 流（GitOps 拼 CI 部分） | Data / ML / 一切 |

## 十五、典型用法

### 1. Git Push → Build → Test → Image

```text
trigger push (Triggers)
  → fetch source
  → unit test
  → build image
  → push image
  → update deploy.yaml arg
```

### 2. 任意 Pipeline 复用

在 Hub 拉 `golang-build`：

```yaml
resolver: hub
params:
  - name: name
    value: golang-build
  - name: version
    value: "0.7"
```

## 十六、最佳实践

- **Task 颗粒度小**：可重用
- **Result 共享**：用 results 而非 XCom 等临时方案
- **Workspace 传递**：通过 PVC 或 emptyDir 共享数据
- **Trusted Resources**：v1 必备，防止供应链
- **镜像提权**：禁用 STEP 提权（`securityContext: allowPrivilegeEscalation: false`）
- **Audit**：通过 Triggers 的 Interceptor 做验证

## 十七、Tekton 与 Jenkins / GitHub Actions

| 特性 | Tekton | Jenkins | GHA |
| ---- | ------ | ------- | --- |
| 云原生 | 强 | 中 | 中 |
| 容器化 | 全 | 部分 | 全 |
| 插件 | 主要是 Task 资源 | 巨量生态 | Action 生态 |
| 部署 | K8s Operator | Server / Agent | 托管 |
| 适合 | 大团队自建 CI | 复杂 Pipeline | GitHub 项目 |

## 十八、v1 重要变化

- `PipelineResource` 移除
- Conditions：替代 when
- Trusted Resources：必须校验
- Bundle Resolver + Hub v2

升级路径：v0.50 → v1 注意 YAML breaking 变更。

## 十九、典型项目

- **Pipelines as Code**：基于 Tekton + GitOps
- **OpenShift Pipelines**：OpenShift 自带 Tekton
- **Jenkins X**：基于 Tekton 插件
- **Knative Build**：前身
