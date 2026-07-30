# 常用 Linux 命令 (Linux Commands)

## 一、文件与目录命令

### 1. ls (列出目录)

```bash
ls                      # 列出当前目录
ls /path                # 指定目录
ls -l                   # 长格式(详细)
ls -a                   # 显示隐藏文件(.开头)
ls -h                   # 人类可读大小
ls -t                   # 按时间排序
ls -S                   # 按大小排序
ls -r                   # 反向
ls -R                   # 递归
ls -d                   # 目录本身,不是内容
ls -i                   # 显示 inode
ls -F                   # 加类型符号 (/, *, @, =)
ls -1                   # 一行一项

# 组合
ls -lah                 # 详细 + 隐藏 + 人类可读
ls -lt                  # 按时间,详细
ls -lS                  # 按大小,详细
ls *.txt                # 通配符
ls file?                # 单字符通配
ls file[12]             # 字符类

# 排序
ls -lt --time=atime    # 按访问时间
ls -lt --time=ctime    # 按元数据修改
```

### 2. cd (切换目录)

```bash
cd /                    # 根
cd ~                    # 主目录
cd -                    # 上次目录
cd ..                   # 上级
cd ../..                # 上上级
cd ~username            # 用户主目录
```

### 3. pwd (当前目录)

```bash
pwd                     # 当前
pwd -P                  # 物理路径(无符号链接)
```

### 4. mkdir (创建目录)

```bash
mkdir dir               # 单个
mkdir a b c              # 多个
mkdir -p a/b/c          # 递归
mkdir -m 755 dir         # 指定权限
```

### 5. rmdir (删除空目录)

```bash
rmdir dir               # 删空目录
rmdir -p a/b/c          # 递归删
```

### 6. cp (复制)

```bash
cp src dst
cp file1 file2 dir/      # 多个
cp -r dir1/ dir2/         # 递归
cp -p file dst           # 保留属性
cp -a src/ dst/          # 归档模式(所有属性)
cp -i src dst           # 交互
cp -f src dst           # 强制覆盖
cp -n src dst           # 不覆盖
cp -u src dst           # 仅较新
cp -v src dst           # 详细
cp -l src dst           # 硬链接
cp -s src dst           # 软链接

# 复制到多目录
echo "a b c" | xargs -n 1 cp src.txt
```

### 7. mv (移动/重命名)

```bash
mv src dst
mv file1 file2 dir/
mv -i src dst            # 交互
mv -f src dst            # 强制
mv -u src dst            # 仅较新
mv -v src dst            # 详细
mv dir1 dir2             # 改名
```

### 8. rm (删除)

```bash
rm file
rm -f file               # 强制
rm -i file               # 交互
rm -r dir/                # 递归
rm -rf dir/              # 强制递归 (慎用!)
rm -v file               # 详细
```

**危险命令**: `rm -rf /` 会删全系统,**千万不要输入**!

### 9. ln (链接)

```bash
ln file hardlink         # 硬链接
ln -s target symlink     # 软链接
ln -sf target symlink    # 强制
ln -b file link          # 备份
```

### 10. touch (更新时间戳/创建空文件)

```bash
touch file               # 创建/更新时间
touch -a file            # 只改访问时间
touch -m file            # 只改修改时间
touch -t 202401010000 file  # 指定时间
touch -d "2024-01-01 12:00" file
```

### 11. file (文件类型)

```bash
file file
file -i file             # MIME 类型
file -L symlink          # 跟随符号链接
```

### 12. stat (文件状态)

```bash
stat file
stat -c "%a %n" file     # 自定义格式
```

### 13. tree (目录树)

```bash
tree                    # 树形显示
tree -L 2                # 限制深度
tree -d                  # 只目录
tree -f                 # 完整路径
tree -h                 # 人类可读大小
```

---

## 二、文件查看命令

### 1. cat (连接显示)

```bash
cat file
cat -n file              # 显示行号
cat -b file              # 只对非空行编号
cat -s file              # 合并连续空行
cat -A file              # 显示所有(不可见字符)
cat file1 file2          # 拼接
```

### 2. less / more (分页)

```bash
less file                # 推荐(可前后翻)
more file               # 旧(只能向下)

# less 快捷键
j / ↓       下一行
k / ↑       上一行
f / Space   下一页
b           上一页
g           文件首
G           文件尾
/pattern    搜索
n           下一个匹配
N           上一个匹配
q           退出
```

### 3. head / tail (头/尾)

```bash
head file               # 前 10 行
head -n 5 file           # 前 5 行
head -c 100 file         # 前 100 字节
tail file               # 后 10 行
tail -n 5 file           # 后 5 行
tail -f file             # 实时跟踪(最常用)
tail -F file             # 跟文件名(防轮转)
tail -n +5 file          # 从第 5 行开始
```

### 4. nl (显示行号)

```bash
nl file                  # 显示行号
nl -ba file              # 包含空行
nl -bt file              # 不包含空行
```

### 5. od / hexdump (二进制查看)

```bash
od file                  # 八进制
od -c file               # 字符
od -x file               # 十六进制
hexdump -C file          # 经典 hex 查看
xxd file                 # 另一个 hex
```

### 6. strings (提取字符串)

```bash
strings file             # 提取可打印字符串
strings -n 5 file        # 至少 5 字符
```

---

## 三、文件查找与定位

### 1. find (按条件查找)

```bash
# 按名字
find / -name "*.txt"
find / -iname "*.TXT"     # 忽略大小写
find / -regex ".*\.txt$"

# 按类型
find / -type f           # 普通文件
find / -type d           # 目录
find / -type l           # 符号链接
find / -type b           # 块设备
find / -type c           # 字符设备
find / -type p           # 命名管道
find / -type s           # socket

# 按大小
find / -size +100M       # 大于 100M
find / -size -1k         # 小于 1K
find / -size 0           # 0 字节

# 按时间
find / -mtime -7          # 7 天内修改
find / -mtime +30         # 30 天前修改
find / -atime -1          # 1 天内访问
find / -ctime -1          # 1 天内元数据修改
find / -newer file        # 比 file 新
find / -mmin -60          # 60 分钟内修改

# 按权限
find / -perm 755
find / -perm -u+w         # 有写权限
find / -perm /u+w         # 任一用户有写权限

# 按属主
find / -user root
find / -group admin
find / -uid 1000

# 按深度
find / -maxdepth 3 -name "*.log"
find / -mindepth 2 -name "*.log"

# 空文件
find / -empty

# 链接
find / -inum 12345       # inode

# 多个条件
find / -name "*.log" -size +10M
find / \( -name "*.log" -o -name "*.tmp" \)
find / -not -name "*.log"

# 执行命令
find / -name "*.tmp" -delete
find / -name "*.log" -exec rm {} \;
find / -name "*.log" -exec rm {} +
find / -name "*.log" -exec rm -f {} \; -print

# 限制
find / -name "*.log" 2>/dev/null     # 错误丢弃
find / -name "*.log" -maxdepth 3
```

### 2. locate (从索引找)

```bash
locate filename          # 从 /var/lib/mlocate 索引
locate -i filename       # 忽略大小写
locate -c filename       # 计数
locate -r "regex"        # 正则

# 更新索引
updatedb
```

### 3. which / whereis / type

```bash
which ls                # 找 PATH 中的位置
whereis ls              # 命令、源码、man
type ls                 # 类型
```

### 4. grep (文本搜索)

```bash
# 基本
grep "pattern" file
grep -i "pattern" file          # 忽略大小写
grep -v "pattern" file          # 反向
grep -n "pattern" file          # 显示行号
grep -c "pattern" file          # 计数
grep -l "pattern" *              # 只列文件名
grep -r "pattern" dir/          # 递归
grep -A 3 "pattern" file        # 后 3 行
grep -B 2 "pattern" file        # 前 2 行
grep -C 5 "pattern" file        # 前后各 5 行
grep -w "word" file             # 整词
grep -x "line" file             # 整行
grep -E "regex" file            # 扩展正则
grep -P "regex" file            # Perl 正则
grep -F "string" file           # 固定字符串
grep -h "pattern" file          # 不显示文件名
grep -o "pattern" file          # 只显示匹配部分

# 多个模式
grep -e "p1" -e "p2" file
grep -E "p1|p2" file

# 例:找大日志的错误
grep -i "error" /var/log/*.log

# 例:找进程
ps aux | grep nginx
```

---

## 四、文本处理命令

### 1. sort (排序)

```bash
sort file
sort -n file                    # 数字
sort -r file                    # 反向
sort -u file                    # 去重
sort -k 2 file                  # 按第 2 列
sort -t: -k 3 -n /etc/passwd     # 冒号分隔,第 3 列数字
sort -h file                    # 人类可读数字 (2K, 1G)
sort -R file                    # 随机
sort -o output file             # 输出到文件
sort -c file                    # 检查是否已排序
```

### 2. uniq (去重)

```bash
sort file | uniq                # 去重
uniq -c file                    # 计数
uniq -d file                    # 只显示重复
uniq -u file                    # 只显示不重复
sort file | uniq -c | sort -rn  # 排序
```

### 3. wc (统计)

```bash
wc file                         # 行 词 字符
wc -l file                      # 行数
wc -w file                      # 词数
wc -c file                      # 字符
wc -m file                      # 字符(支持多字节)
wc -L file                      # 最长行
```

### 4. cut (提取列)

```bash
cut -d: -f1 /etc/passwd         # 冒号分隔,第 1 列
cut -d, -f1,3 file              # 多列
cut -c1-10 file                 # 字符 1-10
cut -c1,3,5 file                # 字符 1,3,5
```

### 5. paste (合并)

```bash
paste file1 file2               # 合并
paste -d',' file1 file2         # 自定义分隔符
paste -s file                   # 把多行合并为一行
```

### 6. tr (字符转换)

```bash
tr 'a-z' 'A-Z' < file          # 小写转大写
tr -d '\r' < file               # 删除字符
tr -s ' ' < file                # 压缩重复
tr '\n' ' ' < file              # 换行转空格
```

### 7. sed (流编辑器)

```bash
# 替换
sed 's/old/new/' file           # 替换第一个
sed 's/old/new/g' file         # 全部
sed 's/old/new/2' file         # 第 2 个
sed 's#/#-#g' file             # 用 # 分隔
sed 's/o/N/i' file             # 忽略大小写
sed -i 's/old/new/g' file      # 直接修改
sed -i.bak 's/old/new/g' file  # 备份

# 删除
sed '/pattern/d' file          # 删匹配行
sed '5d' file                   # 第 5 行
sed '1,5d' file                # 1-5 行
sed '$d' file                   # 最后一行
sed '/^$/d' file               # 空行
sed '/^#/d' file                # 注释

# 打印
sed -n '5p' file                # 第 5 行
sed -n '/start/,/end/p' file   # 范围
sed -n '1~2p' file              # 奇数行

# 插入
sed '5i\插入行' file
sed '5a\追加行' file
sed '5c\替换行' file
```

### 8. awk (字段处理)

```bash
# 打印字段
awk '{print $1}' file           # 第 1 列
awk '{print $NF}' file         # 最后一列
awk '{print $1, $3}' file      # 多列

# 分隔符
awk -F: '{print $1}' /etc/passwd
awk -F'[,:]' '{print $1, $2}' file

# 条件
awk '$3 > 100' file
awk 'NR > 1' file               # 跳过第 1 行
awk 'NR == 5' file              # 第 5 行
awk '/error/' file              # 匹配

# 统计
awk '{sum += $3} END {print sum}' file
awk '{count[$1]++} END {for (k in count) print k, count[k]}' file

# BEGIN/END
awk 'BEGIN {print "Header"} {print} END {print "Total:", NR}' file

# 内置
awk 'BEGIN {OFS="|"} {print $1, $2, $3}' file
```

### 9. xxd / hexdump (二进制)

```bash
xxd file | head                # 16 进制
xxd -r file                    # 还原
```

### 10. column (列格式化)

```bash
column -t file                 # 自动对齐
column -t -s: file             # : 分隔
mount | column -t
```

---

## 五、文件权限与属性

### 1. chmod (改权限)

```bash
# 数字模式
chmod 755 file
chmod 644 file

# 符号模式
chmod u+x file                  # 用户加执行
chmod g-w file                  # 组去写
chmod o=r file                  # 其他只读
chmod a+x file                  # 所有人加执行
chmod u+rwx,g+rx,o-rwx file

# 递归
chmod -R 755 dir/

# 特殊位
chmod u+s file                  # SUID
chmod g+s file                  # SGID
chmod +t dir                    # Sticky
```

**权限含义**:

| 数字 | 符号    | 含义                  |
|------|---------|-----------------------|
| 4    | r--     | 只读                  |
| 2    | -w-     | 只写                  |
| 1    | --x     | 只执行                |
| 0    | ---     | 无                    |

**特殊位**:

- **SUID (4)**:执行时,UID 临时变文件属主
- **SGID (2)**:组 ID 临时变文件属组
- **Sticky (1)**:目录中只有属主可删自己的文件 (如 /tmp)

### 2. chown (改属主)

```bash
chown user file
chown user:group file
chown -R user dir/              # 递归
chown :group file               # 只改组
chown 1000 file                 # 用 UID
```

### 3. chgrp (改组)

```bash
chgrp group file
chgrp -R group dir/
```

### 4. umask (默认权限)

```bash
umask                          # 看当前
umask 022                      # 改
# 文件默认 = 666 - umask
# 目录默认 = 777 - umask
# umask 022 → 文件 644,目录 755
```

### 5. chattr / lsattr (扩展属性)

```bash
# 不可变
chattr +i file                  # 不可修改
chattr -i file                  # 取消
# 只追加
chattr +a file                  # 只能追加
# 查看
lsattr file
```

### 6. getfacl / setfacl (ACL)

```bash
getfacl file
setfacl -m u:user:rw file       # 加 ACL
setfacl -m g:group:r file
setfacl -x u:user file          # 删
setfacl -b file                 # 全部删
```

---

## 六、用户与组

### 1. useradd / userdel / usermod

```bash
useradd username
useradd -u 1001 -g users username
useradd -m -d /home/user username    # 创建主目录
useradd -G sudo,docker username     # 附加组
useradd -s /bin/bash username       # 默认 shell
useradd -e 2024-12-31 username      # 过期时间

userdel username
userdel -r username             # 删主目录

usermod -aG sudo username       # 加组
usermod -l newname oldname      # 改名
usermod -d /new/home user      # 改主目录
usermod -s /bin/zsh user       # 改 shell
usermod -L user                # 锁定
usermod -U user                # 解锁
```

### 2. groupadd / groupdel / groupmod

```bash
groupadd groupname
groupdel groupname
groupmod -n new old             # 改名
groupmod -g 1234 group          # 改 GID
gpasswd -a user group           # 加成员
gpasswd -d user group           # 删成员
```

### 3. passwd / chpasswd

```bash
passwd                          # 改自己
passwd username                 # 改用户
passwd -d username              # 删密码
passwd -l username              # 锁定
passwd -u username              # 解锁

chpasswd                        # 批量改(从 stdin)
echo "user:newpass" | chpasswd
```

### 4. id / whoami / who / w

```bash
id                              # 当前用户信息
id username                     # 用户信息
whoami                          # 当前用户
who                             # 谁登录
w                               # 谁在干什么
last                            # 历史登录
lastlog                         # 最后登录
```

### 5. su / sudo

```bash
su -                            # 切 root
su - username                   # 切用户
sudo command                    # 临时 root
sudo -i                         # 交互 root
sudo -u user command            # 以 user 身份
sudo -l                         # 列出权限
visudo                          # 编辑 sudoers
```

---

## 七、进程与作业控制

### 1. ps (进程)

```bash
ps                              # 当前终端
ps aux                          # BSD 风格 (所有)
ps -ef                          # System V 风格
ps -e                           # 所有进程
ps -eH                          # 树形
ps -L                           # 显示线程
ps -o pid,user,comm             # 自定义列
ps -eo pid,user,pri,ni,stat,comm  # 完整信息
ps -p 1234                      # 特定 PID
ps -u user                      # 特定用户
ps -C nginx                     # 特定命令
ps --sort=-%cpu | head          # 按 CPU 排序
ps --sort=-rss | head          # 按内存排序
ps axf                          # 树形
ps -eo pid,etime,comm          # 启动时间
```

### 2. top / htop / atop

```bash
top                             # 实时
top -d 1                        # 1 秒刷新
top -p 1234                     # 特定 PID
top -u user                     # 特定用户
top -bn1                        # 批处理模式
top -bn1 | head -20             # 一次显示
htop                            # 增强
atop                            # 高级

# top 内部快捷键
M - 按内存排序
P - 按 CPU 排序
1 - 看每核
k - 杀进程
r - renice
q - 退出
```

### 3. kill / killall / pkill

```bash
kill PID                        # SIGTERM (15)
kill -9 PID                     # SIGKILL
kill -HUP PID                   # 重新加载
kill -STOP PID                  # 暂停
kill -CONT PID                  # 继续
kill -USR1 PID                  # 用户信号 1
kill -USR2 PID                  # 用户信号 2

killall nginx                   # 按名字
pkill -f "python.*"             # 模式匹配
pkill -u user                   # 按用户
pkill -t pts/0                  # 按终端
```

### 4. jobs / bg / fg

```bash
command &                       # 后台
jobs                            # 列出作业
fg %1                           # 提到前台
bg %1                           # 后台继续
Ctrl+Z                          # 挂起
kill %1                         # 杀
disown                          # 脱离 shell
nohup command &                 # 忽略 SIGHUP
```

### 5. nice / renice

```bash
nice -n -10 command             # 启动时
renice -n 5 -p PID              # 调整
# 范围: -20 (高) ~ 19 (低)
```

### 6. uptime

```bash
uptime                          # 启动时间 + 负载
# 输出: 10:30:00 up 100 days, 1 user, load average: 0.5, 0.3, 0.2
# 1/5/15 分钟平均负载
```

### 7. lsof

```bash
lsof                            # 所有打开文件
lsof -p PID                     # 进程
lsof -i                         # 网络
lsof -i :80                     # 端口
lsof -u user                    # 用户
lsof file                       # 谁在用
lsof +D dir                     # 目录下
```

### 8. fuser

```bash
fuser file                      # 谁在用文件
fuser -k file                   # 杀掉
fuser -m file                   # 挂载点
fuser -n tcp 80                 # 端口
```

---

## 八、系统监控命令

### 1. free (内存)

```bash
free                            # 总体
free -h                         # 人类可读
free -m                         # MB
free -g                         # GB
free -s 1                       # 1 秒刷新
free -t                         # 包含 total
```

### 2. df (磁盘)

```bash
df                              # 文件系统
df -h                           # 人类可读
df -i                           # inode
df -T                           # 显示 FS 类型
df -t ext4                      # 只 ext4
df -x tmpfs                     # 排除 tmpfs
```

### 3. du (目录)

```bash
du dir                          # 目录大小
du -sh dir                      # 人类可读总计
du -h dir                       # 详细
du -ah dir                      # 包含文件
du -h --max-depth 1 dir         # 1 级
du -h dir | sort -h | tail      # 找最大
du -h --exclude="*.log" dir     # 排除
```

### 4. iostat (IO 状态)

```bash
iostat                          # 总体
iostat -x                       # 详细
iostat -x 1                     # 1 秒刷新
iostat -d /dev/sda              # 特定盘
iostat -p sda                   # 特定盘 + 分区
```

### 5. vmstat (虚拟内存)

```bash
vmstat                          # 总体
vmstat 1                        # 1 秒刷新
vmstat 1 5                      # 5 次
```

**输出列**:
- `r`: 运行队列
- `b`: 阻塞队列
- `si/so`: 换入/换出
- `bi/bo`: 块 IO
- `cs`: 上下文切换

### 6. mpstat (CPU)

```bash
mpstat                          # 总体
mpstat 1                        # 1 秒刷新
mpstat -P ALL 1                 # 每核
```

### 7. sar (System Activity Reporter)

```bash
sar                             # 今日
sar -u 1 5                      # CPU 5 次
sar -r 1                        # 内存
sar -b 1                        # IO
sar -n DEV 1                    # 网络
sar -n TCP 1                    # TCP
sar -B 1                        # 换页
```

### 8. nstat

```bash
nstat                          # 网络统计
nstat -s                        # 简版
```

### 9. 性能查看

```bash
uptime                          # 负载
top / htop                      # 实时
vmstat 1                        # 整体
mpstat -P ALL 1                 # CPU
iostat -x 1                     # IO
free -h                         # 内存
df -h                           # 磁盘
ss -s                           # 网络连接
nstat                           # 网络统计
```

---

## 九、网络命令

### 1. ip (替代 ifconfig)

```bash
ip addr                         # 看 IP
ip addr show dev eth0
ip -4 addr                      # 只 IPv4
ip link                         # 看接口
ip link show eth0
ip route                        # 路由
ip route show default
ip neigh                        # ARP 表
ip neigh show
ip -s link show eth0            # 统计
ip rule                         # 路由策略
ip tunnel                       # 隧道
```

### 2. ping

```bash
ping host
ping -c 5 host                  # 5 次
ping -i 0.5 host                # 0.5 秒间隔
ping -s 1000 host               # 包大小
ping -t TTL host                # 设置 TTL
ping -I eth0 host               # 指定接口
ping -W 2 host                  # 超时
```

### 3. traceroute / tracepath / mtr

```bash
traceroute host
tracepath host
mtr host                        # 实时
mtr -n host                     # 不解析
```

### 4. ss (替代 netstat)

```bash
ss                              # 全部
ss -t                           # TCP
ss -u                           # UDP
ss -l                           # 监听
ss -a                           # 全部(含监听/非监听)
ss -p                           # 显示进程
ss -n                           # 数字
ss -tan                         # TCP all num
ss -s                           # 汇总
ss state established           # 已建立
ss state time-wait              # TIME_WAIT
ss sport = :22                  # 源端口 22
ss dport = :80                  # 目的端口 80

# 看 socket 内存
ss -m
```

### 5. netstat (传统)

```bash
netstat -tan                    # TCP 数字
netstat -l                      # 监听
netstat -p                      # 进程
netstat -s                      # 统计
netstat -rn                     # 路由
```

### 6. curl / wget

```bash
curl URL                        # 下载
curl -I URL                     # 头
curl -o file URL                # 输出到文件
curl -O URL                     # 保留远程文件名
curl -L URL                     # 跟随重定向
curl -X POST -d "data" URL     # POST
curl -H "X-Foo: bar" URL       # 自定义头
curl -u user:pass URL          # 认证
curl -k URL                     # 不验证证书
curl -v URL                     # 详细
curl -s URL                     # 静默
curl -L --max-redirs 3 URL     # 限制重定向
curl -c cookie.txt URL         # 存 cookie
curl -b cookie.txt URL         # 发送 cookie
curl -x proxy:8080 URL         # 代理
curl -T file URL                # PUT
curl -X DELETE URL              # DELETE
curl --data-urlencode "q=hello world" URL
curl -A "User-Agent" URL        # UA

wget URL
wget -c URL                     # 断点续传
wget -O file URL                # 输出到文件
wget -r URL                     # 递归
```

### 7. tcpdump

```bash
tcpdump -i eth0                  # 抓包
tcpdump -i eth0 -w capture.pcap # 保存
tcpdump -r capture.pcap         # 读
tcpdump -A -i eth0              # ASCII
tcpdump -X -i eth0              # 16 进制
tcpdump -i eth0 port 80         # 端口
tcpdump -i eth0 host 1.2.3.4   # 主机
tcpdump -i eth0 tcp             # TCP
tcpdump -i eth0 'tcp port 80 and not host 1.2.3.4'
tcpdump -i eth0 -c 100          # 100 包
tcpdump -i eth0 -n              # 不解析域名
```

### 8. nc (netcat)

```bash
nc host port                    # TCP 连接
nc -l 8080                      # 监听端口
nc -z host 1-1000               # 端口扫描
nc -l 8080 > file.out           # 接收
nc host 80 < file.in            # 发送
```

### 9. dig / nslookup / host

```bash
dig example.com                 # A 记录
dig example.com MX              # 邮件
dig example.com NS              # NS
dig @8.8.8.8 example.com        # 用特定 DNS
dig -x 8.8.8.8                  # 反向
dig +trace example.com          # 跟踪
dig +short example.com         # 简版

nslookup example.com
host example.com
```

### 10. nmap (端口扫描)

```bash
nmap host                       # 默认扫描
nmap -p 1-1000 host             # 端口范围
nmap -sV host                   # 探测服务版本
nmap -O host                    # 操作系统
nmap -A host                    # 综合
nmap -sS host                   # SYN 扫描(需 root)
nmap -sU host                   # UDP 扫描
nmap -A -T4 host                 # 激进模式
```

### 11. firewall-cmd (RHEL) / ufw (Ubuntu)

```bash
# firewalld
firewall-cmd --list-all
firewall-cmd --add-port=80/tcp
firewall-cmd --add-service=http
firewall-cmd --remove-port=80/tcp
firewall-cmd --reload

# ufw
ufw allow 22
ufw deny 23
ufw status
ufw enable
```

### 12. iptables / nft

```bash
# iptables
iptables -L                     # 列出规则
iptables -A INPUT -p tcp --dport 22 -j ACCEPT
iptables -A INPUT -j DROP
iptables -F                     # 清空
iptables -t nat -A POSTROUTING -s 192.168.1.0/24 -j MASQUERADE

# nft
nft list ruleset
nft add rule inet filter input tcp dport 22 accept
```

### 13. arp

```bash
arp -a                          # ARP 表
ip neigh                        # 新版
arp -s IP MAC                   # 静态
arp -d IP                       # 删除
```

---

## 十、系统信息

### 1. uname

```bash
uname -a                        # 全部
uname -r                        # 内核版本
uname -m                        # 架构
uname -s                        # 系统名
```

### 2. hostname

```bash
hostname                        # 主机名
hostname -f                     # 完整名
hostnamectl                     # systemd
hostnamectl set-hostname new    # 改
```

### 3. uptime

```bash
uptime
```

### 4. date / cal

```bash
date                            # 当前
date +"%Y-%m-%d %H:%M:%S"      # 格式
date -d "yesterday"             # 昨天
date -d "next monday"           # 下周一
date -s "2024-01-01 12:00:00"  # 设置
date +%s                        # 时间戳
date -d @1234567890             # 时间戳转时间

cal                             # 当月日历
cal 2024                        # 整年
cal 12 2024                     # 12 月
```

### 5. who / w / last

```bash
who                             # 谁登录
w                               # 谁在做什么
last                            # 历史登录
lastlog                         # 最后登录
```

### 6. lscpu / lsblk / lspci / lsusb

```bash
lscpu                           # CPU 信息
lsblk                           # 块设备
lsblk -f                        # 含 FS
lspci                           # PCI 设备
lspci -v                        # 详细
lsusb                           # USB
lsusb -v                        # 详细
```

### 7. dmidecode (硬件信息)

```bash
dmidecode                       # 全部
dmidecode -t memory             # 内存
dmidecode -t processor          # CPU
sudo dmidecode -t bios         # BIOS (需 root)
```

### 8. /proc 关键文件

```bash
cat /proc/cpuinfo
cat /proc/meminfo
cat /proc/version
cat /proc/uptime
cat /proc/loadavg
cat /proc/PID/status
```

---

## 十一、磁盘与存储

### 1. lsblk (块设备)

```bash
lsblk                           # 看块设备
lsblk -f                        # 含文件系统
lsblk -o NAME,SIZE,TYPE,MOUNTPOINT
```

### 2. fdisk / parted (分区)

```bash
fdisk -l                        # 看分区
fdisk /dev/sdb                  # 分区(交互)
# parted (推荐,支持 GPT)
parted /dev/sdb print
parted /dev/sdb mklabel gpt
parted /dev/sdb mkpart primary ext4 1MiB 10GiB
```

### 3. mkfs (格式化)

```bash
mkfs.ext4 /dev/sda1
mkfs.xfs /dev/sda1
mkfs.btrfs /dev/sda1
mkfs.fat -F32 /dev/sda1         # FAT32 (ESP)
mkswap /dev/sda1                # swap
```

### 4. mount / umount

```bash
mount                           # 看挂载
mount /dev/sda1 /mnt            # 挂载
mount -o ro,noexec /dev/sda1 /mnt
mount -t nfs server:/path /mnt
mount -o remount,ro /          # 重新挂载(只读)

umount /mnt                     # 卸载
umount -f /mnt                 # 强制
umount -l /mnt                 # 懒卸载
```

### 5. /etc/fstab

```bash
cat /etc/fstab                  # 配置
# 设备                挂载点  FS    选项       dump fsck
UUID=xxxxx        /       ext4  defaults   0    1
```

### 6. dd (复制)

```bash
dd if=/dev/sda of=image.dd bs=4M         # 整盘备份
dd if=image.dd of=/dev/sdb bs=4M       # 整盘恢复
dd if=/dev/zero of=file bs=1M count=100  # 写 100MB
dd if=/dev/urandom of=file bs=1M count=1 # 随机 1MB
dd if=file of=/dev/null bs=4M           # 测读速度
dd if=/dev/zero of=/dev/null bs=4M       # 测写速度
dd status=progress                     # 显示进度
```

### 7. sync (刷盘)

```bash
sync                            # 刷所有
sync -d                         # 数据
sync -f                         # 文件系统元数据
```

### 8. lvm (逻辑卷)

```bash
pvs                             # 看 PV
vgs                             # 看 VG
lvs                             # 看 LV

pvcreate /dev/sdb
vgcreate vg1 /dev/sdb
lvcreate -L 10G -n lv1 vg1

lvextend -L 20G /dev/vg1/lv1
resize2fs /dev/vg1/lv1
```

### 9. mdadm (软 RAID)

```bash
mdadm --create /dev/md0 --level=1 --raid-devices=2 /dev/sda1 /dev/sdb1
mdadm --detail /dev/md0
```

---

## 十二、压缩与解压

### 1. tar

```bash
# 打包
tar -cvf archive.tar dir/                 # 不压缩
tar -czvf archive.tar.gz dir/             # gzip
tar -cjvfa archive.tar.bz2 dir/           # bzip2
tar -cJvf archive.tar.xz dir/             # xz
tar -czvf archive.tar.gz --exclude="*.log" dir/

# 查看
tar -tvf archive.tar
tar -tzvf archive.tar.gz

# 解压
tar -xvf archive.tar
tar -xzvf archive.tar.gz
tar -xjvf archive.tar.bz2
tar -xJvf archive.tar.xz
tar -xzf archive.tar.gz -C /target/      # 解到指定目录

# 常用:
# -c 创建, -x 解压, -t 查看
# -v 详细, -f 文件名
# -z gzip, -j bzip2, -J xz
# -C 目录
# --exclude 排除
```

### 2. zip / unzip

```bash
zip file.zip file
zip -r archive.zip dir/
unzip archive.zip
unzip -l archive.zip            # 列出
unzip -d /target archive.zip   # 解到目录
```

### 3. gzip / gunzip

```bash
gzip file                       # 压缩为 file.gz
gzip -d file.gz                 # 解压
gunzip file.gz
gzip -k file                    # 保留原文件
gzip -9 file                    # 最大压缩
```

### 4. bzip2 / xz

```bash
bzip2 file                      # 压缩
bzip2 -d file.bz2
xz file                         # xz 压缩,更小
xz -d file.xz
```

### 5. 7z

```bash
7z a archive.7z dir/            # 压缩
7z x archive.7z                 # 解压
7z l archive.7z                 # 列表
```

### 6. zstd (现代压缩)

```bash
zstd file                       # 压缩为 file.zst
zstd -d file.zst                # 解压
```

---

## 十三、日志与调试

### 1. journalctl (systemd 日志)

```bash
journalctl                      # 全部
journalctl -u nginx             # 特定服务
journalctl -f                   # 跟踪
journalctl -n 100               # 最近 100 条
journalctl --since today        # 今日
journalctl --since "1 hour ago"
journalctl --until "2024-01-01"
journalctl -p err               # 错误级
journalctl -b                   # 启动后
journalctl -b -1                # 上次启动
journalctl -k                   # 内核日志
journalctl --disk-usage         # 占用空间
journalctl --vacuum-time=2d    # 保留 2 天
```

### 2. dmesg (内核日志)

```bash
dmesg                           # 全部
dmesg -w                        # 跟踪
dmesg -T                        # 人类时间
dmesg | grep -i error           # 错误
dmesg --level=err               # 错误级
```

### 3. rsyslog / syslog

```bash
tail -f /var/log/syslog          # 跟踪
tail -f /var/log/messages        # RHEL
tail -f /var/log/auth.log        # 认证日志
tail -f /var/log/nginx/error.log # 应用日志
```

### 4. strace (系统调用追踪)

```bash
strace command                  # 跟命令
strace -p PID                   # 跟进程
strace -e trace=open,read,write cmd  # 特定系统调用
strace -c command               # 统计
strace -o log.txt command       # 输出到文件
strace -f command               # 跟子进程
strace -t command               # 显示时间
```

### 5. ltrace (库调用追踪)

```bash
ltrace command
ltrace -p PID
ltrace -c command               # 统计
```

### 6. perf (性能分析)

```bash
perf top                        # 实时
perf record command              # 记录
perf report                     # 报告
perf stat command               # 统计
perf list                       # 列出事件
```

### 7. bpftrace (eBPF 高级追踪)

```bash
bpftrace -e 'kprobe:do_sys_open { printf("%s %s\n", comm, str(arg0)); }'
```

### 8. ltrace / pmap / pstack

```bash
pmap PID                        # 内存映射
pstack PID                      # 调用栈
```

---

## 十四、内核与模块

### 1. uname / lsmod / modinfo

```bash
uname -r                        # 内核版本
lsmod                           # 已加载模块
modinfo module_name             # 模块信息
```

### 2. modprobe / insmod / rmmod

```bash
modprobe module_name            # 加载(自动依赖)
modprobe -r module_name          # 卸载
insmod file.ko                  # 直接加载
rmmod module_name                # 卸载
```

### 3. /proc/sys 调优

```bash
sysctl -a                       # 全部参数
sysctl vm.swappiness=10         # 改
sysctl -p /etc/sysctl.conf      # 加载配置
cat /proc/sys/kernel/pid_max    # 看
```

### 4. dmesg / kern.log

```bash
dmesg
cat /var/log/kern.log
```

### 5. /proc/cmdline

```bash
cat /proc/cmdline                # 当前启动参数
```

---

## 十五、其他常用命令

### 1. time (计时)

```bash
time command                    # 计时
time -p command                 # 简版输出
```

### 2. watch (周期执行)

```bash
watch command
watch -n 1 command               # 1 秒
watch -d command                 # 高亮变化
```

### 3. xargs

```bash
find . -name "*.log" | xargs rm
find . -name "*.log" -print0 | xargs -0 rm   # 处理空格
```

### 4. parallel (GNU Parallel)

```bash
ls *.txt | parallel wc -l
ls *.txt | parallel -j 4 gzip  # 4 并发
```

### 5. screen / tmux (终端复用)

```bash
# screen
screen -S name                  # 新会话
screen -ls                      # 列出
screen -r name                  # 重新连接
Ctrl+A D                        # 分离
Ctrl+A C                        # 新窗口

# tmux
tmux new -s name
tmux ls
tmux attach -t name
Ctrl+B D                        # 分离
Ctrl+B C                        # 新窗口
```

### 6. at / cron (定时任务)

```bash
# at: 一次性
at 23:00
> command
> Ctrl+D

atq                             # 列出
atrm 1                          # 删除

# cron: 周期性
crontab -e                      # 编辑
crontab -l                      # 列出
crontab -r                      # 清空
```

**cron 格式**:`分 时 日 月 周 命令`

```text
0 2 * * * /scripts/backup.sh     # 每天凌晨 2 点
*/5 * * * * command                # 每 5 分钟
0 0 * * 0 command                 # 每周日 0 点
```

### 7. history

```bash
history                         # 列出
history | grep docker            # 搜索
!123                            # 执行 123 条
!!                              # 上条
Ctrl+R                          # 搜索
HISTSIZE=10000                   # 改历史大小
```

### 8. alias

```bash
alias ll='ls -lah'
alias gs='git status'
unalias ll
# 永久: 写 ~/.bashrc
```

### 9. source

```bash
source script.sh                # 当前 shell 执行
. script.sh                     # 同上
source ~/.bashrc                # 重新加载配置
```

### 10. 实用工具

```bash
man command                     # 手册
whatis command                  # 一句话
info command                    # 详细
tldr command                    # 简洁(需装 tldr)
cheat command                   # 速查
```

---

## 十六、命令速查表 (按功能)

### 文件操作

| 命令          | 功能                |
|---------------|---------------------|
| `ls`          | 列目录              |
| `cd`          | 切目录              |
| `pwd`         | 当前目录            |
| `mkdir`       | 创建目录            |
| `rmdir`       | 删空目录            |
| `cp`          | 复制                |
| `mv`          | 移动/改名           |
| `rm`          | 删除                |
| `ln`          | 链接                |
| `touch`       | 创建空/更新时间     |
| `tree`        | 树形显示            |
| `file`        | 文件类型            |

### 文本查看

| 命令        | 功能             |
|-------------|------------------|
| `cat`       | 全部输出         |
| `less/more` | 分页             |
| `head/tail` | 头/尾            |
| `nl`        | 加行号           |
| `od`        | 16/8 进制        |
| `xxd`       | 16 进制          |

### 文本处理

| 命令       | 功能                |
|------------|---------------------|
| `grep`     | 搜索                |
| `sed`      | 编辑                |
| `awk`      | 字段处理            |
| `sort`     | 排序                |
| `uniq`     | 去重                |
| `cut`      | 切列                |
| `paste`    | 合并                |
| `tr`       | 字符转换            |
| `wc`       | 统计                |
| `column`   | 对齐                |

### 进程

| 命令        | 功能              |
|-------------|-------------------|
| `ps`        | 进程              |
| `top/htop`  | 实时              |
| `kill`      | 杀进程            |
| `killall`   | 按名杀            |
| `pkill`     | 模式杀            |
| `nice`      | 优先级            |
| `lsof`      | 打开文件          |
| `fuser`     | 文件使用进程      |

### 网络

| 命令           | 功能                |
|----------------|---------------------|
| `ip`           | 网络配置            |
| `ping`         | 连通性              |
| `traceroute`   | 路径                |
| `mtr`          | 实时路径            |
| `curl/wget`    | HTTP                |
| `ss/netstat`   | 连接                |
| `tcpdump`      | 抓包                |
| `dig/nslookup` | DNS                 |
| `nmap`         | 端口扫描            |
| `nc`           | 网络瑞士军刀        |
| `iptables`     | 防火墙              |

### 磁盘

| 命令      | 功能                |
|-----------|---------------------|
| `df`      | 文件系统            |
| `du`      | 目录大小            |
| `lsblk`   | 块设备              |
| `fdisk`   | 分区(MBR)           |
| `parted`  | 分区(GPT)           |
| `mount`   | 挂载                |
| `mkfs`    | 格式化              |
| `dd`      | 复制                |
| `lvm`     | 逻辑卷              |

### 压缩

| 命令    | 功能              |
|---------|-------------------|
| `tar`   | 打包              |
| `gzip`  | gz 压缩           |
| `bzip2` | bz2 压缩          |
| `xz`    | xz 压缩           |
| `zstd`  | zstd 压缩(现代)   |
| `zip`   | zip               |
| `7z`    | 7z                |

### 系统

| 命令       | 功能           |
|------------|----------------|
| `uname`    | 系统信息       |
| `hostname` | 主机名         |
| `uptime`   | 启动时间/负载  |
| `date`     | 日期           |
| `free`     | 内存           |
| `iostat`   | IO             |
| `vmstat`   | 虚拟内存       |
| `mpstat`   | CPU            |
| `dmesg`    | 内核日志       |
| `sysctl`   | 调参数         |

---

## 十七、命令组合实战

### 1. 找大文件

```bash
find / -type f -size +100M 2>/dev/null | xargs ls -lh | sort -k5 -hr | head
```

### 2. 找大目录

```bash
du -h / | sort -h | tail
```

### 3. 监控 CPU 高的进程

```bash
ps -eo pid,user,%cpu,comm --sort=-%cpu | head
top -bn1 | head -20
```

### 4. 监控网络

```bash
ss -tan | grep ESTAB | wc -l     # 已建立连接数
nstat                          # 网卡统计
sar -n DEV 1 3                  # 网络流量
```

### 5. 实时日志

```bash
tail -f /var/log/nginx/access.log | grep -E "404|500"
```

### 6. 统计访问 IP

```bash
awk '{print $1}' /var/log/nginx/access.log | sort | uniq -c | sort -rn | head
```

### 7. 批量重命名

```bash
# 加前缀
for f in *.txt; do mv "$f" "old_$f"; done
# 改后缀
for f in *.txt; do mv "$f" "${f%.txt}.bak"; done
```

### 8. 杀一类进程

```bash
pkill -f "python.*script.py"
pkill -u baduser
```

### 9. 找最近修改的文件

```bash
find /tmp -mmin -30 -type f      # 30 分钟内
find /home -mtime -1 -type f      # 1 天内
```

### 10. 看大进程的 IO

```bash
iotop -p PID
pidstat -d -p PID 1
```

---

## 十八、命令历史与别名

### 推荐 .bashrc 配置

```bash
# 别名
alias ll='ls -lah'
alias la='ls -A'
alias l='ls -CF'
alias gs='git status'
alias gp='git pull'
alias k='kubectl'
alias h='history | tail -20'
alias c='clear'
alias grep='grep --color=auto'
alias egrep='egrep --color=auto'
alias fgrep='fgrep --color=auto'
alias df='df -h'
alias du='du -h'
alias free='free -h'
alias ps='ps auxf'
alias ping='ping -c 5'
alias vi='vim'
alias ports='netstat -tulanp'

# 函数
extract() {
    if [ -f $1 ]; then
        case $1 in
            *.tar.bz2) tar xvjf $1 ;;
            *.tar.gz)  tar xvzf $1 ;;
            *.tar.xz)  tar xvJf $1 ;;
            *.bz2)     bunzip2 $1 ;;
            *.rar)     unrar x $1 ;;
            *.gz)      gunzip $1 ;;
            *.tar)     tar xvf $1 ;;
            *.tbz2)    tar xvjf $1 ;;
            *.tgz)     tar xvzf $1 ;;
            *.zip)     unzip $1 ;;
            *.Z)       uncompress $1 ;;
            *.7z)      7z x $1 ;;
            *)         echo "'$1' 无法解压" ;;
        esac
    fi
}

# 历史
HISTSIZE=10000
HISTFILESIZE=20000
HISTCONTROL=ignoreboth
shopt -s histappend
PROMPT_COMMAND="history -a; history -c; history -r; $PROMPT_COMMAND"
```

---

## 十九、核心要点速记

- **文件**:ls / cat / cp / mv / rm / find / grep
- **文本三剑客**:grep(搜索) / sed(替换) / awk(字段)
- **查看**:cat / less / head / tail / file
- **进程**:ps / top / htop / kill / pkill
- **系统**:uname / hostname / uptime / date
- **网络**:ip / ping / ss / curl / tcpdump / dig
- **磁盘**:df / du / mount / lsblk
- **内存**:free / vmstat
- **CPU**:top / mpstat
- **IO**:iostat / iotop
- **监控**:top / htop / iostat / vmstat / mpstat / sar / nstat
- **包管理**:apt (Debian) / dnf (RHEL) / pacman (Arch)
- **服务**:systemctl / journalctl
- **用户**:useradd / usermod / userdel / passwd
- **权限**:chmod / chown / umask
- **进程优先级**:nice / renice
- **时间**:date / cal / uptime
- **压缩**:tar / zip / gzip / xz / zstd
- **抓包**:tcpdump / wireshark
- **安全**:sudo / iptables / ssh
- **别名**:alias (临时) / ~/.bashrc (永久)
- **source / .** = 当前 shell 执行
- **nohup ... &** = 永久后台
- **Ctrl+R** = 历史搜索
- **Ctrl+Z** = 挂起
