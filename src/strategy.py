def sma_strategy(prices, n=5):
    """返回最简单的移动平均方向：1 多 / -1 空 / 0 观望"""
    if len(prices) < n:
        return 0
    return 1 if prices[-1] > sum(prices[-n:]) / n else -1