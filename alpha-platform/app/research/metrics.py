"""
Backtest performance metrics.

All functions take a list of trade records and return scalar metrics.
Trade record format: dict with keys:
  entry_price, exit_price, direction (LONG/SHORT), quantity,
  entry_time, exit_time, pnl (realized)

Functions are pure — no side effects.
"""
from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from app.core.constants import MIN_TRADES_FOR_METRICS
from app.core.exceptions import InsufficientTradesError

logger = logging.getLogger(__name__)


def compute_all_metrics(
    trades: List[Dict[str, Any]],
    equity_curve: Optional[pd.Series] = None,
    risk_free_rate: float = 0.0,
) -> Dict[str, float]:
    """
    Compute all standard metrics from a list of closed trades.
    Returns a dict of metric_name → value.
    Raises InsufficientTradesError if too few trades.
    """
    if len(trades) < MIN_TRADES_FOR_METRICS:
        raise InsufficientTradesError(
            f"Only {len(trades)} trades. Minimum {MIN_TRADES_FOR_METRICS} required."
        )

    pnls = np.array([t["pnl"] for t in trades])
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]

    total_return = float(pnls.sum())
    total_trades = len(trades)
    win_rate = len(wins) / total_trades if total_trades else 0.0
    avg_win = float(wins.mean()) if len(wins) else 0.0
    avg_loss = float(losses.mean()) if len(losses) else 0.0  # negative number
    expectancy = compute_expectancy(win_rate, avg_win, avg_loss)
    profit_factor = compute_profit_factor(wins, losses)
    max_dd = compute_max_drawdown(pnls)

    if equity_curve is not None:
        sharpe = compute_sharpe(equity_curve.pct_change().dropna(), risk_free_rate)
        sortino = compute_sortino(equity_curve.pct_change().dropna(), risk_free_rate)
    else:
        # Build equity curve from pnls
        eq = pd.Series(pnls).cumsum() + 10000.0  # assume 10k start
        sharpe = compute_sharpe(eq.pct_change().dropna(), risk_free_rate)
        sortino = compute_sortino(eq.pct_change().dropna(), risk_free_rate)

    recovery_factor = total_return / abs(max_dd) if max_dd != 0 else 0.0
    avg_trade = total_return / total_trades if total_trades else 0.0

    return {
        "total_return": total_return,
        "total_trades": total_trades,
        "win_rate": win_rate,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "expectancy": expectancy,
        "profit_factor": profit_factor,
        "max_drawdown": max_dd,
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "recovery_factor": recovery_factor,
        "avg_trade": avg_trade,
    }


def compute_profit_factor(
    wins: np.ndarray, losses: np.ndarray
) -> float:
    """
    Profit Factor = Gross Profit / Gross Loss.
    Returns 0.0 if no losses; infinity capped at 99.0.
    """
    gross_profit = wins.sum() if len(wins) else 0.0
    gross_loss = abs(losses.sum()) if len(losses) else 0.0
    if gross_loss == 0:
        return 99.0 if gross_profit > 0 else 0.0
    return round(gross_profit / gross_loss, 4)


def compute_max_drawdown(pnls: np.ndarray) -> float:
    """
    Maximum drawdown from the cumulative PnL curve.
    Returns the worst peak-to-trough decline (negative number).
    """
    cumulative = np.cumsum(pnls)
    running_max = np.maximum.accumulate(cumulative)
    drawdowns = cumulative - running_max
    return float(drawdowns.min())


def compute_sharpe(
    returns: pd.Series, risk_free_rate: float = 0.0, annualize: int = 252
) -> float:
    """
    Sharpe ratio. Annualized by default (daily returns assumed).
    """
    excess = returns - risk_free_rate / annualize
    std = returns.std()
    if std == 0 or math.isnan(std):
        return 0.0
    return float((excess.mean() / std) * math.sqrt(annualize))


def compute_sortino(
    returns: pd.Series, risk_free_rate: float = 0.0, annualize: int = 252
) -> float:
    """
    Sortino ratio. Uses downside deviation.
    """
    excess = returns - risk_free_rate / annualize
    downside = returns[returns < 0]
    downside_std = downside.std()
    if downside_std == 0 or math.isnan(downside_std) or len(downside) == 0:
        return 0.0
    return float((excess.mean() / downside_std) * math.sqrt(annualize))


def compute_expectancy(
    win_rate: float, avg_win: float, avg_loss: float
) -> float:
    """
    Expectancy per trade = (WR * avg_win) + ((1-WR) * avg_loss).
    avg_loss should be negative.
    """
    return (win_rate * avg_win) + ((1 - win_rate) * avg_loss)


def compute_robustness_score(
    metrics: Dict[str, float],
    oos_metrics: Optional[Dict[str, float]] = None,
    wf_consistency: float = 0.0,
) -> float:
    """
    Compute a composite robustness score in [0, 1].

    Components (see constants.py for weights):
      - Profit factor (capped at 3.0 for scoring)
      - Sharpe ratio (capped at 3.0)
      - Max drawdown (penalty)
      - Expectancy (normalized)
      - Win rate (moderate, not dominant)
      - OOS degradation (how much OOS underperforms IS)
      - Walk-forward consistency

    Returns a float in [0.0, 1.0].
    Higher is better. 0.70+ = ROBUST, 0.50+ = ACCEPTABLE, else FRAGILE.
    """
    from app.core.constants import (
        ROBUSTNESS_WEIGHT_PROFIT_FACTOR,
        ROBUSTNESS_WEIGHT_SHARPE,
        ROBUSTNESS_WEIGHT_MAX_DD,
        ROBUSTNESS_WEIGHT_WIN_RATE,
        ROBUSTNESS_WEIGHT_EXPECTANCY,
        ROBUSTNESS_WEIGHT_OOS_DEGRADATION,
        ROBUSTNESS_WEIGHT_WF_CONSISTENCY,
    )

    score = 0.0

    # Profit factor: map [1.0 → 3.0] → [0 → 1]
    pf = metrics.get("profit_factor", 0.0)
    pf_score = min(max((pf - 1.0) / 2.0, 0.0), 1.0)
    score += pf_score * ROBUSTNESS_WEIGHT_PROFIT_FACTOR

    # Sharpe: map [0 → 3] → [0 → 1]
    sharpe = metrics.get("sharpe_ratio", 0.0)
    sharpe_score = min(max(sharpe / 3.0, 0.0), 1.0)
    score += sharpe_score * ROBUSTNESS_WEIGHT_SHARPE

    # Max drawdown: penalty. map [0 → -0.5] → [1 → 0]
    max_dd = metrics.get("max_drawdown", 0.0)
    dd_pct = abs(max_dd) / 10000.0  # normalize vs 10k start
    dd_score = max(1.0 - dd_pct * 4.0, 0.0)
    score += dd_score * ROBUSTNESS_WEIGHT_MAX_DD

    # Win rate: gentle component [0.3 → 0.7] → [0 → 1]
    wr = metrics.get("win_rate", 0.0)
    wr_score = min(max((wr - 0.30) / 0.40, 0.0), 1.0)
    score += wr_score * ROBUSTNESS_WEIGHT_WIN_RATE

    # Expectancy: map [0 → 200] → [0 → 1]
    exp = metrics.get("expectancy", 0.0)
    exp_score = min(max(exp / 200.0, 0.0), 1.0)
    score += exp_score * ROBUSTNESS_WEIGHT_EXPECTANCY

    # OOS degradation
    if oos_metrics:
        is_pf = metrics.get("profit_factor", 1.0)
        oos_pf = oos_metrics.get("profit_factor", 0.0)
        degradation = (is_pf - oos_pf) / max(is_pf, 0.001)
        oos_score = max(1.0 - degradation, 0.0)
    else:
        oos_score = 0.5  # neutral if no OOS data
    score += oos_score * ROBUSTNESS_WEIGHT_OOS_DEGRADATION

    # Walk-forward consistency
    wf_score = min(max(wf_consistency, 0.0), 1.0)
    score += wf_score * ROBUSTNESS_WEIGHT_WF_CONSISTENCY

    return round(min(max(score, 0.0), 1.0), 4)


def label_robustness(score: float, n_trades: int) -> str:
    """Map a robustness score to a RobustnessLabel string."""
    from app.core.constants import (
        MIN_TRADES_FOR_ROBUST_LABEL,
        ROBUSTNESS_ACCEPTABLE_THRESHOLD,
        ROBUSTNESS_FRAGILE_THRESHOLD,
        ROBUSTNESS_ROBUST_THRESHOLD,
    )
    from app.core.enums import RobustnessLabel

    if n_trades < MIN_TRADES_FOR_ROBUST_LABEL:
        return RobustnessLabel.INSUFFICIENT_DATA.value
    if score >= ROBUSTNESS_ROBUST_THRESHOLD:
        return RobustnessLabel.ROBUST.value
    if score >= ROBUSTNESS_ACCEPTABLE_THRESHOLD:
        return RobustnessLabel.ACCEPTABLE.value
    if score >= ROBUSTNESS_FRAGILE_THRESHOLD:
        return RobustnessLabel.FRAGILE.value
    return RobustnessLabel.OVERFIT.value
