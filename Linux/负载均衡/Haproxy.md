# HAProxy

## 一、HAProxy 概述

### 什么是 HAProxy

**HAProxy**:高性能的 TCP / HTTP 反向代理与负载均衡器

- Willy Tarreau 2000 年开源,现由他维护
- GPLv2 协议
- 事件驱动 + 单线程/多线程模型
- 占据 L4/L7 LB 中大量市场份额,核心生产级
- 关键口号:**"世界上最快的负载均衡器之一"**

### 核心组件

| 组件                  | 说明                                |
|-----------------------|-------------------------------------|
| **HAProxy Core**      | 主进程、配置加载、事件循环             |
| **frontend**          | 监听 + 规则匹配                       |
| **backend**           | 上游服务器组                          |
| **listen**            | frontend + backend 合并              |
| **stick-table**       | 共享内存 K/V(粘性会话 / 限流)         |
| **peers**             | 多实例同步(共享 stick-table)         |
| **log**               | 访问日志 / 错误日志                   |

### HAProxy vs 其他 LB

| 维度        | HAProxy             | Nginx             | LVS              | Envoy           |
|-------------|---------------------|--------------------|------------------|-----------------|
| 模式        | L4 + L7            | L7 强 + L4(stream)| L4              | L4 + L7          |
| 性能        | **极高**           | 高                 | **极高**         | 高              |
| 配置        | 单 haproxy.cfg      | nginx.conf         | ipvsadm          | YAML + xDS     |
| 健康检查    | **强**(主动 + 被动) | 被动为主            | 弱               | 强              |
| 监控        | stats page / Prometheus | stub_status    | –                | stats / admin  |
| 动态配置    | 弱(需 reload / Runtime API) | 弱       | –                | **强**(xDS)     |
| 适用        | L4/L7 LB,Web/API    | 反代、网关          | 纯 L4 透传        | 服务网格         |

---

## 二、架构与运行机制

### 1. 进程与线程模型

```text
Master 进程(可选,HAProxy 2.0+)
├── Master CLI (socket / Runtime API)
└── Worker 1
    ├── thread 1 (事件循环)
    ├── thread 2 (事件循环)
    └── thread N (事件循环)
```

- **Master**:可选,管理 Worker + Runtime API(动态调整)
- **Worker**:每个 Worker 多线程
- **线程数**:`nbthread N`,一般 1-8 倍 CPU 核数
- **请求分发**:每个连接绑定到固定线程(避免锁竞争)
- **accept_mutex**:多线程时自动串行化 accept

### 2. 事件循环

**HAProxy 的"高并发"= epoll + 多线程 + 单连接固定线程**

- 一个线程可处理上万连接
- 基于 epoll(Linux)/ kqueue(BSD)
- I/O 阻塞 → 注册回调 → 事件就绪 → 回调执行

```text
请求 1 ──┐
请求 2 ──┤── 同一线程中,通过事件循环分发
请求 3 ──┘
```

### 3. 内存模型

**Worker 间 + 线程间部分共享**:

- **stick-table / peers**:基于共享内存的 K/V,跨 Worker / 跨进程 / 跨机
- **进程独立**:每个 Worker / 线程自己的连接池
- **stats**:统计独立,定时上报

---

## 三、运行模式与 I/O 模型

### 1. 模式

```text
haproxy.cfg 配置
├── mode http       # L7,完整解析 HTTP
├── mode tcp        # L4,纯透传
└── mode health     # 健康检查模式(仅响应 health check)
```

### 2. 线程模型

```text
global
    nbthread 4      # 4 个线程
    cpu-map auto:1/1-4  # 绑定 CPU

defaults
    balance roundrobin
```

### 3. 转发模式

```text
TPROXY:    客户端 → LB → upstream,源 IP 保留(IP 透明)
TOX:       客户端 → LB → upstream,LB 替换客户端 IP
HTTP:      L7 反代
TCP:       L4 透传
```

### 4. 多进程 / 多实例

```text
# 多个 haproxy 实例,共享 stick-table
peers mycluster
    peer haproxy1 10.0.0.1:1024
    peer haproxy2 10.0.0.2:1024
```

---

## 四、配置结构 (Configuration Phases)

### 1. 配置段总览

```text
haproxy.cfg
├── global           # 进程级配置
├── defaults          # 默认配置(可被段继承)
├── frontend          # 监听 + ACL
├── backend           # 上游 + 调度
├── listen            # frontend + backend 合并
├── userlist          # 用户认证
├── peers             # 多实例同步
├── mailers           # 邮件告警
├── cache             # 响应缓存
├── program           # 外部程序
└── http-errors       # 自定义错误页
```

### 2. 段详解

| 段                | 时机                  | 常用配置                       |
|-------------------|-----------------------|--------------------------------|
| **global**        | 启动时进程级           | daemon, maxconn, nbthread, ssl |
| **defaults**      | 全段默认值             | mode, balance, timeout         |
| **frontend**      | 接收请求,匹配规则     | bind, acl, use_backend         |
| **backend**       | 上游服务器组           | server, balance, health-check  |
| **listen**        | frontend + backend 简化 | 同上                           |

### 3. 段继承关系

```text
global
   │
   ▼
defaults ◄─────────────┐
   │                    │
   ▼                    │
frontend                │
   │                    │
   ▼                    │
backend ────────────────┘
```

### 4. 配置示例

```haproxy
global
    daemon
    maxconn 100000
    nbthread 4

defaults
    mode http
    balance roundrobin
    timeout connect 5s
    timeout client 30s
    timeout server 30s

frontend ft_web
    bind *:80
    acl is_api path_beg /api
    use_backend bk_api if is_api
    default_backend bk_web

backend bk_api
    server api1 10.0.0.1:8080 check
    server api2 10.0.0.2:8080 check

backend bk_web
    server web1 10.0.0.10:80 check
    server web2 10.0.0.11:80 check
```

---

## 五、常用指令

### 1. global 段

```haproxy
global
    daemon                            # 守护进程模式
    maxconn 100000                    # 全局最大并发连接
    nbthread 4                        # 线程数
    cpu-map auto:1/1-4                # CPU 亲和
    log 127.0.0.1 local0              # 日志目标
    user haproxy
    group haproxy
    ssl-default-bind-ciphers ECDHE+AESGCM:!aNULL:!MD5:!RC4
    stats socket /var/run/haproxy.sock mode 660 level admin
```

### 2. defaults 段

```haproxy
defaults
    mode http                         # http / tcp / health
    balance roundrobin
    option httplog                    # HTTP 详细日志
    option forwardfor                 # 加 X-Forwarded-For
    option dontlognull                # 不记空连接
    option redispatch                  # 失败重派
    retries 3
    timeout connect 5s
    timeout client 30s
    timeout server 30s
    timeout http-request 10s
    timeout http-keep-alive 10s
```

### 3. frontend 段

```haproxy
frontend ft_web
    bind *:80
    bind *:443 ssl crt /etc/haproxy/certs/

    # 路由 ACL
    acl is_api   path_beg /api
    acl is_admin hdr_dom(host) -i admin.example.com
    acl is_ssl   ssl_fc

    use_backend bk_api   if is_api
    use_backend bk_admin if is_admin
    default_backend bk_web
```

### 4. backend 段

```haproxy
backend bk_api
    balance roundrobin
    option httpchk GET /health
    http-check expect status 200

    server api1 10.0.0.1:8080 check weight=3
    server api2 10.0.0.2:8080 check weight=1
    server api3 10.0.0.3:8080 check backup

    cookie SRVID insert indirect nocache
```

### 5. listen 段

```haproxy
listen stats
    bind *:9000
    stats enable
    stats uri /stats
    stats refresh 10s
    stats auth admin:password
```

### 6. 变量

```haproxy
%{capture.req.hdr(0)}                # 请求头(0=第一行)
%[capture.req.uri]                  # URI
%[src]                              # 客户端 IP
%[dst]                              # 目标 IP
%[be_conn]                          # backend 连接数
%[srv_conn]                         # 当前 server 连接数
```

---

## 六、Stick-table(共享内存 K/V)

### 1. 概述

**stick-table**:HAProxy 的共享内存 K/V 存储

- 分配在共享内存
- **所有 Worker / 线程可见**
- 用 type + size 指定存储类型
- 适合粘性会话、限流、统计

### 2. 配置

```haproxy
backend bk_web
    stick-table type ip size 50k expire 30s store http_req_rate(10s)

    # 应用:粘性 + 限流
    stick on src
    http-request track-sc0 src
    http-request deny if { sc_http_req_rate(0) gt 100 }
```

### 3. 类型

| type        | 存储              | 大小 |
|-------------|-------------------|------|
| `ip`        | 字符串(IP)        | 4 + len |
| `ipv6`      | 字符串(IPv6)      | 16 + len |
| `int`       | 32 位整数         | 4 |
| `string`    | 字符串            | len |
| `binary`    | 二进制            | len |

### 4. 存储字段

```haproxy
stick-table type ip size 50k expire 30s \
    store http_req_rate(10s) \    # 10s 请求速率
          http_err_rate(10s) \    # 10s 错误率
          gpc0 \                  # 全局计数器 0
          gpc1                    # 全局计数器 1
```

### 5. API

```haproxy
# http-request track-sc0 src       # 跟踪 + 提取值到 sc0
# stick on src                    # 粘性(根据 src)
# http-request deny if { sc_http_req_rate(0) gt 100 }  # 限流
```

### 6. 应用场景

| 场景         | 做法                              |
|--------------|-----------------------------------|
| 粘性会话     | `stick on src` 或 `cookie`        |
| QPS 限流     | `http_req_rate` + `deny`          |
| 防并发       | `conn_cur` + `deny`               |
| 异常检测     | `http_err_rate` + `deny`          |
| 灰度 / A/B   | stick-table + map                 |
| 爬虫识别     | `src_http_req_rate(10s)`         |

### 7. 限制

- 单 key 上限 `size` 配置项
- 字段数限制(`nbsrv` 影响 server 字段)
- 复杂数据结构需多个字段组合

---

## 七、网络 I/O(L4 + L7)

### 1. L4 转发(stream / mode tcp)

```haproxy
frontend ft_tcp_mysql
    bind *:3306
    mode tcp
    default_backend bk_mysql

backend bk_mysql
    mode tcp
    balance leastconn
    option mysql-check user haproxy
    server db1 10.0.0.1:3306 check
    server db2 10.0.0.2:3306 check
```

### 2. L7 反代(mode http)

```haproxy
frontend ft_http
    bind *:80
    mode http
    default_backend bk_web

backend bk_web
    mode http
    balance roundrobin
    option httpchk GET /health
    http-request set-header X-Real-IP %[src]
    server web1 10.0.0.10:80 check
```

### 3. HTTP/2 + HTTPS

```haproxy
frontend ft_https
    bind *:443 ssl crt /etc/haproxy/certs/ alpn h2,http/1.1
    mode http
    http-request redirect scheme https unless { ssl_fc }

backend bk_web
    mode http
    http-reuse safe                     # HTTP/2 多路复用
    server web1 10.0.0.10:443 ssl verify required ca-file /etc/ssl/ca.pem check
```

### 4. gRPC

```haproxy
frontend ft_grpc
    bind *:50051
    mode http
    acl is_grpc req.hdr Content-Type application/grpc
    use_backend bk_grpc if is_grpc

backend bk_grpc
    mode http
    option httpchk
    server grpc1 10.0.0.20:50051 check
```

### 5. WebSocket

```haproxy
frontend ft_ws
    bind *:80
    mode http
    acl is_ws hdr(Upgrade) -i WebSocket
    use_backend bk_ws if is_ws

backend bk_ws
    mode http
    option httpchk
    timeout tunnel 3600s                 # WebSocket 长连接超时
    server ws1 10.0.0.30:8080 check
```

### 6. HTTP Client(类似 cosocket)

通过 `program` + `external-check` 或 `http-request lua.*` 调用外部 HTTP 服务。

### 7. 连接池

```haproxy
backend bk_web
    option http-keep-alive
    http-reuse aggressive                # 复用上游连接
    server web1 10.0.0.10:80 check
```

### 8. 关键能力

- **L4 + L7 一体**:同一进程同时支持 TCP + HTTP
- **健康检查**:主动 + 被动
- **连接池**:HTTP keep-alive + 上游复用
- **源 IP 保留**:`option forwardfor` + `source 0`(`usesrc`)
- **慢启动**:`server web1 ... slowstart 60s`

---

## 八、log forwarder(子请求 / 日志转发)

### 1. 概述

**log forwarder**:HAProxy 把日志通过 TCP 协议发送出去(类似子请求)

- 通过 `log` 指令 + `log-format`
- 支持 RFC 5424 syslog / custom
- 通过 `program` 段转发到任意处理程序

### 2. 用法

```haproxy
global
    log 127.0.0.1:514 local0
    log 192.168.1.100:514 local0
    log-format ${HAPROXY_LOG}

defaults
    log global
    option httplog

frontend ft_web
    capture request header X-Trace-Id len 32
    capture response header Content-Type len 16

    # 自定义日志格式
    log-format "%ci:%cp [%tr] %ft %b/%s %Tq %Tw %Tc/%Tt %ST %B %CC %CS %tsc %ac/%fc/%bc/%sc/%rc %sq/%bq %hr %hs %[capture.req.hdr(0)]"
```

### 3. log vs lua-program

| 维度        | log 指令           | program + lua-program   |
|-------------|--------------------|-------------------------|
| 用途        | 转发日志到外部       | 自定义处理               |
| 灵活性      | 受 log-format 限制   | Lua 灵活                 |
| 性能        | 异步,不阻塞请求       | 异步,自定义调度         |
| 适用        | 日志聚合 / 审计      | 自定义控制平面           |

---

## 九、定时任务 / Cron

### 1. cron 段(HAProxy 1.8+)

```haproxy
# 每天凌晨 3 点清理 stick-table 过期条目
cron /usr/bin/haproxy-cron-cleanup 0 3 * * *
```

### 2. 日志触发

```haproxy
# 收到特定 HTTP 请求触发动作
http-request lua.cron_handler
```

### 3. Runtime API(动态调整)

```bash
# 通过 stats socket 触发
echo "set maxconn frontend ft_web 50000" | socat stdio /var/run/haproxy.sock
echo "show stat" | socat stdio /var/run/haproxy.sock
```

### 4. 注意事项

- **cron 在主进程运行**,会阻塞 haProxy
- Runtime API 通过 socket,**不重启**

---

## 十、ACL 与正则(fetchers)

### 1. ACL fetchers

| fetcher                  | 含义                  | 例子                              |
|--------------------------|-----------------------|-----------------------------------|
| `path_beg`               | URL 路径前缀           | `path_beg /api`                   |
| `path_end`               | URL 路径后缀           | `path_end .jpg`                   |
| `path_reg`               | URL 路径正则           | `path_reg ^/api/v[0-9]+/`         |
| `hdr_dom(host)`          | Host 头匹配            | `hdr_dom(host) -i example.com`    |
| `hdr(host)`              | Host 头(精确)          | `hdr(host) www.example.com`       |
| `hdr_beg`                | 请求头前缀             | `hdr_beg(user-agent) Mozilla`     |
| `src`                    | 客户端 IP              | `src 192.168.1.0/24`              |
| `src_port`               | 源端口                 | `src_port 0:1024`                 |
| `ssl_fc`                 | 是否 SSL 连接          | `ssl_fc`                          |
| `req.cook(name)`         | 请求 Cookie 值         | `req.cook(session) -m found`      |
| `req.hdr(name)`          | 请求头                 | `req.hdr(user-agent)`             |
| `method`                 | HTTP 方法              | `method GET POST`                 |
| `capture.req.hdr(N)`     | 第 N 个 capture 的请求头 | `capture.req.hdr(0)`             |
| `nbsrv`                  | 上游 server 数          | `nbsrv(bk_web) gt 1`              |
| `be_conn`                | backend 连接数         | `be_conn(bk_web) gt 1000`         |

### 2. ACL 匹配符

| 标志  | 含义 |
|-------|------|
| `-i`  | 忽略大小写 |
| `-m`  | 模式匹配(method/header 默认行为) |
| `-f`  | 从文件加载 |
| `-n`  | 否定 |
| `--`  | 分隔 fetcher 与值(避免歧义) |

### 3. 正则与转换

```haproxy
# 正则(基于 PCRE)
acl bad_ua hdr_reg(user-agent) -i (bot|crawler|spider)

# 字符串转换
acl admin hdr(host) -m str admin.example.com
acl admin hdr(host) -m beg admin

# 数值比较
backend bk_web
    acl overload nbsrv(bk_web) ge 2
```

### 4. map 文件

```haproxy
# /etc/haproxy/maps/region.map
api.cn-east example.com backend_cn_east
api.cn-west example.com backend_cn_west

# haproxy.cfg
http-request set-header X-Region %[str(test.region),/etc/haproxy/maps/region.map]
```

### 5. converters(字符串处理)

```haproxy
http-request set-header X-Real-IP %[src]
http-request set-header X-Host-Lower %[req.hdr(host),lower]
http-request set-var(req.my_var) %[capture.req.uri,regsub(^/old/,/new/)]
```

---

## 十一、Lua 集成

### 1. 概述

**HAProxy Lua**:HAProxy 通过 LuaJIT 支持自定义逻辑(类似 OpenResty)

- HAProxy 1.6+ 内置 LuaJIT
- 通过 `lua-load` 加载 Lua 脚本
- 提供 fetcher / converter / service / task 类型

### 2. fetcher(获取数据)

```lua
-- 加载
lua-load /etc/haproxy/lua/fetch_user.lua
```

```lua
-- /etc/haproxy/lua/fetch_user.lua
core.register_fetcher("fetch_user", function(txn)
    local user_id = txn.f:req_hdr("X-User-Id")
    -- 可查 DB / Redis / 共享内存
    return user_id or ""
end)
```

```haproxy
http-request set-var(req.user_id) %[lua.fetch_user]
```

### 3. converter(转换数据)

```lua
core.register_converter("upper", function(txn, value)
    return value:upper()
end)
```

```haproxy
http-request set-header X-Host-Up %[req.hdr(host),lua.upper]
```

### 4. service(后台服务)

```lua
core.register_service("stats_logger", function(txn)
    -- 后台运行
end)
```

### 5. task(定时任务)

```lua
core.register_task("heartbeat", function()
    -- 每秒执行一次
    core.Info("heartbeat\n")
end)
```

### 6. 共享内存 API

```lua
-- stick-table 操作
local st = core.shared_sticktable("bans")
st:set("1.2.3.4", 1, 0)
local val = st:get("1.2.3.4")
```

### 7. 与 OpenResty Lua 对比

| 维度        | HAProxy Lua       | OpenResty ngx_lua    |
|-------------|--------------------|-----------------------|
| 集成度      | 内置               | 模块                  |
| API         | core / stick-table | ngx.* / shared dict   |
| 协程        | 异步任务          | 协程                   |
| 性能        | 高                 | 高                     |
| 适用        | 流量整形、限流      | 网关层业务            |

---

## 十二、常用功能

### 1. 状态页(stats)

```haproxy
listen stats
    bind *:9000
    stats enable
    stats uri /stats
    stats refresh 5s
    stats auth admin:password
    stats admin if TRUE              # 启用 admin(危险,慎用)
```

### 2. 健康检查

```haproxy
# 主动 HTTP 检查
option httpchk GET /health HTTP/1.1\r\nHost:\ example.com
http-check expect status 200

# TCP 检查(默认)
option tcp-check

# MySQL 检查
option mysql-check user haproxy
```

### 3. 源 IP 获取(`option forwardfor`)

```haproxy
backend bk_web
    option forwardfor
    option forwardfor header X-Real-IP except 127.0.0.1
    http-request set-header X-Forwarded-For %[src]
```

### 4. stick-table 多实例同步(peers)

```haproxy
peers mycluster
    peer haproxy1 10.0.0.1:1024
    peer haproxy2 10.0.0.2:1024
    stick-table type ip size 50k expire 30s store http_req_rate(10s)

backend bk_web
    stick-table type ip size 50k expire 30s store http_req_rate(10s) peers mycluster
```

### 5. 响应缓存(HAProxy 2.0+)

```haproxy
global
    cache my_cache
        total-max-size 1024
        max-age 600
        process-shared on

backend bk_web
    http-request cache-use my_cache
    http-response cache-store my_cache
```

### 6. 程序(program)外部调用

```haproxy
program healthcheck
    command /usr/local/bin/healthcheck.sh
```

### 7. mailers

```haproxy
mailers mymailers
    mailer smtp1 10.0.0.1:25

frontend ft_web
    errorloc 503 /errors/503.http
```

### 8. http-errors

```haproxy
http-errors err503
    errorfile 503 /etc/haproxy/errors/503.http
```

---

## 十三、缓存策略

### 1. 多级缓存

```text
请求 → HAProxy 进程内缓存(cache) → stick-table → upstream
```

### 2. cache 段配置

```haproxy
global
    cache my_cache
        total-max-size 1024        # 总内存(MB)
        max-age 600                # 默认最大 TTL
        max-object-size 1024       # 单对象上限(KB)
        process-shared on          # 跨 Worker 共享
```

### 3. 缓存应用

```haproxy
backend bk_web
    http-request cache-use my_cache
    http-response cache-store my_cache
```

### 4. 缓存模式

**被动缓存**(默认):

```haproxy
http-response cache-store my_cache
```

**主动失效**(`http-request` 标记):

```haproxy
acl no_cache method POST PUT DELETE
http-request cache-use my_cache unless no_cache
```

### 5. 缓存击穿 / 雪崩

```haproxy
backend bk_web
    option redispatch                    # 失败重派
    retries 3
    http-request deny deny_status 503 if { nbsrv(bk_web) eq 0 }
```

---

## 十四、性能优化

### 1. 全局参数

```haproxy
global
    maxconn 100000
    nbthread 4                          # 1-8 倍 CPU 核数
    cpu-map auto:1/1-4                  # CPU 亲和
    daemon
    tune.bufsize 16384                   # 缓冲大小
    tune.maxrewrite 1024                 # 重写 buffer
    tune.recvbufsize 16384
    tune.sendbufsize 16384
    tune.pipesize 16384
```

### 2. 连接复用

```haproxy
backend bk_web
    option http-keep-alive
    http-reuse aggressive                # 复用上游连接
    timeout http-keep-alive 10s
    timeout http-request 10s
    timeout connect 5s
    timeout server 60s
```

### 3. SSL 优化

```haproxy
global
    ssl-default-bind-ciphersuites TLS_AES_128_GCM_SHA256:TLS_AES_256_GCM_SHA384
    ssl-default-bind-options ssl-min-ver TLSv1.2 no-tls-tickets

    # SSL session cache
    ssl-session-cache shared my_sess:1g
    ssl-session-cache-timeout 300
```

### 4. 日志优化

```haproxy
global
    log 192.168.1.100:514 local0 info     # 不开 debug
defaults
    option dontlognull
    option log-separate-errors
```

### 5. 性能基准

| 操作                          | 量级          |
|-------------------------------|---------------|
| L4 TCP 转发(短连接)         | ~200K CPS     |
| L4 TCP 转发(长连接)         | 数百万并发    |
| L7 HTTP 转发                 | ~50K-100K RPS|
| L7 HTTPS 卸载                 | ~30K-50K RPS |
| L7 + 复杂 ACL                | ~10K-30K RPS |

(随硬件不同)

---

## 十五、WAF / 网关层应用

### 1. IP 黑名单

```haproxy
frontend ft_web
    acl blacklist src -f /etc/haproxy/blacklist.lst
    http-request deny if blacklist
```

### 2. 限流(QPS / 并发)

```haproxy
backend bk_api
    stick-table type ip size 50k expire 30s store http_req_rate(10s)

    http-request track-sc0 src
    http-request deny if { sc_http_req_rate(0) gt 100 }
    http-request deny deny_status 429
```

### 3. 并发连接限制

```haproxy
backend bk_web
    stick-table type ip size 50k expire 30s store conn_cur

    tcp-request content track-sc0 src
    tcp-request content reject if { sc_conn_cur(0) gt 10 }
```

### 4. 鉴权(Basic / 子请求)

```haproxy
userlist auth_users
    user admin password $6$...

frontend ft_admin
    bind *:8080
    acl auth_ok http_auth(auth_users)
    http-request auth realm "Admin" unless auth_ok
```

子请求鉴权:

```haproxy
frontend ft_api
    bind *:80
    http-request set-header X-Token %[req.hdr(Authorization)]

    acl auth_ok capture.req.hdr(0) -m found
    http-request deny if !auth_ok
```

### 5. Header 注入 / 改写

```haproxy
http-request set-header X-Real-IP %[src]
http-request set-header X-Forwarded-Proto https if { ssl_fc }
http-request del-header X-Internal

http-response set-header X-Frame-Options DENY
http-response del-header Server
```

### 6. 灰度 / A/B

```haproxy
acl canary_user req.cook(canary) -m found
use_backend bk_canary if canary_user
default_backend bk_stable
```

### 7. 防爬虫 / UA 过滤

```haproxy
acl bad_ua hdr_reg(user-agent) -i (bot|crawler|spider|scrapy)
http-request deny if bad_ua
```

### 8. SQL 注入 / XSS 防御

```haproxy
acl sql_inj path_reg -i (union|select|insert|drop|delete).*from
acl xss_payload path_reg -i (<script|javascript:)
http-request deny if sql_inj or xss_payload
```

---

## 十六、调试与监控

### 1. 日志

```haproxy
global
    log 127.0.0.1:514 local0

defaults
    option httplog
    log-format "%ci:%cp [%tr] %ft %b/%s %Tq %Tw %Tc/%Tt %B %CC %CS %tsc %ac/%fc/%bc/%sc/%rc %sq/%bq %hr %hs %{+Q}r"
```

### 2. stats page

访问 `http://lb:9000/stats`:

- 实时 QPS / 连接数 / 错误率
- 各 server 健康状态
- frontend / backend 流量统计

### 3. Prometheus exporter

```haproxy
frontend ft_metrics
    bind *:9101
    http-request use-service prometheus-exporter if { path /metrics }
```

### 4. Runtime API

```bash
# 通过 stats socket
echo "show stat" | socat stdio /var/run/haproxy.sock
echo "show info" | socat stdio /var/run/haproxy.sock

# 动态调整
echo "set maxconn frontend ft_web 50000" | socat stdio /var/run/haproxy.sock
echo "enable server bk_web/web1" | socat stdio /var/run/haproxy.sock
echo "disable server bk_web/web1" | socat stdio /var/run/haproxy.sock

# 平滑 drain
echo "set server bk_web/web1 state drain" | socat stdio /var/run/haproxy.sock
```

### 5. debug 日志

```haproxy
global
    debug
    log 127.0.0.1:514 local0 debug
```

**生产不开 debug**,会拖慢性能。

### 6. 火焰图

```bash
# perf 抓 CPU 采样
perf record -F 99 -p $(pgrep -n haproxy) -g -- sleep 30
perf script | ./stackcollapse-perf.pl > out.folded
./flamegraph.pl out.folded > haproxy.svg
```

---

## 十七、常见陷阱

### 1. `mode tcp` 时不能用 HTTP 指令

```haproxy
# ❌ 错:mode tcp 下用 http-request
frontend ft_tcp
    mode tcp
    http-request set-header X-Foo bar          # 不可用

# ✅ 改用 mode http 或 tcp-request content
frontend ft_tcp
    mode tcp
    tcp-request content set-header X-Foo bar   # 也不行
    # mode tcp 下不能改 Header
```

### 2. health-check 误杀

```haproxy
# 默认 health-check 是 TCP 三次握手
# 应用启动慢时,启动期会判定为 down
server web1 10.0.0.1:8080 check inter 5s rise 3 fall 2 slowstart 30s
```

### 3. balance 算法选错

```haproxy
# 短连接: round-robin 即可
# 长连接(mysql): least_conn
# 缓存亲和: uri / url_param / hdr / source
backend bk_cache
    balance uri
    hash-type consistent
```

### 4. stick-table size 不足

```haproxy
# 太小 → LRU 淘汰 → 限流失效
stick-table type ip size 200k expire 30s store http_req_rate(10s)
```

### 5. maxconn 与 ulimit

```haproxy
# maxconn 需小于 ulimit -n
# /etc/security/limits.conf
haproxy  soft  nofile  100000
haproxy  hard  nofile  100000
```

### 6. SSL session 缓存未启用

```haproxy
# 不开 session cache → 每次都重建连接,慢
global
    ssl-session-cache shared my_sess:1g
```

### 7. reload 配置不生效

```bash
haproxy -c -f /etc/haproxy/haproxy.cfg    # 先校验
systemctl reload haproxy                  # 平滑热加载
```

---

## 十八、HAProxy vs 其他网关

| 维度          | HAProxy         | Nginx             | Envoy            | OpenResty / Kong | LVS              |
|---------------|-----------------|-------------------|------------------|-------------------|------------------|
| 语言          | C               | C                 | C++              | C + Lua          | 内核 C           |
| 性能          | **极高**        | 高                 | 高               | 高                | **极高**         |
| L4 / L7       | L4 + L7 都强    | L7 强 + L4(stream)| L4 + L7 都强    | L7 强             | L4              |
| 健康检查      | **强**(主动)    | 弱(被动)          | **强**(主动)    | 弱                | 弱              |
| 动态配置      | Runtime API     | 弱(reload)        | **强(xDS)**     | Lua 热加载        | 弱              |
| 配置          | haproxy.cfg     | nginx.conf         | YAML / xDS      | 配置 + Lua        | ipvsadm          |
| 监控          | stats / Prometheus | stub_status    | admin / stats    | 自定义            | –                |
| 适用          | L4/L7 LB,Web/API | 反代、网关         | 服务网格         | 网关层编程        | 纯 L4 透传       |

---

## 十九、部署与运维

### 1. 安装

**apt / yum**:

```bash
apt install haproxy
yum install haproxy
systemctl enable --now haproxy
```

**官方源**:

```bash
# Debian/Ubuntu
wget https://haproxy.debian.net/keys/bdb0a925.asc
apt-key add bdb0a925.asc
echo "deb https://haproxy.debian.net bullseye-backports main" > /etc/apt/sources.list.d/haproxy.list
apt update && apt install haproxy

# CentOS/RHEL
yum install yum-plugin-copr
yum copr enable netcoder/haproxy
yum install haproxy
```

**源码编译**:

```bash
wget https://www.haproxy.org/download/2.8/src/haproxy-2.8.0.tar.gz
tar xf haproxy-2.8.0.tar.gz
cd haproxy-2.8.0
make TARGET=linux-glibc USE_OPENSSL=1 USE_ZLIB=1 USE_LUA=1 USE_PROMETHEUS=1
make install PREFIX=/usr/local/haproxy
```

### 2. 目录结构

```text
/etc/haproxy/
├── haproxy.cfg          # 主配置
├── maps/                # map 文件
├── certs/               # SSL 证书
└── errors/              # 自定义错误页

/var/log/haproxy/        # 日志(若有)
                       # 默认走 syslog
/var/run/haproxy.pid     # PID
/var/run/haproxy.sock    # stats socket
```

### 3. haproxy.cfg 结构

```haproxy
global
    daemon
    maxconn 100000
    nbthread 4
    user haproxy
    group haproxy
    log 127.0.0.1 local0
    stats socket /var/run/haproxy.sock mode 660 level admin

defaults
    mode http
    log global
    balance roundrobin
    option httplog
    option forwardfor
    timeout connect 5s
    timeout client 30s
    timeout server 30s

frontend ft_web
    bind *:80
    default_backend bk_web

backend bk_web
    server web1 10.0.0.1:80 check
    server web2 10.0.0.2:80 check

listen stats
    bind *:9000
    stats enable
    stats uri /stats
    stats refresh 10s
```

### 4. 常用命令

```bash
# 测试配置
haproxy -c -f /etc/haproxy/haproxy.cfg

# 前台运行(调试)
haproxy -db -f /etc/haproxy/haproxy.cfg

# 启动 / 停止 / 重载
haproxy -D -f /etc/haproxy/haproxy.cfg
haproxy -f /etc/haproxy/haproxy.cfg -sf $(cat /var/run/haproxy.pid)   # 优雅重启
systemctl reload haproxy

# 看版本
haproxy -v

# 编译参数
haproxy -vv
```

### 5. systemd

```bash
systemctl status haproxy
systemctl reload haproxy        # 平滑热加载
journalctl -u haproxy -f
```

### 6. 平滑升级

```bash
# 1. 编译新版本
make install PREFIX=/usr/local/haproxy-2.8

# 2. 替换符号链接
ln -sfn /usr/local/haproxy-2.8 /usr/local/haproxy

# 3. 平滑重启
haproxy -f /etc/haproxy/haproxy.cfg -sf $(cat /var/run/haproxy.pid)
```

### 7. 日志聚合

```bash
# rsyslog 配置 /etc/rsyslog.d/49-haproxy.conf
$ModLoad imudp
$UDPServerRun 514
local0.* /var/log/haproxy.log
& stop
```

---

## 二十、核心要点速记

- **HAProxy = TCP + HTTP LB**,事件驱动 + 多线程
- **Master + Worker(多线程)**,`nbthread 1-8 倍 CPU 核数`
- **连接固定到线程**,避免锁竞争
- **`mode http / tcp / health`** 三种模式
- **`frontend + backend + listen`** 配置三段
- **`use_backend`** 决定路由,基于 ACL 匹配
- **ACL 极其强大**:`path_beg` / `hdr_dom` / `src` / `nbsrv` / `method` 等
- **`balance`**:`roundrobin` / `leastconn` / `uri` / `source` / `random` / `hdr`
- **stick-table**:Worker / 跨进程 / 跨机共享 K/V
- **peers 段**:多 HAProxy 共享 stick-table
- **Lua 集成**:fetcher / converter / service / task
- **响应缓存**(HAProxy 2.0+):`cache` 段 + `cache-use` / `cache-store`
- **健康检查**:主动 HTTP / TCP / MySQL 等
- **`option forwardfor`** 加 X-Forwarded-For
- **Runtime API**:通过 socket,不停机动态调整
- **stats page**:`/stats` 实时监控
- **Prometheus exporter**:内置支持
- **性能优化**:`nbthread` / `http-reuse aggressive` / `ssl-session-cache` / `cpu-map`
- **常见陷阱**:mode tcp 不能用 http 指令 / health-check 误杀 / stick-table size 不足 / maxconn 与 ulimit / SSL session cache 未启用
- **`set server ... state drain`** 优雅下线
- **`option redispatch`**:失败重派其他 server
- **`slowstart`**:刚启动 server 慢加权重
- **`hash-type consistent`**:缓存亲和一致性哈希
- **`option log-separate-errors`**:错误日志单独
- **`tune.bufsize`** 调整 buffer
- **WAF / 网关**:ACL 黑名单 / 限流(stick-table) / 鉴权(Basic / 子请求) / 灰度 / 防爬
- **`option dontlognull`**:不记空连接
- **HAProxy vs Nginx**:HAProxy 健康检查强、active check 强、Nginx 反代静态强
- **HAProxy vs Envoy**:Envoy xDS 动态配置,HAProxy Runtime API 弱动态
- **HAProxy vs LVS**:HAProxy 是用户态,LVS 是内核态;HAProxy 健康检查强,LVS 纯 L4
- **`haproxy -c`** 先校验配置再 reload
- **`haproxy -sf $(cat pid)`** 平滑重启
- **健康检查 `inter` 默认 2s,生产可设 5s 减负**
