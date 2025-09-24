## 使用binlog恢复数据

```shell
# 查看是否开启了binlog,如果没有开启则无法使用binlog恢复数据
SHOW VARIABLES LIKE 'log_bin';

# 查看binlog的格式
SHOW VARIABLES LIKE 'binlog_format';


# 这将返回一个结果集，其中包含当前的binlog格式。可能的值有：

# ROW： 表示使用行模式（row-based replication），这是推荐的设置，因为它提供了更好的数据一致性。

# STATEMENT： 表示使用语句模式（statement-based replication），在这种模式下，可能会丢失一些数据，因为它仅记录执行的SQL语句。

# MIXED： 表示混合模式（mixed-based replication），在这种模式下，MySQL会根据需要自动切换行模式和语句模式。


# 查看当前的binlog文件,需要记录下来当前的binlog文件名
show master status

# 将binlog写入磁盘,确保之前的操作都已经写入binlog文件,同时结束这个文件写入，开启一个新的binlog文件的写入 
flush logs;

# 将文件转换为可阅读的sql语句
mysqlbinlog --no-defaults -vv --base64-output=decode-rows binlog.000001 > log.sql

# 可以根据时间和语句等信息过滤出需要的信息,

# 例如
#  SET
###   @1=877631 /* INT meta=0 nullable=0 is_null=0 */
###   @2=163 /* INT meta=0 nullable=0 is_null=0 */
###   @3=3133.00000000 /* DECIMAL(32,8) meta=8200 nullable=0 is_null=0 */
###   @4=3133.00000000 /* DECIMAL(32,8) meta=8200 nullable=0 is_null=0 */
###   @5=0.03719203 /* DECIMAL(32,8) meta=8200 nullable=0 is_null=0 */
###   @6=1 /* INT meta=0 nullable=0 is_null=0 */
###   @7=3367.68132378 /* DECIMAL(32,8) meta=8200 nullable=0 is_null=0 */
###   @8=NULL /* JSON meta=4 nullable=1 is_null=1 */
###   @9=NULL /* VARSTRING(240) meta=240 nullable=1 is_null=1 */
### INSERT INTO `dashboard`.`account_detail`

### DELETE FROM `dashboard`.`account_detail`
### WHERE
###   @1=877630 /* INT meta=0 nullable=0 is_null=0 */
###   @2=164 /* INT meta=0 nullable=0 is_null=0 */
###   @3=29904.80736835 /* DECIMAL(32,8) meta=8200 nullable=0 is_null=0 */
###   @4=30180.18648003 /* DECIMAL(32,8) meta=8200 nullable=0 is_null=0 */
###   @5=0.00000000 /* DECIMAL(32,8) meta=8200 nullable=0 is_null=0 */
###   @6=1 /* INT meta=0 nullable=0 is_null=0 */
###   @7=3123.46420993 /* DECIMAL(32,8) meta=8200 nullable=0 is_null=0 */
###   @8=NULL /* JSON meta=4 nullable=1 is_null=1 */
###   @9=NULL /* VARSTRING(240) meta=240 nullable=1 is_null=1 */
### DELETE FROM `dashboard`.`account_detail`
### WHERE


# 将上面的文本解析为sql语句,然后执行即可恢复数据
```
