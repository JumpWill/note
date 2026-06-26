## 概念

io_uring 是 Linux 5.1+ 引入的异步 I/O 框架，用户态 + 内核态共享两个 ring buffer（SQ 提交队列 + CQ 完成队列），提交和收割都不走 syscall，配 IORING_SETUP_SQPOLL 还能免唤醒。文件 I/O、网络收发、计时器都能用。

云服务器友好：跟 NIC 无关，virtio-net / ENA 都能跑，是云上唯一"零改造"的内核旁路手段。

参考数据（tick 接收场景）：

* p50 ~5–10μs，p99 ~20–40μs，p999 ~80μs
* 单核吞吐 ~150–300 万 msg/s，CPU 50–70%

## C（liburing，官方）

`liburing` 是 Jens Axboe 写的官方封装，包管理器直接装。

```c
#include <liburing.h>

int main(void) {
    struct io_uring ring;
    io_uring_queue_init(32, &ring, 0);

    int fd = open("data.bin", O_RDONLY);
    struct iovec iov = { .iov_base = buf, .iov_len = 4096 };

    struct io_uring_sqe *sqe = io_uring_get_sqe(&ring);
    io_uring_prep_readv(sqe, fd, &iov, 1, 0);
    io_uring_submit(&ring);

    struct io_uring_cqe *cqe;
    io_uring_wait_cqe(&ring, &cqe);
    /* cqe->res 是 read 返回的字节数 */
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
asio::io_context ctx(asio::io_uring_executor());  // 后端走 io_uring
asio::ip::tcp::socket sock(ctx);
sock.async_read_some(asio::buffer(buf), [](auto ec, auto n){ ... });
```

## Rust

* `tokio-uring`：tokio 团队出品，最高层的封装，但已停止积极维护
* `io-uring`：更底层，纯 syscall 风格，控制精细
* `glommio`：基于 io_uring 的协程运行时，绑核 + 共享内存友好

```rust
// io-uring 风格
use io_uring::{IoUring, opcode, types};

let mut ring = IoUring::new(32)?;
let fd = std::fs::File::open("data.bin")?;
let mut buf = vec![0u8; 4096];

let sqe = opcode::Read::new(fd.as_raw_fd(), buf.as_mut_ptr(), buf.len() as _)
    .build()
    .user_data(0x42);
unsafe { ring.submission().push(&sqe) }?;
ring.submit_and_wait(1)?;

let cqe = ring.completion().next().expect("cqe");
assert_eq!(cqe.user_data(), 0x42);
let n = cqe.result();
```

## Go

官方没有第一方支持，社区有 `github.com/iceber/iouring-go`（最成熟），可以 `Read / Write / Accept / Recv / Send` 全套 syscall 化。

```go
import "github.com/iceber/iouring-go"

ring, _ := iouring.New(32)
defer ring.Close()

fd, _ := unix.Open("data.bin", unix.O_RDONLY, 0)
defer unix.Close(fd)

buf := make([]byte, 4096)
req := iouring.Read(fd, buf, 0).WithUserData(0x42)
ch := ring.SubmitRequest(req)
result := <-ch
n, _ := result.ReturnValue()  // 读到的字节数
```

Go 1.21+ 起 `internal/poll` 有 `IO_URING` 实验开关（`GOEXPERIMENT=iouring`），但稳定性一般，生产还是推荐 `iouring-go`。

## Python

`pyo3-uring` / `liburing-py` / `python-uring` 几个库都能调，但都是 ctypes 风格的薄封装，性能不极致。Python 本身 GIL + 解释器开销大，io_uring 的省 syscall 优势在 Python 里被吃光。

* 如果是研究 / 原型：随便挑一个库试试
* 真要生产做 tick 接收：别用 Python 直接收，前面套一层 C / Rust 写的接收器，Python 走共享内存或 ZeroMQ 拿解析好的 bar

```python
# 演示用，不推荐生产
import pyuring
ring = pyuring.IoUring(32)
sqe = pyuring.ReadOp(fd=fd, addr=buf, length=4096, offset=0)
ring.submit(sqe)
cqe = ring.wait_cqe()
print(cqe.result)  # 读到的字节数
```

## Node.js

Node 22+ 起 libuv 默认支持 io_uring 后端（Linux 5.6+ 时启用）。对应用层透明，不用改代码就能享受省 syscall 红利。

```bash
# 确认启用了
node -e "console.log(process.uv)"  # 看 internal/uv 报告 IO_URING
```

业务代码不变：

```js
const fs = require('fs');
fs.readFile('data.bin', (err, data) => { /* ... */ });
// 内部自动走 io_uring
```

## 各语言选用建议

* 极致性能 / 行情接收服务：C / C++ / Rust
* 通用高并发服务：C++ (boost::asio) / Rust (tokio) / Go (iouring-go)
* 脚本 / 研究：Python 调底层，别自己写
* Web 服务：Node.js 22+ 透明收益，写法不变
