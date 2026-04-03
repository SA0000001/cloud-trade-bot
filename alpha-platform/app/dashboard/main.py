"""
Alpha Platform — Streamlit Dashboard

Architecture rules:
  - This file is ONLY routing and layout.
  - NO business logic here.
  - All data comes via API calls to FastAPI or service layer.
  - Each page is a separate module in /pages.

Run:
  streamlit run app/dashboard/main.py
"""
from pathlib import Path
import sys

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

st.set_page_config(
    page_title="Alpha Trading Platform",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inject custom CSS — dark terminal aesthetic
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Space+Grotesk:wght@400;600&display=swap');

  html, body, [class*="css"] {
    font-family: 'Space Grotesk', sans-serif;
    background-color: #0a0e1a;
    color: #e0e4f0;
  }

  .stApp {
    background-color: #0a0e1a;
  }

  .metric-card {
    background: #111827;
    border: 1px solid #1f2d47;
    border-radius: 8px;
    padding: 16px 20px;
    margin: 4px 0;
  }

  .status-ok    { color: #00ff88; font-weight: 700; }
  .status-warn  { color: #ffaa00; font-weight: 700; }
  .status-stop  { color: #ff4466; font-weight: 700; }

  .signal-long  { color: #00ff88; }
  .signal-short { color: #ff4466; }

  code, .stCode {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.85rem;
  }

  h1, h2, h3 {
    font-family: 'JetBrains Mono', monospace;
    letter-spacing: -0.5px;
  }

  .sidebar .sidebar-content {
    background-color: #0d1321;
  }

  div[data-testid="stMetricValue"] {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.6rem;
    color: #00d4ff;
  }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------

PAGES = {
    "📊 Overview": "overview",
    "⚡ Live Signals": "signals",
    "📂 Open Positions": "positions",
    "🔬 Strategy Lab": "strategy_lab",
    "📜 Trade History": "history",
    "🛡️ Risk Monitor": "risk",
    "🤖 AI Report": "ai_report",
}

with st.sidebar:
    st.markdown("## 🧠 Alpha Platform")
    st.markdown("---")
    selection = st.radio(
        "Navigate",
        list(PAGES.keys()),
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.markdown(
        "<small style='color:#555;'>Paper trading only.<br>No real orders executed.</small>",
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Page routing
# ---------------------------------------------------------------------------

page_key = PAGES[selection]

if page_key == "overview":
    from app.dashboard.pages import overview
    overview.render()

elif page_key == "signals":
    from app.dashboard.pages import signals
    signals.render()

elif page_key == "positions":
    from app.dashboard.pages import positions
    positions.render()

elif page_key == "strategy_lab":
    from app.dashboard.pages import strategy_lab
    strategy_lab.render()

elif page_key == "history":
    from app.dashboard.pages import history
    history.render()

elif page_key == "risk":
    from app.dashboard.pages import risk_monitor
    risk_monitor.render()

elif page_key == "ai_report":
    from app.dashboard.pages import ai_report
    ai_report.render()
