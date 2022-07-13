## 简介
FastAPI 是一个用于构建 API 的现代、快速（高性能）的 web 框架，使用 Python 3.6+ 并基于标准的 Python 类型提示。
关键特性:
    快速：可与 NodeJS 和 Go 比肩的极高性能（归功于 Starlette 和 Pydantic）。最快的 Python web 框架之一。
    高效编码：提高功能开发速度约 200％ 至 300％。*
    更少 bug：减少约 40％ 的人为（开发者）导致错误。*
    智能：极佳的编辑器支持。处处皆可自动补全，减少调试时间。
    简单：设计的易于使用和学习，阅读文档的时间更短。
    简短：使代码重复最小化。通过不同的参数声明实现丰富功能。bug 更少。
    健壮：生产可用级别的代码。还有自动生成的交互式文档。
标准化：基于（并完全兼容）API 的相关开放标准：OpenAPI (以前被称为 Swagger) 和 JSON Schema。

## swagger
基于开放标准
用于创建 API 的 OpenAPI 包含了路径操作，请求参数，请求体，安全性等的声明。
使用 JSON Schema (因为 OpenAPI 本身就是基于 JSON Schema 的)自动生成数据模型文档。
经过了缜密的研究后围绕这些标准而设计。并非狗尾续貂。
这也允许了在很多语言中自动生成客户端代码
访问   /docs
### 相关配置
 ```python
debug: bool = False
docs_url: str = "/docs"
openapi_prefix: str = ""
openapi_url: str = "/openapi.json"
redoc_url: str = "/redoc"
title: str = "FastAPI"
version: str = "0.1.0"
disable_docs: bool = False
 ```
将docs_url,redoc_url,openapi_url均设为None的情况下，disable_docs为true才会生效，也就是不能访问docs。

## 依赖注入
在很多的时候，不同的方法有公共的参数，这时候就可以使用Depends设置公共参数并且将其注入到请求中。通过这样做到复用以及代码的简化，并且其中还能对数据进行一些校验。一个方法中也可以使用多个依赖，灵活组合。只能在包含在查询参数GET里面。其中有一个use_cache的参数，其作用为 多个依赖有共同的子依赖的时候，多个request访问，则会将这个子依赖放入缓存中
```python
# @app.get("/")
# async def read_items(commons: dict = Depends(XXX))
# XXX可以 方法,类等。


# 依赖于方法       
async def common_parameters(q: str = None, skip: int = 0, limit: int = 100):
    return {"q": q, "skip": skip, "limit": limit}
            
@app.get("/items/")
async def read_items(commons: dict = Depends(common_parameters)):
    commons.update({'小钟': '同学'})
    return commons

#依赖类       
class Data:
    def __init__(self, q: str , skip: int, limit: int):
        # if q == "shepi":
        #     raise HTTPException(status_code=400, detail="X-Token header invalid")
        self.q = q
        self.skip = skip
        self.limit = limit
@app01.post("/")
def get(commons: Data = Depends(Data)):
    print(commons.q)
    return {"id": "嘤嘤嘤"}

# 多重嵌套
def query_extractor(q: str = None):
    return q

def query_or_cookie_extractor(
        q: str = Depends(query_extractor), last_query: str = Cookie(None)
):
    if not q:
        return last_query
    return q
        
        @app.get("/items/")
        async def read_query(query_or_default: str = Depends(query_or_cookie_extractor)):
            return {"q_or_cookie": query_or_default}
# 多依赖
async def verify_token(x_token: str = Header(...)):
    if x_token != "fake-super-secret-token":
        raise HTTPException(status_code=400, detail="X-Token header invalid")

async def verify_key(x_key: str = Header(...)):
    if x_key != "fake-super-secret-key":
        raise HTTPException(status_code=400, detail="X-Key header invalid")
    return x_key

@app.get("/items/", dependencies=[Depends(verify_token), Depends(verify_key)])
async def read_items():
    return [{"item": "Foo"}, {"item": "Bar"}]
```
### 写法
```python
commons=Depends(CommonQueryParams) 
commons: CommonQueryParams = Depends(CommonQueryParams)
commons: CommonQueryParams = Depends()
commons = Depends(CommonQueryParams)
```
### 依赖
```
app = FastAPI(dependencies=[Depends(verify_token), Depends(verify_key)])

# 分api
from fastapi import ApiRouter
router = ApiRouter(dependencies=[])

```

## 请求相关
### header/cookie/query
大多数标准的headers用 "连字符" 分隔，也称为 "减号" (-)。
但是像 user-agent 这样的变量在Python中是无效的。
因此, 默认情况下, Header 将把参数名称的字符从下划线 (_) 转换为连字符 (-) 来提取并记录 headers.
同时，HTTP headers 是大小写不敏感的，因此，因此可以使用标准Python样式(也称为 "snake_case")声明它们。
因此，您可以像通常在Python代码中那样使用 user_agent ，而不需要将首字母大写为 User_Agent 或类似的东西。
如果出于某些原因，你需要禁用下划线到连字符的自动转换，设置Header的参数 convert_underscores 为 False:


```python
from typing import Optional

from fastapi import FastAPI, Header

app = FastAPI()


@app.get("/items/")
async def read_items(user_agent: Optional[str] = Header(None)):
    return {"User-Agent": user_agent}

@app.get("/items/")
async def read_items(ads_id: Optional[str] = Cookie(None)):
    return {"ads_id": ads_id}
```

### 路径参数
```python
@app.delete("/{id}")
async def get(id: int):
    print(id)
return {"mes": "delete"}
```
PS:	如果有一个方法 路径为 /name  另一个是 /{name},访问/name写在前面的那个方法将会被访问。
### GET参数
可以设置请求参数中必需与不必需的参数，以及设置其默认值。
如果未表明 参数名:optional[类型] = 默认值，那么这个参数就是必须的。
```python
from typing import Optional
@app.get("/xx")
def read_item(page: int = 0, limit: Optional[int] = 10):
```
PS:	对于bool类型数据，1,yes,on,true ，以及其中字母任意变换大小写均为True。no，false同理
### Json
POST或者其他方式的请求参数，使用pydantic可以将json数据直接序列化为对象，对其中数据也可以设置默认值以及可选值.可以多个类深层次嵌套.
```python
from typing import Optional
from fastapi import FastAPI
from pydantic import BaseModel


class Item(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    tax: Optional[float] = None

@app.post("/")
async def get( item:Item,page: bool):
    print(item.name)
    print(page)
return {"mes": "get"}
```
### form
要使用表单，需预先安装 python-multipart。
例如，pip install python-multipart。
声明表单体要显式使用 Form ，否则，FastAPI 会把该参数当作查询参数或请求体（JSON）参数。
```python
from fastapi import FastAPI, Form

app = FastAPI()

@app.post("/login/")
async def login(username: str = Form(...), password: str = Form(...)):
    return {"username": username}
```

## 数据类型
常见的有str,int,bool,float
UUID:

- 一种标准的     "通用唯一标识符" ，在许多数据库和系统中用作ID。
- 在请求和响应中将以 str 表示。

datetime.datetime:

- 一个     Python datetime.datetime.
- 在请求和响应中将表示为     ISO 8601 格式的 str ，比如: 2008-09-15T15:53:00+05:00.

datetime.date:

- Python datetime.date.
- 在请求和响应中将表示为     ISO 8601 格式的 str ，比如: 2008-09-15.

datetime.time:

- 一个     Python datetime.time.
- 在请求和响应中将表示为     ISO 8601 格式的 str ，比如: 14:23:55.003.

datetime.timedelta:

- 一个     Python datetime.timedelta.
- 在请求和响应中将表示为 float 代表总秒数。
- Pydantic     也允许将其表示为 "ISO 8601 时间差异编码", [查看文档了解更多信息](https://pydantic-docs.helpmanual.io/#json-serialisation)。

frozenset:

- 在请求和响应中，作为 set 对待：
- 在请求中，列表将被读取，消除重复，并将其转换为一个 set。
- 在响应中 set 将被转换为 list 。
- 产生的模式将指定那些 set 的值是唯一的     (使用 JSON 模式的 uniqueItems)。

bytes:

- 标准的     Python bytes。
- 在请求和相应中被当作 str 处理。
- 生成的模式将指定这个 str 是 binary "格式"。

Decimal:

- 标准的     Python Decimal。
- 在请求和相应中被当做 float 一样处理。

## 任务
在请求函数中需要执行一些耗时操作，类似于django使用celery那样，为fastapi增加的后台任务。也可以将耗时任务依赖注入到一个方法里面，然后这个方法被请求函数依赖。
后台任务对应的那个函数最好不要有依赖项。
### 后台任务
```python
from fastapi import BackgroundTasks, FastAPI

def task(email: str, message: str = ""):
    time.sleep(5)
    print(email)
    print(message)

@app.get("/")
async def get(backtask: BackgroundTasks):
    email = "999"
    message = "task"
    backtask.add_task(task, email,message)
return {"mes": "get"}
```
### 中间件中的后台任务
```pythpn
from starlette.background import BackgroundTask
from somewhere import functionA
@app.middleware("http")
async def middleware(request: Request, call_next):
........(do something)
response.background = BackgroundTask(functionA, arg)
return response
```
### 定时任务
```python
from fastapi_restful.tasks import repeat_every

app = FastAPI()


@app.on_event("startup")
@repeat_every(seconds=60*60)  # 1 hour
def remove_expired_tokens_task() -> None:
    with open(r"1.txt","a") as f:
        f.write("9999")
print("this is 定时任务!")
```
## 中间件
