# KubeSphere

国产全栈容器平台，青云 QingCloud 开源，面向企业级多租户场景。在一个 K8s 之上提供 DevOps / 可观测 / 服务网格 / 应用商店 / 多集群联邦等完整能力，国内政企与金融行业使用广泛。

## 一、定位与特性

- "K8s 之上的全栈平台"：装在一个 K8s 上，提供 DevOps、可观测、Service Mesh、应用商店、边缘计算等
- 多租户：企业空间（Workspace）→ 项目（Project）→ K8s Namespace
- 可插拔组件：`enabledComponents` 按需开启，避免一刀切资源开销
- 安装器：ks-installer（已有 K8s 上安装）或 KubeKey（一站式部署 K8s + KubeSphere）
- 与国产化栈兼容较好（信创、ARM、国产数据库）
- 4.0 起架构代号 "LuBan"，把核心与扩展解耦

## 二、架构

```text
┌─────────────────────────────────────────────────────────────┐
│                    K8s Cluster（已有 / KubeKey 创建）         │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                ks-installer（Job 一次性安装）           │  │
│  └───────────────────────────────────────────────────────┘  │
│  ┌──────────────┐ ┌──────────────┐ ┌─────────────────────┐  │
│  │ ks-apiserver │ │  ks-console  │ │ ks-controller-manager│ │
│  │ （CRD + API）│ │   （UI）      │ │ （控制器 + webhook）   │ │
│  └──────────────┘ └──────────────┘ └─────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         可插拔组件（enabledComponents 控制）            │  │
│  │  - whizard-monitoring   - whizard-logging             │   │
│  │  - devops（Jenkins/Argo）  - istio                    │   │
│  │  - openpitrix（应用商店）  - kubeedge（边缘）          │   │
│  │  - events / audit / alerting                          │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

- **ks-apiserver**：聚合 K8s API + KubeSphere 自定义资源
- **ks-console**：前端 UI（基于 React）
- **ks-controller-manager**：所有 KubeSphere CRD 的控制器
- **ks-installer**：通过 Job 一次性渲染并 apply 所有 manifest，安装器
- **ClusterConfiguration CR**：ks-installer 读取此 CR 决定启用哪些组件

## 三、核心 CRD 与多租户模型

### 1. 三层多租户

```text
Workspace（企业空间）
  └── Project（项目，对应 K8s Namespace）
        └── Namespace（标准 K8s 命名空间，可与 Project 一一对应或一对多）
```

| KubeSphere 概念 | 对应 K8s 资源 | 备注 |
| ---------------- | ------------- | ---- |
| Workspace | 无对应原生对象 | 顶层隔离 |
| Project | 一个或多个 Namespace | 项目管理员管理 |
| Namespace | K8s 原生 | 实际负载运行空间 |
| ClusterRoleBinding | K8s 原生 | RBAC 展开目标 |

### 2. 角色

| 角色 | 范围 |
| ---- | ---- |
| platform-admin | 平台管理员（cluster-admin 级别） |
| platform-regular | 平台普通用户 |
| platform-view | 只读 |
| workspace-admin | 企业空间管理员 |
| workspace-regular | 企业空间普通用户 |
| workspace-view | 企业空间只读 |
| project-admin / project-regular / project-view | 项目级别 |

### 3. ClusterConfiguration CR 示例

```yaml
apiVersion: installer.kubesphere.io/v1alpha1
kind: ClusterConfiguration
metadata:
  name: ks-installer
  namespace: kubesphere-system
spec:
  persistence:
    storageClassName: local
    mysql:
      host: 192.168.0.2
      port: 3306
      rootPassword: "******"
  authentication:
    jwtSecret: "******"
  local_registry: dockerhub.kubesphere.local
  devops:
    enabled: true
    jenkinsMemoryLim: 4Gi
    jenkinsMemoryReq: 2Gi
    jenkinsVolumeSize: 20Gi
    sonarqube:
      enabled: false
  monitoring:
    prometheusMemoryLim: 8Gi
    prometheusMemoryReq: 2Gi
  logging:
    enabled: true
    logsidecarMemoryLim: 1Gi
    logsidecarMemoryReq: 100Mi
    elasticsearchMemoryLim: 8Gi
    elasticsearchMemoryReq: 4Gi
    elasticsearchVolumeSize: 20Gi
  openpitrix:
    enabled: true
  servicemesh:
    enabled: true
    istioVersion: v1.18.0
  events:
    enabled: true
    ruler:
      enabled: true
  alerting:
    enabled: true
    notificationManager:
      enabled: true
  auditing:
    enabled: true
  multicluster:
    enabled: true
  kubeedge:
    enabled: false
  network:
    networkpolicy:
      enabled: true
    ippool:
      type: calico
  metrics_server:
    enabled: true
```

修改 `spec` 后 ks-installer 会重新执行 apply，重新渲染。

## 四、可插拔组件详解

### 1. DevOps（基于 Jenkins + Argo CD）

- Jenkins 跑在集群内（devops-jenkins）
- 内置 Pipeline / 凭证管理 / S2I / Binary-to-Image（B2I）
- 可选 Argo CD 做应用同步（启用 `devops.argoCd.enabled`）
- 流水线状态、构建产物直接在 UI 展示

### 2. 可观测（Monitoring + Logging + Events + Auditing）

| 子模块 | 后端 | 来源 |
| ------ | ---- | ---- |
| Monitoring | Prometheus + Thanos | 自研 whizard-monitoring |
| Logging | Fluent Bit + Elasticsearch | 自研 whizard-logging |
| Events | K8s Events + 自研 | events.kubesphere.io |
| Auditing | kube-apiserver audit log + 自研 | auditing.kubesphere.io |
| Alerting | notification-manager | KubeSphere 自研 |

- Monitoring v2 起基于 Prometheus Operator
- Logging 4.x 起支持 Loki 后端（whizard-logging-loki）

### 3. Service Mesh（基于 Istio）

- 启用后自动注入 sidecar
- UI 提供流量拓扑、灰度发布（蓝绿/金丝雀）、熔断、流量镜像
- 内置 Bookinfo 等示例

### 4. 应用商店（基于 OpenPitrix）

- 内置应用模板（Helm chart）
- 用户可一键部署到任意项目
- 4.x 起逐步被 KubeSphere App Store 替代

### 5. 边缘计算（基于 KubeEdge）

- 启用 `kubeedge` 组件
- 边缘节点通过 CloudCore / EdgeCore 接入
- 适合 IoT / 工厂 / 边缘门店

### 6. 多集群联邦（Cluster Federation）

- 主集群纳管其他集群
- 集群成员关系存储在 `cluster.kubesphere.io/v1alpha1 Cluster` CR
- Federation v2 CR（已弃用，转向 Karmada 内置方案）

## 五、安装

### 1. ks-installer 在已有 K8s 上

```bash
# 前置：K8s ≥ 1.20，default StorageClass
kubectl apply -f https://github.com/kubesphere/ks-installer/releases/download/v3.4.1/kubesphere-installer.yaml
kubectl apply -f https://github.com/kubesphere/ks-installer/releases/download/v3.4.1/cluster-configuration.yaml

# 查看安装日志
kubectl logs -n kubesphere-system $(kubectl get pod -n kubesphere-system -l app=ks-installer -o jsonpath='{.items[0].metadata.name}') -f
```

### 2. KubeKey 一体化（推荐生产）

```bash
# 下载 KubeKey
curl -sfL https://get-kk.kubesphere.io | VERSION=v3.1.2 sh -

# 创建集群配置
./kk create config --with-kubesphere v3.4.1

# 编辑 config-sample.yaml，填节点 + ks 组件
# 执行安装
./kk create cluster -f config-sample.yaml
```

KubeKey 同时支持：

- 创建 K8s（kubeadm / K3s）
- 安装 KubeSphere
- 添加 / 删除节点
- 升级集群

### 3. Air-Gap 离线安装

- KubeKey 支持指定私有镜像仓库
- 提前导入镜像到内网 Harbor / registry
- 离线包下载：`https://download.kubesphere.io`

## 六、v4 LuBan 架构变化

v4.0 起代号 **LuBan**，主要变化：

- 前后端完全分离：前端 React SPA，后端通过 OpenAPI 网关
- 核心精简：ks-core 仅包含认证、租户、集群纳管等基础能力
- 扩展机制：Extension（前端 + 后端），第三方可插拔贡献功能
- 监控、日志等组件从核心拆出为独立扩展
- 安装模型简化，ClusterConfiguration 字段收敛

```text
v3.4                                    v4.x LuBan
─────────                              ──────────
ks-apiserver                           ks-core（精简）
  ├─ all components built-in             ├─ auth / tenant / cluster mgmt
  ├─ one big CR list                     └─ Extension framework
  └─ single install                       ├─ whizard-monitoring (extension)
                                          ├─ whizard-logging (extension)
                                          └─ ... 第三方扩展
```

迁移：v3 → v4 需要走 ks-installer 升级路径，注意 ClusterConfiguration 字段变化。

## 七、与 Rancher 对比

| 维度 | KubeSphere | Rancher |
| ---- | ---------- | ------- |
| 国产生态 | 强（中文文档、信创） | 一般 |
| 多集群 | 联邦模型，主从概念 | API 代理 + import，无主从 |
| 多租户 | Workspace / Project / Namespace | Global / Cluster / Project / NS |
| DevOps | 内置 Jenkins / Argo | 无原生 DevOps，需外部 |
| 应用商店 | OpenPitrix | Apps & Marketplace |
| 监控 | Prometheus + 自研扩展 | Prometheus Operator + Rancher Monitoring |
| 安装 | ks-installer / KubeKey | Helm（已有 K8s）/ RKE2（自建） |
| 商业版 | KubeSphere 企业版（SUSE 接管后有商业） | Rancher Prime |

适用差异：

- 多集群 DevOps 一体化 → KubeSphere
- 多云多集群纳管（异构 K8s） → Rancher

## 八、优缺点

### 优点

- 功能丰富：DevOps + Mesh + Store + Edge + 监控日志完整
- 中文文档 + 国内社区活跃
- 国产化栈适配好（信创 OS、ARM、达梦、人大金仓等）
- KubeKey 一站式：装 K8s + 装平台一次性搞定
- UI 设计在国内同类产品中较为成熟

### 缺点

- 组件全开后资源占用较大（默认推荐至少 8C16G）
- ks-installer 升级偶尔出现组件状态不一致
- 4.x 架构变化较大，第三方文档适配滞后
- 大规模多集群联邦（数百集群）支持不及 Rancher
- 部分高级功能（Service Mesh 高级流量管理）仍以 Istio 原生为准

## 九、最佳实践

- **节点规划**：dev/test 集群 8C16G，prod 集群至少 16C32G 起步（开启 monitoring + logging 后）
- **StorageClass**：生产必须有动态供给（local-path / nfs / ceph-rbd 均可）
- **ClusterConfiguration 集中管理**：用 Git 管理 YAML，ks-installer 触发 reconcile
- **多集群**：主集群单独部署，只跑 ks-core + federation-controller
- **DevOps 节点隔离**：jenkins / sonarqube 可放到独立节点池
- **监控自监控**：用 whizard-monitoring 自身告警面板做 SLO
- **审计必开**：审计日志直送 ES，平台层面所有动作可追溯
- **升级节奏**：跟随官方 release note，重大版本（3→4）单独做 POC
- **资源配额**：项目级 `resourceQuota` + 默认 LimitRange，避免误用