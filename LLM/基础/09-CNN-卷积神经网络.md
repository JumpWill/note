# CNN：卷积神经网络详解

## 1. 历史脉络

```
1968  Hubel & Wiesel ────────── 视觉皮层研究 (局部感受野)
1980  Neocognitron (Fukushima) ── 神经认知机 (CNN 雏形)
1998  LeNet-5 (LeCun) ────────── 手写数字识别
2012  AlexNet (Krizhevsky) ──────── ImageNet 冠军，深度学习爆发
2014  VGG / GoogLeNet ──────────── 3×3 卷积 / 多尺度并行
2015  ResNet (He) ──────────────── 残差连接，152 层
2016  DenseNet ─────────────────── 密集连接
2017  MobileNet (v1) ───────────── 深度可分离卷积
2018  EfficientNet ─────────────── 复合缩放
2019  EfficientNet v2 / NFNet ──── 更高效训练
2020  ViT ──────────────────────── Transformer 抢视觉
2022  ConvNeXt ─────────────────── 现代化 CNN
2023+ ConvNeXt V2 / FastViT ────── CNN 仍然重要
```

## 2. 卷积数学

### 2.1 2D 卷积（实际是 cross-correlation）

$$
Y_{i,j,k} = \sum_{c, u, v} W_{u,v,c,k} \cdot X_{i+u, j+v, c} + b_k
$$

- $X \in \mathbb{R}^{C_{in} \times H \times W}$
- $W \in \mathbb{R}^{k_h \times k_w \times C_{in} \times C_{out}}$ (输出通道 $k$)
- $Y \in \mathbb{R}^{C_{out} \times H' \times W'}$

### 2.2 卷积核大小

- $1 \times 1$：通道变换，不动空间
- $3 \times 3$：经典最小感受野
- $5 \times 5$ / $7 \times 7$：更大感受野（但参数更多）
- 多个 $3 \times 3$ 堆叠 ≈ 一个大核（参数更少、非线性更多）

### 2.3 Stride 步长

- stride = 1：输出与输入同尺寸
- stride = 2：输出尺寸减半（下采样）

### 2.4 Padding 填充

保持空间尺寸：

- **valid** (无 padding)：$H' = H - k + 1$
- **same** (补 0)：$H' = H$
- **reflect / replicate**：边界用相邻值填充

### 2.5 Dilation 空洞卷积

在核元素间插入空洞，扩大感受野而不增加参数：

- dilation = 1：普通卷积
- dilation = 2：核大小从 3 变成 5 (但参数仍是 9)

用于：语义分割 (DeepLab)、音频生成 (WaveNet)。

### 2.6 输出尺寸公式

$$
H' = \left\lfloor \frac{H + 2p - d(k_h - 1) - 1}{s} \right\rfloor + 1
$$

$p$ = padding, $d$ = dilation, $s$ = stride。

## 3. 关键算子

### 3.1 Depthwise Conv (MobileNet)

每个输入通道独立做卷积：

- 普通 Conv：$k^2 \cdot c_{in} \cdot c_{out}$ 参数
- Depthwise：$k^2 \cdot c_{in}$ 参数
- 接着 1×1 Conv (Pointwise) 混合通道
- 总参数量减少 ≈ $k^2$ 倍

### 3.2 Transposed Conv (反卷积)

上采样用的卷积：

- 普通 Conv：下采样
- Transposed Conv：上采样
- 用于：分割 (decoder)、GAN (generator)

注意：会产生 checkerboard artifacts，现代用 Upsample + Conv 替代。

### 3.3 1D / 3D Conv

- **1D Conv**：序列、音频、文本 (kernel 沿时间方向)
- **3D Conv**：视频、体素 (Voxel)

### 3.4 Group Conv (分组卷积)

将 $C_{in}$ 通道分 $g$ 组，每组独立卷积：

- $g = 1$：普通 Conv
- $g = C_{in}$：Depthwise Conv
- $g = $ 中间值：折中 (ResNeXt)

### 3.5 Pooling 池化

- **MaxPool**：取窗口最大值，保留最显著特征
- **AvgPool**：取窗口均值，平滑
- **GlobalAvgPool**：每张 feature map 取一个均值 → 替代 FC 做输出层 (大幅减参数)

### 3.6 归一化

- **BatchNorm** (CNN 标配)：对每个通道在 batch 内归一化
  - 训练时用 batch 统计，推理用 running mean/var
  - 训练不稳定时 (图像生成) 用 **GroupNorm** 或 **LayerNorm**
- **GroupNorm**：把通道分组，组内归一化
- **LayerNorm**：对每个样本所有通道归一化 (LLM 主流)

## 4. 经典架构演进

### 4.1 LeNet-5 (1998)

```
Input(1×32×32)
   ↓ C1: Conv 6@5×5
   ↓ S2: AvgPool 2×2
   ↓ C3: Conv 16@5×5
   ↓ S4: AvgPool 2×2
   ↓ C5: Conv 120@5×5
   ↓ F6: FC 84
   ↓ Output: 10 classes
```

第一个真正工作的 CNN。Sigmoid 激活。

### 4.2 AlexNet (2012)

- 5 个 Conv + 3 个 FC = 60M 参数
- **ReLU** 替换 Sigmoid → 训练快 6x
- **Dropout** 防过拟合
- **GPU 训练** (两块 GTX 580)
- **Data Augmentation** (随机裁剪、翻转、PCA jitter)
- **LRN** (Local Response Normalization)

### 4.3 VGG (2014)

- 只用 3×3 Conv 堆叠
- 11/13/16/19 层四种规格
- 138M 参数 (VGG-19)
- 优点：简单、统一
- 缺点：参数大、已过时

### 4.4 GoogLeNet / Inception (2014)

Inception module：多尺度并行

```
        Input
        ┌─┬─┬─┐
        │ │ │ │
      1×1 3×3 5×5 3×3maxpool
        │ │ │ │
        └─┴─┴─┘
        Concat
```

- 1×1 Conv 先降维 → 减少计算
- 22 层，5M 参数 (VGG 的 1/27)
- Inception v2/v3/v4 改进：BN、分解卷积

### 4.5 ResNet (2015)

残差块：

$$
y = \mathcal{F}(x, \{W_i\}) + x
$$

```
Input
   ↓ Conv 3×3
   ↓ BN, ReLU
   ↓ Conv 3×3
   ↓ BN
   ↓ + (shortcut)
   ↓ ReLU
```

- 残差连接让梯度有"恒等通路"
- 可训练到 152 / 1001 层
- 后续: ResNeXt (分组)、Wide ResNet (加宽)

### 4.6 DenseNet (2016)

每层与所有前置层 concat：

$$
x_l = H_l([x_0, x_1, \ldots, x_{l-1}])
$$

- 特征重用好
- 参数比 ResNet 略少
- 显存占用大

### 4.7 MobileNet (2017-2019)

- **v1**: Depthwise Separable Conv
- **v2**: Inverted Residuals + Linear Bottleneck
- **v3**: NAS + h-swish + 平台感知

目标：移动端低延迟。

### 4.8 EfficientNet (2019)

**复合缩放**：

$$
\text{depth} = \alpha^\phi, \quad \text{width} = \beta^\phi, \quad \text{resolution} = \gamma^\phi
$$

统一缩放深度/宽度/分辨率。B0~B7。

### 4.9 ConvNeXt (2022)

把 ResNet 现代化 ("Transformer 配方")：

- 7×7 Depthwise Conv 替代 3×3
- LN 替代 BN (LN 在 Transformer 训练更稳)
- GELU 替代 ReLU
- 更少激活函数、更少 Norm

性能接近 Swin Transformer，但保留 CNN 的高效推理。

## 5. 应用领域

### 5.1 图像分类

```
ResNet-50 → GlobalAvgPool → FC(num_classes)
```

### 5.2 目标检测

#### R-CNN 系 (两阶段)

```
Image → CNN backbone → Region Proposals → RoI Pooling → FC → bbox + class
```

- R-CNN → Faster R-CNN (RPN)
- 精度高、速度慢

#### YOLO 系 (单阶段)

```
Image → CNN → 多个 feature map → 直接预测 bbox + class + confidence
```

- YOLO v1~v11 (Ultralytics)
- 实时检测

#### DETR (Transformer 端到端)

```
Image → CNN backbone → Transformer → N 个 object query → set prediction
```

无 anchor、无 NMS。

### 5.3 语义分割

#### FCN

```
CNN → Conv (转置卷积上采样) → per-pixel class
```

#### U-Net

```
Encoder (CNN 下采样) ↔ Decoder (上采样)
                ↑
         skip connections
```

医学影像标配。

#### DeepLab

- Atrous Conv (空洞卷积)
- ASPP (Atrous Spatial Pyramid Pooling)
- CRF 后处理

### 5.4 其他

- **实例分割**：Mask R-CNN
- **关键点检测**：Hourglass
- **3D 目标检测**：VoxelNet、PointNet++ (CNN 提取 3D 特征)
- **OCR**：CRNN (CNN + RNN + CTC)
- **语音**：1D Conv (WaveNet)

## 6. CNN 的 Inductive Bias

| 偏置 | 含义 | 实现 |
|------|------|------|
| 平移不变性 | 同一物体出现在任何位置都识别 | 权值共享 |
| 局部性 | 局部像素相关性强 | 局部连接 |
| 尺度层次 | 边缘 → 纹理 → 部件 → 物体 | 多层 + 池化 |

这些偏置让 CNN 在**小数据集**上也能学好（不需要从头学这些先验）。

## 7. 训练配方

### 7.1 数据增强

| 方法 | 用途 |
|------|------|
| 随机翻转 / 裁剪 | 标配 |
| Color Jitter | 颜色扰动 |
| Random Erasing / Cutout | 随机遮挡 |
| Mixup | 样本凸组合 |
| CutMix | 区域替换 |
| AutoAugment | 学习到的增强策略 |

### 7.2 优化器

- **SGD + Momentum** (传统，CNN 经典)
- **AdamW** (现代通用)

### 7.3 学习率调度

- Step Decay (传统)：每 N epoch × 0.1
- Cosine Annealing (现代)
- Warmup + Cosine (LLM 风格，CNN 也常用)

### 7.4 正则化

- Weight Decay (1e-4 ~ 1e-2)
- Dropout (FC 层 0.5，Conv 层 0.1~0.3)
- Label Smoothing (0.1)
- Stochastic Depth (深层)
- Early Stopping

## 8. CNN vs ViT

| 维度 | CNN | ViT |
|------|-----|-----|
| Inductive bias | 强 (局部+平移不变) | 弱 (靠大数据学) |
| 小数据 | ✅ 友好 | ❌ 需大数据 |
| 大数据 | 中 | ✅ 表现强 |
| 推理速度 (边缘) | 快 | 慢 |
| 推理速度 (GPU) | 中 | 略快 |
| 解释性 | 中 (可视化滤波器) | 弱 (黑盒) |
| 现状 | 工业部署主流 | 学术前沿主流 |

**ConvNeXt 表明**：用 Transformer 配方训练的 CNN，差距很小。CNN 仍是工业首选。

## 9. 现代趋势

### 9.1 Conv + Transformer 混合

- **CoAtNet**：CNN 早期 + Transformer 后期
- **ConvNeXt**：纯 CNN 但用 Transformer 配方
- **MobileNet v4**：移动端新基线

### 9.2 大卷积核

- ConvNeXt 用 7×7 Depthwise
- RepLKNet：30×30 大核
- 大核 = 更大感受野 + 更少层

### 9.3 Foundation Model 视角

- CLIP / DINOv2 用 ViT 训的视觉特征主导
- 视觉任务越来越多迁移到 ImageNet 外的预训练
- CNN backbone 仍用于边缘 / 实时场景

## 10. 选型建议

| 场景 | 推荐 |
|------|------|
| 图像分类 (中等数据) | ResNet-50 / EfficientNet-B3 |
| 图像分类 (大数据) | ConvNeXt-Base / ViT-L |
| 目标检测 (高精度) | Faster R-CNN + ResNet |
| 目标检测 (实时) | YOLO v11 |
| 语义分割 | U-Net / DeepLab v3+ |
| 移动端 | MobileNet v4 / EfficientNet-Lite |
| 边缘 GPU (Jetson) | EfficientNet / ConvNeXt-Tiny |
| 视频理解 | 3D ResNet / SlowFast / TimeSformer |

## 11. 参考

- LeCun et al., 1998 *Gradient-Based Learning Applied to Document Recognition* (LeNet)
- Krizhevsky et al., 2012 *ImageNet Classification with Deep CNN* (AlexNet)
- Simonyan & Zisserman, 2014 *Very Deep CNN for Large-Scale Image Recognition* (VGG)
- Szegedy et al., 2015 *Going Deeper with Convolutions* (GoogLeNet)
- He et al., 2015 *Deep Residual Learning* (ResNet)
- Huang et al., 2016 *Densely Connected CNN* (DenseNet)
- Howard et al., 2017 *MobileNets: Efficient CNNs for Mobile Vision*
- Tan & Le, 2019 *EfficientNet: Rethinking Model Scaling for CNNs*
- Liu et al., 2022 *A ConvNet for the 2020s* (ConvNeXt)
- Howard et al., 2019 *Searching for MobileNet v3*
