# 05 - Map

Go 的 `map` 是哈希表的引用类型,键必须可比较。

## 一、基础

### 1. 创建

```go
// 字面量
m := map[string]int{
    "alice": 30,
    "bob":   25,
}

// make
m := make(map[string]int, 10)  // 预分配容量,提示性能

// nil map:可读但写会 panic
var m map[string]int            // m == nil
fmt.Println(m["x"])             // 0(零值)
m["x"] = 1                      // panic: assignment to entry in nil map
```

### 2. 增删改查

```go
m := make(map[string]int)

// 增 / 改
m["alice"] = 30

// 查(经典的双返回值)
v, ok := m["alice"]
if ok {
    fmt.Println("found:", v)
} else {
    fmt.Println("not found")
}

// 仅返回值(忽略存在性)
v := m["alice"]   // 不存在时返回零值

// 删
delete(m, "alice")

// 删不存在的键,不报错
delete(m, "nonexistent")

// 清空
clear(m)            // Go 1.21+,清空所有键
```

### 3. 长度

```go
len(m)               // 键值对数量
m == nil             // 仅判断 nil,不能判空
len(m) == 0          // 推荐判空
```

## 二、遍历

```go
m := map[string]int{"a": 1, "b": 2, "c": 3}

// 1. range
for k, v := range m {
    fmt.Println(k, v)
}

// 2. 仅遍历 key
for k := range m {
    fmt.Println(k)
}

// 3. 仅遍历 value
for _, v := range m {
    fmt.Println(v)
}

// 4. 顺序:Go 的 map 遍历顺序是**随机的**,每次都可能不同
//    想稳定顺序:把 key 取出来排序再遍历
keys := make([]string, 0, len(m))
for k := range m {
    keys = append(keys, k)
}
sort.Strings(keys)
for _, k := range keys {
    fmt.Println(k, m[k])
}
```

## 三、键类型

键必须是**可比较**的类型:`==` 和 `!=` 可用。

```go
// 可用:基本类型、string、数组(元素也可比较)、指针、接口(动态值可比)、struct(字段全可比较)
m1 := map[string]int{}
m2 := map[int]string{}
m3 := map[[2]int]string{}           // 数组作键
m4 := map[struct{ x, y int }]int{}  // struct 作键(字段全可比较)

// 不可用:slice、map、函数
// m5 := map[[]int]string{}    // 编译错误
// m6 := map[map[string]int]string{}    // 编译错误
```

## 四、并发安全

**map 不是并发安全的**。多 goroutine 同时读写会 panic。

```go
// ❌ 错误
var m = make(map[string]int)
go func() { m["a"] = 1 }()       // 写
go func() { _ = m["a"] }()       // 读
// 并发读写 → fatal error: concurrent map read and map write

// ✅ 方案 1:sync.Mutex / RWLock
var mu sync.RWMutex
m := make(map[string]int)
go func() {
    mu.Lock()
    m["a"] = 1
    mu.Unlock()
}()
go func() {
    mu.RLock()
    _ = m["a"]
    mu.RUnlock()
}()

// ✅ 方案 2:sync.Map(读多写少场景)
var m sync.Map
m.Store("a", 1)
v, ok := m.Load("a")
m.Range(func(k, v interface{}) bool {
    fmt.Println(k, v)
    return true
})
m.Delete("a")
```

## 五、set(集合)

Go 没有内建 set,用 `map[T]struct{}` 实现:

```go
type Set[T comparable] map[T]struct{}

// 添加
func (s Set[T]) Add(v T) { s[v] = struct{}{} }

// 删除
func (s Set[T]) Delete(v T) { delete(s, v) }

// 存在
func (s Set[T]) Has(v T) bool {
    _, ok := s[v]
    return ok
}

// 大小
func (s Set[T]) Len() int { return len(s) }

// 集合操作
func Union[T comparable](a, b Set[T]) Set[T] {
    out := make(Set[T], len(a)+len(b))
    for k := range a {
        out[k] = struct{}{}
    }
    for k := range b {
        out[k] = struct{}{}
    }
    return out
}

func Intersection[T comparable](a, b Set[T]) Set[T] {
    out := make(Set[T])
    for k := range a {
        if _, ok := b[k]; ok {
            out[k] = struct{}{}
        }
    }
    return out
}

func Difference[T comparable](a, b Set[T]) Set[T] {
    out := make(Set[T])
    for k := range a {
        if _, ok := b[k]; !ok {
            out[k] = struct{}{}
        }
    }
    return out
}
```

## 六、综合实战:词频统计

```go
package wordcount

import (
    "bufio"
    "sort"
    "strings"
)

type Pair struct {
    Word  string
    Count int
}

func Count(text string) []Pair {
    counts := make(map[string]int)
    scanner := bufio.NewScanner(strings.NewReader(text))
    scanner.Split(bufio.ScanWords)

    for scanner.Scan() {
        word := strings.ToLower(scanner.Text())
        counts[word]++
    }

    // 排序
    pairs := make([]Pair, 0, len(counts))
    for w, c := range counts {
        pairs = append(pairs, Pair{w, c})
    }
    sort.Slice(pairs, func(i, j int) bool {
        if pairs[i].Count != pairs[j].Count {
            return pairs[i].Count > pairs[j].Count
        }
        return pairs[i].Word < pairs[j].Word
    })
    return pairs
}
```

## 七、要点速记

- **`map` 是引用类型,`make` 或字面量创建**
- **`v, ok := m[key]` 检查存在**
- **`delete(m, key)` 删除,`clear(m)` 清空(Go 1.21+)**
- **map 遍历顺序随机,需要稳定顺序时 sort key**
- **map 不是并发安全,读写并发会 panic**
- **`sync.Map` 适合读多写少场景**
- **键必须可比较,slice / map / 函数不能作键**
- **集合用 `map[T]struct{}` 实现,`struct{}` 零字节**
- **Go 1.21+ 标准库 `maps` 包:`maps.Clone` / `maps.Copy` / `maps.DeleteFunc`**
