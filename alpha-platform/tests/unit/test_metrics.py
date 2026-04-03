"""
Tests for backtest metrics calculations.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from app.research.metrics import (
    compute_all_metrics,
    compute_max_drawdown,
    compute_profit_factor,
    compute_robustness_score,
    compute_sharpe,
    compute_sortino,
    label_robustness,
)
from app.core.exceptions import InsufficientTradesError


def _make_trades(n: int, win_rate: float = 0.55, avg_win: float = 100.0, avg_loss: float = -70.0):
    """Generate synthetic trade records."""
    import random
    random.seed(42)
    trades = []
    for _ in range(n):
        is_win = random.random() < win_rate
        pnl = avg_win if is_win else avg_loss
        trades.append({"pnl": pnl, "entry_price": 100.0, "exit_price": 105.0})
    return trades


class TestComputeMetrics:

    def test_raises_on_insufficient_trades(self):
        with pytest.raises(InsufficientTradesError):
            compute_all_metrics(_make_trades(5))

    def test_returns_all_expected_keys(self):
        trades = _make_trades(50)
        metrics = compute_all_metrics(trades)
        expected_keys = [
            "total_return", "total_trades", "win_rate", "avg_win",
            "avg_loss", "expectancy", "profit_factor", "max_drawdown",
            "sharpe_ratio", "sortino_ratio", "recovery_factor", "avg_trade",
        ]
        for key in expected_keys:
            assert key in metrics, f"Missing key: {key}"

    def test_win_rate_range(self):
        trades = _make_trades(60, win_rate=0.6)
        metrics = compute_all_metrics(trades)
        assert 0.0 <= metrics["win_rate"] <= 1.0

    def test_profit_factor_positive_expectancy(self):
        trades = _make_trades(60, win_rate=0.6, avg_win=150.0, avg_loss=-80.0)
        metrics = compute_all_metrics(trades)
        assert metrics["profit_factor"] > 1.0, "Positive edge should have PF > 1"

    def test_profit_factor_negative_expectancy(self):
        trades = _make_trades(60, win_rate=0.3, avg_win=50.0, avg_loss=-100.0)
        metrics = compute_all_metrics(trades)
        assert metrics["profit_factor"] < 1.0, "Negative edge should have PF < 1"


class TestMaxDrawdown:

    def test_no_drawdown(self):
        pnls = np.array([10.0, 20.0, 30.0, 40.0])
        dd = compute_max_drawdown(pnls)
        assert dd == 0.0

    def test_simple_drawdown(self):
        # Goes up 100, down 50 → drawdown = -50
        pnls = np.array([100.0, -50.0])
        dd = compute_max_drawdown(pnls)
        assert dd == -50.0

    def test_multiple_drawdowns_picks_worst(self):
        pnls = np.array([100.0, -30.0, 50.0, -80.0])
        dd = compute_max_drawdown(pnls)
        assert dd < -70.0  # worst is the second decline from 120 to 40 = -80


class TestProfitFactor:

    def test_no_losses_returns_max(self):
        wins = np.array([100.0, 200.0])
        losses = np.array([])
        pf = compute_profit_factor(wins, losses)
        assert pf == 99.0

    def test_no_wins_returns_zero(self):
        wins = np.array([])
        losses = np.array([-50.0])
        pf = compute_profit_factor(wins, losses)
        assert pf == 0.0

    def test_equal_wins_losses(self):
        wins = np.array([100.0])
        losses = np.array([-100.0])
        pf = compute_profit_factor(wins, losses)
        assert abs(pf - 1.0) < 0.001


class TestSharpe:

    def test_positive_returns_positive_sharpe(self):
        import pandas as pd
        returns = pd.Series([0.01, 0.02, 0.015, 0.01, 0.005] * 10)
        sharpe = compute_sharpe(returns)
        assert sharpe > 0

    def test_zero_std_returns_zero(self):
        import pandas as pd
        returns = pd.Series([0.0] * 50)
        sharpe = compute_sharpe(returns)
        assert sharpe == 0.0


class TestRobustnessScore:

    def test_score_in_range(self):
        metrics = {
            "profit_factor": 2.0,
            "sharpe_ratio": 1.5,
            "max_drawdown": -500.0,
            "win_rate": 0.55,
            "expectancy": 80.0,
        }
        score = compute_robustness_score(metrics)
        assert 0.0 <= score <= 1.0

    def test_excellent_metrics_score_high(self):
        metrics = {
            "profit_factor": 2.8,
            "sharpe_ratio": 2.5,
            "max_drawdown": -200.0,
            "win_rate": 0.62,
            "expectancy": 150.0,
        }
        score = compute_robustness_score(metrics)
        assert score >= 0.60, f"Expected high score, got {score}"

    def test_terrible_metrics_score_low(self):
        metrics = {
            "profit_factor": 0.5,
            "sharpe_ratio": -1.0,
            "max_drawdown": -8000.0,
            "win_rate": 0.25,
            "expectancy": -50.0,
        }
        score = compute_robustness_score(metrics)
        assert score < 0.30, f"Expected low score, got {score}"

    def test_oos_degradation_lowers_score(self):
        metrics = {"profit_factor": 2.5, "sharpe_ratio": 1.8,
                   "max_drawdown": -300.0, "win_rate": 0.58, "expectancy": 100.0}
        oos_metrics = {"profit_factor": 0.8}
        score_with_oos = compute_robustness_score(metrics, oos_metrics=oos_metrics)
        score_no_oos = compute_robustness_score(metrics)
        assert score_with_oos < score_no_oos


class TestLabelRobustness:

    def test_robust_label(self):
        label = label_robustness(0.75, n_trades=60)
        assert label == "ROBUST"

    def test_acceptable_label(self):
        label = label_robustness(0.55, n_trades=60)
        assert label == "ACCEPTABLE"

    def test_fragile_label(self):
        label = label_robustness(0.35, n_trades=60)
        assert label == "FRAGILE"

    def test_insufficient_data_label(self):
        label = label_robustness(0.80, n_trades=10)
        assert label == "INSUFFICIENT_DATA"
