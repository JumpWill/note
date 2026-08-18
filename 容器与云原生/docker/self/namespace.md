# Linux Namespace

## 是什么

Linux Namespace 是内核用来**隔离系统资源**的机制。同一台机器上不同 namespace 里的进程看到的是**独立的全局资源**——各自的 PID、各自的网络栈、各自的 mount 树、各自的 hostname……

```text
没 namespace 的世界：                   有 namespace 的世界：
所有进程共享一份全局资源                每个 namespace 是一份独立资源视图
┌────────────────────────┐             ┌─────────┐ ┌─────────┐ ┌─────────┐
│ PID 1  init            │             │ ns A    │ │ ns B    │ │ ns C    │
│ PID 2  kthreadd        │             │ PID 1   │ │ PID 1   │ │ PID 1   │
│ PID 3  ...             │             │ PID 2   │ │ PID 2   │ │ PID 2   │
│ 同一棵进程树            │             │ 独立树   │ │ 独立树   │ │ 独立树   │
│ 同一个 /proc            │             │ 独立 /   │ │ 独立 /   │ │ 独立 /   │
└────────────────────────┘             └─────────┘ └─────────┘ └─────────┘
```

> **核心思想：让"看起来像独立操作系统"，本质上是同一个内核在做权限/视图的隔离。**

Docker / LXC / Podman / K8s 容器都靠它做隔离（K8s 还加了 cgroup 限制资源）。

## 全部类型（Linux 5.x 共 8 种）

| 类型 | 作用 | 版本 | 隔离 |
| ---- | ---- | ---- | ---- |
| mount | 挂载 | 2.4.19 | 文件系统 |
| uts | 主机 | 2.6.19 | hostname |
| ipc | IPC | 2.6.19 | 进程通信 |
| net | 网络 | 2.6.24 | 网络栈 |
| pid | 进程 | 2.6.24 | 进程号 |
| user | 用户 | 2.6.23 | UID 映射 |
| cgroup | cgroup | 4.6 | 资源限制 |
| time | 时钟 | 5.6 | 时间 |

```shell
# 查看当前进程的 namespace 列表
ls -l /proc/self/ns/

# 输出示例（数字是 inode 号）
lrwxrwxrwx mnt -> mnt:[4026531840]
lrwxrwxrwx uts -> uts:[4026531838]
lrwxrwxrwx ipc -> ipc:[4026531839]
lrwxrwxrwx net -> net:[4026531992]
lrwxrwxrwx pid -> pid:[4026531836]
lrwxrwxrwx user -> user:[4026531837]
lrwxrwxrwx cgroup -> cgroup:[4026531835]
```

> 同一种类型的 namespace，多个进程可以属于**同一个**（inode 号相同）。inode 号 = namespace 的"身份证"。

PS:
- 不同类型的 namespace **互不嵌套**，是平行关系
- 同一类型的 namespace 之间**没有父子关系**（除了 user 和 pid 有"创建者-被创建者"概念）
- 当一个 namespace 里**最后一个进程退出**时，namespace 本身也被销毁（user 和 pid 例外）

## 三个核心系统调用

```c
// 1. 创建新 namespace（让子进程在新的 ns 里启动）
clone(CLONE_NEWNS | CLONE_NEWUTS | ..., child_func);

// 2. 把当前进程移到已有的 namespace
setns(fd, CLONE_NEWNET);

// 3. 把当前进程的部分资源 unshare（脱离共享）
unshare(CLONE_NEWNS);
```

| 调用 | 用途 | 典型场景 |
| ---- | ---- | -------- |
| `clone` | 创建子进程 + 新 namespace | 容器启动（docker/containerd） |
| `unshare` | 当前进程脱离共享、创建新 namespace | 调试、临时隔离 |
| `setns` | 加入已存在的 namespace | nsenter、调试容器内部 |

PS:
三个调用是 namespace 编程的基础，Docker daemon 通过 `clone(CLONE_NEWNS|CLONE_NEWUTS|...|CLONE_NEWPID)` 拉起容器进程。

## 自己玩一下 namespace

### 用 `unshare` 开个新 shell

```shell
# 创建一个新 mount namespace，pid namespace，uts namespace
sudo unshare --mount --pid --uts --fork /bin/bash

# 此时
ps -ef
#   PID TTY          TIME CMD
#     1 pts/0    00:00:00 bash      ← PID 重新从 1 开始
hostname mycontainer
hostname                              # 改的只是本 namespace 的 hostname
# mycontainer
exit                                   # 退出后，外部宿主一切照旧
```

### 用 `nsenter` 进入另一个进程的 namespace

```shell
# 查看某进程的 namespace
ls -l /proc/<pid>/ns/

# 进入目标进程的所有 namespace
sudo nsenter -t <pid> -m -u -i -n -p -- /bin/bash

# 只进网络 namespace（最常用）
sudo nsenter -t <pid> -n -- ip addr
```

nsenter 选项：

| 选项 | 含义 |
| ---- | ---- |
| `-t pid` | 目标进程 PID |
| `-m` | mount ns |
| `-u` | uts ns |
| `-i` | ipc ns |
| `-n` | net ns |
| `-p` | pid ns |
| `-U` | user ns |
| `-C` | cgroup ns |
| `-r DIR` | 设置根目录 |
| `-w DIR` | 设置工作目录 |

### 持久化 namespace

`/proc/PID/ns/XX` 是**软链到 namespace inode**。把这个软链 bind mount 到一个文件，那个文件就成了 namespace 的"句柄"，可以脱离原进程独立存在：

```shell
# 把当前 net namespace 持久化
touch /var/run/netns/mynet
mount --bind /proc/self/ns/net /var/run/netns/mynet

# 即使原进程退出了，mynet 还在
ls -l /var/run/netns/mynet

# 别的进程可以 setns 加入
sudo nsenter --net=/var/run/netns/mynet ip addr
```

> 这就是 `ip netns add` 的底层实现：每个 netns 就是个 bind mount 的文件。

## 嵌套 namespace

namespace 之间**没有继承关系**（除了 user namespace 特殊）：

```text
正确理解：
   进程 A 创建 ns1
   进程 B 用 setns 进入 ns1
   进程 C 在 ns1 里 clone 创建子进程 → 子进程仍在 ns1，但子进程可以再创建 ns2

   关系是 "共享"，不是 "父子树"
```

特殊点：
- **user namespace** 是**所有**其他 namespace 的"前置条件"：没建 user ns 就建不了其他 ns（unprivileged user 角度）
- **pid namespace** 有"父子"关系：父 namespace 看到的子 ns 的进程号是个"代理"
- 其他类型一律平级

## Docker / K8s 中的 namespace

```shell
# docker run 本质就是 clone() 拉一个进程，传入 N 多个 CLONE_NEW*
docker run -it --rm alpine sh

# 看这个容器进程的 namespace
PID=$(docker inspect -f '{{.State.Pid}}' <container>)
ls -l /proc/$PID/ns

# mnt -> mnt:[4026532589]   ← 独立 mount ns（overlay 挂载就在这里）
# net -> net:[4026532680]   ← 独立 net ns（veth 一端在这）
# pid -> pid:[4026532681]   ← 独立 pid ns（容器内 PID 1）
# ...
```

| Docker 用的 ns | 体现 |
| -------------- | ---- |
| mount | 容器有独立 `/`, overlay |
| uts | 容器有独立 hostname |
| ipc | 容器有独立 System V IPC |
| net | 容器有独立 veth、网络栈 |
| pid | 容器进程 PID 1 起步 |
| user | UID 映射到宿主 |
| cgroup | 容器只能看自己 cgroup |

## 调试与排查

```shell
# 看容器是哪个 namespace
docker inspect -f '{{.State.Pid}}' <container>       # 拿容器主进程 PID
sudo ls -l /proc/$(...)/ns/

# 不用进容器，看容器网络（host 上直接操作）
PID=$(docker inspect -f '{{.State.Pid}}' web)
sudo nsenter -t $PID -n -- ip addr

# 看容器的 mount 树
sudo nsenter -t $PID -m -- mount | head

# 看容器 cgroup 限制
cat /proc/$PID/cgroup
```

### 找出"为什么两个进程明明隔离了还能看到对方资源"

```shell
# 1. 看它们的 namespace inode
for pid in <pid1> <pid2>; do
  echo "=== PID $pid ==="
  ls -l /proc/$pid/ns/ | awk '{print $9, $11}'
done

# 2. 如果某个 ns 的 inode 号一样，说明它们没被隔离
# 3. inode 一样 = 同一个 namespace
```

### 容器逃逸相关

namespace 是"看起来隔离"，不是"真的隔离"。能突破边界的几个点：

```text
容器内 → 宿主机
├── mount 权限过高  → 挂载宿主目录
├── privileged=true → 所有 capability + 设备访问
├── user namespace 缺失 → 容器内 root = 宿主机 root
├── /proc/sysrq-trigger 可写 → 直接触发内核 panic
└── 内核漏洞（CVE-2022-0185 等） → 任意内存读写
```

PS:
**`privileged` 模式 + 没 user namespace** 是最常见的逃逸组合。生产上：默认关 privileged、用 rootless container、用 user namespace 映射。

## 参考

- <https://man7.org/linux/man-pages/man7/namespaces.7.html>
- <https://www.kernel.org/doc/html/latest/admin-guide/namespaces/index.html>
- [网络模式.md](网络模式.md) — net namespace 在 Docker 中的应用
- [overlay.md](overlay.md) — mount namespace 配合 overlay 实现的镜像分层
