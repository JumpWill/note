# etcd

高可用的分布式 KV 存储，CoreOS 开源、Raft 一致性协议，Kubernetes 的配置/元数据底座。

## 一、定位与特性

- 强一致 KV：`/foo/bar=val`，revision 全局单调递增
- Raft 保证集群写线性化，任意节点读可走 follower
- MVCC 历史保留 + 订阅（Watch），是配置中心、选主、服务发现的事实标准
- K8s 的整个 control plane 都跑在它上面：apiserver 把 Pod / Service / ConfigMap / Secret 落 etcd
- gRPC + HTTP/JSON 双协议，对外提供 v2/v3 API（v3 是当前推荐）

```text
┌────────────────────────────────────────┐
│              etcd cluster              │
│                                        │
│  ┌────────┐   ┌────────┐   ┌────────┐ │
│  │ node-1 │──▶│ node-2 │◀──│ node-3 │ │
│  │ (lead) │   │(follow)│   │(follow)│ │
│  └────┬───┘   └────┬───┘   └────┬───┘ │
│       │      Raft log replication     │
└───────┴───────────────────────────────┘
```

## 二、架构

```text
              ┌──────────── HTTP/JSON (v2) ───────────┐
              │                                        │
 Client ────▶│  etcd gRPC Proxy / gRPC-Gateway (v3)    │
              │                                        │
              └──┬─────────────────────────────────┬───┘
                 │                                 │
                 ▼                                 ▼
       ┌─────────────────────┐         ┌─────────────────────┐
       │  Raft layer         │         │  MVCC bbolt store    │
       │  (log, snapshot)    │◀───────▶│  key -> rev tree     │
       └──────────┬──────────┘         └─────────────────────┘
                  │
                  ▼
         ┌────────────────┐
         │  Lease manager │  TTL / keepalive
         └────────────────┘
```

- **Raft**：每条写先记 log，多数派 fsync 后 commit，再应用到状态机（MVCC）
- **WAL**：每个节点写 `wal/` 目录 append only，崩溃从 log 重放
- **Snapshot**：超出 `--snapshot-count` 阈值时自动压缩并打 snapshot，避免日志无限增长
- **Disk**：推荐 SSD，fsync 的延迟直接卡 P99，HDD 会频繁触发选举

## 三、数据模型（MVCC）

```text
revision:  全局单调递增，每次写 +1
   │
   ▼
key         create_rev   mod_rev   version   value
/abc        1            2         2          v2
/abc/x      3            3         1          hello
/config     5            7         3          {"k":"v3"}
/zoo        100          100       0          (deleted, tombstone)
```

- **revision**：集群全局逻辑时钟，写事务提交时递增
- **create_revision**：key 第一次创建时的 revision
- **mod_revision**：本次写入时的 revision
- **version**：该 key 的修改次数，删除后归零（tombstone 仍占历史）
- **value** 在 bbolt 里按 revision 分版本存储，compaction 之前的版本都能读

### Range 查询

```bash
# 单 key
etcdctl get /foo

# range
etcdctl get /foo --from-key --limit 100

# 前缀
etcdctl get /config/ --prefix

# 仅 key
etcdctl get /config/ --prefix --keys-only
```

### 四种操作

| 操作 | 说明 |
| ---- | ---- |
| `Range` | range / prefix / from-key，读多个 revision |
| `Put` | 写一个 revision，原子覆盖 |
| `DeleteRange` | 单 key 或 range；带 `prevK=true` 时退回旧版本 |
| `Txn` | 多 compare + 多 then/else，原子事务 |

## 四、Watch 机制

etcd 提供的「增量推送」是配置中心最关键的能力：

```text
client                          etcd server
  │  Watch(key, startRev=N, progressNotify) │
  │────────────────────────────────────────▶│
  │                                         │
  │  stream ◀────────────────────  events   │
  │   ev{N, type=PUT, key, value}           │
  │   ev{N+1, type=DELETE, key}            │
  │   ev{N+2, type=PUT, key, value}        │
```

- **基于 revision 订阅**：`startRev=N` 表示从第 N 次写开始把后续事件全推过来，能可靠重连
- **progress notify**：长无变化时服务端周期性推 `{rev, type=ProgressNotify}`，用来探测连接活性和 compaction 落后
- **多路复用**：单 gRPC stream 共享所有 watcher，减少连接数

### 1. required revision has been compacted

```text
etcd compaction 后，旧的 revision 不再保留
如果你 watch startRev=10，但 keepalive 太慢、期间已经被 compact 掉了
server 关闭 stream，客户端必须 用最新 revision 重新拉一次全量 + 重新 watch
```

处理要点：

| 现象 | 解决 |
| ---- | ---- |
| connection broken by compaction | 客户端 catch 后，重新 `Get(WithRev=currentRev)` 再 `Watch(startRev=currentRev+1)` |
| 进程启动时如何拿到最新 revision | v3 没有直接 API，可用一个「应用专属 key，每次启动写入；启动时 Get 拿到」 |

## 五、事务 Txn

Txn = N 个 `compare` + 1 个 `then` + 1 个 `else`，原子一次性提交：

```bash
# CompareAndSwap：仅当 current revision = 10 才更新
etcdctl txn --interactive \
  --compare mod_revision("/config/db") = "10" \
  --then put /config/db '{"host":"db1"}' \
  --else get /config/db
```

- 这是配置变更做「乐观锁」的核心：用 `mod_revision` 当版本号，配置 stale 时直接拒绝，避免脑裂

| compare 类型 | 说明 |
| ---- | ---- |
| `version`, `mod_revision`, `create_revision` | 整数比较 `= != < >` |
| `value` | 按字节切片比较 |

## 六、租约 Lease

Lease 给 key 绑 TTL，TTL 内客户端不发 keepalive 就会被自动删除（带 tombstone）：

```text
client                     etcd
  │  LeaseGrant(TTL=30s)  │
  │─────────────────────▶ │  id=L1
  │  KeepAlive(L1) stream │
  │◀─────┐ KeepAliveReply{TTL=30} │
  │       │ (每 ~TTL/3 一次)      │
  │  Put("k","v", lease=L1)       │
  │─────────────────────────────▶ │
```

- 应用：**服务注册**（instance 临时下线自动剔除）、**分布式锁**（持锁 = 持 lease，TTL 过期释放）、**配置 TTL**（临时配置自动失效）
- Lease 与 key 解绑：一个 lease 可挂多个 key，Lease 失效所有 key 一起删

## 七、etcdctl 常用命令

```bash
# 写读
etcdctl put /config/db '{"host":"db1"}'
etcdctl get /config/db
etcdctl get /config/db --print-value-only
etcdctl del /config/db

# 前缀
etcdctl get /config/ --prefix

# watch
etcdctl watch /config/db
etcdctl watch /config/db --rev 100

# 压缩历史
etcdctl compact 1000
etcdctl compaction --physical   # 带物理清理

# 快照
etcdctl snapshot save /tmp/etcd.db
etcdctl snapshot status /tmp/etcd.db

# member
etcdctl member list
etcdctl endpoint status --cluster -w table
etcdctl endpoint health --cluster

# user / auth
etcdctl user add root
etcdctl auth enable
etcdctl role grant-permission readwrite /config/ --prefix

# 常用 flags
ETCDCTL_API=3 etcdctl ...
  --endpoints=https://127.0.0.1:2379
  --cacert=... --cert=... --key=...
```

## 八、Go 客户端 clientv3

```go
import (
    "context"
    "fmt"
    "time"

    clientv3 "go.etcd.io/etcd/client/v3"
)

func main() {
    cli, err := clientv3.New(clientv3.Config{
        Endpoints:   []string{"http://127.0.0.1:2379"},
        DialTimeout: 5 * time.Second,
    })
    if err != nil {
        panic(err)
    }
    defer cli.Close()

    ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
    defer cancel()

    // 1) Put
    _, err = cli.Put(ctx, "/config/db", `{"host":"db1"}`)
    if err != nil {
        panic(err)
    }

    // 2) Get with prefix
    resp, err := cli.Get(ctx, "/config/", clientv3.WithPrefix(), clientv3.WithLimit(100))
    if err != nil {
        panic(err)
    }
    for _, kv := range resp.Kvs {
        fmt.Printf("%s = %s (rev=%d)\n", kv.Key, kv.Value, kv.ModRevision)
    }

    // 3) Watch: 重连重放
    go watchLoop(cli)

    // 4) Txn: CompareAndSwap
    cur, _ := cli.Get(ctx, "/config/db")
    cmps := []clientv3.Cmp{clientv3.Compare(clientv3.ModRevision("/config/db"), "=", cur.Kvs[0].ModRevision)}
    txn := cli.Txn(ctx).If(cmps...).
        Then(clientv3.OpPut("/config/db", `{"host":"db2"}`)).
        Else(clientv3.OpGet("/config/db"))
    tresp, _ := txn.Commit()
    fmt.Println("txn succeeded=", tresp.Succeeded)

    // 5) Lease + keepalive
    lease, _ := cli.Grant(ctx, 30)
    keepCh, _ := cli.KeepAlive(ctx, lease.ID)
    go func() {
        for ka := range keepCh {
            fmt.Printf("keepalive: id=%x ttl=%ds\n", ka.ID, ka.TTL)
        }
    }()
    cli.Put(ctx, "/node/1", "alive", clientv3.WithLease(lease.ID))
}

func watchLoop(cli *clientv3.Client) {
    var lastRev int64
    for {
        rch := cli.Watch(context.Background(), "/config/", clientv3.WithPrefix(), clientv3.WithRev(lastRev))
        for wr := range rch {
            if wr.Err() != nil {
                fmt.Println("watch err:", wr.Err(), "-> reconnect")
                break
            }
            for _, ev := range wr.Events {
                fmt.Printf("[%s] %s = %q\n", ev.Type, ev.Kv.Key, ev.Kv.Value)
                lastRev = ev.Kv.ModRevision
            }
        }
        time.Sleep(1 * time.Second) // compaction 时短暂 backoff 拉全量
    }
}
```

### 选主 Campaign

```go
import (
    "context"
    clientv3 "go.etcd.io/etcd/client/v3"
    "go.etcd.io/etcd/client/v3/concurrency"
)

func elect(cli *clientv3.Client, name string) {
    s, _ := concurrency.NewSession(cli, concurrency.WithTTL(10))
    e := concurrency.NewElection(s, "/election/db")
    ctx := context.Background()
    if err := e.Campaign(ctx, name); err != nil {
        panic(err)
    }
    fmt.Println("i'm leader now:", string(e.Key())) // 任期 = Key, Value=name
    // leader 工作完后 Resign 让其他节点接
}
```

## 九、配置渲染：confd

confd 监听 etcd key 变化，把模板渲染到本地配置文件，触发 `nginx -s reload` / `systemctl reload`：

```toml
# /etc/confd/conf.d/myapp.toml
[template]
src   = "myapp.conf.tmpl"
dest  = "/etc/myapp/myapp.conf"
keys  = ["/config/myapp/db", "/config/myapp/port"]
check_cmd  = "/usr/bin/nginx -t -c {{.src}}"
reload_cmd = "/usr/sbin/nginx -s reload"
```

```go-template
# /etc/confd/templates/myapp.conf.tmpl
upstream db {
  server {{getv "/config/myapp/db"}};
}
listen {{getv "/config/myapp/port"}};
```

```bash
confd -watch -backend etcd -node http://127.0.0.1:2379 -prefix /config/myapp
```

## 十、鉴权与 TLS

### 1. TLS

```bash
etcd \
  --cert-file=/etc/etcd/server.pem \
  --key-file=/etc/etcd/server-key.pem \
  --trusted-ca-file=/etc/etcd/ca.pem \
  --peer-cert-file=... --peer-key-file=... --peer-trusted-ca-file=...
```

- 客户端 gRPC 用 `WithTLS(...)` 或 `--cacert --cert --key`

### 2. RBAC

```bash
etcdctl user add app-readonly
etcdctl role add config-reader
etcdctl role grant-permission config-reader read /config/ --prefix
etcdctl user grant-role app-readonly config-reader
etcdctl auth enable
```

| 维度 | 说明 |
| ---- | ---- |
| user | 谁来调，token-based |
| role | 一个 role = 一组权限 |
| permission | `read` / `write` / `readwrite`，绑 path + range |
| root | 唯一能开 auth 的用户，必须在 enable auth 之前创建 |

## 十一、容量与限制

| 项 | 默认 / 上限 |
| ---- | ---- |
| `--quota-backend-bytes` | 默认 2 GB (8 GB 已是 SSD 上限) |
| 单 value | 推荐 ≤ 1.5 MB（gRPC 默认 max message 2MB） |
| key 数量 | 数百万级，越多 revision 越多，compaction 必须配 |
| revision 触发 | `--auto-compaction-mode=periodic --auto-compaction-retention=1h` |
| watch stream | 单 gRPC stream 多路复用，但后端有 watcher 数上限 |

### 运维要点

- db size 接近 quota → 默认 `NOSPACE` 写失败，必须 `etcdctl defrag` 在线碎片回收
- 监控：`etcd_disk_wal_fsync_duration_seconds`、`etcd_disk_backend_commit_duration_seconds`、`etcd_server_proposals_applied_total`、`etcd_server_slow_apply_total`
- `--election-timeout` 推荐 1s，`--heartbeat-interval` 100ms

## 十二、备份与恢复

### 1. snapshot

```bash
etcdctl snapshot save /var/backup/etcd-$(date +%F).db
etcdctl snapshot status /var/backup/etcd-etcd-2026-07-31.db -w table
```

- snapshot 是「一致性 + 压缩过」的物理文件，可直接喂给新集群 `etcd --data-dir=/var/lib/etcd-restore`

### 2. restore

```bash
etcdctl snapshot restore /var/backup/etcd-*.db \
  --name=node-1 \
  --initial-cluster=node-1=https://10.0.0.1:2380,node-2=https://10.0.0.2:2380 \
  --initial-advertise-peer-urls=https://10.0.0.1:2380 \
  --data-dir=/var/lib/etcd-restore
```

- 用于「旧集群迁移到新集群」、「误操作恢复时把数据导到测试环境排错」

## 十三、何时用 vs 不该用

### 适合直接当配置中心

- 应用是 Go / 任何语言都行（gRPC/HTTP 客户端），需要「强一致 + Watch 推送」
- 配置变更需要「原子 CAS」，避免脑裂（轮询型的 Apollo/Nacos 做不到 Raft 级的线性化）
- 同集群已经为 K8s 装了 etcd，复用即可
- 需要选主 / 分布式锁 / 服务发现

### 不适合

- **大 value / 大文件**：> 1.5MB 的配置进 etcd 一定错（拆小 + OSS + URL）
- **业务级高 QPS KV 读写**：etcd 推荐 < 10K ops/s 当数据源用，> 这个走 Redis / MySQL
- **跨地域多活**：单集群 Raft 受网络延迟影响，K8s 集群都是同城，跨域要走 Spanner 路线
- **复杂查询 / SQL**：etcd 是 KV 不是关系库，业务对象用 JSON 塞；想检索 → 单独建 ES / 加前缀索引

## 十四、优缺点

### 优点

- 强一致（线性化）+ Watch 增量推送是它的「杀手锏」，Nacos/Apollo 都做不到 Raft 级的一致性
- K8s 标配，背靠 CNCF 生态
- clientv3 维护活跃，Java / Go / Python / Rust 都有官方或社区 SDK
- 部署运维成熟：3/5/7 节点、snapshot、defrag 命令齐全

### 缺点

- 单 value 1.5MB、namespace 2GB 限制明显，不能当业务主库
- 运维门槛高：磁盘 IO、Raft 调参、compaction、defarg 必须心中有数
- 无内置权限 UI、无部门 / 项目概念，ACL 自己写
- 写扩展性受限于多数派 fsync，~数 K ops/s 量级

适用：K8s 控制面、Kafka/Kubernetes 等需要分布式选主、配置中心强一致、服务注册 + 健康检查、分布式锁实现者。

## 十五、最佳实践

- **集群**：生产 3 节点起步，跨可用区部署，最少 50ms RTT 内能完成一轮心跳
- **磁盘**：必须 SSD，禁用 swap，`--quota-backend-bytes=8G` 比 2G 更宽裕
- **compaction**：`--auto-compaction-mode=periodic --auto-compaction-retention=5m`，结合你的变更频率调
- **defarg**：监控 `etcd_mvcc_db_total_size_in_bytes`，>1.5GB 触发 `etcdctl defrag --cluster`
- **客户端**：永远处理 compaction 中断，重连用「最新 revision 拉全量 + 重新 watch」
- **路径规划**：用前缀做 namespace，例如 `/config/{app}/{env}/...`、`/registry/{svc}/{id}`
- **CAS 更新**：改配置前读 `mod_revision`，用 Txn 做 CAS，避免覆盖正在被改的人
- **trace**：每次写带 context，业务可追踪到哪个上游触发了配置更新
- **备份**：cron snapshot 推 S3，演练过 restore 路径
- **连接复用**：单进程一个 `clientv3.Client`，**不要**每 Put 都 New，连一下上千 RTT
