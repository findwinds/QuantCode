# test/test_virtual_broker.py
from datetime import datetime
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pandas as pd
from core.virtual_broker import VirtualBroker
from models.order import Order, OrderSide, OrderStatus, OrderType


def test_basic_order_flow():
    """测试基础订单流程"""
    print("=== 测试基础订单流程 ===")

    broker = VirtualBroker(initial_capital=100000.0)

    # 1. 测试市价买单
    buy_order = Order(
        symbol="RB0",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=10
    )

    order_id = broker.place_order(buy_order)
    print(f"提交买单: {order_id}, 状态: {buy_order.status}")
    assert buy_order.status == OrderStatus.SUBMITTED

    # 2. 更新市场数据触发成交
    timestamp = datetime.now()
    market_data = pd.Series({
        'open': 3500.0,
        'high': 3520.0,
        'low': 3480.0,
        'close': 3500.0,
        'volume': 10000
    }, name=timestamp)

    broker.update_market_data("RB0", market_data)
    print(f"更新市场数据后订单状态: {buy_order.status}")
    print(f"成交均价: {buy_order.avg_filled_price}")

    # 3. 检查订单状态
    if buy_order.status != OrderStatus.FILLED:
        print(f"订单未完全成交: {buy_order.filled_quantity}/{buy_order.quantity}")

    # 4. 检查持仓
    positions = broker.get_positions()
    print(f"当前持仓: {positions}")

    # 5. 检查账户信息
    account_info = broker.get_account_info()
    print(f"账户现金: {account_info.available_cash:.2f}")
    print(f"总资产: {account_info.total_assets:.2f}")

    print("基础订单流程测试完成 ✓\n")
    return broker


def run_all_tests():
    """运行所有测试"""
    print("开始测试 VirtualBroker...\n")
    print("=" * 60)

    tests = [
        test_basic_order_flow
    ]

    results = []

    for test_func in tests:
        try:
            test_func()
            results.append((test_func.__name__, True, None))
        except AssertionError as e:
            print(f"断言失败: {e}")
            results.append((test_func.__name__, False, str(e)))
        except Exception as e:
            print(f"测试异常: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_func.__name__, False, str(e)))

    print("=" * 60)
    print("\n测试结果汇总:")
    print("-" * 60)

    passed = 0
    failed = 0

    for name, success, error in results:
        status = "✓ 通过" if success else "✗ 失败"
        print(f"{name:30} {status}")
        if error:
            print(f"    错误: {error}")
        
        if success:
            passed += 1
        else:
            failed += 1

    print("-" * 60)
    print(f"总计: {len(results)} 个测试")
    print(f"通过: {passed}")
    print(f"失败: {failed}")
    
    if failed == 0:
        print("\n所有测试通过！✓")
    else:
        print(f"\n有 {failed} 个测试失败，请检查代码。")


if __name__ == "__main__":
    run_all_tests()