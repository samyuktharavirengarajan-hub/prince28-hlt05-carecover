"""Check Gemini and Groq API connectivity using httpx."""

import json

import httpx

from carecover.config import get_settings


def ping_provider(name: str, base_url: str, api_key: str, model: str) -> bool:
    """Send a small chat-completion request and report the result."""

    if not api_key:
        print(f"{name}: API key is missing")
        return False

    url = f"{base_url.rstrip('/')}/chat/completions"

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
        "max_tokens": 10,
        "stream": False,
    }

    try:
        with httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
            response = client.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

        response.raise_for_status()
        result = response.json()
        answer = result["choices"][0]["message"]["content"]

        print(f"{name}: SUCCESS (HTTP {response.status_code})")
        print(f"Response: {answer}")
        return True

    except httpx.HTTPStatusError as error:
        print(f"{name}: FAILED (HTTP {error.response.status_code})")
        print(error.response.text[:500])
    except httpx.TransportError as error:
        print(f"{name}: CONNECTION FAILED - {error}")
    except (KeyError, IndexError, json.JSONDecodeError) as error:
        print(f"{name}: INVALID RESPONSE - {error}")

    return False


def main() -> None:
    settings = get_settings()

    gemini_ok = ping_provider(
        "Gemini",
        settings.llm_primary_base_url,
        settings.gemini_api_key,
        settings.llm_primary_model,
    )

    groq_ok = ping_provider(
        "Groq",
        settings.llm_fallback_base_url,
        settings.groq_api_key,
        settings.llm_fallback_model,
    )

    if not (gemini_ok and groq_ok):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
