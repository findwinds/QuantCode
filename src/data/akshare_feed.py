# src/data/akshare_feed.py  仅替换/追加 get_kline 内逻辑
import akshare as ak
import pandas as pd
from .feed import DataFeed

class AkShareFeed(DataFeed):
    def get_kline(self, symbol: str, freq: str,
              start: str = None, end: str = None,
              fields: list = None) -> pd.DataFrame:
        """
        支持期货日/分钟级统一接口
        freq: '1d' | '1m' | '5m' | '15m' | '30m' | '60m'
        symbol: 如 'RB0'（连续合约）或具体合约 'RB2410'
        """
        # 1. 频率映射
        period_map = {'1d': 'daily',
                      '1m': '1',
                      '5m': '5',
                      '15m': '15',
                      '30m': '30',
                      '60m': '60'}
        if freq not in period_map:
            raise ValueError(f'暂不支持 {freq}')

        # 2. 拉数据
        if freq == '1d':
            # 日 K
            df = ak.futures_zh_daily_sina(symbol=symbol)
        else:
            # 分钟 K
            df = ak.futures_zh_minute_sina(symbol=symbol, period=period_map[freq])

        # 3. 统一列名 & 索引
        df = df[['date' if 'date' in df.columns else 'datetime',
                'open', 'high', 'low', 'close', 'volume']]
        df.columns = ['datetime', 'open', 'high', 'low', 'close', 'volume']
        df['datetime'] = pd.to_datetime(df['datetime'])
        df = df.set_index('datetime').sort_index()

        # 4. 时间裁剪（字符串索引即可）
        df = df.loc[start:end]

        # 5. 返回所需列
        return df if fields is None else df[fields]