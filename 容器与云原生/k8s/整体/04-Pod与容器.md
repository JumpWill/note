# Pod 与容器 (Pod & Containers)

> Pod 是 K8s 调度的最小单元,本章讲解 Pod 的设计理念、生命周期、容器配置与最佳实践。

## 一、Pod 概述

### 1.1 什么是 Pod

**Pod** 是 K8s 创建和管理的最小可部署单元,一个 Pod 代表集群中一个运行的进程实例。

```text
Pod = 一组容器(1+ 个)的封装
    + 共享网络命名空间
    + 共享存储卷
    + 共享生命周期

┌─────────────────── Pod ───────────────────┐
│                                          │
│   ┌──────────┐      ┌──────────┐         │
│   │ Container │      │ Container │         │
│   │  (App)    │      │ (Sidecar) │         │
│   │  eth0 ◄──┴──────┴► eth0            │  ← 共享网络 (localhost 互通)
│   │  /data ◄──┴──────┴► /data           │  ← 共享存储卷
│   └──────────┘      └──────────┘         │
│                                          │
└──────────────────────────────────────────┘
```

### 1.2 为什么需要 Pod

```text
直接调度容器的缺点:
1. 容器通常需要"主从配对" (主容器 + 日志/监控 sidecar)
2. 主从容器需协调 (如共享网络、共享卷)
3. K8s 调度器不应关心容器间关系

Pod 的解决方案:
- 把"紧密协作"的多个容器打包成 Pod
- Pod 内容器共享网络、存储
- K8s 调度 Pod 而非容器
```

### 1.3 Pod 特性

```text
1. 共享网络命名空间
   - 共享 IP 地址
   - 共享端口空间
   - 容器间通过 localhost 通信
   - Pod 内容器可见其他容器的网络

2. 共享存储卷
   - Pod 内所有容器可挂载同一个 Volume
   - 适合共享配置文件、数据

3. 共享生命周期
   - 同时被创建/启动
   - 同时被调度到同一节点
   - 同时被终止

4. 唯一 IP 地址
   - 每个 Pod 拥有集群内唯一 IP
   - Pod 内所有容器共享此 IP
```

---

## 二、Pod 完整定义

### 2.1 最小 Pod 定义

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: my-pod
  labels:
    app: my-app
spec:
  containers:
  - name: main-container
    image: nginx:1.25
```

### 2.2 完整 Pod 定义

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: my-pod
  namespace: production
  labels:
    app: my-app
    tier: frontend
    version: v1.0
  annotations:
    description: "My application pod"
    contact: "team@example.com"

spec:
  # 容器列表
  containers:
  - name: main-app                # 必填,容器名
    image: my-app:1.0            # 镜像
    imagePullPolicy: IfNotPresent # Always / Never / IfNotPresent
    ports:
    - containerPort: 8080
      name: http
      protocol: TCP
    - containerPort: 9090
      name: metrics

    # 环境变量
    env:
    - name: DB_HOST
      value: "10.0.0.1"
    - name: LOG_LEVEL
      value: "INFO"
    - name: POD_NAME               # Downward API
      valueFrom:
        fieldRef:
          fieldPath: metadata.name
    - name: DB_PASSWORD            # 来自 Secret
      valueFrom:
        secretKeyRef:
          name: db-secret
          key: password
    - name: DB_NAME                # 来自 ConfigMap
      valueFrom:
        configMapKeyRef:
          name: db-config
          key: database

    # 资源限制
    resources:
      requests:
        cpu: 100m                  # 0.1 核
        memory: 128Mi              # 128 MB
      limits:
        cpu: 500m                  # 最多 0.5 核
        memory: 256Mi              # 最多 256 MB

    # 卷挂载
    volumeMounts:
    - name: data
      mountPath: /data
    - name: config
      mountPath: /etc/config
      readOnly: true
    - name: secrets
      mountPath: /etc/secrets
      readOnly: true

    # 健康检查
    livenessProbe:
      httpGet:
        path: /health
        port: 8080
      initialDelaySeconds: 30
      periodSeconds: 10
      timeoutSeconds: 3
      failureThreshold: 3

    readinessProbe:
      httpGet:
        path: /ready
        port: 8080
      initialDelaySeconds: 5
      periodSeconds: 5

    livenessProbe:
      exec:
        command: ["cat", "/tmp/healthy"]
      initialDelaySeconds: 15
      periodSeconds: 20

    # 启动钩子
    lifecycle:
      postStart:
        exec:
          command: ["/bin/sh", "-c", "echo Pod started > /var/log/start.log"]
      preStop:
        exec:
          command: ["/bin/sh", "-c", "nginx -s quit"]

    # 镜像拉取凭证
    imagePullSecrets:
    - name: my-registry-secret

    # 安全上下文
    securityContext:
      runAsUser: 1000
      runAsGroup: 3000
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      capabilities:
        drop: ["ALL"]

    # 资源限制
    resources:
      ...

  # Init Containers (先于主容器启动)
  initContainers:
  - name: init-db
    image: busybox:1.36
    command: ['sh', '-c', 'until nslookup db; do echo waiting for db; sleep 2; done']

  # 容器间共享卷
  volumes:
  - name: data
    emptyDir: {}
  - name: config
    configMap:
      name: app-config
  - name: secrets
    secret:
      secretName: app-secrets

  # DNS 策略
  dnsPolicy: ClusterFirst
  # 可选: Default / ClusterFirst / ClusterFirstWithHostNet / None

  # 主机网络 (一般不用)
  hostNetwork: false

  # DNS 配置
  dnsConfig:
    nameservers:
    - 1.1.1.1
    - 8.8.8.8
    searches:
    - ns1.svc.cluster.local
    options:
    - name: ndots
      value: "2"

  # 节点选择器
  nodeSelector:
    disktype: ssd
    zone: us-east-1a

  # 容忍
  tolerations:
  - key: "node.kubernetes.io/unreachable"
    operator: "Exists"
    effect: "NoExecute"
    tolerationSeconds: 30

  # 亲和性
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
        - matchExpressions:
          - key: kubernetes.io/os
            operator: In
            values: ["linux"]
    podAffinity:
      preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 100
        podAffinityTerm:
          topologyKey: kubernetes.io/hostname
          labelSelector:
            matchLabels:
              app: cache

  # 安全上下文
  securityContext:
    runAsUser: 1000
    runAsNonRoot: true
    fsGroup: 2000
    seLinuxOptions:
      level: "s0:c123,c456"

  # 调度器名 (多调度器场景)
  schedulerName: default-scheduler

  # 主机别名
  hostAliases:
  - ip: "10.0.0.5"
    hostnames:
    - "foo.local"
    - "bar.local"

  # 重启策略 (Always / OnFailure / Never)
  restartPolicy: Always
```

---

## 三、容器配置详解

### 3.1 镜像 (image)

```yaml
# 标准格式
image: nginx:1.25                # 镜像名:标签

# 完整格式
image: registry.example.com/myorg/myapp:v1.0

# 使用 SHA256 (不可变)
image: nginx@sha256:abc123...

# 拉取策略
imagePullPolicy:
  - Always     # 总是拉取最新
  - Never      # 使用本地,不拉取
  - IfNotPresent  # 本地有就用,没有就拉 (默认)
```

### 3.2 环境变量

```yaml
# 方式 1: 直接赋值
env:
- name: DB_HOST
  value: "10.0.0.1"

# 方式 2: 引用 ConfigMap
env:
- name: DB_HOST
  valueFrom:
    configMapKeyRef:
      name: db-config
      key: host
      optional: false  # 必须存在

# 方式 3: 引用 Secret
env:
- name: DB_PASSWORD
  valueFrom:
    secretKeyRef:
      name: db-secret
      key: password

# 方式 4: 引用其他字段 (Downward API)
env:
- name: POD_NAME
  valueFrom:
    fieldRef:
      fieldPath: metadata.name
- name: POD_NAMESPACE
  valueFrom:
    fieldRef:
      fieldPath: metadata.namespace
- name: NODE_NAME
  valueFrom:
    fieldRef:
      fieldPath: spec.nodeName

# 方式 5: 引用资源
env:
- name: MY_POD_IP
  valueFrom:
    fieldRef:
      fieldPath: status.podIP

# 方式 6: 整个 ConfigMap 转为环境变量
envFrom:
- configMapRef:
    name: app-config
- secretRef:
    name: app-secrets
```

### 3.3 资源请求与限制

```yaml
resources:
  requests:                    # 调度时保证
    cpu: 100m                 # 0.1 核
    memory: 128Mi
    ephemeral-storage: 1Gi    # 临时存储
  limits:                      # 运行时硬限
    cpu: 500m                 # 最多 0.5 核
    memory: 256Mi
    ephemeral-storage: 2Gi

# CPU 单位:
# 100m = 0.1 核
# 1 = 1 核
# 可以是 0.5、1.5、2 等小数

# 内存单位:
# 128Mi = 128 MiB = 134 MB
# 1Gi = 1 GiB
# 也可写 128M、1G
```

**资源单位说明**:

```text
CPU: 
- 1 核 = 1000m
- 100m = 0.1 核
- 可小数: 0.5, 1.5
- 不允许 0 (K8s 不支持)

Memory:
- E/P/T/G/M/K (十进制: 1000)
- Ei/Pi/Ti/Gi/Mi/Ki (二进制: 1024)
- 1Mi = 1,048,576 bytes
- 1M = 1,000,000 bytes
```

### 3.4 端口配置

```yaml
ports:
- name: http              # 端口名
  containerPort: 8080      # 容器内端口
  hostPort: 30080          # 主机端口 (一般不用)
  protocol: TCP            # TCP / UDP / SCTP

# 注意:
# - containerPort 只是声明,需 EXPOSE 镜像也声明
# - 实际访问通过 Service
```

### 3.5 启动命令与参数

```yaml
# 方式 1: command + args (覆盖镜像 ENTRYPOINT 和 CMD)
command: ["/bin/sh"]
args: ["-c", "echo hello && sleep 3600"]

# 方式 2: 只覆盖 args
args: ["--port=8080"]

# 方式 3: 用环境变量
env:
- name: PARAM
  value: "production"
command: ["./start.sh"]
```

### 3.6 健康检查 (Probe)

```yaml
spec:
  containers:
  - name: app
    image: my-app:1.0

    # 启动探针 (1.16+)
    # 用于慢启动应用,决定何时算"启动完成"
    startupProbe:
      httpGet:
        path: /startup
        port: 8080
      initialDelaySeconds: 10
      periodSeconds: 5
      failureThreshold: 30   # 30 * 5s = 150s 启动时间

    # 存活探针
    # 失败 → 重启容器
    livenessProbe:
      httpGet:
        path: /health
        port: 8080
      initialDelaySeconds: 0
      periodSeconds: 10
      timeoutSeconds: 3
      successThreshold: 1
      failureThreshold: 3     # 3 次失败 = 容器不健康

    # 就绪探针
    # 失败 → 从 Service Endpoints 移除
    readinessProbe:
      httpGet:
        path: /ready
        port: 8080
      initialDelaySeconds: 5
      periodSeconds: 5

# Probe 类型:
# 1. httpGet: HTTP GET 请求
# 2. tcpSocket: TCP 端口检查
# 3. exec: 执行命令,退出码 0 表示成功
# 4. gRPC (1.24+): gRPC 健康检查

# 探针参数说明:
# initialDelaySeconds: 容器启动后多久开始探测
# periodSeconds: 探测间隔
# timeoutSeconds: 探测超时
# successThreshold: 成功阈值 (默认 1)
# failureThreshold: 失败阈值
```

### 3.7 生命周期钩子

```yaml
spec:
  containers:
  - name: app
    image: my-app:1.0

    lifecycle:
      postStart:                # 容器启动后
        exec:
          command: ["/bin/sh", "-c", "echo Pod started > /var/log/start.log"]

      preStop:                  # 容器停止前 (重要!)
        exec:
          command: ["/bin/sh", "-c", "/app/shutdown.sh"]

# preStop 的典型用途:
# 1. 优雅关闭 (drain 连接)
# 2. 注销服务注册
# 3. 保存状态
# 4. 上报监控数据

# K8s 发送 SIGTERM 前会先执行 preStop
# preStop 完成后才发 SIGTERM
# 容器收到 SIGTERM 后等待 terminationGracePeriodSeconds (默认 30s)
```

### 3.8 安全上下文 (SecurityContext)

```yaml
spec:
  # Pod 级
  securityContext:
    runAsUser: 1000                  # 以哪个用户 UID 运行
    runAsGroup: 3000                 # GID
    runAsNonRoot: true               # 必须非 root
    fsGroup: 2000                    # 卷的 GID
    fsGroupChangePolicy: "OnRootMismatch"
    seLinuxOptions:
      level: "s0:c123,c456"
      role: "object_r"
      user: "system_u"
      type: "container_t"
    sysctls:
    - name: net.core.somaxconn
      value: "1024"
    supplementalGroups: ["4000"]
    windowsOptions:
      gmsaCredentialSpecName: null

  containers:
  - name: app
    image: my-app:1.0
    # 容器级 (覆盖 Pod 级)
    securityContext:
      allowPrivilegeEscalation: false   # 禁止提权
      privileged: false                 # 禁止特权模式
      readOnlyRootFilesystem: true       # 只读根文件系统
      runAsNonRoot: true
      runAsUser: 1000
      capabilities:                     # Linux capabilities
        add: ["NET_ADMIN"]              # 添加
        drop: ["ALL"]                   # 删除所有
      procMount:
        default: DefaultProcMount
```

---

## 四、Pod 生命周期

### 4.1 Pod 阶段

```text
Pod 阶段 (phase):
1. Pending    - 已创建,等待调度/镜像拉取
2. Running    - 至少一个容器已启动
3. Succeeded  - 所有容器成功退出,不会重启 (Job)
4. Failed     - 至少一个容器失败
5. Unknown    - 状态无法获取 (通常 kubelet 通信失败)
```

### 4.2 容器状态

```text
Waiting:
  - reason: ContainerCreating  - 创建中
  - reason: CrashLoopBackOff   - 反复崩溃
  - reason: ImagePullBackOff   - 镜像拉取失败
  - reason: CreateContainerConfigError  - 配置错误
  - reason: InvalidImageName   - 镜像名无效

Running:
  startedAt: "2026-08-18T10:00:00Z"
  finishedAt: null
  containerID: "containerd://..."

Terminated:
  exitCode: 0           # 0 成功
  reason: Completed
  finishedAt: "2026-08-18T11:00:00Z"
```

### 4.3 重启策略

```yaml
spec:
  restartPolicy: Always     # 默认 (Deployment / StatefulSet)
  # restartPolicy: OnFailure   # (Job)
  # restartPolicy: Never       # (一次性任务)
```

### 4.4 终止流程

```text
1. Pod 被标记为 terminating
2. 从 Service Endpoints 移除 (触发 readiness probe 失败)
3. 执行 preStop 钩子
4. 发送 SIGTERM 给容器
5. 等待 gracePeriodSeconds (默认 30s)
6. SIGKILL 强制终止
7. 删除 Pod
```

---

## 五、Init Containers

### 5.1 概念

**Init Container** 在主容器启动前先运行,常用于初始化工作。

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: my-app
spec:
  initContainers:
  - name: init-db
    image: busybox:1.36
    command: ['sh', '-c', 'until nslookup db; do echo waiting; sleep 2; done']

  - name: init-config
    image: busybox:1.36
    command: ['sh', '-c', 'wget -O /work/config.yaml http://config-server/config']
    volumeMounts:
    - name: work
      mountPath: /work

  containers:
  - name: main-app
    image: my-app:1.0
    volumeMounts:
    - name: work
      mountPath: /app/config
    command: ['sh', '-c', './start.sh /app/config/config.yaml']
```

### 5.2 Init Container 用途

```text
1. 等待依赖服务 (数据库、缓存)
2. 下载配置或密钥
3. 数据库迁移
4. 权限初始化
5. 注册服务发现
6. 预热缓存
```

---

## 六、多容器 Pod (Sidecar 模式)

### 6.1 Sidecar 模式 (1.28+ 原生)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: app-with-sidecar
spec:
  template:
    spec:
      containers:
      - name: main-app
        image: my-app:1.0
        
      - name: log-shipper          # sidecar
        image: fluent-bit:2.0
        restartPolicy: Always     # 关键: sidecar 必须 Always 重启
```

### 6.2 经典 Sidecar 模式

```text
1. 日志收集 (Filebeat / Fluent-bit)
2. 监控导出 (Prometheus exporter)
3. 代理 (Envoy / Sidecar)
4. 数据库迁移工具 (Schema migration)
5. 配置热更新 (Reloader)
6. 服务网格 (Istio / Linkerd)
```

### 6.3 完整 Sidecar 示例

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: app-with-sidecar
spec:
  containers:
  - name: app
    image: my-app:1.0
    ports:
    - containerPort: 8080
    volumeMounts:
    - name: shared-logs
      mountPath: /var/log/app

  - name: log-shipper
    image: fluent-bit:1.9
    volumeMounts:
    - name: shared-logs
      mountPath: /var/log/app
      readOnly: true
    env:
    - name: FLUENTD_HOST
      value: "fluentd.monitoring.svc"

  volumes:
  - name: shared-logs
    emptyDir: {}
```

---

## 七、生命周期管理

### 7.1 Pod 中断 (Disruption)

```yaml
# PodDisruptionBudget (PDB)
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: my-app-pdb
spec:
  minAvailable: 2           # 至少 2 个可用
  # minAvailable: 50%      # 或百分比
  maxUnavailable: 1         # 最多 1 个不可用
  selector:
    matchLabels:
      app: my-app
```

### 7.2 优雅终止

```yaml
spec:
  # Pod 终止宽限期 (默认 30s)
  terminationGracePeriodSeconds: 60

  containers:
  - name: app
    lifecycle:
      preStop:
        # 容器停止前执行 (优雅关闭)
        exec:
          command: ["/bin/sh", "-c", "/app/bin/shutdown.sh"]
```

### 7.3 钩子执行顺序

```text
Pod 删除:
   1. API Server 更新 gracePeriodSeconds
   2. Endpoint Controller 移除 Endpoints
   3. kubelet 收到删除请求
   4. 执行 preStop 钩子
   5. 发送 SIGTERM
   6. 等待 gracePeriodSeconds
   7. (如未退出) 发送 SIGKILL
   8. 容器删除
   9. Pod 删除
```

---

## 八、Pod 调度策略

### 8.1 nodeSelector (简单)

```yaml
spec:
  nodeSelector:
    disktype: ssd
    zone: us-east-1a
```

### 8.2 nodeAffinity (推荐)

```yaml
spec:
  affinity:
    nodeAffinity:
      # 硬要求: 必须满足
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
        - matchExpressions:
          - key: kubernetes.io/os
            operator: In
            values: ["linux"]
          - key: zone
            operator: NotIn
            values: ["us-east-1b"]
      
      # 软偏好: 优先满足
      preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 80
        preference:
          matchExpressions:
          - key: disktype
            operator: In
            values: ["ssd"]
```

### 8.3 Pod Affinity/Anti-Affinity

```yaml
spec:
  affinity:
    # Pod 亲和: 与某 Pod 同节点
    podAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
      - labelSelector:
          matchLabels:
            app: cache
        topologyKey: kubernetes.io/hostname

    # Pod 反亲和: 与某 Pod 不同节点
    podAntiAffinity:
      preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 100
        podAffinityTerm:
          labelSelector:
            matchLabels:
              app: web
          topologyKey: kubernetes.io/hostname
```

### 8.4 Taints 和 Tolerations (污点)

```bash
# 给节点打污点
kubectl taint nodes node1 key=value:NoSchedule
kubectl taint nodes node1 dedicated=gpu:NoSchedule

# 去除污点
kubectl taint nodes node1 dedicated=gpu:NoSchedule-
```

```yaml
# Pod 容忍污点
spec:
  tolerations:
  - key: "dedicated"
    operator: "Equal"
    value: "gpu"
    effect: "NoSchedule"

  # 通用容忍 (匹配所有 key)
  - operator: "Exists"
    effect: "NoSchedule"
```

### 8.5 调度优先级

```yaml
spec:
  priorityClassName: high-priority     # 高优先级

  # 或
  priority: 1000000                  # 数值 (deprecated, 用 priorityClassName)
```

---

## 九、Pod 实战

### 9.1 创建 Pod

```bash
# 命令式
kubectl run nginx --image=nginx:1.25 --port=80

# 声明式
kubectl apply -f pod.yaml

# 自动生成 YAML
kubectl run nginx --image=nginx:1.25 --dry-run=client -o yaml > pod.yaml
```

### 9.2 查看 Pod

```bash
# 列出 Pod
kubectl get pods
kubectl get pods -A                # 所有命名空间
kubectl get pods -o wide          # 详细信息
kubectl get pods --show-labels    # 显示标签

# 详细信息
kubectl describe pod <pod-name>

# 日志
kubectl logs <pod-name>
kubectl logs -f <pod-name>
kubectl logs --previous <pod-name>
kubectl logs -c <container> <pod-name>
```

### 9.3 调试 Pod

```bash
# 进入容器
kubectl exec -it <pod-name> -- /bin/bash

# 临时容器调试
kubectl debug -it <pod-name> --image=busybox --target=main-container

# 端口转发
kubectl port-forward <pod-name> 8080:80

# 文件传输
kubectl cp <pod-name>:/var/log/app.log ./app.log
```

### 9.4 删除 Pod

```bash
kubectl delete pod <pod-name>
kubectl delete pod --all                   # 所有 (慎用)
kubectl delete pod -l app=my-app           # 按标签
kubectl delete pod --grace-period=0 --force  # 强制立即删除
```

---

## 核心要点速记

### Pod 核心概念

```text
- Pod = 1+ 个紧密协作的容器
- 共享网络 (IP、端口)
- 共享存储卷
- 同时调度到同一节点
- 同时启动/终止
```

### 容器配置关键字段

```text
- image + imagePullPolicy
- resources.requests/limits (必填)
- readiness/liveness/startupProbe (生产必填)
- securityContext (安全)
- volumeMounts + volumes
- env (环境变量)
- ports
- lifecycle.postStart/preStop
```

### 生命周期阶段

```text
Pending → Running → Succeeded/Failed
       或
Pending → Running → CrashLoopBackOff

优雅终止:
preStop → SIGTERM → 等待 gracePeriod → SIGKILL
```

### 多容器模式

```text
- Sidecar (1.28+ 原生, restartPolicy: Always)
- Ambassador (代理外部服务)
- Adapter (标准化输出)
- Init Container (启动前初始化)
```

### 健康检查三件套

```text
- startupProbe: 启动慢的应用 (1.16+)
- livenessProbe: 失败 → 重启容器
- readinessProbe: 失败 → 移出 Service Endpoints
```

### 调度五大策略

```text
1. nodeSelector: 简单标签匹配
2. nodeAffinity: 节点亲和 (推荐)
3. podAffinity/Anti-Affinity: Pod 亲和/反亲和
4. Taints/Tolerations: 污点容忍
5. priorityClassName: 优先级
```

### 资源限制注意事项

```text
- requests 必须设 (调度依据)
- limits 推荐设 (防止资源耗尽)
- CPU 限流 (throttle, 不杀死)
- Memory 超限 → OOMKilled
- requests + limits = 1:1~1:2 比较合理
```

---

## 参考

- **Pod 官方文档**: https://kubernetes.io/docs/concepts/workloads/pods/
- **容器生命周期**: https://kubernetes.io/docs/concepts/containers/container-lifecycle-hooks/
- **资源管理**: https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/
- **Probe 配置**: https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/
