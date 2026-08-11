# 四层转发 vs 七层转发

`四层(L4)` 与 `七层(L7)` 转发是负载均衡 / 反向代理选型时最常遇到的抉择**:L4 看 IP + 端口 + 连接状态(TCP/UDP 层);L7 拆开应用层协议(HTTP/HTTPS/gRPC),按 URL / Host / Header / Cookie 智能路由。两者**不是互斥**,而是分层组合的常见架构。

注意:

- L4 / L7 指 **OSI 模型** 的传输层(L4)与应用层(L7)
- "转发"广义包括 **负载均衡**(LB)、**反向代理**(Reverse Proxy)、**API Gateway**
- 性能 L4 > L7,但 L7 提供内容级路由、缓存、安全等能力
- 真实部署大多是 **L4 在边缘 + L7 在内部** 的组合

## 作用

```text
L4 转发:  client ──TCP/UDP 连接──> L4 LB ──TCP/UDP──> upstream
L7 转发:  client ──HTTP 请求──> L7 Proxy ──HTTP──> upstream
```

主要解决:

- 流量分发(多机负载均衡)
- 对外暴露单一入口
- 跨协议路由(同一 IP 不同端口、不同域名)
- TLS 卸载 / 内容缓存 / 安全防护

## 概念对比

### 1. 一句话差异

```text
L4 = "看包头决定往哪转"(IP / Port / 协议号)
L7 = "拆开请求看内容决定往哪转"(URL / Host / Header / Body)
```

### 2. 决策依据

| 维度 | L4 | L7 |
| ---- | -- | -- |
| OSI 层 | 传输层(TCP/UDP) | 应用层(HTTP/HTTPS/gRPC) |
| 看到的 | 源/目的 IP、端口、协议号、TCP 状态 | L4 + URL、Host、Header、Cookie、Body |
| 决策粒度 | 连接级(一次连接固定 upstream) | 请求级(同一连接不同请求可不同 upstream) |
| 协议依赖 | 无(任何 TCP/UDP 协议) | 需协议解析(HTTP/2、gRPC 等) |
| TLS 终止 | 可选(常用于透传) | 必备(拆包后才有 L7 信息) |

### 3. 性能

| 指标 | L4 | L7 |
| ---- | -- | -- |
| 吞吐 | 极高(纯包转发) | 中(解析 + 路由) |
| 延迟 | 低(~微秒级) | 中(~毫秒级) |
| CPU 消耗 | 几乎只算 checksum | 解析 + 路由计算 + 可能的 TLS |
| 长连接友好 | 是(连接级固定) | 是(可复用 upstream 连接) |
| 短连接友好 | 是(纯透传) | 中(每次都要解析) |

L4 在大流量 / 高并发 / 长连接(数据库、游戏、语音)场景优势明显。

## 四层转发详解

### 1. 工作原理

```text
client                     L4 LB                     upstream
  │                          │                          │
  │─────── SYN ────────────>│                          │
  │                          │── SYN ────>              │
  │<──── SYN+ACK ───────────│<── SYN+ACK ──             │
  │─────── ACK ────────────>│── ACK ───>                │
  │                          │                          │
  │<════════ 数据透传 ══════════════════════════════>│
```

L4 LB 维护一张 **conntrack 表**(五元组 → upstream),数据透传,**不读 payload**。

### 2. 转发模式

```text
NAT / SNAT:    客户端 → LB → upstream,源 IP 改写为 LB IP
DR(Direct Return): 客户端 → LB → upstream,响应直接回客户端(MAC 欺骗)
Tunnel(IPIP):    客户端 → LB → upstream,IP 隧道封装
Full-NAT:     LB 同时改源 IP 和目的 IP
```

### 3. 调度算法

```text
轮询(RR)         # 简单轮转
加权轮询(WRR)    # 按权重分配
最少连接(LC)     # 当前连接数最少的 upstream
加权最少连接(WLC) # 加权 + 最少连接
源地址哈希(SH)   # 同一 client → 同一 upstream(会话保持)
目标地址哈希(DH)  # 同一 URL → 同一 upstream(缓存亲和)
```

### 4. 健康检查

```text
TCP 检查:  尝试三次握手,能连上即健康
HTTP 检查: 类似,但发送 GET /health
自定义脚本: keepalived 支持外部脚本
```

### 5. 典型工具

| 工具 | 模式 | 特点 |
| ---- | ---- | ---- |
| LVS(Linux Virtual Server) | L4 NAT/DR/Tunnel | 内核态,性能极高,经典生产方案 |
| HAProxy(TCP mode) | L4 | 用户态,配置灵活 |
| Nginx(stream 块) | L4 | 兼顾 L7,常用 |
| Envoy(L4 filter) | L4 | Service mesh 主流数据面 |
| IPVS(k8s kube-proxy) | L4 | k8s 默认 Service 实现 |
| F5 BIG-IP | L4/L7 | 商业硬件,功能全 |
| AWS NLB | L4 | 云原生 L4 LB,百万级 QPS |

### 6. 适用场景

- 数据库代理(MySQL、PostgreSQL、Redis)
- 游戏服务器(UDP 低延迟)
- 语音 / 视频 / 实时通信
- 内部东西向流量(微服务 mesh)
- 边缘入口,先 L4 分流再转 L7

## 七层转发详解

### 1. 工作原理

```text
client                  L7 Proxy                  upstream
  │                       │                          │
  │── GET /api/users ──> │                          │
  │                       │── 解析 URL/Host ──>     │
  │                       │── GET /api/users ──>     │
  │<── 200 OK ──────────│<── 200 OK ───             │
  │                       │                          │
```

L7 Proxy **完整解析 HTTP 报文**(或 TLS 终止后解析),根据应用层信息路由。

### 2. 路由维度

| 维度 | 例子 |
| ---- | ---- |
| Host | `api.example.com` → api 集群;`admin.example.com` → admin 集群 |
| URL Path | `/api/v1/*` → v1 集群;`/static/*` → CDN |
| Header | `X-Region: cn-east` → 区域路由 |
| Cookie | `session=xxx` → 粘性会话 |
| Method | `POST /login` → 鉴权服务 |
| Query | `?debug=1` → 灰度环境 |
| Body(高级) | JSON 中字段路由(罕见,贵) |

### 3. 调度算法

L7 算法基本沿用 L4,**额外增加**:

```text
URL 哈希     # 同一 URL → 同一 upstream(缓存亲和)
一致性哈希   # upstream 增减时只迁移少量 key
最小响应时间 # 优先转给响应最快的 upstream
最小请求数   # 按 pending 请求数负载均衡
```

### 4. 高级能力

```text
- TLS 卸载     # L7 终止 TLS,内网明文
- 内容缓存     # 静态资源 / API 响应缓存
- 限流限速     # 单 IP / 全局 QPS / 漏桶 / 令牌桶
- 鉴权         # JWT / OAuth / Basic
- 改写         # URL 重写、Header 注入、Body 替换
- WAF / 防 SQL注入 / 防爬虫
- gRPC / HTTP/2 / WebSocket 支持
```

### 5. 典型工具

| 工具 | 特点 |
| ---- | ---- |
| Nginx(http 块) | 经典,生态成熟 |
| HAProxy(http mode) | 高性能,配置清晰 |
| Envoy | 云原生数据面,Service mesh 标配 |
| Traefik | 自动发现 + Let’s Encrypt |
| Apache APISIX | 国产,高性能 + 插件丰富 |
| Kong | 插件生态丰富 |
| AWS ALB / GCP HTTPS LB | 云 L7 LB |
| OpenResty | Nginx + Lua,扩展性强 |

### 6. 适用场景

- Web 网站 / API 网关
- 微服务入口(根据 URL/Header 路由到不同服务)
- 灰度发布 / A/B 测试 / 蓝绿
- 跨域 / 鉴权 / 限流统一收口
- CDN 边缘节点

## 核心对比

| 维度 | L4 | L7 |
| ---- | -- | -- |
| OSI 层 | 传输层 | 应用层 |
| 看到的内容 | IP / Port / 协议号 / 连接状态 | L4 + URL / Host / Header / Cookie / Body |
| 性能 | 极高(纯包转发) | 中(需解析) |
| 延迟 | 低(μs 级) | 中(ms 级) |
| 协议支持 | 任意 TCP/UDP | HTTP / gRPC / WebSocket 等 |
| TLS 终止 | 可选 | 必备 |
| 路由粒度 | 连接级 | 请求级 |
| 内容缓存 | 否 | 是 |
| 鉴权 / 限流 / 改写 | 否 | 是 |
| 配置复杂度 | 低 | 中-高 |
| 调试难度 | 低(纯包) | 中(需看 HTTP) |
| 故障域影响 | 小(透传) | 大(单点故障影响所有 vhost) |

## 常见架构

### 1. 纯 L4(高性能场景)

```text
client → DNS → L4 LB → upstream pool
```

适合:数据库、游戏、UDP 服务。

### 2. 纯 L7(Web / API)

```text
client → L7 LB(Nginx/Envoy) → upstream pool
```

适合:Web、API 网关。

### 3. L4 + L7 分层(最常见生产架构)

```text
client
  │
  ▼
┌─────────────────────────────┐
│  L4 LB(边缘入口)             │   ← 高吞吐、SSL 终结、TLS 卸载
│  - HAProxy / NLB / F5       │
└──────────────┬───────────────┘
               ▼
┌─────────────────────────────┐
│  L7 LB(内部)                 │   ← 智能路由、限流、缓存
│  - Nginx / Envoy / APISIX   │
└──────────────┬───────────────┘
               ▼
        upstream 服务池
```

优势:L4 顶住大流量,L7 在内网做精细路由。

### 4. Service Mesh 内部(东西向 L4)

```text
pod-A ──sidecar(envoy L4)──> pod-B
```

Envoy 在 mesh 内部以 L4 为主,辅以 L7 路由。

### 5. CDN 边缘(L7 缓存 + 回源)

```text
client → CDN edge(L7 缓存) → origin(L4/L7)
```

CDN 边缘必须 L7 才能解析 URL / Host 做缓存与回源。

## 选型要点

### 1. 何时选 L4

- 协议不是 HTTP(TCP/UDP 自定义协议)
- 极致性能 / 低延迟(数据库、游戏、实时)
- 仅需 IP+Port 维度的负载均衡
- 不需要内容路由、缓存、鉴权

### 2. 何时选 L7

- Web / HTTP / gRPC / WebSocket
- 需要按 URL / Host / Header 路由
- 需要鉴权 / 限流 / 改写 / 缓存
- 需要 TLS 终止统一管理

### 3. 何时组合

```text
边缘入口 → L4(顶住 DDoS / 大流量)
内部网关 → L7(智能路由 / 限流)
数据库 / 内部 RPC → L4(性能优先)
Web API → L7(灵活路由)
```

### 4. 不要踩的坑

- **不要在 L4 上做 HTTP 路由**:做不到;客户端连 L4 后,L4 把同一连接透传出去
- **不要用 L7 转纯 TCP 流量**:性能浪费,且很多 L7 代理不支持非 HTTP
- **不要把 TLS 终止放在 L4 同时又想做 Header 路由**:L4 终止 TLS 拿到的是密文,无法读 Header;**要么 L4 透传 + L7 终止,要么 L7 终止 + 直接路由**
- **L7 单点故障影响大**:L4 透传后端,L7 挂了所有 vhost 都挂;考虑多副本 + 健康检查
- **L4 透传时无法修改 Header**:要做限流 / 鉴权,只能走 L7

## 实战案例

### 1. Nginx:同一端口按 Host / Path 路由(L7)

```nginx
http {
    upstream api_backend  { server 10.0.0.1:8080; server 10.0.0.2:8080; }
    upstream admin_backend { server 10.0.0.3:8080; }

    server {
        listen 80;
        server_name api.example.com;
        location / {
            proxy_pass http://api_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
    }

    server {
        listen 80;
        server_name admin.example.com;
        location / {
            proxy_pass http://admin_backend;
        }
    }

    # 同 host 不同 path
    server {
        listen 80;
        server_name example.com;
        location /api/ {
            proxy_pass http://api_backend;
        }
        location /static/ {
            proxy_pass http://static_backend;
            expires 30d;
        }
    }
}
```

### 2. HAProxy:L4 TCP 转发 + L7 HTTP 路由共存

```conf
# /etc/haproxy/haproxy.cfg

frontend ft_tcp_mysql
    bind *:3306
    mode tcp              # L4
    default_backend bk_mysql

backend bk_mysql
    mode tcp
    balance leastconn
    option mysql-check
    server db1 10.0.0.11:3306 check
    server db2 10.0.0.12:3306 check

frontend ft_http
    bind *:80
    mode http             # L7
    acl is_api path_beg /api/
    acl is_admin hdr(host) -i admin.example.com
    use_backend bk_api    if is_api
    use_backend bk_admin  if is_admin
    default_backend bk_web

backend bk_api
    balance roundrobin
    server api1 10.0.0.21:8080 check
    server api2 10.0.0.22:8080 check

backend bk_admin
    server admin1 10.0.0.31:8080 check

backend bk_web
    balance roundrobin
    server web1 10.0.0.41:80 check
```

### 3. LVS + Nginx:经典 L4 + L7 分层

```text
client → LVS(L4 DR) → Nginx(L7) → upstream
```

```bash
# LVS(Linux Virtual Server,DR 模式)
ipvsadm -A -t 192.168.1.100:80 -s rr
ipvsadm -a -t 192.168.1.100:80 -r 10.0.0.1:80 -g
ipvsadm -a -t 192.168.1.100:80 -r 10.0.0.2:80 -g
```

```nginx
# Nginx 上游(L7)
upstream backend {
    server 10.0.1.1:8080;
    server 10.0.1.2:8080;
}
server {
    listen 80;
    location / {
        proxy_pass http://backend;
    }
}
```

### 4. Nginx stream(L4 转发 TCP)

```nginx
stream {
    upstream mysql {
        server 10.0.0.11:3306;
        server 10.0.0.12:3306;
    }
    server {
        listen 3306;
        proxy_pass mysql;
        proxy_connect_timeout 5s;
        proxy_timeout 600s;
    }
}
```

### 5. k8s Service(IPVS / iptables,默认 L4)

```yaml
apiVersion: v1
kind: Service
metadata:
  name: my-svc
spec:
  type: ClusterIP
  selector:
    app: my-app
  ports:
    - port: 80
      targetPort: 8080
```

L4 转发由 kube-proxy(IPVS / iptables)实现,**Ingress 才上 L7**。

### 6. 性能压测对比(L4 vs L7)

```bash
# wrk 打 L7(Nginx)
wrk -t4 -c100 -d30s http://lb/

# iperf 打 L4(TCP 透传)
iperf3 -c lb -p 3306

# 同等硬件下 L4 吞吐常是 L7 的 3-10 倍
```

## 一句话总结

```text
L4 = 看包头转(快、简单、协议无关)
L7 = 拆请求转(慢、灵活、内容级)
生产 = L4 顶在边缘 + L7 收口在内部
```

决策树:

```text
协议非 HTTP?           ──> L4
只要按 IP/Port 负载?    ──> L4
需要按 URL/Host 路由?    ──> L7
需要鉴权/限流/缓存?      ──> L7
极致性能 / 低延迟?       ──> L4
Web / API 网关?         ──> L7
边缘顶大流量?           ──> L4,内层补 L7
```

## 参考

- `man ipvsadm`(LVS)
- `man haproxy`
- `nginx` 文档 `http` / `stream` 块
- [HAProxy 配置手册](http://www.haproxy.org/download/1.8/doc/configuration.txt)
- [Envoy 官方文档](https://www.envoyproxy.io/docs)
- [LVS 项目主页](http://www.linuxvirtualserver.org/)
- [AWS ALB vs NLB 文档](https://docs.aws.amazon.com/elasticloadbalancing/)