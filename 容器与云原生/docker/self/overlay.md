# overlay 文件系统

## 是什么

OverlayFS 是一种**联合挂载**文件系统（UnionFS），Linux 内核 3.18 开始支持。它能把**多个目录**（多个 layer）合并成一个统一的视图呈现给上层，对外就像一个普通文件系统。

Docker 用它来实现**镜像分层**和**容器读写层**，是镜像分层、docker commit、docker save 的底层支撑。

```text
# 联合挂载：把多个目录的内容"叠"在一起，对上呈现为同一个目录
lowerdir (只读)  ─┐
lowerdir (只读)  ─┤  →  merged (统一视图)  ← 进程看到的就是这个
upperdir (读写)  ─┤
workdir (工作)   ─┘
```

PS:
- Docker 在 Linux 上的 graphdriver 历史上有过 aufs、btrfs、devicemapper、overlay、overlay2，目前**默认且推荐**是 overlay2。
- Windows 上用的是自己的 filter driver，机制不一样，本篇只讲 Linux。

---

## overlay 与 overlay2 区别

| 驱动          | 层级上限 | inode 占用 | 状态         |
| ------------- | -------- | ---------- | ------------ |
| overlay       | 单层     | 双份 inode | **已弃用**   |
| overlay2     | 128 层   | 一份 inode | **推荐使用** |

```shell
# 查看 docker 当前的存储驱动
docker info | grep -i "storage driver"

# 查看 /var/lib/docker/overlay2 下的层
ls /var/lib/docker/overlay2
```

PS:
overlay2 之所以比 overlay 好，是因为它把每一层目录的 inode 复用了，不再像 overlay 那样硬链接一份，所以 inode 占用减半，性能也更好。**生产环境一定要用 overlay2**。

---

## 核心四个目录

overlay2 挂载需要四个目录，理解了这四个目录，原理就懂了一大半：

| 目录       | 别名          | 作用                                   | 读写     |
| ---------- | ------------- | -------------------------------------- | -------- |
| lowerdir   | 镜像层        | 只读的镜像分层，**多个**               | 只读     |
| upperdir   | 容器层        | 容器运行时产生的修改都在这一层         | 读写     |
| workdir    | 工作目录      | 原子性保证用的中转区，**不能删**       | 内部使用 |
| merged     | 合并视图      | 给进程看到的统一目录，挂载点本身       | 表现层   |

```text
挂载关系：
mount -t overlay overlay \
  -o lowerdir=/lower1:/lower2,\
     upperdir=/upper,\
     workdir=/work \
     /merged
```

> 注意 lowerdir 多个时**从右到左**是上层（也就是离 upper 更近），写时复制时优先从最右边的 lower 开始找。

---

## 工作原理：COW（Copy-on-Write）

### 读

1. 先在 upperdir 找，找到直接返回
2. 找不到再去 lowerdir 找（按从右到左的顺序）
3. 合并后的视图就是 merged

### 写（首次修改文件）

1. 把 lowerdir 里的文件**拷贝**到 upperdir（这一步叫 copy-up）
2. 在 upperdir 上做修改
3. 后续的读写都直接走 upperdir

```text
  第一次写                后续写
  ┌──────────┐           ┌──────────┐
  │  lower   │ copy-up   │  lower   │ (不再动)
  │  /a.txt  │ ────────► │  /a.txt  │
  └──────────┘           └──────────┘
                          ┌──────────┐
                          │  upper   │
                          │  /a.txt  │ ← 写这里
                          └──────────┘
```

### 删文件

- 在 upperdir 里建一个**白卡**（character device，major:minor 为 0,0），对上层表现为"文件被删"
- 真正的文件还在 lowerdir 里没动，下次容器删了，删除白卡文件又"恢复"了

```text
# 实际在 upperdir 里看到的是这个
ls -la /var/lib/docker/overlay2/<容器层>/diff/
# c---------  1 root root 0, 0  ...  a.txt   ← 这就是"白卡"
```

### 改目录

目录的 copy-up 比较特殊，要先把这个目录里**所有文件**都从 lower 拷到 upper（递归），再做修改。所以**第一次改一个很大目录时会很慢**。

---

## 在 Docker 中看 overlay

```shell
# 1. 拉一个镜像，看镜像层
docker pull nginx
docker inspect nginx | jq '.[0].GraphDriver.Data'

# 看到类似输出
{
  "LowerDir": "/var/lib/docker/overlay2/xxx/diff:...",
  "MergedDir": "/var/lib/docker/overlay2/yyy/merged",
  "UpperDir": "/var/lib/docker/overlay2/yyy/diff",
  "WorkDir": "/var/lib/docker/overlay2/yyy/work"
}

# 2. 启动容器，对照看一下
docker run -d --name test nginx
docker inspect test | jq '.[0].GraphDriver.Data'

# 3. 进入容器写个文件，再看 upperdir
docker exec test touch /newfile
ls /var/lib/docker/overlay2/<对应 UpperDir>/diff
# 能看到 newfile，这就是容器层
```

```shell
# 自己手动 mount 一个 overlay 玩一下（不依赖 docker）
mkdir -p /tmp/ov/{lower,upper,work,merged}
echo "from lower" > /tmp/ov/lower/a.txt
echo "from upper" > /tmp/ov/upper/b.txt
mount -t overlay overlay \
  -o lowerdir=/tmp/ov/lower,upperdir=/tmp/ov/upper,workdir=/tmp/ov/work \
  /tmp/ov/merged

# 看一下合并效果
ls /tmp/ov/merged
cat /tmp/ov/merged/a.txt   # from lower
cat /tmp/ov/merged/b.txt   # from upper

# 改文件观察 copy-up
echo "modified" >> /tmp/ov/merged/a.txt
ls /tmp/ov/upper/          # a.txt 出现了，lower 里没动

# 清理
umount /tmp/ov/merged
```

---

## 镜像、容器与 overlay 的对应关系

```text
镜像 nginx (多层)
   │
   ├── lowerdir1  (基础层 debian)
   ├── lowerdir2  (apt 安装)
   ├── lowerdir3  (COPY 配置文件)
   └── lowerdir4  (CMD 等元数据)
                ↓
   启动容器时再加一层 upperdir + workdir + merged
                ↓
   容器内所有改动只在 upperdir
                ↓
   docker commit 后，upperdir 就被冻结成新的一个 lowerdir
```

```shell
# 提交容器为镜像
docker commit <container> mynginx:v1
# 这之后，容器的 upperdir 就变成了 mynginx:v1 镜像的一层只读 lowerdir
```

---

## docker 中实际目录结构

```text
/var/lib/docker/overlay2/
├── <layer-id-1>/          # 镜像层1（只读）
│   ├── diff/              # 这一层真实内容
│   ├── link               # 短名软链（避免 mount 参数超长）
│   ├── lower              # 指向父层
│   └── merged/            # 不挂载，文件结构
├── <layer-id-2>/
│   └── ...
└── <container-id>/        # 容器层（读写）
    ├── diff/              # 容器改动
    ├── link
    ├── lower              # 指向上面所有镜像层
    ├── merged/            # 挂载点，容器根文件系统
    └── work/              # 必须存在，不能动
```

PS:
`link` 这个短链文件是为了规避 `mount` 命令行参数长度限制（LOWER_DIR 太多时会超 ARG_MAX），内核会通过 `/proc/self/mountinfo` 自动读 link 文件去拼真实路径。

---

## 性能注意点

| 场景                     | 表现                  | 原因                                       |
| ------------------------ | --------------------- | ------------------------------------------ |
| 第一次写大目录里的文件   | **很慢**              | 触发整目录 copy-up                         |
| inode 很多的镜像         | 慢                    | 合并时元数据操作多                          |
| 层数太多                 | mount 慢              | 内核要把所有 lower 串起来                   |
| 频繁改小文件             | 快                    | copy-up 粒度小                             |
| volume 挂载              | **绕过 overlay**      | bind mount 走的是另一条路，性能好得多       |

```text
# 对比 bind mount 和 overlay 写
docker run -v /host/path:/data ...   # bind mount，写直接落宿主盘
docker run ...                        # 写要经过 overlay 联合挂载，多一跳
```

PS:
- 大量写入（如 MySQL、Redis 的数据目录）**应该挂载 volume**，别让数据进容器层，否则：
  1. 容器层会膨胀
  2. 触发大量 copy-up
  3. 容器删了数据就没了
- 镜像层数尽量少，多阶段构建是最好的实践（参见 [多阶段构建.md](多阶段构建.md)）

---

## 常见问题

##### 磁盘满了

```shell
# 容器层用得最多
docker system df

# 清理
docker system prune -a      # 清理所有未用
docker container prune      # 只清理停止的容器
docker image prune          # 只清理悬空镜像
```

##### 容器层里有大文件但是容器已经删了？

overlay 一旦容器删了，容器层（upperdir）就整个没了。但镜像层里的"白卡"会让某些大文件看起来消失，实则镜像里还在：

```shell
# 看看哪个镜像层最大
docker history --no-trunc <image> | less
```

##### 不要手动改 /var/lib/docker/overlay2 下的东西

任何手动改动都会让 docker engine 认不出这一层，containerd 报错甚至镜像不可用。**所有操作走 docker 命令**。

---

## 容器内 MySQL Buffer Pool 双倍占用

### 现象

跑 MySQL 的容器，`free` 看到可用内存比预期少很多，buffer pool 配的 1G，实际 cgroup 限制内可能吃到 2G+，OOM 提前触发。

```text
# 容器内 free 输出，cached 列特别大
              total    used    free    shared  buff/cache  available
Mem:           2Gi     1Gi    100Mi    0Mi        900Mi     100Mi
                                      ↑↑↑↑↑↑↑↑↑↑↑
                                      这一大块都是 MySQL 数据文件的缓存
```

### 根因：双重缓存

MySQL 同一份数据被缓存了**两次**：

```text
┌────────────────────────────────────────┐
│ MySQL 进程内                            │
│   ┌──────────────────────┐             │
│   │ InnoDB Buffer Pool   │ ← 应用层缓存 │ 1G
│   └──────────────────────┘             │
└────────────────────────────────────────┘
                ↕ read()/write()
┌────────────────────────────────────────┐
│ 内核层                                  │
│   ┌──────────────────────┐             │
│   │ Page Cache           │ ← 文件页缓存 │ 1G（同一份数据）
│   └──────────────────────┘             │
└────────────────────────────────────────┘
                ↕
┌────────────────────────────────────────┐
│ overlay / 文件系统                       │
│   lowerdir / upperdir 的页                │
└────────────────────────────────────────┘
```

在物理机上 MySQL 用 `innodb_flush_method=O_DIRECT` 绕过 Page Cache，就能避免双份。但在 Docker 里**这条路径断了**，因为：

1. **overlay 不是块设备**，`O_DIRECT` 语义在某些版本内核上对 overlayfs 无效
2. 内核仍会把读过的页放进 Page Cache，InnoDB 也仍把自己读过的页留在 Buffer Pool
3. **cgroup 限制的是整容器 RSS + Page Cache**（cgroup v1）—— Page Cache 算进 cgroup 用量，等于 MySQL 在容器视角"用了两遍"
4. `free` 看到的 `available` 不算 cgroup，超用就 OOM

参考 moby issue：<https://github.com/moby/moby/issues/22255>，这个争论从 2015 年吵到现在。

### 怎么验证是不是这个问题

```shell
# 容器内
cat /proc/meminfo | grep -E "Cached|Buffers|Inactive"
# Cached 很大基本就是了

# 看 InnoDB 自己读了多少
mysql> SHOW GLOBAL STATUS LIKE 'Innodb_buffer_pool_read%';
# Innodb_buffer_pool_read_requests / Innodb_buffer_pool_reads 比值高
# 说明大部分读都命中 BP，但 Page Cache 里仍存了一份

# 看不打开文件的方式
mysql> SHOW ENGINE INNODB STATUS\G
# 找 "I/O" 小节，看 read() 系统调用是否走 O_DIRECT
# 容器里大概率不走
```

### 解决方案

按推荐顺序：

| 方案                | 效果      | 适用场景             |
|-----------------------|-------------|--------------------------|
| 数据目录挂 volume| 根治      | 任何数据库          |
| O_DIRECT              | 部分缓解| 物理机/原生块设备|
| cgroup v2             | 准确感知| 新集群                |
| 调小 buffer pool    | 治标      | 临时止血             |
| 裸机或 hostPath    | 完全规避| 有条件时             |

#### 1. 数据目录挂 volume（推荐）

让 MySQL 的数据文件直接落宿主盘或独立卷，**不走 overlay**：

```shell
docker run -d \
  -v /data/mysql:/var/lib/mysql \
  -v /data/mysql-conf:/etc/mysql/conf.d \
  mysql:8.0
```

```text
bind mount 路径
   ↓
宿主盘（ext4/xfs/...）
   ↓
MySQL 直接读写，Page Cache 只缓存一次
```

> bind mount 走 VFS，O_DIRECT 重新生效，Page Cache 跟 BP 不再重复。

#### 2. cgroup v2 让 cgroup 真正感知 Page Cache

cgroup v1 把容器 RSS 和 Page Cache 分开统计但**限制到一起**，所以 Page Cache 涨会顶掉 BP。v2 的 `memory.current` 把它们合并算，OOM 更准确，但**双份缓存本身没解决**。

```shell
# 启用 cgroup v2（systemd）
systemd-resolve --status | grep -i cgroup
# 看 cgroup2 那一行

# 容器内查实际内存压力
cat /sys/fs/cgroup/memory.peak
cat /sys/fs/cgroup/memory.current
```

#### 3. 如果实在没法挂 volume

```ini
# my.cnf 调小点，给 Page Cache 留空间
[mysqld]
innodb_buffer_pool_size = 512M       # 配额的 50% 左右
innodb_flush_method = O_DIRECT       # 在容器里不一定生效，但开着没坏处
innodb_log_file_size = 256M
```

```shell
# 同时给容器多预留点内存上限
docker run -m 4g ...   # 而不是按 BP 1:1 配
```

### 一句话总结

> **数据库类容器，数据目录必须挂 volume，不进 overlay。** 这样 O_DIRECT 生效，Page Cache 和 Buffer Pool 不再重复缓存，cgroup 限制才准。

---

## 参考

- <https://docs.docker.com/storage/storagedriver/overlayfs-driver/>
- <https://www.kernel.org/doc/html/latest/filesystems/overlayfs.html>
- <https://docs.kernel.org/filesystems/overlayfs.html>
- <https://github.com/moby/moby/issues/22255> (O_DIRECT + overlay 的根源讨论)
