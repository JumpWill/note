## tortoise-orm

tortoise-orm是一个异步的ORM，使用方法参考django-orm，只是它的方法都是异步的，前面需要加await。
此处重在讲tortoise-orm与fastapi使用以及aerich的使用。
下面的auth目录下的

``` shell
├── api
├── app.py
├── __init__.py
├── migrations
│   └── auth
│       └── 0_20220521114611_init.sql
├── models.py
├── settings.py
```

### model

app可以将model分类，然后之后在初始化连接的时候会用到。

```python
# models
from tortoise import fields, models

class User(models.Model):
    ...

    class Meta:
        app = "auth"
        table = "table_name"
        table_description = "用户信息"


class Test(models.Model):
    ...

    class Meta:
        app = "test"
        table = "table_name"
        table_description = "测试信息"

```

### with fastapi

启动app中如何使用了？
TODO: 此处需要在做一下测试,

例如·上面声明了User app为auth,在写models

```python
# app
from tortoise.contrib.fastapi import HTTPNotFoundError, register_tortoise

register_tortoise(
    app,
    db_url=DB_URL,
    modules={
        "auth": ["auth.models",]
        # 此处则是选择使用哪些model，且如果需要使用则需要写(可以将model按文件分)
        "test": [ "auth.models"]
  },
    # generate_schemas=True,  # 是否生成对应的表
    add_exception_handlers=True,
)
```

## aerich

这儿是tortoise-orm的迁移工具

```python
# settings

# apps中可以以app划分数据，aerich中可以 --app 指定操作具体某个
TORTOISE_ORM = {
    "connections": {"default": DB_URL },
    "apps": {
        "auth": {
            "models": ["aerich.models", "models"], 
            "default_connection": "default",
        },
    },
}

```

```shell
# 初始化
aerich init  --tortoise-orm xxx.settings.TORTOISE_ORM
# 创建表  
aerich --app xxx init-db
# 之前报错是因为aerich0.6.3版本有问题，回退到了0.6.2正常
aerich --app xxx upgrade
# 降级数据库 
aerich --app xxx downgrade
```

ps：项目中有了对应的migration,可以直接使用upgrade将models的当前信息映射到数据库。
