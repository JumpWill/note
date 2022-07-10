## nocalhost

Nocalhost 是一款开源的基于 IDE 的云原生应用开发工具
1.直接在 Kubernetes 集群中构建、测试和调试应用程序
2.提供易于使用的 IDE 插件(支持 VS Code 和 JetBrains),即使在 Kubernetes 集群中进行开发和调试，Nocalhost 也能保持和本地开发一样的开发体验
3.使用即时文件同步进行开发： 即时将您的代码更改同步到远端容器，而无需重建镜像或重新启动容器。

## start

### 要求

```
任何本地或远程 Kubernetes 集群 (如 minikube, Docker Desktop, TKE, GKE, EKS, AKS, Rancher 等)。 为如 Docker Desktop 和 Minikube 这样的单节点集群至少分配 4 GB 内存.
RBAC 必须在上述集群中启用
应该在集群节点安装 Socat (Nocalhost 文件同步依赖 port-forward)
配置好的具备命名空间的管理员权限的 KubeConfig 文件
Kubernetes api-server 可以被内部和外部访问
Visual Studio Code (1.52 以上版本)
```

使用详见：<https://nocalhost.dev/zh-CN/docs/quick-start>

### 使用经验

使用：<https://nocalhost.dev/zh-CN/docs/guides/develop-service>

nocalhost的工作方式将原来的pod杀掉，然后根据自己设置的镜像和配置新起一个pod(里面不用启动任何服务)，然后在terminal中启动服务，在其他页面完成测试，会将日志打印到terminal，修改了代码也会同步到pod中(需要配置socat).
在开发之前，一般需要配置以下三个方面，点击nocalhost的中控制器的设置图标，会跳转到网页，完成配置后apply就oK.

```
1.容器镜像
2.workdir
3.项目代码路径(用于将容器里的代码进行覆盖)

```

## 总结

nocalhost是一种快捷开发调试的方式，可以认为nocalhost是把原来的积木(有服务的pod)换成自己的积木(未启动服务的pod)，然后terminal里面启服务，完成开发调试。
