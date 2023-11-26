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
