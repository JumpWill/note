# Alertmanager

> Prometheus 的**告警中枢**。Prometheus 负责"算"（PromQL + alert rules），Alertmanager 负责**分发**（分组、去重、抑制、静默、路由）。
> 没有 Alertmanager，Prometheus 也能发 `console` 邮件测试，但生产告警链路都靠它。

---

## 一、它在链路里的位置

```
┌─────────────┐   rules 命中   ┌──────────────┐   AM 协议   ┌──────────────┐
│  Prometheus │ ─────────────► │ Alertmanager │ ──────────► │ 接收器/通道  │
│  (alerting) │               │  (routing)   │             │ 飞书/钉钉/… │
└─────────────┘               └──────────────┘             └──────────────┘
                                     ▲
                                     │ HA Cluster (gossip)
                              ┌──────┴───────┐
                              │ Alertmanager │
                              │   (peer)     │
                              └──────────────┘
```

Prometheus 启动时通过 `--web.enable-lifecycle` 暴露 `/api/v1/alerts`，Alertmanager 拉取并处理。
Alertmanager 之间用 **gossip 协议**同步告警状态与静默规则——所以 HA 必须 2 副本起步。

---

## 二、核心概念（读懂配置的关键）

| 概念 | 一句话 | 关键参数 |
| --- | --- | --- |
| **Group（分组）** | 把**同一组**的告警压成一条通知，避免刷屏 | `group_by` / `group_wait` / `group_interval` |
| **Route（路由）** | 树状结构，按 label 匹配决定**发给谁** | `matchers` / `routes`（递归子路由） |
| **Receiver（接收器）** | 最终的发送通道，飞书/钉钉/邮件/Webhook… | `webhook_configs` / `email_configs` … |
| **Inhibit（抑制）** | A 发生时**自动屏蔽** B（避免噪音掩盖真凶） | `inhibit_rules` |
| **Silence（静默））** | 维护窗口/已知故障时**手动屏蔽**一段时间 | `silences`（CLI/API） |
| **Repeat** | 告警未恢复，**多久再发一次** | `repeat_interval` |

**时间参数怎么配合**：

```
告警触发 ──┐
           │ group_wait（等多久，看同一波会不会再有）─► 首次发送
           ▼
      持续未恢复 ──► group_interval（同组新告警多久合一波再发）
           ▼
      仍未恢复 ──► repeat_interval（**单条**告警多久重发一次）
```

- `group_wait` 太大：首次告警延迟；太小：抖动风暴时告警风暴
- `repeat_interval` 太小：手机被刷屏；太大：真出事没人盯
- 经验值：P0 30s–2min、P1 1h、P2 6h–24h

---

## 三、完整配置（生产可用版）

```yaml
global:
  resolve_timeout: 5m                  # 告警恢复后多久发"已恢复"通知
  smtp_smarthost: 'smtp.example.com:465'
  smtp_from: 'alert@example.com'
  smtp_auth_username: 'alert@example.com'
  smtp_auth_password: 'xxx'
  smtp_require_tls: false              # 465 端口走 SSL，不要再启 TLS
  # PagerDuty / Slack / VictorOps 等也在这里配

templates:
  - '/etc/alertmanager/templates/*.tmpl'   # 自定义通知模板路径

# ============ 路由树（核心） ============
route:
  receiver: 'default'                  # 兜底接收器
  group_by: ['alertname', 'namespace'] # 默认分组维度
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  routes:
    # P0 → 立即多通道（飞书+电话+邮件）
    - matchers:
        - severity="P0"
      receiver: 'p0-oncall'
      group_wait: 10s
      group_interval: 1m
      repeat_interval: 30m
      continue: true                   # P0 命中后继续向下匹配（让电话+钉钉都收到）

    # 业务团队按 namespace 路由
    - matchers:
        - namespace=~"order|payment"
      receiver: 'team-payment'
      group_by: ['alertname', 'pod']

    - matchers:
        - namespace=~"infra|kube-system"
      receiver: 'team-sre'

    # 白天/夜间分流
    - matchers:
        - severity=~"P1|P2"
      active_time_intervals:
        - business_hours               # 见下面的 time_intervals
      receiver: 'slack-business'
      repeat_interval: 24h

# ============ 接收器 ============
receivers:
  - name: 'default'
    webhook_configs:
      - url: 'http://prometheus-alert:8080/prometheusalert?type=fs&tpl=prometheus-default'

  - name: 'p0-oncall'
    webhook_configs:
      - url: 'http://prometheus-alert:8080/prometheusalert?type=fs&tpl=prometheus-p0'
        send_resolved: true
    # 多通道同时发
    pagerduty_configs:
      - service_key: 'xxx'
        send_resolved: true
    email_configs:
      - to: 'oncall@example.com'
        send_resolved: true

  - name: 'team-payment'
    webhook_configs:
      - url: 'http://prometheus-alert:8080/prometheusalert?type=fs&tpl=prometheus-payment'

  - name: 'team-sre'
    webhook_configs:
      - url: 'http://prometheus-alert:8080/prometheusalert?type=fs&tpl=prometheus-sre'

  - name: 'slack-business'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/xxx'
        channel: '#alerts-business'
        send_resolved: true

# ============ 抑制规则（避免噪音） ============
inhibit_rules:
  # ① 整个集群 down → 单个 node down 不再发
  - source_matchers:
      - alertname="ClusterDown"
    target_matchers:
      - alertname=~"NodeDown|APIServerDown|EtcdDown"
    equal: ['cluster']

  # ② Pod 已被 OOMKilled → 容器重启告警不再发
  - source_matchers:
      - alertname="PodOOMKilled"
    target_matchers:
      - alertname="PodCrashLooping"

  # ③ 高优告警 → 低优告警
  - source_matchers:
      - severity=~"P0|P1"
    target_matchers:
      - severity=~"P2|P3"

# ============ 时间窗口 ============
time_intervals:
  - name: business_hours
    time_intervals:
      - weekdays: ['monday:friday']
        times:
          - start_time: '09:00'
            end_time: '20:00'
      - weekdays: ['saturday', 'sunday']
        times:
          - start_time: '00:00'         # 周末全天静默业务告警
            end_time: '24:00'
```

---

## 四、关键参数详解

### 4.1 `matchers`（v0.22+ 推荐用，老的 `match`/`match_re` 已废弃）

```yaml
- matchers:
    - severity="P0"                   # 完全匹配
    - namespace=~"order|payment"      # 正则
    - alertname!="InfoAlert"          # 不等于
    - cluster                        # 存在即匹配（无值）
```

注意：`=~` 用 **RE2 正则**，不是 PCRE，`|` 是或，`^`/`$` 自动加。

### 4.2 路由树的评估顺序

- 按 `routes` 列表**自上而下**匹配
- 第一个**完全命中**的路由决定 receiver（除非 `continue: true`）
- 子路由的 `matchers` 是**叠加**在父路由之上的（AND 关系）
- 子路由可继续嵌套

### 4.3 告警模板（Go template）

`/etc/alertmanager/templates/feishu.tmpl`：

```
{{ define "feishu.default" }}
{
  "msg_type": "interactive",
  "card": {
    "header": {
      "title": {{ .Status | toUpper }},
      "template": {{ if eq .Status "firing" }}"red"{{ else }}"green"{{ end }}
    },
    "elements": [{
      "fields": [
        {{ range .Alerts }}
        { "is_short": true, "text": { "tag": "text", "text": "**{{ .Labels.alertname }}**\n{{ .Annotations.summary }}" }},
        {{ end }}
      ]
    }]
  }
}
{{ end }}
```

模板可在 `webhook_configs` 里通过 `&tpl=` 选择：

```
http://prometheus-alert:8080/prometheusalert?type=fs&tpl={{ template "name" . }}
```

---

## 五、常用操作

### 5.1 命令行工具 `amtool`

```bash
# 安装（在 alertmanager 镜像里就有）
amtool check-config alertmanager.yml    # 校验配置
amtool config show --alertmanager.url=http://localhost:9093

# 查看告警
amtool alert query --alertmanager.url=http://localhost:9093
amtool alert query alertname=PodCrashLooping

# 加静默（1 小时内不发 namespace=order 的告警）
amtool silence add \
  --comment="订单库升级" \
  --duration=1h \
  --matchers="namespace=order,severity=~P1|P2"

# 查/删静默
amtool silence list
amtool silence expire <silence_id>
```

### 5.2 热加载配置

```bash
curl -X POST http://localhost:9093/-/reload
# 或发 SIGHUP
```

但**路由/接收器变更**无需 reload（通过 API 推），**新加 inhibit_rules / templates** 必须 reload。

### 5.3 静默（Silence）最佳实践

- 静默匹配**要尽量窄**（带 namespace/cluster/alertname），别静默整个 severity
- 静默一定要写 **comment**——半年后没人记得为什么静默
- 长期静默（>24h）走**抑制规则**或**修告警表达式**，别靠 silence 续命

---

## 六、高可用（HA）

Alertmanager HA 是**集群模式**，不是主备——多个副本同时工作，gossip 同步状态。

```yaml
# alertmanager.yml
global: {}

# 关键：用 --cluster.* 参数启动（不是配在 yaml 里）
# alertmanager \
#   --config.file=/etc/alertmanager/alertmanager.yml \
#   --storage.path=/alertmanager \
#   --cluster.listen-address="" \          # 空 = 本节点 IP
#   --cluster.peer=alertmanager-0:9094 \
#   --cluster.peer=alertmanager-1:9094 \
#   --web.external-url=http://am.example.com
```

**注意**：
- 副本数 ≥ 2，推荐 3（容忍 1 挂）
- gossip 端口 `9094` 必须互通
- 共享后端存储（GossipStore 可选 `nflog` 存本地，但**Silences 必须外部存储**——通常用 `bbolt` 文件挂 PVC，多副本 PVC 需 RWX）

---

## 七、踩过的坑

1. **告警风暴**：一条规则写成 `up == 0` 没加 `for: 5m`，网络抖动就会刷屏——`for` 是必填
2. **没区分 severity**：所有告警都进同一个 receiver，运维被刷爆——**告警分级 + 路由树是第一步**
3. **Prometheus 多个副本推给同一个 AM**：需要**一致性哈希**（`--alertmanager.target` 多个用 `--alertmanager.shard` 切分），否则同一告警会重复发送
4. **`resolve_timeout` 太短**：服务闪断一下就发"恢复"，监控人员以为没事——设 5m 起步
5. **webhook URL 拼参数出错**：`?type=fs&tpl=xxx` 里 `tpl` 不存在，消息体空白——**模板名必须先在 prometheus-alert 里注册**
6. **静默匹配过宽**：静默了 `severity=P2`，结果 P0 也被吞——matcher **必须带具体维度**

---

## 八、与 Prometheus 的接线

Prometheus 侧只需要在 `prometheus.yml` 里指：

```yaml
alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager-0:9093', 'alertmanager-1:9093']
      # 大集群加 path_prefix + scheme
    - path_prefix: /      # 适配 AM 前面挂 nginx ingress
```

alert rules 在 Prometheus 端（PrometheusRule CRD / `rule_files`），AM 不写 PromQL——**算归 Prometheus，发归 Alertmanager**，职责清晰。
