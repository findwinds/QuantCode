# src/data/feed.py
from abc import ABC, abstractmethod
import pandas as pd


class DataFeed(ABC):
    """
    数据获取器抽象基类（ABC）
    任何数据源（AKShare、CSV、交易所 API…）都必须继承此类，
    并实现 get_kline 方法，保证“出口”完全一致。
    """

    @abstractmethod
    def get_kline(self,
                  symbol: str,
                  freq: str,
                  start: str,
                  end: str,
                  fields: list = None) -> pd.DataFrame:
        """
        统一查询接口：获取指定品种、周期、时间范围的 K 线数据

        参数说明
        --------
        symbol : str
            交易标的代码，例如 'BTCUSDT'、'SH600519'、'AAPL'。
        freq : str
            K 线周期，常见取值：
                '1d'  – 日 K
                '1h'  – 小时 K
                '30m' – 30 分钟 K
                '15m' – 15 分钟 K
                '5m'  – 5 分钟 K
                '1m'  – 1 分钟 K
        start : str
            起始日期，含当日，格式 'YYYY-MM-DD'，如 '2023-01-01'。
        end : str
            结束日期，含当日，格式 'YYYY-MM-DD'，如 '2023-12-31'。
        fields : list, optional (默认 None)
            只返回需要的列，例如 ['close', 'volume']。
            传 None 时返回全部 OHLCV 五列。

        返回说明
        --------
        pd.DataFrame
            标准 OHLCV 表格，必须满足：
            1. 列名含 open / high / low / close / volume（volume 为成交量）
            2. 索引为 datetime 类型，且按时间升序排列
            3. 时间段已被 [start, end] 裁剪完毕
        """
        raise NotImplementedError