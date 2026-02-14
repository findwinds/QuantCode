# strategies/range_break_strategy.py
from typing import Dict, Any, Optional
import pandas as pd
import numpy as np
from enum import Enum
import logging
from datetime import datetime

from models.order import Order, OrderType, OrderSide
from .strategy import BaseStrategy


class TrendDirection(Enum):
    """趋势方向枚举"""
    UP = 1      # 上升趋势
    DOWN = -1   # 下降趋势
    SIDEWAYS = 0 # 震荡


class RangeBreakStrategy(BaseStrategy):
    """
    震荡区间突破策略
    
    核心逻辑:
    1. 识别震荡区间(上界和下界)
    2. 当价格突破区间后,等待回调/反弹
    3. 回调不破前低/反弹不破前高时入场
    4. 使用回调/反弹点作为移动止损
    """
    
    def __init__(self, broker=None, params: Dict[str, Any] = None):
        """
        初始化策略
        
        Args:
            broker: 交易代理实例
            params: 策略参数
                - lookback_period: 震荡区间回溯周期(默认20)
                - range_threshold: 震荡区间阈值(默认0.05, 即5%)
                - min_range_bars: 最小区间K线数量(默认5)
                - max_range_bars: 最大区间K线数量(默认30)
                - volume_ratio: 突破成交量倍数(默认1.5)
                - use_atr_stop: 是否使用ATR止损(默认False)
                - atr_period: ATR周期(默认14)
                - atr_multiplier: ATR乘数(默认2)
                - debug: 是否打印调试信息(默认False)
        """
        super().__init__(broker, params)
        
        # 默认参数
        self.default_params = {
            'lookback_period': 20,
            'range_threshold': 0.05,
            'min_range_bars': 5,
            'max_range_bars': 30,
            'volume_ratio': 1.5,
            'use_atr_stop': False,
            'atr_period': 14,
            'atr_multiplier': 2,
            'debug': False  # 添加调试开关
        }
        
        # 合并参数
        for key, value in self.default_params.items():
            if key not in self.params:
                self.params[key] = value
        
        # 状态变量
        self.data_buffer = {}  # 存储各symbol的数据缓存
        self.positions = {}     # 持仓状态
        self.range_info = {}    # 震荡区间信息
        self.breakout_info = {} # 突破信息
        self.stop_orders = {}   # 止损订单ID
        
        # 设置日志
        self.logger = logging.getLogger(__name__)
        if self.params['debug']:
            self.logger.setLevel(logging.DEBUG)
            # 添加控制台处理器如果没有的话
            if not self.logger.handlers:
                ch = logging.StreamHandler()
                ch.setLevel(logging.DEBUG)
                formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                ch.setFormatter(formatter)
                self.logger.addHandler(ch)
        
    def on_bar(self, symbol: str, data: pd.Series):
        """
        每个Bar触发一次
        
        Args:
            symbol: 交易对
            data: K线数据(包含open, high, low, close, volume)
        """
        # 获取当前时间
        current_time = data.get('datetime', data.get('date', data.get('time', 'Unknown')))
        
        # 初始化数据缓存
        if symbol not in self.data_buffer:
            self.data_buffer[symbol] = []
            if self.params['debug']:
                self.logger.debug(f"[{symbol}] 初始化数据缓存")
        
        # 更新数据缓存
        self.data_buffer[symbol].append(data)
        
        # 保留足够的数据用于计算
        max_keep = max(self.params['lookback_period'], 
                      self.params['max_range_bars']) * 2
        if len(self.data_buffer[symbol]) > max_keep:
            self.data_buffer[symbol].pop(0)
        
        # 检查是否有足够数据进行计算
        if len(self.data_buffer[symbol]) < self.params['lookback_period']:
            if self.params['debug'] and len(self.data_buffer[symbol]) % 5 == 0:
                self.logger.debug(f"[{symbol}] 数据不足: {len(self.data_buffer[symbol])}/{self.params['lookback_period']}")
            return
        
        # 获取当前持仓状态
        position = self._get_position(symbol)
        
        if self.params['debug']:
            close_price = data.get('close', 0)
            high_price = data.get('high', 0)
            low_price = data.get('low', 0)
            volume = data.get('volume', 0)
            self.logger.debug(f"[{symbol}] {current_time} - 价格: C={close_price:.2f} H={high_price:.2f} L={low_price:.2f} V={volume:.0f} 持仓:{position}")
        
        # 如果没有持仓,寻找入场机会
        if position == 0:
            self._check_entry(symbol, current_time)
        else:
            # 检查是否触发移动止损
            self._check_trailing_stop(symbol, current_time)
    
    def _check_entry(self, symbol: str, current_time=None):
        """
        检查入场信号
        """
        # 获取数据
        data_list = self.data_buffer[symbol]
        current_bar = data_list[-1]
        
        # 1. 识别震荡区间
        range_info = self._identify_range(symbol)
        if not range_info:
            if self.params['debug']:
                self.logger.debug(f"[{symbol}] {current_time} - 未识别到震荡区间")
            return
            
        upper_bound = range_info['upper_bound']
        lower_bound = range_info['lower_bound']
        
        if self.params['debug']:
            self.logger.debug(f"[{symbol}] {current_time} - 震荡区间: 上界={upper_bound:.2f} 下界={lower_bound:.2f} 宽度={range_info['range_width']:.2%}")
        
        # 2. 检查是否突破
        breakout_info = self._check_breakout(symbol, upper_bound, lower_bound, current_time)
        if not breakout_info:
            if self.params['debug']:
                # 检查价格是否接近边界
                current_high = current_bar['high']
                current_low = current_bar['low']
                if current_high > upper_bound:
                    self.logger.debug(f"[{symbol}] {current_time} - 价格突破上界 {current_high:.2f} > {upper_bound:.2f}，但成交量未确认")
                elif current_low < lower_bound:
                    self.logger.debug(f"[{symbol}] {current_time} - 价格突破下界 {current_low:.2f} < {lower_bound:.2f}，但成交量未确认")
            return
            
        direction = breakout_info['direction']
        breakout_bar = breakout_info['breakout_bar']
        
        if self.params['debug']:
            direction_str = "向上" if direction == TrendDirection.UP else "向下"
            self.logger.debug(f"[{symbol}] {current_time} - 检测到{direction_str}突破！突破价格={breakout_info['breakout_price']:.2f}")
        
        # 3. 等待回调/反弹
        if direction == TrendDirection.UP:
            # 向上突破,等待回调
            self._check_pullback_entry(symbol, breakout_info, direction, current_time)
        elif direction == TrendDirection.DOWN:
            # 向下突破,等待反弹
            self._check_rally_entry(symbol, breakout_info, direction, current_time)
    
    def _identify_range(self, symbol: str) -> Optional[Dict]:
        """
        识别震荡区间
        使用价格通道方法识别震荡区间
        """
        data_list = self.data_buffer[symbol]
        lookback = self.params['lookback_period']
        
        # 获取最近的数据用于区间识别
        recent_data = data_list[-lookback:]
        
        # 计算最高点和最低点
        highs = [bar['high'] for bar in recent_data]
        lows = [bar['low'] for bar in recent_data]
        
        max_high = max(highs)
        min_low = min(lows)
        
        # 计算区间幅度
        range_width = (max_high - min_low) / min_low if min_low > 0 else 0
        
        # 检查是否符合震荡区间条件
        if range_width > self.params['range_threshold']:
            # 幅度过大,可能不是震荡
            return None
            
        # 检查价格是否多次触及边界
        touch_high_count = sum(1 for bar in recent_data 
                              if bar['high'] >= max_high * 0.99)
        touch_low_count = sum(1 for bar in recent_data 
                             if bar['low'] <= min_low * 1.01)
        
        if touch_high_count < 2 or touch_low_count < 2:
            # 触及边界次数不足
            return None
            
        return {
            'upper_bound': max_high,
            'lower_bound': min_low,
            'range_width': range_width,
            'touch_high_count': touch_high_count,
            'touch_low_count': touch_low_count,
            'identified_at': len(data_list) - 1
        }
    
    def _check_breakout(self, symbol: str, upper_bound: float, 
                        lower_bound: float, current_time=None) -> Optional[Dict]:
        """
        检查是否突破区间
        """
        data_list = self.data_buffer[symbol]
        current_bar = data_list[-1]
        prev_bar = data_list[-2] if len(data_list) > 1 else None
        
        if prev_bar is None:
            return None
        
        # 检查向上突破
        if (prev_bar['high'] <= upper_bound and 
            current_bar['high'] > upper_bound):
            
            # 成交量确认
            if self._check_volume_confirm(symbol, current_bar):
                return {
                    'direction': TrendDirection.UP,
                    'breakout_bar': current_bar,
                    'breakout_price': current_bar['high'],
                    'breakout_index': len(data_list) - 1
                }
            else:
                if self.params['debug']:
                    avg_volume = np.mean([b['volume'] for b in data_list[-10:]])
                    self.logger.debug(f"[{symbol}] {current_time} - 向上突破但成交量不足: {current_bar['volume']:.0f} < {avg_volume * self.params['volume_ratio']:.0f}")
        
        # 检查向下突破
        if (prev_bar['low'] >= lower_bound and 
            current_bar['low'] < lower_bound):
            
            if self._check_volume_confirm(symbol, current_bar):
                return {
                    'direction': TrendDirection.DOWN,
                    'breakout_bar': current_bar,
                    'breakout_price': current_bar['low'],
                    'breakout_index': len(data_list) - 1
                }
            else:
                if self.params['debug']:
                    avg_volume = np.mean([b['volume'] for b in data_list[-10:]])
                    self.logger.debug(f"[{symbol}] {current_time} - 向下突破但成交量不足: {current_bar['volume']:.0f} < {avg_volume * self.params['volume_ratio']:.0f}")
        
        return None
    
    def _check_volume_confirm(self, symbol: str, bar: pd.Series) -> bool:
        """
        成交量确认突破
        """
        if 'volume' not in bar:
            return True
            
        data_list = self.data_buffer[symbol]
        avg_volume = np.mean([b['volume'] for b in data_list[-10:]])
        
        return bar['volume'] > avg_volume * self.params['volume_ratio']
    
    def _check_pullback_entry(self, symbol: str, breakout_info: Dict, 
                              direction: TrendDirection, current_time=None):
        """
        检查回调入场(向上突破后)
        """
        data_list = self.data_buffer[symbol]
        current_bar = data_list[-1]
        breakout_index = breakout_info['breakout_index']
        
        # 获取突破后的数据
        post_breakout_data = data_list[breakout_index+1:]
        
        if len(post_breakout_data) < 2:
            if self.params['debug']:
                self.logger.debug(f"[{symbol}] {current_time} - 向上突破后等待回调中... (已等待{len(post_breakout_data)}根K线)")
            return
        
        # 寻找突破后的最低点(回调低点)
        pullback_low = min([bar['low'] for bar in post_breakout_data[:-1]])
        pullback_bars = [bar for bar in post_breakout_data[:-1] 
                        if bar['low'] == pullback_low]
        if not pullback_bars:
            return
        pullback_bar = pullback_bars[-1]
        
        if self.params['debug']:
            self.logger.debug(f"[{symbol}] {current_time} - 向上突破后回调低点: {pullback_low:.2f}")
        
        # 检查当前价格是否突破回调低点后的新高
        if current_bar['high'] > pullback_bar['high']:
            if self.params['debug']:
                self.logger.debug(f"[{symbol}] {current_time} - 回调结束，准备入场! 当前高:{current_bar['high']:.2f} > 回调高:{pullback_bar['high']:.2f}")
            
            # 回调结束,准备入场
            self._place_entry_order(
                symbol=symbol,
                direction=direction,
                entry_price=current_bar['high'],
                stop_price=pullback_low,  # 止损设在回调低点
                breakout_info=breakout_info,
                pullback_info={
                    'price': pullback_low,
                    'bar': pullback_bar
                }
            )
        else:
            if self.params['debug']:
                self.logger.debug(f"[{symbol}] {current_time} - 仍在回调中... 当前高:{current_bar['high']:.2f} <= 回调高:{pullback_bar['high']:.2f}")
    
    def _check_rally_entry(self, symbol: str, breakout_info: Dict, 
                           direction: TrendDirection, current_time=None):
        """
        检查反弹入场(向下突破后)
        """
        data_list = self.data_buffer[symbol]
        current_bar = data_list[-1]
        breakout_index = breakout_info['breakout_index']
        
        # 获取突破后的数据
        post_breakout_data = data_list[breakout_index+1:]
        
        if len(post_breakout_data) < 2:
            if self.params['debug']:
                self.logger.debug(f"[{symbol}] {current_time} - 向下突破后等待反弹中... (已等待{len(post_breakout_data)}根K线)")
            return
        
        # 寻找突破后的最高点(反弹高点)
        rally_high = max([bar['high'] for bar in post_breakout_data[:-1]])
        rally_bars = [bar for bar in post_breakout_data[:-1] 
                     if bar['high'] == rally_high]
        if not rally_bars:
            return
        rally_bar = rally_bars[-1]
        
        if self.params['debug']:
            self.logger.debug(f"[{symbol}] {current_time} - 向下突破后反弹高点: {rally_high:.2f}")
        
        # 检查当前价格是否突破反弹高点后的新低
        if current_bar['low'] < rally_bar['low']:
            if self.params['debug']:
                self.logger.debug(f"[{symbol}] {current_time} - 反弹结束，准备入场! 当前低:{current_bar['low']:.2f} < 反弹低:{rally_bar['low']:.2f}")
            
            # 反弹结束,准备入场
            self._place_entry_order(
                symbol=symbol,
                direction=direction,
                entry_price=current_bar['low'],
                stop_price=rally_high,  # 止损设在反弹高点
                breakout_info=breakout_info,
                pullback_info={
                    'price': rally_high,
                    'bar': rally_bar
                }
            )
        else:
            if self.params['debug']:
                self.logger.debug(f"[{symbol}] {current_time} - 仍在反弹中... 当前低:{current_bar['low']:.2f} >= 反弹低:{rally_bar['low']:.2f}")
    
    def _place_entry_order(self, symbol: str, direction: TrendDirection,
                          entry_price: float, stop_price: float,
                          breakout_info: Dict, pullback_info: Dict):
        """
        下入场单
        """
        # 计算订单数量(这里需要根据你的资金管理来定)
        quantity = self._calculate_position_size(symbol, entry_price, stop_price)
        
        if quantity <= 0:
            if self.params['debug']:
                self.logger.debug(f"[{symbol}] 计算仓位失败: quantity={quantity}")
            return
        
        # 确定订单方向
        if direction == TrendDirection.UP:
            order_side = OrderSide.BUY
            action = "买入"
        else:
            order_side = OrderSide.SELL
            action = "卖出"
        
        if self.params['debug']:
            self.logger.debug(f"[{symbol}] ===== 准备入场 =====")
            self.logger.debug(f"[{symbol}] 方向: {action}")
            self.logger.debug(f"[{symbol}] 入场价: {entry_price:.2f}")
            self.logger.debug(f"[{symbol}] 止损价: {stop_price:.2f}")
            self.logger.debug(f"[{symbol}] 数量: {quantity}")
        
        # 创建入场订单
        entry_order = Order(
            symbol=symbol,
            type=OrderType.MARKET,  # 使用市价单确保成交
            side=order_side,
            quantity=quantity
        )
        
        # 提交订单
        if self.broker:
            order_id = self.broker.place_order(entry_order)
            
            # 保存订单信息用于后续管理
            self.positions[symbol] = {
                'entry_price': entry_price,
                'initial_stop': stop_price,
                'current_stop': stop_price,
                'direction': direction,
                'quantity': quantity,
                'breakout_info': breakout_info,
                'pullback_info': pullback_info,
                'entry_order_id': order_id
            }
            
            # 设置初始止损单
            self._set_stop_loss(symbol, stop_price)
            
            if self.params['debug']:
                self.logger.debug(f"[{symbol}] 订单已提交, order_id: {order_id}")
    
    def _set_stop_loss(self, symbol: str, stop_price: float):
        """
        设置止损单
        """
        if not self.broker:
            return
            
        position = self.positions.get(symbol)
        if not position:
            return
        
        # 确定止损方向
        if position['direction'] == TrendDirection.UP:
            stop_side = OrderSide.SELL
            action = "卖出止损"
        else:
            stop_side = OrderSide.BUY
            action = "买入止损"
        
        if self.params['debug']:
            self.logger.debug(f"[{symbol}] 设置{action}单: {stop_price:.2f}")
        
        # 创建止损订单
        stop_order = Order(
            symbol=symbol,
            type=OrderType.STOP,
            side=stop_side,
            quantity=position['quantity'],
            price=stop_price  # 止损价格
        )
        
        order_id = self.broker.place_order(stop_order)
        self.stop_orders[symbol] = order_id
    
    def _check_trailing_stop(self, symbol: str, current_time=None):
        """
        检查移动止损
        每当形成新的回调/反弹低点/高点时,移动止损
        """
        position = self.positions.get(symbol)
        if not position:
            return
        
        data_list = self.data_buffer[symbol]
        current_bar = data_list[-1]
        
        if position['direction'] == TrendDirection.UP:
            # 多头持仓:寻找更高的回调低点
            recent_lows = [bar['low'] for bar in data_list[-5:]]
            new_low = min(recent_lows)
            
            # 如果形成更高的回调低点,移动止损
            if new_low > position['current_stop']:
                if self.params['debug']:
                    self.logger.debug(f"[{symbol}] {current_time} - 移动止损: {position['current_stop']:.2f} -> {new_low:.2f}")
                
                # 取消旧的止损单
                if symbol in self.stop_orders:
                    self.broker.cancel_order(self.stop_orders[symbol])
                
                # 设置新的止损单
                self._set_stop_loss(symbol, new_low)
                position['current_stop'] = new_low
                
        else:
            # 空头持仓:寻找更低的反弹高点
            recent_highs = [bar['high'] for bar in data_list[-5:]]
            new_high = max(recent_highs)
            
            # 如果形成更低的反弹高点,移动止损
            if new_high < position['current_stop']:
                if self.params['debug']:
                    self.logger.debug(f"[{symbol}] {current_time} - 移动止损: {position['current_stop']:.2f} -> {new_high:.2f}")
                
                if symbol in self.stop_orders:
                    self.broker.cancel_order(self.stop_orders[symbol])
                
                self._set_stop_loss(symbol, new_high)
                position['current_stop'] = new_high
    
    def _calculate_position_size(self, symbol: str, entry_price: float, 
                                 stop_price: float) -> float:
        """
        计算仓位大小
        基于固定风险比例
        """
        # 获取账户信息
        if not self.broker:
            return 0.1  # 默认值
        
        account = self.broker.get_account()
        risk_per_trade = 0.02  # 每笔交易风险2%账户余额
        
        # 计算风险金额
        risk_amount = account.balance * risk_per_trade
        
        # 计算每单位风险
        price_risk = abs(entry_price - stop_price)
        
        if price_risk == 0:
            return 0
        
        # 计算仓位大小
        quantity = risk_amount / price_risk
        
        # 考虑最小交易单位
        min_quantity = 0.01  # 根据具体交易对调整
        quantity = max(min_quantity, round(quantity, 2))
        
        return quantity
    
    def _get_position(self, symbol: str) -> float:
        """
        获取当前持仓数量
        """
        if not self.broker:
            return 0
        
        positions = self.broker.get_positions()
        for pos in positions:
            if pos.symbol == symbol:
                return pos.quantity
        
        return 0
    
    def on_order(self, order: Order):
        """
        订单状态变化回调
        """
        if self.params['debug']:
            self.logger.debug(f"[{order.symbol}] 订单状态更新: {order.order_id} - {order.status}")
        
        # 检查是否止损单被触发
        if order.type == OrderType.STOP and order.status == 'filled':
            if self.params['debug']:
                self.logger.debug(f"[{order.symbol}] 止损单成交，清除持仓记录")
            
            # 清除持仓记录
            if order.symbol in self.positions:
                del self.positions[order.symbol]
            if order.symbol in self.stop_orders:
                del self.stop_orders[order.symbol]
    
    def on_trade(self, trade):
        """
        成交回调
        """
        if self.params['debug']:
            self.logger.debug(f"[{trade.symbol}] 成交: {trade.quantity} @ {trade.price}")
    
    def reset(self):
        """
        重置策略状态
        """
        self.data_buffer.clear()
        self.positions.clear()
        self.range_info.clear()
        self.breakout_info.clear()
        self.stop_orders.clear()
        if self.params['debug']:
            self.logger.debug("策略状态已重置")