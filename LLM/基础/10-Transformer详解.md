# Transformer 详解

## 1. 历史与动机

### 1.1 起源

```
2014  Seq2Seq + Attention (Bahdanau)
      └─ RNN encoder-decoder + attention，机器翻译 SOTA
      └─ 痛点：RNN 必须串行，长距离依赖弱
2017  "Attention Is All You Need" (Vaswani)
      └─ 完全去掉 RNN，全 Attention
      └─ 8 卡 P100 训练 3.5 天，BLEU 28.4
2018  BERT (Encoder) / GPT-1 (Decoder) ── 预训练范式
2020  GPT-3 (175B) ── In-context Learning
2023+ GPT-4 / Claude / LLaMA / Qwen ── 大一统
```

### 1.2 为什么 Transformer 赢了

1. **并行性**：整序列一次算完，无 RNN 串行依赖
2. **长距离依赖**：任意两个 token 直连，O(1) 路径
3. **Scaling Law**：性能随参数 / 数据 / 算力单调上升
4. **通用性**：NLP → CV → Audio → 多模态 → 蛋白质

## 2. Self-Attention 数学

### 2.1 缩放点积注意力

输入序列 $X \in \mathbb{R}^{n \times d}$，投影到三个矩阵：

$$
Q = X W_Q, \quad K = X W_K, \quad V = X W_V
$$

注意力：

$$
\text{Attention}(Q, K, V) = \text{softmax}\left(\frac{QK^T}{\sqrt{d_k}}\right) V
$$

- $Q, K, V \in \mathbb{R}^{n \times d_k}$
- $QK^T \in \mathbb{R}^{n \times n}$：每对 (i, j) 的相似度
- 除 $\sqrt{d_k}$：防止内积方差过大导致 softmax 饱和
- softmax 沿 key 维度归一化 → 注意力权重
- 加权聚合 $V$

### 2.2 直觉解释

```
seq:   [我  爱  学习]
Q[i]:   ←  i 位置的"查询"
K[j]:   ←  j 位置的"键"，被 i 查询
V[j]:   ←  j 位置的"值"，被 i 提取

输出[i] = Σ_j  α[i,j] · V[j]
其中 α[i,j] = softmax( Q[i] · K[j] / √d )
```

### 2.3 Masked Attention (Decoder-only)

训练时不能让 token 看到未来：

$$
\text{mask}(QK^T)_{ij} = \begin{cases} QK^T_{ij}, & j \le i \\ -\infty, & j > i \end{cases}
$$

softmax 后，未来位置权重 = 0。

### 2.4 Multi-Head Attention

并行 $h$ 个注意力头，每头在低维子空间工作：

$$
\text{MHA}(Q, K, V) = \text{Concat}(\text{head}_1, \ldots, \text{head}_h) W_O
$$

$$
\text{head}_i = \text{Attention}(X W_Q^{(i)}, X W_K^{(i)}, X W_V^{(i)})
$$

- $W_Q^{(i)} \in \mathbb{R}^{d \times d_k}$，$d_k = d/h$
- 多头允许模型同时关注不同子空间的关系

## 3. 完整结构

### 3.1 Encoder Block (BERT 系)

```
x
   ↓
LayerNorm ─→ Multi-Head Self-Attention ─→ + ─┐
   │                                         ├→ LayerNorm → FFN → + → out
   └─────────────────────────────────────────┘
```

(Pre-LN，当前主流)

### 3.2 Decoder Block (GPT 系)

```
x
   ↓
LayerNorm ─→ Masked MHA ─→ + ─┐
   │                           ├→ LayerNorm → MHA (cross, 可选) ─→ + ─┐
   │                           │                                          ├→ LN → FFN → + → out
   └───────────────────────────┘                                          │
       (T5 等 Enc-Dec 用 cross-attn)                                       │
                                                    └──────────────────────┘
```

Decoder-only LLM：只有 masked self-attention + FFN，没有 cross-attn。

### 3.3 Pre-Norm vs Post-Norm

**Pre-Norm** (主流 LLM)：

$$
\text{out} = x + \text{SubLayer}(\text{LN}(x))
$$

- 训练更稳定，无需 warmup / 学习率限制
- 当前 LLaMA、GPT、Qwen 全部用

**Post-Norm** (原 Transformer)：

$$
\text{out} = \text{LN}(x + \text{SubLayer}(x))
$$

- 早期 Transformer / ViT 某些变体
- 深层训练不稳

## 5. 位置编码

### 5.1 绝对位置编码 (Sinusoidal, 原 Transformer)

$$
PE_{(pos, 2i)} = \sin(pos / 10000^{2i/d})
$$

$$
PE_{(pos, 2i+1)} = \cos(pos / 10000^{2i/d})
$$

- 加到 input embedding 上
- 早期 BERT / GPT-2 用

### 5.2 相对位置编码 (RoPE, 当前主流)

对 Q、K 应用旋转矩阵：

$$
\text{RoPE}(x_m, m) = \begin{pmatrix} \cos m\theta & -\sin m\theta \\ \sin m\theta & \cos m\theta \end{pmatrix} x_m
$$

其中 $\theta = 10000^{-2i/d}$。

优点：

- 相对位置信息自然编码 (inner product 仅依赖相对位置)
- 长度外推性更好 (YaRN、LongRoPE 进一步改进)
- **LLaMA / Mistral / Qwen / DeepSeek 全部用 RoPE**

### 5.3 ALiBi (Attention with Linear Biases)

加到 attention score 上：

$$
\text{score}_{ij} = Q_i K_j^T / \sqrt{d} - r \cdot |i - j|
$$

- 无额外参数
- 强长度外推性 (很多任务到 100K token 仍工作)
- BLOOM 用

### 5.4 选型

| 场景 | 推荐 |
|------|------|
| 现代 LLM | RoPE (事实标准) |
| 长上下文 | RoPE + YaRN/LongRoPE 扩展 |
| 极致外推 | ALiBi |
| 视觉 (ViT) | Sinusoidal 或可学习 2D |
| 老模型 | Sinusoidal / 绝对 |

## 6. 归一化

### 6.1 LayerNorm

$$
\hat{x} = \frac{x - \mu}{\sqrt{\sigma^2 + \epsilon}} \cdot \gamma + \beta
$$

- 对每个 token 单独归一化（沿 hidden dim）
- 不依赖 batch
- 训练和推理一致

### 6.2 RMSNorm (现代主流)

$$
\hat{x} = \frac{x}{\text{RMS}(x)} \cdot \gamma, \quad \text{RMS}(x) = \sqrt{\frac{1}{d}\sum x_i^2}
$$

- 不要 mean 中心化，只缩放
- 计算更便宜，效果几乎一样
- LLaMA / Gemma / Qwen / Mistral 全部用 RMSNorm

### 6.3 选型

当前 LLM 几乎都用 **RMSNorm + Pre-LN**。

## 7. FFN（前馈网络）

### 7.1 标准 FFN

$$
\text{FFN}(x) = W_2 \sigma(W_1 x + b_1) + b_2
$$

- 两层 Linear
- 中间维度 $4d$ (ReLU 时代)
- 激活：ReLU → GELU → SwiGLU

### 7.2 GELU FFN

$$
\text{FFN}(x) = W_2 \text{GELU}(W_1 x + b_1) + b_2
$$

BERT、GPT-2/3 标准。

### 7.3 SwiGLU FFN (LLaMA 系)

$$
\text{FFN}(x) = W_2 (\text{SiLU}(W_1 x) \otimes W_3 x)
$$

- 三条线性 + 门控乘
- 参数从 $8d^2$ 增到 $12d^2$，但用更小中间维度（$8d/3$）
- **LLaMA-2/3、Mistral、Qwen、DeepSeek 全部用 SwiGLU**

### 7.4 FFN 是 LLM 的"知识库"

可解释性研究表明：FFN 中间神经元相当于"键值查找"，存了大量事实性知识。

- 知识更新可通过编辑 FFN 神经元实现 (ROME、MEMIT)
- 这是当前 LLM 知识机制研究的核心方向之一

## 8. Embedding

### 8.1 Token Embedding

```
token_id (int) → Embedding[V, d] → [d]
```

- 词表大小 $V$（中文 LLM 通常 100K~250K）
- 维度 $d$ 与 hidden size 一致

### 8.2 共享 Embedding / Weight Tying

input embedding 与 output projection 共享权重：

- 减少参数 30%~50%
- 加速收敛（小 LLM 收益明显）
- **LLM 标配**

### 8.3 Tied vs Untied

| 规模 | 推荐 |
|------|------|
| < 1B | Tied (共享) |
| 1B~7B | 视情况 |
| > 13B | Untied (分开) |

大模型 untied 反而效果更好（参数足够，不需要 tie 来防止过拟合）。

## 9. 三种家族

### 9.1 Encoder-only (BERT)

双向注意力，"理解"任务：

```
[CLS] sentence [SEP]
   ↓
N × Encoder block
   ↓
[CLS] 位置向量 → 分类
```

适用：

- 文本分类、NER、QA (答案抽取)
- 检索 (query/document encoding)

代表：BERT、RoBERTa、DeBERTa、E5/BGE (embedding)

### 9.2 Decoder-only (GPT, 当前主流)

单向 (masked) 自回归，"生成"任务：

```
prompt + [generated tokens]
   ↓
N × Decoder block (masked MHA + FFN)
   ↓
logits → next token
```

适用：

- 文本生成、对话、代码、推理
- 当前 LLM 主流 (GPT、Claude、LLaMA、Qwen、DeepSeek)

代表：GPT-1/2/3/4、Claude、LLaMA、Mistral、Qwen、DeepSeek、GLM

### 9.3 Encoder-Decoder (T5)

```
input  → Encoder → memory
                    ↓
output ← Decoder (cross-attn to memory) + masked self-attn
```

适用：

- 翻译、摘要、QA (生成式)
- 语音 (Whisper)

代表：T5、mBART、Whisper、Flan-T5

## 10. KV Cache

推理加速关键：

```
生成第 t 个 token 时：
- 不重新算前 t-1 个 token 的 K, V
- 只算当前 token 的 Q, K, V
- 拼接 K, V 到 cache
- attention 时只用当前 Q 与完整 K cache 算 attention
```

显存：

$$
\text{KV cache} = 2 \cdot L \cdot n \cdot d_k \cdot B \cdot \text{bytes per elem}
$$

- LLaMA-7B (32 层, d_k=128)：每 token 约 0.5 MB
- 100K 上下文：每序列约 50 GB → 单卡放不下

KV cache 优化：

- **GQA** (Grouped Query Attention)：多个 Q 头共享 K/V 头
- **MQA** (Multi-Query Attention)：所有 Q 共享一个 K、V
- **KV cache 量化**：INT8 / INT4 进一步省
- **PagedAttention** (vLLM)：分页存储，类似 OS 虚拟内存

## 11. Flash Attention

把 Attention 的 IO 复杂度从 $\mathcal{O}(n^2)$ 降到 $\mathcal{O}(n)$：

- 标准 Attention：要把 $n \times n$ 矩阵写到 HBM 再算 softmax
- Flash Attention：分块计算，全程留在 SRAM
- 数学结果**精确一致**，仅 IO 优化

效果：

- 长序列加速 2~4x
- 显存占用大降
- **现代 Transformer 训练标配**

## 12. 现代 LLM 架构

### 12.1 LLaMA-3 (Meta)

- Decoder-only, RoPE, RMSNorm, Pre-LN
- SwiGLU FFN
- GQA (8B/70B/405B)
- 词表 128K (多语言)
- 上下文 8K (可扩展到 128K)

### 12.2 Mistral / Mixtral (Mistral AI)

- Mistral 7B：标准 Transformer + GQA + Sliding Window Attention
- Mixtral 8x7B：MoE，8 专家 / 激活 2
- 上下文长 / 推理快

### 12.3 Qwen-2 / 2.5 (阿里)

- Dense + MoE 版本
- 词表大（151K），中文友好
- 上下文到 128K

### 12.4 DeepSeek-V3

- MoE：256 专家 / 激活 8
- Multi-head Latent Attention (MLA)
- FP8 训练

### 12.5 GPT-4 (OpenAI)

- 推测：MoE，~1.8T 总参数，~280B 激活
- 多模态 (文本 + 图像)

### 12.6 共同点

- Pre-LN + RMSNorm + SwiGLU
- RoPE 位置编码
- GQA 减少 KV cache
- MoE 减小推理成本
- 大词表 + 长上下文

## 13. Scaling Law

Kaplan & McCandlish (2020)，Hoffmann et al. (2022)：

$$
L(N, D) \approx \left[\left(\frac{N_c}{N}\right)^{\alpha_N} + \left(\frac{D_c}{D}\right)^{\alpha_D}\right]^{\alpha_L}
$$

- $N$ 参数，$D$ tokens
- $L$ loss 单调下降
- Hoffmann (Chinchilla)：最佳比例 $N : D \approx 1 : 20$ (每参数训练 20 token)

启示：

- 模型和数据应同步增长
- 固定算力下，宁可小模型多训 (Chinchilla)
- 推理成本随参数线性增

## 14. 训练配方

### 14.1 预训练

```python
optimizer = torch.optim.AdamW(
    model.parameters(),
    lr=3e-4,                # 峰值
    betas=(0.9, 0.95),
    weight_decay=0.1,
)
scheduler = get_cosine_schedule_with_warmup(optimizer, warmup=2000, total=200000)
```

- bf16 mixed precision
- Gradient checkpointing
- Flash Attention
- DDP + ZeRO (大模型)

### 14.2 SFT

- lr 1e-5 ~ 5e-5
- 单 epoch 或几 epoch
- 数据多样化

### 14.3 DPO / RLHF

- DPO 比 PPO 更稳、更省
- lr 极小 (5e-7 ~ 5e-6)
- 短训练 (几百步)

## 15. 选型

| 任务 | 推荐架构 |
|------|----------|
| 文本理解 (分类/NER/检索) | Encoder (BERT/E5) |
| 文本生成 (对话/创作/代码) | Decoder (LLaMA/Qwen) |
| 翻译 / 摘要 | Encoder-Decoder (T5) |
| 长文档处理 | Decoder + 长上下文 (RoPE-YaRN) |
| 多模态 | Decoder-only + vision encoder (LLaVA) |
| 高效推理 | Decoder + MoE + GQA |
| 边缘部署 | Decoder INT4 量化 (llama.cpp) |

## 16. 参考

- Vaswani et al., 2017 *Attention Is All You Need*
- Devlin et al., 2019 *BERT: Pre-training of Deep Bidirectional Transformers*
- Brown et al., 2020 *Language Models are Few-Shot Learners* (GPT-3)
- Su et al., 2021 *RoFormer: Enhanced Transformer with Rotary Position Embedding* (RoPE)
- Shazeer, 2019 *Fast Transformer Decoding: One Write-Head is All You Need* (MQA)
- Press et al., 2022 *Train Short, Test Long: Attention with Linear Biases* (ALiBi)
- Touvron et al., 2023 *LLaMA: Open and Efficient Foundation Language Models*
- Hoffmann et al., 2022 *Training Compute-Optimal Large Language Models* (Chinchilla)
- Dao et al., 2022 *FlashAttention: Fast and Memory-Efficient Exact Attention*
- Jacobs et al., 2023 *QLoRA: Efficient Finetuning of Quantized LLMs*
- DeepSeek-AI, 2024 *DeepSeek-V2: A Strong, Economical, and Efficient Mixture-of-Experts Language Model*
