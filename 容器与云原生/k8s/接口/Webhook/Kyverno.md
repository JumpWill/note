## 概念

Kyverno 是 **专为 K8s 设计的策略引擎**，用 YAML 写策略（不用 Rego），做 admission webhook（mutate + validate + generate）。

* 项目：<https://github.com/kyverno/kyverno>（CNCF incubating）
* 定位：**K8s 原生**，DSL 直接是 K8s YAML，不需要学新语言

## 三大能力

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-labels
spec:
  validationFailureAction: Enforce     # Enforce 拒绝 / Audit 仅审计
  rules:
  - name: check-owner
    match:
      any:
      - resources:
          kinds: ["Pod"]
    validate:
      message: "必须带 owner label"
      pattern:
        metadata:
          labels:
            owner: "?*"        # ?* 表示必须存在

  - name: inject-sidecar
    match:
      any:
      - resources:
          kinds: ["Pod"]
    mutate:
      patchStrategicMerge:
        spec:
          containers:
          - name: istio-proxy
            image: docker.io/istio/proxyv2:1.20

  - name: auto-gen-network-policy
    match:
      any:
      - resources:
          kinds: ["Namespace"]
    generate:
      apiVersion: networking.k8s.io/v1
      kind: NetworkPolicy
      name: "default-deny-{{request.object.metadata.name}}"
      synchronize: true        # 源删了自动清理
```

* **Validate**：拒绝不合规
* **Mutate**：自动改 spec（注入 sidecar、加 label）
* **Generate**：根据源对象生成新对象（自动建 NetworkPolicy / RoleBinding）

## 部署

```bash
# Helm
helm repo add kyverno https://kyverno.github.io/kyverno
helm install kyverno kyverno/kyverno \
  --namespace kyverno --create-namespace

# 或 yaml
kubectl apply -f https://github.com/kyverno/kyverno/releases/latest/download/install.yaml
```

## 关键能力

* **Policy Report**：策略违规报告（类似 PodSecurity）
* **背景扫描**：对存量资源做策略审计
* **Variable Substitution**：`{{request.object.metadata.name}}` 等
* **Preconditions / Overlays**：高级 match 条件
* **Multi-tenancy**：namespace 隔离策略
* **Verify Image / Signatures**：镜像签名验证（cosign / Notary v2）
* **Generate synchronize**：自动生成的资源随源变化

## 优缺点

* ✅ **YAML 写策略**，K8s 用户零学习成本
* ✅ 一站式：mutate / validate / generate 都原生支持
* ✅ 镜像签名验证内置
* ✅ 背景扫描：可以审计存量
* ✅ 中文社区友好（韩国出品）
* ❌ 复杂逻辑（多条件组合）写起来长
* ❌ 高级逻辑仍要借助 JMESPath / CEL
* ❌ 性能比 Gatekeeper 稍弱（大量规则时）

## 适用场景

* **大多数 K8s 用户的策略首选**
* 多团队多集群统一策略
* 镜像签名 / SBOM 验证
* 自动注入 sidecar / 配置

## 监控 / 排查

```bash
# 策略状态
kubectl get cpol
kubectl describe cpol require-labels

# 策略报告
kubectl get policyreport -A

# webhook 状态
kubectl -n kyverno get pods
kubectl -n kyverno logs -l app.kubernetes.io/component=kyverno

# 测试策略
kubectl test --filename policy.yaml --values values.yaml
```

## 一句话

**K8s YAML 写策略，零学习成本，mutate + validate + generate 一站式**。