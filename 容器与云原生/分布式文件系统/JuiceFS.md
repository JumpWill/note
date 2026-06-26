# JuiceFS 笔记

## 一、JuiceFS 简介

JuiceFS 是一款面向云原生设计的高性能 **分布式 POSIX 文件系统**,由 Juice Data(原 JuiceFS Tech)开源。它的核心特点是:

- **数据与元数据分离存储**:文件数据存到对象存储(S3/OSS/COS 等),元数据存到独立的元数据引擎(Redis/MySQL/TiKV 等)。
- **POSIX 兼容**:几乎所有应用无需修改即可使用。
- **HDFS 替代品**:与 S3 类似的成本,但提供完整的文件系统语义。
- **云原生友好**:K8s CSI 驱动完善,适合 AI/大数据/容器化场景。

### 适用场景

| 场景 | 适用度 | 说明 |
| --- | --- | --- |
| AI/ML 训练数据集 | ⭐⭐⭐⭐⭐ | 海量小文件并发读、低成本 |
| 大数据分析 | ⭐⭐⭐⭐⭐ | 替代 HDFS、兼容 Hadoop/Spark |
| K8s 持久化存储 | ⭐⭐⭐⭐⭐ | CSI 驱动完善,跨 Pod 共享 |
| 数据湖冷热分层 | ⭐⭐⭐⭐ | 与对象存储原生结合 |
| 跨云/混合云 | ⭐⭐⭐⭐ | 元数据 + 对象存储可跨云 |
| 数据库 OLTP | ⭐ | 不推荐 |
| 视频流媒体 | ⭐⭐⭐ | 需要客户端缓存配合 |

### 与其他分布式文件系统对比

| 维度 | JuiceFS | HDFS | CephFS | MinIO | Alluxio |
| --- | --- | --- | --- | --- | --- |
| 接口 | POSIX | HDFS API | POSIX | S3 | POSIX+HDFS |
| 元数据存储 | Redis/MySQL/TiKV | NameNode | Ceph MDS | 无 | 自身存储 |
| 数据存储 | 对象存储 | 本地磁盘 | OSD 节点 | 节点本地 | 对象存储 |
| 部署难度 | 低 | 中 | 高 | 中 | 中 |
| 性能 | 高(对象存储) | 高(本地) | 中 | 高(S3 API) | 中(缓存层) |
| 成本 | 低 | 中 | 高 | 中 | 中 |
| 跨云 | 强 | 弱 | 弱 | 弱 | 中 |
| 适用规模 | PB+ | PB+ | PB+ | EB | PB+ |

---

## 二、架构

### 1. 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                    应用(Application)                     │
│        (Hadoop / Spark / K8s / 机器学习 / 通用程序)      │
└────────────────────┬────────────────────────────────────┘
                     │ POSIX API (read/write/open/...)
                     ▼
┌─────────────────────────────────────────────────────────┐
│              JuiceFS 客户端 (FUSE 用户态)                 │
│   - 文件读写、目录管理、权限、缓存、压缩、加密            │
│   - Linux: libfuse / macFUSE                              │
└────────┬─────────────────────────┬──────────────────────┘
         │ 元数据请求              │ 数据读写(块级)
         ▼                         ▼
┌──────────────────────┐   ┌──────────────────────┐
│   元数据引擎          │   │   对象存储            │
│ (Redis/MySQL/TiKV)   │   │ (S3/OSS/COS/MinIO)   │
│ - 文件名/目录树       │   │ - 文件被切成 Chunk   │
│ - 属性/权限/时间戳    │   │ - Chunk 切成 Block    │
│ - 数据 → 块映射      │   │ - Block 压缩+加密     │
└──────────────────────┘   └──────────────────────┘
```

### 2. 关键组件

| 组件 | 作用 |
| --- | --- |
| **JuiceFS 客户端** | 用户态进程,通过 FUSE 提供 POSIX 接口 |
| **元数据引擎** | 存储文件元数据(属性、目录树、chunk→block 映射) |
| **对象存储** | 存储实际数据(以 chunk/block 为粒度) |
| **Format 文件** | 描述一个 JuiceFS 卷的配置(`metaurl`, `bucket`) |
| **Mount 挂载点** | 客户端把 JuiceFS 卷挂载到本地路径 |

### 3. 数据存储结构(重点)

JuiceFS 把数据切分成 **Chunk → Slice → Block** 三级:

```
文件(file)
└── 多个 Chunk(默认 64MB,可调)
    └── 多个 Slice(变长,写入时产生)
        └── 多个 Block(默认 4MB,可调)
            └── 压缩 + 加密 → 对象存储中的对象
```

- **Chunk**:文件的逻辑分段,默认 64MB。跨越多个 Chunk 时不必复制整个文件。
- **Slice**:Chunk 内一次写入产生的连续区间。变长,记录实际写入位置。
- **Block**:Slice 内的物理块,默认 4MB,实际存储对象。

> 这种 **Chunk/Slice/Block** 三层结构让 JuiceFS 在随机写、覆盖写时非常高效,不需要重写整个文件(类似 WAL 思想)。

---

## 三、安装与准备

### 1. 安装客户端

#### Linux 一键安装

```bash
curl -L https://juicefs.com/static/juicefs -o /usr/local/bin/juicefs
chmod +x /usr/local/bin/juicefs
juicefs --version
```

#### 包管理器安装

```bash
# Ubuntu/Debian
apt install -y juicefs

# CentOS/RHEL
yum install -y juicefs

# macOS
brew install juicefs
```

### 2. 准备元数据引擎

JuiceFS 支持多种元数据引擎,生产环境推荐 Redis Cluster / TiKV / MySQL:

#### Redis(简单场景)

```bash
docker run -d --name redis \
  -p 6379:6379 \
  redis:7-alpine
```

#### Redis Cluster(生产)

```bash
docker run -d --name redis -p 6379:6379 \
  -e REDIS_CLUSTER=yes \
  -e CLUSTER_ANNOUNCE_IP=10.0.0.10 \
  redis:7-alpine redis-server --cluster-enabled yes
```

#### MySQL(传统企业)

```sql
CREATE DATABASE juicefs;
CREATE USER 'juicefs'@'%' IDENTIFIED BY 'password';
GRANT ALL ON juicefs.* TO 'juicefs'@'%';
```

#### TiKV(超大集群)

需要先部署一个 TiKV 集群,通过 PD 地址访问。

### 3. 准备对象存储

JuiceFS 支持所有 S3 兼容的对象存储:

- AWS S3 / 阿里云 OSS / 腾讯云 COS / 华为云 OBS
- MinIO / Ceph RADOS Gateway
- Azure Blob / Google GCS

创建一个 bucket 即可(无需额外配置)。

---

## 四、格式化与挂载

### 1. 格式化(创建文件系统)

```bash
juicefs format \
  --storage s3 \
  --bucket https://s3.us-west-1.amazonaws.com/mybucket \
  --access-key AKIA... \
  --secret-key '...' \
  redis://10.0.0.10:6379/1 \
  myjfs
```

参数说明:

| 参数 | 含义 |
| --- | --- |
| `--storage` | 对象存储类型:`s3`、`oss`、`cos`、`gs`、`azblob` 等 |
| `--bucket` | bucket 地址,可以是 S3 endpoint + path |
| `--access-key` / `--secret-key` | 对象存储的 AK/SK |
| `redis://...` | 元数据引擎 URL(也支持 `mysql://`、`tikv://`) |
| `myjfs` | 卷名(全局唯一) |

格式化只创建一次,后续挂载直接用 `juicefs mount` 即可。

### 2. 简化:用环境变量

```bash
export ACCESS_KEY=AKIA...
export SECRET_KEY='...'
export BUCKET=https://s3.us-west-1.amazonaws.com/mybucket

juicefs format --storage s3 redis://10.0.0.10:6379/1 myjfs
```

### 3. 挂载

#### 基础挂载

```bash
mkdir -p /mnt/jfs
juicefs mount --no-update redis://10.0.0.10:6379/1 /mnt/jfs
```

#### 生产推荐参数

```bash
juicefs mount \
  --no-update \
  --cache-dir /var/jfs/cache \
  --cache-size 102400 \
  --free-space-ratio 0.15 \
  --buffer-size 300 \
  --max-uploads 50 \
  --writeback \
  redis://10.0.0.10:6379/1 \
  /mnt/jfs
```

#### 开机自动挂载(systemd)

```bash
# juicefs 自动生成 systemd 单元
sudo juicefs mount \
  -o "cache-dir=/var/jfs/cache,cache-size=102400" \
  redis://10.0.0.10:6379/1 /mnt/jfs

# 或手动创建 /etc/systemd/system/jfs.service
cat > /etc/systemd/system/jfs.service <<EOF
[Unit]
Description=JuiceFS Mount
After=network-online.target
Wants=network-online.target

[Service]
Type=forking
ExecStart=/usr/local/bin/juicefs mount --no-update --cache-dir=/var/jfs/cache redis://10.0.0.10:6379/1 /mnt/jfs
ExecStop=/bin/umount /mnt/jfs
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now jfs
```

### 4. 验证

```bash
# 查看挂载信息
mount | grep juicefs

# 测试读写
echo "hello juicefs" > /mnt/jfs/test.txt
cat /mnt/jfs/test.txt
ls -lh /mnt/jfs/

# 查看 JuiceFS 卷信息
juicefs status redis://10.0.0.10:6379/1

# 查看客户端统计
juicefs stats /mnt/jfs
```

---

## 五、客户端使用

### 1. POSIX 文件操作

挂载后,JuiceFS 就是一个普通目录:

```bash
# 创建文件
echo "data" > /mnt/jfs/data.txt

# 复制大文件
cp big-file.bin /mnt/jfs/

# 创建目录
mkdir -p /mnt/jfs/projects/{app1,app2}

# 权限管理
chmod 755 /mnt/jfs/script.sh

# 软链接
ln -s /mnt/jfs/data /tmp/data

# 查看文件系统
df -h /mnt/jfs
du -sh /mnt/jfs/
```

### 2. 常用 CLI 命令

```bash
# 查看所有 JuiceFS 卷(基于 metacli)
juicefs status redis://10.0.0.10:6379/1

# 实时统计读写流量
juicefs stats /mnt/jfs

# 配置文件管理
juicefs config redis://10.0.0.10:6379/1 --trash-days 7

# 查看对象存储占用情况
juicefs rmr /mnt/jfs/large_dir    # 递归删除(可走回收站)

# 预热数据(把对象存储数据加载到本地缓存)
juicefs warmup /mnt/jfs/dataset/

# 清除本地缓存
juicefs gc /mnt/jfs              # 释放未引用的缓存
juicefs cache-validate /mnt/jfs  # 验证缓存有效性
```

### 3. 多客户端共享

所有挂载同一个元数据引擎和对象存储的客户端,看到的是同一份数据:

```bash
# 客户端 A
juicefs mount redis://10.0.0.10:6379/1 /mnt/jfs
echo "clientA" > /mnt/jfs/from-a.txt

# 客户端 B(同一时刻)
juicefs mount redis://10.0.0.10:6379/1 /mnt/jfs
cat /mnt/jfs/from-a.txt    # 立刻可见(秒级延迟)
```

---

## 六、缓存机制

JuiceFS 客户端自带多级缓存,大幅提升读性能。

### 1. 缓存目录

```bash
# 多个缓存目录(逗号分隔)
juicefs mount \
  --cache-dir /var/jfs/cache1,/var/jfs/cache2 \
  redis://10.0.0.10:6379/1 /mnt/jfs

# 缓存大小(MB), 0 表示无限制
--cache-size 102400

# 当磁盘剩余空间低于该比例时,停止写入缓存
--free-space-ratio 0.15
```

### 2. 写回模式(Writeback)

`--writeback` 让客户端先把数据写入本地内存和缓存,再异步上传到对象存储。提高写吞吐,但崩溃有数据丢失风险。

```bash
juicefs mount --writeback redis://10.0.0.10:6379/1 /mnt/jfs
```

### 3. 预读(Read-ahead)

提升顺序读性能:

```bash
--buffer-size 300   # 预读大小(MB), 默认 300
```

### 4. 缓存观察与调优

```bash
# 实时统计(每秒刷新)
watch juicefs stats /mnt/jfs

# 输出示例:
#   used cache:    12.34 GiB
#   used inode:     12345
#   read QPS:      100
#   write QPS:     50
#   read BPS:      120 MB/s
#   write BPS:     30 MB/s
```

---

## 七、压缩、加密、去重

### 1. 压缩

格式化时指定:

```bash
juicefs format \
  --compression lz4 \      # lz4 / zstd / snappy
  ...
```

支持的算法:

| 算法 | 压缩比 | CPU | 速度 |
| --- | --- | --- | --- |
| `none` | 1.0x | 0 | 最快 |
| `lz4` | 2.1x | 极低 | 极快 |
| `zstd` | 2.7x | 中 | 快 |
| `snappy` | 2.0x | 低 | 极快 |

> 推荐 `zstd`(平衡压缩比与速度)或 `lz4`(极致速度)。

### 2. 加密

格式化时指定加密密钥(客户端本地保存,不上传对象存储):

```bash
# 交互式输入密码
juicefs format --encryptor aes256-cbc ...

# 或用环境变量
export JFS_ENCRYPT_KEY='mypassword123'

# 挂载时也要提供
juicefs mount redis://10.0.0.10:6379/1 /mnt/jfs
```

> 如果忘记加密密钥,文件**无法恢复**!请妥善备份。

### 3. 去重

JuiceFS 默认在 **块(Block)** 级别做去重:相同内容的 Block 在对象存储里只存一份,通过引用计数。重复数据(机器学习数据集、备份)节省显著。

---

## 八、回收站与快照

### 1. 回收站

```bash
# 设置回收站保留时间(天)
juicefs config redis://10.0.0.10:6379/1 --trash-days 7

# 启用 / 禁用回收站
juicefs config redis://10.0.0.10:6379/1 --enable-trash true

# 查看回收站内容
ls /mnt/jfs/.trash/

# 恢复文件
mv /mnt/jfs/.trash/2025-01-01/data.txt /mnt/jfs/

# 彻底清空回收站
juicefs rmr /mnt/jfs/.trash/
```

### 2. 快照(Snapshot)

JuiceFS 支持目录级快照(基于 copy-on-write):

```bash
# 创建快照
mkdir /mnt/jfs/.snapshot/2025-01-01
cp -a /mnt/jfs/project/* /mnt/jfs/.snapshot/2025-01-01/

# 也可以用 juicefs snapshot 命令
juicefs snapshot redis://10.0.0.10:6379/1 /mnt/jfs/project /mnt/jfs/.snapshot/2025-01-01
```

---

## 九、Kubernetes CSI 集成

### 1. 安装 CSI

```bash
# 添加 helm repo
helm repo add juicefs https://juicedata.github.io/juicefs-helm-charts
helm repo update

# 安装
helm install juicefs juicefs/juicefs-csi-driver \
  --namespace kube-system \
  --set storageClass.enabled=true
```

### 2. 创建 Secret(挂载凭证)

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: juicefs-secret
  namespace: kube-system
type: Opaque
stringData:
  metaurl: redis://10.0.0.10:6379/1
  bucket: https://s3.us-west-1.amazonaws.com/mybucket
  access-key: AKIA...
  secret-key: '...'
```

### 3. StorageClass

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: juicefs
provisioner: csi.juicefs.com
parameters:
  csi.storage.k8s.io/provisioner-secret-name: juicefs-secret
  csi.storage.k8s.io/provisioner-secret-namespace: kube-system
  csi.storage.k8s.io/node-publish-secret-name: juicefs-secret
  csi.storage.k8s.io/node-publish-secret-namespace: kube-system
reclaimPolicy: Retain
volumeBindingMode: Immediate
mountOptions:
  - cache-dir=/var/jfs/cache
  - cache-size=102400
  - buffer-size=300
```

### 4. PVC 使用

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: jfs-pvc
spec:
  storageClassName: juicefs
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 100Gi
```

### 5. Pod 挂载

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: ai-training
spec:
  containers:
  - name: trainer
    image: tensorflow/tensorflow:2.15-gpu
    volumeMounts:
    - name: dataset
      mountPath: /data
    resources:
      requests:
        nvidia.com/gpu: 1
  volumes:
  - name: dataset
    persistentVolumeClaim:
      claimName: jfs-pvc
```

> 🔥 **ReadWriteMany(RWX)** 是 JuiceFS 的强项:多个 Pod 同时读写同一份数据,适合分布式训练。

### 6. 动态配置(免 Secret)

使用 [JuiceFS 商业版](https://juicefs.com/)或自建 token 服务,可以用 `volumes:` 形式内嵌配置。

---

## 十、跨区域与数据复制

### 1. 镜像(挂载只读)

```bash
# 把远端 JuiceFS 镜像到本地(只读)
juicefs mount --no-update \
  --read-only \
  redis://remote-meta:6379/1 /mnt/jfs-mirror
```

### 2. 数据迁移(juicefs sync)

类似 `rsync`,在两个文件系统间同步数据:

```bash
# 本地 JuiceFS → 远程 S3
juicefs sync \
  redis://src-meta:6379/1/dataset/ \
  s3://my-bucket/backup/

# 远程 S3 → 本地 JuiceFS
juicefs sync \
  s3://my-bucket/source/ \
  redis://dst-meta:6379/1/dataset/

# JuiceFS → JuiceFS(跨集群)
juicefs sync \
  redis://meta1:6379/1/ \
  redis://meta2:6379/1/

# 多线程/多并发
juicefs sync --threads 50 --buffer-size 200 \
  redis://src:6379/1/data \
  redis://dst:6379/1/data
```

支持的源/目标:

| 类型 | 是否支持 |
| --- | --- |
| 本地文件系统 | ✅ |
| JuiceFS | ✅ |
| S3 / S3-compatible | ✅ |
| OSS / COS / GCS | ✅ |
| HDFS | ✅ |
| WebDAV | ✅ |
| SFTP | ✅ |

### 3. 双向同步

```bash
# 注意:双向同步有冲突风险,谨慎使用
juicefs sync --force-update \
  redis://meta1:6379/1/ \
  redis://meta2:6379/1/
```

---

## 十一、数据加密备份与生命周期

### 1. 通过 S3 生命周期管理冷数据

JuiceFS 数据存于对象存储,直接利用云厂商的对象存储生命周期:

- **AWS S3 / 阿里云 OSS** 都有 Lifecycle Rule,可以把 Object 转 Glacier / 归档存储,大幅降低成本。
- JuiceFS 读归档数据时,客户端会自动触发解冻(对象存储厂商计费)。

### 2. 数据加密

- 客户端加密(`--encryptor`):数据加密后写入对象存储,服务端拿到的是密文。
- 服务端加密(SSE):依赖对象存储厂商的 SSE-KMS。
- 两种加密可叠加使用(客户端加密 + 服务端加密)。

---

## 十二、性能优化

### 1. 块大小调优

```bash
# 格式化时指定
juicefs format --block-size 4096 ...    # 默认 4MB
```

- **大文件**(视频、数据湖):调大到 8MB 或 16MB,减少对象数。
- **小文件**(图片、配置):保持 4MB 或更小。

### 2. 缓存调优

```bash
--cache-dir /data/jfs-cache    # 用高速磁盘(本地 NVMe)
--cache-size 204800             # 200 GB
--free-space-ratio 0.1         # 至少留 10% 磁盘空间
--buffer-size 300              # 预读大小,大文件顺序读可调大
```

### 3. 上传并发

```bash
--max-uploads 50               # 并发上传分片数
--max-parallel 20              # 单文件并发上传
--upload-limit 100             # 全局上传带宽限制(MB/s)
```

### 4. 内存

JuiceFS 客户端是 Go 进程,默认吃内存不大;但启用 writeback 时,内存会被缓存占用。可以限制:

```bash
--buffer-size 300              # 内存中的写缓冲(MB)
```

### 5. 元数据引擎性能

| 引擎 | 适用规模 | 元数据 QPS | 单文件延迟 |
| --- | --- | --- | --- |
| Redis 单机 | < 1M 文件 | 10w+ | 0.5ms |
| Redis Cluster | < 100M 文件 | 100w+ | 1ms |
| TiKV | PB 级,亿级文件 | 10w+ | 5~10ms |
| MySQL | 中小规模 | 1w+ | 5~10ms |

### 6. 性能对比(参考)

| 操作 | JuiceFS(Cache 命中) | JuiceFS(对象存储) | 本地 NVMe |
| --- | --- | --- | --- |
| 顺序读 | 1.5 GB/s | 200 MB/s | 3 GB/s |
| 顺序写 | 1.0 GB/s | 150 MB/s | 2 GB/s |
| 随机读 4KB | 50K IOPS | 5K IOPS | 200K IOPS |
| 元数据操作 | 10w/s | - | 100w/s |

---

## 十三、监控与运维

### 1. Prometheus 指标

JuiceFS 客户端暴露 Prometheus 指标(`/metrics`,默认端口 9567):

```bash
juicefs mount \
  --metrics 0.0.0.0:9567 \
  redis://10.0.0.10:6379/1 /mnt/jfs
```

主要指标:

| 指标 | 说明 |
| --- | --- |
| `juicefs_used_cache_size` | 已用缓存大小 |
| `juicefs_used_inodes` | 已用 inode 数 |
| `juicefs_read_qps` / `juicefs_write_qps` | 读写 QPS |
| `juicefs_read_bw_bytes` / `juicefs_write_bw_bytes` | 读写带宽 |
| `juicefs_object_request_count` | 对象存储请求数 |

### 2. Grafana Dashboard

官方提供 Grafana Dashboard JSON,导入即可,地址: `https://github.com/juicedata/juicefs/blob/main/docker/grafana/dashboards/juicefs.json`

### 3. 调试日志

```bash
juicefs mount --no-update \
  --log-level debug \
  --log-rotate 3 \
  redis://10.0.0.10:6379/1 /mnt/jfs

# 日志路径
ls /var/log/juicefs/
# 或
ls $HOME/.juicefs/
```

### 4. 健康检查

```bash
# 查看文件系统状态
juicefs status redis://10.0.0.10:6379/1

# 查看客户端运行信息
juicefs stats /mnt/jfs

# 监控特定目录
juicefs debug /mnt/jfs/project
```

---

## 十四、与其他系统集成

### 1. Hadoop / Spark / Hive

```xml
<!-- core-site.xml -->
<configuration>
    <property>
        <name>fs.jfs.impl</name>
        <value>io.juicefs.JuiceFSFileSystem</value>
    </property>
    <property>
        <name>juicefs.meta</name>
        <value>redis://10.0.0.10:6379/1</value>
    </property>
    <property>
        <name>juicefs.bucket</name>
        <value>https://s3.us-west-1.amazonaws.com/mybucket</value>
    </property>
    <property>
        <name>juicefs.access-key</name>
        <value>AKIA...</value>
    </property>
    <property>
        <name>juicefs.secret-key</name>
        <value>...</value>
    </property>
</configuration>
```

```bash
# Spark 读 JuiceFS
spark.read.parquet("jfs://myjfs/dataset/")
```

### 2. S3 Gateway

把 JuiceFS 暴露成 S3 兼容 API(适合已有 S3 SDK 的应用):

```bash
docker run -d --name juicefs-s3-gateway \
  -p 9000:9000 \
  -e META_URL=redis://10.0.0.10:6379/1 \
  -e BUCKET=https://s3.us-west-1.amazonaws.com/mybucket \
  -e AK=AKIA... \
  -e SK=... \
  juicedata/juicefs-s3-gateway
```

### 3. Python SDK

```python
import juicefs

# 客户端 API(无需挂载)
jfs = juicefs.Client(
    metaurl='redis://10.0.0.10:6379/1',
    bucket='https://s3.us-west-1.amazonaws.com/mybucket',
    access_key='...',
    secret_key='...',
    name='myjfs'
)

# 列出目录
for entry in jfs.ls('/'):
    print(entry['Name'], entry['Size'])

# 上传
jfs.put('local_file.txt', '/remote_file.txt')

# 下载
jfs.get('/remote_file.txt', 'local_file.txt')
```

### 4. S3 API(FUSE 暴露)

JuiceFS 客户端支持 S3 网关模式,允许通过 S3 API 访问 JuiceFS。

---

## 十五、Quota(配额)

```bash
# 设置目录配额(GB)
juicefs quota set /mnt/jfs/projects 1000

# 查看配额
juicefs quota get /mnt/jfs/projects
```

---

## 十六、ACL 与权限

JuiceFS 支持 POSIX ACL 和基于 UGO 的传统权限:

```bash
# 传统方式
chown alice:devops /mnt/jfs/project
chmod 750 /mnt/jfs/project

# ACL 方式
setfacl -m u:alice:rwx /mnt/jfs/project
setfacl -m g:devops:r-x /mnt/jfs/project
getfacl /mnt/jfs/project
```

权限基于 uid/gid,所以容器挂载时建议显式设置 `runAsUser`:

```yaml
securityContext:
  runAsUser: 1001
  runAsGroup: 1001
  fsGroup: 1001
```

---

## 十七、常见问题与排查

### 1. mount 失败

```bash
# 查看日志
juicefs mount --log-level debug ... 2>&1 | tee mount.log

# 常见原因:
# - redis 连接不上 → telnet 10.0.0.10 6379
# - AK/SK 错误 → 用 s3cmd / aws s3 ls 验证
# - bucket 不存在或无权限
```

### 2. 性能慢

```bash
# 检查缓存命中率
juicefs stats /mnt/jfs
# 观察 cache hit/miss 比例

# 检查元数据延迟
juicefs status redis://10.0.0.10:6379/1
```

### 3. 磁盘空间满

```bash
# 检查缓存占用
du -sh /var/jfs/cache

# 清理未引用缓存
juicefs gc /mnt/jfs
```

### 4. 元数据引擎压力

```bash
# 查看 Redis 内存
redis-cli -h 10.0.0.10 info memory

# 如果 Redis 压力大,迁移到 TiKV
```

### 5. 数据损坏

JuiceFS 默认在对象存储中存 **校验和**,自动检测损坏。如发现:

```bash
# 查看坏块
juicefs debug /mnt/jfs/path

# 重建某个文件(慎用)
# juicefs rmr + juicefs put
```

### 6. FUSE 限制

JuiceFS 基于 FUSE,某些系统调用不支持:

- 不支持内存映射(MMAP)的随机写(只支持顺序读 mmap)。
- 不支持 direct IO。
- 部分工具(如 `parallel`)可能遇到 "Too many open files",需调大 `ulimit -n`。

---

## 十八、生产最佳实践

### 1. 资源规划

| 资源 | 推荐 |
| --- | --- |
| 元数据引擎 | TiKV 或 Redis Cluster,**绝不**用 Redis 单机存生产数据 |
| 对象存储 | 跨可用区 bucket,启用版本控制 |
| 客户端缓存盘 | 本地 NVMe,**不**用网络盘 |
| 客户端机器 | 8+ vCPU, 16+ GB 内存 |

### 2. 高可用

```bash
# Redis HA(主从 + Sentinel)
juicefs format \
  --metacache-size 1000 \
  redis-sentinel://sentinel1:26379,sentinel2:26379,sentinel3:26379/1/mymaster
```

### 3. 监控告警

关键告警项:

- 缓存命中率 < 80%
- 元数据引擎 CPU > 70%
- 对象存储 5xx 错误率 > 1%
- 单客户端 QPS > 1万

### 4. 安全

- AK/SK 通过 Secret / 环境变量注入,不要写入代码
- 启用客户端加密(`--encryptor aes256-cbc`)保护敏感数据
- 对象存储桶启用 SSE-KMS
- VPC 内网访问对象存储,避免公网出流量

### 5. 容量规划

| 业务 | 估算 | 元数据规模 |
| --- | --- | --- |
| 1PB 数据, 100KB 平均文件 | ~100亿文件 | TiKV 必选 |
| 100TB 数据, 1MB 平均文件 | ~1亿文件 | Redis Cluster |
| 10TB 数据, 100MB 平均文件 | ~10万文件 | MySQL 即可 |

---

## 十九、参考资料

- [JuiceFS 官方文档](https://juicefs.com/docs/)
- [JuiceFS GitHub](https://github.com/juicedata/juicefs)
- [JuiceFS 架构白皮书](https://juicefs.com/docs/community/architecture/)
- [JuiceFS CSI Driver](https://github.com/juicedata/juicefs-csi-driver)
- [JuiceFS Helm Charts](https://github.com/juicedata/juicefs-helm-charts)
- [社区案例:知乎自建 KV 替换 TiKV](https://juicefs.com/blog/)
- [CNCF 云原生存储白皮书](https://www.cncf.io/reports/storage-whitepaper/)