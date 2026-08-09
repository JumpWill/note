# 08 - 模块与 Cargo

## 一、模块系统

### 1. 模块层级

```
Package (Cargo.toml)
└── Crate (lib.rs / main.rs)
    └── Module (mod ...)
        └── Item (fn / struct / enum / trait / ...)
```

### 2. 定义模块

```rust
mod front_of_house {
    pub mod hosting {
        pub fn add_to_waitlist() {
            println!("added");
        }

        // 默认私有
        fn seat_at_table() {}
    }

    mod serving {
        fn take_order() {}
    }
}

fn main() {
    front_of_house::hosting::add_to_waitlist();
    // front_of_house::serving::take_order(); // ❌ 私有模块
}
```

### 3. 可见性 `pub`

```rust
mod outer {
    pub mod inner {
        pub fn public_fn() {}

        // crate 内可见(同 crate 任何模块)
        pub(crate) fn crate_fn() {}

        // 父模块可见
        pub(super) fn super_fn() {}

        // 当前模块可见(同 inner 内)
        pub(self) fn self_fn() {}

        fn private_fn() {}
    }
}

fn main() {
    outer::inner::public_fn();
    outer::inner::crate_fn();
    // outer::inner::super_fn();   // ❌ 父模块外不可见
}
```

## 二、路径

### 1. 绝对路径 vs 相对路径

```rust
mod a {
    pub fn foo() {}
}

mod b {
    pub fn foo() {}

    pub mod c {
        // 绝对路径
        use crate::a::foo;

        // 相对路径
        use super::foo;

        pub fn call() {
            foo();       // super::foo
            crate::a::foo();
        }
    }
}
```

### 2. `use` 导入

```rust
use std::collections::HashMap;
use std::io::{self, Read, Write};
use std::fmt::{Display, Debug};
use std::collections::*;                    // 通配(谨慎)

// 别名
use std::fmt::Result as FmtResult;
use std::io::Result as IoResult;

// 重导出
pub use crate::inner::Public;               // 外部可直接 use my_crate::Public
```

### 3. as 别名解决同名冲突

```rust
mod lib1 { pub fn process() {} }
mod lib2 { pub fn process() {} }

use crate::lib1::process as p1;
use crate::lib2::process as p2;

fn main() {
    p1();
    p2();
}
```

### 4. 私有模块的可见性测试

```rust
mod database {
    pub fn query(sql: &str) -> String {
        execute_internal(sql)
    }

    fn execute_internal(sql: &str) -> String {
        format!("执行: {}", sql)
    }

    #[cfg(test)]
    mod tests {
        use super::*;

        #[test]
        fn test_internal() {
            assert_eq!(execute_internal("SELECT 1"), "执行: SELECT 1");
        }
    }
}
```

## 三、文件系统映射

### 1. 两种风格

**老风格(mod.rs)**:

```
src/
├── lib.rs
├── network/
│   ├── mod.rs
│   ├── tcp.rs
│   └── udp.rs
└── database.rs
```

**新风格(2018+)**:无 `mod.rs`,文件名即模块名

```
src/
├── lib.rs
├── network.rs           # mod network; 自动找 src/network.rs
├── database/
│   ├── mod.rs (可选,也可省略)
│   ├── connection.rs
│   └── models/
│       ├── mod.rs (可选)
│       └── user.rs
```

```rust
// src/lib.rs
mod network;         // 找 src/network.rs
mod database;        // 找 src/database.rs 或 src/database/mod.rs

// src/network.rs
pub mod tcp;         // 找 src/network/tcp.rs
pub mod udp;         // 找 src/network/udp.rs
```

### 2. lib.rs 模板

```rust
// src/lib.rs

// 公有模块
pub mod api;
pub mod config;
pub mod utils;

// 内部模块
pub(crate) mod internal;

// 私有模块
mod private;

// 重新导出常用项
pub use api::ApiClient;
pub use config::Config;
pub use utils::helpers;
```

### 3. bin + lib 混合

```
my_project/
├── Cargo.toml
├── src/
│   ├── lib.rs           # 库入口
│   ├── main.rs          # 二进制入口
│   └── bin/
│       ├── cli.rs       # 额外二进制
│       └── server.rs
```

二进制可直接 `use my_project::xxx`。

## 四、可见性设计模式

```rust
// 库 crate:分层可见性
pub mod api {              // 公开 API
    pub mod v1;
}

pub(crate) mod internal {  // 内部模块
    mod cache;
    mod validation;
}

mod private {              // 私有模块
    mod legacy;
}
```

## 五、Cargo 详解

### 1. 完整 Cargo.toml

```toml
[package]
name = "my_crate"
version = "0.1.0"
edition = "2021"
rust-version = "1.75"
authors = ["you <you@example.com>"]
description = "..."
license = "MIT OR Apache-2.0"
repository = "https://github.com/x/y"
documentation = "https://docs.rs/my_crate"
readme = "README.md"
keywords = ["cli", "tools"]
categories = ["command-line-utilities"]

[lib]
name = "my_lib"
path = "src/lib.rs"

[[bin]]
name = "my_app"
path = "src/main.rs"

[dependencies]
serde = { version = "1.0", features = ["derive"] }
tokio = { version = "1", features = ["full"] }

# 平台特定依赖
[target.'cfg(unix)'.dependencies]
libc = "0.2"

[dev-dependencies]
criterion = "0.5"
proptest = "1"

[build-dependencies]
cc = "1"

[features]
default = ["json"]
json = ["serde_json"]
yaml = ["serde_yaml"]
full = ["json", "yaml"]

[profile.release]
opt-level = 3
lto = "thin"
codegen-units = 1
strip = "symbols"
```

### 2. 依赖版本语法

```toml
# 精确版本
serde = "1.0.195"

# 兼容版本(caret,默认):>=1.0.195, <2.0.0
serde = "^1.0.195"

# 范围
serde = ">=1.0, <2.0"

# Git
serde = { git = "https://github.com/serde-rs/serde", branch = "main" }

# 本地路径
my_lib = { path = "../my_lib" }

# 可选依赖
serde = { version = "1", optional = true }
```

### 3. Features

```toml
[features]
default = ["json"]
json = ["dep:serde_json"]
full = ["json", "yaml"]
```

```rust
#[cfg(feature = "json")]
mod json_support;

#[cfg(feature = "json")]
pub use json_support::*;
```

使用方选择 feature:

```toml
my_crate = { version = "0.1", features = ["full"] }
```

### 4. 工作空间 (workspace)

```toml
# Cargo.toml (workspace 根)
[workspace]
members = ["crates/*"]
resolver = "2"

[workspace.package]
version = "0.1.0"
edition = "2021"
license = "MIT"

[workspace.dependencies]
serde = { version = "1", features = ["derive"] }
tokio = { version = "1", features = ["full"] }
anyhow = "1"
```

子 crate 复用:

```toml
# crates/core/Cargo.toml
[dependencies]
serde = { workspace = true }
tokio = { workspace = true }
```

### 5. 构建脚本 (build.rs)

```rust
// build.rs
fn main() {
    println!("cargo:rerun-if-changed=build.rs");
    println!("cargo:rustc-link-lib=foo");
    println!("cargo:rustc-env=VERSION=1.0");
}
```

```toml
[package]
build = "build.rs"
```

## 六、文档注释

```rust
/// 计算阶乘
///
/// # Examples
/// ```
/// let n = factorial(5);
/// assert_eq!(n, 120);
/// ```
///
/// # Panics
/// 当 n 为负数时 panic
pub fn factorial(n: u64) -> u64 {
    if n == 0 { 1 } else { n * factorial(n - 1) }
}

//! 模块级文档:在 lib.rs / main.rs 顶部
//! 
//! # 模块说明
//! 提供核心功能
```

```bash
cargo doc --open        # 生成并打开
cargo doc --no-deps     # 仅本 crate
```

## 七、发布到 crates.io

```bash
# 1. 登录
cargo login <token>

# 2. 预检
cargo publish --dry-run

# 3. 发布
cargo publish

# 4. 撤回(yank)
cargo yank --version 0.1.0
cargo yank --version 0.1.0 --undo
```

## 八、要点速记

- **`mod` 声明模块,`use` 导入项,`pub` 控制可见性**
- **`pub(crate)` crate 内可见,`pub(super)` 父模块可见**
- **`use crate::xxx` 绝对路径,`use super::xxx` 相对路径**
- **`pub use` 重导出,简化外部接口**
- **2018+ Edition 鼓励无 mod.rs 风格**
- **二进制 `src/main.rs` + 库 `src/lib.rs` 可共存**
- **`cargo new` / `cargo build` / `cargo run` / `cargo test`**
- **`Cargo.lock` 二进制项目也要提交,锁定依赖版本**
- **依赖版本默认 caret:`^1.2.3` = `>=1.2.3, <2.0.0`**
- **`cargo doc --open` 生成文档,文档注释支持 Markdown**
- **`cargo publish` 上传到 crates.io,`yank` 撤回**

---

## 九、综合实战:多 crate workspace 项目

完整的多 crate workspace,展示模块可见性、依赖、特性门控的实际应用。

### 1. 项目结构

```text
acme_cli/                          # workspace 根
├── Cargo.toml                     # [workspace]
├── Cargo.lock
├── README.md
├── crates/
│   ├── acme_core/                 # 核心库
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── lib.rs
│   │       ├── config.rs
│   │       ├── error.rs
│   │       └── version.rs
│   ├── acme_cli/                  # CLI 二进制
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── main.rs
│   │       ├── args.rs
│   │       └── commands/
│   │           ├── mod.rs
│   │           ├── init.rs
│   │           └── build.rs
│   └── acme_server/               # 可选:HTTP 服务器
│       ├── Cargo.toml
│       └── src/
│           ├── lib.rs
│           ├── router.rs
│           └── handlers.rs
└── tests/
    └── cli_smoke.rs
```

### 2. workspace 根 `Cargo.toml`

```toml
[workspace]
members = ["crates/*"]
resolver = "2"

[workspace.package]
version = "0.1.0"
edition = "2021"
license = "MIT OR Apache-2.0"
authors = ["ACME Team"]
repository = "https://github.com/acme/cli"

[workspace.dependencies]
serde = { version = "1", features = ["derive"] }
serde_json = "1"
thiserror = "1"
anyhow = "1"
clap = { version = "4", features = ["derive"] }
tracing = "0.1"
tokio = { version = "1", features = ["full"] }

[profile.release]
opt-level = 3
lto = "thin"
codegen-units = 1
strip = "symbols"
```

### 3. `crates/acme_core/Cargo.toml`

```toml
[package]
name = "acme_core"
version.workspace = true
edition.workspace = true
license.workspace = true

[dependencies]
serde = { workspace = true }
thiserror = { workspace = true }
```

### 4. `crates/acme_core/src/lib.rs`

```rust
//! 核心库:配置、错误、版本
//!
//! 提供给 CLI 和 Server 共用的基础组件。

pub mod config;
pub mod error;
pub mod version;

// 重导出常用项
pub use config::{Config, ServerConfig};
pub use error::{Error, Result};
pub use version::VERSION;

/// 项目信息
pub fn project_info() -> String {
    format!("acme_cli v{}", VERSION)
}
```

### 5. `crates/acme_core/src/version.rs`

```rust
/// 当前版本,从 workspace.package 继承
pub const VERSION: &str = env!("CARGO_PKG_VERSION");
```

### 6. `crates/acme_core/src/error.rs`

```rust
use thiserror::Error;

#[derive(Error, Debug)]
pub enum Error {
    #[error("配置错误: {0}")]
    Config(String),

    #[error("IO 错误: {0}")]
    Io(#[from] std::io::Error),

    #[error("序列化错误: {0}")]
    Serde(#[from] serde_json::Error),

    #[error("命令执行失败: {0}")]
    Command(String),
}

pub type Result<T> = std::result::Result<T, Error>;
```

### 7. `crates/acme_core/src/config.rs`

```rust
use serde::{Deserialize, Serialize};

use crate::error::{Error, Result};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Config {
    pub project_name: String,
    pub version: String,
    #[serde(default)]
    pub server: ServerConfig,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ServerConfig {
    #[serde(default = "default_host")]
    pub host: String,
    #[serde(default = "default_port")]
    pub port: u16,
}

fn default_host() -> String { "127.0.0.1".into() }
fn default_port() -> u16 { 8080 }

impl Default for ServerConfig {
    fn default() -> Self {
        Self {
            host: default_host(),
            port: default_port(),
        }
    }
}

impl Default for Config {
    fn default() -> Self {
        Self {
            project_name: String::from("my-app"),
            version: String::from("0.1.0"),
            server: ServerConfig::default(),
        }
    }
}

impl Config {
    pub fn from_file(path: &str) -> Result<Self> {
        let content = std::fs::read_to_string(path)?;
        let cfg: Self = serde_json::from_str(&content)?;
        Ok(cfg)
    }

    pub fn save(&self, path: &str) -> Result<()> {
        let s = serde_json::to_string_pretty(self)?;
        std::fs::write(path, s)?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default() {
        let cfg = Config::default();
        assert_eq!(cfg.server.port, 8080);
    }
}
```

### 8. `crates/acme_cli/Cargo.toml`

```toml
[package]
name = "acme_cli"
version.workspace = true
edition.workspace = true
license.workspace = true

[[bin]]
name = "acme"
path = "src/main.rs"

[dependencies]
acme_core = { path = "../acme_core" }
anyhow = { workspace = true }
clap = { workspace = true }
tokio = { workspace = true }
tracing = { workspace = true }

[features]
default = []
server = ["dep:acme_server"]
```

### 9. `crates/acme_cli/src/main.rs`

```rust
mod args;
mod commands;

use anyhow::{Context, Result};
use tracing_subscriber::EnvFilter;

fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info")))
        .init();

    let cli = args::Cli::parse();
    cli.run().context("命令执行失败")
}
```

### 10. `crates/acme_cli/src/args.rs`

```rust
use clap::{Parser, Subcommand};

use acme_core::project_info;

#[derive(Parser, Debug)]
#[command(name = "acme", version, about = project_info())]
pub struct Cli {
    #[command(subcommand)]
    pub command: Command,
}

#[derive(Subcommand, Debug)]
pub enum Command {
    /// 初始化新项目
    Init {
        /// 项目名称
        name: String,
    },
    /// 构建项目
    Build {
        #[arg(short, long)]
        release: bool,
    },
    /// 启动服务(需 feature "server")
    Serve {
        #[arg(short, long, default_value = "8080")]
        port: u16,
    },
}

impl Cli {
    pub fn run(self) -> anyhow::Result<()> {
        match self.command {
            Command::Init { name } => commands::init::run(&name),
            Command::Build { release } => commands::build::run(release),
            Command::Serve { port } => commands::serve::run(port),
        }
    }
}
```

### 11. `crates/acme_cli/src/commands/mod.rs`

```rust
pub mod build;
pub mod init;
pub mod serve;
```

### 12. `crates/acme_cli/src/commands/init.rs`

```rust
use anyhow::{Context, Result};

use acme_core::Config;

pub fn run(name: &str) -> Result<()> {
    let cfg = Config {
        project_name: name.to_string(),
        ..Default::default()
    };

    let path = format!("{}/acme.json", name);
    std::fs::create_dir_all(name).context("创建目录失败")?;
    cfg.save(&path).context("保存配置失败")?;

    println!("✅ 初始化项目 '{}' 完成", name);
    println!("� 配置保存到 {}", path);
    Ok(())
}
```

### 13. `crates/acme_cli/src/commands/build.rs`

```rust
use anyhow::Result;

pub fn run(release: bool) -> Result<()> {
    let mode = if release { "release" } else { "debug" };
    println!("🔨 构建 ({})...", mode);
    // 实际:调用 cargo build
    println!("✅ 构建完成");
    Ok(())
}
```

### 14. `crates/acme_cli/src/commands/serve.rs`

```rust
use anyhow::Result;

#[cfg(feature = "server")]
pub fn run(port: u16) -> Result<()> {
    println!("🚀 启动服务在 :{}", port);
    acme_server::run(port).map_err(Into::into)
}

#[cfg(not(feature = "server"))]
pub fn run(_port: u16) -> Result<()> {
    anyhow::bail!("需要启用 'server' feature:cargo run --features server -- serve")
}
```

### 15. `crates/acme_server/Cargo.toml`

```toml
[package]
name = "acme_server"
version.workspace = true
edition.workspace = true

[dependencies]
acme_core = { path = "../acme_core" }
tokio = { workspace = true }
anyhow = { workspace = true }
```

### 16. `crates/acme_server/src/lib.rs`

```rust
pub mod router;
pub mod handlers;

use anyhow::Result;

pub async fn run(port: u16) -> Result<()> {
    let app = router::build();
    let listener = tokio::net::TcpListener::bind(("127.0.0.1", port)).await?;
    println!("监听 127.0.0.1:{}", port);
    axum::serve(listener, app).await?;
    Ok(())
}
```

### 17. `crates/acme_server/src/router.rs`(示意)

```rust
pub fn build() -> axum::Router {
    axum::Router::new()
        .route("/", axum::routing::get(handlers::index))
        .route("/health", axum::routing::get(handlers::health))
}
```

### 18. `crates/acme_server/src/handlers.rs`

```rust
use axum::Json;
use serde_json::{json, Value};

pub async fn index() -> &'static str {
    "Hello from acme_server"
}

pub async fn health() -> Json<Value> {
    Json(json!({ "status": "ok" }))
}
```

### 19. 集成测试 `tests/cli_smoke.rs`

```rust
use assert_cmd::Command;

#[test]
fn test_help() {
    Command::cargo_bin("acme")
        .unwrap()
        .arg("--help")
        .assert()
        .success();
}

#[test]
fn test_init() {
    let temp = tempfile::tempdir().unwrap();
    Command::cargo_bin("acme")
        .unwrap()
        .arg("init")
        .arg("test-project")
        .current_dir(temp.path())
        .assert()
        .success();

    assert!(temp.path().join("test-project/acme.json").exists());
}
```

### 20. workspace 命令

```bash
# 编译所有
cargo build --workspace

# 测试所有
cargo test --workspace

# 仅 CLI
cargo run -p acme_cli -- init my-app

# 启用 server feature
cargo run -p acme_cli --features server -- serve --port 8080

# 发布全部
cargo publish --workspace

# 清理
cargo clean
```

### 21. 关键点

| 概念 | 用法 |
| --- | --- |
| `workspace.members` | 通配 `crates/*` |
| `workspace.package` | 共享元数据 |
| `workspace.dependencies` | 共享依赖声明,子 crate 用 `workspace = true` |
| `version.workspace = true` | 子 crate 继承版本 |
| `path = "../acme_core"` | workspace 内路径依赖 |
| `features` | 可选依赖门控(如 server) |
| `#[cfg(feature = "...")]` | 条件编译 |
| 重导出 | `pub use config::Config` 简化外部接口 |
| clap derive | 类型安全的 CLI 参数解析 |
| `tracing_subscriber` | 结构化日志 |
