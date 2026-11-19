from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from carecover.config import Settings
from carecover.db.models import Document, Page
from carecover.db.repository import DocumentRepository
from carecover.db.session import make_engine, make_sessionmaker


@pytest.fixture
async def db_session(database_url):
    """Provide a session connected to the fresh integration-test database."""
    settings = Settings(
        app_env="ci",
        database_url=database_url,
        _env_file=None,
    )

    engine = make_engine(settings)
    session_factory = make_sessionmaker(engine)

    try:
        async with session_factory() as session:
            yield session
    finally:
        await engine.dispose()


async def test_insert_and_retrieve_document(db_session):
    external_id = f"TEST-{uuid4().hex[:12]}"

    document = Document(
        external_id=external_id,
        title="Integration test document",
        doc_type="record",
        metadata_={"scheme": "TEST"},
        sha256="a" * 64,
    )

    db_session.add(document)
    await db_session.commit()

    result = await db_session.scalar(select(Document).where(Document.external_id == external_id))

    assert result is not None
    assert result.title == "Integration test document"


async def test_jsonb_metadata_filter(db_session):
    external_id = f"TEST-{uuid4().hex[:12]}"

    document = Document(
        external_id=external_id,
        title="JSONB integration test",
        doc_type="record",
        metadata_={"scheme": "TEST_FILTER"},
        sha256="b" * 64,
    )

    db_session.add(document)
    await db_session.commit()

    result = await db_session.scalar(
        select(Document).where(Document.metadata_.contains({"scheme": "TEST_FILTER"}))
    )

    assert result is not None
    assert result.external_id == external_id


async def test_document_page_relationship(db_session):
    external_id = f"TEST-{uuid4().hex[:12]}"

    document = Document(
        external_id=external_id,
        title="Page relationship test",
        doc_type="record",
        metadata_={},
        sha256="c" * 64,
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


async def test_repository_case_insensitive_search(db_session):
    external_id = f"SEARCH-{uuid4().hex[:12]}"

    document = Document(
        external_id=external_id,
        title="CareCover Integration Search",
        doc_type="record",
        metadata_={},
        sha256="d" * 64,
    )

    db_session.add(document)
    await db_session.commit()

    repository = DocumentRepository(db_session)
    result = await repository.list(q="carecover integration search")

    assert result["total"] >= 1
    assert any(item["id"] == external_id for item in result["items"])


async def test_repository_pagination(db_session):
    token = uuid4().hex[:12]

    documents = [
        Document(
            external_id=f"PAGE-{token}-{number}",
            title=f"Pagination test {token} {number}",
            doc_type="record",
            metadata_={},
            sha256="e" * 64,
        )
        for number in range(3)
    ]

    db_session.add_all(documents)
    await db_session.commit()

    repository = DocumentRepository(db_session)
    result = await repository.list(q=token, limit=2, offset=1)

    assert result["total"] == 3
    assert len(result["items"]) == 2
    assert result["limit"] == 2
    assert result["offset"] == 1


async def test_duplicate_external_id_is_rejected(db_session):
    external_id = f"DUPLICATE-{uuid4().hex[:12]}"

    document_one = Document(
        external_id=external_id,
        title="First document",
        doc_type="record",
        metadata_={},
        sha256="f" * 64,
    )

    document_two = Document(
        external_id=external_id,
        title="Duplicate document",
        doc_type="record",
        metadata_={},
        sha256="g" * 64,
    )

    db_session.add(document_one)
    await db_session.commit()

    db_session.add(document_two)

    with pytest.raises(IntegrityError):
        await db_session.commit()

    await db_session.rollback()


async def test_page_number_must_be_positive(db_session):
    document = Document(
        external_id=f"INVALID-PAGE-{uuid4().hex[:12]}",
        title="Invalid page test",
        doc_type="record",
        metadata_={},
        sha256="h" * 64,
    )

    db_session.add(document)
    await db_session.flush()

    page = Page(
        document_id=document.id,
        page_no=0,
        text="This page number should be rejected.",
    )

    db_session.add(page)

    with pytest.raises(IntegrityError):
        await db_session.commit()

    await db_session.rollback()
