# Rust 编程笔记 (整理版)

按"由浅入深、概念聚合"原则重新组织,每个文件聚焦一个主题,例子密集且包含多文件项目示例。

## 目录

### 基础篇

| 章节 | 文件 | 内容 |
| --- | --- | --- |
| 01 | [01-快速开始.md](01-快速开始.md) | 安装、Cargo、Hello World、猜数游戏 |
| 02 | [02-基础语法.md](02-基础语法.md) | 变量、数据类型、函数、控制流、注释、表达式 |
| 03 | [03-所有权与借用.md](03-所有权与借用.md) | 所有权规则、借用、切片、生命周期 + **CSV 解析器实战** |
| 04 | [04-结构体与枚举.md](04-结构体与枚举.md) | struct / enum / 模式匹配 / 方法 |
| 05 | [05-集合与字符串.md](05-集合与字符串.md) | Vec / String / HashMap / HashSet |

### 进阶篇

| 章节 | 文件 | 内容 |
| --- | --- | --- |
| 06 | [06-错误处理.md](06-错误处理.md) | panic / Result / ? / 自定义错误 + **config_tool 多文件实战** |
| 07 | [07-泛型与Trait.md](07-泛型与Trait.md) | 泛型 / Trait / Trait Bound / 分发 + **plugin_system 多文件实战** |
| 08 | [08-模块与Cargo.md](08-模块与Cargo.md) | mod / use / pub / crate / Cargo.toml / 依赖管理 |
| 09 | [09-智能指针.md](09-智能指针.md) | Box / Rc / Arc / RefCell / Cell / Weak + **graph_lib 多文件实战** |

### 实战篇

| 章节 | 文件 | 内容 |
| --- | --- | --- |
| 10 | [10-闭包与迭代器.md](10-闭包与迭代器.md) | 闭包 / Fn 系列 / Iterator / 适配器 |
| 11 | [11-并发编程.md](11-并发编程.md) | 线程 / channel / Mutex / Send / Sync / async + **web_crawler 多文件实战** |
| 12 | [12-文件与IO.md](12-文件与IO.md) | 文件读写 / 目录 / 元数据 / 临时文件 / 异步 IO |
| 13 | [13-测试.md](13-测试.md) | 单元测试 / 集成测试 / 文档测试 / 覆盖率 |
| 14 | [14-高级特性.md](14-高级特性.md) | unsafe / FFI / 宏 / 属性 / 过程宏入门 |

### 专题篇(深入)

| 章节 | 文件 | 内容 |
| --- | --- | --- |
| 15 | [15-宏与元编程.md](15-宏与元编程.md) | macro_rules / 派生宏 / 属性宏 / 函数式宏 / 项目结构 |
| 16 | [16-Unsafe进阶与FFI.md](16-Unsafe进阶与FFI.md) | 裸指针 / repr / alloc / MaybeUninit / bindgen + rust_c_demo 实战 |
| 17 | [17-Async运行时深入.md](17-Async运行时深入.md) | Future / Pin / Waker / 自定义 executor + tokio_app 实战 |

## 多文件项目实战索引

| 文件 | 项目 | 关键概念 |
| --- | --- | --- |
| 02 | `calc_cli` | 模块拆分、模式匹配、字符串解析 |
| 03 | `csv_parse` | 借用切片、零拷贝迭代器、生命周期参数 |
| 04 | `expr_eval` | 递归枚举、Box<dyn>、Peekable 迭代器 |
| 05 | `log_analyzer` | HashMap/BTreeMap/HashSet 组合、统计聚合 |
| 06 | `config_tool` | thiserror + anyhow 分层、`?` + From 传播 |
| 07 | `plugin_system` | dyn Trait、注册表、Any downcast、扩展 trait |
| 08 | `acme_cli` workspace | 多 crate、workspace.* 共享、可选 feature |
| 09 | `graph_lib` | Rc + RefCell + Weak 协作避免循环 |
| 10 | `csv_pipeline` | 自定义 Iterator、Window 适配器、闭包捕获 |
| 11 | `web_crawler` | 工作池、Trait Object、优雅关闭 |
| 12 | `backup_tool` | walkdir 递归、gzip 压缩、manifest 持久化 |
| 13 | `task_queue` | 完整测试体系(单元/集成/并发/属性/基准) |
| 14 | `log_macro_lib` | 派生宏 + 属性宏 + 函数式宏 组合 |
| 15 | `hello_macro` + `hello_macro_derive` | workspace、proc-macro crate、syn/quote |
| 16 | `rust_c_demo` + `bindgen` 集成 | build.rs、`#[repr(C)]`、`CString` |
| 17 | `tokio_app` | 模块化 handler/service、Arc<Mutex>、tokio |

## 速查表

| 概念 | 一句话 |
| --- | --- |
| 所有权 | 每个值有唯一所有者,所有者离开作用域,值被自动释放 |
| 借用 | `&T` / `&mut T`,引用不获取所有权 |
| 生命周期 | 引用必须不活得比它的所有者久 |
| Trait | 定义共享行为,类似接口但支持默认实现 |
| 智能指针 | 拥有元数据 + 额外能力的指针 (Box/Rc/Arc/RefCell) |
| Send | 类型的所有权可在线程间转移 |
| Sync | 类型可被多线程同时引用访问 |
| `?` | 错误传播,Err 自动 return |
| `impl Trait` | 静态分发,零成本 |
| `dyn Trait` | 动态分发,运行时多态 |
| `Pin<&mut T>` | 防止 move,自引用结构必需 |
| `PhantomData<T>` | 携带类型信息,零运行时开销 |

## 学习路径

```text
入门:  01 → 02 → 03 → 04
基础:  05 → 06 → 07 → 08
进阶:  09 → 10 → 11
实战:  12 → 13 → 14
专题:  15 → 16 → 17(任选)
```

## 项目组织通用模式

### 单文件

```text
project/
├── Cargo.toml
└── src/
    └── main.rs
```

### 库 + 二进制

```text
project/
├── Cargo.toml
├── src/
│   ├── lib.rs
│   └── main.rs
└── tests/
```

### 多模块

```text
project/
├── Cargo.toml
├── src/
│   ├── lib.rs
│   ├── module_a.rs
│   └── module_b/
│       ├── mod.rs
│       └── sub.rs
└── examples/
```

### Workspace + 过程宏

```text
workspace/
├── Cargo.toml                 # [workspace]
├── crate_a/                   # 用户 crate
│   ├── Cargo.toml
│   └── src/lib.rs
└── crate_a_derive/            # proc-macro crate
    ├── Cargo.toml
    └── src/lib.rs             # proc-macro = true
```

### FFI 项目

```text
ffi_project/
├── Cargo.toml
├── build.rs                   # cc::Build
├── wrapper.h
├── wrapper.c
├── src/
│   └── lib.rs                 # extern "C" + 安全包装
└── test/
```

## 与原版目录对应

| 原文件 | 整合到 |
| --- | --- |
| `基础学习.md` | 拆分为 01 / 02 / 03 / 04 / 05 / 06 / 07 / 09 / 10 / 11 / 13 |
| `包管理.md`(空) | 合并到 01 + 08 |
| `模块.md` | 整合到 08 |
| `引用与解引用.md` | 整合到 03 |
| `智能指针.md`(空) | 写入 09 |
| `闭包.md` | 整合到 10 |
| `迭代器.md` | 整合到 10 |
| `错误处理.md` | 整合到 06 |
| `多线程.md` | 整合到 11 |
| `文件操作.md` | 整合到 12 |
| 新增 15/16/17 | 专题深入 |
