# Calico eBPF 数据面详解

> Calico 默认数据面是 **Linux 路由表 + iptables**，但从 v3.13+ 开始提供了 **eBPF 数据面**选项，
> 把 kube-proxy 的 iptables 规则 + Pod 转发的 conntrack 全换成 eBPF 程序，性能提升 30%+。
> 这篇讲清楚：
> 1. eBPF 在 Calico 里到底做了啥
> 2. 怎么开启 / 配置
> 3. 性能调优点
> 4. 限制 / 要求 / 排查

---

## 一、什么是 eBPF（30 秒讲清）

```text
eBPF（extended Berkeley Packet Filter）= Linux 内核里的"沙箱程序运行机制"

一句话：
  - 用户写一段 C 代码 → 编译成 eBPF 字节码 → 加载到内核
  - 挂在某个内核钩子点（网络、XDP、tracepoint...）
  - 数据包 / 系统调用经过时，eBPF 程序先处理

跟传统 iptables 的区别：

  iptables：匹配规则是链表（O(n) 遍历），数据包每跳都查
  eBPF：    程序直接在协议栈跑（O(1) 哈希查表 / 跳转），效率高一个数量级

类比：
  iptables = 邮局里翻名单本找人（慢）
  eBPF    = 进门刷身份证号直接定位（快）
```

---

## 二、Calico eBPF 数据面 vs Linux 数据面

### 2.1 两种数据面对比

| 维度 | Linux 数据面（默认） | eBPF 数据面 |
| --- | --- | --- |
| kube-proxy | 需要（iptables / IPVS 模式） | **不需要**（eBPF 直接接管 Service 转发） |
| iptables 规则 | 几万条（Service 多时） | 0 条（eBPF map 替代） |
| conntrack | 走内核 conntrack 表 | Calico 自管 conntrack map |
| Service 转发路径 | iptables → conntrack → netfilter | XDP / TC hook → eBPF → 直发 |
| NodePort / DNAT | kube-proxy 实现 | Calico eBPF 实现 |
| Pod 路由 | iproute2 + ip rule（策略路由） | eBPF program |
| Host → Pod | iptables 规则链 | eBPF map 查表 |
| Pod → 外部（源 IP 转换） | iptables masquerade | eBPF 做 SNAT |
| Pod 网络策略 | iptables 规则链 | eBPF program（L3/L4） |
| 性能（Service 多） | 慢（O(n)） | **快（O(1)）** |

### 2.2 eBPF 在 Calico 中的角色

```text
Calico 数据面分两部分：

  ┌──────────────────────────────┐
  │  控制平面（一直没变）          │
  │  - Felix（策略下发）          │
  │  - BIRD（BGP 路由同步）       │
  │  - confd（配置生成）          │
  └──────────────┬───────────────┘
                 │ 下发策略 + 路由
                 ▼
  ┌──────────────────────────────┐
  │  数据平面（可切换）            │
  │  Linux 数据面：iptables + conntrack
  │  eBPF 数据面：eBPF 程序 + map  ← 本文档主角
  └──────────────────────────────┘
```

**eBPF 接管的部分**：

```text
1. Service 转发（kube-proxy 功能）
   ClusterIP / NodePort / LoadBalancer / ExternalIP
   全走 eBPF map 查表，不写一条 iptables 规则

2. Pod 间转发
   Pod → Pod：直接 eBPF 查 endpoint，转发
   跨节点：eBPF 改下一跳 MAC（不查路由表）

3. 网络策略（NetworkPolicy）
   CalicoProfile 程序在内核做 L3/L4 策略判定
   不再下 iptables 规则

4. 源 IP 转换（masquerade / SNAT）
   Pod 出网时直接 eBPF 改包头 SNAT
```

---

## 三、架构细节：eBPF 钩子点怎么挂

### 3.1 Calico 用到的内核钩子点

```text
┌─────────────────────────────────────────────────────────────┐
│                          数据包路径                          │
│                                                             │
│  [网卡驱动] → [XDP] → [TC ingress] → [协议栈] → [TC egress] → [网卡驱动]
│                ↓            ↓                              ↓
│           eBPF/XDP    eBPF/TC                        eBPF/TC
│           (NodePort,  (Pod 间转发,                    (Pod → 外部,
│            LoadBalancer)  网络策略)                     SNAT)
└─────────────────────────────────────────────────────────────┘
```

| 钩子点 | 挂载位置 | Calico 用它做啥 |
| --- | --- | --- |
| **XDP** (eXpress Data Path) | 网卡驱动收包后最早一刻 | NodePort / LoadBalancer / 外部流量 DNAT（绕过协议栈，最快） |
| **TC ingress** | 协议栈入栈前 | Pod 收到的包，校验 + 策略 + conntrack |
| **TC egress** | 协议栈出栈后 | Pod 发出的包，路由 + 策略 + SNAT |

### 3.2 三种 XDP 模式

```text
XDP 有三种运行模式：

  Native XDP
    - 由网卡驱动直接支持
    - 性能最好（最早就拦截）
    - 但要求驱动支持（mlx5、i40e 等）
    - Calico 默认不要求

  Generic XDP
    - 内核模拟实现，所有网卡都支持
    - 性能比 Native 差一些
    - Calico 默认模式（兼容性好）

  Offloaded XDP
    - 程序卸载到网卡硬件执行
    - 性能最好但功能受限（不能做 conntrack）
    - Calico 用不上
```

### 3.3 eBPF Map（数据存哪）

```text
Calico 用到的关键 eBPF map：

  ① endpoints map
     key = IP, value = Pod 接口索引
     → Service ClusterIP 查询这个

  ② conntrack map
     key = 五元组, value = 状态 + 重写信息
     → eBPF 自己管 conntrack，不再走内核 nf_conntrack

  ③ nat map
     key = 五元组, value = 转换后的地址
     → DNAT / SNAT 用

  ④ policy map
     key = endpoint ID, value = 策略规则
     → NetworkPolicy 判定

 ⑤  routes map
    key = CIDR, value = 下一跳
    → 替代 ip route
```

---

## 四、开启 eBPF 数据面

### 4.1 前置要求

```text
硬性要求：

  ✅ 内核版本 ≥ 4.19（推荐 5.4+，5.10 LTS 更稳）
     - CentOS 7 内核 3.10 → 不行（升级内核或换 OS）
     - Ubuntu 20.04 默认 5.4 → 完美
     - RHEL 8 默认 4.18 → 边缘可用
     - RHEL 9 / Rocky 9 / Ubuntu 22.04 默认 5.15+ → 完美

  ✅ 架构：x86_64 / arm64
     - 其他架构（ppc64le / s390x）3.20+ 才有支持

  ✅ 主机网络命名空间关闭 Calico（避免冲突）
     - Calico eBPF 自己处理 hostnetwork Pod

  ✅ 禁用 kube-proxy（或设为 iptables 模式但允许 Calico 接管）

  ✅ Linux 发行版要求（编译 BPF 程序用）：
     - Ubuntu/Debian：libbpf-dev / linux-headers
     - RHEL/Fedora：kernel-devel / kernel-headers / elfutils-libelf-devel / clang
     - 通常 Calico 镜像里都有，但节点上需要编译头文件

  ⚠️ 重要：CPU 必须支持 BPF
     - 几乎所有 2015 年后的 x86_64 / arm64 都支持
     - 检查：grep -E 'flags.*\b(ebpf|bpf)\b' /proc/cpuinfo
```

### 4.2 安装方式（Helm / Operator）

```bash
# Helm 安装示例
helm repo add projectcalico https://docs.tigera.io/calico/charts
helm install calico projectcalico/tigera-operator \
  --set installation.calicoNetwork.bpf.enabled=true \
  --set installation.calicoNetwork.bpf.hostNetworkedPodsWithoutTLSAuth.enabled=true \
  --set installation.kubeProxyReplacement=true
```

```yaml
# Operator 安装（Installation CR）
apiVersion: operator.tigera.io/v1
kind: Installation
metadata:
  name: default
spec:
  calicoNetwork:
    # 关键三行
    linuxDataplane: BPF
    bpfEnabled: true
    kubeProxyReplacement: true                # eBPF 替代 kube-proxy
    ipPools:
      - blockSize: 26
        cidr: 10.244.0.0/16
        encapsulation: VXLAN                  # eBPF + VXLAN 是推荐组合
        natOutgoing: Enabled
        nodeSelector: all()
```

```yaml
# 关键说明：
# 1. linuxDataplane: BPF       → 切换数据面（默认 Iptables）
# 2. bpfEnabled: true          → 启用 BPF 编程（v3.13+ 由 linuxDataplane 控制，但仍可显式打开）
# 3. kubeProxyReplacement: true→ Calico eBPF 接管 Service 转发
```

### 4.3 从默认数据面迁移到 eBPF

```bash
# 步骤
# 1. 确认内核版本（必须）
uname -r

# 2. 检查 BPF 支持
grep -E 'flags.*\b(ebpf|bpf)\b' /proc/cpuinfo | head -1

# 3. 关 kube-proxy（或保留但不工作）
kubectl -n kube-system delete daemonset kube-proxy
# 或保留 kube-proxy，但 Calico eBPF 会绕过它

# 4. 修改 Installation CR，linuxDataplane: BPF

# 5. 观察 rollout
kubectl -n calico-system rollout status ds/calico-node

# 6. 验证 eBPF 跑起来（见 8.1）
calicoctl node status
```

---

## 五、eBPF 模式下的 Calico 配置详解

### 5.1 FelixConfiguration（核心调参）

```yaml
apiVersion: projectcalico.org/v3
kind: FelixConfiguration
metadata:
  name: default
spec:
  # ---- 必选 ----
  bpfEnabled: true
  linuxDataplane: BPF

  # ---- Service 转发相关 ----
  kubeProxyReplacement: true                # 是否替代 kube-proxy
  bpfKubeProxyIptablesCleanup: true         # 自动清理 kube-proxy 的 iptables 残留

  # ---- 主机端口相关 ----
  bpfHostNetworkedNAT: true                 # hostNetwork Pod 的 NAT 行为
  bpfPolicyConnectTime: 5000                # 首次策略判定超时（ms）

  # ---- 连接跟踪 ----
  bpfConntrackCleanupMode: Auto             # Auto / Userspace / Disabled
  bpfConntrackTTL: 600000                   # 连接跟踪表项寿命（ms）

  # ---- 策略相关 ----
  bpfPolicyDebugEnabled: false              # 调试日志（仅测试用）
  bpfMapSizePolicy: 65535                   # 策略 map 大小

  # ---- 路由 / MTU ----
  mtu: 1450                                 # VXLAN 模式下需要减小 MTU（IP 头 50 字节开销）

  # ---- Service / LoadBalancer ----
  serviceIPADSExcluded: 1.1.1.1,2.2.2.2     # 排除某 IP 不参与 Service 转发
  serviceExternalIPs: []                    # 显式指定哪些 Service externalIPs 允许
```

### 5.2 关键开关详解

```text
bpfEnabled
  是否启用 eBPF 程序（true / false）
  等价于 linuxDataplane: BPF

kubeProxyReplacement
  true   → Calico 完全替代 kube-proxy（推荐）
  false  → kube-proxy 仍工作，Calico eBPF 负责 Pod 间转发
  Disabled（v3.26+） → 明确关闭替代

bpfKubeProxyIptablesCleanup
  true → 自动清理 kube-proxy 下发的 iptables 规则（推荐）
  → 避免双重 NAT 路径

bpfHostNetworkedNAT
  HostNetwork Pod 的 NAT 行为：
    true → Calico 帮你做 SNAT（推荐）
    false → HostNetwork Pod 出网会丢包或 IP 不对

bpfConntrackCleanupMode
  Auto     → Calico 自动清连接（默认）
  Userspace→ 用户态工具清（更精细但要配 CronJob）
  Disabled → 不清，连接多时 map 会撑爆
```

### 5.3 XDP 配置

```yaml
spec:
  bpfEnabled: true
  bpfDisableXDP: false                      # false = 启用 XDP（默认）
  # XDP 模式（Calico 自动选最佳）
  # - mlx5/i40e/virtio_net 驱动 → Native XDP
  # - 其他驱动               → Generic XDP
```

```bash
# 查节点用的是哪种 XDP
ip link show eth0
# 看 driver: ...

# 查 XDP 程序是否挂载
ip link show eth0 | grep xdp
# 输出示例：xdp bpf_calico  或  xdpgeneric bpf_calico
```

---

## 六、性能优化点

### 6.1 调优清单（按收益排序）

```text
高收益（一做就有明显提升）：
  ✅ kubeProxyReplacement: true
  ✅ bpfEnabled: true
  ✅ bpfKubeProxyIptablesCleanup: true
  ✅ MTU 调到合适（VXLAN 1450 / IPIP 1480 / 直连 1500）

中收益（Service 多 / 节点多时有效）：
  ✅ 调大 conntrack TTL（默认 10 min，压力大改 30 min）
  ✅ 调大 conntrack map size（默认 512K，按 Service 数预估）
  ✅ 关闭 bpfPolicyDebugEnabled（生产环境）

低收益（边缘优化）：
  ✅ Native XDP（网卡驱动支持时）
  ✅ CPU 绑核（Calico 自动绑到 0 号 CPU）
  ✅ NUMA 亲和（多 NUMA 节点时）
```

### 6.2 性能对比基准

```text
典型性能提升（vs iptables 数据面）：

  Service 转发延迟：-30% 到 -50%
  Service 转发吞吐：+30% 到 +100%
  Service 规则更新延迟：-90%（eBPF map 是 O(1)，iptables 是全量重建）
  iptables 规则数：从几万条降到 0
  conntrack 表大小：减少 60%（eBPF 自管，更紧凑）

实测参考：
  10k Services + 5k Pods 集群
  - iptables 模式：每节点 ~80k 条规则，Service 新增延迟 30s+
  - eBPF 模式：每节点 0 条 iptables 规则，Service 新增 < 1s
```

### 6.3 内核参数调优（节点 sysctl）

```bash
# /etc/sysctl.d/99-calico.conf

# BPF map 大小（建议跟 Service 数对得上）
kernel.bpf_stats_enabled = 1

# conntrack 表（Calico 自管，但仍建议开）
net.netfilter.nf_conntrack_max = 1048576

# 网卡多队列（XDP 性能关键）
net.core.netdev_max_backlog = 30000
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216

# 中断亲和（避免所有包打到 CPU 0）
net.core.rps_sock_flow_entries = 32768
```

### 6.4 MTU 计算（不同封装方式）

```text
以太网默认 MTU = 1500
各种封装的开销：

  IPIP  隧道：+20 字节 → MTU 1480
  VXLAN 隧道：+50 字节 → MTU 1450
  无封装（直连 BGP）：MTU 1500

Calico FelixConfiguration 里要同步设置：
  encapsulation: VXLAN   →  mtu: 1450
  encapsulation: IPIP     →  mtu: 1480
  encapsulation: None     →  mtu: 1500

⚠️ MTU 算错 → 大包丢、ping 大包失败、TCP 重传
```

---

## 七、eBPF 模式的限制

### 7.1 不能用的特性

```text
❌ kube-proxy 的 IPVS 模式（Calico eBPF 替代，不是共存）
❌ 内核 < 4.19 的旧 OS（CentOS 7 / RHEL 7）
❌ Windows 节点（eBPF 仅 Linux）
❌ 部分网络策略高级特性：
   - ICMP 策略（v3.20+ 部分支持）
   - 主机名匹配 policy 中 hostname selector
❌ IPVS 负载均衡算法（Calico 自带算法不同）
❌ 一些 iptables 扩展模块
```

### 7.2 已知边缘问题

```text
⚠️ 与 Cilium 共存：不能，两个都用 eBPF 会冲突
⚠️ HostNetwork Pod + 复杂 NAT：需要 bpfHostNetworkedNAT 调参
⚠️ CalicoNetworkPolicy 的某些高级 selector：要看 v3.x release notes
⚠️ 部分 Linux 发行版的 custom kernel：编译 BPF 程序可能失败
⚠️ 公有云上的特殊网络增强（VPC 流量镜像等）：可能不兼容
```

### 7.3 不能随便关 kube-proxy

```text
如果 Calico eBPF 已经启用：

  ✅ 可以：保留 kube-proxy DaemonSet，但 Calico 会绕过它
  ❌ 不要：手动删 Service 时改 kube-proxy 留的 iptables 规则
  ❌ 不要：在 kube-proxy 仍运行时把 Calico 切回 iptables 数据面
     → 会有冲突的 NAT 规则
```

---

## 八、验证 / 排查

### 8.1 查看 eBPF 状态

```bash
# 1. 看 Calico 数据面类型
calicoctl node status
# 输出：
#   calico-node container is running
#   ...
#   BPF Maps:   v1.0
#   BPF Progs:  v1.0
#   Linux dataplane: BPF
#   ...

# 2. 看节点上 BPF 程序
calicoctl node bpf
# 或
bpftool prog list | grep calico

# 3. 看 BPF maps（数据存在哪）
bpftool map list | grep calico

# 4. 看 Service 在 eBPF map 里怎么映射
calicoctl node bpf service show

# 5. 看 XDP 是否挂上
ip link show eth0 | grep xdp
# xdp bpf_calico id 1234

# 6. 看 conntrack
cat /proc/net/ip_conntrack | head    # 内核 conntrack
calicoctl node bpf conntrack show    # Calico 自管 conntrack
```

### 8.2 性能指标监控

```text
关键指标（从 node-exporter / Prometheus 拿）：

  节点级：
    - node_bpf_progs_total：节点上 BPF 程序数（持续增长要警惕）
    - node_bpf_maps_total：BPF map 数
    - node_bpf_jit_limit_hits：JIT 编译限制命中（>0 要调）
    - node_softnet_dropped_packets：软中断丢包（>0 调 RPS）

  Calico 内置指标（端口 9091）：
    - felix_bpf_maps
    - felix_bpf_progs
    - felix_bpf_policy_accepted / denied
    - felix_bpf_conntrack_resets
    - felix_bpf_kube_proxy_iptables_cleanup_status
```

### 8.3 常见问题

#### 8.3.1 eBPF 启用后 Pod 起不来

```text
排查：
  1. 看 Calico Pod 日志：
     kubectl -n calico-system logs ds/calico-node | grep -i "bpf\|dataplane"
  2. 检查内核版本：uname -r ≥ 4.19？
  3. 检查 BPF 文件系统：
     mount | grep bpf
     → 应有：bpffs on /sys/fs/bpf type bpf
  4. 检查 kube-proxy 是否关干净：
     iptables -t nat -L | wc -l
     → Calico 模式下应该几乎为 0
```

#### 8.3.2 Service 访问不通

```text
排查：
  1. 看 eBPF map 里有没有这个 Service：
     calicoctl node bpf service show | grep <svc-cluster-ip>
  2. 看 conntrack：
     calicoctl node bpf conntrack show | grep <pod-ip>
  3. 看策略：
     calicoctl node bpf policy show
  4. 在节点抓包（XDP 抓不到，要在 TC 上抓）：
     tcpdump -i eth0 -nn port <svc-port>
```

#### 8.3.3 conntrack 表被打爆

```text
症状：
  - 部分新连接被丢（看到 felix_bpf_conntrack_resets 增长）
  - 日志里有 "Failed to allocate conntrack entry"

解决：
  1. 调大 map 大小：
     bpfMapSizeConntrack: 524288    # 默认 512K，调到 1M
  2. 调小 TTL：
     bpfConntrackTTL: 300000        # 默认 10 min → 5 min
  3. 检查是否有连接泄漏（长连接没正常关闭）
```

#### 8.3.4 性能反而下降

```text
可能原因：
  ① XDP 模式不匹配
     → Generic XDP 在某些驱动上比 iptables 还慢
     → 检查网卡驱动是否支持 Native XDP
     → 临时关 XDP 测：bpfDisableXDP: true
  ② MTU 不对（分片开销）
     → 大包被分片，性能下降明显
  ③ CPU 单核打满（XDP 默认绑 CPU 0）
     → 启用 RPS / RFS 分流
```

---

## 九、监控指标清单

```yaml
# ServiceMonitor for Calico eBPF metrics
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: calico-bpf
  namespace: calico-system
  labels:
    app: calico-node
spec:
  selector:
    matchLabels:
      app: calico-node
  endpoints:
  - port: metrics
    interval: 30s
    path: /metrics
```

```promql
# 关键 PromQL

# Calico eBPF 程序状态
felix_bpf_progs

# eBPF map 大小 / 使用量
felix_bpf_maps
felix_bpf_map_bytes
  / felix_bpf_map_max_bytes

# 策略评估性能
rate(felix_bpf_policy_accepted_total[5m])
rate(felix_bpf_policy_denied_total[5m])

# conntrack 状态
felix_bpf_conntrack_resets_total
felix_bpf_conntrack_cleaned_total

# kube-proxy 清理状态（应该一直为完成）
felix_bpf_kube_proxy_iptables_cleanup_status == 1
```

---

## 十、生产部署清单

```text
部署前：
  ☐ 集群所有节点内核 ≥ 4.19（推荐 5.10 LTS）
  ☐ 所有节点 BPF 支持确认（grep bpf /proc/cpuinfo）
  ☐ 节点时间同步（chrony）
  ☐ BPF 文件系统挂载（calico-node 自动处理）
  ☐ 备份当前 iptables 规则（出问题能回滚）

部署中：
  ☐ 先在 staging / 测试集群跑一遍
  ☐ 灰度节点切换（label + nodeSelector）
  ☐ 监控关键指标 24h 无异常
  ☐ Service / NetworkPolicy 跑回归测试

部署后：
  ☐ 验证 iptables 规则数降为 0（calico node 节点上）
  ☐ 验证 XDP 挂载成功（ip link show）
  ☐ 验证 conntrack 工作（calicoctl node bpf conntrack show）
  ☐ 性能基线测试（iperf3 / wrk）

回滚准备：
  ☐ 保留原 Installation CR 配置（IPIP / iptables 数据面）
  ☐ 准备回滚 yaml（linuxDataplane: Iptables）
  ☐ 知道怎么临时关 eBPF（calicoctl node bpf disable）
```

---

## 十一、eBPF vs iptables 数据面选型

| 维度 | iptables 数据面 | eBPF 数据面 |
| --- | --- | --- |
| 内核要求 | 任意 | ≥ 4.19（推荐 5.4+） |
| 性能（Service 多） | 差（O(n)） | 好（O(1)） |
| Service 规则更新 | 慢（iptables 重生成） | 快（map 更新） |
| 网络策略性能 | 一般 | 好 |
| 调试难度 | 中（iptables-legacy） | 难（要懂 eBPF 工具链） |
| 兼容性 | 最好 | 部分高级特性不支持 |
| kube-proxy | 需要 | 可省 |
| 运维成本 | 低 | 中 |
| 适用集群规模 | 任意 | 推荐 ≥ 100 节点 |
| 学习曲线 | 短 | 长 |

**选型建议**：

```text
集群 < 50 节点，Service < 100：
  → iptables 数据面（默认）
  → 简单稳定，没必要折腾

集群 50-200 节点，Service 100-1000：
  → 都可以，看团队对 eBPF 熟悉程度
  → eBPF 性能更好，但出问题排查更复杂

集群 > 200 节点 或 Service > 1000：
  → eBPF 数据面（强烈推荐）
  → iptables 数据面下，规则数 / 重建延迟会成为瓶颈

有特殊需求（IPVS 负载均衡算法、复杂 iptables 规则）：
  → iptables 数据面
```

---

## 十二、一句话总结

> **Calico eBPF 数据面 = Calico 在内核里跑的"超级 kube-proxy + 智能 iptables 替代品"**，
> 内核 ≥ 4.19 就能开，Service 多、集群大时性能提升 30%+；
> 但要内核版本、BPF 工具链、调试能力都到位，**别盲目开**。

---

## 十三、参考

- [Calico 官方文档 - eBPF dataplane](https://docs.tigera.io/calico/latest/operations/ebpf/)
- [Calico 官方文档 - Configure eBPF](https://docs.tigera.io/calico/latest/networking/configuring/bpf)
- [Calico 官方文档 - BPF datapath mode](https://docs.tigera.io/calico/latest/reference/felix/configuration#bpf-enabled)
- [Cilium eBPF 文档](https://docs.cilium.io/en/latest/bpf/)（理解 eBPF 原理的经典）
- [BPF Performance Tools (book)](https://www.brendangregg.com/bpf-performance-tools-book.html)
