# Helm 包管理 (Helm Package Manager)

> 本章系统讲解 Helm:K8s 的事实标准包管理工具,Chart、Release、Template、Values 等核心概念与实战。

## 一、Helm 概述

### 1.1 什么是 Helm

**Helm** 是 K8s 的包管理器,类似 apt/yum/homebrew。

```text
Helm 三大概念:
1. Chart     - 应用包,描述 K8s 资源
2. Release   - Chart 的运行实例
3. Repository - Chart 仓库 (类似 apt 源)

Helm 解决:
1. 模板化 K8s 资源
2. 版本管理
3. 一键部署/升级/回滚
4. 多环境复用 (dev/test/prod)
```

### 1.2 Helm vs kubectl apply

```text
kubectl apply -f xxx.yaml:
  - 直接应用 YAML
  - 不支持模板化
  - 不支持版本管理
  - 不支持参数化

Helm:
  - 模板化 (Go template)
  - 参数化 (values.yaml)
  - 版本管理 (Release)
  - 一键升级/回滚
```

### 1.3 Helm 版本

```text
Helm v3 (当前主流):
- 移除 Tiller (v2 有,客户端服务端架构)
- 直接使用 kubeconfig
- 三方仓库 (无中心仓库)
- Chart 格式变化

当前最新: v3.14+
```

---

## 二、Helm 安装

### 2.1 安装客户端

```bash
# macOS
brew install helm

# Linux
curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3
chmod 700 get_helm.sh
./get_helm.sh

# 验证
helm version
```

### 2.2 常用命令速查

```bash
# 仓库管理
helm repo add <repo-name> <url>
helm repo list
helm repo update
helm repo remove <repo-name>
helm search repo <keyword>      # 搜索远程仓库
helm search hub <keyword>       # 搜索 Artifact Hub

# Chart 操作
helm pull <chart>               # 下载 Chart (不安装)
helm show values <chart>        # 查看默认 values
helm show all <chart>           # 查看完整信息
helm template <release> <chart> # 渲染模板 (不安装)

# Release 管理
helm install <release> <chart>           # 安装
helm upgrade <release> <chart>           # 升级
helm uninstall <release>                 # 卸载
helm list                                  # 列出所有 Release
helm status <release>                     # 查看状态
helm history <release>                    # 历史版本
helm rollback <release> <revision>        # 回滚

# 渲染与调试
helm template my-release bitnami/nginx     # 渲染模板输出
helm install --dry-run --debug my-release bitnami/nginx  # 模拟安装

# 插件管理
helm plugin install <url>
helm plugin list
```

---

## 三、Chart 结构

### 3.1 标准目录结构

```text
mychart/
├── Chart.yaml          # Chart 元数据 (必需)
├── values.yaml         # 默认配置值
├── charts/             # 依赖的子 Chart
├── templates/          # K8s 资源模板 (核心)
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── ingress.yaml
│   ├── configmap.yaml
│   ├── secret.yaml
│   ├── pvc.yaml
│   ├── serviceaccount.yaml
│   ├── hpa.yaml
│   ├── _helpers.tpl    # 模板辅助函数
│   └── NOTES.txt       # 安装后说明
├── LICENSE             # 许可证 (可选)
├── README.md           # 说明 (可选)
└── .helmignore         # 打包时排除的文件
```

### 3.2 Chart.yaml

```yaml
apiVersion: v2                    # Helm 3+
name: my-app                      # Chart 名 (必填)
version: 1.0.0                    # Chart 版本 (必填,SemVer)
appVersion: "2.1.0"               # 应用版本 (必填,任意)
description: A Helm chart for my application  # 描述
type: application                  # application / library
home: https://example.com
sources:
  - https://github.com/myorg/myapp
keywords:
  - web
  - nginx
maintainers:
  - name: Alice
    email: alice@example.com
icon: https://example.com/icon.png

dependencies:
  - name: postgresql
    version: 12.1.0
    repository: https://charts.bitnami.com/bitnami
    condition: postgresql.enabled
```

### 3.3 values.yaml (默认配置)

```yaml
# 默认配置 - 安装时可不指定,使用默认值
replicaCount: 1

image:
  repository: nginx
  tag: "1.25"
  pullPolicy: IfNotPresent

imagePullSecrets: []

service:
  type: ClusterIP
  port: 80

ingress:
  enabled: false
  className: ""
  annotations: {}
  hosts:
    - host: chart-example.local
      paths:
        - path: /
          pathType: Prefix

resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    cpu: 500m
    memory: 256Mi

autoscaling:
  enabled: false
  minReplicas: 1
  maxReplicas: 10
  targetCPUUtilizationPercentage: 80

nodeSelector: {}
tolerations: []
affinity: {}
```

### 3.4 templates/deployment.yaml (模板)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "my-app.fullname" . }}
  labels:
    {{- include "my-app.labels" . | nindent 4 }}
spec:
  {{- if not .Values.autoscaling.enabled }}
  replicas: {{ .Values.replicaCount }}
  {{- end }}
  selector:
    matchLabels:
      {{- include "my-app.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      labels:
        {{- include "my-app.selectorLabels" . | nindent 8 }}
    spec:
      {{- with .Values.imagePullSecrets }}
      imagePullSecrets:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      serviceAccountName: {{ include "my-app.serviceAccountName" . }}
      containers:
      - name: {{ .Chart.Name }}
        image: "{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}"
        imagePullPolicy: {{ .Values.image.pullPolicy }}
        ports:
        - name: http
          containerPort: 80
          protocol: TCP
        livenessProbe:
          httpGet:
            path: /
            port: http
        readinessProbe:
          httpGet:
            path: /
            port: http
        resources:
          {{- toYaml .Values.resources | nindent 10 }}
```

### 3.5 templates/_helpers.tpl

```yaml
{{/*
Expand the name of the chart.
*/}}
{{- define "my-app.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "my-app.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Common labels
*/}}
{{- define "my-app.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{ include "my-app.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{/*
Selector labels
*/}}
{{- define "my-app.selectorLabels" -}}
app.kubernetes.io/name: {{ include "my-app.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
```

---

## 四、模板语法

### 4.1 变量引用

```yaml
# 引用值
{{ .Values.replicaCount }}

# 引用 Chart 信息
{{ .Chart.Name }}
{{ .Chart.Version }}
{{ .Chart.AppVersion }}

# 引用 Release 信息
{{ .Release.Name }}
{{ .Release.Namespace }}
{{ .Release.Service }}
{{ .Release.IsInstall }}
{{ .Release.IsUpgrade }}
{{ .Release.Revision }}
```

### 4.2 流程控制

```yaml
# if/else
{{- if .Values.ingress.enabled }}
apiVersion: networking.k8s.io/v1
kind: Ingress
...
{{- end }}

# with (设置上下文)
{{- with .Values.service }}
type: {{ .type }}
port: {{ .port }}
{{- end }}

# range (循环)
{{- range .Values.hosts }}
- host: {{ .host }}
  paths:
  - path: /
    pathType: Prefix
{{- end }}
```

### 4.3 函数与管道

```yaml
# 字符串
{{ .Values.name | quote }}             # "myapp"
{{ .Values.name | upper }}            # MYAPP
{{ .Values.name | default "default" }} # 若空,使用默认值
{{ .Values.name | trunc 10 }}         # 截断到 10 字符

# toYaml (对象转 YAML)
{{- toYaml .Values.resources | nindent 10 }}

# nindent (新行 + 缩进)
{{ include "my-app.labels" . | nindent 4 }}
```

### 4.4 命名模板 (define)

```yaml
# templates/_helpers.tpl
{{- define "my-app.labels" }}
app: my-app
env: {{ .Values.env | default "dev" }}
{{- end }}

# 使用
metadata:
  labels:
    {{- include "my-app.labels" . | nindent 4 }}
```

---

## 五、Release 管理

### 5.1 安装

```bash
# 基本安装
helm install my-release ./mychart

# 指定 values 文件
helm install my-release ./mychart -f values-prod.yaml

# 命令行覆盖 values
helm install my-release ./mychart \
  --set replicaCount=3 \
  --set image.tag=1.26

# 指定 namespace
helm install my-release ./mychart -n production --create-namespace

# 模拟安装 (不实际执行)
helm install my-release ./mychart --dry-run

# 生成 YAML (不实际部署)
helm install my-release ./mychart --dry-run --debug > manifest.yaml
```

### 5.2 查看

```bash
# 列出所有 Release
helm list
helm list -A                     # 所有命名空间
helm list --namespace production

# 查看详情
helm status my-release
helm history my-release
helm get all my-release           # 获取所有 manifest
helm get manifest my-release      # 获取 K8s manifest
helm get values my-release        # 获取实际应用的 values
```

### 5.3 升级

```bash
# 升级 (用新 values)
helm upgrade my-release ./mychart -f new-values.yaml

# 强制覆盖 (用于更新已有 release)
helm upgrade my-release ./mychart -f new-values.yaml --reuse-values

# 升级并重新创建 (失败则回滚)
helm upgrade my-release ./mychart --atomic

# 升级并清理历史 (只保留最近 5 个版本)
helm upgrade my-release ./mychart --history-max 5

# 仅在 release 存在时升级 (不存在则跳过)
helm upgrade my-release ./mychart --install
```

### 5.4 回滚

```bash
# 查看历史
helm history my-release
# REVISION  STATUS     CHART         DESCRIPTION
# 1         superseded my-app-1.0.0  Install complete
# 2         deployed   my-app-1.0.0  Upgrade complete
# 3         superseded my-app-1.0.0  Upgrade complete
# 4         deployed   my-app-1.0.0  Upgrade complete

# 回滚到指定版本
helm rollback my-release 2

# 回滚时清理资源 (默认)
helm rollback my-release 2 --cleanup-on-fail
```

### 5.5 卸载

```bash
helm uninstall my-release

# 保留历史
helm uninstall my-release --keep-history
```

---

## 六、Chart 开发

### 6.1 创建 Chart

```bash
helm create mychart
```

生成结构:

```text
mychart/
├── .helmignore
├── Chart.yaml
├── values.yaml
├── charts/
└── templates/
    ├── _helpers.tpl
    ├── deployment.yaml
    ├── hpa.yaml
    ├── ingress.yaml
    ├── NOTES.txt
    ├── service.yaml
    ├── serviceaccount.yaml
    └── tests/
        └── test-connection.yaml
```

### 6.2 渲染模板 (调试)

```bash
# 渲染并输出
helm template my-release ./mychart

# 渲染指定 values
helm template my-release ./mychart -f values-prod.yaml

# 查看渲染结果中的某个资源
helm template my-release ./mychart | kubectl apply --dry-run=client -f -

# 验证 Chart 语法
helm lint ./mychart
```

### 6.3 Chart 依赖管理

```yaml
# Chart.yaml
dependencies:
- name: postgresql
  version: 12.1.0
  repository: https://charts.bitnami.com/bitnami
  condition: postgresql.enabled    # 启用条件
  alias: db                        # 别名 (用 .Values.db.xxx)
```

```bash
# 更新依赖
helm dependency update ./mychart

# 列出依赖
helm dependency list ./mychart
```

### 6.4 Chart Hooks

```yaml
# templates/pre-install-job.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: "{{ include "my-app.fullname" . }}-pre-install"
  annotations:
    "helm.sh/hook": pre-install      # 钩子类型
    "helm.sh/hook-weight": "1"        # 执行顺序
spec:
  template:
    spec:
      restartPolicy: Never
      containers:
      - name: pre-install
        image: busybox
        command: ['sh', '-c', 'echo Pre-install hook']
```

支持的 hook 类型:
- pre-install     - 安装前
- post-install    - 安装后
- pre-delete      - 删除前
- post-delete     - 删除后
- pre-upgrade     - 升级前
- post-upgrade    - 升级后
- pre-rollback    - 回滚前
- post-rollback   - 回滚后
- test            - helm test 执行

---

## 七、Chart 仓库

### 7.1 公共仓库

```bash
# 添加主流仓库
helm repo add stable https://charts.helm.sh/stable
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo add bitnami https://charts.bitnami.com/bitnami

# 更新
helm repo update

# 搜索
helm search repo nginx
helm search hub nginx
```

### 7.2 私有仓库 (ChartMuseum / Harbor / OCI)

```bash
# 添加 OCI 仓库 (Helm 3+)
helm registry login registry.example.com -u admin

# 添加普通 HTTP 仓库
helm repo add myrepo https://charts.example.com

# 添加 ChartMuseum
helm repo add chartmuseum http://chartmuseum.local

# 推送 Chart 到 OCI Registry
helm push mychart-1.0.0.tgz oci://registry.example.com/charts

# 推送 Chart 到 ChartMuseum
curl --data-binary "@mychart-1.0.0.tgz" http://chartmuseum/api/charts
```

### 7.3 OCI Registry (推荐)

```text
Helm 3.7+ 原生支持 OCI (Open Container Initiative)

优势:
- 复用 Docker Registry 基础设施 (Harbor, ECR, ACR)
- 无需单独部署 ChartMuseum
- 统一的镜像和 Chart 管理

例:
  Harbor (含 OCI):
    - 推送 Helm Chart 到 harbor.example.com/library/mychart
    - 推送 Docker 镜像到同一仓库
```

---

## 八、Helm 实战

### 8.1 多环境部署

```bash
# dev 环境
helm install my-app ./mychart \
  -n dev \
  -f values-dev.yaml \
  --set replicaCount=1

# staging 环境
helm install my-app ./mychart \
  -n staging \
  -f values-staging.yaml \
  --set replicaCount=2

# prod 环境
helm install my-app ./mychart \
  -n prod \
  -f values-prod.yaml \
  --set replicaCount=5
```

### 8.2 Helm + CI/CD

```yaml
# .gitlab-ci.yml 示例
deploy_prod:
  stage: deploy
  script:
    - helm repo add myrepo https://charts.example.com
    - helm repo update
    - helm upgrade my-app myrepo/my-app
        --version ${CI_COMMIT_TAG}
        -n production
        -f values-prod.yaml
        --atomic
        --wait
```

### 8.3 Helmfile (Helm 编排工具)

```yaml
# helmfile.yaml
repositories:
- name: stable
  url: https://charts.helm.sh/stable
- name: bitnami
  url: https://charts.bitnami.com/bitnami

releases:
- name: prometheus
  namespace: monitoring
  chart: prometheus-community/prometheus
  version: 25.0.0
  values:
  - values/prometheus.yaml

- name: grafana
  namespace: monitoring
  chart: grafana/grafana
  version: 6.50.0
  values:
  - values/grafana.yaml
```

```bash
# 部署所有
helmfile apply

# 同步到目标版本
helmfile sync
```

### 8.4 Helm test

```yaml
# templates/tests/test-connection.yaml
apiVersion: v1
kind: Pod
metadata:
  name: "{{ include "my-app.fullname" . }}-test-connection"
  labels:
    {{- include "my-app.labels" . | nindent 4 }}
  annotations:
    "helm.sh/hook": test
spec:
  containers:
  - name: wget
    image: busybox
    command: ['wget']
    args: ['{{ include "my-app.fullname" . }}:{{ .Values.service.port }}']
  restartPolicy: Never
```

```bash
# 执行测试
helm test my-release

# 清理测试 Pod
helm test my-release --cleanup
```

---

## 九、Helm 最佳实践

### 9.1 Chart 开发

```text
1. Chart 命名规范: <product>-<purpose> (如 nginx-ingress)
2. 版本管理: SemVer (主.次.补丁)
3. appVersion 与 version 区分:
   - version: Chart 自身版本
   - appVersion: 应用版本
4. values 必须有合理默认值
5. README.md 必填
6. _helpers.tpl 提取通用模板片段
```

### 9.2 安全

```text
1. Secrets 不要硬编码到 values.yaml
2. 用外部密钥管理 (External Secrets)
3. 限制 Chart 仓库访问权限
4. Helm 3.x 不需要 Tiller,安全性更好
5. 使用 --atomic 确保升级失败回滚
```

### 9.3 CI/CD 集成

```text
- 使用 Helmfile / ArgoCD / Flux 管理多环境
- GitOps: Chart 在 Git,部署自动同步
- Chart 版本与 Git tag 对应
- helm diff 查看变更
- helm test 部署后验证
```

---

## 核心要点速记

### Helm 三大概念

```text
Chart     - 包 (类似 rpm/deb)
Release   - Chart 的运行实例
Repository - 包仓库
```

### Chart 结构

```text
Chart.yaml      - 元数据
values.yaml     - 默认配置
templates/      - K8s 模板
charts/         - 子 Chart 依赖
_helpers.tpl    - 模板辅助
```

### 模板语法

```yaml
{{ .Values.xxx }}          # 引用值
{{ if .Values.enabled }} {{ end }}  # 条件
{{ range .Values.list }} {{ end }}  # 循环
{{ include "name" . }}    # 引入模板
{{- toYaml . | nindent 4 }} # YAML 格式化
```

### Release 管理

```bash
helm install      # 安装
helm upgrade      # 升级
helm rollback     # 回滚
helm uninstall    # 卸载
helm list         # 列表
helm history      # 历史
```

### 关键特性

```text
- Helm 3+ 无 Tiller,直接用 kubeconfig
- OCI Registry 支持 (Harbor/ECR/ACR)
- Hook 机制 (pre-install/post-upgrade 等)
- 多环境管理 (values 文件)
- 模板 + 参数化
```

### 实战速记

```bash
# 安装
helm install my-app ./chart -n prod -f values.yaml

# 升级 (原子性)
helm upgrade my-app ./chart -f new-values.yaml --atomic

# 回滚
helm rollback my-app 2

# 渲染不部署 (调试)
helm template my-app ./chart > manifest.yaml
```

---

## 参考

- **Helm 官方文档**: https://helm.sh/docs/
- **Chart 模板指南**: https://helm.sh/docs/chart_template_guide/
- **Chart 最佳实践**: https://helm.sh/docs/chart_best_practices/
- **Artifact Hub**: https://artifacthub.io/
- **Helmfile**: https://github.com/helmfile/helmfile
