# Gremlin 详解 (商业故障注入平台)

> Gremlin 是混沌工程领域最成熟的商业平台,提供 SaaS 化服务和完整的企业级能力。

## 一、Gremlin 概述

### 1.1 公司简介

```text
公司:    Gremlin Inc.
官网:    https://www.gremlin.com/
成立:    2016 年 (旧金山)
定位:    混沌工程商业平台
用户:    亚马逊、Twilio、Confluent、Salesforce 等
```

### 1.2 核心特性

```text
1. 全面的故障类型
   - 12 种攻击类型
   - 涵盖资源/网络/状态/平台

2. Scenarios 场景
   - 预定义实验模板
   - 可组合编排
   - 持续运行

3. Reliability Management
   - SLA 管理
   - 风险评估
   - 改进跟踪

4. Game Days
   - 跨团队演练
   - 完整流程
   - 自动报告

5. SaaS 平台
   - 无需自己部署
   - Web UI + API
   - 团队协作
```

---

## 二、安装与接入

### 2.1 SaaS 模式 (推荐)

```bash
# 1. 注册账户
# https://www.gremlin.com/

# 2. 获取 API Key

# 3. 安装 Gremlin Client
curl -L https://github.com/gremlin/gremlin-cli/releases/latest/download/gremlin_linux_amd64 -o /usr/local/bin/gremlin
chmod +x /usr/local/bin/gremlin

# 4. 配置
gremlin config \
  --token=<your-api-token> \
  --team-id=<your-team-id>
```

### 2.2 容器接入

```yaml
# 在应用容器中注入 Gremlin Agent
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
spec:
  template:
    spec:
      containers:
      - name: my-app
        image: my-app:1.0
      - name: gremlin-agent
        image: gremlin/gremlin-agent:latest
        env:
        - name: GREMLIN_CLIENT_ID
          value: "<your-client-id>"
        - name: GREMLIN_CLIENT_SECRET
          valueFrom:
            secretKeyRef:
              name: gremlin-credentials
              key: client-secret
        - name: GREMLIN_TEAM_ID
          value: "<your-team-id>"
```

---

## 三、攻击类型 (Attacks)

### 3.1 Resources (资源类)

```text
CPU:
  - fullload: CPU 满载
  - usage: CPU 占用指定百分比
  - stress: 压力测试

Memory:
  - load: 占用指定大小
  - ramload: 内存满
  - oom: OOM

IO:
  - disk: 磁盘 IO 压力
  - fill: 磁盘填满

GPU:
  - stress: GPU 压力
```

### 3.2 Network (网络类)

```text
Latency:
  - 添加固定延迟 (ms)
  - 支持 jitter
  - 可针对性主机/端口

Loss:
  - 丢包率 (%)
  - 可针对性方向
  - 突发模式

Bandwidth:
  - 限制带宽
  - Mbps/Kbps

Blackhole:
  - 完全丢包
  - 模拟网络断开

DNS:
  - 劫持 DNS
  - 返回错误

Partition:
  - 网络分区
  - 隔离特定主机
```

### 3.3 State (状态类)

```text
Process Killer: 杀进程
Shutdown: 关机
Time Travel: 时钟漂移
Pause: 进程暂停
Hibernate: 休眠
```

### 3.4 Platform (平台类)

```text
Container Killer: 杀容器
Container Pause: 暂停容器
Host Reboot: 重启主机
Kubernetes:
  - Pod Kill
  - Node Drain
  - Service Disruption
```

### 3.5 Application (应用类)

```text
Latency:    添加延迟
Exception: 抛出异常
Replace:   替换响应
Blackhole: 黑洞
```

---

## 四、Scenarios (实验场景)

### 4.1 创建 Scenario

```bash
# 1. 通过 CLI 创建
gremlin scenario create \
  --name "数据库故障演练" \
  --description "测试应用在数据库故障时的韧性"

# 2. 添加攻击
gremlin scenario attack add \
  --scenario "数据库故障演练" \
  --type latency \
  --target redis \
  --length 30

# 3. 执行
gremlin scenario run "数据库故障演练"
```

### 4.2 Gremlin Web UI 场景

```text
Scenario 组成:

1. 选择攻击类型
2. 选择目标
3. 配置参数
4. 调度执行
5. 监控结果
```

### 4.3 预定义 Scenario

```text
Netflix Chaos Day:
  - 杀 EC2 实例
  - 杀 AZ
  - 网络分区

Database Failure:
  - DB 慢
  - DB 断
  - DB 资源耗尽

Cache Failure:
  - Redis 慢
  - Redis 满
  - Redis 雪崩

Network Failure:
  - 跨机房延迟
  - DNS 故障
  - 丢包

Kubernetes Failure:
  - Pod 杀
  - 节点故障
  - K8s API 不可用
```

---

## 五、实战案例

### 5.1 微服务故障注入

```bash
# 1. 创建服务账户
gremlin client create \
  --name my-app \
  --type kubernetes

# 2. 选择目标
gremlin attack create \
  --type latency \
  --target name=my-app \
  --length 30 \
  --latency 500

# 3. 执行
gremlin attack run <attack-id>
```

### 5.2 数据库故障演练

```bash
# Redis 慢响应
gremlin attack create \
  --type latency \
  --target name=redis \
  --length 5m \
  --latency 1000 \
  --jitter 100

# 数据库丢包
gremlin attack create \
  --type blackhole \
  --target name=mysql \
  --length 30s

# CPU 满载
gremlin attack create \
  --type cpu \
  --target name=api-service \
  --length 60s \
  --cpu 80
```

### 5.3 Game Day 演练

```bash
# 1. 创建 Game Day
gremlin gameday create \
  --name "黑色星期五压力测试" \
  --date "2026-11-25" \
  --duration 4h

# 2. 添加多个 Scenario
gremlin gameday add-scenario "黑色星期五压力测试" --scenario "DB故障"
gremlin gameday add-scenario "黑色星期五压力测试" --scenario "Redis慢响应"
gremlin gameday add-scenario "黑色星期五压力测试" --scenario "网络分区"

# 3. 邀请团队
gremlin gameday invite "黑色星期五压力测试" --team platform

# 4. 执行
gremlin gameday run "黑色星期五压力测试"
```

---

## 六、监控与报告

### 6.1 实时监控

```text
Gremlin Dashboard:
  - 实验执行状态
  - 系统指标
  - 服务降级
  - 错误率
  - 恢复时间
```

### 6.2 实验报告

```text
报告内容:
  1. 实验概述
  2. 攻击类型与持续时间
  3. SLI 变化曲线
  4. 告警触发
  5. 系统反应
  6. 改进建议
  7. 风险评分
```

### 6.3 Reliability Score

```text
Gremlin Reliability Score:
  - 基于历史实验数据
  - SLI 表现
  - 故障恢复时间
  - 监控告警
  - 团队响应

评分: 0-100
  - 90+: 优秀
  - 70-90: 良好
  - 50-70: 需改进
  - < 50: 高风险
```

---

## 七、Reliability Management

### 7.1 风险评估

```text
Gremlin Risk Assessment:
  - 列出系统所有组件
  - 评估每个组件的韧性
  - 给出风险评分
  - 提供改进建议
```

### 7.2 SLA 管理

```text
- 定义 SLA (SLO/SLI)
- 监控 SLO 状态
- 错误预算 (Error Budget)
- 告警阈值
- 改进建议
```

### 7.3 改进跟踪

```text
- 实验发现问题
- 自动创建 JIRA
- 跟踪改进进度
- 验证改进效果
```

---

## 八、安全与权限

### 8.1 RBAC

```bash
# 角色
- Admin: 完全权限
- Operator: 创建/执行实验
- Viewer: 只读
- Custom: 自定义角色
```

### 8.2 审计日志

```text
所有操作记录:
  - 用户
  - 操作
  - 时间
  - 目标
  - 结果
```

### 8.3 合规

```text
- SOC 2
- ISO 27001
- HIPAA
- PCI DSS
```

---

## 九、价格与版本

### 9.1 价格

```text
Free 试用: 5 次故障/月
Pro:     ~$200/月 (按工程师)
Enterprise: 定制
```

### 9.2 版本对比

| 版本 | 适合 |
|------|------|
| Free | 个人学习, 小实验 |
| Pro | 中小团队 |
| Enterprise | 大型企业 |

---

## 十、核心要点速记

### Gremlin 12 种攻击类型

```text
Resources: CPU, Memory, IO, GPU
Network:   Latency, Loss, Bandwidth, Blackhole, DNS, Partition
State:     Process Killer, Shutdown, Time Travel, Pause
Platform:  Container, Host, K8s Pod
```

### Gremlin 命令

```bash
# 配置
gremlin config --token=<token> --team-id=<id>

# 实验
gremlin attack create --type TYPE --target TARGET
gremlin attack run <id>
gremlin attack stop <id>

# Scenario
gremlin scenario create --name "演练"
gremlin scenario run "演练"

# Game Day
gremlin gameday create
gremlin gameday run
```

### 选型建议

```text
初创 / 个人 → Free 版试用
中小团队 → Pro (商业 SaaS, 免运维)
大型企业 → Enterprise (合规 + 报告)
阿里生态 → ChaosBlade (免费, 中文)
K8s 重度用户 → Chaos Mesh (免费, 集成好)
实验库 + UI → Litmus (免费, 实验丰富)
```

### Gremlin vs 其他工具

```text
Gremlin:    商业最成熟, UI 强大, 全功能
Chaos Mesh: CNCF, K8s 原生, 开源
Litmus:     实验库丰富, 开源
ChaosBlade: 阿里, 中文好, 一站式
```

### 何时选择 Gremlin

```text
✓ 预算充足
✓ 想要现成平台 (不自己维护)
✓ 需要专业报告
✓ 大型企业
✓ 合规要求高 (SOC 2, HIPAA)

✗ 初创 / 个人 → 免费工具 (Chaos Mesh, Litmus)
✗ 不想数据出境 → 开源工具
```

---

## 参考

- **Gremlin 官方**: https://www.gremlin.com/
- **Gremlin 文档**: https://www.gremlin.com/docs/
- **Gremlin 博客**: https://www.gremlin.com/blog/
- **Gremlin CLI**: https://github.com/gremlin/gremlin-cli
- **Gremlin Slack**: https://www.gremlin.com/community/
- **Slack Community**: https://slack.gremlin.com/
- **故障注入视频**: https://www.gremlin.com/community/tutorials/
- **Chaos Conf**: https://www.chaosconf.io/

## 二、场景设计与实验方法
