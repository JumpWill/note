# ConfigMap、Secret 与配置管理 (Configuration)

> 本章讲解 K8s 的配置管理:ConfigMap、Secret、环境变量注入与最佳实践。

## 一、ConfigMap 概述

### 1.1 为什么需要 ConfigMap

```text
问题: 应用配置与镜像耦合
   - 配置硬编码在镜像中
   - 不同环境 (dev/test/prod) 需要不同配置
   - 配置变更需要重新构建镜像

ConfigMap 解决方案:
   - 配置与镜像解耦
   - 配置以 K8s 资源形式存储
   - 多种注入方式 (env / volume)
   - 修改 ConfigMap 实时生效 (volume 方式)
```

### 1.2 ConfigMap 核心特性

```text
- 存储非机密配置 (URL、端口、配置文件)
- 以 KV 或完整文件形式存储
- 注入方式:
  - 环境变量 (env)
  - 命令行参数 (args)
  - 配置文件 (volume)
- 修改后:
  - envFrom env: 不会自动更新 (Pod 重启才生效)
  - volume mount: 自动更新 (延迟约 30-60s)
```

---

## 二、ConfigMap 创建

### 2.1 命令式

```bash
# 单个 key-value
kubectl create configmap app-config \
  --from-literal=db.host=mysql \
  --from-literal=db.port=3306

# 从文件创建 (文件名作为 key)
kubectl create configmap app-config \
  --from-file=config.yaml \
  --from-file=app.properties

# 从目录创建
kubectl create configmap app-config \
  --from-file=./config-dir/

# 查看
kubectl get configmap
kubectl get cm           # 简写
kubectl describe cm app-config
```

### 2.2 声明式 (YAML)

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
  namespace: default
  labels:
    app: my-app
data:
  # 简单键值对
  db.host: "mysql.default.svc.cluster.local"
  db.port: "3306"
  log.level: "INFO"
  
  # 完整配置文件 (用 | 多行)
  application.yml: |
    server:
      port: 8080
      servlet:
        context-path: /api
    spring:
      datasource:
        url: jdbc:mysql://mysql:3306/mydb
        username: app
        password: ${DB_PASSWORD}
      redis:
        host: redis
        port: 6379
  
  nginx.conf: |
    worker_processes auto;
    events {
        worker_connections 1024;
    }
    http {
        upstream backend {
            server 127.0.0.1:8080;
        }
        server {
            listen 80;
            location / {
                proxy_pass http://backend;
            }
        }
    }
  
  # 二进制数据 (需要 base64 编码)
  binaryData:
    cert.pem: <base64-encoded-pem>
  
  # 不可变 (1.21+)
  immutable: false
```

### 2.3 ConfigMap 操作

```bash
# 查看 YAML
kubectl get cm app-config -o yaml

# 编辑
kubectl edit cm app-config

# 删除
kubectl delete cm app-config

# 查看指定 key
kubectl get cm app-config -o jsonpath='{.data.db\.host}'
```

---

## 三、ConfigMap 注入方式

### 3.1 方式 1:环境变量 (env)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
spec:
  template:
    spec:
      containers:
      - name: app
        image: my-app:1.0
        env:
        # 方式 1: 单个 key
        - name: DB_HOST
          valueFrom:
            configMapKeyRef:
              name: app-config
              key: db.host
              optional: false    # 必须存在

        # 方式 2: 整个 ConfigMap 转环境变量
        envFrom:
        - configMapRef:
            name: app-config
            prefix: CONFIG_    # 可选,加前缀

  # 自动更新: 不支持 (Pod 重启才生效)
```

### 3.2 方式 2:挂载为 Volume (推荐)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
spec:
  template:
    spec:
      containers:
      - name: app
        image: my-app:1.0
        volumeMounts:
        # 整个 ConfigMap 挂载为目录
        - name: config-volume
          mountPath: /etc/config
          readOnly: true

        # 单个 key 挂载为文件
        - name: config-volume
          mountPath: /etc/app.properties
          subPath: app.properties
          readOnly: true

      volumes:
      - name: config-volume
        configMap:
          name: app-config
          # 可选: 只挂载部分 key
          items:
          - key: application.yml
            path: app.yml
          - key: nginx.conf
            path: nginx.conf

  # 自动更新: 支持 (kubelet 定期刷新,延迟 ~30s)
```

### 3.3 方式 3:命令行参数

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
spec:
  template:
    spec:
      containers:
      - name: app
        image: my-app:1.0
        env:
        - name: DB_HOST
          valueFrom:
            configMapKeyRef:
              name: app-config
              key: db.host
        command: ["./start.sh"]
        args:
        - "--host=$(DB_HOST)"
        - "--port=8080"
```

### 3.4 三种方式对比

| 方式 | 实时更新 | 适用场景 |
|------|---------|---------|
| **环境变量 (env)** | ❌ Pod 重启 | 启动时需要、不常变更 |
| **Volume 挂载** | ✅ 自动 (~30s) | 配置文件,频繁变更 |
| **命令行参数** | ❌ Pod 重启 | 启动参数 |

---

## 四、ConfigMap 实战

### 4.1 多环境配置

```yaml
# base-config (通用配置)
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-base-config
data:
  app.name: "my-app"
  app.version: "1.0.0"
  log.level: "INFO"

---
# prod-config (生产覆盖)
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-prod-config
  namespace: production
data:
  db.host: "prod-mysql.cluster.local"
  log.level: "WARN"
```

### 4.2 热更新实战

```bash
# 1. 创建 ConfigMap
kubectl create cm app-config --from-literal=log.level=INFO

# 2. Deployment 挂载为 volume
# (Pod 中有 /etc/config/log.level = INFO)

# 3. 修改 ConfigMap
kubectl edit cm app-config
# 改为 log.level = DEBUG

# 4. 等待 ~30s,容器内文件自动更新
kubectl exec -it <pod> -- cat /etc/config/log.level
# 输出: DEBUG
```

### 4.3 完整示例

```yaml
# ===== ConfigMap =====
apiVersion: v1
kind: ConfigMap
metadata:
  name: web-config
data:
  application.yml: |
    server:
      port: 8080
    spring:
      profiles:
        active: production
  logback.xml: |
    <configuration>
      <appender name="STDOUT" class="ch.qos.logback.core.ConsoleAppender">
        <encoder>
          <pattern>%d{HH:mm:ss} %-5level %logger{36} - %msg%n</pattern>
        </encoder>
      </appender>
      <root level="INFO">
        <appender-ref ref="STDOUT" />
      </root>
    </configuration>

---
# ===== Deployment =====
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
spec:
  replicas: 3
  selector:
    matchLabels:
      app: web
  template:
    metadata:
      labels:
        app: web
    spec:
      containers:
      - name: web
        image: myorg/web:1.0
        ports:
        - containerPort: 8080
        volumeMounts:
        - name: config
          mountPath: /app/config
        - name: logs
          mountPath: /app/logs
        env:
        - name: JAVA_OPTS
          valueFrom:
            configMapKeyRef:
              name: web-config
              key: log.level
              optional: true
              # 注意: ConfigMap key 含 "." 需用 \ 转义 YAML
              # 这里实际 key 是 "log.level"
        resources:
          requests:
            cpu: 200m
            memory: 256Mi
          limits:
            cpu: 1000m
            memory: 512Mi
      volumes:
      - name: config
        configMap:
          name: web-config
      - name: logs
        emptyDir: {}
```

---

## 五、Secret 概述

### 5.1 Secret 与 ConfigMap 区别

| 维度 | ConfigMap | Secret |
|------|-----------|--------|
| 用途 | 非机密配置 | 密码、密钥、Token |
| 存储 | 明文 | base64 编码 (非加密!) |
| 大小限制 | 1MB | 1MB |
| 默认 | 明文 etcd | etcd (需配置加密) |
| K8s 版本 | 全部 | 全部 |

### 5.2 Secret 类型

```text
1. Opaque          - 自定义数据 (最常用)
2. kubernetes.io/service-account-token  - SA Token
3. kubernetes.io/dockerconfigjson    - Docker Registry 凭证
4. kubernetes.io/tls                 - TLS 证书
5. kubernetes.io/ssh-auth            - SSH 凭证
6. bootstrap.kubernetes.io/token     - 节点引导 Token
```

### 5.3 创建 Secret

```bash
# 命令式 (单 key)
kubectl create secret generic db-secret \
  --from-literal=username=admin \
  --from-literal=password='S3cr3t!'

# 从文件
kubectl create secret generic tls-secret \
  --from-file=tls.crt \
  --from-file=tls.key

# Docker Registry 凭证
kubectl create secret docker-registry my-registry \
  --docker-server=docker.io \
  --docker-username=myuser \
  --docker-password=mypassword \
  --docker-email=my@email.com

# TLS Secret
kubectl create secret tls tls-secret \
  --cert=path/to/tls.crt \
  --key=path/to/tls.key
```

### 5.4 声明式 (YAML)

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: db-secret
  namespace: production
type: Opaque                # 自定义类型
data:
  # 注意: 必须是 base64 编码
  username: YWRtaW4=        # admin
  password: UzNjcjN0IQ==   # S3cr3t!
  
  # 1.21+ 支持 stringData (明文,自动 base64)
  stringData:
    config.ini: |
      [database]
      host=mysql
      port=3306
      user=admin
```

### 5.5 Secret 使用

#### 方式 1:环境变量

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
spec:
  template:
    spec:
      containers:
      - name: app
        env:
        - name: DB_USER
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: username
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: password

        # 整体挂载
        envFrom:
        - secretRef:
            name: db-secret
```

#### 方式 2:挂载为 Volume

```yaml
spec:
  containers:
  - name: app
    volumeMounts:
    - name: secret-volume
      mountPath: /etc/secrets
      readOnly: true

  volumes:
  - name: secret-volume
    secret:
      secretName: db-secret
      # 可选: 指定 items
      items:
      - key: password
        path: db-password      # 容器内 /etc/secrets/db-password
      defaultMode: 0400         # 文件权限
```

#### 方式 3:imagePullSecrets (镜像拉取)

```yaml
spec:
  imagePullSecrets:
  - name: my-registry-secret  # 引用 docker-registry 类型 Secret
  
  containers:
  - name: app
    image: registry.example.com/myorg/private-app:1.0
```

---

## 六、Secret 安全最佳实践

### 6.1 etcd 加密

```text
默认: Secret 在 etcd 中明文存储 (只 base64 编码)
生产: 必须开启 etcd 加密

K8s 1.13+ 提供 KMS 加密 Secret 的特性:
```

```yaml
# 1. 创建加密配置
apiVersion: apiserver.config.k8s.io/v1
kind: EncryptionConfiguration
resources:
  - resources:
    - secrets
    providers:
    - aescbc:
        keys:
        - name: key1
          secret: <base64-encoded-32-byte-key>
    - identity: {}

# 2. 重新配置 kube-apiserver
# 在 /etc/kubernetes/manifests/kube-apiserver.yaml 添加
# --encryption-provider-config=/etc/kubernetes/encryption-config.yaml

# 3. 重启 kube-apiserver
```

### 6.2 访问控制

```yaml
# RBAC 限制 Secret 访问 (推荐)
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: production
  name: secret-reader
rules:
- apiGroups: [""]
  resources: ["secrets"]
  resourceNames: ["db-secret"]
  verbs: ["get"]
```

### 6.3 不在镜像中硬编码

```text
❌ 错误: ENV DB_PASSWORD=secret123 (在 Dockerfile)
   - 镜像被共享后,密码泄露
   - 改密码需重建镜像

✅ 正确: 使用 Secret 注入
   - 镜像纯净,配置动态注入
```

### 6.4 使用外部密钥管理

```text
生产推荐: External Secrets Operator (ESO)
  - 从 AWS Secrets Manager / HashiCorp Vault / GCP Secret Manager 同步
  - K8s Secret 作为本地缓存
```

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: db-credentials
spec:
  secretStoreRef:
    name: aws-secrets-manager
    kind: ClusterSecretStore
  target:
    name: db-secret
  data:
  - secretKey: db-password
    remoteRef:
      key: production/database
      property: password
```

---

## 七、ConfigMap 与 Secret 实战案例

### 7.1 Spring Boot 应用

```yaml
# application.yml
apiVersion: v1
kind: ConfigMap
metadata:
  name: spring-app-config
data:
  application.yml: |
    server:
      port: 8080
    spring:
      application:
        name: my-app
      profiles:
        active: production
      datasource:
        url: jdbc:mysql://mysql:3306/mydb
        username: ${DB_USER}
        password: ${DB_PASSWORD}
      redis:
        host: redis
        port: 6379

---
apiVersion: v1
kind: Secret
metadata:
  name: spring-app-secret
type: Opaque
stringData:
  DB_USER: appuser
  DB_PASSWORD: 'V3ryS3cr3t!'

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: spring-app
spec:
  replicas: 3
  selector:
    matchLabels:
      app: spring-app
  template:
    metadata:
      labels:
        app: spring-app
    spec:
      containers:
      - name: app
        image: myorg/spring-app:1.0
        ports:
        - containerPort: 8080
        volumeMounts:
        - name: config
          mountPath: /app/config
        env:
        - name: DB_USER
          valueFrom:
            secretKeyRef:
              name: spring-app-secret
              key: DB_USER
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: spring-app-secret
              key: DB_PASSWORD
      volumes:
      - name: config
        configMap:
          name: spring-app-config
```

### 7.2 多环境部署

```yaml
# 使用 Kustomize 或 Helm 区分环境

# base/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  log.level: INFO
---
# overlays/dev/configmap-patch.yaml
- op: replace
  path: /data/log\.level
  value: DEBUG
---
# overlays/prod/configmap-patch.yaml
- op: replace
  path: /data/log\.level
  value: WARN
```

---

## 八、不可变 ConfigMap / Secret (K8s 1.21+)

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  log.level: INFO
immutable: true              # 创建后不可修改

# 优点:
# - 防止意外修改
# - kubelet 不需要 watch (减少 API Server 负载)
# - 提升性能
```

适用: 不会变更的配置 (证书、配置常量)

---

## 核心要点速记

### ConfigMap vs Secret

```text
ConfigMap: 非机密配置 (URL、端口、配置项)
Secret:    机密信息 (密码、Token、证书)
都支持: env / volume / 命令行参数 三种注入方式
```

### 注入方式选择

```text
环境变量 (env):    启动参数,变更需重启
Volume 挂载:         配置文件,自动更新 (延迟 ~30s) ← 推荐
命令行参数 (args):  启动参数,需重启
```

### Secret 安全

```text
1. 必须开启 etcd 加密 (EncryptionConfiguration)
2. 用 RBAC 限制访问
3. 不在镜像中硬编码
4. 生产推荐 External Secrets Operator
5. 使用 immutable Secret (1.21+) 减少 watch
```

### ConfigMap 实战

```text
- ConfigMap 挂载到 /etc/config
- 修改后 ~30s 自动更新
- 不适合大型文件 (> 1MB 用 PV)
- 不可变 ConfigMap 性能更好
```

### YAML 转义

```text
ConfigMap/Secret key 可包含 . - _ 等字符
YAML 中 . 需转义: db\.host
```

---

## 参考

- **ConfigMap**: https://kubernetes.io/docs/concepts/configuration/configmap/
- **Secret**: https://kubernetes.io/docs/concepts/configuration/secret/
- **etcd 加密**: https://kubernetes.io/docs/tasks/administer-cluster/encrypt-data/
- **External Secrets**: https://external-secrets.io/
