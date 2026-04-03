"""
Paper Trading Engine.

Responsibilities:
  - Accept signals and open paper trades
  - Track open positions and compute unrealized PnL
  - Check SL/TP on price updates
  - Persist state to disk (JSON) for restart recovery
  - Maintain equity curve and journal
  - Support emergency close-all

Design rules:
  - NO live order execution. Paper only.
  - State is persisted after every mutating operation.
  - All monetary values are in USD equivalent.
  - One trade per asset at a time (configurable).
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from app.core.enums import (
    AssetSymbol,
    EngineState,
    ExitReason,
    SignalDirection,
    TradeStatus,
)
from app.core.exceptions import EngineBlockedError, StateRecoveryError, TradeNotFoundError
from app.core.interfaces import IPaperBroker
from app.core.models import EquitySnapshot, PaperTrade, RiskState, Signal

logger = logging.getLogger(__name__)


class PaperBroker(IPaperBroker):
    """
    Paper trading broker.

    State is stored in a JSON file at `state_file` path.
    On startup, call `recover()` to reload any persisted state.

    One open trade per asset is enforced by default.
    """

    def __init__(
        self,
        initial_equity: float = 10000.0,
        state_file: str = "data/state/paper_engine_state.json",
        allow_multiple_per_asset: bool = False,
    ) -> None:
        self._initial_equity = initial_equity
        self._equity = initial_equity
        self._state_file = Path(state_file)
        self._allow_multiple_per_asset = allow_multiple_per_asset

        self._open_trades: Dict[str, PaperTrade] = {}       # trade_id → PaperTrade
        self._closed_trades: List[PaperTrade] = []
        self._equity_curve: List[EquitySnapshot] = []
        self._engine_state: EngineState = EngineState.INITIALIZING

        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        logger.info(
            "PaperBroker initialized. equity=%.2f state_file=%s",
            initial_equity, state_file,
        )

    # ------------------------------------------------------------------
    # IPaperBroker interface
    # ------------------------------------------------------------------

    def submit_signal(self, signal: Signal) -> Optional[PaperTrade]:
        """Open a new paper trade from a signal."""
        if self._engine_state in (EngineState.HARD_STOP, EngineState.EMERGENCY):
            raise EngineBlockedError(
                f"Engine is in {self._engine_state} — no new trades accepted."
            )

        if not self._allow_multiple_per_asset:
            existing = self._get_open_for_asset(signal.asset)
            if existing:
                logger.debug(
                    "Skipping signal for %s — already have open trade %s",
                    signal.asset, existing.id,
                )
                return None

        trade = PaperTrade(
            signal_id=signal.id,
            asset=signal.asset,
            strategy_name=signal.strategy_name,
            timeframe=signal.timeframe,
            direction=signal.direction,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
        )

        self._open_trades[trade.id] = trade
        logger.info(
            "OPEN TRADE %s | %s %s @ %.4f | SL=%.4f TP=%.4f",
            trade.id[:8], trade.direction, trade.asset,
            trade.entry_price, trade.stop_loss, trade.take_profit,
        )
        self._persist_state()
        return trade

    def update_positions(
        self, current_prices: Dict[str, float]
    ) -> List[PaperTrade]:
        """
        Check all open trades against current prices.
        Close any that have hit SL or TP.
        Returns list of newly closed trades.
        """
        newly_closed: List[PaperTrade] = []

        for trade_id, trade in list(self._open_trades.items()):
            asset_key = trade.asset if isinstance(trade.asset, str) else trade.asset.value
            price = current_prices.get(asset_key) or current_prices.get(str(trade.asset))
            if price is None:
                continue

            trade.unrealized_pnl = trade.compute_unrealized_pnl(price)
            direction = trade.direction if isinstance(trade.direction, str) else trade.direction.value

            hit_sl = hit_tp = False
            if direction == "LONG":
                hit_sl = price <= trade.stop_loss
                hit_tp = price >= trade.take_profit
            elif direction == "SHORT":
                hit_sl = price >= trade.stop_loss
                hit_tp = price <= trade.take_profit

            if hit_sl or hit_tp:
                exit_reason = ExitReason.TAKE_PROFIT if hit_tp else ExitReason.STOP_LOSS
                exit_price = trade.take_profit if hit_tp else trade.stop_loss
                self._close_trade(trade, exit_price, exit_reason)
                newly_closed.append(trade)

        if newly_closed:
            self._persist_state()
            for t in newly_closed:
                logger.info(
                    "CLOSED TRADE %s | %s | PnL=%.2f | reason=%s",
                    t.id[:8], t.asset, t.realized_pnl, t.exit_reason,
                )

        self._snapshot_equity()
        return newly_closed

    def get_open_trades(self) -> List[PaperTrade]:
        return list(self._open_trades.values())

    def get_closed_trades(self) -> List[PaperTrade]:
        return list(self._closed_trades)

    def get_equity(self) -> float:
        return self._equity

    def get_equity_curve(self) -> List[EquitySnapshot]:
        return list(self._equity_curve)

    def emergency_close_all(self, reason: str) -> List[PaperTrade]:
        """Force-close all open positions at last known price."""
        closed: List[PaperTrade] = []
        for trade in list(self._open_trades.values()):
            # Close at entry price (worst case: no market price available)
            exit_price = trade.entry_price
            self._close_trade(trade, exit_price, ExitReason.EMERGENCY_STOP)
            closed.append(trade)

        self._engine_state = EngineState.EMERGENCY
        self._persist_state()
        logger.warning(
            "EMERGENCY CLOSE ALL: %d trades closed. Reason: %s", len(closed), reason
        )
        return closed

    def manual_close(self, trade_id: str, exit_price: float) -> PaperTrade:
        """Close a specific trade manually."""
        if trade_id not in self._open_trades:
            raise TradeNotFoundError(f"Trade {trade_id} not found in open trades.")
        trade = self._open_trades[trade_id]
        self._close_trade(trade, exit_price, ExitReason.MANUAL)
        self._persist_state()
        return trade

    # ------------------------------------------------------------------
    # State persistence
    # ------------------------------------------------------------------

    def recover(self) -> bool:
        """
        Load persisted state from disk.
        Returns True if state was recovered, False if fresh start.
        """
        if not self._state_file.exists():
            logger.info("No persisted state found — starting fresh.")
            self._engine_state = EngineState.RUNNING
            return False

        try:
            with open(self._state_file) as f:
                raw = json.load(f)

            self._equity = raw.get("equity", self._initial_equity)

            for t_dict in raw.get("open_trades", []):
                trade = PaperTrade(**t_dict)
                self._open_trades[trade.id] = trade

            for t_dict in raw.get("closed_trades", []):
                self._closed_trades.append(PaperTrade(**t_dict))

            self._engine_state = EngineState.RECOVERING
            logger.info(
                "State recovered: equity=%.2f, open=%d, closed=%d",
                self._equity, len(self._open_trades), len(self._closed_trades),
            )
            self._engine_state = EngineState.RUNNING
            return True

        except Exception as exc:
            raise StateRecoveryError(
                f"Failed to recover state from {self._state_file}: {exc}"
            ) from exc

    def _persist_state(self) -> None:
        """Write current state to disk atomically."""
        state = {
            "equity": self._equity,
            "persisted_at": datetime.utcnow().isoformat(),
            "engine_state": str(self._engine_state),
            "open_trades": [t.dict() for t in self._open_trades.values()],
            "closed_trades": [t.dict() for t in self._closed_trades[-500:]],  # keep last 500
        }
        tmp_path = self._state_file.with_suffix(".tmp")
        with open(tmp_path, "w") as f:
            json.dump(state, f, default=str, indent=2)
        os.replace(tmp_path, self._state_file)  # atomic rename

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _close_trade(
        self, trade: PaperTrade, exit_price: float, reason: ExitReason
    ) -> None:
        trade.close(exit_price, reason)
        self._equity += trade.realized_pnl or 0.0
        del self._open_trades[trade.id]
        self._closed_trades.append(trade)

    def _get_open_for_asset(self, asset: AssetSymbol) -> Optional[PaperTrade]:
        asset_val = asset if isinstance(asset, str) else asset.value
        for trade in self._open_trades.values():
            t_asset = trade.asset if isinstance(trade.asset, str) else trade.asset.value
            if t_asset == asset_val:
                return trade
        return None

    def _snapshot_equity(self) -> None:
        open_pnl = sum(
            t.unrealized_pnl or 0.0 for t in self._open_trades.values()
        )
        realized_total = sum(t.realized_pnl or 0.0 for t in self._closed_trades)
        snap = EquitySnapshot(
            timestamp=datetime.utcnow(),
            equity=self._equity,
            open_pnl=open_pnl,
            realized_pnl=realized_total,
            open_positions=len(self._open_trades),
        )
        self._equity_curve.append(snap)
        # Keep curve bounded in memory
        if len(self._equity_curve) > 10000:
            self._equity_curve = self._equity_curve[-5000:]

    def set_engine_state(self, state: EngineState) -> None:
        logger.info("Engine state: %s → %s", self._engine_state, state)
        self._engine_state = state

    @property
    def engine_state(self) -> EngineState:
        return self._engine_state

    def summary(self) -> Dict:
        """Return a lightweight summary dict for dashboards."""
        realized = sum(t.realized_pnl or 0.0 for t in self._closed_trades)
        open_pnl = sum(t.unrealized_pnl or 0.0 for t in self._open_trades.values())
        wins = [t for t in self._closed_trades if (t.realized_pnl or 0.0) > 0]
        win_rate = len(wins) / max(len(self._closed_trades), 1)
        return {
            "equity": self._equity,
            "initial_equity": self._initial_equity,
            "total_return_pct": (self._equity - self._initial_equity) / self._initial_equity,
            "realized_pnl": realized,
            "open_pnl": open_pnl,
            "open_trades": len(self._open_trades),
            "closed_trades": len(self._closed_trades),
            "win_rate": win_rate,
            "engine_state": str(self._engine_state),
        }
