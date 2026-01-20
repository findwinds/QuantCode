# src/backtest/engine.py
import pandas as pd
from pathlib import Path
from dataclasses import dataclass


@dataclass
class Stats:
    total_return: float
    sharpe: float
    max_drawdown: float
    trade_count: int


class SimpleEngine:
    def __init__(self, cash: float = 100_000,
                 comm: float = 0.0002,
                 margin_ratio: float = 0.12,   # 螺纹钢 12 %
                 contract_multiplier: int = 10, # 合约乘数 
                 slip: float = 1.0):            # 1 跳滑点（元/手）
        self.init_cash = cash
        self.comm = comm
        self.margin_ratio = margin_ratio
        self.contract_multiplier = contract_multiplier
        self.slip = slip          # 滑点金额

    def run(self, signal_df: pd.DataFrame) -> tuple[pd.DataFrame, Stats]:
        df = signal_df.copy()
        df['pos']   = 0.0
        df['cash']  = float(self.init_cash)
        df['equity']= float(self.init_cash)

        for i, (ts, row) in enumerate(df.iterrows()):
            price   = row['close']
            target  = row['signal']          # 第一根必为 0
            prev_pos = df['pos'].iloc[i-1] if i > 0 else 0.0   # 昨日仓位（首日为 0）
            # 只有目标 ≠ 昨日仓位才下单
            if target != prev_pos:
                # 交易量 要么是2 要么是-2
                trade_size = target - prev_pos
                notional   = abs(trade_size) * price
                margin     = notional * self.margin_ratio
                fee        = notional * self.comm
                slip_cost  = abs(trade_size) * self.slip

                # 现金扣减：保证金 + 费用 + 滑点
                df.at[ts, 'cash'] = (df['cash'].iloc[i-1] if i > 0 else self.init_cash) - (margin + fee + slip_cost)
                df.at[ts, 'pos']  = target
            else:
                # 无交易，只盯市
                df.at[ts, 'cash'] = df['cash'].iloc[i-1] if i > 0 else self.init_cash
                df.at[ts, 'pos']  = target

            # 收盘权益
            df.at[ts, 'equity'] = df.at[ts, 'cash'] + df.at[ts, 'pos'] * price

        # 绩效
        ret = df['equity'].pct_change().fillna(0)
        stats = Stats(
            total_return=(df['equity'].iloc[-1] / df['equity'].iloc[0] - 1),
            sharpe=ret.mean() / ret.std() * (252 ** 0.5) if ret.std() else 0,
            max_drawdown=(df['equity'] / df['equity'].cummax() - 1).min(),
            trade_count=(df['pos'].diff().abs() > 0).sum()
        )
        return df, stats