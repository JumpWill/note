# kubectl 上下文原理与配置 (kubectl Context)

> 本章系统讲解 kubectl 的上下文（Context）原理、配置方法、多集群管理技巧及最佳实践。

## 一、为什么需要理解 kubectl 上下文

### 1.1 多集群时代背景

```text
现实场景：

  场景 1：同时管理多个 K8s 集群
    - 生产环境（prod）
    - 预发布环境（staging）
    - 测试环境（dev）
    - 多个云厂商的集群
    - 本地 K3s / kind 开发集群

  场景 2：多环境隔离
    - 不同 namespace 切换繁琐
    - 容易误操作在错误集群执行
    - 需要确认"我在哪个集群"

  场景 3：多用户协作
    - 开发者 vs 运维使用不同凭证
    - 临时借用其他账号
    - 多 SSO 账号管理
```

### 1.2 kubectl 上下文解决的问题

```text
kubectl context = 集群 + 用户 + namespace 的组合

解决问题：
  1. 快速切换集群（无需重新认证）
  2. 区分"我现在的环境"（避免误操作）
  3. 多账户管理（不同集群用不同账号）
  4. 团队共享配置（团队成员快速接入）
  5. 自动化脚本（明确目标环境）
```

---

## 二、Context 核心概念

### 2.1 三个核心对象

```text
kubectl context（上下文）= cluster + user + namespace

┌─────────────────────────────────────────────┐
│                Context（上下文）                │
│                                               │
│   ┌─────────┐  ┌─────────┐  ┌──────────┐     │
│   │ Cluster │  │   User  │  │Namespace │     │
│   │  集群   │  │  用户   │  │  命名空间 │     │
│   └─────────┘  └─────────┘  └──────────┘     │
│         ↓            ↓            ↓           │
│   API Server     认证信息      默认命名空间   │
│   地址与证书                  （如 default）  │
└─────────────────────────────────────────────┘
```

### 2.2 kubeconfig 文件

```text
kubectl 通过 kubeconfig 文件管理所有上下文：

  默认位置：~/.kube/config

  也可通过环境变量指定：
    KUBECONFIG=/path/to/config:/another/path

  多个文件可以合并：
    KUBECONFIG=~/.kube/config:~/.kube/prod-config

  优先级：
    1. --kubeconfig 命令行参数
    2. $KUBECONFIG 环境变量
    3. ~/.kube/config（默认）
```

### 2.3 Context 完整结构

```yaml
# ~/.kube/config 完整示例
apiVersion: v1
kind: Config
clusters:
- name: prod-cluster
  cluster:
    server: https://api.prod.example.com:6443
    certificate-authority-data: <base64-ca-cert>
- name: dev-cluster
  cluster:
    server: https://192.168.1.100:6443
    insecure-skip-tls-verify: true

users:
- name: prod-admin
  user:
    client-certificate-data: <base64-client-cert>
    client-key-data: <base64-client-key>
- name: dev-user
  user:
    username: admin
    password: <base64-password>

contexts:
- name: prod
  context:
    cluster: prod-cluster
    user: prod-admin
    namespace: production
- name: dev
  context:
    cluster: dev-cluster
    user: dev-user
    namespace: default

current-context: dev
```

---

## 三、Context 核心操作

### 3.1 查看 Context

```bash
# 查看所有 context
kubectl config get-contexts
# 输出：
# CURRENT   NAME      CLUSTER       AUTHINFO        NAMESPACE
# *         dev       dev-cluster   dev-user        default
#           prod      prod-cluster  prod-admin      production

# 查看当前 context
kubectl config current-context
# 输出：dev

# 查看当前详细配置
kubectl config view
# 输出当前生效的所有配置
```

### 3.2 切换 Context

```bash
# 切换到指定 context
kubectl config use-context prod
# 输出：Switched to context "prod"

# 验证
kubectl config current-context
# 输出：prod

# 列出所有 namespace（确认是 prod 集群）
kubectl get ns

# 直接执行命令（基于当前 context）
kubectl get pods
```

### 3.3 临时切换 Namespace

```bash
# 不切换 context，临时指定 namespace
kubectl get pods -n kube-system
kubectl get pods --namespace=kube-system

# 设置当前 context 的默认 namespace
kubectl config set-context --current --namespace=dev

# 验证
kubectl get ns

# 恢复
kubectl config set-context --current --namespace=default
```

### 3.4 创建 Context

```bash
# 一键创建 cluster + user + context
kubectl config set-cluster prod-cluster \
  --server=https://api.prod.example.com:6443 \
  --certificate-authority=/path/to/ca.crt

kubectl config set-credentials prod-admin \
  --client-certificate=/path/to/client.crt \
  --client-key=/path/to/client.key

kubectl config set-context prod \
  --cluster=prod-cluster \
  --user=prod-admin \
  --namespace=production

# 设置为默认
kubectl config use-context prod
```

### 3.5 简化配置（无需 CA 证书）

```bash
# 跳过 TLS 验证（仅测试环境）
kubectl config set-cluster dev-cluster \
  --server=https://192.168.1.100:6443 \
  --insecure-skip-tls-verify=true

# 使用 token 认证
kubectl config set-credentials dev-user \
  --token=eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...

# 使用账号密码
kubectl config set-credentials dev-user \
  --username=admin \
  --password=secret123
```

---

## 四、Context 高级特性

### 4.1 Context 重命名

```bash
# 重命名 context
kubectl config rename-context old-name new-name

# 重命名 cluster
kubectl config rename-cluster old-cluster new-cluster

# 重命名 user
kubectl config rename-user old-user new-user
```

### 4.2 删除 Context

```bash
# 删除 context（不会删除 cluster 和 user）
kubectl config delete-context dev

# 删除 cluster
kubectl config delete-cluster dev-cluster

# 删除 user
kubectl config delete-user dev-user
```

### 4.3 合并多个 kubeconfig

```bash
# 场景：合并多个配置
# 1. 单独的 prod config
cat ~/.kube/prod-config > /tmp/merged-config
# 2. 合并 dev config
KUBECONFIG=/tmp/merged-config:~/.kube/config kubectl config view --flatten > ~/.kube/config

# 3. 验证合并
kubectl config get-contexts
```

### 4.4 临时切换 Cluster（不修改配置）

```bash
# KUBECONFIG 环境变量指定临时配置
KUBECONFIG=/path/to/prod-config kubectl get nodes

# 或者临时修改 KUBECTL_FLAGS
kubectl --context=prod get pods

# 一次性命令使用指定 context
kubectl --context=dev get pods
kubectl --context=prod -n kube-system get pods
```

---

## 五、多集群管理实战

### 5.1 典型多集群配置

```yaml
# ~/.kube/config 完整多集群配置
apiVersion: v1
kind: Config
preferences: {}

clusters:
# 生产集群（AWS EKS）
- name: aws-prod
  cluster:
    server: https://api.prod-eks.aws.example.com
    certificate-authority-data: LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0t...

# 测试集群（阿里云 ACK）
- name: aliyun-staging
  cluster:
    server: https://api.staging-ack.aliyuncs.com:6443
    certificate-authority-data: LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0t...

# 本地 dev（k3s / kind）
- name: local-dev
  cluster:
    server: https://127.0.0.1:6443
    insecure-skip-tls-verify: true

users:
# 生产管理员
- name: prod-admin
  user:
    client-certificate-data: LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0t...
    client-key-data: LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0t...

# 测试开发者
- name: dev-user
  user:
    token: eyJhbGciOiJSUzI1NiIs...

# 本地 root
- name: local-admin
  user:
    username: admin
    password: admin123

contexts:
# 生产：使用 prod 集群，prod 用户，production namespace
- name: prod
  context:
    cluster: aws-prod
    user: prod-admin
    namespace: production

# 测试：使用 aliyun 集群，dev 用户，default namespace
- name: staging
  context:
    cluster: aliyun-staging
    user: dev-user
    namespace: default

# 本地：使用本地集群，local 用户，dev namespace
- name: dev
  context:
    cluster: local-dev
    user: local-admin
    namespace: dev

current-context: dev
```

### 5.2 快速切换场景

```bash
# 早上开发（本地）
kubectl config use-context dev
kubectl get pods

# 提交代码前（测试环境）
kubectl config use-context staging
kubectl apply -f deployment.yaml

# 部署到生产
kubectl config use-context prod
kubectl apply -f deployment.yaml

# 临时查看其他集群（不切换）
kubectl --context=prod get nodes
```

### 5.3 别名与脚本化

```bash
# 设置 shell 别名
alias k='kubectl'
alias kp='kubectl get pods'
alias kd='kubectl describe deployment'
alias kl='kubectl logs -f'
alias kgp='kubectl get pods -o wide'
alias kn='kubectl config set-context --current --namespace'

# 快速切换脚本
cat > ~/bin/k8s-switch <<'EOF'
#!/bin/bash
case $1 in
  prod|p)
    kubectl config use-context prod
    ;;
  staging|s)
    kubectl config use-context staging
    ;;
  dev|d)
    kubectl config use-context dev
    ;;
  *)
    echo "Usage: k8s-switch {prod|staging|dev}"
    ;;
esac
EOF
chmod +x ~/bin/k8s-switch

# 使用
k8s-switch prod
k8s-switch dev
```

---

## 六、Context 底层原理

### 6.1 Context 加载流程

```text
kubectl 启动时加载 context 的顺序：

┌──────────────────────────────────────┐
│  1. 命令行参数                        │
│     --context=xxx                     │
│     --cluster=xxx                     │
│     --kubeconfig=xxx                  │
└──────────────────┬───────────────────┘
                   ↓ 优先
┌──────────────────────────────────────┐
│  2. 环境变量                          │
│     KUBECONFIG                        │
│     KUBECTL_COMMAND_CONTEXT           │
└──────────────────┬───────────────────┘
                   ↓
┌──────────────────────────────────────┐
│  3. 默认路径                          │
│     ~/.kube/config                    │
│     $HOME/.kube/config                │
└──────────────────────────────────────┘

kubectl 启动后：
  1. 加载所有集群、用户、context
  2. 找到 current-context（或 default）
  3. 通过该 context 找到 cluster 和 user
  4. 用 user 凭证访问 cluster 的 API
  5. 后续 kubectl 命令基于这个 cluster + user
```

### 6.2 API 请求链

```text
kubectl get pods

  ↓
1. 读取当前 context
   cluster = dev-cluster
   user = dev-user
   namespace = default
   ↓
2. 加载 cluster 配置
   server = https://127.0.0.1:6443
   ca = /path/to/ca.crt
   ↓
3. 加载 user 凭证
   token = xxx
   ↓
4. 发送 HTTPS 请求
   GET https://127.0.0.1:6443/api/v1/namespaces/default/pods
   Authorization: Bearer xxx
   ↓
5. API Server 验证
   - 验证 token
   - 检查 RBAC
   ↓
6. 返回 Pod 列表
   ↓
7. kubectl 解析输出
```

### 6.3 凭证加密

```text
kubeconfig 中的敏感信息：
  - certificate-authority-data（CA 证书）
  - client-certificate-data（客户端证书）
  - client-key-data（客户端私钥）
  - token（Bearer token）
  - password（账号密码）

安全最佳实践：
  1. 文件权限：chmod 600 ~/.kube/config
  2. 使用 client-go 的 credential plugin：
     user:
       exec:
         command: aws-iam-authenticator
         apiVersion: client.authentication.k8s.io/v1beta1
  3. 使用 SSO 集成：
     OIDC、LDAP、SAML
  4. 使用 Vault 等 secret 管理
  5. 避免明文密码，使用 token
```

---

## 七、Context 高级实战

### 7.1 KUBECONFIG 多文件合并

```bash
# 场景：多个文件组合使用
# 1. 团队共享 config
cat > /etc/k8s/team-shared-config <<EOF
apiVersion: v1
kind: Config
clusters:
- name: shared-cluster
  cluster:
    server: https://shared.example.com
users:
- name: shared-user
  user:
    token: xxx
EOF

# 2. 个人 config
cat > ~/.kube/config <<EOF
apiVersion: v1
kind: Config
clusters:
- name: my-personal
  cluster:
    server: https://personal.example.com
users:
- name: me
  user:
    token: yyy
contexts:
- name: personal
  context: {cluster: my-personal, user: me}
current-context: personal
EOF

# 3. 使用多个文件（按顺序合并）
KUBECONFIG=~/.kube/config:/etc/k8s/team-shared-config

# 4. 第一个文件中的 context 优先级最高
kubectl config get-contexts

# 5. 临时只使用一个文件
KUBECONFIG=/etc/k8s/team-shared-config kubectl get pods
```

### 7.2 凭证管理最佳实践

```bash
# 1. AWS EKS（使用 aws-iam-authenticator）
cat > ~/.kube/config <<EOF
apiVersion: v1
kind: Config
clusters:
- name: aws-eks
  cluster:
    server: https://api.xxx.amazonaws.com
    certificate-authority-data: ...
users:
- name: aws-user
  user:
    exec:
      apiVersion: client.authentication.k8s.io/v1beta1
      command: aws-iam-authenticator
      args:
        - "token"
        - "-i"
        - "my-cluster"
      env:
        - name: AWS_PROFILE
          value: dev
contexts:
- name: aws
  context:
    cluster: aws-eks
    user: aws-user
EOF

# 2. OIDC（Keycloak / Okta / Auth0）
users:
- name: oidc-user
  user:
    auth-provider:
      name: oidc
      config:
        client-id: xxx
        client-secret: yyy
        id-token: zzz
        refresh-token: aaa
```

### 7.3 多 SSO 账号

```bash
# 场景：同一公司不同部门用不同 SSO
cat > ~/.kube/config <<EOF
apiVersion: v1
kind: Config
clusters:
- name: prod
  cluster:
    server: https://api.prod.com
- name: staging
  cluster:
    server: https://api.staging.com

users:
# 部门 A 的 SSO
- name: dept-a-user
  user:
    exec:
      command: aws-iam-authenticator
      args: ["token", "-i", "prod"]
      apiVersion: client.authentication.k8s.io/v1beta1

# 部门 B 的 SSO
- name: dept-b-user
  user:
    exec:
      command: gke-gcloud-auth-plugin
      apiVersion: client.authentication.k8s.io/v1beta1

contexts:
- name: prod-a
  context: {cluster: prod, user: dept-a-user}
- name: prod-b
  context: {cluster: prod, user: dept-b-user}
- name: staging-a
  context: {cluster: staging, user: dept-a-user}
EOF
```

---

## 八、Context 在自动化中的应用

### 8.1 CI/CD Pipeline

```yaml
# GitLab CI 示例
deploy-prod:
  stage: deploy
  script:
    # 使用生产 context
    - kubectl config use-context prod
    - kubectl apply -f deployment.yaml
    - kubectl rollout status deployment/app

deploy-staging:
  stage: deploy
  script:
    - kubectl config use-context staging
    - kubectl apply -f deployment.yaml
```

### 8.2 多集群 GitOps

```yaml
# ArgoCD ApplicationSet
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: multi-cluster
spec:
  generators:
  - list:
      items:
      - cluster: prod
        url: https://argocd-prod.example.com
      - cluster: staging
        url: https://argocd-staging.example.com
  template:
    metadata:
      name: '{{cluster}}-app'
    spec:
      project: default
      source:
        repoURL: https://github.com/myorg/app
        targetRevision: main
      destination:
        name: '{{cluster}}'
        server: '{{url}}'
```

### 8.3 K8s 内部应用使用 Context

```go
// K8s 应用内部使用 client-go 操作多个集群
package main

import (
    "k8s.io/client-go/kubernetes"
    "k8s.io/client-go/tools/clientcmd"
)

func main() {
    // 加载多个 context
    config, _ := clientcmd.NewNonInteractiveDeferredLoadingClientConfig(
        &clientcmd.ClientConfigLoadingRules{
            Precedence: []string{"/etc/k8s/config"},
        },
        &clientcmd.ConfigOverrides{
            CurrentContext: "prod",
        },
    )
    
    restConfig, _ := config.ClientConfig()
    clientset, _ := kubernetes.NewForConfig(restConfig)
    
    // 操作 prod 集群
    clientset.CoreV1().Pods("").List(...)
}
```

---

## 九、Context 最佳实践

### 9.1 命名规范

```text
context 命名建议：
  - 按环境：prod / staging / dev
  - 按集群：prod-east / prod-west
  - 按角色：prod-admin / prod-readonly
  - 避免无意义：ctx1 / default / test

cluster 命名建议：
  - 按云厂商：aws-prod / gcp-staging
  - 按地理位置：us-east-prod / eu-west-prod
  - 按功能：prod-k8s / dev-k3s

user 命名建议：
  - 按角色：admin / dev / readonly
  - 按 SSO：aws-sso / gcp-sso
  - 避免中文 / 特殊字符
```

### 9.2 安全最佳实践

```text
1. 文件权限
   - chmod 600 ~/.kube/config
   - 不要提交到 Git

2. 不使用明文密码
   - 改用 token / client-cert / SSO
   - 密码加密存储

3. 使用 exec 插件动态获取凭证
   - aws-iam-authenticator
   - gke-gcloud-auth-plugin
   - oidc-token 刷新

4. 区分不同环境的凭证
   - 生产与开发凭证隔离
   - 最小权限原则

5. 凭证轮换
   - 定期更新 token
   - 自动轮换证书

6. 审计
   - kubectl 配置审计日志
   - 记录 kubectl 操作
   - 集成到 SIEM
```

### 9.3 团队协作

```text
1. 共享 config
   - 通过内部平台管理
   - 加密分发
   - 版本控制（加密）

2. Context 命名约定
   - 团队达成一致
   - 文档化
   - 培训新人

3. 切换频繁的 context
   - 用 alias 简化
   - shell 脚本
   - IDE 插件（VSCode、IntelliJ）

4. 防止误操作
   - production 加颜色
   - 二次确认
   - dry-run 模式
```

### 9.4 性能与限制

```text
# 验证当前 context
PS1='[\u@\h \W $(kubectl config current-context 2>/dev/null)]\$ '

# 限制 context 列表
# 通过 RBAC 控制 context 访问
# 通过 IAM 控制 AWS EKS context 访问

# 性能影响
# kubectl 命令性能主要受：
# 1. API Server 响应速度
# 2. 网络延迟
# 3. 凭证解析（token vs cert）
# 4. Context 切换本身极快
```

---

## 十、Context 调试与排错

### 10.1 常用调试命令

```bash
# 查看完整配置
kubectl config view
# 或
kubectl config view --flatten --minify

# 查看特定字段
kubectl config view --raw -o jsonpath='{.clusters[0].cluster.server}'

# 测试连接
kubectl cluster-info

# 验证凭证
kubectl auth whoami

# 检查 RBAC 权限
kubectl auth can-i list pods
kubectl auth can-i create deployments

# 详细诊断
kubectl get events
kubectl describe pod
```

### 10.2 常见问题

```text
Q1: 切换 context 后报错 "couldn't get current server API group list"
A1: 检查：
    - cluster.server 是否正确
    - 网络是否能访问
    - 凭证是否有效
    - 防火墙 / 代理配置

Q2: token 过期
A2: 
    - AWS：aws-iam-authenticator 自动轮换
    - GCP：gke-gcloud-auth-plugin 自动轮换
    - 手动：kubectl config set-credentials --token=xxx

Q3: context 太多，分不清
A3:
    - 设置 PS1 显示当前 context
    - 使用 kubectl-tree 等工具
    - 使用 IDE 插件

Q4: 多个 config 文件冲突
A4:
    - KUBECONFIG 用 : 分隔
    - 第一个文件优先
    - 合并到单一文件
```

### 10.3 配置排错流程

```bash
# 1. 查看原始 config
kubectl config view --raw

# 2. 检查认证
kubectl auth whoami
# 输出：dev-user

# 3. 检查权限
kubectl auth can-i list pods --namespace=dev

# 4. 测试 API 连接
curl -k https://<api-server>/healthz

# 5. 详细日志
kubectl -v=8 get pods 2>/tmp/kubectl.log
tail -f /tmp/kubectl.log

# 6. 重置配置
rm -rf ~/.kube/config
# 重新初始化
aws eks update-kubeconfig --name <cluster>  # AWS
# 或
gcloud container clusters get-credentials <cluster>  # GCP
```

---

## 十一、Context 速记

### 三要素

```
context = cluster + user + namespace

cluster:  API Server 地址 + CA 证书
user:     认证信息（cert、token、exec）
namespace: 默认命名空间（如 default）
```

### 核心操作

```text
查看：kubectl config get-contexts / view / current-context
切换：kubectl config use-context <name>
创建：kubectl config set-cluster/set-credentials/set-context
删除：kubectl config delete-cluster/user/context
重命名：kubectl config rename-cluster/user/context
设置：kubectl config set-context --current --namespace=xxx
```

### 文件位置

```text
~/.kube/config（默认）
KUBECONFIG 环境变量
--kubeconfig 命令行参数
KUBECTL_COMMAND_CONTEXT 环境变量
--context 命令行参数
优先级：命令行 > 环境变量 > 默认文件
```

### 调试命令

```bash
kubectl config view
kubectl config get-contexts
kubectl config current-context
kubectl auth whoami
kubectl auth can-i list pods
kubectl cluster-info
kubectl get events
```

### 一句话总结

```
kubectl context = 集群 + 用户 + 命名空间
作用：避免误操作，简化多集群切换
文件：~/.kube/config（YAML 格式）
切换：kubectl config use-context <name>
最佳实践：chmod 600 + 用 SSO + 凭证 exec 插件
```

---

## 十二、参考资源

```text
- K8s 官方文档：https://kubernetes.io/docs/concepts/configuration/organize-cluster-access-kubeconfig/
- kubectl config 参考：https://kubernetes.io/docs/reference/generated/kubectl/kubectl-commands#config
- clientcmd 源码：https://github.com/kubernetes/client-go/tree/master/tools/clientcmd
- AWS IAM 集成：https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html
- GKE 认证：https://cloud.google.com/kubernetes-engine/docs/concepts/authentication
- kubectx 工具：https://github.com/ahmetb/kubectx
- kube-ps1 工具：https://github.com/jonmosco/kube-ps1
```

## 速记卡

- **Context** = cluster + user + namespace
- **配置文件**：~/.kube/config（YAML 格式）
- **多文件**：KUBECONFIG=file1:file2:file3
- **创建**：`set-cluster` + `set-credentials` + `set-context`
- **切换**：`use-context` 或 `--context=`
- **凭证**：`client-cert`、`token`、`exec` 插件
- **凭证插件**：aws-iam-authenticator、gke-gcloud-auth-plugin、OIDC
- **安全**：chmod 600、不明文密码、SSO、最小权限
- **调试**：`view`、`auth whoami`、`auth can-i`
- **便利工具**：kubectx、kube-ps1、shell alias
- **多集群**：`KUBECONFIG` 多文件、`use-context`
- **GitOps**：ArgoCD ApplicationSet 多集群
- **CI/CD**：`use-context` + `apply`