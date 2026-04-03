"""Strategy Lab page."""
from __future__ import annotations

from pathlib import Path

import requests
import streamlit as st

from app.config.settings import settings

API_BASE = f"http://localhost:{settings.api.port}/api/v1"


def _fetch(endpoint: str, fallback=None):
    try:
        r = requests.get(f"{API_BASE}/{endpoint}", timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception:
        return fallback


def _robustness_badge(label: str) -> str:
    colors = {
        "ROBUST": ("#00ff88", "black"),
        "ACCEPTABLE": ("#ffaa00", "black"),
        "FRAGILE": ("#ff8800", "white"),
        "OVERFIT": ("#ff4466", "white"),
        "INSUFFICIENT_DATA": ("#555", "white"),
    }
    bg, fg = colors.get(label, ("#333", "white"))
    return (
        f"<span style='background:{bg};color:{fg};padding:2px 8px;"
        f"border-radius:4px;font-size:0.75rem;font-weight:700;'>{label}</span>"
    )


def render():
    st.title("Strategy Lab")
    st.caption("Backtest results, walk-forward analysis, and robustness diagnostics")

    st.markdown("### Registered Strategies")
    try:
        import app.strategies
        from app.strategies.base import StrategyRegistry

        strategies = StrategyRegistry.list_all()
        if strategies:
            import pandas as pd

            df = pd.DataFrame(
                [{"Strategy": k, "Family": v} for k, v in strategies.items()]
            )
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No strategies registered yet.")
    except Exception as e:
        st.error(f"Failed to load strategy registry: {e}")

    st.markdown("---")

    st.markdown("### Backtest Results")
    results = _fetch("backtests/best", fallback=[])

    if results:
        import pandas as pd

        df = pd.DataFrame(results)
        display = [
            c
            for c in [
                "strategy",
                "asset",
                "timeframe",
                "total_return_pct",
                "profit_factor",
                "sharpe_ratio",
                "max_drawdown_pct",
                "win_rate",
                "total_trades",
                "robustness_score",
                "robustness_label",
            ]
            if c in df.columns
        ]
        st.dataframe(df[display], use_container_width=True, hide_index=True)
    else:
        st.info("No backtest results in database yet. Run a backtest from the research scripts.")

    st.markdown("---")

    st.markdown("### Quick Backtest Runner")
    st.caption(
        "Run a quick in-sample backtest directly from the dashboard. "
        "If CSV data is missing, demo data will be generated automatically."
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        strategy_name = st.selectbox(
            "Strategy",
            ["SMA_CROSS", "DONCHIAN_BREAKOUT", "RSI_MEAN_REVERSION"],
        )
    with col2:
        asset = st.selectbox("Asset", ["BTCUSDT", "XAUUSD", "EURUSD"])
    with col3:
        timeframe = st.selectbox("Timeframe", ["1h", "4h", "30m", "15m"])

    if st.button("Run Backtest"):
        with st.spinner("Running backtest..."):
            try:
                from app.core.enums import AssetSymbol, Timeframe
                from app.core.models import StrategyConfig
                from app.data.providers.csv_provider import CSVDataProvider
                from app.data.sample_data import generate_sample_csv
                from app.research.backtest_runner import SimpleBacktestRunner
                from app.strategies.base import StrategyRegistry
                import app.strategies

                provider = CSVDataProvider(settings.research.data_dir)
                asset_enum = AssetSymbol(asset)
                tf_enum = Timeframe(timeframe)

                if not provider.is_available(asset_enum, tf_enum):
                    csv_path = generate_sample_csv(
                        asset,
                        timeframe,
                        output_dir=Path(provider._data_dir),
                    )
                    provider.clear_cache()
                    st.info(
                        f"No CSV data was found for {asset}/{timeframe}. "
                        f"Generated demo data at `{csv_path}` and continued with that dataset."
                    )

                data = provider.get_ohlcv(asset_enum, tf_enum)
                strategy = StrategyRegistry.get(strategy_name)
                config = StrategyConfig(
                    name=strategy_name,
                    family=strategy.family,
                    asset=asset_enum,
                    timeframe=tf_enum,
                    parameters=strategy.default_parameters(),
                )
                runner = SimpleBacktestRunner()
                result = runner.run(strategy, data, config)

                st.success("Backtest complete!")
                col_a, col_b, col_c, col_d = st.columns(4)
                col_a.metric("Profit Factor", f"{result.profit_factor:.2f}")
                col_b.metric("Sharpe", f"{result.sharpe_ratio:.2f}")
                col_c.metric("Max DD", f"{result.max_drawdown_pct * 100:.1f}%")
                col_d.metric("Trades", result.total_trades)
                st.markdown(
                    f"**Robustness:** {_robustness_badge(str(result.robustness_label))} "
                    f"(score: {result.robustness_score:.3f})",
                    unsafe_allow_html=True,
                )

            except Exception as e:
                st.error(f"Backtest failed: {e}")
