# 第 19 章 — RNN / LSTM / GRU

## 章节目标

- 序列建模基础
- LSTM/GRU 长依赖
- 双向 + 注意力

## 19.1 序列建模挑战

### 问题

- 长期依赖
- 梯度消失/爆炸
- 变长输入

### 解决方案

- LSTM/GRU（门控）
- Attention
- Transformer

## 19.2 RNN 基础

### 公式

$$
h_t = \tanh(W_{hh} h_{t-1} + W_{xh} x_t + b)
$$

- $h_t$：隐状态
- $x_t$：输入

```python
import tensorflow as tf

# 简单 RNN
from tensorflow.keras.layers import SimpleRNN

model = Sequential([
    SimpleRNN(64, input_shape=(seq_len, n_features)),
    Dense(1),
])
```

### 限制

- 短记忆
- 训练难
- 现代几乎不用

## 19.3 LSTM

### 三个门

$$
\begin{aligned}
f_t &= \sigma(W_f [h_{t-1}, x_t] + b_f) & \text{遗忘门} \\
i_t &= \sigma(W_i [h_{t-1}, x_t] + b_i) & \text{输入门} \\
o_t &= \sigma(W_o [h_{t-1}, x_t] + b_o) & \text{输出门} \\
\tilde{C}_t &= \tanh(W_C [h_{t-1}, x_t] + b_C) \\
C_t &= f_t \cdot C_{t-1} + i_t \cdot \tilde{C}_t \\
h_t &= o_t \cdot \tanh(C_t)
\end{aligned}
$$

### 实现

```python
from tensorflow.keras.layers import LSTM

model = Sequential([
    LSTM(64, return_sequences=True, input_shape=(seq_len, n_features)),
    LSTM(32),
    Dense(1),
])
```

## 19.4 GRU

### 两个门

$$
\begin{aligned}
z_t &= \sigma(W_z [h_{t-1}, x_t]) & \text{更新门} \\
r_t &= \sigma(W_r [h_{t-1}, x_t]) & \text{重置门} \\
\tilde{h}_t &= \tanh(W [r_t \cdot h_{t-1}, x_t]) \\
h_t &= (1 - z_t) \cdot h_{t-1} + z_t \cdot \tilde{h}_t
\end{aligned}
$$

### 实现

```python
from tensorflow.keras.layers import GRU

model = Sequential([
    GRU(64, return_sequences=True, input_shape=(seq_len, n_features)),
    GRU(32),
    Dense(1),
])
```

### GRU vs LSTM

- GRU 参数少（更易训练）
- LSTM 表达力稍强
- 实践中差别不大

## 19.5 双向 RNN

```python
from tensorflow.keras.layers import Bidirectional

model = Sequential([
    Bidirectional(LSTM(64, return_sequences=True), input_shape=(seq_len, n_features)),
    Bidirectional(LSTM(32)),
    Dense(1),
])
```

### 注意

- 双向前看后看
- 不能用于**真实交易**（用未来）
- 只适合回测 / 离线分析

## 19.6 Attention 机制

### 加权

$$
c = \sum_t \alpha_t h_t
$$

```python
from tensorflow.keras.layers import Attention

# Keras Attention
query = LSTM(64)(input_layer)
value = LSTM(64, return_sequences=True)(input_layer)

attention = Attention()([query, value])
output = Dense(1)(attention)
```

### 自注意力

```python
from tensorflow.keras.layers import MultiHeadAttention

x = MultiHeadAttention(num_heads=4, key_dim=64)(input_layer, input_layer)
```

## 19.7 实战：LSTM 收益预测

```python
"""LSTM 收益预测"""
import numpy as np
import pandas as pd
import yfinance as yf
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout, BatchNormalization
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
from sklearn.preprocessing import RobustScaler

# 1. 数据
prices = yf.download('^GSPC', start='2010-01-01')['Close']
returns = prices.pct_change().dropna()

# 2. 多频率特征
features = pd.DataFrame(index=returns.index)
for w in [1, 5, 20, 60]:
    features[f'ret_{w}'] = prices.pct_change(w)
    features[f'vol_{w}'] = returns.rolling(w).std()

target = returns.shift(-1).loc[features.index]
features = features.dropna()

# 3. 标准化
scaler = RobustScaler()
X_scaled = scaler.fit_transform(features)

# 4. 序列窗口
def make_seq(X, y, window):
    Xs, ys = [], []
    for i in range(window, len(X)):
        Xs.append(X[i-window:i])
        ys.append(y[i])
    return np.array(Xs), np.array(ys)

window = 60
X_seq, y_seq = make_seq(X_scaled, target.values, window)

# 5. 模型
model = Sequential([
    LSTM(64, return_sequences=True, input_shape=(window, X_seq.shape[2])),
    Dropout(0.3),
    LSTM(32),
    BatchNormalization(),
    Dropout(0.3),
    Dense(1),
])
model.compile(optimizer='adam', loss='mse')

# 6. 时序 CV
split = int(0.8 * len(X_seq))
early_stop = EarlyStopping(patience=10, restore_best_weights=True)
reduce_lr = ReduceLROnPlateau(factor=0.5, patience=5)

model.fit(
    X_seq[:split], y_seq[:split],
    validation_data=(X_seq[split:], y_seq[split:]),
    epochs=50, batch_size=32,
    callbacks=[early_stop, reduce_lr],
)

# 7. 评估
pred = model.predict(X_seq[split:])
print(f"IC: {np.corrcoef(pred.flatten(), y_seq[split:])[0, 1]:.4f}")
```

## 19.8 实战：多资产 LSTM

```python
"""多资产 LSTM"""
import numpy as np
import pandas as pd
import yfinance as yf
from tensorflow.keras.models import Model
from tensorflow.keras.layers import LSTM, Dense, Dropout, Input, Concatenate

# 1. 多资产数据
tickers = ['AAPL', 'MSFT', 'GOOGL']
prices = yf.download(tickers, start='2015-01-01')['Close']
returns = prices.pct_change().dropna()

# 2. 每个资产单独 LSTM
def build_model_per_stock(window=20, n_features=1):
    input_layer = Input(shape=(window, n_features))
    x = LSTM(32, return_sequences=True)(input_layer)
    x = Dropout(0.3)(x)
    x = LSTM(16)(x)
    output = Dense(1)(x)
    return Model(input_layer, output)

# 每个股票
models = {}
for ticker in tickers:
    models[ticker] = build_model_per_stock()
    models[ticker].compile(optimizer='adam', loss='mse')

# 训练
def make_seq_single(prices, window=20):
    X, y = [], []
    for i in range(window, len(prices)):
        X.append(prices[i-window:i])
        y.append(prices[i])
    return np.array(X), np.array(y)

for ticker in tickers:
    X, y = make_seq_single(returns[ticker].values)
    models[ticker].fit(X, y, epochs=30, verbose=0)

# 联合预测
preds = {}
for ticker in tickers:
    X, _ = make_seq_single(returns[ticker].values)
    preds[ticker] = models[ticker].predict(X[-100:]).flatten()

# 多空
signal = pd.DataFrame(preds, index=returns.index[-100:])
weights = signal.rank(axis=1).sub(1).div(len(tickers) - 1)
```

## 19.9 Encoder-Decoder

### 思想

- Encoder 编码输入序列
- Decoder 解码输出序列

```python
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.models import Model
from tensorflow.keras.layers import Input, RepeatVector, TimeDistributed

window = 20
n_features = 5
output_steps = 5

# Encoder
encoder_inputs = Input(shape=(window, n_features))
encoder = LSTM(64, return_state=True)
encoder_outputs, state_h, state_c = encoder(encoder_inputs)
encoder_states = [state_h, state_c]

# Decoder
decoder_inputs = RepeatVector(output_steps)(state_h)
decoder_lstm = LSTM(64, return_sequences=True)
decoder_outputs = decoder_lstm(decoder_inputs, initial_state=encoder_states)
decoder_outputs = TimeDistributed(Dense(1))(decoder_outputs)

model = Model(encoder_inputs, decoder_outputs)
model.compile(optimizer='adam', loss='mse')
```

## 19.10 Attention 可视化

```python
"""LSTM + 注意力"""
import tensorflow as tf
from tensorflow.keras.layers import LSTM, Dense, Dropout, Attention
from tensorflow.keras.models import Model
from tensorflow.keras.layers import Input

def build_attention_model(window, n_features):
    inputs = Input(shape=(window, n_features))
    lstm_out = LSTM(64, return_sequences=True)(inputs)

    # 自注意力
    attention = Attention()([lstm_out, lstm_out])

    # 全局池化
    pooled = tf.reduce_sum(attention, axis=1)
    output = Dense(1)(pooled)

    return Model(inputs, output)
```

## 19.11 实战：完整 LSTM 流水线

```python
"""LSTM 完整流水线"""
import numpy as np
import pandas as pd
import yfinance as yf
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout, BatchNormalization
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
from sklearn.preprocessing import RobustScaler
from sklearn.model_selection import TimeSeriesSplit
import pyfolio as pf

# 1. 数据
prices = yf.download(['AAPL', 'MSFT'], start='2010-01-01')['Close']
returns = prices.pct_change().dropna()

# 2. 特征
features = pd.DataFrame(index=returns.index)
for stock in prices.columns:
    for w in [5, 20]:
        features[f'{stock}_ret_{w}'] = prices[stock].pct_change(w)
        features[f'{stock}_vol_{w}'] = returns[stock].rolling(w).std()

features = features.dropna()
target = returns.loc[features.index].mean(axis=1)  # 跨资产平均

# 3. 标准化
scaler = RobustScaler()
X_scaled = scaler.fit_transform(features)

# 4. 序列
window = 30
def make_seq(X, y, w):
    Xs, ys = [], []
    for i in range(w, len(X)):
        Xs.append(X[i-w:i])
        ys.append(y[i])
    return np.array(Xs), np.array(ys)

X_seq, y_seq = make_seq(X_scaled, target.values, window)

# 5. 时序 CV
tscv = TimeSeriesSplit(n_splits=5, test_size=63)
predictions = []

for train_idx, test_idx in tscv.split(X_seq):
    model = Sequential([
        LSTM(64, return_sequences=True, input_shape=(window, X_seq.shape[2])),
        Dropout(0.3),
        LSTM(32),
        Dropout(0.3),
        Dense(1),
    ])
    model.compile(optimizer='adam', loss='mse')

    early_stop = EarlyStopping(patience=10, restore_best_weights=True)
    model.fit(
        X_seq[train_idx], y_seq[train_idx],
        validation_data=(X_seq[test_idx], y_seq[test_idx]),
        epochs=50, batch_size=32,
        callbacks=[early_stop], verbose=0,
    )

    pred = pd.Series(
        model.predict(X_seq[test_idx]).flatten(),
        index=target.index[window:][test_idx]
    )
    predictions.append(pred)

predictions = pd.concat(predictions)

# 6. 评估
strategy_returns = target.reindex(predictions.index) * np.sign(predictions)
strategy_returns = strategy_returns.dropna()

# Sharpe
sharpe = strategy_returns.mean() / strategy_returns.std() * np.sqrt(252)
print(f"Sharpe: {sharpe:.2f}")
```

## 19.12 关键 Notebook

```
19_RNN_for_trading/
├── 01_lstm_returns.ipynb
├── 02_gru_returns.ipynb
├── 03_bidirectional.ipynb
├── 04_attention_lstm.ipynb
└── 05_seq2seq_returns.ipynb
```

## 19.13 关键 takeaway

- LSTM/GRU 解决长依赖
- GRU 更快，LSTM 稍准
- 双向不能用于真实交易
- Transformer 正在替代 RNN

## 19.14 RNN vs LSTM vs Transformer

| 维度 | RNN | LSTM | Transformer |
|------|-----|------|-------------|
| 长依赖 | 弱 | 中 | **强** |
| 训练速度 | 中 | 慢 | **中** |
| 内存 | 少 | 多 | 多 |
| 并行性 | 低 | 低 | **高** |
| 解释 | 中 | 中 | **强** |

## 19.15 实战陷阱

### 过拟合

- LSTM 极易过拟合
- Dropout / 早停 / 数据增强

### 计算成本

- LSTM 训练慢
- 用 GRU 节省时间

### 状态持久

- 实时推理需保存状态
- 用 streaming inference

## 19.16 参考

- Hochreiter & Schmidhuber, 1997 *Long Short-Term Memory* (LSTM 原始)
- Cho et al., 2014 *Learning Phrase Representations using RNN Encoder-Decoder* (GRU 原始)
- Bahdanau et al., 2014 *Neural Machine Translation by Jointly Learning to Align and Translate* (Attention 原始)
- Chollet, 2021 *Deep Learning with Python*