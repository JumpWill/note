
## 基本命令

```shell
pytest -v  file/path

# 测试一个函数
pytest tests/test_mod.py::test_func
# 测试一个类
pytest tests/test_mod.py::TestClass
# 测试一个类方法
pytest tests/test_mod.py::TestClass::test_method
# 测试函数带参数
pytest tests/test_mod.py::test_func[x1,y2]
# 组织

```

## 写法

```python
def test_fun1():
    res = fun1()
    assert res == xxx
    with pytest.raises(xxx):
        fun1()
    # 增加匹配错误信息
    with pytest.raises(ValueError, match=r".* 123 .*"):
        myfunc()


# 函数返回作为入参,分解步骤，也可以供给其他地方使用
# @pytest.fixture可复用
@pytest.fixture
def first_entry():
    return "a"


@pytest.fixture
def order(first_entry):
    return [first_entry]


def test_string(order):
    # Act
    order.append("b")

    # Assert
    assert order == ["a", "b"]
```
