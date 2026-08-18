# Docker 网络 (Networking)

> 本章详解 Docker 网络架构、各种网络模式、容器间通信、DNS 解析与网络排查。

## 一、Docker 网络架构

### 1.1 默认网络驱动

```text
Docker 网络驱动:
1. bridge    - 默认 (NAT 模式)
2. host      - 共享宿主网络栈
3. overlay   - Swarm / 多主机
4. macvlan   - 物理网卡虚拟
5. ipvlan    - 类似 macvlan
6. none      - 无网络

第三方 CNI 驱动:
- calico
- flannel
- weave
- cilium
```

### 1.2 默认网络 (bridge)

```text
Docker 安装时自动创建 3 个网络:

$ docker network ls
NETWORK ID     NAME      DRIVER    SCOPE
abc123...      bridge    bridge    local    # 默认
def456...      host      host      local    # 共享宿主
ghi789...      none      null      local    # 无网络

默认 bridge 网络特征:
- 网桥: docker0 (172.17.0.1/16)
- 容器 IP: 172.17.0.x
- 容器间通过 IP 互通
- 容器到外网通过 NAT
- DNS 只能用 IP, 不用容器名 (老版本)
```

---

## 二、网络模式详解

### 2.1 bridge (默认)

```bash
# 默认网络
docker run -d --name web nginx

# 创建自定义 bridge 网络 (推荐)
docker network create my-net
docker run -d --name web --network my-net nginx
docker run -d --name api --network my-net my-api

# 自定义网络特点:
# - 容器间可用容器名互通 (Docker DNS)
# - 自动 DNS 解析
# - 更好的隔离

# 测试互通
docker exec -it api ping web
# PING web (172.18.0.2): 56 data bytes
```

### 2.2 host (共享宿主)

```bash
# 容器直接使用宿主网络栈 (无隔离)
docker run -d --network host nginx

# 特点:
# - 性能最好 (无网络虚拟化)
# - 容器与宿主共享 IP/端口
# - 端口冲突风险高
# - 适合: 监控 agent、网络工具

# 测试
curl http://localhost/    # 直接访问宿主的 80 端口

# 适用场景:
# - Prometheus node-exporter
# - 网络诊断工具 (iperf, tcpdump)
# - 高性能要求的应用
```

### 2.3 none (无网络)

```bash
# 完全无网络
docker run -d --network none alpine

# 适用:
# - 安全敏感任务
# - 数据处理任务 (不需要网络)
# - 离线计算
```

### 2.4 container (共享网络命名空间)

```bash
# 与已存在容器共享网络命名空间
docker run -d --name web nginx
docker run -d --network container:web alpine

# 适用:
# - 紧密协作的容器 (sidecar 模式)
# - 性能要求高 (避免 NAT)
```

### 2.5 overlay (多主机 Swarm)

```bash
# Swarm 集群 (需先初始化)
docker swarm init

# 创建 overlay 网络
docker network create --driver overlay my-overlay

# 部署服务
docker service create --network my-overlay --name web nginx

# 跨主机容器间通过 overlay 网络通信
```

### 2.6 macvlan / ipvlan

```bash
# macvlan: 容器有独立 MAC 地址, 像物理机
docker network create -d macvlan \
  --subnet=192.168.1.0/24 \
  --gateway=192.168.1.1 \
  -o parent=eth0 \
  my-macvlan

# 容器直接获得物理网络 IP
docker run --network my-macvlan alpine

# 适用:
# - 需要容器像独立机器一样
# - 传统网络应用
# - 性能最佳 (无 NAT)
```

---

## 三、容器 DNS

### 3.1 Docker 内置 DNS

```text
Docker 守护进程内置 DNS 服务器:
- 默认 127.0.0.11:53
- 容器内 /etc/resolv.conf 自动配置

DNS 解析能力:
- 同一网络中的容器名 (自定义网络)
- Service 名 (Swarm)
- Task 名 (Swarm)
```

### 3.2 自定义网络 vs 默认网络

```bash
# 默认 bridge 网络 (旧版本限制)
docker run -d --name web1 nginx
docker run -d --name web2 nginx

docker exec web1 ping web2
# ping: bad address 'web2'    # 默认网络无法解析!

# 自定义网络 (推荐)
docker network create my-net
docker run -d --name web1 --network my-net nginx
docker run -d --name web2 --network my-net nginx

docker exec web1 ping web2
# PING web2 (172.18.0.3): 56 data bytes    # OK
```

### 3.3 DNS 自定义

```bash
# 指定 DNS 服务器
docker run -d \
  --dns 8.8.8.8 \
  --dns 8.8.4.4 \
  nginx

# DNS 搜索域
docker run -d \
  --dns-search example.com \
  --dns-search internal.example.com \
  nginx

# DNS 选项
docker run -d \
  --dns-option ndots:5 \
  --dns-option timeout:3 \
  nginx

# 容器内查看
docker run --rm \
  --dns 8.8.8.8 \
  alpine cat /etc/resolv.conf
```

---

## 四、端口映射

### 4.1 基本映射

```bash
# -p host:container
docker run -d -p 8080:80 nginx
# 访问 http://localhost:8080 → 容器 80

# 指定 IP
docker run -d -p 127.0.0.1:8080:80 nginx
docker run -d -p 0.0.0.0:8080:80 nginx

# 协议
docker run -d -p 53:53/udp dns-server
docker run -d -p 53:53/tcp dns-server
docker run -d -p 53:53     # 两种协议都暴露

# 端口范围
docker run -d -p 8080-8090:8080-8090 my-app

# 随机端口
docker run -d -P nginx    # 暴露所有 EXPOSE 端口, 映射到随机端口

# 查看映射
docker port <container>
```

### 4.2 容器间通信

```bash
# 方式 1: 同一网络, 用容器名
docker network create backend
docker run -d --name db --network backend postgres
docker run -d --network backend --env DB_HOST=db my-app
# my-app 容器内可解析 db → DB IP

# 方式 2: link (旧, 推荐用 --network)
docker run -d --name db postgres
docker run -d --link db:database my-app
# my-app 容器内可通过 database 访问 db
```

---

## 五、高级网络配置

### 5.1 自定义网络参数

```bash
# 创建网络时指定参数
docker network create \
  --driver bridge \
  --subnet 172.20.0.0/16 \
  --gateway 172.20.0.1 \
  --ip-range 172.20.0.0/24 \
  --aux-address "my-router=172.20.0.254" \
  --opt com.docker.network.bridge.name=br-custom \
  my-custom-net

# 网络驱动选项
docker network create \
  --driver bridge \
  --opt com.docker.network.bridge.enable_icc=true \      # 容器间通信
  --opt com.docker.network.bridge.enable_ip_masquerade=true \
  --opt com.docker.network.bridge.host_binding_ipv4=0.0.0.0 \
  my-net
```

### 5.2 多网络连接

```bash
# 一个容器连接多个网络
docker network create frontend
docker network create backend

# 启动前端容器
docker run -d --name web \
  --network frontend \
  nginx

# 启动后端容器
docker run -d --name api \
  --network backend \
  my-api

# 中间层连接两个网络
docker network connect frontend api

# 现在 api 容器同时在 frontend 和 backend 网络
```

### 5.3 IP 指定

```bash
# 创建网络时指定子网
docker network create --subnet=172.25.0.0/16 my-net

# 启动容器指定 IP
docker run -d --network my-net --ip 172.25.0.100 nginx

# 查看 IP
docker inspect <container> | grep IPAddress
```

---

## 六、网络安全

### 6.1 端口暴露最小化

```bash
# ❌ 暴露所有端口 (危险)
docker run -d -P nginx    # 自动暴露所有 EXPOSE 端口

# ✅ 仅暴露必要端口
docker run -d -p 80:80 nginx    # 只暴露 80
```

### 6.2 网络隔离

```bash
# 不同业务用不同网络
docker network create public    # 对外服务
docker network create internal  # 内部服务

# 应用只加入 internal
docker run -d --network internal my-app

# 入口 (Nginx) 同时加入两个
docker run -d \
  --network public \
  --network internal \
  nginx
```

### 6.3 防火墙 (iptables)

```bash
# Docker 自动管理 iptables 规则

# 查看 Docker 的 iptables 规则
sudo iptables -L DOCKER-USER -n -v
sudo iptables -L DOCKER -n -v

# 自定义规则 (添加到 DOCKER-USER 链)
sudo iptables -I DOCKER-USER -i docker0 \
  -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT

# 限制来自特定 IP 的访问
sudo iptables -I DOCKER-USER -i docker0 \
  -s 10.0.0.0/24 -j DROP

# Docker 启用 userland-proxy (推荐)
# /etc/docker/daemon.json
{
  "userland-proxy": true,
  "iptables": true
}
```

---

## 七、DNS 与服务发现

### 7.1 Docker DNS 实战

```bash
# 创建网络
docker network create --driver bridge my-net

# 启动服务
docker run -d --name db --network my-net postgres
docker run -d --name redis --network my-net redis
docker run -d --name api --network my-net my-api

# 在 api 容器内
docker exec -it api sh
/ $ nslookup db
# Server:    127.0.0.11
# Address:  127.0.0.11:53
# Non-authoritative answer:
# Name:  db
# Address: 172.18.0.2

/ $ getent hosts db
# 172.18.0.2      db

/ $ ping db
# PING db (172.18.0.2): 56 data bytes
```

### 7.2 别名 (Aliases)

```bash
# 一个容器有多个别名
docker run -d --name web \
  --network my-net \
  --network-alias frontend \
  --network-alias www \
  nginx

# 现在其他容器可用 web, frontend, www 访问
```

### 7.3 链接外部服务

```bash
# 容器内访问宿主服务
docker run -d --add-host=mydb.example.com:10.0.0.5 my-app
# my-app 容器内 mydb.example.com → 10.0.0.5

# 通过 host.docker.internal 访问宿主
docker run -d alpine
docker exec -it alpine wget host.docker.internal:8080
```

---

## 八、网络故障排查

### 8.1 排查工具

```bash
# 进入容器测试网络
docker run --rm -it --network my-net nicolaka/netshoot

# 工具包含:
# - ping, traceroute, mtr
# - nslookup, dig
# - curl, wget
# - iperf (带宽测试)
# - tcpdump (抓包)
# - nmap (端口扫描)

# 基础排查命令
docker exec -it <container> ping <target>
docker exec -it <container> nslookup <host>
docker exec -it <container> curl -v http://target
docker exec -it <container> netstat -tnlp
```

### 8.2 常见网络问题

```bash
# 问题 1: 容器间无法通信
# 排查:
docker network inspect <network>
# 检查所有容器是否在同一网络
docker network connect <network> <container>

# 问题 2: 端口无法从外部访问
# 排查:
docker port <container>      # 检查端口映射
sudo iptables -L -n -v        # 检查防火墙
ss -tlnp | grep <port>         # 监听检查

# 问题 3: DNS 解析失败
# 排查:
docker exec -it <container> cat /etc/resolv.conf
docker exec -it <container> nslookup <target>

# 问题 4: 性能问题 (延迟高)
# 排查:
docker network inspect <network>
# 确认 MTU 设置
docker exec -it <container> ip link show eth0
```

### 8.3 抓包调试

```bash
# 在容器内抓包
docker exec -it <container> apk add tcpdump
docker exec -it <container> tcpdump -i eth0 -w /tmp/capture.pcap

# 从容器外抓包 (宿主机)
sudo tcpdump -i docker0 -w capture.pcap

# 使用 netshoot
docker run --rm -it \
  --network container:<target> \
  --cap-add NET_ADMIN \
  --cap-add NET_RAW \
  nicolaka/netshoot tcpdump -i eth0
```

---

## 九、生产网络最佳实践

### 9.1 网络规划

```text
生产集群网络设计:

1. 多网络隔离
   - frontend 网络 (对外)
   - backend 网络 (内部服务)
   - database 网络 (数据库, 严格隔离)

2. 子网规划
   - 每个网络独立的 IP 段
   - 避免冲突

3. DNS 规划
   - 容器名规范 (service-name)
   - 不用 IP 通信
```

### 9.2 网络安全

```text
1. 最小化端口暴露
2. 使用网络隔离
3. 加密通信 (TLS)
4. 使用服务网格 (Istio, Linkerd)
5. 定期扫描镜像漏洞
6. 网络策略 (NetworkPolicy, K8s)
```

### 9.3 性能优化

```text
1. host 网络 (性能优先)
2. 自定义网桥 (避免 iptables)
3. macvlan/ipvlan (绕过 NAT)
4. SR-IOV (硬件加速)
5. CNI 插件 (Calico, Cilium)
```

---

## 核心要点速记

### 网络模式

```text
bridge    - 默认 NAT 模式, 容器间通过 IP
host      - 共享宿主网络, 性能最优
none      - 无网络
overlay   - Swarm 跨主机
macvlan   - 物理网卡虚拟
container - 共享另一个容器网络
```

### DNS 解析

```text
- 自定义网络: 容器名互通 ✅
- 默认 bridge (旧): 仅 IP 互通 ❌
- host.docker.internal: 访问宿主
- --add-host: 自定义 hosts
```

### 端口映射

```bash
docker run -p 8080:80 nginx     # -p 宿主:容器
docker run -p 53:53/udp dns     # 指定协议
docker run -P nginx             # 自动暴露 EXPOSE
```

### 网络排查

```bash
# 进入容器测试
docker run --rm -it --network <net> nicolaka/netshoot

# 关键命令
ping / nslookup / curl / netstat / tcpdump
```

### 选型决策

```text
生产默认 → 自定义 bridge + DNS
性能优先 → host
跨主机 → overlay (Swarm) / Calico / Flannel
传统网络 → macvlan
```

### 生产实践

```text
- 不用默认 bridge (用自定义)
- 不暴露不必要的端口
- 不同业务用不同网络
- 用 netshoot/nicolaka 容器调试
- 跨主机用 overlay / Calico
```

---

## 参考

- **Docker 网络**: https://docs.docker.com/network/
- **Bridge 驱动**: https://docs.docker.com/network/bridge/
- **Host 驱动**: https://docs.docker.com/network/host/
- **Overlay 驱动**: https://docs.docker.com/network/overlay/
- **netshoot 工具**: https://github.com/nicolaka/netshoot
