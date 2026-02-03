# src/account/account.py
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Position:
    def __init__(self, symbol: str, quantity: float, entry_price: float, trading_unit: int = 1, locked_margin: float = 0.0):
        self.symbol = symbol
        self.quantity = quantity
        self.entry_price = entry_price
        self.trading_unit = trading_unit
        self.locked_margin = locked_margin
        self.market_value = 0.0
        self.unrealized_pnl = 0.0

    def update(self, current_price: float):
        """更新持仓信息"""
        self.market_value = abs(self.quantity) * self.trading_unit * current_price
        if self.quantity != 0:
            current_value = self.quantity * self.trading_unit * current_price
            cost = self.quantity * self.trading_unit * self.entry_price
            self.unrealized_pnl = current_value - cost
        else:
            self.unrealized_pnl = 0.0


@dataclass
class AccountInfo:
    """账户信息（只读视图）"""
    total_assets: float = 0.0
    cash: float = 0.0
    market_value: float = 0.0
    total_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    positions: Dict[str, List[Position]] = None
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
            'cash': self.cash,
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
        self.cash = initial_capital
        self.positions: Dict[str, List[Position]] = {}
        self.realized_pnl = 0.0
        self.commission_total = 0.0
        self.trade_count = 0

    def get_info(self, current_prices: Dict[str, float]) -> AccountInfo:
        """获取账户信息（只读）"""
        market_value = 0.0
        unrealized_pnl = 0.0

        # 更新所有持仓
        for symbol, lots in self.positions.items():
            if symbol in current_prices:
                price = current_prices[symbol]
                for lot in lots:
                    lot.update(price)
                    market_value += lot.market_value
                    unrealized_pnl += lot.unrealized_pnl

        # 期货总资产计算
        # total_assets = 现金 + 未实现盈亏
        total_assets = self.cash + unrealized_pnl
        total_pnl = self.realized_pnl + unrealized_pnl

        return AccountInfo(
            total_assets=total_assets,
            cash=self.cash,
            market_value=market_value,  # 持仓总规模（总是正数）
            total_pnl=total_pnl,
            unrealized_pnl=unrealized_pnl,  # 浮动盈亏
            realized_pnl=self.realized_pnl,
            positions=self.positions  # 直接引用，避免复制
        )

    # 账户不再维护 available/locked 资金，锁定保证金由订单和持仓承担
