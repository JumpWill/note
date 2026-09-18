# 09. RNN 与序列模型

循环神经网络 (RNN) 处理序列数据（文本、时间序列、语音）。核心是**循环连接**让信息跨时间步传递。

## 9.1 序列数据

### 类型

- **文本**：词 / 字符序列
- **时间序列**：股票、温度、传感器
- **音频**：采样点序列
- **视频**：帧序列

### 任务

| 任务 | 输入 | 输出 | 例 |
|------|------|------|----|
| 一对一 | 单 | 单 | 普通分类 |
| 一对多 | 单 | 序列 | 图像描述 |
| 多对一 | 序列 | 单 | 情感分类 |
| 多对多 (等长) | 序列 | 序列 | 词性标注 |
| 多对多 (异长) | 序列 | 序列 | 翻译 |

## 9.2 标准 RNN

### 数学

$$
h_t = f(W_h h_{t-1} + W_x x_t + b)
$$

$$
y_t = g(V h_t + c)
$$

- $h_t$：隐藏状态
- $x_t$：当前输入
- $y_t$：当前输出

### 流程

```
x_1 → x_2 → x_3 → x_4 → ... → x_T
↓     ↓     ↓     ↓
h_1 → h_2 → h_3 → h_4 → ... → h_T
↓
y_1   y_2   y_3   y_4       y_T
```

### 双向 RNN

```python
nn.RNN(input_size=128, hidden_size=256, num_layers=2, bidirectional=True, batch_first=True)
```

前向 + 反向，最后拼接。

### PyTorch 实现

```python
rnn = nn.RNN(input_size=128, hidden_size=256, num_layers=2, batch_first=True)
x = torch.randn(32, 50, 128)  # (B, L, F)
output, h_n = rnn(x)
# output: (B, L, H)
# h_n: (num_layers, B, H)
```

## 9.3 梯度问题

### BPTT (Backpropagation Through Time)

沿时间反向传播。

### 梯度消失 / 爆炸

$$
\frac{\partial L}{\partial h_1} = \prod_{t=2}^{T} \frac{\partial h_t}{\partial h_{t-1}}
$$

- 链式乘积 → 指数级消失 / 爆炸
- 序列长 → 无法学长期依赖

## 9.4 LSTM (Long Short-Term Memory)

### 核心思想

引入**门控机制**控制信息流：

- **遗忘门**：决定丢弃什么
- **输入门**：决定存什么
- **输出门**：决定输出什么

### 数学

$$
\begin{aligned}
f_t &= \sigma(W_f \cdot [h_{t-1}, x_t] + b_f) \\
i_t &= \sigma(W_i \cdot [h_{t-1}, x_t] + b_i) \\
\tilde{C}_t &= \tanh(W_C \cdot [h_{t-1}, x_t] + b_C) \\
C_t &= f_t \odot C_{t-1} + i_t \odot \tilde{C}_t \\
o_t &= \sigma(W_o \cdot [h_{t-1}, x_t] + b_o) \\
h_t &= o_t \odot \tanh(C_t)
\end{aligned}
$$

### 流程图

```
        ┌─────────────────────────┐
        │                         │
        │   ┌─────┐    ┌─────┐    │
x_t →  σ(i)─→ tanh ──┐           │
            │         ↓           │
        C_{t-1} → ⊗ → ⊕ → C_t    │
                  ↑   ↑           │
        σ(f)──┘   │              │
                  │              │
        h_{t-1} ─────────────────→ σ(o)─→ tanh ──→ h_t
        │                                         │
        └─────────────────────────────────────────┘
```

### PyTorch

```python
lstm = nn.LSTM(input_size=128, hidden_size=256, num_layers=2,
               batch_first=True, dropout=0.3, bidirectional=True)
output, (h_n, c_n) = lstm(x)
```

## 9.5 GRU (Gated Recurrent Unit)

LSTM 简化版，两个门：

$$
\begin{aligned}
z_t &= \sigma(W_z \cdot [h_{t-1}, x_t])  \quad \text{(update gate)} \\
r_t &= \sigma(W_r \cdot [h_{t-1}, x_t])  \quad \text{(reset gate)} \\
\tilde{h}_t &= \tanh(W \cdot [r_t \odot h_{t-1}, x_t]) \\
h_t &= (1 - z_t) \odot h_{t-1} + z_t \odot \tilde{h}_t
\end{aligned}
$$

```python
gru = nn.GRU(input_size=128, hidden_size=256, num_layers=2, batch_first=True)
```

参数少 1/3，性能与 LSTM 接近。

## 9.6 RNN 变体

### Peephole LSTM

门控看 cell state。

### Coupled Gate

GRU 风格合并遗忘门与输入门。

### QRNN

并行计算，训练快。

### SRU

简化版 + 高速。

### IndRNN

独立循环，深度友好。

## 9.7 序列到序列 (Seq2Seq)

### 编码器-解码器

```
Encoder:               Decoder:
x_1 → h_1              z_0 → y_1
x_2 → h_2              z_1 → y_2
x_3 → h_3              z_2 → y_3
       ↘ context ↗      z_3 → EOS
```

```python
class Seq2Seq(nn.Module):
    def __init__(self, enc, dec):
        super().__init__()
        self.encoder = enc
        self.decoder = dec

    def forward(self, src, tgt):
        context, hidden = self.encoder(src)
        output, _ = self.decoder(tgt, hidden)
        return output
```

### Teacher Forcing

训练时用真实标签作为下一步输入：

```python
# 50% 概率 teacher forcing
use_teacher = random.random() < 0.5
next_input = y_true if use_teacher else y_pred
```

## 9.8 注意力机制 (RNN 中)

### Bahdanau Attention

$$
\begin{aligned}
e_{t,i} &= v^T \tanh(W_h h_i + W_s s_{t-1}) \\
\alpha_{t,i} &= \frac{\exp(e_{t,i})}{\sum_j \exp(e_{t,j})} \\
c_t &= \sum_i \alpha_{t,i} h_i
\end{aligned}
$$

详见 [10-Transformer](10-Transformer详解.md)。

## 9.9 实战：情感分类

```python
class SentimentRNN(nn.Module):
    def __init__(self, vocab_size, embed_dim, hidden_dim, output_dim, n_layers=2):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embed_dim)
        self.lstm = nn.LSTM(embed_dim, hidden_dim, n_layers,
                            batch_first=True, bidirectional=True, dropout=0.3)
        self.fc = nn.Linear(hidden_dim * 2, output_dim)
        self.dropout = nn.Dropout(0.3)

    def forward(self, x):
        # x: (B, L)
        embedded = self.dropout(self.embedding(x))
        # embedded: (B, L, E)

        output, (hidden, cell) = self.lstm(embedded)
        # hidden: (n_layers * 2, B, H)
        hidden = torch.cat((hidden[-2], hidden[-1]), dim=1)

        return self.fc(self.dropout(hidden))
```

## 9.10 时间序列预测

### 单变量 LSTM

```python
class LSTMPredictor(nn.Module):
    def __init__(self, input_dim, hidden_dim, output_dim, num_layers=2):
        super().__init__()
        self.lstm = nn.LSTM(input_dim, hidden_dim, num_layers, batch_first=True)
        self.fc = nn.Linear(hidden_dim, output_dim)

    def forward(self, x):
        # x: (B, T, F)
        output, _ = self.lstm(x)
        return self.fc(output[:, -1, :])  # 用最后时间步
```

### 多步预测

```python
# 自回归
preds = []
for _ in range(future_steps):
    y = model(x)
    preds.append(y)
    x = torch.cat([x[:, 1:, :], y.unsqueeze(1)], dim=1)
```

### Seq2Seq 时间序列

编码器看历史，解码器输出未来。

## 9.11 文本生成

```python
class TextGenerator(nn.Module):
    def __init__(self, vocab_size, embed_dim, hidden_dim, num_layers=2):
        super().__init__()
        self.embed = nn.Embedding(vocab_size, embed_dim)
        self.lstm = nn.LSTM(embed_dim, hidden_dim, num_layers, batch_first=True)
        self.fc = nn.Linear(hidden_dim, vocab_size)

    def forward(self, x, hidden=None):
        emb = self.embed(x)
        output, hidden = self.lstm(emb, hidden)
        return self.fc(output), hidden

# 生成
def generate(model, start_token, length=50, temperature=1.0):
    model.eval()
    tokens = [start_token]
    hidden = None
    input = torch.tensor([[start_token]])
    with torch.no_grad():
        for _ in range(length):
            output, hidden = model(input, hidden)
            logits = output[0, -1] / temperature
            probs = F.softmax(logits, dim=-1)
            next_token = torch.multinomial(probs, 1).item()
            tokens.append(next_token)
            input = torch.tensor([[next_token]])
    return tokens
```

## 9.12 RNN vs Transformer

| 维度 | RNN | Transformer |
|------|-----|-------------|
| 并行训练 | ❌ 顺序 | ✅ 完全并行 |
| 长期依赖 | 差（百级） | **强（万级）** |
| 推理速度 | O(L) 串行 | O(L²) 自回归 |
| 长序列 | 慢 | O(L²) 内存 |
| 小数据 | ✅ 好 | 中 |
| 大数据 | 中 | **强** |
| 当前地位 | **已被替代** | 主流 |

### RNN 何时仍有用

- 实时流式（无完整序列）
- 超长序列
- 小数据 / 资源受限

## 9.13 替换方案

### 1D Convolution

```python
nn.Conv1d(embed_dim, hidden_dim, kernel_size=3, padding=1)
```

并行 + 大感受野。

### Transformer

详见 [10](10-Transformer详解.md)。

### S4 / Mamba

最新架构，处理超长序列 O(L)。

### Linear Attention

Performer / Linformer 等。

## 9.14 实战技巧

1. **梯度裁剪**：RNN 必备
   ```python
   torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
   ```

2. **层归一化**：层间 LN（Layer Normalization）

3. **Dropout**：嵌入后 / 层间

4. **Teacher Forcing Schedule**：从 1 退火到 0

5. **梯度累积**：batch 大显存不够

6. **混合精度**：提速

## 9.15 训练常见错误

| 问题 | 解决 |
|------|------|
| Loss NaN | 梯度裁剪 / 调小 LR |
| 输出全相同 | 检查 embedding / 模型容量 |
| 长序列不收敛 | 换 LSTM/GRU / 截断 BPTT |
| 训练慢 | 减小 hidden / 用 GRU |
| 显存不够 | 梯度累积 / 1D Conv |

## 9.16 现代混合架构

### Conformer (Speech)

Conv + Self-Attention：

```python
class ConformerBlock(nn.Module):
    def __init__(self, dim, heads):
        super().__init__()
        self.ff1 = FeedForward(dim)
        self.attn = MultiHeadSelfAttention(dim, heads)
        self.conv = ConvModule(dim)
        self.ff2 = FeedForward(dim)
        self.ln = nn.LayerNorm(dim)
```

### Mamba / SSM

线性复杂度序列建模。

## 9.17 参考

- Rumelhart et al., 1986 *Learning Representations by Back-Propagating Errors*
- Hochreiter & Schmidhuber, 1997 *Long Short-Term Memory*
- Cho et al., 2014 *Learning Phrase Representations using RNN Encoder-Decoder* (GRU)
- Sutskever et al., 2014 *Sequence to Sequence Learning with Neural Networks*
- Bahdanau et al., 2015 *Neural Machine Translation by Jointly Learning to Align and Translate*
- Vaswani et al., 2017 *Attention Is All You Need*
- Gu & Dao, 2023 *Mamba: Linear-Time Sequence Modeling with Selective State Spaces*