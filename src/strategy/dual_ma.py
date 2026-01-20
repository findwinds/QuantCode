# src/strategy/dual_ma.py
import pandas as pd


class DualMaStrategy:
    """双均线趋势跟随：金叉做多，死叉做空"""

    def __init__(self, fast: int = 20, slow: int = 60):
        self.fast = fast
        self.slow = slow

    # 唯一必须实现的接口
    def create_signal(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        输入标准 OHLCV(df) ->
        返回同表 + signal 列(+1/-1/0)
        """
        df = df.copy()
        df['fast'] = df['close'].rolling(self.fast).mean()
        df['slow'] = df['close'].rolling(self.slow).mean()

        # 0 观望；1 金叉(多)；-1 死叉(空)
        df['signal'] = 0.0
        # 1=多头持仓；-1=空头持仓；0=空仓（可扩展）
        df.loc[df['fast'] > df['slow'], 'signal'] = 1.0
        df.loc[df['fast'] < df['slow'], 'signal'] = -1.0
        # 其余行天然 0.0 → 空仓（或无均线区域）
        return df