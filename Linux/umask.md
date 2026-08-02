# umask

umask（user file-creation mask）控制**新文件 / 目录的默认权限**。本质是"不希望新文件默认拿到的那几位"。

## 1. 基本

```bash
$ umask
0022

$ umask -S
u=rwx,g=rx,o=rx
```

新文件权限 = `base permission & ~umask`

| 类型 | base | 解释 |
| ---- | ---- | ---- |
| 目录 | 0777 | 全开放 |
| 文件 | 0666 | 默认不可执行 |

```text
umask = 022
目录默认: 0777 & ~022 = 0755 → rwxr-xr-x
文件默认: 0666 & ~022 = 0644 → rw-r--r--

umask = 002
文件默认: 0666 & ~002 = 0664 → rw-rw-r--
目录默认: 0777 & ~002 = 0775 → rwxrwxr-x
```

## 2. 命令

```bash
umask                      # 显示当前 umask（八进制）
umask -S                   # 显示符号形式
umask -p                   # 输出可 shell eval 形式（像 mask 022）
umask <mask>              # 设新值（当前会话）
umask u=rwx,g=,o=         # 符号式
umask -R u=rwx,g=,o= ...  # root 设置用户全部 umask
```

## 3. 几种常见 umask

| umask | 文件 | 目录 | 常见场景 |
| ----- | ---- | ---- | -------- |
| 0022 | 644 | 755 | 系统 / root 默认 |
| 0002 | 664 | 775 | 协作组 |
| 0077 | 600 | 700 | 用户私人目录 |
| 0027 | 640 | 750 | 多用户开发机 |
| 0007 | 660 | 770 | 组内多用户 |
| 0000 | 666 | 777 | 完全开放（一般不要） |

```bash
umask
# 022

# 改临时会话
umask 077
touch .private
ls -l .private
# -rw------- 1 root root  ...   ← 私人

# 永久：写在 ~/.bashrc / ~/.profile / /etc/profile
```

## 4. 系统默认值

- Linux / Unix 多数发行版：root `0022`、用户 `0002`（Ubuntu 部分）/ `0022`
- 检查 / 改：

```bash
cat /etc/profile      # umask 022
cat /etc/login.defs   # USERGROUPS_ENAB yes → 创建同名组
cat /etc/pam.d/*      # pam_umask 模块
```

Debian 系：

```bash
# /etc/login.defs
UMASK           077
USERGROUPS_ENAB yes
```

CentOS / RHEL：

```bash
# /etc/profile
umask 022
```

Ubuntu 用户登录：

```bash
$ grep -R 'UMASK' /etc/login.defs
UMASK 027
```

## 5. pam_umask

很多发行版用 PAM (`pam_umask.so`) 设置 login shell：

```bash
# /etc/pam.d/login
session optional pam_umask.so umask=077
```

PAM 会按以下优先级决定 umask：

1. 优先级 1：`/etc/pam.d/login` 中显式参数
2. 优先级 2：`UMASK=xxx` 取自 /etc/login.defs
3. 优先级 3：USERGROUPS_ENAB + primary group 反算
4. 优先级 4：`/etc/profile` 等 shell 启动脚本
5. 优先级 5：默认 022

## 6. umask 与特殊位

新文件 / 目录创建时：

- 不带 SUID / SGID / sticky
- 只用 base & ~umask

```text
umask=022
目录默认: rwxr-xr-x  ← 没有 SGID
文件默认: rw-r--r--  ← 没有 SUID
```

`umask` 不"复制"父目录的"特殊位"，但 SGID 在父目录上**确实**会让新建子目录继承 group 与 SGID：

```bash
mkdir /opt/project
chmod 2775 /opt/project
mkdir /opt/project/sub
ls -ld /opt/project/sub
# drwxrwsr-x   ← SGID 继承自父目录
```

## 7. 文件创建 vs chmod 之后

```bash
umask 077
touch foo
ls -l foo
# -rw-------    ← 因为 & ~077 = 600
chmod 644 foo
ls -l foo
# -rw-r--r--    ← 改不受 umask 限制
```

umask 只对新创建时生效；对已有文件 chmod 不受影响。

## 8. 进程级 / 子进程

每个进程都有自己的 umask：

- 子进程继承父进程 umask
- `fork` 时复制

```bash
bash
  $ umask 077
  bash
    $ umask        # 077，继承
    $ touch bar
    exit

  $ umask            # 077
```

```c
#include <sys/stat.h>
mode_t old = umask(0);
int fd = open(..., CREAT, 0644);
umask(old);
```

API：

- `umask()` / `umask(2)` syscall
- C：`#include <sys/stat.h>` `mode_t old = umask(new);`

## 9. cp / mv / tar / rsync 的 umask 处理

| 命令 | umask 影响范围 |
| ---- | -------------- |
| `cp` | 受当前 umask 限制 |
| `cp -p` | 保留源 mode（不改） |
| `cp --no-preserve=mode` | 强制覆盖 |
| `mv` | 不创建新文件，保持原 mode |
| `tar cf` | 受创建 umask 限制 |
| `tar xf` | 反序列化时应用到当前用户 umask |
| `install -m 755 src dst` | 显式 mode，覆盖 umask |
| `rsync --chmod=u+rw` | 显式修改 |

`cp -p src dst`：

- 保留 mode 时不再受新 umask 影响

`install` 命令本身可以指定 mode：

```bash
install -m 755 -d /opt/app
install -m 644 -t /etc/app/ file
```

## 10. 文件描述符 / O_CREAT

编程中：

```c
fd = open(path, O_WRONLY|O_CREAT, 0644);
```

实际 mode = `0644 & ~umask`。

NGINX/HTTP server 默认 644：

```c
open(...) & ~023  -> 默认更严
```

## 11. 粘性目录 / mkdir 默认

```bash
mkdir foo
ls -ld foo
# drwxr-xr-x  默认 0755

mkdir -m 0755 foo     # 同上
mkdir -m 0777 foo     # 777
```

注意：

- `mkdir` 默认 mode 是进程 oumask 决定
- 加 `-m` 是显式 mode，再被 umask 影响
- 加 `-p` 处理父目录

## 12. setuid 程序影响

特殊权限（如 SUID）+ umask 顺序：

```text
file created with 0755 umask 022
  - 实际 mode = 0755 & ~022 = 0744  ← S 仍生效，但 # 不可执行
```

实际上 创建时若显式给了 mode 数组，**仅** `mode & ~umask`。SUID 位不能跨进程"父 → 子"继承。

## 13. 抓出新文件应该是什么

```bash
mkdir dir  # 默认 0755

cat > /etc/profile.d/umask.sh <<'EOF'
umask 027
EOF
```

注：

- `dot files` 默认 0644（多数），umask 022 时
- 与 shell `dotglob` 选项无关

## 14. 几个常见误区

### 14.1 umask 是"赋值" 而不是"屏蔽"

- 错误：`umask 064` 等同于 `chmod 064`
- 正确：`umask 064` 是"新文件权限 = 0666 - 064 = 0600"，结果是 `0600`

### 14.2 与 chmod 同步

`umask` 只管新建，不影响 chmod / chown 操作后的模式。

### 14.3 与 daemon / 服务进程

服务进程（systemd）通常默认 umask=0022，运行时可能根据 EnvironmentFile 配置变化。

```bash
# /etc/systemd/system/foo.service
[Service]
UMask=0077
User=app
```

### 14.4 SUID 处理

```bash
mkdir foo
chmod 4755 foo                  # 这是 chmod，与 umask 无关
```

SUID / SGID / sticky 一定不要被新建过程影响。

### 14.5 容器 / K8s 安全基线

K8s Pod 可设 securityContext：

```yaml
securityContext:
  fsGroup: 1000
  defaultMode: 0400    # 文件
  defaultMode: 0750    # 目录
```

容器镜像默认 umask 可通过 ENTRYPOINT 或 Dockerfile 修改：

```dockerfile
RUN echo "umask 027" > /etc/profile.d/umask.sh
```

## 15. 网络服务 / 临时文件

### 15.1 /tmp

`/tmp` 通常 1777 sticky + 0777。

### 15.2 服务运行临时文件

```bash
mkdir -p /run/myapp
chown app:app /run/myapp
chmod 0750 /run/myapp
```

`/run` 默认 tmpfs。

### 15.3 /var/cache

`/var/cache/<pkg>` 通常 0755。

## 16. 实战例子

### 16.1 私人目录

```bash
umask 077
cd /tmp
mkdir secret
echo "thing" > secret/x
ls -ld secret secret/x
# drwx------ root root
# -rw------- root root
```

### 16.2 协作目录

```bash
groupadd team
mkdir -p /opt/proj
chown root:team /opt/proj
chmod 2775 /opt/proj
umask 002

# 组成员创建文件自动 = 组 + rw-rw-r--
```

### 16.3 检查新建时

```bash
(umask; touch test_$$
ls -l test_$$ 
rm test_$$) 2>/dev/null
```

### 16.4 调试 umask 来自 PAM 还是 Profile

```bash
echo $'umask\nid' >> /tmp/login_test
chmod +x /tmp/login_test
```

## 17. 与其他工具的关系

### 17.1 监督 umask

- `Lynis` 安全合规检查
- `auditd` 监听 chmod / setuid

```bash
ausearch -m SYSCALL -sc chmod
```

### 17.2 ACL ACL vs umask

`setfacl -d -m u::rwx,g::rx,o::rx /dir`：ACL 默认 ACL 会**覆盖 umask**。

`POSIX ACLs` 在 dir 上有 `default ACL` 时，新建文件 / 子目录继承该 ACL，且不再使用 umask。

> 例外：default ACL 与 umask 都存在的复杂情形：

```bash
mkdir test
setfacl -m u::rw,u:bob:r,g::rw,o::- test    # o:- 移除 other 权限
touch test/x
# 此时 x 文件继承 default ACL，umask 仅对 "没有 default ACL" 起作用
```

### 17.3 file(1) 命令

`file` 探测类型 与 umask 无关。

## 18. 多 shell 行为

| Shell | umask 显示 | 配置 |
| --- | --- | --- |
| bash | `umask` | /etc/profile, ~/.bashrc |
| zsh | `umask` | /etc/zsh/zshrc, ~/.zshrc |
| tcsh | umask | ~/.cshrc |
| fish | `umask` | ~/.config/fish/config.fish |
| ksh | `umask` | ~/.kshrc |
| dash | `umask` | /etc/profile |

```bash
# ~/.zshrc
umask 022
```

## 19. 一句话总结

```text
umask = 新文件创建时要去除的权限位
默认 022 → 文件 644、目录 755
umask 077 → 文件 600、目录 700 （私人）
umask 002 → 文件 664、目录 775 （协作组）
```

## 20. 参考

- `man 1 umask`
- `man 2 umask`
- `man 1 chmod`
- `man 5 login.defs`
- `man 5 pam_umask`
- Linux `Documentation/userspace-api/credentials.rst`
- [POSIX umask](https://pubs.opengroup.org/onlinepubs/9699919799/utilities/umask.html)
- The Linux Programming Interface (TLPI) Chapter 15
