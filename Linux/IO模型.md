# Linux I/O 模型

## 一、I/O 模型概述

### 什么是 I/O 模型

**I/O 模型**:应用进程与内核、硬件之间进行数据读写时所采用的协作机制,直接决定了高并发服务的吞吐与延迟表现。

```text
应用进程
   ↓ 系统调用
内核空间
   ↓ 数据拷贝
硬件(磁盘 / 网卡 / 外设)
```

I/O 模型主要解决:

- 数据如何从内核到达应用(读)、或从应用到达内核(写)
- 调用方在等待 I/O 完成期间是否被阻塞
- 如何让单线程同时处理大量并发连接
- 如何减少数据在内核与用户态之间的冗余拷贝

### I/O 模型的主要分类

按 **POSIX 的** 5 类经典划分:

| 模型 | 缩写 | 调用方等待 | 内核通知时机 |
| ---- | ---- | ---------- | ------------ |
| 阻塞 I/O | Blocking I/O | 阻塞至完成 | 内核把数据搬到用户态前 |
| 非阻塞 I/O | Non-blocking I/O | 不阻塞,轮询 | 数据准备好立即返回 |
| I/O 多路复用 | I/O Multiplexing | 在 select/poll/epoll 上阻塞 | 由 select/poll/epoll 通知 |
| 信号驱动 I/O | Signal-driven I/O | 不阻塞 | 通过 SIGIO 信号通知 |
| 异步 I/O | Asynchronous I/O | 不阻塞 | 内核把全部操作完成后通知 |

### I/O 模型在协议栈中的位置

| 层次 | 抽象 | 典型系统调用 |
| ---- | ---- | ------------ |
| 应用层 | 编程语言运行时 | Java NIO、Go runtime |
| 系统调用层 | POSIX / Linux API | read / write / epoll / io_uring |
| 内核空间 | VFS / 协议栈 | socket / inode / bio |
| 驱动与硬件 | 设备驱动 | 网卡驱动 / 磁盘控制器 |

---

## 二、用户态与内核态

### 1. 用户态(User Space)

- 应用进程运行的地址空间
- 不能直接访问硬件
- 通过系统调用进入内核

### 2. 内核态(Kernel Space)

- 操作系统运行的特权空间
- 直接访问硬件
- 提供系统调用接口给用户态

### 3. 切换过程

```text
应用调用 read()
   │
   ▼
CPU 切到内核态(保存寄存器、切换页表)
   │
   ▼
内核处理 read()
   │
   ▼
CPU 切回用户态(恢复寄存器、返回用户态)
```

切换成本:**典型 0.1-1μs**,频繁切换会显著影响性能。

### 4. 上下文切换观察

```bash
# 查看系统上下文切换次数
vmstat 1
# cs 列:每秒上下文切换数

# 查看自愿与非自愿切换
cat /proc/<pid>/status | grep -E "voluntary_ctxt|nonvoluntary"

# 高并发服务的切换观察
pidstat -w -p <pid> 1
```

---

## 三、文件描述符(fd)

### 1. 概述

**文件描述符**(fd,File Descriptor):进程打开文件、socket、管道等资源时,内核返回的非负整数索引。

- 0 = 标准输入(stdin)
- 1 = 标准输出(stdout)
- 2 = 标准错误(stderr)
- 3+ = 用户打开的资源(socket、文件、pipe 等)

### 2. fd 表

```text
进程 PCB
   ├─ 文件描述符表(数组)
   │   ├─ [0] → 标准输入
   │   ├─ [1] → 标准输出
   │   ├─ [2] → 标准错误
   │   ├─ [3] → /var/log/app.log
   │   ├─ [4] → socket(1.2.3.4:80)
   │   └─ ...
   │
   ├─ inode 表(内核全局)
   │   ├─ inode 1024 → /var/log/app.log
   │   └─ inode 2048 → socket
   │
   └─ file 结构(内核)
       ├─ file 1024 → 读写位置、flag 等
       └─ file 2048 → socket 元数据
```

### 3. fd 限制

```bash
# 系统级
cat /proc/sys/fs/file-max

# 用户级
ulimit -n

# 进程已用
ls /proc/<pid>/fd | wc -l
```

高并发服务需调高:

```bash
# /etc/security/limits.conf
* soft nofile 65535
* hard nofile 65535
```

### 4. 常用工具

```bash
# 查看进程打开的文件
lsof -p <pid>

# 查看谁在使用某文件
lsof /var/log/app.log

# 查看所有 socket 占用
ss -tnp

# 查看 fd 数量
ls /proc/<pid>/fd | wc -l
```

---

## 四、阻塞 I/O(Blocking I/O)

### 1. 模型

**阻塞 I/O**:调用 read/write 后,进程阻塞直到数据拷贝完成。

```text
应用进程           内核              硬件
  │                │                │
  │── read() ────>│                │
  │  阻塞等待       │── 等待数据 ──>│
  │                │<── 数据到达 ──│
  │                │── 拷贝到用户态 │
  │<── 返回数据 ───│                │
  │                │                │
```

### 2. 特点

- **简单**:代码最直观
- **低效**:每个连接独占一个线程或进程,阻塞期间占资源
- **适用**:低并发、批处理任务

### 3. 同步阻塞服务端示例

```c
// 伪代码
while (1) {
    int client = accept(server_fd, ...);   // 阻塞
    char buf[1024];
    int n = read(client, buf, ...);        // 阻塞
    write(client, buf, n);                  // 阻塞
    close(client);
}
```

### 4. 性能瓶颈

- 1000 个并发连接 = 1000 个线程/进程
- 每个线程默认栈 8MB = **8GB 内存**
- 上下文切换成本不可忽视

---

## 五、非阻塞 I/O(Non-blocking I/O)

### 1. 模型

**非阻塞 I/O**:调用 read/write 后立即返回,通过轮询检查是否有数据。

```text
应用进程           内核              硬件
  │                │                │
  │── read() ────>│                │
  │<─ EAGAIN ──────│                │
  │  继续做别的事    │── 等待数据 ──>│
  │── read() ────>│                │
  │<─ EAGAIN ──────│                │
  │── read() ────>│                │
  │                │<── 数据到达 ──│
  │<── 返回数据 ───│                │
```

### 2. 设置非阻塞

```c
// C
int flags = fcntl(fd, F_GETFL);
fcntl(fd, F_SETFL, flags | O_NONBLOCK);
```

```python
# Python
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setblocking(False)
```

### 3. 优缺点

| 优点 | 缺点 |
| ---- | ---- |
| 单一线程可同时管理多个 fd | 大量空轮询浪费 CPU |
| 调用立即返回,可做其他事 | EAGAIN 处理繁琐 |

### 4. 适用场景

- 与 I/O 多路复用(epoll)配合
- 短轮询探测

---

## 六、I/O 多路复用(I/O Multiplexing)

### 1. 模型

**I/O 多路复用**:单一线程监听多个 fd,内核告知哪些 fd 就绪。

```text
应用进程                内核
  │                     │
  │── epoll_wait() ───>│
  │  阻塞              │── 监听 fd1 / fd2 / fd3 ...
  │                     │
  │<── fd2 就绪 ───────│
  │── read( fd2 ) ────>│
  │<── 返回数据 ───────│
```

### 2. select

```c
fd_set readfds;
FD_ZERO(&readfds);
FD_SET(fd1, &readfds);
FD_SET(fd2, &readfds);

struct timeval tv = {5, 0};
int n = select(max_fd + 1, &readfds, NULL, NULL, &tv);

if (FD_ISSET(fd1, &readfds)) {
    read(fd1, ...);
}
```

**特点**:

- 单进程可监听多个 fd
- 限制:`FD_SETSIZE` 通常 1024
- 每次调用需**全量拷贝 fd 集合**到内核
- 线性扫描 fd 集合,**O(n)** 复杂度

### 3. poll

```c
struct pollfd fds[2];
fds[0].fd = fd1; fds[0].events = POLLIN;
fds[1].fd = fd2; fds[1].events = POLLIN;

int n = poll(fds, 2, 5000);   // 5 秒超时

if (fds[0].revents & POLLIN) {
    read(fds[0].fd, ...);
}
```

**特点**:

- 无 fd 数量上限
- 仍需全量拷贝
- 仍**线性扫描**

### 4. epoll(Linux 高性能方案)

```c
int epfd = epoll_create1(0);

struct epoll_event ev;
ev.events = EPOLLIN;
ev.data.fd = fd1;
epoll_ctl(epfd, EPOLL_CTL_ADD, fd1, &ev);

struct epoll_event events[64];
int n = epoll_wait(epfd, events, 64, 5000);

for (int i = 0; i < n; i++) {
    if (events[i].events & EPOLLIN) {
        read(events[i].data.fd, ...);
    }
}
```

**特点**:

- `epoll_create1` 创建 epoll 实例
- `epoll_ctl` 增删改 fd
- `epoll_wait` 阻塞返回已就绪的 fd
- **红黑树**存储 fd,**O(log n)** 增删
- **就绪链表**返回时仅含就绪 fd,**O(1)** 通知
- 内核使用 **回调 + 事件驱动**(水平触发 LT / 边缘触发 ET)

#### 触发模式

| 模式 | 行为 |
| ---- | ---- |
| **LT**(Level Triggered,水平触发,默认) | fd 未读完,下次 epoll_wait 还会通知 |
| **ET**(Edge Triggered,边缘触发) | 只通知一次,必须一次读完;性能更高 |

ET 模式要求:

```c
// 必须配合非阻塞 I/O
fcntl(fd, F_SETFL, O_NONBLOCK);

// 循环读到 EAGAIN
while (read(fd, buf, size) > 0) { }
```

### 5. select / poll / epoll 对比

| 特性 | select | poll | epoll |
| ---- | ------ | ---- | ----- |
| fd 数量上限 | 1024 | 无 | 无 |
| fd 拷贝 | 每次全量 | 每次全量 | 仅增删改 |
| 就绪通知 | 线性扫描 | 线性扫描 | 回调驱动 |
| 时间复杂度 | O(n) | O(n) | O(1) |
| 适用 OS | 跨平台 | 跨平台 | Linux |
| 性能(高并发) | 差 | 差 | **极佳** |

### 6. kqueue(BSD/macOS)

```c
int kq = kqueue();
struct kevent ev;
EV_SET(&ev, fd1, EVFILT_READ, EV_ADD, 0, 0, NULL);
kevent(kq, &ev, 1, NULL, 0, NULL);

struct kevent events[64];
int n = kevent(kq, NULL, 0, events, 64, NULL);
```

**特点**:

- FreeBSD / macOS / iOS 的 epoll 等价物
- 支持多种通知:fd、信号、定时器、AIO、VNODE 等

### 7. io_uring(Linux 5.1+)

```c
struct io_uring ring;
io_uring_queue_init(64, &ring, 0);

struct io_uring_sqe *sqe = io_uring_get_sqe(&ring);
io_uring_prep_read(sqe, fd, buf, size, 0);
io_uring_submit(&ring);

struct io_uring_cqe *cqe;
io_uring_wait_cqe(&ring, &cqe);
// 处理 cqe->res
io_uring_cqe_seen(&ring, cqe);
```

**特点**:

- 共享内存 ring buffer,系统调用次数从 **N 降到 1**
- 轮询模式可完全避免阻塞调用
- 支持读、写、accept、sendfile、fsync 等

---

## 七、信号驱动 I/O(Signal-driven I/O)

### 1. 模型

**信号驱动 I/O**:内核在数据就绪时通过 `SIGIO` 信号通知应用。

```text
应用进程            内核
  │                 │
  │── 设置 SIGIO 处理 │
  │── fcntl(FASYNC) ──>│
  │                 │── 等待数据
  │<── SIGIO 信号 ─────│  数据就绪
  │── 信号处理函数 ────>│
  │── read() ────>│
  │<── 返回数据 ───│
```

### 2. 使用步骤

```c
signal(SIGIO, handler);
fcntl(fd, F_SETOWN, getpid());
fcntl(fd, F_SETFL, O_ASYNC | O_NONBLOCK);
```

### 3. 特点

| 优点 | 缺点 |
| ---- | ---- |
| 数据就绪前应用可做其他事 | 信号处理函数中调用 read 可能阻塞 |
| 不用轮询 | 信号开销大、复杂 |
| 适用 UDP(连接少) | TCP 流场景下基本不用 |

### 4. 现状

- **实际生产中已很少用**
- TCP 场景被 **epoll + 非阻塞**完全取代
- UDP 仍偶尔使用(UDP 服务器接收信号)

---

## 八、异步 I/O(Asynchronous I/O,AIO)

### 1. POSIX AIO

```c
struct aiocb cb;
cb.aio_fildes = fd;
cb.aio_buf = buf;
cb.aio_nbytes = size;
cb.aio_offset = 0;

aio_read(&cb);
// 立即返回
// 通过 aio_suspend / aio_error 等待
```

**特点**:

- 真正的"异步":数据到达用户态后才通知
- POSIX 标准
- Linux 实现较弱,**libaio**(内核级)更常用

### 2. Linux libaio

```c
io_context_t ctx;
io_setup(128, &ctx);

struct iocb cb;
cb.aio_fildes = fd;
cb.aio_buf = (uint64_t)buf;
cb.aio_nbytes = size;
cb.aio_offset = 0;
cb.aio_lio_opcode = IO_CMD_PREAD;

io_submit(ctx, 1, &cb);
// 通过 io_getevents 等待完成
```

### 3. io_uring(推荐)

- Linux 5.1+ 现代异步 I/O
- 性能最优、API 最完整
- 推荐替代 libaio 与 epoll 组合

### 4. POSIX AIO vs io_uring

| 维度 | POSIX AIO | io_uring |
| ---- | --------- | -------- |
| 实现 | 用户态 glibc | 内核 |
| 性能 | 中 | **极高** |
| 系统调用次数 | 每次操作 | **批处理 + 共享 ring** |
| 适用 | 跨平台需求 | Linux 5.1+ |

---

## 九、同步 / 异步、阻塞 / 非阻塞

### 1. 概念辨析

- **同步**(Synchronous):调用方发起 I/O 后,需要主动等待或检查结果
- **异步**(Asynchronous):调用方发起 I/O 后,内核完成后通知调用方
- **阻塞**(Blocking):调用期间调用方线程挂起
- **非阻塞**(Non-blocking):调用立即返回,可通过返回值或回调获取结果

### 2. 矩阵组合

| 模型 | 同步/异步 | 阻塞/非阻塞 | 调用方等待 | 内核完成时机 |
| ---- | --------- | ----------- | ---------- | ------------ |
| **阻塞 I/O** | 同步 | 阻塞 | 必须等 | 数据到用户态前 |
| **非阻塞 I/O** | 同步 | 非阻塞 | 轮询 | 数据到用户态前 |
| **I/O 多路复用** | 同步 | 阻塞(select 上) | 阻塞在 select/epoll | 数据就绪 |
| **信号驱动 I/O** | 同步 | 非阻塞 | 信号通知 | 数据就绪 |
| **异步 I/O** | **异步** | 非阻塞 | 不等待 | **数据到用户态后** |

### 3. 真正"异步"只有 POSIX AIO / io_uring

其他都是"同步 I/O"(无论阻塞与否),因为内核拷贝数据到用户态时调用方需要参与。

---

## 十、零拷贝(Zero Copy)

### 1. 传统 I/O 路径

```text
read + write 路径(2 次拷贝、4 次切换):
磁盘 → 内核缓冲 → 用户缓冲 → socket 缓冲 → 网卡

数据在内核缓冲 ↔ 用户缓冲 ↔ socket 缓冲 之间来回搬运
```

### 2. sendfile(内核态直接转发)

```c
#include <sys/sendfile.h>
ssize_t sendfile(int out_fd, int in_fd, off_t *offset, size_t count);
```

```text
sendfile 路径(1 次拷贝、2 次切换):
磁盘 → 内核缓冲 → socket 缓冲 → 网卡
```

- **Nginx 静态文件**、Kafka 日志投递都用此

### 3. splice(管道零拷贝)

```c
ssize_t splice(int fd_in, loff_t *off_in, int fd_out,
              loff_t *off_out, size_t len, unsigned int flags);
```

```text
splice 路径(0 次拷贝):
磁盘 → 内核缓冲(管道)→ socket 缓冲 → 网卡
```

### 4. mmap(内存映射)

```c
void *mmap(void *addr, size_t length, int prot, int flags, int fd, off_t offset);
```

```text
mmap 路径(1 次拷贝):
磁盘 → 内核缓冲(直接映射到用户态)→ socket 缓冲 → 网卡
```

- 适用于**同一进程**处理文件 + 内存场景
- 数据量大时节省内存(无需把文件加载到用户堆)

### 5. 对比

| 方案 | 数据拷贝次数 | 系统调用次数 | 上下文切换 |
| ---- | ------------ | ------------ | ---------- |
| read + write | 2 | 2 | 4 |
| sendfile | 1 | 1 | 2 |
| splice | 0 | 2 | 4 |
| mmap + write | 1 | 2 | 4 |
| io_uring + send | 0 | 1 | 2 |

---

## 十一、Page Cache 与 Buffer Cache

### 1. Page Cache(页缓存)

- 内核将磁盘文件内容缓存在 **页
- 命中时:**纳秒级
- 由 `pdflush` / `writeback` 后台线程写回磁盘
- 写策略:
  - write-through:直接写磁盘(慢)
  - write-back:写缓存(快,宕机可能丢数据)
  - write-around:仅写大文件不缓存

### 2. Buffer Cache(块缓存)

- 内核对块设备的元数据 / 数据块缓存
- 现代 Linux 与 Page Cache 已合并

### 3. 直 I/O(O_DIRECT)

```c
int fd = open("/data/file", O_DIRECT | O_RDWR);
```

- 绕过 Page Cache,直接读写磁盘
- 适合数据库(自己的 buffer 比 OS 缓存更精准)
- 性能与 Page Cache 命中情况强相关

### 4. 调优

```bash
# 查看缓存命中率
vmstat 1
# bi / bo:块设备读写

# 查看 page cache
cat /proc/meminfo | grep -E "Cached|Buffers"

# 内核参数
sysctl -w vm.dirty_ratio=20
sysctl -w vm.dirty_background_ratio=10
sysctl -w vm.dirty_expire_centisecs=3000
```

---

## 十二、内存映射(mmap)

### 1. 概述

**mmap**:将文件或设备映射到进程的虚拟地址空间,之后通过访问内存读写文件。

```text
进程虚拟地址空间
   │
   ├─ [代码段]
   ├─ [堆]
   ├─ [mmap 区域] ←── 文件 / 设备 / 匿名
   └─ [栈]
```

### 2. 用法

```c
int fd = open("file", O_RDWR);
void *addr = mmap(NULL, size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);

// 直接读写 addr 即读写文件
memcpy(addr, data, len);
msync(addr, size, MS_SYNC);   // 写回磁盘
munmap(addr, size);
close(fd);
```

### 3. 优势

- 避免 read/write 系统调用开销
- 适合**大文件**处理
- 进程间共享内存(MAP_SHARED)

### 4. 局限

- 文件大小固定
- 32 位进程最多映射 2GB
- 大小必须页对齐(4KB)
- mmap 区域大小计入进程 RSS

### 5. 应用场景

- 数据库(WiredTiger、InnoDB)
- 高性能消息队列
- 跨进程共享内存

---

## 十三、I/O 调度器

### 1. 概述

**I/O 调度器**:内核为块设备(磁盘 / SSD)提供的请求队列管理算法,决定请求顺序与合并策略。

### 2. Linux 调度器

| 调度器 | 适用 | 特点 |
| ------ | ---- | ---- |
| **noop** | SSD / NVMe / 虚拟磁盘 | 不排序,适合低延迟设备 |
| **deadline** | 数据库 / 通用 | 保证请求延迟上限 |
| **cfq**(已废弃) | HDD 桌面 | 公平调度 |
| **mq-deadline** | 多队列 SSD / NVMe | deadline 的多队列版本 |
| **kyber** | NVMe | 低延迟优先 |
| **bfq** | 桌面 / 慢设备 | 公平 + 预算 |

### 3. 查看与设置

```bash
# 查看当前调度器
cat /sys/block/sda/queue/scheduler
# [mq-deadline] kyber bfq none

# 临时切换
echo noop > /sys/block/sda/queue/scheduler

# udev 规则永久生效
# /etc/udev/rules.d/60-ioschedulers.rules
ACTION=="add|change", KERNEL=="sd[a-z]", ATTR{queue/rotational}=="0", ATTR{queue/scheduler}="none"
```

### 4. 选择建议

```text
NVMe SSD:   none / kyber
SATA SSD:   mq-deadline / kyber
HDD:        mq-deadline / bfq
虚拟机磁盘: none
```

---

## 十四、内存映射 I/O 与 DMA

### 1. DMA(Direct Memory Access)

- 设备绕过 CPU,直接读写内存
- 大块数据传输时**释放 CPU**
- 网络: / /网卡 DMA 把包写入内存
- 磁盘: / /磁盘 DMA 把扇区写入内存

### 2. CPU 角色

```text
传统 I/O:    CPU ──> 内核缓冲 ──> 用户缓冲(全程占用 CPU)
DMA + 零拷贝: 设备 ──> 内核缓冲 ──> 网卡(CPU 只参与少量设置)
```

### 3. CPU 亲和性

```bash
# 把进程绑定到特定 CPU(减少跨核调度)
taskset -c 0,1 ./myapp

# 软中断绑定
echo f > /proc/irq/32/smp_affinity
```

### 4. 性能监控

```bash
# CPU 软中断占比
top -H    # 查看 si 软中断 CPU 占用
mpstat -P ALL 1

# 网卡中断
cat /proc/interrupts | grep eth0

# 多队列网卡
ethtool -l eth0
ethtool -L eth0 combined 8
```

---

## 十五、网络 I/O 模型

### 1. C10K 问题

经典问题:单机如何同时处理 10000+ 个并发客户端?

```text
传统模型(每连接一线程):
10000 连接 → 10000 线程 → 8MB × 10000 = 80GB 内存
            → 上下文切换风暴
            → CPU 调度耗尽

解决方案:
1. epoll + 单线程事件循环(Redis / Nginx worker)
2. epoll + 多线程(主线程 accept,工作线程处理)
3. 协程(Go goroutine、Java virtual thread)
4. io_uring + 用户态 polling
```

### 2. Reactor 模式

```text
┌─────────────────────────────────────────────┐
│            主 Reactor(accept)                │
│  ┌────────────┐    ┌──────────────────────┐ │
│  │  epoll     │───>│ accept(连接)         │ │
│  └────────────┘    └──────────────────────┘ │
└────────────────┬────────────────────────────┘
                 │ 分配给工作线程
                 ▼
┌─────────────────────────────────────────────┐
│       工作 Reactor(read / write)             │
│  ┌────────────┐    ┌──────────────────────┐ │
│  │  epoll     │───>│ read(数据)           │ │
│  │            │    │ 处理业务逻辑          │ │
│  │            │    │ write(响应)          │ │
│  └────────────┘    └──────────────────────┘ │
└─────────────────────────────────────────────┘
```

### 3. Proactor 模式(异步)

- 基于异步 I/O(io_uring / IOCP)
- 内核完成 I/O 后回调应用
- 较少使用,生态不如 Reactor

### 4. 现代服务端模式

| 框架 / 语言 | 模型 |
| ----------- | ---- |
| Nginx | 多 worker + epoll |
| Redis | 单线程 + epoll |
| Netty(Java) | 主从 Reactor + 多线程 |
| Tokio(Rust) | 多线程 Reactor + work-stealing |
| Go net | goroutine + netpoller(epoll/kqueue) |

---

## 十六、常用工具

### 1. strace(系统调用追踪)

```bash
# 跟踪进程的系统调用
strace -p <pid>

# 跟踪新建进程
strace -e trace=network -f ./myapp

# 看 read / write 次数
strace -c -e read,write ./myapp
```

### 2. lsof(打开文件)

```bash
# 查看进程打开的文件
lsof -p <pid>

# 查看占用某文件的进程
lsof /var/log/app.log

# 查看 socket
lsof -i
```

### 3. ss / netstat

```bash
# TCP 连接
ss -tnp

# 监听端口
ss -tlnp

# 各状态计数
ss -ant | awk '{print $1}' | sort | uniq -c
```

### 4. iostat / iotop

```bash
# 磁盘 IO
iostat -x 1

# 进程级 IO
iotop
```

### 5. perf(性能剖析)

```bash
# 看系统调用耗时
perf trace -p <pid>

# 火焰图
perf record -F 99 -p <pid> -g -- sleep 30
perf script | ./stackcollapse-perf.pl > out.folded
./flamegraph.pl out.folded > io.svg
```

### 6. bcc / bpftrace(动态追踪)

```bash
# bcc biosnoop:块设备 IO 跟踪
biosnoop

# bcc tcpaccept:TCP accept 跟踪
tcpaccept
```

---

## 十七、性能调优

### 1. 文件描述符

```bash
# /etc/security/limits.conf
* soft nofile 65535
* hard nofile 65535

# /etc/sysctl.conf
fs.file-max = 2097152
```

### 2. TCP 缓冲

```bash
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.ipv4.tcp_rmem = 4096 87380 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216
```

### 3. TCP 队列

```bash
net.core.somaxconn = 4096
net.ipv4.tcp_max_syn_backlog = 8192
net.ipv4.tcp_synack_retries = 2
```

### 4. 网络设备

```bash
# 多队列
ethtool -L eth0 combined 8

# 环形缓冲
ethtool -g eth0
ethtool -G eth0 rx 4096 tx 4096

# 软中断均衡
echo f > /sys/class/net/eth0/queues/rx-0/rps_cpus
```

### 5. 文件系统

```bash
# 读预读
blockdev --setra 256 /dev/sda

# mount 选项
mount -o / /noatime,data=writeback,barrier=0 /dev/sda1 /data
```

### 6. 应用层

```c
// 关闭 Nagle(对小包)
TCP_NODELAY

// 启用 TCP_QUICKACK(减少 ACK 延迟)
TCP_QUICKACK

// SO_REUSEPORT(多进程 accept 同一端口)
SO_REUSEPORT
```

---

## 十八、I/O 框架与库

### 1. libuv

- Node.js 底层事件循环库
- 跨平台 epoll / kqueue / IOCP 抽象
- C 库,API 类似 libev

### 2. libevent

- 老牌 C 库事件库
- 支持 epoll / kqueue / select
- bufferevent 简化读写

### 3. libev

- 比 libevent 更轻量
- 仅事件循环,无 bufferevent 等高级抽象

### 4. Netty(Java)

- 异步事件驱动 NIO 框架
- 主从 Reactor + Pipeline
- Java 生态主流

### 5. Tokio(Rust)

- 异步运行时
- 底层 mio(epoll/kqueue/IOCP)
- async/await 风格

### 6. Go runtime

- goroutine + netpoller
- 协程由 runtime 调度
- 同步写法,异步性能

### 7. 框架对比

| 框架 | 平台 | 模型 | 语言 |
| ---- | ---- | ---- | ---- |
| libuv | 跨平台 | Reactor | C |
| libevent | 跨平台 | Reactor | C |
| Netty | JVM | Reactor | Java |
| Tokio | Rust | 多线程 Reactor | Rust |
| asyncio | 跨平台 | Reactor | Python |

---

## 十九、核心要点速记

- **I/O 模型决定高并发服务的吞吐与延迟**
- **5 类模型:阻塞 / 非阻塞 / 多路复用 / 信号驱动 / 异步**
- **POSIX 真正的"异步"只有 AIO / io_uring**
- **I/O 多路复用是 Linux 高并发的基石**
- **select / poll 是 fd 全量扫描,O(n)**
- **epoll 是回调 + 事件驱动,O(1) 就绪通知**
- **epoll 两种触发模式:LT(默认) / ET(高性能,需配合非阻塞)**
- **kqueue 是 BSD/macOS 的 epoll 等价物**
- **io_uring 是 Linux 5.1+ 的现代异步 I/O,共享 ring buffer**
- **零拷贝减少数据在内核 ↔ 用户态之间的搬运**
- **sendfile(1 次拷贝)/ splice(0 次拷贝)/ mmap(共享映射)**
- **Page Cache 是文件读写的关键缓存层**
- **直 I/O(O_DIRECT)绕过 Page Cache,适合数据库**
- **mmap 适合大文件、跨进程共享内存场景**
- **I/O 调度器:NVMe 选 none / kyber,HDD 选 mq-deadline**
- **DMA 让设备直接读写,释放 CPU**
- **CPU 亲和性减少跨核调度**
- **C10K 问题靠 epoll + 事件循环 + 多线程解决**
- **Reactor 模式是主流(Netty / Nginx / Redis)**
- **Proactor(异步)生态较弱,io_uring 正在改变**
- **strace / lsof / iostat / perf 是排查必备**
- **fd 调高:`ulimit -n` + `fs.file-max`**
- **TCP 缓冲 / 队列 / 多队列网卡是高并发关键调优**
- **SO_REUSEPORT 实现多进程 accept 同一端口**
- **TCP_NODELAY 关闭 Nagle 算法,适合小包高频**
- **O_ASYNC + SIGIO 已很少用,被 epoll 完全取代**
- **零拷贝对静态文件服务、Kafka 日志投递最关键**
- **io_uring + send/recv 是未来方向**
- **选择 I/O 模型要看:并发连接数、I/O 频率、延迟要求、跨平台需求**
