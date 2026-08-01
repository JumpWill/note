# grep

按文本模式（regex）逐行匹配并输出，Linux 文本三剑客之一。三个常用变体：

| 命令 | 含义 |
| ---- | ---- |
| `grep` | 基础正则（BRE） |
| `egrep` | 扩展正则（ERE），已并入 `grep -E` |
| `fgrep` | 字面字符串（已并入 `grep -F`） |
| `rgrep` | 递归（`-r`） |
| `pgrep` | 进程名匹配 |

## 1. 基本用法

```bash
grep [OPTIONS] PATTERN [FILE...]
```

| 选项 | 含义 |
| ---- | ---- |
| `-i` | 忽略大小写 |
| `-v` | 取反匹配 |
| `-c` | 仅显示计数 |
| `-l` | 只列文件 |
| `-L` | 不匹配的文件 |
| `-n` | 带行号 |
| `-h` | 不显示文件名 |
| `-r / -R` | 递归（默认 skip binary，可加 `-a`） |
| `-o` | 只输出匹配的内容 |
| `-m N` | 最多匹配 N 处 |
| `-q` | quiet（只关心退出码，不输出） |
| `-w` | 全词匹配 |
| `-x` | 全行匹配 |
| `-A N` | 匹配后 N 行 |
| `-B N` | 匹配前 N 行 |
| `-C N` | 前后各 N 行 |
| `-s` | 不报错 |
| `-e PAT1` | 多模式 |
| `-E` | ERE 正则 |
| `-P` | PCRE 正则（GNU 扩展） |
| `-F` | 字面字符串 |
| `--color=auto` | 命中彩色 |
| `-Z` | NUL-separated filename |
| `-z` | NUL-separated input |
| `-I` | 跳过二进制 |

## 2. 三种正则

### 2.1 BRE（默认）

转义元字符 `\{ \} \( \) \+`：

```bash
grep '[0-9]\{3\}'                        # 3 位数字
grep '\(ab\)\+'
```

### 2.2 ERE（`grep -E` / `egrep`）

元字符直接生效：

```bash
grep -E '#[0-9]+|#[A-F]+' file          # 颜色或数字
grep -E '^[^:]+:[^:]+$' /etc/passwd     # 简单两字段
```

### 2.3 PCRE（`grep -P`）

```bash
grep -P '\b\d{1,3}(\.\d{1,3}){3}\b'     # IP
grep -P '(?<=[^a-z])err(?=[^a-z])'      # 词边界
grep -P '\d+(?= )' file                  # lookahead
```

### 2.4 常用元字符（PCRE/ERE）

| 元字符 | 含义 |
| ----- | ---- |
| `.` | 任意单字符 |
| `^` / `$` | 行首 / 行尾 |
| `*` / `+` / `?` | 0+ / 1+ / 0-1 |
| `{n,m}` | n–m 次 |
| `[abc]` / `[^abc]` | 字符类 |
| `(...)` | 分组 |
| <code>&#124;</code> | OR |
| `\b / \B` | 词边 / 非词边 |
| `\d / \D` | 数字 / 非数字（PCRE） |
| `\w / \W` | 词字符 / 反（PCRE） |
| `(?=...) / (?!...)` | 正负 lookahead（PCRE） |
| `(?<=...) / (?<!...)` | 后顾（PCRE） |

## 3. 常用例子

### 3.1 基本

```bash
grep foo /etc/passwd                       # 含 foo
grep -in 'error' file.log                  # 不分大小写 + 行号
grep -v '^$' file                          # 去空行
grep -v '^[[:space:]]*$' file              # 也去含空格的"空行"
grep '^$' file | wc -l                     # 统计空行数
grep -c '^$' file                          # 直接计数
```

### 3.2 反义与组合

```bash
grep -E '(error|fail)' file                # 含 error 或 fail
grep -E 'error' file | grep -v 'fail'      # 含 error 且不含 fail
grep -v 'debug' *.log                      # 多个文件中去除 debug
```

### 3.3 词边界

```bash
grep -w 'host' /etc/hosts                  # host 单独成词，不匹配 ghost
grep -wE 'port|host|user' file            # 任一关键词
```

### 3.4 上下文

```bash
grep -B 2 'panic' kern.log                 # panic 前 2 行
grep -A 5 'Traceback' app.log              # 后 5 行
grep -C 3 'Connection refused' app.log     # 前后 3 行
```

### 3.5 递归

```bash
grep -rn 'TODO' src/                       # 列出所有匹配 + 行号
grep -rn --include='*.go' 'TODO' .         # 限定 .go 文件
grep -rn --exclude-dir=vendor --exclude='*.test.go' .
grep -rl 'TODO' src/                        # 仅列文件
grep -L 'TODO' src/                        # 不含 TODO 的文件
```

### 3.6 输出控制

```bash
grep -oE '[0-9]+(\.[0-9]+){3}' file        # 仅输出匹配 IP，不带前后缀
grep -m 1 'systemd' /var/log/kern.log      # 找到 1 个就停
grep -B 1 -m 5 'CPU' log                   # 最多 5 处
```

### 3.7 二次过滤 / 流水线

```bash
grep -oE 'pid=[0-9]+' file | sort -u
grep '^2024-' access.log | awk '{print $7}' | sort | uniq -c | sort -rn | head
```

### 3.8 退出码

```bash
grep -q ERROR log; echo $?   # 0:命中, 1:不命中, 2:错误
if grep -q 'pattern' file; then ... ; fi
```

适合 shell 脚本。

### 3.9 大文件 / 流

```bash
cat big.log | grep --line-buffered 'INFO'   # 每行一次刷
pv -c access.log | grep 'GET' | ...        # 进度条
```

### 3.10 二进制

```bash
grep -a 'url' nginx                       # 把二进制当文本
grep -I 'string' .                         # 跳过二进制
grep -Z 'pattern' file                     # 配 -print0 使用
```

### 3.11 字面字符串 (no regex)

```bash
grep -F 'http://example.com/login?a[1]=2' file
fgrep 'a.b.c' file                         # 老语法
```

适合匹配含特殊字符的字面串。

### 3.12 行内 IP / 邮箱 / 域名

```bash
grep -Eo '([0-9]{1,3}\.){3}[0-9]{1,3}' file
grep -Eo '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}' file
grep -Eo '\bhttps?://[A-Za-z0-9.-]+(/[^\s]*)?\b' file
```

### 3.13 含颜色 / 高亮

```bash
grep --color=always 'foo' file              # 强制颜色（管道后有用）
grep --color=auto -nE 'error|fail' file
```

`alias` 加全局默认：

```bash
alias grep='grep --color=auto'
```

### 3.14 --include / --exclude

```bash
grep -rnE 'foo' --include='*.py' .          # 只 .py
grep -rnE 'bar' --exclude='*.min.js' .     # 排除 .min.js
grep -rn --exclude-dir='node_modules|.git' .
```

### 3.15 -z / -Z 处理 NUL

```bash
grep -rlZ 'pattern' dir | xargs -0 rm
```

### 3.16 流式日志匹配

```bash
tail -F /var/log/nginx/access.log | grep --line-buffered '5[0-9][0-9]'
```

### 3.17 性能 / 提前终止

```bash
LC_ALL=C grep -E 'PATTERN' huge.log        # LC_ALL=C 提速度
grep -m 1 '...' huge.log                  # 找到就退出
```

字节模式更快：把 regex 简化为 `-F`

```bash
grep -Fc 'fixed_string' huge.log
```

## 4. 常见 fgrep / egrep 替代

| 旧 | 现代 |
| -- | ---- |
| `fgrep 'PAT'` | `grep -F 'PAT'` |
| `egrep 'PAT'` | `grep -E 'PAT'` |
| `grep -P` | PCRE |

`grep` 三种行为并入一个命令。

## 5. 在 shell 中的小工具

### 5.1 进程 / 端口

```bash
pgrep -f 'python'
pgrep -l 'ssh'
pkill -TERM $(pgrep -f 'python')
```

### 5.2 在管道 / xargs 中

```bash
grep -rl 'TODO' src/ | xargs sed -i 's/TODO/DONE/g'
git grep -l ''                            # 当前仓库
```

### 5.3 多模式

```bash
grep -e 'foo' -e 'bar'                    # OR 多模式
grep -E 'foo|bar'
```

### 5.4 仅看列

```bash
grep -E '^[0-9]+:' /etc/passwd > users.txt
```

### 5.5 fgrep + 模式文件

```bash
grep -f patterns.list file                # 命中 patterns.list 中任一行
grep -Fxvf - file                        # 反向字面去重
```

## 6. ripgrep (rg)

比 grep 快的现代替代，Rust 写：

- 默认递归
- 默认忽略 `.gitignore`
- 默认 PCRE2
- 输出更友好

```bash
rg 'TODO'
rg -tgo 'function' .                     # 只 .go
rg -F 'literal.string'
rg -A 3 'panic'
rg -n 'pattern' --stats
```

## 7. 更多实用例子

### 7.1 日志 / Nginx / Apache

```bash
# nginx 5xx 错误 + 客户端 IP
grep -E '" [5][0-9]{2} [0-9]+"' access.log | awk '{print $1}' | sort -u

# 5 秒滑动窗口内 5xx 增多报警思路
grep -E '" 5[0-9]{2} ' access.log | awk '{print $4}' | sort | uniq -c

# Top 10 错误 UA
grep -E '" 5[0-9]{2} ' access.log | awk -F'"' '{print $6}' | sort | uniq -c | sort -rn | head

# 错误码 500，仅 match 静态文件
grep -nE 'GET /static/[^\"]* HTTP/1\.[01]\" 5[0-9]{2} ' access.log

# access.log 中指定 IP
grep -E '^\"?[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+\"' access.log | grep -E '212\.123\.[0-9]+\.[0-9]+'
```

### 7.2 系统日志 / K8s

```bash
# Docker / K8s 日志多行匹配关键 stacktrace
grep -A 30 'panic:' /var/log/containers/*.log | head -50

# systemd 日志按 PID
grep -i 'segfault' /var/log/kern.log
journalctl -k | grep -i 'oom'

# K8s 拉镜像失败
grep -E 'image pull' /var/log/containers/*

# 查找 restarts
grep -E 'restart_count' /var/log/containers/kube-system* | head
```

### 7.3 文件 / 代码搜索

```bash
# 查找包含 TODO 的 Python 文件
grep -rl 'TODO' --include='*.py' .

# 找出函数定义
grep -nE 'def [a-z_][a-zA-Z0-9_]*' *.py

# 查找 IPv4 严格
grep -Eo '\b(([0-9]{1,3}\.){3}[0-9]{1,3})\b' *.log

# 邮箱
grep -Eo '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'

# URL
grep -Eo '\bhttps?://[^ \t\n]+' *.html

# 查找 commit hash（7–40 位）
git log | grep -Eo '\b[0-9a-f]{7,40}\b'
```

### 7.4 CSV / 配置 / ETL

```bash
# 取第 3 列含数字的行
grep -E '^[^,]+,[^,]+,[0-9]+,' data.csv

# 找出超长行（CSV 列错位）
grep -E -c '.' file | # 反过来
awk '{n=gsub(/,/,"&"); print NR, n}' file

# 排除 inode / dev / utmp 噪声
grep -v '/proc\|/sys' /proc/*/cmdline 2>/dev/null | xargs -0 -n1 grep
```

### 7.5 多文件 / 流水线

```bash
# 并行 grep
parallel -j 8 'grep -l PATTERN {}' ::: *.log

# grep 二进制 AS 文本
grep -ao 'pattern' binary > /dev/null

# 反向输出（行顺序反转）
grep -nE '.' file | tac
```

### 7.6 regex 速查

```text
匹配 IPv4:
  \b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b

匹配 email:
  [A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}

匹配 ISO 日期:
  [0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])

匹配中文字符:
  [\x{4e00}-\x{9fa5}]
```

### 7.7 含中文 / Unicode

```bash
grep -P '[\x{4e00}-\x{9fa5}]' file         # PCRE
LC_ALL=C grep -P '[\x80-\xff]+' file       # 单字节 UTF-8
```

### 7.8 性能 / 高亮技巧

```bash
# 大文件先 narrow 再 grep
grep -m 1000 pattern huge | tail
LC_ALL=C grep -F 'literal' huge            # 字面比 ERE 快
grep --mmap -F 'literal' huge              # mmap 提升 IO
```

### 7.9 含特殊字符

```bash
grep -e '-abc' file            # -abc 被当成 option
grep '\-abc' file              # 转义
grep -F '\-' file
grep -e '\\' -e '"' file       # 多模式
```

### 7.10 复杂组合

```bash
# 文件名 + 内容双匹配
git grep -l 'TODO'            # git 仓库内
git grep -E 'TODO|FIXME'

# 内部出现 "PASS" 前后 5 行
grep -C 5 PASS app.log

# 任意 1 个 IP 起头访问 4xx
grep -E '^[0-9.]+\ .*" 4[0-9]{2} ' access.log

# 多个压缩文件去重
zgrep -h 'pattern' *.gz | sort -u
```

## 8. 一句话总结

```text
grep = pattern + per-line + regex
-i 忽略大小写
-v 取反
-n 行号
-r 递归
-E ERE
-F 字面
-o 仅匹配
-C N 上下文
```

## 8. 参考

- `man grep`
- `man pcre2pattern`
- `info grep`
- [ripgrep (BurntSushi/ripgrep)](https://github.com/BurntSushi/ripgrep)
