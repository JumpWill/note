# 第 6 章 — ML 流程

## 章节目标

- 理解 ML 在交易中的端到端流程
- 数据 / 特征 / 模型 / 评估各阶段挑战
- 交易特有的注意事项

## 6.1 标准 ML 流程

```
1. 问题定义
   ↓
2. 数据收集
   ↓
3. 数据清洗 / EDA
   ↓
4. 特征工程
   ↓
5. 模型选择
   ↓
6. 训练 / 验证 / 测试
   ↓
7. 部署 / 监控
   ↓
8. 反馈循环
```

## 6.2 交易中的 ML 任务

### 回归（收益预测）

```python
# 目标：预测次日收益
y = close.pct_change().shift(-1)

# 特征：动量、波动、价值
X = pd.DataFrame({
    'momentum_20': close.pct_change(20),
    'vol_20': close.pct_change().rolling(20).std(),
})

# 模型
from sklearn.linear_model import Ridge
model = Ridge(alpha=1.0)
```

### 分类（涨跌方向）

```python
y = (close.pct_change().shift(-1) > 0).astype(int)

from sklearn.ensemble import GradientBoostingClassifier
model = GradientBoostingClassifier()
```

### 多任务 / 多输出

```python
# 同时预测：收益 + 波动
y = pd.DataFrame({
    'return': close.pct_change().shift(-1),
    'vol': close.pct_change().rolling(5).std().shift(-5),
})
```

## 6.3 数据准备

### 时间对齐

```python
# 避免未来信息（look-ahead bias）
X_lagged = X.shift(1)
y_lagged = y.shift(-1)
```

### 缺失处理

```python
# 前向填充（金融数据常用）
df.fillna(method='ffill', inplace=True)

# 限制（避免填太多）
df.fillna(method='ffill', limit=5, inplace=True)
```

### 标准化

```python
from sklearn.preprocessing import StandardScaler

scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)
```

### 行业中性化

```python
# 减去行业均值
industry_means = X.groupby(industry).transform('mean')
X_neutral = X - industry_means
```

## 6.4 时序交叉验证

```python
from sklearn.model_selection import TimeSeriesSplit

tscv = TimeSeriesSplit(n_splits=5)

for train_idx, test_idx in tscv.split(X):
    X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
    y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

    model.fit(X_train, y_train)
    score = model.score(X_test, y_test)
```

### 注意

- ❌ **不能**用 `KFold`（乱序 → 数据泄露）
- ✅ **必须**用 `TimeSeriesSplit` 或 purged CV
- ✅ **谨慎**用 `StratifiedKFold`（仅对分类）

## 6.5 评估指标

### 回归

```python
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

mse = mean_squared_error(y_test, y_pred)
mae = mean_absolute_error(y_test, y_pred)
r2 = r2_score(y_test, y_pred)
```

### 分类

```python
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, roc_auc_score, confusion_matrix,
)

acc = accuracy_score(y_test, y_pred)
auc = roc_auc_score(y_test, y_prob)
```

### 交易特定

- **IC (Information Coefficient)**：因子与未来收益的相关
- **Sharpe Ratio**：策略夏普
- **Max Drawdown**：最大回撤

## 6.6 模型选择

| 任务 | 推荐模型 |
|------|----------|
| 表格 / 因子预测 | 树模型（XGBoost / LightGBM） |
| 时间序列 | ARIMA / GARCH |
| 文本数据 | BERT / FinBERT |
| 图像数据 | CNN |
| 序列预测 | RNN / LSTM / Transformer |
| 复杂决策 | RL |

## 6.7 过拟合检测

### 训练 vs 验证

```python
# 关键指标：是否过拟合
train_score = model.score(X_train, y_train)
val_score = model.score(X_val, y_val)

if train_score - val_score > 0.1:  # 经验值
    print("可能过拟合")
```

### 学习曲线

```python
import numpy as np

train_sizes = np.linspace(0.1, 1.0, 10)
train_scores = []
val_scores = []

for size in train_sizes:
    n = int(len(X_train) * size)
    model.fit(X_train[:n], y_train[:n])
    train_scores.append(model.score(X_train[:n], y_train[:n]))
    val_scores.append(model.score(X_val, y_val))

plt.plot(train_sizes, train_scores, label='train')
plt.plot(train_sizes, val_scores, label='val')
plt.xlabel('Training size')
plt.ylabel('Score')
plt.legend()
```

### 偏差-方差

- **高偏差**：train 与 val 都差 → 模型欠拟合
- **高方差**：train 好，val 差 → 过拟合

## 6.8 超参调优

### 网格搜索（不推荐，时序下会过拟合）

```python
from sklearn.model_selection import GridSearchCV

param_grid = {
    'n_estimators': [100, 200, 500],
    'max_depth': [3, 5, 7],
}

grid = GridSearchCV(model, param_grid, cv=tscv)
grid.fit(X_train, y_train)
```

### 贝叶斯优化

```python
import optuna

def objective(trial):
    params = {
        'n_estimators': trial.suggest_int('n_estimators', 50, 500),
        'max_depth': trial.suggest_int('max_depth', 3, 10),
        'learning_rate': trial.suggest_float('lr', 0.01, 0.3, log=True),
    }
    model = LGBMRegressor(**params)
    model.fit(X_train, y_train)
    return model.score(X_val, y_val)

study = optuna.create_study(direction='maximize')
study.optimize(objective, n_trials=50)
```

### Walk-Forward Optimization

```python
# 模拟真实部署
for train_start, train_end in rolling_windows:
    # 训练
    model.fit(X[train_start:train_end], y[train_start:train_end])

    # 预测下一窗口
    pred = model.predict(X[train_end:train_end + test_size])

    # 评估
    score = metric(y[test_size], pred)
```

## 6.9 流水线（Pipeline）

```python
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.model_selection import TimeSeriesSplit

pipe = Pipeline([
    ('scaler', StandardScaler()),
    ('model', Ridge(alpha=1.0)),
])

tscv = TimeSeriesSplit(n_splits=5)
scores = cross_val_score(pipe, X, y, cv=tscv)
```

## 6.10 模型选择：复杂度权衡

```
线性 < 树模型 < 集成 < 神经网络
  ↓         ↓         ↓         ↓
 强解释    中等       难解释    难解释
低容量    中等       高        高
小数据友好       大数据友好
```

### 经验

- **小数据 + 解释重要**：线性 / 树
- **大数据 + 性能重要**：深度学习
- **NLP**：Transformer
- **时序**：LSTM / Transformer

## 6.11 实战：完整流水线

```python
"""ML4T 完整流水线"""
import pandas as pd
import numpy as np
import yfinance as yf
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error
import alphalens

# 1. 数据
prices = yf.download(['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META'],
                     start='2015-01-01')['Close']
returns = prices.pct_change()

# 2. 特征
def build_features(prices):
    features = pd.DataFrame()
    for col in prices.columns:
        s = prices[col]
        features[f'{col}_mom_5'] = s.pct_change(5)
        features[f'{col}_mom_20'] = s.pct_change(20)
        features[f'{col}_vol_20'] = s.pct_change().rolling(20).std()
        features[f'{col}_rsi_14'] = compute_rsi(s, 14)
    return features.dropna()

# 4. 标签
y = returns.shift(-1).stack().dropna()
X = build_features(prices).stack()

# 5. 时间序列 CV
tscv = TimeSeriesSplit(n_splits=5)
predictions = []

for train_idx, test_idx in tscv.split(X):
    X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
    y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    model = Ridge(alpha=1.0)
    model.fit(X_train_scaled, y_train)

    pred = model.predict(X_test_scaled)
    predictions.append((y_test, pd.Series(pred, index=y_test.index)))

# 6. 评估
all_y = pd.concat([y for y, _ in predictions])
all_pred = pd.concat([p for _, p in predictions])

print(f"Test MSE: {mean_squared_error(all_y, all_pred):.6f}")
print(f"IC: {all_y.corr(all_pred):.4f}")
```

## 6.12 实战陷阱

### 不可重现

```python
# ❌ 没设随机种子
model.fit(X, y)  # 每次不同结果

# ✅ 设定
import random
random.seed(42)
np.random.seed(42)
```

### 隐含未来信息

```python
# ❌ 用未来信息
X['next_close'] = close.shift(-1)

# ✅ 严格滞后
X['next_close'] = close.shift(-1)  # 但 y 不能用这个
```

### 不切实际换手率

```python
# ❌ 每日重平衡（高换手率）
# ✅ 现实换手率（如月度）
```

## 6.13 关键 takeaway

- 时序数据不能用普通 CV，必须用 TimeSeriesSplit 或 purged CV
- 样本外表现是关键
- 警惕未来信息泄露
- 评估要看 Sharpe 等交易指标，不是简单 MSE

## 6.14 关键 Notebook

```
06_machine_learning_process/
├── 01_data_preparation.ipynb
├── 02_feature_engineering.ipynb
├── 03_model_training.ipynb
├── 04_hyperparameter_tuning.ipynb
├── 05_model_evaluation.ipynb
└── 06_pipeline_construction.ipynb
```

## 6.15 参考

- Hastie, Tibshirani, Friedman, 2009 *The Elements of Statistical Learning*
- López de Prado, 2018 *Advances in Financial Machine Learning*
- Bergstra & Bengio, 2012 *Random Search for Hyper-Parameter Optimization*
- Bailey et al., 2015 *The Probability of Backtest Overfitting*