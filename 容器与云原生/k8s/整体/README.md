# Kubernetes 知识体系 (Kubernetes Complete)

> 按照 [MySQL 文档](../../数据库/MySQL/) 的章节组织方式编排。涵盖 Kubernetes 从入门到精通的完整知识体系,适用于 Kubernetes 1.27+。

## 章节目录

| 章节 | 标题 | 大小 | 主要内容 |
|------|------|------|---------|
| [01](01-K8s概述与安装.md) | K8s 概述与安装 | 13K | Borg 起源、版本、安装方式、kubeadm 部署 |
| [02](02-体系结构与核心组件.md) | 体系结构与核心组件 | 19K | Control Plane / Worker Node / etcd / Pod 创建流程 |
| [03](03-kubectl与YAML.md) | kubectl 与 YAML | 13K | kubectl 命令、YAML 语法、JSONPath |
| [04](04-Pod与容器.md) | Pod 与容器 | 19K | Pod 完整定义、Probe、SecurityContext、多容器 |
| [05](05-Deployment与StatefulSet.md) | Deployment、StatefulSet | 17K | 无状态/有状态工作负载、HPA、滚动升级 |
| [06](06-Service网络.md) | Service 与网络 | 16K | 4 种 Service 类型、DNS、CNI、Ingress |
| [07](07-ConfigMap与Secret.md) | ConfigMap 与 Secret | 15K | 配置注入、3 种方式、etcd 加密 |
| [08](08-存储与Volume.md) | 存储与 Volume | 17K | PV/PVC、StorageClass、CSI、动态供给 |
| [09](09-RBAC权限管理.md) | RBAC 权限管理 | 12K | Role、ClusterRole、ServiceAccount、调试 |
| [10](10-Helm包管理.md) | Helm 包管理 | 19K | Chart、Release、Template、Repository |
| [11](11-监控日志与可观测性.md) | 监控、日志与可观测性 | 16K | Prometheus + Grafana + Loki + Tempo |
| [12](12-调度与亲和性.md) | 调度与亲和性 | 13K | NodeAffinity、PodAffinity、Taints |
| [13](13-安全最佳实践.md) | 安全最佳实践 | 16K | 认证、RBAC、网络策略、镜像安全、Falco |
| [14](14-高可用与升级.md) | 高可用集群与升级 | 17K | etcd 集群、控制平面 HA、升级流程 |
| [15](15-Namespace与资源管理.md) | Namespace 与资源管理 | 11K | ResourceQuota、LimitRange、多租户 |
| [16](16-Ingress与Gateway.md) | Ingress 与 Gateway API | 13K | Nginx Ingress、Traefik、Gateway API |
| [17](17-故障排查与运维实战.md) | 故障排查与运维实战 | 13K | Pod/Node/网络/存储故障排查 |
| [18](18-K8s实战案例集.md) | K8s 实战案例集 | 14K | 12 个真实场景完整实战 |

## 知识地图

```text
入门                进阶                       高级                       实战
├─ 01 概述安装     ├─ 04 Pod 与容器           ├─ 08 存储与 Volume       ├─ 14 高可用与升级
├─ 02 体系结构     ├─ 05 Deployment           ├─ 09 RBAC              ├─ 15 Namespace
└─ 03 kubectl     ├─ 06 Service 网络         ├─ 10 Helm              ├─ 16 Ingress
                 ├─ 07 ConfigMap/Secret    ├─ 11 监控日志           ├─ 17 故障排查
                                            ├─ 12 调度              └─ 18 实战案例集
                                            └─ 13 安全
```

## 学习路线建议

### 初学者 (1-2 周)

1. 阅读 01 了解 K8s 是什么、如何安装
2. 学习 02 掌握整体架构
3. 学习 03 熟悉 kubectl 命令
4. 实战 04 创建第一个 Pod

### 进阶者 (2-3 周)

1. 学习 05 Deployment/StatefulSet 各种工作负载
2. 学习 06 Service 与网络
3. 学习 07 ConfigMap/Secret 配置管理
4. 学习 16 Ingress 入口

### 高级者 (4-6 周)

1. 学习 08 存储与 PV/PVC
2. 学习 09 RBAC 权限管理
3. 学习 10 Helm 包管理
4. 学习 12 调度策略

### 实战方向

- 重点:11 监控日志、13 安全、14 高可用
- 必备:15 Namespace 多租户、17 故障排查
- 进阶:18 实战案例集

### 运维方向

1. 安装部署 (01, 02, 14)
2. 工作负载 (04, 05, 15)
3. 网络与存储 (06, 07, 08)
4. 监控安全 (09, 11, 13)
5. 排错与实战 (17, 18)

### 开发方向

1. kubectl 命令 (03)
2. Pod 与容器 (04)
3. Deployment 与 Service (05, 06)
4. 配置与 Helm (07, 10)
5. 实战案例 (18)

## 配套工具推荐

| 工具 | 用途 | 链接 |
|------|------|------|
| kubectl | 命令行客户端 | 自带 |
| k9s | TUI 管理工具 | https://k9scli.io/ |
| Stern | 多 Pod 日志聚合 | https://github.com/stern/stern |
| Helm | 包管理 | https://helm.sh/ |
| ArgoCD | GitOps | https://argo-cd.readthedocs.io/ |
| Prometheus | 监控 | https://prometheus.io/ |
| Grafana | 可视化 | https://grafana.com/ |
| Loki | 日志聚合 | https://grafana.com/oss/loki/ |
| Velero | 备份恢复 | https://velero.io/ |
| cert-manager | TLS 自动化 | https://cert-manager.io/ |

## 安装方式选择

| 场景 | 推荐 |
|------|------|
| 本地学习 | minikube / kind |
| 边缘/IoT | k3s |
| 开发测试 | kind / Docker Desktop |
| 生产标准 | kubeadm |
| 生产推荐 | 托管 K8s (EKS/GKE/ACK) |
| 国产生态 | KubeSphere / Rancher |

## 核心概念速记

```text
Pod        - 最小调度单元 (1+ 容器)
Deployment - 无状态应用
StatefulSet- 有状态应用 (DB/MQ)
DaemonSet  - 节点级服务
Service    - 服务发现 + 负载均衡
Ingress    - HTTP/HTTPS 入口
ConfigMap  - 非机密配置
Secret     - 机密信息
Volume     - 存储卷
Namespace  - 多租户隔离
RBAC       - 权限控制
```

## 版本说明

- 主要面向 **Kubernetes 1.28+**
- K8s 每 4 个月发版,生产推荐用 N-1 (稳定)
- 支持版本: 上游最新 3 个次版本
- 1.28+ 引入 Sidecar Containers GA、nftables backend

## Kubernetes vs 其他编排系统

| 特性 | Kubernetes | Docker Swarm | Mesos |
|------|-----------|--------------|-------|
| 成熟度 | 极高 | 中 | 中 |
| 生态 | 极丰富 | 一般 | 复杂 |
| 学习曲线 | 陡 | 平缓 | 陡 |
| 扩展性 | 极强 | 弱 | 强 |
| 市场份额 | **80%+** | 5% | 5% |

## 贡献

发现错误或想补充内容,直接修改对应章节的 md 文件即可。
