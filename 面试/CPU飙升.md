# CPU 飙升

> **面试高频题**：生产环境某台 / 某集群服务器 CPU 使用率从 20% 飙到 95%，监控告警；部分接口响应时间从 100ms 变到 5s。**你如何排查？怎么定位根因？怎么恢复？怎么防止复发？**

这道题考察的是：**对 OS / 运行时调度模型的理解 + 性能工具熟练度 + 多维度排查能力 + 长期可观测性建设**。

---

## 一、先看问题归属（面试官在考什么）

| 维度 | 占比 | 考察点 |
| --- | --- | --- |
| **CPU 调度模型** | ★★★ | user / system / iowait / steal / softirq 区分 |
| **进程级分析** | ★★★ | top / pidstat / perf / flame graph |
| **代码级分析** | ★★★ | 火焰图 / hotspot / 锁竞争 / GC 频繁 |
| **运维工具熟练度** | ★★★ | perf / ebpf / sysdig / bcc |
| **排查方法论** | ★★★ | 系统 → 进程 → 代码 三步下沉 |
| **长期预防** | ★ | 监控告警 / 容量规划 / 自愈 |

**答浅**：只说 `top` 看进程然后重启。
**答深**：能区分 user / sys / iowait / steal，知道用 `perf` 出火焰图、能识 GC / 锁 / 慢 SQL / 第三方库等不同根因。

---

## 二、CPU 基础知识

### 1. CPU 时间维度

```bash
top
# %Cpu(s): 25.0 us,  2.5 sy,  0.0 ni, 70.0 id,  1.5 wa,  0.0 hi,  0.5 si,  0.0 st
```

| 字段 | 含义 | 排查方向 |
| ---- | ---- | -------- |
| **us** (user) | 用户态 CPU | 应用代码 / GC / 业务逻辑 |
| **sy** (system) | 内核态 CPU | syscall / 中断 / 驱动 / TCP / IO |
| **ni** (nice) | 调整优先级 | - |
| **id** (idle) | 空闲 | - |
| **wa** (iowait) | 等待 IO | 磁盘 / 网络瓶颈 |
| **hi** (hardirq) | 硬件中断 | 网卡 / 存储 |
| **si** (softirq) | 软中断 | ksoftirqd、网络收包 |
| **st** (steal) | 被 hypervisor 偷走 | 邻居 VM / 容器耗光 CPU 配额 |

### 2. CPU 调度

```text
                ┌──────────────────┐
                │ 用户进程（us）    │
                ├──────────────────┤
                │ 内核态 (sy)       │
                │ - system call    │
                │ - 中断处理        │
                ├──────────────────┤
                │ softirq（si）     │  ← 网络收发包 / 调度
                ├──────────────────┤
                │ hardirq（hi）     │  ← 网卡 / NVMe 中断
                ├──────────────────┤
                │ idle（id）        │
                └──────────────────┘
```

### 3. 多核负载

- **load average**：1/5/15 分钟负载（运行 + 不可中断）
- load > ncpu：CPU / IO 紧张（`nproc` 看核心数）
- 单核 100% 也可能引起排队（单线程 Java）

---

## 三、6 步排查法

### 第 1 步：确认 CPU 维度

```bash
top
mpstat 1 5          # 每核心情况
htop
uptime
nproc
```

- 看 us / sy / wa / si / st 占比
- load > ncpu → 整体紧张
- load < ncpu 但 100% → 单核跑满

### 第 2 步：找是哪个进程 / 线程

```bash
top -o %CPU              # 按 CPU 排序
ps -eo pid,pcpu,comm --sort -pcpu | head
pidstat -u 1 5            # 实时 CPU 占用
ps -T -p <pid>            # 看线程
top -H                   # thread view
```

### 第 3 步：找到具体占用线程

```bash
# 找出最耗 CPU 线程（TID）
top -H -p <pid>
# 取 hex TID → /proc/<pid>/task/<tid>/stat
ps -eLo pid,tid,pcpu,comm | sort -k3 -rn | head
```

把 TID 转 16 进制，对比 `jstack` / `dotnet-stack` / `pprof`。

### 第 4 步：火焰图 / on-CPU 栈

```bash
# 采样
perf record -F 99 -p <pid> -g -- sleep 30
perf report

# 直接生成火焰图
perf script | ./stackcollapse-perf.pl | ./flamegraph.pl > flame.svg
```

工具：

- **perf**（Linux 自带）
- **async-profiler**（Java）
- **bcc / bpftrace**（Linux 内核）
- **py-spy / pyspy**（Python）
- **rbspy**（Ruby）
- **pprof**（Go / Java）

### 第 5 步：看系统状态

```bash
vmstat 1 5                # procs / mem / io / system
iostat -xz 1 5            # 磁盘
nicstat / sar -n DEV      # 网络
cat /proc/loadavg
cat /proc/pressure/cpu    # PSI / pressure
```

### 第 6 步：排查业务逻辑

- 慢 SQL（`EXPLAIN`、索引、锁）
- 锁 / 信号 / Channel
- 大批量计算（重复 N 次）
- 第三方 RPC 超时导致重试
- 死循环 / 正则灾难

---

## 四、常见 6 大根因

| 根因 | 现象 | 排查工具 |
| ---- | ---- | -------- |
| **Java Full GC** | Old Gen 满，CPU 100% | `jstat -gcutil` / `GC.log` |
| **慢 SQL / 锁等待** | CPU 高，DB load 高 | `pg_stat_activity` / `MySQL show processlist` |
| **正则灾难 / 死循环** | 单线程 CPU 100% | `perf top` / 火焰图 |
| **线程池爆炸** | 大量 RUNNABLE 线程 | `jstack` / `arthas thread` |
| **网卡 / 软中断爆** | si 高，CPU 队列 | `sar -n DEV` / `nicstat` |
| **cgroup 限制** | 单核 100% 整体不高 | `cat /sys/fs/cgroup/cpuacct/...` |

### 案例 1：Java Full GC 频繁

```text
- top -H 显示 PID 占满单核
- jstat -gcutil 1000 5：Old 区 99.99% → FGC
- GC 日志：每次 Full GC 1.5s
- heap dump 找内存大对象
```

**修复**：

- 检查内存泄漏 / 增大 Old Gen
- 调整 G1 / ZGC
- `+UseG1GC -XX:MaxGCPauseMillis=200`

### 案例 2：慢 SQL 锁表

```text
- top 看到 mysqld 占 200% 多核
- show processlist 看到一堆 Sending data / Waiting for lock
- 抓慢日志
```

**修复**：

- 加索引
- EXPLAIN 优化
- 拆分大事务

### 案例 3：正则灾难（ReDoS）

```text
单核 100%，jstack 一直停在 java.util.regex.Pattern
火焰图明显
```

**修复**：

- 改用确定性 regex（safe-regex）
- 改 nfa.dfa 库（RE2）
- 输入校验层（白名单）

### 案例 4：线程池爆炸

```text
Thread-12345... 多数
jstack 看大量 BLOCKED / WAITING on lock
```

**修复**：

- 限流
- 隔离池
- 控制共享资源访问

### 案例 5：网络软中断

```text
si 高，CPU 在 ksoftirqd
ss -s 显示大量 SYN_RECV / TIME_WAIT
```

**修复**：

- 减少短连接
- 调大 somaxconn / tcp_max_syn_backlog
- 用 `irqbalance` / RSS

### 案例 6：容器 CPU limit 太低

```text
top 看单核 100%，但 system 上 ncpu 很多空闲
systemd-cgtop 看 cpu.throttled_usec
```

**修复**：

- 调高 K8s pod limit
- 设 Burstable QoS
- 关 cgroup throttling

---

## 五、5 步应急

| 步骤 | 行动 |
| --- | --- |
| 1. **取证** | `perf record` / `jstack` / `vmstat 1 60` 抓一段时间 |
| 2. **隔离** | 限流 / 摘流量 / 单容器杀掉 |
| 3. **止血** | 重启 / 扩容 / 切换 Canary |
| 4. **回滚** | GitOps 回上一版本 |
| 5. **复盘** | Post-Mortem + e2e 测试 + 监控告警 |

**关键：保留现场比立刻重启重要**。火焰图 + jstack + GC 日志是事故复盘的命脉。

---

## 六、长期预防

### 1. 资源管理

```yaml
# K8s
resources:
  requests:
    cpu: 500m
  limits:
    cpu: 1000m
```

```text
# JVM
-XX:+UseG1GC -XX:MaxGCPauseMillis=200
-XX:+UseStringDeduplication
-XX:+UnlockExperimentalVMOptions
```

### 2. 监控与告警

```promql
# CPU 利用率（多核）
100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# 负载
node_load5 / count without(cpu, mode)(node_cpu_seconds_total{mode="idle"})

# JVM Full GC 频率
rate(jvm_gc_collection_seconds_count{action="end of major GC"}[5m])

# 单线程 CPU 飙高
process_cpu_seconds_total{mode="user"} > 0.5
```

```yaml
- alert: HighCPU
  expr: 100 - avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100 > 85
  for: 5m
- alert: CPUThrottled
  expr: rate(container_cpu_cfs_throttled_seconds_total[5m]) > 0.1
- alert: JVMFullGC
  expr: rate(jvm_gc_collection_seconds_count{action="end of major GC"}[1m]) > 0
```

### 3. 代码 / 架构层面

- 慢 SQL 拦截（p6spy / MyBatis SQL 审计）
- 限流 / 熔断 / 隔离（Sentinel / Resilience4j）
- 异步化 + 队列削峰（Kafka / Pulsar）
- ReDoS 自动化扫描（redos / arden）

### 4. 性能基线

- 容量：日常 100 TPS，巅峰 1000 TPS，扩 5 倍需要补 4 节点
- 性能回归：CI 跑 baseline 火焰图对比

---

## 七、面试回答框架

1. **接到告警如何排查**（1 分钟）
   - `top` / `mpstat 1 5` / `pidstat`
   - 区分 us / sy / wa / si / st
   - 找 CPU 高线程

2. **进程内分析**（1 分钟）
   - `top -H` 找线程 TID
   - `jstack <pid>` / `perf record -g -p <pid>`
   - 出火焰图，看是否 Full GC / 锁 / 死循环 / 慢 SQL

3. **6 大根因**（1 分钟）
   - Java Full GC / 慢 SQL / ReDoS / 线程池爆 / 软中断 / cgroup 限制

4. **应急与长期预防**（1 分钟）
   - 取证 → 隔离 → 止血 → 回滚 → 复盘
   - 长期：资源 + 监控 + 自愈 + 基线

5. **加分项**（0.5 分钟）
   - PSI / Pressure Stall Info
   - 火焰图入 CI（regression check）
   - `runqlat` / `runqlen` 调度延迟观测
   - cgroup v2 的 cpu.weight / cpu.max

---

## 八、参考工具速查

| 工具 | 用途 |
| --- | --- |
| `top` / `htop` / `atop` | 进程 CPU |
| `mpstat` / `iostat` / `vmstat` | 系统维度 |
| `pidstat` | 每进程 CPU |
| `perf record / report` | on-CPU 采样 |
| `perf top` | 实时栈 |
| `bcc / bpftrace` | 内核 / 系统态 |
| `async-profiler` | Java |
| `py-spy / rbspy` | Python / Ruby |
| `pprof` | Go |
| `dtrace / sysdig` | 系统调用 |
| `jcmd <pid> Thread.print` | Java thread dump |
| `arthas` | Java 在线诊断 |
| `PSI` (`/proc/pressure/*`) | CPU / IO / Memory 压力 |

---

## 九、一句话总结

```text
CPU 飙升排查：
  1) top 看维度：us / sy / wa / si / st + load
  2) top -H + pidstat 找进程与线程
  3) perf / jstack / 火焰图看栈
  4) 6 大根因：Full GC / 慢 SQL / ReDoS / 线程池 / 软中断 / cgroup
  5) 应急取证 → 隔离 → 止血 → 回滚 → 复盘
  6) 预防：资源 + 监控 + 容量基线 + CI 性能门禁
```