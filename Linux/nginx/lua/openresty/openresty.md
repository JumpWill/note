# OpenResty

## 一、OpenResty 概述

### 什么是 OpenResty

**OpenResty**:基于 Nginx + LuaJIT 的高性能 Web 平台

- 章亦春 (agentzh) 主导开发
- 把 Lua 脚本嵌入 Nginx
- 同步非阻塞的网络编程模型 (cosocket)
- 可处理十万级并发连接

### 核心组件

| 组件                  | 说明                          |
|-----------------------|-------------------------------|
| **Nginx**             | 核心 HTTP 服务器               |
| **LuaJIT**            | Lua 5.1 兼容的 JIT 编译器       |
| **ngx_lua**           | 把 Lua 嵌入 Nginx 的 C 模块    |
| **stream-lua-nginx-module** | TCP/UDP 流上的 Lua      |
| **lua-resty-\***      | 官方维护的 Lua 库集合          |

### OpenResty vs Nginx

| 维度        | Nginx                 | OpenResty                |
|-------------|-----------------------|--------------------------|
| 配置        | 纯配置文件              | 配置文件 + Lua 脚本       |
| 灵活性      | 受限于模块             | 灵活编程                  |
| 性能        | 高                    | 同样高(零拷贝)           |
| 适用        | 反向代理、负载均衡       | 网关层编程、复杂业务逻辑   |

---

## 二、架构与运行机制

### 1. 进程模型

```text
Master 进程
├── Worker 1 (Lua VM A)
├── Worker 2 (Lua VM B)
├── Worker 3 (Lua VM C)
└── ...
```

- **Master**:管理 Worker,不处理请求
- **Worker**:每个 Worker 一个独立 Lua VM,处理请求
- **Worker 数**:`worker_processes auto` (一般等于 CPU 核数)
- **请求分发**:每个请求只在一个 Worker 中处理

### 2. 协程模型

**OpenResty 的"协程"= Lua 协程 + 异步 I/O**

- 一个 Worker 可处理上千连接
- 每个请求一个 Lua 协程
- I/O 阻塞 → 自动 yield,事件就绪 → 唤醒

```text
请求 1 ──┐
请求 2 ──┤── 共用一个 Lua VM,但每个请求独立协程
请求 3 ──┘
```

### 3. 内存共享

**Worker 间内存不共享**,需要靠:

- **共享字典** (shared dict):基于共享内存的 K/V
- **Redis/Memcached** 等外部存储
- **Unix Domain Socket** + 本地守护进程

---

## 三、LuaJIT

### 1. 概述

**LuaJIT**:Lua 5.1 兼容的 JIT 编译器

- 比官方 Lua 解释器快 5-20 倍
- 默认集成在 OpenResty
- 路径:`luajit` 或 `lj`

### 2. LuaJIT vs 标准 Lua

| 维度        | LuaJIT               | Lua 5.1/5.2/5.3    |
|-------------|----------------------|---------------------|
| 性能        | **极快** (JIT)       | 较慢                |
| FFI         | **支持** (C 互操作)  | 不支持              |
| bit 库      | 内置                 | 5.2+ 内置,5.1 需外部 |
| 协程        | 不支持 (但 OpenResty 用自己的) | 支持            |

### 3. LuaJIT 不支持的功能

**避免使用**:

- `goto`
- `string.gmatch` 之外的某些 string 函数性能差
- `table` 大于 2^26 (67M) 元素
- `math.*` 中的某些函数

**FFI 是杀手锏**:可直接调用 C 函数

```lua
local ffi = require("ffi")
ffi.cdef[[
    int printf(const char *fmt, ...);
]]
ffi.C.printf("Hello, %s!\n", "World")
```

### 4. OpenResty 中使用 LuaJIT

- 默认使用 LuaJIT
- `lua-nginx-module` 也支持标准 Lua,但 **OpenResty 默认 LuaJIT**

---

## 四、执行阶段 (Phases)

### 1. 阶段总览

```text
请求进入
   │
   ▼
┌─────────────────────┐
│ init_by_lua         │  Master 启动时执行 1 次
└─────────────────────┘
   ▼
┌─────────────────────┐
│ init_worker_by_lua  │  每个 Worker 启动时执行 1 次
└─────────────────────┘
   ▼
请求阶段(每个请求):
   │
   ▼
┌─────────────────────┐
│ ssl_certificate_by_lua* │  SSL 握手
└─────────────────────┘
   ▼
┌─────────────────────┐
│ set_by_lua*         │  设置 Nginx 变量
└─────────────────────┘
   ▼
┌─────────────────────┐
│ rewrite_by_lua*     │  URL 重写
└─────────────────────┘
   ▼
┌─────────────────────┐
│ access_by_lua*      │  访问控制
└─────────────────────┘
   ▼
┌─────────────────────�
│ content_by_lua*     │  内容生成
└─────────────────────┘
   ▼
┌─────────────────────┐
│ balancer_by_lua*    │  负载均衡
└─────────────────────┘
   ▼
┌─────────────────────┐
│ header_filter_by_lua*  │  响应头处理
└─────────────────────┘
   ▼
┌─────────────────────┐
│ body_filter_by_lua*    │  响应体处理
└─────────────────────┘
   ▼
┌─────────────────────┐
│ log_by_lua*         │  日志
└─────────────────────┘
```

### 2. 阶段详解

| 阶段                    | 时机                            | 常用场景                |
|-------------------------|--------------------------------|-------------------------|
| **init_by_lua**         | Master 启动/reload            | 模块加载、共享字典预热   |
| **init_worker_by_lua**  | Worker 启动/reload            | 定时任务、健康检查       |
| **ssl_certificate_by_lua** | SSL 握手时                   | 动态证书                 |
| **set_by_lua**          | 每次请求,设置变量              | 复杂变量计算             |
| **rewrite_by_lua**      | Nginx rewrite 阶段             | URL 重写、跳转           |
| **access_by_lua**       | Nginx access 阶段              | 鉴权、限流、IP 黑名单    |
| **content_by_lua**      | 内容生成阶段                    | **业务逻辑主战场**       |
| **balancer_by_lua**     | upstream 选择                   | 动态负载均衡             |
| **header_filter_by_lua** | 响应头过滤                    | 修改响应头               |
| **body_filter_by_lua**  | 响应体过滤 (可能多次调用)       | 修改/压缩响应体          |
| **log_by_lua**          | 日志阶段                        | 自定义访问日志           |

### 3. 阶段使用方式

```nginx
# 方式 1:内联代码 (不推荐)
location / {
    content_by_lua 'ngx.say("hello")';
}

# 方式 2:代码块
location / {
    content_by_lua_block {
        ngx.say("hello")
    }
}

# 方式 3:外部文件 (推荐)
location / {
    content_by_lua_file conf/lua/hello.lua;
}
```

---

## 五、常用 API (ngx.\*)

### 1. 输出与响应

```lua
ngx.say("hello")           -- 输出并自动换行
ngx.print("hello")         -- 输出不换行
ngx.flush(true)            -- 立即刷新到客户端
ngx.eof()                  -- 提前关闭连接
ngx.status = 404           -- 设置状态码
ngx.header["X-Foo"] = "bar"  -- 设置响应头
```

### 2. 请求信息

```lua
ngx.var.arg_name           -- 获取 URL 参数 ?name=xxx
ngx.var.http_host          -- Host 头
ngx.var.remote_addr        -- 客户端 IP
ngx.req.get_headers()      -- 请求头(可设置 max_headers)
ngx.req.get_uri_args()     -- GET 参数
ngx.req.get_post_args()    -- POST 参数
ngx.req.get_body_data()    -- 请求体
ngx.req.read_body()        -- 显式读取请求体
```

### 3. 变量操作

```lua
ngx.var.variable_name      -- 读写 Nginx 变量
```

**注意**:`ngx.var.*` 是字符串,需要 `tonumber()` 转换

### 4. 编码

```lua
ngx.encode_args({a=1, b=2})  -- URL 编码 table
ngx.decode_args("a=1&b=2")   -- URL 解码字符串
ngx.encode_base64(str)       -- Base64
ngx.decode_base64(str)
ngx.encode_uri(str, opts)    -- URI 编码
```

### 5. 时间

```lua
ngx.now()                  -- 当前时间(秒,浮点)
ngx.time()                 -- 当前时间戳(秒,整数)
ngx.var.msec               -- 毫秒
ngx.sleep(0.1)             -- 非阻塞 sleep
ngx.update_time()          -- 强制刷新缓存的时间
```

### 6. 日志

```lua
ngx.log(ngx.ERR, "error msg")
ngx.log(ngx.WARN, "warn msg")
ngx.log(ngx.INFO, "info msg")
ngx.log(ngx.DEBUG, "debug msg")
```

**级别**:`STDERR` < `EMERG` < `ALERT` < `CRIT` < `ERR` < `WARN` < `NOTICE` < `INFO` < `DEBUG`

### 7. 重定向与跳转

```lua
ngx.redirect("/new_path", 302)  -- 302 跳转
ngx.exec("/internal")           -- 内部跳转 (不发回客户端)
ngx.req.set_uri("/new")        -- 重写 URI
```

---

## 六、共享字典 (lua_shared_dict)

### 1. 概述

**共享字典**:Worker 间共享的 K/V 存储

- 分配在共享内存
- **所有 Worker 可见**
- 有 LRU 淘汰
- 适合缓存、限流、计数器

### 2. 配置

```nginx
http {
    lua_shared_dict my_cache 100m;   # 100MB 共享字典
}
```

### 3. API

```lua
local dict = ngx.shared.my_cache

-- 基本操作
dict:set("key", "value", ttl)       -- 设置(可选 TTL 秒)
dict:get("key")                     -- 读取
dict:delete("key")
dict:incr("key", 1, 100)            -- 自增,初始值 100
dict:flush_all()                    -- 清空
dict:flush_expired(num)             -- 清除已过期

-- TTL
local ok, err = dict:set("key", "value", 60)  -- 60 秒过期
local ttl = dict:get_ttl("key")     -- 剩余 TTL

-- 安全操作 (避免竞争)
local val, err = dict:safe_set("k", "v")
local val, err = dict:safe_get("k")
local new, err = dict:safe_inc("k", 1, 0)
```

### 4. 应用场景

| 场景       | 做法                          |
|------------|-------------------------------|
| 缓存       | 存热点数据                     |
| 限流       | `incr` 计数器                 |
| 防重放     | 存 nonce                       |
| 分布式锁   | `add` 操作原子性               |
| 计数器     | 访问计数                       |

### 5. 限制

- 值大小:**2MB** (OpenResty 1.13.6.1+)
- key 大小:**65535 字节**
- 字典数量受限于共享内存
- 复杂数据结构需要序列化

---

## 七、cosocket (网络 I/O)

### 1. 概述

**cosocket**:OpenResty 的非阻塞网络 I/O

- 基于 Lua 协程
- **同步写法,异步性能**
- 可访问 MySQL、Redis、HTTP、TCP、UDP

### 2. TCP/UDP Socket

```lua
local socket = ngx.socket.tcp()

socket:settimeout(1000)             -- 1 秒超时

local ok, err = socket:connect("127.0.0.1", 11211)
local bytes, err = socket:send("get foo\r\n")
local line, err = socket:receive()
socket:close()

-- udp
local udp = ngx.socket.udp()
udp:setpeername("127.0.0.1", 53)
udp:send("query")
local data = udp:receive()
```

### 3. HTTP Client (lua-resty-http)

```lua
local http = require("resty.http")
local httpc = http.new()

httpc:set_timeout(2000)

local res, err = httpc:request_uri("http://example.com", {
    method = "GET",
    query = { a = 1, b = 2 },
    headers = { ["User-Agent"] = "openresty" },
})

if not res then return end

ngx.status = res.status
ngx.say(res.body)
```

### 4. Redis Client (lua-resty-redis)

```lua
local redis = require("resty.redis")
local red = redis.new()

red:set_timeout(1000)
local ok, err = red:connect("127.0.0.1", 6379)
if not ok then return end

local res, err = red:get("foo")
red:set("foo", "bar", "EX", 60)
red:close()
```

### 5. MySQL Client (lua-resty-mysql)

```lua
local mysql = require("resty.mysql")
local db = mysql.new()

db:set_timeout(1000)
local ok, err = db:connect({
    host = "127.0.0.1",
    port = 3306,
    user = "root",
    password = "pass",
    database = "test",
})

local res, err = db:query("SELECT * FROM users WHERE id = " .. ngx.var.arg_id)
db:close()
```

### 6. 连接池

```lua
-- Redis 连接池示例
local redis = require("resty.redis")
local red = redis.new()

local function get_redis()
    local ok, err = red:connect("127.0.0.1", 6379)
    if not ok then return nil, err end
    return red
end

local ok, err = red:set_keepalive(10000, 100)  -- 10s, 100 个连接
```

### 7. 关键优势

- **同步写法**:代码易读
- **异步执行**:不阻塞 Worker
- **统一超时**:可设置毫秒级超时
- **连接复用**:keepalive 池

---

## 八、子请求 (Subrequest)

### 1. 概述

**子请求**:在一个请求中发起其他内部请求

- 不发到客户端
- 可用于组合多个后端响应
- 通过 `ngx.location.capture` 实现

### 2. 用法

```lua
local res = ngx.location.capture("/some/internal", {
    method = ngx.HTTP_POST,
    args = { a = 1, b = 2 },
    body = "raw body",
    headers = { ["Content-Type"] = "application/json" },
})

if res.status == 200 then
    ngx.print(res.body)
end

-- 并发子请求
local res1, res2 = ngx.location.capture_multi({{"/a"}, {"/b"}})
```

### 3. 子请求 vs cosocket

| 维度        | 子请求              | cosocket (HTTP client)     |
|-------------|---------------------|----------------------------|
| 配置        | 走 Nginx location   | 直接连后端                  |
| 灵活性      | 受 location 限制    | 灵活                        |
| 性能        | 快(共享 Lua VM)     | 略慢                        |
| 适用        | 内部模块组合         | 外部服务调用                |

---

## 九、定时任务

### 1. init_worker_by_lua 中启动

```lua
local function heartbeat()
    -- 心跳逻辑
end

local ok, err = ngx.timer.at(0, heartbeat)  -- 立即执行

-- 定时循环
local function schedule()
    local ok, err = ngx.timer.at(5, function(premature)
        if premature then return end
        -- 每 5 秒执行
        do_work()
        schedule()  -- 递归调度
    end)
end

schedule()
```

### 2. 定时器 API

```lua
local handle = ngx.timer.at(delay, callback)
-- delay 秒后调用 callback
-- callback 第一个参数:premature (是否被 Worker 退出打断)
```

### 3. 注意事项

- **定时器回调在协程中运行**,可阻塞
- 但会占用该 Worker 的执行时间
- 不要做长任务

---

## 十、正则表达式 (ngx.re)

### 1. ngx.re.match

```lua
local m, err = ngx.re.match("hello world", "([a-z]+) ([a-z]+)", "i")
if m then
    ngx.say(m[0])    -- "hello world"
    ngx.say(m[1])    -- "hello"
    ngx.say(m[2])    -- "world"
end
```

### 2. ngx.re.find / gsub / split

```lua
local from, to, err = ngx.re.find(s, pattern)
local new, n, err = ngx.re.gsub(s, pattern, replace)
local splits, err = ngx.re.split(s, ",")
```

### 3. 性能选项

```lua
local m = ngx.re.match(s, "regex", {
    jo  = true,   -- 一次性编译
    o   = true,   -- 缓存选项
})
```

### 4. ngx.re vs Lua string

| 维度        | ngx.re.*        | string.*              |
|-------------|-----------------|-----------------------|
| 性能        | **快** (PCRE)   | 慢                     |
| 支持        | PCRE 语法       | Lua 模式               |
| 大小写      | 选项            | 需手动                |

---

## 十一、FFI (调用 C)

### 1. 调用系统 C 库

```lua
local ffi = require("ffi")
local C = ffi.C

ffi.cdef[[
    typedef struct { int pid; } proc_t;
    int getpid(void);
    char *getenv(const char *name);
]]

local pid = C.getpid()
local path = ffi.string(C.getenv("PATH"))
```

### 2. 调用自定义 C 库

```lua
ffi.cdef[[
    int my_func(int a, int b);
]]
local lib = ffi.load("/path/to/lib.so")
local result = lib.my_func(1, 2)
```

### 3. 性能

- FFI 调用极快(纳秒级)
- 比 `os.execute` / `io.popen` 快几个数量级

### 4. 注意

- 必须用 FFI-safe 类型
- C 函数必须可重入
- 不要在 FFI 中阻塞

---

## 十二、常用库 (lua-resty-\*)

| 库                    | 用途                  |
|-----------------------|-----------------------|
| **lua-resty-http**    | HTTP 客户端            |
| **lua-resty-redis**   | Redis 客户端           |
| **lua-resty-mysql**   | MySQL 客户端           |
| **lua-resty-memcached** | Memcached 客户端     |
| **lua-resty-string**  | 字符串处理             |
| **lua-resty-jit-uuid** | UUID 生成            |
| **lua-resty-kafka**   | Kafka 客户端           |
| **lua-resty-dns**     | DNS 解析               |
| **lua-resty-limit**   | 限流                   |
| **lua-resty-lock**    | 分布式锁               |
| **lua-resty-balancer**| 动态负载均衡           |
| **lua-cjson**         | JSON 编解码            |
| **lua-resty-upload**  | 文件上传               |
| **lua-resty-cookie**  | Cookie 处理            |
| **lua-resty-session** | Session               |
| **lua-resty-websocket**| WebSocket            |

---

## 十三、缓存策略

### 1. 多级缓存

```text
请求 → L1 (lua_shared_dict) → L2 (Redis) → L3 (MySQL)
```

### 2. 缓存模式

**Cache-Aside (懒加载)**:

```lua
local cache_key = "user:" .. id
local user = ngx.shared.user_cache:get(cache_key)

if not user then
    local res = db:query("SELECT * FROM users WHERE id = " .. id)
    user = cjson.encode(res)
    ngx.shared.user_cache:set(cache_key, user, 60)
end
```

**Write-Through (同步写)**:

```lua
-- 写缓存 + 写 DB
ngx.shared.user_cache:set(key, val)
db:query("UPDATE ...")
```

**Write-Behind (异步写)**:

```lua
-- 写缓存,异步刷 DB
ngx.shared.user_cache:set(key, val)
ngx.timer.at(0, function() db:query("UPDATE ...") end)
```

### 3. 缓存击穿

```lua
local lock_key = "lock:" .. cache_key
local ok, err = ngx.shared.lock:set(lock_key, 1, 0, 10)  -- 10s 过期
if not ok then
    -- 未拿到锁,短暂等待后重试
    ngx.sleep(0.05)
    return get_data(id)
end

-- 拿到锁,查 DB + 写缓存
local data = db:query(...)
ngx.shared.cache:set(cache_key, data, 60)
ngx.shared.lock:delete(lock_key)
```

---

## 十四、性能优化

### 1. 关键原则

- **避免阻塞操作**:不要在 Lua 中做 CPU 密集型
- **使用 cosocket**:不要用 Lua 写 socket
- **预编译正则**:`jo = true` 选项
- **缓存热点数据**:用 `lua_shared_dict` 或 Redis
- **减少 Nginx 变量读取**:`ngx.var.*` 有开销

### 2. 性能优化清单

| 优化点                   | 方法                              |
|--------------------------|-----------------------------------|
| JSON 编解码              | `cjson.encode` (C 实现)           |
| 正则                     | 预编译 + `jo` 选项                |
| 字典读写                 | `safe_*` 操作避免锁竞争           |
| 字符串拼接               | `table.concat` 比 `..` 快         |
| `ngx.var`                | 缓存到 local 变量                  |
| `ngx.req.get_uri_args()` | 设置 `cache = true` (OpenResty 1.13+) |
| 时间                     | 用 `ngx.now()` (缓存的)             |

### 3. 性能基准

| 操作                     | 耗时         |
|--------------------------|--------------|
| `ngx.say`                | 几百 ns      |
| `ngx.var.*`              | 几百 ns      |
| `shared_dict:get`        | 几十 ns      |
| `cjson.encode`           | 几百 ns/对象  |
| HTTP 子请求 (内部)       | 几百 μs       |
| Redis cosocket           | 几 ms        |

---

## 十五、WAF / 网关层应用

### 1. IP 黑名单

```lua
local ip = ngx.var.remote_addr
local blacklist = ngx.shared.ip_blacklist

if blacklist:get(ip) then
    return ngx.exit(403)
end
```

### 2. 限流

```lua
local limit_key = "rate:" .. ngx.var.remote_addr
local count, err = ngx.shared.rate_limit:incr(limit_key, 1, 0)

if count and count > 100 then
    return ngx.exit(503)
end
```

### 3. 鉴权

```lua
local token = ngx.req.get_headers()["Authorization"]
if not token then
    return ngx.exit(401)
end

-- 验证 token
local res = ngx.location.capture("/verify", { args = { token = token }})
if res.status ~= 200 then
    return ngx.exit(403)
end
```

### 4. 灰度发布

```lua
local user_id = ngx.var.arg_uid
if user_id and user_id % 100 < 10 then  -- 10% 流量
    ngx.var.upstream = "new_version"
else
    ngx.var.upstream = "old_version"
end
```

### 5. 统一鉴权网关

```lua
location /api/ {
    access_by_lua_block {
        -- 1. 鉴权
        local token = ngx.req.get_headers()["X-Token"]
        if not token then return ngx.exit(401) end

        -- 2. 限流
        local c = ngx.shared.rate:incr("ip:" .. ngx.var.remote_addr, 1, 0)
        if c > 1000 then return ngx.exit(429) end

        -- 3. 路由
        ngx.var.backend = select_backend(ngx.var.uri)
    }
}
```

---

## 十六、调试与监控

### 1. 日志调试

```lua
ngx.log(ngx.DEBUG, "debug msg: ", value)
```

需要在 `nginx.conf` 设置:

```nginx
error_log logs/error.log debug;
```

### 2. 性能分析

```lua
local start = ngx.now()
-- do something
local cost = ngx.now() - start
ngx.log(ngx.INFO, "cost: ", cost, "s")
```

### 3. 请求 ID

```lua
local uuid = require("resty.jit-uuid")
ngx.var.req_id = uuid()
```

### 4. 火焰图

```bash
# OpenResty 自带 systemtap 工具
opm get openresty/lua-resty-debug
```

### 5. 错误处理

```lua
local ok, err = pcall(function()
    -- 业务代码
end)

if not ok then
    ngx.log(ngx.ERR, "error: ", err)
    return ngx.exit(500)
end
```

---

## 十七、常见陷阱

### 1. 阻塞陷阱

- **不要用 `os.execute`**:`os.execute` 阻塞 Worker
- **不要用 `io.popen`**:`io.popen` 阻塞
- **不要做长 CPU 计算**:yield 让其他请求饿死
- **不要用 Lua 标准 socket**:用 cosocket

### 2. 内存陷阱

- **不要在 init_by_lua 加载大模块**:占用 Master 内存
- **Lua 函数 upvalue**:可能被闭包持有
- **大响应体**:不要全缓存到内存

### 3. 共享字典陷阱

- **过大字典**:每个 Worker 都有一份
- **无 TTL**:内存泄露
- **热点 key**:竞争严重,考虑分片

### 4. cosocket 陷阱

- **忘记 close**:连接泄露
- **DNS 缓存**:cosocket connect 不走系统 DNS,会查 DNS
- **超时**:一定要设 `set_timeout`

### 5. 升级陷阱

- **reload 不会中断请求**:Lua 代码热更新有延迟
- **init_by_lua 在 reload 时执行**:注意资源
- **变量定义**:模块级变量在 Worker 启动时初始化一次

---

## 十八、OpenResty vs 其他网关

| 维度          | OpenResty    | Kong       | Envoy + WASM | Spring Cloud Gateway |
|---------------|--------------|------------|--------------|----------------------|
| 语言          | Lua          | Lua        | C++ + WASM   | Java                 |
| 性能          | **极高**     | 高         | 高            | 中                   |
| 配置复杂度    | 中            | 中         | 高            | 低                    |
| 生态          | lua-resty-*  | 插件       | WASM 扩展    | Spring 全家桶         |
| 适用          | 高性能网关    | API 网关   | 服务网格      | 微服务网关            |

---

## 十九、部署与运维

### 1. 安装

**官方包**:

```bash
# CentOS
yum install openresty

# 启动
systemctl start openresty

# 命令行
openresty -h
resty -h
```

### 2. 目录结构

```
/usr/local/openresty/
├── nginx/           # Nginx 主程序
├── luajit/          # LuaJIT
├── lualib/          # Lua 库
├── pod/             # Lua 模块文档
└── bin/
    ├── openresty
    └── resty
```

### 3. 配置文件

```
/usr/local/openresty/nginx/conf/
├── nginx.conf
├── conf.d/         # 自定义配置
└── lua/            # Lua 脚本
```

### 4. 常用命令

```bash
# 启动
openresty -p /usr/local/openresty/nginx/

# 停止
openresty -s stop

# 重载 (HUP)
openresty -s reload

# 测试配置
openresty -t

# 单文件运行 Lua
resty -e 'print("hello")'

# 调试
openresty -c conf/nginx.conf -g 'daemon off;'
```

### 5. opm (OpenResty 包管理)

```bash
opm search keyword
opm install user/repo
opm get openresty/lua-resty-redis
```

---

## 二十、核心要点速记

- **OpenResty = Nginx + LuaJIT + ngx_lua**,高性能 Web 平台
- **协程模型**:每个请求一个 Lua 协程,I/O 自动 yield
- **Worker 间不共享内存**,靠 shared dict 或外部存储
- **lua_shared_dict**:Worker 间共享的 K/V,带 LRU
- **cosocket** = 同步写法 + 异步执行,杀手锏特性
- **11 个执行阶段**,`content_by_lua` 是业务主战场
- **`init_worker_by_lua`** 启动定时任务、心跳
- **`log_by_lua`** 自定义访问日志
- **`ngx.re.*`** 比 Lua 原生正则快 (PCRE)
- **FFI** 可调 C 函数,纳秒级
- **cjson** 是 C 实现的 JSON,快
- **避免阻塞**:`os.execute` / `io.popen` / 标准 socket 都阻塞 Worker
- **lua-resty-\*** 库覆盖 Redis、MySQL、HTTP、DNS 等
- **`set_keepalive`** 实现连接池
- **`ngx.timer.at`** 用于定时任务 (在 init_worker 中启动)
- **`access_by_lua`** 是网关鉴权/限流的常用阶段
- **子请求 `ngx.location.capture`** 用于组合内部模块
- **正则加 `jo = true`** 预编译
- **`ngx.req.get_uri_args(max_args, cache=true)`** 缓存参数解析
- **lua_shared_dict 单 key 最大 2MB**
- **lua_shared_dict 字典大小受共享内存限制**
- **opm** 是包管理,类似 luarocks
- **openresty 命令** 是 nginx 命令的超集
- **`-s reload`** 热加载,不中断运行中的请求
- **共享字典 vs Redis**:本地内存 vs 跨机;快 vs 一致性
- **`lua-resty-lock`** 实现分布式锁
- **网关层应用**:鉴权、限流、灰度、聚合、A/B
- **WASM 插件**是 OpenResty 的扩展方向(实验)
- **OpenResty 的 LuaJIT 是 5.1**,与 5.2/5.3 不完全兼容
- **不要在 init_by_lua 阻塞**:会卡住整个 Master
- **`ngx.log(ngx.ERR, ...)`** 是 async-signal-safe 的
- **`ngx.exit(403)`** 立即返回指定状态码
