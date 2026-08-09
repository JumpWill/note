# 16 - Unsafe 进阶与 FFI

`unsafe` 不是关闭借用检查,而是关闭编译器**无法证明的安全检查**。本章深入 unsafe 模式、内存布局、FFI 实践。

## 一、`unsafe` 五大能力回顾

1. 解引用裸指针 `*const T` / `*mut T`
2. 调用 `unsafe fn` / `unsafe trait` 的方法
3. 访问 / 修改 `static mut`
4. 实现 `unsafe trait`
5. 访问 `union` 字段

## 二、裸指针 (Raw Pointers)

### 1. 创建与解引用

```rust
fn main() {
    let mut n = 5;

    // 从引用转换(隐式)
    let p1 = &n as *const i32;
    let p2 = &mut n as *mut i32;

    // 从整数地址
    let addr = 0x12345usize;
    let p3 = addr as *const i32;

    // 空指针
    let null: *const i32 = std::ptr::null();
    let null_mut: *mut i32 = std::ptr::null_mut();

    // 解引用必须 unsafe
    unsafe {
        println!("*p1 = {}", *p1);    // 5
        *p2 = 10;                     // 写
        if !null.is_null() {
            println!("{}", *null);    // 跳过
        }
    }
}
```

### 2. 指针算术

```rust
fn main() {
    let arr = [1, 2, 3, 4, 5];
    let p = arr.as_ptr();

    unsafe {
        let second = p.add(1);
        println!("second: {}", *second);  // 2

        // 偏移(带溢出检查)
        let diff = second.offset_from(p);
        println!("diff: {}", diff);  // 1

        // 边界外安全访问
        let out = p.add(10);
        if !out.is_null() {
            // 仍可能越界,需先检查
        }
    }
}
```

### 3. 指针操作 API

| 函数 | 作用 |
| --- | --- |
| `add(n)` / `sub(n)` | 移动 n 个元素(不检查边界) |
| `offset(n)` | 同上,边界溢出 panic |
| `wrapping_add(n)` | 同 add,usize 溢出回绕 |
| `read()` / `write(v)` | 读 / 写,不 drop 旧值 |
| `read_unaligned()` / `write_unaligned()` | 未对齐读写 |
| `copy_nonoverlapping(src, dst, count)` | 复制(不重叠) |
| `copy(src, dst, count)` | 复制(可重叠) |
| `drop_in_place(ptr)` | 原地 drop |
| `replace(ptr, new)` | 替换 |
| `swap(p1, p2)` | 交换 |
| `cast<U>()` | 类型转换 |

## 三、`unsafe` 安全封装模式

### 1. 从裸指针构建安全抽象

```rust
use std::ptr;

pub struct Buffer<T> {
    ptr: *mut T,
    len: usize,
    cap: usize,
}

impl<T> Buffer<T> {
    pub fn new() -> Self {
        Self { ptr: ptr::null_mut(), len: 0, cap: 0 }
    }

    pub fn push(&mut self, val: T) {
        if self.len == self.cap {
            self.grow();
        }
        unsafe {
            ptr::write(self.ptr.add(self.len), val);
        }
        self.len += 1;
    }

    pub fn pop(&mut self) -> Option<T> {
        if self.len == 0 { return None; }
        self.len -= 1;
        unsafe {
            Some(ptr::read(self.ptr.add(self.len)))
        }
    }

    pub fn get(&self, idx: usize) -> Option<&T> {
        if idx < self.len {
            unsafe { Some(&*self.ptr.add(idx)) }
        } else {
            None
        }
    }

    fn grow(&mut self) {
        let new_cap = if self.cap == 0 { 4 } else { self.cap * 2 };
        let new_ptr = unsafe {
            let layout = std::alloc::Layout::array::<T>(new_cap);
            let ptr = std::alloc::alloc(layout) as *mut T;

            if !self.ptr.is_null() {
                std::ptr::copy_nonoverlapping(self.ptr, ptr, self.len);
                let old_layout = std::alloc::Layout::array::<T>(self.cap);
                std::alloc::dealloc(self.ptr as *mut u8, old_layout);
            }
            ptr
        };

        self.ptr = new_ptr;
        self.cap = new_cap;
    }
}

impl<T> Drop for Buffer<T> {
    fn drop(&mut self) {
        unsafe {
            // 逐元素 drop
            for i in 0..self.len {
                ptr::drop_in_place(self.ptr.add(i));
            }
            if !self.ptr.is_null() {
                let layout = std::alloc::Layout::array::<T>(self.cap);
                std::alloc::dealloc(self.ptr as *mut u8, layout);
            }
        }
    }
}
```

## 四、内存布局

### 1. repr 属性

```rust
// 默认:Rust 优化布局
struct Default {
    a: u8,    // 1 字节
    b: u32,   // 4 字节
    c: u16,   // 2 字节
}

// #[repr(C)]:C 兼容布局,字段顺序固定
#[repr(C)]
struct CStruct {
    a: u8,    // offset 0
    b: u32,   // offset 4(对齐到 4)
    c: u16,   // offset 8
}
// 总大小:12(对齐到 4)

// #[repr(packed)]:无填充,可能未对齐
#[repr(packed)]
struct Packed {
    a: u8,
    b: u32,   // 可能未对齐,访问变慢
}

// #[repr(transparent)]:与内部字段布局完全一致
#[repr(transparent)]
struct UserId(u64);     // 布局 == u64

// 枚举的 repr
#[repr(u8)]
enum Small {
    A = 1,
    B = 2,
    C = 3,
}
// 大小 == u8
```

### 2. 大小、对齐、偏移

```rust
use std::mem;

#[repr(C)]
struct S {
    a: u8,
    b: u32,
    c: u16,
}

fn main() {
    println!("size: {}", mem::size_of::<S>());         // 12
    println!("align: {}", mem::align_of::<S>());       // 4

    println!("a offset: {}", mem::offset_of!(S, a));   // 0
    println!("b offset: {}", mem::offset_of!(S, b));   // 4
    println!("c offset: {}", mem::offset_of!(S, c));   // 8
}
```

## 五、动态内存分配

### 1. 直接调用 allocator

```rust
use std::alloc::{alloc, dealloc, Layout};

fn main() {
    unsafe {
        let layout = Layout::new::<u64>();
        let ptr = alloc(layout) as *mut u64;

        *ptr = 42;
        println!("value: {}", *ptr);

        dealloc(ptr as *mut u8, layout);
    }
}
```

### 2. 数组分配

```rust
use std::alloc::{alloc, dealloc, Layout};

fn alloc_array<T>(n: usize) -> *mut T {
    unsafe {
        let layout = Layout::array::<T>(n).expect("layout error");
        let ptr = alloc(layout) as *mut T;
        if ptr.is_null() {
            std::alloc::handle_alloc_error(layout);
        }
        ptr
    }
}

fn dealloc_array<T>(ptr: *mut T, n: usize) {
    unsafe {
        let layout = Layout::array::<T>(n).expect("layout error");
        dealloc(ptr as *mut u8, layout);
    }
}

fn main() {
    unsafe {
        let p = alloc_array::<u32>(10);
        for i in 0..10 {
            *p.add(i) = (i * i) as u32;
        }
        println!("{} {}", *p.add(3), *p.add(7));
        dealloc_array(p, 10);
    }
}
```

## 六、未对齐访问

```rust
use std::ptr;

fn main() {
    let mut buf = [0u8; 16];

    unsafe {
        // 写入未对齐的 u32
        let p = buf.as_mut_ptr().add(1) as *mut u32;
        ptr::write_unaligned(p, 0xDEAD_BEEF);

        // 读出
        let v = ptr::read_unaligned(p);
        println!("{:x}", v);
    }
}
```

## 七、`MaybeUninit`

### 1. 未初始化内存

```rust
use std::mem::MaybeUninit;

fn main() {
    // 创建未初始化数组
    let mut arr: [MaybeUninit<i32>; 10] = unsafe {
        MaybeUninit::uninit().assume_init()
    };

    // 初始化
    for i in 0..10 {
        arr[i] = MaybeUninit::new(i as i32 * 2);
    }

    // 转成 [i32; 10]
    let arr: [i32; 10] = unsafe {
        // transmute 安全版本:逐元素读
        std::array::from_fn(|i| arr[i].assume_init())
    };

    println!("{:?}", arr);
}
```

### 2. 延迟初始化

```rust
use std::mem::MaybeUninit;

struct Lazy<T> {
    data: MaybeUninit<T>,
    init: bool,
}

impl<T> Lazy<T> {
    fn new() -> Self {
        Self { data: MaybeUninit::uninit(), init: false }
    }

    fn get_or_init<F: FnOnce() -> T>(&mut self, f: F) -> &T {
        if !self.init {
            unsafe {
                self.data = MaybeUninit::new(f());
                self.init = true;
            }
        }
        unsafe { self.data.assume_init_ref() }
    }
}

impl<T> Drop for Lazy<T> {
    fn drop(&mut self) {
        if self.init {
            unsafe { self.data.assume_init_drop(); }
        }
    }
}

fn main() {
    let mut x = Lazy::<String>::new();
    println!("init: {}", x.get_or_init(|| String::from("hello")));
}
```

## 八、FFI - 与 C 互操作

### 1. 项目结构

```
rust_c_demo/
├── Cargo.toml
├── build.rs                 # 构建脚本:链接 C 库
├── wrapper.h                # C 头文件
├── src/
│   ├── lib.rs               # Rust 库入口
│   └── c_helpers.rs         # C 函数的安全包装
└── test/
    └── test_ffi.rs
```

### 2. `wrapper.h`

```c
// wrapper.h
#ifndef WRAPPER_H
#define WRAPPER_H

#include <stdint.h>

typedef struct {
    int32_t x;
    int32_t y;
} Point;

Point add_points(Point a, Point b);
int64_t sum_array(const int32_t* arr, size_t len);
const char* get_message(void);

#endif
```

### 3. `build.rs`

```rust
// build.rs
fn main() {
    cc::Build::new()
        .file("wrapper.c")
        .compile("wrapper");
}
```

`Cargo.toml`:

```toml
[package]
name = "rust_c_demo"
version = "0.1.0"
edition = "2021"

[lib]
name = "rust_c_demo"

[dependencies]

[build-dependencies]
cc = "1"
```

### 4. Rust 端声明 C 函数

```rust
// src/lib.rs
mod c_helpers;

pub use c_helpers::*;
```

```rust
// src/c_helpers.rs
use std::ffi::{CStr, CString};
use std::os::raw::{c_char, c_int, c_int32_t, c_longlong, c_void};

#[repr(C)]
#[derive(Debug, Copy, Clone)]
pub struct Point {
    pub x: c_int32_t,
    pub y: c_int32_t,
}

// 声明 C 函数
extern "C" {
    fn add_points(a: Point, b: Point) -> Point;
    fn sum_array(arr: *const c_int32_t, len: usize) -> c_longlong;
    fn get_message() -> *const c_char;
}

// 安全包装
pub fn add_points_safe(a: Point, b: Point) -> Point {
    unsafe { add_points(a, b) }
}

pub fn sum_array_safe(arr: &[i32]) -> i64 {
    unsafe { sum_array(arr.as_ptr(), arr.len()) as i64 }
}

pub fn get_message_safe() -> Option<String> {
    unsafe {
        let ptr = get_message();
        if ptr.is_null() {
            return None;
        }
        CStr::from_ptr(ptr).to_str().ok().map(|s| s.to_string())
    }
}

pub fn greet(name: &str) -> String {
    let c_name = CString::new(name).expect("invalid name");
    unsafe {
        // 假设 C 端有 greet(const char* name)
        let ptr = greet(c_name.as_ptr());
        if ptr.is_null() {
            return String::from("error");
        }
        CStr::from_ptr(ptr).to_string_lossy().into_owned()
    }
}

extern "C" {
    fn greet(name: *const c_char) -> *const c_char;
}
```

### 5. C 端实现(`wrapper.c`)

```c
// wrapper.c
#include "wrapper.h"
#include <string.h>

Point add_points(Point a, Point b) {
    return (Point){a.x + b.x, a.y + b.y};
}

int64_t sum_array(const int32_t* arr, size_t len) {
    int64_t total = 0;
    for (size_t i = 0; i < len; i++) total += arr[i];
    return total;
}

static const char* MSG = "Hello from C!";

const char* get_message(void) { return MSG; }

const char* greet(const char* name) {
    static char buf[256];
    snprintf(buf, sizeof(buf), "Hi, %s!", name);
    return buf;
}
```

### 6. 测试

```rust
// test/test_ffi.rs
use rust_c_demo::*;

#[test]
fn test_add_points() {
    let a = Point { x: 1, y: 2 };
    let b = Point { x: 10, y: 20 };
    let s = add_points_safe(a, b);
    assert_eq!(s.x, 11);
    assert_eq!(s.y, 22);
}

#[test]
fn test_sum_array() {
    let arr = vec![1, 2, 3, 4, 5];
    assert_eq!(sum_array_safe(&arr), 15);
}

#[test]
fn test_get_message() {
    let msg = get_message_safe();
    assert_eq!(msg, Some("Hello from C!".to_string()));
}
```

## 九、bindgen 自动生成绑定

### 1. 项目结构

```
with_bindgen/
├── Cargo.toml
├── build.rs
├── src/
│   └── lib.rs
└── bindings/                # bindgen 输出目录
    └── bindings.rs
```

### 2. `build.rs`

```rust
fn main() {
    println!("cargo:rerun-if-changed=wrapper.h");
    println!("cargo:rerun-if-changed=build.rs");

    let bindings = bindgen::Builder::default()
        .header("wrapper.h")
        .parse_callbacks(Box::new(bindgen::CargoCallbacks))
        .generate()
        .expect("Unable to generate bindings");

    let out_path = std::path::PathBuf::from(std::env::var("OUT_DIR").unwrap());
    bindings
        .write_to_file(out_path.join("bindings.rs"))
        .expect("Couldn't write bindings!");
}
```

`Cargo.toml`:

```toml
[build-dependencies]
bindgen = "0.69"
```

### 3. 使用

```rust
include!(concat!(env!("OUT_DIR"), "/bindings.rs"));

pub use bindings::*;
```

## 十、unsafe trait 实现

### 1. Send / Sync 手动实现

```rust
use std::marker::PhantomData;

// 类型本身是线程不安全的,但我们保证安全(因为内部 Mutex 保护)
struct MyType(Mutex<i32>);

unsafe impl Send for MyType {}    // ✅ 内部 Mutex 保证线程安全
unsafe impl Sync for MyType {}    // ✅

// 反例:未保护的内部状态
struct RawPtr(*mut i32);

unsafe impl Send for RawPtr {}    // ❌ 不能跨线程
```

### 2. 标记 trait:!Send / !Sync

```rust
use std::marker::PhantomData;

// PhantomData<*const T> 自动让类型 !Send / !Sync
struct NotThreadSafe<T> {
    _marker: PhantomData<*const T>,
    inner: T,
}
```

## 十一、内存安全审计清单

使用 `unsafe` 时必须验证:

| 检查项 | 描述 |
| --- | --- |
| 指针有效性 | 指向合法对象或 null |
| 对齐 | 读写是否满足类型对齐 |
| 初始化 | 读前是否已初始化 |
| 借用 | 没有同时活跃的可变 / 不可变借用 |
| 所有权 | 移动后未使用,drop 不重复 |
| 类型安全 | transmute 前后类型布局一致 |
| 越界 | 指针算术在合法范围内 |
| 异常安全 | panic 时资源正确释放 |

## 十二、要点速记

- **`unsafe` 不关闭借用检查,只关闭编译器无法证明的检查**
- **裸指针 `*const T` / `*mut T` 解引用需 unsafe**
- **`std::ptr` 提供指针运算、读写、复制 API**
- **`#[repr(C)]` 保证字段顺序固定,可与 C 互操作**
- **`#[repr(transparent)]` 让 newtype 与内部字段布局相同**
- **`MaybeUninit<T>` 表示可能未初始化的内存**
- **`std::alloc` 直接操作堆分配,需手动配对 `dealloc`**
- **FFI 用 `extern "C" { fn ... }` 声明 C 函数**
- **字符串交互用 `CString` / `CStr`**
- **build.rs + cc crate 编译 C 代码,`bindgen` 自动生成绑定**
- **手动 `unsafe impl Send` 时必须保证内部同步原语正确**
- **使用 `unsafe` 前用清单审计所有不变量**
