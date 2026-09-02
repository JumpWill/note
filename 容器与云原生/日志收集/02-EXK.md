# E(L|F)K —— Elasticsearch + (Logstash | Fluentd | Filebeat) + Kibana

> K8s 上**最经典**的日志栈。三种写法：**ELK**（Elastic 官方栈，Logstash 收日志）、**EFK**（CNCF 偏好的 Fluentd）、**ECK**（Elastic Cloud on Kubernetes，Operator 一键装整套）。
> 适合：**必须全文检索 + 复杂聚合 + 长期合规存储** 的场景。代价：**资源重、运维重、贵**。

---

## 一、命名解释

```text
ELK  = Elasticsearch + Logstash + Kibana       （Logstash 是 JVM 重量级 shipper）
EFK  = Elasticsearch + Fluentd + Kibana        （Fluentd 是 Ruby 中量级 shipper）
EXK  = Elasticsearch + X + Kibana              （X 可替换）

X 还有别的选择：
  - Filebeat（Elastic 官方轻量 shipper，Go 写的）⭐ K8s 上主流
  - Fluent Bit（C 写，比 Fluentd 更轻）
```

**实际生产组合（2026 年推荐）**：
- **E + Filebeat + K** —— Elastic 官方，资源最省
- **E + Fluent Bit + K** —— CNCF 偏好的非 Elastic 栈
- **ECK（Operator）** —— 任何上面的组合 + Operator 一键管理

---

## 二、架构对比

### 2.1 ELK（传统）

```text
┌──────────┐   ┌──────────┐   ┌──────────────┐   ┌────────┐
│  Beats   │──►│ Logstash │──►│Elasticsearch │──►│ Kibana │
│ Filebeat │   │ (JVM 过滤) │   │   集群        │   │ 可视化  │
└──────────┘   └──────────┘   └──────────────┘   └────────┘
                              ▲
                              │ Curator / ILM（保留策略）
```

### 2.2 EFK

```text
┌────────────┐   ┌──────────┐   ┌──────────────┐   ┌────────┐
│ Fluent Bit │──►│ Fluentd  │──►│Elasticsearch │──►│ Kibana │
│ (DaemonSet)│   │ (聚合/过滤)│   │   集群        │   │ 可视化  │
└────────────┘   └──────────┘   └──────────────┘   └────────┘
```

### 2.3 K8s 实际推荐：Filebeat/Fluent Bit 直推 ES（去掉中间层）

```text
Node (DaemonSet)
  └─ Filebeat / Fluent Bit ──► Elasticsearch ──► Kibana
```

> **去掉 Logstash / Fluentd 中间层**：业务简单时多一跳只是耗资源、增故障点。**90% 场景 DaemonSet 直推 ES 就够**。

---

## 三、三个 Shipper 对比

| 维度 | **Filebeat** ⭐ | **Fluent Bit** | **Fluentd** | Logstash |
| --- | --- | --- | --- | --- |
| 语言 | Go | C | Ruby（C 核心） | JRuby（JVM） |
| 内存占用 | ~100MB | ~30MB | ~200MB | ~500MB–1GB |
| CPU | 低 | 极低 | 中 | 高 |
| K8s 友好度 | 极高（官方 module） | 极高 | 中 | 低 |
| 插件生态 | Elastic 生态 | 庞大 | 庞大 | Elastic 生态 |
| 过滤能力 | 弱（beats processor） | 中（Lua filter） | 强 | 极强 |
| 启动速度 | 秒级 | 毫秒级 | 较慢 | 慢（JVM） |
| 多路输出 | ✅ | ✅ | ✅ | ✅ |
| 背压处理 | 内置（harvester queue） | 内置（storage plugin） | 内置 | buffer plugin |

**结论**：
- K8s **首选 Filebeat**（与 Elastic 栈无缝、与 ES ILM/Kibana 一体）
- 多源异构、不想绑定 Elastic → **Fluent Bit**
- 必须 Ruby 插件 / 超复杂解析 → **Fluentd**
- **不要**用 Logstash 做 K8s 边车（资源太重）

---

## 四、安装方式

### 方式 A：ECK（Elastic Cloud on Kubernetes）⭐ 推荐

Elastic 官方 Operator，一键装 ES + Kibana + APM + Beats，支持证书、自动伸缩、升级。

```bash
# 1. 装 Operator
kubectl apply -f https://download.elastic.co/downloads/ecm/operator-installer.yaml

# 2. 装 ES 集群
cat <<EOF | kubectl apply -f -
apiVersion: elasticsearch.k8s.elastic.co/v1
kind: Elasticsearch
metadata:
  name: elasticsearch
  namespace: logging
spec:
  version: 8.15.0
  nodeSets:
    - name: master
      count: 3
      config:
        node.roles: ["master"]
      podTemplate:
        spec:
          resources:
            requests: { cpu: 1, memory: 4Gi }
            limits:   { cpu: 2, memory: 8Gi }
      volumeClaimTemplates:
        - metadata: { name: elasticsearch-data }
          spec:
            storageClassName: ssd
            resources: { requests: { storage: 50Gi } }
    - name: data
      count: 3
      config:
        node.roles: ["data", "ingest"]
      podTemplate:
        spec:
          resources:
            requests: { cpu: 4, memory: 16Gi }
            limits:   { cpu: 8, memory: 32Gi }
      volumeClaimTemplates:
        - metadata: { name: elasticsearch-data }
          spec:
            storageClassName: ssd
            resources: { requests: { storage: 500Gi } }
EOF

# 3. 装 Kibana
cat <<EOF | kubectl apply -f -
apiVersion: kibana.k8s.elastic.co/v1
kind: Kibana
metadata:
  name: kibana
  namespace: logging
spec:
  version: 8.15.0
  count: 1
  elasticsearchRef:
    name: elasticsearch
  http:
    tls:
      selfSignedCertificate: { disabled: true }
EOF
```

### 方式 B：Helm chart（更灵活）

```bash
helm repo add elastic https://helm.elastic.co
helm install elasticsearch elastic/elasticsearch -n logging
helm install kibana        elastic/kibana        -n logging
helm install filebeat      elastic/filebeat      -n logging
```

### 方式 C：裸 manifest（不推荐）

ES 配置项几百个，手写易出错。仅在极特殊定制场景用。

---

## 五、Filebeat K8s 配置（核心）

### 5.1 启动方式：DaemonSet 自动挂载

```yaml
# elastic/filebeat helm chart 自带 DaemonSet
# 关键 volumeMounts：
volumeMounts:
  - name: var-lib-containers
    mountPath: /var/log/containers
  - name: var-lib-containers-pods
    mountPath: /var/log/pods
  - name: var-lib-docker-containers
    mountPath: /var/lib/docker/containers
  - name: filebeat-config
    mountPath: /usr/share/filebeat/config
```

### 5.2 filebeat.yml（K8s 模式）

```yaml
filebeat.inputs:
  - type: container
    paths:
      - /var/log/containers/*.log
    processors:
      - add_kubernetes_metadata:
          host: ${NODE_NAME}
          matchers:
            - logs_path:
                logs_path: /var/log/containers/

# 输出：直推 ES
output.elasticsearch:
  hosts: ["${ELASTICSEARCH_HOSTS:elasticsearch-master:9200}"]
  username: "${ELASTICSEARCH_USERNAME:elastic}"
  password: "${ELASTICSEARCH_PASSWORD}"
  ssl:
    verification_mode: none          # 自签证书时，生产改 full

# 索引模板：按日期滚动
setup.template.name: "logs"
setup.template.pattern: "logs-*"
setup.ilm.enabled: true              # 启用 ILM
setup.ilm.policy_file: /etc/filebeat/ilm-policy.json

# 内部监控
monitoring.enabled: true             # 输出 metrics 到 ES
```

### 5.3 ILM 策略（生命周期管理，**生产必做**）

```json
{
  "policy": {
    "phases": {
      "hot": {
        "min_age": "0ms",
        "actions": {
          "rollover": {
            "max_age": "1d",        # 1 天滚动
            "max_size": "50gb"      # 单索引 50GB
          },
          "set_priority": { "priority": 100 }
        }
      },
      "warm": {
        "min_age": "3d",
        "actions": {
          "shrink": { "number_of_shards": 1 },
          "forcemerge": { "max_num_segments": 1 },
          "set_priority": { "priority": 50 }
        }
      },
      "cold": {
        "min_age": "7d",
        "actions": {
          "freeze": {},
          "set_priority": { "priority": 0 }
        }
      },
      "delete": {
        "min_age": "30d",
        "actions": { "delete": {} }
      }
    }
  }
}
```

---

## 六、Fluent Bit 配置（EFK 路线）

### 6.1 ConfigMap 核心配置

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: fluent-bit-config
  namespace: logging
data:
  fluent-bit.conf: |
    [SERVICE]
      Flush        5
      Log_Level    info
      Daemon       off
      Parsers_File  parsers.conf

    [INPUT]
      Name              tail
      Path              /var/log/containers/*.log
      Parser            docker
      Tag               kube.*
      Refresh_Interval  10
      DB                /var/lib/fluent-bit/pos.db

    [FILTER]
      Name                kubernetes
      Match               kube.*
      Kube_URL            https://kubernetes.default.svc:443
      Kube_CA_File        /var/run/secrets/kubernetes.io/serviceaccount/ca.crt
      Kube_Token_File     /var/run/secrets/kubernetes.io/serviceaccount/token
      Merge_Log           On          # 多行合并
      Keep_Log            On
      K8S-Logging.Parser  On
      K8S-Logging.Exclude On

    [OUTPUT]
      Name            es
      Match           *
      Host            elasticsearch-master.logging.svc
      Port            9200
      Index           logs
      Type            _doc
      Logstash_Format On
      Logstash_Prefix k8s            # 索引名：k8s-2026.09.01
```

### 6.2 与 ES 的接入

Fluent Bit 的 `[OUTPUT] es` 插件：
- 自动按日切索引（`k8s-YYYY.MM.DD`）
- 支持 ILM（`Index_Lifecycle_Policy_Name`）
- 比 Filebeat 灵活，但 K8s 元数据注入需要靠 filter plugin

---

## 七、Kibana 使用

### 7.1 入口访问

```bash
# port-forward（开发用）
kubectl port-forward -n logging svc/kibana-kibana 5601:5601

# 生产用 Ingress
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: kibana
  namespace: logging
spec:
  rules:
    - host: kibana.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service: { name: kibana-kibana, port: { number: 5601 } }
```

### 7.2 常用 Kibana 操作

| 操作 | 路径 |
| --- | --- |
| 创建 Index Pattern | Stack Management → Index Patterns → `k8s-*` |
| Discovery 查询 | Discover → 选 index pattern → KQL 或 Lucene |
| 可视化 | Visualize → Lens（推荐）/ TSVB / Vega |
| Dashboard | Dashboard → 把多个可视化拼一起 |
| 告警 | Stack Management → Rules → Elasticsearch query |
| APM / 监控 | Observability → Logs / Metrics / APM / Uptime |

### 7.3 KQL 常用查询（Kibana Query Language）

```text
kubernetes.namespace: "prod" and log.level: "error"
kubernetes.pod.name: "order-api-*" and message: "timeout"
@timestamp >= "now-1h" and http.response.status_code >= 500
kubernetes.labels.app: "payment" and not message: "health check"
```

---

## 八、生产必做的配置

### 8.1 资源规划（核心：内存）

ES JVM heap 推荐 **≤ 物理内存的 50%**（超过 32GB 反而性能下降）；单节点最大堆 **32GB**。

```text
小规模 (< 100 节点 / < 50GB/天):  3 master + 3 data(8GB heap, 32GB RAM) + 1 Kibana
中规模 (100–500 节点 / 50–500GB/天): 3 master + 5 data(16GB heap, 64GB RAM) + 2 Kibana
大规模:  引入 Coordinating / Ingest / Hot-Warm 分离
```

### 8.2 分片设计（生产关键）

```text
shard 数建议：单 shard 10–50GB，最大 100GB
replica 数：1 起步，重要索引 2

# 举例：500GB/天、单 shard 50GB
   主分片 = 10，副本 = 1 → 总 shard = 20
   data 节点 3 个 → 每节点 ~7 个 shard

# 检查分片均衡
GET _cat/shards?v&h=index,shard,prirep,state,unassigned.reason
```

> ⚠️ **分片一旦定下不能改**——必须用 **Rollover API** 或 **reindex** 才能调整。
> 早期按日滚（每天一索引）+ 1 主 1 副 是最稳的起步。

### 8.3 冷热分离（Hot-Warm-Cold）

```text
Hot 节点（NVMe SSD）→ 写 + 最近 3 天查询
Warm 节点（普通 SSD）→ 3–7 天查询（force merge + shrink）
Cold 节点（HDD）→ 7–30 天（freeze 索引，内存不加载）
```

通过 ILM 自动迁移 tier，**省 60%+ 存储成本**。

### 8.4 安全（必做）

ECK 默认开安全：

```yaml
# 自动生成 elastic 用户密码
PASSWORD=$(kubectl get secret elasticsearch-es-elastic-user -n logging -o jsonpath='{.data.elastic}' | base64 -d)
echo $PASSWORD

# 创建只读用户给业务方
PUT _security/role/logs_reader
{
  "indices": [
    {
      "names": ["k8s-*"],
      "privileges": ["read", "view_index_metadata"]
    }
  ]
}
```

### 8.5 备份（Elasticsearch Snapshot）

```yaml
# 1. 配置 S3 仓库（minio / OSS / S3）
cat <<EOF | kubectl apply -f -
apiVersion: elasticsearch.k8s.elastic.co/v1
kind: Elasticsearch
metadata:
  name: elasticsearch
spec:
  snapshotRepositories:
    - name: s3-backup
      type: s3
      settings:
        bucket: es-snapshots
        endpoint: s3.amazonaws.com
        access_key: xxx
        secret_key: yyy
EOF

# 2. SLM 策略：每天快照，保留 7 天
PUT _slm/policy/daily-snapshots
{
  "schedule": "0 0 2 * * ?",
  "name": "<daily-{now/d}>",
  "repository": "s3-backup",
  "retention": { "expire_after": "7d" }
}
```

---

## 九、Filebeat vs Fluent Bit 选哪个

| 场景 | 推荐 |
| --- | --- |
| 已经用 Elastic 全家桶（ES/Kibana/APM） | **Filebeat** —— 一体化体验 |
| 不想绑定 Elastic，可能要换 Loki/SLS | **Fluent Bit** —— 中立 |
| 多云混合（同时推 ES / Loki / S3） | **Fluent Bit** —— 多 output 灵活 |
| 节点 < 100，资源紧张 | **Fluent Bit** —— 内存少一半 |
| 业务日志复杂解析（多行 + regex 重） | 两者都行，Filebeat processor 略弱 |
| 已经装 Fluentd 做集中处理 | 节点用 **Fluent Bit**（轻），中心用 Fluentd（功能强） |

**绝大多数 K8s 生产**：Filebeat 或 Fluent Bit **二选一即可**。

---

## 十、E(L|F)K vs Loki（什么时候用哪个）

| 维度 | E(L\|F)K | Loki |
| --- | --- | --- |
| 全文检索 | ✅ 强 | ⚠️ 弱（基于标签过滤 + LogQL 简单匹配） |
| 大文本检索（grep 长字符串） | ✅ | ❌（grep 全文要拉整段日志，巨慢） |
| 标签查询性能 | 一般（索引大） | 极快（无索引） |
| 存储成本 | **高**（建索引） | **低 5–10×**（不建索引） |
| 运维复杂度 | **高**（分片 / ILM / 调参） | **低**（单二进制起步） |
| Kibana 可视化 | ✅ 极强 | ⚠️ 中等（Grafana 还行） |
| 实时聚合（count/sum） | ✅ aggregations | ✅ LogQL |
| 适合业务 | 金融/医疗合规、深度分析 | 日常运维、K8s 日志、容量大 |

**决策**：
- **要全文搜** → E(L|F)K
- **只要标签 + 时间过滤** → Loki
- **预算敏感** → Loki
- **已有 Elastic 栈** → 直接扩 E(L|F)K
- **两者都要**？很多公司 E(L|F)K 跑核心、Loki 跑 K8s 日志，**并行部署**

---

## 十一、运维常用命令

```bash
# ES 健康
curl -u elastic:$PASSWORD https://elasticsearch:9200/_cluster/health?pretty

# 索引列表
curl -u elastic:$PASSWORD https://elasticsearch:9200/_cat/indices?v

# 删除老索引
curl -u elastic:$PASSWORD -XDELETE https://elasticsearch:9200/k8s-2026.08.*

# Filebeat 状态
kubectl exec -n logging <filebeat-pod> -- filebeat test output
kubectl exec -n logging <filebeat-pod> -- filebeat test config

# Filebeat 内部日志（debug）
kubectl logs -n logging <filebeat-pod> -c filebeat --tail 100

# Fluent Bit 内部指标（暴露端口 2020）
kubectl port-forward <fb-pod> 2020:2020
curl localhost:2020/api/v1/metrics

# ES 索引模板查询
GET _index_template/logs
```

---

## 十二、踩坑清单

| 现象 | 原因 |
| --- | --- |
| ES 集群 red | 分片未分配（磁盘满 / 节点挂），查 `_cluster/allocation/explain` |
| ES OOM | JVM heap 太大 → 改 `ES_JAVA_OPTS=-Xms16g -Xmx16g`；数据节点内存至少给 32GB |
| Kibana 打不开 | ES 没起来 / 网络不通 / 证书不匹配 |
| Filebeat 抓不到日志 | 没挂 `/var/log/containers` 或 RBAC 权限缺 |
| ILM 没生效 | `setup.ilm.enabled` 没开 / 索引模板没生效 / 用错了 phase |
| 索引越来越大没分片 | ILM 没配 / rollover 没触发；查 `GET k8s-*/_settings` |
| 全文搜索超慢 | 跨太多 shard → 调大 max shards 或减少索引数 |
| Filebeat 卡住 / 内存涨 | `harvester_limit` 没限制 → 节点日志文件太多 |
| ES 写入 429 | 队列满 / bulk size 太大 → 调小 `bulk_max_size` |
| Kibana 索引模式看不到 `kubernetes.*` | Filebeat 没加 `add_kubernetes_metadata` processor |

---

## 十三、最佳实践

1. **生产用 ECK**：自动证书 / 自动升级 / 自动伸缩，比裸装省心 10 倍
2. **节点分角色**：master / data / ingest / coordinating 分离，**不要全堆一起**
3. **冷热分层**：Hot SSD + Warm SATA + Cold HDD，存储成本直接砍半
4. **ILM 必开**：按日 rollover → warm 3d → cold 7d → delete 30d
5. **索引命名规范**：`{app}-{env}-{YYYY.MM.DD}`，便于按业务路由和清理
6. **监控 ES 自己**：用 Elastic 自带的 Stack Monitoring 或 Prometheus exporter
7. **权限分级**：elastic 管理员 / logs_reader 只读 / kibana_only 只看
8. **Filebeat/Fluent Bit 资源限制**：requests 必须设，limits 给 2× 弹性
9. **不要让 ES 当业务数据库**：聚合慢 / 写慢 / 不擅长 join
10. **定期 reindex**：换 mapping → 老索引 reindex 到新索引（**mapping 不能改**）

---

## 十四、参考

- [Elastic Cloud on Kubernetes 官方](https://www.elastic.co/guide/en/cloud-on-k8s/current/index.html)
- [Filebeat Kubernetes 输入](https://www.elastic.co/guide/en/beats/filebeat/current/kubernetes-input.html)
- [Fluent Bit Elasticsearch 输出插件](https://docs.fluentbit.io/manual/pipeline/outputs/elasticsearch.html)
- [Elasticsearch ILM 文档](https://www.elastic.co/guide/en/elasticsearch/reference/current/index-lifecycle-management.html)
- [Kibana KQL 语法](https://www.elastic.co/guide/en/kibana/current/kuery-query.html)
