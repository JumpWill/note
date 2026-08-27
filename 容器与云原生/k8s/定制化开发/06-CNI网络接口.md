# CNI 网络接口（Container Network Interface）

## 一、为什么要做 CNI

### 1.1 业务背景

```text
K8s 需要解决的核心问题：Pod 之间如何通信？

需求场景：
  - 跨主机 Pod 通信（Calico、Flannel）
  - 多租户网络隔离（Calico NetworkPolicy）
  - 高性能网络（Cilium eBPF）
  - 自研 SDN/网络设备
  - 与 Underlay 网络集成（BGP、SDN）
  - L2 网络需求（Multus 多网络）
  - 特殊网络功能（SR-IOV、MACVLAN、IPVLAN）
  - 监控可观测性（Hubble）

K8s 网络模型的灵活性需求：
  - 不同业务场景需要不同网络方案
  - 单一网络方案无法满足所有场景
  - K8s 需要可插拔的网络架构
```

### 1.2 CNI 核心价值

```text
1. 标准化
   - 统一接口（基于 CNI 规范）
   - 多种 CNI 可插拔
   - 多语言 SDK

2. 解耦
   - 网络与 K8s 核心解耦
   - 独立演进
   - 多厂商竞争

3. 灵活
   - 根据场景选择 CNI
   - 切换 CNI 无需改 K8s
   - 可多 CNI 协同（Multus）

4. 生态丰富
   - Flannel、Calico、Cilium、Weave 等
   - 适配各种场景
   - 持续创新
```

### 1.3 适用场景

```text
适合 CNI 的场景：
  ✅ 选择网络方案（Flannel、Calico、Cilium）
  ✅ 自研网络设备接入 K8s
  ✅ 多网络平面（Multus）
  ✅ 高性能网络（eBPF）
  ✅ 严格 NetworkPolicy 隔离
  ✅ SR-IOV、硬件卸载

不适合：
  ❌ K8s 不需要网络（用 host network）
  ❌ 单机测试（Flannel host-gw 即可）
```

---

## 二、CNI 规范

### 2.1 CNI 规范概述

```text
CNI（Container Network Interface）：
  - 由 CNCF 维护的标准规范
  - 基于 JSON 配置
  - 定义容器网络操作
  - 多个实现：Flannel、Calico、Cilium 等

规范地址：https://github.com/containernetworking/cni

CNI 规范特点：
  - 简单（基于 JSON）
  - 灵活（插件化）
  - 可组合（多个插件）
  - 跨运行时（Docker、containerd、CRI-O）
```

### 2.2 CNI 操作类型

```text
CNI 定义了 4 种操作：

  ADD        - 创建网络接口（容器启动时）
  DEL        - 删除网络接口（容器删除时）
  CHECK      - 检查网络接口状态
  GC         - 垃圾回收

操作时序：
  Pod 启动 → kubelet → CNI ADD → 创建网络 → Pod 运行
  Pod 删除 → kubelet → CNI DEL → 清理网络
```

### 2.3 CNI 配置文件

```json
{
  "cniVersion": "1.0.0",
  "name": "mynet",
  "type": "calico",
  "ipam": {
    "type": "calico-ipam",
    "subnet": "10.244.0.0/16",
    "range-start": "10.244.1.0",
    "range-end": "10.244.255.254",
    "gateway": "10.244.0.1",
    "routes": [
      {
        "dst": "0.0.0.0/0",
        "gw": "10.244.0.1"
      }
    ]
  },
  "dns": {
    "nameservers": ["10.96.0.10"]
  },
  "isGateway": true,
  "ipMasq": false,
  "mtu": 1500,
  "chainLink": "INPUT",
  "hairpinMode": false
}
```

### 2.4 CNI 插件执行流程

```text
Pod 启动时 CNI 调用流程：

  ┌──────────────────────────────────┐
  │  kubelet 创建 Pod                 │
  └──────────────┬───────────────────┘
                 ↓
  ┌──────────────────────────────────┐
  │  kubelet 调用 CNI ADD            │
  │  （通过 CNI 二进制）             │
  └──────────────┬───────────────────┘
                 ↓
  ┌──────────────────────────────────┐
  │  CNI 插件执行                    │
  │  1. 创建 veth pair               │
  │  2. 一端放入 Pod netns           │
  │  3. 另一端接入 host bridge      │
  │  4. 配置 IP（IPAM）             │
  │  5. 配置路由                     │
  │  6. 返回结果给 kubelet           │
  └──────────────────────────────────┘
                 ↓
  ┌──────────────────────────────────┐
  │  kubelet 启动容器进程           │
  └──────────────────────────────────┘
```

### 2.5 CNI 插件可组合性

```text
CNI 插件可以组合：

  /etc/cni/net.d/10-mynet.conflist
  {
    "name": "mynet",
    "plugins": [
      {
        "type": "calico",          // 主 CNI 插件
        "ipam": { ... }
      },
      {
        "type": "bandwidth",       // 带宽限制
        "bandwidth": {
          "ingressRate": 1000000,
          "egressRate": 1000000
        }
      },
      {
        "type": "portmap"          // 端口映射
      }
    ]
  }
```

常用辅助 CNI 插件：
  - portmap：端口映射
  - bandwidth：带宽限制
  - firewall：iptables 规则
  - sbr（Source Based Routing）
  - tuning：网络调优
  - whereabouts：IP 推断
```

---

## 三、CNI 插件开发

### 3.1 CNI 插件开发基础

```go
// myplugin/main.go
package main

import (
    "encoding/json"
    "fmt"
    "os"
    "runtime"

    "github.com/containernetworking/cni/pkg/skel"
    "github.com/containernetworking/cni/pkg/types"
    "github.com/containernetworking/cni/pkg/version"
    "github.com/containernetworking/plugins/pkg/ns"
)

// NetConf 网络配置
type NetConf struct {
    types.CommonArgs
    types.NetConfArgs
    Bridge string `json:"bridge"`
    IsGW   bool   `json:"isGateway"`
    IPMasq bool   `json:"ipMasq"`
    MTU    int    `json:"mtu"`
}

// cmdAdd CNI ADD 命令
func cmdAdd(args *skel.CmdArgs) error {
    n, _, err := loadNetConf(args.StdinData)
    if err != nil {
        return err
    }

    // 1. 进入容器网络命名空间
    netns, err := ns.GetNS(args.Netns)
    if err != nil {
        return fmt.Errorf("failed to open netns: %v", err)
    }
    defer netns.Close()

    // 2. 在 netns 中创建网络接口
    err = netns.Do(func(_ ns.NetNS) error {
        // 创建 veth pair
        // 配置 IP 地址
        // 设置路由
        return nil
    })
    if err != nil {
        return err
    }

    // 3. 返回结果
    result := &types.Result{
        CNIVersion: version.Current(),
        IPs: []types.IPConfig{
            {
                Version: "4",
                Address: net.IP{10, 244, 0, 5},
                Gateway: net.IP{10, 244, 0, 1},
            },
        },
    }
    return types.PrintResult(result, n.CNIVersion)
}

// cmdDel CNI DEL 命令
func cmdDel(args *skel.CmdArgs) error {
    n, _, err := loadNetConf(args.StdinData)
    if err != nil {
        return err
    }
    
    // 进入 netns 清理接口
    netns, err := ns.GetNS(args.Netns)
    if err != nil {
        return err
    }
    defer netns.Close()
    
    err = netns.Do(func(_ ns.NetNS) error {
        // 删除 veth pair
        return nil
    })
    return err
}

func loadNetConf(bytes []byte) (*NetConf, string, error) {
    n := &NetConf{}
    if err := json.Unmarshal(bytes, n); err != nil {
        return nil, "", fmt.Errorf("failed to parse netconf: %v", err)
    }
    return n, n.CNIVersion, nil
}

func main() {
    skel.PluginMain(cmdAdd, cmdCheck, cmdDel, version.All, "CNI myplugin v0.1.0")
}
```

### 3.2 CNI 插件编译部署

```bash
# 1. 编译
go build -o myplugin ./cmd/myplugin

# 2. 安装到 CNI 目录
sudo cp myplugin /opt/cni/bin/

# 3. 创建 CNI 配置
sudo tee /etc/cni/net.d/10-mynet.conflist <<'EOF'
{
  "cniVersion": "1.0.0",
  "name": "mynet",
  "type": "myplugin",
  "bridge": "cni0",
  "isGateway": true,
  "ipMasq": true,
  "mtu": 1500,
  "ipam": {
    "type": "host-local",
    "subnet": "10.244.0.0/16",
    "gateway": "10.244.0.1"
  }
}
EOF

# 4. 测试
cat /opt/cni/bin/myplugin
```

### 3.3 CNI 插件与 K8s 集成

```yaml
# kubelet 配置
apiVersion: kubelet.config.k8s.io/v1beta1
kind: KubeletConfiguration
networkPlugin: cni
cniConfDir: /etc/cni/net.d
cniBinDir: /opt/cni/bin
networkPluginName: cni
```

---

## 四、CNI 实战场景

### 4.1 场景 1：自研 SDN 控制器集成

```yaml
# 自研 CNI 通过 Multus 集成
apiVersion: k8s.cni.cncf.io/v1
kind: NetworkAttachmentDefinition
metadata:
  name: my-sdn-network
  namespace: default
spec:
  config: '{
    "cniVersion": "0.3.1",
    "type": "my-sdn",
    "name": "my-sdn",
    "sdnController": "http://sdn-controller:8080",
    "tenantId": "tenant-a",
    "ipam": {
      "type": "my-ipam"
    }
  }'
```

### 4.2 场景 2：多网络平面（Multus）

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: multus-pod
  annotations:
    k8s.v1.cni.cncf.io/networks: |
      [
        {
          "name": "default-network",
          "interface": "eth0"
        },
        {
          "name": "high-bandwidth-network",
          "interface": "eth1"
        },
        {
          "name": "monitoring-network",
          "interface": "eth2"
        }
      ]
spec:
  containers:
  - name: app
    image: my-app:1.0
    ports:
    - containerPort: 8080
    - containerPort: 9090
```

### 4.3 场景 3：SR-IOV 高性能网络

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: sriov-pod
  annotations:
    k8s.v1.cni.cncf.io/networks: |
      [{
        "name": "sriov-net",
        "interface": "net1"
      }]
spec:
  containers:
  - name: dpdk-app
    image: my-dpdk-app:1.0
    resources:
      requests:
        hugepages-1Gi: 2Gi
        memory: 4Gi
      limits:
        hugepages-1Gi: 4Gi
        memory: 8Gi
```

### 4.4 场景 4：KubeVirt 多网络

```yaml
apiVersion: kubevirt.io/v1
kind: VirtualMachineInstance
metadata:
  name: multi-net-vm
spec:
  domain:
    devices:
      interfaces:
      - name: default
        bridge: {}
      - name: sriov-net
        sriov: {}
  networks:
  - name: default
    pod: {}
  - name: sriov-net
    multus:
      networkName: sriov-network
```

---

## 五、CNI 性能对比

### 5.1 主流 CNI 性能基准

| CNI | 跨节点延迟 | 吞吐 | CPU 开销 | 适用 |
|-----|-----------|------|---------|------|
| Flannel (host-gw) | ~40μs | 9.4Gbps | 极低 | 中小集群 |
| Flannel (vxlan) | ~70μs | 9.0Gbps | 极低 | 通用 |
| Calico (iptables) | ~50μs | 9.0Gbps | 中 | 标准生产 |
| Calico (eBPF) | ~30μs | 9.5Gbps | 低 | 高性能 |
| Calico (BGP) | ~30μs | 9.5Gbps | 低 | 裸金属 |
| Cilium (eBPF) | ~25μs | 9.4Gbps | 低 | 高端生产 |
| Antrea (eBPF) | ~30μs | 9.3Gbps | 低 | VMware |
| Multus + Macvlan | ~20μs | 9.5Gbps | 极低 | 多网络 |
| Weave | ~80μs | 8.5Gbps | 中 | 老项目 |

### 5.2 性能测试方法

```bash
# 1. 部署iperf测试Pod
kubectl run iperf-server --image=networkstatic/iperf3 -it --rm

# 2. 在另一节点运行iperf客户端
kubectl run iperf-client --image=networkstatic/iperf3 -it --rm -- \
  iperf3 -c <iperf-server-ip> -t 30 -P 4

# 3. 测试延迟
kubectl run latency-test --image=alpine -it --rm -- ping -c 100 <target-pod-ip>
```

---

## 六、CNI 调试

### 6.1 调试工具

```bash
# 1. 查看 CNI 配置
ls /etc/cni/net.d/
cat /etc/cni/net.d/10-calico.conflist

# 2. 查看 CNI 二进制
ls /opt/cni/bin/

# 3. 查看 CNI 插件日志
journalctl -u kubelet -f

# 4. 手动测试 CNI
cat /opt/cni/bin/calico
echo '{"cniVersion":"0.3.1","name":"test","type":"calico","ipam":{"type":"calico-ipam","subnet":"10.244.0.0/16"},"isGateway":true}' | /opt/cni/bin/calico <ADD> ...

# 5. 检查 Pod 网络
kubectl exec -it <pod> -- ip addr
kubectl exec -it <pod> -- ip route
kubectl exec -it <pod> -- iptables -L -n
```

### 6.2 常见问题

```text
Q1: Pod 无法分配 IP
A1: 检查：
    - CNI 插件是否安装：ls /opt/cni/bin/
    - CNI 配置是否正确：cat /etc/cni/net.d/*.conflist
    - kubelet 日志：journalctl -u kubelet
    - IPAM 是否耗尽

Q2: Pod 之间无法通信
A2: 检查：
    - NetworkPolicy 是否放行：kubectl get networkpolicy
    - CNI 是否在用 VXLAN/host-gw：cat /etc/cni/net.d/*.conflist
    - 路由表：ip route
    - iptables 规则：iptables -L -n

Q3: Service ClusterIP 无法访问
A3: 检查：
    - kube-proxy 是否正常：kubectl get ds -n kube-system kube-proxy
    - iptables 规则：iptables -t nat -L KUBE-SERVICES
    - Service Endpoints：kubectl get endpoints
```

---

## 七、CNI 选型指南

```text
选择 CNI 的考虑因素：

1. 集群规模
   - 小（< 50 节点）：Flannel
   - 中（50-500 节点）：Calico
   - 大（> 500 节点）：Cilium / Calico eBPF

2. 网络性能要求
   - 普通：Flannel、Calico iptables
   - 高性能：Cilium eBPF、Calico eBPF

3. NetworkPolicy
   - 简单：Flannel（无）、Calico
   - L7：Cilium

4. 可观测性
   - 弱：Flannel
   - 中：Calico
   - 强：Cilium Hubble

5. 云环境
   - 公有云：使用云厂商 CNI
   - 私有云：Calico、Cilium

6. 多网络平面
   - Multus + 主 CNI
   - 用于 SR-IOV、Macvlan、DPDK 等

推荐：
  - 中小企业：Calico
  - 大型互联网：Cilium
  - 简单场景：Flannel
  - 特殊硬件：Multus + SR-IOV
```

---

## 八、参考资源

```text
- CNI 规范: https://github.com/containernetworking/cni
- CNI 插件列表: https://www.cni.dev/plugins/
- K8s 网络模型: https://kubernetes.io/docs/concepts/networking/
- Flannel: https://github.com/flannel-io/flannel
- Calico: https://docs.tigera.io/calico/latest/
- Cilium: https://docs.cilium.io/
- Multus: https://github.com/k8snetworkplumbingwg/multus-cni
- Antrea: https://antrea.io/
- Weave: https://www.weave.works/
- CNI 实战: https://www.cni.dev/docs/
```
## 速记卡

CNI = Container Network Interface（容器网络接口）
四操作：ADD / DEL / CHECK / GC
配置文件：/etc/cni/net.d/*.conflist
二进制：/opt/cni/bin/
主流 CNI：Flannel、Calico、Cilium、Antrea
多网络：Multus
K8s 默认 CNI：Flannel（v1.0-1.24）、Cilium（v1.25+）
核心数据：cniVersion、name、type、ipam、plugins
