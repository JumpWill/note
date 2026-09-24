# 参考资源

> 本文汇总 ML4T 项目相关的论文、书籍、课程、博客、数据源、库等资源，便于深入研究与参考。

## A. 核心项目

### 项目本身

- **GitHub**: https://github.com/stefan-jansen/machine-learning-for-trading
- **第二版 (2020)**: 24 章
- **第三版 (2024)**: 27 章
- **书籍**: Stefan Jansen, "Machine Learning for Algorithmic Trading", Packt Publishing

### 配套仓库

- **第二版代码**: https://github.com/PacktPublishing/Machine-Learning-for-Algorithmic-Trading-Second-Edition
- **第三版代码**: https://github.com/PacktPublishing/Machine-Learning-for-Algorithmic-Trading-Third-Edition

## B. 关键书籍

### 1. ML4T 必读

- Stefan Jansen (2020) *Machine Learning for Algorithmic Trading* (2nd ed)
- Stefan Jansen (2024) *Machine Learning for Algorithmic Trading* (3rd ed)
- Marcos López de Prado (2018) *Advances in Financial Machine Learning*
- Ernie Chan (2017) *Machine Trading: Deploying Computer Algorithms to Conquer the Markets*
- Yves Hilpisch (2021) *Python for Algorithmic Trading* (O'Reilly)
- Matthew F. Dixon (2020) *Machine Learning in Finance: From Theory to Practice*

### 2. 量化基础

- Ernest Chan (2013) *Quantitative Trading: My First Book*
- Ernest Chan (2011) *Algorithmic Trading: Winning Strategies and Their Rationale*
- Robert Carver (2015) *Systematic Trading*
- Euan Sinclair (2010) *Positional Option Trading*
- Andrew Pole (2007) *Statistical Arbitrage*
- Frank Fabozzi (2008) *Quantitative Equity Investing*

### 3. 资产定价

- John Cochrane (2009) *Asset Pricing (Revised Edition)*
- Eugene Fama & Kenneth French (1993) *Common Risk Factors in the Returns on Stocks and Bonds*
- John Campbell, Andrew Lo, Craig MacKinlay (1997) *The Econometrics of Financial Markets*
- Andrew Lo (2017) *Adaptive Markets*

### 4. 投资组合

- Harry Markowitz (1959) *Portfolio Selection*
- Richard Michaud (1989) *The Markowitz Optimization Enigma*
- Marcos López de Prado (2016) *Building Diversified Portfolios that Outperform Out-of-Sample*

### 5. 时间序列

- James Hamilton (1994) *Time Series Analysis*
- Ruey Tsay (2010) *Analysis of Financial Time Series*
- Francis Diebold (2006) *Elements of Forecasting*

### 6. 强化学习

- Sutton & Barto (2018) *Reinforcement Learning: An Introduction*
- Maxim Lapan (2018) *Deep Reinforcement Learning Hands-On*

### 7. 深度学习

- Ian Goodfellow, Yoshua Bengio, Aaron Courville (2016) *Deep Learning*
- François Chollet (2021) *Deep Learning with Python* (2nd ed)
- Aston Zhang, Zachary C. Lipton, Mu Li, Alex J. Smola (2020) *Dive into Deep Learning*

### 8. NLP

- Dan Jurafsky, James H. Martin (2023) *Speech and Language Processing*
- Jacob Eisenstein (2018) *Natural Language Processing*

## C. 关键论文

### 1. 经典因子

- Fama, E. & French, K. (1993). *Common Risk Factors in the Returns on Stocks and Bonds*. Journal of Financial Economics.
- Carhart, M. (1997). *On Persistence in Mutual Fund Performance*. Journal of Finance.
- Novy-Marx, R. (2013). *The Other Side of Value: The Gross Profitability Premium*. Journal of Financial Economics.
- Hou, K., Xue, C., & Zhang, L. (2015). *Digesting Anomalies: An Investment Approach*. Review of Financial Studies.
- Stambaugh, R. & Yuan, Y. (2017). *Mispricing Factors*. Review of Financial Studies.

### 2. ML 在资产定价

- Gu, S., Kelly, B., & Xiu, D. (2020). *Empirical Asset Pricing via Machine Learning*. Review of Financial Studies. ⭐
- Chen, L., Pelger, M., & Zhu, J. (2024). *Deep Learning in Asset Pricing*. Management Science.
- Feng, G., Giglio, S., & Xiu, D. (2020). *Taming the Factor Zoo*. Journal of Finance.
- Kelly, B., Pruitt, S., & Su, Y. (2019). *Characteristics Are Covariances: A Unified Model of Risk and Return*. Journal of Financial Economics.

### 4. NLP 情感

- Loughran, T. & McDonald, B. (2011). *When Is a Liability Not a Liability? Textual Analysis, Dictionaries, and 10-Ks*. Journal of Finance.
- Hutto, C. & Gilbert, E. (2014). *VADER: A Parsimonious Rule-Based Model for Sentiment Analysis of Social Media Text*.
- Araci, D. (2019). *FinBERT: Financial Sentiment Analysis with Pre-trained Language Models*.
- Houlsby, N. & Hu, A. (2022). *A Survey on Transfer Learning for NLP*. IEEE Transactions on Neural Networks.

### 5. 文本因子

- Heston, S. & Sinha, N. (2017). *News vs. Sentiment: Predicting Stock Returns from News Stories*. Journal of Finance.
- Tetlock, P. (2007). *Giving Content to Investor Sentiment: The Role of Media in the Stock Market*. Journal of Finance.
- García, D. (2013). *Sentiment during Recessions*. Journal of Finance.

### 6. 强化学习交易

- Deng, Y., Bao, F., Kong, Y., Ren, Z., & Dai, Q. (2017). *Deep Direct Reinforcement Learning for Financial Signal Representation and Trading*. IEEE Transactions on Signal Processing.
- Théate, T. & Ernst, D. (2021). *Trading Algorithm Based on Deep Reinforcement Learning*. Quantitative Finance.
- Fischer, T. & Krauss, C. (2018). *Deep Learning with Long Short-Term Memory Networks for Financial Market Predictions*. European Journal of Operational Research.
- Jiang, Z., Xu, D., & Liang, J. (2017). *A Deep Reinforcement Learning Framework for the Financial Portfolio Management Problem*. arXiv.

### 7. GAN / VAE

- Yoon, J., Jarrett, D., & van der Schaar, M. (2019). *TimeGAN: Time-Series Generative Adversarial Networks*. NeurIPS.
- Zhou, X., Pan, Z., Hu, G., Tang, S., & Zhao, C. (2018). *Stock Market Prediction on Complementary Feature Self-Attentive LSTMs and Temporal Convolutional Networks*. Neurocomputing.
- Goodfellow, I. et al. (2014). *Generative Adversarial Networks*. NeurIPS.
- Kingma, D. & Welling, M. (2013). *Auto-Encoding Variational Bayes*. ICLR.

### 8. CNN for time series

- Bai, S., Kolter, J., & Koltun, V. (2018). *An Empirical Evaluation of Generic Convolutional and Recurrent Networks for Sequence Modeling*. arXiv.
- Borovykh, A., Bohte, S., & Oosterlee, C. (2017). *Conditional Time Series Forecasting with Convolutional Neural Networks*. arXiv.
- Oord, A. et al. (2016). *WaveNet: A Generative Model for Raw Audio*. arXiv.

### 9. Transformer

- Vaswani, A. et al. (2017). *Attention Is All You Need*. NeurIPS.
- Devlin, J., Chang, M., Lee, K., & Toutanova, K. (2019). *BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding*. NAACL.

### 10. 因果推断

- Pearl, J. (2009). *Causality*. Cambridge University Press.
- Imbens, G. & Rubin, D. (2015). *Causal Inference for Statistics, Social, and Biomedical Sciences*. Cambridge.
- Chernozhukov, V. et al. (2018). *Double/debiased machine learning for treatment and structural parameters*. Econometrics Journal.

### 11. 另类数据

- Cong, L., Gao, H., Ponticelli, J., & Yang, X. (2019). *Credit Allocation Under Economic Stimulus*. SSRN.
- Bryzgal, A. (2017). *Alternative Data in Investment Management*.
- Li, K. & Zhao, X. (2020). *The Use of Satellite Images in Asset Pricing*.

## D. 课程与教学

### 在线课程

- Coursera: Machine Learning Specialization (Andrew Ng)
- Coursera: Deep Learning Specialization (Andrew Ng)
- Coursera: Financial Engineering (Hee-Kwon Moon)
- Coursera: Investment Management (University of Geneva)
- Udacity: AI for Trading (Quantopian)
- edX: MIT 18.S096 Topics in Mathematics with Applications in Finance
- edX: Columbia University Financial Engineering
- Stanford CS231N / CS224N

### 教程

- QuantConnect Lean Documentation
- Zipline Documentation
- Backtrader Documentation
- PyFolio Documentation
- TensorFlow Documentation
- PyTorch Tutorials
- HuggingFace Course

### YouTube

- Sentdex (Python + Quant)
- QuantPy
- StatQuest (ML 概念)
- 3Blue1Brown (数学直觉)
- DeepMind (RL)

## E. 关键博客与网站

### 数据科学 / ML

- **Distill.pub**: 深度学习可视化
- **Towards Data Science**: ML 教程
- **Medium**: ML 博客
- **arXiv Sanity Preserver**: 论文推荐
- **Papers with Code**: 论文 + 代码
- **Reddit r/MachineLearning**、**r/algotrading**、**r/quant**

### 量化

- **QuantConnect**: 算法交易平台
- **Quantpedia**: 量化策略百科
- **Alpha Architect**: 学术策略
- **Quant Start**: 量化教程
- **Quantocracy**: 量化博客聚合
- **Robot Wealth**: 量化研究
- **Ernie Chan's Blog**: 量化经典

### 学术 / 金融

- **SSRN**: 金融论文预印本
- **NBER**: 经济论文
- **Federal Reserve Research**: 央行研究
- **Bank of England Research**
- **BIS Working Papers**

## F. 数据源

### 价格数据

| 来源 | 范围 | 频率 | 费用 |
|------|------|------|------|
| **Yahoo Finance** | 全球股票 | 日 | 免费 |
| **Alpha Vantage** | 全球股票 | 日-分 | 免费额度 |
| **Polygon.io** | 美国 | 分-tick | 收费 |
| **Tiingo** | 全球 | 日-分 | 免费额度 |
| **IEX Cloud** | 美国 | 日-分 | 收费 |
| **Quandl** | 多家 | 多 | 部分收费 |
| **Bloomberg** | 全球 | 全 | 贵 |
| **Refinitiv** | 全球 | 全 | 贵 |

### 基本面

| 来源 | 数据 |
|------|------|
| **SEC EDGAR** | 财报、文件 |
| **Compustat** | 财务数据 |
| **IBES** | 分析师预测 |
| **FactSet** | 综合 |
| **WRDS** | 学术数据 |

### 另类数据

| 来源 | 数据 |
|------|------|
| **Quandl** | 多 |
| **RavenPack** | 新闻情绪 |
| **Social Market Analytics** | 社交媒体 |
| **Preqin** | 私募 |
| **Eagle Alpha** | 卫星 / 网络 |
| **Quandl Nasdaq Data Link** | 多 |

### 链上数据

- **Glassnode**: 加密链上
- **Coin Metrics**: 加密
- **The Graph**: 区块链数据
- **Dune Analytics**: 链上 SQL
- **Nansen**: 智能资金流

### 加密交易所

- **Binance API**
- **Coinbase Pro API**
- **Kraken API**
- **FTX (已关闭)**
- **OKX API**

## G. 关键库

### 数据获取

```python
yfinance              # Yahoo Finance
pandas-datareader     # 多数据源
quandl                # Quandl
alpha_vantage         # Alpha Vantage
polygon               # Polygon
tiingo                # Tiingo
```

### 数据存储

```python
parquet          # 列存储
h5py / pytables # HDF5
feather          # 快速 IO
duckdb           # 嵌入式 SQL
```

### 因子

```python
TA-Lib           # 技术指标
ta               # 替代 TA-Lib
finta             # 金融指标
alphalens        # 因子分析
factor-attribution # 因子归因
```

### 回测

```python
zipline-reloaded  # Quantopian 续作
backtrader        # 经典
vectorbt          # 矢量化
bt                # 灵活
lean              # QuantConnect 开源版
pythalesians      # 通用
```

### 评估

```python
pyfolio-reloaded  # 风险评估
empyrical         # 量化指标
quantstats        # tear sheet
riskfolio-lib     # 组合优化
```

### ML

```python
scikit-learn      # 基础 ML
xgboost           # XGBoost
lightgbm          # LightGBM
catboost          # CatBoost
optuna            # 超参
hyperopt          # 超参
```

### 时间序列

```python
statsmodels       # 时间序列
arch              # GARCH
pmdarima          # auto-ARIMA
prophet           # 时序预测
neuralforecast    # 深度时序
```

### 深度学习

```python
tensorflow        # TF / Keras
pytorch           # PyTorch
transformers      # HuggingFace
pytorch-lightning # PyTorch 包装
```

### NLP

```python
nltk              # NLP 工具
spacy             # 工业级 NLP
gensim            # 主题 / 嵌入
transformers      # BERT 等
sentence-transformers # Sentence-BERT
bertopic          # 主题
top2vec           # 主题
```

### RL

```python
stable-baselines3 # RL 算法
ray               # RLlib
gym / gymnasium   # 环境
```

### 组合优化

```python
riskfolio-lib     # 组合
PyPortfolioOpt    # 组合
empyrical         # 风险
```

### 可视化

```python
matplotlib        # 基础
seaborn           # 统计
plotly            # 交互
bokeh             # 交互
mplfinance        # K 线
```

### 实验管理

```python
mlflow            # 实验管理
wandb             # 实验管理
tensorboard      # 实验管理
dvc               # 数据版本
```

## H. 关键期刊 / 会议

### 金融

- Journal of Finance
- Review of Financial Studies
- Journal of Financial Economics
- Journal of Financial and Quantitative Analysis
- Review of Finance
- Financial Analysts Journal
- Quantitative Finance

### ML

- NeurIPS
- ICML
- ICLR
- AAAI
- KDD

### 经济

- American Economic Review
- Journal of Econometrics
- Review of Economic Studies
- Quantitative Economics

### 交叉

- Journal of Financial Data Science
- Journal of Financial Econometrics
- IEEE Transactions on Signal Processing
- Expert Systems with Applications

## I. 社交 / 社区

### Reddit

- r/algotrading
- r/quant
- r/MachineLearning
- r/datascience
- r/Python
- r/MLQuestions

### 论坛

- QuantConnect 论坛
- Elite Trader
- Traderji
- NuclearPhynance (历史)

### Twitter

- 关注 ML + 量化研究者
- Stefan Jansen
- Marcos López de Prado
- Ernie Chan
- Andrew Ng
- Yann LeCun

### Discord / Slack

- QuantConnect
- HuggingFace
- 各 ML 库 Discord

## J. 实战项目仓库

### 学习用

- **ML4T 项目**: https://github.com/stefan-jansen/machine-learning-for-trading
- **QuantConnect Lean**: https://github.com/QuantConnect/Lean
- **Zipline**: https://github.com/zipline-reloaded/zipline-reloaded
- **Backtrader**: https://github.com/mementum/backtrader
- **HFTFramework**: https://github.com/HFTFramework

### 工具

- **statsforecast**: https://github.com/Nixtla/statsforecast
- **neuralforecast**: https://github.com/Nixtla/neuralforecast
- **mlforecast**: https://github.com/Nixtla/mlforecast
- **riskfolio-lib**: https://github.com/dcajasn/riskfolio-lib

### 论文 + 代码

- **Papers with Code**: https://paperswithcode.com/

## K. 面试 / 求职

### 准备

- 概率统计
- 编程（Python、C++）
- 算法
- 金融基础

### 资源

- **QuantStart**: 入门
- **Quant Trading Interview Questions (GitHub)**
- **Jane Street puzzles**
- **SIG Trading Competition**

### 公司

- Jane Street
- Citadel / Citadel Securities
- Two Sigma
- DE Shaw
- Renaissance Technologies
- Man AHL
- AQR Capital
- WorldQuant
- Jump Trading

## L. 合规 / 道德

### 注意事项

- **数据许可**: 遵守 ToS
- **内幕交易**: 严禁
- **市场操纵**: 严禁
- **回测 ≠ 实盘**: 差异
- **风险管理**: 头寸控制

### 合规资源

- FINRA
- SEC
- MiFID II
- 各交易所规则

## M. 总结

### 学习路径

```
基础（Python / pandas / ML）
   ↓
量化基础（资产定价 / 组合）
   ↓
ML4T（数据 → 因子 → 模型 → 策略）
   ↓
前沿（DL / NLP / RL）
   ↓
实战（自营 / 公司 / 研究）
```

### 关键资源

1. **ML4T 项目本身** - 完整教程
2. **López de Prado 的书** - 量化 ML 圣经
3. **arXiv q-fin** - 前沿论文
4. **QuantConnect** - 实战平台
5. **GitHub** - 找代码

### 持续学习

- 跟踪论文
- 实践项目
- 跟社区
- 写博客分享

> "The goal is not to predict the future. The goal is to be right when others are wrong."

祝学习愉快、交易顺利！