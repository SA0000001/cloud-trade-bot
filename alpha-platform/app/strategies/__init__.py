"""
app.strategies — Import this package to auto-register all strategies.

Usage:
    import app.strategies  # triggers registration
    from app.strategies.base import StrategyRegistry
    names = StrategyRegistry.all_names()
"""
# Import all examples to trigger @StrategyRegistry.register decorators
from app.strategies.examples import sma_cross, breakout, mean_reversion  # noqa: F401
from app.strategies.base import BaseStrategy, StrategyRegistry

__all__ = ["BaseStrategy", "StrategyRegistry"]
