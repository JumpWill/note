# Redis 概述与安装

## 一、Redis 简介

### 1.1 什么是 Redis

**Redis**（**Re**mote **Di**ctionary **S**erver）是一个开源的、基于内存的**键值存储系统**，可用作数据库、缓存、消息中间件和流式引擎。它支持多种数据结构（String、Hash、List、Set、Sorted Set、Bitmap、HyperLogLog、GEO、Stream 等），并提供了丰富的命令、事务、脚本（Lua）、发布/订阅、管道、模块化扩展等能力。

**核心定位**：

- 属于 **NoSQL** 中的 **键值（Key-Value）** 类型
- 数据主要驻留**内存**，可按需落地到磁盘（RDB / AOF）
- 由 **Salvatore Sanfilippo**（网名 antirez）开发，最初为解决 LLOOGG 实时日志分析的高性能需求而设计
- 遵循 **BSD 三条款许可证**，可自由用于商业项目
- 当前由 **Redis Ltd.**（原 Redis Labs）公司主导维护，社区与商业并行

### 1.2 发展历史

```text
┌───────────────────────────────────────────────────────────────┐
│ 2009   Salvatore Sanfilippo（antirez）开发首个版本           │
│        初衷是为 LLOOGG 提供高性能实时日志分析                │
│   ↓                                                           │
│ 2010   Redis 2.0 发布,新增 List/Set 高级命令                  │
│   ↓                                                           │
│ 2011   Redis 2.2,加入 Lua 脚本                                │
│   ↓                                                           │
│ 2012   Redis 2.4,加入虚拟机(VM)及主从复制改进                 │
│   ↓                                                           │
│ 2013   VMware 赞助 antirez;Redis 2.6(脚本、bitmaps)           │
│   ↓                                                           │
│ 2014   Redis 2.8,引入 Sentinel 高可用                          │
│   ↓                                                           │
│ 2015   Redis 3.0,正式发布 **Cluster**(官方分布式方案)         │
│   ↓                                                           │
│ 2017   Redis 4.0,引入 **Module** 机制(Redis Stack 前身)       │
│   ↓                                                           │
│ 2018   Redis 5.0,引入 **Stream** 数据结构                     │
│   ↓                                                           │
│ 2020   Redis 6.0,多线程 IO、ACL、客户端缓存                   │
│   ↓                                                           │
│ 2021   Redis 6.2 / 7.0 RC,Redis Stack 整合 RediSearch 等模块 │
│   ↓                                                           │
│ 2022   Redis 7.0 GA,Function、Multi-part AOF、Redis Stack 7  │
│   ↓                                                           │
│ 2023   Redis 7.2 / 7.4,持续优化(命令合并、shard 负载均衡)   │
│   ↓                                                           │
│ 2024+  Redis 8.0 路线图,Vector Set、AI 模块等新探索            │
└───────────────────────────────────────────────────────────────┘
```

### 1.3 版本演进与现状

| 版本   | 发布时间 | 主要特性                                                                | 状态         |
|--------|----------|-------------------------------------------------------------------------|--------------|
| 1.0    | 2009     | 首个公开版本,基本 KV、过期                                              | 历史版本     |
| 2.x    | 2010-2014 | Lua 脚本、Bitmap、Sentinel、复制完善                                    | 已淘汰       |
| 3.0    | 2015     | **Cluster** GA,分布式方案落地                                            | 仍广泛使用   |
| 3.2    | 2016     | GEO、Bitfield、`MIGRATE` 命令优化                                        | 历史版本     |
| 4.0    | 2017     | Module 机制、PSYNC2 改进、混合 RDB+AOF                                  | 历史版本     |
| 5.0    | 2018     | **Stream** 数据类型、改进的 Active Defragmenter、RESP3               | 仍广泛使用   |
| 6.0    | 2020     | 多线程 IO(写入仍单线程)、ACL、客户端缓存(Tracking)                  | 主流生产版本 |
| 6.2    | 2021     | 性能优化、命令改进、Bitfield 增强                                        | 主流生产版本 |
| 7.0    | 2022     | Function(脚本库)、Multi-part AOF、`CLIENT NO-EVICT`                   | 推荐生产     |
| 7.2    | 2023     | 命令速度优化、`EXPIREAT` 精度优化                                       | 推荐生产     |
| 7.4    | 2024     | 新 Hash、ZSet 编码(`listpack`),性能进一步提升                          | 推荐生产     |
| 8.x    | 2025+    | Vector Set、AI 集成(RedisVL)、更多模块                                  | 新版本       |

> **版本选择建议**：生产环境推荐 **Redis 7.2 / 7.4**(7.x 系列稳定性与性能最佳平衡)。Redis 6.x 在多客户端 IO 场景下也广泛使用。5.x 及更早版本因缺乏 Streams 与较新 Module,逐渐被替换。

### 1.4 Redis 与 Redis Stack

**Redis Stack** 是 Redis Ltd. 提供的一站式发行版,在 Redis 基础上集成了多个常用模块：

| 模块          | 功能                                            | 适用场景                       |
|---------------|-------------------------------------------------|--------------------------------|
| RediSearch    | 全文检索、二级索引、向量检索                     | 搜索、推荐系统                 |
| RedisJSON     | 原生 JSON 数据类型与路径查询                    | 文档型数据                     |
| RedisGraph    | 图数据库(基于 Cypher)                          | 关系网络分析                   |
| RedisTimeSeries | 时序数据存储与聚合                             | 监控、IoT、金融时序           |
| RedisBloom    | Bloom、CMS、TopK、TDigest 概率结构             | 去重、近似统计                 |
| RedisGears    | 函数式编程框架(已被 Function 替代一部分)       | 数据处理管道                   |

> 如果仅使用核心 KV + Stream + Lua,使用官方 `redis` 包即可;若需 RediSearch / RedisJSON 等模块能力,可使用 `redis/redis-stack-server` 镜像或 Redis Stack 安装包。

### 1.5 Redis 的特点

| 维度       | 说明                                                                            |
|------------|---------------------------------------------------------------------------------|
| 高性能     | 单节点读 10w+ QPS,写 8w+ QPS(基于内存 + 高效 IO 多路复用)                    |
| 数据结构   | String、Hash、List、Set、ZSet、Bitmap、HyperLogLog、GEO、Stream(共 9 大类)  |
| 持久化     | RDB 快照 + AOF 日志,支持混合持久化(RDB+AOF,7.x)                              |
| 高可用     | **Sentinel**(主从 + 自动故障转移) / **Cluster**(分布式 + 水平扩展)             |
| 事务       | MULTI/EXEC(非原子回滚)、Lua 脚本(原子执行)                                  |
| 复制       | 主从异步复制、`REPLICAOF`、`PSYNC2` 部分重同步                               |
| 集群       | 16384 槽位、Gossip 协议、客户端智能路由(支持 MOVED / ASK 重定向)             |
| 安全       | ACL(6.0+)、AUTH 密码、TLS 加密、protected-mode                              |
| 多语言     | 官方支持 C / Java / Python / Go / Node.js / .NET / PHP 等近 100 种客户端    |
| 模块化     | Module API 允许 C/Rust 扩展,Redis Stack 集成多个官方模块                      |
| 单线程核心 | **命令执行**单线程(避免锁开销),6.0+ IO 多线程(网络读写可多线程)            |

---

## 二、Redis 与其他缓存/存储对比

### 2.1 vs Memcached

| 维度       | Redis                       | Memcached                    |
|------------|-----------------------------|------------------------------|
| 数据结构   | 多种(9 类)                  | 仅 KV(String)                |
| 持久化     | RDB / AOF                   | 无(纯内存,重启即失)         |
| 集群       | 原生 Cluster / Sentinel     | 一致性哈希,客户端分片       |
| 线程模型   | 命令单线程,IO 可多线程      | 完全多线程                   |
| 内存管理   | 支持 lazy free 与主动释放   | Slab 分配                    |
| 适用场景   | 缓存、计数器、限流、队列、Session | 纯 KV 缓存(纯读场景)        |

> 若仅需要**纯 KV 缓存**,Memcached 在某些纯读场景吞吐略高;但需要**数据结构**或**持久化**时,Redis 优势明显。

### 2.2 vs Ehcache(Java 内置缓存)

| 维度       | Redis                | Ehcache                    |
|------------|----------------------|----------------------------|
| 部署形态   | 独立进程(网络访问)  | JVM 内嵌(本地)            |
| 多实例共享 | 天然支持             | 需 RMI / JGroup 集群       |
| 持久化     | RDB / AOF           | disk store(本地磁盘)      |
| 性能       | 网络 IO 略慢         | 本地访问更快               |
| 适用       | 多服务共享缓存       | 单 JVM 应用本地缓存        |

### 2.3 vs Caffeine(Java 进程内缓存)

| 维度       | Redis                          | Caffeine                    |
|------------|--------------------------------|-----------------------------|
| 位置       | 独立进程                       | JVM 进程内                  |
| 一致性     | 多实例天然共享                 | 仅本地,需 L2 配合           |
| 功能       | 丰富(Pub/Sub、Lua、Stream)   | Window/LFU 淘汰策略         |
| 性能       | 网络 IO 微秒级                 | 纳秒级                      |
| 适用       | 分布式共享缓存                 | JVM 内热点缓存,与 Redis 组成 L1+L2 |

> **L1 + L2 多级缓存** 模式:进程内 Caffeine(L1) + 跨进程 Redis(L2),可显著降低 Redis 压力。

### 2.4 vs Aerospike(企业级 NoSQL)

| 维度       | Redis                  | Aerospike                      |
|------------|------------------------|--------------------------------|
| 数据结构   | 丰富(9 类)            | KV + 二级索引 + UDF            |
| 存储介质   | 内存 + 磁盘            | 内存/SSD/混合                  |
| 一致性     | 异步复制,最终一致      | 强一致可选                     |
| 集群       | Cluster(16384 槽)    | 自动分区 + 智能迁移             |
| 适用       | 通用缓存、消息、计数   | 海量 KV、低延迟、广告/风控      |

### 2.5 总览表

| 产品        | 类型       | 数据结构 | 持久化 | 分布式       | 典型场景                       |
|-------------|------------|----------|--------|--------------|--------------------------------|
| Redis       | 内存 KV    | 极丰富   | RDB/AOF | Cluster/Sentinel | 通用缓存、限流、计数器、消息队列 |
| Memcached   | 内存 KV    | 仅 String | 无     | 客户端哈希   | 纯读缓存                       |
| Ehcache     | Java 嵌入  | 较丰富   | 磁盘   | RMI 集群     | 单 JVM 应用                    |
| Caffeine    | Java 进程内| KV       | 无     | 仅本地       | JVM 内热点                     |
| Aerospike   | 内存/SSD  | KV       | SSD    | 原生         | 海量 KV、低延迟                |

---

## 三、安装方式

Redis 提供 **4 种主要安装方式**：源码编译、包管理器、Docker、macOS Homebrew。

### 3.1 源码编译安装(高级/自定义)

```bash
# 1. 安装编译依赖
yum install -y gcc make tcl         # RHEL/CentOS
apt install -y build-essential tcl  # Debian/Ubuntu

# 2. 下载源码(以 7.4 为例)
wget https://download.redis.io/releases/redis-7.4.1.tar.gz

# 3. 解压
tar -xzf redis-7.4.1.tar.gz
cd redis-7.4.1

# 4. 编译(make)
make                                    # 单线程编译
make -j$(nproc) BUILD_TLS=yes MALLOC=libc   # 多线程 + TLS + libc 分配器
# 常见 MALLOC 选项:libc(默认)、jemalloc(更优)

# 5. 测试(可选,耗时长)
make test

# 6. 安装(make install),默认装到 /usr/local/bin
make install PREFIX=/usr/local/redis

# 7. 复制配置
cp redis.conf /usr/local/redis/

# 8. 创建数据/日志目录
mkdir -p /var/lib/redis /var/log/redis
```

**编译选项**：

| 参数             | 作用                                  |
|------------------|---------------------------------------|
| `MALLOC=libc`    | 使用 libc(默认)                       |
| `MALLOC=jemalloc`| 使用 jemalloc,减少内存碎片(生产推荐)  |
| `BUILD_TLS=yes`  | 启用 TLS(需 OpenSSL 开发包)          |
| `USE_SYSTEMD=yes`| 启用 systemd notify 支持              |

### 3.2 包管理器安装(推荐入门)

#### 3.2.1 Debian/Ubuntu(使用 apt)

```bash
# 1. 添加 Redis 官方源
curl -fsSL https://packages.redis.io/gpg | sudo gpg --dearmor -o /usr/share/keyrings/redis-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/redis-archive-keyring.gpg] https://packages.redis.io/deb $(lsb_release -cs) main" \
  | sudo tee /etc/apt/sources.list.d/redis.list

# 2. 更新并安装
sudo apt update
sudo apt install redis

# 3. 启动
sudo systemctl start redis-server
sudo systemctl enable redis-server

# 4. 验证
redis-cli ping
# 输出: PONG
```

#### 3.2.2 RHEL/CentOS/Rocky(使用 yum/dnf)

```bash
# 1. 添加 EPEL + Redis 源
sudo dnf install epel-release
sudo dnf install https://packages.redis.io/rpm/redis.repo -y

# 或:从 Remi 仓库安装
sudo dnf install redis

# 2. 启动
sudo systemctl start redis
sudo systemctl enable redis
```

> **包管理器安装的特点**：自动创建 `redis` 用户、自动生成 `/etc/redis/redis.conf`、自动注册 systemd 服务,但版本可能滞后于官方最新。

### 3.3 Docker 安装(开发/CI 推荐)

```bash
# 1. 拉取官方镜像
docker pull redis:7.4-alpine

# 2. 启动容器
docker run -d \
  --name redis7 \
  -p 6379:6379 \
  -v /data/redis:/data \
  -v /etc/redis/redis.conf:/usr/local/etc/redis/redis.conf \
  redis:7.4-alpine \
  redis-server /usr/local/etc/redis/redis.conf

# 3. 进入容器测试
docker exec -it redis7 redis-cli ping

# 4. 查看日志
docker logs -f redis7
```

**docker-compose.yml**：

```yaml
version: '3.8'
services:
  redis:
    image: redis:7.4-alpine
    container_name: redis7
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
      - ./conf/redis.conf:/usr/local/etc/redis/redis.conf
    command: redis-server /usr/local/etc/redis/redis.conf
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3

volumes:
  redis_data:
```

### 3.4 macOS Homebrew 安装

```bash
# 安装(会自动启动 brew services)
brew install redis

# 启动(前台)
redis-server /usr/local/etc/redis.conf     # Intel Mac
redis-server /opt/homebrew/etc/redis.conf  # Apple Silicon

# 后台服务(开机自启)
brew services start redis

# 停止
brew services stop redis

# 查看版本
redis-cli --version
```

### 3.5 安装方式对比

| 方式         | 难度 | 升级   | 性能             | 适合场景                     |
|--------------|------|--------|------------------|------------------------------|
| 源码编译     | ★★★  | ★      | 可深度调优       | 定制、嵌入式、深度优化       |
| apt/yum      | ★    | ★★★    | 标准             | 入门、桌面、CI               |
| Docker       | ★    | ★★★    | 接近原生         | 开发、测试、CI、容器化生产   |
| Homebrew     | ★    | ★★     | 标准             | macOS 本地开发               |

---

## 四、目录结构与可执行文件

### 4.1 默认路径

| 安装方式       | 二进制目录           | 配置目录              | 数据目录       |
|----------------|----------------------|-----------------------|----------------|
| 源码安装       | /usr/local/redis/bin | /usr/local/redis      | /var/lib/redis |
| apt (Debian)   | /usr/bin             | /etc/redis            | /var/lib/redis |
| yum (RHEL)     | /usr/bin             | /etc                  | /var/lib/redis |
| Docker         | /usr/local/bin       | /usr/local/etc/redis  | /data          |
| Homebrew       | /usr/local/bin 或 /opt/homebrew/bin | /usr/local/etc/redis 或 /opt/homebrew/etc/redis | /usr/local/var/redis |

### 4.2 主要可执行文件

```text
/usr/local/redis/bin/                (源码安装示例)
├── redis-server                    主服务进程(必须)
├── redis-cli                       命令行客户端(必须)
├── redis-benchmark                 性能压测工具
├── redis-check-aof                 AOF 文件检查/修复
├── redis-check-rdb                 RDB 文件检查
├── redis-sentinel                  Sentinel 高可用进程
├── redis-cluster                   Cluster 集群管理(7.0+已并入 redis-cli)
└── redis-stack-*                   (Redis Stack 模块可选工具)
```

**各工具作用**：

| 程序                | 用途                                                       |
|---------------------|------------------------------------------------------------|
| `redis-server`      | 启动 Redis 实例,加载 redis.conf                           |
| `redis-cli`         | 命令行客户端,几乎所有管理操作入口                         |
| `redis-benchmark`   | 压测 QPS / 延迟(`redis-benchmark -n 100000 -c 50`)        |
| `redis-check-aof`   | 检查 AOF 文件完整性,修复 `redis-check-aof --fix appendonly.aof` |
| `redis-check-rdb`   | 检查 RDB 文件,显示元信息                                  |
| `redis-sentinel`    | Sentinel 高可用监控进程(端口 26379)                      |

---

## 五、启动与停止

### 5.1 启动方式选择流程

```text
┌─────────────────────────────────────────────────────────┐
│                 Redis 启动方式选择                         │
│                                                         │
│  系统使用 systemd? ───── Yes ─→ systemctl start redis    │
│         │                                                │
│         No                                              │
│         ↓                                                │
│  需要自定义启动脚本? ── Yes ─→ redis-server /path/redis.conf &
│         │                                                │
│         No                                              │
│         ↓                                                │
│  直接前台启动 redis-server(调试用)                      │
└─────────────────────────────────────────────────────────┘
```

### 5.2 启动方式对比表

| 方式                      | 命令                                        | 适用场景           |
|---------------------------|---------------------------------------------|--------------------|
| **前台启动**              | `redis-server`                              | 调试、看日志       |
| **前台启动指定配置**      | `redis-server /path/redis.conf`             | 调试、容器内       |
| **守护进程模式**          | `redis-server --daemonize yes`              | 无 systemd 环境    |
| **systemd**               | `systemctl start redis`                     | 生产主流           |
| **brew services**(macOS) | `brew services start redis`                 | macOS 本地         |
| **Docker**                | `docker run redis`                          | 容器化部署         |

### 5.3 前台启动(调试)

```bash
# 1. 最简单启动(默认 6379 端口,无配置)
redis-server

# 2. 指定配置文件
redis-server /etc/redis/redis.conf

# 3. 指定端口和配置覆盖
redis-server --port 6380 --daemonize no --logfile ""

# 4. 启动时打印详细日志(VERY VERBOSE)
redis-server --loglevel debug
```

### 5.4 守护进程方式(后台)

```bash
# 1. 命令行参数
redis-server /etc/redis/redis.conf --daemonize yes

# 2. 修改配置文件中 daemonize
# redis.conf 中:
daemonize yes
pidfile /var/run/redis_6379.pid
logfile /var/log/redis/redis.log

# 3. 启动
redis-server /etc/redis/redis.conf

# 4. 查看 PID
cat /var/run/redis_6379.pid
```

### 5.5 systemd 方式(生产主流)

```bash
# 启动
sudo systemctl start redis

# 停止
sudo systemctl stop redis

# 重启
sudo systemctl restart redis

# 重新加载部分配置(运行时可改的参数)
sudo systemctl reload redis

# 状态
sudo systemctl status redis

# 开机自启
sudo systemctl enable redis

# 取消自启
sudo systemctl disable redis

# 实时跟踪日志
journalctl -u redis -f
```

**systemd 单元文件位置**：

- RHEL/CentOS：`/usr/lib/systemd/system/redis.service`
- Debian/Ubuntu：`/lib/systemd/system/redis-server.service`

### 5.6 优雅停止

```bash
# 方式 1:redis-cli 优雅关闭(推荐)
redis-cli shutdown nosave     # 关闭且不持久化
redis-cli shutdown save       # 关闭并触发一次 SAVE

# 方式 2:systemctl
sudo systemctl stop redis

# 方式 3:信号(SIGTERM = 优雅关闭;SIGKILL = 强制)
kill -TERM $(cat /var/run/redis_6379.pid)

# 强制(不推荐,可能丢数据)
kill -9 $(cat /var/run/redis_6379.pid)
```

### 5.7 启动流程详解

```text
┌───────────────────────────────────────────────────────────┐
│                   redis-server 启动流程                     │
│                                                           │
│  1. 解析命令行参数 / 加载 redis.conf                       │
│        ↓                                                   │
│  2. 初始化事件循环(aeMain / epoll)                         │
│        ↓                                                   │
│  3. 启动后台线程(bio、AOF 刷盘、惰性删除)                 │
│        ↓                                                   │
│  4. 加载 RDB / AOF(若 appendonly=yes)                    │
│        ↓                                                   │
│  5. 监听 TCP 端口(默认 6379)                              │
│        ↓                                                   │
│  6. 监听 Unix Socket(若配置)                              │
│        ↓                                                   │
│  7. 启动主循环(单线程接收并执行客户端命令)                 │
└───────────────────────────────────────────────────────────┘
```

### 5.8 启动失败排查清单

| 现象                                | 排查方向                                  |
|-------------------------------------|-------------------------------------------|
| `Could not create server TCP listening socket` | 端口被占用,`netstat -lnp \| grep 6379` |
| `Can't open the append-only file`   | AOF 目录权限,`chown redis:redis /var/lib/redis` |
| `WARNING overcommit_memory is set to 0` | `sysctl vm.overcommit_memory=1`        |
| `WARNING you have Transparent Huge Pages enabled` | `echo never > /sys/kernel/mm/transparent_hugepage/enabled` |
| `MISCONF Redis cannot persist`       | 磁盘满 / 权限错误,`df -h` 检查            |
| `Out of memory`                     | maxmemory 触顶,检查淘汰策略               |

---

## 六、配置文件 redis.conf 详解

### 6.1 配置文件加载顺序

```text
加载优先级(后者覆盖前者):
  /etc/redis/redis.conf                          ← 包管理器默认
  /usr/local/etc/redis/redis.conf                ← Homebrew
  /usr/local/redis/redis.conf                    ← 源码安装
  命令行参数(如 redis-server --port 6380)
```

> **命令行参数 > 配置文件**,适合临时调优。

### 6.2 完整 redis.conf 示例

```ini
# ============================================
# /etc/redis/redis.conf - Redis 7.x 推荐配置
# ============================================

# -------------------- 基础(GENERAL) --------------------
daemonize          no              # 是否守护进程(Docker 中设为 no)
supervised         no              # systemd / upstart 托管
pidfile            /var/run/redis_6379.pid
loglevel           notice          # debug / verbose / notice / warning
logfile            /var/log/redis/redis.log
databases          16              # 默认 DB 数量 0-15
always-show-logo   no
proc-title-template "{title} {listen-addr} {server-mode}"

# -------------------- 快照(SAVE / RDB) --------------------
save 3600 1            # 3600 秒内有 1 次修改则触发
save 300 100           # 300 秒内 100 次修改
save 60 10000          # 60 秒内 10000 次修改
stop-writes-on-bgsave-error yes
rdbcompression         yes
rdbchecksum            yes
dbfilename             dump.rdb
rdb-del-sync-files    no
dir                    /var/lib/redis

# -------------------- 仅追加(AOF) --------------------
appendonly            yes
appendfilename        "appendonly.aof"
appenddirname         "appendonlydir"
appendfsync           everysec       # always / everysec / no
no-appendfsync-on-rewrite  yes
auto-aof-rewrite-percentage  100
auto-aof-rewrite-min-size   64mb
aof-load-truncated     yes
aof-use-rdb-preamble   yes           # 7.x 默认开启(混合持久化)

# -------------------- 网络(NETWORK) --------------------
bind                 127.0.0.1 -::1   # 监听 IP,生产建议内网 IP 或注释
protected-mode       yes
port                 6379
tcp-backlog          511
timeout              0               # 0 表示永不超时(连接空闲)
tcp-keepalive        300

# -------------------- 通用(GENERAL 续) --------------------
hz                   10
dynamic-hz           yes
dynamic-hz-max      100
set-proc-title       yes

# -------------------- 安全(SECURITY) --------------------
requirepass          "YourStrongPass123!"
rename-command FLUSHALL ""        # 禁用危险命令(集群模式失效)
rename-command CONFIG  ""
rename-command KEYS    ""
# ACL(Redis 6.0+,推荐取代 requirepass)
# aclfile /etc/redis/users.acl

# -------------------- 客户端(CLIENTS) --------------------
maxclients           10000

# -------------------- 内存管理(MEMORY MANAGEMENT) --------------------
maxmemory            4gb
maxmemory-policy     allkeys-lru      # 推荐:allkeys-lru / volatile-lru
maxmemory-samples    5
maxmemory-eviction-tenacity  10

# -------------------- 惰性释放(LAZY FREEING) --------------------
lazyfree-lazy-eviction      yes
lazyfree-lazy-expire        yes
lazyfree-lazy-server-del    yes
lazyfree-lazy-replica-eviction yes

# -------------------- 慢日志(SLOW LOG) --------------------
slowlog-log-slower-than 10000          # 10ms
slowlog-max-len          128

# -------------------- 延迟监控(LATENCY MONITOR) --------------------
latency-monitor-threshold 5

# -------------------- 集群 / 复制 --------------------
# cluster-enabled yes            # Cluster 模式开关
# cluster-config-file nodes-6379.conf
# cluster-node-timeout 15000
# replica-serve-stale-data yes
# replica-read-only yes
# repl-backlog-size 1mb

# -------------------- IO 线程(6.0+) --------------------
io-threads           4
io-threads-do-reads  yes

# -------------------- 附加模块(MODULES) --------------------
# loadmodule /path/to/redisearch.so
# loadmodule /path/to/redisjson.so
```

### 6.3 关键参数详解(分节)

#### 6.3.1 NETWORK(网络)

| 参数                | 默认值                  | 推荐                       | 说明                         |
|---------------------|-------------------------|----------------------------|------------------------------|
| `bind`              | 127.0.0.1 -::1         | 内网 IP 或 0.0.0.0         | 监听地址                     |
| `protected-mode`    | yes                     | yes                        | 无密码 + bind 非本地时拒绝连接 |
| `port`              | 6379                    | 自定                       | TCP 端口                     |
| `tcp-backlog`       | 511                     | 511                        | TCP 监听 backlog             |
| `timeout`           | 0                       | 0(永不)/ 300              | 客户端空闲超时(秒),0=禁用    |
| `tcp-keepalive`     | 300                     | 300                        | TCP keepalive 周期(秒)     |

#### 6.3.2 GENERAL(通用)

| 参数                       | 默认值          | 说明                                   |
|----------------------------|-----------------|----------------------------------------|
| `daemonize`                | no              | yes = 后台进程,Docker 必须 no          |
| `pidfile`                  | /var/run/redis_6379.pid | 进程 ID 文件                  |
| `loglevel`                 | notice          | debug/verbose/notice/warning           |
| `logfile`                  | ""              | 空 = stdout;文件路径则输出到文件      |
| `databases`                | 16              | DB 数量(0-15),Cluster 模式下只能用 0   |
| `hz`                       | 10              | 后台任务频率,1-500(影响 keyspace notifications 等) |

#### 6.3.3 SECURITY(安全)

| 参数             | 默认值            | 推荐                                | 说明                                 |
|------------------|-------------------|-------------------------------------|--------------------------------------|
| `requirepass`    | ""(无密码)       | 强密码 / 改用 ACL                   | 旧版单密码                           |
| `rename-command` | 无                | 禁用 FLUSHALL/KEYS/CONFIG           | 重命名危险命令,空字符串=禁用         |
| `aclfile`        | 无                | /etc/redis/users.acl                | Redis 6.0+ 推荐,基于用户的 ACL       |

#### 6.3.4 LIMITS(限制)

| 参数             | 默认值    | 推荐    | 说明                                  |
|------------------|-----------|---------|---------------------------------------|
| `maxclients`     | 10000     | 10000+  | 最大并发客户端数                      |
| `maxmemory`      | 0(无限制)| 物理内存 75% | 实例最大内存,超过触发淘汰       |
| `maxmemory-policy` | noeviction | allkeys-lru | 淘汰策略                  |
| `maxmemory-samples`| 5        | 5~10    | LRU/LFU 采样数,越大越精确,CPU 略高  |

#### 6.3.5 PERSISTENCE(持久化)

**RDB(快照)**：

| 参数                            | 推荐                       | 说明                                  |
|---------------------------------|----------------------------|---------------------------------------|
| `save 3600 1` 等                | 调整                       | 触发 RDB 的修改次数 + 时间窗口       |
| `stop-writes-on-bgsave-error`   | yes                        | RDB 失败时禁止写入                    |
| `rdbcompression`                | yes                        | RDB 文件 LZF 压缩                     |
| `rdbchecksum`                   | yes                        | RDB 文件 CRC64 校验                   |
| `dbfilename`                    | dump.rdb                   | RDB 文件名                            |
| `dir`                           | /var/lib/redis             | RDB/AOF 存储目录                      |

**AOF(追加日志)**：

| 参数                              | 推荐         | 说明                                          |
|-----------------------------------|--------------|-----------------------------------------------|
| `appendonly`                      | yes          | 开启 AOF                                      |
| `appendfsync`                     | everysec     | everysec=平衡,always=最安全,no=性能最好       |
| `no-appendfsync-on-rewrite`       | yes          | rewrite 时暂停 fsync,避免 IO 尖峰            |
| `auto-aof-rewrite-percentage`     | 100          | AOF 比上次 rewrite 增长 100% 触发 rewrite    |
| `auto-aof-rewrite-min-size`       | 64mb         | AOF 至少达到此大小才允许 rewrite              |
| `aof-use-rdb-preamble`            | yes(7.x)    | 开启混合持久化(AOF 头部为 RDB 格式)         |

#### 6.3.6 LAZY FREEING(惰性释放)

| 参数                              | 默认值  | 说明                                          |
|-----------------------------------|---------|-----------------------------------------------|
| `lazyfree-lazy-eviction`          | no      | 内存淘汰时是否异步释放                        |
| `lazyfree-lazy-expire`            | no      | key 过期是否异步释放                          |
| `lazyfree-lazy-server-del`        | no      | DEL/UNLINK 等服务端命令是否异步               |
| `lazyfree-lazy-replica-eviction`  | no      | replica 淘汰是否异步                          |

> **推荐全部开启 yes**,避免大 key 删除阻塞主线程。

### 6.4 只读 / 动态参数

| 类型       | 修改方式                                    | 示例                                |
|------------|---------------------------------------------|-------------------------------------|
| **静态**   | 仅配置文件,重启生效                          | `port`、`bind`、`daemonize`         |
| **动态**   | `CONFIG SET` 运行时改,无需重启              | `maxmemory`、`maxclients`、`appendonly` |
| **只读**   | 启动时决定,不可改                           | `cluster-enabled`、`replica-priority`(部分) |

```bash
# 动态修改示例
redis-cli CONFIG SET maxmemory 2gb
redis-cli CONFIG SET slowlog-log-slower-than 5000
redis-cli CONFIG SET appendonly yes
# 注:CONFIG 命令可能被 rename-command 禁用,需使用 ACL 放行

# 查看参数
redis-cli CONFIG GET maxmemory
# 1) "maxmemory"
# 2) "2147483648"

# 持久化到配置文件
redis-cli CONFIG REWRITE
```

---

## 七、redis-cli 客户端详解

### 7.1 启动与连接

```bash
# 1. 默认连接(127.0.0.1:6379)
redis-cli

# 2. 指定主机端口
redis-cli -h 192.168.1.10 -p 6380

# 3. 带密码
redis-cli -a YourStrongPass123!
# 或更安全:交互输入
redis-cli
> AUTH YourStrongPass123!

# 4. 指定 DB
redis-cli -n 2      # 连接后选择 2 号数据库

# 5. 通过 Socket
redis-cli -s /tmp/redis.sock

# 6. 通过 TLS
redis-cli --tls --cert client.crt --key client.key --cacert ca.crt

# 7. 进入交互模式 vs 单次执行
redis-cli PING                          # 单次执行
redis-cli -e "PING; INFO server"        # 多命令
```

**常用参数**：

| 参数                | 说明                                       |
|---------------------|--------------------------------------------|
| `-h / --host`       | 主机地址                                   |
| `-p / --port`       | TCP 端口                                   |
| `-s / --socket`     | Unix Socket                                |
| `-a / --password`   | 密码                                       |
| `-n / --dbnum`      | 数据库编号(0-15)                          |
| `-u / --uri`        | URI 形式 `redis://user:pass@host:port/db`  |
| `--tls`             | 启用 TLS                                   |
| `-c`                | 集群模式(自动重定向)                      |
| `-e`                | 退出前执行命令                             |
| `--latency`         | 进入延迟监测模式                           |
| `--stat`            | 实时滚动统计                               |
| `--scan`            | 增量扫描(替代 KEYS)                       |
| `--bigkeys`         | 扫描大 key                                 |
| `--memkeys`         | 扫描内存占用大的 key                       |
| `--hotkeys`         | 监测热 key(基于 LFU)                      |
| `--ldb`             | 启动 Lua 调试器                            |
| `-r / -repeat`      | 重复执行命令 N 次                          |
| `-i / --interval`   | 与 `-r` 配合,每 N 秒重复                   |

### 7.2 交互模式常用操作

```bash
# 1. 启动交互模式
redis-cli -h 127.0.0.1 -p 6379

# 2. 自动补全(Tab)
> KE<TAB>      # 补全 KEYS / KEYSIZE 等

# 3. 帮助
> HELP              # 总览
> HELP SET          # 特定命令帮助
> @generic          # 命令组
> @string
> @hash

# 4. 清屏
> CLEAR

# 5. 退出
> QUIT   /   EXIT   /   Ctrl+D

# 6. 命令历史(上下箭头)
> history           # 列出本次会话命令
```

### 7.3 远程调试与运维命令

```bash
# 1. 监控所有命令(生产慎用,影响性能)
redis-cli MONITOR

# 2. 实时统计(--stat,每秒刷新)
redis-cli --stat
# ------- data ------ ---- load ---- - child -
# keys       mem      clients blocked requests
# 10         1.20M    5        0       100

# 3. 延迟测试
redis-cli --latency
# min: 0, max: 1, avg: 0.05 (1234 samples)

# 4. 延迟历史
redis-cli --latency-history -i 5

# 5. 大 key 扫描(慎用,会扫描整个库)
redis-cli --bigkeys
# -------- summary -------
# Biggest string found '"user:10086:profile"' has 12800 bytes
# Biggest list found '"task:queue"' has 500000 items
# ...

# 6. 内存占用大的 key
redis-cli --memkeys

# 7. 增量扫描(替代 KEYS)
redis-cli --scan --pattern "user:*"

# 8. 批量删除(危险!)
redis-cli --scan --pattern "temp:*" | xargs -L 100 redis-cli DEL

# 9. 管道批处理
echo -e "PING\nSET k v\nGET k" | redis-cli

# 10. 基准测试
redis-benchmark -n 100000 -c 50 -P 10 -t set,get
# 50 clients, 100000 requests, payload=3 bytes
# ====== SET ======
#   100000 requests completed in 1.23 seconds
#   50 parallel clients
#   3 bytes payload
#   keep alive: 1
#   host configuration "save": 3600 1 300 100 60 10000
#   host configuration "appendonly": no
#   multi-thread: no
# Latency by percentile distribution:
# 0.000% <= 0.1 milliseconds
# 50.000% <= 0.3 milliseconds
# 99.900% <= 1.5 milliseconds
# 99.950% <= 2.0 milliseconds
# 99.990% <= 3.0 milliseconds
# 100.000% <= 4.0 milliseconds
# 81234.12 requests per second
```

### 7.4 集群与复制相关

```bash
# 1. 连接集群节点(自动重定向)
redis-cli -c -h 192.168.1.10 -p 6379
> GET key-in-other-slot
-> Redirected to slot [13152] located at 192.168.1.11:6379

# 2. 集群信息
redis-cli CLUSTER INFO
redis-cli CLUSTER NODES

# 3. 主从复制
redis-cli INFO replication
redis-cli REPLICAOF 192.168.1.10 6379   # 设置主节点
redis-cli REPLICAOF NO ONE              # 取消主从

# 4. Sentinel 高可用
redis-cli -p 26379 SENTINEL masters
redis-cli -p 26379 SENTINEL slaves mymaster
```

---

## 八、多数据库(SELECT)

### 8.1 什么是 Redis 数据库

Redis 默认提供 **16 个数据库**,编号 **0-15**,可通过 `SELECT <n>` 切换。逻辑上每个 DB 是**独立的命名空间**,但**共享同一份 RDB/AOF 与同一个 Redis 实例**(不隔离)。

### 8.2 使用方式

```bash
# 默认 DB 0
redis-cli
> SET name "alice"
OK

# 切换到 DB 1
> SELECT 1
OK
> SET name "bob"
OK
> GET name
"bob"

# 切回 DB 0
> SELECT 0
OK
> GET name
"alice"

# 移动 key 到其他 DB
> MOVE name 2
(integer) 1
```

### 8.3 16 个 DB 的局限性

| 限制                           | 说明                                           |
|--------------------------------|------------------------------------------------|
| **非完全隔离**                 | 共享 CPU、内存、IO,一个 DB 阻塞影响所有 DB    |
| **共享 RDB/AOF**               | 所有 DB dump 到同一个 RDB / AOF 文件          |
| **不适用于 Cluster**           | Cluster 模式下**仅支持 DB 0**                 |
| **跨 DB 操作低效**             | 无 `SELECTALL`,需客户端循环                   |
| **监控与 ACL 复杂度**          | 多数命令作用于当前 DB,ACL 粒度粗              |

> **最佳实践**：**每个应用使用独立 Redis 实例**(或独立 Cluster 槽位),**不要**依赖多 DB 做业务隔离。需要逻辑隔离时,用**前缀**(`user:`, `order:`)配合 SCAN 更合适。

---

## 九、常用系统命令

### 9.1 服务连通性

```bash
# PING(测试连通,返回 PONG)
redis-cli PING

# ECHO(回显)
redis-cli ECHO "hello"
# "hello"

# TIME(服务器时间)
redis-cli TIME
# 1) "1700000000"
# 2) "123456"
```

### 9.2 服务端信息(INFO)

```bash
# 完整 INFO(分段输出)
redis-cli INFO

# 分段
redis-cli INFO server
redis-cli INFO clients
redis-cli INFO memory
redis-cli INFO stats
redis-cli INFO replication
redis-cli INFO cpu
redis-cli INFO cluster
redis-cli INFO keyspace
```

**完整输出解读**：

```text
# Server
redis_version:7.4.1
redis_git_sha1:00000000
redis_git_dirty:0
redis_build_id:abc123...
redis_mode:standalone
os:Linux 5.15.0 x86_64
arch_bits:64
monotonic_clock:POSIX
multiplexing_api:epoll
atomicvar_api:atomic-builtin
gcc_version:11.3.0
process_id:12345
process_supervised:no
run_id:abc123def456
tcp_port:6379
server_time_usec:1700000000000000
uptime_in_seconds:86400           # 运行时长(秒)
uptime_in_days:1
hz:10
configured_hz:10
lru_clock:12345678
executable:/usr/local/redis/bin/redis-server
config_file:/etc/redis/redis.conf
io_threads_active:0

# Clients
connected_clients:5              # 当前连接数
cluster_connections:0
maxclients:10000
client_recent_max_input_buffer:20480
client_recent_max_output_buffer:0
blocked_clients:0                 # BLPOP 等阻塞客户端
tracking_clients:0                # 客户端跟踪
clients_in_timeout_table:0

# Memory
used_memory:1048576               # Redis 分配器占用(byte)
used_memory_human:1.00M
used_memory_rss:5242880           # 操作系统 RSS
used_memory_rss_human:5.00M
used_memory_peak:2097152
used_memory_peak_human:2.00M
used_memory_peak_perc:50.00%
used_memory_dataset_perc:75.00%
allocator_allocated:1048576
allocator_active:1572864
allocator_resident:4194304
allocator_frag_ratio:1.50         # 碎片率(>1.5 考虑重启或 jemalloc)
allocator_frag_bytes:524288
allocator_rss_bytes:4194304
allocator_rss_ratio:4.00
mem_fragmentation_ratio:5.00      # RSS / used_memory,>1.5 提示碎片
mem_fragmentation_bytes:4194304
mem_not_counted_for_evict:0
mem_replication_backlog:1048576
mem_total_replication_buffers:0
mem_clients_slaves:0
mem_clients_normal:20480
mem_cluster_links:0
mem_aof_buffer:0
mem_allocator:libc                # 内存分配器:libc / jemalloc
mem_overhead_base:196608
mem_overhead_db_hashtable_index:0
mem_overhead_db_hashtable_rehashing:0
mem_overhead_db_expires:0
mem_overhead_db_total:0
active_defrag_running:0           # 主动碎片整理是否运行

# Stats
total_connections_received:1234
total_commands_processed:567890
instantaneous_ops_per_sec:1234    # 当前 OPS
total_net_input_bytes:1234567890
total_net_output_bytes:9876543210
instantaneous_input_kbps:123.45
instantaneous_output_kbps:987.65
rejected_connections:0            # 因 maxclients 拒绝的连接
expired_keys:100                  # 已过期 key 总数
expired_stale_perc:0.00
expired_time_cap_reached_count:0
evicted_keys:0                    # 内存淘汰 key 总数
keyspace_hits:50000
keyspace_misses:10000
pubsub_channels:0
pubsub_patterns:0
latest_fork_usec:12345            # 最近 fork() 耗时(微秒)
total_forks:5
migrate_cached_sockets:0

# Replication
role:master                       # master / slave
connected_slaves:0
master_failover_state:no-failover
master_replid:abc123...
master_replid2:00000000
master_repl_offset:12345
second_repl_offset:-1
repl_backlog_active:1
repl_backlog_size:1048576
repl_backlog_first_byte_offset:1
repl_backlog_histlen:12345

# CPU
used_cpu_sys:10.50                 # 系统态 CPU(秒)
used_cpu_user:20.30                # 用户态 CPU(秒)
used_cpu_sys_children:0.50
used_cpu_user_children:0.20

# Cluster
cluster_enabled:0                  # 0=单机,1=集群

# Keyspace
db0:keys=10,expires=0,avg_ttl=0   # DB 0:10 个 key,无过期
db1:keys=5,expires=2,avg_ttl=30000 # DB 1:5 个 key,2 个过期
```

**重点指标速查**：

| 指标                                | 含义                                | 告警阈值            |
|-------------------------------------|-------------------------------------|---------------------|
| `used_memory_human`                 | 已用内存                            | 接近 `maxmemory`    |
| `mem_fragmentation_ratio`           | RSS / used_memory                   | > 1.5 告警,> 2 重启 |
| `instantaneous_ops_per_sec`         | 当前 OPS                            | 按业务基线          |
| `connected_clients`                 | 当前连接                            | 接近 `maxclients`   |
| `blocked_clients`                  | 阻塞客户端数                        | > 0 持续告警       |
| `keyspace_hits / (hits+misses)`     | 命中率                              | < 90% 需排查       |
| `expired_keys` / `evicted_keys`     | 过期 / 淘汰速率                     | 大量 evicted 提示内存不足 |
| `latest_fork_usec`                  | 最近 fork 耗时                      | > 1000ms 告警       |
| `rdb_last_bgsave_status`            | RDB 是否成功                        | failed 立即处理     |

### 9.3 数据库管理

```bash
# DBSIZE(当前 DB 的 key 数)
redis-cli DBSIZE
# (integer) 10

# SELECT(切换 DB)
redis-cli SELECT 2

# FLUSHDB(清空当前 DB,慎用!)
redis-cli FLUSHDB                  # 同步清空
redis-cli FLUSHDB ASYNC            # 异步清空(7.4+)

# FLUSHALL(清空所有 DB,极度危险!)
redis-cli FLUSHALL

# KEYS(扫描所有 key,生产禁用!)
redis-cli --scan --pattern "*"

# SCAN(增量游标扫描,生产推荐)
redis-cli SCAN 0 MATCH user:* COUNT 100

# RANDOMKEY(随机返回 1 个 key)
redis-cli RANDOMKEY

# TYPE(查 key 类型)
redis-cli TYPE user:10086
# hash

# EXISTS(查 key 是否存在)
redis-cli EXISTS user:10086
# (integer) 1

# DEL(删除)
redis-cli DEL user:10086
# (integer) 1

# UNLINK(异步删除,大 key 推荐)
redis-cli UNLINK bigkey

# RENAME / RENAMENX(重命名)
redis-cli RENAME old new
redis-cli RENAMENX old new         # 仅当 new 不存在时

# EXPIRE / TTL(过期)
redis-cli EXPIRE user:10086 3600
redis-cli TTL user:10086

# PERSIST(取消过期)
redis-cli PERSIST user:10086
```

### 9.4 服务器控制

```bash
# SHUTDOWN(关闭服务)
redis-cli SHUTDOWN [NOSAVE|SAVE]
# SHUTDOWN 默认触发 SAVE 后再关闭
# SHUTDOWN NOSAVE 不持久化直接关闭

# DEBUG SLEEP(模拟阻塞,调试用)
redis-cli DEBUG SLEEP 5

# CLIENT LIST(查所有连接)
redis-cli CLIENT LIST
# id=1 addr=127.0.0.1:54321 fd=8 name= age=10 idle=0 ...
# CLIENT KILL id=1   # 杀连接

# CLIENT PAUSE(暂停所有客户端,毫秒)
redis-cli CLIENT PAUSE 5000

# CONFIG RESETSTAT(重置 INFO stats)
redis-cli CONFIG RESETSTAT

# SLOWLOG(慢日志)
redis-cli SLOWLOG GET 10
redis-cli SLOWLOG LEN
redis-cli SLOWLOG RESET

# LATENCY(延迟诊断子命令)
redis-cli LATENCY HISTORY event-name
redis-cli LATENCY RESET

# MEMORY(内存诊断)
redis-cli MEMORY DOCTOR
redis-cli MEMORY USAGE key
redis-cli MEMORY PURGE              # 释放内存(7.x)
```

---

## 十、升级与迁移

### 10.1 升级路径

| 升级方式       | 适用场景                                | 风险     |
|----------------|-----------------------------------------|----------|
| **小版本 in-place** | 7.2.x → 7.2.y(同大版本小版本)        | 低       |
| **大版本 in-place** | 6.x → 7.x,需重编译 / 替换二进制      | 中       |
| **逻辑备份**   | `DUMP`/`RESTORE` 单 key、`redis-cli --pipe` | 低     |
| **RDB 迁移**   | 拷 dump.rdb 到新实例(版本兼容性注意)   | 中       |

### 10.2 升级前的检查

```bash
# 1. 查看当前版本
redis-cli INFO server | grep redis_version

# 2. 查看关键配置
redis-cli CONFIG GET maxmemory-policy
redis-cli CONFIG GET appendonly

# 3. 查看数据规模
redis-cli DBSIZE
redis-cli INFO memory

# 4. 备份 RDB(必须)
cp /var/lib/redis/dump.rdb /var/lib/redis/dump.rdb.bak.$(date +%F)

# 5. 备份 AOF
cp -a /var/lib/redis/appendonlydir /var/lib/redis/appendonlydir.bak.$(date +%F)
```

### 10.3 小版本 in-place 升级

```bash
# 1. 停服
redis-cli SHUTDOWN NOSAVE

# 2. 替换二进制
# 源码安装:cp new-redis-server /usr/local/redis/bin/
# 包管理:sudo apt install --only-upgrade redis

# 3. 启动
redis-server /etc/redis/redis.conf

# 4. 验证版本
redis-cli INFO server | grep redis_version
```

### 10.4 大版本升级(6.x → 7.x)

```bash
# 1. 停服并备份
redis-cli SHUTDOWN
cp -a /var/lib/redis /var/lib/redis.bak.$(date +%F)
cp /etc/redis/redis.conf /etc/redis/redis.conf.bak

# 2. 安装新版本(以 Ubuntu 为例)
sudo apt install redis-server=7.4.*    # 或下载 7.4 二进制

# 3. 合并配置差异
# 7.x 移除的参数:slaveof(改 replicaof)、rename-command 行为微调
diff /etc/redis/redis.conf /etc/redis/redis.conf.bak

# 4. 启动新版本
sudo systemctl start redis

# 5. 验证数据
redis-cli DBSIZE
redis-cli INFO keyspace
```

### 10.5 跨主机迁移

#### 10.5.1 使用 SCAN + DUMP/RESTORE(适用于少量数据)

```bash
# 源端
redis-cli --scan --pattern "*" | while read key; do
    TYPE=$(redis-cli TYPE "$key")
    TTL=$(redis-cli TTL "$key")
    VALUE=$(redis-cli DUMP "$key")
    echo "RESTORE $key $TTL $VALUE" >> /tmp/migrate.txt
done

# 目标端
cat /tmp/migrate.txt | redis-cli --pipe
```

#### 10.5.2 使用 RDB 文件(最直接)

```bash
# 1. 源端触发 SAVE(避免 BGSAVE 时拷文件不一致)
redis-cli SAVE

# 2. 拷贝 RDB 到目标主机
scp /var/lib/redis/dump.rdb target:/var/lib/redis/

# 3. 目标端启动,加载该 RDB
redis-server --dir /var/lib/redis --dbfilename dump.rdb
```

#### 10.5.3 使用 redis-cli --pipe(管道方式,高效)

```bash
# 1. 源端导出 aof 或文本格式
redis-cli --pipe <<EOF
SET k1 v1
SET k2 v2
EOF

# 2. 或 RDB 转 RESP 协议(rdb-tools 等)
```

### 10.6 升级注意事项清单

| 注意项                                | 说明                                                |
|---------------------------------------|-----------------------------------------------------|
| 备份 RDB / AOF                        | 升级前必做                                          |
| 检查大版本兼容性                       | 7.x RDB 格式与 6.x 兼容,但 6.x 不一定能读 7.x RDB  |
| 配置文件合并                          | `CONFIG GET *` 记录当前配置,对比新版本默认值       |
| 客户端驱动版本                        | 旧 jedis / redis-py 不支持 RESP3 / ACL 时升级       |
| ACL / TLS 兼容性                      | 6.0+ 引入的 ACL 7.x 有微调,需回归测试              |
| 监控告警验证                          | 升级后检查 INFO / 监控是否正常                     |

---

## 十一、卸载 Redis

### 11.1 包管理器安装的卸载

```bash
# Debian/Ubuntu
sudo systemctl stop redis-server
sudo apt remove redis-server
sudo apt purge redis-server     # 同时删除配置
sudo apt autoremove

# RHEL/CentOS
sudo systemctl stop redis
sudo yum remove redis
# 或 dnf remove redis

# 清理数据(谨慎!)
sudo rm -rf /var/lib/redis
sudo rm -rf /var/log/redis
sudo rm /etc/redis/redis.conf
sudo userdel redis
```

### 11.2 源码安装的卸载

```bash
# 1. 停服
redis-cli SHUTDOWN NOSAVE

# 2. 删除二进制
rm -rf /usr/local/redis
sed -i '/redis/d' /etc/profile           # 清理 PATH
source /etc/profile

# 3. 删除配置与数据
rm -rf /etc/redis
rm -rf /var/lib/redis
rm -rf /var/log/redis

# 4. 删除用户(若有)
userdel redis
```

### 11.3 Docker 卸载

```bash
# 停掉并删除容器
docker stop redis7
docker rm redis7

# 删除镜像
docker rmi redis:7.4-alpine

# 删除数据卷(可选,清数据)
docker volume ls | grep redis
docker volume rm <volume_name>
```

### 11.4 验证已彻底卸载

```bash
# 命令不存在
which redis-server redis-cli

# 没有进程
pgrep -af redis

# 没有服务
systemctl list-unit-files | grep -i redis
```

---

## 十二、核心要点速记

- **Redis 是内存型 KV 数据库**,由 **Salvatore Sanfilippo(antirez)** 开发,BSD 许可,现由 Redis Ltd. 维护
- **9 类数据结构**:String / Hash / List / Set / ZSet / Bitmap / HyperLogLog / GEO / Stream
- **版本选择**:生产推荐 **Redis 7.2 / 7.4**,6.x 仍可使用;5.x 及更早逐步淘汰
- **Redis Stack** 集成 RediSearch、RedisJSON、RedisBloom 等模块,适合搜索/JSON 场景
- **特点**:基于内存、命令执行单线程(IO 6.0+ 可多线程)、丰富数据结构、RDB+AOF 持久化、Cluster 16384 槽
- **安装方式**:源码(深度定制)、apt/yum(入门)、Docker(隔离)、brew(macOS)
- **可执行文件**:`redis-server`(服务)、`redis-cli`(客户端)、`redis-benchmark`(压测)、`redis-check-aof/rdb`(检查)、`redis-sentinel`(高可用)
- **启动方式**:`systemctl start redis`(主流)、`redis-server --daemonize yes`(无 systemd)、前台(调试)
- **配置文件 redis.conf** 分节:NETWORK / GENERAL / SECURITY / LIMITS / PERSISTENCE / LAZY FREEING / REPLICATION / CLUSTER
- **核心参数**:`bind`(监听)、`protected-mode`、`requirepass`/`aclfile`(认证)、`maxmemory` + `maxmemory-policy`(淘汰)、`appendonly` + `appendfsync`(持久化)
- **淘汰策略**:`allkeys-lru`(推荐)、`volatile-lru`、`allkeys-lfu`(7.4+ LFU)、`noeviction`(默认,不淘汰,写失败)
- **持久化策略**:`everysec`(平衡)、`always`(最安全,IO 大)、`no`(性能最好,可能丢秒级数据);7.x 默认开启 `aof-use-rdb-preamble` 混合持久化
- **动态参数**:`CONFIG SET` / `CONFIG REWRITE` 可运行时修改并持久化;`port`/`bind`/`daemonize` 等为静态
- **redis-cli 选项**:`-h/-p/-a/-n/-s/--tls/-c`,运维利器 `--bigkeys`/`--memkeys`/`--hotkeys`/`--latency`/`--stat`/`MONITOR`
- **多 DB 局限**:默认 16 个(0-15),Cluster 模式**仅支持 DB 0**;**不推荐**用于业务隔离,应使用**独立实例** + **key 前缀**
- **INFO 重点指标**:`used_memory`(内存)、`mem_fragmentation_ratio`(碎片,> 1.5 关注)、`instantaneous_ops_per_sec`(OPS)、`keyspace_hits`/`misses`(命中率)、`connected_clients`、`blocked_clients`
- **系统命令**:`PING` / `INFO [section]` / `DBSIZE` / `SELECT n` / `FLUSHDB` / `FLUSHALL` / `SHUTDOWN [NOSAVE|SAVE]` / `CLIENT LIST|KILL|PAUSE` / `SLOWLOG` / `MEMORY`
- **升级路径**:小版本 in-place 安全;**大版本先备份 RDB+AOF,合并配置差异**,验证监控告警
- **迁移方式**:RDB 拷贝(直接)、DUMP/RESTORE(单 key)、SCAN 管道(可控);**升级前必备份**
- **卸载**:包管理器 `remove/purge` → 清 `/var/lib/redis`、`/etc/redis`、`/var/log/redis` → 删 `redis` 用户
- **坑点**:`protected-mode` 开启 + 无密码 + bind 非本地 → 拒绝外部连接;`rename-command` 在 Cluster 下**失效**;`MEMORY` 诊断命令在 Cluster 部分节点**不可用**;`FLUSHALL` 在生产务必 ACL 限制或 rename 禁用