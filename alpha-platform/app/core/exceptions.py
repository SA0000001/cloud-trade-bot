"""
Platform-wide custom exceptions.
All domain errors should derive from AlphaPlatformError.
"""


class AlphaPlatformError(Exception):
    """Base exception for all platform errors."""
    pass


# ---------------------------------------------------------------------------
# Data errors
# ---------------------------------------------------------------------------

class DataProviderError(AlphaPlatformError):
    """Raised when a data provider fails to return data."""
    pass


class InsufficientDataError(DataProviderError):
    """Not enough historical bars for the requested operation."""
    pass


class DataValidationError(DataProviderError):
    """Data failed quality/integrity checks."""
    pass


# ---------------------------------------------------------------------------
# Strategy errors
# ---------------------------------------------------------------------------

class StrategyNotFoundError(AlphaPlatformError):
    """Requested strategy name not in registry."""
    pass


class StrategyConfigError(AlphaPlatformError):
    """Invalid or missing strategy configuration."""
    pass


class StrategyExecutionError(AlphaPlatformError):
    """Runtime error inside strategy logic."""
    pass


# ---------------------------------------------------------------------------
# Research errors
# ---------------------------------------------------------------------------

class BacktestError(AlphaPlatformError):
    """Error during backtest execution."""
    pass


class OptimizationError(AlphaPlatformError):
    """Error during parameter optimization."""
    pass


class WalkForwardError(AlphaPlatformError):
    """Error during walk-forward analysis."""
    pass


class InsufficientTradesError(AlphaPlatformError):
    """Too few trades to compute reliable metrics."""
    pass


# ---------------------------------------------------------------------------
# Paper engine errors
# ---------------------------------------------------------------------------

class PaperEngineError(AlphaPlatformError):
    """Generic paper engine error."""
    pass


class TradeNotFoundError(PaperEngineError):
    """Trade ID not found in journal."""
    pass


class EngineBlockedError(PaperEngineError):
    """Engine is in stop/emergency state; cannot accept new signals."""
    pass


class StateRecoveryError(PaperEngineError):
    """Failed to recover engine state from persistence layer."""
    pass


# ---------------------------------------------------------------------------
# Risk errors
# ---------------------------------------------------------------------------

class RiskLimitBreachedError(AlphaPlatformError):
    """A risk threshold has been breached."""
    pass


class EmergencyStopError(AlphaPlatformError):
    """Emergency stop was triggered."""
    pass


# ---------------------------------------------------------------------------
# Config errors
# ---------------------------------------------------------------------------

class ConfigurationError(AlphaPlatformError):
    """Invalid or missing configuration."""
    pass


# ---------------------------------------------------------------------------
# Notification errors
# ---------------------------------------------------------------------------

class NotificationError(AlphaPlatformError):
    """Failed to deliver a notification."""
    pass


class TelegramError(NotificationError):
    """Telegram-specific delivery failure."""
    pass
