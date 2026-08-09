# 07 - 泛型与 Trait

泛型用于代码复用,Trait 定义共享行为,两者结合是 Rust 抽象能力的核心。

## 一、泛型基础

### 1. 泛型函数

```rust
use std::cmp::PartialOrd;

// 泛型函数:要求 T 可比较
fn largest<T: PartialOrd>(list: &[T]) -> &T {
    let mut largest = &list[0];
    for item in list {
        if item > largest {
            largest = item;
        }
    }
    largest
}

fn main() {
    let nums = vec![34, 50, 25, 100, 65];
    println!("max: {}", largest(&nums)); // 100

    let chars = vec!['y', 'm', 'a', 'q'];
    println!("max: {}", largest(&chars)); // y
}
```

### 2. 泛型结构体

```rust
#[derive(Debug)]
struct Point<T> {
    x: T,
    y: T,
}

// 多类型参数
#[derive(Debug)]
struct Pair<T, U> {
    first: T,
    second: U,
}

impl<T> Point<T> {
    fn new(x: T, y: T) -> Self {
        Self { x, y }
    }

    fn x(&self) -> &T {
        &self.x
    }
}

// 只对特定类型实现方法
impl<T: std::fmt::Display + PartialOrd> Point<T> {
    fn cmp_display(&self) {
        if self.x >= self.y {
            println!("x >= y");
        } else {
            println!("x < y");
        }
    }
}

// 针对具体类型实现方法
impl Point<f32> {
    fn distance_from_origin(&self) -> f32 {
        (self.x.powi(2) + self.y.powi(2)).sqrt()
    }
}

fn main() {
    let p = Point::new(1, 2);
    println!("{:?}", p);

    let pf = Point::new(1.0, 2.0);
    println!("dist: {}", pf.distance_from_origin());
}
```

### 3. 泛型枚举

```rust
// 标准库:Option<T> 和 Result<T, E> 都是泛型
enum Either<L, R> {
    Left(L),
    Right(R),
}

fn main() {
    let e: Either<i32, &str> = Either::Left(42);
    match e {
        Either::Left(n) => println!("left: {}", n),
        Either::Right(s) => println!("right: {}", s),
    }
}
```

### 4. 常量泛型

```rust
struct Buffer<T, const N: usize> {
    data: [T; N],
}

impl<T: Default + Copy, const N: usize> Buffer<T, N> {
    fn new() -> Self {
        Self { data: [T::default(); N] }
    }
}

fn main() {
    let buf: Buffer<u8, 1024> = Buffer::new();
    println!("size: {}", buf.data.len());
}
```

## 二、Trait 定义

### 1. 基本 trait

```rust
pub trait Summary {
    fn summarize(&self) -> String;

    // 默认实现
    fn summarize_author(&self) -> String {
        String::from("(未知作者)")
    }
}

pub struct NewsArticle {
    pub headline: String,
    pub author: String,
    pub location: String,
}

impl Summary for NewsArticle {
    fn summarize(&self) -> String {
        format!("{}, by {} ({})", self.headline, self.author, self.location)
    }
}

pub struct Tweet {
    pub username: String,
    pub content: String,
}

impl Summary for Tweet {
    fn summarize(&self) -> String {
        format!("@{}: {}", self.username, self.content)
    }

    // 覆盖默认实现
    fn summarize_author(&self) -> String {
        format!("@{}", self.username)
    }
}

fn main() {
    let a = NewsArticle {
        headline: String::from("新闻"),
        author: String::from("张三"),
        location: String::from("北京"),
    };
    let t = Tweet {
        username: String::from("rustlang"),
        content: String::from("Rust 1.85 发布"),
    };

    println!("{}", a.summarize());
    println!("{}", t.summarize_author()); // 覆盖默认
}
```

### 2. trait 作为参数

```rust
// impl Trait 语法(语法糖)
fn notify(item: &impl Summary) {
    println!("news: {}", item.summarize());
}

// trait bound 形式(等价)
fn notify_bound<T: Summary>(item: &T) {
    println!("news: {}", item.summarize());
}

// 多个约束
fn notify_multi(item: &(impl Summary + std::fmt::Display)) {
    println!("{}: {}", item, item.summarize());
}

// where 子句
fn notify_where<T>(item: &T)
where
    T: Summary + std::fmt::Display,
{
    println!("{}: {}", item, item.summarize());
}

fn main() {
    let t = Tweet { username: String::from("x"), content: String::from("hi") };
    notify(&t);
}
```

### 3. 返回实现了 trait 的类型

```rust
fn make_summarizable() -> impl Summary {
    Tweet {
        username: String::from("rust"),
        content: String::from("..."),
    }
}

// 限制:必须返回单一具体类型
// 下面代码编译错:
// fn make_summarizable(b: bool) -> impl Summary {
//     if b {
//         NewsArticle { ... }
//     } else {
//         Tweet { ... }
//     }
// }
```

### 4. trait 继承

```rust
trait Animal {
    fn name(&self) -> &str;
}

trait Pet: Animal {  // 实现 Pet 必须先实现 Animal
    fn owner(&self) -> &str;
}

struct Dog {
    name: String,
    owner: String,
}

impl Animal for Dog {
    fn name(&self) -> &str { &self.name }
}

impl Pet for Dog {
    fn owner(&self) -> &str { &self.owner }
}
```

## 三、Trait Object 与动态分发

### 1. `dyn Trait` - 运行时多态

```rust
trait Draw {
    fn draw(&self);
}

struct Circle { radius: f64 }
struct Square { side: f64 }

impl Draw for Circle {
    fn draw(&self) { println!("Circle r={}", self.radius); }
}
impl Draw for Square {
    fn draw(&self) { println!("Square s={}", self.side); }
}

// Vec<Box<dyn Trait>>:异构集合
fn main() {
    let shapes: Vec<Box<dyn Draw>> = vec![
        Box::new(Circle { radius: 1.0 }),
        Box::new(Square { side: 2.0 }),
    ];

    for s in &shapes {
        s.draw();  // 动态分发
    }
}
```

### 2. `impl Trait` vs `dyn Trait`

| 维度 | `impl Trait` | `dyn Trait` |
| --- | --- | --- |
| 分发 | 静态(单态化) | 动态(虚表) |
| 性能 | 零开销 | 一次间接调用 |
| 异构 | ❌ 必须单类型 | ✔ 可放不同类型 |
| 内存 | 内联 / 栈 | 堆分配(Box) |
| 适用 | 性能敏感 | 插件 / 集合 |

## 四、常用标准 Trait

### 1. `Clone` / `Copy`

```rust
#[derive(Clone)]
struct User {
    name: String,
}

// Copy 要求:所有字段 Copy
#[derive(Clone, Copy)]
struct Point {
    x: i32,
    y: i32,
}

let p = Point { x: 1, y: 2 };
let p2 = p;     // 复制
println!("{}", p.x);  // 仍可用
```

### 2. `Debug` / `Display`

```rust
use std::fmt;

#[derive(Debug)]
struct User { name: String }

struct Money(f64);

impl fmt::Display for Money {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "¥{:.2}", self.0)
    }
}

fn main() {
    let u = User { name: String::from("Alice") };
    println!("{:?}", u);       // Debug
    let m = Money(99.95);
    println!("{}", m);         // Display
}
```

### 3. `PartialEq` / `Eq`

```rust
#[derive(PartialEq, Eq)]
struct User {
    id: u32,
    name: String,
}

fn main() {
    let a = User { id: 1, name: String::from("a") };
    let b = User { id: 1, name: String::from("a") };
    println!("{}", a == b);    // true
}
```

### 4. `PartialOrd` / `Ord`

```rust
use std::cmp::Ordering;

#[derive(PartialEq, Eq, PartialOrd, Ord)]
struct Score(u32);

// 浮点:只实现 PartialOrd(不实现 Ord,因为 NaN 不可比较)
```

### 5. `Hash`

```rust
use std::collections::HashSet;
use std::hash::{Hash, Hasher};

#[derive(Hash, Eq, PartialEq)]
struct Point { x: i32, y: i32 }

fn main() {
    let mut s: HashSet<Point> = HashSet::new();
    s.insert(Point { x: 1, y: 2 });
}
```

### 6. `Default`

```rust
#[derive(Default)]
struct Config {
    port: u16,           // 默认 0
    debug: bool,         // 默认 false
    name: String,        // 默认 ""
}

let c = Config::default();
```

### 7. `From` / `Into`

```rust
struct MyInt(i32);

impl From<i32> for MyInt {
    fn from(v: i32) -> Self {
        MyInt(v)
    }
}

// 反向 Into 自动获得
let m: MyInt = 42.into();
```

### 8. `Iterator`

详见 [10-闭包与迭代器.md](10-闭包与迭代器.md)。

## 五、高级 Trait

### 1. 关联类型

```rust
trait Container {
    type Item;

    fn first(&self) -> Option<&Self::Item>;
    fn len(&self) -> usize;
}

struct Stack<T> {
    items: Vec<T>,
}

impl<T> Container for Stack<T> {
    type Item = T;

    fn first(&self) -> Option<&T> {
        self.items.first()
    }

    fn len(&self) -> usize {
        self.items.len()
    }
}
```

### 2. 默认泛型参数

```rust
trait Add<Rhs = Self> {
    type Output;
    fn add(self, rhs: Rhs) -> Self::Output;
}

// 默认为 Self,可重写
```

### 3. 完全限定语法

```rust
trait A {
    fn hello(&self) { println!("A::hello"); }
}
trait B {
    fn hello(&self) { println!("B::hello"); }
}

struct MyType;
impl A for MyType {}
impl B for MyType {}

fn main() {
    let t = MyType;
    t.hello();                          // ❌ 二义性

    // 完全限定
    <MyType as A>::hello(&t);           // A::hello
    <MyType as B>::hello(&t);           // B::hello
}
```

### 4. Supertrait(子 trait 用父 trait 方法)

```rust
trait OutlinePrint: Display {
    fn outline(&self) {
        let s = self.to_string();
        let len = s.len();
        println!("{}", "*".repeat(len + 4));
        println!("*{}*", " ".repeat(len + 2));
        println!("* {} *", s);
        println!("*{}*", " ".repeat(len + 2));
        println!("{}", "*".repeat(len + 4));
    }
}
```

### 5. newtype 模式

```rust
// 解决孤儿规则:不能为外部类型实现外部 trait
struct Wrapper(Vec<String>);

impl std::fmt::Display for Wrapper {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "[{}]", self.0.join(", "))
    }
}

fn main() {
    let w = Wrapper(vec!["a".into(), "b".into()]);
    println!("{}", w);
}
```

### 6. blanket impl

```rust
trait MyTrait {
    fn name(&self) -> &str;
}

impl<T: Display> MyTrait for T {
    fn name(&self) -> &str {
        "any displayable"
    }
}
```

## 六、要点速记

- **泛型用尖括号 `<T>`,默认在 `impl<T>` 块中**
- **Trait 定义共享行为,默认实现可覆盖**
- **`impl Trait`** = 语法糖,等价 trait bound
- **多个约束用 `+` 或 `where` 子句**
- **`dyn Trait` 动态分发,Box 包装,可异构**
- **`impl Trait` 静态分发,单态化,零开销**
- **常用 trait:`Debug`/`Display`/`Clone`/`Copy`/`PartialEq`/`Eq`/`Hash`/`Default`/`From`/`Into`**
- **`#[derive(...)]`** 自动实现常见 trait
- **孤儿规则:不能为外部类型实现外部 trait,用 newtype**
- **关联类型在 trait 内部 `type Item`,实现时具体化**
- **完全限定语法 `<Type as Trait>::method()` 解决二义性**

---

## 七、综合实战:多文件插件系统

完整的多文件项目,展示 trait object、泛型、关联类型、扩展 trait 的综合应用。

### 1. 项目结构

```text
plugin_system/
├── Cargo.toml
├── src/
│   ├── lib.rs           # 库入口
│   ├── plugin.rs        # Plugin trait + 注册表
│   ├── builtin.rs       # 内置插件
│   ├── context.rs       # 插件上下文
│   └── pipeline.rs      # 插件执行管道
└── tests/
    └── plugin_test.rs
```

### 2. `Cargo.toml`

```toml
[package]
name = "plugin_system"
version = "0.1.0"
edition = "2021"
```

### 3. `src/plugin.rs` - 核心 trait

```rust
use std::any::Any;

use crate::context::Context;

/// 所有插件实现这个 trait
pub trait Plugin: Any + Send + Sync {
    fn name(&self) -> &str;

    /// 插件初始化
    fn init(&mut self, _ctx: &mut Context) {}

    /// 处理数据,返回 Some 表示产生结果
    fn process(&self, ctx: &mut Context) -> Option<String>;

    /// 任意类型转换,用于 downcast
    fn as_any(&self) -> &dyn Any;
}

/// 插件注册表
pub struct PluginRegistry {
    plugins: Vec<Box<dyn Plugin>>,
}

impl PluginRegistry {
    pub fn new() -> Self {
        Self { plugins: Vec::new() }
    }

    pub fn register<P: Plugin + 'static>(&mut self, plugin: P) -> &mut Self {
        self.plugins.push(Box::new(plugin));
        self
    }

    pub fn get(&self, name: &str) -> Option<&dyn Plugin> {
        self.plugins.iter().find(|p| p.name() == name).map(|p| p.as_ref())
    }

    pub fn len(&self) -> usize {
        self.plugins.len()
    }

    pub fn is_empty(&self) -> bool {
        self.plugins.is_empty()
    }

    pub fn iter(&self) -> impl Iterator<Item = &dyn Plugin> {
        self.plugins.iter().map(|p| p.as_ref())
    }
}

impl Default for PluginRegistry {
    fn default() -> Self {
        Self::new()
    }
}
```

### 4. `src/context.rs` - 共享上下文

```rust
use std::collections::HashMap;

#[derive(Default)]
pub struct Context {
    pub user: Option<String>,
    pub data: HashMap<String, String>,
    pub trace: Vec<String>,
}

impl Context {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn with_user(mut self, user: impl Into<String>) -> Self {
        self.user = Some(user.into());
        self
    }

    pub fn set(&mut self, key: impl Into<String>, value: impl Into<String>) {
        self.data.insert(key.into(), value.into());
    }

    pub fn get(&self, key: &str) -> Option<&String> {
        self.data.get(key)
    }

    pub fn trace(&mut self, msg: impl Into<String>) {
        self.trace.push(msg.into());
    }
}
```

### 5. `src/builtin.rs` - 内置插件

```rust
use std::any::Any;

use crate::context::Context;
use crate::plugin::Plugin;

/// 转换用户名为大写
pub struct UpperPlugin;

impl Plugin for UpperPlugin {
    fn name(&self) -> &str { "upper" }

    fn process(&self, ctx: &mut Context) -> Option<String> {
        let user = ctx.user.clone()?;
        Some(user.to_uppercase())
    }

    fn as_any(&self) -> &dyn Any { self }
}

/// 添加问候语
pub struct GreetPlugin {
    pub greeting: String,
}

impl Plugin for GreetPlugin {
    fn name(&self) -> &str { "greet" }

    fn process(&self, ctx: &mut Context) -> Option<String> {
        let user = ctx.user.clone()?;
        Some(format!("{}, {}", self.greeting, user))
    }

    fn as_any(&self) -> &dyn Any { self }
}

/// 记录访问日志
pub struct AuditPlugin;

impl Plugin for AuditPlugin {
    fn name(&self) -> &str { "audit" }

    fn process(&self, ctx: &mut Context) -> Option<String> {
        if let Some(u) = &ctx.user {
            ctx.trace(format!("audit: user={}", u));
        }
        Some("logged".into())
    }

    fn as_any(&self) -> &dyn Any { self }
}
```

### 6. `src/pipeline.rs` - 执行管道

```rust
use crate::context::Context;
use crate::plugin::PluginRegistry;

pub struct Pipeline {
    registry: PluginRegistry,
    order: Vec<String>,
}

impl Pipeline {
    pub fn new(registry: PluginRegistry) -> Self {
        Self { registry, order: Vec::new() }
    }

    pub fn chain(mut self, name: impl Into<String>) -> Self {
        self.order.push(name.into());
        self
    }

    pub fn run(&self, mut ctx: Context) -> Vec<String> {
        let mut results = Vec::new();
        for name in &self.order {
            if let Some(plugin) = self.registry.get(name) {
                if let Some(r) = plugin.process(&mut ctx) {
                    results.push(r);
                }
            }
        }
        results
    }
}
```

### 7. `src/lib.rs`

```rust
pub mod builtin;
pub mod context;
pub mod pipeline;
pub mod plugin;

pub use builtin::{AuditPlugin, GreetPlugin, UpperPlugin};
pub use context::Context;
pub use pipeline::Pipeline;
pub use plugin::{Plugin, PluginRegistry};
```

### 8. `tests/plugin_test.rs`

```rust
use plugin_system::*;

#[test]
fn test_register_and_run() {
    let mut registry = PluginRegistry::new();
    registry
        .register(AuditPlugin)
        .register(GreetPlugin { greeting: "Hello".into() })
        .register(UpperPlugin);

    let ctx = Context::new().with_user("alice");
    let pipeline = Pipeline::new(registry)
        .chain("audit")
        .chain("greet")
        .chain("upper");

    let results = pipeline.run(ctx);
    assert_eq!(results.len(), 3);
    assert_eq!(results[2], "ALICE"); // upper 输出
}

#[test]
fn test_plugin_lookup() {
    let mut registry = PluginRegistry::new();
    registry.register(UpperPlugin);

    let p = registry.get("upper").unwrap();
    assert_eq!(p.name(), "upper");
    assert!(registry.get("nonexistent").is_none());
}

#[test]
fn test_downcast() {
    let mut registry = PluginRegistry::new();
    registry.register(GreetPlugin { greeting: "Hi".into() });

    let p = registry.get("greet").unwrap();

    // downcast 到具体类型
    if let Some(g) = p.as_any().downcast_ref::<GreetPlugin>() {
        assert_eq!(g.greeting, "Hi");
    } else {
        panic!("downcast failed");
    }
}

#[test]
fn test_context_trace() {
    let mut registry = PluginRegistry::new();
    registry.register(AuditPlugin);

    let pipeline = Pipeline::new(registry).chain("audit");
    let mut ctx = Context::new().with_user("bob");
    pipeline.run(ctx.clone());

    assert_eq!(ctx.trace.len(), 1);
    assert!(ctx.trace[0].contains("bob"));
}
```

### 9. 关键设计点

| 概念 | 用法 |
| --- | --- |
| `trait Plugin: Any` | 支持 downcast |
| `Box<dyn Plugin>` | 异构插件集合 |
| `Vec<Box<dyn Plugin>>` | 注册表 |
| 关联类型 / dyn | Plugin trait object 化 |
| `as_any()` | 类型擦除与还原 |
| `impl Iterator<Item = &dyn Plugin>` | 隐藏内部表示 |

### 10. 进阶扩展

**泛型执行器**(零开销):

```rust
use std::marker::PhantomData;

// 单态化的执行器
pub struct TypedPlugin<P: Plugin> {
    plugin: P,
    _phantom: PhantomData<P>,
}

impl<P: Plugin> TypedPlugin<P> {
    pub fn new(plugin: P) -> Self {
        Self { plugin, _phantom: PhantomData }
    }

    pub fn run(&self, ctx: &mut Context) -> Option<String> {
        self.plugin.process(ctx)
    }
}

// 静态分发,零开销
let tp = TypedPlugin::new(UpperPlugin);
let result = tp.run(&mut ctx);
```

**扩展 trait**(为已有类型加方法):

```rust
pub trait ContextExt {
    fn with_user_and_role(self, user: &str, role: &str) -> Self;
}

impl ContextExt for Context {
    fn with_user_and_role(mut self, user: &str, role: &str) -> Self {
        self.user = Some(user.into());
        self.data.insert("role".into(), role.into());
        self
    }
}

// 用法
let ctx = Context::new().with_user_and_role("alice", "admin");
```

**Trait bound + Where 子句**:

```rust
pub fn run_with<F>(plugin: &F, ctx: &mut Context) -> Option<String>
where
    F: Plugin + ?Sized,
{
    plugin.process(ctx)
}
```
