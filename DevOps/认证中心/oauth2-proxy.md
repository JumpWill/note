# oauth2-proxy

Bitname / piontec / Quay 维护的开源 Reverse Proxy + OIDC。反向代理层做 OAuth2 / OIDC 登录流程 + Session + 头传递。

## 一、定位

- 在 Nginx / Traefik / Envoy 之前放一层验证
- 支持 Google / GitHub / GitLab / LinkedIn / Azure / OIDC
- 自带 Cookie Session
- Header forwarding → 后端凭据
- 不需改业务应用（适合老旧应用）

## 二、架构

```text
User
  │
  ▼
oauth2-proxy（OIDC / OAuth2 Provider → Cookie Session）
  │
  ▼
后端应用（通过 Header：X-Forwarded-User / X-Forwarded-Email / ...）
```

## 三、流程

```text
用户访问 https://app/secret
   │
   ▼
oauth2-proxy 拦截（404 路径）
   │
   ├─ Session 存在 + token 有效 → 注入 header → 转发
   │
   └─ Session 无 / 失效
         │
         ▼
       重定向到 OIDC Provider
         │
         ▼
       回调 /oauth2/callback
         │
         ▼
       设置 Cookie / Refresh Token
         │
         ▼
       转发
```

## 四、配置（命令行 / 文件）

### 1. 命令行

```bash
oauth2-proxy \
  --provider=keycloak-oidc \
  --client-id=... \
  --client-secret=... \
  --oidc-issuer-url=https://kc/realms/myrealm \
  --email-domain=* \
  --cookie-secret=... \
  --upstream=static=^http://static:8080 \
  --upstream=app=http://app:8080 \
  --http-address=:4180
```

### 2. 配置文件

```yaml
# oauth2-proxy.cfg
provider: "keycloak-oidc"
client_id: "my-app"
client_secret: "xxxxxx"
oidc_issuer_url: "https://kc/realms/myrealm"
email_domains:
  - "*"
upstreams:
  - id: app
    uri: http://app:8080
  - id: static
    static: true
    uri: http://static:8080
cookie_name: "_oauth2_proxy"
cookie_secret: "...32 bytes..."
session_lifetime: 24h
```

## 五、Provider

| 模式 | 含义 |
| ---- | ---- |
| **google** | Google Login |
| **github** | GitHub Apps / OAuth |
| **gitlab** | GitLab.com / 私有 |
| **linkedin** | LinkedIn |
| **azure** | Azure AD |
| **adfs** | ADFS（可选） |
| **keycloak-oidc** | Keycloak / OIDC |
| **oidc** | 通用 OIDC |

通过 `client_id / client_secret / issuer_url` 适配任意 OIDC IdP。

## 六、Cookie 与 Session

- Cookie 名：`_oauth2_proxy`
- 加密：AES-GCM，secret 长度至少 32 字节
- Session 保存 access_token / refresh_token / 用户信息
- Cookie 标志：HttpOnly / Secure / SameSite=Lax
- 失效：会话超时 + CSRF Token

CSRF：

- 路径参数 `state` 校验
- Cookie / Header 双重提交令牌

## 七、Header 传递

后端应用可读：

- `X-Forwarded-User`：用户名
- `X-Forwarded-Email`：邮件
- `X-Forwarded-Groups`：角色组
- `X-Forwarded-Preferred-Username`：username claim
- `X-Forwarded-Access-Token`：原始 access_token（可选）

```nginx
# 限制后端仅访问 X-Forwarded-User
proxy_set_header X-Forwarded-User $oauth2_user;
```

## 八、路由策略

```text
/api/*        -> upstream=app,auth=true
/static/*     -> upstream=static,auth=false
/healthz      -> upstream=null,auth=false
```

通过 `skip_auth_regex` / `skip_auth_route` / nginx_lua 灵活配置。

## 九、K8s 部署

### 1. ingress-nginx

```yaml
metadata:
  annotations:
    nginx.ingress.kubernetes.io/auth-url: "https://oauth2-proxy/oauth2/auth"
    nginx.ingress.kubernetes.io/auth-signin: "https://oauth2-proxy/oauth2/start?rd=$scheme://$host$request_uri"
spec:
  rules:
    - host: app.example.com
      http:
        paths:
          - path: /
            backend:
              service:
                name: app
                port: 80
```

### 2. Traefik

```yaml
labels:
  - "traefik.http.middlewares.oauth2-proxy.forwardauth.address=http://oauth2-proxy:4180"
  - "traefik.http.middlewares.oauth2-proxy.forwardauth.trustforwardheader=true"
  - "traefik.http.middlewares.oauth2-proxy.forwardauth.authResponseHeaders=X-Forwarded-User,X-Forwarded-Groups"
```

### 3. 直接替代 Ingress

```text
User → oauth2-proxy → App
```

用 K8s Deployment 运行 oauth2-proxy + 内部 Service。

## 十、常见模式

### 1. 静态域名 -> App

```text
oauth2-proxy 监听 443
  /api  -> app:8080 (auth)
  /static -> static:8080 (no auth)
```

### 2. 多 IdP

```text
不同 email 域 → 不同 Provider
```

### 3. 自定义 UI

`upstreams.static` 服务自己的 HTML 落地。

### 4. SSO 跨应用

多个 App 公用 oauth2-proxy 实例。

## 十一、Lifecycle Hook

```yaml
# config.cfg
silence_ping_logging: true
session_lifetime: 24h
session_cookie_min_lifetime: 5m
cookie_refresh: 1h
```

- session_lifetime：session 最长有效期
- cookie_refresh：访问后再次设置 cookie，刷新过期

## 十二、安全与最佳实践

- HTTPS 必须（cookie secure flag）
- Cookie secret 用 KMS 管理
- csrf 后端保护 / 随机 source
- 不要给静态 `/health` 暴露 session
- 配置 `allow_groups` 限制
- 启用 `pass_access_token` 控制后端信任

## 十三、可观测

访问日志：

```
http://oauth2-proxy:4180/oauth2/info -> 当前用户信息
```

- Prometheus：直接用文本指标 exporter
- 日志：JSON 输出 → Loki / ELK

## 十四、Theme / Branding

- 登录页内置
- `provider_login_parameters`
- 自定义 logo / css

## 十五、对 IAP / Pomerium 对比

| 工具 | 模式 | 优势 |
| ---- | ---- | ---- |
| **oauth2-proxy** | 反向代理 + OIDC | 简单经典 |
| **Pomerium** | 反向代理 + 策略 | 细粒度 |
| **Cloudflare Access** | SaaS | 零运维 |
| **Google IAP** | 仅 GCP | GCP 集成 |
| **Tailscale / Twingate** | 零信任 VPN | 应用层 zero trust |
| **Keycloak Gatekeeper** | 已停止维护 | 不再用 |

## 十六、与 Keycloak Gatekeeper

- Keycloak Gatekeeper（基于 Go）已停止
- oauth2-proxy 是社区继任者
- API 类似（header 注入）

## 十七、典型组合

### 1. Argo CD + oauth2-proxy

```text
用户访问 https://argo.example.com
   │
   ▼ oauth2-proxy
   │
Argo CD（读取 X-Forwarded-User 拿用户名）
   │
SSO 账号
```

### 2. Grafana + oauth2-proxy

Grafana 内置 generic_oauth，可以直接配 OIDC，无需 oauth2-proxy。但 oauth2-proxy 仍可在多 Grafana / 多应用统一登录态。

## 十八、安装

### 1. Docker

```bash
docker run -d --name oauth2-proxy \
  -p 4180:4180 \
  -v /path/to/oauth2-proxy.cfg:/etc/oauth2-proxy.cfg \
  quay.io/oauth2-proxy/oauth2-proxy:v7.6.0 \
  --config /etc/oauth2-proxy.cfg
```

### 2. K8s

```bash
helm repo add oauth2-proxy https://oauth2-proxy.github.io/manifests
helm install oauth2-proxy oauth2-proxy/oauth2-proxy
```

### 3. native

```bash
go install github.com/oauth2-proxy/oauth2-proxy/v7@latest
```

## 十九、最佳实践

- **`provider=keycloak-oidc`**：与 Keycloak 集成最稳
- **`email-domain`**：按白名单 / 用户域控制访问
- **session_lifetime**：8–24 小时
- **cookie_refresh**：1 小时
- **set_xauthrequest**：让后端有更多 claim
- **`pass_authorization_header`**：X-Forwarded-Access-Token 透传
- **groups claim**：将 Claim 反映到 X-Forwarded-Groups
- **关键应用**：secret + CSRF state 校验
