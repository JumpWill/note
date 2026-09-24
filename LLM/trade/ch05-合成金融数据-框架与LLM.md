# 第 5 章 — 合成金融数据（3rd Edition 新增）

## 章节目标

- 合成数据的 Fidelity-Utility-Privacy 框架
- GAN / Diffusion / LLM 在金融数据生成
- 隐私保护与数据共享

## 5.1 为什么需要合成数据

### 动机

- **数据稀缺**：另类数据贵、稀有
- **隐私合规**：GDPR / 数据保护法
- **数据共享**：在不泄露原始数据的前提下训练
- **压力测试**：合成极端场景
- **模型训练**：增广训练集

## 5.2 Fidelity-Utility-Privacy 框架

### 三个维度

- **Fidelity**：合成数据是否像真实数据
- **Utility**：是否对下游任务有用
- **Privacy**：是否泄露个体信息

```python
from sdv.evaluation import evaluate

# fidelity
evaluate(
    synthetic_data,
    real_data,
    metrics=['KSComplement', 'TVComplement', 'CSTest'],
)
```

## 5.3 评估方法

### 1. 统计相似性

```python
import pandas as pd
import numpy as np
from scipy.stats import ks_2samp

def ks_test(real, synth, columns):
    """逐列 KS 检验。"""
    results = []
    for col in columns:
        stat, p = ks_2samp(real[col].dropna(), synth[col].dropna())
        results.append({'column': col, 'ks_stat': stat, 'p_value': p})
    return pd.DataFrame(results)
```

### 2. 下游任务评估（TSTR）

```python
def tstr_evaluate(real, synth, target_col, model_fn):
    """TSTR：合成训练，真实测试。"""
    # 训练合成
    model_s = model_fn()
    model_s.fit(synth.drop(columns=[target_col]), synth[target_col])

    # 训练真实
    model_r = model_fn()
    model_r.fit(real.drop(columns=[target_col]), real[target_col])

    # 测试真实
    from sklearn.model_selection import train_test_split
    _, X_test, _, y_test = train_test_split(real.drop(columns=[target_col]), real[target_col])

    score_synth = model_s.score(X_test, y_test)
    score_real = model_r.score(X_test, y_test)

    return {'synth_to_real': score_synth, 'real_to_real': score_real}
```

### 3. 隐私：成员推断攻击

```python
def privacy_attack(real_train, real_test, synth, model_fn):
    """成员推断。"""
    # 训练 shadow model
    model_real = model_fn()
    model_real.fit(real_train.drop(columns=['target']), real_train['target'])

    # 区分训练 / 测试
    real_pred = model_real.predict(real_train.drop(columns=['target']))
    test_pred = model_real.predict(real_test.drop(columns=['target']))

    # 看合成是否更接近训练
    synth_pred = model_real.predict(synth.drop(columns=['target']))

    return np.mean(np.abs(real_pred - synth_pred))
```

## 5.4 GAN 合成（重温 + 扩展）

### tabular GAN

```python
# pip install sdv
from sdv.tabular import CTGAN

# 训练
model = CTGAN(
    epochs=500,
    batch_size=500,
    generator_dim=(256, 256),
    discriminator_dim=(256, 256),
)

model.fit(real_data)

# 生成
synthetic_data = model.sample(num_rows=10000)
```

### TimeGAN（时间序列）

```python
# pip install ydata-synthetic
from ydata_synthetic.synthesizers import ModelParameters
from ydata_synthetic.synthesizers.timeseries import TimeSeriesSynthesizer

model = TimeSeriesSynthesizer(
    model=TimeGAN,
    model_parameters=ModelParameters(
        batch_size=128,
        sequence_length=24,
        n_features=10,
        hidden_dim=64,
        gamma=1.0,
    ),
)

model.fit(sequences, epochs=300)
synthetic = model.sample(n_samples=1000)
```

## 5.5 扩散模型（Diffusion）

### 思想

- 前向加噪 → 反向去噪
- DDPM / DDIM

```python
# pip install score-based-models
import torch
import torch.nn as nn

class DenoiseNet(nn.Module):
    """预测噪声。"""
    def __init__(self, dim):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(dim + 1, 128),
            nn.ReLU(),
            nn.Linear(128, 128),
            nn.ReLU(),
            nn.Linear(128, dim),
        )

    def forward(self, x, t):
        t_emb = t.unsqueeze(-1).float() / 1000
        return self.net(torch.cat([x, t_emb], dim=-1))

class Diffusion:
    def __init__(self, T=1000):
        self.T = T
        self.betas = torch.linspace(1e-4, 0.02, T)

    def q_sample(self, x0, t, noise):
        """前向加噪。"""
        alpha_bar = torch.cumprod(1 - self.betas, dim=0)
        alpha_t = alpha_bar[t].unsqueeze(-1)
        return torch.sqrt(alpha_t) * x0 + torch.sqrt(1 - alpha_t) * noise

    def p_sample(self, model, x_t, t):
        """反向去噪。"""
        pred_noise = model(x_t, t)
        alpha_bar = torch.cumprod(1 - self.betas, dim=0)
        alpha_t = alpha_bar[t].unsqueeze(-1)
        return (x_t - torch.sqrt(1 - alpha_t) * pred_noise) / torch.sqrt(alpha_t)
```

### TabDDPM（表格扩散）

```python
# pip install tab-ddpm
from tab_ddpm import TabDDPM

model = TabDDPM(
    num_features=20,
    dim=128,
    timesteps=1000,
)

model.fit(real_data)
synthetic = model.sample(10000)
```

## 5.6 LLM 合成结构化数据

### 思想

- 用 LLM 学表格 schema
- Prompt 生成

```python
# pip install langchain
from langchain.prompts import PromptTemplate

prompt = PromptTemplate(
    input_variables=['schema', 'n_samples'],
    template="""
Generate {n_samples} synthetic financial records following this schema:
{schema}

Return as CSV.
""",
)

# 用 LLM 生成
from langchain.llms import OpenAI
llm = OpenAI()
synthetic_csv = llm(prompt.format(
    schema="date, ticker, open, high, low, close, volume",
    n_samples=100,
))
```

### GReaT (Generation of Realistic Tabular data)

```python
# pip install be-great
from be_great import GReaT

model = GReaT(
    llm='distilgpt2',
    batch_size=8,
    epochs=10,
    save_steps=1000,
)

model.fit(real_data)
synthetic = model.sample(n_samples=1000)
```

## 5.7 多资产相关保持

### 关键

合成数据要保持相关性：

```python
import seaborn as sns

def check_correlations(real, synth):
    real_corr = real.corr()
    synth_corr = synth.corr()

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    sns.heatmap(real_corr, ax=axes[0], vmin=-1, vmax=1)
    sns.heatmap(synth_corr, ax=axes[1], vmin=-1, vmax=1)
```

## 5.8 实战：完整合成数据流水线

```python
"""合成金融数据流水线"""
import pandas as pd
import numpy as np
from sdv.tabular import CTGAN
from sdv.evaluation import evaluate
import yfinance as yf

# 1. 拉真实数据
prices = yf.download(['AAPL', 'MSFT', 'GOOGL'], start='2020-01-01')['Close']
returns = prices.pct_change().dropna()

# 特征
data = pd.DataFrame({
    'AAPL_ret': returns['AAPL'],
    'MSFT_ret': returns['MSFT'],
    'GOOGL_ret': returns['GOOGL'],
    'AAPL_vol_5': returns['AAPL'].rolling(5).std(),
    'MSFT_vol_5': returns['MSFT'].rolling(5).std(),
}).dropna()

# 2. CTGAN
model = CTGAN(epochs=300, batch_size=500)
model.fit(data)

# 3. 生成
synthetic = model.sample(num_rows=5000)

# 4. 评估
report = evaluate(synthetic, data)
print(f"Score: {report}")

# 5. 可视化
import matplotlib.pyplot as plt
fig, ax = plt.subplots(1, 3, figsize=(15, 5))
ax[0].hist(data['AAPL_ret'], bins=50, alpha=0.5, label='real')
ax[0].hist(synthetic['AAPL_ret'], bins=50, alpha=0.5, label='synth')
ax[0].legend()
```

## 5.9 关键 takeaway

- 合成数据用于增广、隐私
- F-U-P 三维度评估
- GAN、Diffusion、LLM 三大方法
- 相关性保持是难点

## 5.10 风险与陷阱

### 隐私

- 成员推断攻击可能泄露
- 用 DP-GAN / PATE 增加噪声

### 分布偏移

- 合成 ≠ 真实
- TSTR 是金标准

### 相关性

- 单列分布好 ≠ 相关结构好
- 需评估相关矩阵

### 极端值

- 合成数据可能无极端事件
- 压力测试时要补充

## 5.11 参考

- Jordon et al., 2018 *PATE-GAN: Generating Synthetic Data with Differential Privacy Guarantees**
- Xu et al., 2019 *Modeling Tabular data using Conditional GAN**
- Ho et al., 2020 *Denoising Diffusion Probabilistic Models**
- Borisov et al., 2022 *Language Models Are Realistic Tabular Data Learners** (GReaT)
- SDV Documentation: https://sdv.dev/

## 5.12 现代工具

| 工具 | 类型 | 特点 |
|------|------|------|
| **SDV** | 表格 GAN | 多种模型 |
| **YData** | 时间序列 | TimeGAN |
| **GReaT** | LLM | 文本 schema |
| **TabDDPM** | Diffusion | SOTA |
| **Synthcity** | 综合 | 多方法 |
| **SmartNoise** | 差分隐私 | 隐私优先 |