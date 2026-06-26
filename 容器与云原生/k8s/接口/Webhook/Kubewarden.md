## 概念

Kubewarden 是 **用 WebAssembly 写策略** 的 admission webhook，每条策略编译成 wasm 模块，可以分发给所有集群。

* 项目：<https://github.com/kubewarden/kubewarden-controller>（CNCF incubating）
* 设计：策略是 OCI 镜像（wasm artifact），可以在镜像仓库管理 / 版本化 / 签名
* 运行时：kubewarden-policy-server（Rust 写）执行 wasm

## 架构

```
┌──────── K8s apiserver ─────────┐
│                                │
│  Validating/Mutating Webhook   │
│         ↓                       │
│  ┌── Kubewarden Policy Server ┐│
│  │  - 加载 wasm policies      ││
│  │  - 执行                     ││
│  └────────────────────────────┘│
│         ↓                       │
│  OCI registry（存策略镜像）       │
└────────────────────────────────┘
```

* **ClusterAdmissionPolicy**：cluster-scoped 策略
* **AdmissionPolicy**：namespace-scoped
* **PolicyServer**：自定义资源，配置一组 wasm 策略 + 运行时
* **kubewarden-controller**：CRD controller，把策略同步到 Policy Server

## 策略形态

* **Rego 策略**：直接用 OPA Rego 编译成 wasm（兼容 OPA 生态）
* **Rust 策略**：用 `kubewarden-policy-sdk` 写，编译成 wasm
* **Go 策略**：用 TinyGo + kubewarden SDK，编译成 wasm
* **CEL 策略**（实验性）：直接写 CEL
* **Sigstore / cosign**：策略镜像签名验证

## Rust 策略示例

```rust
use kubewarden_policy_sdk::wapc_guest as guest;
use kubewarden_policy_sdk::guest::prelude::*;
use serde::{Deserialize, Serialize};

#[derive(Serialize, Deserialize, Debug)]
struct Settings {
    denied_names: Vec<String>,
}

#[no_mangle]
pub extern "C" fn validate(payload: &[u8]) -> CallResult {
    let validation = guest::validate(
        payload,
        |settings: Settings, request: AdmissionRequest| -> Result<(), String> {
            let name = request.name()?;
            if settings.denied_names.contains(&name) {
                Err(format!("name {} 不允许", name))
            } else {
                Ok(())
            }
        },
    );
    validation.into()
}
```

编译：

```bash
cargo build --target wasm32-wasi --release
kwctl push registry.example.com/policies/disallowed-names:v1.0.0
```

## 部署

```bash
# Helm
helm repo add kubewarden https://charts.kubewarden.io
helm install --wait -n kubewarden --create-namespace \
  kubewarden-crds kubewarden/kubewarden-crds
helm install --wait -n kubewarden kubewarden-controller kubewarden/kubewarden-controller
helm install --wait -n kubewarden kubewarden-defaults kubewarden/kubewarden-defaults
```

应用策略：

```yaml
apiVersion: policies.kubewarden.io/v1
kind: ClusterAdmissionPolicy
metadata:
  name: disallowed-names
spec:
  module: registry.example.com/policies/disallowed-names:v1.0.0
  settings:
    denied_names: ["bad-pod-name"]
  rules:
  - apiGroups: [""]
    apiVersions: ["v1"]
    operations: ["CREATE"]
    resources: ["pods"]
  mutating: false
```

## 优缺点

* ✅ **Wasm 沙箱**：策略之间互不影响，不会 crash 整个 webhook
* ✅ **多语言**：Rust / Go / Rego 都能写
* ✅ **策略即镜像**：版本化 / 签名 / 仓库管理
* ✅ 兼容 OPA Rego（导入旧策略容易）
* ✅ PolicyServer 隔离（多个 PS 各管不同 namespace）
* ❌ **新生态**，案例少
* ❌ 写 wasm 策略比 Kyverno YAML 门槛高
* ❌ 文档 / 中文资源少
* ❌ mutate 能力刚起步

## 适用场景

* **多租户 / 多集群**：策略集中管理、跨集群分发
* 已有 Rego 策略：直接打包成 wasm 跑
* 想用 Rust / Go 写策略（比 Rego 工程化更好）

## 监控 / 排查

```bash
# 策略状态
kubectl get clusteradmissionpolicies
kubectl get admissionpolicies -A

# PolicyServer
kubectl -n kubewarden get policyservers

# 测策略
kwctl verify registry.example.com/policies/disallowed-names:v1.0.0
kwctl run registry.example.com/policies/disallowed-names:v1.0.0 \
  --request-path request.json --settings-path settings.yaml
```

## 一句话

**策略用 wasm 跑，多语言支持，沙箱隔离，跨集群分发**。