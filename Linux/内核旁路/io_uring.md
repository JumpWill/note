## 概念

io_uring 是 Linux 5.1+ 引入的异步 I/O 框架，用户态 + 内核态共享两个 ring buffer（SQ 提交队列 + CQ 完成队列），提交和收割都不走 syscall，配 IORING_SETUP_SQPOLL 还能免唤醒。文件 I/O、网络收发、计时器都能用。

云服务器友好：跟 NIC 无关，virtio-net / ENA 都能跑，是云上唯一"零改造"的内核旁路手段。

参考数据（tick 接收场景）：

* p50 ~5–10μs，p99 ~20–40μs，p999 ~80μs
* 单核吞吐 ~150–300 万 msg/s，CPU 50–70%

生产里关键的两个 io_uring 特性：

* `IORING_OP_RECV` 的 multishot 模式：一次 SQE 反复收割 CQ，省掉每次提交，适合 UDP/组播行情流
* `IOSQE_BUFFER_SELECT` + 注册 buffer ring：避免每次 recv 拷贝进用户 buf 的内存分配

## C（liburing，官方）

`liburing` 是 Jens Axboe 写的官方封装，包管理器直接装。

```c
#include <liburing.h>
#include <sys/socket.h>
#include <netinet/in.h>

/* 行情 UDP 包常见 64~256 字节,这里示例用 64 */
#define TICK_LEN 64

int main(void) {
    /* UDP socket 绑行情端口,真要收组播再 setsockopt IP_ADD_MEMBERSHIP */
    int fd = socket(AF_INET, SOCK_DGRAM, 0);
    struct sockaddr_in a = {.sin_family = AF_INET, .sin_port = htons(9000)};
    bind(fd, (struct sockaddr*)&a, sizeof(a));

    struct io_uring ring;
    io_uring_queue_init(128, &ring, 0);

    char buf[TICK_LEN];
    struct iovec iov = {.iov_base = buf, .iov_len = sizeof(buf)};

    struct io_uring_sqe *sqe = io_uring_get_sqe(&ring);
    io_uring_prep_recv(sqe, fd, &iov, 1, 0);
    io_uring_submit(&ring);

    struct io_uring_cqe *cqe;
    io_uring_wait_cqe(&ring, &cqe);
    /* cqe->res = 收到的字节数; buf 里是行情二进制 */
    io_uring_cqe_seen(&ring, cqe);

    io_uring_queue_exit(&ring);
    return 0;
}
```

编译：`gcc -o app app.c -luring`

## C++

直接用 liburing 的 C API，加个轻量 RAII 包装。或者 `boost::asio` 从 1.81 起支持 io_uring 执行器（`io_uring_executor`），用法跟 epoll 一样。

```cpp
#include <boost/asio.hpp>
namespace asio = boost::asio;

asio::io_context ctx(asio::io_uring_executor());   // 后端走 io_uring
asio::ip::udp::socket sock(ctx);
sock.open(asio::ip::udp::v4());
sock.bind({{}, 9000});
// 组播: sock.set_option(asio::ip::multicast::join_group(mcast_addr));

char buf[64];
sock.async_receive(asio::buffer(buf),
    [](auto ec, auto n){ /* n 是包字节数,从 buf[0..n) 解析 tick */ });
ctx.run();
```

## Rust

* `tokio-uring`：tokio 团队出品，最高层的封装，但已停止积极维护
* `io-uring`：更底层，纯 syscall 风格，控制精细
* `glommio`：基于 io_uring 的协程运行时，绑核 + 共享内存友好

```rust
use io_uring::{IoUring, opcode, types};
use std::os::fd::RawFd;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // 真实场景: socket(AF_INET, SOCK_DGRAM) + bind 9000 + IP_ADD_MEMBERSHIP
    let fd: RawFd = unsafe { libc::socket(libc::AF_INET, libc::SOCK_DGRAM, 0) };

    let mut ring = IoUring::new(128)?;
    let mut buf = vec![0u8; 64];

    let sqe = opcode::Recv::new(types::Fd(fd), buf.as_mut_ptr(), buf.len() as _, 0)
        .build()
        .user_data(0x42);
    unsafe { ring.submission().push(&sqe) }?;
    ring.submit_and_wait(1)?;

    let cqe = ring.completion().next().expect("cqe");
    let n = cqe.result();
    if n > 0 { /* 从 &buf[..n as _] 解析 tick */ }
    Ok(())
}
```

## Go

官方没有第一方支持，社区有 `github.com/iceber/iouring-go`（最成熟），可以 `Read / Write / Accept / Recv / Send` 全套 syscall 化。

```go
import (
    "syscall"
    "github.com/iceber/iouring-go"
)

func main() {
    fd, _ := syscall.Socket(syscall.AF_INET, syscall.SOCK_DGRAM, 0)
    syscall.Bind(fd, &syscall.SockaddrInet4{Port: 9000})
    // 组播: setsockopt IP_ADD_MEMBERSHIP

    ring, _ := iouring.New(128)
    defer ring.Close()

    buf := make([]byte, 64)
    ch := ring.SubmitRequest(iouring.Recv(fd, buf, 0).WithUserData(1))
    res := <-ch
    n, _ := res.ReturnValue()
    // 从 buf[:n] 解析 tick
}
```

Go 1.21+ 起 `internal/poll` 有 `IO_URING` 实验开关（`GOEXPERIMENT=iouring`），但稳定性一般，生产还是推荐 `iouring-go`。

## Python

`pyo3-uring` / `liburing-py` / `python-uring` 几个库都能调，但都是 ctypes 风格的薄封装，性能不极致。Python 本身 GIL + 解释器开销大，io_uring 的省 syscall 优势在 Python 里被吃光。

* 如果是研究 / 原型：随便挑一个库试试
* 真要生产做 tick 接收：别用 Python 直接收，前面套一层 C / Rust 写的接收器，Python 走共享内存或 ZeroMQ 拿解析好的 bar

```python
# 演示用,不推荐生产
import socket, pyuring

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(('0.0.0.0', 9000))

ring = pyuring.IoUring(128)
buf = bytearray(64)
sqe = pyuring.RecvOp(fd=sock.fileno(), addr=buf, length=64, flags=0)
ring.submit(sqe)
cqe = ring.wait_cqe()
# cqe.result 是包字节数,buf[:n] 里是 tick 二进制
```

## Node.js

Node 22+ 起 libuv 默认支持 io_uring 后端（Linux 5.6+ 时启用）。对应用层透明，不用改代码就能享受省 syscall 红利。

```bash
# 确认启用了
node -e "console.log(process.uv)"  # 看 internal/uv 报告 IO_URING
```

业务代码不变（`dgram` 走的就是内核 io_uring recv）：

```js
const dgram = require('dgram');

const sock = dgram.createSocket('udp4');
sock.bind(9000);
sock.on('message', (msg, rinfo) => {
    // msg 是 tick 二进制,直接进解析器
});
```

## 各语言选用建议

* 极致性能 / 行情接收服务：C / C++ / Rust
* 通用高并发服务：C++ (boost::asio) / Rust (tokio) / Go (iouring-go)
* 脚本 / 研究：Python 调底层，别自己写
* Web 服务：Node.js 22+ 透明收益，写法不变
