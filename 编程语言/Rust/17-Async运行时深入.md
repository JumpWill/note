# 17 - Async 运行时深入

本章从底层看 async/await:Future trait、Pin、Poll、Waker,以及如何手写迷你运行时。

## 一、Future trait 底层

### 1. trait 定义

```rust
pub trait Future {
    type Output;

    fn poll(self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Self::Output>;
}

pub enum Poll<T> {
    Ready(T),
    Pending,
}
```

### 2. 简单 Future

```rust
use std::future::Future;
use std::pin::Pin;
use std::task::{Context, Poll};
use std::time::Duration;

struct Delay {
    when: std::time::Instant,
}

impl Future for Delay {
    type Output = ();

    fn poll(self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<()> {
        if std::time::Instant::now() >= self.when {
            Poll::Ready(())
        } else {
            // 通知 executor 再次 poll
            cx.waker().wake_by_ref();
            Poll::Pending
        }
    }
}

async fn foo() {
    Delay { when: std::time::Instant::now() + Duration::from_secs(1) }.await;
    println!("done");
}
```

## 二、async/await 反编译

```rust
async fn add(a: i32, b: i32) -> i32 {
    a + b
}

// 反编译后(简化):
fn add(a: i32, b: i32) -> impl Future<Output = i32> {
    AddFuture { a, b }
}

struct AddFuture {
    a: i32,
    b: i32,
}

impl Future for AddFuture {
    type Output = i32;
    fn poll(self: Pin<&mut Self>, _cx: &mut Context<'_>) -> Poll<i32> {
        Poll::Ready(self.a + self.b)
    }
}
```

## 三、`Pin` 与自引用结构

### 1. 为什么需要 Pin

```rust
// 自引用结构:不能安全 move
struct SelfRef {
    data: String,
    ptr: *const String,    // 指向自己的 data
}

// move 后 ptr 仍指向旧地址 -> 悬垂指针
```

`Pin<&mut T>` 保证 `T` 不会被 move,自引用结构才安全。

### 2. `Pin` API

```rust
use std::pin::Pin;

fn main() {
    let mut s = String::from("hello");
    let p1: Pin<&mut String> = Pin::new(&mut s);

    // 访问
    println!("{}", p1);                 // 通过 Deref
    // p1 不能 move s,直到 Pin 被 drop

    // boxed self-ref
    let boxed = Box::pin(SelfRef {
        data: String::from("hello"),
        ptr: std::ptr::null(),
    });

    // boxed.pinned 指针指向自己的 data
    // 这里仅示意,实际初始化需 unsafe + Pin::get_mut
}
```

### 3. `!Unpin`

```rust
use std::marker::PhantomPinned;

// 不实现 Unpin,所以 Pin 后不能 move
struct MyType {
    _marker: PhantomPinned,
}

fn main() {
    let boxed: Pin<Box<MyType>> = Box::pin(MyType {
        _marker: PhantomPinned,
    });
    // boxed 不能 move 出 Pin
}
```

### 4. `Unpin` trait

- `Unpin` = 可以安全 move 出 Pin,大多数类型自动实现
- `PhantomPinned` 不实现 `Unpin`,需要 Pin 固定

```rust
use std::pin::Pin;

fn requires_unpin<T: Unpin>(t: T) {}
fn requires_pinned<T: !Unpin>(t: Pin<&mut T>) {}
```

## 四、`async fn` 与 `Future`

### 1. 状态机

```rust
async fn complex() -> i32 {
    let x = fetch1().await;     // 状态 0
    let y = fetch2(x).await;    // 状态 1
    x + y                        // 状态 2
}

// 编译器生成:
enum ComplexFuture {
    Start { fut1: Fetch1Future },
    Wait1 { x: i32, fut2: Fetch2Future },
    Done,
}

impl Future for ComplexFuture {
    type Output = i32;
    fn poll(self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<i32> {
        match self.get_mut() {
            ComplexFuture::Start { fut1 } => {
                match fut1.poll(cx) {
                    Poll::Ready(x) => {
                        // 转入 Wait1 状态
                        *self = ComplexFuture::Wait1 {
                            x,
                            fut2: fetch2(x),
                        };
                        Poll::Pending  // 再次 poll
                    }
                    Poll::Pending => Poll::Pending,
                }
            }
            ComplexFuture::Wait1 { x, fut2 } => {
                match fut2.poll(cx) {
                    Poll::Ready(y) => {
                        *self = ComplexFuture::Done;
                        Poll::Ready(*x + y)
                    }
                    Poll::Pending => Poll::Pending,
                }
            }
            ComplexFuture::Done => panic!("polled after completion"),
        }
    }
}
```

### 2. 取消语义

```rust
async fn cancelable() {
    let _r = Resource::new();
    step1().await;
    step2().await;  // 如果在这里 drop,_r 仍会 drop
}
```

`async` 块 drop 时,内部资源按 drop 顺序释放。

## 五、`Stream` trait

```rust
use std::task::Poll;

pub trait Stream {
    type Item;

    fn poll_next(self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Option<Self::Item>>;

    fn size_hint(&self) -> (usize, Option<usize>) {
        (0, None)
    }
}

pub enum Poll<T> {
    Ready(T),
    Pending,
}
```

### 1. 自定义 Stream

```rust
use std::pin::Pin;
use std::task::{Context, Poll};

struct Counter {
    current: u32,
    max: u32,
}

impl Counter {
    fn new(max: u32) -> Self {
        Self { current: 0, max }
    }
}

impl futures::Stream for Counter {
    type Item = u32;

    fn poll_next(self: Pin<&mut Self>, _cx: &mut Context<'_>) -> Poll<Option<Self::Item>> {
        let me = self.get_mut();
        if me.current < me.max {
            me.current += 1;
            Poll::Ready(Some(me.current))
        } else {
            Poll::Ready(None)
        }
    }
}

// 使用(Future crate 提供)
use futures::StreamExt;

#[tokio::main]
async fn main() {
    let mut stream = Counter::new(5);
    while let Some(n) = stream.next().await {
        println!("{}", n);
    }
}
```

### 2. `futures` crate 的 StreamExt

```rust
use futures::StreamExt;

#[tokio::main]
async fn main() {
    let stream = futures::stream::iter(1..=5);

    // 适配器
    let sum: i32 = stream
        .map(|x| x * x)
        .filter(|x| *x > 5)
        .sum()
        .await;
    println!("sum: {}", sum);

    // 合并
    let s1 = futures::stream::iter(vec![1, 2, 3]);
    let s2 = futures::stream::iter(vec![4, 5, 6]);
    let merged = s1.chain(s2);
    let v: Vec<_> = merged.collect().await;
}
```

## 六、自定义迷你 Executor

### 1. 项目结构

```
mini_executor/
├── Cargo.toml
└── src/
    ├── main.rs
    ├── executor.rs
    └── task.rs
```

### 2. Task 抽象

```rust
// src/task.rs
use std::future::Future;
use std::pin::Pin;
use std::sync::{Arc, Mutex};
use std::task::{Context, Poll, Wake, Waker};

pub struct Task {
    future: Mutex<Pin<Box<dyn Future<Output = ()> + Send>>>,
    executor: Arc<Executor>,
}

impl Task {
    pub fn new(future: impl Future<Output = ()> + Send + 'static, executor: Arc<Executor>) -> Self {
        Self {
            future: Mutex::new(Box::pin(future)),
            executor,
        }
    }

    pub fn poll(self: Arc<Self>) {
        let waker = self.clone().into_waker();
        let mut cx = Context::from_waker(&waker);
        let mut future = self.future.lock().unwrap();
        match future.as_mut().poll(&mut cx) {
            Poll::Ready(_) => {}
            Poll::Pending => {}
        }
    }

    fn into_waker(self: Arc<Self>) -> Waker {
        Waker::from(Arc::new(TaskWaker { task: self }))
    }
}

struct TaskWaker {
    task: Arc<Task>,
}

impl Wake for TaskWaker {
    fn wake(self: Arc<Self>) {
        self.task.executor.queue.push(self.task.clone());
        self.task.executor.notify();
    }
}

impl TaskWaker {
    fn wake_task(task: &Arc<Task>) {
        task.executor.queue.push(task.clone());
        task.executor.notify();
    }
}
```

### 3. Executor

```rust
// src/executor.rs
use std::collections::VecDeque;
use std::sync::{Arc, Condvar, Mutex};

pub struct Executor {
    queue: Arc<Queue>,
}

struct Queue {
    tasks: Mutex<VecDeque<Arc<crate::task::Task>>>,
    notify: Condvar,
}

impl Executor {
    pub fn new() -> Self {
        Self { queue: Arc::new(Queue {
            tasks: Mutex::new(VecDeque::new()),
            notify: Condvar::new(),
        }) }
    }

    pub fn spawn(&self, future: impl std::future::Future<Output = ()> + Send + 'static) {
        let task = Arc::new(crate::task::Task::new(future, Arc::new(self.clone())));
        self.queue.tasks.lock().unwrap().push_back(task);
        self.queue.notify.notify_one();
    }

    pub fn run(&self) {
        loop {
            let task = {
                let mut q = self.queue.tasks.lock().unwrap();
                q.pop_front()
            };

            match task {
                Some(t) => t.poll(),
                None => {
                    let q = self.queue.tasks.lock().unwrap();
                    if q.is_empty() {
                        let _ = self.queue.notify.wait(q).unwrap();
                    }
                }
            }
        }
    }
}

impl Clone for Executor {
    fn clone(&self) -> Self {
        Self { queue: Arc::clone(&self.queue) }
    }
}
```

### 4. 主程序

```rust
// src/main.rs
mod executor;
mod task;

use std::sync::Arc;
use std::time::Duration;

fn main() {
    let ex = Arc::new(executor::Executor::new());
    let ex2 = ex.clone();

    ex.spawn(async {
        println!("task 1 start");
        Delay { when: std::time::Instant::now() + Duration::from_millis(100) }.await;
        println!("task 1 done");
    });

    ex2.spawn(async {
        println!("task 2 start");
        Delay { when: std::time::Instant::now() + Duration::from_millis(50) }.await;
        println!("task 2 done");
    });

    ex.run();
}

// 自定义 Delay future
struct Delay { when: std::time::Instant }

impl std::future::Future for Delay {
    type Output = ();

    fn poll(self: std::pin::Pin<&mut Self>, cx: &mut std::task::Context<'_>) -> std::task::Poll<()> {
        if std::time::Instant::now() >= self.when {
            std::task::Poll::Ready(())
        } else {
            // 注册 waker
            let when = self.when;
            std::thread::spawn(move || {
                let now = std::time::Instant::now();
                if now < when {
                    std::thread::sleep(when - now);
                }
                cx.waker().wake_by_ref();
            });
            std::task::Poll::Pending
        }
    }
}
```

## 七、Tokio 深入

### 1. 项目结构

```
tokio_app/
├── Cargo.toml
├── src/
│   ├── main.rs
│   ├── handlers/
│   │   ├── mod.rs
│   │   └── user.rs
│   ├── services/
│   │   ├── mod.rs
│   │   └── user_service.rs
│   └── errors.rs
└── tests/
    └── integration.rs
```

### 2. `Cargo.toml`

```toml
[package]
name = "tokio_app"
version = "0.1.0"
edition = "2021"

[dependencies]
tokio = { version = "1", features = ["full"] }
anyhow = "1"
tracing = "0.1"
tracing-subscriber = "0.3"
```

### 3. 多文件示例:HTTP 风格异步处理

`src/main.rs`:

```rust
mod errors;
mod handlers;
mod services;

use handlers::user::{create_user, get_user};
use std::sync::Arc;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt::init();

    let user_service = Arc::new(services::user_service::UserService::new());

    // 模拟请求
    let u = create_user(user_service.clone(), "alice".into(), 30).await?;
    let got = get_user(user_service.clone(), u.id).await?;

    println!("created: {:?}", u);
    println!("got: {:?}", got);

    Ok(())
}
```

`src/errors.rs`:

```rust
use thiserror::Error;

#[derive(Error, Debug)]
pub enum AppError {
    #[error("not found")]
    NotFound,
    #[error("invalid input")]
    InvalidInput,
    #[error("internal: {0}")]
    Internal(String),
}
```

`src/services/mod.rs`:

```rust
pub mod user_service;
```

`src/services/user_service.rs`:

```rust
use crate::errors::AppError;
use std::collections::HashMap;
use std::sync::Mutex;

#[derive(Debug, Clone)]
pub struct User {
    pub id: u64,
    pub name: String,
    pub age: u8,
}

pub struct UserService {
    inner: Mutex<HashMap<u64, User>>,
    next_id: Mutex<u64>,
}

impl UserService {
    pub fn new() -> Self {
        Self {
            inner: Mutex::new(HashMap::new()),
            next_id: Mutex::new(1),
        }
    }

    pub async fn create(&self, name: String, age: u8) -> Result<User, AppError> {
        if name.is_empty() {
            return Err(AppError::InvalidInput);
        }
        // 模拟异步 IO
        tokio::time::sleep(std::time::Duration::from_millis(10)).await;

        let mut next_id = self.next_id.lock().unwrap();
        let mut inner = self.inner.lock().unwrap();
        let id = *next_id;
        *next_id += 1;

        let user = User { id, name, age };
        inner.insert(id, user.clone());
        Ok(user)
    }

    pub async fn get(&self, id: u64) -> Result<User, AppError> {
        tokio::time::sleep(std::time::Duration::from_millis(5)).await;
        self.inner
            .lock()
            .unwrap()
            .get(&id)
            .cloned()
            .ok_or(AppError::NotFound)
    }
}
```

`src/handlers/mod.rs`:

```rust
pub mod user;
```

`src/handlers/user.rs`:

```rust
use crate::errors::AppError;
use crate::services::user_service::{User, UserService};
use std::sync::Arc;

pub async fn create_user(
    svc: Arc<UserService>,
    name: String,
    age: u8,
) -> Result<User, AppError> {
    svc.create(name, age).await
}

pub async fn get_user(
    svc: Arc<UserService>,
    id: u64,
) -> Result<User, AppError> {
    svc.get(id).await
}
```

### 4. 集成测试

```rust
// tests/integration.rs
use std::sync::Arc;
use tokio_app::{create_user, get_user};
use tokio_app::services::user_service::UserService;

#[tokio::test]
async fn test_create_and_get() {
    let svc = Arc::new(UserService::new());
    let u = create_user(svc.clone(), "bob".into(), 25).await.unwrap();
    assert_eq!(u.name, "bob");

    let got = get_user(svc, u.id).await.unwrap();
    assert_eq!(got.age, 25);
}
```

## 八、Tokio 模式

### 1. `select!` - 抢答

```rust
use tokio::time::{sleep, Duration};

#[tokio::main]
async fn main() {
    tokio::select! {
        _ = sleep(Duration::from_secs(1)) => println!("1s"),
        _ = sleep(Duration::from_secs(2)) => println!("2s"),
    }
}
```

### 2. 超时

```rust
use tokio::time::{timeout, Duration};

async fn fetch_with_timeout() -> Result<String, &'static str> {
    timeout(Duration::from_secs(2), fetch_data())
        .await
        .map_err(|_| "timeout")?
}

async fn fetch_data() -> Result<String, &'static str> {
    Ok("data".into())
}
```

### 3. 后台任务 + 优雅退出

```rust
use tokio::signal;

#[tokio::main]
async fn main() {
    // 后台任务
    let bg = tokio::spawn(async {
        loop {
            tokio::time::sleep(Duration::from_secs(1)).await;
            println!("tick");
        }
    });

    // 等待 Ctrl-C
    signal::ctrl_c().await.unwrap();
    println!("shutting down...");

    bg.abort();
}
```

### 4. Channel + 工作池

```rust
use tokio::sync::mpsc;

#[tokio::main]
async fn main() {
    let (tx, mut rx) = mpsc::channel::<i32>(100);

    // 工作池
    let workers: Vec<_> = (0..4).map(|i| {
        let mut rx = rx.clone();
        tokio::spawn(async move {
            while let Some(job) = rx.recv().await {
                println!("worker {} 处理 {}", i, job);
                tokio::time::sleep(Duration::from_millis(100)).await;
            }
        })
    }).collect();

    drop(rx); // 关闭原 rx

    // 投递任务
    for i in 0..20 {
        tx.send(i).await.unwrap();
    }
    drop(tx); // 关闭

    for w in workers { w.await.unwrap(); }
}
```

## 九、`async-trait`

让 trait 方法支持 async。

```toml
[dependencies]
async-trait = "0.1"
```

```rust
use async_trait::async_trait;

#[async_trait]
trait Repository {
    async fn find(&self, id: u64) -> Option<String>;
    async fn save(&self, entity: &str) -> Result<(), String>;
}

struct InMemoryRepo;

#[async_trait]
impl Repository for InMemoryRepo {
    async fn find(&self, _id: u64) -> Option<String> { None }
    async fn save(&self, _e: &str) -> Result<(), String> { Ok(()) }
}
```

## 十、常用 crate

| Crate | 用途 |
| --- | --- |
| `tokio` | 主流异步运行时 |
| `async-std` | 标准库风格的异步 |
| `futures` | Future / Stream 工具 |
| `async-trait` | async fn in trait |
| `tokio-stream` | tokio 流适配 |
| `tower` | 异步服务抽象 + 中间件 |
| `hyper` | HTTP 底层 |
| `axum` | Web 框架(基于 tower) |
| `tonic` | gRPC |

## 十一、要点速记

- **Future 由编译器生成状态机,async/await 是语法糖**
- **`poll` 返回 `Pending` 时必须保证 `Waker` 在 ready 时被调用**
- **`Pin<&mut T>` 保证 T 不会被 move,自引用结构必须 Pin**
- **`PhantomPinned` 标记 `!Unpin`**
- **`Stream` = 异步版本的 Iterator,产生 `Option<Item>`**
- **Executor = 调度器,Waker = 唤醒信号,Reactor = I/O 多路复用**
- **Tokio 多线程运行时 = 多 worker 线程 + 全局队列 + 工作窃取**
- **`select!` 取第一个 ready 的 future,其他 cancel**
- **`timeout` 给 future 套一层超时**
- **`tokio::spawn` 在运行时上调度任务,返回 JoinHandle**
- **`JoinHandle.abort()` 取消任务**
- **同步代码调 async 用 `tokio::runtime::Runtime` block_on 或 `#[tokio::main]`**
