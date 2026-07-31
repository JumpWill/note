# Authorization（授权框架）

AuthN（你是谁）+ AuthZ（你能做什么），本文件讨论授权主流框架。

## 1. OPA (Open Policy Agent)

CNCF 毕业的策略引擎，Rego DSL 表达策略，跨多平台。

### 1. 定位与特点

- DSL `Rego` 表达策略
- 服务 + Library + Sidecar 多种部署模式
- 数据驱动：可注入外部数据
- 高性能（Go 实现）
- 多语言 SDK：Go / Python / JS / Rust / Java

### 2. 部署

```bash
opa run -s server # 单进程 server
opa eval -d input.json -d policy.rego 'data.example.allow'
```

### 3. Rego 基础

```rego
package http.authz

default allow = false

allow {
    input.method = "GET"
    input.path = ["public", _]
}

allow {
    user := input.user
    user.role == "admin"
}

allow {
    user := input.user
    user.role == "operator"
    input.method = "GET"
    input.path = ["ops", _]
}
```

### 4. 集成模式

| 模式 | 含义 |
| ---- | ---- |
| **Sidecar** | 应用 → OPA 本地（最常用） |
| **Daemon** | 节点级共享 |
| **Remote** | 集中式服务 |
| **Library** | 函数打包进应用 |
| **Wasm** | Rego 编译为 WASM 在浏览器 |

### 5. K8s / GitOps

- Gatekeeper：K8s admission webhook
- Konstraint：Constrained 策略到 CRD

```yaml
# constraint.yaml
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: K8sRequiredLabels
metadata:
  name: pod-must-have-label
spec:
  match:
    kinds:
      - apiGroups: [""]
        kinds: ["Pod"]
  parameters:
    labels:
      - key: "app.kubernetes.io/name"
```

### 6. REST API

```text
POST /v1/data/http/authz/allow
Content-Type: application/json

{
  "input": {
    "user": {"role": "admin"},
    "method": "GET",
    "path": ["orders"]
  }
}
```

返回 `result.allow: true`。

## 2. Casbin

国产开源授权库，跨语言（Go / Java / Python / Node.js / Rust / PHP / .NET）。

### 1. 定位

- 库而非服务
- 配置文件描述策略
- 多模型：RBAC / ABAC / ACL / Restful

### 2. 模型

```text
# model.conf
[request_definition]
r = sub, obj, act

[policy_definition]
p = sub, obj, act

[role_definition]
g = _, _

[policy_effect]
e = some(where (p.eft == allow))

[matchers]
m = g(r.sub, p.sub) && r.obj == p.obj && r.act == p.act
```

策略文件：

```text
p, alice, order, read
p, bob, order, write
p, ops, *, *

g, alice, ops
g, bob, ops
```

### 3. 用法

```go
e, _ := casbin.NewEnforcer("model.conf", "policy.csv")
allowed, _ := e.Enforce("alice", "order", "read")  // true
```

### 4. 持久化

- File
- Postgres / MySQL
- Redis
- Remote API（casbin-server）

### 5. Watcher / Adapter

```go
w := Watcher.NewWatcher("redis://localhost")
e.SetWatcher(w)
```

动态加载策略。

### 6. 与 BFF / API Gateway

非常适合把策略内置到 API Gateway / BFF：

```python
from casbin import Enforcer
e = Enforcer("model.conf", "policy.csv")

@app.route("/api/<obj>/<act>")
def handler(obj, act):
    if e.enforce(g.user, obj, act):
        return handle()
    return 403
```

### 7. Casdoor 集成

Casdoor 的权限模型底层用 Casbin。

## 3. Cerbos

现代基于策略的授权服务。YAML / Rego？支持决策图。

### 1. 定位

- 服务化授权（HTTP / gRPC）
- 内嵌 SDK（embedded）
- 多语言支持
- 决策日志 / 审计

### 2. 部署

```bash
cerbos server --config=/path/config.yaml
```

### 3. 策略

```yaml
apiVersion: api.cerbos.dev/v1
resourcePolicies:
  orders:
    - resource: order
      rules:
        - actions: ["read"]
          effect: EFFECT_ALLOW
          condition:
            match:
              expr: request.principal.attr.role == "ops"

        - actions: ["view"]
          effect: EFFECT_ALLOW
          condition:
            match:
              expr: request.resource.attr.user_id == request.principal.id
```

### 4. 决策 API

```text
POST /api/check
{
  "requestId": "x",
  "principal": {"id": "alice", "roles": ["devops"]},
  "resource": {"kind": "order", "id": "1"},
  "actions": ["read"]
}
```

返回 `EFFECT_ALLOW`。

### 5. 与 LangChain（AI）

策略 schema 可被大模型调用。

## 4. OpenFGA

源自 Auth0 FGA（Fine-Grained Authorization）。基于 Google Zanzibar 模型。

### 1. 定位

- 关系模型 / 关系元组（relations tuples）
- 适合：社交关注、文档共享权限
- SDK：Go / Python / Node.js / .NET / Java

### 2. 模型

```yaml
model:
  name: document
  type: document
  relations:
    writer:
      types: [user]
    viewer:
      types: [user]
      unions: [writer]
```

### 3. 关系元组

```
POST /stores/main/write
{
  "tuple": {
    "object": "document:readme",
    "relation": "writer",
    "user": "user:alice"
  }
}
```

### 4. 检查

```
POST /stores/main/check
{
  "tuple_key": {
    "object": "document:readme",
    "relation": "writer",
    "user": "user:alice"
  }
}
```

返回 `allowed: true`。

### 5. 与 Ory Keto 对比

与 Ory Keto 同一思路（Zanzibar）：

- OpenFGA：易用、性能好
- Ory Keto：早期推广、ORM 优化

## 5. Keto

Ory 的 Keto 是更激进的 Zanzibar 实现：

### 1. 概念

```text
namespace: object#relation@user
```

### 2. API

- `/check` 检查
- `/expand` 展开（递归查询）
- `/relation-tuples` 写关系
- ORM DSL 建模

## 6. OSO

Polar 语言的授权策略库 + SaaS。

### 1. 定位

- Polar DSL 学习门槛低
- 内置 RBAC / ReBAC

### 2. Polar 示例

```polar
allow(user, "view", project) if
  project in user.projects;
```

## 7. SpiceDB

Authzed 提供的 Zanzibar 商业版。

### 1. 定位

- 高性能 / 高可用
- Schema 描述关系
- HTTP / gRPC 接口

### 2. Schema

```text
definition user {}

definition document {
  relation viewer: user
  relation editor: user
  permission view = viewer + editor
}
```

### 3. 关系 API

```text
Lookit: wiewers of document:abc
```

## 8. 选型对比

| 工具 | 模型 | 形态 | 易用性 | 性能 | ReBAC |
| ---- | ---- | ---- | ------ | ---- | ----- |
| **OPA** | Rego DSL | 服务 / sidecar | 中 | 中-高 | 中 |
| **Casbin** | 文件 / 库 | 库 | 高 | 中 | ❌ |
| **Cerbos** | YAML / Rego | 服务 | 高 | 中 | ✔ |
| **OpenFGA** | JSON / ORM | 服务 | 高 | 高 | ✔ |
| **Keto** | ORM DSL | 服务 | 中 | 中 | ✔ |
| **SpiceDB** | Schema | 服务 | 高 | 高 | ✔ |
| **OSO** | Polar DSL | 库 | 中 | 中 | 部分 |

## 9. 选型建议

| 场景 | 建议 |
| ---- | ---- |
| K8s 准入控制 | OPA Gatekeeper |
| 应用层 RBAC | Casbin（轻量）或 Cerbos / OpenFGA |
| 多云 API Gateway 策略 | OPA / Styra DAS |
| 关系模型（GitHub 风） | OpenFGA / Keto / SpiceDB |
| 嵌入式 Go 库 | Casbin |
| 需要审计 / 决策图 | Cerbos |
| 多语言 SDK | OPA / OpenFGA |

## 10. 决策审计 / 可观测

| 工具 | 决策日志 |
| ---- | -------- |
| **OPA** | Decision Logger |
| **Cerbos** | Decision Log / Audit |
| **OpenFGA** | 加 Collector |
| **Keto** | 加 hook |

## 11. 与 LDAP / RBAC IdP 关系

- IdP（Keycloak）颁发 token 包含 role claim
- 业务应用再细粒度交给 Authorization SDK
- 每隔一段时间同步（用户 → 组 → 角色 → 权限）

## 12. 最佳实践

- **AuthZ / AuthN 边界**：AuthN 由 IdP 出，AuthZ 由专门系统
- **决策点统一**：所有读路径走到同一授权
- **缓存**：高频检查用本地缓存
- **审计**：关键决策落地
- **策略版本**：用 GitOps 维护
- **单元测试**：策略 DSL 测试要齐
- **冷启动数据**：服务依赖外部数据时，调用初始化
