# 第 26 章 — MLOps 与治理（3rd Edition）

## 章节目标

- 失败分类
- 漂移检测
- 实验管理
- 治理与合规

## 26.1 MLOps 概念

### 三大核心

- **持续集成（CI）**：代码 + 数据
- **持续训练（CT）**：模型定期重训
- **持续部署（CD）**：自动上线

## 26.2 失败分类

### 1. Pipeline 失败

- 数据缺失
- 任务崩溃

### 3. 性能衰减

- 漂移
- 概念漂移
- 数据漂移

## 26.3 数据漂移检测

### KS 检验

```python
from scipy.stats import ks_2samp
import numpy as np

def detect_drift(reference_data, current_data, threshold=0.05):
    """KS 检验检测漂移。"""
    drift_features = []

    for col in reference_data.columns:
        stat, p = ks_2samp(reference_data[col], current_data[col])
        if p < threshold:
            drift_features.append(col)

    return drift_features

# 用法
reference = pd.read_parquet('train_data.parquet')
current = pd.read_parquet('current_data.parquet')

drift = detect_drift(reference, current)
print(f"Drifted features: {drift}")
```

### Population Stability Index

```python
def psi(reference, current, bins=10):
    """PSI：Population Stability Index。"""
    # 分箱
    breakpoints = np.percentile(reference, np.linspace(0, 100, bins + 1))
    breakpoints = np.unique(breakpoints)

    ref_counts = np.histogram(reference, bins=breakpoints)[0]
    cur_counts = np.histogram(current, bins=breakpoints)[0]

    # 比例
    ref_pct = ref_counts / len(reference)
    cur_pct = cur_counts / len(current)

    # 防止 0
    ref_pct = np.where(ref_pct == 0, 0.0001, ref_pct)
    cur_pct = np.where(cur_pct == 0, 0.0001, cur_pct)

    # PSI
    psi_value = np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct))

    return psi_value

# 解释：< 0.1 无漂移，0.1-0.25 中等，> 0.25 严重
```

## 26.4 概念漂移

```python
from alibi_detect.cd import KSDrift, MMDDrift

# KS 漂移检测器
detector = KSDrift(
    p_val=0.05,
    X_ref=reference.values,
)

# 检测
preds = detector.predict(current.values, return_p_val=True)
if preds['data']['is_drift']:
    print("Drift detected!")
```

## 26.5 模型性能监控

```python
class ModelMonitor:
    """模型监控器。"""
    def __init__(self, model, reference_metrics):
        self.model = model
        self.reference_metrics = reference_metrics

    def check(self, X, y):
        # 当前性能
        pred = self.model.predict(X)
        current_metrics = {
            'mse': mean_squared_error(y, pred),
            'sharpe': compute_sharpe(y, pred),
        }

        # 对比
        for metric_name, ref_value in self.reference_metrics.items():
            cur_value = current_metrics[metric_name]
            decay = (ref_value - cur_value) / ref_value

            if decay > 0.2:  # 衰减 20%
                self.alert(f"{metric_name} decayed {decay:.2%}")

    def alert(self, msg):
        # 发送告警
        send_email(msg)
        send_slack(msg)
```

## 26.6 实验管理

### MLflow

```python
import mlflow

mlflow.set_tracking_uri('http://localhost:5000')
mlflow.set_experiment('ml4t_experiment')

# 开始
with mlflow.start_run():
    # 参数
    mlflow.log_param('learning_rate', 0.01)
    mlflow.log_param('max_depth', 6)

    # 训练
    model = train(...)

    # 指标
    mlflow.log_metric('train_sharpe', train_sharpe)
    mlflow.log_metric('val_sharpe', val_sharpe)

    # 模型
    mlflow.sklearn.log_model(model, 'model')

    # Artifact
    mlflow.log_artifact('feature_importance.png')
```

## 26.7 特征存储

### Feast

```python
# pip install feast
from feast import FeatureStore

# 特征定义
fs = FeatureStore(repo_path='feature_repo')

# 在线获取
features = fs.get_online_features(
    features=[
        'stock_features:momentum_20',
        'stock_features:volatility_20',
    ],
    entity_rows=[{'stock': 'AAPL'}],
).to_dict()

# 离线（训练）
training_df = fs.get_historical_features(
    entity_df=entity_df,
    features=[
        'stock_features:momentum_20',
        'stock_features:volatility_20',
    ],
).to_df()
```

## 26.8 模型注册

### MLflow Registry

```python
# 注册
mlflow.register_model(
    model_uri=f'runs:/{run_id}/model',
    name='trading_model',
)

# 转换到生产
client = mlflow.MlflowClient()
client.transition_model_version_stage(
    name='trading_model',
    version=1,
    stage='Production',
)

# 加载生产模型
model = mlflow.pyfunc.load_model('models:/trading_model/Production')
```

## 26.9 安全部署

```python
"""灰度发布"""
class CanaryDeployment:
    """金丝雀发布。"""
    def __init__(self, prod_model, new_model, traffic_pct=0.1):
        self.prod_model = prod_model
        self.new_model = new_model
        self.traffic_pct = traffic_pct

    def predict(self, X):
        # 10% 流量到新模型
        n = len(X)
        n_new = int(n * self.traffic_pct)

        idx = np.random.choice(n, n_new, replace=False)
        new_idx = np.zeros(n, dtype=bool)
        new_idx[idx] = True

        pred = self.prod_model.predict(X)
        if n_new > 0:
            pred[new_idx] = self.new_model.predict(X[new_idx])

        return pred
```

## 26.10 Kill Switch

```python
"""紧急停止"""
class KillSwitch:
    def __init__(self, max_drawdown=0.20, max_daily_loss=0.05):
        self.max_drawdown = max_drawdown
        self.max_daily_loss = max_daily_loss
        self.peak_equity = None
        self.daily_start_equity = None

    def check(self, equity):
        # 更新峰值
        if self.peak_equity is None or equity > self.peak_equity:
            self.peak_equity = equity

        # 回撤检查
        drawdown = (equity - self.peak_equity) / self.peak_equity
        if drawdown < -self.max_drawdown:
            return True, f"Drawdown {drawdown:.2%}"

        # 日损失检查
        if self.daily_start_equity is None:
            self.daily_start_equity = equity
        daily_change = (equity - self.daily_start_equity) / self.daily_start_equity
        if daily_change < -self.max_daily_loss:
            return True, f"Daily loss {daily_change:.2%}"

        return False, None

    def trigger(self, reason):
        """触发紧急停止。"""
        # 1. 平仓所有头寸
        close_all_positions()

        # 2. 告警
        send_alert(f"KILL SWITCH: {reason}")

        # 3. 暂停系统
        pause_system()
```

## 26.11 实验跟踪最佳实践

```python
# 记录一切
with mlflow.start_run(run_name='experiment_001'):
    # 1. 代码版本
    mlflow.log_param('git_commit', get_git_commit())

    # 2. 数据版本
    mlflow.log_param('data_version', '2024-01-15')

    # 3. 超参数
    mlflow.log_params(hparams)

    # 4. 训练指标
    mlflow.log_metrics(train_metrics)

    # 5. 验证指标
    mlflow.log_metrics(val_metrics)

    # 6. 测试指标
    mlflow.log_metrics(test_metrics)

    # 7. 模型
    mlflow.sklearn.log_model(model, 'model')

    # 8. 图表
    mlflow.log_figure(fig, 'test_sharpe.png')

    # 9. 特征重要度
    mlflow.log_artifact('feature_importance.csv')
```

## 26.12 文档化

### 策略文档

```python
"""策略 term sheet"""
strategy_doc = """
策略名称：动量反转策略
作者：...
日期：2024-01-15

目标：
- 长期 Sharpe > 1.0
- 最大回撤 < 15%

策略：
- 每月初调仓
- 买入过去 12 个月表现最好的 10%
- 卖出过去 12 个月表现最差的 10%

参数：
- 持仓数：100
- 再平衡：每月
- 止损：单股 -10%
- 行业限制：单行业 < 30%

风险：
- 模型依赖历史数据
- 极端市场可能失效

回测：
- 期间：2010-2023
- Sharpe: 1.2
- Max DD: -12%

已知问题：
- 2020 年 3 月失效
- 流动性低时滑点大
"""
```

## 26.13 合规

### 监管要点

- **SEC / FINRA**：证券交易
- **MiFID II**：欧盟
- **数据保护**：GDPR
- **算法责任**：决策日志

### 日志

```python
def log_decision(decision, context):
    """记录所有决策。"""
    log_entry = {
        'timestamp': datetime.now(),
        'decision': decision,
        'context': context,
        'model_version': 'v1.2.3',
        'data_version': '2024-01-15',
    }
    write_to_audit_log(log_entry)
```

## 26.14 完整 MLOps 流水线

```python
"""完整 MLOps 流水线"""
from prefect import flow, task
import mlflow

@task
def ingest_data():
    """数据获取。"""
    data = fetch_raw_data()
    validate(data)
    return data

@task
def compute_features(data):
    """特征工程。"""
    features = engineer_features(data)
    return features

@task
def train_model(features, params):
    """训练。"""
    model = train(features, params)
    metrics = evaluate(model)
    return model, metrics

@task
def register_model(model, metrics, threshold=0.05):
    """注册（如果性能达标）。"""
    if metrics['val_sharpe'] > threshold:
        mlflow.sklearn.log_model(model, 'model')
        return True
    return False

@task
def deploy_to_prod(model_version):
    """部署。"""
    # 灰度发布
    deploy_canary(model_version, traffic_pct=0.1)

    # 监控
    monitor_metrics(model_version, duration='24h')

    # 如果好，全量
    if check_metrics_ok(model_version):
        deploy_full(model_version)

@flow(name='ml4t-pipeline')
def ml4t_pipeline():
    data = ingest_data()
    features = compute_features(data)

    # 多个模型并行
    models = []
    for params in hyperparameters:
        model, metrics = train_model(features, params)
        if register_model(model, metrics):
            models.append((model, metrics))

    # 部署最佳
    if models:
        best = max(models, key=lambda x: x[1]['val_sharpe'])
        deploy_to_prod(best[0])
```

## 26.15 关键 takeaway

- MLOps 让模型持续运行
- 监控 + 漂移检测 + 自动重训
- 实验管理可复现

## 26.16 工具栈

| 类别 | 工具 |
|------|------|
| **实验** | MLflow / W&B / Neptune |
| **Pipeline** | Airflow / Prefect / Dagster |
| **漂移** | alibi-detect / evidently |
| **特征存储** | Feast / Tecton |
| **模型注册** | MLflow / BentoML |
| **监控** | Prometheus / Grafana |
| **告警** | PagerDuty / Slack |

## 26.17 参考

- Treveil et al., 2020 *Introducing MLOps*
- Sculley et al., 2015 *Hidden Technical Debt in Machine Learning Systems*
- Polyzotis et al., 2018 *Data Lifecycle Challenges in Production Machine Learning*