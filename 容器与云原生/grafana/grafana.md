## 介绍

Grafana 是一个开源的分析和监控平台，主要用于可视化数据。它支持多种数据源，包括 Prometheus、InfluxDB、Elasticsearch 等。Grafana 的主要特点包括：

1. **数据可视化**：Grafana 提供了丰富的图表和图形选项，用于展示数据。
2. **仪表盘**：用户可以创建仪表盘，将多个图表组合在一起，以直观的方式展示数据。
3. **告警**：Grafana 支持告警功能，当某些条件满足时，可以触发告警并发送通知。
4. **用户管理**：Grafana 提供了用户和权限管理功能，可以控制不同用户对数据和功能的访问权限。

## 存储

Grafana 使用 SQLite 作为默认的数据库，也可以使用其他数据库如 MySQL、PostgreSQL 等。如果使用 SQLite，数据存储在 `grafana.db` 文件中。如果使用其他数据库，需要配置相应的连接信息。

## 配置

Grafana 的配置文件位于 `conf/defaults.ini`，可以通过编辑该文件来修改配置。以下是一些常用的配置选项：

```ini
# 默认端口 
http_port = 3000
# 默认数据库
database = sqlite3
# 默认数据库存储路径
database.path = /var/lib/grafana/grafana.db
# 默认数据源
[datasources]
[datasources.1]
type = "prometheus"
url = "http://localhost:9090"
jsonData = {"timeout":30}
# 使用外部postgresql
database.host = 127.0.0.1
database.name = grafana
database.user = grafana
database.password = grafana_password
# 仪表盘
[dashboard]
[dashboard.1]
title = "My Dashboard"
uid = "my-dashboard-uid"
```

## 功能

### 仪表盘

仪表盘其实就是展示数据的一个视图，可以展示一个或多个数据指标。其本质数据就是json，里面定义查询，指定好查询的数据源，然后选择好时间范围，就可以展示出数据了。

#### 播放列表

播放列表是仪表盘的集合，可以用于展示一组相关的仪表盘。播放列表可以用于展示多个仪表盘，例如，可以创建一个播放列表，用于展示某个时间段内的所有仪表盘。

#### 快照

快照是仪表盘的静态副本，可以用于展示某个时间段内的仪表盘。快照可以用于展示某个时间段内的仪表盘，例如，可以创建一个快照，用于展示某个时间段内的仪表盘。

#### 库面板

库面板是仪表盘的集合，可以用于展示一组相关的仪表盘。库面板可以用于展示多个仪表盘，例如，可以创建一个库面板，用于展示某个时间段内的所有仪表盘。

### 连接

Grafana 支持多种数据源，包括 Prometheus、InfluxDB、Elasticsearch 等。可以通过配置文件或 UI 添加数据源。

### 管理

Grafana 提供了用户和权限管理功能，可以控制不同用户对数据和功能的访问权限。
涉及用户，团队，服务账号的概念。
可以在面板里设置用户，团队的权限，
将用户添加到团队，然后设置团队权限等.

### 告警

Grafana 支持告警功能，当某些条件满足时，可以触发告警并发送通知。

#### Prometheus 告警

1. **告警规则**：在 Prometheus 中，告警规则是基于 PromQL 查询语言定义的，规则文件通常位于 `prometheus.yml` 中。
2. **告警管理**：Prometheus 自带 Alertmanager，用于管理告警的分组、抑制和通知。
3. **通知渠道**：Alertmanager 支持多种通知渠道，如 Email、Slack、PagerDuty 等。
4. **灵活性**：Prometheus 的告警规则非常灵活，可以基于复杂的查询条件触发告警。

#### Grafana 告警

1. **告警规则**：在 Grafana 中，告警规则是基于面板的查询结果定义的，配置较为直观。
2. **告警管理**：Grafana 提供了基本的告警管理功能，但不如 Prometheus 的 Alertmanager 强大。
3. **通知渠道**：Grafana 支持多种通知渠道，如 Email、Slack 等，但配置相对简单。
4. **可视化**：Grafana 的告警配置和管理界面更加友好，适合需要可视化管理的场景。

### 持久化

持久化数据库就OK

### oauth2

Grafana 支持 OAuth2 认证，可以通过配置文件指定 OAuth2 认证信息。

- `enabled`：启用 OAuth2 认证。
- `name`：OAuth2 提供商的名称。
- `allow_sign_up`：允许新用户注册。
- `client_id`：OAuth2 客户端 ID。
- `client_secret`：OAuth2 客户端密钥。
- `scopes`：请求的 OAuth2 范围。
- `auth_url`：OAuth2 授权 URL。
- `token_url`：OAuth2 令牌 URL。
- `api_url`：获取用户信息的 API URL。
- `allowed_domains`：允许的域名，用于限制可以登录的用户。

```ini
[auth.generic_oauth]
enabled = true
name = OAuth
allow_sign_up = true
client_id = your_client_id
client_secret = your_client_secret
scopes = openid profile email
auth_url = https://your-oauth-provider.com/oauth/authorize
token_url = https://your-oauth-provider.com/oauth/token
api_url = https://your-oauth-provider.com/userinfo
allowed_domains = yourdomain.com
```
