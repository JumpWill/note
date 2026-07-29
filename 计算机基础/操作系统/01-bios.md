# BIOS (Basic Input/Output System)

## 一、BIOS 概述

**BIOS** = **B**asic **I**nput/**O**utput **S**ystem,基本输入输出系统。

**本质**:固化在主板**ROM 芯片**中的一段**底层固件程序**,是计算机开机后**第一个运行的软件**。

### BIOS 的核心职责

1. **POST (Power-On Self-Test)**:开机自检,检测 CPU、内存、显卡、硬盘等
2. **系统设置 (CMOS Setup)**:通过 CMOS Setup 界面配置硬件参数
3. **提供中断服务**:为 DOS/早期 OS 提供硬件抽象的软中断 (INT 13h/10h 等)
4. **引导加载 (Boot Loader)**:按启动顺序查找可引导设备,把控制权交给 OS 引导程序
5. **硬件初始化**:在 OS 加载前初始化最基本的硬件(CPU、内存控制器、芯片组)

### BIOS 的位置

- 存储:主板上的 **ROM/EEPROM/Flash ROM** 芯片(现在普遍 SPI Flash)
- 别称:也叫"固件 (Firmware)"
- 升级:通过"刷 BIOS"更新(可修复 bug、支持新 CPU、添加新功能)

---

## 二、计算机启动过程(BIOS 视角)

```text
┌─────────────────────────────────────────────┐
│ 1. 按下电源键,ATX 电源启动                  │
│         ↓                                   │
│ 2. CPU 复位,CS:IP 指向 FFFF:0000 (物理     │
│    地址 FFFFFFF0h),从 BIOS ROM 顶部执行     │
│         ↓                                   │
│ 3. POST 自检:CPU → BIOS → 显卡 → 内存 →  │
│    键盘 → 硬盘 → 其他设备                   │
│         ↓                                   │
│ 4. 屏幕显示:LOGO + 自检信息                  │
│         ↓                                   │
│ 5. 读 CMOS 配置,识别启动设备                │
│         ↓                                   │
│ 6. 按启动顺序(Boot Order)查找引导设备       │
│         ↓                                   │
│ 7. 加载引导扇区(MBR,512 字节)到内存 7C00h  │
│         ↓                                   │
│ 8. 跳转执行 MBR,把控制权交给 OS Bootloader │
│         ↓                                   │
│ 9. Bootloader 加载 OS 内核                  │
│         ↓                                   │
│ 10. OS 启动,BIOS 退居幕后(部分功能仍用)     │
└─────────────────────────────────────────────┘
```

**关键地址**:
- **CS:IP = FFFF:0000h**(实模式),即物理地址 **0xFFFFFFF0**
- 开机第一条指令位于 BIOS ROM 的尾部 16 字节
- **MBR 加载到 0x7C00**(约定)

---

## 三、POST 自检流程

POST (Power-On Self-Test) 是 BIOS 最核心的工作之一,逐项检测关键硬件。

| 步骤 | 检测项           | 失败表现               |
|------|------------------|------------------------|
| 1    | CPU              | 无显示,主板喇叭报警    |
| 2    | BIOS 自身完整性  | 黑屏,连续短 beep       |
| 3    | CMOS 电路        | 提示"CMOS 校验错误"    |
| 4    | 内存 (RAM)       | beep 报警,显示错误地址 |
| 5    | 显卡             | 一长两短 beep(传统)    |
| 6    | 键盘             | 提示"Keyboard Error"   |
| 7    | 软驱 / 硬盘      | 提示未连接             |
| 8    | 其他设备         | 提示 IRQ 冲突          |

**POST 通过标志**:通常一声短 beep + 显示启动画面。

**BIOS 蜂鸣码 (Beep Codes)**:
- AMI BIOS:1 短 = 通过,1 长 2 短 = 显卡错
- Award BIOS:1 短 = 通过,不断长响 = 内存未插好
- Phoenix BIOS:多种 1-x-x 组合代表不同错误

---

## 四、CMOS 与 BIOS Setup

### CMOS 是什么

- **CMOS**:Complementary Metal-Oxide-Semiconductor,一种**低功耗存储技术**
- **CMOS 芯片**:主板上一块由**纽扣电池 (CR2032)** 供电的 **RAM 芯片**,用于保存 BIOS 配置
- **CMOS 数据**:用户设置的硬件参数,断电后由电池维持

> **CMOS ≠ BIOS**:CMOS 是硬件(存储芯片),BIOS 是软件(固件)。CMOS 存 BIOS 的配置。

### BIOS Setup 主要设置项

| 分类     | 常见项                                                    |
|----------|-----------------------------------------------------------|
| 启动相关 | 启动顺序 (Boot Order)、快速启动、CSM/Legacy、UEFI 模式    |
| CPU      | 睿频、虚拟化 (VT-x/AMD-V)、超线程、C-State                |
| 内存     | XMP/EXPO、频率、时序、内存容量                            |
| 存储     | SATA 模式 (AHCI/IDE/RAID)、NVMe 配置                      |
| 电源     | 待机模式 (S1/S3/S5)、来电自启、PCIe ASPM                  |
| 安全     | 密码、TPM、安全启动 (Secure Boot)                         |
| 外设     | USB 启动、PS/2、串口重定向                                |
| 健康     | 风扇策略、温度告警、电压监控                              |

### 清除 CMOS

- **何时清除**:BIOS 设置错乱、超频失败、忘记密码
- **方法**:
  - 拔电池等待 30 秒
  - 短接 CLR_CMOS 跳线
  - 主板按钮 (Clear CMOS Button)

---

## 五、BIOS 的中断服务

### 实模式下的 BIOS 中断

BIOS 为 DOS 和早期 OS 提供**软中断**形式的硬件抽象,程序通过 `INT n` 调用。

| 中断号  | 功能                  | 常用功能号                          |
|---------|-----------------------|-------------------------------------|
| INT 10h | 视频服务              | 00h 设置模式、0Eh 显示字符          |
| INT 13h | 磁盘服务              | 02h 读扇区、03h 写扇区              |
| INT 14h | 串口服务              | 00h 初始化、01h 发送字符            |
| INT 16h | 键盘服务              | 00h 读按键、01h 检查按键            |
| INT 19h | 引导加载              | 启动操作系统                        |
| INT 1Ah | 时钟服务              | 00h 读时间                          |

**示例:用 INT 13h 读 MBR**

```assembly
mov ah, 02h       ; 功能号 = 读扇区
mov al, 01h       ; 读 1 个扇区
mov ch, 00h       ; 柱面 0
mov cl, 01h       ; 扇区 1
mov dh, 00h       ; 磁头 0
mov dl, 80h       ; 硬盘 (第 1 块)
mov bx, 7C00h     ; 读到 0x7C00
int 13h
```

> 注:保护模式 / 64 位 OS 已不再使用这些 BIOS 中断,直接驱动硬件。

---

## 六、BIOS 启动流程(详细)

### MBR 启动方式(传统 BIOS)

```text
1. BIOS 自检通过
2. 读启动设备的 MBR (0 柱面 0 磁头 1 扇区,512 字节) → 0x7C00
3. 检查 MBR 末 2 字节是否为 0x55AA(魔数)
4. 跳到 0x7C00 执行 MBR
5. MBR (446 字节代码 + 64 字节分区表 + 2 字节魔数)
   - 解析分区表,找到"活动分区"
   - 加载活动分区的 VBR (Volume Boot Record)
6. VBR 加载 OS Bootloader(Windows NTLDR / Linux GRUB)
7. Bootloader 加载 OS 内核,启动操作系统
```

**MBR 限制**:
- 仅支持 4 个主分区(或 3 主 + 1 扩展)
- 最大支持 2TB 磁盘
- 无备份机制

### PBR / VBR

- **PBR (Partition Boot Record)** = **VBR (Volume Boot Record)**
- 位于**活动分区**的第一个扇区
- 不同 OS 的 VBR 不同:
  - Windows NTFS 的 VBR 加载 NTLDR / BOOTMGR
  - Linux 的 VBR 加载 GRUB

---

## 七、BIOS vs UEFI

### UEFI 简介

**UEFI** = Unified Extensible Firmware Interface,统一可扩展固件接口,**BIOS 的现代继任者**。

### 详细对比

| 维度           | BIOS (Legacy)              | UEFI                                         |
|----------------|----------------------------|----------------------------------------------|
| 全称           | Basic Input/Output System  | Unified Extensible Firmware Interface        |
| 模式           | 16 位实模式                | 32/64 位保护模式/长模式                      |
| 启动方式       | MBR                        | GPT                                          |
| 最大磁盘       | 2 TB                       | 9.4 ZB(理论)                                 |
| 分区表         | MBR(4 个主分区)            | GPT(128 个分区)                              |
| 启动速度       | 慢(自检逐项)               | 快(并行初始化)                               |
| 图形界面       | 文本/简单 GUI              | 完整 GUI(支持鼠标)                           |
| 启动介质       | 硬盘 MBR                   | ESP 分区(EFI System Partition)               |
| 启动方式       | 直接跳到 MBR               | 通过 EFI 应用(.efi)                          |
| 安全启动       | 无                         | Secure Boot                                  |
| 网络功能       | 无                         | 内置网络栈(可远程管理)                       |
| 扩展性         | 固定                       | 模块化,可加载驱动                            |
| 兼容模式       | -                          | CSM (Compatibility Support Module) 兼容老 OS |

### UEFI 启动流程

```text
1. UEFI 固件自检 (SEC → PEI → DXE → BDS → TSL)
2. 读 CMOS 配置
3. 初始化硬件 (CPU、内存、PCIe、SATA、网络)
4. 读启动项 (Boot####)
5. 从 ESP 分区 (FAT32) 加载 .efi 引导程序
   - \EFI\Microsoft\Boot\bootmgfw.efi (Windows)
   - \EFI\ubuntu\grubx64.efi (Linux)
6. OS 接管
```

### Secure Boot

- **目的**:防止恶意引导程序(bootkit)启动
- **原理**:启动链上的每个组件都有数字签名,验证通过才执行
- **OS 支持**:Windows 8+、Ubuntu、RHEL 7+ 等主流 OS 都支持
- **争议**:理论上可被破解,且对 Linux 自由分发有争议

### CSM

- **Compatibility Support Module**:UEFI 中的兼容模块,模拟传统 BIOS
- 开启后可启动老的 MBR 磁盘上的 OS
- 现代 OS 建议关闭 CSM,使用纯 UEFI + GPT

---

## 八、BIOS 升级 (刷 BIOS)

### 为什么刷 BIOS

- 修复已知 bug
- 支持新 CPU(老主板上新代 CPU 经常要刷 BIOS)
- 提升内存兼容性
- 启用新功能 (如支持 NVMe 启动)
- 修复安全漏洞

### 风险

- **刷坏导致主板变砖**(通常可双 BIOS 救回)
- 升级中**不能断电**
- 版本不匹配可能损坏

### 方法

1. **DOS 环境下刷**:用 U 盘启动 DOS,运行刷写工具
2. **Windows 下刷**:主板厂商工具(如 MSI Center、ASUS AI Suite)
3. **UEFI 内置刷写**:在 UEFI 界面里直接选固件文件刷写
4. **带外刷 (BIOS Flashback)**:不开机,主板按钮直接刷(救砖神器)

### 保护机制

- **Dual BIOS**:主 BIOS 坏了自动从备份 BIOS 启动
- **UEFI Capsule Update**:数字签名,失败自动回滚

---

## 九、BIOS 安全

### 常见 BIOS 级攻击

| 攻击                | 描述                                | 防御                    |
|---------------------|-------------------------------------|-------------------------|
| Bootkit             | 改 MBR/EFI,比 OS 启动早             | Secure Boot、TPM        |
| BIOS 病毒           | 写入 SPI Flash                      | 写保护、签名验证        |
| Evil Maid           | 物理接触刷固件                      | BIOS 密码、机箱锁       |
| 冷启动攻击          | 从内存镜像提取密钥                  | 内存加密、关机清内存    |

### TPM (Trusted Platform Module)

- **硬件芯片**,存储密钥、证书
- 与 BIOS/UEFI 配合实现:
  - **BitLocker 加密**(Windows)
  - **磁盘全盘加密**
  - **平台完整性度量 (PCR)**
- 版本:TPM 1.2(老)、TPM 2.0(主流)
- 中国要求:TCM(国产替代)

---

## 十、各厂商 BIOS 特色

| 厂商          | 品牌       | 特色                                |
|---------------|------------|-------------------------------------|
| 华硕 ASUS     | UEFI BIOS  | EZ Mode、AI 优化、AI Suite 工具     |
| 技嘉 GIGABYTE | UEFI       | Dual BIOS、Q-Flash                  |
| 微星 MSI      | Click BIOS | Click BIOS 5、MSI Center            |
| 华擎 ASRock   | UEFI       | Instant Flash、BIOS Flashback       |
| 戴尔 Dell     | UEFI       | 与 iDRAC 联动,企业级管理            |
| HPE           | iLO + BIOS | 远程管理深度集成                    |
| 联想          | ThinkBIOS  | 与 XClarity 集成                    |
| 七彩虹        | 主流 UEFI  | 性价比                              |

---

## 十一、BIOS 相关概念对比

### 概念辨析

| 概念           | 含义                                |
|----------------|-------------------------------------|
| **BIOS**       | 固件程序,提供硬件抽象和启动         |
| **CMOS**       | 存 BIOS 设置的 RAM + 电池           |
| **UEFI**       | BIOS 的现代替代品                   |
| **POST**       | 开机自检                            |
| **MBR**        | 主引导记录,512 字节                 |
| **GPT**        | 新分区表,取代 MBR                   |
| **VBR/PBR**    | 卷/分区引导记录                     |
| **Bootloader** | OS 引导加载程序(GRUB、BOOTMGR)      |
| **固件**       | 烧录在硬件里的软件(BIOS/UEFI 都算)  |
| **EFI 应用**   | UEFI 下的小程序 (.efi)              |

### BIOS 的工作模式

| 模式        | 时代      | 特点                                |
|-------------|-----------|-------------------------------------|
| 8 位 BIOS   | 早期      | CP/M、Apple II                      |
| 16 位实模式 | DOS 时代  | CS:IP,1MB 寻址,INT 中断             |
| 32 位 BIOS  | 过渡      | 仍用 INT,但支持保护模式             |
| UEFI        | 现代      | 保护模式/长模式,EFI 接口            |

---

## 十二、BIOS 未来趋势

1. **UEFI 全面普及**:BIOS 已基本淘汰,新主板只支持 UEFI
2. **Coreboot / Heads**:开源 BIOS 替代(Google Chromebook 在用)
3. **RISC-V Boot**:RISC-V 架构推动开源固件
4. **云原生 BIOS**:云服务器的固件,集成远程管理、安全启动、加密
5. **DPU 接管**:智能网卡接管部分固件职责

---

## 十三、BIOS 启动故障排查

| 故障现象                         | 原因                    | 解决方法                |
|----------------------------------|-------------------------|-------------------------|
| 开机无任何反应                   | 电源/主板               | 检查电源、Power 按钮    |
| 风扇转但无显示                   | 内存/CPU/显卡           | 重插内存、单条测试      |
| 蜂鸣报警                         | 内存/显卡故障           | 查 beep 码              |
| 显示"CMOS Checksum Error"        | CMOS 没电或配置错乱     | 换电池、Clear CMOS      |
| 显示"Operating system not found" | 启动盘没系统/启动顺序错 | 调整启动顺序、修复引导  |
| 开机自动进 BIOS                  | 键盘错/启动盘没插好     | 拔启动盘、按 F1 跳过    |
| 黑屏只显示 Logo                  | 显卡驱动问题/死循环     | 进安全模式/重装系统     |
| 刷 BIOS 后开不了机               | 刷坏                    | 用 BIOS Flashback 救回  |

**常用进 BIOS 快捷键**(按品牌):

| 品牌           | 进 BIOS 键      | 启动菜单键 |
|----------------|-----------------|------------|
| 华硕 ASUS      | DEL/F2          | F8         |
| 技嘉 GIGABYTE  | DEL             | F12        |
| 微星 MSI       | DEL             | F11        |
| 戴尔 Dell      | F2              | F12        |
| 联想 Lenovo    | F1/F2           | F12        |
| 惠普 HP        | F10             | F9         |
| 苹果 Mac       | 开机长按 Option | -          |
| ThinkPad       | Enter → F1      | F12        |

---

## 十四、核心要点速记

- **BIOS = 固化在 ROM 里的第一个软件**
- **CMOS = 保存 BIOS 配置的电池供电 RAM**
- **POST = 开机自检**
- **MBR = 传统启动方式,2TB 上限,4 主分区**
- **GPT + UEFI = 现代标准**,支持大硬盘、多分区、Secure Boot
- **CPU 复位后执行的第一条指令**位于 0xFFFFFFF0
- **MBR 加载到 0x7C00**,魔数 0x55AA
- **刷 BIOS 有风险**,双 BIOS + Flashback 是救砖手段
- **Secure Boot + TPM** 是现代安全基石
- **未来属于 UEFI**,传统 BIOS 已被淘汰
