# Kubectl 与插件生态

kubectl 是 K8s 的官方 CLI，本身也是工程师最高频接触的「控制台」。理解它的工作原理、补齐插件生态，能把日常运维效率拉到另一档。

## 一、定位与特性

- K8s 官方 CLI，所有 K8s 发行版自带或一键安装
- 调用 kube-apiserver REST API 而非直接操作 etcd
- 通过 kubeconfig 管理多集群、多用户、多 namespace
- 插件生态（krew）使其可扩展为「瑞士军刀」：日志、调试、排障、容量分析
- 备份定位：SSH 之外的事实标准远程运维入口

## 二、工作原理

```text
┌────────────────────────────────────────────────────────────┐
│                       kubectl 进程                          │
│                                                            │
│  1. 加载 kubeconfig (~/.kube/config 或 $KUBECONFIG)         │
│       - clusters / contexts / users                        │
│       - current-context                                    │
│                                                            │
│  2. 构造 *rest.Config（CA / token / client-cert/Server）    │
│                                                            │
│  3. 启动 Discovery 客户端                                    │
│       - 拉 /api、/apis、/version                            │
│       - 缓存到 ~/.kube/cache/{discovery,http}              │
│                                                            │
│  4. REST Mapping                                           │
│       - 把 "kubectl get pod" 翻译成                         │
│         GET /api/v1/namespaces/{ns}/pods                    │
│                                                            │
│  5. 序列化请求（YAML/JSON → API 对象）                       │
│       - 校验 OpenAPI schema                                │
│       - 字段裁剪（prune）                                   │
│                                                            │
│  6. 走 HTTP 与 kube-apiserver 通信                           │
│       - 走 SPDY / WebSocket 升级（exec / attach / port-fwd）│
└─────────────────────┬──────────────────────────────────────┘
                      │ HTTPS/SPDY
                      ▼
              kube-apiserver
```

### 1. kubeconfig 解析

```yaml
apiVersion: v1
kind: Config
current-context: prod-admin
clusters:
  - name: prod
    cluster:
      server: https://api.prod.example.com:6443
      certificate-authority-data: <base64>
  - name: dev
    cluster:
      server: https://api.dev.example.com:6443
      insecure-skip-tls-verify: true
contexts:
  - name: prod-admin
    context:
      cluster: prod
      user: prod-admin
      namespace: payments
users:
  - name: prod-admin
    user:
      token: <bearer>
      # 或
      client-certificate-data: <base64>
      client-key-data: <base64>
```

加载顺序：

- `--kubeconfig` 参数 > `$KUBECONFIG`（可多个，分号 / 冒号分隔）> `~/.kube/config`
- 多文件合并：第一个文件的 `current-context` 生效，其他仅作为 context 池

### 2. Discovery 缓存

首次执行 `kubectl get` 时，kubectl 访问 apiserver 的 `/api`、`/apis` 拿到所有 group/version/resource 列表，写到 `~/.kube/cache/discovery/{host}/...`，有效期由 apiserver 的 Cache-Control 控制（通常几分钟）。

```bash
# 清理 discovery 缓存
rm -rf ~/.kube/cache/discovery
```

何时清理：

- 集群新增 / 升级 CRD 后
- 看到 `error: unable to recognize ...` 时
- 切换集群后旧集群文件不再需要

### 3. REST Mapping

kubectl 收到 `kubectl get pod -n kube-system` 时的内部流程：

```text
"pod" + (-n kube-system)
   │
   ▼
查 discovery：kind=Pod, group="", version=v1
   │
   ▼
REST mapping → namespaced resource
   │
   ▼
GET /api/v1/namespaces/kube-system/pods
```

- 表型 `pod` / 缩写 `po` 来自 OpenAPI 的 `shortNames` / `singularName`
- `kubectl api-resources` 给出完整映射表

### 4. OpenAPI 校验

`kubectl apply -f foo.yaml` 会：

- 用 OpenAPI v3 schema 校验字段类型 / 必填
- 裁剪未知字段（默认开启，可用 `--validate=strict` 报错）
- 客户端先校验 → 减少 apiserver 往返

### 5. Server-Side Apply 与 last-applied-configuration

**Client-Side Apply（kubectl apply 默认）**：

- kubectl 客户端跟踪上一次 apply 的结果，存在 annotation `kubectl.kubernetes.io/last-applied-configuration`
- 下次 apply 时 diff 客户端对象与 last-applied 的字段，得到「所有权」
- 缺点：多人多 client 时字段所有权会乱

**Server-Side Apply（`--server-side=true`）**：

- 字段所有权由 apiserver 跟踪，写到 `metadata.managedFields`
- 不依赖本地文件，不再维护 last-applied-configuration
- 适合多人 / GitOps / controller 协作

```bash
kubectl apply -f deploy.yaml --server-side=true --force-conflicts
```

| 维度 | Client-Side | Server-Side |
| ---- | ----------- | ----------- |
| 跟踪位置 | 客户端 annotation | apiserver managedFields |
| 字段冲突 | 后写覆盖 | 报错 / 必须 force |
| 多人协作 | 容易乱 | 多 owner 合并 |
| 控制器 | 不友好 | 友好 |
| 大对象性能 | 客户端 diff 慢 | 服务端 diff |

## 三、上下文管理

### 1. 原生方法

```bash
kubectl config use-context prod-admin
kubectl config set-context dev --cluster=dev --user=dev-user
kubectl config rename-context old new
kubectl config delete-context dev
kubectl config view --minify
```

### 2. kubectx / kubens

```bash
brew install kubectx   # macOS

kubectx                        # 列出所有 context
kubectx prod-admin             # 切换
kubectx -                       # 切回上一个
kubectx prod=prod-admin        # 重命名
kubectx <(kubectl config get-contexts --output name)
```

- 模糊匹配前缀
- `-i` 交互选择
- `kubens` 同样机制切换 namespace

```bash
kubens                              # 列出
kubens payments                     # 切换 namespace
kubens -                            # 退回上一个
```

### 3. kube-ps1 提示当前 context

```bash
# ~/.zshrc
source <(kubectl completion zsh)
PROMPT='$(kube_ps1)'$PROMPT
```

## 四、krew 插件管理器

`krew` 是 kubectl 插件的事实包管理器（类似 brew）。

```bash
# 安装
(
  set -x; cd "$(mktemp -d)" &&
  OS="$(uname | tr '[:upper:]' '[:lower:]')" &&
  ARCH="$(uname -m | sed -E 's/x86_64/amd64/;s/aarch64/arm64/')" &&
  curl -fsSLO "https://github.com/kubernetes-sigs/krew/releases/latest/download/krew-${OS}_${ARCH}.tar.gz" &&
  tar zxvf krew-${OS}_${ARCH}.tar.gz &&
  ./krew-"${OS}_${ARCH}" install krew
)
export PATH="${KREW_ROOT:-$HOME/.krew}/bin:$PATH"
```

```bash
kubectl krew search tail
kubectl krew install tail
kubectl krew list
kubectl krew upgrade
kubectl krew uninstall tail
```

插件安装位置：`~/.krew/bin`，会被加到 `$PATH` 前。

## 五、必备插件

### 1. stern — 多 Pod 聚合日志

```bash
kubectl krew install stern
```

```bash
stern payments-api -n payments --since 10m
stern -l app=payments --tail 50
stern . -n payments --container user  # 所有 Pod，加 -t 显示时间
stern . -n payments --output raw      # 原始 JSON
```

- 用 `--selector` 或 `-l` 过滤
- `--since` / `--tail` 控制时间
- 自动高亮 color / 错误
- 与 `kubectl logs -f` 的最大区别：自动跟随新增 Pod

### 2. kubecolor — 输出着色

```bash
kubectl krew install kubecolor
alias kubectl=kubecolor
```

- 自动识别 status / age / 资源类型着色
- 与原生命令完全兼容

### 3. view-secret / view-all — 还原 Secret

```bash
kubectl krew install view-secret
kubectl view-secret db-cred -n payments
```

- Secret 默认 base64，view-secret 直接还原明文
- view-all 同理可用于 ConfigMap / token

### 4. neat — 精简 YAML

```bash
kubectl krew install neat
kubectl get deploy api -n payments -o yaml | kubectl neat
```

- 去掉 status / managedFields / last-applied 等「噪音」
- 适合保存为模板 / diff

### 5. tree — 资源树

```bash
kubectl krew install tree
kubectl tree deploy api -n payments
```

- 展示 Deployment → ReplicaSet → Pod 层级
- 也支持 `kubectl tree svc`, `kubectl tree hpa`

### 6. node-shell — 节点调试

```bash
kubectl krew install node-shell
kubectl node-shell node-1
# 进入节点 nsenter，相当于 docker exec 进宿主机
```

- 比 SSH 方便，绕开 SSH 防火墙
- 适合排查 cgroup / 内核问题

### 7. ktop — 资源使用大盘

```bash
kubectl krew install ktop
kubectl ktop
```

- 类似 htop 的 K8s 版本
- 节点 / Pod 实时 CPU / 内存 / 网络
- Top 类似 `top` 但多节点聚合

### 8. popeye — 集群巡检

```bash
kubectl krew install popeye
kubectl popeye --context prod-admin
```

- 自动扫集群，给出可读报告
- 检查点：资源配额 / 健康探针 / 资源限制 / 镜像 tag / 安全等
- 输出 OK / WARN / ERROR 三档

### 9. kube-capacity — 节点容量分析

```bash
kubectl krew install kube-capacity
kubectl capacity       # 节点视角
kubectl capacity -p    # Pod 视角
kubectl capacity -u    # Utilization 视角
```

- 比 `kubectl describe node` 更直观
- 找剩余容量 / 找超用节点

### 10. resource-capacity

```bash
kubectl krew install resource-capacity
kubectl resource-capacity -n payments
```

- 类似 `kube-capacity` 但交互式 / 文本报表
- 支持 `--sort cpu` / `--sort memory`

### 11. trace / kubectl-debug — 临时进 Pod

```bash
kubectl krew install trace
kubectl trace podname -n payments
```

- 通过 Ephemeral Container 启动调试容器
- 不需要重启 Pod
- 见下节「kubectl debug 临时容器原理」

### 12. 其他常备

| 插件 | 用途 |
| ---- | ---- |
| `ctx` / `ns` | 简化上下文切换 |
| `images` | 列出镜像 / 标签 |
| `get-all` | 一键列出所有相关资源 |
| `whoami` / `who-can` | 当前 RBAC 权限 |
| `df-pv` | PV 容量 |
| `tail` | 通用 tail |
| `iexec` | 交互式 exec |
| `sniff` | 配合 wireshark 抓包 |

## 六、kubectl debug 临时容器原理

### 1. 为什么需要临时容器

- 镜像无 shell / 无 curl / 没有 nc 没法排查
- 不想改应用镜像
- 不想重启 Pod（影响流量）

### 2. Ephemeral Container 原理

```text
Pod 状态：Running（不可变）
  │
  ▼
APIServer: 增加 EphemeralContainer 到 spec.ephemeralContainers
  │
  ▼
kubelet: 启动该容器，复用 Pod namespace（network / pid 可选）
  │
  ▼
kubectl debug attach 到容器
```

特性：

- 不重启 Pod
- 与其他容器共享 network namespace（默认）
- 生命周期与 Pod 绑定，Pod 删除时一起消失
- K8s 1.16 alpha，1.23 beta，1.25 GA
- 需要 `ephemeralcontainers` 子资源授权

### 3. 用法

```bash
# 启动调试容器
kubectl debug -it pod/api-xxx -n payments \
  --image=nicolaka/netshoot \
  --target=api              # 与 api 容器共享 PID+net

# 仅共享网络
kubectl debug -it pod/api-xxx -n payments \
  --image=nicolaka/netshoot \
  --share-processes --copy-to=<new-name>

# 节点级调试
kubectl debug node/mynode -it --image=ubuntu
```

常见调试镜像：

- `nicolaka/netshoot`：网络排障工具合集（curl / nc / tcpdump / iperf）
- `docker:dind`：嵌套 Docker
- `alpine`：最简

### 4. 与 trace 插件对比

| 方式 | 优点 | 缺点 |
| ---- | ---- | ---- |
| `kubectl debug` | 原生 / 不装插件 | 镜像受限 / 复用 Pod ns |
| `kubectl trace` | 基于 BPFTrace / OpenLTrace | 部分版本限制 |
| `node-shell` | 节点级 | 不在 Pod 上下文 |

## 七、kubectl proxy 与 raw API 调用

### 1. kubectl proxy

```bash
kubectl proxy --port=8080 --address=0.0.0.0
```

启动后 `http://localhost:8080/api/v1/...` 可直接访问 K8s API，使用本地 kubeconfig 的证书与 token。

用途：

- 浏览器访问 K8s API
- 本地脚本调用
- 不暴露 apiserver 到外网

### 2. 直接用 curl

```bash
TOKEN=$(kubectl create token default)
APISERVER=$(kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}')
curl -k -H "Authorization: Bearer $TOKEN" \
  $APISERVER/api/v1/namespaces/payments/pods
```

### 3. 特殊端点

| 端点 | 用途 |
| ---- | ---- |
| `/api/v1/...` | 核心组 |
| `/apis/{group}/{version}/...` | 扩展组 |
| `/healthz` / `/readyz` | apiserver 健康 |
| `/metrics` | apiserver 指标 |
| `/version` | 版本 |
| `/logs` | apiserver 日志 |
| `/openapi/v2` | OpenAPI schema |
| `/livez` / `/etcd` | 扩展 health |

## 八、JSONPath / custom-columns / go-template 实战

### 1. JSONPath

```bash
# 所有 Pod 名
kubectl get pods -o jsonpath='{.items[*].metadata.name}'

# 节点 internalIP
kubectl get nodes -o jsonpath='{.items[*].status.addresses[?(@.type=="InternalIP")].address}'

# 容器镜像
kubectl get pods -A -o jsonpath='{range .items[*]}{.metadata.namespace}/{.metadata.name}{"\t"}{.spec.containers[*].image}{"\n"}{end}'
```

### 2. custom-columns

```bash
kubectl get pods -A -o custom-columns=\
NAMESPACE:.metadata.namespace,\
NAME:.metadata.name,\
IMAGE:.spec.containers[0].image,\
RESTARTS:.status.containerStatuses[0].restartCount,\
AGE:.metadata.creationTimestamp
```

### 3. go-template

```bash
kubectl get pods -n payments \
  -o go-template='{{range .items}}{{.metadata.name}} {{.status.phase}}{{"\n"}}{{end}}'
```

### 4. 实战场景

```bash
# 内存最大的 5 个 Pod
kubectl top pods -A --sort-by=memory | head -n 6

# 没设 resource limit 的 Deployment 名字
kubectl get deploy -A -o json | \
  jq -r '.items[] | select(.spec.template.spec.containers[] | .resources.limits == null) | .metadata.name'

# 所有 Service 的 ClusterIP
kubectl get svc -A -o jsonpath='{range .items[*]}{.metadata.namespace}/{.metadata.name} {.spec.clusterIP}{"\n"}{end}'
```

## 九、审计友好的 --dry-run=server

```bash
kubectl apply -f deploy.yaml --dry-run=server
kubectl apply -f deploy.yaml --dry-run=server -o yaml
```

- `--dry-run=client`：只做客户端校验，不发请求
- `--dry-run=server`：发到 apiserver 走 RBAC + 准入 + validation，但不入 etcd
- 适用：CI 中验证 manifest 能否被集群接受
- 配合 `-o yaml` 可拿到服务端裁剪后的最终 YAML

```bash
# 组合：CI 中 gate
kubectl apply -f - --dry-run=server <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
spec:
  replicas: 3
  selector:
    matchLabels: {app: api}
  template:
    metadata:
      labels: {app: api}
    spec:
      containers:
        - name: api
          image: my/api:1.0
          resources:
            requests: {cpu: "100m", memory: "128Mi"}
EOF
```

> 注意：`--dry-run=server` 仍可能触发 webhook（如 admission webhook），但不会持久化。

## 十、高频命令速查表

| 场景 | 命令 |
| ---- | ---- |
| 当前 context | `kubectl config current-context` |
| 切 namespace | `kubectl ns payments`（kubens） |
| 看事件 | `kubectl get events --sort-by=.lastTimestamp -A` |
| 看某 Pod 日志 | `kubectl logs -f pod/x -c c` |
| 多 Pod 日志 | `stern -l app=api` |
| 进 Pod | `kubectl exec -it pod/x -- bash` |
| 端口转发 | `kubectl port-forward svc/x 8080:80` |
| 拷贝 | `kubectl cp pod/x:/tmp/a ./a` |
| 临时容器 | `kubectl debug -it pod/x --image=nicolaka/netshoot` |
| 节点 shell | `kubectl node-shell node-1` |
| 资源 Top | `kubectl top node / kubectl top pod` |
| 容量分析 | `kubectl capacity` |
| 集群巡检 | `kubectl popeye` |
| RBAC 谁有 | `kubectl who-can create pods -n dev` |
| RBAC 我是谁 | `kubectl whoami` |
| 服务访问 | `kubectl port-forward svc/api 8080:80` |
| 集群诊断 | `kubectl get --raw='/healthz?verbose'` |
| 镜像列表 | `kubectl get pods -A -o jsonpath='{.items[*].spec.containers[*].image}' | tr ' ' '\n' | sort -u` |
| 检查 API 资源 | `kubectl api-resources` |
| 检查 API 版本 | `kubectl api-versions` |
| diff YAML | `kubectl diff -f deploy.yaml` |
| 字段裁剪 | `kubectl get pod x -o yaml \| kubectl neat` |
| 服务端 dry-run | `kubectl apply -f x.yaml --dry-run=server` |
| 替换为文件 | `kubectl replace -f x.yaml --force` |
| 标注 / 注解 | `kubectl annotate/label pod/x key=val` |
| 缩放 | `kubectl scale deploy api --replicas=5` |
| 滚动重启 | `kubectl rollout restart deploy api` |
| 回滚 | `kubectl rollout undo deploy api --to-revision=2` |
| 暂停恢复 | `kubectl rollout pause/resume deploy api` |
| 集群信息 | `kubectl cluster-info dump \| less` |
| 节点压力 | `kubectl get nodes -o yaml \| grep -A5 conditions` |
| 所有命名空间 | `kubectl get all -A` |
| 临时容器 | `kubectl debug pod/x -it --image=nicolaka/netshoot --target=api` |

## 十一、优缺点

### 优点

- 官方工具，永不过时，与 K8s 版本一同发布
- 覆盖面全：每一种资源、每个动作都有原生命令
- 插件生态成熟（krew 上百个插件）
- 与 RBAC / OIDC 完全对齐，权限可控
- 脚本化、可审计、可回放

### 缺点

- 输出格式原始，需要再加工（jq / jsonpath / go-template）
- 不擅长探索性查询（这时 Grafana / Dashboard 更强）
- 多人协作需要严格的 RBAC 与策略，否则容易误操作
- 集群多时 kubeconfig 维护成本高
- 部分高级用法（ephemeral container）依赖 K8s 版本

### 适用

- 日常运维 / 排查 / 排障（首选）
- CI / GitOps 中的 dry-run 校验
- 教学 / 培训

## 十二、最佳实践

- **kubeconfig 分层**：用 `KUBECONFIG=~/.kube/config:~/.kube/extra` 合并，避免一个文件动辄上千行
- **RBAC 收敛**：用 `kubectl auth can-i` / `who-can` 反复校验
- **服务端校验**：CI 跑 `--dry-run=server` + 准入 webhook
- **可读输出**：常用查询保存为 shell 函数 / Makefile target
- **日志聚合**：配合 stern / Loki / Grafana，告别 `kubectl logs`
- **临时调试**：用 ephemeral container 而非改业务镜像
- **自动补全**：
  ```bash
  # bash
  source <(kubectl completion bash)
  # zsh
  source <(kubectl completion zsh)
  ```
- **避免 `kubectl edit`**：尽量走 GitOps + apply，避免本地漂移
- **禁止 `kubectl delete --all`**：尤其在生产 namespace
- **客户端版本**：kubectl 与 apiserver 版本差异 ≤ 1 个 minor
- **保存 namespace**：用 kubens 或 `alias k=kubectl -n my-ns` 减少失误
- **大对象查询**：用 `kubectl get ... | jq` 而不是 `kubectl describe`
- **审计日志**：开启 apiserver audit log，kubectl 也可加 `--log-request` 排查
