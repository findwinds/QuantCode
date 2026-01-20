import sys, os
import pandas as pd
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.backtest.engine import SimpleEngine

# 1. 造一段假行情：100 根收盘价从 100 涨到 200，再跌回 150
dates = pd.date_range('2025-01-01', periods=100, freq='1d')
price = np.linspace(100, 200, 50).tolist() + np.linspace(200, 150, 50).tolist()
df = pd.DataFrame({
    'open': price,
    'high': price,
    'low': price,
    'close': price,
    'volume': 1000
}, index=dates)

# 2. 造一段假信号：前 50 根做多，后 50 根做空
df['signal'] = 0.0
df.iloc[:50, df.columns.get_loc('signal')] = 1.0   # 1-50 目标多
df.iloc[50:, df.columns.get_loc('signal')] = -1.0  # 51-100 目标空

# 3. 跑回测
engine = SimpleEngine(cash=100_000, comm=0.0002, margin_ratio=0.1, slip=0.0)
result, stats = engine.run(df)

trades = result[result['pos'].diff().abs() > 0]
print('---- 成交日 ----')
print(trades[['close', 'signal', 'pos', 'cash', 'equity']])

print('---- 每日盈亏 ----')
print(result[['close', 'pos', 'cash', 'equity']].head(10))
print(result[['close', 'pos', 'cash', 'equity']].tail(10))

# 4. 断言：低买高卖再高空，总收益应 > 0
print('----- 离线冒烟测试 -----')
print(f'总收益: {stats.total_return:.2%}')
print(f'夏普  : {stats.sharpe:.2f}')
print(f'最大回: {stats.max_drawdown:.2%}')
print(f'交易次: {stats.trade_count}')
assert stats.total_return > 0, '低买高卖应赚钱'
print('✅ 引擎逻辑通过')