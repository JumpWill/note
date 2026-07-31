# inode

inode 是 Linux 文件系统为每一个文件 / 目录分配的索引节点（index node）。每个 inode 记录文件的元数据（除文件名外的信息），并指向数据块，**文件名只是目录里的条目，记录"这个名字对应哪个 inode"**。

## 1. 概念与定位

### 1.1 文件的两条轴

```text
文件名 / 路径  ──────────► inode 表项 ──────────► 数据块
   (dir entry)         (元数据 + 指针)          (block content)
```

- 文件名 + 所在目录：保存在父目录的目录项里
- 元数据：保存在 inode 表项里
- 数据内容：保存在数据块（block）里

### 1.2 inode 存什么

| 字段 | 含义 |
| ---- | ---- |
| **type** | 文件类型（普通文件 / 目录 / 符号链接 / 设备...） |
| **mode / perm** | 权限位（rwxrwxrwx / setuid / sticky） |
| **UID / GID** | 所属用户 / 组 |
| **size** | 文件字节数（目录 4096 起、大文件可能是 indirect block） |
| **atime / mtime / ctime** | 访问 / 修改 / 改变时间 |
| **link count** | 硬链接计数 |
| **block count** | 占用的数据块数 |
| **i_blocks** | 文件块总字节数（512B 单位） |
| **i_flags / i_flock** | 一些标志 / 文件锁 |
| **data pointer / block map** | 数据块位置（直接 / 间接 / 双重间接） |
| **extended attribute** | xattr |
| **generation** | NFS 用，文件身份 id |

### 1.3 inode 不存什么

- 文件名（**重读**：文件名是目录条目，目录项指向 inode）
- 文件内容（数据块）

## 2. inode 数量

### 2.1 创建时决定

inode 总数在 **文件系统格式化（mkfs）** 时被一次性决定，**不能动态扩容**（除非重新格式化和迁移）。

```text
mkfs.ext4 /dev/sdb1
mkfs.ext4 -N <count> /dev/sdb1   # 显式指定 inode count
mkfs.xfs /dev/sdb1
mkfs.btrfs /dev/sdb1
```

- ext4：默认按每 N KB 1 个 inode（mkfs 选项 `-i bytes-per-inode`）
- xfs：动态分配（通常不耗尽）
- btrfs：动态分配
- zfs：动态分配

### 2.2 inode 比例经验

| 文件系统 | 默认比例 | 说明 |
| -------- | -------- | ---- |
| ext4 | 16 KB / inode | 大量小文件偏紧，可指定 `-i 4096` |
| xfs | 动态 | 不会耗尽 inode |
| btrfs | 动态 | 通过 metadata cache |
| tmpfs | 内存 | 通常无限 |

## 3. 查询 inode 状态

### 3.1 df -i（最常用）

```bash
df -i
```

输出：

```text
Filesystem     Inodes  IUsed   IFree   IUse%   Mounted on
/dev/sda1       939K   124K   815K    14%    /
/dev/sdb1      6.0M   8.2K   6.0M     1%    /data
tmpfs           986K      4   986K     1%    /run
```

- IUse% 接近 100 时，再创建文件会报 "No space left on device"，但磁盘空间还有
- 注意：是 inode 而非 disk 满

### 3.2 看具体文件 / 目录的 inode

```bash
ls -li
```

输出：

```text
4718593 -rw-r--r-- 1 root root  4096 Jan 1  2024 init.d
4718592 drwxr-xr-x 2 root root  4096 Jan 1  2024 logs
```

第一列 = inode 号。第一行单个文件 inode 号。

### 3.3 stat（inode 字段详情）

```bash
stat /etc/passwd
```

输出：

```text
File: /etc/passwd
Size: 1234            Blocks: 8          IO Block: 4096   regular file
Device: 801h/2049d      Inode: 6553681    Links: 1
Access: 0644/-rw-r--r--  Uid: 0/root      Gid: 0/root
Access: 2024-05-01 10:00:00.000000000 +0800
Modify: 2024-05-01 09:00:00.000000000 +0800
Change: 2024-05-01 10:00:00.000000000 +0800
```

### 3.4 全局统计

```bash
cat /proc/sys/fs/inode-state
cat /proc/sys/fs/file-max
cat /proc/sys/fs/inode-max
```

`/proc/sys/fs/` 下还有 `file-nr`（当前打开文件数），`inode-nr` / `inode-state`。

### 3.5 按目录统计占用

```text
# 找出最多文件的目录
find / -xdev -type d -exec sh -c 'ls -1 "$1" | wc -l | tr -d "\n"; echo "  $1"' _ {} \; | sort -rn | head -20
```

或者：

```bash
find /var -type f | wc -l
find /var -type f -printf '%h\n' | sort | uniq -c | sort -rn | head -20
```

### 3.6 找"大文件数 / 小文件"目录

```bash
# 列出前 10 inode 占比最高目录
find / -xdev -printf '%h\n' 2>/dev/null | sort | uniq -c | sort -rn | head -10
```

-xdev 不跨越文件系统，避免被 /proc /sys 撑爆。

### 3.7 du 命令的特殊性

`du` 默认按 block 计算占用大小，**不会把每个 inode 都占用列出来**；如果关心 inode 占用，应该用 `find ... | wc -l`。

## 4. inode 耗尽的现象

### 4.1 经典错误

```bash
$ touch /var/test.txt
touch: cannot touch '/var/test.txt': No space left on device
```

但同时 `df -h` 显示还有空间 → 99% 是 inode 耗尽。

### 4.2 应用侧表现

| 应用 | 表现 |
| ---- | ---- |
| Nginx | 写日志报 ENOSPC |
| Crontab | 新建任务失败 |
| Docker | 创建容器 / pull 镜像失败 |
| Mail | 临时文件无法创建 |
| session / cache | 程序内部异常退出 |

### 4.3 进程级提示

`dmesg | grep -i no space` 显示 kernel 报错：

```text
VFS: Out of inodes.
```

`/var/log/messages`：

```text
OSError: [Errno 28] No space left on device: '/var/cache/...'
```

## 5. inode 耗尽的原因

1. **大量小文件**：邮件 queue、session 缓存、logrotate 失败产生的小文件
2. **删除失败**：NFS / Docker 容器或被 handle 打开的文件仍占 inode
3. **意外递归**：脚本循环 delete 但读取失败堆积
4. **小文件系统 + 默认 inode 比例低**：ext4 在小空间下默认总数较少
5. **tmpfs / 容器内**：进程重启期累积的临时 inode
6. **replication 残留**：复制过程残留的小文件

## 6. 解决方案

### 6.1 临时腾出

```bash
# 找出占用最多 inode 的目录
df -i /                    # 看整体比例
du --inodes -d 1 /var      # 看每目录 inode 数（GNU du）
find /var -xdev -maxdepth 6 \
     -printf '%h\n' | sort | uniq -c | sort -rn | head
```

### 6.2 批量删除无用小文件

```bash
# 老 session（>7 天）
find /var/lib/php/sessions -type f -mtime +7 -delete

# 老 logrotate 备份
find /var/log -type f -name "*.gz" -mtime +30 -delete

# 老邮件队列
find /var/spool/postfix/maildrop -type f -mtime +3 -delete

# Docker 中间产物
docker system prune -af
docker volume prune -f

# 容器孤儿
docker container prune -f
```

`xargs -r rm` + `find ... -print0` 大文件安全：

```bash
find /var/cache -type f -size +500M -name "*log*" -print0 \
  | xargs -0 -r rm -f
```

### 6.3 处理打开但已删除的文件

```bash
lsof +L1 | head
```

`+L1` 显示 link count 已为 0 但还有进程打开的文件 → 通过重启服务 / kill 进程释放 inode。

### 6.4 减少特定目录的文件数

- 设置 `session_save_path` 到独立设备
- 配置 `max-file` / logrotate 压缩 + 删除
- 容器使用镜像 slim 化

### 6.5 永久：迁出 + 重新格式化

```bash
# 1. 备份
dump / restore / rsync / cp / 重新 dd

# 2. 重新格式化为 inode 更大的文件系统
mkfs.ext4 -i 4096 /dev/sdb1

mkfs.ext4 -N <自定义数量> /dev/sdb1   # 直接指定总 inode 数

# 3. 修改 /etc/fstab
UUID=xxxx  /data  ext4  defaults  0 2

# 4. 恢复数据
```

或迁移到 **XFS / btrfs / zfs**：

```bash
mkfs.xfs /dev/sdb1     # XFS 动态 inode，几乎不耗尽
mkfs.btrfs /dev/sdb1   # Btrfs 也动态
```

### 6.6 容器内 inode 限制

```bash
docker run --ulimit nofile=65536 ...
# K8s Pod 用 fsGroup + PodSpec 限额
```

Docker 容器根文件系统通常是 overlayfs + 镜像，对 inode 同样有上限。

### 6.7 文件级应用

- `mailman` / `postfix` queue 限制
- `redis` 用 maxmemory
- 数据库日志归档策略
- `XDG_CACHE_HOME` 与日志量限制

### 6.8 监控 + 阈值报警

```bash
# 通过 cron + 邮件报警
df -iP | awk 'NR>2 {print $1, $5}' | while read fs pct; do
  if [ ${pct%\%} -gt 90 ]; then
    echo "Warning: $fs inode usage $pct%"
  fi
done
```

集成 Prometheus：`textfile_collector` + `node_exporter`，或者 `cadvisor` for K8s Pod。

## 7. inode 与硬链接 / 软连接

### 7.1 硬链接

```bash
ln /etc/hosts /tmp/hosts.hard
```

- 同一 inode + 1 link
- link count 增至 2
- 一个删除，另一个仍可访问

### 7.2 软连接

```bash
ln -s /etc/hosts /tmp/hosts.soft
```

- 是 inode 上"符号链接"类型（文件内容是目标路径字符串）
- 占用 1 个 inode（元数据很小）
- 删除原文件后，软链失效

### 7.3 强调

inode 数量 = 普通文件 + 目录 + 软链接 + 设备文件 + 套接字等都算。所以：

- 软连接也会占 inode
- 删除一个目录，等于删除 1 个目录 inode + 它里面所有文件 / 子目录

## 8. inode 与 /proc / sys

虚拟文件系统也消耗内核 inode：

| 文件系统 | 说明 |
| -------- | ---- |
| procfs | /proc 每个项目 |
| sysfs | /sys 每个项目 |
| tmpfs | 内存临时文件 |
| cgroupfs | /sys/fs/cgroup/... |

这些是动态分配 inode，理论不耗尽。但若某 cgroup 限制严格，仍可能有问题。

## 9. 重现 / 演练

### 9.1 模拟小设备

```bash
truncate -s 32M /tmp/img
mkfs.ext4 -i 8192 /tmp/img   # 强制少 inode
mkdir /mnt/img
mount -o loop /tmp/img /mnt/img
df -i /mnt/img
```

### 9.2 充满 inode

```bash
for i in $(seq 1 100000); do touch /mnt/img/$i; done
df -i /mnt/img

touch /mnt/img/x
# cannot touch 'x': No space left on device
df -h /mnt/img  # 还有空间！
```

可以用来做压测、scaling 测试。

## 10. 与其他上限的区分

| 上限 | df 选项 | 表象 |
| ---- | ------- | ---- |
| disk space | `df -h` | `No space left on device` |
| inode | `df -i` | `No space left on device` |
| xattr / xattr 大小 | 系统 | EINVAL / E2BIG |
| 文件描述符 | `ulimit -n` | `Too many open files` |
| process | rlimit | `Cannot fork` |
| 内存 / 卷组 | kernel | ENOMEM |

排错时一查一消除：

```bash
df -h        # 磁盘
df -i        # inode
ulimit -n    # fd
free -m      # 内存
```

## 11. 一句话总结

```text
文件名＝目录条目，inode＝元数据＋数据指针
inode 比例用 df -i 看，耗尽就 touch 不出文件
清理无用小文件 / 重新格式化为 inode 多的比例 / 迁到动态 inode 文件系统（xfs / btrfs / zfs）
```

## 12. 参考

- `man stat(2)`
- `man inode(7)`
- `man df(1)`、`man du(1)`
- Linux kernel `Documentation/filesystems/ext4/`
- `tune2fs -l /dev/sdX` 查看 ext 文件系统 inode 数量与使用
- `mkfs.ext4 -i bytes-per-inode`：inode 比例
- `find ... -print0 ... xargs -0`：安全删除大文件
- Kernel: `fs/inode.c`、`fs/ext4/ialloc.c`（ext4 inode 分配）
- [Linux ext4 inode allocation](https://ext4.wiki.kernel.org/index.php/Articles/Inode)
- [Linux inode limit (Google SRE)](https://www.brendangregg.com/blog/2024-sre-ebook.html)（扩展阅读）
