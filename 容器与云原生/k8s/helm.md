#

## 简介

Helm 可以帮助我们管理 Kubernetes 应用程序 - Helm Charts 可以定义、安装和升级复杂的 Kubernetes 应用程序，Charts 包很容易创建、版本管理、分享和分布。Helm 对于 Kubernetes 来说就相当于 yum 对于 Centos 来说，如果没有 yum 的话，我们在 Centos 下面要安装一些应用程序是极度麻烦的，同样的，对于越来越复杂的 Kubernetes 应用程序来说，如果单纯依靠我们去手动维护应用程序的 YAML 资源清单文件来说，成本也是巨大的。

## helm组件

1. Chart:就是helm的一个整合后的chart包，包含一个应用所有的kubernetes声明模版，类似于yum的rpm包或者apt的dpkg文件
理解:
helm将打包的应用程序部署到k8s,并将它们构建成Chart。这些Chart将所有预配置的应用程序资源以及所有版本都包含在一个易于管理的包中。Helm kubernetes资源(Deployments、Services等)打包到一个Chart中,Chart广被保存到Chart分库。通过Chart分库可用来存情和分享Chart.
2. Helm客户端: helm的客户端组件，负责和k8s apiserver通信
3. Repository:用于发布和存储chart包的仓库，类似yum仓库或docker仓库
4. Release:用Chart包部署的一个实例。通过chart在k8s中部署的应用都会产生一个唯一的Release.同一chart部署多次就会产生多个Release.
    理解:将这些yaml部署完成后，他也会记录部署时候的一个版本，维护了一个release版本状态，通过Release这个实例，他会具体帮我们创建pod，deployment等资源

## helm2 vs helm3

1. helm3移除了Tiller组件helm2中helm客户端和k8s通信是通过Tiller组件和k8s通信,helm3移除了Tiller组件,直接使用kubeconfig文件和k8s的apiserver通信
2. 删除 release 命令变更

```shell
helm delete release-name --purge -------->> helm uninstall release-name
```

3. 查看 charts 信息命令变更

```shell
helm inspect release-name ------------>> helm show
```

4. 拉取 charts 包命令变更

```shell
helm fetch chart-name----->> helm pull chart-name
```

5. helm3中必须指定 release 名称，如果需要生成一个随机名称，需要加选项--generate-name，helm2中如果不指定release名称，可以自动生成一个随机名称

```shell
helm install ./mychart --generate-name
```

## 内置对象

### Release对象

描述了版本发布自身的一些信息。它包含了以下对象
| 对象名称   | 描述            |
| ------ | --------------- |
| .Release.Name   | release 的名称 |
| .Release.Namespace   | release 的命名空间  |
| .Release.IsUpgrade  | 如果当前操作是升级或回滚的话，该值为 true |
| .Release.IsInstall  | 如果当前操作是安装的话，该值为 true |
| .Release.Revision | 获取此次修订的版本号。初次安装时为 1，每次升级或回滚都会递增 |
| .Release.Service  | 获取渲染当前模板的服务名称。一般都是 Helm |

### Chart对象

用于获取Chart.yaml 文件中的内容
Chart.yaml
name: test
info:
    name: test2

获取方式:
.Chart.name
.Chart.info.name

### Values对象

描述的是value.yaml 文件（定义变量的文件）中的内容，默认为空。使用Value 对象可以获取到value.yaml文件中已定义的任何变量数值
values.yaml
name: test
info:
    name: test2

获取方式:
.Values.name
.Values.info.name

### Capabilities 对象

| 对象名称   | 描述            |
| ------ | --------------- |
|.Capabilities.APIVersions | 返回kubernetes集群 API 版本信息集合|
|.Capabilities.APIVersions.Has $version | 用于检测指定的版本或资源在k8s集群中是否可用，例如：apps/v1/Deployment |
|.Capabilities.KubeVersion和.Capabilities.KubeVersion.Version | 都用于获取kubernetes 的版本号 |
|.Capabilities.KubeVersion.Major |  获取kubernetes 的主版本号 |
|.Capabilities.KubeVersion.Minor |获取kubernetes 的小版本号|k

### Template 对象

## 命令

### 创建

```shell
helm create chart-name
chart-name         #chart包的名称
├── Chart.yaml     #保存图表的基本信息，包括名字、描述信息及版本等，这个变量文件都可以被模板目录下文件所引用
├── charts         #存放子图表的目录，目录里存放这个图表依赖的所有子图表
├── templates      #模板文件目录，目录里面存放所有yaml模板文件，包含了所有部署应用的yaml文件
│   ├── NOTES.txt  #存放提示信息的文件，介绍图表帮助信息，螺虫部署后展示给用户。如何使用图表等，是部署图表后给用户的提示信息
│   ├── _helpers.tpl  #放置模板助手的文件，可以在整个chart中重复使用，是放一些templates目录下这些yaml都有可能会用的一些模板
│   ├── deployment.yaml
│   ├── hpa.yaml
│   ├── ingress.yaml
│   ├── service.yaml
│   ├── serviceaccount.yaml
│   └── tests       #用于测试的文件，测试完部署完图表后，如网页，做一个链接，看看你是否部署正常
│       └── test-connection.yaml
└── values.yaml  #用于渲染模板的文件(变量文件，定义变量的值)定义模板目录下的文件可能引用到的变量               #value.yaml用于存储模板目录中模板文件中用到变量的值，这些变量定义都是为了让模板目录下yaml引用
```

### 测试

用于渲染yaml,显示渲染结果,而不真正的作用到集群。

```shell
helm install release-name repo --debug --dry-run
```

### 卸载

```shell
helm uninstall release-name
```
