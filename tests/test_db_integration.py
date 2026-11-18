import os
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from carecover.db.models import Document, Page
from carecover.db.url import to_asyncpg_url

DATABASE_URL = os.getenv("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="TEST_DATABASE_URL is not configured",
)


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(
        to_asyncpg_url(DATABASE_URL),
        pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_insert_and_retrieve_document(db_session):
    external_id = f"TEST-{uuid4().hex[:12]}"

    document = Document(
        external_id=external_id,
        title="Integration test document",
        doc_type="record",
        metadata_={"scheme": "TEST"},
    )

    db_session.add(document)
    await db_session.commit()

    result = await db_session.scalar(select(Document).where(Document.external_id == external_id))

    assert result is not None
    assert result.title == "Integration test document"

    await db_session.delete(result)
    await db_session.commit()


@pytest.mark.asyncio
async def test_jsonb_metadata_filter(db_session):
    external_id = f"TEST-{uuid4().hex[:12]}"

    document = Document(
        external_id=external_id,
        title="JSONB integration test",
        doc_type="record",
        metadata_={"scheme": "TEST_FILTER"},
    )

    db_session.add(document)
    await db_session.commit()

    result = await db_session.scalar(
        select(Document).where(Document.metadata_.contains({"scheme": "TEST_FILTER"}))
    )

    assert result is not None
    assert result.external_id == external_id

    await db_session.delete(document)
    await db_session.commit()


@pytest.mark.asyncio
async def test_document_page_relationship(db_session):
    external_id = f"TEST-{uuid4().hex[:12]}"

    document = Document(
        external_id=external_id,
        title="Page relationship test",
        doc_type="record",
        metadata_={},
    )

    db_session.add(document)
    await db_session.flush()

    page = Page(
        document_id=document.id,
        page_no=1,
        text="This is an integration test page.",
    )

    db_session.add(page)
    await db_session.commit()

    result = await db_session.scalar(select(Page).where(Page.document_id == document.id))

    assert result is not None
    assert result.page_no == 1

    await db_session.delete(document)
    await db_session.commit()
