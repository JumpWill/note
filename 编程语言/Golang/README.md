# Go 编程笔记 (整理版)

按"由浅入深、概念聚合"原则组织,每章独立完整,带多文件项目示例。

## 目录

### 基础篇

| 章节 | 文件 | 内容 |
| --- | --- | --- |
| 01 | [01-快速开始.md](01-快速开始.md) | 安装、go run、第一个程序 |
| 02 | [02-基础语法.md](02-基础语法.md) | 变量、常量、数据类型、字符串 |
| 03 | [03-控制流.md](03-控制流.md) | if / for / switch / goto |
| 04 | [04-数组与切片.md](04-数组与切片.md) | 数组、切片、append、copy |

### 数据结构篇

| 章节 | 文件 | 内容 |
| --- | --- | --- |
| 05 | [05-map.md](05-map.md) | map 创建、迭代、并发安全 |
| 06 | [06-函数与闭包.md](06-函数与闭包.md) | 函数、匿名函数、闭包、defer、错误处理 |
| 07 | [07-指针与内存.md](07-指针与内存.md) | 指针、make / new、内存模型 |

### 面向对象篇

| 章节 | 文件 | 内容 |
| --- | --- | --- |
| 08 | [08-结构体与方法.md](08-结构体与方法.md) | struct、匿名字段、方法、JSON |
| 09 | [09-接口.md](09-接口.md) | interface、类型断言、空接口 |

### 并发篇

| 章节 | 文件 | 内容 |
| --- | --- | --- |
| 10 | [10-并发基础.md](10-并发基础.md) | goroutine、channel、select |
| 11 | [11-并发进阶.md](11-并发进阶.md) | Mutex、RWLock、sync.Once、调度模型 |

### 工程篇

| 章节 | 文件 | 内容 |
| --- | --- | --- |
| 12 | [12-包管理与模块.md](12-包管理与模块.md) | go.mod、go mod、workspace |
| 13 | [13-测试.md](13-测试.md) | 单元测试、子测试、基准测试 |

### 面试篇

| 章节 | 文件 | 内容 |
| --- | --- | --- |
| 14 | [14-面试题.md](14-面试题.md) | 11 类高频面试题 + 代码答案 + 速查清单 |

## 多文件项目实战索引

| 文件 | 项目 | 关键概念 |
| --- | --- | --- |
| 02 | `go_basic_demo` | 包结构、变量作用域 |
| 06 | `func_demo` | 多返回值、闭包、defer、错误处理 |
| 08 | `oop_demo` | 结构体嵌套、方法、JSON 序列化 |
| 09 | `interface_demo` | 接口组合、类型断言 |
| 10 | `concurrency_demo` | goroutine 池、channel 通信、worker pool |
| 11 | `sync_demo` | 共享状态、限流器、Once |
| 13 | `test_demo` | 表驱动测试、benchmark、覆盖率 |

## 学习路径

```text
入门:  01 → 02 → 03 → 04
基础:  05 → 06 → 07
面向对象:  08 → 09
并发:  10 → 11
工程:  12 → 13
```

## 与原版目录对应

| 原文件 | 整合到 |
| --- | --- |
| `Golang笔记.md` | 拆分为 01 - 13 |
| `面试题.md` | 保留原文件 |

## 速查表

| 概念 | 一句话 |
| --- | --- |
| goroutine | 轻量级协程,`go func()` 启动 |
| channel | CSP 并发模型通信管道,默认无缓冲 |
| defer | 函数返回前执行,用于资源清理 |
| interface | 方法集,鸭子类型 |
| goroutine 调度 | G-M-P 三级调度模型 |
| GC | 三色标记 + 并发清扫 |
| error | 普通值,需显式返回/处理 |
| panic / recover | panic 配合 recover 实现异常处理 |
| go.mod | Go 1.11+ 的依赖管理 |
| select | 多 channel 等待 |
| context | 跨 goroutine 取消信号传递 |

## 常用工具命令速查

```bash
go run main.go          # 编译并运行
go build                # 编译
go test                 # 运行测试
go test -bench=.        # 基准测试
go test -race           # 竞态检测
go vet                  # 静态检查
gofmt -w .              # 格式化
go mod init             # 初始化模块
go mod tidy             # 整理依赖
go get pkg              # 下载依赖
go install              # 安装二进制
go doc fmt.Println      # 查看文档
```
