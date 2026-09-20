"""Async database engine and session dependency."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.db_echo,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=True,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request, closed cleanly at the end of it.

    The `rollback()` after a successful request is not tidiness — it is required. A read-only
    request still opens a transaction (SQLAlchemy starts one on the first SELECT), and a
    connection returned to the pool without committing or rolling back sits **idle in
    transaction** until it is reused.

    That was a real outage here. A handful of idle-in-transaction sessions from ordinary GET
    requests blocked the LangGraph checkpointer's `CREATE INDEX CONCURRENTLY` at startup on a
    fresh database — that statement waits for every open transaction to finish — and every
    case stopped before its first node with no error anywhere. Endpoints that write still
    commit explicitly; this only ends the transaction a read left open.
    """
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.rollback()
