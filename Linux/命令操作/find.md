# find

按路径递归查找文件并按规则输出 / 处理，是 Linux 文件搜索的事实标准。工具能力强，可加 -exec / -print0 / -delete，但语法复杂、行为微妙。

```text
find [起始路径...] [表达式]
        /[test]        /[-print]      /[action]
```

## 1. 命令行

```text
find [-H] [-L] [-P] [-Olevel] [-D help|tree|search|stat|rates|opt|exec] [path...] [expression]
```

| 选项 | 含义 |
| ---- | ---- |
| `-P` | 不跟随符号链接（默认） |
| `-L` | 跟随符号链接 |
| `-H` | 仅命令行参数跟随符号链接 |
| `-O1` `-O3` | 查询优化等级 |
| `-D` | 调试（`stat / search / tree / rates`） |
| `-mount / -xdev` | 不跨文件系统 |

结尾表达式：

| 选项 | 含义 |
| ---- | ---- |
| `-print` | 打印路径（默认） |
| `-print0` | NUL 终止 |
| `-ls` | 类似 `ls -dils` 输出 |
| `-exec CMD {} ;` | 对每个文件执行 |
| `-exec CMD {} +` | 一次性批量（参数数组） |
| `-ok CMD {} ;` | exec + 询问 |
| `-delete` | 直接删除（慎用） |

注：`-exec {} ;` 中 `{}` 必须可识别（GNU find 自动），`;`（转义或加引号）作为终止。

## 2. 测试（tests）

### 2.1 文件名 / 类型

| 表达式 | 含义 |
| ----- | ---- |
| `-name '*.log'` | shell glob（大小写敏感） |
| `-iname '*.LOG'` | 大小写不敏感 |
| `-path '/etc/*'` | 全路径 glob |
| `-ipath` | 路径 + ICASE |
| `-regex '...'` | 整路径（emacs） |
| `-iregex` | 大小写不敏感正则 |
| `-type [f\|d\|l\|b\|c\|p\|s]` | 类型 |
| `-xtype [f\|d\|l]` | 对链接指向"解 reference"后的类型 |
| `-links N` | 硬链接数 |
| `-inum N` | inode 号 |
| `-samefile f` | 共享 inode |

### 2.2 时间

```text
       mtime        change      access
       (-cmin)       (-ctime / -cmin)
        ↑
+ │  -N    | + N -  | -N
+ -----现在
```

| 表达式 | 含义 |
| ----- | ---- |
| `-mtime N` | 修改天数（24h） |
| `-mmin N` | 修改分钟 |
| `-atime N` | 访问 |
| `-ctime N` | 创建 / 元数据变化 |
| `-newer file` | 比 file 新 |
| `-anewer / -cnewer` | 访问 / 元数据 newer |

时间以 24 小时为单位；`N` 整数代表 N 个 24 小时前；带前缀有特殊情况：

| 前缀 | 含义 |
| --- | ---- |
| `+N` | N 天 *以前* |
| `N` | 严格 N 天前 |
| `-N` | N 天*内*（< N 天） |

例：7 天前的日志：

```bash
find /var/log -mtime +7 -name '*.log'
find /var/log -mmin -60                     # 1 小时内的
```

### 2.3 大小

| 表达式 | 含义 |
| ----- | ---- |
| `-size N` | 文件大小，N 为 512B 单位 |
| `-size +100M` | 大于 100M |
| `-size -1k` | 小于 1k |
| `-empty` | 空文件 / 目录 |

单位：

| 后缀 | 意义 |
| --- | ---- |
| `b` | 512-byte blocks（默认） |
| `c` | bytes |
| `k` | KB |
| `M` | MB |
| `G` | GB |

### 2.4 权限 / 所有者

| 表达式 | 含义 |
| ----- | ---- |
| `-perm mode` | 完全匹配（如 `-perm 644`） |
| `-perm -mode` | 所有位都设置（交集） |
| `-perm /mode` | 任意位设置（OR） |
| `-user U` | 拥有者 |
| `-group G` | 拥有组 |
| `-uid N` | uid |
| `-gid N` | gid |
| `-nogroup` / `-nouser` | 错属 |

权限例子：

```bash
find /tmp -perm 644
find / -perm -u+s           # 有 SUID
find / -perm /g+w           # 组可写任意
find / -perm -o+w           # 全员可写（与 ACL 区别）
```

`+` / `-` / `0`：GNU find 的"相对"模式：

```bash
find /path -perm -4000     # 至少 SUID 位
find /path -perm /u=w      # 任意写
find /path -perm 600 -type f
```

### 2.5 链接 / 目录深度

| 表达式 | 含义 |
| ----- | ---- |
| `-links N` | 链接数 |
| `-maxdepth N` | 限制最深 |
| `-mindepth N` | 限制最浅 |
| `-fstype TYPE` | 文件系统类型 ext4 / xfs / nfs / tmpfs |
| `-inum N` | inode |
| `-follow` | 已废弃，用 `-L` |

## 3. 链接处理

| 表达式 | 行为 |
| ----- | ---- |
| `-follow` / `-L` | 跟随符号链接 |
| `-noignore_readdir_race` | 同 |
| `-D tree` | 调试看 walk |
| `-ignore_readdir_race` | 防 live build |

`xtype`：

```bash
find . -xtype l    # 类型（不解链接）
```

## 4. 操作符 / 多个表达式

| 形式 | 含义 |
| --- | ---- |
| `( expr )` | 优先级 |
| `expr -o expr` | 隐式 OR，**但默认 between two tests 是 AND** |
| `,` | OR 但保留全部 |
| `! expr` | NOT |
| `expr1 expr2` | AND（隐式） |

例子：

```bash
find . -name '*.log' -o -name '*.tmp'
find . \( -name '*.log' -o -name '*.tmp' \) -size +1M
```

`-or / -and / -not` 等更清晰。

## 5. 标准动作

### 5.1 打印

```bash
find . -print                 # 默认
find . -print0                # NUL，pipe 给 xargs -0
find . -ls                    # 长格式
find . -printf '%p %s\n'      # 自定义格式
```

### 5.2 `%printf` 指令

| 格式 | 含义 |
| --- | ---- |
| `%p` | 路径 |
| `%f` | basename |
| `%h` | 目录前缀 |
| `%P` | 相对 find 的路径 |
| `%i` | inode |
| `%s` | 大小 |
| `%M` | mode |
| `%u` / `%g` | uid / gid |
| `%t` | mtime 日期 |
| `%T@` | mtime 秒浮点 |
| `%A@` | atime |
| `%C@` | ctime |
| `%y` / `%Y` | 文件 type 字符串 |
| `%l` | 链接目标 |

```bash
find . -type f -printf '%10s  %p\n' | sort -k1n | tail
```

### 5.3 -exec

```bash
find . -name '*.html' -exec grep -l 'TODO' {} \;
find . -type f -exec chmod 644 {} \;
find . -name '*.tmp' -exec rm -i {} \;

# 批处理：+ 收所有路径为参数列表
find . -name '*.html' -exec grep -l 'TODO' {} +
```

`* +` 用 `+` 一次性收，比 `\;` 快得多：

```bash
find . -name '*.tmp' -exec rm {} +       # batch rm
find /var/log -name '*.gz' -exec gzip -d {} +
find . -type f -exec chmod 644 {} +      # 一次性 chmod
```

### 5.4 -execdir

不用 cd，相对路径执行：

```bash
find . -name '*.log' -execdir gzip {} \;
```

### 5.5 -ok

```bash
find . -size +100M -ok du -h {} \;
```

### 5.6 -delete

```bash
find /tmp -type f -name '*~' -delete
find ~/.cache -type f -atime +30 -delete
```

注意：必须放在最后；不能跨 `-ok` 中间。

### 5.7 -fprint / -fprint0

```bash
find . -name '*.err' -fprint error.log
find . -name '*.err' -fprint0 - | xargs -0 ...
```

## 6. 高级示例

### 6.1 旧大文件清理

```bash
find /var/log -type f -size +200M -mtime +7 -delete
find / -type f -size +1G 2>/dev/null -exec ls -lh {} \;
```

### 6.2 SUID / SGID 文件

```bash
find / -perm -4000 -type f 2>/dev/null       # SUID
find / -perm -2000 -type f 2>/dev/null       # SGID
```

### 6.3 错主 / 错组

```bash
find / \( -nouser -o -nogroup \) 2>/dev/null
```

### 6.4 找目录占用 inode（见 inode.md）

```bash
find /var -xdev -printf '%h\n' | sort | uniq -c | sort -rn | head
```

### 6.5 找软连接 / 失效软链

```bash
find /etc -xtype l 2>/dev/null
```

### 6.6 文件处理流水线

```bash
find . -type f -name '*.csv' -print0 |
  xargs -0 -I {} gzip {}
```

### 6.7 排除

```bash
find . -name '*.go' -not -path './vendor/*'
find . \( -name '.git' -o -name 'node_modules' \) -prune -o -name '*.css' -print
```

### 6.8 大目录搜索

```bash
find / -type d -name 'node_modules' -prune -o -name '*.ts' -print
```

### 6.9 按周 / 按日期范围

```bash
find . -newermt '2024-01-01' ! -newermt '2024-02-01'
find . -regex '.*/\(2024\|2025\)/.*'
```

### 6.10 find PID

```bash
find /proc -maxdepth 1 -name '[0-9]*' -type d -mmin -30
```

### 6.11 文件类型按扩展名分类

```bash
find . -type f -name '*.md' | wc -l
```

### 6.12 找重复文件

```bash
find . -type f -size +1M -exec md5sum {} \; | sort | awk '{print $1}' | sort | uniq -d
```

### 6.13 删除几天前文件（含中文）

```bash
find /var/log/app -type f -name '*.log.*' -mtime +30 -delete
```

### 6.14 进入压缩文件查找

```bash
find . -type f \( -name '*.gz' -o -name '*.tar.gz' \) -exec zgrep 'pattern' {} +
```

### 6.15 按用户过滤

```bash
find /home -user alice -type f
```

### 6.16 大小 / 类型组合

```bash
find /var -type f -size +100M ! -name '*.gz' -print
```

### 6.17 权限 ISO 写法

```bash
find . -perm u=rw,g=r,o=r               # 等价 -perm 644
find . -perm -u+w,g=w,o=w               # -perm -222
```

### 6.18 包装带日志

```bash
find /data -type f -name '*.json' -exec echo "Processing: {}" \; -exec jq . {} \;
```

## 7. 与 xargs / parallel 配合

### 7.1 xargs

```bash
find . -name '*.log' -print0 | xargs -0 tar czf backup.tgz

# 每个参数一个
find . -name '*.tmp' -print0 | xargs -0 -n1 rm

# 控制并发
find . -name '*.png' -print0 | xargs -0 -P 8 -n1 convert -resize 50% {}
```

### 7.2 GNU parallel

```bash
find . -name '*.log' -print0 | parallel -0 gzip
```

## 8. 常见坑

- **空 glob**：`find . -name '*.log'` 不展开，从字面意义处理；用 `-name` 安全
- **含空格路径**：用 `-print0` + `xargs -0`
- **执行命令**：默认路径相对当前目录加 -exec；要绝对路径用 `-execdir` / 用绝对结果
- **-maxdepth 0** 仅匹配起始点；记住 `-mindepth` 配合
- **跟随链接**：默认不跟随，复制深链接结构时考虑 `-L` 但要小心循环

```bash
find . -L -type f -name '*.config' 2>/dev/null
```

### 8.1 启动性能

```bash
- O3                    # 优化
- warn / nice / ionice
-execdir                # 不用拿绝对路径
```

### 8.2 安全运行

```bash
find /var -type d -name "*.conf" -ok chmod 640 {} \;        # 询问
```

### 8.3 与 locate 区别

- find：实时精确，硬 IO 大
- locate：基于 updatedb 数据库，快但有滞后

## 9. 退出码 / 调试

| 退出码 | 含义 |
| ---- | ---- |
| 0 | 成功 |
| 1 | 错误 |
| 2 (and higher) | 一些 GNU 行为 |

调试：

```bash
find -D tree .
find -D rates .       # 性能统计
find -D search .      # expression 树
```

## 10. vs fd / locate

| 工具 | 优点 | 缺点 |
| --- | --- | ---- |
| `find` | 标准、强大 | 语法复杂 |
| `fd-find (fd)` | 易用、彩色、`.gitignore` 友好 | 年轻 |
| `locate` | 快 | 数据库滞后 |
| `mlocate` | 私有数据库 | 同样滞后 |
| `ls`/`tree` | 简单 | 无数过滤 |

```bash
fd 'pattern'            # 简化版 find
fd -e go 'TODO'         # 按扩展
fd -t f                 # 只普通文件
fd -t d                 # 只目录
```

## 11. 实战精选（更多例子）

### 11.1 按时间窗

```bash
# 过去 1 小时修改过的文件
find . -mmin -60

# 30 天到 60 天前的日志
find /var/log -name '*.log' -mtime +30 -mtime -60

# 仅今天
find /data -newermt "$(date '+%Y-%m-%d')" -type f -ls

# 比某文件新
find . -newer ./config.yaml

# 10 分钟前 ~ 5 分钟前修改
find . -mmin -10 -mmin +5
```

### 11.2 排除某路径

```bash
find . -path './node_modules' -prune -o -type f -name '*.js' -print
find . \( -path './.git' -o -path './vendor' -o -path './dist' \) -prune -o -type f -print

# 多重排除写法（一行干净）
find . -type d \( -name '.git' -o -name 'node_modules' -o -name 'dist' \) -prune -o -type f -name '*.js' -print
```

### 11.3 文件名 + 内容 双重过滤

```bash
# .js 文件里含 "TODO"
find . -name '*.js' -exec grep -l 'TODO' {} +

# 包含 "TODO" 且文件名 .js，含上下文 2 行
find . -name '*.js' -exec grep -B2 -A2 'TODO' {} +
```

### 11.4 替换 / 改文件名

```bash
# 把所有 .html 改为 .htm
find . -name '*.html' -exec sh -c 'mv "$1" "${1%.html}.htm"' _ {} \;

# 加后缀
find . -name '*.log' -exec sh -c 'mv "$1" "$1.bak"' _ {} \;

# 处理空路径
find . -name '*.log' -execdir mv {} "{}.bak" \;
```

### 11.5 软链 dangling 修复 / 删除

```bash
# 列出
find /opt -xtype l -print
# -xtype l  =  跟随软链后测试，不存在即判定

# 删除
find /opt -xtype l -delete

# 自动重启 ( 比如配 /etc/init.d/* 软链 )
find /etc -xtype l -delete
```

### 11.6 修复空目录 / 灌占位

```bash
# 列出空目录
find / -type d -empty 2>/dev/null

# 加占位 .keep
find /path/.git/objects/pack -type d -empty -exec touch {}/.keep \;

# 删除空目录
find /path -type d -empty -delete
```

### 11.7 文件大小分层

```bash
# 1MB - 10MB 的非压缩文件
find /var/log -type f -size +1M -size -10M ! -name '*.gz' -ls

# 0 字节文件
find . -size 0 -type f
find /var/log -type f -empty
```

### 11.8 按 owner / group 报告

```bash
# 谁占用 inode 多
find /var -xdev -type f -printf '%u\n' | sort | uniq -c | sort -rn | head

# 谁占用总 size
find /home -type f -size +1M -printf '%u %s\n' | awk '{s[$1]+=$2} END {for (k in s) print k, s[k]}' | sort -k2 -rn

# 找 STICKY 但 700 缺失的目录
find /tmp /var/tmp -type d \( -perm -1000 -o ! -perm 700 \) -ls
```

### 11.9 大文件中 grep

```bash
find /var/log -name '*.log' -size +500M -exec zgrep -l 'pattern' {} +
```

### 11.10 输出格式化 / 文件清单

```bash
# 生成 tar find 列表
find /etc -type f -name '*.conf' -print0 | tar --null --files-from=- -czf backup.tar.gz

# 文件统计
find . -type f -printf '%f\n' | sort | uniq -c | sort -rn | head -10

# 累计 size
find . -type f -printf '%s\n' | awk '{s+=$1} END{printf "%d KB\n", s/1024}'

# 当前用户的文件总占用
find / -xdev -user $USER -type f -printf '%s\n' | awk '{s+=$1} END{printf "%d MB\n", s/1024/1024}'
```

### 11.11 检测合理性（生产排查）

```bash
# 无主用户
find / -nouser -o -nogroup 2>/dev/null

# 备用：看上去 SUID 但名字奇怪
find /usr/bin /usr/sbin -perm -4000 -name '.*'
```

### 11.12 与 grep + sed / awk 流水线

```bash
# 查出含版权声明的文件
find . -type f -exec grep -l 'Copyright' {} +

# 列出命中文本后的三行
find . -name '*.md' -exec sh -c 'echo "$1"; grep -A3 "TODO" "$1" || true' sh {} \;
```

### 11.13 按时间 batch 备份

```bash
# 30 天前的 SQL dump 打包
find /backups -name '*.sql' -mtime +30 -print0 |
  tar --null --files-from=- -czf old-sql-$(date +%F).tar.gz
```

### 11.14 文件元数据 / inode

```bash
# 同一个 inode（硬链）
find /etc -inum 12345
find /etc -inum 12345 -ls

# inode 信息
stat "$(find . -name '*.log' | head -1)"

# 列出目录下 inode 数 ( 与 inode.md 章节配合 )
find / -xdev -type d -maxdepth 4 -printf '%h\n' | sort | uniq -c | sort -rn
```

### 11.15 与 git 配合

```bash
# 找出 git 跟踪但被手动改名的文件
git ls-files -m | xargs -I {} find {} -type f -ls

# 清理 .gitignore 但 disk 上仍存在
find . -type f ! -readable 2>/dev/null -ls
```

### 11.16 修正日志 / 锁定文件

```bash
# 找日志中例含特殊字符的行
find /var/log -name '*.log' -print0 |
  xargs -0 grep -l $'\r' 2>/dev/null

# 修改 owner
find /data/shared -type f -exec chown www-data:www-data {} +
```

### 11.17 用 -execdir 而非 -exec

```bash
# 抓 ls 速查
find . -name '*.png' -execdir ls -lh {} \;

# 同 tar
find /var -type f -name '*.log' -execdir tar cf - {} \;
```

### 11.18 chmod / chown 批量

```bash
# 文件 644，目录 755
find . -type f -exec chmod 644 {} +
find . -type d -exec chmod 755 {} +

# 兼容性
find . -perm -u+w -not -perm -g+w -type f -exec chmod 644 {} +
```

### 11.19 安全 / 路径清理

```bash
# 路径包含空格换行 用 -print0 + xargs -0
find . -type f -name '*.txt' -print0 | xargs -0 rm

# 调试要用 “防误删” 调用
find . -name '*.tmp' -ok rm {} \;
```

### 11.20 在模拟器上过滤文件

```bash
# 仅查找某个字串（regex）
find . -regextype egrep -regex '.*\.pyc$' -delete

# 挊出包含某函数名
find . -type f -name '*.py' -exec grep -l 'def main' {} +
```

### 11.21 估计 archive 大小

```bash
# 文件总数 / 估计大小
find /var -type f -printf '%s\n' | awk '{s+=$1} END {print s, "bytes"}'

# dry-run backup
find /data -type f -printf '%s\n' | awk '{s+=$1; c++} END {printf "%d files, %d MB\n", c, s/1048576}'
```

### 11.22 find + parallel

```bash
find . -name '*.jpg' -print0 |
  parallel -0 'convert {} -resize 50% {.small}'
```

### 11.23 看到 bash completion / 脚本调试

```bash
find . -type f -name '*.sh' -exec grep -l '^set -x' {} +
```

### 11.24 永久 set 格式 / 限制

```bash
find . -regextype posix-extended -type f -regex '.*\.\(log\|txt\)' -size +10M -exec ls -lh {} \;
```

### 11.25 有变化的文件监控

```bash
find /etc -type f -mmin -60 -newer /etc/.monitor_start -ls
```

### 11.26 仅看指定 ext 的压缩文件

```bash
find . \( -name '*.tar.gz' -o -name '*.tgz' -o -name '*.zip' \) -exec ls -lh {} +
```

### 11.27 采用 -fprintf 多 信息

```bash
find . -type f -fprintf "%h%f %s %TY-%Tm-%Td %TH:%TM:%TS\n" | head
```

### 11.28 中间处理使用 -printf 不周

```bash
# 我自已的环境中项目内最重要的 Top 10 文件（按大小）
find . -type f -printf '%s %p\n' 2>/dev/null | sort -nr | head
```

## 12. 一句话总结

```text
find PATH 表达式(-name, -type, -mtime, -size, ...) + (-print / -exec / -delete)
# 与 xargs / parallel 配合
# -print0 + xargs -0 处理特殊字符
# -maxdepth / -mindepth 控制深度
```

## 12. 参考

- `man find`
- `info find`
- [GNU findutils 文档](https://www.gnu.org/software/findutils/)
- [fd](https://github.com/sharkdp/fd)
