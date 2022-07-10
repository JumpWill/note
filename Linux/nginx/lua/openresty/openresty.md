## openresty
简介：自己搜
简单来说，可以认为是在网关层进行编程。

## luajit
openresty默认使用了luajit。
luajit是一个lua的解释器，相较于官方的解释器更快。
但是luajit仅仅支持一些lua的函数，而不是全部，如果遇到不支持的函数，
那么就会使用lua自己的解释器，所以要避免使用luajit不支持的函数。

## openresty运行机制
nginx中一个master进程，会有多分work的进程，work进程会去处理具体的http请求。
openresty也一样。

### openresty阶段解读
openresty不同的阶段：https://www.cnblogs.com/fly-kaka/p/11102849.html
openresty各个阶段执行的指令解释及其执行顺序:

| 阶段                   | 解释                                                         |
| ---------------------- | ------------------------------------------------------------ |
| init_by_lua            | 初始化 nginx 和预加载 lua(nginx 启动和 reload 时执行)；      |
| init_worker_by_lua     | 每个工作进程(worker_processes)被创建时执行，用于启动一些定时任务，比如心跳检查，后端服务的健康检查，定时拉取服务器配置等； |
| ssl_certificate_by_lua | 对 https 请求的处理，即将启动下游 SSL（https）连接的 SSL 握手时执行，用例：按照每个请求设置 SSL 证书链和相应的私钥，按照 SSL 协议有选择的拒绝请求等； |
| set_by_lua             | 设置 nginx 变量；                                            |
| rewrite_by_lua         | 重写请求（从原生 nginx 的 rewrite 阶段进入），执行内部 URL 重写或者外部重定向，典型的如伪静态化的 URL 重写； |
| access_by_lua          | 处理请求（和 rewrite_by_lua 可以实现相同的功能，从原生 nginx 的 access阶段进入）； |
| content_by_lua         | 执行业务逻辑并产生响应，类似于 jsp 中的 servlet；            |
| balancer_by_lua        | 负载均衡；                                                   |
| header_filter_by_lua   | 处理响应头                                                   |
| body_filter_by_lua     | 处理响应体                                                   |
| log_by_lua             | 记录访问日志                                                 |

上诉的11个阶段的可以使用以下几种插入lua脚本的方式
```lua
-- 1
log_by_lua:lua code
-- 2
log_by_lua_block {  lua code}
-- 3 推荐使用
log_by_lua_file: lua_file_path
```
ps:
在http处理过程中没有preread_by_lua既是preread阶段只能由openresty读取请求头的信息。

### openresty缓存
参考：https://www.w3cschool.cn/openresty1/openresty-缓存.html
### 定时任务
openresty中含有定时任务
# TODO



## openresty常用函数

### 系统信息

### 日志

### 时间与日期

### 数据编码

### sleep

### 数据编码

### 正则表达式


参考：https://www.w3cschool.cn/openresty1