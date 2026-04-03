"""
Strategy ranking and selection engine.

Selects the best strategy per asset+timeframe combination
based on robustness, not just profit. Explicitly rejects fragile
curve-fitted results.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from app.core.enums import AssetSymbol, RobustnessLabel, Timeframe
from app.core.models import BacktestResult, WalkForwardResult
from app.research.metrics import compute_robustness_score

logger = logging.getLogger(__name__)


class StrategyRanker:
    """
    Ranks candidate strategies and selects the best per asset.

    Ranking criteria (explicit, not profit-only):
    1. Robustness score (composite)
    2. Walk-forward consistency
    3. Out-of-sample profit factor
    4. Max drawdown penalty
    5. Minimum trade count gate
    """

    # Strategies with these labels are REJECTED regardless of profit
    REJECTED_LABELS = {
        RobustnessLabel.OVERFIT.value,
        RobustnessLabel.INSUFFICIENT_DATA.value,
    }

    def rank(
        self,
        results: List[BacktestResult],
        wf_results: Optional[Dict[str, WalkForwardResult]] = None,
    ) -> List[Tuple[BacktestResult, float]]:
        """
        Rank a list of backtest results.

        Returns list of (result, composite_score) sorted descending.
        Fragile/overfit results are included but will rank last.
        """
        scored: List[Tuple[BacktestResult, float]] = []

        for result in results:
            if result.robustness_label in self.REJECTED_LABELS:
                logger.info(
                    "REJECTED %s [%s/%s]: label=%s",
                    result.strategy_name,
                    result.asset,
                    result.timeframe,
                    result.robustness_label,
                )
                scored.append((result, -1.0))
                continue

            # Base score from IS metrics
            base_score = result.robustness_score

            # Bonus for passing walk-forward
            wf_bonus = 0.0
            if wf_results:
                key = f"{result.strategy_name}_{result.asset}_{result.timeframe}"
                wf = wf_results.get(key)
                if wf and wf.passed:
                    wf_bonus = 0.15 * wf.wf_efficiency
                elif wf and not wf.passed:
                    wf_bonus = -0.10  # penalty for failing WF

            # Drawdown penalty
            dd_penalty = 0.0
            if result.max_drawdown_pct < -0.25:  # more than 25% drawdown
                dd_penalty = 0.20
            elif result.max_drawdown_pct < -0.15:
                dd_penalty = 0.10

            # Trade count gate: penalize sparse strategies
            trade_penalty = 0.0
            if result.total_trades < 30:
                trade_penalty = 0.20
            elif result.total_trades < 50:
                trade_penalty = 0.05

            composite = base_score + wf_bonus - dd_penalty - trade_penalty
            composite = max(0.0, composite)
            scored.append((result, composite))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    def select_best_per_asset(
        self,
        results: List[BacktestResult],
        wf_results: Optional[Dict[str, WalkForwardResult]] = None,
    ) -> Dict[Tuple[AssetSymbol, Timeframe], BacktestResult]:
        """
        From a list of results, select the best strategy per (asset, timeframe).
        Returns a dict keyed by (asset, timeframe).
        """
        # Group by (asset, timeframe)
        grouped: Dict[Tuple, List[BacktestResult]] = {}
        for r in results:
            key = (r.asset, r.timeframe)
            grouped.setdefault(key, []).append(r)

        best_per_asset: Dict[Tuple, BacktestResult] = {}
        for (asset, tf), group in grouped.items():
            ranked = self.rank(group, wf_results)
            if ranked:
                best_result, best_score = ranked[0]
                if best_score > 0:
                    best_per_asset[(asset, tf)] = best_result
                    logger.info(
                        "Best strategy for %s/%s: %s (score=%.3f, label=%s)",
                        asset, tf, best_result.strategy_name,
                        best_score, best_result.robustness_label,
                    )
                else:
                    logger.warning(
                        "No acceptable strategy found for %s/%s — all rejected",
                        asset, tf,
                    )

        return best_per_asset

    def generate_rejection_report(
        self, results: List[BacktestResult]
    ) -> List[Dict]:
        """
        Returns a list of dicts describing rejected strategies and why.
        Useful for the AI reporting and dashboard pages.
        """
        scored = self.rank(results)
        rejected = []
        for result, score in scored:
            if score < 0 or result.robustness_label in self.REJECTED_LABELS:
                rejected.append({
                    "strategy": result.strategy_name,
                    "asset": result.asset,
                    "timeframe": result.timeframe,
                    "reason": result.robustness_label,
                    "score": score,
                    "total_trades": result.total_trades,
                    "profit_factor": result.profit_factor,
                    "max_drawdown_pct": result.max_drawdown_pct,
                })
        return rejected
