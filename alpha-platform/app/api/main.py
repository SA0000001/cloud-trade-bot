"""
Alpha Platform FastAPI Service.

Endpoints:
  GET  /health           — liveness check
  GET  /api/v1/status    — engine status + risk state
  GET  /api/v1/signals   — recent signals
  GET  /api/v1/trades    — open + closed trades
  GET  /api/v1/equity    — equity curve
  POST /api/v1/webhooks/tradingview  — TradingView alert ingestion (stub)
  POST /api/v1/engine/emergency-stop — manual emergency stop
  POST /api/v1/engine/reset-soft-stop — reset soft stop state
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.core.constants import API_VERSION
from app.storage.database import get_db
from app.storage.repositories.repos import (
    EmergencyRepository,
    EquityRepository,
    HeartbeatRepository,
    SignalRepository,
    TradeRepository,
)
from app.utils.logging import setup_logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.log_level)
    logger.info("Alpha Platform API starting up. env=%s", settings.env)
    yield
    logger.info("Alpha Platform API shutting down.")


app = FastAPI(
    title="Alpha Trading Platform API",
    description="Paper trading research and signal monitoring platform.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    version: str
    env: str


class EmergencyStopRequest(BaseModel):
    reason: str


class WebhookPayload(BaseModel):
    """TradingView alert payload — stub format, extend as needed."""
    ticker: str
    action: str
    price: float
    strategy: str = ""
    timeframe: str = ""
    message: str = ""


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health():
    """Liveness check — always returns 200 if the API is running."""
    return HealthResponse(
        status="ok",
        version="0.1.0",
        env=settings.env,
    )


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

@app.get(f"/api/{API_VERSION}/status", tags=["Engine"])
async def get_status(db: AsyncSession = Depends(get_db)):
    """Return engine status and heartbeat summary."""
    hb_repo = HeartbeatRepository(db)
    services = ["paper_engine", "data_feed", "risk_manager", "scheduler"]

    heartbeats = {}
    for svc in services:
        alive = await hb_repo.is_alive(svc, max_age_seconds=180)
        last = await hb_repo.get_last(svc)
        heartbeats[svc] = {
            "alive": alive,
            "last_seen": last.timestamp.isoformat() if last else None,
            "status": last.status if last else "unknown",
        }

    return {
        "api_status": "running",
        "heartbeats": heartbeats,
        "env": settings.env,
    }


# ---------------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------------

@app.get(f"/api/{API_VERSION}/signals", tags=["Signals"])
async def get_signals(
    limit: int = 50,
    asset: str = None,
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Return recent trading signals."""
    repo = SignalRepository(db)
    if asset:
        records = await repo.get_by_asset(asset, limit=limit)
    else:
        records = await repo.get_recent(limit=limit)

    return [
        {
            "id": r.id,
            "asset": r.asset,
            "strategy": r.strategy_name,
            "timeframe": r.timeframe,
            "direction": r.direction,
            "entry": r.entry_price,
            "stop_loss": r.stop_loss,
            "take_profit": r.take_profit,
            "atr": r.atr,
            "robustness": r.robustness_label,
            "reason": r.reason,
            "generated_at": r.generated_at.isoformat() if r.generated_at else None,
        }
        for r in records
    ]


# ---------------------------------------------------------------------------
# Trades
# ---------------------------------------------------------------------------

@app.get(f"/api/{API_VERSION}/trades/open", tags=["Trades"])
async def get_open_trades(db: AsyncSession = Depends(get_db)):
    repo = TradeRepository(db)
    records = await repo.get_open_positions()
    return [
        {
            "id": r.id,
            "asset": r.asset,
            "strategy": r.strategy_name,
            "direction": r.direction,
            "entry": r.entry_price,
            "stop_loss": r.stop_loss,
            "take_profit": r.take_profit,
            "unrealized_pnl": r.unrealized_pnl,
            "opened_at": r.opened_at.isoformat() if r.opened_at else None,
        }
        for r in records
    ]


@app.get(f"/api/{API_VERSION}/trades/closed", tags=["Trades"])
async def get_closed_trades(
    limit: int = 100,
    asset: str = None,
    db: AsyncSession = Depends(get_db),
):
    repo = TradeRepository(db)
    records = await repo.get_closed_trades(limit=limit, asset=asset)
    return [
        {
            "id": r.id,
            "asset": r.asset,
            "strategy": r.strategy_name,
            "direction": r.direction,
            "entry": r.entry_price,
            "exit": r.exit_price,
            "pnl": r.realized_pnl,
            "exit_reason": r.exit_reason,
            "opened_at": r.opened_at.isoformat() if r.opened_at else None,
            "closed_at": r.closed_at.isoformat() if r.closed_at else None,
        }
        for r in records
    ]


@app.get(f"/api/{API_VERSION}/trades/summary", tags=["Trades"])
async def get_trade_summary(db: AsyncSession = Depends(get_db)):
    repo = TradeRepository(db)
    return await repo.get_pnl_summary()


# ---------------------------------------------------------------------------
# Equity
# ---------------------------------------------------------------------------

@app.get(f"/api/{API_VERSION}/equity", tags=["Portfolio"])
async def get_equity_curve(days: int = 30, db: AsyncSession = Depends(get_db)):
    repo = EquityRepository(db)
    records = await repo.get_curve(days=days)
    return [
        {
            "timestamp": r.snapshot_at.isoformat(),
            "equity": r.equity,
            "open_pnl": r.open_pnl,
            "realized_pnl": r.realized_pnl,
            "open_positions": r.open_positions,
        }
        for r in records
    ]


# ---------------------------------------------------------------------------
# Emergency controls
# ---------------------------------------------------------------------------

@app.post(f"/api/{API_VERSION}/engine/emergency-stop", tags=["Engine"])
async def trigger_emergency_stop(
    request: EmergencyStopRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Manually trigger emergency stop from the API.
    This blocks new signals but does NOT auto-close positions.
    Operator must close positions manually.
    """
    from app.storage.models import EmergencyEventRecord
    repo = EmergencyRepository(db)
    event = EmergencyEventRecord(
        event_type="MANUAL_EMERGENCY_STOP",
        reason=request.reason,
        triggered_by="api_user",
        risk_level="EMERGENCY",
        engine_state="EMERGENCY",
    )
    await repo.save(event)
    logger.critical("Manual emergency stop via API. Reason: %s", request.reason)
    return {"status": "emergency_stop_activated", "reason": request.reason}


# ---------------------------------------------------------------------------
# TradingView Webhook (stub)
# ---------------------------------------------------------------------------

@app.post(f"/api/{API_VERSION}/webhooks/tradingview", tags=["Webhooks"])
async def tradingview_webhook(payload: WebhookPayload):
    """
    Receive a TradingView alert.

    TODO: Implement full TradingView bar ingestion.
    Currently logs the payload and returns acknowledgment.
    Future: store bar data, trigger signal generation pipeline.
    """
    logger.info(
        "TradingView webhook received: ticker=%s action=%s price=%.4f",
        payload.ticker, payload.action, payload.price,
    )
    return {
        "received": True,
        "ticker": payload.ticker,
        "note": "TradingView ingestion not yet fully implemented. See TODO in webhook handler.",
    }
