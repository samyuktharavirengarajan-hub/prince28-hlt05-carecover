from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from carecover.api.deps import check_db, get_repo
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

    async def list(
        self,
        q=None,
        filters=None,
        limit=20,
        offset=0,
    ):
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


@pytest.fixture
def client():
    settings = Settings(
        app_env="ci",
        database_url="postgresql://localhost:5432/carecover",
    )

    app = create_app(settings)

    app.dependency_overrides[get_repo] = FakeRepo
    app.dependency_overrides[check_db] = lambda: True

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
