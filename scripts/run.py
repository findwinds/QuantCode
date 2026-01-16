# scripts/run.py
import sys, os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.strategy import sma_strategy

fake_prices = [100, 102, 101, 105, 107]
print("signal:", sma_strategy(fake_prices))