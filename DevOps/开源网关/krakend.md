# KrakenD

高性能 API Gateway 的极简代表：纯只读配置 + 后端聚合 + 单 Go 二进制。无 Dashboard、无插件热加载，适合"配置即代码"的微服务聚合场景。

## 一、定位与特点

- 极简 API Gateway：只读 JSON 配置
- 后端聚合（Aggregate / Fan-in）：一次请求合并多个后端
- 单一可执行文件（Go 编写）
- 高性能：实测 P99 极低
- 无 Dashboard、无 Admin API（设计哲学：不可运行时改）
- 插件：中间件 / 修改器（修改请求/响应）

## 二、架构

```text
┌────────────────────────────────────┐
│  Client                            │
└─────────────┬──────────────────────┘
              │
              ▼
┌────────────────────────────────────┐
│  KrakenD (Go binary)               │
│   - Router                         │
│   - Middleware Pipeline            │
│   - Aggregator (parallel)          │
│   - Response Merger                │
└─────┬───────────┬──────────┬────────┘
      │           │          │
      ▼           ▼          ▼
  Backend A   Backend B   Backend C
```

特点：

- 启动加载 `krakend.json`
- 不连外部存储
- 进程内聚合（不依赖外部编排）

## 三、核心概念

| 概念 | 含义 |
| --- | --- |
| **Endpoint** | 客户端可见的路由 |
| **Backend** | 上游服务 |
| **Endpoint + Backends** | 一对多，聚合 / 链式 |
| **Method** | GET / POST / PUT / DELETE |
| **Middleware** | 通用管道（限流 / 鉴权 / 日志） |
| **Modifier** | 修改请求/响应（headers / body） |
| **ExtraConfig** | 插件扩展配置 |

## 四、部署

### 1. 单二进制

```bash
# 下载
wget https://github.com/krakendio/krakend-ce/releases/latest/download/krakend-ce-linux-amd64.tar.gz
tar -xzf krakend-ce-linux-amd64.tar.gz

# 校验配置
./krakend check -c krakend.json

# 启动
./krakend run -c krakend.json
```

### 2. Docker

```bash
docker run -p 8080:8080 \
  -v "$PWD:/etc/krakend" \
  devopsfaith/krakend:2.7 \
  run -c /etc/krakend/krakend.json
```

### 3. K8s

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: krakend
spec:
  replicas: 2
  template:
    spec:
      containers:
        - name: krakend
          image: devopsfaith/krakend:2.7
          args: ["run", "-c", "/etc/krakend/krakend.json"]
          ports:
            - containerPort: 8080
          volumeMounts:
            - name: cfg
              mountPath: /etc/krakend
      volumes:
        - name: cfg
          configMap:
            name: krakend-config
```

### 4. FlexConfig

支持环境变量替换：

```json
{
  "port": "${PORT:-8080}",
  "host": "${HOST:-0.0.0.0}"
}
```

## 五、配置文件

### 1. 基础结构

```json
{
  "version": 3,
  "port": 8080,
  "host": ["http://0.0.0.0:8080"],
  "endpoints": [
    {
      "endpoint": "/users/{id}",
      "method": "GET",
      "backend": [
        {
          "url_pattern": "/users/{id}",
          "host": ["http://users-svc:80"]
        }
      ]
    }
  ]
}
```

### 2. 路由参数

- `{id}`：路径参数
- `{name:.*}`：正则匹配

### 3. 多个 Backend

```json
{
  "endpoint": "/users/{id}/profile",
  "backend": [
    {
      "url_pattern": "/users/{id}",
      "host": ["http://users-svc:80"]
    },
    {
      "url_pattern": "/profiles/{id}",
      "host": ["http://profile-svc:80"]
    }
  ],
  "extra_config": {
    "backend/parallel": {
      "backends": ["users", "profiles"]
    },
    "merger": {
      "type": "const",
      "value": "merged"
    }
  }
}
```

## 六、后端聚合

### 1. 三种合并策略

| 类型 | 行为 |
| --- | --- |
| `const` | 合并到固定 key |
| `append` | 追加到数组 |
| `replace` | 覆盖 |

### 2. 完整示例

```json
{
  "endpoint": "/dashboard",
  "method": "GET",
  "backend": [
    {
      "url_pattern": "/users/me",
      "host": ["http://users-svc"],
      "encoding": "json"
    },
    {
      "url_pattern": "/notifications",
      "host": ["http://notif-svc"]
    },
    {
      "url_pattern": "/metrics",
      "host": ["http://metrics-svc"]
    }
  ],
  "extra_config": {
    "backend/parallel": {},
    "merger": {
      "type": "const",
      "value": "data"
    }
  }
}
```

客户端一次请求 `/dashboard`，KrakenD 并发请求三个上游，合并结果。

### 3. 顺序 vs 并行

- **默认并行**：`extra_config: { "backend/parallel": {} }`
- **顺序链式**：不设置 parallel，按数组顺序调用

## 七、Middleware 管道

### 1. 插件式中间件

```json
{
  "extra_config": {
    "plugin/req-resp-modifier": {
      "modifier/headers": {
        "req": [
          {"name": "X-From", "value": "krakend"}
        ],
        "resp": [
          {"name": "X-Cache", "value": "miss"}
        ]
      }
    }
  }
}
```

### 2. 限流（krakend-rate-limit）

```json
{
  "extra_config": {
    "qos/ratelimit/proxy": {
      "max_rate": 100,
      "client_max_rate": 10,
      "strategy": "ip"
    }
  }
}
```

策略：

- `ip`：按客户端 IP
- `header`：按 Header
- `endpoint`：按路由

### 3. 熔断（circuit breaker）

```json
{
  "extra_config": {
    "qos/circuit-breaker": {
      "interval": 60,
      "timeout": 30,
      "max_errors": 5,
      "min_requests": 10
    }
  }
}
```

### 4. 鉴权（JWT）

```json
{
  "extra_config": {
    "auth/validator": {
      "alg": "HS256",
      "key": "secret",
      "cookie": "session",
      "disable_jwt_security": false
    }
  }
}
```

### 5. CORS

```json
{
  "extra_config": {
    "security/cors": {
      "allow_origins": ["https://app.example.com"],
      "allow_methods": ["GET", "POST"],
      "allow_headers": ["Authorization"]
    }
  }
}
```

## 八、Modifier（请求/响应修改）

### 1. Headers

```json
{
  "extra_config": {
    "modifier/headers": {
      "req": [
        {"name": "X-Internal-Token", "value": "secret"},
        {"name": "X-Forwarded-For", "value": "krakend"}
      ],
      "resp": [
        {"name": "X-Gateway", "value": "krakend"}
      ]
    }
  }
```

### 2. Body

```json
{
  "extra_config": {
    "modifier/body": {
      "req": [
        {"path": "$.user.id", "value": "1"}
      ]
    }
  }
}
```

用 JSONPath 修改请求/响应体。

## 九、可观测

### 1. 日志

```json
{
  "extra_config": {
    "logger": {
      "level": "DEBUG",
      "prefix": "[KRAKEND]",
      "syslog": false
    }
  }
}
```

支持：

- stdout
- syslog
- Graylog（GELF）
- Logstash
- 文件

### 2. Metrics（OpenTelemetry）

```json
{
  "extra_config": {
    "telemetry/opentelemetry": {
      "service_name": "krakend",
      "exporters": {
        "otlp": [
          {"name": "otlp/collector", "host": "otel:4317", "disable_secure": true}
        ]
      }
    }
  }
}
```

### 3. StatsD

```json
{
  "extra_config": {
    "telemetry/statsd": {
      "host": "statsd:8125",
      "prefix": "krakend"
    }
  }
}
```

### 4. Prometheus

通过 OpenTelemetry → Prometheus exporter。

## 十、性能

### 1. 优化清单

- **编码**：`encoding: "json"` 加速解析
- **连接池**：复用 HTTP 连接
- **并发**：默认并行 backend
- **压缩**：服务端响应压缩
- **缓存**：`proxy-cache` 中间件

### 2. 基准

| 场景 | 性能 |
| --- | --- |
| 简单代理 | 几万 QPS |
| 3 后端聚合 | 几千 QPS |
| P99 延迟 | 几 ms |

## 十一、KrakenD vs Kong / APISIX

| 维度 | KrakenD | Kong | APISIX |
| --- | --- | --- | --- |
| 运行时配置 | ❌ 只读 | ✔ | ✔ |
| Dashboard | ❌ | ✔（商业） | ✔ |
| 聚合 | **核心功能** | 插件 | 插件 |
| 鉴权插件 | 简单 JWT 等 | 全套 | 全套 |
| 限流 | 简单 | 高级 | 高级 |
| 性能 | **极高** | 高 | 高 |
| 学习曲线 | 低 | 中 | 中 |

## 十二、典型场景

- **BFF（Backend for Frontend）**：聚合多个微服务为前端一个端点
- **API 聚合**：移动端减少请求数
- **网关前置**：已有完整网关，需要聚合层
- **边缘聚合**：CDN 边缘节点聚合源站
- **无状态 API**：纯只读配置，可大规模横向扩展

## 十三、最佳实践

- **配置 GitOps**：配置进仓库，CI 校验 + 部署
- **环境变量替换**：用 `${ENV}` 注入差异
- **FlexConfig 拆分**：大配置拆多个文件
- **避免运行期修改**：设计原则就是不热改
- **健康检查**：依赖 K8s livenessProbe
- **日志统一**：stdout → Fluent Bit / Loki
- **Metrics**：OpenTelemetry 一站式
- **后端超时**：每个 backend 单独设
- **熔断必开**：保护后端
- **限流**：按 IP + 路径双维度
