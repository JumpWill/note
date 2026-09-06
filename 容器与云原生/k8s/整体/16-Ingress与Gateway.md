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

### 4.3 灰度发布 (Canary) —— 真实灰度全流程

> **核心模型**：同一域名跑两个独立的 Deployment + Service（`myapp-stable` 和 `myapp-canary`），靠 canary-weight 切流量。
> 网上很多示例只贴两份 yaml，**没说完整流程怎么走**——下面是从 v1 切到 v2 的端到端实操。

#### 4.3.1 两个 Deployment + 两个 Service 起步

```yaml
# 主版本（v1）—— 副本数 = 生产正常值，比如 5
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp-stable
spec:
  replicas: 1                              # 灰度时先压到最小
  selector: { matchLabels: { app: myapp, track: stable } }
  template:
    metadata:
      labels: { app: myapp, track: stable }
    spec:
      containers:
        - name: myapp
          image: myapp:v1
---
apiVersion: v1
kind: Service
metadata:
  name: myapp-stable
spec:
  selector: { app: myapp, track: stable }
  ports: [{ port: 80, targetPort: 8080 }]
---
# 灰度版本（v2）—— 副本数要多一点，才能扛住生产流量
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp-canary
spec:
  replicas: 4                              # 必须 ≥ 常态副本数（灰度跑满时这批 Pod 全接流量）
  selector: { matchLabels: { app: myapp, track: canary } }
  template:
    metadata:
      labels: { app: myapp, track: canary }
    spec:
      containers:
        - name: myapp
          image: myapp:v2
---
apiVersion: v1
kind: Service
metadata:
  name: myapp-canary
spec:
  selector: { app: myapp, track: canary }
  ports: [{ port: 80, targetPort: 8080 }]
```

#### 4.3.2 两个 Ingress —— 一个主，一个 canary

```yaml
# 主 Ingress（吃默认流量）
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: myapp
spec:
  rules:
  - host: app.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service: { name: myapp-stable, port: { number: 80 } }

---
# Canary Ingress —— 加 canary: "true" 标记
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: myapp-canary
  annotations:
    nginx.ingress.kubernetes.io/canary: "true"
    nginx.ingress.kubernetes.io/canary-weight: "10"     # ← canary 拿 10%
spec:
  rules:
  - host: app.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service: { name: myapp-canary, port: { number: 80 } }
```

#### 4.3.3 关键认知：`canary-weight` 是**单值**语义

```text
nginx.ingress.kubernetes.io/canary-weight: N
   └─ 含义：canary 拿 N%；old（主 Ingress）自动拿 (100 - N)%

所以**只改这一个数字**，不需要同时改两边：

  canary-weight: 10   →  old 90%   canary 10%
  canary-weight: 30   →  old 70%   canary 30%
  canary-weight: 70   →  old 30%   canary 70%
  canary-weight: 100  →  old 0%    canary 100%
```

#### 4.3.4 完整四阶段流程

```text
阶段一：真实灰度（v1 vs v2，版本不同，要慢）
  canary-weight: 10 → 30 → 70 → 100    小步观察，每次留 5–15 min 看监控

阶段二：趁 canary 满流时更新 old 镜像（v1 → v2）
  此时 old 零流量，更新零风险（用户访问的全是 canary Pod）
  set image + scale up old（接下来 old 要扛全量）

阶段三：流量回迁（v2 vs v2，版本相同）
  canary-weight: 100 → 0                一步到位（同版本零风险）

阶段四：清理
  先删 canary Ingress → 再删 canary Service → 最后删 canary Deployment
  ⚠️ 顺序反了会瞬间 502
```

##### 阶段一：小步推进

```bash
# 每步观察 5–15 分钟，看错误率 / P99 / Pod 状态
kubectl annotate ingress myapp-canary -n prod \
  nginx.ingress.kubernetes.io/canary-weight=10 --overwrite

# 监控观察
watch 'kubectl get pods -n prod -l track=canary'
curl -s -o /dev/null -w "%{http_code}\n" https://app.example.com/
```

**节奏参考**：

| 阶段 | 权重 | 观察时长 | 关注指标 |
| --- | --- | --- | --- |
| 1 | 10% | 10 min | canary Pod 错误率、内存 |
| 2 | 30% | 15 min | 整体 P99 是否恶化 |
| 3 | 70% | 20 min | DB / Redis 等下游扛不扛得住 |
| 4 | 100% | 30 min | 全量压测，类似生产环境 |

##### 阶段二：趁零流量更新 old（⭐ 核心技巧）

```bash
# canary 已经 100% 流量的瞬间，old 零流量，趁机更新镜像
kubectl set image deployment/myapp-stable myapp=myapp:v2 -n prod

# old 副本数从 1 扩到 5（要扛住接下来的全量流量）
kubectl scale deployment/myapp-stable -n prod --replicas=5

# 滚动结束前，集群里会短暂同时存在：
#   1 个 v1 old Pod（零流量）+ 4 个 v2 canary Pod
# + 5 个 v2 old Pod（滚动中的新副本）
# = 9–10 个 Pod 资源峰值
```

**为什么这一步关键**：

> 整个方案的核心思路是：**用 canary 的 100% 流量掩护 old 的镜像更新**。
> 否则直接在 old 上 set image v1→v2 会触发滚动替换，期间新旧 Pod 并存——大部分流量打到老 Pod 上，新版本实际验证覆盖率不到 100%。
> 借 canary 满流的窗口更新 old，**保证切换后用户访问的是 100% 新版本**。

##### 阶段三：流量回迁（同版本 → 一步到位）

```bash
# 此时 old 已经是 v2，跟 canary 完全同版本——切流量零风险
kubectl annotate ingress myapp-canary -n prod \
  nginx.ingress.kubernetes.io/canary-weight=0 --overwrite

# 一行回迁完成，不需要 100→70→30→0 慢慢降
```

**判断标准**：

```text
版本不同（v1 vs v2）→ 必须小步 + 观察
版本相同（v2 vs v2）→ 直接切，零风险
```

##### 阶段四：清理（顺序关键）

```bash
# 1. 先删 canary Ingress（立刻让 canary 零流量、old 100%）
kubectl delete ingress myapp-canary -n prod

# 2. 再删 canary Service
kubectl delete service myapp-canary -n prod

# 3. 最后删 canary Deployment（释放 Pod）
kubectl delete deployment myapp-canary -n prod

# 4. 顺手清理旧的稳定 Ingress（如果当时写了两个版本的话）
# kubectl apply -f myapp-stable-only.yaml
```

⚠️ **顺序反了 = 502**：

- 删 Deployment → Ingress 还在 → 流量找不到 Pod → 502
- 删 Service → Ingress 还在 → 同上

#### 4.3.5 资源峰值预警

**假设**：生产常态副本数 = 5。

| 阶段 | Pod 数（old + canary） | 说明 |
| --- | --- | --- |
| 灰度中（old 90% / canary 10%） | 1 + 4 = **5** | 跟常态持平 |
| ① canary 推满 100% | 1 + 4 = **5** | old 零流量 |
| ② old 滚动更新 + scale 5 | 1–5 + 4 = **9（峰值）** | 新旧 Pod 短暂并存 |
| ③ 流量回迁完成 | 5 + 4 = **9** | 同版本，安全 |
| ④ 摘 Ingress + 删 Deployment | 5 = **5** | 回到常态 |

> ⚠️ **峰值 = 9 个 Pod**，比常态多 80%。
> 收敛前**确认节点资源够**，否则 old 扩容会卡 `Pending`、整个流程断在阶段二。
> 节点资源紧张时：**先 scale down canary 到最小**（比如 2），再扩 old——把峰值压到 5+2=7。

#### 4.3.6 一句话总结

> **真实灰度（不同版本，小步慢走）→ 趁 canary 满流时更新 old（零风险）→ 同版本一步回迁 → 先删 Ingress 再删 Svc/Deploy**

#### 4.3.7 监控指标与晋级标准（自动化灰度的量化依据）

> 前面四阶段假设"看监控没毛病就推下一步"——**到底看哪些指标？观察多久？阈值多少？**
> 这一节给出可执行的晋级/回退判定框架。

##### 4.3.7.1 必须监控的 4 类信号

```text
1. 可用性（错误率）—— 能不能用
   - HTTP 5xx 比例
   - 应用层 error / panic / exception 日志条数

2. 性能（延迟）—— 用得顺不顺
   - P50 / P95 / P99 响应时间
   - 慢调用（DB / RPC / 缓存）

3. 饱和度（资源）—— 撑不撑得住
   - Pod CPU / Memory 占用
   - 队列积压、连接池等待
   - 节点级资源余量

4. 流量分布 —— 比例对不对
   - canary 实际拿到流量是否 ≈ canary-weight 设置
   - 如果实际比例远低于设置（比如设 30% 实际 5%），Ingress 可能有问题
```

##### 4.3.7.2 关键原则：相对基线，不是绝对值

```text
❌ 错误率 ≤ 1% 才推
   → 老版本本来就 0.3%，新版本 0.8% 看似"达标"，实际涨了 2.6 倍

✅ canary 错误率 ≈ stable 错误率（允许 1.2–1.5 倍以内）
   → 老版本 0.3%，新版本 0.5% 算可控
   → 老版本 0.3%，新版本 1.5% 必须回退

所有指标都是：canary vs stable（同一个时间窗、同一种请求类型）
```

##### 4.3.7.3 晋级标准参考表

> 数字是常见经验值，**实际项目按业务敏感度调整**：
> 支付类（P0）→ 严苛；内容类（P2）→ 可放宽。

| 灰度阶段 | 观察窗口 | 错误率（canary / stable） | P99 延迟 | 资源 | 不达标处理 |
| --- | --- | --- | --- | --- | --- |
| 10% | 30 min | ≤ 1.5× | ≤ 1.3× | ≤ 1.5× | 暂停推进或回退 |
| 30% | 20 min | ≤ 1.3× | ≤ 1.2× | ≤ 1.3× | 暂停推进 |
| 50% | 15 min | ≤ 1.2× | ≤ 1.15× | ≤ 1.2× | 暂停推进 |
| 70% | 15 min | ≤ 1.1× | ≤ 1.1× | ≤ 1.15× | 暂停推进 |
| 100% | 30 min | ≈ stable | ≈ stable | ≈ stable | 直接回退 |

**采样口径**：

```text
窗口类型选 rolling window（最近 5 min），不是 single point（最近 1 s）
  → 避免抖动假阳

分桶：按 HTTP status code（2xx / 4xx / 5xx）+ 路由
  → 不要把 404 算成"错误"
  → 不要把所有 namespace 混算
```

##### 4.3.7.4 强回退触发器（任意一条命中立即回退，不观察）

```yaml
# 这些是硬规则，不在"灰度多少时间"逻辑内
- canary Pod 出现 CrashLoopBackOff
- 5xx 错误率绝对值 > 5%                     # 哪怕相对值低
- 核心链路（如下单）P99 翻倍
- 业务自定义 critical 告警触发
- 数据库连接池 / 下游 RPC 错误率突增
```

##### 4.3.7.5 落到代码：Prometheus 查询示例

```promql
# canary 5xx 率（最近 5 分钟）
sum(rate(http_requests_total{track="canary",status=~"5xx"}[5m]))
/
sum(rate(http_requests_total{track="canary"}[5m]))

# canary vs stable 错误率比值
  sum(rate(http_requests_total{track="canary",status=~"5xx"}[5m]))
/ sum(rate(http_requests_total{track="canary"}[5m]))
/
(
  sum(rate(http_requests_total{track="stable",status=~"5xx"}[5m]))
/ sum(rate(http_requests_total{track="stable"}[5m]))
)

# canary P99 延迟
histogram_quantile(0.99,
  sum(rate(http_request_duration_seconds_bucket{track="canary"}[5m])) by (le)
)
```

##### 4.3.7.6 SLO 视角的灰度决策

```text
更高级的思路：先定义服务的 SLO（如"99.9% 请求 < 200ms 且错误率 < 0.1%"）

灰度决策：
  - canary 是否消耗了太多 Error Budget（错误预算）
  - 当前阶段过去 N 分钟的 burn rate 是否超过阈值
  - 是否会侵蚀月度 SLO

落地工具：
  - Prometheus + sloth（生成 SLO PromQL）
  - Flagger（自动消费 SLO 决策，下节讲）
```

##### 4.3.7.7 人工 vs 自动判定

| 维度 | 人工 | 自动 |
| --- | --- | --- |
| 决策速度 | 分钟级 | 秒级 |
| 一致性 | 看心情 / 看人 | 永远按规则 |
| 复杂度 | 简单场景够用 | 复杂场景必需 |
| 实施成本 | 写文档 | 写代码 / 接 Operator |
| 适用 | 1–3 个服务 | 几十上百个服务 |

#### 4.3.8 Flagger 拓展认知（自动化灰度的工业级方案）

> 上面四阶段是**人肉操作 canary-weight 注解 + 眼睛看监控**——能用，但**难复制、难一致**。
> Flagger 把这套流程做成 Operator，自动跑灰度、自动回退。

##### 4.3.8.1 它是什么

```text
Flagger（Weaveworks 开源，现在是 FluxCD 一部分）
  - K8s Operator
  - 围绕 CRD Canary 自动化渐进式交付
  - 自带：金丝雀发布、A/B 测试、蓝绿发布
  - 支持多种 Ingress / Service Mesh：
      NGINX、Traefik、Istio、Linkerd、Contour、App Mesh、Gloo、Skipper
  - 配合 Prometheus / Datadog / CloudWatch 自动判定
```

##### 4.3.8.2 为什么需要它

```text
人肉 canary 的痛点：

  ❌ 每个服务都要写一套 yaml、接监控
  ❌ 错误判定靠人盯，容易漏看
  ❌ 凌晨 3 点发布谁盯监控？
  ❌ 服务多了没法统一标准（新人接手的失败率极高）
  ❌ 跟监控 / 告警 / SLO 各系统割裂

Flagger 解决：

  ✅ 声明式：写一个 Canary CR，其他全自动
  ✅ 自动推权重：30s 一次，自动 10 → 20 → 30 → ... → 100
  ✅ 自动判定：拉 Prometheus 指标，对比 stable vs canary
  ✅ 自动回退：指标不达标立刻把权重归零
  ✅ 自动通知：Slack / Teams / MS Teams / Webhook
```

##### 4.3.8.3 工作原理

```text
         ┌──────────────┐
         │ Canary CR    │  ← 你写的：服务名、目标权重、阈值
         └──────┬───────┘
                │ watch
                ▼
      ┌──────────────────┐
      │  Flagger Controller │  ← Operator，每 30s 调一次
      └──────┬───────────┘
             │
   ┌─────────┴──────────┐
   │ ① 拉指标          │──→ Prometheus（metric provider）
   │ ② 跟 baseline 比   │    / Datadog / CloudWatch
   │ ③ 达标就推权重     │
   │ ④ 不达标就回退     │
   │ ⑤ 推完发通知       │──→ Slack / Webhook
   └─────────┬──────────┘
             │
             ▼
      调 Ingress / Service Mesh 的权重
      （改 nginx.ingress.kubernetes.io/canary-weight
        或 Istio VirtualService weight）
```

##### 4.3.8.4 Canary CR 示例

```yaml
apiVersion: flagger.app/v1beta1
kind: Canary
metadata:
  name: myapp
  namespace: prod
spec:
  provider: nginx                    # 用 nginx ingress
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: myapp
  service:
    port: 80
    # 自动生成 primary + canary Service，并指给同一个 Ingress
  analysis:
    interval: 30s                    # 每 30s 评估一次
    threshold: 10                    # 最多失败 10 次再回退
    maxWeight: 50                    # 最高权重（不能直接到 100）
    stepWeight: 10                   # 每次 +10
    metrics:
      - name: request-success-rate
        thresholdRange:
          min: 99                    # canary 成功率 ≥ 99%
        interval: 1m
      - name: request-duration
        thresholdRange:
          max: 500                   # P99 ≤ 500ms
        interval: 1m
    webhooks:
      - name: load-test               # 推权重前先发流量压一下
        type: rollout
        url: http://flagger-loadtester.test/
      - name: notify-slack
        type: post-rollout
        url: https://hooks.slack.com/services/...
```

##### 4.3.8.5 三种发布策略（Flagger 都支持）

```text
1. Canary（金丝雀）
   权重 0 → 100，渐进式，可自动回退

2. A/B Testing（按 Header / Cookie 切流）
   nginx.ingress.kubernetes.io/canary-by-header
   按用户分桶（比如 1% 用户走新版本看转化率）

3. Blue/Green（蓝绿）
   新版本起来 100% 跑着，但不接流量
   切流量是一步切换，验证 OK 后下掉老版本
   适合：DB schema 变更、大版本升级
```

##### 4.3.8.6 Flagger vs 手撸 ingress-nginx canary

| 维度 | 手撸（前面四阶段） | Flagger |
| --- | --- | --- |
| 权重推进 | 人手 `kubectl annotate` | 自动 stepWeight 推进 |
| 指标判定 | 人盯监控 / 告警 | Prometheus 自动拉取对比 |
| 自动回退 | 没有，要写脚本 | 内置 |
| 通知 | 另接（CI/CD 里写） | 内置 webhook |
| A/B 测试 | 要写两份 Ingress | 改 metric selector 即可 |
| 蓝绿 | 要自己管两套资源 | 切 `analysis.iterations` |
| 学习曲线 | 5 分钟 | 半天 |
| 适用 | 1–5 个服务 / 低频发布 | 几十服务 / 高频发布 / 多人协作 |

##### 4.3.8.7 与 Argo Rollouts 的对比

```text
同场景同能力的另一个选择：Argo Rollouts（Intuit 出品）

Argo Rollouts：
  - 也是 Operator + CRD Rollout
  - 更深度集成 Argo CD（GitOps）
  - 支持更复杂的策略（traffic routing、experiment、analysis）
  - UI 更好看（kubectl plugin 有 dashboard）

选哪个：
  - 已有 Argo CD → Rollouts 几乎无成本集成
  - 已有 Prometheus + 多 Ingress 控制器 → Flagger 更灵活
  - 团队小 / 服务少 → Flagger 上手快
  - 团队大 / 已经在 Argo 体系 → Rollouts 更顺
```

##### 4.3.8.8 一句话总结 Flagger

> **Flagger = "把前面四阶段 + 监控判定 + 自动回退 + 通知"做成一个 Operator**，
> 写一个 Canary CR 就完事。

---

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
# 按权重（canary 拿 N%，old 自动 = 100 - N%）
nginx.ingress.kubernetes.io/canary: "true"
nginx.ingress.kubernetes.io/canary-weight: "10"          # 10% 切到 canary

# 按 Header
nginx.ingress.kubernetes.io/canary-by-header: "X-Canary"
nginx.ingress.kubernetes.io/canary-by-header-value: "true"

# 按 Cookie
nginx.ingress.kubernetes.io/canary-by-cookie: "version"
```

```text
真实灰度四阶段：
  ① 真实灰度（v1 vs v2，小步：10 → 30 → 70 → 100）
  ② 趁 canary 满流更新 old（v1 → v2，零风险）+ scale up old
  ③ 流量回迁（v2 vs v2 同版本，一步到位 100 → 0）
  ④ 先删 Ingress → 再删 Service → 最后删 Deployment

⚠️ canary-weight 是单值语义，只改一边
⚠️ 副本数不会随流量自动扩，必须手动 set image + scale
⚠️ 资源峰值 = 常态 + 灰度 + old 滚动（5 → 9），提前算节点容量
⚠️ 顺序反了 = 502（删 Ingress 前流量还在）
```

---

## 参考

- **Ingress**: https://kubernetes.io/docs/concepts/services-networking/ingress/
- **Ingress Controllers**: https://kubernetes.io/docs/concepts/services-networking/ingress-controllers/
- **Gateway API**: https://gateway-api.sigs.k8s.io/
- **Nginx Ingress**: https://kubernetes.github.io/ingress-nginx/
- **Traefik**: https://doc.traefik.io/traefik/
- **cert-manager**: https://cert-manager.io/docs/
