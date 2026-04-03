"""Trade history page."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
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
    st.title("📜 Trade History")

    col1, col2, col3 = st.columns(3)
    with col1:
        asset_filter = st.selectbox("Asset", ["All", "BTCUSDT", "XAUUSD", "EURUSD"])
    with col2:
        limit = st.slider("Max records", 50, 500, 200)
    with col3:
        st.write("")
        if st.button("🔄 Refresh"):
            st.rerun()

    ep = f"trades/closed?limit={limit}"
    if asset_filter != "All":
        ep += f"&asset={asset_filter}"
    trades = _fetch(ep, fallback=[])

    if not trades:
        st.info("No closed trades yet.")
        return

    df = pd.DataFrame(trades)

    # Summary metrics
    total_pnl = df["pnl"].sum() if "pnl" in df else 0
    wins = df[df["pnl"] > 0] if "pnl" in df else pd.DataFrame()
    win_rate = len(wins) / max(len(df), 1) * 100

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total Trades", len(df))
    with c2:
        pnl_delta = f"{total_pnl:+,.2f}"
        st.metric("Total PnL", f"${total_pnl:,.2f}", delta=pnl_delta)
    with c3:
        st.metric("Win Rate", f"{win_rate:.1f}%")
    with c4:
        avg_win = wins["pnl"].mean() if len(wins) else 0
        st.metric("Avg Win", f"${avg_win:,.2f}")

    st.markdown("---")

    # Cumulative PnL chart
    if "pnl" in df.columns and len(df) > 1:
        df_sorted = df.sort_values("closed_at") if "closed_at" in df.columns else df
        df_sorted["cumulative_pnl"] = df_sorted["pnl"].cumsum()
        fig = px.line(
            df_sorted, x="closed_at", y="cumulative_pnl",
            title="Cumulative Realized PnL",
            color_discrete_sequence=["#00d4ff"],
        )
        fig.update_layout(
            paper_bgcolor="#111827", plot_bgcolor="#111827",
            font=dict(color="#e0e4f0"),
            xaxis=dict(gridcolor="#1f2d47"),
            yaxis=dict(gridcolor="#1f2d47"),
            height=280, margin=dict(l=40, r=20, t=40, b=40),
        )
        st.plotly_chart(fig, use_container_width=True)

    # Exit reason breakdown
    if "exit_reason" in df.columns:
        col_a, col_b = st.columns(2)
        with col_a:
            reason_counts = df["exit_reason"].value_counts().reset_index()
            reason_counts.columns = ["reason", "count"]
            fig2 = px.pie(reason_counts, values="count", names="reason",
                          title="Exit Reasons",
                          color_discrete_sequence=px.colors.sequential.Teal)
            fig2.update_layout(
                paper_bgcolor="#111827", font=dict(color="#e0e4f0"), height=260,
                margin=dict(l=10, r=10, t=40, b=10),
            )
            st.plotly_chart(fig2, use_container_width=True)

        with col_b:
            if "asset" in df.columns:
                asset_pnl = df.groupby("asset")["pnl"].sum().reset_index()
                fig3 = px.bar(asset_pnl, x="asset", y="pnl", title="PnL by Asset",
                              color="pnl",
                              color_continuous_scale=["#ff4466", "#111827", "#00ff88"])
                fig3.update_layout(
                    paper_bgcolor="#111827", plot_bgcolor="#111827",
                    font=dict(color="#e0e4f0"),
                    xaxis=dict(gridcolor="#1f2d47"),
                    yaxis=dict(gridcolor="#1f2d47"),
                    height=260, margin=dict(l=40, r=10, t=40, b=40),
                )
                st.plotly_chart(fig3, use_container_width=True)

    st.markdown("### Raw Trade Log")
    display_cols = [c for c in ["closed_at", "asset", "strategy", "direction",
                                "entry", "exit", "pnl", "exit_reason"] if c in df.columns]
    st.dataframe(df[display_cols], use_container_width=True, hide_index=True)
