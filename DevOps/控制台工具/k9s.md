# K9s

终端里的 K8s 全功能 UI，基于 curses 的交互式 CLI，运维工程师的「kubectl 加速器 + dashboard 替代品」。

## 一、定位与特性

- 单二进制 Go 程序，依赖 kubeconfig
- 全交互式：列表 → 选择 → 描述 → 编辑 → 删除，全程不用打完整 kubectl 命令
- 实时 watch 资源变化（默认 2s 刷新）
- 内建 RBAC 检查（看到就代表有权限）
- 跨平台：macOS / Linux / Windows
- 与 lens/dashboard 不冲突，是同一生态位的互补工具

## 二、安装

```bash
# macOS
brew install derailed/k9s/k9s

# Linux (deb)
curl -sS https://webi.sh/k9s | sh
# 或
curl -LO https://github.com/derailed/k9s/releases/latest/download/k9s_linux_amd64.deb
sudo dpkg -i k9s_linux_amd64.deb

# 二进制直装
curl -L -o /usr/local/bin/k9s \
  https://github.com/derailed/k9s/releases/download/v0.32.5/k9s_linux_amd64.tar.gz | tar xz

# 验证
k9s version
```

常用环境变量：

| 变量 | 含义 |
| ---- | ---- |
| `KUBECONFIG` | kubeconfig 路径（默认 `~/.kube/config`） |
| `K9S_CONFIG_DIR` | 配置目录（默认 `~/.config/k9s`） |
| `K9S_NAMESPACE` | 启动命名空间 |
| `K9S_CONTEXT` | 启动 context |

## 三、核心交互模型

### 1. 命令模式 `:`

冒号进入命令，目录式浏览：

```text
:po                # pod
:deploy            # deployment
:svc               # service
:ns                # namespace
:node              # node
:ctx               # context
:secret
:cm                # configmap
:ing               # ingress
:crd               # crd
:ev                # events
:hz                # 快捷键帮助
```

冒号里支持复合命令：

```text
:po prod           # namespace=prod 下所有 pod
:po -c dev         # context=dev 下所有 pod
:po -l app=nginx   # 按 label 过滤
```

### 2. 过滤模式 `/`

进入资源列表后按 `/`：

```text
/app=nginx         # label
/Pod               # 名字包含
/running           # 状态包含
!Completed         # 排除 Completed pod
```

支持多列过滤叠加：`/` 多次输入，列名自动补全。

### 3. 别名 alias

把自定义资源 / 常用组合命名成短命令：

```text
:gp        # = :po -l app=gateway
:web       # = :deploy -n web
```

### 4. 视图切换

- `>` / `<` 或方向键上下选行
- `Enter` 进入详情（describe 风格）
- `Esc` 退回上一级
- `0` 回到列表头

## 四、常用快捷键

| 键 | 作用 |
| ---- | ---- |
| `:` | 命令模式 |
| `/` | 过滤模式 |
| `?` / `F1` | 帮助 |
| `Ctrl+a` | 全选当前列表 |
| `Ctrl+d` / `d d` | 删除选中资源（两次 d 防误删） |
| `e` | 用默认编辑器（`$K9S_EDITOR`/`$EDITOR`）编辑 YAML |
| `y` | 查看 YAML |
| `d` | describe |
| `l` | 当前容器日志 |
| `L` | 切换到上个崩溃容器日志 |
| `p` | 上一容器（logs） |
| `n` | 下一容器（logs） |
| `s` | 进入容器 shell（exec） |
| `Shift+s` | 进入特权模式 shell（如有权限） |
| `Shift+f` | port-forward（弹窗输入 local:remote） |
| `Shift+l` | 切换 logs-full（不截断） |
| `Ctrl+z` | 后台当前 k9s（恢复 fg） |
| `Shift+x` | XRay（关联资源视图） |
| `Shift+p` | Pulse（集群仪表盘） |
| `Shift+b` | Benchmark（需插件） |
| `r` | 手动刷新 |
| `w` | 切换 watch 频率 |
| `f` | 跳到底部（follow 状态） |
| `k` / `j` | 上 / 下 |
| `g` / `G` | 跳到首 / 尾 |
| `Space` | 标记行 |
| `Ctrl+k` | 弹出 XRay/Pulse 详情 |

## 五、上下文与 namespace 切换

```text
:ctx                       # 列 context
:ctx dev                   # 切到 dev
:ctx .                     # 回到上一个 ctx

:ns                        # 列 namespace
:ns prod                   # 切到 prod
:ns all                    # 所有 namespace（cluster-wide）
```

切换后会话级生效，无需重启。`:ctx .` 记的是上一个 context，常用于「来回切」。

## 六、日志与终端

### 1. 日志

```text
# pod 列表里选中行 → l
:l                         # 当前容器日志
:ll                        # logs -l app=xxx
:pl                        # previous log（崩溃前）
```

`Shift+l` 切 `logs-full`，去掉 `--tail` 截断；`p` / `n` 在多容器 pod 上下切容器。日志界面输入 `/` 可搜索。

### 2. 容器 shell

```text
# 选中 pod → s
# 默认进入第一个容器 bash
```

容器里没 bash 时自动降级到 sh（`K9S_SHELL_SCRIPTS=/bin/bash,/bin/sh` 可配降级顺序）。退出用 `exit` 或 `Ctrl+d`。

### 3. port-forward

```text
# pod 列表 → Shift+f
# 弹窗输入：8000:80   或  9000:containerPort
```

后台跑，看 log 跟端口转发互不干扰。退出后端口转发自动停。

## 七、describe / edit / yaml

```text
y       # 看 YAML，支持 / 搜索、复制
e       # 编辑 YAML，保存即 apply
d       # describe，标准 kubectl describe 输出
```

- `e` 调用 `$K9S_EDITOR`（默认 vi/vim/nano）
- 保存时会触发 dry-run 风格的客户端校验，但不会做完整 schema 校验
- 危险改动（删 finalizers 等）k9s 不会二次拦截，全靠 RBAC

## 八、删除与伸缩

```text
d d         # 删除选中资源（两次 d 防误）
Ctrl+d      # 标记行删除（bulk delete）
```

Deployment 详情页：

```text
# 选中 deployment → 进入
# 顶部菜单会显示 scale 提示
# 直接键入数字回车 → 改 replicas
```

StatefulSet / ReplicaSet 同理。

## 九、XRay 视图

`Shift+x` 在选中资源上弹出关联图：

```text
Deployment ──► ReplicaSet ──► Pod
                          └──► Service
                          └──► ConfigMap
                          └──► Secret (volume)
```

是只读视图，常用于排查「为什么 service 打不到 pod」「哪些 configmap 被哪个 deployment 挂载」。

## 十、Pulse 仪表盘

```text
Shift+p
```

```text
┌─────────────────────┬─────────────────────┐
│  CPU  TOPx          │  MEM  TOPx           │
├─────────────────────┼─────────────────────┤
│  node-1 ████████    │  node-2 ████        │
│  node-2 ████        │  node-1 ███         │
├─────────────────────┴─────────────────────┤
│  Pods/Node (bar)                           │
│  PV/PVC used                               │
│  Namespaces count                          │
│  CRDs count                                │
└───────────────────────────────────────────┘
```

基于 metrics-server（先装 metrics-server，否则 CPU/内存列为空）。不会替代 Prometheus/Grafana，但是个 5 秒扫一眼集群健康度的利器。

## 十一、Popeye 集群体检集成

popeye 是 derailed/k9s 同作者做的 K8s 「sanitizer」，扫描集群安全/资源/配置问题：

```bash
brew install derailed/popeye/popeye
popeye -n kube-system
```

k9s 集成 popeye：

```text
Shift+b            # 调 popeye 扫描当前 namespace，结果在 k9s 内显示
```

或单独跑：

```bash
popeye -f ~/.config/k9s/popeye.yaml -o report.html -n dev
```

## 十二、benchmark（hey 压测）

`Shift+b` 在 service 上弹出 benchmark 配置：

```text
# 内部用 vegeta / hey 调用 service
# 弹窗配置：method / path / qps / duration
```

适合快速复现「为什么这个 service 慢」。生产慎用，会产生真实流量。

## 十三、配置文件

### 1. `~/.config/k9s/config.yaml`

```yaml
k9s:
  refreshRate: 2
  maxConnRetry: 5
  enableMouse: true
  headless: false
  logoless: false
  noIcons: false
  readOnly: false
  noPods: false
  activeNamespace: ""
  clusters:
    dev:
      namespace:
        active: dev
        lockScope: namespace
        favorites:
        - default
        - dev
        history:
          - dev
          - default
    prod:
      namespace:
        active: prod
  ui:
    enableMouse: true
    skin: monokai
  editor:
    args:
    - "+set\ terminal=xterm-256color"
    - "-c\ \"set\ fenc=utf-8\""
    cmd: vim
    env: []
  thresholds:
    cpu:
      critical: 90
      warn: 70
    memory:
      critical: 90
      warn: 75
```

`k9s` 启动后用 `:config` 进入可视化编辑器，所有改动自动落盘。

### 2. Skin 主题

内置主题：`monokai` / `dracula` / `solarized-light` / `solarized-dark` 等：

```yaml
# config.yaml
k9s:
  ui:
    skin: dracula
```

也可用 `:skin` 命令行切换。

## 十四、自定义 alias / hotkey / plugin

配置文件默认路径 `~/.config/k9s/`，可与 `XDG_CONFIG_HOME` 同步：

```text
~/.config/k9s/
├── config.yaml
├── alias.yaml
├── hotkeys.yaml
├── plugins.yaml
├── skins/
└── clusters/   # 多集群自定义
```

### 1. alias.yaml

```yaml
alias:
  # 别名 → 真正跑的 k8s 资源命令
  # 支持 gop 模板过滤
  pp: po prod
  gp: po -l app=gateway
  web: deploy -n web
  logall: pods -A
  hp: pods -A
  # CRD
  argocd: crd -l app.kubernetes.io/name=argocd
```

### 2. hotkeys.yaml

```yaml
hotKey:
  # 短命令 + 快捷键绑定
  po:
    shortCut: Shift-P
    description: All Pods
    command: po
  ctx:
    shortCut: Shift-C
    description: Contexts
    command: ctx
  scale-up:
    shortCut: "s+u"
    description: Scale Up
    command: scale --replicas +1
    background: false
    overrides: ["sc", "su"]
  log-prev:
    shortCut: "p+l"
    description: Previous Log
    command: logs --previous
    background: false
    scopes:
    - po
    overrides: ["plprev"]
```

### 3. plugins.yaml（真实例子：重置所有 CrashLoopBackOff Pod）

```yaml
plugins:
  # 描述、命令、快捷键
  bouncer:                                                           # 别名（:bouncer）
    shortCut: Shift-B
    description: Delete all CrashLoopBackOff pods in current ns
    scopes:
    - po
    command: sh
    background: false
    args:
    - -c
    - |
      for p in $(kubectl get pods --field-selector=status.phase!=Running -o name | sed 's|pod/||'); do
        state=$(kubectl get pod "$p" -o jsonpath='{.status.containerStatuses[*].state.waiting.reason}')
        if echo "$state" | grep -q CrashLoopBackOff; then
          echo "killing $p ($state)"
          kubectl delete pod "$p" --wait=false
        fi
      done
    overrides:
    - bc
```

k9s 把 `args` 拼成 shell 执行，所以能用 `kubectl` + `grep` / `sed` / `jq`。插件环境继承 kubeconfig。

## 十五、RBAC 受限时的表现

| 场景 | 表现 |
| ---- | ---- |
| **无 list pods** | `:po` 直接弹「Forbidden」横幅，列表空白 |
| **无 get pods/log** | pod 详情可看，`l` 看日志报错 |
| **无 create pods/exec** | `s` 进 shell 报 forbidden |
| **无 create pods/portforward** | `Shift+f` 报 forbidden |
| **namespace 隔离** | RBAC 没授权的 namespace 显示为空，看不到资源 |
| **CRD 受限** | 自定义资源进得去也读不到实例 |

k9s 不在客户端做越权，永远把 RBAC 当作单一事实源。这点比一些 web dashboard 老实得多。

## 十六、优缺点

### 优点

- 响应即时、键盘流操作远快于 web
- 单二进制，零依赖
- 资源可视化 + 实时 watch
- 插件机制灵活，能干掉一堆临时脚本
- 与现有 kubeconfig / RBAC 完全兼容
- 多集群切换成本极低

### 缺点

- **不擅长看长时间日志**：内置 pager 弱，大日志用 `l` 后用 `Shift+l` + 外部 less
- **终端字体宽度敏感**：表格列对不齐时体验差（建议 Nerd Font）
- **鼠标支持鸡肋**：能点但不如 web 自然
- **多人协作弱**：终端会话式，不适合同时几个人操作同一视图（kubectl 也一样）
- **没有持久化历史**：关了就关
- **CRD 视图有时识别不到**：依赖 OpenAPI v3 schema 注册质量

## 十七、最佳实践

- **键绑定肌肉记忆**：把 `d d` / `y` / `e` / `s` / `Shift+f` 练到下意识
- **`:alias` 个性化**：把每天必跑的 `:po -n x -l y` 折成 `:gp`
- **写 plugin 把重复操作固化**：reconcile、清理 crash pod、清 finalizer 等
- **生产 readOnly 模式**：`k9s --read-only`，禁用所有写操作（edit / delete / scale）
- **搭配 metrics-server**：`Shift+p` 才不空白
- **团队共享 alias/hotkey/plugins**：把 `~/.config/k9s/` 纳入 dotfiles 仓库
- **配合 kubectl**：k9s 不能做的（port-forward 后台跑很久、复杂 explain）回退 kubectl
- **容器里跑 k9s**：CI debug 用 `kubectl debug` / 边车容器里装 k9s 直连
- **定期 `k9s info`**：诊断自身启动问题（XDG、kubeconfig）
- **生产禁 benchmark 插件**：真实流量打穿 prod 是常见事故