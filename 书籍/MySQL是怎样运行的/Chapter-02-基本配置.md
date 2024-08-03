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

```text
[server]
default-storage-engine=MyISAM
```

又因为`~/.my.cnf`比`/etc/my.cnf`顺序靠后，所以如果两个配置文件中出现相同的启动选项，以`~/.my.cnf`中的为准，所以`MySQL`服务器程序启动之后，`default-storage-engine`的值就是`MyISAM`。

##### 单一配置

同一个命令可以访问配置文件中的多个组，比如mysqld可以访问[mysqld]、[server]组，如果在同一个配置文件中，比如~/.my.cnf，在这些组里出现了同样的配置项，比如这样：

```text
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

```mysql
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

```mysql
SHOW [GLOBAL|SESSION] STATUS [LIKE 匹配的模式];
```

类似的，如果我们不写明作用范围，默认的作用范围是`SESSION`，比方说这样：

```mysql
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