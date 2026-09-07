# Calico Block Size 详解

> Calico 给每个 K8s 节点从 IP Pool 里**预分配一段连续 IP**——这段连续 IP 的大小就是 **Block Size**。
> 看完这篇你会知道：
> 1. blocksize 是怎么从 CIDR 里**切分**出来的
> 2. 为什么节点上的 `route -n` 会多出一条 **/26（或 /27、/28）** 的"奇怪路由"
> 3. blocksize 选大还是选小，怎么权衡

---

## 一、什么是 Block Size

### 1.1 一句话定义

```text
Block Size = Calico 给一个节点从 IP Pool 里**一次性预分配**的连续 IP 段大小

默认情况下，Calico 会按 blocksize 把整个 IP Pool 切成 N 块：
  - 每块 = 一个节点能用的 IP 范围（写死在该节点上）
  - 节点再把这块里的 IP 拆给本节点的 Pod

例：IP Pool = 10.244.0.0/16，blocksize = /26
  → /16 切成 1024 个 /26
  → 每个节点分到 1 个 /26（64 个 IP）
  → 节点从这 64 个 IP 里再切给 Pod
```

### 1.2 为什么需要"预分配块"而不是"按需分配"

```text
按需分配（早期版本做法）：
  - 每个 Pod 起一个，从 Pool 拿一个 IP
  - 每个 IP 都要广播给所有节点（BGP 一条路由）
  - 1000 个 Pod = 1000 条 BGP 路由，路由表爆炸

块预分配（blocksize）：
  - 每个节点拿一段（/26 = 64 个 IP）
  - 整个集群路由表只有"每节点 1 条"，路由条目 = 节点数
  - 节点内 Pod 增删只在本节点 + 局部刷新，不动 BGP
  → 控制平面和数据平面都更省
```

---

## 二、blocksize 与 CIDR 子网划分

### 2.1 CIDR 子网划分基础（先把数算清楚）

```text
CIDR 表示法：IP/前缀长度
  /16 = 前 16 位固定，剩下 16 位可分配 = 2^16 = 65536 个 IP
  /20 = 65536 / 16 = 4096 个 IP
  /24 = 256 个 IP
  /26 = 256 / 4 = 64 个 IP      ← Calico 默认 blocksize
  /27 = 32 个 IP
  /28 = 16 个 IP
  /29 = 8 个 IP

切分公式：
  Pool 前缀 a，blocksize 前缀 b（b > a）
  → 切分数 = 2^(b-a)
  → 每块 IP 数 = 2^(32-b)

例：Pool = /16，blocksize = /26
  切分数 = 2^(26-16) = 2^10 = 1024 块
  每块 IP = 2^(32-26) = 2^6 = 64 个
  1024 块 × 64 IP = 65536 个 = /16 总 IP 数 ✓
```

### 2.2 Calico 默认值与可选值

```yaml
apiVersion: projectcalico.org/v3
kind: IPPool
metadata:
  name: default-pool
spec:
  cidr: 10.244.0.0/16
  blockSize: 26                            # ← Calico 默认就是 26
  ipipMode: Always
  vxlanMode: Never
```

```text
Calico 限制（v3.20+）：
  blockSize 范围 = 20 ~ 32（即 /20 ~ /32）

  /20 = 4096 IP / 节点   块数 = 2^(20-a)
  /24 = 256 IP / 节点
  /26 = 64 IP / 节点     ← 默认
  /28 = 16 IP / 节点
  /32 = 1 IP / 节点      ← 几乎不可用，等于按 Pod 分配
```

### 2.3 实际切分示例

```text
IP Pool: 10.244.0.0/16, blockSize: 26

切分结果（1024 块，每块 /26）：

  节点 1    → 10.244.0.0/26    (10.244.0.0   - 10.244.0.63)
  节点 2    → 10.244.0.64/26   (10.244.0.64  - 10.244.0.127)
  节点 3    → 10.244.0.128/26  (10.244.0.128 - 10.244.0.191)
  ...
  节点 1024 → 10.244.255.192/26 (10.244.255.192 - 10.244.255.255)

每个节点的可用 IP 数 = 64，但实际可用 = 64 - 1 (网络地址) - 1 (广播地址) = 62 个 Pod
```

```text
如果改成 blockSize: 24：

  IP Pool: 10.244.0.0/16, blockSize: 24

  切分结果（256 块，每块 /24）：

  节点 1    → 10.244.0.0/24    (256 IP = 254 个 Pod)
  节点 2    → 10.244.1.0/24
  ...
  节点 256  → 10.244.255.0/24
```

### 2.4 子网数对不上节点数怎么办

```text
常见问题：
  /16 + /26 → 1024 块
  但只有 10 个节点

答：Calico 按需分配，用多少切多少。
  - 10 个节点用 10 个 /26
  - 剩下 1014 个 /26 留着备用
  - 新节点加入时自动分配下一个空闲块

如果子网数 < 节点数：
  /20 + /20 → 只有 1 块，但有 2 个节点 → 报错 IP 耗尽
```

---

## 三、blocksize 在 `route -n` 中的体现

### 3.1 节点上的路由表长什么样

```bash
# 在 K8s 节点上执行
route -n
```

```text
Kernel IP routing table
Destination     Gateway         Genmask         Flags Metric Ref    Use Iface
0.0.0.0         172.20.0.1      0.0.0.0         UG    0      0        0 eth0
10.244.0.0      0.0.0.0         255.255.255.192 U     0      0        0 *    ← 本节点的 /26 块
10.244.0.64     0.0.0.0         255.255.255.192 U     0      0        0 *    ← 本机 Pod 直连路由
10.244.0.128    172.20.0.12     255.255.255.192 UG    0      0        0 eth0  ← 节点2 的块，下一跳 = 节点2 IP
10.244.0.192    172.20.0.13     255.255.255.192 UG    0      0        0 eth0  ← 节点3 的块，下一跳 = 节点3 IP
...
172.20.0.0      0.0.0.0         255.255.255.0   U     0      0        0 eth0
```

### 3.2 这些路由怎么读

```text
每行 = 一条路由

重点关注 Destination 和 Gateway 两列：

  Destination = 目的网段（这里是另一个节点的 blocksize 网段）
  Gateway     = 下一跳（对端节点 IP，或者 0.0.0.0 = 直连）
  Genmask     = 子网掩码 = blocksize 大小（这里 255.255.255.192 = /26）
  Flags UG    = U(Up) G(Gateway) = 这条路由要走网关
  Flags U     = U(Up) = 直连路由
```

**关键发现**：

```text
1. 每条路由的 Genmask 都是 255.255.255.192（/26）
   → 这就是 blockSize=26 在路由表里的"物理存在"

2. 路由条目数 ≈ 节点数 + 1（自己那块是直连）
   100 节点 → ~101 条 Pod 段路由

3. 目标地址是"节点的整块"，不是单个 Pod
   → BGP 只通告 /26，不通告单个 Pod IP
```

### 3.3 完整场景示例（3 节点集群）

```text
集群配置：
  IP Pool: 10.244.0.0/16
  blockSize: 26
  节点：node1 (172.20.0.11) / node2 (172.20.0.12) / node3 (172.20.0.13)

Calico 自动分配：
  node1 → 10.244.0.0/26
  node2 → 10.244.0.64/26
  node3 → 10.244.0.128/26

BGP 通告：
  node1 通告: "我能到 10.244.0.0/26"
  node2 通告: "我能到 10.244.0.64/26"
  node3 通告: "我能到 10.244.0.128/26"
```

**node1 上的 `route -n`**：

```text
Kernel IP routing table
Destination     Gateway         Genmask         Flags Metric Ref    Use Iface
0.0.0.0         172.20.0.1      0.0.0.0         UG    0      0        0 eth0
10.244.0.0      0.0.0.0         255.255.255.192 U     0      0        0 *      ← node1 自己的块
10.244.0.64     172.20.0.12     255.255.255.192 UG    0      0        0 eth0   ← node2 的块 → 走 node2
10.244.0.128    172.20.0.13     255.255.255.192 UG    0      0        0 eth0   ← node3 的块 → 走 node3
```

**对比 Pod 路由（Calico 内部维护）**：

```bash
# 在 node1 上
ip route show table all | grep cali
```

```text
# Pod 级别路由（用于 Pod 内的细粒度转发）
10.244.0.10 dev caliabcdef  scope link   ← Pod A 的 IP 走 cali 接口
10.244.0.20 dev cali123456  scope link   ← Pod B 的 IP 走另一个 cali 接口
```

```text
总结一下 node1 上的路由分层：

  ① 默认路由 0.0.0.0/0 → eth0 出网
  ② 自己节点块 10.244.0.0/26 → 直连
  ③ 其他节点块 10.244.0.64/26 等 → 走 BGP 学到的下一跳（其他节点 IP）
  ④ Pod 级别路由 → 走 cali* 虚拟接口

转发顺序：路由最长前缀匹配（LPM）
  10.244.0.10 优先匹配 /32（Pod 级）→ cali 接口
  其他 10.244.0.x → 匹配 /26 → 走对端节点
```

### 3.4 看 blocksize 的几个命令

```bash
# 1. 节点路由表（直接看 Genmask 反推 blocksize）
route -n

# 2. 看节点分配的块
calicoctl ipam show
# 或
calicoctl ipam show --show-blocks

# 3. 看某个 Pod 的 IP 在哪个节点块里
calicoctl ipam get <pod-ip>

# 4. 看 IP Pool 配置（blocksize 在 spec.blockSize）
calicoctl get ippool -o yaml

# 5. 看 BGP 路由表里到底通告了哪些块（bird 控制台）
calicoctl node bird
> show route
> show route where net ~ "10.244"
```

---

## 四、blocksize 怎么配置

### 4.1 创建 Pool 时指定

```yaml
apiVersion: projectcalico.org/v3
kind: IPPool
metadata:
  name: pool-big-block
spec:
  cidr: 10.244.0.0/16
  blockSize: 24                    # ← 每节点 256 个 IP
  ipipMode: Always
  vxlanMode: Never
```

### 4.2 已有 Pool 修改 blockSize（⚠️ 危险操作）

```bash
# Calico 不允许直接修改已有 Pool 的 blockSize
# 必须：建新 Pool → 迁移 → 删旧 Pool

# 步骤
# 1. 建新 Pool（blockSize 改成新值）
cat <<EOF | calicoctl apply -f -
apiVersion: projectcalico.org/v3
kind: IPPool
metadata:
  name: pool-new
spec:
  cidr: 10.245.0.0/16
  blockSize: 24
  ipipMode: Always
  vxlanMode: Never
EOF

# 2. 重启 Pod，让 Pod 分配到新 Pool
kubectl rollout restart deploy --all
# 或
kubectl delete pod --all -n <namespace>

# 3. 旧 Pool 上的 Pod 都迁完后，删旧 Pool
calicoctl delete ippool pool-old
```

### 4.3 改 blockSize 的影响

```text
旧 blockSize=26 (/16 → 1024 块)：
  10.244.0.0/26       node1
  10.244.0.64/26      node2
  ...

新 blockSize=24 (/16 → 256 块)：
  10.244.0.0/24       node1
  10.244.1.0/24       node2
  ...
  ↑ 块大小变了，原来的块边界不兼容
  ↑ 老的 Pod IP 不会被重分配，但块边界变了
```

⚠️ **结论**：生产环境**一开始就选好**，别改。

---

## 五、blocksize 大小怎么选

### 5.1 权衡表

| blocksize | 每节点 IP 数 | 块数(/16) | 优点 | 缺点 |
| --- | --- | --- | --- | --- |
| **/20** | 4096 | 1 | 单块超大，单节点无数 Pod 也用不完 | 一个节点独占 4096 IP，集群最大只 16 节点 |
| **/24** | 256 | 256 | 每节点 254 个 Pod | 节点数 > 256 不够分（/16 Pool 下） |
| **/26**（默认） | 64 | 1024 | 平衡：1000 节点集群 + 每节点 62 Pod | 节点单 Pod 跑满（超过 62）就 IP 耗尽 |
| **/27** | 32 | 2048 | 节点数可以更多 | 每节点最多 30 Pod |
| **/28** | 16 | 4096 | 节点数更多 | 每节点最多 14 Pod |
| **/32** | 1 | 65536 | 路由数 = Pod 数 | 等于没优化，跟早期版本一样 |

### 5.2 经验公式

```text
选 blockSize 的步骤：

1. 预估集群最大节点数 N
2. 预估每节点最大 Pod 数 P（实际很少有超过 100 个）
3. 选 Pool 大小
   Pool 大小 ≥ N × P × 1.5（预留 50% buffer）
4. 算 blocksize
   2^(32-blockSize) ≥ P
   blockSize ≤ 32 - log2(P)

   例：每节点最大 50 个 Pod
     2^(32-blockSize) ≥ 50
     32-blockSize ≥ log2(50) ≈ 5.64
     blockSize ≤ 26.36
     → 选 /26（64 IP，足够）

   例：每节点最大 200 个 Pod（大集群 DaemonSet 多）
     2^(32-blockSize) ≥ 200
     blockSize ≤ 32 - 7.64 = 24.36
     → 选 /24（256 IP）

5. 算块数
   Pool 块数 = 2^(blockSize - pool前缀)
   要 ≥ N，否则 IP Pool 不够分
```

### 5.3 常见场景推荐

```text
小集群（≤ 50 节点，每节点 Pod 数 < 50）：
  → blockSize: 26（默认即可）
  → IP Pool: 10.244.0.0/16 或 10.244.0.0/18

中集群（50–500 节点）：
  → blockSize: 26
  → IP Pool: 10.244.0.0/14（/14 = 262144 IP，足够 4000 节点 × 64 IP）

大集群（500–2000 节点，节点 Pod 多）：
  → blockSize: 24（每节点 256 IP）
  → IP Pool: 10.244.0.0/13（/13 = 524288 IP，足够 2048 节点 × 256 IP）

超大集群（5000+ 节点）：
  → 多 Pool 叠加 + 多 AS + Route Reflector
  → blockSize: 26 或 27，配合更细 Pool 划分
```

### 5.4 千万别这么选

```text
❌ /32（每节点 1 IP）：等于没优化，BGP 路由 = Pod 数
❌ /20（每节点 4096 IP）：/16 Pool 只能分 16 个节点
❌ Pool 大小 / 节点数 < 每节点 Pod 数：必然 IP 耗尽
```

---

## 六、blocksize 对集群容量的影响

### 6.1 三个限制因素

```text
限制 1：Pool 总 IP 数
  Pool /16 = 65536 IP
  集群总 Pod 数 ≤ Pool IP 数

限制 2：单节点 IP 数 = 块大小
  节点上 Pod 数 ≤ 块 IP 数 - 2（网络地址 + 广播）

限制 3：节点数 ≤ Pool 切出的块数
  /16 + /26 → 1024 块 → 最多 1024 个节点
```

### 6.2 容量计算示例

```text
例：10.244.0.0/16 + blockSize 26

  Pool 总 IP：65536
  单节点 Pod 数：62
  集群最大节点数：1024
  集群最大 Pod 数：1024 × 62 = 63488（基本 = Pool IP 数）

例：10.244.0.0/14 + blockSize 24

  Pool 总 IP：262144
  单节点 Pod 数：254
  集群最大节点数：256
  集群最大 Pod 数：256 × 254 = 65024

例：10.244.0.0/13 + blockSize 26

  Pool 总 IP：524288
  单节点 Pod 数：62
  集群最大节点数：8192
  集群最大 Pod 数：8192 × 62 = 507904
```

---

## 七、blocksize 满了怎么办

### 7.1 现象

```text
- Pod 起不来，报错：
  "Failed to allocate IP: No IP addresses available in pool"
- 节点上分配不到新 IP
- calicoctl ipam show 看到 block 已经 100% 用完
```

### 7.2 排查

```bash
# 看块使用率
calicoctl ipam show
# Block 10.244.0.128/26:
#   Used: 64/64   ← 满了
#   Available: 0

# 看节点上 Pod 数
kubectl describe node <node-name> | grep "Pod Limit\|pods"
```

### 7.3 应急方案

```text
方案 1（最快）：扩容 IP Pool
  - 加一个新的 IP Pool（不同 CIDR，比如 10.245.0.0/16）
  - Calico 自动从新 Pool 给没块的节点分配
  - 已分配旧块的节点继续用旧块（不重分）

方案 2：缩 Pod 数
  - 找节点上不用的 Pod 清理
  - 块里 IP 释放需要 Pod 删除（不是 restart）

方案 3：扩容单块（改 blockSize）
  - 见 4.2 改 blockSize 流程
  - 影响大，先在测试环境验证
```

---

## 八、blocksize 调整注意事项

### 8.1 什么时候该改

```text
1. 集群规模预测明显变大
   - 现在 50 节点 × 20 Pod，要扩到 500 节点 × 100 Pod
   - 旧 blockSize 26 不够 → 改 24

2. 路由表有压力
   - 节点数 1000+ 路由条数会到 1000+
   - 检查交换机 FIB 表容量

3. IP 浪费严重
   - 节点平均 5 个 Pod，块大小 64，浪费 90%
   - 改小一点能省 IP
```

### 8.2 什么时候别改

```text
1. 集群已经在生产运行
   - 改 blockSize 等于迁移所有 Pod IP
   - 影响所有 Service / Ingress / DNS 解析

2. 现有块数已用满 50%+
   - 迁移一半的块是高风险操作

3. 节点有 StatefulSet / DaemonSet
   - 这些 Pod 通常固定 IP，迁移会断连接
```

### 8.3 安全修改流程

```text
Step 1：在测试集群试跑（同样的 IP Pool 大小、节点数）
Step 2：建新 Pool（小流量 namespace 灰度）
        kubectl label namespace gray-ns default-felix-bgp-enabled=true
        # 或用 namespace selector 隔离
Step 3：观察一周，确认无 IP 漂移 / 路由抖动
Step 4：全量切换
        - 旧 Pool 标记 disabled: true（不再分配新 IP）
        - Pod 滚动重启会拿到新 Pool 的 IP
        - 监控滚动期间的丢包 / 重连
Step 5：清理旧 Pool（确保没有 Pod 在用）
        calicoctl get ippool -o wide
        calicoctl delete ippool old-pool
```

---

## 九、常见问题

### 9.1 route -n 里看到 /26 的奇怪路由，正常吗？

```text
正常。这就是 Calico 给本节点预分配的 blocksize 网段。
Genmask = 255.255.255.192 = /26 = 64 IP
Gateway = 0.0.0.0 表示直连（这块就在本节点上）
Flags = U（Up）
```

### 9.2 为什么节点上不能动这条路由？

```text
这是 Calico 自动管理的，删掉 / 改了会导致 Pod 网络不通。
如果你想看 Pod 级别的路由，看：
  ip route show table all
  或 ip rule list（Calico 用策略路由）
```

### 9.3 两个节点分到同一块会冲突吗？

```text
不会。Calico IPAM 用 bitwise allocation：
  - 每个 Pool 切成 2^(blockSize - pool_prefix) 个块
  - 用 bitmap 标记已分配
  - 新节点分配时查第一个未分配块

冲突排查：
  calicoctl ipam show
  # 确认没有两个节点都指向同一个块
```

### 9.4 blocksize 跟子网掩码啥关系？

```text
BlockSize = blocksize = 子网前缀长度
  - blockSize: 26 → 子网掩码 255.255.255.192 → /26 → 64 IP
  - blockSize: 24 → 子网掩码 255.255.255.0 → /24 → 256 IP

一个意思，Calico 用 blockSize 字段名（BIRD 配置习惯），
K8s / 网络工程师更习惯叫"子网掩码 / /xx 前缀"
```

---

## 十、一句话总结

> **Block Size = 每个节点从 IP Pool 预分配的子网大小（/xx 前缀）**，
> 默认 /26（64 IP）；它直接决定了 `route -n` 里 Genmask 列的样子，
> 决定了集群能跑多少节点、每节点最多几个 Pod——**建集群前就想好，别后期改**。

---

## 十一、参考

- [Calico 官方文档 - IP Pool blockSize](https://docs.tigera.io/calico/latest/reference/resources/ippool)
- [Calico 官方文档 - Configure IP pools](https://docs.tigera.io/calico/latest/networking/configuring/ipam)
- [Calico 官方文档 - IP address management](https://docs.tigera.io/calico/latest/networking/ipam)
