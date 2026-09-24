# 08 - eBPF Helpers 与 API

> Helper 是 eBPF 程序与内核交互的官方 API。Linux 5.x 已有 **200+ 个 helper**。

## Helper 的来源

```
内核源码 /include/uapi/linux/bpf.h
    │
    │  enum bpf_func_id {
    │      BPF_FUNC_map_lookup_elem,
    │      BPF_FUNC_map_update_elem,
    │      BPF_FUNC_map_delete_elem,
    │      ...
    │  };
    ▼
libbpf (bpf_helpers.h) 提供同名 inline 函数封装
    │
    ▼
clang 编译为 eBPF 字节码
    ▼
内核 verifier 验证调用合法性
    ▼
运行时解析 helper 编号到函数指针
```

## 分类速查表

| 类别 | 数量 | 重要 helper |
|------|------|------------|
| Map 操作 | 20+ | `bpf_map_lookup_elem`、`bpf_map_update_elem` |
| 时间 | 5+ | `bpf_ktime_get_ns`、`bpf_jiffies64` |
| 进程/任务 | 15+ | `bpf_get_current_pid_tgid`、`bpf_get_current_task` |
| 网络 | 30+ | `bpf_redirect`、`bpf_skb_store_bytes` |
| 安全/上下文 | 10+ | `bpf_get_func_arg`、`bpf_probe_read_kernel` |
| 输出 | 8 | `bpf_ringbuf_output`、`bpf_trace_printk` |
| 调试 | 6 | `bpf_override_return`、`bpf_send_signal` |
| BPF 程序间 | 6 | `bpf_tail_call`、`bpf_get_attach_cookie` |
| 转换 | 8 | `bpf_probe_write_user`、`bpf_probe_read` |
| 调度/cgroup | 8 | `bpf_cgroup_path`、`bpf_get_cgroup_classid` |

## 1. Map 操作

### 通用

```c
void *bpf_map_lookup_elem(struct bpf_map *map, const void *key);
long bpf_map_update_elem(struct bpf_map *map, const void *key, const void *value, u64 flags);
long bpf_map_delete_elem(struct bpf_map *map, const void *key);
long bpf_map_push_elem(struct bpf_map *map, const void *value, u64 flags);
long bpf_map_pop_elem(struct bpf_map *map, void *value);
long bpf_map_peek_elem(struct bpf_map *map, void *value);
long bpf_map_lookup_and_delete_elem(struct bpf_map *map, void *key, void *value);
```

注意：
- `lookup` 返回的指针**不可缓存**（map 元素可能被删）
- `flags` 必须是编译期常量，verifier 才能验证

### Flag 详解

```c
BPF_ANY          // 0
BPF_NOEXIST      // key 不存在才插入（新增）
BPF_EXIST        // key 存在才更新（计数器）
BPF_F_LOCK       // 加锁（per-CPU 内部用）
```

## 2. 时间类

```c
u64 bpf_ktime_get_ns(void);                      // 单调时间，ns
u64 bpf_ktime_get_boot_ns(void);                 // 自 boot 时间
u64 bpf_ktime_get_coarse_ns(void);               // 较快
u64 bpf_jiffies64(void);                          // jiffies
u64 bpf_get_ns_current_pid_tgid(u64 pid_tgid);    // 单调时间 + PID namespace
```

### 用法：测量耗时

```c
SEC("kprobe/do_sys_open")
int enter(struct pt_regs *ctx) {
    u64 pid_tgid = bpf_get_current_pid_tgid();
    u64 start = bpf_ktime_get_ns();
    bpf_map_update_elem(&start_map, &pid_tgid, &start, BPF_ANY);
    return 0;
}

SEC("kretprobe/do_sys_open")
int exit(struct pt_regs *ctx) {
    u64 pid_tgid = bpf_get_current_pid_tgid();
    u64 *start = bpf_map_lookup_elem(&start_map, &pid_tgid);
    if (!start) return 0;
    u64 delta = bpf_ktime_get_ns() - *start;
    bpf_printk("open() took %llu ns\n", delta);
    bpf_map_delete_elem(&start_map, &pid_tgid);
    return 0;
}
```

## 3. 进程/任务

```c
u64 bpf_get_current_pid_tgid(void);    // 64位：低32=pid, 高32=tgid
u64 bpf_get_current_uid_gid(void);     // 64位：低32=uid, 高32=gid
u32 bpf_get_current_pid(void);          // 仅 4.18+，建议用 pid_tgid
u64 bpf_get_current_cgroup_id(void);
u32 bpf_get_current_cgroup_id_32(void);  // 32 位版本
struct task_struct *bpf_get_current_task(void);
long bpf_get_current_comm(void *buf, u32 size);   // 进程名
long bpf_task_pt_regs(struct task_struct *tsk);
u32 bpf_get_current_pid_tgid_64(void);   // 64位（仅当内核 64位）

long bpf_send_signal(u32 sig);   // 向当前进程发信号
```

### 用法：基于 UID 限流

```c
SEC("tracepoint/syscalls/sys_enter_connect")
int limit_uid(struct trace_event_raw_sys_enter *ctx) {
    u64 uid_gid = bpf_get_current_uid_gid();
    u32 uid = uid_gid;       // 低 32 位
    if (uid == 0) return 0;  // root 例外

    // 检查该 uid 的频率
    u64 *count = bpf_map_lookup_elem(&uid_conn_count, &uid);
    if (count && *count > 100) {
        bpf_send_signal(SIGTERM);
        return 1;
    }
    if (!count) {
        u64 one = 1;
        bpf_map_update_elem(&uid_conn_count, &uid, &one, BPF_ANY);
    } else {
        *count += 1;
    }
    return 0;
}
```

## 4. 网络类（最丰富）

### SKB 读写

```c
long bpf_skb_load_helper(const void *skb, const void *data, int headlen, int datalen);
long bpf_skb_load_bytes(const void *skb, u32 offset, void *to, u32 len);
long bpf_skb_store_bytes(struct __sk_buff *skb, u32 offset, const void *from, u32 len, u64 flags);
long bpf_skb_load_bytes_relative(const void *skb, u32 offset, void *to, u32 len, u32 start);
```

### 重定向

```c
long bpf_redirect(u32 ifindex, u64 flags);
long bpf_redirect_map(struct bpf_map *map, u32 key, u64 flags);
long bpf_redirect_peek(u64 flags, u64 *ifindex, u64 *flags);
long bpf_redirect_neigh(u32 ifindex, struct bpf_redir_neigh *params, int plen, u64 flags);
long bpf_redirect_xdp(u32 ifindex, u64 flags);   // XDP 内 redirect
```

### 包头改写

```c
long bpf_l3_csum_replace(struct __sk_buff *skb, u32 offset, u64 from, u64 to, u64 size);
long bpf_l4_csum_replace(struct __sk_buff *skb, u32 offset, u64 from, u64 to, u64 size);
long bpf_csum_diff(void *from, u32 from_size, void *to, u32 to_size, __wsum seed);
long bpf_csum_update(struct __sk_buff *skb, u32 offset, __wsum csum);
```

### MTU / 长度

```c
u32 bpf_skb_get_tunnel_key(struct __sk_buff *skb, struct bpf_tunnel_key *key, u32 size, u64 flags);
u32 bpf_skb_set_tunnel_key(struct __sk_buff *skb, const struct bpf_tunnel_key *key, u32 size, u64 flags);
u32 bpf_skb_change_head(struct __sk_buff *skb, u32 head_room, u64 flags);    // 修改 headroom
long bpf_skb_change_proto(struct __sk_buff *skb, const void *proto, u64 flags);
long bpf_skb_adjust_room(struct __sk_buff *skb, s32 len_diff, u32 mode, u64 flags);
```

### 用法：DSR（直接服务返回）

```c
// 在 XDP 中修改目的地址，回复路由不再走 LB
SEC("xdp")
int dsr_xdp(struct xdp_md *ctx) {
    // 读 IP/TCP 头，修改目的 MAC/IP 指向真正服务端
    // ...
    return XDP_TX;  // 原路返回
}
```

## 5. 输出事件

### `bpf_trace_printk`（**已废弃**，仅学习用）

```c
long bpf_trace_printk(const char *fmt, u32 fmt_size, ...);
```

使用：

```c
bpf_trace_printk("openat pid=%d comm=%s\\n", pid, comm);

// 用户态读
sudo cat /sys/kernel/debug/tracing/trace_pipe
```

**缺点**：
- fmt 串占指令空间
- 单 trace_pipe 共享，多程序抢
- 不支持任意格式

**推荐 → ringbuf**：

```c
struct event { u32 pid; u8 comm[16]; u64 ts; };

SEC("tracepoint/syscalls/sys_enter_openat")
int h(struct trace_event_raw_sys_enter *ctx) {
    struct event *e = bpf_ringbuf_reserve(&rb, sizeof(*e), 0);
    if (!e) return 0;
    e->pid = bpf_get_current_pid_tgid() >> 32;
    e->ts  = bpf_ktime_get_ns();
    bpf_get_current_comm(e->comm, sizeof(e->comm));
    bpf_ringbuf_submit(e, 0);
    return 0;
}
```

### ringbuf 输出 helper

```c
void *bpf_ringbuf_reserve(struct bpf_map *ringbuf, u64 size, u64 flags);
void bpf_ringbuf_submit(void *ringbuf, u64 flags);   // 提交
void bpf_ringbuf_discard(void *ringbuf, u64 flags);  // 丢弃
```

flags：
- `BPF_RB_NO_WAKEUP` - 不唤醒用户态轮询
- `BPF_RB_FORCE_WAKEUP` - 强制唤醒

### `bpf_override_return`

```c
long bpf_override_return(struct pt_regs *regs, u64 rc);   // 改 func 函数指针的返回
```

仅限 `SEC("kprobe")` 程序，能**模拟函数返回**：

```c
SEC("kprobe/sys_openat")
int kprobe__sys_openat(struct pt_regs *ctx) {
    // 把所有 openat 都返回 -1
    bpf_override_return(ctx, -1);
    return 0;
}
```

## 6. 安全/上下文

```c
long bpf_probe_read_kernel(void *dst, u32 size, const void *src);   // 内核态读
long bpf_probe_read_user(void *dst, u32 size, const void *src);     // 用户态读
long bpf_probe_read_kernel_str(void *dst, u32 size, const void *src);
long bpf_probe_read_user_str(void *dst, u32 size, const void *src);

// 5.8+
long bpf_copy_from_user(void *dst, u32 size, const void *src);
long bpf_copy_to_user(void *dst, u32 size, const void *src);

long bpf_probe_write_user(void *dst, const void *src, u32 len);  // 写用户态（受限）

long bpf_get_func_arg(struct pt_regs *ctx, u32 n, u64 *value);     // 函数参数
long bpf_get_func_ret(struct pt_regs *ctx, u64 *ret);
long bpf_get_func_arg_cnt(struct pt_regs *ctx);

u64 bpf_get_attach_cookie(void *ctx);
u64 bpf_ktime_get_boot_ns(void);
```

> ⚠️ `bpf_probe_read` 在 5.11+ 已弃用；明确区分 `kernel` / `user`。

### 用法：读大结构体

```c
struct filename f = {};
bpf_probe_read_kernel(&f, sizeof(f), (void *)PT_REGS_PARM1(ctx));
```

## 7. BPF 程序间

```c
void bpf_tail_call_static(struct __sk_buff *skb, struct bpf_map *prog_array, u32 index);
long bpf_tail_call(void *ctx, struct bpf_map *prog_array, u32 index);
```

用于程序间跳转：

```c
SEC("classifier/0")
int stage0(struct __sk_buff *skb) {
    // 解析
    bpf_tail_call_static(skb, &progs, 1);
    return TC_ACT_OK;
}

SEC("classifier/1")
int stage1(struct __sk_buff *skb) {
    // 处理
    return TC_ACT_SHOT;
}
```

## 8. 信号 / 调度

```c
long bpf_send_signal(u32 sig);                // 自杀
long bpf_send_signal_thread(u32 sig);          // 给整个线程组
long bpf_signal(u32 sig, void *info);          // 带信息
u32 bpf_get_smp_processor_id(void);           // 当前 CPU
u32 bpf_get_numa_node_id(void);
```

## 9. LSM hook 专用

```c
u64 bpf_get_current_cgroup_id(void);
u64 bpf_get_attach_cookie(void);
bpf_get_task_stack(struct task_struct *task, void *buf, u32 len, u64 flags);
```

## 10. 调试

```c
long bpf_trace_vprintk(const char *fmt, u32 fmt_len, const void *args, u32 data_len);
long bpf_get_prandom_u32(void);
```

## Helper 兼容性查询

### 用户态检查

```c
#include <bpf/bpf.h>

// 程序 fd 上调用的 helper 列表
struct bpf_prog_info info;
info.nr_func_info = 0;
bpf_obj_get_info_by_fd(prog_fd, &info, &info_sz);

// 也可以用 bpftool
// bpftool prog show id 42 --pretty | grep 'helpers'
```

### 内核侧验证 helper 兼容性

```bash
# 你的内核支持哪些 helper
grep "BPF_FUNC_" /usr/include/linux/bpf.h | head -20
```

## 自定义 helper / kfunc

### 用户态自定义 helper（其实只是把逻辑放到用户态）

eBPF 程序通过 map + 用户态协作实现「自定义 helper」。

### 内核 kfunc（5.18+，标准方案）

```c
// 内核侧
// kernel/bpf/.../custom.c
__bpf_kfunc struct task_struct *bpf_get_my_task(void) {
    return current;
}
BTF_ID_FLAGS(func, bpf_get_my_task, KF_ACQUIRE | KF_RET_NULL)
```

用户态：

```c
// eBPF 程序内
extern struct task_struct *bpf_get_my_task(void) __ksym;

SEC("tracepoint/syscall/sys_enter_getpid")
int h(struct trace_event_raw_sys_enter *ctx) {
    struct task_struct *p = bpf_get_my_task();
    // ...
}
```

## helper 使用规则

### verifier 对 helper 的检查

1. **参数类型**必须正确
2. **flag 值**必须是编译期常量
3. **返回类型**是否正确处理（NULL 检查）
4. **上下文允许**（例如 `bpf_redirect` 只能在 TC/XDP 中调用）

### 常见错误

#### `R0 invalid mem access` 类的越界

```c
// 错：
void *p = bpf_map_lookup_elem(&m, &k);
if (!p) return 0;
return *p;  // verifier 跟踪不到 R0 类型

// 对：
u64 v = 0;
bpf_map_lookup_elem(&m, &k);  // R0 = p or NULL
if (R0 != 0) {                // 或 if (!p) 检查
    v = *p;
}
```

#### `helper call func not allowed in program`

```c
// 错：bpf_redirect 用在 kprobe 中
SEC("kprobe/do_sys_open") int h(...) { bpf_redirect(...); }  // 拒

// 对：用在 TC
SEC("classifier") int h(...) { bpf_redirect(...); }
```

#### `negative offset from BPF stack`

```c
// 错：栈指针偏移写成负数
long *p = (long *)(&mystack - 1);  // 拒

// 对：保持偏移非负
long *p = (long *)mystack;
```

## 性能 hint

- 优先 per-CPU map（避免锁）
- ringbuf 而非 perf_event_array
- `bpf_ktime_get_coarse_ns()` 而非 `bpf_ktime_get_ns()`（代价更小，精度低）

## 进阶：list of helpers

完整列表：

```bash
# 已编译到内核的 helpers（带 ID）
bpftool btf dump file /sys/kernel/btf/vmlinux | grep -A 2 FUNC

# 用户态定义（libbpf bpf_helpers.h）
grep "static long(" /usr/include/bpf/bpf_helpers.h | head -30

# 全部 helper ID
grep -E "BPF_FUNC_" /usr/include/linux/bpf.h
```

文档参考：

- 内核文档：[https://www.kernel.org/doc/html/latest/bpf/](https://www.kernel.org/doc/html/latest/bpf/)
- libbpf 文档：[https://github.com/libbpf/libbpf/blob/master/docs/helpers.rst](https://github.com/libbpf/libbpf/blob/master/docs/helpers.rst)
- Brendan Gregg 的 BPF Performance Tools 一书附录 B 有完整 helper 速查表