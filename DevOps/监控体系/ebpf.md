# eBPF 可观测性

基于 eBPF（Extended Berkeley Packet Filter）技术在内核层面对系统进行观测、安全、可视的工具集。是新一代云原生时代的"无侵入式"观测核心。

## 一、eBPF 原理概要

- 运行在内核沙箱程序（verifier 通过）
- 不需要修改应用代码
- 通过 kprobe / tracepoint / tc / uprobes 挂钩到内核 / 用户态
- JIT 编译为 native code，性能接近 native
- 限制：指令数 / 循环限制 / 大小限制

```text
   用户进程                          内核
                     ┌──────────────────────────────┐
   App  ───── syscall ───►  kprobe / tracepoint  ──►  eBPF 程序
                     │                              │
                     │             map             │
                     │  ┌─────────────────────────┐ │
                     │  │ events / metrics / tail │ │
                     │  └─────────────────────────┘ │
                     │                              │
                     └──────────────────────────────┘
                              │
                              ▼
                       Userspace exporter / agent
```

## 二、主流工具

### 1. Cilium Tetragon

- 由 Isovalent 主导（Cilium 团队）
- 实时 eBPF 安全 / 观测
- K8s Runtime 监控（含网络 / 文件 / 调用）
- Sidecar-free 注入
- 与 Hubble 协同网络观测

### 2. Hubble

- Cilium 提供的网络观测层
- Service Mesh-aware 流量监控
- 网络策略审计

### 3. Pixie

- New Relic 开源
- K8s 即时观测（不埋点）
- 通过 eBPF 拿到 Go / Python / Java / Node.js runtime 信息
- 内建 SQL like `px.Query()`
- 自动解析网络请求，无需 sidecar

### 4. Falco

- CNCF Incubating
- 安全运行时检测
- 检测异常 syscall / 容器逃逸 / 反弹 shell

### 5. Parca（持续剖析 eBPF）

- 持续剖析（continuous profiling）
- eBPF / 语言级 profiler

### 6. Pyroscope eBPF profiler

- Pyroscope 也支持 eBPF 持续剖析

### 7. Inspektor Gadget

- K8s 调试工具集合
- eBPF Gadgets 子项目
- 类似 kubectl gadget ...

### 8. bpftrace

- eBPF 脚本语言
- 单次临时调试
- `bpftrace -e 'kprobe:tcp_connect{ ... }'`

### 9. bcc / bcc-tools

- eBPF tracing tools
- 单行可启用的工具集

### 10. perf

- 内核层 profiling
- eBPF 之前主流工具
- 与 FlameGraph 配合

## 三、Cilium Tetragon 详解

### 1. 架构

```text
   ┌──────────────────────────────────┐
   │  Tetragon Agent (DaemonSet)      │
   │   - eBPF 程序加载到内核           │
   │   - 内核层事件生成                 │
   │   - 策略匹配                       │
   │   - 用户态 export                 │
   └─────────────┬────────────────────┘
                 ▼
   ┌──────────────────────────────────┐
   │  Exporters：                      │
   │   - Log / JSON                  │
   │   - Prometheus metrics          │
   │   - gRPC / Hubble                │
   │   - gRPC / Kube API Server    │
   └──────────────────────────────────┘
```

### 2. TracingPolicy

```yaml
apiVersion: cilium.io/v1alpha1
kind: TracingPolicy
metadata:
  name: detect-exec
spec:
  kprobes:
    - call: "security_bpf_prog"
      syscall: true
  tracepoints:
    - subsystem: "sched"
      event: "sched_process_exec"
      args:
        - index: 0
          type: "nop"
      selectors:
        - matchArgs:
            - index: 1
              operator: "Equal"
              values:
                - "/usr/bin/curl"
        - matchNamespaces:
            - operator: "In"
              values:
                - "default"
            - operator: "NotIn"
              values:
                - "kube-system"
          matchActions:
            - action: Sigkill
```

### 3. 检测类型

- `tracepoints`
- `kprobes`
- `uprobes`
- `kfunc`
- `usdt`
- `network` / `l7`
- `pid / pids`

### 4. 常见用法

- 监控所有 exec 子进程
- 拦截敏感文件访问（如 /etc/passwd）
- 检测容器逃逸（setuid / mount namespace）
- 实时禁止 syscall（Sigkill）

## 四、Hubble 详解

### 1. 角色

- 提供 L3/L4/L7 网络流观测
- 来自 Cilium 暴露的事件流

### 2. UI

```text
hubble ui
  Namespace / Pod / Service / L7 protocol
   - HTTP / gRPC metrics
   - 错误 / 重试
   - Network Policy 生效
```

### 3. RELAY 多集群

- Hubble Relay 跨集群汇聚事件

## 五、Pixie 详解

### 1. 架构

```text
K8s pod
   ├── px-k8s DaemonSet (per-node)
   │      └── eBPF 程序
   │      └── PxL scripts
   │      └── Local storage
   └── px-viz (中央 UI)
```

### 2. PxL

```pxl
df = DataFrame('http_events')
df = df[ df['http_resp_status'] > 200 ]
df.groupby('service').agg({'req_count': 'count'})
```

- 类似 SQL / Pandas
- 实时查询

### 3. 适用

- 不动代码的快速观测
- 网络、HTTP、gRPC、MySQL、SSL 等协议
- trace 自动注入 trace_id

### 4. New Relic 集成

- Pixie 现在归 New Relic
- 商业版：New Relic Pixie / NRDB

## 六、Falco 详解

### 1. 架构

```text
Falco Driver / eBPF probe
   │
   ▼
Falco Userspace
   │
   ├── Rules Engine
   │
   ▼
output → Log / File / Slack / Kafka / StatsD
```

### 2. 规则示例

```yaml
- rule: Detect outbound connection to internet
  desc: Outbound TCP connection
  condition: outbound and container
  output: ...
  priority: WARNING
```

### 3. 现代模式

- 使用 eBPF probe（v0.32+，替代内核模块）
- 性能更好，简化部署

## 七、应用场景

### 1. 性能瓶颈分析

```bash
perf record -g -F 99 ./app
perf script | ./stackcollapse-perf.pl | ./flamegraph.pl > flame.svg
```

或 eBPF 工具：

- `bpftrace -e 'kprobe:tcp_sendmsg { @[comm] = count(); }'`

### 2. 网络可观测

- Hubble 显示哪些 Service 调用了哪些 Service
- DDoS / Flood 检测
- DNS latency 统计

### 3. 安全

- Falco 检测敏感 syscall
- Tetragon 拦截 / 阻断容器逃逸
- 进程白名单 / 文件系统告警

### 4. 调用追踪

- Pixie 把 RPC / DB / 缓存栈与 K8s 元数据关联
- 不需 SDK

## 八、与其他可观测性集成

| 工具 | 与 Loki | 与 Prometheus | 与 Tempo / OTEL |
| ---- | ------ | ------------- | --------------- |
| Tetragon | logger | metrics | - |
| Hubble | - | metrics | - |
| Pixie | - | telemetry | OTLP 上报 |
| Falco | - | metrics via forwarder | - |
| Pyroscope | - | - | - |

## 九、K8s 部署

### Tetragon

DaemonSet：

```bash
helm install tetragon cilium/tetragon -n kube-system
```

### Hubble

Cilium 自带：

```bash
cilium hubble enable
cilium hubble port-forward
```

### Falco

```bash
helm repo add falcosecurity https://falcosecurity.github.io/charts
helm install falco falcosecurity/falco
```

### Pixie

```bash
helm repo add pixie https://pixie-operator-charts.storage.googleapis.com/
helm install pixie-operator pixie/pixie-operator
```

## 十、安全风险与对策

- eBPF 程序可能在 verifier 突破时崩溃内核
- 启用 lockdown mode
- 限制 CAP_SYS_ADMIN / BPF capability
- 单一受信工具运行（Falco / Tetragon）
- 升级内核至最新

## 十一、最佳实践

- **选择合适工具**：性能看 Pixie / Tetragon；安全用 Falco / Tetragon；持续剖析 Pyroscope
- **不要滥用**：每个 eBPF 程序都消耗资源
- **Sidecar-less 优先**：eBPF 优于 sidecar
- **策略即代码**：CRD / YAML 配置文件化
- **能力审计**：开启 lockdown / AppArmor

## 十二、未来趋势

- Tetragon Sigkill 实时阻断（kill 掉非法进程）
- 与服务网格协同（Hubble → Envoy）
- eBPF on Windows / macOS
- 用户态 eBPF 解释器
- eBPF 与 AI 协同：AIOps 异常检测
