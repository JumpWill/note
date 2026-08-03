# top

`top` 是 Linux 必备的实时系统监控工具：CPU / 内存 / 进程 / 负载一目了然，并提供交互式命令来快速过滤和操作。

## 1. 命令行

```text
top [OPTIONS]
  -d <secs>    刷新间隔
  -p <pid>     只看某个 PID
  -u <user>    只看某用户
  -H           按线程显示（线程 ID 模式）
  -i           不显示 idle / zombie 进程
  -b           批模式（适合脚本）
  -n <count>   多少轮后退出（批模式常用）
  -1           单 CPU / 多 CPU 折叠显示
  -E <scale>   内存单位 (k/m/g/t/p/e)
  -c           显示完整命令行
  -S           累加模式（对线程 / 子进程累加）
  -m           关闭模块显示
  -w           宽输出
  -h           帮助
  -v           版本
```

常用：

```bash
top                    # 默认 3s 刷新
top -d 1               # 1 秒刷新
top -H                 # 看线程
top -p 1234            # 看单进程
top -u alice           # 看某用户
top -b -n 2 -d 5 > log # 写日志
```

## 2. 顶部摘要区

```text
top - 10:42:13 up 21 days,  3:12,  2 users,  load average: 0.45, 0.38, 0.32
Tasks: 412 total,   1 running, 411 sleeping,   0 stopped,   0 zombie
%Cpu(s):  8.5 us,  1.2 sy,  0.0 ni, 89.7 id,  0.3 wa,  0.0 hi,  0.3 si,  0.0 st
MiB Mem :  32000.0 total,  14523.4 free,  12345.6 used,   5131.0 buff/cache
MiB Swap:   8192.0 total,   5123.0 free,   3069.0 used.   4123.4 avail Mem
```

### 2.1 第 1 行：系统概览

```text
top - 10:42:13 up 21 days,  3:12,  2 users,  load average: 0.45, 0.38, 0.32
```

| 字段 | 含义 |
| ---- | ---- |
| `top -` | 命令 + 当前时间 |
| `up 21 days, 3:12` | 累计运行 21 天 3 时 12 分 |
| `2 users` | 当前登录用户数 |
| `load average:` | 1/5/15 分钟负载（运行 + 不可中断队列） |

**load** 与 `nproc`（CPU 数）比较：

- load = ncpu：饱和
- load > ncpu：排队
- load 持续 > 2 × ncpu：过载

### 2.2 第 2 行：任务汇总

```text
Tasks: 412 total,   1 running, 411 sleeping,   0 stopped,   0 zombie
```

| 字段 | 含义 |
| ---- | ---- |
| `total` | 总任务数（线程 / 进程） |
| `running` | R 状态 |
| `sleeping` | S / I 状态 |
| `stopped` | T / t |
| `zombie` | Z 状态 |

### 2.3 第 3 行：CPU 时间分布

```text
%Cpu(s):  8.5 us,  1.2 sy,  0.0 ni, 89.7 id,  0.3 wa,  0.0 hi,  0.3 si,  0.0 st
```

| 字段 | 含义 |
| ---- | ---- |
| `us` | 用户态 CPU（应用 + GC） |
| `sy` | 内核态 CPU（系统调用 / 调度） |
| `ni` | nice 调整后用户态 |
| `id` | 空闲 |
| `wa` | iowait（等待 IO） |
| `hi` | 硬中断 |
| `si` | 软中断 |
| `st` | 被虚拟机偷走 |

**`-1`**：让多 CPU 各自显示一行。

### 2.4 第 4 行：内存

```text
MiB Mem :  32000.0 total,  14523.4 free,  12345.6 used,   5131.0 buff/cache
```

| 字段 | 含义 |
| ---- | ---- |
| `total` | 物理内存总量 |
| `free` | 完全空闲 |
| `used` | 已用（不含 buff/cache） |
| `buff/cache` | page cache + buffer，**可回收** |

### 2.5 第 5 行：Swap

```text
MiB Swap:   8192.0 total,   5123.0 free,   3069.0 used.   4123.4 avail Mem
```

| 字段 | 含义 |
| ---- | ---- |
| `total` | swap 总容量 |
| `free` | swap 未使用 |
| `used` | swap 已使用（高 → 内存压力） |
| `avail Mem` | 估算"可分配给应用"的总内存 ≈ free + 部分 buff/cache |

> **判断可用内存**：`available` 而非 `free`。`free` 看着很小但 `avail` 充足说明 page cache 用了大部分，不算紧张。

## 3. 进程列表区

```text
PID    USER   PR  NI    VIRT    RES    SHR S   %CPU  %MEM    TIME+   COMMAND
 1234  alice  20   0  500Mi  120Mi  20Mi  R   25.0   0.5   12:34.5  python3 -m server
 5678  root   20   0  1.2Gi  800Mi  10Mi  S   10.0   2.5   1:23.4   nginx: master
```

| 列 | 含义 |
| --- | ---- |
| `PID` | 进程 ID |
| `USER` | 有效用户 |
| `PR` | 优先级（0 是实时） |
| `NI` | nice 值（-20 高 / 19 低） |
| `VIRT` | 虚拟内存总量 |
| `RES` | 实际占用 RAM（RSS） |
| `SHR` | 共享内存（mappings / IPC） |
| `S` | 状态：R/S/D/T/Z |
| `%CPU` | CPU 使用率（自上次刷新） |
| `%MEM` | 物理内存比例 |
| `TIME+` | 累计 CPU 时间 |
| `COMMAND` | 命令（`-c` 显示完整命令行） |

VIRT / RES / SHR 区别：

```text
虚拟地址空间
  ├── 程序段 (code / data)        → SHR (shared library)
  ├── 堆 (heap)                   → RES
  ├── 栈 (stack)                 → RES
  ├── mmap (so, jdk, libc)       → SHR
  └── ..

VIRT = 进程能访问到的虚拟地址总和 (含 reserved, mapped, unmapped)
RES  = 真实物理占用 (含 shared 的"全量")
SHR  = 与其它进程共享的部分
```

## 4. 交互命令（运行中按）

### 4.1 视图切换

| 键 | 作用 |
| --- | --- |
| `1` | 单 / 多 CPU 切换 |
| `m` | 内存视图切换（4 种） |
| `t` | CPU 视图切换（条 / 块 / 文本） |
| `l` | 切换单独首行（uptime）显示 |
| `b` | 高亮 running 进程（粗体） |
| `B` | 高亮粗体 |
| `x` | 高亮排序列 |
| `y` | 高亮 running 进程 |
| `z` | 颜色开关 |
| `c` | 完整命令行 ↔ 命令名 |
| `f / F` | 字段管理（加列 / 去列） |
| `o / O` | 列排序（按列名） |
| `R` | 反序排序 |

### 4.2 排序

| 键 | 作用 |
| --- | --- |
| `<` | 按选定列名升序 |
| `>` | 按选定列名降序 |
| `F` / `O` | 进入字段管理 |
| `R` | 反转排序 |
| 默认 | CPU% |

### 4.3 进程过滤

| 键 | 作用 |
| --- | --- |
| `u` | 按用户 |
| `U` / `L` | 按用户/组 |
| `p` | 按 PID |
| `i` | 隐藏 idle |
| `n / #` | 限制显示数量 |
| `c` | 命令完整 / 简洁 |
| `V` | forest 视图（父子） |
| `e` | 内存单位（KiB/MiB/GiB） |
| `E` | 摘要区内存单位 |

### 4.4 写入 / 文件名 / 命令

| 键 | 作用 |
| --- | --- |
| `W` | 把当前配置写入 `~/.toprc` |
| `h` / `?` | 帮助 |
| `q` | 退出 |

### 4.5 杀死 / 改优先级（要 root）

| 键 | 作用 |
| --- | --- |
| `k` | 输入 PID + 信号（默认 15） |
| `r` | 输入 PID + 新 nice 值 |

```text
# 选中 PID=1234 后按 k
PID to signal: [default: 1234]
Send pid 1234 signal [15]: 9           ← 改为 9 = SIGKILL
```

## 5. 高级选项

### 5.1 批模式（适合日志）

```bash
top -b -n 3 -d 5 > /tmp/top.log
```

- `-b` 非交互
- `-n N` 跑 N 轮后退出
- `-d secs` 每轮间隔

### 5.2 单进程

```bash
top -p 1234,1235,5678
top -p 1234      # 单进程模式
```

### 5.3 线程模式

```bash
top -H                # LWP / TID 视角
top -H -p 1234        # 仅看某进程的线程
```

线程模式下 PID 列变成 TID，COMMAND 中方括号包裹 [thread-name]。

### 5.4 Cumulative 模式（`S`）

```bash
top -S            # 子进程 / 线程累计
```

- 父进程里所有线程、子进程的总 CPU 都累加
- 适合看"哪个进程组消耗最多"

### 5.5 累计 vs 实时

`%CPU` 列显示"自上次刷新以来的 CPU 使用率"。

- 默认：实时
- 按 `S` 后：累计（自启动以来）
- 单核系统上，CPU% 可能超过 100%（多核累加）

### 5.6 内存单位

```bash
top -E k           # KB
top -E m           # MB
top -E g           # GB
top -E t           # TB
```

### 5.7 colour 切换

```bash
top -1 -m -h -p 1234
# -1：多CPU分行
# -m：关闭模块
# -h：帮助
```

### 5.8 字段筛选

`f` 进入字段管理：

```text
Current Sort Field:  P  for window 1:Def
   * PID     = Process Id            x
     USER    = User Name             x
     PR      = Priority
     NI      = Nice Value
     VIRT    = Virtual Image (KiB)
     RES     = Resident Size (KiB)
     SHR     = Shared Memory (KiB)
     S       = Process Status
     %CPU    = CPU Usage
     %MEM    = Memory Usage (RES)
     TIME+   = CPU Time, hundredths
     COMMAND = Command Name/Line
```

- `*` 当前排序列
- 空格选中显示该列
- `s` 选排序列
- `q` 退出字段管理

## 6. 字段含义详解

| 字段 | 来源 / 计算 |
| --- | --- |
| `%CPU` | `(jiffies_new - jiffies_old) / (interval * ncpu) * 100` |
| `%MEM` | `RES / MemTotal * 100` |
| `VIRT` | `task->mm->total_vm * page_size` |
| `RES` | `get_mm_rss(task->mm)` |
| `SHR` | RSS 中"能被多个进程引用"的部分 |
| `S` | task->state |
| `PR / NI` | kernel scheduling priority + nice offset |

`/proc/<pid>/stat` 是字段源，详情见 [Linux 进程状态.md](进程状态.md)。

## 7. 启动配置文件

- `~/.toprc`：保存列顺序、列显示、排序
- 按 `W` 后 top 把当前配置写入文件，下次启动自动加载

```text
RCfile for "top with support for color"
Id:a, Mode_altscr=0, Mode_irixps=1, Delay_time=3.0, Curwin=0
Def    fieldscur=¥£µ&¼@ÆÊÎÔØ·±ÅÈÆÇÉÊËÌÍÎÏÐÑÒÓÔÕÖ×ØÙÚÛÜÝÞß ...
    winflags=193844, sortindx=18, maxtasks=0, graph_cpus=0, graph_mems=0, double_up=0, combine_cpus=0, core_types=0
    ...
```

## 8. 常见实战

### 8.1 CPU 高

```text
1. top -o %CPU
2. 看进程 PID / COMMAND / TIME+ / %CPU
3. 找 Java 全 GC？   →  jstat -gcutil
4. 慢 SQL？           →  DB log
5. 死循环？           →  perf record -p <PID>
```

### 8.2 内存高

```text
1. top -o %MEM
2. 看 RES / SHR / %MEM
3. cgroup 限制？         →  /sys/fs/cgroup/memory
4. 缓存无上限？         →  heap dump
5. 直接内存泄漏？       →  pmap / jcmd VM.native_memory
```

### 8.3 IO 高

```text
1. top 看 wa / si
2. iotop / iostat -xz 1 5
3. 找 D 状态：ps -eo stat,pid,etime,comm | awk '$1~/D/'
4. cat /proc/<pid>/wchan   看 IO 等待点
```

### 8.4 负载高但 CPU 低

```text
- load = running + uninterruptible
- load 高 + %CPU 低 = 大批 D 状态
  （IO 卡、NFS 卡、内核驱动 bug）
```

### 8.5 找某进程的所有线程

```text
top -H -p 1234
  →
取 LWP (thread ID) 转 hex → 查 jstack
```

### 8.6 脚本中批量采样

```bash
top -b -n 5 -d 60 > /var/log/top.log
# 每 60 秒一次，共 5 次
```

## 9. 进程列表隐藏

| 字段 | 说明 |
| --- | --- |
| `i` | 隐藏 idle/zombie |
| `V` | forest 视图 |
| `n 50` | 只显示 50 行 |
| `L 0` | 不按用户过滤 |
| `o` | 加列排序 |

```text
按下 i 后，再次按 i 恢复
按下 c 后，命令在 COMMAND ↔ ARGS 切换
```

## 10. 替代品

| 工具 | 优势 |
| --- | --- |
| **htop** | 鼠标 / 颜色 / 树状 / 多视图 |
| **btop** | 现代化 / 图表 / 美观 |
| **atop** | 历史 / IO / 网络 / CPU 综合 |
| **iotop** | 进程 IO 视角 |
| **glances** | 跨平台 / Web / API / 客户端 |
| **nmon** | AIX 风格 / 性能采集 |
| **sysstat / sar** | 历史采样 |
| **ps + watch** | 简易循环 |

```bash
htop -d 5
btop
atop -w /tmp/atop.bin
glances
```

## 11. 故障排查"经验公式"

```text
top 看到现象    →  接下来做什么
%CPU 高       →  top -H -p PID  →  perf record -p PID
%MEM 高       →  pmap / smaps / heap dump
wa 高         →  iostat -xz 1 5
si 高         →  sar -n DEV  /  nicstat
load 高 CPU 低  →  ps -eo stat,etime,comm | grep 'D'
Z 多          →  找父进程 / 修父 / 重启父
1 个 %CPU 100% →  单线程应用（Java / Python），需多线程或异步化
```

## 12. 一句话总结

```text
top = 系统总览 + 进程列表
摘要：uptime + load + Tasks + CPU 时间分布 + Mem + Swap
进程：PID/USER/PR/NI/VIRT/RES/SHR/S/%CPU/%MEM/TIME+/COMMAND
操作：1 切 CPU / m 切内存 / i 隐藏 / u 用户 / k 杀 / r nice / W 保存
进阶：-H 线程 / -b 批模式 / -p 单进程 / -E 单位 / -S 累计
```
