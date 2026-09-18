# 06. K 近邻 (K-Nearest Neighbors, KNN)

KNN 是最简单但仍然有效的"学习"算法：找到训练集中与测试样本**最近的 K 个样本**，用它们的标签投票或平均预测。

KNN 是**惰性学习 (lazy learning)**：训练时不学任何东西，推理时才算。

## 6.1 基本思想

### 算法 (KNN 分类)

```
给定测试点 x_test:
1. 计算 x_test 与所有训练样本的距离 d(x_test, x_i)
3. 找出最近的 K 个样本 (x_(1), ..., x_(K))
4. 投票: y_pred = argmax_c Σ I(y_(i) = c)
```

### 算法 (KNN 回归)

```
y_pred = (1/K) Σ y_(i)   (平均)
```

或加权：

$$
y_{\text{pred}} = \frac{\sum_{i=1}^{K} w_i y_{(i)}}{\sum_{i=1}^{K} w_i}
$$

$w_i = 1/d_i$ 等加权方式。

## 6.2 距离度量

### 欧氏距离 (L2)

$$
d(x, y) = \sqrt{\sum_{j=1}^d (x_j - y_j)^2}
$$

最常用，对尺度敏感（需标准化）。

### 曼哈顿距离 (L1)

$$
d(x, y) = \sum_{j=1}^d |x_j - y_j|
$$

维度灾难下比 L2 更稳。

### 切比雪夫距离 (L∞)

$$
d(x, y) = \max_j |x_j - y_j|
$$

### 闵可夫斯基距离 (Lp)

$$
d_p(x, y) = \left(\sum_j |x_j - y_j|^p\right)^{1/p}
$$

$p = 1$ → L1；$p = 2$ → L2；$p \to \infty$ → L∞。

### 余弦相似度

$$
\text{sim}(x, y) = \frac{x^T y}{\|x\| \|y\|}
$$

转成距离：$d = 1 - \text{sim}$。

适合文本、词向量等关心方向而非幅度的场景。

### 汉明距离

类别/二进制特征：

$$
d(x, y) = \sum_j \mathbb{1}[x_j \neq y_j]
$$

### 马氏距离

考虑特征相关性和方差：

$$
d_M(x, y) = \sqrt{(x - y)^T \Sigma^{-1} (x - y)}
$$

$\Sigma$ 是协方差矩阵。

### 自定义距离

```python
def my_distance(x1, x2):
    return np.sqrt(np.sum((x1 - x2)**2))

model = KNeighborsClassifier(metric=my_distance)
```

## 6.3 K 值的选择

### Bias-Variance 权衡

| K | Bias | Variance | 表现 |
|---|------|----------|------|
| K=1 | 低 | 高 | 锯齿状边界、过拟合 |
| K=N | 高 | 低 | 全预测为多数类、欠拟合 |
| K 适中 | 中 | 中 | 平滑、泛化好 |

### 经验值

- 分类：$K = \sqrt{N}$ 或交叉验证
- 回归：$K = N^{0.4} \sim N^{0.5}$
- 二分类 K 用**奇数**，避免平局

```python
from sklearn.model_selection import GridSearchCV

params = {'n_neighbors': [1, 3, 5, 7, 11, 15, 21]}
grid = GridSearchCV(KNeighborsClassifier(), params, cv=5)
grid.fit(X_train, y_train)
print(f"Best K = {grid.best_params_['n_neighbors']}")
```

## 6.4 决策边界示例

```
        + +          + +        + + + +
       +   +        +   +      +       +
      +  ●  +  K=1  + ●  + K=3  +   ●   +
       +   +        +   +      +       +
        + +          + +        + + + +

  K=1: 边界复杂       K=3: 平滑       K=大: 过于平滑
  → 过拟合           → 泛化好         → 欠拟合
```

## 6.5 数据结构加速

### 朴素方法

- 复杂度 $\mathcal{O}(Nd)$ 每查询
- $N$ 大时不可用

### KD-Tree

构造二叉树，每次查询 $\mathcal{O}(\log N)$。

适用：低维 ($d < 20$)。高维退化为朴素。

```python
model = KNeighborsClassifier(algorithm='kd_tree', n_neighbors=5)
```

### Ball Tree

用超球面而非超平面分割，更适合高维。

```python
model = KNeighborsClassifier(algorithm='ball_tree')
```

### Annoy / Faiss (近似)

百万级数据用近似最近邻 (ANN)：

- Annoy (Spotify)
- Faiss (Facebook)
- HNSW (hnswlib)
- ScaNN (Google)

### 大数据 KNN 限制

KNN 推理慢、内存大：

- $N = 1M$, $d = 100$ → 1M × 100 × 8 bytes = 800MB
- 推理一次 = 1M × 100 次距离计算

→ 工业界常先用 embedding + 向量检索代替。

## 6.6 代码

### 基本用法

```python
from sklearn.neighbors import KNeighborsClassifier

model = KNeighborsClassifier(
    n_neighbors=5,
    weights='uniform',  # 或 'distance'
    metric='minkowski', p=2,  # 欧氏距离
    algorithm='auto',
    n_jobs=-1,
)
model.fit(X_train, y_train)
y_pred = model.predict(X_test)
y_proba = model.predict_proba(X_test)
```

### 加权 KNN

距离近的样本影响力更大：

```python
model = KNeighborsClassifier(weights='distance')

# 自定义权重函数
def weight(d):
    return np.exp(-d**2 / (2 * 1.0**2))  # 高斯核

model = KNeighborsClassifier(weights=weight)
```

### KNN 回归

```python
from sklearn.neighbors import KNeighborsRegressor

model = KNeighborsRegressor(n_neighbors=5, weights='distance')
model.fit(X_train, y_train)
y_pred = model.predict(X_test)
```

### 距离矩阵查询

```python
from sklearn.neighbors import NearestNeighbors

nn = NearestNeighbors(n_neighbors=5)
nn.fit(X_train)

# 找每个 test 的 K 近邻
dist, idx = nn.kneighbors(X_test)
print(f"距离矩阵: {dist.shape}")  # (n_test, 5)
print(f"邻居索引: {idx.shape}")   # (n_test, 5)
```

### 半径查询

```python
nn = NearestNeighbors(radius=0.5)
nn.fit(X_train)

# 找半径 0.5 内所有邻居
dist, idx = nn.radius_neighbors(X_test)
```

## 6.7 维度灾难

KNN 在高维下表现糟糕：

- 距离度量集中在相似范围（所有点对的距离接近）
- 最近邻和最远邻的区分度下降
- 需要**指数级**数据才能保持低维性能

直觉：$d$ 维超球体 vs 体积随 $d$ 指数衰减。

```python
# 高维数据务必先降维
from sklearn.pipeline import Pipeline
from sklearn.decomposition import PCA

pipe = Pipeline([
    ('pca', PCA(n_components=20)),
    ('knn', KNeighborsClassifier(n_neighbors=5)),
])
```

## 6.8 数据预处理

### 标准化 (必备)

```python
from sklearn.preprocessing import StandardScaler

scaler = StandardScaler()
X_train = scaler.fit_transform(X_train)
X_test = scaler.transform(X_test)
```

距离对尺度敏感，**必须缩放**。

### 编码

```python
from sklearn.preprocessing import OneHotEncoder

# 类别特征：OneHot
# 数值特征：StandardScaler / MinMaxScaler
```

## 6.9 应用场景

### 适合

- 小数据集 (< 10K)
- 低维 (d < 20)
- 数据集没有清晰分布假设
- 需要非线性决策边界
- 推荐系统 (基于用户相似度的协同过滤)
- 异常检测 (见 10)

### 不适合

- 大数据集 (推理慢)
- 高维数据 (维度灾难)
- 特征尺度差异大
- 实时推理要求高

## 6.10 与其他算法对比

| 维度 | KNN | LR | DT | RF | SVM |
|------|-----|-----|----|-----|-----|
| 训练 | 0 | 快 | 快 | 中 | 慢 |
| 推理 | **慢** | 快 | 快 | 中 | 中 |
| 内存 | **大** | 小 | 小 | 中 | 小 |
| 解释性 | 中 | **强** | **强** | 中 | 中 |
| 维度缩放 | 要 | 要 | 不要 | 不要 | 要 |
| 类别特征 | 不要 | 不要 | ✅ | ✅ | 不要 |
| 缺失值 | ❌ | ❌ | ❌ | ✅ | ❌ |

## 6.11 变体

### 加权 KNN

距离加权投票 / 平均。

### 局部加权回归 (LOESS/LOWESS)

KNN + 局部多项式回归，平滑数据。

### Condensed KNN

保留边界点，去除冗余样本 → 加速推理。

### 编辑 KNN (ENN)

去除与邻居类别不一致的样本 → 抗噪。

## 6.12 实践技巧

1. **总是先缩放**：StandardScaler 必备
2. **K 选奇数**（二分类）：避免平局
3. **交叉验证选 K**：避免过/欠拟合
4. **试试加权**：通常 `weights='distance'` 比 `'uniform'` 好
5. **高维先降维**：PCA / UMAP → KNN
6. **大数据用向量检索**：FAISS / Milvus / Pinecone

## 6.13 参考

- Cover & Hart, 1967 *Nearest Neighbor Pattern Classification*
- Bishop, 2006 *PRML* Ch. 2.5
- Hastie et al., 2009 *ESL* Ch. 13