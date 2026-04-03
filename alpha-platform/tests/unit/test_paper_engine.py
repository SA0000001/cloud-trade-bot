"""
Tests for paper engine broker and risk manager.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime

import pytest

from app.core.enums import (
    AssetSymbol,
    EngineState,
    ExitReason,
    RiskLevel,
    SignalDirection,
    StrategyFamily,
    Timeframe,
)
from app.core.exceptions import EngineBlockedError, TradeNotFoundError
from app.core.models import RiskState, Signal
from app.paper_engine.broker import PaperBroker
from app.risk.manager import RiskManager


def _make_signal(
    asset: str = "BTCUSDT",
    direction: str = "LONG",
    entry: float = 50000.0,
    sl: float = 48000.0,
    tp: float = 54000.0,
) -> Signal:
    return Signal(
        asset=AssetSymbol(asset),
        strategy_name="TEST_STRAT",
        strategy_family=StrategyFamily.TREND_FOLLOWING,
        timeframe=Timeframe.H1,
        direction=SignalDirection(direction),
        entry_price=entry,
        stop_loss=sl,
        take_profit=tp,
        atr=500.0,
        reason="Test signal",
    )


@pytest.fixture
def broker(tmp_path):
    state_file = str(tmp_path / "state.json")
    b = PaperBroker(initial_equity=10000.0, state_file=state_file)
    b.set_engine_state(EngineState.RUNNING)
    return b


class TestPaperBroker:

    def test_submit_signal_opens_trade(self, broker):
        signal = _make_signal()
        trade = broker.submit_signal(signal)
        assert trade is not None
        assert len(broker.get_open_trades()) == 1

    def test_one_trade_per_asset_enforced(self, broker):
        signal1 = _make_signal()
        signal2 = _make_signal(entry=51000.0)
        broker.submit_signal(signal1)
        result = broker.submit_signal(signal2)
        assert result is None  # second signal rejected
        assert len(broker.get_open_trades()) == 1

    def test_multiple_assets_allowed(self, broker):
        broker.submit_signal(_make_signal(asset="BTCUSDT"))
        broker.submit_signal(_make_signal(asset="XAUUSD"))
        assert len(broker.get_open_trades()) == 2

    def test_tp_hit_closes_trade(self, broker):
        signal = _make_signal(entry=50000.0, tp=54000.0, sl=48000.0)
        broker.submit_signal(signal)
        closed = broker.update_positions({"BTCUSDT": 54001.0})  # above TP
        assert len(closed) == 1
        assert closed[0].exit_reason == ExitReason.TAKE_PROFIT.value or \
               closed[0].exit_reason == ExitReason.TAKE_PROFIT
        assert len(broker.get_open_trades()) == 0

    def test_sl_hit_closes_trade(self, broker):
        signal = _make_signal(entry=50000.0, tp=54000.0, sl=48000.0)
        broker.submit_signal(signal)
        closed = broker.update_positions({"BTCUSDT": 47999.0})  # below SL
        assert len(closed) == 1
        assert closed[0].exit_reason == ExitReason.STOP_LOSS.value or \
               closed[0].exit_reason == ExitReason.STOP_LOSS

    def test_equity_updates_after_profitable_trade(self, broker):
        initial = broker.get_equity()
        signal = _make_signal(entry=50000.0, tp=55000.0, sl=48000.0)
        broker.submit_signal(signal)
        broker.update_positions({"BTCUSDT": 55001.0})
        assert broker.get_equity() > initial

    def test_equity_decreases_after_losing_trade(self, broker):
        initial = broker.get_equity()
        signal = _make_signal(entry=50000.0, tp=55000.0, sl=48000.0)
        broker.submit_signal(signal)
        broker.update_positions({"BTCUSDT": 47999.0})
        assert broker.get_equity() < initial

    def test_state_persists_to_file(self, tmp_path):
        state_file = str(tmp_path / "state.json")
        b = PaperBroker(initial_equity=10000.0, state_file=state_file)
        b.set_engine_state(EngineState.RUNNING)
        b.submit_signal(_make_signal())
        assert os.path.exists(state_file)
        with open(state_file) as f:
            data = json.load(f)
        assert len(data["open_trades"]) == 1

    def test_recovery_from_persisted_state(self, tmp_path):
        state_file = str(tmp_path / "state.json")
        # First broker — creates trades
        b1 = PaperBroker(initial_equity=10000.0, state_file=state_file)
        b1.set_engine_state(EngineState.RUNNING)
        b1.submit_signal(_make_signal())
        assert len(b1.get_open_trades()) == 1

        # Second broker — recovers state
        b2 = PaperBroker(initial_equity=10000.0, state_file=state_file)
        b2.recover()
        assert len(b2.get_open_trades()) == 1

    def test_emergency_close_all(self, broker):
        broker.submit_signal(_make_signal(asset="BTCUSDT"))
        broker.submit_signal(_make_signal(asset="XAUUSD"))
        closed = broker.emergency_close_all("Test emergency")
        assert len(closed) == 2
        assert len(broker.get_open_trades()) == 0
        assert broker.engine_state == EngineState.EMERGENCY

    def test_blocked_when_emergency(self, broker):
        broker.set_engine_state(EngineState.EMERGENCY)
        with pytest.raises(EngineBlockedError):
            broker.submit_signal(_make_signal())

    def test_manual_close(self, broker):
        trade = broker.submit_signal(_make_signal())
        broker.manual_close(trade.id, exit_price=52000.0)
        assert len(broker.get_open_trades()) == 0
        assert len(broker.get_closed_trades()) == 1

    def test_manual_close_nonexistent_raises(self, broker):
        with pytest.raises(TradeNotFoundError):
            broker.manual_close("nonexistent-id", exit_price=50000.0)

    def test_short_trade_sl_hit(self, broker):
        # SHORT: SL is above entry
        signal = _make_signal(direction="SHORT", entry=50000.0, sl=52000.0, tp=46000.0)
        broker.submit_signal(signal)
        # Price rises above SL
        closed = broker.update_positions({"BTCUSDT": 52001.0})
        assert len(closed) == 1
        assert closed[0].exit_reason in (ExitReason.STOP_LOSS.value, ExitReason.STOP_LOSS)


class TestRiskManager:

    def _state(
        self,
        daily=0.0, weekly=0.0, total=0.0,
        engine=EngineState.RUNNING,
    ) -> RiskState:
        return RiskState(
            level=RiskLevel.NORMAL,
            engine_state=engine,
            daily_drawdown_pct=daily,
            weekly_drawdown_pct=weekly,
            total_drawdown_pct=total,
        )

    def test_normal_state_unchanged(self):
        rm = RiskManager()
        state = self._state(daily=0.01, weekly=0.03, total=0.05)
        result = rm.evaluate(state)
        assert result.level == RiskLevel.NORMAL
        assert result.no_new_signals is False

    def test_daily_warning_triggered(self):
        rm = RiskManager()
        state = self._state(daily=0.04)
        result = rm.evaluate(state)
        assert result.level == RiskLevel.WARNING

    def test_daily_soft_stop_triggered(self):
        rm = RiskManager()
        state = self._state(daily=0.05)
        result = rm.evaluate(state)
        assert result.level == RiskLevel.SOFT_STOP
        assert result.no_new_signals is True

    def test_total_hard_stop_triggered(self):
        rm = RiskManager()
        state = self._state(total=0.25)
        result = rm.evaluate(state)
        assert result.level == RiskLevel.HARD_STOP
        assert result.no_new_signals is True
        assert result.engine_state == EngineState.HARD_STOP

    def test_signal_allowed_in_normal_state(self):
        rm = RiskManager()
        state = self._state()
        assert rm.is_signal_allowed(state) is True

    def test_signal_blocked_in_soft_stop(self):
        rm = RiskManager()
        state = self._state(daily=0.05)
        state = rm.evaluate(state)
        assert rm.is_signal_allowed(state) is False

    def test_emergency_stop_sets_correct_state(self):
        rm = RiskManager()
        state = rm.trigger_emergency_stop("Test emergency")
        assert state.level == RiskLevel.EMERGENCY
        assert state.engine_state == EngineState.EMERGENCY
        assert state.no_new_signals is True
        assert state.emergency_reason == "Test emergency"

    def test_weekly_soft_stop(self):
        rm = RiskManager()
        state = self._state(weekly=0.10)
        result = rm.evaluate(state)
        assert result.level == RiskLevel.SOFT_STOP

    def test_compute_drawdown(self):
        rm = RiskManager()
        dd = rm.compute_drawdown(current_equity=8000.0, peak_equity=10000.0)
        assert abs(dd - 0.20) < 0.0001

    def test_compute_drawdown_no_decline(self):
        rm = RiskManager()
        dd = rm.compute_drawdown(current_equity=11000.0, peak_equity=10000.0)
        assert dd == 0.0
