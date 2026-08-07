# Shell 编程

Shell 脚本是 Linux / Unix 运维 / 工具开发 / 自动化的核心。这篇从基础到实战，全面覆盖 bash / POSIX shell 编程要点。

## 1. Shell 类型

| Shell | 来源 | 主要场景 |
| --- | --- | --- |
| **sh** | POSIX 标准 | 所有 Unix 默认 |
| **bash** | GNU | Linux 默认 |
| **zsh** | macOS 默认 / oh-my-zsh | 交互 shell |
| **dash** | Debian 系 /bin/sh | POSIX 脚本 |
| **ksh** | KornShell | AIX / 老系统 |
| **fish** | Friendly Shell | 易上手 |

**脚本第一行** shebang：

```bash
#!/bin/bash
#!/usr/bin/env bash
#!/bin/sh
#!/usr/bin/env python3
```

```bash
# 用 env 更兼容（PATH 上多版本）
#!/usr/bin/env bash
```

## 2. 变量

### 2.1 赋值与引用

```bash
NAME="alice"
PATH_DIR=/opt/app          # 推荐: 全大写 + 下划线
readonly CONST_VAR=42       # 常量
unset NAME

# 引用
echo "$NAME"
echo "${NAME}_suffix"      # 推荐显式花括号
echo '$NAME'                # 单引号 → 字面

# 命令替换
NOW=$(date +%s)
FILES=$(ls *.txt)
DIR=$(dirname "$FILE")

# 算术
COUNT=$((1+2))
SUM=$(($a + $b))
((COUNT++))                 # 自增
```

### 2.2 特殊变量

| 变量 | 含义 |
| --- | --- |
| `$0` | 脚本名 |
| `$1`-`$9` | 参数 |
| `${10}+` | 多位参数 |
| `$#` | 参数个数 |
| `$@` | 全部参数（保留分隔） |
| `$*` | 全部参数（合并为单字符串） |
| `$$` | PID |
| `$?` | 上条命令退出码 |
| `$_` | 上一条命令最后一个参数 |
| `$!` | 上一个后台进程 PID |

```bash
# "$@" 是推荐写法
for arg in "$@"; do ...; done
for arg in "$*"; do ...; done    # 单字符串
```

### 2.3 默认值 / 替换

```bash
${var:-default}        # 变量为空时返回 default（不赋值）
${var:=default}        # 变量为空时赋值 default
${var:+alt}            # 变量非空时用 alt
${var:?error}          # 变量为空时输出 error 退出

${var#prefix}          # 删最短前缀
${var##prefix}         # 删最长前缀
${var%suffix}          # 删最短后缀
${var%%suffix}         # 删最长后缀

${var:offset:length}   # 切片

${#var}                # 长度
${var^^}               # 转大写
${var,,}               # 转小写
${var^}                # 首字母大写
${var~}                # 大小写反转首字母
```

例：

```bash
file=/var/log/app.log
echo ${file##*/}        # app.log
echo ${file%.*}         # /var/log/app
echo ${file##*.}        # log
echo ${#file}           # 17
```

### 2.4 数组

```bash
arr=(a b c)
arr[0]=alpha
arr[10]=j

echo "${arr[0]}"
echo "${arr[@]}"            # 全部
echo "${#arr[@]}"           # 长度

# 遍历
for x in "${arr[@]}"; do
    echo "$x"
done

# 切片
echo "${arr[@]:1:2}"       # b c

# 删除
unset arr[1]
```

关联数组（hashmap）：

```bash
declare -A map
map[apple]=red
map[banana]=yellow

echo "${map[apple]}"
for k in "${!map[@]}"; do echo "$k: ${map[$k]}"; done
```

### 2.5 字符串

```bash
s="hello world"
echo ${#s}                # 11
echo ${s/world/earth}
echo ${s%world}           # 删后缀
echo ${s#hello}           # 删前缀
echo ${s^^}                # 全大写
echo ${s,,}                # 全小写
echo ${s:6:5}              # world
```

## 3. 引号与转义

```bash
echo $NAME                 # 词拆分 + 通配
echo "$NAME"               # 字面
echo '$NAME'               # 字面且不展开变量 / 命令

# 反斜杠
echo \$NAME                # $NAME

# 反引号 vs $()
`date`
$(date)                    # 推荐

# 嵌套
echo "$(echo "$(echo hello)")"
```

## 4. 条件

### 4.1 test / [ ]

```bash
[ -f file ]              # 普通文件
[ -d dir ]               # 目录
[ -e path ]              # 存在
[ -r file ]              # 可读
[ -w file ]              # 可写
[ -x file ]              # 可执行
[ -s file ]              # 非空
[ -L link ]              # 符号链接
[ -z str ]               # 空字符串
[ -n str ]               # 非空
[ "$a" = "$b" ]          # 字符串等
[ "$a" != "$b" ]         # 不等
[ "$a" -eq "$b" ]        # 整数等
[ "$a" -ne "$b" ]        # 整数不等
[ "$a" -lt "$b" ]        # <
[ "$a" -gt "$b" ]        # >
[ "$a" -le "$b" ]        # <=
[ "$a" -ge "$b" ]        # >=
[ ! -d dir ]              # 取反
[ -d dir1 -o -d dir2 ]    # 或
[ -f f -a -r f ]          # 与
[[ "$a" =~ regex ]]       # 扩展正则（bash）
[[ "$a" == b* ]]          # glob
```

### 4.2 [[ ]] 与 [ ]

| 特性 | `[ ]` | `[[ ]]` |
| --- | --- | --- |
| POSIX | ✔ | ✘（bash / zsh） |
| 词拆分 | ✔ | ✘ |
| 通配 | ✘ | ✔ |
| 正则 | ✘ | `=~` |
| <code>&& &#124;&#124;</code> | ✘ | ✔ |

### 4.3 if / case

```bash
if [ -f /etc/passwd ]; then
    cat /etc/passwd
elif [ -d /etc ]; then
    ls /etc
else
    echo "missing"
fi
```

```bash
case "$opt" in
    a) do_a ;;
    b) do_b ;;
    *) default_action ;;
esac
```

## 5. 循环

### 5.1 for

```bash
# 列表
for x in a b c; do echo "$x"; done

# 范围
for i in {1..10}; do echo "$i"; done
for i in $(seq 1 10); do echo "$i"; done

# 数组
for x in "${arr[@]}"; do echo "$x"; done

# 命令
for f in *.txt; do echo "$f"; done

# C 风格
for ((i=0; i<10; i++)); do echo "$i"; done

# 文件
while IFS= read -r line; do
    echo "$line"
done < file.txt
```

### 5.2 while / until

```bash
while read -r line; do ...; done < file

count=0
while ((count < 10)); do
    echo $count
    ((count++))
done

until cmd; do ...; done

# 无限循环
while true; do ...; done
for ((;;)); do ...; done
```

### 5.3 break / continue

```bash
for i in 1 2 3 4 5; do
    [ $i -eq 3 ] && continue
    [ $i -eq 5 ] && break
    echo "$i"
done
```

### 5.4 select

```bash
select opt in foo bar quit; do
    case $opt in
        foo) do_foo ;;
        bar) do_bar ;;
        quit) break ;;
    esac
done
```

## 6. 函数

### 6.1 定义

```bash
function greet() {
    local name="$1"
    echo "hello $name"
}

greet alice                # hello alice
```

### 6.2 返回值

```bash
function add() {
    local r=$(($1 + $2))
    echo "$r"               # 输出当作 return
}
sum=$(add 3 4)
echo "$sum"                # 7

# 退出码
function fail() { return 1; }
fail && echo fail || echo ok
```

### 6.3 参数 / 变量作用域

```bash
function foo() {
    local x=42             # 局部
    echo "$1 $2 $# $@"
    echo "$FUNCNAME"       # 函数名
}
```

## 7. 重定向与管道

### 7.1 标准流

```bash
cmd > file                  # stdout → file (覆盖)
cmd >> file                 # append
cmd < file                  # stdin ← file
cmd 2> file                 # stderr → file
cmd > file 2>&1             # stdout + stderr → file
cmd > file1 2> file2        # 分开
cmd &> file                 # >& 同义

cmd | tee file               # 屏幕 + 文件
cmd | tee -a file            # append
cmd | tee -i file            # 中断也写完

cmd <&5                      # stdin ← fd 5
cmd >&7                      # stdout → fd 7
```

### 7.2 HereDoc

```bash
cat <<EOF
hello
world
EOF

cat <<'EOF'                  # 不展开变量
$HOME                        # 字面
EOF

cat <<-EOF                    # 缩进（去掉 tab）
    indented
    here
EOF
```

### 7.3 HereString

```bash
grep error <<<"$log"          # 从字符串读
while read line; do ...; done <<<"$multi_line"
```

### 7.4 管道 + 命名管道

```bash
mkfifo /tmp/pipe
prog1 > /tmp/pipe &
prog2 < /tmp/pipe
```

### 7.5 进程替换

```bash
diff <(ls dir1) <(ls dir2)
while read line; do
    process "$line"
done < <(find . -name "*.log")
```

## 8. 文本处理三剑客

```bash
# grep
grep -rnE 'error' file
grep -v '^#' file

# sed
sed -i 's/old/new/g' file
sed -n '1,5p' file

# awk
awk '{print $1}' file
awk -F: '$3<1000' /etc/passwd

# j
jq '.users[] | select(.active)' data.json
```

## 9. 信号与陷阱

```bash
trap 'echo "exit"' EXIT
trap 'cleanup' SIGINT SIGTERM

# 忽略
trap '' SIGTERM

# kill
kill -TERM <pid>
kill -USR1 <pid>           # 自定义
kill -9 <pid>              # 不可捕获
```

## 10. 调试

```bash
bash -x script.sh           # 打印每条命令
bash -n script.sh           # 语法检查
bash -v script.sh           # 详细输出
set -x                      # 局部
set +x                      # 关

# 错误检查
set -e                      # 出错即退
set -u                      # 未定义变量报错
set -o pipefail             # 管道失败
set -E                      # trap 传给函数
shopt -s inherit_errexit   # 继承 errexit

# trap ERR
trap 'echo error at line $LINENO' ERR
```

## 11. 数学运算

```bash
$((a+b))
$((a/b))                   # 整数除法
let "a=b*2"
echo "scale=2; 10/3" | bc   # 小数

# awk
awk 'BEGIN{print 10/3}'

# 进制
$((16#FF))                 # 16 进制
printf '%x' 255
```

## 12. 数组高级

```bash
mapfile -t arr < <(find .)
readarray -t arr <<<"$lines"

# 排序
arr=(5 1 3)
printf '%s\n' "${arr[@]}" | sort -n
```

## 13. 进程与作业

```bash
cmd &                       # 后台
wait                       # 等所有后台
jobs                       # 列出当前 shell 后台
fg %1                      # 后台调前台
kill %1

# nohup
nohup cmd &
disown %1                  # 让 job 父进程退出时不挂掉

# wait $!
sleep 100 &
PID=$!
wait $PID
```

## 14. 配置 / 启动文件

详见 [login-shell.md](login-shell.md)：

```text
login shell
   /etc/profile
   /etc/profile.d/*.sh
   ~/.bash_profile | ~/.bash_login | ~/.profile

interactive non-login
   /etc/bash.bashrc
   ~/.bashrc

non-interactive
   $BASH_ENV
```

## 15. 完整脚本模板

```bash
#!/usr/bin/env bash
# 描述
# Usage: ./script.sh arg1 arg2

set -Eeuo pipefail
shopt -s inherit_errexit

# 常量
readonly PROG=$(basename "$0")
readonly VERSION=1.0
readonly USAGE="Usage: $PROG arg1 arg2"

# 全局变量
VERBOSE=0
LOG_FILE=""

# 日志
log() {
    echo "[$(date '+%Y-%m-%dT%H:%M:%S')] $*" >&2
}

# trap
trap 'cleanup' EXIT INT TERM
cleanup() {
    [[ -n "$WORK_DIR" ]] && rm -rf "$WORK_DIR"
}

# 参数解析
while (( $# > 0 )); do
    case "$1" in
        -h|--help) echo "$USAGE"; exit 0 ;;
        -v|--verbose) VERBOSE=1 ;;
        --log) LOG_FILE="$2"; shift ;;
        *) ARGS+=("$1") ;;
    esac
    shift
done

# main
main() {
    local arg1="${ARGS[0]:-}"
    local arg2="${ARGS[1]:-}"

    [[ -z "$arg1" ]] && { echo "$USAGE" >&2; exit 1; }

    log "Starting"
    [[ "$VERBOSE" -eq 1 ]] && set -x

    # 业务
    do_work "$arg1" "$arg2"

    log "Done"
}

do_work() {
    local a="$1" b="$2"
    echo "processing $a / $b"
}

main "$@"
```

## 16. 性能优化

```bash
# 用 grep 而非 awk
grep "PATTERN" | wc -l   # 比 awk '{c++}END{print c}' 快

# 避免子 shell
while read x; do echo "$x"; done < file  # 好
cat file | while read x; do ...; done      # 慢（fork）

# bash 内建
echo 代替 echo() 子 shell
[[ ]] 代替 test

# builtin 取代外部命令
echo $PATH | tr ':' '\n'      # 慢
printf "%s\n" "${PATH//:/$'\n'}"  # 快
```

## 17. 命名 / 风格

- 函数 + 变量：snake_case（小写下划线）
- 常量：UPPER_SNAKE_CASE
- 局部变量：local
- 引号：$var 都加引号 "${var}"
- 文件：以 .sh 后缀
- lint：使用 [shellcheck](https://www.shellcheck.net/)

## 18. 常见错误

| 错 | 修 |
| -- | -- |
| `[ $var = foo ]` 报 "syntax error" | `[[ $var == foo ]]` 或加引号 |
| `for f in $(find .)` 词拆分错 | `while IFS= read -r f; do ...; done < <(find .)` |
| `cat file <code>&#124;</code> grep ...` 多了 cat | `grep ... file` |
| 没有 set -e 出错不退出 | `set -e` 或手动检查 $? |
| 子 shell 改父变量 | 重定向或临时文件 |
| 用 -e 测试变量空值 | `[[ -z "$var" ]]` 才稳 |

## 19. 调试技巧

```bash
PS4='+ ${FUNCNAME[0]:-top} ${LINENO}: '
set -x

# bashdb / shell-debug
bash --debugger script.sh
```

## 20. 与其它语言对比

| 任务 | bash | python | Go |
| --- | --- | --- | --- |
| 简单文本 | 优 | 中 | 中 |
| 复杂逻辑 | 中 | 优 | 优 |
| 跨平台 | 弱 | 强 | 强 |
| 部署 | 简单 | 需 python | 编译单文件 |
| 性能 | 慢 | 中 | 快 |

**经验**：

- 1-100 行工具脚本 → bash
- 100-1000 行 → bash + 库化 / Python
- 1000+ 行 → Python / Go / Rust

## 21. 一句话总结

```text
shell 编程 = bash + set -Eeuo pipefail + trap + shellcheck + $@
变量："$@" 引用；local 声明；[[ ]] 测试
循环：for / while / until；break / continue
函数：local + $1 + return / stdout
重定向：> >> < 2>&1 + <<< + pipe + process substitution
调试：set -x / trap ERR / shellcheck
```

## 22. 参考

- `man bash`
- `man test`
- [ShellCheck](https://www.shellcheck.net/)
- [Bash Reference](https://www.gnu.org/software/bash/manual/)
- [Bash Pitfalls](https://mywiki.wooledge.org/BashPitfalls)
- [Pure Bash Bible](https://github.com/dylanbeattie/roguelike/blob/master/pure-bash-bible.md)
- [POSIX Shell Command Language](https://pubs.opengroup.org/onlinepubs/9699919799/utilities/sh.html)
