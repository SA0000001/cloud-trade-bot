"""
Abstract interfaces for all major platform components.
All concrete implementations must satisfy these contracts.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from app.core.enums import AssetSymbol, Timeframe, NotificationChannel
from app.core.models import (
    BacktestResult,
    HeartbeatRecord,
    OHLCV,
    PaperTrade,
    RiskState,
    Signal,
    StrategyConfig,
)


# ---------------------------------------------------------------------------
# Data provider
# ---------------------------------------------------------------------------

class IDataProvider(ABC):
    """Contract for all data providers (CSV, API, Webhook, etc.)."""

    @abstractmethod
    def get_ohlcv(
        self,
        asset: AssetSymbol,
        timeframe: Timeframe,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Return OHLCV data as a DataFrame.
        Columns: ['timestamp','open','high','low','close','volume']
        Index: DatetimeIndex UTC.
        """
        ...

    @abstractmethod
    def is_available(self, asset: AssetSymbol, timeframe: Timeframe) -> bool:
        """Check if data is available for asset/timeframe combo."""
        ...

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Human-readable name of this data source."""
        ...


# ---------------------------------------------------------------------------
# Strategy
# ---------------------------------------------------------------------------

class IStrategy(ABC):
    """Contract for all trading strategies."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique strategy identifier."""
        ...

    @property
    @abstractmethod
    def family(self) -> str:
        """StrategyFamily value."""
        ...

    @abstractmethod
    def generate_signal(
        self,
        data: pd.DataFrame,
        config: StrategyConfig,
    ) -> Optional[Signal]:
        """
        Given OHLCV data, return a Signal or None.
        Must NOT modify the DataFrame.
        Must be deterministic for the same input.
        """
        ...

    @abstractmethod
    def validate_config(self, config: StrategyConfig) -> bool:
        """Validate that the config parameters are valid for this strategy."""
        ...

    @abstractmethod
    def default_parameters(self) -> Dict[str, Any]:
        """Return default parameter set for this strategy."""
        ...


# ---------------------------------------------------------------------------
# Backtest runner
# ---------------------------------------------------------------------------

class IBacktestRunner(ABC):
    """Contract for backtest execution engines."""

    @abstractmethod
    def run(
        self,
        strategy: IStrategy,
        data: pd.DataFrame,
        config: StrategyConfig,
        commission_pct: float = 0.001,
        slippage_pct: float = 0.0005,
    ) -> BacktestResult:
        """Run a single backtest and return metrics."""
        ...


# ---------------------------------------------------------------------------
# Paper broker
# ---------------------------------------------------------------------------

class IPaperBroker(ABC):
    """Contract for the paper trading execution layer."""

    @abstractmethod
    def submit_signal(self, signal: Signal) -> Optional[PaperTrade]:
        """Accept a signal and open a paper trade."""
        ...

    @abstractmethod
    def update_positions(self, current_prices: Dict[str, float]) -> List[PaperTrade]:
        """Update all open positions with latest prices; return closed trades."""
        ...

    @abstractmethod
    def get_open_trades(self) -> List[PaperTrade]:
        """Return all currently open paper trades."""
        ...

    @abstractmethod
    def get_equity(self) -> float:
        """Return current paper equity."""
        ...

    @abstractmethod
    def emergency_close_all(self, reason: str) -> List[PaperTrade]:
        """Force close all open positions immediately."""
        ...


# ---------------------------------------------------------------------------
# Risk manager
# ---------------------------------------------------------------------------

class IRiskManager(ABC):
    """Contract for the risk management layer."""

    @abstractmethod
    def evaluate(self, state: RiskState) -> RiskState:
        """Evaluate risk state and update level/flags."""
        ...

    @abstractmethod
    def is_signal_allowed(self, state: RiskState) -> bool:
        """Return True if new signals should be accepted."""
        ...

    @abstractmethod
    def trigger_emergency_stop(self, reason: str) -> RiskState:
        """Activate emergency stop and return updated state."""
        ...


# ---------------------------------------------------------------------------
# Notification service
# ---------------------------------------------------------------------------

class INotificationService(ABC):
    """Contract for notification delivery."""

    @property
    @abstractmethod
    def channel(self) -> NotificationChannel:
        ...

    @abstractmethod
    def send(self, message: str, parse_mode: str = "HTML") -> bool:
        """Send a plain text/HTML message. Return True on success."""
        ...

    @abstractmethod
    def send_signal_alert(self, signal: Signal) -> bool:
        """Send a formatted signal notification."""
        ...

    @abstractmethod
    def send_risk_alert(self, risk_state: RiskState, context: str = "") -> bool:
        """Send a risk/drawdown alert."""
        ...


# ---------------------------------------------------------------------------
# Heartbeat service
# ---------------------------------------------------------------------------

class IHeartbeatService(ABC):
    """Contract for heartbeat/health monitoring."""

    @abstractmethod
    def ping(self, service_name: str, status: str = "ok", message: str = "") -> HeartbeatRecord:
        """Record a heartbeat ping."""
        ...

    @abstractmethod
    def is_alive(self, service_name: str, max_age_seconds: int = 120) -> bool:
        """Check if a service has pinged recently."""
        ...

    @abstractmethod
    def get_last_heartbeat(self, service_name: str) -> Optional[HeartbeatRecord]:
        """Return the most recent heartbeat for a service."""
        ...


# ---------------------------------------------------------------------------
# AI Report generator
# ---------------------------------------------------------------------------

class IAIReportGenerator(ABC):
    """Contract for AI-assisted report generation."""

    @abstractmethod
    def generate_daily_report(self, context: Dict[str, Any]) -> str:
        """Generate a daily performance and strategy health report."""
        ...

    @abstractmethod
    def generate_strategy_diagnosis(
        self, strategy_name: str, context: Dict[str, Any]
    ) -> str:
        """Diagnose a specific strategy's health and behavior."""
        ...
