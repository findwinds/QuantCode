import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.data import AkShareFeed
from src.strategy.dual_ma import DualMaStrategy
from src.backtest.engine import SimpleEngine

from pathlib import Path
OUTPUT_DIR = Path('output')
OUTPUT_DIR.mkdir(exist_ok=True)

feed = AkShareFeed()
df = feed.get_kline('RB0', '1d', '2022-01-01', '2023-12-31')

strategy = DualMaStrategy(fast=20, slow=60)
signal_df = strategy.create_signal(df)

engine = SimpleEngine(cash=100_000, comm=0.0002)
result, stats = engine.run(signal_df)

print('----- 绩效 -----')
print(f'总收益: {stats.total_return:.2%}')
print(f'夏普  : {stats.sharpe:.2f}')
print(f'最大回: {stats.max_drawdown:.2%}')
print(f'交易次: {stats.trade_count}')

# 保存完整结果
result.to_csv(OUTPUT_DIR / 'backtest.csv')