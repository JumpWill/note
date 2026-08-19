# Litmus 详解 (CNCF Chaos Engineering)

> Litmus 是 CNCF Incubating 项目,提供丰富的故障实验库和强大的 Web UI 平台。

## 一、Litmus 概述

### 1.1 项目简介

```text
项目:    LitmusChaos
官网:    https://litmuschaos.io/
GitHub:  https://github.com/litmuschaos/litmus
维护:    MayaData
License: Apache 2.0
CNCF:    Incubating 项目
当前版本: 3.x
```

### 1.2 核心特性

```text
1. 丰富的实验库 (ChaosHub)
   - 50+ 预定义实验
   - 可共享 (类似镜像仓库)
   - 持续社区贡献

2. Web UI 平台 (Litmus Portal)
   - 实验编排
   - 实时监控
   - 报告生成
   - GitOps 集成

3. K8s 原生
   - CRD 形式
   - 多租户
   - 命名空间隔离

4. RBAC
   - 细粒度权限
   - 团队协作
   - 审批流程

5. ChaosCenter
   - 实验管理
   - 调度执行
   - 报告分析
```

---

## 二、核心概念

### 2.1 核心 CRD 资源

```text
1. ChaosExperiment
   故障实验定义 (YAML)
   描述: 什么故障, 怎么注入

2. ChaosEngine
   实验运行实例
   绑定到目标 (app info)
   调度方式 (now / schedule)

3. ChaosResult
   实验结果
   verdict: pass / fail

4. ChaosHub
   实验共享仓库 (Git Repo)
   团队共享实验模板

5. ChaosSchedule
   定时调度实验

6. ChaosScenario
   多实验编排
   串行 / 并行
```

### 2.2 实验生命周期

```text
1. 选择实验 (从 ChaosHub 或自定义)
2. 创建 ChaosEngine (绑定目标)
3. 实验调度
4. 故障注入
5. 监控与采集
6. 结果判定 (verdict)
7. 实验归档
8. 报告生成
```

---

## 三、安装部署

### 3.1 系统要求

```text
- K8s 1.17+
- Helm 3.0+
- 至少 3 个节点 (生产)
- 存储 (etcd 后端)
- RBAC 启用
```

### 3.2 Helm 安装

```bash
# 1. 添加仓库
helm repo add litmuschaos https://litmuschaos.github.io/litmus-helm/
helm repo update

# 2. 创建 namespace
kubectl create namespace litmus

# 3. 安装
helm install litmus litmuschaos/litmus \
  --namespace litmus \
  --create-namespace \
  --set portal.frontend.service.type=NodePort \
  --set portal.frontend.service.nodePort=30090

# 4. 验证
kubectl get pods -n litmus
# chaos-litmus-portal-frontend
# chaos-litmus-portal-backend
# chaos-litmus-auth-server
# chaos-litmus-event-tracker
# chaos-litmus-workflow-controller
# chaos-runner
```

### 3.3 访问 UI

```bash
# 获取端口
kubectl get svc chaos-litmus-portal-frontend -n litmus
# 默认 NodePort 30091

# 访问
http://<node-ip>:30091
# 默认账号: admin / litmus
```

---

## 四、ChaosHub (实验库)

### 4.1 官方实验库

```text
GitHub: https://github.com/litmuschaos/chaos-charts

实验分类:

Pod:
  - pod-delete
  - pod-cpu-hog
  - pod-memory-hog
  - pod-network-latency
  - pod-network-loss
  - pod-disk-fill
  - pod-cpu-burn
  - container-kill

Network:
  - network-loss
  - network-latency
  - network-duplication
  - network-corruption
  - dns-error

Stress:
  - cpu-stress
  - memory-stress
  - io-stress
  - disk-stress

State:
  - pod-restart
  - container-restart
  - process-kill

Time:
  - time-chaos
```

### 4.2 添加 ChaosHub

```bash
# 添加官方 hub
kubectl apply -f https://raw.githubusercontent.com/litmuschaos/chaos-charts/master/charts/generic/experiments.yaml -n litmus

# 添加自定义 hub
cat <<EOF | kubectl apply -f -
apiVersion: litmuschaos.io/v1alpha1
kind: ChaosHub
metadata:
  name: my-hub
  namespace: litmus
spec:
  scope: Cluster
  charts:
  - name: my-custom-experiment
    version: 1.0.0
    repositoryURL: https://github.com/myorg/chaos-charts
EOF
```

---

## 五、ChaosExperiment (实验定义)

### 5.1 完整示例

```yaml
apiVersion: litmuschaos.io/v1alpha1
kind: ChaosExperiment
metadata:
  name: pod-delete
  namespace: litmus
spec:
  description:
    Kill the pod
  definition:
    scope: Namespaced
  method:
    image: "litmuschaos/go-runner:latest"
    commands:
    - /bin/bash
    - -c
    - |
      kubectl delete pod -n ${{ invocation.experimentObject.metadata.namespace }}
        -l ${{ invocation.experimentObject.spec.labelSelectors }}
        --force=true
      sleep 10
  imagePullPolicy: Always
```

### 5.2 带参数实验

```yaml
apiVersion: litmuschaos.io/v1alpha1
kind: ChaosExperiment
metadata:
  name: pod-cpu-hog
  namespace: litmus
spec:
  description:
    Consume CPU of the target pods
  definition:
    scope: Namespaced
  method:
    image: "litmuschaos/go-runner:latest"
    commands:
    - /bin/bash
    - -c
    - |
      stress-ng --cpu ${{ invocation.experimentObject.parameters.CPU_COUNT }} \
                 --timeout ${{ invocation.experimentObject.parameters.DURATION }}
  imagePullPolicy: Always
  definition:
    scope: Cluster
  kind: Experiment
```

### 5.3 完整实验文件结构

```yaml
apiVersion: litmuschaos.io/v1alpha1
kind: ChaosExperiment
metadata:
  name: experiment-name
  namespace: litmus
spec:
  description: "实验描述"
  definition:
    scope: Cluster | Namespaced
  auth:
    # IAM 角色
  rank: 1  # 调度顺序
  version: 1.0.0
  method:
    image: "image:tag"
    commands:
    - 命令列表
    - 可用变量:
      - invocation.experimentObject.metadata.namespace
      - invocation.experimentObject.spec.labelSelectors
      - invocation.experimentObject.parameters.PARAM_NAME
    imagePullPolicy: IfNotPresent
    entrypoint:  # 可选
    args:
    - 可选参数
  resources:
    requests:
      cpu: 100m
      memory: 100Mi
    limits:
      cpu: 500m
      memory: 500Mi
```

---

## 六、ChaosEngine (运行引擎)

### 6.1 基础引擎

```yaml
apiVersion: litmuschaos.io/v1alpha1
kind: ChaosEngine
metadata:
  name: pod-delete-engine
  namespace: production
spec:
  appinfo:
    appkind: deployment
    applabel: app=nginx
    appns: production
  chaosServiceAccount: litmus-admin
  experiments:
  - name: pod-delete
```

### 6.2 完整引擎

```yaml
apiVersion: litmuschaos.io/v1alpha1
kind: ChaosEngine
metadata:
  name: my-chaos
  namespace: production
spec:
  # 应用信息 (实验目标)
  appinfo:
    appkind: deployment          # deployment / statefulset / daemonset
    applabel: app=nginx,env=prod
    appns: production

  # 混沌服务账号
  chaosServiceAccount: chaos-admin

  # 监控服务账号
  jobsCleanUpPolicy: retain   # retain / delete

  # 实验列表
  experiments:
  - name: pod-delete
  - name: pod-cpu-hog
  - name: pod-network-latency
```

### 6.3 调度策略

```yaml
apiVersion: litmuschaos.io/v1alpha1
kind: ChaosEngine
metadata:
  name: scheduled-chaos
spec:
  appinfo:
    appkind: deployment
    applabel: app=nginx
  chaosServiceAccount: chaos-admin
  experiments:
  - name: pod-delete
  schedule:
    type: now                 # now (立即) / in (延迟) / cron
    when: ""                  # in: "5m" / cron: "0 2 * * *"
    historyLimit: 3
```

---

## 七、ChaosResult (实验结果)

### 7.1 查看结果

```bash
# 列出所有实验结果
kubectl get chaosresults -A

# 查看特定结果详情
kubectl describe chaosresult <name> -n production
```

### 7.2 结果字段

```yaml
status:
  experimentstatus:
    phase: Completed        # Running / Completed / Failed
    verdict: Pass            # Pass / Fail
  probesstatus:
  - name: check-pod-status
    status: Pass
  - name: check-app-health
    status: Fail              # 实验失败,系统暴露脆弱点
  experimentpod: chaos-pod-xxx
  verfication:                # 验证结果
    result:
      verdict: Pass
      description: "Application remained healthy"
```

---

## 八、ChaosSchedule (定时调度)

```yaml
apiVersion: litmuschaos.io/v1alpha1
kind: ChaosSchedule
metadata:
  name: weekly-pod-kill
  namespace: production
spec:
  schedule:
    type: cron
    cron:
      schedule: "0 2 * * 0"     # 每周日 2 点
      timezone: "Asia/Shanghai"
      startingDeadlineSeconds: 60
  chaosEngine: my-chaos-engine
  historyLimit: 5
  concurrencyPolicy: Forbid  # Forbid / Allow
```

---

## 九、ChaosScenario (场景编排)

```yaml
apiVersion: litmuschaos.io/v1alpha1
kind: ChaosScenario
metadata:
  name: resilience-test
  namespace: litmus
spec:
  description: "Application resilience scenario"
  tasks:
  - name: pod-kill
    taskType: chaosengine
    engine: pod-kill-engine
  - name: network-delay
    taskType: chaosengine
    engine: network-delay-engine
    dependsOn: [pod-kill]
  - name: final-check
    taskType: probe
    dependsOn: [network-delay]
```

---

## 十、ChaosProbe (健康探测)

```yaml
apiVersion: litmuschaos.io/v1alpha1
kind: ChaosProbe
metadata:
  name: app-health-check
  namespace: production
spec:
  type: httpProbe
  url: http://my-app/health
  insecureSkipVerify: true
  interval: 5
  timeout: 3
  retry: 3
  probeTimeout: 30
```

```yaml
# Kubernetes 探针
spec:
  type: k8sProbe
  verb: get
  resource: pods
  labelSelectors: app=nginx
  fieldSelector: status.phase=Running
  timeout: 5
  retry: 3
```

---

## 十一、Litmus Portal (Web UI)

### 11.1 功能

```text
1. 实验探索
   - 浏览 ChaosHub
   - 搜索实验
   - 预定义模板

2. 实验编排
   - 选择实验
   - 配置参数
   - 设置调度
   - 配置 Probe

3. 实验监控
   - 实时状态
   - 故障事件
   - 系统响应
   - Probe 结果

4. 报告生成
   - 实验详情
   - 时间线
   - 失败原因
   - 改进建议

5. RBAC
   - 用户管理
   - 团队协作
   - 审批流程

6. 集成
   - GitOps (ArgoCD)
   - 监控 (Prometheus)
   - 通知 (Slack, Teams)
```

### 11.2 RBAC 权限

```yaml
# Role
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: production
  name: chaos-experimenter
rules:
- apiGroups: ["litmuschaos.io"]
  resources: ["chaosengines", "chaosexperiments"]
  verbs: ["get", "list", "create", "delete"]
- apiGroups: [""]
  resources: ["pods", "services"]
  verbs: ["get", "list"]
```

---

## 十二、实战案例

### 12.1 Pod 杀演练

```yaml
# 1. ChaosHub
apiVersion: litmuschaos.io/v1alpha1
kind: ChaosHub
metadata:
  name: litmus
  namespace: litmus
spec:
  scope: Cluster
  charts:
  - name: pod-delete
    version: 1.0.0
    repositoryURL: https://github.com/litmuschaos/chaos-charts
```

```yaml
# 2. ChaosEngine
apiVersion: litmuschaos.io/v1alpha1
kind: ChaosEngine
metadata:
  name: pod-delete-test
  namespace: production
spec:
  appinfo:
    appkind: deployment
    applabel: app=nginx
  chaosServiceAccount: chaos-admin
  experiments:
  - name: pod-delete
```

```bash
# 3. 应用
kubectl apply -f chaosengine.yaml

# 4. 监控
watch kubectl get chaosresult -n production

# 5. 完成后查看结果
kubectl get chaosresult pod-delete-test -n production -o yaml
```

### 12.2 网络延迟演练

```yaml
apiVersion: litmuschaos.io/v1alpha1
kind: ChaosEngine
metadata:
  name: network-delay-test
  namespace: production
spec:
  appinfo:
    appkind: deployment
    applabel: app=api
  chaosServiceAccount: chaos-admin
  experiments:
  - name: pod-network-latency
    spec:
      components:
        env:
        - name: NETWORK_LATENCY
          value: "2000"      # 2 秒
        - name: CONTAINER_RUNTIME
          value: containerd
        - name: SOCKET_PATH
          value: /run/containerd/containerd.sock
        - name: NETWORK_INTERFACE
          value: eth0
        - name: TARGET_CONTAINER
          value: api
```

### 12.3 数据库慢响应演练

```yaml
apiVersion: litmuschaos.io/v1alpha1
kind: ChaosEngine
metadata:
  name: mysql-latency
  namespace: production
spec:
  appinfo:
    appkind: statefulset
    applabel: app=mysql
  chaosServiceAccount: chaos-admin
  experiments:
  - name: pod-network-latency
    spec:
      components:
        env:
        - name: NETWORK_LATENCY
          value: "500"
        - name: TARGET_CONTAINER
          value: mysql
```

---

## 十三、集成与扩展

### 13.1 GitOps 集成

```yaml
# ArgoCD Application
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: litmus
spec:
  source:
    repoURL: https://github.com/myorg/chaos-experiments
    path: experiments/
  destination:
    server: https://kubernetes.default.svc
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

### 13.2 Prometheus 集成

```bash
# chaos-exporter 暴露实验指标
kubectl apply -f https://raw.githubusercontent.com/litmuschaos/litmus/master/monitoring/chaos-exporter.yaml
```

```promql
# 实验执行状态
chaos_engine_status
chaos_experiment_status
chaos_result_verdict
```

### 13.3 通知集成

```yaml
# Slack 通知 (Litmus Slack integration)
apiVersion: v1
kind: ConfigMap
metadata:
  name: slack-config
  namespace: litmus
data:
  SLACK_BOT_TOKEN: "xoxb-xxx"
  SLACK_CHANNEL: "#chaos-alerts"
  CHAOS_UI_URL: "https://litmus.example.com"
```

---

## 十四、核心要点速记

### Litmus 核心 CRD

```text
ChaosExperiment:  故障实验定义
ChaosEngine:      实验运行实例
ChaosResult:      实验结果
ChaosHub:         实验仓库
ChaosSchedule:    定时任务
ChaosScenario:    场景编排
ChaosProbe:       健康探测
```

### 实验库 (ChaosHub)

```text
Pod:       pod-delete, pod-cpu-hog, pod-memory-hog
Network:   network-loss, network-latency, dns-error
Stress:    cpu-stress, memory-stress
State:     container-kill, process-kill
Time:      time-chaos
Disk:      disk-fill
```

### 核心流程

```text
1. 创建 ChaosHub (从 Git)
2. 选择实验
3. 创建 ChaosEngine (绑定目标)
4. 调度执行
5. 监控 ChaosProbe
6. 查看 ChaosResult
7. 总结改进
```

### 快速上手

```bash
# 安装
helm install litmus litmuschaos/litmus -n litmus

# 访问 UI
http://<node-ip>:30091
# admin / litmus

# 准备实验
# 添加 ChaosHub
# 选实验
# 配 ChaosEngine
# 跑实验
```

### 与 Chaos Mesh 对比

```text
Chaos Mesh: K8s 原生, CRD 形式
  - 内置 12+ 种故障类型
  - 完全 K8s 风格
  - CNCF Sandbox

Litmus: 实验库 + Web UI
  - 50+ 预定义实验
  - 强大 UI 平台
  - 实验共享 (ChaosHub)
  - CNCF Incubating
```

### 选择建议

```text
- 想要丰富实验库 → Litmus
- 想要完整 UI 平台 → Litmus
- 想要纯 K8s 集成 → Chaos Mesh
- 中文支持 → ChaosBlade
```

---

## 参考

- **Litmus 官方**: https://litmuschaos.io/
- **Litmus 文档**: https://docs.litmuschaos.io/
- **GitHub**: https://github.com/litmuschaos/litmus
- **ChaosHub 示例**: https://github.com/litmuschaos/chaos-charts
- **CNCF 项目**: https://www.cncf.io/projects/litmuschaos/
- **Slack**: https://kubernetes.slack.com/archives/C0196Q5NZQM
- **Litmus 教程**: https://docs.litmuschaos.io/docs/getting-started/
