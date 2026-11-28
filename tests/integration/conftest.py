"""Integration tests use a fresh PostgreSQL database for every test run."""

import asyncio
import uuid

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from carecover.config import get_settings
from carecover.db.url import to_asyncpg_url

BASE_URL = "postgresql://app:app@localhost:5433/app_test"  # pragma: allowlist secret


async def execute_admin_sql(sql: str) -> None:
    """Execute database creation or deletion using the admin database."""
    engine = create_async_engine(
        to_asyncpg_url(BASE_URL),
        isolation_level="AUTOCOMMIT",
    )

    try:
        async with engine.connect() as connection:
            await connection.execute(text(sql))
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def database_url():
    """Create, migrate and finally drop a unique database for this test run."""
    database_name = f"test_{uuid.uuid4().hex[:12]}"

    asyncio.run(execute_admin_sql(f'CREATE DATABASE "{database_name}"'))

    url = make_url(to_asyncpg_url(BASE_URL)).set(database=database_name)
    test_url = url.render_as_string(hide_password=False)

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("APP_ENV", "ci")
    monkeypatch.setenv("DATABASE_URL", test_url)

    get_settings.cache_clear()

    try:
        alembic_config = Config("alembic.ini")
        command.upgrade(alembic_config, "head")

        yield test_url
    finally:
        get_settings.cache_clear()
        monkeypatch.undo()
        asyncio.run(execute_admin_sql(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)'))
