"""
Walk-Forward Optimization Engine.

Workflow per window:
  1. Optimize parameters on train split (grid search).
  2. Record best parameters.
  3. Validate on test split using those parameters.
  4. Collect metrics from all windows.
  5. Compute WF efficiency = avg OOS PF / avg IS PF.
  6. Score consistency of OOS results.

This avoids curve-fitting by penalizing strategies that only work
on the exact data they were trained on.
"""
from __future__ import annotations

import itertools
import logging
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from app.core.exceptions import WalkForwardError
from app.core.interfaces import IStrategy
from app.core.models import BacktestResult, StrategyConfig, WalkForwardResult
from app.data.processors import generate_walk_forward_windows
from app.research.backtest_runner import SimpleBacktestRunner
from app.research.metrics import compute_robustness_score

logger = logging.getLogger(__name__)


class WalkForwardOptimizer:
    """
    Performs walk-forward optimization over a parameter grid.

    Usage:
        optimizer = WalkForwardOptimizer(runner=SimpleBacktestRunner())
        result = optimizer.run(
            strategy=my_strategy,
            data=full_df,
            config=base_config,
            param_grid={"fast_period": [5,10,20], "slow_period": [20,50,100]},
            n_windows=5,
        )
    """

    def __init__(self, runner: Optional[SimpleBacktestRunner] = None) -> None:
        self._runner = runner or SimpleBacktestRunner()

    def run(
        self,
        strategy: IStrategy,
        data: pd.DataFrame,
        config: StrategyConfig,
        param_grid: Dict[str, List[Any]],
        n_windows: int = 5,
        train_ratio: float = 0.70,
        commission_pct: float = 0.001,
        slippage_pct: float = 0.0005,
        rank_metric: str = "profit_factor",
    ) -> WalkForwardResult:
        """
        Run walk-forward optimization. Returns WalkForwardResult.
        """
        if len(data) < 200:
            raise WalkForwardError(
                f"Not enough data for WF optimization ({len(data)} bars)."
            )

        windows = generate_walk_forward_windows(data, n_windows, train_ratio)
        all_window_results: List[Dict[str, Any]] = []

        for window_idx, (train_df, test_df) in enumerate(windows):
            logger.info(
                "WF window %d/%d | train=%d bars, test=%d bars",
                window_idx + 1, n_windows, len(train_df), len(test_df),
            )

            # --- In-sample: grid search ---
            best_is_result, best_params = self._grid_search(
                strategy, train_df, config, param_grid,
                commission_pct, slippage_pct, rank_metric,
            )

            if best_is_result is None:
                logger.warning("WF window %d: no valid IS result found", window_idx + 1)
                continue

            # --- Out-of-sample: validate with best params ---
            oos_config = StrategyConfig(
                name=config.name,
                family=config.family,
                asset=config.asset,
                timeframe=config.timeframe,
                parameters=best_params,
                enabled=config.enabled,
            )
            try:
                oos_result = self._runner.run(
                    strategy, test_df, oos_config, commission_pct, slippage_pct
                )
            except Exception as exc:
                logger.warning("WF window %d OOS run failed: %s", window_idx + 1, exc)
                oos_result = None

            window_summary = {
                "window": window_idx + 1,
                "best_params": best_params,
                "is_profit_factor": best_is_result.profit_factor,
                "is_sharpe": best_is_result.sharpe_ratio,
                "is_total_return": best_is_result.total_return_pct,
                "is_trades": best_is_result.total_trades,
                "oos_profit_factor": oos_result.profit_factor if oos_result else None,
                "oos_sharpe": oos_result.sharpe_ratio if oos_result else None,
                "oos_total_return": oos_result.total_return_pct if oos_result else None,
                "oos_trades": oos_result.total_trades if oos_result else None,
            }
            all_window_results.append(window_summary)

        if not all_window_results:
            raise WalkForwardError("No valid WF windows produced results.")

        # --- Aggregate metrics ---
        wf_result = self._aggregate(config, all_window_results)
        logger.info(
            "WF complete. Efficiency=%.2f, Consistency=%.2f, Passed=%s",
            wf_result.wf_efficiency, wf_result.consistency_score, wf_result.passed,
        )
        return wf_result

    def _grid_search(
        self,
        strategy: IStrategy,
        data: pd.DataFrame,
        base_config: StrategyConfig,
        param_grid: Dict[str, List[Any]],
        commission_pct: float,
        slippage_pct: float,
        rank_metric: str,
    ) -> Tuple[Optional[BacktestResult], Dict[str, Any]]:
        """
        Exhaustive grid search. Returns (best_result, best_params).
        """
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        combos = list(itertools.product(*param_values))

        best_result: Optional[BacktestResult] = None
        best_metric_value = float("-inf")
        best_params: Dict[str, Any] = {}

        for combo in combos:
            params = dict(zip(param_names, combo))
            test_config = StrategyConfig(
                name=base_config.name,
                family=base_config.family,
                asset=base_config.asset,
                timeframe=base_config.timeframe,
                parameters=params,
                enabled=True,
            )
            try:
                result = self._runner.run(
                    strategy, data, test_config, commission_pct, slippage_pct
                )
            except Exception as exc:
                logger.debug("Grid search combo %s failed: %s", params, exc)
                continue

            metric_val = getattr(result, rank_metric, None)
            if metric_val is None:
                continue

            if metric_val > best_metric_value and result.total_trades >= 10:
                best_metric_value = metric_val
                best_result = result
                best_params = params

        return best_result, best_params

    @staticmethod
    def _aggregate(
        config: StrategyConfig,
        windows: List[Dict[str, Any]],
    ) -> WalkForwardResult:
        """Compute efficiency and consistency from window summaries."""
        import numpy as np

        is_pfs = [w["is_profit_factor"] for w in windows if w["is_profit_factor"]]
        oos_pfs = [w["oos_profit_factor"] for w in windows if w["oos_profit_factor"]]

        avg_is_pf = float(np.mean(is_pfs)) if is_pfs else 0.0
        avg_oos_pf = float(np.mean(oos_pfs)) if oos_pfs else 0.0

        # WF Efficiency: ratio of OOS to IS performance
        wf_efficiency = avg_oos_pf / max(avg_is_pf, 0.001)

        # Consistency: how stable OOS results are across windows
        if len(oos_pfs) >= 2:
            consistency = 1.0 - float(np.std(oos_pfs) / max(np.mean(oos_pfs), 0.001))
            consistency = max(0.0, min(1.0, consistency))
        else:
            consistency = 0.0

        # Pass criteria: WF efficiency > 0.5, consistency > 0.4, avg OOS PF > 1.2
        passed = wf_efficiency > 0.5 and consistency > 0.4 and avg_oos_pf > 1.2

        return WalkForwardResult(
            strategy_name=config.name,
            asset=config.asset,
            timeframe=config.timeframe,
            windows=windows,
            wf_efficiency=round(wf_efficiency, 4),
            consistency_score=round(consistency, 4),
            passed=passed,
        )
