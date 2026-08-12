# Nginx

## 一、Nginx 概述

### 什么是 Nginx

**Nginx**:高性能的 HTTP / 反向代理 / 邮件代理 / TCP-UDP 代理服务器

- Igor Sysoev 2004 年开源,Rambler 公司
- BSD-like 协议,现由 F5 维护
- 事件驱动 + 异步非阻塞 I/O
- 占据 Web 服务器市场份额前列(Netcraft 常年第一)
- 关键口号:**"高并发、低内存、稳如老狗"**

### 核心组件

| 组件                  | 说明                                |
|-----------------------|-------------------------------------|
| **Nginx Core**        | 进程管理、配置加载、事件循环         |
| **http 模块**         | HTTP 协议解析、HTTP 请求处理         |
| **stream 模块**       | TCP / UDP 代理(L4 转发)             |
| **mail 模块**         | 邮件代理(SMTP/POP3/IMAP)           |
| **event 模块**        | epoll / kqueue / select 事件驱动     |

### Nginx vs 其他 Web 服务器

| 维度        | Nginx              | Apache             | Lighttpd          |
|-------------|--------------------|--------------------|-------------------|
| 架构        | 事件驱动异步         | 进程/线程(MPM)      | 事件驱动           |
| 并发        | **高**             | 中                  | 中                 |
| 内存占用    | **低**             | 高                  | 低                 |
| 配置        | 单一 nginx.conf    | .htaccess 分布式    | 单一文件           |
| 适用        | 反代、网关、静态     | 传统动态站点         | 轻量静态           |
| 模块        | 静态/动态编译        | DSO 动态加载        | 静态编译            |

---

## 二、架构与运行机制

### 1. 进程模型

```text
Master 进程
├── Worker 1 (事件循环)
├── Worker 2 (事件循环)
├── Worker 3 (事件循环)
└── ...
```

- **Master**:管理 Worker,不处理请求
- **Worker**:每个 Worker 一个事件循环,处理请求
- **Worker 数**:`worker_processes auto` (一般等于 CPU 核数)
- **请求分发**:每个请求只在一个 Worker 中处理(accept_mutex 串行化)
- **缓存加载器**:启动时一次性加载磁盘缓存到内存

### 2. 事件循环

**Nginx 的"高并发"= 事件驱动 + 异步 I/O**

- 一个 Worker 可处理上万连接
- 基于 epoll(Linux)/ kqueue(BSD)/ select
- I/O 阻塞事件 → 注册回调 → 事件就绪 → 回调执行

```text
请求 1 ──┐
请求 2 ──┤── 共用一个 Worker,通过事件循环分发
请求 3 ──┘
```

### 3. 内存模型

**Worker 间部分共享,部分独立**:

- **共享内存** (shared memory zones):基于共享内存的 K/V / 缓存 / 计数器
- **进程独立**:每个 Worker 自己的连接池、内存池

---

## 三、模块体系

### 1. 模块分类

```text
Nginx 模块
├── Core (核心)         # events, error_log, worker_processes
├── HTTP                # http, server, location, proxy_pass
├── Stream              # stream, upstream (L4)
├── Mail                # mail 块
└── Third-Party         # 第三方:模块编译或 dynamic module
```

### 2. HTTP 子模块分类

```text
http 模块
├── handlers        # 处理请求(rewrite, return, proxy_pass)
├── filters         # 过滤响应(gzip, sub_filter)
├── upstream        # 负载均衡(round-robin, least_conn)
├── load-balancer   # 调度
└── access          # limit_req, limit_conn
```

### 3. 模块编译

**静态编译**(传统):

```bash
./configure --prefix=/usr/local/nginx \
    --with-http_stub_status_module \
    --with-http_ssl_module \
    --with-http_v2_module
make && make install
```

**动态加载**(Nginx 1.9.11+,推荐):

```bash
./configure --with-compat --add-dynamic-module=../module-src
# nginx.conf 中加载
load_module modules/ngx_http_mod_module.so;
```

---

## 四、请求处理阶段 (Phases)

### 1. 阶段总览

```text
请求进入
   │
   ▼
┌──────────────────────┐
│ POST_READ            │  realip / limit_req
└──────────────────────┘
   ▼
┌──────────────────────┐
│ SERVER_REWRITE       │  rewrite(在 server 块)
└──────────────────────┘
   ▼
┌──────────────────────┐
│ FIND_CONFIG          │  location 匹配
└──────────────────────┘
   ▼
┌──────────────────────┐
│ REWRITE              │  rewrite(在 location 块)
└──────────────────────┘
   ▼
┌──────────────────────┐
│ POST_REWRITE         │
└──────────────────────┘
   ▼
┌──────────────────────┐
│ PREACCESS            │  limit_conn / auth_basic
└──────────────────────┘
   ▼
┌──────────────────────┐
│ ACCESS               │  allow / deny / auth_request
└──────────────────────┘
   ▼
┌──────────────────────┐
│ POST_ACCESS          │
└──────────────────────┘
   ▼
┌──────────────────────┐
│ PRECONTENT           │  try_files / mirror
└──────────────────────┘
   ▼
┌──────────────────────┐
│ CONTENT              │  proxy_pass / content_by_lua
└──────────────────────┘
   ▼
┌──────────────────────┐
│ LOG                  │  log_format / access_log
└──────────────────────┘
```

### 2. 阶段详解

| 阶段                | 时机                | 常用模块 / 指令            |
|---------------------|---------------------|----------------------------|
| **POST_READ**       | 收到请求首行         | `realip_module`, `limit_req` |
| **SERVER_REWRITE**  | server 块重写       | `rewrite`, `set`           |
| **FIND_CONFIG**     | 匹配 location       | (系统内部)                  |
| **REWRITE**         | location 块重写     | `rewrite`, `set`           |
| **PREACCESS**       | 访问前检查           | `limit_conn`, `limit_req`  |
| **ACCESS**          | 访问控制             | `allow`, `deny`, `auth_basic` |
| **PRECONTENT**      | 内容生成前           | `try_files`, `mirror`      |
| **CONTENT**         | **生成内容主战场**   | `proxy_pass`, `static`     |
| **LOG**             | 日志阶段             | `access_log`, `log_format` |

### 3. 阶段使用方式

```nginx
# 阶段对应模块:用对应模块的指令即在对应阶段生效
server {
    listen 80;

    # SERVER_REWRITE 阶段
    set $foo "bar";

    # ACCESS 阶段
    allow 192.168.1.0/24;
    deny all;

    location / {
        # REWRITE 阶段
        rewrite ^/old /new permanent;

        # CONTENT 阶段
        proxy_pass http://backend;
    }
}
```

---

## 五、常用指令

### 1. listen 与 server_name

```nginx
server {
    listen 80;
    listen 443 ssl http2;
    server_name example.com www.example.com;

    ssl_certificate     /etc/nginx/ssl/example.crt;
    ssl_certificate_key /etc/nginx/ssl/example.key;
}
```

### 2. location 匹配

| 前缀 | 含义 | 优先级 |
| ---- | ---- | ---- |
| `=` | 精确匹配 | 1(最高) |
| `^~` | 前缀匹配,不再正则 | 2 |
| `~` | 正则(区分大小写) | 3 |
| `~*` | 正则(不区分大小写) | 3 |
| 无 | 前缀匹配 | 4(最低) |

```nginx
location = /favicon.ico { ... }       # 精确
location ^~ /static/ { ... }          # 前缀优先
location ~ \.php$ { ... }             # 正则
location /api/ { ... }                # 普通前缀
```

### 3. rewrite / return / try_files

```nginx
# rewrite 正则重写(返回码可选)
rewrite ^/old/(.*)$ /new/$1 permanent;     # 301
rewrite ^/api/(.*)$ /$1 break;             # break:不再走后续 rewrite

# return 直接返回
return 301 https://$host$request_uri;
return 404;

# try_files 兜底
try_files $uri $uri/ /index.html;
try_files $uri @fallback;                  # @ 命名 location
```

### 4. proxy_pass 与 upstream

```nginx
upstream backend {
    server 10.0.0.1:8080;
    server 10.0.0.2:8080;
    keepalive 32;
}

location / {
    proxy_pass http://backend;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_connect_timeout 5s;
    proxy_read_timeout 60s;
}
```

### 5. 变量

```nginx
$host              # Host 头(无端口)
$server_name       # 匹配到的 server_name
$request_uri       # 完整 URI(含参数)
$uri               # 当前 URI(不含参数)
$args              # 查询参数
$arg_name          # ?name=xxx
$http_header_name  # 请求头
$remote_addr       # 客户端 IP
$proxy_add_x_forwarded_for  # 拼接 X-Forwarded-For
$upstream_addr     # upstream 实际地址
$upstream_status   # upstream 状态码
$upstream_response_time  # upstream 响应时间
```

---

## 六、共享内存 (shared memory zones)

### 1. 概述

**共享内存区**:Worker 间共享的数据结构

- 分配在共享内存
- **所有 Worker 可见**
- 用 `zone` 关键字指定
- 适合缓存、限流、计数器

### 2. 配置示例

```nginx
# 共享字典(类似 OpenResty 的 lua_shared_dict)
proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=my_cache:10m max_size=1g inactive=60m;

# 限流区
limit_req_zone $binary_remote_addr zone=rate_limit:10m rate=10r/s;

# 连接限制区
limit_conn_zone $binary_remote_addr zone=conn_limit:10m;
```

### 3. API

```nginx
# 共享内存不直接读写,通过模块 API:
proxy_cache    my_cache          # 缓存
limit_req      zone=rate_limit burst=20 nodelay;
limit_conn     conn_limit 10;
```

### 4. 应用场景

| 场景         | 做法                              |
|--------------|-----------------------------------|
| 反代缓存     | `proxy_cache_path`                |
| 限流         | `limit_req_zone` + `limit_req`   |
| 防并发连接   | `limit_conn_zone` + `limit_conn`  |
| upstream 状态 | `zone` 关键字                     |
| sticky cookie | `sticky` 指令                     |

### 5. 限制

- 总大小受限于 `worker_rlimit_nofile` 与物理内存
- `keys_zone` 仅存索引,实际值存磁盘或内存池
- 复杂数据需自定义模块

---

## 七、upstream 与负载均衡

### 1. upstream 块

```nginx
upstream backend {
    server 10.0.0.1:8080 weight=3;
    server 10.0.0.2:8080 weight=1;
    server 10.0.0.3:8080 backup;          # 备用
    server 10.0.0.4:8080 down;            # 摘除
    keepalive 32;                          # 保持上游连接
    keepalive_requests 100;
    keepalive_timeout 60s;
}
```

### 2. 调度算法

```nginx
# 默认 round-robin(加权)
upstream a { server 10.0.0.1:8080; server 10.0.0.2:8080; }

# least_conn
upstream b { least_conn; server ...; }

# ip_hash(同一 IP → 同一 upstream)
upstream c { ip_hash; server ...; }

# hash(指定 key 哈希,常用于缓存亲和)
upstream d { hash $request_uri consistent; server ...; }

# random(随机两台选响应最快的,商业版)
upstream e { random two; server ...; }
```

### 3. 健康检查

**被动**(默认,生产请求触发):

```nginx
upstream backend {
    server 10.0.0.1:8080 max_fails=3 fail_timeout=30s;
    server 10.0.0.2:8080;
}
```

**主动**(商业版 / nginx-plus;开源需 `nginx_upstream_check_module`):

```nginx
upstream backend {
    server 10.0.0.1:8080;
    check interval=5000 rise=2 fall=3 timeout=1000 type=http;
    check_http_send "GET /health HTTP/1.0\r\n\r\n";
    check_http_expect_alive http_2xx;
}
```

### 4. keepalive 连接池

```nginx
upstream backend {
    server 10.0.0.1:8080;
    keepalive 32;                # 每个 Worker 保持 32 个到上游的长连接
}

location / {
    proxy_pass http://backend;
    proxy_http_version 1.1;      # 必须 HTTP/1.1
    proxy_set_header Connection "";  # 关闭短连接头
}
```

### 5. proxy_pass 关键点

```nginx
# 末尾 / 行为
location /api/ { proxy_pass http://backend; }    # /api/foo → http://backend/foo
location /api/ { proxy_pass http://backend/; }   # /api/foo → http://backend/foo
location /api  { proxy_pass http://backend; }    # /api/foo → http://backend/api/foo
```

---

## 八、子请求 (Subrequest)

### 1. 内部子请求

**子请求**:在不中断当前请求的前提下,内部触发其他 location 处理

```nginx
location /api/ {
    # auth_request 触发子请求做鉴权
    auth_request /auth;

    # mirror 把请求镜像到其他 location(不影响主响应)
    mirror /mirror;

    proxy_pass http://backend;
}

location = /auth {
    internal;                 # 仅内部可访问
    proxy_pass http://auth-service/verify;
    proxy_pass_request_body off;
    proxy_set_header Content-Length "";
}
```

### 2. subrequest 典型用法

- **auth_request**:鉴权子请求
- **mirror**:请求镜像(用于流量复制、灰度)
- **error_page 触发**:错误页走子请求

```nginx
location / {
    error_page 502 = @fallback;     # 502 时子请求到 fallback
}

location @fallback {
    proxy_pass http://backup;
}
```

### 3. 子请求 vs proxy_pass

| 维度        | 子请求 (auth_request / mirror) | proxy_pass 真实转发     |
|-------------|--------------------------------|--------------------------|
| 配置        | 走 Nginx location             | 直接连后端                |
| 性能        | 极快(共享内存)                | 一次完整 HTTP 调用        |
| 失败影响    | 仅影响当前请求                 | 主响应                   |
| 适用        | 鉴权、镜像、灰度               | 正常业务转发              |

---

## 九、健康检查与重试

### 1. 健康检查

详见 §七.3。

### 2. proxy_next_upstream 重试

```nginx
location / {
    proxy_pass http://backend;
    proxy_next_upstream error timeout http_502 http_503;
    proxy_next_upstream_tries 3;
    proxy_next_upstream_timeout 10s;
}
```

`error / timeout / invalid_header / http_502 / http_503 / http_504 / http_403 / http_404 / http_429 / non_idempotent`

### 3. resolver DNS 刷新

```nginx
location / {
    resolver 10.0.0.1 valid=30s;       # DNS TTL
    resolver_timeout 5s;
    set $upstream http://dynamic-backend.example.com;
    proxy_pass $upstream;
}
```

---

## 十、正则与变量

### 1. location 正则

```nginx
location ~ \.php$ { ... }              # 正则,区分大小写
location ~* \.(gif|jpg|png)$ { ... }   # 正则,不区分大小写
location ~ ^/api/v(\d+)/(.*)$ { ... }  # 带捕获
```

### 2. rewrite 正则

```nginx
# 捕获组 + 重写
rewrite ^/user/(\d+)/?$ /profile?id=$1 last;

# 多捕获
if ($http_user_agent ~ MSIE) {
    rewrite ^ /old-browser.html last;
}
```

### 3. if 指令(慎用)

```nginx
if ($args ~ "debug=1") {
    set $debug 1;
}

if ($host = example.com) {
    return 301 https://www.example.com$request_uri;
}
```

**`if` 是邪恶的**(if is evil)——常见陷阱见 §十七。

### 4. map 指令(推荐替代 if)

```nginx
http {
    map $http_user_agent $is_mobile {
        default 0;
        ~*android|iphone 1;
    }

    server {
        if ($is_mobile) {
            rewrite ^ /mobile/ redirect;
        }
    }
}
```

---

## 十一、Nginx 模块开发 (C)

### 1. 模块结构

```c
#include <ngx_config.h>
#include <ngx_core.h>
#include <ngx_http.h>

static ngx_int_t ngx_http_hello_handler(ngx_http_request_t *r);
static char *ngx_http_hello(ngx_conf_t *cf, ngx_command_t *cmd, void *conf);

static ngx_command_t ngx_http_hello_commands[] = {
    {
        ngx_string("hello"),
        NGX_HTTP_LOC_CONF | NGX_CONF_NOARGS,
        ngx_http_hello,
        0,
        0,
        NULL
    },
    ngx_null_command
};

static ngx_http_module_t ngx_http_hello_module_ctx = {
    NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
};

ngx_module_t ngx_http_hello_module = {
    NGX_MODULE_V1,
    &ngx_http_hello_module_ctx,
    ngx_http_hello_commands,
    NGX_HTTP_MODULE,
    NULL, NULL, NULL, NULL, NULL, NULL, NULL,
    NGX_MODULE_V1_PADDING
};
```

### 2. handler 实现

```c
static ngx_int_t
ngx_http_hello_handler(ngx_http_request_t *r)
{
    ngx_int_t    rc;
    ngx_buf_t   *b;
    ngx_chain_t  out;

    r->headers_out.content_type.len = sizeof("text/plain") - 1;
    r->headers_out.content_type.data = (u_char *) "text/plain";
    r->headers_out.status = NGX_HTTP_OK;
    r->headers_out.content_length_n = 5;

    b = ngx_create_temp_buf(r->pool, 5);
    ngx_memcpy(b->pos, "hello", 5);
    b->last = b->pos + 5;

    out.buf = b;
    out.next = NULL;
    rc = ngx_http_send_header(r);
    return ngx_http_output_filter(r, &out);
}
```

### 3. config 脚本

```text
# config
ngx_addon_name=ngx_http_hello_module
HTTP_MODULES="$HTTP_MODULES ngx_http_hello_module"
NGX_ADDON_SRCS="$NGX_ADDON_SRCS $ngx_addon_dir/ngx_http_hello_module.c"
```

```bash
./configure --add-module=../hello-module
```

### 4. 模块类型

| 类型        | 触发时机        | 典型例子              |
|-------------|-----------------|------------------------|
| **handler** | 接收请求时       | proxy, static           |
| **filter**  | 处理响应时       | gzip, sub_filter        |
| **upstream** | 上游连接        | proxy, fastcgi          |
| **load-balancer** | 选择上游   | round-robin, ip_hash    |
| **access**  | 访问控制        | allow, deny             |

---

## 十二、常用模块

| 模块                         | 用途                       | 是否内置 |
|------------------------------|----------------------------|----------|
| **ngx_http_stub_status_module** | 状态页(`/basic_status`)  | 需编译   |
| **ngx_http_random_index_module** | 目录随机首页             | 需编译   |
| **ngx_http_autoindex_module** | 目录列表                   | 需编译   |
| **ngx_http_limit_req_module** | 限流(QPS)                  | 内置     |
| **ngx_http_limit_conn_module** | 限连接数                   | 内置     |
| **ngx_http_geo_module**     | IP / 变量映射               | 内置     |
| **ngx_http_map_module**     | 变量计算                   | 内置     |
| **ngx_http_sub_module**     | 响应体替换                 | 内置     |
| **ngx_http_auth_basic_module** | Basic 鉴权               | 内置     |
| **ngx_http_auth_request_module** | 子请求鉴权             | 需编译   |
| **ngx_http_realip_module**  | 取真实 IP                   | 内置     |
| **ngx_http_ssl_module**     | HTTPS                      | 需编译   |
| **ngx_http_v2_module**      | HTTP/2                     | 需编译   |
| **ngx_http_gzip_module**    | gzip 压缩                  | 内置     |
| **ngx_http_gzip_static_module** | 预压缩文件              | 需编译   |
| **ngx_http_proxy_module**   | 反向代理                   | 内置     |
| **ngx_http_fastcgi_module** | FastCGI(PHP-FPM)          | 内置     |
| **ngx_http_uwsgi_module**   | uWSGI(Python)             | 内置     |
| **ngx_http_grpc_module**    | gRPC 反代                  | 需编译   |
| **ngx_http_dav_module**     | WebDAV                     | 需编译   |
| **ngx_http_image_filter_module** | 图片处理              | 需编译   |
| **nginx_upstream_check_module** | upstream 主动健康检查 | 第三方   |
| **ngx_brotli**              | Brotli 压缩                | 第三方   |
| **ModSecurity-nginx**       | WAF                        | 第三方   |

---

## 十三、缓存策略

### 1. proxy_cache 配置

```nginx
proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=my_cache:10m
                 max_size=10g inactive=60m use_temp_path=off;

server {
    location / {
        proxy_pass http://backend;
        proxy_cache my_cache;
        proxy_cache_key "$scheme$proxy_host$request_uri";
        proxy_cache_valid 200 302 10m;
        proxy_cache_valid 404      1m;
        proxy_cache_min_uses 1;
        proxy_cache_bypass $arg_nocache;
        proxy_no_cache $arg_nocache;
        add_header X-Cache-Status $upstream_cache_status;
    }
}
```

### 2. 多级缓存

```text
请求 → Nginx 进程内缓存 → proxy_cache(磁盘) → upstream
```

### 3. 缓存模式

**被动缓存**(默认,首次回源后缓存):

```nginx
proxy_cache_valid 200 10m;
```

**主动预热**(启动时填充,可用 `proxy_cache_purge` 或 lua-nginx-module):

```nginx
proxy_cache_bypass $http_pragma;
```

### 4. 缓存击穿 / 雪崩

```nginx
# 加锁防止击穿
proxy_cache_lock on;             # 同一 key 只有一个请求回源
proxy_cache_lock_timeout 5s;

# 防止雪崩:不同 key 错开过期
proxy_cache_valid 200 10m;
proxy_cache_valid 200 301 302 10m;
proxy_cache_valid any 1m;
```

### 5. 缓存状态

`$upstream_cache_status`:

- `HIT` / `MISS` / `EXPIRED` / `STALE` / `UPDATING` / `REVALIDATED` / `BYPASS`

---

## 十四、性能优化

### 1. 关键参数

```nginx
worker_processes auto;                 # CPU 核数
worker_cpu_affinity auto;              # CPU 亲和
worker_rlimit_nofile 65535;

events {
    worker_connections 65535;          # 每 Worker 最大连接
    multi_accept on;                    # 一次 accept 多个连接
    use epoll;                         # Linux 用 epoll
}

http {
    sendfile on;                        # 零拷贝
    tcp_nopush on;                      # 合并包
    tcp_nodelay on;                     # 禁用 Nagle
    keepalive_timeout 65;
    types_hash_max_size 2048;

    open_file_cache max=1000 inactive=20s;
    open_file_cache_valid 30s;
    open_file_cache_min_uses 1;
}
```

### 2. upstream keepalive

```nginx
upstream backend {
    server 10.0.0.1:8080;
    keepalive 32;
}

location / {
    proxy_pass http://backend;
    proxy_http_version 1.1;
    proxy_set_header Connection "";
}
```

### 3. gzip 压缩

```nginx
gzip on;
gzip_min_length 1k;
gzip_comp_level 6;
gzip_types text/plain text/css text/xml application/json application/javascript application/xml+rss image/svg+xml;
gzip_vary on;
gzip_proxied any;
```

### 4. buffer 调优

```nginx
proxy_buffering on;                  # 缓冲到磁盘
proxy_buffer_size 4k;                # 响应头缓冲
proxy_buffers 8 16k;                 # 响应体缓冲
proxy_busy_buffers_size 32k;
proxy_temp_file_write_size 64k;
```

### 5. 性能基准

| 操作                          | 量级          |
|-------------------------------|---------------|
| 静态文件(零拷贝)              | ~100K QPS     |
| 反代转发(keepalive)           | ~50K QPS      |
| 反代转发(短连接)              | ~10K QPS      |
| gzip 压缩                     | ~30K QPS      |
| TLS 握手                      | ~5K QPS       |

(数值随硬件不同)

---

## 十五、配置优化(从各角度加速 Nginx)

本章按"配置角度"系统化梳理 Nginx 加速与调优,涵盖 worker / event / listen / location / 反代 / 缓存 / 压缩 / SSL / 静态文件 / 日志 / 系统等 11 个维度。

### 1. Worker 与 Event 调优

```nginx
worker_processes auto;                 # CPU 核数
worker_cpu_affinity auto;              # 自动绑定
worker_rlimit_nofile 65535;            # fd 上限

events {
    worker_connections 65535;                # 每 Worker 连接数
    multi_accept on;                        # 一次 accept 多个连接
    use epoll;                              # Linux 用 epoll
    accept_mutex on;                        # 多 Worker 串行化 accept
}
```

### 2. listen 套接字优化

```nginx
server {
    listen 80 backlog=2048 reuseport;        # 多 worker 复用端口
    listen 443 ssl default_server backlog=2048 reuseport;
    deferred on;                            # 延迟 accept(待数据到达)
}
```

- **`reuseport`**:Linux 3.9+ 多进程监听同一端口,**避免 accept 锁竞争**
- **`backlog=N`**:内核连接队列长度(> net.core.somaxconn 时取较小)
- **`deferred`**:accept 时内核先不唤醒,数据到达后再唤醒(适合空闲长连接)

### 3. HTTP / HTTPS 优化

```nginx
http {
    sendfile on;                            # 零拷贝
    tcp_nopush on;                          # 合并 TCP 包
    tcp_nodelay on;                         # 禁用 Nagle
    keepalive_timeout 65;
    keepalive_requests 1000;                # 单连接最大请求数

    server_tokens off;                      # 隐藏版本号(安全 + 美观)

    # HTTP/2
    listen 443 ssl http2;
    http2_max_field_size 16k;
    http2_max_header_size 32k;
    http2_body_preread_size 64k;

    # HTTP/3 / QUIC(1.25+)
    # listen 443 quic reuseport;
    # add_header Alt-Svc 'h3=":443"; ma=86400';
}
```

### 4. SSL / TLS 优化

```nginx
http {
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers c ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers on;

    # SSL session 缓存(关键)
    ssl_session_cache shared:SSL:50m;
    ssl_session_timeout 1d;
    ssl_session_tickets on;

    # OCSP stapling(加速证书链验证)
    ssl_stapling on;
    ssl_stapling_verify on;
    resolver 8.8.8.8 1.1.1.1 valid=300s;
    resolver_timeout 5s;

    # 早期数据(0-RTT)
    ssl_early_data on;

    # HTTP/2 推送(谨慎用,有时反效果)
    # http2_push_preload on;

    # 握手加速
    ssl_buffer_size 4k;                     # 大 TLS 记录 → 更快握手
    ssl_handshake_timeout 10s;
}
```

**关键**:

- TLS 1.3 优先(1-RTT)
- Session cache + tickets(0-RTT,安全场景慎用)
- OCSP stapling 减少客户端验证
- **复用会话后 TLS 握手降为 0-RTT**

### 5. 静态资源优化

```nginx
server {
    location /static/ {
        alias /var/www/static/;

        # 零拷贝 + 预读
        sendfile on;
        tcp_nopush on;
        aio threads;                         # 异步 I/O

        # 压缩
        gzip on;
        gzip_static on;                      # 优先返回预压缩 .gz
        gzip_min_length 1k;
        gzip_comp_level 6;
        gzip_vary on;
        gzip_types
       text/plain " application/javascript " "image/svg+xml " "application/wasm";

        # 浏览器缓存
        expires 365d;
        add_header Cache-Control "public, immutable, max-age=31536000";
        add_header X-Content-Type-Options nosniff;

        # 文件描述符缓存
        open_file_cache max=10000 inactive=30s;
        open_file_cache_valid 60s;
        open_file_cache_min_uses 2;
        open_file_cache_errors on;
    }

    # 大文件(视频 / 备份)单独配置
    location /download/ {
        sendfile on;
        tcp_nopush on;
        tcp_nodelay off;                     # 大文件:关 Nagle
        output_buffers 4 1m;                # 大 buffer
    }
}
```

### 6. 反代 / 上游优化

```nginx
upstream backend {
    server 10.0.0.1:8080 max_fails=3 fail_timeout=30s;
    server 10.0.0.2:8080;
    keepalive 32;                            # 连接池
    keepalive_requests 1000;
    keepalive_timeout 60s;

    # ip_hash(粘性会话)/ hash $request_uri(缓存亲和)
}

location / {
    proxy_pass http://backend;

    # 关键:HTTP/1.1 + 清空 Connection 头
    proxy_http_version 1.1;
    proxy_set_header Connection "";

    # Buffer
    proxy_buffering on;
    proxy_buffer_size 16k;
    proxy_buffers 8 32k;
    proxy_busy_buffers_size 64k;

    # 超时
    proxy_connect_timeout 5s;
    proxy_send_timeout 60s;
    proxy_read_timeout 60s;

    # 重试
    proxy_next_upstream error timeout http_502 http_503;
    proxy_next_upstream_tries 3;
    proxy_next_upstream_timeout 10s;

    # 不要缓冲临时文件到磁盘
    proxy_max_temp_file_size 0;

    # 隐藏 upstream 响应头
    proxy_hide_header X-Powered-By;
    proxy_hide_header Server;
}
```

### 7. 压缩优化

```nginx
http {
    gzip on;
    gzip_min_length 1024;                    # 小于 1KB 不压
    gzip_comp_level 5;                       # 1-9,6 是性价比最优
    gzip_vary on;
    gzip_proxied any;
    gzip_types
        text/plain
        text/css
        text/xml
        application/json
        application/javascript
        application/xml+rss
        application/atom+xml
        image/svg+xml
        application/wasm;

    # 动态请求压缩
    gzip_disable "msie6";                    # 旧 IE 不压

    # Brotli 压缩(模块)
    brotli on;
    brotli_comp_level 5;
    brotli_types text/plain text/css application/json application/javascript;
}
```

### 8. 缓存优化(proxy_cache)

```nginx
http {
    # 路径 + 索引
    proxy_cache_path /var/cache/nginx
        levels=1:2
        keys_zone=my_cache:100m                # 100MB 元数据
        max_size=10g                             # 10GB 数据上限
        inactive=60m                            # 60 分钟未用淘汰
        use_temp_path=off;

    server {
        location / {
            proxy_pass http://backend;
            proxy_cache my_cache;
            proxy_cache_key "$scheme$proxy_host$request_uri";
            proxy_cache_valid 200 302 10m;
            proxy_cache_valid 404 1m;
            proxy_cache_lock on;                # 防击穿
            proxy_cache_lock_timeout 5s;
            proxy_cache_min_uses 1;             # 1 次后开始缓存
            proxy_cache_bypass $http_pragma $http_authorization;
            proxy_no_cache $http_authorization; # 鉴权请求不缓存
            add_header X-Cache-Status $upstream_cache_status;
        }
    }
}
```

### 9. location 匹配优化

```nginx
server {
    # ✅ 静态规则在前(精确 > 前缀 > 正则)
    location = /favicon.ico {  ... }
    location = /health { access /; }
    location ^~ /static/ { ... }              # 前缀优先,避免正则扫描
    location ~* \.(jpg|jpeg|png|css|js|gz)$ {
        expires 365d;
    }

    # ✅ API 走前缀
    location /api/ {
        proxy_pass http://api_backend;
    }

    # ❌ 避免:正则里捕获太多
    # location ~ ^/api/v(\d+)/(users|orders|products|...)/(\d+)$ {
    #     proxy_pass http://api_backend/$1/$3;
    # }
    # 改用 map / try_files,正则只做兜底
}
```

**关键**:精确匹配(`=`)是最快的;`^~` 前缀匹配比正则快;正则匹配(`~` / `~*`)最慢,放最后。

### 10. if 指令优化

```nginx
# ❌ 错:用 if 做重写 / 反代
server {
    if ($request_method = POST) {
        proxy_pass http://api_backend;        # 不可靠
    }
    if ($args = "debug=1") {
        rewrite ^ /debug last;
    }
}

# ✅ 用 map / return / try_files 替代
http {
    map $request_method $is_post {
        default 0;
        POST 1;
    }
    map $args $backend {
        default "prod";
        ~*debug=1 "debug";
    }
    server {
        location / {
            return 200 "OK";
        }
        location /api/ {
            if ($backend = "debug") {
                proxy_pass http://debug_backend;
                break;
            }
            proxy_pass http://prod_backend;
        }
    }
}
```

### 11. 系统级优化

```bash
# /etc/security/limits.conf
* soft nofile 65535
* hard nofile 65535
* soft nproc 65535
* hard nproc 65535

# /etc/sysctl.conf
fs.file-max = 2097152
fs.nr_open = 2097152
net.core.somaxconn = 4096
net.core.netdev_max_backlog = 16384
net.ipv4.tcp_max_syn_backlog = 8192
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_fin_timeout = 15

# 网卡多队列(配合 RSS)
ethtool -L eth0 combined 8
echo f > /sys/class/net/eth0/queues/rx-0/rps_cpus

# CPU 频率
performance governor
echo performance > /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
```

### 12. 错误页与日志优化

```nginx
http {
    # 自定义错误页(静态)
    error_page 404 /404.html;
    error_page 500 502 503 504 /50x.html;
    location = /50x.html { internal; }

    # 异步日志(1.25+)
    log_format main escape=json '{...}';
    access_log /var/log/nginx/access.log main buffer=32k flush=5s;

    # 不记空请求
    access_log off if=$log_disabled;       # 配合 map

    # 错误日志降级
    error_log /var/log/nginx/error.log warn;
}
```

### 13. 限流与防护(性能影响)

```nginx
http {
    limit_req_zone $binary_remote_addr zone=rate:10m rate=100r/s;
    limit_conn_zone $binary_remote_addr zone=conn:10m;

    server {
        location /api/ {
            limit_req zone=rate burst=200 nodelay;
            limit_conn conn 50;
        }
    }
}
```

**关键**:限流可减少后端压力,但本身也消耗 CPU / 内存(共享字典)。

### 14. 实战:综合优化清单

```nginx
user www-data;
worker_processes auto;
worker_cpu_affinity auto;
worker_rlimit_nofile 65535;

events {
    worker_connections 65535;
    multi_accept on;
    use epoll;
    accept_mutex on;
}

http {
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    keepalive_requests 1000;
    server_tokens off;

    types_hash_max_size 2048;
    server_names_hash_max_size 4096;

    # 压缩
    gzip on;
    gzip_comp_level 5;
    gzip_min_length 1024;
    gzip_types text/plain text/css application/json application/javascript;
    gzip_vary on;

    # SSL
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers c HIGH:!aNULL:!MD5;
    ssl_session_cache shared:SSL:50m;
    ssl_session_timeout 1d;
    ssl_session_tickets on;

    # 缓存
    proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=cache:100m
                     max_size=10g inactive=60m use_temp_path=off;

    # 文件缓存
    open_file_cache max=10000 inactive=30s;
    open_file_cache_valid 60s;
    open_file_cache_min_uses 2;
    open_file_cache_errors on;

    # 日志
    log_format main '$remote_addr - $remote_user [$time_local] '
                    '"$request" $status $body_bytes_sent '
                    '"$http_referer" "$http_user_agent" '
                    'rt=$request_time uct=$upstream_connect_time '
                    'urt=$upstream_response_time';
    access_log /var/log/nginx/access.log main buffer=32k flush=5s;

    # 服务
    server {
        listen 80 default_server;
        listen 443 ssl http2 default_server backlog=2048 reuseport;
        server_name _;

        # SSL
        ssl_certificate     /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;

        # 压缩
        gzip_static on;

        # 安全头
        add_header X-Frame-Options SAMEORIGIN;
        add_header X-Content-Type-Options nosniff;
        add_header X-XSS-Protection "1; mode=block";
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

        # 静态资源
        location ^~ /static/ {
            alias /var/www/static/;
            expires 365d;
            add_header Cache-Control "public, immutable";
            access_log off;
        }

        # API
        location /api/ {
            proxy_pass http://api_backend;
            proxy_http_version 1.1;
            proxy_set_header Connection "";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

            proxy_buffering on;
            proxy_buffer_size 16k;
            proxy_buffers 8 32k;
            proxy_connect_timeout 5s;
            proxy_read_timeout 60s;

            # 缓存
            proxy_cache cache;
            proxy_cache_valid 200 10m;
            proxy_cache_lock on;
            add_header X-Cache-Status $upstream_cache_status;

            # 限流
            limit_req zone=rate burst=100 nodelay;
        }

        # 兜底
        location / {
            try_files $uri $uri/ /index.html;
        }
    }

    upstream api_backend {
        server 10.0.0.1:8080 max_fails=3 fail_timeout=30s;
        server 10.0.0.2:8080 max_fails=3 fail_timeout=30s;
        keepalive 32;
    }
}
```

### 15. 性能基线与监控

```bash
# ab 压测
ab -n 100000 -c 100 http://nginx/

# wrk 压测
wrk -t4 -c100 -d30s --latency http://nginx/

# 监控
stub_status on;             # Nginx 1.x
vts 模块                   # 详细指标 + Prometheus
```

**对比基线**:

| 优化点 | 性能提升 |
| ------ | -------- |
| sendfile | 20-50% |
| gzip 压缩 | 30-70%(响应体传输) |
| keepalive | 30-50%(反代) |
| proxy_cache 命中 | 70-99% |
| SSL session 复用 | 30-50%(TLS 握手) |
| epoll vs select | 10x(高并发) |
| reuseport | 20-40%(高并发 accept) |

---

## 十六、工作模式(Nginx 并发模型与连接池处理)

Nginx 默认是**多进程 + 单线程事件循环**模型;从 1.7.11 起,**Worker 可以启用线程池**处理阻塞 I/O。本章比较不同工作模式(单线程事件循环、Worker 线程池、多进程接收、多 Worker 共享监听)对连接池的处理方式与适用场景。

### 1. 默认工作模式:多进程 + 单线程事件循环

#### 模型

```text
Master 进程
├── Worker 1(单线程,事件循环 epoll)
├── Worker 2(单线程,事件循环 epoll)
└── Worker N(单线程,事件循环 epoll)
```

- **每个 Worker 一个事件循环**,通过 epoll 监听成千上万的连接
- **每个连接(fd)固定在某个 Worker**(accept_mutex 分配)
- **Worker 间内存独立**,通过共享内存(zone / proxy_cache / limit_req)共享

#### 配置

```nginx
worker_processes auto;            # 一般 = CPU 核数
events {
    worker_connections 65535;     # 单 Worker 最大并发连接
    multi_accept off;             # 默认 off:一次 accept 一个连接(accept_mutex)
    use epoll;
}
```

#### 连接池细节

**Accept 阶段**:

```text
                    ┌─────────────┐
                    │ Master 进程  │
                    │  bind 80    │
                    └──────┬──────┘
                           │ accept_mutex 锁(避免惊群)
              ┌────────────┼────────────┐
              ▼            ▼            ▼
          Worker 1    Worker 2     Worker 3
          accept(1)   (等待锁)    (等待锁)
```

- `accept_mutex on`(默认):同一时刻仅一个 worker accept,避免惊群
- `multi_accept on`:一个 accept 循环中尽可能多地接受连接(消耗 CPU)

**全连接池在 Worker 内的组织**:

```text
Worker 进程
├─ eventfd / 唤醒 fd
├─ epoll 实例
│   ├─ 红黑树:已注册 fd(client + upstream + listen)
│   └─ 就绪链表:本次 epoll_wait 返回的 fd
├─ 连接池(client connections)
│   ├─ c1: client 1.1.1.1:50001 → backend 10.0.0.1:80
│   ├─ c2: client 1.1.1.1:50002 → backend 10.0.0.1:80
│   ├─ c3: client 1.1.1.2:60001 → backend 10.0.0.2:80
│   └─ ...
├─ 上游 keepalive 池(连接复用)
│   ├─ k1: nginx:random → backend 10.0.0.1:80(空闲,可复用)
│   └─ k2: nginx:random → backend 10.0.0.2:80(空闲,可复用)
└─ 共享内存(shm)
    ├─ proxy_cache_path keys_zone
    ├─ limit_req zone
    └─ limit_conn zone
```

#### 优劣

| 优点 | 缺点 |
| ---- | ---- |
| **避免锁竞争**:每连接固定一个 worker | 阻塞 I/O 阻塞整个 worker(只能服务其它连接) |
| **无线程切换**:高并发性能极佳 | CPU 利用不均(部分 worker 可能负载重) |
| **内存隔离**:worker 崩溃不影响其他 | 单 worker 阻塞 = 该 worker 上所有连接卡住 |

### 2. Worker 线程池(异步线程池)

**问题**:某些 I/O 操作**无法异步**(内核不支持非阻塞),如:

- 大文件磁盘读写(常规 read/write 在大文件下会阻塞)
- `open()` 慢设备(网络文件系统、NFS)
- `stat()` / `readdir()` 文件元数据读取

**解决方案**(**Nginx 1.7.11+**):为阻塞 I/O 启用独立线程池,不让事件循环阻塞。

#### 配置

```nginx
# /etc/nginx/nginx.conf
thread_pool default_pool threads=32 max_queue=65536;

events {
    worker_connections 65535;
}

http {
    # 异步文件 I/O(用线程池)
    aio threads;                         # 文件 I/O 走线程池
    sendfile on;

    server {
        location /bigfile {
            aio threads;
            sendfile off;                # 大文件不用 sendfile
            output_buffers 2 256k;
        }
    }
}
```

#### 工作模式

```text
Worker 进程
├─ 主线程(事件循环)
│   ├─ epoll_wait() 监听 fd
│   └─ 处理网络事件(read / write)
│
└─ 线程池(默认 default_pool,32 线程 + 65536 队列)
    ├─ Thread 1 ──>  文件 AIO、阻塞 readdir 等
    ├─ Thread 2 ──>
    ├─ Thread 3 ──>
    └─ ... ──>
```

- **主线程不阻塞**:遇到阻塞 I/O,把任务交给线程池
- **线程完成任务 → 通过 eventfd 通知主线程** → 唤醒 epoll_wait → 处理结果
- **线程池独立,事件循环不被阻塞**

#### 适用场景

- **静态大文件服务**(GB 级视频 / 安装包)
- **NFS / 慢磁盘**文件系统
- **大量 `openat()` 调用**的场景

#### 优劣

| 优点 | 缺点 |
| ---- | ---- |
| 主线程不阻塞 | 线程有创建 / 上下文切换成本 |
| 大文件 I/O 性能显著提升 | 线程多了反而慢(经验值 16-64) |
| 慢设备不影响主循环 | 增加内存占用 |

#### 调优经验

| threads | max_queue | 适用 |
| ------- | --------- | ---- |
| 8 | 65536 | 4-8 CPU 核 |
| 16 | 65536 | 8-16 CPU 核 |
| 32 | 65536 | 16-32 CPU 核(经验上限) |
| 64+ | – | 不推荐(线程切换收益递减) |

### 3. 多进程接收:reuseport 共享监听

#### 问题

默认 `accept_mutex` 让多个 worker 排队 accept,**扩展性受限**:

```text
100K QPS,1 个 Worker accept → 锁竞争 → 单核瓶颈
```

#### 解决方案:`SO_REUSEPORT` 共享监听套接字

```nginx
server {
    listen 80 reuseport;            # 多进程共享同一 listen socket
}

events {
    multi_accept on;
}
```

**内核**:多个进程各自有独立 listen socket(fd),但绑在**同一端口**,**各自独立 accept**。

```text
Master 进程
├── Worker 1: listen_fd_1 ──┐
├── Worker 2: listen_fd_2 ──┼──→ bind(0.0.0.0:80)
└── Worker 3: listen_fd_3 ──┘

内核根据 4 元组哈希分配连接给某个 listen_fd
```

#### 优势

- **避免 accept_mutex 锁竞争**
- **连接分发到多个 worker,真并行**
- **accept 性能几乎线性扩展**(8 worker ≈ 8x accept)

#### 劣势

- **连接不再集中**:每个 worker 各自维护客户端连接
- 缓存一致性挑战(共享字典需考虑 worker 命中率)

#### 性能数据

| 模式 | accept QPS | 备注 |
| ---- | ---------- | ---- |
| accept_mutex on | ~100K | 默认 |
| accept_mutex off + multi_accept | ~200K | 单 worker 内反复 accept |
| **reuseport + multi_accept** | **~800K+** | **多 worker 共享监听** |

### 4. 多 Worker 共享监听 vs accept_mutex

```text
accept_mutex(默认):
   1 个 listen socket(主进程)
   ↓
   accept_mutex 抢锁
   ├─ Worker 1 抢到,accept 100 个连接
   ├─ Worker 2 抢到,accept 100 个
   └─ Worker N 抢到,accept 100 个
   缺点:锁竞争 + 惊群

reuseport:
   N 个 listen socket(每个 worker 一个)
   ├─ Worker 1 独立 accept(无锁)
   ├─ Worker 2 独立 accept(无锁)
   └─ Worker N 独立 accept(无锁)
   优点:无锁,真并行
```

### 5. 工作模式对比矩阵

| 维度 | 单进程 | 多进程 + accept_mutex | **多进程 + reuseport** | **多进程 + 线程池** |
| ---- | ------ | --------------------- | ----------------------- | ------------------- |
| **Worker 数** | 1 | N(auto) | **N(auto)** | **N(auto)** |
| **线程模型** | 单线程 | 单线程 | **单线程** | **主线程 + 线程池** |
| **accept 锁** | 无 | **有(accept_mutex)** | **无(独立 listen)** | 同 accept_mutex / reuseport |
| **可处理并发** | ~50K | ~100K | **~500K+** | ~100K(主线程)+ 线程池容量 |
| **阻塞 I/O** | 阻塞主循环 | 阻塞主循环 | 阻塞主循环 | **线程池异步,不阻塞** |
| **大文件 I/O** | 卡 | 卡 | 卡 | **线程池异步** |
| **内存占用** | 低 | 中(N 倍) | 中(N 倍) | 中偏高 |
| **配置难度** | 低 | 低 | 低 | 中 |

### 6. 全连接池在不同模式下的差异

```text
单进程:
   一条 epoll + 一个连接池 → 简单但扩展性差

多进程 + accept_mutex:
   N 条 epoll + N 个连接池
   Master 唯一 listen_fd,锁分配给各 worker
   同一 worker 内的连接复用 worker 的 keepalive 池

多进程 + reuseport:
   N 条 epoll + N 个连接池 + N 个 listen_fd
   各 worker 独立 accept
   各自维护 keepalive 池,跨 worker 不复用

多进程 + 线程池:
   N 条 epoll + N 个主线程 + 1 个共享线程池
   阻塞 I/O 任务由线程池处理
   网络事件仍由主线程处理(单线程事件循环不变)
```

### 7. Worker 间共享 vs 独立

| 资源 | 默认共享方式 | 备注 |
| ---- | ------------ | ---- |
| listen socket | Master 持有 | accept_mutex 分配 |
| 客户端连接 | **Worker 独立** | 一旦接受,该连接只在那个 worker |
| upstream keepalive 池 | Worker 独立 | 跨 worker 不共享 |
| proxy_cache | 共享内存(keys_zone) | 所有 worker 命中同一缓存 |
| limit_req zone | 共享内存 | 所有 worker 共享计数 |
| limit_conn zone | 共享内存 | 所有 worker 共享计数 |
| Lua shared dict | 共享内存 | OpenResty 才有 |

### 8. 选型决策

```text
Q1: 是否需要支持大文件 / 慢磁盘 I/O?
   ├── 是 ──→ aio threads + 线程池
   └── 否 ──→ Q2

Q2: 是否高并发(10K+ QPS)接入?
   ├── 是 ──→ reuseport + multi_accept
   └── 否 ──→ 默认(accept_mutex)

Q3: Worker 数?
   worker_processes auto             # 一般 = CPU 核数

Q4: 单连接 IO 密集?
   ├── 是 ──→ threads=N 调大,worker 不要过多
   └── 否 ──→ 默认即可
```

### 9. 实战配置

#### 反向代理 / Web(典型配置)

```nginx
worker_processes auto;            # = CPU 核数
worker_cpu_affinity auto;
worker_rlimit_nofile 65535;

events {
    worker_connections 65535;
    multi_accept on;
    use epoll;
}

http {
    sendfile on;
    tcp_nopush on;
    keepalive_timeout 65;
    keepalive_requests 1000;

    # 上游 keepalive 池
    upstream backend {
        server 10.0.0.1:8080;
        server 10.0.0.2:8080;
        keepalive 32;             # 每 worker 维护 32 条到上游的长连接
    }

    server {
        listen 80 reuseport;        # 多 worker 共享 80
        server_name example.com;

        location / {
            proxy_pass http://backend;
            proxy_http_version 1.1;
            proxy_set_header Connection "";
        }
    }
}
```

#### 大文件 + 线程池(视频 / 镜像)

```nginx
worker_processes auto;

thread_pool io_pool threads=16 max_queue=65536;
# aio threads 块默认使用 default_pool
# aio threads=io_pool(1.27.4+)用指定线程池

events {
    worker_connections 65535;
    multi_accept on;
}

http {
    sendfile on;

    server {
        listen 80 reuseport;

        # 大文件:走线程池,主线程不阻塞
        location /video {
            aio threads;
            sendfile off;
            output_buffers 4 1m;
            max_ranges 0;          # 不分片
        }

        # 小文件:常规 sendfile,无线程池开销
        location /static {
            sendfile on;
            expires 30d;
        }
    }
}
```

### 10. 调优清单

```text
默认:
  worker_processes auto
  events: epoll, accept_mutex on

高并发:
  worker_processes auto
  events: epoll, reuseport, multi_accept on
  upstream: keepalive 32+

大文件 / 慢磁盘:
  thread_pool default_pool threads=16
  aio threads;
  output_buffers 4 1m

调试:
  worker_cpu_affinity auto
  worker_rlimit_nofile 65535
```

### 11. 工作模式决策图

```text
              Nginx 工作模式
                    │
        ┌───────────┴───────────┐
        │                       │
  默认(单线程事件循环)   启用线程池
        │                       │
   ┌────┴────┐                  │
   │         │                  │
accept_mutex  reuseport         │
   默认        高并发            │
                              适用:
                              - 大文件
                              - 慢磁盘
                              - NFS
```

**绝大多数场景使用默认模式即可**;**reuseport 在高并发接入下显著提升**;**线程池仅在阻塞型 I/O 多时启用**。
## 十七、WAF / 网关层应用

### 1. IP 黑名单(geo)

```nginx
geo $is_blacklist {
    default 0;
    10.0.0.0/8 1;
    192.168.1.100 1;
}

server {
    if ($is_blacklist) {
        return 403;
    }
}
```

### 2. 限流

```nginx
limit_req_zone $binary_remote_addr zone=rate:10m rate=10r/s;

server {
    location /api/ {
        limit_req zone=rate burst=20 nodelay;   # 突发 20 个,允许排队
        limit_req_status 429;
        proxy_pass http://backend;
    }
}
```

### 3. 并发连接限制

```nginx
limit_conn_zone $binary_remote_addr zone=conn:10m;

server {
    location / {
        limit_conn conn 10;       # 单 IP 最多 10 连接
    }
}
```

### 4. 鉴权

```nginx
# Basic 鉴权
location /admin/ {
    auth_basic "Admin";
    auth_basic_user_file /etc/nginx/.htpasswd;
}

# 子请求鉴权
location /api/ {
    auth_request /auth;
}

location = /auth {
    internal;
    proxy_pass http://auth-service;
}
```

### 5. 灰度发布

```nginx
map $cookie_uid $uid { default ""; }
map $http_x_release $release { default "stable"; }

upstream stable { server 10.0.0.1:8080; }
upstream canary { server 10.0.0.2:8080; }

server {
    location / {
        if ($release = "canary") {
            proxy_pass http://canary;
        }
        # 10% 流量到 canary(按 uid 末位)
        if ($uid ~ "^[0-9]$") {
            proxy_pass http://canary;
        }
        proxy_pass http://stable;
    }
}
```

### 6. 统一鉴权网关

```nginx
server {
    listen 80;

    location / {
        access_by_lua_block {           # OpenResty 才支持
            local token = ngx.var.arg_token
            if not token then return ngx.exit(401) end
            -- 验证 token
        }
    }
}
```

(纯 Nginx 用 `auth_request` 子请求实现类似能力)

---

## 十八、调试与监控

### 1. error_log

```nginx
error_log /var/log/nginx/error.log warn;     # 级别:debug/info/notice/warn/error/crit/alert/emerg
```

### 2. access_log 自定义格式

```nginx
log_format main '$remote_addr - $remote_user [$time_local] '
                '"$request" $status $body_bytes_sent '
                '"$http_referer" "$http_user_agent" '
                'rt=$request_time uct=$upstream_connect_time '
                'urt=$upstream_response_time';

access_log /var/log/nginx/access.log main;
```

### 3. 状态页

```nginx
location = /basic_status {
    stub_status on;           # Nginx 1.x
    # 或 vts 模块:更详细
}
```

输出:

```text
Active connections: 2
server accepts handled requests
 100 100 200
Reading: 0 Writing: 1 Waiting: 1
```

### 4. 监控指标

```text
Active connections              # 当前活跃
accepts / handled / requests    # 累计接受/处理/请求
Reading / Writing / Waiting     # 读/写/等待连接
```

更详细可用 **nginx-module-vts**(响应 JSON / Prometheus)。

### 5. 火焰图

```bash
# 使用 systemtap / perf 抓 CPU 采样
perf record -F 99 -p $(pgrep -n nginx) -g -- sleep 30
perf script | ./stackcollapse-perf.pl > out.folded
./flamegraph.pl out.folded > nginx.svg
```

---

## 十九、常见陷阱

### 1. `if` 指令陷阱

- **`if` 是邪恶的**(if is evil):在 location 中只对部分指令安全,做 request redirect / rewrite 之外的会出问题
- 用 `try_files` / `map` / `return` 替代

```nginx
# ❌ 错:if + proxy_pass 的副作用
if ($args = "debug") { proxy_pass http://debug_backend; }   # 不可靠

# ✅ 用 map
map $args $backend { default "prod"; ~*debug=1 "debug"; }
```

### 2. upstream keepalive 没生效

```nginx
# ❌ 没生效
proxy_pass http://backend;
upstream backend { keepalive 32; }

# ✅ 必须 HTTP/1.1 + 清空 Connection 头
proxy_pass http://backend;
proxy_http_version 1.1;
proxy_set_header Connection "";
```

### 3. proxy_pass 末尾 `/`

```nginx
location /api/ { proxy_pass http://backend; }    # 多带 /api 前缀
location /api/ { proxy_pass http://backend/; }   # 正确
```

### 4. location 匹配优先级

```nginx
# = 精确 > ^~ 前缀 > ~ 正则 > 普通前缀
location / { ... }                      # 最后匹配
location ~ \.php$ { ... }               # 正则优先
```

### 5. reload 不生效

```bash
nginx -t           # 先测配置
nginx -s reload    # 热加载
# 配置问题 reload 会保留旧配置,不抛错
```

### 6. 共享内存爆掉

```nginx
# keys_zone 总大小 ≥ Worker 数 × 单 zone 大小
proxy_cache_path ... keys_zone=cache:10m;
# 10MB 共享内存,所有 Worker 共享
```

### 7. worker_connections 不够

```nginx
# 不是单连接 = worker_connections
# 反代时一个客户端连接可能占 2 个 worker_connections(到客户端 + 到上游)
events {
    worker_connections 65535;   # 反代时按 4 倍峰值估算
}
```

---

## 二十、Nginx vs 其他网关

| 维度          | Nginx             | HAProxy       | Envoy           | OpenResty / Kong | Caddy           |
|---------------|-------------------|---------------|-----------------|-------------------|-----------------|
| 语言          | C                 | C             | C++             | C + Lua           | Go              |
| 性能          | **极高**          | **极高**      | 高              | 高                | 中              |
| L4 / L7       | L7 强 / L4(stream)| L4 + L7 都强  | L4 + L7 都强    | L7 强             | L7              |
| 配置          | 配置文件           | 单文件         | YAML / xDS      | 配置 + Lua        | Caddyfile       |
| 动态配置      | 弱(reload)        | 中(Dataplane API)| 强(xDS 热更)| 强(Lua 热加载)  | 弱              |
| 服务发现      | 弱                 | 弱            | **强**(EDS)     | 中                | 弱              |
| 生态          | 中                 | 中            | **强**          | 强(OpenResty 生态)| 中             |
| 适用          | 反代、网关、静态   | L4/L7 LB      | 服务网格        | 网关层编程        | 简单静态/HTTPS  |

---

## 二十一、部署与运维

### 1. 安装

**apt / yum**:

```bash
apt install nginx
yum install nginx
systemctl enable --now nginx
```

**官方源**:

```bash
# Debian/Ubuntu
wget https://nginx.org/keys/nginx_signing.key
apt-key add nginx_signing.key
echo "deb https://nginx.org/packages/debian bullseye nginx" > /etc/apt/sources.list.d/nginx.list
apt update && apt install nginx
```

**源码编译**:

```bash
./configure --prefix=/usr/local/nginx \
    --user=nginx --group=nginx \
    --with-http_stub_status_module \
    --with-http_ssl_module \
    --with-http_v2_module \
    --with-http_gzip_static_module \
    --with-http_realip_module \
    --add-module=../ngx_brotli
make -j$(nproc) && make install
```

### 2. 目录结构

```text
/etc/nginx/
├── nginx.conf           # 主配置
├── conf.d/              # 自定义 server 块
│   ├── default.conf
│   └── sites/*.conf
├── modules/             # 动态模块(.so)
├── snippets/            # 可复用的片段
└── ssl/                 # 证书

/var/log/nginx/
├── access.log
└── error.log

/var/cache/nginx/        # proxy_cache 目录
/usr/share/nginx/html/   # 默认站点
```

### 3. nginx.conf 结构

```nginx
user                 nginx;
worker_processes     auto;
pid                  /var/run/nginx.pid;
error_log            /var/log/nginx/error.log warn;

events {
    worker_connections 65535;
    multi_accept on;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;
    sendfile      on;
    tcp_nopush    on;
    keepalive_timeout 65;

    log_format main '...';
    access_log   /var/log/nginx/access.log main;

    # 通用配置
    gzip on;

    # 站点
    include /etc/nginx/conf.d/*.conf;
}
```

### 4. 常用命令

```bash
# 测试配置
nginx -t
nginx -T              # 测试 + 打印完整配置

# 启动 / 停止 / 重载
nginx
nginx -s stop         # 立即停止
nginx -s quit         # 优雅退出
nginx -s reload       # 热加载(配置)
nginx -s reopen       # 重新打开日志

# 看版本与编译参数
nginx -v              # 版本
nginx -V              # 版本 + 编译参数
```

### 5. systemd

```bash
systemctl status nginx
systemctl reload nginx       # 等价 nginx -s reload
journalctl -u nginx -f       # 日志
```

### 6. 平滑升级

```bash
# 1. 编译新版本到 /usr/local/nginx-new/
# 2. mv /usr/local/nginx /usr/local/nginx-old
# 3. mv /usr/local/nginx-new /usr/local/nginx
# 4. nginx -t
# 5. make upgrade           # 等价 kill -HUP
```

### 7. 日志切割

```bash
# logrotate /etc/logrotate.d/nginx
/var/log/nginx/*.log {
    daily
    rotate 30
    missingok
    notifempty
    compress
    delaycompress
    sharedscripts
    postrotate
        nginx -s reopen > /dev/null 2>&1 || true
    endscript
}
```

---

## 二十二、实战案例: 七层与四层转发透传真实客户端 IP

场景:反代后,upstream 只能看到 Nginx IP(不是真实 client);要做访问日志、限流、地理识别、攻击溯源,需要**透传真实客户端 IP**。

### 1. 七层(L7 HTTP)透传

#### Nginx 端注入 + realip 模块

```nginx
http {
    # 信任的代理段(根据实际网络)
    set_real_ip_from 10.0.0.0/8;
    set_real_ip_from 192.168.0.0/16;
    set_real_ip_from 172.16.0.0/12;
    set_real_ip_from <cdn_ip>;            # CDN 段

    real_ip_header    X-Forwarded-For;
    real_ip_recursive on;                  # 多层代理时取最左侧

    server {
        listen 80;
        location / {
            proxy_pass http://backend;

            # 主动把真实 IP 写到请求头
            proxy_set_header Host              $host;
            proxy_set_header X-Real-IP         $remote_addr;
            proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header X-Forwarded-Host  $host;
        }
    }
}
```

**关键点**:

| 指令 | 含义 |
| ---- | ---- |
| `set_real_ip_from <cidr>` | 信任的代理 IP,**只有列出的段送的 XFF 才解析** |
| `real_ip_header X-Forwarded-For` | 从哪个 header 取真实 IP |
| `real_ip_recursive on` | 多层代理时递归取最左侧 |
| `proxy_set_header X-Real-IP $remote_addr` | 额外注入,upstream 可直接读 |
| `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for` | **追加**到现有链尾,而不是覆盖 |

**upstream 端读取**:

```nginx
# Tomcat server.xml
<Valve className="org.apache.catalina.valves.RemoteIpValve" />

# Spring Boot application.properties
server.forward-headers-strategy=native

# 自定义读取(Nginx 之外的 PHP / Python 等)
String realIp = request.getHeader("X-Real-IP");
String forwardedFor = request.getHeader("X-Forwarded-For");
```

### 2. 四层(L4 stream)透传

L4 没有 HTTP header,要传真实 IP 必须用其他机制。

#### 方式 A: PROXY protocol(推荐,主流方案)

Nginx 给 upstream 发 PROXY 协议头,upstream 解析。

```nginx
stream {
    upstream mysql {
        server 10.0.0.11:3306;
    }

    server {
        listen 3306;
        proxy_pass mysql;
        proxy_protocol on;              # Nginx ≥ 1.11.4
    }
}
```

握手时,Nginx 发送一行:`PROXY TCP4 <client_ip> <rs_ip> <client_port> <rs_port>\r\n`,upstream 解析后获得真实 IP。

**upstream 启用 PROXY protocol**:

- MySQL: 用 ProxySQL 解析,或 mysql-proxy-plugin
- Redis 6+: 支持,启动时 `proxy_enabled yes`
- HAProxy: `accept-proxy` 一行开启
- 自研 TCP 服务:协议层读取第一行

#### 方式 B: TPROXY(IP_TRANSPARENT,内核级)

让 Nginx **用 client 的源 IP** 连接 upstream。

```nginx
stream {
    upstream mysql {
        server 10.0.0.11:3306;
    }

    server {
        listen 3306;
        proxy_pass mysql;
        proxy_bind $remote_addr transparent;     # 用 client IP 作源
    }
}
```

```bash
# Director 端:开启 IP_TRANSPARENT 权限
setcap cap_net_bind_service,cap_net_admin+ep /usr/sbin/nginx

# RS 端:Director 必须当网关(否则回程找不到 client)
route add default gw <director_ip>

# 内核路由(可选,绕开本地路由)
ip rule add fwmark 1 lookup 100
ip route add local 0.0.0.0/0 dev lo table 100
iptables -t mangle -A PREROUTING -p tcp --dport 3306 -j MARK --set-mark 1
```

**特点**:upstream 看到真实 client IP,但**要求 RS 配合 Director 当网关**(回程路由)。

#### 方式 C: proxy_bind 指定本地源 IP(NAT-like)

```nginx
stream {
    upstream mysql {
        server 10.0.0.11:3306;
    }

    server {
        listen 3306;
        proxy_pass mysql;
        proxy_bind 192.168.1.10:33060;    # 指定出口 IP + 端口
    }
}
```

upstream **看到的是 Nginx 自己 IP**;要传真实 IP 还得靠 PROXY protocol 或 TPROXY。

### 3. 完整链路: client → CDN → LB → Nginx → upstream

```text
client (1.2.3.4)
   │
   ▼
CDN edge    X-Forwarded-For: 1.2.3.4
   │
   ▼
LB          X-Forwarded-For: 1.2.3.4, <cdn_ip>
   │
   ▼
Nginx L7    X-Forwarded-For: 1.2.3.4, <cdn_ip>, <lb_ip>
   │
   ▼
upstream    remote_addr = Nginx IP,但能解析 XFF 得真实 IP
```

**Nginx 多层配置**:

```nginx
http {
    # 第一层 Nginx(CDN 后)
    set_real_ip_from <cdn_edge_ip>;
    real_ip_header X-Forwarded-For;
    real_ip_recursive on;
    # $remote_addr 此时是 <cdn_ip>,解析 XFF 后变 client IP

    # 第二层 Nginx(LB 后)
    set_real_ip_from <lb_internal_ip>;
    real_ip_header X-Forwarded-For;
    real_ip_recursive on;
}
```

每层**只信任自己的直接上游**,XFF 链式追加,不互相覆盖。

### 4. 方案对比

| 方案 | L4/L7 | upstream 改动 | 复杂度 | 适用 |
| ---- | ----- | -------------- | ------ | ---- |
| **X-Forwarded-For** | L7 | 读 header | **低** | Web / API |
| **realip_module** | L7 | 解析 `$remote_addr` | 低 | Web / API |
| **PROXY protocol** | L4 | 协议层解析 | 中 | TCP 服务(数据库 / Redis) |
| **TPROXY** | L4 | 路由层配合 | 高 | TCP 服务,要求高 |
| **proxy_bind** | L4 | 无(Nginx 自身 IP) | 低 | 仅需固定出口 IP |

### 5. 验证脚本

```bash
# L7:看 upstream 是否拿到真实 IP
curl -H "X-Forwarded-For: 1.2.3.4" http://nginx/api/test
# upstream log 应显示:
#   remote_addr: Nginx 内网 IP
#   X-Real-IP:   1.2.3.4(注入后)
#   X-Forwarded-For: 1.2.3.4, client_real_ip

# L4 + PROXY protocol:抓包
tcpdump -i eth0 -nn -X port 3306
# 第一行应见:PROXY TCP4 <client_ip> <rs_ip> ...

# L4 + TPROXY:upstream 应看到 client 真实 IP
mysql -h rs -e "SELECT HOST FROM information_schema.processlist WHERE ID = CONNECTION_ID();"
```

### 6. 陷阱

- **不要无条件信任 XFF**:`set_real_ip_from` 必须**精确**列出可信代理,否则伪造 XFF 即可绕过 IP 黑名单
- **`proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for` 是追加**,**不要**用 `$http_x_forwarded_for`(会覆盖,且不会追加 client IP)
- **`real_ip_recursive on`** 必须开,否则多层代理时取到的是中间代理 IP
- **TPROXY 需要 root + 内核能力**:`setcap cap_net_admin+ep`
- **TPROXY + 防火墙**:RS 端若启用反向路径过滤(`rp_filter`),需关掉或正确路由
- **PROXY protocol 不兼容老版本 Redis**:Redis 6 以下不支持,需 ProxySQL

---

## 二十三、核心要点速记

- **Nginx = 事件驱动 + 异步 I/O**,单 Worker 可处理上万连接
- **Master / Worker 模型**:`worker_processes auto`,一般等于 CPU 核数
- **Worker 独立**,共享内存靠 `proxy_cache_path` / `limit_req_zone` / `limit_conn_zone`
- **HTTP 11 个阶段**,CONTENT 是生成内容主战场
- **location 匹配优先级**:`=` > `^~` > `~` > 普通前缀
- **`upstream` 调度**:round-robin / least_conn / ip_hash / hash
- **`proxy_next_upstream`** 控制重试
- **upstream keepalive 必须 `http_version 1.1 + Connection ""`**
- **`proxy_pass` 末尾 `/`** 决定是否剥离 location 前缀
- **`if is evil`**:用 `map` / `try_files` / `return` 替代
- **`proxy_cache` 缓存击穿**:`proxy_cache_lock on` 只允许一个回源
- **状态页**:`stub_status` 或 vts 模块
- **日志**:自定义 `log_format`,带 `$request_time` `$upstream_response_time`
- **性能优化**:sendfile / tcp_nopush / keepalive / gzip / open_file_cache
- **TLS 1.3 + HTTP/2**:生产标配
- **WAF / 网关**:限流(`limit_req`)、鉴权(`auth_request`)、灰度(`map`)
- **常见陷阱**:if 副作用 / proxy_pass 末尾 / / keepalive 配错 / reload 不生效
- **vts / prometheus exporter** 用于监控指标导出
- **debug 日志**:临时改 `error_log /var/log/nginx/error.log debug;`,生产别开
- **平滑升级**:编译新版本替换,`nginx -s reload` 不中断运行中的请求
- **logrotate** + `nginx -s reopen` 切割日志
- **Nginx 是 L7 反代 + L4 stream** 双能力,云原生时代仍是入口首选之一

