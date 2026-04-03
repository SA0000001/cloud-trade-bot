"""
Platform-wide constants. Never use magic numbers — define them here.
"""

# ---------------------------------------------------------------------------
# Risk thresholds (percentages as decimals)
# ---------------------------------------------------------------------------

DAILY_DRAWDOWN_WARNING_PCT = 0.04     # 4% — enter warning zone
DAILY_DRAWDOWN_SOFT_STOP_PCT = 0.05   # 5% — pause new signals
WEEKLY_DRAWDOWN_WARNING_PCT = 0.08    # 8%
WEEKLY_DRAWDOWN_SOFT_STOP_PCT = 0.10  # 10%
TOTAL_DRAWDOWN_WARNING_PCT = 0.20     # 20%
TOTAL_DRAWDOWN_HARD_STOP_PCT = 0.25   # 25% — emergency stop

# ---------------------------------------------------------------------------
# Trade defaults
# ---------------------------------------------------------------------------

DEFAULT_COMMISSION_PCT = 0.001        # 0.1%
DEFAULT_SLIPPAGE_PCT = 0.0005         # 0.05%
DEFAULT_POSITION_SIZE = 1.0           # notional units (paper)

# ---------------------------------------------------------------------------
# Research
# ---------------------------------------------------------------------------

MIN_TRADES_FOR_METRICS = 30           # below this, results are unreliable
MIN_TRADES_FOR_ROBUST_LABEL = 50
IN_SAMPLE_RATIO = 0.70                # 70% in-sample, 30% out-of-sample
WALK_FORWARD_WINDOWS = 5              # number of WF windows
WF_TRAIN_RATIO = 0.70                 # train portion within each WF window

# Robustness scoring weights
ROBUSTNESS_WEIGHT_PROFIT_FACTOR = 0.20
ROBUSTNESS_WEIGHT_SHARPE = 0.20
ROBUSTNESS_WEIGHT_MAX_DD = 0.15
ROBUSTNESS_WEIGHT_WIN_RATE = 0.10
ROBUSTNESS_WEIGHT_EXPECTANCY = 0.15
ROBUSTNESS_WEIGHT_OOS_DEGRADATION = 0.10
ROBUSTNESS_WEIGHT_WF_CONSISTENCY = 0.10

# Thresholds for robustness labels
ROBUSTNESS_ROBUST_THRESHOLD = 0.70
ROBUSTNESS_ACCEPTABLE_THRESHOLD = 0.50
ROBUSTNESS_FRAGILE_THRESHOLD = 0.30

# ---------------------------------------------------------------------------
# Heartbeat
# ---------------------------------------------------------------------------

HEARTBEAT_INTERVAL_SECONDS = 60
HEARTBEAT_STALE_THRESHOLD_SECONDS = 180   # 3 mins without ping = stale

# ---------------------------------------------------------------------------
# Asset-specific historical data requirements (years)
# ---------------------------------------------------------------------------

ASSET_HISTORY_YEARS = {
    "BTCUSDT": 4,
    "XAUUSD": 5,
    "EURUSD": 5,
}

# ---------------------------------------------------------------------------
# Candidate timeframes per asset
# ---------------------------------------------------------------------------

ASSET_CANDIDATE_TIMEFRAMES = {
    "BTCUSDT": ["15m", "30m", "1h"],
    "XAUUSD": ["15m", "1h", "4h"],
    "EURUSD": ["30m", "1h", "4h"],
}

# ---------------------------------------------------------------------------
# Dashboard / API
# ---------------------------------------------------------------------------

API_PORT = 8000
DASHBOARD_PORT = 8501
API_VERSION = "v1"

# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------

TELEGRAM_MAX_MESSAGE_LENGTH = 4096
TELEGRAM_PARSE_MODE = "HTML"
