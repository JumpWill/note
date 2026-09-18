# 10. Transformer 详解

Transformer (Vaswani et al., 2017) 是当代深度学习的核心架构，统治 NLP、CV、多模态。

## 10.1 核心思想

Transformer 用 **Self-Attention** 替代 RNN/CNN：
- 完全并行训练
- 全局感受野
- 关系建模能力强

## 10.2 Self-Attention

### 核心公式

$$
\text{Attention}(Q, K, V) = \text{softmax}\left(\frac{QK^T}{\sqrt{d_k}}\right) V
$$

- $Q$ (Query)：查询
- $K$ (Key)：键
- $V$ (Value)：值
- $d_k$：key 维度

### 流程

```
Q (n × d_k)
K (m × d_k)
V (m × d_v)

Q @ K^T → (n × m)         # 相似度
/ sqrt(d_k) → scale        # 防止 softmax 饱和
softmax → 概率             # 权重
@ V → (n × d_v)            # 加权求和
```

### 代码实现

```python
def attention(Q, K, V, mask=None):
    d_k = Q.size(-1)
    scores = Q @ K.transpose(-2, -1) / (d_k ** 0.5)

    if mask is not None:
        scores = scores.masked_fill(mask == 0, float('-inf'))

    attn = scores.softmax(dim=-1)
    return attn @ V, attn
```

## 10.3 Multi-Head Attention

并行多个 head，每个 head 学不同子空间：

$$
\text{MultiHead}(Q, K, V) = \text{Concat}(\text{head}_1, \ldots, \text{head}_h) W^O
$$

$$
\text{head}_i = \text{Attention}(QW_i^Q, KW_i^K, VW_i^V)
$$

```python
class MultiHeadAttention(nn.Module):
    def __init__(self, d_model, n_heads):
        super().__init__()
        assert d_model % n_heads == 0
        self.d_k = d_model // n_heads
        self.n_heads = n_heads
        self.W_q = nn.Linear(d_model, d_model)
        self.W_k = nn.Linear(d_model, d_model)
        self.W_v = nn.Linear(d_model, d_model)
        self.W_o = nn.Linear(d_model, d_model)

    def forward(self, x, mask=None):
        B, L, D = x.shape
        H = self.n_heads
        d_k = self.d_k

        # 线性投影 + 拆分 heads
        Q = self.W_q(x).view(B, L, H, d_k).transpose(1, 2)  # (B, H, L, d_k)
        K = self.W_k(x).view(B, L, H, d_k).transpose(1, 2)
        V = self.W_v(x).view(B, L, H, d_k).transpose(1, 2)

        # Attention
        scores = Q @ K.transpose(-2, -1) / (d_k ** 0.5)
        if mask is not None:
            scores = scores.masked_fill(mask == 0, float('-inf'))
        attn = scores.softmax(dim=-1)

        out = attn @ V  # (B, H, L, d_k)
        out = out.transpose(1, 2).contiguous().view(B, L, D)
        return self.W_o(out)
```

## 10.4 Masking

### Padding Mask

忽略 <pad>：

```python
def padding_mask(seq, pad=0):
    return (seq != pad).unsqueeze(1).unsqueeze(2)  # (B, 1, 1, L)
```

### Causal Mask (Decoder)

下三角：

```python
def causal_mask(L):
    return torch.tril(torch.ones(L, L)).unsqueeze(0).unsqueeze(0)  # (1, 1, L, L)
```

组合：

```python
mask = padding_mask & causal_mask  # (B, 1, L, L)
```

### Flash Attention

```python
from torch.nn.functional import scaled_dot_product_attention
# 内置 Flash Attention
output = scaled_dot_product_attention(Q, K, V, is_causal=True)
```

## 10.5 位置编码

Self-Attention 本身**无顺序**，需位置编码。

### Sinusoidal (原始)

$$
\begin{aligned}
PE(pos, 2i) &= \sin(pos / 10000^{2i/d}) \\
PE(pos, 2i+1) &= \cos(pos / 10000^{2i/d})
\end{aligned}
$$

```python
class PositionalEncoding(nn.Module):
    def __init__(self, d_model, max_len=5000):
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len).unsqueeze(1).float()
        div_term = torch.exp(torch.arange(0, d_model, 2).float() *
                             (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer('pe', pe.unsqueeze(0))

    def forward(self, x):
        return x + self.pe[:, :x.size(1)]
```

### Learned Position Embedding

```python
self.pos_embed = nn.Embedding(max_len, d_model)
```

BERT / GPT 用。

### RoPE (Rotary Position Embedding)

旋转位置编码：

$$
\text{RoPE}(x_m, m) = R_m \cdot x_m
$$

- 相对位置自然建模
- LLaMA / Mistral 默认
- 外推到长序列

### ALiBi

位置用注意力偏置：

$$
\text{score}_{i,j} = q_i \cdot k_j - m \cdot |i - j|
$$

线性插值友好。

## 10.6 Transformer Block

### Encoder Block

```
x → LayerNorm → Multi-Head Attention → Add
  → LayerNorm → FFN → Add
```

```python
class TransformerBlock(nn.Module):
    def __init__(self, d_model, n_heads, d_ff, dropout=0.1):
        super().__init__()
        self.attn = MultiHeadAttention(d_model, n_heads)
        self.ff = nn.Sequential(
            nn.Linear(d_model, d_ff),
            nn.GELU(),
            nn.Linear(d_ff, d_model),
        )
        self.ln1 = nn.LayerNorm(d_model)
        self.ln2 = nn.LayerNorm(d_model)
        self.drop = nn.Dropout(dropout)

    def forward(self, x, mask=None):
        # Pre-LN (现代)
        x = x + self.drop(self.attn(self.ln1(x), mask))
        x = x + self.drop(self.ff(self.ln2(x)))
        return x
```

### FFN (Feed-Forward Network)

$$
\text{FFN}(x) = W_2 \sigma(W_1 x + b_1) + b_2
$$

激活函数：

- ReLU (原始)
- GELU (BERT)
- SwiGLU (LLaMA)

### Decoder Block

```
x → LN → Masked MHA → Add
  → LN → Cross-Attention → Add
  → LN → FFN → Add
```

```python
class DecoderBlock(nn.Module):
    def __init__(self, d_model, n_heads, d_ff, dropout=0.1):
        super().__init__()
        self.self_attn = MultiHeadAttention(d_model, n_heads)
        self.cross_attn = MultiHeadAttention(d_model, n_heads)
        self.ff = nn.Sequential(
            nn.Linear(d_model, d_ff),
            nn.GELU(),
            nn.Linear(d_ff, d_model),
        )
        self.ln1 = nn.LayerNorm(d_model)
        self.ln2 = nn.LayerNorm(d_model)
        self.ln3 = nn.LayerNorm(d_model)
        self.drop = nn.Dropout(dropout)

    def forward(self, x, enc, src_mask=None, tgt_mask=None):
        x = x + self.drop(self.self_attn(self.ln1(x), tgt_mask))
        x = x + self.drop(self.cross_attn(self.ln2(x), self.ln2(enc), src_mask))
        x = x + self.drop(self.ff(self.ln3(x)))
        return x
```

## 10.7 完整 Encoder-Decoder

```python
class Transformer(nn.Module):
    def __init__(self, src_vocab, tgt_vocab, d_model=512, n_heads=8,
                 n_enc=6, n_dec=6, d_ff=2048, max_len=5000, dropout=0.1):
        super().__init__()
        self.src_embed = nn.Embedding(src_vocab, d_model)
        self.tgt_embed = nn.Embedding(tgt_vocab, d_model)
        self.pos_enc = PositionalEncoding(d_model, max_len)

        self.encoder = nn.ModuleList([
            TransformerBlock(d_model, n_heads, d_ff, dropout)
            for _ in range(n_enc)
        ])
        self.decoder = nn.ModuleList([
            DecoderBlock(d_model, n_heads, d_ff, dropout)
            for _ in range(n_dec)
        ])
        self.fc = nn.Linear(d_model, tgt_vocab)

    def encode(self, src, src_mask):
        x = self.pos_enc(self.src_embed(src))
        for block in self.encoder:
            x = block(x, src_mask)
        return x

    def decode(self, tgt, enc, src_mask, tgt_mask):
        x = self.pos_enc(self.tgt_embed(tgt))
        for block in self.decoder:
            x = block(x, enc, src_mask, tgt_mask)
        return self.fc(x)
```

## 10.8 三大家族：GPT / BERT / T5

### GPT (Decoder-only)

```
[BOS] x_1 → [Masked MHA] → y_1 (predict x_2)
[BOS] x_1, x_2 → [Masked MHA] → y_2 (predict x_3)
...
```

- **自回归**：从左到右
- **预训练目标**：Next Token Prediction
- **GPT-1/2/3/4**、**LLaMA**、**Mistral**

### BERT (Encoder-only)

```
x_1 → [MHA] → h_1  (双向 context)
x_2 → [MHA] → h_2
...
```

- **双向**
- **预训练目标**：MLM + NSP
- **BERT**、**RoBERTa**、**DeBERTa**

### T5 / BART (Encoder-Decoder)

- **Encoder**：理解输入
- **Decoder**：自回归生成
- **T5**、**BART**、**mBART**、**FLAN-T5**

### 对比

| | GPT | BERT | T5 |
|--|-----|------|----|
| 注意力 | Masked | 全双向 | 双向+因果 |
| 预训练 | NTP | MLM | Span Corruption |
| 优势 | 生成 | 理解 | 通用 |
| 应用 | Chat | 分类 / 检索 | 翻译 / QA |

## 10.9 现代 LLM 架构

### LLaMA / Mistral

- Pre-RMSNorm
- SwiGLU FFN
- RoPE
- GQA (Grouped Query Attention)

```python
class LlamaBlock(nn.Module):
    def __init__(self, dim, n_heads, d_ff):
        super().__init__()
        self.attn = GroupedQueryAttention(dim, n_heads)
        self.ff = SwiGLU(dim, d_ff)
        self.ln1 = RMSNorm(dim)
        self.ln2 = RMSNorm(dim)

    def forward(self, x, mask=None):
        x = x + self.attn(self.ln1(x), mask)
        x = x + self.ff(self.ln2(x))
        return x
```

### 关键技术

#### Pre-Norm vs Post-Norm

- Pre-Norm：稳定、训练深
- Post-Norm：性能略好但难训练

#### RMSNorm

LN 简化版，去均值：

```python
class RMSNorm(nn.Module):
    def __init__(self, dim, eps=1e-6):
        super().__init__()
        self.weight = nn.Parameter(torch.ones(dim))
        self.eps = eps

    def forward(self, x):
        rms = x.pow(2).mean(-1, keepdim=True).sqrt() + self.eps
        return x / rms * self.weight
```

#### GQA / MQA

GQA 减少 KV 缓存：

- **MHA**：n_heads 个 KV
- **MQA**：1 个 KV
- **GQA**：分组 KV (LLaMA-2 70B)

#### RoPE

相对位置编码，外推友好。

### GPT-4 / Claude / Gemini

闭源，详细架构未知。但用 Transformer 变体。

## 10.10 Vision Transformer (ViT)

### 思想

图像切成 patch，线性投影成 token，再过 Transformer。

```
224×224×3 → 16×16 = 196 patches → Linear → 196 tokens → Transformer → CLS
```

```python
class ViT(nn.Module):
    def __init__(self, img_size=224, patch_size=16, in_chans=3,
                 num_classes=1000, embed_dim=768, depth=12, n_heads=12):
        super().__init__()
        self.patch_embed = nn.Conv2d(in_chans, embed_dim, patch_size, patch_size)
        num_patches = (img_size // patch_size) ** 2
        self.cls_token = nn.Parameter(torch.zeros(1, 1, embed_dim))
        self.pos_embed = nn.Parameter(torch.zeros(1, num_patches + 1, embed_dim))
        self.blocks = nn.ModuleList([
            TransformerBlock(embed_dim, n_heads, embed_dim * 4)
            for _ in range(depth)
        ])
        self.norm = nn.LayerNorm(embed_dim)
        self.head = nn.Linear(embed_dim, num_classes)

    def forward(self, x):
        B = x.shape[0]
        x = self.patch_embed(x).flatten(2).transpose(1, 2)  # (B, N, D)
        cls = self.cls_token.expand(B, -1, -1)
        x = torch.cat([cls, x], dim=1) + self.pos_embed
        for block in self.blocks:
            x = block(x)
        return self.head(self.norm(x[:, 0]))
```

### Swin Transformer

- 层级架构（4 阶段）
- 滑动窗口 attention
- 下采样

### 应用

- 分类 (ViT / Swin / DeiT)
- 检测 (DETR / DINO)
- 分割 (SegFormer / Mask2Former)

## 10.11 多模态 Transformer

### CLIP

```
图像 → Image Encoder → 图像 embedding
文本 → Text Encoder  → 文本 embedding
→ 对比学习
```

### Flamingo / BLIP / LLaVA

- 视觉编码器 + LLM
- 投影层对齐
- 视觉问答

详见 [13-预训练与微调](13-预训练与微调.md)。

## 10.12 高效 Attention

### 复杂度问题

标准 attention: $O(L^2 d)$。长序列 OOM。

### 方案

#### Flash Attention

- IO 优化、kernel fusion
- 速度 ↑ 4x，显存 ↓ 20x
- **必装**

```python
from torch.nn.functional import scaled_dot_product_attention
```

#### Multi-Query / Grouped Query

- KV cache 减少
- 推理加速

#### Sliding Window

- 局部窗口 attention
- Mistral

#### Sparse Attention

- BigBird / Longformer
- 全局 + 局部 + 随机

#### Linear Attention

- Performer / Linformer
- $O(L)$

#### State Space Models

- S4 / Mamba
- $O(L)$

## 10.13 KV Cache

推理时缓存之前的 K/V，避免重复计算：

```python
class KVCache:
    def __init__(self, max_len, n_heads, head_dim):
        self.k = torch.zeros(1, n_heads, max_len, head_dim)
        self.v = torch.zeros(1, n_heads, max_len, head_dim)
        self.size = 0

    def update(self, k_new, v_new):
        self.k[:, :, self.size] = k_new
        self.v[:, :, self.size] = v_new
        self.size += 1
        return self.k[:, :, :self.size], self.v[:, :, :self.size]
```

详见 [15-推理与部署](15-推理与部署.md)。

## 10.14 参数高效微调 (PEFT)

详见 [13-预训练与微调](13-预训练与微调.md)。

### LoRA

低秩适配：

$$
W' = W + \Delta W = W + AB
$$

$A \in \mathbb{R}^{d \times r}$, $B \in \mathbb{R}^{r \times d}$，$r \ll d$

```python
class LoRALinear(nn.Module):
    def __init__(self, in_dim, out_dim, r=8, alpha=16):
        super().__init__()
        self.W = nn.Linear(in_dim, out_dim, bias=False)
        self.A = nn.Parameter(torch.randn(in_dim, r) * 0.01)
        self.B = nn.Parameter(torch.zeros(r, out_dim))
        self.alpha = alpha

    def forward(self, x):
        return self.W(x) + (x @ self.A @ self.B) * (self.alpha / self.A.size(1))
```

## 10.15 训练技巧

### Mixed Precision

```python
from torch.cuda.amp import autocast

with autocast(dtype=torch.bfloat16):
    output = model(input_ids)
    loss = criterion(output, labels)
loss.backward()
```

LLM 用 bfloat16，损失缩放较少需要。

### Gradient Checkpointing

```python
model.gradient_checkpointing_enable()
```

### torch.compile

```python
model = torch.compile(model)
```

### ZeRO / FSDP

分布式优化（[14](14-分布式训练.md)）。

## 10.16 训练数据准备

### Tokenization

```python
from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained('meta-llama/Llama-3.1-8B')
tokens = tokenizer.encode("Hello, world!")
# [100, 200, 300]

tokens = tokenizer("Hello, world!", return_tensors='pt')
```

### 主流 tokenizer

- BPE (GPT)
- WordPiece (BERT)
- SentencePiece (LLaMA / T5)
- tiktoken (OpenAI)

## 10.17 评估

### 困惑度 (Perplexity)

$$
\text{PPL} = \exp\left(-\frac{1}{N}\sum_i \log p(x_i)\right)
$$

### 任务评估

- MMLU / GSM8K / HumanEval / TruthfulQA
- lm-evaluation-harness

## 10.18 参考

- Vaswani et al., 2017 *Attention Is All You Need*
- Devlin et al., 2019 *BERT: Pre-training of Deep Bidirectional Transformers*
- Radford et al., 2018/2019/2020 *Improving Language Understanding by Generative Pre-Training* (GPT 1/2/3)
- Touvron et al., 2023 *LLaMA: Open and Efficient Foundation Language Models*
- Dosovitskiy et al., 2021 *An Image is Worth 16x16 Words* (ViT)
- Liu et al., 2021 *Swin Transformer*
- Dao et al., 2022 *FlashAttention*
- Hu et al., 2022 *LoRA: Low-Rank Adaptation of Large Language Models*
- Su et al., 2021 *RoFormer: Enhanced Transformer with Rotary Position Embedding*