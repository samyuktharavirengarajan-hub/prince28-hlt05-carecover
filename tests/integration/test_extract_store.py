"""Validated extraction metadata, written to a real Postgres."""

import pytest
from sqlalchemy import select

from carecover.config import Settings
from carecover.db.models import Document, Page
from carecover.db.session import make_engine, make_sessionmaker
from carecover.llm.doc_meta import DocMeta
from carecover.llm.extract import Extraction, pending, save


@pytest.fixture
async def session(database_url):
    engine = make_engine(Settings(app_env="ci", database_url=database_url, _env_file=None))
    async with make_sessionmaker(engine)() as db:
        await db.execute(Document.__table__.delete())
        await db.commit()
        yield db
    await engine.dispose()


@pytest.fixture
async def document(session):
    doc = Document(
        external_id="extract-test-001",
        title="PM-JAY Knee Replacement Guidelines",
        doc_type="pdf",
        sha256="cd" * 32,
        metadata_={"parser": "pymupdf", "pages": 1, "source": "test"},
    )
    session.add(doc)
    await session.flush()
    session.add(
        Page(
            document_id=doc.id,
            page_no=1,
            text="Knee replacement package details.",
        )
    )
    await session.commit()
    return doc


def valid_record():
    return DocMeta(
        doc_kind="guideline",
        year=2022,
        language="en",
        summary="Guidance about knee replacement package coverage.",
        topics=["knee replacement", "package coverage"],
        scheme=["PM-JAY"],
        package_code=["AB-123"],
        procedure=["knee replacement"],
        rate=["Rs 80,000"],
        preauth_required=["Yes"],
    )


async def test_extraction_is_saved_without_overwriting_parser_metadata(session, document):
    result = Extraction(record=valid_record(), attempts=1, model="fake-model")

    await save(session, document, result, "extract_v1")

    stored = await session.scalar(
        select(Document).where(Document.external_id == "extract-test-001")
    )
    assert stored.metadata_["parser"] == "pymupdf"
    assert stored.metadata_["pages"] == 1
    assert stored.metadata_["source"] == "test"
    assert stored.metadata_["doc_kind"] == "guideline"
    assert stored.metadata_["scheme"] == ["PM-JAY"]
    assert stored.metadata_["package_code"] == ["AB-123"]
    assert stored.metadata_["extract"]["prompt"] == "extract_v1"
    assert stored.metadata_["extract"]["model"] == "fake-model"
    assert stored.metadata_["extract"]["attempts"] == 1
    assert "error" not in stored.metadata_["extract"]


async def test_failed_extraction_is_recorded_and_can_be_retried(session, document):
    result = Extraction(
        record=None,
        attempts=3,
        errors=["topics: Field required"],
        model="fake-model",
    )

    await save(session, document, result, "extract_v1")

    assert document.metadata_["extract"]["prompt"] == "extract_v1"
    assert document.metadata_["extract"]["error"] == "topics: Field required"
    assert await pending(session, "extract_v1") == []
    assert await pending(session, "extract_v1", retry_failed=True) == [document]


async def test_a_new_prompt_version_selects_the_document_again(session, document):
    await save(
        session,
        document,
        Extraction(record=valid_record(), attempts=1, model="fake-model"),
        "extract_v1",
    )

    assert await pending(session, "extract_v1") == []
    assert await pending(session, "extract_v2") == [document]
