"""Open positions page."""
from __future__ import annotations

import pandas as pd
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
    st.title("📂 Open Positions")

    if st.button("🔄 Refresh"):
        st.rerun()

    positions = _fetch("trades/open", fallback=[])

    if not positions:
        st.info("No open positions. Engine may not be running or no signals triggered.")
        return

    df = pd.DataFrame(positions)

    # Color unrealized PnL
    def style_pnl(val):
        try:
            v = float(val)
            color = "#00ff88" if v >= 0 else "#ff4466"
            return f"color: {color}; font-weight: 700"
        except Exception:
            return ""

    display_cols = ["asset", "strategy", "direction", "entry",
                    "stop_loss", "take_profit", "unrealized_pnl", "opened_at"]
    display_cols = [c for c in display_cols if c in df.columns]
    df = df[display_cols]

    st.dataframe(
        df.style.applymap(style_pnl, subset=["unrealized_pnl"]),
        use_container_width=True,
        hide_index=True,
    )

    total_open_pnl = sum(float(p.get("unrealized_pnl", 0)) for p in positions)
    pnl_color = "green" if total_open_pnl >= 0 else "red"
    st.markdown(
        f"**Total Unrealized PnL:** "
        f"<span style='color:{pnl_color};font-weight:700;'>${total_open_pnl:+,.2f}</span>",
        unsafe_allow_html=True,
    )
