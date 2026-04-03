"""
Repository layer — all DB access goes through these classes.
No raw SQL in business logic. No ORM queries in Streamlit pages.

Repositories are split by domain entity.
Each repository has both async (FastAPI) and sync (scripts) variants.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.storage.models import (
    BacktestRunRecord,
    ClosedTradeRecord,
    EmergencyEventRecord,
    EquitySnapshotRecord,
    HeartbeatRecord,
    PaperPositionRecord,
    SignalRecord,
    StrategyHealthRecord,
    WalkForwardRunRecord,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Signal Repository
# ---------------------------------------------------------------------------

class SignalRepository:

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, record: SignalRecord) -> SignalRecord:
        self._session.add(record)
        await self._session.flush()
        return record

    async def get_recent(self, limit: int = 50) -> List[SignalRecord]:
        result = await self._session.execute(
            select(SignalRecord)
            .order_by(desc(SignalRecord.generated_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_asset(self, asset: str, limit: int = 100) -> List[SignalRecord]:
        result = await self._session.execute(
            select(SignalRecord)
            .where(SignalRecord.asset == asset)
            .order_by(desc(SignalRecord.generated_at))
            .limit(limit)
        )
        return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Trade Repository
# ---------------------------------------------------------------------------

class TradeRepository:

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_position(self, record: PaperPositionRecord) -> PaperPositionRecord:
        self._session.add(record)
        await self._session.flush()
        return record

    async def save_closed_trade(self, record: ClosedTradeRecord) -> ClosedTradeRecord:
        self._session.add(record)
        await self._session.flush()
        return record

    async def get_open_positions(self) -> List[PaperPositionRecord]:
        result = await self._session.execute(
            select(PaperPositionRecord)
            .where(PaperPositionRecord.status == "OPEN")
            .order_by(desc(PaperPositionRecord.opened_at))
        )
        return list(result.scalars().all())

    async def get_closed_trades(
        self,
        limit: int = 200,
        asset: Optional[str] = None,
        strategy: Optional[str] = None,
    ) -> List[ClosedTradeRecord]:
        q = select(ClosedTradeRecord).order_by(desc(ClosedTradeRecord.closed_at))
        if asset:
            q = q.where(ClosedTradeRecord.asset == asset)
        if strategy:
            q = q.where(ClosedTradeRecord.strategy_name == strategy)
        q = q.limit(limit)
        result = await self._session.execute(q)
        return list(result.scalars().all())

    async def get_pnl_summary(self) -> dict:
        """Quick aggregate summary for dashboard. Returns raw dict."""
        closed = await self.get_closed_trades(limit=10000)
        total_pnl = sum(t.realized_pnl or 0.0 for t in closed)
        wins = [t for t in closed if (t.realized_pnl or 0.0) > 0]
        win_rate = len(wins) / max(len(closed), 1)
        return {
            "total_trades": len(closed),
            "total_pnl": total_pnl,
            "win_rate": win_rate,
            "winning_trades": len(wins),
            "losing_trades": len(closed) - len(wins),
        }


# ---------------------------------------------------------------------------
# Backtest Repository
# ---------------------------------------------------------------------------

class BacktestRepository:

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, record: BacktestRunRecord) -> BacktestRunRecord:
        self._session.add(record)
        await self._session.flush()
        return record

    async def get_by_strategy_asset(
        self, strategy: str, asset: str, limit: int = 20
    ) -> List[BacktestRunRecord]:
        result = await self._session.execute(
            select(BacktestRunRecord)
            .where(
                BacktestRunRecord.strategy_name == strategy,
                BacktestRunRecord.asset == asset,
            )
            .order_by(desc(BacktestRunRecord.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_best_per_asset(self) -> List[BacktestRunRecord]:
        """Return the highest robustness_score record per asset+strategy."""
        # TODO: upgrade to window function query for true per-group best
        result = await self._session.execute(
            select(BacktestRunRecord)
            .order_by(desc(BacktestRunRecord.robustness_score))
            .limit(50)
        )
        return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Heartbeat Repository
# ---------------------------------------------------------------------------

class HeartbeatRepository:

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def ping(
        self,
        service_name: str,
        status: str = "ok",
        message: str = "",
    ) -> HeartbeatRecord:
        record = HeartbeatRecord(
            service_name=service_name,
            status=status,
            message=message,
            timestamp=datetime.utcnow(),
        )
        self._session.add(record)
        await self._session.flush()
        return record

    async def get_last(self, service_name: str) -> Optional[HeartbeatRecord]:
        result = await self._session.execute(
            select(HeartbeatRecord)
            .where(HeartbeatRecord.service_name == service_name)
            .order_by(desc(HeartbeatRecord.timestamp))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def is_alive(
        self, service_name: str, max_age_seconds: int = 120
    ) -> bool:
        record = await self.get_last(service_name)
        if record is None:
            return False
        age = (datetime.utcnow() - record.timestamp).total_seconds()
        return age < max_age_seconds


# ---------------------------------------------------------------------------
# Emergency Event Repository
# ---------------------------------------------------------------------------

class EmergencyRepository:

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, record: EmergencyEventRecord) -> EmergencyEventRecord:
        self._session.add(record)
        await self._session.flush()
        return record

    async def get_recent(self, limit: int = 20) -> List[EmergencyEventRecord]:
        result = await self._session.execute(
            select(EmergencyEventRecord)
            .order_by(desc(EmergencyEventRecord.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_unresolved(self) -> List[EmergencyEventRecord]:
        result = await self._session.execute(
            select(EmergencyEventRecord)
            .where(EmergencyEventRecord.resolved == False)  # noqa: E712
            .order_by(desc(EmergencyEventRecord.created_at))
        )
        return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Equity Repository
# ---------------------------------------------------------------------------

class EquityRepository:

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_snapshot(self, record: EquitySnapshotRecord) -> EquitySnapshotRecord:
        self._session.add(record)
        await self._session.flush()
        return record

    async def get_curve(self, days: int = 30) -> List[EquitySnapshotRecord]:
        since = datetime.utcnow() - timedelta(days=days)
        result = await self._session.execute(
            select(EquitySnapshotRecord)
            .where(EquitySnapshotRecord.snapshot_at >= since)
            .order_by(EquitySnapshotRecord.snapshot_at)
        )
        return list(result.scalars().all())
