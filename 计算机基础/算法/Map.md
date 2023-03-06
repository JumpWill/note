#

## Map

通常是用一个Map来记录已经遍历的数据的特征,然后在循环中根据条件将得到的数据进行使用；

## 解法

根据条件用一个Map来存储数据,然后使用Map;

## 例题

下面数字是leetcode题号

### 1

```text
给定一个整数数组 nums 和一个整数目标值 target，请你在该数组中找出 和为目标值 target  的那 两个 整数，并返回它们的数组下标。
你可以假设每种输入只会对应一个答案。但是，数组中同一个元素在答案里不能重复出现。
你可以按任意顺序返回答案。

输入：nums = [2,7,11,15], target = 9
输出：[0,1]
解释：因为 nums[0] + nums[1] == 9 ，返回 [0, 1] 。
```

```python
class Solution:
    def twoSum(self, nums: List[int], target: int) -> List[int]:
        # 利用哈希表
        d = {}
        for i, num in enumerate(nums):
            if target - num in d:
                return [d[target - num], i]
            d[num] = i
        return []
```
