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
        
        # 判断是否为日线数据
        is_daily = (freq == '1d')
        
        # 转换start和end为时间戳
        start_ts = None
        end_ts = None
        if start:
            start_ts = pd.Timestamp(start)
        if end:
            end_ts = pd.Timestamp(end)
        
        # 1. 缓存命中且日期足够 → 直接读盘
        if cache_file.exists():
            try:
                df_cache = pd.read_csv(cache_file, index_col=0, parse_dates=True)
                
                # 确保索引是datetime类型且已排序
                df_cache.index = pd.to_datetime(df_cache.index)
                df_cache = df_cache.sort_index()
                
                if df_cache.empty:
                    logger.info('[%s %s] 缓存文件为空，重新拉取', symbol, freq)
                elif start is None and end is None:
                    # 没有指定时间范围，直接返回全部缓存
                    logger.info('[%s %s] 完全命中缓存，直接读盘', symbol, freq)
                    return df_cache if fields is None else df_cache[fields]
                elif start is not None and end is not None:
                    # 检查缓存是否包含请求的时间范围
                    cache_start = df_cache.index[0]
                    cache_end = df_cache.index[-1]
                    
                    # 对于分钟数据，我们只比较日期部分
                    if is_daily:
                        logger.info('[%s %s] 缓存范围: %s 到 %s', symbol, freq, 
                                   cache_start.strftime('%Y-%m-%d'), 
                                   cache_end.strftime('%Y-%m-%d'))
                        logger.info('[%s %s] 请求范围: %s 到 %s', symbol, freq, 
                                   start_ts.strftime('%Y-%m-%d'), 
                                   end_ts.strftime('%Y-%m-%d'))
                        
                        # 日线数据：直接比较日期
                        if cache_start <= start_ts and cache_end >= end_ts:
                            logger.info('[%s %s] 区间命中缓存，直接切片', symbol, freq)
                            result = df_cache.loc[start:end]
                            if not result.empty:
                                logger.info('[%s %s] 返回数据条数: %d', symbol, freq, len(result))
                                return result if fields is None else result[fields]
                            else:
                                logger.info('[%s %s] 缓存切片结果为空，重新拉取', symbol, freq)
                        else:
                            logger.info('[%s %s] 缓存范围不足，需要补充数据', symbol, freq)
                            if cache_start > start_ts:
                                logger.info('[%s %s] 缓存开始日期 %s 晚于请求开始日期 %s', 
                                           symbol, freq, cache_start.strftime('%Y-%m-%d'), 
                                           start_ts.strftime('%Y-%m-%d'))
                            if cache_end < end_ts:
                                logger.info('[%s %s] 缓存结束日期 %s 早于请求结束日期 %s', 
                                           symbol, freq, cache_end.strftime('%Y-%m-%d'), 
                                           end_ts.strftime('%Y-%m-%d'))
                    else:
                        # 分钟数据：显示完整时间
                        logger.info('[%s %s] 缓存范围: %s 到 %s', symbol, freq, 
                                   cache_start.strftime('%Y-%m-%d %H:%M:%S'), 
                                   cache_end.strftime('%Y-%m-%d %H:%M:%S'))
                        logger.info('[%s %s] 请求范围: %s 到 %s', symbol, freq, 
                                   start, end)
                        
                        # 分钟数据：只比较日期部分
                        cache_start_date = cache_start.normalize()
                        cache_end_date = cache_end.normalize()
                        start_date = start_ts.normalize()
                        end_date = end_ts.normalize()
                        
                        # 检查缓存是否包含请求的日期范围
                        if cache_start_date <= start_date and cache_end_date >= end_date:
                            logger.info('[%s %s] 区间命中缓存，直接切片', symbol, freq)
                            # 使用日期范围切片，pandas会自动处理时间部分
                            result = df_cache.loc[start:end]
                            if not result.empty:
                                logger.info('[%s %s] 返回数据条数: %d', symbol, freq, len(result))
                                return result if fields is None else result[fields]
                            else:
                                logger.info('[%s %s] 缓存切片结果为空，重新拉取', symbol, freq)
                        else:
                            logger.info('[%s %s] 缓存范围不足，需要补充数据', symbol, freq)
                            if cache_start_date > start_date:
                                logger.info('[%s %s] 缓存开始日期 %s 晚于请求开始日期 %s', 
                                           symbol, freq, cache_start_date.strftime('%Y-%m-%d'), 
                                           start_date.strftime('%Y-%m-%d'))
                            if cache_end_date < end_date:
                                logger.info('[%s %s] 缓存结束日期 %s 早于请求结束日期 %s', 
                                           symbol, freq, cache_end_date.strftime('%Y-%m-%d'), 
                                           end_date.strftime('%Y-%m-%d'))
            except Exception as e:
                logger.warning('[%s %s] 读取缓存失败: %s，重新拉取', symbol, freq, str(e))
                import traceback
                logger.debug(traceback.format_exc())
        else:
            logger.info('[%s %s] 缓存文件不存在，开始拉取远端数据...', symbol, freq)

        # 2. 缓存不足 → 拉远端
        logger.info('[%s %s] 开始拉取远端数据...', symbol, freq)
        try:
            if freq == '1d':
                # 日 K
                df = ak.futures_zh_daily_sina(symbol=symbol)
            else:
                # 分钟 K
                df = ak.futures_zh_minute_sina(symbol=symbol, period=period_map[freq])

            if df.empty:
                logger.error('[%s %s] 远端数据返回为空', symbol, freq)
                return pd.DataFrame()

            logger.info('[%s %s] 远端数据获取成功，原始条数: %d', symbol, freq, len(df))

            # 3. 统一列名 & 索引
            # 检查列名
            date_col = 'date' if 'date' in df.columns else 'datetime'
            df = df[[date_col, 'open', 'high', 'low', 'close', 'volume']].copy()
            df.columns = ['datetime', 'open', 'high', 'low', 'close', 'volume']
            df['datetime'] = pd.to_datetime(df['datetime'])
            
            # 对于日线数据，确保只保留日期部分
            if is_daily:
                df['datetime'] = df['datetime'].dt.normalize()
            
            df = df.set_index('datetime').sort_index()

            # 4. 增量合并（避免重复下载）
            if cache_file.exists():
                try:
                    df_old = pd.read_csv(cache_file, index_col=0, parse_dates=True)
                    df_old.index = pd.to_datetime(df_old.index)
                    
                    # 合并前记录原有数据量
                    old_len = len(df_old)
                    
                    # 合并并去重
                    df = pd.concat([df_old, df]).drop_duplicates().sort_index()
                    
                    new_len = len(df)
                    added = new_len - old_len
                    
                    if added > 0:
                        logger.info('[%s %s] 合并缓存数据，新增 %d 条，总条数: %d', 
                                   symbol, freq, added, new_len)
                    else:
                        logger.info('[%s %s] 缓存数据已是最新，无需更新', symbol, freq)
                        
                except Exception as e:
                    logger.warning('[%s %s] 合并缓存失败: %s，使用新数据', symbol, freq, str(e))

            # 5. 写盘
            logger.info('[%s %s] 写入本地缓存 %s', symbol, freq, cache_file)
            df.to_csv(cache_file)

        except Exception as e:
            logger.error('[%s %s] 拉取远端数据失败: %s', symbol, freq, str(e))
            import traceback
            logger.error(traceback.format_exc())
            
            # 如果拉取失败但缓存存在，尝试使用缓存
            if cache_file.exists():
                logger.info('[%%s %s] 尝试使用现有缓存', symbol, freq)
                try:
                    df_cache = pd.read_csv(cache_file, index_col=0, parse_dates=True)
                    df_cache.index = pd.to_datetime(df_cache.index)
                    df = df_cache.sort_index()
                    logger.info('[%s %s] 使用缓存数据，条数: %d', symbol, freq, len(df))
                except Exception as cache_error:
                    logger.error('[%s %s] 读取缓存也失败: %s', symbol, freq, str(cache_error))
                    return pd.DataFrame()
            else:
                return pd.DataFrame()

        # 6. 返回请求区间
        if start is not None and end is not None:
            try:
                # 对于分钟数据，我们需要确保返回的数据包含完整的日期范围
                # 使用日期范围切片，pandas会自动处理
                result_df = df.loc[start:end]
                
                if result_df.empty:
                    logger.warning('[%s %s] 请求区间 %s 到 %s 无数据', symbol, freq, start, end)
                    logger.info('[%s %s] 数据总范围: %s 到 %s', symbol, freq, 
                               df.index[0].strftime('%Y-%m-%d %H:%M:%S' if not is_daily else '%Y-%m-%d'), 
                               df.index[-1].strftime('%Y-%m-%d %H:%M:%S' if not is_daily else '%Y-%m-%d'))
                    
                    # 尝试返回所有数据供调试
                    if len(df) > 0:
                        logger.info('[%s %s] 返回全部数据供调试，条数: %d', symbol, freq, len(df))
                        return df if fields is None else df[fields]
                else:
                    logger.info('[%s %s] 返回数据条数: %d', symbol, freq, len(result_df))
                
                df = result_df
            except Exception as e:
                logger.error('[%s %s] 切片失败: %s', symbol, freq, str(e))
                return pd.DataFrame()
        
        return df if fields is None else df[fields]