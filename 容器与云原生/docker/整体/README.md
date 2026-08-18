# Docker 知识体系 (Docker Complete)

> 按照 [MySQL 文档](../../数据库/MySQL/) 的章节组织方式编排。涵盖 Docker 从入门到生产部署的完整知识体系。

## 章节目录

| 章节 | 标题 | 大小 | 主要内容 |
|------|------|------|---------|
| [01](01-Docker概述与安装.md) | Docker 概述与安装 | 11K | 历史、特点、安装、第一个容器 |
| [02](02-Docker体系结构.md) | Docker 体系结构 | 14K | 整体架构、daemon、containerd、Linux 内核机制 |
| [03](03-镜像与容器.md) | Docker 镜像与容器 | 13K | 镜像命令、容器命令、资源管理 |
| [04](04-Dockerfile详解.md) | Dockerfile 详解 | 14K | 所有指令、多阶段构建、镜像优化 |
| [05](05-数据持久化与卷.md) | 数据持久化与卷 | 10K | Volume、Bind Mount、tmpfs |
| [06](06-Docker网络.md) | Docker 网络 | 12K | 网络模式、DNS、端口映射 |
| [07](07-DockerCompose.md) | Docker Compose | 14K | 多服务编排、profiles、stack |
| [08](08-镜像仓库Registry.md) | 镜像仓库 Registry | 13K | Docker Hub、Harbor、签名 |
| [09](09-Docker安全.md) | Docker 安全 | 14K | Namespace、Cgroup、Capability、Falco |
| [10](10-Swarm与集群模式.md) | Docker Swarm 与集群模式 | 13K | Swarm 架构、服务、Stack |
| [11](11-性能调优与监控.md) | 性能调优与监控 | 12K | 资源调优、cAdvisor、Prometheus |
| [12](12-常见问题排查.md) | 常见问题排查 | 11K | 故障排查、实战案例 |
| [13](13-Docker实战案例集.md) | Docker 实战案例集 | 15K | 12 个真实场景完整案例 |
| [14](14-Docker生产实践与生态.md) | Docker 生产实践与生态 | 12K | CI/CD 集成、迁移到 K8s、未来趋势 |

## 知识地图

```text
入门                进阶                       高级                       实战
├─ 01 概述安装     ├─ 04 Dockerfile           ├─ 09 Docker 安全         ├─ 13 实战案例集
├─ 02 体系结构     ├─ 05 数据持久化           ├─ 10 Swarm 集群         └─ 14 生产实践
└─ 03 镜像容器     ├─ 06 Docker 网络         ├─ 11 性能监控
                 ├─ 07 Docker Compose     └─ 12 问题排查
                 └─ 08 镜像仓库
```

## 学习路线建议

### 初学者 (1 周)

1. 阅读 01 了解 Docker 是什么、如何安装
2. 学习 02 掌握整体架构
3. 实战 03 镜像与容器基本命令
4. 入门 04 写简单 Dockerfile

### 进阶者 (2-3 周)

1. 学习 04 完整 Dockerfile 与多阶段构建
2. 学习 05 数据持久化方案
3. 学习 06 Docker 网络与 DNS
4. 学习 07 Docker Compose 多服务编排

### 高级者 (4-6 周)

1. 学习 08 Harbor 私有仓库
2. 学习 09 Docker 安全 (Falco, Trivy, Cosign)
3. 学习 10 Swarm 集群模式
4. 学习 11 性能调优与监控

### 实战方向

- 重点:12 故障排查 + 13 实战案例
- 必备:14 CI/CD 集成 + 迁移到 K8s
- 进阶:Swarm 集群 + K8s 集成

## 配套工具推荐

| 工具 | 用途 | 链接 |
|------|------|------|
| Docker Desktop | 桌面工具 | https://www.docker.com/products/docker-desktop |
| OrbStack | macOS 替代 | https://orbstack.dev |
| Colima | 开源替代 | https://github.com/abiosoft/colima |
| k9s | TUI 管理 | https://k9scli.io |
| Lazydocker | TUI 管理 | https://github.com/jesseduffield/lazydocker |
| dive | 镜像分析 | https://github.com/wagoodman/dive |
| Trivy | 漏洞扫描 | https://trivy.dev |
| Cosign | 镜像签名 | https://github.com/sigstore/cosign |
| Hadolint | Dockerfile 检查 | https://github.com/hadolint/hadolint |
| netshoot | 网络调试 | https://github.com/nicolaka/netshoot |
| cAdvisor | 容器指标 | https://github.com/google/cadvisor |

## 安装方式选择

| 场景 | 推荐 |
|------|------|
| Linux 生产 | docker-ce (apt/yum) |
| macOS 开发 | OrbStack / Colima |
| Windows 开发 | Docker Desktop / WSL2 |
| 边缘/IoT | K3s (基于 K8s) |
| CI/CD | Docker-in-Docker |

## 核心概念速记

```text
镜像 (Image):   标准化应用打包 (分层)
容器 (Container): 镜像的运行实例
仓库 (Registry): 镜像分发 (Docker Hub, Harbor)
数据卷:        持久化 (推荐 Volume)
网络:         桥接 (默认) / host / overlay
Compose:     单机多容器编排
Swarm:       集群编排 (小规模)
K8s:         生产标准
```

## 关键命令速记

```bash
# 镜像
docker pull <image>            # 拉取
docker build -t <name> .        # 构建
docker push <image>            # 推送
docker images                  # 列表
docker rmi <image>             # 删除

# 容器
docker run [opts] <image>      # 创建并启动
docker ps                      # 列表
docker exec -it <c> bash      # 进入
docker logs -f <c>             # 日志
docker stop / start / restart
docker rm <c>                  # 删除

# 网络与卷
docker network ls
docker volume ls

# 清理
docker system prune -af        # 全部清理
```

## 与 K8s 关系

```text
Docker = 容器运行时 (K8s 的底层)
K8s = 容器编排平台 (构建在 Docker/containerd 之上)

迁移路径:
Docker → Compose → Swarm → K8s
(Docker Image) (单实例) (小集群) (生产)
                ↓
           Kompose 转换工具
```

## 版本说明

- Docker Engine: 25.x+ (2024)
- Docker Desktop: 4.x+
- Compose V2: docker compose (无横线)
- 推荐: Docker Engine + Compose V2

## 贡献

发现错误或想补充内容,直接修改对应章节的 md 文件即可。
