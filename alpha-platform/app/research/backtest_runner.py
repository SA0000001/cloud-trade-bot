"""
Backtest runner — bar-by-bar event-driven simulation.

No look-ahead bias: signal generated on close of bar N,
trade entered at open of bar N+1 (simulated as close + slippage).
Commission and slippage applied on both entry and exit.
One position at a time per strategy instance.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from app.core.enums import SignalDirection
from app.core.exceptions import BacktestError, InsufficientTradesError
from app.core.interfaces import IBacktestRunner, IStrategy
from app.core.models import BacktestResult, StrategyConfig
from app.research.metrics import (
    compute_all_metrics,
    compute_robustness_score,
    label_robustness,
)

logger = logging.getLogger(__name__)


class SimpleBacktestRunner(IBacktestRunner):
    """
    Bar-by-bar backtest simulator.

    Rules:
    - One position at a time (flat before new entry).
    - SL/TP checked every bar; exit at next-bar open (≈ close + slippage).
    - Commission applied as pct of trade value on entry AND exit.
    - Slippage applied as pct of price (adverse direction).
    """

    def run(
        self,
        strategy: IStrategy,
        data: pd.DataFrame,
        config: StrategyConfig,
        commission_pct: float = 0.001,
        slippage_pct: float = 0.0005,
    ) -> BacktestResult:
        if len(data) < 50:
            raise BacktestError(f"Not enough data: {len(data)} bars (min 50)")

        # ── Normalise: work with a copy that has integer index + ts column ──
        df = data.copy()
        if df.index.name in (None, "timestamp") or isinstance(df.index, pd.DatetimeIndex):
            df = df.reset_index()
            # After reset_index the former index becomes the first column.
            # Normalise its name to "timestamp".
            first_col = df.columns[0]
            if first_col != "timestamp":
                df.rename(columns={first_col: "timestamp"}, inplace=True)
        df.columns = [c.lower() for c in df.columns]

        trades: List[Dict[str, Any]] = []
        equity: float = 10000.0
        open_trade: Optional[Dict[str, Any]] = None
        equity_curve: List[float] = [equity]

        for i in range(1, len(df)):
            bar = df.iloc[i]
            prev_bars = df.iloc[: i + 1].copy()
            # Strategy expects DatetimeIndex — restore it for signal computation
            if "timestamp" in prev_bars.columns:
                prev_bars = prev_bars.set_index("timestamp")

            # ── Check exit on open trade ──
            if open_trade is not None:
                direction = open_trade["direction"]
                sl = open_trade["stop_loss"]
                tp = open_trade["take_profit"]
                lo = float(bar["low"])
                hi = float(bar["high"])

                hit_sl = (lo <= sl) if direction == "LONG" else (hi >= sl)
                hit_tp = (hi >= tp) if direction == "LONG" else (lo <= tp)

                if hit_sl or hit_tp:
                    exit_price = tp if hit_tp else sl
                    exit_price = self._slippage(exit_price, direction, slippage_pct, entry=False)
                    fee_out = exit_price * commission_pct
                    qty = open_trade["qty"]
                    if direction == "LONG":
                        pnl = (exit_price - open_trade["entry_price"]) * qty - fee_out - open_trade["fee_in"]
                    else:
                        pnl = (open_trade["entry_price"] - exit_price) * qty - fee_out - open_trade["fee_in"]

                    equity += pnl
                    trades.append({
                        "pnl": pnl,
                        "entry_price": open_trade["entry_price"],
                        "exit_price": exit_price,
                        "direction": direction,
                        "quantity": qty,
                        "entry_time": open_trade["entry_time"],
                        "exit_time": bar.get("timestamp", i),
                        "exit_reason": "TP" if hit_tp else "SL",
                    })
                    open_trade = None
                    equity_curve.append(equity)
                    continue

            # ── Generate signal on current bar close ──
            if open_trade is None:
                try:
                    signal = strategy.generate_signal(prev_bars, config)
                except Exception as exc:
                    logger.debug("Strategy error bar %d: %s", i, exc)
                    signal = None

                if signal and signal.direction not in (
                    SignalDirection.FLAT, SignalDirection.FLAT.value, "FLAT"
                ):
                    direction_str = (
                        signal.direction.value
                        if hasattr(signal.direction, "value")
                        else str(signal.direction)
                    )
                    raw_price = float(bar["close"])
                    entry_price = self._slippage(raw_price, direction_str, slippage_pct, entry=True)
                    fee_in = entry_price * commission_pct
                    qty = equity / entry_price  # full notional, no leverage

                    open_trade = {
                        "direction": direction_str,
                        "entry_price": entry_price,
                        "fee_in": fee_in,
                        "stop_loss": signal.stop_loss,
                        "take_profit": signal.take_profit,
                        "qty": qty,
                        "entry_time": bar.get("timestamp", i),
                    }

            equity_curve.append(equity)

        # ── Close any remaining trade at last bar ──
        if open_trade is not None:
            last_bar = df.iloc[-1]
            exit_price = float(last_bar["close"])
            direction = open_trade["direction"]
            fee_out = exit_price * commission_pct
            qty = open_trade["qty"]
            pnl = (
                (exit_price - open_trade["entry_price"]) * qty - fee_out - open_trade["fee_in"]
                if direction == "LONG"
                else (open_trade["entry_price"] - exit_price) * qty - fee_out - open_trade["fee_in"]
            )
            equity += pnl
            trades.append({"pnl": pnl, "entry_price": open_trade["entry_price"],
                           "exit_price": exit_price, "direction": direction,
                           "quantity": qty, "exit_reason": "END_OF_DATA"})

        # ── Build result ──
        result = BacktestResult(
            strategy_name=strategy.name,
            asset=config.asset,
            timeframe=config.timeframe,
            parameters=config.parameters,
            total_trades=len(trades),
            period_start=df["timestamp"].iloc[0] if "timestamp" in df.columns else None,
            period_end=df["timestamp"].iloc[-1] if "timestamp" in df.columns else None,
        )

        if len(trades) < 2:
            logger.warning("%s: only %d trades — skipping metric computation", strategy.name, len(trades))
            return result

        try:
            eq_series = pd.Series(equity_curve)
            raw = compute_all_metrics(trades, equity_curve=eq_series)
            result.total_return_pct  = raw["total_return"] / 10000.0
            result.profit_factor     = raw["profit_factor"]
            result.sharpe_ratio      = raw["sharpe_ratio"]
            result.sortino_ratio     = raw["sortino_ratio"]
            result.max_drawdown_pct  = raw["max_drawdown"] / 10000.0
            result.recovery_factor   = raw["recovery_factor"]
            result.expectancy        = raw["expectancy"]
            result.win_rate          = raw["win_rate"]
            result.avg_win           = raw["avg_win"]
            result.avg_loss          = raw["avg_loss"]
            rob                      = compute_robustness_score(raw)
            result.robustness_score  = rob
            result.robustness_label  = label_robustness(rob, len(trades))  # type: ignore
        except InsufficientTradesError as exc:
            logger.info("Insufficient trades for full metrics: %s", exc)

        return result

    @staticmethod
    def _slippage(price: float, direction: str, pct: float, entry: bool) -> float:
        """Slippage is always adverse: entries worse, exits worse."""
        if direction == "LONG":
            factor = (1 + pct) if entry else (1 - pct)
        else:
            factor = (1 - pct) if entry else (1 + pct)
        return price * factor
