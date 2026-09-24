# eBPF 学习笔记

> Extended Berkeley Packet Filter — 让内核可编程的安全沙箱技术

## 目录

| 章节 | 内容 |
|------|------|
| [01-概述](01-概述.md) | 什么是 eBPF、发展历史、为什么重要、典型应用场景 |
| [02-核心架构](02-核心架构.md) | 内核态/用户态交互、Verifier、Programs、Maps、Helpers 全景图 |
| [03-程序类型](03-程序类型.md) | XDP、TC、kprobe、tracepoint、uprobe、socket、LSC 等 30+ 种程序类型 |
| [04-开发环境](04-开发环境.md) | libbpf、bpftool、bcc、bpftrace、LLVM/Clang 安装与选型 |
| [05-Hello-World](05-Hello-World.md) | 第一个 eBPF 程序：从编写到加载到观测输出 |
| [06-Maps详解](06-Maps详解.md) | Hash/Array/LRU/LPM/Stack/RingBuffer 等 20+ 种 Map 类型 |
| [07-CORE与BTF](07-CORE与BTF.md) | Compile Once Run Everywhere、BTF、内核版本兼容性 |
| [08-Helpers与API](08-Helpers与API.md) | 200+ Helper 函数分组精讲、kfunc、自定义 BTF |
| [09-性能与限制](09-性能与限制.md) | Verifier、复杂度、循环、栈大小、JIT 等 |
| [10-开源项目实战](10-开源项目实战.md) | Cilium、bcc 工具集、bpftrace、Pixie、Tetragon、Katran、Falco |
| [11-调试技巧](11-调试技巧.md) | bpftool、verifier log、bpf_dbg、printk、性能分析 |
| [12-应用场景](12-应用场景.md) | 网络可观测、安全检测、性能分析、负载均衡 |

## 一句话理解 eBPF

> 在内核中运行一段受验证器约束的安全沙箱程序，无需修改内核源码、无需重启即可观测/控制网络、磁盘、CPU、安全等几乎所有子系统。

## 速查地图

```
┌─────────────────────────────────────────────────────────────┐
│  用户态                                                       │
│   ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐             │
│   │ bpftool│  │  bcc   │  │bpftrace│  │ Cilium │  ...        │
│   └───┬────┘  └────┬───┘  └────┬───┘  └────┬───┘             │
│       └─────────────┴───────────┴───────────┘                │
│                          ↓ syscall (bpf())                    │
├──────────────────────────┼──────────────────────────────────┤
│  内核态                                                       │
│                          ↓                                  │
│                ┌─────────────────────┐                       │
│                │   Verifier (验证器)  │ ← 安全性 + 终止性     │
│                └──────────┬──────────┘                       │
│                           ↓                                  │
│   ┌─────────┐    ┌─────────────┐    ┌────────────┐           │
│   │ JIT 编译 │ ←  │   eBPF 程序  │ →  │   Helpers  │           │
│   └─────────┘    └──────┬──────┘    └─────┬──────┘           │
│                         ↓                  ↓                  │
│                  ┌─────────────┐   ┌─────────────┐           │
│                  │   eBPF Maps │   │  kfunc/tail │           │
│                  └─────────────┘   └─────────────┘           │
└─────────────────────────────────────────────────────────────┘
```

## 关键事实

- **起源**：1992 年 BSD Packet Filter，2014 年 Alexei Starovoitov 扩展为 eBPF
- **里程碑**：Linux 3.18 (2014) 引入 eBPF，Linux 4.x 持续增强，5.x 全面爆发
- **核心人物**：Alexei Starovoitov、Daniel Borkman（共同创建 Cilium）
- **生态公司**：Isovalent（Cilium 被 Cisco 收购）、Meta（Katran）、Brendan Gregg（bpftrace）

## 前置知识

- C 语言基础（eBPF 程序主体是受限 C）
- Linux 内核基础（系统调用、网络栈、调度）
- 基本的命令行和编译工具链

## 推荐资源

| 类型 | 资源 |
|------|------|
| 书籍 | 《Learning eBPF》《BPF Performance Tools》(Brendan Gregg) |
| 官方 | [ebpf.io](https://ebpf.io)、[docs.cilium.io](https://docs.cilium.io) |
| 代码 | [github.com/libbpf/libbpf](https://github.com/libbpf/libbpf)、[github.com/iovisor/bcc](https://github.com/iovisor/bcc) |
| 实验 | [github.com/eunomia-bpf/eBPF-hello-world](https://github.com/eunomia-bpf/eBPF-hello-world) |