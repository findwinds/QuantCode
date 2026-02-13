# src/analysis/visualizer.py
"""
可视化模块 - 生成回测结果图表
"""
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime
import os


class BacktestVisualizer:
    """回测结果可视化器"""
    
    def __init__(self, output_dir: str = "data/results"):
        """
        初始化可视化器
        
        Args:
            output_dir: 输出目录
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        # 设置中文字体
        plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False
    
    def plot_equity_curve(self, account_history: List[Dict], title: str = "净值曲线", 
                         save_path: Optional[str] = None) -> str:
        """绘制净值曲线"""
        if not account_history:
            return ""
        
        df = pd.DataFrame(account_history)
        
        fig, ax = plt.subplots(figsize=(14, 6))
        
        if 'timestamp' in df.columns:
            df.set_index('timestamp', inplace=True)
        
        if 'total_assets' in df.columns:
            ax.plot(df.index, df['total_assets'], label='总资产', linewidth=2, color='#1f77b4')
        
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xlabel('日期', fontsize=12)
        ax.set_ylabel('资金 (元)', fontsize=12)
        ax.legend(fontsize=11)
        ax.grid(True, alpha=0.3)
        
        # 格式化x轴
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        plt.xticks(rotation=45)
        
        plt.tight_layout()
        
        save_path = save_path or os.path.join(self.output_dir, 'equity_curve.png')
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        return save_path
    
    def plot_drawdown(self, account_history: List[Dict], save_path: Optional[str] = None) -> str:
        """绘制回撤曲线"""
        if not account_history:
            return ""
        
        df = pd.DataFrame(account_history)
        
        if 'timestamp' in df.columns:
            df.set_index('timestamp', inplace=True)
        
        if 'total_assets' not in df.columns:
            return ""
        
        equity = df['total_assets'].values
        running_max = np.maximum.accumulate(equity)
        drawdown = (equity - running_max) / running_max * 100
        
        fig, ax = plt.subplots(figsize=(14, 6))
        
        # 绘制回撤柱状图
        colors = ['#d62728' if dd < 0 else '#2ca02c' for dd in drawdown]
        ax.bar(df.index, drawdown, color=colors, alpha=0.7, label='回撤')
        
        ax.set_title('最大回撤', fontsize=14, fontweight='bold')
        ax.set_xlabel('日期', fontsize=12)
        ax.set_ylabel('回撤 (%)', fontsize=12)
        ax.axhline(y=0, color='black', linestyle='-', linewidth=0.8)
        ax.legend(fontsize=11)
        ax.grid(True, alpha=0.3, axis='y')
        
        # 格式化x轴
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        plt.xticks(rotation=45)
        
        plt.tight_layout()
        
        save_path = save_path or os.path.join(self.output_dir, 'drawdown.png')
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        return save_path
    
    def plot_returns_distribution(self, daily_returns: np.ndarray, save_path: Optional[str] = None) -> str:
        """绘制收益分布直方图"""
        if daily_returns is None or len(daily_returns) == 0:
            return ""
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        ax.hist(daily_returns * 100, bins=50, color='#1f77b4', alpha=0.7, edgecolor='black')
        
        ax.set_title('日收益率分布', fontsize=14, fontweight='bold')
        ax.set_xlabel('收益率 (%)', fontsize=12)
        ax.set_ylabel('频率', fontsize=12)
        ax.axvline(x=0, color='red', linestyle='--', linewidth=1.5)
        ax.grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        
        save_path = save_path or os.path.join(self.output_dir, 'returns_distribution.png')
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        return save_path
    
    def plot_cumulative_returns(self, daily_returns: np.ndarray, save_path: Optional[str] = None) -> str:
        """绘制累计收益曲线"""
        if daily_returns is None or len(daily_returns) == 0:
            return ""
        
        cumulative_returns = np.cumprod(1 + daily_returns) - 1
        
        fig, ax = plt.subplots(figsize=(14, 6))
        
        ax.plot(cumulative_returns * 100, linewidth=2, color='#1f77b4', label='累计收益')
        
        ax.set_title('累计收益率', fontsize=14, fontweight='bold')
        ax.set_xlabel('交易日', fontsize=12)
        ax.set_ylabel('累计收益率 (%)', fontsize=12)
        ax.axhline(y=0, color='red', linestyle='--', linewidth=1)
        ax.legend(fontsize=11)
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        save_path = save_path or os.path.join(self.output_dir, 'cumulative_returns.png')
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        return save_path
    
    def plot_volatility(self, daily_returns: np.ndarray, window: int = 20, 
                       save_path: Optional[str] = None) -> str:
        """绘制滚动波动率"""
        if daily_returns is None or len(daily_returns) < window:
            return ""
        
        volatility = pd.Series(daily_returns).rolling(window=window).std() * np.sqrt(252)
        
        fig, ax = plt.subplots(figsize=(14, 6))
        
        ax.plot(volatility, linewidth=2, color='#ff7f0e', label=f'{window}日滚动波动率')
        
        ax.set_title(f'滚动波动率 (年化)', fontsize=14, fontweight='bold')
        ax.set_xlabel('交易日', fontsize=12)
        ax.set_ylabel('波动率 (年化)', fontsize=12)
        ax.legend(fontsize=11)
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        save_path = save_path or os.path.join(self.output_dir, 'volatility.png')
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        return save_path
    
    def plot_metrics_summary(self, metrics: Dict, save_path: Optional[str] = None) -> str:
        """绘制指标摘要（文本信息）"""
        fig, ax = plt.subplots(figsize=(10, 8))
        ax.axis('off')
        
        # 格式化指标
        summary_text = "回测性能指标摘要\n" + "=" * 40 + "\n"
        
        metric_labels = {
            'total_return': ('总收益率', '.2%'),
            'max_drawdown': ('最大回撤', '.2%'),
            'sharpe_ratio': ('夏普比率', '.4f'),
            'win_rate': ('胜率', '.2%'),
            'return_volatility': ('收益波动率', '.2%'),
            'profit_factor': ('利润因子', '.2f'),
            'calmar_ratio': ('Calmar比率', '.4f'),
            'total_trades': ('总交易数', 'd'),
            'profitable_trades': ('盈利交易', 'd'),
            'avg_profit_per_trade': ('平均单笔盈利', ',.2f'),
        }
        
        for key, (label, fmt) in metric_labels.items():
            if key in metrics:
                value = metrics[key]
                if isinstance(value, float):
                    formatted_value = format(value, fmt) if fmt.startswith('.') else format(value, fmt)
                else:
                    formatted_value = str(value)
                summary_text += f"{label:.<20} {formatted_value:>15}\n"
        
        ax.text(0.1, 0.95, summary_text, transform=ax.transAxes, fontsize=11,
                verticalalignment='top', fontfamily='monospace',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        plt.tight_layout()
        
        save_path = save_path or os.path.join(self.output_dir, 'metrics_summary.png')
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        return save_path
    
    def plot_metrics_bars(self, metrics: Dict, save_path: Optional[str] = None) -> str:
        """绘制关键指标柱状图"""
        key_metrics = {
            '总收益率': metrics.get('total_return', 0) * 100,
            '最大回撤': metrics.get('max_drawdown', 0) * 100,
            '夏普比率': metrics.get('sharpe_ratio', 0),
            '胜率': metrics.get('win_rate', 0) * 100,
        }
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        colors = ['#2ca02c' if v > 0 else '#d62728' for v in key_metrics.values()]
        bars = ax.bar(key_metrics.keys(), key_metrics.values(), color=colors, alpha=0.7, edgecolor='black')
        
        # 添加数值标签
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.2f}',
                   ha='center', va='bottom', fontsize=11, fontweight='bold')
        
        ax.set_title('关键性能指标', fontsize=14, fontweight='bold')
        ax.set_ylabel('数值', fontsize=12)
        ax.axhline(y=0, color='black', linestyle='-', linewidth=0.8)
        ax.grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        
        save_path = save_path or os.path.join(self.output_dir, 'metrics_bars.png')
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        return save_path
    
    def generate_all_charts(self, account_history: List[Dict], daily_returns: np.ndarray,
                           metrics: Dict, timestamp: str = "") -> Dict[str, str]:
        """生成所有图表"""
        prefix = f"_{timestamp}" if timestamp else ""
        
        charts = {
            'equity_curve': self.plot_equity_curve(
                account_history, 
                save_path=os.path.join(self.output_dir, f'equity_curve{prefix}.png')
            ),
            'drawdown': self.plot_drawdown(
                account_history,
                save_path=os.path.join(self.output_dir, f'drawdown{prefix}.png')
            ),
            'returns_distribution': self.plot_returns_distribution(
                daily_returns,
                save_path=os.path.join(self.output_dir, f'returns_distribution{prefix}.png')
            ),
            'cumulative_returns': self.plot_cumulative_returns(
                daily_returns,
                save_path=os.path.join(self.output_dir, f'cumulative_returns{prefix}.png')
            ),
            'volatility': self.plot_volatility(
                daily_returns,
                save_path=os.path.join(self.output_dir, f'volatility{prefix}.png')
            ),
            'metrics_summary': self.plot_metrics_summary(
                metrics,
                save_path=os.path.join(self.output_dir, f'metrics_summary{prefix}.png')
            ),
            'metrics_bars': self.plot_metrics_bars(
                metrics,
                save_path=os.path.join(self.output_dir, f'metrics_bars{prefix}.png')
            ),
        }
        
        return charts