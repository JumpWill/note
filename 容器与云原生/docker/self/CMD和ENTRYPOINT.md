# CMD 和 ENTRYPOINT

## 是什么

Dockerfile 里两个看着很像、实际完全不同的指令：

| 指令 | 作用 | 是否可被 `docker run` 覆盖 |
| --- | --- | --- |
| **CMD** | 容器**默认**要执行的命令 | ✅ 可被 `run <image> <command>` 整体替换 |
| **ENTRYPOINT** | 容器**入口**，可执行文件 | ⚠️ 只有 `--entrypoint` 能改 |

两者**同时存在时**，CMD 的内容会作为参数传给 ENTRYPOINT。

```text
                Dockerfile                  docker run 时
                ──────────                  ────────────

没有 ENTRYPOINT:                            CMD 可被覆盖
  CMD ["nginx"]                              docker run img ls
                                             → 跑 ls，不跑 nginx

没有 CMD 但有 ENTRYPOINT:                    ENTRYPOINT 不动
  ENTRYPOINT ["nginx"]                       docker run img -g "daemon off;"
                                             → 跑 nginx -g "daemon off;"

两个都有:                                    覆盖 CMD 部分
  ENTRYPOINT ["nginx"]                       docker run img -t
  CMD ["-g", "daemon off;"]                  → 跑 nginx -t
```

## 两种写法：shell vs exec

```dockerfile
# Shell 形式（字符串）：Docker 自动在外面包 /bin/sh -c
CMD nginx -g "daemon off;"
ENTRYPOINT nginx -g "daemon off;"

# Exec 形式（JSON 数组）：原样执行，不走 shell
CMD ["nginx", "-g", "daemon off;"]
ENTRYPOINT ["nginx", "-g", "daemon off;"]
```

| 写法 | 是否走 `/bin/sh -c` | 能否处理环境变量/通配符 | 信号处理 | 推荐 |
| --- | --- | --- | --- | --- |
| **shell 形式** | ✅ 包了一层 | ✅ 变量展开、`$HOME`、`*.log` | ❌ shell 会吃掉 SIGTERM | ❌ 不推荐 |
| **exec 形式** | ❌ 直接 exec | ❌ 不展开，需用 shell 技巧 | ✅ 信号直达 PID 1 | ✅ 强烈推荐 |

```text
shell 形式的实际执行（容器里看到的进程树）：
   PID 1: /bin/sh -c "nginx -g 'daemon off;'"
            └── PID N: nginx            ← 收不到 SIGTERM

exec 形式的实际执行：
   PID 1: nginx -g daemon off;         ← PID 1 直接是 nginx
   ↑ 这才能正常接收 docker stop 发来的 SIGTERM
```

PS:
**生产镜像一律用 exec 形式。** shell 形式会让 PID 1 变成 `/bin/sh`，容器收到 `docker stop` 时 `SIGTERM` 会被 shell 吃掉，nginx 不会优雅退出，最后只能等 10 秒后 `SIGKILL` 强杀，丢数据。

## CMD 详解

### 三个有效形式

```dockerfile
# 1. exec 形式（推荐）
CMD ["nginx", "-g", "daemon off;"]

# 2. shell 形式
CMD nginx -g "daemon off;"

# 3. 给 ENTRYPOINT 传默认参数（最常见）
ENTRYPOINT ["nginx"]
CMD ["-g", "daemon off;"]
```

### 覆盖规则

```shell
# 完整替换 CMD
docker run <image> <新命令>     # CMD 整个被替换
docker run <image>              # 用 Dockerfile 里的 CMD
```

PS:

- 同一个 Dockerfile 里只能有**一个** `CMD`，多个只有**最后一个**生效
- `docker run --entrypoint` 也能改 ENTRYPOINT

## ENTRYPOINT 详解

```dockerfile
# exec 形式（推荐）
ENTRYPOINT ["nginx", "-g", "daemon off;"]

# shell 形式（基本不推荐，等同 CMD shell 形式）
ENTRYPOINT nginx -g "daemon off;"
```

```shell
# 覆盖 ENTRYPOINT
docker run --entrypoint="" <image> <新命令>
# 或者
docker run --entrypoint=/bin/sh <image>
```

### 典型用法：脚本包装

```dockerfile
COPY entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh
ENTRYPOINT ["entrypoint.sh"]
CMD ["default-arg1", "default-arg2"]
```

```bash
# entrypoint.sh
#!/bin/bash
set -e
# 等数据库起来
until pg_isready -h db; do sleep 1; done
# 处理配置
envsubst < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf
# 跑主程序
exec "$@"   # 把 CMD 传过来的参数交给真正的主进程
```

PS:
脚本里 **`exec "$@"`** 是关键——把脚本进程"替换"成主进程，让主进程变成 PID 1，信号才收得到。

## 二者关系：默认参数模式

这是最常见也最推荐的形式：

```dockerfile
ENTRYPOINT ["python", "app.py"]
CMD ["--port", "8080"]
```

```text
docker run myapp
   → 实际执行: python app.py --port 8080

docker run myapp --port 9090
   → 实际执行: python app.py --port 9090   ← CMD 被覆盖
```

> 镜像对外暴露一个**"可执行程序"**的接口，CMD 是默认参数，用户传参就是"调用"。

### 完整覆盖 ENTRYPOINT

```shell
docker run --entrypoint=/bin/sh myapp -c "ps aux"
# 完全替换 ENTRYPOINT（注意要传完整可执行文件路径）
```

## 实战模式

### 1. 官方 nginx 镜像

```dockerfile
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
```

`/docker-entrypoint.sh` 负责：生成配置 → 软链默认配置 → 检查权限 → exec CMD 传过来的 nginx。

### 2. 跑数据库

```dockerfile
COPY entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh
ENTRYPOINT ["entrypoint.sh"]
CMD ["postgres"]
```

### 3. 单可执行程序

```dockerfile
COPY myapp /usr/local/bin/
RUN chmod +x /usr/local/bin/myapp
ENTRYPOINT ["myapp"]
CMD ["--help"]   # 默认行为
```

```shell
docker run myapp                     # myapp --help
docker run myapp --version           # myapp --version
docker run myapp serve --port 80     # myapp serve --port 80
```

### 4. 一行启动多个进程（不推荐）

```dockerfile
CMD sh -c "nginx && node server.js"
```

> **永远不要这么写**。容器 = 单进程，多进程用 K8s Pod 多容器 / supervisord。shell 形式还会带来前面说的信号问题。

## 信号处理：PID 1 问题

容器内 **PID 1 的进程不响应默认信号**——因为 PID 1 只能被 init 处理，不会被 init 默认转发：

```text
docker stop 发 SIGTERM → PID 1 收不收？
   shell 形式 CMD  → PID 1 是 /bin/sh  → 不转发，nginx 收不到
   exec 形式 CMD   → PID 1 是 nginx    → 正常收，优雅退出
   exec 形式 ENTRYPOINT (脚本) → 脚本里没 exec "$@" → 脚本收 SIGTERM
                                → 加上 exec "$@"    → nginx 收
```

### 三个解决套路

```dockerfile
# 1. exec 形式 + exec "$@" 转发（最干净）
ENTRYPOINT ["entrypoint.sh"]

# 2. 用 tini / dumb-init 当 PID 1
RUN apk add --no-cache tini
ENTRYPOINT ["/sbin/tini", "--"]
CMD ["nginx", "-g", "daemon off;"]

# 3. CMD 直接 exec 链
CMD ["sh", "-c", "exec nginx -g 'daemon off;'"]
```

```text
推荐顺序：1 > 2 > 3
1 最干净；2 万能；3 丑但能跑
```

PS:
**K8s 场景特别注意**：K8s `terminationGracePeriodSeconds` 默认 30s，给 `docker stop` 一次 10s 不够的话，改 K8s 配置。前提是你的容器能正确收 SIGTERM。

## 与 RUN 的区别

```dockerfile
RUN apt-get install -y nginx        # 镜像**构建时**执行，结果写入镜像层
CMD ["nginx"]                       # 镜像**运行时**执行，不写入层
ENTRYPOINT ["nginx"]                # 镜像**运行时**执行
EXPOSE 80                           # 纯元数据，告知 Docker 这个容器用 80 端口
```

## 最佳实践

| 实践 | 为什么 |
| --- | --- |
| 一律 exec 形式 | 解决 PID 1 信号问题 |
| ENTRYPOINT 用可执行文件，CMD 给默认参数 | 镜像对外像 CLI 工具 |
| 复杂启动逻辑用 ENTRYPOINT 脚本 + `exec "$@"` | 比 shell 形式干净 |
| 脚本里用 `set -e` | 出错立即退出 |
| 数据库等需要初始化用 ENTRYPOINT 脚本 | 比 CMD 单行塞不进去 |
| 调试时临时换 shell | `docker run --entrypoint=/bin/sh -it <image>` |
| 别用 `CMD service nginx start` | 启动服务不要用 init.d 那套 |

## 常见坑

### 用了 shell 形式，docker stop 要等 10s

```shell
time docker stop myapp
# 10.0s 之后才退出
```

```dockerfile
# 错的
CMD service nginx start
CMD nginx -g "daemon off;"   # 等价于 /bin/sh -c "nginx ..."

# 对的
CMD ["nginx", "-g", "daemon off;"]
```

### JSON 数组里多个单词不引号会报 build 错

```dockerfile
# 错：会被当成 shell 形式
CMD [nginx, -g, "daemon off;"]

# 对：JSON 字符串必须引号
CMD ["nginx", "-g", "daemon off;"]
```

### exec 形式不展开变量

```dockerfile
# 错：$PORT 是字面字符串，不会被 shell 展开
CMD ["node", "server.js", "--port", "$PORT"]

# 对 1：用 shell 形式（接受 PID 1 副作用）
CMD node server.js --port $PORT

# 对 2：先用 envsubst 或脚本处理
ENTRYPOINT ["./entrypoint.sh"]
```

### 多个 CMD / ENTRYPOINT 只最后一个生效

```dockerfile
CMD ["a"]
CMD ["b"]    # 只有 b 生效
```

### 跑 Postgres / Redis 没设 initdb 路径

```dockerfile
# 镜像里 postgres 命令不接受 -D 参数
CMD ["postgres"]
# 启动会失败，要用 entrypoint 脚本检查数据目录
```

## 调试

```shell
# 临时换 shell 进容器，看真实启动命令
docker run --entrypoint=/bin/sh -it <image>

# 看镜像的 ENTRYPOINT 和 CMD
docker inspect <image> | jq '.[0].Config.Entrypoint, .[0].Config.Cmd'

# 启动时附带参数，覆盖 CMD
docker run <image> --help

# 完全替换入口
docker run --entrypoint=ls <image> -la /app
```

## 参考

- <https://docs.docker.com/reference/dockerfile/#entrypoint>
- <https://docs.docker.com/reference/dockerfile/#cmd>
- <https://docs.docker.com/engine/containers/run/#cmd-shell-form>
- <https://github.com/krallin/tini> — 当 PID 1 用的 init
