# 代码示例精选

> 本文汇集书中关键的实战代码片段，便于快速参考与复用。

## A. 数据获取与清洗

### 1. Yahoo Finance

```python
import yfinance as yf
import pandas as pd

tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META']
prices = yf.download(tickers, start='2015-01-01', end='2024-01-01')['Close']
returns = prices.pct_change().dropna()
```

### 2. Quandl (已 deprecated，但概念可参考)

```python
import quandl

quandl.ApiConfig.api_key = '<YOUR_KEY>'
data = quandl.get('WIKI/AAPL', start_date='2015-01-01')
```

### 3. Alpha Vantage

```python
from alpha_vantage.timeseries import TimeSeries
ts = TimeSeries(key='<YOUR_KEY>', output_format='pandas')
data, meta = ts.get_daily(symbol='AAPL', outputsize='full')
```

### 4. Polygon.io

```python
from polygon import RESTClient
client = RESTClient('<YOUR_KEY>')
aggs = client.get_aggs('AAPL', 1, 'day', '2020-01-01', '2024-01-01')
df = pd.DataFrame(aggs)
```

## B. ITCH 数据解析

### 5. NASDAQ ITCH 解析

```python
import struct
from pathlib import Path

def parse_itch(message):
    """解析 ITCH 消息（NASDAQ 总成交报告）。"""
    return {
        'stock_locate': struct.unpack('<H', message[0:2])[0],
        'tracking_number': struct.unpack('<H', message[2:4])[0],
        'timestamp': struct.unpack('<Q', message[4:12])[0] / 1e9,
        'event_code': message[12:13].decode(),
        'order_ref': struct.unpack('<Q', message[13:21])[0],
        'buy_sell': message[21:22].decode(),
        'shares': struct.unpack('<I', message[22:26])[0],
    }

# 读取
with open('01302020.NASDAQ_ITCH50', 'rb') as f:
    while True:
        msg = f.read(26)
        if not msg:
            break
        parsed = parse_itch(msg)
        # 处理
```

### 6. 订单簿重建

```python
class OrderBook:
    def __init__(self):
        self.bids = {}  # price -> {order_ref: shares}
        self.asks = {}

    def add(self, side, price, order_ref, shares):
        book = self.bids if side == 'B' else self.asks
        if price not in book:
            book[price] = {}
        book[price][order_ref] = shares

    def cancel(self, side, order_ref, shares):
        book = self.bids if side == 'B' else self.asks
        for price in book:
            if order_ref in book[price]:
                book[price][order_ref] -= shares
                if book[price][order_ref] <= 0:
                    del book[price][order_ref]
                break

    def execute(self, side, order_ref, shares):
        book = self.bids if side == 'B' else self.asks
        for price in book:
            if order_ref in book[price]:
                book[price][order_ref] -= shares
                if book[price][order_ref] <= 0:
                    del book[price][order_ref]
                break

    def get_snapshot(self):
        return {
            'best_bid': max(self.bids.keys()) if self.bids else None,
            'best_ask': min(self.asks.keys()) if self.asks else None,
            'bid_size_5': sum([sum(p.values()) for p in list(self.bids.values())[-5:]]),
            'ask_size_5': sum([sum(p.values()) for p in list(self.asks.values())[-5:]]),
        }
```

## C. 因子工程

### 7. 动量因子

```python
def momentum(prices, lookback=252, skip=21):
    """12-1 动量。"""
    return prices.pct_change(lookback).shift(skip)

def macd(prices, fast=12, slow=26, signal=9):
    """MACD 指标。"""
    ema_fast = prices.ewm(span=fast).mean()
    ema_slow = prices.ewm(span=slow).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal).mean()
    return macd_line - signal_line
```

### 8. RSI

```python
def rsi(prices, window=14):
    """RSI 指标。"""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0).rolling(window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))
```

### 9. Bollinger Bands

```python
def bollinger_bands(prices, window=20, num_std=2):
    """布林带。"""
    sma = prices.rolling(window).mean()
    std = prices.rolling(window).std()
    upper = sma + num_std * std
    lower = sma - num_std * std
    return upper, sma, lower

def bollinger_signal(prices, window=20, num_std=2):
    """布林带信号。"""
    upper, sma, lower = bollinger_bands(prices, window, num_std)
    signal = pd.Series(0, index=prices.index)
    signal[prices < lower] = 1  # 买入
    signal[prices > upper] = -1  # 卖出
    return signal
```

### 10. Dollar Bars

```python
def dollar_bars(trades, threshold):
    """构造美元 bar。"""
    bars = []
    cum_dollar = 0
    bar_start = 0

    for i, trade in trades.iterrows():
        cum_dollar += trade['price'] * trade['size']

        if cum_dollar >= threshold:
            bar = {
                'open': trades.iloc[bar_start]['price'],
                'high': trades.iloc[bar_start:i]['price'].max(),
                'low': trades.iloc[bar_start:i]['price'].min(),
                'close': trade['price'],
                'volume': trades.iloc[bar_start:i]['size'].sum(),
                'timestamp': trade['timestamp'],
            }
            bars.append(bar)
            cum_dollar = 0
            bar_start = i + 1

    return pd.DataFrame(bars)
```

## D. 因子评估（alphalens）

### 11. 准备 alphalens 数据

```python
import alphalens

# 因子
factor = momentum(prices)

# 转为 alphalens 格式
factor_data = alphalens.utils.get_clean_factor_and_forward_returns(
    factor=factor,
    prices=prices,
    quantiles=5,
    periods=(1, 5, 21),
)
```

### 12. IC 分析

```python
from alphalens.performance import factor_information_coefficient

mean_ic_by_day = factor_information_coefficient(factor_data)
print(f"Mean IC: {mean_ic_by_day.mean():.4f}")
```

### 13. Quantile 收益

```python
from alphalens.performance import mean_return_by_quantile

quantile_returns = mean_return_by_quantile(factor_data, by_date=False)
print(quantile_returns)
```

## E. ML 流水线

### 14. 完整 sklearn pipeline

```python
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.model_selection import TimeSeriesSplit, GridSearchCV

pipe = Pipeline([
    ('scaler', StandardScaler()),
    ('model', Ridge()),
])

params = {'model__alpha': [0.1, 1.0, 10.0]}

search = GridSearchCV(
    pipe, params,
    cv=TimeSeriesSplit(n_splits=5),
    scoring='neg_mean_squared_error',
)

search.fit(X, y)
print(search.best_params_)
```

### 15. 自定义 Transformer

```python
from sklearn.base import BaseEstimator, TransformerMixin

class FeatureEngineer(BaseEstimator, TransformerMixin):
    def __init__(self, momentum_windows=[5, 20, 60]):
        self.momentum_windows = momentum_windows

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        X = X.copy()
        for w in self.momentum_windows:
            X[f'mom_{w}'] = X['close'].pct_change(w)
            X[f'vol_{w}'] = X['close'].pct_change().rolling(w).std()
        return X.dropna()
```

### 16. 时序交叉验证

```python
from sklearn.model_selection import TimeSeriesSplit

tscv = TimeSeriesSplit(n_splits=5, test_size=63)
for train_idx, test_idx in tscv.split(X):
    X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
    y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

    model = build_model()
    model.fit(X_train, y_train)

    pred = model.predict(X_test)
```

## F. 回测（zipline-reloaded）

### 17. 简单策略

```python
from zipline import run_algorithm
from zipline.api import order_target, symbol, record, schedule_function, date_rules, time_rules

def initialize(context):
    context.asset = symbol('AAPL')
    context.window = 20
    schedule_function(
        rebalance,
        date_rules.every_day(),
        time_rules.market_open(),
    )

def rebalance(context, data):
    prices = data.history(context.asset, 'price', context.window + 1, '1d')
    momentum = prices[-1] / prices[0] - 1

    if momentum > 0:
        order_target(context.asset, 100)
    else:
        order_target(context.asset, 0)

def analyze(context, perf):
    print(f"Final value: {perf['portfolio_value'].iloc[-1]}")
```

### 18. Pipeline API

```python
from zipline.pipeline import Pipeline
from zipline.pipeline.factors import Returns, AverageDollarVolume
from zipline.pipeline.engine import SimplePipelineEngine

# Pipeline
def make_pipeline():
    return Pipeline(
        columns={
            'returns': Returns(window_length=5),
            'volume': AverageDollarVolume(window_length=20),
        },
        screen=AverageDollarVolume(window_length=20).top(100),
    )
```

## G. pyfolio 评估

### 19. 完整 tear sheet

```python
import pyfolio as pf

returns = pd.Series(strategy_returns, index=returns_index)

# 完整分析
pf.create_full_tear_sheet(returns)

# 单独分析
pf.create_returns_tear_sheet(returns)
pf.create_position_tear_sheet(returns, positions)
pf.create_txn_tear_sheet(returns, transactions)
```

### 20. 自定义统计

```python
def sharpe_ratio(returns, rf=0, periods=252):
    excess = returns - rf
    return np.sqrt(periods) * excess.mean() / excess.std()

def sortino_ratio(returns, rf=0, periods=252):
    excess = returns - rf
    downside = excess[excess < 0].std() * np.sqrt(periods)
    return excess.mean() * periods / downside

def max_drawdown(returns):
    cum = (1 + returns).cumprod()
    peak = cum.cummax()
    dd = (cum - peak) / peak
    return dd.min()

def calmar_ratio(returns, periods=252):
    return (returns.mean() * periods) / abs(max_drawdown(returns))
```

## H. 时间序列

### 21. ARIMA

```python
from statsmodels.tsa.arima.model import ARIMA

model = ARIMA(returns, order=(1, 0, 1))
fit = model.fit()
forecast = fit.forecast(steps=5)
```

### 22. GARCH

```python
from arch import arch_model

model = arch_model(returns, vol='Garch', p=1, q=1)
fit = model.fit(disp='off')
forecast = fit.forecast(horizon=5)
```

### 23. Kalman Filter Pairs Trading

```python
import numpy as np
from pykalman import KalmanFilter

# 价格
prices_a = data['A']
prices_b = data['B']

# Kalman
kf = KalmanFilter(
    transition_matrices=np.array([[1]]),
    observation_matrices=np.array([[1, -1]]),
    initial_state_mean=np.array([0]),
    initial_state_covariance=np.array([[1]]),
    observation_covariance=np.array([[1]]),
    transition_covariance=np.array([[0.0001]]),
)

# 状态估计
state, _ = kf.filter(prices_a.values - prices_b.values)
spread = state[:, 0]

# 信号
signal = pd.Series(0, index=data.index)
signal[spread > spread.mean() + spread.std()] = -1  # 卖出
signal[spread < spread.mean() - spread.std()] = 1   # 买入
```

## I. 贝叶斯

### 24. PyMC3 动态 Sharpe

```python
import pymc3 as pm

with pm.Model() as model:
    # 先验
    mu = pm.Normal('mu', mu=0, sd=0.1)
    sigma = pm.HalfNormal('sigma', sd=0.1)
    theta = pm.Normal('theta', mu=mu, sd=sigma, shape=len(returns))

    # 似然
    obs = pm.Normal('obs', mu=theta, sd=0.01, observed=returns)

    trace = pm.sample(2000)
```

## J. 树模型

### 25. LightGBM 完整

```python
import lightgbm as lgb

# 参数
params = {
    'objective': 'regression',
    'metric': 'rmse',
    'num_leaves': 31,
    'learning_rate': 0.05,
    'feature_fraction': 0.8,
    'bagging_fraction': 0.8,
    'bagging_freq': 5,
    'verbose': -1,
}

# 训练
dtrain = lgb.Dataset(X_train, label=y_train)
dval = lgb.Dataset(X_val, label=y_val, reference=dtrain)

model = lgb.train(
    params, dtrain,
    num_boost_round=2000,
    valid_sets=[dval],
    callbacks=[lgb.early_stopping(50), lgb.log_evaluation(100)],
)

# 预测
pred = model.predict(X_test)
```

### 26. XGBoost 完整

```python
import xgboost as xgb

dtrain = xgb.DMatrix(X_train, label=y_train)
dval = xgb.DMatrix(X_val, label=y_val)

params = {
    'objective': 'reg:squarederror',
    'max_depth': 6,
    'learning_rate': 0.05,
    'subsample': 0.8,
    'colsample_bytree': 0.8,
    'tree_method': 'hist',
    'device': 'cuda',
}

model = xgb.train(
    params, dtrain,
    num_boost_round=2000,
    evals=[(dval, 'val')],
    early_stopping_rounds=50,
    verbose_eval=100,
)

dtest = xgb.DMatrix(X_test)
pred = model.predict(dtest)
```

## K. 文本

### 27. FinBERT 情感

```python
from transformers import pipeline

finbert = pipeline("sentiment", model="ProsusAI/finbert")

text = "Apple stock surges on record iPhone sales"
result = finbert(text)[0]

# 计算分数
score = result['score'] * (1 if result['label'] == 'positive' else -1)
```

### 28. LDA 主题

```python
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import CountVectorizer

vectorizer = CountVectorizer(max_features=5000, stop_words='english')
X = vectorizer.fit_transform(documents)

lda = LatentDirichletAllocation(n_components=10, random_state=42)
doc_topics = lda.fit_transform(X)
```

## L. 深度学习

### 29. Keras MLP

```python
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout, BatchNormalization

model = Sequential([
    Dense(128, activation='relu', input_shape=(X.shape[1],)),
    BatchNormalization(),
    Dropout(0.3),
    Dense(64, activation='relu'),
    BatchNormalization(),
    Dropout(0.3),
    Dense(1),
])
model.compile(optimizer='adam', loss='mse')
model.fit(X_train, y_train, validation_data=(X_val, y_val), epochs=50)
```

### 30. Keras LSTM

```python
from tensorflow.keras.layers import LSTM, Dense, Dropout

model = Sequential([
    LSTM(64, return_sequences=True, input_shape=(window, n_features)),
    Dropout(0.3),
    LSTM(32),
    Dropout(0.3),
    Dense(1),
])
```

## M. 强化学习

### 31. Stable Baselines PPO

```python
from stable_baselines3 import PPO

env = DummyVecEnv([lambda: TradingEnv(prices, features)])

model = PPO('MlpPolicy', env, verbose=1)
model.learn(total_timesteps=100000)

# 评估
obs = env.reset()
while True:
    action, _ = model.predict(obs)
    obs, reward, done, _ = env.step(action)
    if done:
        break
```

## N. 工具函数

### 32. 时序拆分

```python
def temporal_split(X, y, train_size=0.7, val_size=0.15):
    """时序拆分。"""
    n = len(X)
    train_end = int(n * train_size)
    val_end = int(n * (train_size + val_size))

    return (
        X.iloc[:train_end], y.iloc[:train_end],
        X.iloc[train_end:val_end], y.iloc[train_end:val_end],
        X.iloc[val_end:], y.iloc[val_end:],
    )
```

### 33. Walk-Forward 验证

```python
def walk_forward_validation(X, y, model_func, train_period=252*2, test_period=63):
    """滚动前向验证。"""
    predictions = []

    for start in range(0, len(X) - train_period - test_period, test_period):
        train_end = start + train_period
        test_end = train_end + test_period

        X_train = X.iloc[start:train_end]
        y_train = y.iloc[start:train_end]
        X_test = X.iloc[train_end:test_end]

        model = model_func()
        model.fit(X_train, y_train)

        pred = pd.Series(
            model.predict(X_test),
            index=y.iloc[train_end:test_end].index,
        )
        predictions.append(pred)

    return pd.concat(predictions)
```

### 34. 自定义 IC

```python
def information_coefficient(predictions, actuals, by_date=True):
    """计算 IC。"""
    if by_date:
        # 按日期分组
        df = pd.DataFrame({'pred': predictions, 'actual': actuals})
        ic = df.groupby(level='date').apply(
            lambda x: x['pred'].corr(x['actual'])
        )
        return ic.mean(), ic.std()
    else:
        return predictions.corr(actuals)
```

### 35. 换手率

```python
def turnover(weights):
    """换手率。"""
    return weights.diff().abs().sum(axis=1).mean()
```

## O. 实战技巧

### 36. 内存优化

```python
# 用 category
df['sector'] = df['sector'].astype('category')

# 降精度
df['price'] = df['price'].astype('float32')

# 分块读取
for chunk in pd.read_csv('big.csv', chunksize=10000):
    process(chunk)
```

### 37. 并行

```python
import multiprocessing as mp

def process(ticker):
    return compute_factor(ticker)

with mp.Pool(8) as pool:
    results = pool.map(process, tickers)
```

### 38. 进度条

```python
from tqdm import tqdm

results = []
for ticker in tqdm(tickers):
    results.append(compute_factor(ticker))
```

### 39. 缓存

```python
from functools import lru_cache

@lru_cache(maxsize=128)
def get_prices(ticker, start, end):
    return yf.download(ticker, start=start, end=end)
```

### 40. 日志

```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("Processing data")
logger.warning("Data quality issue")
logger.error("Failed")
```

## P. 评估指标

### 41. 完整评估

```python
def full_evaluation(returns, rf=0, periods=252):
    """完整策略评估。"""
    excess = returns - rf

    metrics = {
        'Total Return': (1 + returns).prod() - 1,
        'Annualized Return': returns.mean() * periods,
        'Annualized Vol': returns.std() * np.sqrt(periods),
        'Sharpe Ratio': excess.mean() / excess.std() * np.sqrt(periods),
        'Sortino Ratio': excess.mean() / excess[excess < 0].std() * np.sqrt(periods),
        'Max Drawdown': max_drawdown(returns),
        'Calmar Ratio': (returns.mean() * periods) / abs(max_drawdown(returns)),
        'Skewness': returns.skew(),
        'Kurtosis': returns.kurtosis(),
        'Win Rate': (returns > 0).mean(),
        'Best Day': returns.max(),
        'Worst Day': returns.min(),
        'Best Month': (1 + returns).resample('M').prod().max() - 1,
        'Worst Month': (1 + returns).resample('M').prod().min() - 1,
    }
    return metrics
```

## Q. 可视化

### 42. 因子分布

```python
import matplotlib.pyplot as plt
import seaborn as sns

# 直方图
fig, axes = plt.subplots(1, 3, figsize=(15, 5))

axes[0].hist(factor.dropna(), bins=50)
axes[0].set_title('Factor Distribution')

# IC 时间序列
axes[1].plot(ic_series)
axes[1].axhline(0, color='red', linestyle='--')
axes[1].set_title('IC Time Series')

# Quantile 收益
quantile_returns.plot(kind='bar', ax=axes[2])
axes[2].set_title('Quantile Returns')

plt.tight_layout()
```

### 43. 累计收益

```python
cum_returns = (1 + returns).cumprod()

fig, ax = plt.subplots(figsize=(12, 6))
ax.plot(cum_returns, label='Strategy')
ax.plot((1 + benchmark_returns).cumprod(), label='Benchmark')
ax.legend()
ax.set_title('Cumulative Returns')
```

### 44. 回撤

```python
def plot_drawdown(returns):
    cum = (1 + returns).cumprod()
    peak = cum.cummax()
    dd = (cum - peak) / peak

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.fill_between(dd.index, dd, 0, color='red', alpha=0.3)
    ax.set_title('Drawdown')
    ax.set_ylabel('Drawdown')
```

### 45. 相关性矩阵

```python
import seaborn as sns

fig, ax = plt.subplots(figsize=(10, 8))
sns.heatmap(
    factors.corr(),
    annot=True,
    cmap='RdBu_r',
    center=0,
    ax=ax,
)
ax.set_title('Factor Correlation Matrix')
```

## R. 实用工具

### 46. 日期工具

```python
def trading_days(start, end):
    """交易日。"""
    return pd.bdate_range(start, end)

def next_trading_day(date):
    """下一个交易日。"""
    return pd.bdate_range(date, periods=2)[-1]

def previous_trading_day(date):
    """上一个交易日。"""
    return pd.bdate_range(end=date, periods=2)[0]
```

### 47. 数据对齐

```python
def align_data(*dfs):
    """对齐多个 dataframe 的索引。"""
    common_index = dfs[0].index
    for df in dfs[1:]:
        common_index = common_index.intersection(df.index)

    return [df.loc[common_index] for df in dfs]
```

### 48. 缺失值处理

```python
def handle_missing(df, method='ffill'):
    """处理缺失值。"""
    if method == 'ffill':
        return df.fillna(method='ffill').dropna()
    elif method == 'interpolate':
        return df.interpolate().dropna()
    elif method == 'drop':
        return df.dropna()
```

## S. 部署与生产

### 49. 保存 / 加载模型

```python
import joblib
import pickle

# 保存 sklearn
joblib.dump(model, 'model.pkl')
loaded = joblib.load('model.pkl')

# 保存 Keras
model.save('model.h5')
loaded = tf.keras.models.load_model('model.h5')
```

### 50. 模型监控

```python
class ModelMonitor:
    def __init__(self, model, metric_fn, threshold=0.05):
        self.model = model
        self.metric_fn = metric_fn
        self.threshold = threshold
        self.history = []

    def check(self, X, y):
        pred = self.model.predict(X)
        metric = self.metric_fn(y, pred)
        self.history.append(metric)

        if metric < self.threshold:
            print(f"WARNING: Metric {metric} < {self.threshold}")
            return False
        return True
```

---

希望这些代码片段对你的量化交易之旅有帮助！

记住：所有代码都要**根据实际场景调整**，并经过**严格回测与验证**。

> "First, write the code that does what you think it should do. Then, run the backtest and find out what it does."
>
> — After all the cleverness, the data tells the truth.