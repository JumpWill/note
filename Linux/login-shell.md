# 登陆 shell vs 非登陆 shell

shell 启动时"读什么配置"与"是不是登陆会话"密切相关，与"是不是交互式"是两件事。这篇解释三种分类与它们在不同 shell 下的行为，以及与 umask / PATH / 环境变量等的联动。

## 1. 三种 shell 类型

| 维度 | 含义 |
| ---- | ---- |
| **login shell** | 第一次登录到主机获得的 shell（TTY 登录 / SSH / `su -` / `sudo -i` 等） |
| **non-login shell** | 已登录 shell 之后开启的子 shell，或开新终端时直接启动的 shell |
| **interactive shell** | 提示符、读 stdin、绑 tty，与是否 login 解耦 |
| **non-interactive shell** | 执行脚本时用，没提示符 |

```text
login ──► login shell (1次)
   │
   ▼  ──── interactive non-login ──► gnome-terminal / xterm / 双击 git-bash
   │
   ▼  ──── non-interactive ───────── 跑 .sh 脚本、CI、make 等
```

四种组合：

| login | interactive | 说明 |
| --- | --- | --- |
| ✔ | ✔ | TTY/SSH 登入后默认 |
| ✘ | ✔ | 开 terminal / gnome-terminal |
| ✔ | ✘ | `bash -l -c cmd` / `su -c` |
| ✘ | ✘ | 跑 .sh 脚本、`bash -c` |

## 2. 配置文件加载顺序

### 2.1 bash

| 启动类型 | 配置文件（顺序） |
| --- | --- |
| **login shell** | `/etc/profile` → `/etc/profile.d/*` → `~/.bash_profile`（优先）/ `~/.bash_login` / `~/.profile` |
| **interactive non-login** | `/etc/bash.bashrc` → `~/.bashrc` |
| **non-interactive** | `$BASH_ENV` 指向的文件 |
| **logout** | `~/.bash_logout` |

```bash
# 查看
echo $0                       # -bash → login
shopt login_shell             # 开 / on → login

# 启动方式
bash -l                       # login
bash                          # non-login interactive
bash -c 'echo x'              # non-interactive
```

### 2.2 zsh

| 启动类型 | 配置文件（顺序） |
| --- | --- |
| login | `/etc/zsh/zprofile`, `/etc/zsh/zshrc`, `/etc/zsh/zlogin`, `~/.zprofile`, `~/.zshrc`, `~/.zlogin` |
| interactive non-login | `/etc/zsh/zshrc`, `~/.zshrc` |
| non-interactive | `~/.zshenv`, `/etc/zsh/zshenv` |

zsh 启动文件分得最细：

- `zshenv`：所有登录时常驻变量
- `zprofile`：登入后的环境设置
- `zshrc`：交互式行为（prompt / alias）
- `zlogin`：登入后一次（fnode wise）

### 2.3 ksh

| 启动类型 | 配置文件 |
| --- | --- |
| login | `/etc/profile`, `/etc/kshrc`, `~/.profile` |
| interactive non-login | `/etc/kshrc`, `~/.kshrc` |
| non-interactive | `$ENV` |

### 2.4 fish

| 启动类型 | 配置文件 |
| --- | --- |
| login | `/etc/fish/config.fish`, `~/.config/fish/config.fish` |
| interactive non-login | `/etc/fish/conf.d/*`, `~/.config/fish/conf.d/*` |

### 2.5 dash / sh

| 启动类型 | 配置文件 |
| --- | --- |
| 通常 | `/etc/profile` → `~/.profile` |
| non-interactive | 通常不读任何 rc |

## 3. 启动差异一图

```text
────────────────────────── TTY 登入 ──────────────────────────
   │
   ▼  bash -bash, shell=bash, 0 argv[0]=bash → login_shell=on
       /etc/profile ── /etc/profile.d/*.sh ── ~/.bash_profile
                                                    │
   ┌────────────────────────────────────────────────┘
   │
   ├── ~/.ssh_session ── ssh 中再连
   │      ├ login shell (有 tty)
   │      └ non-interactive (Command mode)
   │
   ├─ $ bash                       child 1
   │    SHLVL=2, shell=bash, login_shell=off
   │    /etc/bash.bashrc → ~/.bashrc
   │
   ├─ $ xterm                      sub-shell for terminal
   │    /etc/bash.bashrc → ~/.bashrc
   │
   └─ $ bash -c 'echo hi'         non-interactive
        ── BASH_ENV
```

`$0`、`SHLVL`、`$BASH_ENV` 是观察关键。

## 4. 区分

```bash
echo $0                       # -bash 含 '-' 表示 login
shopt login_shell             # bash：当前是不是 login
[ -n "$PS1" ] && echo interactive || echo not interactive
who -m                        # 来源（pty name）
echo -n "interactive: "       # 含 i 表示 interactive
case "$-" in *i*) echo yes;; esac
```

POSIX：

```bash
$ [ -n "$PS1" ] && echo 'inter'
inter                          # bash
$ sh           # vi /etc/profile 不读？
```

## 5. SSH / su / sudo 行为

| 命令 | login? | 说明 |
| --- | --- | --- |
| `ssh user@host` | 是 | 视为'用户已登录' |
| `ssh user@host command` | 否 | 跑一条命令，直接 non-login |
| `su user` | 否 | 不重置 env，读 `~/.bashrc` |
| `su - user` | 是 | 加 `-`，登录式 |
| `su -c cmd` | 否 | 跑命令，login 但 interactive 否 |
| `sudo bash` | 否 | 不读目标用户 profile |
| `sudo -i` | 是 | 强制 login shell + 目标用户 HOME |
| `sudo su -` | 通常是 | 走两次 login |
| `script` 命令 | 派生子 login | 模拟 tty |
| `tmux / screen` | 派生 non-login | session 不属于 login |
| `git` 客户端触发 hook | non-interactive | 跑脚本 |

```bash
# 区别体验
su username                # 当前 umask 022 继承？
su - username              # 改 PATH / HOME / USER，读 ~/.profile
sudo bash                  # 仍留原 umask 与 PATH
sudo -i                    # 切到目标用户 home 读 .profile
```

`sudo` 内部 `pam_env` 设 `HOME / SHELL / USER` 等，类似 login 但 UI 不一致：

```bash
sudo -i bash -c 'echo $0; shopt login_shell'
# -bash
# login_shell   on
```

## 6. 环境变量 / umask 跨进程影响

```text
login shell (umask 027)
  │
  ├── $ vim              ← 继承 027
  │     :!touch /tmp/file1   027 决定 mode
  │
  ├── $ nohup myd        ← nohup 不重设 umask，仍 027
  │
  └── $ bash -c 'umask'  ← 027
```

| 场景 | 是否继承原 umask |
| ---- | --------------- |
| `command` 启动子进程 | ✔ |
| `nohup cmd` | ✔ |
| `at / batch` | ✘（被 atd / PAM 设 022） |
| `cron` | ✘（通常 022） |
| systemd service | ✘（systemd Unit UMask） |
| docker 容器 | ✘（镜像 ENTRYPOINT 默认 022） |
| SSH command（`ssh host cmd`） | 通常 ✘ |

umask 是 shell 进程属性，被子进程 `fork` 继承。但"设它"的位置在 login / non-login 中不同：

| 启动类型 | 配置位置 |
| ------ | ------- |
| login | `/etc/profile`、PAM 的 `pam_umask.so`、`/etc/login.defs` `UMASK=` |
| non-login interactive | `~/.bashrc` `umask 022` 等 |
| non-interactive (脚本) | 脚本内 `umask` 命令 |
| systemd 服务 | Unit `UMask=` 字段 |
| K8s Pod | PodSpec `securityContext.fsGroup` 类似 |

详见 [umask.md](umask.md)。

## 7. POSIX 范围

POSIX 标准 shell 行为：

- 登入 shell 读 `getlogin()` 或等价
- 非登入 shell 不读 `/etc/profile`

POSIX 给出"是否登入"的明确机理：

- `argv[0]` 首字符 `-`
- 或者 `-l` 选项
- 或 `--login`

POSIX 上：

- `getconf CS_PATH` 提供 base `PATH`
- 其它 login behavior 留给 shell 实现

## 8. 配置实践

### 8.1 推荐写法

```text
~/.profile           ← 所有 login 类 shell 共享配置
  PATH / umask / locale / ENV

~/.bash_profile       ← bash 专有 + 触发 ~/.profile
  [ -r ~/.profile ] && . ~/.profile
  export EDITOR=vim
  [[ -f ~/.bashrc ]] && . ~/.bashrc   # 仅当 non-login 还需要

~/.bashrc            ← bash interactive 用
  [ -z "$PS1" ] && return
  alias ll='ls -la'
  set -o vi

~/.bash_logout       ← login 退出清理
  clear
  rsync -a ~/.claude ~/.bak
```

### 8.2 zsh 推荐

```text
~/.zshenv           zsh 启动时（任何）
~/.zprofile         login
~/.zshrc            interactive
~/.zlogin           login 后
~/.zlogout          login 退出
```

### 8.3 排错指引

```bash
# 启动时看到 "command not found"
type <command>           # shell 是否能解析
echo $PATH

# 发现"配置没生效"
echo $-                  # options
shopt login_shell
echo $BASH_ENV
echo $ENV
```

## 9. 与 SSH 的互动

### 9.1 sshd 服务端

```text
sshd
   │
   ├── login shell (ForceCommand / Command)
   │     ↓
   │   ForceCommand: 跑命令不进入交互 shell
   │   TTY 显式:
   │     -tt → 强制 tty
   │     -T → 不必 tty
   │
   └── session: subsystem 决定
```

`/etc/ssh/sshd_config`：

- `AcceptEnv LANG LC_*`: 转发 environment
- `ForceCommand`: 强制覆盖 command
- `PermitUserEnvironment`: 用户可导入 env

### 9.2 ssh-agent / ssh-keygen

```bash
ssh-agent bash -i -c 'ssh-add key; ssh user@host'
```

agent 在 non-login shell 里启动，`-c` 限制命令结束 agent。

## 10. cron / 系统服务

### 10.1 cron

cron 启动的 sh 默认**不读** shell rc 文件：

- `cron` daemon 通常跑命令：
  ```bash
  /bin/sh -c 'command'
  ```
- sh 读 `/etc/profile.d` 通常被 busybox / dash 默认装着，bash 在 cron 上读 `BASH_ENV`

可以在：

- `/etc/cron.d/...`
- `/etc/crontab` 顶部加 `BASH_ENV=/etc/profile`

### 10.2 systemd

systemd service 默认 umask 可设：

```ini
[Service]
UMask=0027
User=app
ExecStart=/opt/app/run
```

systemd 不读 `/etc/profile`、不读 `~/.profile`。

### 10.3 K8s Pod

```yaml
spec:
  securityContext:
    fsGroup: 1000
  containers:
    - securityContext:
        fsGroup: 1000
```

不读 shell rc；K8s 用 PodSpec fsGroup 决定 `group` 在容器内的容器目录。

## 11. 容器内 shell

```bash
docker exec -it <ctr> bash            # login_shell=on (有 -it)
docker exec -i <ctr> bash             # interactive 但 no tty
docker exec <ctr> bash -c 'echo hi'   # non-interactive
```

容器内 shell 跟 host 设置：

- `umask` 通常由镜像 `ENTRYPOINT` 设
- `PATH` 通常在 Dockerfile ENV
- LANG / TZ 同 ENV

容器内：

- `/etc/profile` 由 login 程序（PAM）触发
- `non-interactive` 跑脚本不读

## 12. 终端模拟器

| 类型 | 启动 shell |
| ---- | ---------- |
| gnome-terminal / Konsole | 通常 `bash`（non-login） |
| gnome-terminal 设置 "Login shell" 复选框 | `-l`（login） |
| macOS Terminal 默认 | `-bash`（login）+ `-i` (interactive) |
| iTerm2 / 各种终端 | 都支持，但默认不同 |

## 13. 排查思路

```bash
echo $0                                 # login 情况
shopt login_shell                       # bash
case $- in *i*) echo "interactive";; esac

env | grep -E 'PWD|SHLVL|LOGNAME|USER'
who -m

# 列出加载了什么
STRACE -e trace=openat bash -l 2>&1 | grep -E 'profile|bashrc'
```

## 14. 与 umask 的实际关联

| 场景 | umask 默认 |
| ---- | --------- |
| 直接 `su -` | 该用户 ~/.profile |
| TTY 登入 | pam_umask / login.defs / ~/.profile |
| `sudo -i` | 目标用户 ~/.profile |
| `sudo bash` | 当前用户 ~/.bashrc |
| 开 gnome-terminal | 当前用户 ~/.bashrc |
| `docker exec -it` | 镜像 ENTRYPOINT 决定 |
| cron | 大多 022 / 0022 默认 |
| systemd service | Unit UMask 字段 |
| Jenkins / GitLab Runner | 配置脚本显式设 |

## 15. 一句话总结

```text
login shell:     /etc/profile, ~/.bash_profile, ~/.profile
                  → 设 umask / PATH / locale
                  → 一次性加载
interactive:     ~/.bashrc, /etc/bash.bashrc
                  → alias / prompt / function
                  → 每个 terminal 重新加载
non-interactive: $BASH_ENV 指向的文件
                  → 脚本启动时加载
                  → 没用 tty
```

umask "实际值" 在 login shell 阶段就被影响；改 `~/.bashrc` 影响的是新开 terminal；SSH `command` 默认不走 login。

## 16. 参考

- `man 1 bash`、INVOCATION 部分
- `man 1 zsh`、STARTUP/SHUTDOWN FILES
- POSIX IEEE 1003.1-2017, "Shell & Utilities"
- `info bash` "Bash Startup Files"
- Linux kernel: `shell.c` / `user_namespace`
- [Debian wiki: dotfiles](https://wiki.debian.org/DotFiles)
- Bibiled (TLPI) Chapter 6 "Processors"
