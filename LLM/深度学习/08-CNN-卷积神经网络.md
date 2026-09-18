# 08. CNN 卷积神经网络

CNN (Convolutional Neural Network) 是处理网格结构数据（图像、视频）的标准架构。核心是**卷积**+**池化**+**全连接**。

## 8.1 为什么用 CNN

### 视觉数据的归纳偏置

- **平移不变性**：猫在左在右都是猫
- **局部性**：相邻像素相关性强
- **层次化**：边缘 → 纹理 → 部件 → 物体

### 对比 MLP

- **参数共享**：同一卷积核扫全图 → 少参
- **稀疏连接**：每个输出只连局部输入
- **平移等变**：$f(g(x)) = g(f(x))$

## 8.2 卷积运算

### 一维卷积

$$
y[i] = \sum_{k} x[i + k] \cdot w[k]
$$

### 二维卷积

$$
y[i, j] = \sum_{u, v} x[i + u, j + v] \cdot w[u, v]
$$

### 关键概念

- **Kernel / Filter**：卷积核
- **Stride**：步长
- **Padding**：填充
- **Dilation**：空洞卷积

```
输入 (5x5)        Kernel (3x3)      输出 (3x3)
1 1 1 0 0        1 0 1            4  3  4
0 1 1 1 0        0 1 0            2  4  3
0 0 1 1 1        1 0 1            2  3  4
0 0 1 1 0
1 1 0 0 0
```

### Padding

- **Valid (无填充)**：输出 = 输入 - kernel + 1
- **Same (填充)**：输出 = 输入尺寸，padding = (k-1)/2

### Stride

- stride=1：输出尺寸 = 输入
- stride=2：输出尺寸 = 输入 / 2

### Dilation (空洞)

插入空洞扩大感受野，不增参数：

```
dilation=1:    dilation=2:
1 0 1          1 0 0 0 1
0 1 0          0 0 0 0 0
1 0 1          0 0 1 0 0
                0 0 0 0 0
                1 0 0 0 1
```

## 8.3 输出尺寸

$$
o = \left\lfloor \frac{i + 2p - k}{s} \right\rfloor + 1
$$

- $i$：输入尺寸
- $p$：padding
- $k$：kernel size
- $s$：stride

例：i=32, k=3, p=1, s=1 → o=32
例：i=32, k=3, p=1, s=2 → o=16

## 8.4 PyTorch 实现

```python
import torch.nn as nn

# 2D 卷积
conv = nn.Conv2d(
    in_channels=3,
    out_channels=64,
    kernel_size=3,
    stride=1,
    padding=1,
)

# 1D 卷积 (序列)
conv1d = nn.Conv1d(in_channels=128, out_channels=64, kernel_size=3)

# 3D 卷积 (视频 / 体数据)
conv3d = nn.Conv3d(in_channels=3, out_channels=64, kernel_size=3)

# 转置卷积 (上采样)
convT = nn.ConvTranspose2d(64, 32, kernel_size=2, stride=2)

# 深度可分离卷积
depthwise = nn.Conv2d(64, 64, kernel_size=3, groups=64)
pointwise = nn.Conv2d(64, 128, kernel_size=1)
```

## 8.5 池化

### Max Pooling

```python
nn.MaxPool2d(kernel_size=2, stride=2)
```

保留局部最强响应。

### Average Pooling

```python
nn.AvgPool2d(kernel_size=2, stride=2)
```

更平滑。

### Global Average Pooling (GAP)

```python
nn.AdaptiveAvgPool2d(1)  # 输出 (B, C, 1, 1)
```

替代 FC，参数大量减少。

### Adaptive Pooling

```python
nn.AdaptiveMaxPool2d((7, 7))  # 输出固定 7x7
```

## 8.6 经典架构演进

### LeNet-5 (1998)

```python
class LeNet5(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv1 = nn.Conv2d(1, 6, 5, padding=2)
        self.pool1 = nn.AvgPool2d(2, 2)
        self.conv2 = nn.Conv2d(6, 16, 5)
        self.pool2 = nn.AvgPool2d(2, 2)
        self.fc1 = nn.Linear(16 * 5 * 5, 120)
        self.fc2 = nn.Linear(120, 84)
        self.fc3 = nn.Linear(84, 10)
```

### AlexNet (2012)

- 5 Conv + 3 FC
- ReLU 首次使用
- Dropout 0.5
- LRN（后被 BN 替代）
- Top-5 错误率 16.4%

### VGG (2014)

- 3x3 卷积 + 2x2 池化
- 简洁、堆叠
- VGG-16 / VGG-19

```python
def vgg_block(num_convs, in_channels, out_channels):
    layers = []
    for _ in range(num_convs):
        layers.append(nn.Conv2d(in_channels, out_channels, 3, padding=1))
        layers.append(nn.ReLU())
        in_channels = out_channels
    layers.append(nn.MaxPool2d(2, 2))
    return nn.Sequential(*layers)
```

### Inception / GoogLeNet (2014)

- 多尺度并行卷积
- 1x1 卷积降维
- 22 层

```python
class InceptionModule(nn.Module):
    def __init__(self, in_channels):
        super().__init__()
        self.branch1x1 = nn.Conv2d(in_channels, 64, 1)

        self.branch3x3 = nn.Sequential(
            nn.Conv2d(in_channels, 48, 1),
            nn.Conv2d(48, 64, 3, padding=1),
        )

        self.branch5x5 = nn.Sequential(
            nn.Conv2d(in_channels, 64, 1),
            nn.Conv2d(64, 96, 5, padding=2),
        )

        self.branch_pool = nn.Sequential(
            nn.MaxPool2d(3, stride=1, padding=1),
            nn.Conv2d(in_channels, 32, 1),
        )

    def forward(self, x):
        return torch.cat([
            self.branch1x1(x),
            self.branch3x3(x),
            self.branch5x5(x),
            self.branch_pool(x),
        ], dim=1)
```

### ResNet (2015) ⭐

- 残差连接：$y = F(x) + x$
- 解决深度网络退化
- ResNet-18/34/50/101/152

```python
class ResidualBlock(nn.Module):
    def __init__(self, in_channels, out_channels, stride=1):
        super().__init__()
        self.conv1 = nn.Conv2d(in_channels, out_channels, 3, stride, 1)
        self.bn1 = nn.BatchNorm2d(out_channels)
        self.conv2 = nn.Conv2d(out_channels, out_channels, 3, 1, 1)
        self.bn2 = nn.BatchNorm2d(out_channels)

        self.shortcut = nn.Sequential()
        if stride != 1 or in_channels != out_channels:
            self.shortcut = nn.Sequential(
                nn.Conv2d(in_channels, out_channels, 1, stride),
                nn.BatchNorm2d(out_channels),
            )

    def forward(self, x):
        out = F.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        out += self.shortcut(x)
        return F.relu(out)
```

### ResNeXt

- 多分支 + ResNet
- "cardinality" 维度

### DenseNet

- 每层与前面所有层连接
- 特征复用

### MobileNet (v1/v2/v3)

- **v1**：深度可分离卷积
- **v2**：Inverted Residual + Linear Bottleneck
- **v3**：NAS + h-swish

```python
class DepthwiseSeparableConv(nn.Module):
    def __init__(self, in_c, out_c, stride=1):
        super().__init__()
        self.depthwise = nn.Conv2d(in_c, in_c, 3, stride, 1, groups=in_c)
        self.pointwise = nn.Conv2d(in_c, out_c, 1)

    def forward(self, x):
        return self.pointwise(self.depthwise(x))
```

### EfficientNet (2019)

- **复合缩放**：深度 / 宽度 / 分辨率
- **MBConv**：Mobile Inverted Bottleneck + SE
- AutoML NAS

```python
# timm
import timm
model = timm.create_model('efficientnet_b0', pretrained=True)
```

### ConvNeXt (2022)

- "现代化" ResNet
- 借鉴 Transformer 设计
- 性能可比 Swin Transformer

### Vision Transformer (ViT)

详见 [10-Transformer](10-Transformer详解.md)。

### Swin Transformer

- 层级 + 滑动窗口
- CV 主宰

### ConvNeXt v2

- FCMAE 预训练
- 全卷积 + 全 MLP

## 8.7 常用卷积变体

### 深度可分离卷积

```python
# Depthwise
nn.Conv2d(in_c, in_c, 3, padding=1, groups=in_c)
# Pointwise
nn.Conv2d(in_c, out_c, 1)
```

参数量缩减约 $1/k^2 + 1/c_{out}$。

### 分组卷积 (Grouped Conv)

```python
nn.Conv2d(in_c, out_c, 3, groups=g)
```

参数减少 $g$ 倍。ResNeXt、MobileNet。

### 1x1 卷积

```python
nn.Conv2d(in_c, out_c, 1)
```

- 通道混合
- 不变空间尺寸
- 等价于逐点 FC

### 转置卷积 (Transposed / Deconv)

```python
nn.ConvTranspose2d(in_c, out_c, 4, stride=2, padding=1)  # 2x 上采样
```

用于分割、生成。

### 可变形卷积 (Deformable)

- 卷积核位置可学
- DCN v1/v2

## 8.8 注意力机制

### Squeeze-and-Excitation (SE)

```python
class SEBlock(nn.Module):
    def __init__(self, channel, reduction=16):
        super().__init__()
        self.fc = nn.Sequential(
            nn.Linear(channel, channel // reduction),
            nn.ReLU(),
            nn.Linear(channel // reduction, channel),
            nn.Sigmoid(),
        )

    def forward(self, x):
        b, c, _, _ = x.size()
        y = F.adaptive_avg_pool2d(x, 1).view(b, c)
        y = self.fc(y).view(b, c, 1, 1)
        return x * y
```

### CBAM

通道 + 空间注意力。

### ECA (Efficient Channel Attention)

高效版 SE。

## 8.9 经典任务模型

### 图像分类

- ResNet / EfficientNet / ConvNeXt / ViT
- timm 库

### 目标检测

- **两阶段**：Faster R-CNN / Mask R-CNN
- **单阶段**：YOLO v5/v8 / SSD / RetinaNet
- **Transformer**：DETR / DINO

### 语义分割

- FCN / U-Net / DeepLab v3+ / SegFormer
- 见 timm / segmentation_models_pytorch

### 实例分割

- Mask R-CNN / YOLACT / SAM

### 关键点检测

- OpenPose / HRNet

## 8.10 实战选择

| 场景 | 推荐 |
|------|------|
| 通用 | ResNet-50 / EfficientNet-B3 |
| 移动端 | MobileNet-v3 / EfficientNet-B0 |
| 高精度 | EfficientNet-B7 / ConvNeXt-Large |
| 目标检测 | YOLOv8 / DETR |
| 分割 | U-Net / SegFormer |
| 速度优先 | MobileNet / ShuffleNet |
| Vision Transformer | ViT / Swin / ConvNeXt |

## 8.11 完整训练示例

```python
import torch
import torchvision
import torchvision.transforms as T
from torchvision.models import resnet50, ResNet50_Weights

# 数据
train_transform = T.Compose([
    T.RandomResizedCrop(224),
    T.RandomHorizontalFlip(),
    T.ToTensor(),
    T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])
train_set = torchvision.datasets.ImageFolder('data/train', transform=train_transform)
train_loader = torch.utils.data.DataLoader(train_set, batch_size=64, shuffle=True, num_workers=8)

# 模型
model = resnet50(weights=ResNet50_Weights.DEFAULT)
model.fc = nn.Linear(model.fc.in_features, num_classes)
model = model.cuda()

# 优化器
optimizer = torch.optim.SGD(model.parameters(), lr=0.01, momentum=0.9, weight_decay=1e-4)
scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=100)

# 训练
for epoch in range(100):
    model.train()
    for x, y in train_loader:
        x, y = x.cuda(), y.cuda()
        y_pred = model(x)
        loss = nn.CrossEntropyLoss(label_smoothing=0.1)(y_pred, y)

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
    scheduler.step()
```

## 8.12 常见问题

| 问题 | 解决 |
|------|------|
| 模型不收敛 | 调小 LR、检查数据 |
| 训练/验证差距大 | 数据增强 / Dropout |
| 显存不足 | 减小 batch / 用梯度累积 |
| 推理慢 | 半精度 / 模型剪枝 |
| 输入大小限制 | 用 Adaptive Pooling |
| 类别不平衡 | Focal Loss / 重采样 |

## 8.13 参考

- LeCun et al., 1998 *Gradient-Based Learning Applied to Document Recognition* (LeNet)
- Krizhevsky et al., 2012 *ImageNet Classification with Deep CNN* (AlexNet)
- Simonyan & Zisserman, 2015 *Very Deep CNNs for ImageNet* (VGG)
- Szegedy et al., 2015 *Going Deeper with Convolutions* (GoogLeNet)
- He et al., 2016 *Deep Residual Learning* (ResNet)
- Howard et al., 2017 *MobileNets*
- Tan & Le, 2019 *EfficientNet*
- Liu et al., 2022 *A ConvNet for the 2020s* (ConvNeXt)
- Dosovitskiy et al., 2021 *An Image is Worth 16x16 Words* (ViT)
- Liu et al., 2021 *Swin Transformer*