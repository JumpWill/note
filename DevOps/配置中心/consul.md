# Consul

HashiCorp 的多合一服务网格组件，三层一身：服务发现 + 健康检查 + KV 配置 + 多数据中心 + 服务网格（Connect）。

## 一、定位与特性

- KV：API 级别的 KV 存储 + `blocking query` 增量通知，做配置中心很顺手
- Service Discovery：服务注册、健康检查、查询（DNS / HTTP / gRPC）
- Multi-Datacenter：原生多 DC 同步，「全球集群」这件事的早期代表
- Service Mesh（Connect）：Consul 1.6+ 提供 mTLS、Intentions、Sidecar / 边车模式
- Raft 集群 + Gossip 通信：Server 内部走 Raft，Agent 集群走 Gossip（Serf）
- ACL Token：基于策略的服务/节点/KV 权限

```text
┌────────────── DC1 ──────────────┐  ┌────────────── DC2 ──────────────┐
│  Server       Server       Server│  │  Server       Server       Server│
│   ▲             ▲             ▲  │  │   ▲             ▲             ▲  │
│   │ Raft        │ Raft        │  │  │   │ Raft        │ Raft        │  │
│   └─────────────┘             │  │  │   └─────────────┘             │
│           ▲                   │  │  │           ▲                   │
│     Client│Agent (gossip LAN) │  │  │     Client│Agent (gossip LAN) │
│           ▲                   │  │  │           ▲                   │
│  ┌────────┴────────┐          │  │  │  ┌────────┴────────┐          │
│  │  App+Sidecar    │          │  │  │  │  App+Sidecar    │          │
│  └─────────────────┘          │  │  │  └─────────────────┘          │
└──────────────┬────────────────┘  └──────────────┬────────────────┘
               │                                  │
               └──── WAN gossip (Serf) ───────────┘
```

## 二、架构

### 1. Agent 角色

| 角色 | 职责 |
| ---- | ---- |
| **Server** | Raft 复制组的一员，存 KV / catalog / ACL，-dev 模式下单机充当 |
| **Client** | 轻量 Agent，所有 service/agent 注册先到 client，再走 gossip 同步；client 不存数据 |
| **Server+Client** | 部署也是 server 但同时跑服务（中小规模常见） |

### 2. Gossip

- 集群内：UDP/lan gossip（Serf 协议），增量、最终一致
- 集群间：WAN gossip（TCP/8302 端口），跨 DC 复制 catalog / intent / failure
- 一个 Agent 死掉，30 秒内被识别；新加入的 Node 数分钟收敛

### 3. 端口

| 端口 | 用途 |
| ---- | ---- |
| 8300/tcp | Server RPC（LAN） |
| 8301/tcp+udp | Serf LAN |
| 8302/tcp | Serf WAN（DC 间） |
| 8500/http | HTTP API / UI |
| 8600/udp | DNS 接口 |
| 8503/tcp | HTTPS（启用 tls 时） |

## 三、KV 数据模型

```text
/v1/kv/path/to/key     -> PUT / GET / DELETE
/v1/kv/path/to?recurse -> DELETE 一个 prefix
```

- key/value 都是 opaque bytes（与 etcd 一样不解释）
- 单 value 推荐 ≤ 8 KB，10KB 仍可，更大应该上 Vault / S3
- CAS（Check-and-Set）：用 `X-Consul-Index` 头部做乐观写
- flags uint64 + modify index（集群内全局递增），与 etcd 的 revision 等价

```bash
# 写
curl -X PUT -d 'value1' http://127.0.0.1:8500/v1/kv/config/myapp/db

# 带 index / flags 的 CAS
curl -X PUT -d '{"host":"db1"}' http://127.0.0.1:8500/v1/kv/config/myapp/db?cas=42

# prefix 读 + recurse
curl http://127.0.0.1:8500/v1/kv/config/myapp/?recurse

# 工具
consul kv put config/myapp/db '{"host":"db1"}'
consul kv get config/myapp/db
consul kv get -recurse config/myapp/
consul kv delete -recurse config/myapp/
consul kv import config/ backend.yaml
```

## 四、Blocking Query 长轮询

阻塞查询是 Consul 的「订阅能力」：

```text
client                                                 server
  │   GET /v1/kv/config?recurse                        │
  │   X-Consul-Index: 0  (init/任意起）                  │
  │──────────────────────────────────────────────────▶│
  │   200 + index=42   body=当前                        │
  │   ◀────────────────────────────────────────────────│
  │   (server wait until: index 变化 OR timeout)       │
  │   GET (retry)                                      │
  │   X-Consul-Index: 42                               │
  │──────────────────────────────────────────────────▶│
  │   200 + index=44   (期间发生变化)                    │
  │◀────────────────────────────────────────────────│
```

要点：

- **响应头 `X-Consul-Index`**：客户端下次把它塞到请求头里
- **最长 hold**：`?blocking` 默认 10 秒，可调到 60 秒
- **ID 是单调递增**：与 etcd revision 等价，可做断线追赶
- **无变化**也会因超时返回，下一次继续 long poll
- **多 key 看一个 index**：get-put 的 mod-index 来自 Raft log 全局位置，覆盖 catalog / KV

代码示例（Go）：

```go
import (
    "encoding/json"
    "flag"
    "fmt"
    "io"
    "net/http"
    "strconv"
    "time"
)

func watchKV(addr, prefix string) {
    var index uint64
    for {
        url := fmt.Sprintf("%s/v1/kv/%s?recurse&wait=10s", addr, prefix)
        req, _ := http.NewRequest("GET", url, nil)
        if index > 0 {
            req.Header.Set("X-Consul-Index", strconv.FormatUint(index, 10))
        }
        resp, err := http.DefaultClient.Do(req)
        if err != nil { time.Sleep(time.Second); continue }
        b, _ := io.ReadAll(resp.Body)
        resp.Body.Close()

        newIdx, _ := strconv.ParseUint(resp.Header.Get("X-Consul-Index"), 10, 64)
        if newIdx == 0 || newIdx == index {
            continue // timeout, no change
        }
        index = newIdx

        var items []struct {
            Key, Value string
            ModifyIndex uint64
        }
        json.Unmarshal(b, &items)
        for _, kv := range items {
            fmt.Printf("[%d] %s = %s\n", kv.ModifyIndex, kv.Key, kv.Value)
        }
    }
}

func main() { flag.Parse(); watchKV("http://127.0.0.1:8500", "config/myapp") }
```

## 五、Watch（Consul watch / template）

### 1. consul watch（HCL）

```hcl
# /etc/consul.d/watch/config.hcl
services = [""]    # 服务变化触发
handler  = "bash /etc/consul.d/reload.sh reload nginx"

# 或 KV 触发
key_prefix           = "config/myapp/"
type                 = "keyprefix"
handler              = "consul-template -config /etc/consul.d/consul-template.hcl"
```

### 2. consul-template

```hcl
# /etc/consul-template.d/config.hcl
consul {
  address = "127.0.0.1:8500"
  retry   { enabled = true; attempts = 5 }
}

template {
  source      = "/etc/confd/templates/myapp.conf.tmpl"
  destination = "/etc/myapp/myapp.conf"
  perms       = 0644
  command     = "systemctl reload myapp || true"
}
```

```go-template
# templates/myapp.conf.tmpl
upstream db {
  server {{ key "config/myapp/db" }};
}
listen {{ key "config/myapp/port" }};
```

```bash
consul-template -config /etc/consul-template.d/config.hcl
```

- consul-template 维护 watch 状态 + 渲染模板 + `command` 触发 reload
- `-once` 用于跑一次退出，便于 init container

## 六、Session 与分布式锁

### 1. Session

- 绑定 ttl 的「角色」，过期自动失效 → 用于 leader 选举、状态锁
- Session 与 Consul 1.0+ 的 locking API 配套

### 2. KV 锁

```bash
# 拿 session
SID=$(curl -X PUT -d '{"name":"app-lock","ttl":"15s"}' \
       http://127.0.0.1:8500/v1/session/create | jq -r .ID)

# acquire：CAS 把 key 写到空值并设 session
curl -X PUT -X-PUT -d '{"host":"db1"}' \
    -H "X-Consul-Index: 0" \
    http://127.0.0.1:8500/v1/kv/locks/db?acquire=$SID

# release / release 自动失效
curl -X PUT http://127.0.0.1:8500/v1/kv/locks/db?release=$SID
```

- `?acquire=&sid=` 仅在 key 不存在时 PUT
- `?release=&sid=` 由 session 失效自动触发
- 配合 blocking query，可以做「leader watchdog 争抢」

### 3. Lock API（推荐）

```bash
curl -X PUT http://127.0.0.1:8500/v1/locks/db \
     -H 'X-Lock-Name: db-mutex'
# returns /v1/locks/db/.lock-DESCRIPTOR
```

## 七、ACL Token

Consul 1.4+ 是 ACL v2 / Token System：

| 对象 | 含义 |
| ---- | ---- |
| **token** | 不透明 string，藏在 env / Header `X-Consul-Token` |
| **policy** | 一组规则，对应 `acl/policies` |
| **role** | 多个 policy + 多 identity 的容器 |
| **auth method** | Kubernetes / AWS IAM / JWT，自动生成 token |

```hcl
# policy.hcl
node "ip-10-0-0-*" {
  policy = "read"
}

service "billing" {
  policy = "write"
}

key_prefix "config/myapp/" {
  policy = "read"
}

# deny 优先级高于 allow
deny {
  service "" { policy = "write" }
}
```

```bash
consul acl policy create -name "myapp-ro" -rules @policy.hcl
consul acl token create -policy-name myapp-ro -description "app readonly"
```

- 客户端用 `X-Consul-Token` 或 query `?token=` 传 token
- ACL 默认 disabled；生产必须开

## 八、Vault 与 Consul 的关系

| 工具 | 主责 | Consul KV |
| ---- | ---- | ---- |
| **Consul KV** | 配置、服务发现，注册信息 | 当配置中心用时配置可见给所有读 KV token 的服务 |
| **Vault** | 秘密、证书、动态凭证 | Consul 可作 Vault 的 storage backend，也可被 Consul 用于「service identity」读 token |

**Consul 不是 Vault 的替代品**：

- Consul KV 内容 admin 可见，存 secret 太裸
- Vault 的 secret 有 lease / 撤销 / audit log
- 实际部署：Consul 存非敏感配置 + 集群元数据，敏感数据走 Vault，Vault 可读 Consul 拿 service identity
- Consul 的「Connect mTLS」与 Vault 的 PKI engine 配合：CA 证书在 Vault，业务证书由 Consul Connect 派生

## 九、Spring Cloud Consul Config

### 1. 引入

```xml
<dependency>
  <groupId>org.springframework.cloud</groupId>
  <artifactId>spring-cloud-starter-consul-config</artifactId>
</dependency>
<dependency>
  <groupId>org.springframework.cloud</groupId>
  <artifactId>spring-cloud-starter-bootstrap</artifactId>
</dependency>
```

### 2. 配置

```yaml
# application.yml
spring:
  application:
    name: myapp
  cloud:
    consul:
      host: 127.0.0.1
      port: 8500
      config:
        prefix: config        # 默认 config，可改
        default-context: application
        profile-separator: ','
        format: yaml
        # data-key: data     # 默认为 data
      discovery:
        enabled: true
```

### 3. 路径规则

```text
{spring.cloud.consul.config.prefix}/
   {spring.application.name}/
     {profile}/
        data  -> 顶层配置
```

例：

```yaml
# prefix=配置 是 config
# 应用名 = myapp
# profile = prod
```

KV 路径：`config/myapp/prod/data`

```yaml
# config/myapp/prod/data  的内容
server:
  port: 8080
spring:
  datasource:
    url: jdbc:mysql://...
logging:
  level:
    root: INFO
```

### 4. 刷新

```yaml
management:
  endpoints:
    web:
      exposure:
        include: refresh,health,info
spring:
  cloud:
    consul:
      config:
        watch:
          enabled: true
          delay: 1000
```

- 启动时拉全量 + 后台 long-poll，KV 变化触发 `EnvironmentChangeEvent`，`@RefreshScope` Bean 自动重建
- KV 也可存 JSON/Properties，取决于 format 配置

## 十、HTTP / gRPC API 示例（多 DC 同步）

### 1. Cross-DC 同步语义

```text
DC1.put("config/myapp/db", value)
  │
  ▼
DC1 Raft commit, index=42
  │
  ▼
gossip LAN in DC1 (秒级)
  │
  ▼
WAN 同步到 DC2（最终一致，典型 1~2 秒）
  │
  ▼
DC2 的 watcher 看到 index=42 之后 600ms 收到
```

- DC 间无法保证强一致（与 K8s 多集群同源难题），适合「配置」与「catalog」类业务，不适合抢锁

### 2. dc=DC2 查询

```bash
curl 'http://consul-dc2:8500/v1/kv/config/myapp/db?dc=dc2'
```

### 3. 跨 DC 服务发现

```bash
dig @127.0.0.1 -p 8600 myapp.service.consul    # 远端服务会带 multi-DC tag
```

## 十一、典型用法

| 场景 | 用 Consul 提供的什么 |
| ---- | ---- |
| 服务发现（Spring Cloud / Go） | 注册中心 + DNS / HTTP API |
| 配置中心（YAML/Props） | KV + blocking query；`/v1/agent/reload` |
| 多数据中心 | WAN gossip + 子目录 KV |
| 服务网格 | Consul Connect (mTLS + Intentions) |
| 分布式锁 | Session + KV CAS |
| 集群选举 | Session + Watch |

## 十二、优缺点

### 优点

- UI 开箱即用（`http://:8500/ui`），配置 / 节点 / 健康都能查
- 多数据中心「原生」支持，不靠外部同步工具
- KV + Service 在同一系统，注册/配置联动自然
- blocking query 是通用 LongPolling 协议，不绑定客户端语言
- Connect 提供零升级 mTLS，落地简单

### 缺点

- 写一致性：单 leader Raft 但 Server 集群通常 3~5 节点，量级上限 ≤ 万 ops/s
- KV value 大小限制：默认 8KB 推荐
- 跨 DC 一致性仅最终，配置同步有时间窗
- 生态对比 etcd：基于 Consul 的服务发现框架偏少，Spring Cloud Consul 用得不少，K8s 体系偏爱 etcd
- Vault 不是它替代品，仍要拆开用

适用：多数据中心需求、有现成 Spring Cloud Consul、强 UI 体验、Service Mesh 想减少组件数量。

## 十三、最佳实践

- **部署**：3 或 5 台 Server 起步，跨 AZ；Client 在每个 VM / Pod
- **Consul Cluster 名称**：用 ACID table 区分集群，-datacenter=dc1 / -datacenter=dc2
- **加密**：gossip encrypt + TLS + ACL token + audit，开启三件套
- **配置文件**：用 HCL 写 server.json / client.json，放 `/etc/consul.d/*.hcl` 多文件
- **容量调优**：`performance` 模式关闭 SQLite checksum 等开销，备份用 snapshot agent → S3
- **UI 仅内网**：8500 不暴露到公网
- **path 规划**：`{org}/{app}/{env}/{component}/{key}`，便于 recursive watch
- **数据同步**：敏感配置放 Vault + Consul connect 派生 token；服务列表、开关、非敏感阈值放 KV
- **reload 编排**：consul-template 触发的 systemctl reload 必须幂等
- **测试**：本地 `consul agent -dev` 是 1.7 时代前最稳的本地调试方式，配合 TestContainers / Docker
- **监控**：`consul_exporter` 拉 Prometheus，关键指标：leader changes、commit index、Raft apply latency
