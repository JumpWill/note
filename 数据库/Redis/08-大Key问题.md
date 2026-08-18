# Redis 大 Key 问题 (Big Key)

> 本章系统讲解 Redis 大 Key 问题:定义、危害、产生原因、发现方法、处理方案与预防措施。
>
> 相关章节:[内存管理与淘汰策略](07-内存管理与淘汰策略.md)、[性能调优](16-性能调优.md)、[缓存设计与常见问题](14-缓存设计与常见问题.md)

## 一、大 Key 概述

### 1.1 什么是大 Key

**大 Key (Big Key)** 指 Redis 单个 key 关联的 value 过大,或集合类型包含的元素过多。

### 1.2 大 Key 的判定标准

| 数据类型 | 大 Key 阈值 (业界共识) | 严重阈值 (建议拆分) |
|---------|-------------------------|---------------------|
| **String** | value > 10 KB | > 50 KB |
| **Hash** | field 数量 > 1,000 | > 5,000 |
| **List** | 元素数量 > 5,000 | > 20,000 |
| **Set** | 元素数量 > 5,000 | > 20,000 |
| **ZSet** | 元素数量 > 5,000 | > 20,000 |
| **Stream** | entry 数量 > 5,000 | > 20,000 |

⚠️ **注意**:这些是经验值,具体阈值取决于业务和硬件。32 GB 内存的 Redis 实例,大 Key 阈值可适当放宽;8 GB 内存则更严格。

### 1.3 大 Key 的常见形态

```bash
# 1. String 大 value
SET user:profile:1000 '{"name":"xxx","avatar":"<base64-几十KB>","bio":"..."}'

# 2. Hash 字段过多 (上千个 field)
HSET article:9999 title "..." author "..." tag1 "x" tag2 "y" ...  # 10w+ tags

# 3. List 过长 (例如: 未读消息队列无限增长)
LPUSH msg:queue:user:1000 msg1 msg2 ... msg50000

# 4. Set 元素过多 (例如: 用户黑名单积累)
SADD blacklist:user:1000 baduser1 baduser2 ... baduser50000

# 5. ZSet 排行榜过大
ZADD hot:article:202401 100 a1 99 a2 ... 10000 entries
```

---

## 二、大 Key 的危害

### 2.1 危害全景图

```text
                          ┌─────────────────────────────────┐
                          │      Redis 大 Key 的危害          │
                          └─────────────────────────────────┘
                                      │
        ┌─────────────────┬───────────┼───────────┬─────────────────┐
        │                 │           │           │                 │
        ▼                 ▼           ▼           ▼                 ▼
   ┌────────┐      ┌──────────┐  ┌──────────┐  ┌────────┐     ┌──────────┐
   │内存倾斜│      │删除阻塞  │  │带宽打满  │  │主从延迟│     │集群迁移  │
   │        │      │          │  │          │  │        │     │卡住      │
   └────────┘      └──────────┘  └──────────┘  └────────┘     └──────────┘
```

### 2.2 危害一:内存单点倾斜

**场景**: Cluster 模式下,大 Key 所在节点内存爆涨。

```text
假设 5 个节点的 Redis Cluster,每个节点 8 GB:

key hashslot 计算 → 落在 node-3

if key value = 4 GB:
   node-3 内存: 8 GB (其他数据) + 4 GB (大 Key) = 12 GB
   → OOM! node-3 内存耗尽,触发 maxmemory-policy
   → 部分 key 被淘汰(包括大 Key 本身)
   → 服务异常

其他节点: 内存使用 ~40%,严重浪费
```

**单实例模式**:
- 整个实例内存被单个大 Key 占满
- 触发 `maxmemory` 淘汰,正常 key 丢失

### 2.3 危害二:删除阻塞 (最常见)

**DEL 命令在 Redis 6.0 前是同步阻塞的**,删除大 Key 会卡死 Redis 主线程:

```bash
# 1 GB 的 String, DEL 大约耗时 1-5 秒 (SSD)
127.0.0.1:6379> DEL big:key
#   (此处 Redis 不响应任何其他命令 1-5 秒)
```

```text
DEL 大 Key 触发的事件链:

1. Redis 主线程收到 DEL 命令
2. 遍历 key 的所有元素 (例如 List 100 万个元素)
3. 逐个回收内存
4. 释放底层数据结构 (SDS、listpack、hashtable)
5. 返回 OK

整个过程单线程串行执行 → Redis 阻塞!

P99 延迟可能从 1ms 飙升到 5000ms+
```

**生产事故案例**:
- 凌晨定时任务清理 30 天的用户行为数据(`DEL behavior:user:1000` 含 100 万 entry)
- DEL 耗时 8 秒 → Redis 8 秒内无法响应 → 所有业务超时
- 监控系统告警 → DBA 紧急介入

### 2.4 危害三:网络带宽打满

```text
大 Key 场景下的网络传输:

GET big:key (4 GB value)
   ↓
单次响应占用 4 GB 带宽
   ↓
即使千兆网卡 (1 Gbps),传输也需 32 秒
   ↓
期间该连接独占带宽,其他请求排队等待

主从复制场景:
   master → slave 复制大 Key
   ↓
每次 sync / 部分 resync 都需传输大 Key 的全量数据
   ↓
占用 master-slave 间全部带宽
   ↓
其他小 Key 同步延迟
```

**集群迁移场景**:
- Cluster 重新分片时,需要迁移大 Key
- 迁移期间 slot 内其他请求阻塞或失败
- 大 Key 越大,迁移时间越长

### 2.5 危害四:主从复制延迟

```text
主从同步流程 (大 Key 场景):

master 写入大 Key (例如 HSET huge:hash f1 v1 f2 v2 ... f100000 v100000)
   ↓
生成 RDB (bgsave) 时, 大 Key 也写入 RDB
   ↓
master 向 slave 发送 RDB 字节流
   ↓
slave 接收并加载 RDB
   ↓
如果 master 频繁更新大 Key, 大 Key 的命令也写入 replication backlog
   ↓
部分重同步时, slave 需要从 backlog 拉取并 apply 这些命令
   ↓
backlog 大小有限 (默认 1 MB), 容易溢出 → 触发全量同步

结论:大 Key 频繁修改 → 主从频繁全量同步 → 严重延迟
```

### 2.6 危害五:集群 slot 迁移困难

```text
Cluster reshard 流程:

1. CLUSTER GETKEYSINSLOT slot 100 (获取 slot 内的所有 key)
2. MIGRATE target_ip target_port key 0 timeout
   ↓
大 Key 场景: MIGRATE 大 Key 耗时数秒到数十秒
   ↓
迁移期间, 该 key 不能被访问 (返回 TRYAGAIN 错误)
   ↓
业务请求失败,直到迁移完成
```

### 2.7 危害六:RDB 持久化阻塞

```text
bgsave fork 子进程流程:

master 内存: 10 GB
   ↓
fork 子进程 (Linux Copy-On-Write)
   ↓
子进程遍历内存生成 RDB
   ↓
遍历过程中,master 修改的内存页被复制 (COW)
   ↓
大 Key 所在的页被频繁修改 → COW 复制频繁 → master 内存占用飙升
   ↓
master 内存从 10 GB → 14 GB (OS OOM Killer 风险)

更糟:子进程写 RDB 时,大 Key 序列化占用 CPU + IO
```

### 2.8 危害汇总表

| 危害 | 严重度 | 触发场景 | 故障表现 |
|------|--------|----------|----------|
| 内存单点倾斜 | ⭐⭐⭐⭐ | Cluster 模式 | 节点 OOM、淘汰其他 key |
| **删除阻塞** | ⭐⭐⭐⭐⭐ | DEL / expire | **Redis 整体卡顿** |
| 网络带宽打满 | ⭐⭐⭐⭐ | GET / SET | 延迟飙升、连接超时 |
| 主从复制延迟 | ⭐⭐⭐ | 频繁修改 | 复制中断、频繁全量同步 |
| 集群迁移卡住 | ⭐⭐⭐ | Reshard | slot 内请求失败 |
| RDB fork 阻塞 | ⭐⭐ | 大内存实例 | 内存飙升、延迟抖动 |

---

## 三、大 Key 的产生原因

### 3.1 业务设计不当 (主要原因)

#### 场景 1:用户画像 / Profile 大 JSON

```java
// ❌ 错误: 把整个 profile 序列化到单个 String
public void cacheUserProfile(User user) {
    String json = JsonUtil.toJson(user);  // 假设 50 KB
    redis.setex("user:profile:" + user.getId(), 3600, json);
}
```

```java
// ✅ 正确: 用 Hash 拆分字段
public void cacheUserProfile(User user) {
    String key = "user:profile:" + user.getId();
    redis.hset(key, "name", user.getName());
    redis.hset(key, "age", user.getAge());
    redis.hset(key, "avatar", user.getAvatar());
    redis.hset(key, "bio", user.getBio());
    redis.expire(key, 3600);
}
```

#### 场景 2:无界增长的 List/Stream

```java
// ❌ 错误: 用户消息队列无限增长
public void pushMessage(Long userId, Message msg) {
    redis.lpush("msg:queue:" + userId, JsonUtil.toJson(msg));
    // 没有 LTRIM 限制, 几个月后变成 100 万 entry
}

// ✅ 正确: LTRIM 限制大小
public void pushMessage(Long userId, Message msg) {
    redis.lpush("msg:queue:" + userId, JsonUtil.toJson(msg));
    redis.ltrim("msg:queue:" + userId, 0, 999);  // 只保留最近 1000 条
}
```

#### 场景 3:大 Set 累积 (黑名单、粉丝列表)

```java
// ❌ 错误: 网红用户的粉丝列表
public void addFollower(Long starId, Long fanId) {
    redis.sadd("star:followers:" + starId, fanId.toString());
    // 1000w 粉丝 → 1000w 个 string 元素
}

// ✅ 正确: 拆分 + 滚动 Set
public void addFollower(Long starId, Long fanId) {
    long bucket = System.currentTimeMillis() / 1000 / 86400;  // 按天分桶
    redis.sadd("star:followers:" + starId + ":" + bucket, fanId.toString());
    redis.expire("star:followers:" + starId + ":" + bucket, 7 * 86400);  // 保留 7 天
}
```

### 3.2 数据未清理

```java
// ❌ 错误: 缓存了但从不清理
public void cacheQueryResult(String sql, List<Map> result) {
    String key = "query:" + DigestUtils.md5Hex(sql);
    redis.setex(key, 86400, JsonUtil.toJson(result));
    // 一个月后还在缓存,但业务早已不再用这个 SQL
}

// ✅ 正确: 主动失效 + 短 TTL
public void cacheQueryResult(String sql, List<Map> result) {
    String key = "query:" + DigestUtils.md5Hex(sql);
    redis.setex(key, 300, JsonUtil.toJson(result));  // 5 分钟 TTL
}
```

### 3.3 数据类型选错

```java
// ❌ 错误: 用 String 存有序数据
public void addRanking(Long userId, int score) {
    redis.zincrby("hot:ranking", score, userId.toString());
}

// 但 String 类型存 JSON 数组的写法也常见:
// redis.set("hot:list", "[{...},{...},...]")  ← 10000 个对象 → 1 MB+ JSON
// 这就是大 Key

// ✅ 正确: 用 ZSet
// 同上, ZSet 天然有序
```

### 3.4 在线合并 / 累加

```java
// ❌ 错误: 计数器无上限
public void incrCounter(String key) {
    redis.incr("counter:" + key);  // 假设 key 是 UUID, 永远不会自动清理
}

// 这种不会成为大 Key,但若 value 是 JSON 列表累计就会
```

---

## 四、大 Key 的发现方法

### 4.1 redis-cli --bigkeys (推荐,简单)

**原理**: SCAN 全库,对每个 key 用 STRLEN / HLEN / LLEN / SCARD / ZCARD 估算大小。

```bash
redis-cli --bigkeys

# 输出示例:
# -------- summary -------
# Biggest string found '"user:profile:1000"' has 52341 bytes
# Biggest list found '"msg:queue:9999"' has 50001 items
# Biggest hash found '"article:8888"' has 10001 fields
# Biggest set found '"star:followers:1"' has 1000000 members
# Biggest zset found '"hot:ranking"' has 50000 members

# 12 strings, 5 lists, 8 hashes, 3 sets, 2 zsets, 0 streams
# 0.32 seconds elapsed
```

**优点**:
- 内置工具,无需安装
- 快速扫描(SCAN,非阻塞)
- 给出 top-N 大 Key

**缺点**:
- 只能给出**样本** (Top 1 of each type)
- 不知道**所有**大 Key
- 不知道具体的内存占用

### 4.2 redis-cli --memkeys (Redis 7.0+)

**新增于 Redis 7.0**:基于内存占用排序。

```bash
redis-cli --memkeys -n 0

# 输出格式: key 列表 + 内存估算
# 需要 redis 7.0+
```

### 4.3 MEMORY USAGE 命令

**精确计算** 单个 key 占用的字节数:

```bash
# 单个 key
redis-cli MEMORY USAGE "user:profile:1000"
# (integer) 52341

# 批量检查 (循环)
for key in $(redis-cli --scan --pattern "user:profile:*" | head -100); do
    size=$(redis-cli MEMORY USAGE "$key")
    if [ "$size" -gt 10240 ]; then
        echo "$key: $size bytes"
    fi
done
```

**生产脚本:批量扫描大 Key**:

```bash
#!/bin/bash
# find_bigkeys.sh - 扫描整个 Redis 找出大 Key

PATTERN="${1:-*}"
THRESHOLD_KB="${2:-10}"  # 默认 10 KB
REDIS_HOST="${3:-127.0.0.1}"
REDIS_PORT="${4:-6379}"

echo "Scanning keys matching '$PATTERN' with threshold ${THRESHOLD_KB} KB..."

redis-cli -h $REDIS_HOST -p $REDIS_PORT --scan --pattern "$PATTERN" | while read key; do
    bytes=$(redis-cli -h $REDIS_HOST -p $REDIS_PORT MEMORY USAGE "$key")
    if [ -n "$bytes" ] && [ "$bytes" -gt $((THRESHOLD_KB * 1024)) ]; then
        kb=$((bytes / 1024))
        echo "${kb}KB: $key"
    fi
done | sort -rn | head -50
```

```bash
chmod +x find_bigkeys.sh
./find_bigkeys.sh "user:*" 5
# 扫描所有 user:* key, 阈值 5 KB
```

### 4.4 OBJECT 命令

```bash
# 编码类型
redis-cli OBJECT ENCODING "myset"
# "hashtable"  ← 可能是大 Key (hashtable 编码通常表示元素多)

redis-cli OBJECT IDLETIME "user:1000"
# 120  ← 120 秒未访问,可考虑淘汰

redis-cli OBJECT FREQ "user:1000"
# 5  ← LFU 频率

redis-cli OBJECT REFCOUNT "user:1000"
# 1  ← 引用计数
```

### 4.5 借助外部工具分析 RDB

**redis-rdb-tools** (Python 工具,功能最强):

```bash
pip install rdbtools python-lzf

# 1. 生成 RDB
redis-cli BGSAVE

# 2. 分析 RDB 文件,输出 CSV
rdb -c memory /var/lib/redis/dump.rdb > memory.csv

# 3. 找出大 Key (按内存排序)
sort -t, -k4 -nr memory.csv | head -20
```

**输出示例** (memory.csv 格式):

```csv
database,key,type,size,encoding,num_elements,len_largest_element
0,user:profile:1000,string,52341,raw,52341,52341
0,msg:queue:9999,list,5000000,quicklist,50001,200
0,article:8888,hash,1500000,hashtable,10001,150
```

**生成 HTML 可视化报告**:

```bash
rdb -c memory /var/lib/redis/dump.rdb --bytes 10240 -f memory_report.html
# 生成可交互的 HTML 报告, 按大小排序
```

### 4.6 Prometheus + Redis Exporter 监控

```yaml
# redis_exporter 配置 (默认就抓 Redis 指标)
# 关键告警指标:

# 1. 单个 key 内存占用
redis_key_value_max_size_bytes > 10240    # > 10 KB

# 2. 整个实例大 Key 数量
redis_bigkeys_total > 10                   # > 10 个大 Key

# 3. 实例总内存
redis_memory_used_bytes / redis_memory_max_bytes > 0.8   # > 80%
```

### 4.7 应用层主动上报

```java
// 业务侧自检: 写入前检查 key 大小
public void safeSet(String key, Object value) {
    String json = JsonUtil.toJson(value);
    int bytes = json.getBytes(StandardCharsets.UTF_8).length;

    if (bytes > 10 * 1024) {  // 10 KB 阈值
        log.warn("Large key detected: {} ({} bytes)", key, bytes);
        metrics.counter("redis.large_key.write").inc();
    }
    redis.setex(key, 3600, json);
}

// Hash 字段数检查
public void safeHset(String key, String field, String value) {
    Long count = redis.hlen(key);
    if (count != null && count > 5000) {
        log.warn("Large hash detected: {} ({} fields)", key, count);
    }
    redis.hset(key, field, value);
}
```

---

## 五、大 Key 的处理方案

### 5.1 删除大 Key

#### 方案 1:UNLINK (Redis 4.0+,强烈推荐)

**UNLINK** 是**异步删除**,Redis 立即返回 OK,实际删除由后台线程完成,**主线程不阻塞**。

```bash
# DEL: 同步阻塞
127.0.0.1:6379> DEL huge:key
# (整数延迟, 可能 1-5 秒)

# UNLINK: 异步非阻塞
127.0.0.1:6379> UNLINK huge:key
(integer) 1   ← 立即返回
```

```bash
# 批量异步删除 (适用于 SCAN + DEL 模式)
127.0.0.1:6379> UNLINK huge:key1 huge:key2 huge:key3
```

**底层原理**:

```text
UNLINK 大 Key:
1. 主线程从 keyspace 摘除这个 key (O(1))
2. 把 key 放入待回收队列 (bio 异步线程)
3. 主线程立即返回 OK
4. 后台线程 (默认 1 个) 慢慢回收内存
```

**配置后台删除线程数**:

```conf
# redis.conf
bio-cpuratio 1                     # 后台线程最大占用 CPU 比例 (默认 50%)
lazyfree-lazy-eviction yes         # 内存淘汰时也用 lazy free
lazyfree-lazy-expire yes           # key 过期也 lazy free
lazyfree-lazy-server-del yes       # DEL 命令 lazy free
```

#### 方案 2:SCAN + UNLINK 分批删除

**核心思想**: 避免单次删除过多元素,降低每次操作的开销。

```bash
# Hash 类型: HSCAN 分批 HDEL
redis-cli --no-raw HSCAN huge:hash 0 COUNT 1000 | head -100 | xargs redis-cli HDEL huge:hash
# ↑ 每次删除 1000 个 field, 分批处理

# List 类型: LPOP 逐个删除 (注意是破坏性的)
while redis-cli LLEN huge:list | grep -q "^[1-9]"; do
    redis-cli LPOP huge:list COUNT 1000 > /dev/null
    sleep 0.1
done

# Set 类型: SSCAN + SREM
redis-cli --no-raw SSCAN huge:set 0 COUNT 1000 | xargs redis-cli SREM huge:set

# ZSet 类型: ZSCAN + ZREM
redis-cli --no-raw ZSCAN huge:zset 0 COUNT 1000 | xargs redis-cli ZREM huge:zset
```

**完整生产脚本**:

```bash
#!/bin/bash
# batch_delete_hash.sh - 分批删除大 Hash

KEY="$1"
BATCH_SIZE="${2:-1000}"
SLEEP_TIME="${3:-0.1}"

echo "Deleting hash '$KEY' in batches of $BATCH_SIZE..."

total_deleted=0
cursor=0

while true; do
    # HSCAN 获取一批 field
    fields=$(redis-cli HSCAN "$KEY" $cursor COUNT $BATCH_SIZE | tail -n +2)
    cursor=$(redis-cli HSCAN "$KEY" $cursor COUNT $BATCH_SIZE | head -n 1)

    # 提取 field 名 (跳过 value)
    field_names=$(echo "$fields" | awk 'NR%2==1')

    if [ -z "$field_names" ]; then
        break
    fi

    # HDEL 批量删除
    deleted=$(redis-cli HDEL "$KEY" $field_names)
    total_deleted=$((total_deleted + deleted))

    sleep "$SLEEP_TIME"

    # cursor 0 表示完成
    if [ "$cursor" -eq 0 ]; then
        break
    fi
done

echo "Total deleted: $total_deleted"
```

#### 方案 3:lazyfree 配置兜底

即使业务代码用的是 DEL,通过配置让 Redis 自动用 lazyfree:

```conf
# redis.conf

# DEL 命令是否 lazy free
# 默认: no (同步删除)
# 推荐: yes
lazyfree-lazy-server-del yes

# EXPIRE 触发的删除是否 lazy
lazyfree-lazy-expire yes

# 内存淘汰触发的删除是否 lazy
lazyfree-lazy-eviction yes

# 后台线程最大 CPU 占用比 (默认 50%)
bio-cpuratio 1
```

**效果**: 即使误用 DEL,Redis 也自动转成异步删除,不阻塞。

### 5.2 拆分大 Key

#### 策略 1:业务拆分

```java
// ❌ 大 String
SET user:profile:1000 "{50KB JSON}"

// ✅ 拆分多个 Hash
HMSET user:1000:basic name "xxx" age 30 email "x@y.com"
HMSET user:1000:profile bio "..." avatar "base64..."
HMSET user:1000:settings lang "zh" theme "dark"

// 读时按需获取
HMGET user:1000:basic name age
HMGET user:1000:profile avatar
```

#### 策略 2:分桶 / 分片

```java
// ❌ 1 个 ZSet 存所有文章
ZADD hot:ranking 100 a1 99 a2 ... 1000000 a1000000

// ✅ 按时间分桶,每天一个 ZSet
ZADD hot:ranking:20240118 100 a1 99 a2 ...
ZADD hot:ranking:20240119 95 b1 88 b2 ...
ZADD hot:ranking:20240120 92 c1 90 c2 ...

// 读时合并多个 bucket
ZUNIONSTORE hot:ranking:tmp 3 \
    hot:ranking:20240118 hot:ranking:20240119 hot:ranking:20240120

// 或者应用层合并
List<Article> today = zrevrangeWithScores("hot:ranking:20240120", 0, 99);
List<Article> yesterday = zrevrangeWithScores("hot:ranking:20240119", 0, 99);
return merge(today, yesterday).subList(0, 100);
```

#### 策略 3:压缩

```java
// ❌ JSON 字符串 (可读但冗余)
SET article:1000 '{"title":"标题很长","content":"内容很长","tags":["..."] }'

// ✅ 使用压缩算法 (gzip + base64)
byte[] compressed = gzip(JsonUtil.toJson(article).getBytes());
redis.setex("article:1000", 3600, Base64.getEncoder().encodeToString(compressed));

// 读时解压
byte[] decompressed = ungzip(Base64.getDecoder().decode(redis.get("article:1000")));
```

**注意**: 压缩增加了 CPU 开销,小 Key 不值得压缩。**只对 > 10 KB 的大 value 压缩**。

#### 策略 4:替换数据类型

```java
// ❌ 大 JSON String
SET user:tags:1000 '["tag1","tag2",...,"tag10000"]'

// ✅ 用 Set
SADD user:tags:1000 "tag1" "tag2" ... "tag10000"
```

### 5.3 预防大 Key 产生

#### 预防 1:代码评审 Checklist

```text
大 Key 评审 Checklist:

□ 写入的 String value 大小 < 10 KB?
□ Hash field 数 < 1000?
□ List / Set / ZSet 元素数 < 5000?
□ 是否设置了合理的 TTL?
□ 是否使用 LTRIM 限制 List 长度?
□ 是否使用 ZREMRANGEBYRANK 清理 ZSet?
□ 是否使用 SRANDMEMBER + DEL 限制 Set 大小?
```

#### 预防 2:上线检查

```bash
# 灰度发布时,监控新 key 的大小
# 在 staging 环境启用监控:
config set slowlog-log-slower-than 1000   # 记录慢命令
config set slowlog-max-len 1000

# 应用启动时检查
for key in $(redis-cli --scan); do
    size=$(redis-cli MEMORY USAGE "$key")
    if [ "$size" -gt 51200 ]; then
        echo "WARNING: Large key detected: $key ($size bytes)"
    fi
done
```

#### 预防 3:容量规划

```text
预估大 Key 总内存:

业务总 key 数 = N
平均 key 大小 = S KB
大 key 比例 = R%
大 key 平均大小 = S_big KB

大 key 总内存 = N × R% × S_big KB

要求: 大 key 总内存 < Redis 实例内存的 30%

如果超过 → 拆库 / 拆分业务 / 限制 key 大小
```

#### 预防 4:数据结构选型指导

| 数据特征 | 推荐类型 | 单 key 元素上限 |
|---------|---------|-----------------|
| 单个对象 (用户资料) | Hash (按字段拆) | 100-200 field |
| 排行榜 | ZSet (按时间分桶) | 5000-10000 entry |
| 列表 (消息/通知) | List (LTRIM 限制) | 5000 entry |
| 标签 / 黑名单 | Set (按时间分桶) | 5000 member |
| JSON 配置 | String + 压缩 | 10-50 KB |
| 计数器 | String (int 编码) | 8 字节 |

---

## 六、生产实战案例

### 案例 1:定时任务清理大 Key 导致 Redis 阻塞

**事故**: 凌晨 3 点定时清理 30 天前的用户行为数据,每个用户的 list 有 100w+ entry,DEL 直接阻塞 Redis 8 秒。

**修复**:
```java
// ❌ 原代码
@Scheduled(cron = "0 0 3 * * ?")
public void cleanOldData() {
    Set<String> keys = redis.keys("behavior:user:*");
    for (String key : keys) {
        redis.del(key);  // 阻塞 Redis
    }
}

// ✅ 修复:用 UNLINK 异步删除
@Scheduled(cron = "0 0 3 * * ?")
public void cleanOldData() {
    Set<String> keys = redis.keys("behavior:user:*");
    redis.unlink(keys.toArray(new String[0]));  // 异步非阻塞
}
```

### 案例 2:Hash 字段累积变成大 Key

**事故**: 用户标签系统,HSET user:tags:1000 tag1 v1 tag2 v2 ... 累计到 50000 个 field。

**修复**:
```java
// ❌ 原代码:无限累加
public void addTag(Long userId, String tag) {
    redis.hset("user:tags:" + userId, tag, Instant.now().toString());
}

// ✅ 修复:定期 ZREMRANGEBYRANK 清理旧标签
public void addTag(Long userId, String tag) {
    String key = "user:tags:" + userId;
    redis.zadd(key, Instant.now().getEpochSecond(), tag);
    // 只保留最近 1000 个标签
    redis.zremrangeByRank(key, 0, -1001);
}
```

### 案例 3:Cluster 节点内存倾斜

**事故**: 5 节点 Cluster,某节点 8 GB 内存用满,其他节点只用 4 GB。原因是某个 key 4 GB。

**修复**:
```java
// ❌ 原代码: 单个 key 4 GB
SET user:big:profile:1 "<4GB JSON>"

// ✅ 修复:拆分到多个 key + 业务层重组
public void cacheUserProfile(Long userId, UserProfile profile) {
    String keyPrefix = "user:profile:" + userId;

    // 基础信息
    Map<String, String> basic = Map.of(
        "name", profile.getName(),
        "age", String.valueOf(profile.getAge()),
        "email", profile.getEmail()
    );
    redis.hset(keyPrefix + ":basic", basic);

    // 详细信息 (可分页加载)
    redis.hset(keyPrefix + ":detail:1", profile.getDetailPart1());
    redis.hset(keyPrefix + ":detail:2", profile.getDetailPart2());
    redis.hset(keyPrefix + ":detail:3", profile.getDetailPart3());

    redis.expire(keyPrefix + ":basic", 3600);
    redis.expire(keyPrefix + ":detail:1", 3600);
    redis.expire(keyPrefix + ":detail:2", 3600);
    redis.expire(keyPrefix + ":detail:3", 3600);
}
```

### 案例 4:大 Key 删除导致主从切换

**事故**: 删除 2 GB 的大 Hash,DEL 耗时 6 秒,期间 Sentinel 判定主节点"不健康",触发主从切换,新主没有这些数据。

**修复**:
```conf
# redis.conf

# 启用 lazy free
lazyfree-lazy-server-del yes
lazyfree-lazy-eviction yes
lazyfree-lazy-expire yes

# 调整 sentinel 判定时间
sentinel down-after-milliseconds mymaster 5000    # 默认 30s,可调小
sentinel failover-timeout mymaster 60000
```

---

## 七、大 Key 的监控与告警

### 7.1 关键监控指标

| 指标 | 含义 | 告警阈值 |
|------|------|----------|
| `redis_key_value_max_size_bytes` | 最大单 key 内存 | > 10 KB |
| `redis_db_keys` | 数据库 key 总数 | 业务预期 |
| `used_memory` / `maxmemory` | 实例内存使用率 | > 80% |
| `mem_fragmentation_ratio` | 内存碎片率 | > 1.5 或 < 1 |
| `blocked_clients` | 被阻塞的客户端 | > 10 |
| `slowlog_len` | 慢查询日志长度 | > 100 |
| `instantaneous_input_kbps` | 入带宽 | > 网络带宽 80% |
| `instantaneous_output_kbps` | 出带宽 | > 网络带宽 80% |

### 7.2 Prometheus 告警规则

```yaml
groups:
- name: redis_alerts
  rules:
  - alert: RedisLargeKey
    expr: redis_key_value_max_size_bytes > 10240
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "Redis 大 Key 检测"
      description: "实例 {{ $labels.instance }} 存在大 Key: {{ $value }} bytes"

  - alert: RedisMemoryHigh
    expr: redis_memory_used_bytes / redis_memory_max_bytes > 0.8
    for: 10m
    labels:
      severity: warning
    annotations:
      summary: "Redis 内存使用率过高"

  - alert: RedisBlockedClients
    expr: redis_blocked_clients > 10
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "Redis 有客户端被阻塞"
      description: "可能是大 Key 操作导致"
```

### 7.3 慢查询日志

```bash
# 配置
slowlog-log-slower-than 1000     # 记录 > 1ms 的命令
slowlog-max-len 1000

# 查看慢查询
redis-cli SLOWLOG GET 10
```

**大 Key 操作通常会产生慢查询**:
```text
1) 1) "DEL"
   2) (integer) 1700000000
   3) (integer) 5234        ← 5.2 秒
   4) 1) "huge:key"
   5) "127.0.0.1:12345"
   ...
```

---

## 八、大 Key 检查 Checklist

### 8.1 上线前

- [ ] 评估 key 大小上限,选合适的数据类型
- [ ] 必要时按时间/分桶拆分
- [ ] 设置合理的 TTL
- [ ] 代码评审有"大 Key 检查"项
- [ ] staging 环境跑一遍 redis-cli --bigkeys

### 8.2 运行时

- [ ] 配置 lazyfree-lazy-* (生产必开)
- [ ] Prometheus + Grafana 监控大 Key 指标
- [ ] 定期 (每周) 跑 redis-cli --bigkeys 检查
- [ ] 应用层写入前主动检查 key 大小
- [ ] 慢查询日志每日 review

### 8.3 出问题时

- [ ] 立即用 UNLINK 而非 DEL 删除
- [ ] SCAN 分批删除,避免一次性大操作
- [ ] 临时扩容 Redis 内存缓解
- [ ] 紧急情况下考虑切从库,主库重启清空

---

## 九、核心要点速记

- **大 Key 阈值**: String > 10 KB,集合 > 5000 elements
- **最大危害**: **删除阻塞** (DEL 大 Key 卡死 Redis 几秒到几十秒)
- **首选方案**: **UNLINK** (异步非阻塞, Redis 4.0+)
- **生产必加配置**: `lazyfree-lazy-server-del yes`
- **大 Key 发现**: `redis-cli --bigkeys` (样本) + `MEMORY USAGE` (精确) + `redis-rdb-tools` (RDB 分析)
- **大 Key 拆分**: 业务拆分、分桶分片、压缩、替换数据类型
- **预防**: 代码评审、容量规划、监控告警、上线检查
- **避免**: DEL 大 Key (改 UNLINK)、无界增长的 List/Set (LTRIM/ZREMRANGEBYRANK 限制)、大 JSON String (改 Hash)
- **SCAN + UNLINK 分批删除** 比 DEL 安全
- **lazyfree-lazy-server-del** 是生产环境**必开**配置
- **redis-rdb-tools** 可以生成 HTML 可视化报告,定位大 Key 最有效
- **大 Key 修改频繁** → 主从频繁全量同步 → 考虑拆分
- **大 Key 删除时**: 优先 UNLINK 而非 DEL,即使配了 lazyfree 也用 UNLINK (更可控)
- **集群场景**: 大 Key 集中在单节点 → 内存倾斜 → 拆分或分桶
- **DBA 必会**: 快速定位大 Key + 优雅删除大 Key + 监控大 Key 增长趋势

---

## 十、参考与延伸

- **Redis 官方 lazyfree 文档**: https://redis.io/docs/manual/keyspace-notifications/
- **redis-rdb-tools**: https://github.com/sripathikrishnan/redis-rdb-tools
- **第 7 章**: [内存管理与淘汰策略](07-内存管理与淘汰策略.md)
- **第 14 章**: [缓存设计与常见问题](14-缓存设计与常见问题.md)
- **第 16 章**: [性能调优](16-性能调优.md)
