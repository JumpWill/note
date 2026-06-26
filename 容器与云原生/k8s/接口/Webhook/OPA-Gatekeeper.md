## 概念

OPA Gatekeeper 是 **OPA（Open Policy Agent）** 在 K8s 上的实现，用 **Rego** 写策略。

* 项目：<https://github.com/open-policy-agent/gatekeeper>（CNCF graduated）
* OPA：通用策略引擎（不只是 K8s，跨服务）
* 关系：Gatekeeper 把 OPA 包成 admission webhook，CRD 化模板管理

## 架构

```
┌────────── K8s apiserver ─────────┐
│                                   │
│  Mutating/Validating Webhook     │
│         ↓                         │
│  ┌── Gatekeeper ──────────────┐  │
│  │  Controller Manager          │  │
│  │  - 读 ConstraintTemplate     │  │
│  │  - 跟 OPA sync              │  │
│  │                              │  │
│  │  Audit（背景扫描存量）        │  │
│  └──────────────────────────────┘  │
└───────────────────────────────────┘
```

* **ConstraintTemplate（CRD）**：策略模板（用 Rego 写逻辑）
* **Constraint（CR）**：模板的实例（具体规则，如命名空间必须带 label）
* **OPA**：策略引擎，吃 Rego
* **Audit**：后台扫描已有资源是否符合

## 模板示例

```yaml
# 1. 模板（Rego）
apiVersion: templates.gatekeeper.sh/v1
kind: ConstraintTemplate
metadata:
  name: k8srequiredlabels
spec:
  crd:
    spec:
      names:
        kind: K8sRequiredLabels
      validation:
        openAPIV3Schema:
          properties:
            labels:
              type: array
              items:
                type: string
  targets:
  - target: admission.k8s.io
    rego: |
      package k8srequiredlabels
      violation[{"msg": msg, "details": {"missing_labels": missing}}] {
        provided := {label | input.review.object.metadata.labels[label]}
        required := {label | label := input.parameters.labels[_]}
        missing := required - provided
        count(missing) > 0
        msg := sprintf("缺少 label: %v", [missing])
      }

---
# 2. 实例（具体规则）
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: K8sRequiredLabels
metadata:
  name: ns-must-have-owner
spec:
  match:
    kinds: ["Namespace"]
  parameters:
    labels: ["owner", "env"]
```

## 部署

```bash
# Helm（推荐）
helm repo add gatekeeper https://open-policy-agent.github.io/gatekeeper/charts
helm install gatekeeper gatekeeper/gatekeeper \
  --namespace gatekeeper-system --create-namespace

# 默认装好 3 个 mutation + 1 个 validation webhook
```

## 优缺点

* ✅ **Rego 表达力强**：复杂逻辑（跨资源 / 跨字段 / 跨 namespace）
* ✅ **OPA 通用**：同一套 Rego 可以给 Terraform / Envoy / 数据库用
* ✅ 大规模验证（金融、电信、AWS 多集群）
* ✅ ConstraintTemplate 复用，**多团队共用模板库**
* ❌ **Rego 学习曲线陡**（Datalog 变体，跟 SQL / Python 思路不同）
* ❌ 默认 **只 validate，不原生 mutate**（v3.13+ 才支持）
* ❌ 背景扫描 Audit 性能差，大集群要小心
* ❌ mutate 写起来比 Kyverno 麻烦

## mutate 支持

Gatekeeper 1.14+ 支持 mutate（但要写 `targets[].rego` 里 include mutation 逻辑）：

```rego
# mutating logic
violation[{"msg": msg}] {
  not input.review.object.spec.containers[_].resources.limits.memory
  msg := "must set memory limit"
}
```

实战中 **mutate 还是 Kyverno 强**，Gatekeeper 主打 validate。

## 适用场景

* **复杂跨字段 / 跨资源策略**（如"Pod 引用的 Secret 必须存在"）
* 多云 / 多平台统一策略（OPA 一套语言通用）
* 严格 compliance（金融、电信）

## 监控 / 排查

```bash
# 模板 / 约束
kubectl get constrainttemplates
kubectl get constraints

# Audit 结果
kubectl get constraint -o jsonpath='{.items[*].status.violations}'

# webhook 状态
kubectl -n gatekeeper-system get pods

# 测策略
opa test policy/
```

## 一句话

**Rego 写策略，表达力强，复杂策略首选，但要学新语言**。