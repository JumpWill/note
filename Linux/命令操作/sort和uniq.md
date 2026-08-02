# sort 与 uniq

`sort` 与 `uniq` 是 Linux / Unix 中两个最常用的文本排序 / 去重工具，两者经常组合成流水线。

| 命令 | 作用 |
| ---- | ---- |
| `sort` | 把输入按行排序输出 |
| `uniq` | 把**相邻重复**的行合并，支持去重 / 计次 |

```text
输入 ──► sort ──► uniq ──► 输出
   │          │          │
   │          │          └─ sort -u 其实是 sort 内置 u 选项
   │          └─────────── 相邻去重（必须先 sort 或已按组排列）
   └────────────── 标准输入 / 文件
```

要点先记：

```text
sort 默认按字符字典序，受 LC_ALL 影响
sort -n             按数值
sort -k             按字段 (-k Start[,End][.CharOffset])
sort -t             字段分隔符
sort -u             去重（一遍走）
sort -V             版本号
sort -h             易读（1K 1M 1G）
sort -r             反序
sort --parallel=N   多线程
sort -S / -T        内存 / 临时目录
sort -C / -c        检查是否已排

uniq -c              计次
uniq -d              仅显示重复行
uniq -D              输出所有重复行
uniq -u              仅出现一次的行
uniq -f N            跳过前 N 个字段
uniq -s N            跳过前 N 个字符
uniq -w N            仅比较前 N 个字符
uniq -i              不分大小写
uniq -z              NUL 分隔
```

---

## 1. sort 基础

### 1.1 命令

```bash
sort [OPTION]... [FILE]...
sort [OPTION]... --files0-from=F  # 从 NUL 文件列表读
```

### 1.2 通用选项速查

| 选项 | 含义 |
| ---- | ---- |
| `-r` | 反向 |
| `-n` | 数值 |
| `-h` | 易读（K / M / G） |
| `-V` | 版本号 |
| `-g` | float |
| `-R` | 随机（`--random-source`） |
| `-u` | 去重（行级） |
| `-i` | 忽略非打印 |
| `-f` | 忽略大小写 |
| `-k KEYDEF` | 字段 key 定义 |
| `-t SEP` | 字段分隔符 |
| `-s` | 稳定排序 |
| `-o FILE` | 输出文件 |
| `-c` | 检查是否已排，不一致报错 |
| `-C` | 检查是否已排，不报 |
| `-m` | 合并已排文件 |
| `-T DIR` | 临时目录 |
| `-z` | NUL 分隔 |
| `--parallel N` | 并行（GNU） |
| `-S / --buffer-size` | 缓冲区 |

### 1.3 字段排序

```bash
# 默认整行作 key
sort file

# 按 tab / 空格分割字段（默认）
sort -k2 file

# 第 2 字段从字符 3 开始
sort -k2.3 file

# 范围：第 2 字段从开始到结束（不指定 End 即到行尾）
sort -k2,2 file         # 仅第 2 字段
sort -k2 file           # 第 2 字段起

# 多个 key
sort -k1,1 -k3,3 file
```

KEYDEF 形式：

```text
-k FStart[.CStart][Modifier][,FEnd[.CEnd][Modifier]]

FStart    字段起始位置（如 1、2）
CStart    字段内字符偏移
Modifier  b / d / f / g / h / i / n / r / R / V
FEnd      字段结束位置（默认行尾）
```

例：

```bash
sort -t: -k3n /etc/passwd            # : 分割按 UID 数值排序
sort -k2.4,2.5n -k2.7,2.8n log        # HH:MM:SS 子字段
sort -t. -k1,1n -k2,2n -k3,3n -k4,4n ips
sort -k1,1nr file                     # 第 1 字段按数值反序
sort -k1,1d -k2,2gr file             # 字典 + 数值 + 反序
```

### 1.4 数值排序坑

字典序会把 `1, 10, 100, 2, 3` 排在一起，必须加 `-n`：

```bash
sort -n numbers
sort -t. -k1,1n -k2,2n -k3,3n /proc/loadavg
```

### 1.5 稳定排序

GNU sort 默认是稳定排序（同 key 时保留原输入顺序）。显式 `-s` 保证。

```bash
sort -s -k1,1 -k2,2n file
```

---

## 2. sort 常用例子

### 2.1 基本

```bash
sort file                 # 字典序
sort -r file              # 反序
sort -n numbers.txt       # 数值
sort -u file              # 去重
sort -R file              # 随机
sort -h sizes.log         # 1K 1M 1G
sort -V versions.txt      # 版本号
sort -f file              # 大小写不敏感
```

### 2.2 字段排序

```bash
sort -t: -k3n /etc/passwd | tail                # UID 排序
sort -k3n data.tsv                              # TSV 第 3 数值
sort -k1,1 -k2,2nr data                         # name asc, score desc
sort -t. -k1,1n -k2,2n -k3,3n -k4,4n data.csv  # CSV IP 排序
sort -k1,1n -k2,2M -k3,3n access.log            # log date 字段
sort -k4.2,4.6 access.log                       # 第 4 字段内偏移
sort -m a.txt b.txt c.txt -o all.txt            # 合并
sort -mu a.txt b.txt                            # 合并并去重
```

### 2.3 与 uniq / 输出

```bash
sort file | uniq                 # 去重
sort -u file                     # 一遍去重
sort file | uniq -c              # 计次
sort -k3nr file | head -10       # 取 Top 10
sort file -o file -u             # 原地覆盖
```

---

## 3. locale 与性能

### 3.1 LC_ALL

```bash
LC_ALL=C sort -u big              # 提速、ASCII 顺序
LC_ALL=en_US.UTF-8 sort file     # 字典序
```

`LC_ALL=C` 把"a < A < b < B"按字节（ASCII）排序，否则按 Unicode collation element（不同 locale 顺序不同）。

### 3.2 内存 / 临时空间

```bash
sort -S 4G -T /tmp/large big.txt
sort --buffer-size=1G huge
```

GNU sort 默认溢出到 `/tmp/sort*`，可改 `-T` 到更好位置。

### 3.3 并行

GNU 8+ 多线程：

```bash
sort --parallel=4 file
sort --parallel=$(nproc) file
```

### 3.4 检查是否已排

```bash
sort -C file; echo $?        # 0 = sorted
sort -c file                 # 不是 sorted 报错
```

---

## 4. uniq 基础

### 4.1 命令

```bash
uniq [OPTION]... [INPUT [OUTPUT]]
```

### 4.2 选项

| 选项 | 含义 |
| ---- | ---- |
| `-c` | 计次（行首打印出现次数） |
| `-d` | 仅显示重复行（重复出现 ≥ 2） |
| `-D` | 显示所有重复行（每条都打印） |
| `-u` | 仅出现一次的行 |
| `-i` | 大小写不敏感 |
| `-s N` | 跳过前 N 字符 |
| `-w N` | 仅比较前 N 字符 |
| `-f N` | 跳过前 N 字段（空白分割） |
| `-z` | NUL 分隔 |

### 4.3 工作原理

`uniq` **只比较相邻行**，所以一定要先 sort（或 input 已按 key 排列）。`sort | uniq -c` 是经典的"计次"组合。

---

## 5. uniq 常用例子

### 5.1 基本

```bash
sort file | uniq                 # 去重
sort file | uniq -c | sort -nr | head -10   # Top 10
sort file | uniq -d | wc -l      # 多少重复行
sort file | uniq -u | wc -l      # 多少单独行
sort file | uniq -D               # 全部重复行
sort file | uniq -i              # 不分大小写
```

### 5.2 跳过 / 限宽

```bash
sort file | uniq -f 1            # 跳过第 1 字段
sort file | uniq -w 10           # 只比前 10 字符
sort file | uniq -s 5            # 跳过 5 字符
sort file | uniq -f 1 -w 3       # 跳过 1 字段，再比 3 字符
```

### 5.3 多文件

```bash
cat a.txt b.txt | sort | uniq > merged
sort a.txt b.txt c.txt | uniq -c   # 多文件合并
```

---

## 6. 流水线组合

### 6.1 经典 Top-N

```bash
grep pattern file | sort | uniq -c | sort -rn | head
awk '{print $1}' access.log | sort | uniq -c | sort -rn | head
awk '{print $7}' access.log | sort | uniq -c | sort -rn | head -20
```

### 6.2 与其他工具

```bash
# 抽 ip:port 重复
grep -oE '[\d.]+:[0-9]+' log | sort | uniq -c | sort -rn | head

# PATH 方法统计
cut -d'"' -f2 access.log | sort | uniq -c | sort -rn | head

# 重复轮询 / DDoS 探测
awk '{print $1}' access.log | sort | uniq -c | sort -rn | awk '$1>1000{print}'

# 罕见 / 异常
awk '{print $1}' access.log | sort | uniq -c | sort -n | head
```

---

## 7. access.log 统计访问 IP 次数

### 7.1 标准 combined 格式

```text
192.168.1.10 - - [10/Oct/2024:13:55:36 +0800] "GET /api/users HTTP/1.1" 200 1234 "-" "curl/7.88"
IP 出现在首列，字段按空格分隔。
```

```bash
awk '{print $1}' access.log | sort | uniq -c | sort -rn | head -20
```

输出：

```text
   3421 192.168.1.10
   2890 10.0.0.5
   1234 192.168.1.20
       12 192.168.1.30
```

### 7.2 自定义 `IP:xxxx` 格式

```text
IP:192.168.1.10 - - [10/Oct/2024:13:55:36 +0800] "GET /api/users HTTP/1.1" 200 1234 "-" "curl/7.88"
IP:10.0.0.5 - - [10/Oct/2024:13:55:37 +0800] "POST /api/orders HTTP/1.1" 201 567 "-" "k6/0.45"
IP:192.168.1.10 - - [10/Oct/2024:13:55:38 +0800] "GET /api/products HTTP/1.1" 200 89 "-" "curl/7.88"
```

取出 IP 段并统计：

```bash
# 1) 剥掉前缀
awk '{print $1}' access.log | grep -Eo '^IP:[0-9.]+' | sed 's/^IP://' \
  | sort | uniq -c | sort -rn | head -20

# 2) 直接按 "IP:1.2.3.4" 整段计次
awk '{print $1}' access.log | sort | uniq -c | sort -rn | head -20
```

输出：

```text
   3421 IP:192.168.1.10
   2890 IP:10.0.0.5
   1234 IP:192.168.1.20
```

### 7.3 巨型日志 / 子网聚合

```bash
# 提速
LC_ALL=C awk '{print $1}' access.log | sort | uniq -c | sort -rn | head

# 按子网（前三段）
awk '{print $1}' access.log \
  | sed -E 's/^IP:([0-9]+)\.([0-9]+)\.([0-9]+)\..*/\1.\2.\3/' \
  | sort | uniq -c | sort -rn | head -10
```

### 7.4 Top 1000 + 占比

```bash
awk '{print $1}' access.log \
  | sort | uniq -c | sort -rn | head -1000 \
  | awk 'BEGIN{while ((getline line < "access.log") > 0) all++; close("access.log")}
         {printf "%-22s 访问 %8d 次  ( %.3f%% )\n", $2, $1, $1*100/all}'
```

### 7.5 排除内部 IP / 健康检查

```bash
INTERNAL_IP="192.168.|10.0.0."

awk '{print $1}' access.log \
  | grep -Ev "^(${INTERNAL_IP})" \
  | sort | uniq -c | sort -rn | head -20
```

### 7.6 仅 `/api` 路径

```bash
awk '$7 ~ /^\/api/ {print $1}' access.log \
  | sort | uniq -c | sort -rn | head
```

### 7.7 按小时 + IP 趋势

```bash
awk '{
  split($4, a, ":")
  hour = a[2]
  ip   = $1
  cnt[hour"|"ip]++
}
END {
  for (k in cnt) print cnt[k], k
}' access.log | sort -rn | head -20
```

```text
 98 13|192.168.1.10
 87 14|10.0.0.5
```

### 7.8 异常高频 IP（DDoS 推断）

```bash
THRESHOLD=100

awk '{print $1}' access.log \
  | sort | uniq -c \
  | awk -v t=$THRESHOLD '$1 > t' \
  | sort -rn
```

### 7.9 时间窗口（5 分钟）

```bash
awk '{
  sec=$4
  gsub(/\[/, "", sec); gsub(/:/, " ", sec); split(sec, t, " ")
  epoch=mktime(t[1]" "t[2]" "t[3]" "t[4]" "t[5]" "t[6]) - 300
  if ($1 == lastip && sec >= start && sec <= start + 300) {
    cnt[$1]++
  } else {
    start=epoch; lastip=$1; cnt[$1]=1
  }
}
END {for (k in cnt) print cnt[k], k}' access.log | sort -rn | head
```

### 7.10 转 JSON（jq 配合）

```bash
awk '{print $1}' access.log \
  | sort | uniq -c | sort -rn \
  | awk 'BEGIN{printf "[\n"}
        {printf "%s{\"count\": %d, \"ip\": \"%s\"}\n", sep, $1, $2; sep=","}
        END{print "]"}' \
  | jq .
```

---

## 8. 性能优化

### 8.1 一遍 vs 两遍

```bash
sort file | uniq > u.txt    # 两遍
sort -u file > u.txt        # 一遍，更快
```

### 8.2 内存 + 临时目录

```bash
LC_ALL=C sort --parallel=$(nproc) -S 8G -T /large_disk huge.txt
```

### 8.3 性能调优维度

| 选项 | 作用 |
| ---- | ---- |
| `LC_ALL=C` | 跳过 locale 比较 |
| `-S N` | 内存预算 |
| `-T DIR` | 临时目录要快 |
| `--parallel=N` | 多线程 |
| `-u` | 一遍去重 |
| `-m` | 已排文件不再排序 |

### 8.4 shuf

```bash
shuf file                     # 类似 sort -R
shuf -n 100 file              # 抽 100 行
shuf -e a b c                 # 直接重排参数
```

---

## 9. 跨平台

| 选项 | GNU | BSD / macOS |
| --- | --- | --- |
| `-V` | ✔ | ❌ |
| `-h` | ✔ | ❌ |
| `-R` | ✔ | ❌ |
| `-s` | ✔ | ❌ |
| `--parallel` | ✔ | ❌ |
| `-z` | ✔ | ✔ |
| `-k` | ✔ | ✔ |

macOS 装 coreutils 拿 GNU：

```bash
brew install coreutils
gln /usr/local/opt/coreutils/bin/sort ...
```

---

## 10. 一句话总结

```text
sort = 字典 / 数值 / 版本 / Locale 排序
uniq = 相邻行去重（必须先 sort 或按 key 排好）
sort -u         = sort + uniq 一遍走 + 去重
pipeline: sort | uniq -c | sort -rn | head    # Top-N
access.log IP: sort | uniq -c | sort -rn      # Top IP
```

---

## 11. 参考

- `man sort`
- `man uniq`
- `info coreutils sort`
- [GNU coreutils - sort](https://www.gnu.org/software/coreutils/manual/html_node/sort-invocation.html)
- [POSIX sort](https://pubs.opengroup.org/onlinepubs/9699919799/utilities/sort.html)
