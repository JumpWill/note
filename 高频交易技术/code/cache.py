import time


def benchmark_cache_effect():
    """对比冷启动 vs 缓存预热后的执行延迟"""
    iterations = 100000

    # 冷启动测量
    start = time.perf_counter_ns()
    for _ in range(iterations):
        x = 50000.0
        spread = 2.0
        if spread < 5.0:
            signal = 1
        else:
            signal = 0
    cold_ns_per_op = (time.perf_counter_ns() - start) / iterations

    # 预热后再测
    for _ in range(1000):  # 预热
        pass
    start = time.perf_counter_ns()
    for _ in range(iterations):
        x = 50000.0
        spread = 2.0
        if spread < 5.0:
            signal = 1
        else:
            signal = 0
    warm_ns_per_op = (time.perf_counter_ns() - start) / iterations

    print(f"Cold: {cold_ns_per_op:.1f}ns/op")
    print(f"Warm: {warm_ns_per_op:.1f}ns/op")
    print(
        f"Improvement: {(cold_ns_per_op - warm_ns_per_op) / cold_ns_per_op * 100:.1f}%"
    )

benchmark_cache_effect()