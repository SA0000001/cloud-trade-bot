"""
SMA Crossover Strategy — Trend Following.

Logic:
  - LONG when fast SMA crosses above slow SMA (golden cross)
  - SHORT when fast SMA crosses below slow SMA (death cross)
  - Stop loss: entry ± ATR * sl_atr_mult
  - Take profit: entry ± ATR * tp_atr_mult

Parameters:
  fast_period: int (default 10)
  slow_period: int (default 30)
  atr_period:  int (default 14)
  sl_atr_mult: float (default 2.0)
  tp_atr_mult: float (default 3.0)

This is a FRAMEWORK STARTER strategy — not a production signal.
Performance will vary significantly by asset and timeframe.
Run through the research engine before using live.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import pandas as pd

from app.core.enums import SignalDirection, StrategyFamily
from app.core.models import Signal, StrategyConfig
from app.strategies.base import BaseStrategy, StrategyRegistry


@StrategyRegistry.register
class SMAcrossStrategy(BaseStrategy):

    @property
    def name(self) -> str:
        return "SMA_CROSS"

    @property
    def family(self) -> str:
        return StrategyFamily.TREND_FOLLOWING.value

    def default_parameters(self) -> Dict[str, Any]:
        return {
            "fast_period": 10,
            "slow_period": 30,
            "atr_period": 14,
            "sl_atr_mult": 2.0,
            "tp_atr_mult": 3.0,
            "long_only": False,
        }

    def validate_config(self, config: StrategyConfig) -> bool:
        p = config.parameters
        fast = p.get("fast_period", 10)
        slow = p.get("slow_period", 30)
        if fast >= slow:
            return False
        if fast < 2 or slow < 5:
            return False
        if p.get("sl_atr_mult", 2.0) <= 0:
            return False
        if p.get("tp_atr_mult", 3.0) <= 0:
            return False
        return True

    def _minimum_bars(self, config: StrategyConfig) -> int:
        slow = config.parameters.get("slow_period", 30)
        atr = config.parameters.get("atr_period", 14)
        return max(slow, atr) + 5

    def _compute_signal(
        self, data: pd.DataFrame, config: StrategyConfig
    ) -> Optional[Signal]:
        p = config.parameters
        fast_period = int(p.get("fast_period", 10))
        slow_period = int(p.get("slow_period", 30))
        atr_period = int(p.get("atr_period", 14))
        sl_mult = float(p.get("sl_atr_mult", 2.0))
        tp_mult = float(p.get("tp_atr_mult", 3.0))
        long_only = bool(p.get("long_only", False))

        close = data["close"]
        fast_sma = close.rolling(fast_period).mean()
        slow_sma = close.rolling(slow_period).mean()

        # ATR
        high, low, prev_close = data["high"], data["low"], close.shift(1)
        tr = pd.concat([
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1.0 / atr_period, min_periods=atr_period, adjust=False).mean()

        current_atr = atr.iloc[-1]
        if pd.isna(current_atr) or current_atr <= 0:
            return None

        # Crossover detection: bar[-2] had one order, bar[-1] has opposite
        fast_now = fast_sma.iloc[-1]
        fast_prev = fast_sma.iloc[-2]
        slow_now = slow_sma.iloc[-1]
        slow_prev = slow_sma.iloc[-2]

        if any(pd.isna(v) for v in [fast_now, fast_prev, slow_now, slow_prev]):
            return None

        entry = data["close"].iloc[-1]

        # Golden cross: fast crosses above slow
        if fast_prev <= slow_prev and fast_now > slow_now:
            sl = entry - current_atr * sl_mult
            tp = entry + current_atr * tp_mult
            return self._make_signal(
                config, SignalDirection.LONG, entry, sl, tp, current_atr,
                reason=f"Golden cross: fast({fast_period}) crossed above slow({slow_period})",
            )

        # Death cross: fast crosses below slow
        if not long_only and fast_prev >= slow_prev and fast_now < slow_now:
            sl = entry + current_atr * sl_mult
            tp = entry - current_atr * tp_mult
            return self._make_signal(
                config, SignalDirection.SHORT, entry, sl, tp, current_atr,
                reason=f"Death cross: fast({fast_period}) crossed below slow({slow_period})",
            )

        return None
