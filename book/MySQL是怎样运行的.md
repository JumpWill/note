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
