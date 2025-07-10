## Linux内核事件源

### 硬件事件

* 定义： 硬件事件是指由物理硬件设备（如 CPU、内存、网卡、磁盘等）触发的事件，内核可以通过这些事件进行性能分析、故障排查和调试。
* 常见类型：
  * 中断（Interrupt）：如外部设备中断、定时器中断等。
  * 性能计数器（Performance Counter）：如 CPU 的 PMU（Performance Monitoring Unit），可统计指令数、缓存命中/未命中、分支预测等。
  硬件故障事件：如 ECC 错误、内存故障、PCIe 错误等。
* 调试工具：
  * perf：Linux 性能分析工具，支持采集硬件事件（如 CPU cycles、cache-misses）。
  * oprofile、pmu-tools：专门用于硬件性能事件采集和分析。
* 应用场景：
  * 性能瓶颈定位（如 CPU、内存、I/O）。
  * 硬件异常排查。

### 静态探针

* 定义：静态探针是在内核源码中预先埋点的钩子，编译时就已经确定，运行时可以通过工具动态启用或禁用。
* 常见类型：
  * tracepoint：内核源码中显式插入的追踪点，用户可通过 tracefs、ftrace、perf 等工具采集。
  * kprobe 静态模式：部分内核函数可通过编译选项插入静态探针。
  * USDT（User-level Statically Defined Tracing）：用户空间程序的静态探针（如 DTrace、SystemTap 支持）。
* 调试工具：
  * ftrace：内核自带的追踪框架，支持 tracepoint。
  * perf：可采集 tracepoint 事件。
  * systemtap、bcc/bpftrace：支持静态探针脚本化分析。
* 应用场景：
  * 性能分析、热点追踪。
  * 关键路径监控（如调度、内存分配、网络收发等）。

### 动态探针

* 定义：动态探针是在内核或用户空间运行时动态插入的钩子，无需修改源码或重启系统，适合临时调试和问题定位。
* 常见类型：
  * kprobe：可在任意内核函数入口/出口动态插入探针，捕获参数、返回值等, 类似于调试具体某个函数信息，分析函数是否被调用/耗时/修复bug打补丁。
  * uprobe：用户空间程序的动态探针，类似 kprobe。
  * eBPF 动态探针：现代 Linux 支持通过 eBPF 技术动态插桩，安全高效。
* 调试工具：
  * kprobe/uprobe：通过 /sys/kernel/debug/tracing 或 bpftrace、bcc 工具插入。
  * systemtap：支持动态插桩和脚本化分析。
  * bpftrace、bcc：现代 eBPF 工具，支持动态探针和复杂事件分析。
* 应用场景：
  * 临时问题定位（如线上故障、性能抖动）。
  * 细粒度函数调用、参数、返回值追踪。
  * 无需重启或修改内核源码即可插桩。

## 过程

1. 内核事件发生
2. 事件日志的收集/打印-------> 传到用户空间
3. 用户态程序分析

## 工具介绍

### ftrace

* 可分析的事件源类型：
  * 内核函数调用（函数入口/出口、调用链）
  * 内核 tracepoint（静态追踪点）
  * kprobes 内核函数
  * uprobes 程序函数
* 可视化工具：
  * trace-cmd + kernelshark（图形化查看 trace 日志）
  * ftrace 文本输出（可用脚本/grep/awk 分析）
  * FlameGraph（配合 stack trace 生成火焰图）

#### 实践

```
1、进入debugfs目录
$ cd /sys/kernel/debug/tracing
如果找不到目录，执行下列命令挂载debugfs：
$ mount -t debugfs nodev /sys/kernel/debug

2、查询支持的追踪器
$ cat available_tracers
常用的有两种：

function 表示跟踪函数的执行；
function_graph 则是跟踪函数的调用关系；
3、查看支持追踪的内核函数和事件。其中函数就是内核中的函数名，而事件，则是内核源码中预先定义的跟踪点。
//查看内核函数
$ cat availablefilterfunctions
//查看事件
$ cat available_events

4、设置追踪函数：
$ echo dosysopen > setgraphfunction

5、设置追踪器
$ echo functiongraph > currenttracer
$ echo funcgraph-proc > trace_options

6、开启追踪
$ echo 1 > tracing_on

7、执行一个 ls 命令后，再关闭跟踪
$ ls
$ echo 0 > tracing_on

8、最后一步，查看跟踪结果
$ cat trace
```

### perf

* 可分析的事件源类型：
  * 硬件事件（CPU cycles、cache-misses、分支预测等）
  * 软件事件（上下文切换、页面错误、系统调用等）
  * 内核 tracepoint
  * kprobe/uprobe（内核/用户空间动态探针）
  * 调度、内存、网络等统计
* 可视化工具：
  * perf report（交互式文本分析）
  * perf top（实时热点分析）
  * perf script + FlameGraph（火焰图）
  * Hotspot（GUI，加载 perf.data）
  * speedscope.app（Web 火焰图）

### ebpf

* 可分析的事件源类型：
  * 内核函数（kprobe/kretprobe）
  * 用户空间函数（uprobe/uretprobe）
  * 内核 tracepoint
  * 网络事件（socket、XDP、tc 等）
  * 调度、内存、文件、系统调用等
  * 自定义事件（通过脚本灵活定义）
* 可视化工具：
  * bpftrace/bcc 文本输出
  * FlameGraph（延迟、调用链分析）
  * Pixie、Inspektor Gadget（K8s 场景下的 Web 可视化）
  * Grafana（配合 eBPF Exporter）

### systemtap

* 可分析的事件源类型：
  * 内核函数、tracepoint、kprobe
  * 用户空间函数、uprobe
  * 调度、内存、网络、文件等
  * 自定义事件（通过 SystemTap 脚本）
* 可视化工具：
  * systemtap 文本/表格输出
  * stapgui（SystemTap 图形界面）
  * FlameGraph
  * 可导出到 gnuplot、Excel 等

### sysdig

* 可分析的事件源类型：
  * 系统调用（所有进程/容器的 syscall）
  * 文件系统事件（读写、打开、删除等）
  * 网络事件（连接、数据包、监听等）
  * 进程/容器生命周期事件
  * 自定义事件（chisels 脚本）
* 可视化工具：
  * csysdig（交互式终端 UI）
  * sysdig Inspect（Web GUI）
  * Falco UI（安全事件可视化）
  * 可导出到 Wireshark、ELK、Grafana 等
