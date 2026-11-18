from pydantic import ValidationError

from carecover.config import Settings


def test_health_is_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_when_database_is_available(client):
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["checks"]["database"] is True


def test_list_documents_paginates(client):
    response = client.get("/v1/documents", params={"limit": 2})
    body = response.json()

    assert response.status_code == 200
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["limit"] == 2


def test_search_filters_records(client):
    response = client.get("/v1/documents", params={"q": "beta"})

    assert response.status_code == 200
    assert [doc["id"] for doc in response.json()["items"]] == ["002"]


def test_metadata_filter(client):
    response = client.get(
        "/v1/documents",
        params={"scheme": "CMCHIS"},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert all(doc["scheme"] == "CMCHIS" for doc in response.json()["items"])


def test_invalid_filter_name_returns_400(client):
    response = client.get(
        "/v1/documents",
        params={"Bad-Name": "1"},
    )

    assert response.status_code == 400
    assert "Invalid filter name" in response.json()["detail"]


def test_get_document_found(client):
    response = client.get("/v1/documents/001")

    assert response.status_code == 200
    assert response.json()["title"] == "Alpha guideline"


def test_missing_document_is_problem_details(client):
    response = client.get("/v1/documents/999")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"

    body = response.json()

    assert body["status"] == 404
    assert body["title"] == "Not Found"
    assert body["request_id"] == response.headers["X-Request-ID"]


def test_bad_limit_is_422_problem(client):
    response = client.get("/v1/documents", params={"limit": 0})

    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "query.limit"


def test_request_id_is_echoed(client):
    response = client.get(
        "/health",
        headers={"X-Request-ID": "abc123"},
    )

    assert response.headers["X-Request-ID"] == "abc123"


def test_app_refuses_to_start_without_app_env(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)

    try:
        Settings(_env_file=None)
    except ValidationError:
        pass
    else:
        raise AssertionError("Settings should require APP_ENV")
