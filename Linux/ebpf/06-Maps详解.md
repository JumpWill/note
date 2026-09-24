# 06 - eBPF Maps 详解

> Map 是 eBPF 的「数据中枢」，是内核态和用户态之间、eBPF 程序之间共享状态的唯一机制。

## Map 是什么

```
Map = 内核分配的一段内存
   ├── 由类型决定存储结构（哈希表、数组、LRU...）
   ├── 有 max_entries 上限
   ├── 用户态用 fd 操作
   └── eBPF 程序内用 helper 操作
```

## Map 类型全景

| 类型 | 用途 | 关键特征 |
|------|------|---------|
| HASH | 通用哈希表 | O(1) 查找 |
| ARRAY | 固定索引数组 | O(1) 索引 |
| PERCPU_HASH | per-CPU 哈希 | 写多读少免锁 |
| LRU_HASH | LRU 哈希 | 自动淘汰 |
| LPM_TRIE | 最长前缀匹配 | 用于 IP 路由 |
| ARRAY_OF_MAPS | map of maps | 多组配置切换 |
| HASH_OF_MAPS | hash of maps | 路由表 |
| PROG_ARRAY | 程序数组 | tail call |
| RINGBUF | 环形缓冲 | **事件传输首选** |
| PERF_EVENT_ARRAY | perf 缓冲 | 旧事件机制 |
| STACK_TRACE | 调用栈 | 火焰图 |
| QUEUE | 队列 | FIFO |
| STACK | 栈 | LIFO |
| STRUCT_OPS | 内核结构替换 | TCP 拥塞控制 |
| BPF_MAP_TYPE_CGROUP_* | cgroup 层级 | per-cgroup 策略 |
| BPF_MAP_TYPE_TASK_STORAGE | 任务本地存储 | task_struct 私有数据 |

## 1. HASH（最常用）

```c
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 1024);
    __type(key, u32);
    __type(value, struct event);
} my_hash SEC(".maps");
```

### 操作

```c
// 写
u32 key = 42;
struct event val = {.x = 1};
bpf_map_update_elem(&my_hash, &key, &val, BPF_ANY);

// 读
struct event *p = bpf_map_lookup_elem(&my_hash, &key);
if (p) {
    // 用 p->x
}

// 删
bpf_map_delete_elem(&my_hash, &key);

// 遍历（注意：删除要谨慎，可能被 verifier 拒）
// 首轮 key 必须传 NULL，之后传上一个 key
u32 *k = NULL, nk;
while (1) {
    if (bpf_map_get_next_key(&my_hash, k, &nk))
        break;
    // 用 nk 做查询/统计
    k = &nk;
}
```

### flags 参数

```c
BPF_ANY      // 任意，存在则更新
BPF_NOEXIST  // 不存在才插入
BPF_EXIST    // 存在才更新
BPF_F_LOCK   // 加锁（per-CPU map 自动加）
```

## 2. PERCPU_HASH（写多读多场景首选）

```c
struct {
    __uint(type, BPF_MAP_TYPE_PERCPU_HASH);
    __uint(max_entries, 1024);
    __type(key, u32);
    __type(value, u64);
} pcpu_count SEC(".maps");
```

特点：
- **每个 CPU 一份 value** → 写时无锁，性能极高
- 用户态读取需要 sum 所有 CPU 副本
- **不适合复杂值**（结构体）

```c
// 写：直接 update，helper 帮你选本 CPU 的位置（不需要按 CPU 取 key）
u32 key = 1;  // key 是业务 key（PID、fd 等）
u64 *cnt = bpf_map_lookup_elem(&pcpu_count, &key);
if (cnt) (*cnt)++;
```

用户态聚合（一次拿所有 CPU 的副本）：

```c
// cpu_size 是单个 per-CPU value 的字节数
unsigned int ncpus = libbpf_num_possible_cpus();
u64 values[ncpus];  // 必须 >= ncpus × sizeof(u64)
bpf_map_lookup_percpu_elem(fd, &key, values, sizeof(u64), 0);
u64 total = 0;
for (unsigned int i = 0; i < ncpus; i++) total += values[i];
```

## 3. ARRAY（配置 map）

```c
struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __uint(max_entries, 1);
    __type(key, u32);
    __type(value, struct config);
} config SEC(".maps");
```

特点：
- key 只能是 0..max_entries-1 的整数
- key 必须从 0 开始**严格递增遍历**
- **用于全局开关、配置**

```c
SEC("xdp")
int my_prog(struct xdp_md *ctx) {
    u32 key = 0;
    struct config *cfg = bpf_map_lookup_elem(&config, &key);
    if (!cfg || !cfg->enabled) return XDP_PASS;
    // ...
}
```

## 4. LPM_TRIE（IP 路由场景）

```c
struct lpm_key {
    __u32 prefixlen;  // 前缀长度（位）
    __u32 data;       // 实际数据
};

struct {
    __uint(type, BPF_MAP_TYPE_LPM_TRIE);
    __uint(max_entries, 256);
    __type(key, struct lpm_key);
    __type(value, u32);
} ip_rules SEC(".maps");
```

用法（最长前缀匹配 IP 黑名单）：

```c
// 插入：禁止 10.0.0.0/16
struct lpm_key key = {.prefixlen = 16, .data = bpf_htonl(0x0A000000)};
u32 value = 1;
bpf_map_update_elem(&ip_rules, &key, &value, BPF_ANY);

// 查询
struct lpm_key lookup = {.prefixlen = 32, .data = bpf_htonl(0x0A000123)};
u32 *found = bpf_map_lookup_elem(&ip_rules, &lookup);
if (found) {
    // 命中，IP 在禁止范围内
    return XDP_DROP;
}
```

**典型应用**：Katran、Cilium 的 IP 规则集。

## 5. PROG_ARRAY（tail call 跳转）

```c
struct {
    __uint(type, BPF_MAP_TYPE_PROG_ARRAY);
    __uint(max_entries, 16);
    __type(key, u32);
    __type(value, u32);  // 程序 fd
} progs SEC(".maps");

SEC("classifier")
int main_prog(struct __sk_buff *skb) {
    // 跳转到 index 0 的程序
    bpf_tail_call_static(skb, &progs, 0);
    return TC_ACT_OK;
}

SEC("classifier/0")
int stage0(struct __sk_buff *skb) {
    // ... stage 0
    bpf_tail_call_static(skb, &progs, 1);
    return TC_ACT_OK;
}
```

特点：
- 类似 goto，可跳转 33 次（kernel 5.10 限制）
- **多程序协作**：解析 → 过滤 → 决策，每段一个 BPF 程序
- 用于实现有状态连接跟踪、复杂协议解析

## 6. RINGBUF（事件传输首选）

```c
struct {
    __uint(type, BPF_MAP_TYPE_RINGBUF);
    __uint(max_entries, 256 * 1024);  // 必须 page 整数倍
} events SEC(".maps");
```

特点：
- **5.8+ 内核新增**（替代 perf_event_array）
- 共享内存，零拷贝
- 支持 reserve + submit 两阶段
- 支持时间戳、自动丢事件处理

```c
// 提交事件
struct event *e = bpf_ringbuf_reserve(&events, sizeof(*e), 0);
if (!e) return 0;
e->pid = bpf_get_current_pid_tgid() >> 32;
bpf_ringbuf_submit(e, 0);  // 一次性发布
```

```c
// 用户态
struct ring_buffer *rb = ring_buffer__new(map_fd, on_event, NULL, NULL);
ring_buffer__poll(rb, 100);  // 阻塞 100ms
```

> ⚠️ `max_entries_ro` 不是 BTF map 字段。这里只是举例：ringbuf 的丢事件统计在用户态通过 `ring_buffer__epoll_wait` 的 `cnt` 返回值检查，或用 `BPF_RB_NO_WAKEUP` 控制。

## 7. ARRAY_OF_MAPS（路由表）

```c
struct {
    __uint(type, BPF_MAP_TYPE_ARRAY_OF_MAPS);
    __uint(max_entries, 4);
    __type(key, u32);
    __type(value, u32);  // inner map id
} outer SEC(".maps");
```

inner map 的类型、key/value 必须**和 outer 完全一致**。

用法：

```c
// 获得 inner map 的指针
u32 key = 1;
void *inner = bpf_map_lookup_elem(&outer, &key);
if (inner) {
    u32 k = 100;
    bpf_map_update_elem(inner, &k, &val, BPF_ANY);  // 在 inner 中操作
}
```

**典型应用**：Cilium 的 endpoint map，每个 pod 一个 inner 配置。

## 8. BPF_MAP_TYPE_TASK_STORAGE（任务私有存储）

```c
struct my_task_data {
    u64 open_count;
    u32 flags;
};

struct {
    __uint(type, BPF_MAP_TYPE_TASK_STORAGE);
    __uint(max_entries, 0);  // 必须 0
    __type(key, int);  // 任意，忽略
    __type(value, struct my_task_data);
} task_data SEC(".maps");
```

特点：
- **5.5+** 内核支持
- 类似 thread-local：每个 task_struct 自动有一个存储槽
- **不需要 cleanup**（task 退出时自动回收）

```c
SEC("tracepoint/syscalls/sys_enter_openat")
int on_openat(struct trace_event_raw_sys_enter *ctx) {
    struct task_struct *p = bpf_get_current_task();
    struct my_task_data *d = bpf_task_storage_get(&task_data, p, NULL, BPF_LOCAL_STORAGE_GET_F_CREATE);
    if (d) d->open_count++;
    return 0;
}
```

## 9. 共享 Map：多程序协作

```c
// 在 a.bpf.c
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 1024);
    __type(key, u32);
    __type(value, u64);
} shared_stats SEC(".maps");

// 在 b.bpf.c 中：声明为 extern
extern struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 1024);
    __type(key, u32);
    __type(value, u64);
} shared_stats SEC(".maps");
```

用户态加载两次（同一个 .o），maps 自动共享。

或者用 pin：

```bash
# 加载时 pin 到 /sys/fs/bpf/，下次启动复用
bpftool map pin id 10 /sys/fs/bpf/shared_stats
```

## 10. 性能考量

| Map 类型 | 写 | 读 | 遍历 | 备注 |
|---------|---|-----|------|------|
| HASH | O(1) 加锁 | O(1) 加锁 | O(n) | 默认起点 |
| PERCPU_HASH | O(1) 免锁 | O(1) 免锁 | O(n×ncpu) | 高写吞吐 |
| ARRAY_PCPU | 免锁 | 免锁 | O(n×ncpu) | 最简配置 |
| LRU_HASH | O(1) 加锁 | O(1) | O(n) | 内存可控 |
| LPM_TRIE | O(prefix) | O(prefix) | O(n) | 路由 |
| RINGBUF | 零拷贝 | 零拷贝 | 不支持 | 事件首选 |
| PROG_ARRAY | O(1) | O(1) | - | tail call |

**经验法则**：
- **配置** → ARRAY（max_entries=1）
- **状态** → HASH（需要原子）/ PERCPU_HASH（可累加）
- **事件** → RINGBUF（5.8+）
- **路由** → LPM_TRIE
- **超大有界** → LRU_HASH（防止内存爆炸）

## 11. 常见错误

### `bpf_map_lookup_elem` 返回 NULL

> 不是错误，是「key 不存在」。必须 `if (!p) return 0;` 处理。

### `bpf_map_update_elem` 返回 -EBUSY

> `BPF_NOEXIST` 但 key 已存在，或 `BPF_EXIST` 但 key 不存在。

### `max_entries` 限制

- 不能超过 `vm.max_map_count`（默认 65536）
- 启动时通过 `/proc/sys/kernel/perf_event_max_map` 调整

### RINGBUF 大小

- 必须是 page 的整数倍
- 太小会丢事件，太大浪费内存

```bash
# 系统层 RINGBUF 上限
sysctl -w kernel.bpf_stats_enabled=1
```

## 12. 用户态 Map 操作完整参考

```c
#include <bpf/bpf.h>

int fd = bpf_map__fd(skel->maps.my_map);

// 单个查/改/删
int bpf_map_lookup_elem(int fd, const void *key, void *value);
int bpf_map_update_elem(int fd, const void *key, const void *value, __u64 flags);
int bpf_map_delete_elem(int fd, const void *key);

// 遍历
int bpf_map_get_next_key(int fd, const void *key, void *next_key);

// per-CPU
int bpf_map_lookup_percpu_elem(int fd, const void *key, void *value,
                                __u32 cpu_size, __u64 flags);
int bpf_map_lookup_and_delete_elem(int fd, const void *key, void *value);

// 批量
int bpf_map_lookup_batch(int fd, void *keys, void *values, __u32 *count,
                          void *in_batch, void *out_batch, __u64 flags);
int bpf_map_update_batch(int fd, void *keys, void *values, __u32 *count, __u64 flags);

// 元数据
int bpf_map_get_info_by_fd(int fd, struct bpf_map_info *info, __u32 *info_len);
int bpf_obj_pin(int fd, const char *pathname);
int bpf_obj_get(const char *pathname);
```

## 13. 一个生产级例子：限速

```c
struct {
    __uint(type, BPF_MAP_TYPE_LRU_HASH);
    __uint(max_entries, 10240);
    __type(key, u64);   // src_ip (u32) << 32 | dst_ip
    __type(value, struct rate_entry);
} rate_limit SEC(".maps");

struct rate_entry {
    u64 last_ns;        // 上次允许时间
    u64 tokens;          // 令牌数
};

// 令牌桶算法
SEC("xdp")
int rate_limit_xdp(struct xdp_md *ctx) {
    void *data = (void *)(long)ctx->data;
    void *end = (void *)(long)ctx->data_end;
    struct ethhdr *eth = data;
    if ((void *)(eth + 1) > end) return XDP_PASS;

    // 解析 IP → key
    u32 src_ip = ((u32 *)((void *)eth + sizeof(*eth)))[0];
    u32 dst_ip = ((u32 *)((void *)eth + sizeof(*eth)))[1];
    u64 key = ((u64)src_ip << 32) | dst_ip;

    u64 now = bpf_ktime_get_ns();
    struct rate_entry *e = bpf_map_lookup_elem(&rate_limit, &key);
    if (!e) {
        struct rate_entry init = {.last_ns = now, .tokens = 100};
        bpf_map_update_elem(&rate_limit, &key, &init, BPF_ANY);
        return XDP_PASS;
    }

    // 补充令牌
    u64 elapsed = now - e->last_ns;
    e->tokens = min((u64)100, e->tokens + elapsed / 1000000);  // 1 token / ms
    e->last_ns = now;

    if (e->tokens == 0) return XDP_DROP;  // 限速
    e->tokens--;
    return XDP_PASS;
}
```