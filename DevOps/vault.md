# vault了解

## 认识

权限严格管理的配置中心，可以通过UI，CLI，HTTP对令牌、密码、证书、加密密钥数据进行访问，以保护密钥和其他敏感数据。也可以定义租期，即在某个时间段内才能访问。

## secret engine

可以理解为项目/namespace，其内容为树形结构，叶子节点存储数据，输入path的时候 / 分割路径

### 类型

#### kv

分为v1/v2版本

区别

| Command | KV v1 endpoint | KV v2 endpoint |
|----|----|----|
| ```javascript
vault kv get

``` | secret/<key_path> | secret/**data**/<key_path> |
| ```javascript
vault kv put
``` | secret/<key_path> | secret/**data**/<key_path> |
| ```javascript
vault kv list
``` | secret/<key_path> | secret/**metadata**/<key_path> |
| ```javascript
vault kv delete
``` | secret/<key_path> | secret/**data**/<key_path> |



| Command | KV v2 endpoint |
|----|----|
| ```javascript
vault kv patch
``` | secret/**data**/<key_path> |
| ```javascript
vault kv rollback
``` | secret/**data**/<key_path> |
| ```javascript
vault kv undelete
``` | secret/**undelete**/<key_path> |
| ```javascript
vault kv destroy
``` | secret/**destroy**/<key_path> |
| ```javascript
vault kv metadata
``` | secret/**metadata**/<key_path> |

 ![](attachments/bef2a4b5-9179-4c5e-beba-88cbdd7b0da1.png " =945x1051")




## policy

权限策略，权限分为`["create", "read", "update", "patch", "delete", "list"]`


对于某个 secret engine下面的权限。可以精确到具体某个值



## access

### entity

实体？可以理解为取数据的用户，因为vault不带用户系统，而一般是接三方的用户，如authentik，每个用户通过不同的认证方式接用户认证。

 ![](attachments/46ac8e3f-ac4e-42c6-888b-7c60ee5a1452.png " =2259x1090")

每个用户可以在不同的认证方式里有不同的别名。


但是同一种认证方式下只能有一个别名


可以为单个entity添加policy


### group

组，可以选择多个entity和多个policy到组里以及多个group，

#### 内部组

组A包含了组B,C,组A为父组



绑定到组下面的entity的权限应该是取交集


#### 外部组

外部组，仅仅能绑定策略，类似entity，可以为认证方式取别名。

比较粗犷。
