# scripts/run_with_engine.py
"""
使用BacktestEngine的正确运行脚本
"""
import argparse
import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='QuantCode 回测系统 (使用BacktestEngine)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 基本使用
  python scripts/run_with_engine.py --symbol RB0 --use-akshare
  
  # 多品种
  python scripts/run_with_engine.py --symbol RB0 --symbol AG0 --capital 200000
  
  # 自定义策略参数
  python scripts/run_with_engine.py --symbol RB0 --use-akshare --fast 5 --slow 20 --position 1
        """
    )
    
    parser.add_argument('--symbol', '-s', action='append', required=True,
                       help='交易标的代码')
    parser.add_argument('--start', default='2025-01-01',
                       help='开始日期 (YYYY-MM-DD)')
    parser.add_argument('--end', default='2025-12-31',
                       help='结束日期 (YYYY-MM-DD)')
    parser.add_argument('--freq', default='1d',
                       choices=['1d', '1m', '5m', '15m', '30m', '60m'],
                       help='数据频率')
    parser.add_argument('--capital', type=float, default=100000.0,
                       help='初始资金')
    parser.add_argument('--fast', type=int, default=10,
                       help='快线周期')
    parser.add_argument('--slow', type=int, default=30,
                       help='慢线周期')
    parser.add_argument('--position', type=float, default=0.8,
                       help='仓位比例 (股票) 或 手数 (期货)')
    parser.add_argument('--use-akshare', action='store_true',
                       help='使用AkShare数据')
    parser.add_argument('--use-simulation', action='store_true',
                       help='使用模拟数据')
    parser.add_argument('--strategy', default='dual_ma',
                       choices=['dual_ma', 'futures_dual_ma'],
                       help='策略类型')
    parser.add_argument('--output', '-o', help='输出目录')
    parser.add_argument('--verbose', '-v', action='count', default=0,
                       help='详细输出')
    
    return parser.parse_args()

def load_data(args):
    """加载数据"""
    print("\n[1/4] 加载数据")
    print("-" * 40)
    
    data_dict = {}
    
    for symbol in args.symbol:
        df = None
        
        # 尝试AkShare
        if args.use_akshare and not args.use_simulation:
            try:
                from data.akshare_feed import AkShareFeed
                feed = AkShareFeed()
                df = feed.get_kline(
                    symbol=symbol,
                    freq=args.freq,
                    start=args.start,
                    end=args.end
                )
                if df is not None and not df.empty:
                    print(f"  ✓ {symbol}: {len(df)} 条 (AkShare)")
                else:
                    print(f"  ✗ {symbol}: AkShare数据为空")
                    df = None
            except Exception as e:
                print(f"  ✗ {symbol}: AkShare失败 - {e}")
                df = None
        
        # 使用模拟数据
        if df is None:
            df = create_simulation_data(symbol, args.start, args.end, args.freq)
            print(f"  ✓ {symbol}: {len(df)} 条 (模拟数据)")
        
        if df is not None:
            data_dict[symbol] = df
    
    if not data_dict:
        print("错误: 没有加载到任何数据")
        return None
    
    return data_dict

def create_simulation_data(symbol, start, end, freq):
    """创建模拟数据"""
    freq_map = {'1d': 'D', '1m': 'T', '5m': '5T', '15m': '15T', '30m': '30T', '60m': 'H'}
    freq_pandas = freq_map.get(freq, 'D')
    
    try:
        dates = pd.date_range(start=start, end=end, freq=freq_pandas)
    except:
        dates = pd.date_range(start='2024-01-01', periods=100, freq=freq_pandas)
    
    n_points = len(dates)
    np.random.seed(42)
    
    # 根据不同品种设置基准价格
    base_prices = {
        'AAPL': 150, 'MSFT': 300, 'GOOGL': 100,
        'TSLA': 200, 'RB0': 3500, 'AG0': 5000,
    }
    base_price = base_prices.get(symbol, 100)
    
    # 生成价格序列
    returns = np.random.normal(0.0005, 0.02, n_points)
    prices = base_price * np.exp(np.cumsum(returns))
    
    df = pd.DataFrame({
        'open': prices * (1 + np.random.uniform(-0.01, 0.01, n_points)),
        'high': prices * (1 + np.random.uniform(0, 0.02, n_points)),
        'low': prices * (1 - np.random.uniform(0, 0.02, n_points)),
        'close': prices,
        'volume': np.random.randint(1000000, 10000000, n_points)
    }, index=dates)
    
    return df

def setup_engine(args, data_dict):
    """设置引擎"""
    print("\n[2/4] 设置回测引擎")
    print("-" * 40)
    
    try:
        from core.engine import BacktestEngine
        
        # 创建引擎
        engine = BacktestEngine(initial_capital=args.capital)
        print(f"引擎创建: 初始资金 ¥{args.capital:,.2f}")
        
        # 添加数据到引擎
        for symbol, df in data_dict.items():
            engine.add_data(symbol, df)
            print(f"添加数据: {symbol} ({len(df)}条)")
        
        return engine
        
    except Exception as e:
        print(f"设置引擎失败: {e}")
        import traceback
        traceback.print_exc()
        return None

def add_strategy_to_engine(engine, args):
    """添加策略到引擎"""
    print("\n[3/4] 添加策略")
    print("-" * 40)
    
    try:
        # 如果指定期货策略，确保position是整数手数
        if args.strategy == 'futures_dual_ma':
            # 将position转换为整数手数
            position_value = max(1, int(args.position))  # 至少1手，取整数
            print(f"期货策略: 每次交易 {position_value} 手")
            
            # 使用DualMaStrategy，但调整参数
            from strategy.dual_ma import DualMaStrategy
            strategy_cls = DualMaStrategy
            
            # 对于期货，position_ratio应该大于1表示手数
            strategy_params = {
                'fast': args.fast,
                'slow': args.slow,
                'position_ratio': float(position_value),  # 作为手数
                'is_futures': True,  # 添加标记
            }
        else:
            # 股票策略
            from strategy.dual_ma import DualMaStrategy
            strategy_cls = DualMaStrategy
            strategy_params = {
                'fast': args.fast,
                'slow': args.slow,
                'position_ratio': args.position,  # 仓位比例
                'is_futures': False,
            }
        
        # 添加策略到引擎
        engine.add_strategy('main_strategy', strategy_cls, strategy_params)
        
        if args.strategy == 'futures_dual_ma':
            print(f"参数: 快线={args.fast}, 慢线={args.slow}, 手数={position_value}")
        else:
            print(f"参数: 快线={args.fast}, 慢线={args.slow}, 仓位={args.position:.1%}")
        
        return True
        
    except Exception as e:
        print(f"添加策略失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_backtest(engine, args):
    """运行回测"""
    print("\n[4/4] 运行回测")
    print("-" * 40)
    
    try:
        # 转换日期字符串为datetime
        from datetime import datetime as dt
        
        start_date = dt.strptime(args.start, '%Y-%m-%d') if args.start else None
        end_date = dt.strptime(args.end, '%Y-%m-%d') if args.end else None
        
        # 运行引擎
        print(f"开始回测: {args.start} 到 {args.end}")
        engine.run(start_date=start_date, end_date=end_date)
        
        # 获取结果
        results = engine.get_results()
        performance = engine.get_performance()
        
        # 合并结果
        full_results = {
            **results,
            'performance': performance
        }
        
        return full_results
        
    except Exception as e:
        print(f"回测运行失败: {e}")
        import traceback
        traceback.print_exc()
        return None

def print_results(results, args):
    """打印结果"""
    if not results:
        print("无结果")
        return
    
    print("\n" + "=" * 60)
    print("回测结果")
    print("=" * 60)
    
    # 性能指标 - 只打印一次
    if 'performance' in results:
        perf = results['performance']
        print(f"📊 性能指标:")
        print(f"   初始资金:   ¥{perf.get('initial_capital', args.capital):>12,.2f}")
        print(f"   最终资产:   ¥{perf.get('final_assets', args.capital):>12,.2f}")
        print(f"   总收益率:   {perf.get('total_return', 0):>12.2%}")
        print(f"   交易次数:   {perf.get('total_trades', 0):>12}")
        print(f"   胜率:       {perf.get('win_rate', 0):>12.2%}")
        print(f"   总手续费:   ¥{perf.get('total_commission', 0):>12,.2f}")
    
    # 最终账户 - 只打印一次
    if 'final_account' in results:
        account = results['final_account']
        print(f"\n💼 最终账户:")
        print(f"   总资产:     ¥{getattr(account, 'total_assets', args.capital):>12,.2f}")
        print(f"   可用资金:   ¥{getattr(account, 'available_cash', args.capital):>12,.2f}")
        
        # 只打印一次盈亏
        if hasattr(account, 'realized_pnl'):
            print(f"   已实现盈亏: ¥{getattr(account, 'realized_pnl', 0):>12,.2f}")
        
        # 持仓信息
        positions = getattr(account, 'positions', {})
        if positions:
            print(f"\n📦 持仓:")
            for symbol, pos in positions.items():
                qty = getattr(pos, 'quantity', 0)
                if isinstance(pos, dict):
                    qty = pos.get('quantity', 0)
                
                if qty != 0:
                    value = getattr(pos, 'market_value', 0)
                    if isinstance(pos, dict):
                        value = pos.get('market_value', 0)
                    print(f"   {symbol}: {qty:>8.2f} 股/手, 市值: ¥{value:>10,.2f}")
    
    # 交易记录 - 只打印一次
    if 'trades' in results:
        trades = results['trades']
        if trades:
            print(f"\n💹 交易记录: {len(trades)} 笔")
            # 显示所有交易
            for i, trade in enumerate(trades, 1):
                side = getattr(trade, 'side', 'N/A')
                if hasattr(side, 'value'):
                    side = side.value
                print(f"   {i:2d}. {trade.symbol} {side} {getattr(trade, 'quantity', 0):.2f} " +
                      f"@ ¥{getattr(trade, 'price', 0):.2f}")
    
    print("=" * 60)

def save_results(results, output_dir):
    """保存结果"""
    if not output_dir:
        return
    
    try:
        import json
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # JSON文件
        json_file = os.path.join(output_dir, f'engine_backtest_{timestamp}.json')
        
        def default_serializer(obj):
            if hasattr(obj, '__dict__'):
                return {k: v for k, v in obj.__dict__.items() 
                       if not k.startswith('_') and not callable(v)}
            elif isinstance(obj, (datetime, pd.Timestamp)):
                return obj.isoformat()
            elif hasattr(obj, 'name'):
                return obj.name
            return str(obj)
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, default=default_serializer)
        
        print(f"\n💾 结果保存到: {json_file}")
        
        # CSV文件（账户历史）
        if 'account_history' in results and results['account_history']:
            csv_file = os.path.join(output_dir, f'account_history_{timestamp}.csv')
            df = pd.DataFrame(results['account_history'])
            df.to_csv(csv_file, index=False)
            print(f"💾 账户历史: {csv_file}")
        
    except Exception as e:
        print(f"保存失败: {e}")

def main():
    """主函数"""
    # 解析参数
    args = parse_arguments()

    # =========== 添加参数打印 ===========
    print("=" * 70)
    print("运行参数:")
    print("-" * 70)
    # 打印所有参数
    for key, value in vars(args).items():
        if isinstance(value, list):
            print(f"  {key:20}: {', '.join(value)}")
        else:
            print(f"  {key:20}: {value}")
    print("=" * 70)
    # ====================================

    
    print("=" * 70)
    print("QuantCode 回测系统 (BacktestEngine)")
    print("=" * 70)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"品种: {', '.join(args.symbol)}")
    print(f"策略: {args.strategy}")
    print(f"数据: {'AkShare' if args.use_akshare else '模拟数据'}")
    print("=" * 70)
    
    try:
        # 1. 加载数据
        data_dict = load_data(args)
        if not data_dict:
            return
        
        # 2. 设置引擎
        engine = setup_engine(args, data_dict)
        if not engine:
            return
        
        # 3. 添加策略
        if not add_strategy_to_engine(engine, args):
            return
        
        # 4. 运行回测
        results = run_backtest(engine, args)
        
        if results:
            # 5. 打印结果
            print_results(results, args)
            
            # 6. 保存结果
            if args.output:
                save_results(results, args.output)
            else:
                try:
                    save = input("\n是否保存结果到data/results文件夹？(y/n): ").strip().lower()
                    if save == 'y':
                        results_dir = os.path.join('data', 'results')
                        os.makedirs(results_dir, exist_ok=True)
                        save_results(results, results_dir)
                except:
                    pass
            
            print("\n🎉 回测完成！")
        
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        if args.verbose >= 1:
            traceback.print_exc()

if __name__ == "__main__":
    main()