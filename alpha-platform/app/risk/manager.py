"""
Risk Management Layer.

Evaluates current account state against defined thresholds.
Implements soft-stop (pause signals) and hard-stop (emergency) logic.
The risk manager is stateless — it evaluates a RiskState snapshot
and returns an updated RiskState. It never mutates the broker directly.

All thresholds are defined in app.core.constants.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from app.core.constants import (
    DAILY_DRAWDOWN_SOFT_STOP_PCT,
    DAILY_DRAWDOWN_WARNING_PCT,
    TOTAL_DRAWDOWN_HARD_STOP_PCT,
    TOTAL_DRAWDOWN_WARNING_PCT,
    WEEKLY_DRAWDOWN_SOFT_STOP_PCT,
    WEEKLY_DRAWDOWN_WARNING_PCT,
)
from app.core.enums import EngineState, RiskLevel
from app.core.exceptions import EmergencyStopError
from app.core.interfaces import IRiskManager
from app.core.models import RiskState

logger = logging.getLogger(__name__)


class RiskManager(IRiskManager):
    """
    Evaluates drawdown limits and triggers stop modes.

    Soft stop:
      - Pause new signals
      - Downgrade to WARNING or SOFT_STOP risk level
      - Do NOT close existing trades automatically

    Hard stop:
      - Block all new signals
      - Raise emergency event
      - Caller must initiate broker.emergency_close_all()

    Recovery from stop states requires MANUAL re-enable via
    the dashboard or API. This is intentional — operator oversight.
    """

    def evaluate(self, state: RiskState) -> RiskState:
        """
        Check current drawdown figures against thresholds.
        Returns updated RiskState with new level and flags.
        """
        daily_dd = state.daily_drawdown_pct
        weekly_dd = state.weekly_drawdown_pct
        total_dd = state.total_drawdown_pct

        new_level = RiskLevel.NORMAL
        no_new_signals = False
        engine_state = EngineState.RUNNING

        # --- Total drawdown hard stop (highest priority) ---
        if total_dd >= TOTAL_DRAWDOWN_HARD_STOP_PCT:
            new_level = RiskLevel.HARD_STOP
            engine_state = EngineState.HARD_STOP
            no_new_signals = True
            logger.critical(
                "HARD STOP triggered. Total drawdown=%.1f%% >= %.1f%%",
                total_dd * 100, TOTAL_DRAWDOWN_HARD_STOP_PCT * 100,
            )

        # --- Total drawdown warning ---
        elif total_dd >= TOTAL_DRAWDOWN_WARNING_PCT:
            new_level = RiskLevel.WARNING
            logger.warning(
                "Total drawdown WARNING: %.1f%%", total_dd * 100
            )

        # --- Daily drawdown soft stop ---
        if daily_dd >= DAILY_DRAWDOWN_SOFT_STOP_PCT:
            new_level = max_risk_level(new_level, RiskLevel.SOFT_STOP)
            engine_state = EngineState.SOFT_STOP
            no_new_signals = True
            logger.warning(
                "SOFT STOP: Daily drawdown=%.1f%% >= %.1f%%",
                daily_dd * 100, DAILY_DRAWDOWN_SOFT_STOP_PCT * 100,
            )
        elif daily_dd >= DAILY_DRAWDOWN_WARNING_PCT:
            new_level = max_risk_level(new_level, RiskLevel.WARNING)
            logger.warning(
                "Daily drawdown WARNING: %.1f%%", daily_dd * 100
            )

        # --- Weekly drawdown soft stop ---
        if weekly_dd >= WEEKLY_DRAWDOWN_SOFT_STOP_PCT:
            new_level = max_risk_level(new_level, RiskLevel.SOFT_STOP)
            engine_state = EngineState.SOFT_STOP
            no_new_signals = True
            logger.warning(
                "SOFT STOP: Weekly drawdown=%.1f%% >= %.1f%%",
                weekly_dd * 100, WEEKLY_DRAWDOWN_SOFT_STOP_PCT * 100,
            )
        elif weekly_dd >= WEEKLY_DRAWDOWN_WARNING_PCT:
            new_level = max_risk_level(new_level, RiskLevel.WARNING)

        state.level = new_level
        state.engine_state = engine_state
        state.no_new_signals = no_new_signals
        state.last_updated = datetime.utcnow()
        return state

    def is_signal_allowed(self, state: RiskState) -> bool:
        """True if new signals should be accepted."""
        if state.no_new_signals:
            return False
        if state.engine_state in (
            EngineState.HARD_STOP,
            EngineState.EMERGENCY,
            EngineState.SOFT_STOP,
        ):
            return False
        return True

    def trigger_emergency_stop(self, reason: str) -> RiskState:
        """
        Manually trigger emergency stop.
        Returns a RiskState in EMERGENCY mode.
        The caller must propagate this to the broker.
        """
        logger.critical("EMERGENCY STOP triggered. Reason: %s", reason)
        state = RiskState(
            level=RiskLevel.EMERGENCY,
            engine_state=EngineState.EMERGENCY,
            no_new_signals=True,
            emergency_reason=reason,
            last_updated=datetime.utcnow(),
        )
        return state

    def compute_drawdown(
        self,
        current_equity: float,
        peak_equity: float,
    ) -> float:
        """Compute drawdown as a positive percentage of peak equity."""
        if peak_equity <= 0:
            return 0.0
        return max(0.0, (peak_equity - current_equity) / peak_equity)

    def reset_soft_stop(self, state: RiskState) -> RiskState:
        """
        Manually reset soft stop. Requires operator action.
        Hard stop and emergency cannot be reset here — must go through
        the full re-enable workflow.
        """
        if state.level in (RiskLevel.HARD_STOP, RiskLevel.EMERGENCY):
            raise EmergencyStopError(
                "Cannot auto-reset from HARD_STOP or EMERGENCY. Manual re-enable required."
            )
        state.level = RiskLevel.NORMAL
        state.engine_state = EngineState.RUNNING
        state.no_new_signals = False
        state.emergency_reason = None
        logger.info("Soft stop manually reset.")
        return state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RISK_LEVEL_ORDER = {
    RiskLevel.NORMAL: 0,
    RiskLevel.WARNING: 1,
    RiskLevel.SOFT_STOP: 2,
    RiskLevel.HARD_STOP: 3,
    RiskLevel.EMERGENCY: 4,
}


def max_risk_level(a: RiskLevel, b: RiskLevel) -> RiskLevel:
    """Return the more severe of two risk levels."""
    return a if _RISK_LEVEL_ORDER[a] >= _RISK_LEVEL_ORDER[b] else b
