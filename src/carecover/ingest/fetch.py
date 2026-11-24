"""Source loading and manifest utilities for CareCover."""

import asyncio
import csv
import json
import random
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx
from protego import Protego
from pypdf import PdfReader


def validate_pdf(file_path: Path) -> bool:
    """Check whether a PDF is readable and contains at least one page."""
    try:
        reader = PdfReader(str(file_path))
        return len(reader.pages) > 0
    except Exception:
        return False


class HostRateLimiter:
    """Apply a shared delay between requests to the same host."""

    def __init__(self, delay: float = 1.0):
        self.delay = delay
        self.locks = {}
        self.last_request = {}

    async def wait(self, url: str):
        host = urlparse(url).netloc

        if host not in self.locks:
            self.locks[host] = asyncio.Lock()

        async with self.locks[host]:
            last = self.last_request.get(host)

            if last is not None:
                elapsed = asyncio.get_running_loop().time() - last
                remaining = self.delay - elapsed

                if remaining > 0:
                    await asyncio.sleep(remaining)

            self.last_request[host] = asyncio.get_running_loop().time()


def load_sources(csv_path: Path = Path("data/sources.csv")) -> list[dict]:
    """Read source metadata from the CSV file."""
    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(line for line in file if not line.lstrip().startswith("#"))
        return list(reader)


def load_manifest(
    manifest_path: Path = Path("data/manifest.jsonl"),
) -> dict[str, dict]:
    """Load existing manifest records, indexed by URL."""
    if not manifest_path.exists():
        return {}

    records = {}
    with manifest_path.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                record = json.loads(line)
                records[record["url"]] = record

    return records


def write_manifest(
    source: dict,
    status: str,
    manifest_path: Path = Path("data/manifest.jsonl"),
) -> None:
    """Create or update a source record in the manifest."""
    records = load_manifest(manifest_path)

    file_path = (
        manifest_path.parent
        / "raw"
        / f"{source['source'].lower()}_{source['title'].lower().replace(' ', '_')}.pdf"
    )

    record = {
        "url": source["url"],
        "source": source["source"],
        "title": source["title"],
        "licence": source["licence"],
        "status": status,
        "file_path": str(file_path),
    }

    records[source["url"]] = record
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    with manifest_path.open("w", encoding="utf-8") as file:
        for item in records.values():
            file.write(json.dumps(item) + "\n")


def get_pending_sources(
    sources: list[dict],
    manifest_path: Path = Path("data/manifest.jsonl"),
) -> list[dict]:
    """Return only sources explicitly allowed by robots.txt."""
    manifest = load_manifest(manifest_path)

    return [
        source
        for source in sources
        if manifest.get(source["url"], {}).get("status") == "robots_allowed"
    ]


def check_robots(url: str, retries: int = 3) -> str:
    """Check robots.txt permission, retrying temporary network failures."""
    parsed_url = urlparse(url)
    robots_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"

    for attempt in range(retries):
        try:
            response = httpx.get(
                robots_url,
                timeout=15,
                follow_redirects=True,
            )

            if response.status_code != 200:
                return "robots_unknown"

            parser = Protego.parse(response.text)
            allowed = parser.can_fetch(url, "CareCoverBot")

            return "robots_allowed" if allowed else "blocked_robots"

        except httpx.HTTPError:
            if attempt < retries - 1:
                time.sleep(1)

    return "robots_unknown"


async def download_source(
    source: dict,
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    limiter: HostRateLimiter | None = None,
    delay: float = 1.0,
    retries: int = 3,
) -> str:
    """Download or resume a PDF only when robots permission is granted."""
    manifest = load_manifest()
    record = manifest.get(source["url"], {})

    if record.get("status") != "robots_allowed":
        return "skipped_robots"

    file_path = Path(record["file_path"])
    file_path.parent.mkdir(parents=True, exist_ok=True)

    if file_path.exists():
        write_manifest(source, "downloaded")
        return "downloaded"

    temporary_path = file_path.with_suffix(".pdf.part")

    async with semaphore:
        for attempt in range(retries):
            try:
                offset = temporary_path.stat().st_size if temporary_path.exists() else 0

                headers = {"User-Agent": "CareCoverBot"}

                if offset > 0:
                    headers["Range"] = f"bytes={offset}-"

                if limiter is not None:
                    await limiter.wait(source["url"])

                response = await client.get(
                    source["url"],
                    timeout=30,
                    follow_redirects=True,
                    headers=headers,
                )
                response.raise_for_status()

                if offset > 0 and response.status_code == 206:
                    content_range = response.headers.get("Content-Range", "")

                    if not content_range.startswith(f"bytes {offset}-"):
                        raise httpx.HTTPError("Server returned an incorrect byte range")

                    write_mode = "ab"
                else:
                    write_mode = "wb"

                with temporary_path.open(write_mode) as file:
                    file.write(response.content)

                if not validate_pdf(temporary_path):
                    temporary_path.unlink(missing_ok=True)
                    write_manifest(source, "invalid_file")
                    return "invalid_file"

                temporary_path.replace(file_path)
                write_manifest(source, "downloaded")
                return "downloaded"

            except (httpx.HTTPError, OSError):
                if attempt == retries - 1:
                    write_manifest(source, "failed")
                    return "failed"

                await asyncio.sleep(2**attempt + random.uniform(0, 1))

    return "failed"


async def download_all_sources(sources: list[dict]) -> list[str]:
    """Download eligible sources with at most four concurrent requests."""
    semaphore = asyncio.Semaphore(4)
    limiter = HostRateLimiter(delay=1.0)

    async with httpx.AsyncClient() as client:
        tasks = [
            download_source(
                source,
                client,
                semaphore,
                delay=1.0,
                retries=3,
                limiter=limiter,
            )
            for source in sources
        ]

        return await asyncio.gather(*tasks)
