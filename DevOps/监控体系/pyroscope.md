# Pyroscope

Grafana Labs 主导的开源持续剖析（Continuous Profiling）平台。已并入 Grafana Phlare 并向 Pyroscope Schema 演进。提供持续的 CPU / 内存 / 锁 / IO 等火焰图数据。

## 一、定位

- 持续剖析（生产环境持续采集）
- 极低开销（< 1% CPU / 内存在大多数情况）
- 拉（Pull） 模式：Pyroscope server 反向连接 agent
- 多语言 agent：Go / Java / Python / Node.js / Rust / eBPF
- 火焰图与 trace 关联

## 二、原理

```text
Agent（注入 / 进程内 / eBPF）
   │
   │ 周期性上传栈帧
   ▼
Pyroscope Server
   ├── Storage：good-storage（in-memory + 对象存储）
   ├── Read Path
   └── Badger / BoltDB 用于索引
   │
   ▼
Grafana（UI / Explore / Trace → Profile）

应用 Profile 与 Trace：
- 通过 Exemplars（trace_id → profile）
- 通过 label 关联
```

### 1. 数据模型

```text
Service / Application
   ├── Tag (service_name, env, region, ...)
   ├── Sample Type (cpu, memory, goroutines, inuse_objects, ...)
   └── Time Series（按时间分桶）
```

每个 sample 是带时间戳的栈帧数据。

### 2. Tag

- 服务名（必填）
- 环境（prod / staging）
- 区域
- 自定义 tag（业务参数）

## 三、采集模式

### 1. Embed mode（应用内）

```go
import "github.com/grafana/pyroscope-go"

pyroscope.Start(pyroscope.Config{
    ApplicationName: "order-svc",
    ServerAddress:   "http://pyroscope:4040",
    Tags: map[string]string{
        "env":     "prod",
        "region":  "cn-shanghai",
        "version": "1.2.3",
    },
    ProfileTypes: []pyroscope.ProfileType{
        pyroscope.ProfileCPU,
        pyroscope.ProfileInuseObjects,
        pyroscope.ProfileInuseSpace,
        pyroscope.ProfileAllocObjects,
        pyroscope.ProfileAllocSpace,
        pyroscope.ProfileGoroutines,
    },
})
defer pyroscope.Stop()
```

### 2. Pull Mode（Server 主动拉）

```yaml
scrape_config:
  - job_name: pyroscope-agent
    pyroscope_configs:
      - job_name: app
        auth:
          username: ...
        scrape_interval: 15s
        scrape_timeout: 10s
        service_name: order-svc
        tags:
          env: prod
        scheme: http
```

### 3. eBPF mode（Pyroscope-ebpf）

- 不需要重打包应用
- 内核采集进程 CPU 栈
- 适合语言探针未覆盖的程序（如 C/C++）

### 4. Pyroscope Operator（K8s）

- DaemonSet 部署 eBPF
- 自动服务发现

## 四、SDK 集成

### 1. Go

```go
profiler.Start(profiler.Config{
    ApplicationName: "api",
    ServerAddress:   "http://pyroscope:4040",
    UploadRate:      10 * time.Second,
})
defer profiler.Stop()
```

### 2. Python

```python
import pyroscope

pyroscope.configure(
    application_name="myapp",
    server_address="http://pyroscope:4040",
    sample_rate=100,
)
```

### 3. Java

通过 JFR（Java Flight Recorder）：

```bash
java -XX:+UnlockDiagnosticVMOptions \
     -XX:+DebugNonSafepoints \
     -XX:+StartFlightRecording=duration=0s,maxsize=200m \
     -jar app.jar
```

Pyroscope JFR reader 周期性拉。

### 4. Node.js

```js
require('@pyroscope/nodejs').start({
  appName: 'myapp',
  serverAddress: 'http://pyroscope:4040',
})
```

### 5. Rust / .NET

类似。

## 五、查询与可视化

### 1. Grafana 数据源

```yaml
type: grafana-pyroscope-datasource
url: http://pyroscope:4040
```

### 2. Profile 视图

- 火焰图（flamegraph）
- Top 表
- 区域选择

UI：

```text
Service: order-svc
Tag: env=prod, region=cn-shanghai
Sample Type: CPU / inuse_objects / inuse_space

Time Range: last 1 hour
Aggregation: sum by function / sum by file:line
```

### 3. Diff

两个不同时间片或标签的火焰图 diff。

## 六、Trace → Profile 关联

- 通过 Exemplars
- Tempo trace span 上加 exemplars
- Pyroscope 显示对应火焰图

```yaml
# OTel Collector exporter
exporters:
  otlphttp/pyroscope:
    endpoint: http://pyroscope:4040
```

通过 [OpenTelemetry Log → Profile]，将 trace ID 嵌入 profile label。

## 七、组件架构

```text
Pyroscope server
├── ingest server
├── read server
├── compactor
├── store-gateway
├── querier
└── admin / UI
```

- 单体部署（默认 / `pyroscope server`）
- 微服务按服务划分
- 部署建议：使用 [Grafana Pyroscope operator](https://github.com/grafana-operator) / Grafana Cloud

## 八、存储

| Backend | 适用 |
| ------- | ---- |
| **local** | 嵌入式存储（sdb） |
| **S3** | 生产 |
| **GCS** | GCP |
| **Azure Blob** | Azure |

推荐使用对象存储分级：

- Hot：SDB / Badger 内存 / 临时盘
- Cold：对象存储 + 分块压缩

## 九、与 Grafana Phlare 关系

Phlare 现在是 Pyroscope Schema：

- Phlare 已经重命名为 Pyroscope
- 已统一格式
- 商业版为 Grafana Cloud Profiles

## 十、典型用法

### 1. 找内存泄漏

```text
Inuse Memory 标签不同分支
   │
   ├─ 主分支
   └─ 异常分支
火焰图 → 找到 allocator
```

### 2. 找 CPU 瓶颈

```text
CPU 时间分布 → 谁占最大时间 → 火焰图细节
```

### 3. 锁竞争

```text
锁等待火焰图 → 链而下的瓶颈
```

## 十一、与 Parca / async-profiler 对比

| 工具 | 模型 | 语言 | 适合 |
| ---- | ---- | ---- | ---- |
| **Pyroscope** | 服务 + Agent | 多 | 持续剖析 |
| **Parca** | 多 | 多 | 持续剖析 |
| **async-profiler** | 单库 | Java | 临时剖析 |
| **perf + FlameGraph** | 命令行 | C 系列 | 内核 |
| **bpftrace** | eBPF | C / 多语言 | 内核 |

## 十二、安全

- Auth / API Key
- TLS
- 多租户

## 十三、最佳实践

- **生产开启**：低开销
- **完整 label**：`service_name`, `env`, `region`, `version`
- **业务 tag**：关键客户 id
- **小粒度控制**：CPU / Memory / Allocations
- **追踪联动**：TraceID + Exemplar
- **资源**：对象存储可承受

## 十四、限制

- 采样精度：默认 100 Hz，可调
- 极短函数难采到：语言/平台固有限制
- CPU 火焰图常驻开销需注意
