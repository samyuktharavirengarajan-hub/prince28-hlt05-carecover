from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from carecover.api.deps import (
    check_db,
    get_ingest_repo,
    get_manifest,
    get_queue,
    get_repo,
)
from carecover.api.main import create_app
from carecover.config import Settings

SAMPLE = [
    {
        "id": "001",
        "title": "Alpha guideline",
        "scheme": "PMJAY",
        "year": 2023,
        "doc_type": "record",
        "source_url": None,
        "licence": None,
        "published_on": None,
    },
    {
        "id": "002",
        "title": "Beta circular",
        "scheme": "CMCHIS",
        "year": 2024,
        "doc_type": "record",
        "source_url": None,
        "licence": None,
        "published_on": None,
    },
    {
        "id": "003",
        "title": "Gamma notice",
        "scheme": "CMCHIS",
        "year": 2025,
        "doc_type": "record",
        "source_url": None,
        "licence": None,
        "published_on": None,
    },
]


class FakeRepo:
    def __init__(self):
        self.documents = deepcopy(SAMPLE)

    async def list(self, q=None, filters=None, limit=20, offset=0):
        documents = self.documents

        if q:
            documents = [
                doc
                for doc in documents
                if q.lower() in doc["title"].lower() or q.lower() in str(doc).lower()
            ]

        for key, value in (filters or {}).items():
            documents = [doc for doc in documents if str(doc.get(key, "")).lower() == value.lower()]

        total = len(documents)
        items = documents[offset : offset + limit]

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": items,
        }

    async def get(self, external_id):
        for document in self.documents:
            if document["id"] == external_id:
                return document
        return None


class FakeIngestRepo:
    def __init__(self):
        self.known = set()
        self.failed = []
        self.jobs = {}
        self.next_id = 1

    async def known_ids(self):
        return self.known

    async def failed_records(self):
        return self.failed

    async def create(self, records):
        job_id = f"test-job-{self.next_id}"
        self.next_id += 1
        item_ids = list(range(1, len(records) + 1))
        self.jobs[job_id] = {
            "job_id": job_id,
            "total": len(item_ids),
            "queued": len(item_ids),
        }
        return job_id, item_ids

    async def progress(self, job_id):
        return self.jobs.get(job_id)

    async def dead_letter(self, limit=50):
        return []


class FakeQueue:
    def __init__(self):
        self.items = []
        self.fail = False

    async def put(self, item_ids):
        if self.fail:
            from fastapi import HTTPException

            raise HTTPException(status_code=503, detail="Redis unavailable")
        self.items.extend(item_ids)
        return len(item_ids)

    async def close(self):
        pass


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        app_env="ci",
        database_url="postgresql://localhost:5432/carecover",
        admin_token="test-secret",
    )

    app = create_app(settings)

    fake_ingest_repo = FakeIngestRepo()
    fake_queue = FakeQueue()
    sample_pdf = tmp_path / "alpha.pdf"
    sample_pdf.write_bytes(b"CareCover test PDF content")
    fake_manifest = [
        {
            "url": "https://example.com/alpha.pdf",
            "source": "test",
            "title": "Alpha guideline",
            "status": "downloaded",
            "file_path": str(sample_pdf),
        },
    ]

    app.dependency_overrides[get_repo] = FakeRepo
    app.dependency_overrides[check_db] = lambda: True
    app.dependency_overrides[get_ingest_repo] = lambda: fake_ingest_repo
    app.dependency_overrides[get_queue] = lambda: fake_queue
    app.dependency_overrides[get_manifest] = lambda: fake_manifest

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
