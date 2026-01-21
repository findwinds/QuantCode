import sys, os
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.strategy.dual_ma import DualMaStrategy

# 1. 造一段假行情：200 根日 K，足够慢线算出值
dates = pd.date_range('2025-01-01', periods=200, freq='1d')
n1, n2, n3 = 70, 60, 70        # 三段长度（总和≥200）
price = np.concatenate([
    np.linspace(200, 140, n1),   # 跌：200→140
    np.linspace(140, 200, n2),   # 涨：140→200（金叉在这里）
    np.linspace(200, 140, n3)    # 再跌：200→140（死叉在这里）
])

# 2. 拼成标准 OHLCV（全部用收盘价，方便肉眼验证）
df = pd.DataFrame({
    'open':  price,
    'high':  price + 2,
    'low':   price - 2,
    'close': price,
    'volume': 1000
}, index=dates)

# 3. 跑策略
strategy = DualMaStrategy(fast=20, slow=60)
signal_df = strategy.create_signal(df)

# 4. 肉眼验证：金叉后 signal=1，死叉后 signal=-1
print('----- 策略离线冒烟 -----')
cross = signal_df[signal_df['target'] != 0.0]   # 用 target 判交叉
print('----- 目标敞口交叉样本 -----')
print(cross[['close', 'fast', 'slow', 'signal', 'target']].head(10))

# 5. 断言：至少有一次金叉 & 一次死叉
assert signal_df['signal'].eq(1).any(), '应出现金叉'
assert signal_df['signal'].eq(-1).any(), '应出现死叉'
print('✅ 策略信号生成正确')

# 断言：target 层必须出现 +1.0 和 -1.0
assert signal_df['target'].eq(1.0).any(), '应出现 target=+1.0（满仓多）'
assert signal_df['target'].eq(-1.0).any(), '应出现 target=-1.0（满仓空）'
print('✅ 目标敞口生成正确')