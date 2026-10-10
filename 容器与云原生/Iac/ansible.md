# Ansible 笔记

## 认识

Ansible 是 Red Hat 出的 **自动化运维工具（Agentless / 无代理）**。它通过 SSH（或 WinRM）直接管理远程主机，不在被控端安装任何 agent，本质上是「用 Python 推送到远端执行模块，再拉回结果」。

核心特征：

- **无 Agent**：只需要 SSH + Python，不用在被控端装东西
- **声明式 + Idempotent（幂等）**：同样的 playbook 跑两次，第二次应该是 no-op（changed=0）
- **YAML 为主**：playbook 是 YAML，逻辑用 Jinja2 模板写
- **Push 模型**：控制机主动推，公网可达的机器不需要额外网络设计
- **模块化**：一个 task = 一次「模块调用」，模块是 Ansible 的最小执行单位
- **Agentless 但仍依赖少量条件**：远端要有 Python，Windows 要 WinRM

与同类工具对比：

| 工具 | 模型 | 语言 | 幂等 | 状态 | 适用 |
|---|---|---|---|---|---|
| Ansible | Push（无 agent） | YAML + Jinja2 | 是 | 无 | 配置管理、应用部署 |
| SaltStack | Push/Agent 双模 | YAML + Jinja2 | 是 | 有状态（State 文件） | 大规模、实时（Reactor） |
| Puppet | Pull（agent） | DSL（Puppet） | 是 | 有（Catalog 编译） | 长期状态收敛 |
| Chef | Pull（agent） | Ruby DSL | 是 | 有（Node 对象） | 开发团队 |
| Terraform | 客户端 | HCL | 是 | 有（state 文件） | 资源编排（创建 VM/S3） |
| Kubernetes | 声明式 API | YAML | 是 | 有（etcd） | 容器编排 |

一句话区分：**Terraform 管「资源从无到有」，Ansible 管「已有机器怎么配」。** 常见组合是 Terraform 开机器 → Ansible 装机。

---

## 目录结构

标准推荐布局（`ansible-galaxy init` 生成的骨架）：

```text
.
├── ansible.cfg                 # 全局配置（最优先）
├── inventory/
│   ├── hosts.yml               # 主机清单
│   └── group_vars/
│       ├── all.yml             # 所有主机公用变量
│       └── webservers.yml      # webservers 组变量
├── host_vars/
│   └── web1.yml                # 单主机变量
├── roles/
│   └── nginx/
│       ├── defaults/main.yml   # 角色默认变量（可被覆盖）
│       ├── vars/main.yml       # 角色内部变量（优先级高，不建议被覆盖）
│       ├── tasks/main.yml       # 角色任务入口
│       ├── handlers/main.yml   # 角色 handler
│       ├── templates/          # Jinja2 模板（.j2）
│       ├── files/              # 直接复制的文件
│       ├── meta/main.yml       # 角色依赖
│       └── README.md
├── playbooks/
│   └── site.yml                # 主 playbook
└── filter_plugins/             # 自定义过滤器（可选）
```

**加载顺序（优先级从低到高）**：

```
命令行 -e  >  play vars / vars_files  >  block vars
        >  include_vars  >  role defaults  >  inventory group_vars/all  >  host_vars
        >  实际 inventory 变量  >  role vars  >  set_fact / 注册变量
```

---

## 基础命令

```bash
ansible --version                    # 版本 + 使用的 Python 解释器路径（排错关键）
ansible all -m ping                  # 连通性测试（底层 ping 模块）
ansible all -m "shell uptime"        # 执行任意 shell（不幂等，谨慎用）

# 只在部分主机执行
ansible webservers -m ping
ansible 'web[1:3]' -m ping           # 主机组切片

# ad-hoc 常用参数
ansible all -i hosts.yml, -m user -a "name=deployer shell=/bin/bash groups=wheel"
ansible all -b                       # 提权（become），等价 --become
ansible all -m shell -a "uptime" -b  # 提权执行
ansible all -m file -a "path=/tmp/x state=touch"   # 幂等模块
```

`ansible` 命令格式：

```text
ansible <主机模式> -m <模块> [-a "<模块参数>"] [选项]
```

---

## Inventory 主机清单

Inventory 决定「管理谁」。主机模式（host pattern）的匹配优先级：

1. 并集 `web1,web2`
2. 排除 `webservers:!web2`
3. 交集 `webservers:&prod`

### INI 格式（默认）

```ini
# /etc/ansible/hosts 或 ./hosts
[webservers]
web1.example.com
web2.example.com

[db]
# 行内主机变量（简写，变量多时很难维护，优先用 YAML）
db1.example.com ansible_port=2222 ansible_user=admin

[prod:children]           # 嵌套子组
webservers
db

[prod:vars]               # 组变量
ntp_server=ntp.aliyun.com
env=production

[unreachable:vars]        # 特殊组：默认排除
ansible_connection=paramiko
```

### YAML 格式（推荐）

```yaml
# inventory/hosts.yml
all:
  children:
    prod:                       # 一个逻辑分组
      hosts:
        web1.example.com:
        web2.example.com:
      vars:
        env: production
        ansible_user: deployer
    webservers:
      hosts:
        web1:
          ansible_host: 10.0.0.11
          http_port: 80
        web2:
          ansible_host: 10.0.0.12
          http_port: 8080
      vars:
        nginx_port: 80
    db:
      hosts:
        db1.example.com:
      vars:
        db_engine: postgresql

    # 特殊组：所有 host 都隐式属于
    ungrouped: {}
    # 特殊组：需要密码的才加入
    vault_secrets: {}
```

### 动态 Inventory

云上机器数量会变，不能写死在静态文件里。动态清单就是一个返回 JSON 的脚本/YAML：

```bash
# 阿里云 ECS 动态 inventory 示例（简化）
./aliyun_inventory.py --list
# 返回格式：
# {
#   "_meta": {"hostvars": {"i-xxx": {"ansible_host": "1.2.3.4"}}},
#   "webservers": {"hosts": ["i-xxx"]}
# }
ansible all -i ./aliyun_inventory.py -m ping
```

AWS 用 `amazon.aws.aws_ec2_inventory`，K8s 用 `community.kubernetes.k8s_inventory`，写好后存进 `/etc/ansible/ansible.cfg` 的 `inventory` 项即可全局生效。

---

## ansible.cfg 常用配置

```ini
[defaults]
inventory      = ./inventory/hosts.yml
roles_path     = ./roles
host_key_checking = False          # 首次连接自动接受 host key（生产慎用）
retry_files_enabled = False
stdout_callback = yaml
forks = 20                        # 并发主机数
timeout = 30
log_path = ./ansible.log

[ssh_connection]
pipelining = True                 # 显著提升性能（牺牲可读性）
ssh_args = -o ControlMaster=auto -o ControlPersist=600s   # 复用 SSH 连接，多主机时提速明显

[ssh_connection::ssh_binary]
ssh_binary = ssh
```

优先级：环境变量 `ANSIBLE_CONFIG` > 当前目录 `ansible.cfg` > `~/.ansible.cfg` > `/etc/ansible/ansible.cfg`。

---

## Ad-hoc 命令与模块

```bash
# 文件类
ansible all -m file -a "path=/data state=directory mode=0755 owner=deployer group=deployer"
ansible all -m copy -a "src=./nginx.conf dest=/etc/nginx/nginx.conf mode=0644"
ansible all -m copy -a "content='hello' dest=/etc/hi.txt"
ansible all -m fetch -a "src=/etc/passwd dest=./backup/" flat=no   # 从远端拉回
ansible all -m template -a "src=nginx.conf.j2 dest=/etc/nginx/nginx.conf"
ansible all -m synchronize -a "src=./dist/ dest=/usr/share/app/"  # rsync

# 用户组
ansible all -m user -a "name=deployer groups=wheel,dev append=yes shell=/bin/bash"
ansible all -m group -a "name=dev gid=2000 state=present"

# 包与服务（跨发行版统一）
ansible all -m package -a "name=nginx state=present"
ansible all -m dnf  -a "name=nginx state=latest"
ansible all -m apt  -a "name=nginx state=latest update_cache=yes"
ansible all -m service -a "name=nginx state=started enabled=yes"
ansible all -m systemd -a "name=nginx state=reloaded daemon_reload=yes"

# 事实查询（这些是「只读的 setup 模块」的封装）
ansible web1 -m setup -a "filter=ansible_distribution*"
ansible web1 -m setup -a "filter=ansible_memory_mb"
ansible localhost -m debug -a "var=ansible_distribution_major_version"

# 归档
ansible all -m unarchive -a "src=app.tar.gz dest=/opt/remote=yes"
```

---

## Playbook 结构

Playbook = **plays**（对一组主机的编排）+ **tasks**（具体动作）+ **modules**（执行单位）。

```yaml
# playbooks/site.yml
- name: 配置 web 服务器组         # play 名称（可选，但强烈建议写）
  hosts: webservers              # 目标主机模式
  become: yes                    # 全 play 提权
  gather_facts: yes              # 默认就是 yes，play 开始前采集 setup 信息
  serial: 2                      # 每次只跑 2 台（滚动更新必用）
  max_fail_percentage: 20        # 失败超过 20% 就中止，0 表示任意一台失败即停
  any_errors_fatal: true         # 任一主机出错 → 整个 play 终止
  pre_tasks:                     # play 正式开始前（通常用来关防火墙、加主机）
    - name: 关闭 firewalld
      ansible.builtin.service:
        name: firewalld
        state: stopped
  roles:
    - nginx                      # 角色列表（等价于 import_role）
  tasks:
    - name: 确保 nginx 已安装
      ansible.builtin.package:
        name: nginx
        state: present
      notify: 重载 nginx          # 变化时触发 handler

    - name: 写入默认站点配置
      ansible.builtin.template:
        src: site.conf.j2
        dest: /etc/nginx/conf.d/default.conf
      notify: 重载 nginx

    - name: 分发证书（需要提权，用 become 局部提权）
      ansible.builtin.copy:
        src: "{{ cert_dir }}/{{ item }}.crt"
        dest: "/etc/pki/nginx/{{ item }}.crt"
        mode: "0644"
      loop: "{{ domains }}"
      become: yes

  post_tasks: []                  # play 结束后执行
```

### 常用 play 级关键字

| 关键字 | 说明 |
|---|---|
| `hosts` | 主机模式，`all` / 组名 / `'web*'` |
| `become` | 是否提权（yes/no/user） |
| `gather_facts` | 是否采集主机事实 |
| `serial` | 分批执行数量，`"30%"` 也可以 |
| `strategy` | `linear`（默认，一台失败停全部）/ `free`（各跑各的） |
| `max_fail_percentage` | 允许的失败百分比 |
| `any_errors_fatal` | 致命错误 |
| `when` | 条件 |
| `tags` | 标签，配合 `--tags` 使用 |
| `ignore_errors` | `yes` 忽略失败（慎用，会让后续步骤在错误状态上继续） |

### playbook 特殊变量

```yaml
- hosts: webservers
  gather_facts: no
  vars:
    special:
      hostvars: "{{ hostvars[inventory_hostname] }}"    # 访问其他主机变量
      groups:    "{{ groups['prod'] }}"                 # 访问某个组的主机列表
      play_hosts: "{{ play_hosts }}"                    # 本 play 展开的主机列表
      ansible_play_hosts_all: ...
```

---

## 变量（Variables）

### 定义变量

```yaml
# 1. play 内联
- hosts: all
  vars:
    app_port: 8080

# 2. vars_files 引入
    files:
      - vars/common.yml

# 3. 外部注入（最高优先级）
#    ansible-playbook site.yml -e "@extra.json"
#    ansible-playbook site.yml -e app_port=9090

# 4. 角色 defaults/main.yml（最易被覆盖的地方）
# 5. group_vars / host_vars
```

### 变量引用与运算

```yaml
nginx_port: 80
site_url: "http://{{ inventory_hostname }}:{{ nginx_port }}"

tasks:
  - name: 拼接
    debug: msg="{{ 'nginx port is ' ~ nginx_port }}"

  - name: 列表拼接
    debug: msg="{{ ['a','b'] + ['c'] }}"

  - name: 条件表达式
    debug: msg="{{ 'high' if nginx_port > 1024 else 'low' }}"

  - name: 取默认值（推荐，比 `default` filter 更快）
    debug: msg="{{ log_level | default('info', true) }}"
    # true = 把空字符串也当未定义

  - name: 变量存在才执行
    debug: msg="{{ secret_key }}"
    when: secret_key is defined

  - name: 组合多个条件
    debug: msg="ok"
    when:
      - ansible_os_family == "RedHat"
      - nginx_port == 80
```

### 敏感变量：Vault

```bash
ansible-vault create vault.yml            # 创建加密文件
ansible-vault edit vault.yml
ansible-vault encrypt --output prod.yml plain.yml
ansible-vault decrypt --output - vault.yml | head

ansible-playbook site.yml --ask-vault-pass               # 交互输入密码
ansible-playbook site.yml --vault-password-file ~/.vault_pass
ANSIBLE_VAULT_PASSWORD_FILE=~/.vault_pass ansible-playbook site.yml   # CI 里用
```

`group_vars/all/vault.yml` 里的变量会以 `vault_` 前缀还原：

```yaml
# group_vars/all/vault.yml
vault_db_password: "s3cret"
# 使用时
- debug: msg="{{ vault_db_password }}"
```

### 注册变量与 set_fact

```yaml
- name: 采集磁盘信息
  ansible.builtin.command: df -h /data
  register: disk_result
  changed_when: false          # 只读命令要显式声明，否则每次都显示 changed

- name: 使用结果
  debug:
    msg: "磁盘使用率: {{ disk_result.stdout_lines[1].split()[4] }}"

- name: 持久化变量（set_fact 比 register 范围大，可跨 play 使用）
  ansible.builtin.set_fact:
    app_env: "production"
    app_path: "/opt/{{ app_name }}"
```

`register` 的结果结构：

```yaml
{
  changed: true,
  failed: false,
  rc: 0,
  stdout: "...",
  stdout_lines: [...],
  stderr: "",
  cmd: "df -h /data"
}
```

---

## 常用模块详解

### 文件与内容

```yaml
# template：支持 Jinja2，模板变了才改文件（靠 checksum 幂等）
- ansible.builtin.template:
    src: nginx.conf.j2
    dest: /etc/nginx/nginx.conf
    owner: root
    group: root
    mode: "0644"          # 必须是字符串！0644 会被解析成八进制 420
    backup: yes            # 覆盖前备份成 xxx.conf.NNNN

# copy：content 直接写内容
- ansible.builtin.copy:
    content: |
      # managed by ansible
      PORT={{ app_port }}
    dest: /etc/app.conf

# lineinfile / blockinfile / replace：精确改一行/一段，不动其他内容
- ansible.builtin.lineinfile:
    path: /etc/fstab
    line: "/dev/sdb1 /data xfs defaults,nofail 0 2"
    regexp: "^/dev/sdb1"      # 先匹配再替换，实现幂等
    state: present

- ansible.builtin.blockinfile:
    path: /etc/nginx/nginx.conf
    marker: "# {mark} ANSIBLE MANAGED BLOCK"
    block: |
      location /api { proxy_pass http://backend; }
    create: yes

- ansible.builtin.replace:
    path: /etc/hosts
    regexp: 'localhost\s+'
    replace: '127.0.0.1 localhost '

# stat / find：先查后动，常配合 when
- ansible.builtin.stat:
    path: /etc/secret
  register: secret_stat
- debug: msg="exists={{ secret_stat.stat.exists }}"
```

### 命令类

```yaml
# command：不经过 shell，不支持管道/通配符/变量展开（更安全）
- ansible.builtin.command: /usr/bin/git rev-parse HEAD
  register: git_head
  changed_when: "'HEAD' in git_head.stdout"    # 关键：声明何时算 changed

# shell：经过 shell，支持 | > $VAR glob —— 有注入风险，别拼接外部输入
- ansible.builtin.shell: "systemctl is-active {{ service_name }} | grep -q active"

- ansible.builtin.script: ./deploy.sh
  args: { executable: /bin/bash }

# script 模块：把脚本推到远端 /tmp 执行后删除，适合一次性复杂逻辑
# 更好的做法：把逻辑写成 role + template，别用 script
```

### 系统与软件

```yaml
- ansible.builtin.package: { name: "{{ item }}", state: present }   # 自动选 apt/dnf/yum
  loop: [git, curl, vim]

- ansible.builtin.systemd:
    name: nginx
    state: restarted
    enabled: yes
    daemon_reload: yes

- ansible.builtin.cron:
    name: "日志轮转检查"
    minute: "0 3 * * *"
    job: "/usr/local/bin/logrotate-check"
    user: root

- ansible.builtin.reboot:
    msg: "内核更新后重启"
    reboot_timeout: 600
    # 注意：reboot 之后同一 host 后续任务不会执行，需配合 meta: reset_connection
  post_tasks:
    - meta: reset_connection
```

### 调试类

```yaml
- ansible.builtin.debug:
    msg: "{{ some_var }}"
    verbosity: 2            # -v 才显示

- ansible.builtin.set_stats:              # 在长 play 中打印进度
    data:
        progress: "已完成 {{ 50 + 10 }}%"

- debug: var=hostvars[inventory_hostname]     # 打印整台主机的变量
```

---

## Handlers（处理器）

Handler 是被 `notify` 触发后**在 play 末尾统一执行一次**的任务，不是立刻执行 —— 这样一批 task 改完配置只重启一次服务。

```yaml
- name: 部署 nginx
  hosts: webservers
  become: yes
  handlers:
    - name: 重载 nginx        # 名字必须与 notify 里的字符串一致
      ansible.builtin.service:
        name: nginx
        state: reloaded
    - name: 重载 systemd
      ansible.builtin.systemd: { daemon_reload: yes }

  tasks:
    - name: 装包
      ansible.builtin.package: { name: nginx, state: present }
      notify: 重载 nginx        # ← 只是「挂起」，play 结束才执行

    - name: 改配置
      ansible.builtin.template:
        src: nginx.conf.j2
        dest: /etc/nginx/nginx.conf
      notify:
        - 重载 nginx
        - 重载 systemd          # 可以通知多个
```

### 立即执行

需要立刻生效时用 `listen` 或 `meta: flush_handlers`：

```yaml
# 方式一：listen（一个逻辑名触发多个 handler）
handlers:
  - name: 重载 nginx
    listen: 重载服务
    service: { name: nginx, state: reloaded }

tasks:
  - template: { src: a.conf.j2, dest: /etc/a.conf }
    notify: 重载服务           # 触发上面所有 listen: 重载服务 的 handler

# 方式二：中途强制执行（模板 + 语法校验场景必须用）
tasks:
  - name: 校验配置语法
    command: nginx -t
    changed_when: false
  - meta: flush_handlers      # 立刻执行已挂起的 handler

# 方式三：忽略执行顺序
tasks:
  - meta: flush_handlers
    listen: 立即处理
```

**注意**：handler 定义在 play 的 `handlers:` 段，role 里 handler 由 role 自动加载。

---

## 循环与条件

### 循环

```yaml
# 简洁写法
- ansible.builtin.debug: msg="{{ item }}"
  loop: [a, b, c]

- ansible.builtin.debug: msg="{{ item.key }} -> {{ item.value }}"
  loop: "{{ dict.items() }}"

- ansible.builtin.file: { path: "/data/{{ item }}", state: directory }
  loop: [logs, cache, uploads]

# 带索引和计数（loop_control）
- ansible.builtin.debug: msg="{{ idx }}: {{ item }}"
  loop: "{{ range(5) }}"
  loop_control:
    index_var: idx
    label: "{{ idx }}"        # 减少输出噪音
    loop_var: cur
    extended: true            # 循环内定义变量

# 复杂结构：循环字典列表（嵌套变量写法最常用）
- ansible.builtin.user:
    name: "{{ item.name }}"
    groups: "{{ item.groups }}"
    shell: "{{ item.shell | default('/bin/bash') }}"
  loop:
    - { name: alice, groups: 'wheel,dev' }
    - { name: bob,   groups: 'dev' }

# 循环 register + 汇总结果
- ansible.builtin.command: "echo {{ item }}"
  loop: "{{ hosts }}"
  register: out
- ansible.builtin.debug:
    msg: "{{ out.results | map(attribute='stdout_lines') | flatten }}"

# 并行执行（默认 5 线程）
- ansible.builtin.debug: msg="{{ item }}"
  loop: "{{ range(100) }}"
  loop_control:
    parallel: 10
```

### 条件

```yaml
# 常用测试
when:
  - ansible_os_family == "Debian"        # 等值
  - ansible_distribution_version is version('20.04', '>=')   # 版本比较
  - not container_stat.stat.exists       # 取反
  - port in [80, 443]                    # 成员判断
  - "'amd64' in ansible_architecture"    # 子串
  - key in my_dict                       # 字典键存在

# 常用 filter
when:
  - result is succeeded
  - result is failed
  - result is changed
  - result is skipped
  - var is defined / is undefined
  - var | default('') | length > 0        # 链式
  - path | is directory
  - var | bool
  - nproc | int > 4
```

### 条件与循环组合的坑

```yaml
# 坑：loop 里的 when 是「对每个 item 求值」，不是跳过整个 task
- name: 只装某些包
  package: { name: "{{ item }}", state: present }
  loop: "{{ packages }}"
  when: item in allowed_packages      # 正确写法

# 错：会每个 item 都跳过
  when: false

# 需要整段跳过用 block + when
- block:
    - package: { name: git }
  when: ansible_os_family == "Debian"
```

---

## Jinja2 模板

### 基础语法

```jinja
{{ variable }}                   {# 输出，注释是 {# #} #}
{% if cond %} ... {% else %} ... {% endif %}
{% for i in list %} ... {% endfor %}      {% set %}, {% include %}, {% import %}
{{ a | upper }}  {{ a | default('x') }}  {{ a | length }}  {{ a | join(', ') }}
{{ a | int }}  {{ a | string }}  {{ a | trim }}  {{ a | b64encode }}
{{ a | to_json }}  {{ a | from_json }}  {{ a | to_nice_json(indent=2) }}
{{ a | regex_replace('a', 'b') }}  {{ a | hash('sha256') }}  {{ pwd | password_hash('sha256') }}
{{ ts | to_datetime('%Y%m%d') }}   {{ ts | date('%Y-%m-%d') }}   {{ 0 | random(1,100) }}
{{ list | sort }}  {{ list | unique }}  {{ list | max }}  {{ list | sum }}
{{ groups['web'] | length }}  {{ ansible_play_hosts }}
{{ 'yes' | bool }}   {# 字符串转布尔，注意 "false" 字符串也是 True，要用 | bool #}
```

> ⚠️ 常见坑：`when: var == 'False'` 在 YAML 里会被解析成布尔 `False`。要写 `when: var|string == 'False'` 或加引号 `'False'`。

### 模板示例：nginx.conf.j2

```jinja
# {{ ansible_managed }}
upstream backend {
{% for server in groups['webservers'] %}
    server {{ hostvars[server].ansible_host }}:{{ hostvars[server].http_port | default(80) }}
        max_fails=3 fail_timeout=10s;
{% endfor %}
    keepalive 32;
}

server {
    listen       {{ nginx_port }};
    server_name  {{ server_name }};
{% if enable_https %}
    listen       443 ssl;
    ssl_certificate     /etc/nginx/certs/{{ server_name }}.crt;
    ssl_certificate_key /etc/nginx/certs/{{ server_name }}.key;
    ssl_protocols       TLSv1.2 TLSv1.3;
{% endif %}

    access_log  /var/log/nginx/{{ server_name }}.access.log  {{ log_format | default('main') }};
    client_max_body_size {{ max_body_size | default('16m') }};

    location / {
        proxy_pass         http://backend;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
{% for loc in extra_locations %}
        location {{ loc.path }} { {{ loc.rule }} }
{% endfor %}
    }
}
```

### 模板白名单与检查

```yaml
# ansible.cfg
jinja2_extensions = jinja2.ext.do     # 允许在模板里用 {% do %}

# 命令行检查模板语法（不写文件）
ansible localhost -m debug -a "msg={{ lookup('template', 'nginx.conf.j2') }}"
```

### `template` vs `copy` vs `blockinfile`

| 需求 | 用 |
|---|---|
| 内容随变量变化 | `template` |
| 内容固定 | `copy` |
| 只改配置文件里某一处，不动其他 | `blockinfile` / `lineinfile` |

---

## Roles（角色）

Role 是「可复用的 playbook 片段」，标准目录约定即入口，Ansible 自动加载。

```bash
ansible-galaxy init roles/nginx
ansible-galaxy role install geerlingguy.nginx     # 从 Galaxy 装
ansible-galaxy role list -r requirements.yml
```

### 角色内各文件的作用

| 文件 | 作用 | 被覆盖性 |
|---|---|---|
| `defaults/main.yml` | 默认参数，role 调用时可覆盖 | 高（最该放这里） |
| `vars/main.yml` | 内部变量，优先级高于 defaults | 低（不要在这里放可调参数） |
| `tasks/main.yml` | 任务入口 | — |
| `handlers/main.yml` | 处理器 | — |
| `meta/main.yml` | 依赖声明 | — |
| `templates/`, `files/` | 静态资源 | — |
| `tests/` | 角色自带测试（molecule 等） | — |

### 调用角色

```yaml
- hosts: webservers
  become: yes
  roles:
    # 最简
    - nginx

    # 带变量覆盖
    - role: nginx
      nginx_port: 8080
      nginx_extra_config: |
        add_header X-Frame-Options SAMEORIGIN;

    # 依赖角色先执行（meta/main.yml 里已声明的会自动加载）
    - role: php
      when: with_php

    # 条件包含（tags 控制整段是否执行）
    - role: monitoring
      when: install_monitoring
      tags: [monitoring]

    # include_role：动态，可放循环里；import_role：静态，可被解析器提前解析
    - include_role: { name: app, tasks_from: deploy }
      loop: "{{ apps }}"
```

`meta/main.yml` 声明依赖：

```yaml
# roles/nginx/meta/main.yml
dependencies:
  - role: common            # 依赖的角色的 tasks 会在本角色之前执行
  - role: firewall
    vars: { port: 80 }
  collections:
    - community.general
```

### 角色变量引用（跨目录）

在 `tasks/` 下的子文件里引用同角色目录的文件，**必须用 `{{ role_path }}`**（老版本）或 `{{ lookup('role_path') }}`：

```yaml
- template:
    src: "{{ role_path }}/templates/nginx.conf.j2"     # 跨子目录引用
    dest: /etc/nginx/nginx.conf

- file:
    src: "{{ lookup('env', 'HOME') }}/.vimrc"
    dest: ~/.vimrc
    remote_src: yes
```

---

## Vault 与敏感数据

见上文变量章节。三条铁律：

1. **永远不要把密码写进 git 里的普通变量**，用 `group_vars/all/vault.yml`
2. **不要在 `debug` 里打印敏感变量**，用 `no_log: true`
3. **关闭命令回显中的密码**：`ansible.builtin.command: "mysql -p{{ db_pass }}"` 会泄露，改用 `no_log: true` 或读环境变量

```yaml
- name: 设置 root 密码
  ansible.builtin.user:
    name: root
    password: "{{ root_password | password_hash('sha256') }}"
  no_log: true                      # 整个 task 不输出
```

---

## Tags 与跳过

```bash
ansible-playbook site.yml --tags deploy        # 只跑带 deploy 标签的
ansible-playbook site.yml --skip-tags deploy    # 跳过
ansible-playbook site.yml --list-tags
ansible-playbook site.yml --list-hosts         # 看会打到哪些主机
ansible-playbook site.yml --list-tasks         # 看任务清单（不执行）
ansible-playbook site.yml --start-at-task "安装 nginx"
ansible-playbook site.yml --step               # 每个 task 前交互确认
ansible-playbook site.yml --check --diff       # 试运行：只报告会变什么，不实际改
ansible-playbook site.yml --syntax-check       # 只检查语法
```

```yaml
- name: 生产环境的危险操作
  hosts: prod
  tasks:
    - name: 重启数据库
      service: { name: mysql, state: restarted }
      tags: [never, destructive]        # `never` 标签默认不执行，需 --tags never
```

---

## 错误处理

```yaml
# block + rescue + always
- name: 部署应用
  block:
    - name: 停止服务
      service: { name: myapp, state: stopped }

    - name: 覆盖新版本
      copy: { src: app.tar.gz, dest: /opt/ }

    - name: 启动服务
      service: { name: myapp, state: started }

  rescue:
    - name: 回滚
      debug: msg="部署失败，正在回滚"
    - copy: { src: backup/app.tar.gz, dest: /opt/ }   # 恢复旧包
    - service: { name: myapp, state: started }

  always:
    - debug: msg="无论成败都执行"

  # 也可以给整个 block 加 when/tag
  tags: [deploy]
```

### 常用错误控制

```yaml
- name: 允许的失败
  command: systemctl is-active nginx
  register: r
  failed_when: r.rc not in [0, 3]        # 自定义失败判定，比 ignore_errors 精确
  changed_when: false

- name: 忽略失败（会输出警告但继续）
  command: /usr/bin/true
  failed_when: false
  ignore_errors: yes                    # ⚠️ 用 failed_when 更好

- name: 超时控制
  command: /usr/bin/long_running_thing
  async: 7200
  poll: 10                              # 每 10 秒轮询一次，超时 2 小时
```

### failed_when / changed_when 判断依据

Ansible 判定 task 成功/变化的依据：

| 模块类型 | changed 依据 | failed 依据 |
|---|---|---|
| `command` / `shell` / `script` | 总是 changed（除非 `changed_when`） | rc != 0 |
| `file` / `copy` / `package` 等 | 文件/资源实际变化 | 模块内部判断 |
| `fail` / `assert` | 强制 | 强制 |

**规则**：只读命令（`command` 查状态、`setup`、`pip list`）一定要加 `changed_when: false`，否则每次都显示 changed，日志没法看。

---

## 检查模式（--check）与 Diff

```bash
ansible-playbook site.yml --check --diff
```

- `--check`：所有 task 都不真正执行，只预测结果
- `--diff`：显示文件变更的具体 diff

**限制**：`command` / `shell` / `script` 在 check 模式下被**跳过**（不支持预测），会报 `skipped`。所以依赖 `command` 的逻辑在 check 模式下结果不可靠 —— 尽量用 `template` / `copy` / `file` 这类支持 check 的模块。

条件里可用 `ansible_check_mode` 变量：

```yaml
- name: 只在非 check 模式执行
  command: /usr/bin/rebuild-cache
  when: not ansible_check_mode
```

---

## 变量优先级速查（从低到高）

```text
1  命令行 -e
2  set_fact / register
3  role vars/main.yml
4  block vars
5  task vars
6  include_vars
7  play vars / play vars_files
8  role defaults/main.yml
9  inventory group_vars/all
10 host_vars
11 inventory 主机变量（hosts 文件里的 ansible_*）
12 远程主机上的 facts
13  role defaults（若从 Galaxy 安装且被 include 多次，实际会插在 7~8 之间）
```

实际排查顺序：`ansible localhost -m debug -a "var=hostvars[web1]"`，或者在 task 上加 `no_log: false` 看合并结果。

---

## 事实（Facts）

Facts 是从远端采集的主机信息，`gather_facts: yes`（默认）时在 play 开始前自动执行 `setup` 模块获取。

```bash
ansible web1 -m setup                              # 全部 facts
ansible web1 -m setup -a "filter=ansible_memory*"  # 只看某类
```

```yaml
- debug:
    msg:
      - "主机名: {{ ansible_hostname }}"
      - "系统: {{ ansible_distribution }} {{ ansible_distribution_version }}"
      - "内核: {{ ansible_kernel }}"
      - "架构: {{ ansible_architecture }}"
      - "CPU: {{ ansible_processor_vcpus }} 核"
      - "内存: {{ (ansible_memtotal_mb / 1024) | round(1) }} GB"
      - "IP: {{ ansible_default_ipv4.address | default('N/A') }}"
      - "虚拟化: {{ ansible_virtualization_type }}"
      - "网口: {{ ansible_interfaces | dict2items | map(attribute='key') | list }}"

- name: 条件化任务
  debug: msg="Debian 系"
  when: ansible_os_family == "Debian"
```

### 自定义 Facts

```ini
# /etc/ansible/facts.d/custom.fact
{
  "role": "db_master",
  "app_version": "3.2.1"
}
```

```yaml
- debug: msg="{{ ansible_facts.role }}"
```

### 按组采集不同 facts

```yaml
- hosts: webservers
  gather_facts: yes
- hosts: dbservers
  gather_facts: no          # 省时间
```

---

## Vault + 动态清单 + Molecule 项目模板

一个最小可用项目：

```text
infra/
├── ansible.cfg
├── inventory/hosts.yml
├── group_vars/all.yml
├── group_vars/all/vault.yml
├── roles/common/tasks/main.yml
├── playbooks/site.yml
└── requirements.yml        # ansible-galaxy role install -r requirements.yml
```

```yaml
# requirements.yml
roles:
  - geerlingguy.nginx
  - geerlingguy.postgresql
collections:
  - name: community.general
    version: ">=6.0.0"
```

```bash
ansible-galaxy install -r requirements.yml -p ./roles
ansible-galaxy collection install -r requirements.yml
```

---

## 与 Molecule 配合做角色测试

```bash
molecule init -r nginx
molecule test          # 创建实例 → converge（跑 playbook）→ verify（断言）→ destroy
```

`verify.yml` 里写断言，这是角色 CI 的最低门槛：

```yaml
- name: 验证 nginx 装上了
  ansible.builtin.command: nginx -v
  register: nginx_ver
  changed_when: false

- name: 断言版本
  ansible.builtin.assert:
    that: nginx_ver.rc == 0
```

---

## 性能优化

```bash
# 1. 提高并发
ansible-playbook site.yml -f 50          # forks=50

# 2. SSH 连接复用（ansible.cfg，收益最大）
# ssh_args = -o ControlMaster=auto -o ControlPersist=600s

# 3. pipelining（ansible.cfg）
# pipelining = True

# 4. 非事实采集
gather_facts: no
ansible web1 -m setup -a "filter=ansible_default_ipv4"

# 5. 策略选择
strategy: free        # 主机之间不互相等待，适合各干各的部署
strategy: linear      # 默认，一台失败全部停下，适合有顺序依赖的场景

# 6. 事实缓存（配 ansible-facts cache 插件）
ansible-playbook site.yml -e cacheable=yes
```

---

## 常见错误与排查

| 现象 | 原因 / 解法 |
|---|---|
| `[WARNING]: Could not match supplied host pattern` | inventory 路径不对；确认 `-i` 或 `ansible.cfg` |
| `ssh: connect to host ... port 22: Connection refused` | 防火墙/SSH 端口/安全组 |
| `sudo: a password is required` | 配 NOPASSWD sudo，或 `become_pass_file` |
| `[DEPRECATION WARNING]` | 用旧的短模块名（如 `debug:`）→ 改全限定名 `ansible.builtin.debug:` |
| `Mode 0644` 不生效 | YAML 里 `0644` 被当八进制整数，**要写字符串** `"0644"` |
| task 每次都显示 changed | 只读命令加 `changed_when: false` |
| `when` 里 `False` 判断失效 | YAML 的 yes/no/on/off → 加引号或用 `| bool` |
| 模板不更新 | `template` 模块靠 checksum 判断，确认源模板路径没写错 |
| `meta: flush_handlers` 后任务不执行 | 检查 handler 是否真的被 notify |
| Windows 主机连不上 | 需要 `winrm` 连接插件 + PowerShell，端口 5985/5986 |
| `yum` 报 SSL 错误 | 老系统证书过期，需 `update-ca-trust` / 换 vault |

### 常用排查命令

```bash
ansible -vvvv all -m ping              # 完整调试（-v 提一级）
ansible-playbook site.yml -vvv --syntax-check
ansible all -m debug -a "var=hostvars['web1'].ansible_default_ipv4"
ANSIBLE_KEEP_REMOTE_FILES=1 ansible all -m raw -a "uptime"   # 保留远端模块文件
```

`-v` 级别：

| 级别 | 内容 |
|---|---|
| (无) | task 结果汇总 |
| `-v` | 额外显示 `invocation`（实际执行的任务内容） |
| `-vv` | 显示结果数据（如 template 渲染后的完整内容） |
| `-vvv` | 显示模块调用的完整细节、`set -x` 输出 |
| `-vvvv` | 显示 SSH 命令、Python 模块调用过程 |

---

## 完整实战示例：部署一套 Nginx + 后端应用

```yaml
# playbooks/deploy.yml
- name: 部署应用服务器
  hosts: webservers
  become: yes
  gather_facts: yes
  serial: 2
  max_fail_percentage: 0

  vars:
    app_name: "myapp"
    app_port: 8000
    app_version: "1.4.2"
    deploy_user: "deploy"
    nginx_port: 80

  pre_tasks:
    - name: 校验端口范围
      ansible.builtin.assert:
        that: 1 <= (nginx_port | int) <= 65535
        fail_msg: "nginx_port 非法"

    - name: 关闭 SELinux（CentOS/RHEL）
      ansible.builtin.command: setenforce 0
      when: ansible_os_family == "RedHat"
      changed_when: false
      failed_when: false
      tags: [never]

  handlers:
    - name: 重载 nginx
      ansible.builtin.service:
        name: nginx
        state: reloaded

  roles:
    - role: common              # 系统基线：用户、时区、swap、防火墙
      tags: [common]

  tasks:
    - name: 创建部署用户
      ansible.builtin.user:
        name: "{{ deploy_user }}"
        groups: [wheel]
        shell: /bin/bash
        append: yes

    - name: 安装依赖包
      ansible.builtin.package:
        name:
          - nginx
          - python3
          - "{{ 'python3-pip' if ansible_os_family == 'Debian' else 'python3-pip' }}"
        state: present

    - name: 创建应用目录
      ansible.builtin.file:
        path: "/opt/{{ app_name }}"
        state: directory
        owner: "{{ deploy_user }}"
        mode: "0755"

    - name: 检查当前版本
      ansible.builtin.command:
        cmd: cat /opt/{{ app_name }}/VERSION
      register: current_ver
      changed_when: false
      failed_when: false

    - name: 部署新版本
      ansible.builtin.unarchive:
        src: "dist/{{ app_name }}-{{ app_version }}.tar.gz"
        dest: "/opt/{{ app_name }}"
        remote_src: yes
        extra_opts: ["--strip-components=1"]
      when: current_ver.stdout | trim != app_version
      notify: 重载 nginx

    - name: 写入应用配置
      ansible.builtin.template:
        src: app.conf.j2
        dest: "/opt/{{ app_name }}/app.conf"
        owner: "{{ deploy_user }}"
        mode: "0640"
      notify: 重载 nginx

    - name: 校验配置语法
      ansible.builtin.command:
        cmd: /opt/{{ app_name }}/venv/bin/python -c "import config"
      changed_when: false
      notify: 重载 nginx

    - name: 立即应用 handler
      ansible.builtin.meta: flush_handlers

    - name: 创建 systemd 服务
      ansible.builtin.template:
        src: app.service.j2
        dest: /etc/systemd/system/{{ app_name }}.service
        mode: "0644"
      notify:
        - 重载 nginx
        - 重载 systemd

    - name: 启动服务
      ansible.builtin.systemd:
        name: "{{ app_name }}"
        state: started
        enabled: yes
        daemon_reload: yes

    - name: 健康检查（最多等 30s）
      ansible.builtin.uri:
        url: "http://localhost:{{ app_port }}/health"
        status_code: 200
      register: health
      until: health is succeeded
      retries: 10
      delay: 3
      failed_when: health is failed
```

```jinja
# roles/templates/app.service.j2
[Unit]
Description={{ app_name }}
After=network.target

[Service]
User={{ deploy_user }}
WorkingDirectory=/opt/{{ app_name }}
Environment="APP_ENV=production"
ExecStart=/opt/{{ app_name }}/venv/bin/python -m {{ app_name }}
Restart=always
RestartSec=5
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
```

```bash
# 执行
ansible-playbook -i inventory/hosts.yml playbooks/deploy.yml --check --diff -v
ansible-playbook -i inventory/hosts.yml playbooks/deploy.yml --tags deploy
ansible webservers -b -m service -a "name=myapp state=restarted"
```

---

## 速查清单

```bash
# 排错三连
ansible all -m ping                                          # 连通性
ansible-playbook x.yml --syntax-check                        # 语法
ansible-playbook x.yml -vvv --check --diff                   # 预演 + 详细日志

# 常用组合
ansible-playbook site.yml --tags deploy -e env=prod          # 打标签 + 注变量
ansible-playbook site.yml --limit web1                       # 只打一台
ansible all -m shell -a "df -h | sort -k5 -h | tail -3"     # 排查磁盘
ansible all -m setup -a "filter=ansible_memfree_mb"
```

| 场景 | 一行命令 |
|---|---|
| 测连通 | `ansible all -m ping` |
| 批量执行命令 | `ansible all -m shell -a "cmd"` |
| 下发文件 | `ansible all -m copy -a "src=f dest=/tmp/f"` |
| 装软件 | `ansible all -m package -a "name=xx state=present"` |
| 看服务 | `ansible all -m service -a "name=xx state=started"` |
| 看 facts | `ansible all -m setup -a "filter=ansible_*"` |
| 加密变量 | `ansible-vault create group_vars/all/vault.yml` |
| 装 Galaxy 角色 | `ansible-galaxy role install -r requirements.yml` |

---

## 相关笔记

- [SaltStack](saltstack.md) —— 同类工具，更适合大规模实时场景
- [Terraform](terraform.md) —— 开机器（IaC 资源编排）
- [Docker](../docker/) —— 容器化
- [Helm](../helm/) —— K8s 应用打包