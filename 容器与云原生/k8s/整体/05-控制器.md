# Deployment、StatefulSet 与其他工作负载 (Workloads)

> 本章系统讲解 K8s 的核心工作负载控制器:Deployment (无状态)、StatefulSet (有状态)、DaemonSet、Job/CronJob。

## 一、Workload 控制器总览

```text
K8s 工作负载控制器 (按创建 Pod 方式):

┌─────────────────┬─────────────────┐
│  Deployment     │  StatefulSet   │
│  (无状态应用)    │  (有状态应用)    │
│  滚动升级、回滚  │  稳定网络标识    │
│  最常用          │  数据库、MQ     │
└─────────────────┴─────────────────┘

┌─────────────────┬─────────────────┐
│  DaemonSet      │  Job/CronJob    │
│  (节点守护进程)  │  (批处理任务)    │
│  每个节点一个    │  一次性/定时     │
│  日志/监控收集   │  数据迁移/批处理 │
└─────────────────┴─────────────────┘

所有控制器都管理 Pod,但适用场景不同
```

---

## 二、Deployment (核心)

### 2.1 Deployment 概念

**Deployment** 是最常用的 K8s 控制器,用于部署无状态应用。

```text
Deployment 特点:
1. 管理 ReplicaSet (自动)
2. 滚动升级 + 回滚
3. 副本数动态调整 (HPA)
4. 暂停/恢复部署
5. 蓝绿/金丝雀发布
```

### 2.2 Deployment 完整定义

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-deployment
  namespace: production
  labels:
    app: nginx
    tier: web
  annotations:
    description: "Nginx web server"

spec:
  # 副本数
  replicas: 3

  # 选择器 (必须匹配 template.labels)
  selector:
    matchLabels:
      app: nginx
    matchExpressions:
    - key: tier
      operator: In
      values: ["web", "api"]

  # Pod 模板
  template:
    metadata:
      labels:
        app: nginx
        tier: web
        version: v1.0
      annotations:
        prometheus.io/scrape: "true"
    spec:
      # 副本集约束 (一般不用)
      replicas: 1   # ❌ 不要在 template 中设 replicas

      containers:
      - name: nginx
        image: nginx:1.25
        ports:
        - containerPort: 80
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 500m
            memory: 256Mi
        livenessProbe:
          httpGet:
            path: /
            port: 80
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /
            port: 80
          periodSeconds: 5

      # 升级策略
      strategy:
        type: RollingUpdate      # RollingUpdate / Recreate
        rollingUpdate:
          maxSurge: 1            # 最多多 1 个 Pod (或 25%)
          maxUnavailable: 0      # 最多不可用 0 个 (或 25%)

      # 修订历史限制
      revisionHistoryLimit: 10

      # 进度超时
      progressDeadlineSeconds: 600

  # 暂停 (true = 暂停自动更新)
  paused: false

  # 部署策略
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 25%             # 或具体数字
      maxUnavailable: 25%
```

### 2.3 Deployment 操作

```bash
# 创建
kubectl apply -f deployment.yaml

# 查看
kubectl get deployments
kubectl get deploy             # 简写
kubectl describe deployment nginx-deployment

# 扩缩
kubectl scale deployment nginx --replicas=5
kubectl autoscale deployment nginx --min=2 --max=10 --cpu-percent=80

# 镜像更新
kubectl set image deployment/nginx nginx=nginx:1.26
# 或修改 yaml 后 apply

# 滚动重启
kubectl rollout restart deployment nginx

# 回滚
kubectl rollout undo deployment nginx              # 上一版本
kubectl rollout undo deployment nginx --to-revision=2

# 暂停/恢复 (灰度发布用)
kubectl rollout pause deployment nginx
kubectl set image deployment/nginx nginx=nginx:experimental
kubectl rollout resume deployment nginx

# 查看历史
kubectl rollout history deployment nginx

# 查看状态
kubectl rollout status deployment nginx
```

### 2.4 滚动升级机制

```text
假设 replicas=3, maxSurge=1, maxUnavailable=0

升级前: [Pod1 v1.0] [Pod2 v1.0] [Pod3 v1.0]

步骤 1: 创建新 Pod (maxSurge=1)
   [Pod1 v1.0] [Pod2 v1.0] [Pod3 v1.0] [Pod4 v1.1]
   (总 4 个 Pod, 1 个新版本, 3 个旧版本)

步骤 2: 删除旧 Pod (maxUnavailable=0 保持可用)
   [Pod1 v1.0] [Pod2 v1.0] [Pod3 v1.1] [Pod4 v1.1]
   (确保至少有 3 个可用)

步骤 3: 继续替换
   [Pod1 v1.0] [Pod2 v1.1] [Pod3 v1.1] [Pod4 v1.1]
   [Pod1 v1.1] [Pod2 v1.1] [Pod3 v1.1] [Pod4 v1.1]
   (全部完成升级)
```

### 2.5 蓝绿发布 vs 灰度发布

```text
蓝绿发布 (Blue/Green):
  - 准备两套完全相同的环境 (蓝/绿)
  - 蓝 = 当前生产, 绿 = 新版本
  - 切换流量: Service selector 切换
  
灰度发布 (Canary):
  - 逐步将流量切到新版本
  - 5% → 25% → 50% → 100%
  - 监控指标,无异常继续
```

**蓝绿发布示例**:

```yaml
# 蓝色 (当前)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp-blue
spec:
  replicas: 3
  selector:
    matchLabels:
      app: myapp
      version: blue
  template:
    metadata:
      labels:
        app: myapp
        version: blue
    spec:
      containers:
      - name: app
        image: myapp:1.0

---
# 绿色 (新版本)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp-green
spec:
  replicas: 3
  selector:
    matchLabels:
      app: myapp
      version: green
  template:
    metadata:
      labels:
        app: myapp
        version: green
    spec:
      containers:
      - name: app
        image: myapp:2.0

---
# Service 通过 selector 切换
apiVersion: v1
kind: Service
metadata:
  name: myapp
spec:
  selector:
    app: myapp
    # version: blue   ← 改这一行切换
    version: green
  ports:
  - port: 80
```

**金丝雀发布示例**:

```yaml
# 使用 Istio 实现流量切分
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: myapp
spec:
  hosts:
  - myapp
  http:
  - match:
    - headers:
        canary:
          exact: "true"
    route:
    - destination:
        host: myapp
        subset: v2
  - route:
    - destination:
        host: myapp
        subset: v1
      weight: 95
    - destination:
        host: myapp
        subset: v2
      weight: 5  # 5% 流量到新版本
```

### 2.6 HPA (HorizontalPodAutoscaler)

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: nginx-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: nginx-deployment
  minReplicas: 2
  maxReplicas: 10

  # CPU 利用率目标
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70

  # 内存
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80

  # 行为
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 30
      policies:
      - type: Percent
        value: 100
        periodSeconds: 30
    scaleDown:
      stabilizationWindowSeconds: 300
```

---

## 三、StatefulSet (有状态应用)

### 3.1 为什么需要 StatefulSet

```text
Deployment 不适合有状态应用,因为:
1. Pod 名称随机 (nginx-7d4f5b-x8m2k)
2. 数据存储需要稳定的网络标识
3. 启动顺序有依赖 (主从、leader 选举)

StatefulSet 提供:
1. 稳定的网络标识 (myapp-0, myapp-1, myapp-2)
2. 稳定的持久化存储 (PVC 模板)
3. 有序部署与扩展 (0 → 1 → 2)
4. 有序终止与删除 (n → n-1 → ... → 0)
```

### 3.2 StatefulSet 完整定义

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: mysql
  namespace: production
spec:
  serviceName: mysql-headless   # 必须关联 headless Service
  replicas: 3

  selector:
    matchLabels:
      app: mysql

  template:
    metadata:
      labels:
        app: mysql
    spec:
      containers:
      - name: mysql
        image: mysql:8.0
        ports:
        - containerPort: 3306
        env:
        - name: MYSQL_ROOT_PASSWORD
          valueFrom:
            secretKeyRef:
              name: mysql-secret
              key: password
        volumeMounts:
        - name: data
          mountPath: /var/lib/mysql
        readinessProbe:
          exec:
            command: ["mysqladmin", "ping"]
          initialDelaySeconds: 30
          periodSeconds: 10

  # PVC 模板 (每个 Pod 自动创建独立 PVC)
  volumeClaimTemplates:
  - metadata:
      name: data
      annotations:
        volume.beta.kubernetes.io/storage-class: "fast-ssd"
    spec:
      accessModes: [ "ReadWriteOnce" ]
      storageClassName: "fast-ssd"
      resources:
        requests:
          storage: 100Gi

  # 升级策略
  updateStrategy:
    type: RollingUpdate          # RollingUpdate / OnDelete
    rollingUpdate:
      partition: 0                # 只升级序号 >= 0 的 (灰度)

  # Pod 管理策略
  podManagementPolicy: OrderedReady   # OrderedReady / Parallel
```

### 3.3 Headless Service (StatefulSet 必需)

```yaml
apiVersion: v1
kind: Service
metadata:
  name: mysql-headless
spec:
  clusterIP: None          # headless service
  selector:
    app: mysql
  ports:
  - port: 3306
    targetPort: 3306
```

### 3.4 StatefulSet 操作

```bash
# 查看
kubectl get statefulset
kubectl get sts            # 简写

# Pod 命名规则
# mysql-0, mysql-1, mysql-2 (有序)
kubectl get pods -l app=mysql
# NAME      READY   STATUS    RESTARTS   AGE
# mysql-0   1/1     Running   0          5m
# mysql-1   1/1     Running   0          3m
# mysql-2   1/1     Running   0          1m

# 扩容 (有序,0 → 1 → 2)
kubectl scale statefulset mysql --replicas=5

# 升级 (默认 RollingUpdate)
kubectl rollout status statefulset mysql
kubectl edit statefulset mysql    # 改 image

# 有序删除 (2 → 1 → 0)
kubectl delete statefulset mysql
```

### 3.5 实际应用场景

```text
1. 数据库 (MySQL, PostgreSQL, MongoDB 副本集)
2. 消息队列 (Kafka, RabbitMQ, RocketMQ)
3. 分布式存储 (Ceph, MinIO)
4. 有状态服务 (ZooKeeper, etcd)
5. 大数据集群 (HDFS, HBase)
```

---

## 四、DaemonSet (节点守护进程)

### 4.1 概念

**DaemonSet** 确保每个节点上都运行一个 Pod,适合节点级后台服务。

```text
DaemonSet 用途:
1. 日志收集 (Fluent-bit, Filebeat)
2. 监控导出 (Node Exporter)
3. 网络插件 (Calico, Cilium)
4. 存储守护进程 (ceph, glusterd)
5. 安全 agent (Falco, OSSEC)
```

### 4.2 DaemonSet 定义

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: node-exporter
  namespace: monitoring
spec:
  selector:
    matchLabels:
      app: node-exporter
  template:
    metadata:
      labels:
        app: node-exporter
    spec:
      # 仅在有特定标签的节点运行
      nodeSelector:
        kubernetes.io/os: linux

      # 容忍 master 节点的污点
      tolerations:
      - key: node-role.kubernetes.io/control-plane
        effect: NoSchedule

      containers:
      - name: node-exporter
        image: prom/node-exporter:v1.7.0
        ports:
        - containerPort: 9100
          hostPort: 9100    # 暴露到主机 (DaemonSet 特有)
        volumeMounts:
        - name: proc
          mountPath: /host/proc
          readOnly: true
        - name: sys
          mountPath: /host/sys
          readOnly: true
      volumes:
      - name: proc
        hostPath:
          path: /proc
      - name: sys
        hostPath:
          path: /sys

      # 主机网络 (可选)
      hostNetwork: true
```

### 4.3 DaemonSet 操作

```bash
kubectl get daemonset
kubectl get ds                # 简写

# 查看每个节点上的 Pod
kubectl get pods -n monitoring -o wide -l app=node-exporter
```

---

## 五、Job 与 CronJob

### 5.1 Job (一次性任务)

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: data-migration
spec:
  # 完成任务的总次数
  completions: 1

  # 并行执行数
  parallelism: 1

  # 重试次数
  backoffLimit: 3

  # 活跃时间限制 (超时)
  activeDeadlineSeconds: 3600

  # 完成后保留多少 Pod (查看日志)
  ttlSecondsAfterFinished: 86400  # 保留 1 天

  template:
    metadata:
      labels:
        app: data-migration
    spec:
      restartPolicy: OnFailure     # Job 必须 OnFailure 或 Never
      containers:
      - name: migration
        image: migration:v1.0
        command: ["python", "migrate.py"]
```

### 5.2 CronJob (定时任务)

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: backup-db
spec:
  # Cron 表达式 (分钟 小时 日 月 周)
  schedule: "0 2 * * *"            # 每天凌晨 2 点

  # 时区 (1.27+)
  timeZone: "Asia/Shanghai"

  # 启动截止时间
  startingDeadlineSeconds: 60

  # 任务并发策略
  # Allow: 允许并发 (默认)
  # Forbid: 禁止并发 (跳过)
  # Replace: 替换 (新任务替换旧任务)
  concurrencyPolicy: Forbid

  # 历史保留
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 1

  # 是否挂起
  suspend: false

  # Job 模板
  jobTemplate:
    spec:
      backoffLimit: 2
      ttlSecondsAfterFinished: 86400
      template:
        spec:
          restartPolicy: OnFailure
          containers:
          - name: backup
            image: backup:v1.0
            command: ["/bin/sh", "-c", "mysqldump ... > /backup/db-$(date +\%Y\%m\%d).sql"]
            volumeMounts:
            - name: backup
              mountPath: /backup
          volumes:
          - name: backup
            persistentVolumeClaim:
              claimName: backup-pvc
          restartPolicy: OnFailure
```

### 5.3 Cron 表达式

```text
分 时 日 月 周
*  *  *  *  *

例:
"0 2 * * *"        每天 2:00
"*/5 * * * *"      每 5 分钟
"0 0 * * 0"        每周日 0:00
"0 0 1 * *"        每月 1 日 0:00
"0 9-17 * * 1-5"   工作时间每点 (9-17 点, 周一到周五)
"30 14 1 * *"      每月 1 日 14:30
```

---

## 六、各种 Workload 对比

| 维度 | Deployment | StatefulSet | DaemonSet | Job | CronJob |
|------|-----------|--------------|-----------|-----|----------|
| **用途** | 无状态应用 | 有状态应用 | 节点守护 | 一次性任务 | 定时任务 |
| **Pod 命名** | 随机 | 有序 (0,1,2) | 节点名 | 随机 | 随机 |
| **数据卷** | 共享/无 | 独立 PVC | 主机路径 | 临时 | 临时 |
| **扩缩** | 任意 | 有序 | 自动 | completions | 触发 |
| **滚动升级** | 滚动 | 滚动 (可灰度) | 滚动 | N/A | N/A |
| **典型场景** | Web、API | DB、MQ | 日志、监控 | 数据迁移 | 备份 |
| **副本数** | replicas | replicas | 每节点 1 | completions | 1 (触发) |

---

## 核心要点速记

### Deployment

```text
- 最常用 Workload
- 管理 ReplicaSet
- 滚动升级 + 回滚
- 适合无状态应用
- 三个升级策略:
  - RollingUpdate (默认)
  - Recreate (重建)
  - Blue/Green (蓝绿,需两个 Deployment)
```

### StatefulSet

```text
- 用于有状态应用
- 稳定 Pod 名: name-0, name-1, name-2
- 稳定存储: 每个 Pod 独立 PVC
- 有序部署: 0 → 1 → 2
- 有序删除: 2 → 1 → 0
- 必须配合 Headless Service
```

### DaemonSet

```text
- 每节点一个 Pod
- 新节点加入自动调度
- 适合节点级服务:
  - 日志收集 (Fluent-bit)
  - 监控 (Node Exporter)
  - 网络插件 (Calico)
```

### Job / CronJob

```text
- Job: 一次性任务 (数据迁移)
- CronJob: 定时任务 (备份)
- restartPolicy: OnFailure
- 完成后保留 Pod 用于查看日志
- 并发策略: Allow / Forbid / Replace
```

### Workload 选型

```text
无状态 Web/API → Deployment ✅
数据库 / 消息队列 → StatefulSet ✅
节点级服务 (日志/监控) → DaemonSet ✅
一次性任务 → Job ✅
定时任务 → CronJob ✅
```

---

## 参考

- **Deployment**: https://kubernetes.io/docs/concepts/workloads/controllers/deployment/
- **StatefulSet**: https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/
- **DaemonSet**: https://kubernetes.io/docs/concepts/workloads/controllers/daemonset/
- **Job/CronJob**: https://kubernetes.io/docs/concepts/workloads/controllers/jobs-run-to-completion/
- **HPA**: https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/
