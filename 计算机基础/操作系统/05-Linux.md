# Linux 操作系统

## 一、Linux 概述

### Linux 是什么

**Linux** 是一个**开源、免费**的类 Unix 操作系统内核,由芬兰赫尔辛基大学的 **Linus Torvalds** 于 **1991 年**首次发布。

- **严格定义**:Linux 指 **内核 (Kernel)**
- **广义**:Linux 指基于 Linux 内核的**整个操作系统生态 (GNU/Linux)**

### Linux 的组成

Linux 操作系统 = **Linux 内核** + **GNU 工具** + **桌面环境** + **应用软件**

```text
┌──────────────────────────────┐
│     应用软件                  │
│   (Firefox、LibreOffice)      │
├──────────────────────────────┤
│     桌面环境 / Shell          │
│   (GNOME / bash)              │
├──────────────────────────────┤
│   GNU 工具 + 库 (glibc)       │
│  (coreutils、gcc、bash)       │
├──────────────────────────────┤
│     Linux 内核                │
│  (进程/内存/文件/网络/驱动)  │
├──────────────────────────────┤
│     硬件                      │
└──────────────────────────────┘
```

**GNU 是什么**:GNU = "GNU's Not Unix",目标是做一个**完全自由**的 Unix 兼容系统。1992 年 Linux 内核和 GNU 用户空间工具结合,形成完整的 GNU/Linux 系统。

### Linux 核心特点

| 特点         | 说明                                              |
|--------------|---------------------------------------------------|
| 自由开源     | GPL 协议,源代码公开,可自由使用、修改、分发        |
| 多用户多任务 | 同时多人使用,每用户可同时跑多任务                 |
| 稳定可靠     | 可连续运行数年不重启(服务器)                      |
| 安全         | 权限管理严格,漏洞影响范围小                       |
| 跨平台       | 支持 x86、ARM、MIPS、RISC-V、PowerPC 等           |
| 模块化       | 内核可加载/卸载模块,灵活扩展                      |
| 强大的网络   | 网络协议栈完善,网络功能丰富                       |
| 丰富的发行版 | 数百种发行版,满足各种场景                         |

---

## 二、Linux 内核

### 内核版本号

**格式**:`主版本.次版本.修订号-发布次数`

- 例:Linux 6.6.21-1
- **主版本**:重大变化(目前是 6)
- **次版本**:奇数 = 开发版,偶数 = 稳定版(2.6.x 之后此规则不再严格)
- **修订号**:错误修复次数
- **发布次数**:发行版打包次数

### 内核架构 (单内核 + 模块化)

```text
┌──────────────────────────────────┐
│        系统调用接口 (SCI)         │
├──────────────────────────────────┤
│  进程管理 │ 内存管理 │ VFS        │
│  网络栈   │ 设备驱动 │ IPC        │
├──────────────────────────────────┤
│       体系结构相关代码            │
├──────────────────────────────────┤
│          硬件                     │
└──────────────────────────────────┘
```

### 内核子系统

- **进程调度 (Scheduler)**:CFS (Completely Fair Scheduler)
- **内存管理 (MM)**:虚拟内存、页表、SLAB/SLUB 分配器
- **虚拟文件系统 (VFS)**:Ext4、XFS、Btrfs 等的统一接口
- **网络栈**:TCP/IP、Netfilter、Socket
- **设备驱动**:块设备、字符设备、网络设备
- **进程间通信**:信号、管道、共享内存、消息队列
- **内核模块 (Module)**:可动态加载/卸载 (.ko 文件)

### 内核源码结构

```text
linux/
├── arch/          # 架构相关代码(x86、arm、riscv)
├── block/         # 块 IO 层
├── drivers/       # 设备驱动
├── fs/            # 文件系统
├── include/       # 头文件
├── init/          # 初始化
├── ipc/           # 进程间通信
├── kernel/        # 核心(调度、信号等)
├── lib/           # 库函数
├── mm/            # 内存管理
├── net/           # 网络
├── security/      # 安全模块 (SELinux、AppArmor)
├── sound/         # 声卡
└── tools/         # 工具
```

### 主流内核版本

| 版本 | 发布时间 | 重要特性                                       |
|------|----------|------------------------------------------------|
| 0.01 | 1991     | 第一版                                         |
| 1.0  | 1994     | 首个正式版                                     |
| 2.0  | 1996     | 支持多处理器                                   |
| 2.2  | 1999     | 大幅提升性能                                   |
| 2.4  | 2001     | 更好的 NTFS、RAID 支持                         |
| 2.6  | 2003     | 长寿版本(2003-2011)                            |
| 3.x  | 2011     | 跨平台统一,无数不枚举的设备支持                |
| 4.x  | 2015     | 新文件系统、设备树                             |
| 5.x  | 2019     | io_uring、WireGuard、多种新硬件支持            |
| 6.x  | 2022     | Rust 驱动、改进调度器,新硬件支持               |

---

## 三、Linux 发行版 (Distribution)

### 1. 发行版的本质

**发行版 = Linux 内核 + 包管理器 + 软件仓库 + 默认配置 + 桌面环境 + 安装程序**

不同发行版的区别主要在:

- **包管理器**(格式:deb、rpm、txz 等)
- **软件仓库**(源)
- **更新策略**(滚动/固定)
- **默认桌面环境**(GNOME、KDE、XFCE 等)
- **企业支持模式**(商业 vs 社区)

### 2. 发行版的两大家族

| 项目         | Debian 系 (Debian-based)            | Red Hat 系 (RHEL-based)                |
|--------------|-------------------------------------|----------------------------------------|
| 包格式       | .deb (dpkg)                         | .rpm (rpm)                             |
| 包管理器     | apt / apt-get                       | yum / dnf                              |
| 软件源       | /etc/apt/sources.list               | /etc/yum.repos.d/                      |
| 库           | glibc                               | glibc                                  |
| 默认桌面     | GNOME                               | GNOME                                  |
| 防火墙       | ufw / iptables                      | firewalld                              |
| 服务管理     | systemd                             | systemd                                |
| 代表发行版   | Debian、Ubuntu、Linux Mint、Kali    | RHEL、CentOS、Fedora、Rocky、AlmaLinux |
| 适合         | 服务器、桌面                        | 企业服务器                             |

**第三大族:SUSE 系 (SUSE 系)**
- 包格式:.rpm
- 包管理器:zypper
- 代表:openSUSE、SLES

**第四大族:Arch 系**
- 包格式:pkg.tar.zst (pacman)
- 代表:Arch Linux、Manjaro

**第五大族:独立派**
- Gentoo (portage)
- Slackware
- Alpine (apk,musl,极小)

### 3. 主要 Linux 发行版详解

#### (1) Debian

- **历史**:1993 年由 Ian Murdock 创建
- **特点**:最古老、最稳定、最纯粹的 Linux 发行版
- **口号**:"Universal Operating System"
- **软件包**:超过 5 万个
- **稳定版周期**:每 2 年左右
- **适合**:服务器、追求稳定的用户
- **官网**:debian.org
- **著名衍生**:Ubuntu、Kali、Linux Mint、Raspbian

#### (2) Ubuntu

- **历史**:2004 年由 Mark Shuttleworth (Canonical) 创建
- **特点**:基于 Debian,最流行的桌面 Linux
- **版本周期**:每 6 个月一个版本,每 2 年一个 LTS(长期支持)版
- **当前 LTS**:24.04 (Noble Numbat),支持 5 年
- **桌面**:GNOME
- **衍生**:
  - **Kubuntu**:KDE 桌面
  - **Xubuntu**:XFCE 桌面
  - **Lubuntu**:LXQt 桌面(轻量)
  - **Ubuntu Server**:无桌面
  - **Ubuntu Cloud**:云端优化
  - **Ubuntu Core**:IoT/嵌入式
- **适合**:入门用户、桌面、服务器
- **公司**:Canonical(英国)

#### (3) Linux Mint

- **历史**:2006 年发布
- **特点**:基于 Ubuntu,**最像 Windows 的 Linux**
- **桌面**:Cinnamon、MATE、Xfce
- **适合**:从 Windows 迁移的用户、新手

#### (4) Red Hat Enterprise Linux (RHEL)

- **历史**:1995 年由 Red Hat 公司发布
- **特点**:**企业级 Linux 标杆**,商业支持
- **费用**:订阅制(年费)
- **支持周期**:10 年
- **版本**:RHEL 9 (基于 Fedora 36)
- **认证**:大量硬件和软件厂商认证
- **适合**:大型企业、金融、电信、政府
- **公司**:Red Hat(IBM 旗下)

#### (5) CentOS

- **历史**:原本是 RHEL 的社区免费克隆
- **CentOS Linux 8 (2021 年底 EOL)**:已死
- **CentOS Stream**:现在是 RHEL 上游,**滚动更新**,有"未来版本"性质
- **适合**:测试、CI/CD、不适合生产关键系统

#### (6) Rocky Linux / AlmaLinux

- **历史**:CentOS 8 EOL 后,由原 CentOS 创始人 Gregory Kurtzer 发起
- **特点**:**RHEL 的 1:1 社区免费克隆**,二进制兼容
- **适合**:需要 RHEL 兼容但不想付费的企业
- **现状**:CentOS 8/9 EOL 后的首选替代

#### (7) Fedora

- **历史**:Red Hat 社区版
- **特点**:**RHEL 的上游**,新技术的试验场
- **版本周期**:6 个月
- **支持周期**:13 个月(版本) + 延长
- **适合**:开发者、桌面、技术爱好者
- **新特性首发**:Wayland、Systemd、Podman、Btrfs 等都在 Fedora 首推

#### (8) openSUSE

- **历史**:SUSE 的社区版
- **特点**:稳定性好,YaST 配置工具强大
- **分支**:
  - **Leap**:稳定版(基于 SLE)
  - **Tumbleweed**:滚动更新版
- **包管理**:zypper
- **适合**:企业服务器、桌面

#### (9) Arch Linux

- **历史**:2002 年
- **特点**:**极简、KISS 原则**,用户自己组装系统
- **包管理**:pacman
- **仓库**:**AUR (Arch User Repository)**,海量大社区包
- **更新**:滚动更新
- **适合**:高级用户、学习 Linux 内部原理
- **文档**:**Arch Wiki 是最好的 Linux 文档**(很多非 Arch 用户也看)

#### (10) Manjaro

- **历史**:基于 Arch
- **特点**:**Arch 的友好版**,自带桌面和驱动
- **适合**:想要 Arch 但不想折腾的用户

#### (11) Kali Linux

- **历史**:基于 Debian
- **特点**:**渗透测试专用**,预装 600+ 安全工具
- **适合**:安全研究人员、渗透测试工程师
- **不要**作为日常 OS 用

#### (12) Alpine Linux

- **历史**:基于 musl libc 和 BusyBox
- **特点**:**极小(基础镜像 5MB)**、安全、专为容器设计
- **包管理**:apk
- **适合**:Docker 容器、嵌入式
- **代表使用**:Docker 官方镜像默认 Alpine

#### (13) Amazon Linux

- **历史**:AWS 维护
- **特点**:**AWS EC2 优化版**,兼容 RHEL
- **版本**:Amazon Linux 2、2023
- **包管理**:yum/dnf
- **适合**:AWS 云上部署

#### (14) 国产 Linux 发行版

| 发行版            | 公司       | 基于          | 特点                       |
|-------------------|------------|---------------|----------------------------|
| **Deepin (深度)** | 深度科技   | Debian        | **国产最美观**,DDE 桌面    |
| **UOS (统信)**    | 统信软件   | Deepin        | 党政机关信创主推           |
| **Kylin (麒麟)**  | 中标麒麟   | 多个          | 党政、军队、国企           |
| **openEuler**     | 华为       | RHEL          | **服务器 OS**,欧拉         |
| **openCloudOS**   | 腾讯       | RHEL          | 云端 OS,腾讯云             |
| **Anolis OS**     | 阿里       | RHEL/CentOS   | 龙蜥,阿里云                |
| **OpenAnolis**    | 社区       | RHEL          | 龙蜥社区版                 |
| **CTyunOS**       | 天翼云     | RHEL          | 中国电信云                 |
| **openCloudOS**   | 腾讯/社区  | RHEL          | 社区 OS                    |
| **银河麒麟**      | 国防科大   | FreeBSD→Linux | 国产高端                   |
| **中标麒麟**      | 中标软件   | RHEL          | 党政信创                   |
| **红旗 Linux**    | 中科红旗   | -             | 老牌,已不主流              |

#### (15) 其他特色发行版

| 发行版                       | 特点                            |
|------------------------------|---------------------------------|
| **Tails**                    | 匿名 OS,内存运行,不留痕         |
| **Qubes OS**                 | 安全隔离,基于虚拟机             |
| **Solus**                    | 独立,面向桌面的 Budgie 桌面     |
| **Void Linux**               | 独立,使用 runit,简洁            |
| **NixOS**                    | 声明式配置,原子升级,回滚        |
| **Gentoo**                   | 源码编译,极高度可定制           |
| **Slackware**                | 史上最古老,坚持 KISS            |
| **LFS (Linux From Scratch)** | 从零编译 Linux,学习用           |
| **Puppy Linux**              | 极小,老电脑救星                 |
| **Chrome OS**                | Google,基于 Linux,云端          |
| **Android**                  | Linux 内核,移动端霸主           |
| **HarmonyOS**                | 华为,部分基于 Linux             |
| **SteamOS**                  | Valve,游戏主机 Steam Deck       |
| **Raspberry Pi OS**          | 树莓派官方                      |

### 4. 发行版选择树

```text
你想要什么?
├── 个人桌面
│   ├── 新手/Windows 用户 → Ubuntu / Linux Mint
│   ├── 想要 macOS 体验  → elementary OS
│   ├── 美观优先        → Deepin
│   ├── 学习 Linux      → Arch
│   └── 老电脑          → Lubuntu / Puppy / Puppy
├── 服务器
│   ├── 主流云          → Ubuntu Server / Debian
│   ├── 企业商用        → RHEL (付费) / Rocky / Alma
│   ├── AWS 优化        → Amazon Linux
│   ├── 国产替代        → openEuler / Anolis / UOS
│   └── 高性能/HPC      → CentOS Stream / openSUSE
├── 开发/运维
│   ├── 学习/折腾        → Arch / Fedora
│   ├── 容器友好        → Alpine
│   └── 老牌稳如老狗    → Debian
├── 安全
│   ├── 渗透测试        → Kali / Parrot
│   └── 匿名/隐私       → Tails
├── 容器/云原生
│   ├── 基础镜像        → Alpine / Distroless
│   └── Kubernetes OS  → Flatcar / Talos
└── 嵌入式/IoT
    ├── 树莓派          → Raspberry Pi OS
    ├── OpenWrt         → 路由器
    └── 工业控制        → VxWorks / RT-Linux
```

---

## 四、Linux 桌面环境 (Desktop Environment)

### 1. 主流桌面环境

| 桌面              | 资源占用 | 特点                              | 代表发行版                   |
|-------------------|----------|-----------------------------------|------------------------------|
| **GNOME**         | 大       | 现代化,macOS 风格,默认 Ubuntu     | Ubuntu、Fedora、Debian       |
| **KDE Plasma**    | 中       | 功能丰富,Windows 风格,可定制性强  | Kubuntu、openSUSE            |
| **XFCE**          | 轻量     | 经典,稳定,适合老机器              | Xubuntu、Manjaro XFCE        |
| **MATE**          | 轻量     | GNOME 2 风格延续,适合老用户       | Linux Mint MATE、Ubuntu MATE |
| **Cinnamon**      | 中       | 类 Windows,Linux Mint 默认        | Linux Mint                   |
| **LXQt/LXDE**     | 极轻量   | 老电脑救星                        | Lubuntu                      |
| **Budgie**        | 轻量     | 现代化,简洁                       | Solus、Ubuntu Budgie         |
| **Deepin DDE**    | 中       | 国产,美如苹果,自带应用多          | Deepin                       |
| **Pantheon**      | 中       | macOS 风格                        | elementary OS                |
| **Enlightenment** | 极轻量   | 老牌,炫酷效果                     | Bodhi Linux                  |
| **Sway / i3**     | 极轻量   | 平铺式,极客最爱                   | 各种可装                     |

### 2. 显示服务器

- **X11 (X Window System)**:老牌,40 年历史,网络透明
- **Wayland**:新一代,**X11 替代品**,更安全、更现代
  - Ubuntu 22.04+ 默认 Wayland
  - Fedora 默认 Wayland
  - GNOME、KDE 已支持

### 3. 显示管理器 (Display Manager / Login Manager)

- **GDM** (GNOME Display Manager)
- **LightDM** (轻量,Ubuntu 默认)
- **SDDM** (KDE 推荐)
- **LXDM** (LXQt)

---

## 五、Linux 包管理

### 1. 包管理器分类

| 类型        | 工具                 | 代表发行版            |
|-------------|----------------------|-----------------------|
| dpkg 系     | apt / apt-get / dpkg | Debian、Ubuntu        |
| rpm 系      | yum / dnf / rpm      | RHEL、CentOS、Fedora  |
| pacman      | pacman / yay         | Arch、Manjaro         |
| zypper      | zypper               | openSUSE              |
| apk         | apk                  | Alpine                |
| portage     | emerge               | Gentoo                |
| nix         | nix                  | NixOS                 |

### 2. 包管理常用操作

```bash
# Debian/Ubuntu
sudo apt update              # 更新索引
sudo apt upgrade             # 升级所有包
sudo apt install <pkg>       # 安装包
sudo apt remove <pkg>        # 删除包
sudo apt search <keyword>    # 搜索
apt list --installed         # 已安装列表

# RHEL/Fedora
sudo dnf update              # 更新
sudo dnf install <pkg>       # 安装
sudo dnf remove <pkg>        # 删除
sudo dnf search <keyword>    # 搜索
rpm -qa                      # 已安装列表

# Arch
sudo pacman -Syu             # 更新
sudo pacman -S <pkg>         # 安装
sudo pacman -R <pkg>         # 删除
pacman -Ss <keyword>         # 搜索

# Alpine
sudo apk update
sudo apk add <pkg>
sudo apk del <pkg>
```

### 3. 通用/跨平台包格式

- **Snap** (Ubuntu/Canonical):沙箱、自动更新
- **Flatpak** (社区):沙箱、跨发行版
- **AppImage**:单文件便携,无需安装
- **DEB/RPM**:发行版原生格式
- **容器化应用**:Docker、Podman

---

## 六、Linux 文件系统

### 1. 主流 Linux 文件系统

| 文件系统      | 特点                                                          |
|---------------|---------------------------------------------------------------|
| **Ext4**      | Linux 默认,稳定,日志,最大 1EB(理论)                           |
| **XFS**       | 高性能,大文件友好,RHEL 默认                                   |
| **Btrfs**     | 写时复制 (CoW),快照,压缩,subvolume,RAID,ZFS-like              |
| **ZFS**       | 写时复制,快照,校验和,池化(原 Sun),许可不兼容 GPL              |
| **F2FS**      | 闪存优化,用于手机/SSD                                         |
| **NTFS**      | Windows 兼容,Linux 通过 ntfs-3g 读写                          |
| **exFAT**     | 微软,大文件友好,SD 卡/USB 常见                                |
| **FAT32**     | 兼容性最好,但单文件 4GB 上限                                  |
| **tmpfs**     | 内存文件系统,极快                                             |
| **proc**      | /proc,内核信息暴露                                            |
| **sysfs**     | /sys,内核对象暴露                                             |
| **overlayfs** | Docker/容器用,层叠文件系统                                    |
| **NFS**       | 网络文件系统                                                  |
| **CIFS/SMB**  | Windows 共享                                                  |

### 2. 标准目录结构 (FHS)

```text
/
├── /bin        # 基本命令(所有用户)
├── /sbin       # 系统管理命令
├── /etc        # 配置文件
├── /home       # 用户主目录
├── /root       |  root 主目录
├── /var        # 变化数据(日志、缓存)
│   ├── /var/log
│   ├── /var/lib
│   └── /var/cache
├── /tmp        # 临时文件
├── /usr        # 用户程序
│   ├── /usr/bin
│   ├── /usr/lib
│   └── /usr/local
├── /opt        # 第三方应用
├── /dev        # 设备文件
├── /proc       # 进程/内核信息
├── /sys        # 内核对象
├── /boot       # 启动文件
├── /lib        # 库文件
├── /media      |  可移动介质挂载
├── /mnt        |  临时挂载
├── /run        # 运行时数据
└── /srv        # 服务数据
```

---

## 七、Linux 重要软件生态

### 1. 文本编辑

- **Vim / Neovim**:经典终端编辑器
- **Emacs**:神之编辑器
- **VS Code**:最流行 GUI 编辑器
- **Sublime Text**:轻量 GUI
- **Nano / Pico**:简单终端编辑器
- **Gedit / Kate**:GNOME / KDE 自带

### 2. Shell

- **Bash**:默认,几乎所有发行版都有
- **Zsh**:Oh-My-Zsh,功能丰富
- **Fish**:用户友好,自动补全
- **sh (POSIX)**:标准 shell
- **csh / tcsh**:C 风格
- **PowerShell**:跨平台,从 Windows 来
- **Nushell**:Rust 写的现代 shell

### 3. 终端复用

- **tmux**:终端复用神器
- **screen**:老牌
- **byobu**:tmux 包装,易用

### 4. 开发工具

- **GCC / Clang**:C/C++ 编译器
- **glibc / musl**:C 库
- **Make / CMake / Ninja**:构建工具
- **pkg-config**:库配置
- **GDB**:调试器
- **Valgrind**:内存检测
- **strace / ltrace**:系统调用/库调用追踪
- **perf**:性能分析
- **Bazel**:Google 构建工具

### 5. 编程语言生态

| 语言    | 工具链                                |
|---------|---------------------------------------|
| Python  | pip、conda、venv、poetry、uv          |
| Java    | OpenJDK、Maven、Gradle                |
| Go      | go toolchain                          |
| Rust    | cargo、rustc                          |
| Node.js | npm、yarn、pnpm                       |
| PHP     | composer、pear                        |
| Ruby    | bundler、gem                          |
| R       | CRAN                                  |
| C/C++   | GCC、Clang、CMake、Conan              |

### 6. 数据库

- **MySQL / MariaDB**:关系型
- **PostgreSQL**:开源最强关系型
- **SQLite**:嵌入式
- **Redis**:内存 KV
- **MongoDB**:文档
- **InfluxDB / Prometheus**:时序
- **ClickHouse**:OLAP
- **TiDB / OceanBase**:分布式

### 7. Web 服务器 / 反向代理

- **Nginx**:高性能 Web/反向代理
- **Apache HTTPd**:老牌
- **Caddy**:自动 HTTPS
- **HAProxy**:负载均衡
- **Envoy**:服务网格
- **Traefik**:云原生

### 8. 容器与云原生

- **Docker**:容器运行时
- **containerd**:Docker 内部用的运行时
- **Podman**:Red Hat 出品,无 daemon
- **Kubernetes (K8s)**:容器编排
- **Helm**:K8s 包管理
- **Istio / Linkerd**:服务网格
- **Prometheus**:监控
- **Grafana**:可视化
- **etcd**:K8s 的 KV 存储
- **Containerd / CRI-O**:K8s 容器运行时

### 9. 虚拟化

- **KVM / QEMU**:Linux 原生虚拟化
- **VirtualBox**:Oracle 跨平台
- **Xen**:老牌
- **VMware Workstation / ESXi**

### 10. 运维与监控

- **systemd / init**:服务管理
- **cron / cronie / anacron**:定时任务
- **rsyslog / syslog-ng**:日志
- **logrotate**:日志轮转
- **Prometheus + Grafana**:监控主流
- **Zabbix / Nagios**:传统监控
- **Ansible / Puppet / Chef / SaltStack**:自动化运维
- **Terraform**:IaC

### 11. 安全

- **iptables / nftables**:防火墙
- **ufw**:Ubuntu 简化防火墙
- **firewalld**:RHEL 系列
- **SELinux / AppArmor**:MAC 强制访问控制
- **OpenSSH**:远程登录
- **GnuPG (GPG)**:加密签名
- **Let's Encrypt (certbot)**:免费 HTTPS
- **fail2ban**:防爆破
- **Snort / Suricata**:IDS

### 12. 网络工具

- **curl / wget**:HTTP 客户端
- **OpenSSL**:加密库
- **ip / ss / netstat**:网络配置
- **tcpdump / Wireshark**:抓包
- **nmap**:端口扫描
- **mtr / traceroute / ping**:网络诊断
- **iproute2**:现代网络工具
- **NetworkManager / systemd-networkd**:网络管理
- **WireGuard / OpenVPN**:VPN

### 13. 文件与存储

- **rsync**:增量同步
- **tar / zip / 7z**:归档
- **dd / parted / fdisk**:磁盘
- **LVM**:逻辑卷管理
- **mdadm**:软 RAID
- **GlusterFS / Ceph**:分布式存储
- **MinIO**:对象存储

### 14. 多媒体

- **FFmpeg**:音视频处理神器
- **GStreamer**:多媒体框架
- **Audacity**:音频编辑
- **Blender**:3D
- **GIMP**:图像
- **Inkscape**:矢量图
- **OBS**:直播录屏

### 15. 办公

- **LibreOffice**:开源 Office
- **OnlyOffice**:兼容 MS Office
- **WPS Office for Linux**
- **Thunderbird**:邮件
- **Firefox / Chrome / Edge**:浏览器
- **Obsidian / Joplin / Logseq**:笔记
- **VS Code / JetBrains**:开发

---

## 八、Linux 重要概念

### 1. 一切皆文件 (Everything is a File)

- 文件、设备、管道、Socket 都是文件
- 用统一的 `open/read/write/close` 操作
- 设备文件:`/dev/sda`、`/dev/null`、`/dev/random`

### 2. 文本配置

- 几乎所有配置都是**纯文本文件**
- 可用编辑器直接改
- 便于版本控制、自动化

### 3. 大量小工具

- 一个程序只做一件事,但做到极致
- 用管道 (|) 组合,完成复杂任务
- **Unix 哲学**:
  - 组合性
  - 简洁
  - 透明
  - 专注

### 4. 命令行威力

- 几乎所有操作都能在终端完成
- 远程管理全靠 SSH + 命令行
- 适合自动化 (脚本、CI/CD)

### 5. 进程与服务

- **进程**:运行中的程序
- **服务 (Service/Daemon)**:后台进程
- **systemd**:现代 Linux 的服务管理器
  - `systemctl start nginx`
  - `systemctl enable nginx`
  - `systemctl status nginx`

### 6. 用户与权限

- **root**:超级管理员
- **sudo**:临时提升权限
- **rwx** 三组(owner/group/others) × 三类(read/write/execute)
- **chmod / chown / chgrp**

### 7. 网络配置

- `/etc/hostname`
- `/etc/hosts`
- `/etc/resolv.conf`
- `/etc/network/interfaces` (Debian)
- NetworkManager / systemd-networkd

---

## 九、Linux 应用领域

### 1. 服务器 (Linux 占有率最高)

- **90%+ 的云端服务器**跑 Linux
- Web 服务器、数据库、容器、虚拟化
- 代表公司:Google、Amazon、Meta、Microsoft Azure

### 2. 移动端

- **Android** = Linux 内核
- 全球 70%+ 智能手机
- HarmonyOS 部分基于 Linux

### 3. 嵌入式/IoT

- 路由器、网关、机顶盒、智能家居
- **OpenWrt**:路由器专用 Linux
- **Raspberry Pi OS**:树莓派

### 4. 桌面

- 全球桌面份额 4-5%
- Linux 桌面流行度逐年提升
- 发行版:Ubuntu、Mint、Fedora、Pop!_OS

### 5. 超级计算机

- **TOP500 100%** 跑 Linux

### 6. 主机/游戏

- **Steam Deck** (SteamOS)
- **PS4/PS5** 基于 FreeBSD (类似)
- **Nintendo Switch** 基于类 Unix

### 7. 金融/电信/政府

- 几乎所有大型金融机构核心系统跑 Linux
- 电信运营商用 RHEL/CentOS
- 国产替代(信创)主推 UOS/麒麟

---

## 十、Linux 与开源协议

### 1. 主要开源协议

| 协议           | 关键点                                       | 例子                              |
|----------------|----------------------------------------------|-----------------------------------|
| **GPL**        | 强制开源衍生作品,传染性强                    | Linux 内核、MySQL、MariaDB、GCC   |
| **LGPL**       | 库可用,改动要开源                            | glibc                             |
| **MIT**        | 极宽松,几乎无限制                            | X11、Node.js、Ruby、jQuery        |
| **BSD**        | 宽松,允许闭源                                | FreeBSD、OpenBSD、nginx           |
| **Apache 2.0** | 允许专利,声明修改                            | Kubernetes、Apache HTTPd、Flutter |
| **MPL**        | 修改的文件要开源                             | Firefox                           |
| **ISC**        | 类似 BSD                                     | OpenBSD 部分                      |

### 2. Linux 核心是 **GPL v2**

- 内核必须开源
- 衍生内核(如 Android)也必须开源
- 关键争议:Linux 内核包含 **MIT/BSD** 协议代码,以及部分 **LGPL** 代码
- **"开源但不免费"**:开源 ≠ 免费,商用 Linux 厂商(如 Red Hat)卖的是服务

### 3. 重要开源组织

- **Linux Foundation**:Linux 内核、众多云项目
- **GNU / FSF**:GNU 工具链、gcc、glibc
- **Apache**:Hadoop、Kafka、Spark
- **CNCF (Cloud Native Computing Foundation)**:K8s、Prometheus、containerd
- **OpenSSF**:开源安全
- **Eclipse Foundation**:IDE、IoT
- **Free Software Foundation (FSF)**:GNU 项目

---

## 十一、Linux 学习路径

### 入门

1. 安装一个发行版(Ubuntu 或 Mint)
2. 熟悉终端和基本命令
3. 文件系统、用户权限
4. 软件安装

### 进阶

1. Shell 脚本编程
2. 网络配置、服务管理
3. 系统监控与故障排查
4. 编译安装软件
5. 内核编译

### 高级

1. 性能调优
2. 容器与虚拟化
3. 内核源码阅读
4. 驱动开发
5. 集群、分布式

### 推荐学习资源

- **官方文档**:每个发行版都有
- **Arch Wiki**:最全
- **鸟哥的 Linux 私房菜**(中文经典)
- **The Linux Command Line**(英文经典书)
- **Linux Foundation 培训**(LFCS、LFCE 等认证)
- **Linux Upskill Challenge**(0→运维)

### 认证

- **Linux Foundation Certified Sysadmin (LFCS)**
- **Linux Foundation Certified Engineer (LFCE)**
- **Red Hat Certified System Administrator (RHCSA)**
- **Red Hat Certified Engineer (RHCE)**
- **LPI (Linux Professional Institute) LPIC-1/2/3**

---

## 十二、Linux 关键人物

- **Linus Torvalds**:Linux 内核之父
- **Richard Stallman**:GNU 创始人,自由软件运动领袖
- **Andrew Tanenbaum**:Minix 创始人(Linux 灵感来源)
- **Ken Thompson**:Unix 创始人之一
- **Dennis Ritchie**:C 语言之父
- **Bill Joy**:BSD、vi 作者
- **Mark Shuttleworth**:Ubuntu / Canonical 创始人
- **Ian Murdock**:Debian 创始人
- **Linus Torvalds + Greg Kroah-Hartman**:内核维护核心
- **Rob Pike + Ken Thompson**:Go 语言、UTF-8

---

## 十三、Linux 未来趋势

### 1. 桌面化进展

- Wayland 取代 X11
- Pipewire 取代 PulseAudio
- Flatpak/Snap 通用应用
- 越来越多应用原生支持 Linux

### 2. 容器与云原生

- 容器全面取代虚拟机
- K8s 成为数据中心 OS
- Serverless 进一步抽象

### 3. 内核演进

- **Rust 进入 Linux 内核**(6.1 起)
- 新的调度器 (EEVDF,6.6)
- io_uring 全面替代传统 I/O
- 持续优化性能与安全

### 4. 国产化替代

- 党政、电信、金融、能源 → 国产 Linux
- 自主可控、供应链安全
- openEuler、OpenAnolis、UOS、麒麟

### 5. AI 与 Linux

- PyTorch / TensorFlow 主力平台
- 大模型训练:GPU + Linux
- 边缘 AI:Linux on ARM

### 6. RISC-V

- 国产 CPU 押注
- RISC-V + Linux 生态正在完善

---

## 十四、核心要点速记

- **Linux 严格说指内核**,GNU/Linux 指完整 OS
- **Linus Torvalds 1991 年发布**
- **协议:GPL v2**,强制开源
- **两大家族**:Debian 系 (apt/deb) vs Red Hat 系 (yum/rpm)
- **服务器市占率 90%+**
- **桌面市占率 4-5%**
- **移动市占率 70%+** (Android)
- **超算市占率 100%**
- **一切皆文件**(设备、Socket、管道)
- **配置文件纯文本**
- **小工具组合,管道串起来**
- **systemd 是现代服务管理**
- **主流服务器**:Ubuntu、RHEL、Rocky、openEuler
- **主流桌面**:Ubuntu、Linux Mint、Fedora、Deepin
- **学习推荐**:Ubuntu 起步,Arch Wiki 查资料
- **必学命令**:cd、ls、cat、grep、find、ps、kill、chmod、ssh、scp
- **环境很重要**:**Arch Wiki** + **鸟哥私房菜** + **实操**
- **开源不等于免费**,Red Hat 等卖的是服务和支持
