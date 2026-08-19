# ChaosBlade 详解 (Alibaba Chaos Engineering Tool)

> ChaosBlade 是阿里开源的故障注入工具,支持主机、容器、K8s 多平台,中文文档齐全,故障类型丰富。

## 一、ChaosBlade 概述

### 1.1 项目简介

```text
项目:    ChaosBlade
官网:    https://chaosblade.io/
GitHub:  https://github.com/chaosblade-io/chaosblade
维护:    阿里云
License: Apache 2.0
当前版本: 1.7.x
```

### 1.2 核心特性

```text
1. 多平台支持
   - 主机级 (Linux)
   - 容器级 (Docker)
   - K8s 级 (Pod, Service, Node)

2. 故障类型丰富 (40+)
   - 基础: CPU, 内存, 磁盘, 网络
   - 应用: JVM, Dubbo, HTTP, MySQL, Redis, RocketMQ
   - K8s: Pod 杀, 网络, 节点

3. 中文文档
   - 国内开发, 中文为主
   - 阿里内部验证

4. 单二进制
   - blade 工具可独立使用
   - 轻量级

5. 多种执行方式
   - CLI 命令
   - chaosblade-box (K8s CRD)
   - chaosblade-operator
   - chaosblade-cloud (云)

6. 集成友好
   - Prometheus 指标
   - Grafana Dashboard
   - 与 AHAS 集成
```

---

## 二、安装

### 2.1 系统要求

```text
- Linux 3.10+ 内核
- x86_64 / ARM64
- 容器运行时 (Docker, containerd, CRI-O)
- K8s 1.16+
```

### 2.2 下载安装

```bash
# 1. 下载 (Linux)
wget https://chaosblade.oss-cn-hangzhou.aliyuncs.com/release/latest/chaosblade-1.7.2-linux64.tar.gz

# 2. 解压
tar -xzf chaosblade-1.7.2-linux64.tar.gz
cd chaosblade

# 3. 设置环境变量
echo 'export PATH=$PATH:/path/to/chaosblade/bin' >> ~/.bashrc
source ~/.bashrc

# 4. 验证
blade -h
```

### 2.3 Docker 镜像

```bash
# 拉取镜像
docker pull chaosbladeio/chaosblade-tool:1.7.2

# 使用
docker run -it --rm \
  -v /var/run/docker.sock:/var/run/docker.sock \
  --privileged \
  chaosbladeio/chaosblade-tool:1.7.2 \
  blade -h
```

---

## 三、CLI 基础

### 3.1 blade 命令结构

```text
blade [command] [sub-command] [options] [arguments]

# command: create, destroy, status, list, revoke, server, jvm
# sub-command: cpu, mem, network, disk, process, k8s, redis, mysql, ...

# 示例
blade create cpu fullload
blade create k8s pod-kill --namespace default --names nginx
blade create network delay --time 3000 --interface eth0
```

### 3.2 全局选项

```bash
blade --help
# 全局选项:
#   -d, --debug    debug 模式
#   -h, --help     帮助
#   -n, --no       不创建实验, 只演练
#   -y, --yes      跳过确认

# 子命令帮助
blade create cpu --help
```

### 3.3 核心命令

```bash
# create: 创建实验
blade create cpu fullload

# destroy: 销毁实验
blade destroy <UID>

# status: 查看实验状态
blade status <UID>

# list: 列出实验
blade list --type=create

# revoke: 撤销实验
blade revoke <UID>

# server: 启动 agent (用于 K8s)
blade server start
```

---

## 四、主机级故障注入

### 4.1 CPU 故障

```bash
# CPU 满载 (单核)
blade create cpu fullload

# CPU 满载 (3 核)
blade create cpu fullload --cpu-count 3

# CPU 占用 80%
blade create cpu usage --usage 80

# 指定进程
blade create cpu fullload --process nginx

# 指定进程 PID
blade create cpu fullload --pid 1234

# 持续 60 秒
blade create cpu fullload --timeout 60
```

### 4.2 内存故障

```bash
# 占用 500M 内存
blade create mem load --size 500

# 占用 1G 内存
blade create mem load --size 1024

# 申请 + 保留
blade create mem load --size 1024 --reserve

# 内存满
blade create mem ramload

# OOM
blade create mem oom
```

### 4.3 磁盘故障

```bash
# 磁盘读 IO 压力
blade create disk burn --read

# 磁盘写 IO 压力
blade create disk burn --write

# 磁盘填满
blade create disk fill --size 10000   # 10 GB

# 占用目录
blade create disk fill --path /tmp --size 1000
```

### 4.4 网络故障

```bash
# 网络延迟
blade create network delay --time 3000 --interface eth0
# --time: 延迟毫秒

# 延迟 200ms
blade create network delay --time 200 --interface eth0

# 网络丢包
blade create network loss --percent 30 --interface eth0
# 30% 丢包率

# 网络重复
blade create network duplicate --percent 50 --interface eth0

# 网络乱序
blade create network reorder --percent 40 --interface eth0

# 网络损坏
blade create network corrupt --percent 20 --interface eth0

# DNS 故障
blade create network dns --domain www.example.com --ip 127.0.0.1

# 带宽限制
blade create network rate --rate 1mbps --interface eth0
```

### 4.5 进程故障

```bash
# 杀进程
blade create process kill --process nginx

# 杀进程 (按 PID)
blade create process kill --pid 1234

# 杀进程 (按命令行)
blade create process kill --cmd "python app.py"

# 挂起进程
blade create process stop --process mysql

# 常见进程名
blade create process kill --process "java,python,redis-server"
```

---

## 五、应用层故障注入

### 5.1 Redis 故障

```bash
# Redis 连接延迟
blade create redis delay --addr 10.0.0.10:6379 --time 1000

# Redis 满 (内存满)
blade create redis full --addr 10.0.0.10:6379

# Redis 缓存击穿 (大量请求打 DB)
blade create redis hotspot --addr 10.0.0.10:6379

# Redis 断连
blade create redis disconnect --addr 10.0.0.10:6379
```

### 5.2 MySQL 故障

```bash
# MySQL 慢查询
blade create mysql delay --addr 10.0.0.11:3306 --time 5000

# MySQL 满 (连接数)
blade create mysql full --addr 10.0.0.11:3306

# MySQL 断连
blade create mysql disconnect --addr 10.0.0.11:3306
```

### 5.3 HTTP 故障

```bash
# HTTP 慢响应
blade create http delay --url http://api.example.com --time 5000

# HTTP 错误返回
blade create http error --url http://api.example.com --code 500

# HTTP 503
blade create http error --url http://api.example.com --code 503
```

### 5.4 RocketMQ 故障

```bash
# RocketMQ 延迟
blade create rocketmq delay --addr 10.0.0.12:9876 --time 3000

# RocketMQ 异常
blade create rocketmq exception --addr 10.0.0.12:9876
```

### 5.5 Dubbo 故障

```bash
# Dubbo 调用延迟
blade create dubbo delay --service com.example.UserService --method getUser --time 2000

# Dubbo 调用异常
blade create dubbo exception --service com.example.UserService --method getUser
```

### 5.6 JVM 故障

```bash
# JVM OOM
blade create jvm OOM

# JVM 死锁
blade create jvm deadlock --area method

# JVM CPU 满
blade create jvm cpufullload

# 指定进程
blade create jvm OOM --area HEAP
blade create jvm OOM --area STACK
```

---

## 六、Docker 故障注入

```bash
# 杀容器
blade create docker kill --container-id abc123
# 或
blade create docker kill --container-name nginx

# 暂停容器
blade create docker pause --container-name nginx

# 取消暂停
blade create docker unpause --container-name nginx

# 容器 CPU 压力
blade create docker cpu --cpu-count 2 --container-id abc123

# 删除容器 (Kubernetes 中 Pod 杀)
blade create docker rm --container-name nginx

# 容器网络延迟
blade create docker network delay --time 2000 --container-name nginx
```

---

## 七、K8s 故障注入

### 7.1 PodChaos

```bash
# 杀 Pod
blade create k8s pod-kill --namespace default --names nginx-pod

# 杀所有 nginx Pod
blade create k8s pod-kill --namespace production --label app=nginx

# 杀 N% 的 Pod
blade create k8s pod-kill --namespace production --label app=nginx --percent 30

# 杀 1 个
blade create k8s pod-kill --namespace production --count 1

# 容器故障
blade create k8s container-kill --namespace default --names nginx-pod --container-names nginx

# Pod 启动失败
blade create k8s pod-failure --namespace default --names nginx-pod

# 容器启动慢
blade create k8s container-failure --namespace default --names nginx-pod
```

### 7.2 NodeChaos

```bash
# 节点 CPU 满
blade create k8s node-cpu --node node-1 --cpu-count 4

# 节点网络延迟
blade create k8s node-network --node node-1 --network-type delay --time 1000

# 节点丢包
blade create k8s node-network --node node-1 --network-type loss --percent 30

# K8s API 故障 (生产慎用)
blade create k8s api-server-failure --kubeconfig /root/.kube/config
```

### 7.3 NetworkChaos (K8s)

```bash
# Pod 网络延迟
blade create k8s pod-network --namespace production --names nginx-pod --network-type delay --time 1000

# Pod 网络丢包
blade create k8s pod-network --namespace production --names nginx-pod --network-type loss --percent 30

# Pod 网络分区
blade create k8s pod-network --namespace production --names nginx-pod --network-type partition

# Service 故障
blade create k8s service-account
```

### 7.4 StressChaos (K8s)

```bash
# Pod CPU 压力
blade create k8s pod-cpu --namespace production --names nginx-pod --cpu-percent 80

# Pod 内存压力
blade create k8s pod-mem --namespace production --names nginx-pod --mem-size 512
```

### 7.5 销毁实验

```bash
# 销毁指定实验
blade destroy <UID>

# 销毁所有实验
blade list --type create
blade destroy <UID>  # 一个个销毁
```

---

## 八、实战案例

### 8.1 Redis 主节点故障演练

```bash
# 1. 演练前状态记录
redis-cli -h redis-master INFO replication | head -10
redis-cli -h redis-replica1 INFO replication | head -10

# 2. 启动 Redis 故障 (模拟延迟)
blade create redis delay \
  --addr 192.168.1.10:6379 \
  --time 3000  # 3 秒延迟
  --timeout 300  # 持续 5 分钟

# 3. 演练中观察
# 主从延迟
redis-cli -h redis-replica1 INFO replication | grep -E "master_link|repl_offset"

# 业务影响
curl -s http://api:8080/metrics | grep -E "redis_latency|error_rate"

# 4. 销毁
blade destroy <UID>

# 5. 演练后分析
# 报告: 复制延迟 X ms, 业务错误率 Y%
```

### 8.2 Pod 杀演练 (K8s)

```bash
# 1. 演练前
kubectl get pod web-1 -o wide
curl http://web-1:8080/health  # 200

# 2. 启动演练
blade create k8s pod-kill \
  --kubeconfig ~/.kube/config \
  --namespace production \
  --names web-1 \
  --timeout 60s

# 3. 演练中观察
# 滚动更新是否触发?
kubectl get pod web-* -w

# 流量切换
kubectl get svc web -o yaml | grep -A 5 endpoints

# 4. 销毁
blade list --type create | grep pod-kill
blade destroy <UID>

# 5. 报告
# - 杀 Pod 到恢复时间: X 秒
# - 业务影响: Y 秒中断
# - 副本数: 始终 3
```

### 8.3 数据库慢响应演练

```bash
# 1. 标记目标
MYSQL_SERVER=10.0.0.11

# 2. 启动慢响应
blade create mysql delay \
  --addr $MYSQL_SERVER:3306 \
  --time 3000 \
  --timeout 10m

# 3. 业务侧观察
# 应用超时率
# 数据库连接池使用
# 慢查询日志

# 4. 销毁
blade list --type create
blade destroy <UID>
```

---

## 九、chaosblade-box (K8s CRD)

### 9.1 概述

```text
chaosblade-box 是 ChaosBlade 的 K8s CRD 形式
类似 Chaos Mesh 的使用方式
通过 kubectl apply -f 创建实验
```

### 9.2 PodChaos CRD

```yaml
apiVersion: chaosblade.io/v1alpha1
kind: PodChaos
metadata:
  name: chaosblade-pod-kill
  namespace: chaosblade
spec:
  experiments:
  - scope: pod
    target: pod-kill
    action: pod-kill
    namespaces:
    - production
    labelSelectors:
      app: nginx
    duration: 30s
```

### 9.3 NetworkChaos CRD

```yaml
apiVersion: chaosblade.io/v1alpha1
kind: NetworkChaos
metadata:
  name: chaosblade-net-delay
  namespace: chaosblade
spec:
  experiments:
  - scope: pod
    target: network
    action: delay
    namespaces:
    - production
    labelSelectors:
      app: nginx
    delay:
      time: 1000
      offset: 0
    duration: 5m
```

---

## 十、监控与告警

### 10.1 Prometheus 指标

```bash
# 启用 Prometheus 指标
blade server start --prometheus :9000

# 指标路径
http://<host>:9000/metrics
```

```promql
# 实验创建次数
chaosblade_experiment_total{action="pod-kill",target="pod"}

# 实验执行中
chaosblade_experiment_active

# 实验失败次数
chaosblade_experiment_failure_total
```

### 10.2 与 AHAS 集成

```text
AHAS (Application High Availability Service):
- 阿里云高可用服务
- 集成 ChaosBlade
- 流量防护 + 故障演练 + 监控
- 阿里云最佳实践
```

---

## 十一、安全与最佳实践

### 11.1 风险控制

```text
1. 小范围开始
   - 单实例 → 部分 → 全部
   - 短时 → 持续

2. 业务低峰期
   - 避免高峰
   - 节假日除外

3. 准备回滚
   - 记录实验 UID
   - 一键 destroy

4. 团队就位
   - 通知相关方
   - 监控值班

5. 实验记录
   - 实验报告
   - 发现问题跟踪
```

### 11.2 命令速查表

```bash
# 基础
blade create cpu fullload --cpu-count 4
blade create mem load --size 1024
blade create network delay --time 1000
blade create disk fill --size 5000

# 进程
blade create process kill --process nginx
blade create process stop --process mysql

# 应用
blade create redis delay --addr 10.0.0.10:6379
blade create mysql delay --addr 10.0.0.11:3306
blade create jvm OOM

# K8s
blade create k8s pod-kill --namespace default --names nginx
blade create k8s pod-network --namespace default --names nginx --network-type delay

# 管理
blade status <UID>
blade list --type create
blade destroy <UID>
```

### 11.3 核心要点速记

```text
工具: ChaosBlade (阿里)
平台: 主机 / Docker / K8s
故障: 40+ 种
文档: 中文
License: Apache 2
特点: 一条命令注入故障
```

---

## 参考

- **ChaosBlade 官方**: https://chaosblade.io/
- **GitHub**: https://github.com/chaosblade-io/chaosblade
- **中文文档**: https://chaosblade.io/docs/
- **示例**: https://github.com/chaosblade-io/chaosblade/tree/master/examples
- **chaosblade-box**: https://github.com/chaosblade-io/chaosblade-box
- **AHAS 集成**: https://help.aliyun.com/document_detail/181863.html
- **CNCF Landscape**: https://landscape.cncf.io/

## 二、Toxiproxy 详解 (Network Fault Injection)
