# src/strategy/dual_ma.py
from typing import Dict, Any, Optional
import pandas as pd
from .strategy import BaseStrategy

class DualMaStrategy(BaseStrategy):
    """双均线趋势跟随策略"""
    
    def __init__(self, broker=None, params: Optional[Dict[str, Any]] = None):
        """
        初始化双均线策略
        
        Args:
            broker: 交易代理实例
            params: 策略参数
        """
        # 调用父类的初始化
        super().__init__(broker, params)
        
        # 设置默认参数
        self.default_params = {
            'fast': 20,
            'slow': 60,
            'position_ratio': 1.0,
            'data_window': 100
        }
        
        # 更新用户参数
        if params:
            self.default_params.update(params)
        self.params = self.default_params
        
        # 策略状态 - 监控所有传入的品种
        self.data_cache = {}        # symbol -> DataFrame
        self.current_targets = {}   # symbol -> float
        self.last_signal = {}       # symbol -> int
        
    def on_bar(self, symbol: str, bar: pd.Series):
        """
        每个Bar触发一次
        """
        # 不再检查symbols列表，直接处理所有传入的品种
        self._update_data_cache(symbol, bar)
        
        # 获取足够的历史数据
        df = self._get_historical_data(symbol)
        if df is None or len(df) < self.params['slow']:
            return
        
        # 使用核心逻辑生成信号
        signal_df = self.create_signal(df)
        
        if len(signal_df) == 0:
            return
        
        # 获取最新的信号
        latest_row = signal_df.iloc[-1]
        current_signal = latest_row['signal']
        target_position = latest_row['target'] * self.params['position_ratio']
        
        # 记录当前目标仓位
        self.current_targets[symbol] = target_position
        
        # 检查是否需要交易
        self._execute_trading(symbol, bar['close'], target_position, current_signal)
        
        # 更新上次信号
        self.last_signal[symbol] = current_signal
    
    # 你的核心逻辑保持不变
    def create_signal(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        输入标准 OHLCV(df) -> 返回同表 + signal 列(+1/-1/0)
        """
        df = df.copy()
        df['signal'] = 0.0
        
        # 计算均线
        df['fast_ma'] = df['close'].rolling(self.params['fast']).mean()
        df['slow_ma'] = df['close'].rolling(self.params['slow']).mean()
        
        # 金叉死叉判断
        long_cross = (df['fast_ma'] > df['slow_ma']) & (df['fast_ma'].shift(1) <= df['slow_ma'].shift(1))
        short_cross = (df['fast_ma'] < df['slow_ma']) & (df['fast_ma'].shift(1) >= df['slow_ma'].shift(1))
        
        # 分配信号
        df.loc[long_cross, 'signal'] = 1.0
        df.loc[short_cross, 'signal'] = -1.0
        
        # 目标敞口
        df['target'] = 0.0
        df.loc[df['signal'] == 1, 'target'] = 1.0   # 满仓多
        df.loc[df['signal'] == -1, 'target'] = -1.0  # 满仓空
        
        return df[['open', 'high', 'low', 'close', 'volume', 'signal', 'target', 'fast_ma', 'slow_ma']]
    
    def _update_data_cache(self, symbol: str, bar: pd.Series):
        """更新数据缓存"""
        if symbol not in self.data_cache:
            self.data_cache[symbol] = pd.DataFrame()
        
        # 将当前bar转换为DataFrame的一行
        bar_df = pd.DataFrame([bar.to_dict()], index=[bar.name])
        
        # 追加数据，去重
        self.data_cache[symbol] = pd.concat([self.data_cache[symbol], bar_df])
        self.data_cache[symbol] = self.data_cache[symbol][~self.data_cache[symbol].index.duplicated(keep='last')]
        
        # 限制数据窗口大小
        if len(self.data_cache[symbol]) > self.params['data_window']:
            self.data_cache[symbol] = self.data_cache[symbol].iloc[-self.params['data_window']:]
    
    def _get_historical_data(self, symbol: str):
        """获取历史数据"""
        if symbol not in self.data_cache:
            return None
        return self.data_cache[symbol].copy()
    
    def _execute_trading(self, symbol: str, current_price: float, 
                        target_position: float, current_signal: int):
        """执行交易"""
        if not self.broker:
            return
        
        # 获取当前持仓
        current_pos = self._get_current_position(symbol)
        
        # 获取账户信息
        try:
            account_info = self.broker.get_account_info()
        except:
            account_info = None
        
        if account_info is None:
            return
        
        # 计算需要调整的仓位
        position_diff = target_position - current_pos
        
        # 如果仓位变化很小，不交易
        if abs(position_diff) < 0.001:
            return
        
        # 根据仓位差执行交易
        if position_diff > 0:  # 需要买入
            self._place_buy_order(symbol, position_diff, current_price, account_info)
        else:  # 需要卖出
            self._place_sell_order(symbol, abs(position_diff), current_price, account_info)
    
    def _get_current_position(self, symbol: str) -> float:
        """获取当前持仓"""
        if not self.broker:
            return 0.0
        
        try:
            positions = self.broker.get_positions()
            return positions.get(symbol, 0.0)
        except:
            return 0.0
    
    def _place_buy_order(self, symbol: str, quantity: float, 
                        price: float, account_info):
        """下买单"""
        # 计算可用的资金能买多少
        available_cash = getattr(account_info, 'available_cash', 0)
        max_can_buy = available_cash / price if price > 0 else 0
        
        # 确保不超过可用资金
        qty_to_buy = min(quantity, max_can_buy)
        
        if qty_to_buy > 0:
            # 导入Order相关类
            from models.order import Order, OrderType, OrderSide
            
            order = Order(
                symbol=symbol,
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=qty_to_buy,
                price=price
            )
            
            order_id = self.broker.place_order(order)
            print(f"[{symbol}] 买入信号: 数量={qty_to_buy:.2f}, 价格={price:.2f}, 订单ID={order_id}")
    
    def _place_sell_order(self, symbol: str, quantity: float, 
                         price: float, account_info):
        """下卖单"""
        # 检查是否有足够持仓可卖
        current_pos = self._get_current_position(symbol)
        qty_to_sell = min(quantity, current_pos)
        
        if qty_to_sell > 0:
            # 导入Order相关类
            from models.order import Order, OrderType, OrderSide
            
            order = Order(
                symbol=symbol,
                side=OrderSide.SELL,
                order_type=OrderType.MARKET,
                quantity=qty_to_sell,
                price=price
            )
            
            order_id = self.broker.place_order(order)
            print(f"[{symbol}] 卖出信号: 数量={qty_to_sell:.2f}, 价格={price:.2f}, 订单ID={order_id}")
    
    def get_current_signal(self, symbol: str) -> Dict:
        """获取当前信号状态"""
        if symbol not in self.last_signal:
            return {'signal': 0, 'target': 0}
        
        return {
            'signal': self.last_signal.get(symbol, 0),
            'target': self.current_targets.get(symbol, 0),
            'data_length': len(self.data_cache.get(symbol, []))
        }
    
    def get_strategy_state(self) -> Dict:
        """获取策略状态"""
        return {
            'parameters': self.params.copy(),
            'monitored_symbols': list(self.data_cache.keys()),
            'current_targets': self.current_targets.copy(),
            'last_signals': self.last_signal.copy(),
            'data_cache_size': {sym: len(df) for sym, df in self.data_cache.items()}
        }