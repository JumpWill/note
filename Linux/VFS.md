# Linux VFS（Virtual File System）

## 一、VFS 概述

### 什么是 VFS

**VFS**（Virtual File System，虚拟文件系统）是 Linux 内核的一个**软件层**，为上层应用提供**统一的文件系统访问接口**，屏蔽底层不同文件系统（ext4、XFS、NTFS、proc、sysfs 等）的差异。

```text
应用进程
   │
   ▼ 系统调用
内核空间
   │
   ▼ 数据拷贝
硬件(磁盘 / 网卡 / 外设)
```

VFS 主要解决：

- 数据如何从内核到达应用（读）、或从应用到达内核（写）
- 调用方在等待 I/O 完成期间是否被阻塞
- 如何让单线程同时处理大量并发连接
- 如何减少数据在内核与用户态之间的冗余拷贝

### I/O 模型与 VFS 的关系

| 层次 | 抽象 | 典型系统调用 |
| ---- | ---- | ------------ |
| 应用层 | 编程语言运行时 | Java NIO、Go runtime |
| 系统调用层 | POSIX / Linux API | read / write / open |
| **VFS 层** | **统一抽象** | **socket / inode / bio** |
| 驱动与硬件 | 设备驱动 | 网卡驱动 / 磁盘控制器 |

---

## 二、用户态与内核态

### 1. 用户态（User Space）

- 应用进程运行的地址空间
- 不能直接访问硬件
- 通过系统调用进入内核

### 2. 内核态（Kernel Space）

- 操作系统运行的特权空间
- 直接访问硬件
- 提供系统调用接口给用户态

### 3. 切换过程

```text
应用调用 read()
   │
   ▼
CPU 切到内核态（保存寄存器、切换页表）
   │
   ▼
内核处理 read()
   │
   ▼
CPU 切回用户态（恢复寄存器、返回用户态）
```

切换成本：**典型 0.1-1μs**，频繁切换会显著影响性能。

### 4. 上下文切换观察

```bash
# 查看系统上下文切换次数
vmstat 1
# cs 列：每秒上下文切换数

# 查看自愿与非自愿切换
cat /proc/<pid>/status | grep -E "voluntary_ctxt|nonvoluntary"

# 高并发服务的切换观察
pidstat -w -p <pid> 1
```

---

## 三、文件描述符（fd）

### 1. 概述

**文件描述符**（fd，File Descriptor）：进程打开文件、socket、管道等资源时，内核返回的非负整数索引。

- 0 = 标准输入（stdin）
- 1 = 标准输出（stdout）
- 2 = 标准错误（stderr）
- 3+ = 用户打开的资源（socket、文件、pipe 等）

### 2. fd 表

```text
进程 PCB
   ├─ 文件描述符表（数组）
   │   ├─ [0] → 标准输入
   │   ├─ [1] → 标准输出
   │   ├─ [2] → 标准错误
   │   ├─ [3] → /var/log/app.log
   │   ├─ [4] → socket（1.2.3.4：80）
   │   └─ ...
   │
   ├─ inode 表（内核全局）
   │   ├─ inode 1024 → /var/log/app.log
   │   └─ inode 2048 → socket
   │
   └─ file 结构（内核）
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

高并发服务需调高：

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

## 四、VFS 概述（核心）

### VFS 在内核中的位置

```text
┌─────────────────────────────────────┐
│       用户态应用                      │
│    （glibc / shell / JVM）           │
└──────────────┬───────────────────────┘
               │ 系统调用（open/read/write）
┌──────────────▼───────────────────────┐
│       VFS 层（核心抽象）              │
│   ┌──────────────────────────────┐   │
│   │  文件系统抽象接口            │   │
│   └──────────────────────────────┘   │
│   ┌──────────┐  ┌──────────────┐     │
│   │ Page    │  │  文件对象    │     │
│   │ Cache   │  │  管理        │     │
│   └──────────┘  └──────────────┘     │
│   ┌──────────────────────────────┐   │
│   │  具体文件系统驱动              │   │
│   │  （ext4，xfs，nfs，proc）     │   │
│   └──────────────────────────────┘   │
└──────────────┬───────────────────────┘
               │ 块设备接口
┌──────────────▼───────────────────────┐
│       块设备驱动                       │
│    （磁盘 / SSD / NVMe）               │
└─────────────────────────────────────┘
```

### VFS 解决的核心问题

```text
1. 屏蔽差异
   - 不同文件系统格式（ext4、XFS、Btrfs、NTFS、ZFS）
   - 不同介质（本地磁盘、网络存储、内存、伪文件系统）
   - 不同的元数据结构和访问方式

2. 提供统一接口
   - 进程用同样的系统调用访问所有文件系统
   - read / write / open / close 不区分文件系统类型

3. 缓冲与缓存
   - Page Cache 统一管理
   - 减少物理 I/O 次数

4. 文件系统扩展
   - 新文件系统只需实现 VFS 接口
   - 不需要修改应用
```

### VFS 的核心价值

```text
- 统一接口：read / write 适用于所有文件系统
- 解耦：应用与具体文件系统解耦
- 扩展性：新文件系统只需实现 VFS 接口
- 性能：统一的 Page Cache、Buffer Cache
- 安全：统一的权限检查、ACL、capability
```

### VFS 的设计哲学

```text
1. 一切皆文件
   - 普通文件、目录、设备、socket、pipe 都是文件
   - 都用统一的 fd 访问

2. 面向对象
   - VFS 用 C 语言模拟面向对象
   - struct file_operations 定义方法
   - 类似 Java 接口

3. 分层抽象
   - 应用层 → 系统调用层 → VFS 层 → 驱动层 → 硬件
   - 每层只关注自己的职责

4. 缓存优先
   - Page Cache 是 VFS 核心
   - 先缓存后磁盘
```

### VFS 关键设计模式

```text
VFS 使用「策略-机制分离」：

机制（mechanism）：VFS 提供通用抽象
策略（policy）：具体文件系统实现具体策略

例如：
- 机制：VFS 定义 inode 接口
- 策略：ext4 用 ext4_inode_info 存储元数据

机制：VFS 定义 file_operations
策略：ext4 实现 ext4_file_operations
```

---

## 五、VFS 四大核心对象

VFS 围绕 **4 个核心数据结构**：

### 1. Superblock（超级块）

**超级块**：描述整个文件系统的元数据。

```text
super_block 结构（关键字段）：
  s_list          - 链表节点
  s_dev           - 设备号
  s_blocksize     - 块大小（4KB）
  s_maxbytes      - 最大文件大小
  s_magic         - 文件系统魔数（识别 FS 类型）
  s_op            - 操作函数集合
  s_root          - 根目录 dentry
  s_umount        - 卸载函数
  s_flags         - 标志
```

**超级块的作用**：

```text
1. 描述文件系统基本信息
   - 块大小、总块数、空闲块数
   - inode 总数、空闲 inode 数
   - 文件系统魔数（ext4 = 0xEF53）

2. 提供文件系统操作
   - 挂载、卸载
   - 同步、统计信息
   - 读写 inode
```

**查看超级块**：

```bash
# 查看 ext4 文件系统超级块
sudo dumpe2fs -h /dev/sda1 | head -30

# 输出示例：
# Filesystem volume name:   /dev/sda1
# Filesystem UUID:          a1b2c3d4-...
# Filesystem magic number:  0xEF53
# Filesystem revision #:    1 （dynamic）
# Filesystem features:      has_journal ext_attr resize_inode ...
# Default mount options:    user_xattr acl
# Filesystem state:         clean
# Block size:               4096
# Fragment size:            4096
# Blocks per group:         32768
# Inodes per group:         8192
# Inode blocks per group:   512
```

### 2. inode（索引节点）

**inode**：描述一个文件或目录的元数据。

```text
inode 结构（关键字段）：
  i_ino           - inode 号
  i_mode          - 文件类型和权限
  i_uid，i_gid     - 所有者
  i_size          - 文件大小
  i_atime         - 访问时间
  i_mtime         - 修改时间
  i_ctime         - 元数据修改时间
  i_links_count   - 硬链接数
  i_blocks        - 占用的块数
  i_op            - inode 操作
  i_fop           - 文件操作
  i_sb            - 指向超级块
  i_mapping       - 地址空间（Page Cache）
```

**inode 的关键概念**：

```text
每个文件（目录、文件、设备）都有唯一 inode 号
inode 存储文件的元数据，但不包含文件名
文件名存储在 dentry 中

inode 存储的内容：
  - 文件类型（普通文件、目录、链接、设备）
  - 权限（rwx）
  - 所有者 UID/GID
  - 文件大小
  - 时间戳
  - 数据块指针（指向实际数据位置）
```

**查看 inode**：

```bash
# 查看文件 inode 号
ls -i /etc/passwd
# 1234567 /etc/passwd

# 查看 inode 使用情况
df -i /
# Filesystem     Inodes  IUsed   IFree IUse% Mounted on
# /dev/sda1      1000000  50000  950000    5% /

# 查看 inode 详细信息
stat /etc/passwd
# File: /etc/passwd
# Size: 2345       Blocks: 8          IO Block: 4096
# Device: 803h/2051d  Inode: 1234567   Links: 1
# Access: （0644/-rw-r--r--）  Uid: （ 0/ root）
# Modify: 2024-01-15 10:30:00
# Change: 2024-01-15 10:30:00
```

### 3. dentry（目录项）

**dentry**：描述目录中的一个条目（文件名到 inode 的映射）。

```text
dentry 结构（关键字段）：
  d_count         - 引用计数
  d_flags         - 标志
  d_inode         - 指向 inode
  d_parent        - 父目录 dentry
  d_name          - 文件名（嵌入存储）
  d_op            - dentry 操作
  d_sb            - 指向超级块
```

**dentry 缓存（dcache）**：

```text
dentry 缓存是 VFS 的核心数据结构：

  用户执行 ls /usr/bin/python
       │
       ▼
  VFS 路径查找：
  1. 在 dcache 中查找 "/"
     → 命中（或未命中，从磁盘读）
  2. 在 dcache 中查找 "usr"
     → 命中
  3. 在 dcache 中查找 "bin"
     → 命中
  4. 在 dcache 中查找 "python"
     → 命中（返回 inode）

dcache 的作用：
  - 加速路径查找
  - 避免每次都从磁盘读目录
  - 内存中维护路径树
```

**查看 dcache**：

```bash
# 查看系统 dcache 统计
cat /proc/slabinfo | grep -E "dentry|inode"

# 查看 dcache 命中率
# （没有直接命令，需用 perf 或 trace）
perf stat -e cache-misses ls /usr/bin

# 查看 dentry 数量
sysctl fs.dentry-state
# nr_dentry: 12345
# nr_unused: 678
```

### 4. file（文件对象）

**file**：表示进程打开的文件实例。

```text
file 结构（关键字段）：
  f_path          - 路径（dentry + vfsmount）
  f_inode         - 指向 inode
  f_op            - 文件操作（read/write/open/close）
  f_pos           - 读写位置（偏移）
  f_flags         - 标志（O_RDONLY 等）
  f_count         - 引用计数
  f_owner         - 所有者进程
  f_cred          - 凭证（uid，gid）
```

**fd 与 file 关系**：

```text
进程 A 的 fd 表：
  [0] stdin  → file （引用计数 3: A×1，B×1，C×1）
  [1] stdout → file （引用计数 2）
  [2] stderr → file （引用计数 1）
  [3] /etc/passwd → file （引用计数 1）
  [4] socket → file （引用计数 1）

进程 B 的 fd 表：
  [3] /etc/passwd → 同一个 file（dup/fork 共享）

进程 C 的 fd 表：
  [3] /etc/passwd → 同一个 file（dup）

file 何时释放？
  - f_count == 0 时
  - 最后一个引用消失
  - 调用 close（）或进程退出
```

---

## 六、VFS 四大对象关系图

```text
                  super_block
                  （文件系统）
                       │
       ┌───────────────┼───────────────┐
       │               │               │
   inode （目录）    inode （文件）     inode （目录）
   "usr"          "passwd"         "etc"
   ino=2          ino=5           ino=8
       │               │               │
   dentry          dentry          dentry
   "usr"          "passwd"         "etc"
       │               │               │
       └───────────────┼───────────────┘
                       │
                  dentry
                  "passwd"
                       │
                  file
                  （进程打开）
                       │
                  fd （进程 A 的 4）
                  fd （进程 B 的 3）
                  fd （进程 C 的 3）
```

---

## 七、VFS 与进程关系

### 进程文件描述符表

```text
进程 task_struct
   │
   ├── files_struct
   │   ├── fd_array[0] → file （stdin）
   │   ├── fd_array[1] → file （stdout）
   │   ├── fd_array[2] → file （stderr）
   │   ├── fd_array[3] → file （打开的文件）
   │   └── fd_array[N] → file
   │
   ├── fs_struct
   │   ├── root       → dentry （/）
   │   ├── pwd        → dentry （当前目录）
   │   └── umask      → 0022 （默认权限掩码）
   │
   └── namespace （挂载命名空间）
       ├── root  → dentry + vfsmount （/）
       └── 各挂载点 → vfsmount
```

### 文件操作流程

```text
用户进程调用 write(fd，buf，count)
       │
       ▼
1. 系统调用入口 （sys_write）
       │
       ▼
2. fd → file
       通过 fd_array[fd] 找到 file 结构
       │
       ▼
3. file → file_operations
       通过 file->f_op 找到操作函数表
       │
       ▼
4. 调用 file->f_op->write
       例如 ext4_file_operations.write
       │
       ▼
5. 写入 Page Cache
       数据写入 inode 对应的地址空间
       （Page Cache）
       │
       ▼
6. 触发磁盘回写（异步）
       write（）返回成功
       内核后台写磁盘
```

---

## 八、VFS 系统调用流程

### 1. open（）调用流程

```text
用户进程调用 open（"/etc/passwd"，O_RDONLY）
       │
       ▼
1. 系统调用 sys_open → do_sys_open
       │
       ▼
2. 路径查找
       从 root dentry 开始，逐级查找：
       / → etc → passwd
       检查权限，查找 inode
       │
       ▼
3. 创建 file 对象
       分配 file 结构，初始化
       f_op = inode->i_fop
       │
       ▼
4. 分配 fd
       在进程 fd_array 中找空闲位置
       │
       ▼
5. 返回 fd 给用户
       用户得到 fd = 3（假设 0/1/2 已占用）
```

**open（）系统调用**：

```c
#include <fcntl.h>
#include <unistd.h>

int fd = open("/etc/passwd"，O_RDONLY);
// 返回 fd，失败返回 -1

if （fd == -1） {
    perror（"open"）；
    return 1;
}

char buf[1024];
ssize_t n = read(fd，buf，sizeof(buf));
// 读取数据

close(fd);
```

### 2. read（）调用流程

```text
用户进程调用 read(fd，buf，count)
       │
       ▼
1. sys_read → vfs_read
       │
       ▼
2. 检查 file 状态
       - f_pos 读写位置
       - 是否有错误
       │
       ▼
3. 调用 file->f_op->read
       例如 ext4_file_read
       │
       ▼
4. VFS 通用读取
       - 从 Page Cache 读取
       - 如果不在 Page Cache，从磁盘读
       │
       ▼
5. 数据拷贝到用户态
       内核空间 → 用户空间
       │
       ▼
6. 返回读到的字节数
```

### 3. write（）调用流程

```text
用户进程调用 write(fd，buf，count)
       │
       ▼
1. sys_write → vfs_write
       │
       ▼
2. 检查文件权限
       进程是否有写权限
       │
       ▼
3. 写入 Page Cache
       write（）返回时，数据在 Page Cache
       │
       ▼
4. 触发脏页回写
       pdflush / 内核线程
       异步刷到磁盘
       │
       ▼
5. 返回写入字节数
```

### 4. close（）调用流程

```text
用户进程调用 close(fd)
       │
       ▼
1. sys_close → filp_close
       │
       ▼
2. 释放 fd
       fd_array[fd] = NULL
       │
       ▼
3. 减少 file 引用计数
       file->f_count--
       │
       ▼
4. f_count == 0 时
       调用 file->f_op->release
       释放 file 对象
       │
       ▼
5. 释放 dentry 引用
       减少 d_count
```

---

## 九、VFS 缓存机制

### 1. Page Cache（页缓存）

```text
Page Cache 是 VFS 的核心缓存：

  用户进程
      │
      ▼ read()
      │
  VFS
      │
      ▼
  ┌─ Page Cache（内存）─┐
  │  缓存最近读取的磁盘块 │
  │  与 inode 关联        │
  └──────────┬───────────┘
             │ 缓存命中 → 直接返回
             │ 缓存未命中 → 从磁盘读，放入缓存
             ▼
           磁盘
```

**Page Cache 的优势**：

```text
1. 加速重复读
   - 文件读过一次，后续读从内存返回
   - 内核 LRU 淘汰算法

2. 合并写
   - 多个 write（）合并为一次磁盘写
   - 减少 I/O 次数

3. 预读（readahead）
   - 顺序读时预读后续数据
   - 提高顺序读性能

4. 写回（writeback）
   - 延迟写磁盘
   - 累积后批量写
```

**查看 Page Cache**：

```bash
# 查看系统 Page Cache 使用
free -h
# buff/cache 列就是 Page Cache

# 查看具体文件 Page Cache
pcstat /var/log/app.log

# 强制刷盘
sync
echo 3 > /proc/sys/vm/drop_caches

# 查看 Page Cache 命中率
perf stat -e cache-misses ls /usr/bin
```

### 2. dcache（dentry 缓存）

```text
dcache 缓存路径查找结果：

  用户执行 ls /usr/bin/python
       │
       ▼
  VFS 路径查找：
       │
       ├── 检查 dcache "/"  → 命中
       ├── 检查 dcache "usr" → 命中
       ├── 检查 dcache "bin" → 命中
       └── 检查 dcache "python" → 命中

  如果全部命中：
  - 无需访问 inode 表
  - 无需读取磁盘目录
  - 极快返回结果
```

**dcache 的限制**：

```bash
# dcache 最大数量
sysctl fs.dentry-max

# 默认值：系统内存 / 4K
# 例如：16GB 内存 → 4M entries

# 查看实际使用
cat /proc/sys/fs/dentry-state
# nr_dentry: 123456  （当前活跃）
# nr_unused: 6789    （未引用）
```

### 3. inode 缓存

```text
inode 缓存机制：
  - inode 在首次访问时读入内存
  - 存储在 inode_hashtable
  - 引用计数管理生命周期
  - 修改时写回磁盘
```

---

## 十、文件系统类型

### Linux 支持的文件系统

```text
磁盘文件系统：
  - ext2 / ext3 / ext4      （Linux 原生，最常用）
  - XFS                     （RHEL/CentOS 默认，高性能）
  - Btrfs                   （新一代，CoW）
  - ZFS                     （Solaris 移植，功能强）
  - F2FS                    （闪存优化）
  - NTFS / FAT32 / exFAT   （Windows 兼容）

网络文件系统：
  - NFS                     （Network File System）
  - CIFS / SMB              （Windows 共享）
  - AFS                     （Andrew File System）
  - GlusterFS               （分布式）

伪文件系统：
  - procfs                  （/proc，进程信息）
  - sysfs                   （/sys，设备和驱动）
  - tmpfs                   （/dev/shm，内存文件系统）
  - devpts                   （伪终端）
  - cgroupfs                （/sys/fs/cgroup）
  - debugfs                  （debug 调试）
  - securityfs               （安全模块）
  - sysv                     （System V 兼容）
  - usbfs                    （USB 设备）

分布式文件系统：
  - GlusterFS
  - HDFS（Hadoop）
  - CephFS（Ceph）
  - MinIO
```

### 主流文件系统对比

| 文件系统 | 特点 | 适用场景 |
|---------|------|---------|
| **ext4** | Linux 默认，稳定，最大 1EB | 通用 |
| **XFS** | 高性能，大文件友好，RHEL 默认 | 企业服务器 |
| **Btrfs** | CoW，快照，RAID | 高级特性 |
| **ZFS** | 企业级特性强 | NAS、备份 |
| **F2FS** | 闪存优化 | 嵌入式、SSD |
| **tmpfs** | 内存文件系统 | /dev/shm |
| **procfs** | 进程信息 | /proc |
| **sysfs** | 设备/驱动信息 | /sys |

### 文件系统选择建议

```text
通用服务器：
  → ext4 / XFS（稳定可靠）

大文件存储：
  → XFS（视频、日志）

数据库：
  → XFS / ext4（性能好）

容器 / 嵌入式：
  → overlay2 / F2FS（轻量）

NAS / 备份：
  → ZFS / Btrfs（快照、压缩）

内存临时数据：
  → tmpfs
```

---

## 十一、VFS 系统调用详解

### 1. 常用系统调用

```c
#include <fcntl.h>
#include <unistd.h>
#include <sys/stat.h>

// 打开文件
int open(const char *pathname, int flags, mode_t mode);

// 关闭文件
int close(int fd);

// 读取数据
ssize_t read(int fd, void *buf, size_t count);

// 写入数据
ssize_t write(int fd, const void *buf, size_t count);

// 文件定位
off_t lseek(int fd, off_t offset, int whence);

// 同步刷盘
int fsync(int fd);
int fdatasync(int fd);

// 文件元数据
int fstat(int fd, struct stat *statbuf);

// 文件控制
int fcntl(int fd, int cmd, ...);

// ioctl（设备相关）
int ioctl(int fd, unsigned long request, ...);
```

### 2. 文件系统操作

```c
#include <sys/stat.h>
#include <unistd.h>
#include <dirent.h>

// 获取文件元数据
int stat(const char *pathname, struct stat *statbuf);
int lstat(const char *pathname, struct stat *statbuf);
int fstat(int fd, struct stat *statbuf);

// 目录操作
DIR *opendir(const char *name);
struct dirent *readdir(DIR *dir);
int closedir(DIR *dir);

// 文件系统操作
int access(const char *pathname, int mode);
int chmod(const char *pathname, mode_t mode);
int chown(const char *pathname, uid_t owner, gid_t group);

// 创建/删除
int creat(const char *pathname, mode_t mode);
int mkdir(const char *pathname, mode_t mode);
int rmdir(const char *pathname);
int unlink(const char *pathname);
int rename(const char *oldpath, const char *newpath);
int link(const char *oldpath, const char *newpath);
int symlink(const char *target, const char *linkpath);
ssize_t readlink(const char *pathname, char *buf, size_t bufsiz);

// 截断
int truncate(const char *path, off_t length);
int ftruncate(int fd, off_t length);
```

### 3. 目录操作示例

```c
#include <dirent.h>
#include <stdio.h>

void list_dir(const char *path) {
    DIR *dir = opendir(path);
    if (!dir) {
        perror("opendir");
        return;
    }
    
    struct dirent *entry;
    while ((entry = readdir(dir)) != NULL) {
        printf("%s/%s\n", path, entry->d_name);
    }
    
    closedir(dir);
}

int main() {
    list_dir("/tmp");
    return 0;
}
```

---

## 十二、VFS 路径查找

### 1. 路径查找流程

```text
用户调用 open（"/usr/bin/python"）
       │
       ▼
1. 从进程的 fs_struct.root 开始
       │
       ▼
2. 解析路径，分段：
       ["/"，"usr"，"bin"，"python"]
       │
       ▼
3. 逐段查找 dcache：
       dcache["/"]    → 命中
       dcache["usr"]  → 命中
       dcache["bin"]  → 命中
       dcache["python"] → 命中
       │
       ▼
4. 返回最终 inode
       inode （python 可执行文件）
       │
       ▼
5. 创建 file 对象，分配 fd
```

### 2. dcache 状态

```bash
# 查看 dcache 命中率
perf stat -e cache-misses ls /usr/bin

# 内核统计
cat /proc/sys/fs/dentry-state
# nr_dentry: 12345  当前 dentry 数量
# nr_unused: 6789   未引用 dentry

# 释放 dcache
echo 3 > /proc/sys/vm/drop_caches
# 1 = 释放 pagecache
# 2 = 释放 dentries 和 inodes
# 3 = 释放所有缓存
```

### 3. 路径查找性能优化

```text
1. dcache 命中
   - 路径存在于 dcache，直接返回
   - 微秒级

2. dcache 未命中，需读盘
   - 从磁盘读目录
   - 加入 dcache
   - 毫秒级

3. 长路径性能
   - 路径越长，查找越慢
   - 软链接影响性能
   - mount bind 影响性能

4. openat（）vs open（）
   - openat（）更高效
   - 避免完整路径解析
```

---

## 十三、VFS 与 Page Cache

### 1. Page Cache 架构

```text
用户进程
   │
   ▼ read()
   │
VFS 层
   │
   ▼
  ┌─ Page Cache ─────────────────┐
  │                              │
  │  ┌────────────────────┐     │
  │  │   inode （文件元数据） │     │
  │  └────────────────────┘     │
  │  ┌────────────────────┐     │
  │  │   address_space     │     │
  │  │  （文件数据）         │     │
  │  └────────────────────┘     │
  │                              │
  │  按 4KB 页面组织              │
  └──────────────┬───────────────┘
                 │
                 ▼
              磁盘驱动
```

### 2. 缓存策略

```text
Page Cache 策略：
  - read-ahead（预读）：顺序读时预读后续数据
  - write-back（回写）：延迟写磁盘
  - dirty ratio（脏页比例）：达到阈值开始回写
```

```bash
# 查看 dirty page 参数
sysctl vm.dirty_ratio          # 内存百分比（默认 20）
sysctl vm.dirty_background_ratio  # 5
sysctl vm.dirty_expire_centisecs  # 30 秒
sysctl vm.dirty_writeback_centisecs  # 5 秒

# 强制刷盘
sync
echo 1 > /proc/sys/vm/drop_caches

# 查看脏页
cat /proc/vmstat | grep -E "dirty|writeback"
```

---

## 十四、文件系统注册与挂载

### 1. 文件系统注册

```c
// ext4 文件系统注册（内核代码）
static struct file_system_type ext4_fs_type = {
    .owner       = THIS_MODULE,
    .name        = "ext4",
    .mount       = ext4_mount,
    .kill_sb     = ext4_kill_sb,
    .fs_flags    = FS_REQUIRES_DEV | FS_EXT4,
};
module_init(ext4_init)
module_exit(ext4_exit)
```

```text
文件系统注册过程：
  1. 文件系统驱动加载（内核模块）
  2. register_filesystem（）注册 file_system_type
  3. 内核维护 file_systems 链表
  4. /proc/filesystems 显示可用文件系统
```

### 2. 文件系统挂载

```bash
# 查看可用文件系统
cat /proc/filesystems
# nodev sysfs
# nodev tmpfs
# nodev bdev
# nodev proc
# nodev cgroup
# nodev cgroup2
#       ext4
#       xfs
#       btrfs

# 挂载
mount -t ext4 /dev/sda1 /mnt
mount -t nfs 192.168.1.100:/share /mnt/nfs

# 查看挂载点
mount | head
# /dev/sda1 on / type ext4 （rw，relatime）
# proc on /proc type proc （rw，nosuid，nodev，noexec，relatime）
# tmpfs on /dev/shm type tmpfs （rw，nosuid，nodev）

# 查看挂载详细信息
findmnt
```

### 3. 挂载命名空间

```c
// 挂载命名空间（Mount Namespace）
struct mnt_namespace {
    atomic_t count;                // 引用计数
    struct vfsmount *root;          // 根挂载
    struct list_head list;          // 挂载点列表
    struct user_namespace *user_ns;
    struct ns_common ns;           // 通用 ns 字段
};
```

**挂载命名空间的作用**：

```text
- 每个进程有独立的挂载视图
- Docker 用 mount namespace 实现容器文件系统隔离
- /proc/<pid>/mounts 显示该进程的挂载
- /proc/<pid>/mountinfo 显示详细信息
```

---

## 十五、VFS 调试与排查

### 1. 常用调试工具

```bash
# 查看文件系统信息
df -h          # 空间使用
df -i          # inode 使用
mount          # 挂载点
findmnt        # 树形显示挂载

# 查看文件元数据
stat <file>    # inode、权限、时间等
ls -li <file>  # inode + 文件
file <file>    # 文件类型

# 查看进程打开的文件
lsof -p <pid>           # 进程打开的所有 fd
lsof <file>             # 哪些进程打开了该文件
lsof -i :80             # 谁在用端口 80
ls -l /proc/<pid>/fd     # fd 详情

# 查看文件系统统计
cat /proc/filesystems
cat /proc/mounts
cat /proc/diskstats

# 查看 Page Cache
free -h
cat /proc/meminfo | grep -E "Cached|Buffers"

# 查看 dcache / inode cache
cat /proc/slabinfo
slabtop
```

### 2. strace 跟踪文件操作

```bash
# 跟踪某个进程的文件系统调用
strace -f -e openat,read,write,close -p <pid>

# 跟踪 cat 命令的系统调用
strace cat /etc/passwd

# 典型输出：
# openat(AT_FDCWD, "/etc/passwd", O_RDONLY) = 3
# read(3, "root:x:0:0:root:/root:/bin/bash\n"..., 1024) = 2345
# close(3)                                = 0
```

### 3. perf 跟踪 VFS

```bash
# 跟踪 VFS 函数
perf trace -p <pid> -e vfs_*

# 跟踪具体 VFS 函数
perf stat -e 'vfs_read*,vfs_write*,d_lookup' -p <pid>

# 火焰图分析
perf record -F 99 -p <pid> -g
perf script | stackcollapse-perf | flamegraph-stackcollapse > vfs.svg
```

### 4. 常见问题排查

#### 文件描述符耗尽

```bash
# 现象：too many open files
# 查看进程 fd 数量
ls /proc/<pid>/fd | wc -l

# 查看系统限制
ulimit -n
cat /proc/sys/fs/file-max

# 解决
ulimit -n 65535
# 或修改 /etc/security/limits.conf
* soft nofile 65535
* hard nofile 65535
```

#### inode 耗尽

```bash
# 现象：No space left on device，但 df 仍有空间
df -i    # 查看 inode 使用

# 解决：删除大量小文件
find /path -type f -name "*.tmp" -delete
```

#### Page Cache 占用过多

```bash
# 查看 Page Cache
free -h

# 清理 Page Cache
echo 1 > /proc/sys/vm/drop_caches    # pagecache
echo 2 > /proc/sys/vm/drop_caches    # dentries + inodes
echo 3 > /proc/sys/vm/drop_caches    # 所有缓存

# 注意：清理缓存会导致下一次读磁盘
```

---

## 十六、VFS 性能优化

### 1. 文件系统选型优化

```text
应用场景          推荐文件系统   原因
─────────────────────────────────
通用服务器         ext4 / XFS    稳定可靠
大文件（视频、日志）XFS           优化大文件 IO
数据库              XFS / ext4   性能好
容器              overlay2       联合挂载，适合镜像
高频写小文件       F2FS          闪存优化
小内存环境         ext2 / ext4   无日志，开销小
大文件压缩         Btrfs / ZFS   内置压缩
```

### 2. mount 选项优化

```bash
# noatime：不更新访问时间（性能提升 5-10%）
mount -o noatime,nodiratime /dev/sda1 /mnt

# 数据盘常用选项
mount -o noatime,nodiratime,data=writeback,barrier=0 /dev/sda1 /mnt/data

# 数据库专用
mount -o noatime,nodiratime,data=writeback /dev/sda1 /var/lib/mysql
```

### 3. Page Cache 优化

```bash
# 调整脏页参数（高 IO 场景）
sysctl vm.dirty_ratio = 10           # 默认 20
sysctl vm.dirty_background_ratio = 5 # 默认 10

# 调整 swappiness（数据库建议低值）
sysctl vm.swappiness = 10            # 默认 60

# 增加 Page Cache 回收
echo 1 > /proc/sys/vm/drop_caches
```

### 4. dcache 优化

```bash
# 增加 dcache 上限
sysctl fs.dentry-max = 5000000

# 查看 dcache 命中率
cat /proc/slabinfo | grep dentry

# 监控 dcache 状态
cat /proc/sys/fs/dentry-state
```

### 5. 文件描述符优化

```bash
# 系统级
sysctl fs.file-max = 1000000

# 用户级
# /etc/security/limits.conf
* soft nofile 1000000
* hard nofile 1000000

# 进程级
ulimit -n 1000000

# 查看当前使用
cat /proc/sys/fs/file-nr
# 已分配  空闲   最大
# 54321   45679  100000
```

---

## 十七、VFS 与其他内核子系统

### 1. VFS 与 I/O 模型

```text
VFS 提供同步 I/O（read/write）

异步 I/O 方式：
  - libaio（Linux AIO）
  - io_uring（推荐，性能最强）
  - POSIX AIO
  - SPDK（内核旁路）

VFS 与 io_uring：
  io_uring 通过 uring_submit / uring_wait 与 VFS 交互
  减少系统调用次数，提升性能
```

### 2. VFS 与内存管理

```text
VFS 与内存管理紧密关联：

内存管理功能         VFS 中使用
─────────────────────────────────
Page Cache      VFS 数据缓存
mmap            文件映射到内存
Direct I/O      绕过 Page Cache
Swap            内存压力时换页
COW             写时复制（fork）
```

### 3. VFS 与网络

```text
网络与 VFS 的交叉点：
  - NFS（网络文件系统）
  - CIFS（Windows 网络共享）
  - 9P（Plan 9 文件系统）
  - FUSE（用户态文件系统）
  - 网络 socket 也在 VFS 中（/proc/<pid>/fd/）
```

### 4. VFS 与容器

```text
Docker / K8s 使用 VFS 的方式：

1. Mount Namespace
   - 每个容器独立的挂载视图
   - 隔离文件系统

2. OverlayFS / UnionFS
   - 镜像分层
   - 写时复制
   - 容器存储驱动

3. /proc / sys / dev
   - 容器内的伪文件系统
   - 来自宿主 namespace

4. Volume 挂载
   - bind mount
   - tmpfs（emptyDir）
   - 持久卷（PV/PVC）
```

---

## 十八、VFS 在 Docker 中的应用

### 1. Docker 文件系统分层

```text
Docker 镜像分层：

  ┌─────────────────────┐
  │  Container Layer     │  ← 可写层
  │  （容器运行时修改）     │
  ├─────────────────────┤
  │  Image Layer 5       │  ← 只读层
  ├─────────────────────┤
  │  Image Layer 4       │
  ├─────────────────────┤
  │  Image Layer 3       │
  ├─────────────────────┤
  │  Image Layer 2       │
  ├─────────────────────┤
  │  Base Layer 1        │  ← 基础镜像
  └─────────────────────┘

  OverlayFS 联合挂载：
  - 上层可见下层所有内容
  - 修改文件 → 写时复制到上层
  - 删除文件 → 创建 whiteout 文件
```

### 2. Docker 存储驱动

```bash
# 查看 Docker 存储驱动
docker info | grep "Storage Driver"
# Storage Driver: overlay2

# 主流存储驱动对比
# overlay2:  推荐，Linux 4.0+
# devicemapper: 旧版 CentOS
# btrfs:     Btrfs 文件系统
# zfs:       ZFS 文件系统
# vfs:       测试用
```

### 3. Docker 文件系统挂载

```bash
# bind mount（绑定挂载）
docker run -v /host/path:/container/path nginx
docker run --mount type=bind,source=/host,target=/container nginx

# tmpfs（内存文件系统）
docker run --tmpfs /tmp nginx
docker run --mount type=tmpfs,destination=/tmp nginx

# volume（数据卷）
docker run -v my-volume:/data nginx
docker volume create my-volume
docker run -v my-volume:/data nginx

# 只读
docker run --read-only nginx
docker run --mount type=volume,source=my-vol,target=/data,readonly nginx
```

### 4. K8s Volume

```yaml
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: app
    image: nginx
    volumeMounts:
    - name: data
      mountPath: /data
  volumes:
  # emptyDir（Pod 内共享）
  - name: data
    emptyDir: {}

  # hostPath（节点目录）
  - name: host-data
    hostPath:
      path: /data
      type: Directory

  # PersistentVolumeClaim（持久卷）
  - name: persistent
    persistentVolumeClaim:
      claimName: my-pvc
```

---

## 十九、VFS 与 FUSE

### FUSE 概述

**FUSE**（Filesystem in Userspace）：用户态文件系统，无需修改内核。

```text
应用进程
   │
   ▼ 系统调用（open/read/write）
   │
VFS
   │
   ▼
FUSE 内核模块
   │
   ▼
   ↓ 通信（/dev/fuse）
   ↓
FUSE 用户态进程（实现文件系统逻辑）
   │
   ▼
后端存储（S3、本地文件、内存、远程服务）
```

### FUSE 应用场景

```text
1. S3FS：将 S3 挂载为本地文件系统
   s3fs mybucket /mnt/s3 -o passwd_file=~/.passwd

2. SSHFS：通过 SSH 挂载远程目录
   sshfs user@server:/remote/path /mnt/sshfs

3. GlusterFS：分布式文件系统用户态客户端

4. mergerfs：联合多个挂载点

5. bindfs：FUSE 实现 bind mount 高级功能
```

### FUSE 性能

```text
FUSE 缺点：
  - 用户态/内核态切换开销
  - 性能比内核文件系统低 30-50%
  - 不适合高 I/O 场景

适用场景：
  - 中低 IO 场景
  - 需要快速实现自定义文件系统
  - 测试和原型
```

---

## 二十、VFS 安全机制

### 1. 文件权限检查

```text
VFS 权限检查流程：
  1. 用户进程调用 open(path, O_RDONLY)
  2. VFS 检查 path 的每个分量：
     - 从 root 到文件
     - 检查每级目录的 x（执行）权限
  3. 检查 inode 的权限：
     - 当前用户是 owner → 检查 owner 权限位
     - 否则在 group → 检查 group 权限位
     - 否则检查 other 权限位
  4. 权限足够 → 允许
     否则 → EACCES
```

### 2. 能力（Capabilities）

```text
普通权限 vs 能力：

传统 Unix 权限：
  - 只能限制 owner/group/other
  - root 是万能的

Linux Capabilities：
  - 把 root 权限细分为 40+ 个 capability
  - 普通进程可以拥有部分能力

常用 Capability：
  - CAP_DAC_OVERRIDE  绕过文件权限检查
  - CAP_CHOWN         修改文件所有者
  - CAP_NET_ADMIN      网络管理
  - CAP_SYS_ADMIN     系统管理（危险）
  - CAP_SYS_PTRACE    调试其他进程
```

### 3. 文件系统安全选项

```bash
# 只读挂载
mount -o ro /dev/sda1 /mnt

# noexec：禁止执行
mount -o noexec /tmp

# nosuid：禁止 setuid
mount -o nosuid /home

# nodev：禁止设备文件
mount -o nodev /tmp

# 综合（/tmp 标准配置）
mount -o noexec,nosuid,nodev /tmp
```

### 4. ACL（访问控制列表）

```bash
# 设置 ACL
setfacl -m u:alice:rwx /project
setfacl -m g:dev:r-- /project/docs
setfacl -m d:u:alice:rwx /project

# 查看 ACL
getfacl /project

# 启用 ACL（mount 选项）
mount -o acl /dev/sda1 /mnt
```

---

## 二十一、VFS 常见问题排查

### 1. too many open files

```bash
# 现象：进程报错 "too many open files"

# 1. 查看系统级限制
cat /proc/sys/fs/file-max

# 2. 查看用户级限制
ulimit -n

# 3. 查看进程实际使用
ls /proc/<pid>/fd | wc -l
lsof -p <pid> | wc -l

# 4. 解决：调高限制
ulimit -n 65535
# 或修改 /etc/security/limits.conf
* soft nofile 65535
* hard nofile 65535

# 5. 找到 fd 泄漏的进程
for pid in $(pgrep -f java); do
    count=$(ls /proc/$pid/fd 2>/dev/null | wc -l)
    echo "PID $pid: $count fds"
done | sort -t: -k2 -nr | head
```

### 2. No space left on device

```bash
# 现象：写文件失败，但 df 显示有空间

# 1. inode 耗尽
df -i
# Filesystem     Inodes  IUsed   IFree IUse% Mounted on
# /dev/sda1      1000000  999999     1  100% /  ← inode 满了

# 解决：删除大量小文件

# 2. 磁盘配额
mount -o usrquota,grpquota /dev/sda1 /home

# 3. inode 缓存过多
sysctl fs.inode-max
echo 1 > /proc/sys/vm/drop_caches

# 4. 文件系统满
df -h
# du -sh * | sort -hr 找出大文件
```

### 3. 文件系统只读

```bash
# 现象：写文件失败，错误 read-only file system

# 1. 检查挂载
mount | grep <mount>
# 看到 ro（read-only）就是只读

# 2. 重新挂载为读写
mount -o remount,rw /

# 3. 文件系统错误
dmesg | grep -i "ext4\|i/o error"
mount | grep ro

# 4. 磁盘故障
smartctl -a /dev/sda

# 5. 强制修复
umount /dev/sda1
fsck -y /dev/sda1
mount /dev/sda1 /mnt
```

### 4. 路径查找慢

```bash
# 现象：find、ls 等操作慢

# 1. 检查 dcache 状态
cat /proc/sys/fs/dentry-state

# 2. 检查目录深度
find / -type d -mindepth 10 | head

# 3. 检查大量软链接
find / -type l | wc -l

# 4. 性能分析
perf stat -e 'd_lookup*,dentry_open' ls -l /path

# 5. 解决方案
mount -o noatime /dev/sda1 /mnt    # 减少元数据更新
# 整理目录层级
# 缓存关键路径
```

### 5. 文件锁问题

```bash
# 现象：NFS 文件锁住

# 1. 查看锁
lsof /path/to/file

# 2. 强制解锁
fuser -k /path/to/file
fuser -m -u /path/to/file

# 3. POSIX 文件锁
flock --help

# 4. fcntl 文件锁
man fcntl
```

---

## 二十二、核心要点速记

### VFS 四大核心对象

```
1. super_block  - 文件系统元数据
2. inode        - 文件/目录元数据
3. dentry       - 目录项（路径名 → inode）
4. file         - 进程打开的文件实例
```

### VFS 核心思想

```
1. 一切皆文件
   - 普通文件、目录、设备、socket、pipe
   - 都用统一的 fd 访问

2. 面向对象设计
   - C 语言模拟 OOP
   - file_operations 接口
   - 类似 Java interface

3. 策略与机制分离
   - VFS 提供通用接口
   - 具体文件系统实现策略

4. 缓存优先
   - Page Cache 是性能关键
   - dentry Cache 加速路径查找
```

### 关键路径速记

```
v1 系统调用：
  user → sys_open → do_sys_open → path_lookup → file_open
       → file_operations.open → 具体 FS open
       → 分配 fd → 返回

路径查找：
  root → dentry cache → 一级一级匹配 → 最终 inode

缓存：
  Page Cache：文件数据缓存
  dcache：     路径缓存
  inode cache：inode 缓存
```

### 关键文件

```
# super block
dumpe2fs -h /dev/sda1

# inode
ls -i /etc/passwd
stat /etc/passwd

# 进程 fd
ls -l /proc/<pid>/fd
lsof -p <pid>

# Page Cache
free -h
cat /proc/meminfo | grep Cached

# dcache
cat /proc/sys/fs/dentry-state
```

### 关键命令速记

```bash
df -h              # 空间
df -i              # inode
mount             # 挂载点
findmnt           # 树形挂载
stat <file>       # 元数据
lsof -p <pid>      # 进程 fd
strace -e open,read,write <cmd>  # 跟踪系统调用
```

### 文件系统选型速记

```
通用：ext4 / XFS
大文件：XFS
数据库：XFS
容器：overlay2
小内存：ext2
闪存：F2FS
```

### 一句话总结

```
VFS = Linux 内核的虚拟文件系统层
4 大对象：super_block / inode / dentry / file
核心设计：一切皆文件 + 策略机制分离 + 缓存优先
优化重点：Page Cache + dentry Cache + 文件描述符
容器基础：Docker / K8s 都建立在 VFS 之上
```

### VFS 与 I/O 模型的关系

```
VFS 同步 I/O：
  read/write → 阻塞等返回

VFS 异步 I/O：
  libaio（AIO）→ 提交后立即返回
  io_uring → 高性能异步 I/O

mmap：
  文件映射到内存 → 减少数据拷贝

sendfile：
  文件 → socket 直接传送 → 零拷贝
```

---

## 二十三、VFS 相关内核参数配置与优化

### 1. 文件描述符（fd）参数

```bash
# 系统级 fd 上限
sysctl fs.file-max                    # 系统最大 fd 数

# 单进程 fd 上限
ulimit -n                              # 查看当前进程限制

# 持久化配置（/etc/security/limits.conf）
* soft nofile 1048576                  # 软限制
* hard nofile 1048576                  # 硬限制
root soft nofile 1048576
root hard nofile 1048576

# 系统级配置（/etc/sysctl.conf）
fs.file-max = 1048576
fs.nr_open = 1048576

# 查看当前使用
cat /proc/sys/fs/file-nr
# 输出：已分配  空闲   最大
#       1024     99184   100000
```

### 2. dentry 缓存参数

```bash
# dcache 最大数量
sysctl fs.dentry-max                 # 默认 16GB 内存约 400 万

# 查看 dcache 状态
cat /proc/sys/fs/dentry-state
# nr_dentry: 123456  当前 dentry 数量
# nr_unused: 67890   未引用 dentry 数量

# 调整建议
echo "fs.dentry-max = 10000000" >> /etc/sysctl.conf
sysctl -p

# 释放 dcache（影响性能，慎用）
echo 2 > /proc/sys/vm/drop_caches

# 监控 dcache 命中率
perf stat -e cache-misses ls -l /path
```

### 3. inode 缓存参数

```bash
# inode 处理参数
sysctl fs.inode-max                  # 系统 inode 处理上限

# inode-state（v2 内核）
cat /proc/sys/fs/inode-state
# nr_inodes: 12345   当前 inode 对象数
# nr_unused: 6789    未引用的 inode

# 调整（高并发文件服务）
sysctl fs.inode-max = 10000000

# 查看文件系统 inode 使用
df -i
```

### 4. Page Cache 参数

```bash
# 脏页刷新参数
sysctl vm.dirty_ratio                 # 内存百分比（默认 20）
sysctl vm.dirty_background_ratio     # 后台回写阈值（默认 10）
sysctl vm.dirty_expire_centisecs     # 过期时间（默认 30 秒）
sysctl vm.dirty_writeback_centisecs  # 回写间隔（默认 5 秒）

# 数据库优化配置
sysctl vm.dirty_ratio = 5
sysctl vm.dirty_background_ratio = 2
sysctl vm.dirty_expire_centisecs = 1500
sysctl vm.dirty_writeback_centisecs = 100

# Web 服务器配置
sysctl vm.dirty_ratio = 20
sysctl vm.dirty_background_ratio = 10
sysctl vm.dirty_expire_centisecs = 3000
sysctl vm.dirty_writeback_centisecs = 500

# Page Cache 回收
echo 1 > /proc/sys/vm/drop_caches         # 释放 Page Cache
echo 2 > /proc/sys/vm/drop_caches         # 释放 dentries + inodes
echo 3 > /proc/sys/vm/drop_caches         # 释放所有缓存

# min_free_kbytes（最小空闲内存）
sysctl vm.min_free_kbytes                # 默认根据内存自动计算
# 高负载建议：总内存的 1-3%
sysctl vm.min_free_kbytes = 262144       # 256MB
```

### 5. 预读（readahead）参数

```bash
# 块设备预读
blockdev --getra /dev/sda              # 查看当前预读值（KB）
blockdev --setra 4096 /dev/sda          # 设置预读 4MB

# 单文件预读（v2 cgroup）
cat /sys/fs/cgroup/test/filesystem.read_ahead_kb
# 默认 128 KB

# 内核参数
sysctl vm.pagecache_ratio              # Page Cache 占内存比例（无此参数）

# 通过 udev 规则设置（按设备）
cat > /etc/udev/rules.d/99-readahead.rules << 'EOF'
ACTION=="add|change", KERNEL=="sda", ATTR{queue/rotational}=="0", RUN+="/sbin/blockdev --setra 4096 /dev/sda"
EOF
udevadm control --reload-rules
```

### 6. 文件系统挂载参数

```bash
# 数据盘标准选项（生产推荐）
mount -o noatime,nodiratime,data=writeback /dev/sda1 /data

# 各参数详解
mount -o 参数  # 含义

# noatime       - 不更新文件访问时间（性能提升 5-10%）
# nodiratime    - 不更新目录访问时间
# data=writeback - 数据写入绕过日志（性能好，断电可能丢数据）
# data=ordered   - 数据按顺序写入（默认，安全但慢）
# data=journal   - 数据先写日志（最安全）
# barrier=0     - 禁用写屏障（性能好，需电池备份）
# noexec        - 禁止执行（安全）
# nosuid        - 禁止 setuid（安全）
# nodev         - 禁止设备文件
# acl           - 启用 ACL
# user_xattr    - 启用用户扩展属性

# 数据库专用挂载
mount -o noatime,nodiratime,data=writeback /dev/sda1 /var/lib/mysql

# /tmp 标准挂载
mount -o noexec,nosuid,nodev /tmp

# NFS 挂载
mount -o vers=4,noatime,rsize=32768,wsize=32768,hard,intr server:/share /mnt/nfs
```

### 7. 文件系统类型相关参数

```bash
# ext4 优化
tune2fs -o journal_data_writeback /dev/sda1    # 数据不写日志
tune2fs -O ^has_journal /dev/sda1              # 移除日志（不推荐生产）
tune2fs -m 1 /dev/sda1                          # 预留空间 1%（默认 5%）
tune2fs -l /dev/sda1 | grep "Reserved block count"

# ext4 文件系统参数
sysctl fs.ext4.inode-cache
sysctl fs.ext4.lazy-itable

# XFS 优化（高性能）
xfs_info /dev/sda1
# 查看 allocation group、log size 等

# XFS 日志优化
mkfs.xfs -l size=128m,lazy-count=1 /dev/sda1
# size=128m     - 日志大小
# lazy-count=1  - 延迟计数

# Btrfs 优化
mount -o compress=zstd,space_cache=v2,autodefrag /dev/sda1 /mnt

# F2FS 优化（闪存）
mkfs.f2fs -l label -o compress_algorithm=lz4 /dev/sda1
```

### 8. 文件描述符优化配置

```bash
# /etc/sysctl.conf 推荐配置
fs.file-max = 2097152                       # 系统级 fd 上限
fs.nr_open = 1048576                       # 单进程 fd 上限
fs.aio-max-nr = 1048576                    # 异步 I/O 上限
fs.dentry-max = 2000000                    # dcache 最大
fs.inode-max = 2000000                     # inode 处理上限
fs.file-max = 2097152

# /etc/security/limits.conf 推荐配置
* soft nofile 1048576
* hard nofile 1048576
* soft nproc 65535
* hard nproc 65535

# systemd 服务覆盖
systemctl edit <service>.service
[Service]
LimitNOFILE=1048576
LimitNPROC=65535
```

### 9. 内存与 VFS 相关参数

```bash
# 内存回收
sysctl vm.swappiness                    # 默认 60
sysctl vm.vfs_cache_pressure           # 默认 100

# 数据库服务器（推荐低 swappiness）
sysctl vm.swappiness = 10
sysctl vm.vfs_cache_pressure = 50      # 减少 VFS 缓存回收

# Web 服务器（推荐高 swappiness）
sysctl vm.swappiness = 100
sysctl vm.vfs_cache_pressure = 200     # 倾向保留 VFS 缓存

# min_free_kbytes（最低保留内存）
sysctl vm.min_free_kbytes = 524288      # 512MB

# zone_reclaim_mode（NUMA 推荐 0）
sysctl vm.zone_reclaim_mode = 0
```

### 10. 各场景推荐配置

#### 数据库服务器

```bash
# /etc/sysctl.d/99-database.conf
vm.swappiness = 1
vm.dirty_ratio = 5
vm.dirty_background_ratio = 2
vm.dirty_expire_centisecs = 1500
vm.dirty_writeback_centisecs = 100

fs.file-max = 2097152
fs.aio-max-nr = 1048576
fs.dentry-max = 2000000

# /etc/security/limits.d/99-database.conf
* soft nofile 1048576
* hard nofile 1048576
```

#### Web 服务器

```bash
# /etc/sysctl.d/99-web.conf
vm.swappiness = 30
vm.dirty_ratio = 20
vm.dirty_background_ratio = 10
vm.dirty_expire_centisecs = 3000
vm.dirty_writeback_centisecs = 500

fs.file-max = 1048576
fs.dentry-max = 1000000

# 挂载选项
mount -o noatime,nodiratime,data=writeback /dev/sda1 /var/www
```

#### 大数据/日志服务器

```bash
# /etc/sysctl.d/99-bigdata.conf
vm.swappiness = 100
vm.dirty_ratio = 40
vm.dirty_background_ratio = 20
vm.dirty_expire_centisecs = 60000
vm.dirty_writeback_centisecs = 5000

fs.file-max = 2097152
fs.dentry-max = 5000000

# 挂载选项
mount -o noatime,nodiratime,allocsize=64M /dev/sda1 /data
```

### 11. 验证配置生效

```bash
# 1. 检查所有 VFS 相关参数
sysctl -a 2>/dev/null | grep -E "^fs\.|^vm\.(dirty|swappiness|min_free)"

# 2. 检查 fd 限制
ulimit -n
cat /proc/sys/fs/file-nr

# 3. 检查缓存状态
free -h
cat /proc/meminfo | grep -E "Cached|Buffers|Dirty|Writeback"
cat /proc/slabinfo | grep -E "dentry|inode"

# 4. 检查挂载选项
findmnt -o TARGET,SOURCE,FSTYPE,OPTIONS

# 5. 检查 IO 统计
cat /proc/diskstats | head
iostat -dx 1 5

# 6. 性能基准测试
fio --name=randread --ioengine=libaio --direct=1 \
    --filename=/dev/sda1 --bs=4k --numjobs=1 \
    --size=1G --runtime=30 --time_based
```

### 12. 持久化配置方法

```bash
# 方法 1：/etc/sysctl.conf（推荐）
echo "fs.file-max = 2097152" >> /etc/sysctl.conf
sysctl -p                                  # 立即生效

# 方法 2：/etc/sysctl.d/*.conf（推荐，更清晰）
cat > /etc/sysctl.d/99-vfs-tuning.conf << 'EOF'
fs.file-max = 2097152
fs.dentry-max = 2000000
vm.swappiness = 10
vm.dirty_ratio = 5
vm.dirty_background_ratio = 2
EOF
sysctl -p /etc/sysctl.d/99-vfs-tuning.conf

# 方法 3：/etc/security/limits.conf
cat > /etc/security/limits.d/99-vfs.conf << 'EOF'
* soft nofile 1048576
* hard nofile 1048576
* soft nproc 65535
* hard nproc 65535
EOF

# 方法 4：systemd 服务覆盖
mkdir -p /etc/systemd/system/<service>.service.d
cat > /etc/systemd/system/<service>.service.d/limits.conf << 'EOF'
[Service]
LimitNOFILE=1048576
LimitNPROC=65535
EOF
systemctl daemon-reload
systemctl restart <service>

# 方法 5：grub 内核参数（启动时生效）
vim /etc/default/grub
GRUB_CMDLINE_LINUX="... fs.file-max=2097152 fs.dentry-max=2000000"
grub2-mkconfig -o /boot/grub2/grub.cfg
reboot
```

### 13. 调优前后对比验证

```bash
# 1. 调优前记录基线
sysctl fs.file-max > baseline.txt
sysctl fs.dentry-max >> baseline.txt
ulimit -n >> baseline.txt

# 2. 压测对比
# 调整前
fio --name=test --ioengine=libaio --direct=1 \
    --filename=/mnt/test --bs=4k --numjobs=4 \
    --size=1G --runtime=60 --time_based \
    --rw=randread > before.txt

# 调整参数
sysctl -w fs.file-max=2097152
sysctl -w fs.dentry-max=2000000
mount -o remount,noatime,nodiratime /mnt

# 调整后
fio ... > after.txt

# 3. 对比结果
diff before.txt after.txt

# 4. 应用性能对比
# wrk -t4 -c100 -d60s http://localhost:8080/ > before_perf.txt
# wrk ... > after_perf.txt
# diff before_perf.txt after_perf.txt
```

### 14. 内核参数速查表

| 参数 | 路径 | 默认值 | 推荐值 | 适用 | 作用 |
|------|------|--------|--------|------|------|
| fs.file-max | /proc/sys/fs/file-max | 内存/10K | 2097152 | 系统 | 系统级最大文件描述符数量（所有进程总和） |
| fs.nr_open | /proc/sys/fs/nr_open | 1048576 | 1048576 | 进程 | 单个进程可打开的最大文件描述符数 |
| fs.dentry-max | /proc/sys/fs/dentry-max | 内存/4K | 2000000 | 系统 | dentry 缓存最大条目数（加速路径查找） |
| fs.inode-max | /proc/sys/fs/inode-max | 内存/250 | 2000000 | 系统 | inode 缓存最大条目数（加速元数据访问） |
| fs.aio-max-nr | /proc/sys/fs/aio-max-nr | 65536 | 1048576 | 异步 I/O | 系统级最大并发异步 I/O 请求数 |
| vm.dirty_ratio | /proc/sys/vm/dirty_ratio | 20 | 5-40 | 数据库/Web | 内存脏页占比上限（%），超过时开始同步写磁盘 |
| vm.dirty_background_ratio | /proc/sys/vm/dirty_background_ratio | 10 | 2-20 | 数据库/Web | 后台回写阈值（%），达到时后台异步刷盘 |
| vm.dirty_expire_centisecs | /proc/sys/vm/dirty_expire_centisecs | 3000 | 1500-60000 | 数据库/Web | 脏页过期时间（厘秒），超时强制写回 |
| vm.dirty_writeback_centisecs | /proc/sys/vm/dirty_writeback_centisecs | 500 | 100-5000 | 数据库/Web | 后台写回线程唤醒间隔（厘秒） |
| vm.swappiness | /proc/sys/vm/swappiness | 60 | 1-100 | 数据库 1-10 | 内存回收时倾向 swap 的程度（0=尽量不swap，100=积极swap） |
| vm.vfs_cache_pressure | /proc/sys/vm/vfs_cache_pressure | 100 | 50-200 | 数据库 50 | VFS 缓存回收倾向（相对pagecache_inode回收，<100优先保留） |
| vm.min_free_kbytes | /proc/sys/vm/min_free_kbytes | 自动 | 内存 1-3% | 所有 | 系统必须保留的最小空闲内存（防止OOM） |
| ulimit -n | /etc/security/limits.conf | 1024 | 1048576 | 服务 | 用户/进程可打开的最大文件描述符数 |

### 15. 各场景推荐参数组合

```text
数据库服务器：
  fs.file-max = 2097152
  fs.aio-max-nr = 1048576
  fs.dentry-max = 2000000
  vm.swappiness = 1
  vm.dirty_ratio = 5
  vm.dirty_background_ratio = 2
  ulimit -n = 1048576
  mount: noatime,nodiratime,data=writeback

Web 服务器：
  fs.file-max = 1048576
  fs.dentry-max = 1000000
  vm.swappiness = 30
  vm.dirty_ratio = 20
  vm.dirty_background_ratio = 10
  ulimit -n = 65535
  mount: noatime,nodiratime,data=writeback

大数据/日志服务器：
  fs.file-max = 2097152
  fs.dentry-max = 5000000
  vm.swappiness = 100
  vm.dirty_ratio = 40
  vm.dirty_background_ratio = 20
  ulimit -n = 1048576
  mount: noatime,nodiratime,allocsize=64M

容器宿主机：
  fs.file-max = 2097152
  fs.dentry-max = 2000000
  fs.inode-max = 2000000
  vm.swappiness = 10
  vm.dirty_ratio = 15
  ulimit -n = 1048576
  mount: noatime,nodiratime

高 IO 数据库（NVMe SSD）：
  fs.file-max = 2097152
  fs.aio-max-nr = 1048576
  vm.swappiness = 1
  vm.dirty_ratio = 5
  vm.dirty_background_ratio = 2
  ulimit -n = 1048576
  mount: noatime,nodiratime,data=writeback,barrier=0
```

---

## 附录：参考资源

```
- Linux 内核文档 VFS: https://www.kernel.org/doc/Documentation/filesystems/vfs.txt
- Linux 内核源码 fs/ 目录: https://elixir.bootlin.com/linux/latest/source/fs/
- Understanding the Linux Kernel: VFS 章节
- Linux Device Drivers: 第 12 章 VFS
- proc_filesystems(5): 已注册文件系统列表
- stat(2): 文件元数据结构
- mount(8): 文件系统挂载
```

## 快速参考卡

```
VFS 四大对象：
  super_block  - 文件系统元数据
  inode        - 文件元数据
  dentry       - 路径条目
  file         - 打开的文件

关键命令：
  df -h / df -i           - 空间 / inode
  mount / findmnt         - 挂载点
  stat <file>            - 元数据
  lsof -p <pid>           - 进程 fd
  strace -e openat <cmd>  - 跟踪系统调用

性能优化：
  mount -o noatime        - 不更新访问时间
  sysctl vm.dirty_ratio   - 调整脏页
  ulimit -n 65535         - 调高 fd 上限

文件系统选型：
  通用 → ext4 / XFS
  大文件 → XFS
  数据库 → XFS / ext4
  容器 → overlay2
```
