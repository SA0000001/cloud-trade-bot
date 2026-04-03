"""Risk monitor page."""
from __future__ import annotations

import requests
import streamlit as st

from app.config.settings import settings
from app.core.constants import (
    DAILY_DRAWDOWN_SOFT_STOP_PCT,
    DAILY_DRAWDOWN_WARNING_PCT,
    TOTAL_DRAWDOWN_HARD_STOP_PCT,
    TOTAL_DRAWDOWN_WARNING_PCT,
    WEEKLY_DRAWDOWN_SOFT_STOP_PCT,
    WEEKLY_DRAWDOWN_WARNING_PCT,
)

API_BASE = f"http://localhost:{settings.api.port}/api/v1"


def _fetch(endpoint: str, fallback=None):
    try:
        r = requests.get(f"{API_BASE}/{endpoint}", timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception:
        return fallback


def _post(endpoint: str, payload: dict):
    try:
        r = requests.post(f"{API_BASE}/{endpoint}", json=payload, timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def _dd_gauge(label: str, current_pct: float, warning_pct: float, stop_pct: float):
    """Render a simple drawdown gauge with color coding."""
    if current_pct >= stop_pct:
        color = "#ff4466"
        status = "🚨 STOP"
    elif current_pct >= warning_pct:
        color = "#ffaa00"
        status = "⚠️ WARNING"
    else:
        color = "#00ff88"
        status = "✅ NORMAL"

    fill_pct = min(current_pct / max(stop_pct, 0.001) * 100, 100)

    st.markdown(
        f"""
        <div style="background:#111827;border:1px solid #1f2d47;border-radius:8px;
                    padding:14px 18px;margin-bottom:10px;">
          <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
            <span style="font-weight:600;">{label}</span>
            <span style="color:{color};font-weight:700;">{status} — {current_pct*100:.2f}%</span>
          </div>
          <div style="background:#1f2d47;border-radius:4px;height:8px;">
            <div style="background:{color};width:{fill_pct:.0f}%;height:8px;border-radius:4px;"></div>
          </div>
          <div style="display:flex;justify-content:space-between;margin-top:4px;font-size:0.75rem;color:#555;">
            <span>0%</span>
            <span>⚠️ {warning_pct*100:.0f}%</span>
            <span>🛑 {stop_pct*100:.0f}%</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render():
    st.title("🛡️ Risk Monitor")

    if st.button("🔄 Refresh"):
        st.rerun()

    # TODO: pull real-time risk state from a /risk/state API endpoint
    # For now showing placeholder values — wire up after risk service integration
    st.warning(
        "⚠️ Risk state is currently sourced from local engine state. "
        "Connect the risk service API endpoint for live updates.",
        icon="⚠️",
    )

    # Drawdown gauges — placeholder values until wired to live engine
    st.markdown("### Drawdown Levels")
    _dd_gauge("Daily Drawdown", 0.0, DAILY_DRAWDOWN_WARNING_PCT, DAILY_DRAWDOWN_SOFT_STOP_PCT)
    _dd_gauge("Weekly Drawdown", 0.0, WEEKLY_DRAWDOWN_WARNING_PCT, WEEKLY_DRAWDOWN_SOFT_STOP_PCT)
    _dd_gauge("Total Drawdown", 0.0, TOTAL_DRAWDOWN_WARNING_PCT, TOTAL_DRAWDOWN_HARD_STOP_PCT)

    st.markdown("---")

    # Thresholds reference table
    st.markdown("### Risk Thresholds Reference")
    import pandas as pd
    thresholds = pd.DataFrame([
        {"Metric": "Daily DD Warning",   "Threshold": f"{DAILY_DRAWDOWN_WARNING_PCT*100:.0f}%",   "Action": "Log + monitor"},
        {"Metric": "Daily DD Soft Stop", "Threshold": f"{DAILY_DRAWDOWN_SOFT_STOP_PCT*100:.0f}%", "Action": "Pause new signals"},
        {"Metric": "Weekly DD Warning",  "Threshold": f"{WEEKLY_DRAWDOWN_WARNING_PCT*100:.0f}%",  "Action": "Log + monitor"},
        {"Metric": "Weekly DD Soft Stop","Threshold": f"{WEEKLY_DRAWDOWN_SOFT_STOP_PCT*100:.0f}%","Action": "Pause new signals"},
        {"Metric": "Total DD Warning",   "Threshold": f"{TOTAL_DRAWDOWN_WARNING_PCT*100:.0f}%",   "Action": "Alert + review"},
        {"Metric": "Total DD Hard Stop", "Threshold": f"{TOTAL_DRAWDOWN_HARD_STOP_PCT*100:.0f}%", "Action": "Emergency stop"},
    ])
    st.dataframe(thresholds, use_container_width=True, hide_index=True)

    st.markdown("---")

    # Manual emergency stop
    st.markdown("### ⚠️ Emergency Controls")
    st.markdown(
        "<small style='color:#888;'>These controls affect the paper engine signal state only. "
        "No real orders will be placed or cancelled.</small>",
        unsafe_allow_html=True,
    )

    with st.expander("🚨 Trigger Emergency Stop"):
        reason = st.text_input("Reason (required)", placeholder="e.g. Manual override — unusual market conditions")
        if st.button("🚨 TRIGGER EMERGENCY STOP", type="primary"):
            if not reason.strip():
                st.error("Please provide a reason before triggering emergency stop.")
            else:
                result = _post("engine/emergency-stop", {"reason": reason})
                if "error" in result:
                    st.error(f"Failed: {result['error']}")
                else:
                    st.success("✅ Emergency stop activated. No new signals will be generated.")

    # Recent emergency events
    st.markdown("### 📋 Recent Emergency Events")
    events = _fetch("engine/emergency-events", fallback=[])
    if events:
        import pandas as pd
        df = pd.DataFrame(events)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No emergency events recorded.")
