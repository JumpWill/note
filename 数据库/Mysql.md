#

## 基本命令

### 数据库

| 命令                                                         | 作用                         |
| ------------------------------------------------------------ | :--------------------------- |
| create database db;                                          | 创建数据库                   |
| show databases;                                              | 查看数据库                   |
| show create database db;                                     | 查看数据库信息               |
| alter database db default character set gbk collate gbk_bin; | 修改数据库的编码和排序规则   |
| drop database db;                                            | 删除某一数据库               |
| CREATE DATABASE db DEFAULT CHARACTER SET utf8 COLLATE utf8_general_ci; | 创建的时候指定编码和排序规则 |
| use db                                                       | 选择使用某一数据库           |
| select database();                                           | 查看当前选择的数据库         |

PS:

​ 表格中的db代表你的数据库名字。

​ **要想支持表情存储需要使用  utf8mb4**  

### 表

#### 前置知识

##### 字段类型

###### 数值

| 类型         | 大小                                     | 范围（有符号）                                               | 范围（无符号）                                               | 用途            |
| :----------- | :--------------------------------------- | :----------------------------------------------------------- | :----------------------------------------------------------- | :-------------- |
| TINYINT      | 1 Bytes                                  | (-128，127)                                                  | (0，255)                                                     | 小整数值        |
| SMALLINT     | 2 Bytes                                  | (-32 768，32 767)                                            | (0，65 535)                                                  | 大整数值        |
| MEDIUMINT    | 3 Bytes                                  | (-8 388 608，8 388 607)                                      | (0，16 777 215)                                              | 大整数值        |
| INT或INTEGER | 4 Bytes                                  | (-2 147 483 648，2 147 483 647)                              | (0，4 294 967 295)                                           | 大整数值        |
| BIGINT       | 8 Bytes                                  | (-9,223,372,036,854,775,808，9 223 372 036 854 775 807)      | (0，18 446 744 073 709 551 615)                              | 极大整数值      |
| FLOAT        | 4 Bytes                                  | (-3.402 823 466 E+38，-1.175 494 351 E-38)，0，(1.175 494 351 E-38，3.402 823 466 351 E+38) | 0，(1.175 494 351 E-38，3.402 823 466 E+38)                  | 单精度 浮点数值 |
| DOUBLE       | 8 Bytes                                  | (-1.797 693 134 862 315 7 E+308，-2.225 073 858 507 201 4 E-308)，0，(2.225 073 858 507 201 4 E-308，1.797 693 134 862 315 7 E+308) | 0，(2.225 073 858 507 201 4 E-308，1.797 693 134 862 315 7 E+308) | 双精度 浮点数值 |
| DECIMAL      | 对DECIMAL(M,D) ，如果M>D，为M+2否则为D+2 | 依赖于M和D的值                                               | 依赖于M和D的值                                               | 小数值          |

PS:

​  关键字INT是INTEGER的同义词，关键字DEC是DECIMAL的同义词。

###### 时间

| 类型      | 大小 ( bytes) | 范围                                                         | 格式                | 用途                     |
| :-------- | :------------ | :----------------------------------------------------------- | :------------------ | :----------------------- |
| DATE      | 3             | 1000-01-01/9999-12-31                                        | YYYY-MM-DD          | 日期值                   |
| TIME      | 3             | '-838:59:59'/'838:59:59'                                     | HH:MM:SS            | 时间值或持续时间         |
| YEAR      | 1             | 1901/2155                                                    | YYYY                | 年份值                   |
| DATETIME  | 8             | 1000-01-01 00:00:00/9999-12-31 23:59:59                      | YYYY-MM-DD HH:MM:SS | 混合日期和时间值         |
| TIMESTAMP | 4             | 1970-01-01 00:00:00/2038结束时间是第 **2147483647** 秒，北京时间 **2038-1-19 11:14:07**，格林尼治时间 2038年1月19日 凌晨 03:14:07 | YYYYMMDD HHMMSS     | 混合日期和时间值，时间戳 |

###### 字符串类型

| 类型       | 大小                  | 用途                            |
| :--------- | :-------------------- | :------------------------------ |
| CHAR       | 0-255 bytes           | 定长字符串                      |
| VARCHAR    | 0-65535 bytes         | 变长字符串                      |
| TINYBLOB   | 0-255 bytes           | 不超过 255 个字符的二进制字符串 |
| TINYTEXT   | 0-255 bytes           | 短文本字符串                    |
| BLOB       | 0-65 535 bytes        | 二进制形式的长文本数据          |
| TEXT       | 0-65 535 bytes        | 长文本数据                      |
| MEDIUMBLOB | 0-16 777 215 bytes    | 二进制形式的中等长度文本数据    |
| MEDIUMTEXT | 0-16 777 215 bytes    | 中等长度文本数据                |
| LONGBLOB   | 0-4 294 967 295 bytes | 二进制形式的极大文本数据        |
| LONGTEXT   | 0-4 294 967 295 bytes | 极大文本数据                    |

PS：

​  char(n) 和 varchar(n) 中括号中 n 代表字符的个数，并不代表字节个数，比如 CHAR(30) 就可以存储 30 个字符。

##### 字段约束

| 名称           | 释义                 |
| -------------- | -------------------- |
| unique         | 不可重复(可以多个列) |
| not null       | 不能为空             |
| default        | 存在默认值           |
| primary        | 主键约束(可以多个列) |
| foreign key    | 外键约束             |
| auto_increment | 自增类型             |

一个例子：

一个文章表，包含id 主键，title不为空，id和title一起不能重复，auther_id 外键关联到作者id。

```mysql
create table essay(
   id INT NOT NULL AUTO_INCREMENT,
   title VARCHAR(100) NOT NULL,
   author_id VARCHAR(40) NOT NULL,
   create_time DATE,
   unique(title,id),
   foreign key(author_id) references auther(id),
   PRIMARY KEY (id,xxxx)
);
```

##### 存储引擎

不同的存储引擎支持的功能有所不用，可通过以下命令查看MySQL支持的存储引擎。

```mysql
# 查看当前所支持的存储引擎
show engines
# 查看表的创建语句，其中就有存储引擎的信息，mysql在5.5之后的默认存储引擎是InnorDB
show create table table_name 
```

下面是对比较一些存储引擎。

| 功能         | MylSAM | MEMORY | InnoDB | Archive |
| ------------ | ------ | ------ | ------ | ------- |
| 存储限制     | 256TB  | RAM    | 64TB   | None    |
| 支持事务     | No     | No     | Yes    | No      |
| 支持全文索引 | Yes    | No     | No     | No      |
| 支持树索引   | Yes    | Yes    | Yes    | No      |
| 支持哈希索引 | No     | Yes    | No     | No      |
| 支持数据缓存 | No     | N/A    | Yes    | No      |
| 支持外键     | No     | No     | Yes    | No      |

###### InnoDB

InnoDB是一种兼顾高可靠性和高性能的通用存储引擎,在MySQL 5.5之后, InnoDB是默认的MySQL存储引擎。

支持事务，行级锁，外键·。

存储结构：表空间 段 区 页 行(trx id 最后一次事务的id)。

![1645028724724](C:\Users\will\AppData\Roaming\Typora\typora-user-images\1645028724724.png)

###### MyIsam

不支持事务，不支持外键，不支持表锁，支持行锁，访问速度快。

文件存储信息(xxx.sdi 表结构信息  xxx.myd 存储的信息 xxx.myi 索引信息 )

###### Memory

存在内存中，访问速度贼快，支持hash索引。

#### 新增数据表

​     create table 'table_name'(

​      'column1'  type    字段约束

​        ...

​      )  engine =存储引擎

示例

```mysql
create table essay(
   id INT NOT NULL AUTO_INCREMENT,
   title VARCHAR(100) NOT NULL,
   author_id VARCHAR(40) NOT NULL,
   create_time DATE,
   unique(title,id),
   foreign key(author_id) references auther(id),
   PRIMARY KEY (id,xxxx)
);
```

#### 删除数据表

```mysql
drop table table_name
drop table if exists table_name；
```

#### 查看数据表

```mysql
# 查看表结构
show [FULL] columns from db.tablename；
# 查看具体某一列
describe table_name column_name 
```

#### 修改数据表

修改数据表，会包括修改字段类型，添加约束，添加索引等。

```mysql
ALTER TABLE <表名> [修改内容:]

修改内容:
{ ADD COLUMN <列名> <类型>
| CHANGE COLUMN <旧列名> <新列名> <新列类型>
| ALTER COLUMN <列名> { SET DEFAULT <默认值> | DROP DEFAULT }
| MODIFY COLUMN <列名> <类型>
| DROP COLUMN <列名>
| RENAME TO <新表名>
| CHARACTER SET <字符集名>
| COLLATE <校对规则名> }
```

举多个例子：

```mysql
alter table essay change title name varchar(100);
alter table essay drop column name;
alter table essay RENAME TO article;
```

#### 重命名数据表

```mysql
rename table old_name to new_name
```

#### 增删查改

##### 增

```mysql
#指定列和值，列和值的顺序需要对应
insert into table (列名1,列名2...) values  (列值1,列值2...),(列值1,列值2;..);
# 只是指定值，值的顺序需要和数据表的列的顺序一致
insert into table values (列值1,列值2...),(列值1,列值2;..);
```

PS:

​ 插入的数据的类型为字符创或者日期的时候，需要加引号，且数据大小应该遵守表的设计的限制。

##### 删

```mysql
# 删除数据，如果不加后面的限制条件，则会将该数据表的所有数据删除
delete from table [where 限制条件]
```

##### 改

```mysql
# 修改数据，如果不加限制条件，泽会将该数据表的所有数据进行修改。
update table set 列名1=值1,,列名2=值2 [where 限制条件]
```

##### 查

查询语句的基本格式如下，下文会将每个部分讲解。

```mysql
# 查询一般包含以下的内容
select 字段列表 from 表列表 where 条件列表 group by 分组字段列表 
having 分组后的条件列表  order by 排序字段列表 
limit 分页参数


# 可以通过 as 列名取一个别名。也可以省略as。
select 列1,列2 as 别名, 列3 '别名2'from table 
# 通过distinct，对一个列的值进行去重。
```

###### 条件(where)

| 字符                  | 说明                               | 实例                  |
| --------------------- | ---------------------------------- | --------------------- |
| >                     | 限制大于                           | age>18                |
| <                     | 限制小于                           | age<18                |
| =                     | 限制 等于                          | age=18                |
| != 或者<>             | 限制不等                           | age!=18               |
| in (值1,值2...)       | 限制值在某些数值内                 | age in (18,19.20)     |
| between start and end | 限制在某一范围，包含最大最小值     | age between 18 and 20 |
| like  通配符          | 用于模糊查询(_单个字符，%多个字符) | like _蛇皮%           |
| is null               | 限制为null                         | boyfriend is null     |

###### 逻辑限制

| 字符         | 说明 | 示例                   |
| ------------ | ---- | ---------------------- |
| and 或者 &&  | 且   | age=18 and gender='女' |
| or 或者 \|\| | 或   | age=18 or gender='女'  |
| not 或者 !   | 非   | not in /               |

###### 分组(group by)

group by只的是按照某一个列的数值进行分租，并且可以使用聚合函数对数据进行聚合。形式如下：

```mysql
select 字段列表 from 表列表 where 条件列表 
group by 分组字段列表  having 分组后的条件列表  
```

where和having区别：

where是分组之前进行过滤，不满足where条件,不参与分组:而having是分组之后对结果进行过滤。

having是对聚合结果进行筛选，而where是对列值进行筛选。

###### 聚合函数

| 函数名 | 含义         |
| ------ | ------------ |
| COUNT  | 统计行的数量 |
| AVG    | 平均数       |
| SUM    | 求累加和     |
| MAX    | 最大值       |
| MIN    | 最小值       |

```mysql
# 使用方式
select 聚合函数(字段) from table
# 举个例子
select 
COUNT(age) "总数",AVG(age) "平均",
SUM(age) "总和",MAX(age) "最大",MIN(age) "最小" 
from student

# 统计学生表中，查询男女人数中大于10的
select gender,COUNT(*) from student group by gender having COUNT(*)>10;
```

PS:

​ ①null不参加聚合查询。

​    ②执行顺序是：where 聚合函数 having。

​    ③ 分组之后，一般查询的是分组字段和聚合字段。

###### 排序（order by）

```mysql
order by 字段1 排序方式1,字段2 排序方式2...
```

| 排序方式 | 释义           |
| -------- | -------------- |
| ASC      | 升序排序(默认) |
| DESC     | 降序排序       |

示例：

```mysql
order by id asc ,name desc
```

###### 分页

```mysql
# start是查询的起始索引=(页码-1)*每页数据量，size则是要返回的数据条数。
limit start,size
```

###### 执行顺序

从前到后： from     where      group by    having    select   order by     limit

##### 连接

```mysql
# 形式如下
select column
from table xxx join table2 on 连接条件
where 限制条件
```

###### 左连接( **LEFT JOIN** )

左边为主表，连接右边，左边对应到右边，如果右边没有则为None。

```mysql
# 查询 学生的班级信息，学生表stu通过class_id 与班级表关联
# 会查到所有学生，没有班级的学生，cname为none
select stu.name name,c.name cname
from stu left join class c on stu.class_id =c.id
```

 ![img](https://www.runoob.com/wp-content/uploads/2014/03/img_leftjoin.gif)

###### 右连接( **RIGHT JOIN** )

右边为主表，连接左边，右边对应到左边，如果左边没有则为None。

 ![img](https://www.runoob.com/wp-content/uploads/2014/03/img_rightjoin.gif)

```mysql
# 查询 学生的班级信息，学生表stu通过class_id 与班级表关联
# 会查到所有班级，如果有学生没有班级，则不会被查询出来
select stu.name name,c.name cname
from stu right join class c on stu.class_id =c.id
```

###### 内连接( **INNER JOIN**)

将左右两边共有的数据进行连接。

 ![img](https://www.runoob.com/wp-content/uploads/2014/03/img_innerjoin.gif)

```mysql
# 查询 学生的班级信息，学生表stu通过class_id 与班级表关联
# 有班级的学生信息
# 显示内连接
select stu.name name,c.name cname
from stu inner join class c on stu.class_id =c.id
# 隐式内连接
select stu.name name,c.name cname
from stu,class c where stu.class_id =c.id
```

###### 自连接

自连接是指自己连接自己，其中可以左右内连接，和上面三个类似只是必须取别名。

##### 联合查询

union，将两个查询(返回的列数据格式要一致)结果，共同返回，

使用union all不去重，单独使用union去重。

```mysql
# 查询age=20的或者为女的学生
select * from student where age =18
union
select * from student where gender="女";
```

##### 子查询

又称嵌套查询，形式如下：

```mysql
# 前面的可以是CRUD中任一
select * from table where clomun = 
(select ...);
```

将子查询按子查询(即后面那个select)的结果分类

###### 单值

即是后面的select返回的是单个值，例如查询到了一个具体学生所有成绩。

```mysql
select * from grades where stu_id = 
(select id from stu where name ="will");
```

###### 多个列值

即后面的select返回的结果是一个列的数据的列表，例如查询到了性别为男的学生所有成绩。

```mysql
# grades表通过stu_id与stu表关联
select * from grades where stu_id = 
(select id from stu where gender = "男");
```

###### 一行数据

即后面的select返回的结果是一个表的某一行数据中的某些数据，例如查询和张三年龄性别相同的学生。

```mysql
# 子查询返回一个的gender，age ，用(gender,age)去接收。
select * from stu where (gender,age) =
(select gender,age from stu where name='张三' );
```

###### 多行多列

即后面的select返回的是多行多列的数据，例如查询与张三(男18)或者小美(女17) 年龄性别相同的学生信息。

```mysql
# 查询出张三和小美的数据，在查stu中与张三或者小美 年龄性别相同的数据。
select * from stu where (gender,age) in
(select gender,age from stu where name="张三" or name="小美")
```

### 函数

```mysql
#函数的使用方式
select function(列值1...) from table
```

#### 字符串

|                 函数                  | 描述                                                         | 实例                                                         |
| :-----------------------------------: | :----------------------------------------------------------- | :----------------------------------------------------------- |
|               ASCII(s)                | 返回字符串 s 的第一个字符的 ASCII 码。                       | `SELECT ASCII(name) AS name FROM Customers`                  |
|            CHAR_LENGTH(s)             | 返回字符串长度。                                             | `SELECT CHAR_LENGTH(name) AS name FROM STU`                  |
|          CHARACTER_LENGTH(s)          | 返回字符长度。                                               | `SELECT CHARACTER_LENGTH(name) AS name FROM STU`             |
|          CONCAT(s1,s2...sn)           | 将字符串连起来。                                             | `SELECT CONCAT(name,nickname) as info from STU`              |
|       CONCAT_WS(x, s1,s2...sn)        | 以间隔x将字符串起来, 例如 ',','a', 'b' 返回a,b。             | `SELECT CONCAT(",",name,nickname) as info from STU`          |
|           FIELD(s,s1,s2...)           | 返回s在后面字符列表位置。                                    | `SELECT FIELD(name,'a','b','c')  as level from STU'`         |
|          FIND_IN_SET(s1,s2)           | 返回在字符串s2中与s1匹配的字符串的位置                       | `SELECT FIND_IN_SET("c", "a,b,c,d,e");`                      |
|              FORMAT(x,n)              | 函数可以将数字 x 进行格式化 "#,###.##", 将 x 保留到小数点后 n 位，最后一位四舍五入。 | 格式化数字 "#,###.##" 形式：`SELECT FORMAT(250500.5634, 2);     -- 输出 250,500.56` |
|          INSERT(s1,x,len,s2)          | 字符串 s2 替换 s1 的 x 位置开始长度为 len 的字符串           | `SELECT INSERT("google.com", 1, 6, "runoob");  -- 输出：runoob.com` |
|             LOCATE(s1,s)              | 从字符串 s 中获取                                            | `SELECT LOCATE('st','myteststring');  -- 5`                  |
|               LCASE(s)                | 将字符串 s 的所有字母变成小写字母                            | `SELECT LCASE('RUNOOB') -- runoob`                           |
|               LEFT(s,n)               | 返回字符串 s 的前 n 个字符                                   | `SELECT LEFT('runoob',2) -- ru`                              |
|               LOWER(s)                | 将字符串 s 的所有字母变成小写字母                            | `SELECT LOWER('RUNOOB') -- runoob`                           |
|            LPAD(s1,len,s2)            | 在字符串 s1 的开始处填充字符串 s2，使字符串长度达到 len      | `SELECT LPAD('abc',5,'xx') -- xxabc`                         |
|               LTRIM(s)                | 去掉字符串 s 开始处的空格                                    | `SELECT LTRIM("    RUNOOB") AS data;-- RUNOOB`               |
|             MID(s,n,len)              | 从字符串 s 的 n 位置截取长度为 len 的子字符串，同 SUBSTRING(s,n,len) | `SELECT MID("RUNOOB", 2, 3) AS data; -- UNO`                 |
|           POSITION(s1 IN s)           | 从字符串 s 中获取 s1 的开始位置                              | `SELECT POSITION('b' in 'abc') -- 2`                         |
|              REPEAT(s,n)              | 将字符串 s 重复 n 次                                         | `SELECT REPEAT('runoob',3) -- runoobrunoobrunoob`            |
|           REPLACE(s,s1,s2)            | 将字符串 s2 替代字符串 s 中的字符串 s1                       | `SELECT REPLACE('abc','a','x') --xbc`                        |
|              REVERSE(s)               | 将字符串s的顺序反过来                                        | `SELECT REVERSE('abc') -- cba`                               |
|              RIGHT(s,n)               | 返回字符串 s 的后 n 个字符                                   | `SELECT RIGHT('runoob',2) -- ob`                             |
|            RPAD(s1,len,s2)            | 在字符串 s1 的结尾处添加字符串 s2，使字符串的长度达到 len    | `SELECT RPAD('abc',5,'xx') -- abcxx`                         |
|               RTRIM(s)                | 去掉字符串 s 结尾处的空格                                    | `SELECT RTRIM("RUNOOB     ") AS RightTrimmedString;   -- RUNOOB` |
|               SPACE(n)                | 返回 n 个空格                                                | `SELECT SPACE(10);`                                          |
|             STRCMP(s1,s2)             | 比较字符串 s1 和 s2，如果 s1 与 s2 相等返回 0 ，如果 s1>s2 返回 1，如果 s1<s2 返回 -1 | `SELECT STRCMP("runoob", "runoob");  -- 0`                   |
|       SUBSTR(s, start, length)        | 从字符串 s 的 start 位置截取长度为 length 的子字符串         | `SELECT SUBSTR("RUNOOB", 2, 3) AS data; -- UNO`              |
|      SUBSTRING(s, start, length)      | 从字符串 s 的 start 位置截取长度为 length 的子字符串         | `SELECT SUBSTRING("RUNOOB", 2, 3) AS data; -- UNO`           |
| SUBSTRING_INDEX(s, delimiter, number) | 返回从字符串 s 的第 number 个出现的分隔符 delimiter 之后的子串。 如果 number 是正数，返回第 number 个字符左边的字符串。 如果 number 是负数，返回第(number 的绝对值(从右边数))个字符右边的字符串。 | `SELECT SUBSTRING_INDEX('a*b','*',1) -- a SELECT SUBSTRING_INDEX('a*b','*',-1)  -- b SELECT SUBSTRING_INDEX(SUBSTRING_INDEX('a*b*c*d*e','*',3),'*',-1)  -- c` |
|                TRIM(s)                | 去掉字符串 s 开始和结尾处的空格                              | `SELECT TRIM('    RUNOOB    ') AS data;`                     |
|               UCASE(s)                | 将字符串转换为大写                                           | `SELECT UCASE("runoob"); -- RUNOOB`                          |
|               UPPER(s)                | 将字符串转换为大写                                           | `SELECT UPPER("runoob"); -- RUNOOB`                          |

#### 数值

| 函数名                             | 描述                                                         | 实例                                                         |
| :--------------------------------- | :----------------------------------------------------------- | :----------------------------------------------------------- |
| ABS(x)                             | 返回 x 的绝对值                                              | `SELECT ABS(-1) -- 返回1`                                    |
| ACOS(x)                            | 求 x 的反余弦值（单位为弧度），x 为一个数值                  | `SELECT ACOS(0.25);`                                         |
| ASIN(x)                            | 求反正弦值（单位为弧度），x 为一个数值                       | `SELECT ASIN(0.25);`                                         |
| ATAN(x)                            | 求反正切值（单位为弧度），x 为一个数值                       | `SELECT ATAN(2.5);`                                          |
| ATAN2(n, m)                        | 求反正切值（单位为弧度）                                     | `SELECT ATAN2(-0.8, 2);`                                     |
| AVG(expression)                    | 返回一个表达式的平均值，expression 是一个字段                | `SELECT AVG(Price) AS AveragePrice FROM Products;`           |
| CEIL(x)                            | 返回大于或等于 x 的最小整数                                  | `SELECT CEIL(1.5) -- 返回2`                                  |
| CEILING(x)                         | 返回大于或等于 x 的最小整数                                  | `SELECT CEILING(1.5); -- 返回2`                              |
| COS(x)                             | 求余弦值(参数是弧度)                                         | `SELECT COS(2);`                                             |
| COT(x)                             | 求余切值(参数是弧度)                                         | `SELECT COT(6);`                                             |
| COUNT(expression)                  | 返回查询的记录总数，expression 参数是一个字段或者 * 号       | `SELECT COUNT(ProductID) AS NumberOfProducts FROM Products;` |
| DEGREES(x)                         | 将弧度转换为角度                                             | `SELECT DEGREES(3.1415926535898) -- 180`                     |
| n DIV m                            | 整除，n 为被除数，m 为除数                                   | 计算 10 除于 5：`SELECT 10 DIV 5;  -- 2`                     |
| EXP(x)                             | 返回 e 的 x 次方                                             | `SELECT EXP(3) -- 20.085536923188`                           |
| FLOOR(x)                           | 返回小于或等于 x 的最大整数                                  | `SELECT FLOOR(1.5) -- 返回1`                                 |
| GREATEST(expr1, expr2, expr3, ...) | 返回列表(数值或者字符)中的最大值                             | `SELECT GREATEST("Google", "Runoob", "Apple");   -- Runoob`  |
| LEAST(expr1, expr2, expr3, ...)    | 返回列表(数值或者字符)中的最小值                             | `SELECT LEAST("Google", "Runoob", "Apple");   -- Apple`      |
| LN                                 | 返回数字的自然对数，以 e 为底。                              | `SELECT LN(2);  -- 0.6931471805599453`                       |
| LOG(x) 或 LOG(base, x)             | 返回自然对数(以 e 为底的对数)，如果带有 base 参数，则 base 为指定带底数。 | `SELECT LOG(20.085536923188) -- 3 SELECT LOG(2, 4); -- 2`    |
| LOG10(x)                           | 返回以 10 为底的对数                                         | `SELECT LOG10(100) -- 2`                                     |
| LOG2(x)                            | 返回以 2 为底的对数                                          | `SELECT LOG2(6);  -- 2.584962500721156`                      |
| MAX(expression)                    | 返回字段 expression 中的最大值                               | `SELECT MAX(Price) AS LargestPrice FROM Products;`           |
| MIN(expression)                    | 返回字段 expression 中的最小值                               | `SELECT MIN(Price) AS MinPrice FROM Products;`               |
| MOD(x,y)                           | 返回 x 除以 y 以后的余数                                     | `SELECT MOD(5,2) -- 1`                                       |
| PI()                               | 返回圆周率(3.141593）                                        | `SELECT PI() --3.141593`                                     |
| POW(x,y)                           | 返回 x 的 y 次方                                             | `SELECT POW(2,3) -- 8`                                       |
| POWER(x,y)                         | 返回 x 的 y 次方                                             | `SELECT POWER(2,3) -- 8`                                     |
| RADIANS(x)                         | 将角度转换为弧度                                             | `SELECT RADIANS(180) -- 3.1415926535898`                     |
| RAND()                             | 返回 0 到 1 的随机数                                         | `SELECT RAND() --0.93099315644334`                           |
| ROUND(x)                           | 返回离 x 最近的整数                                          | `SELECT ROUND(1.23456) --1`                                  |
| SIGN(x)                            | 返回 x 的符号，x 是负数、0、正数分别返回 -1、0 和 1          | `SELECT SIGN(-10) -- (-1)`                                   |
| SIN(x)                             | 求正弦值(参数是弧度)                                         | `SELECT SIN(RADIANS(30)) -- 0.5`                             |
| SQRT(x)                            | 返回x的平方根                                                | `SELECT SQRT(25) -- 5`                                       |
| SUM(expression)                    | 返回指定字段的总和                                           | `SELECT SUM(Quantity) AS TotalItemsOrdered FROM OrderDetails;` |
| TAN(x)                             | 求正切值(参数是弧度)                                         | `SELECT TAN(1.75);  -- -5.52037992250933`                    |
| TRUNCATE(x,y)                      | 返回数值 x 保留到小数点后 y 位的值（与 ROUND 最大的区别是不会进行四舍五入） | `SELECT TRUNCATE(1.23456,3) -- 1.234`                        |

#### 日期

| 函数名                                            | 描述                                                         | 实例                                                         |
| :------------------------------------------------ | :----------------------------------------------------------- | :----------------------------------------------------------- |
| ADDDATE(d,n)                                      | 计算起始日期 d 加上 n 天的日期                               | `SELECT ADDDATE("2017-06-15", INTERVAL 10 DAY); ->2017-06-25` |
| ADDTIME(t,n)                                      | n 是一个时间表达式，时间 t 加上时间表达式 n                  | 加 5 秒：`SELECT ADDTIME('2011-11-11 11:11:11', 5); ->2011-11-11 11:11:16 (秒)`添加 2 小时, 10 分钟, 5 秒:`SELECT ADDTIME("2020-06-15 09:34:21", "2:10:5");  -> 2020-06-15 11:44:26` |
| CURDATE()                                         | 返回当前日期                                                 | `SELECT CURDATE(); -> 2018-09-19`                            |
| CURRENT_DATE()                                    | 返回当前日期                                                 | `SELECT CURRENT_DATE(); -> 2018-09-19`                       |
| CURRENT_TIME                                      | 返回当前时间                                                 | `SELECT CURRENT_TIME(); -> 19:59:02`                         |
| CURRENT_TIMESTAMP()                               | 返回当前日期和时间                                           | `SELECT CURRENT_TIMESTAMP() -> 2018-09-19 20:57:43`          |
| CURTIME()                                         | 返回当前时间                                                 | `SELECT CURTIME(); -> 19:59:02`                              |
| DATE()                                            | 从日期或日期时间表达式中提取日期值                           | `SELECT DATE("2017-06-15");     -> 2017-06-15`               |
| DATEDIFF(d1,d2)                                   | 计算日期 d1->d2 之间相隔的天数                               | `SELECT DATEDIFF('2001-01-01','2001-02-02') -> -32`          |
| DATE_ADD(d，INTERVAL expr type)                   | 计算起始日期 d 加上一个时间段后的日期，type 值可以是：MICROSECONDSECONDMINUTEHOURDAYWEEKMONTHQUARTERYEARSECOND_MICROSECONDMINUTE_MICROSECONDMINUTE_SECONDHOUR_MICROSECONDHOUR_SECONDHOUR_MINUTEDAY_MICROSECONDDAY_SECONDDAY_MINUTEDAY_HOURYEAR_MONTH | `SELECT DATE_ADD("2017-06-15", INTERVAL 10 DAY);     -> 2017-06-25 SELECT DATE_ADD("2017-06-15 09:34:21", INTERVAL 15 MINUTE); -> 2017-06-15 09:49:21 SELECT DATE_ADD("2017-06-15 09:34:21", INTERVAL -3 HOUR); ->2017-06-15 06:34:21 SELECT DATE_ADD("2017-06-15 09:34:21", INTERVAL -3 MONTH); ->2017-04-15` |
| DATE_FORMAT(d,f)                                  | 按表达式 f的要求显示日期 d                                   | `SELECT DATE_FORMAT('2011-11-11 11:11:11','%Y-%m-%d %r') -> 2011-11-11 11:11:11 AM` |
| DATE_SUB(date,INTERVAL expr type)                 | 函数从日期减去指定的时间间隔。                               | Orders 表中 OrderDate 字段减去 2 天：`SELECT OrderId,DATE_SUB(OrderDate,INTERVAL 2 DAY) AS OrderPayDate FROM Orders` |
| DAY(d)                                            | 返回日期值 d 的日期部分                                      | `SELECT DAY("2017-06-15");   -> 15`                          |
| DAYNAME(d)                                        | 返回日期 d 是星期几，如 Monday,Tuesday                       | `SELECT DAYNAME('2011-11-11 11:11:11') ->Friday`             |
| DAYOFMONTH(d)                                     | 计算日期 d 是本月的第几天                                    | `SELECT DAYOFMONTH('2011-11-11 11:11:11') ->11`              |
| DAYOFWEEK(d)                                      | 日期 d 今天是星期几，1 星期日，2 星期一，以此类推            | `SELECT DAYOFWEEK('2011-11-11 11:11:11') ->6`                |
| DAYOFYEAR(d)                                      | 计算日期 d 是本年的第几天                                    | `SELECT DAYOFYEAR('2011-11-11 11:11:11') ->315`              |
| EXTRACT(type FROM d)                              | 从日期 d 中获取指定的值，type 指定返回的值。 type可取值为： MICROSECONDSECONDMINUTEHOURDAYWEEKMONTHQUARTERYEARSECOND_MICROSECONDMINUTE_MICROSECONDMINUTE_SECONDHOUR_MICROSECONDHOUR_SECONDHOUR_MINUTEDAY_MICROSECONDDAY_SECONDDAY_MINUTEDAY_HOURYEAR_MONTH | `SELECT EXTRACT(MINUTE FROM '2011-11-11 11:11:11')  -> 11`   |
| FROM_DAYS(n)                                      | 计算从 0000 年 1 月 1 日开始 n 天后的日期                    | `SELECT FROM_DAYS(1111) -> 0003-01-16`                       |
| HOUR(t)                                           | 返回 t 中的小时值                                            | `SELECT HOUR('1:2:3') -> 1`                                  |
| LAST_DAY(d)                                       | 返回给给定日期的那一月份的最后一天                           | `SELECT LAST_DAY("2017-06-20"); -> 2017-06-30`               |
| LOCALTIME()                                       | 返回当前日期和时间                                           | `SELECT LOCALTIME() -> 2018-09-19 20:57:43`                  |
| LOCALTIMESTAMP()                                  | 返回当前日期和时间                                           | `SELECT LOCALTIMESTAMP() -> 2018-09-19 20:57:43`             |
| MAKEDATE(year, day-of-year)                       | 基于给定参数年份 year 和所在年中的天数序号 day-of-year 返回一个日期 | `SELECT MAKEDATE(2017, 3); -> 2017-01-03`                    |
| MAKETIME(hour, minute, second)                    | 组合时间，参数分别为小时、分钟、秒                           | `SELECT MAKETIME(11, 35, 4); -> 11:35:04`                    |
| MICROSECOND(date)                                 | 返回日期参数所对应的微秒数                                   | `SELECT MICROSECOND("2017-06-20 09:34:00.000023"); -> 23`    |
| MINUTE(t)                                         | 返回 t 中的分钟值                                            | `SELECT MINUTE('1:2:3') -> 2`                                |
| MONTHNAME(d)                                      | 返回日期当中的月份名称，如 November                          | `SELECT MONTHNAME('2011-11-11 11:11:11') -> November`        |
| MONTH(d)                                          | 返回日期d中的月份值，1 到 12                                 | `SELECT MONTH('2011-11-11 11:11:11') ->11`                   |
| NOW()                                             | 返回当前日期和时间                                           | `SELECT NOW() -> 2018-09-19 20:57:43`                        |
| PERIOD_ADD(period, number)                        | 为 年-月 组合日期添加一个时段                                | `SELECT PERIOD_ADD(201703, 5);    -> 201708`                 |
| PERIOD_DIFF(period1, period2)                     | 返回两个时段之间的月份差值                                   | `SELECT PERIOD_DIFF(201710, 201703); -> 7`                   |
| QUARTER(d)                                        | 返回日期d是第几季节，返回 1 到 4                             | `SELECT QUARTER('2011-11-11 11:11:11') -> 4`                 |
| SECOND(t)                                         | 返回 t 中的秒钟值                                            | `SELECT SECOND('1:2:3') -> 3`                                |
| SEC_TO_TIME(s)                                    | 将以秒为单位的时间 s 转换为时分秒的格式                      | `SELECT SEC_TO_TIME(4320) -> 01:12:00`                       |
| STR_TO_DATE(string, format_mask)                  | 将字符串转变为日期                                           | `SELECT STR_TO_DATE("August 10 2017", "%M %d %Y"); -> 2017-08-10` |
| SUBDATE(d,n)                                      | 日期 d 减去 n 天后的日期                                     | `SELECT SUBDATE('2011-11-11 11:11:11', 1) ->2011-11-10 11:11:11 (默认是天)` |
| SUBTIME(t,n)                                      | 时间 t 减去 n 秒的时间                                       | `SELECT SUBTIME('2011-11-11 11:11:11', 5) ->2011-11-11 11:11:06 (秒)` |
| SYSDATE()                                         | 返回当前日期和时间                                           | `SELECT SYSDATE() -> 2018-09-19 20:57:43`                    |
| TIME(expression)                                  | 提取传入表达式的时间部分                                     | `SELECT TIME("19:30:10"); -> 19:30:10`                       |
| TIME_FORMAT(t,f)                                  | 按表达式 f 的要求显示时间 t                                  | `SELECT TIME_FORMAT('11:11:11','%r') 11:11:11 AM`            |
| TIME_TO_SEC(t)                                    | 将时间 t 转换为秒                                            | `SELECT TIME_TO_SEC('1:12:00') -> 4320`                      |
| TIMEDIFF(time1, time2)                            | 计算时间差值                                                 | `mysql> SELECT TIMEDIFF("13:10:11", "13:10:10"); -> 00:00:01 mysql> SELECT TIMEDIFF('2000:01:01 00:00:00',    ->                 '2000:01:01 00:00:00.000001');        -> '-00:00:00.000001' mysql> SELECT TIMEDIFF('2008-12-31 23:59:59.000001',    ->                 '2008-12-30 01:01:01.000002');        -> '46:58:57.999999'` |
| TIMESTAMP(expression, interval)                   | 单个参数时，函数返回日期或日期时间表达式；有2个参数时，将参数加和 | `mysql> SELECT TIMESTAMP("2017-07-23",  "13:10:11"); -> 2017-07-23 13:10:11 mysql> SELECT TIMESTAMP('2003-12-31');        -> '2003-12-31 00:00:00' mysql> SELECT TIMESTAMP('2003-12-31 12:00:00','12:00:00');        -> '2004-01-01 00:00:00'` |
| TIMESTAMPDIFF(unit,datetime_expr1,datetime_expr2) | 计算时间差，返回 datetime_expr2 − datetime_expr1 的时间差    | `mysql> SELECT TIMESTAMPDIFF(DAY,'2003-02-01','2003-05-01');   // 计算两个时间相隔多少天        -> 89 mysql> SELECT TIMESTAMPDIFF(MONTH,'2003-02-01','2003-05-01');   // 计算两个时间相隔多少月        -> 3 mysql> SELECT TIMESTAMPDIFF(YEAR,'2002-05-01','2001-01-01');    // 计算两个时间相隔多少年        -> -1 mysql> SELECT TIMESTAMPDIFF(MINUTE,'2003-02-01','2003-05-01 12:05:55');  // 计算两个时间相隔多少分钟        -> 128885` |
| TO_DAYS(d)                                        | 计算日期 d 距离 0000 年 1 月 1 日的天数                      | `SELECT TO_DAYS('0001-01-01 01:01:01') -> 366`               |
| WEEK(d)                                           | 计算日期 d 是本年的第几个星期，范围是 0 到 53                | `SELECT WEEK('2011-11-11 11:11:11') -> 45`                   |
| WEEKDAY(d)                                        | 日期 d 是星期几，0 表示星期一，1 表示星期二                  | `SELECT WEEKDAY("2017-06-15"); -> 3`                         |
| WEEKOFYEAR(d)                                     | 计算日期 d 是本年的第几个星期，范围是 0 到 53                | `SELECT WEEKOFYEAR('2011-11-11 11:11:11') -> 45`             |
| YEAR(d)                                           | 返回年份                                                     | `SELECT YEAR("2017-06-15"); -> 2017`                         |
| YEARWEEK(date, mode)                              | 返回年份及第几周（0到53），mode 中 0 表示周天，1表示周一，以此类推 | `SELECT YEARWEEK("2017-06-15"); -> 201724`                   |

#### 高级函数

| 函数名                                                       | 描述                                                         | 实例                                                         |
| :----------------------------------------------------------- | :----------------------------------------------------------- | :----------------------------------------------------------- |
| BIN(x)                                                       | 返回 x 的二进制编码                                          | 15 的 2 进制编码:`SELECT BIN(15); -- 1111`                   |
| BINARY(s)                                                    | 将字符串 s 转换为二进制字符串                                | `SELECT BINARY "RUNOOB"; -> RUNOOB`                          |
| `CASE expression WHEN condition1 THEN result1    WHEN condition2 THEN result2   ...    WHEN conditionN THEN resultN    ELSE result END` | CASE 表示函数开始，END 表示函数结束。如果 condition1 成立，则返回 result1, 如果 condition2 成立，则返回 result2，当全部不成立则返回 result，而当有一个成立之后，后面的就不执行了。 | `SELECT case when age<18 then "未成年" when age>=18 and age<40 then "成年" else "老年" end 成分 from STU` |
| CAST(x AS type)                                              | 转换数据类型                                                 | 字符串日期转换为日期：`SELECT CAST("2017-08-29" AS DATE); -> 2017-08-29` |
| COALESCE(expr1, expr2, ...., expr_n)                         | 返回参数中的第一个非空表达式（从左向右）                     | `SELECT COALESCE(NULL, NULL, NULL, 'runoob.com', NULL, 'google.com'); -> runoob.com` |
| CONNECTION_ID()                                              | 返回唯一的连接 ID                                            | `SELECT CONNECTION_ID(); -> 4292835`                         |
| CONV(x,f1,f2)                                                | 返回 f1 进制数变成 f2 进制数                                 | `SELECT CONV(15, 10, 2); -> 1111`                            |
| CONVERT(s USING cs)                                          | 函数将字符串 s 的字符集变成 cs                               | `SELECT CHARSET('ABC') ->utf-8     SELECT CHARSET(CONVERT('ABC' USING gbk)) ->gbk` |
| CURRENT_USER()                                               | 返回当前用户                                                 | `SELECT CURRENT_USER(); -> guest@%`                          |
| DATABASE()                                                   | 返回当前数据库名                                             | `SELECT DATABASE();    -> runoob`                            |
| if(条件,a,b)                                                 | 如果表达式 expr 成立，返回结果 v1；否则，返回结果 v2。       | `SELECT IF(1 > 0,'正确','错误')     ->正确`                  |
| [IFNULL(v1,v2)](https://www.runoob.com/mysql/mysql-func-ifnull.html) | 如果 v1 的值不为 NULL，则返回 v1，否则返回 v2。              | `SELECT IFNULL(null,'Hello Word') ->Hello Word`              |
| ISNULL(expression)                                           | 判断表达式是否为 NULL                                        | `SELECT ISNULL(NULL); ->1`                                   |
| LAST_INSERT_ID()                                             | 返回最近生成的 AUTO_INCREMENT 值                             | `SELECT LAST_INSERT_ID(); ->6`                               |
| NULLIF(expr1, expr2)                                         | 比较两个字符串，如果字符串 expr1 与 expr2 相等 返回 NULL，否则返回 expr1 | `SELECT NULLIF(25, 25); ->`                                  |
| SESSION_USER()                                               | 返回当前用户                                                 | `SELECT SESSION_USER(); -> guest@%`                          |
| SYSTEM_USER()                                                | 返回当前用户                                                 | `SELECT SYSTEM_USER(); -> guest@%`                           |
| USER()                                                       | 返回当前用户                                                 | `SELECT USER(); -> guest@%`                                  |
| VERSION()                                                    | 返回数据库的版本号                                           | `SELECT VERSION() -> 5.6.34`                                 |

### 事件

## 事务

 事务是指是程序中一系列严密的逻辑操作，而且所有操作必须全部成功完成，否则在每个操作中所作的所有更改都会被撤消。可以通俗理解为：就是把多件事情当做一件事情来处理，好比大家同在一条飞机上，要活一起活，要完一起完 。

#### 四大特性

| 特性                  |                             说明                             |
| :-------------------- | :----------------------------------------------------------: |
| 一致性（Consistency） | 一致性是指事务必须使数据库从一个一致性状态变换到另一个一致性状态，也就是说一个事务执行之前和执行之后都必须处于一致性状态。 |
| 隔离性（隔离）        | 隔离性是当多个用户并发访问数据库时，比如操作同一张表时，数据库为每一个用户开启的事务，不能被其他事务的操作所干扰，多个并发事务之间要相互隔离。 |
| 持久性（耐久性）      | 持久性是指一个事务一旦被提交了，那么对数据库中的数据的改变就是永久性的，即便是在数据库系统遇到故障的情况下也不会丢失提交事务的操作。 |
| 原子性（Atomicity     | 原子性是指事务包含的所有操作要么全部成功，要么全部失败回滚，这和前面两篇博客介绍事务的功能是一样的概念，因此事务的操作如果成功就必须要完全应用到数据库，如果操作失败则不能对数据库有任何影响。 |

#### 并发中的问题

| 名称       |                             解释                             |
| ---------- | :----------------------------------------------------------: |
| 脏读       |                事务A读到了事务B还未提交的数据                |
| 不可重复读 | 事务A读取了一条数据，事务B将此数据修改了，事务A再次读取该数据，与第一次读的不一样。 |
| 幻读       | 事务A按照条件查询不到某数据，然后插入数据时发现该数据已经有了，像发生了幻觉。 |

#### 事务隔离级别

```mysql
# 查看隔离级别
select @@transaction_isolation
# 设置当前会话的隔离级别
set session transaction isolation level read commitd
#
```

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

  ![1645026306052](C:\Users\will\AppData\Roaming\Typora\typora-user-images\1645026306052.png)

## 结构

![1645027555503](C:\Users\will\AppData\Roaming\Typora\typora-user-images\1645027555503.png)

## 索引

索引(index) 是帮助MySQL,高效获取数据的数据结构(有序)。在数据之外,数据库系统还维护着满足特定查找算法的数据结构,这些数据结构以某种方式引用(指向)数据，这样就可以在这些数据结构 上实现高级查找算法,这种数据结构就是索引。

索引可以提高检索效率，减少IO次数。提高排序效率，降低排序成本，降低CPU的消耗，但是会占用空间，以及对删除,更新,插入的效率。

### 索引方式

#### B+Tree

B-Tree是最常见的索引类型，所有值（被索引的列）都是排过序的，每个叶节点到跟节点距离相等。所以B-Tree适合用来查找某一范围内的数据，而且可以直接支持数据排序（ORDER BY）
B-Tree在MyISAM里的形式和Innodb稍有不同：
MyISAM表数据文件和索引文件是分离的，索引文件仅保存数据记录的磁盘地址
InnoDB表数据文件本身就是主索引，叶节点data域保存了完整的数据记录。

![](C:\Users\will\Desktop\未命名图片.png)

![](C:\Users\will\Desktop\未命名图片.png)

B-TREE：

​   因为每个节点上都会存储数据，就会导致每一个节点上面的degree小，从而是存储的数据量会变得很小。 举个例子：只考虑图中的 16和data 这样的数据的大小，假设为1K，那么第三层存储的数。

B+tree：

​  不是叶子节点的只存储关键的比较的数据值。并且这个值占存储空间越小越好，因为这样就会可以使非叶子节点的degree更大，比如   16K中   假设 指针+比较值=10B 和  等于 5B  ，5B对应所存储的就是10B存储的数据量的4倍，因为 第一层是两倍 第二层也是两倍，第三层存储数据degree一样。举个例子：每个节点的大小为16k(mysql每次读取的大小为16K)，而 指针+比较值 假设为10B，简单计算degree=16*1024/10 =1600  而第二层 就是 1600*1600 第三层是数据层 每个数据大小为1K，那么每个节点存储16个，三层下来就能存储 1600*1600*16=40960000个数据。

#### Hash索引

1.仅支持"=","IN"和"<=>"精确查询，不能使用范围查询：
由于Hash索引比较的是进行Hash运算之后的Hash值，所以它只能用于等值的过滤，不能用于基于范围的过滤，因为经过相应的Hash算法处理之后的Hash
2.不支持排序：
由于Hash索引中存放的是经过Hash计算之后的Hash值，而且Hash值的大小关系并不一定和Hash运算前的键值完全一样，所以数据库无法利用索引的数据来避免任何排序运算
3.在任何时候都不能避免表扫描：
由于Hash索引比较的是进行Hash运算之后的Hash值，所以即使取满足某个Hash键值的数据的记录条数，也无法从Hash索引中直接完成查询，还是要通过访问表中的实际数据进行相应的比较，并得到相应的结果
4.检索效率高，索引的检索可以一次定位，不像B-Tree索引需要从根节点到枝节点，最后才能访问到页节点这样多次的IO访问，所以Hash索引的查询效率要远高于B-Tree索引
5.只有Memory引擎支持显式的Hash索引，但是它的Hash是nonunique的，冲突太多时也会影响查找性能。Memory引擎默认的索引类型即是Hash索引，虽然它也支持B-Tree索引

#### R-Tree索引

R-Tree在MySQL很少使用，仅支持geometry数据类型，支持该类型的存储引擎只有MyISAM、BDb、InnoDb、NDb、Archive几种。

#### FULL-TEXT索引

如ES

#### 支持情况

|   索引    |  InnoDB   | MyIsam | Memory |
| :-------: | :-------: | :----: | :----: |
|  B+tree   |     √     |   √    |   √    |
|  R-Tree   |     ×     |   ×    |   √    |
|   HASH    |     ×     |   √    |   ×    |
| FULL-TEXT | 5.6后支持 |   √    |   ×    |

### 索引种类

#### 普通索引

在一个普通字段上建立的索引，可以有多个。

#### 唯一索引

针对不重复的数据创建的索引，可以有多个，关键字为unique。

如果为某个字段加了unique的约束，会创建对应的唯一索引。

#### 主键索引

针对表的主键创建的索引，默认自动创建且仅有一个，关键字为primary。

#### 组合索引

将几个字段联合创建的索引。

#### 全文索引

Mysql中用的少，且例如ES(作为搜索数据库)中用的更为好。

### 名词解析

#### 聚簇索引与非聚簇索引

##### 聚簇索引

​    B+Tree是根据主键索引的，叶子节点上的数据即为要查询行的数据，一个表仅仅只有一个聚簇索引。

##### 非聚簇索引(辅助索引)

​    叶子节点上的数据为主键，通过聚簇索引得到的主键还需要通过查一下聚簇索引才能得到数据(这个过程叫回表)。一个表可以有多个非聚簇索引。

![1645109151313](C:\Users\will\AppData\Roaming\Typora\typora-user-images\1645109151313.png)

### 索引操作

#### 创建

```mysql
# 创建索引 索引种类                 索引名称      表名        在哪些列值上创建
Create [unique|fulltext] index index_name on table_name (column1,column2)
```

#### 删除

```mysql
# 删除索引
drop index_name from table_name
```

#### 查看

```mysql
#查看索引
show index from table_name
```

### 分析SQL

#### SQL频率

```
# 通过一下命令查询SQL语句的数量
show global status like 'Com_____'
```

参考：<https://blog.csdn.net/shan_zhi_jun/article/details/79322395>

#### 慢查询分析

```mysql
# 查看是否开启慢查询分析
show variable like 'slow_query_log';

# 配置慢查询，在mysql的my.cnf中配置以下数据 ,查询时间超过2s就算慢。
# 在linux下可以找到 localhost_slow.log,其中记录了慢查询。
slow_query = 1
long_time = 2
```

#### 分析耗时

```mysql
# 数据库有profiles指令，可以帮助分析SQL耗时在什么地方。


# 需要选择到数据库,查看是否支持profiles，如果为yes则为支持
select @@having__profiling;

# 查看是否开启profile
select @@profiling;

# 开启profiles
set session profilng = 1;

# 查看当前会话的历史SQL的耗时情况,会得到一个表格数据，其中包含query_id duration query
show profiles

# 分析具体某个SQL
show profile for query query_id

# 查看具体某个SQL的CPU占用信息
show profile cpu for query_id
```

#### 执行计划

查看SQL的执行计划，看SQL的索引使用情况，表连接情况等详细信息。

```mysql
# expain/desc 加一个SQL语句
explain/desc SQL

# 会返回以下信息
| id | select_type | table | partitions | type | possible_keys | key  | key_len | ref  | rows | filtered | Extra |

|  1 | SIMPLE      | user  | NULL       | ALL  | NULL          | NULL | NULL    | NULL |    5 |   100.00 | NULL  |
```

##### id

表示一个SQL中子语句的执行顺序，且多个值的时候，id值相同的执行顺序是上面的先执行，id值不同的就是值越大越先执行。

##### select_type

select的类型，有如下几种情况

###### *simple*

表示不需要union操作或者不包含子查询的简单查询。

###### *primary*

表示最外层查询。

###### *union*

union操作中第二个及之后的查询。

###### *dependent union*

union操作中第二个及之后的查询，并且该查询依赖于外部查询。

###### *subquery*

子查询中的第一个查询。

###### *dependent subquery*

子查询中的第一个查询，并且该查询依赖于外部查询。

###### derived

派生表查询，既from字句中的子查询。

###### materialized

物化查询。

# 

###### uncacheable union

union操作中第二个及之后的查询，并且该查询属于uncacheable subquery。

##### type

表示连接类型，

###### null

​ 无需访问表或者索引，比如获取一个索引列的最大值或最小值。

###### *system/const*

当查询最多匹配一行时，常出现于where条件是＝的情况。system是const的一种特殊情况，既表本身只有一行数据的情况。

###### eq_ref

多表关联查询时，根据唯一非空索引进行查询的情况。

###### *ref*

多表查询时，根据非唯一非空索引进行查询的情况。

###### *range*

在一个索引上进行范围查找。

###### *index*

遍历索引树查询，通常发生在查询结果只包含索引字段时。

###### all

全表扫描，没有任何索引可以使用时。这是最差的情况，应该避免。

##### possible_key

可能用到的索引。

##### key

实际用到的索引。

##### key_len

 使用的索引的长度。该值越小越好。

##### rows

 估计此次查询所需读取的行数。该值越小越好。

##### ref

 连接查询的连接条件 。

##### filtered

表示返回结果占查询数的百分比，该值越小越好。

##### extra

using index condition: 查询中使用到了索引，但是需要回表再查。

using index using in:使用到了索引，且直接能拿到数据。

参考：<https://blog.csdn.net/poxiaonie/article/details/77757471>

### 使用原则

#### 最左原则匹配

在使用联合索引的时候，例如stu上建立了name,age,gender的联合索引。

最左匹配即是

①最左边(即是上面的name)的必须存在。

②左边的存在，但是跳过了中间字段，则只会走左边存在的，

​ 例如select使用了name，gender，那么用到的索引只包含name。

③如果建立索引(age,gender,name)的都存在,但是顺序不与建立的一致，

  Mysql有RBO(基于规则的优化器)，会用到该联合索引的全部。

④如果存在范围查询，则范围查询右侧的索引将失效，只会用到name和age的索引。

 但是可以使用 >= ,就会走全部的索引。

  例如  where name = xxx  and age<250 and gender='女'

#### 不要运算

不要索引列上进行运算或者使用函数，如果使用了索引失效。

#### 不做类型转换

不要索引列上进行类型转换，如果使用了索引失效。

#### 头部模糊查询

使用头部模糊查询索引会失效，反之使用尾部模糊索引不会失效

(简单理解就是让Mysql能找到范围)。

#### Or

使用or的时候，如果条件之一的列值上没有建立索引，那么索引失效。

只有or的条件的列上均建立了索引，才不会索引失效。

#### 数据分布

如果查询到的数据是数据表的全部或者大部分数据，走索引反而会使时间消耗增多，那么放弃走索引，而直接全表扫描。

### 限制索引

如果在一个列上存在多个索引，但是Mysql选择使用的索引，你觉得不太行，

那么就可以自己对使用的索引进行限制。

例如stu表建立了联合索引A((name,age,gender ),以及name上单独建立了索引。

```mysql
# 建议Mysql使用某一索引A,Mysql评估一下选择使用。
select xxx from table use index(A) where ... 
# 让Mysql忽略某一索引A
select xxx from table ignore index(A) where ... 
#强制让Mysql使用索引。
select xxx from table force index(A) where ...
```

### 索引覆盖和回表

![1645120095657](C:\Users\will\AppData\Roaming\Typora\typora-user-images\1645120095657.png)

看上图中，id是主键索引，name上有个普通索引，

当根据id查询的时候，因为走的是主键索引，直接能拿到所有数据，且效率高，因为叶子结点有所有数据。

根据name查询，且只返回id和name，或者两者之一，因为叶子结点上有数据，所以直接能拿到，不需要在去主键索引去查(覆盖索引)。

但是如果根据查询 除了id和name以外的任何数据，因为name的索引树的叶子结点没有，所以需要去主键索引通过从name索引树上取到的id进行查询，从而拿到需要的数据(回表)。

### 索引设计原则

创建索引的数据尽量分散，重复的值少，且不常修改。

```mysql
# 可以通过一下SQL查看数据的分散程度(<=1),越靠近1越分散。
select distinct(column1)/ count(*) from table_name
```

#### 前缀索引

想要在某个字段(长度较长)上建立索引，但是因为其数据长度较长，而导致索引的长度较长，这时候就可以去该字段值的前几个字符创建索引。

```mysql
# 前缀索引,取column1的前n个字符创建索引。
create index index_name on table(column1(n))

# 可以使用下面的数据来选择决定n的取值,比较多个n值的时候，分散程度的大小。
select distinct(substring(cloumn1,1,n))/ count(*) from table_name
```

#### 设计原则

1.针对于数据量较大, 且查询比较频繁的表建立索引。

2.针对于 常作为查询条件(where) 、排序(orderby) 、分组(group by)操作的字段建立索引。

3.尽量选择区分度高的列作为索引， 尽量建立唯一索引， 区分度越高，使用索引的效率越高。

4.如果是字符串类型的字段, 字段的长度较长，可以针对于字段的特点，建立前缀索引。

5.尽量使用联合索引， 减少单列索引，查询时，联合索引很多时候可以覆盖索引，节省存储空间，避免回表,提高查询效率。

6.要控制索引的数量,索引并不是多多益善，索引越多，维护索引结构的代价也就越大,会影响增删改的效率。

7.如果索引列不能存储NULL值，请在创建表时使用NOT NULL约束它。当优化器知道每列是否包含NULL值时，它可以更好地确定哪个索引最有效地用于查询。

## SQL优化

这儿的优化重要指其他方面，而不是关于索引的。

### insert

#### 批量插入

不是一条一条插入，而是批量插入(<1000),如果数量真的太多，那么就分多次插入。

#### 手动提交事务

将上面所说的多次插入，放到一个事务中。

#### 按住键顺序插入

因为插入数据后需要对索引树等进行重建，按照主键顺序插入的话，就可以减少索引树建立的开销(直接插在最右侧，以及调整非叶子结点，而不调节其他的叶子结点)

#### 使用load

大批量的插入数据。

```mysql
1客户端连接服务端时，加上参数local infile
mysql --local-infile -u root -p
#设置全局参数localL intile为1,开启从本地加载文件导入数据的开关
sel global local_infile = 1:
#执行load指令将准备好的数据，加载到表结构中
1,hjt,男

#指定文件位置
load data lncal infile 'filepath' 
#指定插入的表名
into table 'table_name' 
# 各个字段数据以什么符号分割，这儿是逗号
fields terminated by ','
# 每行数据以什么分割
lines terminated by \n' ;
```

### 主键优化

降低主键的长度，插入数据是尽量使用自增且顺序插入。

页分裂,页合并:<https://www.bilibili.com/video/BV1Kr4y1i7ru?p=90>

### order by

explain 含有order by数据时候，extra可能会出现

Using filesort :通过表的索引或全表扫描,读取满足条件的数据行，然后在排序缓冲区sort buffer中完成排序操作,所有不是通过索引直接返回排序结果的排序都叫FileSort排序

using index:通过有序索引顺序扫描直接返回有序数据,这种情况即为using index,不需要额外排序，操作效率高。

①order by 中尽量使用覆盖索引，例如在name上建立了索引，order by id,name，不会回表。

②多字段排序的时候也需要遵循索引的最左匹配原则。

③多个字段排序的要求不一样，例如一个需要升序，一个降序，在创建索引的时候需要指定。

④如果不可避免出现Using filesort，可以加大换冲排序区(sort_buffer_size)。

### group by

explain 含有group by数据时候，extra可能会出现

temporary :通过表的索引或全表扫描,读取满足条件的数据行，然后在排序缓冲区sort buffer中完成排序操作,所有不是通过索引直接返回排序结果的排序都叫FileSort排序

using index:用到了索引。

①遵循最左前缀法则。

②合适的建立联合索引，以配合第一条。

### limit

使用limit start,size 在start很大的时候是非常耗时间的。

使用覆盖索引+子查询的方式。

```mysql
# 子查询中使用到了覆盖索引
select * from tale_name t1,(select id from table_name limit 99999,10) t2 
where t1.id=t2.id
```

### count

MyISAM引擎把一个表的总行数存在了磁盘上，因此执行count(*)的时候会直接返回这个数，效率很高;

InnoDB引擎就麻烦了，它执行count(*)的时候，需要把数据一行一-行地从引擎里面读出来，然后累积计数。

count用法：

#### count(主键)

​  InnoDB引擎会遍历整张表，把每一行的主键id值都取出来,返回给服务层。服务层拿到主键后，直接按行进行累加(主键不可能为null)。

#### count(字段)

​  没有not null约束: InnoDB引擎会遍历整张表把每一行的字段值都取出来，返回给服务层,服务层判断是否为null,不为null, 计数累加。

​ 有not null约束: InnoDB 引擎会遍历整张表把每一-行的字段值都取出来, 返回给服务层，直接按行进行累加。

#### count(1)

   InnoDB引擎遍历整张表，但不取值。服务层对于返回的每-行，放一个数字“1” 进去,直接按行进行累加。

#### count(*)

InnoDB引擎并不会把全部字段取出来，而是专门做了优化，不取值，服务层直接按行进行累加。

#### 性能

count(字段) < count(主键id) < count(1)≈count(*)，建议使用最后一个。

### update

避免行锁升级为表锁，导致其他事务提交不了。

举个例子，事务A中开启了事务，更新 name(无索引)为张三的学生，但是没有提交事务，因为没有创建索引所以并不知道要更新具体哪一条数据，其他事务在修改数据的时候就会卡住，等到事务A提交之后才能修改。

反之创建索引呢？这个索引是怎么样的索引才能使用行锁而不使用表锁，分为下面几种情况：

使用到了主键索或者唯一索引一定不会升级为表锁，因为它能找到唯一你要操作的数据。

普通索引如果数据够分散(即是重复数据少)也不会升级为表锁，但是数据集中的时候就会升级为表锁。

其实简单理解就是，尽量让Mysql知道你想操作的哪一条具体的数据，它能直接通过索引找到的话，就不会升级为表锁，反之升级为表锁。

## 视图

视图(View) 是一种虚拟存在的表。视图中的数据并不在数据库中实际存在，行和列数据来自定义视图的查询中使用的表，并且是在使用视图的动态生成的。
通俗的讲，视图只保存了查询的SQL逻辑，不保存查询结果。所以在创建视图的时候，主要的工作就落在创建这条SQL查询语句上。

### 创建

```mysql
# 创建视图，后面得 with... 是否检查选项
create VIEW view_name as select语句 [ WITH[ CASCADED | LOCAL ]CHECK OPTION]
```

检查选项可以认为是操作这个视图操作数据的限制，如果有with...则会检查数据是否符合限制，反之不。

#### CASCADED

```mysql
# WITH  CASCADED OPTION 是指在插入或者更新的操作的时候是否要符合视图中的SQL限制。
# 如下面的视图创建语句，带有with CASCADED CHECK OPTIO 遵循age=18的限制
# 如果插入或者更新的数据不符合，就无法插入到表中。
create view B from select * from stu where age=18 with CASCADED CHECK OPTION
# 并且如果视图A依赖于视图B创建，视图B也加了with CASCADED CHECK OPTION，
# 通过视图B插入数据的时候就需要遵守A,B的限制。
# 如下面的例子，从视图A插入数据就需要gender=女 age=18
create view A from select * from B where gender='女' with CASCADED CHECK OPTION

# 简而言之，视图在操作数据的时候要遵循依赖所有视图的规范。
```

#### LOCAL

在mysql5.7.6之前，local表示只需要满足本视图的约束就能对数据进行操作，在后面得版本作用用CASCADED。

### 查询

```mysql
# 查看视图创建语句
show create view 视图名字;
# 查看视图数据,可以对视图进行类似的CRUD,并且会作用到对应的表。
select * from 视图名字;
```

### 修改

```mysql
# 修改视图
CREATE [OR REPLACE] VIEW视图名称[(列名列表)] AS SELECT语句 [ WITH[ CASCADED | LOCAL ] CHECK OPTION]
# 修改视图
ALTER VIEW 视图名称[(列名列表)] AS SELECT语句 [ WITH[ CASCADED| LOCAL] CHECK OPTION ]
```

### 删除

```mysql
# 删除视图
DROP VIEW [IF EXISTS] 视图名
```

### 对数据操作

对于视图的操作会更新的具体的表。

当视图想要对表数据进行更新的时候，视图的行数据必须与表数据一对一。

在视图中是使用了例如sum/grouy by等，视图数据都不能与表中数据一对一，所以不能进行通过视图更新表数据。

### 视图作用

##### 简化操作

可以将常用的查询操作写入视图，操作的时候调用很方便。

##### 安全

Mysql可以限制操作者对于表的权限，而不能限制表中数据权限，可以通过视图完成对操作者能操作表数据的限制。

##### 数据独立

有的时候需要更新表的字段名，当更新了表的字段名的时候，不使用视图的时候还需要更新相关代码。

但是使用了视图，更新了字段名，只需要修改一下视图，给新字段名取上别名，代码就不需要更改，依然能运行。

## 存储过程

存储过程就是将一些SQL放在一起，其中涉及逻辑判断，会被Mysql编译好，

且能减少数据在Mysql和应用来回传输。

且存储过程在执行一次后，二进制代码会驻留在缓冲区，下一次执行，只需要执行二进制代码就行，提高了效率

 存储过程思想上很简单，就是数据库 SQL 语言层面的代码封装与重用。

### 创建

```mysql
create procedure 名称([参数列表...])
begin
 执行逻辑和SQL
end;
```

PS:

​    在Mysql的cmd中创建存储过程的时候，存储过程中的SQL语句带有 **;** ,会被系统认为SQL结束了，此时可以通过

   delimiter 字符A，来指定SQL的结束字符，end后面加上指定的字符A就可。

### 查看

```mysql
# 查看某一数据库下的存储过程
seLect * from information_schema.ROUTINES where ROUTINE_SCHEMA = "数据库名";
# 查看某一存储过程具体信息
show create procedure 名称;
```

### 删除

```mysql
drop procedure 名称;
```

### 调用

```mysql
call 名称(参数...)
```

### 语法

#### 变量

##### 系统变量

```mysql
# mysql有很多全局变量和会话变量
# 查看，如果不指定global|session，默认是session。
select global|session 变量名
# 设置
set global|session 变量名
```

##### 自定义变量

```mysql
# 设置值
# 方式一
set @变量名:= xxx;
# 方式二
set @变量名= xxx;
# 方式三
select @变量名=xxx;
# 查询赋值
select name into @name from stu where id=1

# 使用值
select @变量名
# 如果为申明就使用，那么查看的结果会是null
```

##### 局部变量

即为存储过程中的变量

```mysql
# 声明
declare 变量名 类型 default 0;
# 赋值
set 变量名= xxx;
select 变量名:=xxx;
# 查询赋值
select name into @name from stu where id=1

# 使用值
select @变量名

# 实例
create procedure p()
begin
  DECLARE num int default 0;
  SELECT COUNT(*) INTO num from stu;
  select num;
end;
```

#### if

```mysql
if 条件 then 
...
elseif 条件2 then
...
else
...
end if;

# 示例，判断成绩等级
create procedure p()
begin
  DECLARE num int default 80;
  DECLARE lever int ;
  if num>85 then 
     set lever=1;
  elseif num>60 then
     set lever=2;
  else
    set lever=3;
 end if;
 SELECT lever;
end;
```

#### case

```mysql
# 方式1
case 变量
 when value1 then  ...
 when value2 thne  ...
 else    .... 
end case;

# 方式二
case  
 when 条件1 then ...
 when 条件2 then ...
 else ...
end case;

# 示例
create procedure p_sex()
begin
 declare sex int default 0;
    case sex
       when 0 then  SELECT '男';
       when 1 then  select '女';
       else select '未知';
    end case;
end;
# 通过年龄给人打标签
create procedure p_age()
begin
   declare age int default 0;
   declare tag varchar(20);
   set age = 20
   case 
       when age<18 then set tag = '未成年';
       when age<40 then set tag = '壮年';
       else set tag = '老年';
    end case;
    select tag;
end;
```

#### 参数

```mysql
# 使用方式
create procedure p(参数类型(in,out,inout)) 参数名 type...)

# in 入参,默认
# out 出参
# inout 既出又如

# 示例
create procedure p_age(in age int, out tag varchar(20))
begin
   case 
       when age<18 then set tag = '未成年';
       when age<40 then set tag = '壮年';
       else set tag = '老年';
    end case;
    select tag;
end;

# 使用一个变量来接收结果信息.
call p_age(18,@tag);
# 查看tag。
secect @tag;
```

#### 循环

##### while

```mysql
# 满足条件 执行循环
while 条件 do 执行内容;
end while;

#举个例子
create procedure cal(in n int)
begin
  declare total int DEFAULT 0;
     while n do
     SET total = total+n;
    SET n = n -1;
  end while; 
  SELECT total;
end;
```

##### repeat

```mysql
# 先执行一次，然后再判断条件。
# 满足条件的时候，退出循环,util中写出退出条件。
repeat
   执行内容...
until 条件 end repeat;

#示例
create procedure cal2(in n int)
begin
  declare total int DEFAULT 0;
  REPEAT
     SET total = total+n;
     set n = n-1;
     UNTIL n=0 END REPEAT;
  SELECT total;
end;
```

##### loop

```mysql
lable: loop
 ...
 # loop可以被认为是死循环，中间自写条件退出循环，leave lable
 leave label;
 # 自写条件直接进入下一次循环，即continue
 iterate;
 
end loop lable;



# 举个例子
create procedure cal3(in n int)
begin
  declare total int DEFAULT 0;
  sum:loop
     if n then 
     set total = total +n;
     set n = n-1;
   else
      LEAVE sum;
   end if;
  END loop sum;
  SELECT total;
end;
```

### 游标

游标可以认为是一个数据集合，当我想要遍历这个数据集合的是否，就是操作这个游标。、

举个例子，例如我想把stu表中的gender为女的id和name'，拿出来放到一个新的表，我就需要遍历游标，

每次取到数据之后做一次插入。

```mysql
# 游标的使用，包括游标的声明(需要位置变量之后)，游标开启，游标获取数据，游标关闭
# 声明
declare 名称 cursor for SELECT...
# 打开
open 名称;
# 获取数据
fetch 游标名 into 变量1,变量2...
# 关闭游标
close 名称;
 
# 举个例子,将stu的女生的id name信息插入到girls(字段仅有为id，name)表中
# 就是声明游标，然后遍历游标，但是到了最后游标获取不到数据，就会是02000状态码
# 此时就声明一个handler来处理这个错误，执行关闭游标的操作，类似于异常处理。
create procedure cur()
begin
  declare id int DEFAULT 0;
  declare name VARCHAR(20);
  declare c CURSOR for SELECT id,name FROM stu where gender='女';
  DECLARE exit HANDLER for SQLSTATE '02000' CLOSE c;
 
     OPEN c;
  WHILE true DO
   FETCH c into id,name;
   insert into girls VALUES(id,name);
  END WHILE;
end;
```

### handler

即是MySQL中的异常处理。

```mysql
# 声明一个handler,类型包括 continue(继续执行),exit(退出)
declare 类型 handler for 出错情况 对应操作...

# 出错情况中可以下以下几种:
SQLSTATE '出错码'
# SQLWARNING 表示所有01开头的出错码
SQLWARNING  
# NOT FOUND表示所有02开头的出错码,数据未找到。
NOT FOUND
# 没有被SQLWARNING,NOT FOUND捕获到的。
SQLEXCEPTION

# 例子，见游标中的例子。
```

### 存储函数

自定义函数，参数仅为in类型，且有返回值。

```mysql
# 基本格式，必须要有返回值
# characteristic是指对这个函数的说明，有以下三种，mysql8之后必写有 
# DETERMINISTIC:相同的输入参数总是产生相同的结果
# NOSQL :不包含SQL语句。
# READS SQL DATA:包含读取数据的语句，但不包含写入数据的语句。
CREATE  FUNCTION 函数名( 变量名 类型...)  #指定函数名,以及参数名和类型
RETURNS returnVarType  [characteristic ...]  # 指定返回值类型
begin
   函数体
end;  

# 举个例子
create FUNCTION cal(n int)
RETURNS int DETERMINISTIC
begin
  declare total int DEFAULT 0;
  while n do
     SET total = total+n;
    SET n = n -1;
  end while;
 return total; 
end;
```

## 触发器

触发器是与表有关的数据库对象，指在insert/update/delete之前或之后，触发并执行触发器中定义的SQL语句集合。触发器的这种特性可以协助应用在数据库端确保数据的完整性,日志记录,数据校验等操作。使用别名OLD和NEW来引用触发器中发生变化的记录内容,这与其他的数据库是相似的。现在触发器还只支持行级触发,不支持语句级触发。

#### 创建

```mysql
# 触发器创建语法，
# after/before表示在更改数据操作之前之后触发
# insert/update/delete针对什么类型的进行触发
# 
create trigger 名称
after/before  insert/update/delete
on table_name for rows
begin
 执行的操作
end;

# 在插入之后将部分信息写入log(这儿只是演示)
# 通过new.xxx获取新数据的属性
# 在update用old.xxx获取删除修改之前的原数据 new拿到更新后的数据。
# delete用 old拿删除的数据信息。
create TRIGGER log
after INSERT
on stu for EACH ROW
begin
 INSERT INTO log VALUES (new.id,new.name) ;
end;
```

#### 查看

```mysql
show triggers
```

#### 删除

```mysql
delete trigger 数据库名.触发器名
```

## 事件

事件可以调用一次，或者周期性的调用，它是由特定线程管理。

```mysql
# 查看事件调度器是否开启
SHOW VARIABLES LIKE 'event_scheduler';
# 开启
SET GLOBAL event_scheduler = ON;
# 也可在mysql的配置文件中写好
event_scheduler = on
```

### 创建

```mysql
# 创建事件

CREATE EVENT [IF NOT EXISTS] event_name
# 定义事件的执行事件，具体语法见下。
ON SCHEDULE schedule                
# 定义事件是否一次执行删除,ON COMPLETION NOT PRESERVE
# 循环执行 ON COMPLETION PRESERVE
[ON COMPLETION [NOT] PRESERVE]  
# 设置事件创建之后是否就启用,DISABLE是在从数据库关闭的。
[ENABLE | DISABLE | DISABLE ON SLAVE]
# 对事件的注释,可选
[COMMENT 'comment']
# 事件需要执行的内容,执行单个句子可以直接加在do后面，执行多个则加begin/end;
DO 
begin 
 event_body;
end;


schedule:
    # 指定事件的发生时间，at timestamp即是发生于指定事件,与下面的every...二选一。
    AT timestamp [+ INTERVAL interval] ... 
    # 每多少事件间隔发生
    | EVERY interval      
    # starts/ends 是指定事件周期范围，不在这个范围就不会执行事件。
    [STARTS timestamp [+ INTERVAL interval] ...]
    [ENDS timestamp [+ INTERVAL interval] ...]
 
interval:
    quantity {YEAR | QUARTER | MONTH | DAY | HOUR | MINUTE |
              WEEK | SECOND | YEAR_MONTH | DAY_HOUR | DAY_MINUTE |
              DAY_SECOND | HOUR_MINUTE | HOUR_SECOND | MINUTE_SECOND}

# schedule的一些例子
on schedule every 1 second         -- 每秒执行1次
on schedule every 2 minute         -- 每两分钟执行1次
on schedule every 3 day            -- 每3天执行1次
ON schedule every 1 day starts date_add(date_add_curdate(), interval 1 day), interval 1 hour)  -- 每天凌晨1点执行
ON schedule every 1 month starts date_add(date_add(date_sub(curdatte(),interval day(curdate())-1 day),interval 1 month),interval 1 hour) -- 每个月的第一天凌晨1点执行

on schedule at current_timestamp()+interval 5 day     -- 5天后执行
on schedule at current_timestamp()+interval 10 minute -- 10分钟后执行
on schedule at '2022-10-01 21:50:00'                  -- 在2022年10月1日，晚上9点50执行
ON SCHEDULE EVERY 3 MONTH STARTS CURRENT_TIMESTAMP + 1 WEEK -- 每 3 个月，从现在起一周后开始
ON SCHEDULE EVERY 12 HOUR STARTS CURRENT_TIMESTAMP + INTERVAL 30 MINUTE ENDS CURRENT_TIMESTAMP + INTERVAL 4 WEEK -- 每十二个小时，从现在起三十分钟后开始，并于现在起四个星期后结束

on schedule every 1 day starts current_timestamp()+interval 5 day ends current_timestamp()+interval 1 month -- 5天后开始每天都执行执行到下个月底
on schedule every 1 day ends current_timestamp()+interval 5 day -- 从现在起每天执行，执行5天
```

### 删除

```mysql
DROP EVENT [IF EXISTS] event_name
```

### 查看

```mysql
SELECT event_name,event_definition,interval_value,interval_field,status FROM information_schema.EVENTS;
```

### 修改

```mysql
# 与创建语法类似
ALTER
    EVENT [IF NOT EXISTS] event_name
    ON SCHEDULE schedule
    [ON COMPLETION [NOT] PRESERVE]
    [ENABLE | DISABLE | DISABLE ON SLAVE]
    [COMMENT 'comment']
    DO event_body;
```

### 开启/关闭

```mysql
# 开启
alter event 事件名 on completion preserve enable; 
# 关闭
alter event 事件名 on completion preserve disable; 
```

## 锁
