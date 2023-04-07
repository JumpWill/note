Pod 使用 downward API 通过环境变量把自身的信息呈现给 Pod 中运行的容器。
参考： <https://kubernetes.io/zh-cn/docs/tasks/inject-data-application/environment-variable-expose-pod-information/>

```yaml
apiVersion: v1
kind: Pod
metadata:
    name: test-env-pod
    namespace: kube-system
spec:
    containers:
    - name: test-env-pod
      image: busybox:latest
      command: ["/bin/sh", "-c", "env"]
      env:
    - name: NODE_NAME
        valueFrom:
        fieldRef:
            fieldPath: spec.nodeName
      - name: POD_NAME
        valueFrom:
          fieldRef:
            fieldPath: metadata.name
      - name: POD_NAMESPACE
        valueFrom:
          fieldRef:
            fieldPath: metadata.namespace
      - name: POD_IP
        valueFrom:
          fieldRef:
            fieldPath: status.podIP
```
