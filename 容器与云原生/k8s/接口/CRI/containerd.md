## 概念

containerd 是 CNCF 毕业项目，从 Docker daemon 拆出来的 **工业级容器运行时**，1.24+ 起 K8s 默认 CRI。

* 项目前身：Docker → 2017 年捐给 CNCF
* 起源：Docker 内部 containerd → 独立开源
* K8s 集成：`cri-containerd` plugin（1.0 起内置）→ 后来并入主仓库

## 架构

```
┌────────────── kubelet ──────────────┐
│           CRI gRPC                   │
└──────────────┬──────────────────────┘
               ▼
┌────── containerd ────────────────────┐
│  CRI plugin                          │
│      ↓                               │
│  containerd core                     │
│  ┌─────────────┐  ┌──────────────┐  │
│  │ snapshotter │  │   content    │  │
│  │  (overlayfs)│  │  store       │  │
│  └─────────────┘  └──────────────┘  │
│  ┌─────────────┐  ┌──────────────┐  │
│  │   images    │  │  metadata    │  │
│  └─────────────┘  └──────────────┘  │
│      ↓                               │
│  runtime shim (containerd-shim-...)   │
│      ↓                               │
│  runc                                │
└──────────────────────────────────────┘
```

## 关键能力

* **snapshotter**：overlayfs、native、btrfs、zfs、devmapper 等多种 fs driver
* **image pull**：并发拉取、p2p（自建 registry mirror）
* **runtime**：runc（默认）、crun 可切换
* **镜像 GC**：自动清理未用镜像
* **namespace**：每个 Pod 一个 Linux namespace（cri plugin 管理）
* **多镜像仓库**：自带 docker.io / gcr.io / harbor / 自签名
* **WASM runtime**：可加 `runwasi` 跑 wasm（边缘场景）

## 部署

K8s 默认装 containerd 的方式：

```bash
# kubeadm 装 containerd（推荐）
sudo apt install -y containerd
sudo containerd config default | sudo tee /etc/containerd/config.toml
sudo systemctl restart containerd

# kubeadm init 用 containerd
kubeadm init --cri-socket unix:///run/containerd/containerd.sock
```

配置文件 `/etc/containerd/config.toml` 关键项：

```toml
version = 2

[plugins."io.containerd.grpc.v1.cri"]
  sandbox_image = "registry.k8s.io/pause:3.9"
  [plugins."io.containerd.grpc.v1.cri".containerd]
    [plugins."io.containerd.grpc.v1.cri".containerd.runtimes]
      [plugins."io.containerd.grpc.v1.cri".containerd.runtimes.runc]
        runtime_type = "io.containerd.runc.v2"
        [plugins."io.containerd.grpc.v1.cri".containerd.runtimes.runc.options]
          SystemdCgroup = true
```

## 优缺点

* ✅ **K8s 默认**，文档全，社区最大
* ✅ 比 dockerd 轻量、稳定，资源占用低
* ✅ 支持多 runtime（runc、crun、wasm）
* ✅ 镜像存储 / GC / 私有仓库都齐
* ❌ 比 CRI-O 略重（但实际差距不大）
* ❌ CRI plugin 跟 daemon 主线 merge 时有过 break change

## 适用场景

* **几乎所有场景**，特别是裸 K8s / kubeadm / kOps 装的集群
* 需要 WASM runtime（runwasi）的边缘计算

## 监控 / 排查

```bash
# 状态
systemctl status containerd

# 镜像列表
ctr -n k8s.io images list

# 看 containerd 配置
containerd config default

# 日志
journalctl -u containerd -f

# 看容器
ctr -n k8s.io containers list
ctr -n k8s.io tasks list

# 调试模式
containerd --log-level debug
```

## 一句话

**K8s 默认 CRI，工业级稳定，1.24+ 起首选**。