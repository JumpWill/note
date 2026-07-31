# cron / systemd timers

OS 级时间触发调度，最基础也最常用。

## 一、cron

### 1. 工作原理

cron 由守护进程 `crond` 周期性扫描所有用户的 crontab 文件，匹配当前时间与调度表达式，到点 fork 出子进程执行命令。

```text
crond（每分钟扫描一次）
   │
   ├─ /etc/crontab            系统级
   ├─ /etc/cron.d/*           系统级片段
   ├─ /var/spool/cron/<user>  用户级
   │
   ▼
匹配成功 → fork+exec 执行命令
```

- 最小粒度 1 分钟
- 运行结果通过邮件或 stdout（日志）通知
- 不保证幂等和重试，需上层任务自行处理

### 2. crontab 语法

```text
分 时 日 月 周  命令
*  *  *  *  *  /opt/run.sh
0  3  *  *  *  daily job
*/5 *  *  *  *  every 5 min
```

| 字段 | 范围 | 特殊字符 |
| ---- | ---- | -------- |
| 分 | 0–59 | `* , / -` |
| 时 | 0–23 | `* , / -` |
| 日 | 1–31 | `* , / - ?` |
| 月 | 1–12 / name | `* , / -` |
| 周 | 0–7 / name | `* , / - ?` |

### 3. 常用命令

```bash
crontab -e                  # 编辑当前用户 crontab
crontab -l                  # 列出当前
crontab -r                  # 删除当前
sudo crontab -u www -e      # 编辑指定用户
cat /etc/crontab            # 系统级
ls /etc/cron.d/             # 系统片段
```

### 4. 常见坑

- 环境变量：cron 默认极少 PATH，需在脚本中显式 source profile 或设绝对路径
- 时区：使用系统时区；多时区场景注意容器/虚拟机时区
- 输出：`>` 重定向，否则默认发邮件
- 跨日 23:59 任务不支持跨年；`@yearly` 类似
- 不保证执行结果幂等，单实例运行

### 5. anacron

为不能保证 24 小时开机的机器补跑漏掉的任务：

```text
/etc/cron.daily  /etc/cron.weekly  /etc/cron.monthly
由 anacron 启动后补跑
```

适合笔记本、边缘节点。

### 6. 典型场景

- 日志切割
- 证书续签提醒
- 数据库备份
- 简单清理任务
- 健康检查心跳

---

## 二、systemd timer

### 1. 工作原理

systemd 的 timer 单元 `.timer` 触发对应的 service 单元 `.service` 启动，本质上是 systemd 管理的服务而不是独立调度器。

```text
foo.timer   →  到点 → 启动 foo.service
                  ↓
            systemd 启动服务（long-running / one-shot）
```

- 精度可达微秒（默认 OnBootSec/OnUnitInactiveSec）
- 拥有完整日志 `journalctl -u foo.service`
- 资源控制 cgroup 复用（CPU/内存/IO limit）
- 支持 realtime（需精度时间源）和 monotonic 触发
- 与 cron 兼容（`systemd-cron` / `systemd-run`）

### 2. 单元示例

```ini
# /etc/systemd/system/backup.timer
[Unit]
Description=Daily backup timer

[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true
Unit=backup.service

[Install]
WantedBy=timers.target
```

```ini
# /etc/systemd/system/backup.service
[Unit]
Description=Run backup

[Service]
Type=oneshot
ExecStart=/opt/backup.sh
User=backup
```

### 3. 启用

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now backup.timer
systemctl list-timers --all
systemctl status backup.service
journalctl -u backup.service
```

### 4. 调度格式 `OnCalendar`

| 表达式 | 含义 |
| ------ | ---- |
| `*-*-* 03:00:00` | 每日 3 点 |
| `Mon..Fri 09:00:00` | 工作日 9 点 |
| `hourly` / `daily` / `weekly` | 快捷名 |
| `*:0/5` | 每 5 分钟 |
| `Sat,Sun 12:00:00` | 周末正午 |

### 5. timer 触发方式

| 字段 | 含义 |
| ---- | ---- |
| **OnCalendar** | 绝对时间（wall clock） |
| **OnBootSec** | 启动后多久 |
| **OnUnitActiveSec** | 服务上次 active 之后 |
| **OnUnitInactiveSec** | 服务上次 inactive 之后 |
| **OnStartupSec** | systemd 启动后 |
| **AccuracySec** | 触发精度，默认 1m |
| **RandomizedDelaySec** | 随机抖动 |

### 6. 与 cron 比较

| 维度 | cron | systemd timer |
| ---- | ---- | ------------- |
| 最小粒度 | 1 分钟 | 微秒 |
| 跨重启补跑 | 无（除非 anacron） | `Persistent=true` |
| 日志 | 邮件 / 自行重定向 | journalctl |
| 资源限制 | 无 | cgroup 全能力 |
| 依赖管理 | 无 | systemd 依赖链 |
| 单实例保证 | 文件锁 flock | `RemainAfterElapse=false` + 串行执行 |

### 7. systemd-run（临时任务）

```bash
systemd-run --on-active=5m /opt/task.sh
systemd-run --on-calendar="*:0/15" /opt/heartbeat.sh
```

适合临时一次性任务排程。

### 8. 常见坑

- 多个同 timer 同时启动可能要排队，需控制并发
- `Persistent=true` 补跑不会立即触发 on-boot 任务，仅按 OnCalendar
- 用户级 timer 需用 `systemctl --user` 配合 lingering（`loginctl enable-linger`）
- 容器内运行 timer 受 cgroup 限制，需注意主机 reboot 后容器是否启动

---

## 三、最佳实践

### 1. 何时选 cron

- 单机低频任务（每天 / 每小时）
- 简单备份 / 切割 / 巡检
- 不需要重启补跑

### 2. 何时选 systemd timer

- 需要高频触发（秒级）
- 需要跨重启补跑
- 需要 cgroup 资源限制
- 需要统一日志与依赖管理

### 3. 何时升级到分布式调度

- 需要高可用（主机挂了任务仍跑）
- 需要横向扩容（分片执行）
- 需要可视化管理、告警、审计
- 需要传递上下文或 DAG 依赖
- 转入 [XXL-JOB](xxl-job.md) / [Airflow](airflow.md) / [Argo](argo-workflows.md) / [Temporal](temporal.md)
