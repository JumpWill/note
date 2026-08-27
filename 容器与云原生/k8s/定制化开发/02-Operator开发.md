# Operator 开发（基于 Operator SDK）

## 一、为什么要做 Operator

### 1.1 业务背景

```text
Operator 是 K8s 扩展能力的核心模式。
本质：将运维领域知识（Operator 模式）编码到软件中。

现实场景：
  - 自研数据库：部署、扩缩容、备份、升级
  - 消息中间件：Kafka 集群、RocketMQ 集群
  - 缓存：Redis Cluster、Memcached
  - 存储：Ceph、MinIO
  - 监控：Prometheus 联邦集群
  - 大数据：Spark、Flink、Elasticsearch

Operator 让 K8s 不只是 "调度 Pod"，而是 "运维应用"。
```

### 1.2 Operator 核心价值

```text
1. 自动化运维
   - 部署、扩缩容、备份、升级
   - 故障自愈
   - 无人值守

2. 领域知识编码
   - DBA 的运维经验 → 代码
   - SRE 的故障处理 → 代码
   - 业务专家的部署流程 → 代码

3. 与 K8s 生态融合
   - kubectl get/apply/delete
   - 监控、告警、日志
   - 滚动升级、灰度发布

4. 标准化运维
   - 同一类应用统一管理
   - 减少运维错误
   - 提升效率
```

### 1.3 Operator vs 普通 Controller

```text
┌─────────────────┬────────────────────┐
│  普通 Controller │  Operator           │
├─────────────────┼────────────────────┤
│  通用逻辑        │  领域专业逻辑      │
│  Deployment     │  MySQL Operator   │
│  副本管理        │  部署+主从+备份  │
│                 │  +升级+故障恢复  │
│  通用         │  专业              │
│  单一          │  复杂              │
└─────────────────┴────────────────────┘
```

---

## 二、Operator 核心概念

### 2.1 Operator 模式

```text
Operator = CRD + Controller + 运维领域知识

  ┌─────────────────────────────────────────┐
  │  CRD（自定义资源）                     │
  │  - 定义资源 schema                     │
  │  - 用户的期望状态                      │
  └────────────────┬────────────────────────┘
                   │
                   ↓ reconcile
                   │
  ┌─────────────────────────────────────────┐
  │  Controller（自定义控制器）             │
  │  - watch CR                            │
  │  - 调谐 spec → status                 │
  │  - 管理相关 K8s 资源                    │
  └────────────────┬────────────────────────┘
                   │
                   ↓ operate
                   │
  ┌─────────────────────────────────────────┐
  │  K8s 资源（Pod/Service/ConfigMap...）  │
  │  业务资源（数据库实例/消息队列...）    │
  └─────────────────────────────────────────┘
```

### 2.2 Operator 核心循环

```text
Reconcile Loop（调谐循环）：

  ┌────────────────────────────────────┐
  │  1. Watch CR                        │
  │     （变更时触发）                  │
  └────────────┬───────────────────────┘
               │
               ▼
  ┌────────────────────────────────────┐
  │  2. Get 当前状态                    │
  │     - spec（期望）                  │
  │     - status（实际）                │
  │     - 关联资源                      │
  └────────────┬───────────────────────┘
               │
               ▼
  ┌────────────────────────────────────┐
  │  3. Diff 分析差异                   │
  │     - spec.replicas vs actual     │
  │     - spec.image vs deployment     │
  └────────────┬───────────────────────┘
               │
               ▼
  ┌────────────────────────────────────┐
  │  4. 调谐（Reconcile）               │
  │     - 创建缺失资源                  │
  │     - 更新不匹配资源                │
  │     - 删除多余资源                  │
  └────────────┬───────────────────────┘
               │
               ▼
  ┌────────────────────────────────────┐
  │  5. Update status                   │
  │     - phase                         │
  │     - conditions                   │
  │     - 业务状态                       │
  └────────────┬───────────────────────┘
               │
               ▼
  ┌────────────────────────────────────┐
  │  6. Requeue（再次调谐）             │
  │     - 定期同步                       │
  │     - 事件触发                       │
  └────────────────────────────────────┘
```

---

## 三、Operator SDK 与 Kubebuilder

### 3.1 工具对比

```text
┌─────────────────┬──────────────────────┐
│  工具            │  用途                │
├─────────────────┼──────────────────────┤
│  Kubebuilder    │  脚手架、生成代码     │
│  Operator SDK   │  高级特性、生命周期  │
│  controller-     │  运行时库            │
│  runtime         │                     │
│  kustomize      │  部署 Operator       │
└─────────────────┴──────────────────────┘

推荐使用：
  - 入门 → Kubebuilder
  - 生产 → Operator SDK + Kubebuilder
```

### 3.2 Kubebuilder 初始化项目

```bash
# 安装 kubebuilder
curl -L -o kubebuilder "https://go.kubebuilder.io/latest-linux/amd64"
chmod +x kubebuilder
mv kubebuilder /usr/local/bin/

# 初始化项目
mkdir my-operator && cd my-operator
go mod init github.com/example/my-operator

kubebuilder init \
  --domain example.com \
  --repo github.com/example/my-operator \
  --project-name my-operator

# 创建 API
kubebuilder create api \
  --group database \
  --version v1 \
  --kind MySQLCluster

# 项目结构
my-operator/
├── api/
│   └── v1/
│       ├── groupversion_info.go
│       └── mysqlcluster_types.go
├── internal/controller/
│   ├── mysqlcluster_controller.go
│   └── suite_test.go
├── cmd/
│   ├── main.go
│   └── ...
├── config/
│   ├── crd/
│   │   └── bases/
│   │       └── database.example.com_mysqlclusters.yaml
│   ├── rbac/
│   ├── manager/
│   └── ...
├── Dockerfile
├── Makefile
├── PROJECT
└── go.mod
```

### 3.3 Operator SDK 初始化（更完整）

```bash
# 安装 operator-sdk
curl -L -o operator-sdk "https://github.com/operator-framework/operator-sdk/releases/latest/download/operator-sdk_linux_amd64"
chmod +x operator-sdk
mv operator-sdk /usr/local/bin/

# 初始化项目
operator-sdk init \
  --domain example.com \
  --repo github.com/example/my-operator \
  --project-name my-operator \
  --plugins go/v4

# 创建 API + Controller
operator-sdk create api \
  --group database \
  --version v1 \
  --kind MySQLCluster \
  --resource \
  --controller

# 启用 Webhook（可选）
operator-sdk create webhook \
  --group database \
  --version v1 \
  --kind MySQLCluster \
  --defaulting \
  --programmatic-validation
```

---

## 四、Operator 开发完整流程

### 4.1 定义 CRD（types.go）

```go
// api/v1/mysqlcluster_types.go
package v1

import (
    "time"
    metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

// MySQLCluster 是 MySQL Cluster 资源的 Schema
type MySQLCluster struct {
    metav1.TypeMeta   `json:",inline"`
    metav1.ObjectMeta `json:"metadata,omitempty"`

    Spec   MySQLClusterSpec   `json:"spec,omitempty"`
    Status MySQLClusterStatus `json:"status,omitempty"`
}

// MySQLClusterSpec 定义期望状态
type MySQLClusterSpec struct {
    // 版本（必填）
    Version string `json:"version"`

    // 副本数（默认 3）
    Replicas *int32 `json:"replicas,omitempty"`

    // 存储配置（必填）
    Storage StorageSpec `json:"storage"`

    // 资源限制
    Resources ResourceRequirements `json:"resources,omitempty"`

    // 配置参数
    Config *MySQLConfig `json:"config,omitempty"`

    // 主从配置
    Replication *ReplicationConfig `json:"replication,omitempty"`

    // 备份策略
    Backup *BackupConfig `json:"backup,omitempty"`
}

// StorageSpec 存储配置
type StorageSpec struct {
    Size         string `json:"size"`
    StorageClass string `json:"storageClass,omitempty"`
}

// MySQLConfig MySQL 配置
type MySQLConfig struct {
    InnoDBBufferPoolSize string            `json:"innodbBufferPoolSize,omitempty"`
    MaxConnections       int32             `json:"maxConnections,omitempty"`
    SlowQueryLog         bool              `json:"slowQueryLog,omitempty"`
    CharacterSet         string            `json:"characterSet,omitempty"`
}

// ReplicationConfig 主从配置
type ReplicationConfig struct {
    Mode              string `json:"mode"`              // GTID/ROW
    SemiSync          bool   `json:"semiSync"`
    BackupTimeoutSec  int32  `json:"backupTimeoutSec,omitempty"`
}

// BackupConfig 备份配置
type BackupConfig struct {
    Enabled   bool          `json:"enabled"`
    Schedule  string        `json:"schedule,omitempty"`  // cron
    Retention string        `json:"retention,omitempty"`  // 7d
    Method    string        `json:"method,omitempty"`   // xtrabackup/mysqldump
}

// MySQLClusterStatus 定义实际状态
type MySQLClusterStatus struct {
    // 阶段：Pending/Creating/Running/Failed/Upgrading
    Phase string `json:"phase,omitempty"`

    // 已就绪副本数
    ReadyReplicas int32 `json:"readyReplicas"`

    // 服务入口
    Endpoints []Endpoint `json:"endpoints,omitempty"`

    // 当前主节点
    PrimaryPod string `json:"primaryPod,omitempty"`

    // 副本节点
    ReplicaPods []string `json:"replicaPods,omitempty"`

    // 备份状态
    LastBackup string `json:"lastBackup,omitempty"`

    // 观察到的 generation
    ObservedGeneration int64 `json:"observedGeneration,omitempty"`

    // 条件
    Conditions []metav1.Condition `json:"conditions,omitempty"`
}

type Endpoint struct {
    Name  string `json:"name"`
    Host string `json:"host"`
    Port int32  `json:"port"`
}

// +kubebuilder:object:root=true
// +kubebuilder:subresource:status
// +kubebuilder:subresource:scale:specReplicas=.spec.replicas,statusReplicas=.status.readyReplicas
// +kubebuilder:printcolumn:name="Version",type=string,JSONPath=`.spec.version`
// +kubebuilder:printcolumn:name="Replicas",type=integer,JSONPath=`.spec.replicas`
// +kubebuilder:printcolumn:name="Ready",type=integer,JSONPath=`.status.readyReplicas`
// +kubebuilder:printcolumn:name="Phase",type=string,JSONPath=`.status.phase`
// +kubebuilder:printcolumn:name="Age",type=date,JSONPath=`.metadata.creationTimestamp`
type MySQLCluster struct {
    metav1.TypeMeta   `json:",inline"`
    metav1.ObjectMeta `json:"metadata,omitempty"`

    Spec   MySQLClusterSpec   `json:"spec,omitempty"`
    Status MySQLClusterStatus `json:"status,omitempty"`
}

// +kubebuilder:object:root=true
type MySQLClusterList struct {
    metav1.TypeMeta `json:",inline"`
    metav1.ListMeta `json:"metadata,omitempty"`
    Items           []MySQLCluster `json:"items"`
}

func init() {
    SchemeBuilder.Register(&MySQLCluster{}, &MySQLClusterList{})
}
```

### 4.2 CRD 生成（Webhook）

```go
// api/v1/mysqlcluster_webhook.go
package v1

import (
    "fmt"

    "k8s.io/apimachinery/pkg/runtime"
    ctrl "sigs.k8s.io/controller-runtime"
    logf "sigs.k8s.io/controller-runtime/pkg/log"
    "sigs.k8s.io/controller-runtime/pkg/webhook"
    "sigs.k8s.io/controller-runtime/pkg/webhook/admission"

    apierrors "k8s.io/apimachinery/pkg/api/errors"
)

func (r *MySQLCluster) SetupWebhookWithManager(mgr ctrl.Manager) error {
    return ctrl.NewWebhookManagedBy(mgr).
        For(r).
        Complete()
}

// +kubebuilder:webhook:path=/mutate-database-example-com-v1-mysqlcluster,mutating=true,failurePolicy=fail,sideEffects=None,groups=database.example.com,resources=mysqlclusters,verbs=create;update,versions=v1,name=mmysqlcluster.kb.io,admissionReviewVersions=v1

var _ webhook.Validator = &MySQLClusterCustomValidator{}

// MySQLClusterCustomValidator 验证 webhook
type MySQLClusterCustomValidator struct{}

func (webhook *MySQLClusterCustomValidator) ValidateCreate(ctx context.Context, obj *MySQLCluster) (admission.Warnings, error) {
    return validate(obj)
}

func (webhook *MySQLClusterCustomValidator) ValidateUpdate(ctx context.Context, oldObj, newObj *MySQLCluster) (admission.Warnings, error) {
    return validate(newObj)
}

func validate(mc *MySQLCluster) (admission.Warnings, error) {
    var warnings admission.Warnings

    // 校验：副本数
    if mc.Spec.Replicas != nil {
        if *mc.Spec.Replicas < 1 {
            return warnings, apierrors.NewBadRequest(
                fmt.Sprintf("replicas must be >= 1, got %d", *mc.Spec.Replicas))
        }
        if *mc.Spec.Replicas > 10 {
            return warnings, apierrors.NewBadRequest(
                "replicas must be <= 10")
        }
    }

    // 校验：版本
    validVersions := map[string]bool{"5.7": true, "8.0": true}
    if !validVersions[mc.Spec.Version] {
        return warnings, apierrors.NewBadRequest(
            fmt.Sprintf("version must be 5.7 or 8.0, got %s", mc.Spec.Version))
    }

    return warnings, nil
}
```

### 4.3 Controller 主逻辑

```go
// internal/controller/mysqlcluster_controller.go
package controller

import (
    "context"
    "fmt"
    "time"

    appsv1 "k8s.io/api/apps/v1"
    corev1 "k8s.io/api/core/v1"
    "k8s.io/apimachinery/pkg/api/errors"
    "k8s.io/apimachinery/pkg/api/resource"
    metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
    "k8s.io/apimachinery/pkg/runtime"
    "k8s.io/apimachinery/pkg/types"
    ctrl "sigs.k8s.io/controller-runtime"
    "sigs.k8s.io/controller-runtime/pkg/client"
    "sigs.k8s.io/controller-runtime/pkg/controller/controllerutil"
    "sigs.k8s.io/controller-runtime/pkg/log"

    mysqlv1 "github.com/example/my-operator/api/v1"
)

const (
    finalizerName    = "mysql.example.com/finalizer"
    requeueAfterDelay = 30 * time.Second
)

type MySQLClusterReconciler struct {
    client.Client
    Scheme *runtime.Scheme
}

// +kubebuilder:rbac:groups=database.example.com,resources=mysqlclusters,verbs=get;list;watch;create;update;patch;delete
// +kubebuilder:rbac:groups=database.example.com,resources=mysqlclusters/status,verbs=get;update;patch
// +kubebuilder:rbac:groups=database.example.com,resources=mysqlclusters/finalizers,verbs=update
// +kubebuilder:rbac:groups=apps,resources=statefulsets,verbs=get;list;watch;create;update;patch;delete
// +kubebuilder:rbac:groups=core,resources=services,verbs=get;list;watch;create;update;patch;delete
// +kubebuilder:rbac:groups=core,resources=configmaps,verbs=get;list;watch;create;update;patch;delete
// +kubebuilder:rbac:groups=core,resources=secrets,verbs=get;list;watch;create;update;patch;delete
// +kubebuilder:rbac:groups=core,resources=pods,verbs=get;list;watch
// +kubebuilder:rbac:groups=core,resources=services,verbs=get;list;watch;create;update;patch;delete

func (r *MySQLClusterReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
    log := log.FromContext(ctx).WithValues("mysqlcluster", req.NamespacedName)

    // 1. 获取 CR
    mc := &mysqlv1.MySQLCluster{}
    if err := r.Get(ctx, req.NamespacedName, mc); err != nil {
        return ctrl.Result{}, client.IgnoreNotFound(err)
    }

    // 2. 处理删除
    if !mc.DeletionTimestamp.IsZero() {
        return r.reconcileDelete(ctx, mc)
    }

    // 3. 添加 Finalizer
    if !controllerutil.ContainsFinalizer(mc, finalizerName) {
        controllerutil.AddFinalizer(mc, finalizerName)
        return ctrl.Result{}, r.Update(ctx, mc)
    }

    // 4. 业务 reconcile 逻辑
    return r.reconcileNormal(ctx, mc, log)
}

func (r *MySQLClusterReconciler) reconcileNormal(
    ctx context.Context, mc *mysqlv1.MySQLCluster, log logr.Logger,
) (ctrl.Result, error) {

    // 1. 创建/更新 StatefulSet
    if err := r.reconcileStatefulSet(ctx, mc); err != nil {
        return ctrl.Result{}, err
    }

    // 2. 创建/更新 Service
    if err := r.reconcileService(ctx, mc); err != nil {
        return ctrl.Result{}, err
    }

    // 3. 创建/更新 ConfigMap
    if err := r.reconcileConfigMap(ctx, mc); err != nil {
        return ctrl.Result{}, err
    }

    // 4. 创建/更新 Secret
    if err := r.reconcileSecret(ctx, mc); err != nil {
        return ctrl.Result{}, err
    }

    // 5. 更新 status
    if err := r.updateStatus(ctx, mc); err != nil {
        return ctrl.Result{}, err
    }

    // 6. 定期 reconcile
    return ctrl.Result{RequeueAfter: requeueAfterDelay}, nil
}

func (r *MySQLClusterReconciler) reconcileStatefulSet(
    ctx context.Context, mc *mysqlv1.MySQLCluster,
) error {
    sts := &appsv1.StatefulSet{
        ObjectMeta: metav1.ObjectMeta{
            Name:      mc.Name,
            Namespace: mc.Namespace,
        },
        Spec: appsv1.StatefulSetSpec{
            Replicas: mc.Spec.Replicas,
            Selector: &metav1.LabelSelector{
                MatchLabels: r.labelsForMySQLCluster(mc.Name),
            },
            Template: corev1.PodTemplateSpec{
                ObjectMeta: metav1.ObjectMeta{
                    Labels: r.labelsForMySQLCluster(mc.Name),
                },
                Spec: corev1.PodSpec{
                    Containers: []corev1.Container{
                        {
                            Name:  "mysql",
                            Image: fmt.Sprintf("mysql:%s", mc.Spec.Version),
                            Ports: []corev1.ContainerPort{
                                {Name: "mysql", ContainerPort: 3306},
                            },
                            Env: []corev1.EnvVar{
                                {Name: "MYSQL_ROOT_PASSWORD",
                                    ValueFrom: &corev1.EnvVarSource{
                                        SecretKeyRef: &corev1.SecretKeySelector{
                                            LocalObjectReference: corev1.LocalObjectReference{Name: mc.Name + "-secret"},
                                            Key: "password",
                                        },
                                    },
                                },
                            },
                            Resources: r.resourceRequirements(mc),
                            VolumeMounts: r.volumeMounts(mc),
                        },
                    },
                },
            },
            VolumeClaimTemplates: r.volumeClaimTemplates(mc),
        },
    }

    // 应用 owner reference
    if err := controllerutil.SetControllerReference(mc, sts, r.Scheme); err != nil {
        return err
    }

    // 创建或更新
    found := &appsv1.StatefulSet{}
    err := r.Get(ctx, types.NamespacedName{Name: sts.Name, Namespace: sts.Namespace}, found)
    if err != nil && errors.IsNotFound(err) {
        return r.Create(ctx, sts)
    } else if err != nil {
        return err
    }
    found.Spec = sts.Spec
    return r.Update(ctx, found)
}

// 其他 reconcile 方法（reconcileService、reconcileConfigMap 等）类似
// 省略...

func (r *MySQLClusterReconciler) reconcileDelete(
    ctx context.Context, mc *mysqlv1.MySQLCluster,
) (ctrl.Result, error) {
    if controllerutil.ContainsFinalizer(mc, finalizerName) {
        // 清理外部资源（如调用 API 删除数据库实例）
        if err := r.cleanupExternalResources(ctx, mc); err != nil {
            return ctrl.Result{}, err
        }
        // 移除 Finalizer
        controllerutil.RemoveFinalizer(mc, finalizerName)
        return ctrl.Result{}, r.Update(ctx, mc)
    }
    return ctrl.Result{}, nil
}

func (r *MySQLClusterReconciler) SetupWithManager(mgr ctrl.Manager) error {
    return ctrl.NewControllerManagedBy(mgr).
        For(&mysqlv1.MySQLCluster{}).
        WithOptions(controller.Options{
            MaxConcurrentReconciles: 3,
            RateLimiter: workqueue.NewItemExponentialFailureRateLimiter(
                5*time.Second, 60*time.Second),
        }).
        Owns(&appsv1.StatefulSet{}).
        Owns(&corev1.Service{}).
        Owns(&corev1.ConfigMap{}).
        Owns(&corev1.Secret{}).
        Complete(r)
}

// labelsForMySQLCluster 生成标准标签
func (r *MySQLClusterReconciler) labelsForMySQLCluster(name string) map[string]string {
    return map[string]string{
        "app":      "mysql",
        "cluster": name,
    }
}
```

### 4.4 main.go 入口

```go
// cmd/main.go
package main

import (
    "flag"
    "os"

    "k8s.io/apimachinery/pkg/runtime"
    utilruntime "k8s.io/apimachinery/pkg/util/runtime"
    clientgoscheme "k8s.io/client-go/kubernetes/scheme"
    ctrl "sigs.k8s.io/controller-runtime"
    "sigs.k8s.io/controller-runtime/pkg/cache"
    "sigs.k8s.io/controller-runtime/pkg/healthz"
    "sigs.k8s.io/controller-runtime/pkg/log/zap"
    "sigs.k8s.io/controller-runtime/pkg/metrics/server"
    "sigs.k8s.io/controller-runtime/pkg/webhook"

    databasev1 "github.com/example/my-operator/api/v1"
    "github.com/example/my-operator/internal/controller"
)

var (
    scheme   = runtime.NewScheme()
    setupLog = ctrl.Log.WithName("setup")
)

func init() {
    utilruntime.Must(clientgoscheme.AddToScheme(scheme))
    utilruntime.Must(databasev1.AddToScheme(scheme))
}

func main() {
    var metricsAddr         string
    var enableLeaderElection bool
    var probeAddr            string

    flag.StringVar(&metricsAddr, "metrics-bind-address", ":8080", "...")
    flag.StringVar(&probeAddr, "health-probe-bind-address", ":8081", "...")
    flag.BoolVar(&enableLeaderElection, "leader-elect", false, "...")

    opts := ctrl.Options{
        Scheme:                 scheme,
        Metrics:                metricsserver.Options{BindAddress: metricsAddr},
        HealthProbeBindAddress: probeAddr,
        LeaderElection:         enableLeaderElection,
        LeaderElectionID:       "my-operator-leader",
    }

    mgr, err := ctrl.NewManager(ctrl.GetConfigOrDie(), opts)
    if err != nil {
        setupLog.Error(err, "unable to start manager")
        os.Exit(1)
    }

    if err = (&controller.MySQLClusterReconciler{
        Client: mgr.GetClient(),
        Scheme: mgr.GetScheme(),
    }).SetupWithManager(mgr); err != nil {
        setupLog.Error(err, "unable to create controller")
        os.Exit(1)
    }

    if err = (&databasev1.MySQLCluster{}).SetupWebhookWithManager(mgr); err != nil {
        setupLog.Error(err, "unable to create webhook")
        os.Exit(1)
    }

    if err := mgr.AddHealthzCheck("healthz", healthz.Ping); err != nil {
        setupLog.Error(err, "unable to set up health check")
        os.Exit(1)
    }
    if err := mgr.AddReadyzCheck("readyz", healthz.Ping); err != nil {
        setupLog.Error(err, "unable to set up ready check")
        os.Exit(1)
    }

    setupLog.Info("starting manager")
    if err := mgr.Start(ctrl.SetupSignalHandler()); err != nil {
        setupLog.Error(err, "problem running manager")
        os.Exit(1)
    }
}
```

---

## 五、Operator 部署与运维

### 5.1 构建镜像

```bash
# 1. 生成 CRD/部署清单
make manifests

# 2. 构建镜像
make docker-build IMG=registry.example.com/my-operator:v1.0.0

# 3. 推送镜像
make docker-push IMG=registry.example.com/my-operator:v1.0.0

# 4. 部署
make deploy IMG=registry.example.com/my-operator:v1.0.0
```

### 5.2 生成的部署清单

```yaml
# config/manager/manager.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: controller-manager
  namespace: system
  labels:
    app.kubernetes.io/name: my-operator
    app.kubernetes.io/managed-by: kustomize
spec:
  replicas: 1
  selector:
    matchLabels:
      control-plane: controller-manager
  template:
    metadata:
      labels:
        control-plane: controller-manager
    spec:
      containers:
      - args:
        - --secure-metrics-server
        - --health-probe-bind-address=:8081
        - --metrics-bind-address=:8080
        - --leader-elect
        command:
        - /manager
        image: registry.example.com/my-operator:v1.0.0
        env:
        - name: POD_NAMESPACE
          valueFrom:
            fieldRef:
              fieldPath: metadata.namespace
        livenessProbe:
          httpGet:
            path: /healthz
            port: 8081
        readinessProbe:
          httpGet:
            path: /readyz
            port: 8081
        resources:
          limits:
            cpu: 500m
            memory: 256Mi
          requests:
            cpu: 100m
            memory: 64Mi
      serviceAccountName: controller-manager
      terminationGracePeriodSeconds: 10
```

### 5.3 CRD 安装

```bash
# 安装 CRD
make install
# 等价于：
kubectl apply -f config/crd/bases/database.example.com_mysqlclusters.yaml
```

### 5.4 创建自定义资源

```bash
# 创建示例 CR
cat <<EOF | kubectl apply -f -
apiVersion: database.example.com/v1
kind: MySQLCluster
metadata:
  name: my-production-db
  namespace: production
spec:
  version: "8.0"
  replicas: 3
  storage:
    size: 100Gi
    storageClass: ssd
  resources:
    cpu: "2"
    memory: 8Gi
  config:
    innodbBufferPoolSize: 4G
    maxConnections: 1000
  replication:
    mode: GTID
    semiSync: true
EOF

# 查看状态
kubectl get mysqlcluster
# NAME              VERSION   REPLICAS   READY   PHASE     AGE
# my-production-db  8.0       3          3       Running   5m

kubectl describe mysqlcluster my-production-db
```

---

## 六、Operator 高级特性

### 6.1 Webhook

```go
// 默认 webhook（注入默认值）
func (r *MySQLCluster) Default() {
    if r.Spec.Replicas == nil {
        r.Spec.Replicas = new(int32)
        *r.Spec.Replicas = 3
    }
    if r.Spec.Storage.StorageClass == "" {
        r.Spec.Storage.StorageClass = "standard"
    }
}

// 验证 webhook（见前面代码）

// 转换 webhook（多版本）
func (r *MySQLCluster) ConvertTo(dst runtime.Object) error {
    switch dst.(type) {
    case *MySQLClusterv1beta1:
        // 从 v1 转换为 v1beta1
    case *MySQLCluster:
        // 同版本
    }
    return nil
}
```

### 6.2 Leader Election

```go
// 多副本 Operator 需要 Leader Election
opts := ctrl.Options{
    LeaderElection:          true,
    LeaderElectionID:        "my-operator-leader",
    LeaderElectionNamespace: "my-operator-system",
}

// 只有 Leader 才会执行 reconcile
// 其他副本在等待
```

### 6.3 高级 Reconcile 模式

```go
// Reconcile 时只关心自己拥有的资源
func (r *MySQLClusterReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
    mc := &mysqlv1.MySQLCluster{}
    if err := r.Get(ctx, req.NamespacedName, mc); err != nil {
        return ctrl.Result{}, client.IgnoreNotFound(err)
    }

    // 设置 owner reference（关键！）
    // 这样当 CR 删除时，所有者属资源会自动删除
    if err := controllerutil.SetControllerReference(mc, mc, r.Scheme); err != nil {
        return ctrl.Result{}, err
    }

    // 调谐各子资源
    return r.reconcile(ctx, mc)
}

// 使用 Owns() 自动 watch
func (r *MySQLClusterReconciler) SetupWithManager(mgr ctrl.Manager) error {
    return ctrl.NewControllerManagedBy(mgr).
        For(&mysqlv1.MySQLCluster{}).  // watch 主资源
        Owns(&appsv1.StatefulSet{}).     // 自动 watch 拥有者
        Owns(&corev1.Service{}).
        Complete(r)
}
```

### 6.4 优雅处理删除

```go
func (r *MySQLClusterReconciler) reconcileDelete(
    ctx context.Context, mc *mysqlv1.MySQLCluster,
) (ctrl.Result, error) {
    if !controllerutil.ContainsFinalizer(mc, finalizerName) {
        return ctrl.Result{}, nil
    }

    // 执行清理逻辑
    if err := r.cleanupExternalResources(ctx, mc); err != nil {
        return ctrl.Result{Requeue: true}, err
    }

    // 移除 Finalizer（必须在最后）
    controllerutil.RemoveFinalizer(mc, finalizerName)
    return ctrl.Result{}, r.Update(ctx, mc)
}
```

### 6.5 高级 Status 管理

```go
func (r *MySQLClusterReconciler) updateStatus(
    ctx context.Context, mc *mysqlv1.MySQLCluster,
) error {
    // 获取实际状态
    sts := &appsv1.StatefulSet{}
    err := r.Get(ctx, types.NamespacedName{
        Name:      mc.Name,
        Namespace: mc.Namespace,
    }, sts)
    if err != nil {
        return err
    }

    // 计算就绪副本数
    readyReplicas := sts.Status.ReadyReplicas

    // 设置 Phase
    if readyReplicas == *mc.Spec.Replicas {
        mc.Status.Phase = "Running"
    } else if readyReplicas > 0 {
        mc.Status.Phase = "Creating"
    } else {
        mc.Status.Phase = "Pending"
    }

    // 设置 Conditions
    mc.Status.Conditions = []metav1.Condition{
        {
            Type:               "Ready",
            Status:             metav1.ConditionTrue,
            LastTransitionTime: metav1.Now(),
            Reason:             "AllPodsReady",
            Message:            fmt.Sprintf("%d/%d pods ready", readyReplicas, *mc.Spec.Replicas),
        },
    }

    mc.Status.ReadyReplicas = readyReplicas
    mc.Status.ObservedGeneration = mc.Generation

    return r.Status().Update(ctx, mc)
}
```

---

## 七、实战案例

### 7.1 Redis Cluster Operator

```go
// RedisCluster API
type RedisClusterSpec struct {
    Replicas     int32  `json:"replicas"`        // 6, 9, 12...
    ClusterMode string `json:"clusterMode"`    // cluster/sentinel
    Resources    ResourceRequirements `json:"resources"`
    
    // Redis 配置
    RedisVersion string `json:"redisVersion"`  // 7.2, 7.0...
    MaxMemory    string `json:"maxMemory"`     // 1Gi, 4Gi
    
    // 集群配置
    Persistence *PersistenceConfig `json:"persistence,omitempty"`
    Sentinel    *SentinelConfig   `json:"sentinel,omitempty"`
}

// Controller 主要逻辑
// 1. 创建 Redis StatefulSet
// 2. 等待 Pod Ready
// 3. 执行 redis-cli --cluster create
// 4. 更新 status
```

### 7.2 Kafka Cluster Operator

```go
// KafkaCluster API
type KafkaClusterSpec struct {
    Brokers      int32  `json:"brokers"`         // 3, 5, 7...
    KafkaVersion string `json:"kafkaVersion"`   // 3.6
    Storage       StorageSpec `json:"storage"`
    
    // 关键配置
    Controller   *KafkaController `json:"controller,omitempty"`  // KRaft/ZK
    Listeners    *ListenersConfig `json:"listeners,omitempty"`
    Security     *SecurityConfig  `json:"security,omitempty"`
    
    // 高级特性
    MirrorMaker  *MirrorConfig `json:"mirrorMaker,omitempty"`
    TieredStorage *TieredStorageConfig `json:"tieredStorage,omitempty"`
}
```

### 7.3 Elasticsearch Operator

```go
// ElasticsearchCluster API
type ElasticsearchClusterSpec struct {
    Version  string `json:"version"`         // 8.x
    Nodes    []NodeSpec `json:"nodes"`        // master/data/ingest/coordinating
    
    // 每种节点角色单独配置
    Node NodeSpec `json:",inline"`
}

type NodeSpec struct {
    Replicas  int32             `json:"replicas"`
    Roles     []string          `json:"roles"`     // master, data, ingest
    Resources ResourceRequirements `json:"resources"`
    Storage   StorageSpec       `json:"storage"`
    NodeSelector map[string]string `json:"nodeSelector,omitempty"`
}
```

---

## 八、Operator 测试与调试

### 8.1 单元测试

```go
var _ = Describe("MySQLCluster Controller", func() {
    Context("When creating a new MySQLCluster", func() {
        It("Should create a StatefulSet", func() {
            By("Creating a new MySQLCluster")
            mc := &MySQLCluster{
                ObjectMeta: metav1.ObjectMeta{
                    Name:      "test-mysql",
                    Namespace: "default",
                },
                Spec: MySQLClusterSpec{
                    Version:  "8.0",
                    Replicas: ptr.To[int32](3),
                    Storage: StorageSpec{Size: "10Gi"},
                },
            }
            Expect(k8sClient.Create(ctx, mc)).Should(Succeed())

            By("Reconciling")
            controllerReconciler.Reconcile(ctx, reconcileRequest(mc))

            By("Checking the StatefulSet is created")
            sts := &appsv1.StatefulSet{}
            Eventually(func() error {
                return k8sClient.Get(ctx, types.NamespacedName{
                    Name: "test-mysql", Namespace: "default",
                }, sts)
            }).Should(Succeed())

            Expect(*sts.Spec.Replicas).Should(Equal(int32(3)))
        })
    })
})
```

### 8.2 本地调试

```bash
# 使用 envtest（推荐）
make test

# 或本地运行 Operator（连接真实集群）
make run
# INFO  starting manager
# INFO  MySQLCluster reconciled successfully

# 触发 reconcile
kubectl annotate mysqlcluster my-db force-reconcile=$(date +%s)
```

### 8.3 调试技巧

```bash
# 1. 查看 Operator 日志
kubectl logs -n my-operator-system deploy/my-operator-controller-manager -f

# 2. 查看 Operator 状态
kubectl get mysqlcluster -A
kubectl describe mysqlcluster my-db

# 3. 查看事件
kubectl get events --sort-by='.lastTimestamp' -A

# 4. 增加日志详细度
# 编辑 main.go：
#   opts := ctrl.Options{...}
#   ctrl.SetLogger(zap.New(zap.UseDevMode(true)))
make run

# 5. 远程调试 Operator
# 编辑 Makefile：
#   run: go run ./cmd/main.go
# 用 Delve：
dlv debug ./cmd/main.go -- --kubeconfig=~/.kube/config
```

---

## 九、Operator 最佳实践

### 9.1 设计原则

```text
1. 单一职责
   - 一个 Operator 对应一种资源
   - 不要做"万能 Operator"

2. 声明式 API
   - spec 是期望，status 是实际
   - 避免命令式操作

3. 幂等性
   - 同一 CR 多次 reconcile 结果相同
   - 不依赖 Reconcile 次数

4. 优雅升级
   - CR schema 版本化
   - Conversion Webhook 处理兼容

5. 优雅降级
   - 外部依赖失败时保持 CR 状态
   - 记录事件，不要 panic
```

### 9.2 性能与稳定性

```text
1. 限制并发
   - MaxConcurrentReconciles: 3
   - 避免 Controller OOM

2. 限流与重试
   - ExponentialBackoff
   - 限制最大重试次数

3. Owner Reference
   - 所有子资源必须设 owner
   - CR 删除时自动清理

4. Finalizer
   - 清理外部资源
   - 必须能完成清理才能删除 CR

5. Status 幂等
   - 只有变化才更新
   - 避免大量空更新
```

### 9.3 生产级检查清单

```text
- [ ] CRD 声明 status subresource
- [ ] Finalizer 处理完整
- [ ] Owner reference 设置
- [ ] Reconcile 幂等
- [ ] 错误处理（requeue 策略）
- [ ] 限流（RateLimiter）
- [ ] 监控指标（Prometheus）
- [ ] 健康检查（/healthz, /readyz）
- [ ] Webhook 高可用（多副本 + leader election）
- [ ] 优雅降级
- [ ] 日志结构化
- [ ] 文档（API、CR 字段说明）
- [ ] 测试覆盖（unit + e2e）
```

---

## 十、参考资源

```text
- Operator SDK: https://sdk.operatorframework.io/
- Kubebuilder: https://book.kubebuilder.io/
- Controller Runtime: https://github.com/kubernetes-sigs/controller-runtime
- Operator Hub: https://operatorhub.io/
- Operator Framework: https://github.com/operator-framework
- awesome-operators: https://github.com/operator-framework/awesome-operators
- 核心示例: https://github.com/operator-framework/samples
- 实践指南: https://sdk.operatorframework.io/docs/best-practices/

## 速记卡

Operator = CRD + Controller + 运维知识
工具链：Kubebuilder + controller-runtime + Operator SDK
核心循环：Watch → Diff → Reconcile → Update Status
关键 API：Reconcile() + SetupWithManager()
关键模式：Owner Reference + Finalizer + Status Subresource
Owner Reference → 删除 CR 自动清理子资源
Finalizer → 处理外部资源清理
Status Subresource → 分离期望/实际状态
```

## 速记

- **Operator** = CRD + Controller + 运维知识
- **工具链**：Kubebuilder + controller-runtime + Operator SDK
- **核心循环**：Watch → Get → Diff → Reconcile → Update Status
- **关键 API**：Reconcile() + SetupWithManager()
- **关键模式**：
  - Owner Reference：CR 删除自动清理
  - Finalizer：清理外部资源
  - Status Subresource：分离 spec/status
  - Webhook：验证、默认值、转换

```bash
kubectl apply -f cr.yaml
# → Controller watch
# → Reconcile
# → K8s 资源创建
# → status 更新
```