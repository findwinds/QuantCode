# src/analysis/performance_analyzer.py
"""
性能分析模块 - 计算各种回测指标
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from datetime import datetime


class PerformanceAnalyzer:
    """性能分析器"""
    
    def __init__(self, initial_capital: float, account_history: List[Dict], trades: List):
        """
        初始化分析器
        
        Args:
            initial_capital: 初始资金
            account_history: 账户历史列表 [{'timestamp': datetime, 'total_assets': float, ...}, ...]
            trades: 成交记录列表
        """
        self.initial_capital = initial_capital
        self.account_history = account_history
        self.trades = trades
        self.performance_metrics = {}
    
    def calculate_all_metrics(self) -> Dict:
        """计算所有性能指标"""
        self.performance_metrics = {
            'total_return': self.calculate_total_return(),
            'max_drawdown': self.calculate_max_drawdown(),
            'sharpe_ratio': self.calculate_sharpe_ratio(),
            'win_rate': self.calculate_win_rate(),
            'return_volatility': self.calculate_return_volatility(),
            'total_trades': len(self.trades),
            'profitable_trades': self.count_profitable_trades(),
            'avg_profit_per_trade': self.calculate_avg_profit_per_trade(),
            'profit_factor': self.calculate_profit_factor(),
            'calmar_ratio': self.calculate_calmar_ratio(),
        }
        return self.performance_metrics
    
    def get_equity_curve(self) -> pd.DataFrame:
        """获取净值曲线"""
        if not self.account_history:
            return pd.DataFrame()
        
        df = pd.DataFrame(self.account_history)
        if 'timestamp' in df.columns:
            df.set_index('timestamp', inplace=True)
        
        return df[['total_assets']] if 'total_assets' in df.columns else df
    
    def calculate_total_return(self) -> float:
        """计算总收益率"""
        if not self.account_history:
            return 0.0
        
        final_assets = self.account_history[-1].get('total_assets', self.initial_capital)
        return (final_assets - self.initial_capital) / self.initial_capital
    
    def calculate_max_drawdown(self) -> float:
        """
        计算最大回撤
        
        最大回撤 = (峰值 - 谷值) / 峰值
        """
        if not self.account_history:
            return 0.0
        
        equity_values = [h.get('total_assets', self.initial_capital) for h in self.account_history]
        
        if len(equity_values) < 2:
            return 0.0
        
        equity_array = np.array(equity_values)
        running_max = np.maximum.accumulate(equity_array)
        drawdown = (equity_array - running_max) / running_max
        max_drawdown = np.min(drawdown)
        
        return abs(max_drawdown)
    
    def calculate_daily_returns(self) -> np.ndarray:
        """计算每日收益率"""
        if not self.account_history or len(self.account_history) < 2:
            return np.array([])
        
        equity_values = np.array([h.get('total_assets', self.initial_capital) for h in self.account_history])
        
        # 计算日收益率
        daily_returns = np.diff(equity_values) / equity_values[:-1]
        
        return daily_returns
    
    def calculate_return_volatility(self) -> float:
        """
        计算收益波动率 (年化)
        
        假设252个交易日
        """
        daily_returns = self.calculate_daily_returns()
        
        if len(daily_returns) < 2:
            return 0.0
        
        volatility = np.std(daily_returns, ddof=1)
        # 年化波动率
        annual_volatility = volatility * np.sqrt(252)
        
        return annual_volatility
    
    def calculate_sharpe_ratio(self, risk_free_rate: float = 0.03) -> float:
        """
        计算夏普比率
        
        Sharpe Ratio = (平均收益率 - 无风险利率) / 收益波动率
        
        Args:
            risk_free_rate: 无风险利率 (年化，默认3%)
        """
        daily_returns = self.calculate_daily_returns()
        
        if len(daily_returns) < 2:
            return 0.0
        
        mean_return = np.mean(daily_returns)
        volatility = np.std(daily_returns, ddof=1)
        
        if volatility == 0:
            return 0.0
        
        # 转换为年化收益率
        annual_mean_return = mean_return * 252
        annual_volatility = volatility * np.sqrt(252)
        
        # 夏普比率
        sharpe_ratio = (annual_mean_return - risk_free_rate) / annual_volatility
        
        return sharpe_ratio
    
    def calculate_calmar_ratio(self) -> float:
        """
        计算Calmar比率
        
        Calmar Ratio = 年化收益率 / 最大回撤
        """
        total_return = self.calculate_total_return()
        max_drawdown = self.calculate_max_drawdown()
        
        if max_drawdown == 0 or not self.account_history:
            return 0.0
        
        # 计算年化收益率（假设1年回测）
        days = (self.account_history[-1].get('timestamp', datetime.now()) - 
                self.account_history[0].get('timestamp', datetime.now())).days
        
        if days <= 0:
            days = 1
        
        years = days / 365.0
        annual_return = total_return / years if years > 0 else 0.0
        
        calmar_ratio = annual_return / max_drawdown if max_drawdown > 0 else 0.0
        
        return calmar_ratio
    
    def calculate_win_rate(self) -> float:
        """计算胜率"""
        if not self.trades:
            return 0.0
        
        profitable_trades = 0
        
        for trade in self.trades:
            pnl = self._calculate_trade_pnl(trade)
            if pnl > 0:
                profitable_trades += 1
        
        return profitable_trades / len(self.trades)
    
    def count_profitable_trades(self) -> int:
        """统计盈利交易数"""
        profitable_count = 0
        for trade in self.trades:
            pnl = self._calculate_trade_pnl(trade)
            if pnl > 0:
                profitable_count += 1
        return profitable_count
    
    def calculate_avg_profit_per_trade(self) -> float:
        """计算每笔交易平均盈利"""
        if not self.trades:
            return 0.0
        
        total_pnl = sum(self._calculate_trade_pnl(t) for t in self.trades)
        return total_pnl / len(self.trades)
    
    def calculate_profit_factor(self) -> float:
        """
        计算利润因子
        
        Profit Factor = 总盈利 / 总亏损
        """
        if not self.trades:
            return 0.0
        
        total_gains = 0.0
        total_losses = 0.0
        
        for trade in self.trades:
            pnl = self._calculate_trade_pnl(trade)
            if pnl > 0:
                total_gains += pnl
            else:
                total_losses += abs(pnl)
        
        if total_losses == 0:
            return 0.0
        
        return total_gains / total_losses
    
    def _calculate_trade_pnl(self, trade) -> float:
        """
        计算单笔交易盈亏
        
        支持多种trade数据结构
        """
        # 检查是否有直接的pnl属性
        if hasattr(trade, 'pnl'):
            return trade.pnl
        
        # 检查是否有profit属性
        if hasattr(trade, 'profit'):
            return trade.profit
        
        # 对于期货交易，根据side计算
        if hasattr(trade, 'side') and hasattr(trade, 'quantity') and hasattr(trade, 'price'):
            # 这种情况下需要额外信息（对手方价格等），暂时返回0
            # 实际应该在Trade对象中记录pnl
            return 0.0
        
        return 0.0
    
    def get_metrics_dict(self) -> Dict:
        """获取指标字典"""
        return self.performance_metrics


class DrawdownAnalyzer:
    """回撤分析器"""
    
    @staticmethod
    def calculate_drawdown_series(equity_values: np.ndarray) -> np.ndarray:
        """计算回撤序列"""
        running_max = np.maximum.accumulate(equity_values)
        drawdown = (equity_values - running_max) / running_max
        return drawdown
    
    @staticmethod
    def find_drawdown_periods(equity_values: np.ndarray, threshold: float = 0.05) -> List[Tuple[int, int, float]]:
        """
        找出回撤期间
        
        Args:
            equity_values: 净值序列
            threshold: 回撤阈值 (默认5%)
        
        Returns:
            [(开始索引, 结束索引, 最大回撤), ...]
        """
        drawdown = DrawdownAnalyzer.calculate_drawdown_series(equity_values)
        
        periods = []
        start_idx = None
        peak_idx = 0
        
        for i in range(len(drawdown)):
            if drawdown[i] < -threshold:
                if start_idx is None:
                    start_idx = i
                    peak_idx = i
            else:
                if start_idx is not None:
                    max_dd = np.min(drawdown[start_idx:i])
                    periods.append((start_idx, i, abs(max_dd)))
                    start_idx = None
        
        if start_idx is not None:
            max_dd = np.min(drawdown[start_idx:])
            periods.append((start_idx, len(drawdown) - 1, abs(max_dd)))
        
        return periods