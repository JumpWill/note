# SaltStack 笔记

## 一、SaltStack 简介

SaltStack(简称 Salt)是一个基于 Python 的 **配置管理 + 远程执行** 平台,采用 **ZeroMQ** 消息总线,支持每秒上万次命令分发。SaltStack 与 Ansible、Puppet、Chef 并称"四大配置管理工具",但相比之下更强调:

- **极快的远程执行**:ZeroMQ PUB/SUB 异步推送,适合大规模服务器批量操作。
- **双模工作**:既支持 Master/Minion 架构,也支持 **Salt SSH**(纯 SSH 模式,无需安装 agent)。
- **声明式状态系统**:SLS(State)文件描述最终状态,支持幂等执行。

### 与其他工具的对比

| 维度       | SaltStack       | Ansible        | Puppet           | Chef         |
| ---------- | --------------- | -------------- | ---------------- | ------------ |
| 通信       | ZeroMQ(默认)/ RAET / SSH | SSH    | HTTPS(拉模式)    | HTTPS(拉模式) |
| Agent      | Minion          | 无(SSH)       | Agent            | Agent        |
| 性能       | 极快(可万级)   | 慢(串行 SSH)  | 中等             | 中等         |
| 配置语言   | YAML + Jinja    | YAML + Jinja   | Puppet DSL       | Ruby DSL     |
| 学习曲线   | 较陡            | 平缓           | 较陡             | 较陡         |
| 大规模集群 | 强(数千节点)   | 弱(需优化)    | 强               | 强           |

---

## 二、架构

### 1. Master / Minion 架构(默认)

```
                   ┌─────────────────────────────┐
                   │       Salt Master           │
                   │   (ZeroMQ PUB/SUB/REP)      │
                   │   - 接收 Minion 的 key       │
                   │   - 编译 SLS                 │
                   │   - 分发指令                 │
                   └──────────┬──────────────────┘
                              │ ZeroMQ (TCP 4505/4506)
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        ┌──────────┐    ┌──────────┐    ┌──────────┐
        │ Minion 1 │    │ Minion 2 │    │ Minion N │
        └──────────┘    └──────────┘    └──────────┘
```

- **端口**:Pub 端口 `4505`,Ret 端口 `4506`。
- **Minion 启动时**:连接 Master 的 4505 端口订阅消息。
- **指令下发**:Master 在 4505 上发指令,目标 Minion 通过 4506 上的 REP/REQ 模式返回结果。

### 2. Salt SSH(纯 SSH 模式)

不需要安装 Minion,通过 SSH 在目标主机上临时运行 Python + Salt 模块。适合:

- 无法安装 agent 的网络设备
- 临时调试、跨网络隔离环境
- 一次性的配置管理任务

```bash
# 用 SSH 模式执行命令
salt-ssh '*' test.ping

# 指定用户名、端口、密码
salt-ssh '*' cmd.run 'uptime' --user=ubuntu --port=2222 --ask-pass
```

### 3. Syndic(分层 Master)

当一个 Master 管理不了太多 Minion(> 5K)时,使用 Syndic:

```
Lower Master(1K Minion) → Syndic → Top Master
```

### 4. Proxy Minion

通过 Proxy Minion 代理连接 **无 agent 设备**(网络设备、API 服务的设备),如:

- 网络设备(Cisco、华为交换机)
- 存储设备
- 云资源(AWS EC2、阿里云 ECS)

---

## 三、核心概念

| 概念 | 解释 | 存放位置 |
| --- | --- | --- |
| **Grains** | 静态信息(系统信息) | Minion 端,采集 OS、CPU、内存等 |
| **Pillars** | 敏感/动态数据 | Master 端,加密存储,只发给目标 minion |
| **States** | 描述期望状态(SLS) | Master 端 |
| **Modules** | 执行模块(test.ping、cmd.run) | Master/Minion |
| **Returners** | 把执行结果存到外部系统 | Minion 端 |
| **Renderers** | SLS 文件解析器(YAML、Jinja) | Master 端 |
| **Reactor** | Master 事件触发的自动化 | Master 端 |
| **Beacons** | 监听 Minion 上的事件 | Minion 端 |
| **Engines** | Master 端的长驻进程 | Master 端 |

---

## 四、安装与初始化

### 1. 安装 Master

#### RHEL/CentOS

```bash
# 安装源
yum install -y https://repo.saltproject.io/salt/py3/redhat/salt-py3-repo-latest.el8.noarch.rpm
yum clean expire-cache

# 安装 Master
yum install -y salt-master salt-minion salt-ssh salt-syndic salt-cloud salt-api

# 启动
systemctl enable --now salt-master
```

#### Ubuntu/Debian

```bash
curl -fsSL -o /usr/share/keyrings/salt-archive-keyring.gpg https://repo.saltproject.io/salt/py3/ubuntu/22.04/amd64/latest/salt-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/salt-archive-keyring.gpg] https://repo.saltproject.io/salt/py3/ubuntu/22.04/amd64/latest jammy main" > /etc/apt/sources.list.d/salt.list
apt update
apt install -y salt-master salt-minion salt-ssh salt-syndic
```

### 2. Master 配置 `/etc/salt/master`

```yaml
# 接口绑定
interface: 0.0.0.0

# 状态文件根目录(默认 /srv/salt)
file_roots:
  base:
    - /srv/salt
    - /srv/salt/custom

# Pillar 根目录
pillar_roots:
  base:
    - /srv/pillar

# Salt 文件服务器
file_buffer_size: 1048576

# 加密 Pillar 数据(gpg 密钥目录)
gpg_keydir: /etc/salt/gpgkeys

# 自动接受 key(慎用)
auto_accept: False

# Master 端日志
log_file: /var/log/salt/master
log_level: warning
```

### 3. 安装 Minion

```bash
yum install -y salt-minion
```

### 4. Minion 配置 `/etc/salt/minion`

```yaml
# 必填:Master 地址
master: salt.example.com

# Minion 自身的 ID(默认是 hostname)
id: web01.example.com

# 多个 Master
master:
  - salt1.example.com
  - salt2.example.com

# Master 不可达时重连
master_alive_interval: 30
master_tries: 3

# Minion 端缓存目录
cachedir: /var/cache/salt/minion
```

启动 Minion:

```bash
systemctl enable --now salt-minion
```

### 5. 认证 Minion

```bash
# Master 上查看待接受的 key
salt-key -L

# 输出:
# Unaccepted Keys:
#   web01.example.com
#   web02.example.com
# Accepted Keys:
#   db01.example.com

# 接受特定 key
salt-key -a web01.example.com

# 接受所有
salt-key -A -y

# 拒绝某个
salt-key -d web01.example.com

# 打印 minion 公钥
salt-key -p web01.example.com
```

### 6. 测试连通性

```bash
# 测试所有 minion
salt '*' test.ping

# 输出:
# web01.example.com:
#     True
# web02.example.com:
#     True
```

---

## 五、远程执行

### 1. `salt` 命令格式

```bash
salt '<target>' <module>.<function> [arguments] [options]
```

```bash
# 单个 minion
salt 'web01.example.com' cmd.run 'uptime'

# 多个 minion(空格分隔)
salt 'web01* web02*' cmd.run 'date'

# 所有 minion
salt '*' cmd.run 'whoami'
```

### 2. 常用执行模块速查

| 模块 | 用途 | 示例 |
| --- | --- | --- |
| `cmd` | 执行 shell | `cmd.run 'ls -l'` |
| `file` | 文件操作 | `file.copy /src /dst` |
| `service` | 服务管理 | `service.available nginx` |
| `pkg` | 包管理 | `pkg.install nginx` |
| `user` | 用户管理 | `user.add alice` |
| `group` | 用户组 | `group.add devops` |
| `cron` | 计划任务 | `cron.present` |
| `network` | 网络配置 | `network.mod\_state eth0 up` |
| `sysctl` | 内核参数 | `sysctl.present net.ipv4.ip_forward 1` |
| `archive` | 压缩解压 | `archive.tar` |
| `mount` | 挂载 | `mount.mount /mnt` |
| `firewall` | 防火墙 | `firewall.present` |
| `iptables` | iptables | `iptables.append_policy` |
| `host` | /etc/hosts | `host.present` |
| `ssh_auth` | 免密登录 | `ssh_auth.present` |
| `grains` | 操作 grains | `grains.items` |
| `pillar` | 操作 pillar | `pillar.items` |

### 3. 常用远程执行示例

```bash
# 查看系统信息
salt '*' grains.items
salt '*' grains.get os

# 查看 IP 地址
salt '*' network.ip_addrs

# 磁盘使用
salt '*' disk.usage

# 重启服务
salt '*' service.restart nginx

# 批量传文件
salt '*' cp.get_file salt://scripts/deploy.sh /root/deploy.sh

# 看进程
salt '*' cmd.run 'ps -ef | grep nginx'
```

---

## 六、Targeting(目标匹配)

Salt 提供了非常灵活的目标匹配方式:

| 匹配方式 | 语法 | 说明 |
| --- | --- | --- |
| **Glob**(默认) | `'*'`、`'web*'`、`'web0[1-3]'` | 通配符 |
| **List** | `'web01,db01'` | 逗号分隔列表 |
| **PCRE** | `-E 'web\d+'` | Perl 正则(用 `-E`) |
| **Grain** | `-G 'os:Ubuntu'` | 用 `-G` 按 grain |
| **Grain PCRE** | `--grain-pcre 'os:Cent.*'` | grain 正则 |
| **Pillar** | `-I 'role:web'` | 按 pillar |
| **Compound** | `-C 'web* and G@os:Ubuntu'` | 组合 |
| **CIDR** | `-S '10.0.0.0/24'` | IP 网段 |
| **Range** | `--range 10.0.0.1` | 端口范围 |

### 1. Glob 通配

```bash
salt 'web*' test.ping              # 所有 web 开头的
salt 'web0[1-3]' test.ping         # web01/web02/web03
salt 'web0?' test.ping             # web0 后跟任意一个字符
```

### 2. 列表

```bash
salt -L 'web01,db01,cache01' test.ping
```

### 3. PCRE 正则

```bash
salt -E 'web\d+\.example\.com' test.ping
```

### 4. Grain 匹配

```bash
# OS 是 Ubuntu 的
salt -G 'os:Ubuntu' test.ping

# 内存大于 8G
salt -G 'mem_total:>8000' test.ping

# 内存正则在 16G-32G 之间
salt --grain-pcre 'mem_total:[1-3][6-9][0-9]{3,}' test.ping
```

### 5. Pillar 匹配

```bash
salt -I 'role:web' test.ping
salt -I 'region:us-east and env:prod' test.ping
```

### 6. Compound 复合

Salt 的 Compound 是 **布尔表达式**,支持 `and` / `or` / `not` / 括号:

```bash
# web01 且 OS 是 Ubuntu
salt -C 'web01 and G@os:Ubuntu' test.ping

# 内存大于 16G 的 web 节点
salt -C 'web* and G@mem_total:>16000' test.ping

# 复杂组合
salt -C '(web* or db*) and not G@os:Windows and S@10.0.0.0/24' test.ping
```

> 💡 Compound 是 Salt 最强大的匹配方式,生产中基本都用它。

### 7. CIDR 子网匹配

```bash
salt -S '10.0.0.0/24' test.ping
salt -S '192.168.1.100' test.ping     # 单 IP
```

### 8. 保存常用 target(节点组)

```bash
# Master 端 /etc/salt/master 中配置:
nodegroups:
  webservers: 'web01,web02,web03'
  dbservers: 'G@role:db'
  production: 'G@env:prod and not L@kubernetes'
```

```bash
salt -N webservers test.ping
salt -N production cmd.run 'hostname'
```

---

## 七、Grains(静态数据)

### 1. 内置 Grains

```bash
# 查看所有 grains
salt '*' grains.items

# 查看单项
salt '*' grains.get os
salt '*' grains.get ipv4
salt '*' grains.get num_cpus
salt '*' grains.get osrelease
salt '*' grains.get fqdn
```

常用内置 grain:

| Grain | 示例 |
| --- | --- |
| `os` | `Ubuntu` |
| `osrelease` | `22.04` |
| `os_family` | `Debian` |
| `kernel` | `Linux` |
| `cpuarch` | `x86_64` |
| `num_cpus` | `4` |
| `mem_total` | `16086`(MB) |
| `ipv4` | `[10.0.0.10, ...]` |
| `fqdn` | `web01.example.com` |
| `host` | `web01` |
| `domain` | `example.com` |
| `id` | `web01.example.com` |
| `saltversion` | `3006.1` |

### 2. 自定义 Grains

#### 方式 1:`/etc/salt/grains`(Minion 端)

```yaml
# /etc/salt/grains
role: web
env: prod
tier: frontend
cluster: cluster-a
```

#### 方式 2:`_grains` 目录(自定义模块)

```bash
mkdir -p /srv/salt/_grains
```

```python
# /srv/salt/_grains/custom.py
def get_role():
    grains = {}
    try:
        with open('/etc/role') as f:
            grains['role'] = f.read().strip()
    except FileNotFoundError:
        grains['role'] = 'unknown'
    return grains
```

同步到 Minion:

```bash
salt '*' saltutil.sync_grains
salt '*' grains.get role
```

#### 方式 3:Pillar 推到 grains(实时计算)

使用 `ext_pillar` 或自定义 grains 模块从外部系统拿数据。

### 3. 在 State 中使用 Grains

```yaml
# /srv/salt/web/install.sls
{% if grains['os'] == 'Ubuntu' %}
nginx_pkg:
  pkg.installed:
    - name: nginx
{% elif grains['os'] == 'CentOS' %}
nginx_pkg:
  pkg.installed:
    - name: nginx
{% endif %}
```

或更优雅的写法(见 Jinja 章节):

```yaml
nginx_pkg:
  pkg.installed:
    - name: {{ salt['pillar.get']('nginx:pkg_name', 'nginx') }}
```

---

## 八、Pillars(敏感/动态数据)

### 1. Pillar 的作用

- 存放敏感数据(密码、token、证书)
- 存放每个 minion 专属的配置
- 在 SLS 文件中通过 `pillar.get()` 访问

### 2. Pillar 目录结构

```
/srv/pillar/
├── top.sls
├── web/
│   ├── init.sls
│   ├── prod.sls
│   └── stage.sls
└── db/
    ├── init.sls
    └── creds.sls
```

### 3. Pillar 顶层 `top.sls`

```yaml
# /srv/pillar/top.sls
base:
  '*':
    - users
  'web*':
    - match: glob
    - web.init
    - web.config
  'G@env:prod':
    - match: grain
    - common.prod_secrets
  'I@role:db':
    - match: pillar
    - db.creds
```

### 4. Pillar 数据示例

```yaml
# /srv/pillar/users.sls
users:
  alice:
    uid: 1001
    shell: /bin/bash
    groups: [sudo, docker]
  bob:
    uid: 1002
    groups: [developers]

# /srv/pillar/web/init.sls
nginx:
  listen_port: 80
  workers: 4
  vhosts:
    - domain: example.com
      root: /var/www/example
    - domain: api.example.com
      root: /var/www/api

# /srv/pillar/web/config.sls
db_password: {{ pillar['secrets']['db_password'] }}

# /srv/pillar/db/creds.sls
mysql:
  root_password: 's3cr3tP@ssw0rd!'
  repl_user: repl
  repl_password: 'r3plP@ss'
```

### 5. 刷新 Pillar

```bash
# 刷新所有
salt '*' saltutil.refresh_pillar

# 看 pillar 数据
salt '*' pillar.items
salt '*' pillar.get nginx:listen_port
```

### 6. GPG 加密 Pillar

```bash
# 生成 GPG 密钥对
mkdir -p /etc/salt/gpgkeys
chmod 0700 /etc/salt/gpgkeys
gpg --gen-key

# 配置 master
gpg_keydir: /etc/salt/gpgkeys

# 加密 Pillar
gpg --armor --batch --trust-model always \
    --recipient 'saltmaster@example.com' \
    --output secrets.sls \
    --encrypt secrets.yml
```

---

## 九、States(SLS 声明式状态)

### 1. State 文件结构

Salt States 由 **SLS 文件**(SaLt State)组成,本质是 YAML + Jinja。

```
/srv/salt/
├── top.sls                # 入口
├── _modules/              # 自定义执行模块
├── _states/               # 自定义 state 模块
├── _grains/               # 自定义 grains
├── web/
│   ├── init.sls           # 入口(目录同名)
│   ├── nginx.sls
│   └── config.sls
└── db/
    └── init.sls
```

### 2. 顶层 `top.sls`

```yaml
# /srv/salt/top.sls
base:
  '*':
    - common.init
    - users.init
  'web*':
    - match: glob
    - web.nginx
    - web.config
  'G@role:db':
    - match: grain
    - mysql.server
```

### 3. State 文件核心元素

每个 State 由 **State ID**(全局唯一) + **State Module**(点分函数) + **属性 + 状态声明** 组成。

```yaml
# /srv/salt/common/init.sls
# 这是一个简单示例:安装并启动 nginx

nginx:
  pkg.installed: []      # 安装包
  service.running:       # 启动服务
    - name: nginx
    - enable: True
    - watch:             # watch 的文件变化触发 reload
      - file: /etc/nginx/nginx.conf

/etc/nginx/nginx.conf:
  file.managed:
    - source: salt://common/files/nginx.conf
    - user: root
    - group: root
    - mode: 0644
    - require:
      - pkg: nginx
```

### 4. 状态 ID 与声明方式

#### 隐式 ID

```yaml
nginx:                       # ID 与 module.name 一致
  pkg.installed: []          # 直接用 module.name 当声明
```

#### 显式 ID

```yaml
my_nginx_pkg:                # 自定义 ID
  pkg.installed:
    - name: nginx            # 显式指定资源
```

### 5. 状态声明属性

每个 state 函数都接受特定参数,常用通用属性:

| 属性 | 含义 |
| --- | --- |
| `name` | 要管理的资源(目录、文件、服务名) |
| `state` | 同级 priority 的多个 state 中优先级 |
| `enforce_stateful` | 强制覆盖 |
| `require` | 依赖:当前 state 在某个 state 成功后执行 |
| `watch` | 监听:依赖变更时执行(用于 reload) |
| `unless` / `onlyif` | 条件执行 |
| `order` | 声明顺序 |
| `parallel` | 并行执行 |

### 6. 常用 State 模块

#### pkg(包管理)

```yaml
nginx:
  pkg.installed:
    - name: nginx
    - version: 1.18.0
    - fromrepo: nginx-stable
    - allow_updates: True

redis_pkg:
  pkg.removed: []

all_pkgs:
  pkg.latest:
    - pkgs:
      - vim
      - git
      - htop
```

#### file(文件操作)

```yaml
# 1. 文件管理(从 salt:// 源复制)
/etc/nginx/nginx.conf:
  file.managed:
    - source: salt://nginx/files/nginx.conf
    - user: root
    - group: root
    - mode: 0644
    - template: jinja       # 用 jinja 渲染
    - defaults:             # 传给模板的变量
      workers: 4
    - require:
      - pkg: nginx

# 2. 直接写文件
/etc/motd:
  file.managed:
    - contents: |
        Welcome to {{ grains['fqdn'] }}
        Role: {{ grains['role'] }}

# 3. 目录
/srv/app:
  file.directory:
    - user: app
    - group: app
    - mode: 0755
    - makedirs: True
    - clean: True           # 删掉不属于 salt 管理的文件

# 4. 软链接
/etc/nginx/sites-enabled/default:
  file.symlink:
    - target: /etc/nginx/sites-available/default

# 5. 脚本
/usr/local/bin/deploy.sh:
  file.managed:
    - source: salt://scripts/deploy.sh
    - mode: 0755

# 6. 追加内容(不会重置)
extra_conf:
  file.append:
    - name: /etc/hosts
    - text: "10.0.0.10 salt-master"
```

#### service

```yaml
nginx:
  service.running:
    - name: nginx
    - enable: True
    - watch:
      - file: /etc/nginx/nginx.conf
    - require:
      - pkg: nginx

# mask 一个服务
cron:
  service.masked: []
```

#### user / group

```yaml
alice:
  user.present:
    - fullname: Alice Wang
    - uid: 1001
    - gid: 1001
    - home: /home/alice
    - shell: /bin/bash
    - groups:
      - sudo
      - docker
    - password: '$6$...'        # openssl passwd 生成的 hash
    - enforce_password: False   # 已存在用户不强制覆盖密码
    - require:
      - group: alice

alice_group:
  group.present:
    - name: alice
    - gid: 1001
```

#### cron

```yaml
backup_cron:
  cron.present:
    - name: /usr/local/bin/backup.sh
    - user: root
    - minute: 0
    - hour: 2
    - daymonth: '*'
    - month: '*'
    - dayweek: '*'
    - identifier: nightly-backup

old_cron:
  cron.absent:
    - name: /tmp/cleanup.sh
    - identifier: old-cleanup
```

#### sysctl

```yaml
ip_forward:
  sysctl.present:
    - name: net.ipv4.ip_forward
    - value: 1
    - config: /etc/sysctl.d/99-salt.conf
```

#### archive

```yaml
# 解压 tar.gz
extract_app:
  archive.extracted:
    - name: /opt/app
    - source: salt://files/app-1.0.0.tar.gz
    - if_missing: /opt/app/bin/app
    - archive_format: tar
    - options: --strip-components=1

# 解压 zip
extract_data:
  archive.extracted:
    - name: /var/data
    - source: https://example.com/data.zip
    - source_hash: https://example.com/data.zip.sha256
    - archive_format: zip
```

---

## 十、声明顺序与依赖

### 1. `require`(强依赖)

被依赖项成功才执行。

```yaml
deploy_app:
  file.recurse:
    - name: /opt/myapp
    - source: salt://myapp/files
    - require:
      - pkg: myapp_pkg

start_app:
  cmd.run:
    - name: systemctl start myapp
    - require:
      - file: deploy_app
```

### 2. `watch`(变化触发)

被 watch 的资源变化时,触发 reload(类似 Ansible 的 handlers)。

```yaml
nginx:
  service.running:
    - watch:
      - file: /etc/nginx/nginx.conf
      - pkg: nginx           # nginx 升级时也 reload

/etc/nginx/nginx.conf:
  file.managed:
    - source: salt://nginx/files/nginx.conf
    - require:
      - pkg: nginx
```

### 3. `require_in` / `watch_in`(反向声明)

```yaml
/etc/nginx/sites-enabled/default.conf:
  file.symlink:
    - target: /etc/nginx/sites-available/default

# 在另一个地方反向声明
nginx_service:
  service.running:
    - name: nginx
    - watch_in:
      - file: /etc/nginx/sites-enabled/default.conf
```

### 4. 顺序控制 `order`

默认按声明顺序执行,可用 `order` 显式指定:

```yaml
first_task:
  cmd.run:
    - name: echo "first"
    - order: 1

second_task:
  cmd.run:
    - name: echo "second"
    - order: 2
```

### 5. 条件执行 `onlyif` / `unless`

```yaml
update_db:
  cmd.run:
    - name: /opt/myapp/migrate.sh
    - onlyif:
      - test -f /opt/myapp/NEED_MIGRATE

restart_only_if_changed:
  cmd.run:
    - name: systemctl restart myapp
    - unless:
      - pgrep -f myapp
```

---

## 十一、Jinja 模板

Salt 的 SLS 默认用 YAML + Jinja 渲染。

### 1. 基础变量

```yaml
# /srv/salt/web/init.sls
{% set workers = pillar.get('nginx:workers', 4) %}
{% set port = salt['pillar.get']('nginx:listen_port', 80) %}

nginx:
  pkg.installed:
    - name: nginx
  service.running:
    - name: nginx
    - watch:
      - file: /etc/nginx/nginx.conf

/etc/nginx/nginx.conf:
  file.managed:
    - source: salt://web/files/nginx.conf.j2
    - template: jinja
    - context:
      workers: {{ workers }}
      port: {{ port }}
      server_name: {{ grains['fqdn'] }}
    - defaults:
      enable_https: True
```

### 2. 模板文件 `nginx.conf.j2`

```nginx
# /srv/salt/web/files/nginx.conf.j2
user www-data;
worker_processes {{ workers }};

events {
    worker_connections 1024;
}

http {
    server {
        listen {{ port }};
        server_name {{ server_name }};

        {% if enable_https %}
        listen 443 ssl http2;
        ssl_certificate /etc/ssl/certs/{{ server_name }}.pem;
        {% endif %}

        location / {
            root /var/www/html;
        }
    }
}
```

### 3. 条件分支

```jinja
{% if grains['os'] == 'Ubuntu' %}
pkg_name: nginx
{% elif grains['os_family'] == 'RedHat' %}
pkg_name: nginx
{% else %}
pkg_name: nginx-full
{% endif %}
```

### 4. 循环

```jinja
# 遍历 pillar 中的 vhosts
{% for vhost in pillar.get('nginx:vhosts', []) %}
server {
    listen 80;
    server_name {{ vhost.domain }};
    root {{ vhost.root }};
}
{% endfor %}
```

```yaml
# 遍历生成多个 state
{% for user, attrs in pillar.get('users', {}).items() %}
{{ user }}_user:
  user.present:
    - name: {{ user }}
    - uid: {{ attrs.uid }}
    - groups: {{ attrs.groups }}
{% endfor %}
```

### 5. 过滤器

```jinja
{# 字符串转大写 #}
{{ pillar['region'] | upper }}

{# 列表 join #}
{{ groups | join(',') }}

{# 字典取值 #}
{{ pillar['db'] | json }}

{# 字符串替换 #}
{{ 'hello world' | replace('world', 'salt') }}

{# 默认值 #}
{{ var | default('default_value') }}
```

### 6. 宏(Macro)

```jinja
{% macro user_block(name, uid, groups=[]) %}
{{ name }}_user:
  user.present:
    - name: {{ name }}
    - uid: {{ uid }}
    - groups: {{ groups }}
{{ name }}_ssh_dir:
  file.directory:
    - name: /home/{{ name }}/.ssh
    - mode: 0700
    - require:
      - user: {{ name }}_user
{% endmacro %}

{{ user_block('alice', 1001, ['sudo']) }}
{{ user_block('bob', 1002, ['docker']) }}
```

---

## 十二、include / extend / exclude

### 1. include(包含其他 SLS)

```yaml
# /srv/salt/web/init.sls
include:
  - common.users
  - common.timezone
  - web.nginx
  - web.firewall
```

### 2. extend(扩展已有 state)

```yaml
# /srv/salt/web/prod.sls
extend:
  nginx:
    service.running:
      - watch_in:
        - file: /etc/nginx/sites-enabled/prod.conf

  /etc/nginx/sites-enabled/prod.conf:
    file.managed:
      - source: salt://web/files/prod.conf
```

### 3. exclude(排除某个 state)

```yaml
exclude:
  - common.unwanted
```

### 4. `requisite` 引用外部 state

```yaml
deploy_app:
  cmd.run:
    - name: /opt/myapp/deploy.sh
    - require:
      - sls: common.base       # 等待另一个 SLS 完成
      - id: nginx               # 等待另一个 state ID
        - sls: web.nginx        # 限定在哪个 SLS
```

---

## 十三、实战场景示例

### 场景 1:初始化一台 Web 服务器

#### top.sls

```yaml
base:
  '*':
    - common.init
  'web*':
    - match: glob
    - web.nginx
    - web.app
```

#### common/init.sls(系统初始化)

```yaml
# 时区
timezone:
  timezone.system:
    - name: Asia/Shanghai

# 基础包
common_packages:
  pkg.installed:
    - pkgs:
      - vim
      - curl
      - git
      - htop
      - net-tools
      - chrony

# 时间同步
chrony:
  pkg.installed: []
  service.running:
    - enable: True
    - watch:
      - pkg: chrony

# 内核参数
ip_forward:
  sysctl.present:
    - name: net.ipv4.ip_forward
    - value: 1

vm.swappiness:
  sysctl.present:
    - name: vm.swappiness
    - value: 10

# 关闭无用服务
postfix:
  service.dead:
    - enable: False
```

#### web/nginx.sls

```yaml
{% set port = pillar.get('nginx:listen_port', 80) %}
{% set workers = pillar.get('nginx:workers', grains['num_cpus'] * 2) %}

nginx:
  pkg.installed: []
  service.running:
    - enable: True
    - watch:
      - file: /etc/nginx/nginx.conf

/etc/nginx/nginx.conf:
  file.managed:
    - source: salt://web/files/nginx.conf.j2
    - template: jinja
    - user: root
    - group: root
    - mode: 0644
    - require:
      - pkg: nginx
    - context:
      workers: {{ workers }}
      port: {{ port }}
      vhosts: {{ pillar.get('nginx:vhosts', []) }}

/var/www/html:
  file.directory:
    - user: www-data
    - group: www-data
    - mode: 0755
    - makedirs: True
    - require:
      - pkg: nginx

# 防火墙
firewall_open_http:
  iptables.append:
    - table: filter
    - chain: INPUT
    - jump: ACCEPT
    - match:
      - protocol: tcp
      - dport: {{ port }}
    - save: True

# 部署应用(来自 pillar 配置)
{% for vhost in pillar.get('nginx:vhosts', []) %}
deploy_{{ vhost.domain }}:
  file.recurse:
    - name: {{ vhost.root }}
    - source: salt://web/files/site
    - clean: False
    - require:
      - file: /var/www/html
{% endfor %}
```

#### web/files/nginx.conf.j2

```nginx
user www-data;
worker_processes {{ workers }};
pid /run/nginx.pid;

events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    server {
        listen {{ port }};
        server_name _;

        root /var/www/html;
        index index.html;

        location / {
            try_files $uri $uri/ =404;
        }
    }

    {% for vhost in vhosts %}
    server {
        listen {{ port }};
        server_name {{ vhost.domain }};
        root {{ vhost.root }};
        access_log /var/log/nginx/{{ vhost.domain }}.access.log;
        error_log /var/log/nginx/{{ vhost.domain }}.error.log;
    }
    {% endfor %}
}
```

应用:

```bash
# 高状态检查(不执行,只看 diff)
salt 'web*' state.apply web.nginx test=True

# 真正执行
salt 'web*' state.apply web.nginx

# 看详细输出
salt 'web*' state.apply web.nginx -l debug
```

### 场景 2:LAMP 部署(MySQL + PHP + Apache)

#### pillar 配置

```yaml
# /srv/pillar/lamp.sls
mysql:
  root_password: 'MyS3cur3P@ss'
  databases:
    - name: wordpress
      user: wp_user
      password: 'WpP@ss123'
    - name: phpmyadmin
      user: pma
      password: 'PmaP@ss'
  version: '8.0'

php:
  version: '8.2'

apache:
  vhosts:
    - domain: example.com
      docroot: /var/www/example
      php: True
```

#### db/init.sls

```yaml
{% set mysql = pillar.get('mysql', {}) %}
{% set pwd = mysql.get('root_password', 'changeme') %}

mysql_packages:
  pkg.installed:
    - pkgs:
      - mysql-server
      - mysql-client

mysql_service:
  service.running:
    - name: mysql
    - enable: True
    - watch:
      - pkg: mysql_packages

# 设置 root 密码
mysql_root_password:
  cmd.run:
    - name: |
        mysql --user=root <<EOF
        ALTER USER 'root'@'localhost' IDENTIFIED BY '{{ pwd }}';
        FLUSH PRIVILEGES;
        EOF
    - unless: mysql --user=root --password={{ pwd }} -e "SELECT 1"

# 创建数据库
{% for db in mysql.get('databases', []) %}
mysql_db_{{ db.name }}:
  mysql_database.present:
    - name: {{ db.name }}
    - require:
      - service: mysql_service

mysql_user_{{ db.user }}:
  mysql_user.present:
    - name: {{ db.user }}
    - host: 'localhost'
    - password: {{ db.password }}
    - require:
      - mysql_database: mysql_db_{{ db.name }}

mysql_grant_{{ db.user }}_{{ db.name }}:
  mysql_grants.present:
    - grant: all privileges
    - database: {{ db.name }}.*
    - user: {{ db.user }}
    - host: 'localhost'
    - require:
      - mysql_user: mysql_user_{{ db.user }}
{% endfor %}
```

### 场景 3:批量用户管理

#### pillar 配置

```yaml
# /srv/pillar/users.sls
users:
  alice:
    uid: 1001
    fullname: 'Alice Wang'
    shell: /bin/bash
    groups: [sudo, docker, devops]
    ssh_keys:
      - 'ssh-rsa AAAAB3NzaC1yc2EAAAADA... alice@laptop'
      - 'ssh-rsa AAAAB3NzaC1yc2EAAAADA... alice@work'
  bob:
    uid: 1002
    fullname: 'Bob Lee'
    shell: /bin/zsh
    groups: [developers]
```

#### users/init.sls

```yaml
{% for name, attrs in pillar.get('users', {}).items() %}

{{ name }}_group:
  group.present:
    - name: {{ name }}
    - gid: {{ attrs.uid }}

{{ name }}_user:
  user.present:
    - name: {{ name }}
    - fullname: {{ attrs.fullname }}
    - uid: {{ attrs.uid }}
    - gid: {{ attrs.uid }}
    - shell: {{ attrs.get('shell', '/bin/bash') }}
    - home: /home/{{ name }}
    - groups: {{ attrs.get('groups', []) }}
    - createhome: True
    - require:
      - group: {{ name }}_group

/home/{{ name }}/.ssh:
  file.directory:
    - user: {{ name }}
    - group: {{ name }}
    - mode: 0700
    - require:
      - user: {{ name }}_user

/home/{{ name }}/.ssh/authorized_keys:
  file.managed:
    - user: {{ name }}
    - group: {{ name }}
    - mode: 0600
    - contents: |
        {% for key in attrs.get('ssh_keys', []) %}
        {{ key }}
        {% endfor %}
    - require:
      - file: /home/{{ name }}/.ssh

# 密码永不过期
{% for grp in attrs.get('groups', []) %}
{{ name }}_group_{{ grp }}:
  group.present:
    - name: {{ grp }}
    - addusers:
      - {{ name }}
    - require:
      - user: {{ name }}_user
{% endfor %}

{% endfor %}

# sudo 配置
/etc/sudoers.d/devops:
  file.managed:
    - source: salt://users/files/devops.sudoers
    - mode: 0440
    - user: root
    - group: root
```

---

## 十四、Salt SSH(无 agent)

```bash
# 启用 rosters(/etc/salt/roster)
salt-ssh '*' test.ping
```

### 配置 roster

```yaml
# /etc/salt/roster
web01:
  host: 192.168.1.10
  user: ubuntu
  port: 22
  sudo: True

web02:
  host: 192.168.1.11
  user: root
  priv: /root/.ssh/id_rsa
```

```bash
# 执行命令
salt-ssh 'web*' cmd.run 'uptime'

# 应用 state
salt-ssh 'web*' state.apply web.nginx

# 用密码(不推荐)
salt-ssh 'web*' test.ping --ask-pass
```

Salt SSH 适合:

- 跨网段、无法安装 agent 的设备
- 一次性操作
- Windows(通过 PowerShell 远程执行)

---

## 十五、Returners(结果存储)

默认 Salt 命令结果只返回到 Master 终端,Returner 可以把结果存到外部系统。

### 1. local_cache(默认,临时)

```yaml
# /etc/salt/minion
return: local_cache
```

### 2. MySQL Returner

```bash
# 建表
mysql < /usr/share/doc/salt-{version}/returners/mysql.sql
```

```yaml
# /etc/salt/minion
mysql.host: '127.0.0.1'
mysql.user: 'salt'
mysql.pass: 'salt'
mysql.db: 'salt'
mysql.port: 3306
```

### 3. Redis Returner

```yaml
# /etc/salt/minion
redis.db: '0'
redis.host: '127.0.0.1'
redis.port: 6379
```

使用:

```bash
# 单命令返回存 Redis
salt '*' cmd.run 'uptime' --return redis

# state apply 存 Redis
salt '*' state.apply --return redis
```

### 4. 自定义 Returner

```python
# /srv/salt/_returners/slack_return.py
import json
import urllib.request

def returner(ret):
    cmd = ret.get('fun')
    jid = ret.get('jid')
    result = ret.get('return', {})
    success = ret.get('success', True)

    text = f"Salt job `{cmd}` (jid={jid}) success={success}"
    payload = json.dumps({"text": text}).encode()

    req = urllib.request.Request(
        'https://hooks.slack.com/services/XXX',
        data=payload,
        headers={'Content-Type': 'application/json'}
    )
    urllib.request.urlopen(req)
```

```bash
salt '*' test.ping --return slack_return
```

---

## 十六、Reactor 系统(事件驱动)

Reactor 在 Master 上监听事件,触发响应,实现自动化运维。

### 1. 监听 Minion 启动事件

```yaml
# /etc/salt/master.d/reactor.conf
reactor:
  - 'salt/minion/*/start':
    - /srv/reactor/minion_start.sls
```

### 2. Reactor SLS(实际是 orch state)

```yaml
# /srv/reactor/minion_start.sls
{% if data['act'] == 'start' and data['id'].startswith('web') %}
log_minion_start:
  local.cmd.run:
    - tgt: salt-master
    - arg:
      - "echo 'Minion {{ data['id'] }} started at $(date)' >> /var/log/salt/minions.log"

# 自动接受新 key(谨慎!)
auto_accept_new_web:
  local.saltutil.refresh_grains:
    - tgt: '{{ data['id'] }}'
{% endif %}
```

### 3. 自定义事件触发

```bash
# 手动发事件
salt 'master' event.send 'myapp/deploy' '{version: "1.2.3"}'
```

```yaml
# reactor 监听
reactor:
  - 'myapp/deploy':
    - /srv/reactor/app_deploy.sls
```

---

## 十七、Orchestration(`salt-run state.orchestrate`)

Orchestrate 用于 **跨 Minion 协调**(先 A 后 B,整体编排)。

### 1. Orchestrate SLS

```yaml
# /srv/salt/orch/web_cluster/init.sls
# salt-run state.orchestrate orch.web_cluster.deploy

deploy_order:
  salt.state:
    - tgt: 'lb*'
    - sls:
      - lb.nginx
    - order: 1

deploy_web:
  salt.state:
    - tgt: 'web*'
    - sls:
      - web.nginx
      - web.app
    - require:
      - salt: deploy_order

deploy_db:
  salt.state:
    - tgt: 'G@role:db'
    - sls:
      - db.mysql
    - require:
      - salt: deploy_order
```

执行:

```bash
salt-run state.orchestrate orch.web_cluster.deploy
```

### 2. 函数式编排

```yaml
# orch/rolling_restart.sls
restart_one_at_a_time:
  salt.function:
    - name: cmd.run
    - tgt: 'web*'
    - tgt_type: glob
    - arg:
      - "systemctl restart myapp"
    - batch: 1                    # 一次只重启 1 台
    - batch_wait: 30               # 间隔 30 秒
```

> `batch` 是 Rolling 部署的核心。

---

## 十八、Beacons(监控事件)

Beacons 让 Minion 监听系统事件并发送给 Master。

```yaml
# /etc/salt/minion
beacons:
  inotify:
    - files:
        /etc/passwd:
          mask:
            - modify
      disable_during_state_run: True
  loadavg:
    - 1.0
    - 5.0
  diskusage:
    - interval: 60
    - percent: 80
  service:
    - services:
        nginx:
          onchangeonly: True
        mysql:
          onchangeonly: True
```

```bash
# 查看 beacons
salt '*' beacons.list
salt '*' beacons.list_available

# 添加 beacon
salt '*' beacons.add diskusage '[{"percent": 80}]'

# 启用
salt '*' beacons.enable inotify
```

---

## 十九、Salt API(REST)

```bash
# 安装 salt-api
yum install -y salt-api

# 启用 cherrypy
# /etc/salt/master.d/api.conf
rest_cherrypy:
  port: 8000
  host: 0.0.0.0
  disable_ssl: True
  webhook_disable_auth: True

external_auth:
  auto:
    saltuser:
      - .*
      - '@runner'
      - '@wheel'
```

```bash
# 获取 token
curl -k http://localhost:8000/login \
  -H 'Accept: application/json' \
  -d username=saltuser \
  -d password=saltpass \
  -d eauth=pam

# 调用
curl -k http://localhost:8000 \
  -H 'Accept: application/x-yaml' \
  -H 'X-Auth-Token: <TOKEN>' \
  -d client=local \
  -d tgt='*' \
  -d fun=test.ping
```

---

## 二十、Salt Cloud(云资源管理)

```bash
# 配置云厂商
mkdir /etc/salt/cloud.providers.d
cat > /etc/salt/cloud.providers.d/aws.conf <<EOF
aws:
  driver: ec2
  id: AKIA...
  key: '...'
  private_key: /etc/salt/aws.pem
  keyname: my-key
  securitygroup: default
  location: us-east-1
  availability_zone: us-east-1a
  minion:
    master: salt.example.com
EOF

# 配置 profile
cat > /etc/salt/cloud.profiles.d/web.conf <<EOF
web_t2_micro:
  provider: aws
  image: ami-0c55b159cbfafe1f0
  size: t2.micro
  ssh_username: ubuntu
EOF

# 创建 5 台
salt-cloud -p web_t2_micro web0{1..5}

# 销毁
salt-cloud -d web01
```

---

## 二十一、高可用与扩展

### 1. 多 Master(Master HA)

每个 Minion 配置多个 Master,Minion 随机连接一个。Master 之间共享 file\_roots、pillar\_roots(用 gitfs + git pillar)。

```yaml
# /etc/salt/minion
master:
  - salt1.example.com
  - salt2.example.com

master_type: failover       # failover / str
```

### 2. Salt Syndic(分层)

```yaml
# Lower Master
syndic_master: salt-top.example.com
syndic_log_file: /var/log/salt/syndic

# Top Master
order_masters: True
```

### 3. 文件后端 gitfs

```yaml
# /etc/salt/master
fileserver_backend:
  - git
  - roots

gitfs_remotes:
  - https://github.com/myorg/salt-states.git:
    - root: salt
    - env: base
```

---

## 二十二、调试与排错

### 1. 查看日志

```bash
tail -f /var/log/salt/master
tail -f /var/log/salt/minion

# 临时提高日志级别
salt '*' -l debug cmd.run 'whoami'
```

### 2. 检查 minion 连接状态

```bash
# 查看 minion 是否在线
salt-run manage.up

# 查看离线 minion
salt-run manage.down

# 列出所有 minion
salt-key -L
```

### 3. 手动重连

```bash
# Minion 重连 master
salt-minion -d && salt-minion
```

### 4. 测试单个 state

```bash
# 单个 state 测试
salt 'web01' state.single pkg.installed name=nginx

# 看 state 树
salt 'web01' state.show_top

# 看具体的 state 文件渲染后内容
salt 'web01' state.show_sls web.nginx
```

### 5. 常见问题

| 现象 | 原因 | 排查 |
| --- | --- | --- |
| Minion 不出现在 Key 列表 | 端口不通 | `nc -zv master 4505 4506` |
| test.ping 一直 False | key 未接受 | `salt-key -L` 然后 `salt-key -A` |
| State 一直显示 changed | Jinja 变量每次都不同 | 检查 grains、pillar 取值 |
| Pillar 数据缺失 | top.sls 拼写错误 | `salt '*' pillar.items` |
| 文件模板渲染失败 | YAML 缩进问题 | 看 master 日志的 YAML 错误 |
| 反应器未触发 | 事件路径不对 | `salt-run state.event_runner` 看事件流 |

---

## 二十三、最佳实践

1. **永远用 top.sls 入口**,不要在命令行指定 SLS。
2. **Pillar 加密**:密码、token、证书必须用 GPG 加密。
3. **Grains 不要存敏感数据**(在 Minion 端,不安全)。
4. **State ID 全局唯一**,不要重复。
5. **合理分层**:common → role → instance 三层 SLS 结构。
6. **使用 gitfs** + Git 仓库管理 State,带版本可回滚。
7. **预编译 SLS**:`salt '*' state.show_highstate` 在生产前先看渲染结果。
8. **开启 Master 端 Grains Cache**,加速高 cardinality 环境。
9. **Rollback 预案**:State 一定要幂等,且能反向(declare `pkg.removed` 等)。
10. **小步快跑**:State 改动先 `test=True`,再正式 apply。

---

## 二十四、参考资料

- [SaltStack 官方文档](https://docs.saltproject.io/en/latest/)
- [Salt States 详解](https://docs.saltproject.io/en/latest/topics/states/)
- [Salt Grains](https://docs.saltproject.io/en/latest/topics/grains/)
- [Salt Pillar](https://docs.saltproject.io/en/latest/topics/pillar/)
- [SaltStack YouTube 教程](https://www.youtube.com/c/SaltStack)
- 《Salt Essentials》 — Craig Sebenik
- [Salt 最佳实践(官方)](https://docs.saltproject.io/en/latest/topics/best_practices.html)