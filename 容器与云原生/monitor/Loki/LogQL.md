# LogQL 使用语法

LogQL 是 Loki 的查询语言,语法上类似 PromQL,但专门用于日志查询。它由 **日志流选择器(Log Stream Selector)** 和 **日志管道(Log Pipeline)** 两部分组成,可以组合出非常强大的日志查询与聚合能力。

## 一、LogQL 基本结构

```logql
{log_stream_selector} | log_pipeline [ | log_pipeline ... ]
```

- **`{...}`**:日志流选择器,用于选择日志流(类似 SQL 的 FROM 子句)
- **`| ...`**:管道,用于对选中的日志流做进一步处理(过滤、解析、格式化)
- 没有管道部分时,返回原始日志;有管道部分时,可以过滤、解析、提取标签或计算指标

> 注:大括号和管道之间可以有空格,管道之间使用 `|` 分隔。

---

## 二、日志流选择器(Log Stream Selector)

日志流选择器用于匹配标签(label),每个标签都有 key 和 value,支持以下操作符:

| 操作符 | 含义       | 示例                       |
| ------ | ---------- | -------------------------- |
| `=`    | 完全相等   | `app="nginx"`              |
| `!=`   | 不相等     | `env!=prod`                |
| `=~`   | 正则匹配   | `level=~"warn\|error"`     |
| `!~`   | 正则不匹配 | `pod!~"test-.*"`           |

### 1. 完全匹配

```logql
{app="nginx", env="production"}
```

### 2. 正则匹配

```logql
{job=~"api|web"}
{namespace!~"kube-system|kube-public"}
```

> ⚠️ 正则使用 **RE2** 语法,且必须用双引号或反引号包裹。

### 3. 多个标签组合

多个标签之间是 **AND** 关系:

```logql
{app="mysql", env="prod", level="error"}
```

---

## 三、日志管道(Log Pipeline)

日志管道按顺序对日志流进行过滤、解析、重新打标签等操作,由三类操作符组成:

| 类型 | 操作符 | 作用 |
| --- | --- | --- |
| 行过滤表达式 | `\|=`, `!=`, `\|~`, `!~` | 对日志内容做文本过滤 |
| 解析器(Parser) | `\| json`、`\| logfmt` 等 | 把日志内容解析为键值对 |
| 标签格式化器 | `\| label_format`、`\| unwrap` | 对标签或日志内容进行格式化 |

### 1. 行过滤表达式(Line Filter)

行过滤器在日志内容上工作,操作符说明:

| 操作符 | 含义                                |
| ------ | ----------------------------------- |
| `|=`   | 日志行 **包含** 字符串              |
| `!=`   | 日志行 **不包含** 字符串            |
| `|~`   | 日志行 **正则匹配** 字符串          |
| `!~`   | 日志行 **正则不匹配** 字符串        |

```logql
# 包含 "error" 的行
{job="mysql"} |= "error"

# 不包含 "GET /health" 的行
{job="nginx"} != "GET /health"

# 正则匹配数字开头的行
{job="nginx"} |~ "^[0-9]+"

# 过滤掉健康检查日志
{job="nginx"} != "GET /health"
```

多个过滤条件之间是 **AND** 关系:

```logql
{app="nginx"} |= "error" != "info"
{app="nginx"} |= "error" |~ "user_id=[0-9]+"
```

### 2. 解析器(Parser)

解析器将日志内容解析成可查询的键值对。Loki 内置了四种常用解析器:

#### (1) JSON 解析器

最常用的解析器,将 JSON 格式日志转为可访问的字段:

```logql
# 解析 JSON,并过滤 status>=500 的请求
{app="nginx"} | json | status >= 500

# 多级嵌套字段
{app="nginx"} | json | http_user_agent="Mozilla/5.0"

# 数组索引(只能取数组最后一个元素)
{app="nginx"} | json | http_foo[0]="bar"
```

#### (2) logfmt 解析器

用于 key=value 格式的日志(如 Go 系统日志):

```logql
{app="go-service"} | logfmt | level="error"
```

#### (3) Pattern 解析器

通过自定义模式解析非结构化日志:

```logql
# 模式语法: <_> 表示任意字符,_<field_name> 表示捕获
{app="myapp"} | pattern "<_> level=<level> msg=<msg> <_>"

# 提取后即可过滤
{app="myapp"} | pattern "<_> level=<level> msg=<msg> <_>" | level="error"
```

#### (4) Regexp 解析器

使用正则表达式提取字段:

```logql
# (?P<name>...) 定义捕获字段
{app="myapp"} | regexp "(?P<method>\\w+) (?P<path>\\S+) (?P<status>\\d+)"

{app="myapp"} | regexp "(?P<method>\\w+) (?P<path>\\S+) (?P<status>\\d+)" | status="500"
```

### 3. 标签格式化器

#### (1) line_format — 修改日志内容

```logql
# 给日志行加上 prefix
{app="nginx"} | line_format "{{.status}} {{.method}} {{.path}}"

# 在 Grafana 中,通常用此函数渲染模板
{app="nginx"} | line_format `{{ __time__ | json }}`
```

> line_format 中可使用的内置函数:`__line__`、`__line_no__`、`__time__`、`__timestamp__` 等。

#### (2) label_format — 修改或新增标签

```logql
# 给每个日志流增加一个 env 标签
{app="nginx"} | label_format env="production"

# 引用已有的字段作为标签值
{app="nginx"} | json | label_format status_code="{{.status}}"
```

> 标签格式化后的值会被视为新的标签,在同一查询后续阶段可使用,但不会写回存储。

---

## 四、指标查询(Metric Queries)

LogQL 的最大特色是能通过日志流计算指标。语法是在日志管道后追加 **范围向量表达式**:

```logql
{log_stream_selector} | log_pipeline [ <range_vector_expression> ]
```

### 1. 范围向量函数

| 函数                          | 作用                            |
| ----------------------------- | ------------------------------- |
| `rate(<expr>[5m])`            | 每秒日志行数(类似 PromQL 的 rate) |
| `count_over_time(<expr>[5m])` | 时间窗口内日志行数              |
| `bytes_rate(<expr>[5m])`      | 每秒日志字节数                  |
| `bytes_over_time(<expr>[5m])` | 时间窗口内日志字节数            |
| `absent_over_time(<expr>[5m])`| 窗口内为空时返回 1              |

#### 示例

```logql
# 5 分钟内 nginx 的 QPS
rate({job="nginx"}[5m])

# 5 分钟内 error 级别日志数量
count_over_time({job="nginx"} |= "error" [5m])
```

> 注意:LogQL 中的时间单位支持 `s`,`m`,`h`,`d`,`w`,`y`。

### 2. 聚合操作(Aggregation Operators)

指标结果可以像 PromQL 一样做聚合:

| 函数          | 含义     |
| ------------- | -------- |
| `sum(...)`    | 求和     |
| `avg(...)`    | 平均     |
| `min(...)`    | 最小     |
| `max(...)`    | 最大     |
| `count(...)`  | 计数     |
| `stddev(...)` | 标准差   |
| `stdvar(...)` | 方差     |
| `topk(k,...)` | 前 K 大  |
| `bottomk(k,...)` | 后 K 大 |

#### 示例

```logql
# 按 status 分组的错误率(按秒计数)
sum by (status) (
  rate({job="nginx"}
    | json
    | status >= 400 [5m])
)

# Top 5 高频 IP
topk(5,
  sum by (client_ip) (
    rate({job="nginx"} | json [5m])
  )
)
```

### 3. unwrap — 解包数值字段

`unwrap` 是 Loki 的杀手级特性:把日志中的数值字段当作样本值,参与聚合计算:

```logql
# 计算 5 分钟内响应时间的平均值
avg_over_time({job="nginx"} | json | unwrap duration [5m])

# 计算 P99(用近似算法)
quantile_over_time(0.99,
  {job="nginx"} | json | unwrap duration [5m]
)

# 最大值
max_over_time({job="nginx"} | json | unwrap bytes [5m])
```

### 4. 数学与标签运算

```logql
# on(label) - 指定匹配的 group 标签
sum(rate({job="nginx"}[5m])) by (status)
    / on() group_left ()
sum(rate({job="nginx"}[5m]))

# 过滤指标结果
sum(rate({job="nginx"} | json | status=~"5.." [5m])) by (status) > 0.1

# 计算错误率
sum(rate({job="nginx"} | json | status=~"5.." [5m]))
/
sum(rate({job="nginx"} [5m]))

# 字节转 KB
sum(rate({job="nginx"} | json | unwrap bytes [5m])) / 1024
```

支持的运算符:`+`, `-`, `*`, `/`, `%`, `^`, `==`, `!=`, `>`, `>=`, `<`, `<=`, `and`, `or`, `unless`

---

## 五、Grafana 模板变量

在 Grafana 中配合下拉框使用,常见变量:

| 变量                | 含义                |
| ------------------- | ------------------- |
| `$__interval`       | 适配数据点间隔      |
| `$__range`          | 当前时间范围        |
| `$__from`, `$__to`  | 起止时间(毫秒)     |
| `{label_name}`      | 标签查询选择器      |
| `query_result(...)` | 内嵌查询返回的标签值 |

### label_values 函数

```logql
# 在变量查询中,获取 app 标签的所有值
label_values({cluster="prod"}, app)
```

---

## 六、常见查询示例

### 1. 错误日志聚合

```logql
sum(
  rate({app="myapp", level="error"}[5m])
) by (pod)
```

### 2. 慢请求 TOP10

```logql
topk(10,
  avg_over_time(
    {app="myapp"} | json | unwrap latency [5m]
  ) by (path)
)
```

### 3. 关键字 + 数值范围组合

```logql
{app="myapp"} | json | status="500" | method="POST"
```

### 4. 在线用户/IP 数(去重)

```logql
count(
  count_over_time(
    {app="myapp"} | json | unwrap user_id [5m]
  ) by (user_id)
)
```

---

## 七、使用建议与最佳实践

1. **先选择再过滤**:尽量在 `{...}` 中通过 label 选择器缩小范围,再使用管道做内容过滤,效率更高。
2. **避免在标签上做正则**:正则标签匹配(如 `app=~"nginx-.*"`)会扫描所有相关流,代价较高。
3. **JSON 字段优先**:能用 `| json` 解析的结构化日志,尽量不要用 `| regexp`。
4. **谨慎使用 `unwrap`**:数值字段需要确保类型一致,否则查询会报错。
5. **使用 `line_format` 调试**:在排查问题时,可以附加 `| line_format "{{.field}}"` 看到提取出的字段值。
6. **关注查询时间范围**:范围向量表达式 `[5m]` 中的窗口决定了内存计算量,窗口越大越慢。

---

## 八、参考资料

- [Loki 官方文档 — LogQL](https://grafana.com/docs/loki/latest/query/)
- [LogQL 语法详解(Grafana Labs 博客)](https://grafana.com/blog/2020/04/21/the-logql-book/)
- [Loki 官方查询示例](https://github.com/grafana/loki/tree/main/docs)