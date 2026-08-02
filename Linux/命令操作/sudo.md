# sudo

`sudo` 是 Linux / Unix 上"按策略授权以另一个用户身份运行命令"的标准机制。原始作者：BDFL 大神 Todd C. Miller，主流发行版默认预装。

## 1. 概览

```text
             ┌──────────────────────┐
             │ /etc/sudoers          │   策略
             │ /etc/sudoers.d/*      │
             └─────────┬────────────┘
                       │
                       ▼
              ┌─────────────────┐
              │   sudo (8)       │
              └────────┬────────┘
                       │
    ┌──────────────────┼──────────────────┐
    ▼                  ▼                  ▼
 入参解析          安全策略引擎        auth + log
  ldap / AD        是否允许运行           syslog
  SSSD / files      who where when what     auditd
```

关键概念：

- **sudo**：单机命令提权
- **su**：切换用户身份（需要密码）
- **polkit**：桌面图形提权
- **doas**：OpenBSD 风格简约 sudo 替代品

## 2. 配置文件 /etc/sudoers

### 2.1 主文件与片段

```text
/etc/sudoers                 # 主策略文件
/etc/sudoers.d/...           # 片段，drop-in 形式
```

使用 `visudo` 编辑。它调用 `$EDITOR`（默认 vi）并做语法校验，避免错配导致所有 sudo 失效。

```bash
visudo                       # 编辑 /etc/sudoers
visudo -f /etc/sudoers.d/dev # 编辑片段
```

### 2.2 语法（一行格式）

```text
who    where=(as_whom)    tag    commands
USER   HOSTS=(RUNAS)      TAGS:  COMMANDS
```

字段解释：

| 字段 | 含义 |
| ---- | ---- |
| **who** | 用户 / 用户组 / 用户别名 |
| **where** | 主机（多机器上复用同一文件时） |
| **as_whom** | 以谁身份运行（默认 root） |
| **tag** | NOPASSWD / NOPASSWD / SETENV / NOEXEC / LOG_OUTPUT 等 |
| **commands** | 命令 / 命令别名 |

例：

```sudoers
root        ALL=(ALL:ALL)          ALL
%sudo       ALL=(ALL:ALL)          ALL
alice       ALL=(root)             NOPASSWD: /usr/bin/systemctl restart nginx
bob         ALL=(ALL)              /bin/ls, /usr/bin/cat
devops      ALL=(nginx,www-data)  /usr/sbin/service *
DBAs        ALL=(postgres)        NOPASSWD: ALL
```

### 2.3 别名

四种别名：`User_Alias` / `Runas_Alias` / `Host_Alias` / `Cmnd_Alias`。

```sudoers
User_Alias     ADMINS = alice, bob, %admin
Runas_Alias     APPS  = www-data, nginx
Cmnd_Alias      SERVICES = /usr/bin/systemctl, /usr/sbin/service
Host_Alias      SERVERS = server1, server2, 10.1.0.0/16

ADMINS SERVERS=(APPS) NOPASSWD: SERVICES
```

### 2.4 规则如何匹配

- 一行末尾匹配（自上而下）。第一次匹配即生效。
- `=` 显式 allow；注释行不匹配；nothing 之后默认 deny。
- 多条规则叠加：被 deny 后的 allow 不能解除 deny。

```sudoers
# 显式 deny
alice ALL=(ALL) !/bin/bash
# 后面 allow 的 vim 不受影响
alice ALL=(ALL) /usr/bin/vim
```

### 2.5 关键默认（Defaults）

很多发行版 `/etc/sudoers.d/...` 含这些 Default：

```sudoers
Defaults    env_reset
Defaults    secure_path = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Defaults    !requiretty
Defaults    log_input
Defaults    log_output
Defaults    use_pty
Defaults    mail_badpass
Defaults    badpass_message = "Sorry, try again."
Defaults    timestamp_timeout = 5
Defaults    passwd_timeout = 5
Defaults    passwd_tries = 3
Defaults    insults
Defaults    !visiblepw
```

`Defaults` 可以放主文件或片段中。

## 3. 常见 Default 选项

| 选项 | 含义 |
| ---- | ---- |
| `env_reset` | 清空 env，仅保留安全几个 |
| `secure_path` | PATH 强制（防止 LD_PRELOAD 等） |
| `requiretty` | 必须有 tty（默认 ✘） |
| `pwfeedback` | 显示密码提示符 |
| `passwd_timeout` | 输入密码分钟数 |
| `timestamp_timeout` | 复用 sudo 间隔（分钟） |
| `use_pty` | 用 pseudo-terminal 跑命令 |
| `mail_badpass` | 错误密码发邮件给 root |
| `pwfeedback` | 密码进度条 |
| `env_keep` / `env_check` | env 白 / 黑名单 |
| `use_sudo_path` | 走 sudo 编译时 path |
| `secure_path` | sudo PATH |
| `always_query_group_list` | 群组多则显示 |
| `preserve_groups` | 不丢用户组 |
| `runchroot` | `sudo chroot` |
| `log_input` / `log_output` | 输入输出记录 |
| `log_format` | 日志格式（`sudo` 自带格式） |
| `iolog_dir` | I/O log 位置，默认 `/var/log/sudo-io` |
| `verifypw` | 账号密码 vs all |
| `pwcheck` | 验证别名列表外是否要密码 |

## 4. 命令行使用

```bash
sudo -l                       # 列出我能 sudo 的命令
sudo cat /etc/shadow          # 以 root 跑命令
sudo -u alice bash            # 以 alice 跑 bash
sudo -u www-data -g www-data ls /var/www
sudo -g docker docker ps       # 以指定组运行
sudo -i                       # 启动 login shell，su 到 root
sudo -s                       # non-login shell
sudo -b                       # 后台跑
sudo -e /path/script          # 编辑单个文件（sudoedit）
sudo -E                       # 保留当前 env
sudo --                      # 不能 sudo 的参数
sudo command 1 ; sudo command 2  # 两条
sudo sh -c 'ls /; ls /etc'
sudo -n command               # 不交互（no password）
sudo -A command               # 用辅助程序认证（不常用）
sudo -t TIMEOUT                # 复用窗口
```

`sudoedit`（`sudo -e`）按安全方式"借编辑另一个文件"，editor 跑在用户进程，没有 SUID 风险：

```bash
sudoedit /etc/hosts
sudo -e /etc/hosts
```

### 4.1 重要参数

| 参数 | 用途 |
| ---- | ---- |
| `-l` | 列出可执行命令 |
| `-u user` | 切目标用户 |
| `-g group` | 切目标组 |
| `-i` | 模拟 login |
| `-s shell` | 跑当前 shell |
| `-E` | env 不清 |
| `-k` | 立即过期密码缓存 |
| `-K` | 完全过期 |
| `-v` | 延长 timestamp |
| `-V` | 显示版本 |
| `-n` | 非交互 |
| `-b` | 后台（`fork to background`） |
| `-p prompt` | 自定义提示符 |
| `-S` | 从 stdin 读密码（`sudo -S`） |
| `-D defaults` | 临时改 Defaults |
| `-C fd` | 从 fd 读命令 |
| `--` | 之后的参数原样 |

### 4.2 sudoers 的 `Tag`

```sudoers
# NOPASSWD 不问密码
alice ALL=NOPASSWD: /bin/kill

# PASSWD 默认（问）
alice ALL=PASSWD: /usr/bin/vim

# NOEXEC 禁用 execve 子 shell 提权
bob ALL=NOEXEC: /usr/bin/vim

# SETENV 可设环境变量
dev ALL=SETENV: /usr/bin/vim
```

常用：`NOPASSWD / PASSWD / NOEXEC / SETENV / LOG_INPUT / LOG_OUTPUT`

## 5. 时间和会话管理

### 5.1 timestamp 复用机制

```bash
sudo whoami                     # 看你当前会话
sudo -nv                        # 查看是否还需密码（详细）
sudo -k                         # 撤销当前会话的 sudo 凭据
sudo -K                         # 完全过期（root 用户也能给）
```

机制：默认 5 分钟内，sudo 不重输密码。

- `Defaults timestamp_timeout=0` 永远要密码
- `Defaults timestamp_timeout=1440` 单日复用
- `Defaults !tty_tickets` 多个 tty 共享缓存

### 5.2 tty / pty

要求 tty 后才能 sudo（防止后门）：

```sudoers
Defaults requiretty
```

`sudo -S` 与 `requiretty` 互冲；脚本化 sudo 通常配：

```bash
visudo -f /etc/sudoers.d/dashboard
```

```sudoers
Defaults:dashboard !requiretty
```

## 6. 环境变量

```sudoers
# 保留 / 移除
Defaults env_keep += "TZ HISTFILE EDITOR"
Defaults env_reset
Defaults env_check = ["PATH", "HOME", "TERM", ...]

# 安全提示：env_reset 必清 LD_PRELOAD / LD_LIBRARY_PATH
Defaults secure_path="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
```

`-E` 保留当前（allowlist 内的）env。

## 7. 例子集

### 7.1 系统管理

```sudoers
%admins       ALL=(ALL)              ALL

alice         ALL=(ALL) NOPASSWD: /usr/bin/systemctl, /usr/sbin/reboot
bob           ALL=(ALL) NOPASSWD: ALL
```

### 7.2 Docker / K8s 容器用户

```sudoers
%docker      ALL=(ALL) NOPASSWD: /usr/bin/docker
%kubeadm     ALL=(root) NOPASSWD: /usr/bin/kubectl, /usr/bin/helm
```

### 7.3 Web / Database 服务

```sudoers
%nginx        ALL=(nginx,www-data) NOPASSWD: /usr/sbin/nginx, /usr/sbin/service nginx *
%pgdb         ALL=(postgres) NOPASSWD: /usr/bin/psql, /usr/lib/postgresql/*/bin/pg_*
```

### 7.4 只允许某特定命令

```sudoers
alice  ALL=(root) /usr/bin/systemctl restart my-app.service, /usr/bin/systemctl status my-app.service
```

允许 `restart` 与 `status` 但不允许 `start` 或 `stop`：

```bash
sudo -l     # alice
```

### 7.5 免密码运行 / 不需 tty

```sudoers
jenkins  ALL=(root) NOPASSWD: /usr/sbin/service my-app
Defaults:jenkins !requiretty
```

### 7.6 group 全员 sudo

```sudoers
%sudo  ALL=(ALL:ALL) ALL
```

## 8. /etc/sudoers.d/ 规则

/usr/local/etc/sudoers.d/、/etc/sudoers.d/ 都会自动读到：

```bash
visudo -f /etc/sudoers.d/myapp
```

`#includedir /etc/sudoers.d` 在主文件。文件必须 chmod 0440 / 0444，否则 sudo 警告并跳过。

```bash
ls -la /etc/sudoers.d/
# 必须 0440 或更严
```

## 9. 调试 / 测试

```bash
sudo -l                                     # 本人可用命令
sudo -llU alice                             # 看 alice 可用
sudo -V                                     # 版本
sudo --debug=2 ls                           # 输出调试
strace -f -e trace=execve sudo cmd          # 看 sudo 用了什么
```

错误信息：

| 错误 | 含义 |
| ---- | ---- |
| `incorrect password attempts` | 输错 |
| `user NOT in sudoers` | 不在配置里 |
| `no password for user` | 设了 NOPASSWD |
| `command not allowed` | rule 不允许 |
| `unable to resolve host` | hostname 问题 |

## 10. sudo 自身的日志

- syslog：`/var/log/auth.log` 或 `/var/log/secure`
- io log：`/var/log/sudo-io/<seq>`（设置 `LOG_INPUT` 与 `LOG_OUTPUT`）

```bash
# 监控
sudo journalctl -u sudo
last -f /var/log/wtmp                    # 用户登入记录
last -f /var/log/btmp                    # 失败
ausearch -m SYSCALL -sc execve -i ne     # audit + sudo
```

## 11. 集中认证（NSS / LDAP / SSSD）

```sudoers
# /etc/nsswitch.conf
sudoers: ldap files

# /etc/ldap.conf /etc/sssd/sssd.conf
sudo_provider = ldap
ldap_uri = ldap://ldap.corp.example.com
ldap_search_base = ou=sudoers,dc=corp,dc=com
sudoers_base = ou=sudoers,dc=corp,dc=com
```

`sssd` 守护 sudoers 缓存到本地（默认 30s）。

## 12. CVE 与安全

历史漏洞：

- **CVE-2019-14287**：sudo 1.8.28 之前 `sudo -u -1` 提权（已修）
- **CVE-2019-18684**：sudo 输入缓冲溢出（1.8.31 修）
- **CVE-2021-23240 / 3156** sudoedit 越权编辑（限定 = 修）

加固：

```bash
sudo -V | grep -i 'version'   # 用最新版
```

```sudoers
Defaults    secure_path="..."
Defaults    env_reset
Defaults    always_set_home
Defaults    use_pty
Defaults    log_input
Defaults    log_output
Defaults    iolog_dir=/var/log/sudo-io
Defaults    verifypw=all
Defaults    badpass_message="Sorry."
Defaults    timestamp_timeout=5
```

- `Defaults env_keep` 白名单
- `Defaults !visiblepw` 不给远程登录机会
- `Defaults !authenticate` 高危命令禁用
- `Defaults listpw=all` 看密码过程
- `Defaults targetpw` 单一密码

## 13. doas / opendoas

`doas`（OpenBSD），更简约：

```text
permit nopass alice as root cmd /usr/sbin/service
permit nopass :wheel cmd /bin/ls
```

- `permit [options] identity [as user] [cmd command]`
- 配置文件 `/etc/doas.conf`，uid=0 chmod 0400

适合 personal server。

## 14. polkit

桌面版：

```text
/usr/share/polkit-1/actions/*.policy
```

`.policy` 文件定义动作如 `org.freedesktop.systemd1.manage-units`，pkexec 跑命令。

```bash
pkexec systemctl restart nginx
```

适用桌面交互；sudo 更适合 CLI。

## 15. sudo 与容器 / K8s

容器内 sudo 受：

```bash
sudo unshare -m echo "docker container"
```

- root 在容器内：
  - 通常不需要 sudo（已是 root）
  - 镜像 `USER 0` 时没 sudo
- K8s Pod：
  - `securityContext.privileged: true` + sudo
  - `securityContext.allowPrivilegeEscalation: true` (允许获取 sudo)
  - `securityContext.runAsUser: 1000`

## 16. 实战例子

### 16.1 系统管理员

```sudoers
%admins ALL=(ALL) ALL
%auditors ALL=(root) NOPASSWD: /usr/bin/journalctl -e --, /bin/cat
%release ALL=(root) NOPASSWD: /usr/bin/systemctl restart my-app.service, /usr/bin/systemctl reload nginx.service
```

### 16.2 数据库

```sudoers
%dba  ALL=(postgres) NOPASSWD: /usr/bin/psql, /usr/lib/postgresql/*/bin/pg_*
node  ALL=(root)      NOPASSWD: /usr/bin/systemctl restart postgresql
```

### 16.3 容器 / K8s

```sudoers
%operators  ALL=(root)  NOPASSWD: /usr/bin/docker, /usr/bin/kubectl
```

### 16.4 不带密码的情况

```sudoers
%backup  ALL=(root) NOPASSWD: /usr/bin/rsync, /bin/tar
```

### 16.5 特定 sudoedit

```sudoers
sudoedit.allowfiles = /etc/nginx/nginx.conf, /etc/myapp/*.yaml
alice    ALL=(root) sudoedit /etc/myapp/*.yaml
```

## 17. 一句话总结

```text
sudo = 授权另一个用户跑命令
策略在 /etc/sudoers / /etc/sudoers.d/*，用 visudo 编辑
who where=(as_whom) tag commands
Defaults 设 env_reset / secure_path / log_input / timestamp_timeout
SUID 是 0755 全家伞；sudo -l 看自己可用
兜底：只用最新版 / 设 Defaults / 审计日志
```

## 18. 参考

- `man 5 sudoers`
- `man 8 sudo`
- `man 8 visudo`
- `man sudoers.ldap`
- `man 8 pam_timestamp_check`
- `man 5 doas.conf`
- `man polkit`
- `man pkexec`
- [sudo.ws](https://www.sudo.ws/)
- [Sudo project history](https://www.sudo.ws/history.html)
