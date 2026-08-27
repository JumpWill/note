# Admission Webhook（准入控制）

## 一、为什么要做 Admission Webhook

### 1.1 业务背景

```text
现实场景：
  - 公司要求所有镜像必须来自内部 registry.example.com
  - 禁止 Pod 使用 hostNetwork
  - 强制要求所有 Pod 设置资源 limits
  - 自动注入 sidecar 容器（如 Istio proxy）
  - 校验 configmap 内容不包含敏感词
  - 阻止 privileged 容器在生产环境运行
  - 强制 Pod label 必须包含团队标识
  - 多租户环境配额管理

这些需求用 K8s 内置 RBAC 做不到，需要拦截 API 请求并自定义处理。
```

### 1.2 Admission Webhook 核心价值

```text
1. 拦截 API 请求
   - 在请求到达 etcd 之前拦截
   - 可以修改或拒绝请求
   - 同步处理（快速决策）

2. 自定义业务规则
   - 镜像白名单/黑名单
   - 安全合规检查
   - 资源配额校验
   - 自动注入 sidecar

3. 与 K8s 生态融合
   - 与 RBAC 配合
   - 与 PSP/PSA 配合
   - 可观测性集成
```

### 1.3 适用场景

```text
适合 Admission Webhook 的场景：
  ✅ 镜像仓库管控（强制内部 registry）
  ✅ 安全合规（禁止 privileged）
  ✅ 自动注入 sidecar
  ✅ 资源配额校验
  ✅ 多租户隔离
  ✅ 镜像签名验证（Cosign）
  ✅ 自定义资源验证

不适合：
  ❌ 简单权限控制（用 RBAC）
  ❌ 复杂业务逻辑（用 Operator）
  ❌ 异步任务（用 Job/CronJob）
```

---

## 二、Admission Webhook 类型

### 2.1 两种类型

```text
┌─────────────────┬──────────────────────┐
│  类型            │  用途                │
├─────────────────┼──────────────────────┤
│  Mutating       │  修改对象（注入字段）│
│  Validating      │  验证对象（拒绝/通过）│
└─────────────────┴──────────────────────┘

调用顺序：
  1. Mutating Webhook（可修改 spec）
  2. Validating Webhook（只读验证）
  3. Default 准入（SA/PSP/PSA 等）
  4. 持久化到 etcd
```

### 2.2 准入流程

```text
kubectl apply -f pod.yaml
       │
       ▼
  ┌──────────────────────────────────┐
  │  Authentication（认证）         │
  │  - 验证 ServiceAccount         │
  │  - 验证 Token                    │
  └────────────┬─────────────────────┘
               │
               ▼
  ┌──────────────────────────────────┐
  │  Authorization（授权）         │
  │  - RBAC 检查                    │
  │  - ABAC 检查                    │
  └────────────┬─────────────────────┘
               │
               ▼
  ┌──────────────────────────────────┐
  │  MutatingAdmissionWebhook       │ ← 你的 Webhook 1
  │  - 注入 sidecar                  │
  │  - 修改镜像仓库                │
  │  - 设置默认值                    │
  └────────────┬─────────────────────┘
               │
               ▼
  ┌──────────────────────────────────┐
  │  ValidatingAdmissionWebhook      │ ← 你的 Webhook 2
  │  - 验证镜像白名单                │
  │  - 校验资源 limits                │
  │  - 阻止 hostNetwork             │
  └────────────┬─────────────────────┘
               │
               ▼
  ┌──────────────────────────────────┐
  │  Default 准入控制器              │
  │  - ServiceAccount               │
  │  - PodSecurityAdmission         │
  │  - ResourceQuota                │
  └────────────┬─────────────────────┘
               │
               ▼
  ┌──────────────────────────────────┐
  │  持久化到 etcd                  │
  │  → ApiServer 响应客户端         │
  └──────────────────────────────────┘
```

---

## 三、Admission Webhook 开发

### 3.1 项目结构

```text
admission-webhook/
├── cmd/
│   └── webhook/
│       └── main.go             # Webhook 服务器入口
├── internal/
│   ├── webhook/
│   │   ├── handler.go          # Mutating/Validating Handler
│   │   ├── mutator.go          # 修改逻辑
│   │   ├── validator.go        # 验证逻辑
│   │   └── types.go            # AdmissionReview 等类型
│   └── config/
│       └── config.go           # 加载配置
├── deploy/
│   ├── cert-manager.yaml       # cert-manager 自动证书
│   ├── mutating-webhook.yaml   # MutatingWebhookConfiguration
│   ├── validating-webhook.yaml # ValidatingWebhookConfiguration
│   └── deployment.yaml          # Webhook Deployment
├── Dockerfile
├── Makefile
└── go.mod
```

### 3.2 Webhook Handler（核心实现）

```go
// internal/webhook/handler.go
package webhook

import (
    "context"
    "encoding/json"
    "fmt"
    "net/http"

    "github.com/sirupsen/logrus"
    admissionv1 "k8s.io/api/admission/v1"
    metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
    "k8s.io/apimachinery/pkg/runtime"
    "sigs.k8s.io/controller-runtime/pkg/webhook"
    "sigs.k8s.io/controller-runtime/pkg/webhook/admission"
)

const (
    webhookPath = "/mutate"
)

// MutatingHandler Mutating Admission Webhook Handler
type MutatingHandler struct {
    decoder *admission.Decoder
    log     *logrus.Logger
}

// Handle 处理 AdmissionReview 请求
func (h *MutatingHandler) Handle(ctx context.Context, req admission.Request) admission.Response {
    log := h.log.WithFields(logrus.Fields{
        "uid": req.UID,
        "kind": req.Kind.String(),
        "operation": req.Operation,
        "name": req.Name,
        "namespace": req.Namespace,
    })

    // 1. 解析 AdmissionReview
    if req.Kind.Kind != "Pod" {
        return admission.Allowed("not a pod, skip")
    }

    if req.Operation != admissionv1.Create && req.Operation != admissionv1.Update {
        return admission.Allowed("not create/update, skip")
    }

    // 2. 反序列化为 Pod 对象
    pod := &corev1.Pod{}
    if err := h.decoder.Decode(req, pod); err != nil {
        log.WithError(err).Error("decode pod failed")
        return admission.Errored(http.StatusBadRequest, err)
    }

    log.WithField("image", pod.Spec.Containers[0].Image).Info("processing")

    // 3. 调用修改逻辑
    patches, err := h.mutate(ctx, pod)
    if err != nil {
        log.WithError(err).Error("mutate failed")
        return admission.Errored(http.StatusInternalServerError, err)
    }

    // 4. 返回 patch
    return admission.Patched("", patches...)
}

// mutate 实施修改逻辑
func (h *MutatingHandler) mutate(ctx context.Context, pod *corev1.Pod) ([]jsonpatch.JsonPatchOperation, error) {
    var patches []jsonpatch.JsonPatchOperation

    // 修改 1：注入 sidecar
    if !hasContainer(pod, "istio-proxy") {
        sidecar := corev1.Container{
            Name:  "istio-proxy",
            Image: "istio/proxyv2:1.20.0",
            ... （完整 sidecar 配置）
        }
        patches = append(patches, addContainerPatch(sidecar))
    }

    // 修改 2：替换镜像仓库
    for i, container := range pod.Spec.Containers {
        if !strings.HasPrefix(container.Image, "registry.example.com/") {
            newImage := "registry.example.com/" + container.Image
            patches = append(patches, replaceImagePatch(i, newImage))
        }
    }

    // 修改 3：注入资源 limits（如缺失）
    for i, container := range pod.Spec.Containers {
        if container.Resources.Limits == nil {
            patches = append(patches, addDefaultLimits(i, ...))
        }
    }

    return patches, nil
}
```

### 3.3 Validating Handler

```go
// internal/webhook/validator.go
package webhook

import (
    "context"
    "fmt"
    "net/http"
    "strings"

    "sigs.k8s.io/controller-runtime/pkg/webhook/admission"
)

const (
    validatePath = "/validate"
)

type ValidatingHandler struct {
    decoder *admission.Decoder
    log     *logrus.Logger
}

// Handle 验证 Pod
func (h *ValidatingHandler) Handle(ctx context.Context, req admission.Request) admission.Response {
    // 1. 解析
    pod := &corev1.Pod{}
    if err := h.decoder.Decode(req, pod); err != nil {
        return admission.Errored(http.StatusBadRequest, err)
    }

    // 2. 验证规则
    if err := h.validate(ctx, pod); err != nil {
        return admission.Denied(err.Error())
    }

    return admission.Allowed("")
}

// validate 实施所有验证规则
func (h *ValidatingHandler) validate(ctx context.Context, pod *corev1.Pod) error {
    // 规则 1：禁止 hostNetwork
    if pod.Spec.HostNetwork {
        return fmt.Errorf("hostNetwork is not allowed")
    }

    // 规则 2：禁止 privileged
    for _, c := range pod.Spec.Containers {
        if c.SecurityContext != nil && c.SecurityContext.Privileged != nil && *c.SecurityContext.Privileged {
            return fmt.Errorf("privileged container %s is not allowed", c.Name)
        }
    }

    // 规则 3：镜像必须在白名单
    for _, c := range pod.Spec.Containers {
        if !isAllowedImage(c.Image) {
            return fmt.Errorf("image %s is not in allowed list", c.Image)
        }
    }

    // 规则 4：必须设置 resources.limits
    for _, c := range pod.Spec.Containers {
        if c.Resources.Limits == nil {
            return fmt.Errorf("container %s must set resources.limits", c.Name)
        }
    }

    // 规则 5：必须包含团队 label
    if !hasTeamLabel(pod) {
        return fmt.Errorf("pod must have label team=xxx")
    }

    return nil
}

// isAllowedImage 镜像白名单
func isAllowedImage(image string) bool {
    allowedRegistries := []string{
        "registry.example.com/",
        "docker.io/library/",
        "gcr.io/google_containers/",
    }
    for _, r := range allowedRegistries {
        if strings.HasPrefix(image, r) {
            return true
        }
    }
    return false
}
```

### 3.4 main.go 入口

```go
// cmd/webhook/main.go
package main

import (
    "context"
    "crypto/tls"
    "flag"
    "fmt"
    "net/http"
    "os"
    "os/signal"
    "syscall"

    "github.com/sirupsen/logrus"
    "k8s.io/apimachinery/pkg/runtime"
    utilruntime "k8s.io/apimachinery/pkg/util/runtime"
    "k8s.io/client-go/kubernetes"
    "sigs.k8s.io/controller-runtime/pkg/webhook"

    "github.com/example/admission-webhook/internal/webhook"
)

var (
    certDir = flag.String("cert-dir", "/etc/webhook/certs", "Cert directory")
    port    = flag.Int("port", 8443, "Webhook server port")
)

func main() {
    flag.Parse()

    log := logrus.New()
    log.SetLevel(logrus.InfoLevel)

    // 1. 加载 K8s 配置
    config, err := rest.InClusterConfig()
    if err != nil {
        log.Fatal(err)
    }
    clientset, err := kubernetes.NewForConfig(config)
    if err != nil {
        log.Fatal(err)
    }

    // 2. 创建 Webhook 服务器
    scheme := runtime.NewScheme()
    utilruntime.Must(corev1.AddToScheme(scheme))
    utilruntime.Must(appsv1.AddToScheme(scheme))

    decoder, _ := admission.NewDecoder(scheme)

    // 3. 注册 Handler
    mutatingHandler := &webhook.MutatingHandler{
        Decoder: decoder,
        Log:     log,
    }
    validatingHandler := &webhook.ValidatingHandler{
        Decoder: decoder,
        Log:     log,
    }

    mux := http.NewServeMux()
    mux.HandleFunc("/mutate", mutatingHandler.ServeHTTP)
    mux.HandleFunc("/validate", validatingHandler.ServeHTTP)
    mux.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
        w.WriteHeader(http.StatusOK)
    })

    // 4. 加载 TLS 证书
    cert, err := tls.LoadX509KeyPair(
        *certDir+"/tls.crt",
        *certDir+"/tls.key",
    )
    if err != nil {
        log.Fatal(err)
    }
    tlsConfig := &tls.Config{
        Certificates: []tls.Certificate{cert},
    }

    server := &http.Server{
        Addr:      fmt.Sprintf(":%d", *port),
        Handler:   mux,
        TLSConfig: tlsConfig,
    }

    // 5. 优雅关闭
    ctx, cancel := signal.NotifyContext(context.Background(),
        os.Interrupt, syscall.SIGTERM)
    defer cancel()

    log.Info("starting webhook server")
    if err := server.ListenAndServeTLS("", ""); err != nil {
        log.Fatal(err)
    }
}
```

---

## 四、证书管理

### 4.1 手动生成证书

```bash
#!/bin/bash
# generate-certs.sh

CERT_DIR=/etc/webhook/certs
mkdir -p $CERT_DIR

# 1. 生成 CA
openssl genrsa -out $CERT_DIR/ca.key 2048
openssl req -new -x509 -days 365 \
  -key $CERT_DIR/ca.key \
  -out $CERT_DIR/ca.crt \
  -subj "/CN=admission-webhook-ca"

# 2. 生成服务器证书
openssl genrsa -out $CERT_DIR/tls.key 2048

openssl req -new \
  -key $CERT_DIR/tls.key \
  -out $CERT_DIR/tls.csr \
  -subj "/CN=admission-webhook"

# 3. 使用 CA 签发
openssl x509 -req -days 365 \
  -in $CERT_DIR/tls.csr \
  -CA $CERT_DIR/ca.crt \
  -CAkey $CERT_DIR/ca.key \
  -CAcreateserial \
  -out $CERT_DIR/tls.crt

# 4. 获取 CA Bundle（用于 MutatingWebhookConfiguration）
CA_BUNDLE=$(cat $CERT_DIR/ca.crt | base64 | tr -d '\n')

echo "CA_BUNDLE=$CA_BUNDLE"
echo "Certificates generated in $CERT_DIR"
```

### 4.2 使用 cert-manager 自动管理（推荐）

```yaml
# 1. 安装 cert-manager
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.14.0/cert-manager.yaml

# 2. 创建 Issuer
apiVersion: cert-manager.io/v1
kind: Issuer
metadata:
  name: selfsigned-issuer
  namespace: cert-manager
spec:
  selfSigned: {}

# 3. 创建 Certificate（Webhook 证书）
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: admission-webhook-cert
  namespace: webhook-system
spec:
  secretName: admission-webhook-cert-secret
  duration: 2160h    # 90 天
  renewBefore: 360h  # 15 天前续签
  issuerRef:
    name: selfsigned-issuer
    kind: Issuer
  commonName: admission-webhook.webhook-system.svc
  dnsNames:
  - admission-webhook.webhook-system.svc
  - admission-webhook.webhook-system.svc.cluster.local
```

```go
// 在 Go 代码中读取证书
tlsConfig := &tls.Config{
    Certificates: []tls.Certificate{cert},
    MinVersion:   tls.VersionTLS12,
}
// cert 由 cert-manager 自动管理
```

### 4.3 使用 Kustomize 自动注入 caBundle

```yaml
# webhook-configuration.yaml
apiVersion: admissionregistration.k8s.io/v1
kind: MutatingWebhookConfiguration
metadata:
  name: admission-webhook-mutating
webhooks:
- name: mutating.example.com
  clientConfig:
    service:
      name: admission-webhook
      namespace: webhook-system
      path: /mutate
    caBundle: cG9zZWtramVkbWFwbmVsb3Y=    # ← cert-manager 自动注入
  rules:
  - operations: ["CREATE", "UPDATE"]
    apiGroups: [""]
    apiVersions: ["v1"]
    resources: ["pods"]
  sideEffects: None
  admissionReviewVersions: ["v1"]
```

---

## 五、Admission Webhook 配置

### 5.1 MutatingWebhookConfiguration

```yaml
apiVersion: admissionregistration.k8s.io/v1
kind: MutatingWebhookConfiguration
metadata:
  name: my-mutating-webhook
webhooks:
- name: pod-mutation.example.com
  clientConfig:
    caBundle: <base64-ca-cert>
    service:
      name: admission-webhook-service
      namespace: webhook-system
      path: /mutate
      port: 443
  rules:
  - operations: ["CREATE", "UPDATE"]
    apiGroups: [""]
    apiVersions: ["v1"]
    resources: ["pods"]
  # failurePolicy：失败时策略
  # Ignore：失败时放行（避免 Webhook 故障导致集群不可用）
  # Fail：失败时拒绝（严格模式）
  failurePolicy: Fail
  # 副作用声明
  sideEffects: None
  # 超时
  timeoutSeconds: 10
  # AdmissionReview 版本
  admissionReviewVersions: ["v1"]
  # 命名空间过滤（可选）
  namespaceSelector:
    matchLabels:
      enforce-policies: "true"
  # 对象选择器（可选）
  objectSelector:
    matchLabels:
      tier: "production"
```

### 5.2 ValidatingWebhookConfiguration

```yaml
apiVersion: admissionregistration.k8s.io/v1
kind: ValidatingWebhookConfiguration
metadata:
  name: my-validating-webhook
webhooks:
- name: pod-validation.example.com
  clientConfig:
    caBundle: <base64-ca-cert>
    service:
      name: admission-webhook-service
      namespace: webhook-system
      path: /validate
      port: 443
  rules:
  - operations: ["CREATE", "UPDATE"]
    apiGroups: [""]
    apiVersions: ["v1"]
    resources: ["pods"]
  failurePolicy: Fail
  sideEffects: None
  timeoutSeconds: 5
  admissionReviewVersions: ["v1"]
```

### 5.3 Service 配置

```yaml
apiVersion: v1
kind: Service
metadata:
  name: admission-webhook-service
  namespace: webhook-system
spec:
  selector:
    app: admission-webhook
  ports:
  - name: webhook
    port: 443
    targetPort: 8443
  type: ClusterIP
```

### 5.4 Deployment 部署

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: admission-webhook
  namespace: webhook-system
  labels:
    app: admission-webhook
spec:
  replicas: 2    # 多副本
  selector:
    matchLabels:
      app: admission-webhook
  template:
    metadata:
      labels:
        app: admission-webhook
    spec:
      serviceAccountName: admission-webhook
      containers:
      - name: webhook
        image: registry.example.com/admission-webhook:v1.0
        ports:
        - containerPort: 8443
        env:
        - name: POD_NAMESPACE
          valueFrom:
            fieldRef:
              fieldPath: metadata.namespace
        volumeMounts:
        - name: certs
          mountPath: /etc/webhook/certs
          readOnly: true
        resources:
          requests:
            cpu: 100m
            memory: 64Mi
          limits:
            cpu: 500m
            memory: 256Mi
        livenessProbe:
          httpGet:
            path: /healthz
            port: 8443
            scheme: HTTPS
        readinessProbe:
          httpGet:
            path: /healthz
            port: 8443
            scheme: HTTPS
      volumes:
      - name: certs
        secret:
          secretName: admission-webhook-cert-secret
```

---

## 六、实战场景

### 6.1 场景 1：镜像仓库管控

```go
// 强制所有镜像使用内部 registry
func validateImage(image string) error {
    internalRegistries := []string{
        "registry.example.com/",
        "harbor.example.com/",
    }
    
    for _, r := range internalRegistries {
        if strings.HasPrefix(image, r) {
            return nil
        }
    }
    
    // 允许官方镜像（特殊情况）
    officialImages := []string{
        "k8s.gcr.io/",
        "docker.io/library/",
    }
    for _, r := range officialImages {
        if strings.HasPrefix(image, r) {
            return nil
        }
    }
    
    return fmt.Errorf("image %s must be from internal registry", image)
}
```

### 6.2 场景 2：自动注入 Istio Sidecar

```go
// 注入 sidecar
func injectIstioSidecar(pod *corev1.Pod) []corev1.Container {
    if !hasSidecar(pod, "istio-proxy") {
        return []corev1.Container{
            {
                Name:  "istio-proxy",
                Image: "istio/proxyv2:1.20.0",
                Args:  []string{"proxy", "sidecar"},
                Ports: []corev1.ContainerPort{
                    {Name: "http-envoy-prom", ContainerPort: 15090},
                },
            },
        }
    }
    return nil
}
```

### 6.3 场景 3：阻止 privileged 容器（生产环境）

```go
func validatePodSecurity(pod *corev1.Pod) error {
    // 1. 禁止 privileged
    for _, c := range pod.Spec.Containers {
        if c.SecurityContext != nil &&
           c.SecurityContext.Privileged != nil &&
           *c.SecurityContext.Privileged {
            return fmt.Errorf("privileged container %s is not allowed in production", c.Name)
        }
    }
    
    // 2. 禁止 hostNetwork
    if pod.Spec.HostNetwork {
        return fmt.Errorf("hostNetwork is not allowed")
    }
    
    // 3. 禁止 hostPID/hostIPC
    if pod.Spec.HostPID {
        return fmt.Errorf("hostPID is not allowed")
    }
    if pod.Spec.HostIPC {
        return fmt.Errorf("hostIPC is not allowed")
    }
    
    // 4. 必须使用非 root 用户
    for _, c := range pod.Spec.Containers {
        if c.SecurityContext == nil ||
           c.SecurityContext.RunAsNonRoot == nil ||
           !*c.SecurityContext.RunAsNonRoot {
            return fmt.Errorf("container %s must set runAsNonRoot=true", c.Name)
        }
    }
    
    return nil
}
```

### 6.4 场景 4：多租户资源配额

```go
// 根据 namespace 限制资源
var namespaceQuotas = map[string]corev1.ResourceRequirements{
    "production": {
        Limits: corev1.ResourceList{
            corev1.ResourceCPU:    resource.MustParse("4"),
            corev1.ResourceMemory: resource.MustParse("8Gi"),
        },
    },
    "staging": {
        Limits: corev1.ResourceList{
            corev1.ResourceCPU:    resource.MustParse("2"),
            corev1.ResourceMemory: resource.MustParse("4Gi"),
        },
    },
    "dev": {
        Limits: corev1.ResourceList{
            corev1.ResourceCPU:    resource.MustParse("1"),
            corev1.ResourceMemory: resource.MustParse("2Gi"),
        },
    },
}

func validateResourceQuota(pod *corev1.Pod) error {
    quota, ok := namespaceQuotas[pod.Namespace]
    if !ok {
        return nil
    }
    
    for _, c := range pod.Spec.Containers {
        if c.Resources.Limits == nil {
            return fmt.Errorf("container %s in namespace %s must set resources.limits",
                c.Name, pod.Namespace)
        }
        
        // 检查 CPU limit
        if cpuLimit, ok := c.Resources.Limits[corev1.ResourceCPU]; ok {
            maxCPU := quota.Limits[corev1.ResourceCPU]
            if cpuLimit.Cmp(maxCPU) > 0 {
                return fmt.Errorf("container %s CPU limit %s exceeds namespace quota %s",
                    c.Name, cpuLimit.String(), maxCPU.String())
            }
        }
        
        // 检查 Memory limit（类似）
    }
    
    return nil
}
```

### 6.5 场景 5：自动注入 sidecar 注入（带 namespace 过滤）

```go
// 只在特定 namespace 注入 sidecar
func shouldInjectSidecar(namespace string) bool {
    enabledNamespaces := map[string]bool{
        "production": true,
        "staging":    true,
    }
    return enabledNamespaces[namespace]
}

func injectSidecarIfNeeded(pod *corev1.Pod) []corev1.Container {
    if !shouldInjectSidecar(pod.Namespace) {
        return nil
    }
    
    if hasContainer(pod, "istio-proxy") {
        return nil
    }
    
    return []corev1.Container{ /* istio sidecar */ }
}
```

---

## 七、高级主题

### 7.1 性能优化

```go
// Webhook 性能关键
// 1. 快速响应（避免慢逻辑）
// 2. 缓存（避免重复计算）
// 3. 异步处理（不阻塞 API Server）

// 缓存示例：缓存 namespace 元数据
type Cache struct {
    sync.RWMutex
    namespaces map[string]*NamespaceMeta
    ttl        time.Duration
}

func (c *Cache) Get(ns string) (*NamespaceMeta, bool) {
    c.RLock()
    defer c.RUnlock()
    if meta, ok := c.namespaces[ns]; ok {
        if time.Since(meta.fetchedAt) < c.ttl {
            return meta, true
        }
    }
    return nil, false
}

// 超时控制
ctx, cancel := context.WithTimeout(ctx, 3*time.Second)
defer cancel()
```

### 7.2 高可用

```yaml
# 1. 多副本 + Leader Election
apiVersion: apps/v1
kind: Deployment
metadata:
  name: admission-webhook
spec:
  replicas: 2   # 多副本
  template:
    spec:
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              topologyKey: kubernetes.io/hostname
              labelSelector:
                matchLabels:
                  app: admission-webhook

# 2. PodDisruptionBudget
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: admission-webhook-pdb
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: admission-webhook

# 3. 资源限制
containers:
- name: webhook
  resources:
    requests:
      cpu: 100m
      memory: 64Mi
    limits:
      cpu: 500m
      memory: 256Mi
```

### 7.3 failurePolicy 选择

```text
failurePolicy 选项：

Fail（默认）：Webhook 失败 → 拒绝请求
  - 严格模式
  - Webhook 故障会导致 API Server 无法处理请求
  - 适合关键操作

Ignore：Webhook 失败 → 放行请求
  - 宽松模式
  - 防止 Webhook 故障拖垮集群
  - 适合非关键操作

推荐：
  - 生产关键：Fail
  - 开发/测试：Ignore
  - 混合：根据命名空间配置
```

### 7.4 监控与日志

```go
import (
    "github.com/prometheus/client_golang/prometheus"
)

var (
    webhookRequests = prometheus.NewCounterVec(
        prometheus.CounterOpts{
            Name: "admission_webhook_requests_total",
            Help: "Total admission webhook requests",
        },
        []string{"type", "decision", "code"},
    )
    
    webhookDuration = prometheus.NewHistogramVec(
        prometheus.HistogramOpts{
            Name:    "admission_webhook_duration_seconds",
            Help:    "Admission webhook request duration",
            Buckets: prometheus.DefBuckets,
        },
        []string{"type", "decision"},
    )
)

func recordMetrics(decision string, duration time.Duration, isMutating bool) {
    typ := "validating"
    if isMutating {
        typ = "mutating"
    }
    webhookRequests.WithLabelValues(typ, decision, "200").Inc()
    webhookDuration.WithLabelValues(typ, decision).Observe(duration.Seconds())
}
```

```yaml
# Prometheus ServiceMonitor
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: admission-webhook
  namespace: webhook-system
spec:
  selector:
    matchLabels:
      app: admission-webhook
  endpoints:
  - port: metrics
    interval: 30s
    path: /metrics
```

### 7.5 调试技巧

```bash
# 1. 查看 Webhook 配置
kubectl get mutatingwebhookconfigurations
kubectl get validatingwebhookconfigurations

# 2. 查看 Webhook 详情
kubectl get mutatingwebhookconfigurations my-webhook -o yaml

# 3. 查看 Webhook Service
kubectl get svc -n webhook-system

# 4. 测试 Webhook
kubectl create deployment test --image=nginx --dry-run=server
# 启用 debug 查看请求/响应
kubectl logs -n webhook-system deploy/admission-webhook -f

# 5. 临时禁用 Webhook
kubectl delete mutatingwebhookconfiguration my-webhook
# 操作完后恢复
kubectl apply -f mutating-webhook.yaml
```

---

## 八、最佳实践

### 8.1 设计原则

```text
1. 单一职责
   - 一个 Webhook 对应一类规则
   - 避免"万能 Webhook"

2. 性能优先
   - Webhook 必须快速响应
   - 默认 < 100ms
   - 超时时间 5-10s

3. 幂等性
   - 同一请求多次处理结果相同
   - Webhook 可重入

4. 安全性
   - TLS 加密通信
   - RBAC 最小权限
   - 失败不影响核心

5. 可观测
   - 暴露 Prometheus 指标
   - 详细日志
   - 追踪请求 ID
```

### 8.2 性能与稳定性检查清单

```text
- [ ] Webhook 响应时间 < 1s（典型 < 100ms）
- [ ] timeoutSeconds 合理设置（5-10s）
- [ ] failurePolicy 明确（Fail 或 Ignore）
- [ ] 多副本 + Leader Election（可选）
- [ ] 健康检查 /healthz、/readyz
- [ ] Prometheus 指标暴露
- [ ] 日志结构化
- [ ] 资源 limits 设置
- [ ] PDB（PodDisruptionBudget）
- [ ] 证书自动管理（cert-manager）
- [ ] 灰度发布（先 1 副本验证）
- [ ] 错误注入测试
```

### 8.3 调试命令速记

```text
# 查看所有 Webhook
kubectl get mutatingwebhookconfigurations,validatingwebhookconfigurations

# 查看 Webhook 详细配置
kubectl get <type> <name> -o yaml

# 临时禁用 Webhook（不删除）
kubectl edit <type> <name>
# 设置 failurePolicy: Ignore

# 恢复
kubectl rollout restart deployment/admission-webhook -n webhook-system

# 调试 Pod
kubectl exec -it <pod> -n webhook-system -- sh
ls /etc/webhook/certs
cat /var/log/webhook.log

# 测试 Webhook 连接
curl -k https://<webhook-service>.<ns>.svc/healthz
```

---

## 九、参考资源

```text
- K8s Admission Webhook: https://kubernetes.io/docs/reference/access-authn-authz/admission-controllers/
- Kubebuilder Webhook: https://book.kubebuilder.io/cronjob-tutorial/webhook-implementation.html
- controller-runtime Webhook: https://book.kubebuilder.io/reference/admission-webhook.html
- cert-manager: https://cert-manager.io/docs/
- Admission Review API: https://kubernetes.io/docs/reference/access-authn-authz/admission-review/
- 实战参考: https://github.com/kubernetes-sigs/kubebuilder/tree/master/docs/book/src

```
## 速记卡

Admission Webhook = K8s API 拦截器
两种类型：Mutating（修改）/ Validating（验证）
调用顺序：AuthN → AuthZ → Mutating → Validating → Default → 持久化
关键字段：rules（匹配规则）、failurePolicy（Fail/Ignore）、sideEffects
必须 TLS：用 cert-manager 自动管理证书
Pod 必须能访问 Webhook Service
性能要求：< 1 秒（< 100ms 为佳）
生产配置：Fail + 多副本 + 健康检查 + 监控
最常见场景：镜像仓库管控、注入 sidecar、安全合规
