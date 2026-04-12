"""
IncidentOps - Async SQLite Database Layer
"""
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./incidentops.db",
)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base"""
    pass


engine = create_async_engine(
    DATABASE_URL,
    echo=bool(os.environ.get("SQLALCHEMY_ECHO", "")),
    future=True,
)

_async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for DB sessions"""
    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:  # pragma: no cover
            await session.rollback()  # pragma: no cover
            raise  # pragma: no cover
        finally:  # pragma: no cover
            await session.close()  # pragma: no cover


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Standalone context manager for non-FastAPI usage"""
    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:  # pragma: no cover
            await session.rollback()  # pragma: no cover
            raise  # pragma: no cover


async def init_db() -> None:
    """Create all tables — safe to call multiple times"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close engine on shutdown"""
    await engine.dispose()
