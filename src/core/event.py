# src/core/event.py
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional
from enum import Enum


class EventType(Enum):
    """事件类型枚举"""
    MARKET = "market"           # 市场数据事件
    SIGNAL = "signal"           # 交易信号事件
    ORDER = "order"             # 订单事件
    FILL = "fill"               # 成交事件
    ACCOUNT = "account"         # 账户更新事件
    TRADE = "trade"             # 交易事件

@dataclass
class Event:
    """基础事件类"""
    event_type: EventType
    timestamp: datetime
    data: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.data is None:
            self.data = {}