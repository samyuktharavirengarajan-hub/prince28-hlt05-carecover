import pytest

from carecover.api.deps import get_llm_gateway
from carecover.llm.gateway import LLMResult


class FakeGateway:
    async def generate(self, messages, **kwargs):
        return LLMResult(
            text="Please check with the hospital for confirmation.",
            provider="gemini",
            model="gemini-3.8-flash",
            tokens_in=20,
            tokens_out=12,
            latency_ms=100,
            attempts=1,
            fallback_used=False,
            cost_inr=0.001,
        )

    async def stream(self, messages, **kwargs):
        yield "Please check "
        yield "with the hospital "
        yield "for confirmation."
        yield LLMResult(
            text="Please check with the hospital for confirmation.",
            provider="gemini",
            model="gemini-3.8-flash",
            tokens_in=20,
            tokens_out=12,
            latency_ms=100,
            attempts=1,
            fallback_used=False,
            cost_inr=0.001,
        )


@pytest.fixture
def chat_client(client):
    client.app.dependency_overrides[get_llm_gateway] = FakeGateway
    yield client
    client.app.dependency_overrides.pop(get_llm_gateway, None)


def test_chat_returns_json(chat_client):
    response = chat_client.post(
        "/v1/chat?stream=false",
        json={"message": "Is knee replacement covered?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Please check with the hospital for confirmation."
    assert body["provider"] == "gemini"
    assert body["tokens_in"] == 20
    assert body["fallback_used"] is False


def test_chat_streams_server_sent_events(chat_client):
    response = chat_client.post(
        "/v1/chat",
        json={"message": "Is knee replacement covered?"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert '"type": "delta"' in response.text
    assert '"type": "done"' in response.text
    assert "Please check" in response.text


def test_usage_returns_daily_summary(client, monkeypatch):
    from carecover.api.routes import usage as usage_route

    async def fake_by_day(self, days=7):
        return [
            {
                "day": "2026-11-25",
                "calls": 3,
                "errors": 1,
                "fallbacks": 1,
                "tokens_in": 60,
                "tokens_out": 30,
                "cost_inr": 0.01,
            }
        ]

    monkeypatch.setattr(usage_route.UsageRepository, "by_day", fake_by_day)

    response = client.get("/v1/usage?days=7")

    assert response.status_code == 200
    body = response.json()
    assert body["period_days"] == 7
    assert body["totals"]["calls"] == 3
    assert body["totals"]["errors"] == 1
    assert body["totals"]["fallbacks"] == 1
    assert body["totals"]["tokens_in"] == 60
    assert body["totals"]["tokens_out"] == 30
    assert body["totals"]["cost_inr"] == 0.01
