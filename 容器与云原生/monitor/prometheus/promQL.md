# PromQL 使用语法

PromQL(Prometheus Query Language)是 Prometheus 专为时序数据库设计的查询语言。除了 Prometheus,也广泛用于 Thanos、Cortex/Mimir、VictoriaMetrics、Grafana 等监控系统。

## 一、PromQL 表达式四种结果类型

PromQL 表达式的求值结果是以下四种之一:

| 类型 | 说明 | 示例 |
| --- | --- | --- |
| **Instant vector**(瞬时向量) | 一组时间序列,每个序列只有一个最新样本 | `up{job="node"}` |
| **Range vector**(范围向量) | 一组时间序列,每个序列包含一段时间内的多个样本 | `up{job="node"}[5m]` |
| **Scalar**(标量) | 一个浮点数 | `1.5`、`time()` |
| **String**(字符串) | 字符串,目前几乎不用 | `"hello"` |

> 大部分查询返回 instant vector,只有包含 `[5m]` 这种 range vector selector 的查询返回 range vector。

---

## 二、时序选择器(Time Series Selectors)

### 1. 瞬时向量选择器(Instant Vector Selector)

```promql
# 选择所有名称为 up 的指标
up

# 加上标签过滤
up{job="node-exporter"}

# 多个标签(AND 关系)
up{job="node-exporter", instance="node1:9100"}
```

#### 标签匹配操作符

| 操作符 | 含义 | 示例 |
| --- | --- | --- |
| `=` | 完全相等 | `job="nginx"` |
| `!=` | 不等于 | `job!="nginx"` |
| `=~` | 正则匹配 | `job=~"ngin.*"` |
| `!~` | 正则不匹配 | `job!~"test-.*"` |

```promql
# 正则匹配多个值
http_requests_total{status=~"5.."}

# 反选
http_requests_total{status!~"2.."}
```

### 2. 范围向量选择器(Range Vector Selector)

在 metric name 后追加 `[duration]` 即返回范围向量:

```promql
# 最近 5 分钟的样本
rate(http_requests_total[5m])

# 单位支持:s, m, h, d, w, y
http_requests_total{job="api"}[1h]
```

### 3. 偏移修饰符(Offset)

将求值时间往前推 N 秒,常用于对比昨天/上周同期:

```promql
# 1 小时前的瞬时值
http_requests_total offset 1h

# 1 小时前的 5 分钟范围
rate(http_requests_total[5m] offset 1h)

# 上一周同期的瞬时值
node_cpu_usage offset 1w
```

> `offset` 关键字必须放在 metric selector 之后,函数之前。

---

## 三、运算符

### 1. 算术运算符

| 运算符 | 说明 | 示例 |
| --- | --- | --- |
| `+` | 加 | `node_memory_MemFree_bytes + node_memory_Buffers_bytes` |
| `-` | 减 | `node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes` |
| `*` | 乘 | `rate(http_requests_total[5m]) * 60` |
| `/` | 除 | `node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes` |
| `%` | 取模 | `metric % 100` |
| `^` | 幂 | `2 ^ 10` |

**注意**:操作符两侧必须是兼容的数据类型。如果一边是 instant vector,另一边是 scalar,vector 的每个样本都会与 scalar 计算。

### 2. 比较运算符

| 运算符 | 说明 | 示例 |
| --- | --- | --- |
| `==` | 等于 | `up == 1` |
| `!=` | 不等于 | `up != 1` |
| `>` | 大于 | `node_cpu_seconds_total > 0.8` |
| `>=` | 大于等于 | `node_load5 >= 4` |
| `<` | 小于 | `node_filesystem_avail_bytes < 1e9` |
| `<=` | 小于等于 | `up <= 0` |

> ⚠️ 比较运算符默认会 **过滤掉不匹配的序列**,而不是返回 0/1。如需返回 0/1,使用 `bool` 修饰符:
>
> ```promql
> up == bool 1   # 不匹配的返回 0
> ```

### 3. 逻辑/集合运算符

只在两个 instant vector 之间使用:

| 运算符 | 说明 | 保留规则 |
| --- | --- | --- |
| `and` | 交集 | 左侧 + 右侧共有的标签 |
| `or` | 并集 | 任一侧有的标签 |
| `unless` | 差集 | 左侧有、右侧没有 |

```promql
# 状态为 up 且 1 分钟 CPU > 80%
up == 1 and rate(node_cpu_seconds_total[1m]) > 0.8

# 失败的 target(在 up{} 中不在 1)
up == 0 or absent(up)

# 不在剔除列表中的实例
up == 1 unless on(instance) (up{env="obsolete"})
```

### 4. 优先级(从高到低)

```
^  * / %  + -
== !=  > >= < <=
and  unless  or
```

> 一元负号(取相反数)优先级最高:`-up` 返回 0/1 反转。

---

## 四、内置函数

### 1. 速率类(最重要的几类)

#### `rate(v range-vector)`

- **作用**:区间向量每秒的平均增长率。**counter 指标**首选。
- **公式**:`(v[end] - v[start]) / duration`
- **特点**:能处理 counter 重置(自动 break),适合长期趋势分析。

```promql
# HTTP 请求 QPS(过去 5 分钟)
rate(http_requests_total[5m])
```

#### `irate(v range-vector)`

- **作用**:区间向量中最后两个样本的瞬时增长率。**短窗口**(1~5 分钟)。
- **特点**:对短期尖刺敏感,适合监控实时波动。

```promql
irate(http_requests_total[1m])
```

#### `increase(v range-vector)`

- **作用**:区间向量增加的总和(非每秒)。
- **场景**:统计一段时间的总增长量。

```promql
# 过去 1 小时新增错误数
increase(http_requests_total{status="500"}[1h])
```

#### `deriv(v range-vector)`

- **作用**:用最小二乘法估算每秒变化率。**gauge** 类型适用。

```promql
# 内存使用每秒变化
deriv(node_memory_MemAvailable_bytes[2m])
```

#### `delta(v range-vector)` / `idelta(v range-vector)`

- **delta**:区间内首尾差值(gauge)。
- **idelta**:区间内最后两个样本差值。

#### `predict_linear(v range-vector, t scalar)`

- **作用**:用线性回归预测 `t` 秒后的值。常用于磁盘预测告警。

```promql
# 预测 4 小时后磁盘是否满
predict_linear(node_filesystem_avail_bytes{mountpoint="/"}[6h], 4 * 3600) < 0
```

### 2. 数学函数

| 函数 | 说明 | 示例 |
| --- | --- | --- |
| `abs(v)` | 绝对值 | `abs(delta)` |
| `ceil(v)` | 向上取整 | `ceil(1.2) = 2` |
| `floor(v)` | 向下取整 | `floor(1.8) = 1` |
| `round(v)` | 四舍五入 | `round(1.5) = 2` |
| `exp(v)` | e 的 v 次方 | `exp(1) = 2.718` |
| `ln(v)` / `log2(v)` / `log10(v)` | 自然对数 / 2 底 / 10 底 | |
| `sqrt(v)` | 平方根 | `sqrt(4) = 2` |
| `sgn(v)` | 符号函数 | `sgn(-3) = -1` |
| `clamp_min(v, min)` | 下限 | `clamp_min(-5, 0) = 0` |
| `clamp_max(v, max)` | 上限 | `clamp_max(15, 10) = 10` |
| `clamp(v, min, max)` | 双向限制 | |
| `topk(k, v)` | 前 K 大(返回 K 条) | `topk(3, http_requests_total)` |
| `bottomk(k, v)` | 后 K 小 | |
| `quantile(φ, v)` | 分位数(φ 0~1) | `quantile(0.9, rate(...))` |

### 3. 时间函数

```promql
time()              # 当前 UTC 时间戳(秒)
timestamp(v)        # 样本的时间戳(秒)
minute() / hour()   # 当前时间的小时/分钟(UTC)
day_of_week()       # 0~6,周日=0
day_of_month()      # 1~31
days_in_month()     # 当月天数
month()             # 1~12
year()              # 当前年
```

> 这些函数都是返回 scalar,可以和 instant vector 比较做时间判断。

### 4. 标签处理函数

#### `label_replace(v, dst_label, replacement, src_label, regex)`

```promql
# 把 instance="10.0.0.1:9100" 拆出 host="10.0.0.1"
label_replace(
  up{job="node"},
  "host", "$1",
  "instance", "(.+):\\d+"
)
```

#### `label_join(v, dst_label, separator, src_label_1, src_label_2, ...)`

```promql
# 把 {a="x", b="y"} 合并成 {joined="x-y"}
label_join(up{job="node"}, "joined", "-", "a", "b")
```

### 5. 排序

```promql
sort(node_load5)             # 升序
sort_desc(node_load5)        # 降序
```

### 6. 缺失处理

```promql
# 当 node_load5 没有数据时返回 1
absent(node_load5)

# 当某 job 完全没上报时报警
absent(up{job="critical-service"})
```

---

## 五、聚合操作符(Aggregation Operators)

聚合把 instant vector 的多条序列聚合成更少的序列。

### 1. 基本聚合

| 聚合 | 含义 |
| --- | --- |
| `sum(v)` | 求和 |
| `avg(v)` | 平均 |
| `min(v)` | 最小 |
| `max(v)` | 最大 |
| `count(v)` | 计数 |
| `stddev(v)` | 标准差 |
| `stdvar(v)` | 方差 |
| `topk(k, v)` | 前 K 大(返回 K 条样本) |
| `bottomk(k, v)` | 后 K 小 |
| `quantile(φ, v)` | φ 分位数(0~1) |
| `count_values("label", v)` | 按值分组计数 |

### 2. by / without 子句

控制聚合时保留哪些 label:

```promql
# 按 instance 聚合
sum by (instance) (rate(http_requests_total[5m]))

# 删除某些 label 再聚合
sum without (instance, pod) (rate(http_requests_total[5m]))

# 计算 P99 延迟
quantile by (path) (0.99, rate(http_request_duration_seconds_sum[5m])
                         / rate(http_request_duration_seconds_count[5m]))
```

---

## 六、二进制运算符的标签匹配

二元运算符两侧都是 instant vector 时,默认按 **所有 label 相同** 才匹配。可以通过以下修饰符调整:

### `on(label_list)` 和 `ignoring(label_list)`

- `on`:只匹配指定 label。
- `ignoring`:忽略指定 label,其他都匹配。

```promql
# 计算每 instance 的内存使用率
node_memory_MemAvailable_bytes / on(instance) node_memory_MemTotal_bytes
```

### `group_left` / `group_right`

当两侧的 cardinality 不一致时(左侧一对一右侧多对多),用 `group_left` 或 `group_right` 拼接:

```promql
# 把 k8s pod 信息 join 到 metric 上
kube_pod_info * on (pod) group_left(namespace, node) kube_pod_status_phase

# 左侧多条 + 右侧多条,用 group_left 选左侧
sum(rate(http_requests_total[5m])) by (pod)
  * on(pod) group_left(namespace) kube_pod_info
```

> `group_left(label_list)` 还能给左侧添加额外的标签。

---

## 七、直方图与分位数

Prometheus 直方图(Histogram)是基于 bucket 估算分位数的近似算法。

### 直方图核心指标(以 Go HTTP 为例)

```promql
http_request_duration_seconds_bucket{le="0.005"}   # ≤5ms 的请求数
http_request_duration_seconds_bucket{le="0.01"}    # ≤10ms
http_request_duration_seconds_bucket{le="+Inf"}    # 总数
http_request_duration_seconds_sum                  # 总耗时(秒)
http_request_duration_seconds_count                # 总请求数
```

### `histogram_quantile(φ, b)`

```promql
# 过去 5 分钟 P99 延迟
histogram_quantile(0.99,
  sum by (le, path) (
    rate(http_request_duration_seconds_bucket[5m])
  )
)

# 过去 5 分钟 P50
histogram_quantile(0.5,
  rate(http_request_duration_seconds_bucket[5m])
) by (path)
```

> ⚠️ **必须** 先按 `le` 聚合再求分位数,否则不同 instance 的 bucket 会混在一起。

### 平均响应时间

```promql
# 总耗时 / 总请求数
rate(http_request_duration_seconds_sum[5m])
  /
rate(http_request_duration_seconds_count[5m])
```

### `histogram_count` 与 `histogram_sum`

对于 native histogram(在 Prometheus 2.40+):

```promql
histogram_count(http_request_duration_seconds)   # 总样本数
histogram_sum(http_request_duration_seconds)     # 总和
```

---

## 八、常见查询实战

### 1. CPU 使用率

```promql
# 单核 CPU 非空闲时间(0~1)
rate(node_cpu_seconds_total{mode!="idle"}[5m])

# 多核总占用(0~核心数)
sum by (instance) (rate(node_cpu_seconds_total{mode!="idle"}[5m]))

# 单核归一化(0~1)
sum by (instance) (rate(node_cpu_seconds_total{mode!="idle"}[5m]))
  /
count by (instance) (node_cpu_seconds_total{mode="idle"})
```

### 2. 内存使用率

```promql
# (Total - Available) / Total
1 - (
  node_memory_MemAvailable_bytes
  /
  node_memory_MemTotal_bytes
)
```

### 3. 磁盘使用率

```promql
1 - (
  node_filesystem_avail_bytes{fstype!~"tmpfs|overlay"}
  /
  node_filesystem_size_bytes{fstype!~"tmpfs|overlay"}
)
```

### 4. HTTP QPS

```promql
sum(rate(http_requests_total[5m]))
```

### 5. HTTP 错误率

```promql
# 5xx 比例
sum(rate(http_requests_total{status=~"5.."}[5m]))
  /
sum(rate(http_requests_total[5m]))
```

### 6. P99 延迟(直方图)

```promql
histogram_quantile(0.99,
  sum by (le, path) (rate(http_request_duration_seconds_bucket[5m]))
)
```

### 7. Apdex 指数

Apdex = (satisfied + tolerating/2) / total

```promql
(
  sum(rate(http_request_duration_seconds_bucket{le="0.3"}[5m]))
  +
  sum(rate(http_request_duration_seconds_bucket{le="1.2"}[5m])) / 2
)
/
sum(rate(http_request_duration_seconds_count[5m]))
```

### 8. 服务可用性

```promql
# 假设 1 分钟内至少一个样本为 1
avg_over_time(up{job="api"}[5m])
```

### 9. K8s Pod 重启次数

```promql
increase(kube_pod_container_status_restarts_total[1h])
```

### 10. 容器 CPU 使用率

```promql
# 容器实际使用 / 限额
rate(container_cpu_usage_seconds_total[5m])
  /
container_spec_cpu_quota / container_spec_cpu_period
```

---

## 九、聚合时长函数(`_over_time`)

把 range vector 在时间维度上聚合为 instant vector,与上面 rate/irate 不同,这些函数不计算增长:

| 函数 | 说明 |
| --- | --- |
| `avg_over_time(v)` | 平均 |
| `sum_over_time(v)` | 求和 |
| `min_over_time(v)` | 最小 |
| `max_over_time(v)` | 最大 |
| `count_over_time(v)` | 样本数 |
| `quantile_over_time(φ, v)` | φ 分位数 |
| `stddev_over_time(v)` | 标准差 |
| `last_over_time(v)` | 最后一个值 |
| `present_over_time(v)` | 1(只要有样本) |

**典型用法**:统计一小时内的 P99:

```promql
quantile_over_time(0.99,
  http_request_duration_seconds_bucket{le="0.5"}[1h]
)
```

> `quantile_over_time` 只能基于单个序列的分位数,不能跨多条序列。

---

## 十、子查询(Subquery)

在方括号内嵌套 PromQL 表达式,本质是按子步长计算再聚合:

```promql
# 过去 1 小时每 1 分钟计算一次 P99
max_over_time(
  quantile_over_time(0.99,
    rate(http_request_duration_seconds_bucket[5m])[1h:1m]
  )
)
```

> 注意是 `[1h:1m]` 形式:**总时长:子步长**。会增加 Prometheus 负担,谨慎使用。

---

## 十一、常见陷阱与最佳实践

### 1. 避免高基数

```promql
# ❌ 错误:可能引入 label 维度的 cardinality 爆炸
some_metric{user_id="..."}

# ✅ 正确:把高基数维度放 metric 名或 metric label 中限定
sum(rate(http_requests_total[5m])) by (api, status)
```

### 2. rate() 窗口选择

- 4 个采样点为最低要求:采集间隔 15s,rate 窗口 ≥ 1m;采集间隔 30s,rate 窗口 ≥ 2m。
- 推荐:`rate(metric[5m])` 或 `rate(metric[4m])`。

### 3. histogram_quantile 之前要聚合

```promql
# ❌ 错误
histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))

# ✅ 正确(按 le 和分组维度聚合)
histogram_quantile(0.99,
  sum by (le, path) (rate(http_request_duration_seconds_bucket[5m]))
)
```

### 4. 不要用 increase() 跨重置时间

`increase()` 内部使用 `rate`,能处理 counter 重置,但短窗口(< 1m)误差大。

### 5. 即时向量比较的过滤语义

```promql
# 过滤掉不等于 1 的(返回的 vector 不含不等于 1 的)
up == 1

# 想保留所有时间序列,值为 0/1
up == bool 1
```

### 6. 避免在 metric name 上做正则

```promql
# ❌ 性能差
{__name__=~"http_.*_total"}

# ✅ 改用精确匹配或显式多选
{__name__="http_requests_total"}
```

### 7. 函数式指标比较

```promql
# CPU 使用率 > 80% 的实例(过滤语义)
sum by (instance) (rate(node_cpu_seconds_total[5m])) > 0.8

# 找 top N
topk(3, sum by (instance) (rate(node_cpu_seconds_total[5m])))
```

---

## 十二、@ 时间戳修饰符

指定查询的求值时间(用于回填查询):

```promql
# 在某个时间点的瞬时值
http_requests_total @ 1600000000

# 在某个时间点的 5m 范围
rate(http_requests_total[5m] @ 1600000000)
```

> 多用于 Prometheus 的 federate / replay。

---

## 十三、Grafana 中的模板变量

| 变量 | 说明 |
| --- | --- |
| `$__interval` | 自适应步长 |
| `$__range` | 时间范围(秒) |
| `$__from` / `$__to` | 起止时间(毫秒) |
| `label_values(metric, label)` | 取 label 的所有值 |
| `query_result(promql)` | 内嵌查询的结果 |
| `metrics(prefix)` | 自动匹配指标名 |

### 模板变量示例

```promql
# 在变量配置中,获取 job 的所有值
label_values(up, job)

# 多级变量
label_values(kube_pod_info{namespace="$namespace"}, pod)
```

---

## 十四、HTTP API 直接调用

Prometheus 提供 HTTP API:

```bash
# 瞬时查询
curl 'http://prom:9090/api/v1/query?query=up' | jq .

# 范围查询(从 2026-06-25T00:00:00Z 到 2026-06-25T01:00:00Z,步长 30s)
curl 'http://prom:9090/api/v1/query_range?query=up&start=2026-06-25T00:00:00Z&end=2026-06-25T01:00:00Z&step=30s' | jq .

# 元数据查询
curl 'http://prom:9090/api/v1/metadata' | jq .
```

---

## 十五、参考资料

- [Prometheus 官方文档 — Querying](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Prometheus 函数索引](https://prometheus.io/docs/prometheus/latest/querying/functions/)
- [Prometheus 官方示例](https://github.com/prometheus/prometheus/blob/main/docs/querying/examples.md)
- [PromQL 备忘单(Grafana Labs)](https://promlabs.com/promql-cheat-sheet/)
- [Brendan Gregg 性能图表解读](https://www.brendangregg.com/usemethod.html)
- 《Prometheus 监控实战》 — James Turnbull(书籍)