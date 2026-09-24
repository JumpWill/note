# 第 1 章 — ML 在交易中的应用

## 章节目标

- 理解 ML 在投资行业的演进
- 掌握端到端交易工作流
- 熟悉主要 ML/交易用例

## 1.1 ML 在投资行业的崛起

### 驱动力

```
1. 数据爆炸
   - 价格、基本面 → 卫星 / 文本 / 信用卡 / 地理
2. 算力下降
   - GPU / 云计算 → 单位计算成本指数级下降
3. 算法突破
   - 深度学习 / Transformer / RL
4. 基础设施
   - Pandas / Scikit-learn / PyTorch / 各类开源
5. 竞争压力
   - 量化对冲基金主导 → 主动管理被迫跟进
```

### 关键时间线

- **2007**：Quantcast 公开 Quantopian 平台
- **2010s**：量化交易以另类数据为前沿
- **2014-2017**：文艺复兴、Two Sigma 等招聘大量 ML 研究员
- **2017**：AlphaGo 引发 AI 浪潮
- **2018**：深度学习应用于金融 NLP
- **2020+**：Transformer / RL 在交易中落地

## 1.2 端到端交易工作流

```
┌──────────────────────────────────────────────────────┐
│                   交易策略生命周期                      │
└──────────────────────────────────────────────────────┘

   数据源        ②特征工程        ③策略
   (Ch.2-3)     (Ch.4)         (Ch.5,17-22)
        ↓             ↓                ↓
   raw data  →  factors  →  signals  →  weights
        ↓             ↓                ↓
   ①采集        ④验证             ⑥回测
        ↓             ↓                ↓
   清洗后     补回测          评估
                                    ↓
                              ⑦执行 / 监控
```

### 详细步骤

#### 1. 数据获取（Ch.2-3）

```python
import yfinance as yf
import pandas_datareader.data as web

# 价格
prices = yf.download(['AAPL', 'MSFT'], start='2010-01-01')

# 宏观
gdp = web.DataReader('GDP', 'fred', start='2000-01-01')

# 另类数据
# - 卫星图像
# - 公司公告
# - 信用卡刷卡数据
# - 社交媒体情绪
```

#### 2. 特征工程 / Alpha 因子（Ch.4）

```python
import talib

# 动量
momentum_20d = prices['Close'].pct_change(20)

# RSI
rsi = talib.RSI(prices['Close'].values)

# 波动率
vol = prices['Close'].pct_change().rolling(20).std()

# 价值（市净率）
# 质量（ROE）
# 情绪（社交媒体 NLP）
```

#### 3. 信号 / 模型（Ch.7-22）

```python
from sklearn.linear_model import Ridge

model = Ridge(alpha=1.0)
model.fit(X_train, y_train)  # y 是未来收益
signals = model.predict(X_test)
```

#### 4. 验证（Ch.4）

```python
import alphalens

factor_data = alphalens.utils.get_clean_factor_and_forward_returns(
    factor=signals, prices=prices, quantiles=5
)

# IC 评估
ic = alphalens.performance.factor_information_coefficient(factor_data)
mean_ic = ic.mean()

# 检验：mean_ic > 0.02 通常认为是有效 alpha
```

#### 5. 组合优化（Ch.5）

```python
# 简单的等权配置 top N
top_n = signals[signals > signals.quantile(0.8)]
weights = top_n / top_n.abs().sum()
```

#### 6. 回测（Ch.5）

```python
import zipline
# 用 zipline-reloaded 回测完整策略
# 含滑点、手续费、冲击成本
```

#### 7. 评估（Ch.5）

```python
import pyfolio as pf

pf.create_full_tear_sheet(returns, benchmark_rets=benchmark)
# Sharpe、Sortino、最大回撤、Calmar...
```

#### 8. 执行

```python
# 连接到经纪商
# Alpaca / Interactive Brokers / 内部 OMS
```

## 1.3 ML 驱动的策略用例

### 1. 收益预测（回归）

```python
# 预测未来 5 日收益
y = close.pct_change(5).shift(-5)
model = LGBMRegressor
```

### 2. 方向分类

```python
# 二分类：涨 / 跌
y = (close.pct_change() > 0).astype(int)
model = XGBClassifier
```

### 3. 多空组合

```python
# top quintile long / bottom quintile short
long = signals[signals > q5]
short = signals[signals < q1]
```

### 4. 统计套利

```python
# 配对交易
spread = stock_a - hedge_ratio * stock_b
# z-score 判断偏离
z = (spread - spread.mean()) / spread.std()
# z > 2: short
# z < -2: long
```

### 5. 风险因子建模

```python
# Fama-French / 自定义因子
factors = ['MKT-RF', 'SMB', 'HML', 'RMW', 'CMA']
```

### 6. 组合优化

```python
# 均值-方差 / Black-Litterman / 风险平价
```

### 7. 文本数据（Ch.14-16）

```python
# 公告情绪、研报情感
# 财报电话会议
```

### 8. 强化学习（Ch.22）

```python
# 直接优化交易决策
# 如：何时买、何时卖、买多少
```

## 1.4 关键挑战

### 数据挑战

- **非平稳性**：金融市场变化（regime change）
- **低信噪比**：alpha 难发现
- **稀疏信号**：多数时间无 alpha
- **幸存者偏差**：已退市股票看不见
- **前视偏差**：用了未来信息
- **数据窥探**：overfit to history

### ML 挑战

- **回测过拟合** ：样本外表现差
- **过拟合**：参数多、噪声多
- **稀疏样本**：日数据 > 250 点 / 年
- **黑天鹅**：模型未见过

### 工程挑战

- 数据 pipeline
- 模型版本
- 监控与漂移检测
- 滑点 / 冲击成本

## 1.5 评估框架

### 因子层面

- **IC (Information Coefficient)**：Spearman 相关
- **ICIR (IC / std)**：稳定性
- **Quantile Returns**：分层收益
- **Factor Turnover**：换手率
- **Decay**：IC 衰减速度

### 组合层面

- **Sharpe Ratio**：超额收益 / 波动
- **Sortino**：超额收益 / 下行波动
- **Calmar**：年化收益 / 最大回撤
- **Information Ratio**：主动收益 / 跟踪误差

### 策略层面

- 年化收益
- 最大回撤
- 胜率
- 盈亏比
- 持仓时间分布
- 月度胜率

## 1.6 工作流图

```python
import matplotlib.pyplot as plt
import matplotlib.patches as patches

fig, ax = plt.subplots(figsize=(12, 4))
ax.set_xlim(0, 12)
ax.set_ylim(0, 4)
ax.axis('off')

stages = [
    ("Data Sources", 0.5, "Market / Fundamental / Alt"),
    ("Features", 2.5, "Alpha Factors"),
    ("Model", 4.5, "ML Algorithm"),
    ("Signal", 6.5, "Predictions"),
    ("Backtest", 8.5, "Strategy Eval"),
    ("Execution", 10.5, "Live Trading"),
]

for i, (title, x, sub) in enumerate(stages):
    rect = patches.FancyBboxPatch(
        (x, 1.5), 1.6, 1.0,
        boxstyle="round,pad=0.05",
        facecolor='lightblue', edgecolor='black'
    )
    ax.add_patch(rect)
    ax.text(x + 0.8, 2.1, title, ha='center', fontsize=11, weight='bold')
    ax.text(x + 0.8, 1.7, sub, ha='center', fontsize=8)

    if i < len(stages) - 1:
        ax.annotate('', xy=(x + 1.95, 2), xytext=(x + 1.65, 2),
                    arrowprops=dict(arrowstyle='->', lw=1.5))

ax.set_title("End-to-End ML4T Workflow", fontsize=14, weight='bold')
plt.tight_layout()
plt.show()
```

## 1.7 ML4T 与传统量化区别

| 维度 | 传统量化 | ML4T |
|------|----------|------|
| 模型 | 线性 / 因子模型 | 深度 / 非线性 |
| 数据 | 价格 + 基本面 | 加上另类 |
| 调参 | 较少 | 超多 |
| 解释 | 强 | 弱 |
| 容量 | 几十因子 | 千+ 因子 |
| 部署 | 简单 | 复杂 |
| 优势 | 稳健 | 数据多时强 |

## 1.8 本书定位

**不是**：

- 编程教程（假设 Python 熟练）
- 金融入门（假设知道股票 / 债券）
- 机器学习入门（假设知道 LR / NN）

**是**：

- ML + 量化交叉的实战桥梁
- 现代工具链介绍
- 多领域最新进展

## 1.9 关键 Notebook 内容

```python
# 01_machine_learning_for_trading/01_trading_workflow.ipynb
# 演示完整流水线：
# 1. 加载价格
# 2. 计算几个简单因子
# 3. 拟合 LR
# 4. 评估 IC
# 5. 简单回测
```

## 1.10 关键 takeaway

- ML 在交易中是**系统性 alpha 创造工具**，不是圣杯
- 端到端工作流：数据 → 特征 → 模型 → 信号 → 组合 → 回测 → 执行
- 因子评估（IC）和组合评估（Sharpe）都关键
- 数据挑战大于数据规模

## 1.11 与本书其他章节的关系

```
1 (overview)
├─ 2 (data) ─── 4 (factors) ──┐
│                              ├── 6-13 (ML)
├─ 3 (alt data) ─┘              │
│                                │
└─ 5 (portfolio) ───────────────┤
                                 │
                             14-22 (advanced)
```

## 1.12 参考

- Prado, 2018 *Advances in Financial Machine Learning* (Marcos López de)
- Chan, 2013 *Algorithmic Trading*
- Jansen, 2020 *Machine Learning for Trading* (本书)
- Aronson, 2007 *Evidence-Based Technical Analysis*