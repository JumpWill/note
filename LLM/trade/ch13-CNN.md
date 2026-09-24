# 第 18 章 — CNN：金融时间序列

## 章节目标

- 用 1D CNN 处理金融序列
- 多尺度模式识别
- 与时间卷积网络（TCN）

## 18.1 CNN 在金融中

### 应用

- 价格模式识别（chart pattern）
- 多频率信号
- 多资产横向
- 异常检测

## 18.2 一维卷积

### 卷积运算

$$
y[i] = \sum_k w[k] \cdot x[i - k]
$$

- 局部感受野
- 权重共享
- 平移不变性

```python
import numpy as np

# 1D 卷积示意
def conv1d(x, w):
    n = len(x)
    m = len(w)
    y = np.zeros(n - m + 1)
    for i in range(len(y)):
        y[i] = np.sum(x[i:i+m] * w)
    return y

x = np.sin(np.linspace(0, 4*np.pi, 100))
w = np.array([0.2, 0.3, 0.5])  # 平滑核
y = conv1d(x, w)
```

### 多通道

- 类似 RGB 图像
- 每个通道 = 一个特征
- 多滤波器 = 多模式

## 18.3 Keras Conv1D

```python
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Conv1D, MaxPooling1D, Flatten, Dense, Dropout

model = Sequential([
    Conv1D(filters=32, kernel_size=3, activation='relu', input_shape=(seq_len, n_features)),
    Conv1D(filters=32, kernel_size=3, activation='relu'),
    MaxPooling1D(pool_size=2),
    Conv1D(filters=64, kernel_size=3, activation='relu'),
    Conv1D(filters=64, kernel_size=3, activation='relu'),
    MaxPooling1D(pool_size=2),
    Flatten(),
    Dense(64, activation='relu'),
    Dropout(0.3),
    Dense(1),
])
```

### 参数

- `filters`：滤波器数（输出通道）
- `kernel_size`：卷积核大小
- `strides`：步长
- `padding`：'same' / 'valid'
- `activation`：激活函数

## 18.4 多尺度模式

```python
# 不同 kernel size 提取不同尺度
from tensorflow.keras.layers import Input, Concatenate
from tensorflow.keras.models import Model

input_layer = Input(shape=(seq_len, n_features))

# 不同尺度
conv1 = Conv1D(32, kernel_size=3, activation='relu')(input_layer)
conv2 = Conv1D(32, kernel_size=5, activation='relu')(input_layer)
conv3 = Conv1D(32, kernel_size=7, activation='relu')(input_layer)

merged = Concatenate()([conv1, conv2, conv3])
x = MaxPooling1D(2)(merged)
x = Flatten()(x)
x = Dense(64, activation='relu')(x)
output = Dense(1)(x)

model = Model(inputs=input_layer, outputs=output)
```

## 18.5 TCN（时间卷积网络）

### 思想

- 因果卷积（不偷看未来）
- 膨胀卷积（指数级感受野）

```python
from tensorflow.keras.layers import Conv1D, Dropout, Add, Input
from tensorflow.keras.models import Model
from tensorflow.keras.activations import relu

def residual_block(x, dilation_rate, n_filters, kernel_size=3):
    # 因果填充
    padding = (kernel_size - 1) * dilation_rate
    x_padded = tf.pad(x, [[0, 0], [padding, 0], [0, 0]])

    conv1 = Conv1D(n_filters, kernel_size, dilation_rate=dilation_rate,
                   padding='valid', activation='relu')(x_padded)
    conv1 = Dropout(0.3)(conv1)

    conv2 = Conv1D(n_filters, kernel_size, dilation_rate=dilation_rate,
                   padding='valid', activation='linear')(conv1)
    conv2 = Dropout(0.3)(conv2)

    # 残差
    if x.shape[-1] != n_filters:
        x = Conv1D(n_filters, 1, padding='same')(x)

    return Add()([x, conv2])

def build_tcn(input_shape, n_blocks=4, n_filters=32):
    inputs = Input(shape=input_shape)
    x = inputs
    for i in range(n_blocks):
        x = residual_block(x, dilation_rate=2**i, n_filters=n_filters)
    x = Dense(1)(x)
    return Model(inputs, x)
```

## 18.6 多资产横向 CNN

```python
"""多资产横向 CNN"""
import numpy as np
import pandas as pd
import yfinance as yf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Conv1D, MaxPooling1D, Flatten, Dense, Dropout
from tensorflow.keras.optimizers import Adam

# 1. 多资产数据
tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META']
prices = yf.download(tickers, start='2015-01-01')['Close']
returns = prices.pct_change().dropna()

# 2. 转置：(n_samples, n_assets, 1)
X = returns.T.values[:, :, np.newaxis]  # (n_assets, n_samples, 1)

# 3. 模型：每个资产是 channel
model = Sequential([
    Conv1D(32, kernel_size=3, activation='relu', input_shape=(X.shape[1], X.shape[2])),
    Conv1D(32, kernel_size=3, activation='relu'),
    MaxPooling1D(2),
    Conv1D(64, kernel_size=3, activation='relu'),
    MaxPooling1D(2),
    Flatten(),
    Dense(64, activation='relu'),
    Dropout(0.3),
    Dense(len(tickers)),  # 每个资产预测
])

model.compile(optimizer=Adam(learning_rate=1e-4), loss='mse')

# y 也是形状 (n_samples, n_assets)
y = returns.values  # (n_samples, n_assets)
model.fit(X[0], y, epochs=50, batch_size=32)
```

## 18.7 实战：CNN 多因子预测

```python
"""CNN 完整流水线"""
import numpy as np
import pandas as pd
import yfinance as yf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Conv1D, MaxPooling1D, Dropout, Dense
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
from sklearn.preprocessing import RobustScaler

# 1. 数据
prices = yf.download('AAPL', start='2010-01-01')['Close']

# 2. 多频率特征
features = pd.DataFrame(index=prices.index)
for w in [5, 10, 20, 60]:
    features[f'ret_{w}'] = prices.pct_change(w)
    features[f'vol_{w}'] = prices.pct_change().rolling(w).std()
    features[f'sma_{w}'] = prices / prices.rolling(w).mean()

features['rsi'] = compute_rsi(prices, 14)
features = features.dropna()

target = prices.pct_change(5).shift(-5).loc[features.index]

# 3. 序列窗口
def make_seq(X, y, window):
    Xs, ys = [], []
    for i in range(window, len(X)):
        Xs.append(X[i-window:i])
        ys.append(y[i])
    return np.array(Xs), np.array(ys)

window = 30
X_arr = features.values
y_arr = target.values

scaler = RobustScaler()
X_arr_scaled = scaler.fit_transform(X_arr)

X_seq, y_seq = make_seq(X_arr_scaled, y_arr, window)

# 4. 模型
model = Sequential([
    Conv1D(32, kernel_size=3, activation='relu', input_shape=(window, X_seq.shape[2])),
    Conv1D(32, kernel_size=3, activation='relu'),
    MaxPooling1D(2),
    Dropout(0.3),
    Conv1D(64, kernel_size=3, activation='relu'),
    MaxPooling1D(2),
    Dropout(0.3),
    tf.keras.layers.Flatten(),
    Dense(64, activation='relu'),
    Dropout(0.3),
    Dense(1),
])
model.compile(optimizer='adam', loss='mse')

# 5. 时序训练
split = int(0.8 * len(X_seq))
early_stop = EarlyStopping(patience=10, restore_best_weights=True)
reduce_lr = ReduceLROnPlateau(factor=0.5, patience=5)

model.fit(
    X_seq[:split], y_seq[:split],
    validation_data=(X_seq[split:], y_seq[split:]),
    epochs=50, batch_size=32,
    callbacks=[early_stop, reduce_lr], verbose=1,
)
```

## 18.8 模式识别：chart patterns

```python
"""CNN chart pattern 识别"""

# 假设我们已标注了 chart patterns
# （三角形、头肩、双底等）

from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Conv2D, MaxPooling2D, Flatten, Dense, Dropout

# 输入：60x60 OHLC 图
model = Sequential([
    Conv2D(32, (3, 3), activation='relu', input_shape=(60, 60, 1)),
    MaxPooling2D(2, 2),
    Conv2D(64, (3, 3), activation='relu'),
    MaxPooling2D(2, 2),
    Conv2D(128, (3, 3), activation='relu'),
    MaxPooling2D(2, 2),
    Flatten(),
    Dense(128, activation='relu'),
    Dropout(0.5),
    Dense(num_patterns, activation='softmax'),
])
```

## 18.9 实战：多频率 CNN 集成

```python
"""多频率集成"""
import numpy as np
import pandas as pd
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Conv1D, MaxPooling1D, Dense, Dropout
from sklearn.preprocessing import RobustScaler

def build_cnn(input_shape):
    return Sequential([
        Conv1D(32, 3, activation='relu', input_shape=input_shape),
        Conv1D(32, 3, activation='relu'),
        MaxPooling1D(2),
        Dropout(0.3),
        Conv1D(64, 3, activation='relu'),
        MaxPooling1D(2),
        Dropout(0.3),
        tf.keras.layers.Flatten(),
        Dense(64, activation='relu'),
        Dropout(0.3),
        Dense(1),
    ])

# 多个频率
freq_models = {}
for window in [5, 10, 20, 60]:
    X_seq, y_seq = make_seq(features_scaled, target, window)
    model = build_cnn((window, X_seq.shape[2]))
    model.compile(optimizer='adam', loss='mse')
    model.fit(X_seq, y_seq, epochs=30, verbose=0)
    freq_models[window] = model

# 集成预测
def ensemble_predict(X_new, windows=[5, 10, 20, 60]):
    preds = []
    for w in windows:
        # 准备该频率输入
        X_w = make_seq_for_predict(X_new, w)
        preds.append(freq_models[w].predict(X_w))
    return np.mean(preds, axis=0)
```

## 18.10 关键 Notebook

```
18_cnn_for_finance/
├── 01_conv_basics.ipynb
├── 02_tcn_trading.ipynb
├── 03_multi_scale_cnn.ipynb
└── 04_chart_patterns.ipynb
```

## 18.11 关键 takeaway

- CNN 适合局部模式
- 1D CNN 用于序列
- 多 kernel 提取多尺度
- TCN 兼顾因果和长依赖

## 18.12 CNN vs RNN

| 维度 | CNN | RNN |
|------|-----|-----|
| 并行性 | **高** | 低 |
| 长依赖 | 弱（需 TCN） | **强** |
| 速度 | **快** | 慢 |
| 适用 | 短局部模式 | 长序列 |

## 18.13 参考

- LeCun et al., 1998 *Gradient-Based Learning Applied to Document Recognition*
- Oord et al., 2016 *WaveNet: A Generative Model for Raw Audio* (膨胀卷积)
- Bai et al., 2018 *An Empirical Evaluation of Generic Convolutional and Recurrent Networks for Sequence Modeling* (TCN)