## todo

选项式和组合式(看起来舒服)

<https://zhuanlan.zhihu.com/p/603872840>

## 项目

```shell
# node -v > 15
npm  init vue@lastest
```

Project name 不要大些
SX Support

### 项目结构

| 文件 |           作用           |
| :--: | :-----------------------: |
| node_modules |      vue项目运行以的依赖      |
| public |   icon    |
| src |     源码    |
| index.html |  入口文件  |
| package.json |   信息描述文件  |
| vite.config.js |  配置文件   |

## 基础

### 内置指令

指令是带有 v- 前缀的特殊 attribute。Vue 提供了许多内置指令，如 v-bind 和 v-html。

#### v-text

更新元素的文本内容。

期望的绑定值类型：string

```vue
<span v-text="msg"></span>
<!-- 等同于 -->
<span>{{msg}}</span>
```

#### v-html

更新元素的 innerHTML。

期望的绑定值类型：原生html string

```vue
<div v-html="html"></div>
```

#### v-if/v-else/v-else-if/v-show

v-if 指令用于条件性地渲染一块内容。这块内容只会在指令的表达式返回真值时才被渲染。
v-else-if 判断值的时候用
v-else 均不满足
v-show 用法同 v-if
(不同之处在于 v-show 会在 DOM 渲染中保留该元素；v-show 仅切换了该元素上名为 display 的 CSS 属性。v-show 不支持在 <template> 元素上使用，也不能和 v-else 搭配使用。)

```vue

<div v-if="type === 'A'">
  A
</div>
<div v-else-if="type === 'B'">
  B
</div>
<div v-else-if="type === 'C'">
  C
</div>
<div v-else>
  Not A/B/C
</div>
```

##### 对比

v-if 是“真实的”按条件渲染，因为它确保了在切换时，条件区块内的事件监听器和子组件都会被销毁与重建。

v-if 也是惰性的：如果在初次渲染时条件值为 false，则不会做任何事。条件区块只有当条件首次变为 true 时才被渲染。

相比之下，v-show 简单许多，元素无论初始条件如何，始终会被渲染，只有 CSS display 属性会被切换。

总的来说，v-if 有更高的切换开销，而 v-show 有更高的初始渲染开销。因此，如果需要频繁切换，则使用 v-show 较好；如果在运行时绑定条件很少改变，则 v-if 会更合适

#### v-for

基于原始数据多次渲染元素或模板块。

期望的绑定值类型：Array | Object | number | string | Iterable

```vue
<div v-for="item in items">
<!-- <div v-for="(item, index) in items">​ -->
<!-- <div v-for="(value, key) in object"> -->
<!-- <div v-for="(value, name, index) in object"> -->
  {{ item.text }}
</div>
```

##### 数组变化侦测

当使用循环的时候,如果列表自身数据发生变化,那么UI也会发生变化,
但是数组的方法分为改变自身数据和返回个新数据两类,
调用前者UI会变化,
后者则是需要将返会的数据赋予给原数组

###### 改变自身数据

- push()
- pop()
- shift()
- unshift()
- splice()
- sort()
- reverse()

###### 返回新数据

- filter()
- concat()
- slice()

```vue
// 添加数据
items.push(xx)

// `items` 是一个数组的 ref
items.value = items.value.filter((item) => item.message.match(/Foo/))


// 例子

const msg = ref('hello')

//侦听器
watch(msg, async (new_value, old_value) => {
  console.log(new_value, old_value)
})
```

##### 通过 key 管理状态

Vue 默认按照“就地更新”的策略来更新通过 v-for 渲染的元素列表。当数据项的顺序改变时，Vue 不会随之移动 DOM 元素的顺序，而是就地更新每个元素，确保它们在原本指定的索引位置上渲染。

默认模式是高效的，但只适用于列表渲染输出的结果不依赖子组件状态或者临时 DOM 状态 (例如表单输入值) 的情况。

TODO v-for 组件

#### v-bind

双大括号不能在 HTML attributes 中使用。想要响应式地绑定一个 attribute，应该使用 v-bind 指令：
v-bind 指令指示 Vue 将元素的 id attribute 与组件的 dynamicId 属性保持一致。如果绑定的值是 null 或者 undefined，那么该 attribute 将会从渲染的元素上移除,该属性不会渲染到网页中。

```vue
<!-- 全写 -->
<div v-bind:id="dynamicId"></div>
<!-- 简写 -->
<div :id="dynamicId"></div>
<!-- 布尔型 -->
<button :disabled="isButtonDisabled">Button</button>
<!-- 动态绑定多个值​ -->
<div v-bind="objectOfAttrs">动态绑定多个值​</div>
<!-- 动态 attribute 名 -->
<button v-bind:[key]="value"></button>
<!-- 实例​ -->
<script>
export default {
  data() {
    return {
      msg: " am attributes"
      isButtonDisabled:true,
      objectOfAttrs : {
            id: 'container',
            class: 'wrapper'
        }       
    }
  }
}
</script>

<template>
  <div :id="msg">{{ msg }}</div>
</template>
```

#### v-on

给元素绑定事件处理器。
事件处理器 (handler) 的值可以是

- 内联事件处理器：事件被触发时执行的内联 JavaScript 语句 (与 onclick 类似)。
- 方法事件处理器：一个指向组件上定义的方法的属性名或是路径(方法)

修饰符

- stop - 调用 event.stopPropagation()。
- prevent - 调用 event.preventDefault()。
- capture - 在捕获模式添加事件监听器。
- self - 只有事件从元素本身发出才触发处理函数。
- {keyAlias} - 只在某些按键下触发处理函数。
- once - 最多触发一次处理函数。
- left - 只在鼠标左键事件触发处理函数。
- right - 只在鼠标右键事件触发处理函数。
- middle - 只在鼠标中键事件触发处理函数。
- passive - 通过 { passive: true } 附加一个 DOM 事件

参考:<https://cn.vuejs.org/guide/essentials/event-handling.html#key-modifiers>

```vue
<!-- 方法处理函数 -->
<button v-on:click="doThis"></button>

<!-- 动态事件 -->
<button v-on:[event]="doThis"></button>

<!-- 内联声明 -->
<button v-on:click="doThat('hello', $event)"></button>

<!-- 缩写 -->
<button @click="doThis"></button>

<!-- 使用缩写的动态事件 -->
<button @[event]="doThis"></button>

<!-- 停止传播 -->
<button @click.stop="doThis"></button>

<!-- 阻止默认事件 -->
<button @click.prevent="doThis"></button>

<!-- 不带表达式地阻止默认事件 -->
<form @submit.prevent></form>

<!-- 链式调用修饰符 -->
<button @click.stop.prevent="doThis"></button>

<!-- 按键用于 keyAlias 修饰符-->
<input @keyup.enter="onEnter" />

<!-- 点击事件将最多触发一次 -->
<button v-on:click.once="doThis"></button>

<!-- 对象语法 -->
<button v-on="{ mousedown: doThis, mouseup: doThat }"></button>

<!-- 参数传递 123是方法的参数,event是事件本身 -->
<MyComponent @my-event="handleThis(123, $event)" />

```

### 计算属性​

模板中的表达式虽然方便，但也只能用来做简单的操作。如果在模板中写太多逻辑，会让模板变得臃肿，难以维护。

因此我们推荐使用计算属性来描述依赖响应式状态的复杂逻辑.

```vue
<script>
const msg = ref('hello')

// 计算
const computed_msg = computed(() => {
  return msg.value + '  world'
})
// 直接使用方法
// 组件中
function computed_msg2() {
  return msg.value + '  world'
}

function change() {
  msg.value = msg.value + '111'
}

</script>
<template>
  <span>{{ computed_msg }}</span>
  <span>{{ computed_msg2() }}</span>
  <button @click="change">1111</button>
</template>
```

#### 计算属性缓存 vs 方法

计算属性值会基于其响应式依赖被缓存(相同的东西多次使用会有缓存)
方法调用多少次执行多少次

### 类与样式绑定

在操作中可能需要改变某个元素的样式,此时就需要为某个元素单独加上样式
class/style 类似

```vue
<script setup>
import { ref, reactive } from 'vue'
const msg = ref('hello')
// 变量
const color = ref(true)
const size = ref(true)

// 复杂对象
let style = ref({
  'color': true,
  'size': true
})

// 复杂数组
let arr = ref(['color', 'size'])

function change() {
  color.value = !color.value
  size.value = !size.value

  style.value.color = !style.value.color
  style.value.size = !style.value.size
  if (arr.value.length === 0) {
    arr.value = ['color', 'size']
  } else {
    arr.value = []
  }
}

</script>

<template>
  <p :class="{ 'color': color, 'size': size }">{{ msg }}</p><br>
  <p :class="style">{{ msg }}</p><br>
  <p :class="arr">{{ msg }}</p><br>
  <button @click="change">1111</button>
</template>
<style scoped>
.color {
  color: red;
}
.size {
  font-size: 30px;
}
</style><script setup>
import { ref, reactive } from 'vue'
const msg = ref('hello')
// 变量
const color = ref(true)
const size = ref(true)

// 复杂对象
let style = ref({
  'color': true,
  'size': true
})

// 复杂数组
let arr = ref(['color', 'size'])

function change() {
  color.value = !color.value
  size.value = !size.value

  style.value.color = !style.value.color
  style.value.size = !style.value.size
  if (arr.value.length === 0) {
    arr.value = ['color', 'size']
  } else {
    arr.value = []
  }
}

</script>

<template>
  <p :class="{ 'color': color, 'size': size }">{{ msg }}</p><br>
  <p :class="style">{{ msg }}</p><br>
  <p :class="arr">{{ msg }}</p><br>

  <button @click='change'>1111</button>
</template>

<style scoped>
.color {
  color: red;
}

.size {
  font-size: 30px;
}
</style>

```

### 侦听器

计算属性允许我们声明性地计算衍生值。然而在有些情况下，我们需要在状态变化时执行一些“副作用”：例如更改 DOM，或是根据异步操作的结果去修改另一处的状态。

```vue
const question = ref('')
// watch(var_name ) var_name指定需要侦听的数据
watch(question, async (new_value, old_value) => {
  console.log(new_value, old_value)
})
```

### 表单输入绑定

```vue
<script setup>
import { ref } from 'vue'
const msg = ref('hello')
const checked = ref('')
function change() {
  msg.value = msg.value + "111"
}
</script>

<template>
  <textarea v-model="msg"></textarea><br>
  <button @click="change">1111</button>


  <input type="checkbox" id="checkbox" v-model="checked" />
<label for="checkbox">{{ checked }}</label>
</template>

<style scoped></style>
```

参考:<https://cn.vuejs.org/guide/essentials/forms.html>

#### 修饰符

#### .lazy

默认情况下，v-model 会在每次 input 事件后更新数据 (IME 拼字阶段的状态例外)。你可以添加 lazy 修饰符来改为在每次 change 事件后更新数据

```vue
<!-- 在 "change" 事件后同步更新而不是 "input" -->
<input v-model.lazy="msg" />

```

#### .number

如果你想让用户输入自动转换为数字，你可以在 v-model 后添加 .number 修饰符来管理输入：

```vue
<input v-model.number="age" />
```

#### .trim

如果你想要默认自动去除用户输入内容中两端的空格，你可以在 v-model 后添加 .trim 修饰符

```vue
<input v-model.trim="name" />
```

### 模板

组件允许我们将 UI 划分为独立的、可重用的部分，并且可以对每个部分进行单独的思考。

```vue
<script setup>
// 导入B
import B from './components/B.vue'
</script>

<template>
// 使用
  <B />
</template>

<style scoped></style>

```

#### 传值

##### 父->子

```vue

// 子
// 父组件传过来的数据,子组件不能变
<script setup>
import A from './A.vue'
import { ref, defineProps } from 'vue'

const { le, list } = defineProps({
    le: {
        type: String, // 接收的参数类型
        default: '默认文字', //默认值
        requires:
    },
    list: {
        type: Array, // 接收的参数类型
        default: [], //默认值
        required: true // 必传
    }
})

</script>

<template>
    <A />
    <p ref="p">{{ le }}</p><br>
    <p ref="p">{{ list }}</p><br>
    <button @click="change">I am B</button><br>
</template>

<style scoped></style>



// 父
<script setup>
import { ref } from 'vue';
import B from './components/B.vue'
let le = ref("B")
let list = ref([1, 2, 3])
</script>

<template>
    //传递参数
  <B :le=le :list='list' />
</template>

<style scoped></style>

```

##### 子->父

###### emit 子->父

在父组件上声明 事件以及相关处理方法，在子组件设置emit.

```vue

// parent
<script setup>
import A from './A.vue'
import { ref, defineProps } from 'vue'

let msg = ref("111222")

const { le, list } = defineProps({
    le: {
        type: String, // 接收的参数类型
        default: '默认文字', //默认值
    },
    list: {
        type: Array, // 接收的参数类型
        default: [], //默认值
        required: true // 必传
    }
})
// 后面p1是接收的参数
function han(p1) {
    console.log(p1)
    console.log("hhhhh")
    msg.value = p1
}
</script>

<template>
    // 设置事件和处理方法
    <A @ChildToPar="han" />
    <p>{{ msg }}</p><br>
    <p>{{ le }}</p><br>
    <p>{{ list }}</p><br>
</template>


// child


<script setup>
import { ref } from 'vue'
const msg = ref('I am A')

//使用方法 ChildToPar与父组件设置的名称相同
const emit = defineEmits(['ChildToPar'])
function change() {

    // 后面111是传递的参数
    emit('ChildToPar', '111')
}
</script>

<template>
    <p ref="p">{{ msg }}</p><br>
    <button @click="change">I am A</button><br>
</template>

<style scoped></style>


```

###### v-model 子->父

使用watch当数值改变了,就通过emit将子组件的数据传递到父组件

```vue
// parent
<script setup>
import A from './A.vue'
import { ref, defineProps } from 'vue'

let msg = ref("111222")

const { le, list } = defineProps({
    le: {
        type: String, // 接收的参数类型
        default: '默认文字', //默认值
    },
    list: {
        type: Array, // 接收的参数类型
        default: [], //默认值
        required: true // 必传
    }
})
// 后面p1是接收的参数
function han(p1, p2) {
    console.log(p1, p2)
    console.log("hhhhh")
    msg.value = p1
}
</script>

<template>
    <A @ChildToPar="han" /><br>
    <p>{{ msg }}</p><br>

    <p>{{ le }}</p><br>
    <p>{{ list }}</p><br>
    <!-- <button @click="change">I am B</button><br> -->
</template>

<style scoped></style>

//child

<script setup>
import { ref, watch } from 'vue'
let msg = ref('I am A')

//使用方法
const emit = defineEmits(['ChildToPar'])
function change() {
    // 后面111是传递的参数
    emit('ChildToPar', '111')
}
watch(msg, async (newQuestion, oldQuestion) => {
    emit('ChildToPar', newQuestion, oldQuestion)
})
</script>

<template>
    <p ref="p">{{ msg }}</p><br>
    <textarea v-model="msg"></textarea><br>
    <button @click="change">I am A</button><br>
</template>

<style scoped></style>
```

##### props 子->父
