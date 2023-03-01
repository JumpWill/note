#

## 简介

Helm 可以帮助我们管理 Kubernetes 应用程序 - Helm Charts 可以定义、安装和升级复杂的 Kubernetes 应用程序，Charts 包很容易创建、版本管理、分享和分布。Helm 对于 Kubernetes 来说就相当于 yum 对于 Centos 来说，如果没有 yum 的话，我们在 Centos 下面要安装一些应用程序是极度麻烦的，同样的，对于越来越复杂的 Kubernetes 应用程序来说，如果单纯依靠我们去手动维护应用程序的 YAML 资源清单文件来说，成本也是巨大的。

## 安装

```shell
# 换源
helm repo add stable http://mirror.azure.cn/kubernetes/charts/
```
