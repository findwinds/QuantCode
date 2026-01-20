# src/data/akshare_feed.py  仅替换/追加 get_kline 内逻辑
import akshare as ak
import pandas as pd
from pathlib import Path
from .feed import DataFeed

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger('AkShareFeed')

CACHE_DIR = Path(__file__).resolve().parents[2] / 'data' / 'futures'
CACHE_DIR.mkdir(parents=True, exist_ok=True)

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
        
        cache_file = CACHE_DIR / f'{symbol}_{freq}.csv'
        # 1. 缓存命中且日期足够 → 直接读盘
        if cache_file.exists():
            df_cache = pd.read_csv(cache_file, index_col=0, parse_dates=True)
            if start is None:
                logger.info('[%s %s] 完全命中缓存，直接读盘', symbol, freq)
                return df_cache if fields is None else df_cache[fields]
            cache_start, cache_end = df_cache.index[[0, -1]]
            if pd.Timestamp(start) >= cache_start and pd.Timestamp(end) <= cache_end:
                logger.info('[%s %s] 区间命中缓存，直接切片', symbol, freq)
                return df_cache.loc[start:end] if fields is None else df_cache.loc[start:end, fields]

        # 2. 缓存不足 → 拉远端
        logger.info('[%s %s] 缓存缺失/不足，开始拉取远端数据...', symbol, freq)
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

        # 4. 增量合并（避免重复下载）
        if cache_file.exists():
            df_old = pd.read_csv(cache_file, index_col=0, parse_dates=True)
            df = pd.concat([df_old, df]).drop_duplicates().sort_index()

        # 5. 写盘
        logger.info('[%s %s] 写入本地缓存 %s', symbol, freq, cache_file)
        df.to_csv(cache_file, compression=None)

        # 6. 返回请求区间
        if start is not None:
            df = df.loc[start:end]
        return df if fields is None else df[fields]