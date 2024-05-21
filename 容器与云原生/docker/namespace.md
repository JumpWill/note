#

## namespace

Linux的[命名空间](https://so.csdn.net/so/search?q=命名空间&spm=1001.2101.3001.7020)机制提供了一种**资源隔离**的解决方案。PID,IPC,Network等系统资源不再是全局性的，而是属于特定的Namespace。Linux Namespace机制为实现基于容器的虚拟化技术提供了很好的基础，LXC（Linux containers）就是利用这一特性实现了资源的隔离。不同Container内的进程属于不同的Namespace，彼此透明，互不干扰。
Namespace是对全局系统资源的一种封装隔离，使得处于不同namespace的进程拥有独立的全局系统资源，改变一个namespace中的系统资源只会影响当前namespace里的进程，对其他namespace中的进程没有影响。

```shell
# 查看linux内核支持的namespace类型
ls -l /proc/$$/ns
# 查看Linux的内核版本
uname -r
```

不同的Linux内核版本对不同的

| 类型   | 释义            | 作用                                                         | 内核版本                          |
| ------ | --------------- | ------------------------------------------------------------ | --------------------------------- |
| mount  | 挂载命名空间    | 使进程有一个独立的挂载文件系统                               | 始于Linux 2.4.19                  |
| ipc    | ipc命名空间     | 使进程有一个独立的ipc，包括消息队列，共享内存和信号量        | 始于Linux 2.6.19                  |
| uts    | uts命名空间     | 使进程有一个独立的hostname和domainname(域名系统)             | 始于Linux 2.6.19                  |
| net    | network命令空间 | 使进程有一个独立的网络栈，就如一个普通的操作系统一样。       | 始于Linux 2.6.24                  |
| pid    | pid命名空间     | 使进程有一个独立的pid空间                                    | 始于Linux 2.6.24                  |
| user   | user命名空间    | 是进程有一个独立的user空间                                   | 始于Linux 2.6.23，结束于Linux 3.8 |
| cgroup | cgroup命名空间  | 使进程有一个独立的cgroup控制组，控制进程所占资源上限如内存CPU等 | 始于Linux 4.6                     |

PS:

当一个namespace里面的所有进程都退出时，namespace也会被销毁，所以抛开进程谈namespace没有意义。
UTS namespace就是进程的一个属性，属性值相同的一组进程就属于同一个namespace，跟这组进程之间有没有亲戚关系无关
UTS namespace没有嵌套关系，即不存在说一个namespace是另一个namespace的父namespace

参考：

​ <https://www.cnblogs.com/yinzhengjie/p/12183066.html>

## 使用docker容器namespace

docker的资源隔离就使用到了Linux的namespace，一个容器就对应一个进程，所以容器有自己的网络文件等。

当使用docker exec 进入容器的时候，所处的namespace也会被切换，所对应的资源(网络，存储等)也会相应切换。

但是很多时候，我们只是想要访问容器的某些namespace的信息，例如访问其中的文件存储，这时候只是需要选择切换一下某个进程的某一namespace。

```shell
# 查看容器的pid process id
docker inspect -f '{{.State.Pid}}' container_id
# 在系统中会有/proc/pid/ns，可以查看到不同的进程的namepace，pid为进程id
ll /proc/pid/ns


# 切换到某个进程的namespace
nsenter [options] [program [arguments]]
 
options:
-t, --target pid：指定被进入命名空间的目标进程的pid
-m, --mount[=file]：进入mount命令空间。如果指定了file，则进入file的命令空间
-u, --uts[=file]：进入uts命令空间。如果指定了file，则进入file的命令空间
-i, --ipc[=file]：进入ipc命令空间。如果指定了file，则进入file的命令空间
-n, --net[=file]：进入net命令空间。如果指定了file，则进入file的命令空间
-p, --pid[=file]：进入pid命令空间。如果指定了file，则进入file的命令空间
-U, --user[=file]：进入user命令空间。如果指定了file，则进入file的命令空间
-G, --setgid gid：设置运行程序的gid
-S, --setuid uid：设置运行程序的uid
-r, --root[=directory]：设置根目录
-w, --wd[=directory]：设置工作目录

# 例如进入某pid的网络namespace
nsenter -t pid -n
```
