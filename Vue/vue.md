Vue使用CDN

```html
<script src="https://unpkg.com/vue/dist/vue.js"></script>
```

### Vue对象的格式

```html
<div id="root">加油，{{name}}</div>
// {{这里可以放表达式变量函数等}}
<script type="text/javascript">  
    //方式一 ，此处是el 和data的
        // 创建vue对象 其中包含 el(某个元素) data(数据)    
        new Vue({        
        // # id选择器        
        // . class选择器        
        el:"#root",        
        data:{          
        name:"Will"        
        },   
        })
    //方式二   使用组件的话data需要写成函数式  
        const v = new Vue({                        
         data: function () {
            return {
                name: "Will",
                url: "https://www.baidu.com"
            }
        },   
        })
        v.$mount("#root")
     //通过这种方法绑定对象
</script>
```

### 模板语法

#### 插值语法

​  将vue的data插入到网页的显示内容中{{ name }}。

#### 指令语法

​  将vue中的数据放到标签。

​  v-bind是单向绑定，即vue对象中data改变了页面中对应的值会改变，但是页面中值改变不会影响data的值。

​  v-model是双向绑定，即是某一方改变之后对应的数据不会变。v-model只能用于输入类的参数。

```html
 // 插值语法
<div id="root">加油，{{name}}<br>
    //指令语法 v-bind:href 也可以简写为:href
    <a v-bind:href="url">linkto</a>
    <a :href="url">linkto</a>
    
    //指令语法 v-model:value="xxx" 输入参数的属性名为value也可以简写为 v-model="xxx"
    <input type="text "v-model:value="url">
    <input type="text "v-model="url">
</div>
```

### MVVM

model ：模型(指数据)

view ：视图

viewmodel：vue中的实例对象。

![1638705603884](C:\Users\will\AppData\Roaming\Typora\typora-user-images\1638705603884.png)

### Object.defineProperty

#### 释义

其作用是为一个对象增添属性，并且设置属性的可删除，可变化等属性，并且可以将属性值与其他的变量进行关联。如果直接将某个变量的值赋予到属性，那么之后该变量的值变化，对应的属性值是不会变化的，但是通过Object.defineProperty中的get 将变量值赋予到属性，变量值会映射到属性。

```html
   const v = new Vue({
        // # id选择器
        // . class选择器
        data: function () {
            return {
                name: "Will",
                url: "https://www.baidu.com"
            }
        },
    })
    v.$mount("#root")



    let age = 22
    let person = {
        name: "will"
    }
    Object.defineProperty(v, "age", {
    /*
    指定三个参数，对象，属性名，属性值相关配置
 value 直接指定值,enumerable 可遍历的默认为false
 writable 是否可改变 默认为false  不能与get同用
 configurable 是否可删除 默认为false
 get()     set(value) 方法 其中value是获取到的变化的值。
    get:funtion(){} 简写为get() 
    */

        // value: 22,
        // enumerable:true,
        // writable:true,
        // configurable:true,
        get:function () {
        //get(){  return xxx}
   //值与变量绑定
            return  age
        },
        set(value){
            console.log(value)
            console.log("modify value")
   //将变化的值在赋值给变量
            age = value
        }
    })
    console.log(person)
```

#### 数据代理

数据代理：通过一个对象完成对另一个对象数据的读写。

在vue对象中，data的数据会在 vm的_data复制一份，然后vue对象中会生成对应的data中的key，

vue通过Object.definePropert添加对应的key，以及get/set完成对_data的数据操作，完成数据代理。

### 事件处理

#### 鼠标事件

##### 基础使用

网页中存在与用户交互，需要处理相关事件，并且处理函数中会默认有event(鼠标事件)，但是如果对事件函数传入了参数，如果还需要使用event则 click($event,par1,par2...),使用$event。如果没有参数可以直接写@click。

事件中@xxx后面也可以写一些简单语句。

如代码中的

```html
<body>
<div id="root">
    <button v-on:click="click">美女荷官</button>
    //也可以简写为@click
    <button v-on:click="click($event,250)">美女荷官</button>
</div>
<script type="text/javascript">
    const v = new Vue({

        data: function () {
            return {
                name: "Will",
                url: "https://www.baidu.com"
            }
        },
        methods:{
            click(event,number){
                alert("666")
            }
        }
    })
    v.$mount("#root")
</script>
</body>
```

##### 事件修饰符

```html
<!-- 阻止单击事件继续传播，例如一个div里有一个button，同时给div button(设置stop)设置点击事件，因为有stop，就不会触发div的点击事件-->
<a @click.stop="doThis"></a>

<!-- 阻止默认行为，例如阻止a链接的跳转-->
<form v-on:submit.prevent="onSubmit"></form>

<!-- 事件只触发一次-->
<button @click.once="click"></button>


<!-- 一个事件开始是从大div到小div的事件捕获，然后再是小div到大div的冒泡事件-->
<!-- 事件捕获，事件捕获先于冒泡发生，如下面的代码，点击button先调用div的click，再调用button的-->
<div class="div" @click.capture="click($event,99)">
    <button @click="click($event,222)">美女荷官</button>
</div>

<!-- 当点击的对象是它自己的时候才触发，如下面情况,当点击div本身而不是button的时候才调用div的click‘-->
<!-- 点击button的target是button，而不是div-->
<div class="div" @click.self="click($event,99)">
    <button @click.once="click($event,222)">美女荷官</button>
</div>

<!-- 先执行事件的默认行为，之后再进行对应的回调-->
<div class="div" @click.passive="click($event,99)">
</div>

<!-- 事件修饰符可以连用-->
<div class="div" @click.prevent.passive="click($event,99)">
</div>
```

#### 键盘事件

键盘事件包括@keyup/@keydown，vue中给常用的按键取了别名，即这个键发生了事件，就会触发函数。

```html
<!-- up/down/right/left -->
<input type="text"  @keyup.up="keyup"><!-- 输入回车-->
<input @kyup.enter="enter">

<!-- backspace 或者delete -->
<input type="text"  @keyup.delete="keyup">

<!-- up/down/right/left -->
<input type="text"  @keyup.up="keyup">

<!-- esc-->
<input type="text"  @keyup.esc="keyup">

<!-- space -->
<input type="text"  @keyup.space="keyup">

<!-- tab 需要注意tab其功能是跳到下一个元素，使用keyup的时候已经是到下一个元素了，目标就成了一个元素-->
<!-- 而此时需要用keydown，-->
<!-- 与tab类似的还有shift,alt,ctrl,meta-->
<input type="text"  @keyup.tab="keyup">

<!-- 想要查看其他键，可以直接将event.key(键名)和event.keyCode(键码) 去做判断 -->
keyup(event) {
    console.log(event.key)
    console.log(event.keyCode)
}

<!-- 键盘按键可以同用，例如下面tab和a同按触发-->
<input type="text"  @keyup.tab.a="keyup">
```

### 计算属性

很多时候需要对vue中的属性进行计算或者组合，就可以使用vue中的计算属性，就可以将其设置在computed中写，写其中的get，然后再网页中像普通属性一样使用计算属性，set中注意的是修改之后要修改关联的属性。

如果不需要用set，那么就可以简写 key(){  return xxx  }.

计算属性再使用第一次之后，会进行缓存，在一个网页使用N次，get方法只会调用一次，并且计算属性中关联到的属性在变化了之后调用get，使得计算属性的值也发生相应的变化。

```html
show:{{ info}}
  
  new Vue({
  data: function () {
      return {
      name: "Will",
      sex: "https://www.baidu.com"
      }
   },
  computed:{
      info:{
          get(){
          return this.name+this.sex
        }
      }
   }
  })
  v.$mount("#root")


//简写
  computed:{
      info(){
  return this,name+this.sex
   }
   }
```

### 侦听属性

#### 基础使用

vue中的数据(包括普通data和计算属性)发生了变化，想要完成对属性的检测，则可以使用watch。

如果需要监视多级属性中的某个数据，例如student.name，想要单独监视它，key需要写为"student.name"。

```html
    const v = new Vue({
        data: function () {
            return {
                name: "Will",
                sex: "男"
            }
        },
        computed: {
            info() {
                return this.name + this.sex
            }
        },
//直接在vue对象中配置watch,监视属性的变化
        watch:{
            name:{
    deep:true,
                handler(newValue,oldValue){
                    console.log(newValue)
                    console.log(oldValue)
                }
            }
        },
    })
    v.$mount("#root")

// 在后面配置配置，传入参数为key,{ handler(){}}
    v.$watch("sex", {handler(newValue, oldValue){
        console.log(newValue)
        console.log(oldValue)
  //逻辑
    }})
```

#### 深度监视

一个数据含有**多个层级**的话，需要监视其中的属性的变化，在该数据的监视中配置一个deep：true，即可开启深度监测。

#### 简写形式

如果不配置deep以及immediately，就可以采用下面的简写形式。

```html
    const v = new Vue({
        data: function () {
            return {
                name: "Will",
                sex: "男"
            }
        },
        computed: {
            info() {
                return this.name + this.sex
            }
        },
        watch:{ 
   //简写
            name(newValue,oldValue){
                    console.log(newValue)
                    console.log(oldValue)
            }
        },
    })
    v.$mount("#root")
 
//简写，后面传入个函数就行。
   v.$watch("sex", function (newValue, oldValue){
        console.log(newValue)
        console.log(oldValue)
        alert("sex changed")
    })
```

#### 对比计算属性和监视属性

监视属性和计算属性(配置一下set)都可以达到改变改变属性的目的。

计算属性中不能开启异步任务返回属性，因为异步任务需要将return写在那个setTiemeout，而这个setTimeout

的对象是windows，而不是vue对象，在其中写return value ，vue对象是拿不到值。

在监听属性中，直接改变其中的属性值，而不是返回给setTimeout的对象。

注意：有些函数式不被vue对象管理的，例如上面的setTiemeout以及ajax等。

### 样式绑定

有的时候需要在事件操作之后完成对网页样式的修改，此时就需要绑定样式。

使用:class,在事件回调中修改对应的属性就行，class的内容可以是单个样式，或者是样式的列表，如["div","root"]，或者是一个字典里面配置true/false代表样式是否显示出来。

更换样式也可以使用标签style，用法类似，设置样式对象就行。

```html
<div :class="xx">
new Vue({
        data: function () {
            return {
                name: "Will",
                sex: "https://www.baidu.com",
       //样式为普通的字符
                style:"root",
       //样式为字典
       classObj:{
       //div 和 root均为class属性
       div:true
       root:false
       },
            }
        },
        methods: {
            keyup() {
                this.style ="div"
                return this.name + this.sex
            }
        },
    })
    v.$mount("#root")
```

### 条件渲染

v-show=表达式 可以控制是否展示，直降元素的display设置为了none。

v-if= 表达式  则是对应的元素都没有。v-else(-if)类似。

使用if else if 结构不能被打断(在v-if  else中加入普通的网页标签)。‘

但是v-if 常与template标签连用。

因为v-if会操作dom元素的修改，所以相对于v-show销量更低一点。

### 列表渲染

使用v-for对数组数据或者对象数据进行遍历。

**建议key不要用index，因为在新增数据破坏了原有数据结构顺序，新数据可能会出错。**

阅读：<https://blog.csdn.net/AiHuanhuan110/article/details/98223011>

```html
// 遍历数组
<ul id="root">
    <li v-for="student,index in students" :key="student.index">
        // 第一个为列表中的元素，第二个为索引值
        {{student.name}}--{{student.sex}}</li>
</ul>


//遍地对象,注意是value key
<li v-for="value,key in student" :key="key">
    
//遍历数字    
<li v-for="number,key in 66" :key="key">
```

 docker run -it -d --name 容器名-p 80:80 images

 COPY ./ ./   #将同属于dockerfile文件夹下的所有东西复制到工作目录
