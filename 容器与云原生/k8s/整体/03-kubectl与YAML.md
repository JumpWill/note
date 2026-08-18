# kubectl 与 YAML 基础 (kubectl & YAML Basics)

> 本章系统讲解 kubectl 命令行工具与 K8s YAML 配置语法,是使用 K8s 的基础。

## 一、kubectl 概述

### 1.1 什么是 kubectl

```text
kubectl = Kubernetes API 客户端命令行工具

功能:
- 部署应用 (kubectl apply)
- 查看资源 (kubectl get)
- 修改资源 (kubectl edit)
- 删除资源 (kubectl delete)
- 调试应用 (kubectl exec/logs)
- 集群管理 (kubectl drain/cordon)
```

### 1.2 kubectl 安装

```bash
# macOS
brew install kubectl

# Linux
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

# 验证
kubectl version --client

# 配置 kubeconfig
mkdir -p ~/.kube
# kubeadm init 后会自动复制:
sudo cp -f /etc/kubernetes/admin.conf ~/.kube/config
```

### 1.3 kubeconfig 配置

```yaml
# ~/.kube/config
apiVersion: v1
kind: Config
clusters:
- name: production
  cluster:
    server: https://10.0.0.10:6443
    certificate-authority-data: <base64-encoded-ca-cert>
- name: staging
  cluster:
    server: https://staging.example.com:6443
contexts:
- name: prod-admin
  context:
    cluster: production
    user: admin
- name: staging-admin
  context:
    cluster: staging
    user: admin
users:
- name: admin
  user:
    client-certificate-data: <base64-encoded-cert>
    client-key-data: <base64-encoded-key>
current-context: prod-admin

# 多集群切换
kubectl config use-context staging-admin

# 查看当前上下文
kubectl config current-context

# 设置默认 namespace
kubectl config set-context --current --namespace=my-app
```

---

## 二、kubectl 核心命令

### 2.1 基础语法

```text
kubectl [command] [TYPE] [NAME] [flags]

例:
  kubectl get pods                       # 列出所有 Pod
  kubectl get pods nginx                # 列出名为 nginx 的 Pod
  kubectl get pods -n kube-system       # 在 kube-system 命名空间
  kubectl get pods -o yaml              # YAML 格式输出
  kubectl get pods -o json              # JSON 格式输出
  kubectl get pods -o wide              # 详细信息
```

### 2.2 常用命令速查

```bash
# ===== 信息查询 =====
kubectl get nodes                      # 节点
kubectl get pods                       # Pod
kubectl get deployments                # Deployment
kubectl get services                    # Service
kubectl get all                         # 所有资源
kubectl get pods -A                     # 所有命名空间
kubectl get pods -o yaml                # YAML 输出
kubectl get pods -o jsonpath='{.items[*].metadata.name}'  # JSONPath
kubectl get pods --show-labels          # 显示 labels
kubectl get pods -l app=nginx          # 按 label 过滤
kubectl get pods --field-selector=status.phase=Running

# ===== 详细信息 =====
kubectl describe pod <pod-name>         # Pod 详情
kubectl describe node <node-name>
kubectl describe deployment <deploy-name>

# ===== 日志 =====
kubectl logs <pod-name>                 # 标准输出
kubectl logs <pod-name> --previous      # 上一个实例
kubectl logs <pod-name> -c <container>  # 多容器 Pod
kubectl logs -f <pod-name>              # 实时跟踪
kubectl logs --tail=100 <pod-name>       # 最后 100 行

# ===== 进入容器 =====
kubectl exec -it <pod-name> -- /bin/bash
kubectl exec -it <pod-name> -c <container> -- /bin/sh

# ===== 端口转发 =====
kubectl port-forward <pod-name> 8080:80  # 本地 8080 → Pod 80
kubectl port-forward service/<service-name> 8080:80

# ===== 文件传输 =====
kubectl cp <pod-name>:/path/to/file ./local-file
kubectl cp ./local-file <pod-name>:/path/to/file

# ===== 资源创建/更新 =====
kubectl apply -f manifest.yaml         # 创建/更新
kubectl apply -f ./directory/            # 目录下所有 yaml
kubectl apply -f https://example.com/manifest.yaml

# ===== 资源删除 =====
kubectl delete -f manifest.yaml
kubectl delete pod <pod-name>
kubectl delete pods --all               # 删除所有 (慎用!)
kubectl delete namespace <ns>           # 删除命名空间

# ===== 资源编辑 =====
kubectl edit deployment <name>          # 编辑 (默认 vim)
kubectl edit svc <name>                 # 用 EDITOR 环境变量

# ===== 资源扩缩 =====
kubectl scale deployment <name> --replicas=5
kubectl scale statefulset <name> --replicas=3

# ===== 资源状态 =====
kubectl rollout status deployment/<name>
kubectl rollout history deployment/<name>
kubectl rollout undo deployment/<name>   # 回滚
kubectl rollout restart deployment/<name>

# ===== 标签操作 =====
kubectl label pod <pod> tier=frontend
kubectl label pod <pod> tier-             # 删除标签
kubectl annotate pod <pod> description='my app'

# ===== 节点管理 =====
kubectl cordon <node>                   # 标记不可调度
kubectl uncordon <node>                 # 恢复
kubectl drain <node> --ignore-daemonsets  # 驱逐 Pod

# ===== 集群管理 =====
kubectl cluster-info
kubectl api-resources
kubectl api-versions
kubectl version

# ===== 上下文管理 =====
kubectl config get-contexts
kubectl config current-context
kubectl config use-context <name>
kubectl config set-context --current --namespace=<ns>

# ===== 自动补全 =====
source <(kubectl completion bash)
echo "source <(kubectl completion bash)" >> ~/.bashrc
```

### 2.3 输出格式

```bash
# -o 输出格式
-o wide           # 详细信息
-o yaml           # YAML 完整格式
-o json           # JSON 完整格式
-o jsonpath='{}'  # JSONPath
-o name           # 仅名称

# JSONPath 示例
kubectl get pods -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.phase}{"\n"}'

# 自定义列
kubectl get pods -o custom-columns=NAME:.metadata.name,STATUS:.status.phase

# 排序
kubectl get pods --sort-by=.metadata.creationTimestamp

# 标签过滤
kubectl get pods -l app=nginx,tier=frontend
kubectl get pods -l '!app'                 # 不等于
kubectl get pods -l 'app in (nginx,redis)'  # 多值
```

---

## 三、YAML 基础

### 3.1 YAML 语法

```yaml
# YAML = YAML Ain't Markup Language
# 特点:
# - 缩进表示层级 (2 空格, 不要用 Tab)
# - 键值对: key: value
# - 列表: - item
# - 注释: #
# - 字符串引号: " 或 ' 或省略

# 键值对
name: kubernetes
version: 1.30
stable: true

# 字符串
description: "hello world"           # 推荐用双引号
description: 'it''s a test'           # 单引号转义
description: 纯文本,无特殊字符      # 可以省略

# 数字
port: 8080
count: 100
price: 99.99
hex: 0xFF
scientific: 1.2e+5

# 布尔
enabled: true
disabled: false

# 空值
key: ~
key: null
key: 

# 日期
date: 2026-08-18
datetime: 2026-08-18T10:00:00Z

# 多行字符串
description: |
  多行文本
  保留换行
  第二行

# 折叠多行
description: >
  多行文本
  折叠为单行
  第二行

# 列表
items:
  - apple
  - banana
  - cherry

# 对象
server:
  host: 10.0.0.1
  port: 8080

# 列表中的对象
users:
  - name: alice
    age: 30
  - name: bob
    age: 25

# 嵌套对象
server:
  host: 10.0.0.1
  database:
    name: mydb
    credentials:
      username: admin
      password: secret
```

### 3.2 K8s YAML 通用结构

```yaml
# 必填字段
apiVersion: apps/v1             # API 版本 (必填)
kind: Deployment                # 资源类型 (必填)

metadata:                       # 元数据
  name: my-app                  # 名称 (必填)
  namespace: default            # 命名空间
  labels:                       # 标签 (key-value)
    app: my-app
    tier: frontend
    version: v1.0
  annotations:                  # 注解 (更多元数据)
    description: My application
    contact: admin@example.com

spec:                           # 期望状态 (不同资源不同)
  # ...

status:                         # 实际状态 (K8s 自动维护,通常不写)
  # ...
```

### 3.3 常用 K8s YAML 示例

#### Pod

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: nginx-pod
  labels:
    app: nginx
spec:
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
    env:
    - name: ENV_NAME
      value: production
    volumeMounts:
    - name: data
      mountPath: /data
  volumes:
  - name: data
    emptyDir: {}
```

#### Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-deployment
  labels:
    app: nginx
spec:
  replicas: 3
  selector:
    matchLabels:
      app: nginx
  template:
    metadata:
      labels:
        app: nginx
    spec:
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
```

#### Service

```yaml
apiVersion: v1
kind: Service
metadata:
  name: nginx-service
spec:
  type: ClusterIP       # ClusterIP / NodePort / LoadBalancer / ExternalName
  selector:
    app: nginx
  ports:
  - port: 80             # Service 端口
    targetPort: 80       # Pod 端口
    protocol: TCP
```

#### ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  # 简单配置
  log.level: INFO
  cache.size: "1000"
  # 完整配置文件
  application.yml: |
    server:
      port: 8080
    database:
      url: jdbc:postgresql://db:5432/mydb
      pool:
        max-size: 20
```

#### Namespace

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: production
  labels:
    env: prod
```

---

## 四、字段引用语法

### 4.1 env 引用

```yaml
spec:
  containers:
  - name: app
    env:
    # 直接赋值
    - name: DB_HOST
      value: "10.0.0.1"
    # 引用 ConfigMap
    - name: DB_HOST
      valueFrom:
        configMapKeyRef:
          name: db-config
          key: host
    # 引用 Secret
    - name: DB_PASSWORD
      valueFrom:
        secretKeyRef:
          name: db-secret
          key: password
    # 引用其他字段
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
```

### 4.2 资源引用

```yaml
spec:
  containers:
  - name: app
    env:
    # 引用其他 Pod 的字段 (Downward API)
    - name: MY_POD_NAME
      valueFrom:
        fieldRef:
          fieldPath: metadata.name

  # 引用其他资源
  volumes:
  - name: config
    configMap:
      name: app-config        # 引用名为 app-config 的 ConfigMap
      items:
      - key: application.yml
        path: application.yml

  - name: secret-volume
    secret:
      secretName: app-secret   # 引用 Secret
```

---

## 五、kubectl 高级技巧

### 5.1 JSONPath 详解

```bash
# 基础语法
kubectl get pods -o jsonpath='{.items[0].metadata.name}'

# 常用模式
{
  .items[*]              # 所有项
  .items[0]              # 第一项
  .items[?(@.metadata.labels.app==nginx)]   # 过滤
  .items[].metadata.name # 提取字段
}

# 实战示例
# 1. 获取所有 Pod 名称
kubectl get pods -o jsonpath='{.items[*].metadata.name}'

# 2. 获取所有 Pod 的镜像
kubectl get pods -o jsonpath='{.items[*].spec.containers[0].image}'

# 3. 获取所有命名空间
kubectl get ns -o jsonpath='{.items[*].metadata.name}'

# 4. 统计 Running 状态的 Pod
kubectl get pods -o jsonpath='{.items[?(@.status.phase=="Running")].metadata.name}' | wc -w

# 5. 自定义格式
kubectl get pods -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.phase}{"\n"}{end}'
```

### 5.2 Go Template

```bash
# 复杂输出
kubectl get pods -o go-template='{{range .items}}{{.metadata.name}}{{"\t"}}{{.status.podIP}}{{"\n"}}{{end}}'

# 表格输出
kubectl get pods -o go-template='{{printf "%-30s %-15s %-10s\n" "NAME" "IP" "STATUS"}}{{range .items}}{{printf "%-30s %-15s %-10s\n" .metadata.name .status.podIP .status.phase}}{{end}}'
```

### 5.3 kubectl 插件 (Krew)

```bash
# 安装 Krew (kubectl 插件管理器)
(
  set -x; cd "$(mktemp -d)" &&
  OS="$(uname | tr '[:upper:]' '[:lower:]')" &&
  ARCH="$(uname -m | sed -a 's/x86_64/amd64/' | sed 's/aarch64/arm64/')" &&
  curl -fsSLO "https://github.com/kubernetes-sigs/krew/releases/latest/download/krew-${OS}_${ARCH}.tar.gz" &&
  tar zxvf "krew-${OS}_${ARCH}.tar.gz" &&
  KREW=./krew-"${OS}_${ARCH}" &&
  "$KREW" install krew
)

export PATH="$PATH:$HOME/.krew/bin"

# 搜索插件
kubectl krew search

# 常用插件
kubectl krew install tail                     # 日志着色
kubectl krew install ns                      # 切换 namespace
kubectl krew install ctx                     # 切换 context
kubectl krew install tree                    # 资源树
kubectl krew install whoami                  # 当前身份
kubectl krew install images                  # 镜像信息
kubectl krew install outdated                # 检查过期镜像
```

---

## 六、kubectl 调试技巧

### 6.1 临时调试容器

```bash
# 1.28+ 使用 ephemeralContainer
kubectl debug -it <pod-name> --image=busybox --target=<container-name>

# 示例
kubectl debug -it nginx-abc --image=busybox:1.36 --target=nginx

# 进入 Pod 主机网络命名空间
kubectl debug -it <pod-name> --image=busybox --target=nginx -- nsenter --target 1 --net
```

### 6.2 复制 Pod 调试

```bash
# 复制一个 Pod 进行调试 (不影响原 Pod)
kubectl debug <pod-name> -it --copy-to=debug-pod --image=busybox --container=debug -- sh

# 删除调试 Pod
kubectl delete pod debug-pod
```

### 6.3 故障排查清单

```text
Pod 不调度:
1. kubectl describe pod → Events 段
2. 检查节点资源: kubectl describe node
3. 检查 affinity/taints/tolerations
4. kubectl get events --sort-by='.lastTimestamp'

Pod Pending:
1. 资源不足 (CPU/内存)
2. 没有匹配的节点
3. PV/PVC 未绑定
4. 镜像拉取失败

Pod Running 但服务不通:
1. kubectl exec 进入容器测试
2. kubectl port-forward 本地测试
3. 检查 Service/Endpoints
4. 检查 NetworkPolicy
5. 检查 readiness probe

Pod CrashLoopBackOff:
1. kubectl logs --previous
2. 检查 imagePullSecrets
3. 检查 liveness probe
4. 检查资源配置 (OOMKilled)
```

---

## 核心要点速记

### kubectl 速查

```text
查: get / describe / logs
改: apply / edit / scale / patch
删: delete
调试: exec / logs / port-forward / debug
集群: cluster-info / top / cordon / drain
配置: config
```

### YAML 速查

```text
必填: apiVersion / kind / metadata.name
spec: 期望状态
status: 实际状态 (K8s 维护)

缩进: 2 空格, 不要 Tab
列表: - item
注释: #
```

### 高频命令

```bash
kubectl get pods -A                    # 所有 Pod
kubectl describe pod <pod>             # 详情
kubectl logs -f <pod>                  # 日志
kubectl exec -it <pod> -- bash         # 进入
kubectl apply -f file.yaml            # 应用
kubectl delete -f file.yaml           # 删除
kubectl rollout undo deployment/<name>  # 回滚
```

### YAML 模板

```yaml
apiVersion: <group>/<version>     # 必填
kind: <ResourceType>              # 必填
metadata:
  name: <name>                    # 必填
  namespace: <ns>
  labels: {key: value}
  annotations: {key: value}
spec:                             # 期望状态
  ...
status:                           # 实际状态 (不要写)
  ...
```

---

## 参考

- **kubectl 速查表**: https://kubernetes.io/docs/reference/kubectl/cheatsheet/
- **kubectl 命令参考**: https://kubernetes.io/docs/reference/generated/kubectl/kubectl-commands
- **YAML 教程**: https://yaml.org/spec/
- **JSONPath**: https://goessner.net/articles/JsonPath/
- **Krew 插件**: https://krew.sigs.k8s.io/
