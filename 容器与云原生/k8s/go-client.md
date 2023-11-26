## go-client结构

| 文件                                                      | 作用                         |
| -------------------------------------------------------- | :--------------------------- |
| discovery  | 提供 DiscoveryClient 发现客户端。 |
| dynamic  | 提供 DynamicClient 动态客户端。|
| informers  | 每种 K8S 资源的 Informer 实现。|
| kubernetes  | 提供 ClientSet 客户端。|
| listers  | 为每一个 K8S 资源提供 Lister 功能，该功能对 Get 和 List 请求提供只读的缓存数据。|
| plugin  | 提供 OpenStack，GCP 和 Azure 等云服务商授权插件。|
| rest  | 提供 RESTClient 客户端，对 K8S API Server 执行 RESTful 操作。|
| scale  | 提供 ScaleClient 客户端，用于扩容或缩容 Deployment, Replicaset, Replication Controller 等资源对象。|
| tools  | 提供常用工具，例如 SharedInformer, Reflector, DeltaFIFO 及 Indexers。 提供 Client 查询和缓存机制，以减少向 kube apiserver 发起的请求数等。主要子目录为/tools/cache。|
| transport  | 提供安全的 TCP 连接，支持 HTTP Stream，某些操作需要在客户端和容器之间传输二进制流，例如 exec，attach 等操作。该功能由内部的 SPDY 包提供支持。|
| util  | 提供常用方法。例如 WorkQueue 工作队列，Certificate 证书管理等。 |

## client

### RESTClient 客户端

RESTful Client 是最基础的客户端，它主要是对 HTTP 请求进行了封装，并且支持 JSON 和 Protobuf 格式数据。

### DynamicClient 客户端

DynamicClient 是一种动态客户端，它可以动态的指定资源的组，版本和资源。因此它可以对任意 K8S 资源进行 RESTful 操作，包括 CRD 自定义资源。它封装了 RESTClient。所以同样提供 RESTClient 的各种方法。

具体使用方法，可参考官方示例：dynamic-create-update-delete-deployment。

注意: 该官方示例是基于集群外的环境，如果你需要在集群内部使用（例如你需要在 container 中访问），你将需要调用 rest.InClusterConfig() 生成一个 configuration。具体的示例请参考 in-cluster-client-configuration。

### ClientSet 客户端

ClientSet 客户端在 RESTClient 的基础上封装了对资源和版本的管理方法。每个资源可以理解为一个客户端，而 ClientSet 则是多个客户端的集合，每一个资源和版本都以函数的方式暴露给开发者。

具体使用方法，可参考官方示例：create-update-delete-deployment。

### DiscoveryClient 客户端

DiscoveryClient 是一个发现客户端，它主要用于发现 K8S API Server 支持的资源组，资源版本和资源信息。所以开发者可以通过使用 DiscoveryClient 客户端查看所支持的资源组，资源版本和资源信息。
