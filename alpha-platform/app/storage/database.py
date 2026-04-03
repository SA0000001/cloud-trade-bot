"""
Database session factory.

Uses SQLAlchemy async engine for FastAPI compatibility.
Sync engine also available for scripts and workers.

Usage (async):
    from app.storage.database import get_async_session
    async with get_async_session() as session:
        result = await session.execute(...)

Usage (sync, scripts):
    from app.storage.database import SyncSessionLocal
    with SyncSessionLocal() as session:
        ...
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager, contextmanager
from typing import AsyncGenerator, Generator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Async engine (FastAPI, background workers)
# ---------------------------------------------------------------------------

async_engine = create_async_engine(
    settings.database.url,
    pool_size=settings.database.pool_size,
    echo=settings.database.echo,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency-injectable async session context manager."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# Sync engine (scripts, Celery workers, Alembic)
# ---------------------------------------------------------------------------

# Convert asyncpg URL to psycopg2 for sync operations
_sync_url = settings.database.url.replace("+asyncpg", "+psycopg2").replace(
    "postgresql+asyncpg", "postgresql"
)

sync_engine = create_engine(
    _sync_url,
    pool_size=settings.database.pool_size,
    echo=settings.database.echo,
    future=True,
)

SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False,
)


@contextmanager
def get_sync_session() -> Generator[Session, None, None]:
    """Sync session context manager for scripts and workers."""
    with SyncSessionLocal() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for injecting async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
