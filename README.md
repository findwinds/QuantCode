# QuantCode

```
# 基本使用
python scripts/run_with_engine.py --symbol RB0 --use-akshare

# 多品种
python scripts/run_with_engine.py --symbol RB0 --symbol AG0 --use-akshare

# 期货策略
python scripts/run_with_engine.py --symbol RB0 --use-akshare --strategy futures_dual_ma --position 1

# 自定义参数
python scripts/run_with_engine.py --symbol RB0 --use-akshare --fast 5 --slow 20 --position 2

# 保存结果
python scripts/run_with_engine.py --symbol RB0 --use-akshare --output ./results
```