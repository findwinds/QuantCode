# config/futures_config.py
from pathlib import Path
from typing import Dict
import yaml


class FuturesConfigError(Exception):
    """期货配置错误"""
    pass


class FuturesConfig:
    def __init__(self, config_path: str = "config/futures_config.yaml"):
        self.config_path = Path(config_path)
        self.configs: Dict[str, dict] = {}
        
        # 直接加载配置，如果失败就报错
        self.load_config()
        
    def load_config(self):
        """加载配置文件，如果没有文件则抛出异常"""
        if not self.config_path.exists():
            raise FuturesConfigError(
                f"期货配置文件不存在: {self.config_path.absolute()}\n"
                f"请创建配置文件，或指定正确的配置文件路径。\n"
                f"示例配置文件内容:\n"
                f"RB:\n"
                f"  name: '螺纹钢'\n"
                f"  trading_unit: 10\n"
                f"  margin_rate: 0.12\n"
                f"  commission_rate: 0.0001\n"
                f"  min_commission: 1.0\n"
                f"  price_tick: 1.0"
            )
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                loaded_configs = yaml.safe_load(f)
                
            if not loaded_configs:
                raise FuturesConfigError(f"配置文件为空: {self.config_path}")
                
            self.configs = loaded_configs
            
        except yaml.YAMLError as e:
            raise FuturesConfigError(f"配置文件格式错误: {e}")
        except Exception as e:
            raise FuturesConfigError(f"加载配置文件失败: {e}")

    def get_config(self, symbol: str) -> dict:
        """获取品种配置"""
        # 提取基础品种代码（如 RB2310 -> RB）
        base_symbol = ''.join(filter(str.isalpha, symbol))
        
        # 检查是否有该品种配置
        if base_symbol in self.configs:
            return self.configs[base_symbol]
        
        # 没有找到配置，抛出异常
        raise FuturesConfigError(
            f"未找到品种 '{symbol}' (基础代码: '{base_symbol}') 的配置。\n"
            f"请检查配置文件 {self.config_path}，确认是否配置了该品种。\n"
            f"已配置的品种: {', '.join(self.configs.keys())}"
        )
    
    def calculate_margin(self, symbol: str, price: float, quantity: int) -> float:
        """计算保证金"""
        config = self.get_config(symbol)
        
        # 验证必要字段
        required_fields = ['trading_unit', 'margin_rate']
        for field in required_fields:
            if field not in config:
                raise FuturesConfigError(f"配置中缺少必要字段 '{field}' for {symbol}")
        
        contract_value = price * config['trading_unit'] * quantity
        return contract_value * config['margin_rate']
    
    def calculate_commission(self, symbol: str, trade_value: float) -> float:
        """计算手续费"""
        config = self.get_config(symbol)
        
        # 验证必要字段
        required_fields = ['commission_rate', 'min_commission']
        for field in required_fields:
            if field not in config:
                raise FuturesConfigError(f"配置中缺少必要字段 '{field}' for {symbol}")
        
        commission = trade_value * config['commission_rate']
        return max(commission, config['min_commission'])
    
    def get_all_symbols(self) -> list:
        """获取所有已配置的品种代码"""
        return list(self.configs.keys())
    
    def validate_config(self, symbol: str = None) -> bool:
        """验证配置完整性"""
        if symbol:
            config = self.get_config(symbol)
            required_fields = ['trading_unit', 'margin_rate', 'commission_rate', 'min_commission', 'price_tick']
            for field in required_fields:
                if field not in config:
                    raise FuturesConfigError(f"品种 '{symbol}' 配置缺少字段 '{field}'")
            return True
        else:
            # 验证所有品种
            for sym in self.configs.keys():
                self.validate_config(sym)
            return True