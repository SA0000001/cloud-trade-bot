"""
Strategy base class and global registry.

All strategies must:
  1. Inherit from BaseStrategy
  2. Implement: name, family, generate_signal, validate_config, default_parameters
  3. Register themselves via @StrategyRegistry.register

Registry usage:
    from app.strategies.registry import StrategyRegistry
    strategy = StrategyRegistry.get("SMA_CROSS")
    signal = strategy.generate_signal(data, config)
"""
from __future__ import annotations

import logging
from typing import ClassVar, Dict, Optional, Type

import pandas as pd

from app.core.enums import AssetSymbol, SignalDirection, StrategyFamily, Timeframe
from app.core.exceptions import StrategyConfigError, StrategyNotFoundError
from app.core.interfaces import IStrategy
from app.core.models import Signal, StrategyConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class BaseStrategy(IStrategy):
    """
    Abstract base for all strategies.
    Subclasses only need to implement:
      - name (property)
      - family (property)
      - _compute_signal(data, config) -> Optional[Signal]
      - default_parameters() -> Dict
      - validate_config(config) -> bool
    """

    def generate_signal(
        self,
        data: pd.DataFrame,
        config: StrategyConfig,
    ) -> Optional[Signal]:
        """
        Public entry point. Validates config, checks data length,
        then delegates to _compute_signal.
        """
        if not self.validate_config(config):
            raise StrategyConfigError(
                f"Invalid config for strategy {self.name}: {config.parameters}"
            )

        min_bars = self._minimum_bars(config)
        if len(data) < min_bars:
            logger.debug(
                "%s: not enough bars (%d < %d)", self.name, len(data), min_bars
            )
            return None

        try:
            return self._compute_signal(data, config)
        except Exception as exc:
            logger.error("%s: signal computation error: %s", self.name, exc)
            return None

    def _compute_signal(
        self, data: pd.DataFrame, config: StrategyConfig
    ) -> Optional[Signal]:
        """Override in subclass to produce a Signal."""
        raise NotImplementedError

    def _minimum_bars(self, config: StrategyConfig) -> int:
        """Minimum bars needed. Override if strategy requires more."""
        return 50

    def _make_signal(
        self,
        config: StrategyConfig,
        direction: SignalDirection,
        entry: float,
        stop_loss: float,
        take_profit: float,
        atr: float,
        reason: str = "",
    ) -> Signal:
        """Helper to build a Signal with common fields populated."""
        from app.core.enums import RobustnessLabel
        return Signal(
            asset=config.asset,
            strategy_name=self.name,
            strategy_family=self.family,
            timeframe=config.timeframe,
            direction=direction,
            entry_price=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            atr=atr,
            robustness_label=RobustnessLabel.ACCEPTABLE,
            reason=reason,
        )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class StrategyRegistry:
    """Global strategy registry. Thread-safe for reads after startup."""

    _registry: ClassVar[Dict[str, Type[BaseStrategy]]] = {}

    @classmethod
    def register(cls, strategy_cls: Type[BaseStrategy]) -> Type[BaseStrategy]:
        """Decorator to register a strategy class."""
        name = strategy_cls().name  # instantiate to get name
        cls._registry[name] = strategy_cls
        logger.debug("Registered strategy: %s", name)
        return strategy_cls

    @classmethod
    def get(cls, name: str) -> BaseStrategy:
        """Instantiate and return a strategy by name."""
        if name not in cls._registry:
            available = list(cls._registry.keys())
            raise StrategyNotFoundError(
                f"Strategy '{name}' not found. Available: {available}"
            )
        return cls._registry[name]()

    @classmethod
    def list_all(cls) -> Dict[str, str]:
        """Return {name: family} for all registered strategies."""
        result = {}
        for name, cls_ in cls._registry.items():
            try:
                instance = cls_()
                result[name] = instance.family
            except Exception:
                result[name] = "UNKNOWN"
        return result

    @classmethod
    def all_names(cls) -> list[str]:
        return list(cls._registry.keys())
