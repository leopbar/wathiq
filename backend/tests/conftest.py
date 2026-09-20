"""Test fixtures.

Tests run inside the api container against a throwaway `*_test` database, which is created,
migrated (via metadata) and seeded once per session.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator

import psycopg
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.db.base import Base
from app.db.seed import seed
from app.db.session import SessionLocal, engine
from app.main import app


def _ensure_test_database() -> None:
    url = settings.sync_database_url
    db_name = url.rsplit("/", 1)[-1].split("?")[0]
    if not db_name.endswith("_test"):
        raise RuntimeError(
            f"Refusing to run tests against '{db_name}'. "
            "Set WATHIQ_DATABASE_URL to a database whose name ends with _test."
        )
    admin_url = url.rsplit("/", 1)[0] + "/postgres"
    with psycopg.connect(admin_url, autocommit=True) as connection:
        exists = connection.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (db_name,)
        ).fetchone()
        if not exists:
            connection.execute(f'CREATE DATABASE "{db_name}"')


@pytest.fixture(scope="session")
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def prepared_database() -> AsyncIterator[None]:
    _ensure_test_database()
    async with engine.begin() as connection:
        await connection.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
        await connection.exec_driver_sql("DROP SEQUENCE IF EXISTS events_seq CASCADE")
        await connection.run_sync(Base.metadata.drop_all)
        await connection.exec_driver_sql("CREATE SEQUENCE events_seq")
        await connection.run_sync(Base.metadata.create_all)
    await seed(force=True)
    yield
    await engine.dispose()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client


async def _token(client: AsyncClient, role: str) -> str:
    response = await client.post("/api/v1/auth/demo-login", json={"role": role})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.fixture
async def auth(client: AsyncClient):
    """`await auth("reviewer")` -> headers for that demo role."""

    async def _headers(role: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {await _token(client, role)}"}

    return _headers


@pytest.fixture
async def db_session():
    async with SessionLocal() as session:
        yield session
