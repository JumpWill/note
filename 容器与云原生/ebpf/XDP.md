## 概念

XDP（eXpress Data Path）是 eBPF 的网络数据面 hook，跑在 NIC 驱动里，**包还没分配 skb 就已经过 XDP 了**。是内核网络栈里最早能拦截包的位置，单核单 NIC 能到 24 Mpps+，延迟 ~μs 级。

普通路径：`DMA → skb alloc → netif_receive_skb → ip_rcv → ...`
XDP 路径：`DMA → BPF program → XDP_TX / XDP_DROP / XDP_PASS(才进 skb)`

XDP 程序拿到的是 `struct xdp_md`，里面有 `data / data_end / ingress_ifindex / rx_queue_index`，**不是 sk_buff**——所有解析要从裸以太网帧头手工来。

## 三种运行模式

| 模式 | 跑在哪 | 性能 | 限制 |
| --- | --- | --- | --- |
| **Native (driver) XDP** | NIC 驱动里，DMA 之后立刻 | 最高，单核 ~24 Mpps | 要驱动支持：i40e / ice / mlx5 / nfp / virtio-net 较新版本 |
| **Generic XDP** | 内核 netif_receive_skb 路径里的 fallback | 慢 ~10x（要走 skb alloc） | 任何 NIC 都能跑，只适合测试 / 原型 |
| **Offloaded XDP** | NIC 硬件本身（SmartNIC / FPGA） | 极低延迟，CPU 几乎不占 | 受 NIC 指令集限制，Netronome NFP / 部分 Mellanox |

生产用 Native；开发 / CI 用 Generic 兜底。

## XDP 程序返回值

```c
enum xdp_action {
    XDP_ABORTED = 0,   // 程序出错,丢包 + 触发 trace
    XDP_DROP,          // 直接丢,最高效
    XDP_PASS,          // 走正常内核协议栈
    XDP_TX,            // 从原 NIC 出口弹回去(MAC 交换),最快的回包
    XDP_REDIRECT,      // 重定向到另一个 NIC / CPUMAP / AF_XDP socket
};
```

```c
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
```

每个指针解引用都要 `data_end` 边界检查，**否则 verifier 拒**。

## 应用场景

* **DDOS 抗攻击**：SYN flood / UDP flood / 反射放大，在 XDP 直接 DROP，比 iptables 早 ~10 倍到达
* **L4 负载均衡**：Katran、Cloudflare Spectrum。`XDP_TX` 一来一回，CGNAT / Maglev 一致性哈希
* **防火墙 / 黑名单**：毫秒级封禁 IP 段
* **流量染色 / 镜像**：`XDP_TX` 把原始包弹给旁路分析系统
* **可观测**：Cilium Hubble、netdata、Pixie 的网络部分
* **AF_XDP 用户态 socket**：完全跳过内核协议栈，收包进用户态（io_uring + AF_XDP 是高频交易常见搭配）

## Attach 方式

三种挂法：

```bash
# 1. 旧：setsockopt,只能挂一个
ip link set dev eth0 xdp obj app.bpf.o sec xdp

# 2. 新（推荐）：netlink + flags,可以多挂/替换
ip link set dev eth0 xdp pinned /sys/fs/bpf/app obj app.bpf.o sec xdp

# 3. 通过 bpftool / libbpf 的 bpf_link_create
bpftool net attach xdp pinned /sys/fs/bpf/app dev eth0
```

代码侧用 `bpf_xdp_attach()` 或 `bpf_link_create()`，Native vs Generic 由 `XDP_FLAGS_HW_MODE` / `XDP_FLAGS_SKB_MODE` / `XDP_FLAGS_DRV_MODE` 控制。

## 代码示例

### C + libbpf

见上面 `drop_ssh` 完整例子。完整骨架：

```c
#include <linux/bpf.h>
#include <bpf/bpf_helpers.h>

SEC("xdp")
int drop_ssh(struct xdp_md *ctx) { ... }

char _license[] SEC("license") = "GPL";
```

加载：

```c
skel->links.drop_ssh = bpf_program__attach_xdp(
    skel->progs.drop_ssh, "eth0", XDP_FLAGS_DRV_MODE, NULL);
```

### Rust + aya

```rust
use aya::programs::{Xdp, XdpFlags};

let prog: &mut Xdp = bpf.program_mut("drop_ssh")?.try_into()?;
prog.load()?;
prog.attach("eth0", XdpFlags::default())?;
```

### Go + cilium/ebpf

```go
lprog, _ := prog.AssignUninitialized()
defer lprog.Close()
lprog.AttachXDP("eth0", 0)   // 0 = native 优先,失败 fallback generic
```

## 性能参考

| 操作 | 延迟 | 吞吐 |
| --- | --- | --- |
| XDP_DROP（纯丢包） | ~100ns | ~24 Mpps/核 |
| XDP_PASS（放行） | ~500ns | ~10 Mpps/核（要给内核栈） |
| XDP_TX（回弹） | ~200ns | ~12 Mpps/核 |
| XDP_REDIRECT → CPUMAP | ~1μs | ~6 Mpps/核 |
| Generic XDP | 比 Native 慢 5–10x | ~2–3 Mpps/核 |
| iptables 同等 DROP（对比） | ~1–3μs | ~3 Mpps/核 |

CPU：mlx5 / ice 单核跑满 24 Mpps 用 ~60% 一个核。

## 限制与坑

* **看不到 TCP 状态**：XDP 没有 socket、没有 conntrack，stateful 防火墙要做在 TC 或 socket hook
* **只能用有限的 helper**：能用 `bpf_redirect` / `bpf_fib_lookup` / `bpf_csum_diff` 等，但 `bpf_skb_ancestor_*` 类拿不到
* **不支持 IP 重组 / GSO 重组**：大包拆成小包要靠 NIC 自己；分片处理要在 TC
* **云限制**：virtio-net 在大部分云上不支持 Native XDP，只能 Generic（慢）；AWS ENA、Azure vFP 都不行。要真 Native 必须 SR-IOV + VF passthrough
* **load 不上**：驱动不支持、CPU 架构不支持、BTF 缺失都会失败，dmesg 看 `journalctl -k | grep xdp`
* **挂不上多个**：`ip link set xdp` 老接口一次只能挂一个，要叠加用 `bpf_link_create` 的 multi-attach

## XDP vs TC ingress

| 维度 | XDP | TC ingress (clsact) |
| --- | --- | --- |
| 位置 | NIC driver，skb alloc 前 | qdisc 层，有 skb |
| 性能 | 高 | 中 |
| 能看到 | 裸 L2 帧 | skb / 网络层信息齐全 |
| 适合 | DDOS、L4 LB、纯 L2/L3 决策 | stateful、L7、需要 conntrack 的策略 |
| 与 iptables / nftables 关系 | 早于它们 | 同级，可替代 |

简单规则：**只 DROP / TX / 简单 redirect 用 XDP；要状态、要看 socket 用 TC**。

## 生产案例

* **Cloudflare**：Magic Transit / Spectrum 用 XDP 做全球 DDoS 抗，DPDK-style LB
* **Meta**：Katran L4 LB 跑在 XDP 上
* **Cilium**：node-to-node 转发、load balancing、policy 都走 XDP + TC
* **Cloudflare 1.1.1.1**：XDP_TX 加快 DNS 应答
* **高频交易**：io_uring + AF_XDP 收行情，自己写驱动接收
* **NFV**：运营商 vCPE、vBRAS 用 XDP 做边缘网关

## 一句话

**XDP 是内核网络栈最早的可编程 hook，跑在 NIC 驱动里；适合 DDOS / L4 LB / 简单转发；Native 模式单核 ~24 Mpps，但驱动和云环境都受限**。
