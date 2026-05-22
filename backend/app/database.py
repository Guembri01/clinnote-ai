from __future__ import annotations
"""
ClinNote AI — Async Database Engine & Session Factory
======================================================
Uses SQLAlchemy 2.0 async engine backed by asyncpg for PostgreSQL.
In test environments, aiosqlite is used with an in-memory SQLite database.
"""


from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
_is_sqlite = settings.DATABASE_URL.startswith("sqlite")
_engine_kw: dict = {"echo": settings.ENVIRONMENT == "development"}
if not _is_sqlite:
    _engine_kw.update({"pool_pre_ping": True, "pool_size": 10, "max_overflow": 20, "pool_recycle": 1800})
engine = create_async_engine(settings.DATABASE_URL, **_engine_kw)

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ---------------------------------------------------------------------------
# Declarative base (shared by all models)
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    """
    Base class for all ORM models.
    All subclasses inherit metadata tracking and the async engine.
    """
    pass


# ---------------------------------------------------------------------------
# Dependency — async session per request
# ---------------------------------------------------------------------------
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an async database session.
    The session is committed on success and rolled back on exception,
    then always closed.

    Usage:
        @router.get("/")
        async def my_route(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ---------------------------------------------------------------------------
# Create all tables (used in lifespan)
# ---------------------------------------------------------------------------
async def create_tables() -> None:
    """
    Create all database tables derived from Base metadata.
    Called once on application startup via the FastAPI lifespan handler.
    In production, use Alembic migrations instead.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
