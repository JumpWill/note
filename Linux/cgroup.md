# Linux cgroup 完全指南 (Control Groups)

> 本文档系统讲解 Linux cgroup（控制组）的概念、原理、各类资源控制器（CPU/内存/IO/网络等）以及实战应用。

## 一、cgroup 概述

### 1.1 什么是 cgroup

**cgroup**（Control Groups，控制组）是 Linux 内核提供的**资源管理机制**，用于**限制、记录、隔离进程组**所使用的物理资源（CPU、内存、磁盘 I/O、网络等）。

**核心功能：**

- **资源限制**（Resource Limiting）：限制进程组使用的资源量
- **资源优先级**（Prioritization）：控制进程组获得资源的优先级
- **资源记录**（Accounting）：记录进程组使用的资源量
- **资源隔离**（Isolation）：不同进程组使用独立资源空间
- **资源控制**（Control）：挂起/恢复进程组

**应用场景：**

- 容器（Docker、K8s）的资源隔离
- 虚拟化（KVM）
- Linux 进程资源管理
- cgroups v2 已成为 systemd 的一部分

### 1.2 cgroup 与其他资源管理技术对比

| 工具 | 功能 | 作用范围 | 特点 |
|------|------|----------|------|
| **cgroup** | 资源限制、隔离、统计 | 进程组 | 内核级，细粒度 |
| **ulimit** | 资源限制（per-process） | 单个进程 | 用户级 shell 限制 |
| **systemd unit** | 资源管理（基于 cgroup） | 服务 | 简化使用 |
| **nice/renice** | 进程优先级 | 单个进程 | CPU 调度优先级 |
| **cgroups v2** | 统一资源管理 | 进程组 | 新一代 |

**关系：**

- `ulimit` 是用户级工具，最终会调用 cgroup 设置
- `systemd` 使用 cgroup 管理服务
- `cgroup` 是底层机制，其他工具通常基于它

---

## 二、cgroup 基础概念

### 2.1 核心概念

**cgroup** 是一个**层级化**的进程组管理机制。

**关键概念：**

- **Task（任务）**：进程或线程
- **Control Group（控制组）**：一组任务的集合
- **Hierarchy（层级）**：cgroup 形成的树状结构
- **Subsystem/Resource Controller（子系统/资源控制器）**：管理特定资源的模块

### 2.2 cgroup 三种操作

cgroup 提供三种核心操作：

**1. 资源限制（Limiting）**

- 限制进程组使用的最大资源量
- 超过限制会被阻止（OOM、限流等）

**2. 资源优先级（Prioritization）**

- 控制不同进程组的资源分配比例
- 优先级高的组获得更多资源

**3. 资源统计（Accounting）**

- 记录进程组实际使用的资源量
- 用于计费、监控、审计

### 2.3 cgroup v1 vs v2 对比

| 特性 | cgroup v1 | cgroup v2 |
|------|----------|----------|
| **发布** | Linux 2.6.24 (2008) | Linux 4.5 (2016) |
| **层级** | 多层级（每子系统独立） | 统一单层级 |
| **控制器** | 分散（cpu、memory、blkio 等） | 统一（cgroup.subtree_control） |
| **接口** | 多个 mount 点 | 统一 `/sys/fs/cgroup/` |
| **兼容性** | 旧 | 向后兼容 v1 |
| **特性** | 简单但分裂 | 统一、强大、新特性多 |
| **内核要求** | 任意 | 4.5+ |
| **systemd** | 支持 | 强烈推荐 |

---

## 三、cgroup v1 详解

### 3.1 v1 子系统（Subsystem）

cgroup v1 包含多个独立的子系统，每个负责一种资源：

| 子系统 | 路径 | 作用 |
|------|------|------|
| `cpu` | `/sys/fs/cgroup/cpu/` | CPU 时间限制（份额、周期） |
| `cpuacct` | `/sys/fs/cgroup/cpuacct/` | CPU 使用统计 |
| `cpuset` | `/sys/fs/cgroup/cpuset/` | 绑定特定 CPU 核心 |
| `memory` | `/sys/fs/cgroup/memory/` | 内存限制、统计 |
| `blkio` | `/sys/fs/cgroup/blkio/` | 块设备 I/O 控制 |
| `devices` | `/sys/fs/cgroup/devices/` | 设备访问控制 |
| `freezer` | `/sys/fs/cgroup/freezer/` | 挂起/恢复进程组 |
| `net_cls` | `/sys/fs/cgroup/net_cls/` | 网络分类（标记包） |
| `net_prio` | `/sys/fs/cgroup/net_prio/` | 网络包优先级 |
| `ns` | `/sys/fs/cgroup/ns/` | 命名空间 |
| `pids` | `/sys/fs/cgroup/pids/` | 进程数限制 |
| `hugetlb` | `/sys/fs/cgroup/hugetlb/` | 大页内存 |
| `rdma` | `/sys/fs/cgroup/rdma/` | RDMA 资源 |
| `misc` | `/sys/fs/cgroup/misc/` | 其他资源 |

### 3.2 v1 层级结构

cgroup v1 每个子系统有**独立的层级树**：

```
cpu:
├── /sys/fs/cgroup/cpu/
│   ├── user.slice/
│   │   ├── user-1000.slice/
│   │   │   ├── session-c1.scope/
│   │   │   └── user@1000.service/
│   │   └── user-1001.slice/
│   └── system.slice/
│       ├── docker-<id>.scope/
│       └── kubepods.slice/
└── /

memory:
├── /sys/fs/cgroup/memory/
│   ├── user.slice/
│   └── system.slice/
└── /

cpu 树和 memory 树是独立的！
```

**特点：**

- 每个子系统有独立挂载点
- 同一进程可在多个树中
- 灵活性高但配置复杂
- 子系统间可能不一致

### 3.3 v1 文件接口

每个 cgroup 是一个目录，包含以下文件：

**通用文件：**

- `tasks`：cgroup 中的所有进程 PID 列表
- `cgroup.procs` 或 `cgroup.events`：进程事件通知
- `notify_on_release`：子 cgroup 空时是否通知
- `release_agent`：释放时执行的脚本

**资源限制文件（以 cpu 为例）：**

- `cpu.cfs_quota_us`：周期内 CPU 时间配额（微秒）
- `cpu.cfs_period_us`：CPU 周期（微秒）
- `cpu.shares`：CPU 份额（默认 1024）
- `cpu.rt_runtime_us：实时进程运行时间
- `cpu.rt_period_us`：实时进程周期

**内存限制文件：**

- `memory.limit_in_bytes`：内存使用上限
- `memory.soft_limit_in_bytes`：软限制
- `memory.max_usage_in_bytes`：观察到的最大使用量
- `memory.usage_in_bytes`：当前使用量
- `memory.failcnt`：触发限制的次数
- `memory.oom_control`：是否开启 OOM killer

---

## 四、cgroup v2 详解

### 4.1 v2 统一层级

cgroup v2 采用**统一层级**，所有资源控制器在同一棵树中：

```
/sys/fs/cgroup/
├── system.slice/        ← 系统服务
│   ├── docker-<id>.scope/
│   ├── kubepods.slice/
│   │   ├── kubepods-pod<id>.slice/
│   │   └── cri-containerd-<id>.scope/
│   └── sshd.service/
├── user.slice/          ← 用户会话
│   ├── user-1000.slice/
│   │   ├── session-c1.scope/
│   │   └── gnome-shell.service/
│   └── user-1001.slice/
└── /
```

**优势：**

- 统一视图，避免不一致
- 单一挂载点，简化管理
- 支持新资源（psi、eBPF 等）
- 改进的资源分配算法

### 4.2 v2 接口文件

**cgroup v2 核心文件：**

- `cgroup.controllers`：可用控制器
- `cgroup.subtree_control`：子 cgroup 启用的控制器
- `cgroup.procs` 或 `cgroup.events`：进程成员
- `cgroup.freeze`：冻结控制
- `cgroup.max.descendants`：最大子 cgroup 数
- `cgroup.max.depth`：最大层级深度
- `cgroup.stat`：统计信息
- `cgroup.threads`：线程成员
- `cgroup.events.local`：本地事件

**资源控制文件示例（cpu）：**

- `cpu.max`：带宽限制（`$MAX $PERIOD`）
- `cpu.weight`：权重（1-10000，默认 100）
- `cpu.idle`：是否视为空闲
- `cpu.burst`：突发允许的微秒数
- `cpu.stat`：CPU 统计

**资源控制文件示例（memory）：**

- `memory.max`：硬限制
- `memory.high`：软限制（触发回收）
- `memory.low`：保护（不回收）
- `memory.swap.max`：swap 上限
- `memory.swap.high`：swap 软限制
- `memory.events`：内存事件通知
- `memory.current`：当前使用
- `memory.stat`：详细统计

### 4.3 v2 关键概念

**Weight（权重）：**

- 范围 1-10000
- 默认 100
- 比例分配资源
- 替代 v1 的 shares 概念

**Limit vs High：**

- `memory.max`：硬限制，触发 OOM
- `memory.high`：软限制，触发回收但不杀进程
- 区别于 v1 的 hard limit / soft limit

**Pressure Stall Information (PSI)：**

- v2 新特性
- 衡量资源竞争程度
- 文件：`cpu.pressure`、`memory.pressure`、`io.pressure`
- 三种状态：some/full
- 用于性能监控和自动扩缩容

---

## 五、CPU 资源控制

### 5.1 cgroup v1 CPU 控制

**CPU 份额（shares）：**

```bash
# 查看默认份额
cat /sys/fs/cgroup/cpu/cpu.shares
# 1024

# 创建子 cgroup
mkdir /sys/fs/cgroup/cpu/test
cd /sys/fs/cgroup/cpu/test

# 设置份额
echo 512 > cpu.shares
# test cgroup 可获得 50% CPU（512/1024）

# 添加进程
echo $$ > tasks
# 进程 PID 加入

# 删除
cd ..
rmdir test
```

**CFS（Completely Fair Scheduler）带宽：**

```bash
# 设置周期（默认 100ms = 100000us）
echo 100000 > cpu.cfs_period_us

# 设置配额（每个周期可用的 CPU 时间）
echo 50000 > cpu.cfs_quota_us
# 该 cgroup 每 100ms 可用 50ms CPU，相当于 0.5 核
```

**cpuset 绑定核心：**

```bash
# 创建 cgroup
mkdir /sys/fs/cgroup/cpuset/test

# 绑定到 CPU 0 和 2
echo "0,2" > cpuset.cpus
# 绑定到内存节点 0
echo "0" > cpuset.mems

# 继承
echo 1 > cgroup.clone_children

# 添加进程
echo $$ > tasks
```

### 5.2 cgroup v2 CPU 控制

**CPU 带宽：**

```bash
# 创建 cgroup
mkdir /sys/fs/cgroup/test

cd /sys/fs/cgroup/test

# 格式：$MAX $PERIOD
# 例如：50000 100000 = 50% 单核
echo "50000 100000" > cpu.max
# 允许每 100ms 使用 50ms

# 2 核限制
echo "200000 100000" > cpu.max

# 无限制（删除）
echo "max 100000" > cpu.max
```

**CPU 权重：**

```bash
# 权重（1-10000，默认 100）
echo 200 > cpu.weight
# 该 cgroup 可获得 2 倍默认份额的 CPU

# 多 cgroup 资源分配示例：
# cgroup A: cpu.weight=100  → 25%
# cgroup B: cpu.weight=300  → 75%
# 总和为 400，A 占 100/400=25%
```

**CPU Burst（突发）：**

```bash
# 允许突发（v2.6+）
echo 50000 100000 > cpu.max
echo 100000 > cpu.burst
# 平时 50ms/100ms，突发可达 100ms/100ms

# 查看 burst 余额
cat cpu.burst.current
```

### 5.3 CPU 控制实战示例

**Web 服务器 CPU 限制：**

```bash
# cgroup v2
# 创建 cgroup
mkdir /sys/fs/cgroup/web

# 限制为 1.5 核
echo "150000 100000" > web/cpu.max
# 权重 200（比默认高 2 倍）
echo 200 > web/cpu.weight

# 将 Nginx 进程加入
nginx_pid=$(pgrep nginx)
echo $nginx_pid > web/cgroup.procs
```

**批量任务 CPU 限制：**

```bash
# cgroup v2
mkdir /sys/fs/cgroup/batch

# 限制 0.5 核
echo "50000 100000" > batch/cpu.max
# 权重低（优先级低）
echo 50 > batch/cpu.weight

# 测试
yes > /dev/null &
pid=$!
echo $pid > batch/cgroup.procs
# 观察 CPU 占用被限制在 50%
top -p $pid
```

---

## 六、内存资源控制

### 6.1 cgroup v1 内存控制

**内存限制：**

```bash
# 创建 cgroup
mkdir /sys/fs/cgroup/memory/test

cd /sys/fs/cgroup/memory/test

# 硬限制（100MB）
echo 100M > memory.limit_in_bytes

# 软限制（50MB，触发回收但不杀进程）
echo 50M > memory.soft_limit_in_bytes

# 关闭 OOM killer（慎用！）
echo 1 > memory.oom_control
# 0 = 启用 OOM killer（默认）
# 1 = 禁用 OOM killer，进程可继续分配直到硬限制

# 查看使用情况
cat memory.usage_in_bytes
cat memory.max_usage_in_bytes
cat memory.failcnt
# failcnt = 触发限制的次数
```

**内存统计：**

```bash
# 详细内存使用
cat memory.stat
# cache 12345
# rss 67890
# rss_huge 0
# mapped_file 1234
# dirty 100
# ...

# 内存事件
cat memory.events
# low 0
# high 5
# max 0
# oom 0
# oom_kill 0
```

**OOM killer 控制：**

```bash
# 调整 OOM 分数（-1000 ~ 1000）
# -1000 = 永不被杀
# 1000 = 必定被杀
echo -500 > memory.oom_score_adj

# 或为进程设置
echo -800 > /proc/$PID/oom_score_adj
```

### 6.2 cgroup v2 内存控制

**内存限制：**

```bash
# 创建 cgroup
mkdir /sys/fs/cgroup/test

cd /sys/fs/cgroup/test

# 硬限制（100MB）
echo 100M > memory.max

# 软限制（50MB，触发回收）
echo 50M > memory.high

# 保护（不回收）
echo 10M > memory.low

# swap 限制
echo 50M > memory.swap.max
echo 30M > memory.swap.high
```

**内存事件：**

```bash
# v2 内存事件
cat memory.events

# local 事件（自定义）
cat memory.events.local
```

**内存压力（PSI）：**

```bash
# 读取内存压力
cat memory.pressure
# some avg10=0.00 avg60=0.00 avg300=0.00 total=0
# full avg10=0.00 avg60=0.00 avg300=0.00 total=0

# some = 至少一个任务在内存竞争中阻塞
# full = 所有任务都在内存竞争中阻塞（100% 阻塞）
# avg10 = 10 秒窗口
# avg60 = 60 秒窗口
# avg300 = 5 分钟窗口
# total = 总时间（毫秒）
```

### 6.3 内存控制实战

**Web 应用内存限制：**

```bash
# cgroup v2
# 创建 cgroup
mkdir /sys/fs/cgroup/webapp

# 内存硬限制 1GB
echo 1G > webapp/memory.max

# 内存软限制 800MB（触发主动回收）
echo 800M > webapp/memory.high

# swap 禁用
echo 0 > webapp/memory.swap.max

# OOM 优先级（避免被 OOM killer 选中）
# 注意：在 cgroup v2 中，需要将进程加入 cgroup 后设置 oom_score_adj
nginx_pid=$(pgrep nginx)
echo -500 > /proc/$nginx_pid/oom_score_adj

# 将进程加入 cgroup
echo $nginx_pid > webapp/cgroup.procs
```

**Java 应用内存限制：**

```bash
# 创建 cgroup
mkdir /sys/fs/cgroup/java-app

# 堆内存 1GB
echo 1G > java-app/memory.max

# 非堆 256MB（off-heap）
echo 256M > java-app/memory.high

# JVM 自身会管理堆，但 OOM 时系统也会限制
```

---

## 七、磁盘 I/O 资源控制

### 7.1 cgroup v1 块 I/O 控制

**blkio 限制：**

```bash
# 创建 cgroup
mkdir /sys/fs/cgroup/blkio/test

cd /sys/fs/cgroup/blkio/test

# 限制读 IO（10MB/s）
echo '8:0 10485760' > blkio.throttle.read_bps_device
# 8:0 是主设备号:次设备号
# 10485760 = 10 * 1024 * 1024

# 限制写 IO（5MB/s）
echo '8:0 5242880' > blkio.throttle.write_bps_device

# 限制 IOPS（读 1000/s）
echo '8:0 1000' > blkio.throttle.read_iops_device

# 限制 IOPS（写 500/s）
echo '8:0 500' > blkio.throttle.write_iops_device

# 权重（500-10000，默认 500）
echo 1000 > blkio.weight
# 权重高的组获得更多 IO 带宽

# 查看设备号
ls -la /dev/sda
# brw-rw---- 1 root disk 8, 0 ... /dev/sda
# 主设备号 8，次设备号 0
```

**blkio 实战：**

```bash
# 数据库 cgroup
mkdir /sys/fs/cgroup/blkio/database

# 限制数据库磁盘 IO
echo '8:0 104857600' > database/blkio.throttle.read_bps_device   # 100MB/s
echo '8:0 52428800' > database/blkio.throttle.write_bps_device   # 50MB/s

# 高权重（数据库优先）
echo 2000 > database/blkio.weight
```

### 7.2 cgroup v2 I/O 控制

**I/O 带宽限制：**

```bash
# 创建 cgroup
mkdir /sys/fs/cgroup/test

cd /sys/fs/cgroup/test

# 限制读带宽
echo "10485760" > io.max
# 格式：$MAJOR:$MINOR $BYTES

# 多设备限制
cat > io.max << 'EOF'
8:0 10485760
8:16 5242880
EOF

# I/O 权重（1-10000，默认 100）
echo 500 > io.weight

# 查看权重分配
cat io.weight
```

**I/O 统计：**

```bash
# 详细 I/O 统计
cat io.stat
# 8:0 rbytes=... wbytes=... rios=... wios=...
# 8:16 rbytes=... wbytes=... rios=... wios=...

# 当前 I/O 状态
cat io.pressure
# some avg10=0.00 avg60=0.00 total=0
# full avg10=0.00 avg60=0.00 total=0
```

### 7.3 I/O 控制实战

**Docker 容器磁盘限制：**

```yaml
# docker run 限制 IO
docker run -d \
  --name postgres \
  --device-read-bps /dev/sda:50mb \
  --device-write-bps /dev/sda:30mb \
  --device-read-iops /dev/sda:500 \
  --device-write-iops /dev/sda:300 \
  postgres:15
```

**K8s 资源限制：**

```yaml
apiVersion: apps/v1
kind: Pod
metadata:
  name: database
spec:
  containers:
  - name: postgres
    image: postgres:15
    resources:
      requests:
        cpu: 500m
        memory: 1Gi
      limits:
        cpu: 2000m
        memory: 4Gi
```

---

## 八、网络资源控制

### 8.1 cgroup v1 网络控制

**net_cls（网络分类）：**

```bash
# 创建 cgroup
mkdir /sys/fs/cgroup/net_cls/test

# 设置 classid（流量控制标识符）
echo 0x10001 > net_cls.classid
# 0x10001 = 65537

# 配置 tc 使用这个 classid
# 需要结合 iptables 或 tc 工具使用
```

**net_prio（网络包优先级）：**

```bash
# 创建 cgroup
mkdir /sys/fs/cgroup/net_prio/test

# 设置接口 eth0 的优先级
echo "eth0 5" > net_prio.ifpriomap
# 5 = 最高优先级

# 设置进程的优先级
echo "1234 5" > net_prio.prio
# 1234 = PID
# 5 = 最高优先级
```

### 8.2 cgroup v2 网络控制

**网络资源 v2 支持有限：**

- v2 主要通过 eBPF/TC 实现网络控制
- cgroup 本身只提供少数接口
- 大部分网络控制由 eBPF 程序完成

### 8.3 Docker 网络限速

**Docker 限制网络带宽：**

```bash
# 限制网络带宽
docker run -d \
  --name webapp \
  --network mynetwork \
  --sysctl net.core.rmem_max=8388608 \
  nginx

# 但 Docker 原生不支持直接限制带宽
# 需要使用 TC（traffic control）实现

# 在容器内使用 TC 限制带宽
docker exec webapp bash -c "tc qdisc add dev eth0 root tbf rate 10mbit burst 32kbit latency 400ms"
```

**K8s 网络策略：**

```yaml
# 网络策略限制网络访问
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: webapp-policy
spec:
  podSelector:
    matchLabels:
      app: webapp
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: frontend
    ports:
    - protocol: TCP
      port: 8080
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: database
    ports:
    - protocol: TCP
      port: 5432
```

---

## 九、进程数（PID）控制

### 9.1 cgroup v1 PID 控制

```bash
# 创建 cgroup
mkdir /sys/fs/cgroup/pids/test

cd /sys/fs/cgroup/pids/test

# 设置最大进程数
echo 100 > pids.max

# 添加进程
echo $$ > tasks

# 查看当前进程数
cat pids.current
cat pids.events
```

### 9.2 cgroup v2 PID 控制

```bash
# 创建 cgroup
mkdir /sys/fs/cgroup/test

cd /sys/fs/cgroup/test

# 设置最大进程数
echo 100 > pids.max

# 启用 PID 控制器
# 必须在 cgroup.subtree_control 中启用
echo "+pids" > ../cgroup.subtree_control

# 查看当前进程数
cat pids.current
# 显示当前子 cgroup 进程数
cat pids.events
```

### 9.3 实战：防止 fork bomb

```bash
# 防止 fork bomb（经典 Linux 防御）
# 设置进程数限制

# 系统级限制
echo 10000 > /sys/fs/cgroup/pids/user.slice/pids.max

# 用户级限制
echo 5000 > /sys/fs/cgroup/pids/user.slice/user-1000.slice/pids.max

# 测试 fork bomb
docker run --rm -it --pids-limit 100 alpine sh -c ":(){ :|:& };:"
# 报错：Resource temporarily unavailable
# 进程数达到 100 限制，无法继续 fork
```

---

## 十、设备访问控制

### 10.1 devices 子系统（v1）

```bash
# 创建 cgroup
mkdir /sys/fs/cgroup/devices/test

cd /sys/fs/cgroup/devices/test

# 允许访问所有设备
echo "a *:* rwm" > devices.allow

# 拒绝所有设备
echo "a *:* r" > devices.list

# 允许访问特定设备
echo "c 1:3 rwm" > devices.allow
# 允许 /dev/null
# c = 字符设备
# 1:3 = 主设备号 1，次设备号 3
# rwm = 读/写/创建(mknod)

# 拒绝特定设备
echo "c 4:0 w" > devices.deny

# 列出允许的设备
cat devices.allow

# 设备列表
cat devices.list
```

### 10.2 cgroup v2 设备控制

```bash
# v2 中没有 devices 控制器
# 设备控制通过 cgroup 之外的方式：
# 1. 文件系统挂载限制
# 2. seccomp 系统调用过滤
# 3. AppArmor/SELinux
# 4. 用户命名空间隔离
```

### 10.3 Docker 设备控制

```bash
# Docker 暴露设备
docker run -d \
  --name redis \
  --device /dev/sda:/dev/sda:rwm \
  redis

# 暴露 GPU
docker run -d \
  --name ml-app \
  --gpus all \
  --device /dev/nvidia0 \
  pytorch/pytorch

# capability 控制
docker run -d \
  --cap-drop ALL \
  --cap-add NET_BIND_SERVICE \
  --security-opt no-new-privileges \
  nginx
```

---

## 十一、freezer 冻结控制

### 11.1 cgroup v1 freezer

```bash
# 冻结进程组
echo FROZEN > /sys/fs/cgroup/freezer/test/freezer.state

# 查看状态
cat /sys/fs/cgroup/freezer/test/freezer.state
# FROZEN

# 解冻
echo THAWED > /sys/fs/cgroup/freezer/test/freezer.state

# 冻结状态：
# FREEZING - 正在冻结
# FROZEN - 已冻结
# THAWED - 已解冻
```

### 11.2 cgroup v2 freezer

```bash
# 冻结
echo 1 > cgroup.freeze

# 解冻
echo 0 > cgroup.freeze

# 查看状态
cat cgroup.freeze
# 1（冻结）或 0（解冻）
```

### 11.3 Docker/K8s 中的使用

**Docker 暂停：**

```bash
# 暂停容器（cgroup freezer）
docker pause myapp
# 容器进程被冻结，但内存保留

# 恢复
docker unpause myapp
```

**K8s 中应用：**

- Pod 创建时短暂冻结
- cgroup v2 默认支持
- 调试时暂停可疑进程

---

## 十二、cgroup 操作实战

### 12.1 工具管理 cgroup

**systemd-run（推荐）：**

```bash
# 限制 CPU 50% 的临时任务
systemd-run --scope --property=CPUQuota=50% -- echo hello

# 限制内存 500MB
systemd-run --scope --property=MemoryMax=500M -- bash

# 限制 1000 个进程
systemd-run --scope --property=TasksMax=1000 -- bash

# 自定义 Slice
systemd-run --slice=myapp.slice --unit=myapp.service --property=CPUQuota=200% -- bash
```

**systemctl 限制服务：**

```bash
# 编辑服务配置
systemctl edit nginx

# 添加限制
[Service]
CPUQuota=200%
MemoryMax=1G
TasksMax=500
IOReadBandwidthMax=/dev/sda 100M
```

**Docker cgroup 操作：**

```bash
# 查看容器 cgroup
docker inspect myapp | grep -A 3 CgroupParent

# 进入容器 cgroup 目录
ls /sys/fs/cgroup/system.slice/docker-<id>.scope/

# 实时修改
echo 1000 > cpu.max
# 不需要重启容器
```

### 12.2 创建自定义 cgroup

**手动创建：**

```bash
# v1 方式
mkdir /sys/fs/cgroup/cpu/myapp
echo 50000 > /sys/fs/cgroup/cpu/myapp/cpu.cfs_quota_us
echo 100000 > /sys/fs/cgroup/cpu/myapp/cpu.cfs_period_us
echo 1024 > /sys/fs/cgroup/cpu/myapp/cpu.shares

mkdir /sys/fs/cgroup/memory/myapp
echo 1G > /sys/fs/cgroup/memory/myapp/memory.limit_in_bytes

# 启用子 cgroup 继承
echo 1 > /sys/fs/cgroup/cpu/myapp/cgroup.clone_children

# v2 方式
mkdir /sys/fs/cgroup/myapp
echo "+cpu +memory" > /sys/fs/cgroup/cgroup.subtree_control
echo "50000 100000" > /sys/fs/cgroup/myapp/cpu.max
echo 1G > /sys/fs/cgroup/myapp/memory.max
```

**systemd-cgtop 监控：**

```bash
# 实时监控 cgroup 资源使用
systemd-cgtop

# 输出：
# Path                                Tasks   %CPU   Memory
# /                                  312     5.2    8.5G
# /system.slice/docker-<id>.scope     1       1.5    500M
# /system.slice/kubepods.slice/...   50      20.3   4.2G
```

**systemd-run 限制示例：**

```bash
# 编译任务：限制 1 核 1GB
systemd-run --scope \
  --property="CPUQuota=100%" \
  --property="MemoryMax=1G" \
  --property="TasksMax=10" \
  make -j4

# 数据库：限制 IO 优先级高
systemd-run --scope \
  --property="IOWeight=1000" \
  --property="CPUWeight=500" \
  --property="MemoryMax=8G" \
  postgres

# 批处理任务：低优先级
systemd-run --scope \
  --property="CPUWeight=50" \
  --property="IOWeight=10" \
  --property="MemoryMax=2G" \
  backup-script.sh
```

---

## 十三、生产实战案例

### 13.1 限制进程 CPU 使用

```bash
# 创建一个 CPU 密集型测试进程
stress-ng --cpu 4 --timeout 60s &
pid=$!

# 查看它的 cgroup
cat /proc/$pid/cgroup
# 0::/system.slice/session-3.scope

# 限制它的 CPU 为 50%
mkdir /sys/fs/cgroup/system.slice/session-3.scope
echo 50000 > /sys/fs/cgroup/system.slice/session-3.scope/cpu.max
echo 100000 > /sys/fs/cgroup/system.slice/session-3.scope/cpu.max
# 注意：完整路径是 /sys/fs/cgroup/system.slice/session-3.scope/cpu.max

# 查看效果
top -p $pid
# CPU 占用从 400% 降到 50%
```

### 13.2 限制 Java 应用的内存

```bash
# 启动 Java 应用
java -jar myapp.jar &
pid=$!

# 设置内存限制为 1GB
echo $pid > /sys/fs/cgroup/memory/myapp/cgroup.procs
echo 1G > /sys/fs/cgroup/memory/myapp/memory.max

# 监控
cat /sys/fs/cgroup/memory/myapp/memory.current
cat /sys/fs/cgroup/memory/myapp/memory.events
```

### 13.3 防止 fork bomb

```bash
# 系统级防止 fork bomb
# 在 /etc/security/limits.conf 添加
# * hard nproc 10000

# cgroup 级别
mkdir /sys/fs/cgroup/pids/user.slice
echo 5000 > /sys/fs/cgroup/pids/user.slice/pids.max

# 测试
bash -c ":(){ :|:& };:"
# 几秒后：
# bash: fork: Resource temporarily unavailable
```

### 13.4 限制数据库 IO

```bash
# 创建数据库 cgroup
mkdir /sys/fs/cgroup/blkio/database

# 限制磁盘 IO
echo '8:0 104857600' > /sys/fs/cgroup/blkio/database/blkio.throttle.read_bps_device   # 100MB/s
echo '8:0 52428800' > /sys/fs/cgroup/blkio/database/blkio.throttle.write_bps_device  # 50MB/s
echo 2000 > /sys/fs/cgroup/blkio/database/blkio.weight

# 将 MySQL 进程加入
mysql_pid=$(pgrep mysqld)
echo $mysql_pid > /sys/fs/cgroup/blkio/database/tasks

# 验证
cat /sys/fs/cgroup/blkio/database/blkio.throttle.read_bps_device
```

---

## 十四、cgroup 在容器中的应用

### 14.1 Docker 中的 cgroup

**Docker 默认使用 cgroup v1：**

```bash
# 查看 Docker 容器使用的 cgroup
docker run -d --name myapp nginx
docker inspect myapp | grep CgroupParent
# 0::/docker-<container-id>

# 进入容器 cgroup 目录
ls /sys/fs/cgroup/system.slice/docker-<id>.scope/
# cpu.max  memory.max  cgroup.procs  etc.
```

**Docker 资源限制参数：**

```bash
# CPU 限制
docker run --cpus=1.5 nginx              # 1.5 核
docker run --cpu-shares=512 nginx       # 权重

# 内存限制
docker run -m 1g nginx                  # 硬限制
docker run --memory-reservation 512m nginx  # 软限制

# IO 限制
docker run --device-read-bps /dev/sda:100mb nginx
docker run --device-write-iops /dev/sda:1000 nginx

# PID 限制
docker run --pids-limit 200 nginx       # 最多 200 进程
```

### 14.2 K8s 中的 cgroup

**K8s 通过 kubelet 使用 cgroup：**

```yaml
# K8s 自动将 Pod 放入 cgroup
# 默认路径：/sys/fs/cgroup/<subsystem>/kubepods/...

# 查看 Pod 的 cgroup
kubectl exec myapp -- cat /proc/self/cgroup
# 0::/kubepods.slice/kubepods-burstable.slice/...
```

**资源限制在 cgroup 中的体现：**

```yaml
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: app
    image: nginx
    resources:
      requests:
        cpu: 100m        # 转换为 cgroup 的 shares
        memory: 128Mi   # 转换为 cgroup 的 memory.limit
      limits:
        cpu: 500m        # 转换为 cgroup 的 cpu.max
        memory: 256Mi   # 转换为 cgroup 的 memory.max
```

**K8s cgroup driver 配置：**

```yaml
# kubelet 配置
apiVersion: kubelet.config.k8s.io/v1beta1
kind: KubeletConfiguration
cgroupDriver: systemd  # 推荐 K8s 1.22+
# 或 cgroupfs
```

### 14.3 容器 OOM 处理

**Docker OOM：**

```bash
# Docker 容器 OOM 时
# 1. 内存超限 → 内核 OOM killer
# 2. 选择最耗内存的进程杀掉
# 3. 容器状态变为 OOMKilled
# 4. exit code 137

# 调整 OOM 优先级
docker run --oom-score-adj -500 myapp
# 减少被 OOM killer 选中的概率
```

**K8s OOM：**

```yaml
# Pod 内存超限行为
spec:
  containers:
  - name: app
    resources:
      limits:
        memory: 1Gi
  # 内存超限 → OOM killed → Pod 重启
  # restartPolicy: Always（默认）

# 调整 OOM 优先级
spec:
  containers:
  - name: app
    securityContext:
      oomScoreAdj: -500  # 减少被杀概率
```

---

## 十五、cgroup v2 迁移

### 15.1 检查系统版本

```bash
# 检查 cgroup 版本
stat -fc %T /sys/fs/cgroup/
# tmpfs = v1
# cgroup2fs = v2

# 或者
cat /proc/filesystems | grep cgroup
# nodev cgroup
# nodev cgroup2

# 或者
cat /proc/self/cgroup
# 0::/      # v1
# 0::/user.slice/...   # v2
```

### 15.2 v1 升级到 v2

```bash
# 启用 v2
# 启动参数
GRUB_CMDLINE_LINUX="systemd.unified_cgroup_hierarchy=1"
sudo update-grub

# 或者启动时
sudo grubby --update-kernel=ALL --args="systemd.unified_cgroup_hierarchy=1"
sudo reboot

# 验证
stat -fc %T /sys/fs/cgroup/
# cgroup2fs
```

### 15.3 v1 到 v2 迁移注意事项

- v2 不兼容旧的 v1 工具
- 一些软件可能不兼容 v2
- Docker 17.06+ 支持 v2
- K8s 1.25+ 默认 v2
- 建议测试后再生产部署

---

## 十六、监控与调试

### 16.1 监控工具

**systemd-cgtop：**

```bash
# 实时监控所有 cgroup
systemd-cgtop

# 监控特定 cgroup
systemd-cgtop /system.slice/docker-*.scope
```

**cgroup 工具：**

```bash
# 查看 cgroup 信息
systemctl status myapp.service
# 显示 MemoryMax, CPUQuota, TasksMax 等

# 查看 cgroup 详情
cat /proc/<pid>/cgroup
ls /proc/<pid>/cgroup

# 详细内存信息
cat /sys/fs/cgroup/memory/<cgroup>/memory.stat
```

**Prometheus + Grafana：**

```bash
# node_exporter 暴露 cgroup 指标
# 关键指标：
# - node_cpu_seconds_total
# - node_memory_MemTotal_bytes
# - container_cpu_usage_seconds_total
# - container_memory_usage_bytes

# Grafana Dashboard
# ID 893: cAdvisor + Prometheus
# ID 179: Docker Container (Prometheus)
```

### 16.2 调试技巧

**查看进程 cgroup：**

```bash
# 查看进程属于哪个 cgroup
cat /proc/<pid>/cgroup

# 例子：
# 0::/system.slice/docker-<id>.scope
# 0::/kubepods-pod<id>.slice/...

# 查看进程的 cgroup 限制
cat /proc/<pid>/cgroup | awk -F'::' '{print $2}' | xargs -I{} cat /sys/fs/cgroup/{}/cpu.max
```

**实时监控：**

```bash
# 每秒刷新
watch -n 1 "cat /sys/fs/cgroup/memory/system.slice/memory.current"

# 多 cgroup 对比
for cgroup in cpu memory blkio; do
    echo "$cgroup:"
    ls /sys/fs/cgroup/$cgroup/ | head -5
    echo
done
```

**systemd-cgls 递归查看：**

```bash
# 树状显示所有 cgroup
systemd-cgls

# 显示特定 slice
systemd-cgls /system.slice/docker-*.scope

# 详细 cgroup 信息
systemd-cgtop
```

---

## 十七、cgroup 核心要点速记

### cgroup 三大功能

```
1. 资源限制 (Limit)    - 限制 CPU/内存/IO 使用
2. 资源优先级 (Priority) - 控制资源分配比例
3. 资源统计 (Accounting) - 记录实际使用量
```

### cgroup v1 vs v2 速记

```
cgroup v1:
- 多子系统，每个独立挂载
- 多个挂载点
- 简单但分裂

cgroup v2:
- 统一层级
- 单挂载点 /sys/fs/cgroup/
- 内核 4.5+
- K8s 1.25+ 默认
- 推荐
```

### 关键路径速记

```
v1:
/sys/fs/cgroup/cpu/<cgroup>/cpu.cfs_quota_us
/sys/fs/cgroup/memory/<cgroup>/memory.limit_in_bytes
/sys/fs/cgroup/blkio/<cgroup>/blkio.throttle.read_bps_device

v2:
/sys/fs/cgroup/<cgroup>/cpu.max
/sys/fs/cgroup/<cgroup>/memory.max
/sys/fs/cgroup/<cgroup>/io.max
```

### 关键文件速记

```
# v2 CPU
echo "50000 100000" > cpu.max  # 50% 单核

# v2 内存
echo 1G > memory.max            # 硬限制
echo 800M > memory.high          # 软限制
echo 100M > memory.low           # 保护

# v2 进程数
echo 1000 > pids.max

# 添加进程
echo $pid > cgroup.procs
```

### 资源限制推荐公式

```
# Web 服务
CPU:    50% 单核 (50000/100000)
Memory: 500M 硬限制
IO:     50MB/s 读
Pids:   200

# 数据库
CPU:    2 核 (200000/100000)
Memory: 4G 硬限制
IO:     200MB/s 读
Pids:   500
```

### 一句话总结

```
cgroup = Linux 内核资源管理机制
v2 单层级统一，推荐
Docker/K8s 都基于 cgroup
CPU 用 shares/weight + max
Memory 用 max/high/low
IO 用 bps/iops + weight
```

### 关键命令速记

```
systemd-run --scope \
  --property="CPUQuota=50%" \
  --property="MemoryMax=500M" \
  --property="TasksMax=100" \
  -- bash

systemd-cgtop               # 实时监控
systemd-cgls                # 树状显示
```

---

## 十七、Docker 容器 OOM 与 cgroup memory 控制器

### 17.1 内存组成与 cgroup 统计

容器的内存使用分为两大类：

- **RSS（Resident Set Size）**：匿名页（进程堆栈、mmap 映射的私有内存），不可回收，除非 swap。
- **Page Cache**：文件缓存（读文件、共享库等），内核可以在内存压力下回收。

cgroup 的 `memory.usage_in_bytes` 包含 RSS + Cache + 内核 slab 等。当这个值达到 `memory.limit_in_bytes` 时，内核会进入 **内存回收路径**。

### 17.2 回收 vs OOM 的决策流程

当容器内存使用触及上限时：

**步骤 1：尝试回收 page cache**

内核启动 kswapd 或直接回收，优先释放可回收的页面（page cache、dentries、inodes）。如果回收后内存使用降到限制以下，则一切正常，不会触发 OOM。

**步骤 2：回收不足则触发 OOM**

如果 page cache 已被压缩到很低，而 RSS 仍然占据大部分空间，并且新分配请求无法满足，内核就在该容器的 cgroup 内调用 OOM killer。

**步骤 3：OOM killer 的选择**

内核在该 cgroup 的所有进程中选一个"得分最高"的杀掉。得分基于进程的 RSS、swap 使用、运行时间等因素。由于 cgroup 隔离，**不会杀掉宿主机或其他容器的进程**。

### 17.3 为什么 page cache 多也可能 OOM

虽然 page cache 可回收，但：

- 回收需要**时间**
- 部分 page cache 可能是**脏页（dirty pages）**，必须先回写磁盘才能释放
- 如果容器瞬间申请大量匿名内存（如 malloc 大块内存），而 page cache 很多但来不及全部回收，内核可能直接判定无法满足而触发 OOM

此外，`memory.limit_in_bytes` 是**硬限制**，任何时刻都不能突破，哪怕只是瞬时的超额分配也会立即触发回收或 OOM。

### 17.4 Docker 的额外控制参数

| Docker 参数 | cgroup 对应 | 说明 |
|-------------|------------|------|
| `--memory` | `memory.limit_in_bytes` | 硬限制 |
| `--memory-reservation` | `memory.soft_limit_in_bytes` | 软限制（仅在内存竞争时生效） |
| `--memory-swappiness` | 内核参数 | 控制 swap 倾向，默认 60。设为 0 优先回收 page cache |
| `--oom-kill-disable` | `memory.oom_control` | 禁止 OOM killer（容器会阻塞直到内存可用） |

### 17.5 查看容器内存详情

```bash
# Docker stats 实时查看
docker stats <container>

# 进入容器查看 cgroup 详细统计
cat /sys/fs/cgroup/memory/memory.stat
```

**memory.stat 关键字段：**

| 字段 | 含义 |
|------|------|
| `rss` | 匿名页占用 |
| `cache` | 页面缓存 + tmpfs |
| `pgfault` | 缺页次数 |
| `pgmajfault` | 主缺页次数（反映内存压力） |
| `mapped_file` | 文件映射内存 |
| `dirty` | 脏页数 |

### 17.6 OOM 调优建议

```
1. 合理设置内存限制
   - 不要超过节点可用内存的 70%
   - 留出 20-30% 给系统缓存

2. 调整 swappiness
   - 数据库容器: --memory-swappiness=0 (避免 swap)
   - 缓存容器: 默认 60

3. 启用 OOM 优先级
   - 关键服务: --oom-score-adj=-500 (减少被杀概率)
   - 临时任务: --oom-score-adj=+500 (优先被杀)

4. 监控关键指标
   - container_memory_usage_bytes / memory.limit_bytes > 0.8 告警
   - pgmajfault 突增反映内存压力
   - OOM kill 事件告警

5. 内存问题诊断流程
   - docker stats 看实时使用
   - 查 memory.stat 看 rss vs cache 比例
   - 看内核日志 dmesg | grep -i oom
   - 启用 PSI 监控 (memory.pressure)
```

### 17.7 内存压力 PSI (Pressure Stall Information)

```bash
# 查看内存压力 (v2 新特性)
cat /sys/fs/cgroup/memory.pressure
# some avg10=0.00 avg60=0.00 avg300=0.00 total=0
# full avg10=0.00 avg60=0.00 avg300=0.00 total=0

# some = 至少一个任务在内存竞争中阻塞
# full = 所有任务都在内存竞争中阻塞（100% 阻塞）
# avg10 = 10 秒窗口
# avg60 = 60 秒窗口
# avg300 = 5 分钟窗口
# total = 总时间（毫秒）
```

**PSI 在自动扩缩容中应用：**

```yaml
# K8s HPA 基于内存压力自动扩缩
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: myapp-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: myapp
  metrics:
  - type: Pods
    pods:
      metric:
        name: memory.pressure
      target:
        type: Utilization
        averageUtilization: 70
```

### 17.8 总结

Docker 容器 OOM 的判断依据是 **cgroup 总内存（RSS + Page Cache 等）超过硬限制**，但内核会先尽力回收 page cache，只有回收后依然无法满足新分配请求时，才在该容器内触发 OOM killer。

---

## 十八、K8s 为什么禁用 Swap

### 18.1 背景：K8s 默认禁用 Swap

```bash
# 查看节点 swap 状态
free -h
# 输出：
#               total        used        free      shared  buff/cache   available
# Mem:           16Gi       4.0Gi       8.0Gi       100Mi       4.0Gi        11Gi
# Swap:            0B          0B          0B         # ← K8s 节点 swap 通常为 0

# kubelet 启动参数会拒绝有 swap 的节点
# --fail-swap-on=true (默认)
```

### 18.2 K8s 禁用 Swap 的核心原因

#### 1. 内存可预测性破坏

```text
问题场景:
  Pod A 请求 4Gi 内存
  但使用了 Swap:
    - 真实内存占用: 6Gi (实际)
    - 报告占用: 4Gi (cgroup 看不到 Swap)

后果:
  - 调度器以为节点空闲
  - 实际节点已超载
  - 内存耗尽时, Pod 突然变慢或 OOM Killed
```

#### 2. 性能下降

```text
Swap 与内存速度对比:
  DDR4 内存: ~100 ns
  NVMe SSD:  ~100,000 ns  (慢 1000 倍)
  SATA SSD:  ~500,000 ns  (慢 5000 倍)
  HDD:       ~10,000,000 ns (慢 100,000 倍)

Swap 触发后:
  - 应用突然变慢 10-1000 倍
  - 数据库查询从 1ms 变成 100ms
  - 用户感知明显卡顿
```

#### 3. cgroup 内存统计失效

```text
cgroup memory.usage_in_bytes:
  - 只统计 RSS (物理内存)
  - 不包含 Swap 中的内存

当 Pod 使用 Swap:
  - 真实使用: RSS (2Gi) + Swap (4Gi) = 6Gi
  - cgroup 看到: 2Gi
  - 触发 OOM 阈值: 8Gi (永远达不到)

后果:
  - 容器实际用 6Gi, cgroup 以为只用 2Gi
  - 内存压力被隐藏
  - 节点其他 Pod 被坑
```

#### 4. 调度决策错误

```text
K8s 调度器逻辑:
  节点可用内存 = 节点总内存 - 已分配内存

但如果 Pod A 用了 Swap:
  - 已分配内存 (按 Request): 4Gi
  - 实际使用内存 (含 Swap): 8Gi

调度器误判:
  - 以为节点空闲 4Gi
  - 调度 Pod B 上去
  - 实际节点内存紧张
  - Pod A 和 Pod B 都变慢
```

#### 5. 内存回收延迟

```text
cgroup memory.high / soft limit 触发回收时:
  - 回收 Page Cache: 快 (毫秒)
  - 回收 Swap:    慢 (秒到分钟)

影响:
  - 回收不及时
  - 节点内存压力持续
  - OOM 风险增加
```

### 18.3 K8s 禁用 Swap 的具体体现

#### kubelet 启动参数

```bash
# kubelet 默认配置
kubelet --fail-swap-on=true

# 行为:
# - 检测到节点 swap > 0 → kubelet 启动失败
# - Pod 无法调度到该节点
# - 节点 NotReady
```

#### kubelet 配置

```yaml
# /var/lib/kubelet/config.yaml
apiVersion: kubelet.config.k8s.io/v1beta1
kind: KubeletConfiguration
failSwapOn: true  # 默认值, 检测到 swap 就失败
```

#### 节点初始化时关闭 swap

```bash
# 永久关闭 swap
sudo swapoff -a
sudo sed -i '/ swap / s/^\(.*\)$/#\1/g' /etc/fstab

# 验证
free -h | grep Swap
# Swap: 0B 0B 0B  ✓ 已关闭
```

### 18.4 为什么有些场景要开启 Swap

虽然 K8s 默认禁用 swap，但有些场景需要开启：

```text
场景 1: 内存偶尔不足
  - 突发流量超过规划
  - swap 兜底比 OOM kill 好
  - 例: 离线批处理任务

场景 2: 内存密集型应用
  - 大数据分析 (Spark/Hadoop)
  - 内存换磁盘性能 (swappiness 低)
  - 例: 数据库冷数据缓存

场景 3: 开发/测试环境
  - 不追求极致性能
  - swap 提供灵活性
```

### 18.5 K8s 启用 Swap 的方案

#### 方案 1: kubelet 关闭 fail-swap-on (不推荐)

```bash
# kubelet 参数
kubelet --fail-swap-on=false

# 风险:
# - 调度决策错误
# - cgroup 统计失真
# - 性能不可预测
```

#### 方案 2: Node-level swap + cgroups v2 (K8s 1.28+)

```text
K8s 1.28+ 支持 cgroup v2 下的 swap:
  - kubelet 设置 memorySwap:
    swapBehavior: LimitedSwap  # 默认
    # 或
    swapBehavior: UnlimitedSwap

  LimitedSwap:
    - Node 总 swap = Node 内存 * 配置比例
    - Pod 可以使用 swap, 但限制 swap 上限
    - K8s 仍按 Request 调度

  UnlimitedSwap:
    - Pod 可以无限制使用 swap
    - 调度不考虑 swap
```

```yaml
# kubelet 配置 (1.28+)
apiVersion: kubelet.config.k8s.io/v1beta1
kind: KubeletConfiguration
memorySwap:
  swapBehavior: LimitedSwap
```

#### 方案 3: K8s + swap-aware QoS

```yaml
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: app
    resources:
      requests:
        memory: 1Gi
      limits:
        memory: 4Gi
    # K8s 1.28+ 可以使用 swap
    # 实际可用: 1Gi 物理内存 + 3Gi swap
```

### 18.6 各 OS 默认 swap 配置

| OS | 默认 swap | 推荐 K8s 设置 |
|----|-----------|--------------|
| Ubuntu 22.04+ | 关闭 | 关闭 (默认) |
| CentOS 7 | 启用 | 关闭 |
| CentOS 8+ | 关闭 | 关闭 (默认) |
| RHEL 8+ | 关闭 | 关闭 (默认) |
| Debian 11+ | 关闭 | 关闭 (默认) |
| Amazon Linux 2 | 启用 | 关闭 |
| 阿里云镜像 | 关闭 | 关闭 (默认) |

### 18.7 检测和处理节点 swap

```bash
# 1. 检测节点 swap
for node in $(kubectl get nodes -o name); do
    echo "Node: $node"
    kubectl debug $node -it --image=alpine -- \
        sh -c "free -h | grep Swap; swapon --show"
done

# 2. 临时关闭 swap (不重启)
kubectl debug <node> -it --image=alpine -- \
    sh -c "swapoff -a && free -h | grep Swap"

# 3. 永久关闭 swap
kubectl debug <node> -it --image=alpine -- \
    sh -c "
        swapoff -a
        sed -i '/ swap / s/^\(.*\)$/#\1/g' /etc/fstab
    "

# 4. 验证 kubelet 是否就绪
kubectl get node <node> -o wide
# Ready 状态显示
```

### 18.8 总结

```
K8s 禁用 Swap 的核心原因:

1. 内存可预测性破坏 (Swap 隐藏真实用量)
2. 性能严重下降 (Swap 比内存慢 100-1000 倍)
3. cgroup 内存统计失效 (看不到 Swap 中的内存)
4. 调度决策错误 (基于错误的内存视图)
5. 内存回收延迟 (Swap 回收慢)

K8s 默认配置:
  failSwapOn: true
  检测到 swap → kubelet 启动失败 → 节点 NotReady

生产建议:
  - 默认保持禁用 swap
  - 关闭节点 swap: swapoff -a
  - 注释 /etc/fstab 中 swap 行

K8s 1.28+ 特殊场景:
  - memorySwap.swapBehavior: LimitedSwap
  - 允许 swap 但限制使用
  - 仅特殊场景使用 (如离线批处理)
```

---

## 附录：参考资源

```
- Linux 内核文档 cgroup v1: https://www.kernel.org/doc/Documentation/cgroup-v1/
- Linux 内核文档 cgroup v2: https://www.kernel.org/doc/Documentation/admin-guide/cgroup-v2.rst
- Red Hat cgroup 文档: https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/8/html/managing_monitoring_and_updating_the_kernel/using-cgroups-v1-to-control-resource-allocation
- Docker cgroup 文档: https://docs.docker.com/config/containers/resource_constraints/
- K8s 资源管理: https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/
- systemd cgroup 文档: https://www.freedesktop.org/software/systemd/man/systemd.resource-control.html
- Cgroup v2 介绍: https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html
```
