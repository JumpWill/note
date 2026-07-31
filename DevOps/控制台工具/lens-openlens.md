# Lens / OpenLens

K8s 桌面端 IDE 风格的 GUI 控制台，Electron + 内嵌 kubectl + 每集群一个 lens-k8s-proxy 进程。Lens 商业化后，OpenLens 成为社区主线。

## 一、定位与特性

- 桌面应用（macOS / Linux / Windows），原生多集群管理
- 内部走 kubeconfig，等价于「GUI 化的 kubectl」
- 内置 Helm、Prometheus 集成（指标视图）、日志、终端、YAML 编辑
- 工作负载视图比 kubectl get 直观得多（Deployment → Pod → 容器树）
- 早期 v3/v4 是 Mirantis 开源，社区版；v5+ Lens 收归商业公司后变为收费（部分功能），社区 fork 出 OpenLens

## 二、架构

```text
┌────────────────────────────────────────────┐
│  Lens Desktop (Electron 渲染进程)          │
│   - Renderer (React/TypeScript UI)         │
│   - 主进程                                  │
└────────────────────────────────────────────┘
                    │
                    │  WebSocket / HTTP (本地 loopback)
                    ▼
┌────────────────────────────────────────────┐
│  kubectl 子进程 (Lens 内嵌)                │
│  ~/.kube/lens 临时 kubeconfig               │
└────────────────────────────────────────────┘
                    │
                    │  kubeconfig + 凭据转发
                    ▼
┌────────────────────────────────────────────┐
│  每个集群一个独立进程                        │
│  lens-k8s-proxy (Go)                       │
│  - ClusterRoleBinding                       │
│  - 暴露 service account token                │
│  - Lens UI 用它做 port-forward / exec      │
└────────────────────────────────────────────┘
                    │
                    ▼
             kube-apiserver
```

- **Electron**：UI 容器，把 React 应用跑在浏览器引擎里
- **内嵌 kubectl**：每个操作映射成 kubectl 调用，避免重新实现 K8s 协议
- **lens-k8s-proxy**：在远程集群（或本地）起的代理 Pod，负责把 port-forward、exec、log 流转发回 Lens UI
- **Extension API**：v5+ 收费，OpenLens 早期版本保留，Freelens 保留大部分扩展能力

### 2. 安装 lens-k8s-proxy

Lens 第一次接入集群会：

1. 在目标集群建 `kube-system` 下的 `lens` ServiceAccount + ClusterRoleBinding + Deployment `lens-k8s-proxy`
2. 起一个 DaemonSet/Deployment 形式的 proxy pod
3. 通过该 pod 转发 exec/log/port-forward 流量

清理：

```bash
kubectl delete clusterrolebinding lens
kubectl delete sa lens -n kube-system
kubectl delete deploy lens-k8s-proxy -n kube-system
```

## 三、Lens Desktop 与 OpenLens 的关系

| 项目 | 维护方 | 状态 | 备注 |
| ---- | ---- | ---- | ---- |
| **Lens Desktop** | Mirantis（后被 Akamai 收购期间变阵）| 商业化，主仓库 `lensapp/lens` | v5+ 部分功能收费，扩展市场受限 |
| **OpenLens** | 社区 fork `MuhammedKalkan/OpenLens` | 社区维护 | 6.x 系列最后一版开源版本，扩展 API 完整 |
| **OpenLens-legacy** | `openlens-community` | 维护分支 | 跟上游 OpenLens 有偏移 |
| **Freelens** | `freelensapp/freelens` | 活跃社区 fork | 保留扩展 API、对 Helm 3 支持更好 |
| **k8slens** | `k8slens/k8slens` | 旁支 | 不再活跃 |

> 版本线混乱：建议生产内固定一个 fork，统一打包规则。

### 1. Lens Desktop 安装

```bash
# macOS
brew install --cask lens

# 或官网 dmg
# https://k8slens.dev/

# Linux (AppImage)
chmod +x lens-*.AppImage
./lens-*.AppImage
```

### 2. OpenLens 安装

```bash
# GitHub release 下载
# https://github.com/MuhammedKalkan/OpenLens/releases

# Linux deb
sudo dpkg -i OpenLens-*.deb

# macOS dmg
# Windows msi
```

## 四、扩展被移除后如何装回

v6 之后的 Lens Desktop 移除了原「Lens Extensions」市场（含 Pod Logs/Terminal 增强扩展），需要在 OpenLens 或 Freelens 才能用。

OpenLens 装扩展：

```text
File → Extensions → Install Extension
  → 选择 .tar / .tar.gz / 目录
  → 自动 reload
```

或者手工把扩展扔进：

```text
~/Library/Application Support/Lens/plugins/
# Linux: ~/.config/Lens/plugins/
# Windows: %APPDATA%\Lens\plugins\
```

常见扩展列表：

| 扩展 | 功能 |
| ---- | ---- |
| `@k8slens/pod-manager` | Pod 操作增强 |
| `lens-pod-logs-extension` | 多容器日志着色、过滤 |
| `lens-terminal-tabs` | 终端多 Tab |
| `flux-extension` | Flux HelmRelease/Kustomization 视图 |
| `argocd-extension` | ArgoCD App 视图 |
| `prometheus-extension` | 内嵌 Prometheus query UI |

OpenLens 时代的扩展大多可用；新写扩展要按 v5 Extension API。

## 五、集群接入

### 1. kubeconfig 自动导入

```text
首次启动 → Lens 扫描默认路径
  - ~/.kube/config
  - kubectl 自带 kubeconfig
  - ~/.lens/config.json
```

多集群自动列出，可为每个集群配置：

- 显示名 / 别名
- 默认 namespace
- 工作目录（Helm chart 路径）
- Prometheus 来源
- 标签（prod / staging）

### 2. 手动添加

```text
Clusters → Add Cluster
  - From kubeconfig（粘贴）
  - From file（选 kubeconfig 文件）
  - From URL（http(s)://server:port）
```

自定义 kubeconfig 示例：

```yaml
apiVersion: v1
kind: Config
clusters:
- name: prod
  cluster:
    server: https://k8s-prod.example.com:6443
    certificate-authority-data: <base64>
contexts:
- name: prod-ctx
  context:
    cluster: prod
    user: prod-user
current-context: prod-ctx
users:
- name: prod-user
  user:
    exec:
      apiVersion: client.authentication.k8s.io/v1
      command: /usr/local/bin/aws-iam-authenticator
      args: ["token", "-i", "my-cluster"]
      env:
      - name: AWS_PROFILE
        value: prod
```

exec 凭据插件（如 aws-iam-authenticator、gke-gcloud-auth-plugin、kubelogin）在 Lens 内部会 fork 调用，跟本地 kubectl 等价。

### 3. 集群设置

每个集群右键 → Settings：

| 设置 | 含义 |
| ---- | ---- |
| **Default namespace** | 启动默认 namespace |
| **Helm charts folder** | helm 模板本地目录 |
| **Metrics** | Prometheus URL（自动建议） |
| **Icon** | 自定义图标 |
| **Labels** | 自定义标签，用于过滤 |
| **kubeconfig context override** | 自定义不同上下文 |

## 六、内置功能

### 1. 工作负载视图

```text
Workloads
  ├─ Pods
  ├─ Deployments
  ├─ StatefulSets
  ├─ DaemonSets
  ├─ ReplicaSets
  ├─ Jobs
  ├─ CronJobs
  ├─ Services
  ├─ Ingresses
  ├─ ConfigMaps
  ├─ Secrets
  ├─ HPAs
  ├─ PDBs
  ├─ NetworkPolicies
  └─ ... (CRDs 自动识别)
```

- 每个资源有详情页：Events、Conditions、Owner References、YAML
- 右键菜单：Edit / Delete / Restart（Deployment）/ Scale / Port Forward / Logs / Terminal

### 2. Metrics

需要外部 Prometheus，Lens 不内置存储：

```text
Cluster Settings → Metrics → Add
  URL:  http://prometheus.monitoring:9090
  Prometheus 工作目录（可选）
```

接上后：

- Pod/Node 详情页多出 Prometheus query 面板
- 集群总览多了 CPU/Memory/网络曲线
- Lens 在 Helm 部署时自动尝试 service-monitor 模式

不接 Prometheus 时这些面板空白，不是 Bug。

### 3. Helm Release 管理

```text
Helm → Releases
```

- 列表显示已装的 release、版本、状态、values 摘要
- 详情可看 manifest、values、revision 历史
- 「Upgrade」直接选 chart 文件 / OCI repo
- 「Rollback」选历史 revision
- 注意：Lens 早期版本 Helm 2/3 都有，6.x 默认 Helm 3

### 4. 内置终端

```text
Workloads → Pods → 选中 → 右键 Open Terminal
```

- 默认 bash，容器没 bash 时降级到 sh
- 多 Tab，多 Pod
- 支持 ANSI 颜色

> 这是基于 lens-k8s-proxy 的 exec 流量，本质还是 kubectl exec。

### 5. YAML 编辑

```text
任意资源 → Edit
  - Monaco Editor（VS Code 同款）
  - 保存 = kubectl apply
  - 支持 YAML 模板片段
```

不会做 schema 校验（依赖 apiserver），但会显示 dry-run 错误。

## 七、Lens Extension API

OpenLens/Freelens 保留 v5 Extension API：

```typescript
import { LensMainExtension } from "@k8slens/extensions";

export default class MyExtension extends LensMainExtension {
  clusterPages = [
    {
      id: "my-page",
      title: "My View",
      component: MyComponent,
    },
  ];

  kubeObjectMenuItems = [
    {
      kind: "Pod",
      title: "Snapshot",
      icon: "camera",
      action: (kubeObject) => snapshot(kubeObject),
    },
  ];

  clusterFeatureHandlers = [
    {
      path: "/my-route",
      handler: "my-handler",
    },
  ];
}
```

打包：

```bash
npm run build
npm pack    # 生成 my-ext.tgz
# 把 tgz 放到 ~/Library/Application Support/Lens/plugins/
```

## 八、资源占用问题

Lens 是 Electron 应用，资源占用偏高是公认问题：

| 资源 | 典型占用 | 备注 |
| ---- | ---- | ---- |
| **内存** | 600MB-1.5GB | 多个集群时叠加 |
| **磁盘** | 500MB+ | Electron 运行时 + Lens 自身 |
| **CPU** | 空闲 < 1%，watch 时 5-10% | 集群多时上升 |

优化建议：

- 不要一次性加载所有集群，按需切换
- 关闭不活跃集群的 watch（Settings → Auto Refresh）
- macOS 关闭自动更新降低 IO
- Linux 用 AppImage 而非 deb（不污染系统）
- 不需要 IDE 时用 k9s 替代，资源占用 < 50MB

## 九、替代品对比

| 工具 | 形态 | 优势 | 劣势 |
| ---- | ---- | ---- | ---- |
| **Lens Desktop** | Electron 桌面 | 商业支持，UI 现代 | 部分功能收费，扩展受限 |
| **OpenLens** | Electron 桌面 fork | 完全免费，扩展 API 完整 | 维护节奏跟随社区 |
| **Freelens** | Electron 桌面 fork | 扩展 API，活跃 | 生态尚小 |
| **Headlamp** | Web + 桌面 | CNCF 沙箱，多语言，扩展 React-based | 部署稍复杂 |
| **Aptakube** | Electron 桌面 | 极简、快 | 功能少 |
| **k9s** | 终端 TUI | 极低资源，键盘流 | 不能多人共享视图 |
| **Rancher** | 多集群 Web | 多 K8s 发行版、策略、审计 | 重型 |
| **Portainer** | Web | 多容器平台 | 不是 K8s 原生 |

### 1. Headlamp 简介

CNCF 沙箱项目，可装在集群内或本地：

```bash
helm repo add headlamp https://headlamp-k8s.github.io/headlamp/
helm install headlamp headlamp/headlamp -n kube-system
```

特点：纯前端 React + 可插拔插件，能通过 OIDC 接企业 SSO。

### 2. Aptakube

主打「轻量级 Lens 体验」，适合不需要 Helm / Prometheus 视图的个人。

## 十、企业内使用的合规注意

- **每个集群建 lens ServiceAccount + ClusterRoleBinding**：
  - 默认是 cluster-admin 权限（K8s 内任何能改 kubelet-metric 的身份都能拿）
  - 建议改用细粒度 Role：限定 namespace
- **lens-k8s-proxy 留痕**：
  - 审计日志会看到 lens SA 的所有动作
  - 合规要求严格时关掉或自托管自定义 proxy
- **kubeconfig 凭据存本地**：
  - 桌面应用本地存储 kubeconfig 与 token
  - 满足 SOC2/PCI 的企业要确保本地磁盘加密（FileVault / BitLocker）
- **数据出境**：
  - Lens Analytics 默认开启，会回传使用遥测
  - Settings → Telemetry 关闭
- **代理**：
  - exec/port-forward 走 lens-k8s-proxy，需在公司网络白名单放通 apiserver
- **升级节奏**：
  - OpenLens/Freelens 升级比 Lens Desktop 慢，但不会被商业策略切功能

## 十一、优缺点

### 优点

- UI 美观，资源视图直观（Deployment → Pod → Container 树）
- 多集群切换成本极低
- 内置 Helm、Prometheus、Terminal、Logs
- YAML 编辑器（Monaco）体验好
- kubeconfig 自动扫描
- OpenLens/Freelens 完全免费可用

### 缺点

- 资源占用高（Electron 通病）
- Lens Desktop 商业化（部分功能收费，扩展市场受限）
- OpenLens 主线社区维护节奏放缓，部分功能陈旧
- 网络受限环境（公司 NTLM 代理、严格防火墙）装插件难
- **认证中心化在本地 kubeconfig**：设备丢失 = 集群泄露
- 没有内置审计/合规报表
- 没接 SSO 时只能靠 kubeconfig

## 十二、最佳实践

- **企业内推 OpenLens/Freelens**：避开商业功能，切合合规
- **每个集群建最小权限 SA**：不要默认 cluster-admin
- **关闭遥测**：Settings → Privacy → Disable Analytics
- **Prometheus 显式配置**：不要让 Lens 自动猜，造成无意义的网络扫描
- **Helm charts 目录隔离**：dev / staging / prod 各自一份仓库路径，避免误升
- **升级前 export kubeconfig**：Lens 升级偶尔会重置 ~/.kube/config 的自定义部分
- **多集群分窗口**：不要把 30 个集群塞一个 Lens，用 --user-data-dir 分实例
- **关键集群同时配 k9s**：Lens 卡死 / 装不上时降级到 k9s 不影响排查
- **审计外置**：用 apiserver audit log + lens SA 监控 lens 操作
- **长期演进考虑 Headlamp**：如果对 SaaS 化、企业内嵌有要求，Headlamp 比 Electron 更合云原生调性