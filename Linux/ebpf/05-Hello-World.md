# 05 - Hello World：你的第一个 eBPF 程序

## 路径 1：bpftrace 一行命令（最快）

### 1.1 第一个 hello world

```bash
sudo bpftrace -e 'BEGIN { printf("hello eBPF!\n"); }'
```

输出：

```
Attaching 1 probe...
hello eBPF!
```

### 1.2 追踪进程 exec

```bash
sudo bpftrace -e 'tracepoint:syscalls:sys_enter_execve { printf("%s [%d] -> %s\n", comm, pid, str(args->filename)); }'
```

开一个终端执行 `ls /tmp`，你会看到：

```
bash [12345] -> /usr/bin/ls
ls [12346] -> /usr/bin/ls
```

### 1.3 统计每个进程的 syscall 次数

```bash
sudo bpftrace -e 't:syscalls:sys_enter_* { @[comm] = count(); }'
Ctrl-C 退出后自动打印：
^C
@[systemd] = 4
@[bash] = 12
@[ls] = 56
```

## 路径 2：libbpf + C（生产级标准）

我们写一个真正生产可用的 eBPF 程序：追踪所有 `openat` 系统调用，把文件名和 PID 打到 ringbuf。

### 2.1 项目结构

```
hello-ebpf/
├── Makefile
├── src/
│   ├── hello.bpf.c         # 内核态 eBPF 程序
│   ├── hello.c             # 用户态加载器
│   └── vmlinux.h           # 内核 BTF 头（自动生成）
└── README.md
```

### 2.2 编写内核态程序 [src/hello.bpf.c](hello.bpf.c)

```c
// SPDX-License-Identifier: GPL-2.0
#include "vmlinux.h"
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>

// 事件结构体：与用户态共享
struct event {
    u32 pid;
    u8  comm[16];
    u8  filename[256];
};

// ringbuf map：把事件从内核送到用户态
struct {
    __uint(type, BPF_MAP_TYPE_RINGBUF);
    __uint(max_entries, 256 * 1024);  // 256KB
} events SEC(".maps");

char LICENSE[] SEC("license") = "GPL";

SEC("tracepoint/syscalls/sys_enter_openat")
int handle_openat(struct trace_event_raw_sys_enter *ctx) {
    struct event *event;
    u32 pid;

    // 1. 从 ringbuf 申请一块内存
    event = bpf_ringbuf_reserve(&events, sizeof(*event), 0);
    if (!event)
        return 0;

    // 2. 填字段
    pid = bpf_get_current_pid_tgid() >> 32;
    event->pid = pid;
    bpf_get_current_comm(event->comm, sizeof(event->comm));
    bpf_probe_read_user_str(event->filename, sizeof(event->filename),
                            (char *)ctx->args[0]);

    // 3. 提交（一次性发布给用户态）
    bpf_ringbuf_submit(event, 0);
    return 0;
}
```

### 2.3 编写用户态加载器 [src/hello.c](hello.c)

```c
// SPDX-License-Identifier: GPL-2.0
#include <stdio.h>
#include <stdlib.h>
#include <signal.h>
#include <unistd.h>
#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include "hello.skel.h"

static volatile int stop = 0;
static void on_sigint(int _) { stop = 1; }

// 事件回调：每条事件触发一次
static int on_event(void *ctx, void *data, size_t sz) {
    const struct event *e = data;
    printf("pid=%-7d comm=%-16s file=%s\n",
           e->pid, e->comm, e->filename);
    return 0;
}

int main(int argc, char **argv) {
    struct hello_bpf *skel;
    struct ring_buffer *rb = NULL;
    int err;

    signal(SIGINT, on_sigint);

    // 1. 打开并加载 BPF 对象
    skel = hello_bpf__open();
    if (!skel) {
        fprintf(stderr, "open failed\n");
        return 1;
    }

    // 可选：设置参数
    // skel->rodata->my_var = 42;

    err = hello_bpf__load(skel);
    if (err) {
        fprintf(stderr, "load failed: %d\n", err);
        goto cleanup;
    }

    // 2. 挂载
    err = hello_bpf__attach(skel);
    if (err) {
        fprintf(stderr, "attach failed: %d\n", err);
        goto cleanup;
    }

    // 3. 创建 ringbuffer 并设置回调
    rb = ring_buffer__new(bpf_map__fd(skel->maps.events),
                          on_event, NULL, NULL);
    if (!rb) {
        fprintf(stderr, "ring_buffer create failed\n");
        goto cleanup;
    }

    printf("Tracing openat... Ctrl-C to stop\n");

    // 4. 事件循环
    while (!stop) {
        err = ring_buffer__poll(rb, 100 /*ms*/);
        if (err < 0 && err != -EINTR) {
            fprintf(stderr, "poll failed: %d\n", err);
            break;
        }
    }

cleanup:
    ring_buffer__free(rb);
    hello_bpf__destroy(skel);
    return 0;
}
```

### 2.4 Makefile

```makefile
CLANG ?= clang
BPFTOOL ?= bpftool

INCLUDES := -I/usr/include

# vmlinux.h 自动从内核 BTF 生成
SRC := src
TARGET := hello

.PHONY: all clean

all: $(TARGET)

vmlinux.h:
	$(BPFTOOL) btf dump file /sys/kernel/btf/vmlinux format c > $@

$(SRC)/%.bpf.o: $(SRC)/%.bpf.c vmlinux.h
	$(CLANG) -O2 -g -Wall -target bpf -D__TARGET_ARCH_x86 \
		-fno-stack-protector -fno-jump-tables \
		$(INCLUDES) -c $< -o $@

$(SRC)/%.skel.h: $(SRC)/%.bpf.o
	$(BPFTOOL) gen skeleton $< > $@

$(TARGET): $(SRC)/hello.c $(SRC)/hello.skel.h
	$(CLANG) -O2 -g -Wall $(SRC)/hello.c -o $@ \
		-lbpf -lelf -lz -static

clean:
	rm -f $(SRC)/*.o $(SRC)/*.skel.h vmlinux.h $(TARGET)
```

### 2.5 编译运行

```bash
cd hello-ebpf
make
sudo ./hello
# 在另一个终端
ls /tmp
cat /etc/hostname
```

输出示例：

```
Tracing openat... Ctrl-C to stop
pid=12345   comm=cat            file=/etc/hostname
pid=12346   comm=ls             file=/tmp
pid=12347   comm=bash           file=/etc/profile
```

## 路径 3：bcc Python 嵌入

适合**快速开发**或**动态部署**的程序。

```python
#!/usr/bin/env python3
from bcc import BPF

prog = """
#include <uapi/linux/ptrace.h>
#include <linux/sched.h>

struct event_t {
    u32 pid;
    char comm[TASK_COMM_LEN];
    char filename[256];
};

BPF_RINGBUF_OUTPUT(events, 256 * 1024);

int trace_openat(struct trace_event_raw_sys_enter *ctx) {
    struct event_t *e;
    e = events.ringbuf_reserve(sizeof(*e), 0);
    if (!e) return 0;

    e->pid = bpf_get_current_pid_tgid() >> 32;
    bpf_get_current_comm(e->comm, sizeof(e->comm));
    bpf_probe_read_user_str(e->filename, sizeof(e->filename),
                            (char *)ctx->args[0]);
    events.ringbuf_submit(e, 0);
    return 0;
}
"""

b = BPF(text=prog)
b.attach_raw_tracepoint(tp="sys_enter_openat", fn_name="trace_openat")

print("Tracing openat... Ctrl-C to stop")

def on_event(ctx, data, size):
    event = b["events"].event(data)
    print(f"pid={event.pid} comm={event.comm.decode()} "
          f"file={event.filename.decode()}")

b["events"].open_ring_buffer(on_event)
try:
    while True:
        b.ring_buffer_consume()
except KeyboardInterrupt:
    pass
```

```bash
sudo python3 trace_openat.py
```

## 三种路径对比

| 维度 | bpftrace | bcc | libbpf + C |
|------|---------|-----|-----------|
| 部署速度 | ★★★★★ | 一生 | ★★ |
| 性能 | ★★★ | ★★★ | ★★★★★ |
| 内核版本兼容 | ★ | ★ | ★★★★★（CO-RE） |
| 生产可用 | 不推荐 | 可以 | **推荐** |
| 学习曲线 | 平缓 | 中等 | 较陡 |

## 调试时常见报错

### `failed to open BPF object file: No such file or directory`

```bash
# 检查文件存在、绝对路径正确
ls -la hello.bpf.o
```

### `Verifier output: ... invalid mem access`

> Verifier 拒绝。最常见原因：
> 1. 越界读：没 `if (ptr + 1 > end)`
> 2. 用户态/内核态混淆：`bpf_probe_read_user` vs `bpf_probe_read_kernel`
> 3. 栈空间不足
>
> 看完整 log：`sudo cat /sys/kernel/debug/tracing/trace_pipe` 或 `--debug`

### `failed to load: invalid argument`（libbpf）

```bash
# 加载时 verbose 看 verifier 输出
sudo strace -e bpf ./hello 2>&1 | grep -i bpf
# 或使用环境变量
LIBBPF_STRICT=0 ./hello
```

### `failed to attach`

> 程序加载成功了，但挂载失败。可能：
> - 内核不支持该 hook（`/proc/version` 检查）
> - 内核版本低于预期
> - 没 root 权限
> - `tracepoint/syscalls/sys_enter_openat` 名字写错

## 进阶：多程序协作

```c
// hello.bpf.c 扩展
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 10240);
    __type(key, u32);    // pid
    __type(value, u64);  // 计数
} open_count SEC(".maps");

SEC("kprobe/dup_task_struct")
int on_fork(struct pt_regs *ctx) {
    u32 pid = bpf_get_current_pid_tgid() >> 32;
    u64 *cnt, one = 1;

    cnt = bpf_map_lookup_elem(&open_count, &pid);
    if (cnt) {
        *cnt += 1;
    } else {
        bpf_map_update_elem(&open_count, &pid, &one, BPF_ANY);
    }
    return 0;
}
```

用户态查询：

```c
// 列出所有 pid 的 openat 计数
static int dump_count_map(int fd) {
    struct bpf_map_info info;
    uint32_t info_len = sizeof(info);

    bpf_map_get_info_by_fd(fd, &info, &info_len);

    // 遍历所有 key
    u32 key, next_key;
    u64 value;
    for (key = 0;;) {
        if (bpf_map_get_next_key(fd, &key, &next_key))
            break;
        if (bpf_map_lookup_elem(fd, &next_key, &value) == 0)
            printf("pid=%u open_count=%llu\n", next_key, value);
        key = next_key;
    }
    return 0;
}
```

## 链接

- [BPF Performance Tools](http://www.brendangregg.com/bpf-performance-tools-book.html) 第 1-3 章：brendan gregg 的入门示例
- [libbpf-bootstrap](https://github.com/libbpf/libbpf-bootstrap)：官方模板项目
- [eunomia-bpf/eBPF-hello-world](https://github.com/eunomia-bpf/eBPF-hello-world)：中文示例集
- [Cilium 官方教程](https://docs.cilium.io/en/latest/bpf/)：进阶必看