# QuantCode - Python 期货量化交易框架

一个基于事件驱动的期货量化交易框架，支持完整的回测和模拟交易功能。

## 🌟 特性

- **完整期货交易支持**：保证金计算、手续费管理、持仓管理
- **事件驱动架构**：订单、成交、市场数据事件系统
- **策略抽象**：易于实现和测试交易策略
- **多数据源**：支持 AkShare API 和本地 CSV 数据
- **配置化管理**：YAML 配置文件管理期货品种参数
- **完善的测试**：单元测试和交互式测试

## 🚀 快速开始

### 环境要求
- Python 3.8+
- pip

### 安装
```bash
# 克隆项目
git clone <repository-url>
cd QuantCode

# 安装依赖
pip install -r requirements.txt
```

## 📊 基本使用

### 运行回测
```bash
# 使用AkShare数据运行双均线策略
python scripts/run_with_engine.py --symbol RB0 --use-akshare --strategy futures_dual_ma

# 多品种回测
python scripts/run_with_engine.py --symbol RB0 --symbol MA0 --use-akshare

# 自定义策略参数
python scripts/run_with_engine.py --symbol RB0 --use-akshare --fast 5 --slow 20 --position 2

# 指定初始资金
python scripts/run_with_engine.py --symbol RB0 --use-akshare --capital 1000000

# 保存回测结果
python scripts/run_with_engine.py --symbol RB0 --use-akshare --output ./results
```

### 运行测试
```bash
# 运行测试
python test/test_virtual_broker.py
```

## 🔧 核心组件

### 经纪商系统 (Broker)
- BaseBroker: 抽象基类，定义统一接口
- VirtualBroker: 虚拟经纪商，用于回测
- 支持功能: 下单、撤单、保证金计算、手续费计算

### 回测引擎 (Engine)
```python
from src.core.engine import BacktestEngine
from src.core.virtual_broker import VirtualBroker

# 创建引擎
engine = BacktestEngine(initial_capital=1000000)
```

### 策略系统
```python
from src.strategy import BaseStrategy

class MyStrategy(BaseStrategy):
    def on_data(self, symbol: str, data: pd.DataFrame):
        # 实现交易逻辑
        if data['close'].iloc[-1] > data['ma20'].iloc[-1]:
            self.buy(symbol, quantity=1)
```

### 事件系统
```python
# 注册事件处理器
broker.register_event_handler(EventType.ORDER, self.on_order)
broker.register_event_handler(EventType.FILL, self.on_fill)
```

## 🤝 贡献指南
1. Fork 项目
2. 创建特性分支 (git checkout -b feature/AmazingFeature)
3. 提交更改 (git commit -m 'Add some AmazingFeature')
4. 推送到分支 (git push origin feature/AmazingFeature)
5. 开启 Pull Request

## 📄 许可证
本项目采用 MIT 许可证 - 查看 LICENSE 文件了解详情