# HTTP 协议 (Hypertext Transfer Protocol)

## 一、HTTP 概述

### 什么是 HTTP

**HTTP (Hypertext Transfer Protocol，超文本传输协议)**：一种用于传输资源和操作资源的**应用层协议**，采用请求—响应模型。

```text
客户端                                      服务器
  │                                            │
  │ HTTP Request                               │
  ├───────────────────────────────────────────→│
  │                                            │
  │ HTTP Response                              │
  │←───────────────────────────────────────────┤
```

HTTP 最初用于传输 HTML，现在广泛用于：

- Web 页面和静态资源
- REST API / Web API
- 文件上传与下载
- 微服务通信
- CDN 内容分发
- 流媒体和事件流
- WebSocket 握手

### HTTP 的核心特点

- **客户端—服务器模型**
- **请求—响应通信**
- **无状态语义**：协议不自动保存前一次业务状态
- **可扩展**：通过 Header、Method、Status Code 扩展
- **资源导向**：通过 URI 标识资源
- **内容无关**：可传输文本、JSON、图片、视频等
- **可缓存**：内置缓存语义
- **可通过代理转发**

### HTTP 无状态

每个请求在语义上独立：

```text
请求 1:登录
请求 2:查看订单
```

HTTP 本身不会自动记住请求 1 的用户身份。业务状态通常通过以下方式关联：

- Cookie + Session
- Authorization Token
- URL 或请求体中的标识
- 客户端证书

无状态不代表底层每次都重新连接；HTTP 可以复用 TCP 或 QUIC 连接。

### HTTP 协议栈

```text
HTTP/1.1、HTTP/2
        ↓
TLS（HTTPS 时）
        ↓
TCP
        ↓
IP
```

```text
HTTP/3
   ↓
QUIC（内置 TLS 1.3）
   ↓
UDP
   ↓
IP
```

---

## 二、URI、URL 与资源

### 1. URI

**URI (Uniform Resource Identifier)**：用于标识资源。

```text
https://user:pass@example.com:8443/path/file?q=test#section
```

结构：

```text
scheme://userinfo@host:port/path?query#fragment
```

| 部分 | 示例 | 含义 |
| ---- | ---- | ---- |
| Scheme | `https` | 协议方案 |
| Userinfo | `user:pass` | 用户信息，不建议在 URL 中使用密码 |
| Host | `example.com` | 主机名或 IP |
| Port | `8443` | 服务端口 |
| Path | `/path/file` | 资源路径 |
| Query | `q=test` | 查询参数 |
| Fragment | `section` | 客户端片段标识 |

### 2. URL

**URL (Uniform Resource Locator)** 是 URI 的常见形式，既标识资源，也说明访问位置和方式。

```text
https://example.com/products/100?lang=zh
```

### 3. Fragment 不会发送给服务器

```text
https://example.com/page#chapter-2
```

`#chapter-2` 通常只由浏览器使用，不包含在 HTTP 请求目标中。

### 4. 百分号编码

URI 中不能直接安全表示的字节使用百分号编码：

```text
空格 → %20
中文 → 先编码为 UTF-8，再对字节进行百分号编码
```

Query 中 `+` 是否代表空格取决于表单编码和解析规则，不能在所有 URI 场景中一概而论。

### 5. 相对 URI

HTML 和 HTTP Header 可以使用相对引用：

```text
/images/logo.png
../api/users
?sort=time
```

客户端根据基础 URI 解析为绝对地址。

---

## 三、HTTP 请求报文

### 1. HTTP/1.1 请求格式

```http
POST /api/users?notify=true HTTP/1.1
Host: example.com
Content-Type: application/json
Content-Length: 35
Authorization: Bearer token

{"name":"Alice","role":"admin"}
```

结构：

```text
请求行
请求头
空行
可选的消息体
```

### 2. 请求行

```text
METHOD SP request-target SP HTTP-version CRLF
```

示例：

```http
GET /products/100 HTTP/1.1
```

### 3. Request Target 形式

| 形式 | 示例 | 场景 |
| ---- | ---- | ---- |
| origin-form | `/path?q=1` | 普通源站请求 |
| absolute-form | `http://example.com/path` | 正向代理 |
| authority-form | `example.com:443` | CONNECT |
| asterisk-form | `*` | `OPTIONS *` |

### 4. Host Header

HTTP/1.1 请求必须提供 Host 信息：

```http
Host: www.example.com
```

同一 IP 可以托管多个虚拟主机，服务器根据 Host 选择站点。HTTP/2 和 HTTP/3 使用 `:authority` 伪首部表达相同信息。

### 5. 请求体

常见携带请求体的方法：

- POST
- PUT
- PATCH

协议并未简单禁止其他方法携带请求体，但部分服务器、代理和客户端不支持或不定义其语义。例如 GET 请求体没有通用一致的语义，不应依赖它传参。

---

## 四、HTTP 响应报文

### 1. HTTP/1.1 响应格式

```http
HTTP/1.1 200 OK
Content-Type: application/json; charset=utf-8
Content-Length: 27
Cache-Control: no-cache

{"id":100,"name":"Alice"}
```

结构：

```text
状态行
响应头
空行
可选的消息体
```

### 2. 状态行

```text
HTTP-version SP status-code SP reason-phrase CRLF
```

示例：

```http
HTTP/1.1 404 Not Found
```

Reason Phrase 主要供人阅读，HTTP/2 和 HTTP/3 不再传输它，程序应根据状态码判断结果。

### 3. 响应体

以下响应通常没有消息体：

- HEAD 请求的响应
- 1xx 信息响应
- 204 No Content
- 304 Not Modified
- CONNECT 成功后切换为隧道

服务器仍可能在 HEAD 响应中发送表示“若为 GET 时响应体会有多大”的 Content-Length。

---

## 五、HTTP 方法

### 1. 常用方法

| 方法 | 典型语义 | 安全 | 幂等 |
| ---- | -------- | ---- | ---- |
| **GET** | 获取资源 | 是 | 是 |
| **HEAD** | 只获取响应头 | 是 | 是 |
| **POST** | 提交数据、触发处理、创建子资源 | 否 | 通常否 |
| **PUT** | 创建或完整替换指定资源 | 否 | 是 |
| **PATCH** | 部分修改资源 | 否 | 不一定 |
| **DELETE** | 删除资源 | 否 | 是 |
| **OPTIONS** | 查询通信选项 | 是 | 是 |
| **CONNECT** | 建立隧道 | 否 | 否 |
| **TRACE** | 回显诊断请求 | 是 | 是 |

### 2. 安全方法

**Safe Method** 表示客户端请求的语义是只读，不应主动修改服务器状态：

```text
GET、HEAD、OPTIONS、TRACE
```

日志、计费等附带影响不改变其安全语义，但不能用 GET 实现删除、转账等操作。

### 3. 幂等方法

同一个请求执行一次或多次，预期资源状态相同：

```text
PUT /users/100
DELETE /users/100
```

幂等不代表响应完全相同，也不代表请求没有副作用；日志数量和首次/再次响应状态可以不同。

### 4. POST 与 PUT

```text
POST /orders
```

- 由服务器决定新资源 URI
- 重复提交可能创建多个订单

```text
PUT /users/100
```

- 客户端指定目标 URI
- 重复发送同一表示，最终资源状态应相同

### 5. PATCH

PATCH 表示部分更新，常见格式：

```http
Content-Type: application/merge-patch+json
```

```json
{"nickname":"Will"}
```

或：

```http
Content-Type: application/json-patch+json
```

PATCH 是否幂等取决于补丁格式和操作语义。

### 6. OPTIONS 与 Allow

```http
OPTIONS /api/users HTTP/1.1
Host: example.com
```

响应：

```http
HTTP/1.1 204 No Content
Allow: GET, POST, OPTIONS
```

OPTIONS 也用于 CORS 预检。

---

## 六、HTTP 状态码

### 1. 状态码分类

| 范围 | 类型 | 含义 |
| ---- | ---- | ---- |
| 1xx | 信息 | 请求已收到，继续处理 |
| 2xx | 成功 | 请求成功 |
| 3xx | 重定向 | 需要进一步操作或使用缓存 |
| 4xx | 客户端错误 | 请求本身有问题或无权限 |
| 5xx | 服务器错误 | 服务器处理失败 |

### 2. 常见 1xx

| 状态码 | 名称 | 说明 |
| ------ | ---- | ---- |
| **100** | Continue | 可以继续发送请求体 |
| **101** | Switching Protocols | 切换协议，如 WebSocket |
| **102** | Processing | WebDAV，正在处理 |
| **103** | Early Hints | 提前发送资源提示 |

### 3. 常见 2xx

| 状态码 | 名称 | 说明 |
| ------ | ---- | ---- |
| **200** | OK | 请求成功 |
| **201** | Created | 已创建资源，常配合 Location |
| **202** | Accepted | 已接受，尚未完成异步处理 |
| **204** | No Content | 成功但无响应体 |
| **206** | Partial Content | 返回范围请求的一部分 |

### 4. 常见 3xx

| 状态码 | 名称 | 说明 |
| ------ | ---- | ---- |
| **301** | Moved Permanently | 永久重定向 |
| **302** | Found | 临时重定向，历史客户端可能改为 GET |
| **303** | See Other | 使用 GET 访问另一个 URI |
| **304** | Not Modified | 缓存验证通过，继续使用本地副本 |
| **307** | Temporary Redirect | 临时重定向，保留方法和请求体 |
| **308** | Permanent Redirect | 永久重定向，保留方法和请求体 |

### 5. 常见 4xx

| 状态码 | 名称 | 说明 |
| ------ | ---- | ---- |
| **400** | Bad Request | 请求语法或参数错误 |
| **401** | Unauthorized | 缺少或无效身份认证 |
| **403** | Forbidden | 已理解请求，但拒绝授权 |
| **404** | Not Found | 资源不存在或不愿透露 |
| **405** | Method Not Allowed | 方法不允许，应返回 Allow |
| **406** | Not Acceptable | 无法生成客户端接受的表示 |
| **408** | Request Timeout | 请求超时 |
| **409** | Conflict | 与当前资源状态冲突 |
| **410** | Gone | 资源已永久删除 |
| **411** | Length Required | 需要 Content-Length |
| **412** | Precondition Failed | 条件请求失败 |
| **413** | Content Too Large | 请求体过大 |
| **414** | URI Too Long | URI 过长 |
| **415** | Unsupported Media Type | 不支持请求内容类型 |
| **416** | Range Not Satisfiable | 请求范围无效 |
| **422** | Unprocessable Content | 语法正确但语义校验失败 |
| **426** | Upgrade Required | 需要升级协议 |
| **429** | Too Many Requests | 请求过多，常配合 Retry-After |
| **431** | Request Header Fields Too Large | Header 过大 |
| **451** | Unavailable For Legal Reasons | 因法律原因不可用 |

### 6. 401 与 403

```text
401:你是谁? 请认证
403:知道你是谁，但你无权访问
```

401 响应通常包含：

```http
WWW-Authenticate: Bearer
```

### 7. 常见 5xx

| 状态码 | 名称 | 说明 |
| ------ | ---- | ---- |
| **500** | Internal Server Error | 服务器内部错误 |
| **501** | Not Implemented | 不支持该功能 |
| **502** | Bad Gateway | 网关从上游收到无效响应 |
| **503** | Service Unavailable | 服务暂时不可用 |
| **504** | Gateway Timeout | 网关等待上游超时 |
| **505** | HTTP Version Not Supported | 不支持该 HTTP 版本 |

### 8. 502、503、504 对比

```text
502:上游返回了坏响应或连接被异常断开
503:服务当前不可用或主动过载保护
504:网关等待上游响应超时
```

具体含义还受代理软件实现影响，应结合网关和上游日志判断。

---

## 七、HTTP Header

### 1. Header 基本格式

```text
Field-Name: Field-Value
```

HTTP 字段名大小写不敏感，但通常使用规范写法便于阅读。HTTP/2 和 HTTP/3 要求线上字段名使用小写。

### 2. 常见请求 Header

| Header | 作用 |
| ------ | ---- |
| **Host** | 目标主机和可选端口 |
| **User-Agent** | 客户端信息 |
| **Accept** | 可接受的媒体类型 |
| **Accept-Encoding** | 可接受的内容编码 |
| **Accept-Language** | 首选语言 |
| **Authorization** | 身份认证凭据 |
| **Cookie** | 客户端 Cookie |
| **Referer** | 来源页面 URI |
| **Origin** | 请求来源 Origin |
| **If-None-Match** | ETag 条件请求 |
| **If-Modified-Since** | 修改时间条件请求 |
| **Range** | 请求资源的一部分 |

### 3. 常见响应 Header

| Header | 作用 |
| ------ | ---- |
| **Content-Type** | 响应表示的媒体类型 |
| **Content-Length** | 消息体字节数 |
| **Content-Encoding** | 内容压缩/编码方式 |
| **Cache-Control** | 缓存策略 |
| **ETag** | 资源版本标识 |
| **Last-Modified** | 最后修改时间 |
| **Location** | 重定向地址或新资源地址 |
| **Set-Cookie** | 设置 Cookie |
| **WWW-Authenticate** | 认证方式挑战 |
| **Retry-After** | 建议重试时间 |
| **Content-Range** | 部分响应的范围 |
| **Vary** | 缓存键还需考虑的请求 Header |

### 4. 表示元数据

以下 Header 描述消息体的表示：

```http
Content-Type: application/json; charset=utf-8
Content-Encoding: gzip
Content-Language: zh-CN
Content-Length: 1024
```

### 5. 端到端与逐跳 Header

逐跳 Header 只对当前连接有效，不应由代理直接转发：

- Connection
- Keep-Alive
- Proxy-Authenticate
- Proxy-Authorization
- TE
- Trailer
- Transfer-Encoding
- Upgrade

HTTP/2 和 HTTP/3 不使用 Connection 等连接专属字段。

### 6. 自定义 Header

可以定义应用专用字段：

```http
Idempotency-Key: 4cfe...
Traceparent: 00-...
X-Request-ID: req-123
```

新标准字段不再要求使用 `X-` 前缀，但现有系统中仍很常见。

---

## 八、请求体与媒体类型

### 1. Content-Type

```http
Content-Type: type/subtype; parameter=value
```

常见媒体类型：

| 类型 | 用途 |
| ---- | ---- |
| `text/html` | HTML |
| `text/plain` | 纯文本 |
| `text/css` | CSS |
| `application/json` | JSON |
| `application/xml` | XML |
| `application/octet-stream` | 任意二进制 |
| `application/x-www-form-urlencoded` | 普通表单 |
| `multipart/form-data` | 文件上传表单 |
| `image/png` | PNG 图片 |
| `video/mp4` | MP4 视频 |

### 2. JSON 请求

```http
POST /api/users HTTP/1.1
Host: example.com
Content-Type: application/json

{"name":"Alice","age":20}
```

服务器应验证：

- Content-Type
- 请求体大小
- JSON 语法
- 字段类型
- 必填字段
- 业务规则

### 3. URL 编码表单

```http
Content-Type: application/x-www-form-urlencoded

name=Alice&role=admin
```

字段使用表单 URL 编码规则，不等同于任意 URI 组件编码。

### 4. Multipart 文件上传

```http
Content-Type: multipart/form-data; boundary=----boundary
```

```text
------boundary
Content-Disposition: form-data; name="title"

photo
------boundary
Content-Disposition: form-data; name="file"; filename="a.png"
Content-Type: image/png

<binary data>
------boundary--
```

不要手动只设置 Content-Type 而遗漏 boundary；浏览器和 HTTP 库通常会自动生成。

### 5. Charset

```http
Content-Type: text/html; charset=utf-8
```

JSON 的网络编码通常使用 UTF-8。文本协议应明确字符编码，避免客户端和服务器解释不一致。

---

## 九、消息体长度与传输编码

### 1. Content-Length

```http
Content-Length: 1024
```

表示 HTTP 消息体的字节数，不包含 Header。

### 2. Chunked Transfer Coding

HTTP/1.1 可以逐块传输未知总长度的消息体：

```http
Transfer-Encoding: chunked

4
Wiki
5
pedia
0

```

每块格式：

```text
十六进制长度 CRLF
块数据 CRLF
```

长度为 0 的块表示结束，之后可以携带 Trailer。

### 3. HTTP/2 和 HTTP/3

HTTP/2 和 HTTP/3 使用二进制帧表达数据边界，不使用 HTTP/1.1 的 `Transfer-Encoding: chunked`。

### 4. 长度冲突

代理和服务器若对 Content-Length 与 Transfer-Encoding 的解析不同，可能造成 HTTP Request Smuggling。

安全处理：

- 严格遵循协议解析规则
- 拒绝模糊、冲突或重复长度信息
- 前端代理和后端服务器使用一致的解析策略
- 保持代理和服务器软件更新

---

## 十、内容协商

### 1. 媒体类型协商

请求：

```http
Accept: application/json, text/html;q=0.8, */*;q=0.1
```

服务器选择合适的表示：

```http
Content-Type: application/json
```

`q` 表示偏好权重，范围 0~1。

### 2. 压缩协商

请求：

```http
Accept-Encoding: br, gzip
```

响应：

```http
Content-Encoding: br
Vary: Accept-Encoding
```

### 3. 语言协商

```http
Accept-Language: zh-CN, zh;q=0.9, en;q=0.5
```

响应可包含：

```http
Content-Language: zh-CN
Vary: Accept-Language
```

### 4. Vary

```http
Vary: Accept-Encoding, Accept-Language
```

告诉缓存：这些请求 Header 不同，应视为不同缓存变体。`Vary: *` 会显著限制共享缓存复用。

---

## 十一、HTTP 缓存

### 1. 缓存类型

| 类型 | 示例 | 特点 |
| ---- | ---- | ---- |
| 私有缓存 | 浏览器缓存 | 单个用户使用 |
| 共享缓存 | CDN、代理缓存 | 多个用户共享 |
| 服务端缓存 | 应用、反向代理 | 不完全由 HTTP 规范控制 |

### 2. 强缓存

响应：

```http
Cache-Control: public, max-age=3600
```

在 3600 秒内，缓存可以直接使用响应，无需向源站验证。

### 3. 条件请求

第一次响应：

```http
ETag: "v123"
Last-Modified: Wed, 30 Jul 2026 10:00:00 GMT
```

再次请求：

```http
If-None-Match: "v123"
If-Modified-Since: Wed, 30 Jul 2026 10:00:00 GMT
```

资源未变化：

```http
HTTP/1.1 304 Not Modified
```

客户端继续使用缓存中的响应体。

### 4. ETag

```http
ETag: "abc123"       # 强验证器
ETag: W/"abc123"     # 弱验证器
```

- 强 ETag 表示字节级等价
- 弱 ETag 表示语义上等价，字节可能不同
- ETag 通常比秒级 Last-Modified 更精确

### 5. Cache-Control 常用指令

| 指令 | 含义 |
| ---- | ---- |
| **max-age=N** | 客户端缓存新鲜时间 |
| **s-maxage=N** | 共享缓存新鲜时间，覆盖 max-age |
| **public** | 允许共享缓存存储 |
| **private** | 仅私有缓存存储 |
| **no-cache** | 可存储，但复用前必须验证 |
| **no-store** | 不应存储请求或响应 |
| **must-revalidate** | 过期后必须向源站验证 |
| **proxy-revalidate** | 共享缓存过期后必须验证 |
| **immutable** | 新鲜期内内容不会变化 |
| **stale-while-revalidate=N** | 后台验证时允许暂用过期内容 |
| **stale-if-error=N** | 源站错误时允许暂用过期内容 |

### 6. no-cache 与 no-store

```text
no-cache:可以保存，但每次使用前要验证
no-store:不要保存
```

`no-cache` 不是“完全不缓存”。

### 7. Expires

```http
Expires: Wed, 30 Jul 2026 11:00:00 GMT
```

是较早的绝对时间缓存机制。现代服务通常优先使用 Cache-Control，因为它使用相对时间并提供更丰富的控制。

### 8. 缓存静态资源

常见策略：

```text
文件名包含内容哈希:
app.a1b2c3.js

Cache-Control: public, max-age=31536000, immutable
```

内容变化时生成新文件名，无需频繁验证旧资源。

### 9. 不应误缓存私有数据

用户专属响应应谨慎设置：

```http
Cache-Control: private, no-store
```

还要检查 CDN 缓存键是否正确包含 Authorization、Cookie 或其他用户维度，避免不同用户之间泄露数据。

---

## 十二、Cookie 与会话

### 1. 设置 Cookie

响应：

```http
Set-Cookie: session_id=abc123; Path=/; Secure; HttpOnly; SameSite=Lax
```

后续请求：

```http
Cookie: session_id=abc123
```

### 2. Cookie 属性

| 属性 | 作用 |
| ---- | ---- |
| **Domain** | Cookie 可发送到的域范围 |
| **Path** | Cookie 可发送到的路径范围 |
| **Expires** | 绝对过期时间 |
| **Max-Age** | 相对有效时间 |
| **Secure** | 仅通过安全连接发送 |
| **HttpOnly** | 禁止 JavaScript 通过 `document.cookie` 读取 |
| **SameSite** | 限制跨站请求携带 Cookie |
| **Partitioned** | 分区 Cookie，用于隔离跨站上下文 |

### 3. SameSite

| 值 | 行为 |
| -- | ---- |
| **Strict** | 跨站请求通常不发送 |
| **Lax** | 对部分顶级导航等场景允许 |
| **None** | 允许跨站发送，必须同时设置 Secure |

SameSite 是 CSRF 防护的一层，但不能代替所有 CSRF 防护。

### 4. Session Cookie 与持久 Cookie

- 没有 Expires/Max-Age：通常为会话 Cookie
- 设置 Expires 或 Max-Age：持久 Cookie
- 浏览器会话恢复功能可能保留会话 Cookie，不能把“关闭窗口”作为安全登出保证

### 5. Cookie 安全建议

- 会话 Cookie 使用 Secure、HttpOnly、SameSite
- 登录后轮换 Session ID
- 服务端保存会话失效状态
- 限制 Domain 和 Path
- 不在 Cookie 中保存明文敏感信息
- 对值进行签名或加密不能替代权限校验
- 设置合理过期时间

### 6. Cookie 前缀

```text
__Secure-  要求 Secure
__Host-    要求 Secure、Path=/，且不能设置 Domain
```

支持这些前缀的浏览器会强制对应约束，可减少错误配置。

---

## 十三、HTTP 身份认证

### 1. Basic Authentication

请求：

```http
Authorization: Basic base64(username:password)
```

Base64 不是加密，必须配合 HTTPS。服务端返回挑战：

```http
WWW-Authenticate: Basic realm="admin"
```

### 2. Bearer Token

```http
Authorization: Bearer eyJ...
```

持有 Token 即可使用对应权限，因此必须：

- 全程使用 HTTPS
- 避免写入 URL
- 限制权限和有效期
- 防止日志泄露
- 支持轮换和撤销策略

### 3. Session 认证

```text
用户登录
  ↓
服务器创建 Session
  ↓
Set-Cookie: session_id=...
  ↓
浏览器后续自动携带 Cookie
```

适合浏览器 Web 应用，需要重点防护 CSRF 和 Session 固定攻击。

### 4. API Key

```http
Authorization: ApiKey key-value
```

或自定义 Header。不要把长期密钥放在 URL Query 中，因为 URL 常被浏览器历史、代理和日志记录。

### 5. 客户端证书

mTLS 中，客户端在 TLS 握手时提供证书：

- 双向认证
- 常用于服务间通信和高安全企业环境
- 需要证书签发、轮换和吊销管理

### 6. 认证与授权

```text
认证 Authentication:你是谁
授权 Authorization:你能做什么
```

通过身份认证后，服务器仍需对每个资源和操作执行授权校验。

---

## 十四、HTTP 连接管理

### 1. HTTP/1.0 短连接

早期 HTTP/1.0 通常每次请求新建 TCP 连接：

```text
TCP 握手 → HTTP 请求/响应 → TCP 关闭
```

开销包括 TCP 握手、慢启动和可能的 TLS 握手。

### 2. HTTP/1.1 持久连接

HTTP/1.1 默认使用持久连接：

```text
一个 TCP 连接
  ├── 请求 1 / 响应 1
  ├── 请求 2 / 响应 2
  └── 请求 3 / 响应 3
```

关闭连接：

```http
Connection: close
```

### 3. HTTP/1.1 Pipelining

客户端可以不等待前一个响应就发送多个请求，但服务器必须按请求顺序返回响应：

```text
请求 A、B、C
响应 A 很慢
响应 B、C 即使完成也必须等待 A
```

这会产生应用层队头阻塞，浏览器实际很少使用 HTTP/1.1 Pipelining。

### 4. 空闲连接超时

客户端、服务器、代理、NAT 都可能关闭空闲连接。连接池必须正确处理：

- 空闲连接已被对端关闭
- 请求发送时出现 RST
- 超时后重新建立连接
- 不安全方法不能盲目自动重试

### 5. Expect: 100-continue

客户端准备发送大请求体时，可先发送 Header：

```http
Expect: 100-continue
```

服务器允许后返回：

```http
HTTP/1.1 100 Continue
```

如果认证或大小检查失败，服务器可以直接返回最终错误，避免客户端发送完整大文件。

---

## 十五、HTTP 版本演进

### 1. HTTP/0.9

- 只有简单 GET
- 没有 Header
- 响应直接返回 HTML
- 已淘汰

### 2. HTTP/1.0

- 引入状态码和 Header
- 支持多种媒体类型
- 默认每请求一个连接
- 后期通过非标准或扩展 Keep-Alive 复用连接

### 3. HTTP/1.1

- 持久连接默认启用
- Host Header 支持虚拟主机
- Chunked Transfer Coding
- 更完整的缓存语义
- Range 请求
- 条件请求
- Pipelining

### 4. HTTP/2

HTTP/2 不改变 HTTP 方法、状态码和 URI 等语义，主要改变线上表示和传输方式。

核心特性：

- 二进制分帧
- 一个 TCP 连接上多路复用多个 Stream
- HPACK Header 压缩
- Stream 优先级机制
- 流量控制
- Server Push（实践中已较少使用，浏览器支持已弱化）

### 5. HTTP/2 多路复用

```text
一个 TCP 连接:
Stream 1: HTML
Stream 3: CSS
Stream 5: API
Stream 7: 图片
```

不同 Stream 的帧可以交错传输，不需要像 HTTP/1.1 响应一样严格串行。

### 6. HTTP/2 队头阻塞

HTTP/2 消除了 HTTP/1.1 应用层队头阻塞，但所有 Stream 仍共享一个 TCP 连接：

```text
一个 TCP 报文段丢失
        ↓
TCP 等待重传并按序交付
        ↓
连接上的多个 Stream 都可能暂时受阻
```

### 7. HTTP/3

HTTP/3 使用 QUIC：

- 基于 UDP
- TLS 1.3 集成
- 多个独立 Stream
- QPACK Header 压缩
- 减少传输层队头阻塞
- 支持连接迁移
- 低延迟握手

### 8. HTTP/3 连接迁移

QUIC 使用 Connection ID 标识连接，不完全依赖 IP 和端口四元组：

```text
手机从 Wi-Fi 切换到 5G
IP 地址变化
QUIC 连接可以验证新路径后继续使用
```

### 9. 版本对比

| 维度 | HTTP/1.1 | HTTP/2 | HTTP/3 |
| ---- | -------- | ------ | ------ |
| 传输层 | TCP | TCP | QUIC/UDP |
| 表示 | 文本起始行+Header | 二进制帧 | QUIC 上二进制帧 |
| 多路复用 | 有限 | 支持 | 支持 |
| Header 压缩 | 无 | HPACK | QPACK |
| TLS | 可选，公网通常使用 | 规范允许明文，但浏览器实际通常要求 TLS | TLS 1.3 集成 |
| 队头阻塞 | HTTP 层和 TCP 层 | TCP 层 | 单个 Stream 内 |
| 连接迁移 | 不支持 | 不支持 | 支持 |

---

## 十六、HTTPS 与 TLS

### 1. 什么是 HTTPS

```text
HTTPS = HTTP over TLS
```

TLS 提供：

- 机密性：防止明文窃听
- 完整性：检测传输篡改
- 服务器认证：通过证书验证服务身份
- 可选客户端认证：mTLS

### 2. HTTPS 访问流程

HTTP/1.1 或 HTTP/2：

```text
1. DNS 解析
2. TCP 三次握手
3. TLS 握手
4. HTTP 请求/响应
```

HTTP/3：

```text
1. DNS 解析
2. QUIC + TLS 1.3 握手
3. HTTP/3 请求/响应
```

### 3. 证书验证

客户端通常检查：

- 证书是否由受信任 CA 签发
- 域名是否匹配 SAN
- 是否在有效期内
- 签名链是否有效
- 密钥用途是否正确
- 吊销信息和本地安全策略

### 4. SNI

客户端在 TLS 握手中通过 **SNI (Server Name Indication)** 告诉服务器要访问的域名，使同一 IP 可以选择不同证书。

传统 SNI 通常可被路径观察者看到；ECH 用于加密 ClientHello 中的敏感信息，但部署和支持取决于客户端、DNS 和服务器。

### 5. ALPN

客户端和服务器通过 **ALPN** 协商应用协议：

```text
h2       → HTTP/2
http/1.1 → HTTP/1.1
h3       → HTTP/3 通过 QUIC 协商
```

### 6. TLS 会话恢复

TLS 1.3 可通过 Session Ticket / PSK 恢复会话，减少重复连接握手开销。0-RTT 数据可能被重放，只应承载可安全重试的操作。

### 7. HTTPS 仍不能防止什么

- 服务器自身被入侵
- 客户端恶意脚本读取页面可访问的数据
- 用户主动忽略证书警告
- 应用授权缺陷
- 流量分析得到 IP、大小和时序等元数据

---

## 十七、代理、网关与 CDN

### 1. 正向代理

```text
客户端 → 正向代理 → 互联网服务器
```

代表客户端访问外部资源，用途：

- 企业出口控制
- 隐藏客户端直接地址
- 内容过滤
- 缓存

HTTPS 通常通过 CONNECT 建立 TCP 隧道：

```http
CONNECT example.com:443 HTTP/1.1
Host: example.com:443
```

### 2. 反向代理

```text
客户端 → 反向代理 → 后端应用
```

代表服务器接收请求，用途：

- TLS 终止
- 负载均衡
- 缓存和压缩
- WAF
- 限流
- 路由到不同服务

常见软件：

- Nginx
- HAProxy
- Envoy
- Caddy
- 云负载均衡器

### 3. Forwarded Header

代理可传递原始请求信息：

```http
Forwarded: for=192.0.2.10;proto=https;host=example.com
```

常见非标准字段：

```http
X-Forwarded-For: 192.0.2.10
X-Forwarded-Proto: https
X-Forwarded-Host: example.com
```

应用只能信任由**受信代理**写入和清洗的字段，否则客户端可以自行伪造。

### 4. CDN

```text
用户 → 就近 CDN 边缘节点 → 源站
```

功能：

- 静态和动态内容缓存
- Anycast 或 DNS 调度
- TLS 终止
- DDoS 缓解
- 图片优化
- 回源保护

### 5. CDN 缓存键

常见缓存键可能包含：

- Scheme
- Host
- Path
- Query
- 部分 Header
- Cookie

缓存键配置错误可能导致：

- 不同用户内容串用
- 查询参数被忽略
- 缓存命中率过低
- Web Cache Poisoning

---

## 十八、重定向

### 1. Location

```http
HTTP/1.1 302 Found
Location: https://www.example.com/login
```

Location 可以是绝对 URI，也可在允许的语境中使用相对引用。

### 2. 301 / 302 / 303 / 307 / 308

| 状态码 | 永久性 | 后续方法 |
| ------ | ------ | -------- |
| 301 | 永久 | 历史客户端可能改为 GET |
| 302 | 临时 | 历史客户端可能改为 GET |
| 303 | 临时 | 明确使用 GET |
| 307 | 临时 | 保留原方法和请求体 |
| 308 | 永久 | 保留原方法和请求体 |

### 3. 常见用途

- HTTP 跳转 HTTPS
- 域名规范化
- 登录后跳转
- 资源永久迁移
- POST 成功后使用 303 跳转结果页面

### 4. 重定向问题

- 循环重定向
- 重定向次数过多
- HTTPS 降级到 HTTP
- POST 被意外改成 GET
- Location 使用错误域名
- 开放重定向被用于钓鱼

应用应验证用户提供的跳转目标，优先使用允许列表或站内相对路径。

---

## 十九、Range 与断点续传

### 1. 范围请求

```http
Range: bytes=0-999
```

服务器支持时返回：

```http
HTTP/1.1 206 Partial Content
Content-Range: bytes 0-999/5000
Content-Length: 1000
```

### 2. 常见 Range

```text
bytes=0-999       前 1000 字节
bytes=1000-       从 1000 到末尾
bytes=-500        最后 500 字节
```

### 3. If-Range

```http
If-Range: "etag-value"
Range: bytes=1000-
```

如果资源未变化，返回范围；如果已变化，返回完整新资源，避免把不同版本拼接到一起。

### 4. 用途

- 下载断点续传
- 视频拖动播放
- 大文件分块读取
- 并行下载

服务器应限制过多、重叠或异常 Range，防止资源消耗攻击。

---

## 二十、CORS

### 1. 同源策略

浏览器中的 Origin 由以下三部分组成：

```text
Scheme + Host + Port
```

以下地址不同源：

```text
https://example.com
http://example.com
https://api.example.com
https://example.com:8443
```

同源策略限制脚本读取跨源响应，但不会阻止所有跨源请求被发送。

### 2. 简单跨源请求

服务器允许指定来源：

```http
Access-Control-Allow-Origin: https://app.example.com
```

### 3. 预检请求

浏览器在某些跨源请求前发送 OPTIONS：

```http
OPTIONS /api/users HTTP/1.1
Origin: https://app.example.com
Access-Control-Request-Method: PUT
Access-Control-Request-Headers: Authorization, Content-Type
```

服务器响应：

```http
Access-Control-Allow-Origin: https://app.example.com
Access-Control-Allow-Methods: GET, PUT, OPTIONS
Access-Control-Allow-Headers: Authorization, Content-Type
Access-Control-Max-Age: 600
```

### 4. 携带凭据

响应：

```http
Access-Control-Allow-Credentials: true
Access-Control-Allow-Origin: https://app.example.com
```

允许凭据时，`Access-Control-Allow-Origin` 不能使用 `*`。

客户端还需要显式启用凭据，例如 Fetch 的 `credentials` 选项。

### 5. CORS 不是服务端访问控制

非浏览器客户端不受浏览器 CORS 限制。服务器仍必须执行：

- 身份认证
- 权限检查
- CSRF 防护
- 输入验证

不能用 CORS 代替 API 安全。

---

## 二十一、压缩与编码

### 1. Content-Encoding

```http
Content-Encoding: gzip
```

表示对资源表示进行编码，客户端解码后获得原始内容。

常见算法：

- gzip
- br (Brotli)
- zstd

### 2. Transfer-Encoding

```http
Transfer-Encoding: chunked
```

描述消息在当前 HTTP/1.1 连接上的传输编码，不等同于资源压缩。

### 3. 压缩策略

适合压缩：

- HTML
- CSS
- JavaScript
- JSON
- XML
- SVG

通常不必再次压缩：

- JPEG
- PNG
- MP4
- ZIP
- 已压缩文档

### 4. 压缩安全

如果响应同时包含秘密数据和攻击者可控内容，压缩后的长度可能泄露信息。敏感场景应评估 BREACH 类侧信道：

- 不把秘密和可控输入放入同一压缩上下文
- 对高风险响应禁用压缩
- 使用随机化和 CSRF 防护
- 避免把秘密反射到页面

---

## 二十二、REST 与 HTTP API

### 1. 资源 URI

推荐表达资源，而不是动作：

```text
GET    /users/100
POST   /orders
PUT    /users/100/profile
DELETE /sessions/current
```

不是所有 API 都必须采用 REST；关键是语义一致、可维护并有清晰契约。

### 2. 状态码选择

```text
查询成功           → 200
创建成功           → 201 + Location
异步任务已接受     → 202
删除成功无正文     → 204
参数格式错误       → 400
未认证             → 401
无权限             → 403
资源不存在         → 404
版本冲突           → 409 / 412
校验不通过         → 422
请求过于频繁       → 429
服务器内部错误     → 500
```

### 3. 分页

```http
GET /users?limit=20&cursor=abc
```

响应应明确：

- 当前数据
- 下一页游标
- 是否还有更多数据
- 排序规则

游标分页通常比大偏移量分页更适合持续变化的大数据集。

### 4. 幂等键

创建订单、支付等接口可接受：

```http
Idempotency-Key: unique-request-id
```

服务器保存键与结果，重复请求返回同一业务结果，避免网络重试造成重复操作。

### 5. 乐观并发控制

查询：

```http
ETag: "version-7"
```

更新：

```http
If-Match: "version-7"
```

版本已变化时：

```http
HTTP/1.1 412 Precondition Failed
```

可以避免后写入者静默覆盖先前修改。

### 6. 错误响应

错误结构应稳定并可机器处理：

```json
{
  "code": "INVALID_EMAIL",
  "message": "email format is invalid",
  "request_id": "req-123"
}
```

不要向客户端暴露堆栈、数据库语句、密钥或内部路径。

---

## 二十三、实时 HTTP 技术

### 1. Long Polling

```text
客户端发起请求
服务器暂不响应
有事件或超时后返回
客户端立即发起下一次请求
```

兼容性好，但每次事件可能需要新请求。

### 2. Server-Sent Events

```http
Content-Type: text/event-stream
Cache-Control: no-cache
```

数据：

```text
event: update
data: {"id":100}

```

特点：

- 服务器到浏览器单向推送
- 基于普通 HTTP
- 浏览器自动重连
- 文本事件格式

### 3. WebSocket

HTTP/1.1 握手：

```http
GET /chat HTTP/1.1
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Key: ...
Sec-WebSocket-Version: 13
```

响应：

```http
HTTP/1.1 101 Switching Protocols
Upgrade: websocket
Connection: Upgrade
```

升级后使用 WebSocket 帧，不再是普通 HTTP 请求—响应消息。

### 4. 选择建议

| 场景 | 技术 |
| ---- | ---- |
| 普通请求响应 | HTTP API |
| 服务器单向事件 | SSE |
| 双向低延迟消息 | WebSocket |
| 低频、兼容旧系统 | Long Polling |
| 浏览器到服务器流式上传/双向 RPC | 评估 Fetch Stream、WebTransport、gRPC-Web 等 |

---

## 二十四、HTTP 安全

### 1. 基础措施

- 全站 HTTPS
- 正确验证证书
- 输入验证和输出编码
- 身份认证与逐资源授权
- 安全 Cookie
- CSRF 防护
- 限制请求体和 Header 大小
- 超时、限流和并发限制
- 隐藏详细错误信息
- 依赖和服务器及时更新

### 2. 常见安全 Header

| Header | 作用 |
| ------ | ---- |
| **Strict-Transport-Security** | 强制后续使用 HTTPS |
| **Content-Security-Policy** | 限制脚本、样式等资源来源 |
| **X-Content-Type-Options: nosniff** | 禁止 MIME 嗅探 |
| **Referrer-Policy** | 控制 Referer 信息 |
| **Permissions-Policy** | 限制浏览器功能 |
| **Cross-Origin-Opener-Policy** | 控制跨源窗口关系 |
| **Cross-Origin-Resource-Policy** | 控制资源被跨源加载 |
| **Cross-Origin-Embedder-Policy** | 控制嵌入跨源资源 |

点击劫持可优先使用 CSP `frame-ancestors`，旧系统也常使用 X-Frame-Options。

### 3. HSTS

```http
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

浏览器在有效期内自动把 HTTP 升级为 HTTPS。启用 `includeSubDomains` 或提交 Preload 前，应确认所有子域都支持 HTTPS，因为配置很难立即撤回。

### 4. CSRF

Cookie 会被浏览器自动携带，攻击网站可能诱导用户浏览器向目标站发送请求。

防护：

- SameSite Cookie
- CSRF Token
- 验证 Origin / Referer
- 修改操作不使用 GET
- 关键操作二次确认
- API 使用不自动携带的 Authorization Header

### 5. XSS

恶意输入被当作脚本执行。防护：

- 按 HTML、属性、JavaScript、URL 上下文正确输出编码
- 使用安全模板系统
- 避免危险 DOM API
- 部署严格 CSP
- Cookie 使用 HttpOnly

### 6. Host Header 攻击

应用使用 Host 生成重置密码链接或回调地址时，如果信任任意输入，可能生成攻击者域名。

防护：

- 配置允许的 Host 列表
- 使用固定外部基准 URL
- 代理覆盖并验证 Host
- 不直接信任 X-Forwarded-Host

### 7. HTTP Request Smuggling

前端代理和后端对消息边界理解不一致，可能把一个请求的一部分解释为下一个请求。

防护：

- 拒绝 Content-Length / Transfer-Encoding 冲突
- 规范化重复 Header
- 前后端使用一致、更新的协议栈
- HTTP/2/3 转 HTTP/1.1 时严格校验
- 限制异常请求并监控解析错误

### 8. SSRF

服务器根据用户输入请求 URL 时，攻击者可能访问内网或云元数据服务。

防护：

- 目标域名/地址允许列表
- 解析后检查最终 IP 和重定向目标
- 阻止私有、环回、链路本地和元数据地址
- 限制协议和端口
- 使用隔离的出站代理
- 防止 DNS Rebinding

---

## 二十五、curl 使用

### 1. 基本请求

```bash
curl https://example.com/
```

### 2. 查看详细过程

```bash
curl -v https://example.com/
```

可查看：

- DNS 和连接目标
- TLS 协商
- 请求 Header
- 响应 Header
- HTTP 版本

### 3. 只看响应头

```bash
curl -I https://example.com/
```

这会发送 HEAD，请注意服务端对 HEAD 的处理可能与 GET 不完全一致。

### 4. 指定方法和 JSON

```bash
curl -X POST https://api.example.com/users \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer token' \
  --data '{"name":"Alice"}'
```

使用 `--data` 时 curl 已会选择 POST，通常不需要额外写 `-X POST`。

### 5. 保存响应

```bash
curl -o file.zip https://example.com/file.zip
curl -O https://example.com/file.zip
```

### 6. 跟随重定向

```bash
curl -L https://example.com/old
```

### 7. 指定 HTTP 版本

```bash
curl --http1.1 https://example.com/
curl --http2 https://example.com/
curl --http3 https://example.com/
```

是否支持 HTTP/3 取决于 curl 的构建选项。

### 8. 输出性能指标

```bash
curl -o /dev/null -sS \
  -w 'dns=%{time_namelookup} connect=%{time_connect} tls=%{time_appconnect} ttfb=%{time_starttransfer} total=%{time_total}\n' \
  https://example.com/
```

### 9. 指定解析结果

```bash
curl --resolve example.com:443:192.0.2.10 https://example.com/
```

可绕过 DNS 指定 IP，同时保留 URL 域名、Host 和 TLS SNI，适合测试特定节点。

### 10. 忽略证书验证

```bash
curl -k https://example.com/
```

`-k` 只适合临时诊断。生产调用应修复证书链、域名或信任配置，不能长期关闭验证。

---

## 二十六、抓包与协议分析

### 1. 抓取 HTTP/1.1 明文

```bash
sudo tcpdump -i any -n 'tcp port 80'
```

Wireshark 过滤器：

```text
http
http.request
http.response
http.request.method == "POST"
http.response.code >= 400
```

### 2. HTTPS 抓包

HTTPS 内容已加密，普通抓包通常只能看到：

- IP 和端口
- TCP 或 QUIC
- TLS 握手部分信息
- 报文大小和时序

在受控调试环境中，可使用浏览器导出的 TLS Session Key 配合 Wireshark 解密自己有权分析的流量。

### 3. HTTP/2 过滤器

```text
http2
http2.type == 1
http2.streamid == 1
```

### 4. HTTP/3 / QUIC 过滤器

```text
quic
http3
udp.port == 443
```

### 5. 反向代理日志

建议记录：

- 时间
- 客户端地址（经过可信代理解析）
- Host
- Method
- Path（谨慎处理敏感 Query）
- Status
- 响应大小
- 总耗时
- 上游连接和响应时间
- Request ID / Trace ID
- HTTP 版本

不要记录明文密码、Authorization、Session Cookie 和敏感个人数据。

---

## 二十七、HTTP 性能

### 1. 请求总耗时

```text
总耗时 ≈ DNS
       + 建立连接
       + TLS 握手
       + 请求上传
       + 服务器排队和处理
       + 首字节等待
       + 响应下载
```

### 2. 常见指标

| 指标 | 含义 |
| ---- | ---- |
| DNS Time | 域名解析时间 |
| Connect Time | TCP/QUIC 建连时间 |
| TLS Time | TLS 握手时间 |
| TTFB | 从开始请求到首字节 |
| Download Time | 响应体下载时间 |
| Total Time | 完整请求耗时 |

### 3. 优化顺序

优先测量瓶颈，再选择措施：

- 使用持久连接和连接池
- 启用 HTTP/2 或 HTTP/3
- 使用 CDN
- 正确设置缓存
- 压缩文本资源
- 减少不必要的请求和响应数据
- 优化服务器处理和数据库查询
- 避免重定向链
- 合理设置超时

### 4. TTFB 高

可能原因：

- 上游服务慢
- 数据库查询慢
- 连接池耗尽
- 服务排队
- 跨区域调用
- 缓存未命中
- 代理重试

### 5. 下载慢

可能原因：

- 响应体过大
- 带宽不足
- 丢包和拥塞
- 未压缩文本
- 客户端接收慢
- CDN 未命中或节点异常

### 6. 不要盲目增加连接数

更多连接可能带来：

- TLS 和 TCP 开销
- 服务端文件描述符压力
- 拥塞竞争
- 连接池排队转移
- 下游过载

连接数应根据吞吐、延迟和下游容量测量调整。

---

## 二十八、HTTP 故障排查

### 1. 分层排查流程

```text
1. URL:Scheme、Host、Port、Path 是否正确
2. DNS:域名是否解析到预期地址
3. 网络:路由和端口是否可达
4. TCP/QUIC:连接能否建立
5. TLS:证书、SNI、协议和时间是否正确
6. HTTP:方法、Host、Header、Body 是否正确
7. 代理:CDN、负载均衡、网关转发是否正常
8. 应用:路由、认证、参数、数据库是否正常
9. 缓存:浏览器、代理、CDN 是否返回旧内容
```

### 2. 使用 curl 分解问题

```bash
curl -v https://example.com/path
curl --resolve example.com:443:192.0.2.10 -v https://example.com/path
curl --http1.1 -v https://example.com/path
curl --http2 -v https://example.com/path
```

可以区分：

- DNS 问题
- 特定节点问题
- TLS 问题
- HTTP 版本兼容问题

### 3. 400 Bad Request

检查：

- URL 和 Query 编码
- Host
- Header 格式和大小
- Content-Type
- JSON / 表单语法
- Content-Length
- 代理是否修改请求

### 4. 401 / 403

检查：

- Authorization 是否发送
- Token 是否过期
- Cookie Domain、Path、SameSite、Secure
- 用户角色和资源权限
- 代理是否移除认证 Header
- 客户端和服务器时间

### 5. 404

检查：

- Path 和大小写
- 路由前缀
- Host 是否命中正确虚拟主机
- 反向代理 rewrite 规则
- 部署版本
- CDN 是否缓存旧 404

### 6. 413 / 431

```text
413:请求体太大
431:请求 Header 太大
```

需要同时检查 CDN、负载均衡器、反向代理和应用的限制。不要只调大最内层应用配置。

### 7. 502

检查：

- 上游进程是否运行
- 代理连接的 IP/端口是否正确
- 上游是否立即断开或返回无效 HTTP
- TLS 回源配置和 SNI
- DNS 服务发现
- 上游日志

### 8. 503

检查：

- 服务是否主动维护或过载
- 是否没有健康上游
- 连接池、线程池、队列是否耗尽
- 限流和熔断策略
- Retry-After

### 9. 504

检查各阶段超时：

- 连接上游超时
- 等待响应头超时
- 响应读取超时
- 应用处理超时
- 数据库和下游 RPC 超时

代理超时应略大于应用内部超时，避免外层先断开而应用继续无效工作。

### 10. TLS 错误

常见原因：

- 证书过期
- 域名与 SAN 不匹配
- 缺少中间证书
- 客户端不信任 CA
- 系统时间错误
- TLS 版本或密码套件不兼容
- SNI 错误
- mTLS 缺少客户端证书

### 11. 内容不是最新版本

检查：

- Browser Cache
- Service Worker
- CDN Cache
- 反向代理缓存
- Cache-Control / Expires
- ETag / Last-Modified
- 缓存键和 Vary
- 是否访问了不同部署节点

### 12. 常见问题对照

| 现象 | 常见原因 | 重点检查 |
| ---- | -------- | -------- |
| 无法连接 | DNS、路由、端口、防火墙 | curl -v、ss、抓包 |
| 证书错误 | 过期、域名不匹配、链不完整 | SAN、证书链、时间 |
| 400 | 请求格式、Host、长度冲突 | 原始请求、代理日志 |
| 401 | 未认证或凭据无效 | Authorization、Cookie |
| 403 | 权限、WAF、策略拒绝 | 授权日志、WAF 规则 |
| 404 | 路由或虚拟主机错误 | Host、Path、rewrite |
| 429 | 限流 | Retry-After、请求速率 |
| 502 | 上游无效响应 | 代理和上游日志 |
| 503 | 无健康实例或过载 | 健康检查、资源池 |
| 504 | 上游超时 | 全链路耗时、超时层级 |
| 页面旧 | 多级缓存 | Cache-Control、CDN |
| 上传失败 | 大小限制、超时 | 413、代理限制、带宽 |
| HTTP/3 不可用 | UDP 443 被阻断 | Alt-Svc、QUIC 抓包 |

---

## 二十九、HTTP/2 与 HTTP/3 排障

### 1. 确认协商版本

```bash
curl -I -v --http2 https://example.com/
curl -I -v --http3 https://example.com/
```

浏览器开发者工具的 Protocol 列也可显示：

```text
http/1.1
h2
h3
```

### 2. HTTP/2 常见问题

- ALPN 未协商 h2
- TLS 终止设备不支持 HTTP/2
- 代理回源仍使用 HTTP/1.1
- 单个大响应占用流量控制窗口
- TCP 丢包影响所有 Stream
- Header 列表过大

### 3. HTTP/3 发现

客户端通常通过：

- HTTPS DNS 记录中的协议参数
- `Alt-Svc` 响应 Header
- 已缓存的替代服务信息

发现 HTTP/3：

```http
Alt-Svc: h3=":443"; ma=86400
```

### 4. HTTP/3 回退

如果 UDP 443 被网络阻断，客户端通常应回退到 HTTP/2 或 HTTP/1.1。若回退很慢，应检查：

- QUIC 建连超时
- 防火墙策略
- 客户端 Happy Eyeballs / 回退实现
- Alt-Svc 是否指向错误端口

---

## 三十、核心要点速记

- **HTTP = 应用层请求—响应协议**
- **HTTP 无状态，但可以复用底层连接**
- **URI 标识资源，URL 是常见 URI 形式**
- **Fragment `#...` 通常不会发送给服务器**
- **HTTP/1.1 消息：起始行 + Header + 空行 + 可选 Body**
- **Host 支持同一 IP 上的虚拟主机**
- **GET 获取，POST 提交，PUT 完整替换，PATCH 部分更新，DELETE 删除**
- **GET、HEAD、OPTIONS 是安全方法**
- **PUT、DELETE 是幂等方法，POST 通常不是**
- **2xx 成功，3xx 重定向，4xx 客户端错误，5xx 服务器错误**
- **201 = 已创建，204 = 成功但无响应体**
- **301/302 可能改变方法，307/308 保留方法和请求体**
- **401 = 需要认证，403 = 已识别但无权限**
- **502 = 坏网关，503 = 服务不可用，504 = 网关超时**
- **Content-Type 描述媒体类型，Content-Encoding 描述内容编码**
- **Content-Length 是消息体字节数**
- **HTTP/1.1 Chunked 用十六进制块长度传输未知大小消息体**
- **HTTP/2/3 不使用 `Transfer-Encoding: chunked`**
- **Cache-Control 的 no-cache 表示复用前验证，不等于不存储**
- **no-store 才表示不应存储**
- **ETag / If-None-Match 可实现缓存验证，未变化返回 304**
- **Vary 告诉共享缓存哪些请求 Header 影响响应表示**
- **Cookie 常用于 Session，应设置 Secure、HttpOnly、SameSite**
- **Authorization Bearer Token 必须通过 HTTPS 传输**
- **HTTP/1.1 默认持久连接**
- **HTTP/2 = 二进制分帧、多路复用、HPACK，运行在 TCP 上**
- **HTTP/3 = HTTP over QUIC，使用 UDP，内置 TLS 1.3**
- **HTTP/3 减少跨 Stream 的传输层队头阻塞并支持连接迁移**
- **HTTPS 提供加密、完整性和身份认证，但不能代替应用授权**
- **ALPN 用于协商 HTTP/1.1、HTTP/2 等应用协议**
- **CORS 是浏览器跨源读取策略，不是服务端认证授权**
- **Range + 206 用于断点续传和部分内容**
- **反向代理代表服务器，正向代理代表客户端**
- **只能信任受信代理清洗并写入的 Forwarded / X-Forwarded-* Header**
- **HSTS 强制 HTTPS，启用 includeSubDomains 前应确认所有子域兼容**
- **请求解析必须拒绝模糊长度，防止 Request Smuggling**
- **非幂等接口重试应使用 Idempotency-Key 或业务唯一 ID**
- **`curl -v` 查看连接、TLS 和 HTTP 过程**
- **`curl --resolve` 可测试指定 IP，同时保留 Host 和 SNI**
- **排障按 DNS → 网络 → TCP/QUIC → TLS → HTTP → 代理 → 应用 → 缓存分层进行**
