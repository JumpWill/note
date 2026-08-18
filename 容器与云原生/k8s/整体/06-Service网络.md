# Service 与网络 (Service & Networking)

> 本章系统讲解 K8s 的 Service 机制、DNS、负载均衡与网络模型。

## 一、Service 概述

### 1.1 为什么需要 Service

```text
问题: Pod 是动态的 (IP 变化、扩缩、漂移)

传统 Pod 访问:
   Client → Pod IP → 容器
   问题: Pod 重启后 IP 变了!

Service 解决方案:
   - 稳定的虚拟 IP (ClusterIP)
   - 自动负载均衡到后端 Pod
   - Pod 变化对客户端透明
   - 服务发现 (DNS)
```

### 1.2 Service 工作原理

```text
┌──────────────┐
│   Client     │
└──────┬───────┘
       │ DNS 查询: my-service.default.svc.cluster.local
       ↓
┌──────────────┐
│ CoreDNS      │ → 返回 ClusterIP: 10.96.10.50
└──────┬───────┘
       ↓
┌──────────────┐
│   Service    │  (my-service, IP: 10.96.10.50)
│  ClusterIP   │
└──────┬───────┘
       │ kube-proxy / iptables / IPVS
       ↓ DNAT
┌──────┴──────┬───────────┬──────────┐
│ Pod-1 (v1)  │ Pod-2 (v2)│ Pod-3(v1)│
│ 10.244.1.1  │ 10.244.2.5│ 10.244.3.8│
└─────────────┴───────────┴──────────┘
```

### 1.3 Service 类型

```text
4 种类型 (type):
1. ClusterIP     - 默认,仅集群内访问
2. NodePort      - 暴露节点端口,可外部访问
3. LoadBalancer  - 云厂商 LB,生产推荐
4. ExternalName  - CNAME 代理,用于跨集群访问
```

---

## 二、ClusterIP (默认)

### 2.1 完整定义

```yaml
apiVersion: v1
kind: Service
metadata:
  name: my-service
  namespace: default
  labels:
    app: my-app
spec:
  type: ClusterIP                # 默认,可省略

  # 选择器 (关键)
  selector:
    app: my-app
    tier: backend

  # 端口定义
  ports:
  - name: http
    protocol: TCP               # TCP / UDP
    port: 80                    # Service 端口 (集群内访问用)
    targetPort: 8080            # Pod 端口
  - name: https
    port: 443
    targetPort: 8443

  # 发布到哪些 IP
  # clusterIP: 10.96.10.50      # 静态分配 (默认自动)
  # clusterIPs:                  # 双栈 (IPv4 + IPv6)
  #   - 10.96.10.50
  #   - fd00::1

  # 会话保持 (基于客户端 IP)
  sessionAffinity: ClientIP
  sessionAffinityConfig:
    clientIP:
      timeoutSeconds: 10800     # 3 小时

  # 健康检查 (可选)
  healthCheckNodePort: 30010
```

### 2.2 Endpoints 与 EndpointSlices

```text
Service 通过 Endpoints/EndpointSlices 自动维护后端 Pod 列表:

Service my-service (10.96.10.50)
   ↓ 自动维护
Endpoints my-service:
  - 10.244.1.1:8080  (Pod-1)
  - 10.244.2.5:8080  (Pod-2)
  - 10.244.3.8:8080  (Pod-3)

K8s 1.21+ 默认使用 EndpointSlices (替代 Endpoints)
```

### 2.3 工作流程

```text
1. 创建 Service,指定 selector
2. Controller watch Pod
3. Pod label 匹配 selector → 加入 Endpoints
4. kube-proxy watch Endpoints
5. 创建 iptables/IPVS 规则
6. Service ClusterIP 收到请求
7. iptables DNAT 到具体 Pod
```

---

## 三、NodePort

### 3.1 概念

**NodePort** 在每个节点上开放一个固定端口,外部可通过 `<NodeIP>:<NodePort>` 访问。

```yaml
apiVersion: v1
kind: Service
metadata:
  name: my-service-nodeport
spec:
  type: NodePort

  selector:
    app: my-app

  ports:
  - name: http
    port: 80                  # ClusterIP port (集群内)
    targetPort: 8080          # Pod port
    nodePort: 30080            # 节点 port (30000-32767, 默认范围)
    protocol: TCP

  # externalTrafficPolicy
  # Cluster: 默认,任一节点都接受,可能跨节点转发
  # Local: 只本地有 Pod 的节点接受,保留客户端 IP
  externalTrafficPolicy: Cluster
```

### 3.2 端口范围

```text
默认范围: 30000-32767

修改:
  --service-node-port-range=30000-39999 (启动 kube-apiserver 时)
```

### 3.3 访问方式

```bash
# 假设:
# - 节点 IP: 192.168.1.10
# - Service NodePort: 30080
# - 任意节点都可访问

# 访问服务
curl http://192.168.1.10:30080
curl http://192.168.1.11:30080
curl http://192.168.1.12:30080

# 任何节点都可以访问,即使 Pod 不在该节点
# (kube-proxy 会跨节点转发)
```

---

## 四、LoadBalancer

### 4.1 概念

**LoadBalancer** 调用云厂商的 LB 服务创建外部 LB,生产环境推荐。

```yaml
apiVersion: v1
kind: Service
metadata:
  name: my-service-lb
spec:
  type: LoadBalancer

  selector:
    app: my-app

  ports:
  - name: http
    port: 80
    targetPort: 8080
  - name: https
    port: 443
    targetPort: 8443

  # 云厂商特定配置
  annotations:
    # AWS ELB
    service.beta.kubernetes.io/aws-load-balancer-name: "my-app-lb"
    service.beta.kubernetes.io/aws-load-balancer-type: "nlb"
    service.beta.kubernetes.io/aws-load-balancer-ssl-cert: "arn:aws:acm:..."

    # 阿里云 SLB
    service.beta.kubernetes.io/alicloud-loadbalancer-id: "lb-xxxxx"
    service.beta.kubernetes.io/alicloud-loadbalancer-force-override-listen-port: "true"

  # 健康检查
  healthCheckNodePort: 30010

  # 分配 IP
  # loadBalancerIP: 1.2.3.4   # 静态 IP (云厂商支持)

  # externalTrafficPolicy: Local  # 推荐 (避免跨节点转发)

  # 会话保持
  sessionAffinity: ClientIP
  sessionAffinityConfig:
    clientIP:
      timeoutSeconds: 10800
```

### 4.2 各云厂商对比

| 云厂商 | Service 类型 | 备注 |
|--------|------------|------|
| AWS | NLB / ALB | 通过 AWS LB Controller |
| GCP | TCP/UDP LB | 自动创建 |
| Azure | Load Balancer | 自动创建 |
| 阿里云 | SLB | 通过 CCM |
| 腾讯云 | CLB | 通过 CCM |
| 自建 | MetalLB | 推荐使用 |

---

## 五、Headless Service

### 5.1 概念

**Headless Service** (`clusterIP: None`) 不分配 ClusterIP,直接返回 Pod IP 列表。

```yaml
apiVersion: v1
kind: Service
metadata:
  name: mysql-headless
spec:
  clusterIP: None            # headless
  selector:
    app: mysql
  ports:
  - port: 3306
    targetPort: 3306
```

### 5.2 使用场景

```text
1. StatefulSet 必须配合 Headless Service
   - 提供稳定的 Pod DNS 解析 (mysql-0.mysql-headless)

2. 自定义服务发现
   - 客户端直接连 Pod,不经过 LB

3. 数据库集群
   - 主从复制 (mysql-0 写, mysql-1/2 读)
```

### 5.3 DNS 解析对比

```text
普通 Service:
  my-service.default.svc.cluster.local → 10.96.10.50 (ClusterIP)

Headless Service:
  my-service.default.svc.cluster.local → 10.244.1.1 (Pod-1)
                                       → 10.244.2.5 (Pod-2)
                                       → 10.244.3.8 (Pod-3)

StatefulSet (自动生成):
  mysql-0.mysql-headless.default.svc.cluster.local → 10.244.1.1
  mysql-1.mysql-headless.default.svc.cluster.local → 10.244.2.5
  mysql-2.mysql-headless.default.svc.cluster.local → 10.244.3.8
```

---

## 六、ExternalName

### 6.1 概念

**ExternalName** 通过 CNAME 引用集群外部服务。

```yaml
apiVersion: v1
kind: Service
metadata:
  name: my-database
  namespace: default
spec:
  type: ExternalName
  externalName: db.example.com
```

### 6.2 用途

```text
1. 集群内服务访问外部数据库
   - Service DNS: my-database.default.svc → db.example.com
   - 应用无需修改,只改 Service 即可

2. 跨集群服务访问
   - 集群 A 的 Service 指向集群 B 的服务
```

---

## 七、kube-proxy 三种模式

### 7.1 iptables 模式 (默认)

```text
工作原理:
1. kube-proxy watch API Server
2. 创建/更新 iptables 规则
3. 数据包到达 Service ClusterIP 时
4. iptables DNAT 到具体 Pod

优点: 简单,通用
缺点: 规则数量大时性能下降 (数千条)
```

### 7.2 IPVS 模式 (推荐生产)

```text
工作原理:
1. 创建 IPVS 虚拟服务 (ClusterIP)
2. 后端 Pod 加入 real server
3. 数据包通过 IPVS 调度算法转发

优点: 
- 高性能 (哈希表)
- 多种负载均衡算法 (rr, lc, dh, sh, sed, nq)

启用:
  kubectl -n kube-system edit cm kube-proxy
  # mode: "ipvs"
```

### 7.3 nftables 模式 (1.28+ stable)

```text
新模式,取代 iptables:
- 性能更好 (Linux 5.x 内核优化)
- IPv6 支持更好
- 规则合并减少

启用:
  kubectl -n kube-system edit cm kube-proxy
  # mode: "nftables"
```

### 7.4 三种模式对比

| 特性 | iptables | IPVS | nftables |
|------|----------|------|----------|
| 性能 | 中 | 高 | 高 |
| 复杂度 | 低 | 中 | 中 |
| IPv6 | 一般 | 好 | 优秀 |
| 集群规模 | 小 (< 1000 Service) | 大 (5000+ Service) | 大 |
| 推荐度 | 兼容性好 | 生产推荐 | 新集群推荐 |

---

## 八、DNS 服务发现

### 8.1 CoreDNS

```text
K8s 默认 DNS: CoreDNS (替代 kube-dns)

DNS 服务器地址 (Pod 内 /etc/resolv.conf):
  nameserver 10.96.0.10
  search default.svc.cluster.local svc.cluster.local cluster.local
```

### 8.2 DNS 解析规则

```text
完整域名格式:
  <service-name>.<namespace>.svc.cluster.local

例:
  - my-service               # 默认命名空间
  - my-service.default       # 同命名空间省略
  - my-service.default.svc
  - my-service.default.svc.cluster.local  # 完整

Pod DNS:
  - pod-ip-addr.pod-namespace.pod.cluster.local
  - 10-244-1-1.default.pod.cluster.local
```

### 8.3 StatefulSet Pod DNS

```text
mysql-0.mysql-headless.default.svc.cluster.local
↓
解析为 mysql-0 Pod 的 IP

可以用于主从识别:
  mysql-0 = master (主)
  mysql-1, mysql-2 = slave (从)
```

---

## 九、CNI 网络插件

### 9.1 CNI 概念

**CNI (Container Network Interface)** 是 K8s 网络的标准接口,主流实现:

| CNI | 特点 |
|-----|------|
| **Calico** | BGP 网络,支持 NetworkPolicy,生产推荐 |
| **Flannel** | 简单 Overlay,适合小集群 |
| **Cilium** | eBPF 技术,高性能,可观测 |
| **Weave Net** | 多主机通信,易用 |
| **Antrea** | 基于 OVS,适合 VMware |

### 9.2 Calico 安装

```bash
kubectl apply -f https://docs.projectcalico.org/manifests/calico.yaml

# 验证
kubectl get pods -n kube-system | grep calico
```

### 9.3 Calico NetworkPolicy 示例

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-frontend-to-backend
spec:
  podSelector:
    matchLabels:
      app: backend
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: frontend
    ports:
    - protocol: TCP
      port: 8080
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: database
    ports:
    - protocol: TCP
      port: 3306
```

---

## 十、Ingress (入口)

### 10.1 Ingress 概念

**Ingress** 是 K8s 的 HTTP/HTTPS 路由,基于域名和路径将外部请求转发到不同 Service。

```text
Ingress = 7 层反向代理
  + 基于 Host (域名) 路由
  + 基于 Path (路径) 路由
  + TLS 终止
  + 限流、认证、重写

注意: Ingress 只是路由规则,实际代理由 Ingress Controller 实现
```

### 10.2 主流 Ingress Controller

| Controller | 特点 |
|-----------|------|
| **Nginx Ingress** | 最常用,功能全 |
| **Traefik** | 自动服务发现,配置简单 |
| **HAProxy Ingress** | 高性能 |
| **Istio Gateway** | 服务网格集成 |
| **Contour** | Envoy-based |

### 10.3 Ingress 资源定义

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-app-ingress
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - app.example.com
    - api.example.com
    secretName: app-tls-secret

  rules:
  # 域名路由
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

  - host: api.example.com
    http:
      paths:
      - path: /v1
        pathType: Prefix
        backend:
          service:
            name: api-service
            port:
              number: 8080
      - path: /v2
        pathType: Prefix
        backend:
          service:
            name: api-v2-service
            port:
              number: 8080

  # 默认后端
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

### 10.4 Nginx Ingress Controller 安装

```bash
# Helm 安装 (推荐)
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update

helm install nginx-ingress ingress-nginx/ingress-nginx \
  --namespace ingress-nginx --create-namespace \
  --set controller.service.type=LoadBalancer
```

---

## 十一、NetworkPolicy (网络策略)

### 11.1 概念

**NetworkPolicy** 控制 Pod 之间的网络流量 (类似防火墙规则)。

```text
默认: K8s 所有 Pod 之间可互相访问 (扁平网络)
启用 NetworkPolicy: 实现微隔离

注意: 需要 CNI 支持 (Calico、Cilium)
```

### 11.2 完整示例

```yaml
# 默认拒绝所有
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: production
spec:
  podSelector: {}             # 匹配所有 Pod
  policyTypes:
  - Ingress
  - Egress
---
# 允许 frontend 访问 backend
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-frontend-to-backend
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: backend
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: frontend
    - namespaceSelector:
        matchLabels:
          name: production
    ports:
    - protocol: TCP
      port: 8080
---
# 允许 backend 访问 database
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-backend-to-db
spec:
  podSelector:
    matchLabels:
      app: backend
  policyTypes:
  - Egress
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: database
    ports:
    - protocol: TCP
      port: 3306
  # DNS 解析
  - to:
    - namespaceSelector: {}
    ports:
    - protocol: UDP
      port: 53
```

---

## 十二、Service Mesh 入口 (Istio 简述)

```text
Istio = Service Mesh 主流实现
  - Envoy Sidecar (每个 Pod 一个代理)
  - 控制面 (istiod)
  - 数据面 (Envoy)

提供:
  - 流量管理 (蓝绿/金丝雀/A/B 测试)
  - 安全 (mTLS)
  - 可观测性 (调用链、Metrics)
  - 策略 (限流、ACL)

适合:
  - 大规模微服务
  - 多语言应用
  - 需要高级流量管理
```

---

## 核心要点速记

### Service 类型速记

```text
ClusterIP    - 集群内,默认
NodePort     - 节点端口 (30000-32767),可外部访问
LoadBalancer - 云 LB,生产推荐
ExternalName - CNAME,跨集群/外部服务
Headless     - clusterIP: None,直返 Pod IP (StatefulSet 用)
```

### 选型决策

```text
集群内微服务调用 → ClusterIP
简单外部访问 (测试) → NodePort
生产外部访问 (云) → LoadBalancer
有状态应用 (DB/MQ) → Headless + StatefulSet
跨集群/外部服务 → ExternalName
```

### DNS 解析格式

```text
普通 Service:
  my-svc.default.svc.cluster.local → ClusterIP (10.96.x.x)

Headless Service:
  my-svc.default.svc.cluster.local → Pod IPs (列表)

StatefulSet Pod:
  pod-name-0.svc-name.ns.svc.cluster.local → Pod IP
```

### kube-proxy 模式选择

```text
小集群 (< 1000 Service) → iptables (默认)
大集群 → IPVS (性能好)
新集群 (1.28+) → nftables (推荐)
```

### Ingress 选型

```text
通用场景 → Nginx Ingress
自动配置 → Traefik
服务网格 → Istio Gateway
企业级 → HAProxy
```

### NetworkPolicy 关键

```text
- 默认所有 Pod 互通
- NetworkPolicy 启用后按规则过滤
- 需要 CNI 支持 (Calico)
- 三个维度: podSelector, namespaceSelector, ipBlock
- 谨慎使用,可能误阻服务
```

---

## 参考

- **Service**: https://kubernetes.io/docs/concepts/services-networking/service/
- **Ingress**: https://kubernetes.io/docs/concepts/services-networking/ingress/
- **NetworkPolicy**: https://kubernetes.io/docs/concepts/services-networking/network-policies/
- **DNS**: https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/
- **CNI 规范**: https://github.com/containernetworking/cni
