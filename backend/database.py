"""Database connection and session management for Neon PostgreSQL."""
from __future__ import annotations

import asyncio
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from backend.core.config import settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy declarative models."""
    pass


_async_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None
_engine_loop: asyncio.AbstractEventLoop | None = None


def get_engine() -> AsyncEngine:
    """Get or create loop-aware async engine with secure SSL connectivity."""
    global _async_engine, _async_session_factory, _engine_loop
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    if _async_engine is None or (_engine_loop is not None and current_loop is not None and current_loop != _engine_loop):
        _engine_loop = current_loop
        url = settings.async_database_url
        if not url:
            # Fallback to local SQLite in-memory for testing if DATABASE_URL is unset
            url = "sqlite+aiosqlite:///:memory:"
            _async_engine = create_async_engine(url, echo=False)
        else:
            _async_engine = create_async_engine(
                url,
                echo=False,
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=20,
                connect_args={"ssl": "require"},
            )
        _async_session_factory = async_sessionmaker(
            _async_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create session factory."""
    global _async_session_factory
    get_engine()
    assert _async_session_factory is not None
    return _async_session_factory


async def init_db() -> None:
    """Initialize database tables if they do not exist."""
    engine = get_engine()
    from backend import models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding active AsyncSession."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
