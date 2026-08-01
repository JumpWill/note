# awk

字段驱动 + 脚本化 + 文本处理 / 报告生成三位一体。Linux 文本三剑客之"最强大的一个"。可看作简化版脚本语言。

变体：

| 名称 | 含义 |
| ---- | ---- |
| `awk` / `gawk` | GNU awk（Linux 默认） |
| `mawk` / `nawk` | 精简版 / new awk |
| 标准参考 | POSIX awk |

## 1. 基本形状

```text
awk 'program' file
awk -f script.awk file
```

```text
awk 'BEGIN{...} /pattern/{action} END{...}'
   ▲         ▲              ▲
   启动        模式（选）       动作
```

每个周期：

1. `BEGIN` 块执行一次
2. 每行读入
3. 若匹配 `/pattern/`，运行 action
4. 读完文件后 `END` 块执行一次

## 2. 内置变量

| 变量 | 含义 |
| ---- | ---- |
| `$0` | 整行 |
| `$1..$NF` | 字段 |
| `NF` | 字段数（最后一个字段是 `$NF`） |
| `NR` | 当前行号（多文件累加） |
| `FNR` | 当前文件内行号 |
| `FS` | 输入字段分隔符（默认空白） |
| `RS` | 输入记录分隔符（默认 `\n`） |
| `OFS` | 输出字段分隔符（默认空格） |
| `ORS` | 输出记录分隔符（默认 `\n`） |
| `FILENAME` | 当前文件名 |
| `ARGC / ARGV` | 命令行参数计数 / 数组 |
| `ENVIRON` | 环境变量关联数组 |
| `RSTART / RLENGTH` | match 位置 |
| `PROCINFO` | 进程信息（GNU） |
| `FNR` | 当前文件行号 |

修改分隔符：

```awk
BEGIN{FS=":"}
BEGIN{FS=","; OFS="\t"}
BEGIN{FS="\t"}
```

## 3. 命令行

```bash
awk '...' file                          # 直接
awk -F: '...' /etc/passwd               # 指定分隔符
awk -v var=42 'BEGIN{print var}' file   # 变量
awk -f prog.awk file                    # 脚本文件
gawk --lint '...' file                  # lint 警告
awk -W traditional '...' file           # 老 awk
```

## 4. 模式 (Pattern)

| 形式 | 含义 |
| ---- | ---- |
| `/regex/` | 匹配 |
| `BEGIN / END` | 启动 / 收尾 |
| `BEGINFILE / ENDFILE` | (gawk) |
| `expr` | 表达式（非 0 字符串非空则匹配） |
| `nr==5` 等 | 比较 |
| `NR>10 && NR<20` | 复合条件 |
| `next` | 跳过本行 |
| `exit` | 退出 |

正则：

```awk
/error/                 { print $0 }
/^(From|Date):/          { print $1 }
```

## 5. 动作 (Action)

```awk
{ print $1, $NF }
{ print NR, $0 }
{ printf "%-15s %5d\n", $1, $2 }
{ sum += $3 }                     # 累计
{ count[$1]++ }                   # 关联数组
```

输出格式化：

```awk
printf "%d %s = %.3f\n", NR, $1, $3 / 100
```

## 6. 内置函数

### 6.1 字符串

| 函数 | 功能 |
| ---- | ---- |
| `length(s)` | 长度 |
| `substr(s, m, n)` | 切片 |
| `index(s, t)` | 起始位置 |
| `match(s, re)` | re 起始位置（RSTART / RLENGTH） |
| `sub(re, repl, s)` | 首处替换 |
| `gsub(re, repl, s)` | 全部替换 |
| `split(s, a, sep)` | 切字段入数组 |
| `sprintf(fmt, args)` | 格式化 |
| `toupper(s) / tolower(s)` | 大小写 |

### 6.2 数值

| 函数 | 功能 |
| ---- | ---- |
| `int(x)` | 取整 |
| `sqrt(x)` | 平方根 |
| `sin / cos / atan2` | 三角 |
| `rand()` / `srand(x)` | 伪随机 |
| `log / exp` | 指数对数 |

### 6.3 其他

| 函数 | 功能 |
| ---- | ---- |
| `system(cmd)` | 跑 shell |
| `getline` / `getline x` | 读下一行 |
| `close(f)` | 关闭文件 |
| `mktime / strftime / systime` | 时间 |

## 7. 数组

```awk
BEGIN{
  for(i=0;i<10;i++) a[i]=i*i
  print a[3]
}
delete a[1]
for(k in a) print k, a[k]
```

关联数组（哈希）：

```awk
END{
  for (ip in count) print ip, count[ip]
}
```

判断键存在：

```awk
if (key in arr) ...
```

## 8. 控制流

```awk
if (NR > 10) ...
while (i < 10) {i++; ...}
for (i=0;i<10;i++)
for (k in arr)        # 关联数组
do { ... } while (...)
```

## 9. 自定义函数

```awk
function add(a, b) { return a + b }
```

gawk 函数可以传"引用变量"：

```awk
function inc(p,    v){v=p+1; p=v}   # 默认是值
```

## 10. 实战例子

### 10.1 字段提取

```bash
awk '{print $1, $3}' file                 # 字段 1 和 3
awk '{print $NF}' file                    # 末字段
awk '{print $(NF-1)}' file                # 倒数第二
awk '$2 ~ /^[0-9]/' file                  # 第二个匹配数字
```

### 10.2 累加 / 求和

```bash
awk '{sum+=$1} END{print sum}' file
awk '{sum+=$1; count++} END{print sum/count}' file   # 平均
```

### 10.3 计数

```bash
awk '/error/{c++} END{print c}' log
awk '/DEBUG|INFO|WARN|ERROR/{c[$1]++} END{for (k in c) print k, c[k]}' log
```

### 10.4 /etc/passwd 加工

```bash
awk -F: '{print $1}' /etc/passwd                       # 用户名
awk -F: '$3<1000' /etc/passwd                          # 系统账户
awk -F: '{printf "%-15s uid=%s\n", $1, $3}' /etc/passwd
```

### 10.5 日志分析

```bash
# nginx access.log 字段：remote - - time req stat size ...
awk '{print $7}' access.log                            # URL
awk '{sum+=$10; c++} END{print sum/c, "bytes avg"}'    # 平均 size
awk '$9 ~ /^[45]/ {print $7, $9}'                      # 4xx/5xx URL
awk -F'"' '$6 ~ /Mozilla/ {c["browser"]++} END{for(k in c) print k,c[k]}'
```

### 10.6 字段分隔

```bash
awk -F: '{print $1":"$2}' file                        # 改输出分隔
awk -F'\t' '{OFS="|"; print $1,$2,$3}'                # 输出指定分隔
awk -F, 'NF > 0' csv                                  # 至少一字段
awk 'BEGIN{FS=","}{print NF}' csv                     # 每行 字段数
```

### 10.7 数据列重排

```bash
awk '{print $2, $1}' file                             # 交换两列
awk '{for(i=NF;i>0;i--) printf "%s%s",$i,(i==1?ORS:OFS)}' file
                                                         # 反向字段
```

### 10.8 `getline` 跨行

```awk
{
    if ((getline nxt) > 0) {
        print "current:", $0, "next:", nxt
    }
}
```

### 10.9 处理 / 分组

```bash
awk 'BEGIN{print "=== START ==="} /2024/{print} END{print NR}' log

# 按 session 归并
awk '/START/{session=$0} /END/{print session, $0}' trace.log

# 多表合并
awk '{count[$1]++; size[$1]+=$2} END{for (k in count) print k, count[k], size[k]/count[k]}' file
```

### 10.10 监控 / 统计

```bash
# 每秒钟不同 IP 计数
awk '{count[$1]++} END{for (k in count) print k, count[k]}' access.log | sort -k2 -rn | head

# 滑动窗口
awk 'NR>30 {count[$1]=count[$1]-cnt[NR-30]} {count[$1]++} END{...}' file

# 区间统计（按小时聚合）
awk '{hour=substr($4,2,14)":00:00"; sum[hour]+=$NF; cnt[hour]++} END{for (k in sum) print k, sum[k]/cnt[k]}' json.log
```

### 10.11 CSV 重整

```bash
# 调字段顺序
awk -F, 'BEGIN{OFS="|"} {print $3, $1, $2}' data.csv

# 含逗号的字段（带 quote）
awk -F',"' '{print substr($2, 1, length($2)-1)}' data.csv
```

### 10.12 数值化 / 过滤

```bash
awk '$1>100' data                      # 第一列 > 100
awk 'NR%2==0' file                     # 偶数行
awk 'NF>=3' file                       # 至少 3 字段
awk 'length($0)>80' log                # 长行
```

### 10.13 多文件处理

```bash
awk 'FNR==1 {print FILENAME}' *.log    # 每个文件开头打印名字
awk 'FNR==1 && NR>1 {print "=="}' *.log
```

### 10.14 统计 / 直方图

```bash
awk '{bucket=int($1/10)*10; cnt[bucket]++} END{for(k=0; k<=100; k+=10) printf "%3d: %s\n", k, (k in cnt)?cnt[k]:"0"}' file
```

### 10.15 awk 跑 SQL-style 查询

```awk
# where + group by 模拟
$3 ~ /^public/ {cnt[$7]++}
END {
    for (k in cnt) print cnt[k], k
} | sort -rn
```

### 10.16 shell 接口：subprocess

```awk
{ "date" | getline d; print $0, d; close("date") }
```

### 10.17 自定义函数

```awk
function median(arr,    n, i) {
    n = length(arr)
    return (n % 2) ? arr[int(n/2)] : (arr[n/2 - 1] + arr[n/2]) / 2
}
```

### 10.18 拆分多行记录

```awk
BEGIN { RS="\n\n" }                    # 段间空行
{                                       # 一段 = 一记录
    print "RECORD", NR
    print
}
```

### 10.19 计算相位 / 状态累计

```awk
{ if ($1 == "TIME") total += $2 }
```

### 10.20 文本中提取 URL

```bash
grep -oE 'https?://[^"<> ]*' page.html | awk '{print length($0), $0}' | sort -rn | head
```

### 10.21 文件的字段统计

```bash
awk -F'|' '{
    # 统计每行字段数分布
    c[NF]++
} END {
    for (n in c) print n, c[n]
}' data.txt
```

### 10.22 多表 join

```awk
BEGIN { FS="," }
FNR==NR { A[$1]=$2; next }
{ print $0, ($1 in A) ? A[$1] : "???" }
```

### 10.23 模拟 awk 内建选择

```bash
awk 'BEGIN{srand(); for (i=0;i<5;i++) print rand()}' file
awk 'BEGIN{for(i=1;i<=12;i++) printf "%-8s %d\n", "month="i, 31*86400*int((1+sin(i))) }'
```

### 10.24 解析 JSON 行

```bash
awk -F'"' '
    /"user_id":/   {uid=$4}
    /"action":/    {action=$4}
    /"duration":/  {dur=$4}
    /}/ {print uid, action, dur; uid=""; action=""; dur=""}
' jsonl.log
```

### 10.25 轮转上报

```bash
tail -F /var/log/app.log | awk '{ if (/ERROR/) print }' | head -100 | mail -s "errors" admin@corp
```

## 11. gawk 与 awk 的差别

| 特性 | POSIX awk | gawk |
| --- | -------- | ---- |
| 中文 encoding | 弱 | 强（内置 unicode 支持） |
| 网络 I/O | ❌ | ✔ `/inet/` |
| 数据库绑定 | ❌ | ✔ gawk-pm |
| 调试 | ❌ | ✔ `--profile` / `--debug` |
| ICU | ❌ | ✔ unicode-aware |
| 异步 / 协程 | ❌ | （受限） |

`awk --profile out=p.prof '...' file` 输出执行次数。

## 12. 性能

- `LC_ALL=C` 提高字段匹配速度
- 二维/多维数组可使用 gawk 哈希优势
- 排序用外部 `sort`；awk 自带 sort 函数较慢
- 用 `mawk`：轻而快；`gawk`：强而相对慢

## 13. 与其它工具分工

| 场景 | 工具 |
| ---- | ---- |
| 单行 grep 替代 | grep -E |
| 字段提取 + 计算 | awk |
| 替换 / 改写 | sed / perl |
| 列模式编辑 | column |
| 表格内容截取 | cut |
| 排序去重 | sort / uniq |
| 数据 → JSON | jq |
| 文件 / 目录 | find |

组合：

```bash
grep pattern file | awk '{print $1}' | sort | uniq -c | sort -rn | head
```

## 14. 一句话总结

```text
awk = 字段 + 模式 + 动作
$1/$NF 来取字段，printf 格式化输出
END{print sum/count} 算平均
BEGIN{FS=","} 改分隔符
```

## 14. 更多实战例子

### 14.1 nginx / apache 访问日志

```bash
# Top 10 URL（按请求数）
awk '{print $7}' access.log | sort | uniq -c | sort -rn | head

# 5xx 状态码 URL + 错误次数
awk '$9 ~ /^5[0-9][0-9]$/ {print $7, $9}' access.log | sort | uniq -c | sort -rn | head

# Top 10 Client IP
awk '{print $1}' access.log | sort | uniq -c | sort -rn | head

# 4xx / 5xx 的响应时间分布（P95、P99）
awk '$9 ~ /^[45]/ {print $NF}' access.log | sort -n | awk 'BEGIN{c=0}{a[c++]=$1}END{printf "p50=%d p95=%d p99=%d\n", a[int(c*0.5)], a[int(c*0.95)], a[int(c*0.99)]}'

# 总字节 / 平均响应字节
awk '{b+=$10} END{printf "%d bytes (%.2f MB)\n", b, b/1048576}' access.log

# 按小时聚合
awk '{h=substr($4,2,13)":00:00"; cnt[h]++; sum[h]+=$NF} END {for (k in cnt) print k, sum[k]/cnt[k]}' access.log
```

### 14.2 数据库 / MySQL 慢查询

```bash
# 出现最多次的 query
awk '/Query_time/{getline; print}' slow.log | sort | uniq -c | sort -rn | head

# Top 10 最慢 query
awk '/Query_time/{q=$2; getline; print q, $0}' slow.log | sort -rn | head

# query 聚合时间
awk '/Query_time:/{sum+=$3; cnt++} END {print "Avg:", sum/cnt}' slow.log
```

### 14.3 /etc/passwd / 配置 / ETL

```bash
# passwd 第一列 + UID
awk -F: '{printf "%-20s uid=%s gid=%s shell=%s\n", $1, $3, $4, $7}' /etc/passwd

# 找出 UID 大于 1000 的用户
awk -F: '$3 >= 1000 {print $1, $3}' /etc/passwd

# 查找空值（missing 字段）
awk -F: 'NF < 7' /etc/passwd

# 打印 shell 不存在的 user
awk -F: '$7 !~ /^(\/|\/bin\/|\/usr)/ {print $1, $7}' /etc/passwd

# 取组名
awk -F: '$1 == "mysql" {print $4}' /etc/group
```

### 14.4 系统监控 / ps / top

```bash
# ps 中某个进程 cpu + rss
ps aux | awk '/nginx/ {sum+=$4; rss+=$6} END {printf "CPU=%.1f%% RSS=%.0f MB\n", sum, rss/1024}'

# 内存使用 Top 5
ps -eo comm,rss | awk '{rss[$1]+=$2} END {for (k in rss) print rss[k]/1024, k}' | sort -rn | head

# 借用 awk 取网卡流量
awk '/eth0/ {rx+=$2; tx+=$10} END {printf "RX=%d MB TX=%d MB\n", rx/1024, tx/1024}' /proc/net/dev
```

### 14.5 JSON 行处理

```bash
# 用 awk 简易抽取 JSON field
awk -F'"' '/"user_id"/{u=$4} /"action"/{a=$4} /}/{print u, a}' jsonl

# 多事件 JSONL 提取某一字段（gawk 多字段）
gawk -F: '/user_id/{u=$NF} END{print u}' jsonl

# 数值聚合（gawk）
gawk 'match($0, /"duration": *([0-9.]+)/, m) {sum += m[1]; cnt++} END {printf "avg=%.3f, count=%d\n", sum/cnt, cnt}' jsonl
```

### 14.6 大数据计算 / 窗口聚合

```bash
# 间隔平均值
awk 'NR>5{sum+=$1; if(NR%10==0){print NR, sum/10; sum=0}}' data

# 滑动平均（5 个一组）
awk '{a[NR%5]+=$1; if(NR>=5) printf "%d %.2f\n", NR, (a[0]+a[1]+a[2]+a[3]+a[4])/5}' data

# 中位数
awk '{a[NR]=$1; if(NR%10000==0) print NR}
END {
  asort(a); n=asorti(a);
  print a[int(n/2)]
}' data
```

### 14.7 排序 / 排名

```bash
# Top N 最大行
awk 'NR>1{if ($2 > max) {max=$2; row=$0}} END {print row}' data

# 字典序排名
awk 'NR>1{print $1}' data | sort | uniq -c | sort -k2

# 计算 percentile
gawk 'BEGIN{for(i=1; i<1000; i++) a[i]=rand();} {asort(a)} END {print a[950], a[990]}'
```

### 14.8 报表 / 表格

```bash
# 简单表格
awk 'BEGIN{print "User", "UID", "Shell"}
     FS=":"
     {printf "%-15s %5d %s\n", $1, $3, $7}
     END {print "Total:", NR, "users"}' /etc/passwd

# 简单柱状图
awk '{cnt[$1]++} END {for (k in cnt) print k, cnt[k], "|", substr("##########", 1, int(50*cnt[k]/NR))}' file
```

### 14.9 多文件 / 多列合并

```bash
awk 'FNR==1{print FILENAME}' *.log                       # 每文件首行打名字

# 多文件合并输出
awk '{print FILENAME, $0}' a.log b.log c.log

# 两个 CSV 按共同 key join
awk -F, 'FNR==NR{left[$1]=$2; next} {print $0, left[$1]}' 1.csv 2.csv

# 显示一行中出现的最大数
awk 'BEGIN{IGNORECASE=1} {for (i=1; i<=NF; i++) if ($i+0 > max) max=$i} END {print max}' data
```

### 14.10 子进程 / 外部命令

```bash
# 调 shell 转码
awk '{system("date -d @"$2" +%FT%T")}' file

# pipe into external
awk 'BEGIN{while (("ls" | getline line) > 0) print line}'

# 计算时间间隔
awk '/start/{s=$NF} /end/{print "duration: "(($2-s)/100)"sec", $NF}' log
```

### 14.11 gawk 扩展（适用 GNU）

```bash
# 大小写不敏感匹配
gawk 'BEGIN{IGNORECASE=1} /AUTH/' log

# asort 系列
gawk '{a[NR]=$0} END{asort(a); for (i=1; i<=10; i++) print a[i]}' data

# 高级匹配
gawk 'match($0, /(foo)(bar)?/, m){print m[1], m[2]}'

# 自带 read & write to file
gawk 'BEGIN{print "header" > "out"} {print NR, $1 >> "out"} END{close("out")}' file
```

### 14.12 awk + shell 联合

```bash
# awk 内的 var 暴露
awk -v name=$1 '{cnt[name]++} END{for(k in cnt) print k, cnt[k]}' files

# 运行多应用 awk 处理
export LC_ALL=C
awk 'BEGIN{srand()} {key=$1; sum[key]+=$2; cnt[key]++}
     END{for (k in cnt) printf "%-15s count=%4d avg=%.2f\n", k, cnt[k], sum[k]/cnt[k]}' data
```

### 14.13 logging / monitoring / prometheus exporter

```bash
# awk 直接输出 Prom metrics
awk -v n=$(hostname) '
{
  metric=gensub(/^([^ ]+).*/, "\\1", $1)
  count[metric]++
}
END{
  for (k in count) printf "app_metric_%s_total %d\n", k, count[k]
}' app.log

# 简单的告警：平均负载 > n
uptime | awk -F, '{print $(NF-2), $(NF-1), $NF}' | \
  awk '$1>4||$(NF-1)>2 {print "overload"}'

# 多行统计 → 转 JSON
awk 'BEGIN{printf "["} { ... } END{printf "]"}' | jq .
```

### 14.14 文本数据 → 二进制

```bash
# hex 输出
awk 'BEGIN{print "0123456789ABCDEF"; print "\n"} {h=sprintf("%04x\n", strtonum("0x"$0)); print}' data

# 进制转化
awk 'BEGIN{printf "%d\n", strtonum("0xff")}'        # 255
```

### 14.15 模式匹配 / 字符串处理

```bash
# 正则抽取字段
awk '{
  for(i=1;i<=NF;i++) {
    if (match($i, /[0-9]+/, m)) printf "%d ", m[1]
  }
  print ""
}' log

# 列名 / JSON key 重组
awk '/"kpi":/{gsub(/[":]/,""); print}' jsonl

# 抽取中文字
awk 'BEGIN{IGNORECASE=0} {gsub(/[一-龥]/, " "); print}' file | head
```

### 14.16 awk user-defined DBF 查询

```bash
# awk + sqlite
awk -v q="SELECT * FROM users LIMIT 10" '
BEGIN{
  cmd="sqlite3 db.sqlite \"" q "\""
  while ((cmd | getline row) > 0) {
    print row
  }
  close(cmd)
}'
```

### 14.17 真实生产中的例子

```bash
# 系统 OS / 版本
awk '/^NAME=/ {sub(/"/,""); print $1}' /etc/os-release
awk -F'=' '/^VERSION_ID/ {print $2}' /etc/os-release

# 拆装 IP
awk -F. '/^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+/{
  print "class A: "$1, "B: "$2, "C: "$3, "D: "$4
}' ips.log

# nginx 转 openresty 配置
awk -F: '/lua_shared_dict|lua_socket/ {printf "lua_%-20s %s;\n", $1, $2}' conf

# 备份文件输出
awk '{out=$0; gsub(/[ \/]/,"_"); print tolower($0) > "/tmp/out/" $0}' filelist

# 随机抽样
gawk 'BEGIN{srand()} rand() < 0.1' huge > sample
```

## 15. 参考

- `man awk`
- `man gawk`
- `info gawk`
- [Effective AWK Programming](https://www.gnu.org/software/gawk/manual/)（经典）
- [awk.dev](https://awk.dev)
- [Aho/Kernighan/Weinberger "The AWK Programming Language"](https://en.wikipedia.org/wiki/The_AWK_Programming_Language)
