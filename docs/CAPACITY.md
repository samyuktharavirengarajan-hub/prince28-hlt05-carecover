# CareCover Fetcher Capacity Report

## 1. Concurrency

- Maximum concurrent downloads: 4
- Implementation: Python `asyncio.Semaphore`
- Downloads are coordinated using asynchronous tasks.
- This limits the number of simultaneous downloads and prevents excessive resource usage.

## 2. Request Rate Limiting

- Per-host delay: 1 second
- Implementation: Shared `HostRateLimiter`
- Requests to the same host are spaced to avoid excessive traffic.
- This helps respect website server resources.

## 3. Retry Strategy

- Maximum attempts: 3
- Backoff strategy: Exponential backoff
- Formula: `2^attempt + random jitter`
- Jitter range: 0 to 1 second.
- Failed requests are retried with increasing delays.

## 4. Resume Capability

- Partial downloads are stored using the `.pdf.part` extension.
- HTTP Range headers are used to request remaining bytes.
- `Content-Range` is checked before appending resumed content.
- This helps avoid downloading the entire file again after an interruption.

## 5. PDF Validation

- Downloaded files are validated using `pypdf`.
- A PDF must be readable and contain at least one page.
- Invalid files are not marked as downloaded.

## 6. Current Dataset Status

Verified from `data/manifest.jsonl`, `data/manual_manifest.jsonl`, and the PostgreSQL database.

- PDF manifest records: 22
- Successfully downloaded PDF files: 7
- Manually collected Excel files: 3
- Total unique files collected: 10
- Total file size: 22,771,211 bytes (approximately 21.72 MiB)
- Document records stored in PostgreSQL: 30
- Parsed pages stored in PostgreSQL: 1,044
- Remaining parsing failures: 0

The PDF manifest contains other sources that are blocked, unavailable, invalid, or not yet verified. They are not counted as downloaded documents.

## 7. Test Evidence

Unit test results:

- Total unit tests: 82
- Passed: 82
- Failed: 0
- Warnings: 1 (optional PySocks dependency warning; tests passed)

Command:

```powershell
uv run pytest tests/unit/ -v
```

Latest verification: 2026-11-26 — 82 passed, 0 failed, 1 non-blocking dependency warning.

## 8. Limitations

- Actual download throughput has not been benchmarked.
- The measured file size represents the current collected corpus, not maximum system capacity.
- The current corpus contains 10 unique files; it is not a complete collection of all PM-JAY and CMCHIS documents.
- Some source URLs remain blocked, unavailable, invalid, or unverified.
- Parser comparison is documented separately in `NOTES.md`.

The configured concurrency and rate limits describe implementation settings, not measured production capacity.
