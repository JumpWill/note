# Apache APISIX

云原生 API Gateway，基于 OpenResty/Nginx + etcd。配置变更毫秒级生效，路由匹配用 Radix Tree 极致高效，是云原生时代的网关首选之一。

## 一、定位与特点

- 云原生、etcd 驱动的 API Gateway
- 路由匹配用 Radix Tree（比链式快）
- 插件多语言：Lua / Go / Java / Node / Python
- 全协议：HTTP / HTTPS / gRPC / WebSocket / TCP / UDP / MQTT
- 内置 Dashboard
- 与 Apache SkyWalking / Prometheus / OpenTelemetry 集成
- 商业版 API7（API7 Cloud）

## 二、架构

```text
┌────────────────────────────────────┐
│  Client                            │
└─────────────┬──────────────────────┘
              │ HTTP / gRPC / TCP / UDP
              ▼
┌────────────────────────────────────┐
│  APISIX (Nginx + Lua)              │
│   - Radix Tree Router              │
│   - Plugins (Lua/Go/Java/Node)     │
│   - Load Balancer (etcd)           │
└─────┬──────────────────┬───────────┘
      │                  │
      ▼                  ▼
  Upstream           etcd Cluster
  Services           (配置中心)
```

核心组件：

- **Nginx**：处理连接
- **Lua**：业务逻辑
- **etcd**：配置存储 + watch
- **Plugin Runner**：Go / Java / Node / Python 插件独立进程
- **Dashboard**：Vue.js Web UI

## 三、核心概念

| 概念 | 含义 |
| --- | --- |
| **Route** | 路由规则（匹配 Path / Host / Header / Method） |
| **Upstream** | 后端目标集合 |
| **Service** | 上游服务抽象（可绑定 Route 与 Upstream） |
| **Consumer** | API 调用方 |
| **Plugin** | 钩入请求/响应的功能 |
| **Global Rule** | 全局插件配置 |
| **Plugin Config** | 跨路由复用插件 |

关系：`Route → Service → Upstream`，`Plugin` 挂在 Route/Service/Consumer/Global。

## 四、部署

### 1. Docker（最快上手）

```bash
# 起 etcd
docker run -d --name etcd \
  -p 2379:2379 \
  -e ALLOW_NONE_AUTHENTICATION=yes \
  -e ETCD_ADVERTISE_CLIENT_URLS=http://etcd:2379 \
  bitnami/etcd

# 起 APISIX
docker run -d --name apisix \
  --network container:etcd \
  -p 9080:9080 -p 9091:9091 -p 9443:9443 -p 9092:9092 \
  -e ETCD_SERVER=http://etcd:2379 \
  apache/apisix:latest
```

### 2. Docker Compose

参考 [apisix-docker](https://github.com/apache/apisix-docker) 的 `all-in-one.yml`。

### 3. K8s (Helm)

```bash
helm repo add apisix https://charts.apiseven.com
helm repo update
helm install apisix apisix/apisix \
  --set ingress-controller.enabled=true \
  --set etcd.persistentVolume.enabled=false
```

### 4. Dashboard

```bash
docker run -d --name apisix-dashboard \
  -p 9000:9000 \
  -e APISIX_DASHBOARD_LISTEN_ADDRESS=0.0.0.0:9000 \
  apache/apisix-dashboard
```

默认账号 `admin / admin`。

## 五、路由

### 1. Route 基础

```bash
curl -X POST http://127.0.0.1:9080/apisix/admin/routes/1 \
  -H 'X-API-KEY: edd1c9f034335f136f87ad84b625c8f1' \
  -d '{
    "uri": "/api/*",
    "upstream": {
      "type": "roundrobin",
      "nodes": {
        "10.0.0.1:80": 1,
        "10.0.0.2:80": 1
      }
    }
  }'
```

### 2. 高级匹配

```json
{
  "uri": "~/^/api/v\\d+/(.*)$",
  "hosts": ["api.example.com"],
  "methods": ["GET", "POST"],
  "priority": 100,
  "vars": [
    ["http_user_agent", "==", "Mozilla/5.0"]
  ],
  "upstream": {...}
}
```

### 3. 路由匹配字段

| 字段 | 匹配 |
| --- | --- |
| `uri` | URL Path（前缀 / 精确 / 正则） |
| `uris` | 多 URI |
| `host` / `hosts` | Host 头 |
| `method` / `methods` | HTTP Method |
| `headers` | Header 键值 |
| `vars` | 复杂表达式 |
| `priority` | 优先级（数字越大越先） |
| `filter_func` | Lua 函数 |

### 4. Upstream 配置

```json
{
  "type": "chash",                 // roundrobin / chash / leastconn / ewma
  "hash_on": "vars",
  "key": "remote_addr",
  "nodes": [
    { "host": "10.0.0.1", "port": 80, "weight": 1 },
    { "host": "10.0.0.2", "port": 80, "weight": 2 }
  ],
  "checks": {
    "active": {
      "http_path": "/health",
      "interval": 5
    }
  },
  "retries": 3,
  "timeout": { "connect": 5, "send": 10, "read": 10 }
}
```

### 5. 健康检查

- **Active**：APISIX 主动探活
- **Passive**：被动剔除（连续 N 次失败）
- **上游自动剔除** + **恢复**

## 六、插件生态

### 1. 内置插件分类

| 类别 | 插件 |
| --- | --- |
| **认证** | `key-auth`、`basic-auth`、`jwt-auth`、`oauth2`、`hmac-auth`、`wolf-rbac`、`authz-casbin`、`openid-connect` |
| **安全** | `cors`、`csrf`、`ip-restriction`、`uri-blocker`、`bot-detection`、`referer-restriction` |
| **流量控制** | `limit-count`、`limit-req`、`limit-conn`、`proxy-cache`、`request-validation` |
| **可观测** | `prometheus`、`http-logger`、`tcp-logger`、`syslog`、`skywalking`、`opentelemetry`、`jaeger` |
| **转换** | `response-rewrite`、`proxy-rewrite`、`grpc-transcode`、`grpc-web`、`fault-injection` |
| **Serverless** | `serverless-pre-function`、`serverless-post-function`、`azure-functions`、`openwhisk`、`aws-lambda` |
| **协议** | `mqtt-proxy`、`kafka-proxy`、`dubbo-proxy` |

### 2. 启用插件

```bash
# 全局
curl -X PUT http://127.0.0.1:9080/apisix/admin/global_rules/1 \
  -H 'X-API-KEY: edd1c9f034335f136f87ad84b625c8f1' \
  -d '{"plugins":{"limit-count":{"count":100,"time_window":60,"key_type":"var","key":"remote_addr"}}}'

# 路由级
curl -X PATCH http://127.0.0.1:9080/apisix/admin/routes/1 \
  -H 'X-API-KEY: edd1c9f034335f136f87ad84b625c8f1' \
  -d '{"plugins":{"jwt-auth":{"key":"user-key"}}}'
```

### 3. 插件优先级

`Plugin metadata` 字段定义执行顺序，数字越小越先。

### 4. 多语言插件（Plugin Runner）

Java 示例（独立进程）：

```java
// /plugins/my-plugin/src/main/java/.../MyPlugin.java
public class MyPlugin implements Plugin {
    @Override
    public String getName() { return "MyPlugin"; }
    @Override
    public void filter(Request req, Response resp, PluginFilterChain chain) {
        // 业务逻辑
        chain.execute();
    }
}
```

注册：

```yaml
plugins:
  - my-plugin:9000
```

## 七、限流

### 1. limit-count

```json
{
  "limit-count": {
    "count": 100,
    "time_window": 60,
    "key_type": "var",
    "key": "remote_addr",
    "policy": "redis",
    "redis": {
      "host": "redis",
      "port": 6379
    },
    "rejected_code": 429
  }
}
```

### 2. 维度

- `var`：Nginx 变量
- `consumer`：Consumer 名
- `service_id` / `route_id`
- `header`
- 自定义 Lua 函数

### 3. limit-req（漏桶）

按瞬时速率限流：

```json
{
  "limit-req": {
    "rate": 10,
    "burst": 20,
    "key": "remote_addr"
  }
}
```

## 八、灰度发布

### 1. 基于 Header

```json
{
  "uri": "/api",
  "vars": [
    ["http_x_canary", "==", "true"]
  ],
  "upstream": {"nodes": {"canary:80": 1}}
}
```

### 2. 基于权重

```json
{
  "uri": "/api",
  "upstream": {
    "type": "roundrobin",
    "nodes": [
      {"host": "v1:80", "weight": 90},
      {"host": "v2:80", "weight": 10}
    ]
  }
}
```

### 3. traffic-split 插件

```json
{
  "traffic-split": {
    "rules": [
      {
        "weighted_upstreams": [
          {"upstream": {"name": "v1", "type": "roundrobin", "nodes": [{"host": "v1", "port": 80, "weight": 1}]}},
          {"upstream": {"name": "v2", "type": "roundrobin", "nodes": [{"host": "v2", "port": 80, "weight": 1}]}}
        ]
      }
    ]
  }
}
```

## 九、认证集成

### 1. JWT

```json
{
  "plugins": {
    "jwt-auth": {
      "key": "user-key",
      "secret": "my-secret",
      "algorithm": "HS256"
    }
  }
}
```

### 2. OIDC

```json
{
  "plugins": {
    "openid-connect": {
      "client_id": "my-app",
      "client_secret": "xxx",
      "discovery": "http://kc/realms/myrealm/.well-known/openid-configuration",
      "scope": "openid profile email"
    }
  }
}
```

### 3. Key Auth

```bash
# 创建 Consumer
curl -X POST .../apisix/admin/consumers \
  -d '{"username":"alice","plugins":{"key-auth":{"key":"alice-key"}}}'
```

## 十、可观测

### 1. Prometheus

启用 `prometheus` 插件后访问 `/apisix/prometheus/metrics`。

### 2. SkyWalking

```json
{
  "plugins": {
    "skywalking": {
      "endpoint": "http://skywalking:12800",
      "service_name": "apisix"
    }
  }
}
```

### 3. Trace（OpenTelemetry）

```json
{
  "plugins": {
    "opentelemetry": {
      "tracing_collector_endpoint": "http://otel-collector:4318"
    }
  }
}
```

## 十一、K8s Ingress Controller

### 1. CRD

```yaml
apiVersion: apisix.apache.org/v2
kind: ApisixRoute
metadata:
  name: my-app
spec:
  http:
    - name: rule1
      match:
        paths: ["/api/*"]
        hosts: ["app.example.com"]
      backends:
        - serviceName: my-app
          servicePort: 80
      plugins:
        - name: limit-count
          enable: true
          config:
            count: 100
            time_window: 60
```

### 2. ApisixPlugin / ApisixUpstream / ApisixTls

完整 CRD 体系，覆盖证书、插件、上游抽象。

## 十二、APISIX vs Kong

| 维度 | APISIX | Kong |
| --- | --- | --- |
| 配置中心 | etcd | Postgres |
| 路由 | Radix Tree | 链式匹配 |
| 热更新 | ms 级 | DB 模式秒级 |
| 插件 | Lua + 4 外部语言 | Lua + 2 外部语言 |
| Dashboard | 内置 | 商业（Konnect） |
| K8s | CRD 完善 | Ingress + CRD |
| 协议 | 全（含 UDP） | HTTP/gRPC/TCP |
| 性能 | 高（实测略高 Kong） | 高 |
| 文档 | 中文友好 | 英文为主 |

## 十三、典型场景

- **云原生入口网关**：K8s Ingress + 全协议
- **混合云 API 平台**：多集群 APISIX + etcd federation
- **Serverless 网关**：插件触发 Lambda / OpenWhisk
- **MQTT 代理**：物联网场景
- **GraphQL 聚合**：route + serverless 函数

## 十四、最佳实践

- **etcd 集群**：至少 3 节点；监控 leader；开启 client auth
- **限流用 Redis**：避免单点
- **证书管理**：cert-manager + ApisixTls
- **可观测**：Prometheus + SkyWalking + OTel
- **插件精简**：核心插件 < 5 个，全局插件更要少
- **路由优先级**：数字从 0 开始，留扩展空间
- **灰度**：traffic-split 优先于多 Route
- **Admin API 鉴权**：改默认 `X-API-KEY`
- **etcd 备份**：定期 snapshot
- **Dashboard RBAC**：内置用户管理
- **变更审计**：通过 admin API diff + Git diff
