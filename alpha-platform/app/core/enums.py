"""
Core enumerations used across the entire platform.
"""
from enum import Enum, auto


class AssetSymbol(str, Enum):
    BTCUSDT = "BTCUSDT"
    XAUUSD = "XAUUSD"
    EURUSD = "EURUSD"


class Timeframe(str, Enum):
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"


class SignalDirection(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"


class TradeStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class ExitReason(str, Enum):
    TAKE_PROFIT = "TAKE_PROFIT"
    STOP_LOSS = "STOP_LOSS"
    TRAILING_STOP = "TRAILING_STOP"
    MANUAL = "MANUAL"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    SIGNAL_REVERSAL = "SIGNAL_REVERSAL"
    RISK_LIMIT = "RISK_LIMIT"
    SYSTEM_SHUTDOWN = "SYSTEM_SHUTDOWN"


class StrategyFamily(str, Enum):
    TREND_FOLLOWING = "TREND_FOLLOWING"
    BREAKOUT = "BREAKOUT"
    MEAN_REVERSION = "MEAN_REVERSION"
    MOMENTUM = "MOMENTUM"
    PULLBACK = "PULLBACK"
    VOLATILITY_EXPANSION = "VOLATILITY_EXPANSION"
    RANGE_TRADING = "RANGE_TRADING"


class MarketRegime(str, Enum):
    TRENDING_UP = "TRENDING_UP"
    TRENDING_DOWN = "TRENDING_DOWN"
    RANGING = "RANGING"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"
    UNSTABLE = "UNSTABLE"
    UNKNOWN = "UNKNOWN"


class RiskLevel(str, Enum):
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    SOFT_STOP = "SOFT_STOP"
    HARD_STOP = "HARD_STOP"
    EMERGENCY = "EMERGENCY"


class EngineState(str, Enum):
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    SOFT_STOP = "SOFT_STOP"
    HARD_STOP = "HARD_STOP"
    EMERGENCY = "EMERGENCY"
    INITIALIZING = "INITIALIZING"
    RECOVERING = "RECOVERING"


class DataSource(str, Enum):
    CSV = "CSV"
    TRADINGVIEW_WEBHOOK = "TRADINGVIEW_WEBHOOK"
    BINANCE_API = "BINANCE_API"
    STUB = "STUB"


class NotificationChannel(str, Enum):
    TELEGRAM = "TELEGRAM"
    EMAIL = "EMAIL"
    WEBHOOK = "WEBHOOK"


class ReportType(str, Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    STRATEGY_HEALTH = "STRATEGY_HEALTH"
    EMERGENCY = "EMERGENCY"
    OPTIMIZATION_COMPLETE = "OPTIMIZATION_COMPLETE"


class RobustnessLabel(str, Enum):
    ROBUST = "ROBUST"
    ACCEPTABLE = "ACCEPTABLE"
    FRAGILE = "FRAGILE"
    OVERFIT = "OVERFIT"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
