# scripts/run_strategy.py
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.data import AkShareFeed
from src.strategy.dual_ma import DualMaStrategy

# 1. 取数据
feed = AkShareFeed()
df = feed.get_kline('RB0', '1d', '2023-01-01', '2023-12-31')

# 2. 策略生成信号
strategy = DualMaStrategy(fast=20, slow=60)
signal_df = strategy.create_signal(df)

# 3. 看最后 10 根 K 线信号
print(signal_df[['close', 'fast', 'slow', 'signal']].tail(10))