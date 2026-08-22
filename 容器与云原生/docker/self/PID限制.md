# 容器 PID 上限设置 (PID Limit in Docker & Kubernetes)

> 本文档系统讲解为什么需要限制容器 PID 数量、Docker 和 K8s 中如何配置 PID 上限、常见问题与最佳实践。

## 一、为什么需要限制容器 PID

### 1.1 PID 是什么

```text
PID (Process ID, 进程标识符):
  - Linux 内核为每个进程分配唯一 ID
  - PID 1 是 init 进程 (容器内是 ENTRYPOINT)
  - PID 表大小是有限的 (/proc/sys/kernel/pid_max)

# 查看系统 PID 上限
cat /proc/sys/kernel/pid_max
# 通常: 32768 (默认) 或 4194304

# 容器内查看
docker exec myapp cat /proc/sys/kernel/pid_max
# 默认与宿主机一致
```

### 1.2 PID 耗尽攻击 (Fork Bomb)

```text
Fork Bomb 示例:

# 经典 Fork Bomb (一行代码)
:() { :|:& };:

# 解释:
# 1. 定义函数 :(), 调用自己两次 (递归)
# 2. :|:&  调用自己, 管道输出, 后台运行
# 3. 指数级增长, 瞬间耗尽 PID

# 普通容器内 fork bomb:
docker run --rm -it alpine sh -c ":() { :|:& };:"
# 几秒内: 系统无响应, PID 耗尽
# 整个宿主机崩溃
```

### 1.3 真实事故案例

```text
案例 1: Java 应用线程泄露
  场景: 应用 Bug 创建大量线程
  现象: 容器内 PID 涨到 10000+
  后果: 整个节点 PID 耗尽, 节点上其他容器也卡死
  解决: 限制 --pids-limit, 应用层修复线程泄露

案例 2: 恶意镜像 fork bomb
  场景: 第三方镜像含恶意脚本
  现象: 镜像运行时疯狂创建进程
  后果: 单容器耗尽节点所有 PID
  解决: PidsLimit cgroup 限制

案例 3: 共享内核影响
  在 K8s 中, Pod 间共享节点 PID namespace (默认隔离)
  一个 Pod fork bomb 可以影响整个节点所有 Pod
```

### 1.4 PID 耗尽的影响

```text
PID 耗尽后的症状:
  1. 系统无法创建新进程
  2. 系统调用 (fork, exec) 失败
     - EAGAIN (Resource temporarily unavailable)
  3. 应用崩溃 (新线程创建失败)
  4. 系统命令 (ls, ps) 执行失败
  5. ssh 登录失败 (无法创建子进程)
  6. 系统完全无响应
  7. 唯一恢复: 重启
```

---

## 二、Linux Cgroup PIDS 限制原理

### 2.1 cgroup v1 PIDS Controller

```text
Linux cgroup v1 中 PIDS controller:

# 文件位置
/sys/fs/cgroup/pids/
├── docker/                  # Docker 容器
│   └── <container-id>/
│       ├── pids.max        # PID 上限
│       ├── pids.current    # 当前 PID 数
│       └── tasks           # PID 列表
├── kubepods/                # K8s Pod
│   ├── burstable/
│   │   └── pod-xxx/
│   │       └── <container-id>/
│   └── guaranteed/
└── system.slice/
```

### 2.2 cgroup v2 PIDS Controller

```text
Linux cgroup v2 统一层级:

/sys/fs/cgroup/
├── system.slice/
│   ├── docker-<id>.scope/    # Docker 容器
│   │   ├── pids.max
│   │   └── pids.current
│   └── kubepods.slice/        # K8s
│       └── kubepods-burstable.slice/
│           └── pod-xxx/
│               └── <container-id>/
│                   ├── pids.max
│                   └── pids.current

# cgroup v2 优势:
- 统一层级管理
- 更好的资源隔离
- v1 和 v2 互不兼容
- 现代 Linux 推荐 v2
```

### 2.3 PID 限制工作原理

```text
进程创建流程:

应用调用 fork() / clone()
       ↓
内核 cgroup 检查 pids.current >= pids.max ?
       ↓
    是 → 返回 EAGAIN (失败)
    否 → 创建新进程
       pids.current += 1
       ↓
       进程创建成功

PID 限制的作用:
  - 限制进程总数 (含线程, 因为线程也是 PID)
  - 超限时直接拒绝
  - 不影响其他 cgroup
```

---

## 三、Docker 中设置 PID 上限

### 3.1 命令行方式

```bash
# --pids-limit 参数
docker run -d --pids-limit 200 --name myapp myimage

# 不设置时 (默认)
docker run -d --name myapp myimage
# 默认: 与宿主机 pid_max 一致 (通常很大)
# 风险: 应用可创建无数进程, 拖垮节点

# 推荐: 根据应用合理设置
docker run -d --pids-limit 200 myapp      # 一般应用
docker run -d --pids-limit 500 myapp      # 中等复杂应用
docker run -d --pids-limit 100 myapp      # 简单应用
docker run -d --pids-limit 1000 myapp     # 高并发应用
```

### 3.2 Dockerfile 方式

```dockerfile
# 通过 HEALTHCHECK 的 --pids-limit (不直接支持)
# 需要在 docker run 时指定
# 或在 docker-compose 中指定
```

### 3.3 docker-compose 方式

```yaml
# docker-compose.yml
services:
  web:
    image: nginx
    pids_limit: 200          # 注意: 字段名是 pids_limit
    
  api:
    image: my-api
    pids_limit: 500
    
  worker:
    image: my-worker
    pids_limit: 100
```

```bash
# 启动
docker compose up -d

# 验证
docker inspect myapp | grep Pid
docker exec myapp sh -c "ulimit -u"
# 200
```

### 3.4 Docker Daemon 全局配置

```json
# /etc/docker/daemon.json
{
  "default-pids-limit": 200
}

# 重新加载
sudo systemctl reload docker

# 全局默认值生效
# 单独 run 时仍可覆盖
docker run --pids-limit 500 myapp
```

### 3.5 验证 PID 限制

```bash
# 查看容器进程数限制
docker inspect myapp --format='{{.HostConfig.PidsLimit}}'
# 200

# 进入容器查看
docker exec myapp sh -c "cat /sys/fs/cgroup/pids.max"
# 200

# 容器内实际 PID 数
docker exec myapp sh -c "cat /sys/fs/cgroup/pids.current"
# 5

# 容器内 ulimit 查看
docker exec myapp sh -c "ulimit -u"
# 200

# 进程详情
docker exec myapp ps aux
```

### 3.6 测试 PID 限制生效

```bash
# 启动有限制的容器
docker run -d --pids-limit 100 --name test myimage

# 进入尝试 fork bomb
docker exec test sh -c ":() { :|:& };:"

# 报错
# bash: fork: Resource temporarily unavailable
# 容器依然存活

# 验证进程数限制生效
docker exec test sh -c "cat /sys/fs/cgroup/pids.current"
# ~100 (达到上限)

# 对比: 不用 --pids-limit
docker run -d --name test2 myimage
docker exec test2 sh -c ":() { :|:& };:"

# 可能:
# - 容器卡死
# - 节点其他容器无响应
# - 主机无法创建新进程
```

---

## 四、K8s 中设置 PID 上限

### 4.1 K8s PidsLimit cgroup 机制

```text
K8s 通过 cgroup PIDS subsystem 限制容器 PID:

# Pod 维度
/sys/fs/cgroup/pids/kubepods/pod-xxx/pids.max
# Container 维度
/sys/fs/cgroup/pids/kubepods/pod-xxx/container-yyy/pids.max
```

### 4.2 K8s 限制方式

```yaml
# 方式 1: Pod 级别限制 (推荐)
apiVersion: v1
kind: Pod
metadata:
  name: myapp
spec:
  containers:
  - name: app
    image: myapp:1.0
    resources:
      requests:
        cpu: 100m
        memory: 128Mi
      limits:
        # PID 限制
        # 注意: K8s 1.20+ 才支持
        # 早期版本需要通过 PodSpec.PidsLimit
```

```yaml
# K8s 1.20+ 方式
apiVersion: v1
kind: Pod
metadata:
  name: myapp
spec:
  containers:
  - name: app
    image: myapp:1.0
    resources:
      limits:
        cpu: "500m"
        memory: "512Mi"
    # 早期版本
    securityContext:
      capabilities:
        add: ["SYS_RESOURCE"]    # 需要此权限
```

### 4.3 实际 K8s 中配置

```text
K8s 1.20 之前:
  - K8s 没有原生的 PidsLimit 字段
  - 需要使用 PodSpec.PidsLimit
  - 但需要额外开启 feature gate

K8s 1.20 ~ 1.33:
  - 通过 PodSpec.PidsLimit
  - 部分版本需要 feature gate

K8s 1.33+:
  - 通过 ephemeral containers 限制
  - 通过 cgroup v2 PidsLimit
```

### 4.4 K8s 中实际可用的方法

```yaml
# 方法 1: 使用 securityContext.capabilities 限制
apiVersion: v1
kind: Pod
metadata:
  name: myapp
spec:
  containers:
  - name: app
    image: myapp:1.0
    securityContext:
      runAsUser: 1000
      runAsGroup: 3000
      # 关键: 限制 fork() 能力
      capabilities:
        drop:
          - SYS_RESOURCE  # 限制 ulimit 设置
      resources:
        requests:
          cpu: 100m
          memory: 128Mi
        limits:
          cpu: 500m
          memory: 256Mi
```

```yaml
# 方法 2: 使用 PodSpec.PidsLimit (K8s 1.20+, 需要 feature gate)
apiVersion: v1
kind: Pod
metadata:
  name: myapp
spec:
  # 关键: K8s 1.20+ 需要 --feature-gates=PodPidsLimit=true
  pidsLimit: 200    # 限制 Pod 中所有进程数总和
  containers:
  - name: app
    image: myapp:1.0
```

```yaml
# 方法 3: 使用 OCI Runtime Spec 限制 (K8s 1.27+)
apiVersion: v1
kind: Pod
metadata:
  name: myapp
spec:
  runtimeClassName: oci-runtime-with-limits
  containers:
  - name: app
    image: myapp:1.0
    resources:
      limits:
        cpu: 500m
        memory: 256Mi
```

### 4.5 验证 K8s PID 限制

```bash
# 进入 K8s Pod 查看
kubectl exec -it myapp -- sh

# 查看 PID 限制
cat /sys/fs/cgroup/pids.max

# 查看当前 PID 数
cat /sys/fs/cgroup/pids.current

# 查看进程树
ps aux

# 查看 ulimit
ulimit -u
```

### 4.6 K8s 中 PID 限制的现状

```text
截至 2026 年 K8s PID 限制支持的现状:

K8s 1.20-1.29:
  - 早期: 需要 feature gate + 安全上下文
  - 部分版本无原生 PidsLimit

K8s 1.30+:
  - 推荐使用 PodSecurity Standards 限制
  - 通过 cgroup v2 自动应用
  - 容器运行时 (containerd) 支持

实际上推荐做法:
  - Docker 中用 --pids-limit
  - K8s 中通过 DaemonSet 配置 (在节点层)
  - 或使用安全策略 (PodSecurity Standards)
  - 或使用 cgroup 直接限制
```

---

## 五、生产级 PID 限制实践

### 5.1 各应用推荐 PID 数

```text
应用类型               推荐 PID 限制     理由
────────────────────────────────────────
静态网站 (Nginx)         100            通常 < 50
API 服务 (Node/Python)    200-500        框架 + 业务线程
Java Spring Boot          500-1000       JVM + 线程池 + Netty worker
Go HTTP 服务             200-300        goroutine (每个连接 1 个)
高并发服务 (Netty/Golang)  1000-2000      大量 worker
批处理 (Python)           100-200        简单任务
数据库 (Postgres)         500-1000       主进程 + worker
消息队列消费者 (Kafka)     300-500       consumer 池
机器学习推理              200-500        推理 + 后台
恶意应用防护 (不可信)       50-100       严防 fork bomb
```

### 5.2 K8s 中按 namespace 限制

```yaml
# LimitRange 限制命名空间下所有 Pod 的 PID
apiVersion: v1
kind: LimitRange
metadata:
  name: pid-limit
  namespace: production
spec:
  limits:
  - type: Container
    default:
      # 这里只能设置 resources, 不能直接设置 pids
      cpu: 500m
      memory: 512Mi
    # 早期 K8s 可通过 extension
```

```yaml
# K8s 1.30+ 通过 OCI Runtime + LimitRange
apiVersion: v1
kind: LimitRange
metadata:
  name: pids-limits
  namespace: production
spec:
  limits:
  - type: Container
    max:
      # 配合 RuntimeClass 设置
      pids:
        limit: 500
```

### 5.3 K8s 准入控制 (Admission Control)

```yaml
# K8s 准入控制器 (PodSecurity) 可以限制危险配置
apiVersion: apiserver.config.k8s.io/v1
kind: AdmissionConfiguration
plugins:
- name: PodSecurity
  configuration:
    apiVersion: pod-security.admission.config.k8s.io/v1
    kind: PodSecurityConfiguration
    defaults:
      enforce: "restricted"
      audit: "restricted"
      warn: "restricted"
    exemptions:
      # 排除不需要限制的
      usernames: []
      runtimeClasses: []
      namespaces: [kube-system]
```

### 5.4 RuntimeClass 控制

```yaml
# 1. 创建 RuntimeClass (限制 cgroup)
apiVersion: node.k8s.io/v1
kind: RuntimeClass
metadata:
  name: restricted-pids
handler: restricted-pids
scheduling:
  nodeSelector:
    pids-restricted: "true"
overhead:
  podFixed:
    memory: "100Mi"
    pids: "50"    # 容器默认 PID 上限 (K8s 1.28+)
```

```yaml
# 2. Pod 使用 RuntimeClass
apiVersion: v1
kind: Pod
metadata:
  name: myapp
spec:
  runtimeClassName: restricted-pids
  containers:
  - name: app
    image: myapp:1.0
    resources:
      limits:
        cpu: 500m
        memory: 256Mi
```

---

## 六、完整实战示例

### 6.1 Docker 中完整配置

```bash
# 1. 启动带 PID 限制的容器
docker run -d \
  --name myapp \
  --pids-limit 200 \
  --memory 512m \
  --cpus 1.0 \
  --restart unless-stopped \
  -p 8080:8080 \
  myapp:1.0

# 2. 验证配置
docker inspect myapp | grep -E "PidsLimit|Memory|CpuShares"
# 输出:
# "PidsLimit": 200
# "Memory": 536870912
# "CpuShares": 1024

# 3. 查看 cgroup
docker exec myapp sh -c "ls /sys/fs/cgroup/"
# (cgroup v1)
# cgroup.clone_children memory ...
# 或 (cgroup v2)
# cgroup.controllers cgroup.stat ...

docker exec myapp sh -c "cat /sys/fs/cgroup/pids/pids.max"
# 200 (cgroup v1)
# 或
docker exec myapp sh -c "cat /sys/fs/cgroup/pids.max"
# 200 (cgroup v2)

# 4. 测试 fork bomb
docker exec myapp sh -c ":() { :|:& };:" 2>&1 | head -3
# bash: fork: retry: Resource temporarily unavailable
# bash: fork: retry: Resource temporarily unavailable
# bash: fork: Resource temporarily unavailable

# 5. 容器仍然存活
docker ps | grep myapp
# myapp  Up 5 minutes  myapp:1.0
```

### 6.2 K8s 中完整配置

```bash
# 1. 部署带 PID 限制的 Pod
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: myapp
spec:
  containers:
  - name: app
    image: myapp:1.0
    resources:
      requests:
        cpu: 100m
        memory: 128Mi
      limits:
        cpu: 500m
        memory: 256Mi
    # 早期 K8s 通过 cgroup 限制 (K8s 1.27+ 部分支持)
    securityContext:
      capabilities:
        drop:
        - ALL
        add:
        - NET_BIND_SERVICE
EOF

# 2. 验证 cgroup 限制
kubectl exec myapp -- cat /sys/fs/cgroup/pids.max
# 取决于 cgroup driver 和 K8s 版本

# 3. 测试 fork bomb
kubectl exec myapp -- sh -c ":() { :|:& };:" 2>&1 | head -3
# 容器应该限制
```

### 6.3 K8s 部署清单 (生产)

```yaml
# 1. Pod 配置最佳实践
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
spec:
  replicas: 3
  selector:
    matchLabels:
      app: myapp
  template:
    metadata:
      labels:
        app: myapp
    spec:
      # 关键: 限制资源 (避免 fork bomb 影响节点)
      containers:
      - name: app
        image: myapp:1.0
        resources:
          requests:
            cpu: 200m
            memory: 256Mi
          limits:
            cpu: 1000m
            memory: 512Mi
        # 早期 K8s: 通过 securityContext 限制
        securityContext:
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
          runAsNonRoot: true
          runAsUser: 1000
          capabilities:
            drop: ["ALL"]
        # 健康检查
        livenessProbe:
          httpGet: { path: /health, port: 8080 }
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet: { path: /ready, port: 8080 }
          initialDelaySeconds: 5
          periodSeconds: 5
```

---

## 七、故障排查

### 7.1 应用启动失败

```text
Q: 应用启动报 fork: Resource temporarily unavailable
A: 原因: PID 限制太小, 启动时子进程过多
   解决: 增加 --pids-limit 或应用启动优化

# 诊断
docker exec myapp sh -c "ulimit -u"
# 200
docker exec myapp sh -c "cat /sys/fs/cgroup/pids.current"
# 195 (接近上限)

# 解决
docker run --pids-limit 500 myapp    # 调大
```

### 7.2 节点其他容器受影响

```text
Q: 单个容器 fork bomb 导致同节点其他容器卡死
A: 原因: K8s cgroup 默认隔离不阻止 fork bomb 拖垮节点
   解决: 配置 PID 限制 + 监控告警

# 监控节点 PID 总数
cat /sys/fs/cgroup/pids/kubepods/pids.current
# 若接近 pids.max, 节点接近耗尽
```

### 7.3 告警配置

```yaml
# Prometheus 告警规则
groups:
- name: pid_exhaustion
  rules:
  - alert: ContainerPIDHigh
    expr: container_pid_current / container_pid_max > 0.8
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "容器 {{ $labels.container }} PID 接近上限"
  
  - alert: NodePIDHigh
    expr: node_pid_used / node_pid_max > 0.8
    for: 5m
    labels:
      severity: critical
```

### 7.4 应急响应

```bash
# 容器 fork bomb 应急
# 1. 立即停止容器
docker stop myapp

# 2. 限制进程数后启动
docker run --pids-limit 100 myapp

# 3. K8s 应急
kubectl delete pod myapp
# Pod 重新调度

# 4. 节点级紧急处理
ssh node
# 查看节点总进程数
ps aux | wc -l
# 若接近 32768, 重启节点或清理进程
```

---

## 八、cgroup v1 vs v2 区别

### 8.1 cgroup 版本对比

```text
特性                 cgroup v1         cgroup v2
──────────────────────────────────────────────
层级                 多层 (混合)        统一单层
控制器               分散              统一 (cgroup.subtree_control)
PIDS 控制器          pids/             pids (单层)
文件系统             /sys/fs/cgroup/  /sys/fs/cgroup/
                    pids/ (独立)
内存                memory/           memory (统一)
cgroup v1 转 v2     -                转换复杂

判断当前版本:
  cat /sys/fs/cgroup/cgroup.controllers
  # 空 → v1
  # 有内容 → v2

  stat /sys/fs/cgroup/init.scope
  # 1 (数字) → v1
  # 目录 → v2
```

### 8.2 K8s cgroup driver 配置

```bash
# kubelet 配置 (/var/lib/kubelet/config.yaml)
apiVersion: kubelet.config.k8s.io/v1beta1
kind: KubeletConfiguration
cgroupDriver: "systemd"   # 或 "cgroupfs"

# 推荐: K8s 1.22+ 使用 systemd
# 因为 v2 的统一层级更适合 cgroup v2
```

---

## 九、最佳实践

### 9.1 推荐策略

```text
1. 必须限制 PID
   - Docker: --pids-limit 始终设置
   - K8s: 通过 LimitRange / RuntimeClass / 安全策略
   - 默认值合理, 不要过大

2. 监控 PID 使用
   - 监控 container_pid_current / container_pid_max
   - 告警阈值 80%
   - 趋势监控, 提前发现异常

3. 应用层加固
   - 限制线程池大小
   - 限制连接池大小
   - 防止 fork bomb 类应用 Bug

4. 配合其他资源限制
   - CPU 限制
   - 内存限制
   - 进程数限制
   - 文件描述符限制

5. 安全策略
   - 启用 PodSecurity Standards
   - 限制 capabilities (drop ALL)
   - 非 root 运行 (runAsNonRoot)
   - 只读根文件系统
```

### 9.2 完整资源限制示例

```bash
# Docker
docker run -d \
  --name myapp \
  --pids-limit 200 \
  --memory 512m \
  --memory-swap 512m \
  --cpus 1.0 \
  --ulimit nofile=65535:65535 \
  --ulimit nproc=200 \
  --read-only \
  --security-opt no-new-privileges \
  --cap-drop ALL \
  --cap-add NET_BIND_SERVICE \
  --user 1000:1000 \
  myapp:1.0
```

```yaml
# K8s
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: app
    image: myapp:1.0
    resources:
      requests: { cpu: 100m, memory: 128Mi }
      limits:   { cpu: 500m, memory: 256Mi }
    securityContext:
      runAsNonRoot: true
      runAsUser: 1000
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      capabilities:
        drop: ["ALL"]
        add: ["NET_BIND_SERVICE"]
```

### 9.3 监控告警

```yaml
# Prometheus 告警规则
groups:
- name: container_pids
  rules:
  - alert: ContainerPIDUsageHigh
    expr: |
      (
        kube_pod_container_resource_limits{p resource="pids"} > 0
        and
        container_pid_current / kube_pod_container_resource_limits{p resource="pids"} > 0.8
      )
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "容器 PID 使用率高"
      description: "容器 {{ $labels.pod }} 接近 PID 上限"

  - alert: ContainerPIDReachedLimit
    expr: |
      container_pid_current >= container_pid_max
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "容器 PID 已达上限, 即将无法创建新进程"
```

### 9.4 排查清单

```text
应用启动失败: fork: Resource temporarily unavailable
  □ 调整 --pids-limit (增加)
  □ 检查应用启动脚本 (避免大量子进程)
  □ 查看 ulimit -u

节点整体无响应
  □ 检查 /proc/sys/kernel/pid_max
  □ 检查 cgroup pids.current (节点级)
  □ 重启节点
  □ 隔离恶意 Pod

K8s Pod 启动失败
  □ kubectl describe pod
  □ 检查 events
  □ 检查 LimitRange
  □ 检查 RuntimeClass

PID 监控
  □ 部署 kube-prometheus
  □ 配置 container_pid 告警
  □ 监控节点 PID 总数
```

---

## 十、核心要点速记

### PID 限制速记

```text
为什么限制:
  1. 防止 fork bomb
  2. 防止应用 Bug 创建大量进程
  3. 保护节点其他容器
  4. 提高系统稳定性

Docker 中设置:
  docker run --pids-limit 200 myapp
  docker-compose: pids_limit: 200
  daemon.json: default-pids-limit: 200

K8s 中设置:
  早期: securityContext.capabilities + RuntimeClass
  K8s 1.20+: PodSpec.PidsLimit (需 feature gate)
  K8s 1.28+: Sidecar + RuntimeClass
  K8s 1.33+: 通过 OCI Runtime 限制
```

### 推荐 PID 上限

```text
应用类型               PID 上限
──────────────────────────────────
静态网站               100
API 服务              200-500
Java 应用             500-1000
高并发服务            1000-2000
不可信应用            50-100
```

### 关键监控

```text
# Docker
docker exec myapp cat /sys/fs/cgroup/pids.max
docker exec myapp cat /sys/fs/cgroup/pids.current

# K8s (需 metrics-server 或 Prometheus)
container_pid_current / container_pid_max

# 告警
> 0.8 → 警告
> 0.95 → 严重
```

### cgroup 文件位置

```text
cgroup v1: /sys/fs/cgroup/pids/<cgroup>/pids.max
cgroup v2: /sys/fs/cgroup/<cgroup>.scope/pids.max
```

### 核心速记

```text
1. PID 限制是容器安全的基础
2. Docker 中用 --pids-limit, K8s 中通过 RuntimeClass/PodSpec
3. 监控 container_pid_current / container_pid_max
4. 配合其他 cgroup 限制 (CPU, 内存)
5. 应用层也要限制 (线程池, 连接池)
6. 出现 fork bomb 时快速停止容器
```

### 与其他限制配合

```text
完整的 cgroup 限制:

docker run \
  --pids-limit 200 \        # 进程数
  --memory 512m \            # 内存
  --cpus 1.0 \               # CPU
  --ulimit nofile=65535 \    # 文件描述符
  --cap-drop ALL \           # capability
  --read-only \              # 根文件系统
  --security-opt no-new-privileges
  myapp:1.0

每项都限制:
  - 进程数 (fork bomb 防护)
  - 内存 (OOM 防护)
  - CPU (公平调度)
  - 文件描述符 (fd 泄露防护)
  - capability (权限最小化)
```

---

## 附录: 关键参考

```text
- Docker run 命令: https://docs.docker.com/engine/reference/run/#pids-limit
- Docker cgroup: https://docs.docker.com/config/containers/runmetrics/
- K8s PidsLimit: https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/#pod-lifecycle
- cgroup v1: https://www.kernel.org/doc/Documentation/cgroup-v1/cgroups.txt
- cgroup v2: https://www.kernel.org/doc/Documentation/admin-guide/cgroup-v2.rst
- K8s RuntimeClass: https://kubernetes.io/docs/concepts/containers/runtime-class/
- Linux pid_namespaces: https://man7.org/linux/man-pages/man7/pid_namespaces.7.html
- K8s 资源管理: https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/
- Linux 进程限制 (ulimit): https://man7.org/linux/man-pages/man2/getrlimit.2.html

## 快速参考卡

```text
Docker:  docker run --pids-limit 200 myapp
K8s:     spec.pidsLimit: 200 (K8s 1.20+)
        或 RuntimeClass + cgroup v2

推荐 PID 上限:
  静态网站: 100
  API:      200-500
  Java:     500-1000
  高并发:   1000-2000

验证:
  docker exec myapp cat /sys/fs/cgroup/pids.max
  kubectl exec myapp -- cat /sys/fs/cgroup/pids.max
```
