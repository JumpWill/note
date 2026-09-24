# 07 - CO-RE 与 BTF

> CO-RE（Compile Once, Run Everywhere）+ BTF（BPF Type Format）是 eBPF 走向工业级生产的基石。

## 问题背景

传统 eBPF 程序最大痛点：**内核升级后程序崩溃**，因为内核结构体布局变了。

```c
// 编译期：task_struct.pid 在偏移 800
// 升级后：偏移变成 900（新增了字段）
// 程序还在用 800，读到错误的数据 → verifier 失败或错乱
```

传统解法（痛苦）：
- 给每个内核版本编译一份程序（kernel-devel）
- 启动时 uname -r 检测，做 if-else
- 维护成本 O(内核版本数)

## BTF：内核类型元数据

**BTF** 是一种紧凑的、类似 DWARF 的**类型元数据格式**。内核编译时生成，运行时通过 `/sys/kernel/btf/vmlinux` 暴露。

### BTF 能告诉我们什么

```bash
sudo bpftool btf dump file /sys/kernel/btf/vmlinux format c | grep -A 5 "struct task_struct"
```

输出：

```c
struct task_struct {
    struct thread_info thread_info;       /* offset 0, size 16 */
    unsigned int __state;                 /* offset 16, size 4 */
    unsigned int saved_state;             /* offset 20, size 4 */
    void *stack;                          /* offset 24, size 8 */
    refcount_t usage;                     /* offset 32, size 4 */
    unsigned int flags;                   /* offset 36, size 4 */
    /* ... 200 多个字段 ... */
    pid_t pid;                             /* offset 略 不同内核 */
    /* ... */
};
```

**每个字段的偏移、大小、类型都明确**。

### BTF 类型

- `BTF_KIND_INT` - 整数
- `BTF_KIND_PTR` - 指针
- `BTF_KIND_ARRAY` - 数组
- `BTF_KIND_STRUCT` / `BTF_KIND_UNION` - 结构/联合
- `BTF_KIND_ENUM` - 枚举
- `BTF_KIND_FWD` - 前向声明
- `BTF_KIND_TYPEDEF` - typedef
- `BTF_KIND_VOLATILE` / `BTF_KIND_CONST` / `BTF_KIND_RESTRICT`
- `BTF_KIND_FUNC` / `BTF_KIND_FUNC_PROTO` - 函数

## CO-RE 工作流

```
你的 BPF C 源（用 vmlinux.h 引用内核类型）
         ↓
    clang 编译（保留重定位信息）
         ↓
    .o 文件（带 reloc 段）
         ↓
    libbpf 在目标机器加载时：
       1. 读取本机 BTF
       2. 对比 .o 里的重定位需求
       3. 重写代码中的偏移
       4. 加载到内核
         ↓
    内核 verifier 接受
```

### 三种集成

1. **BTF + libbpf CO-RE**（推荐）：运行期重定位
2. **kernel-devel**：每台机器编译（痛苦）
3. **uapi only**：只用稳定的 UAPI header（最受限）

## vmlinux.h：内核类型的头文件

从 BTF 自动生成：

```bash
bpftool btf dump file /sys/kernel/btf/vmlinux format c > vmlinux.h
```

但 **.h 文件很大**（8MB+），包含全内核类型。优化：

```bash
# 只生成你需要用到的结构
bpftool btf dump file /sys/kernel/btf/vmlinux format c | \
    awk '/^struct task_struct/,/^};/' > vmlinux_subset.h
```

或者只保留 BTF 段（不生成 C 头）：

```bash
bpftool btf dump file /sys/kernel/btf/vmlinux format raw > vmlinux.btf
```

`vmlinux.h` 的样子（截选）：

```c
// 从 BTF 自动生成
struct task_struct {
    struct thread_info thread_info;
    unsigned int __state;
    unsigned int saved_state;
    void *stack;
    refcount_t usage;
    unsigned int flags;
    // ... 
} __attribute__((preserve_access_index));

// 注意 __attribute__((preserve_access_index))
// 关键！告诉 clang 不要在编译期计算偏移，保留下来运行时由 libbpf 改写
```

## CO-RE 关键技术

### 1. `__attribute__((preserve_access_index))`

```c
// 让 libbpf 知道你需要重定位
struct task_struct___my {
    unsigned int __state;
    pid_t pid;
} __attribute__((preserve_access_index));

SEC("kprobe/do_fork")
int kprobe__do_fork(struct pt_regs *ctx) {
    struct task_struct *current = (struct task_struct *)bpf_get_current_task();
    u32 state = BPF_CORE_READ(current, __state);  // ← 重定位点
    return 0;
}
```

### 2. BPF_CORE_READ 系列宏

```c
#include <bpf/bpf_core_read.h>

// 等价于：tmp = current->__state; 但带类型/越界检查
unsigned int state = BPF_CORE_READ(current, __state);

// 嵌套
unsigned int flags = BPF_CORE_READ(current, flags);

// 多级嵌套
struct mm_struct *mm = BPF_CORE_READ(current, mm);

// 数组索引
char name = BPF_CORE_READ(current, comm[0]);

// 写入（带重定位）
BPF_CORE_WRITE(current, flags, 0);

// 字面量重定位
unsigned int offset = BPF_CORE_OFFSET(struct task_struct, pid);
```

> `BPF_CORE_READ` 是**安全访问宏**，会自动加 verifier 友好的边界检查。

### 3. 存在性检查与重定义

```c
// BTF 有此字段才执行
if (BPF_CORE_FIELD_EXISTS(struct task_struct, cgroup_v1)) {
    // ...
}

// 字段类型不同时做适配
if (bpf_core_type_matches(struct task_struct, _KERN, 1))
    return 1;
```

### 4. 字段重定位：libbpf 改写

编译产物里的某条指令：

```c
current->__state
```

clang 生成 eBPF 汇编：

```
*(u32 *)(r1 + 16)   // 假设编译期计算偏移是 16
```

`.o` 中包含 reloc：

```
.reloc_offset(16)   // 这里需要运行时重写
```

libbpf 加载时读 BTF，发现 6.1 内核的 `__state` 偏移是 12，于是把 16 改成 12，最终指令：

```
*(u32 *)(r1 + 12)
```

## 实际例子：跨内核追踪进程状态

```c
// SPDX-License-Identifier: GPL-2.0
#include "vmlinux.h"
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_core_read.h>

SEC("tracepoint/sched/sched_switch")
int handle_sched_switch(struct trace_event_raw_sched_switch *ctx) {
    // ctx->prev_pid / next_pid 是 pid_t（u32），不是指针
    pid_t prev_pid = ctx->prev_pid;
    pid_t next_pid = ctx->next_pid;

    // 通过 BTF + kfunc 拿 task_struct（推荐）
    struct task_struct *prev = bpf_task_from_pid(prev_pid);
    struct task_struct *next = bpf_task_from_pid(next_pid);

    if (prev && next) {
        u32 prev_state = BPF_CORE_READ(prev, __state);
        bpf_task_release(prev);
        bpf_task_release(next);

        bpf_printk("switch %d -> %d, prev_state=%d\n",
                   ctx->prev_pid, ctx->next_pid, prev_state);
    }
    return 0;
}
```

### 不支持 BTF 的兜底

```c
// BPF_CORE_READ 在无 BTF 时会失败，libbpf 会重定位失败
// 解决方法：用 BPF_CORE_READ_STRICT 或 fallback

u32 pid;
if (bpf_core_field_exists(struct task_struct, pid))
    pid = BPF_CORE_READ(task, pid);
else
    pid = 0;  // fallback
```

## BTF 内核支持

| 内核版本 | BTF 支持 |
|---------|---------|
| 4.18 | 引入（基础） |
| 5.4 | 全功能 + 模块 BTF |
| 5.10 | kfunc + 更多字段重定位 |
| 5.13 | ksym + 内核函数追踪 |

### 如何确认内核支持

```bash
# 看是否有 vmlinux BTF
ls /sys/kernel/btf/vmlinux

# 内核配置
grep BTF /boot/config-$(uname -r)
# CONFIG_DEBUG_INFO_BTF=y
# CONFIG_DEBUG_INFO_BTF_MODULES=y

# 启用 BTF 重启后仍无：检查安装的 kernel-headers 是否包含
rpm -q kernel-debuginfo  # 或 apt
```

## BTF 生成工具

### bpftool 生成 vmlinux.h

```bash
bpftool btf dump file /sys/kernel/btf/vmlinux format c > vmlinux.h
```

### bpftool gen min_core_btf

```bash
# 从目标内核 BTF 中提取需要的最小子集
bpftool gen min_core_btf vmlinux_5_15.btf vmlinux_5_10.btf min.btf
# 生成 5.15 + 5.10 都兼容的 BTF
```

### pahole（用户态二进制 BTF）

```bash
# 给可执行文件生成 BTF
pahole -J your_app
# 或
llvm-objcopy --add-section .BTF=btf.o --set-section-flags .BTF=readonly,contents \
    your_app
```

### libbpf-bootstrap 自动生成

`make` 过程：

```makefile
vmlinux.h:
	$(BPFTOOL) btf dump file /sys/kernel/btf/vmlinux format c > $@
```

## BTF Maps：.data 共享只读常量

```c
// .data 是只读且共享的（所有程序共享同一份数据）
const volatile u32 magic_number = 0xDEADBEEF;

// .rodata 也只读，但分段不同
const volatile u32 rodata_const = 42;

// .bss 私有读写
volatile u32 bss_var = 0;
```

用户态：

```c
skel->rodata->rodata_const = 100;   // 加载前设置
```

## 内核函数 kfunc（基于 BTF）

`BTF_KIND_FUNC` + `BTF_KIND_FUNC_PROTO` 描述内核函数，内核通过 BTF 导出。

```c
// 5.18+
extern struct task_struct *bpf_get_task_from_pid(int pid) __ksym;
extern void bpf_task_release(struct task_struct *p) __ksym;
```

定义（在内核）：

```c
// include/.../btf_ids.h
BTF_ID_FLAGS(func, bpf_get_task_from_pid, KF_ACQUIRE | KF_RET_NULL)
```

使用：

```c
SEC("tracepoint/syscall/sys_enter_getpid")
int handle_getpid(struct trace_event_raw_sys_enter *ctx) {
    u32 pid = bpf_get_current_pid_tgid() >> 32;
    struct task_struct *p = bpf_get_task_from_pid(pid);
    if (p) {
        // 用 p 做点啥
        bpf_task_release(p);
    }
    return 0;
}
```

## BTF 调试点滴

```bash
# 看某个程序的 BTF 信息
sudo bpftool prog show id 42 --pretty

# 看 map 的 key/value 类型
sudo bpftool map show id 10 --pretty
sudo bpftool btf dump id 10
```

输出示例：

```
prog show id 42:
    name: handle_openat
    type: tracepoint
    ...
    btf_id: 100

btf dump id 100:
    ...
    type_id=1 name=event type_id=2 kind=struct
    "u32 pid" encoding=type_id=3
    ...
```

## CO-RE vs kernel-devel

| 维度 | CO-RE + BTF | kernel-devel |
|------|------------|--------------|
| 部署 | 一次编译到处跑 | 每个内核一份 |
| 编译时间 | 0 | 长 |
| 大小 | 小 | 大 |
| 类型完整性 | 全内核类型（受限） | 全（看头文件） |
| 内核要求 | ≥ 4.18 | 任何 |
| 调试便利 | 中 | 高 |

**结论**：5.4+ 内核 + CO-RE 是工业标准。

## 进一步阅读

- [BPF CO-RE reference](https://github.com/libbpf/libbpf/blob/master/docs/program_types.rst)
- [BPF Type Format (BTF) — Kernel docs](https://www.kernel.org/doc/html/latest/bpf/btf.html)
- [Cilium's BPF and XDP guide](https://docs.cilium.io/en/latest/bpf/) — 第 7 章