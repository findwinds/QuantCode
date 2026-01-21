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
        df['signal'] = 0.0
        df['fast'] = df['close'].rolling(self.fast).mean()
        df['slow'] = df['close'].rolling(self.slow).mean()
    
        # 0 观望；1 金叉(多)；-1 死叉(空)
        long_cross  = (df['fast'] > df['slow']) & (df['fast'].shift(1) <= df['slow'].shift(1))
        short_cross = (df['fast'] < df['slow']) & (df['fast'].shift(1) >= df['slow'].shift(1))

        # 方向
        df.loc[long_cross,  'signal'] = 1.0
        df.loc[short_cross, 'signal'] = -1.0
        
        # 目标敞口：默认满仓，可外部改
        df['target'] = 0.0
        df.loc[df['signal'] == 1,  'target'] = 1.0   # 满仓多
        df.loc[df['signal'] == -1, 'target'] = -1.0  # 满仓空
        # 其余 target=0 → 空仓  
        return df