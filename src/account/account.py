# src/account/account.py
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Position:
    def __init__(self, symbol: str, trading_unit: int = 1):  # 添加交易单位参数
        self.symbol = symbol
        self.quantity = 0.0
        self.avg_price = 0.0
        self.trading_unit = trading_unit  # 新增
        self.market_value = 0.0 # 持仓的绝对价值（总是正数）
        self.unrealized_pnl = 0.0   # 未实现盈亏（可正可负）
        self.realized_pnl = 0.0
    
    def update(self, current_price: float):
        """更新持仓信息"""
        # 持仓市值：持仓的绝对价值
        self.market_value = abs(self.quantity) * self.trading_unit * current_price
        
        # 未实现盈亏
        if self.quantity != 0:
            current_value = self.quantity * self.trading_unit * current_price
            cost = self.quantity * self.trading_unit * self.avg_price
            self.unrealized_pnl = current_value - cost
        else:
            self.unrealized_pnl = 0.0


@dataclass
class AccountInfo:
    """账户信息（只读视图）"""
    total_assets: float = 0.0
    available_cash: float = 0.0
    locked_cash: float = 0.0
    market_value: float = 0.0
    total_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    positions: Dict[str, Position] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.positions is None:
            self.positions = {}
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'total_assets': self.total_assets,
            'available_cash': self.available_cash,
            'locked_cash': self.locked_cash,
            'market_value': self.market_value,
            'total_pnl': self.total_pnl,
            'unrealized_pnl': self.unrealized_pnl,
            'realized_pnl': self.realized_pnl,
            'timestamp': self.timestamp
        }


class Account:
    """账户类（内部使用）"""
    def __init__(self, initial_capital: float = 100000.0):
        self.initial_capital = initial_capital
        self.available_cash = initial_capital
        self.locked_cash = 0.0
        self.positions: Dict[str, Position] = {}
        self.realized_pnl = 0.0
        self.commission_total = 0.0
        self.trade_count = 0
        
    def get_info(self, current_prices: Dict[str, float]) -> AccountInfo:
        """获取账户信息（只读）"""
        market_value = 0.0
        unrealized_pnl = 0.0
        
        # 更新所有持仓
        for symbol, pos in self.positions.items():
            if symbol in current_prices:
                price = current_prices[symbol]
                pos.update(price)
                market_value += pos.market_value
                unrealized_pnl += pos.unrealized_pnl
        
        # 期货总资产计算
        # total_assets = 可用资金 + 锁定资金 + 未实现盈亏
        total_assets = self.available_cash + self.locked_cash + unrealized_pnl
        total_pnl = self.realized_pnl + unrealized_pnl

        return AccountInfo(
            total_assets=total_assets,
            available_cash=self.available_cash,
            locked_cash=self.locked_cash,
            market_value=market_value,  # 持仓总规模（总是正数）
            total_pnl=total_pnl,
            unrealized_pnl=unrealized_pnl,  # 浮动盈亏
            realized_pnl=self.realized_pnl,
            positions=self.positions  # 直接引用，避免复制
        )
    
    def lock_cash(self, amount: float) -> bool:
        """锁定资金"""
        if amount <= self.available_cash:
            self.available_cash -= amount
            self.locked_cash += amount
            return True
        return False
    
    def unlock_cash(self, amount: float) -> bool:
        """解锁资金"""
        if amount <= self.locked_cash:
            self.locked_cash -= amount
            self.available_cash += amount
            return True
        return False