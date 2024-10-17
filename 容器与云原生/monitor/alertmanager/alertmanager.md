## alertmanager

alertmanager 是 prometheus 的告警组件，可以用来发送告警信息。

### 配置

```yaml
global:
  resolve_timeout: 5m

route:
  group_by: ['instance']
  group_wait: 10s
  # 告警分组时间间隔
  group_interval: 10s
  # 告警重复发送时间间隔
  repeat_interval: 10m
  # 告警接收者
  receiver: 'web.hook.prometheusalert'

receivers:

- name: 'web.hook.prometheusalert'
  webhook_configs:
  # 此处配置的是prometheus-alert的webhook地址，需要配置到prometheus-alert的配置文件中
  - url: 'http://prometheus-alert:8080/prometheusalert?type=fs&tpl=prometheus-fs&fsurl=https://open.feishu.cn/open-apis/bot/v2/hook/11111'
    send_resolved: true
```
