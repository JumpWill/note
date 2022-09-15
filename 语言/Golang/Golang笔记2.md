## 包的导入

```go
// 导入一个包
import "fmt"

//给包取别名
import fmt "fmt"

// 多个包的导入
import (
	"fmt"
    "os"
)   

//导入而不使用
import _ "fmt" 

//使用的时候可以直接使用其方法，而不需要 fmt.xxx
import . "fmt" 
```

## 注释方式

```go
 // 单行注释

/*
多行注释
*/
```
## 关键字
```
包管理（2个）：
	import	package

程序实体声明与定义（8个）：
	chan	const	func	interface	map	struct	type	var

程序流程控制（15个）：
	break	case	continue	default	defer	else	fallthrough	
	for		go		goto		if		range	return	select		switch
```
## 变量
大写字母开头可被其他包使用，反之则是只能被本包使用。
使用驼峰命名法

## 数据类型

### 概述

Go 语言中数据类型分为：基本数据类型和复合数据类型基本数据类型有：

整型、浮点型、布尔型、字符串

复合数据类型有：

数组、切片、结构体、函数、map、通道（channel）、接口等。
### 整型

整型的类型有很多中，包括 int8，int16，int32，int64。我们可以根据具体的情况来进行定义

如果我们直接写 int也是可以的，它在不同的操作系统中，int的大小是不一样的

- 32位操作系统：int  -> int32
- 64位操作系统：int -> int64

|     类型      |                             释义                             |
| :-----------: | :----------------------------------------------------------: |
| uint8 (byte)  |                  无符号 8位整型 (0 到 255)                   |
|    uint16     |                 无符号 16位整型 (0 到 65535)                 |
|    uint32     |              无符号 32位整型 (0 到 4294967295)               |
|    uint64     |         无符号 64位整型 (0 到 18446744073709551615)          |
|     int8      |                 有符号 8位整型 (-128 到 127)                 |
|     int16     |              有符号 16位整型 (-32768 到 32767)               |
| int32（rune） |         有符号 32位整型 (-2147483648 到 2147483647)          |
|     int64     | 有符号 64位整型 (-9223372036854775808 到 9223372036854775807) |
|    uintptr    |                   无符号整型，用于存放指针                   |
|    float32    |                          32位浮点数                          |
|    float64    |                          64位浮点数                          |

> 可以通过unsafe.Sizeof 查看不同长度的整型，在内存里面的存储空间
>
> ```
> var num2 = 12
> fmt.Println(unsafe.Sizeof(num2))
> ```

#### 类型转换

通过在变量前面添加指定类型，就可以进行强制类型转换

```go
var a1 int16 = 10
var a2 int32 = 12
var a3 = int32(a1) + a2
fmt.Println(a3)
```

注意，高位转低位的时候，需要注意，会存在精度丢失，比如上述16转8位的时候，就丢失了

```go
var n1 int16 = 130
fmt.Println(int8(n1)) // 变成 -126
```

#### 数字字面量语法

Go1.13版本之后，引入了数字字面量语法，这样便于开发者以二进制、八进制或十六进制浮点数的格式定义数字，例如：

```go
v := 0b00101101  // 代表二进制的101101
v：= Oo377       // 代表八进制的377
```

#### 进制转换

```go
number := int64(17)

// 十进制输出
a := Sprintf("%d", number)
Println("  十进制   ",a)

o := Sprintf("%o", number)
Println("  八进制   ",o)

b := Sprintf("%b", number)
Println("  二进制   ",b)

s := strconv.FormatInt(number, 16)
Println("十六进制   ",s)


// 数值转n进制,数字需要为int64
// s := strconv.FormatInt(number, n)
```

### 浮点型

Go语言支持两种浮点型数：float32和float64。这两种浮点型数据格式遵循IEEE754标准：

float32的浮点数的最大范围约为3.4e38，可以使用常量定义：math.MaxFloat32。float64的浮点数的最大范围约为1.8e308，可以使用一个常量定义：math.MaxFloat64

打印浮点数时，可以使用fmt包配合动词%f，代码如下：

```go
var pi = math.Pi
// 打印浮点类型，默认小数点6位
fmt.Printf("%f\n", pi)
// 打印浮点类型，打印小数点后2位
fmt.Printf("%.2f\n", pi)
```

#### Golang中精度丢失的问题

几乎所有的编程语言都有精度丢失的问题，这是典型的二进制浮点数精度损失问题，在定长条件下，二进制小数和十进制小数互转可能有精度丢失

```go
d := 1129.6
fmt.Println(d*100) //输出112959.99999999
```

解决方法，使用第三方包来解决精度损失的问题

http://github.com/shopspring/decimal

### 布尔类型

定义

```go
var fl = false
if f1 {
    fmt.Println("true")
} else {
    fmt.Println("false")
}
```

### 字符串类型

Go 语言中的字符串以原生数据类型出现，使用字符串就像使用其他原生数据类型（int、bool、float32、float64等）一样。Go语言里的字符串的内部实现使用UTF-8编码。字符串的值为双引号（"）中的内容，可以在Go语言的源码中直接添加非ASCll码字符，例如：

```go
s1 := "hello"
s1 := "你好"
```

如果想要定义多行字符串，可以使用反引号
```go
	var str = `第一行
          第二行`
	fmt.Println(str)
```

#### 字符串常见操作

- len(str)：求长度
- +或fmt.Sprintf：拼接字符串
- strings.Split：分割
- strings.contains：判断是否包含
- strings.HasPrefix，strings.HasSuffix：前缀/后缀判断
- strings.Index()，strings.LastIndex()：子串出现的位置
- strings.Join()：join操作
- strings.Index()：判断在字符串中的位置

#### byte 和 rune类型

组成每个字符串的元素叫做 “字符”，可以通过遍历字符串元素获得字符。字符用单引号 '' 包裹起来

Go语言中的字符有以下两种类型

- uint8类型：或者叫byte型，代表了ACII码的一个字符
- rune类型：代表一个UTF-8字符

当需要处理中文，日文或者其他复合字符时，则需要用到rune类型，rune类型实际上是一个int32

Go使用了特殊的rune类型来处理Unicode，让基于Unicode的文本处理更为方便，也可以使用byte型进行默认字符串处理，性能和扩展性都有照顾。

需要注意的是，在go语言中，一个汉字占用3个字节（utf-8），一个字母占用1个字节

```go
package main
import "fmt"

func main() {
	var a byte = 'a'
	// 输出的是ASCII码值，也就是说当我们直接输出byte（字符）的时候，输出的是这个字符对应的码值
	fmt.Println(a)
	// 输出的是字符
	fmt.Printf("%c", a)

	// for循环打印字符串里面的字符
	// 通过len来循环的，相当于打印的是ASCII码
	s := "你好 golang"
	for i := 0; i < len(s); i++ {
		fmt.Printf("%v(%c)\t", s[i], s[i])
	}

	// 通过rune打印的是 utf-8字符
	for index, v := range s {
		fmt.Println(index, string(v))
	}

	// 将字符串转为unicode序列 
	data := []rune(s)
	for index, v := range data {
		fmt.Println(index, string(v))
	}
}
```

#### 修改字符串

要修改字符串，需要先将其转换成[]rune 或 []byte类型，完成后在转换成string，无论哪种转换都会重新分配内存，并复制字节数组

转换为 []byte 类型

```go
// 字符串转换
s1 := "big"
byteS1 := []byte(s1)
byteS1[0] = 'p'
fmt.Println(string(byteS1))
```

转换为rune类型

```go
// rune类型
s2 := "你好golang"
byteS2 := []rune(s2)
byteS2[0] = '我'
fmt.Println(string(byteS2))
```
#### 单引号/双引号/反引号
Golang限定字符或者字符串一共三种引号，单引号（’’)，双引号("") 以及反引号(``)。反引号就是标准键盘“Esc”按钮下面的那个键。
 >单引号，表示byte类型或rune类型，对应 uint8和int32类型，默认是 rune 类型。byte用来强调数据是raw data，而不是数字；而rune用来表示Unicode的code point。
 >
 >双引号，才是字符串，实际上是字符数组。可以用索引号访问某字节，也可以用len()函数来获取字符串所占的字节长度。
 >
 >反引号，表示字符串字面量，但不支持任何转义序列。字面量 raw literal string 的意思是，你定义时写的啥样，它就啥样，你有换行，它就换行。你写转义字符，它也就展示转义字符。
### 类型声明
```go
如果两个类型具有相同的底层类型，则两者可以互相转换
// type name 底层类型
type Int int
```
### 类型转换

#### 数值类型转换

```go
// 整型和浮点型之间转换
var aa int8 = 20
var bb int16 = 40
fmt.Println(int16(aa) + bb)

// 建议整型转换成浮点型
var cc int8 = 20
var dd float32 = 40
fmt.Println(float32(cc) + dd)
```

建议从低位转换成高位，这样可以避免

#### 转换成字符串类型

第一种方式，就是通过 fmt.Sprintf()来转换

```go
// 字符串类型转换
var i int = 20
var f float64 = 12.456
var t bool = true
var b byte = 'a'
str1 := fmt.Sprintf("%d", i)
fmt.Printf("类型：%v-%T \n", str1, str1)

str2 := fmt.Sprintf("%f", f)
fmt.Printf("类型：%v-%T \n", str2, str2)

str3 := fmt.Sprintf("%t", t)
fmt.Printf("类型：%v-%T \n", str3, str3)

str4 := fmt.Sprintf("%c", b)
fmt.Printf("类型：%v-%T \n", str4, str4)
```

第二种方法就是通过strconv包里面的集中转换方法进行转换

```go
// int类型转换str类型
var num1 int64 = 20
s1 := strconv.FormatInt(num1, 10)
fmt.Printf("转换：%v - %T", s1, s1)

// float类型转换成string类型
var num2 float64 = 3.1415926

/*
		参数1：要转换的值
		参数2：格式化类型 'f'表示float，'b'表示二进制，‘e’表示 十进制
		参数3：表示保留的小数点，-1表示不对小数点格式化
		参数4：格式化的类型，传入64位 或者 32位
	 */
s2 := strconv.FormatFloat(num2, 'f', -1, 64)
fmt.Printf("转换：%v-%T", s2, s2)
```

#### 字符串转换成int 和 float类型

```go
str := "10"
// 第一个参数：需要转换的数，第二个参数：进制， 参数三：32位或64位
num,_ = strconv.ParseInt(str, 10, 64)

// 转换成float类型
str2 := "3.141592654"
num,_ = strconv.ParseFloat(str2, 10)
```
## 控制与循环
### if/else
流程控制是每种编程语言控制逻辑走向和执行次序的重要部分，流程控制可以说是一门语言的“经脉"

Go 语言中最常用的流程控制有if和for，而switch和goto主要是为了简化代码、降低重复代码而生的结构，属于扩展类的流程控制。
```go
func main() {
	var num = 10
	if num == 10 {
		fmt.Println("hello == 10")
	} else if(num > 10) {
		fmt.Println("hello > 10")
	} else {
		fmt.Println("hello < 10")
	}
}
```
### for
Go语言中的所有循环类型均可使用for关键字来完成

for循环的基本格式如下：

```
for 初始语句; 条件表达式; 结束语句 {
	循环体
}
```

条件表达式返回true时循环体不停地进行循环，直到条件表达式返回false时自动退出循环

实例：打印1 ~ 10

```go
for i := 0; i < 10; i++ {
    fmt.Printf("%v ", i+1)
}
```

注意，在Go语言中，没有while语句，我们可以通过for来代替

```go
for {
    循环体
}
```

for循环可以通过break、goto、return、panic语句退出循环
#### for/range
Go 语言中可以使用for range遍历数组、切片、字符串、map及通道（channel）。通过for range遍历的返回值有以下规律：

- 数组、切片、字符串返回索引和值。
- map返回键和值。
- 通道（channel）只返回通道内的值。

实例：遍历字符串

```go
var str = "你好golang"
for key, value := range str {
    fmt.Printf("%v - %c ", key, value)
}
```

遍历切片（数组）

```go
var array = []string{"php", "java", "node", "golang"}
for index, value := range array {
    fmt.Printf("%v %s ", index, value)
}
```
### switch
-  可以使用任何类型或表达式作为条件语句；
- 不需要写break，一旦条件符合自动终止；
- case xxxx中，xxx可以是多个条件。
- 若希望继续执行下一个case，需使用fallthrough语句，但是仅仅只能执行下一个case，例如case a fallthrough case b,满足a条件，因为a中有fallthrough,则b中的也会执行。

```go
extname := ".a"
switch extname {
	case ".html": {
		fmt.Println(".html")
	}
	// 多个条件
	case ".doc",".txt": {
		fmt.Println(".doc")
	}
	case ".js": {
		fmt.Println(".js")
	}
	default: {
		fmt.Println("其它后缀")
	}
}
```
#### fallthrough
```
extname := ".txt"
switch extname {
	case ".html": {
		fmt.Println(".html")
		fallthrought
	}
	case ".txt",".doc": {
		fmt.Println("传递来的是文档")
		fallthrought
	}
	case ".js": {
		fmt.Println(".js")
		fallthrought
	}
	default: {
		fmt.Println("其它后缀")
	}
}
```
## 数组与切片
> 数组是固定长度的同一类型的数据集合，占用连续的内存
> 切片是可伸缩动态序列
### 数组

```go
// 数组的长度是类型的一部分
var arr1 [3]int
var arr2 [4]string
fmt.Printf("%T, %T \n", arr1, arr2)

// 数组的初始化 第一种方法
var arr3 [3]int
arr3[0] = 1
arr3[1] = 2
arr3[2] = 3
fmt.Println(arr3)

// 第二种初始化数组的方法
var arr4 = [4]int {10, 20, 30, 40}
fmt.Println(arr4)

// 第三种数组初始化方法，自动推断数组长度
var arr5 = [...]int{1, 2}
fmt.Println(arr5)

// 第四种初始化数组的方法，指定下标
a := [...]int{1:1, 3:5}
fmt.Println(a)

// 遍历
a := [...]int{1:1, 3:5}
for i := 0; i < len(a); i++ {
	fmt.Print(a[i], " ")
}
for _, value := range a {
    fmt.Print(value, " ")
}
```
### 切片
切片（Slice）是一个拥有相同类型元素的可变长度的序列。它是基于数组类型做的一层封装。
它非常灵活，支持自动扩容(切片就如python中的列表)

切片是一个引用类型，它的内部结构包含地址、长度和容量。
#### 基本使用
声明切片类型的基本语法如下：
```go
//- name：表示变量名
//T：表示切片中的元素类型
var name [] T
// 声明切片，把长度去除就是切片
var slice = []int{1,2,3}
fmt.Println(slice)
// 遍历切片
for i := 0; i < len(slice); i++ {
    fmt.Print(slice[i], " ")
}
```
#### 底层结构
切片的本质就是对底层数组的封装，它包含了三个信息

>底层数组的指针
>切片的长度(len)
>切片的容量(cap)


![image-20200720094247624](images/image-20200720094247624.png)

#### 长度和容量
切片拥有自己的长度和容量，我们可以通过使用内置的len）函数求长度，使用内置的cap（）
函数求切片的容量。

切片的长度就是它所包含的元素个数。

切片的容量是从它的第一个元素开始数，到其底层数组元素末尾的个数。切片s的长度和容量可通过表达式len（s）和cap（s）来获取。

#### make切片
切片扩容：当元素存放不下的时候，当容量小于1024的时候，会将原来的容量扩大两倍。大于1024，则会容量*1.25.
```go
// T：切片的元素类型
// size：切片中元素的数量
// cap：切片的容量
make ([]T, size, cap)

fmt.Println()
var slices = make([]int, 4, 8)
//[0 0 0 0]
fmt.Println(slices)
// 长度：4, 容量8
fmt.Printf("长度：%d, 容量%d", len(slices), cap(slices))
// 添加元素
slices = append(slices, 5)
// 合并两个切片
slices2 = append(slices, slices1...)
// 复制切片，改变其中一个的实话另一个不受不受影响
copy(slices5, slices4)
// Go语言中并没有删除切片元素的专用方法，利用切片本身的特性来删除元素
slices6 = append(slices6[:1], slices6[2:]...)



// 判断一个切片是否为空，应该是len(slice1)==0
var s []int // len(s)为0，s为nil
s = nil    // len(s)为0，s为nil
s = []int(nil) // len(s)为0，s为nil
s=[]int{} // len(s)为0，s不为nil
```


### 比较
- 数组是值类型，赋值和传参会赋值整个数组，因此改变副本的值，不会改变本身的值
- 在golang中，切片的定义和数组定义是相似的，但是需要注意的是，切片是引用数据类型，因此改变副本的值,会改变本身的值

```go
// 数组
var array1 = [...]int {1, 2, 3}
array2 := array1
array2[0] = 3
fmt.Println(array1, array2)
//[1 2 3] [3 2 3]

// 切片定义
var array3 = []int{1,2,3}
array4 := array3
array4[0] = 3
fmt.Println(array3, array4)
//[3 2 3] [3 2 3]
```

## map
map是一种无序的基于key-value的数据结构，Go语言中的map是引用类型，必须初始化才能使用。map类型的变量默认初始值为nil，需要使用make()函数来分配内存。语法为：
```go
// KeyType：表示键的类型
// ValueType：表示键对应的值的类型
map[KeyType]ValueType

// 方式1初始化
var userInfo = make(map[string]string)
userInfo["userName"] = "zhangsan"
fmt.Println(userInfo)
fmt.Println(userInfo["userName"])
// 创建方式2，map也支持声明的时候填充元素
var userInfo2 = map[string]string {
    "username":"张三",
    "sex":"女",
}
fmt.Println(userInfo2)

// 遍历map
for key, value := range userInfo2 {
    fmt.Println("key:", key, " value:", value)
}

// 判断是否存在,如果存在  ok = true，否则 ok = false
value, ok := userInfo2["username2"]
fmt.Println(value, ok)
// 删除map数据里面的key，以及对应的值
delete(userInfo2, "sex")
fmt.Println(userInfo2)
```
## 函数
函数是组织好的、可重复使用的、用于执行指定任务的代码块
Go语言支持：函数、匿名函数和闭包
Go语言中定义函数使用func关键字，具体格式如下：
```go
func 函数名(参数)(返回值) {
    函数体
}

// 求两个数的和
func sumFn(x int, y int) int{
	return x + y
}
// 调用方式
sunFn(1, 2)

//获取可变的参数，可变参数是指函数的参数数量不固定。Go语言中的可变参数通过在参数名后面加... 来标识。
//注意：可变参数通常要作为函数的最后一个参数
func sunFn2(x ...int) int {
	sum := 0
	for _, num := range x {
		sum = sum + num
	}
	return sum
}
// 调用方法
sunFn2(1, 2, 3, 4, 5, 7)


// 多值返回,返回的东西不需要声明，而可以直接赋值返回
func sunFn4(x int, y int)(sum int, sub int) {
	sum = x + y
	sub = x -y
	return
}
```
### 匿名函数
函数当然还可以作为返回值，但是在Go语言中，函数内部不能再像之前那样定义函数了，只能定义匿名函数,匿名函数就是没有函数名的函数，匿名函数的定义格式如下

```go
func (参数)(返回值) {
    函数体
}

fun return_fun() func(){
	return func(){
		...
	}
}

func main() {
	func () {
		fmt.Println("匿名自执行函数")
	}()

	fun := return_fun() 
	fun() //执行函数的内部的匿名函数

}
```
### 闭包
- 可以让一个变量常驻内存
- 可以让一个变量不污染全局

闭包可以理解成 “定义在一个函数内部的函数”。在本质上，闭包就是将函数内部 和 函数外部连接起来的桥梁。或者说是函数和其引用环境的组合体。

- 闭包是指有权访问另一个函数作用域中的变量的函数
- 创建闭包的常见的方式就是在一个函数内部创建另一个函数，通过另一个函数访问这个函数的局部变量

注意：由于闭包里作用域返回的局部变量资源不会被立刻销毁，所以可能会占用更多的内存，过度使用闭包会导致性能下降，建议在非常有必要的时候才使用闭包。

```go
package main
import "fmt"
func adder() func() int {
	var i = 10
	return func() int {
		return i + 1
	}
}

func adder2() func(y int) int {
	var i = 10
	return func(y int) int {
		i = i + y
		return i
	}
}

func main() {
	// 闭包

	// 不会污染全局变量
	var fn = adder()
	fmt.Println(fn())
	fmt.Println(fn())
	fmt.Println(fn())

	// 更改了函数内的变量,会修改函数内的变量
	// data的值更改
	var fn2 = adder2()
	data := 10
	fmt.Println(fn2(data))
	fmt.Println(fn2(data))
	fmt.Println(fn2(data))
}
```
### defer
Go 语言中的defer 语句会将其后面跟随的语句进行延迟处理。在defer归属的函数即将返回时，将延迟处理的语句按defer定义的逆序进行执行，也就是说，先被defer的语句最后被执行，最后被defer的语句，最先被执行。

并且多个defer是逆序执行，既是栈的顺序执行
```go
fmt.Println("1")
defer fmt.Println("2")
defer fmt.Println("3")
fmt.Println("4")

func main() {
	fmt.Println("开始")
	defer func() {
		fmt.Println("1")
		fmt.Println("2")
	}()
	fmt.Println("结束")
}
```
#### 执行时机
在Go语言的函数中return语句在底层并不是原子操作，它分为返回值赋值和RET指令两步。而defer语句执行的时机就在返回值赋值操作后，RET指令执行前。

### 错误处理
Go语言中是没有异常机制，但是使用panic / recover模式来处理错误

- panic：可以在任何地方引发
- recover：只有在defer调用函数内有效
``` go
func readFile(fileName string) error {
	if fileName == "main.go" {
		return nil
	} else {
		return errors.New("读取文件失败")
	}
}

func myFn () {
	defer func() {
		e := recover()
		if e != nil {
			fmt.Println("给管理员发送邮件")
		}
	}()
	err := readFile("XXX.go")
	if err != nil {
		panic(err)
	}
}

func main() {
	myFn()
}
```
### 内置函数
| 内置函数      | 介绍                                         |
| ------------- | ------------------------------------------------------------ |
| close         | 主要用来关闭channel                                          |
| len           | 用来求长度，比如string、array、slice、map、channel           |
| new           | 用来分配内存、主要用来分配值类型，比如 int、struct ，返回的是指针 |
| make          | 用来分配内存，主要用来分配引用类型，比如chan、map、slice     |
| append        | 用来追加元素到数组、slice中                                  |
| panic\recover | 用来处理错误  

## 日期函数
时间和日期是我们编程中经常会用到的，在golang中time包提供了时间的显示和测量用的函数。
```go

timeObj := time.Now()
year := timeObj.Year()
month := timeObj.Month()
day := timeObj.Day()
fmt.Printf("%d-%02d-%02d \n", year, month, day)

// 格式化
fmt.Println(timeObj2.Format("2006-01-02 15:04:05"))
// 获取时间戳
timeObj3 := time.Now()
// 获取毫秒时间戳
unixTime := timeObj3.Unix()
// 获取纳秒时间戳
unixNaTime := timeObj3.UnixNano(

// 日期字符串转换成时间戳
var timeStr2 = "2020-07-21 08:10:05";
var tmp = "2006-01-02 15:04:05"
timeObj5, _ := time.ParseInLocation(tmp, timeStr2, time.Local)
fmt.Println(timeObj5.Unix())

// 时间间隔
// 参考：https://www.zhangbj.com/p/652.html
t := time.Now()
time.Sleep(2e9) // 休眠2秒
delta := time.Now().Sub(t)
fmt.Println("时间差：", delta) 

// 睡眠
time.Sleep(time.Second)
fmt.Println("一秒后")
```
## 指针
要搞明白Go语言中的指针需要先知道三个概念

- 指针地址
- 指针类型
- 指针取值

Go语言中的指针操作非常简单，我们只需要记住两个符号：&：取地址，*：根据地址取值.
不是所有的值都有地址，但是所有变量都有地址，
```go
func main() {

	// 声明某个类型的指针，两种方式。
	// p := *int
	// p := new(int)
	v := 1
	fmt.Println(pointer(&v))
}

func pointer(p *int) *int {
	*p++
	return p
}

```
### make和new
可以通过new和make创建指针
```go
// 使用new关键字创建指针
aPoint := new(int)
fmt.Printf("%T \n", aPoint)
fmt.Println(*aPoint)
```


- 两者都是用来做内存分配的
- make只能用于slice、map以及channel的初始化，返回的还是这三个引用类型的本身
- 而new用于类型的内存分配，并且内存赌赢的值为类型的零值，返回的是指向类型的指针

## struct 
Golang中没有“类”的概念，Golang中的结构体和其他语言中的类有点相似。和其他面向对象语言中的类相比，Golang中的结构体具有更高的扩展性和灵活性。

Golang中的基础数据类型可以装示一些事物的基本属性，但是当我们想表达一个事物的全部或部分属性时，这时候再用单一的基本数据类型就无法满足需求了，Golang提供了一种自定义数据类型，可以封装多个基本数据类型，这种数据类型叫结构体，英文名称struct。也就是我们可以通过struct来定义自己的类型了。
```go
type Person struct {
	name string
	age int
	sex string
}
func main() {
	// 实例化结构体
	var person Person
	person.name = "张三"
	person.age = 20
	person.sex = "男"
	fmt.Printf("%#v", person)

	// 
	var person2 = new(Person)
	person2.name = "李四"
	person2.age = 30
	person2.sex = "女"
	fmt.Printf("%#v", person2)

	// 
	var person4 = Person{
    name: "张三",
    age: 10,
    sex: "女",
	}
	fmt.Printf("%#v", person4)
}
```
> 注意：结构体首字母可以大写也可以小写，大写表示这个结构体是公有的，在其它的包里面也可以使用，小写表示结构体属于私有的，在其它地方不能使用
struct是可以直接比较的

### 匿名字段与继承
结构体允许其成员字段在声明时没有字段名而只有类型，这种没有名字的字段就被称为匿名字段

匿名字段默认采用类型名作为字段名，结构体要求字段名称必须唯一，因此一个结构体中同种类型的匿名字段**只能一个**

结构体的字段类型可以是：基本数据类型，也可以是切片、Map 以及结构体

如果结构体的字段类似是：指针、slice、和 map 的零值都是nil，即还没有分配空间

如果需要使用这样的字段，需要先make，才能使用。

当使用嵌套的结构体时候，如A中使用到B，可以将B声明为匿名字段，就可以直接A.xxx,这个xxx可以是A和B的成员变量。

将一个变量声明为匿名字段就可以认为是继承了该结构体。
```go
// 嵌套，声明匿名变量，
type Mouse struct{
	Material string
	Color string
}

type Pc struct{
	Mouse
	Price float32
}
func main() {

	pc := Pc{}
	pc.Price = 250
	pc.Color = "Red"
	pc.Material = "塑料"
	fmt.Println(pc)
}
```


### 方法
在go语言中，没有类的概念但是可以给类型（结构体，自定义类型）定义方法。所谓方法就是定义了接收者的函数。接收者的概念就类似于其他语言中的this 或者self。


方法的定义格式如下：

```go
func (接收者变量 接收者类型) 方法名(参数列表)(返回参数) {
    函数体
}

type Person struct {
	name string
	age int
	sex string
}

// 定义一个结构体方法
func (self Person) PrintInfo() {
	fmt.Print(" 姓名: ", self.name)
	fmt.Print(" 年龄: ", self.age)
	fmt.Print(" 性别: ", self.sex)
	fmt.Println()
}

// 传入指针的话，在方法里面修改了值，会修改对应的结构体对象的值。可以直接使用p.SetInfo,实际应该是&p.SetInfo,编译器会隐式转换
func (p *Person) SetInfo(name string, age int, sex string)  {
	p.name = name
	p.age = age
	p.sex = sex
}

func main() {
	var person = Person{
		"张三",
		18,
		"女",
	}
	person.PrintInfo()	
	person.SetInfo("李四", 18, "男")
	person.PrintInfo()

	// 也可以将方法赋值给变量，然后插入的第一个参数是结构体，后面跟参数
	printinfo := Person.SetInfo
	printinfo(person,"李四", 18, "男")

}
```
### 结构体与json
Golang中的序列化和反序列化主要通过“encoding/json”包中的 json.Marshal() 和 json.Unmarshal()

#### 标签
Tag是结构体的元信息，可以在运行的时候通过反射的机制读取出来。Tag在结构体字段的后方定义，由一对反引号包裹起来，具体的格式如下：

```json
key1："value1" key2："value2"
```

结构体tag由一个或多个键值对组成。键与值使用冒号分隔，值用双引号括起来。同一个结构体字段可以设置多个键值对tag，不同的键值对之间使用空格分隔。

注意事项：为结构体编写Tag时，必须严格遵守键值对的规则。结构体标签的解析代码的容错能力很差，一旦格式写错，编译和运行时都不会提示任何错误，通过反射也无法正确取值。例如不要在key和value之间添加空格。
```go
// 定义一个学生结构体，注意结构体的首字母必须大写，代表公有，否则将无法转换
type Student struct {
	Id string `json:"id"` // 通过指定tag实现json序列化该字段的key
	Gender string `json:"gender"`
	Name string `json:"name"`
	Sno string `json:"sno"`
}
func main() {
	var s1 = Student{
		ID: "12",
		Gender: "男",
		Name: "李四",
		Sno: "s001",
	}
	// 结构体转换成Json（返回的是byte类型的切片）
	jsonByte, _ := json.Marshal(s1)
	jsonStr := string(jsonByte)
	fmt.Printf(jsonStr)

	var s2 = Student{}
	// 第一个是需要传入byte类型的数据，第二参数需要传入转换的地址
	err := json.Unmarshal([]byte(jsonStr), &s2)
	if err != nil {
		fmt.Printf("转换失败 \n")
	} else {
		fmt.Printf("%#v \n", s2)
	}


	// 通过tag去与结构体的数据进行绑定
	var str = `{"id":"12","gender":"男","name":"李四","sno":"s001"}`
	var s3 = Student{}
	// 第一个是需要传入byte类型的数据，第二参数需要传入转换的地址
	err = json.Unmarshal([]byte(str), &s3)
	if err != nil {
		fmt.Printf("转换失败 \n")
	} else {
		fmt.Printf("%#v \n", s2)
	} 
}
```
## 接口
Golang中的接口是一种抽象数据类型，Golang中接口定义了对象的行为规范，只定义规范不实现。接口中定义的规范由具体的对象来实现。

在Golang中接口（interface）是一种类型，一种抽象的类型。接口（interface）是一组函数method的集合，Golang中的接口不能包含任何变量。接口也可以像struct那样组合嵌套使用。

接口值都为nil或者二者的动态类型完全一致，且二者的动态类型的值可以比较，那么两个接口值相等。但是接口值不可比较例如是map/slice，那么比较两个接口会崩溃。

```go
/*
形式如下
type 接口名 interface {
    方法名1 (参数列表1) 返回值列表1
    方法名2 (参数列表2) 返回值列表2
}  
*/
type Animal interface {
	Run() string
	Eat() string
}



type Dog struct {
	Name  string
	Speed int
	Food  string
}
type Cat struct {
	Name  string
	Speed int
	Food  string
}

func (self *Dog) Run() string {
	return fmt.Sprintf("dog:%v is running and its speed is %v", self.Name, self.Speed)
}
func (self *Dog) Eat() string {
	return fmt.Sprintf("dog:%v is eating %v", self.Name, self.Food)
}

func (self *Cat) Run() string {
	return fmt.Sprintf("Cat:%v is running and its speed is %v", self.Name, self.Speed)
}
func (self *Cat) Eat() string {
	return fmt.Sprintf("Cat:%v is eating %v", self.Name, self.Food)
}

func Run(animal Animal) string {
	return animal.Run()
}
func Eat(animal Animal) string {
	return animal.Eat()
}

func main() {
	cat := Cat{Name: "tom", Speed: 5, Food: "fish"}
	dog := Dog{Name: "cheems", Speed: 20, Food: "bone"}
	fmt.Println(Run(&cat))
	fmt.Println(Run(&dog))
	fmt.Println(Eat(&cat))
	fmt.Println(Eat(&dog))

}
```
### 类型断言
一般用于函数or方法中传入动态类型，其实在go1.18中引入了范型。
```go
//相当于python中的isinstance
//如果x是type类型，那么ok为true
f,ok = x.(type)
```
## 并发
### goroutine
可以理解为用户级线程，这是对内核透明的，也就是系统并不知道有协程的存在，是完全由用户自己的程序进行调度的。Golang的一大特色就是从语言层面原生持协程，在函数或者方法前面加go关键字就可创建一个协程。可以说Golang中的协程就是goroutine。
```go
// 执行一个函数
go funA()
// 执行一个匿名函数
go func(){ ... }()
```
### 通道
管道是Golang在语言级别上提供的goroutine间的通讯方式，我们可以使用channel在多个goroutine之间传递消息。如果说goroutine是Go程序并发的执行体，channel就是它们之间的连接。channel是可以让一个goroutine发送特定值到另一个goroutine的通信机制。

Golang的并发模型是CSP（Communicating Sequential Processes），提倡通过通信共享内存而不是通过共享内存而实现通信。

Go语言中的管道（channel）是一种特殊的类型。管道像一个传送带或者队列，总是遵循先入先出（First In First Out）的规则，保证收发数据的顺序。每一个管道都是一个具体类型的导管，也就是声明channel的时候需要为其指定元素类型.

关闭channel后，无法向channel 再发送数据(引发 panic 错误后导致接收立即返回零值)；关闭channel后，可以继续从channel接收数据；
```go
// 定义 
// ch :=make(chan type)
ch :=make(chan int)

// 发送，接收和关闭(关闭一个通道不是必须的，通道会被垃圾回收)的三个功能
ch <- 1
num := <- ch
close(ch)

// 遍历通道
for x:=range ch{
	fmt.Println("get data from channel value is",x)
}
```
#### 无缓冲通道
无缓冲通道发送操作将会阻塞，直到另一个goroutine执行了接受操作。使用无缓冲通道发送和接受会同步化。
```go
func main() {
	num := make(chan int)
	res := make(chan int)
	go func() {
		for i := 0; i < 10; i++ {
			num <- i
		}
		close(num)
	}()
	go func() {
		for {
			if i, ok := <-num; ok {
				res <- i*i
			} else {
				break
			}
		}
		close(res)
	}()
		
	for x:=range res{
		fmt.Println("get data from channel value is",x)
	}
}
```
#### 单向通道
一个通道可以被限制为只能输入数据(输入通道)或者是只能输出数据(输出通道)。普通的通道可以转换为单向通道，但是反过来不行。
```go

var ch = make(chan int, 2)
ch <- 10
<- ch

// 管道声明为只写管道，只能够写入，不能读
var ch2 = make(chan<- int, 2)
ch2 <- 10

// 声明一个只读管道
var ch3 = make(<-chan int, 2)
<- ch3


// 一个例子

func insert_num(in chan<- int) {
	for i := 0; i < 10; i++ {
		in <- i
	}
	close(in)
}
func cal(input <-chan int, output chan<- int) {
	for x := range input {
		output <- x * x
	}
	// 可以关闭写入通道，但是不能关闭读取通道
	// 单向通道需要适当的关闭
	close(output)
}

func main() {
	num := make(chan int)
	res := make(chan int)
	go insert_num(num)
	go cal(num, res)
	for x := range res {
		fmt.Println("get data from channel value is", x)
	}
}
```
#### 缓存通道
缓冲通道是一个元素队列，创建时指定队列的最大长度。
使用缓冲通道，当队列没有满的时候，插入值是无阻塞的，当队列满了，则需要等待数据被取出。
```go
ch :=make(chan int,size)
// 获取通道的容量
cap(ch)
// 获取通道的len
len(ch)
```
#### select
同时需要用多个通道，从其中选择一个通道来用。当需要接受多个goroutine的信息的时候，当多个case同时到达，将会允许一个伪随机散算法选择case。
```go
func main() {
	ch1 := make(chan int, 10)
	ch1 <- 10
	ch1 <- 12
	ch1 <- 13
	ch2 := make(chan int, 10)
	ch2 <- 20
	ch2 <- 23
	ch2 <- 24

// 每次循环的时候，会随机中一个chan中读取，其中for是死循环
	for {
		select {
			case v:= <- ch1:
			fmt.Println("从initChan中读取数据：", v)
			case v:= <- ch2:
			fmt.Println("从stringChan中读取数据：", v)
			default:
			fmt.Println("所有的数据获取完毕")
			return
		}
	}
}
```
#### 选择
无缓冲通道和缓冲通道的选择，取决于生产和消费的速度。如果生产快，选择缓冲通道可以让消费也快。如果是消费快，缓冲通道就没意义。
#### 并行循环
for里面启动goroutine，让每个goroutine去跑执行每一次的循环。但需要考虑数据竞争的问题。
##### 例1，便利数据然后求和返回
goroutine需要结束后在执行，所以加上waitgroup。
因为可能产生数据竞争，所以加锁，保证数据安全。
```go
package main

import (
	"fmt"
	"sync"
	"time"
)

func sum(index int, num *[]int, total *int) {
	*total += (*num)[index]
}

func main() {
	num := []int{1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11}
	total := 0
	var mu sync.Mutex

	// 使用waitgroup，保证每个goroutine结束之后，在进行主线程
	var wg sync.WaitGroup
	for index, _ := range num {
		// 每次执行一个+1
		wg.Add(1)
		go func(index int, num *[]int, total *int) {
			mu.Lock()
			sum(index, num, total)
			mu.Unlock()
			wg.Done()
			// 完成然后done
		}(index, &num, &total)
	}
	time.Sleep(1000 * time.Microsecond)

	fmt.Println(total)
}
```
##### 例2,并行修改数组数据
```go
package main

import (
	"fmt"
	"sync"
	"time"
)
func update(index int, num *[]string) {
	(*num)[index] = (*num)[index] + " 11"
}

func main() {
	num := []string{"a", "b", "c"}
	var wg sync.WaitGroup
	for index, _ := range num {
		wg.Add(1)
		go func(index int, num *[]string) {
			update(index, num)
			wg.Done()
		}(index, &num)
	}
	time.Sleep(1000 * time.Microsecond)

	for _, value := range num {
		fmt.Println(value)
	}
}
``` 
## 共享内存
golang中建议使用channel来完成通信，而不是共享内存。
### 互斥锁
```go
var mu sync.Mutex
mu.Lock()
mu.Unlock()
```
### 读写锁
```go
var mu sync.RWMutex
// 读锁
mu.RLock()
mu.RUnlock()
// 写锁
mu.Lock()
mu.Unlock()
```
### 比较与选择
读写锁在竞争不激烈的时候才有优势。
在golang中写并发，尽量把变量限制到单个goroutine，对于其他变量，使用互斥锁。
### sync.once
当某些数据只需要一次初始化的时候，就可以用它。例如加载一些初始化变量。
```go
package main

import (
	"fmt"
	"sync"
)
var once sync.Once

func InitData()  {
	once.Do(func() {
		fmt.Println("init data just once")
	})
}


func main() {
	var wg sync.WaitGroup
	for I := 0; I < 10000; I++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			InitData()
		}()
	}
}

```
### 静态检测器
如果有数据安全的问题，就会有warning。
```shell
go run/build -race xxx.go
```
## 包
包（package）是多个Go源码的集合，是一种高级的代码复用方案，Go语言为我们提供了很多内置包，如fmt、strconv、strings、sort、errors、time、encoding/json、os、io等。

Golang中的包可以分为三种：1、系统内置包   2、自定义包   3、第三方包
### go mod
在Golang1.11版本之前如果我们要自定义包的话必须把项目放在GOPATH目录。Go1.11版本之后无需手动配置环境变量，使用go mod 管理项目，也不需要非得把项目放到GOPATH指定目录下，你可以在你磁盘的任何位置新建一个项目，Go1.13以后可以彻底不要GOPATH了。

常用指令
- go download：下载依赖的module到本地cache
- go edit：编辑go.mod文件
- go graph：打印模块依赖图
- go init：在当前文件夹下初始化一个新的module，创建go.mod文件
- tidy：增加丢失的module，去掉未使用的module
- vendor：将依赖复制到vendor下
- verify：校验依赖，检查下载的第三方库有没有本地修改，如果有修改，则会返回非0，否则校验成功
