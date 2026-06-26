## 概念

CRI-O 是 **专为 K8s 设计的容器运行时**，由 Red Hat 主导，**OpenShift 默认**。最小化、跟 K8s CRI 协议同步演进。

* 项目起源：2016 Red Hat 发起
* 设计原则：只做一件事——CRI，不支持 docker CLI、不做 build
* 跟 containerd 的关系：两者都符合 CRI / OCI 规范，CRI-O 更轻，containerd 更通用

## 架构

```
┌──────── kubelet ─────────┐
│      CRI gRPC            │
└────────────┬─────────────┘
             ▼
┌──────── CRI-O ───────────┐
│  server (CRI)            │
│      ↓                   │
│  container runtime (runc)│
│      ↓                   │
│  image service           │
│  (registries.conf)       │
│      ↓                   │
│  storage                │
│  (overlay / devmapper)  │
└──────────────────────────┘
```

* **没有 shim**：直接用 runc
* **没有 docker 兼容层**：纯 CRI
* **没有 image build**：纯 pull / run

## 关键能力

* **runC / crun**：默认 runC，可切 crun（C 写的，更小更快）
* **seccomp profile**：内置 K8s 默认 profile，可在 config 配置自定义
* **apparmor**：默认启用，可关
* **镜像仓库配置**：`/etc/containers/registries.conf` 集中管 mirror / insecure
* **多架构**：arm64 / x86_64 / s390x / ppc64le
* **policy**：sigstore / cosign 签名校验
* **WASM**：实验性支持（CRUN + WASI）

## 部署

OpenShift 自带。裸 K8s 装：

```bash
# CentOS / RHEL / Fedora
sudo dnf install -y cri-o
sudo systemctl enable --now cri-o

# kubeadm 配 CRI socket
sudo kubeadm init --cri-socket unix:///var/run/crio/crio.sock

# 配置文件
/etc/crio/crio.conf
/etc/containers/registries.conf
/etc/containers/policy.json
```

切换 runtime（runc ↔ crun）：

```toml
# /etc/crio/crio.conf
[crio.runtime]
default_runtime = "crun"

[crio.runtime.runtimes.crun]
runtime_path = "/usr/bin/crun"
runtime_type = "oci"

[crio.runtime.runtimes.runc]
runtime_path = "/usr/bin/runc"
runtime_type = "oci"
```

## 优缺点

* ✅ **最轻**：没有 shim，资源占用比 containerd 还少
* ✅ **跟 K8s 同步演进**：新 CRI 特性第一时间支持
* ✅ OpenShift 默认，**Red Hat 生态首选**
* ✅ sigstore / cosign 验证原生支持
* ❌ 没有 docker CLI 兼容，要调试得用 `crictl`
* ❌ 社区比 containerd 小，但 Red Hat 背书稳
* ❌ 没 WASM runtime（虽然有实验性支持）

## 适用场景

* **OpenShift / RHEL 生态**
* 想用 crun（比 runc 启动更快，内存更少）
* 严格 sigstore 签名验证场景

## 监控 / 排查

```bash
# 状态
systemctl status crio

# 日志
journalctl -u crio -f

# 容器列表（用 crictl，不是 docker）
crictl ps
crictl images

# 配置验证
crio-status info

# 调试模式
crio --debug
```

## 一句话

**为 K8s 量身定做的最轻量 CRI，OpenShift / Red Hat 生态默认**。