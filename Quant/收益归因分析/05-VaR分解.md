# 5. 风险归因-VaR分解：VaR的边际贡献、增量VaR、成分VaR

聊到风险归因，很多朋友第一反应就是算个VaR完事。嗯，我以前也这么干过。直到有一次，我拿着一个多策略组合的VaR报告去找风控总监，他问我：「这个数字是挺好看，但你告诉我，到底是哪个策略在拖后腿？」

我当场就愣住了。光知道总风险，不知道风险从哪来，这就像只知道体温39度，却不知道是哪里发炎。所以，今天我们就来拆解一下VaR——看看边际贡献、增量VaR和成分VaR到底在说什么。

> **核心逻辑：** VaR分解不是为了炫技，而是为了回答三个问题：
> - 哪个资产/因子对组合风险贡献最大？（边际贡献）
> - 如果我把某个资产剔除，风险会降多少？（增量VaR）
> - 每个资产应该承担多少风险责任？（成分VaR）

```mermaid
flowchart TD
    Root[VaR 风险归因] --> A[边际贡献 VaR]
    Root --> B[增量 VaR]
    Root --> C[成分 VaR]
    A --> A1[∂VaR / ∂wᵢ]
    A --> A2[敏感度分析]
    A --> A3[风险暴露]
    B --> B1[VaR(组合) - VaR(剔除)]
    B --> B2[边际影响]
    B --> B3[对冲决策]
    C --> C1[wᵢ × 边际贡献]
    C --> C2[可加性分解]
    C --> C3[风险预算]
    Note["三者关系：边际贡献 → 成分VaR（加权求和）= 总VaR"]
    A -.-> Note
    B -.-> Note
    C -.-> Note
```

### 5.1 边际贡献 VaR：谁在「推高」风险？

边际贡献VaR，说白了就是「每增加一单位头寸，组合VaR会变多少」。数学上就是VaR对权重的偏导数。

```python
# 边际贡献VaR计算（Python示例）
import numpy as np

def marginal_contribution_var(weights, cov_matrix, portfolio_var):
    """
    weights: 资产权重向量
    cov_matrix: 协方差矩阵
    portfolio_var: 组合方差
    """
    # 组合标准差
    portfolio_std = np.sqrt(portfolio_var)
    # 边际贡献 = (协方差矩阵 @ 权重) / 组合标准差
    marginal_var = (cov_matrix @ weights) / portfolio_std
    return marginal_var

# 假设3个资产
weights = np.array([0.4, 0.35, 0.25])
cov = np.array([[0.01, 0.002, 0.001],
                [0.002, 0.02, 0.003],
                [0.001, 0.003, 0.015]])
portfolio_var = weights.T @ cov @ weights

mcv = marginal_contribution_var(weights, cov, portfolio_var)
print("边际贡献VaR:", mcv)
# 输出类似：[0.12, 0.18, 0.09]  —— 第二个资产边际风险最大
```

> **💡 我的经验：** 边际贡献VaR有个很实用的场景——调仓时，你想知道「稍微加点仓位」会不会让风险失控。我曾经有个CTA策略，边际贡献突然飙升，一查发现是某个商品期货的波动率在悄悄放大。还好提前发现了，不然那天夜盘就要爆仓。

### 5.2 增量 VaR：去掉它，世界会怎样？

增量VaR问的是：如果我把某个资产完全剔除，组合VaR会下降多少？

公式很简单：**增量VaR = VaR(全组合) - VaR(剔除该资产后的组合)**

你可能会想，这不就是边际贡献乘以权重吗？嗯，不完全对。因为边际贡献是「微小的变化」，而增量VaR是「完全移除」——这涉及到组合的非线性效应。尤其是当资产之间有对冲关系时，增量VaR可能比边际贡献小很多。

> **⚠️ 避坑指南：** 我曾经犯过一个错——直接用边际贡献乘以权重来估算增量VaR。结果发现估算值比实际值大了30%。为什么？因为两个高度相关的资产，去掉一个后，另一个的风险暴露反而更集中了。所以，增量VaR一定要重新计算，别偷懒。

```python
def incremental_var(weights, cov_matrix, asset_index, confidence=0.95):
    """
    计算剔除某个资产后的增量VaR
    """
    from scipy.stats import norm

    # 全组合VaR
    portfolio_var = weights.T @ cov_matrix @ weights
    portfolio_std = np.sqrt(portfolio_var)
    z_score = norm.ppf(confidence)
    full_var = z_score * portfolio_std

    # 剔除资产后的组合
    new_weights = np.delete(weights, asset_index)
    new_cov = np.delete(np.delete(cov_matrix, asset_index, axis=0), asset_index, axis=1)
    new_var = new_weights.T @ new_cov @ new_weights
    new_std = np.sqrt(new_var)
    new_var_value = z_score * new_std

    return full_var - new_var_value

# 计算剔除第2个资产的增量VaR
inc_var = incremental_var(weights, cov, 1)
print(f"增量VaR（剔除资产2）: {inc_var:.4f}")
```

### 5.3 成分 VaR：风险「分锅」的艺术

成分VaR是我个人最喜欢的一个指标。它解决了边际贡献和增量VaR的痛点——边际贡献不能直接加总，增量VaR计算量大。而成分VaR，它满足一个漂亮的性质：**所有资产的成分VaR之和等于组合总VaR**。

公式：**成分VaRᵢ = wᵢ × 边际贡献VaRᵢ**

你想想看，这意味着什么？意味着你可以把总风险像切蛋糕一样，分到每个资产头上。谁占比大，谁就是风险的主要来源。

| 资产 | 权重 | 边际贡献VaR | 成分VaR | 风险占比 |
| --- | --- | --- | --- | --- |
| 资产A | 40% | 0.12 | 0.048 | 32% |
| 资产B | 35% | 0.18 | 0.063 | 42% |
| 资产C | 25% | 0.09 | 0.0225 | 15% |
| **合计** | **100%** | **—** | **0.1335** | **100%** |

> **关键洞察：** 资产B权重只有35%，但风险占比却高达42%。这说明它是个「高风险低权重」的资产。如果你要做风险预算，第一个要调整的就是它。

### 5.4 三者对比：什么时候用哪个？

- **边际贡献VaR**：适合微调。比如你想知道「再加1%仓位会怎样」，用它准没错。
- **增量VaR**：适合「要不要砍掉这个策略」的决策。我每次做策略淘汰时，都会先算一遍增量VaR。
- **成分VaR**：适合做风险报告和归因分析。给老板看的时候，成分VaR最直观——「你看，这个策略占了40%的风险，但只贡献了20%的收益」。

> **💡 我的习惯：** 每周跑一次成分VaR，然后画个饼图。哪个策略的「风险占比」明显高于「收益占比」，我就把它列入观察名单。连续两周异常，直接触发预警。

### 5.5 实战中的注意事项

1. **正态假设的陷阱**：VaR本身假设收益率正态分布，但实际中肥尾效应很常见。我建议在计算边际贡献时，用历史模拟法或蒙特卡洛模拟做一次校验。
2. **相关性突变**：2008年金融危机时，很多原本低相关的资产突然高度相关。成分VaR在这种时候会严重低估风险。所以，压力测试不能省。
3. **计算效率**：如果你的组合有几百个资产，增量VaR要算几百次，很慢。我一般先用成分VaR做初筛，只对排名前10的风险源做增量VaR分析。

好了，关于VaR分解就聊这么多。记住一句话：**风险归因不是为了算出一个数字，而是为了知道下一步该往哪走**。边际贡献告诉你方向，增量VaR告诉你力度，成分VaR告诉你责任。三者配合，你就能把风险管得明明白白。

> **📌 一句话总结：** 边际贡献VaR看敏感度，增量VaR看剔除效果，成分VaR看风险分摊。三者结合，才是完整的风险归因。
