# 配置中心

按工具分文件整理配置中心原理与使用。

## 分类与索引

| 分类 | 工具 |
| --- | --- |
| **Java 生态专用配置中心** | [Nacos](nacos.md)、[Apollo](apollo.md)、[Spring Cloud Config](spring-cloud-config.md) |
| **通用 KV / 一致性存储** | [etcd](etcd.md)、[ZooKeeper](zookeeper.md)、[Consul](consul.md) |
| **密钥 / 敏感配置** | [Vault](vault.md) |
| **K8s 原生** | [ConfigMap / Secret 及生态](kubernetes.md) |
| **云厂商托管** | [AWS / 阿里云 / 腾讯云 / Azure / GCP](cloud-managed.md) |

## 选型速查

| 场景 | 建议 |
| --- | --- |
| Spring Cloud 微服务，要 UI + 灰度 + 审计 | [Apollo](apollo.md) |
| Spring Cloud Alibaba，配置 + 注册一体 | [Nacos](nacos.md) |
| 已有 Git 流程，只要最简配置分发 | [Spring Cloud Config](spring-cloud-config.md) |
| 纯 K8s，应用不想引 SDK | [ConfigMap + Reloader / External Secrets](kubernetes.md) |
| Go / 多语言、要强一致 + Watch | [etcd](etcd.md) |
| 老 Java 中间件生态（Dubbo/Kafka/HBase） | [ZooKeeper](zookeeper.md) |
| 服务发现 + KV + 配置文件模板渲染 | [Consul](consul.md) + consul-template |
| 数据库密码、证书、动态凭证、轮转 | [Vault](vault.md) |
| 不想运维、已在某朵云上 | [云厂商托管](cloud-managed.md) |

## 概念对比

| 工具 | 一致性 | 数据模型 | 推送机制 | 灰度 | 版本/回滚 | 权限 | 自带 UI | 主要语言栈 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Nacos | Raft(配置持久化用 DB) | Namespace/Group/DataId | 长轮询 29.5s，v2 gRPC 长连接 | ✔ Beta 按 IP | ✔ 历史版本 | ✔ 命名空间 + RBAC | ✔ | Java 为主，多语言 SDK |
| Apollo | 最终一致（DB + 推送） | App/Env/Cluster/Namespace | DeferredResult 长轮询 60s + 5min 兜底 | ✔ 灰度规则 | ✔ 发布历史 | ✔ 细粒度 + 审计 | ✔ 最强 | Java 为主 |
| Spring Cloud Config | 取决于 Git | Git 仓库文件 | ❌ 需 /refresh 或 Bus 广播 | ❌（靠分支/profile） | ✔ Git 天然 | Git 权限 | ❌ | Spring |
| etcd | Raft 强一致 | 扁平 Key + MVCC revision | ✔ Watch（revision 重放） | ❌ | 版本号有，需自管 | RBAC + TLS | ❌ | Go / 多语言 |
| ZooKeeper | ZAB 强一致 | znode 树 | ✔ Watcher（一次性） | ❌ | ❌ 需自建 | ACL | ❌ | Java |
| Consul | Raft 强一致 | KV 前缀树 | ✔ blocking query | ❌ | 有 ModifyIndex | ACL Token | ✔ 简易 | 多语言 |
| Vault | Raft / 外部存储 | Path + Secret Engine | ❌ 拉取 + Lease 续期 | ❌ | ✔ KV v2 版本 | ✔ Policy 最细 | ✔ | 多语言 |
| K8s ConfigMap | etcd 强一致 | 命名空间内 K/V | volume 挂载自动更新（~1min） | ❌ 靠滚动发布 | ❌ 需 GitOps | RBAC | ❌（用 Dashboard） | 语言无关 |
| 云托管 | 厂商保证 | 参数路径 / 键值 | 轮询 / 事件通知 | ✔（AppConfig 等） | ✔ | IAM | ✔ | SDK |

## 核心机制

- **推送 vs 拉取**：主流是「长轮询」伪推送（Nacos 29.5s、Apollo 60s、Consul blocking query），兼顾实时性与连接数；etcd/ZK 是真 Watch；Spring Cloud Config 只有拉取
- **本地快照**：Nacos/Apollo 都会把配置落盘（`~/nacos/config`、`/opt/data/{appId}/config-cache`），配置中心挂了应用仍能启动，这是可用性底线
- **动态刷新原理**：Spring 侧统一靠 `@RefreshScope`（scope 代理 + bean 销毁重建）或 `SpringValueProcessor` 反射改 `@Value` 字段；静态 `static` 字段和构造注入拿不到更新
- **配置 vs 密钥**：普通配置进 Nacos/Apollo/ConfigMap，密码证书进 Vault / KMS / Secrets Manager，两者权限模型和轮转需求完全不同
- **一致性等级**：配置读多写少，最终一致足够；强一致（Raft）主要是为了选主和分布式锁，别为配置本身付这个代价

## 落地要点

- **配置分层**：全局公共配置 → 环境配置 → 应用私有配置，优先级明确写文档，避免"改了不生效"的排查地狱
- **环境隔离**：物理隔离（不同集群）优于逻辑隔离（namespace），生产配置中心不与测试共用
- **变更即发布**：配置变更走审批 + 灰度 + 可回滚，配置改错造成的故障不比代码少
- **敏感信息不落明文**：至少 jasypt/SOPS 加密，理想是 Vault 动态凭证
- **降级兜底**：客户端必须有本地缓存 + 默认值，配置中心不可用不能拖垮业务
- **监控**：配置推送延迟、客户端连接数、长轮询超时率、配置读取失败率
