# rsync

`rsync` 是 Linux/Unix 下最快的**增量文件同步**工具:本地或远程(ssh)之间复制和同步目录与文件,特点是**只传差异**(delta transfer),在镜像、备份、部署场景几乎无可替代。源自 Andrew Tridgell 1996 年的算法与同名实现。

注意:

- 几乎所有发行版预装;macOS / BSD 也都有
- 与 `cp` 相比:保留权限、时间、链接、稀疏等元数据,支持远程
- 与 `scp` 相比:增量、断点续传、断网可续
- 与 `tar + ssh` 管道相比:免打包,对超大文件友好

## 作用

```text
rsync [options] SRC [USER@]HOST:DEST        # 本地 → 远程
rsync [options] [USER@]HOST:SRC DEST        # 远程 → 本地
rsync [options] SRC DEST                     # 本地 → 本地
rsync [options] SRC rsync://[USER@]HOST/MODULE/DEST    # daemon 模式
```

主要解决:

- 镜像目录(首次全量,之后增量)
- 远程备份与恢复
- 大目录分发(代码仓库、静态资源)
- 文件迁移(机器间 / 跨机房)

## 常见参数

### 1. 常用选项速查

| 参数 | 含义 |
| ---- | ---- |
| `-a` / `--archive` | 归档模式:`-rlptgoD` 组合(最常用) |
| `-v` / `--verbose` | 详细输出 |
| `-z` / `--compress` | 传输时压缩 |
| `-P` | 等价 `--partial --progress`(断点续传 + 进度) |
| `-n` / `--dry-run` | 空跑,不实际改文件 |
| `-r` / `--recursive` | 递归目录(`-a` 已含) |
| `-l` / `--links` | 保留符号链接(`-a` 已含) |
| `-p` / `--perms` | 保留权限(`-a` 已含) |
| `-t` / `--times` | 保留 mtime(`-a` 已含) |
| `-g` / `--group` | 保留所属组(`-a` 已含) |
| `-o` / `--owner` | 保留所有者(需 root,`-a` 已含) |
| `-D` | 保留设备文件与特殊文件(`-a` 已含) |
| `-A` / `--acls` | 保留 ACL |
| `-X` / `--xattrs` | 保留扩展属性 |
| `-H` / `--hard-links` | 保留硬链接 |
| `-S` / `--sparse` | 高效处理稀疏文件 |
| `-x` / `--one-file-system` | 不跨文件系统 |
| `--numeric-ids` | 不映射 UID/GID(root 默认开启) |
| `--delete` | 删除目标中源没有的文件(严格镜像) |
| `--delete-after` | 先传完再删(更安全) |
| `--delete-excluded` | 删除目标中被排除的文件 |
| `--exclude=PATTERN` | 排除匹配(可多次使用) |
| `--include=PATTERN` | 强制包含(可多次使用) |
| `--exclude-from=FILE` | 从文件读排除列表 |
| `--filter=RULE` | 高级过滤规则(`+ / - / H / S / R`) |
| `-e SHELL` | 指定远程 shell,默认 ssh |
| `--partial` | 保留部分传输的文件(断点续传) |
| `--bwlimit=RATE` | 限速 KB/s |
| `--checksum` / `-c` | 用整文件 checksum 判定差异(慢但准) |
| `--size-only` | 只用 size 判定差异 |
| `--inplace` | 直接写到目标位置 |
| `--append` | 追加写,只追加新数据(适合日志) |

### 2. 路径规则(末尾 `/`)

```text
rsync -a src/   dst/        # 复制 src/ 内的内容到 dst/
rsync -a src    dst/        # 复制 src 本身到 dst/src/

远程路径用 : 区分:
rsync -a local/path/ user@host:/remote/path/
```

末尾 `/` 是 rsync 最容易踩的坑:加 `/` 表示"目录内容",不加表示"目录本身"。

## 常用组合

### 1. 本地镜像目录

```bash
rsync -av /data/src/ /data/dst/
```

- `-a`:归档(权限 / 时间 / 链接都保留)
- `-v`:看到文件名

输出:

```text
sending incremental file list
file1.txt
subdir/file2.txt

sent 1,234 bytes  received 56 bytes  total size 1,234,567
```

### 2. 推送到远程(ssh)

```bash
rsync -avz /data/src/ user@host:/data/dst/
```

- `-z`:网络传输时压缩(本地镜像意义不大,远程常用)

### 3. 远程拉取

```bash
rsync -avz user@host:/data/src/ /data/dst/
```

### 4. 严格镜像(删除目标多余)

```bash
rsync -av --delete /data/src/ /data/dst/
```

### 5. 增量 + 进度 + 断点续传

```bash
rsync -avP /data/src/ user@host:/data/dst/
```

### 6. 试运行(dry run)

```bash
rsync -avn --delete /data/src/ /data/dst/
```

任何带 `--delete` 的命令**先 `-n` 试跑**再执行。

### 7. 排除日志与缓存

```bash
rsync -av --exclude='*.log' --exclude='.cache' /src/ /dst/
```

### 8. 从文件读排除列表

```bash
rsync -av --exclude-from=rsync-exclude.txt /src/ /dst/
```

`rsync-exclude.txt`:

```text
*.log
*.tmp
.git
node_modules/
.cache
```

### 9. 限速(白天备份带宽友好)

```bash
rsync -av --bwlimit=5000 /src/ user@host:/dst/   # 5 MB/s
```

### 10. 自定义 ssh 端口 / 密钥

```bash
rsync -av -e 'ssh -p 2222 -i ~/.ssh/id_rsa' /src/ user@host:/dst/
```

### 11. 用 ssh config 中的 alias

```bash
rsync -av /src/ myalias:/dst/
```

`myalias` 是 `~/.ssh/config` 中的 Host 段,无需 `-e ssh`。

### 12. 整文件 checksum 判定(精确但慢)

```bash
rsync -avc /src/ /dst/
```

## 同步语义与路径

### 1. 末尾 `/` 的关键差异

```text
rsync -a /src/   /dst/    # 把 /src 内文件拷到 /dst
rsync -a /src    /dst/    # 把 /src 整个目录拷到 /dst/src
```

### 2. --delete 的几种时机

| 选项 | 行为 |
| ---- | ---- |
| `--delete` | 默认:边传边删 |
| `--delete-before` | 先全部删完再传 |
| `--delete-after` | 先传完再统一删(最安全) |
| `--delete-during` | 边传边删(`--delete` 等价) |
| `--delete-delay` | 类似 after,但保留临时 |
| `--delete-excluded` | 排除的也一并删目标侧 |

`--delete-after` 在备份 / 迁移场景最安全:源端出问题时,目标侧不会被先清空。

### 3. 过滤顺序(include / exclude)

```bash
# 想保留 .git 但排除其它点开头目录
rsync -av \
  --include='.git/***' \
  --include='.gitignore' \
  --exclude='.*' \
  /src/ /dst/
```

rsync 按顺序匹配 `--include` 与 `--exclude`,**先匹配先生效**;`--filter` 用 `+ pattern` 强制 include、`- pattern` 强制 exclude。

## 工作原理

### 1. 增量算法(delta transfer)

```text
1. 把文件切成固定大小块(默认 700 字节起,二分递归)
2. 对每块算 rolling checksum(弱校验,cheap)+ MD5(强校验)
3. 接收端对目标文件算同样 checksum,找差异块
4. 只传差异块;接收端重组
```

代价:双方 CPU 多算一次校验;收益:网络流量极大降低(典型 90%+ 节省)。

### 2. 何时判定"需要重传"

```text
默认按 mtime + size(mtime 一致 + size 一致 → 跳过)
加 -c / --checksum 后:改用整文件 MD5(更准确但更慢)
加 --size-only 后:只看 size(忽略 mtime)
```

### 3. 通信通道

```text
本地:       fork + pipe
远程(默认):ssh (走 stdin / stdout)
daemon 模式:rsync:// 协议,TCP 端口 873
```

```bash
rsync -av /src/ rsync://user@host/module/dst/   # daemon 模式
```

## 与 cp / scp / tar 对比

| 维度 | rsync | cp -a | scp | tar+ssh |
| ---- | ----- | ----- | --- | ------- |
| 增量传输 | 是(块级) | 否 | 否 | 否 |
| 远程 | ssh / daemon | 否 | ssh | ssh |
| 断点续传 | 是(`--partial`) | 否 | 否 | 否 |
| 元数据保留 | 完整(`-a`) | 较完整 | 部分 | 完整 |
| 删除多余 | `--delete` | 否 | 否 | 否 |
| 大文件稀疏 | `-S` | 否 | 否 | 否 |
| 跨主机管道 | 否 | 否 | 否 | 是(流式) |
| 速度(首次) | 中 | 极快 | 较慢 | 慢(打包) |

典型选择:

- 日常镜像:**rsync**
- 一次性快速本地拷:**cp -a**
- 跨主机单文件流式:**scp**
- 一次性打包迁移大目录:**tar -cf - | ssh host tar -xf - -C**

### 1. ssh + tar 管道(适合一次性大目录迁移)

```bash
tar -cf - /src | ssh user@host 'tar -xf - -C /dst'
```

### 2. scp 单文件传输

```bash
scp file user@host:/dst/
```

## 实用场景

### 1. 网站镜像

```bash
rsync -avz --delete /var/www/ backup@web2:/var/www/
```

### 2. 备份用户家目录

```bash
rsync -avz --exclude={'.cache','*.tmp'} /home/user/ backup:/backup/user/
```

### 3. 部署代码

```bash
rsync -avz --delete --exclude='.git' /local/app/ deploy@app:/srv/app/
```

### 4. 保留 hardlink 的快照同步

```bash
rsync -avHP /snapshots/2024-01-01/ /snapshots/2024-01-02/
```

### 5. 大目录 + 限速 + 断点

```bash
rsync -avP --bwlimit=20000 /bigdata/ user@host:/bigdata/
```

### 6. 追加写日志

```bash
rsync -av --append user@host:/var/log/app.log /backup/app.log
```

`--append` 只追加新数据,极快;适合增量收日志。

### 7. daemon 模式(/etc/rsyncd.conf)

```conf
uid = nobody
gid = nogroup
use chroot = yes
max connections = 4
syslog facility = local5
pid file = /var/run/rsyncd.pid

[backup]
    path = /srv/backup
    comment = backup area
    read only = no
    auth users = backup
    secrets file = /etc/rsyncd.secrets
    hosts allow = 192.168.1.0/24
```

```bash
rsync -av /src/ rsync://backup@server/backup/
```

## 退出码

| 退出码 | 含义 |
| ---- | ---- |
| 0 | 成功 |
| 1 | 语法或用法错 |
| 2 | 协议不兼容(两端 rsync 版本差异大) |
| 3 | 文件 IO 错 |
| 4 | 不支持的请求 |
| 5 | 启动协议失败 |
| 6 | 守护进程错误 |
| 10 | socket IO 错误 |
| 11 | socket IO 错误 |
| 12 | 协议数据错误 |
| 13 | 内部错误 |
| 14 | 内存错误 |
| 20 | socket 等待超时 |
| 21 | 等待子进程错误 |
| 22 | 等待守护进程错误 |
| 23 | 文件 IO 错误 |
| 24 | 文件 IO 错误 |
| 25 | 超时 |
| 30 | 大文件传输中 max-delete 限制触发 |

常用判断脚本:

```bash
rsync ... && echo "ok" || echo "fail code=$?"
```

## 注意

- 末尾 `/` 是最常踩的坑——先 `rsync -avn` 试跑看路径
- `--delete` 是**单向删目标**,源端被删前不要乱用;迁移建议加 `--delete-after`
- `-a` 已含 `-rlptgoD`,**不要再加 `-r`**(无影响但冗余)
- 跨主机时间不同步时,别用 mtime 判定差异;改用 `-c`(但慢)
- 大文件 + 多人访问时**不要 `--inplace`**(读到的可能是半截文件)
- 远程 rsync 走 ssh,**两端需有 rsync 二进制**;daemon 模式不需要
- 路径含空格或中文:两端字符集 / 终端要一致,避免乱码
- `--bwlimit` 单位是 **KB/s**
- 大量小文件同步慢:可考虑先 tar 再传(参考 `tar+ssh` 模式)
- `--checksum` 比 `--partial` 重得多:前者全文件 MD5,后者只保留已传部分

## 一句话总结

```text
rsync      = 增量同步首选(本地 / 远程 / daemon)
cp -a      = 本地一次性拷贝,无增量无远程
scp        = 单文件简单传输,无增量无断点
tar + ssh  = 一次性大目录管道迁移
```

常用顺序:

1. `rsync -avn --delete src/ dst/` 试跑,确认要删啥
2. `rsync -avP src/ dst/` 日常同步(进度 + 断点)
3. `rsync -avzP -e 'ssh -p 22' src/ user@host:dst/` 远程
4. 一次性大目录:`tar -cf - | ssh host tar -xf -`

## 参考

- `man rsync`
- `man rsyncd.conf`
- [rsync 官网](https://rsync.samba.org/)
- [rsync 算法原文(Tridgell 1996)](https://rsync.samba.org/tech_report/)
- [rsync 算法中文图解](https://rsync.samba.org/how-rsync-works.html)
