# K8s 定制化开发文档集

> 本文档集系统讲解 K8s 各种定制化开发方向,从为什么做、怎么做到生产实践,帮助开发者深入掌握 K8s 扩展能力。

## 文档目录

| 编号 | 文档 | 主要内容 | 推荐度 |
|------|------|---------|--------|
| 01 | [CRD 自定义资源](01-CRD自定义资源.md) | 自定义资源、Schema 设计、CRD 版本管理、CEL 验证、Finalizer | ⭐⭐⭐⭐⭐ |
| 02 | [Operator 开发](02-Operator开发.md) | Operator SDK、Kubebuilder、Controller 编写、Operator 全流程 | ⭐⭐⭐⭐⭐ |
| 03 | [Admission Webhook](03-AdmissionWebhook准入控制.md) | Mutating/Validating、镜像管控、sidecar 注入、安全合规 | ⭐⭐⭐⭐ |
| 04 | [自定义 Scheduler](04-自定义Scheduler调度器.md) | Scheduler 扩展点、Filter/Score、多 Scheduler 并行 | ⭐⭐⭐ |
| 05 | [CSI 存储接口](05-CSI存储接口.md) | CSI 规范、Controller/Node、Snapshot、扩容 | ⭐⭐⭐⭐ |
| 06 | [CNI 网络接口](06-CNI网络接口.md) | CNI 规范、ADD/DEL/CHECK、Multus 多网络 | ⭐⭐⭐ |
| 07 | [Device Plugin 设备插件](07-DevicePlugin设备插件.md) | GPU/RDMA/FPGA 设备、ResourceClaim、DRA | ⭐⭐⭐ |
| 08 | [Aggregated API Server](08-AggregatedAPIServer聚合API服务.md) | 自研 API 扩展、复用 K8s 认证授权 | ⭐⭐⭐ |
| 09 | [开发工具链](09-开发工具链与最佳实践.md) | 脚手架、测试、CI/CD、Helm、OLM | ⭐⭐⭐⭐⭐ |

## 知识地图

```text
K8s 定制化开发全景：

┌──────────────────────────────────────────────────────────┐
│                    业务场景                                │
│                                                          │
│  自研中间件  自研数据库  业务平台  多集群管理  AI/GPU  │
│  Kafka  MySQL  Redis  TiDB  业务PaaS  Argo  Calico       │
└──────┬──────────┬──────────┬──────────┬──────────┬────────┘
       │          │          │          │          │
       ↓          ↓          ↓          ↓          ↓
┌──────────────────────────────────────────────────────────┐
│                    扩展机制选择                            │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐  │
│  │   CRD    │  │ Operator │  │   AA     │  │ 其他     │  │
│  │ 简单资源  │  │ 业务逻辑  │  │ 完整API  │  │ 扩展     │  │
│  └──────────┘  └──────────┘  └──────────┘  └─────────┘  │
│       │              │            │             │           │
│       │              │            │             │           │
│  ┌────┴──────────────┴─┬──────────┴─────────┬───┴─────┐  │
│  │                    │                    │           │  │
│  │              CRD + Controller        │    CNI/CSI  │  │
│  │              （推荐组合）             │   DP/Sched  │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

## 文档集结构

```text
每个文档遵循统一结构：
  1. 为什么做（业务背景、价值、适用场景）
  2. 核心原理（架构、规范、关键概念）
  3. 实战开发（项目结构、核心代码、详细示例）
  4. 实战场景（多个真实用例 + 完整 YAML）
  5. 高级主题（性能优化、调试、最佳实践）
  6. 参考资源（官方文档、社区资源）
  7. 速记卡（核心要点）
```

## 选型指南

```text
问：我想自定义资源（CRD）吗？
  → CRD 足够（最常用）
  → 看 01-CRD自定义资源.md

问：CRD 不够，需要业务逻辑？
  → Operator（CRD + Controller）
  → 看 02-Operator开发.md

问：需要在 API 请求落地前拦截修改？
  → Admission Webhook
  → 看 03-AdmissionWebhook准入控制.md

问：需要自定义 Pod 调度逻辑？
  → 自定义 Scheduler
  → 看 04-自定义Scheduler调度器.md

问：需要接入自研存储？
  → CSI 存储接口
  → 看 05-CSI存储接口.md

问：需要接入自研网络？
  → CNI 网络接口
  → 看 06-CNI网络接口.md

问：需要接入 GPU/RDMA/FPGA？
  → Device Plugin
  → 看 07-DevicePlugin设备插件.md

问：需要完整的 API 扩展（CRD 不够）？
  → Aggregated API Server
  → 看 08-AggregatedAPIServer聚合API服务.md

问：开发工具链、CI/CD、测试怎么选？
  → 看 09-开发工具链与最佳实践.md
```

## 扩展机制对比速记

```text
┌─────────────────┬────────────┬──────────────┬─────────────┐
│  机制            │  复杂度    │  适合        │  典型场景   │
├─────────────────┼────────────┼──────────────┼─────────────┤
│  CRD             │  低        │  简单资源     │  资源抽象  │
│  Operator        │  中        │  业务编排     │  中间件    │
│  AA              │  高        │  完整 API     │  PaaS 平台 │
│  Webhook         │  中        │  拦截修改     │  安全合规  │
│  Scheduler       │  高        │  自定义调度  │  AI/GPU   │
│  CSI             │  高        │  存储插件    │  块存储    │
│  CNI             │  高        │  网络插件    │  SDN 设备  │
│  Device Plugin  │  中        │  硬件设备    │  GPU/RDMA  │
└─────────────────┴────────────┴──────────────┴─────────────┘
```

## 推荐学习路径

```text
入门路径：
  1. 01-CRD（最基础）
  2. 02-Operator（最常用）
  3. 09-工具链（必备）

进阶路径：
  1. 03-AdmissionWebhook
  2. 05-CSI 或 07-DevicePlugin（按需）

高级路径：
  1. 04-Scheduler
  2. 06-CNI
  3. 08-AA
```

## 开发工具链速记

```text
脚手架：Kubebuilder（最常用）
框架：Operator SDK / controller-runtime
测试：envtest（单元）+ kind（集成）
CI/CD：GitHub Actions / GitLab CI
打包：Helm + OLM（Operator Lifecycle Manager）
清单：Kustomize
```

## 一句话总结

```
K8s 定制化开发 = 标准化接口 + 领域代码
  1. 简单资源用 CRD
  2. 复杂业务用 Operator
  3. 准入控制用 Webhook
  4. 调度用自定义 Scheduler
  5. 存储用 CSI
  6. 网络用 CNI
  7. 设备用 Device Plugin
  8. 完整 API 扩展用 Aggregated APIServer
  9. 开发流程：脚手架 + 测试 + CI/CD + Helm
```

## 贡献

发现错误或想补充内容,直接修改对应章节的 md 文件即可。
```