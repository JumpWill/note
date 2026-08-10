# CDN 完全参考

CDN (Content Delivery Network, 内容分发网络) 是由**分布在各地的边缘节点**组成的网络,通过把内容**缓存到离用户最近**的节点,加速访问、减轻源站压力、提供安全防护。本文覆盖原理、协议、配置、实战与各厂商对比。

## 一、基本概念

### 1. 什么是 CDN

```text
用户 (北京)
  ↓ DNS 解析 → 智能调度到最近的边缘节点 (北京边缘)
  ↓ 边缘命中 → 直接返回
  ↓ 边缘未命中 → 回源拉取 → 缓存后返回

用户 (上海)
  ↓ DNS 解析 → 调度到上海边缘
  ...
```

- **边缘节点 (Edge / POP)**:分布式在全球/全国的小型数据中心
- **源站 (Origin)**:真实服务的服务器
- **回源 (Origin Pull)**:边缘未命中时去源站拉取
- **命中 (Cache Hit)**:边缘有缓存,直接返回
- **命中率 (Hit Ratio)**:命中数 / 总请求数

### 2. 为什么需要 CDN

- **加速**:物理距离近,延迟低
- **节省带宽**:回源减少,源站带宽成本下降
- **抗流量**:边缘承担大流量,源站不被冲垮
- **高可用**:边缘多节点,任一节点故障可切
- **安全**:DDoS 缓解、WAF、CC 防护、Bot 管理
- **全球分发**:跨国/跨地区服务,边缘让各地用户都感觉"就近"

### 3. 适用场景

| 场景 | 适用度 | 说明 |
| --- | --- | --- |
| 静态资源 (图片/JS/CSS) | ⭐⭐⭐⭐⭐ | CDN 主战场 |
| 视频/大文件下载 | ⭐⭐⭐⭐⭐ | 节省回源流量 |
| 动态 API | ⭐⭐ | 部分 CDN 支持 (智能路由) |
| 直播/点播 | ⭐⭐⭐⭐ | HLS/FLV 分发 |
| 移动端 SDK/包 | ⭐⭐⭐⭐ | 大文件分发 |
| WebSocket | ⭐ | 不适合走 CDN |
| 强一致写 | ❌ | 走源站,不走 CDN |

## 二、CDN 关键组成

### 1. 调度系统

| 类型 | 说明 |
| --- | --- |
| **DNS 调度** | 权威 DNS 按地域/运营商返回不同 IP (常见) |
| **HTTP 302 调度** | DNS 解析到统一 IP,边缘返回 302 到最佳节点 (精准) |
| **Anycast** | 同一 IP 多个节点广播,BGP 选最近 (高级) |
| **EDNS-Client-Subnet** | DNS 携带客户端子网,精准定位 |

```text
用户 (北京联通) → DNS 解析 → 北京联通边缘 IP
用户 (上海电信) → DNS 解析 → 上海电信边缘 IP
```

### 2. 边缘节点 (Edge)

- **L1 节点 (省级)**:覆盖广,容量大
- **L2 节点 (地市级)**:更靠近用户,容量较小
- **L3 节点 (边缘 POP)**:机房级,极靠近用户 (5G / 边缘计算)
- 调度按"地理位置 + 运营商 + 实时负载"综合选择

### 3. 缓存系统

- **正向缓存 (Pull)**:用户请求触发,边缘拉源
- **预热 (Prefetch)**:主动把内容推到边缘
- **多级缓存**:Edge L1 → L2 → L3 → 源站
- **内存缓存** (Hot Key) + **SSD 缓存** (冷数据)

### 4. 源站

- **主源 / 备源**:主备切换
- **回源 Host**:边缘访问源站时用的域名
- **回源协议**:HTTP / HTTPS / 跟随客户端
- **回源端口**:80 / 443 / 自定义

## 三、CDN 加速原理

### 1. 请求流程

```text
用户 → Local DNS → 权威 DNS (智能解析)
   ↓
   返回最优边缘 IP
   ↓
用户 → 边缘节点
   ├── 命中:直接返回
   └── 未命中:边缘 → 源站拉取 → 缓存 → 返回
```

### 2. 命中规则

- **按 URL 完整匹配**:最常见
- **按目录前缀**:`/static/**` 走 CDN
- **按文件后缀**:`.js .css .png`
- **按 Query / Header**:高级配置

### 3. 缓存策略

| 字段 | 含义 |
| --- | --- |
| `Cache-Control: max-age=N` | 浏览器和边缘缓存 N 秒 |
| `Cache-Control: no-cache` | 强制回源校验 |
| `Cache-Control: no-store` | 不缓存 |
| `Cache-Control: public/private` | 是否允许中间缓存 |
| `Expires` | 旧式过期时间 (HTTP/1.0) |
| `ETag` / `Last-Modified` | 协商缓存 |
| `Vary` | 按 Header 区分缓存 |

## 四、CDN 协议与端口

### 1. 客户端协议

| 协议 | 端口 | 特点 |
| --- | --- | --- |
| **HTTP/1.1** | 80 / 443 | 主流,连接复用有限 |
| **HTTP/2** | 443 | 多路复用,头部压缩 |
| **HTTP/3 (QUIC)** | 443/UDP | 基于 UDP,0-RTT,抗丢包 |
| **HTTPS (TLS 1.2/1.3)** | 443 | 主流,加密 |
| **WebSocket** | 80/443 | 长连接,CDN 支持有限 |

### 2. 回源协议

| 回源方式 | 适用 | 优点 | 缺点 |
| --- | --- | --- | --- |
| **HTTP 回源** | 内部可信网络 | 简单 | 明文,需注意安全 |
| **HTTPS 回源** | 通用 | 加密 | 回源延迟略增 |
| **协议跟随** | 智能 | 用户用啥就用啥 | 配置复杂 |
| **私有协议** | 自定义源 | 性能好 | 仅特定厂商 |

### 3. 端口

| 端口 | 用途 |
| --- | --- |
| 80 | HTTP |
| 443 | HTTPS |
| 8080 / 8443 | 自定义 HTTP / HTTPS |
| UDP 443 | HTTP/3 (QUIC) |

## 五、HTTP 缓存控制

### 1. Cache-Control 指令

```text
Cache-Control: max-age=3600         # 缓存 1 小时
Cache-Control: max-age=3600, public  # 共享缓存
Cache-Control: no-cache             # 必须回源校验
Cache-Control: no-store             # 不缓存
Cache-Control: s-maxage=3600        # 边缘缓存 (覆盖 max-age)
Cache-Control: must-revalidate      # 过期后必须校验
Cache-Control: stale-while-revalidate=60  # 过期后 60s 内先用旧
Cache-Control: immutable            # 内容永不变
```

### 2. 协商缓存

```text
请求: If-None-Match: "abc123"
       If-Modified-Since: Wed, 21 Oct 2024 07:28:00 GMT
源站: 304 Not Modified (用缓存)
       200 OK + 新内容 (内容变了)
```

### 3. Vary 头

```text
Vary: Accept-Encoding      # 按编码缓存 (gzip / br)
Vary: User-Agent           # 按 UA 缓存 (移动 / PC)
Vary: Origin               # 按来源缓存 (CORS)
```

> Vary 维度越多,缓存命中率越低,谨慎使用。

## 六、CDN 安全

### 1. HTTPS / TLS

- **证书管理**:CDN 厂商托管 / 自有证书上传
- **SNI**:多证书共享 IP
- **TLS 版本**:禁用 1.0 / 1.1,启用 1.2 / 1.3
- **加密套件**:禁用弱算法 (RC4 / 3DES)
- **OCSP Stapling**:减少握手延迟
- **HSTS**:强制 HTTPS

### 2. 防 DDoS

- **CC 防护**:基于行为分析的限速
- **DDoS 清洗**:大流量攻击牵引至清洗中心
- **IP 黑白名单**:精细化访问控制
- **UA / Referer 限制**:防爬虫
- **挑战验证**:JS 挑战 / 验证码 / 5 秒盾

### 3. WAF (Web Application Firewall)

- **SQL 注入 / XSS 防护**
- **WebShell 上传拦截**
- **命令执行防护**
- **敏感信息泄露防护**
- **自定义规则**

### 4. Referer 防盗链

```nginx
# Nginx 防盗链
location ~* \.(jpg|jpeg|png|gif)$ {
    valid_referers none blocked server_names *.example.com;
    if ($invalid_referer) {
        return 403;
    }
}
```

### 5. URL 鉴权

- **签名 URL**:过期时间 + 签名 (类似 OSS / S3)
- **Token 鉴权**:CDN 边缘验证 Token
- **IP 鉴权**:只允许特定 IP 段
- **时间戳 + 路径签名**:防外链 / 防盗链

### 6. 防盗链高级

- **回源鉴权**:每次回源时源站验证
- **边缘 Token**:边缘解析 JWT / 自定义 Token
- **Referer 链 + UA + IP**:组合策略

## 七、CDN 性能优化

### 1. 静态资源优化

- **合并请求**:JS / CSS 合并
- **雪碧图 (Sprite)**:多图合成
- **字体子集化**:Web Font 按需加载
- **WebP / AVIF**:新图片格式
- **图片懒加载**:首屏外延迟加载
- **资源预加载**:`<link rel="preload">`
- **HTTP/2 Server Push**(已弃用,改用 Early Hints 103)
- **HTTP/3 (QUIC)**:0-RTT,改善弱网

### 2. 缓存优化

- **合理 max-age**:静态资源长期缓存 (1 年)
- **文件指纹**:内容变更时换 URL (`app.a1b2c3.js`)
- **预热**:大促前主动推送
- **分层缓存**:边缘 → 中间层 → 源站
- **Range 回源**:断点续传节省回源流量
- **合并回源**:批量未命中合并请求

### 3. 网络优化

- **Brotli 压缩**:比 gzip 更高压缩比
- **智能压缩**:按文件类型 / 客户端支持选算法
- **连接复用**:HTTP/2 多路复用
- **TCP 优化**:BBR / 拥塞控制
- **边缘计算 (Edge Computing)**:边缘跑函数,延迟 < 5ms

### 4. 边缘计算 (Edge Functions)

- **Cloudflare Workers**
- **AWS Lambda@Edge / CloudFront Functions**
- **阿里云边缘函数 / ESA**
- **Cloudflare Workers KV / D1** (边缘 KV / 边缘数据库)
- **Vercel Edge Functions**
- **Deno Deploy**

> 适合:地理位置敏感、A/B 测试、个性化重写、防盗链、轻量鉴权。

## 八、回源与源站

### 1. 回源策略

| 策略 | 行为 |
| --- | --- |
| **主备回源** | 主源故障切备源 |
| **多源负载均衡** | 多源按权重轮询 |
| **回源跟随** | 用户用啥协议就用啥 |
| **Range 回源** | 客户端 Range 请求回源也带 Range |
| **合并回源** | 同一资源多个未命中合并为一次回源 |
| **回源重试** | 失败后重试其他源 |

### 2. 源站保护

- **回源鉴权**:边缘 → 源站带 Token
- **专线 / VPC Peering**:云上内网回源
- **回源 IP 白名单**:源站只允许 CDN IP 段
- **回源限速**:防止突发回源冲垮源站
- **回源超时**:超时切备源

### 3. 预热与刷新

- **URL 预热**:主动推送热点资源
- **目录预热**:整目录推送
- **URL 刷新**:主动清除指定 URL
- **目录刷新**:清除整目录
- **全量刷新**:慎用,所有缓存清除

## 九、动态加速 (DCDN)

### 1. 什么是动态加速

传统 CDN 缓存静态资源,**动态内容不缓存**。DCDN (Dynamic CDN) 通过:
- **智能路由**:BGP 选最优路径
- **传输优化**:协议优化、连接复用
- **回源加速**:专线、节点优选
- **边缘计算**:边缘跑逻辑

让动态请求也享受 CDN 加速。

### 2. 适用

- API 接口
- 表单提交
- 登录认证
- 实时数据查询
- 跨境电商 (跨地域动态请求)

### 3. 局限

- 仍然每次回源,源站压力未减
- 不减少回源带宽
- 延迟主要在回源路径,优化空间有限

## 十、CDN 监控与日志

### 1. 核心指标

| 指标 | 说明 |
| --- | --- |
| **命中率 (Hit Ratio)** | 缓存命中比例,通常 90%+ |
| **回源率 (Origin Pull Ratio)** | 1 - 命中率 |
| **响应时间 (TTFB / TTLB)** | 首字节 / 末字节时间 |
| **下载速度** | 字节/秒 |
| **错误率** | 5xx / 4xx 比例 |
| **并发数** | 同时在线请求数 |
| **带宽** | 边缘出口带宽 (Mbps) |
| **请求数** | QPS / TPS |

### 2. 监控维度

- 域名 / 路径 / 资源类型
- 地域 / 国家 / 运营商
- 客户端 IP / UA
- 缓存状态 (HIT / MISS / EXPIRED)
- 状态码分布

### 3. 日志类型

- **访问日志**:每条请求详情 (URL, IP, status, size, time, ua, referer)
- **回源日志**:回源请求记录
- **错误日志**:异常请求
- **操作日志**:管理操作审计

### 4. 日志分析

- 实时投递到 Kafka / SLS / CLS
- 离线分析到 OSS / S3 + Spark
- 看板:命中率趋势、TOP URL、TOP IP、TOP 错误

## 十一、CDN 厂商对比

| 厂商 | 全球节点 | 国内节点 | 特点 |
| --- | --- | --- | --- |
| **Cloudflare** | 300+ | 与京东合作 | 免费版强,Workers 优秀,生态丰富 |
| **Akamai** | 4000+ | 有 | 老牌,企业级,媒体行业主导 |
| **Fastly** | 300+ | 无 | 实时清除,边缘计算强 (Compute@Edge) |
| **AWS CloudFront** | 600+ | 与光环新网合作 | 与 AWS 生态深度集成 |
| **Azure CDN** | 200+ | 与世纪互联合作 | Azure 生态 |
| **Google Cloud CDN** | 200+ | 无 | GCP 生态 |
| **阿里云 CDN** | 2800+ | 多 | 国内主流,DCDN 强 |
| **腾讯云 CDN** | 2800+ | 多 | 国内主流,游戏/视频强 |
| **华为云 CDN** | 2800+ | 多 | 政企市场 |
| **七牛云** | 2500+ | 多 | 国内中小客户 |
| **又拍云** | 1000+ | 多 | 国内中小客户 |
| **网宿科技** | 2500+ | 多 | 老牌 CDN |
| **白山云** | 1000+ | 多 | 边缘云 |

## 十二、选型速查

| 场景 | 建议 |
| --- | --- |
| 国内静态资源加速 | 阿里云 / 腾讯云 / 华为云 |
| 全球分发 | Cloudflare / Akamai / Fastly |
| AWS 生态 | CloudFront |
| 视频/直播 | 阿里云 / 腾讯云 / 七牛 / Akamai |
| 个人 / 小项目 | Cloudflare 免费版 |
| 边缘函数需求 | Cloudflare Workers / Vercel / Fastly Compute |
| 政企合规 | 华为云 / 网宿 / 自建 |
| 海外为主 | Cloudflare / CloudFront / Fastly |
| 游戏分发 | 腾讯云 / 网宿 / Akamai |

## 十三、核心配置示例

### 1. Nginx 源站防盗链 + 缓存

```nginx
# 静态资源
location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff2?)$ {
    expires 365d;
    add_header Cache-Control "public, max-age=31536000, immutable";
    add_header X-Content-Type-Options nosniff;
    
    valid_referers none blocked server_names *.example.com;
    if ($invalid_referer) {
        return 403;
    }
}

# HTML 不缓存
location ~* \.html$ {
    add_header Cache-Control "no-cache, no-store, must-revalidate";
    add_header Pragma "no-cache";
    add_header Expires "0";
}
```

### 2. 阿里云 CDN 加速域名配置

```json
{
  "Domain": "cdn.example.com",
  "CdnType": "web",
  "Sources": [
    {
      "Type": "oss",
      "Content": "my-bucket.oss-cn-hangzhou.aliyuncs.com",
      "Priority": 20
    },
    {
      "Type": "domain",
      "Content": "origin.example.com",
      "Priority": 10
    }
  ],
  "CacheConfig": {
    "TTL": 86400,
    "CacheKey": {
      "QueryString": {
        "Action": "ignore",
        "Value": ""
      }
    }
  },
  "HttpsOption": {
    "CertType": "cas",
    "CertId": 12345
  }
}
```

### 3. Cloudflare Workers 边缘重写

```javascript
export default {
  async fetch(request) {
    const url = new URL(request.url);
    
    // A/B 测试
    if (url.pathname.startsWith("/api/")) {
      const bucket = Math.random() < 0.5 ? "A" : "B";
      url.hostname = `api-${bucket}.example.com`;
    }
    
    // 安全头
    const response = await fetch(url, request);
    const newHeaders = new Headers(response.headers);
    newHeaders.set("X-Content-Type-Options", "nosniff");
    newHeaders.set("X-Frame-Options", "DENY");
    newHeaders.set("Referrer-Policy", "strict-origin-when-cross-origin");
    
    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: newHeaders,
    });
  },
};
```

### 4. Cloudflare 缓存规则 (Page Rules / Cache Rules)

```text
URL: example.com/static/*
Cache eligibility: Cacheable
Edge TTL: 1 month
Browser TTL: 1 year
Cache key: Include query string (sorted)
```

## 十四、CDN 与源站集成

### 1. 回源 Host

- 用户访问 `cdn.example.com`
- 边缘 → 源站 IP 时带的 Host 是 `origin.example.com` (回源 Host)
- 源站 nginx `server_name` 必须匹配

### 2. 多源站策略

```text
主源: origin.example.com
备源: backup.example.com
回源协议: HTTPS
回源端口: 443
回源 Host: origin-internal.example.com
```

### 3. CDN 与对象存储

- OSS / S3 自带 CDN 加速
- 直接用 OSS Bucket 作源,免运维
- 静态网站托管 + CDN 加速

## 十五、跨地区 / 跨域

### 1. 跨域 (CORS)

```nginx
# 源站 CORS 头
add_header Access-Control-Allow-Origin "https://www.example.com" always;
add_header Access-Control-Allow-Methods "GET, POST, OPTIONS" always;
add_header Access-Control-Allow-Headers "Content-Type, Authorization" always;
add_header Access-Control-Max-Age 86400;
```

> CDN 边缘默认透传 CORS 头,源站设置即可。

### 2. 多 CDN 策略

- **主备 CDN**:主 CDN 故障切备 CDN (DNS 切换)
- **负载均衡**:按地域/内容类型分 CDN
- **多 CDN 监控**:实时比较,挑最优

### 3. 跨地区 / 跨国

- **边缘节点分布**:不同 CDN 全球覆盖不同
- **跨境加速**:专线 / 国际加速
- **合规**:数据主权 (GDPR / 数据本地化)

## 十六、CDN 成本优化

### 1. 计费方式

| 计费项 | 单位 | 优化方向 |
| --- | --- | --- |
| **流量** | GB | 提升命中率,启用压缩 |
| **带宽** | Mbps | 削峰填谷,预热 |
| **请求数** | 万次 | 减少无效请求,合并 |
| **HTTPS 请求** | 万次 | 单独计费,按需 |
| **增值服务** | 每月 | WAF、实时日志 |

### 2. 优化手段

- **提升命中率** 到 95%+,大幅降流量
- **图片优化**:WebP / AVIF / 压缩
- **Brotli 压缩**:比 gzip 多压 15~20%
- **Range 请求**:断点续传节省回源
- **合并请求**:JS / CSS sprite
- **大文件分片**:视频 HLS / DASH
- **回源限速**:防突发
- **避开高峰**:预热错峰

### 3. 选型权衡

- **免费版** (Cloudflare) → 适合个人/小流量
- **按量付费** → 适合波动业务
- **包年包月 / 流量包** → 适合稳定大流量
- **企业合约** → 超大规模可议价

## 十七、CDN 安全实战

### 1. HTTPS 完整配置

```nginx
server {
    listen 443 ssl http2;
    server_name cdn.example.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;
    ssl_session_tickets off;
    
    # HSTS
    add_header Strict-Transport-Security "max-age=63072000" always;
    
    location / {
        root /var/www/html;
    }
}
```

### 2. 限流与防刷

```nginx
# Nginx 限流
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

location /api/ {
    limit_req zone=api burst=20 nodelay;
    proxy_pass http://backend;
}
```

### 3. 抗 CC 攻击

- **JavaScript Challenge**:浏览器验证
- **CAPTCHA**:验证码
- **5 秒盾**:Cloudflare Under Attack Mode
- **行为分析**:异常流量识别
- **IP 信誉库**:黑名单

## 十八、CDN 故障排查

### 1. 常见问题

| 问题 | 原因 | 排查 |
| --- | --- | --- |
| 访问 404 | 回源失败 / 路径错 | 检查源站、缓存配置 |
| 命中率低 | 缓存策略过短 / 变化大 | 调整 max-age,加指纹 |
| 跨域错误 | 源站 CORS 头缺失 | 源站加 CORS 头 |
| HTTPS 不通 | 证书 / SNI / 协议 | 检查证书链、TLS 版本 |
| 访问慢 | 节点选择错 / 回源慢 | DNS 调度、回源网络 |
| 内容不更新 | 缓存未刷新 | 主动刷新 / 设置短 TTL |
| 源站压力大 | 命中率低 / 攻击 | 提升命中率,加 WAF |

### 2. 排查工具

- **CDN 控制台**:实时监控、日志
- **`curl -I`**:查看响应头 (X-Cache, Age, X-Served-By)
- **`dig` / `nslookup`**:检查 DNS 解析
- **`traceroute`**:网络路径
- **CDN 厂商工单**:深度排查

```bash
# 查看 CDN 缓存状态
curl -I https://cdn.example.com/static/app.js
```

```text
HTTP/2 200
date: Wed, 21 Oct 2024 07:28:00 GMT
content-type: application/javascript
content-length: 12345
cache-control: public, max-age=31536000, immutable
cf-cache-status: HIT         # 命中
age: 86400                    # 缓存了 1 天
server: cloudflare
x-cache: HIT from cdn-xxx
```

## 十九、CDN 新趋势

### 1. 边缘计算 (Edge Computing)

- **Cloudflare Workers / D1 / R2**
- **Fastly Compute@Edge / Compute**
- **AWS Lambda@Edge**
- **Deno Deploy / Vercel Edge**
- 边缘 AI 推理,边缘 KV,边缘数据库

### 2. QUIC / HTTP/3

- 基于 UDP,0-RTT
- 抗丢包 / 弱网表现好
- Cloudflare / CloudFront 已全面支持
- 国内大厂跟进中

### 3. AI 与 CDN

- **边缘 AI 推理**:图像识别 / 内容审核
- **智能预热**:预测热点提前推送
- **A/B 测试**:边缘分流
- **个性化**:基于用户特征的边缘定制

### 4. 零信任安全 (Zero Trust)

- **Cloudflare Access / Gateway**
- **ZTNA**:不暴露源站,边缘代理一切
- **mTLS**:双向认证

### 5. 多媒体增强

- **HLS / DASH 自适应码率**
- **低延迟直播 (LL-HLS / WebRTC)**
- **图像自适应**:按设备/网络自动转码

## 二十、要点速记

- **核心目的**:加速 + 节省带宽 + 抗攻击
- **工作原理**:DNS 智能调度 + 边缘缓存 + 回源
- **命中率**:静态资源 95%+ 才算合格
- **缓存策略**:静态长缓存 (1年) + 指纹 URL + HTML 不缓存
- **协议**:HTTP/2 主流,HTTP/3 演进中,HTTPS 必备
- **压缩**:Brotli > gzip,文本类多压 15~20%
- **HTTPS**:证书 CDN 托管,启用 TLS 1.3,加 HSTS
- **安全**:WAF + DDoS 清洗 + 防盗链 + URL 鉴权
- **动态加速**:智能路由 + 协议优化,仍每次回源
- **边缘计算**:Cloudflare Workers / Lambda@Edge,延迟 < 5ms
- **监控**:命中率 / TTFB / 错误率 / 带宽,实时告警
- **回源**:主备源 + 协议跟随 + IP 白名单
- **成本优化**:提升命中率 + 压缩 + 大文件分片 + 包年优惠
- **多 CDN**:主备 / 负载均衡,跨厂商监控
- **故障排查**:`curl -I` 看缓存头,DNS 看解析,日志查命中
- **新趋势**:HTTP/3 / 边缘计算 / 零信任 / AI 边缘推理
- **关键头部**:`Cache-Control`、`ETag`、`Vary`、`X-Cache`
- **选型**:国内阿里/腾讯/华为,全球 Cloudflare/Akamai,边缘选 Cloudflare
- **不要把** 强一致写 / WebSocket / 实时个性化 寄希望于 CDN
- **源站保护** 永远比 CDN 加速更重要
