# type

Bash 内建命令（builtin），用于查看 shell 解析到的命令类型 / 来源 / 位置。比 `which` 范围更广：能识别别名、函数、内建、关键字、外部可执行、哈希缓存等多种形式。

## 作用

- 显示一个命令名最终被解析成什么
- 排查"我的命令怎么变了个样""alias / function / 哪个 PATH 下的二进制生效"
- 辨别 shell 内建 vs 外部可执行
- 配合 hash 命令验证缓存命中

## 常见参数

```text
type [-aftpP] name [name ...]
```

| 参数 | 含义 |
| ---- | ---- |
| `-a` | 列出所有可能的命令，不仅是最先匹配的（按 alias → function → builtin → file 顺序） |
| `-f` | 跳过 shell function（别名、内建、关键字不受影响） |
| `-t` | 仅打印类型单词：`alias` / `function` / `builtin` / `file` / `keyword` / `none` |
| `-p` | 仅返回外部文件路径（PATH 解析），其余类型不打印 |
| `-P` | 强制大写：在某些 shell 中强制 PATH 重新解析（默认已忽略 hash） |

> shell 内建，所以 `-h` / `--help` 不是有效选项。

## 五种返回类型

| 类型 | 含义 |
| ---- | ---- |
| **alias** | 已定义的别名 |
| **function** | shell function |
| **builtin** | shell 内建命令（cd / echo / printf / type ...） |
| **keyword** | 保留字（if / for / while / do ...） |
| **file** | PATH 上可执行的外部文件 |
| **none** | 没有匹配的类型 |

## 使用示例

### 1. 基本使用

```bash
$ type ls
ls is an alias for ls -G'

$ type cd
cd is a shell builtin

$ type type
type is a shell builtin

$ type python
python is /usr/bin/python

$ type if
if is a shell keyword

$ type my_func
my_func is a function
my_func ()
{
    echo "hi"
}
```

### 2. 仅显示类型（脚本里常用）

```bash
$ type -t ls
alias

$ type -t cd
builtin

$ type -t grep
file
```

### 3. 解析为外部路径

```bash
$ type -p grep
/usr/bin/grep

$ type -p cd
                                  # 内建命令没有 -p 输出，返回空
$ type -p ls
                                  # alias 没有 -p 输出
```

### 4. 列出所有可能

```bash
$ type -a python
python is /opt/homebrew/bin/python
python is /usr/bin/python

$ type -a python3
python3 is /usr/bin/python3
python3 is /opt/homebrew/bin/python3
```

适合排查"PATH 顺序导致命令版本不是我想要的"。

### 5. 函数判断

```bash
greet() { echo hi; }
$ type -t greet
function
```

### 6. 不存在的命令

```bash
$ type -t some_cmd_nonexist
none
$ echo $?
1
```

退出码：

| 状态 | 含义 |
| ---- | ---- |
| 0 | 所有 name 都找到 |
| 1 | 至少一个找不到 |

## 与 which / command -v / whence 的区别

| 命令 | 类型 | 返回 |
| ---- | ---- | ---- |
| `type` | Bash builtin | 详细分类 |
| `which` | 外部 / builtin 都有 | PATH 解析结果 |
| `command -v` | builtin | 类似 type，跨 shell 通用 |
| `whence` | ksh / zsh builtin | 类似 type |
| `hash -t` | builtin | 哈希中缓存的文件名 |

```bash
$ which python
/usr/bin/python

$ command -v python
/usr/bin/python

$ command -v ls
alias ls='ls -G'
```

很多脚本里用 `command -v` 代替 `which`：

- `which` 在没有 PATH 目录时返回空，可能误导
- `command -v` 是 builtin，不依赖 PATH 中可执行存在
- `command -V` 给详细说明

## 实际场景

### 1. 看真正的命令是哪个

```bash
$ which git
/usr/bin/git
$ type -a git
git is /opt/homebrew/bin/git
git is /usr/bin/git
$ type -p git
/opt/homebrew/bin/git
```

### 2. 排除别名

```bash
$ alias ls='ls -G'
$ type -p ls
                                  # 空，因为 alias 没有"文件"
$ \ls
$ command ls                       # 不展开别名
```

### 3. 排查 hash 缓存

```bash
$ hash
hits  command
   2  /usr/bin/git
$ type -P git                      # 忽略 hash，重新查询 PATH
/usr/bin/git
```

### 4. 编写可移植脚本

```bash
# 优先 command -v 检测命令是否存在，POSIX 兼容
if command -v foo >/dev/null 2>&1; then
    ...
fi

# Bash 脚本中可用 type
if type -t foo >/dev/null; then
    ...
fi
```

### 5. 函数内调试

```bash
f() {
    echo "running"
    type -t f                     # function
}
```

### 6. 检查关键字

```bash
$ type -t in
keyword
```

`if / in / for / while` 等都是 keyword，而非 alias / builtin / file。

## 返回值与退出码

| 情况 | 退出码 |
| ---- | ------ |
| 至少一个 name 找到 | 0 |
| 所有 name 都找不到 | 1 |
| 有无效选项 | 2 |

`-t` 输出非空时返回 0（实际命令解析成功）；无任何匹配项返回 1。

## 注意事项

- `type` 是 **Bash 内建命令**，没有 man page；用 `help type` 查看 Bash 内置文档
- `type -a` 列出"所有"但优先级仍按 alias → function → builtin → file 排序
- 不同 shell 下顺序可能略不同（zsh / ksh）
- `type` 不会启动命令，只是解析名字，对性能友好

## 一句话总结

```text
type = which + 能区分 alias / function / builtin / keyword
```

排查"现在的 cd 是内建还是文件里那个" → `type cd`。
排查"PATH 里有哪些 grep" → `type -a grep`。
脚本里检测一个命令是否存在 → `command -v` 或 `type -t`。

## 参考

- Bash 官方手册 `man bash`，搜索 `type [-aftpP]`
- `help type`：Bash 内建帮助
- [Bash 官方手册 - Type 内建](https://www.gnu.org/software/bash/manual/html_node/Type.html)
- `command -v` vs `which`：POSIX 推荐使用 `command -v`，跨 shell 一致
