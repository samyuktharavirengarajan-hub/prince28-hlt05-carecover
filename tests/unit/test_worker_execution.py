from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from carecover.workers.ingest import ingest_document


@pytest.mark.asyncio
async def test_completed_item_is_ignored():
    item = SimpleNamespace(status="done", attempts=1)

    session = AsyncMock()
    session.__aenter__.return_value = session
    session.get.return_value = item

    ctx = {
        "settings": SimpleNamespace(ingest_max_tries=3),
        "sessionmaker": lambda: session,
    }

    result = await ingest_document(ctx, 42)

    assert result == "ignored"
    assert item.status == "done"
    assert item.attempts == 1
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_item_is_ignored():
    session = AsyncMock()
    session.__aenter__.return_value = session
    session.get.return_value = None

    ctx = {
        "settings": SimpleNamespace(ingest_max_tries=3),
        "sessionmaker": lambda: session,
    }

    result = await ingest_document(ctx, 999)

    assert result == "ignored"
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_permanent_failure_marks_item_failed(monkeypatch):
    from carecover.workers import ingest

    item = SimpleNamespace(status="queued", attempts=0, error="", pages=0)

    session = AsyncMock()
    session.__aenter__.return_value = session
    session.get.return_value = item

    async def fail_permanently(ctx, session, item):
        raise ingest.Permanent("parse: no_text_layer")

    monkeypatch.setattr(ingest, "process", fail_permanently)

    ctx = {
        "settings": SimpleNamespace(ingest_max_tries=3),
        "sessionmaker": lambda: session,
    }

    result = await ingest.ingest_document(ctx, 42)

    assert result == "failed"
    assert item.status == "failed"
    assert item.attempts == 1
    assert item.error == "parse: no_text_layer"
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_temporary_failure_requeues_and_retries(monkeypatch):
    from arq import Retry

    from carecover.workers import ingest

    item = SimpleNamespace(status="queued", attempts=0, error="", pages=0)

    session = AsyncMock()
    session.__aenter__.return_value = session
    session.get.return_value = item

    async def fail_temporarily(ctx, session, item):
        raise RuntimeError("provider temporarily unavailable")

    monkeypatch.setattr(ingest, "process", fail_temporarily)

    ctx = {
        "settings": SimpleNamespace(ingest_max_tries=3),
        "sessionmaker": lambda: session,
    }

    with pytest.raises(Retry):
        await ingest.ingest_document(ctx, 42)

    assert item.status == "queued"
    assert item.attempts == 1
    assert "provider temporarily unavailable" in item.error
    assert session.commit.await_count == 2


@pytest.mark.asyncio
async def test_max_attempts_marks_item_failed():
    item = SimpleNamespace(
        status="queued",
        attempts=3,
        error="",
        pages=0,
    )

    session = AsyncMock()
    session.__aenter__.return_value = session
    session.get.return_value = item

    ctx = {
        "settings": SimpleNamespace(ingest_max_tries=3),
        "sessionmaker": lambda: session,
    }

    result = await ingest_document(ctx, 42)

    assert result == "failed"
    assert item.status == "failed"
    assert item.attempts == 3
    assert "never finished" in item.error
    session.commit.assert_awaited_once()
