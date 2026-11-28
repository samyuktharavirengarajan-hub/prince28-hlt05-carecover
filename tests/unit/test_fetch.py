import asyncio
from unittest.mock import Mock, patch

from carecover.ingest.fetch import check_robots, download_source


def test_robots_blocks_disallowed_url():
    response = Mock()
    response.status_code = 200
    response.headers = {"Content-Type": "text/plain"}
    response.text = "User-agent: *\nDisallow: /"

    with patch("carecover.ingest.fetch.httpx.get", return_value=response):
        result = check_robots("https://example.com/test.pdf")

    assert result == "blocked_robots"


def test_robots_allows_permitted_url():
    response = Mock()
    response.status_code = 200
    response.headers = {"Content-Type": "text/plain"}
    response.text = "User-agent: *\nAllow: /"

    with patch("carecover.ingest.fetch.httpx.get", return_value=response):
        result = check_robots("https://example.com/test.pdf")

    assert result == "robots_allowed"


def test_robots_unknown_on_network_error():
    import httpx

    with patch(
        "carecover.ingest.fetch.httpx.get",
        side_effect=httpx.TimeoutException("Timed out"),
    ):
        result = check_robots("https://example.com/test.pdf")

    assert result == "robots_unknown"


def test_download_skips_source_without_robots_permission():
    source = {
        "url": "https://example.com/test.pdf",
        "source": "Example",
        "title": "Test PDF",
        "licence": "Test licence",
    }

    client = Mock()
    semaphore = asyncio.Semaphore(4)

    with patch(
        "carecover.ingest.fetch.load_manifest",
        return_value={source["url"]: {"status": "robots_unknown"}},
    ):
        result = asyncio.run(download_source(source, client, semaphore))

    assert result == "skipped_robots"
    client.get.assert_not_called()


def test_same_host_uses_shared_delay():
    from carecover.ingest.fetch import HostRateLimiter

    async def run_test():
        limiter = HostRateLimiter(delay=1.0)

        with patch("carecover.ingest.fetch.asyncio.sleep") as mock_sleep:
            await limiter.wait("https://example.com/a.pdf")
            await limiter.wait("https://example.com/b.pdf")

        return mock_sleep.call_count

    assert asyncio.run(run_test()) == 1


def test_download_uses_range_header_for_partial_file(tmp_path):
    import asyncio
    from io import BytesIO
    from unittest.mock import AsyncMock, Mock, patch

    from pypdf import PdfWriter

    from carecover.ingest.fetch import download_source

    source = {
        "url": "https://example.com/test.pdf",
        "source": "Example",
        "title": "Test PDF",
        "licence": "Test licence",
    }

    # Generate a genuine PDF for testing.
    buffer = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.write(buffer)
    pdf_bytes = buffer.getvalue()

    file_path = tmp_path / "test.pdf"
    partial_path = file_path.with_suffix(".pdf.part")

    # Simulate an interrupted download.
    offset = 100
    partial_path.write_bytes(pdf_bytes[:offset])

    async def run_test():
        client = Mock()
        client.get = AsyncMock()

        response = Mock()
        response.status_code = 206
        response.content = pdf_bytes[offset:]
        response.headers = {
            "Content-Range": (f"bytes {offset}-{len(pdf_bytes) - 1}/{len(pdf_bytes)}")
        }
        response.raise_for_status = Mock()

        client.get.return_value = response

        with (
            patch(
                "carecover.ingest.fetch.load_manifest",
                return_value={
                    source["url"]: {
                        "status": "robots_allowed",
                        "file_path": str(file_path),
                    }
                },
            ),
            patch("carecover.ingest.fetch.write_manifest"),
        ):
            await download_source(
                source,
                client,
                asyncio.Semaphore(4),
                retries=1,
            )

        return client.get.call_args.kwargs["headers"]

    headers = asyncio.run(run_test())

    assert headers["Range"] == "bytes=100-"
    assert file_path.read_bytes() == pdf_bytes
    assert not partial_path.exists()


def test_robots_retries_after_temporary_network_errors():
    import httpx

    response = Mock()
    response.status_code = 200
    response.headers = {"Content-Type": "text/plain"}
    response.text = "User-agent: *\nAllow: /"

    with (
        patch(
            "carecover.ingest.fetch.httpx.get",
            side_effect=[
                httpx.TimeoutException("Timed out"),
                httpx.TimeoutException("Timed out"),
                response,
            ],
        ) as mock_get,
        patch("carecover.ingest.fetch.time.sleep"),
    ):
        result = check_robots("https://example.com/test.pdf")

    assert result == "robots_allowed"
    assert mock_get.call_count == 3


def test_robots_allows_when_file_not_found():
    response = Mock()
    response.status_code = 404

    with patch("carecover.ingest.fetch.httpx.get", return_value=response):
        result = check_robots("https://example.com/test.pdf")

    assert result == "robots_allowed"


def test_robots_blocks_when_server_error():
    response = Mock()
    response.status_code = 500

    with patch("carecover.ingest.fetch.httpx.get", return_value=response):
        result = check_robots("https://example.com/test.pdf")

    assert result == "blocked_robots"


def test_robots_blocks_when_access_is_denied():
    for status_code in (401, 403):
        response = Mock()
        response.status_code = status_code

        with patch("carecover.ingest.fetch.httpx.get", return_value=response):
            result = check_robots("https://example.com/test.pdf")

        assert result == "blocked_robots"


def test_robots_returns_unknown_when_rate_limited():
    response = Mock()
    response.status_code = 429

    with patch("carecover.ingest.fetch.httpx.get", return_value=response):
        result = check_robots("https://example.com/test.pdf")

    assert result == "robots_unknown"


def test_robots_returns_unknown_for_other_client_errors():
    response = Mock()
    response.status_code = 400

    with patch("carecover.ingest.fetch.httpx.get", return_value=response):
        result = check_robots("https://example.com/test.pdf")

    assert result == "robots_unknown"
