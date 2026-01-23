# virtual_broker.py
from typing import Dict, List, Callable
from datetime import datetime
import pandas as pd
from .broker import BaseBroker
from models.order import Order, OrderType, OrderSide, OrderStatus, Trade
from account.account import Account, AccountInfo, Position
from core.event import Event, EventType


class ExecutionRule:
    """执行规则抽象类"""
    def check(self, broker, order: Order, current_price: float) -> bool:
        """检查是否允许执行"""
        raise NotImplementedError


class CommissionRule(ExecutionRule):
    """手续费规则"""
    def __init__(self, commission_rate: float = 0.0003, min_commission: float = 5.0):
        self.commission_rate = commission_rate
        self.min_commission = min_commission
    
    def check(self, broker, order: Order, current_price: float) -> bool:
        # 这里仅作为规则示例，实际在成交时计算
        return True
    
    def calculate_commission(self, trade_value: float) -> float:
        """计算手续费"""
        commission = trade_value * self.commission_rate
        return max(commission, self.min_commission)


class TPlusOneRule(ExecutionRule):
    """T+1规则"""
    def __init__(self):
        self.today_buy_symbols = set()
    
    def check(self, broker, order: Order, current_price: float) -> bool:
        if order.side == OrderSide.SELL:
            # 检查是否有持仓
            position = broker.account.positions.get(order.symbol)
            if position is None or position.quantity < order.quantity:
                # 检查是否是当日买入的
                if order.symbol in self.today_buy_symbols:
                    return False  # T+1不允许卖出
        elif order.side == OrderSide.BUY:
            # 记录当日买入的股票
            self.today_buy_symbols.add(order.symbol)
        
        return True


class VirtualBroker(BaseBroker):
    """虚拟经纪商"""
    
    def __init__(self, initial_capital: float = 100000.0):
        self.account = Account(initial_capital)
        self.orders: Dict[str, Order] = {}
        self.trades: List[Trade] = []
        self.current_prices: Dict[str, float] = {}
        self.rules: List[ExecutionRule] = []
        self.event_handlers: Dict[EventType, List[Callable]] = {}
        self.daily_reset()
    
    def add_rule(self, rule: ExecutionRule):
        """添加执行规则"""
        self.rules.append(rule)
    
    def register_event_handler(self, event_type: EventType, handler: Callable):
        """注册事件处理器"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
    
    def emit_event(self, event: Event):
        """触发事件"""
        handlers = self.event_handlers.get(event.event_type, [])
        for handler in handlers:
            handler(event)
    
    def update_market_data(self, symbol: str, data: pd.Series):
        """更新市场数据"""
        self.current_prices[symbol] = data['close']
        
        # 触发市场数据事件
        self.emit_event(Event(
            event_type=EventType.MARKET,
            timestamp=data.name,  # 假设index是datetime
            data={'symbol': symbol, 'data': data.to_dict()}
        ))
        
        # 尝试撮合订单
        self._match_orders(symbol, data)
    
    def place_order(self, order: Order) -> str:
        """下单"""
        # 检查规则
        current_price = self.current_prices.get(order.symbol, 0)
        for rule in self.rules:
            if not rule.check(self, order, current_price):
                order.status = OrderStatus.REJECTED
                return order.order_id
        
        # 检查资金
        if order.side == OrderSide.BUY:
            required_cash = order.quantity * (order.price or current_price)
            if not self.account.lock_cash(required_cash):
                order.status = OrderStatus.REJECTED
                return order.order_id
        
        # 接受订单
        order.status = OrderStatus.SUBMITTED
        self.orders[order.order_id] = order
        
        # 触发订单事件
        self.emit_event(Event(
            event_type=EventType.ORDER,
            timestamp=datetime.now(),
            data={'order': order}
        ))
        
        return order.order_id
    
    def cancel_order(self, order_id: str) -> bool:
        """撤单"""
        if order_id in self.orders:
            order = self.orders[order_id]
            if order.is_active:
                order.status = OrderStatus.CANCELLED
                # 解锁资金
                if order.side == OrderSide.BUY:
                    self.account.unlock_cash(order.remaining_quantity * order.price)
                return True
        return False
    
    def _match_orders(self, symbol: str, data: pd.Series):
        """撮合订单"""
        current_price = data['close']
        open_price = data['open']
        high_price = data['high']
        low_price = data['low']
        
        for order in self.orders.values():
            if not order.is_active or order.symbol != symbol:
                continue
            
            # 简化的撮合逻辑
            if order.order_type == OrderType.MARKET:
                fill_price = current_price
                can_fill = True
            elif order.order_type == OrderType.LIMIT:
                if order.side == OrderSide.BUY:
                    fill_price = order.price
                    can_fill = order.price >= low_price
                else:  # SELL
                    fill_price = order.price
                    can_fill = order.price <= high_price
            else:
                continue
            
            if can_fill:
                self._fill_order(order, fill_price, data.name)
    
    def _fill_order(self, order: Order, fill_price: float, timestamp: datetime):
        """订单成交"""
        # 计算成交数量（简化：全部成交）
        fill_qty = order.remaining_quantity
        trade_value = fill_qty * fill_price
        
        # 计算手续费（简化）
        commission = trade_value * 0.0003  # 0.03%
        
        # 更新订单
        order.filled_quantity += fill_qty
        order.avg_filled_price = fill_price
        order.commission += commission
        order.status = OrderStatus.FILLED if order.remaining_quantity == 0 else OrderStatus.PARTIAL_FILLED
        
        # 更新账户
        if order.side == OrderSide.BUY:
            # 解锁已使用的资金
            used_cash = fill_qty * fill_price
            self.account.unlock_cash(used_cash)
            self.account.available_cash -= (used_cash + commission)
            
            # 更新持仓
            if order.symbol not in self.account.positions:
                self.account.positions[order.symbol] = Position(symbol=order.symbol)
            
            position = self.account.positions[order.symbol]
            total_qty = position.quantity + fill_qty
            position.avg_price = (position.avg_price * position.quantity + fill_price * fill_qty) / total_qty
            position.quantity = total_qty
            
        else:  # SELL
            # 更新持仓
            position = self.account.positions[order.symbol]
            position.quantity -= fill_qty
            if position.quantity == 0:
                position.avg_price = 0.0
                del self.account.positions[order.symbol]
            
            # 计算盈亏
            pnl = (fill_price - position.avg_price) * fill_qty
            self.account.realized_pnl += pnl - commission
            self.account.available_cash += (fill_qty * fill_price - commission)
        
        self.account.commission_total += commission
        self.account.trade_count += 1
        
        # 记录成交
        trade = Trade(
            trade_id=str(len(self.trades) + 1),
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=fill_qty,
            price=fill_price,
            commission=commission,
            timestamp=timestamp
        )
        self.trades.append(trade)
        
        # 触发成交事件
        self.emit_event(Event(
            event_type=EventType.FILL,
            timestamp=timestamp,
            data={'trade': trade, 'order': order}
        ))
    
    def daily_reset(self):
        """每日重置"""
        # 这里可以重置T+1规则等
        pass
    
    # 实现其他抽象方法
    def get_order_status(self, order_id: str) -> OrderStatus:
        order = self.orders.get(order_id)
        return order.status if order else OrderStatus.REJECTED
    
    def get_account_info(self) -> AccountInfo:
        return self.account.get_info(self.current_prices)
    
    def get_positions(self) -> Dict[str, float]:
        return {symbol: pos.quantity for symbol, pos in self.account.positions.items()}
    
    def get_open_orders(self) -> List[Order]:
        return [order for order in self.orders.values() if order.is_active]
    
    def get_today_trades(self) -> List:
        return self.trades
    
    def get_available_cash(self) -> float:
        return self.account.available_cash