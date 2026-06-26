## 概念

eBPF（extended Berkeley Packet Filter）是 Linux 3.18 起逐步成型的内核技术：用户把一段受限制的字节码（eBPF program）通过 `bpf()` 系统调用塞进内核，挂在某个 **hook point** 上执行。运行流程是：

1. 用户写 C / Rust → clang/rustc 编译成 eBPF 字节码
2. `bpf(2)` 加载，**verifier** 静态证明安全（无越界、无死循环、无不可达）
3. JIT 编译为目标架构原生码（性能 ≈ 内核模块）
4. 挂到 hook 上，符合条件的事件触发就执行
5. 程序通过 **BPF map** 跟用户态交换数据：写入 ringbuf、percpu array、hash 等

跟内核模块的区别：eBPF 跑在受限沙箱里，不需要重编内核、不会 crash kernel，verifier 把坑挡在前面。

跟 io_uring / netmap 的区别：那俩是 **数据面**（绕过栈收发包），eBPF 是 **观测 + 决策面**（hook 到内核任何事件点收数据 / 做策略）。

## Hook 点全景

按层次从底到顶：

| 类别 | 钩子 | 典型用途 |
|------|------|----------|
| 网络驱动层 | XDP（`BPF_PROG_TYPE_XDP`） | DDOS 抗、DPDK 级 drop / redirect，**最早到达** |
| 网络 qdisc | TC clsact / ingress / egress | L3/L4 策略、负载均衡、流量镜像 |
| Socket 层 | `BPF_PROG_TYPE_SOCK_OPS`、`sk_msg` | 透明代理、socket 重定向 |
| Cgroup | `BPF_PROG_TYPE_CGROUP_SKB` | 容器级流量管控 |
| kprobe / kretprobe | 任意内核函数入口 / 返回 | 性能分析、内核行为观测 |
| tracepoint | 稳定内核事件 | perf、`/sys/kernel/debug/tracing` 替代 |
| uprobes | 用户态任意函数 | 应用级 trace（MySQL / Redis / JVM 内部） |
| USDT | 用户态静态 tracepoint | 某些 runtime 自带 |
| perf event | 硬件 PMU / 软件事件 | perf 类采样 |
| LSM | 安全模块 hook | 运行时安全策略（Falco、Tetragon） |
| BTF-based | `fentry` / `fexit` | kprobe 的现代版，开销更低、内联 |

## 工具链

* **libbpf**：C 库，官方 loader，**CO-RE**（Compile Once Run Everywhere）靠 BTF 解决跨内核版本兼容
* **bpftool**：内核自带的 CLI，dump program / map / 挂载点 / BTF
* **BCC**：Python / Lua 前端，运行时编译 BPF（慢但方便）
* **bpftrace**：单行脚本 DSL，类似 `awk` for kernel
* **cilium/ebpf**：Go 的纯 Go 库（不依赖 libbpf），Cilium 团队出品
* **aya**：Rust 的纯 Rust 库，编译期 `musl` 静态链接方便
* **falco / cilium / pixie / tetragon**：上层产品，把 eBPF 包成可观测 / 安全平台

## BPF Map 数据交换

程序和用户态之间的唯一渠道：

| 类型 | 用途 |
|------|------|
| `BPF_MAP_TYPE_HASH` | 通用 K/V，状态、限速计数器 |
| `BPF_MAP_TYPE_ARRAY` | 固定下标，常作配置 |
| `BPF_MAP_TYPE_PERCPU_HASH` | 避免多核竞争，但聚合要用户态求和 |
| `BPF_MAP_TYPE_LRU_HASH` | 自动淘汰，防止 map 撑爆 |
| `BPF_MAP_TYPE_RINGBUF` | 程序 → 用户态事件流，**替代 perf_event_array**，推荐 |
| `BPF_MAP_TYPE_PERF_EVENT_ARRAY` | 老的事件流机制 |
| `BPF_MAP_TYPE_STACK_TRACE` | 抓调用栈，配合 profile |
| `BPF_MAP_TYPE_LPM_TRIE` | IP 前缀树，做路由 / 规则匹配 |

## C + libbpf（XDP drop 示例）

挂到网卡 `eth0` 的 XDP hook，丢弃目的端口 22 的包：

```c
#include <linux/bpf.h>
#include <bpf/bpf_helpers.h>

SEC("xdp")
int drop_ssh(struct xdp_md *ctx) {
    void *data     = (void *)(long)ctx->data;
    void *data_end = (void *)(long)ctx->data_end;

    struct ethhdr *eth = data;
    if ((void *)(eth + 1) > data_end) return XDP_PASS;
    if (eth->h_proto != __constant_htons(ETH_P_IP)) return XDP_PASS;

    struct iphdr *ip = (void *)(eth + 1);
    if ((void *)(ip + 1) > data_end) return XDP_PASS;
    if (ip->protocol != IPPROTO_TCP) return XDP_PASS;

    struct tcphdr *tcp = (void *)(ip + 1);
    if ((void *)(tcp + 1) > data_end) return XDP_PASS;
    if (tcp->dest == __constant_htons(22)) return XDP_DROP;

    return XDP_PASS;
}

char _license[] SEC("license") = "GPL";
```

加载（用户态用 libbpf，`skel->progs.drop_ssh__attach_xdp(...)`），挂上就能拦。

## Rust（aya）

```rust
use aya::programs::{Xdp, XdpFlags};
use aya::{Bpf, include_bytes_aligned};

#[tokio::main]
async fn main() -> Result<(), aya::BpfError> {
    let mut bpf = Bpf::load(include_bytes_aligned!("../../target/app.bpf.o"))?;
    let prog: &mut Xdp = bpf.program_mut("drop_ssh").unwrap().try_into()?;
    prog.load()?;
    prog.attach("eth0", XdpFlags::default())?;
    // Ctrl-C 等待后 detach
    Ok(())
}
```

Aya 纯 Rust 编 .bpf.o + 用户态，单 binary 部署友好。

## Go（cilium/ebpf）

```go
import "github.com/cilium/ebpf"

spec, _ := ebpf.LoadCollectionSpec("app.bpf.o")
coll, _ := ebpf.NewCollection(spec)
prog  := coll.Programs["drop_ssh"]
lprog, _ := prog.AssignUninitialized()
defer lprog.Close()
lprog.AttachXDP("eth0", 0)
```

Cilium 主线就是这套，所有 map 操作、ringbuf poll 都是 Go 原生。

## bpftrace 单行脚本

```bash
# 看哪些进程在 open 文件
sudo bpftrace -e 'tracepoint:syscalls:sys_enter_openat { printf("%s %s\n", comm, str(args->filename)); }'

# 看 TCP 重传
sudo bpftrace -e 'tracepoint:tcp:tcp_retransmit_skb { printf("%s -> %pI4:%d\n", comm, args->saddr, args->sport); }'

# 看新建连接
sudo bpftrace -e 'tracepoint:syscalls:sys_enter_connect { printf("pid=%d comm=%s\n", pid, comm); }'
```

排障、调研首选 bpftrace，不用写编译流程。

## BCC Python 示例

```python
from bcc import BPF

b = BPF(text='''
int kprobe__tcp_connect(struct pt_regs *ctx, struct sock *sk) {
    bpf_trace_printk("%s connect\\n", bpf_get_current_comm());
    return 0;
}
''')
b.trace_print()
```

不写 Makefile 直接跑，但每次启动要现场 clang 编 BPF，启动慢（生产服务级别不太合适）。

## 典型场景

* **观测**：Cilium Hubble、pixie、Parca（profile）、bpftrace 临时排查
* **安全**：Falco（runtime 异常检测）、Tetragon（直接 eBPF）、Tracee
* **网络**：Cilium / Calico eBPF datapath，替代 kube-proxy iptables；XDP 做 DDOS
* **调度**：`sched_ext`（Linux 6.12+）让 BPF 程序当调度器
* **服务网格**：Istio ambient 的 waypoint proxy 跟 eBPF 联动
* **存储 / IO**：IO_uring 跟 eBPF 联动做 storage profiling；btrfs / iovisor 类
* **性能分析**：bpftrace + bcc + Parca，连续 profile

## 选型决策

* 我只是临时看一次内核行为 → **bpftrace**
* 我要做常驻服务 / 产品 → **libbpf / aya / cilium-ebpf**，根据语言栈选
* 我要 Python 临时脚本 → **BCC**
* 我要做实时策略 / 拦截 → **XDP / TC / LSM**
* 我要做高频 trace 落地 → 用 **ringbuf**，别用 perf_event_array（ringbuf 无 per-CPU 锁）

## 局限 / 坑

* **verifier** 是大爹：循环必须 verifier 能证明有界，复杂程序写不出；栈 512 字节；指令数 ≤ 100 万（5.2+）；内核函数可调用集合受限
* **CO-RE 依赖 BTF**：发行版要带 BTF（Debian / Ubuntu / RHEL 都开），不然就得每内核版本重编 .bpf.o
* **调试器支持差**：`bpftool prog dump xlated` 看反汇编，`bpf_printk` 是最常用调试手段，断点支持基本没有
* **性能 ≠ 零开销**：高频 hook（每包触发的 XDP）每核百万级包时还是吃 CPU
* **资源限制**：map 默认总大小受 `RLIMIT_MEMLOCK` 约束，systemd 服务的 unit 要 `LimitMEMLOCK=infinity`
* **安全**：eBPF 提权等于 root，`kernel.unprivileged_bpf_disabled=1` 默认开；CAP_BPF 是 Linux 5.8+ 引入的细粒度能力

## 一句话

eBPF 是 **“可热加载的安全内核代码”**：观测用它做上帝视角，安全用它做拦截点，网络用它做 in-kernel datapath。代价是 verifier 限制 + 调试痛苦，但写熟之后生产收益巨大。