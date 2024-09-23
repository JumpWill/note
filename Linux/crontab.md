## Crontab

cron 是linux 下的定时任务的后台进程
crontab 是cron 的配置文件

### 进程

```bash
# 启动
service cron start
# 停止
service cron stop
# 重启
service cron restart
```

### 编写

编写crontab

```bash
crontab -e
```

### 格式

```bash
* * * * * command
```

### notice  

1. 如果有多个python版本，需要指定python版本

```bash
/usr/bin/python3 /home/user/work/test.py
```

2. 如果需要执行的脚本依赖于环境变量，需要将环境变量写入到脚本中,或者在命令中指定，crontab的任务是cron的子进程，无法继承父进程的环境变量

```bash
export PATH=/usr/local/bin:$PATH

# 指定环境变量
name=value /usr/bin/python3 /home/user/work/test.py
```
