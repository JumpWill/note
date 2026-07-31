# Grafana

可视化平台，Grafana Labs 主导。成为云原生监控的事实展示层，从 metrics 仪表板扩展到日志 / 追踪 / RUM / Profiling。

## 一、定位与特点

- 单一视图：Metrics / Logs / Traces / Profiles
- 多数据源：Prometheus / Loki / Elasticsearch / Tempo / MySQL / CloudWatch / BigQuery / Pyroscope / 大几十种
- 仪表板 DSL：JSON 模板化，可用 variables 复用
- Alerting：自带告警通道，支持独立和统一告警路由
- Plugins：自定义面板 / 数据源 / 集成应用

## 二、架构

```text
┌──────────────────────────────────────┐
│ Grafana Frontend（React SPA UI）       │
├──────────────────────────────────────┤
│ Grafana Server（Golang）               │
│   - 数据源适配                          │
│   - Query 转换                          │
│   - Alerting Engine                     │
│   - Provisioning                        │
├──────────────────────────────────────┤
│ 数据源                                 │
│   Prometheus / Loki / Tempo / ES       │
│   CloudWatch / Pyroscope / 商业方案 ...  │
└──────────────────────────────────────┘

存储：
   - SQLite (内置)
   - MySQL / PostgreSQL（生产部署，用于用户 / 仪表板 / alerting）
```

## 三、数据源

| 类型 | 用途 |
| ---- | ---- |
| **Prometheus** | 时序指标 + 告警 |
| **Loki** | 日志 |
| **Tempo** | 追踪 |
| **Elasticsearch** | 日志 / 检索 |
| **CloudWatch** | AWS 指标 |
| **BigQuery** | 数据仓库查询 |
| **Pyroscope** | Profiling |
| **PostgreSQL / MySQL / MSSQL** | 关系型可视化 |
| **InfluxDB / ClickHouse / OpenObserve** | 时序 / OLAP |
| **TDengine** | 国产时序 |
| **Redis / Druid** | 其他 |

每数据源有自己的 Query Editor。

## 四、仪表板

### 1. 组成

- **Panel**：单个图 / 表 / 仪表 / HeatMap
- **Row**：多个 Panel 的容器
- **Dashboard**：多个 Row
- **Variables**：动态参数（$env、$region）
- **Links**：跳转其他 dashboard
- **Annotations**：事件标记
- **Templating**：可重用 JSON

### 2. JSON 模型

```json
{
  "title": "API Server",
  "uid": "abc123",
  "panels": [
    {
      "type": "timeseries",
      "title": "QPS",
      "targets": [
        {"expr": "rate(http_requests_total{service=\"api\"}[1m])"}
      ]
    }
  ],
  "templating": {
    "list": [
      {
        "name": "env",
        "type": "query",
        "datasource": "Prometheus",
        "query": "label_values(up, env)"
      }
    ]
  }
}
```

### 3. 面板类型（部分）

| 类型 | 用途 |
| ---- | ---- |
| **timeseries** | 折线 / 面积 |
| **stat / bargauge** | 当前数值 / 排名 |
| **gauge** | 单指标仪表盘 |
| **barchart** | 柱状 |
| **table** | 表格 |
| **heatmap** | 密度 |
| **logs** | 日志检索结果 |
| **traces** | Trace 列表 |
| **nodeGraph** | 服务依赖 |
| **geomap** | 地图 |
| **candlestick** | 股票 K 线 |
| **text / markdown** | 说明 |
| **alertlist / dashboardlist** | 引用其他 |

## 五、变量 Templating

```text
datasource: Prometheus
query: label_values(up{job="node"}, instance)
multi: true
includeAll: true
```

变量面板使用：

```promql
node_cpu_seconds_total{instance=~"$instance"}
```

变量类型：

| 类型 | 含义 |
| ---- | ---- |
| `query` | 数据源查询 |
| `datasource` | 数据源列表 |
| `constant` | 常量 |
| `textbox` | 文本输入 |
| `interval` | 时间步长 |
| `custom` | 自定义（HTTP） |
| `system` | 内置（$__from, $__to） |

## 六、Alerting

### 1. Alerting 模式

- **Unified Alerting**（v8 后默认）：统一告警引擎，跨数据源
- **Legacy**：基于 Dashboard 阈值（旧版）

### 2. Alert Rule 组成

```yaml
apiVersion: 1
groups:
  - orgId: 1
    name: myrule
    folder: prod
    interval: 1m
    rules:
      - uid: myalert
        title: HighErrorRate
        condition: A
        for: 5m
        annotations:
          summary: ""
        labels:
          severity: critical
        data:
          - refId: A
            datasourceUid: prometheus
            model:
              expr: |
                sum(rate(http_requests_total{status=~"5.."}[1m]))
                  / sum(rate(http_requests_total[1m])) > 0.05
              instantQuery: true
              refId: A
              hide: false
```

### 3. Contact Point + Policy

- **Contact Point**：Email / Slack / PagerDuty / Webhook / 钉钉 / 企业微信
- **Notification Policy**：按 label 路由
- **Silence / Mute**：抑制窗口

## 七、Provisioning

使用文件系统声明式配置：

```yaml
# /etc/grafana/provisioning/datasources/datasource.yml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
```

```yaml
# /etc/grafana/provisioning/dashboards/dashboard.yml
apiVersion: 1
providers:
  - name: default
    folder: ''
    type: file
    options:
      path: /var/lib/grafana/dashboards
```

UI 操作 + 文件同步是 SaaS 团队最常用做法。

## 八、Explore

交互式查询界面：

- Metrics：直接输入 PromQL / MySQL
- Logs：LogQL / Lucene Query
- Traces：TraceQL
- 支持 traceId jump
- 看一眼属于哪个服务 / 调用哪个依赖

## 九、插件系统

| 类别 | 例子 |
| ---- | ---- |
| **Panel** | Polystat / Flowcharting / Canvas |
| **Datasource** | Elasticsearch / InfluxDB / TDengine |
| **App** | Kubernetes / Zabbix / AWS / Datadog |
| **Renderer** | Headless rendering |

```bash
grafana-cli plugins install <plugin-id>
```

## 十、企业特性

| 特性 | 说明 |
| ---- | ---- |
| **Loki / Tempo / Pyroscope** | Grafana Labs 全家桶 |
| **Grafana Cloud** | SaaS |
| **Grafana Enterprise** | 商业 |
| **Reporting** | 定期邮件 / PDF |
| **Audit Logs** | 操作审计 |
| **SAML / OAuth** | 鉴权 |
| **Cluster** | 多前端 / DB shared |

## 十一、与各类后端搭配

```text
Grafana
├── Prometheus   ──── metrics + alerting
├── Loki         ──── logs
├── Tempo        ──── traces
├── Pyroscope    ──── profiles
└── Grafana Agent / Alloy ─ 统一采集
```

统一界面切换。

## 十二、客户端 / 嵌入

### 1. 嵌入 iframe

```html
<iframe src="http://grafana/d-solo/abc123?panelId=1" />
```

`d-solo` 加参数得到单面板图。

### 2. Public Dashboard

v7.1+：免登录面板（不安全，仅限定 dashboard）。

## 十三、K8s 部署

```yaml
# Helm chart: grafana/grafana
persistence:
  enabled: true
  size: 10Gi
env:
  GF_SECURITY_ADMIN_PASSWORD: secret
sidecar:
  dashboards:
    enabled: true
    label: grafana_dashboard
    folder: /tmp/dashboards
datasources:
  default-datasource.yaml:
    apiVersion: 1
    datasources:
      - name: Prometheus
        type: prometheus
        access: proxy
        url: http://prometheus-server
```

- Sidecar 自动加载 ConfigMap 中的 dashboard
- Grafana Agent / Alloy + Promtail 也可一起安装

## 十四、最佳实践

- **统一约定**：dashboard JSON 进 Git，自动化 restore
- **告警分级**：label 化 + 路由
- **Query 复用**：用 recording rule / dashboard variable
- **模板复用**：公共 row + multi-via variable
- **alias**：使用显式 alias 利于搜索
- **Rate interval 与采集间隔**：与 Prometheus 一致避免空图
- **死链清理**：定期清理重复 dashboard
- **权限**：引入 RBAC，避免所有人能编辑全部
