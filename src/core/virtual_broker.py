# virtual_broker.py
import logging
import os
import sys
from typing import Dict, List, Callable, Optional
from datetime import datetime
import pandas as pd
from .broker import BaseBroker
from models.order import Order, OrderType, OrderSide, OrderStatus, Trade
from account.account import Account, AccountInfo, Position
from core.event import Event, EventType

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, project_root)

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

    def reset(self):
        """每日重置"""
        self.today_buy_symbols.clear()


class VirtualBroker(BaseBroker):
    """虚拟经纪商"""
    
    def __init__(
        self, 
        initial_capital: float = 1000000.0,
        config_path: Optional[str] = None
    ):
        self.account = Account(initial_capital)
        self.orders: Dict[str, Order] = {}
        self.trades: List[Trade] = []
        self.current_prices: Dict[str, float] = {}
        self.rules: List[ExecutionRule] = []
        self.event_handlers: Dict[EventType, List[Callable]] = {}

        self.logger = logging.getLogger(__name__)

        if config_path is None:
            config_path = "config/futures_config.yaml"

        try:
            from config.futures_config import FuturesConfig
            self.futures_config = FuturesConfig(config_path)
        except ImportError as e:
            self.logger.error(f"无法导入期货配置模块: {e}")
            self.futures_config = None
        except Exception as e:
            self.logger.error(f"加载期货配置文件失败: {e}")
            self.futures_config = None

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
        """下单（严格资金检查）"""
        current_price = self.current_prices.get(order.symbol, order.price or 0)
        if current_price <= 0 and order.price is None:
            order.status = OrderStatus.REJECTED
            order.reject_reason = "缺少有效价格，无法下单"
            return order.order_id

        # 检查规则
        for rule in self.rules:
            if not rule.check(self, order, current_price):
                order.status = OrderStatus.REJECTED
                return order.order_id

        # 获取当前持仓
        position = self.account.positions.get(order.symbol)
        current_qty = position.quantity if position else 0

        # 计算开仓数量（需要保证金的）
        if order.side == OrderSide.BUY:
            # 买入操作
            if current_qty < 0:  # 当前有空头
                close_qty = min(order.quantity, abs(current_qty))  # 平空仓数量
                open_qty = max(0, order.quantity - close_qty)  # 剩余开多仓
            else:  # 当前没有空头或有多头
                close_qty = 0
                open_qty = order.quantity  # 全部开多仓（加仓）
        else:  # SELL
            # 卖出操作
            if current_qty > 0:  # 当前有多头
                close_qty = min(order.quantity, current_qty)  # 平多仓数量
                open_qty = max(0, order.quantity - close_qty)  # 剩余开空仓
            else:  # 当前没有多头或有空头
                close_qty = 0
                open_qty = order.quantity  # 全部开空仓（加仓）

        order.close_quantity = close_qty

        # 资金检查：开仓部分需要保证金
        if open_qty > 0:
            try:
                if self.futures_config:
                    margin_required = self.futures_config.calculate_margin(
                        order.symbol, current_price, open_qty
                    )
                else:
                    margin_required = open_qty * (order.price or current_price)

                available_cash = self.account.cash - self._get_total_locked_cash()

                # 严格检查：当前可用资金必须足够
                if margin_required > available_cash:
                    if close_qty > 0:
                        # 保证金不足时优先允许平仓，避免整个反手被拒绝
                        self.logger.warning(
                            "开仓保证金不足，订单将仅执行平仓部分: symbol=%s, close_qty=%s, open_qty=%s",
                            order.symbol,
                            close_qty,
                            open_qty,
                        )
                        order.quantity = close_qty
                        order.required_margin = 0
                        order.open_quantity = 0
                        order.close_quantity = close_qty
                    else:
                        order.status = OrderStatus.REJECTED
                        order.reject_reason = (
                            f"开仓保证金不足: 需要{margin_required:.2f}元，可用{available_cash:.2f}元"
                        )
                        return order.order_id
                else:
                    # 锁定保证金挂在订单上
                    order.required_margin = margin_required
                    order.open_quantity = open_qty

            except Exception as e:
                order.status = OrderStatus.REJECTED
                order.reject_reason = f"计算保证金失败: {str(e)}"
                return order.order_id
        else:
            # 全部是平仓，不需要保证金
            order.required_margin = 0
            order.open_quantity = 0

        # 接受订单...
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
                order.required_margin = 0.0
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
        if fill_qty <= 0:
            return

        # 获取品种配置
        if self.futures_config:
            config = self.futures_config.get_config(order.symbol)
            trading_unit = config['trading_unit']
            margin_rate = config['margin_rate']
            commission = self.futures_config.calculate_commission(
                order.symbol, fill_qty * trading_unit * fill_price
            )
        else:
            trading_unit = 1
            margin_rate = 1.0
            commission = 0.0

        # 期货合约价值 = 手数 × 交易单位 × 价格
        contract_value = fill_qty * trading_unit * fill_price

        # 获取或创建持仓
        if order.symbol not in self.account.positions:
            self.account.positions[order.symbol] = Position(symbol=order.symbol, trading_unit=trading_unit)

        position = self.account.positions[order.symbol]
        if position.trading_unit != trading_unit:
            position.trading_unit = trading_unit

        # 计算开平仓数量（按成交部分）
        close_qty = min(getattr(order, "close_quantity", 0.0), fill_qty)
        open_qty = max(fill_qty - close_qty, 0.0)

        # 若成交价导致开仓保证金不足，拒绝成交
        if open_qty > 0:
            if self.futures_config:
                fill_margin_required = self.futures_config.calculate_margin(
                    order.symbol, fill_price, open_qty
                )
            else:
                fill_margin_required = open_qty * fill_price

            reserved_margin = getattr(order, "required_margin", 0.0) or 0.0
            if fill_margin_required > reserved_margin:
                additional_needed = fill_margin_required - reserved_margin
                available_cash = self.account.cash - self._get_total_locked_cash(exclude_order_id=order.order_id)
                if additional_needed > available_cash:
                    order.status = OrderStatus.REJECTED
                    order.reject_reason = "成交价导致保证金不足"
                    order.required_margin = 0.0
                    return

        # 更新订单
        order.filled_quantity += fill_qty
        order.avg_filled_price = fill_price
        order.commission += commission
        order.status = OrderStatus.FILLED if order.remaining_quantity == 0 else OrderStatus.PARTIAL_FILLED
        order.required_margin = 0.0

        realized_pnl = 0.0

        # 先处理平仓，再处理开仓
        if order.side == OrderSide.BUY:
            # 买入逻辑
            if position.quantity < 0:
                # 当前持有空头仓位
                close_qty = min(fill_qty, abs(position.quantity))
                # 空头盈亏：开仓价 - 平仓价 * 平仓仓位 * 交易单位
                realized_pnl += (position.avg_price - fill_price) * close_qty * trading_unit
                # 平仓释放保证金
                released_margin = close_qty * trading_unit * position.avg_price * margin_rate
                position.locked_margin = max(position.locked_margin - released_margin, 0.0)

                position.quantity += close_qty  # 负数加上去，绝对值减小

                # 剩余部分为买入开仓（开多头）
                if fill_qty > close_qty:
                    open_qty = fill_qty - close_qty
                    total_qty = position.quantity + open_qty
                    if position.quantity == 0:
                        position.avg_price = fill_price
                    else:
                        position.avg_price = (position.avg_price * position.quantity + fill_price * open_qty) / total_qty
                    position.quantity = total_qty

                    if open_qty > 0:
                        if self.futures_config:
                            fill_margin_required = self.futures_config.calculate_margin(
                                order.symbol, fill_price, open_qty
                            )
                        else:
                            fill_margin_required = open_qty * fill_price
                        position.locked_margin += fill_margin_required
            else:
                # 买入开仓（开多头）或加仓
                total_qty = position.quantity + fill_qty
                if position.quantity == 0:
                    position.avg_price = fill_price
                else:
                    position.avg_price = (position.avg_price * position.quantity + fill_price * fill_qty) / total_qty
                position.quantity = total_qty

                if fill_qty > 0:
                    if self.futures_config:
                        fill_margin_required = self.futures_config.calculate_margin(
                            order.symbol, fill_price, fill_qty
                        )
                    else:
                        fill_margin_required = fill_qty * fill_price
                    position.locked_margin += fill_margin_required
        else:
            if position.quantity > 0:
                # 卖出平仓（平多头）
                close_qty = min(fill_qty, position.quantity)
                # 期货盈亏计算：考虑交易单位
                realized_pnl += (fill_price - position.avg_price) * close_qty * trading_unit
                # 平仓释放保证金
                released_margin = close_qty * trading_unit * position.avg_price * margin_rate
                position.locked_margin = max(position.locked_margin - released_margin, 0.0)

                position.quantity -= close_qty

                # 剩余部分为卖出开仓（开空头）
                if fill_qty > close_qty:
                    open_qty = fill_qty - close_qty
                    total_qty = position.quantity - open_qty  # 减，因为是负数
                    if position.quantity == 0:
                        position.avg_price = fill_price
                    else:
                        position.avg_price = (position.avg_price * position.quantity + fill_price * open_qty) / abs(total_qty)
                    position.quantity = total_qty

                    if open_qty > 0:
                        if self.futures_config:
                            fill_margin_required = self.futures_config.calculate_margin(
                                order.symbol, fill_price, open_qty
                            )
                        else:
                            fill_margin_required = open_qty * fill_price
                        position.locked_margin += fill_margin_required
            else:
                total_qty = position.quantity - fill_qty  # 减，空头为负
                if position.quantity == 0:
                    position.avg_price = fill_price
                else:
                    # 空头加仓，计算新的均价
                    position.avg_price = (abs(position.avg_price) * abs(position.quantity) + fill_price * fill_qty) / abs(total_qty)
                position.quantity = total_qty

                if fill_qty > 0:
                    if self.futures_config:
                        fill_margin_required = self.futures_config.calculate_margin(
                            order.symbol, fill_price, fill_qty
                        )
                    else:
                        fill_margin_required = fill_qty * fill_price
                    position.locked_margin += fill_margin_required

        # 统一更新现金：只在成交时计入手续费和盈亏
        self.account.cash -= commission
        self.account.cash += realized_pnl
        self.account.realized_pnl += realized_pnl

        # 清理零持仓
        if position.quantity == 0:
            del self.account.positions[order.symbol]

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
            timestamp=timestamp,
            contract_value=contract_value  # 合约价值
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
        for rule in self.rules:
            if hasattr(rule, "reset") and callable(rule.reset):
                rule.reset()

    # 实现其他抽象方法
    def get_order_status(self, order_id: str) -> OrderStatus:
        order = self.orders.get(order_id)
        return order.status if order else OrderStatus.REJECTED
    
    def get_account_info(self) -> AccountInfo:
        locked_cash = self._get_total_locked_cash()
        return self.account.get_info(self.current_prices, locked_cash)

    def get_positions(self) -> Dict[str, float]:
        return {symbol: pos.quantity for symbol, pos in self.account.positions.items()}
    
    def get_open_orders(self) -> List[Order]:
        return [order for order in self.orders.values() if order.is_active]
    
    def get_today_trades(self) -> List:
        return self.trades
    
    def get_available_cash(self) -> float:
        return self.account.cash - self._get_total_locked_cash()

    def _get_total_locked_cash(self, exclude_order_id: Optional[str] = None) -> float:
        """计算当前持仓与挂单占用的保证金"""
        locked_cash = 0.0
        for pos in self.account.positions.values():
            locked_cash += getattr(pos, "locked_margin", 0.0) or 0.0

        for order in self.orders.values():
            if not order.is_active:
                continue
            if exclude_order_id and order.order_id == exclude_order_id:
                continue
            locked_cash += getattr(order, "required_margin", 0.0) or 0.0

        return locked_cash
