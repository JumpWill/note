# 第 21 章 — GAN：合成数据与时间序列生成

## 章节目标

- GAN 原理
- 合成金融数据
- 时间序列 GAN

## 21.1 GAN 基础

### 概念

- **Generator** G：生成假样本
- **Discriminator** D：区分真假

### 对抗训练

$$
\min_G \max_D \mathbb{E}_{x \sim p_{\text{data}}} [\log D(x)] + \mathbb{E}_{z \sim p_z} [\log(1 - D(G(z)))]
$$

- G 试图骗过 D
- D 试图识别假样本

## 21.2 简单 GAN

```python
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, LeakyReLU, BatchNormalization, Input

# Generator
def build_generator(latent_dim, output_dim):
    model = Sequential([
        Dense(128, input_dim=latent_dim),
        LeakyReLU(0.2),
        BatchNormalization(),
        Dense(256),
        LeakyReLU(0.2),
        BatchNormalization(),
        Dense(output_dim, activation='tanh'),
    ])
    return model

# Discriminator
def build_discriminator(input_dim):
    model = Sequential([
        Dense(256, input_dim=input_dim),
        LeakyReLU(0.2),
        Dropout(0.3),
        Dense(128),
        LeakyReLU(0.2),
        Dropout(0.3),
        Dense(1, activation='sigmoid'),
    ])
    return model

# 编译
latent_dim = 100
data_dim = 60  # 序列长度 × 特征

generator = build_generator(latent_dim, data_dim)
discriminator = build_discriminator(data_dim)
discriminator.compile(optimizer='adam', loss='binary_crossentropy')

# GAN
discriminator.trainable = False
gan_input = Input(shape=(latent_dim,))
generated = generator(gan_input)
validity = discriminator(generated)
gan = Model(gan_input, validity)
gan.compile(optimizer='adam', loss='binary_crossentropy')
```

## 21.3 GAN 训练循环

```python
import numpy as np

def train_gan(gan, generator, discriminator, X_train, latent_dim, epochs=10000, batch_size=64):
    half_batch = batch_size // 2

    for epoch in range(epochs):
        # 1. 训练 Discriminator
        idx = np.random.randint(0, X_train.shape[0], half_batch)
        real = X_train[idx]
        noise = np.random.normal(0, 1, (half_batch, latent_dim))
        fake = generator.predict(noise, verbose=0)

        d_loss_real = discriminator.train_on_batch(real, np.ones((half_batch, 1)))
        d_loss_fake = discriminator.train_on_batch(fake, np.zeros((half_batch, 1)))

        # 2. 训练 Generator（通过 GAN）
        noise = np.random.normal(0, 1, (batch_size, latent_dim))
        g_loss = gan.train_on_batch(noise, np.ones((batch_size, 1)))

        if epoch % 1000 == 0:
            print(f"Epoch {epoch}: D={d_loss_real + d_loss_fake:.4f}, G={g_loss:.4f}")
```

## 21.4 GAN 变体

### DCGAN

- 用 Conv 代替 Dense
- 更适合图像

### Wasserstein GAN (WGAN)

- Wasserstein 距离
- 更稳定

```python
# WGAN
from tensorflow.keras.layers import Dense, LeakyReLU

def build_wgan_critic(input_dim):
    model = Sequential([
        Dense(256, input_dim=input_dim),
        LeakyReLU(0.2),
        Dense(128),
        LeakyReLU(0.2),
        Dense(1),  # 没有 sigmoid
    ])
    return model

# 训练
def wasserstein_loss(y_true, y_pred):
    return tf.reduce_mean(y_true * y_pred)
```

### Conditional GAN

- 条件生成
- 标签 / 资产特征

```python
from tensorflow.keras.layers import Concatenate

def build_cgan(latent_dim, n_classes, output_dim):
    # Generator
    noise_input = Input(shape=(latent_dim,))
    label_input = Input(shape=(1,))

    # 标签嵌入
    label_embedding = Dense(latent_dim)(tf.one_hot(label_input, n_classes))
    merged = Concatenate()([noise_input, label_embedding])

    x = Dense(128, activation='relu')(merged)
    output = Dense(output_dim, activation='tanh')(x)

    generator = Model([noise_input, label_input], output)
    return generator
```

## 21.5 时间序列 GAN

### 挑战

- 序列有依赖
- 多种统计特征

### TimeGAN

```python
# pip install yfinance
import numpy as np
import yfinance as yf

# 多股票收益
tickers = ['AAPL', 'MSFT', 'GOOGL']
prices = yf.download(tickers, start='2010-01-01')['Close']
returns = prices.pct_change().dropna()
data = returns.values  # (T, 3)
```

## 21.6 TimeGAN 实现

```python
"""TimeGAN"""
import tensorflow as tf
from tensorflow.keras.layers import LSTM, Dense, Input, Concatenate
from tensorflow.keras.models import Model

class TimeGAN:
    def __init__(self, seq_len, n_features, latent_dim=24):
        self.seq_len = seq_len
        self.n_features = n_features
        self.latent_dim = latent_dim

        # Embedder
        self.embedder = self.build_embedder()
        self.recovery = self.build_recovery()

        # Generator
        self.generator = self.build_generator()

        # Discriminator
        self.discriminator = self.build_discriminator()

    def build_embedder(self):
        inputs = Input(shape=(self.seq_len, self.n_features))
        x = LSTM(64)(inputs)
        x = Dense(self.latent_dim)(x)
        return Model(inputs, x, name='embedder')

    def build_recovery(self):
        inputs = Input(shape=(self.latent_dim,))
        x = Dense(64)(inputs)
        x = Dense(self.seq_len * self.n_features)(x)
        x = tf.keras.layers.Reshape((self.seq_len, self.n_features))(x)
        return Model(inputs, x, name='recovery')

    def build_generator(self):
        inputs = Input(shape=(self.seq_len, self.latent_dim))
        x = LSTM(64)(inputs)
        x = Dense(self.latent_dim)(x)
        return Model(inputs, x, name='generator')

    def build_discriminator(self):
        inputs = Input(shape=(self.seq_len, self.latent_dim))
        x = LSTM(64)(inputs)
        x = Dense(1, activation='sigmoid')(x)
        return Model(inputs, x, name='discriminator')
```

## 21.7 合成数据生成

### 动机

- 数据增强
- 隐私保护
- 模拟压力场景
- 解决数据稀缺

### 评估

- TSTR（Train on Synthetic, Real on Test）
- 统计相似度
- 因子相关性

## 21.8 实战：金融数据 GAN 增强

```python
"""用 GAN 增强金融数据"""
import numpy as np
import pandas as pd
import yfinance as yf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, LeakyReLU, BatchNormalization, Dropout, Input, LSTM, Reshape
from tensorflow.keras.optimizers import Adam

# 1. 数据
prices = yf.download('AAPL', start='2010-01-01')['Close']
returns = prices.pct_change().dropna().values

# 2. 准备序列
def create_sequences(data, seq_len=20):
    X = []
    for i in range(len(data) - seq_len):
        X.append(data[i:i+seq_len])
    return np.array(X)

seq_len = 20
X = create_sequences(returns, seq_len)
X = (X - X.mean()) / X.std()  # 标准化

# 3. Generator
def build_generator(latent_dim, seq_len):
    model = Sequential([
        Dense(128, input_dim=latent_dim),
        LeakyReLU(0.2),
        BatchNormalization(),
        Dense(256),
        LeakyReLU(0.2),
        BatchNormalization(),
        Dense(seq_len, activation='tanh'),
        Reshape((seq_len, 1)),
    ])
    return model

# 4. Discriminator
def build_discriminator(seq_len):
    model = Sequential([
        LSTM(64, input_shape=(seq_len, 1)),
        Dropout(0.3),
        Dense(32),
        LeakyReLU(0.2),
        Dropout(0.3),
        Dense(1, activation='sigmoid'),
    ])
    return model

# 5. 编译
latent_dim = 100
generator = build_generator(latent_dim, seq_len)
discriminator = build_discriminator(seq_len)
discriminator.compile(optimizer=Adam(0.0002, 0.5), loss='binary_crossentropy')

# GAN
discriminator.trainable = False
gan_input = Input(shape=(latent_dim,))
generated = generator(gan_input)
validity = discriminator(generated)
gan = Model(gan_input, validity)
gan.compile(optimizer=Adam(0.0002, 0.5), loss='binary_crossentropy')

# 6. 训练
epochs = 5000
batch_size = 64

for epoch in range(epochs):
    # 真实
    idx = np.random.randint(0, X.shape[0], batch_size // 2)
    real = X[idx]

    # 假
    noise = np.random.normal(0, 1, (batch_size // 2, latent_dim))
    fake = generator.predict(noise, verbose=0)

    # 训练 D
    d_loss_real = discriminator.train_on_batch(real, np.ones((batch_size // 2, 1)))
    d_loss_fake = discriminator.train_on_batch(fake, np.zeros((batch_size // 2, 1)))

    # 训练 G
    noise = np.random.normal(0, 1, (batch_size, latent_dim))
    g_loss = gan.train_on_batch(noise, np.ones((batch_size, 1)))

    if epoch % 500 == 0:
        print(f"Epoch {epoch}: D={0.5*(d_loss_real+d_loss_fake):.4f}, G={g_loss:.4f}")

# 7. 生成
noise = np.random.normal(0, 1, (1000, latent_dim))
synthetic = generator.predict(noise, verbose=0)

# 8. 评估
real_returns = returns[:1000]
synthetic_returns = synthetic.flatten()[:1000]

print(f"Real mean: {real_returns.mean():.4f}, std: {real_returns.std():.4f}")
print(f"Synth mean: {synthetic_returns.mean():.4f}, std: {synthetic_returns.std():.4f}")
```

## 21.9 关键 Notebook

```
21_gans_for_synthetic_data/
├── 01_basic_gan.ipynb
├── 02_wgan.ipynb
├── 03_conditional_gan.ipynb
├── 04_timegan.ipynb
└── 05_synthetic_returns.ipynb
```

## 21.10 关键 takeaway

- GAN 学数据分布
- 适合生成合成数据
- TimeGAN 处理序列
- 评估需谨慎

## 21.11 实战陷阱

#### 模式塌缩

- G 只会生成少量样本
- 解决：minibatch discrimination / WGAN

#### 训练不稳定

- 平衡 G / D 训练
- 调学习率

#### 评估难

- 合成数据是否"够好"难量化
- 用 TSTR

## 21.12 评估方法

| 方法 | 说明 |
|------|------|
| **TSTR** | 训练合成，测试真实 |
| **可视化** | t-SNE / UMAP |
| **统计** | mean / var / ACF |
| **判别器** | 区分合成 vs 真实 |

## 21.13 GAN vs VAE

| 维度 | GAN | VAE |
|------|-----|-----|
| 训练 | 难、不稳定 | 稳定 |
| 质量 | **锐利** | 模糊 |
| 评估 | 难 | 容易（下界） |
| 模式 | 可能塌缩 | 全覆盖 |

## 21.14 应用案例

### 数据增强

- 数据稀缺时增广
- 防止过拟合

### 隐私

- 训练 GAN 而非公开数据
- 共享 GAN 模型

### 压力测试

- 合成极端场景
- 模型稳健性

### 市场模拟

- 训练 RL 交易
- 模拟对手

## 21.15 参考

- Goodfellow et al., 2014 *Generative Adversarial Networks*
- Arjovsky et al., 2017 *Wasserstein GAN*
- Mirza & Osindero, 2014 *Conditional GANs*
- Yoon et al., 2019 *TimeGAN: Time-series Generative Adversarial Network for Synthetic Financial Signals*