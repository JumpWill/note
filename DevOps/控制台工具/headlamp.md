# Headlamp

CNCF Sandbox 项目，kinvolk（后被 Microsoft 收购）开源的现代 K8s Web UI。定位「可扩展的 K8s 控制台」，同时提供完整桌面 App 与集群内可部署的 Web 形态，常被用来替换 / 补充 Kubernetes Dashboard。

## 一、定位与特性

- 现代化 React/TypeScript 前端 + Go 后端
- 桌面 App（headlamp-app）：本地直接读 kubeconfig，连多集群
- 集群内部署（headlamp-server + headlamp-frontend）：内网统一访问
- 插件系统：TypeScript 插件可注册自定义视图、侧边栏、详情页、API 路由
- 不绑定分发商：原生 K8s，可对接任意 cluster
- 与官方的 Kubernetes Dashboard 思路一致，但 UI / 扩展性 / 多集群体验更现代

## 二、架构

```text
┌──────────────────────────────────────────────────────────┐
│                    Headlamp 前端                          │
│   - React + TypeScript SPA                                │
│   - Material UI 组件                                      │
│   - 插件运行时（动态加载插件 JS）                           │
└────────────────────────┬─────────────────────────────────┘
                         │ HTTPS / WebSocket
                         ▼
┌──────────────────────────────────────────────────────────┐
│                    Headlamp 后端 (Go)                     │
│   - kube client-go                                       │
│   - 仅做 API 代理（不持久化）                              │
│   - 认证中转（token / OIDC / client-cert）                │
│   - 插件 SSR / 静态资源托管                                │
└────────────────────────┬─────────────────────────────────┘
                         │ mTLS / Bearer
                         ▼
              kube-apiserver (s)
```

### 1. 桌面 App 形态

```text
┌──────────────────────────────────┐
│ Headlamp 桌面 App（Electron）      │
│   - 内嵌 headlamp-server (Go)    │
│   - 直接读 ~/.kube/config         │
│   - 浏览器打开 localhost:...     │
└──────────────────────────────────┘
```

- 启动时读取 `~/.kube/config`，无需任何服务端
- 在应用内切换 context / cluster
- 适合 DevOps 个人工作台

### 2. 集群内部署

```text
┌─────────────────────────────────────────────────┐
│   headlamp-server (Deployment)                  │
│   - 暴露 8080                                   │
│   - 接收前端静态 + 代理到集群 apiserver          │
│   - 认证用 ServiceAccount / OIDC                │
└─────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────┐
│   headlamp-frontend (ConfigMap / Nginx)         │
│   - 静态 React App                              │
│   - 反代 /api 到 headlamp-server                │
└─────────────────────────────────────────────────┘
```

- Helm chart：`headlamp-k8s/headlamp`
- 一个 chart 同时部署前后端，可独立扩缩

## 三、部署

### 1. Helm 安装

```bash
helm repo add headlamp https://kubernetes-sigs.github.io/headlamp
helm repo update
```

```yaml
# values.yaml
config:
  namespace: "headlamp"

# 启用 OIDC
oidc:
  enabled: true
  issuerUrl: "https://keycloak.example.com/realms/k8s"
  clientID: "headlamp"
  clientSecret: "<from-keycloak>"
  scopes: "openid profile email groups"

# 监听 Service
service:
  type: ClusterIP
  port: 80

# 节点端口 / Ingress 由外部决定
ingress:
  enabled: true
  className: nginx
  hosts:
    - host: k8s.example.com
      paths:
        - path: /
          pathType: Prefix
```

```bash
helm install headlamp headlamp/headlamp -n headlamp --create-namespace -f values.yaml
```

### 2. Ingress 暴露示例

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: headlamp
  namespace: headlamp
  annotations:
    nginx.ingress.kubernetes.io/proxy-body-size: "10m"
spec:
  ingressClassName: nginx
  rules:
    - host: k8s.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: headlamp
                port:
                  number: 80
```

### 3. 桌面 App

- 跨平台二进制：macOS / Linux / Windows
- 启动后自动读取 kubeconfig
- 内置 OIDC 登录（点 Cluster → Add → OIDC）
- 可视为「本地 kubectl 代理的 UI」

## 四、认证

### 1. Token 模式（最简）

```yaml
# 创建 ServiceAccount + ClusterRoleBinding
apiVersion: v1
kind: ServiceAccount
metadata:
  name: headlamp-admin
  namespace: headlamp
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: headlamp-admin
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: cluster-admin
subjects:
  - kind: ServiceAccount
    name: headlamp-admin
    namespace: headlamp
```

```bash
# 取 token
kubectl -n headlamp create token headlamp-admin
```

把这个 token 填到 Headlamp 登录页。

### 2. OIDC 模式

```yaml
oidc:
  enabled: true
  issuerUrl: "https://keycloak.example.com/realms/k8s"
  clientID: "headlamp"
  clientSecret: "<secret>"
  scopes: "openid profile email groups"
```

- Headlamp 后端会：
  - 跳浏览器到 Keycloak 登录
  - 拿到 ID token / refresh token
  - 用 access token 调 apiserver
  - 解析 groups 字段映射到 K8s RBAC

### 3. 客户端证书模式

桌面 App 直接用 kubeconfig 里的 client-certificate / client-key 认证，Headlamp 不参与。

### 4. 桌面 App 读 kubeconfig

- 默认 `~/.kube/config`
- 可在「+ Add Cluster」选 kubeconfig 路径
- 选定 context 后直接走 client-go，权限等于本机 kubectl

## 五、插件系统

### 1. 插件能做什么

| 注册项 | 含义 |
| ------ | ---- |
| `register.Lens` | 顶部菜单 / 名字空间菜单中加自定义视图 |
| `register.DetailsView` | 详情页中的额外 Tab |
| `register.DetailsViewHeader` | 详情页顶部 section |
| `register.SidebarItem` | 侧边栏自定义入口 |
| `register.Route` | 自定义路由 |
| `register.AppBarAction` | 顶部按钮 |
| `register.KubeObject` | 自定义资源显示 |
| `register.ResourceTableColumnsProcessor` | 表格列增强 |

### 2. 最小插件示例

```typescript
// my-plugin/src/index.tsx
import { register } from '@kinvolk/headlamp-plugin/lib';

register.registerSidebarItem({
  name: 'my-plugin',
  label: 'My Plugin',
  url: '/my-plugin',
  icon: 'https://example.com/icon.svg',
});

register.registerRoute({
  path: '/my-plugin',
  sidebar: 'my-plugin',
  component: () => <div>Hello from Headlamp!</div>,
});
```

```bash
# 用脚手架
npx create-headlamp-plugin my-plugin
cd my-plugin
npm install
npm run build
# 产物: dist/main.js → 上传到 ConfigMap / 远端 URL
```

### 3. 部署插件

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: headlamp-plugins
  namespace: headlamp
data:
  my-plugin.main.js: |
    // dist/main.js 内容
```

```yaml
# headlamp helm values
config:
  plugins:
    - name: my-plugin
      url: /static-plugins/my-plugin.main.js
```

后端启动时把 ConfigMap 挂到 `headlamp-server` 的静态目录，前端运行时通过 `dynamic import` 加载。

### 4. 真实插件例子

| 插件 | 用途 |
| ---- | ---- |
| `headlamp_kubernetes` | 强化 K8s 资源视图 |
| `cert-manager` | 证书状态可视化 |
| `prometheus` | 直接看 SLO / 面板 |
| `argo-cd` | Argo 状态集成 |
| `node-explorer` | 节点 / Pod 资源矩阵 |
| `pod-security` | 边车 / 安全检查 |

## 六、与官方 Kubernetes Dashboard 差异

| 维度 | Headlamp | Kubernetes Dashboard |
| ---- | -------- | -------------------- |
| 后端 | Go（直接 client-go） | Go（泛型） |
| 前端 | React + TypeScript | AngularJS（v2.x 已经在 Vue/React 化） |
| 插件 | 完整 API + TypeScript | 极少 |
| 桌面 App | 有 | 无 |
| 集群内 | 有 | 有 |
| 认证 | Token / OIDC / Client-cert | Token / OIDC / Kubeconfig |
| 多集群 | 切换 context / 集群 | 单集群（部署多实例） |
| 移动端 | 响应式 | 响应式 |
| 社区 | CNCF Sandbox | kubernetes/dashboard |
| 现状 | 活跃 | 维护模式 |

适用场景：

- 想换掉 angular 风格的官方 Dashboard
- 需要在桌面开发机直接连多集群
- 想做定制化视图（插件）

## 七、Portainer 对比

Portainer 是另一类「统一容器管理控制台」，覆盖 Docker + Swarm + K8s + Edge，比 Headlamp 更「运维平台」。

### 1. Portainer 定位

- **最初**：Docker UI（管理 Docker / Swarm）
- **现在**：容器平台控制台（Docker / Swarm / K8s / ACI / Edge）
- **用户**：不想直接执行 kubectl / docker 的运维 / 业务团队
- **形态**：服务端部署 + 浏览器访问（无桌面 App）

### 2. 架构

```text
┌─────────────────────────────────────────────┐
│        Portainer Server (Go)                 │
│   - UI + REST API + WebSocket               │
│   - 内部 SQLite / Postgres                  │
│   - 内置身份 / RBAC / 团队 / Endpoint Registry│
└──────┬───────────────┬───────────────┬──────┘
       │               │               │
   Portainer       Portainer       K8s API
   Agent (Edge)    Agent (DOCKER)  (直接)
```

- **Portainer Server**：单二进制，部署在容器 / VM 中
- **Portainer Edge Agent**：装在远端节点（Edge 场景），主动外连 Server
- **K8s 场景**：无需 agent，Server 直接连 kube-apiserver 与 kubelet

### 3. Environment / Endpoint 概念

Portainer 用「Environment」抽象一个被管对象：

| 类型 | 含义 |
| ---- | ---- |
| Docker Local | 本地 Docker |
| Docker Swarm | Swarm 集群 |
| Kubernetes | K8s 集群 |
| ACI / Nomad | Azure Container / HashiCorp Nomad |
| Edge Agent | 远端 agent 自注册 |

- 一个 Portainer Server 可纳管多个 Environment
- 环境级别的 RBAC
- 环境级别的访问 token，与 K8s 原生 RBAC 完全独立

### 4. K8s 支持范围与局限

| 能力 | 支持 |
| ---- | ---- |
| 部署 / Pod / Service / ConfigMap 等 CRUD | 有 |
| 命名空间 / 配额 | 有 |
| RBAC（K8s 原生） | 浏览 / 展示 |
| 自定义 CRD | 列表 + 查看 |
| Helm / 应用模板 | 有（自家 App Template） |
| Argo / Flux 集成 | 无 |
| 集群自省 / 故障诊断 | 弱 |
| 节点的 systemctl / shell | 弱 |
| 多集群统一 RBAC | Portainer 自身 RBAC |

局限：

- 不像 Argo / Rancher 那样能做 GitOps 完整闭环
- 不像 Lens / Headlamp 桌面版那样深度本地体验
- 复杂的 K8s 高级特性（CRD 详情 / 准入）覆盖有限

### 5. GitOps 能力

Portainer 提供「应用模板 + Stack」：

- **Stack**：可以从 Git 仓库 / manifest 部署
- **Compose**：Docker Compose 格式（Swarm / K8s 翻译）
- **App Templates**：管理员预定义 Helm / manifest 模板，业务侧一键部署

```yaml
# 简易 Stack：Git 仓库
URL: https://github.com/org/k8s-manifests
Compose file path: docker-compose.yml
```

Portainer 拉取 → 解析 → 调 K8s API Apply，不是真正的 GitOps controller（不会持续 reconcile），更像「升级按钮」。

### 6. Business vs CE 版

| 维度 | Community Edition (CE) | Business Edition (BE) |
| ---- | ---------------------- | ---------------------- |
| 价格 | 免费 | 订阅 |
| RBAC | 基础 | 高级 RBAC（角色 / 团队） |
| 审计日志 | 基础 | 完整审计 |
| SSO / SAML | 无 | 有 |
| Edge Agent | 有限 | 高级 |
| 备份 / 迁移 | 基础 | 完整 |
| 支持 | 社区 | 商业 |
| 多集群 | 有 | 有 |
| 限制 | 单实例限制 | 无 |

适用：

- CE：个人 / 小团队 / 内网
- BE：企业 / 多团队 / 合规 / SLA

### 7. Headlamp / Portainer / 其他控制台对比

| 维度 | Headlamp | Portainer | Rancher | Kubernetes Dashboard |
| ---- | -------- | --------- | ------- | -------------------- |
| 形态 | Web + 桌面 | Web | Web | Web |
| 多集群 | 桌面 App 切换 | 同一 Server 多 Environment | 强 | 单集群 |
| 插件 | 强（TS） | 弱（App Template） | 中（Catalog） | 弱 |
| 桌面体验 | 强 | 无 | 无 | 无 |
| Docker | 无 | 强 | 无 | 无 |
| GitOps | 无 | 弱（Stack） | 强（Fleet） | 无 |
| 适用 | DevOps 个人 / 团队 | 容器平台统一管 | 大规模多集群 | 最小化替代 |

### 8. 选择建议

- 想要现代化 UI + 桌面 App + 插件 → **Headlamp**
- 想要 Docker + K8s 统一管 + 业务自助 → **Portainer**
- 想要多套 K8s + Fleet GitOps + 企业 RBAC → **Rancher**
- 想要最小可行替代 → **Kubernetes Dashboard**

## 八、Headlamp 优缺点

### 优点

- 现代化 UI，移动端可用
- 插件体系完整，TypeScript 友好
- 桌面 App + 集群内双形态
- CNCF Sandbox，中立
- 社区贡献活跃（2024 起 Microsoft 投入增加）
- 多集群切换自然，桌面 App 体验顺滑

### 缺点

- 本身不做 RBAC，复用 K8s 原生 RBAC（这其实更安全但也意味着需要在集群侧配置）
- 插件生态仍在快速成长，覆盖的 K8s 高级特性不如 Rancher
- 集群内部署需要做 Ingress + 认证 + TLS
- 与 Argo / Loki / 监控体系集成需要插件支持
- 长期可观察性不如 Grafana / Rancher

### 适用

- DevOps 个人 / 小团队，希望本地直接管多集群
- 需要一个现代化 UI 替代 angular-style Dashboard
- 想基于它做内部定制化控制台（用插件）

## 九、最佳实践

- **认证优先 OIDC**：避免长期 token，把权限托给 IdP（Keycloak / Okta / Azure AD）
- **RBAC 拆分**：不要直接 cluster-admin，用「最小权限」ServiceAccount
- **桌面 App + 集群部署两套**：开发用桌面，运维用集群内
- **插件版本管理**：插件 JS 进 Git / OCI 镜像，用 helm value 控制启用
- **外部数据库**（Business / 自建 K8s）：不重要，因为 Headlamp 不持久化
- **HTTPS 加固**：生产前必有 Ingress + cert-manager，否则明文 token
- **审计**：集群 apiserver 开启 audit log，Headlamp 也可考虑前端接 SSO 审计
- **离线 / 内网**：插件从仓库提前下载打成 ConfigMap
- **OIDC 映射**：在 Keycloak 设 groups 映射到 K8s ClusterRoleGroups
- **多集群**：桌面 App 一次配所有 cluster，不在多集群间反复插拔 kubeconfig
