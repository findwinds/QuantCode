# src/strategy/futures_dual_ma.py
"""
期货专用的双均线策略 - 修正版
"""
import logging
from typing import Dict, Any, Optional
import pandas as pd
from .strategy import BaseStrategy
from models.order import Order, OrderType, OrderSide

class FuturesDualMaStrategy(BaseStrategy):
    """期货双均线趋势跟随策略"""
    
    def __init__(self, broker=None, params: Optional[Dict[str, Any]] = None):
        super().__init__(broker, params)
        
        # 设置默认参数（针对期货）
        self.default_params = {
            'fast': 10,
            'slow': 30,
            'position': 1,           # 每次交易手数（必须是正整数）
            'data_window': 100,
            'contract_multiplier': 10,  # 螺纹钢是10吨/手
            'margin_ratio': 0.10,       # 保证金比例10%
            'allow_short': True,        # 允许做空
        }
        
        if params:
            self.default_params.update(params)
        self.params = self.default_params
        
        # 确保position是正整数
        self.params['position'] = max(1, int(self.params['position']))
        
        # 策略状态
        self.data_cache = {}
        self.current_position = {}  # symbol -> 当前持仓手数（正数=多单，负数=空单）
        self.last_signal = {}
        self.entry_prices = {}      # symbol -> 开仓均价

        self.logger = logging.getLogger(__name__)
    
    def on_bar(self, symbol: str, bar: pd.Series):
        """每个Bar触发一次"""
        self._update_data_cache(symbol, bar)
        
        df = self._get_historical_data(symbol)
        if df is None or len(df) < self.params['slow']:
            return
        
        # 生成信号
        signal = self.generate_signal(df)
        
        if signal == 0:
            return
        
        # 执行交易逻辑
        self.execute_trading_logic(symbol, bar['close'], signal)
        
        # 记录信号
        self.last_signal[symbol] = signal
    
    def generate_signal(self, df: pd.DataFrame) -> int:
        """生成交易信号"""
        if len(df) < self.params['slow']:
            return 0
        
        # 计算均线
        fast_ma = df['close'].rolling(self.params['fast']).mean()
        slow_ma = df['close'].rolling(self.params['slow']).mean()
        
        # 获取最新值
        if len(fast_ma) < 2 or len(slow_ma) < 2:
            return 0
        
        current_fast = fast_ma.iloc[-1]
        current_slow = slow_ma.iloc[-1]
        prev_fast = fast_ma.iloc[-2]
        prev_slow = slow_ma.iloc[-2]
        
        # 金叉：上穿
        if prev_fast <= prev_slow and current_fast > current_slow:
            return 1  # 买入信号
        
        # 死叉：下穿
        elif prev_fast >= prev_slow and current_fast < current_slow:
            return -1  # 卖出信号
        
        return 0
    
    def execute_trading_logic(self, symbol: str, price: float, signal: int):
        """执行交易逻辑"""
        if not self.broker:
            return
        
        # 获取当前持仓
        current_pos = self.current_position.get(symbol, 0)
        
        # 根据信号决定操作
        if signal == 1:  # 买入信号
            if current_pos <= 0:  # 空仓或持有空单
                # 平空（如果有空单）并开多
                if current_pos < 0:
                    self.close_position(symbol, price)
                self.open_long(symbol, price)
        
        elif signal == -1:  # 卖出信号
            if self.params['allow_short']:
                if current_pos >= 0:  # 空仓或持有多单
                    # 平多（如果有多单）并开空
                    if current_pos > 0:
                        self.close_position(symbol, price)
                    self.open_short(symbol, price)
    
    def open_long(self, symbol: str, price: float):
        """开多单"""
        position = self.params['position']
        
        # 检查保证金
        if not self.check_margin(symbol, position, price):
            self.logger.debug(f"[{symbol}] 保证金不足，无法开多单")
            return
        
        # 下单
        order = Order(
            symbol=symbol,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=position,
            price=price
        )
        
        order_id = self.broker.place_order(order)
        
        # 更新持仓
        self.current_position[symbol] = position
        self.entry_prices[symbol] = price
        
        self.logger.debug(f"[{symbol}] 开多单: {position}手 @ {price:.2f}, 订单ID={order_id}")
    
    def open_short(self, symbol: str, price: float):
        """开空单"""
        position = self.params['position']
        
        # 检查保证金
        if not self.check_margin(symbol, position, price):
            self.logger.debug(f"[{symbol}] 保证金不足，无法开空单")
            return
        
        # 下单
        order = Order(
            symbol=symbol,
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=position,
            price=price
        )
        
        order_id = self.broker.place_order(order)
        
        # 更新持仓（空单为负数）
        self.current_position[symbol] = -position
        self.entry_prices[symbol] = price
        
        self.logger.debug(f"[{symbol}] 开空单: {position}手 @ {price:.2f}, 订单ID={order_id}")
    
    def close_position(self, symbol: str, price: float):
        """平仓"""
        current_pos = self.current_position.get(symbol, 0)
        
        if current_pos == 0:
            return
        
        # 决定平仓方向
        if current_pos > 0:  # 平多单
            side = OrderSide.SELL
            action = "平多单"
        else:  # 平空单
            side = OrderSide.BUY
            action = "平空单"
        
        # 下单
        order = Order(
            symbol=symbol,
            side=side,
            order_type=OrderType.MARKET,
            quantity=abs(current_pos),
            price=price
        )
        
        order_id = self.broker.place_order(order)
        
        # 计算盈亏
        entry_price = self.entry_prices.get(symbol, price)
        pnl = self.calculate_pnl(current_pos, entry_price, price)
        
        # 更新持仓
        self.current_position[symbol] = 0
        
        self.logger.debug(f"[{symbol}] {action}: {abs(current_pos)}手 @ {price:.2f}, "
                         f"开仓价={entry_price:.2f}, 盈亏={pnl:.2f}, 订单ID={order_id}")
    
    def check_margin(self, symbol: str, position: int, price: float) -> bool:
        """检查保证金是否足够"""
        if not self.broker:
            return False
        
        try:
            account_info = self.broker.get_account_info()
            available_cash = getattr(account_info, 'available_cash', 0)
        except:
            available_cash = 0
        
        # 计算所需保证金
        contract_value = price * self.params['contract_multiplier'] * position
        required_margin = contract_value * self.params['margin_ratio']
        
        return required_margin <= available_cash
    
    def calculate_pnl(self, position: int, entry_price: float, exit_price: float) -> float:
        """计算盈亏"""
        contract_multiplier = self.params['contract_multiplier']
        
        if position > 0:  # 多单
            pnl = (exit_price - entry_price) * abs(position) * contract_multiplier
        elif position < 0:  # 空单
            pnl = (entry_price - exit_price) * abs(position) * contract_multiplier
        else:
            pnl = 0
        
        return pnl
    
    def _update_data_cache(self, symbol: str, bar: pd.Series):
        """更新数据缓存"""
        if symbol not in self.data_cache:
            self.data_cache[symbol] = pd.DataFrame()
        
        bar_df = pd.DataFrame([bar.to_dict()], index=[bar.name])
        self.data_cache[symbol] = pd.concat([self.data_cache[symbol], bar_df])
        self.data_cache[symbol] = self.data_cache[symbol][~self.data_cache[symbol].index.duplicated(keep='last')]
        
        if len(self.data_cache[symbol]) > self.params['data_window']:
            self.data_cache[symbol] = self.data_cache[symbol].iloc[-self.params['data_window']:]
    
    def _get_historical_data(self, symbol: str):
        """获取历史数据"""
        if symbol not in self.data_cache:
            return None
        return self.data_cache[symbol].copy()
    
    def get_strategy_state(self) -> Dict:
        """获取策略状态"""
        return {
            'parameters': self.params.copy(),
            'current_positions': self.current_position.copy(),
            'last_signals': self.last_signal.copy(),
            'entry_prices': self.entry_prices.copy(),
        }