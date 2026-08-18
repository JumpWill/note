# Ingress 与 Gateway API (Ingress & Gateway)

> 本章系统讲解 K8s 的 HTTP 入口方案:Ingress 资源、Nginx Ingress Controller 与新一代 Gateway API。

## 一、Ingress 概述

### 1.1 为什么需要 Ingress

```text
问题: Service 只能 L4 (IP + Port) 暴露
   - ClusterIP: 集群内
   - NodePort: 性能差,需要 30000+ 端口
   - LoadBalancer: 每个 Service 一个 LB,成本高

Ingress 解决:
   - L7 (HTTP/HTTPS) 路由
   - 基于域名 (Host) 路由
   - 基于路径 (Path) 路由
   - TLS 终止
   - 一个 LB 入口,多服务路由
```

### 1.2 Ingress 架构

```text
外部用户
   ↓ HTTPS:443
[Nginx Ingress Controller]  ← 单个 LoadBalancer IP
   ↓ (按 Host / Path 分发)
   ├─ app.example.com → service-a:80
   ├─ api.example.com → service-b:8080
   └─ app.example.com/admin → service-c:8080

Ingress Controller:
   - Nginx / Traefik / HAProxy / Envoy
   - 监听 80/443 端口
   - 解析 Ingress 资源生成配置
   - 动态加载 (无需重启)
```

### 1.3 主流 Ingress Controller

| Controller | 特点 |
|-----------|------|
| **Nginx Ingress** | 最常用,功能全,文档丰富 |
| **Traefik** | 自动服务发现,配置简单 |
| **HAProxy Ingress** | 高性能 |
| **Contour** | Envoy-based |
| **Istio Gateway** | 服务网格集成 |
| **Apache APISIX** | 高性能,云原生 |

---

## 二、Ingress 资源定义

### 2.1 简单示例

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-app-ingress
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  ingressClassName: nginx
  rules:
  - host: app.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: web-service
            port:
              number: 80
```

### 2.2 pathType 类型

```text
- Prefix      - 前缀匹配 (推荐)
              /api 匹配 /api, /api/v1, /api/users
              但不匹配 /application

- Exact       - 精确匹配
              /api 仅匹配 /api
              不匹配 /api/ 或 /api/v1

- ImplementationSpecific  - 实现决定 (Nginx: 正则)
```

### 2.3 完整 Ingress 示例

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: multi-app-ingress
  annotations:
    # Nginx 配置
    nginx.ingress.kubernetes.io/rewrite-target: /$2
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/force-ssl-redirect: "true"
    # 限流
    nginx.ingress.kubernetes.io/limit-rps: "100"
    # CORS
    nginx.ingress.kubernetes.io/cors-allow-origin: "*"
    # 会话保持
    nginx.ingress.kubernetes.io/affinity: "cookie"
    # 超时
    nginx.ingress.kubernetes.io/proxy-connect-timeout: "30"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "60"

spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - app.example.com
    - api.example.com
    secretName: app-tls-secret   # 引用 Secret 存证书

  rules:
  # 规则 1: app.example.com
  - host: app.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: web-service
            port:
              number: 80

  # 规则 2: api.example.com/api/* → api-service
  - host: api.example.com
    http:
      paths:
      - path: /api(/|$)(.*)
        pathType: ImplementationSpecific
        backend:
          service:
            name: api-service
            port:
              number: 8080

  # 规则 3: 默认后端 (无 host 匹配)
  - http:
      paths:
      - path: /default
        pathType: Prefix
        backend:
          service:
            name: default-service
            port:
              number: 80
```

---

## 三、Nginx Ingress Controller

### 3.1 安装

```bash
# Helm 安装 (推荐)
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update

# 创建 namespace
kubectl create namespace ingress-nginx

# 安装 (使用 LoadBalancer 类型)
helm install nginx-ingress ingress-nginx/ingress-nginx \
  --namespace ingress-nginx \
  --set controller.service.type=LoadBalancer \
  --set controller.service.annotations."service\.beta\.kubernetes\.io/aws-load-balancer-type"="nlb"

# 或使用 NodePort (用于测试)
helm install nginx-ingress ingress-nginx/ingress-nginx \
  --namespace ingress-nginx \
  --set controller.service.type=NodePort
```

### 3.2 安装验证

```bash
# 查看 Pod
kubectl get pods -n ingress-nginx

# 查看 Service (获取 LoadBalancer IP)
kubectl get svc -n ingress-nginx
# NAME                       TYPE           CLUSTER-IP    EXTERNAL-IP
# nginx-ingress-controller   LoadBalancer   10.96.10.50  a123.us-east-1.elb.amazonaws.com

# 测试
curl -H "Host: app.example.com" http://a123.us-east-1.elb.amazonaws.com/
```

### 3.3 IngressClass

```yaml
apiVersion: networking.k8s.io/v1
kind: IngressClass
metadata:
  name: nginx
  annotations:
    ingressclass.kubernetes.io/is-default-class: "true"
spec:
  controller: k8s.io/ingress-nginx
  parameters:
    apiGroup: k8s.example.com
    kind: NginxIngressParameters
    name: external
```

### 3.4 高级 Nginx Ingress 配置

#### 限流

```yaml
metadata:
  annotations:
    # 每秒 100 请求
    nginx.ingress.kubernetes.io/limit-rps: "100"
    # 每 IP 每秒 10 请求
    nginx.ingress.kubernetes.io/limit-rps: "10"
    # 每分钟 1000 请求
    nginx.ingress.kubernetes.io/limit-rpm: "1000"
```

#### 跨域 (CORS)

```yaml
metadata:
  annotations:
    nginx.ingress.kubernetes.io/cors-allow-origin: "https://app.example.com"
    nginx.ingress.kubernetes.io/cors-allow-methods: "GET, POST, OPTIONS"
    nginx.ingress.kubernetes.io/cors-allow-headers: "DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range,Authorization"
    nginx.ingress.kubernetes.io/cors-allow-credentials: "true"
    nginx.ingress.kubernetes.io/cors-max-age: "86400"
```

#### 客户端证书认证

```yaml
metadata:
  annotations:
    nginx.ingress.kubernetes.io/auth-tls-verify-client: "on"
    nginx.ingress.kubernetes.io/auth-tls-secret: "ca-secret"
    nginx.ingress.kubernetes.io/auth-tls-verify-depth: "1"
    nginx.ingress.kubernetes.io/auth-tls-error-page: "https://example.com/error"
```

#### WebSocket

```yaml
metadata:
  annotations:
    # 默认支持 WebSocket,无需特殊配置
    nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "3600"
```

#### URL 重写

```yaml
metadata:
  annotations:
    # /api/v1/users → /users
    nginx.ingress.kubernetes.io/rewrite-target: /$2
spec:
  rules:
  - host: api.example.com
    http:
      paths:
      - path: /api/v1(/|$)(.*)
        pathType: ImplementationSpecific
        backend:
          service:
            name: api-service
            port:
              number: 80
```

### 3.5 TLS/HTTPS

#### 自签名证书 (测试)

```bash
# 1. 创建自签名证书
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout tls.key -out tls.crt \
  -subj "/CN=app.example.com"

# 2. 创建 Secret
kubectl create secret tls app-tls-secret \
  --cert=tls.crt --key=tls.key
```

#### Let's Encrypt (cert-manager)

```bash
# 安装 cert-manager
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.14.0/cert-manager.yaml

# 创建 ClusterIssuer
cat << EOF | kubectl apply -f -
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@example.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: nginx
EOF
```

```yaml
# Ingress 自动签发证书
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
  name: my-app
spec:
  tls:
  - hosts:
    - app.example.com
    secretName: my-app-tls
  rules:
  - host: app.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: web-service
            port:
              number: 80
```

---

## 四、Ingress 实战

### 4.1 单域名多服务

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: monolith
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /$2
spec:
  rules:
  - host: app.example.com
    http:
      paths:
      # /api → backend-api
      - path: /api(/|$)(.*)
        pathType: ImplementationSpecific
        backend:
          service:
            name: backend-api
            port:
              number: 8080

      # /admin → admin-dashboard
      - path: /admin(/|$)(.*)
        pathType: ImplementationSpecific
        backend:
          service:
            name: admin-dashboard
            port:
              number: 9000

      # / → main-website
      - path: /
        pathType: Prefix
        backend:
          service:
            name: main-website
            port:
              number: 80
```

### 4.2 多域名多服务

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: multi-tenant
spec:
  rules:
  - host: tenant-a.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: tenant-a
            port:
              number: 80

  - host: tenant-b.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: tenant-b
            port:
              number: 80

  - host: tenant-c.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: tenant-c
            port:
              number: 80
```

### 4.3 灰度发布 (Canary)

```yaml
# 主版本 (90% 流量)
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: web-v1
  annotations:
    nginx.ingress.kubernetes.io/canary-weight: "90"
spec:
  rules:
  - host: app.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: web-v1
            port:
              number: 80

---
# 新版本 (10% 流量)
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: web-v2
  annotations:
    nginx.ingress.kubernetes.com/canary: "true"
    nginx.ingress.kubernetes.io/canary-weight: "10"
spec:
  rules:
  - host: app.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: web-v2
            port:
              number: 80
```

### 4.4 基于 Header 的灰度

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: web-v2-canary
  annotations:
    nginx.ingress.kubernetes.io/canary: "true"
    nginx.ingress.kubernetes.io/canary-by-header: "X-Canary"
    nginx.ingress.kubernetes.io/canary-by-header-value: "true"
spec:
  rules:
  - host: app.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: web-v2
            port:
              number: 80
```

---

## 五、Traefik (备选 Ingress Controller)

### 5.1 Traefik 特点

```text
- Go 编写,性能好
- 自动服务发现 (K8s, Docker, Consul...)
- 自动 HTTPS (Let's Encrypt 集成)
- Web UI (Dashboard)
- 配置简单 (Helm values)
- 支持 HTTP/2, HTTP/3, gRPC
```

### 5.2 Helm 安装

```bash
helm repo add traefik https://helm.traefik.io/traefik
helm repo update

helm install traefik traefik/traefik \
  --namespace traefik --create-namespace \
  --set service.type=LoadBalancer \
  --set dashboard.enabled=true \
  --set dashboard.domain=dashboard.example.com \
  --set ingressRoute.dashboard.enabled=true
```

### 5.3 IngressRoute (Traefik 资源)

```yaml
apiVersion: traefik.containo.us/v1alpha1
kind: IngressRoute
metadata:
  name: my-app
  namespace: default
spec:
  entryPoints:
  - websecure
  routes:
  - match: Host(`app.example.com`)
    kind: Rule
    services:
    - name: web-service
      port: 80
  tls:
    certResolver: letsencrypt
```

---

## 六、Gateway API (下一代)

### 6.1 概念

**Gateway API** (SIG Network)是 K8s 新一代 L4/L7 路由 API,目标是替代 Ingress。

```text
优势:
- 角色化 (Role-oriented): 基础设施提供者、应用开发者、运维
- 多协议 (HTTP, TCP, UDP, gRPC, TLS)
- 跨命名空间路由
- 流量切分、镜像、重定向

核心资源:
1. GatewayClass   - 基础设施类 (类似 IngressClass)
2. Gateway        - 入口实例 (类似 Ingress Controller)
3. HTTPRoute      - HTTP 路由
4. TCPRoute       - TCP 路由
5. UDPRoute       - UDP 路由
6. TLSRoute       - TLS 路由
```

### 6.2 Gateway API vs Ingress

| 维度 | Ingress | Gateway API |
|------|---------|-------------|
| 状态 | 稳定 (GA) | Beta (1.0+) |
| 协议 | HTTP/HTTPS | HTTP, TCP, UDP, gRPC, TLS |
| 跨命名空间 | 受限 | 原生支持 |
| 角色化 | 弱 | 强 (Infra / Dev) |
| 后端 | Service | Service + HTTPRoute 权重 |
| 控制器 | Nginx / Traefik | Istio / Contour / Nginx |

### 6.3 Gateway API 示例

```yaml
# 1. GatewayClass
apiVersion: gateway.networking.k8s.io/v1
kind: GatewayClass
metadata:
  name: istio
spec:
  controllerName: istio.io/gateway-controller
---
# 2. Gateway (集群级)
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: my-gateway
  namespace: infra
spec:
  gatewayClassName: istio
  listeners:
  - name: http
    port: 80
    protocol: HTTP
    allowedRoutes:
      namespaces:
        from: All
---
# 3. HTTPRoute (应用级,可跨 ns)
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: my-app
  namespace: app
spec:
  parentRefs:
  - name: my-gateway
    namespace: infra
  hostnames: ["app.example.com"]
  rules:
  - matches:
    - path: /api
    backendRefs:
    - name: api-service
      port: 8080
  - matches:
    - path: /
    backendRefs:
    - name: web-service
      port: 80
```

### 6.4 Gateway API 实战 (Istio)

```bash
# 安装 Istio (含 Gateway API)
istioctl install --set profile=demo -y

# 启用 Gateway API CRD
kubectl get crd | grep gateway.networking.k8s.io

# 部署应用
kubectl create namespace app
kubectl apply -f app.yaml -n app

# 创建 Gateway
kubectl apply -f gateway.yaml -n infra

# 创建 HTTPRoute
kubectl apply -f httproute.yaml -n app

# 获取 Gateway IP
kubectl get gateway my-gateway -n infra
```

---

## 七、Ingress 监控与运维

### 7.1 监控关键指标

```promql
# 请求率
sum(rate(nginx_ingress_controller_requests[5m])) by (ingress)

# 错误率
sum(rate(nginx_ingress_controller_requests{status=~"5.."}[5m])) by (ingress)
/
sum(rate(nginx_ingress_controller_requests[5m])) by (ingress)

# P99 延迟
histogram_quantile(0.99, sum(rate(nginx_ingress_controller_request_duration_seconds_bucket[5m])) by (le, ingress))

# 当前活跃连接
sum(nginx_ingress_controller_nginx_process_connections) by (state)
```

### 7.2 常用运维命令

```bash
# 查看所有 Ingress
kubectl get ingress -A
kubectl get ing              # 简写

# 查看详情
kubectl describe ingress <name>

# 查看后端 Service 健康
kubectl get endpoints -n ingress-nginx

# 查看 Nginx 配置 (debug)
kubectl exec -it <nginx-ingress-pod> -n ingress-nginx -- nginx -T

# 重载配置 (修改 ConfigMap 后)
kubectl exec -it <nginx-ingress-pod> -n ingress-nginx -- nginx -s reload

# 查看访问日志
kubectl logs -f <nginx-ingress-pod> -n ingress-nginx

# 查看 Ingress Controller 日志
kubectl logs -l app.kubernetes.io/name=ingress-nginx -n ingress-nginx
```

### 7.3 性能优化

```yaml
# 资源限制
resources:
  requests:
    cpu: 500m
    memory: 512Mi
  limits:
    cpu: 2000m
    memory: 2Gi

# 副本数 (高可用 + 性能)
replicaCount: 3

# 启用 HPA
autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 10
  targetCPUUtilizationPercentage: 60

# 节点选择 (独立节点池)
nodeSelector:
  ingress: "true"

# 容忍专用节点
tolerations:
- key: "ingress"
    operator: "Equal"
    value: "true"
    effect: "NoSchedule"
```

---

## 核心要点速记

### Ingress vs Gateway API

```text
Ingress (v1, GA):
  - 单命名空间路由为主
  - HTTP/HTTPS
  - 主流控制器: Nginx, Traefik, HAProxy

Gateway API (v1, Beta+):
  - 跨命名空间路由
  - HTTP/TCP/UDP/gRPC/TLS
  - 下一代标准
  - 控制器: Istio, Contour, NGINX Gateway Fabric
```

### Nginx Ingress 核心注解

```yaml
rewrite-target        # URL 重写
ssl-redirect         # HTTPS 强制
limit-rps            # 限流
cors-allow-origin    # CORS
canary               # 灰度
proxy-read-timeout   # 超时
affinity             # 会话保持
auth-tls-verify-client  # 客户端证书认证
```

### 部署选型

```text
- 通用场景 → Nginx Ingress (最成熟)
- 自动配置 → Traefik (自动服务发现)
- 服务网格 → Istio Gateway (功能最强)
- 新集群 → Gateway API (未来标准)
```

### TLS 自动化

```bash
# cert-manager + Let's Encrypt
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/latest/download/cert-manager.yaml

# 配置 ClusterIssuer 自动签发
# Ingress 注解: cert-manager.io/cluster-issuer: letsencrypt-prod
```

### 灰度发布 (Canary)

```yaml
# 按权重
nginx.ingress.kubernetes.io/canary-weight: "10"  # 10% 流量

# 按 Header
nginx.ingress.kubernetes.io/canary-by-header: "X-Canary"
nginx.ingress.kubernetes.io/canary-by-header-value: "true"

# 按 Cookie
nginx.ingress.kubernetes.io/canary-by-cookie: "version"
```

---

## 参考

- **Ingress**: https://kubernetes.io/docs/concepts/services-networking/ingress/
- **Ingress Controllers**: https://kubernetes.io/docs/concepts/services-networking/ingress-controllers/
- **Gateway API**: https://gateway-api.sigs.k8s.io/
- **Nginx Ingress**: https://kubernetes.github.io/ingress-nginx/
- **Traefik**: https://doc.traefik.io/traefik/
- **cert-manager**: https://cert-manager.io/docs/
