"""
RSI Mean Reversion Strategy — Mean Reversion family.

Logic:
  - LONG when RSI drops below oversold threshold (default 30)
    AND price is near a Bollinger Band lower boundary
  - SHORT when RSI rises above overbought threshold (default 70)
    AND price is near Bollinger Band upper boundary
  - Tighter stops than trend strategies (mean reversion assumes quick snaps)

Parameters:
  rsi_period:      int (default 14)
  rsi_oversold:    float (default 30)
  rsi_overbought:  float (default 70)
  bb_period:       int (default 20)
  bb_std:          float (default 2.0)
  atr_period:      int (default 14)
  sl_atr_mult:     float (default 1.5)
  tp_atr_mult:     float (default 2.0)
  long_only:       bool (default False)
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import pandas as pd

from app.core.enums import SignalDirection, StrategyFamily
from app.core.models import Signal, StrategyConfig
from app.strategies.base import BaseStrategy, StrategyRegistry


@StrategyRegistry.register
class MeanReversionStrategy(BaseStrategy):

    @property
    def name(self) -> str:
        return "RSI_MEAN_REVERSION"

    @property
    def family(self) -> str:
        return StrategyFamily.MEAN_REVERSION.value

    def default_parameters(self) -> Dict[str, Any]:
        return {
            "rsi_period": 14,
            "rsi_oversold": 30,
            "rsi_overbought": 70,
            "bb_period": 20,
            "bb_std": 2.0,
            "atr_period": 14,
            "sl_atr_mult": 1.5,
            "tp_atr_mult": 2.0,
            "long_only": False,
        }

    def validate_config(self, config: StrategyConfig) -> bool:
        p = config.parameters
        if p.get("rsi_oversold", 30) >= p.get("rsi_overbought", 70):
            return False
        if p.get("bb_period", 20) < 5:
            return False
        if p.get("sl_atr_mult", 1.5) <= 0:
            return False
        return True

    def _minimum_bars(self, config: StrategyConfig) -> int:
        bb = config.parameters.get("bb_period", 20)
        rsi = config.parameters.get("rsi_period", 14)
        return max(bb, rsi) + 10

    def _compute_signal(
        self, data: pd.DataFrame, config: StrategyConfig
    ) -> Optional[Signal]:
        p = config.parameters
        rsi_period = int(p.get("rsi_period", 14))
        rsi_oversold = float(p.get("rsi_oversold", 30))
        rsi_overbought = float(p.get("rsi_overbought", 70))
        bb_period = int(p.get("bb_period", 20))
        bb_std_mult = float(p.get("bb_std", 2.0))
        atr_period = int(p.get("atr_period", 14))
        sl_mult = float(p.get("sl_atr_mult", 1.5))
        tp_mult = float(p.get("tp_atr_mult", 2.0))
        long_only = bool(p.get("long_only", False))

        close = data["close"]
        high = data["high"]
        low = data["low"]

        # RSI
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        avg_gain = gain.ewm(alpha=1.0 / rsi_period, min_periods=rsi_period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1.0 / rsi_period, min_periods=rsi_period, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, float("nan"))
        rsi = 100 - (100 / (1 + rs))

        # Bollinger Bands
        bb_mean = close.rolling(bb_period).mean()
        bb_std = close.rolling(bb_period).std()
        bb_upper = bb_mean + bb_std_mult * bb_std
        bb_lower = bb_mean - bb_std_mult * bb_std

        # ATR
        prev_close = close.shift(1)
        tr = pd.concat([
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ], axis=1).max(axis=1)
        atr_series = tr.ewm(alpha=1.0 / atr_period, min_periods=atr_period, adjust=False).mean()

        current_rsi = rsi.iloc[-1]
        current_close = close.iloc[-1]
        current_bb_lower = bb_lower.iloc[-1]
        current_bb_upper = bb_upper.iloc[-1]
        current_atr = atr_series.iloc[-1]

        if any(pd.isna(v) for v in [current_rsi, current_bb_lower, current_bb_upper, current_atr]):
            return None
        if current_atr <= 0:
            return None

        entry = current_close

        # Oversold + near lower band → LONG
        if current_rsi < rsi_oversold and current_close <= current_bb_lower * 1.01:
            sl = entry - current_atr * sl_mult
            tp = bb_mean.iloc[-1]  # TP at mean
            tp = max(tp, entry + current_atr * tp_mult)  # ensure minimum RR
            return self._make_signal(
                config, SignalDirection.LONG, entry, sl, tp, current_atr,
                reason=f"RSI={current_rsi:.1f} oversold, price near BB lower ({current_bb_lower:.2f})",
            )

        # Overbought + near upper band → SHORT
        if not long_only and current_rsi > rsi_overbought and current_close >= current_bb_upper * 0.99:
            sl = entry + current_atr * sl_mult
            tp = bb_mean.iloc[-1]
            tp = min(tp, entry - current_atr * tp_mult)
            return self._make_signal(
                config, SignalDirection.SHORT, entry, sl, tp, current_atr,
                reason=f"RSI={current_rsi:.1f} overbought, price near BB upper ({current_bb_upper:.2f})",
            )

        return None
