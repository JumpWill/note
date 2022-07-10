## 注释方式
```lua
-- 单行注释

--[[
多行注释
--]]

```
## 关键字

|          |       |       |        |
| -------- | ----- | ----- | ------ |
| and      | break | do    | else   |
| elseif   | end   | false | for    |
| function | if    | in    | local  |
| nil      | not   | or    | repeat |
| return   | then  | true  | until  |
| while    | goto  |       |        |


## 变量
```lua
-- 全局变量，删除全局变量就是把global_var置为nil
global_var = 123

-- 局部变量
local local_var =123
```

## 数据类型
| 数据类型 | 描述                                                         |
| :------- | :----------------------------------------------------------- |
| nil      | 这个最简单，只有值nil属于该类，表示一个无效值（在条件表达式中相当于false）。 |
| boolean  | 包含两个值：false和true。                                    |
| number   | 表示双精度类型的实浮点数                                     |
| string   | 字符串由一对双引号或单引号来表示                             |
| function | 由 C 或 Lua 编写的函数                                       |
| userdata | 表示任意存储在变量中的C数据结构                              |
| thread   | 表示执行的独立线路，用于执行协同程序                         |
| table    | Lua 中的表（table）其实是一个"关联数组"（associative arrays），数组的索引可以是数字、字符串或表类型。在 Lua 里，table 的创建是通过"构造表达式"来完成，最简单构造表达式是{}，用来创建一个空表。 |

### nil
nil 类型表示一种没有任何有效值，它只有一个值 -- nil，例如打印一个没有赋值的变量，便会输出一个 nil 值：
```lua
local name = nil
-- 变量为nil的时候,
-- if nil为假,if 0 为真
if name then:
    print("this is not nil")
else
    print("this is nil")
```
### boolen
```lua
local bool = true
```
### number
Number 类型用于表示实数，和 C/C++ 里面的 double 类型很类似。可以使用数学函数 math.floor（向下取整）和 math.ceil（向上取整）进行取整操作。
一般地，Lua 的 number 类型就是用双精度浮点数来实现的。值得一提的是，LuaJIT 支持所谓的“dual-number”（双数）模式，即 LuaJIT 会根据上下文用整型来存储整数，而用双精度浮点数来存放浮点数。

另外，LuaJIT 还支持“长长整型”的大整数（在 x86_64 体系结构上则是 64 位整数）。例如

```lua
local order = 3.99
local score = 98.01
print(math.floor(order))   -->output:3
print(math.ceil(score))    -->output:99

print(9223372036854775807LL - 1)  -->output:9223372036854775806LL
```
### string
```lua
-- 三种方式,第三种方式特殊字符不会被转义
local name = 'hello world'
local name = "hello world"
local name = [["hello world"]]


--> 字符连接
print("Hello " .. "World")    -->打印 Hello World
print(0 .. 1)                 -->打印 01

str1 = string.format("%s-%s","hello","world")
print(str1)              -->打印 hello-world

str2 = string.format("%d-%s-%.2f",123,"world",1.21)
print(str2)              -->打印 123-world-1.21
```
Lua 的字符串是不可改变的值，不能像在 c 语言中那样直接修改字符串的某个字符，而是根据修改要求来创建一个新的字符串。Lua 也不能通过下标来访问字符串的某个字符。

想了解更多关于字符串的操作，请查看String 库章节。<https://moonbingbing.gitbooks.io/openresty-best-practices/content/lua/string_library.html>

在 Lua 实现中，Lua 字符串一般都会经历一个“内化”（intern）的过程，即两个完全一样的 Lua 字符串在 Lua 虚拟机中只会存储一份。

每一个 Lua 字符串在创建时都会插入到 Lua 虚拟机内部的一个全局的哈希表中。 这意味着创建相同的 Lua 字符串并不会引入新的动态内存分配操作，所以相对便宜（但仍有全局哈希表查询的开销），内容相同的 Lua 字符串不会占用多份存储空间，


已经创建好的 Lua 字符串之间进行相等性比较时是 O(1) 时间度的开销，而不是通常见到的 O(n)

由于 Lua 字符串本质上是只读的，因此字符串连接运算符几乎总会创建一个新的（更大的）字符串。这意味着如果有很多这样的连接操作（比如在循环中使用 .. 来拼接最终结果），则性能损耗会非常大。在这种情况下，推荐使用 table 和 table.concat() 来进行很多字符串的拼接。
### table
Table 类型实现了一种抽象的“关联数组”。“关联数组”是一种具有特殊索引方式的数组，索引通常是字符串（string）或者 number 类型，但也可以是除 nil 以外的任意类型的值。

在内部实现上，table 通常实现为一个哈希表、一个数组、或者两者的混合。具体的实现为何种形式，动态依赖于具体的 table 的键分布特点。

参考：<https://moonbingbing.gitbooks.io/openresty-best-practices/content/lua/table_library.html>

```lua
local corp = {
    web = "www.google.com",   --索引为字符串，key = "web",
                              -- value = "www.google.com"
    telephone = "12345678",   --索引为字符串
    staff = {"Jack", "Scott", "Gary"}, --索引为字符串，值也是一个表
    100876,              --相当于 [1] = 100876，此时索引为数字
                         --key = 1, value = 100876
    100191,              --相当于 [2] = 100191，此时索引为数字
    [10] = 360,          --直接把数字索引给出
    ["city"] = "Beijing" --索引为字符串
}

print(corp.web)               -->output:www.google.com
print(corp["telephone"])      -->output:12345678
print(corp[2])                -->output:100191
print(corp["city"])           -->output:"Beijing"
print(corp.staff[1])          -->output:Jack
print(corp[10])               -->output:360
print(#corp)                  --> 2 指的是100876,100191



--table作为数组
arr = {1,2,3}
print(#arr)                   --> 3

```

在table中最好使用table.remove(table_var,xxx)
### function
```lua
local function foo()
    print("in the function")
    --dosomething()
    local x = 10
    local y = 20
    return x + y
end

local a = foo    --把函数赋给变量

print(a())

--output:
in the function
30
```
#### 参数
##### 普通
略
```lua
function adds(numbers)
    total = 0
    for i, v in pairs(numbers) do
        total = total + v
    end

    return total
end
nums = { 1, 2, 3 }
t = adds(nums)
print(t)     -->> 6
nums = { 1, 2, 3, 4 }
t = adds(nums)
print(t)    -->> 10
```
##### 可变长参数

可变长参数 ...

```lua
function adds(...)
    total = 0
    -- 可变长参数通过{...}使用
    for i, v in pairs({...}) do
        total = total + v
    end
    return total
end

t = log(adds(1, 2, 3, 4))
print(t)
-->> 执行累加操作
-->> 10
```
##### 传入table
传入table为引用传递，如果说是函数里面改变了某些值,那么会改变函数外的table信息。
```lua
function_name{table content}

function worker(employee)
    if not employee.name or type(employee.name) ~= "string" then
        error("员工必须具备姓名")
    end
    if type(employee.language) ~= "string" then
        error("必须具备开发语言")
    end
    if type(employee.workingYears) ~= "number" then
        error("需要工作年限")
    end
    -- 还有其他属性，如籍贯省市，月薪等
    print(employee.province)
    print(employee.city)
    print(employee.salary)
end

worker{
    name = "ray",
    language = "java",
    workingYears = 10,
    province = "beiijng",
    city = "beijing"
}
```

#### 返回值
函数可以返回多个值。  

### userdata
自定义类型
### thread
待定

## 表达式与运算

无位运算
特殊 ~=
逻辑运算符 and/or/not
注意：所有逻辑操作符将 false 和 nil 视作假，其他任何值视作真，对于 and 和 or，“短路求值”，对于 not，永远只返回 true 或者 false。

## 控制结构
### if/else

```lua
score = 90
if score == 100 then
    print("Very good!Your score is 100")
elseif score >= 60 then
    print("Congratulations, you have passed it,your score greater or equal to 60")
--此处可以添加多个elseif
else
    print("Sorry, you do not pass the exam! ")
end
```

### while/repeat

lua中没有continue，但是有break。

```lua
x = 1
sum = 0
while x <= 5 do
    sum = sum + x
    x = x + 1
end
print(sum)  -->output 15

x = 10
repeat
    print(x)
 x = x-1
until x<0
```
### for
```lua
for var = begin, finish, step do
    --body
end

for i = 1, 10, 2 do
  print(i)
end

-- output:
1
3
5
7
9


-- 打印数组a的所有值
local a = {"a", "b", "c", "d"}
for i, v in ipairs(a) do
  print("index:", i, " value:", v)
end

-- output:
index:  1  value: a
index:  2  value: b
index:  3  value: c
index:  4  value: d
```

## pairs/ipairs
pairs既能遍历key/value类型数据，也能遍历数组类型数据，ipairs只能遍历key/value
pairs遍历所有不为nil的数据，ipairs遍历到位nil的数据就会停止。
```lua
local corp = {
    web = "www.google.com",   --索引为字符串，key = "web",
                              -- value = "www.google.com"
    telephone = nil,   --索引为字符串
    staff = {"Jack", "Scott", "Gary"}, --索引为字符串，值也是一个表
    100876,              --相当于 [1] = 100876，此时索引为数字
                         --key = 1, value = 100876
    -- 100191,              --相当于 [2] = 100191，此时索引为数字
    [10] = 360,          --直接把数字索引给出
    ["city"] = "Beijing" --索引为字符串
}


for i,j in pairs(corp) do
    print(i,j)
end
print("分割线----------------")
for i,j in ipairs(corp) do
    print(i,j)
end

-- 遍历的时候其实是根据存储的hash值进行遍历的，所以是先遍历的数值，然后才是字符。
-- 1	100876
-- 10	360
-- web	www.google.com
-- staff	table: 00000000001e9f00
-- city	Beijing
-- 分割线----------------
-- 1	100876

-- 在末尾添加new字符串
table.insert(corp, "new")
-- 在1处添加new字符串
table.insert(corp, 1, "new")
-- 连接只能是将其中数组类型连接起来，类似python xxx.join
print(table.concat(corp, " "))
-- 删除
table.remove(corp, 1)
-- 排序,数组才能排序
table.sort(corp)
for i,j in ipairs(corp) do
    print(i, j)
end

```
## 模块

一个单独的lua脚本可以被认为是一个模块，使用require就可以直接加载和缓存该模块，以及后续调用其方法。

``` lua
--> my.lua
local M = {}

function M.greeting()
    print("hello lua" )
end

return M

--> use my.lua
local my_module = require("my")
my_module.greeting()     -->output: hello Lu
```

## 元表(方法重载)

有一些+，-等运算以及tostring的运算，某些时候需要重写，这时候就需要元表。
例如下面的例子是重写了set1的+，将结果返回复制给set3.

```lua
local set1 = {10, 20, 30}   -- 集合
local set2 = {20, 40, 50}   -- 集合

-- 将用于重载__add的函数，注意第一个参数是self
local union = function (self, another)
    local set = {}
    local result = {}

    -- 利用数组来确保集合的互异性
    for i, j in pairs(self) do set[j] = true end
    for i, j in pairs(another) do set[j] = true end

    -- 加入结果集合
    for i, j in pairs(set) do table.insert(result, i) end
    return result
end
setmetatable(set1, {__add = union}) -- 重载 set1 表的 __add 元方法

local set3 = set1 + set2
for _, j in pairs(set3) do
    io.write(j.." ")               -->output：30 50 20 40 10
end
```

| 元方法     |                             含义                             |
| --------- | ----------------------------------------------------------|
| __add    |                            + 操作                            |
| "__sub"    |                - 操作 其行为类似于 "add" 操作                |
| "__mul"    |                * 操作 其行为类似于 "add" 操作                |
| "__div"    |                / 操作 其行为类似于 "add" 操作                |
| "__mod"    |                % 操作 其行为类似于 "add" 操作                |
| "__pow"    |             ^ （幂）操作 其行为类似于 "add" 操作              |
| "__unm"    |                         一元 - 操作                        |
| "__concat" |                    .. （字符串连接）操作                     |
| "__len"    |                            # 操作                            |
| "__eq"     | == 操作 函数 getcomphandler 定义了 Lua 怎样选择一个处理器来作比较操作 仅在两个对象类型相同且有对应操作相同的元方法时才起效 |
| "__lt"     |                            < 操作                            |
| "__le"     |                           <= 操作                            |
| "__index"    | 取下标操作用于访问 table[key]     |
| "__newindex" | 赋值给指定下标 table[key] = value |
| "__tostring" | 转换成字符串                      |
| "__call"     | 将table作为一个函数使用           |
| "__mode"     | 用于弱表(*week table*)            |

## 面向对象编程
lua中是通过table来实现面向对象编程的。
```lua
local _M = {}

local mt = { __index = _M }

function _M.deposit (self, v)
    self.balance = self.balance + v
end

function _M.withdraw (self, v)
    if self.balance > v then
        self.balance = self.balance - v
    else
        error("insufficient funds")
    end
end

function _M.new (self, balance)
    balance = balance or 0
    return setmetatable({balance = balance}, mt)
end

return _M


-- 其他地方使用
obj = require(xxx)
obj.xxx(args)
```

## 常用库

时间与日期 <https://moonbingbing.gitbooks.io/openresty-best-practices/content/lua/time_date_function.html>

数学操作 <https://moonbingbing.gitbooks.io/openresty-best-practices/content/lua/math_library.html>

文件操作 <https://moonbingbing.gitbooks.io/openresty-best-practices/content/lua/file.html>


## lua---协程
协程又称为微线程。
| 方法                | 描述                                                         |
| :------------------ | :----------------------------------------------------------- |
| coroutine.create()  | 创建 coroutine，返回 coroutine， 参数是一个函数，当和 resume 配合使用的时候就唤醒函数调用 |
| coroutine.resume()  | 重启 coroutine，和 create 配合使用                           |
| coroutine.yield()   | 挂起 coroutine，将 coroutine 设置为挂起状态，这个和 resume 配合使用能有很多有用的效果 |
| coroutine.status()  | 查看 coroutine 的状态 注：coroutine 的状态有三种：dead，suspended，running，具体什么时候有这样的状态请参考下面的程序 |
| coroutine.wrap（）  | 创建 coroutine，返回一个函数，一旦你调用这个函数，就进入 coroutine，和 create 功能重复 |
| coroutine.running() | 返回正在跑的 coroutine，一个 coroutine 就是一个线程，当使用running的时候，就是返回一个 corouting 的线程号 |
```lua
-- coroutine_test.lua 文件

-- 使用方式1
co = coroutine.create(
    function(i)
        print(i);
    end
)
 
coroutine.resume(co, 1)   -- 1
print(coroutine.status(co))  -- dead
 
print("----------")

-- 使用方式2
co = coroutine.wrap(
    function(i)
        print(i);
    end
)
 
co(1)
 
print("----------")
 


```
参考:https://www.runoob.com/lua/lua-coroutine.html
```lua
--协程例子

co2 = coroutine.create(
    function()
        for i=1,10 do
            print(i)
            if i == 3 then
                print(coroutine.status(co2))  --running
                print(coroutine.running()) --thread:XXXXXX
            end
            coroutine.yield()
        end
    end
)

-- 每yield一次,就需要resume一次
coroutine.resume(co2) --1
coroutine.resume(co2) --2
coroutine.resume(co2) --3
coroutine.resume(co2) --4
-- 还能resume

print(coroutine.status(co2))   -- suspended
print(coroutine.running())
 
print("----------")



```


## 文件IO
Lua I/O 库用于读取和处理文件。分为简单模式（和C一样）、完全模式。

- 简单模式（simple model）拥有一个当前输入文件和一个当前输出文件，并且提供针对这些文件相关的操作。
- 完全模式（complete model） 使用外部的文件句柄来实现。它以一种面对对象的形式，将所有的文件操作定义为文件句柄的方法

| 模式 | 描述                                                         |
| :--- | :----------------------------------------------------------- |
| r    | 以只读方式打开文件，该文件必须存在。                         |
| w    | 打开只写文件，若文件存在则文件长度清为0，即该文件内容会消失。若文件不存在则建立该文件。 |
| a    | 以附加的方式打开只写文件。若文件不存在，则会建立该文件，如果文件存在，写入的数据会被加到文件尾，即文件原先的内容会被保留。（EOF符保留） |
| r+   | 以可读写方式打开文件，该文件必须存在。                       |
| w+   | 打开可读写文件，若文件存在则文件长度清为零，即该文件内容会消失。若文件不存在则建立该文件。 |
| a+   | 与a类似，但此文件可读可写                                    |
| b    | 二进制模式，如果文件是二进制文件，可以加上b                  |
| +    | 号表示对文件既可以读也可以写                                 |

### io模块
io.read的参数
| 模式 | 描述                                                         |
| :--- | :----------------------------------------------------------- |
| a    |        从当前位置读取余下的所有内容，如果在文件尾，则返回空串""                |
| l   | 读取下一个行内容，如果在文件尾部则会返回nil |
| 数值    | 读取number个字符的字符串，如果在文件尾则会返回nil，如果吧number=0，则这个函数不会读取任何内容而返回一个空串""，在文件尾返回nil |

io.tmpfile():返回一个临时文件句柄，该文件以更新模式打开，程序结束时自动删除
io.type(file): 检测obj是否一个可用的文件句柄
io.flush(): 向文件写入缓冲中的所有数据
io.lines(optional file name): 返回一个迭代函数,每次调用将获得文件中的一行内容,当到文件尾时，将返回nil,但不关闭文件

### 简单模式
简单模式在做一些简单的文件操作时较为合适。但是在进行一些高级的文件操作的时候，简单模式就显得力不从心。例如同时读取多个文件这样的操作，使用完全模式则较为合适。

```lua
-- 以只读方式打开文件
file = io.open("test.lua", "r")

-- 设置默认输入文件为 test.lua
io.input(file)

-- 输出文件第一行
print(io.read())

-- 关闭打开的文件
io.close(file)

-- 以附加的方式打开只写文件
file = io.open("test.lua", "a")

-- 设置默认输出文件为 test.lua
io.output(file)

-- 在文件最后一行添加 Lua 注释
io.write("--  test.lua 文件末尾注释")

-- 关闭打开的文件
io.close(file)
```

### 完全模式
通常我们需要在同一时间处理多个文件。我们需要使用 file:function_name 来代替 io.function_name 方法。
```lua
-- 以只读方式打开文件
test = io.open("test.lua", "r")

-- 输出文件第一行
print(test:read())

-- 关闭打开的文件
test:close()

-- 以附加的方式打开只写文件
test = io.open("test.lua", "a")

-- 在文件最后一行添加 Lua 注释
test:write("--test")

-- 关闭打开的文件
test:close()

```

read方法的参数与普通模式一致。
其他方法
```lua
file:seek(optional whence, optional offset): 设置和获取当前文件位置,成功则返回最终的文件位置(按字节),失败则返回nil加错误信息。参数 whence 值可以是:
"set": 从文件头开始
"cur": 从当前位置开始[默认]
"end": 从文件尾开始
offset:默认为0
不带参数file:seek()则返回当前位置,file:seek("set")则定位到文件头,file:seek("end")则定位到文件尾并返回文件大小
file:flush(): 向文件写入缓冲中的所有数据
```                           |
## 错误处理
### assert/error
运行错误是程序可以正常执行，但是会输出报错信息。
```lua
local function add(a,b)
    assert(type(a) == "number", "a 不是一个数字")
    if type(b) ~= "number"
    then
        error("this is errror",1)
    end
    return a+b
end
add(10)
```
### pcall/xcall
```lua
function myfunction ()
    n = n/nil
end

if pcall(myfunction) then
    print("Success")
else
    print("error")
end

function ErrorHandler( err )
    print( "ERROR:", err )
end

status = xpcall( myfunction, ErrorHandler )
print( status)  -- fasle 表示出错
```
## 垃圾回收
Lua 采用了自动内存管理。 这意味着你不用操心新创建的对象需要的内存如何分配出来， 也不用考虑在对象不再被使用后怎样释放它们所占用的内存。
### 垃圾回收机制
Lua 实现了一个增量标记-扫描收集器。 它使用这两个数字来控制垃圾收集循环： 垃圾收集器间歇率和垃圾收集器步进倍率。 这两个数字都使用百分数为单位 （例如：值 100 在内部表示 1 ）。
```lua
垃圾收集器间歇率:
    垃圾收集器间歇率控制着收集器需要在开启新的循环前要等待多久。 增大这个值会减少收集器的积极性。 当这个值比 100 小的时候，收集器在开启新的循环前不会有等待。 设置这个值为 200 就会让收集器等到总内存使用量达到 之前的两倍时才开始新的循环。
垃圾收集器的进倍进率：
    垃圾收集器步进倍率控制着收集器运作速度相对于内存分配速度的倍率。 增大这个值不仅会让收集器更加积极，还会增加每个增量步骤的长度。 不要把这个值设得小于 100 ， 那样的话收集器就工作的太慢了以至于永远都干不完一个循环。 默认值是 200 ，这表示收集器以内存分配的"两倍"速工作
```
Lua 提供了以下函数collectgarbage ([opt [, arg]])用来控制自动内存管理:
collectgarbage("collect"): 做一次完整的垃圾收集循环。通过参数 opt 它提供了一组不同的功能：
collectgarbage("count"): 以 K 字节数为单位返回 Lua 使用的总内存数。 这个值有小数部分，所以只需要乘上 1024 就能得到 Lua 使用的准确字节数（除非溢出）。
collectgarbage("restart"): 重启垃圾收集器的自动运行。
collectgarbage("setpause"): 将 arg 设为收集器的 间歇率。 返回 间歇率 的前一个值。
collectgarbage("setstepmul"): 返回 步进倍率 的前一个值。
collectgarbage("step"): 单步运行垃圾收集器。 步长"大小"由 arg 控制。 传入 0 时，收集器步进（不可分割的）一步。 传入非 0 值， 收集器收集相当于 Lua 分配这些多（K 字节）内存的工作。 如果收集器结束一个循环将返回 true 。
collectgarbage("stop"): 停止垃圾收集器的运行。 在调用重启前，收集器只会因显式的调用运行。
参考：https://zhuanlan.zhihu.com/p/476061122