# Chaos Mesh 详解 (CNCF Chaos Engineering Platform)

> Chaos Mesh 是 CNCF Sandbox 项目,K8s 原生的混沌工程平台,功能全面且活跃维护。

## 一、Chaos Mesh 概述

### 1.1 项目简介

```text
项目:     Chaos Mesh
官网:     https://chaos-mesh.org/
GitHub:   https://github.com/chaos-mesh/chaos-mesh
维护:     PingCAP (Tidb 公司)
License:  Apache 2.0
CNCF:     Sandbox 项目
当前版本: 2.7+
```

### 1.2 核心特性

```text
1. K8s 原生
   - CRD 形式定义实验
   - kubectl apply 直接运行
   - 与 K8s 生态深度集成

2. 故障类型丰富 (12+ 种)
   - PodChaos, NetworkChaos, StressChaos
   - DiskChaos, DNSChaos, TimeChaos
   - KernelChaos, JVMChaos
   - AwsChaos, GcpChaos

3. 完整工作流
   - 实验 (Chaos) 定义
   - 计划 (Schedule) 自动执行
   - 工作流 (Workflow) 编排
   - 归档 (Archive) 记录
   - 事件 (Event) 通知

4. 可视化
   - 内置 Dashboard
   - 实验状态实时展示
   - 历史回放

5. 范围控制
   - Namespace, Label 过滤
   - 随机选择 N 个
   - 灰度范围
```

---

## 二、安装部署

### 2.1 系统要求

```text
- K8s 1.18+
- Helm 3.0+
- containerd / Docker / CRI-O
- 内核支持 (Linux 3.10+)
```

### 2.2 Helm 安装 (推荐)

```bash
# 1. 添加 Helm 仓库
helm repo add chaos-mesh https://charts.chaos-mesh.org
helm repo update

# 2. 创建 namespace
kubectl create namespace chaos-mesh

# 3. 安装 Chaos Mesh
helm install chaos-mesh chaos-mesh/chaos-mesh \
  --namespace chaos-mesh \
  --set chaosDaemon.runtime=containerd \
  --set chaosDaemon.socketPath=/run/containerd/containerd.sock

# 4. 验证
kubectl get pods -n chaos-mesh
# chaos-controller-manager
# chaos-daemon (每节点一个)
# chaos-daemon-deployer
# chaos-dashboard (可选)
```

### 2.3 自定义配置

```yaml
# values.yaml
chaosDaemon:
  runtime: containerd
  socketPath: /run/containerd/containerd.sock
  mountPath: /etc/containerd
  privileged: true
  resources:
    requests:
      cpu: 100m
      memory: 100Mi
    limits:
      cpu: 500m
      memory: 500Mi

chaosControllerManager:
  replicas: 3
  resources:
    requests:
      cpu: 200m
      memory: 200Mi

chaosDashboard:
  enabled: true
  service:
    type: NodePort
    nodePort: 30080
```

```bash
helm install chaos-mesh chaos-mesh/chaos-mesh -f values.yaml -n chaos-mesh
```

---

## 三、CRD 类型详解

### 3.1 PodChaos (Pod 故障)

#### pod-kill (杀 Pod)

```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: pod-kill-example
  namespace: chaos-mesh
spec:
  action: pod-kill
  mode: one             # one, all, fixed, fixed-percent, random-max-percent
  selector:
    namespaces:
      - production
    labelSelectors:
      app: web
  scheduler:
    cron: "@every 1m"   # 或 duration: "5m"
  duration: "30s"
```

#### pod-failure (容器失败)

```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: pod-failure
spec:
  action: pod-failure
  mode: all
  selector:
    labelSelectors:
      app: cache
  duration: "3m"
  # 容器持续报错
```

#### pod-delay (启动延迟)

```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: pod-delay
spec:
  action: pod-delay
  mode: one
  selector:
    labelSelectors:
      app: slow-startup
  duration: "2m"
  # 启动延迟
```

### 3.2 NetworkChaos (网络故障)

#### 网络延迟

```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata:
  name: network-delay
spec:
  action: delay
  mode: all
  selector:
    namespaces:
      - production
    labelSelectors:
      app: web
  delay:
    latency: "200ms"
    correlation: "75"   # 0-100, 相关性
    jitter: "50ms"      # 抖动
  duration: "5m"
```

#### 网络丢包

```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata:
  name: network-loss
spec:
  action: loss
  mode: all
  selector:
    labelSelectors:
      app: web
  loss:
    loss: "30"        # 30% 丢包
    correlation: "50"
  duration: "3m"
```

#### 网络分区

```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata:
  name: network-partition
spec:
  action: partition
  mode: all
  selector:
    namespaces:
      - production
    labelSelectors:
      app: web
  direction: both       # from, to, both
  # 让 web 之间的网络完全中断
  duration: "2m"
```

#### 带宽限制

```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata:
  name: network-bandwidth
spec:
  action: bandwidth
  mode: all
  selector:
    labelSelectors:
      app: web
  bandwidth:
    rate: "1mbps"      # 1 Mbps
    limit: 1000
    buffer: 10000
  duration: "5m"
```

### 3.3 StressChaos (资源压力)

```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: StressChaos
metadata:
  name: stress-cpu
spec:
  mode: all
  selector:
    namespaces:
      - production
    labelSelectors:
      app: web
  stressors:
    cpu:
      workers: 2        # 2 个 worker
      load: 80          # 80% 占用
  duration: "5m"
```

```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: StressChaos
metadata:
  name: stress-memory
spec:
  mode: all
  selector:
    labelSelectors:
      app: web
  stressors:
    memory:
      workers: 1
      size: "512Mi"     # 占用 512 MB
    vm:
      workers: 1
      size: "1G"
      # 申请 + 保留内存
  duration: "5m"
```

### 3.4 DiskChaos (磁盘故障)

```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: DiskChaos
metadata:
  name: disk-fill
spec:
  action: fill
  mode: all
  selector:
    labelSelectors:
      app: db
  volumePath: /var/lib/postgresql/data
  fill:
    path: /var/lib/postgresql/data
    size: "10G"           # 填充 10 GB
  duration: "5m"
```

### 3.5 DNSChaos (DNS 故障)

```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: DNSChaos
metadata:
  name: dns-error
spec:
  action: error
  mode: all
  selector:
    namespaces:
      - production
    labelSelectors:
      app: web
  patterns:
    - "*.example.com"     # 该域名解析失败
  duration: "3m"
```

### 3.6 TimeChaos (时钟漂移)

```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: TimeChaos
metadata:
  name: time-skew
spec:
  mode: all
  selector:
    labelSelectors:
      app: scheduled-job
  timeOffset: "-2h"      # 时钟向前跳跃 2 小时
  clockIds:
    - "CLOCK_REALTIME"
    - "CLOCK_MONOTONIC"
  duration: "5m"
```

### 3.7 KernelChaos (内核故障)

```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: KernelChaos
metadata:
  name: kernel-fail
spec:
  mode: all
  selector:
    labelSelectors:
      app: web
  failkfuncs:
    - "tcp_sendmsg"       # 失败的系统调用
  duration: "2m"
```

---

## 四、范围选择

### 4.1 mode 选项

```text
mode 指定影响范围:
  - one:         1 个 Pod
  - all:         所有匹配
  - fixed:       固定 N 个
  - fixed-percent: 固定百分比
  - random-max-percent: 随机最大百分比
```

```yaml
# 杀 50% 的 Pod
spec:
  mode: fixed-percent
  modeValue: "50"
  selector:
    labelSelectors:
      app: web

# 杀 1-3 个随机 Pod
spec:
  mode: random-max-percent
  modeValue: "30"
  selector:
    labelSelectors:
      app: web
```

### 4.2 selector 灵活过滤

```yaml
selector:
  namespaces:
    - production
    - staging
  labelSelectors:
    app: web
    tier: frontend
  # K8s 1.21+ 还有 pod 字段
  pods:
    - production/web-1
    - production/web-2
```

---

## 五、Scheduler (计划任务)

### 5.1 定时执行实验

```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: scheduled-chaos
spec:
  action: pod-kill
  mode: one
  selector:
    labelSelectors:
      app: web
  scheduler:
    cron: "@every 5m"     # cron 表达式
    type: Cron
  duration: "30s"
  # 或者: scheduler:
  #        type: Continuous
  #        duration: "1h"
  #        # 持续 1 小时, 持续执行故障
```

### 5.2 Cron 表达式

```text
@every 30s     # 每 30 秒
@every 5m      # 每 5 分钟
0 */1 * * *   # 每小时
0 0 * * *     # 每天 0 点
```

---

## 六、Workflow (工作流)

### 6.1 串行工作流

```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: Workflow
metadata:
  name: workflow-serial
  namespace: chaos-mesh
spec:
  entry: start
  templates:
  - name: start
    templateType: Serial
    duration: 30s
    children:
    - cpu-stress
    - network-delay
    - pod-kill
  - name: cpu-stress
    type: StressChaos
    duration: 60s
    stressors:
      cpu:
        workers: 1
        load: 80
  - name: network-delay
    type: NetworkChaos
    duration: 60s
    delay:
      latency: 100ms
  - name: pod-kill
    type: PodChaos
    duration: 30s
    action: pod-kill
```

### 6.2 并行工作流

```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: Workflow
metadata:
  name: workflow-parallel
spec:
  entry: start
  templates:
  - name: start
    templateType: Parallel
    children:
    - chaos-pod
    - chaos-network
    - chaos-cpu
  - name: chaos-pod
    type: PodChaos
    duration: 60s
    action: pod-kill
  - name: chaos-network
    type: NetworkChaos
    duration: 60s
    delay:
      latency: 200ms
  - name: chaos-cpu
    type: StressChaos
    duration: 60s
    stressors:
      cpu:
        workers: 1
        load: 90
```

### 6.3 复杂工作流 (条件分支)

```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: Workflow
metadata:
  name: conditional-workflow
spec:
  entry: check-status
  templates:
  - name: check-status
    templateType: Suspend
  - name: success-task
    type: PodChaos
    duration: 30s
    action: pod-kill
  - name: failure-task
    type: NetworkChaos
    duration: 30s
    delay:
      latency: 1000ms
```

---

## 七、Schedule (定时任务)

```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: Schedule
metadata:
  name: weekly-chaos
  namespace: chaos-mesh
spec:
  schedule: "0 2 * * 0"     # 每周日 2 点
  type: PodChaos
  historyLimit: 5
  concurrencyPolicy: Forbid  # Forbid / Allow
  workflow:
    entry: start
    templates:
    - name: start
      templateType: Serial
      children: [chaos-pod, chaos-network]
    - name: chaos-pod
      type: PodChaos
      duration: 30s
      action: pod-kill
    - name: chaos-network
      type: NetworkChaos
      duration: 30s
      delay:
        latency: 100ms
```

---

## 八、事件 (Event) 与告警

### 8.1 ChaosEvent

```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: EventWatcherTemplate
metadata:
  name: chaos-event-watcher
  namespace: chaos-mesh
spec:
  rule:
  - selector: "namespace in ('production', 'staging')"
    event: ["pod_kill", "network_delay", "cpu_stress"]
  receive:
    - type: HTTP
      url: "http://alertmanager:9093/api/v1/alerts"
      template: |
        {
          "labels": {
            "alertname": "ChaosExperiment",
            "severity": "info"
          },
          "annotations": {
            "summary": "Chaos 实验执行: {{.Event}}"
          }
        }
```

### 8.2 集成 Alertmanager

```yaml
# Alertmanager 配置接收 Chaos 告警
- name: 'chaos-experiments'
  matchers:
  - alertname: "ChaosExperiment"
  receiver: 'chaos-team'
```

---

## 九、归档 (Archive)

```text
Chaos Mesh 自动归档所有实验:
  - 实验开始时间
  - 实验结束时间
  - 实验配置
  - 实验结果 (注入点、恢复状态)
  - 关联的 K8s 事件
  - 故障事件 (POD KILLED, NETWORK DELAYED 等)

保留时间:
  - spec.historyLimit: 历史保留数
  - 默认 5 个
```

```bash
# 查看归档
kubectl get events -n chaos-mesh --field-selector involvedObject.kind=PodChaos

# 查看实验详情
kubectl describe podchaos pod-kill -n chaos-mesh

# 查看故障事件
kubectl get events --field-selector reason=ChaosInjected
```

---

## 十、Dashboard

### 10.1 访问 Dashboard

```bash
# 默认 NodePort 方式
kubectl get svc chaos-daemon -n chaos-mesh
# NAME          TYPE       CLUSTER-IP   EXTERNAL-IP   PORT(S)
# chaos-dashboard  NodePort  10.96.x.x    <none>        2333:30080/TCP

# 访问
http://<node-ip>:30080
```

### 10.2 Dashboard 功能

```text
1. 实验列表
   - 查看所有 Chaos 资源
   - 按 namespace, type 过滤
   
2. 实验详情
   - 配置预览
   - 实时状态
   - 关联资源

3. 归档回放
   - 历史实验
   - 详细信息
   - 时间线

4. Workflow 编辑
   - 图形化编排
   - 拖拽式设计

5. 监控面板
   - 实验执行情况
   - 系统响应指标
   - 故障事件
```

---

## 十一、实战案例

### 11.1 Redis 主节点故障演练

```yaml
# 1. 启动实验
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: redis-master-fail
  namespace: chaos-mesh
spec:
  action: pod-kill
  mode: one
  selector:
    namespaces:
      - production
    labelSelectors:
      app: redis
      role: master
  duration: "5m"
  scheduler:
    cron: "@every 1h"     # 每小时一次
```

```bash
# 2. 执行期间观察

# Redis 监控
redis-cli -h redis-replica INFO replication

# 业务影响
watch -n 1 "curl -s http://api/business-metrics | jq .error_rate"

# Sentinel 切换状态
redis-cli -h redis-sentinel SENTINEL get-master-addr-by-name mymaster
```

### 11.2 数据库慢响应演练

```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata:
  name: mysql-slow
  namespace: chaos-mesh
spec:
  action: delay
  mode: all
  selector:
    namespaces:
      - production
    labelSelectors:
      app: mysql
  delay:
    latency: "500ms"
    correlation: "100"
    jitter: "100ms"
  duration: "10m"
```

### 11.3 节点故障演练

```yaml
# Chaos Mesh 不能直接杀 K8s 节点
# 用 Cordoning + Drain 模拟
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: node-down
spec:
  action: pod-kill
  mode: all
  selector:
    labelSelectors:
      app: web
    # 同时可设置 nodeSelector
  duration: "10m"
```

```bash
# 配合手动节点模拟
kubectl cordon node-1
kubectl drain node-1 --ignore-daemonsets --delete-emptydir-data
```

---

## 十二、核心要点速记

### Chaos Mesh 核心 CRD

```text
PodChaos:      Pod 故障
NetworkChaos:  网络故障
StressChaos:   CPU/内存压力
DiskChaos:     磁盘故障
DNSChaos:      DNS 故障
TimeChaos:     时钟漂移
KernelChaos:   内核故障
JVMChaos:      JVM 故障
AwsChaos:      AWS 故障
GcpChaos:      GCP 故障
```

### 范围选择

```text
mode: one / all / fixed / fixed-percent / random-max-percent
selector: namespaces + labelSelectors
```

### 核心命令

```bash
# 安装
helm install chaos-mesh chaos-mesh/chaos-mesh -n chaos-mesh

# 创建实验
kubectl apply -f pod-kill.yaml

# 查看实验
kubectl get podchaos

# 查看归档
kubectl describe podchaos pod-kill

# 删除
kubectl delete podchaos pod-kill
```

### 完整工作流

```text
Chaos (单次实验) 
  → Schedule (定时)
  → Workflow (编排多个)
  → Archive (历史)
  → EventWatcher (告警)
```

### 实战要点

```text
1. 生产先在测试环境演练
2. 范围从小开始 (1 个实例)
3. 业务低峰期执行
4. 准备回滚方案
5. 监控实验过程
6. 总结并改进
```

### 与其他工具对比

```text
Chaos Mesh:  K8s 原生, CRD 形式
ChaosBlade:  主机/容器/K8s 多级, CLI 命令
Litmus:     实验库丰富, ChaosEngine
Gremlin:    商业 SaaS, 全面
```

---

## 参考

- **Chaos Mesh 官方**: https://chaos-mesh.org/
- **Chaos Mesh 文档**: https://chaos-mesh.org/docs/
- **GitHub**: https://github.com/chaos-mesh/chaos-mesh
- **示例库**: https://github.com/chaos-mesh/chaos-mesh/tree/master/examples
- **CNCF 项目**: https://www.cncf.io/projects/chaos-mesh/
- **Chaos Mesh Slack**: https://cloud-native.slack.com/archives/C0233E8SGU3
- **实战指南**: https://chaos-mesh.org/docs/simulate-pod-chaos-on-kubernetes/
