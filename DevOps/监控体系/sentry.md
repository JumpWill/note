# Sentry

应用错误监控（Error Tracking）平台，覆盖前端、后端、移动端。支持 release / source map / issue assignment / 集成通知 / 监控告警。

## 一、定位

- 错误监控 + 性能监控（RUM / APM）
- 客户端为主
- 自托管或 SaaS（sentry.io / 国产替代如 OpenSentry / 闪测）
- 多语言 SDK：Python / Java / Node.js / Go / PHP / Ruby / .NET / Rust / Flutter / React Native / iOS / Android / 浏览器

## 二、组件

```text
┌──────────────────────────────────┐
│ Application SDK（自动捕获错误）     │
│   - Console / Unhandled / API    │
│   - 关联 Trace / Session        │
└─────────────┬────────────────────┘
              │ HTTPS / Envelope
              ▼
┌──────────────────────────────────┐
│ Relay（可选代理，签名 / 缓冲）     │
└─────────────┬────────────────────┘
              ▼
┌──────────────────────────────────┐
│ Sentry Server                     │
│   - Symbolicator / Processing    │
│   - Snuba / Events Store（ClickHouse）│
│   - Post-Processing              │
│   - Performance / Profiling       │
└─────────────┬────────────────────┘
              ▼
Web / SaaS UI
```

## 三、数据模型

### 1. Event

每次错误或性能事件：

- `event_id`
- `timestamp`
- `platform` / `runtime`
- `exception` / `stacktrace`
- `breadcrumbs`（面包屑）
- `release` / `environment`
- `tags` / `user`
- `request`
- `extra`
- `sdk` / `contexts`

### 2. Issue

事件聚合而成：

- 一组相同问题
- 一致的 fingerprint
- 状态变更：unresolved / resolved / ignored

### 3. Project / Organization

Project = 一个应用。

## 四、SDK 使用

### 1. Python（以 Django 为例）

```python
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.redis import RedisIntegration

sentry_sdk.init(
    dsn="https://<key>@<org>.ingest.sentry.io/<proj>",
    environment="prod",
    release="order-svc@2.4.1",
    traces_sample_rate=0.1,
    profiles_sample_rate=0.05,
    integrations=[
        DjangoIntegration(),
        CeleryIntegration(),
        RedisIntegration(),
    ],
    before_send=filter_healthcheck,
)
```

- `before_send`：`event` -> dict，可过滤敏感
- `traces_sample_rate`：性能追踪采样
- `profiles_sample_rate`：剖析采样

### 2. JavaScript / Browser

```js
import * as Sentry from "@sentry/browser";

Sentry.init({
  dsn: "https://...@...ingest.sentry.io/...",
  release: "web@1.2.3",
  environment: "prod",
  tracesSampleRate: 0.1,
  integrations: [
    new Sentry.BrowserTracing(),
    new Sentry.Replay(),
  ],
});
```

- Replay：会话回放（DOM / 网络）
- SourceMap 上传：release 时一起上传

### 3. Node.js

```js
import * as Sentry from "@sentry/node";
Sentry.init({ dsn: "...", tracesSampleRate: 0.2 });
```

### 4. Go

```go
err := sentry.Init(sentry.ClientOptions{
    Dsn: "https://...",
    Environment: "prod",
    Release: "order-svc@1.0.0",
    TracesSampleRate: 0.1,
})
defer sentry.Flush(2 * time.Second)
```

### 5. Mobile

iOS / Android / Flutter / React Native：

- Crash 后下次启动发送
- Offline / Online 都可缓冲

## 五、Source Map & Release

### 1. CLI 上传

```bash
npx sentry-cli releases new "$RELEASE_NAME"
npx sentry-cli releases files "$RELEASE_NAME" upload-sourcemaps ./dist
```

### 2. CI / CD

- 每次构建生成 release
- 在端错误信息变成源代码行号

### 3. Debug Files（Native）

```bash
sentry-cli debug-files upload --org o --project p path/to/dSYM
```

## 六、性能监控（RUM / APM）

### 1. Transaction

每个 `finish()` 的 span 视为 transaction：

```python
with sentry_sdk.start_transaction(name="GET /orders"):
    with sentry_sdk.start_span(op="db"):
        ...
```

### 2. 自动追踪

- Web 框架：HTTP 中间件
- 数据库：SQLAlchemy / Django ORM / 异步 DB
- Http：requests / urllib / httpx
- 缓存：Redis

### 3. Distributed Tracing

- 默认通过 headers `sentry-trace`
- 关联上游服务
- 可连 Jaeger / Tempo

### 4. Profile / Continuous Profiling

Sentry v22+ 支持持续剖析：

```python
sentry_sdk.init(..., profiles_sample_rate=0.2)
```

## 七、Replay

- 浏览器 / 移动端回放
- 自动采集 DOM / 交互 / 网络
- 默认 10% session
- 隐私模式：遮蔽 password / token 等

## 八、错误分组与 Fingerprint

- 默认按 stacktrace + exception type
- 自定义 `fingerprint` 强制分组
- tag: 影响 grouping

```python
with sentry_sdk.push_scope() as scope:
    scope.set_tag("customer_tier", "vip")
    scope.set_extra("cart_size", 12)
```

## 九、告警与分配

### 1. Alert Rule

```yaml
action: email/slack/pagerduty/dingtalk
conditions:
  - when: number_of_errors
    interval: 5 minutes
    threshold: 50
  - when: first_seen
```

或 Issue 状态变更告警。

### 2. Issue Owners

- 代码路径 owner 自动通知
- `CODEOWNERS` 集成

### 3. Workflow Automation

- Issue 新出现 → 自动加 tag / 分配
- 分级严重程度

## 十、Sentry 在 K8s / 微服务

- 一个 project / 一组服务
- 通过 tag 区分（service / env）
- Through 大，DSN 单独 project 隔离
- Performance per service

## 十一、自部署

```bash
# Docker Compose
git clone https://github.com/getsentry/self-hosted
./install.sh
```

资源：

- Postgres
- Redis
- ClickHouse（Snuba 用）
- Kafka / ZooKeeper
- 多个 Sentry Service（web / worker / cron / relay / symbolicator）

### 1. Snuba

事件存储后端（基于 ClickHouse）。

### 2. Relay

HTTP / gRPC 代理：限流 / 缓冲 / 签名。

### 3. Symbolicator

还原 stacktrace 行号。

## 十二、性能与容量

- 单实例：~ 50k events/day
- 集群：分片 + Kafka
- ClickHouse 压缩：~ 80% 节约空间

## 十三、国产替代

| 工具 | 备注 |
| ---- | ---- |
| **OpenSentry**（开源） | 社区版 |
| **闪测 (FlashDuty)** | 国内 SaaS |
| **阿里云 ARMS 错误监控** | 阿里云 |
| **腾讯云 CAT** | 腾讯云 |
| **fundebug** | 国产 SaaS |
| **听云** | APM SaaS |

## 十四、自定义与扩展

- 自定义 Event Processor
- 自定义 Transport
- Inbound WebHook（如 GitLab / GitHub -> Sentry）
- 集成：Jira / Slack / Linear / GitHub Issue / Notion

## 十五、安全

- DSN 控制可访问性
- 自部署过滤：去掉敏感 header / body
- `before_send`：过滤 token / password
- Sensitive data：`request.headers` 屏蔽

## 十六、最佳实践

- **Release 必填**：定位 commits
- **Tag 充分**：业务上下文
- **采样**：根据数据量调整 trace_sample_rate
- **Source Map 上传**在 CI
- **Issue 循环**：自动解决、新错误强制分配
- **Replay 仅调试**：默认 sample 5~10%
- **过滤器**：去除无关错误（404 / 健康检查）
- **集成 APM**：升级性能监控
