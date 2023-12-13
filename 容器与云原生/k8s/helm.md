#

## 简介

Helm 可以帮助我们管理 Kubernetes 应用程序 - Helm Charts 可以定义、安装和升级复杂的 Kubernetes 应用程序，Charts 包很容易创建、版本管理、分享和分布。Helm 对于 Kubernetes 来说就相当于 yum 对于 Centos 来说，如果没有 yum 的话，我们在 Centos 下面要安装一些应用程序是极度麻烦的，同样的，对于越来越复杂的 Kubernetes 应用程序来说，如果单纯依靠我们去手动维护应用程序的 YAML 资源清单文件来说，成本也是巨大的。

## helm组件

1. Chart:就是helm的一个整合后的chart包，包含一个应用所有的kubernetes声明模版，类似于yum的rpm包或者apt的dpkg文件
理解:
helm将打包的应用程序部署到k8s,并将它们构建成Chart。这些Chart将所有预配置的应用程序资源以及所有版本都包含在一个易于管理的包中。Helm kubernetes资源(Deployments、Services等)打包到一个Chart中,Chart广被保存到Chart分库。通过Chart分库可用来存情和分享Chart.
2. Helm客户端: helm的客户端组件，负责和k8s apiserver通信
3. Repository:用于发布和存储chart包的仓库，类似yum仓库或docker仓库
4. Release:用Chart包部署的一个实例。通过chart在k8s中部署的应用都会产生一个唯一的Release.同一chart部署多次就会产生多个Release.
    理解:将这些yaml部署完成后，他也会记录部署时候的一个版本，维护了一个release版本状态，通过Release这个实例，他会具体帮我们创建pod，deployment等资源

## helm2 vs helm3

1. helm3移除了Tiller组件helm2中helm客户端和k8s通信是通过Tiller组件和k8s通信,helm3移除了Tiller组件,直接使用kubeconfig文件和k8s的apiserver通信
2. 删除 release 命令变更

```shell
helm delete release-name --purge -------->> helm uninstall release-name
```

3. 查看 charts 信息命令变更

```shell
helm inspect release-name ------------>> helm show
```

4. 拉取 charts 包命令变更

```shell
helm fetch chart-name----->> helm pull chart-name
```

5. helm3中必须指定 release 名称，如果需要生成一个随机名称，需要加选项--generate-name，helm2中如果不指定release名称，可以自动生成一个随机名称

```shell
helm install ./mychart --generate-name
```

## 内置对象

### Release对象

描述了版本发布自身的一些信息。它包含了以下对象
| 对象名称   | 描述            |
| ------ | --------------- |
| .Release.Name   | release 的名称 |
| .Release.Namespace   | release 的命名空间  |
| .Release.IsUpgrade  | 如果当前操作是升级或回滚的话，该值为 true |
| .Release.IsInstall  | 如果当前操作是安装的话，该值为 true |
| .Release.Revision | 获取此次修订的版本号。初次安装时为 1，每次升级或回滚都会递增 |
| .Release.Service  | 获取渲染当前模板的服务名称。一般都是 Helm |

### Chart对象

用于获取Chart.yaml 文件中的内容
Chart.yaml
name: test
info:
    name: test2

获取方式:
.Chart.name
.Chart.info.name

### Values对象

描述的是value.yaml 文件（定义变量的文件）中的内容，默认为空。使用Value 对象可以获取到value.yaml文件中已定义的任何变量数值
values.yaml
name: test
info:
    name: test2

获取方式:
.Values.name
.Values.info.name

### Capabilities 对象

| 对象名称   | 描述            |
| ------ | --------------- |
|.Capabilities.APIVersions | 返回kubernetes集群 API 版本信息集合|
|.Capabilities.APIVersions.Has $version | 用于检测指定的版本或资源在k8s集群中是否可用，例如：apps/v1/Deployment |
|.Capabilities.KubeVersion和.Capabilities.KubeVersion.Version | 都用于获取kubernetes 的版本号 |
|.Capabilities.KubeVersion.Major |  获取kubernetes 的主版本号 |
|.Capabilities.KubeVersion.Minor |获取kubernetes 的小版本号|k

### Template 对象

## 命令

### 创建

```shell
helm create chart-name
chart-name         #chart包的名称
├── Chart.yaml     #保存图表的基本信息，包括名字、描述信息及版本等，这个变量文件都可以被模板目录下文件所引用
├── charts         #存放子图表的目录，目录里存放这个图表依赖的所有子图表
├── templates      #模板文件目录，目录里面存放所有yaml模板文件，包含了所有部署应用的yaml文件
│   ├── NOTES.txt  #存放提示信息的文件，介绍图表帮助信息，螺虫部署后展示给用户。如何使用图表等，是部署图表后给用户的提示信息
│   ├── _helpers.tpl  #放置模板助手的文件，可以在整个chart中重复使用，是放一些templates目录下这些yaml都有可能会用的一些模板
│   ├── deployment.yaml
│   ├── hpa.yaml
│   ├── ingress.yaml
│   ├── service.yaml
│   ├── serviceaccount.yaml
│   └── tests       #用于测试的文件，测试完部署完图表后，如网页，做一个链接，看看你是否部署正常
│       └── test-connection.yaml
└── values.yaml  #用于渲染模板的文件(变量文件，定义变量的值)定义模板目录下的文件可能引用到的变量               #value.yaml用于存储模板目录中模板文件中用到变量的值，这些变量定义都是为了让模板目录下yaml引用
```

### 测试

用于渲染yaml,显示渲染结果,而不真正的作用到集群。

```shell
helm install release-name repo --debug --dry-run
```

### 卸载

```shell
helm uninstall chart-name
```

### 升级

```shell
helm upgrade -f values.yaml release-name path
# helm upgrade -f test/values.yaml test ./test
```

### 回退

```shell
helm rollback chart-name [reversion]
# helm rollback test
# helm rollback test 2
```

### 历史

```shell
helm history chart-name 
# helm history test
```

## helm3内置函数详解

### 内置函数

#### quote/squote

通过向quote或squote函数中传递一个参数，即可为这个参数(调用的变量值)添加一个双引号（quote）或单引号（squote）

```text
data:
value1: {{ quote .Values.name }} #调用的变量值添加一个双引号(quote)
value2: {{ squote .Values.name }} #调用的变量值添加一个单引号(squote)
```

#### upper/lower

使用 upper 和 lower 函数可以分别将字符串转换为大写（upper）和小写字母（lower）的样式

#### repeat

使用default函数指定一个默认值，这样当引入的值不存在时，就可以使用这个默认值

#### default

使用default函数指定一个默认值，这样当引入的值不存在时，就可以使用这个默认值

#### lookup

使用lookup 函数用于在当前的k8s集群中获取一些资源的信息，功能有些类似于 kubectl get ...
函数的格式如下：
lookup "apiVersion" "kind" "namespace" "name" 其中"namespace"和"name" 都是可选的,或可以指定为空字符串"",函数执行完成后会返回特定的资源

```text
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ .Release.Name  }}-cm
  # namespace: {{ .Release.NameSpace }}
data:
  value: {{ .Values.Value }}
  value1: {{ quote .Values.Value }}
  value2: {{ squote .Values.Value }}
  value3: {{ .Values.Value | squote }}
  value4: {{ .Values.Value | quote }}
  value5: {{ .Values.Value | upper }}
  value6: {{ .Values.Value | lower }}
  value7: {{ .Values.Value | repeat 3 }}
  value8: {{ .Values.Value1 | default 333 }}
  value9

# apiVersion: v1
# kind: ConfigMap
# metadata:
#   name: test-cm
#   # namespace: 
# data:
#   value: test
#   value1: "test"
#   value2: 'test'
#   value3: 'test'
#   value4: "test"
#   value5: TEST
#   value6: test
#   value7: testtesttest
#   value8: 333
```

### 逻辑和流控制函数

#### eq

用于判断两个参数是否相等，如果等于则为 true，不等于则为 false。

#### ne

用于判断两个参数是否不相等，如果不等于则为 true，等于则为 false。

#### lt  

lt 函数用于判断第一个参数是否小于第二个参数，如果小于则为 true，如果大于则为 false。

#### le

判断第一个参数是否小于等于第二个参数，如果成立则为 true，如果不成立则为 false。

#### gt

用于判断第一个参数是否大于第二个参数，如果大于则为 true，如果小于则为 false。

#### ge

判断第一个参数是否大于等于第二个参数，如果成立则为 true，如果不成立则为 false。

#### and

返回两个参数的逻辑与结果（布尔值），也就是说如果两个参数为真，则结果为 true。否认哪怕一个为假，则返回false

#### or

判断两个参数的逻辑或的关系，两个参数中有一个为真，则为真。返回第一个不为空的参数或者是返回后一个参数

#### not

 用于对参数的布尔值取反,如果参数是正常参数(非空)，正常为true，取反后就为false，参数是空的,正常是false，取反后是true

#### default

用来设置一个默认值，在参数的值为空的情况下，则会使用默认值

#### empty

用于判断给定值是否为空，如果为空则返回true

#### coalesce

用于扫描一个给定的列表，并返回第一个非空的值。

#### ternary

接受两个参数和一个 test 值，如果test 的布尔值为 true，则返回第一个参数的值，如果test 的布尔值为false，则返回第二个参数的值(){{ ternary "First" "Second" true }}

```text
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ .Release.Name  }}-cm
  # namespace: {{ .Release.NameSpace }}
data:
  value: {{ eq 2 2 }}
  value1: {{ ne 2 2 }}
  value2: {{ lt 3 2 }}
  value3: {{ le 3 2 }}
  value4: {{ gt 3 2 }}
  value5: {{ ge 3 2 }}
  value6: {{ and .Values.Value .Values.Value  }}
  value7: {{ or 1 "" 2 | quote }} #返回1,返回第一个不为空的参数或者是返回后一个参数,并加上双引号(quote ) 
  value8: {{ or 1 2 "" | quote }} #返回1,返回第一个不为空的参数或者是返回后一个参数,并加上双引号(quote ) 
  value9: {{ or "" 2 3 | quote }} #返回2,返回第一个不为空的参数或者是返回后一个参数,并加上双引号(quote ) 
  value10: {{ or "" "" 3 | quote }} #返回3,返回第一个不为空的参数或者是返回后一个参数,并加上双引号(quote ) 
  value11: {{ or "" "" "" | quote }}
  value12: {{ .Values.address | default "bj" | quote }} 
  bool1: {{ not 2 | quote }} #用于对参数的布尔值取反,并加上双引号(quote ) 
  bool2: {{ not "" | quote }} #用于对参数的布尔值取反,并加上双引号(quote ) 
  bool3: {{ 0 | empty }} #用于判断给定值是否为空，如果为空则返回true，0是空值
  bool4: {{ 1 | empty }} #用于判断给定值是否为空，如果为空则返回true 
  bool5: {{ "" | empty }} #用于判断给定值是否为空，如果为空则返回true，""是空值
  bool6: {{ false | empty }} #用于判断给定值是否为空，如果为空则返回true，false是空值
  type1: {{ coalesce 0 1 2 }} #用于扫描一个给定的列表，并返回第一个非空的值
  type2: {{ coalesce "" false "Test" }} #用于扫描一个给定的列表，并返回第一个非空的值
  type3: {{ ternary "First" "Second" true }} #接受两个参数和一个 test值,如果test的布尔值为true,则返回第一个参数的值
  type4: {{ ternary "First" "Second" false }} #接受两个参数和一个 test值,如果test的布尔值为false,则返回第二个参数的值
# apiVersion: v1
# kind: ConfigMap
# metadata:
#   name: test-cm
#   # namespace: 
# data:
#   value: true
#   value1: false
#   value2: false
#   value3: false
#   value4: true
#   value5: true
#   value6: test
#   value7: "1" #返回1,返回第一个不为空的参数或者是返回后一个参数,并加上双引号(quote ) 
#   value8: "1" #返回1,返回第一个不为空的参数或者是返回后一个参数,并加上双引号(quote ) 
#   value9: "2" #返回2,返回第一个不为空的参数或者是返回后一个参数,并加上双引号(quote ) 
#   value10: "3" #返回3,返回第一个不为空的参数或者是返回后一个参数,并加上双引号(quote ) 
#   value11: ""
#   value12: "bj" 
#   bool1: "false" #用于对参数的布尔值取反,并加上双引号(quote ) 
#   bool2: "true" #用于对参数的布尔值取反,并加上双引号(quote ) 
#   bool3: true #用于判断给定值是否为空，如果为空则返回true，0是空值
#   bool4: false #用于判断给定值是否为空，如果为空则返回true 
#   bool5: true #用于判断给定值是否为空，如果为空则返回true，""是空值
#   bool6: true #用于判断给定值是否为空，如果为空则返回true，false是空值
#   type1: 1 #用于扫描一个给定的列表，并返回第一个非空的值
#   type2: Test #用于扫描一个给定的列表，并返回第一个非空的值
#   type3: First #接受两个参数和一个 test值,如果test的布尔值为true,则返回第一个参数的值
#   type4: Second #接受两个参数和一个 test值,如果test的布尔值为false,则返回第二个参数的值
```

### 字符串函数

#### print 和 println函数

#### printf函数

#### trim函数

可以用来去除字符串两边的空格，示例：trim " hello "

#### trimAll函数

 用于移除字符串中指定的字符，示例：trimAll "$" "$5.00"

#### trimPrefix 和 trimSuffix 函数

分别用于移除字符串中指定的前缀和后缀：示例1：trimPrefix "-" "-hello" 示例2：trimSuffix "+" "hello+"

#### lower函数

用于将所有字母转换成小写，示例1：lower "HELLO"

#### upper函数

 用于将所有字母转换成大写，示例2：upper "hello"

#### title函数

 用于将首字母转换成大写，示例3：title "test"

#### untitle函数

用于将大写的首字母转换成小写，示例4：untitle "Test"

#### snakecase函数、camelcase函数 和 kebabcase函数

#### snakecase函数

用于将驼峰写法转换为下划线命名写法， 示例：snakecase "UserName" # 返回结果 user_name

#### camelcase函数

用于将下划线命名写法转换为驼峰写法，示例：camelcase "user_name" # 返回结果 UserName

#### kebabcase函数

用于将驼峰写法转换为中横线写法，示例：kebabcase "UserName" # 返回结果 user-name

#### swapcase函数

作用是基于内置的算法来切换字符串的大小写
算法规则如下：

1. 大写字符变成小写字母
2. 首字母变成小写字母
3. 空格后或开头的小写字母转换成大写字母
4. 其他小写字母转换成大写字母
示例：swapcase "This Is A.Test" # 返回结果："tHIS iS a.tEST"

#### substr函数

用于切割字符串（指定切割起、始位置），并且返回切割后的字串.
start (int)：起始位置，索引位置从0开始
end (int)：结束位置，索引位置从0开始
string (string)：需要切割的字符串
示例：substr 3 5 "message" #返回结果 "sa"

#### trunc函数

trunc 可以使用正整数或负整数来分别表示从左向右截取的个数和从右向左截取的个数
示例：trunc 5 "Hello World" # 返回结果："Hello"
示例：trunc -5 "Hello World" # 返回结果："World"

#### abbrev函数

作用是使用省略号（...）切割字符串，保留指定的长度，注意省略号的长度是3个。其中省略号也是计算在长度之内的。
作用是使用省略号（...）切割字符串，保留指定的长度，注意省略号的长度是3个。其中省略号也是计算在长度之内的。

#### randAlphaNum函数

randAlphaNum： 使用 0-9a-zA-Z，生成随机字符串,需要传递一个参数用于指定生成的字符串长度

#### randAlpha函数

使用 a-zA-Z，生成随机字符串,需要传递一个参数用于指定生成的字符串长度

#### randNumeric函数

使用 0-9，生成随机字符串,需要传递一个参数用于指定生成的字符串长度

#### randAscii 函数

使用所有的可使用的 ASCII 字符，生成随机字符串,需要传递一个参数用于指定生成的字符串长度

#### contains函数

用于测试一个字符串是否包含在另一个字符串里面，返回布尔值，true或false，包含返回true，不包含返回false
示例：contains "llo" "Hello" # 结果返回 true

#### hasPrefix函数 和 hasSuffix函数

这两个函数用于测试一个字符串是否是指定字符串的前缀或者后缀,返回布尔值,true或false,包含返回true,不包含返回false
示例：hasPrefix "He" "Hello" # 判断前缀，是前缀，结果返回 true
示例：hasSuffix "le" "Hello" # 判断后缀，不是后缀，结果返回 false

#### repeat函数

repeat函数用于将字符串重复输出指定的次数 示例：repeat 3 "Hello" # 结果返回 HelloHelloHello

#### nospace函数

nospace函数用于去掉字符串中所有的空格 示例：nospace "T e s t" # 返回 Test

#### initials 函数

initials函数用于截取指定字符串的每个单词的首字母，并拼接在一起 示例：initials "People Like Peace" # 返回 PLP

#### wrapWith函数

作用是在文档中在指定的列数添加内容，例如添加内容: "\t"
示例：wrapWith 5 " " "HelloWorld", 会在第五个索引的位置添加" "，所以结果为："Hello World"

#### quote函数 和 squote 函数

该函数将字符串用双引号（quote） 或者单引号（squote）括起来

#### cat 函数

用于将多个字符串合并成一个字符串，并使用空格分隔开
示例：cat "Hello" "World" , 结果: Hello World

#### replace函数

用于执行简单的字符串替换。该函数需要传递三个参数:待替换的字符串、将要替换的字符串、源字符串
第1个参数： 待替换的字符串
第2个参数： 将要替换的字符串
第3个参数： 源字符串
示例："I Am Test" | replace " " "-" # 返回结果：I-Am-Test

#### shuffle函数

用于对字符串中的字符进行重新排序,是基于他内部的一个算法

```text
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ .Release.Name  }}-cm
  # namespace: {{ .Release.NameSpace }}
data:
  data1: {{ trim " Test " }} #trim函数可以用来去除字符串两边的空格
  data2: {{ trimAll "%" "%Test" }} #trimAll函数用于移除字符串中指定的字符，此处指定的字符为"%"
  data3: {{ trimPrefix "-" "-hello" }} #trimPrefix函数用于移除字符串中指定的前缀，此处指定的前缀是:"-"
  data4: {{ trimSuffix "+" "hello+" }} #trimSuffix函数用于移除字符串中指定的后缀，此处指定的后缀是:"+"
  data5: {{ lower "HELLO" }} #lower函数用于将所有字母转换成小写
  data6: {{ upper "hello" }} #upper函数用于将所有字母转换成大写
  data7: {{ title "test" }} #title函数用于将首字母转换成大写
  data8: {{ untitle "Test" }} #untitle函数用于将大写的首字母转换成小写
  data10: {{ snakecase "UserName" }} #snakecase函数,用于将驼峰写法转换为下划线命名写法,返回结果 user_name
  data11: {{ camelcase "user_name" }} #camelcase函数,用于将下划线命名写法转换为驼峰写法,返回结果 UserName
  data12: {{ kebabcase "UserName" }} #kebabcase函数,用于将驼峰写法转换为中横线写法,返回结果 user-name
  data13: {{ swapcase "This Is A.Test" }} #作用是基于内置的算法来切换字符串的大小写,返回结果："tHIS iS a.tEST"
  data14: {{ substr 3 5 "message" }}
  data15: {{ trunc 5 "Hello World" }} #函数用于截断字符串,从左向右截取5个,返回结果："Hello"
  data16: {{ trunc -5 "Hello World" }} #函数用于截断字符串,从右向左截取5个,返回结果："World"
  data17: {{ abbrev 5 "Hello World" }}
  data18: {{ randAlphaNum 10 }} #randAlphaNum函数：使用 0-9a-zA-Z，生成随机字符串
  data19: {{ randAlpha 10 }} #randAlpha函数： 使用 a-zA-Z，生成随机字符串
  data20: {{ randNumeric 10 }} #randNumeric函数： 使用 0-9，生成随机字符串
  data21: {{ randAscii 10 }} #randAscii函数： 使用所有的可使用的 ASCII 字符，生成随机字符串
  data22: {{ contains "llo" "Hello" }}
  data23: {{ hasPrefix "He" "Hello" }} #测试一个字符串是否是指定字符串的前缀,返回布尔值,true或false,结果:true
  data24: {{ hasSuffix "le" "Hello" }} #测试一个字符串是否是指定字符串的后缀,返回布尔值,true或false,结果:false
  data25: {{ repeat 3 "Hello" }} #repeat函数用于将字符串重复输出指定的次数,结果: HelloHelloHello
  data26: {{ nospace "T e s t" }} #nospace函数用于去掉字符串中所有的空格
  data27: {{ initials "People Like Peace" }} #initials函数用于截取指定字符串的每个单词的首字母,并拼接在一起,结果:PLP
  data28: {{ wrapWith 5 " " "HelloWorld" }} 
  data29: {{ cat "Hello" "World" }} 
  data30: {{ replace " " "-" "I Am Test"}} 

apiVersion: v1
kind: ConfigMap
metadata:
  name: test-cm
  # namespace: 
data:
  data1: Test #trim函数可以用来去除字符串两边的空格
  data2: Test #trimAll函数用于移除字符串中指定的字符，此处指定的字符为"%"
  data3: hello #trimPrefix函数用于移除字符串中指定的前缀，此处指定的前缀是:"-"
  data4: hello #trimSuffix函数用于移除字符串中指定的后缀，此处指定的后缀是:"+"
  data5: hello #lower函数用于将所有字母转换成小写
  data6: HELLO #upper函数用于将所有字母转换成大写
  data7: Test #title函数用于将首字母转换成大写
  data8: test #untitle函数用于将大写的首字母转换成小写
  data10: user_name #snakecase函数,用于将驼峰写法转换为下划线命名写法,返回结果 user_name
  data11: UserName #camelcase函数,用于将下划线命名写法转换为驼峰写法,返回结果 UserName
  data12: user-name #kebabcase函数,用于将驼峰写法转换为中横线写法,返回结果 user-name
  data13: tHIS iS a.tEST #作用是基于内置的算法来切换字符串的大小写,返回结果："tHIS iS a.tEST"
  data14: sa
  data15: Hello #函数用于截断字符串,从左向右截取5个,返回结果："Hello"
  data16: World #函数用于截断字符串,从右向左截取5个,返回结果："World"
test/helm » helm upgrade -f test/values.yaml test ./test --debug --dry-run
upgrade.go:150: [debug] preparing upgrade for test
upgrade.go:158: [debug] performing update for test
upgrade.go:321: [debug] dry run for test
Release "test" has been upgraded. Happy Helming!
NAME: test
LAST DEPLOYED: Mon Dec 11 22:40:48 2023
NAMESPACE: default
STATUS: pending-upgrade
REVISION: 7
TEST SUITE: None
USER-SUPPLIED VALUES:
Image:
  Repo: I am a repo
Value: test

COMPUTED VALUES:
Image:
  Repo: I am a repo
Value: test

HOOKS:
MANIFEST:
---
# Source: test/templates/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: test-cm
  # namespace: 
data:
  data1: Test #trim函数可以用来去除字符串两边的空格
  data2: Test #trimAll函数用于移除字符串中指定的字符，此处指定的字符为"%"
  data3: hello #trimPrefix函数用于移除字符串中指定的前缀，此处指定的前缀是:"-"
  data4: hello #trimSuffix函数用于移除字符串中指定的后缀，此处指定的后缀是:"+"
  data5: hello #lower函数用于将所有字母转换成小写
  data6: HELLO #upper函数用于将所有字母转换成大写
  data7: Test #title函数用于将首字母转换成大写
  data8: test #untitle函数用于将大写的首字母转换成小写
  data10: user_name #snakecase函数,用于将驼峰写法转换为下划线命名写法,返回结果 user_name
  data11: UserName #camelcase函数,用于将下划线命名写法转换为驼峰写法,返回结果 UserName
  data12: user-name #kebabcase函数,用于将驼峰写法转换为中横线写法,返回结果 user-name
  data13: tHIS iS a.tEST #作用是基于内置的算法来切换字符串的大小写,返回结果："tHIS iS a.tEST"
  data14: sa
  data15: Hello #函数用于截断字符串,从左向右截取5个,返回结果："Hello"
  data16: World #函数用于截断字符串,从右向左截取5个,返回结果："World"
  data17: He...
  data18: mVqJFnToii #randAlphaNum函数：使用 0-9a-zA-Z，生成随机字符串
  data19: ZusJPDTZan #randAlpha函数： 使用 a-zA-Z，生成随机字符串
  data20: 2117484970 #randNumeric函数： 使用 0-9，生成随机字符串
  data21: 9#$%~>bMRB #randAscii函数： 使用所有的可使用的 ASCII 字符，生成随机字符串
  data22: true
  data23: true #测试一个字符串是否是指定字符串的前缀,返回布尔值,true或false,结果:true
  data24: false #测试一个字符串是否是指定字符串的后缀,返回布尔值,true或false,结果:false
  data25: HelloHelloHello #repeat函数用于将字符串重复输出指定的次数,结果: HelloHelloHello
  data26: Test #nospace函数用于去掉字符串中所有的空格
  data27: PLP #initials函数用于截取指定字符串的每个单词的首字母,并拼接在一起,结果:PLP
  data28: Hello World 
  data29: Hello World 
  data30: I-Am-Test
```

### 类型转换

#### atoi函数

将字符串转换为整型

#### float64函数

 转换成 float64 类型

#### int函数

 转换为 int 类型

#### toString函数

 转换成字符串

#### int64函数

转换成 int64 类型

#### toDecimal函数

将 unix 八进制转换成 int64

#### toStrings函数

 将列表、切片或数组转换成字符串列表

#### toJson函数 (mustToJson)

将列表、切片、数组、字典或对象转换成JSON

#### toPrettyJson函数 (mustToPrettyJson)

 将列表、切片、数组、字典或对象转换成格式化JSON

#### toRawJson函数(mustToRawJson)

 将列表、切片、数组、字典或对象转换成JSON（HTML字符不转义）

```text
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ .Release.Name  }}-cm
  # namespace: {{ .Release.NameSpace }}
data:
  data1: {{ "16" | kindOf }}
  data2: {{ 16 | kindOf }} 
  data3: {{ atoi "16" | kindOf }} 
  data4: {{ float64 "16.0" | kindOf }} 
  data6: {{ toString 16 | kindOf }} 

apiVersion: v1
kind: ConfigMap
metadata:
  name: test-cm
  # namespace: 
data:
  data1: string
  data2: int 
  data3: int 
  data4: float64 
  data6: string
```

### 正则表达式函数

#### regexFind函数 和 mustRegexFind函数

regexMatch函数 和 mustRegexMatch函数 用于根据指定的正则来匹配字符串,如果匹配成功则返回true.
如果表达式有问题,regexMatch会直接抛出错误,mustRegexMatch会向模板引擎返回错误。
示例：regexMatch "^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$" "<test@xxx.com>" #正则表达式是一个邮箱地址的格式，能匹配到，返回:true

#### regexFindAll函数 和 mustRegexFindAll函数

用于获取字符串中匹配正则表达式的所有子字符串内容,并且在该函数的最后指定一个整型来表示返回多少个正则匹配的字符串。-1 代表返回所有正则匹配的结果

#### regexMatch函数 和 mustRegexMatch函数

regexMatch函数 和 mustRegexMatch函数 用于根据指定的正则来匹配字符串,如果匹配成功则返回true.
如果表达式有问题,regexMatch会直接抛出错误,mustRegexMatch会向模板引擎返回错误。
示例：regexMatch "^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$" "<test@xxx.com>" #正则表达式是一个邮箱地址的格式，能匹配到，返回:true

#### regexReplaceAll函数 和 mustRegexReplaceAll函数

在替换字符串里面，$ 符号代表拓展符号，$1 代表正则表达式的第一个分组
示例：regexReplaceAll "a(x*)b" "-ab-axxb-" "${1}W" #正则含义: a为前缀,b为后缀,中间有多个x

#### regexReplaceAllLiteral函数 和 mustRegexReplaceAllLiteral函数

将通过正则匹配到的内容，替换成其他内容
regexReplaceAllLiteral 和 mustRegexReplaceAllLiteral函数的用法 和 regexReplaceAll函数/mustRegexReplaceAll函数 其实差不多
不同的是: regexReplaceAllLiteral 和 mustRegexReplaceAllLiteral函数中不包括$拓展,也就是说会将$也视作字符串直接替换

#### regexSplit函数 和 mustRegexSplit函数

作用都是指定一个分隔符(以正则表达式匹配的内容为分隔符),将字符串进行切割，并返回切割后的字符串切片
在函数的最后需要指定一个整型，来确定要返回的切片数量，-1 代表返回所有的切片
示例：regexSplit "z+" "pizza" -1 #正则表达式含义: 可以匹配1-多个z， 匹配到正则的内容，

```text
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ .Release.Name  }}-cm
  # namespace: {{ .Release.NameSpace }}
data:
  data1: {{ regexReplaceAll "ab" "-ab-ab-axxb-" "W" }} #将匹配到的正则形式的ab,替换成W
  data2: {{ regexReplaceAll "a(x*)b" "-ab-axxb-" "W" }} #将匹配到的正则形式的:前缀为:a,后缀为b,中间n个x的(包括没有x的),都替换成W
  data3: {{ regexReplaceAll "a(x*)b" "-axb-axxb-" "W" }} #将匹配到的正则形式的:前缀为:a,后缀为b,中间n个x的(包括没有x的),都替换成W
  data4: {{ regexReplaceAll "a(x*)b" "-ab-axxb-" "${1}W" }} #$1代表正则表达式的第一个分组(第一个括号里的:(x*)),$1的值会保留,其他匹配到正则的都替换为W 
  data5: {{ mustRegexReplaceAll "ab" "-ab-ab-axxb-" "W" }} #将匹配到的正则形式的ab,替换成W
  data6: {{ mustRegexReplaceAll "a(x*)b" "-ab-axxb-" "W" }} #将匹配到的正则形式的:前缀为:a,后缀为b,中间n个x的(包括没有x的),都替换成W
  data7: {{ mustRegexReplaceAll "a(x*)b" "-axb-axxb-" "W" }} #将匹配到的正则形式的:前缀为:a,后缀为b,中间n个x的(包括没有x的),都替换成W
  data8: {{ mustRegexReplaceAll "a(x*)b" "-ab-axxb-" "${1}W" }} #$1代表正则表达式的第一个分组((x*)),$1的值会保留,其他匹配到正则的都替换为W 
  data9: {{ regexFindAll "[2,4,6,8]" "123456789" 3 | quote }} #在给的字符串中,匹配正则表达式的所有子字符串内容,并指定返回3个字符串,加双引号quote
  data10: {{ regexFindAll "[2,4,6,8]" "123456789" -1 | quote }} #在给的字符串中,匹配正则表达式的所有子字符串内容,-1代表返回所有正则匹配的结果
  data11: {{ mustRegexFindAll "[2,4,6,8]" "123456789" 3 | quote }} #在给的字符串中,匹配正则表达式的所有子字符串内容,并指定返回3个字符串,加双引号quote
  data12: {{ mustRegexFindAll "[2,4,6,8]" "123456789" -1 | quote }} #在给的字符串中,匹配正则表达式的所有子字符串内容,-1代表返回所有正则匹配的结果
  data13: {{ regexReplaceAll "ab" "-ab-ab-axxb-" "W" }} #将匹配到的正则形式的ab,替换成W
  data14: {{ regexReplaceAll "a(x*)b" "-ab-axxb-" "W" }} #将匹配到的正则形式的:前缀为:a,后缀为b,中间n个x的(包括没有x的),都替换成W
  data15: {{ regexReplaceAll "a(x*)b" "-axb-axxb-" "W" }} #将匹配到的正则形式的:前缀为:a,后缀为b,中间n个x的(包括没有x的),都替换成W
  data16: {{ regexReplaceAll "a(x*)b" "-ab-axxb-" "${1}W" }} #$1代表正则表达式的第一个分组(第一个括号里的:(x*)),$1的值会保留,其他匹配到正则的都替换为W 
  data17: {{ mustRegexReplaceAll "ab" "-ab-ab-axxb-" "W" }} #将匹配到的正则形式的ab,替换成W
  data18: {{ mustRegexReplaceAll "a(x*)b" "-ab-axxb-" "W" }} #将匹配到的正则形式的:前缀为:a,后缀为b,中间n个x的(包括没有x的),都替换成W
  data19: {{ mustRegexReplaceAll "a(x*)b" "-axb-axxb-" "W" }} #将匹配到的正则形式的:前缀为:a,后缀为b,中间n个x的(包括没有x的),都替换成W
  data20: {{ mustRegexReplaceAll "a(x*)b" "-ab-axxb-" "${1}W" }} #$1代表正则表达式的第一个分组((x*)),$1的值会保留,其他匹配到正则的都替换为W 
  data21: {{ regexMatch "^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$" "test@xxx.com" }} #正则表达式是邮箱格式,能匹配到,结果返回:true
  data22: {{ mustRegexMatch "^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$" "test@xxx.com" }} #正则表达式是邮箱格式,能匹配到,结果返回:true
  data23: {{ regexReplaceAllLiteral "ab" "-ab-ab-axxb-" "W" }} #将匹配到的正则形式的ab,替换成W
  data24: {{ regexReplaceAllLiteral "a(x*)b" "-ab-axxb-" "W" }} #将匹配到的正则形式的:前缀为:a,后缀为b,中间n个x的(包括没有x的),都替换成W
  data25: {{ regexReplaceAllLiteral "a(x*)b" "-axb-axxb-" "W" }} #将匹配到的正则形式的:前缀为:a,后缀为b,中间n个x的(包括没有x的),都替换成W
  data26: {{ regexReplaceAllLiteral "a(x*)b" "-ab-axxb-" "${1}W" }} #第一个分组(第一个括号里的:(x*)),$1的值不会保留,匹配到正则的都替换为${1}W 
  data27: {{ mustRegexReplaceAllLiteral "ab" "-ab-ab-axxb-" "W" }} #将匹配到的正则形式的ab,替换成W
  data28: {{ mustRegexReplaceAllLiteral "a(x*)b" "-ab-axxb-" "W" }} #将匹配到的正则形式的:前缀为:a,后缀为b,中间n个x的(包括没有x的),都替换成W
  data29: {{ mustRegexReplaceAllLiteral "a(x*)b" "-axb-axxb-" "W" }} #将匹配到的正则形式的:前缀为:a,后缀为b,中间n个x的(包括没有x的),都替换成W
  data30: {{ mustRegexReplaceAllLiteral "a(x*)b" "-ab-axxb-" "${1}W" }} #第一个分组(第一个括号里的:(x*)),$1的值不会保留,匹配到正则的都替换为${1}W
  data31: {{ regexSplit "z+" "pizza" -1 | quote }} #以正则表达式的内容为分隔符,即以zz为分隔符,默认返回的是数组,将双引号quote转成字符串类型
  data32: {{ mustRegexSplit "z+" "pizza" -1 |quote }} #以正则表达式的内容为分隔符,即以zz为分隔符,默认返回的是数组,将双引号quote转成字符串类型

apiVersion: v1
kind: ConfigMap
metadata:
  name: test-cm
data:
  data1: -W-W-axxb- #将匹配到的正则形式的ab,替换成W
  data2: -W-W- #将匹配到的正则形式的:前缀为:a,后缀为b,中间n个x的(包括没有x的),都替换成W
  data3: -W-W- #将匹配到的正则形式的:前缀为:a,后缀为b,中间n个x的(包括没有x的),都替换成W
  data4: -W-xxW- #$1代表正则表达式的第一个分组(第一个括号里的:(x*)),$1的值会保留,其他匹配到正则的都替换为W 
  data5: -W-W-axxb- #将匹配到的正则形式的ab,替换成W
  data6: -W-W- #将匹配到的正则形式的:前缀为:a,后缀为b,中间n个x的(包括没有x的),都替换成W
  data7: -W-W- #将匹配到的正则形式的:前缀为:a,后缀为b,中间n个x的(包括没有x的),都替换成W
  data8: -W-xxW- #$1代表正则表达式的第一个分组((x*)),$1的值会保留,其他匹配到正则的都替换为W 
  data9: "[2 4 6]" #在给的字符串中,匹配正则表达式的所有子字符串内容,并指定返回3个字符串,加双引号quote
  data10: "[2 4 6 8]" #在给的字符串中,匹配正则表达式的所有子字符串内容,-1代表返回所有正则匹配的结果
  data11: "[2 4 6]" #在给的字符串中,匹配正则表达式的所有子字符串内容,并指定返回3个字符串,加双引号quote
  data12: "[2 4 6 8]" #在给的字符串中,匹配正则表达式的所有子字符串内容,-1代表返回所有正则匹配的结果
  data13: -W-W-axxb- #将匹配到的正则形式的ab,替换成W
  data14: -W-W- #将匹配到的正则形式的:前缀为:a,后缀为b,中间n个x的(包括没有x的),都替换成W
  data15: -W-W- #将匹配到的正则形式的:前缀为:a,后缀为b,中间n个x的(包括没有x的),都替换成W
  data16: -W-xxW- #$1代表正则表达式的第一个分组(第一个括号里的:(x*)),$1的值会保留,其他匹配到正则的都替换为W 
  data17: -W-W-axxb- #将匹配到的正则形式的ab,替换成W
  data18: -W-W- #将匹配到的正则形式的:前缀为:a,后缀为b,中间n个x的(包括没有x的),都替换成W
  data19: -W-W- #将匹配到的正则形式的:前缀为:a,后缀为b,中间n个x的(包括没有x的),都替换成W
  data20: -W-xxW- #$1代表正则表达式的第一个分组((x*)),$1的值会保留,其他匹配到正则的都替换为W 
  data21: true #正则表达式是邮箱格式,能匹配到,结果返回:true
  data22: true #正则表达式是邮箱格式,能匹配到,结果返回:true
  data23: -W-W-axxb- #将匹配到的正则形式的ab,替换成W
  data24: -W-W- #将匹配到的正则形式的:前缀为:a,后缀为b,中间n个x的(包括没有x的),都替换成W
  data25: -W-W- #将匹配到的正则形式的:前缀为:a,后缀为b,中间n个x的(包括没有x的),都替换成W
  data26: -${1}W-${1}W- #第一个分组(第一个括号里的:(x*)),$1的值不会保留,匹配到正则的都替换为${1}W 
  data27: -W-W-axxb- #将匹配到的正则形式的ab,替换成W
  data28: -W-W- #将匹配到的正则形式的:前缀为:a,后缀为b,中间n个x的(包括没有x的),都替换成W
  data29: -W-W- #将匹配到的正则形式的:前缀为:a,后缀为b,中间n个x的(包括没有x的),都替换成W
  data30: -${1}W-${1}W- #第一个分组(第一个括号里的:(x*)),$1的值不会保留,匹配到正则的都替换为${1}W
  data31: "[pi a]" #以正则表达式的内容为分隔符,即以zz为分隔符,默认返回的是数组,将双引号quote转成字符串类型
  data32: "[pi a]" #以正则表达式的内容为分隔符,即以zz为分隔符,默认返回的是数组,将双引号quote转成字符串类型
```

### 加密函数

#### sha1sum 函数

#### sha256sum 函数

用于计算字符串的SHA256值进行加密

#### adler32sum 函数

用于计算字符串的Adler-32校验和进行加密

#### htpasswd 函数

可以根据传入的username和password生成一个密码的bcrypt 哈希值,可以用于HTTP Server的基础认证

#### encryptAES 函数

加密函数，使用AES-256 CBC 加密文本并返回一个base64编码字符串

#### decryptAES 函数

解密函数，接收一个AES-256 CBC编码的字符串并返回解密文本

#### b64enc编码函数

b64enc编码函数和b64dec解码函数：编码或解码 Base64

#### b64dec解码函

b64enc编码函数和b64dec解码函数：编码或解码 Base64
编写k8s的secret文件时候会用到

```text
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ .Release.Name  }}-cm
  # namespace: {{ .Release.NameSpace }}
data:
  data1: {{ sha1sum "hello world" }} #sha1sum函数:用于计算字符串的SHA1值进行加密
  data2: {{ sha256sum "hello world" }} #sha256sum函数:用于计算字符串的SHA256值进行加密
  data3: {{ adler32sum "hello world" }} #adler32sum函数:用于计算字符串的Adler-32校验和进行加密
  data4: {{ htpasswd "user1" "123456" }} #htpasswd函数:可以根据传入的username和password生成一个密码的bcrypt 哈希值,可以用于HTTP Server的基础认证
  data5: {{ encryptAES "testkey" "hello" }}
  data6: {{ decryptAES "testkey" "Imwqlmo/uJws0pvSXx0kLG83Hd2linIn6KMT6IYfvAw=" }} 
  data7: {{ "test" | b64enc }}
  data8: {{ "dGVzdA==" | b64dec }} 

apiVersion: v1
kind: ConfigMap
metadata:
  name: test-cm
  # namespace: 
data:
  data1: 2aae6c35c94fcfb415dbe95f408b9ce91ee846ed #sha1sum函数:用于计算字符串的SHA1值进行加密
  data2: b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9 #sha256sum函数:用于计算字符串的SHA256值进行加密
  data3: 436929629 #adler32sum函数:用于计算字符串的Adler-32校验和进行加密
  data4: user1:$2a$10$VZkG/ZvP1DxadDxnlRYenOXXlHArzNT7ThnzgrJ1Q8Gn4NJDB.euG #htpasswd函数:可以根据传入的username和password生成一个密码的bcrypt 哈希值,可以用于HTTP Server的基础认证
  data5: vzB7V88CBh/uIXgHTmGImRmeGPgmnOzfLiYYr1KcbQo=
  data6: hello 
  data7: dGVzdA==
  data8: test
```

### 日期函数

#### now函数

用于返回当前日期和时间，通常与其他日期函数共同使用

#### date函数

用于将日期信息进行格式化。date 函数后面需要指明日期的格式，这个格式内容必须使用"2006-01-02" 或 "02/01/2006" 来标明，否则会出错.
示例：now | date "2006-01-02" 或 now | date "02/01/2006" 注意: 格式内容必须是这两个示例的内容，内容换成其他日期都不行。

#### dateInZone函数

用法与date函数基本一致，只不过dataInZone函数可以指定时区返回时间，如:指定UTC时区返回时间
示例：dateInZone "2006-01-02" (now) "UTC" #指定UTC时区返回时间
duration函数：该函数可以将给定的秒数转换为golang 中的time.Duration类型，例如指定 95秒可以返回1m35s,秒数必须需要使用双引号,否则会返回 0s

#### duration函数

该函数可以将给定的秒数转换为golang 中的time.Duration类型，例如指定 95秒可以返回1m35s,秒数必须需要使用双引号,否则会返回 0s

#### durationRound函数

durationRound函数用于将给定的日期进行取整，保留最大的单位
示例：durationRound "2h10m5s" #结果: 2h

#### unixEpoch函数

用于返回给定时间的时间戳格式

示例：now | unixEpoch
dateModify和mustDateModify函数:这两个函数用于将一个给定的日期修改一定的时间,并返回修改后的时间
区别是: 如果修改格式错误,dateModify会返回日期未定义.而mustDateModify会返回错误

#### dateModify函数 和 mustDateModify函数

这两个函数用于将一个给定的日期修改一定的时间,并返回修改后的时间
区别是: 如果修改格式错误,dateModify会返回日期未定义.而mustDateModify会返回错误

#### toDate函数 和 mustToDate函数

这两个函数都是用于将字符串转换成日期,第一个参数需要指明要转成的日期格式,第二个参数需要传递要转换的日期字符串
区别是：如果字符串无法转换,toDate函数就会返回0值。mustToDate 函数无法转换时会抛出错误

```text
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ .Release.Name  }}-cm
  # namespace: {{ .Release.NameSpace }}
data:
  data1: {{ now | unixEpoch }} #unixEpoch函数:用于返回给定时间的时间戳格式 
  data2: {{ now | date_modify "-2h" }} #将当前的时间减去2h再返回
  data3: {{ now | mustDateModify "-2h" }} #将当前的时间减去2h再返回
  date4: {{ toDate "2006-01-02" "2017-12-31" }} #将后面的字符串以前面的格式进行转换输出
  date5: {{ mustToDate "2006-01-02" "2017-12-31" }} #将后面的字符串以前面的日期格式进行转换输出
  data6: {{ now }} #now函数:用于返回当前日期和时间,通常与其他日期函数共同使用
  data7: {{ now | date "2006-01-02" }} #date函数:用于将日期信息进行格式化,date函数后面需要指明日期的格式
  #这个格式内容必须使用"2006-01-02"或"02/01/2006"来标明
  data8: {{ dateInZone "2006-01-02" (now) "UTC" }} #dateInZone函数:用法与date函数基本一致,只不过dataInZone函数可以指定时区返回时间
  data9: {{ duration "95" }} #该函数可将给定的秒数转换为golang中的time.Duration类型,如:指定95秒可返回1m35s,秒数必须需要使用双引号,否则会返回0s 
  data10: {{ durationRound "2h10m5s" }} #结果:2h,durationRound函数用于将给定的日期进行取整,保留最大的单位 
  data11: {{ now }} #now函数:用于返回当前日期和时间,通常与其他日期函数共同使用
  data12: {{ now | date "2006-01-02" }} #date函数:用于将日期信息进行格式化,date函数后面需要指明日期的格式
  #这个格式内容必须使用"2006-01-02"或"02/01/2006"来标明
  data13: {{ dateInZone "2006-01-02" (now) "UTC" }} #dateInZone函数:用法与date函数基本一致,只不过dataInZone函数可以指定时区返回时间
  data14: {{ duration "95" }} #该函数可将给定的秒数转换为golang中的time.Duration类型,如:指定95秒可返回1m35s,秒数必须需要使用双引号,否则会返回0s 
  data15: {{ durationRound "2h10m5s" }} #结果:2h,durationRound函数用于将给定的日期进行取整,保留最大的单位 


apiVersion: v1
kind: ConfigMap
metadata:
  name: test-cm
  # namespace: 
data:
  data1: 1702473627 #unixEpoch函数:用于返回给定时间的时间戳格式 
  data2: 2023-12-13 19:20:27.549612 +0800 CST m=-7199.853926874 #将当前的时间减去2h再返回
  data3: 2023-12-13 19:20:27.549624 +0800 CST m=-7199.853914499 #将当前的时间减去2h再返回
  date4: 2017-12-31 00:00:00 +0800 CST #将后面的字符串以前面的格式进行转换输出
  date5: 2017-12-31 00:00:00 +0800 CST #将后面的字符串以前面的日期格式进行转换输出
  data6: 2023-12-13 21:20:27.549637 +0800 CST m=+0.146098376 #now函数:用于返回当前日期和时间,通常与其他日期函数共同使用
  data7: 2023-12-13 #date函数:用于将日期信息进行格式化,date函数后面需要指明日期的格式
  #这个格式内容必须使用"2006-01-02"或"02/01/2006"来标明
  data8: 2023-12-13 #dateInZone函数:用法与date函数基本一致,只不过dataInZone函数可以指定时区返回时间
  data9: 1m35s #该函数可将给定的秒数转换为golang中的time.Duration类型,如:指定95秒可返回1m35s,秒数必须需要使用双引号,否则会返回0s 
  data10: 2h #结果:2h,durationRound函数用于将给定的日期进行取整,保留最大的单位 
  data11: 2023-12-13 21:20:27.549648 +0800 CST m=+0.146109293 #now函数:用于返回当前日期和时间,通常与其他日期函数共同使用
  data12: 2023-12-13 #date函数:用于将日期信息进行格式化,date函数后面需要指明日期的格式
  #这个格式内容必须使用"2006-01-02"或"02/01/2006"来标明
  data13: 2023-12-13 #dateInZone函数:用法与date函数基本一致,只不过dataInZone函数可以指定时区返回时间
  data14: 1m35s #该函数可将给定的秒数转换为golang中的time.Duration类型,如:指定95秒可返回1m35s,秒数必须需要使用双引号,否则会返回0s 
  data15: 2h #结果:2h,durationRound函数用于将给定的日期进行取整,保留最大的单位
```
