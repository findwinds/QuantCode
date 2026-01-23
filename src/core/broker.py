# broker.py
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from datetime import datetime
from models.order import Order, OrderType, OrderSide, OrderStatus
from account.account import AccountInfo


class BaseBroker(ABC):
    """交易代理抽象基类"""
    
    @abstractmethod
    def place_order(self, order: Order) -> str:
        """下单"""
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """撤单"""
        pass
    
    @abstractmethod
    def get_order_status(self, order_id: str) -> OrderStatus:
        """获取订单状态"""
        pass
    
    @abstractmethod
    def get_account_info(self) -> AccountInfo:
        """获取账户信息"""
        pass
    
    @abstractmethod
    def get_positions(self) -> Dict[str, float]:
        """获取持仓"""
        pass
    
    @abstractmethod
    def get_open_orders(self) -> List[Order]:
        """获取活跃订单"""
        pass
    
    @abstractmethod
    def get_today_trades(self) -> List:
        """获取当日成交"""
        pass
    
    @abstractmethod
    def get_available_cash(self) -> float:
        """获取可用资金"""
        pass