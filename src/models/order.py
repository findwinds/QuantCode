# src/models/order.py
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class OrderType(Enum):
    """订单类型"""
    MARKET = "market"      # 市价单
    LIMIT = "limit"        # 限价单
    STOP = "stop"          # 止损单
    STOP_LIMIT = "stop_limit"  # 止损限价单


class OrderSide(Enum):
    """买卖方向"""
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    """订单状态"""
    PENDING = "pending"     # 等待提交
    SUBMITTED = "submitted" # 已提交
    PARTIAL_FILLED = "partial_filled"  # 部分成交
    FILLED = "filled"       # 完全成交
    CANCELLED = "cancelled" # 已取消
    REJECTED = "rejected"   # 已拒绝


@dataclass
class Order:
    """订单类"""
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float] = None
    order_id: Optional[str] = None
    status: OrderStatus = OrderStatus.PENDING
    timestamp: Optional[datetime] = None
    filled_quantity: float = 0.0
    avg_filled_price: float = 0.0
    commission: float = 0.0
    required_margin: float = 0.0
    reject_reason: Optional[str] = None

    def __post_init__(self):
        if self.order_id is None:
            import uuid
            self.order_id = str(uuid.uuid4())[:8]
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    @property
    def is_active(self):
        """是否活跃订单"""
        return self.status in [OrderStatus.PENDING, OrderStatus.SUBMITTED, OrderStatus.PARTIAL_FILLED]
    
    @property
    def remaining_quantity(self):
        """剩余数量"""
        return self.quantity - self.filled_quantity


@dataclass
class Trade:
    """成交记录"""
    trade_id: str
    order_id: str
    symbol: str
    side: OrderSide
    quantity: float
    price: float
    commission: float
    timestamp: datetime
    contract_value: float