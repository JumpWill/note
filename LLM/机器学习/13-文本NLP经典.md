# 13. 文本 NLP 经典 (Classical NLP)

深度学习时代之前的 NLP 方法仍然有重要价值：可解释、轻量、对小数据友好。这一章回顾经典 NLP 技术。

## 13.1 NLP 任务概览

### 经典任务

- **分词 (Tokenization)**：句子 → 词
- **词性标注 (POS)**：每个词的语法角色
- **命名实体识别 (NER)**：人名、地名、机构等
- **文本分类**：情感、主题
- **情感分析 (Sentiment)**
- **机器翻译 (MT)**：经典 IBM Models / 统计 MT
- **问答 (QA)**
- **摘要 (Summarization)**：抽取式 / 生成式

## 13.2 文本预处理

### 分词

```python
# 英文：NLTK, spaCy
import nltk
nltk.download('punkt')
nltk.word_tokenize("Hello, world!")

import spacy
nlp = spacy.load("en_core_web_sm")
doc = nlp("Hello, world!")
tokens = [token.text for token in doc]
```

```python
# 中文：jieba
import jieba

seg_list = jieba.cut("我爱自然语言处理")
print("/".join(seg_list))
```

### 停用词

```python
from nltk.corpus import stopwords
stop_words = set(stopwords.words('english'))

tokens = [w for w in tokens if w not in stop_words]
```

### 词形还原 / 词干提取

```python
from nltk.stem import WordNetLemmatizer, PorterStemmer

# 词形还原
lemmatizer = WordNetLemmatizer()
lemmatizer.lemmatize("running")  # 'running'

# 词干提取
stemmer = PorterStemmer()
stemmer.stem("running")  # 'run'
```

### 标准化

- 转小写
- 去除标点
- 数字归一化
- 拼写纠正

## 13.3 词袋模型 (Bag of Words, BoW)

把文本表示为词频向量：

$$
x = [\text{count}(\text{word}_1), \text{count}(\text{word}_2), \ldots]
$$

```python
from sklearn.feature_extraction.text import CountVectorizer

corpus = ["I love NLP", "NLP is great"]
vec = CountVectorizer()
X = vec.fit_transform(corpus)
print(vec.get_feature_names_out())
print(X.toarray())
```

## 13.4 TF-IDF

**TF (Term Frequency)**：

$$
\text{tf}(t, d) = \frac{\text{count}(t, d)}{\sum_{t' \in d} \text{count}(t', d)}
$$

**IDF (Inverse Document Frequency)**：

$$
\text{idf}(t) = \log\frac{N}{\text{df}(t) + 1}
$$

**TF-IDF**：

$$
\text{tfidf}(t, d) = \text{tf}(t, d) \cdot \text{idf}(t)
$$

高频词 (the, is) IDF 低；稀有词 IDF 高。

```python
from sklearn.feature_extraction.text import TfidfVectorizer

vec = TfidfVectorizer(
    max_features=10000,
    ngram_range=(1, 2),
    min_df=2,
    max_df=0.95,
    sublinear_tf=True,  # 1 + log(tf)
)
X = vec.fit_transform(corpus)
```

### 变体

- **sublinear_tf**：用 `1 + log(tf)` 替代 tf
- **smooth_idf**：`(N+1)/(df+1) + 1`

## 13.5 N-gram

考虑连续 N 个词的组合：

- Unigram (1-gram): 我 爱 NLP
- Bigram (2-gram): 我爱 爱NLP
- Trigram (3-gram): ...

```python
vec = CountVectorizer(ngram_range=(1, 3))  # 1-3 gram
```

### 应用

- 文本分类
- 语言模型 (经典)
- 关键词提取

## 13.6 主题模型

### LSA (Latent Semantic Analysis)

TF-IDF + SVD = 主题向量。

```python
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD

tfidf = TfidfVectorizer(max_features=10000)
X = tfidf.fit_transform(corpus)

svd = TruncatedSVD(n_components=100)
X_topic = svd.fit_transform(X)
```

### LDA (Latent Dirichlet Allocation)

每个文档 = 多个主题的混合，每个主题 = 词的分布。

```python
from sklearn.decomposition import LatentDirichletAllocation

lda = LatentDirichletAllocation(
    n_components=10,  # 主题数
    learning_method='batch',
    random_state=42,
)
lda.fit(X_tfidf)
# 主题-词分布：lda.components_
# 文档-主题分布：lda.transform(X)
```

### 应用

- 文档聚类
- 主题探索
- 文档摘要

## 13.7 词向量

### Word2Vec (Mikolov 2013)

两种架构：

- **CBOW**：从上下文预测目标词
- **Skip-gram**：从目标词预测上下文

```python
from gensim.models import Word2Vec

sentences = [["i", "love", "nlp"], ["i", "love", "ml"]]
model = Word2Vec(sentences, vector_size=100, window=5,
                 min_count=1, workers=4)

# 词向量
vec = model.wv['nlp']

# 相似词
model.wv.most_similar('nlp')

# 类比
model.wv.most_similar(positive=['king', 'woman'], negative=['man'])
```

### GloVe (Stanford)

基于全局共现矩阵分解：

$$
\log X_{ij} = w_i^T \tilde{w}_j + b_i + \tilde{b}_j
$$

```python
import gensim.downloader as api

glove = api.load("glove-wiki-gigaword-100")
```

### FastText (Facebook)

子词 (subword) 信息 + 词向量：

- 处理 OOV（罕见词 / 未登录词）
- 形态学丰富语言（德语、土耳其语）友好

```python
from gensim.models import FastText

model = FastText(sentences, vector_size=100, window=5)
model.wv['unseenword']  # 仍可得到向量
```

## 13.8 文本分类

### 经典 Pipeline

```python
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC

pipe = Pipeline([
    ('tfidf', TfidfVectorizer(max_features=50000, ngram_range=(1, 2))),
    ('clf', LogisticRegression(max_iter=1000)),
])

pipe.fit(X_train, y_train)
y_pred = pipe.predict(X_test)
```

### 模型选择

- **NB**：快、文本友好
- **LR**：基准、概率输出
- **SVM**：高维准确率
- **RF / GBDT**：特征组合

### 文本深度学习

- TextCNN (Kim 2014)
- BiLSTM + Attention
- HAN (Hierarchical Attention Network)
- ULMFiT
- BERT / Transformers

## 13.9 词性标注 (POS)

### 经典方法

- HMM (隐马尔可夫模型)
- MEMM (Maximum Entropy Markov)
- CRF (条件随机场)
- BiLSTM-CRF

### spaCy 一键标品

```python
doc = nlp("The quick brown fox jumps over the lazy dog.")
for token in doc:
    print(f"{token.text}\t{token.pos_}\t{token.tag_}")
```

## 13.10 命名实体识别 (NER)

### BIO 标注

- B-X：实体 X 的开始
- I-X：实体 X 的内部
- O：非实体

### 模型

- HMM
- MEMM
- **CRF**：经典 SOTA（深度学习前）
- BiLSTM-CRF
- BERT NER

```python
# spaCy
doc = nlp("Apple is looking at buying U.K. startup for $1 billion")
for ent in doc.ents:
    print(f"{ent.text}: {ent.label_}")
```

## 13.11 语言模型 (经典)

### N-gram 语言模型

$$
P(w_t | w_{1:t-1}) \approx P(w_t | w_{t-n+1:t-1})
$$

平滑方法：

- Laplace
- Kneser-Ney
- Interpolation

```python
# KenLM / SRILM 工具
# 训练后查询词序列概率
```

### 应用

- 语音识别解码
- 机器翻译评分
- 文本生成

## 13.12 序列标注 (CRF)

条件随机场：考虑整个序列的标签依赖。

$$
P(y|x) = \frac{1}{Z(x)} \exp\left(\sum_t \theta^T f(y_t, y_{t-1}, x_t)\right)
$$

```python
from sklearn_crfsuite import CRF

crf = CRF(
    algorithm='lbfgs',
    c1=0.1, c2=0.1,
    max_iterations=100,
    all_possible_transitions=True,
)
crf.fit(X_train, y_train)
```

## 13.13 关键词提取

### TF-IDF 排序

```python
from sklearn.feature_extraction.text import TfidfVectorizer

vec = TfidfVectorizer()
X = vec.fit_transform(docs)
# 每行 TF-IDF 最高分 = 关键词
```

### TextRank

基于 PageRank 的图算法：

- 节点：词
- 边：词共现
- 迭代算 PageRank

```python
import jieba.analyse
keywords = jieba.analyse.textrank(sentence, topK=10)
```

### YAKE

统计特征组合，无需训练语料。

## 13.14 文本相似度

### 词汇层面

- **余弦**：$\cos(A, B)$
- **Jaccard**：$|A \cap B| / |A \cup B|$
- **编辑距离** (Levenshtein)

### 句子层面

- BoW / TF-IDF + 余弦
- 词向量平均 + 余弦
- Sentence-BERT

```python
# S-BERT 嵌入
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')
emb = model.encode(sentences)
similarity = emb @ emb.T  # 余弦
```

## 13.15 机器翻译 (经典)

### 统计机器翻译 (SMT)

- **IBM Models**：词对齐
- **短语翻译表**：短语级别翻译
- **语言模型**：目标语言流畅性
- **解码**：束搜索找最佳翻译

### 工具

- Moses
- GIZA++ (词对齐)

现代已被神经 MT (NMT) 取代。

## 13.16 文本纠错

### 编辑距离

计算两个字串的最小编辑次数：

```
kitten → sitting
k → s (1)
e → i (1)
+ g (1)
= 3 次编辑
```

```python
import Levenshtein
Levenshtein.distance("kitten", "sitting")  # 3
```

### 应用

- OCR 后处理
- 输入法纠错
- ASR 后处理

## 13.17 文本数据增强

- **同义词替换**：用 WordNet 替换
- **回译**：中文 → 英文 → 中文
- **随机插入 / 删除 / 交换**
- **TF-IDF 词替换（保留关键词）**

```python
import nlpaug.augmenter.word as naw

aug = naw.SynonymAug(aug_src='wordnet')
text_aug = aug.augment("I love natural language processing")
```

## 13.18 文本可视化

### WordCloud

```python
from wordcloud import WordCloud

wc = WordCloud(width=800, height=400, background_color='white')
wc.generate(text)
wc.to_file('wordcloud.png')
```

### 主题气泡图

pyLDAvis 可视化 LDA 主题。

## 13.19 完整 Pipeline

```python
import pandas as pd
import re
import jieba
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

# 加载
df = pd.read_csv('chinese_text.csv')

# 预处理
def preprocess(text):
    text = re.sub(r'[^\w\s]', '', text)  # 去标点
    words = jieba.cut(text)              # 分词
    return ' '.join([w for w in words if len(w) > 1])  # 过滤单字

df['clean'] = df['text'].apply(preprocess)

# 划分
X_train, X_test, y_train, y_test = train_test_split(
    df['clean'], df['label'],
    test_size=0.2, random_state=42, stratify=df['label'],
)

# TF-IDF + LR
vec = TfidfVectorizer(max_features=50000, ngram_range=(1, 2))
X_train_vec = vec.fit_transform(X_train)
X_test_vec = vec.transform(X_test)

clf = LogisticRegression(max_iter=1000)
clf.fit(X_train_vec, y_train)

# 评估
y_pred = clf.predict(X_test_vec)
print(classification_report(y_test, y_pred))
```

## 13.20 经典 vs 现代

| 维度 | 经典 | 深度学习 |
|------|------|----------|
| 特征 | BoW, TF-IDF | Embedding (BERT) |
| 模型 | LR, SVM, NB | RNN, Transformer |
| 数据需求 | 千 ~ 万 | 万 ~ 亿 |
| 训练速度 | **快** | 慢 |
| 推理速度 | **快** | 中 |
| 可解释 | **强** | 弱 |
| 性能 | 中 | **强** |
| 部署 | 简单 | 复杂 |

### 何时用经典

- 数据少 (< 10K)
- 实时性要求高
- 可解释性优先
- 资源受限

### 何时用深度

- 数据多 (> 100K)
- 精度要求高
- 复杂任务 (QA、生成)

## 13.21 工具库

- **NLTK**：教学库
- **spaCy**：工业级
- **Gensim**：主题模型 + 词向量
- **scikit-learn**：TF-IDF + 分类
- **jieba**：中文分词
- **SnowNLP**：中文情感
- **pynlpir / pyltp**：中文处理
- **Hugging Face Transformers**：现代 SOTA

## 13.22 参考

- Jurafsky & Martin, 2023 *Speech and Language Processing* (经典教材)
- Manning et al., 2008 *Introduction to Information Retrieval*
- Mikolov et al., 2013 *Efficient Estimation of Word Representations in Vector Space* (Word2Vec)
- Pennington et al., 2014 *GloVe: Global Vectors for Word Representation*
- Blei et al., 2003 *Latent Dirichlet Allocation* (LDA)
- Lafferty et al., 2001 *Conditional Random Fields* (CRF)