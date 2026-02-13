# engine.py
from typing import Dict, Optional
import pandas as pd
from datetime import datetime
from core.virtual_broker import VirtualBroker
from models.order import OrderSide
from strategy.strategy import BaseStrategy
from .event import Event, EventType


class BacktestEngine:
    """回测引擎"""
    
    def __init__(self, initial_capital: float = 100000.0, broker=None):
        if broker is None:
            # 创建默认的VirtualBroker
            from .virtual_broker import VirtualBroker
            self.broker = VirtualBroker(initial_capital)
        else:
            # 使用传入的broker
            self.broker = broker
        self.strategies: Dict[str, BaseStrategy] = {}
        self.data: Dict[str, pd.DataFrame] = {}
        self.current_time: Optional[datetime] = None
        self.results = {}
        self.account_history = []  # 记录账户历史
        
    def add_data(self, symbol: str, data: pd.DataFrame):
        """添加数据"""
        # 确保数据按时间排序
        data = data.sort_index()
        self.data[symbol] = data
    
    def add_strategy(self, name: str, strategy_cls: BaseStrategy, params: Dict = None):
        """添加策略"""
        strategy = strategy_cls(self.broker, params)
        self.strategies[name] = strategy
        
        # 注册事件处理器
        self.broker.register_event_handler(EventType.ORDER, strategy.on_order)
        self.broker.register_event_handler(EventType.FILL, lambda e: strategy.on_trade(e.data['trade']))
        self.broker.register_event_handler(EventType.ACCOUNT, lambda e: strategy.on_account(e.data['account_info']))
    
    def add_rule(self, rule):
        """添加执行规则"""
        self.broker.add_rule(rule)
    
    def run(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None):
        """运行回测"""
        # 合并所有数据的时间索引
        all_times = set()
        for symbol, df in self.data.items():
            all_times.update(df.index)
        
        times = sorted(list(all_times))
        
        # 时间范围过滤
        if start_date:
            times = [t for t in times if t >= start_date]
        if end_date:
            times = [t for t in times if t <= end_date]
        
        # 回测主循环
        for i, timestamp in enumerate(times):
            self.current_time = timestamp
            
            # 每日重置
            if i > 0 and timestamp.date() != times[i-1].date():
                self.broker.daily_reset()
            
            # 更新每个symbol的数据
            for symbol, df in self.data.items():
                if timestamp in df.index:
                    data = df.loc[timestamp]
                    # 更新经纪商市场数据
                    self.broker.update_market_data(symbol, data)
                    
                    # 触发策略
                    for strategy in self.strategies.values():
                        strategy.on_bar(symbol, data)
            
            # 触发账户更新事件
            account_info = self.broker.get_account_info()
            self.account_history.append({
                'timestamp': timestamp,
                'total_assets': account_info.total_assets,
                'cash': account_info.cash,
                'market_value': account_info.market_value,
                'realized_pnl': account_info.realized_pnl,
                'unrealized_pnl': account_info.unrealized_pnl,
            })
            self.broker.emit_event(Event(
                event_type=EventType.ACCOUNT,
                timestamp=timestamp,
                data={'account_info': account_info}
            ))
        
        # 收集结果
        self._collect_results()
    
    def _collect_results(self):
        """收集回测结果"""
        self.results = {
            'final_account': self.broker.get_account_info(),
            'trades': self.broker.trades,
            'orders': list(self.broker.orders.values()),
            'account_history': self.account_history,
        }
    
    def get_results(self) -> Dict:
        """获取回测结果"""
        return self.results
    
    def get_performance(self) -> Dict:
        """计算性能指标"""
        from analysis.performance_analyzer import PerformanceAnalyzer
        
        analyzer = PerformanceAnalyzer(
            self.broker.account.initial_capital,
            self.account_history,
            self.results['trades']
        )
        
        return analyzer.calculate_all_metrics()