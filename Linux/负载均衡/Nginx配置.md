# Nginx 配置详解

## 一、配置文件结构

### 1. 主从结构

Nginx 配置采用 **指令(directive) + 块(block)** 的树形结构,块可以嵌套。

```nginx
# /etc/nginx/nginx.conf

# ============ main 块(全局) ============
user                 nginx;
worker_processes     auto;
events {
    worker_connections 65535;
}

# ============ http 块 ============
http {
    include       mime.types;
    default_type  application/octet-stream;
    sendfile      on;

    # server 块(虚拟主机)
    server {
        listen      80;
        server_name example.com;

        # location 块(URL 路由)
        location / {
            root   /var/www;
            index  index.html;
        }
    }
}
```

### 2. 块与指令

- **简单指令**:`key value;`(一行,以 `;` 结尾)
- **块指令**:`block_name { ... }`(可嵌套)
- **顶级块**:`main`、`events`、`http`、`stream`、`mail`
- **嵌套块**:`http { server { location { ... } } }`

### 3. 常用文件分布

```text
/var/nginx/conf/
├── nginx.conf              # 主配置
├── conf.d/                # 自定义 server
│   ├── default.conf
│   └── sites/*.conf
├── modules/               # 动态模块
├── snippets/              # 可复用片段
└── ssl/                   # 证书
```

---

## 二、配置语法基础

### 1. 注释与单位

```nginx
# 单行注释
# sendfile on;             # 行尾注释也可

sendfile      on;           # 布尔:on / off
worker_processes 4;         # 整数
keepalive_timeout 65s;     # 时间:ms / s / m / h / d / w / M / y
client_max_body_size 100m; # 字节:k / m / g
```

### 2. 包含指令

```nginx
# 拆分配置
include /etc/nginx/conf.d/*.conf;
include /etc/nginx/mime.types;
include snippets/security-headers.conf;
```

### 3. 变量

```nginx
set $my_var "hello";        # 自定义变量
log_format main '$remote_addr - $host';   # 预定义变量
```

### 4. 单位与值

| 类型 | 示例 | 备注 |
| ---- | ---- | ---- |
| 整数 | `1024` | 无单位 |
| 字节 | `1k` `100m` `8g` | `k` = 1024 |
| 时间 | `5s` `30m` `1h` `1d` | 支持 d / w / M / y |
| 字符串 | `on` `off` `text/plain` | 无引号 |

---

## 三、main 全局指令

### 1. 进程与权限

```nginx
user                 www-data www-data;      # 用户和组
worker_processes     auto;                   # Worker 数(= CPU 核数)
worker_cpu_affinity  auto;                   # CPU 亲和
worker_priority      0;                      # nice 值
worker_rlimit_nofile 65535;                  # fd 上限
worker_rlimit_core   500M;                   # core dump 大小
daemon               on;                     # 守护进程
master_process      on;                     # 是否启用 master(关闭后单进程)
pid                  /var/run/nginx.pid;
```

### 2. 错误日志

```nginx
error_log /var/log/nginx/error.log warn;     # debug | info | notice | warn | error | crit | alert | emerg
```

### 3. 加载动态模块

```nginx
load_module modules/ngx_http_brotli_filter_module.so;
load_module modules/ngx_http_geoip_module.so;
```

### 4. 其他

```nginx
env PATH;                       # 保留环境变量给 worker
thread_pool default_pool threads=32 max_queue=65536;   # 1.7.11+
```

---

## 四、events 块

### 1. Worker 连接与事件模型

```nginx
events {
    worker_connections      65535;       # 每 Worker 最大连接
    use                     epoll;       # Linux 用 epoll
    multi_accept            on;          # 一次 accept 多个
    accept_mutex            on;          # 默认 on(避免惊群)
    accept_mutex_delay      500ms;       # 抢锁间隔
    worker_aio_requests     32;          # AIO 队列大小
}
```

### 2. 关键参数

| 指令 | 默认 | 含义 |
| ---- | ---- | ---- |
| `worker_connections` | 512 | 单 Worker 最大并发 |
| `use` | OS 默认 | 事件模型(epoll / kqueue) |
| `multi_accept` | off | 一次 accept 多个连接 |
| `accept_mutex` | on | accept 互斥锁 |
| `accept_mutex_delay` | 500ms | 抢锁失败等待时间 |

---

## 五、http 块(全局)

### 1. 文件与 MIME

```nginx
http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;
    charset       utf-8;
    types_hash_max_size 2048;
    types_hash_bucket_size 128;
}
```

### 2. 性能开关

```nginx
http {
    sendfile          on;        # 零拷贝
    tcp_nopush        on;        # 合并包
    tcp_nodelay       on;        # 禁用 Nagle
    aio               on;        # 异步 I/O(Linux 2.6+)
    aio threads;                 # 用线程池
    directio          4m;        # > 4m 文件用直 I/O
    read_ahead        512k;      # 内核预读
    output_buffers    2 32k;     # 输出缓冲
    postpone_output   1460;      # 延迟输出(让 sendfile 合并)
}
```

### 3. 超时与连接

```nginx
http {
    keepalive_timeout      65s;
    keepalive_requests     1000;
    keepalive_disable      msie6;       # 旧 IE 不支持 keepalive
    lingering_timeout       5s;
    client_header_timeout  60s;
    client_body_timeout    60s;
    send_timeout           60s;
    reset_timedout_connection on;
}
```

### 4. 客户端请求

```nginx
http {
    client_max_body_size         100m;     # 请求体上限
    client_body_buffer_size      16k;
    client_header_buffer_size    1k;
    large_client_header_buffers  4 8k;    # 大请求头
    client_body_temp_path        /var/cache/nginx/client_temp;
    client_header_timeout        60s;
    merge_slashes                on;      # 合并 ///
    ignore_invalid_headers       on;
}
```

### 5. 日志

```nginx
http {
    log_format main '$remote_addr - $remote_user [$time_local] '
                    '"$request" $status $body_bytes_sent '
                    '"$http_referer" "$http_user_agent" '
                    'rt=$request_time uct=$upstream_connect_time '
                    'urt=$upstream_response_time';

    log_format json escape=json '{...}';

    access_log /var/log/nginx/access.log main buffer=32k flush=5s gzip=1;
    access_log off;     # 关闭日志
}
```

### 6. 文件描述符缓存

```nginx
http {
    open_file_cache             max=10000 inactive=30s;
    open_file_cache_valid       60s;
    open_file_cache_min_uses    2;
    open_file_cache_errors      on;
}
```

### 7. 压缩

```nginx
http {
    gzip               on;
    gzip_min_length    1024;
    gzip_comp_level    5;
    gzip_vary          on;
    gzip_proxied       any;
    gzip_types         text/plain text/css application/json application/javascript image/svg+xml;
    gzip_disable       "msie6";
    gzip_buffers       16 8k;
    gzip_http_version  1.1;
}
```

### 8. SSL / TLS(全局)

```nginx
http {
    ssl_protocols              TLSv1.2 TLSv1.3;
    ssl_ciphers                ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers  on;
    ssl_session_cache          shared:SSL:50m;
    ssl_session_timeout        1d;
    ssl_session_tickets        on;
}
```

### 9. 代理 / FastCGI / uwsgi 全局

```nginx
http {
    proxy_buffering          on;
    proxy_buffer_size        16k;
    proxy_buffers            8 32k;
    proxy_busy_buffers_size  64k;
    proxy_temp_path          /var/cache/nginx/proxy_temp;
    proxy_max_temp_file_size 1024m;

    fastcgi_buffer_size      16k;
    fastcgi_buffers          8 32k;
    fastcgi_temp_path        /var/cache/nginx/fastcgi_temp;

    uwsgi_buffer_size        16k;
    uwsgi_buffers            8 32k;
}
```

### 10. 哈希表

```nginx
http {
    server_names_hash_max_size  4096;
    server_names_hash_bucket_size 128;
    variables_hash_max_size     2048;
    variables_hash_bucket_size  128;
    map_hash_max_size           2048;
    map_hash_bucket_size        128;
}
```

---

## 六、server 块

### 1. listen 与 server_name

```nginx
server {
    listen 80 default_server;
    listen 443 ssl http2 default_server backlog=2048 reuseport;
    listen [::]:80 ipv6only=on;

    server_name example.com www.example.com *.example.com;
    server_name_in_redirect  on;
}
```

### 2. 路由

```nginx
server {
    server_name _;                       # 默认 server(catch-all)

    location / {
        root   /var/www;
        index  index.html index.htm;
    }

    location = /favicon.ico { ... }       # 精确匹配
    location ^~ /static/ { ... }         # 前缀优先
    location ~ \.php$ { ... }            # 正则
    location /api/ { ... }               # 普通前缀
}
```

### 3. 错误页

```nginx
server {
    error_page 404              /404.html;
    error_page 500 502 503 504  /50x.html;
    error_page 403              http://example.com/forbidden;

    location = /404.html {
        root   /var/www/errors;
        internal;
    }
}
```

### 4. 重定向

```nginx
server {
    return 301 https://$host$request_uri;
    rewrite ^/old/(.*)$ /new/$1 permanent;     # 301
    rewrite ^/api/(.*)$ /$1 break;              # break:不再走 rewrite
}
```

### 5. try_files

```nginx
server {
    root /var/www;
    try_files $uri $uri/ /index.html;          # 静态找,找不到 → index.html
    try_files $uri $uri/ @backend;              # @ 命名 location
    try_files /nonexistent @fallback;
}

location @backend {
    proxy_pass http://backend;
}
```

### 6. 认证

```nginx
server {
    auth_basic           "Restricted";
    auth_basic_user_file /etc/nginx/.htpasswd;

    location /api/ {
        auth_request       /auth;                # 子请求鉴权
        auth_request_set   $auth_user $upstream_http_x_user;
    }

    location = /auth {
        internal;
        proxy_pass http://auth-svc/verify;
    }
}
```

---

## 七、location 块(深入)

### 1. 匹配优先级

| 前缀 | 含义 | 优先级 |
| ---- | ---- | ------ |
| `=` | 精确匹配 | 1(最高) |
| `^~` | 前缀匹配,不再走正则 | 2 |
| `~` | 正则(区分大小写) | 3 |
| `~*` | 正则(不区分大小写) | 3 |
| 无 | 普通前缀 | 4(最低) |

### 2. 实战

```nginx
location = /health {
    access_log off;
    return 200 "OK";
}

location ^~ /static/ {
    root   /var/www;
    expires 30d;
}

location ~* \.(jpg|jpeg|png|gif|webp)$ {
    expires 365d;
    access_log off;
}

location / {
    try_files $uri $uri/ /index.html;
}

location /api/ {
    proxy_pass http://api_backend;
}

location ~ /api/v(\d+)/(.+\.json)$ {
    # 复杂正则提取 + 转发
    set $version $1;
    set $path    $2;
    proxy_pass http://api_v$version_backend/$path;
}
```

### 3. 命名 location(@)

```nginx
location / {
    try_files $uri @backend;
}

location @backend {
    proxy_pass http://backend;
}
```

命名 location **只能内部跳转**,常用于 try_files / error_page 兜底。

### 4. internal 指令

```nginx
location = /secret {
    internal;        # 仅内部跳转可访问
    root /var/secret;
}
```

---

## 八、upstream 块

### 1. 基本配置

```nginx
upstream backend {
    server 10.0.0.1:8080 weight=3;
    server 10.0.0.2:8080 weight=1;
    server 10.0.0.3:8080 backup;       # 备用
    server 10.0.0.4:8080 down;          # 摘除

    keepalive 32;                       # 连接池
    keepalive_requests 1000;
    keepalive_timeout 60s;
}
```

### 2. 调度算法

```nginx
upstream a {                            # 默认 rr
    server 10.0.0.1:8080;
    server 10.0.0.2:8080;
}

upstream b {
    least_conn;                          # 最少连接
    server 10.0.0.1:8080;
    server 10.0.0.2:8080;
}

upstream c {
    ip_hash;                             # 源 IP 哈希
    server 10.0.0.1:8080;
    server 10.0.0.2:8080;
}

upstream d {
    hash $request_uri consistent;        # URI 一致性哈希
    server 10.0.0.1:8080;
    server 10.0.0.2:8080;
}

upstream e {
    random two;                          # 两台随机(商业版)
    server 10.0.0.1:8080;
    server 10.0.0.2:8080;
}
```

### 3. 健康检查

```nginx
upstream backend {
    server 10.0.0.1:8080 max_fails=3 fail_timeout=30s;
    server 10.0.0.2:8080 max_fails=3 fail_timeout=30s;
    keepalive 32;

    # 主动检查(开源需 nginx_upstream_check_module)
    check interval=5000 rise=2 fall=3 timeout=1000 type=http;
    check_http_send "GET /health HTTP/1.0\r\n\r\n";
    check_http_expect_alive http_2xx;
}
```

### 4. server 指令参数

| 参数 | 含义 |
| ---- | ---- |
| `weight=N` | 权重(默认 1) |
| `max_fails=N` | 最大失败次数(默认 1) |
| `fail_timeout=S` | 失败超时(默认 10s) |
| `backup` | 备用(其他全挂才生效) |
| `down` | 永久摘除 |
| `max_conns=N` | 最大并发连接(商业版) |
| `slow_start=S` | 慢启动(商业版) |

---

## 九、proxy_pass 与上游交互

### 1. 基本配置

```nginx
location / {
    proxy_pass http://backend;     # 转到 upstream backend
    proxy_pass http://10.0.0.1:8080;
    proxy_pass https://api.example.com;
}
```

### 2. proxy_pass 末尾 `/` 行为

```nginx
location /api/ {
    proxy_pass http://backend;      # /api/foo → http://backend/api/foo(保留前缀)
}
location /api/ {
    proxy_pass http://backend/;     # /api/foo → http://backend/foo(剥离 /api/)
}
location /api {
    proxy_pass http://backend;      # /api/foo → http://backend/api/foo
}
```

### 3. 关键 Header

```nginx
proxy_set_header Host              $host;
proxy_set_header X-Real-IP         $remote_addr;
proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header X-Forwarded-Host  $host;
proxy_set_header Connection        "";
```

### 4. Buffer 与超时

```nginx
proxy_buffering          on;
proxy_buffer_size        16k;
proxy_buffers            8 32k;
proxy_busy_buffers_size  64k;
proxy_temp_file_write_size 64k;
proxy_max_temp_file_size  1024m;

proxy_connect_timeout    5s;
proxy_send_timeout       60s;
proxy_read_timeout       60s;
proxy_next_upstream      error timeout http_502 http_503;
proxy_next_upstream_tries 3;
proxy_next_upstream_timeout 10s;
```

### 5. HTTP 版本与协议

```nginx
proxy_http_version  1.1;          # 默认 1.0,反代必 1.1
proxy_ssl_protocols TLSv1.2 TLSv1.3;
proxy_ssl_server_name on;          # SNI
proxy_ssl_name        api.example.com;
```

---

## 十、if / map / geo 条件判断

### 1. if 指令(谨慎)

```nginx
if ($request_method = POST) {
    return 405;
}

if ($http_user_agent ~ MSIE) {
    rewrite ^ /old-browser;
}

if ($args = "debug=1") {
    set $debug 1;
}
```

**警告**:`if` 在 location 中只对部分指令安全,其他场景不可靠。

### 2. map 指令(推荐)

```nginx
http {
    map $http_user_agent $is_mobile {
        default 0;
        ~*android|iphone 1;
    }

    map $args $backend {
        default "prod";
        ~*debug=1 "debug";
        ~*test=1 "test";
    }

    map $request_method $is_write {
        default 0;
        POST    1;
        PUT     1;
        DELETE  1;
    }
}
```

### 3. geo 指令(IP 段映射)

```nginx
geo $is_blacklist {
    default        0;
    10.0.0.0/8     1;
    192.168.1.100  1;
    127.0.0.1      0;
}

geo $country {
    default  "unknown";
    1.0.0.0/8 "Australia";
    1.1.1.0/8 "Australia";
}
```

### 4. split_clients(按比例)

```nginx
split_clients $request_id $backend {
    10%     "canary";
    *       "stable";
}
```

---

## 十一、变量系统

### 1. 内置变量(常用)

```nginx
$remote_addr          # 客户端 IP
$remote_port          # 客户端端口
$remote_user          # Basic 鉴权用户名
$binary_remote_addr   # 二进制 IP(用于 limit_req zone)
$server_addr          # 服务端 IP
$server_name          # 匹配到的 server_name
$server_port          # 服务端端口

$host                 # Host 头(无端口)
$http_host            # Host 头(原始)
$hostname             # 主机名

$request              # 完整请求行
$request_method       # GET / POST
$request_uri          # 完整 URI(含参数)
$uri                  # 当前 URI(不含参数)
$args                 # 查询字符串
$arg_name             # ?name=xxx
$query_string         # 同 $args
$is_args              # 是否有参数("?" 或 "")

$http_HEADER          # 请求头(小写)
$cookie_name          # Cookie 值
$content_type         # 请求体类型
$content_length       # 请求体大小

$scheme               # http / https
$request_time         # 请求处理耗时(秒)
$upstream_addr        # 上游地址
$upstream_status      # 上游状态码
$upstream_response_time   # 上游响应耗时
$upstream_connect_time    # 连接上游耗时
$upstream_header_time     # 上游接收首字节耗时
$upstream_cache_status    # HIT / MISS / EXPIRED / STALE / BYPASS

$ssl_protocol         # TLSv1.2 / TLSv1.3
$ssl_cipher           # 加密套件
$ssl_client_verify    # 客户端证书验证结果

$proxy_add_x_forwarded_for   # 拼接 XFF
$realip_remote_addr          # 用 realip 模块后的真实 IP

$limit_req_status    # 限流触发状态码(默认 503)
$connection          # 连接序号
$connection_requests # 当前连接的请求数
$msc                 # 自启动以来的毫秒数
$msec                # 当前毫秒时间戳
```

### 2. 自定义变量

```nginx
set $foo "bar";
set $debug 0;
```

---

## 十二、缓存配置

### 1. 静态文件缓存

```nginx
open_file_cache             max=10000 inactive=30s;
open_file_cache_valid       60s;
open_file_cache_min_uses    2;
open_file_cache_errors      on;
```

### 2. proxy_cache(响应缓存)

```nginx
proxy_cache_path /var/cache/nginx
    levels=1:2
    keys_zone=my_cache:100m
    max_size=10g
    inactive=60m
    use_temp_path=off;

server {
    location /api/ {
        proxy_pass http://backend;
        proxy_cache          my_cache;
        proxy_cache_key      "$scheme$proxy_host$request_uri";
        proxy_cache_valid    200 302 10m;
        proxy_cache_valid    404 1m;
        proxy_cache_lock     on;
        proxy_cache_lock_timeout 5s;
        proxy_cache_min_uses 1;
        proxy_cache_bypass   $http_pragma $http_authorization;
        proxy_no_cache       $http_authorization;
        add_header X-Cache-Status $upstream_cache_status;
    }
}
```

### 3. FastCGI / uwsgi 缓存(类似)

```nginx
fastcgi_cache_path /var/cache/nginx/fastcgi
    levels=1:2 keys_zone=fcgi:50m max_size=1g inactive=30m;

location ~ \.php$ {
    fastcgi_pass unix:/run/php-fpm.sock;
    fastcgi_cache fcgi;
    fastcgi_cache_key "$scheme$request_method$host$request_uri";
}
```

---

## 十三、限流与防护

### 1. limit_req(请求速率)

```nginx
limit_req_zone $binary_remote_addr zone=rate:10m rate=100r/s;

server {
    location /api/ {
        limit_req zone=rate burst=200 nodelay;
        limit_req_status 429;
    }
}
```

### 2. limit_conn(并发连接)

```nginx
limit_conn_zone $binary_remote_addr zone=conn:10m;

server {
    location / {
        limit_conn conn 10;
    }
}
```

### 3. limit_rate(下载限速)

```nginx
location /download/ {
    limit_rate 100k;            # 100 KB/s
    limit_rate_after 1m;         # 前 1MB 不限速
}
```

### 4. limit_req_dry_run(测试模式)

```nginx
limit_req_dry_run on;           # 仅日志,不真正拒绝
```

---

## 十四、SSL / TLS 配置

### 1. HTTP → HTTPS 跳转

```nginx
server {
    listen 80;
    server_name example.com;
    return 301 https://$host$request_uri;
}
```

### 2. HTTPS server

```nginx
server {
    listen 443 ssl http2;
    server_name example.com;

    ssl_certificate     /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA384;
    ssl_prefer_server_ciphers on;
    ssl_session_cache   shared:SSL:50m;
    ssl_session_timeout 1d;
    ssl_session_tickets on;

    ssl_stapling       on;
    ssl_stapling_verify on;
    resolver           8.8.8.8 1.1.1.1 valid=300s;
    resolver_timeout   5s;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
}
```

### 3. HTTP/2 / HTTP/3

```nginx
listen 443 ssl http2;
# listen 443 quic;     # HTTP/3(1.25+)
# add_header Alt-Svc 'h3=":443"; ma=86400';
```

### 4. SSL session ticket 密钥

```nginx
ssl_session_ticket_key /etc/nginx/ssl/ticket.key;
```

---

## 十五、安全与 Header

### 1. 通用安全 Header

```nginx
add_header X-Frame-Options          "SAMEORIGIN" always;
add_header X-Content-Type-Options   "nosniff" always;
add_header X-XSS-Protection         "1; mode=block" always;
add_header Referrer-Policy          "strict-origin-when-cross-origin" always;
add_header Content-Security-Policy  "default-src 'self'" always;
add_header Permissions-Policy        "geolocation=(), microphone=()" always;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header Cross-Origin-Opener-Policy   "same-origin" always;
add_header Cross-Origin-Embedder-Policy "require-corp" always;
add_header Cross-Origin-Resource-Policy "same-origin" always;
```

### 2. 隐藏信息

```nginx
server_tokens off;
proxy_hide_header X-Powered-By;
proxy_hide_header Server;
more_clear_headers "X-Powered-By";
```

### 3. limit_except(方法限制)

```nginx
location /api/ {
    limit_except GET POST {
        deny all;
    }
}
```

### 4. 路径限制

```nginx
location ~ /\.(?!well-known) {
    deny all;       # 禁止访问隐藏文件(.git / .env 等)
}
```

### 5. valid_referers(防盗链)

```nginx
location /static/ {
    valid_referers none blocked server_names example.com *.example.com;
    if ($invalid_referer) {
        return 403;
    }
}
```

---

## 十六、状态与监控

### 1. stub_status(基础状态)

```nginx
location = /basic_status {
    stub_status on;
    access_log off;
    allow 127.0.0.1;
    deny  all;
}
```

### 2. vts 模块(详细指标 + Prometheus)

```nginx
location /vts {
    vhost_traffic_status_display;
    vhost_traffic_status_display_format json;
}
```

### 3. 健康端点

```nginx
location = /health {
    access_log off;
    return 200 "OK\n";
    add_header Content-Type text/plain;
}

location = /ready {
    access_log off;
    return 200 "READY\n";
}
```

### 4. 自定义指标上报

```nginx
location = /metrics {
    access_log off;
    default_type text/plain;
    return 200 "# HELP active_connections Active\n# TYPE active_connections gauge\nactive_connections $connections_active\n";
}
```

---

## 十七、include 与配置组织

### 1. 拆分策略

```nginx
# /etc/nginx/nginx.conf(主配置)
http {
    include mime.types;
    include conf.d/*.conf;          # 站点
    include snippets/gzip.conf;
    include snippets/ssl.conf;
    include snippets/security-headers.conf;
    include snippets/proxy-params.conf;
}
```

### 2. 片段(snippet)

```nginx
# snippets/proxy-params.conf
proxy_http_version 1.1;
proxy_set_header Host $host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_connect_timeout 5s;
proxy_read_timeout 60s;
```

```nginx
# 在 server 中使用
location /api/ {
    include snippets/proxy-params.conf;
    proxy_pass http://backend;
}
```

### 3. 配置变量化

```nginx
# 使用 define 风格(借助 env / map)
map $http_x_release $backend_name {
    default "stable";
    "canary" "canary";
}

upstream stable { server 10.0.0.1:8080; }
upstream canary { server 10.0.0.2:8080; }

server {
    location / {
        proxy_pass http://$backend_name;
    }
}
```

---

## 十八、配置验证与热加载

### 1. 验证语法

```bash
nginx -t                              # 默认 /etc/nginx/nginx.conf
nginx -t -c /path/to/nginx.conf       # 指定配置
```

### 2. 平滑热加载

```bash
nginx -s reload                       # 等价 kill -HUP master
# Master 收到信号 → fork 新 worker → 旧 worker 处理完请求后退出
```

### 3. 平滑停机

```bash
nginx -s quit                         # 优雅退出(等请求完成)
nginx -s stop                         # 立即停止
```

### 4. 强制重载(配置有问题但已运行)

```bash
# 1. 测试新配置
nginx -t

# 2. 重新加载
nginx -s reload
```

### 5. 配置版本管理

```bash
# 备份旧配置
cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.bak

# 测试
diff /etc/nginx/nginx.conf /etc/nginx/nginx.conf.bak

# 提交 git
git add /etc/nginx/ && git commit -m "add new site"
```

---

## 十九、调试与排错

### 1. debug 日志(慎用)

```nginx
error_log /var/log/nginx/error.log debug;     # 生产不开,极耗 CPU
```

### 2. 常见调试指令

```bash
nginx -V              # 版本 + 编译参数
nginx -t              # 测语法
nginx -T              # 测 + 打印完整配置
```

### 3. 配置检查清单

```text
□ nginx -t 通过
□ pid 文件可写
□ 证书路径正确(fullchain + key)
□ listen 端口未占用(ss -tlnp)
□ upstream 后端可达(curl)
□ worker_rlimit_nofile < ulimit -n
□ include 文件存在
□ 文件权限可读
□ 日志目录可写
□ proxy_cache_path 目录存在
□ map / geo 数据文件存在
```

---

## 二十、常用配置模板

### 1. 反向代理 + 网关

```nginx
upstream api_backend {
    server 10.0.0.1:8080 max_fails=3 fail_timeout=30s;
    server 10.0.0.2:8080 max_fails=3 fail_timeout=30s;
    keepalive 32;
}

server {
    listen 80 reuseport;
    server_name api.example.com;

    # 安全
    include snippets/security-headers.conf;

    # 限流
    limit_req zone=rate burst=100 nodelay;

    # 反代
    location /api/ {
        proxy_pass http://api_backend;
        include snippets/proxy-params.conf;
    }

    # 健康
    location = /health {
        access_log off;
        return 200 "OK\n";
    }
}
```

### 2. 静态资源服务

```nginx
server {
    listen 80 reuseport;
    server_name static.example.com;
    root /var/www/static;

    # 隐藏文件
    location ~ /\.(?!well-known) { deny all; }

    location / {
        try_files $uri $uri/ =404;

        # 文件缓存
        open_file_cache max=10000 inactive=30s;
    }

    location ~* \.(jpg|jpeg|png|gif|webp|css|js|woff2?)$ {
        expires 365d;
        add_header Cache-Control "public, immutable";
        access_log off;
    }

    location ~* \.(html|json)$ {
        expires 1h;
    }
}
```

### 3. HTTPS 全站

```nginx
server {
    listen 80;
    server_name example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2 default_server;
    server_name example.com;

    ssl_certificate     /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;

    include snippets/ssl-params.conf;
    include snippets/security-headers.conf;

    root /var/www/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

### 4. 灰度发布(按 Header)

```nginx
map $http_x_release $backend {
    default "stable";
    "canary" "canary";
}

upstream stable { server 10.0.0.1:8080; }
upstream canary { server 10.0.0.2:8080; }

server {
    listen 80;
    server_name example.com;

    location / {
        # 注意:用 redirect 避免 if 副作用
        if ($backend = "canary") {
            proxy_pass http://canary;
        }
        proxy_pass http://stable;
    }
}
```

### 5. L4 TCP 代理

```nginx
stream {
    upstream mysql {
        server 10.0.0.1:3306;
        server 10.0.0.2:3306;
    }

    server {
        listen 3306;
        proxy_pass mysql;
        proxy_timeout 60s;
        proxy_connect_timeout 5s;
    }
}
```

---

## 二十一、配置常见陷阱

### 1. 末尾 `/` 错配

```nginx
# ❌ 错(多带前缀)
location /api/ { proxy_pass http://backend; }

# ✅ 对(剥离)
location /api/ { proxy_pass http://backend/; }
```

### 2. if 指令副作用

```nginx
# ❌ 错:if + proxy_pass 不可靠
if ($args = "debug=1") { proxy_pass http://debug_backend; }

# ✅ 对:用 map
map $args $backend {
    default "prod";
    ~*debug=1 "debug";
}
```

### 3. upstream keepalive 没生效

```nginx
# ✅ 必加 HTTP/1.1 + 清空 Connection
proxy_http_version 1.1;
proxy_set_header Connection "";
```

### 4. proxy_buffer_size 太小

```nginx
proxy_buffer_size    16k;       # 默认 4k,某些响应头超过(cookie 长)
proxy_buffers        8 32k;
```

### 5. listen 没 default_server

```nginx
# 多个 server 时未匹配,默认按 listen 第一个
# 显式 default_server 明确 catch-all
server {
    listen 80 default_server;
    server_name _;
    return 444;
}
```

### 6. worker_rlimit_nofile 小于 ulimit

```nginx
worker_rlimit_nofile 65535;     # 不能超过 ulimit -n
```

### 7. map 数据文件不存在

```nginx
# ❌ 文件不在
geo $country {
    include /etc/nginx/conf/geoip.dat;   # 文件不存在 → 启动失败
}

# ✅ 配合 try_files 或默认
geo $country {
    default "unknown";
    include /etc/nginx/conf/geoip.dat;
}
```

### 8. error_page 死循环

```nginx
# ❌ 错:404 走 /404.html,但 /404.html 不存在又 404
error_page 404 /404.html;

# ✅ 对:internal + try_files
error_page 404 /404.html;
location = /404.html { internal; root /var/www/errors; }
```

---

## 二十二、要点速记

- **配置树形结构**:main → events / http → server → location
- **指令以 `;` 结尾**,块用 `{ }`
- **include** 是拆分的核心
- **http 块指令**对所有 server 生效
- **server 块**定义虚拟主机
- **location 块**匹配 URL(`=` / `^~` / `~` / `~*` / 前缀)
- **upstream 块**定义上游服务器组
- **nginx -t** 测语法,**nginx -s reload** 热加载
- **proxy_pass 末尾 `/`** 决定是否剥离 location 前缀
- **proxy_set_header Connection ""** 是 upstream keepalive 前提
- **map / geo / if** 做条件判断,**map 推荐**
- **变量 $remote_addr** 是客户端 IP(透传见 §七 模块)
- **限流**:`limit_req`(速率)/ `limit_conn`(并发)/ `limit_rate`(下载)
- **缓存**:`proxy_cache`(响应)/ `open_file_cache`(文件描述符)
- **安全 Header**:`X-Frame-Options` / `CSP` / `HSTS` / `nosniff`
- **HTTPS**:`ssl_certificate` + `ssl_certificate_key` + `ssl_protocols`
- **`return 301` vs `rewrite ... permanent`**:简单跳转用前者
- **stub_status / vts** 是监控入口
- **常见错误**:`if` 副作用 / proxy_pass 末尾 `/` / keepalive 配错 / ulimit 不够
- **`server_tokens off`** 隐藏版本号
- **`error_log`** 级别 debug → emerg(生产用 warn 以上)
- **配置组织**:nginx.conf + conf.d/ + snippets/ 三层结构
- **高级特性**:`aio threads`(线程池)/ `reuseport`(共享监听)/ HTTP/3
- **改动后一定**:`nginx -t && nginx -s reload`
- **生产不开 `debug` 日志**(极耗 CPU)
- **include 通配符**:include /etc/nginx/conf.d/*.conf