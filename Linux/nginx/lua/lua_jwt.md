```shell
yum install yum-utils

# 添加仓库
yum-config-manager --add-repo https://openresty.org/package/centos/openresty.repo

# 安装 OpenResty
yum install openresty

# 安装命令行工具 resty
yum install openresty-resty

# 安装命令行工具 opm
yum install openresty-opm

# 安装插件
opm get SkyLothar/lua-resty-jwt
```

默认情况下，nginx 会移除所有从父进程继承的环境变量，如果你想使用这些环境变量，需要使用该指令显示告知nginx不要移除你指定的环境变量。而且你也可以更改它们的值或创建新的环境变量。
需要在总的配置文件中配置
···
env XXXX;

# lua脚本中

os.getenv("XXXX")
···





在请求头中最好是存在中滑线，不要使用下划线，会存在一些问题。