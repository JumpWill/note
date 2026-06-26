## 概念

kata-containers 是 **VM 级隔离的容器 runtime**：每个 Pod 跑在一个轻量 KVM 虚机里。

* 项目起源：Intel Clear Containers + Hyper runV → 2017 合并为 kata
* 设计：在 **硬件虚拟化** 之上跑容器，把 VM 当容器用
* 现在由 OpenInfra Foundation 治理

## 架构

```
┌──────── Host kernel (Linux) ──────────┐
│                                        │
│  ┌─── QEMU / Cloud-hypervisor ────┐    │
│  │  ┌─── Guest kernel ─────────┐  │    │
│  │  │  ┌─── Container processes│  │    │
│  │  │  └─────────────────────────┘  │    │
│  │  └─────────────────────────────┘   │
│  │  virtio-net / virtio-blk          │
│  └──────────────────────────────────┘    │
│      ▲                                  │
│      │ vsock / virtio                   │
│  kata-runtime / kata-shim              │
│                                        │
└────────────────────────────────────────┘
```

* **VM 跑容器**：每个 Pod 一个 micro-VM
* **agent**：在 Guest VM 里跑，监控容器进程
* **runtime / shim**：host 端，遵守 CRI
* **hypervisor**：QEMU（默认）/ Cloud-hypervisor（更轻）/ Dragonball（AWS Firecracker 派生）

## 关键能力

* **VM 隔离**：跟 host 内核完全隔离，**最强**
* **多 hypervisor**：QEMU / Cloud-hypervisor / Dragonball / Firecracker
* **机密计算**：配合 Intel TDX / AMD SEV / ARM CCA
* **virtio**：标准 virtio-net / blk，性能接近裸机
* **跟 runc 兼容**：Pod 角度看就是普通容器

## 性能

| 维度 | runc | gVisor | kata |
| --- | --- | --- | --- |
| 启动 | ~100ms | ~200ms | ~500ms–2s |
| 内存占用 | ~10MB | ~50MB | ~150–300MB（VM） |
| 网络 IO | 100% | ~70% | ~90% |
| 计算 CPU | 100% | ~80% | ~95% |

## 部署

```yaml
apiVersion: node.k8s.io/v1
kind: RuntimeClass
metadata:
  name: kata
handler: kata
```

Node 装：

```bash
# CentOS / RHEL
sudo dnf install -y kata-containers

# 配 containerd
[plugins."io.containerd.grpc.v1.cri".containerd.runtimes.kata]
  runtime_type = "io.containerd.kata.v2"

# 测
sudo kata-runtime check
```

## 优缺点

* ✅ **最强隔离**：VM 级别，几乎无法逃逸
* ✅ 兼容 runc 接口，迁移简单
* ✅ 机密计算支持（TDX / SEV）
* ✅ 性能比 gVisor 好（接近 runc）
* ❌ **需要 KVM**：要求 host 有 `/dev/kvm`，云上**不一定有**
* ❌ 内存占用大（每个 Pod 一个 VM）
* ❌ 启动慢（VM 启动开销）
* ❌ 调试比 gVisor 还麻烦

## 适用场景

* **金融 / 政府 / 高敏感数据**
* 多租户隔离（serverless、CI/CD runner）
* **机密计算**：TDX / SEV 加密内存
* 不能信任 host 内核的场景（最极端）

## 云上的 kata

* **AWS**：Firecracker microVM（kata 的 AWS 定制版）
* **Azure**：Kata + Confidential VM
* **GCP**：Confidential Space 用 kata
* **阿里云 / 华为云**：部分实例支持嵌套虚拟化，可装

> ⚠️ **绝大多数云 ECS / VM 不开嵌套虚拟化**，要先确认 `/dev/kvm` 可用

## 监控 / 排查

```bash
# 检查环境
sudo kata-runtime check

# 看 kata 容器
crictl ps --runtime kata

# kata 日志
journalctl -u kata-containers -f

# VM 内部（debug VM）
sudo kata-runtime exec <container-id> /bin/sh
```

## 一句话

**VM 级隔离，最强安全，要 KVM，性能接近 runc 但启动慢**。