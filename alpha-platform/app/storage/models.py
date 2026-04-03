"""
SQLAlchemy ORM models for PostgreSQL.

All models inherit from Base (declarative).
Use Alembic for schema migrations — do not auto-create tables in production.

Schema design:
  - signals            — every signal ever generated
  - paper_positions    — open paper trades (denormalized for speed)
  - closed_trades      — historical closed paper trades
  - backtest_runs      — every backtest executed
  - strategy_health    — periodic strategy health snapshots
  - engine_heartbeat   — heartbeat pings from services
  - emergency_events   — log of all emergency/stop events
  - equity_snapshots   — periodic equity curve records
  - walk_forward_runs  — WF optimization run summaries
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------------

class SignalRecord(Base):
    __tablename__ = "signals"

    id = Column(String(36), primary_key=True, default=_uuid)
    asset = Column(String(20), nullable=False, index=True)
    strategy_name = Column(String(100), nullable=False, index=True)
    strategy_family = Column(String(50))
    timeframe = Column(String(10))
    direction = Column(String(10))
    entry_price = Column(Float, nullable=False)
    stop_loss = Column(Float)
    take_profit = Column(Float)
    atr = Column(Float)
    regime = Column(String(30))
    robustness_label = Column(String(30))
    confidence_score = Column(Float, default=0.5)
    reason = Column(Text)
    generated_at = Column(DateTime, default=datetime.utcnow, index=True)
    metadata_ = Column("metadata", JSON, default=dict)


# ---------------------------------------------------------------------------
# Paper positions (open trades)
# ---------------------------------------------------------------------------

class PaperPositionRecord(Base):
    __tablename__ = "paper_positions"

    id = Column(String(36), primary_key=True, default=_uuid)
    signal_id = Column(String(36), index=True)
    asset = Column(String(20), nullable=False, index=True)
    strategy_name = Column(String(100))
    timeframe = Column(String(10))
    direction = Column(String(10))
    entry_price = Column(Float, nullable=False)
    stop_loss = Column(Float)
    take_profit = Column(Float)
    quantity = Column(Float, default=1.0)
    unrealized_pnl = Column(Float, default=0.0)
    status = Column(String(20), default="OPEN", index=True)
    opened_at = Column(DateTime, default=datetime.utcnow, index=True)
    metadata_ = Column("metadata", JSON, default=dict)


# ---------------------------------------------------------------------------
# Closed trades
# ---------------------------------------------------------------------------

class ClosedTradeRecord(Base):
    __tablename__ = "closed_trades"

    id = Column(String(36), primary_key=True, default=_uuid)
    signal_id = Column(String(36), index=True)
    asset = Column(String(20), nullable=False, index=True)
    strategy_name = Column(String(100), index=True)
    timeframe = Column(String(10))
    direction = Column(String(10))
    entry_price = Column(Float)
    exit_price = Column(Float)
    quantity = Column(Float)
    realized_pnl = Column(Float)
    exit_reason = Column(String(50))
    opened_at = Column(DateTime)
    closed_at = Column(DateTime, default=datetime.utcnow, index=True)
    metadata_ = Column("metadata", JSON, default=dict)


# ---------------------------------------------------------------------------
# Backtest runs
# ---------------------------------------------------------------------------

class BacktestRunRecord(Base):
    __tablename__ = "backtest_runs"

    id = Column(String(36), primary_key=True, default=_uuid)
    strategy_name = Column(String(100), nullable=False, index=True)
    asset = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(10), index=True)
    parameters = Column(JSON)
    in_sample = Column(Boolean, default=True)
    period_start = Column(DateTime)
    period_end = Column(DateTime)

    # Metrics
    total_return_pct = Column(Float)
    profit_factor = Column(Float)
    sharpe_ratio = Column(Float)
    sortino_ratio = Column(Float)
    max_drawdown_pct = Column(Float)
    recovery_factor = Column(Float)
    expectancy = Column(Float)
    total_trades = Column(Integer)
    win_rate = Column(Float)
    robustness_score = Column(Float)
    robustness_label = Column(String(30))
    notes = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# ---------------------------------------------------------------------------
# Walk-forward runs
# ---------------------------------------------------------------------------

class WalkForwardRunRecord(Base):
    __tablename__ = "walk_forward_runs"

    id = Column(String(36), primary_key=True, default=_uuid)
    strategy_name = Column(String(100), nullable=False, index=True)
    asset = Column(String(20), nullable=False)
    timeframe = Column(String(10))
    param_grid = Column(JSON)
    windows = Column(JSON)
    wf_efficiency = Column(Float)
    consistency_score = Column(Float)
    passed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# ---------------------------------------------------------------------------
# Strategy health snapshots
# ---------------------------------------------------------------------------

class StrategyHealthRecord(Base):
    __tablename__ = "strategy_health"

    id = Column(String(36), primary_key=True, default=_uuid)
    strategy_name = Column(String(100), nullable=False, index=True)
    asset = Column(String(20), index=True)
    timeframe = Column(String(10))
    live_profit_factor = Column(Float)
    live_sharpe = Column(Float)
    live_win_rate = Column(Float)
    live_total_trades = Column(Integer)
    expected_profit_factor = Column(Float)  # from backtest
    degradation_flag = Column(Boolean, default=False)
    regime = Column(String(30))
    robustness_label = Column(String(30))
    notes = Column(Text)
    snapshot_at = Column(DateTime, default=datetime.utcnow, index=True)


# ---------------------------------------------------------------------------
# Engine heartbeat
# ---------------------------------------------------------------------------

class HeartbeatRecord(Base):
    __tablename__ = "engine_heartbeat"

    id = Column(Integer, primary_key=True, autoincrement=True)
    service_name = Column(String(100), nullable=False, index=True)
    status = Column(String(20), default="ok")
    message = Column(Text)
    metadata_ = Column("metadata", JSON, default=dict)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)


# ---------------------------------------------------------------------------
# Emergency events
# ---------------------------------------------------------------------------

class EmergencyEventRecord(Base):
    __tablename__ = "emergency_events"

    id = Column(String(36), primary_key=True, default=_uuid)
    event_type = Column(String(50), nullable=False, index=True)
    reason = Column(Text)
    triggered_by = Column(String(100))   # "system" | "user" | "risk_manager"
    risk_level = Column(String(30))
    engine_state = Column(String(30))
    daily_dd_pct = Column(Float)
    weekly_dd_pct = Column(Float)
    total_dd_pct = Column(Float)
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# ---------------------------------------------------------------------------
# Equity snapshots
# ---------------------------------------------------------------------------

class EquitySnapshotRecord(Base):
    __tablename__ = "equity_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    equity = Column(Float, nullable=False)
    open_pnl = Column(Float, default=0.0)
    realized_pnl = Column(Float, default=0.0)
    open_positions = Column(Integer, default=0)
    snapshot_at = Column(DateTime, default=datetime.utcnow, index=True)
