# sed

流式编辑器（Stream Editor），按规则对输入流（文件 / stdin）做"逐行处理 + 转"的修改，最终写到 stdout。擅长批量替换、删除 / 插入、迁移、打印指定行。标准在 GNU sed 与 BSD sed 之间基本一致。

```text
input ──► pattern space ──► 输出
   │           │
   │           ▼
   └──── hold space（保留区）
```

每个周期：读一行 → 放到 pattern space → 跑脚本 → 把结果写到 output → 循环。

## 1. 命令行

```text
sed [OPTIONS]... {script-only-if-no-other-script} [input-file]...
```

| 选项 | 含义 |
| ---- | ---- |
| `-n / --quiet / --silent` | 不自动打印模式空间 |
| `-e SCRIPT` | 多脚本 |
| `-f FILE` | 脚本从文件来 |
| `-i[SUFFIX]` | 直接编辑文件，可备份（`-i.bak` 备份到 `*.bak`） |
| `-E / -r` | 扩展正则（ERE） |
| `-l` | 输出"行-N"格式 |
| `-u` | 取消缓冲区 |
| `-z` | NUL 终止行 |
| `-i` 备份 | `sed -i.bak 's/x/y/' file` 留原文件 |

## 2. 地址（pattern_addr）

把脚本作用于"哪些行"。

```text
sed '<addr><!><command>'
```

| 地址 | 含义 |
| ---- | ---- |
| `n` | 单行 |
| `$` | 最后一行 |
| `m,n` | 第 m 到第 n 行（n>m）；逗号后加 `~` 步长 |
| `m~n` | 第 m 行起，每个 n |
| `/regex/` | 匹配行（基本正则） |
| `m,/X/` | 从 m 到第一个 X |
| `/X/,/Y/` | X 到 Y 之间（含） |
| `0,/X/` | 顶到 X（注意 0 含 1 行前） |

否定：在地址前加 `!`：`sed -n '/error/!p'` 只输出非 error。

## 3. 命令（commands）

常用：

| 命令 | 含义 |
| ---- | ---- |
| `p` | 打印模式空间 |
| `d` | 删除（到下个周期） |
| `q` | 退出 |
| `Q N` | 退出码 N |
| `n` | 读下行 |
| `N` | 当前行 + 下一行 join |
| `y/in/out` | 字面字符转换 |
| `s/PAT/REPL/[flags]` | 替换 |
| `=`, `a\TEXT`, `i\TEXT`, `c\TEXT` | 行号、追加、插入、改写 |
| `r FILE` / `w FILE` | 读 / 写 |
| `l` | 可视化 |
| `l label` / `b label` / `t label` | 标签 / 跳转 / 条件跳 |
| `g / G / h / H / x` | hold space 互换 |

替换 flags：

| flag | 含义 |
| ---- | ---- |
| `g` | 全行 replace（不止第一处） |
| `i` | 大小写不敏感 |
| `I` | 大小写不敏感（GNU） |
| `p` | 替换后打印 |
| `w FILE` | 替换后写文件 |
| `N` | 行号 |
| `e` | shell 命令 |

## 4. 替换 s/PAT/REPL/

### 4.1 基本

```bash
sed 's/foo/bar/'                  # 每行第 1 个 foo → bar
sed 's/foo/bar/g'                 # 一行所有
sed 's/foo/bar/2'                 # 仅第 2 个
sed 's/foo/bar/2g'                # 第 2 起全部
sed -E 's/(foo)(bar)/\2\1/'       # ERE 引用
sed 's/foo.c/& pass/'             # & = 匹配本身
```

### 4.2 大小写

```bash
sed 's/foo/[&]/I'                 # 忽略大小写
sed 's/(foo)/\L\1\E/'             # \L 转小写，\E 终止
sed 's/(foo)/\U\1/'               # 转大写
sed 's/(foo)/\u\1/'               # 首字母大写
```

### 4.3 字面 / 字符类

```bash
sed 's/:/=42/'                   # 单字符
sed 's/[[:digit:]]+/N/g' file    # POSIX 类
sed 's/\t/  /g' file            # tab
```

### 4.4 行内换行

GNU sed：

```bash
sed 's/foo\nbar/baz&/' file      # 含 \n（GNU）
sed -z 's/o\nb/x\ny/g' file      # -z 把多行合一输入
```

## 5. 实战例子

### 5.1 替换 + 删除

```bash
sed 's/old/new/g' file                    # 默认输出到 stdout
sed -i 's/old/new/g' file                  # 原地修改
sed -i.bak 's/old/new/g' file              # 备份 .bak
sed 's#/old/dir#/new/dir#g' file           # 改分隔符
sed 's#/etc/#/etc/nginx/#g' file           # 路径替换
```

### 5.2 行删除

```bash
sed -i '/^#/d' file                       # 删除 # 起首行
sed -i '/^$/d' file                        # 删空行
sed -i '/^[[:space:]]*$/d' file           # 含空白的空行
sed '/DEBUG/d' file                       # 删 DEBUG 行
sed '/^from:/,/^----/d' mail              # 删邮件正文
```

### 5.3 行插入 / 追加

```bash
sed -i '/pattern/a NEW_LINE' file         # 在匹配后插入
sed -i '/pattern/i BEFORE_LINE' file      # 在匹配前插入
sed -i '5i HEADER' file                   # 第 5 行前插
sed -i '$a END' file                      # 末行后插
```

GNU 多行：

```bash
sed -i '/pattern/c\REPLACE_CONTENT' file  # 替代匹配行
sed -i '5c\NEW BODY' file                 # 第 5 行被整段替代
```

### 5.4 重新格式化输出

```bash
sed -n '5,10p' file                       # 5 至 10 行
sed -n '/start/,/end/p' file              # start 到 end
sed -n '/2024-01/p' log                   # 含 2024-01
```

### 5.5 单行多 command

```bash
sed 's/foo/bar/; /^[ ]*#/d' file
```

-n 与 p：

```bash
sed -n '/error/{p; q;}' log              # 第一个 error 后退出
```

### 5.6 多文件

```bash
sed -i.bak 's/old/new/' *.go
sed -n 's/.* (\(.*\))/\1/p' *.conf       # 每文件加文件名
```

加文件名：

```bash
sed "s/.*/$(basename file): &/" file
```

### 5.7 注释 / 添加行号

```bash
sed 's/^/  /' file                       # 每行加两空格
sed 's/^/  /; 10,$s/^  /##/' file        # 部分单段
sed '=' file | sed 's/^/=== /'            # 行号
sed 's/$/\r/' file                       # 改行尾
```

### 5.8 操作路径替换

```bash
sed -i 's|/usr/local|/opt|g' file
```

避免反斜杠转义。

### 5.9 找配置文件改 key

```bash
sed -i 's/^#\?\(max_connections = \).*/\11000/' /etc/mysql/my.cnf
```

### 5.10 改网段

```bash
sed -i 's/192.168.1./10.0.0./g' /etc/hosts
```

### 5.11 删某行 + 整行替代

```bash
sed -i '/Type=DNS-SD/c Type=AAAA' file
sed '/^somekey=/c somekey=value' app.conf
```

### 5.12 简单脚本（-f）

```text
# /tmp/script.sed
s/^/   /
$a\=== end ===
```

```bash
sed -f /tmp/script.sed input
```

### 5.13 多次替换为一行输出

```bash
echo "Hello   World" | sed -e 's/\s\+/ /g' -e 's/^/>>> /'
```

### 5.14 删除 HTML 标签

```bash
sed -E 's/<[^>]+>//g' page.html
sed -E 's/<script.*<\/script>//g' page.html
```

### 5.15 反转行 / 列

```bash
# 反转行
sed '1!G;h;$!d' file      # tac

# 反转每行
sed -E 's/[^\n]/\0/g' file
sed 'n;p;d' file         # 错位输出
```

### 5.16 与 awk 配合

```bash
sed -n '1,100p' file | awk '{print $1}'
```

### 5.17 多个文件 xargs

```bash
git grep -l 'old_term' | xargs sed -i 's/old_term/new_term/g'
```

### 5.18 行内 delimiter 转换

```bash
sed 's/=/\t/g' csv                       # → 表格
sed 's/,/\t/g' csv                       # 表格
```

### 5.19 过滤注释 / 空行 + 展开

```bash
sed -E '/^#|^$/d' app.conf               # 注释 / 空行
sed -E '/^$/d; /^#/d; s/[ \t]+/ /' file  # trim + 去掉注释
```

### 5.20 sed + environment

```bash
PASS=$(echo "$URL" | sed -E 's|.*://([^/]*).*|\1|')
```

### 5.21 字符串操作

```bash
echo "$var" | sed 's/[1-9]\+/N/g'        # 数字 → N
echo "$line" | sed 's/^[[:space:]]*//'   # trim leading
echo "$line" | sed 's/[[:space:]]*$//'   # trim trailing
```

### 5.22 数据清洗：替换双引号 / 反引号

```bash
sed -i 's/&quot;/"/g; s/&amp;/\&/g; s/&lt;/</g; s/&gt;/>/g' file
```

### 5.23 多脚本

```bash
sed -e '/^#/d' -e 's/foo/bar/g' file
sed -e 's/^/> /' -e 's/$/ < /' file
```

### 5.24 标签 / 流程控制

```text
:label
  cmd
b label

t label       (上一次替换成功后跳转)

# 加 sed 模拟循环
:loop
  s/foo/bar/
t done
b loop
:done
```

如简单计算：

```bash
sed ':a; s/  / /g; ta' file             # 重复合并多空格
```

`ta` 表示替换成功后再跳转。

### 5.25 数据切片

```bash
sed -n '100,200p' access.log > slice.log
sed -n '1,50!p'                      # 跳过前 50 行
sed -n 'NR==1{n;p}'                 # 第一行
```

### 5.26 中文 / 编码处理

```bash
iconv -f gbk -t utf-8 file | sed 's/中文/CHINESE/g'
LC_ALL=C sed 's/[[:cntrl:]]//g' file
```

### 5.27 多行替换

```bash
sed -E ':a; N; $!ba; s/foo\nbar/XYZ/g' file       # GNU 模式
```

把 foo\nbar 看作一整体。`-z` 模式：

```bash
sed -z 's/foo\nbar/XYZ/g' file
```

### 5.28 字符串 / 单行脚本

```bash
sed -i 's/^/$/' foo.db     # DB 行尾插入 $
```

## 6. Hold space（暂存）示例

模式空间 = 一行；Hold space = 跨行缓存；命令：

| 命令 | 行为 |
| ---- | ---- |
| `h` | 模式 → 保持（overwrite） |
| `H` | 模式 → 保持（append） |
| `g` | 保持 → 模式（overwrite） |
| `G` | 保持 → 模式（append） |
| `x` | 互换 |
| `n` | 读下行到模式 |

经典：合并两行：

```bash
sed 'N; s/\n/ /' file
sed '$!N; $!s/\n/ /' file              # 所有邻近行 pair
```

## 7. 标签 / 循环 / 分支

```text
:label
cmd1
t label        如果上一次 s/// 成功，跳转
cmd2
```

合并多余空白成单个：

```bash
sed -E ':a; s/[ \t]+/ /g; ta' file
```

删除 / 合并即可。

## 8. 与 grep / cut / awk 协作

```bash
sed '1,5d' file | awk 'NF > 0'
sed -n '/^#/!p' file | grep -v '^$' | awk '{print NR, $1}'
```

## 9. 性能 / 大文件

- `sed -u`：一行一刷
- `LC_ALL=C`：避免 locale
- `grep -F`：先粗过滤
- `split + xargs`：分而治之

```bash
split -l 1000000 huge.log part_
for f in part_*; do
    sed 's/old/new/g' "$f" > "$f.new" && mv "$f.new" "$f"
done
rm part_*
```

## 10. 常见错

| 错 | 修 |
| -- | -- |
| 没生效 | 没 `-i` 或忘加 `/g` |
| 反斜杠爆炸 | 改用 `#` 作分隔符：`s#old#new#g` |
| `&` 被替换 | 用 `\1` 分组 |
| `\|` 无效 | 用 `-E` 后用 <code>&#124;</code> |
| utf8 转义 | `LC_ALL=C` |
| 中文字符"半宽" | 检查 locale |

## 11. vs perl / awk / perl

- `sed` 擅长顺序文本替换 / 删除
- `awk` 擅长按"行 → 字段 → 转换"
- `perl -pe / perl -pi` 是 sed 加强版（带 string 编程能力）

```bash
perl -pe 's/foo/bar/g' file
perl -pi -e 's/foo/bar/g' file
```

Perl 支持 lookahead/lookback、负向断言、非贪婪：

```bash
perl -ne 'print if /(?<!default)\bstyle/' file
```

## 12. 更多实战例子

### 12.1 日志 / nginx 配置

```bash
# 修改 nginx 配置的最大连接数
sed -i 's/^worker_connections [0-9]*/worker_connections 4096/' /etc/nginx/nginx.conf

# 注释行 / 启用行切换
sed -i 's/^#\(http {.*\)$/\1/' /etc/nginx/nginx.conf

# 把旧路径改为新路径
sed -i 's|/var/log/app|/var/log/my-app|g' /etc/nginx/conf.d/*.conf

# 跨行记录 config
sed -in 'BEGIN{ORS="\n\n"} 1{h; d}; ${G}' /etc/nginx/nginx.conf
```

### 12.2 多行重排

```bash
# tac（行反转）
sed '1!G;h;$!d' file

# 段落归并
sed -E '/./{H;$!d}; x; s/\n+/\n/g' file

# 多个空行 → 单空行
sed '/^$/N;/^\n$/D' file

# 双空行 → 单空行
sed '/^$/N;/^\n$/D' file

# 反向行内容（每行字节反转）
sed -E '/\n/!G;s/\n/&&/;h;$!d; x' file
```

### 12.3 注释 / 反注释

```bash
# 在匹配前一行加 #
sed -i '/^max_connections/s/^/#/' my.cnf

# 去掉 #
sed -i 's/^#\?\(max_connections = \).*$/\15000/' my.cnf

# 整段环境变量加引号
sed -E "s/^([A-Z_][A-Z0-9_]*)=(.*)\$/\\1=\"\\2\"/" /etc/profile.d/*.sh
```

### 12.4 文本字段处理

```bash
# 每行清白所有逗号
sed -E 's/,(.*),/, \1/' csv

# 把 "key=value" 转 key=value 精炼
sed -E 's/^\s*"?([A-Za-z_][A-Za-z0-9_]*)"?\s*[:=]\s*"?([^"]*?)"?\s*$/\1=\2/' file

# 过滤版本号
sed -E 's/v([0-9]+)\.([0-9]+)\.([0-9]+)/V\1_\2_\3/' CHANGELOG
```

### 12.5 改行尾 / 行首 / 末尾

```bash
# 加行首
sed 's/^/prefix-/' file

# 加行尾
sed 's/$/-suffix/'

# 把 \r\n 转 \n (Windows → Unix)
sed -i 's/\r$//' file

# Unix → Windows
sed -i 's/$/\r/' file

# 删行前空白
sed 's/^[ \t]*//'

# 删行尾空白
sed 's/[ \t]*$//'

# 多个空格合并为单空格
sed -E 's/[ ]+/ /g'

# trim 头尾
sed -E 's/^[ \t]+//; s/[ \t]+$//'
```

### 12.6 排版 / 文本加工

```bash
# 双换行
sed G file

# 双倍行间
sed 'G;G;s/^/\n/'   # 三倍
sed '/^$/d;G' file  # 删除多余空行后双倍

# 删除阶梯裂入
sed -E ':a;N;$!ba;s/\n[ ]*[\n ]*/\n/g' file

# JSON / YAML 格式转 CSV （pipeline 仅示意）
sed -E 's/^([\w-]+):\s*"?([^",]+)"?(,?)$/\1\t\2\3/' YAML文件
```

### 12.7 进程 / 端口 / 服务

```bash
# 改 sshd 端口
sed -i 's/^#\?Port [0-9]*/Port 22222/' /etc/ssh/sshd_config

# 去掉不安全的 Cisco 设备领域
sed -i 's/^transport input telnet.*$/transport input ssh/' /etc/cisco_ios.cfg
```

### 12.8 查找 + 替换 + 大改

```bash
# 删除 "deleted-vars" 变量
sed -i '/^deleted-vars:/,/^$/d' config

# 重新分配产品 ID + 1
sed -E 's/^(\s*)"id": ([0-9]+)(,)$/\1"id": \3/' data.json

# 修正 " 老错字 → 新错字 "
sed -i 's/foobbar/foobar/' file
```

### 12.9 列表式示例

```bash
# 1. /etc/resolv.conf 插 nameserver
sed -i '1i nameserver 1.1.1.1' /etc/resolv.conf

# 2. 跳出括号包台
sed -E 's/[()]//g' file

# 3. 移除 RFC 4180 中双引号 JSON 中的 "
sed -E 's/(^|,)"([^",]+)"$/\1\2/' csv

# 4. 让 IPv4 地址中间两位整数反序
sed -E 's/^\(([0-9]{1,3})\.\([0-9]{1,3})\.\([0-9]{1,3})\.\([0-9]{1,3})\).*$/' file
```

### 12.10 multi-pattern 替换

```bash
sed -i 's/foo/BAR/g; s/^#/WARN/#/' config

# 多命令以 ; 分隔
sed -i -e 's/foo/bar/' -e 's/hello/hi/' -e '/^#/d' file

# 使用脚本：
cat <<EOF | sed -f - file
s/foo/bar/
s/hello/world/
EOF
```

### 12.11 sed 加速 / 多线程 / 进度

```bash
# 拆开后压缩合
split -l 1000000 huge.log part_
for f in part_*; do sed 's/foo/bar/g' "$f" > "$f.new"; mv "$f.new" "$f"; done
rm part_*

# GNU parallel sed
ls *.log | parallel 'sed -i.bak "s/foo/bar/g" {}'

# 显示进度
time sed 's/foo/bar/g' huge
```

### 12.12 sed + SQL / 配置

```bash
# 改 INSERT 为 UPSERT
sed -i 's/INSERT INTO/UPSERT INTO/' migration.sql

# 生成批量 SET init
sed -E 's/^(\S+)=[0-9]\+/SET \1=DEFAULT;/' env

# k8s configMap 批量顺序修改
sed -E 's/(image: my/app):v[0-9.]+/\1:v2.0.0/' k8s/deploy.yaml
```

### 12.13 生产环境中使用例子

```bash
# TOML 、INI、CUE 、env 不同格式互转
sed -E 's/^([A-Z_]+)=(.*)$/\1 = "\2"/' env-file      # env → TOML-like
sed -E 's/^([A-Z_]+) = "(.*)"$/\1=\2/' toml-file    # TOML → env
sed -E 's/^([a-z]+):\s*(.*)$/\1=\2/' yaml-file      # YAML → env
```

### 12.14 纯文本三例

```bash
# 反转每行字节
sed -E ':a; /\n/!{s/^(.*)(.)$/\2&\1/;ba}' file
sed -E '1h;2!{1!G;h;$!d};x' file

# 隔一行拼接
sed 'N;s/\n/ /' file

# 10行为一组反拼
sed -E ':a;N; $!ba;1~10d' file
```

## 13. 一句话总结

```text
sed = 流式逐行变换 + s/A/B/g 替换
-i 改文件，-n -p 只输出，-E 扩展正则
地址 + 命令 + regex = 经典组合
s///g 是 80% 场景
```

## 13. 参考

- `man sed`
- `info sed`
- [GNU sed 手册](https://www.gnu.org/software/sed/manual/)
