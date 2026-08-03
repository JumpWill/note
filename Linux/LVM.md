# LVM (Logical Volume Manager)

LVM 是 Linux 的逻辑卷管理子系统：在物理磁盘（PV, Physical Volume）之上抽象出 VG（卷组），再切分出 LV（逻辑卷），可以动态扩容、缩容、快照、镜像。替代了把整块物理磁盘直接分区的硬方式。

```text
物理磁盘 / 分区
   │
   ▼  pvcreate
  PV (Physical Volume)  /dev/sda1 /dev/sdb /dev/nvme0n1
   │
   ▼  vgextend
  VG (Volume Group)     vg_data
   │
   ▼  lvcreate
  LV (Logical Volume)   lv_root / lv_swap / lv_data
   │
   ▼  mkfs.xfs / mkfs.ext4
  文件系统
   │
   ▼  mount
  /   /data
```

## 1. 三层模型

| 概念 | 含义 | 设备文件 |
| ---- | ---- | -------- |
| **PV** | Physical Volume，物理卷，可以是整块磁盘 / 分区 / 块设备 | `/dev/sda1`, `/dev/nvme0n1` |
| **VG** | Volume Group，将多个 PV 组合为一个容量池 | `/dev/vg_data` |
| **LV** | Logical Volume，从 VG 切割出的逻辑卷 | `/dev/vg_data/lv_root` |
| **PE** | Physical Extent，PV 上划分的等大小块（默认 4 MiB） | — |
| **LE** | Logical Extent，LV 上的等大小块 | — |

```text
PE/LE 是 LVM 的最小存储单位
LV 的容量 = LE 数 × LE 大小
LV 跨多个 PV 时，分片 (striped) 行为
```

## 2. 安装与查看工具

```bash
# 核心命令
pvdisplay / pvs / pvcreate / pvremove / pvmove
vgdisplay / vgs / vgcreate / vgremove / vgextend / vgreduce / vgscan
lvdisplay / lvs / lvcreate / lvremove / lvextend / lvreduce / lvscan

# 工具
lvm                    # lvm> 提示符，所有命令交互
lvm dumpconfig         # 查看 /etc/lvm/lvm.conf
lvs -a                 # 显示内部 LV（cache、raid 等）
pvs --segments         # 显示 seg / extents
```

`/etc/lvm/lvm.conf`：主配置；`/etc/lvm/profile/`：内置 / 自定义 profile。

## 3. 创建 LV 全流程

```bash
# 1. 在物理盘上创建 PV
pvcreate /dev/sdb
pvcreate /dev/sdc

# 2. 创建 VG
vgcreate vg_data /dev/sdb /dev/sdc

# 3. 创建 LV
lvcreate -n lv_app -L 100G vg_data
# 或者用 extents：-l 100%FREE 分配 100% 空间

# 4. 创建文件系统
mkfs.xfs /dev/vg_data/lv_app

# 5. 挂载
mkdir /data
mount /dev/vg_data/lv_app /data
```

加 `/etc/fstab`：

```text
/dev/vg_data/lv_app   /data   xfs   defaults   0 0
```

## 4. 物理卷 PV

```bash
# 创建
pvcreate /dev/sdb
pvcreate /dev/sdc /dev/sdd

# 显示
pvs
pvdisplay /dev/sdb

# 移动
pvmove /dev/sdb

# 删除
pvremove /dev/sdb

# 重新分配 / 修复 PE
pvresize --setphysicalvolumesize 200G /dev/sdb

# 卷标签
pvchange --addtag ssd /dev/sdc
```

PV 占空间 = 1024 bytes metadata + 1 PE 在 metadata 内 + 其余。LVM 默认放 metadata 在 PV 头部。

## 5. 卷组 VG

### 5.1 创建 / 删除

```bash
vgcreate vg_data /dev/sdb /dev/sdc
vgextend vg_data /dev/sdd
vgreduce vg_data /dev/sdc       # 需要先 pvmove
vgremove vg_data                # 删前需删除所有 LV

# 显示
vgs
vgdisplay vg_data
```

### 5.2 VG 信息

```bash
vgdisplay vg_data
# VG Name                vg_data
# System ID
# Format                 lvm2
# Metadata Areas        3
# VG Size                <500 GiB
# PE Size                4.00 MiB
# Total PE               127999
# Alloc PE / Size        100000 / <390 GiB>
# Free  PE / Size        27999 / <109 GiB>
# VG UUID                ...
```

### 5.3 PE 大小

```bash
vgcreate -s 16M vg_data /dev/sdb
```

PE 越大对齐性能越好，但 LV 切粒度越粗。PE 大小在 vgcreate 时设定，整 VG 内一致。

### 5.4 元数据备份 / 修复

```bash
vgcfgbackup -f backup.vg vg_data     # 导出
vgcfgrestore -f backup.vg vg_data    # 恢复
vgcfgbackup vg_data                 # 默认导出到 /etc/lvm/backup

# 自动备份设置（lvm.conf）
backup {
  # 总是保留自动备份
}
```

## 6. 逻辑卷 LV

### 6.1 创建

```bash
# 大小
lvcreate -n lv_app -L 100G vg_data
lvcreate -n lv_data -l 100%FREE vg_data
lvcreate -n lv_swap -L 8G vg_data

# 类型（thin / raid / cache）
lvcreate -n lv_thin --type thin -L 100G vg_data/thinpool
lvcreate -n lv_raid --type raid1 -m 1 -L 50G vg_data
lvcreate -n lv_cache --type cache -L 100G vg_data/main --cachepool vg_data/cache

# 条带（性能）
lvcreate -n lv_striped -L 100G -i 2 -I 64 vg_data
```

### 6.2 显示

```bash
lvs
lvdisplay /dev/vg_data/lv_app
lvs -o +devices /dev/vg_data/lv_app
lvs --segments
```

### 6.3 扩展 / 缩小

```bash
lvextend -L +20G /dev/vg_data/lv_app       # 加 20G
lvextend -L 200G /dev/vg_data/lv_app         # 总大小 200G
lvextend -l +100%FREE /dev/vg_data/lv_app   # 占 VG 剩余空间

# 在线扩容 + 文件系统
lvextend -L +10G /dev/vg_data/lv_app
xfs_growfs /data             # xfs
resize2fs /dev/vg_data/lv_app   # ext4
```

缩容（要先缩 FS，再缩 LV）：

```bash
# ext4
umount /data
fsck -f /dev/vg_data/lv_app
resize2fs /dev/vg_data/lv_app 100G
lvreduce -L 100G /dev/vg_data/lv_app
mount /dev/vg_data/lv_app /data

# xfs 不支持缩容
```

### 6.4 删除 / 重命名

```bash
lvremove /dev/vg_data/lv_app
lvrename vg_data lv_app lv_main
```

### 6.5 类型转换

```bash
lvconvert --type thin vg_data/lv_main        # 转 thin
lvconvert -m 1 vg_data/lv_raid               # 加 mirror
lvconvert --thinpool vg_data/thinpool vg_data/lv_data   # 重组
```

## 7. 文件系统 + 挂载

```bash
mkfs.xfs /dev/vg_data/lv_app
mkfs.ext4 /dev/vg_data/lv_app
mount /dev/vg_data/lv_app /mnt

# 在线扩容
lvextend -L +10G /dev/vg_data/lv_app
xfs_growfs /mnt
resize2fs /dev/vg_data/lv_app
```

`/etc/fstab`：

```text
/dev/mapper/vg_data-lv_app  /data  xfs  defaults,noatime  0 0
```

`/dev/mapper/*` 与 `/dev/vg_data/lv_app` 是软链，等价。

## 8. Thin Provisioning（瘦分配）

Thin 是 LVM 的重要特性：

- Thin pool（虚拟化）= 大 PE，物理大小未必完全用满
- Thin LV（虚拟卷）= "逻辑上" 看起来 N GiB
- 实际占用 = pool 内被用到的部分

```bash
# 创建 thin pool
lvcreate -L 1T --type thin-pool -n thinpool vg_data

# 创建 thin LV
lvcreate -n lv_data --type thin -V 10T vg_data/thinpool
```

- 多 Thin LV 共享一个 Pool
- Pool 占满后 Thin LV 写入失败（IO error）
- 警告阈值：`lvchange --monitor y vg_data/thinpool`

```bash
dmsetup status | grep thin
lvs vg_data/thinpool -o data_percent,lv_name
```

## 9. Snapshot 快照

```bash
# 创建快照
lvcreate -L 10G -n snap_app -s /dev/vg_data/lv_app

# 快照是另一个 LV，可挂载做只读备份
mount -o ro /dev/vg_data/snap_app /mnt/snap

# 合并（销毁原 LV，回滚到快照）
lvconvert --merge /dev/vg_data/snap_app
```

Thin 快照：

```bash
lvcreate -kn -n snap_thin --type thin -s vg_data/lv_data
```

`--thin` thin snapshot 默认是 cow-on-write 占空间小。

## 10. RAID / 镜像 / Cache / 复制

### 10.1 镜像 (RAID1)

```bash
lvcreate -m 1 -L 50G vg_data -n lv_mirror
# 写法 1：单镜像
lvcreate -m 1 --type raid1 -L 50G vg_data -n lv_mirror

# 加镜像
lvconvert -m +1 vg_data/lv_mirror

# 移除镜像
lvconvert -m 0 vg_data/lv_mirror
```

### 10.2 RAID5 / 6

```bash
lvcreate --type raid5 -i 3 -L 100G vg_data -n lv_raid5
lvcreate --type raid6 -i 4 -L 100G vg_data -n lv_raid6
```

### 10.3 Thin Cache

```bash
lvcreate -L 100G -n cache_pool vg_data --type cache-pool
lvconvert --type cache --cachepool cache_pool vg_data/lv_main
lvconvert --splitcache vg_data/lv_main   # 脱离
```

cache + cachepool 用 fast SSD 做 read-through / write-back 加速机械盘。

### 11. 精简压缩 + 备份

**ZFS** 不算 LVM，但与 LVM-thin 一起用多：`zfs send/receive`、`zfs snapshot`。

### 12. 实战例子

#### 12.1 创建新盘全流程

```bash
lsblk                              # 看新磁盘
fdisk -l /dev/sdb
# 整盘做 PV（推荐 GPT + 整盘作为 PV）
pvcreate /dev/sdb

vgcreate vg_storage /dev/sdb

lvcreate -L 200G -n lv_media vg_storage
mkfs.xfs /dev/vg_storage/lv_media
mkdir /media
mount /dev/vg_storage/lv_media /media
echo '/dev/vg_storage/lv_media /media xfs defaults 0 0' >> /etc/fstab

# 监控
pvs ; vgs ; lvs
```

#### 12.2 在线扩容

```bash
# 新加盘
echo ' 100G' | tee /dev/sdd          # 给新盘 100G
pvcreate /dev/sdd
vgextend vg_storage /dev/sdd

# 扩容 LV
lvextend -L +100G /dev/vg_storage/lv_media
xfs_growfs /media
```

#### 12.3 迁移数据到新盘

```bash
# 旧 LV 在 sdb，要把数据移到 sdc 上
pvmove /dev/sdb
# VG 自动从 sdb 移到 sdc
```

#### 12.4 缩减空间

```bash
# 先缩 FS（ext4）
umount /data
e2fsck -f /dev/vg_data/lv_app
resize2fs /dev/vg_data/lv_app 50G
lvreduce -L 50G /dev/vg_data/lv_app

# 注意：xfs 不能缩
```

#### 12.5 备份与还原

```bash
# LV 镜像（自动备份）
lvcreate -s -L 10G -n snap_data vg_data/lv_data
# 备份 mount 上 read-only
mkdir /tmp/snap; mount -o ro /dev/vg_data/snap_data /tmp/snap
tar -czvf backup.tgz -C /tmp/snap .
umount /tmp/snap
lvremove vg_data/snap_data

# 灾难恢复：导出 + 重新导入
vgcfgbackup -f vg_data.bak vg_data
vgcfgrestore -f vg_data.bak vg_data
```

#### 12.6 Thin LV

```bash
lvcreate -L 100G --type thin-pool -n thinpool vg_data
lvcreate -n lv_proj -V 1T --type thin vg_data/thinpool

# 设置警示阈值
lvchange --monitor y vg_data/thinpool
```

监控：

```bash
lvs -o lv_name,data_percent vg_data
```

#### 12.7 镜像切换

```bash
lvcreate -m 1 --type raid1 -L 100G vg_data -n lv_raid1
# 模拟主 PV 失败：
# 取出 /dev/sdc，验证 PV 自动失效切换
```

#### 12.8 cache 加速

```bash
# SSD 做 cache
lvcreate -n cache_meta -L 100M vg_data --type cache-pool
# 把慢盘镜像作为主
lvcreate -L 1T vg_data -n lv_db
lvconvert --type cache --cachepool cache_meta vg_data/lv_db
```

## 12.5 优点与缺点

### 1. 优点

| 维度 | 描述 |
| ---- | ---- |
| **在线扩容** | 多数文件系统（xfs / ext4 / btrfs）支持 `lvextend` + `xfs_growfs` 而不需中断服务 |
| **缩容 / 重调容量** | ext4 可缩；xfs 不可缩 |
| **跨多盘拼合** | 多个 PV 组 VG，LV 跨盘；后期加入新盘不需重启 |
| **快照** | COW 快照支持快照即备份 / 测试环境克隆 |
| **Thin Provisioning** | 虚拟化层，可"超分配"以简化容量规划 |
| **逻辑卷迁移** | `pvmove` 在线迁移数据，物理盘可更换 |
| **RAID 集成** | LVM RAID1 / 5 / 6 / 10 在 LVM 层做，比 mdadm + LVM 更简洁 |
| **Cache 加速** | SSD cache pool 自动迁移热数据 |
| **跨多机一致性** | device-mapper 公开了统一 dmsetup，便于 OpenStack / K8s PV 接入 |
| **易于备份 / 重建** | metadata 备份 + 还原（`vgcfgbackup / vgcfgrestore`） |
| **可脚本化** | 全部命令友好，配合 Ansible / Terraform 可编程 |

### 2. 缺点

| 维度 | 描述 |
| ---- | ---- |
| **启动依赖** | 必须先把 LVM metadata 加载；ramfs / initramfs 配置出错可让系统挂掉 |
| **不可移植到 Windows** | NTFS / ReFS 看不到；移动盘多 OS 读取困难 |
| **性能开销** | 透过多一层 device-mapper，I/O 路径增加 5–15%（极少见且单层） |
| **元数据损坏危险** | VG metadata 损坏 + 没有备份 = 数据全失 |
| **快照过载（heavy use）** | 大量快照会撑爆 thin pool，写阻塞 |
| **复杂运维** | Thin / RAID / Cache 混合后的故障排查比裸盘难度大 |
| **加密集成慢** | LUKS on LVM 比 LUKS 直接 + ext4 启动慢 |
| **PXE / LiveCD 升级风险** | 旧 initramfs 不识别新 LVM，常见机房踩坑 |
| **可观察性 / 监控** | 需要 dm、lvs、pvmove 等多 tool，非一站式 |
| **跨主机 cluster** | 需 OCFS2 / GFS2 共享存储，普通文件系统不直接支持 |
| **冷启动 + 系统盘** | 根目录或 `/boot` 不能直接 LVM，要单独 `/boot` 分区 |
| **缓存 / Thin 与生产监控不足** | 占满、慢盘失败等情况需要专门的监控 |

### 3. 与裸盘 / ZFS / 硬件 RAID 对比

| 维度 | 裸盘 + 分区 | LVM | ZFS | 硬件 RAID |
| ---- | ------------ | --- | --- | --------- |
| 灵活扩容 | ✘ | ✔ | ✔（zpool） | ✘ |
| 跨多盘 | ✘ | ✔ | ✔ | 部分 |
| 快照 | ✘ | ✔ | ✔ | 取决于硬件 |
| 校验 / 写安全 | ✘ | ✘（除非 md + RAID） | ✔（checksum） | 取决于 |
| 加密 | dmcrypt | LUKS | ✔（zfs） | 厂商 |
| 性能开销 | ✘ | ~5–10% | ~10% | ✘ |
| 启动独立 | ✔ | 复杂 | 复杂 | 简单 |
| 学习曲线 | 简单 | 中 | 中高 | 中 |

### 4. 何时该用 / 不该用

| 场景 | 推荐 |
| ---- | ---- |
| 服务器存储变化频繁（数据库 / 应用） | **LVM + RAID** |
| 单块盘 / 单机使用 | 裸盘 + 分区 |
| 多节点 NAS | **ZFS** |
| 高密度容器存储 | **LVM Thin + OpenEBS / Longhorn** |
| 边缘 / IoT | 裸盘 |
| 大数据 + 集群 | **ZFS / Lustre / GlusterFS** |
| 私有云底层 | **LVM + Ceph RBD** |

### 5. 与 K8s 集成

```text
HostLVM
   ├── vg_storage
   │     ├── lv_data_thin_pool  ← thin pool
   │     └── lv_data            ← thin LV (mounted at /var/lib/kubelet)
   └── K8s local PV on this LVM
```

Host 上 LVM 配置好，K8s 用 local-path storageclass。

### 6. 一句话总结

```text
LVM 优点：
  - 灵活（在线扩容 / 缩容 / 快照 / 镜像 / cache）
  - 多盘池化 / 数据迁移

缺点：
  - 启动依赖 / 元数据损坏危险 / 跨 OS 不便
  - 单层 DM 性能损耗（轻微）
  - 复杂运维 / 不易恢复
```

## 13. lvm.conf 关键选项

```text
# 锁定
locking_type = 1              # flock
# 备份
backup {
    backup_archive_enable = 1
    backup_dir = "/etc/lvm/backup"
}
# 元数据
metadata {
    pvmetadatasize = 1024
}
# 设备扫描
devices {
    filter = ...
}
```

`filter` 影响 LVM 找到哪些设备，多 path / SAN 场景必用。

## 14. 与 RAID / ZFS / 文件系统集成

| 场景 | 选择 |
| ---- | ---- |
| 单盘 + 灵活分区 | LVM |
| 多盘 RAID | LVM RAID 或 mdadm + LVM |
| 容量校验 | ZFS（独立 + LVM） |
| 加密 | LUKS on top of LVM |
| 网络存储 | iSCSI + LVM |
| K8s | kubelet 与 PV / VG 无关 |
| 虚拟机 | qemu-img over thin LV |

## 15. 安全 / 备份

```bash
# 元数据自动备份
vgcfgbackup vg_data             # 写在 /etc/lvm/backup/vg_data
ls -la /etc/lvm/backup

# 备份传输
rsync -av /etc/lvm/backup/ bkp_server:/etc/lvm/backup/

# crypt 备份（防泄漏 metadata）
dd if=/dev/sdc bs=512 count=1 of=metadata.bin
```

## 16. 常见排错

| 现象 | 排查 |
| ---- | ---- |
| VG 失踪 | `vgscan` / `lvm vgscan` |
| PV miss | `pvscan` |
| LV 锁 | `lvm pvmove` 失败 |
| I/O error | `dmesg` |
| thin pool 占满 | `lvs -o data_percent` |
| raid 同步 | `lvs -o sync_percent` |
| 替换 PV | `pvmove + pvremove` |
| ext4 resize 失败 | `e2fsck -f` |
| 重启找不到 LV | 确认 `lvmetad` + initramfs |

## 17. 与 Docker / K8s 集成

LVM 在容器里不直接使用，但 host 上 LVM 提供的磁盘是底层存储：

- K8s local-storage PV：本地 LVM Thin Pool
- OpenEBS / MAYA / Longhorn：建在 LVM 之上
- Portworx / Rook + Ceph：先 LVM 后 Ceph

```bash
docker volume create --driver local --opt type=devicemapper --opt device=/dev/vg_data/lv_app data_vol
```

## 18. 与加密（LUKS）

```bash
cryptsetup luksFormat /dev/vg_data/lv_secret
cryptsetup open /dev/vg_data/lv_secret sec_open
mkfs.xfs /dev/mapper/sec_open
```

也可以对 PV 加密（LUKS on PV），但较少见。

## 19. 一句话总结

```text
LVM = PV 池化 (VG) 再切片 (LV)
PV / VG / LV / PE 概念
可在线扩容 / 缩容 / 快照 / 镜像 / thin / cache
关键命令：pvs / vgs / lvs / vgextend / lvextend
```

## 20. 参考

- `man 5 lvm.conf`
- `man 8 pvcreate / vgcreate / lvcreate`
- `man 8 pvmove / pvreduce`
- `man 8 lvm`
- `man 8 lvmconfig`
- `man 8 lvs / vgs / pvs`
- `man 8 dmsetup`
- Linux kernel: `Documentation/admin-guide/devices.rst`
- Linux LVM GitHub: [https://github.com/lvmteam/lvm2](https://github.com/lvmteam/lvm2)