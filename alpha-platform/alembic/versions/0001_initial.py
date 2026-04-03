"""Initial schema — create all tables

Revision ID: 0001_initial
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "signals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("asset", sa.String(20), nullable=False),
        sa.Column("strategy_name", sa.String(100), nullable=False),
        sa.Column("strategy_family", sa.String(50)),
        sa.Column("timeframe", sa.String(10)),
        sa.Column("direction", sa.String(10)),
        sa.Column("entry_price", sa.Float, nullable=False),
        sa.Column("stop_loss", sa.Float),
        sa.Column("take_profit", sa.Float),
        sa.Column("atr", sa.Float),
        sa.Column("regime", sa.String(30)),
        sa.Column("robustness_label", sa.String(30)),
        sa.Column("confidence_score", sa.Float),
        sa.Column("reason", sa.Text),
        sa.Column("generated_at", sa.DateTime),
        sa.Column("metadata", sa.JSON),
    )
    op.create_index("ix_signals_asset", "signals", ["asset"])
    op.create_index("ix_signals_strategy_name", "signals", ["strategy_name"])
    op.create_index("ix_signals_generated_at", "signals", ["generated_at"])

    op.create_table(
        "paper_positions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("signal_id", sa.String(36)),
        sa.Column("asset", sa.String(20), nullable=False),
        sa.Column("strategy_name", sa.String(100)),
        sa.Column("timeframe", sa.String(10)),
        sa.Column("direction", sa.String(10)),
        sa.Column("entry_price", sa.Float, nullable=False),
        sa.Column("stop_loss", sa.Float),
        sa.Column("take_profit", sa.Float),
        sa.Column("quantity", sa.Float),
        sa.Column("unrealized_pnl", sa.Float),
        sa.Column("status", sa.String(20)),
        sa.Column("opened_at", sa.DateTime),
        sa.Column("metadata", sa.JSON),
    )
    op.create_index("ix_paper_positions_asset", "paper_positions", ["asset"])
    op.create_index("ix_paper_positions_status", "paper_positions", ["status"])

    op.create_table(
        "closed_trades",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("signal_id", sa.String(36)),
        sa.Column("asset", sa.String(20), nullable=False),
        sa.Column("strategy_name", sa.String(100)),
        sa.Column("timeframe", sa.String(10)),
        sa.Column("direction", sa.String(10)),
        sa.Column("entry_price", sa.Float),
        sa.Column("exit_price", sa.Float),
        sa.Column("quantity", sa.Float),
        sa.Column("realized_pnl", sa.Float),
        sa.Column("exit_reason", sa.String(50)),
        sa.Column("opened_at", sa.DateTime),
        sa.Column("closed_at", sa.DateTime),
        sa.Column("metadata", sa.JSON),
    )
    op.create_index("ix_closed_trades_asset", "closed_trades", ["asset"])
    op.create_index("ix_closed_trades_strategy_name", "closed_trades", ["strategy_name"])
    op.create_index("ix_closed_trades_closed_at", "closed_trades", ["closed_at"])

    op.create_table(
        "backtest_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("strategy_name", sa.String(100), nullable=False),
        sa.Column("asset", sa.String(20), nullable=False),
        sa.Column("timeframe", sa.String(10)),
        sa.Column("parameters", sa.JSON),
        sa.Column("in_sample", sa.Boolean),
        sa.Column("period_start", sa.DateTime),
        sa.Column("period_end", sa.DateTime),
        sa.Column("total_return_pct", sa.Float),
        sa.Column("profit_factor", sa.Float),
        sa.Column("sharpe_ratio", sa.Float),
        sa.Column("sortino_ratio", sa.Float),
        sa.Column("max_drawdown_pct", sa.Float),
        sa.Column("recovery_factor", sa.Float),
        sa.Column("expectancy", sa.Float),
        sa.Column("total_trades", sa.Integer),
        sa.Column("win_rate", sa.Float),
        sa.Column("robustness_score", sa.Float),
        sa.Column("robustness_label", sa.String(30)),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime),
    )
    op.create_index("ix_backtest_runs_strategy_name", "backtest_runs", ["strategy_name"])
    op.create_index("ix_backtest_runs_asset", "backtest_runs", ["asset"])
    op.create_index("ix_backtest_runs_created_at", "backtest_runs", ["created_at"])

    op.create_table(
        "walk_forward_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("strategy_name", sa.String(100), nullable=False),
        sa.Column("asset", sa.String(20)),
        sa.Column("timeframe", sa.String(10)),
        sa.Column("param_grid", sa.JSON),
        sa.Column("windows", sa.JSON),
        sa.Column("wf_efficiency", sa.Float),
        sa.Column("consistency_score", sa.Float),
        sa.Column("passed", sa.Boolean),
        sa.Column("created_at", sa.DateTime),
    )
    op.create_index("ix_walk_forward_runs_strategy_name", "walk_forward_runs", ["strategy_name"])

    op.create_table(
        "strategy_health",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("strategy_name", sa.String(100), nullable=False),
        sa.Column("asset", sa.String(20)),
        sa.Column("timeframe", sa.String(10)),
        sa.Column("live_profit_factor", sa.Float),
        sa.Column("live_sharpe", sa.Float),
        sa.Column("live_win_rate", sa.Float),
        sa.Column("live_total_trades", sa.Integer),
        sa.Column("expected_profit_factor", sa.Float),
        sa.Column("degradation_flag", sa.Boolean),
        sa.Column("regime", sa.String(30)),
        sa.Column("robustness_label", sa.String(30)),
        sa.Column("notes", sa.Text),
        sa.Column("snapshot_at", sa.DateTime),
    )
    op.create_index("ix_strategy_health_strategy_name", "strategy_health", ["strategy_name"])
    op.create_index("ix_strategy_health_snapshot_at", "strategy_health", ["snapshot_at"])

    op.create_table(
        "engine_heartbeat",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("service_name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20)),
        sa.Column("message", sa.Text),
        sa.Column("metadata", sa.JSON),
        sa.Column("timestamp", sa.DateTime),
    )
    op.create_index("ix_engine_heartbeat_service_name", "engine_heartbeat", ["service_name"])
    op.create_index("ix_engine_heartbeat_timestamp", "engine_heartbeat", ["timestamp"])

    op.create_table(
        "emergency_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("reason", sa.Text),
        sa.Column("triggered_by", sa.String(100)),
        sa.Column("risk_level", sa.String(30)),
        sa.Column("engine_state", sa.String(30)),
        sa.Column("daily_dd_pct", sa.Float),
        sa.Column("weekly_dd_pct", sa.Float),
        sa.Column("total_dd_pct", sa.Float),
        sa.Column("resolved", sa.Boolean),
        sa.Column("resolved_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime),
    )
    op.create_index("ix_emergency_events_event_type", "emergency_events", ["event_type"])
    op.create_index("ix_emergency_events_created_at", "emergency_events", ["created_at"])

    op.create_table(
        "equity_snapshots",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("equity", sa.Float, nullable=False),
        sa.Column("open_pnl", sa.Float),
        sa.Column("realized_pnl", sa.Float),
        sa.Column("open_positions", sa.Integer),
        sa.Column("snapshot_at", sa.DateTime),
    )
    op.create_index("ix_equity_snapshots_snapshot_at", "equity_snapshots", ["snapshot_at"])


def downgrade() -> None:
    for table in [
        "equity_snapshots",
        "emergency_events",
        "engine_heartbeat",
        "strategy_health",
        "walk_forward_runs",
        "backtest_runs",
        "closed_trades",
        "paper_positions",
        "signals",
    ]:
        op.drop_table(table)
