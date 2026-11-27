def test_ingest_accepts_and_queues_documents(client):
    response = client.post(
        "/v1/ingest",
        headers={"X-Admin-Token": "test-secret"},
        json={"limit": 20},
    )

    body = response.json()

    assert response.status_code == 202
    assert body["job_id"] is not None
    assert body["queued"] == 1
    assert body["status_url"].startswith("/v1/ingest/")


def test_ingest_requires_admin_token(client):
    missing = client.post("/v1/ingest", json={"limit": 20})
    invalid = client.post(
        "/v1/ingest",
        headers={"X-Admin-Token": "wrong-token"},
        json={"limit": 20},
    )

    assert missing.status_code == 401
    assert invalid.status_code == 401


def test_ingest_refuses_when_admin_token_is_not_configured(client):
    client.app.state.settings.admin_token = ""

    response = client.post(
        "/v1/ingest",
        headers={"X-Admin-Token": "test-secret"},
        json={"limit": 20},
    )

    assert response.status_code == 403


def test_ingest_returns_ok_when_nothing_to_do(client):
    from carecover.api.deps import get_ingest_repo, get_manifest

    client.app.dependency_overrides[get_manifest] = lambda: []

    class EmptyRepo:
        async def known_ids(self):
            return {"already-ingested"}

    client.app.dependency_overrides[get_ingest_repo] = lambda: EmptyRepo()

    response = client.post(
        "/v1/ingest",
        headers={"X-Admin-Token": "test-secret"},
        json={"limit": 20},
    )

    assert response.status_code == 200
    assert response.json()["job_id"] is None
    assert response.json()["queued"] == 0


def test_ingest_validates_limit(client):
    response = client.post(
        "/v1/ingest",
        headers={"X-Admin-Token": "test-secret"},
        json={"limit": 0},
    )

    assert response.status_code == 422


def test_ingest_retries_failed_records(client):
    from carecover.api.deps import get_ingest_repo

    class FailedRepo:
        async def failed_records(self):
            return [
                {
                    "url": "https://example.com/failed.pdf",
                    "source": "test",
                    "title": "Failed document",
                    "status": "downloaded",
                    "file_path": "data/raw/failed.pdf",
                }
            ]

        async def create(self, records):
            assert len(records) == 1
            return "retry-job", [99]

    client.app.dependency_overrides[get_ingest_repo] = lambda: FailedRepo()

    response = client.post(
        "/v1/ingest",
        headers={"X-Admin-Token": "test-secret"},
        json={"retry_failed": True, "limit": 10},
    )

    assert response.status_code == 202
    assert response.json()["job_id"] == "retry-job"
    assert response.json()["queued"] == 1


def test_ingest_progress_is_public_and_unknown_job_is_404(client):
    created = client.post(
        "/v1/ingest",
        headers={"X-Admin-Token": "test-secret"},
        json={"limit": 20},
    )
    assert created.status_code == 202

    job_id = created.json()["job_id"]
    known = client.get(f"/v1/ingest/{job_id}")
    unknown = client.get("/v1/ingest/not-a-real-job")

    assert known.status_code == 200
    assert known.json()["job_id"] == job_id
    assert unknown.status_code == 404


def test_dead_letter_is_public(client):
    response = client.get("/v1/ingest/dead-letter")

    assert response.status_code == 200
    assert response.json()["count"] == 0
    assert response.json()["items"] == []


def test_redis_unavailable_does_not_break_health(client):
    from carecover.api.deps import get_queue

    async def unavailable_queue():
        from fastapi import HTTPException

        raise HTTPException(
            status_code=503,
            detail="The job queue (Redis) cannot be reached.",
        )

    client.app.dependency_overrides[get_queue] = unavailable_queue

    ingest_response = client.post(
        "/v1/ingest",
        headers={"X-Admin-Token": "test-secret"},
        json={"limit": 20},
    )
    health_response = client.get("/health")

    assert ingest_response.status_code == 503
    assert health_response.status_code == 200
