"""
Donchian Channel Breakout Strategy — Breakout family.

Logic:
  - LONG when price closes above highest high of last N bars
  - SHORT when price closes below lowest low of last N bars
  - Uses ATR-based stops and targets
  - Optional: ADX filter to avoid trading in low-momentum conditions

Parameters:
  channel_period: int (default 20)
  atr_period:     int (default 14)
  sl_atr_mult:    float (default 1.5)
  tp_atr_mult:    float (default 3.0)
  adx_filter:     bool (default True)
  adx_period:     int (default 14)
  adx_threshold:  float (default 20.0)
  long_only:      bool (default False)
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from app.core.enums import SignalDirection, StrategyFamily
from app.core.models import Signal, StrategyConfig
from app.strategies.base import BaseStrategy, StrategyRegistry


@StrategyRegistry.register
class BreakoutStrategy(BaseStrategy):

    @property
    def name(self) -> str:
        return "DONCHIAN_BREAKOUT"

    @property
    def family(self) -> str:
        return StrategyFamily.BREAKOUT.value

    def default_parameters(self) -> Dict[str, Any]:
        return {
            "channel_period": 20,
            "atr_period": 14,
            "sl_atr_mult": 1.5,
            "tp_atr_mult": 3.0,
            "adx_filter": True,
            "adx_period": 14,
            "adx_threshold": 20.0,
            "long_only": False,
        }

    def validate_config(self, config: StrategyConfig) -> bool:
        p = config.parameters
        if p.get("channel_period", 20) < 5:
            return False
        if p.get("sl_atr_mult", 1.5) <= 0:
            return False
        if p.get("tp_atr_mult", 3.0) <= 0:
            return False
        return True

    def _minimum_bars(self, config: StrategyConfig) -> int:
        ch = config.parameters.get("channel_period", 20)
        adx = config.parameters.get("adx_period", 14)
        return max(ch, adx) * 2 + 10

    def _compute_signal(
        self, data: pd.DataFrame, config: StrategyConfig
    ) -> Optional[Signal]:
        p = config.parameters
        ch_period = int(p.get("channel_period", 20))
        atr_period = int(p.get("atr_period", 14))
        sl_mult = float(p.get("sl_atr_mult", 1.5))
        tp_mult = float(p.get("tp_atr_mult", 3.0))
        adx_filter = bool(p.get("adx_filter", True))
        adx_period = int(p.get("adx_period", 14))
        adx_threshold = float(p.get("adx_threshold", 20.0))
        long_only = bool(p.get("long_only", False))

        close = data["close"]
        high = data["high"]
        low = data["low"]

        # Donchian channels (exclude current bar to avoid look-ahead)
        upper = high.iloc[-(ch_period + 1):-1].max()
        lower = low.iloc[-(ch_period + 1):-1].min()

        current_close = close.iloc[-1]
        prev_close = close.iloc[-2]

        # ATR
        prev_c = close.shift(1)
        tr = pd.concat([
            high - low,
            (high - prev_c).abs(),
            (low - prev_c).abs(),
        ], axis=1).max(axis=1)
        atr_series = tr.ewm(alpha=1.0 / atr_period, min_periods=atr_period, adjust=False).mean()
        current_atr = atr_series.iloc[-1]

        if pd.isna(current_atr) or current_atr <= 0:
            return None

        # ADX filter
        if adx_filter:
            adx = self._compute_adx(high, low, close, adx_period)
            if adx < adx_threshold:
                return None  # not enough directional momentum

        entry = current_close

        # Upside breakout
        if prev_close <= upper and current_close > upper:
            sl = entry - current_atr * sl_mult
            tp = entry + current_atr * tp_mult
            return self._make_signal(
                config, SignalDirection.LONG, entry, sl, tp, current_atr,
                reason=f"Upside breakout above {upper:.2f} (Donchian {ch_period})",
            )

        # Downside breakout
        if not long_only and prev_close >= lower and current_close < lower:
            sl = entry + current_atr * sl_mult
            tp = entry - current_atr * tp_mult
            return self._make_signal(
                config, SignalDirection.SHORT, entry, sl, tp, current_atr,
                reason=f"Downside breakout below {lower:.2f} (Donchian {ch_period})",
            )

        return None

    @staticmethod
    def _compute_adx(
        high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
    ) -> float:
        """
        Simplified ADX computation (Wilder smoothing).
        Returns the last ADX value.
        """
        if len(high) < period * 2:
            return 0.0

        up_move = high.diff()
        down_move = -low.diff()

        plus_dm = pd.Series(
            np.where((up_move > down_move) & (up_move > 0), up_move, 0.0),
            index=high.index,
        )
        minus_dm = pd.Series(
            np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
            index=high.index,
        )

        prev_close = close.shift(1)
        tr = pd.concat([
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ], axis=1).max(axis=1)

        atr = tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
        plus_di = 100 * (plus_dm.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean() / atr)
        minus_di = 100 * (minus_dm.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean() / atr)

        dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
        adx = dx.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

        return float(adx.iloc[-1]) if not pd.isna(adx.iloc[-1]) else 0.0
