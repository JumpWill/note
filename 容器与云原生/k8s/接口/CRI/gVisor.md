## 概念

gVisor（项目名 runsc）是 Google 开源的 **用户态内核（sandbox kernel）**，用作容器 runtime，提供比 runc 强得多的隔离。

* 项目起源：Google 内部 Sentry 经验 → 2018 开源
* 设计：在用户态跑一个 **迷你 Linux 内核**（goos / goarch，Go 写），拦截容器所有 syscall 并在该用户态内核里处理
* **不依赖硬件虚拟化**，不像 kata-containers

## 架构

```
┌─────────────── Host kernel ─────────────────┐
│                                              │
│  ┌────── runsc (sandbox) ─────────────────┐  │
│  │  ┌─── Sentry (用户态内核, Go) ──────┐  │  │
│  │  │  - 处理 syscalls                  │  │  │
│  │  │  - 内存管理                       │  │  │
│  │  │  - TCP/IP 栈（netstack）           │  │  │
│  │  │  - 文件系统 (gofer / fuse)         │  │  │
│  │  └────────────────────────────────────┘  │  │
│  │       ▲                                   │  │
│  │       │ intercept                         │  │
│  │  ┌────┴─────────────────────────────┐    │  │
│  │  │  Container processes (app)        │    │  │
│  │  └──────────────────────────────────┘    │  │
│  └──────────────────────────────────────────┘  │
│                                              │
└──────────────────────────────────────────────┘
```

* **Sentry**：用户态内核，拦 syscall
* **Gofer**：文件系统代理（基于 9P / FUSE）
* **netstack**：用户态 TCP/IP（可选，host network 也行）

## 关键能力

* **强隔离**：syscall 全部走 Sentry，攻击面比 runc 小 ~80%
* **不需 KVM**：纯软件沙箱，云上不挑硬件
* **多平台**：Linux x86_64 / arm64
* **K8s 集成**：RuntimeClass
* **性能**：比 runc 慢 10–30%，CPU 多 10–20%（取决于 syscall 量）

## 部署

K8s RuntimeClass：

```yaml
apiVersion: node.k8s.io/v1
kind: RuntimeClass
metadata:
  name: gvisor
handler: runsc
```

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: sandboxed
spec:
  runtimeClassName: gvisor
  containers:
  - name: app
    image: myapp:latest
```

Node 装 runsc：

```bash
# containerd 配置
[plugins."io.containerd.grpc.v1.cri".containerd.runtimes.runsc]
  runtime_type = "io.containerd.runsc.v1"

# 或直接装 deb / rpm
```

## 优缺点

* ✅ **强隔离**：不需硬件虚拟化，宿主级安全
* ✅ **云友好**：AWS / GCP / Azure 都能跑
* ✅ 比 VM 方案（kata）启动快 ~10x，资源占用少
* ✅ 跟 runc 兼容，迁移成本低
* ❌ **性能开销**：syscall 多 ~30%，吞吐下降
* ❌ 不完全兼容所有 syscall（少数边缘 case 失败）
* ❌ 不支持某些高级特性（`ptrace`、`/proc/<pid>/mem`）
* ❌ 不适合高 IO / 高网络吞吐场景

## 适用场景

* **多租户 / untrusted 代码**（CI runner、serverless）
* SaaS 平台让用户跑代码（Cloud Run 类似场景）
* 防御容器逃逸（即使 runc 0day 也很难打到 host）
* 不方便用 VM（无 KVM 权限）的云环境

## 监控 / 排查

```bash
# 看用 runsc 的容器
crictl ps --runtime runsc

# 进容器
crictl exec <container-id> /bin/sh

# 看 runsc 内部（通过 Sentry pprof）
curl http://localhost:6060/debug/pprof/

# 看 syscall overhead
sudo perf top -e syscalls:sys_enter_*
```

## 一句话

**用户态内核沙箱，强隔离、轻量、云友好，代价是性能下降 10–30%**。