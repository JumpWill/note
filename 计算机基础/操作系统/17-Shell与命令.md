# Shell 与命令 (Shell & Commands)

## 一、Shell 概述

### 什么是 Shell

**Shell**:用户与操作系统交互的**命令解释器**(Command Interpreter)

**主要职责**:
- 解析命令
- 执行命令
- 提供脚本编程
- 启动程序
- 文件操作
- 进程控制

### 主流 Shell

| Shell           | 特点                          | 默认 OS        |
|-----------------|-------------------------------|----------------|
| **sh (Bourne)** | Unix 经典,POSIX 兼容          | Unix、Linux    |
| **bash**        | sh 的超集,最流行              | Linux 默认     |
| **zsh**         | 强大,Oh My Zsh 必备           | macOS 默认     |
| **fish**        | 用户友好,自动补全             | 第三方         |
| **csh/tcsh**    | C 风格语法                    | BSD Unix       |
| **ksh**         | Korn shell,商业用             | AIX、HP-UX     |
| **PowerShell**  | 对象导向,跨平台               | Windows、Linux |
| **Nushell**     | Rust 写的现代 shell           | 第三方         |
| **dash**        | 轻量 bash 替代,Debian 默认 sh | 嵌入式、Debian |

### Shell 选择建议

- **服务器**:bash (默认,生态成熟)
- **桌面**:zsh (Oh My Zsh 增强)
- **学习/脚本**:bash (最大兼容性)
- **嵌入式**:dash / busybox sh

---

## 二、Bash 基础

### 1. 启动

```bash
# 查看当前 shell
echo $SHELL
echo $0

# 切换 shell
bash
zsh

# 退出
exit
logout
Ctrl+D
```

### 2. 命令行结构

```bash
command [-options] [arguments]
```

- **command**:命令
- **options**:选项,通常 `-` 短选项,`--` 长选项
- **arguments**:参数

### 3. 命令类型

```bash
type ls           # 看类型: alias / builtin / file / function / keyword
type -a ls        # 全部
which ls         # 找 PATH 中的位置
whereis ls       # 找命令、源码、man page
```

**类型**:
- **alias**:别名
- **builtin**:内建命令
- **file**:外部程序
- **function**:shell 函数
- **keyword**:关键字 (if、while 等)

### 4. 常用快捷键

| 快捷键         | 作用                       |
|----------------|----------------------------|
| `Ctrl+C`       | 终止当前命令               |
| `Ctrl+D`       | EOF, 退出                  |
| `Ctrl+Z`       | 挂起(暂停)                 |
| `Ctrl+L`       | 清屏                       |
| `Ctrl+A`       | 移到行首                   |
| `Ctrl+E`       | 移到行尾                   |
| `Ctrl+U`       | 删除到行首                 |
| `Ctrl+K`       | 删除到行尾                 |
| `Ctrl+W`       | 删除一个单词               |
| `Ctrl+Y`       | 粘贴删除的内容             |
| `Ctrl+R`       | 反向搜索历史               |
| `Ctrl+P` / `↑` | 上一条命令                 |
| `Ctrl+N` / `↓` | 下一条命令                 |
| `Tab`          | 自动补全                   |
| `Ctrl+Shift+C` | 复制 (终端)                |
| `Ctrl+Shift+V` | 粘贴 (终端)                |

---

## 三、Bash 脚本基础

### 1. 创建脚本

```bash
#!/bin/bash
# 这是一个注释
echo "Hello, World!"
```

**Shebang**:`#!/bin/bash` 告诉系统用什么解释器执行

**可用的解释器**:

| Shebang               | 用途                  |
|-----------------------|-----------------------|
| `#!/bin/bash`         | bash                  |
| `#!/bin/sh`           | sh (POSIX 兼容)       |
| `#!/bin/zsh`          | zsh                   |
| `#!/usr/bin/python3`  | Python                |
| `#!/usr/bin/env bash` | 跨平台,自动找 bash    |
| `#!/bin/dash`         | dash,轻量             |

### 2. 脚本执行

```bash
# 方式 1: 显式调用解释器
bash script.sh

# 方式 2: 给执行权限,直接执行
chmod +x script.sh
./script.sh

# 方式 3: source (在当前 shell 中执行)
source script.sh
. script.sh
```

**区别**:
- `bash script.sh`:子 shell 执行
- `./script.sh`:子 shell 执行
- `source script.sh`:当前 shell 执行(变量保留)

### 3. 注释

```bash
# 单行注释

: '
多行注释(冒号 + 空格 + 单引号包围)
'

<<COMMENT
另一种多行注释
用 here-document
COMMENT
```

### 4. 变量

```bash
# 定义变量 (无空格!)
name="John"
age=30
path="/usr/local/bin"

# 使用变量
echo $name
echo ${name}              # 推荐加花括号
echo "Hello, $name!"
echo "Hello, ${name}!"

# 只读变量
readonly PI=3.14
declare -r PI=3.14

# 删除变量
unset name

# 变量类型
declare -i num=42         # 整数
declare -a arr=()          # 数组
declare -A map=()          # 关联数组 (Bash 4+)
declare -x VAR=value       # 导出为环境变量 (= export)
declare -r VAR=value       # 只读

# 变量作用域
local var=value           # 函数内局部变量
```

**特殊变量**:

| 变量        | 含义                                    |
|-------------|-----------------------------------------|
| `$0`        | 脚本名                                  |
| `$1` ~ `$9` | 位置参数                                |
| `$#`        | 参数个数                                |
| `$@`        | 所有参数(每个独立)                      |
| `$*`        | 所有参数(整体)                          |
| `$?`        | 上一个命令的退出码(0=成功)              |
| `$$`        | 当前 shell 的 PID                       |
| `$!`        | 上一个后台进程的 PID                    |
| `$_`        | 上一个命令的最后一个参数                |

**环境变量**:

```bash
# 查看所有环境变量
env
printenv

# 临时设置
export PATH=$PATH:/opt/app/bin

# 永久设置
echo 'export PATH=$PATH:/opt/app/bin' >> ~/.bashrc
```

**PATH**:`:` 分隔的目录列表,shell 在这些目录里找命令

```bash
# 推荐:用命令找命令位置
which python3
type ls
```

### 5. 字符串

```bash
str="Hello World"
echo ${#str}                # 长度 11
echo ${str:0:5}              # 切片 Hello
echo ${str:6}                # 切片 World
echo ${str/World/Bash}       # 替换第一个
echo ${str//o/0}             # 替换所有
echo ${str#Hello}            # 删前缀
echo ${str%World}            # 删后缀

# 字符串拼接
a="Hello"
b="World"
c="$a $b"                    # Hello World
c="${a},${b}!"               # Hello,World!

# 默认值
${var:-default}              # var 为空,用 default
${var:=default}              # var 为空,设 default
${var:+value}                # var 非空,用 value
${var:?error}                # var 为空,报 error
```

### 6. 数组

```bash
# 一维数组
arr=(apple banana cherry)
echo ${arr[0]}                # apple
echo ${arr[@]}                # 全部
echo ${#arr[@]}               # 长度 3
arr[3]=date
arr+=(fig grape)              # 追加

# 关联数组 (Bash 4+)
declare -A map
map[name]="John"
map[age]=30
echo ${map[name]}

# 遍历
for fruit in "${arr[@]}"; do
    echo $fruit
done
```

### 7. 算术运算

```bash
# 整数运算
a=10
b=3
echo $((a + b))               # 13
echo $((a - b))               # 7
echo $((a * b))               # 30
echo $((a / b))               # 3 (整数)
echo $((a % b))               # 1
echo $((a ** 2))              # 100

# 自增
((i++))                       # 1
((i+=1))

# let
let "result = a + b"

# expr (古老)
result=`expr $a + $b`
```

### 8. 命令替换

```bash
# $(命令) 推荐
date=$(date +%Y-%m-%d)
files=$(ls)

# 旧式
date=`date +%Y-%m-%d`

# 进程替换
diff <(ls dir1) <(ls dir2)
```

### 9. 引号

| 引用     | 符号        | 行为              |
|----------|-------------|-------------------|
| 单引号   | `' '`       | 字面量,所有都原样 |
| 双引号   | `" "`       | 解释变量和命令    |
| 反引号   | `` ` ` ``   | 同 $() ,命令替换  |
| 转义     | `\`         | 转义单个字符      |
| `$'...'` | ANSI-C 引用 | 解释反斜杠转义    |

```bash
echo '$name'                  # $name
echo "$name"                  # John
echo \$name                   # $name
echo $'\n'                    # 换行
```

---

## 四、控制流

### 1. 条件 if

```bash
if [ condition ]; then
    # 块
elif [ condition2 ]; then
    # 块
else
    # 块
fi

# 一行版
if [ -f file ]; then echo "is file"; fi
```

**文件测试**:

| 表达式            | 含义              |
|-------------------|-------------------|
| `-e file`         | 存在              |
| `-f file`         | 普通文件          |
| `-d file`         | 目录              |
| `-L file`         | 符号链接          |
| `-r file`         | 可读              |
| `-w file`         | 可写              |
| `-x file`         | 可执行            |
| `-s file`         | 存在且非空        |
| `file1 -nt file2` | file1 比 file2 新 |
| `file1 -ot file2` | file1 比 file2 旧 |

**字符串测试**:

| 表达式          | 含义             |
|-----------------|------------------|
| `-z str`        | 空字符串         |
| `-n str`        | 非空字符串       |
| `str1 = str2`   | 相等             |
| `str1 != str2`  | 不等             |
| `str1 == str2`  | 相等(双括号)     |

**数值测试**:

| 表达式              | 含义           |
|---------------------|----------------|
| `n1 -eq n2`         | 等于           |
| `n1 -ne n2`         | 不等           |
| `n1 -lt n2`         | 小于           |
| `n1 -le n2`         | 小于等于       |
| `n1 -gt n2`         | 大于           |
| `n1 -ge n2`         | 大于等于       |

**逻辑测试**:

| 表达式           | 含义           |
|------------------|----------------|
| `! expr`         | 非             |
| `expr1 -a expr2` | 与(and)        |
| `expr1 -o expr2` | 或(or)         |

**现代写法**:

```bash
# [[ ]] 增强版
if [[ -f $file && -r $file ]]; then
    ...
fi

# (( )) 数值
if (( a > b )); then
    ...
fi

# 命令直接
if grep -q "error" logfile; then
    echo "有错误"
fi
```

### 2. 循环

#### for 循环

```bash
# 列表
for i in 1 2 3 4 5; do
    echo $i
done

# 范围
for i in {1..10}; do
    echo $i
done

# C 风格
for ((i=0; i<10; i++)); do
    echo $i
done

# 数组
for fruit in "${fruits[@]}"; do
    echo $fruit
done

# 命令结果
for line in $(cat file.txt); do
    echo $line
done

# 文件
for file in *.txt; do
    echo $file
done
```

#### while 循环

```bash
while [ condition ]; do
    # 块
done

# 读文件
while read line; do
    echo $line
done < file.txt

# 无限循环
while true; do
    ...
done

# until(条件为假时执行)
until [ condition ]; do
    ...
done
```

#### 控制语句

```bash
# break 退出循环
for i in {1..10}; do
    if [ $i -eq 5 ]; then
        break
    fi
    echo $i
done

# continue 跳过本轮
for i in {1..10}; do
    if [ $((i % 2)) -eq 0 ]; then
        continue
    fi
    echo $i
done
```

### 3. case

```bash
case $var in
    pattern1)
        # 块
        ;;
    pattern2|pattern3)
        # 块
        ;;
    *)
        # 默认
        ;;
esac
```

**示例**:

```bash
case "$1" in
    start)
        echo "Starting"
        ;;
    stop)
        echo "Stopping"
        ;;
    restart|reload)
        echo "Restarting"
        ;;
    *)
        echo "Usage: $0 {start|stop|restart}"
        exit 1
        ;;
esac
```

### 4. select

```bash
select option in "Option 1" "Option 2" "Quit"; do
    case $option in
        "Option 1")
            echo "1"
            ;;
        "Option 2")
            echo "2"
            ;;
        "Quit")
            break
            ;;
    esac
done
```

---

## 五、函数

### 1. 定义与调用

```bash
# 定义
function greet() {
    echo "Hello, $1!"
}

# 调用
greet "John"

# 或
greet() {
    local name=$1                # local 局部变量
    echo "Hello, $name!"
    return 0                     # 退出码
}
```

### 2. 参数与返回值

```bash
myfunc() {
    echo "参数1: $1"
    echo "参数2: $2"
    echo "所有参数: $@"
    echo "参数个数: $#"
    
    local result=$(( $1 + $2 ))
    return $result                # return 只能返回 0-255
}

# 捕获输出
result=$(myfunc 3 4)
echo $result

# 捕获退出码
myfunc 3 4
echo "退出码: $?"
```

### 3. 导出函数

```bash
# 导出给子 shell
export -f myfunc
```

---

## 六、输入输出

### 1. 标准流

| 流      | 文件描述符 | 默认       |
|---------|------------|------------|
| stdin   | 0          | 键盘       |
| stdout  | 1          | 终端       |
| stderr  | 2          | 终端       |

### 2. 重定向

```bash
# 输出重定向
ls > file.txt              # 覆盖
ls >> file.txt             # 追加
ls 2> err.txt              # stderr
ls > out.txt 2>&1          # stdout + stderr
ls &> all.txt               # stdout + stderr (Bash)

# 输入重定向
read line < file.txt
while read line; do
    echo $line
done < file.txt

# Here Document
cat <<EOF
多行
内容
EOF

# Here String
cat <<< "Hello, World!"
```

### 3. 管道 (|)

```bash
ls | grep ".txt" | wc -l
ps aux | grep nginx | awk '{print $2}'

# 命名管道 (FIFO)
mkfifo /tmp/myfifo
cmd1 > /tmp/myfifo &
cmd2 < /tmp/myfifo
```

### 4. tee

```bash
# 同时输出到文件和屏幕
ls | tee file.txt
ls | tee -a file.txt          # 追加

# 多文件
ls | tee file1.txt file2.txt
```

---

## 七、文本处理三剑客

### 1. grep (Global Regular Expression Print)

**作用**:文本搜索

**语法**:`grep [options] PATTERN [files]`

**常用选项**:

| 选项              | 作用                            |
|-------------------|---------------------------------|
| `-i`              | 忽略大小写                      |
| `-v`              | 反向(不匹配)                    |
| `-r / -R`         | 递归搜索目录                    |
| `-l`              | 只显示文件名                    |
| `-c`              | 只显示匹配次数                  |
| `-n`              | 显示行号                        |
| `-w`              | 匹配整个单词                    |
| `-E`              | 扩展正则(同 egrep)              |
| `-P`              | Perl 正则                       |
| `-A n`            | 显示匹配后 n 行                 |
| `-B n`            | 显示匹配前 n 行                 |
| `-C n`            | 显示匹配前后 n 行               |
| `--include=*.txt` | 只搜特定文件                    |
| `--exclude=*.log` | 排除特定文件                    |
| `-h`              | 不显示文件名                    |
| `-o`              | 只显示匹配部分                  |

**示例**:

```bash
# 基本
grep "error" log.txt
grep -i "error" log.txt                  # 不区分大小写
grep -r "TODO" src/                      # 递归
grep -n "error" log.txt                  # 显示行号
grep -v "DEBUG" log.txt                 # 排除
grep -c "error" log.txt                 # 统计
grep -l "error" *.log                    # 只列文件名

# 正则
grep "^error" log.txt                    # 行首
grep "error$" log.txt                    # 行尾
grep "[Ee]rror" log.txt                  # 字符类
grep "err(or)?s?" log.txt                # 扩展正则 -E
grep "192\.168\.[0-9]+" log.txt          # 数字

# 上下文
grep -A 3 "error" log.txt                # 后 3 行
grep -B 2 "error" log.txt                # 前 2 行
grep -C 5 "error" log.txt                # 前后各 5 行

# 复杂
grep -E "warn|error|fatal" log.txt       # 多个模式
grep -P "192\.168\.\d+\.\d+" log.txt     # Perl 正则
```

### 2. sed (Stream Editor)

**作用**:流编辑器,文本替换/删除/插入

**语法**:`sed [options] 'command' file`

**常用选项**:

| 选项          | 作用                          |
|---------------|-------------------------------|
| `-i`          | 直接修改文件                  |
| `-e`          | 多命令                        |
| `-n`          | 安静模式(只输出处理的行)      |
| `-r / -E`     | 扩展正则                      |
| `-s`          | 多个文件分别处理              |
| `-z`          | 用 NUL 分隔行                 |

**命令**:

```bash
# 替换
sed 's/old/new/' file                 # 每行替换第一个
sed 's/old/new/g' file               # 全局替换
sed 's/old/new/2' file               # 替换第二个
sed 's#old#new#g' file               # 用 # 作分隔
sed 's/old/new/i' file               # 忽略大小写

# 删除
sed '/pattern/d' file                # 删除匹配行
sed '5d' file                         # 删除第 5 行
sed '1,5d' file                       # 删除 1-5 行
sed '$d' file                         # 删除最后一行
sed '/^$/d' file                      # 删除空行

# 打印
sed -n '5p' file                      # 打印第 5 行
sed -n '/start/,/end/p' file         # 打印范围
sed -n '1~2p' file                    # 打印奇数行

# 插入
sed '5i\插入行' file                  # 第 5 行前插入
sed '5a\追加行' file                  # 第 5 行后追加
sed '5c\替换行' file                  # 替换第 5 行

# 多命令
sed -e 's/a/A/' -e 's/b/B/' file

# 修改文件
sed -i 's/old/new/g' file
sed -i.bak 's/old/new/g' file         # 备份
```

**示例**:

```bash
# 替换并写回
sed -i 's/8080/8081/g' config.txt

# 删除空行和注释
sed '/^$/d; /^#/d' file

# 在指定行插入
sed -i '3i\新增的第 3 行' file

# 提取字段
sed -n 's/.*: \([0-9]*\).*/\1/p' file
```

### 3. awk (Aho, Weinberger, Kernighan)

**作用**:文本处理,字段提取,报告生成

**语法**:`awk 'pattern { action }' file`

**模式**:

```bash
# BEGIN / END
awk 'BEGIN { print "开始" } { print $1 } END { print "结束" }' file

# 正则
awk '/error/ { print $0 }' file
awk '$1 ~ /err/ { print }' file
awk '$1 !~ /ok/ { print }' file

# 条件
awk '$3 > 100 { print $1 }' file
awk 'NR > 1 && $2 == "yes" { print }' file

# 范围
awk '/start/,/end/' file
```

**内置变量**:

| 变量       | 含义                                |
|------------|-------------------------------------|
| `$0`       | 整行                                |
| `$1`-`$NF` | 第 1 / 最后字段                     |
| `NF`       | 字段数                              |
| `NR`       | 当前行号(累计)                      |
| `FNR`      | 当前行号(当前文件)                  |
| `FS`       | 字段分隔符(默认空格)                |
| `OFS`      | 输出字段分隔符                      |
| `RS`       | 记录分隔符(默认换行)                |
| `ORS`      | 输出记录分隔符                      |
| `FILENAME` | 当前文件名                          |

**函数**:

```bash
# 字符串
length(s)        # 长度
substr(s, i, n)   # 子串
split(s, arr, sep)# 分割
sprintf(fmt, ...) # 格式化
tolower(s)        # 小写
toupper(s)        # 大写
match(s, regex)   # 匹配
sub(regex, repl)  # 替换
gsub(regex, repl)# 全局替换

# 数学
int(x)            # 整数
sqrt(x)           # 根
exp(x), log(x)
sin(x), cos(x)
rand()            # 随机数 0-1
srand(seed)       # 随机种子
```

**示例**:

```bash
# 打印特定字段
awk '{print $1, $3}' file
awk '{print $NF}' file                # 最后一列

# 条件
awk '$3 > 100' file
awk 'NR == 1, NR == 5' file          # 前 5 行
awk 'END { print NR }' file          # 行数

# 自定义分隔符
awk -F: '{print $1, $7}' /etc/passwd
awk -F',' '{print $2}' data.csv

# 多个分隔符
awk -F'[,:]' '{print $1, $2}' file

# 求和
awk '{sum += $3} END {print sum}' file
awk '{sum += $1} END {print "Total:", sum}' numbers.txt

# BEGIN/END
awk 'BEGIN {print "Header"} {print} END {print "Footer"}' file

# 数组
awk '{count[$1]++} END {for (k in count) print k, count[k]}' file

# 输出分隔符
awk 'BEGIN {OFS="|"} {print $1, $2, $3}' file

# 复杂
ps aux | awk '$3 > 50 {print $2, $11}'    # CPU 高的进程
df -h | awk '$5 > "80%" {print $1, $5}'   # 磁盘超过 80%
```

### 4. 三剑客对比

| 工具   | 用途                  | 适合               |
|--------|-----------------------|--------------------|
| grep   | 搜索                  | 过滤               |
| sed    | 替换/删除             | 文本转换           |
| awk    | 字段提取/计算         | 报表生成           |

**经典管道**:

```bash
# 找大文件
find / -type f -size +100M 2>/dev/null | xargs ls -lh | sort -k5 -h

# 找 CPU 高的进程
ps aux | grep -v grep | grep mysql | awk '{sum += $3} END {print sum}'

# 统计日志错误类型
grep "ERROR" log.txt | awk '{print $4}' | sort | uniq -c | sort -rn

# CSV 报表
awk -F, 'NR>1 {sum += $3} END {print "Total:", sum}' sales.csv
```

---

## 八、其他常用命令

### 1. 文本查看

```bash
cat file                    # 全部输出
less file                   # 分页(可向上)
more file                   # 分页(只能向下)
head -n 10 file             # 前 10 行
tail -n 10 file             # 后 10 行
tail -f file                # 实时跟踪
nl file                     # 显示行号
```

### 2. 文本处理

```bash
sort file                   # 排序
sort -n file                # 数字排序
sort -k2 file               # 按第 2 列
sort -r file                # 反向
sort -u file                # 去重
sort -t: -k3 -n /etc/passwd # 按 : 分隔,第 3 列数字排序

uniq file                   # 去重(只去连续重复)
uniq -c file                # 计数
sort file | uniq -c         # 全部去重并计数
sort file | uniq -c | sort -rn | head  # Top N

tr 'a-z' 'A-Z' < file     # 大小写转换
tr -d '\r' < file          # 删除字符

cut -d: -f1 /etc/passwd    # 提取字段
cut -c1-10 file             # 提取字符

paste file1 file2           # 合并文件
expand file                 # tab 转空格
unexpand file               # 空格转 tab
```

### 3. 文件操作

```bash
cp src dst                  # 复制
cp -r dir/ newdir/          # 递归
cp -p file1 file2           # 保留属性

mv src dst                  # 移动/重命名

rm file                     # 删除
rm -rf dir/                 # 强制递归删除

mkdir dir                   # 创建
mkdir -p a/b/c              # 多级

ln file hardlink            # 硬链接
ln -s target symlink        # 软链接

find / -name "*.txt"        # 查找
find / -size +100M          # 大于 100M
find / -user root           # 用户
find / -mtime -7             # 7 天内修改
find / -perm 755             # 权限
find / -type f               # 类型
find . -name "*.log" -delete  # 查找并删除

xargs -I {} cmd {}           # 构造命令
```

### 4. 系统信息

```bash
date                        # 日期
cal                         # 日历
uptime                      # 启动时间 + 负载
hostname                    # 主机名
uname -a                    # 内核信息
who                         # 谁在登录
whoami                      # 我是谁
id                          # 我的 ID
```

### 5. 用户和权限

```bash
chmod 755 file              # 改权限
chmod u+x file              # 加执行权限
chown user:group file       # 改属主
chgrp group file            # 改属组

useradd username            # 加用户
userdel -r username         # 删用户
usermod -aG sudo user       # 加 sudo 组
passwd username             # 改密码

su - username               # 切换用户
sudo command                # 临时 root
```

### 6. 进程和服务

```bash
ps aux                      # 看进程
ps -ef                      # 系统 V 风格
ps -eo pid,user,comm        # 自定义列

top                         # 实时
htop                        # 增强版
atop                        # 高级

kill PID                    # 终止
kill -9 PID                 # 强制
killall nginx               # 按名字
pkill nginx                 # 按名字(扩展)

nice -n -10 command         # 启动时
renice -n 5 -p PID          # 调整

systemctl start nginx       # 启动
systemctl status nginx      # 状态
journalctl -u nginx         # 日志
```

### 7. 网络

```bash
ip addr                     # IP 地址
ip link                     # 网络接口
ip route                    # 路由
ifconfig                    # 旧命令

ping host                   # 测连通
traceroute host             # 路径
mtr host                    # 实时

curl URL                    # HTTP 客户端
wget URL                    # 下载

ss -tan                     # TCP 连接
netstat -tan                # 旧
```

### 8. 磁盘

```bash
df -h                       # 磁盘空间
du -sh dir                  # 目录大小
du -h dir | sort -h | tail  # 找最大

lsblk                      # 看块设备
mount                      # 挂载
umount /mnt                # 卸载

dd if=/dev/zero of=file bs=1M count=100  # 写 100MB
sync                        # 刷盘
```

---

## 九、Shell 进阶

### 1. trap 信号处理

```bash
trap 'echo "中断"; cleanup' INT TERM
trap '' INT                # 忽略
trap - INT                  # 恢复默认

cleanup() {
    rm -f /tmp/mytmpfile
    exit 1
}
trap cleanup EXIT
```

### 2. 调试

```bash
# bash -x 调试
bash -x script.sh

# 在脚本中
set -x                      # 开启调试
set +x                      # 关闭

# 检查语法
bash -n script.sh

# 详细
set -v                      # 显示输入
set -e                      # 出错退出
set -u                      # 未定义变量报错
set -o pipefail             # 管道失败
set -euo pipefail            # 严格模式
```

### 3. 性能优化

```bash
# 避免子 shell
$(command)  # 子 shell
${var}      # 不用子 shell

# 避免 cat
grep pattern file          # 不用 cat file | grep
# 改为
grep pattern < file

# 数组代替字符串
arr=(a b c)                # 比
str="a b c"                # 字符串好

# 内建命令优先
[[ ]]                      # 比 [ ] 快
$(())                      # 比 expr 快
```

### 4. 安全

```bash
# 引用变量
rm "$file"                  # 不是 rm $file

# IFS 控制
IFS=$'\n'                   # 改分隔符
for line in $(cat file); do
    ...

# 临时文件
tmpfile=$(mktemp)
trap "rm -f $tmpfile" EXIT

# 防止注入
eval "$user_input"          # 危险
# 替代:case / [[ ]]

# 权限
umask 077                   # 默认新文件 600
chmod 700 sensitive.sh      # 脚本只自己可执行
```

---

## 十、实用模式

### 1. 日志分析

```bash
# 实时跟踪
tail -F /var/log/syslog

# 错误统计
grep -c "ERROR" log.txt

# Top IP
awk '{print $1}' access.log | sort | uniq -c | sort -rn | head

# 错误趋势
grep "ERROR" log.txt | awk '{print $1}' | cut -d: -f1 | uniq -c

# 大日志
journalctl --since today
```

### 2. 备份脚本

```bash
#!/bin/bash
set -euo pipefail

BACKUP_DIR=/var/backups
DATE=$(date +%Y%m%d)
SRC=/var/www/html

tar -czf $BACKUP_DIR/website-$DATE.tar.gz $SRC

# 保留最近 7 天
find $BACKUP_DIR -name "website-*.tar.gz" -mtime +7 -delete

# 远程备份
rsync -avz $BACKUP_DIR/ user@backup:/backups/
```

### 3. 系统监控

```bash
#!/bin/bash
# 监控脚本
echo "=== CPU ==="
uptime
mpstat 1 3 2>/dev/null

echo "=== 内存 ==="
free -h

echo "=== 磁盘 ==="
df -h | grep -v tmpfs

echo "=== 网络 ==="
ss -s

echo "=== 进程 ==="
ps -eo pid,user,%cpu,%mem,comm --sort=-%cpu | head
```

### 4. 日志切割

```bash
# logrotate 配置示例
/var/log/myapp/*.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
    postrotate
        systemctl reload myapp
    endscript
}
```

---

## 十一、Shell 风格

### Google Shell 风格指南 (推荐)

```bash
#!/bin/bash
#
# 脚本说明
#

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_NAME="$(basename "$0")"

# 常量大写
readonly MAX_RETRIES=3
readonly DEFAULT_TIMEOUT=30

# 局部变量小写
local file_path=""
local retry_count=0

# 函数
function get_config() {
    local config_file="$1"
    [[ -f "$config_file" ]] || { echo "Error: $config_file not found"; return 1; }
    cat "$config_file"
}

# 主函数
function main() {
    parse_args "$@"
    init
    run
    cleanup
}

main "$@"
```

---

## 十二、Shell 进阶工具

### 1. xargs

```bash
# 把 stdin 转命令参数
find . -name "*.txt" | xargs rm
find . -name "*.log" | xargs -I {} mv {} {}.old
echo "a b c" | xargs -n 1 echo "arg:"

# 安全
find . -name "*.txt" -print0 | xargs -0 rm   # 处理带空格文件名
```

### 2. parallel (GNU Parallel)

```bash
# 并行执行
ls *.txt | parallel -j 4 wc -l

# 远程
parallel -S host1,host2 wc -l {} ::: *.txt
```

### 3. xargs vs parallel

| 工具      | 特点                 |
|-----------|----------------------|
| xargs     | 简单,系统自带        |
| parallel  | 功能强,易用,需安装   |

---

## 十三、核心要点速记

- **Bash 是 Linux 默认 shell**
- **Shebang** = `#!/bin/bash`
- **变量** = `name=value` (无空格)
- **特殊变量**: `$0 $1-9 $# $@ $? $$`
- **引号**:
  - `'$var'` 字面
  - `"$var"` 解释
  - `\$` 转义
- **数组** = `arr=(a b c)`,`${arr[0]}` `${arr[@]}`
- **条件**:
  - `[ ]` 传统
  - `[[ ]]` 增强(推荐)
  - `(( ))` 数值
- **循环**:
  - `for` / `while` / `until`
  - `break` / `continue`
- **case** 多分支
- **函数** = `myfunc() { ... }`,参数 `$1 $2`
- **重定向**:
  - `>` `>>` `<` `2>`
  - `<<EOF` here document
  - `<<<` here string
- **管道** = `|` 串联命令
- **三剑客**:
  - `grep` 搜索
  - `sed` 替换
  - `awk` 字段处理
- **set -euo pipefail** = 严格模式
- **trap** = 信号处理,清理
- **source / .** = 当前 shell 执行
- **export** = 导出环境变量
- **PATH** = 命令搜索路径
- **alias** = 别名
- **history** = 命令历史
- **Ctrl+R** = 历史搜索
- **Tab** = 补全
- **read** = 输入
- **tee** = 同时输出
- **$(cmd)** = 命令替换(推荐)
- **IFS** = 字段分隔符
- **umask** = 默认权限
- **mktemp** = 临时文件
- **chattr +i** = 不可变
- **xargs** = 参数化命令
