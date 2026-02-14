# strategies/range_break_strategy_v2.py
from typing import Dict, Any, Optional, List, Tuple
import pandas as pd
import numpy as np
from enum import Enum

from models.order import Order, OrderType, OrderSide
from .strategy import BaseStrategy


class RangeState(Enum):
    """震荡区间状态"""
    NO_RANGE = 0        # 未形成震荡
    FORMING = 1         # 震荡形成中
    ACTIVE = 2          # 震荡区间活跃
    BREAKOUT = 3        # 突破中
    WAITING_PULLBACK = 4 # 等待回调/反弹
    READY_TO_ENTER = 5  # 准备入场


class RangeBreakStrategyV2(BaseStrategy):
    """
    震荡区间突破策略V2
    
    核心逻辑:
    1. 震荡开始判断:至少4根K线,形成高低点结构
    2. 区间上下界:反弹高点为上界,回调低点为下界
    3. 震荡结束判断:
       - 完全脱离:高低点都脱离区间
       - 部分突破:突破但未完全脱离,形成入场标识
    4. 交易时机:
       - 完全脱离:等待回调/反弹后,再次突破入场
       - 部分突破:直接等待再次突破入场
    """
    
    def __init__(self, broker=None, params: Dict[str, Any] = None):
        super().__init__(broker, params)
        
        # 默认参数
        self.default_params = {
            'min_range_bars': 4,           # 最小区间K线数量
            'range_deviation': 0.001,       # 区间偏离阈值(0.1%)
            'use_volume_filter': False,      # 是否使用成交量过滤
            'volume_ratio': 1.5,             # 成交量倍数
            'risk_per_trade': 0.02,          # 每笔交易风险比例
            'fixed_position_size': 1,        # 固定仓位大小(最小1手)
            'contract_multiplier': 10,       # 合约乘数(期货每点价值)
            'min_position_size': 1,           # 最小交易手数
            'max_position_size': 100,         # 最大交易手数
        }
        
        # 合并参数
        for key, value in self.default_params.items():
            if key not in self.params:
                self.params[key] = value
        
        # 状态变量
        self.data_buffer = {}           # 各symbol的数据缓存
        self.range_states = {}           # 各symbol的震荡状态
        self.positions = {}              # 持仓信息
        self.stop_orders = {}             # 止损订单ID
        
    def on_bar(self, symbol: str, data: pd.Series):
        """每个Bar触发一次"""
        # 初始化
        self._init_symbol(symbol, data)
        
        # 获取当前状态
        position = self._get_position(symbol)
        
        # 更新数据
        self.data_buffer[symbol].append(data)
        
        # 如果没有持仓,检查入场机会
        if position == 0:
            self._check_range_formation(symbol)
            self._check_entry_signal(symbol)
        else:
            # 更新移动止损
            self._update_trailing_stop(symbol)
    
    def _init_symbol(self, symbol: str, data: pd.Series):
        """初始化symbol相关数据"""
        if symbol not in self.data_buffer:
            self.data_buffer[symbol] = []
            self.range_states[symbol] = {
                'state': RangeState.NO_RANGE,
                'upper_bound': None,
                'lower_bound': None,
                'swing_highs': [],      # 摆动高点列表 [(index, price)]
                'swing_lows': [],        # 摆动低点列表 [(index, price)]
                'breakout_point': None,   # 突破点
                'pullback_point': None,   # 回调/反弹点
                'entry_trigger': None,    # 入场触发点
                'last_high': None,        # 最近高点
                'last_low': None,         # 最近低点
                'bars_since_breakout': 0,
                'last_breakout_direction': None  # 最后一次突破方向
            }
    
    def _check_range_formation(self, symbol: str):
        """
        检查震荡区间形成
        需要至少4根K线形成高低点结构
        """
        state_info = self.range_states[symbol]
        data_list = self.data_buffer[symbol]
        
        if len(data_list) < self.params['min_range_bars']:
            return
        
        # 识别摆动高点和低点
        self._identify_swing_points(symbol)
        
        # 检查是否形成震荡区间
        if len(state_info['swing_highs']) >= 2 and len(state_info['swing_lows']) >= 2:
            # 获取最近的两个高点和两个低点
            recent_highs = sorted(state_info['swing_highs'][-2:], key=lambda x: x[1])
            recent_lows = sorted(state_info['swing_lows'][-2:], key=lambda x: x[1])
            
            # 检查高点是否依次降低(震荡区间特征)
            if len(recent_highs) >= 2 and len(recent_lows) >= 2:
                high1, high2 = recent_highs[-2][1], recent_highs[-1][1]
                low1, low2 = recent_lows[-2][1], recent_lows[-1][1]
                
                # 震荡区间特征:高点没有突破前高,低点没有跌破前低
                if high2 <= high1 and low2 >= low1:
                    state_info['state'] = RangeState.ACTIVE
                    state_info['upper_bound'] = high1  # 区间上界
                    state_info['lower_bound'] = low1   # 区间下界
                    
                    print(f"震荡区间形成 - 上界:{high1:.4f}, 下界:{low1:.4f}")
    
    def _identify_swing_points(self, symbol: str):
        """
        识别摆动高点和低点
        使用相邻K线比较法
        """
        state_info = self.range_states[symbol]
        data_list = self.data_buffer[symbol]
        
        if len(data_list) < 3:
            return
        
        # 检查当前K线是否为摆动高点
        current = data_list[-2]  # 使用前一根K线判断
        prev = data_list[-3] if len(data_list) >= 3 else None
        next_bar = data_list[-1]
        
        # 修复：正确判断prev是否为None
        if prev is not None:
            # 检查是否为摆动高点
            if (isinstance(current, pd.Series) and 
                isinstance(prev, pd.Series) and 
                isinstance(next_bar, pd.Series)):
                
                if (current['high'] > prev['high'] and 
                    current['high'] > next_bar['high']):
                    state_info['swing_highs'].append((len(data_list)-2, float(current['high'])))
                    state_info['last_high'] = float(current['high'])
                
                # 检查是否为摆动低点
                if (current['low'] < prev['low'] and 
                    current['low'] < next_bar['low']):
                    state_info['swing_lows'].append((len(data_list)-2, float(current['low'])))
                    state_info['last_low'] = float(current['low'])
    
    def _check_entry_signal(self, symbol: str):
        """
        检查入场信号
        基于震荡结束判断条件
        """
        state_info = self.range_states[symbol]
        data_list = self.data_buffer[symbol]
        
        if state_info['state'] not in [RangeState.ACTIVE, RangeState.BREAKOUT, 
                                       RangeState.WAITING_PULLBACK]:
            return
        
        current_bar = data_list[-1]
        prev_bar = data_list[-2] if len(data_list) > 1 else None
        
        upper = state_info['upper_bound']
        lower = state_info['lower_bound']
        
        if upper is None or lower is None:
            return
        
        # 3. 震荡结束判断
        # 3.1 完全脱离区间
        if current_bar['low'] < lower and current_bar['high'] > upper:
            # 高低点都脱离区间 - 可能是假突破或趋势反转
            state_info['state'] = RangeState.NO_RANGE
            return
            
        # 3.2 部分突破
        # 向上突破
        if prev_bar is not None:
            if prev_bar['high'] <= upper and current_bar['high'] > upper:
                if current_bar['low'] >= lower:  # 低点仍在区间内
                    self._handle_up_breakout(symbol, current_bar)
            
            # 向下突破
            if prev_bar['low'] >= lower and current_bar['low'] < lower:
                if current_bar['high'] <= upper:  # 高点仍在区间内
                    self._handle_down_breakout(symbol, current_bar)
        
        # 根据当前状态执行相应逻辑
        self._execute_trading_logic(symbol)
    
    def _handle_up_breakout(self, symbol: str, breakout_bar: pd.Series):
        """处理向上突破"""
        state_info = self.range_states[symbol]
        
        state_info['state'] = RangeState.BREAKOUT
        state_info['breakout_point'] = {
            'price': float(breakout_bar['high']),
            'bar': breakout_bar,
            'direction': 'up'
        }
        state_info['last_breakout_direction'] = 'up'
        
        print(f"向上突破 - 价格:{float(breakout_bar['high']):.4f}")
    
    def _handle_down_breakout(self, symbol: str, breakout_bar: pd.Series):
        """处理向下突破"""
        state_info = self.range_states[symbol]
        
        state_info['state'] = RangeState.BREAKOUT
        state_info['breakout_point'] = {
            'price': float(breakout_bar['low']),
            'bar': breakout_bar,
            'direction': 'down'
        }
        state_info['last_breakout_direction'] = 'down'
        
        print(f"向下突破 - 价格:{float(breakout_bar['low']):.4f}")
    
    def _execute_trading_logic(self, symbol: str):
        """
        执行交易逻辑
        处理4.1和4.2两种情况
        """
        state_info = self.range_states[symbol]
        data_list = self.data_buffer[symbol]
        current_bar = data_list[-1]
        
        upper = state_info['upper_bound']
        lower = state_info['lower_bound']
        breakout = state_info['breakout_point']
        
        if not breakout:
            return
        
        # 4.1 完全脱离区间的情况
        if current_bar['low'] < lower or current_bar['high'] > upper:
            # 记录高低点
            if current_bar['high'] > upper:
                state_info['pullback_point'] = float(current_bar['high'])
            
            # 等待回调/反弹
            state_info['state'] = RangeState.WAITING_PULLBACK
            state_info['bars_since_breakout'] += 1
            
            # 4.1.1 向下脱离
            if current_bar['low'] < lower:
                # 等待K线最低没有再次出现(确认反弹)
                if state_info['bars_since_breakout'] >= 2:
                    # 检查是否形成反弹高点
                    if (state_info['last_high'] is not None and 
                        current_bar['high'] < state_info['last_high']):
                        # 等待再次向下突破时入场
                        if (state_info['pullback_point'] is not None and 
                            current_bar['low'] < state_info['pullback_point']):
                            self._enter_short(symbol, float(current_bar['low']), lower)
                            
            # 4.1.2 向上脱离
            if current_bar['high'] > upper:
                # 等待K线最高没有再次出现(确认回调)
                if state_info['bars_since_breakout'] >= 2:
                    # 检查是否形成回调低点
                    if (state_info['last_low'] is not None and 
                        current_bar['low'] > state_info['last_low']):
                        # 等待再次向上突破时入场
                        if (state_info['pullback_point'] is not None and 
                            current_bar['high'] > state_info['pullback_point']):
                            self._enter_long(symbol, float(current_bar['high']), upper)
        
        # 4.2 部分突破的情况
        else:
            # 4.2.1 突破下界但未完全脱离
            if breakout['direction'] == 'down':
                # 等待再次向下突破时入场
                if current_bar['low'] < breakout['price']:
                    self._enter_short(symbol, float(current_bar['low']), lower)
            
            # 4.2.2 突破上界但未完全脱离
            if breakout['direction'] == 'up':
                # 等待再次向上突破时入场
                if current_bar['high'] > breakout['price']:
                    self._enter_long(symbol, float(current_bar['high']), upper)
    
    def _enter_long(self, symbol: str, entry_price: float, stop_price: float):
        """
        开多仓
        """
        quantity = self._calculate_position_size(symbol, entry_price, stop_price)
        
        if quantity < self.params['min_position_size']:
            print(f"仓位计算小于最小交易单位，不开仓")
            return
        
        # 根据错误信息调整订单创建方式
        try:
            # 尝试第一种方式
            entry_order = Order(
                symbol=symbol,
                order_type=OrderType.MARKET,  # 使用order_type而不是type
                side=OrderSide.BUY,
                quantity=quantity
            )
        except TypeError:
            try:
                # 尝试第二种方式
                entry_order = Order(
                    symbol=symbol,
                    type=OrderType.MARKET,
                    side=OrderSide.BUY,
                    quantity=quantity
                )
            except TypeError:
                try:
                    # 尝试第三种方式
                    entry_order = Order(
                        symbol=symbol,
                        order_type='MARKET',
                        side='BUY',
                        quantity=quantity
                    )
                except TypeError as e:
                    print(f"创建订单失败: {e}")
                    return
        
        if self.broker:
            order_id = self.broker.place_order(entry_order)
            
            # 保存持仓信息
            self.positions[symbol] = {
                'direction': 'long',
                'entry_price': entry_price,
                'initial_stop': stop_price,
                'current_stop': stop_price,
                'quantity': quantity,
                'highest_since_entry': entry_price,
                'lowest_since_entry': entry_price,
                'entry_order_id': order_id
            }
            
            # 设置止损
            self._set_stop_loss(symbol, stop_price)
            
            print(f"开多仓 - 入场:{entry_price:.4f}, 止损:{stop_price:.4f}, 手数:{quantity}")
            
            # 重置状态
            self._reset_range_state(symbol)
    
    def _enter_short(self, symbol: str, entry_price: float, stop_price: float):
        """
        开空仓
        """
        quantity = self._calculate_position_size(symbol, entry_price, stop_price)
        
        if quantity < self.params['min_position_size']:
            print(f"仓位计算小于最小交易单位，不开仓")
            return
        
        # 根据错误信息调整订单创建方式
        try:
            # 尝试第一种方式
            entry_order = Order(
                symbol=symbol,
                order_type=OrderType.MARKET,  # 使用order_type而不是type
                side=OrderSide.SELL,
                quantity=quantity
            )
        except TypeError:
            try:
                # 尝试第二种方式
                entry_order = Order(
                    symbol=symbol,
                    type=OrderType.MARKET,
                    side=OrderSide.SELL,
                    quantity=quantity
                )
            except TypeError:
                try:
                    # 尝试第三种方式
                    entry_order = Order(
                        symbol=symbol,
                        order_type='MARKET',
                        side='SELL',
                        quantity=quantity
                    )
                except TypeError as e:
                    print(f"创建订单失败: {e}")
                    return
        
        if self.broker:
            order_id = self.broker.place_order(entry_order)
            
            self.positions[symbol] = {
                'direction': 'short',
                'entry_price': entry_price,
                'initial_stop': stop_price,
                'current_stop': stop_price,
                'quantity': quantity,
                'highest_since_entry': entry_price,
                'lowest_since_entry': entry_price,
                'entry_order_id': order_id
            }
            
            self._set_stop_loss(symbol, stop_price)
            
            print(f"开空仓 - 入场:{entry_price:.4f}, 止损:{stop_price:.4f}, 手数:{quantity}")
            
            self._reset_range_state(symbol)
    
    def _update_trailing_stop(self, symbol: str):
        """
        更新移动止损
        使用新的回调/反弹点
        """
        position = self.positions.get(symbol)
        if not position:
            return
        
        data_list = self.data_buffer[symbol]
        current_bar = data_list[-1]
        
        # 更新最高/最低点
        position['highest_since_entry'] = max(position['highest_since_entry'], 
                                              float(current_bar['high']))
        position['lowest_since_entry'] = min(position['lowest_since_entry'], 
                                             float(current_bar['low']))
        
        if position['direction'] == 'long':
            # 多头:寻找新的回调低点作为移动止损
            recent_lows = [float(bar['low']) for bar in data_list[-5:]]
            new_low = min(recent_lows)
            
            # 如果形成更高的回调低点,移动止损
            if new_low > position['current_stop']:
                self._update_stop_order(symbol, new_low)
                position['current_stop'] = new_low
                print(f"移动止损更新 - 新止损:{new_low:.4f}")
        
        else:  # short
            # 空头:寻找新的反弹高点作为移动止损
            recent_highs = [float(bar['high']) for bar in data_list[-5:]]
            new_high = max(recent_highs)
            
            # 如果形成更低的反弹高点,移动止损
            if new_high < position['current_stop']:
                self._update_stop_order(symbol, new_high)
                position['current_stop'] = new_high
                print(f"移动止损更新 - 新止损:{new_high:.4f}")
    
    def _set_stop_loss(self, symbol: str, stop_price: float):
        """设置止损单"""
        if not self.broker:
            return
            
        position = self.positions.get(symbol)
        if not position:
            return
        
        stop_side = OrderSide.SELL if position['direction'] == 'long' else OrderSide.BUY
        
        # 创建止损订单
        try:
            # 尝试第一种方式
            stop_order = Order(
                symbol=symbol,
                order_type=OrderType.STOP,
                side=stop_side,
                quantity=position['quantity'],
                price=stop_price
            )
        except TypeError:
            try:
                # 尝试第二种方式
                stop_order = Order(
                    symbol=symbol,
                    type=OrderType.STOP,
                    side=stop_side,
                    quantity=position['quantity'],
                    price=stop_price
                )
            except TypeError:
                try:
                    # 尝试第三种方式
                    stop_order = Order(
                        symbol=symbol,
                        order_type='STOP',
                        side='SELL' if stop_side == OrderSide.SELL else 'BUY',
                        quantity=position['quantity'],
                        price=stop_price
                    )
                except TypeError as e:
                    print(f"创建止损订单失败: {e}")
                    return
        
        order_id = self.broker.place_order(stop_order)
        self.stop_orders[symbol] = order_id
    
    def _update_stop_order(self, symbol: str, new_stop: float):
        """更新止损单"""
        if symbol in self.stop_orders:
            self.broker.cancel_order(self.stop_orders[symbol])
        self._set_stop_loss(symbol, new_stop)
    
    def _calculate_position_size(self, symbol: str, entry_price: float, 
                                stop_price: float) -> int:
        """
        计算仓位大小(手数)
        
        期货交易以"手"为单位，最小1手
        
        计算逻辑：
        1. 风险金额 = 账户余额 * 风险比例
        2. 每手风险金额 = 价格差 * 合约乘数
        3. 手数 = 风险金额 / 每手风险金额
        4. 取整到整数，且不小于最小手数，不大于最大手数
        """
        # 如果没有broker,使用固定手数
        if not self.broker:
            return self.params['fixed_position_size']
        
        # 尝试获取账户信息
        try:
            # 使用get_account_info方法
            account_info = self.broker.get_account_info()
            
            # 获取账户余额(根据实际返回的数据结构调整)
            balance = 0
            if hasattr(account_info, 'balance'):
                balance = account_info.balance
            elif isinstance(account_info, dict):
                if 'balance' in account_info:
                    balance = account_info['balance']
                elif 'total_asset' in account_info:
                    balance = account_info['total_asset']
                elif 'available' in account_info:
                    balance = account_info['available']
            
            if balance <= 0:
                # 如果无法获取余额,使用固定手数
                return self.params['fixed_position_size']
            
            # 计算风险金额
            risk_amount = balance * self.params['risk_per_trade']
            
            # 计算价格风险(点数)
            price_risk_points = abs(entry_price - stop_price)
            
            if price_risk_points == 0:
                return self.params['fixed_position_size']
            
            # 计算每手风险金额 = 价格差 * 合约乘数
            risk_per_contract = price_risk_points * self.params['contract_multiplier']
            
            if risk_per_contract <= 0:
                return self.params['fixed_position_size']
            
            # 计算手数
            contracts = risk_amount / risk_per_contract
            
            # 取整到整数手
            contracts = int(np.floor(contracts))
            
            # 限制在最小和最大手数之间
            contracts = max(self.params['min_position_size'], 
                           min(contracts, self.params['max_position_size']))
            
            return contracts
            
        except (AttributeError, KeyError, TypeError, ZeroDivisionError) as e:
            print(f"计算仓位失败: {e}, 使用固定手数")
            return self.params['fixed_position_size']
    
    def _get_position(self, symbol: str) -> float:
        """获取当前持仓"""
        if not self.broker:
            return 0
        
        try:
            positions = self.broker.get_positions()
            for pos in positions:
                if hasattr(pos, 'symbol') and pos.symbol == symbol:
                    return pos.quantity if hasattr(pos, 'quantity') else 0
                elif isinstance(pos, dict) and pos.get('symbol') == symbol:
                    return pos.get('quantity', 0)
            return 0
        except:
            return 0
    
    def _reset_range_state(self, symbol: str):
        """重置区间状态"""
        self.range_states[symbol] = {
            'state': RangeState.NO_RANGE,
            'upper_bound': None,
            'lower_bound': None,
            'swing_highs': [],
            'swing_lows': [],
            'breakout_point': None,
            'pullback_point': None,
            'entry_trigger': None,
            'last_high': None,
            'last_low': None,
            'bars_since_breakout': 0,
            'last_breakout_direction': None
        }
    
    def on_order(self, order: Order):
        """订单状态变化回调"""
        # 检查是否止损单被触发
        try:
            # 尝试多种方式判断订单类型
            is_stop = False
            if hasattr(order, 'order_type'):
                is_stop = order.order_type == OrderType.STOP or order.order_type == 'STOP'
            elif hasattr(order, 'type'):
                is_stop = order.type == OrderType.STOP or order.type == 'STOP'
            
            if is_stop and hasattr(order, 'status') and order.status == 'filled':
                if order.symbol in self.positions:
                    del self.positions[order.symbol]
                if order.symbol in self.stop_orders:
                    del self.stop_orders[order.symbol]
                print(f"止损触发 - {order.symbol}")
        except:
            pass