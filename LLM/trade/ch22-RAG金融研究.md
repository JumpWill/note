# 第 22 章 — RAG 金融研究（3rd Edition）

## 章节目标

- RAG 原理
- 在 SEC 文件上的应用
- 检索增强的金融分析

## 22.1 RAG 基础

### 思想

- **R**etrieval-**A**ugmented **G**eneration
- 检索相关文档 → 提供给 LLM
- 减少幻觉、引入新知识

### 三步

1. **索引**：文档分块 + embedding + 向量库
2. **检索**：查询 → 相似文档
3. **生成**：LLM + 检索上下文 → 答案

## 22.2 LangChain RAG

### 基础流水线

```python
from langchain.document_loaders import DirectoryLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from langchain.chains import RetrievalQA
from langchain.llms import OpenAI

# 1. 加载
loader = DirectoryLoader('./sec_filings/', glob='**/*.txt', loader_cls=TextLoader)
documents = loader.load()

# 2. 分块
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
)
texts = text_splitter.split_documents(documents)

# 3. Embedding & 向量库
embeddings = OpenAIEmbeddings()
vectorstore = Chroma.from_documents(texts, embeddings)

# 4. QA 链
qa = RetrievalQA.from_chain_type(
    llm=OpenAI(model='gpt-4'),
    chain_type='stuff',
    retriever=vectorstore.as_retriever(search_kwargs={'k': 5}),
)

# 5. 查询
query = "What was the company's revenue growth in 2023?"
result = qa.run(query)
print(result)
```

## 22.3 嵌入模型选择

### 金融专用

- **FinBERT**：情感
- **OpenAI text-embedding-3-small**：通用 SOTA
- **BGE / M3E**：开源

```python
# 中文嵌入
from langchain.embeddings import HuggingFaceEmbeddings

embeddings = HuggingFaceEmbeddings(
    model_name='BAAI/bge-large-zh-v1.5',
    model_kwargs={'device': 'cuda'},
)
```

## 22.4 高级检索

### Hybrid Retrieval

```python
from langchain.retrievers import BM25Retriever, EnsembleRetriever

# BM25 (稀疏)
bm25_retriever = BM25Retriever.from_documents(texts)
bm25_retriever.k = 5

# 向量（稠密）
vector_retriever = vectorstore.as_retriever(search_kwargs={'k': 5})

# 集成
ensemble_retriever = EnsembleRetriever(
    retrievers=[bm25_retriever, vector_retriever],
    weights=[0.5, 0.5],
)

# 查询
docs = ensemble_retriever.get_relevant_documents(query)
```

### Re-ranking

```python
# pip install cohere
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import CohereRerank

compressor = CohereRerank(top_n=5)

compression_retriever = ContextualCompressionRetriever(
    base_compressor=compressor,
    base_retriever=vectorstore.as_retriever(search_kwargs={'k': 20}),
)

docs = compression_retriever.get_relevant_documents(query)
```

### Multi-Query

```python
from langchain.retrievers.multi_query import MultiQueryRetriever

retriever = MultiQueryRetriever.from_llm(
    retriever=vectorstore.as_retriever(),
    llm=OpenAI(),
)

# 自动生成多个查询
docs = retriever.get_relevant_documents("What is Apple's growth?")
```

## 22.5 SEC 文件 RAG

### 完整流水线

```python
"""SEC 文件 RAG"""
import os
from pathlib import Path
from langchain.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from langchain.chains import RetrievalQA
from langchain.llms import OpenAI
import pandas as pd

# 1. 加载所有 10-K 文件
filings_dir = Path('./10K_filings/')
filings = []

for filepath in filings_dir.glob('*.txt'):
    ticker = filepath.stem.split('_')[0]
    loader = TextLoader(str(filepath))
    docs = loader.load()

    # 添加 ticker metadata
    for doc in docs:
        doc.metadata['ticker'] = ticker

    filings.extend(docs)

# 2. 分块（按 ticker + 表格）
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1500,
    chunk_overlap=300,
    separators=['\n\n', '\n', '.', ' ', ''],
)
texts = text_splitter.split_documents(filings)

# 3. Embedding + 向量库
embeddings = OpenAIEmbeddings(model='text-embedding-3-small')
vectorstore = Chroma.from_documents(texts, embeddings, persist_directory='./chroma_db')

# 4. 自定义 QA
qa = RetrievalQA.from_chain_type(
    llm=OpenAI(model='gpt-4', temperature=0),
    chain_type='stuff',
    retriever=vectorstore.as_retriever(
        search_type='similarity',
        search_kwargs={'k': 8},
    ),
    return_source_documents=True,
)

# 5. 查询
queries = [
    "Which companies mentioned AI as a strategic priority?",
    "What are the main risk factors cited by tech companies?",
    "Compare revenue growth between AAPL and MSFT",
]

for query in queries:
    result = qa({'query': query})
    print(f"\nQ: {query}")
    print(f"A: {result['result']}")
    print(f"Sources: {[doc.metadata.get('ticker') for doc in result['source_documents']]}")
```

## 22.6 表格解析

### 数字 / 表格提取

```python
from langchain.document_loaders import UnstructuredHTMLLoader
from langchain.document_loaders.csv_loader import CSVLoader

# HTML 文件（含表格）
loader = UnstructuredHTMLLoader('apple_10k.html')
docs = loader.load()

# 或 PDF
from langchain.document_loaders import UnstructuredPDFLoader

loader = UnstructuredPDFLoader('apple_10k.pdf')
docs = loader.load()
```

### 处理表格

```python
import pandas as pd

# 把表格转为 markdown（LLM 友好）
def table_to_markdown(table):
    md = "| " + " | ".join(table.columns) + " |\n"
    md += "| " + " | ".join(["---"] * len(table.columns)) + " |\n"
    for _, row in table.iterrows():
        md += "| " + " | ".join(str(v) for v in row) + " |\n"
    return md
```

## 22.7 提示模板

### 财务分析模板

```python
from langchain.prompts import PromptTemplate

financial_prompt = PromptTemplate(
    input_variables=['context', 'question'],
    template="""
You are a financial analyst. Use the following SEC filing excerpts to answer the question.

Context from 10-K filings:
{context}

Question: {question}

Answer in a structured way:
1. Direct answer
2. Supporting evidence (quote if possible)
3. Source (ticker, page)
4. Confidence level

Answer:
""",
)

qa = RetrievalQA.from_chain_type(
    llm=OpenAI(model='gpt-4'),
    chain_type='stuff',
    retriever=vectorstore.as_retriever(),
    chain_type_kwargs={'prompt': financial_prompt},
)
```

## 22.8 GraphRAG

### 知识图谱 + RAG

```python
# pip install llama-index
from llama_index import (
    SimpleDirectoryReader,
    GPTVectorStoreIndex,
    ServiceContext,
)

# 加载
documents = SimpleDirectoryReader('./sec_filings/').load_data()

# 索引
service_context = ServiceContext.from_defaults(
    llm=OpenAI(model='gpt-4'),
    embed_model=OpenAIEmbedding(),
)

# 查询
query_engine = index.as_query_engine(
    similarity_top_k=10,
    response_mode='tree_summarize',
)

response = query_engine.query("Summarize Apple's strategy")
print(response)
```

## 22.9 评估 RAG

### 评估指标

- **Faithfulness**：答案是否基于上下文
- **Answer Relevance**：是否答非所问
- **Context Precision**：检索到的上下文是否相关
- **Context Recall**：是否检索到所有相关上下文

```python
# pip install ragas
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
)

# 准备评估数据
eval_data = {
    'question': ['Q1', 'Q2', ...],
    'answer': [result1, result2, ...],
    'contexts': [[...], [...], ...],
    'ground_truth': ['A1', 'A2', ...],
}

# 评估
result = evaluate(
    eval_data,
    metrics=[
        faithfulness,
        answer_relevancy,
        context_precision,
        context_recall,
    ],
)
```

## 22.10 实战：端到端 RAG 金融分析

```python
"""端到端 RAG 金融分析"""
import pandas as pd
from langchain.document_loaders import DirectoryLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from langchain.chains import RetrievalQA
from langchain.llms import OpenAI
from langchain.prompts import PromptTemplate

# 1. 加载 10-K
loader = DirectoryLoader('./filings/', glob='**/*.txt', loader_cls=TextLoader)
documents = loader.load()

# 2. 分块
splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
texts = splitter.split_documents(documents)

# 3. 向量化
vectorstore = Chroma.from_documents(
    texts,
    OpenAIEmbeddings(),
    collection_name='sec_filings',
    persist_directory='./db',
)

# 4. 自定义 prompt
prompt = PromptTemplate(
    input_variables=['context', 'question'],
    template="""
Based on the following SEC filing excerpts, answer the question.
If the answer isn't in the context, say so.

Context:
{context}

Question: {question}

Answer:
""",
)

# 5. QA 链
qa = RetrievalQA.from_chain_type(
    llm=OpenAI(model='gpt-4', temperature=0),
    chain_type='stuff',
    retriever=vectorstore.as_retriever(search_kwargs={'k': 5}),
    chain_type_kwargs={'prompt': prompt},
    return_source_documents=True,
)

# 6. 批量查询
questions = [
    "What are the key risk factors mentioned in the latest 10-K?",
    "Compare the revenue growth of AAPL vs MSFT over the past year.",
    "Which company has the highest gross margin?",
    "Identify companies that discussed AI initiatives.",
]

results = []
for q in questions:
    r = qa({'query': q})
    results.append({
        'question': q,
        'answer': r['result'],
        'sources': [doc.metadata.get('source', 'unknown') for doc in r['source_documents']],
    })

# 7. 输出
df_results = pd.DataFrame(results)
print(df_results)
```

## 22.11 RAG vs Fine-tuning

| 维度 | RAG | Fine-tuning |
|------|-----|-------------|
| 知识更新 | 立即 | 需重训 |
| 成本 | 中 | 高 |
| 定制 | 中 | **高** |
| 幻觉 | 较少 | 较多 |
| 适合 | 检索任务 | 风格 / 任务 |

## 22.12 关键 takeaway

- RAG 让 LLM 接入最新知识
- SEC 文件是典型应用
- 检索质量决定答案质量
- 评估很重要

## 22.13 现代框架

| 框架 | 特点 |
|------|------|
| **LangChain** | 主流、生态广 |
| **LlamaIndex** | 检索增强强 |
| **Haystack** | deepset 出品 |
| **DSPy** | 程序化 prompt |
| **txtai** | 轻量 |

## 22.14 实战陷阱

### 上下文窗口

- 文档太长超限
- 用 Map-Reduce / Refine

### 检索质量

- BM25 vs 向量 vs 混合
- Re-ranking

### Prompt 设计

- 提示要清晰
- 限制幻觉

### 评估

- 用 RAGAS
- 人工检查

## 22.15 参考

- Lewis et al., 2020 *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*
- Gao et al., 2024 *Retrieval-Augmented Generation for Large Language Models: A Survey*
- Khattab & Zaharia, 2024 *ColBERTv2: Effective and Efficient Retrieval via Lightweight Late Interaction*