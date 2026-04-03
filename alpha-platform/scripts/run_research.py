"""
Full research pipeline runner.

Runs in-sample/OOS backtest + walk-forward optimization
for all configured assets, timeframes, and strategies.
Saves results and prints a ranked summary.

Usage:
    python scripts/run_research.py
    # or
    make research-run

Prerequisites:
    - CSV data in data/historical/ (run make generate-data first)
    - pip install -e . (or make dev-install)

Output:
    - Console summary with rankings
    - JSON results saved to data/results/
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# Project root on path
sys.path.insert(0, str(Path(__file__).parent.parent))

import app.strategies  # register all strategies  # noqa: F401
from app.config.settings import settings
from app.core.constants import ASSET_CANDIDATE_TIMEFRAMES
from app.core.enums import AssetSymbol, Timeframe
from app.core.models import StrategyConfig
from app.data.processors import split_in_sample_oos
from app.data.providers.csv_provider import CSVDataProvider
from app.research.backtest_runner import SimpleBacktestRunner
from app.research.ranking import StrategyRanker
from app.research.walk_forward import WalkForwardOptimizer
from app.strategies.base import StrategyRegistry
from app.utils.logging import setup_logging

setup_logging("INFO")
logger = logging.getLogger(__name__)

RESULTS_DIR = Path(settings.research.results_dir)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def run_pipeline():
    provider = CSVDataProvider(settings.research.data_dir)
    runner = SimpleBacktestRunner()
    wf_optimizer = WalkForwardOptimizer(runner)
    ranker = StrategyRanker()

    strategy_names = StrategyRegistry.all_names()
    logger.info("Registered strategies: %s", strategy_names)

    all_results = []
    all_wf_results: Dict[str, Any] = {}

    for asset_str, timeframes in ASSET_CANDIDATE_TIMEFRAMES.items():
        asset = AssetSymbol(asset_str)

        for tf_str in timeframes:
            tf = Timeframe(tf_str)

            if not provider.is_available(asset, tf):
                logger.warning(
                    "No data for %s/%s — skipping. Run: make generate-data",
                    asset_str, tf_str,
                )
                continue

            logger.info("\n═══ %s / %s ═══", asset_str, tf_str)
            full_data = provider.get_ohlcv(asset, tf)
            is_data, oos_data = split_in_sample_oos(
                full_data, in_sample_ratio=settings.research.in_sample_ratio
            )
            logger.info(
                "Data split: IS=%d bars, OOS=%d bars (total=%d)",
                len(is_data), len(oos_data), len(full_data),
            )

            for strategy_name in strategy_names:
                strategy = StrategyRegistry.get(strategy_name)
                config = StrategyConfig(
                    name=strategy_name,
                    family=strategy.family,
                    asset=asset,
                    timeframe=tf,
                    parameters=strategy.default_parameters(),
                )

                # ── In-sample backtest ──
                logger.info("  Backtesting %s (IS)...", strategy_name)
                try:
                    is_result = runner.run(
                        strategy=strategy,
                        data=is_data,
                        config=config,
                        commission_pct=settings.research.commission_pct,
                        slippage_pct=settings.research.slippage_pct,
                    )
                    is_result.in_sample = True
                    all_results.append(is_result)
                    logger.info(
                        "    IS → PF=%.2f  Sharpe=%.2f  DD=%.1f%%  Trades=%d  [%s]",
                        is_result.profit_factor,
                        is_result.sharpe_ratio,
                        is_result.max_drawdown_pct * 100,
                        is_result.total_trades,
                        is_result.robustness_label,
                    )
                except Exception as e:
                    logger.warning("  IS backtest failed for %s: %s", strategy_name, e)
                    continue

                # ── Out-of-sample validation ──
                logger.info("  Validating %s (OOS)...", strategy_name)
                try:
                    oos_result = runner.run(
                        strategy=strategy,
                        data=oos_data,
                        config=config,
                        commission_pct=settings.research.commission_pct,
                        slippage_pct=settings.research.slippage_pct,
                    )
                    oos_result.in_sample = False
                    all_results.append(oos_result)
                    logger.info(
                        "    OOS → PF=%.2f  Sharpe=%.2f  DD=%.1f%%  Trades=%d",
                        oos_result.profit_factor,
                        oos_result.sharpe_ratio,
                        oos_result.max_drawdown_pct * 100,
                        oos_result.total_trades,
                    )
                except Exception as e:
                    logger.warning("  OOS validation failed for %s: %s", strategy_name, e)

                # ── Walk-forward optimization ──
                logger.info("  Walk-forward: %s...", strategy_name)
                try:
                    param_grid = _default_param_grid(strategy_name)
                    wf_result = wf_optimizer.run(
                        strategy=strategy,
                        data=full_data,
                        config=config,
                        param_grid=param_grid,
                        n_windows=settings.research.walk_forward_windows,
                        commission_pct=settings.research.commission_pct,
                        slippage_pct=settings.research.slippage_pct,
                    )
                    wf_key = f"{strategy_name}_{asset_str}_{tf_str}"
                    all_wf_results[wf_key] = wf_result
                    logger.info(
                        "    WF → efficiency=%.2f  consistency=%.2f  passed=%s",
                        wf_result.wf_efficiency,
                        wf_result.consistency_score,
                        wf_result.passed,
                    )
                except Exception as e:
                    logger.warning("  Walk-forward failed for %s: %s", strategy_name, e)

    # ── Ranking ──
    logger.info("\n\n═══════════════════════════════════")
    logger.info("  STRATEGY RANKING")
    logger.info("═══════════════════════════════════")

    is_results = [r for r in all_results if r.in_sample]
    ranked = ranker.rank(is_results, wf_results=all_wf_results)

    for i, (result, score) in enumerate(ranked[:20], 1):
        marker = "✅" if score >= 0.5 else "⚠️" if score > 0 else "❌"
        logger.info(
            "%s %2d. %-25s | %s/%-4s | PF=%.2f  Sharpe=%.2f  Score=%.3f  [%s]",
            marker, i,
            result.strategy_name,
            result.asset, result.timeframe,
            result.profit_factor,
            result.sharpe_ratio,
            score,
            result.robustness_label,
        )

    # ── Best per asset ──
    best = ranker.select_best_per_asset(is_results, wf_results=all_wf_results)
    logger.info("\n\n═══════════════════════════════════")
    logger.info("  BEST STRATEGY PER ASSET")
    logger.info("═══════════════════════════════════")
    for (asset, tf), result in best.items():
        logger.info("  %s/%s → %s  [%s]", asset, tf, result.strategy_name, result.robustness_label)

    # ── Save results ──
    _save_results(all_results, all_wf_results, ranked)
    logger.info("\n✅ Research pipeline complete. Results saved to %s", RESULTS_DIR)


def _default_param_grid(strategy_name: str) -> Dict[str, List[Any]]:
    """Return a modest parameter grid per strategy for walk-forward."""
    grids = {
        "SMA_CROSS": {
            "fast_period": [5, 10, 20],
            "slow_period": [30, 50, 100],
            "sl_atr_mult": [1.5, 2.0, 2.5],
            "tp_atr_mult": [2.5, 3.0, 4.0],
        },
        "DONCHIAN_BREAKOUT": {
            "channel_period": [15, 20, 30],
            "sl_atr_mult": [1.0, 1.5, 2.0],
            "tp_atr_mult": [2.0, 3.0, 4.0],
        },
        "RSI_MEAN_REVERSION": {
            "rsi_period": [10, 14, 20],
            "rsi_oversold": [25, 30, 35],
            "rsi_overbought": [65, 70, 75],
            "sl_atr_mult": [1.0, 1.5, 2.0],
        },
    }
    return grids.get(strategy_name, {})


def _save_results(all_results, wf_results, ranked):
    """Save results as JSON for later analysis."""
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    results_payload = {
        "generated_at": datetime.utcnow().isoformat(),
        "backtest_results": [
            {
                "strategy": r.strategy_name,
                "asset": str(r.asset),
                "timeframe": str(r.timeframe),
                "in_sample": r.in_sample,
                "profit_factor": r.profit_factor,
                "sharpe": r.sharpe_ratio,
                "max_drawdown_pct": r.max_drawdown_pct,
                "win_rate": r.win_rate,
                "total_trades": r.total_trades,
                "robustness_score": r.robustness_score,
                "robustness_label": str(r.robustness_label),
            }
            for r in all_results
        ],
        "walk_forward": {
            k: {
                "efficiency": v.wf_efficiency,
                "consistency": v.consistency_score,
                "passed": v.passed,
            }
            for k, v in wf_results.items()
        },
        "ranking": [
            {
                "strategy": r.strategy_name,
                "asset": str(r.asset),
                "timeframe": str(r.timeframe),
                "score": score,
                "label": str(r.robustness_label),
            }
            for r, score in ranked
        ],
    }

    out_path = RESULTS_DIR / f"research_{ts}.json"
    with open(out_path, "w") as f:
        json.dump(results_payload, f, indent=2, default=str)
    logger.info("Results written to %s", out_path)


if __name__ == "__main__":
    run_pipeline()
