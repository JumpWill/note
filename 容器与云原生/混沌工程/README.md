# 混沌工程知识体系 (Chaos Engineering Complete)

> 按照 [MySQL 文档](../../数据库/MySQL/) 的章节组织方式编排。涵盖混沌工程从理念、原则、工具到生产实战的完整知识体系。

## 章节目录

| 章节 | 标题 | 主要内容 |
|------|------|---------|
| [01](01-混沌工程概述.md) | 混沌工程概述 | 历史、原则、成熟度模型 |
| [02](02-原则与方法论.md) | 原则与方法论 | 五大原则、稳态假说、实验流程 |
| [03](03-故障注入工具总览.md) | 故障注入工具总览 | 工具生态、对比、选型 |
| [04](04-ChaosMesh详解.md) | Chaos Mesh 详解 | CNCF K8s 原生平台 |
| [05](05-Litmus详解.md) | Litmus 详解 | CNCF 实验库平台 |
| [06](06-ChaosBlade详解.md) | ChaosBlade 详解 | 阿里开源多平台工具 |
| [07](07-Toxiproxy与Pumba.md) | Toxiproxy 与 Pumba | 网络与容器工具 |
| [08](08-Gremlin详解.md) | Gremlin 详解 | 商业故障注入平台 |
| [09](09-场景设计与实验方法.md) | 场景设计与实验方法 | 场景库与编排 |
| [10](10-实验最佳实践.md) | 实验最佳实践 | 流程、应急、合规 |
| [11](11-监控与可观测性.md) | 监控与可观测性 | SLI、Prometheus、OpenTelemetry |
| [12](12-案例实战.md) | 案例实战 | 10+ 真实场景演练 |
| [13](13-总结与速记.md) | 总结与速记 | 核心要点、面试速记 |

## 知识地图

```text
入门                进阶                       高级                       实战
├─ 01 概述         ├─ 04 Chaos Mesh          ├─ 09 场景设计           ├─ 12 案例实战
├─ 02 原则方法论   ├─ 05 Litmus              ├─ 10 最佳实践           └─ 13 总结速记
└─ 03 工具总览     ├─ 06 ChaosBlade          └─ 11 监控可观测性
                 ├─ 07 Toxiproxy/Pumba
                 └─ 08 Gremlin
```

## 学习路线建议

### 初学者 (1 周)

1. 阅读 01 了解混沌工程起源
2. 学习 02 掌握五大原则
3. 了解 03 工具生态
4. 阅读 12 案例实战 (感受价值)

### 进阶者 (2-3 周)

1. 学习 04 Chaos Mesh (K8s 推荐)
2. 学习 05 Litmus (实验库丰富)
3. 学习 09 场景设计方法
4. 学习 11 监控可观测性

### 高级者 (4-6 周)

1. 学习 06 ChaosBlade (中文)
2. 学习 10 最佳实践
3. 学习 08 Gremlin (商业方案)
4. 组织 Game Day

### 实战方向

- 重点:10 最佳实践 + 12 案例实战
- 必备:11 监控可观测性
- 进阶:组织 Game Day

## 配套工具推荐

| 工具 | 用途 | 链接 |
|------|------|------|
| **Chaos Mesh** | K8s 原生故障注入 | https://chaos-mesh.org |
| **Litmus** | 实验库 + Web UI | https://litmuschaos.io |
| **ChaosBlade** | 阿里多平台工具 | https://chaosblade.io |
| **Gremlin** | 商业 SaaS 平台 | https://www.gremlin.com |
| **Toxiproxy** | 网络代理故障 | https://github.com/Shopify/toxiproxy |
| **Pumba** | 容器混沌 | https://github.com/alexei-led/pumba |
| **stress-ng** | 主机压力 | https://github.com/ColinIanKing/stress-ng |
| **Prometheus** | 指标监控 | https://prometheus.io |
| **LGTM Stack** | 可观测性 | https://grafana.com/oss |
| **OpenTelemetry** | 统一采集 | https://opentelemetry.io |

## 安装方式选择

| 场景 | 推荐 |
|------|------|
| K8s 重度用户 | Chaos Mesh (CNCF) |
| 实验库 + UI 需求 | Litmus (CNCF) |
| 阿里生态 / 多平台 | ChaosBlade |
| 商业预算充足 | Gremlin |
| 网络/中间件测试 | Toxiproxy |
| 学习研究 | Chaos Monkey |

## 核心概念速记

```text
稳态 (Steady State):   系统正常时的可观察指标
假说 (Hypothesis):     故障 → 预期 SLI 变化
爆炸半径 (Blast Radius): 故障影响范围
SLI (Service Level Indicator): 核心指标
SLO (Service Level Objective): 指标目标
RPS/RED/USE:           监控方法论
RTO/RPO:               故障恢复时间/数据丢失
```

## 五大原则速记

```text
1. 围绕稳态提出假说 (Steady State)
2. 多样化的真实世界事件 (Real Events)
3. 在生产环境运行 (Production)
4. 持续自动化 (Continuous)
5. 最小化爆炸半径 (Blast Radius)
```

## 实验流程速记

```text
1. 准备 (1-2 周) - 假说/稳态/通知
2. 执行 (30 分钟) - 注入/监控/停止
3. 收尾 (30 分钟) - 销毁/验证
4. 复盘 (1 周) - 报告/改进/跟踪
```

## 立即停止条件

```text
- SLI 突破阈值 (>2 倍基线)
- 错误率超限
- 数据丢失
- 用户投诉
- 业务影响超出预期
- 人员不足
```

## 核心要点速记

```text
1. 工具选型: K8s→Chaos Mesh, 实验库→Litmus, 阿里→ChaosBlade
2. 必做稳态: SLO/SLI 是稳态指标
3. 小范围开始: 1 实例 → 全部
4. 集成 CI/CD: 部署后自动验证
5. 持续改进: 实验 → 报告 → 改进 → 验证
6. 培养文化: 假设永远会失败
7. 选低峰期: 业务影响最小
8. 准备回滚: 一键停止脚本
```

## 与其他章节关系

```text
SRE: 混沌工程是 SRE 实践的一部分
DevOps: 混沌工程集成到 CI/CD
K8s: 故障注入主要场景
Docker: 容器混沌 (Pumba, ChaosBlade)
监控: 可观测性是混沌的基础
安全: 混沌工程也是一种安全验证
```

## 版本说明

- 主要参考 Chaos Mesh 2.7+
- Litmus 3.x
- ChaosBlade 1.7.x
- 兼容 K8s 1.18+
- 监控基于 Prometheus + Grafana
- 链路追踪基于 OpenTelemetry

## 贡献

发现错误或想补充内容,直接修改对应章节的 md 文件即可。
