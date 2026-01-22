# src/backtest/engine.py
import pandas as pd
import numpy as np

class SimpleEngine:
    """
    实盘级回测引擎：支持加仓/减仓（不平仓重开），仅调整仓位差值
    - 核心优化：仓位调整仅处理「目标仓位与当前仓位的差值」，避免重复平仓开仓
    - signal=0：不交易，维持当前仓位，仅更新浮盈
    - signal≠0：触发交易检查
      - target≠当前仓位：计算仓位差值，仅调整差值部分（加仓/减仓/反手）
      - target=当前仓位：不交易，仅更新浮盈
    """
    def __init__(self, cash: float = 100_000,
                 comm: float = 0.0002,  # 手续费率（成交金额的比例）
                 margin_ratio: float = 0.12,  # 保证金率（持仓市值的比例）
                 contract_multiplier: int = 10,  # 合约乘数
                 slip: float = 1.0):  # 滑点（每单位价格，做多+滑点，做空-滑点）
        self.init_cash = cash
        self.comm = comm
        self.margin_ratio = margin_ratio
        self.multiplier = contract_multiplier
        self.slip = slip

    def _calculate_volume(self, cash: float, price: float, position_ratio: float) -> int:
        """
        计算指定仓位比例对应的合约数量
        :param cash: 可用现金
        :param price: 成交价格
        :param position_ratio: 仓位比例（1.0=满仓，0.5=半仓）
        :return: 合约数量
        """
        if position_ratio == 0:
            return 0
        # 保证金 = 价格 * 合约乘数 * 合约数量 * 保证金率
        # 可用现金的95%用于开仓（留5%缓冲）
        available_cash = cash * 0.95
        margin_per_contract = price * self.multiplier * self.margin_ratio
        max_volume = int(available_cash / margin_per_contract)
        # 按仓位比例计算合约数量
        target_volume = int(max_volume * abs(position_ratio))
        return max(target_volume, 1)  # 至少1手

    def run(self, signal_df: pd.DataFrame) -> pd.DataFrame:
        """
        执行交易过程模拟（支持加仓/减仓，不平仓重开）
        :param signal_df: 包含OHLCV + signal(交易信号) + target(目标仓位百分比)的DataFrame
        :return: 新增账户状态列的DataFrame
        """
        # 复制数据避免修改原数据，重置索引方便遍历
        df = signal_df.copy().reset_index(drop=False)
        
        # 检查必要列
        required_cols = ['open', 'high', 'low', 'close', 'signal', 'target']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"输入数据缺少必要列：{missing_cols}，必须包含{required_cols}")
        
        # 初始化账户状态列
        df['cash'] = self.init_cash  # 可用现金
        df['equity'] = self.init_cash  # 账户总权益（现金 + 持仓盈亏）
        df['position'] = 0.0  # 当前持仓仓位百分比（1.0=满仓多，-1.0=满仓空，0=空仓）
        df['holding_volume'] = 0  # 当前持仓合约数量
        df['holding_price'] = np.nan  # 持仓均价
        df['holding_pnl'] = 0.0  # 持仓浮盈/浮亏
        df['trade_pnl'] = 0.0  # 本次交易实际盈亏（平仓部分）
        df['commission'] = 0.0  # 本次交易手续费
        df['trade_price'] = np.nan  # 成交价格（含滑点）
        df['trade_volume'] = 0  # 本次交易合约数量
        df['is_trade'] = False  # 是否发生交易
        
        # 初始化运行变量
        current_position = 0.0  # 当前持仓仓位百分比
        current_cash = self.init_cash  # 当前可用现金
        holding_volume = 0  # 当前持仓合约数量
        holding_price = np.nan  # 持仓均价

        # 逐行模拟交易（从第1行开始）
        for i in range(1, len(df)):
            row = df.iloc[i]
            signal = row['signal']       # 交易信号（0=不交易，±1=触发交易）
            target_pos = row['target']   # 目标仓位百分比
            
            # 初始化本行交易相关变量
            trade_price = np.nan
            trade_volume = 0
            trade_pnl = 0.0
            commission = 0.0
            is_trade = False
            
            # 核心逻辑1：signal≠0 时触发交易检查
            if signal != 0 and target_pos != current_position:
                is_trade = True
                
                # 步骤1：计算目标合约数量和当前合约数量
                # 成交价格（基于开盘价+滑点）
                if target_pos > 0:  # 做多/加仓多
                    trade_price = row['open'] + self.slip
                elif target_pos < 0:  # 做空/加仓空
                    trade_price = row['open'] - self.slip
                else:  # 平仓（target=0）
                    trade_price = row['open'] + (self.slip if current_position < 0 else -self.slip)
                
                # 目标合约数量（基于目标仓位比例）
                target_volume = self._calculate_volume(current_cash, trade_price, target_pos)
                # 当前合约数量
                current_volume = holding_volume
                
                # 步骤2：处理仓位调整（分场景）
                if current_position == 0:
                    # 场景1：空仓→开仓（直接开仓）
                    trade_volume = target_volume
                    # 开仓手续费
                    commission = trade_price * self.multiplier * trade_volume * self.comm
                    current_cash -= commission
                    # 更新持仓
                    holding_price = trade_price
                    holding_volume = trade_volume
                
                elif target_pos == 0:
                    # 场景2：平仓（直接平全部仓位）
                    trade_volume = current_volume
                    # 平仓盈亏
                    trade_pnl = (trade_price - holding_price) * self.multiplier * trade_volume * current_position
                    # 平仓手续费
                    commission = trade_price * self.multiplier * trade_volume * self.comm
                    # 更新现金
                    current_cash += trade_pnl - commission
                    # 重置持仓
                    holding_price = np.nan
                    holding_volume = 0
                
                elif np.sign(current_position) == np.sign(target_pos):
                    # 场景3：同方向加仓/减仓
                    volume_diff = target_volume - current_volume
                    if volume_diff > 0:
                        # 加仓：仅开仓差值部分
                        trade_volume = volume_diff
                        # 加仓手续费
                        commission = trade_price * self.multiplier * trade_volume * self.comm
                        current_cash -= commission
                        # 计算新的持仓均价（加权平均）
                        new_holding_value = (holding_price * holding_volume) + (trade_price * trade_volume)
                        holding_volume += trade_volume
                        holding_price = new_holding_value / holding_volume
                    elif volume_diff < 0:
                        # 减仓：仅平仓差值部分（绝对值）
                        trade_volume = abs(volume_diff)
                        # 减仓盈亏
                        trade_pnl = (trade_price - holding_price) * self.multiplier * trade_volume * current_position
                        # 减仓手续费
                        commission = trade_price * self.multiplier * trade_volume * self.comm
                        # 更新现金
                        current_cash += trade_pnl - commission
                        # 更新持仓
                        holding_volume -= trade_volume
                        if holding_volume == 0:
                            holding_price = np.nan
                
                else:
                    # 场景4：反手（先平仓全部，再开仓新方向）
                    # 第一步：平仓原有仓位
                    close_volume = current_volume
                    close_pnl = (trade_price - holding_price) * self.multiplier * close_volume * current_position
                    close_commission = trade_price * self.multiplier * close_volume * self.comm
                    current_cash += close_pnl - close_commission
                    
                    # 第二步：开仓新方向
                    open_volume = target_volume
                    open_commission = trade_price * self.multiplier * open_volume * self.comm
                    current_cash -= open_commission
                    
                    # 汇总交易数据
                    trade_volume = close_volume + open_volume
                    trade_pnl = close_pnl
                    commission = close_commission + open_commission
                    
                    # 更新持仓
                    holding_price = trade_price
                    holding_volume = open_volume
                
                # 步骤3：更新当前仓位
                current_position = target_pos
            
            # 核心逻辑2：计算持仓浮盈（无论是否交易，有持仓就计算）
            holding_pnl = 0.0
            if holding_volume > 0 and not np.isnan(holding_price):
                holding_pnl = (row['close'] - holding_price) * self.multiplier * holding_volume * np.sign(current_position)
            
            # 核心逻辑3：更新本行账户状态到DataFrame
            df.at[i, 'cash'] = current_cash
            df.at[i, 'position'] = current_position
            df.at[i, 'holding_volume'] = holding_volume
            df.at[i, 'holding_price'] = holding_price
            df.at[i, 'holding_pnl'] = holding_pnl
            df.at[i, 'equity'] = current_cash + holding_pnl
            df.at[i, 'trade_price'] = trade_price
            df.at[i, 'trade_volume'] = trade_volume
            df.at[i, 'trade_pnl'] = trade_pnl
            df.at[i, 'commission'] = commission
            df.at[i, 'is_trade'] = is_trade
        
        # 填充首行的账户状态
        df.iloc[0, df.columns.get_loc('cash')] = self.init_cash
        df.iloc[0, df.columns.get_loc('equity')] = self.init_cash
        df.iloc[0, df.columns.get_loc('position')] = 0.0
        df.iloc[0, df.columns.get_loc('holding_volume')] = 0
        
        return df