# 第15章 查询优化的百科全书-Explain详解

&emsp;&emsp;一条查询语句在经过`MySQL`查询优化器的各种基于成本和规则的优化会后生成一个所谓的`执行计划`，这个执行计划展示了接下来具体执行查询的方式，比如多表连接的顺序是什么，对于每个表采用什么访问方法来具体执行查询等等。设计`MySQL`的大佬贴心的为我们提供了`EXPLAIN`语句来帮助我们查看某个查询语句的具体执行计划，本章的内容就是为了帮助大家看懂`EXPLAIN`语句的各个输出项都是干嘛使的，从而可以有针对性的提升我们查询语句的性能。

&emsp;&emsp;如果我们想看看某个查询的执行计划的话，可以在具体的查询语句前面加一个`EXPLAIN`，就像这样：

```
mysql> EXPLAIN SELECT 1;
+----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+----------------+
| id | select_type | table | partitions | type | possible_keys | key  | key_len | ref  | rows | filtered | Extra          |
+----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+----------------+
|  1 | SIMPLE      | NULL  | NULL       | NULL | NULL          | NULL | NULL    | NULL | NULL |     NULL | No tables used |
+----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+----------------+
1 row in set, 1 warning (0.01 sec)
```

&emsp;&emsp;然后这输出的一大坨东西就是所谓的`执行计划`，我的任务就是带领大家看懂这一大坨东西里边的每个列都是干什么用的，以及在这个`执行计划`的辅助下，我们应该怎样改进自己的查询语句以使查询执行起来更高效。其实除了以`SELECT`开头的查询语句，其余的`DELETE`、`INSERT`、`REPLACE`以及`UPDATE`语句前面都可以加上`EXPLAIN`这个词儿，用来查看这些语句的执行计划，不过我们这里对`SELECT`语句更感兴趣，所以后边只会以`SELECT`语句为例来描述`EXPLAIN`语句的用法。为了让大家先有一个感性的认识，我们把`EXPLAIN`语句输出的各个列的作用先大致罗列一下：

|列名|描述|
|:--:|:--|
|`id`|在一个大的查询语句中每个`SELECT`关键字都对应一个唯一的`id`|
|`select_type`|`SELECT`关键字对应的那个查询的类型|
|`table`|表名|
|`partitions`|匹配的分区信息|
|`type`|针对单表的访问方法|
|`possible_keys`|可能用到的索引|
|`key`|实际上使用的索引|
|`key_len`|实际使用到的索引长度|
|`ref`|当使用索引列等值查询时，与索引列进行等值匹配的对象信息|
|`rows`|预估的需要读取的记录条数|
|`filtered`|某个表经过搜索条件过滤后剩余记录条数的百分比|
|`Extra`|一些额外的信息|

&emsp;&emsp;需要注意的是，<span style="color:red">大家如果看不懂上面输出列含义，那是正常的，千万不要纠结～</span>。我在这里把它们都列出来只是为了描述一个轮廓，让大家有一个大致的印象，下面会细细道来，等会儿说完了不信你不会～ 为了故事的顺利发展，我们还是要请出我们前面已经用了n遍的`single_table`表，为了防止大家忘了，再把它的结构描述一遍：

```
CREATE TABLE single_table (
    id INT NOT NULL AUTO_INCREMENT,
    key1 VARCHAR(100),
    key2 INT,
    key3 VARCHAR(100),
    key_part1 VARCHAR(100),
    key_part2 VARCHAR(100),
    key_part3 VARCHAR(100),
    common_field VARCHAR(100),
    PRIMARY KEY (id),
    KEY idx_key1 (key1),
    UNIQUE KEY idx_key2 (key2),
    KEY idx_key3 (key3),
    KEY idx_key_part(key_part1, key_part2, key_part3)
) Engine=InnoDB CHARSET=utf8;
```

&emsp;&emsp;我们仍然假设有两个和`single_table`表构造一模一样的`s1`、`s2`表，而且这两个表里边儿有10000条记录，除id列外其余的列都插入随机值。为了让大家有比较好的阅读体验，我们下面并不准备严格按照`EXPLAIN`输出列的顺序来介绍这些列分别是干嘛的，大家注意一下就好了。

## 执行计划输出中各列详解

### table

&emsp;&emsp;不论我们的查询语句有多复杂，里边儿包含了多少个表，到最后也是需要对每个表进行单表访问的，所以设计`MySQL`的大佬规定<span style="color:red">EXPLAIN语句输出的每条记录都对应着某个单表的访问方法，该条记录的table列代表着该表的表名</span>。所以我们看一条比较简单的查询语句：

```
mysql> EXPLAIN SELECT * FROM s1;
+----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+-------+
| id | select_type | table | partitions | type | possible_keys | key  | key_len | ref  | rows | filtered | Extra |
+----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+-------+
|  1 | SIMPLE      | s1    | NULL       | ALL  | NULL          | NULL | NULL    | NULL | 9688 |   100.00 | NULL  |
+----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+-------+
1 row in set, 1 warning (0.00 sec)
```

&emsp;&emsp;这个查询语句只涉及对`s1`表的单表查询，所以`EXPLAIN`输出中只有一条记录，其中的`table`列的值是`s1`，表明这条记录是用来说明对`s1`表的单表访问方法的。

&emsp;&emsp;下面我们看一下一个连接查询的执行计划：

```
mysql> EXPLAIN SELECT * FROM s1 INNER JOIN s2;
+----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+---------------------------------------+
| id | select_type | table | partitions | type | possible_keys | key  | key_len | ref  | rows | filtered | Extra                                 |
+----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+---------------------------------------+
|  1 | SIMPLE      | s1    | NULL       | ALL  | NULL          | NULL | NULL    | NULL | 9688 |   100.00 | NULL                                  |
|  1 | SIMPLE      | s2    | NULL       | ALL  | NULL          | NULL | NULL    | NULL | 9954 |   100.00 | Using join buffer (Block Nested Loop) |
+----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+---------------------------------------+
2 rows in set, 1 warning (0.01 sec)
```

&emsp;&emsp;可以看到这个连接查询的执行计划中有两条记录，这两条记录的`table`列分别是`s1`和`s2`，这两条记录用来分别说明对`s1`表和`s2`表的访问方法是什么。

### id

&emsp;&emsp;我们知道我们写的查询语句一般都以`SELECT`关键字开头，比较简单的查询语句里只有一个`SELECT`关键字，比如下面这个查询语句：

```
SELECT * FROM s1 WHERE key1 = 'a';
```

&emsp;&emsp;稍微复杂一点的连接查询中也只有一个`SELECT`关键字，比如：

```
SELECT * FROM s1 INNER JOIN s2
    ON s1.key1 = s2.key1
    WHERE s1.common_field = 'a';
```

&emsp;&emsp;但是下面两种情况下在一条查询语句中会出现多个`SELECT`关键字：

- 查询中包含子查询的情况

    &emsp;&emsp;比如下面这个查询语句中就包含2个`SELECT`关键字：

    ```
    SELECT * FROM s1 
        WHERE key1 IN (SELECT * FROM s2);
    ```

- 查询中包含`UNION`语句的情况

    &emsp;&emsp;比如下面这个查询语句中也包含2个`SELECT`关键字：

    ```
    SELECT * FROM s1  UNION SELECT * FROM s2;
    ```

&emsp;&emsp;查询语句中每出现一个`SELECT`关键字，设计`MySQL`的大佬就会为它分配一个唯一的`id`值。这个`id`值就是`EXPLAIN`语句的第一个列，比如下面这个查询中只有一个`SELECT`关键字，所以`EXPLAIN`的结果中也就只有一条`id`列为`1`的记录：

```
mysql> EXPLAIN SELECT * FROM s1 WHERE key1 = 'a';
+----+-------------+-------+------------+------+---------------+----------+---------+-------+------+----------+-------+
| id | select_type | table | partitions | type | possible_keys | key      | key_len | ref   | rows | filtered | Extra |
+----+-------------+-------+------------+------+---------------+----------+---------+-------+------+----------+-------+
|  1 | SIMPLE      | s1    | NULL       | ref  | idx_key1      | idx_key1 | 303     | const |    8 |   100.00 | NULL  |
+----+-------------+-------+------------+------+---------------+----------+---------+-------+------+----------+-------+
1 row in set, 1 warning (0.03 sec)
```

&emsp;&emsp;对于连接查询来说，一个`SELECT`关键字后边的`FROM`子句中可以跟随多个表，所以在连接查询的执行计划中，<span style="color:red">每个表都会对应一条记录，但是这些记录的id值都是相同的</span>，比如：

```
mysql> EXPLAIN SELECT * FROM s1 INNER JOIN s2;
+----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+---------------------------------------+
| id | select_type | table | partitions | type | possible_keys | key  | key_len | ref  | rows | filtered | Extra                                 |
+----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+---------------------------------------+
|  1 | SIMPLE      | s1    | NULL       | ALL  | NULL          | NULL | NULL    | NULL | 9688 |   100.00 | NULL                                  |
|  1 | SIMPLE      | s2    | NULL       | ALL  | NULL          | NULL | NULL    | NULL | 9954 |   100.00 | Using join buffer (Block Nested Loop) |
+----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+---------------------------------------+
2 rows in set, 1 warning (0.01 sec)
```

&emsp;&emsp;可以看到，上述连接查询中参与连接的`s1`和`s2`表分别对应一条记录，但是这两条记录对应的`id`值都是`1`。这里需要大家记住的是，<span style="color:red">在连接查询的执行计划中，每个表都会对应一条记录，这些记录的id列的值是相同的，出现在前面的表表示驱动表，出现在后边的表表示被驱动表</span>。所以从上面的`EXPLAIN`输出中我们可以看出，查询优化器准备让`s1`表作为驱动表，让`s2`表作为被驱动表来执行查询。

&emsp;&emsp;对于包含子查询的查询语句来说，就可能涉及多个`SELECT`关键字，所以在包含子查询的查询语句的执行计划中，每个`SELECT`关键字都会对应一个唯一的`id`值，比如这样：

```
mysql> EXPLAIN SELECT * FROM s1 WHERE key1 IN (SELECT key1 FROM s2) OR key3 = 'a';
+----+-------------+-------+------------+-------+---------------+----------+---------+------+------+----------+-------------+
| id | select_type | table | partitions | type  | possible_keys | key      | key_len | ref  | rows | filtered | Extra       |
+----+-------------+-------+------------+-------+---------------+----------+---------+------+------+----------+-------------+
|  1 | PRIMARY     | s1    | NULL       | ALL   | idx_key3      | NULL     | NULL    | NULL | 9688 |   100.00 | Using where |
|  2 | SUBQUERY    | s2    | NULL       | index | idx_key1      | idx_key1 | 303     | NULL | 9954 |   100.00 | Using index |
+----+-------------+-------+------------+-------+---------------+----------+---------+------+------+----------+-------------+
2 rows in set, 1 warning (0.02 sec)
```

&emsp;&emsp;从输出结果中我们可以看到，`s1`表在外层查询中，外层查询有一个独立的`SELECT`关键字，所以第一条记录的`id`值就是`1`，`s2`表在子查询中，子查询有一个独立的`SELECT`关键字，所以第二条记录的`id`值就是`2`。

&emsp;&emsp;但是这里大家需要特别注意，<span style="color:red">查询优化器可能对涉及子查询的查询语句进行重写，从而转换为连接查询</span>。所以如果我们想知道查询优化器对某个包含子查询的语句是否进行了重写，直接查看执行计划就好了，比如说：

```
mysql> EXPLAIN SELECT * FROM s1 WHERE key1 IN (SELECT key3 FROM s2 WHERE common_field = 'a');
+----+-------------+-------+------------+------+---------------+----------+---------+-------------------+------+----------+------------------------------+
| id | select_type | table | partitions | type | possible_keys | key      | key_len | ref               | rows | filtered | Extra                        |
+----+-------------+-------+------------+------+---------------+----------+---------+-------------------+------+----------+------------------------------+
|  1 | SIMPLE      | s2    | NULL       | ALL  | idx_key3      | NULL     | NULL    | NULL              | 9954 |    10.00 | Using where; Start temporary |
|  1 | SIMPLE      | s1    | NULL       | ref  | idx_key1      | idx_key1 | 303     | xiaohaizi.s2.key3 |    1 |   100.00 | End temporary                |
+----+-------------+-------+------------+------+---------------+----------+---------+-------------------+------+----------+------------------------------+
2 rows in set, 1 warning (0.00 sec)
```

&emsp;&emsp;可以看到，虽然我们的查询语句是一个子查询，但是执行计划中`s1`和`s2`表对应的记录的`id`值全部是`1`，这就表明了<span style="color:red">查询优化器将子查询转换为了连接查询</span>。

&emsp;&emsp;对于包含`UNION`子句的查询语句来说，每个`SELECT`关键字对应一个`id`值也是没错的，不过还是有点儿特别的东西，比方说下面这个查询：

```
mysql> EXPLAIN SELECT * FROM s1  UNION SELECT * FROM s2;
+----+--------------+------------+------------+------+---------------+------+---------+------+------+----------+-----------------+
| id | select_type  | table      | partitions | type | possible_keys | key  | key_len | ref  | rows | filtered | Extra           |
+----+--------------+------------+------------+------+---------------+------+---------+------+------+----------+-----------------+
|  1 | PRIMARY      | s1         | NULL       | ALL  | NULL          | NULL | NULL    | NULL | 9688 |   100.00 | NULL            |
|  2 | UNION        | s2         | NULL       | ALL  | NULL          | NULL | NULL    | NULL | 9954 |   100.00 | NULL            |
| NULL | UNION RESULT | <union1,2> | NULL       | ALL  | NULL          | NULL | NULL    | NULL | NULL |     NULL | Using temporary |
+----+--------------+------------+------------+------+---------------+------+---------+------+------+----------+-----------------+
3 rows in set, 1 warning (0.00 sec)
```

&emsp;&emsp;这个语句的执行计划的第三条记录是个什么鬼？为毛`id`值是`NULL`，而且`table`列长的也怪怪的？大家别忘了`UNION`子句是干嘛用的，它会把多个查询的结果集合并起来并对结果集中的记录进行去重，怎么去重呢？`MySQL`使用的是内部的临时表。正如上面的查询计划中所示，`UNION`子句是为了把`id`为`1`的查询和`id`为`2`的查询的结果集合并起来并去重，所以在内部创建了一个名为`<union1, 2>`的临时表（就是执行计划第三条记录的`table`列的名称），`id`为`NULL`表明这个临时表是为了合并两个查询的结果集而创建的。

&emsp;&emsp;跟`UNION`对比起来，`UNION ALL`就不需要为最终的结果集进行去重，它只是单纯的把多个查询的结果集中的记录合并成一个并返回给用户，所以也就不需要使用临时表。所以在包含`UNION ALL`子句的查询的执行计划中，就没有那个`id`为`NULL`的记录，如下所示：

```
mysql> EXPLAIN SELECT * FROM s1  UNION ALL SELECT * FROM s2;
+----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+-------+
| id | select_type | table | partitions | type | possible_keys | key  | key_len | ref  | rows | filtered | Extra |
+----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+-------+
|  1 | PRIMARY     | s1    | NULL       | ALL  | NULL          | NULL | NULL    | NULL | 9688 |   100.00 | NULL  |
|  2 | UNION       | s2    | NULL       | ALL  | NULL          | NULL | NULL    | NULL | 9954 |   100.00 | NULL  |
+----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+-------+
2 rows in set, 1 warning (0.01 sec)
```

### select_type

&emsp;&emsp;通过上面的内容我们知道，一条大的查询语句里边可以包含若干个`SELECT`关键字，每个`SELECT`关键字代表着一个小的查询语句，而每个`SELECT`关键字的`FROM`子句中都可以包含若干张表（这些表用来做连接查询），每一张表都对应着执行计划输出中的一条记录，对于在同一个`SELECT`关键字中的表来说，它们的`id`值是相同的。

&emsp;&emsp;设计`MySQL`的大佬为每一个`SELECT`关键字代表的小查询都定义了一个称之为`select_type`的属性，意思是我们只要知道了某个小查询的`select_type`属性，就知道了这个小查询在整个大查询中扮演了一个什么角色，口说无凭，我们还是先来见识见识这个`select_type`都能取哪些值（为了精确起见，我们直接使用文档中的英文做简要描述，随后会进行详细解释的）：

|名称|描述|
|:--:|:--|
|`SIMPLE`|Simple SELECT (not using UNION or subqueries)|
|`PRIMARY`|Outermost SELECT|
|`UNION`|Second or later SELECT statement in a UNION|
|`UNION RESULT`|Result of a UNION|
|`SUBQUERY`|First SELECT in subquery|
|`DEPENDENT SUBQUERY`|First SELECT in subquery, dependent on outer query|
|`DEPENDENT UNION`|Second or later SELECT statement in a UNION, dependent on outer query|
|`DERIVED`|Derived table|
|`MATERIALIZED`|Materialized subquery|
|`UNCACHEABLE SUBQUERY`|A subquery for which the result cannot be cached and must be re-evaluated for each row of the outer query|
|`UNCACHEABLE UNION`|The second or later select in a UNION that belongs to an uncacheable subquery (see UNCACHEABLE SUBQUERY)|

&emsp;&emsp;英文描述太简单，不知道说了什么？来详细看看里边儿的每个值都是干什么吃的：

- `SIMPLE`

    &emsp;&emsp;查询语句中不包含`UNION`或者子查询的查询都算作是`SIMPLE`类型，比方说下面这个单表查询的`select_type`的值就是`SIMPLE`：

    ```
    mysql> EXPLAIN SELECT * FROM s1;
    +----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+-------+
    | id | select_type | table | partitions | type | possible_keys | key  | key_len | ref  | rows | filtered | Extra |
    +----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+-------+
    |  1 | SIMPLE      | s1    | NULL       | ALL  | NULL          | NULL | NULL    | NULL | 9688 |   100.00 | NULL  |
    +----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+-------+
    1 row in set, 1 warning (0.00 sec)
    ```

    &emsp;&emsp;当然，连接查询也算是`SIMPLE`类型，比如：

    ```
    mysql> EXPLAIN SELECT * FROM s1 INNER JOIN s2;
    +----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+---------------------------------------+
    | id | select_type | table | partitions | type | possible_keys | key  | key_len | ref  | rows | filtered | Extra                                 |
    +----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+---------------------------------------+
    |  1 | SIMPLE      | s1    | NULL       | ALL  | NULL          | NULL | NULL    | NULL | 9688 |   100.00 | NULL                                  |
    |  1 | SIMPLE      | s2    | NULL       | ALL  | NULL          | NULL | NULL    | NULL | 9954 |   100.00 | Using join buffer (Block Nested Loop) |
    +----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+---------------------------------------+
    2 rows in set, 1 warning (0.01 sec)
    ```

- `PRIMARY`

    &emsp;&emsp;对于包含`UNION`、`UNION ALL`或者子查询的大查询来说，它是由几个小查询组成的，其中最左边的那个查询的`select_type`值就是`PRIMARY`，比方说：

    ```
    mysql> EXPLAIN SELECT * FROM s1 UNION SELECT * FROM s2;
    +----+--------------+------------+------------+------+---------------+------+---------+------+------+----------+-----------------+
    | id | select_type  | table      | partitions | type | possible_keys | key  | key_len | ref  | rows | filtered | Extra           |
    +----+--------------+------------+------------+------+---------------+------+---------+------+------+----------+-----------------+
    |  1 | PRIMARY      | s1         | NULL       | ALL  | NULL          | NULL | NULL    | NULL | 9688 |   100.00 | NULL            |
    |  2 | UNION        | s2         | NULL       | ALL  | NULL          | NULL | NULL    | NULL | 9954 |   100.00 | NULL            |
    | NULL | UNION RESULT | <union1,2> | NULL       | ALL  | NULL          | NULL | NULL    | NULL | NULL |     NULL | Using temporary |
    +----+--------------+------------+------------+------+---------------+------+---------+------+------+----------+-----------------+
    3 rows in set, 1 warning (0.00 sec)
    ```

    &emsp;&emsp;从结果中可以看到，最左边的小查询`SELECT * FROM s1`对应的是执行计划中的第一条记录，它的`select_type`值就是`PRIMARY`。

- `UNION`

    &emsp;&emsp;对于包含`UNION`或者`UNION ALL`的大查询来说，它是由几个小查询组成的，其中除了最左边的那个小查询以外，其余的小查询的`select_type`值就是`UNION`，可以对比上一个例子的效果，这就不多举例子了。

- `UNION RESULT`

    &emsp;&emsp;`MySQL`选择使用临时表来完成`UNION`查询的去重工作，针对该临时表的查询的`select_type`就是`UNION RESULT`，例子上面有，就不赘述了。

- `SUBQUERY`

    &emsp;&emsp;如果包含子查询的查询语句不能够转为对应的`semi-join`的形式，并且该子查询是不相关子查询，并且查询优化器决定采用将该子查询物化的方案来执行该子查询时，该子查询的第一个`SELECT`关键字代表的那个查询的`select_type`就是`SUBQUERY`，比如下面这个查询：

    ```
    mysql> EXPLAIN SELECT * FROM s1 WHERE key1 IN (SELECT key1 FROM s2) OR key3 = 'a';
    +----+-------------+-------+------------+-------+---------------+----------+---------+------+------+----------+-------------+
    | id | select_type | table | partitions | type  | possible_keys | key      | key_len | ref  | rows | filtered | Extra       |
    +----+-------------+-------+------------+-------+---------------+----------+---------+------+------+----------+-------------+
    |  1 | PRIMARY     | s1    | NULL       | ALL   | idx_key3      | NULL     | NULL    | NULL | 9688 |   100.00 | Using where |
    |  2 | SUBQUERY    | s2    | NULL       | index | idx_key1      | idx_key1 | 303     | NULL | 9954 |   100.00 | Using index |
    +----+-------------+-------+------------+-------+---------------+----------+---------+------+------+----------+-------------+
    2 rows in set, 1 warning (0.00 sec)
    ```

    &emsp;&emsp;可以看到，外层查询的`select_type`就是`PRIMARY`，子查询的`select_type`就是`SUBQUERY`。需要大家注意的是，<span style="color:red">由于select_type为SUBQUERY的子查询由于会被物化，所以只需要执行一遍</span>。

- `DEPENDENT SUBQUERY`

    &emsp;&emsp;如果包含子查询的查询语句不能够转为对应的`semi-join`的形式，并且该子查询是相关子查询，则该子查询的第一个`SELECT`关键字代表的那个查询的`select_type`就是`DEPENDENT SUBQUERY`，比如下面这个查询：

    ```
    mysql> EXPLAIN SELECT * FROM s1 WHERE key1 IN (SELECT key1 FROM s2 WHERE s1.key2 = s2.key2) OR key3 = 'a';
    +----+--------------------+-------+------------+------+-------------------+----------+---------+-------------------+------+----------+-------------+
    | id | select_type        | table | partitions | type | possible_keys     | key      | key_len | ref               | rows | filtered | Extra       |
    +----+--------------------+-------+------------+------+-------------------+----------+---------+-------------------+------+----------+-------------+
    |  1 | PRIMARY            | s1    | NULL       | ALL  | idx_key3          | NULL     | NULL    | NULL              | 9688 |   100.00 | Using where |
    |  2 | DEPENDENT SUBQUERY | s2    | NULL       | ref  | idx_key2,idx_key1 | idx_key2 | 5       | xiaohaizi.s1.key2 |    1 |    10.00 | Using where |
    +----+--------------------+-------+------------+------+-------------------+----------+---------+-------------------+------+----------+-------------+
    2 rows in set, 2 warnings (0.00 sec)
    ```

    &emsp;&emsp;需要大家注意的是，<span style="color:red">select_type为DEPENDENT SUBQUERY的查询可能会被执行多次</span>。

- `DEPENDENT UNION`

    &emsp;&emsp;在包含`UNION`或者`UNION ALL`的大查询中，如果各个小查询都依赖于外层查询的话，那除了最左边的那个小查询之外，其余的小查询的`select_type`的值就是`DEPENDENT UNION`。说的有些绕，比方说下面这个查询：

    ```
    mysql> EXPLAIN SELECT * FROM s1 WHERE key1 IN (SELECT key1 FROM s2 WHERE key1 = 'a' UNION SELECT key1 FROM s1 WHERE key1 = 'b');
    +----+--------------------+------------+------------+------+---------------+----------+---------+-------+------+----------+--------------------------+
    | id | select_type        | table      | partitions | type | possible_keys | key      | key_len | ref   | rows | filtered | Extra                    |
    +----+--------------------+------------+------------+------+---------------+----------+---------+-------+------+----------+--------------------------+
    |  1 | PRIMARY            | s1         | NULL       | ALL  | NULL          | NULL     | NULL    | NULL  | 9688 |   100.00 | Using where              |
    |  2 | DEPENDENT SUBQUERY | s2         | NULL       | ref  | idx_key1      | idx_key1 | 303     | const |   12 |   100.00 | Using where; Using index |
    |  3 | DEPENDENT UNION    | s1         | NULL       | ref  | idx_key1      | idx_key1 | 303     | const |    8 |   100.00 | Using where; Using index |
    | NULL | UNION RESULT       | <union2,3> | NULL       | ALL  | NULL          | NULL     | NULL    | NULL  | NULL |     NULL | Using temporary          |
    +----+--------------------+------------+------------+------+---------------+----------+---------+-------+------+----------+--------------------------+
    4 rows in set, 1 warning (0.03 sec)
    ```

    &emsp;&emsp;这个查询比较复杂啊，大查询里包含了一个子查询，子查询里又是由`UNION`连起来的两个小查询。从执行计划中可以看出来，`SELECT key1 FROM s2 WHERE key1 = 'a'`这个小查询由于是子查询中第一个查询，所以它的`select_type`是`DEPENDENT SUBQUERY`，而`SELECT key1 FROM s1 WHERE key1 = 'b'`这个查询的`select_type`就是`DEPENDENT UNION`。

- `DERIVED`

    &emsp;&emsp;对于采用物化的方式执行的包含派生表的查询，该派生表对应的子查询的`select_type`就是`DERIVED`，比方说下面这个查询：

    ```
    mysql> EXPLAIN SELECT * FROM (SELECT key1, count(*) as c FROM s1 GROUP BY key1) AS derived_s1 where c > 1;
    +----+-------------+------------+------------+-------+---------------+----------+---------+------+------+----------+-------------+
    | id | select_type | table      | partitions | type  | possible_keys | key      | key_len | ref  | rows | filtered | Extra       |
    +----+-------------+------------+------------+-------+---------------+----------+---------+------+------+----------+-------------+
    |  1 | PRIMARY     | <derived2> | NULL       | ALL   | NULL          | NULL     | NULL    | NULL | 9688 |    33.33 | Using where |
    |  2 | DERIVED     | s1         | NULL       | index | idx_key1      | idx_key1 | 303     | NULL | 9688 |   100.00 | Using index |
    +----+-------------+------------+------------+-------+---------------+----------+---------+------+------+----------+-------------+
    2 rows in set, 1 warning (0.00 sec)
    ```

    &emsp;&emsp;从执行计划中可以看出，`id`为`2`的记录就代表子查询的执行方式，它的`select_type`是`DERIVED`，说明该子查询是以物化的方式执行的。`id`为`1`的记录代表外层查询，大家注意看它的`table`列显示的是`<derived2>`，表示该查询是针对将派生表物化之后的表进行查询的。

    ```
    小贴士：如果派生表可以通过和外层查询合并的方式执行的话，执行计划又是另一番景象，大家可以试试～
    ```

- `MATERIALIZED`

    &emsp;&emsp;当查询优化器在执行包含子查询的语句时，选择将子查询物化之后与外层查询进行连接查询时，该子查询对应的`select_type`属性就是`MATERIALIZED`，比如下面这个查询：

    ```
    mysql> EXPLAIN SELECT * FROM s1 WHERE key1 IN (SELECT key1 FROM s2);
    +----+--------------+-------------+------------+--------+---------------+------------+---------+-------------------+------+----------+-------------+
    | id | select_type  | table       | partitions | type   | possible_keys | key        | key_len | ref               | rows | filtered | Extra       |
    +----+--------------+-------------+------------+--------+---------------+------------+---------+-------------------+------+----------+-------------+
    |  1 | SIMPLE       | s1          | NULL       | ALL    | idx_key1      | NULL       | NULL    | NULL              | 9688 |   100.00 | Using where |
    |  1 | SIMPLE       | <subquery2> | NULL       | eq_ref | <auto_key>    | <auto_key> | 303     | xiaohaizi.s1.key1 |    1 |   100.00 | NULL        |
    |  2 | MATERIALIZED | s2          | NULL       | index  | idx_key1      | idx_key1   | 303     | NULL              | 9954 |   100.00 | Using index |
    +----+--------------+-------------+------------+--------+---------------+------------+---------+-------------------+------+----------+-------------+
    3 rows in set, 1 warning (0.01 sec)
    ```

    &emsp;&emsp;执行计划的第三条记录的`id`值为`2`，说明该条记录对应的是一个单表查询，从它的`select_type`值为`MATERIALIZED`可以看出，查询优化器是要把子查询先转换成物化表。然后看执行计划的前两条记录的`id`值都为`1`，说明这两条记录对应的表进行连接查询，需要注意的是第二条记录的`table`列的值是`<subquery2>`，说明该表其实就是`id`为`2`对应的子查询执行之后产生的物化表，然后将`s1`和该物化表进行连接查询。

- `UNCACHEABLE SUBQUERY`

    不常用，就不多介绍了。
- `UNCACHEABLE UNION`

    不常用，就不多介绍了。

### partitions

&emsp;&emsp;由于我们压根儿就没介绍过分区是什么，所以这个输出列我们也就不说了，一般情况下我们的查询语句的执行计划的`partitions`列的值都是`NULL`。

### type

&emsp;&emsp;我们前面说过执行计划的一条记录就代表着`MySQL`对某个表的执行查询时的访问方法，其中的`type`列就表明了这个访问方法是什么，比方说下面这个查询：

```
mysql> EXPLAIN SELECT * FROM s1 WHERE key1 = 'a';
+----+-------------+-------+------------+------+---------------+----------+---------+-------+------+----------+-------+
| id | select_type | table | partitions | type | possible_keys | key      | key_len | ref   | rows | filtered | Extra |
+----+-------------+-------+------------+------+---------------+----------+---------+-------+------+----------+-------+
|  1 | SIMPLE      | s1    | NULL       | ref  | idx_key1      | idx_key1 | 303     | const |    8 |   100.00 | NULL  |
+----+-------------+-------+------------+------+---------------+----------+---------+-------+------+----------+-------+
1 row in set, 1 warning (0.04 sec)
```

&emsp;&emsp;可以看到`type`列的值是`ref`，表明`MySQL`即将使用`ref`访问方法来执行对`s1`表的查询。但是我们之前只介绍过对使用`InnoDB`存储引擎的表进行单表访问的一些访问方法，完整的访问方法如下：`system`，`const`，`eq_ref`，`ref`，`fulltext`，`ref_or_null`，`index_merge`，`unique_subquery`，`index_subquery`，`range`，`index`，`ALL`。当然我们还要详细介绍一下：

- `system`

    &emsp;&emsp;当表中只有一条记录并且<span style="color:red">该表使用的存储引擎的统计数据是精确的，比如MyISAM、Memory</span>，那么对该表的访问方法就是`system`。比方说我们新建一个`MyISAM`表，并为其插入一条记录：

    ```
    mysql> CREATE TABLE t(i int) Engine=MyISAM;
    Query OK, 0 rows affected (0.05 sec)
    
    mysql> INSERT INTO t VALUES(1);
    Query OK, 1 row affected (0.01 sec)
    ```

    &emsp;&emsp;然后我们看一下查询这个表的执行计划：

    ```
    mysql> EXPLAIN SELECT * FROM t;
    +----+-------------+-------+------------+--------+---------------+------+---------+------+------+----------+-------+
    | id | select_type | table | partitions | type   | possible_keys | key  | key_len | ref  | rows | filtered | Extra |
    +----+-------------+-------+------------+--------+---------------+------+---------+------+------+----------+-------+
    |  1 | SIMPLE      | t     | NULL       | system | NULL          | NULL | NULL    | NULL |    1 |   100.00 | NULL  |
    +----+-------------+-------+------------+--------+---------------+------+---------+------+------+----------+-------+
    1 row in set, 1 warning (0.00 sec)
    ```

    &emsp;&emsp;可以看到`type`列的值就是`system`了。

    ```
    小贴士：你可以把表改成使用InnoDB存储引擎，试试看执行计划的type列是什么。
    ```

- `const`

    &emsp;&emsp;这个我们前面介绍过，就是当我们根据主键或者唯一二级索引列与常数进行等值匹配时，对单表的访问方法就是`const`，比如：

    ```
    mysql> EXPLAIN SELECT * FROM s1 WHERE id = 5;
    +----+-------------+-------+------------+-------+---------------+---------+---------+-------+------+----------+-------+
    | id | select_type | table | partitions | type  | possible_keys | key     | key_len | ref   | rows | filtered | Extra |
    +----+-------------+-------+------------+-------+---------------+---------+---------+-------+------+----------+-------+
    |  1 | SIMPLE      | s1    | NULL       | const | PRIMARY       | PRIMARY | 4       | const |    1 |   100.00 | NULL  |
    +----+-------------+-------+------------+-------+---------------+---------+---------+-------+------+----------+-------+
    1 row in set, 1 warning (0.01 sec)
    ```

- `eq_ref`

    &emsp;&emsp;在连接查询时，如果被驱动表是通过主键或者唯一二级索引列等值匹配的方式进行访问的（如果该主键或者唯一二级索引是联合索引的话，所有的索引列都必须进行等值比较），则对该被驱动表的访问方法就是`eq_ref`，比方说：

    ```
    mysql> EXPLAIN SELECT * FROM s1 INNER JOIN s2 ON s1.id = s2.id;
    +----+-------------+-------+------------+--------+---------------+---------+---------+-----------------+------+----------+-------+
    | id | select_type | table | partitions | type   | possible_keys | key     | key_len | ref             | rows | filtered | Extra |
    +----+-------------+-------+------------+--------+---------------+---------+---------+-----------------+------+----------+-------+
    |  1 | SIMPLE      | s1    | NULL       | ALL    | PRIMARY       | NULL    | NULL    | NULL            | 9688 |   100.00 | NULL  |
    |  1 | SIMPLE      | s2    | NULL       | eq_ref | PRIMARY       | PRIMARY | 4       | xiaohaizi.s1.id |    1 |   100.00 | NULL  |
    +----+-------------+-------+------------+--------+---------------+---------+---------+-----------------+------+----------+-------+
    2 rows in set, 1 warning (0.01 sec)
    ```

    &emsp;&emsp;从执行计划的结果中可以看出，`MySQL`打算将`s1`作为驱动表，`s2`作为被驱动表，重点关注`s2`的访问方法是`eq_ref`，表明在访问`s2`表的时候可以通过主键的等值匹配来进行访问。

- `ref`

    &emsp;&emsp;当通过普通的二级索引列与常量进行等值匹配时来查询某个表，那么对该表的访问方法就<span style="color:red">可能</span>是`ref`，最开始举过例子了，就不重复举例了。

- `fulltext`

    &emsp;&emsp;全文索引，我们没有细讲过，跳过～

- `ref_or_null`

    &emsp;&emsp;当对普通二级索引进行等值匹配查询，该索引列的值也可以是`NULL`值时，那么对该表的访问方法就<span style="color:red">可能</span>是`ref_or_null`，比如说：

    ```
    mysql> EXPLAIN SELECT * FROM s1 WHERE key1 = 'a' OR key1 IS NULL;
    +----+-------------+-------+------------+-------------+---------------+----------+---------+-------+------+----------+-----------------------+
    | id | select_type | table | partitions | type        | possible_keys | key      | key_len | ref   | rows | filtered | Extra                 |
    +----+-------------+-------+------------+-------------+---------------+----------+---------+-------+------+----------+-----------------------+
    |  1 | SIMPLE      | s1    | NULL       | ref_or_null | idx_key1      | idx_key1 | 303     | const |    9 |   100.00 | Using index condition |
    +----+-------------+-------+------------+-------------+---------------+----------+---------+-------+------+----------+-----------------------+
    1 row in set, 1 warning (0.01 sec)
    ```

- `index_merge`

    &emsp;&emsp;一般情况下对于某个表的查询只能使用到一个索引，但我们介绍单表访问方法时特意强调了在某些场景下可以使用`Intersection`、`Union`、`Sort-Union`这三种索引合并的方式来执行查询，忘掉的回去补一下，我们看一下执行计划中是怎么体现`MySQL`使用索引合并的方式来对某个表执行查询的：

    ```
    mysql> EXPLAIN SELECT * FROM s1 WHERE key1 = 'a' OR key3 = 'a';
    +----+-------------+-------+------------+-------------+-------------------+-------------------+---------+------+------+----------+---------------------------------------------+
    | id | select_type | table | partitions | type        | possible_keys     | key               | key_len | ref  | rows | filtered | Extra                                       |
    +----+-------------+-------+------------+-------------+-------------------+-------------------+---------+------+------+----------+---------------------------------------------+
    |  1 | SIMPLE      | s1    | NULL       | index_merge | idx_key1,idx_key3 | idx_key1,idx_key3 | 303,303 | NULL |   14 |   100.00 | Using union(idx_key1,idx_key3); Using where |
    +----+-------------+-------+------------+-------------+-------------------+-------------------+---------+------+------+----------+---------------------------------------------+
    1 row in set, 1 warning (0.01 sec)
    ```

    &emsp;&emsp;从执行计划的`type`列的值是`index_merge`就可以看出，`MySQL`打算使用索引合并的方式来执行对`s1`表的查询。

- `unique_subquery`

    &emsp;&emsp;类似于两表连接中被驱动表的`eq_ref`访问方法，`unique_subquery`是针对在一些包含`IN`子查询的查询语句中，如果查询优化器决定将`IN`子查询转换为`EXISTS`子查询，而且子查询可以使用到主键进行等值匹配的话，那么该子查询执行计划的`type`列的值就是`unique_subquery`，比如下面的这个查询语句：

    ```
    mysql> EXPLAIN SELECT * FROM s1 WHERE key2 IN (SELECT id FROM s2 where s1.key1 = s2.key1) OR key3 = 'a';
    +----+--------------------+-------+------------+-----------------+------------------+---------+---------+------+------+----------+-------------+
    | id | select_type        | table | partitions | type            | possible_keys    | key     | key_len | ref  | rows | filtered | Extra       |
    +----+--------------------+-------+------------+-----------------+------------------+---------+---------+------+------+----------+-------------+
    |  1 | PRIMARY            | s1    | NULL       | ALL             | idx_key3         | NULL    | NULL    | NULL | 9688 |   100.00 | Using where |
    |  2 | DEPENDENT SUBQUERY | s2    | NULL       | unique_subquery | PRIMARY,idx_key1 | PRIMARY | 4       | func |    1 |    10.00 | Using where |
    +----+--------------------+-------+------------+-----------------+------------------+---------+---------+------+------+----------+-------------+
    2 rows in set, 2 warnings (0.00 sec)
    ```

    &emsp;&emsp;可以看到执行计划的第二条记录的`type`值就是`unique_subquery`，说明在执行子查询时会使用到`id`列的索引。

- `index_subquery`

    &emsp;&emsp;`index_subquery`与`unique_subquery`类似，只不过访问子查询中的表时使用的是普通的索引，比如这样：

    ```
    mysql> EXPLAIN SELECT * FROM s1 WHERE common_field IN (SELECT key3 FROM s2 where s1.key1 = s2.key1) OR key3 = 'a';
    +----+--------------------+-------+------------+----------------+-------------------+----------+---------+------+------+----------+-------------+
    | id | select_type        | table | partitions | type           | possible_keys     | key      | key_len | ref  | rows | filtered | Extra       |
    +----+--------------------+-------+------------+----------------+-------------------+----------+---------+------+------+----------+-------------+
    |  1 | PRIMARY            | s1    | NULL       | ALL            | idx_key3          | NULL     | NULL    | NULL | 9688 |   100.00 | Using where |
    |  2 | DEPENDENT SUBQUERY | s2    | NULL       | index_subquery | idx_key1,idx_key3 | idx_key3 | 303     | func |    1 |    10.00 | Using where |
    +----+--------------------+-------+------------+----------------+-------------------+----------+---------+------+------+----------+-------------+
    2 rows in set, 2 warnings (0.01 sec)
    ```

- `range`

    &emsp;&emsp;如果使用索引获取某些`范围区间`的记录，那么就<span style="color:red">可能</span>使用到`range`访问方法，比如下面的这个查询：

    ```
    mysql> EXPLAIN SELECT * FROM s1 WHERE key1 IN ('a', 'b', 'c');
    +----+-------------+-------+------------+-------+---------------+----------+---------+------+------+----------+-----------------------+
    | id | select_type | table | partitions | type  | possible_keys | key      | key_len | ref  | rows | filtered | Extra                 |
    +----+-------------+-------+------------+-------+---------------+----------+---------+------+------+----------+-----------------------+
    |  1 | SIMPLE      | s1    | NULL       | range | idx_key1      | idx_key1 | 303     | NULL |   27 |   100.00 | Using index condition |
    +----+-------------+-------+------------+-------+---------------+----------+---------+------+------+----------+-----------------------+
    1 row in set, 1 warning (0.01 sec)
    ```

    &emsp;&emsp;或者：

    ```
    
    mysql> EXPLAIN SELECT * FROM s1 WHERE key1 > 'a' AND key1 < 'b';
    +----+-------------+-------+------------+-------+---------------+----------+---------+------+------+----------+-----------------------+
    | id | select_type | table | partitions | type  | possible_keys | key      | key_len | ref  | rows | filtered | Extra                 |
    +----+-------------+-------+------------+-------+---------------+----------+---------+------+------+----------+-----------------------+
    |  1 | SIMPLE      | s1    | NULL       | range | idx_key1      | idx_key1 | 303     | NULL |  294 |   100.00 | Using index condition |
    +----+-------------+-------+------------+-------+---------------+----------+---------+------+------+----------+-----------------------+
    1 row in set, 1 warning (0.00 sec)
    ```

- `index`

    &emsp;&emsp;当我们可以使用索引覆盖，但需要扫描全部的索引记录时，该表的访问方法就是`index`，比如这样：

    ```
    mysql> EXPLAIN SELECT key_part2 FROM s1 WHERE key_part3 = 'a';
    +----+-------------+-------+------------+-------+---------------+--------------+---------+------+------+----------+--------------------------+
    | id | select_type | table | partitions | type  | possible_keys | key          | key_len | ref  | rows | filtered | Extra                    |
    +----+-------------+-------+------------+-------+---------------+--------------+---------+------+------+----------+--------------------------+
    |  1 | SIMPLE      | s1    | NULL       | index | NULL          | idx_key_part | 909     | NULL | 9688 |    10.00 | Using where; Using index |
    +----+-------------+-------+------------+-------+---------------+--------------+---------+------+------+----------+--------------------------+
    1 row in set, 1 warning (0.00 sec)
    ```

    &emsp;&emsp;上述查询中的搜索列表中只有`key_part2`一个列，而且搜索条件中也只有`key_part3`一个列，这两个列又恰好包含在`idx_key_part`这个索引中，可是搜索条件`key_part3`不能直接使用该索引进行`ref`或者`range`方式的访问，只能扫描整个`idx_key_part`索引的记录，所以查询计划的`type`列的值就是`index`。

    ```
    小贴士：再一次强调，对于使用InnoDB存储引擎的表来说，二级索引的记录只包含索引列和主键列的值，而聚簇索引中包含用户定义的全部列以及一些隐藏列，所以扫描二级索引的代价比直接全表扫描，也就是扫描聚簇索引的代价更低一些。
    ```

- `ALL`

    &emsp;&emsp;最熟悉的全表扫描，就不多介绍了，直接看例子：

    ```
    mysql> EXPLAIN SELECT * FROM s1;
    +----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+-------+
    | id | select_type | table | partitions | type | possible_keys | key  | key_len | ref  | rows | filtered | Extra |
    +----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+-------+
    |  1 | SIMPLE      | s1    | NULL       | ALL  | NULL          | NULL | NULL    | NULL | 9688 |   100.00 | NULL  |
    +----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+-------+
    1 row in set, 1 warning (0.00 sec)
    ```

&emsp;&emsp;一般来说，这些访问方法按照我们介绍它们的顺序性能依次变差。其中除了`All`这个访问方法外，其余的访问方法都能用到索引，除了`index_merge`访问方法外，其余的访问方法都最多只能用到一个索引。

### possible_keys和key

&emsp;&emsp;在`EXPLAIN`语句输出的执行计划中，`possible_keys`列表示在某个查询语句中，对某个表执行单表查询时可能用到的索引有哪些，`key`列表示实际用到的索引有哪些，比方说下面这个查询：

```
mysql> EXPLAIN SELECT * FROM s1 WHERE key1 > 'z' AND key3 = 'a';
+----+-------------+-------+------------+------+-------------------+----------+---------+-------+------+----------+-------------+
| id | select_type | table | partitions | type | possible_keys     | key      | key_len | ref   | rows | filtered | Extra       |
+----+-------------+-------+------------+------+-------------------+----------+---------+-------+------+----------+-------------+
|  1 | SIMPLE      | s1    | NULL       | ref  | idx_key1,idx_key3 | idx_key3 | 303     | const |    6 |     2.75 | Using where |
+----+-------------+-------+------------+------+-------------------+----------+---------+-------+------+----------+-------------+
1 row in set, 1 warning (0.01 sec)
```

&emsp;&emsp;上述执行计划的`possible_keys`列的值是`idx_key1,idx_key3`，表示该查询可能使用到`idx_key1,idx_key3`两个索引，然后`key`列的值是`idx_key3`，表示经过查询优化器计算使用不同索引的成本后，最后决定使用`idx_key3`来执行查询比较划算。

&emsp;&emsp;不过有一点比较特别，就是在使用`index`访问方法来查询某个表时，`possible_keys`列是空的，而`key`列展示的是实际使用到的索引，比如这样：

```
mysql> EXPLAIN SELECT key_part2 FROM s1 WHERE key_part3 = 'a';
+----+-------------+-------+------------+-------+---------------+--------------+---------+------+------+----------+--------------------------+
| id | select_type | table | partitions | type  | possible_keys | key          | key_len | ref  | rows | filtered | Extra                    |
+----+-------------+-------+------------+-------+---------------+--------------+---------+------+------+----------+--------------------------+
|  1 | SIMPLE      | s1    | NULL       | index | NULL          | idx_key_part | 909     | NULL | 9688 |    10.00 | Using where; Using index |
+----+-------------+-------+------------+-------+---------------+--------------+---------+------+------+----------+--------------------------+
1 row in set, 1 warning (0.00 sec)
```

&emsp;&emsp;另外需要注意的一点是，<span style="color:red">possible_keys列中的值并不是越多越好，可能使用的索引越多，查询优化器计算查询成本时就得花费更长时间，所以如果可以的话，尽量删除那些用不到的索引</span>。

### key_len

&emsp;&emsp;`key_len`列表示当优化器决定使用某个索引执行查询时，该索引记录的最大长度，它是由这三个部分构成的：

- 对于使用固定长度类型的索引列来说，它实际占用的存储空间的最大长度就是该固定值，对于指定字符集的变长类型的索引列来说，比如某个索引列的类型是`VARCHAR(100)`，使用的字符集是`utf8`，那么该列实际占用的最大存储空间就是`100 × 3 = 300`个字节。
- 如果该索引列可以存储`NULL`值，则`key_len`比不可以存储`NULL`值时多1个字节。
- 对于变长字段来说，都会有2个字节的空间来存储该变长列的实际长度。

&emsp;&emsp;比如下面这个查询：

```
mysql> EXPLAIN SELECT * FROM s1 WHERE id = 5;
+----+-------------+-------+------------+-------+---------------+---------+---------+-------+------+----------+-------+
| id | select_type | table | partitions | type  | possible_keys | key     | key_len | ref   | rows | filtered | Extra |
+----+-------------+-------+------------+-------+---------------+---------+---------+-------+------+----------+-------+
|  1 | SIMPLE      | s1    | NULL       | const | PRIMARY       | PRIMARY | 4       | const |    1 |   100.00 | NULL  |
+----+-------------+-------+------------+-------+---------------+---------+---------+-------+------+----------+-------+
1 row in set, 1 warning (0.01 sec)
```

&emsp;&emsp;由于`id`列的类型是`INT`，并且不可以存储`NULL`值，所以在使用该列的索引时`key_len`大小就是`4`。当索引列可以存储`NULL`值时，比如：

```
mysql> EXPLAIN SELECT * FROM s1 WHERE key2 = 5;
+----+-------------+-------+------------+-------+---------------+----------+---------+-------+------+----------+-------+
| id | select_type | table | partitions | type  | possible_keys | key      | key_len | ref   | rows | filtered | Extra |
+----+-------------+-------+------------+-------+---------------+----------+---------+-------+------+----------+-------+
|  1 | SIMPLE      | s1    | NULL       | const | idx_key2      | idx_key2 | 5       | const |    1 |   100.00 | NULL  |
+----+-------------+-------+------------+-------+---------------+----------+---------+-------+------+----------+-------+
1 row in set, 1 warning (0.00 sec)
```

&emsp;&emsp;可以看到`key_len`列就变成了`5`，比使用`id`列的索引时多了`1`。

&emsp;&emsp;对于可变长度的索引列来说，比如下面这个查询：

```
mysql> EXPLAIN SELECT * FROM s1 WHERE key1 = 'a';
+----+-------------+-------+------------+------+---------------+----------+---------+-------+------+----------+-------+
| id | select_type | table | partitions | type | possible_keys | key      | key_len | ref   | rows | filtered | Extra |
+----+-------------+-------+------------+------+---------------+----------+---------+-------+------+----------+-------+
|  1 | SIMPLE      | s1    | NULL       | ref  | idx_key1      | idx_key1 | 303     | const |    8 |   100.00 | NULL  |
+----+-------------+-------+------------+------+---------------+----------+---------+-------+------+----------+-------+
1 row in set, 1 warning (0.00 sec)
```

&emsp;&emsp;由于`key1`列的类型是`VARCHAR(100)`，所以该列实际最多占用的存储空间就是`300`字节，又因为该列允许存储`NULL`值，所以`key_len`需要加`1`，又因为该列是可变长度列，所以`key_len`需要加`2`，所以最后`ken_len`的值就是`303`。

&emsp;&emsp;有的同学可能有疑问：你在前面介绍`InnoDB`行格式的时候不是说，存储变长字段的实际长度不是可能占用1个字节或者2个字节么？为什么现在不管三七二十一都用了`2`个字节？这里需要强调的一点是，执行计划的生成是在`MySQL server`层中的功能，并不是针对具体某个存储引擎的功能，设计`MySQL`的大佬在执行计划中输出`key_len`列主要是为了让我们区分某个使用联合索引的查询具体用了几个索引列，而不是为了准确的说明针对某个具体存储引擎存储变长字段的实际长度占用的空间到底是占用1个字节还是2个字节。比方说下面这个使用到联合索引`idx_key_part`的查询：

```
mysql> EXPLAIN SELECT * FROM s1 WHERE key_part1 = 'a';
+----+-------------+-------+------------+------+---------------+--------------+---------+-------+------+----------+-------+
| id | select_type | table | partitions | type | possible_keys | key          | key_len | ref   | rows | filtered | Extra |
+----+-------------+-------+------------+------+---------------+--------------+---------+-------+------+----------+-------+
|  1 | SIMPLE      | s1    | NULL       | ref  | idx_key_part  | idx_key_part | 303     | const |   12 |   100.00 | NULL  |
+----+-------------+-------+------------+------+---------------+--------------+---------+-------+------+----------+-------+
1 row in set, 1 warning (0.00 sec)
```

&emsp;&emsp;我们可以从执行计划的`key_len`列中看到值是`303`，这意味着`MySQL`在执行上述查询中只能用到`idx_key_part`索引的一个索引列，而下面这个查询：

```
mysql> EXPLAIN SELECT * FROM s1 WHERE key_part1 = 'a' AND key_part2 = 'b';
+----+-------------+-------+------------+------+---------------+--------------+---------+-------------+------+----------+-------+
| id | select_type | table | partitions | type | possible_keys | key          | key_len | ref         | rows | filtered | Extra |
+----+-------------+-------+------------+------+---------------+--------------+---------+-------------+------+----------+-------+
|  1 | SIMPLE      | s1    | NULL       | ref  | idx_key_part  | idx_key_part | 606     | const,const |    1 |   100.00 | NULL  |
+----+-------------+-------+------------+------+---------------+--------------+---------+-------------+------+----------+-------+
1 row in set, 1 warning (0.01 sec)
```

&emsp;&emsp;这个查询的执行计划的`ken_len`列的值是`606`，说明执行这个查询的时候可以用到联合索引`idx_key_part`的两个索引列。

### ref

&emsp;&emsp;当使用索引列等值匹配的条件去执行查询时，也就是在访问方法是`const`、`eq_ref`、`ref`、`ref_or_null`、`unique_subquery`、`index_subquery`其中之一时，`ref`列展示的就是与索引列作等值匹配的东东是什么，比如只是一个常数或者是某个列。大家看下面这个查询：

```
mysql> EXPLAIN SELECT * FROM s1 WHERE key1 = 'a';
+----+-------------+-------+------------+------+---------------+----------+---------+-------+------+----------+-------+
| id | select_type | table | partitions | type | possible_keys | key      | key_len | ref   | rows | filtered | Extra |
+----+-------------+-------+------------+------+---------------+----------+---------+-------+------+----------+-------+
|  1 | SIMPLE      | s1    | NULL       | ref  | idx_key1      | idx_key1 | 303     | const |    8 |   100.00 | NULL  |
+----+-------------+-------+------------+------+---------------+----------+---------+-------+------+----------+-------+
1 row in set, 1 warning (0.01 sec)
```

&emsp;&emsp;可以看到`ref`列的值是`const`，表明在使用`idx_key1`索引执行查询时，与`key1`列作等值匹配的对象是一个常数，当然有时候更复杂一点：

```
mysql> EXPLAIN SELECT * FROM s1 INNER JOIN s2 ON s1.id = s2.id;
+----+-------------+-------+------------+--------+---------------+---------+---------+-----------------+------+----------+-------+
| id | select_type | table | partitions | type   | possible_keys | key     | key_len | ref             | rows | filtered | Extra |
+----+-------------+-------+------------+--------+---------------+---------+---------+-----------------+------+----------+-------+
|  1 | SIMPLE      | s1    | NULL       | ALL    | PRIMARY       | NULL    | NULL    | NULL            | 9688 |   100.00 | NULL  |
|  1 | SIMPLE      | s2    | NULL       | eq_ref | PRIMARY       | PRIMARY | 4       | xiaohaizi.s1.id |    1 |   100.00 | NULL  |
+----+-------------+-------+------------+--------+---------------+---------+---------+-----------------+------+----------+-------+
2 rows in set, 1 warning (0.00 sec)
```

&emsp;&emsp;可以看到对被驱动表`s2`的访问方法是`eq_ref`，而对应的`ref`列的值是`xiaohaizi.s1.id`，这说明在对被驱动表进行访问时会用到`PRIMARY`索引，也就是聚簇索引与一个列进行等值匹配的条件，于`s2`表的`id`作等值匹配的对象就是`xiaohaizi.s1.id`列（注意这里把数据库名也写出来了）。

&emsp;&emsp;有的时候与索引列进行等值匹配的对象是一个函数，比方说下面这个查询：

```
mysql> EXPLAIN SELECT * FROM s1 INNER JOIN s2 ON s2.key1 = UPPER(s1.key1);
+----+-------------+-------+------------+------+---------------+----------+---------+------+------+----------+-----------------------+
| id | select_type | table | partitions | type | possible_keys | key      | key_len | ref  | rows | filtered | Extra                 |
+----+-------------+-------+------------+------+---------------+----------+---------+------+------+----------+-----------------------+
|  1 | SIMPLE      | s1    | NULL       | ALL  | NULL          | NULL     | NULL    | NULL | 9688 |   100.00 | NULL                  |
|  1 | SIMPLE      | s2    | NULL       | ref  | idx_key1      | idx_key1 | 303     | func |    1 |   100.00 | Using index condition |
+----+-------------+-------+------------+------+---------------+----------+---------+------+------+----------+-----------------------+
2 rows in set, 1 warning (0.00 sec)
```

&emsp;&emsp;我们看执行计划的第二条记录，可以看到对`s2`表采用`ref`访问方法执行查询，然后在查询计划的`ref`列里输出的是`func`，说明与`s2`表的`key1`列进行等值匹配的对象是一个函数。

### rows

&emsp;&emsp;如果查询优化器决定使用全表扫描的方式对某个表执行查询时，执行计划的`rows`列就代表预计需要扫描的行数，如果使用索引来执行查询时，执行计划的`rows`列就代表预计扫描的索引记录行数。比如下面这个查询：

```
mysql> EXPLAIN SELECT * FROM s1 WHERE key1 > 'z';
+----+-------------+-------+------------+-------+---------------+----------+---------+------+------+----------+-----------------------+
| id | select_type | table | partitions | type  | possible_keys | key      | key_len | ref  | rows | filtered | Extra                 |
+----+-------------+-------+------------+-------+---------------+----------+---------+------+------+----------+-----------------------+
|  1 | SIMPLE      | s1    | NULL       | range | idx_key1      | idx_key1 | 303     | NULL |  266 |   100.00 | Using index condition |
+----+-------------+-------+------------+-------+---------------+----------+---------+------+------+----------+-----------------------+
1 row in set, 1 warning (0.00 sec)
```

&emsp;&emsp;我们看到执行计划的`rows`列的值是`266`，这意味着查询优化器在经过分析使用`idx_key1`进行查询的成本之后，觉得满足`key1 > 'z'`这个条件的记录只有`266`条。

### filtered

&emsp;&emsp;之前在分析连接查询的成本时提出过一个`condition filtering`的概念，就是`MySQL`在计算驱动表扇出时采用的一个策略：

- 如果使用的是全表扫描的方式执行的单表查询，那么计算驱动表扇出时需要估计出满足搜索条件的记录到底有多少条。
- 如果使用的是索引执行的单表扫描，那么计算驱动表扇出的时候需要估计出满足除使用到对应索引的搜索条件外的其他搜索条件的记录有多少条。

&emsp;&emsp;比方说下面这个查询：

```
mysql> EXPLAIN SELECT * FROM s1 WHERE key1 > 'z' AND common_field = 'a';
+----+-------------+-------+------------+-------+---------------+----------+---------+------+------+----------+------------------------------------+
| id | select_type | table | partitions | type  | possible_keys | key      | key_len | ref  | rows | filtered | Extra                              |
+----+-------------+-------+------------+-------+---------------+----------+---------+------+------+----------+------------------------------------+
|  1 | SIMPLE      | s1    | NULL       | range | idx_key1      | idx_key1 | 303     | NULL |  266 |    10.00 | Using index condition; Using where |
+----+-------------+-------+------------+-------+---------------+----------+---------+------+------+----------+------------------------------------+
1 row in set, 1 warning (0.00 sec)
```

&emsp;&emsp;从执行计划的`key`列中可以看出来，该查询使用`idx_key1`索引来执行查询，从`rows`列可以看出满足`key1 > 'z'`的记录有`266`条。执行计划的`filtered`列就代表查询优化器预测在这`266`条记录中，有多少条记录满足其余的搜索条件，也就是`common_field = 'a'`这个条件的百分比。此处`filtered`列的值是`10.00`，说明查询优化器预测在`266`条记录中有`10.00%`的记录满足`common_field = 'a'`这个条件。

&emsp;&emsp;对于单表查询来说，这个`filtered`列的值没什么意义，我们更关注在连接查询中驱动表对应的执行计划记录的`filtered`值，比方说下面这个查询：

```
mysql> EXPLAIN SELECT * FROM s1 INNER JOIN s2 ON s1.key1 = s2.key1 WHERE s1.common_field = 'a';
+----+-------------+-------+------------+------+---------------+----------+---------+-------------------+------+----------+-------------+
| id | select_type | table | partitions | type | possible_keys | key      | key_len | ref               | rows | filtered | Extra       |
+----+-------------+-------+------------+------+---------------+----------+---------+-------------------+------+----------+-------------+
|  1 | SIMPLE      | s1    | NULL       | ALL  | idx_key1      | NULL     | NULL    | NULL              | 9688 |    10.00 | Using where |
|  1 | SIMPLE      | s2    | NULL       | ref  | idx_key1      | idx_key1 | 303     | xiaohaizi.s1.key1 |    1 |   100.00 | NULL        |
+----+-------------+-------+------------+------+---------------+----------+---------+-------------------+------+----------+-------------+
2 rows in set, 1 warning (0.00 sec)
```

&emsp;&emsp;从执行计划中可以看出来，查询优化器打算把`s1`当作驱动表，`s2`当作被驱动表。我们可以看到驱动表`s1`表的执行计划的`rows`列为`9688`， `filtered`列为`10.00`，这意味着驱动表`s1`的扇出值就是`9688 × 10.00% = 968.8`，这说明还要对被驱动表执行大约`968`次查询。

### Extra

&emsp;&emsp;顾名思义，`Extra`列是用来说明一些额外信息的，我们可以通过这些额外信息来更准确的理解`MySQL`到底将如何执行给定的查询语句。`MySQL`提供的额外信息有好几十个，我们就不一个一个介绍了（都介绍了感觉我们的文章就跟文档差不多了～），所以我们只挑一些平时常见的或者比较重要的额外信息介绍给大家。

- `No tables used`

    &emsp;&emsp;当查询语句的没有`FROM`子句时将会提示该额外信息，比如：

    ```
    mysql> EXPLAIN SELECT 1;
    +----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+----------------+
    | id | select_type | table | partitions | type | possible_keys | key  | key_len | ref  | rows | filtered | Extra          |
    +----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+----------------+
    |  1 | SIMPLE      | NULL  | NULL       | NULL | NULL          | NULL | NULL    | NULL | NULL |     NULL | No tables used |
    +----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+----------------+
    1 row in set, 1 warning (0.00 sec)
    ```

- `Impossible WHERE`

    &emsp;&emsp;查询语句的`WHERE`子句永远为`FALSE`时将会提示该额外信息，比方说：

    ```
    mysql> EXPLAIN SELECT * FROM s1 WHERE 1 != 1;
    +----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+------------------+
    | id | select_type | table | partitions | type | possible_keys | key  | key_len | ref  | rows | filtered | Extra            |
    +----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+------------------+
    |  1 | SIMPLE      | NULL  | NULL       | NULL | NULL          | NULL | NULL    | NULL | NULL |     NULL | Impossible WHERE |
    +----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+------------------+
    1 row in set, 1 warning (0.01 sec)
    ```

- `No matching min/max row`

    &emsp;&emsp;当查询列表处有`MIN`或者`MAX`聚集函数，但是并没有符合`WHERE`子句中的搜索条件的记录时，将会提示该额外信息，比方说：

    ```
    mysql> EXPLAIN SELECT MIN(key1) FROM s1 WHERE key1 = 'abcdefg';
    +----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+-------------------------+
    | id | select_type | table | partitions | type | possible_keys | key  | key_len | ref  | rows | filtered | Extra                   |
    +----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+-------------------------+
    |  1 | SIMPLE      | NULL  | NULL       | NULL | NULL          | NULL | NULL    | NULL | NULL |     NULL | No matching min/max row |
    +----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+-------------------------+
    1 row in set, 1 warning (0.00 sec)
    ```

- `Using index`

    &emsp;&emsp;当我们的查询列表以及搜索条件中只包含属于某个索引的列，也就是在可以使用索引覆盖的情况下，在`Extra`列将会提示该额外信息。比方说下面这个查询中只需要用到`idx_key1`而不需要回表操作：

    ```
    mysql> EXPLAIN SELECT key1 FROM s1 WHERE key1 = 'a';
    +----+-------------+-------+------------+------+---------------+----------+---------+-------+------+----------+-------------+
    | id | select_type | table | partitions | type | possible_keys | key      | key_len | ref   | rows | filtered | Extra       |
    +----+-------------+-------+------------+------+---------------+----------+---------+-------+------+----------+-------------+
    |  1 | SIMPLE      | s1    | NULL       | ref  | idx_key1      | idx_key1 | 303     | const |    8 |   100.00 | Using index |
    +----+-------------+-------+------------+------+---------------+----------+---------+-------+------+----------+-------------+
    1 row in set, 1 warning (0.00 sec)
    ```

- `Using index condition`

    &emsp;&emsp;有些搜索条件中虽然出现了索引列，但却不能使用到索引，比如下面这个查询：

    ```
    SELECT * FROM s1 WHERE key1 > 'z' AND key1 LIKE '%a';
    ```

    &emsp;&emsp;其中的`key1 > 'z'`可以使用到索引，但是`key1 LIKE '%a'`却无法使用到索引，在以前版本的`MySQL`中，是按照下面步骤来执行这个查询的：
  - 先根据`key1 > 'z'`这个条件，从二级索引`idx_key1`中获取到对应的二级索引记录。
  - 根据上一步骤得到的二级索引记录中的主键值进行回表，找到完整的用户记录再检测该记录是否符合`key1 LIKE '%a'`这个条件，将符合条件的记录加入到最后的结果集。

    &emsp;&emsp;但是虽然`key1 LIKE '%a'`不能组成范围区间参与`range`访问方法的执行，但这个条件毕竟只涉及到了`key1`列，所以设计`MySQL`的大佬把上面的步骤改进了一下：
  - 先根据`key1 > 'z'`这个条件，定位到二级索引`idx_key1`中对应的二级索引记录。
  - 对于指定的二级索引记录，先不着急回表，而是先检测一下该记录是否满足`key1 LIKE '%a'`这个条件，如果这个条件不满足，则该二级索引记录压根儿就没必要回表。
  - 对于满足`key1 LIKE '%a'`这个条件的二级索引记录执行回表操作。

    &emsp;&emsp;我们说回表操作其实是一个随机`IO`，比较耗时，所以上述修改虽然只改进了一点点，但是可以省去好多回表操作的成本。设计`MySQL`的大佬们把他们的这个改进称之为`索引条件下推`（英文名：`Index Condition Pushdown`）。

    &emsp;&emsp;如果在查询语句的执行过程中将要使用`索引条件下推`这个特性，在`Extra`列中将会显示`Using index condition`，比如这样：
  
  ```
  mysql> EXPLAIN SELECT * FROM s1 WHERE key1 > 'z' AND key1 LIKE '%b';
    +----+-------------+-------+------------+-------+---------------+----------+---------+------+------+----------+-----------------------+
    | id | select_type | table | partitions | type  | possible_keys | key      | key_len | ref  | rows | filtered | Extra                 |
    +----+-------------+-------+------------+-------+---------------+----------+---------+------+------+----------+-----------------------+
    |  1 | SIMPLE      | s1    | NULL       | range | idx_key1      | idx_key1 | 303     | NULL |  266 |   100.00 | Using index condition |
    +----+-------------+-------+------------+-------+---------------+----------+---------+------+------+----------+-----------------------+
    1 row in set, 1 warning (0.01 sec)
  ```

- `Using where`

    &emsp;&emsp;当我们使用全表扫描来执行对某个表的查询，并且该语句的`WHERE`子句中有针对该表的搜索条件时，在`Extra`列中会提示上述额外信息。比如下面这个查询：

    ```
    mysql> EXPLAIN SELECT * FROM s1 WHERE common_field = 'a';
    +----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+-------------+
    | id | select_type | table | partitions | type | possible_keys | key  | key_len | ref  | rows | filtered | Extra       |
    +----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+-------------+
    |  1 | SIMPLE      | s1    | NULL       | ALL  | NULL          | NULL | NULL    | NULL | 9688 |    10.00 | Using where |
    +----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+-------------+
    1 row in set, 1 warning (0.01 sec)
    ```

    &emsp;&emsp;当使用索引访问来执行对某个表的查询，并且该语句的`WHERE`子句中有除了该索引包含的列之外的其他搜索条件时，在`Extra`列中也会提示上述额外信息。比如下面这个查询虽然使用`idx_key1`索引执行查询，但是搜索条件中除了包含`key1`的搜索条件`key1 = 'a'`，还有包含`common_field`的搜索条件，所以`Extra`列会显示`Using where`的提示：

    ```
    mysql> EXPLAIN SELECT * FROM s1 WHERE key1 = 'a' AND common_field = 'a';
    +----+-------------+-------+------------+------+---------------+----------+---------+-------+------+----------+-------------+
    | id | select_type | table | partitions | type | possible_keys | key      | key_len | ref   | rows | filtered | Extra       |
    +----+-------------+-------+------------+------+---------------+----------+---------+-------+------+----------+-------------+
    |  1 | SIMPLE      | s1    | NULL       | ref  | idx_key1      | idx_key1 | 303     | const |    8 |    10.00 | Using where |
    +----+-------------+-------+------------+------+---------------+----------+---------+-------+------+----------+-------------+
    1 row in set, 1 warning (0.00 sec)
    ```

- `Using join buffer (Block Nested Loop)`

    &emsp;&emsp;在连接查询执行过程中，当被驱动表不能有效的利用索引加快访问速度，`MySQL`一般会为其分配一块名叫`join buffer`的内存块来加快查询速度，也就是我们所讲的`基于块的嵌套循环算法`，比如下面这个查询语句：

    ```
    mysql> EXPLAIN SELECT * FROM s1 INNER JOIN s2 ON s1.common_field = s2.common_field;
    +----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+----------------------------------------------------+
    | id | select_type | table | partitions | type | possible_keys | key  | key_len | ref  | rows | filtered | Extra                                              |
    +----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+----------------------------------------------------+
    |  1 | SIMPLE      | s1    | NULL       | ALL  | NULL          | NULL | NULL    | NULL | 9688 |   100.00 | NULL                                               |
    |  1 | SIMPLE      | s2    | NULL       | ALL  | NULL          | NULL | NULL    | NULL | 9954 |    10.00 | Using where; Using join buffer (Block Nested Loop) |
    +----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+----------------------------------------------------+
    2 rows in set, 1 warning (0.03 sec)
    ```

    &emsp;&emsp;可以在对`s2`表的执行计划的`Extra`列显示了两个提示：

  - `Using join buffer (Block Nested Loop)`：这是因为对表`s2`的访问不能有效利用索引，只好退而求其次，使用`join buffer`来减少对`s2`表的访问次数，从而提高性能。

  - `Using where`：可以看到查询语句中有一个`s1.common_field = s2.common_field`条件，因为`s1`是驱动表，`s2`是被驱动表，所以在访问`s2`表时，`s1.common_field`的值已经确定下来了，所以实际上查询`s2`表的条件就是`s2.common_field = 一个常数`，所以提示了`Using where`额外信息。

- `Not exists`

    &emsp;&emsp;当我们使用左（外）连接时，如果`WHERE`子句中包含要求被驱动表的某个列等于`NULL`值的搜索条件，而且那个列又是不允许存储`NULL`值的，那么在该表的执行计划的`Extra`列就会提示`Not exists`额外信息，比如这样：

    ```
    mysql> EXPLAIN SELECT * FROM s1 LEFT JOIN s2 ON s1.key1 = s2.key1 WHERE s2.id IS NULL;
    +----+-------------+-------+------------+------+---------------+----------+---------+-------------------+------+----------+-------------------------+
    | id | select_type | table | partitions | type | possible_keys | key      | key_len | ref               | rows | filtered | Extra                   |
    +----+-------------+-------+------------+------+---------------+----------+---------+-------------------+------+----------+-------------------------+
    |  1 | SIMPLE      | s1    | NULL       | ALL  | NULL          | NULL     | NULL    | NULL              | 9688 |   100.00 | NULL                    |
    |  1 | SIMPLE      | s2    | NULL       | ref  | idx_key1      | idx_key1 | 303     | xiaohaizi.s1.key1 |    1 |    10.00 | Using where; Not exists |
    +----+-------------+-------+------------+------+---------------+----------+---------+-------------------+------+----------+-------------------------+
    2 rows in set, 1 warning (0.00 sec)
    ```

    &emsp;&emsp;上述查询中`s1`表是驱动表，`s2`表是被驱动表，`s2.id`列是不允许存储`NULL`值的，而`WHERE`子句中又包含`s2.id IS NULL`的搜索条件，这意味着必定是驱动表的记录在被驱动表中找不到匹配`ON`子句条件的记录才会把该驱动表的记录加入到最终的结果集，所以对于某条驱动表中的记录来说，如果能在被驱动表中找到1条符合`ON`子句条件的记录，那么该驱动表的记录就不会被加入到最终的结果集，也就是说我们<span style="color:red">没有必要到被驱动表中找到全部符合ON子句条件的记录</span>，这样可以稍微节省一点性能。

    ```
    小贴士：右（外）连接可以被转换为左（外）连接，所以就不提右（外）连接的情况了。
    ```

- `Using intersect(...)`、`Using union(...)`和`Using sort_union(...)`

    &emsp;&emsp;如果执行计划的`Extra`列出现了`Using intersect(...)`提示，说明准备使用`Intersect`索引合并的方式执行查询，括号中的`...`表示需要进行索引合并的索引名称；如果出现了`Using union(...)`提示，说明准备使用`Union`索引合并的方式执行查询；出现了`Using sort_union(...)`提示，说明准备使用`Sort-Union`索引合并的方式执行查询。比如这个查询的执行计划：

    ```
    mysql> EXPLAIN SELECT * FROM s1 WHERE key1 = 'a' AND key3 = 'a';
    +----+-------------+-------+------------+-------------+-------------------+-------------------+---------+------+------+----------+-------------------------------------------------+
    | id | select_type | table | partitions | type        | possible_keys     | key               | key_len | ref  | rows | filtered | Extra                                           |
    +----+-------------+-------+------------+-------------+-------------------+-------------------+---------+------+------+----------+-------------------------------------------------+
    |  1 | SIMPLE      | s1    | NULL       | index_merge | idx_key1,idx_key3 | idx_key3,idx_key1 | 303,303 | NULL |    1 |   100.00 | Using intersect(idx_key3,idx_key1); Using where |
    +----+-------------+-------+------------+-------------+-------------------+-------------------+---------+------+------+----------+-------------------------------------------------+
    1 row in set, 1 warning (0.01 sec)
    ```

   &emsp;&emsp;其中`Extra`列就显示了`Using intersect(idx_key3,idx_key1)`，表明`MySQL`即将使用`idx_key3`和`idx_key1`这两个索引进行`Intersect`索引合并的方式执行查询。

   ```
   小贴士：剩下两种类型的索引合并的Extra列信息就不一一举例子了，自己写个查询看看呗～
   ```

- `Zero limit`

    &emsp;&emsp;当我们的`LIMIT`子句的参数为`0`时，表示压根儿不打算从表中读出任何记录，将会提示该额外信息，比如这样：

    ```
    mysql> EXPLAIN SELECT * FROM s1 LIMIT 0;
    +----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+------------+
    | id | select_type | table | partitions | type | possible_keys | key  | key_len | ref  | rows | filtered | Extra      |
    +----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+------------+
    |  1 | SIMPLE      | NULL  | NULL       | NULL | NULL          | NULL | NULL    | NULL | NULL |     NULL | Zero limit |
    +----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+------------+
    1 row in set, 1 warning (0.00 sec)
    ```

- `Using filesort`

    &emsp;&emsp;有一些情况下对结果集中的记录进行排序是可以使用到索引的，比如下面这个查询：

    ```
    mysql> EXPLAIN SELECT * FROM s1 ORDER BY key1 LIMIT 10;
    +----+-------------+-------+------------+-------+---------------+----------+---------+------+------+----------+-------+
    | id | select_type | table | partitions | type  | possible_keys | key      | key_len | ref  | rows | filtered | Extra |
    +----+-------------+-------+------------+-------+---------------+----------+---------+------+------+----------+-------+
    |  1 | SIMPLE      | s1    | NULL       | index | NULL          | idx_key1 | 303     | NULL |   10 |   100.00 | NULL  |
    +----+-------------+-------+------------+-------+---------------+----------+---------+------+------+----------+-------+
    1 row in set, 1 warning (0.03 sec)
    ```

    &emsp;&emsp;这个查询语句可以利用`idx_key1`索引直接取出`key1`列的10条记录，然后再进行回表操作就好了。但是很多情况下排序操作无法使用到索引，只能在内存中（记录较少的时候）或者磁盘中（记录较多的时候）进行排序，设计`MySQL`的大佬把这种在内存中或者磁盘上进行排序的方式统称为文件排序（英文名：`filesort`）。如果某个查询需要使用文件排序的方式执行查询，就会在执行计划的`Extra`列中显示`Using filesort`提示，比如这样：

    ```
    mysql> EXPLAIN SELECT * FROM s1 ORDER BY common_field LIMIT 10;
    +----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+----------------+
    | id | select_type | table | partitions | type | possible_keys | key  | key_len | ref  | rows | filtered | Extra          |
    +----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+----------------+
    |  1 | SIMPLE      | s1    | NULL       | ALL  | NULL          | NULL | NULL    | NULL | 9688 |   100.00 | Using filesort |
    +----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+----------------+
    1 row in set, 1 warning (0.00 sec)
    ```

    &emsp;&emsp;需要注意的是，如果查询中需要使用`filesort`的方式进行排序的记录非常多，那么这个过程是很耗费性能的，我们最好想办法将使用`文件排序`的执行方式改为使用索引进行排序。
  
- `Using temporary`

    &emsp;&emsp;在许多查询的执行过程中，`MySQL`可能会借助临时表来完成一些功能，比如去重、排序之类的，比如我们在执行许多包含`DISTINCT`、`GROUP BY`、`UNION`等子句的查询过程中，如果不能有效利用索引来完成查询，`MySQL`很有可能寻求通过建立内部的临时表来执行查询。如果查询中使用到了内部的临时表，在执行计划的`Extra`列将会显示`Using temporary`提示，比方说这样：

    ```
    mysql> EXPLAIN SELECT DISTINCT common_field FROM s1;
    +----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+-----------------+
    | id | select_type | table | partitions | type | possible_keys | key  | key_len | ref  | rows | filtered | Extra           |
    +----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+-----------------+
    |  1 | SIMPLE      | s1    | NULL       | ALL  | NULL          | NULL | NULL    | NULL | 9688 |   100.00 | Using temporary |
    +----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+-----------------+
    1 row in set, 1 warning (0.00 sec)
    ```

    &emsp;&emsp;再比如：

    ```
    mysql> EXPLAIN SELECT common_field, COUNT(*) AS amount FROM s1 GROUP BY common_field;
    +----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+---------------------------------+
    | id | select_type | table | partitions | type | possible_keys | key  | key_len | ref  | rows | filtered | Extra                           |
    +----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+---------------------------------+
    |  1 | SIMPLE      | s1    | NULL       | ALL  | NULL          | NULL | NULL    | NULL | 9688 |   100.00 | Using temporary; Using filesort |
    +----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+---------------------------------+
    1 row in set, 1 warning (0.00 sec)
    ```

    &emsp;&emsp;不知道大家注意到没有，上述执行计划的`Extra`列不仅仅包含`Using temporary`提示，还包含`Using filesort`提示，可是我们的查询语句中明明没有写`ORDER BY`子句呀？这是因为`MySQL`会在包含`GROUP BY`子句的查询中默认添加上`ORDER BY`子句，也就是说上述查询其实和下面这个查询等价：

    ```
    EXPLAIN SELECT common_field, COUNT(*) AS amount FROM s1 GROUP BY common_field ORDER BY common_field;
    ```

    &emsp;&emsp;如果我们并不想为包含`GROUP BY`子句的查询进行排序，需要我们显式的写上`ORDER BY NULL`，就像这样：

    ```
    mysql> EXPLAIN SELECT common_field, COUNT(*) AS amount FROM s1 GROUP BY common_field ORDER BY NULL;
    +----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+-----------------+
    | id | select_type | table | partitions | type | possible_keys | key  | key_len | ref  | rows | filtered | Extra           |
    +----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+-----------------+
    |  1 | SIMPLE      | s1    | NULL       | ALL  | NULL          | NULL | NULL    | NULL | 9688 |   100.00 | Using temporary |
    +----+-------------+-------+------------+------+---------------+------+---------+------+------+----------+-----------------+
    1 row in set, 1 warning (0.00 sec)
    ```

    &emsp;&emsp;这回执行计划中就没有`Using filesort`的提示了，也就意味着执行查询时可以省去对记录进行文件排序的成本了。

    &emsp;&emsp;另外，执行计划中出现`Using temporary`并不是一个好的征兆，因为建立与维护临时表要付出很大成本的，所以我们最好能使用索引来替代掉使用临时表，比方说下面这个包含`GROUP BY`子句的查询就不需要使用临时表：

    ```
    mysql> EXPLAIN SELECT key1, COUNT(*) AS amount FROM s1 GROUP BY key1;
    +----+-------------+-------+------------+-------+---------------+----------+---------+------+------+----------+-------------+
    | id | select_type | table | partitions | type  | possible_keys | key      | key_len | ref  | rows | filtered | Extra       |
    +----+-------------+-------+------------+-------+---------------+----------+---------+------+------+----------+-------------+
    |  1 | SIMPLE      | s1    | NULL       | index | idx_key1      | idx_key1 | 303     | NULL | 9688 |   100.00 | Using index |
    +----+-------------+-------+------------+-------+---------------+----------+---------+------+------+----------+-------------+
    1 row in set, 1 warning (0.00 sec)
    ```

    &emsp;&emsp;从`Extra`的`Using index`的提示里我们可以看出，上述查询只需要扫描`idx_key1`索引就可以搞定了，不再需要临时表了。

- `Start temporary, End temporary`

    &emsp;&emsp;我们前面介绍子查询的时候说过，查询优化器会优先尝试将`IN`子查询转换成`semi-join`，而`semi-join`又有好多种执行策略，当执行策略为`DuplicateWeedout`时，也就是通过建立临时表来实现为外层查询中的记录进行去重操作时，驱动表查询执行计划的`Extra`列将显示`Start temporary`提示，被驱动表查询执行计划的`Extra`列将显示`End temporary`提示，就是这样：

    ```
    mysql> EXPLAIN SELECT * FROM s1 WHERE key1 IN (SELECT key3 FROM s2 WHERE common_field = 'a');
    +----+-------------+-------+------------+------+---------------+----------+---------+-------------------+------+----------+------------------------------+
    | id | select_type | table | partitions | type | possible_keys | key      | key_len | ref               | rows | filtered | Extra                        |
    +----+-------------+-------+------------+------+---------------+----------+---------+-------------------+------+----------+------------------------------+
    |  1 | SIMPLE      | s2    | NULL       | ALL  | idx_key3      | NULL     | NULL    | NULL              | 9954 |    10.00 | Using where; Start temporary |
    |  1 | SIMPLE      | s1    | NULL       | ref  | idx_key1      | idx_key1 | 303     | xiaohaizi.s2.key3 |    1 |   100.00 | End temporary                |
    +----+-------------+-------+------------+------+---------------+----------+---------+-------------------+------+----------+------------------------------+
    2 rows in set, 1 warning (0.00 sec)
    ```

- `LooseScan`

    &emsp;&emsp;在将`In`子查询转为`semi-join`时，如果采用的是`LooseScan`执行策略，则在驱动表执行计划的`Extra`列就是显示`LooseScan`提示，比如这样：

    ```
    mysql> EXPLAIN SELECT * FROM s1 WHERE key3 IN (SELECT key1 FROM s2 WHERE key1 > 'z');
    +----+-------------+-------+------------+-------+---------------+----------+---------+-------------------+------+----------+-------------------------------------+
    | id | select_type | table | partitions | type  | possible_keys | key      | key_len | ref               | rows | filtered | Extra                               |
    +----+-------------+-------+------------+-------+---------------+----------+---------+-------------------+------+----------+-------------------------------------+
    |  1 | SIMPLE      | s2    | NULL       | range | idx_key1      | idx_key1 | 303     | NULL              |  270 |   100.00 | Using where; Using index; LooseScan |
    |  1 | SIMPLE      | s1    | NULL       | ref   | idx_key3      | idx_key3 | 303     | xiaohaizi.s2.key1 |    1 |   100.00 | NULL                                |
    +----+-------------+-------+------------+-------+---------------+----------+---------+-------------------+------+----------+-------------------------------------+
    2 rows in set, 1 warning (0.01 sec)
    ```

- `FirstMatch(tbl_name)`

    &emsp;&emsp;在将`In`子查询转为`semi-join`时，如果采用的是`FirstMatch`执行策略，则在被驱动表执行计划的`Extra`列就是显示`FirstMatch(tbl_name)`提示，比如这样：

    ```
    mysql> EXPLAIN SELECT * FROM s1 WHERE common_field IN (SELECT key1 FROM s2 where s1.key3 = s2.key3);
    +----+-------------+-------+------------+------+-------------------+----------+---------+-------------------+------+----------+-----------------------------+
    | id | select_type | table | partitions | type | possible_keys     | key      | key_len | ref               | rows | filtered | Extra                       |
    +----+-------------+-------+------------+------+-------------------+----------+---------+-------------------+------+----------+-----------------------------+
    |  1 | SIMPLE      | s1    | NULL       | ALL  | idx_key3          | NULL     | NULL    | NULL              | 9688 |   100.00 | Using where                 |
    |  1 | SIMPLE      | s2    | NULL       | ref  | idx_key1,idx_key3 | idx_key3 | 303     | xiaohaizi.s1.key3 |    1 |     4.87 | Using where; FirstMatch(s1) |
    +----+-------------+-------+------------+------+-------------------+----------+---------+-------------------+------+----------+-----------------------------+
    2 rows in set, 2 warnings (0.00 sec)
    ```

## Json格式的执行计划

&emsp;&emsp;我们上面介绍的`EXPLAIN`语句输出中缺少了一个衡量执行计划好坏的重要属性 —— <span style="color:red">成本</span>。不过设计`MySQL`的大佬贴心的为我们提供了一种查看某个执行计划花费的成本的方式：

- 在`EXPLAIN`单词和真正的查询语句中间加上`FORMAT=JSON`。

&emsp;&emsp;这样我们就可以得到一个`json`格式的执行计划，里边儿包含该计划花费的成本，比如这样：

```
mysql> EXPLAIN FORMAT=JSON SELECT * FROM s1 INNER JOIN s2 ON s1.key1 = s2.key2 WHERE s1.common_field = 'a'\G
*************************** 1. row ***************************

EXPLAIN: {
  "query_block": {
    "select_id": 1,     # 整个查询语句只有1个SELECT关键字，该关键字对应的id号为1
    "cost_info": {
      "query_cost": "3197.16"   # 整个查询的执行成本预计为3197.16
    },
    "nested_loop": [    # 几个表之间采用嵌套循环连接算法执行
    
    # 以下是参与嵌套循环连接算法的各个表的信息
      {
        "table": {
          "table_name": "s1",   # s1表是驱动表
          "access_type": "ALL",     # 访问方法为ALL，意味着使用全表扫描访问
          "possible_keys": [    # 可能使用的索引
            "idx_key1"
          ],
          "rows_examined_per_scan": 9688,   # 查询一次s1表大致需要扫描9688条记录
          "rows_produced_per_join": 968,    # 驱动表s1的扇出是968
          "filtered": "10.00",  # condition filtering代表的百分比
          "cost_info": {
            "read_cost": "1840.84",     # 稍后解释
            "eval_cost": "193.76",      # 稍后解释
            "prefix_cost": "2034.60",   # 单次查询s1表总共的成本
            "data_read_per_join": "1M"  # 读取的数据量
          },
          "used_columns": [     # 执行查询中涉及到的列
            "id",
            "key1",
            "key2",
            "key3",
            "key_part1",
            "key_part2",
            "key_part3",
            "common_field"
          ],
          
          # 对s1表访问时针对单表查询的条件
          "attached_condition": "((`xiaohaizi`.`s1`.`common_field` = 'a') and (`xiaohaizi`.`s1`.`key1` is not null))"
        }
      },
      {
        "table": {
          "table_name": "s2",   # s2表是被驱动表
          "access_type": "ref",     # 访问方法为ref，意味着使用索引等值匹配的方式访问
          "possible_keys": [    # 可能使用的索引
            "idx_key2"
          ],
          "key": "idx_key2",    # 实际使用的索引
          "used_key_parts": [   # 使用到的索引列
            "key2"
          ],
          "key_length": "5",    # key_len
          "ref": [      # 与key2列进行等值匹配的对象
            "xiaohaizi.s1.key1"
          ],
          "rows_examined_per_scan": 1,  # 查询一次s2表大致需要扫描1条记录
          "rows_produced_per_join": 968,    # 被驱动表s2的扇出是968（由于后边没有多余的表进行连接，所以这个值也没什么用）
          "filtered": "100.00",     # condition filtering代表的百分比
          
          # s2表使用索引进行查询的搜索条件
          "index_condition": "(`xiaohaizi`.`s1`.`key1` = `xiaohaizi`.`s2`.`key2`)",
          "cost_info": {
            "read_cost": "968.80",      # 稍后解释
            "eval_cost": "193.76",      # 稍后解释
            "prefix_cost": "3197.16",   # 单次查询s1、多次查询s2表总共的成本
            "data_read_per_join": "1M"  # 读取的数据量
          },
          "used_columns": [     # 执行查询中涉及到的列
            "id",
            "key1",
            "key2",
            "key3",
            "key_part1",
            "key_part2",
            "key_part3",
            "common_field"
          ]
        }
      }
    ]
  }
}
1 row in set, 2 warnings (0.00 sec)
```

&emsp;&emsp;我们使用`#`后边跟随注释的形式为大家解释了`EXPLAIN FORMAT=JSON`语句的输出内容，但是大家可能有疑问`"cost_info"`里边的成本看着怪怪的，它们是怎么计算出来的？先看`s1`表的`"cost_info"`部分：

```
"cost_info": {
    "read_cost": "1840.84",
    "eval_cost": "193.76",
    "prefix_cost": "2034.60",
    "data_read_per_join": "1M"
}
```

- `read_cost`是由下面这两部分组成的：

  - `IO`成本
  - 检测`rows × (1 - filter)`条记录的`CPU`成本

    ```
    小贴士：rows和filter都是我们前面介绍执行计划的输出列，在JSON格式的执行计划中，rows相当于rows_examined_per_scan，filtered名称不变。
    ```

- `eval_cost`是这样计算的：

   &emsp;&emsp;检测 `rows × filter`条记录的成本。

- `prefix_cost`就是单独查询`s1`表的成本，也就是：

    `read_cost + eval_cost`

- `data_read_per_join`表示在此次查询中需要读取的数据量，我们就不多介绍这个了。

```
小贴士：大家其实没必要关注MySQL为什么使用这么古怪的方式计算出read_cost和eval_cost，关注prefix_cost是查询s1表的成本就好了。
```

&emsp;&emsp;对于`s2`表的`"cost_info"`部分是这样的：

```
"cost_info": {
    "read_cost": "968.80",
    "eval_cost": "193.76",
    "prefix_cost": "3197.16",
    "data_read_per_join": "1M"
}
```

&emsp;&emsp;由于`s2`表是被驱动表，所以可能被读取多次，这里的`read_cost`和`eval_cost`是访问多次`s2`表后累加起来的值，大家主要关注里边儿的`prefix_cost`的值代表的是整个连接查询预计的成本，也就是单次查询`s1`表和多次查询`s2`表后的成本的和，也就是：

```
968.80 + 193.76 + 2034.60 = 3197.16
```

## Extented EXPLAIN

&emsp;&emsp;最后，设计`MySQL`的大佬还为我们留了个彩蛋，在我们使用`EXPLAIN`语句查看了某个查询的执行计划后，紧接着还可以使用`SHOW WARNINGS`语句查看与这个查询的执行计划有关的一些扩展信息，比如这样：

```
mysql> EXPLAIN SELECT s1.key1, s2.key1 FROM s1 LEFT JOIN s2 ON s1.key1 = s2.key1 WHERE s2.common_field IS NOT NULL;
+----+-------------+-------+------------+------+---------------+----------+---------+-------------------+------+----------+-------------+
| id | select_type | table | partitions | type | possible_keys | key      | key_len | ref               | rows | filtered | Extra       |
+----+-------------+-------+------------+------+---------------+----------+---------+-------------------+------+----------+-------------+
|  1 | SIMPLE      | s2    | NULL       | ALL  | idx_key1      | NULL     | NULL    | NULL              | 9954 |    90.00 | Using where |
|  1 | SIMPLE      | s1    | NULL       | ref  | idx_key1      | idx_key1 | 303     | xiaohaizi.s2.key1 |    1 |   100.00 | Using index |
+----+-------------+-------+------------+------+---------------+----------+---------+-------------------+------+----------+-------------+
2 rows in set, 1 warning (0.00 sec)

mysql> SHOW WARNINGS\G
*************************** 1. row ***************************
  Level: Note
   Code: 1003
Message: /* select#1 */ select `xiaohaizi`.`s1`.`key1` AS `key1`,`xiaohaizi`.`s2`.`key1` AS `key1` from `xiaohaizi`.`s1` join `xiaohaizi`.`s2` where ((`xiaohaizi`.`s1`.`key1` = `xiaohaizi`.`s2`.`key1`) and (`xiaohaizi`.`s2`.`common_field` is not null))
1 row in set (0.00 sec)
```

&emsp;&emsp;大家可以看到`SHOW WARNINGS`展示出来的信息有三个字段，分别是`Level`、`Code`、`Message`。我们最常见的就是`Code`为`1003`的信息，当`Code`值为`1003`时，`Message`字段展示的信息<span style="color:red">类似于</span>查询优化器将我们的查询语句重写后的语句。比如我们上面的查询本来是一个左（外）连接查询，但是有一个`s2.common_field IS NOT NULL`的条件，着就会导致查询优化器把左（外）连接查询优化为内连接查询，从`SHOW WARNINGS`的`Message`字段也可以看出来，原本的`LEFT JOIN`已经变成了`JOIN`。

&emsp;&emsp;但是大家一定要注意，我们说`Message`字段展示的信息<span style="color:red">类似于</span>查询优化器将我们的查询语句重写后的语句，并不是等价于，也就是说`Message`字段展示的信息并不是标准的查询语句，在很多情况下并不能直接拿到黑框框中运行，它只能作为帮助我们理解查`MySQL`将如何执行查询语句的一个参考依据而已。

## 总结

|列名|描述|
|:--:|:--|
|`id`|在一个大的查询语句中每个`SELECT`关键字都对应一个唯一的`id`|
|`select_type`|`SELECT`关键字对应的那个查询的类型|
|`table`|表名|
|`partitions`|匹配的分区信息|
|`type`|针对单表的访问方法|
|`possible_keys`|可能用到的索引|
|`key`|实际上使用的索引|
|`key_len`|实际使用到的索引长度|
|`ref`|当使用索引列等值查询时，与索引列进行等值匹配的对象信息|
|`rows`|预估的需要读取的记录条数|
|`filtered`|某个表经过搜索条件过滤后剩余记录条数的百分比|
|`Extra`|一些额外的信息|

### id

`id`是`EXPLAIN`语句中唯一一个必须出现的列，`id`的值代表在一个大的查询语句中，每个`SELECT`关键字都对应一个唯一的`id`

### select_type

查询的类别

|名称|描述|
|:--:|:--|
|`SIMPLE`| 查询语句中不包含UNION或者子查询的查询都算作是SIMPLE类型|
|`PRIMARY`|对于包含UNION、UNION ALL或者子查询的大查询来说，它是由几个小查询组成的，其中最左边的那个查询的select_type值就是PRIMARY|
|`UNION`| 对于包含UNION或者UNION ALL的大查询来说，它是由几个小查询组成的，其中除了最左边的那个小查询以外，其余的小查询的select_type值就是UNION|
|`UNION RESULT`|MySQL选择使用临时表来完成UNION查询的去重工作，针对该临时表的查询的select_type就是UNION RESULT|
|`SUBQUERY`|F如果包含子查询的查询语句不能够转为对应的semi-join的形式，并且该子查询是不相关子查询，并且查询优化器决定采用将该子查询物化的方案来执行该子查询时，该子查询的第一个SELECT关键字代表的那个查询的select_type就是SUBQUERY|
|`DEPENDENT SUBQUERY`|F如果包含子查询的查询语句不能够转为对应的semi-join的形式，并且该子查询是相关子查询，则该子查询的第一个SELECT关键字代表的那个查询的select_type就是DEPENDENT SUBQUERY|
|`DEPENDENT UNION`|在包含UNION或者UNION ALL的大查询中，如果各个小查询都依赖于外层查询的话，那除了最左边的那个小查询之外，其余的小查询的select_type的值就是DEPENDENT UNION|
|`DERIVED`|对于采用物化的方式执行的包含派生表的查询，该派生表对应的子查询的select_type就是DERIVED|
|`MATERIALIZED`|当查询优化器在执行包含子查询的语句时，选择将子查询物化之后与外层查询进行连接查询时，该子查询对应的select_type属性就是MATERIALIZED|
|`UNCACHEABLE SUBQUERY`|A subquery for which the result cannot be cached and must be re-evaluated for each row of the outer query|
|`UNCACHEABLE UNION`|The second or later select in a UNION that belongs to an uncacheable subquery (see UNCACHEABLE SUBQUERY)|

### partitions

未做解释

### type

|名称|描述|
|------|-------|
| system | 当表中只有一条记录并且该表使用的存储引擎的统计数据是精确的，比如MyISAM、Memory，那么对该表的访问方法就是system |
| const | 根据主键或者唯一二级索引列与常数进行等值匹配时，对单表的访问方法就是const |
| eq_ref |  在连接查询时，如果被驱动表是通过主键或者唯一二级索引列等值匹配的方式进行访问的（如果该主键或者唯一二级索引是联合索引的话，所有的索引列都必须进行等值比较），则对该被驱动表的访问方法就是eq_ref |
| ref | 当通过普通的二级索引列与常量进行等值匹配时来查询某个表，那么对该表的访问方法就可能是ref |
| ref_or_null | 当对普通二级索引进行等值匹配查询，该索引列的值也可以是NULL值时，那么对该表的访问方法就可能是ref_or_null |
| index_merge | 使用Intersection、Union、Sort-Union这三种索引合并的方式来执行查询 |
| unique_subquery | unique_subquery是针对在一些包含IN子查询的查询语句中，如果查询优化器决定将IN子查询转换为EXISTS子查询，而且子查询可以使用到主键进行等值匹配的话，那么该子查询执行计划的type列的值就是unique_subquery |
| index_subquery | index_subquery与unique_subquery类似，只不过访问子查询中的表时使用的是普通的索引 |
| range | 如果使用索引获取某些范围区间的记录，那么就可能使用到range访问方法 |
| index | 需要扫描全部的索引记录 |
| ALL | 全表扫描 |

### possible_keys和key

possible_keys列表示在某个查询语句中，对某个表执行单表查询时可能用到的索引有哪些，key列表示实际用到的索引有哪些

### key_len

key_len列表示当优化器决定使用某个索引执行查询时，该索引记录的最大长度

1. 对于使用固定长度类型的索引列来说，它实际占用的存储空间的最大长度就是该固定值，对于指定字符集的变长类型的索引列来说，比如某个索引列的类型是VARCHAR(100)，使用的字符集是utf8，那么该列实际占用的最大存储空间就是100 × 3 = 300个字节。
2. 如果该索引列可以存储NULL值，则key_len比不可以存储NULL值时多1个字节。
3. 对于变长字段来说，都会有2个字节的空间来存储该变长列的实际长度。

### ref

  当使用索引列等值匹配的条件去执行查询时，也就是在访问方法是const、eq_ref、ref、ref_or_null、unique_subquery、index_subquery其中之一时，ref列展示的就是与索引列作等值匹配的东东是什么，比如只是一个常数或者是某个列。

### rows

如果查询优化器决定使用全表扫描的方式对某个表执行查询时，执行计划的rows列就代表预计需要扫描的行数，如果使用索引来执行查询时，执行计划的rows列就代表预计扫描的索引记录行数

### filtered

1. 如果使用的是全表扫描的方式执行的单表查询，那么计算驱动表扇出时需要估计出满足搜索条件的记录到底有多少条。
2. 如果使用的是索引执行的单表扫描，那么计算驱动表扇出的时候需要估计出满足除使用到对应索引的搜索条件外的其他搜索条件的记录有多少条。

```sql
mysql> EXPLAIN SELECT * FROM s1 INNER JOIN s2 ON s1.key1 = s2.key1 WHERE s1.common_field = 'a';
+----+-------------+-------+------------+------+---------------+----------+---------+-------------------+------+----------+-------------+
| id | select_type | table | partitions | type | possible_keys | key      | key_len | ref               | rows | filtered | Extra       |
+----+-------------+-------+------------+------+---------------+----------+---------+-------------------+------+----------+-------------+
|  1 | SIMPLE      | s1    | NULL       | ALL  | idx_key1      | NULL     | NULL    | NULL              | 9688 |    10.00 | Using where |
|  1 | SIMPLE      | s2    | NULL       | ref  | idx_key1      | idx_key1 | 303     | xiaohaizi.s1.key1 |    1 |   100.00 | NULL        |
+----+-------------+-------+------------+------+---------------+----------+---------+-------------------+------+----------+-------------+
2 rows in set, 1 warning (0.00 sec)
```

从执行计划中可以看出来，查询优化器打算把s1当作驱动表，s2当作被驱动表。我们可以看到驱动表s1表的执行计划的rows列为9688， filtered列为10.00，这意味着驱动表s1的扇出值就是9688 × 10.00% = 968.8，这说明还要对被驱动表执行大约968次查询

### Extra

|名称|描述|
|------|-------|
| No tables used | 当查询语句的没有FROM子句时将会提示该额外信息 |
| Impossible WHERE | 查询语句的WHERE子句永远为FALSE时将会提示该额外信息 |
| No matching min/max row | 当查询列表处有MIN或者MAX聚集函数，但是并没有符合WHERE子句中的搜索条件的记录时，将会提示该额外信息 |
| Using index | 当我们的查询列表以及搜索条件中只包含属于某个索引的列，也就是在可以使用索引覆盖的情况下，在Extra列将会提示该额外信息。 |
| Using index condition | 有些搜索条件中虽然出现了索引列，但却不能使用到索引 |
| Using where | 当我们使用全表扫描来执行对某个表的查询，并且该语句的WHERE子句中有针对该表的搜索条件时，在Extra列中会提示上述额外信息 |
| Using join buffer (Block Nested Loop) | 在连接查询执行过程中，当被驱动表不能有效的利用索引加快访问速度，MySQL一般会为其分配一块名叫join buffer的内存块来加快查询速度，也就是我们所讲的基于块的嵌套循环算法 |
| Not exists | 当我们使用左（外）连接时，如果WHERE子句中包含要求被驱动表的某个列等于NULL值的搜索条件，而且那个列又是不允许存储NULL值的，那么在该表的执行计划的Extra列就会提示Not exists额外信息 |
| Using intersect(...)、Using union(...)和Using sort_union(...) | 索引合并 |
| Zero limit | 当我们的LIMIT子句的参数为0时，表示压根儿不打算从表中读出任何记录，将会提示该额外信息 |
| Using filesort | 结果集中的记录进行排序是可以使用到索引的 |
| Using temporary | 如果查询中使用到了内部的临时表，在执行计划的Extra列将会显示Using temporary提示 |
| Start temporary, End temporary | 看上面 |
| LooseScan | 在将In子查询转为semi-join时，如果采用的是LooseScan执行策略，则在驱动表执行计划的Extra列就是显示LooseScan提示 |
| FirstMatch(tbl_name) | 在将In子查询转为semi-join时，如果采用的是FirstMatch执行策略，则在被驱动表执行计划的Extra列就是显示FirstMatch(tbl_name)提示，比如这样： |
