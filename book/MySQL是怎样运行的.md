# MySQL是怎样运行的

## 第一章

### 通信方式

#### TCP/IP

真实环境中，数据库服务器进程和客户端进程可能运行在不同的主机中，它们之间必须通过网络来进行通讯。MySQL采用TCP作为服务器和客户端之间的网络通信协议。在网络环境下，每台计算机都有一个唯一的IP地址，如果某个进程有需要采用TCP协议进行网络通信方面的需求，可以向操作系统申请一个端口号，这是一个整数值，它的取值范围是0~65535。这样在网络中的其他进程就可以通过IP地址 + 端口号的方式来与这个进程连接，这样进程之间就可以通过网络进行通信了

#### 命名管道和共享内存

如果你是一个`Windows`用户，那么客户端进程和服务器进程之间可以考虑使用`命名管道`或`共享内存`进行通信。不过启用这些通信方式的时候需要在启动服务器程序和客户端程序时添加一些参数：

- 使用`命名管道`来进行进程间通信

    需要在启动服务器程序的命令中加上`--enable-named-pipe`参数，然后在启动客户端程序的命令中加入`--pipe`或者`--protocol=pipe`参数。

- 使用`共享内存`来进行进程间通信

    需要在启动服务器程序的命令中加上`--shared-memory`参数，在成功启动服务器后，`共享内存`便成为本地客户端程序的默认连接方式，不过我们也可以在启动客户端程序的命令中加入`--protocol=memory`参数来显式的指定使用共享内存进行通信。

    不过需要注意的是，使用`共享内存`的方式进行通信的服务器进程和客户端进程必须在同一台`Windows`主机中。

#### Unix域套接字文件

如果我们的服务器进程和客户端进程都运行在同一台操作系统为类`Unix`的机器上的话，我们可以使用`Unix域套接字文件`来进行进程间通信。如果我们在启动客户端程序的时候指定的主机名为`localhost`，或者指定了`--protocol=socket`的启动参数，那服务器程序和客户端程序之间就可以通过`Unix`域套接字文件来进行通信了。`MySQL`服务器程序默认监听的`Unix`域套接字文件路径为`/tmp/mysql.sock`，客户端程序也默认连接到这个`Unix`域套接字文件。如果我们想改变这个默认路径，可以在启动服务器程序时指定`socket`参数，就像这样：

```
mysqld --socket=/tmp/a.txt
```

这样服务器启动后便会监听`/tmp/a.txt`。在服务器改变了默认的`UNIX`域套接字文件后，如果客户端程序想通过`UNIX`域套接字文件进行通信的话，也需要显式的指定连接到的`UNIX`域套接字文件路径，就像这样：

```
mysql -hlocalhost -uroot --socket=/tmp/a.txt -p
```

这样该客户端进程和服务器进程就可以通过路径为`/tmp/a.txt`的`Unix`域套接字文件进行通信了。

### 处理过程

其实不论客户端进程和服务器进程是采用哪种方式进行通信，最后实现的效果都是：<span style="color:red">客户端进程向服务器进程发送一段文本（MySQL语句），服务器进程处理后再向客户端进程发送一段文本（处理结果）</span>。那服务器进程对客户端进程发送的请求做了什么处理，才能产生最后的处理结果呢？客户端可以向服务器发送增删改查各类请求，我们这里以比较复杂的查询请求为例来画个图展示一下大致的过程：
`连接管理`、`解析与优化`、`存储引擎`

#### 连接管理

每当有一个客户端进程连接到服务器进程时，服务器进程都会创建一个线程来专门处理与这个客户端的交互，当该客户端退出时会与服务器断开连接，服务器并不会立即把与该客户端交互的线程销毁掉，而是把它缓存起来，在另一个新的客户端再进行连接时，把这个缓存的线程分配给该新客户端。这样就起到了不频繁创建和销毁线程的效果，从而节省开销。

当连接建立后，与该客户端关联的服务器线程会一直等待客户端发送过来的请求，`MySQL`服务器接收到的请求只是一个文本消息，该文本消息还要经过各种处。

#### 解析与优化

`MySQL`服务器已经获得了文本形式的请求，接着
还要经过九九八十一难的处理，其中的几个比较重要的部分分别是`查询缓存`、`语法解析`和`查询优化`，下边我们详细来看。

##### 查询缓存

`MySQL`服务器程序处理查询请求会把刚刚处理过的查询请求和结果`缓存`起来，如果下一次有一模一样的请求过来，直接从缓存中查找结果就好了，就不用再傻呵呵的去底层的表中查找了。这个查询缓存可以在不同客户端之间共享，也就是说如果客户端A刚刚查询了一个语句，而客户端B之后发送了同样的查询请求，那么客户端B的这次查询就可以直接使用查询缓存中的数据

<span style="color:red">如果两个查询请求在任何字符上的不同（例如：空格、注释、大小写），都会导致缓存不会命中</span>。另外，<span style="color:red">如果查询请求中包含某些系统函数、用户自定义变量和函数、一些系统表，如 mysql 、information_schema、 performance_schema 数据库中的表，那这个请求就不会被缓存</span>。以某些系统函数举例，可能同样的函数的两次调用会产生不一样的结果，比如函数`NOW`，每次调用都会产生最新的当前时间，如果在一个查询请求中调用了这个函数，那即使查询请求的文本信息都一样，那不同时间的两次查询也应该得到不同的结果，如果在第一次查询时就缓存了，那第二次查询的时候直接使用第一次查询的结果就是错误的！

不过既然是缓存，那就有它缓存失效的时候。<span style="color:red">MySQL的缓存系统会监测涉及到的每张表，只要该表的结构或者数据被修改，如对该表使用了`INSERT`、 `UPDATE`、`DELETE`、`TRUNCATE TABLE`、`ALTER TABLE`、`DROP TABLE`或 `DROP DATABASE`语句，那使用该表的所有高速缓存查询都将变为无效并从高速缓存中删除</span>！

```!
小贴士：

虽然查询缓存有时可以提升系统性能，但也不得不因维护这块缓存而造成一些开销，比如每次都要去查询缓存中检索，查询请求处理完需要更新查询缓存，维护该查询缓存对应的内存区域。从MySQL 5.7.20开始，不推荐使用查询缓存，并在MySQL 8.0中删除。
```

##### 语法解析

因为客户端程序发送过来的请求只是一段文本而已，所以`MySQL`服务器程序首先要对这段文本做分析，判断请求的语法是否正确，然后从文本中将要查询的表、各种查询条件都提取出来放到`MySQL`服务器内部使用的一些数据结构上来。

##### 查询优化

语法解析之后，服务器程序获得到了需要的信息，比如要查询的列是哪些，表是哪个，搜索条件是什么等等，但光有这些是不够的，因为我们写的`MySQL`语句执行起来效率可能并不是很高，`MySQL`的优化程序会对我们的语句做一些优化，如外连接转换为内连接、表达式简化、子查询转为连接等。优化的结果就是生成一个执行计划，这个执行计划表明了应该使用哪些索引进行查询，表之间的连接顺序是啥样的。可以使用`EXPLAIN`语句来查看某个语句的执行计划。

### 存储引擎

截止到服务器程序完成了查询优化为止，还没有真正的去访问真实的数据表，`MySQL`服务器把数据的存储和提取操作都封装到了一个叫`存储引擎`的模块里。我们知道`表`是由一行一行的记录组成的，但这只是一个逻辑上的概念，物理上如何表示记录，怎么从表中读取数据，怎么把数据写入具体的物理存储器上，这都是`存储引擎`负责的事情。为了实现不同的功能，`MySQL`提供了各式各样的`存储引擎`，不同`存储引擎`管理的表具体的存储结构可能不同，采用的存取算法也可能不同。

为了管理方便，人们把`连接管理`、`查询缓存`、`语法解析`、`查询优化`这些并不涉及真实数据存储的功能划分为`MySQL server`的功能，把真实存取数据的功能划分为`存储引擎`的功能。各种不同的存储引擎向上边的`MySQL server`层提供统一的调用接口（也就是存储引擎API），包含了几十个底层函数，像"读取索引第一条内容"、"读取索引下一条内容"、"插入记录"等等。

#### 常用存储引擎

|存储引擎|描述|
|:--:|:--:|
|`ARCHIVE`|用于数据存档（行被插入后不能再修改）|
|`BLACKHOLE`|丢弃写操作，读操作会返回空内容|
|`CSV`|在存储数据时，以逗号分隔各个数据项|
|`FEDERATED`|用来访问远程表|
|`InnoDB`|具备外键支持功能的事务存储引擎|
|`MEMORY`|置于内存的表|
|`MERGE`|用来管理多个MyISAM表构成的表集合|
|`MyISAM`|主要的非事务处理存储引擎|
|`NDB`|MySQL集群专用存储引擎|

|Feature	|MyISAM	|Memory	|InnoDB	|Archive	|NDB|
|:--:|:--:|:--:|:--:|:--:|:--:|
|B-tree indexes	|yes	|yes	|yes	|no	|no|
|Backup/point-in-time recovery 	|yes	|yes	|yes	|yes	|yes|
|Cluster database support	|no	|no	|no	|no	|yes|
|Clustered indexes	|no	|no	|yes	|no	|no|
|Compressed data	|yes 	|no	|yes	|yes	|no|
|Data caches	|no	|N/A	|yes	|no	|yes|
|Encrypted data 	|yes	|yes	|yes	|yes	|yes|
|Foreign key support	|no	|no	|yes	|no	|yes |
|Full-text search indexes	|yes	|no	|yes 	|no	|no|
|Geospatial data type support	|yes	|no	|yes	|yes	|yes|
|Geospatial indexing support	|yes	|no	|yes 	|no	|no|
|Hash indexes	|no	|yes	|no 	|no	|yes|
|Index caches	|yes	|N/A	|yes	|no	|yes|
|Locking granularity	|Table	|Table	|Row	|Row	|Row|
|MVCC	|no	|no	|yes	|no	|no|
|Query cache support	|yes	|yes	|yes	|yes	|yes|
|Replication support 	|yes	|Limited 	|yes	|yes	|yes|
|Storage limits	|256TB	|RAM	|64TB	|None	|384EB|
|T-tree indexes	|no	|no	|no	|no	|yes|
|Transactions	|no	|no	|yes	|no	|yes|
|Update statistics for data dictionary	|yes	|yes	|yes	|yes	|yes|

#### 相关操作

```
mysql> SHOW ENGINES;
+--------------------+---------+----------------------------------------------------------------+--------------+------+------------+
| Engine             | Support | Comment                                                        | Transactions | XA   | Savepoints |
+--------------------+---------+----------------------------------------------------------------+--------------+------+------------+
| InnoDB             | DEFAULT | Supports transactions, row-level locking, and foreign keys     | YES          | YES  | YES        |
| MRG_MYISAM         | YES     | Collection of identical MyISAM tables                          | NO           | NO   | NO         |
| MEMORY             | YES     | Hash based, stored in memory, useful for temporary tables      | NO           | NO   | NO         |
| BLACKHOLE          | YES     | /dev/null storage engine (anything you write to it disappears) | NO           | NO   | NO         |
| MyISAM             | YES     | MyISAM storage engine                                          | NO           | NO   | NO         |
| CSV                | YES     | CSV storage engine                                             | NO           | NO   | NO         |
| ARCHIVE            | YES     | Archive storage engine                                         | NO           | NO   | NO         |
| PERFORMANCE_SCHEMA | YES     | Performance Schema                                             | NO           | NO   | NO         |
| FEDERATED          | NO      | Federated MySQL storage engine                                 | NULL         | NULL | NULL       |
+--------------------+---------+----------------------------------------------------------------+--------------+------+------------+
9 rows in set (0.00 sec)


# 创建表时指定存储引擎
CREATE TABLE 表名(
    建表语句;
) ENGINE = 存储引擎名称;
# 修改
ALTER TABLE 表名 ENGINE = 存储引擎名称;
```

其中的`Support`列表示该存储引擎是否可用，`DEFAULT`值代表是当前服务器程序的默认存储引擎。`Comment`列是对存储引擎的一个描述，英文的，将就着看吧。`Transactions`列代表该存储引擎是否支持事务处理。`XA`列代表着该存储引擎是否支持分布式事务。`Savepoints`代表着该列是否支持部分事务回滚

## 第二章 启动选项和配置文件

### 配置文件

`MySQL`程序在启动时会寻找多个路径下的配置文件，这些路径有的是固定的，有的是可以在命令行指定的.
在类UNIX操作系统中，MySQL会按照下列路径来寻找配置文件：

|路径名|备注|
|--|--|
|`/etc/my.cnf`||
|`/etc/mysql/my.cnf`||
|`SYSCONFDIR/my.cnf`||
|`$MYSQL_HOME/my.cnf`|特定于服务器的选项（仅限服务器）|
|`defaults-extra-file`|命令行指定的额外配置文件路径|
|`~/.my.cnf`|用户特定选项|
|`~/.mylogin.cnf`|用户特定的登录路径选项（仅限客户端）|

像这个配置文件里就定义了许多个组，组名分别是server、mysqld、mysqld_safe、client、mysql、mysqladmin。每个组下边可以定义若干个启动选项

``` text
[server]
(具体的启动选项...)

[mysqld]
(具体的启动选项...)

[mysqld_safe]
(具体的启动选项...)

[client]
(具体的启动选项...)

[mysql]
(具体的启动选项...)

[mysqladmin]
(具体的启动选项...)
```

配置文件中不同的选项组是给不同的启动命令使用的，如果选项组名称与程序名称相同，则组中的选项将专门应用于该程序。例如， [mysqld]和[mysql]组分别应用于mysqld服务器程序和mysql客户端程序。不过有两个选项组比较特别：

- `[server]`组下边的启动选项将作用于所有的服务器程序。

- `[client]`组下边的启动选项将作用于所有的客户端程序。

为了直观感受一下，我们挑一些启动命令来看一下它们能读取的选项组都有哪些：

|启动命令|类别|能读取的组|
|:--:|:--:|:--:|
|`mysqld`|启动服务器|`[mysqld]`、`[server]`|
|`mysqld_safe`|启动服务器|`[mysqld]`、`[server]`、`[mysqld_safe]`|
|`mysql.server`|启动服务器|`[mysqld]`、`[server]`、`[mysql.server]`|
|`mysql`|启动客户端|`[mysql]`、`[client]`|
|`mysqladmin`|启动客户端|`[mysqladmin]`、`[client]`|
|`mysqldump`|启动客户端|`[mysqldump]`、`[client]`|

#### 优先级

##### 配置文件

<span style="color:red">如果我们在多个配置文件中设置了相同的启动选项，那以最后一个配置文件中的为准</span>。比方说`/etc/my.cnf`文件的内容是这样的：

```
[server]
default-storage-engine=InnoDB
```

而`~/.my.cnf`文件中的内容是这样的：

```
[server]
default-storage-engine=MyISAM
```

又因为`~/.my.cnf`比`/etc/my.cnf`顺序靠后，所以如果两个配置文件中出现相同的启动选项，以`~/.my.cnf`中的为准，所以`MySQL`服务器程序启动之后，`default-storage-engine`的值就是`MyISAM`。

##### 单一配置

同一个命令可以访问配置文件中的多个组，比如mysqld可以访问[mysqld]、[server]组，如果在同一个配置文件中，比如~/.my.cnf，在这些组里出现了同样的配置项，比如这样：

```
[server]
default-storage-engine=InnoDB

[mysqld]
default-storage-engine=MyISAM
```

么，将以最后一个出现的组中的启动选项为准，比方说例子中default-storage-engine既出现在[mysqld]组也出现在[server]组，因为[mysqld]组在[server]组后边，就以[mysqld]组中的配置项为准。

##### 命令行和配置文件中启动选项的区别

如果同一个启动选项既出现在命令行中，又出现在配置文件中，那么以命令行中的启动选项为准！

### 系统变量

`MySQL`服务器程序运行过程中会用到许多影响程序行为的变量，它们被称为`MySQL`系统变量，比如允许同时连入的客户端数量用系统变量`max_connections`表示，表的默认存储引擎用系统变量`default_storage_engine`表示，查询缓存的大小用系统变量`query_cache_size`表示，`MySQL`服务器程序的系统变量有好几百条，我们就不一一列举了。每个系统变量都有一个默认值，我们可以使用命令行或者配置文件中的选项在启动服务器时改变一些系统变量的值。大多数的系统变量的值也可以在程序运行过程中修改，而无需停止并重新启动它。

根据系统变量的作用范围的概念，具体来说作用范围分为这两种：

- `GLOBAL`：全局变量，影响服务器的整体操作。

- `SESSION`：会话变量，影响某个客户端连接的操作。（注：`SESSION`有个别名叫`LOCAL`）

#### 命令

##### 查看

```shell
SHOW VARIABLES [LIKE 匹配的模式];
```

##### 设置

```
SET [GLOBAL|SESSION] 系统变量名 = 值;
```

#### 注意

- <span style="color:red">并不是所有系统变量都具有`GLOBAL`和`SESSION`的作用范围</span>。

  - 有一些系统变量只具有`GLOBAL`作用范围，比方说`max_connections`，表示服务器程序支持同时最多有多少个客户端程序进行连接。

  - 有一些系统变量只具有`SESSION`作用范围，比如`insert_id`，表示在对某个包含`AUTO_INCREMENT`列的表进行插入时，该列初始的值。

  - 有一些系统变量的值既具有`GLOBAL`作用范围，也具有`SESSION`作用范围，比如我们前边用到的`default_storage_engine`，而且其实大部分的系统变量都是这样的，

- <span style="color:red">有些系统变量是只读的，并不能设置值</span>。

    比方说`version`，表示当前`MySQL`的版本，我们客户端是不能设置它的值的，只能在`SHOW VARIABLES`语句里查看。

### 状态变量

为了让我们更好的了解服务器程序的运行情况，`MySQL`服务器程序中维护了好多关于程序运行状态的变量，它们被称为`状态变量`。比方说`Threads_connected`表示当前有多少客户端与服务器建立了连接。

由于`状态变量`是用来显示服务器程序运行状况的，所以<span style="color:red">它们的值只能由服务器程序自己来设置，我们程序员是不能设置的</span>。与`系统变量`类似，`状态变量`也有`GLOBAL`和`SESSION`两个作用范围的，所以查看`状态变量`的语句可以这么写：

```
SHOW [GLOBAL|SESSION] STATUS [LIKE 匹配的模式];
```

类似的，如果我们不写明作用范围，默认的作用范围是`SESSION`，比方说这样：

```
mysql> SHOW STATUS LIKE 'thread%';
+-------------------+-------+
| Variable_name     | Value |
+-------------------+-------+
| Threads_cached    | 0     |
| Threads_connected | 1     |
| Threads_created   | 1     |
| Threads_running   | 1     |
+-------------------+-------+
4 rows in set (0.00 sec)

mysql>
```

所有以`Thread`开头的`SESSION`作用范围的状态变量就都被展示出来了。

## 第三章 字符集和比较规则

### 概念

#### 字符集

描述某个字符范围的编码规则。

常见字符集

- `ASCII`字符集

    共收录128个字符，包括空格、标点符号、数字、大小写字母和一些不可见字符。由于总共才128个字符，所以可以使用1个字节来进行编码，我们看一些字符的编码方式：

    ```
    'L' ->  01001100（十六进制：0x4C，十进制：76）
    'M' ->  01001101（十六进制：0x4D，十进制：77）
    ```

- `ISO 8859-1`字符集

    共收录256个字符，是在`ASCII`字符集的基础上又扩充了128个西欧常用字符(包括德法两国的字母)，也可以使用1个字节来进行编码。这个字符集也有一个别名`latin1`。

- `GB2312`字符集

    收录了汉字以及拉丁字母、希腊字母、日文平假名及片假名字母、俄语西里尔字母。其中收录汉字6763个，其他文字符号682个。同时这种字符集又兼容`ASCII`字符集，所以在编码方式上显得有些奇怪：

  - 如果该字符在`ASCII`字符集中，则采用1字节编码。
  - 否则采用2字节编码。

    这种表示一个字符需要的字节数可能不同的编码方式称为`变长编码方式`。比方说字符串`'爱u'`，其中`'爱'`需要用2个字节进行编码，编码后的十六进制表示为`0xCED2`，`'u'`需要用1个字节进行编码，编码后的十六进制表示为`0x75`，所以拼合起来就是`0xCED275`。

    ```!
    小贴士：
    
    我们怎么区分某个字节代表一个单独的字符还是代表某个字符的一部分呢？别忘了`ASCII`字符集只收录128个字符，使用0～127就可以表示全部字符，所以如果某个字节是在0～127之内的，就意味着一个字节代表一个单独的字符，否则就是两个字节代表一个单独的字符。
    ```

- `GBK`字符集

    `GBK`字符集只是在收录字符范围上对`GB2312`字符集作了扩充，编码方式上兼容`GB2312`。

- `utf8`字符集

    收录地球上能想到的所有字符，而且还在不断扩充。这种字符集兼容`ASCII`字符集，采用变长编码方式，编码一个字符需要使用1～4个字节，比方说这样：

    ```
    'L' ->  01001100（十六进制：0x4C）
    '啊' ->  111001011001010110001010（十六进制：0xE5958A）
    ```

    ```!
    小贴士：
    
    其实准确的说，utf8只是Unicode字符集的一种编码方案，Unicode字符集可以采用utf8、utf16、utf32这几种编码方案，utf8使用1～4个字节编码一个字符，utf16使用2个或4个字节编码一个字符，utf32使用4个字节编码一个字符。更详细的Unicode和其编码方案的知识不是本书的重点，大家上网查查哈～
    
    MySQL中并不区分字符集和编码方案的概念，所以后边唠叨的时候把utf8、utf16、utf32都当作一种字符集对待。
    ```

对于同一个字符，不同字符集也可能有不同的编码方式。比如对于汉字`'我'`来说，`ASCII`字符集中根本没有收录这个字符，`utf8`和`gb2312`字符集对汉字`我`的编码方式如下：

```text
utf8编码：111001101000100010010001 (3个字节，十六进制表示是：0xE68891)
gb2312编码：1100111011010010 (2个字节，十六进制表示是：0xCED2)
```

#### 比较规则

在我们确定了xiaohaizi字符集表示字符的范围以及编码规则后，怎么比较两个字符的大小呢？最容易想到的就是直接比较这两个字符对应的二进制编码的大小，比方说字符'a'的编码为0x01，字符'b'的编码为0x02，所以'a'小于'b'，这种简单的比较规则也可以被称为二进制比较规则，英文名为binary collation。

### 在MySQL中

`utf8`字符集表示一个字符需要使用1～4个字节，但是我们常用的一些字符使用1～3个字节就可以表示了。而在`MySQL`中字符集表示一个字符所用最大字节长度在某些方面会影响系统的存储和性能，所以设计`MySQL`的大叔偷偷的定义了两个概念：

- `utf8mb3`：阉割过的`utf8`字符集，只使用1～3个字节表示字符。

- `utf8mb4`：正宗的`utf8`字符集，使用1～4个字节表示字符。

有一点需要大家十分的注意，在`MySQL`中`utf8`是`utf8mb3`的别名，所以之后在`MySQL`中提到`utf8`就意味着使用1~3个字节来表示一个字符，如果大家有使用4字节编码一个字符的情况，比如存储一些emoji表情啥的，那请使用`utf8mb4`。

#### 字符集的支持

`MySQL`支持好多好多种字符集，查看当前`MySQL`中支持的字符集可以用下边这个语句：

```
SHOW (CHARACTER SET|CHARSET) [LIKE 匹配的模式];
```

其中`CHARACTER SET`和`CHARSET`是同义词，用任意一个都可以。我们查询一下（支持的字符集太多了，我们省略了一些）

```shell
mysql> SHOW CHARSET;
+----------+---------------------------------+---------------------+--------+
| Charset  | Description                     | Default collation   | Maxlen |
+----------+---------------------------------+---------------------+--------+
| big5     | Big5 Traditional Chinese        | big5_chinese_ci     |      2 |
...
| latin1   | cp1252 West European            | latin1_swedish_ci   |      1 |
| latin2   | ISO 8859-2 Central European     | latin2_general_ci   |      1 |
...
| ascii    | US ASCII                        | ascii_general_ci    |      1 |
...
| gb2312   | GB2312 Simplified Chinese       | gb2312_chinese_ci   |      2 |
...
| gbk      | GBK Simplified Chinese          | gbk_chinese_ci      |      2 |
| latin5   | ISO 8859-9 Turkish              | latin5_turkish_ci   |      1 |
...
| utf8     | UTF-8 Unicode                   | utf8_general_ci     |      3 |
| ucs2     | UCS-2 Unicode                   | ucs2_general_ci     |      2 |
...
| latin7   | ISO 8859-13 Baltic              | latin7_general_ci   |      1 |
| utf8mb4  | UTF-8 Unicode                   | utf8mb4_general_ci  |      4 |
| utf16    | UTF-16 Unicode                  | utf16_general_ci    |      4 |
| utf16le  | UTF-16LE Unicode                | utf16le_general_ci  |      4 |
...
| utf32    | UTF-32 Unicode                  | utf32_general_ci    |      4 |
| binary   | Binary pseudo charset           | binary              |      1 |
...
| gb18030  | China National Standard GB18030 | gb18030_chinese_ci  |      4 |
+----------+---------------------------------+---------------------+--------+
41 rows in set (0.01 sec)
```

#### 比较规则的支持

查看`MySQL`中支持的比较规则的命令如下：

```
SHOW COLLATION [LIKE 匹配的模式];
```

我们前边说过一种字符集可能对应着若干种比较规则，`MySQL`支持的字符集就已经非常多了，所以支持的比较规则更多，我们先只查看一下`utf8`字符集下的比较规则：

```
mysql> SHOW COLLATION LIKE 'utf8\_%';
+--------------------------+---------+-----+---------+----------+---------+
| Collation                | Charset | Id  | Default | Compiled | Sortlen |
+--------------------------+---------+-----+---------+----------+---------+
| utf8_general_ci          | utf8    |  33 | Yes     | Yes      |       1 |
| utf8_bin                 | utf8    |  83 |         | Yes      |       1 |
| utf8_unicode_ci          | utf8    | 192 |         | Yes      |       8 |
| utf8_icelandic_ci        | utf8    | 193 |         | Yes      |       8 |
| utf8_latvian_ci          | utf8    | 194 |         | Yes      |       8 |
| utf8_romanian_ci         | utf8    | 195 |         | Yes      |       8 |
| utf8_slovenian_ci        | utf8    | 196 |         | Yes      |       8 |
| utf8_polish_ci           | utf8    | 197 |         | Yes      |       8 |
| utf8_estonian_ci         | utf8    | 198 |         | Yes      |       8 |
| utf8_spanish_ci          | utf8    | 199 |         | Yes      |       8 |
| utf8_swedish_ci          | utf8    | 200 |         | Yes      |       8 |
| utf8_turkish_ci          | utf8    | 201 |         | Yes      |       8 |
| utf8_czech_ci            | utf8    | 202 |         | Yes      |       8 |
| utf8_danish_ci           | utf8    | 203 |         | Yes      |       8 |
| utf8_lithuanian_ci       | utf8    | 204 |         | Yes      |       8 |
| utf8_slovak_ci           | utf8    | 205 |         | Yes      |       8 |
| utf8_spanish2_ci         | utf8    | 206 |         | Yes      |       8 |
| utf8_roman_ci            | utf8    | 207 |         | Yes      |       8 |
| utf8_persian_ci          | utf8    | 208 |         | Yes      |       8 |
| utf8_esperanto_ci        | utf8    | 209 |         | Yes      |       8 |
| utf8_hungarian_ci        | utf8    | 210 |         | Yes      |       8 |
| utf8_sinhala_ci          | utf8    | 211 |         | Yes      |       8 |
| utf8_german2_ci          | utf8    | 212 |         | Yes      |       8 |
| utf8_croatian_ci         | utf8    | 213 |         | Yes      |       8 |
| utf8_unicode_520_ci      | utf8    | 214 |         | Yes      |       8 |
| utf8_vietnamese_ci       | utf8    | 215 |         | Yes      |       8 |
| utf8_general_mysql500_ci | utf8    | 223 |         | Yes      |       1 |
+--------------------------+---------+-----+---------+----------+---------+
27 rows in set (0.00 sec)
```

<span style="color:red">每种字符集对应若干种比较规则，每种字符集都有一种默认的比较规则</span>，`SHOW COLLATION`的返回结果中的`Default`列的值为`YES`的就是该字符集的默认比较规则，比方说`utf8`字符集默认的比较规则就是`utf8_general_ci`

#### MySQL中的级别

`MySQL`有4个级别的字符集和比较规则，分别是：

- 服务器级别
- 数据库级别
- 表级别
- 列级别

##### 服务器级别

`MySQL`提供了两个系统变量来表示服务器级别的字符集和比较规则：

|系统变量|描述|
|:--:|:--:|
|`character_set_server`|服务器级别的字符集|
|`collation_server`|服务器级别的比较规则|

```text
mysql> SHOW VARIABLES LIKE 'character_set_server';
+----------------------+-------+
| Variable_name        | Value |
+----------------------+-------+
| character_set_server | utf8  |
+----------------------+-------+
1 row in set (0.00 sec)

mysql> SHOW VARIABLES LIKE 'collation_server';
+------------------+-----------------+
| Variable_name    | Value           |
+------------------+-----------------+
| collation_server | utf8_general_ci |
+------------------+-----------------+
1 row in set (0.00 sec)

```

在启动服务器程序时通过启动选项或者在服务器程序运行过程中使用`SET`语句修改这两个变量的值。比如我们可以在配置文件中这样写：

```
[server]
character_set_server=gbk
collation_server=gbk_chinese_ci
```

##### 数据库级别

在创建和修改数据库的时候可以指定该数据库的字符集和比较规则，具体语法如下

```text
CREATE DATABASE 数据库名
    [[DEFAULT] CHARACTER SET 字符集名称]
    [[DEFAULT] COLLATE 比较规则名称];

ALTER DATABASE 数据库名
    [[DEFAULT] CHARACTER SET 字符集名称]
    [[DEFAULT] COLLATE 比较规则名称];

#例子
mysql> CREATE DATABASE charset_demo_db
    -> CHARACTER SET gb2312
    -> COLLATE gb2312_chinese_ci;
Query OK, 1 row affected (0.01 sec)
```

如果想查看当前数据库使用的字符集和比较规则，可以查看下面两个系统变量的值（前提是使用`USE`语句选择当前默认数据库，如果没有默认数据库，则变量与相应的服务器级系统变量具有相同的值）：

|系统变量|描述|
|:--:|:--:|
|`character_set_database`|当前数据库的字符集|
|`collation_database`|当前数据库的比较规则|

```
mysql> USE charset_demo_db;
Database changed

mysql> SHOW VARIABLES LIKE 'character_set_database';
+------------------------+--------+
| Variable_name          | Value  |
+------------------------+--------+
| character_set_database | gb2312 |
+------------------------+--------+
1 row in set (0.00 sec)

mysql> SHOW VARIABLES LIKE 'collation_database';
+--------------------+-------------------+
| Variable_name      | Value             |
+--------------------+-------------------+
| collation_database | gb2312_chinese_ci |
+--------------------+-------------------+
1 row in set (0.00 sec)

mysql>
```

可以看到这个`charset_demo_db`数据库的字符集和比较规则就是我们在创建语句中指定的。需要注意的一点是：<span style="color:red"> ***character_set_database*** 和 ***collation_database*** 这两个系统变量是只读的，我们不能通过修改这两个变量的值而改变当前数据库的字符集和比较规则</span>。

数据库的创建语句中也可以不指定字符集和比较规则，比如这样：

```shell
CREATE DATABASE 数据库名;
```

<span style="color:red">这样的话将使用服务器级别的字符集和比较规则作为数据库的字符集和比较规则</span>。

##### 表级别

在创建和修改表的时候指定表的字符集和比较规则，语法如下：

```
CREATE TABLE 表名 (列的信息)
    [[DEFAULT] CHARACTER SET 字符集名称]
    [COLLATE 比较规则名称]]

ALTER TABLE 表名
    [[DEFAULT] CHARACTER SET 字符集名称]
    [COLLATE 比较规则名称]
```

比方说我们在刚刚创建的`charset_demo_db`数据库中创建一个名为`t`的表，并指定这个表的字符集和比较规则：

```shell
mysql> CREATE TABLE t(
    ->     col VARCHAR(10)
    -> ) CHARACTER SET utf8 COLLATE utf8_general_ci;
Query OK, 0 rows affected (0.03 sec)
```

如果创建和修改表的语句中没有指明字符集和比较规则，<span style="color:red">将使用该表所在数据库的字符集和比较规则作为该表的字符集和比较规则</span>。假设我们的创建表`t`的语句是这么写的：

```
CREATE TABLE t(
    col VARCHAR(10)
);
```

因为表`t`的建表语句中并没有明确指定字符集和比较规则，则表`t`的字符集和比较规则将继承所在数据库`charset_demo_db`的字符集和比较规则，也就是`gb2312`和`gb2312_chinese_ci`。

##### 列级别

需要注意的是，对于存储字符串的列，<span style="color:red">同一个表中的不同的列也可以有不同的字符集和比较规则</span>。我们在创建和修改列定义的时候可以指定该列的字符集和比较规则，语法如下：

```
CREATE TABLE 表名(
    列名 字符串类型 [CHARACTER SET 字符集名称] [COLLATE 比较规则名称],
    其他列...
);

ALTER TABLE 表名 MODIFY 列名 字符串类型 [CHARACTER SET 字符集名称] [COLLATE 比较规则名称];
```

比如我们修改一下表`t`中列`col`的字符集和比较规则可以这么写：

```
mysql> ALTER TABLE t MODIFY col VARCHAR(10) CHARACTER SET gbk COLLATE gbk_chinese_ci;
Query OK, 0 rows affected (0.04 sec)
Records: 0  Duplicates: 0  Warnings: 0

mysql>
```

对于某个列来说，如果在创建和修改的语句中没有指明字符集和比较规则，<span style="color:red">将使用该列所在表的字符集和比较规则作为该列的字符集和比较规则</span>。比方说表`t`的字符集是`utf8`，比较规则是`utf8_general_ci`，修改列`col`的语句是这么写的：

```
ALTER TABLE t MODIFY col VARCHAR(10);
```

那列`col`的字符集和编码将使用表`t`的字符集和比较规则，也就是`utf8`和`utf8_general_ci`。

```!
小贴士：
在转换列的字符集时需要注意，如果转换前列中存储的数据不能用转换后的字符集进行表示会发生错误。比方说原先列使用的字符集是utf8，列中存储了一些汉字，现在把列的字符集转换为ascii的话就会出错，因为ascii字符集并不能表示汉字字符。
```

##### 仅修改字符集或仅修改比较规则

由于字符集和比较规则是互相有联系的，如果我们只修改了字符集，比较规则也会跟着变化，如果只修改了比较规则，字符集也会跟着变化，具体规则如下：

- 只修改字符集，则比较规则将变为修改后的字符集默认的比较规则。
- 只修改比较规则，则字符集将变为修改后的比较规则对应的字符集。

<span style="color:red">不论哪个级别的字符集和比较规则，这两条规则都适用</span>，我们以服务器级别的字符集和比较规则为例来看一下详细过程：

- 只修改字符集，则比较规则将变为修改后的字符集默认的比较规则。

    ```
    mysql> SET character_set_server = gb2312;
    Query OK, 0 rows affected (0.00 sec)
    
    mysql> SHOW VARIABLES LIKE 'character_set_server';
    +----------------------+--------+
    | Variable_name        | Value  |
    +----------------------+--------+
    | character_set_server | gb2312 |
    +----------------------+--------+
    1 row in set (0.00 sec)
    
    mysql>  SHOW VARIABLES LIKE 'collation_server';
    +------------------+-------------------+
    | Variable_name    | Value             |
    +------------------+-------------------+
    | collation_server | gb2312_chinese_ci |
    +------------------+-------------------+
    1 row in set (0.00 sec)
    ```

    我们只修改了`character_set_server`的值为`gb2312`，`collation_server`的值自动变为了`gb2312_chinese_ci`。

- 只修改比较规则，则字符集将变为修改后的比较规则对应的字符集。

    ```
    mysql> SET collation_server = utf8_general_ci;
    Query OK, 0 rows affected (0.00 sec)
    
    mysql> SHOW VARIABLES LIKE 'character_set_server';
    +----------------------+-------+
    | Variable_name        | Value |
    +----------------------+-------+
    | character_set_server | utf8  |
    +----------------------+-------+
    1 row in set (0.00 sec)
    
    mysql> SHOW VARIABLES LIKE 'collation_server';
    +------------------+-----------------+
    | Variable_name    | Value           |
    +------------------+-----------------+
    | collation_server | utf8_general_ci |
    +------------------+-----------------+
    1 row in set (0.00 sec)
    
    mysql>
    ```

    我们只修改了`collation_server`的值为`utf8_general_ci`，`character_set_server`的值自动变为了`utf8`。

### 客户端和服务器通信中的字符集

#### 编码和解码使用的字符集不一致的后果

说到底，字符串在计算机上的体现就是一个字节串，如果你使用不同字符集去解码这个字节串，最后得到的结果可能让你挠头。

我们知道字符`'我'`在`utf8`字符集编码下的字节串长这样：`0xE68891`，如果一个程序把这个字节串发送到另一个程序里，另一个程序用不同的字符集去解码这个字节串，假设使用的是`gbk`字符集来解释这串字节，解码过程就是这样的：

1. 首先看第一个字节`0xE6`，它的值大于`0x7F`（十进制：127），说明是两字节编码，继续读一字节后是`0xE688`，然后从`gbk`编码表中查找字节为`0xE688`对应的字符，发现是字符`'鎴'`

2. 继续读一个字节`0x91`，它的值也大于`0x7F`，再往后读一个字节发现木有了，所以这是半个字符。

3. 所以`0xE68891`被`gbk`字符集解释成一个字符`'鎴'`和半个字符。

假设用`iso-8859-1`，也就是`latin1`字符集去解释这串字节，解码过程如下：

1. 先读第一个字节`0xE6`，它对应的`latin1`字符为`æ`。

2. 再读第二个字节`0x88`，它对应的`latin1`字符为`ˆ`。

3. 再读第二个字节`0x91`，它对应的`latin1`字符为`‘`。

4. 所以整串字节`0xE68891`被`latin1`字符集解释后的字符串就是`'æˆ‘'`

可见，<span style="color:red">如果对于同一个字符串编码和解码使用的字符集不一样，会产生意想不到的结果</span>，作为人类的我们看上去就像是产生了乱码一样。

#### 字符集转换的概念

如果接收`0xE68891`这个字节串的程序按照`utf8`字符集进行解码，然后又把它按照`gbk`字符集进行编码，最后编码后的字节串就是`0xCED2`，我们把这个过程称为`字符集的转换`，也就是字符串`'我'`从`utf8`字符集转换为`gbk`字符集。

#### MySQL中字符集的转换

从客户端发往服务器的请求本质上就是一个字符串，服务器向客户端返回的结果本质上也是一个字符串，而字符串其实是使用某种字符集编码的二进制数据。这个字符串可不是使用一种字符集的编码方式一条道走到黑的，从发送请求到返回结果这个过程中伴随着多次字符集的转换，在这个过程中会用到3个系统变量，我们先把它们写出来看一下：

|系统变量|描述|
|:--:|:--:|
|`character_set_client`|服务器解码请求时使用的字符集|
|`character_set_connection`|服务器处理请求时会把请求字符串从`character_set_client`转为`character_set_connection`|
|`character_set_results`|服务器向客户端返回数据时使用的字符集|

查看（不同操作系统的默认值可能不同）：

```
mysql> SHOW VARIABLES LIKE 'character_set_client';
+----------------------+-------+
| Variable_name        | Value |
+----------------------+-------+
| character_set_client | utf8  |
+----------------------+-------+
1 row in set (0.00 sec)

mysql> SHOW VARIABLES LIKE 'character_set_connection';
+--------------------------+-------+
| Variable_name            | Value |
+--------------------------+-------+
| character_set_connection | utf8  |
+--------------------------+-------+
1 row in set (0.01 sec)

mysql> SHOW VARIABLES LIKE 'character_set_results';
+-----------------------+-------+
| Variable_name         | Value |
+-----------------------+-------+
| character_set_results | utf8  |
+-----------------------+-------+
1 row in set (0.00 sec)
```

大家可以看到这几个系统变量的值都是`utf8`，为了体现出字符集在请求处理过程中的变化，我们这里特意修改一个系统变量的值：

```shell
mysql> set character_set_connection = gbk;
Query OK, 0 rows affected (0.00 sec)
```

所以现在系统变量`character_set_client`和`character_set_results`的值还是`utf8`，而`character_set_connection`的值为`gbk`。现在假设我们客户端发送的请求是下边这个字符串：

```shell
SELECT * FROM t WHERE s = '我';
```

为了方便大家理解这个过程，我们只分析字符`'我'`在这个过程中字符集的转换。

现在看一下在请求从发送到结果返回过程中字符集的变化：

1. 客户端发送请求所使用的字符集

    一般情况下客户端所使用的字符集和当前操作系统一致，不同操作系统使用的字符集可能不一样，如下：

    - 类`Unix`系统使用的是`utf8`
    - `Windows`使用的是`gbk`

    例如我在使用的`macOS`操作系统时，客户端使用的就是`utf8`字符集。所以字符`'我'`在发送给服务器的请求中的字节形式就是：`0xE68891`

    ```!
    小贴士：
    
    如果你使用的是可视化工具，比如navicat之类的，这些工具可能会使用自定义的字符集来编码发送到服务器的字符串，而不采用操作系统默认的字符集（所以在学习的时候还是尽量用黑框框哈）。
    ```

2. 服务器接收到客户端发送来的请求其实是一串二进制的字节，它会认为这串字节采用的字符集是`character_set_client`，然后把这串字节转换为`character_set_connection`字符集编码的字符。

    由于我的计算机上`character_set_client`的值是`utf8`，首先会按照`utf8`字符集对字节串`0xE68891`进行解码，得到的字符串就是`'我'`，然后按照`character_set_connection`代表的字符集，也就是`gbk`进行编码，得到的结果就是字节串`0xCED2`。

3. 因为表`t`的列`col`采用的是`gbk`字符集，与`character_set_connection`一致，所以直接到列中找字节值为`0xCED2`的记录，最后找到了一条记录。

    ```!
    小贴士：
    
    如果某个列使用的字符集和character_set_connection代表的字符集不一致的话，还需要进行一次字符集转换。
    ```

4. 上一步骤找到的记录中的`col`列其实是一个字节串`0xCED2`，`col`列是采用`gbk`进行编码的，所以首先会将这个字节串使用`gbk`进行解码，得到字符串`'我'`，然后再把这个字符串使用`character_set_results`代表的字符集，也就是`utf8`进行编码，得到了新的字节串：`0xE68891`，然后发送给客户端。

5. 由于客户端是用的字符集是`utf8`，所以可以顺利的将`0xE68891`解释成字符`我`，从而显示到我们的显示器上，所以我们人类也读懂了返回的结果。

总之,因为不同的字符集的存在,character_set_client/character_set_connection/character_set_results如果不同就需要转换,通常都把 character_set_client 、character_set_connection、character_set_results 这三个系统变量设置成和客户端使用的字符集一致的情况，这样减少了很多无谓的字符集转换。

```mysql
SET character_set_client = 字符集名;
SET character_set_connection = 字符集名;
SET character_set_results = 字符集名;
```

想在启动客户端的时候就把`character_set_client`、`character_set_connection`、`character_set_results`这三个系统变量的值设置成一样的，那我们可以在启动客户端的时候指定一个叫`default-character-set`的启动选项，比如在配置文件里可以这么写：

```
[client]
default-character-set=utf8
```

它起到的效果和执行一遍`SET NAMES utf8`是一样一样的，都会将那三个系统变量的值设置成`utf8`。

### 比较规则的应用

`比较规则`的作用通常体现比较字符串大小的表达式以及对某个字符串列进行排序中，所以有时候也称为`排序规则`。
比方说表`t`的列`col`使用的字符集是`gbk`，使用的比较规则是`gbk_chinese_ci`，我们向里边插入几条记录：

```mysql
mysql> INSERT INTO t(col) VALUES('a'), ('b'), ('A'), ('B');
Query OK, 4 rows affected (0.00 sec)
Records: 4  Duplicates: 0  Warnings: 0

mysql> SELECT * FROM t ORDER BY col;
+------+
| col  |
+------+
| a    |
| A    |
| b    |
| B    |
| 我   |
+------+
5 rows in set (0.00 sec)

# 可以看到在默认的比较规则gbk_chinese_ci中是不区分大小写的，我们现在把列col的比较规则修改为gbk_bin：

mysql> SELECT * FROM t ORDER BY s;
+------+
| s    |
+------+
| A    |
| B    |
| a    |
| b    |
| 我   |
+------+
5 rows in set (0.00 sec)
```

如果以后在对字符串做比较或者对某个字符串列做排序操作时没有得到想象中的结果，需要思考一下是不是比较规则的问题

## InnoDB记录存储结构

将数据划分为若干个页，以页作为磁盘和内存之间交互的基本单位，InnoDB中页的大小一般为 16 KB。也就是在一般情况下，一次最少从磁盘中读取16KB的内容到内存中，一次最少把内存中的16KB内容刷新到磁盘中。一般情况下，一次最少从磁盘中读取16KB的内容到内存中，一次最少把内存中的16KB内容刷新到磁盘中。

### InnoDB行格式

设计InnoDB存储引擎的大叔们到现在为止设计了4种不同类型的行格式，分别是Compact、Redundant、Dynamic和Compressed行格式，随着时间的推移，他们可能会设计出更多的行格式，但是不管怎么变，在原理上大体都是相同的。

## 第四章 InnoDB记录存储结构

### 简介

InnoDB采取的方式是：将数据划分为若干个页，以页作为磁盘和内存之间交互的基本单位，InnoDB中页的大小一般为 16 KB。也就是在一般情况下，一次最少从磁盘中读取16KB的内容到内存中，一次最少把内存中的16KB内容刷新到磁盘中。

### InnoDB行格式

计InnoDB存储引擎的大叔们到现在为止设计了4种不同类型的行格式，分别是Compact、Redundant、Dynamic和Compressed行格式，随着时间的推移，他们可能会设计出更多的行格式，但是不管怎么变，在原理上大体都是相同的。

#### 指定行格式的语法

可以在创建或修改表的语句中指定`行格式`：

```mysql
CREATE TABLE 表名 (列的信息) ROW_FORMAT=行格式名称
    
ALTER TABLE 表名 ROW_FORMAT=行格式名称
```

比如我们在xiaohaizi数据库里创建一个演示用的表record_format_demo，可以这样指定它的行格式

```mysql
mysql> CREATE TABLE record_format_demo (
    ->     c1 VARCHAR(10),
    ->     c2 VARCHAR(10) NOT NULL,
    ->     c3 CHAR(10),
    ->     c4 VARCHAR(10)
    -> ) CHARSET=ascii ROW_FORMAT=COMPACT;
Query OK, 0 rows affected (0.03 sec)

mysql> INSERT INTO record_format_demo(c1, c2, c3, c4) VALUES('aaaa', 'bbb', 'cc', 'd'), ('eeee', 'fff', NULL, NULL);
Query OK, 2 rows affected (0.02 sec)
Records: 2  Duplicates: 0  Warnings: 0

mysql> SELECT * FROM record_format_demo;
+------+-----+------+------+
| c1   | c2  | c3   | c4   |
+------+-----+------+------+
| aaaa | bbb | cc   | d    |
| eeee | fff | NULL | NULL |
+------+-----+------+------+
2 rows in set (0.00 sec)
```

#### COMPACT行格式

![avatar](./imgs/MySQL是怎样运行的/compact.jpg)

##### 记录的额外信息

###### 变长字段长度列表

`MySQL`支持一些变长的数据类型，比如`VARCHAR(M)`、`VARBINARY(M)`、各种`TEXT`类型，各种`BLOB`类型，我们也可以把拥有这些数据类型的列称为`变长字段`，变长字段中存储多少字节的数据是不固定的，所以我们在存储真实数据的时候需要顺便把这些数据占用的字节数也存起来，这样才不至于把`MySQL`服务器搞懵，所以这些变长字段占用的存储空间分为两部分:

1. 真正的数据内容
2. 占用的字节数

在`Compact`行格式中，<span style="color:red">把所有变长字段的真实数据占用的字节长度都存放在记录的开头部位，从而形成一个变长字段长度列表，各变长字段数据占用的字节数按照列的顺序逆序存放</span>，我们再次强调一遍，是<span style="color:red">逆序</span>存放！

`record_format_demo`表中的第一条记录来举个例子。因为`record_format_demo`表的`c1`、`c2`、`c4`列都是`VARCHAR(10)`类型的，也就是变长的数据类型，所以这三个列的值的长度都需要保存在记录开头处，因为`record_format_demo`表中的各个列都使用的是`ascii`字符集，所以每个字符只需要1个字节来进行编码，来看一下第一条记录各变长字段内容的长度：

|列名|存储内容|内容长度（十进制表示）|内容长度（十六进制表示）|
|:--:|:--:|:--:|:--:|
|`c1`|`'aaaa'`|`4`|`0x04`|
|`c2`|`'bbb'`|`3`|`0x03`|
|`c4`|`'d'`|`1`|`0x01`|

又因为这些长度值需要按照列的<span style="color:red">逆序</span>存放，所以最后`变长字段长度列表`的字节串用十六进制表示的效果就是（各个字节之间实际上没有空格，用空格隔开只是方便理解）：

```
01 03 04 
```

![avatar](./imgs/MySQL是怎样运行的/list.png)

由于第一行记录中`c1`、`c2`、`c4`列中的字符串都比较短，也就是说内容占用的字节数比较小，用1个字节就可以表示，但是如果变长列的内容占用的字节数比较多，可能就需要用2个字节来表示。具体用1个还是2个字节来表示真实数据占用的字节数，`InnoDB`有它的一套规则，我们首先声明一下`W`、`M`和`L`的意思：

1. 假设某个字符集中表示一个字符最多需要使用的字节数为`W`，也就是使用`SHOW CHARSET`语句的结果中的`Maxlen`列，比方说`utf8`字符集中的`W`就是`3`，`gbk`字符集中的`W`就是`2`，`ascii`字符集中的`W`就是`1`。

2. 对于变长类型`VARCHAR(M)`来说，这种类型表示能存储最多`M`个字符（注意是字符不是字节），所以这个类型能表示的字符串最多占用的字节数就是`M×W`。

3. 假设它实际存储的字符串占用的字节数是`L`。

所以确定使用1个字节还是2个字节表示真正字符串占用的字节数的规则就是这样：

- 如果`M×W <= 255`，那么使用1个字节来表示真正字符串占用的字节数。

    ```!
    也就是说InnoDB在读记录的变长字段长度列表时先查看表结构，如果某个变长字段允许存储的最大字节数不大于255时，可以认为只使用1个字节来表示真正字符串占用的字节数。
    ```

- 如果`M×W > 255`，则分为两种情况：

  - 如果`L <= 127`，则用1个字节来表示真正字符串占用的字节数。

  - 如果`L > 127`，则用2个字节来表示真正字符串占用的字节数。

    ```!
    InnoDB在读记录的变长字段长度列表时先查看表结构，如果某个变长字段允许存储的最大字节数大于255时，该怎么区分它正在读的某个字节是一个单独的字段长度还是半个字段长度呢？设计InnoDB的大叔使用该字节的第一个二进制位作为标志位：如果该字节的第一个位为0，那该字节就是一个单独的字段长度（使用一个字节表示不大于127的二进制的第一个位都为0），如果该字节的第一个位为1，那该字节就是半个字段长度。
    
    对于一些占用字节数非常多的字段，比方说某个字段长度大于了16KB，那么如果该记录在单个页面中无法存储时，InnoDB会把一部分数据存放到所谓的溢出页中（我们后边会唠叨），在变长字段长度列表处只存储留在本页面中的长度，所以使用两个字节也可以存放下来。
    ```

总结一下就是说：如果该可变字段允许存储的最大字节数（`M×W`）超过255字节并且真实存储的字节数（`L`）超过127字节，则使用2个字节，否则使用1个字节。

总结一下就是说：如果该可变字段允许存储的最大字节数（M×W）超过255字节并且真实存储的字节数（L）超过127字节，则使用2个字节，否则使用1个字节

另外需要注意的一点是，<span style="color:red">变长字段长度列表中只存储值为 ***非NULL*** 的列内容占用的长度，值为 ***NULL*** 的列的长度是不储存的 </span>。也就是说对于第二条记录来说，因为`c4`列的值为`NULL`，所以第二条记录的`变长字段长度列表`只需要存储`c1`和`c2`列的长度即可。其中`c1`列存储的值为`'eeee'`，占用的字节数为`4`，`c2`列存储的值为`'fff'`，占用的字节数为`3`。数字`4`可以用1个字节表示，`3`也可以用1个字节表示，所以整个`变长字段长度列表`共需2个字节。填充完`变长字段长度列表`的两条记录的对比图如下：
![avatar](./imgs/MySQL是怎样运行的/list2.png)

###### NULL值列表

某些列可能存储`NULL`值，如果把这些`NULL`值都放到`记录的真实数据`中存储会很占地方，所以`Compact`行格式把这些值为`NULL`的列统一管理起来，存储到`NULL`值列表中，它的处理过程是这样的：

1. 首先统计表中允许存储`NULL`的列有哪些。

    我们前边说过，主键列、被`NOT NULL`修饰的列都是不可以存储`NULL`值的，所以在统计的时候不会把这些列算进去。比方说表`record_format_demo`的3个列`c1`、`c3`、`c4`都是允许存储`NULL`值的，而`c2`列是被`NOT NULL`修饰，不允许存储`NULL`值。

2. <span style="color:red">如果表中没有允许存储 ***NULL*** 的列，则 *NULL值列表* 也不存在了</span>，否则将每个允许存储`NULL`的列对应一个二进制位，二进制位按照列的顺序<span style="color:red">逆序</span>排列，二进制位表示的意义如下：

    - 二进制位的值为`1`时，代表该列的值为`NULL`。
    - 二进制位的值为`0`时，代表该列的值不为`NULL`。

    因为表`record_format_demo`有3个值允许为`NULL`的列，所以这3个列和二进制位的对应关系就是这样：

    ![avatar](./imgs/MySQL是怎样运行的/null-1.png)

    再一次强调，二进制位按照列的顺序<span style="color:red">逆序</span>排列，所以第一个列`c1`和最后一个二进制位对应。

3. `MySQL`规定`NULL值列表`必须用整数个字节的位表示，如果使用的二进制位个数不是整数个字节，则在字节的高位补`0`。

    表`record_format_demo`只有3个值允许为`NULL`的列，对应3个二进制位，不足一个字节，所以在字节的高位补`0`，效果就是这样：

   ![avatar](./imgs/MySQL是怎样运行的/null-2.png)

    以此类推，如果一个表中有9个允许为`NULL`，那这个记录的`NULL`值列表部分就需要2个字节来表示了。

知道了规则之后，我们再返回头看表`record_format_demo`中的两条记录中的`NULL值列表`应该怎么储存。因为只有`c1`、`c3`、`c4`这3个列允许存储`NULL`值，所以所有记录的`NULL值列表`只需要一个字节。

- 对于第一条记录来说，`c1`、`c3`、`c4`这3个列的值都不为`NULL`，所以它们对应的二进制位都是`0`，画个图就是这样：

    ![avatar](./imgs/MySQL是怎样运行的/null-3.png)
    所以第一条记录的`NULL值列表`用十六进制表示就是：`0x00`。

- 对于第二条记录来说，`c1`、`c3`、`c4`这3个列中`c3`和`c4`的值都为`NULL`，所以这3个列对应的二进制位的情况就是：

    ![avatar](./imgs/MySQL是怎样运行的/null-4.png)

    所以第二条记录的`NULL值列表`用十六进制表示就是：`0x06`。

所以这两条记录在填充了`NULL值列表`后的示意图就是这样：

![avatar](./imgs/MySQL是怎样运行的/null-5.png)

###### 记录头信息

除了`变长字段长度列表`、`NULL值列表`之外，还有一个用于描述记录的`记录头信息`，它是由固定的`5`个字节组成。`5`个字节也就是`40`个二进制位，不同的位代表不同的意思，如图：
![avatar](./imgs/MySQL是怎样运行的/header-1.png)

这些二进制位代表的详细信息如下表：

|名称|大小（单位：bit）|描述|
|:--:|:--:|:--:|
|`预留位1`|`1`|没有使用|
|`预留位2`|`1`|没有使用|
|`delete_mask`|`1`|标记该记录是否被删除|
|`min_rec_mask`|`1`|B+树的每层非叶子节点中的最小记录都会添加该标记|
|`n_owned`|`4`|表示当前记录拥有的记录数|
|`heap_no`|`13`|表示当前记录在记录堆的位置信息|
|`record_type`|`3`|表示当前记录的类型，`0`表示普通记录，`1`表示B+树非叶子节点记录，`2`表示最小记录，`3`表示最大记录|
|`next_record`|`16`|表示下一条记录的相对位置|

之后会详细介绍,当前仅仅是看下存储`record_format_demo`中的两条记录的`头信息`分别是什么：
![avatar](./imgs/MySQL是怎样运行的/header-2.png)

###### 记录的真实数据

对于`record_format_demo`表来说，`记录的真实数据`除了`c1`、`c2`、`c3`、`c4`这几个我们自己定义的列的数据以外，`MySQL`会为每个记录默认的添加一些列（也称为`隐藏列`），具体的列如下：

|列名|是否必须|占用空间|描述|
|:--:|:--:|:--:|:--:|
|`row_id`|否|`6`字节|行ID，唯一标识一条记录|
|`transaction_id`|是|`6`字节|事务ID|
|`roll_pointer`|是|`7`字节|回滚指针|

```!
小贴士：

实际上这几个列的真正名称其实是：DB_ROW_ID、DB_TRX_ID、DB_ROLL_PTR，我们为了美观才写成了row_id、transaction_id和roll_pointer。
```

![avatar](./imgs/MySQL是怎样运行的/record-1.png)

看这个图的时候需要注意几点：

1. 表`record_format_demo`使用的是`ascii`字符集，所以`0x61616161`就表示字符串`'aaaa'`，`0x626262`就表示字符串`'bbb'`，以此类推。

2. 注意第1条记录中`c3`列的值，它是`CHAR(10)`类型的，它实际存储的字符串是：`'cc'`，而`ascii`字符集中的字节表示是`'0x6363'`，虽然表示这个字符串只占用了2个字节，但整个`c3`列仍然占用了10个字节的空间，除真实数据以外的8个字节的统统都用<span style="color:red">空格字符</span>填充，空格字符在`ascii`字符集的表示就是`0x20`。

3. 注意第2条记录中`c3`和`c4`列的值都为`NULL`，它们被存储在了前边的`NULL值列表`处，在记录的真实数据处就不再冗余存储，从而节省存储空间。

### char与varchar

#### CHAR(M)列的存储格式

`record_format_demo`表的`c1`、`c2`、`c4`列的类型是`VARCHAR(10)`，而`c3`列的类型是`CHAR(10)`，我们说在`Compact`行格式下只会把变长类型的列的长度<span style="color:red">逆序</span>存到`变长字段长度列表`中，就像这样：

![avatar](./imgs/MySQL是怎样运行的/char-1.png)

但是这只是因为我们的`record_format_demo`表采用的是`ascii`字符集，这个字符集是一个定长字符集，也就是说表示一个字符采用固定的一个字节，如果采用变长的字符集（也就是表示一个字符需要的字节数不确定，比如`gbk`表示一个字符要1~2个字节、`utf8`表示一个字符要1 ~3个字节等）的话，`c3`列的长度也会被存储到`变长字段长度列表`中，比如我们修改一下`record_format_demo`表的字符集：

```
mysql> ALTER TABLE record_format_demo MODIFY COLUMN c3 CHAR(10) CHARACTER SET utf8;
Query OK, 2 rows affected (0.02 sec)
Records: 2  Duplicates: 0  Warnings: 0
```

修改该列字符集后记录的`变长字段长度列表`也发生了变化，如图：
![avatar](./imgs/MySQL是怎样运行的/char-2.png)
![avatar](./imgs/MySQL是怎样运行的/char-3.png)

这就意味着：<span style="color:red">对于 ***CHAR(M)*** 类型的列来说，当列采用的是定长字符集时，该列占用的字节数不会被加到变长字段长度列表，而如果采用变长字符集时，该列占用的字节数也会被加到变长字段长度列表</span>

另外有一点还需要注意，变长字符集的`CHAR(M)`类型的列要求至少占用`M`个字节，而`VARCHAR(M)`却没有这个要求。比方说对于使用`utf8`字符集的`CHAR(10)`的列来说，该列存储的数据字节长度的范围是10～30个字节。即使我们向该列中存储一个空字符串也会占用`10`个字节，这是怕将来更新该列的值的字节长度大于原有值的字节长度而小于10个字节时，可以在该记录处直接更新，而不是在存储空间中重新分配一个新的记录空间，导致原有的记录空间成为所谓的碎片。（这里你感受到设计`Compact`行格式的大叔既想节省存储空间，又不想更新`CHAR(M)`类型的列产生碎片时的纠结心情了吧。）

#### VARCHAR(M)

对于`VARCHAR(M)`类型的列最多可以占用`65535`个字节。其中的`M`代表该类型最多存储的字符数量，如果我们使用`ascii`字符集的话，一个字符就代表一个字节，我们看看`VARCHAR(65535)`是否可用：

mysql> CREATE TABLE varchar_size_demo(
    ->     c VARCHAR(65535)
    -> ) CHARSET=ascii ROW_FORMAT=Compact;
ERROR 1118 (42000): Row size too large. The maximum row size for the used table type, not counting BLOBs, is 65535. This includes storage overhead, check the manual. You have to change some columns to TEXT or BLOBs
mysql>
``

从报错信息里可以看出，`MySQL`对一条记录占用的最大存储空间是有限制的，除了`BLOB`或者`TEXT`类型的列之外，其他所有的列（不包括隐藏列和记录头信息）占用的字节长度加起来不能超过`65535`个字节。所以`MySQL`服务器建议我们把存储类型改为`TEXT`或者`BLOB`的类型。这个`65535`个字节除了列本身的数据之外，还包括一些其他的数据（`storage overhead`），比如说我们为了存储一个`VARCHAR(M)`类型的列，其实需要占用3部分存储空间：

- 真实数据
- 真实数据占用字节的长度 2个字节
- `NULL`值标识，如果该列有`NOT NULL`属性则可以没有这部分存储空间 如果需要则一个字节

```
mysql> CREATE TABLE varchar_size_demo(
    ->      c VARCHAR(65532)
    -> ) CHARSET=ascii ROW_FORMAT=Compact;
Query OK, 0 rows affected (0.02 sec)
```

如果`VARCHAR`类型的列有`NOT NULL`属性，那最多只能存储`65533`个字节的数据，因为真实数据的长度可能占用2个字节，不需要`NULL`值标识：

如果`VARCHAR`类型的列有`NOT NULL`属性，那最多只能存储`65533`个字节的数据，因为真实数据的长度可能占用2个字节，不需要`NULL`值标识：

```mysql
mysql> CREATE TABLE varchar_size_demo(
    ->      c VARCHAR(65532)
    -> ) CHARSET=ascii ROW_FORMAT=Compact;
Query OK, 0 rows affected (0.02 sec)


mysql> DROP TABLE varchar_size_demo;
Query OK, 0 rows affected (0.01 sec)

mysql> CREATE TABLE varchar_size_demo(
    ->      c VARCHAR(65533) NOT NULL
    -> ) CHARSET=ascii ROW_FORMAT=Compact;
Query OK, 0 rows affected (0.02 sec)
```

如果`VARCHAR(M)`类型的列使用的不是`ascii`字符集，那会怎么样呢？来看一下：

```
mysql> DROP TABLE varchar_size_demo;
Query OK, 0 rows affected (0.00 sec)

mysql> CREATE TABLE varchar_size_demo(
    ->       c VARCHAR(65532)
    -> ) CHARSET=gbk ROW_FORMAT=Compact;
ERROR 1074 (42000): Column length too big for column 'c' (max = 32767); use BLOB or TEXT instead

mysql> CREATE TABLE varchar_size_demo(
    ->       c VARCHAR(65532)
    -> ) CHARSET=utf8 ROW_FORMAT=Compact;
ERROR 1074 (42000): Column length too big for column 'c' (max = 21845); use BLOB or TEXT instead
```

从执行结果中可以看出，如果`VARCHAR(M)`类型的列使用的不是`ascii`字符集，那`M`的最大取值取决于该字符集表示一个字符最多需要的字节数。在列的值允许为`NULL`的情况下，`gbk`字符集表示一个字符最多需要`2`个字节，那在该字符集下，`M`的最大取值就是`32766`（也就是：65532/2），也就是说最多能存储`32766`个字符；`utf8`字符集表示一个字符最多需要`3`个字节，那在该字符集下，`M`的最大取值就是`21844`，就是说最多能存储`21844`（也就是：65532/3）个字符。

```!
小贴士：

上述所言在列的值允许为NULL的情况下，gbk字符集下M的最大取值就是32766，utf8字符集下M的最大取值就是21844，这都是在表中只有一个字段的情况下说的，一定要记住一个行中的所有列（不包括隐藏列和记录头信息）占用的字节长度加起来不能超过65535个字节！
```

#### 记录中的数据太多产生的溢出

以`ascii`字符集下的`varchar_size_demo`表为例，插入一条记录：

```
mysql> CREATE TABLE varchar_size_demo(
    ->       c VARCHAR(65532)
    -> ) CHARSET=ascii ROW_FORMAT=Compact;
Query OK, 0 rows affected (0.01 sec)

mysql> INSERT INTO varchar_size_demo(c) VALUES(REPEAT('a', 65532));
Query OK, 1 row affected (0.00 sec)
```

`MySQL`是以`页`为基本单位来管理存储空间的，我们的记录都会被分配到某个`页`中存储。而一个页的大小一般是`16KB`，也就是`16384`字节，而一个`VARCHAR(M)`类型的列就最多可以存储`65532`个字节，这样就可能造成一个页存放不了一条记录的尴尬情况。

在`Compact`和`Reduntant`行格式中，对于占用存储空间非常大的列，在`记录的真实数据`处只会存储该列的一部分数据，把剩余的数据分散存储在几个其他的页中，然后`记录的真实数据`处用20个字节存储指向这些页的地址（当然这20个字节中还包括这些分散在其他页面中的数据的占用的字节数），从而可以找到剩余数据所在的页，如图所示：
![avatar](./imgs/MySQL是怎样运行的/over-store-1.png)

从图中可以看出来，对于`Compact`和`Reduntant`行格式来说，如果某一列中的数据非常多的话，在本记录的真实数据处只会存储该列的前`768`个字节的数据和一个指向其他页的地址，然后把剩下的数据存放到其他页中，这个过程也叫做`行溢出`，存储超出`768`字节的那些页面也被称为`溢出页`。

最后需要注意的是，<span style="color:red">不只是 ***VARCHAR(M)*** 类型的列，其他的 ***TEXT***、***BLOB*** 类型的列在存储数据非常多的时候也会发生`行溢出`</span>。

#### 行溢出的临界点

`MySQL`中规定<span style="color:red">一个页中至少存放两行记录</span>，至于为什么这么规定我们之后再说，现在看一下这个规定造成的影响。以上边的`varchar_size_demo`表为例，它只有一个列`c`，我们往这个表中插入两条记录，每条记录最少插入多少字节的数据才会`行溢出`的现象呢？这得分析一下页中的空间都是如何利用的。

- 每个页除了存放我们的记录以外，也需要存储一些额外的信息，乱七八糟的额外信息加起来需要`136`个字节的空间（现在只要知道这个数字就好了），其他的空间都可以被用来存储记录。

- 每个记录需要的额外信息是`27`字节。

    这27个字节包括下边这些部分：
  - 2个字节用于存储真实数据的长度
  - 1个字节用于存储列是否是NULL值
  - 5个字节大小的头信息
  - 6个字节的`row_id`列
  - 6个字节的`transaction_id`列
  - 7个字节的`roll_pointer`列

假设一个列中存储的数据字节数为n，那么发生`行溢出`现象时需要满足这个式子：

```
136 + 2×(27 + n) > 16384
```

求解这个式子得出的解是：`n > 8098`。也就是说如果一个列中存储的数据不大于`8098`个字节，那就不会发生`行溢出`，否则就会发生`行溢出`。不过这个`8098`个字节的结论只是针对只有一个列的`varchar_size_demo`表来说的，如果表中有多个列，那上边的式子和结论都需要改一改了，所以重点就是：<span style="color:red">你不用关注这个临界点是什么，只要知道如果我们想一个行中存储了很大的数据时，可能发生`行溢出`的现象</span>。

##### Dynamic和Compressed行格式

下边要介绍另外两个行格式，`Dynamic`和`Compressed`行格式，我现在使用的`MySQL`版本是`5.7`，它的默认行格式就是`Dynamic`，这俩行格式和`Compact`行格式挺像，只不过在处理`行溢出`数据时有点儿分歧，它们不会在记录的真实数据处存储字段真实数据的前`768`个字节，而是把所有的字节都存储到其他页面中，只在记录的真实数据处存储其他页面的地址，就像这样：

![avatar](./imgs/MySQL是怎样运行的/over-store-2.png)

`Compressed`行格式和`Dynamic`不同的一点是，`Compressed`行格式会采用压缩算法对页面进行压缩，以节省空间。
