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
        
        # 设置中文字体 - 改进版本
        self._setup_font()

    
    def _setup_font(self):
        """设置中文字体"""
        import matplotlib
        import sys
        
        # Windows系统
        if sys.platform == 'win32':
            font_names = ['SimHei', 'Microsoft YaHei', 'STHeiti', 'DejaVu Sans']
        # Mac系统
        elif sys.platform == 'darwin':
            font_names = ['Arial Unicode MS', 'SimHei', 'STHeiti', 'DejaVu Sans']
        # Linux系统
        else:
            font_names = ['DejaVu Sans', 'SimHei', 'STHeiti']
        
        # 尝试找到可用的字体
        available_fonts = matplotlib.font_manager.findSystemFonts()
        available_font_names = [os.path.basename(f) for f in available_fonts]
        
        selected_font = None
        for font in font_names:
            if any(font.lower() in fname.lower() for fname in available_font_names):
                selected_font = font
                break
        
        # 如果没有找到中文字体，使用默认
        if selected_font is None:
            selected_font = 'DejaVu Sans'
        
        plt.rcParams['font.sans-serif'] = [selected_font, 'DejaVu Sans']
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
        # 回撤是负数，表示从峰值下降的百分比
        drawdown = (equity - running_max) / running_max * 100
        
        fig, ax = plt.subplots(figsize=(14, 6))
        
        # 绘制回撤柱状图 - 回撤总是负数或零，所以统一用红色
        ax.bar(df.index, drawdown, color='#d62728', alpha=0.7, label='回撤 (%)')
        
        ax.set_title('最大回撤', fontsize=14, fontweight='bold')
        ax.set_xlabel('日期', fontsize=12)
        ax.set_ylabel('回撤 (%)', fontsize=12)
        ax.axhline(y=0, color='black', linestyle='-', linewidth=1.5)
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
        import matplotlib.pyplot as plt
        import matplotlib.font_manager as fm
        
        # 设置中文字体
        plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']  # 用来正常显示中文标签
        plt.rcParams['axes.unicode_minus'] = False  # 用来正常显示负号

        fig, ax = plt.subplots(figsize=(10, 8))
        ax.axis('off')
        
        # 格式化指标
        summary_lines = [
            "Backtest Performance Summary",
            "=" * 50,
        ]
        
        metric_labels = [
            ('total_return', 'Total Return', '.2%'),
            ('max_drawdown', 'Max Drawdown', '.2%'),
            ('sharpe_ratio', 'Sharpe Ratio', '.4f'),
            ('calmar_ratio', 'Calmar Ratio', '.4f'),
            ('win_rate', 'Win Rate', '.2%'),
            ('return_volatility', 'Volatility', '.2%'),
            ('profit_factor', 'Profit Factor', '.2f'),
            ('total_trades', 'Total Trades', 'd'),
            ('profitable_trades', 'Profitable Trades', 'd'),
            ('avg_profit_per_trade', 'Avg Profit/Trade', ',.2f'),
        ]
        
        for key, label, fmt in metric_labels:
            if key in metrics:
                value = metrics[key]
                try:
                    if isinstance(value, float) and fmt.startswith('.'):
                        formatted_value = format(value, fmt)
                    elif isinstance(value, (int, float)):
                        formatted_value = format(value, fmt)
                    else:
                        formatted_value = str(value)
                except:
                    formatted_value = str(value)
                
                # 使用固定宽度格式化
                line = f"{label}".ljust(20) + f"{formatted_value:>15}"
                summary_lines.append(line)
        
        summary_text = "\n".join(summary_lines)

        # 使用monospace字体确保对齐
        ax.text(0.05, 0.95, summary_text, 
                transform=ax.transAxes, 
                fontsize=11,
                verticalalignment='top', 
                fontfamily='monospace',  # 使用等宽字体
                bbox=dict(boxstyle='round', facecolor='#f0f0f0', alpha=0.8, pad=1),
                wrap=False)
        
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