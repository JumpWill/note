# Vim

Vim / Neovim 是 Linux/Unix 传统编辑器，"全键盘 + 多模式 + 组合命令 + 文本对象 + 插件生态"的高效编辑工具。区别于现代 IDE：纯键盘、轻量、可远程、走命令组合。

```text
Normal Mode ── i / a / o ── Insert Mode ── Esc ── Normal Mode
                                                 │
                                                 ├── v    Visual
                                                 ├── V    Visual Line
                                                 ├── Ctrl+v Visual Block
                                                 └── :    Ex (Command-line)
```

## 1. 模式总览

| 模式 | 进入 | 特点 |
| ---- | ---- | ---- |
| **Normal（命令模式）** | 默认 / `Esc` | 移动 + 操作符 + 文本对象 |
| **Insert（插入模式）** | `i / a / o / I / A / O / c / s` | 直接输入文本 |
| **Visual（可视化）** | `v / V / Ctrl-v` | 选区 |
| **Command-line（命令模式）** | `:` / `/` / `?` | 范围 / 替换 / 设置 |
| **Replace** | `R` | 替换（覆写） |
| **Operator-pending** | `d / c / y / gu / gU` | 等待 motion |

## 2. 进入与退出

```bash
vim file                  # 打开（不存在则新建）
vim +10 file              # 打开并跳到第 10 行
vim +/pattern file        # 打开并定位第一个匹配
vim -O file1 file2        # 横向分屏
vim -o file1 file2        # 纵向分屏
vim -R file               # 只读
vim -d file1 file2        # diff
```

退出：

| 命令 | 行为 |
| ---- | ---- |
| `:q` | 退出（无修改） |
| `:q!` | 强制退出，丢弃修改 |
| `:w` | 保存 |
| `:w!` | 强制保存（如 root 可覆盖） |
| `:wq` / `:x` | 保存退出 |
| `:wq!` | 强制保存退出 |
| `ZZ` | 视作 `:wq`（Normal 下大写） |
| `ZQ` | 视作 `:q!` |

## 3. Normal Mode 移动

### 3.1 基本

| 命令 | 作用 |
| ---- | ---- |
| `h j k l` | 左 下 上 右 |
| `w / W` | 下个词 / 空白分隔 |
| `e / E` | 词尾 |
| `b / B` | 上个词头 |
| `0` / `^` | 行首 / 首个非空字符 |
| `$` | 行尾 |
| `g_` | 行末最后一个非空字符 |

### 3.2 屏幕

| 命令 | 作用 |
| ---- | ---- |
| `H M L` | 屏幕 顶 中 底 |
| `Ctrl-f / Ctrl-b` | 向下 / 向上滚一屏 |
| `Ctrl-d / Ctrl-u` | 半屏 |
| `Ctrl-e / Ctrl-y` | 行级别 |
| `zt / zz / zb` | 当前行 顶 中 底（重新对齐） |

### 3.3 文件 / 搜索

| 命令 | 作用 |
| ---- | ---- |
| `gg / G` | 首行 / 末行 |
| `%` | 跳转配对 `()[]{}` |
| `/pattern / ?pattern` | 向下 / 向上搜索 |
| `n / N` | 同向 / 反向 |
| `* / #` | 当前 word 向下 / 向上 全词搜索 |
| `f<char> / F<char>` | 行内右 / 左 跳字符 |
| `t<char> / T<char>` | 跳到字符前 |
| `; / ,` | 重复 / 反向 f 跳转 |

### 3.4 翻段落

| 命令 | 作用 |
| ---- | ---- |
| `{ / }` | 上 / 下 个空行 |
| `(` / `)` | 上 / 下 个句子 |
| `H M L` | 同上 |
| `g / g` | 已见 |

### 3.5 行内 / 列位置

| 命令 | 作用 |
| ---- | ---- |
| `<n> j / k` | 跳 n 行 |
| `:n` | 跳到 n 行 |
| `Ctrl-o / Ctrl-i` | 跳转列表前 / 后 |

## 4. Insert Mode

### 4.1 进入

| 命令 | 作用 |
| ---- | ---- |
| `i / I` | 当前光标前 / 行首 |
| `a / A` | 当前光标后 / 行尾 |
| `o / O` | 下方 / 上方插入新行 |
| `c / C` | 修改（删除再进入） |
| `s / S` | 替换字符 / 行 |
| `gi` | 继续上次插入位置 |

### 4.2 Insert 下的快捷键

| 命令 | 作用 |
| ---- | ---- |
| `Ctrl-h` | 删一字符 |
| `Ctrl-w` | 删一词 |
| `Ctrl-u` | 删到行首 |
| `Ctrl-c` | 退出插入（不动文档不展开缩写） |
| `Ctrl-o <cmd>` | 临时入 Normal 跑一次命令 |

### 4.3 自动缩进

```vim
set autoindent                       " 继承上行
set smartindent                      " 按语言缩进
set cindent                          " C 风格
```

## 5. 操作符与 Motion

Vim 的核心：**operator + motion** 组合。

### 5.1 操作符

| 操作符 | 含义 |
| ---- | ---- |
| `d` | delete（剪切） |
| `c` | change（删除进 insert） |
| `y` | yank（复制） |
| `>` / `<` | 缩进 / 反缩进 |
| `=` | 格式化（依赖 fmt 或 外部 formatter） |
| `gu / gU` | 变小写 / 大写 |
| `!` | 经 filter 处理 |

### 5.2 Motion 速查

| Motion | 含义 |
| ---- | ---- |
| `w / e / b` | 词头 / 词尾 |
| `W / E / B` | 大词 |
| `0 / $` | 行首 / 尾 |
| `j / k` | 下 / 上 |
| `f<char>` | 行内字符 |
| `/pattern` | 全文搜索 |
| `i( / i)` | 内 |
| `i{ / i}` | 内 |
| `ip` | 内 paragraph |
| `aw` | a word |
| `a"` | 引号整 |
| `G / gg` | 末 / 首 |

### 5.3 组合

```text
d + w    → dw       删除一词
c + i(   → ci(      删除 ( 内并进入 insert
y + $    → y$       复制到行尾
> + G    → >G       本行到末行缩进
gU + ip  → gUip     把段落内文字大写
```

数字 + 操作：

```vim
d5j                          # 删除 5 行（含本行）
y3w                          # 复制 3 个词
gU10j                         # 大写 11 行
```

## 6. 文本对象

| 对象 | 含义 |
| ---- | ---- |
| `iw / aw` | inner word / a word（含边界） |
| `is / as` | inner sentence / a sentence |
| `ip / ap` | inner paragraph / a paragraph |
| `i( / a(` | inner (...) |
| `i{ / a{` | inner {...} |
| `i< / a<` | inner <...> |
| `i" / a"` | inner "..." |
| `i' / a'` | inner '...' |
| `i` / a`` ` `` `` | inner \`...\` |
| `it / at` | inner HTML tag |

**inner** 不包含边界，**a** 包含。

## 7. 剪贴板 / 复制

### 7.1 寄存器

| Register | 用途 |
| -------- | ---- |
| `""` (0) | 默认（与 `"` 同），存最近 yanked |
| `"0` | 最近 yank 内容 |
| `"1-9` | history (删除 / 修改) |
| `"a` | 命名寄存器 a |
| `"+` | 系统剪贴板 |
| `"*` | X11 selection |
| `"_` | 黑洞寄存器 |

```vim
"ayy                       # 复制一行到 a
"ap                        # 粘贴 a
"_dw                       # 删除到黑洞（不放任何寄存器）
"+yy                       # 复制到系统剪贴板
"+p                        # 从系统剪贴板粘贴
```

### 7.2 撤销

| 命令 | 行为 |
| ---- | ---- |
| `u` | undo |
| `Ctrl-r` | redo |
| `:earlier Ns` | 回到 N 秒前 |
| `:later Ns` | 回到 N 秒后 |
| `:undolist` | 显示 undo 历史树 |

持久化 undo：

```vim
set undofile
set undodir=~/.vim/undodir
```

### 7.3 宏

```vim
qa        # 录制到 a 寄存器
...       # 后续操作被记录
q         # 结束
@a        # 执行宏
@@        # 重复执行
```

`recording` 显示在状态栏。

例：多行加注释：

```vim
qa                  # 开始录制
i// <Esc>           # 行首插入 //
j                   # 下行
q                   # 停止
100@a               # 执行 100 次
```

## 8. 搜索 / 替换

### 8.1 普通搜索

```vim
/foo              / 向下
?foo              / 向上
:set hlsearch     / 高亮
*                  / 当前 word 向下全词搜索
```

### 8.2 替换

```vim
:%s/foo/bar/g                # 全文
:%s/foo/bar/gc               # 询问
:5,10s/foo/bar/g             # 指定行
:'<,'>s/foo/bar/g            # 选区（前一行 :' '<esc> 触发）
:g/^\s*$/d                   # 删除空白行
:v/error/d                   # 删除不包含 error 的
:s/foo/\=@a/g                # 插入 register a
:%s/^\(\w\+\)/\1/gc          # 元组
:%s/^/  /                    # 每行前加两个空格
:g/^/m0                      # 反转（基于 m0）
```

`\=` 可以扩展成 expression。

## 9. 缓冲区 / 窗口

### 9.1 缓冲区

```vim
:ls                          / 缓冲区列表
:b <name>                    / 切换
:bd                          / 关闭
:bufdo %s/foo/bar/g          / 所有缓冲区执行
```

### 9.2 窗口

| 命令 | 用途 |
| ---- | ---- |
| `:sp file` / `:vs file` | 横 / 纵分屏 |
| `Ctrl-w s / Ctrl-w v` | 横 / 纵分（当前 buffer） |
| `Ctrl-w hjkl` | 左下上右 |
| `Ctrl-w w` | 循环 |
| `Ctrl-w q` | 关闭当前窗 |
| `Ctrl-w o` | 仅留当前 |
| `Ctrl-w =` | 等宽 |

### 9.3 Tab

```vim
:tabnew file
:tabn / :tabp
:tabdo %s/foo/bar/g
gt / gT               # 下/上个 tab
```

## 10. Fold（折叠）

```vim
set foldmethod=manual     # 默认
set foldmethod=indent     # 按缩进
set foldmethod=syntax     # 按语法
set foldmethod=expr       # 按表达式
set foldmethod=marker     # 按 marker

zf{motion}              # 创建折叠
zo / zO                 # 打开 / 全部打开
zc / zC                 # 关闭
za                      # 切换
zA                      # 递归切换
zd                      # 删除当前折叠
zD                      # 删除当前 buffer 折叠
zR                      # 全部打开
zM                      # 全部关闭
```

Markdown / 注释级别折叠：

```vim
set foldlevel=2
```

## 11. 设置（:set）

### 11.1 命令行

```vim
:set number                / 显示行号
:set relativenumber        / 相对行号
:set autoindent            / 自动缩进
:set smartindent
:set cindent
:set expandtab
:set tabstop=4
:set shiftwidth=4
:set hlsearch              / 高亮搜索
:set incsearch             / 增量
:set ignorecase            / 忽略大小写
:set smartcase             / 含大写时大小写敏感
:set showmatch             / 匹配括号高亮
:set cursorline            / 当前行高亮
:set wrap / nowrap         / 自动换行
:set mouse=a               / 鼠标
:set background=dark
:colorscheme default
:syntax on
:set spell spelllang=en_us
```

### 11.2 setlocal 与配置文件

- `~/.vimrc` / `~/.config/nvim/init.vim`
- `:` 模式下 `:edit ~/.vimrc` 后 `:source %`

```vim
" ~/.vimrc
set nocompatible
set number
set relativenumber
syntax on
filetype plugin indent on
set expandtab
set tabstop=2 shiftwidth=2
set smartcase incsearch hlsearch
set undofile
set undodir=~/.vim/undodir
nnoremap <Leader>w :w<CR>
nnoremap <Leader>q :q<CR>
```

### 11.3 Leader

```vim
let mapleader = " "     " 设 Leader 为空格
nnoremap <Leader>f :Files<CR>
```

## 12. 实用场景

### 12.1 多行注释

```vim
<count>i// <Esc>             # count 行 + //
:<count>i// | <Esc>
```

### 12.2 列编辑

```vim
Ctrl-v                  # 进入 visual block
jjjj                    # 选多行
I//                     # 插入 //
<Esc><Esc>              # 全部应用
```

### 12.3 替换 — 多行

```vim
:5,$s/foo/bar/g
```

### 12.4 自动完成

- `Ctrl-x Ctrl-f` 文件名
- `Ctrl-x Ctrl-o` omni completion（需 `:set omnifunc`）
- `<C-p> / <C-n>` 通用
- `Ctrl-x Ctrl-k` 字典

### 12.5 命令行宏

```vim
:10,20normal >>               # 对 10–20 行执行 >> 缩进
:%normal A.                    # 每行末尾加 .
:'<'>normal gUU                # 选区大写
```

### 12.6 与 shell 交互

```vim
:!ls                          # 跑 shell 命令
:r!date                       # 插入执行结果
:read !head file.txt
:'<,'>!sort                   # filter 选区
```

### 12.7 Diff / 合版

```vim
vim -d file1 file2
:diffthis                     # 标记当前窗为 diff
:diffupdate                   # 刷新
]c / [c                       # 下一 / 上一个 hunk
:diffget / :diffput           # 取 / 喂
```

### 12.8 同名 buffer 的存盘

`:set hidden` 让打开多个文件不强制关闭当前 buffer。

## 13. 文本对齐与格式化

| 命令 | 含义 |
| ---- | ---- |
| `=ip` | 段落内格式化 |
| `==` | 当前行缩进对齐 |
| `gq{motion}` | 段落 reformat (如 `gqap`) |
| `:center / :right / :left` | 范围对齐 |

按宽度格式化：`:set textwidth=80`

## 14. ASCII / 十六进制

```vim
:set fileformat=unix
:e ++ff=dos                   # 读为 DOS 格式
:x / :X                       # 编码 / 解码
:edit ++bin file              # 二进制
```

## 15. Neovim 增强

| 能力 | 说明 |
| ---- | ---- |
| LSP 内置 | Neovim 0.5+ 内置 |
| `:LspInfo` / `vim.lsp.*` | 语言服务器协议 |
| Treesitter | 语法树 |
| Lua | 配置语言（取代 vimrc） |
| Plugin | Nvim 兼容大部分 Vim 插件 |

```lua
-- ~/.config/nvim/init.lua
vim.opt.number = true
vim.opt.expandtab = true
vim.opt.tabstop = 2
vim.cmd('syntax on')
```

## 16. 插件管理

- **vim-plug** (vim8 / nvim)
- **packer** (nvim)
- **lazy.nvim** (nvim 现代懒加载)
- **dein**

示例 (lazy.nvim)：

```lua
{
  "nvim-lualine/lualine.nvim",
  config = function() require("lualine").setup({}) end,
}
```

## 17. 疑难与常见坑

| 问题 | 解决 |
| ---- | ---- |
| 替换不生效 | `:s/foo/bar/g` 中 `g` 必须；`%s/` 加 `%` |
| 折叠卡住 | `set foldlevel=99` 全部展开 |
| 中文编码 | `set encoding=utf-8` + `fileencodings=utf-8,gbk,latin1` |
| `:set paste` 影响性能 | 使用 `+` register 提交 |
| 终端颜色错乱 | 检查 `$TERM`，`xterm-256color` |
| `:!` 不返回 | `:!cmd && read` |
| Tab 缩进 4 / 2 切换 | `:retab` 全文件重排 |

## 18. 一句话总结

Vim 操控的核心：模式 + 操作符 + 文本对象 + 寄存器和宏 + 简单插件。
把 `i / Esc / :w / :q / hjkl / ddp / yyp / cw / u / Ctrl-r` 熟练即可覆盖 80% 编辑场景。

## 19. 参考

- `vimtutor`
- `:help usr_02.txt`
- [Vim Help](https://vimhelp.org/)
- [Practical Vim](https://pragprog.com/titles/dnvim2/)
- [vim-plug](https://github.com/junegunn/vim-plug)
- [Neovim](https://neovim.io/)
