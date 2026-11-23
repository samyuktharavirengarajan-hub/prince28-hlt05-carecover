# CareCover Fetcher Capacity Report

## 1. Concurrency

- Maximum concurrent downloads: 4
- Implementation: Python asyncio Semaphore
- Downloads are coordinated using asynchronous tasks.

## 2. Request Rate Limiting

- Per-host delay: 1 second
- Implementation: Shared HostRateLimiter
- Requests to the same host are spaced to avoid excessive traffic.

## 3. Retry Strategy

- Maximum attempts: 3
- Backoff strategy: Exponential backoff
- Formula: 2^attempt + random jitter
- Jitter range: 0 to 1 second

## 4. Resume Capability

- Partial downloads are stored using the `.pdf.part` extension.
- HTTP Range headers are used to request remaining bytes.
- Content-Range is checked before appending resumed content.

## 5. PDF Validation

- Downloaded files are validated using pypdf.
- A PDF must be readable and contain at least one page.
- Invalid files are not marked as downloaded.

## 6. Current Dataset Status

- Sources identified: 2
- Sources eligible for download: 0
- Downloads completed: 0

Downloads were not attempted because robots.txt permission was either unknown or explicitly denied.

## 7. Test Evidence

Unit test results:

- Total unit tests: 19
- Passed: 19
- Failed: 0

Command:

`uv run pytest tests/unit/ -v`

## 8. Limitations

Actual download throughput, file sizes, and processing times have not been benchmarked because no source was eligible for download.

The configured concurrency and rate limits describe implementation settings, not measured production capacity.
