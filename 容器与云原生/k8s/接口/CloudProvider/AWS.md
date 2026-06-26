## 概念

AWS Cloud Provider 是让 K8s **集成 AWS 云资源**（EC2 / ELB / EBS / Route53 / ASG）的 out-of-tree 插件。1.28 起 in-tree plugin 全部废弃，**统一走 cloud-controller-manager + aws-cloud-provider**。

* 项目：<https://github.com/kubernetes/cloud-provider-aws>
* 配套组件：**cloud-controller-manager**（独立 deployment）
* IAM：需要 **IRSA（IAM Roles for Service Accounts）** 给 K8s ServiceAccount 配 AWS 权限

## 集成的能力

| K8s 资源 | AWS 资源 |
| --- | --- |
| Service type=LoadBalancer | **ELB（NLB / CLB）** |
| Service type=LoadBalancer annotation `aws-load-balancer-type: nlb` | **NLB** |
| Ingress（alb-ingress-controller） | **ALB** |
| PersistentVolume (EBS) | **EBS 卷** |
| Node lifecycle | **ASG / Spot Fleet** |
| 节点 hostname | EC2 private DNS |
| 节点 zone / region | EC2 metadata |

## 架构

```
┌───────── K8s control plane ──────────┐
│                                       │
│  kube-controller-manager             │
│  cloud-controller-manager（独立）      │
│   ├─ Service Controller              │ → ELB / NLB 创建
│   ├─ Node Controller                 │ → 节点 lifecycle
│   ├─ Node Lifecycle Controller       │ → ASG 联动
│   └─ Volume Controller               │ → EBS attach/detach
│                                       │
│  aws-cloud-provider (binary)         │
└───────────────────────────────────────┘
       │
       │ AWS API（IAM / EC2 / ELB / EBS）
       ▼
┌───────── AWS ──────────────────────────┐
│  EC2 / ASG / ELB / NLB / EBS / Route53 │
└─────────────────────────────────────────┘
```

## 部署

### EKS

EKS 已经自带 cloud-controller-manager（managed），不用自己装。

### 自建 K8s（kubeadm）

```bash
# 1. IAM 角色（IRSA 或 AccessKey, 权限策略见 aws-cloud-provider docs）
# 2. helm 装 cloud-controller-manager
helm repo add aws-cloud-provider https://kubernetes.github.io/cloud-provider-aws
helm install aws-cloud-provider aws-cloud-provider/aws-cloud-controller-manager \
  --namespace kube-system \
  --set clusterName=my-cluster \
  --set region=us-east-1

# 3. kubelet 配 provider id（kubelet 启动参数）
--node-labels=node.kubernetes.io/provider-id=aws:///us-east-1a/i-xxxxx
```

## 常用用法

### Service → NLB

```yaml
apiVersion: v1
kind: Service
metadata:
  name: web
  annotations:
    service.beta.kubernetes.io/aws-load-balancer-type: nlb
    service.beta.kubernetes.io/aws-load-balancer-cross-zone-load-balancing-enabled: "true"
spec:
  type: LoadBalancer
  selector:
    app: web
  ports:
  - port: 80
    targetPort: 8080
```

### EBS StorageClass

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: gp3
provisioner: ebs.csi.aws.com   # 注意:用 EBS CSI driver（独立）
parameters:
  type: gp3
  iops: "3000"
  throughput: "125"
volumeBindingMode: WaitForFirstConsumer
```

> EBS 现在**走 CSI driver**（`aws-ebs-csi-driver`），不在 cloud-controller-manager 里。

### ALB Ingress（ALB Controller）

独立 helm chart：`aws-load-balancer-controller`，**不是** cloud-controller-manager。

## 优缺点

* ✅ **AWS 官方**，生态最完整
* ✅ EKS / 自建 K8s 都支持
* ✅ IRSA 集成安全（IAM 权限精细到 ServiceAccount）
* ✅ 跟 AWS 服务深度集成（NLB / ALB / EBS / ASG）
* ❌ **绑定 AWS**，迁移到别的云要换
* ❌ Service LB 创建慢（~30s ~ 数分钟）
* ❌ 一些高级 ALB 特性要靠 aws-load-balancer-controller（额外组件）
* ❌ EBS CSI driver 跟 cloud-controller-manager 是分开的，要单独装

## 适用场景

* **AWS 上跑 K8s**（EKS 或自建）
* 用 NLB / ALB 做 ingress
* 用 EBS 做持久化

## 监控 / 排查

```bash
# cloud-controller-manager 状态
kubectl -n kube-system get pods -l app=aws-cloud-controller-manager

# LB 创建事件
kubectl describe svc <lb-svc>

# AWS 侧看
aws elbv2 describe-load-balancers
aws ec2 describe-volumes

# IAM 权限检查（IRSA）
kubectl -n kube-system exec -ti <ccm-pod> -- aws sts get-caller-identity
```

## 一句话

**AWS 上 K8s 的标配，cloud-controller-manager + IRSA + EBS CSI**。