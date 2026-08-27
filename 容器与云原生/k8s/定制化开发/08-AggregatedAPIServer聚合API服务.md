# Aggregated API Server 聚合 API 服务

## 一、为什么要做 Aggregated API Server

### 1.1 业务背景

```text
K8s 原生 API 资源的局限：
  - 内置资源有限（Pod、Service、Deployment...）
  - Operator 用 CRD 扩展（但逻辑在 Controller）
  - 某些场景需要完整的 API 扩展

业务场景：
  - 自研 PaaS 平台（多租户、计量、计费）
  - 自研 Service Mesh（如 Istio 的 Pilot）
  - 内部开发者门户
  - 自定义 CRD 操作工具（如 kubectl plugin）
  - 多集群管理 API
  - 内部资源管理
  - 自定义认证 API

这些场景需要：
  - 在 K8s API Server 上注册自定义 API
  - 复用 K8s 的认证、授权、配额
  - 复用 kubectl 工具
  - 复用 RBAC
```

### 1.2 Aggregated API Server 核心价值

```text
1. 复用 K8s 生态
   - 复用 K8s 认证（client certs、token）
   - 复用 K8s 授权（RBAC）
   - 复用 kubectl / UI（K8s Dashboard）
   - 复用 K8s client libraries

2. 独立部署
   - 独立进程
   - 独立扩展
   - 独立升级

3. 标准化协议
   - 使用 K8s apiserver 库
   - 实现 apiserver.Builder
   - 兼容 K8s OpenAPI

4. 灵活 API
   - 自定义资源
   - 自定义子资源
   - 自定义操作
```

### 1.3 适用场景

```text
适合 Aggregated API Server 的场景：
  ✅ 自研 PaaS 平台
  ✅ 多租户管理
  ✅ 复杂资源（CRD 不够用）
  ✅ 需要完整 K8s 生态集成
  ✅ Service Mesh 控制面
  ✅ 内部开发者工具

不适合：
  ❌ 简单 CRD 即可（用 Operator）
  ❌ 不想复用 K8s 认证（用独立服务）
  ❌ K8s 版本 < 1.7（API 聚合）
```

---

## 二、Aggregated API Server 架构

### 2.1 整体架构

```text
┌────────────────────────────────────────────────────────────┐
│                  K8s API Server                              │
│                                                            │
│  /api/v1/pods（核心资源）                                │
│  /apis/apps/v1/deployments                                │
│  /apis/batch/v1/jobs                                     │
│  /apis/networking.k8s.io/v1/networkpolicies               │
│                                                            │
│       ↓                                                    │
│  ┌──────────────────────────────────────────────────┐    │
│  │  Aggregator Layer                                 │    │
│  │  - 客户端请求路由到 AA                            │    │
│  │  - 保留客户端连接                                │    │
│  │  - 协议转换                                      │    │
│  └────────────────────┬─────────────────────────────┘    │
│                       │                                    │
└───────────────────────┼────────────────────────────────────┘
                       │
                       │ HTTPS（K8s 内部协议）
                       │ 包含认证、授权信息
                       ↓
┌────────────────────────────────────────────────────────────┐
│       Aggregated API Server（独立进程）                    │
│                                                            │
│  - 实现 K8s apiserver 库接口                            │
│  - 注册自定义资源（MyResource）                         │
│  - 复用 K8s 认证、授权                                  │
│  - 自定义业务逻辑                                        │
│                                                            │
│       ↓                                                    │
│  ┌──────────────────────────────────────────────────┐    │
│  │  Storage Layer（可选）                              │    │
│  │  - etcd（推荐）                                    │    │
│  │  - 或外部数据库                                    │    │
│  └──────────────────────────────────────────────────┘    │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

### 2.2 Aggregator Layer

```text
K8s Aggregator Layer 负责：

  ┌──────────────────────────────────┐
  │  1. 接收 API 请求              │
  │  2. 检查 APIService 对象        │
  │  3. 找到对应的 AA               │
  │  4. 代理请求到 AA              │
  │  5. 返回响应给客户端          │
  └──────────────────────────────────┘

  APIService 对象（K8s 内置）：
    - 定义 AA 服务的 URL
    - 定义代理规则
    - 定义哪些路径/组转发

  示例：
    apiVersion: apiregistration.k8s.io/v1
    kind: APIService
    metadata:
      name: v1beta1.metrics.k8s.io
    spec:
      service:
        name: metrics-server
        namespace: kube-system
        port: 443
      group: metrics.k8s.io
      versionPriority: 100
      caBundle: ...
```

### 2.3 与 CRD 的区别

```text
┌────────────────┬──────────────────────┐
│  维度          │  CRD          │  Aggregated API Server  │
├────────────────┼──────────────────────┤
│  复杂度        │  低              │  高                  │
│  适合场景      │  简单资源        │  复杂 API            │
│  注册方式      │  K8s 内置机制  │  APIService 资源   │
│  通信协议      │  etcd 直读      │  gRPC/HTTPS         │
│  开发语言      │  任意          │  任意               │
│  部署方式      │  Operator Pod  │  AA Pod（独立）    │
│  复用 K8s     │  有限          │  完全（认证、RBAC）│
│  K8s 版本要求 │  1.16+         │  1.7+                │
└────────────────┴──────────────────────┘
```

---

## 三、Aggregated API Server 开发

### 3.1 项目结构

```text
aa-server/
├── cmd/
│   └── aa/
│       └── main.go              # AA 入口
├── pkg/
│   ├── apis/
│   │   └── myresource/
│   │       ├── register.go      # 注册到 K8s
│   │       ├── types.go         # 资源定义
│   │       └── v1alpha1/        # 版本
│   ├── apiserver/
│   │   ├── apiserver.go        # AA 主体
│   │   └── storage.go          # 存储层
│   └── registry/
│       └── rest.go             # REST 路由
├── deploy/
│   ├── rbac.yaml
│   ├── apiservice.yaml
│   └── deployment.yaml
├── Dockerfile
└── go.mod
```

### 3.2 定义自定义资源

```go
// pkg/apis/myresource/v1alpha1/types.go
package v1alpha1

import (
    metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
    "k8s.io/apimachinery/pkg/runtime"
    "k8s.io/apimachinery/pkg/runtime/schema"
)

// MyResource 自定义资源
type MyResource struct {
    metav1.TypeMeta   `json:",inline"`
    metav1.ObjectMeta `json:"metadata,omitempty"`

    Spec   MyResourceSpec   `json:"spec,omitempty"`
    Status MyResourceStatus `json:"status,omitempty"`
}

type MyResourceSpec struct {
    // 业务字段
    Image    string `json:"image"`
    Replicas int32  `json:"replicas"`
    Database string `json:"database"`
}

type MyResourceStatus struct {
    Phase   string `json:"phase,omitempty"`
    Message string `json:"message,omitempty"`
}

// DeepCopyObject 实现 runtime.Object
func (in *MyResource) DeepCopyObject() runtime.Object {
    if c := in.DeepCopy(); c != nil {
        return c
    }
    return nil
}

func (in *MyResource) DeepCopy() *MyResource {
    out := new(MyResource)
    in.DeepCopyInto(out)
    return out
}

func (in *MyResource) DeepCopyInto(out *MyResource) {
    *out = *in
    out.TypeMeta = in.TypeMeta
    in.ObjectMeta.DeepCopyInto(&out.ObjectMeta)
    in.Spec.DeepCopyInto(&out.Spec)
    in.Status.DeepCopyInto(&out.Status)
}

// 注册到 scheme
func init() {
    SchemeBuilder.Register(addKnownTypes)
}

var (
    SchemeBuilder = runtime.NewSchemeBuilder(addKnownTypes)
    AddToScheme    = SchemeBuilder.AddToScheme
)

func addKnownTypes(scheme *runtime.Scheme) error {
    scheme.AddKnownTypes(SchemeGroupVersion,
        &MyResource{},
        &MyResourceList{},
    )
    metav1.AddToGroupVersion(scheme, SchemeGroupVersion)
    return nil
}

var SchemeGroupVersion = schema.GroupVersion{
    Group:   "mycompany.com",
    Version: "v1alpha1",
}

type MyResourceList struct {
    metav1.TypeMeta `json:",inline"`
    metav1.ListMeta `json:"metadata,omitempty"`
    Items           []MyResource `json:"items"`
}
```

### 3.3 实现 REST Storage

```go
// pkg/registry/rest.go
package registry

import (
    "context"
    "fmt"

    metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
    "k8s.io/apimachinery/pkg/runtime"
    "k8s.io/apimachinery/pkg/watch"
    "k8s.io/apiserver/pkg/registry/rest"

    "github.com/example/aa-server/pkg/apis/myresource/v1alpha1"
)

type MyResourceStorage struct {
    *Backend
}

// Get 读取资源
func (s *MyResourceStorage) Get(ctx context.Context, name string, options *metav1.GetOptions) (runtime.Object, error) {
    obj, err := s.Backend.Get(ctx, name, options)
    if err != nil {
        return nil, err
    }
    return obj, nil
}

// List 列出资源
func (s *MyResourceStorage) List(ctx context.Context, options *metav1.ListOptions) (runtime.Object, error) {
    objs, err := s.Backend.List(ctx, options)
    if err != nil {
        return nil, err
    }
    return objs, nil
}

// Create 创建资源
func (s *MyResourceStorage) Create(ctx context.Context, obj runtime.Object, createValidation rest.ValidateObjectFunc, options *metav1.CreateOptions) (runtime.Object, error) {
    obj, err := s.Backend.Create(ctx, obj, createValidation, options)
    if err != nil {
        return nil, err
    }
    return obj, nil
}

// Update 更新资源
func (s *MyResourceStorage) Update(ctx context.Context, name string, obj rest.UpdatedObjectInfo, createValidation rest.ValidateObjectFunc, updateValidation rest.ValidateObjectUpdateFunc, options *metav1.UpdateOptions) (runtime.Object, bool, error) {
    obj, created, err := s.Backend.Update(ctx, name, obj, createValidation, updateValidation, options)
    return obj, created, err
}

// Delete 删除资源
func (s *MyResourceStorage) Delete(ctx context.Context, name string, options *metav1.DeleteOptions) (runtime.Object, bool, error) {
    obj, deleted, err := s.Backend.Delete(ctx, name, options)
    return obj, deleted, err
}

// Watch 监听资源
func (s *MyResourceStorage) Watch(ctx context.Context, options *metav1.ListOptions) (watch.Interface, error) {
    return s.Backend.Watch(ctx, options)
}
```

### 3.4 实现 Storage Backend（etcd）

```go
// pkg/apiserver/storage.go
package apiserver

import (
    "fmt"

    "k8s.io/apimachinery/pkg/runtime"
    "k8s.io/apimachinery/pkg/runtime/schema"
    "k8s.io/apiserver/pkg/registry/generic"
    "k8s.io/apiserver/pkg/registry/rest"
    "k8s.io/apiserver/pkg/server"
    "k8s.io/apiserver/pkg/server/options"
    "k8s.io/apiserver/pkg/server/storage"
    "k8s.io/client-go/informers"

    "github.com/example/aa-server/pkg/apis/myresource/v1alpha1"
)

func buildStorage(etcd *storagebackend.Config) (server.Storage, error) {
    // 创建 etcd 存储
    storageFactory, err := storagebackend.NewFactory(
        "etcd",
        etcd,
    )
    if err != nil {
        return nil, err
    }
    
    storage, err := generic.NewRESTStorageProvider(
        storageFactory,
        &generic.RESTOptions{
            StorageConfig:           etcd,
            Decorator:              generic.UndecoratedStorage,
            ResourcePrefix:         "registry",
            GroupVersion:           v1alpha1.SchemeGroupVersion,
        },
        &MyResource{},
        nil, nil,
    )
    if err != nil {
        return nil, err
    }
    
    // 注册到 etcd
    err = storage.Update(
        v1alpha1.SchemeGroupVersion.WithResource("myresources"),
        v1alpha1.SchemeGroupVersion,
        v1alpha1.MyResource{},
        nil, nil,
    )
    if err != nil {
        return nil, err
    }
    
    return storage, nil
}
```

### 3.5 实现 AA Server 主体

```go
// pkg/apiserver/apiserver.go
package apiserver

import (
    "github.com/spf13/cobra"
    "k8s.io/apimachinery/pkg/runtime"
    "k8s.io/apimachinery/pkg/runtime/schema"
    "k8s.io/apiserver/pkg/admission"
    "k8s.io/apiserver/pkg/server"
    "k8s.io/apimachinery/pkg/util/wait"
    "k8s.io/klog/v2"
    
    "github.com/example/aa-server/pkg/apis/myresource/v1alpha1"
)

type Config struct {
    SecureServing  *server.SecureServingInfo
    Authentication  Authn
    Authorization   Authz
    EtcdServersList []string
    TlsCert         []byte
    TlsKey          []byte
}

// NewCommand 创建 cobra 命令
func NewCommand() *cobra.Command {
    o := &ServerOptions{
        RecommendedOptions: &options.RecommendedOptions{},
    }
    
    cmd := &cobra.Command{
        Use:  "aa-server",
        Long: "My Aggregated API Server",
        RunE: func(c *cobra.Command, args []string) error {
            return Run(o, args)
        },
    }
    
    flags := cmd.Flags()
    o.AddFlags(flags)
    
    return cmd
}

func Run(options *ServerOptions, args []string) error {
    // 1. 创建 API Server 配置
    serverConfig := server.NewConfig(options.RecommendedOptions...)
    
    // 2. 创建 Generic API Server
    apiServer, err := serverConfig.Complete().New()
    if err != nil {
        return err
    }
    
    // 3. 注册自定义资源
    apiGroup := schema.GroupVersion{
        Group:   "mycompany.com",
        Version: "v1alpha1",
    }
    
    err = apiServer.InstallAPIGroups(&[]schema.GroupVersion{apiGroup})
    if err != nil {
        return err
    }
    
    // 4. 启动 API Server
    prepared, err := apiServer.PrepareRun()
    if err != nil {
        return err
    }
    
    klog.InfoS("starting my AA server", "info", prepared.SecureServingInfo)
    
    return prepared.Run(wait.NeverStop)
}
```

### 3.6 main.go 入口

```go
// cmd/aa/main.go
package main

import (
    "fmt"
    "os"
    
    "github.com/example/aa-server/pkg/apiserver"
)

func main() {
    cmd := apiserver.NewCommand()
    if err := cmd.Execute(); err != nil {
        fmt.Fprintf(os.Stderr, "%v\n", err)
        os.Exit(1)
    }
}
```

### 3.7 APIService 注册

```yaml
# deploy/apiservice.yaml
apiVersion: apiregistration.k8s.io/v1
kind: APIService
metadata:
  name: v1alpha1.mycompany.com
spec:
  group: mycompany.com
  groupPriorityMinimum: 1000
  versionPriority: 100
  service:
    name: my-aa-service
    namespace: my-aa-system
    port: 443
  caBundle: <base64-encoded-ca-cert>
  version: v1alpha1
```

```yaml
# deploy/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: my-aa-service
  namespace: my-aa-system
spec:
  selector:
    app: my-aa
  ports:
  - name: https
    port: 443
    targetPort: 8443
```

```yaml
# deploy/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-aa
  namespace: my-aa-system
  labels:
    app: my-aa
spec:
  replicas: 2
  selector:
    matchLabels:
      app: my-aa
  template:
    metadata:
      labels:
        app: my-aa
    spec:
      serviceAccountName: my-aa
      containers:
      - name: my-aa
        image: registry.example.com/my-aa:v1.0
        command: ["/aa-server"]
        ports:
        - containerPort: 8443
        args:
        - --tls-cert-file=/etc/certs/tls.crt
        - --tls-private-key-file=/etc/certs/tls.key
        - --etcd-servers=https://etcd:2379
        - --etcd-cafile=/etc/etcd/ca.crt
        - --etcd-certfile=/etc/etcd/etcd.crt
        - --etcd-keyfile=/etc/etcd/etcd.key
        - --secure-port=8443
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 500m
            memory: 256Mi
        volumeMounts:
        - name: etcd-certs
          mountPath: /etc/etcd
          readOnly: true
      volumes:
      - name: etcd-certs
        secret:
          secretName: my-aa-etcd-certs
```

### 3.8 RBAC 配置

```yaml
# RBAC for AA Server to interact with K8s
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: my-aa
rules:
- apiGroups: [""]
  resources: ["events"]
  verbs: ["create", "update", "patch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: my-aa
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: my-aa
subjects:
- kind: ServiceAccount
  name: my-aa
  namespace: my-aa-system
```

---

## 四、实战场景

### 4.1 场景 1：metrics-server（最经典 AA）

```yaml
# metrics-server 就是一个 AA
apiVersion: v1
kind: Service
metadata:
  name: metrics-server
  namespace: kube-system
spec:
  selector:
    k8s-app: metrics-server
  ports:
  - name: https
    port: 443
    targetPort: 4443
---
apiVersion: apiregistration.k8s.io/v1
kind: APIService
metadata:
  name: v1beta1.metrics.k8s.io
spec:
  service:
    name: metrics-server
    namespace: kube-system
    port: 443
  group: metrics.k8s.io
  versionPriority: 100
  caBundle: ...
  version: v1beta1

# 用户使用
# kubectl top nodes
# kubectl top pods
```

### 4.2 场景 2：自研 PaaS 平台

```yaml
# 抽象出 Tenant、Project、Pipeline 等资源
apiVersion: mycompany.com/v1
kind: Tenant
metadata:
  name: acme-corp
spec:
  quota:
    cpu: "100"
    memory: 200Gi
    storage: 1Ti
  projects:
  - name: web-app
  - name: data-pipeline
---
apiVersion: mycompany.com/v1
kind: Pipeline
metadata:
  name: data-etl
  namespace: acme-corp
spec:
  source: kafka://input-topic
  sink: s3://output-bucket/
  schedule: "0 2 * * *"
```

### 4.3 场景 3：内部 Service Mesh 控制面

```yaml
# 类似 Istio 的 Pilot
apiVersion: mycompany.com/v1
kind: ServiceRoute
metadata:
  name: order-service-route
spec:
  service: order-service
  destination: payment-service
  trafficPolicy:
    retry: 3
    timeout: 5s
  canary:
    weight: 10
    match:
      headers:
        x-user-type: beta
```

### 4.4 场景 4：kubectl 插件化扩展

```bash
# 用户使用
kubectl get tenants
kubectl get pipelines
kubectl describe tenant acme-corp

# 与内置资源一样的体验
```

---

## 五、客户端使用

### 5.1 kubectl 直接访问

```bash
# AA 资源对 kubectl 透明
kubectl get myresources
# NAME              AGE
# my-resource-1     10m
# my-resource-2     5m

kubectl describe myresource my-resource-1

kubectl get myresource my-resource-1 -o yaml
```

### 5.2 Client-go 编程访问

```go
import (
    "context"
    metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
    "k8s.io/client-go/kubernetes"
    "k8s.io/client-go/rest"
    
    myv1alpha1 "github.com/example/aa-client/pkg/apis/myresource/v1alpha1"
)

func main() {
    config, _ := rest.InClusterConfig()
    // 配置 API 服务路径
    config.APIPath = "/apis"
    config.GroupVersion = &myv1alpha1.SchemeGroupVersion
    
    clientset, _ := kubernetes.NewForConfig(config)
    
    // 列出 MyResource
    list, _ := clientset.RESTClient().Get().
        AbsPath("/apis/mycompany.com/v1alpha1/myresources").
        DoRaw(context.TODO())
    fmt.Println(string(list))
}
```

### 5.3 curl 直接访问

```bash
# 通过 K8s Aggregator 访问
curl -k \
  -H "Authorization: Bearer $TOKEN" \
  https://k8s-api:6443/apis/mycompany.com/v1alpha1/myresources

# 响应：
# {
#   "items": [...],
#   "metadata": {...}
# }
```

---

## 六、高级特性

### 6.1 自定义 subresources

```go
// 子资源实现
func (s *MyResourceStorage) UpdateStatus(
    ctx context.Context, name string, obj runtime.Object,
    options *metav1.UpdateOptions,
) (runtime.Object, error) {
    // 更新 status 子资源
    return s.Backend.UpdateStatus(ctx, name, obj, options)
}

// 子资源 endpoint 自动生成
// PUT /apis/mycompany.com/v1alpha1/myresources/foo/status
```

### 6.2 自定义 Admission Webhook 集成

```go
// 在 AA 中集成 Webhook 验证
import (
    "k8s.io/apiserver/pkg/admission"
)

type MyAdmission struct {
    PluginName string
}

func (a *MyAdmission) Validate(ctx context.Context, attr admission.Attributes) (err error) {
    if attr.GetKind() != "MyResource" {
        return nil
    }
    // 自定义验证逻辑
    obj := attr.GetObject()
    if obj.GetName() == "forbidden" {
        return fmt.Errorf("name 'forbidden' is not allowed")
    }
    return nil
}

// 注册到 AA
defs := admission.NewPlugins()
defs.Register("MyAdmission", &MyAdmission{PluginName: "MyAdmission"})

apiServerConfig := &apiserver.Config{
    Admission: &admission.Config{
        Plugins: defs,
    },
}
```

### 6.3 多个 GroupVersion 支持

```go
// 同时支持 v1alpha1 和 v1beta1
apiGroupVersions := []schema.GroupVersion{
    {Group: "mycompany.com", Version: "v1alpha1"},
    {Group: "mycompany.com", Version: "v1beta1"},
}

for _, gv := range apiGroupVersions {
    apiServer.InstallAPIGroups(&[]schema.GroupVersion{gv})
}
```

### 6.4 自定义 OpenAPI

```go
// 自动生成 OpenAPI 规范
import (
    "k8s.io/kube-openapi/pkg/common"
    "k8s.io/kube-openapi/pkg/builder"
)

func GetOpenAPIDefinitions(common.Parameters) []common.OpenAPIDefinition {
    return []common.OpenAPIDefinition{
        schemagen.GroupVersionKind{Group: "mycompany.com", Kind: "MyResource"}.
            OpenAPIDefinition(),
    }
}
```

---

## 七、Aggregated API Server 调试

### 7.1 调试工具

```bash
# 1. 查看 APIService
kubectl get apiservices
kubectl describe apiservice v1alpha1.mycompany.com

# 2. 查看 AA 健康状态
kubectl get --raw='/healthz?verbose' -k

# 3. 直接访问 AA
curl -k https://<aa-service>:443/healthz

# 4. 查看 AA Pod 日志
kubectl logs -n my-aa-system deploy/my-aa -f

# 5. 测试 AA 资源
kubectl get myresources -v=8
```

### 7.2 常见问题

```text
Q1: kubectl get myresources 报 no matches
A1: 检查：
    - kubectl api-resources | grep myresources
    - APIService 是否就绪
    - RBAC 权限

Q2: APIService 无法注册
A2: 检查：
    - caBundle 是否正确
    - AA 服务是否可访问
    - AA Pod 是否健康

Q3: AA 启动失败
A3: 检查：
    - etcd 连接
    - 证书配置
    - 端口冲突
```

### 7.3 安全最佳实践

```text
1. 严格 RBAC
   - 限制 AA Pod 权限
   - 使用专用 ServiceAccount

2. 证书管理
   - 使用 cert-manager 自动管理
   - 定期轮换证书

3. 网络隔离
   - 独立 namespace
   - NetworkPolicy 限制

4. 审计日志
   - 记录所有 API 请求
   - 监控异常访问
```

---

## 八、参考资源

```text
- K8s Aggregated API Server: https://kubernetes.io/docs/tasks/access-kubernetes-api/setup-extension-api-server/
- K8s apiserver 库: https://github.com/kubernetes/apiserver
- sample-apiserver: https://github.com/kubernetes/sample-apiserver
- kube-openapi: https://github.com/kubernetes/kube-openapi
- AA 实践教程: https://kubernetes.io/docs/tasks/access-kubernetes-api/setup-extension-api-server/
- K8s 客户端: https://github.com/kubernetes/client-go
- AA 部署示例: https://github.com/kubernetes/sample-apiserver/blob/master/README.md

```

## 速记卡

Aggregated API Server = K8s API 扩展机制
注册方式：APIService 资源 + 证书
核心：复用 K8s 认证 / 授权 / 客户端
流程：客户端 → K8s API → Aggregator → AA → 后端存储
开发框架：k8s.io/apiserver
多 GroupVersion 支持：v1alpha1、v1beta1、v1 等
最适合：完整 PaaS 平台、复杂业务系统
CRD 不够用时考虑 AA
metrics-server 是最经典的 AA 示例
