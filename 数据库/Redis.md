
## NoSQL
    not only SQL
### 常见的Nosql：
	Redis
	memcha
	Hbase
	MongoDB
### redis
	remote    dictionary  sever
### 特征
	key-value
	内部采用单线程
	性能高
	多数据类型存储（String、list、hash、set、sorted_set）
        支持持久化
### 应用
	加速热点信息的查询
	任务队列
	信息即时查询
	时效性的东西
	分布式数据共享


## 五种数据类型

### 字符类型String

字符串或者是数值，可以设置其过期时间

|           **命令**            |                   **作用**                   |
| :---------------------------: | :------------------------------------------: |
|         set key value         |                 添加一个key                  |
|            get key            |       查询信息，如果不存在的话返回nil        |
|            del key            |     删除（删除成功返回1，删除失败返回0）     |
| mset key1 value1 key2 value2  |                 存储多个数据                 |
|        mget key1 key2         |                  获取多个值                  |
|          strlen key           |                返回字符串长度                |
|     append key 追加的内容     |      给key追加值，如果不存在直接新建key      |
|           incr key            |  让字符数值增加1，例如2变为3，返回值是value  |
|           decr key            |  让字符数值减少1，例如3变为2，返回值是value  |
|        incrby key num         | 让value值增加num（num为整数），返回值是value |
|        decrby key num         |       让value值减少num，返回值是value        |
|      incrbyfloat key num      | 让value值增加num（num为小数），返回值是value |
|      decrbyfloat key num      | 让value值减少num（num为小数），返回值是value |
|    setex key seconds value    |     让一个值存在多少秒数，时间到了就没了     |
| psetex key milliseconds value |             让一个值存在多少毫秒             |

PS:

①使用数值操作，如果不能转换为数字或者范围超出将报错。其最大值范围-9223372036854775808到9,223,372,036,854,775,807，即是-2的63次方到2的63次方-1

②string的最大数据是512MB

### **哈希hash**  

hash可被认为是key的值是一个字典，通过指定key field才能找到具体的值。 

![](C:\Users\will\Desktop\图片1.png)

|          **命令**           |           **作用**            |
| :-------------------------: | :---------------------------: |
|     hset key field vaue     | 给key新增一个field其值为value |
|       hget key field        |     获取key值中field的值      |
|         hgetall key         |       获取key中所有东西       |
|   hdel key field1 field2    |      删除key中的field1….      |
|          hlen key           |       key有的field数量        |
|      hexists key field      |    查看key中是否存在field     |
|          hkeys key          |     查看key下的所有field      |
|          hvals key          |     查看key下的所有value      |
|    hincrby key filed num    |     让key中的filed增加num     |
| hincrbyfloat key  filed num | 让key中的filed增加num（小数） |
|  hmset key field1 value1 …  |          设置多个值           |
|       hdel key field        |        删除key中field         |
|   hsetnx key field value    | 如果存在不变，如果不存在添加  |

 PS:

​	①value中只能是字符串/数值类型。

​    ②hash中的存储类似于对象，但是不能滥用。 

​    ③hash不能设置过期时间。

### **列表list**  

存储多个数据，底层使用的数据结构为双向列表。使用的插入方法是头插法。

例如：如图，从左遍历是b a ，插入c ，因为是头插，所以成了cba （从左边遍历）

![](C:\Users\will\Desktop\图片2.png)

|          **命令**           |                           **作用**                           |
| :-------------------------: | :----------------------------------------------------------: |
| **lpush key value1 value2** |                        **左插入list**                        |
| **rpush key value1 value2** |                     **将数据右插入list**                     |
|  **lrange key start end**   | **查看start到end的元素（end可以为负数，但是start不能为负数）** |
|    **lindex key  index**    |                  **查看位置为index的元素**                   |
|        **llen key**         |                      **查看key的长度**                       |
|        **lpop key**         |                  **获取并且移除左边的数据**                  |
|        **rpop key**         |                  **获取并且移除右边的数据**                  |
|     **blpop key time**      |              **在一定时间内左边取出数据且移除**              |
|     **brpop key time**      |              **在一定时间内右边取出数据且移除**              |
|    **lrem key n value**     |          **移除列表里的值value，并且移除n个value**           |

### 集合set

​        存储大量数据，提供高效率查询，数据不允许重复。可以用于去重 。

|          **命令**           |                **作用**                |
| :-------------------------: | :------------------------------------: |
|   sadd key value1  value2   |                增加元素                |
|        smembers key         |           查看key中所有元素            |
|       srem key value        |              移除某个元素              |
|          scard key          |          获取集合元素的总数量          |
|    sismembers key member    |         查看member是否在集合中         |
|   srandmember key   count   |  随机取集合中的一个值，不在元素中删除  |
|          spop kye           |     随机获取集合中的某个数据且移除     |
|      sinter set1 set2…      |                 求交集                 |
|     sunion set1 set2….      |                 求并集                 |
|       sdiff set1 set2       |                 求差集                 |
| sinterstore set1  set2 set3 |      将set2与set3的交集存到set1中      |
| sunionstore set1  set2 set3 |      将set2与set3的并集存到set1中      |
| sdiffstore set1  set2 set3  |      将set2与set3的差集存到set1中      |
|   smove set1 set2 member    | 将set1中的member移到set2中，s1中会去除 |

### 排序集合 sorted_set

​        key member score，某个班级里某个同学有一个分数，通过分数排名。

|                           **命令**                           |                           **作用**                           |
| :----------------------------------------------------------: | :----------------------------------------------------------: |
|            zadd key score member   score1 member1            |                           添加数据                           |
|             zrange key start stop （withscores）             | 从start看到stop，选择是否看到score（由小到大排的），不使用withscore返回的menber的值  使用withscores返回的数据为member1 score1 member2 score1 2 |
|           zrevrange key start stop （withscores）            |      从start看到stop，选择是否看到score（由大到小排的）      |
|                       zrem key member                        |                           移除数据                           |
|  zrangebyscore key min max （withscores  limit start end）   |  查看min到max之间的数据，可以使用limit限制数量。从小到大。   |
| zrevrangebyscore key   max min （withscores limit start end） | 查看min到max之间的数据，可以使用limit限制数量，  从大到小。  |
|                zremrangebyrank key start stop                |       按索引删除，start到stop的都删除（两端的都删除）        |
|                zremrangebyscore key min   max                |              按score删除，删除从min到max的数据               |
|                          zcard key                           |                         查看多少数据                         |
|                      zconut key min max                      |                查看范围在min到max中的数据总数                |
| zinterstore st1 num st2 st3 st4  （ZINTERSTORE destination numkeys key [key ...] [WEIGHTS weight  [weight ...]] [AGGREGATE SUM\|MIN\|MAX） | 交集，指定num个st（后面写的数量需与num一致），将这些个集合里都公共的东西的score加起来，然后存在st1中，还可以求平均最大最小，以及设置权重。 |
|               zunionstore st1 num st2 st3 st4                | 并集，指定num个st（后面写的数量需与num一致），将这些个集合里都公共的东西的score加起来，然后存在st1中，还可以求平均最大最小，以及设置权重。 |
|                       zrank key member                       |                  查看member的索引，从小到大                  |
|                     zrevrank key member                      |                  查看member的索引，从大到小                  |
|                      zscore key member                       |                      查看member的score                       |
|                    zincrby key num member                    |                     将key中的member加num                     |

PS:

①如果score使用整数，其范围是2的64位。

②score为小数的时候，是双精度的double类型，进行加减的时候会造成精度丢失等。

参考：

**[https://blog.csdn.net/qq_27215113/article/details/100663914](https://blog.csdn.net/qq_27215113/article/details/100663914)**


## 通用命令

### key相关
|          **命令**           |                           **作用**                           |
| :-------------------------: | :----------------------------------------------------------: |
| del key | 删除key |
| exists key | 查看key是否存在 |
| type key | 查看key的类型 |
| expire key seconds| 为key设置有效期，秒数 |
| pexpire key milliseconds| 为key设置有效期，毫秒数 |
| ttl key | 获取key的有效时间（如果key是永久的返回-1，如果key是已经失效，返回-2） |
| persist key| 将key转为永久化的 |

### db相关
|          **命令**           |                           **作用**                           |
| :-------------------------: | :----------------------------------------------------------: |
|  select index | 选择数据库 |
|  quit |  退出 |
|  ping | 查看是否建立连接 |
| move key db | 把当前的数据库的key移动到db中，db中不能存在相同的key |
|  dbsize |  查看当前数据库的key的多少 |
|  flushdb | 清除当前数据库的key |
| flushall | 删除数据库所有数据 |


## 持久化
	save   前台保存
	bgsave 后台保存
	利用永久性存储介质，在特定时间里将保存的数据恢复回去。
    RDB存储的数据是存在data里面的  xxxx.rdb文件，里面存储的持久化的数据。

|          **方式**           |     **save**|**bgsave**|
| :-------------------------: | :-------------------------: | :-------------------------: |
| 读写 | 同步 | 异步 |
| 阻塞 | 是 | 否 |
| 额外消耗内存 | 否 | 是 |
| 是否启新进程 | 否 | 是 |



### RDB
RDB为存取某个时间段的快照。
#### 配置文件相关
|          **命令**           |                           **作用**                           |
| :-------------------------: | :----------------------------------------------------------: |
| rdbchecksum yes | 从版本RDB版本5开始，一个CRC64的校验就被放在了文件末尾.这会让格式更加耐攻击，但是当存储或者加载rbd文件的时候会有一个10%左右的性能下降，所以，为了达到性能的最大化，你可以关掉这个配置项。没有校验的RDB文件会有一个0校验位，来告诉加载代码跳过校验检查 |
| rdbcompression yes | 是否在导出.rdb数据库文件的时候采用LZF压缩字符串和对象,默认情况下总是设置成‘yes’,他看起来是一把双刃剑.如果你想在存储的子进程中节省一些CPU就设置成'no',但是这样如果你的key/value是可压缩的，你得到的数据接就会很大。 |
| dbfilename xxx.rdb | 存储数据的文件名称 |
| stop-writes-on-bgsave-error yes | 在默认情况下，如果RDB快照持久化操作被激活（至少一个条件被激活）并且持久化操作失败，Redis则会停止接受更新操作.这样会让用户了解到数据没有被正确的存储到磁盘上。否则没人会注意到这个问题，可能会造成灾难,#如果后台存储（持久化）操作进程再次工作，Redis会自动允许更新操作.然而，如果你已经恰当的配置了对Redis服务器的监视和备份，你也许想关掉这项功能,如此一来即使后台保存操作出错,redis也仍然可以继续像平常一样工作。 |
| 	dir ./data 	 | 数据文件存储位置 |
| save second nums | 当限定时间内key的数量变化达到了一定数量就进行持久化 |

#### 流程细说
	当条件满足，redis需要执行RDB的时候，服务器会执行以下操作：
	1. redis调用系统函数fork() ，创建一个子进程。
	
	2.子进程将数据集写入到一个临时 RDB 文件中。
	
	3.当子进程完成对临时RDB文件的写入时，redis 用新的临时RDB 文件替换原来的RDB 文件，并删除旧 RDB 文件。
	
	在执行fork的时候操作系统（类Unix操作系统）会使用写时复制（copy-on-write）策略，即fork函数发生的一刻父子进程共享同一内存数据，当父进程要更改其中某片数据时（如执行一个写命令 ），操作系统会将该片数据复制一份以保证子进程的数据不受影响，所以新的RDB文件存储的是执行fork那一刻的内存数据。
	
	Redis在进行快照的过程中不会修改RDB文件，只有快照结束后才会将旧的文件替换成新的，也就是说任何时候RDB文件都是完整的。这使得我们可以通过定时备份RDB文件来实 现Redis数据库备份。RDB文件是经过压缩（可以配置rdbcompression参数以禁用压缩节省CPU占用）的二进制格式，所以占用的空间会小于内存中的数据大小，更加利于传输。
	
除了自动快照，还可以手动发送SAVE或BGSAVE命令让Redis执行快照，两个命令的区别在于，前者是由主进程进行快照操作，会阻塞住其他请求，后者会通过fork子进程进行快照操作。

#### 优点与缺点
##### 优点
    1.RDB是一个非常紧凑(compact)的文件，它保存了redis 在某个时间点上的数据集。这种文件非常适合用于进行备份和灾难恢复。
    2.生成RDB文件的时候，redis主进程会fork()一个子进程来处理所有保存工作，主进程不需要进行任何磁盘IO操作。
    3.RDB 在恢复大数据集时的速度比 AOF 的恢复速度要快。
##### 缺点
    1.如果你需要尽量避免在服务器故障时丢失数据，那么RDB 不适合你。 虽然Redis 允许你设置不同的保存点（save point）来控制保存 RDB 文件的频率， 但是， 因为RDB 文件需要保存整个数据集的状态， 所以它并不是一个轻松的操作。 因此你可能会至少 5 分钟才保存一次 RDB 文件。 在这种情况下， 一旦发生故障停机， 你就可能会丢失好几分钟的数据。
    2.每次保存 RDB 的时候，Redis 都要 fork() 出一个子进程，并由子进程来进行实际的持久化工作。 在数据集比较庞大时， fork() 可能会非常耗时，造成服务器在某某毫秒内停止处理客户端； 如果数据集非常巨大，并且 CPU 时间非常紧张的话，那么这种停止时间甚至可能会长达整整一秒。 虽然 AOF 重写也需要进行 fork() ，但无论 AOF 重写的执行间隔有多长，数据的耐久性都不会有任何损失。
    3.redis多版本的rbd文件可能不一致，同一文件在不同版本可能不适用。
	 
	通过RDB方式实现持久化，一旦Redis异常退出，就会丢失最后一次快照以后更改的所有数据。
	参考：
    https://blog.csdn.net/aitangyong/article/details/52045251

### AOF
append only file，将数据的变化操作记录到文件中，重启之后执行这些数据变化，以保持与之前的数据一致。
#### 相关配置
|          **命令**           |                           **作用**                           |
| :-------------------------: | :----------------------------------------------------------: |
| appendonly no |   是否开启aof |
|  appendfilename  "appendonly.aof"| 数据存储文件名 |
|  appendfsync no  | 配置写数据策略有:always 每次数据变化都记录，性能低.exerysec每秒 将缓冲区指令放到aof文件中，性能较高.no 有系统控制，整体自己不可控。 |
| auto-aof-rewrite-percentage | 触发自动重写的最低文件体积（小于64mb不自动重写） |
| aof-use-rdb-preamble yes | 开启混合持久化 |
#### 流程详解
在使用AOF如果频繁修改一个key的value，只有最后的value才是有效的，中间的修改可以认为是无用的，，但是无用操作都会写到AOF。在AOF中有一个重写机制，会将这些中间数据删除，只记录最后的，因为重写机制会使恢复数据更快。其重写机制如下：
①进程已超时的数据不再写入文件中。
②中间数据不写入，只写入最终的数据。
③对同一个数据的多个写操作，将其和并为一条指令，但是为了防止缓冲区溢出，对list，set，hash等每条指令最多写入64个元素。
#### 优点与缺点
##### 优点
	①AOF 持久化的方法提供了多种的同步频率，即使使用默认的同步频率每秒同步一次，Redis 最多也就丢失 1 秒的数据而已。
	②AOF 文件使用 Redis 命令追加的形式来构造，因此，即使 Redis 只能向 AOF 文件写入命令的片断，使用 redis-check-aof 工具也很容易修正 AOF 文件。
	③AOF 文件的格式可读性较强，这也为使用者提供了更灵活的处理方式。例如，如果我们不小心错用了 FLUSHALL 命令，在重写还没进行时，我们可以手工将最后的 FLUSHALL 命令去掉，然后再使用 AOF 来恢复数据。
##### 缺点
    ①对于具有相同数据的的Redis,AOF文件通常会比RDF文件体积更大。
	②虽然AOF提供了多种同步的频率，默认情况下，每秒同步一次的频率也具有较高的性能。但在Redis的负载较高时,RDB比AOF具好更好的性能保证。
    ③RDB使用快照的形式来持久化整个Redis数据，而AOF只是将每次执行的命令追加到AOF文件中，因此从理论上说RDB比AOF方式更健壮。官方文档也指出,AOF的确也存在一些BUG，这些BUG在RDB没有存在

### RDB和AOF对比
|          **方式**           |     **RDB**|**AOF**|
| :-------------------------: | :-------------------------: | :-------------------------: |
| 占用存储 | 小 | 大 |
| 存储速度 | 慢 | 快 |
| 恢复速度 | 快 | 慢 |
| 数据安全 | 会丢失数据 | 根据策略而定 |
| 资源消耗 | 多 | 少 |
| 启动优先级 | 低 | 高 |

## 事务
