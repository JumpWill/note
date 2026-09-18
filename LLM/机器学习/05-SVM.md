# 05. 支持向量机 (SVM)

支持向量机 (Support Vector Machine, SVM) 是 1990s 发展起来的分类算法，核心思想是在特征空间中找**最大化间隔**的超平面。

## 5.1 基本思想

### 线性可分

二维空间里，两类样本能被一条直线分开：

```
   +             +         |
  + +   o       + +    o   |     +
   +   o o      +    o o   |  o  +
    +   o        +   o     | o o
  ──────────────────────   ──────────
  无数条可分       只有 1 条使间隔最大 (粗线)
```

最优超平面使两类的**间隔 (margin)** 最大化。

### 关键直觉

- **支持向量 (Support Vector)**：离超平面最近的样本点
- **间隔 = 2 / ||w||**（超平面到两侧支持向量的距离）
- 最大化间隔 → 等价于最小化 ||w||²
- 仅支持向量决定超平面 → 稀疏、解高效

## 5.2 线性 SVM (硬间隔)

### 优化问题

$$
\min_{w, b} \frac{1}{2}\|w\|^2
$$

约束：

$$
y_i(w^T x_i + b) \geq 1, \quad \forall i = 1, \ldots, N
$$

### 几何解释

$$
\text{超平面} = \{x \mid w^T x + b = 0\}
$$

- 正类支持向量在 $w^T x + b = +1$
- 负类支持向量在 $w^T x + b = -1$
- 间隔 = $\frac{2}{\|w\|}$

### 求解 (Lagrange 对偶)

构造 Lagrange 函数：

$$
L(w, b, \alpha) = \frac{1}{2}\|w\|^2 - \sum_{i=1}^N \alpha_i[y_i(w^T x_i + b) - 1]
$$

KKT 条件：

$$
\alpha_i \geq 0, \quad \alpha_i [y_i(w^T x_i + b) - 1] = 0
$$

对偶问题：

$$
\max_{\alpha} \sum_{i=1}^N \alpha_i - \frac{1}{2}\sum_{i,j}\alpha_i\alpha_j y_i y_j (x_i^T x_j)
$$

$$
\text{s.t.} \quad \alpha_i \geq 0, \sum_i \alpha_i y_i = 0
$$

$\alpha_i > 0$ 的样本就是支持向量。

## 5.3 软间隔 SVM

实际数据常线性不可分，引入**松弛变量** $\xi_i \geq 0$：

$$
\min_{w, b, \xi} \frac{1}{2}\|w\|^2 + C\sum_{i=1}^N \xi_i
$$

$$
\text{s.t.} \quad y_i(w^T x_i + b) \geq 1 - \xi_i, \quad \xi_i \geq 0
$$

- $C$ 大 → 重视误分（可能过拟合）
- $C$ 小 → 重视间隔（容忍误分）

Hinge 损失视角：

$$
\min_w \frac{1}{2}\|w\|^2 + C\sum_{i=1}^N \max(0, 1 - y_i(w^T x_i + b))
$$

## 5.4 核方法 (Kernel Trick)

很多问题不是线性可分的，但高维空间里可能线性可分。

### 思想

不显式映射 $\phi: \mathcal{X} \to \mathcal{H}$，而是用核函数：

$$
K(x_i, x_j) = \langle \phi(x_i), \phi(x_j) \rangle
$$

决策函数：

$$
f(x) = \text{sign}\left(\sum_{i=1}^N \alpha_i y_i K(x_i, x) + b\right)
$$

### 常用核函数

| 核 | 公式 | 适用 |
|----|------|------|
| 线性核 | $K(x, x') = x^T x'$ | 线性可分、高维稀疏 |
| 多项式核 | $K(x, x') = (x^T x' + c)^d$ | 多项式关系 |
| RBF (高斯) | $K(x, x') = \exp(-\gamma \\|x - x'\\|^2)$ | 通用、默认选择 |
| Sigmoid | $K(x, x') = \tanh(\beta x^T x' + c)$ | 类似 NN（实际不太用） |

### RBF 核展开

RBF 核映射到无穷维空间：

$$
K(x, x') = \exp(-\gamma\|x - x'\|^2)
$$

等价于用泰勒展开成无穷维多项式组合。

### Mercer 条件

合法核函数的条件：

$$
\iint K(x, y) f(x) f(y) dx dy \geq 0, \quad \forall f \in L_2
$$

任何满足 Mercer 条件的函数都可作核。

## 5.5 代码

### 线性 SVM

```python
from sklearn.svm import SVC

model = SVC(
    C=1.0,             # 正则强度倒数，越大越接近硬间隔
    kernel='linear',
    random_state=42,
)
model.fit(X_train, y_train)
y_pred = model.predict(X_test)
```

### RBF 核 SVM

```python
model = SVC(
    C=1.0,
    kernel='rbf',
    gamma='scale',     # 或 'auto' 或具体值
    probability=True,  # 启用 predict_proba (会慢)
    random_state=42,
)
y_proba = model.predict_proba(X_test)[:, 1]
```

### 多分类

SVM 本身是二分类，多分类用：

- **One-vs-Rest (OvR)**：每类 vs 其他
- **One-vs-One (OvO)**：每对类一个 SVM

sklearn 默认 OvO。

```python
model = SVC(decision_function_shape='ovr')  # 或 'ovo'
```

## 5.6 超参调优

| 超参 | 影响 | 推荐范围 |
|------|------|----------|
| `C` | 大 → 低 bias, 高方差；小 → 高 bias, 低方差 | [0.01, 100] (log) |
| `gamma` (RBF) | 大 → 局部、小方差；小 → 全局、大方差 | [0.001, 10] (log) |
| `degree` (poly) | 多项式次数 | 2~5 |

```python
from sklearn.model_selection import GridSearchCV

params = {
    'C': [0.1, 1, 10],
    'gamma': [0.001, 0.01, 0.1, 1],
    'kernel': ['rbf'],
}

grid = GridSearchCV(SVC(), params, cv=5, scoring='accuracy')
grid.fit(X_train, y_train)
print(f"Best params = {grid.best_params_}")
print(f"Best CV = {grid.best_score_:.3f}")
```

## 5.7 支持向量回归 (SVR)

把 SVR 损失换成 $\epsilon$-insensitive：

$$
L = \sum \max(0, |y_i - f(x_i)| - \epsilon)
$$

优化问题：

$$
\min \frac{1}{2}\|w\|^2 + C\sum (\xi_i + \xi_i^*)
$$

$$
\text{s.t.} \quad \begin{cases}
y_i - w^T x_i - b \leq \epsilon + \xi_i \\
w^T x_i + b - y_i \leq \epsilon + \xi_i^*
\end{cases}
$$

```python
from sklearn.svm import SVR

model = SVR(kernel='rbf', C=1.0, epsilon=0.1, gamma='scale')
y_pred = model.predict(X_test)
```

## 5.8 数学性质

### 间隔边界

SVM 的泛化误差有界：

$$
R \leq \frac{R_{\text{emp}}}{\text{间隔}} = \frac{\text{分}}{\|\hat{w}\|}
$$

最小化 $\|\hat{w}\|$ → 间隔最大 → 泛化好。

### VC 维

RBF 核 SVM 的 VC 维 $\le \lceil R^2 \|w\|^2 \rceil + 1$。

### 凸优化

SVM 是凸优化问题 → 全局最优。

## 5.9 优缺点

### 优点

- 高维数据表现好 (文本、生物信息)
- 仅支持向量决定决策 → 内存省
- 核方法灵活
- 间隔大 → 泛化强
- 凸优化保证全局最优

### 缺点

- 大数据集训练慢 ($\mathcal{O}(N^2)$~$\mathcal{O}(N^3)$)
- 对特征缩放敏感
- 不直接输出概率 (要 `probability=True` 才支持，但慢)
- 多分类不如 LR / GBDT 直观
- 缺失值需预处理

## 5.10 实用建议

### 数据预处理

```python
from sklearn.preprocessing import StandardScaler

# 一定要缩放！
scaler = StandardScaler()
X_train = scaler.fit_transform(X_train)
X_test = scaler.transform(X_test)  # 注意只 transform
```

### 大数据集

>10K 样本：考虑用 `LinearSVC` 或 `SGDClassifier`

```python
from sklearn.svm import LinearSVC

# 线性 SVM 的快速实现，适合大 N
model = LinearSVC(C=1.0, max_iter=1000, dual='auto')
```

### 加速库

- `LibSVM` (sklearn 用)：完整核 SVM，慢
- `LibLinear`：线性 SVM，快
- `ThunderSVM`：GPU 加速
- `cuML`：GPU RAPIDS

### 类别不均衡

```python
model = SVC(class_weight='balanced')
```

## 5.11 与其他分类器对比

| 维度 | SVM | LR | RF | KNN |
|------|-----|-----|-----|-----|
| 训练速度 | 慢 | 快 | 中 | - |
| 推理速度 | 中 | 快 | 快 | 慢 |
| 高维数据 | 强 | 强 | 中 | ❌ |
| 解释性 | 中 | **强** | 中 | 中 |
| 概率输出 | 弱 | **强** | 强 | 强 |
| 处理缺失 | ❌ | ❌ | ✅ | ❌ |

## 5.12 应用场景

- 文本分类 (高维稀疏，TF-IDF + Linear SVC)
- 图像分类 (中小数据集 + RBF)
- 生物信息学 (基因表达数据，高维少样本)
- 异常检测 (One-Class SVM，见 [10-异常检测](10-异常检测.md))
- 回归 (SVR)

## 5.13 参考

- Cortes & Vapnik, 1995 *Support-Vector Networks*
- Vapnik, 1998 *Statistical Learning Theory*
- Bishop, 2006 *PRML* Ch. 7
- Hastie et al., 2009 *ESL* Ch. 12