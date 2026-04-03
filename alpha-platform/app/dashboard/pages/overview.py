"""
Overview page — top-level platform health snapshot.
All data fetched from API or service layer. No business logic here.
"""
from __future__ import annotations

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


def render():
    st.title("📊 Platform Overview")
    st.caption("Live paper trading dashboard — no real orders executed")

    col_refresh = st.columns([6, 1])[1]
    with col_refresh:
        if st.button("🔄 Refresh"):
            st.rerun()

    # -----------------------------------------------------------------------
    # Engine status strip
    # -----------------------------------------------------------------------
    status_data = _fetch("status", fallback={})
    heartbeats = status_data.get("heartbeats", {})

    st.markdown("### 🔌 Service Health")
    hb_cols = st.columns(4)
    service_names = ["paper_engine", "data_feed", "risk_manager", "scheduler"]
    for col, svc in zip(hb_cols, service_names):
        info = heartbeats.get(svc, {})
        alive = info.get("alive", False)
        with col:
            color = "status-ok" if alive else "status-stop"
            label = "●  ALIVE" if alive else "●  DEAD"
            st.markdown(
                f"<div class='metric-card'><small>{svc}</small><br>"
                f"<span class='{color}'>{label}</span></div>",
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # -----------------------------------------------------------------------
    # Key metrics
    # -----------------------------------------------------------------------
    summary = _fetch("trades/summary", fallback={})
    equity_data = _fetch("equity?days=1", fallback=[])

    current_equity = equity_data[-1]["equity"] if equity_data else 10000.0
    initial_equity = 10000.0  # TODO: pull from config endpoint
    total_return_pct = (current_equity - initial_equity) / initial_equity * 100

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("💰 Equity", f"${current_equity:,.2f}",
                  delta=f"{total_return_pct:+.2f}%")
    with col2:
        st.metric("📈 Total PnL", f"${summary.get('total_pnl', 0):+,.2f}")
    with col3:
        st.metric("🎯 Win Rate", f"{summary.get('win_rate', 0)*100:.1f}%")
    with col4:
        st.metric("📂 Open Trades", summary.get("open_trades", 0))
    with col5:
        st.metric("📜 Closed Trades", summary.get("total_trades", 0))

    st.markdown("---")

    # -----------------------------------------------------------------------
    # Equity curve chart
    # -----------------------------------------------------------------------
    st.markdown("### 📈 Equity Curve (30 days)")
    equity_curve = _fetch("equity?days=30", fallback=[])

    if equity_curve:
        import pandas as pd
        import plotly.graph_objects as go

        df = pd.DataFrame(equity_curve)
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=df["equity"],
            mode="lines",
            name="Equity",
            line=dict(color="#00d4ff", width=2),
            fill="tozeroy",
            fillcolor="rgba(0, 212, 255, 0.05)",
        ))
        fig.update_layout(
            paper_bgcolor="#111827",
            plot_bgcolor="#111827",
            font=dict(color="#e0e4f0", family="JetBrains Mono"),
            margin=dict(l=40, r=20, t=20, b=40),
            xaxis=dict(gridcolor="#1f2d47", showgrid=True),
            yaxis=dict(gridcolor="#1f2d47", showgrid=True),
            height=300,
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No equity data yet. Start the paper engine to begin tracking.")

    # -----------------------------------------------------------------------
    # Recent signals
    # -----------------------------------------------------------------------
    st.markdown("### ⚡ Recent Signals")
    signals = _fetch("signals?limit=5", fallback=[])

    if signals:
        import pandas as pd
        df = pd.DataFrame(signals)
        df = df[["generated_at", "asset", "strategy", "timeframe", "direction", "entry", "robustness"]]
        df["direction"] = df["direction"].apply(
            lambda d: f"🟢 {d}" if d == "LONG" else f"🔴 {d}"
        )
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No signals generated yet.")
