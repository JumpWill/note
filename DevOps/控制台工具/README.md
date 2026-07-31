# 控制台工具

按工具分文件整理 K8s 控制台 / 管理平台的原理与使用。

## 分类与索引

| 分类 | 工具 |
| --- | --- |
| **CLI / 终端** | [kubectl 及插件生态](kubectl-plugins.md)、[k9s](k9s.md) |
| **轻量 Web UI** | [Kubernetes Dashboard](kubernetes-dashboard.md)、[Headlamp / Portainer](headlamp.md) |
| **桌面客户端** | [Lens / OpenLens](lens-openlens.md) |
| **多集群管理平台** | [Rancher](rancher.md)、[KubeSphere](kubesphere.md) |
| **GitOps 控制台** | [Argo CD](argocd.md) |
| **观测控制台** | [Grafana / Kiali / Loki 矩阵](observability-console.md) |

## 选型速查

| 场景 | 建议 |
| --- | --- |
| 日常排障、SSH 到跳板机就干活 | [k9s](k9s.md) + [kubectl 插件](kubectl-plugins.md) |
| 只想给开发一个只读看板 | [Kubernetes Dashboard](kubernetes-dashboard.md)（限 namespace + 只读 RBAC） |
| 本地多集群来回切，要图形界面 | [Lens / OpenLens / Freelens](lens-openlens.md) |
| 要可扩展、要自己写插件的 Web UI | [Headlamp](headlamp.md) |
| 公司几十个集群，要统一纳管 + 多租户 | [Rancher](rancher.md) |
| 国产化 / 要开箱即用的全栈平台（DevOps + 网格 + 日志） | [KubeSphere](kubesphere.md) |
| 部署以 Git 为准，要看清 diff 和同步状态 | [Argo CD](argocd.md) |
| Docker 与 K8s 混合管理，团队非 K8s 专家 | Portainer（见 [headlamp.md](headlamp.md)） |
| 看指标、看拓扑、看日志 | [Grafana / Kiali / Loki](observability-console.md) |

## 概念对比

| 工具 | 形态 | 多集群 | 多租户模型 | 认证 | 写操作 | 扩展机制 | 资源开销 | 学习成本 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| kubectl | CLI | kubeconfig context | 靠 RBAC | kubeconfig | ✔ 全量 | krew 插件 | 极低 | 高（要记命令） |
| k9s | 终端 UI | context 切换 | 靠 RBAC | kubeconfig | ✔ 全量 | plugins.yaml | 极低 | 中 |
| Dashboard | 集群内 Web | ❌ 单集群 | 靠 RBAC | SA Token / kubeconfig | ✔ | ❌ | 低 | 低 |
| Headlamp | Web + 桌面 | ✔ | 靠 RBAC | Token / OIDC | ✔ | TS 插件 API | 低 | 低 |
| Lens / OpenLens | 桌面 | ✔ 多集群 | 靠 RBAC | kubeconfig | ✔ | Extension API | 高（Electron） | 低 |
| Portainer | Web | ✔ Agent | 团队 / 环境 | 本地 / OAuth / LDAP | ✔ | ❌ | 中 | 极低 |
| Rancher | Web 平台 | ✔ 核心能力 | Project + Namespace | LDAP/OIDC/SAML | ✔ | Fleet / Helm 应用 | 高 | 中 |
| KubeSphere | Web 平台 | ✔ 联邦 | 企业空间 / 项目 | 内置 + OIDC | ✔ | 可插拔组件 | 高 | 中 |
| Argo CD | Web + CLI | ✔ cluster secret | AppProject | SSO / Dex | 只改 Git（声明式） | CMP 插件 | 中 | 中 |
| Grafana 等 | Web | ✔ 数据源 | 组织 / 文件夹权限 | 多种 | ❌ 只读 | 插件 + 大盘 | 中 | 中 |

## 核心机制

- **本质都是 API Server 的前端**：所有控制台最终都调 `kube-apiserver`，能做什么由携带的凭证的 RBAC 决定。控制台自己不该有"超级权限绕过"，Dashboard 的历史 CVE 基本都栽在这
- **两种权限模型**：
  - *透传型*（k9s / Lens / Headlamp / Dashboard）：用用户自己的 kubeconfig 或 Token，权限 = 用户的 RBAC，审计日志里是真实用户
  - *代理型*（Rancher / KubeSphere / Portainer）：平台用自己的高权限 SA 访问集群，再在平台层做鉴权。好处是能做 K8s 没有的抽象（Project、企业空间），代价是 K8s 审计日志里全是平台 SA，需要平台自身的审计补齐
- **多集群的实现**：kubeconfig 多 context（客户端型）、Agent 反向长连接（Rancher cattle-agent、Portainer Agent，适合集群在防火墙后）、cluster secret 直连（Argo CD）
- **实时性**：几乎都基于 `watch` + informer 增量推送，UI 侧再走 WebSocket / SSE；列表页卡顿通常是没走 informer 缓存而在轮询 LIST
- **指标从哪来**：控制台自己不采集。`kubectl top` / Dashboard 依赖 metrics-server（只有实时值，无历史），趋势图一律要接 Prometheus

## 落地要点

- **给不同角色不同控制台**：SRE 用 k9s/kubectl，开发用只读 Web UI 看自己 namespace，管理层看 Grafana 大盘。别指望一个工具通吃
- **最小权限**：控制台账号按 namespace 发 RoleBinding，禁止随手 `cluster-admin`；Dashboard 关掉 skip login
- **不要裸暴露**：任何 Web 控制台都走 Ingress + TLS + SSO + IP 白名单，内网也一样
- **写操作走 GitOps**：能在 Argo CD 里改的就别在 UI 上点。UI 直接改的资源下次同步会被覆盖，且没有变更记录
- **控制台自身要监控**：平台型（Rancher/KubeSphere）本身就是有状态服务，它挂了会挡住所有人的排障路径，必须有备用的 kubectl 通道
- **资源占用**：KubeSphere/Rancher 全家桶起步就是十几个 GB 内存，小集群直接上是本末倒置
