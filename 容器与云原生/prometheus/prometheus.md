## Prometheus
Prometheus是一个开放性的监控解决方案，用户可以非常方便的安装和使用Prometheus并且能够非常方便的对其进行扩展。为了能够更加直观的了解Prometheus Server，接下来我们将在本地部署并运行一个Prometheus Server实例，通过Node Exporter采集当前主机的系统资源使用情况。 并通过Grafana创建一个简单的可视化仪表盘。

## 安装
### docker安装
```shell
docker run -p 9090:9090  prom/prometheus
curl http://localhost:9090
```
### 普通安装
```shell
export VERSION=2.13.0
curl -LO  https://github.com/prometheus/prometheus/releases/download/v$VERSION/prometheus-$VERSION.darwin-amd64.tar.gz
tar -xzf prometheus-${VERSION}.darwin-amd64.tar.gz
# 数据存在data中
cd prometheus-${VERSION}.darwin-amd64
mkdir -p data
# 启动
./prometheus
```

### Node Exporter

在Prometheus的架构设计中，Prometheus Server并不直接服务监控特定的目标，其主要任务负责数据的收集，存储并且对外提供数据查询支持。因此为了能够能够监控到某些东西，如主机的CPU使用率，我们需要使用到Exporter。Prometheus周期性的从Exporter暴露的HTTP服务地址（通常是/metrics）拉取监控样本数据。
相关安装参考：<https://www.prometheus.wang/quickstart/use-node-exporter.html>
