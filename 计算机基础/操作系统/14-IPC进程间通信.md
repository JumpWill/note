# 进程间通信 (IPC - Inter-Process Communication)

## 一、IPC 概述

### 为什么需要 IPC

- **数据共享**:多个进程需要共享数据
- **消息传递**:协同工作
- **协作同步**:协调执行
- **通知事件**:状态变化通知

### IPC 的分类

**按通信范围**:

- **本地 IPC**:同一台机器上的进程
- **远程 IPC**:不同机器上的进程 (RPC、网络)

**按通信方式**:

| 类别         | 机制                                 | 适用            |
|--------------|--------------------------------------|-----------------|
| **管道**     | Pipe、FIFO                           | 父子/无关系进程 |
| **消息队列** | System V / POSIX MQ                  | 短消息          |
| **共享内存** | System V / POSIX SHM / mmap          | **最快**        |
| **信号**     | signal                               | 异步事件        |
| **信号量**   | System V / POSIX sem / futex         | 同步            |
| **Socket**   | Unix Domain / TCP / UDP              | 本机/网络       |
| **文件**     | 锁文件、文件读写                     | 简单            |
| **内存映射** | mmap                                 | 大块数据        |
| **RPC**      | ONC RPC、gRPC、Thrift                | 跨网络          |

---

## 二、管道 (Pipe)

### 1. 匿名管道 (Anonymous Pipe)

**特点**:
- 半双工(一端读,一端写)
- 只能用于**有亲缘关系**的进程(父子、兄弟)
- 存在于内存,无文件名
- 通过 `fork()` 继承 fd

**系统调用**:

```c
#include <unistd.h>

int pipe(int pipefd[2]);
// 成功返回 0,pipefd[0] 是读端,pipefd[1] 是写端
```

**使用步骤**:
```c
int fd[2];
pipe(fd);

pid_t pid = fork();
if (pid == 0) {
    // 子进程
    close(fd[1]);              // 关闭写端
    char buf[100];
    int n = read(fd[0], buf, sizeof(buf));
    // 处理
    close(fd[0]);
} else {
    // 父进程
    close(fd[0]);              // 关闭读端
    write(fd[1], "hello", 6);
    close(fd[1]);
}
```

**管道的容量**:Linux 默认 64 KB,可通过 `F_SETPIPE_SZ` 修改

**特点**:
- 阻塞:read() 等待 write
- 半双工:需要 2 个管道做全双工
- 退出:进程退出时 fd 关闭,读端返回 0 (EOF)
- 大小限制:`PIPE_BUF` (4096 字节),写小于此可保证原子

### 2. 命名管道 (FIFO / Named Pipe)

**特点**:
- **有文件名**(在文件系统中)
- **任意进程**可访问
- 半双工

**创建**:
```bash
mkfifo /tmp/myfifo
ls -l /tmp/myfifo
# prw-r--r-- 1 user user 0  myfifo
#     ↑ p 表示命名管道
```

**系统调用**:
```c
#include <sys/stat.h>

int mkfifo(const char *pathname, mode_t mode);
```

**使用**:
```c
// 进程 A: 写
int fd = open("/tmp/myfifo", O_WRONLY);
write(fd, "hello", 6);
close(fd);

// 进程 B: 读
int fd = open("/tmp/myfifo", O_RDONLY);
char buf[100];
int n = read(fd, buf, sizeof(buf));
close(fd);
```

**特点**:
- 打开 O_RDONLY 会阻塞,直到有进程以写方式打开(反之亦然)
- 文件系统中有节点(`ls -l` 可见)
- 适合单机 IPC,客户端-服务器模式

### 3. 管道的使用场景

- shell 管道: `cmd1 | cmd2 | cmd3`
- 父子进程通信
- 简单数据流

---

## 三、消息队列 (Message Queue)

### 1. POSIX 消息队列

**特点**:
- **有优先级**
- **异步**:发完不阻塞
- **有消息类型**(可按类型读取)
- 适合**短消息**通知

**系统调用**:

```c
#include <mqueue.h>

// 创建或打开
mqd_t mq_open(const char *name, int oflag, mode_t mode, struct mq_attr *attr);
// name: 名字,以 "/" 开头, 如 "/myqueue"

// 关闭
int mq_close(mqd_t mqdes);

// 删除
int mq_unlink(const char *name);

// 发送
int mq_send(mqd_t mqdes, const char *msg_ptr, size_t msg_len, unsigned int msg_prio);

// 接收
ssize_t mq_receive(mqd_t mqdes, char *msg_ptr, size_t msg_len, unsigned int *msg_prio);

// 通知 (异步)
int mq_notify(mqd_t mqdes, const struct sigevent *sevp);
```

**使用示例**:
```c
// 发送
mqd_t mq = mq_open("/myqueue", O_CREAT | O_WRONLY, 0644, NULL);
mq_send(mq, "hello", 6, 1);  // 优先级 1
mq_close(mq);

// 接收
mqd_t mq = mq_open("/myqueue", O_RDONLY);
char buf[100];
unsigned int prio;
ssize_t n = mq_receive(mq, buf, sizeof(buf), &prio);
mq_close(mq);
mq_unlink("/myqueue");
```

### 2. System V 消息队列

```c
#include <sys/msg.h>

// 创建或获取
int msgget(key_t key, int msgflg);

// 发送
int msgsnd(int msqid, const void *msgp, size_t msgsz, int msgflg);

// 接收
ssize_t msgrcv(int msqid, void *msgp, size_t msgsz, long msgtyp, int msgflg);

// 控制
int msgctl(int msqid, int cmd, struct msqid_ds *buf);
```

### 3. 消息队列对比

| 维度       | POSIX MQ               | System V MQ        |
|------------|------------------------|--------------------|
| 名字       | 文件名风格 /name       | 数字 key           |
| 删除       | 引用计数 / 显式 unlink | 显式 msgctl        |
| 接口       | 简洁                   | 复杂               |
| 通知       | mq_notify + 信号       | 需自行实现         |
| 优先级     | 0-31                   | 0-32767            |
| 限制       | /proc/sys/fs/mqueue/*  | 系统限制           |

**使用命令**:
```bash
# POSIX MQ
cat /proc/sys/fs/mqueue/queues_max
cat /proc/sys/fs/mqueue/msg_max

# System V MQ
ipcs -q
ipcrm -q <id>
```

---

## 四、共享内存 (Shared Memory) - 最快

### 1. 原理

**让多个进程把同一段物理内存映射到自己的虚拟地址空间**

```text
进程 A 虚拟地址空间       物理内存
   0x1000  ───────┐     ┌──────────┐
                   ├────→│ 共享内存 │  ←── 同一物理页
   0x1000  ───────┘     └──────────┘
进程 B 虚拟地址空间
```

**特点**:
- **最快的 IPC**(不需要数据复制)
- **需要自己同步**(配合信号量、文件锁等)

### 2. POSIX 共享内存

**4 步用法**:
```c
#include <sys/mman.h>
#include <fcntl.h>

// 1. 创建或打开
int shm_fd = shm_open("/myshm", O_CREAT | O_RDWR, 0644);

// 2. 设置大小
ftruncate(shm_fd, SIZE);

// 3. 映射
void *ptr = mmap(NULL, SIZE, PROT_READ | PROT_WRITE, MAP_SHARED, shm_fd, 0);

// 4. 取消映射 & 关闭
munmap(ptr, SIZE);
close(shm_fd);

// 删除
shm_unlink("/myshm");
```

**特点**:
- 文件名风格:`/name`
- 用了 VFS,挂载在 `/dev/shm`
- 自动随系统清理(引用计数)

### 3. System V 共享内存

```c
#include <sys/shm.h>

// 创建或获取
int shmid = shmget(key_t key, size_t size, int shflg);

// 附加
void *ptr = shmat(shmid, NULL, 0);

// 分离
int shmdt(const void *shmaddr);

// 控制
int shmctl(int shmid, int cmd, struct shmid_ds *buf);
```

**使用命令**:
```bash
# 查看
ipcs -m
# 删除
ipcrm -m <id>
```

### 4. 共享内存的应用

- **数据库**:Oracle、PostgreSQL 共享内存
- **进程间大数据传输**
- **mmap 同一文件**(多进程共享)
- **GPU 驱动**(CUDA)
- **DPDK / SPDK**:大页共享内存

### 5. 共享内存的同步

**需要同步**,否则数据竞争:

- 信号量
- futex (Linux 高效同步)
- 互斥锁 (pthread_mutex)
- 文件锁 (flock/fcntl)
- atomic 操作 (C11)

---

## 五、信号量 (Semaphore)

### 1. 信号量概念

**信号量**:一个**整数计数器**,用于控制对共享资源的访问

**两种操作**:
- **P (wait / down / proberen)**:减 1,如果 < 0 则阻塞
- **V (signal / up / verhogen)**:加 1,唤醒等待者

### 2. POSIX 信号量

**两类**:
- **命名信号量**:不同进程用,通过名字
- **未命名信号量**:同一进程内,内存中

**命名信号量 API**:
```c
#include <semaphore.h>

// 打开
sem_t *sem_open(const char *name, int oflag, mode_t mode, unsigned int value);

// P 操作
int sem_wait(sem_t *sem);                  // 阻塞
int sem_trywait(sem_t *sem);              // 非阻塞
int sem_timedwait(sem_t *sem, const struct timespec *abs_timeout);  // 超时

// V 操作
int sem_post(sem_t *sem);

// 关闭
int sem_close(sem_t *sem);

// 删除
int sem_unlink(const char *name);
```

**未命名信号量 API**:
```c
sem_t sem;
sem_init(&sem, 0, 1);     // 0 = 进程内,初值 1
sem_wait(&sem);
sem_post(&sem);
sem_destroy(&sem);
```

### 3. System V 信号量

```c
#include <sys/sem.h>

// 创建
int semid = semget(key_t key, int nsems, int semflg);

// 操作
int semop(int semid, struct sembuf *sops, size_t nsops);

// 控制
int semctl(int semid, int semnum, int cmd, ...);
```

### 4. futex (Fast Userspace muTEX)

**futex**:Linux 内核的"快速同步原语"

**思想**:
- 用户态做大部分工作(自旋等待)
- 必要时进入内核(等待队列)
- 比纯内核同步快得多

**API**:
```c
#include <linux/futex.h>
#include <sys/syscall.h>

int futex(uint32_t *uaddr, int futex_op, uint32_t val,
          const struct timespec *timeout, uint32_t *uaddr2, uint32_t val3);

// 用法:
// 1. 原子地修改一个 int
// 2. 如果修改后的值让其他线程需要等待,调用 futex 阻塞
// 3. 唤醒时调用 futex
```

**应用**:
- pthread_mutex 的底层实现
- C++ std::mutex
- Java 的 j.u.c

**`/proc/sys/kernel/futex_*`** 可调

---

## 六、消息队列 vs 共享内存 vs 管道

| 维度       | 管道            | 消息队列     | 共享内存     |
|------------|-----------------|--------------|--------------|------------|
| 速度       | 中              | 中           | **最快**     |
| 数据量     | 字节流          | 消息         | 任意         |
| 亲缘要求   | 匿名:有,FIFO:无 | 无           | 无           |
| 持久       | 临时            | 临时         | 临时         |
| 优先级     | 无              | 有           | 无           |
| 同步       | 自动            | 自动         | **需要**     |
| 用法       | 流              | 消息         | 共享数据     |
| 经典用途   | shell \         | pipe         | 通知         | 大数据传输 |

---

## 七、信号 (Signal)

### 1. 信号概念

**信号**:内核向进程**异步**通知事件的机制(软中断)

**本质**:
- 1-31:传统信号(不可靠)
- 32-64:实时信号(可靠,带数据)
- 进程收到信号 → 走默认动作 / 执行信号处理函数

### 2. 常见信号

| 信号        | 编号  | 默认动作       | 含义                   |
|-------------|-------|----------------|------------------------|
| SIGHUP      | 1     | Term           | 终端挂起,守护进程重载  |
| SIGINT      | 2     | Term           | Ctrl+C                 |
| SIGQUIT     | 3     | Core           | Ctrl+\                 |
| SIGILL      | 4     | Core           | 非法指令               |
| SIGTRAP     | 5     | Core           | 断点                   |
| SIGABRT     | 6     | Core           | abort()                |
| SIGBUS      | 7     | Core           | 总线错误               |
| SIGFPE      | 8     | Core           | 算术错误               |
| **SIGKILL** | **9** | **Term**       | **强制终止(不可捕获)** |
| **SIGUSR1** | 10    | Term           | 用户自定义             |
| **SIGSEGV** | 11    | Core           | 段错误                 |
| **SIGUSR2** | 12    | Term           | 用户自定义             |
| **SIGPIPE** | 13    | Term           | 写关闭的管道           |
| SIGALRM     | 14    | Term           | alarm()                |
| **SIGTERM** | 15    | Term           | 优雅终止               |
| SIGCHLD     | 17    | Ign            | 子进程退出             |
| SIGCONT     | 18    | Cont           | 继续                   |
| **SIGSTOP** | 19    | **Stop**       | **暂停(不可捕获)**     |
| SIGTSTP     | 20    | Stop           | Ctrl+Z                 |
| SIGTTIN     | 21    | Stop           | 后台读终端             |
| SIGTTOU     | 22    | Stop           | 后台写终端             |
| SIGURG      | 23    | Ign            | 紧急数据               |
| SIGXCPU     | 24    | Core           | CPU 超时               |
| SIGXFSZ     | 25    | Core           | 文件大小超限           |
| SIGALRM     | 26    | Term           | 实时钟                 |
| SIGIO       | 29    | Term           | I/O 就绪               |
| SIGPWR      | 30    | Term           | 电源故障               |
| SIGSYS      | 31    | Core           | 系统调用错误           |

**实时信号**:SIGRTMIN (32) ~ SIGRTMAX (64),带数据,不会合并

### 3. 信号 API

```c
// 发送
int kill(pid_t pid, int sig);    // 发给进程
int raise(int sig);              // 发给自己
unsigned int alarm(unsigned int seconds);  // 定时
int killpg(int pgrp, int sig);   // 发给进程组

// 处理 (handler)
sighandler_t signal(int signum, sighandler_t handler);
int sigaction(int signum, const struct sigaction *act, struct sigaction *oldact);

// 屏蔽 / 解除
int sigprocmask(int how, const sigset_t *set, sigset_t *oldset);
int sigemptyset(sigset_t *set);
int sigfillset(sigset_t *set);
int sigaddset(sigset_t *set, int signum);
int sigdelset(sigset_t *set, int signum);
int sigismember(const sigset_t *set, int signum);

// 挂起
int pause(void);
int sigsuspend(const sigset_t *mask);

// 等待
int sigwait(const sigset_t *set, int *sig);
int sigwaitinfo(const sigset_t *set, siginfo_t *info);
int sigtimedwait(...);

// 队列
int sigqueue(pid_t pid, int sig, const union sigval value);
```

### 4. 信号使用示例

```c
// 设置 SIGINT handler
void handler(int sig) {
    printf("Caught %d\n", sig);
}

int main() {
    signal(SIGINT, handler);
    
    // 推荐用 sigaction
    struct sigaction sa = {0};
    sa.sa_handler = handler;
    sigemptyset(&sa.sa_mask);
    sa.sa_flags = 0;
    sigaction(SIGINT, &sa, NULL);
    
    while (1) {
        pause();    // 等待信号
    }
}
```

### 5. 关键信号详解

- **SIGKILL (9)**:不能捕获、阻塞、忽略。用于强制终止
- **SIGSTOP (19)**:不能捕获、阻塞、忽略。用于暂停进程
- **SIGCHLD (17)**:子进程退出,父进程默认忽略
- **SIGPIPE (13)**:写已关闭的管道,默认终止,用于网络服务器
- **SIGIO (29)**:异步 I/O 通知

---

## 八、Unix Domain Socket

### 1. 概述

**Unix Domain Socket (UDS)**:在本机进程间通信的 socket

- 像网络 socket 但走**文件系统**
- 性能高(不经过网络协议栈)
- 支持流式(SOCK_STREAM) 和数据报(SOCK_DGRAM)
- 支持**fd 传递**、**凭证传递**

### 2. 三种类型

- **SOCK_STREAM**:类似 TCP,面向连接
- **SOCK_DGRAM**:类似 UDP,无连接
- **SOCK_SEQPACKET**:有序数据报

### 3. API

```c
#include <sys/socket.h>
#include <sys/un.h>

// 创建
int sockfd = socket(AF_UNIX, SOCK_STREAM, 0);

// 绑定地址
struct sockaddr_un addr = {0};
addr.sun_family = AF_UNIX;
strcpy(addr.sun_path, "/tmp/mysocket");
bind(sockfd, (struct sockaddr *)&addr, sizeof(addr));

// 监听
listen(sockfd, 128);

// 接受 / 连接 (同 TCP)
```

### 4. 抽象命名空间 (Linux)

**Linux 新增**:`abstract:` 命名空间,无需文件系统

```c
strcpy(addr.sun_path, "\0mysocket");  // \0 开头
// socket 在文件系统不可见
```

**优点**:
- 不污染文件系统
- 不用担心清理
- 长度可达 108 字节(普通是 108)

### 5. 关键优势

- 性能高(本机最快之一)
- **fd 传递**:`SCM_RIGHTS` (进程间传文件描述符)
- **凭证传递**:`SCM_CREDENTIALS` (传 UID/PID)

---

## 九、内存映射 (mmap) IPC

### 1. mmap 共享文件

多个进程 mmap 同一文件,共享内存

```c
// 进程 A
int fd = open("shared.dat", O_RDWR | O_CREAT, 0644);
ftruncate(fd, SIZE);
void *ptr = mmap(NULL, SIZE, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);

// 进程 B
int fd2 = open("shared.dat", O_RDWR);
void *ptr2 = mmap(NULL, SIZE, PROT_READ | PROT_WRITE, MAP_SHARED, fd2, 0);
// ptr 和 ptr2 指向同一物理内存
```

### 2. 匿名 mmap

```c
// 父子进程共享匿名映射
void *ptr = mmap(NULL, SIZE, PROT_READ | PROT_WRITE,
                  MAP_SHARED | MAP_ANONYMOUS, -1, 0);
if (fork() == 0) {
    // 子进程能访问 ptr
}
```

### 3. mmap 优缺点

**优点**:
- 自动同步到磁盘(MS_SYNC)
- 多进程共享方便
- 高效(避免 read/write 系统调用)

**缺点**:
- 文件大小有限制(2GB 通常)
- 需要文件描述符

---

## 十、Socket (网络 IPC)

### 1. 概述

**Socket**:跨网络的进程通信

- 同一台机器可走环回 (127.0.0.1)
- 跨机器走真实网络
- **详见 [13-网络协议栈.md](13-网络协议栈.md)**

### 2. Unix Domain vs TCP

| 维度     | UDS          | TCP/UDP loopback  |
|----------|--------------|-------------------|
| 协议栈   | 无           | 完整 TCP/IP       |
| 性能     | **高**       | 较低              |
| 可靠性   | 同本地       | 同 TCP/UDP        |
| fd 传递  | 支持         | 有限              |
| 跨机     | 否           | 是                |

---

## 十一、文件锁 (File Locking)

### 1. flock (建议锁)

```c
#include <sys/file.h>

int flock(int fd, int operation);
// LOCK_SH: 共享锁(读)
// LOCK_EX: 排他锁(写)
// LOCK_UN: 解锁
// LOCK_NB: 非阻塞
```

**特点**:
- 锁整个文件
- 进程级(非线程级)
- 锁随 fd 关闭自动释放

### 2. fcntl (POSIX 建议锁)

```c
int fcntl(int fd, F_SETLK, &flock);
int fcntl(int fd, F_SETLKW, &flock);  // 阻塞
int fcntl(int fd, F_GETLK, &flock);
```

**特点**:
- 可锁字节范围
- 进程级

### 3. 文件锁的用途

- 防止多个进程同时写文件
- 实现简单的进程间互斥
- 数据库锁
- 日志文件轮转

---

## 十二、RPC (远程过程调用)

### 1. RPC 概念

**RPC**:让程序像调用本地函数一样调用远程函数

**核心思想**:
- 客户端 stub 序列化参数,发送到服务端
- 服务端 stub 反序列化,执行函数,序列化结果
- 客户端反序列化结果

### 2. 主流 RPC 框架

| 框架         | 协议        | 序列化       | 特点                |
|--------------|-------------|--------------|---------------------|
| **gRPC**     | HTTP/2      | Protobuf     | Google 出品,主流    |
| **Thrift**   | 自定义      | 自定义       | Facebook 出品       |
| **Dubbo**    | HTTP/RPC    | JSON/Hessian | 阿里出品            |
| **JSON-RPC** | HTTP        | JSON         | 简单,Web 友好       |
| **ONC RPC**  | 自定义      | XDR          | 老牌 Unix RPC       |
| **Avro RPC** | 自定义      | Avro         | Apache 出品         |
| **Finagle**  | HTTP/Thrift | Thrift       | Twitter 出品        |
| **gRPC-Web** | HTTP/1.1    | Protobuf     | gRPC 的浏览器版     |

### 3. RPC 流程

```text
Client                    Network                Server
  |                          |                        |
| 1. 调用 client stub |                     |
|---------------------|---------------------|---------------|
| 2. 序列化参数       |                     |
| 3. 发送请求         | ---- 网络传输 ----> |
|                     |                     | 4. 接收       |
|                     |                     | 5. 反序列化   |
|                     |                     | 6. 调用函数   |
|                     |                     | 7. 序列化结果 |
| 8. 接收             | <---- 网络传输 ---- |
| 9. 反序列化         |                     |
| 10. 返回结果        |                     |
```

### 4. gRPC 示例

```protobuf
// .proto 文件
service Greeter {
    rpc SayHello (HelloRequest) returns (HelloReply);
}
message HelloRequest {
    string name = 1;
}
message HelloReply {
    string message = 1;
}
```

```python
# 客户端
import grpc
import hello_pb2
import hello_pb2_grpc

channel = grpc.insecure_channel('localhost:50051')
stub = hello_pb2_grpc.GreeterStub(channel)
response = stub.SayHello(hello_pb2.HelloRequest(name='World'))
print(response.message)
```

---

## 十三、消息中间件 (分布式 IPC)

### 1. 消息队列中间件

| 中间件            | 协议    | 特点                       |
|-------------------|---------|----------------------------|
| **Kafka**         | 自定义  | 高吞吐、日志流             |
| **RabbitMQ**      | AMQP    | 功能丰富                   |
| **RocketMQ**      | 自定义  | 阿里,Java 生态             |
| **Pulsar**        | 自定义  | Yahoo 出品                 |
| **ActiveMQ**      | JMS     | 老牌                       |
| **NATS**          | 自定义  | 轻量                       |
| **Redis Streams** | 自定义  | Redis 内置                 |

### 2. Kafka 核心概念

- **Broker**:Kafka 节点
- **Topic**:消息主题
- **Partition**:分区(可并行)
- **Producer/Consumer**:生产/消费
- **Consumer Group**:消费者组
- **Offset**:消费位移

### 3. 选择建议

- **超吞吐日志/事件流** → Kafka
- **复杂路由** → RabbitMQ
- **事务消息** → RocketMQ
- **轻量** → NATS
- **云原生** → Pulsar

---

## 十四、零拷贝 IPC

### 1. splice / tee

```c
ssize_t splice(int fd_in, off64_t *off_in, int fd_out,
               off64_t *off_out, size_t len, unsigned int flags);
ssize_t tee(int fd_in, int fd_out, size_t len, unsigned int flags);
```

**splice**:两个 fd 间零拷贝
**tee**:零拷贝复制(类似 tee 命令)

### 2. sendfile

```c
ssize_t sendfile(int out_fd, int in_fd, off_t *offset, size_t count);
```

**两个文件描述符间零拷贝**

### 3. vmsplice

```c
ssize_t vmsplice(int fd, const struct iovec *iov, unsigned long nr_segs, unsigned int flags);
```

**用户态内存直接到管道**

---

## 十五、IPC 性能对比

| IPC 方式              | 速度       | 亲缘要求 | 跨机 | 复杂度 | 典型延迟        |
|-----------------------|------------|----------|------|--------|-----------------|
| 匿名管道              | 中         | 有       | 否   | 低     | 几 μs           |
| 命名管道 (FIFO)       | 中         | 无       | 否   | 低     | 几 μs           |
| POSIX 消息队列        | 中         | 无       | 否   | 中     | 几 μs           |
| System V 消息队列     | 中         | 无       | 否   | 中     | 几 μs           |
| **POSIX 共享内存**    | **最快**   | 无       | 否   | 中     | 几十 ns         |
| **System V 共享内存** | **最快**   | 无       | 否   | 中     | 几十 ns         |
| mmap                  | **最快**   | 通常有   | 否   | 中     | 几十 ns         |
| 信号                  | 异步       | 无       | 否   | 低     | 几 μs           |
| 命名信号量            | 中         | 无       | 否   | 低     | 几 μs           |
| 套接字 (Unix Domain)  | 中-快      | 无       | 否   | 中     | 几 μs           |
| 套接字 (TCP)          | 慢         | 无       | 是   | 中     | 几十 μs ~ 几 ms |
| 套接字 (UDP)          | 中         | 无       | 是   | 中     | 几十 μs         |
| 文件 (write/read)     | 慢         | 无       | 否   | 低     | 几 ms           |
| RPC (gRPC)            | 慢         | 无       | 是   | 高     | 几 ms           |

---

## 十六、IPC 选型指南

### 1. 选型决策树

```text
需要 IPC
├── 跨机器?
│   ├── 是 → TCP/HTTP/RPC/gRPC
│   └── 否
│       ├── 大数据传输?
│       │   ├── 是 → 共享内存 / mmap
│       │   └── 否
│       │       ├── 同步/互斥?
│       │       │   ├── 是 → 信号量 / futex / 文件锁
│       │       │   └── 否
│       │       │       ├── 异步事件?
│       │       │       │   ├── 是 → 信号
│       │       │       │   └── 否
│       │       │       │       ├── 父子进程?
│       │       │       │       │   ├── 是 → 匿名管道
│       │       │       │       │   └── 否
│       │       │       │       │       ├── 双向 RPC?
│       │       │       │       │       │   ├── 是 → Unix Domain Socket
│       │       │       │       │       │   └── 否 → 命名管道
│       │       │       │       │       └── 单向流 → 命名管道
```

### 2. 实际建议

| 场景                          | 推荐                |
|-------------------------------|---------------------|
| 父子进程流式通信              | 匿名管道            |
| 任意进程短消息                | POSIX 消息队列      |
| 大块数据共享                  | 共享内存 + 信号量   |
| 进程同步                      | 信号量、futex       |
| 异步事件通知                  | 信号                |
| 任意进程双向 RPC              | Unix Domain Socket  |
| 跨网络                        | TCP / gRPC          |
| 高吞吐日志流                  | Kafka               |
| 简单锁                        | 文件锁 (flock)      |

---

## 十七、IPC 调试与监控

### 1. System V IPC 命令

```bash
# 查看
ipcs         # 全部
ipcs -m      # 共享内存
ipcs -q      # 消息队列
ipcs -s      # 信号量

# 删除
ipcrm -m <id>
ipcrm -q <id>
ipcrm -s <id>
```

### 2. POSIX IPC

```bash
# POSIX 共享内存
ls /dev/shm/

# POSIX 消息队列
mount | grep mqueue
ls /dev/mqueue/    # 需先 mount -t mqueue mqueue /dev/mqueue
```

### 3. 信号调试

```bash
# 看信号
strace -e signal
strace -e trace=signal

# 进程默认信号处理
cat /proc/PID/status | grep SigCgt
# SigCgt, SigIgn, SigPnd, SigBlk, SigIgn
```

### 4. UDS 监控

```bash
# 列 UDS
ss -x
ss -xl    # 详细信息
```

---

## 十八、IPC 的陷阱

### 1. 性能陷阱

- **共享内存没同步**:数据竞争、脏读
- **频繁 IPC**:系统调用开销大
- **小消息用消息队列**:浪费资源
- **大文件用管道**:不灵活

### 2. 安全陷阱

- **管道文件权限**:默认 644
- **共享内存访问**:无保护,任何进程可读写
- **FIFO 注入**:小心数据合法性
- **UDS 文件权限**:`chmod 660 /tmp/sock`
- **抽象命名空间**:本地用户可访问

### 3. 资源陷阱

- **信号量忘记释放**:死锁
- **共享内存忘记 detach**:资源泄露
- **消息队列满**:send 阻塞或失败
- **FIFO 不消费**:写阻塞
- **管道容量**:`fcntl F_SETPIPE_SZ` 调整

### 4. 编程陷阱

- **多线程访问共享内存**:需要同步
- **父子进程共享 fd**:关闭一端
- **信号非异步安全**:用 async-signal-safe 函数
- **TCP 关闭**:正确 close,防止 TIME_WAIT 过多

---

## 十九、现代 IPC 趋势

### 1. 高性能 IPC

- **io_uring**:异步共享 ring buffer
- **eBPF**:内核态数据共享
- **DPDK / SPDK**:用户态驱动

### 2. 跨语言

- **gRPC**:通用 RPC
- **Apache Arrow**:跨语言数据共享
- **Cap'n Proto**:高效的 RPC + 序列化

### 3. 云原生

- **service mesh**:Sidecar 代理
- **NATS / Kafka**:事件驱动
- **gRPC over HTTP/2 + QUIC**

### 4. 安全 IPC

- **TLS / mTLS**
- **Wireguard**(安全 VPN)
- **Wireguard 风格的 IPC**

---

## 二十、核心要点速记

- **共享内存是最快的 IPC**(零拷贝)
- **管道适合父子进程流式数据**
- **消息队列适合短消息 + 优先级**
- **信号适合异步事件**
- **Socket (Unix Domain) 适合双向 RPC**
- **信号量、互斥锁用于同步**
- **System V IPC 较老,POSIX IPC 推荐**
- **futex** = Linux 高效同步原语
- **SIGKILL (9) 和 SIGSTOP (19) 不能捕获**
- **SIGCHLD** 用于子进程回收
- **mmap 同一文件** = 多进程共享
- **gRPC 是现代 RPC 首选**(HTTP/2 + Protobuf)
- **Kafka 是高吞吐日志/事件流首选**
- **futex 是 pthread_mutex 底层**
- **System V 共享内存 vs POSIX 共享内存**:
  - POSIX 用文件 / 名字,System V 用 key
  - POSIX 在 /dev/shm/,System V 由系统管理
- **管道容量 64KB**,可调
- **POSIX MQ 名字** = "/name",在 /dev/mqueue/
- **FIFO 路径** = 普通文件系统路径
- **UDS 抽象命名空间** 以 \0 开头
- **sendfile / splice** = 零拷贝
- **strace** = 调试 IPC 系统调用
- **ipcs / ipcrm** = System V IPC 工具
