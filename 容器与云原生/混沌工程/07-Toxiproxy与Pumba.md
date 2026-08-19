# Toxiproxy 与 Pumba (网络与容器故障注入)

> 本章讲解 Toxiproxy (网络代理故障注入) 和 Pumba (容器混沌) 两个轻量级工具,它们在中间件测试场景中非常实用。

## 一、Toxiproxy 详解

### 1.1 项目简介

```text
项目:    Toxiproxy
官网:    https://github.com/Shopify/toxiproxy
维护:    Shopify
License: MIT
语言:    Go
当前版本: 2.9.x
```

### 1.2 核心特性

```text
1. 透明代理
   - 不需要修改应用
   - 部署在客户端和服务器之间

2. 丰富的网络故障
   - latency (延迟)
   - loss (丢包)
   - duplicate (重复)
   - corrupt (损坏)
   - bandwidth (带宽限制)
   - timeout (超时)
   - reset_peer (重置)
   - slow_close (慢关闭)
   - slicer (切片)

3. 集成友好
   - Go 客户端库
   - Java 客户端
   - Python 客户端
   - REST API
   - CLI (toxiproxy-cli)

4. 适用场景
   - 微服务测试
   - 数据库故障模拟
   - 网络分区
   - 性能降级
```

### 1.3 架构

```text
应用 ──→ Toxiproxy (代理) ──→ 真实服务
              ↓
        注入故障 (latency, loss, ...)

例:
应用 (localhost:20000) ──→ Toxiproxy ──→ Redis (localhost:6379)
                                ↓
                          注入 100ms 延迟
```

---

## 二、安装部署

### 2.1 Docker 部署 (推荐)

```bash
# 启动 Toxiproxy Server
docker run -d \
  --name toxiproxy \
  --restart always \
  -p 8474:8474 \
  -p 20000:20000 \
  -p 20001:20001 \
  shopify/toxiproxy:2.9.0

# 端口说明:
# 8474: Toxiproxy API
# 20000+: 用户自定义代理端口
```

### 2.2 二进制部署

```bash
# 下载
wget https://github.com/Shopify/toxiproxy/releases/download/v2.9.0/toxiproxy-server-2.9.0-linux-amd64
chmod +x toxiproxy-server-2.9.0-linux-amd64

# 启动
./toxiproxy-server -config toxiproxy.conf

# 配置文件
cat > toxiproxy.conf <<EOF
api.listenAddr = "0.0.0.0:8474"
EOF
```

### 2.3 toxiproxy-cli 安装

```bash
# 二进制
wget https://github.com/Shopify/toxiproxy/releases/download/v2.9.0/toxiproxy-cli-2.9.0-linux-amd64
chmod +x toxiproxy-cli-2.9.0-linux-amd64
mv toxiproxy-cli-2.9.0-linux-amd64 /usr/local/bin/toxiproxy-cli

# Mac
brew tap shopify/shopify && brew install toxiproxy-cli

# Docker
docker run --rm --network host shopify/toxiproxy-cli:2.9.0 \
  -h http://localhost:8474 ...
```

---

## 三、使用 Toxiproxy

### 3.1 创建代理

```bash
# 创建 MySQL 代理
toxiproxy-cli -h http://localhost:8474 \
  toxiproxy create -n mysql -l 0.0.0.0:20000 -u mysql:3306

# 创建 Redis 代理
toxiproxy-cli -h http://localhost:8474 \
  toxiproxy create -n redis -l 0.0.0.0:20001 -u redis:6379

# 创建 HTTP 代理
toxiproxy-cli -h http://localhost:8474 \
  toxiproxy create -n api -l 0.0.0.0:20002 -u api:8080

# 列出所有代理
toxiproxy-cli -h http://localhost:8474 list
```

### 3.2 添加故障 (Toxics)

#### 延迟 (latency)

```bash
# 添加 200ms 延迟
toxiproxy-cli -h http://localhost:8474 \
  toxic add -n mysql -t latency \
  -a latency=200 -a jitter=50

# 移除延迟
toxiproxy-cli -h http://localhost:8474 \
  toxic remove -n mysql -t latency
```

#### 丢包 (loss)

```bash
# 30% 丢包
toxiproxy-cli -h http://localhost:8474 \
  toxic add -n api -t loss -a probability=0.3

# 指定客户端
toxiproxy-cli -h http://localhost:8474 \
  toxic add -n api -t loss \
  -a probability=0.5 \
  -a attributes=client

# 指定服务端
toxiproxy-cli -h http://localhost:8474 \
  toxic add -n api -t loss \
  -a probability=0.5 \
  -a attributes=server
```

#### 重复 (duplicate)

```bash
# 20% 重复包
toxiproxy-cli -h http://localhost:8474 \
  toxic add -n api -t duplicate -a probability=0.2
```

#### 损坏 (corrupt)

```bash
# 25% 数据损坏
toxiproxy-cli -h http://localhost:8474 \
  toxic add -n api -t corrupt -a probability=0.25
```

#### 带宽限制 (bandwidth)

```bash
# 限制 1 Mbps
toxiproxy-cli -h http://localhost:8474 \
  toxic add -n api -t bandwidth -a rate=1024

# 限制 100 Kbps
toxiproxy-cli -h http://localhost:8474 \
  toxic add -n api -t bandwidth -a rate=100
```

#### 超时 (timeout)

```bash
# 连接超时
toxiproxy-cli -h http://localhost:8474 \
  toxic add -n api -t timeout -a timeout=5000

# 空闲超时
toxiproxy-cli -h http://localhost:8474 \
  toxic add -n api -t timeout -a timeout=30000
```

#### 重置连接 (reset_peer)

```bash
# TCP RST 重置
toxiproxy-cli -h http://localhost:8474 \
  toxic add -n api -t reset_peer -a timeout=1000
```

#### 慢关闭 (slow_close)

```bash
# 慢关闭连接
toxiproxy-cli -h http://localhost:8474 \
  toxic add -n api -t slow_close -a delay=5000
```

#### 切片 (slicer)

```bash
# 数据包切片
toxiproxy-cli -h http://localhost:8474 \
  toxic add -n api -t slicer -a average_size=64 -a size_variation=32
```

### 3.3 管理 Toxxics

```bash
# 列出所有 toxic
toxiproxy-cli -h http://localhost:8474 list

# 查看某个 proxy 的 toxic
toxiproxy-cli -h http://localhost:8474 toxic show -n mysql

# 移除 toxic
toxiproxy-cli -h http://localhost:8474 toxic remove -n mysql -t latency

# 启用/禁用 proxy
toxiproxy-cli -h http://localhost:8474 toxic enable -n mysql
toxiproxy-cli -h http://localhost:8474 toxic disable -n mysql

# 删除 proxy
toxiproxy-cli -h http://localhost:8474 toxic remove -n mysql
toxiproxy-cli -h http://localhost:8474 toxiproxy delete -n mysql
```

---

## 四、Toxiproxy 实战

### 4.1 Redis 慢响应测试

```bash
# 1. 创建 Redis 代理
toxiproxy-cli create -n redis -l 0.0.0.0:20001 -u redis:6379

# 2. 应用连接到 localhost:20001
# 修改应用配置: redis://localhost:20001

# 3. 添加 200ms 延迟
toxiproxy-cli toxic add -n redis -t latency \
  -a latency=200 -a jitter=50

# 4. 观察应用延迟
redis-cli -h localhost -p 20001 ping
# PONG (200ms+ 延迟)

# 5. 移除
toxiproxy-cli toxic remove -n redis -t latency
```

### 4.2 MySQL 主从切换测试

```bash
# 模拟主库故障
toxiproxy-cli toxic add -n mysql -t reset_peer -a timeout=1000
# 主库连接断开, 应用应自动重连从库

# 模拟从库延迟
toxiproxy-cli toxic add -n mysql-replica -t latency -a latency=5000
# 从库延迟 5s, 观察应用超时
```

### 4.3 API 降级测试

```bash
# 模拟下游服务 503
toxiproxy-cli toxic add -n api -t reset_peer -a timeout=500

# 模拟下游慢
toxiproxy-cli toxic add -n api -t latency -a latency=2000

# 模拟带宽限制
toxiproxy-cli toxic add -n api -t bandwidth -a rate=100
```

### 4.4 应用代码集成

```java
// Java 集成
import com.shopify.toxiproxy.ToxiproxyClient;
import com.shopify.toxiproxy.Toxic;

public class ChaosTest {
    public static void main(String[] args) {
        ToxiproxyClient client = new ToxiproxyClient("localhost", 8474);
        
        // 创建 proxy
        Proxy redisProxy = client.createProxy("redis", "localhost:20001:6379");
        
        // 添加 toxic
        Toxic latency = new Toxic();
        latency.setAttributes(Map.of(
            "latency", 100,
            "jitter", 10
        ));
        redisProxy.addToxic("latency", "latency", "downstream", latency);
        
        // 业务逻辑...
        
        // 清理
        redisProxy.removeToxic("latency");
        client.deleteProxy("redis");
    }
}
```

```python
# Python 集成
import toxiproxy
import time

proxy = toxiproxy.create('localhost', 8474)
redis = proxy.create('redis', '0.0.0.0:20001', 'redis:6379')

# 添加延迟
toxic = redis.add_toxic('latency', 'downstream',
    attributes={'latency': 200, 'jitter': 50})

# 业务测试
import redis
r = redis.Redis(host='localhost', port=20001)
r.ping()  # 会有 200ms 延迟

# 清理
redis.remove_toxic(toxic)
proxy.destroy()
```

---

## 五、Pumba 详解

### 5.1 项目简介

```text
项目:    Pumba
官网:    https://github.com/alexei-led/pumba
语言:    Go
License: Apache 2.0
```

### 5.2 核心特性

```text
1. 容器混沌
   - 杀容器
   - 暂停容器
   - 停止容器
   - 删除容器

2. 容器网络
   - 延迟
   - 丢包
   - 带宽限制
   - 丢包率

3. 容器命令
   - 发送任意命令
   - 修改资源限制

4. K8s 支持
   - 杀 Pod
   - 杀节点 Pod

5. 简单易用
   - 单二进制
   - Docker / K8s / Podman
```

### 5.3 安装

```bash
# 二进制
curl -L https://github.com/alexei-led/pumba/releases/download/0.10.0/pumba_linux_amd64 -o /usr/local/bin/pumba
chmod +x /usr/local/bin/pumba

# Docker 镜像
docker pull gaiaadm/pumba:latest
```

---

## 六、Pumba 使用

### 6.1 杀容器

```bash
# 杀指定容器
pumba kill my-container

# 杀 1 个匹配容器
pumba --random kill re2:5s "name=nginx"

# 杀 N% 容器
pumba --pattern "node.role=worker" kill re2:5s "node.role=worker" 5%

# 间隔杀 (持续 60s, 每 10s 杀一次)
pumba --interval 10s --time-limit 60s kill re2:5s "name=nginx"
```

### 6.2 暂停/停止容器

```bash
# 暂停 30s
pumba pause --time 30s re2:30s "name=nginx"

# 停止容器
pumba stop my-container

# 停止并重启
pumba stop --time 30s re2:30s "name=db"
```

### 6.3 网络故障

```bash
# 网络延迟 1s
pumba netem --duration 5m delay --time 1000 "name=nginx"

# 丢包 30%
pumba netem --duration 5m loss --percent 30 "name=nginx"

# 带宽限制
pumba netem --duration 5m rate --rate 1mbps "name=nginx"
```

### 6.4 K8s 杀 Pod

```bash
# 杀所有匹配 Pod
pumba k8s kill --kubeconfig ~/.kube/config "namespace=production,name=web"

# 间隔杀 Pod
pumba k8s kill --kubeconfig ~/.kube/config \
  --interval 1m --time-limit 30m \
  "namespace=production,name=web"
```

### 6.5 节点混沌

```bash
# 杀指定节点所有 Pod
pumba k8s kill --kubeconfig ~/.kube/config "node=node-1"

# 节点 CPU 满
pumba k8s node-cpu --kubeconfig ~/.kube/config \
  --stress-image polinux/stress \
  --stress-args "--cpu 4 --timeout 5m" "node=node-1"
```

### 6.6 Pumba vs ChaosBlade vs Chaos Mesh

| 工具 | K8s | Docker | 故障类型 | 易用性 |
|------|-----|--------|---------|--------|
| Pumba | ✓ | ✓ | 少 (杀 + 网络) | 简单 |
| ChaosBlade | ✓ | ✓ | 多 (40+) | 中等 |
| Chaos Mesh | ✓ | ✗ | 多 (12+) | 中等 |

---

## 七、实战案例

### 7.1 完整的数据库故障演练 (Toxiproxy + 脚本)

```bash
#!/bin/bash
# database-chaos.sh

PROXY="http://localhost:8474"

echo "=== 数据库故障演练 ==="

echo "1. 创建 MySQL 代理"
toxiproxy-cli -h $PROXY toxiproxy create \
  -n mysql -l 0.0.0.0:20000 -u mysql-real:3306

echo "2. 启动应用"
docker run -d \
  --name my-app \
  -e DB_URL=mysql://localhost:20000/mydb \
  my-app:1.0

echo "3. 等待应用启动"
sleep 30

echo "4. 验证应用正常"
curl -s http://my-app:8080/health
# {"status": "ok", "db": "connected"}

echo "5. 注入 500ms 延迟"
toxiproxy-cli -h $PROXY toxic add -n mysql -t latency \
  -a latency=500 -a jitter=100
sleep 60

echo "6. 观察业务指标"
curl -s http://my-app:8080/metrics | grep -E "db_latency|error_rate"

echo "7. 移除延迟"
toxiproxy-cli -h $PROXY toxic remove -n mysql -t latency

echo "8. 注入连接超时"
toxiproxy-cli -h $PROXY toxic add -n mysql -t timeout -a timeout=1000
sleep 30

echo "9. 移除所有 toxic"
toxiproxy-cli -h $PROXY toxic remove -n mysql -t timeout

echo "10. 清理"
toxiproxy-cli -h $PROXY toxiproxy delete -n mysql
docker stop my-app
docker rm my-app
```

### 7.2 微服务网络分区演练 (Pumba + ChaosBlade)

```bash
# 1. 网络分区
# 阻塞 service-a 和 service-b 之间
# 使用 iptables
iptables -A FORWARD -i eth0 -s service-a -d service-b -j DROP

# 2. 观察熔断
watch -n 1 "curl -s http://service-a:8080/metrics | grep circuit_breaker_state"

# 3. 解除分区
iptables -D FORWARD -i eth0 -s service-a -d service-b -j DROP
```

---

## 八、核心要点速记

### Toxiproxy 速记

```text
项目: Shopify
功能: 网络代理 + 故障注入
特点: 透明, 不改应用
故障: latency, loss, duplicate, corrupt, bandwidth, timeout
```

### Toxiproxy 命令

```bash
# 创建
toxiproxy-cli create -n NAME -l LISTEN -u UPSTREAM

# 添加故障
toxiproxy-cli toxic add -n NAME -t TYPE -a KEY=VALUE

# 移除故障
toxiproxy-cli toxic remove -n NAME -t TYPE

# 删除
toxiproxy-cli toxiproxy delete -n NAME
```

### Toxiproxy 故障类型

```text
latency     - 延迟
loss        - 丢包
duplicate   - 重复
corrupt     - 损坏
bandwidth   - 带宽限制
timeout     - 超时
reset_peer  - TCP RST
slow_close  - 慢关闭
slicer      - 数据包切片
```

### Pumba 速记

```text
项目: alexei-led/pumba
功能: 容器混沌
特点: 简单, 单二进制
故障: kill, pause, stop, 网络
```

### Pumba 命令

```bash
# 杀容器
pumba kill re2:5s "name=nginx"

# 暂停
pumba pause --time 30s re2:30s "name=nginx"

# 网络故障
pumba netem --duration 5m delay --time 1000 "name=nginx"

# K8s 杀 Pod
pumba k8s kill --kubeconfig ~/.kube/config "namespace=prod,name=web"
```

### 工具选型

```text
中间件网络故障:  Toxiproxy
简单容器混沌:   Pumba
全面 K8s 故障:   Chaos Mesh
主机 + 容器 + K8s: ChaosBlade
商业平台:        Gremlin
```

### 集成方式

```text
应用代码集成:
  - Java 客户端 (ToxiproxyClient)
  - Python 客户端 (toxiproxy)
  - Go 客户端 (原生)

CI/CD 集成:
  - 演练前: 创建 proxy
  - 演练中: 注入 toxic
  - 演练后: 清理 toxic + 删除 proxy
```

---

## 参考

- **Toxiproxy**: https://github.com/Shopify/toxiproxy
- **Toxiproxy 文档**: https://github.com/Shopify/toxiproxy/blob/master/README.md
- **Toxiproxy Server**: https://github.com/Shopify/toxiproxy/releases
- **Pumba**: https://github.com/alexei-led/pumba
- **Pumba 文档**: https://github.com/alexei-led/pumba/blob/master/README.md
- **Toxiproxy Java Client**: https://github.com/httptoolkit/toxiproxy-java
- **Toxiproxy Python Client**: https://github.com/ketami/toxiproxy-py
- **Shopify Engineering Blog**: https://shopify.engineering/

## 二、Gremlin 详解 (商业故障注入平台)
