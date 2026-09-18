# DNN：深度神经网络详解

> DNN (Deep Neural Network) 是"深度"的神经网络统称，狭义上指多层感知机 (MLP, Multi-Layer Perceptron)。本文聚焦 MLP/DNN 的细节。

## 1. 起源与历史

```
1943  McCulloch-Pitts 神经元（线性阈值）
1958  Perceptron (Rosenblatt) ───── 第一个可学习模型
1969  Minsky 指出 XOR 问题 ───────── AI 寒冬
1986  Backprop (Rumelhart) ───────── 第二次兴起
1989  Universal Approximation (Cybenko) ───── 理论奠基
2006  Deep Belief Net (Hinton) ───── "深度"概念复兴
2012  AlexNet ────────────────────── GPU + ReLU + 大数据 → 爆发
2015  Highway / ResNet ──────────── 解决深度训练问题
2021  MLP-Mixer ─────────────────── 纯 MLP 在视觉上复出
```

## 2. 基本结构

### 2.1 单层感知机

$$
z = \sum_i w_i x_i + b = W x + b
$$

$$
\hat{y} = \sigma(z)
$$

- 输入 $x \in \mathbb{R}^{d_{in}}$
- 权重 $W \in \mathbb{R}^{d_{out} \times d_{in}}$，偏置 $b \in \mathbb{R}^{d_{out}}$
- 激活 $\sigma$ (非线性)
- 单层：只能分线性问题 (XOR 反例)

### 2.2 多层感知机 (MLP)

```
x [d_in]
   ↓
W₁, b₁ → Linear → [d₁]
   ↓
σ (激活)
   ↓
W₂, b₂ → Linear → [d₂]
   ↓
σ
   ↓
...
   ↓
W_L, b_L → Linear → [d_out]
   ↓
σ (输出激活)
```

第 $l$ 层：

$$
x^{(l)} = \sigma_l(W^{(l)} x^{(l-1)} + b^{(l)})
$$

### 2.3 通用近似定理

**Cybenko (1989)** / **Hornik (1991)**：

单隐层神经网络（足够宽）可任意精度逼近**任意**连续函数于紧集上。

**但是**：

- 定理只保证"存在"，不保证"能学出来"
- 实际需要的宽度可能是指数级
- 深层网络用更少参数达到同样逼近能力

## 3. 激活函数

### 3.1 性质对比

| 激活 | 范围 | 零中心 | 饱和 | 当前主流场景 |
|------|------|-------|------|--------------|
| Sigmoid | (0, 1) | ❌ | ✅ 双向 | 二分类输出层 |
| Tanh | (-1, 1) | ✅ | ✅ 双向 | RNN 历史、归一化输出 |
| ReLU | [0, ∞) | ❌ | ❌ 单边 | CNN 经典 |
| LeakyReLU | (-∞, ∞) | ✅ | ❌ | 替代 ReLU |
| GELU | (-0.3, ∞) | ✅ | ❌ | **LLM 标配** |
| SiLU / Swish | (-0.28, ∞) | ✅ | ❌ | LLM 替代品 |
| SwiGLU | $\mathbb{R}$ | ✅ | ❌ | LLaMA FFN |
| Mish | 近似 ReLU | ✅ | ❌ | 视觉实验 |

### 3.2 几何直觉

激活函数把线性变换后的直线/平面"弯曲"：

```
Sigmoid:   ──────⌒──────      把线性值压到 0~1
ReLU:      ──────╱─────       把负值截掉
GELU:      ────⌣───────       ReLU 的"软"版
```

### 3.4 Dying ReLU 问题

ReLU 在 $x < 0$ 时梯度为 0。如果一个神经元落入此区，会"永久死亡" (再也不会激活)。

解决：

- **Leaky ReLU**：$\max(0.01x, x)$
- **PReLU**：$\alpha$ 可学
- **GELU / SiLU**：平滑，无硬切

## 4. 反向传播详解

### 4.1 链式法则

对 $L$ 层 MLP，最终 loss $L$：

$$
\frac{\partial L}{\partial W^{(l)}} = \frac{\partial L}{\partial x^{(L)}} \cdot \left(\prod_{k=l+1}^{L} \frac{\partial x^{(k)}}{\partial x^{(k-1)}}\right) \cdot \frac{\partial x^{(l)}}{\partial W^{(l)}}
$$

每个 $\frac{\partial x^{(k)}}{\partial x^{(k-1)}}$ 是 $d_k \times d_{k-1}$ 的矩阵 → 链式乘导致深度网络梯度爆炸/消失。

### 4.2 单层梯度推导

最后一层：

$$
\frac{\partial L}{\partial W^{(L)}} = \frac{\partial L}{\partial x^{(L)}} \cdot \frac{\partial x^{(L)}}{\partial W^{(L)}} = \delta^{(L)} (x^{(L-1)})^T
$$

其中 $\delta^{(L)} = \frac{\partial L}{\partial x^{(L)}}$ 是上游梯度。

倒数第二层：

$$
\delta^{(L-1)} = (W^{(L)})^T \delta^{(L)} \odot \sigma'(z^{(L-1)})
$$

### 4.3 显式推导 vs Autograd

- 显式推导：教学用，公式长
- 实际工程：用 `loss.backward()` 让 PyTorch / TensorFlow 自动微分

## 5. 训练动态

### 5.1 梯度消失 / 爆炸

Sigmoid 网络中，每层梯度被乘以 $\sigma'(z)$（最大 0.25）：

$$
\|\delta^{(l)}\| \le 0.25^L \|\delta^{(L)}\|
$$

100 层 → 梯度乘以 $0.25^{100} \approx 0$，几乎消失。

| 现象 | 主因 | 缓解 |
|------|------|------|
| 消失 | 激活饱和、链式乘 < 1 | ReLU、残差、Norm |
| 爆炸 | 链式乘 > 1 | 梯度裁剪、Norm |

### 5.2 初始化

不能太大或太小：

- **Xavier (Glorot)**: 适合 Tanh/Sigmoid，$V \sim U(-\sqrt{6/(n_{in}+n_{out})}, \sqrt{6/(n_{in}+n_{out})})$
- **Kaiming (MSRA)**: 适合 ReLU，$V \sim N(0, \sqrt{2/n_{in}})$
- **Xavier Uniform / Normal**: PyTorch `nn.Linear` 默认

### 5.3 BatchNorm / LayerNorm

DNN 中 LayerNorm 更常见：

$$
\hat{x} = \frac{x - \mu}{\sqrt{\sigma^2 + \epsilon}}, \quad y = \gamma \hat{x} + \beta
$$

- 稳定训练
- 允许大学习率
- 轻微正则化效果

## 6. 深度 = 性能？

### 6.1 深度的好处

- 每层学一种**抽象层次**：边缘 → 纹理 → 部件 → 物体
- 参数效率高：深层网络指数级表达能力强
- 迁移到下游任务更容易

### 6.2 深度的代价

- 训练难：梯度消失/爆炸
- 计算贵：$L$ 倍前向/反向
- 容易过拟合

### 6.3 加深训练的方法

- **残差连接** (ResNet)：$\text{out} = x + \mathcal{F}(x)$，梯度有恒等通路
- **Highway Network**：类残差但带门控
- **DenseNet**：每层与所有后续层 concat
- **Pre-Norm**：在 sublayer 之前归一化（比 Post-Norm 稳）

## 7. 现代 DNN 变体

### 7.1 ResNet (2015)

残差块：

$$
x_{l+1} = x_l + \mathcal{F}(x_l, W_l)
$$

允许 100+ 层网络可训练。**DNN 史上最关键的进步之一**。

### 7.2 Highway Network (2015)

$$
x_{l+1} = T(x_l) \cdot \mathcal{F}(x_l, W_l) + (1 - T(x_l)) \cdot x_l
$$

$T$ 是学习的门控函数。ResNet 是 Highway 的特例（$T=1$）。

### 7.3 DenseNet (2016)

$$
x_{l+1} = [x_l, x_{l-1}, \ldots, x_0]
$$

每层与所有前置层 concat。参数量略增，但特征重用好。

### 7.4 MLP-Mixer (2021)

把图像切成 patch，每个 patch 当 token，跨 patch / 通道各做一次 MLP：

```
patch tokens [N, d]
   ↓
MLP across patches (跨 patch 混合空间信息)
   ↓
MLP across channels (跨通道混合特征)
   ↓
重复
```

纯 MLP，无 attention、无卷积。在大数据上接近 ViT。

### 7.5 gMLP (2021)

MLP-Mixer + 门控，在 NLP 上接近 Transformer。

### 7.6 现代趋势

LLM 的 FFN (Feed-Forward Network) 本质就是一个两层 MLP：

```
FFN(x) = W₂ · σ(W₁ x + b₁) + b₂
```

中间维度通常 $4d$ (ReLU 时代) 或 $8d/3$ (SwiGLU 时代)。

## 8. DNN vs CNN vs Transformer

| 维度 | DNN/MLP | CNN | Transformer |
|------|---------|-----|-------------|
| 数据偏好 | 表格、一维 | 网格 (图像) | 序列、集合 |
| 平移不变性 | ❌ | ✅ | ❌ (需位置编码) |
| 局部性 | ❌ | ✅ | ❌ (需位置编码) |
| 权重共享 | ❌ | ✅ (核) | ❌ |
| 数据效率 | 中 | 高 (小数据) | 低 (需大数据) |
| 当前位置 | FFN 子模块 | 视觉主流 | LLM/多模态主流 |

## 9. 实践选型

### 9.1 何时用 DNN/MLP

- 表格数据 (tabular)：特征独立，无空间结构
- LLM 的 FFN：永远是两层 MLP
- 小数据集 + 简单分类
- 教学 / 快速原型

### 9.2 常见错误

- 在图像/序列上直接用 MLP → 浪费数据 + 不收敛
- 用 sigmoid 当隐藏层激活 → 训练极慢
- 不归一化输入 → 收敛慢
- 不用正则化 → 必过拟合
- batch size 太小 + 学习率大 → 训练不稳

### 9.3 推荐配方

```python
# 2 层 MLP 分类器 (PyTorch)
model = nn.Sequential(
    nn.Linear(d_in, d_hidden),
    nn.LayerNorm(d_hidden),
    nn.GELU(),
    nn.Dropout(0.1),
    nn.Linear(d_hidden, d_hidden),
    nn.LayerNorm(d_hidden),
    nn.GELU(),
    nn.Dropout(0.1),
    nn.Linear(d_hidden, d_out),
)

optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=0.01)
scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
```

## 10. 参考

- Cybenko, 1989 *Approximation by Superpositions of a Sigmoidal Function* (UAT)
- Hornik et al., 1989 *Multilayer Feedforward Networks are Universal Approximators*
- Rumelhart et al., 1986 *Learning Representations by Back-propagating Errors*
- He et al., 2015 *Deep Residual Learning for Image Recognition* (ResNet)
- Huang et al., 2016 *Densely Connected Convolutional Networks*
- Tolstikhin et al., 2021 *MLP-Mixer: An all-MLP Architecture for Vision*
- Liu et al., 2021 *Pay Attention to MLPs* (gMLP)
