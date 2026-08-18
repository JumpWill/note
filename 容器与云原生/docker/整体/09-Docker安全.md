# Docker 安全 (Security)

> 本章系统讲解 Docker 安全体系:Namespace/Cgroup/Capability、镜像安全、容器隔离、网络安全、运行时防护。

## 一、Docker 安全概述

### 1.1 Docker 安全威胁

```text
Docker 容器面临的威胁:

1. 镜像层
   - 恶意镜像 (后门、挖矿木马)
   - 已知漏洞 (CVE)
   - 硬编码密钥

2. 容器层
   - 容器逃逸 (Container Escape)
   - 特权升级 (Privilege Escalation)
   - 资源耗尽 (DoS)
   - 网络攻击

3. 运行时层
   - 横向移动 (Lateral Movement)
   - 数据窃取
   - 持久化 (Persistence)
   - 反弹 Shell
```

### 1.2 Docker 安全模型

```text
Docker 安全 = 多层防御:

┌────────────────────────────────�
│  镜像层                         │
│  - 镜像签名                      │
│  - 漏洞扫描                      │
│  - 基础镜像选择                  │
├────────────────────────────────┤
│  容器层                         │
│  - Namespace 隔离                │
│  - Cgroup 限制                   │
│  - Capability 最小化              │
│  - Seccomp 系统调用过滤            │
│  - AppArmor / SELinux             │
├────────────────────────────────┤
│  网络层                         │
│  - 用户自定义网络                │
│  - NetworkPolicy (K8s)          │
│  - TLS 加密通信                  │
│  - Service Mesh                  │
├────────────────────────────────┤
│  运行时层                       │
│  - Falco / Tracee               │
│  - 日志审计                      │
│  - 异常行为检测                  │
└────────────────────────────────┘
```

### 1.3 Docker 安全原则

```text
1. 最小权限原则 (Principle of Least Privilege)
2. 纵深防御 (Defense in Depth)
3. 默认拒绝 (Deny by Default)
4. 零信任 (Zero Trust)
5. 持续验证 (Continuous Verification)
6. 可审计 (Audit Trail)
```

---

## 二、Linux 内核安全机制

### 2.1 Namespace (命名空间)

```text
Namespace 提供资源隔离,Docker 用 6 种 namespace:

1. PID namespace    - 进程 ID 隔离
   每个容器看到自己的 PID 1 (init 进程)

2. Network namespace - 网络隔离
   每个容器有独立的网卡、IP、路由表

3. Mount namespace   - 文件系统挂载隔离
   每个容器有自己的 / 目录树

4. UTS namespace     - 主机名/域名隔离
   容器可设置不同的 hostname

5. IPC namespace     - 进程间通信隔离
   System V IPC 和 POSIX 消息队列隔离

6. User namespace    - 用户 ID 映射 (Docker 1.10+)
   容器内 root 映射到宿主普通用户
```

### 2.2 Cgroup (控制组)

```text
Cgroup 提供资源限制:

Docker 通过 Cgroup 限制:
- CPU (cpu, cpuset)
- 内存 (memory)
- 块设备 IO (blkio)
- 网络 (net_cls, net_prio)
- 进程数 (pids)

Docker 自动为每个容器创建 Cgroup:
/sys/fs/cgroup/<subsystem>/docker/<container-id>/

查看容器资源限制:
cat /sys/fs/cgroup/memory/docker/<container-id>/memory.limit_in_bytes
```

### 2.3 Linux Capabilities

```text
传统 Unix root 权限过大,Linux 拆分成 40+ 个细粒度 capabilities:

Capability (部分):
- CAP_CHOWN            - 修改文件权限
- CAP_NET_ADMIN        - 网络管理
- CAP_NET_BIND_SERVICE - 绑定特权端口 (< 1024)
- CAP_SYS_ADMIN        - 系统管理 (⚠️ 危险)
- CAP_SYS_PTRACE       - ptrace 其他进程 (⚠️ 危险)
- CAP_SYS_MODULE       - 加载内核模块 (⚠️ 危险)
- CAP_DAC_OVERRIDE     - 绕过文件权限检查

Docker 默认 capability 集合:
- 保留: CHOWN, DAC_OVERRIDE, FSETID, FOWNER, MKNOD, NET_RAW,
        SETGID, SETUID, SETFCAP, SETPCAP, NET_BIND_SERVICE,
        SYS_CHROOT, KILL, AUDIT_WRITE
- 移除: SYS_ADMIN, SYS_MODULE, SYS_RAWIO, SYS_PTRACE 等危险权限
```

### 2.4 Seccomp (安全计算)

```text
Seccomp 限制进程可用的系统调用:

Docker 默认 Seccomp profile:
- 允许 ~300+ 系统调用 (足够容器运行)
- 拒绝危险调用 (如 kexec, reboot, mount 等)

自定义 Seccomp profile:
# seccomp.json
{
  "defaultAction": "SCMP_ACT_ERRNO",
  "architectures": ["SCMP_ARCH_X86_64"],
  "syscalls": [
    {
      "names": ["read", "write", "exit", ...],
      "action": "SCMP_ACT_ALLOW"
    }
  ]
}

# 使用
docker run --security-opt seccomp=./seccomp.json alpine
```

---

## 三、容器安全配置

### 3.1 安全选项 (Security Options)

```bash
# 设置运行用户
docker run -u 1000:1000 nginx
docker run --user nginx nginx

# 限制 capability
docker run --cap-drop=ALL --cap-add=NET_BIND_SERVICE nginx

# 只读根文件系统
docker run --read-only nginx
docker run --read-only --tmpfs /tmp --tmpfs /run nginx

# 禁止特权升级
docker run --security-opt no-new-privileges nginx

# 禁用 seccomp
docker run --security-opt seccomp=unconfined nginx

# 自定义 seccomp
docker run --security-opt seccomp=./seccomp.json alpine

# 启用 AppArmor
docker run --security-opt apparmor=docker-default nginx

# SELinux (RHEL/CentOS)
docker run --security-opt label=level:s0:c100,c200 nginx
```

### 3.2 特权模式 (避免使用)

```bash
# ⚠️ 特权模式 (几乎禁用所有安全机制)
docker run --privileged nginx

# 风险:
# - 访问所有设备
# - 关闭大部分 capability
# - 可以挂载 / 目录
# - 容器逃逸风险极高

# 只有特殊场景需要:
# - Docker-in-Docker
# - 需要操作硬件设备
# - 系统级调试

# 替代: 精确授予 capability
docker run --cap-add=SYS_ADMIN --cap-add=SYS_PTRACE ...
```

### 3.3 安全上下文示例

```bash
# 生产标准配置
docker run -d \
  --name web \
  --user 1000:1000 \                    # 非 root
  --read-only \                        # 根 FS 只读
  --tmpfs /tmp:size=100m \            # 临时目录
  --cap-drop=ALL \                    # 删除所有 capability
  --cap-add=NET_BIND_SERVICE \         # 只加必要的
  --security-opt no-new-privileges \   # 禁止提权
  --security-opt seccomp=./seccomp.json \
  --security-opt apparmor=docker-default \
  --read-only \
  --tmpfs /tmp:size=100m \
  nginx:alpine
```

---

## 四、镜像安全

### 4.1 镜像扫描

```bash
# Trivy (推荐, 全面)
trivy image nginx:1.25
trivy image --severity HIGH,CRITICAL myapp:1.0
trivy image --format json -o report.json myapp:1.0

# Trivy 与 Harbor 集成 (自动扫描)
# Harbor 系统管理 → 配置 → 镜像扫描 → Trivy

# Clair (CoreOS 出品)
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  quay.io/coreos/clair-local-scan myapp:1.0

# Snyk (商业)
snyk container test myapp:1.0
```

### 4.2 镜像签名 (Cosign)

```bash
# 1. 安装 cosign
brew install cosign

# 2. 生成密钥
cosign generate-key-pair
# 生成 cosign.key 和 cosign.pub

# 3. 签名镜像
cosign sign --key cosign.key myregistry/myapp:1.0

# 4. 验证签名
cosign verify --key cosign.pub myregistry/myapp:1.0

# 5. Keyless 签名 (推荐, CI/CD 用)
#    使用 GitHub Actions / GitLab CI OIDC token
cosign sign --keyless myregistry/myapp:1.0

# 6. 在 K8s 中强制验证 (使用 Sigstore Policy Controller)
```

### 4.3 Docker Content Trust (DCT)

```bash
# 启用 DCT
export DOCKER_CONTENT_TRUST=1

# 推送 (自动签名)
docker push myregistry/myapp:1.0

# 拉取 (自动验证)
docker pull myregistry/myapp:1.0
# 签名失败: "Error response from daemon: ..."

# 禁用 DCT
export DOCKER_CONTENT_TRUST=0
```

### 4.4 镜像最佳实践

```dockerfile
# 1. 使用官方最小基础镜像
FROM alpine:3.18

# 2. 不要用 root
RUN addgroup -S app && adduser -S -G app app
USER app

# 3. 清理缓存
RUN apk add --no-cache curl \
    && rm -rf /var/cache/apk/*

# 4. 不要硬编码密钥
# 错误: ENV DB_PASSWORD=secret
# 正确: 使用 K8s Secret / Vault / External Secrets

# 5. 不要在镜像中留不必要的文件
# 使用 .dockerignore 排除

# 6. 多阶段构建, 最终镜像最小
FROM golang:1.21 AS builder
...
FROM alpine:3.18
COPY --from=builder /app/myapp /app/
```

### 4.5 镜像分发安全

```bash
# 1. 使用 HTTPS Registry (强制 TLS)
# 2. 私有 Registry 防火墙限制
# 3. RBAC 控制访问 (Harbor)
# 4. 审计日志
# 5. 镜像复制签名 (Harbor 镜像复制可保持签名)
```

---

## 五、网络安全

### 5.1 容器网络安全最佳实践

```bash
# 1. 使用用户自定义网络 (而非默认 bridge)
docker network create my-net
docker run --network my-net --name web nginx

# 2. 最小化端口暴露
docker run -p 80:80 nginx    # 只暴露 80

# 3. 使用 host 网络 (性能优先场景)
docker run --network host nginx

# 4. 多网络隔离
docker network create frontend
docker network create backend
docker run --network backend --name db postgres
docker run --network frontend --network backend --name api my-api
```

### 5.2 TLS 加密 Registry 通信

```bash
# Docker daemon 配置 TLS Registry
# /etc/docker/daemon.json
{
  "insecure-registries": []    # 强制 HTTPS
}

# 单个 Registry 配置
docker daemon.json
{
  "tlscacert": "/etc/docker/certs/ca.crt",
  "tlscert": "/etc/docker/certs/client.crt",
  "tlskey": "/etc/docker/certs/client.key"
}

# 登录时指定证书
docker login --tlscacert=ca.crt registry.example.com
```

### 5.3 容器间通信加密

```bash
# 容器间 mTLS (服务网格如 Istio)
# - 自动加密容器间通信
# - 自动证书管理

# Docker Swarm 内置加密 overlay 网络
docker network create -d overlay \
  --opt encrypted=true \
  my-secure-net
```

### 5.4 网络流量控制

```bash
# 限制容器网络带宽
docker run --device-read-bps /dev/sda:1mb \
  my-app

# Docker 内置流量控制 (CNI 插件)
# Calico:
#   - NetworkPolicy
#   - 带宽限制

# 在 K8s 中使用 NetworkPolicy
```

---

## 六、运行时安全

### 6.1 Falco (CNCF 运行时安全)

```bash
# 1. 安装 Falco (DaemonSet 部署)
helm repo add falcosecurity https://falcosecurity.github.io/charts
helm install falco falcosecurity/falco \
  --namespace falco --create-namespace \
  --set tty=true \
  --set falco.json_output=true \
  --set falco.http_output.enabled=true \
  --set falco.http_output.url="http://falcosidekick:2801"
```

### 6.2 Falco 检测规则

```yaml
# /etc/falco/falco_rules.yaml (示例)

# 规则 1: 检测容器内 shell
- rule: Terminal shell in container
  desc: Detect shell activity spawned inside a container
  condition: >
    spawned_process and container and
    proc.name in (bash, sh, zsh, ksh)
  output: >
    Shell spawned in container
    (user=%user.name command=%proc.cmdline container=%container.name)
  priority: WARNING
  tags: [process, container]

# 规则 2: 检测容器内安装软件
- rule: Package management in container
  desc: Package management process in container
  condition: >
    spawned_process and container and
    proc.name in (apt, yum, dnf, apk, pip)
  output: >
    Package management in container
    (user=%user.name command=%proc.cmdline container=%container.name)
  priority: ERROR

# 规则 3: 检测敏感文件访问
- rule: Sensitive file accessed
  desc: Detect access to sensitive files
  condition: >
    open_read and container and
    fd.name in (/etc/shadow, /etc/passwd, /etc/sudoers)
  output: >
    Sensitive file accessed
    (user=%user.name file=%fd.name container=%container.name)
  priority: CRITICAL

# 规则 4: 检测容器逃逸
- rule: Container escape detected
  desc: Detect potential container escape via privileged container
  condition: >
    container and
    container.privileged=true and
    spawned_process and
    proc.name in (nsenter, chroot, unshare)
  output: >
    Possible container escape
    (user=%user.name command=%proc.cmdline container=%container.name)
  priority: CRITICAL
  tags: [escalation]
```

### 6.3 容器逃逸检测

```bash
# Falco 默认规则涵盖:
- privileged container escape (nsenter, unshare)
- sensitive mount (宿主机 / 挂载)
- capability escape (CAP_SYS_ADMIN, CAP_SYS_PTRACE)
- network escape (CAP_NET_ADMIN)
- crypto mining detection

# 自定义规则示例: 检测容器内 SSH 服务
- rule: SSH server in container
  condition: container and proc.name in (sshd)
  output: SSH server running in container
  priority: WARNING
```

### 6.4 日志审计

```bash
# Docker daemon 日志 (JSON driver)
# /var/lib/docker/containers/<id>/<id>-json.log

# 每条日志包含:
{
  "log": "...",
  "stream": "stdout",
  "time": "2026-08-18T10:00:00Z",
  "container_id": "abc...",
  "container_name": "web"
}

# 推荐: 用 Loki / ELK 收集
```

---

## 七、Docker 安全工具链

### 7.1 工具一览

```text
镜像层:
- Trivy        - 漏洞扫描 (推荐)
- Clair        - 漏洞扫描 (CoreOS)
- Snyk         - 商业漏洞扫描
- Anchore      - 镜像合规
- Cosign       - 镜像签名

容器层:
- Docker Bench Security - 安全基线检查
- Falco        - 运行时检测 (CNCF)
- Tracee       - 基于 eBPF 的运行时检测
- Sysdig       - 商业运行时安全

密钥管理:
- HashiCorp Vault
- External Secrets Operator
- Docker Secrets (Swarm)
- Bitnami Sealed Secrets

合规与策略:
- Open Policy Agent (OPA) / Gatekeeper
- Kyverno
- Docker Security Benchmark (CIS)
```

### 7.2 Docker Bench Security

```bash
# 安装
docker run --rm \
  --net host \
  --pid host \
  --userns host \
  --cap-add audit_control \
  -e DOCKER_SOCKET_PATH=/var/run/docker.sock \
  docker/docker-bench-security

# 输出:
# [PASS] 1.1 - Ensure a separate partition for containers has been created
# [WARN] 1.2 - Ensure only trusted users are able to control Docker daemon
# ...
```

### 7.3 OPA / Gatekeeper (策略执行)

```yaml
# K8s Gatekeeper 限制镜像来源
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: K8sAllowedRepos
metadata:
  name: allowed-repos
spec:
  match:
    kinds:
    - apiGroups: [""]
      kinds: ["Pod"]
  parameters:
    repos:
    - "registry.example.com/*"
    - "gcr.io/myorg/*"
```

---

## 八、Docker Bench for Security (CIS 标准)

### 8.1 CIS Docker Benchmark

```text
CIS Docker Benchmark 关键检查项:

1. Host Configuration
   - 1.1 独立分区
   - 1.2 受信任用户
   - 1.3 审计 docker daemon
   - 1.4 限制容器间网络流量

2. Docker daemon 配置
   - 2.1 限制网络流量
   - 2.2 日志级别 info
   - 2.3 启用 userland-proxy
   - 2.4 启用 iptables
   - 2.5 启用 ip-forward
   - 2.6 启用 live-restore

3. Docker 文件配置
   - 3.1 daemon.json 权限 644
   - 3.2 daemon.json 所有者 root
   - 3.3 /var/lib/docker 权限 711
   - 3.4 /etc/docker 权限 755

4. 容器镜像
   - 4.1 创建用户
   - 4.5 使用最小化基础镜像
   - 4.6 HEALTHCHECK
   - 4.7 COPY 而非 ADD
   - 4.8 --user 指定用户
   - 4.9 --read-only 根 FS

5. 容器运行时
   - 5.1 --privileged=false
   - 5.2 限制 capability
   - 5.3 限制内存
   - 5.4 限制 CPU
   - 5.5 --pids-limit
   - 5.7 --security-opt no-new-privileges
   - 5.10 --read-only 根 FS
   - 5.12 --pids-limit
   - 5.28 容器内禁止 SSH

6. Docker 安全操作
   - 6.1 镜像漏洞扫描
   - 6.2 镜像签名
   - 6.3 最小化镜像
```

### 8.2 运行 Docker Bench

```bash
# 方式 1: Docker 镜像
docker run --rm \
  --net host \
  --pid host \
  --userns host \
  --cap-add audit_control \
  -v /etc:/etc:ro \
  -v /var/lib:/var/lib:ro \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  -v /usr/lib/systemd:/usr/lib/systemd:ro \
  -v /etc/systemd:/etc/systemd:ro \
  --security-opt seccomp=unconfined \
  docker/docker-bench-security

# 输出 JSON 报告
docker run --rm ... docker/docker-bench-security -l /tmp/report.json

# 方式 2: 手动检查 (对照 CIS 文档)
```

---

## 九、Docker 安全最佳实践

### 9.1 镜像构建安全

```text
1. 使用官方最小基础镜像
2. 指定镜像 tag (不用 latest)
3. 不要在镜像中硬编码密钥
4. 使用 .dockerignore
5. 多阶段构建, 减小攻击面
6. HEALTHCHECK 必须设置
7. 镜像签名 (CI/CD 自动签名)
8. 镜像扫描集成到 CI/CD
```

### 9.2 容器运行安全

```text
1. 设置非 root 用户 (--user)
2. 只读根 FS (--read-only)
3. 删除所有 capability, 只加必要的 (--cap-drop ALL --cap-add ...)
4. 禁止特权升级 (--security-opt no-new-privileges)
5. 资源限制 (--memory, --cpus, --pids-limit)
6. 健康检查 (HEALTHCHECK)
7. 日志配置 (--log-driver + --log-opt)
8. 重启策略 (--restart unless-stopped)
9. 网络隔离 (用户自定义网络)
10. 不在容器内 SSH
```

### 9.3 Docker daemon 安全

```json
{
  "icc": false,                              // 容器间禁止通信 (默认 true)
  "userland-proxy": true,                    // userland proxy
  "iptables": true,                          // iptables
  "ip-forward": true,                        // ip 转发
  "ipv6": false,                             // 禁用 IPv6 (如不需要)
  "live-restore": true,                      // daemon 重启容器存活
  "no-new-privileges": true,                 // 默认禁止提权
  "user-namespace-remap": "default",         // user namespace (1.10+)
  "default-ulimits": {
    "nofile": { "Name": "nofile", "Hard": 65535, "Soft": 65535 }
  },
  "live-restore": true
}
```

### 9.4 镜像仓库安全

```text
1. 使用 TLS Registry
2. RBAC 控制访问 (Harbor)
3. 镜像签名 (Cosign)
4. 漏洞扫描 (Trivy)
5. 镜像复制签名保留
6. 审计日志
7. 凭据定期轮换
8. 私有仓库防火墙
```

---

## 核心要点速记

### Docker 安全模型

```text
镜像层:  签名 + 扫描 + 基础镜像
容器层:  namespace + cgroup + capability + seccomp
网络层:  自定义网络 + TLS + NetworkPolicy
运行时:  Falco + 日志审计
```

### Linux 内核三大机制

```text
namespace:  资源隔离 (进程/网络/文件系统)
cgroup:    资源限制 (CPU/内存/IO)
capability: 权限拆分 (40+ 细粒度权限)
```

### 容器安全选项

```bash
docker run \
  --user 1000:1000 \              # 非 root
  --read-only \                  # 根 FS 只读
  --cap-drop=ALL \               # 删除所有 capability
  --cap-add=NET_BIND_SERVICE \   # 只加必要的
  --security-opt no-new-privileges \
  --tmpfs /tmp \
  nginx
```

### 镜像安全工具链

```text
漏洞扫描: Trivy, Clair, Snyk
镜像签名: Cosign, Notary
运行时检测: Falco, Tracee
合规检查: Docker Bench (CIS)
策略执行: OPA Gatekeeper, Kyverno
密钥管理: Vault, External Secrets
```

### 镜像扫描

```bash
trivy image myapp:1.0
trivy image --severity HIGH,CRITICAL myapp:1.0
```

### 镜像签名

```bash
cosign sign --key cosign.key myregistry/myapp:1.0
cosign verify --key cosign.pub myregistry/myapp:1.0
cosign sign --keyless myregistry/myapp:1.0
```

### Falco 规则示例

```yaml
- rule: Terminal shell in container
  condition: spawned_process and container and proc.name in (bash, sh)
  output: Shell spawned in container
  priority: WARNING
```

### CIS Benchmark 关键项

```text
1. --privileged=false
2. --cap-drop=ALL
3. --read-only 根 FS
4. --user 非 root
5. --pids-limit
6. --memory 限制
7. --security-opt no-new-privileges
```

### 完整安全清单

```text
镜像:  官方镜像 + 签名 + 扫描 + 不可变 tag
构建:  多阶段 + 非 root + HEALTHCHECK
运行:  user + read-only + cap 限制 + security-opt
网络:  自定义网络 + TLS + 最小化端口
注册表:  私有 Harbor + RBAC + 漏洞扫描
运行时:  Falco + 日志 + 审计
```

---

## 参考

- **Docker 安全**: https://docs.docker.com/engine/security/
- **CIS Docker Benchmark**: https://www.cisecurity.org/benchmark/docker
- **Falco**: https://falco.org/
- **Trivy**: https://github.com/aquasecurity/trivy
- **Cosign**: https://github.com/sigstore/cosign
- **Docker Bench**: https://github.com/docker/docker-bench-security
- **OPA Gatekeeper**: https://github.com/open-policy-agent/gatekeeper
