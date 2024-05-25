## 定位慢查询

### 慢查询日志

```sql
# 查看慢查询日志信息
show variables like '%slow_query_log%';
+---------------------+--------------------------------------+
| Variable_name       | Value                                |
+---------------------+--------------------------------------+
| slow_query_log      | OFF                                  |
| slow_query_log_file | /var/lib/mysql/41077670ad8f-slow.log |
+---------------------+--------------------------------------+
# 查询阈值
show variables like '%long_query_time%';
# 启用慢日志
set global slow_query_log=on;
# 设置慢查询日志时间阈值 4s
set global long_query_time=4;
```

### show processlist

一个mysql连接，或者说一个线程，任何时刻都有一个状态，该状态表示了mysql当前正在做什么。SHOW PROCESSLIST;显示哪些线程正在运行。

可以看到所有链接的情况，但是大多链接的 state 其实是 Sleep 的，这种的其实是空闲状态，没有太多查看价值

我们要观察的是有问题的，所以可以进行过滤：

```sql

mysql> show processlist;
+----+-----------------+-----------+------+---------+---------+------------------------+-----------------------------------------+
| Id | User            | Host      | db   | Command | Time    | State                  | Info                                    |
+----+-----------------+-----------+------+---------+---------+------------------------+-----------------------------------------+
|  5 | event_scheduler | localhost | NULL | Daemon  | 3028986 | Waiting on empty queue | NULL                                    |
| 34 | root            | localhost | NULL | Query   |       0 | init                   | show processlist                        |
| 35 | root            | localhost | chat | Query   |       2 | User sleep             | select * from chat_group where sleep(2) |
+----+-----------------+-----------+------+---------+---------+------------------------+-----------------------------------------+

-- 查询非 Sleep 状态的链接，按消耗时间倒序展示，自己加条件过滤
select id, db, user, host, command, time, state, info
from information_schema.processlist
where command != 'Sleep'
order by time desc 
```

| STATE | 解释 |
|  ----  | ----  |
|Checking table|正在检查数据表（这是自动的）。|
|Closing tables|正在将表中修改的数据刷新到磁盘中，同时正在关闭已经用完的表。这是一个很快的操作，如果不是这样的话，就应该确认磁盘空间是否已经满了或者磁盘是否正处于重负中。|
|Connect Out|复制从服务器正在连接主服务器。|
|Copying to tmp table on disk|由于临时结果集大于tmp_table_size，正在将临时表从内存存储转为磁盘存储以此节省内存。|
|Creating tmp table|正在创建临时表以存放部分查询结果。|
|deleting from main table|服务器正在执行多表删除中的第一部分，刚删除第一个表。|
|deleting from reference tables|服务器正在执行多表删除中的第二部分，正在删除其他表的记录。|
|Flushing tables|正在执行FLUSH TABLES，等待其他线程关闭数据表。|
|Killed|发送了一个kill请求给某线程，那么这个线程将会检查kill标志位，同时会放弃下一个kill请求。MySQL会在每次的主循环中检查kill标志位，不过有些情况下该线程可能会过一小段才能死掉。如果该线程程被其他线程锁住了，那么kill请求会在锁释放时马上生效。|
|Locked|被其他查询锁住了。|
|Sending data|正在处理SELECT查询的记录，同时正在把结果发送给客户端。|
|Sorting for group|正在为GROUP BY做排序。|
|Sorting for order|正在为ORDER BY做排序。|
|Opening tables|这个过程应该会很快，除非受到其他因素的干扰。例如，在执ALTER TABLE或LOCK TABLE语句行完以前，数据表无法被其他线程打开。正尝试打开一个表。|
|Removing duplicates|正在执行一个SELECT DISTINCT方式的查询，但是MySQL无法在前一个阶段优化掉那些重复的记录。因此，MySQL需要再次去掉重复的记录，然后再把结果发送给客户端。|
|Reopen table|获得了对一个表的锁，但是必须在表结构修改之后才能获得这个锁。已经释放锁，关闭数据表，正尝试重新打开数据表。|
|Repair by sorting|修复指令正在排序以创建索引。|
|Repair with keycache|修复指令正在利用索引缓存一个一个地创建新索引。它会比Repair by sorting慢些。|
|Searching rows for update|正在讲符合条件的记录找出来以备更新。它必须在UPDATE要修改相关的记录之前就完成了。|
|Sleeping|正在等待客户端发送新请求|
|System lock|正在等待取得一个外部的系统锁。如果当前没有运行多个mysqld服务器同时请求同一个表，那么可以通过增加--skip-external-locking参数来禁止外部系统锁。|
|Upgrading lock|INSERT DELAYED正在尝试取得一个锁表以插入新记录。|
|Updating|正在搜索匹配的记录，并且修改它们。|
|User Lock|正在等待GET_LOCK()。|
|Waiting for tables|该线程得到通知，数据表结构已经被修改了，需要重新打开数据表以取得新的结构。然后，为了能的重新打开数据表，必须等到所有其他线程关闭这个表。以下几种情况下会产生这个通知：FLUSH TABLES tbl_name, ALTER TABLE, RENAME TABLE, REPAIR TABLE, ANALYZE TABLE,或OPTIMIZE TABLE。|
|waiting for handler insert|INSERT DELAYED已经处理完了所有待处理的插入操作，正在等待新的请求。|
