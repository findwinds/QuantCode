# strategy.py
from abc import ABC, abstractmethod
from typing import Dict, Any
import pandas as pd
from core.broker import BaseBroker
from models.order import Order


class BaseStrategy(ABC):
    """策略抽象基类"""
    
    def __init__(self, broker=None, params: Dict[str, Any] = None):
        """
        初始化策略
        
        Args:
            broker: 交易代理实例
            params: 策略参数字典
        """
        self.broker = broker
        self.params = params or {}
        
    @abstractmethod
    def on_bar(self, symbol: str, data: pd.Series):
        """
        每个Bar触发一次
        data包含: open, high, low, close, volume等
        """
        pass
    
    def on_order(self, order: Order):
        """订单状态变化回调"""
        pass
    
    def on_trade(self, trade):
        """成交回调"""
        pass
    
    def on_account(self, account_info):
        """账户更新回调"""
        pass
    
    def set_params(self, params: Dict[str, Any]):
        """设置参数"""
        self.params.update(params)
    
    def get_params(self) -> Dict[str, Any]:
        """获取参数"""
        return self.params.copy()