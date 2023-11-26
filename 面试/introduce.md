1. 个人基本情况介绍
2. 技术介绍  
   · 编程语言python+go+shell+(java)
   · 熟悉linux的基本操作
   · 数据库 mysql+redis+es
     · redis
       · 数据类型 string/list/hash/sorted_set/set/ 高级
       · 持久化 RDB 保存快照(文件小恢复快 丢失最后一次保存后的数据 占用小 资源消耗多) AOF(存储命令,将每次变化存储到文件，文件比较大恢复慢)   持久化方式RDB+AOF
       · 删除策略  定期删除/惰性删除/定时删除
     · mysql
       · 存储引擎
            | 功能         | MylSAM | MEMORY | InnoDB | Archive |
            | ------------ | ------ | ------ | ------ | ------- |
            | 存储限制     | 256TB  | RAM    | 64TB   | None    |
            | 支持事务     | No     | No     | Yes    | No      |
            | 支持全文索引 | Yes    | No     | No     | No      |
            | 支持树索引   | Yes    | Yes    | Yes    | No      |
            | 支持哈希索引 | No     | Yes    | No     | No      |
            | 支持数据缓存 | No     | N/A    | Yes    | No      |
            | 支持外键     | No     | No     | Yes    | No      |
       · curd
            select 字段列表 from 表列表 where 条件列表 group by 分组字段列表  having 分组后的条件列表  order by 排序字段列表  limit 分页参数
            update table set 列名1=值1,,列名2=值2 [where 限制条件]
            delete from table [where 限制条件]
            insert into table values (列值1,列值2...),(列值1,列值2;..);
       · 四大特性
            | 特性                  |                             说明                             |
            | :-------------------- | :----------------------------------------------------------: |
            | 一致性（Consistency） | 一致性是指事务必须使数据库从一个一致性状态变换到另一个一致性状态，也就是说一个事务执行之前和执行之后都必须处于一致性状态。 |
            | 隔离性（隔离）        | 隔离性是当多个用户并发访问数据库时，比如操作同一张表时，数据库为每一个用户开启的事务，不能被其他事务的操作所干扰，多个并发事务之间要相互隔离。 |
            | 持久性（耐久性）      | 持久性是指一个事务一旦被提交了，那么对数据库中的数据的改变就是永久性的，即便是在数据库系统遇到故障的情况下也不会丢失提交事务的操作。 |
            | 原子性（Atomicity     | 原子性是指事务包含的所有操作要么全部成功，要么全部失败回滚，这和前面两篇博客介绍事务的功能是一样的概念，因此事务的操作如果成功就必须要完全应用到数据库，如果操作失败则不能对数据库有任何影响。 |
       · 事务隔离级别
            ##### **Read Uncommitted（读取未提交内容）**

            在该隔离级别，所有事务都可以看到其他未提交事务的执行结果。本隔离级别很少用于实际应用，因为它的性能也不比其他级别好多少。读取未提交的数据，也被称之为脏读（Dirty Read）。

            ##### **Read Committed（读取提交内容）**

            这是大多数数据库系统的默认隔离级别（但不是MySQL默认的）。它满足了隔离的简单定义：一个事务只能看见已经提交事务所做的改变。这种隔离级别 也支持所谓的不可重复读（Nonrepeatable Read），因为同一事务的其他实例在该实例处理其间可能会有新的commit，所以同一select可能返回不同结果。

            ##### **Repeatable Read（可重读）**

            这是MySQL的默认事务隔离级别，它确保同一事务的多个实例在并发读取数据时，会看到同样的数据行。不过理论上，这会导致另一个棘手的问题：幻读 （Phantom Read）。简单的说，幻读指当用户读取某一范围的数据行时，另一个事务又在该范围内插入了新行，当用户再读取该范围的数据行时，会发现有新的“幻影” 行。InnoDB和Falcon存储引擎通过多版本并发控制（MVCC，Multiversion Concurrency Control）机制解决了该问题。

            ##### **Serializable（可串行化）**

            这是最高的隔离级别，它通过强制事务排序，使之不可能相互冲突，从而解决幻读问题。简言之，它是在每个读的数据行上加上共享锁。在这个级别，可能导致大量的超时现象和锁竞争。这四种隔离级别采取不同的锁类型来实现，若读取的是同一个数据的话，就容易发生问题。例如：

            - 脏读(Drity     Read)：某个事务已更新一份数据，另一个事务在此时读取了同一份数据，由于某些原因，前一个RollBack了操作，则后一个事务所读取的数据就会是不正确的。

            - 不可重复读(Non-repeatable     read):在一个事务的两次查询之中数据不一致，这可能是两次查询过程中间插入了一个事务更新的原有的数据。

            - 幻读(Phantom     Read):在一个事务的两次查询中数据笔数不一致，例如有一个事务查询了几列(Row)数据，而另一个事务却在此时插入了新的几列数据，先前的事务在接下来的查询中，就有几列数据是未查询出来的，如果此时插入和另外一个事务插入的数据，就会报错。
     ·
   · 容器 docker+k8s
     · docker linux的进程隔离 cgroup和namespace(挂载命名空间,pid命名空间,hostname命名空间,user命名空间,ipc命名空间)  harbor镜像仓库
     · k8s 容器调度
       · 进程/进程组----> pod(健康检查,端口暴露,prestart/prestop,污点,重启策略,调度(亲和性反亲和性))/deployment/statufulset/StatefulSet/Job/
       · 资源限额度----> limitRange/Resourcequota
       · 网络    ----->  LB/ingress(nodeport ip+端口访问 clusterip )/service/网络策略(进出)
       · 存储    ------>   pv/pvc/configmap/secret/volumn
       · 权限控制  ----->   role/clutserrole/rolebingding/ServiceAccount
       · 其他 crd/helm 仅仅简单用过
       · 相关技术 普罗米休斯/grafana/airflow/
   · gitlab/cicd
3. 前公司介绍
    · python开发
    · 主要职责：修bug 重构代码 推动B端项目进程
    · 离职原因: 老板做技术,想一套是一套,没有规划,不管你手上有啥事情都打断你,让敏捷开发,被折磨烦了。敏捷开发做下来并没有多少设计或者说是考虑,所以导致了很多缺陷,像雪球一样越滚越大越积累越多，然后又会打断你让你修,最终恶性循环。
4. 装饰器

```python

def out2(x):
    def debug(func):
        def wrapper(*args, **kwargs):
            print("here is ,", x)
            print("[DEBUG]: enter {}()".format(func.__name__))
            return func(*args, **kwargs)
        return wrapper
    return debug
@out2(x=99)
def hello():
    print("hello")
hello()
```
