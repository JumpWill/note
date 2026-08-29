# K8s CoreDNS 原理与配置

> 本章系统讲解 K8s CoreDNS 的工作原理、配置、定制方法以及集群 DNS 调优。

## 一、为什么需要 CoreDNS

### 1.1 业务背景

```text
K8s 集群中的 DNS 挑战：

  1. 服务发现
     - Pod 创建后 K8s 自动分配 IP
     - Pod 之间需要通过名称访问而非 IP
     - Service 是虚拟 IP，需要 DNS 解析

  2. 集群内部域名
     - Service 需要 A 记录
     - Pod 需要 A 记录
     - Headless Service 需要多条 A 记录

  3. 外部 DNS 解析
     - 集群内 Pod 访问外部服务
     - 自定义上游 DNS
     - 转发到公司内网 DNS

  4. 策略与控制
     - 基于域名过滤
     - DNS 级别访问控制
     - split-horizon DNS

  5. 性能与可用性
     - 高并发查询
     - 缓存降低延迟
     - 多个 Pod 副本
```

### 1.2 CoreDNS 优势

```text
CoreDNS 是 K8s 默认的 DNS 服务器：

  1. 插件化架构
     - 每个功能都是插件
     - 可按需启用/禁用
     - 灵活组合

  2. 高性能
     - Go 编写，原生异步
     - 毫秒级响应
     - 支持 DNS-over-HTTPS、DNSCrypt

  3. 云原生
     - CNCF 项目（毕业级）
     - K8s 默认选择
     - 完整 K8s 集成

  4. 可扩展
     - 自定义插件
     - 多种协议（UDP/TCP/TLS/QUIC/HTTP）
```

### 1.3 替代品对比

| DNS | 特点 | 现状 |
|-----|------|------|
| **CoreDNS** | 插件化、高性能、推荐 | K8s 1.11+ 默认 |
| kube-dns | 老版本，K8s 默认 | K8s 1.13 前 |
| dnsmasq | 轻量、CNI 常用 | 非 K8s 服务发现 |
| BIND | 经典 DNS | 复杂场景 |
| NSD | 权威 DNS | 外部权威 |

---

## 二、CoreDNS 工作原理

### 2.1 K8s 服务发现机制

```text
K8s 服务发现流程：

  Pod 创建时：
    1. K8s 为 Pod 分配 IP（如 10.244.1.5）
    2. 创建 DNS A 记录：<pod-ip>.<namespace>.pod.cluster.local
    3. Service 创建时：
       - ClusterIP（如 10.96.0.10）
       - DNS A 记录：<svc-name>.<namespace>.svc.cluster.local

  Pod 解析 DNS：
    Pod A → DNS query: my-svc.default.svc.cluster.local
    → CoreDNS 响应: 10.96.0.10
    → Pod A 通过 ClusterIP 10.96.0.10 访问 Service
    → kube-proxy 转发到后端 Pod
```

### 2.2 完整 DNS 名称

```text
K8s 完整 DNS 命名规则：

  Service（普通 Service）：
    <svc>.<ns>.svc.cluster.local
    例：my-svc.default.svc.cluster.local

  Pod：
    <pod-ip-with-dashes>.<ns>.pod.cluster.local
    例：10-244-1-5.default.pod.cluster.local

  Headless Service（StatefulSet）：
    <pod-name>.<svc>.<ns>.svc.cluster.local
    例：web-0.nginx.default.svc.cluster.local

  Service 端口：
    <svc>.<ns>.svc.cluster.local:<port>
    例：my-svc.default.svc.cluster.local:80

  默认域名：
    cluster.local
    （可修改为自定义）
```

### 2.3 CoreDNS 架构

```text
CoreDNS 架构：

  ┌──────────────────────────────────────┐
  │        CoreDNS Pod（kube-system）    │
  │                                      │
  │  ┌──────────────────────────────┐  │
  │  │  CoreDNS Server                │  │
  │  │  ┌────────────────────────┐  │  │
  │  │  │  Plugin Chain            │  │  │
  │  │  │                        │  │  │
  │  │  │  cache → bind → ...   │  │  │
  │  │  └────────────────────────┘  │  │
  │  └──────────────────────────────┘  │
  │                                      │
  │  Pod 内（2 个容器）：               │
  │  ┌────────────────────────────┐    │
  │  │  CoreDNS（主容器）            │    │
  │  │  端口：53（UDP/TCP）          │    │
  │  └────────────────────────────┘    │
  │  ┌────────────────────────────┐    │
  │  │  dnsmasq（Sidecar）            │    │
  │  │  - nodelocaldns 缓存        │    │
  │  │  - 减少 CoreDNS 压力        │    │
  │  └────────────────────────────┘    │
  │                                      │
  └──────────────────────────────────────┘
```

### 2.4 插件链

```text
CoreDNS 插件链（按顺序处理 DNS 查询）：

  查询：my-svc.default.svc.cluster.local A
  
  1. metrics（记录查询指标）
  2. cache（缓存结果）
  3. loadbalancer（随机选择后端 IP）
  4. kubernetes（K8s 服务发现核心）
     - 解析 Service、Pod、Endpoint
  5. bind（DNS 查询执行）
  6. cache（命中直接返回）
  7. loop（继续链）
  8. forward（转发到上游 DNS）
     - /etc/resolv.conf 的 nameserver
     - 默认 8.8.8.8
  9. cache（最终缓存）
  10. errors（错误处理）
  11. log（日志）
  12. ready（就绪状态）
```

### 2.5 完整请求流程

```text
Pod 发起 DNS 查询完整流程：

  Pod A (10.244.1.5) 解析 my-svc.default.svc.cluster.local

  1. Pod A 内 glibc resolver
     - 检查 /etc/resolv.conf
     - nameserver 10.96.0.10（kube-dns ClusterIP）
     - ndots:5（少于 5 个点的域名先尝试 search 列表）

  2. Pod A 发起 DNS 查询
     - 通过 NodeLocal DNSCache（K8s 1.18+）
     - 或直接发送到 CoreDNS Service 10.96.0.10:53
     - 协议：UDP（默认）/ TCP

  3. CoreDNS Pod（kube-system）接收
     - 插件链按顺序处理
     - cache 插件检查本地缓存
     - 命中 → 直接返回
     - 未命中 → 继续处理

  4. kubernetes 插件处理
     - 查询 K8s API Server
     - 获取 Service、Endpoints、Pod 信息
     - 生成 A 记录（ServiceIP）
     - 或生成 SRV 记录

  5. 响应返回
     - 包含 A 记录（如 10.96.0.10）
     - 包含 TTL
     - Pod A 接收响应

  6. Pod A 连接
     - 拿到 ServiceIP 10.96.0.10
     - 通过 kube-proxy 转发到后端 Pod
     - 完成服务发现
```

---

## 三、CoreDNS 部署与架构

### 3.1 部署结构

```text
K8s 中 CoreDNS 部署：

  ┌──────────────────────────────────────┐
  │  Deployment：coredns（kube-system）   │
  │  - 副本数：通常 2（高可用）        │
  │  - 镜像：registry.k8s.io/coredns  │
  │  - 镜像版本：v1.10.x 或更新       │
  └──────────────────────────────────────┘
         ↕ 通过 Service（kube-dns）暴露
  ┌──────────────────────────────────────┐
  │  Service：kube-dns（kube-system）   │
  │  - ClusterIP：10.96.0.10            │
  │  - 端口：53（UDP/TCP）              │
  │  - IP：ClusterIP + DNS port          │
  └──────────────────────────────────────┘
         ↕
  ┌──────────────────────────────────────┐
  │  ConfigMap：coredns                  │
  │  - Corefile（CoreDNS 配置）        │
  └──────────────────────────────────────┘
         ↕
  ┌──────────────────────────────────────┐
  │  ServiceAccount：coredns            │
  └──────────────────────────────────────┘
         ↕ 拥有
  ┌──────────────────────────────────────┐
  │  ClusterRole：system:coredns        │
  │  - endpoints, services, pods...    │
  └──────────────────────────────────────┘
```

### 3.2 默认 ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: coredns
  namespace: kube-system
data:
  Corefile: |
    .:53 {
        errors
        health {
            lameduck 5s
        }
        ready
        kubernetes cluster.local in-addr.arpa ip6.arpa {
            pods insecure
            fallthrough in-addr.arpa ip6.arpa
            ttl 30
        }
        prometheus :9153
        forward . /etc/resolv.conf
        cache 30
        loop
        reload
        loadbalance
    }
```

### 3.3 关键文件

```bash
# 部署清单
/manifests/coredns/                      # 原始清单
/etc/coredns/Corefile                    # CoreDNS 主配置
/var/log/coredns/coredns.log            # 日志
/etc/coredns/ConfigMap.yaml             # 完整 ConfigMap
```

---

## 四、CoreDNS 配置详解

### 4.1 Corefile 语法

```text
Corefile 格式：

  <zone>:<port> {
      <plugin> [parameters]
      <plugin> [parameters]
  }

示例：
  .:53 {                          # 所有域监听 53 端口
      errors                       # 错误日志
      health                        # 健康检查
      ready                         # 就绪探针
      kubernetes cluster.local ...  # K8s 集成
      forward . 8.8.8.8          # 上游 DNS
      cache 30                      # 缓存 30 秒
  }
```

### 4.2 核心插件详解

#### errors 插件

```text
errors：记录 DNS 查询错误
参数：
  - log：是否打印到 stdout
  - debug：是否打印调试信息

示例：
  errors
  errors {
      log
      debug
  }
```

#### health 插件

```text
health：健康检查端点
HTTP 端点：/health
参数：
  - lameduck：延迟不健康时间（秒）

示例：
  health {
      lameduck 5s    # 5 秒后报不健康（K8s 用）
  }

验证：
  curl http://<coredns-ip>:8080/health
```

#### ready 插件

```text
ready：就绪探针
HTTP 端点：/ready
参数：无

示例：
  ready

验证：
  curl http://<coredns-ip>:8181/ready
```

#### kubernetes 插件（核心）

```text
kubernetes：K8s 服务发现核心插件
参数：
  - cluster.local：集群域
  - in-addr.arpa：IPv4 反向解析
  - ip6.arpa：IPv6 反向解析
  - pods disabled/enabled/insecure/verified
    - disabled：禁用 Pod 记录
    - enabled：启用 Pod 记录（需要验证）
    - insecure：跳过验证（性能高）
    - verified：验证 Pod（安全高）
  - namespaces：限定命名空间
  - endpoint_pod_names：是否用 endpoint 名
  - ttl：TTL 秒数
  - kubeconfig：kubeconfig 路径

完整配置：
  kubernetes cluster.local in-addr.arpa ip6.arpa {
      pods insecure
      fallthrough in-addr.arpa ip6.arpa
      ttl 30
      kubeconfig /etc/coredns/kubeconfig
  }
```

#### forward 插件

```text
forward：转发到上游 DNS
参数：
  - 上游地址列表
  - .：使用 /etc/resolv.conf
  - prefer：prefer tcp / prefer udp
  - max_fails：最大失败次数
  - expire：过期时间
  - timeout：超时

示例：
  forward . /etc/resolv.conf        # 使用宿主 DNS
  forward . 8.8.8.8 1.1.1.1         # 指定上游
  forward . 8.8.8.8 {
      max_fails 3
      expire 10s
      timeout 5s
  }
```

#### cache 插件

```text
cache：缓存 DNS 查询结果
参数：
  - success：成功响应缓存时间（默认 4h）
  - denial：拒绝响应缓存时间（默认 30m）
  - prefetch：预取数量
  - serve_stale：过期是否仍返回

示例：
  cache 30                    # 缓存 30 秒
  cache {
      success 1000
      denial 100
      prefetch 10
      serve_stale 1h
  }
```

#### log 插件

```text
log：DNS 查询日志
参数：
  - class：日志类别（all/error/denial）
  - format：日志格式

示例：
  log
  log {
      class all
      format "{>json}"
  }
```

#### prometheus 插件

```text
prometheus：暴露 Prometheus 指标
参数：
  - 监听端口（默认 :9153）
  - 监控路径（默认 /metrics）

示例：
  prometheus :9153

指标：
  - coredns_dns_requests_total
  - coredns_dns_response_rcode_count_total
  - coredns_cache_hits_total
  - coredns_cache_misses_total
  - coredns_dns_request_duration_seconds
```

#### loop 插件

```text
loop：循环重新查询（用于检查 cache 命中）
参数：
  - 最多循环次数

示例：
  loop
  loop 5
```

#### reload 插件

```text
reload：自动重载 Corefile
参数：
  - interval：检查间隔
  - zone：限制重载的 zone

示例：
  reload
  reload 30s    # 每 30 秒检查
```

#### loadbalance 插件

```text
loadbalance：随机选择后端 IP
参数：
  - 默认开启

作用：
  - Service 有多个 Endpoint 时随机返回
  - 避免热点（避免每次都返回第一个）

示例：
  loadbalance
```

---

## 五、K8s 服务发现详细配置

### 5.1 启用 Service 解析

```yaml
apiVersion: v1
kind: Service
metadata:
  name: my-service
  namespace: production
spec:
  selector:
    app: my-app
  ports:
  - port: 80
    targetPort: 8080
---
apiVersion: v1
kind: Pod
metadata:
  name: my-app
  namespace: production
  labels:
    app: my-app
spec:
  containers:
  - name: app
    image: my-app:1.0
```

```bash
# 解析
kubectl exec -it my-app -- nslookup my-service
# 输出：
# Server:    10.96.0.10
# Address 1: 10.96.0.10 kube-dns.kube-system.svc.cluster.local
# Name:      my-service
# Address 1: 10.96.0.10   ← Service ClusterIP
```

### 5.2 启用 Pod 解析

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: my-app
  namespace: production
spec:
  containers:
  - name: app
    image: my-app:1.0
```

```bash
# Pod 解析（按 IP 反查）
kubectl exec -it my-app -- nslookup 10-244-1-5.production.pod.cluster.local
# 输出：返回 Pod 的 IP（10.244.1.5）
```

### 5.3 启用 Headless Service 解析

```yaml
apiVersion: v1
kind: Service
metadata:
  name: my-headless
  namespace: production
spec:
  clusterIP: None                 # Headless Service
  selector:
    app: my-app
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: my-app
  namespace: production
spec:
  serviceName: my-headless
  replicas: 3
  selector:
    matchLabels:
      app: my-app
  template:
    metadata:
      labels:
        app: my-app
    spec:
      containers:
      - name: app
        image: my-app:1.0
```

```bash
# Headless Service 解析每个 Pod
kubectl exec -it my-app-0 -- nslookup my-headless
# 输出：
# my-app-0.my-headless.production.svc.cluster.local → 10.244.1.5
# my-app-1.my-headless.production.svc.cluster.local → 10.244.1.6
# my-app-2.my-headless.production.svc.cluster.local → 10.244.1.7
```

---

## 六、CoreDNS 自定义配置

### 6.1 添加自定义域名解析

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: coredns
  namespace: kube-system
data:
  Corefile: |
    .:53 {
        errors
        health
        ready
        kubernetes cluster.local in-addr.arpa ip6.arpa {
            pods insecure
            fallthrough in-addr.arpa ip6.arpa
            ttl 30
        }
        
        # 自定义内网域名
        example.internal:53 {
            errors
            cache 30
            forward . 10.0.0.53
        }
        
        # 自定义应用域名
        myapp.io:53 {
            errors
            cache 300
            forward . 8.8.8.8
        }
        
        prometheus :9153
        forward . /etc/resolv.conf
        cache 30
        loop
        reload
        loadbalance
    }
```

### 6.2 添加自定义 hosts

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: coredns
  namespace: kube-system
data:
  Corefile: |
    .:53 {
        errors
        health
        ready
        kubernetes cluster.local in-addr.arpa ip6.arpa {
            pods insecure
            fallthrough in-addr.arpa ip6.arpa
            ttl 30
        }
        
        # 自定义 hosts
        template {
            match "db.internal|^db\\..*\\.internal$"
            answer "db.internal. 10.0.0.100"
            upstream
        }
        
        template {
            match "cache.internal|^cache\\..*"
            answer "cache.internal. 10.0.0.200"
            upstream
        }
        
        prometheus :9153
        forward . /etc/resolv.conf
        cache 30
        loop
        reload
        loadbalance
    }
```

### 6.3 配置上游 DNS 转发

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: coredns
  namespace: kube-system
data:
  Corefile: |
    .:53 {
        errors
        health
        ready
        kubernetes cluster.local in-addr.arpa ip6.arpa {
            pods insecure
            fallthrough in-addr.arpa ip6.arpa
            ttl 30
        }
        
        # 转发到内网 DNS
        forward . 10.0.0.53 {
            max_fails 3
            expire 10s
            timeout 5s
            prefer udp
        }
        
        # 转发到外部 DNS
        forward . 8.8.8.8 1.1.1.1
        
        # 阻止泄漏到外部
        block example.com
        block unwanted-domain.com
        
        prometheus :9153
        cache 30
        loop
        reload
        loadbalance
    }
```

### 6.4 配置 Debug 日志

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: coredns
  namespace: kube-system
data:
  Corefile: |
    .:53 {
        errors debug          # 错误 + 调试日志
        log {
            class all          # 记录所有查询
        }
        health
        ready
        kubernetes cluster.local in-addr.arpa ip6.arpa {
            pods insecure
            fallthrough in-addr.arpa ip6.arpa
            ttl 30
        }
        prometheus :9153
        forward . /etc/resolv.conf
        cache 30
        loop
        reload
        loadbalance
    }
```

查看日志：

```bash
kubectl logs -n kube-system -l k8s-app=kube-dns -c coredns -f
```

---

## 七、修改 CoreDNS ConfigMap

### 7.1 修改流程

```bash
# 1. 编辑 ConfigMap
kubectl edit cm coredns -n kube-system

# 2. 修改 Corefile 内容
# 3. 保存退出
# 4. CoreDNS 会自动重载（reload 插件）

# 或者：
# 完整替换
kubectl apply -f coredns-configmap.yaml

# 5. 验证重载
kubectl logs -n kube-system -l k8s-app=kube-dns -c coredns
# 应看到 reload 相关日志
```

### 7.2 完整替换示例

```bash
# 1. 导出当前配置
kubectl get cm coredns -n kube-system -o yaml > coredns-cm.yaml

# 2. 编辑 coredns-cm.yaml
vim coredns-cm.yaml

# 3. 应用
kubectl apply -f coredns-cm.yaml

# 4. 验证
kubectl rollout restart deployment/coredns -n kube-system
kubectl logs -n kube-system -l k8s-app=kube-dns -c coredns
```

### 7.3 强制重载（如果 reload 失败）

```bash
# 重启 CoreDNS
kubectl rollout restart deployment/coredns -n kube-system

# 查看状态
kubectl get pods -n kube-system -l k8s-app=kube-dns
```

---

## 八、CoreDNS 性能调优

### 8.1 调整副本数和资源

```yaml
# 调整 CoreDNS Deployment 资源
apiVersion: apps/v1
kind: Deployment
metadata:
  name: coredns
  namespace: kube-system
spec:
  replicas: 4                  # 默认 2，高负载集群建议 3-5
  template:
    spec:
      containers:
      - name: coredns
        image: registry.k8s.io/coredns/coredns:v1.11.1
        resources:
          requests:
            cpu: 200m            # 默认 100m
            memory: 256Mi       # 默认 128Mi
          limits:
            cpu: 1000m          # 防止突发占用过多 CPU
            memory: 1Gi         # 防止 OOM
        args:
        - -conf
        - /etc/coredns/Corefile
```

### 8.2 调整 nodelocaldns

```yaml
# 部署 nodelocaldns（推荐 K8s 1.18+）
# 大幅减少 CoreDNS 压力，提升性能
apiVersion: v1
kind: Service
metadata:
  name: kube-dns-upstream
  namespace: kube-system
  labels:
    k8s-app: kube-dns
spec:
  ports:
  - name: dns
    port: 53
    targetPort: 53
  selector:
    k8s-app: kube-dns
```

### 8.3 调整缓存时间

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: coredns
  namespace: kube-system
data:
  Corefile: |
    .:53 {
        errors
        health
        ready
        kubernetes cluster.local in-addr.arpa ip6.arpa {
            pods insecure
            fallthrough in-addr.arpa ip6.arpa
            ttl 60                          # 增加 TTL
        }
        
        prometheus :9153
        forward . /etc/resolv.conf
        cache 300                           # 增加缓存（5 分钟）
        loop
        reload
        loadbalance
    }
```

### 8.4 启用 NodeLocal DNSCache

```bash
# K8s 1.18+ 推荐启用
# 每个 Node 运行本地 DNS 缓存
# 避免所有查询都打到 CoreDNS

# 部署
kubectl apply -f https://k8s.io/examples/admin/dns/dns-horizontal-autoscaler/dns-horizontal-autoscaler.yaml

# 验证
kubectl -n kube-system get pods -l k8s-app=node-local-dns
```

### 8.5 性能指标

```bash
# 1. CoreDNS 指标
kubectl -n kube-system port-forward svc/kube-dns 9153:9153 &
curl http://localhost:9153/metrics | grep coredns_

# 关键指标
# - coredns_dns_requests_total：总请求数
# - coredns_dns_response_rcode_count_total：响应码统计
# - coredns_cache_hits_total：缓存命中
# - coredns_cache_misses_total：缓存未命中
# - coredns_dns_request_duration_seconds：请求延迟

# 2. 查询延迟
dig @<coredns-ip> my-svc.default.svc.cluster.local | grep "Query time"

# 3. 缓存命中率
curl http://localhost:9153/metrics | grep cache_hits | head
```

---

## 九、高级场景

### 9.1 自定义上游 DNS

```yaml
# 场景：集群内 Pod 需要访问公司内网域名
apiVersion: v1
kind: ConfigMap
metadata:
  name: coredns
  namespace: kube-system
data:
  Corefile: |
    .:53 {
        errors
        health
        ready
        kubernetes cluster.local in-addr.arpa ip6.arpa {
            pods insecure
            fallthrough in-addr.arpa ip6.arpa
            ttl 30
        }
        
        # 特定域名转发到内网 DNS
        forward mycompany.local 10.0.0.53
        forward internal.io 10.0.0.53
        
        # 其他查询转发到外部 DNS
        forward . 8.8.8.8
        
        prometheus :9153
        cache 30
        loop
        reload
        loadbalance
    }
```

### 9.2 Split-Horizon DNS

```yaml
# 场景：不同 namespace 用不同 DNS
apiVersion: v1
kind: ConfigMap
metadata:
  name: coredns
  namespace: kube-system
data:
  Corefile: |
    .:53 {
        errors
        health
        ready
        
        # 生产环境
        kubernetes cluster.local in-addr.arpa ip6.arpa {
            pods insecure
            fallthrough in-addr.arpa ip6.arpa
        }
        
        # 默认上游
        forward . /etc/resolv.conf
        
        # 自定义 host
        template {
            match "*.test.local"
            answer "{{ .Name }} 10.0.0.100"
            upstream
        }
        
        prometheus :9153
        cache 30
        loop
        reload
        loadbalance
    }
```

### 9.3 服务网格集成

```yaml
# 与 Istio 集成（Sidecar DNS 拦截）
apiVersion: v1
kind: ConfigMap
metadata:
  name: coredns
  namespace: kube-system
data:
  Corefile: |
    .:53 {
        errors
        health
        ready
        
        kubernetes cluster.local in-addr.arpa ip6.arpa {
            pods insecure
            fallthrough in-addr.arpa ip6.arpa
            ttl 30
        }
        
        # 允许 Istio sidecar 访问
        prometheus :9153
        forward . /etc/resolv.conf
        cache 30
        loop
        reload
        loadbalance
    }
```

### 9.4 禁用 NodeLocal DNS

```bash
# 某些场景需要禁用 NodeLocal DNS（如 Service Mesh）
# 1. 删除 nodelocaldns DaemonSet
kubectl delete ds node-local-dns -n kube-system

# 2. 修改 kubelet 配置
# /var/lib/kubelet/config.yaml
apiVersion: kubelet.config.k8s.io/v1beta1
kind: KubeletConfiguration
clusterDomain: cluster.local

# 3. 重启 kubelet
sudo systemctl restart kubelet
```

### 9.5 Pod 的 4 种 DNS 策略（dnsPolicy）

```text
K8s 为 Pod 配置 DNS 解析时提供 4 种 dnsPolicy：

  ┌────────────────────────────────────────────────────────────┐
  │                    Pod spec                                │
  │                                                           │
  │  dnsPolicy: <选项>          ← 关键字段                     │
  │                                                           │
  │  Pod 内 /etc/resolv.conf 由 kubelet 根据此字段生成        │
  └────────────────────────────────────────────────────────────┘
```

#### 4 种 dnsPolicy 详解

```yaml
# 1. Default（默认）
apiVersion: v1
kind: Pod
metadata:
  name: dns-default
spec:
  dnsPolicy: Default    # 不显式写也行（默认）
  containers:
  - name: app
    image: nginx
---
# 生成的 /etc/resolv.conf：
# nameserver <node-dns>
# search <node-dns-search>
# 行为：Pod 使用节点（hostNetwork）的 DNS 配置
#      不会经过 CoreDNS
# 用途：节点能访问的域名，Pod 也能访问
# 适用：hostNetwork 模式，或与节点共享 DNS
```

```yaml
# 2. ClusterFirst（K8s 默认推荐）
apiVersion: v1
kind: Pod
metadata:
  name: dns-clusterfirst
spec:
  dnsPolicy: ClusterFirst
  containers:
  - name: app
    image: nginx
---
# 生成的 /etc/resolv.conf：
# nameserver <coredns-cluster-ip>      # CoreDNS Service IP
# search <namespace>.svc.cluster.local
#          svc.cluster.local
#          cluster.local
# ndots: 5
# 行为：优先查询集群内域名
#      查不到的走节点上游（fallthrough）
# 用途：标准 K8s 应用
# 适用：绝大多数场景（默认推荐）
```

```yaml
# 3. ClusterFirstWithHostNet（hostNetwork 特殊）
apiVersion: v1
kind: Pod
metadata:
  name: dns-hostnet
spec:
  hostNetwork: true              # 必须同时使用 hostNetwork
  dnsPolicy: ClusterFirstWithHostNet
  containers:
  - name: app
    image: nginx
---
# 生成的 /etc/resolv.conf：
# nameserver <coredns-cluster-ip>     # 仍然使用 CoreDNS
# search <namespace>.svc.cluster.local
#          svc.cluster.local
#          cluster.local
# 行为：使用 hostNetwork，但仍然走 CoreDNS
# 用途：hostNetwork 模式下仍想用 K8s 服务发现
# 适用：CNI 插件、监控 Agent 等系统组件
```

```yaml
# 4. None（完全自定义）
apiVersion: v1
kind: Pod
metadata:
  name: dns-none
spec:
  dnsPolicy: None
  containers:
  - name: app
    image: nginx
---
# 生成的 /etc/resolv.conf：
# nameserver <pod-dns>      # 来自 Pod 的 dnsConfig
# 行为：完全忽略 K8s 的 DNS 配置
#      使用 Pod 自定义 dnsConfig 配置
# 用途：自定义上游 DNS（绕过 CoreDNS）
# 适用：特殊场景（不推荐）
```

#### 4 种策略对比

```text
┌──────────────────────────┬────────────────────────────────┐
│  dnsPolicy               │  行为                        │
├──────────────────────────┼────────────────────────────────┤
│  Default                │  继承宿主 DNS 配置            │
│                          │  不经过 CoreDNS                │
│                          │  hostNetwork Pod 适用        │
├──────────────────────────┼────────────────────────────────┤
│  ClusterFirst（默认）   │  优先查 CoreDNS                │
│                          │  查不到走宿主的 upstream       │
│                          │  绝大多数场景推荐            │
├──────────────────────────┼────────────────────────────────┤
│  ClusterFirstWithHostNet │  hostNetwork + 走 CoreDNS     │
│                          │  系统组件（CNI/监控）适用    │
├──────────────────────────┼────────────────────────────────┤
│  None                  │  完全自定义 DNS               │
│                          │  需配置 dnsConfig             │
│                          │  不推荐                       │
└──────────────────────────┴────────────────────────────────┘
```

#### 实战：自定义上游 DNS（dnsConfig）

```yaml
# 使用 dnsPolicy: None + dnsConfig 自定义上游
apiVersion: v1
kind: Pod
metadata:
  name: custom-dns
spec:
  dnsPolicy: None
  dnsConfig:
    nameservers:
    - 1.1.1.1
    - 8.8.8.8
    searches:
    - example.com
    - internal.local
    options:
    - name: ndots
      value: "3"
    - name: timeout
      value: "5"
    - name: attempts
      value: "3"
  containers:
  - name: app
    image: nginx
```

生成的 /etc/resolv.conf：
```text
nameserver 1.1.1.1
nameserver 8.8.8.8
search example.com internal.local
options ndots:3 timeout:5 attempts:3
```

#### 决策树

```text
问：Pod 需要什么 DNS 行为？
  ├─ 标准 K8s 应用 → ClusterFirst（默认）
  ├─ hostNetwork Pod（如 CNI 插件）→ ClusterFirstWithHostNet
  ├─ 节点 DNS 可用且与 K8s 共享 → Default
  └─ 完全自定义 → None + dnsConfig

选择 Default 的场景：
  - 节点使用公司统一 DNS
  - Pod 也想用同一个 DNS
  - 不想经过 CoreDNS（性能优先）
  - 通常是 hostNetwork Pod

选择 ClusterFirst 的场景：
  - 标准 K8s 应用（绝大多数）
  - 使用 Service 名称访问
  - 推荐（也是 K8s 默认）

选择 ClusterFirstWithHostNet：
  - hostNetwork Pod 但要用 K8s 服务发现
  - 系统组件（监控、Agent、Operator）

选择 None：
  - ⚠️ 几乎不用
  - 除非有非常特殊的 DNS 需求
```

#### 调试 DNS 策略

```bash
# 查看 Pod 的 dnsPolicy
kubectl get pod <pod> -o jsonpath='{.spec.dnsPolicy}'
# 输出：ClusterFirst

# 查看 Pod 的 /etc/resolv.conf
kubectl exec -it <pod> -- cat /etc/resolv.conf
# 输出：
# nameserver 10.96.0.10          ← CoreDNS Service IP
# search default.svc.cluster.local svc.cluster.local cluster.local
# ndots: 5

# 验证 DNS 解析路径
kubectl exec -it <pod> -- nslookup my-svc
# Server:  10.96.0.10          ← ClusterFirst 走 CoreDNS
# Address: 10.96.0.10 kube-dns.kube-system.svc.cluster.local
# Name:    my-svc
# Address: 10.96.0.10

# 强制自定义 upstream（要重启 Pod）
kubectl delete pod <pod>
kubectl apply -f pod-with-custom-dns.yaml
```

#### CoreDNS 配置与 dnsPolicy 协同

```text
注意：
  - dnsPolicy 控制 Pod 的 DNS 客户端配置
  - Corefile 控制 CoreDNS 服务端的查询行为
  - 两者必须配合才能正确解析

示例：
  Pod A：dnsPolicy: ClusterFirst（用 CoreDNS）
  Pod B：dnsPolicy: Default（用节点 DNS）
  Pod C：dnsPolicy: None + dnsConfig（自定义）

  CoreDNS 需要：
  - 配置 Service Account 才能 watch K8s API
  - 配置 Service Account 绑定 system:coredns ClusterRole
  - 监控指标（prometheus :9153）
```

#### 与 Corefile 配置的关联

```text
CoreDNS Corefile 关键配置：

  kubernetes cluster.local in-addr.arpa ip6.arpa {
      pods insecure        # Pod 名称解析（推荐 insecure）
      ttl 30               # DNS 记录 TTL
      fallthrough in-addr.arpa ip6.arpa
  }

  forward . /etc/resolv.conf  # 查不到时转发到节点 DNS

  关键点：
    1. pods insecure 允许 Pod 短名解析（如 pod-name）
    2. ttl 30 缓存时间（避免每次都查 K8s API）
    3. forward . 使用节点 DNS（fallthrough 行为）
```

#### K8s DNS 完整解析示例

```text
Pod A 在 production namespace，IP 是 10.244.1.5

查询 1：production.svc.cluster.local
  → CoreDNS 查询 K8s API
  → 返回 production namespace 下的所有 Service IP

查询 2：my-svc.production.svc.cluster.local
  → CoreDNS 查询 K8s API
  → 返回 my-svc Service 的 ClusterIP

查询 3：10-244-1-5.production.pod.cluster.local
  → CoreDNS 查询 K8s API
  → 返回 Pod IP 10.244.1.5

查询 4：my-app.default.svc.cluster.local
  → CoreDNS（fallthrough 到节点 DNS）
  → 查不到 → 转发到节点上游 DNS
  → 节点 DNS 查询
```



---

## 十、调试与排错

### 10.1 常见问题诊断

```bash
# 1. Pod DNS 解析失败
kubectl exec -it <pod> -- nslookup kubernetes
# 看是否返回 ClusterIP

# 2. CoreDNS Pod 状态
kubectl get pods -n kube-system -l k8s-app=kube-dns

# 3. CoreDNS 日志
kubectl logs -n kube-system -l k8s-app=kube-dns -c coredns --tail=100

# 4. CoreDNS 端点测试
kubectl exec -it <pod> -- nslookup my-svc.default.svc.cluster.local 10.96.0.10
# 指定 nameserver 测试

# 5. CoreDNS 端点健康
kubectl get endpoints kube-dns -n kube-system
kubectl get svc kube-dns -n kube-system

# 6. 性能监控
kubectl -n kube-system port-forward svc/kube-dns 9153:9153
curl http://localhost:9153/metrics | grep coredns_

# 7. 完整 trace
kubectl exec -it <pod> -- cat /etc/resolv.conf
# 输出的 nameserver 应该是 10.96.0.10
```

### 10.2 常见问题与解决

```text
Q1: Pod 解析 Service 失败
A1:
  - 检查 CoreDNS Pod 状态：kubectl -n kube-system get pods
  - 检查 Service 是否有 Endpoints
  - 检查 Pod 的 /etc/resolv.conf nameserver
  - 手动测试：nslookup my-svc.default.svc.cluster.local 10.96.0.10

Q2: CoreDNS OOMKilled
A2:
  - 调整 resources.limits
  - 增加 replicas
  - 启用 nodelocaldns 减少查询
  - 减小 cache 时间

Q3: CoreDNS 解析慢
A3:
  - 启用 nodelocaldns
  - 减小 cache 时间
  - 检查 forward 上游 DNS
  - 监控 metrics

Q4: 自定义域名不生效
A4:
  - 检查 Corefile 语法
  - 验证 reload 生效
  - 检查 Pod 的 search 列表
  - 确认 ndots 配置

Q5: 跨 namespace 解析失败
A5:
  - 使用完整 FQDN：my-svc.production.svc.cluster.local
  - 或在 Pod 中设置 ndots:2
  - 配置 search 列表
```

### 10.3 性能调优脚本

```bash
# 1. 分析慢查询
curl -s http://localhost:9153/metrics | grep coredns_dns_request_duration_seconds_count

# 2. 查看错误率
curl -s http://localhost:9153/metrics | grep -E "rcode_count_total" | head

# 3. 查看缓存效果
echo "缓存命中率："
curl -s http://localhost:9153/metrics | grep "cache_hits_total" | head
echo "缓存未命中："
curl -s http://localhost:9153/metrics | grep "cache_misses_total" | head

# 4. 调整副本数（基于负载）
HPA:
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: coredns-hpa
  namespace: kube-system
spec:
  scaleTargetRef:
    name: coredns
    kind: Deployment
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 60
```

---

## 十一、安全与多租户

### 11.1 限制 Pod 可解析的域名

```yaml
# 通过 NetworkPolicy 限制 Pod 访问 CoreDNS
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: restrict-dns
  namespace: production
spec:
  podSelector: {}
  policyTypes:
  - Egress
  egress:
  # 只允许访问 kube-dns Service（10.96.0.10）和外部 DNS（8.8.8.8）
  - to:
    - namespaceSelector:
        matchLabels:
          name: kube-system
      podSelector:
        matchLabels:
          k8s-app: kube-dns
    ports:
    - protocol: UDP
      port: 53
    - protocol: TCP
      port: 53
  - to:
    - ipBlock:
        cidr: 8.8.8.8/32
    ports:
    - protocol: UDP
      port: 53
    - protocol: TCP
      port: 53
```

### 11.2 RBAC 控制

```yaml
# ConfigMap 读取权限控制
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: kube-system
  name: coredns-reader
rules:
- apiGroups: [""]
  resources: ["configmaps"]
  resourceNames: ["coredns"]
  verbs: ["get", "watch", "list"]
```

---

## 十二、核心要点速记

### CoreDNS 三大特性

```
1. 插件化（plugins chain）
2. K8s 服务发现（内置）
3. 高性能（Go 异步）
```

### 完整 DNS 名称速记

```
Service：
  <svc>.<ns>.svc.cluster.local
Pod：
  <ip-dashed>.<ns>.pod.cluster.local
Headless：
  <pod>.<svc>.<ns>.svc.cluster.local
```

### 常用命令

```bash
# 查看 CoreDNS 状态
kubectl get pods -n kube-system -l k8s-app=kube-dns
kubectl get cm coredns -n kube-system -o yaml

# 查看日志
kubectl logs -n kube-system -l k8s-app=kube-dns -c coredns

# 启用 debug
kubectl edit cm coredns -n kube-system
# 在 errors 块加 debug

# 强制重启
kubectl rollout restart deployment/coredns -n kube-system

# 测试解析
kubectl exec -it <pod> -- nslookup my-svc
```

### 性能调优

```
- 副本数：3-5（高可用）
- nodelocaldns：必备（K8s 1.18+）
- cache：30-300 秒
- replicas：HPA 自动扩缩
- resources：limits 设置
```

### 速记卡

- **CoreDNS** = K8s 默认 DNS（自 1.11）
- **Corefile** = CoreDNS 配置（Plugins chain）
- **kube-dns Service** = ClusterIP 10.96.0.10
- **ndots:5** = 默认（少于 5 点的域名先 search）
- **NodeLocal DNSCache** = 性能优化必备
- **k8s-app: kube-dns** label = 识别 CoreDNS
- **修改配置** = kubectl edit cm coredns -n kube-system
- **reload 插件** = 自动重载（修改后无需手动）
- **插件链顺序** = metrics → cache → kubernetes → forward
- **必备插件** = errors / health / ready / kubernetes / forward / cache
- **K8s 集成** = 监听 Service/Pod/Endpoint 变化
- **debug** = errors 块加 debug 启用