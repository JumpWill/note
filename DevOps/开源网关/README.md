# 开源网关

按场景分文件整理开源 API Gateway / Ingress Controller / Service Mesh / 反向代理的原理、架构、接入与对比。

## 分类与索引

| 分类 | 工具 |
| --- | --- |
| **传统 API Gateway** | [Kong](kong.md)、[Tyk](tyk.md)、[KrakenD](krakend.md) |
| **云原生 API Gateway** | [Apache APISIX](apisix.md)、[Higress](higress.md) |
| **API 管理平台** | [Gravitee](gravitee.md) |
| **Ingress / 反向代理** | [Traefik](traefik.md)、[Envoy](envoy.md) |
| **Service Mesh** | [Istio](istio.md)、[Linkerd](linkerd.md) |

## 选型速查

| 场景 | 建议 |
| --- | --- |
| 老牌企业 / 插件生态丰富 | Kong |
| 云原生 / etcd / 动态路由 | Apache APISIX |
| API 全生命周期管理 + 文档 + 订阅 | Gravitee |
| 性能聚合 / 只读 JSON 配置 | KrakenD |
| Go 单文件 / 内置仪表盘 | Tyk |
| K8s Ingress + 自动 HTTPS + Dashboard | Traefik |
| Service Mesh + 流量管理 | Istio |
| 轻量 Service Mesh + Rust 数据面 | Linkerd |
| Envoy 数据面 + 自定义控制面 | Envoy + 自研/Istio |
| 阿里云原生 + Wasm 插件 | Higress |

## 概念对比

| 工具 | 数据面 | 控制面 | 配置中心 | 插件 | 多协议 | Dashboard | Wasm | 语言栈 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Kong** | OpenResty | Kong Server | DB/DB-less | Lua/Go/Python | HTTP/gRPC/TCP | ✔ | ❌ | Lua + Go |
| **APISIX** | OpenResty/Nginx | APISIX Server | etcd | Lua/Go/Java/Node | HTTP/gRPC/TCP/UDP | ✔ | 实验 | Lua + Go |
| **Tyk** | Go | Tyk Gateway | Redis | Go/Lua/JS/GraphQL | HTTP/gRPC | ✔ | ❌ | Go |
| **KrakenD** | Go | 无（只读配置） | 文件 | 中间件 | HTTP | ❌ | ❌ | Go |
| **Gravitee** | Java/Netty | Gravitee APIM | MongoDB | 策略/插件 | HTTP | ✔ | ❌ | Java |
| **Traefik** | Go | 内置 | 文件/K8s/Consul | 中间件 | HTTP/TCP/UDP | ✔ | ❌ | Go |
| **Envoy** | C++ | xDS（自研控制面） | xDS API | Filter (C++/Wasm) | HTTP/gRPC/TCP/UDP | ❌ | ✔ | C++ |
| **Istio** | Envoy | Istiod | K8s CRD | EnvoyFilter + Wasm | 全协议 | ✔ (Kiali) | ✔ | Go + C++ |
| **Linkerd** | linkerd2-proxy (Rust) | Controller | K8s CRD | Service Profile | HTTP/gRPC | ✔ (Viz) | ❌ | Go + Rust |
| **Higress** | Envoy + Nginx | Higress Controller | K8s CRD/Nacos | Wasm/插件 | HTTP/gRPC/Redis | ✔ | ✔ 一等公民 | Go + C++ |

## 核心机制

- **数据面 vs 控制面**：数据面处理流量，控制面管配置和状态
- **代理模式**：Reverse Proxy（最常见）、Sidecar（Mesh）、eBPK 透明代理
- **路由**：Path / Host / Header / Method / Cookie / Body / gRPC method
- **插件 / Filter**：鉴权、限流、灰度、缓存、转换、日志、Metric
- **配置中心**：DB（Kong）、etcd（APISIX）、K8s CRD（Istio/Higress）、文件（KrakenD）、xDS（Envoy）
- **服务发现**：DNS / Consul / Nacos / K8s Service / Eureka
- **热更新**：配置变更不停机 reload，APISIX/Envoy/Istio 毫秒级
- **可观测**：Access log、Prometheus Metric、Trace（OpenTelemetry）

## 落地要点

- **入口网关**：Kong / APISIX / Traefik 集中鉴权、限流、灰度
- **东西向**：Service Mesh（Istio / Linkerd）处理 mTLS、重试、熔断
- **API 治理**：Gravitee / APISIX 控制台审批、文档、订阅、计量
- **边缘**：Higress / Envoy 部署在 CDN 边缘节点
- **混合**：数据面用 Envoy，控制面自研或用 Istio
- **插件**：优先用现成插件，二次开发评估 Wasm vs 原生
- **配置**：GitOps 优先（Argo CD / Flux），不要 CLI 改
- **证书**：cert-manager + ACME 自动签发
- **可观测**：Prometheus + Loki + Tempo 三件套
- **性能压测**：wrk / vegeta / k6 验证后上线
