# NFS 完全参考

NFS(Network File System)是 Sun Microsystems 1984 年发布的**分布式文件系统协议**,允许客户端像访问本地文件一样访问远程服务器上的文件。本文档覆盖协议版本、架构、配置、挂载、安全、性能、故障排查与实战案例。

## 一、基本概念

### 1. NFS 是什么

```text
- 由 Sun 公司 1984 年发布
- 基于 ONC RPC / XDR(外部数据表示)
- 默认端口 2049(NFSv4 起无需 portmapper)
- 工作在应用层,使用 TCP/UDP 传输
- 通过 VFS 虚拟文件系统层接入
```

### 2. 关键术语

```text
NFS        # 协议本身
RPC        # 远程过程调用,NFS 的底层机制
mountd     # 处理挂载请求的守护进程
nfsd       # 提供文件服务的守护进程
statd      # 状态监控(锁恢复)
lockd      # 锁管理(NLM)
quotad     # 配额守护进程
idmapd     # 用户/组 ID 映射
export     # 共享出去的目录
VFS        # 虚拟文件系统,客户端接入层
```

### 3. 一次挂载的工作流程

```text
1. 客户端 mount server:/path /mnt
2. mountd 响应客户端,告知 nfsd 端口
3. 客户端通过 RPC 与 nfsd 通信
4. 文件操作(open/read/write)经 VFS 转 RPC 调用
5. 服务端执行并返回结果
```

## 二、NFS 版本对比

### 1. 版本演进

| 版本 | 年份 | 传输 | 文件大小 | 关键特性 |
| --- | --- | --- | --- | --- |
| NFSv2 | 1989 | UDP | 2GB | 最初标准,RFC 1094 |
| NFSv3 | 1995 | TCP/UDP | 64位偏移 | RFC 1813,异步写 |
| NFSv4.0 | 2003 | TCP | 大文件 | RFC 3010,单端口 2049 |
| NFSv4.1 | 2010 | TCP | pNFS 并行访问 | RFC 5661 |
| NFSv4.2 | 2016 | TCP | 高级特性 | RFC 7862,稀疏文件、克隆 |

### 2. NFSv3 vs NFSv4 关键差异

```text
NFSv3:
  - 需要 portmapper(port 111)
  - 需要 mountd(动态端口)
  - 无内置锁,需 NLM(lockd)
  - 无状态,客户端缓存

NFSv4:
  - 单端口 2049,无需 portmapper
  - 内置锁(lease-based)
  - 复合操作(compound)
  - 内置 ACL、安全模型
  - 有状态协议
  - 支持 Kerberos 安全
```

### 3. 版本选择

```text
# 内网、Linux 客户端 → NFSv4.2(最新特性)
# 跨平台(Linux/BSD/macOS)→ NFSv4.1 或 NFSv3
# 老旧设备兼容 → NFSv3
# 性能优先 + 内核 ≥4.0 → NFSv4.1+(自动协商 rsize/wsize)
```

## 三、架构与组件

### 1. 服务端进程

```text
nfsd        # NFS 主守护进程(多线程)
mountd      # 处理挂载请求
statd       # 监听网络状态(锁恢复)
lockd       # NLM 锁管理(v3)
quotad      # 磁盘配额
idmapd      # 用户 ID 映射(v4)
rpcbind     # RPC 端口映射(v3 及以下)
gssd        # GSS-API 安全(v4 Kerberos)
```

### 2. 客户端进程

```text
nfsiod      # 异步 I/O 守护进程(已废弃,v4 内置)
rpcbind     # v3 必需
idmapd      # 用户 ID 映射(v4)
```

### 3. 内核模块

```bash
lsmod | grep nfs
# nfsv4 nfs nfs_acl lockd grace fscache nfs_ssc
```

### 4. 数据流:一次 read() 调用

```text
用户态:
  fd = open("/mnt/nfs/foo")
  read(fd, buf, n)
       │
       ▼
内核 VFS:
  vfs_read → nfs_file_read → nfs_read_rpcsetup
       │
       ▼ (RPC over TCP 2049)
网络:
  READ call ─────► 服务端
       │
       ▼
服务端 nfsd:
  fh_verify → vfs_read(本地) → 回复
```

## 四、服务端配置 /etc/exports

### 1. 文件格式

```text
# /etc/exports
# 共享路径  客户端(选项)  客户端(选项)
/srv/nfs   192.168.1.0/24(rw,sync,no_subtree_check)
/home      *.example.com(rw,sync,no_root_squash)
/data      10.0.0.0/8(ro,async) 192.168.1.10(rw,sync)
/backup    @admins(rw,sync)
```

### 2. 客户端指定方式

```text
单个主机:   192.168.1.100
通配符:     *.example.com / 192.168.1.*
IP 网段:    192.168.1.0/24
NIS 网组:   @groupname
通配子网:   192.168.1.*  10.0.0.0/255.0.0.0
```

### 3. 常用选项

```text
rw               # 读写(默认只读)
sync             # 同步写入(数据落盘再返回)
async            # 异步写入(性能好,断电可能丢)
no_subtree_check # 不检查父目录,提高性能(推荐)
subtree_check    # 检查父目录(默认)
no_root_squash   # 允许 root 保留权限(危险)
root_squash      # root 映射为 nobody(默认)
all_squash       # 所有用户映射为 nobody
anonuid/anongid  # 指定匿名 UID/GID
crossmnt         # 允许跨挂载点
fsid=num         # 强制 fsid(用于 NFSv4 伪根)
```

### 4. 应用配置

```bash
exportfs -a          # 应用 /etc/exports
exportfs -r          # 重读配置(全部撤销再导出)
exportfs -u /data    # 取消共享
exportfs -v          # 详细列出当前导出
```

## 五、客户端挂载

### 1. 临时挂载

```bash
mount -t nfs  server:/path  /mnt
mount -t nfs4 server:/      /mnt
mount -t nfs -o rw,sync,vers=4 server:/data /mnt
mount -t nfs -o vers=4.1 server:/pnfs /mnt
```

### 2. /etc/fstab 永久挂载

```text
server:/srv/nfs  /mnt/nfs  nfs   defaults,_netdev              0 0
server:/data     /mnt/data nfs4  rw,sync,hard,vers=4           0 0
server:/pnfs     /mnt/pnfs nfs   rw,vers=4.1,nconnect=16       0 0
```

`_netdev` 让 systemd 等待网络可达后再挂载。

### 3. autofs 自动挂载

```text
# /etc/auto.master
/mnt/nfs  /etc/auto.nfs

# /etc/auto.nfs
data   -rw,sync  server:/data
home   -rw       server:/home/&
backup -ro       server:/backup
```

`&` 表示按子目录自动展开;`timeout=300` 在 `/etc/auto.master` 中设置空闲卸载时间。

## 六、挂载选项详解

### 1. 通用选项

```text
rw / ro           # 读写 / 只读
sync / async      # 同步 / 异步写入
hard / soft       # 硬挂载(无限重试)/ 软挂载(超时失败)
intr / nointr     # 允许中断(v3)
_netdev           # 网络可用后才挂载
noacl             # 禁用 ACL(性能好)
acl               # 启用 ACL
```

### 2. NFS 版本

```text
vers=2 / vers=3 / vers=4 / vers=4.0 / vers=4.1 / vers=4.2
nfsvers=2         # 等同 vers
```

### 3. 性能调优

```text
rsize=32768       # 读块大小(字节),默认 32768
wsize=32768       # 写块大小
retrans=3         # 重传次数(软挂载时生效)
timeo=600         # 超时(十分之一秒,默认 600 = 60s)
async             # 异步写(性能好,断电可能丢)
nconnect=N        # 多连接并行(NFSv4.1+,Linux 5.3+)
```

### 4. 安全选项

```text
sec=sys           # 默认,UNIX UID 认证(明文)
sec=krb5          # Kerberos 5 认证
sec=krb5i         # Kerberos + 完整性校验(防篡改)
sec=krb5p         # Kerberos + 加密(防窃听)
```

### 5. 实战调优样例

```bash
# 高吞吐、Linux 内核 ≥5.3
mount -t nfs -o vers=4.2,rsize=1048576,wsize=1048576,nconnect=8 server:/data /mnt

# 高安全
mount -t nfs -o vers=4,sec=krb5p server:/secure /mnt

# 普通兼容
mount -t nfs -o vers=3,timeo=300,retrans=2 server:/data /mnt
```

## 七、命令行工具

### 1. 服务端

```bash
exportfs -a               # 应用 /etc/exports
exportfs -r               # 重读
exportfs -u /data         # 取消共享
exportfs -v               # 详细列表
showmount -e server       # 显示共享列表
showmount -a server       # 已挂载客户端
showmount -d server       # 目录导出
rpcinfo -p server         # RPC 服务端口
nfsstat -s                # 服务端统计
```

### 2. 客户端

```bash
mount / umount            # 挂载 / 卸载
mount -t nfs              # 指定 NFS
mountstats /mnt           # 挂载详细统计(每挂载)
nfsstat -c                # 客户端统计
nfsstat -c 5              # 客户端 5 秒采样
umount -f /mnt            # 强制卸载(可能数据丢失)
umount -l /mnt            # 延迟卸载(空闲时卸载)
```

### 3. /etc/nfs.conf 关键段

```conf
[nfsd]
debug=0
threads=32                # 默认 8,根据 CPU 数调整

[mountd]
debug=0

[exportd]
debug=0
```

## 八、安全与认证

### 1. 安全模式

```text
sys        # 默认,基于 UNIX UID(明文,易仿冒)
krb5       # 仅认证
krb5i      # 认证 + 完整性(防篡改)
krb5p      # 认证 + 加密(防窃听,性能损耗)
```

### 2. Kerberos 配置要点

```bash
# /etc/krb5.conf
[libdefaults]
    default_realm = EXAMPLE.COM
    rdns = false
[realms]
    EXAMPLE.COM = {
        kdc = kdc.example.com
        admin_server = kdc.example.com
    }
[domain_realm]
    .example.com = EXAMPLE.COM
    example.com  = EXAMPLE.COM
```

```bash
# 服务端:为 nfs/<host> 创建 principal
kadmin -q "addprinc -randkey nfs/server.example.com"

# 客户端:为 nfs/<host> 创建 principal
kadmin -q "addprinc -randkey nfs/client.example.com"
```

### 3. root_squash 策略

```text
root_squash         # 默认,root → nobody
no_root_squash      # 保留 root 权限(慎用)
all_squash          # 所有用户 → nobody
anonuid=65534       # 显式匿名 UID(nfsnobody)
anongid=65534       # 显式匿名 GID
```

`no_root_squash` 仅在受信网络中、对可信主机的导出使用。

### 4. 网络层防护

```bash
# 防火墙只放行授权网段
firewall-cmd --add-rich-rule='rule family=ipv4 source address=192.168.1.0/24 service name=nfs accept'
firewall-cmd --add-rich-rule='rule family=ipv4 source address=192.168.1.0/24 port port=2049 protocol=tcp accept'

# 或 TCP wrapper(/etc/hosts.allow / /etc/hosts.deny)
# hosts.deny: rpcbind mountd nfsd statd lockd : ALL
# hosts.allow: rpcbind mountd nfsd statd lockd : 192.168.1.
```

## 九、性能调优

### 1. 网络层

```bash
# MTU / Jumbo Frame
ip link set eth0 mtu 9000

# 队列与多连接
mount -o nconnect=16 server:/data /mnt   # NFSv4.1+,Linux 5.3+
```

### 2. 块大小

```bash
# Linux 4.0+ 自动协商最大值
mount -t nfs -o rsize=1048576,wsize=1048576 server:/data /mnt
```

`rsize/wsize` 默认 32768(32K);最大 1048576(1M)。同一挂载点内核按协商结果统一。

### 3. 服务端 nfsd 数量

```conf
# /etc/nfs.conf
[nfsd]
threads = 32           # 一般每 CPU 核心 4-8 线程

# 或
echo 32 > /proc/fs/nfsd/threads
```

`threads` 不必等于 CPU 核数,通常 16-32 已足够;太多反而增加调度开销。

### 4. 缓存与回写

```bash
# /etc/sysctl.conf
sunrpc.tcp_slot_table_entries = 128     # 默认 2,增大提高并发
sunrpc.max_slot_table_entries = 128
```

```bash
sysctl -p
```

### 5. 监控指标

```bash
iostat -x 1                # 磁盘 IO
nfsstat -c 5               # 客户端 RPC / 网络
nfsstat -s 5               # 服务端 RPC / 网络
mountstats /mnt            # 单挂载点详细计数
ss -tin '( dport = :2049 or sport = :2049 )'   # TCP 重传
```

## 十、故障排查

### 1. 常见错误

```text
"Stale file handle"               # 服务端重启或导出路径变更
"Permission denied"               # root_squash / 本地权限不足
"Connection refused"              # 防火墙 / 服务未启动
"RPC: Program not registered"     # portmapper / rpcbind 未运行
"No route to host"                # 网络 / 路由问题
"mount.nfs: access denied"        # /etc/exports 客户端不匹配
"nfs: server not responding"      # 软挂载超时 / 网络抖动
```

### 2. 排查步骤

```bash
# 1. 网络可达
ping server
traceroute server
telnet server 2049               # NFSv4

# 2. 服务运行
systemctl status nfs-server
ss -tlnp | grep -E '2049|111|20048'
rpcinfo -p server

# 3. 导出列表
showmount -e server

# 4. 客户端调试
mount -v -o vers=3 server:/data /mnt
mountstats /mnt

# 5. 内核日志
dmesg | tail -50
journalctl -u nfs-client.target -n 100
```

### 3. Stale Handle 修复

```bash
# 客户端
umount /mnt
mount -t nfs server:/data /mnt

# 强制(慎用)
umount -f /mnt
mount -t nfs server:/data /mnt

# 查找持有者
lsof /mnt 2>/dev/null
fuser -mv /mnt
```

### 4. 锁与状态问题

```bash
# 服务端清空 grace period
# /etc/nfs.conf
[exportd]
manage-gids = yes

# 查看锁
cat /proc/fs/lockd/nlm_clients
```

## 十一、高级特性(pNFS / NFSv4.2)

### 1. pNFS(NFSv4.1)

```text
数据路径与元数据分离:
  MDS(元数据服务器)  ──► 客户端
  DS(数据服务器 ×N)  ──► 客户端(并行直连)
```

```bash
mount -t nfs -o vers=4.1 server:/pnfs /mnt
# 客户端自动并行从多个 DS 读写
```

### 2. NFSv4.2 新特性

```text
- sparse files       # 稀疏文件
- server-side copy   # 服务端拷贝
- named attributes   # 命名扩展属性
- LAYOUTSTATS        # 性能统计
- IO_ADVISE          # 访问模式提示
```

### 3. 部署要点

```bash
# 元数据服务器导出
exportfs -o fsid=0,no_subtree_check,insecure *:/export
exportfs -o fsid=1,refer=/export/data *:/data

# 客户端(内核 ≥ 4.0 多数已支持)
mount -t nfs4 -o minorversion=1 server:/ /mnt
```

## 十二、与同类对比

| 特性 | NFS | SMB/CIFS | AFP | iSCSI | GlusterFS |
| --- | --- | --- | --- | --- | --- |
| 平台 | Unix/Linux | Windows | macOS | 块设备 | 通用 |
| 协议 | RFC 标准化 | 私有+开放 | 私有 | SCSI over IP | 对象/文件 |
| 默认端口 | 2049 | 445 | 548 | 3260 | 自定义 |
| 鉴权 | Kerberos | 域控 | Kerberos | CHAP | TLS |
| 粒度 | 文件 | 文件 | 文件 | 块 | 文件 |
| 适用场景 | Linux 集群 | 混合办公 | macOS | 数据库 | 大规模存储 |

## 十三、实战案例

### 1. 搭建简单 NFS 服务器

```bash
# 安装(RHEL/CentOS)
yum install -y nfs-utils
systemctl enable --now nfs-server rpcbind

# 创建共享目录
mkdir -p /srv/nfs/data
chown nfsnobody:nfsnobody /srv/nfs/data
chmod 755 /srv/nfs/data

# 配置导出
cat >> /etc/exports <<'EOF'
/srv/nfs/data  192.168.1.0/24(rw,sync,no_root_squash,no_subtree_check)
EOF

# 应用
exportfs -a
exportfs -v

# 防火墙
firewall-cmd --permanent --add-service=nfs
firewall-cmd --permanent --add-service={mountd,rpc-bind}
firewall-cmd --reload
```

### 2. 客户端挂载

```bash
# 安装
yum install -y nfs-utils        # RHEL
apt install -y nfs-common       # Debian/Ubuntu

# 查看可用导出
showmount -e server

# 挂载
mkdir -p /mnt/data
mount -t nfs server:/srv/nfs/data /mnt/data
```

### 3. /etc/fstab 永久挂载

```text
server:/srv/nfs/data   /mnt/data   nfs   rw,sync,hard,_netdev,vers=4.2,nconnect=8   0 0
```

### 4. autofs 自动挂载

```text
# /etc/auto.master.d/nfs.autofs
/mnt/nfs  /etc/auto.nfs  --timeout=300

# /etc/auto.nfs
data   -rw,sync,vers=4   server:/data
home   -rw                server:/home/&
backup -ro                server:/backup
```

### 5. Kerberos 安全导出

```bash
# 服务端 /etc/exports
/secure   192.168.1.0/24(rw,sync,sec=krb5p,no_subtree_check)

# 客户端
mount -t nfs -o vers=4,sec=krb5p server:/secure /mnt/secure
```

### 6. 验证与基准

```bash
# 读写验证
dd if=/dev/zero of=/mnt/data/testfile bs=1M count=1024 oflag=direct
dd if=/mnt/data/testfile of=/dev/null bs=1M iflag=direct

# 多客户端并行压测
fio --name=randwrite --ioengine=libaio --direct=1 \
    --filename=/mnt/data/fiotest --bs=4k --size=1G \
    --rw=randwrite --numjobs=16 --runtime=60 --group_reporting

# 监控
nfsstat -c 5
iostat -x 1
```

### 7. pNFS 部署(NFSv4.1)

```bash
# MDS 端
echo "/export   *(rw,sync,fsid=0,no_subtree_check,insecure)" >> /etc/exports
echo "/export/data  *(rw,sync,fsid=1,refer=/export,no_subtree_check)" >> /etc/exports
exportfs -a

# DS 端(每台)
echo "/data  *(rw,sync,fsid=2,no_subtree_check)" >> /etc/exports
exportfs -a

# 客户端
mount -t nfs4 -o minorversion=1 server:/ /mnt
```

### 8. rsync + inotify 实时备份到 NFS

场景:本地 `/var/www/` 内容实时同步到 NFS 挂载点 `/mnt/backup/`,文件变化即触发。

#### 安装

```bash
yum install -y inotify-tools rsync
# Debian/Ubuntu: apt install -y inotify-tools rsync
```

#### 挂载 NFS(参考 §五)

```bash
mount -t nfs server:/srv/backup /mnt/backup
```

#### 备份脚本 /usr/local/bin/nfs-backup.sh

```bash
#!/bin/bash
SRC="/var/www/"
DST="/mnt/backup/www/"

inotifywait -m -r -e modify,create,delete,move,attrib "$SRC" |
while read -r path event file; do
    # rsync 本身已增量;此处只负责"何时触发"
    rsync -av --delete --exclude='.tmp' "$SRC" "$DST"
done
```

| 选项 | 含义 |
| ---- | ---- |
| `-m` | 持续监听不退出 |
| `-r` | 递归目录 |
| `-e` | 监听事件类型 |
| `modify / create / delete / move / attrib` | 写、新建、删、移动、属性变更 |

#### systemd 服务 /etc/systemd/system/nfs-backup.service

```conf
[Unit]
Description=Real-time NFS backup via rsync + inotify
After=network-online.target nfs-client.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/nfs-backup.sh
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
chmod +x /usr/local/bin/nfs-backup.sh
systemctl daemon-reload
systemctl enable --now nfs-backup.service
```

#### 节流版(避免风暴)

频繁写入场景下,每个事件都触发 rsync 会导致反复扫盘。加入节流:

```bash
#!/bin/bash
SRC="/var/www/"
DST="/mnt/backup/www/"
THROTTLE=2          # 至少间隔 N 秒才触发一次

last_run=0
inotifywait -m -r -e modify,create,delete,move,attrib "$SRC" |
while read -r path event file; do
    now=$(date +%s)
    if (( now - last_run >= THROTTLE )); then
        rsync -av --delete --exclude='.tmp' "$SRC" "$DST" \
            || logger -t nfs-backup "rsync failed: $?"
        last_run=$now
    fi
done
```

#### 稳定性要点

- **不要对每个事件 rsync 一次**:`inotifywait` 收事件后**批处理**(节流 1-5s),避免风暴
- **rsync 本身已增量**:监听只决定"何时跑",不决定"传什么"
- **inotify 句柄限制**:`/proc/sys/fs/inotify/max_user_watches`,监控大目录时调大
- **NFS 上慎用 `--delete`**:`sync` 模式保证一致性,但**断连时不要让删除操作扩散**
- **失败告警**:rsync 退出码非 0 时写日志 + 告警;`Type=simple + Restart=on-failure` 兜底
- **首跑先手动全量**:`rsync -av /var/www/ /mnt/backup/www/`,再启服务
- **避免本地与 NFS 双向同步**:单向就好,否则循环触发

#### 替代方案

| 工具 | 特点 |
| ---- | ---- |
| `incron` | 类 cron 但事件驱动,规则写在 `/etc/incron.d/` |
| `lsyncd` | 封装 inotify + rsync,自带节流与状态恢复(生产推荐) |
| `inotifywatch` | 只统计不触发,适合分析 |
| `fsevents → osascript`(macOS) | 替代方案,跨平台时考虑 |

```bash
# lsyncd 极简配置 /etc/lsyncd.conf
settings {
    logfile = "/var/log/lsyncd.log",
    statusFile = "/var/run/lsyncd.status",
    nodaemon = false,
}

sync {
    default.rsync,
    source = "/var/www/",
    target = "/mnt/backup/www/",
    rsync = {
        binary = "/usr/bin/rsync",
        archive = true,
        compress = false,
        delete = true,
    }
}
```

```bash
systemctl enable --now lsyncd
```

## 十四、要点速记

- **端口:NFSv3 用 portmapper(111),NFSv4 直接 2049**
- **/etc/exports:`路径 客户端(选项)`,改完 `exportfs -a` 或 `-r`**
- **核心选项:`rw / sync / root_squash / no_subtree_check`**
- **fstab:`server:/path /mount nfs opts 0 0`,加 `_netdev` 等网络**
- **硬挂载 vs 软挂载:生产用 hard + intr,避免数据损坏**
- **块大小:`rsize/wsize` 默认 32K,V4.1+ 自动协商至 1M**
- **安全:`sec=sys` 明文;`krb5p` 加密;按需选**
- **多连接:`nconnect=N`(NFSv4.1+,Linux 5.3+)**
- **服务端线程:`/etc/nfs.conf [nfsd] threads`,一般 16-32**
- **调试:`showmount`、`nfsstat`、`mountstats`、`dmesg`、`rpcinfo`**
- **锁:NFSv3 用 NLM(lockd),NFSv4 内置 lease**
- **常见错误:Stale handle → 重挂载;access denied → 检查导出列表**
- **NFSv4.2:sparse files、server-side copy、IO_ADVISE**
- **pNFS:元数据 + 多数据服务器并行(NFSv4.1+)**