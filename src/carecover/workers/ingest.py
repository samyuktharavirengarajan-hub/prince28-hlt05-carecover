"""One ARQ job processes one manifest document.

Postgres stores durable item state. Redis only carries the item ID.
A worker may restart or retry without creating duplicate documents.
"""

import asyncio
import hashlib
import logging
import time
from pathlib import Path

from arq import Retry
from sqlalchemy import select

from carecover.db.models import Document, IngestItem
from carecover.ingest.parse import ParseError, parse_file
from carecover.ingest.store import document_id, save_document, save_failure
from carecover.llm.extract import document_text, extract, save

logger = logging.getLogger("carecover.worker")


def manifest_path(raw_path: str | Path) -> Path:
    """Normalize Windows manifest paths for Linux containers."""
    return Path(str(raw_path).replace(chr(92), "/"))


class Permanent(Exception):
    """An error that another attempt cannot fix."""


class Pace:
    """Keep LLM calls within the configured requests-per-minute limit."""

    def __init__(self, per_minute: float) -> None:
        if per_minute <= 0:
            raise ValueError("ingest_rpm must be greater than zero")
        self._gap = 60.0 / per_minute
        self._next = 0.0
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        async with self._lock:
            now = time.monotonic()
            delay = max(0.0, self._next - now)
            self._next = max(now, self._next) + self._gap

        if delay:
            await asyncio.sleep(delay)


def sha256_of(path: Path) -> str:
    """Calculate a file's SHA-256 hash without loading it all into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def plan(
    records: list[dict],
    done_ids: set[str],
    *,
    source: str = "",
    limit: int = 0,
) -> list[dict]:
    """Select downloaded, existing, not-yet-ingested manifest records."""
    todo = []
    seen = set(done_ids)

    for record in records:
        if record.get("status") != "downloaded":
            continue
        if source and record.get("source") != source:
            continue

        raw_path = record.get("file_path") or record.get("path")
        if not raw_path:
            continue

        path = manifest_path(raw_path)
        if not path.is_file():
            continue

        doc_id = document_id(sha256_of(path))
        if doc_id in seen:
            continue

        seen.add(doc_id)
        todo.append(record)

    return todo[:limit] if limit else todo


async def process(ctx: dict, session, item: IngestItem) -> tuple[str, int]:
    """Parse and store one document, then optionally extract metadata."""
    record = dict(item.record)
    raw_path = record.get("file_path") or record.get("path")

    if not raw_path:
        raise Permanent("manifest record has no file_path")

    path = manifest_path(raw_path)
    record["path"] = str(path)
    if not path.is_file():
        raise Permanent(f"local file is missing: {path}")

    if record.get("status") != "downloaded":
        raise Permanent("manifest record is not marked downloaded")

    digest = await asyncio.to_thread(sha256_of, path)
    record["sha256"] = digest
    doc_id = document_id(digest)

    document = await session.scalar(select(Document).where(Document.external_id == doc_id))

    status = "skipped"

    if document is None:
        try:
            parsed = await asyncio.to_thread(parse_file, path)
        except ParseError as error:
            await save_failure(session, record, error)
            raise Permanent(f"parse: {error.reason}") from error

        await save_document(session, record, parsed)
        document = await session.scalar(select(Document).where(Document.external_id == doc_id))

        if document is None:
            raise RuntimeError("document was not found after saving")
        status = "done"

    pages = int(document.metadata_.get("pages", 0))

    task = ctx.get("extract")
    note = document.metadata_.get("extract") or {}

    if task and (note.get("prompt") != task["version"] or "error" in note):
        await ctx["pace"].wait()

        text = await document_text(session, document, task["chars"])
        result = await extract(
            ctx["gateway"],
            task["schema"],
            task["prompt"],
            task["version"],
            document.title,
            text,
        )

        await save(session, document, result, task["version"])

        if result.record is None:
            reason = result.errors[-1] if result.errors else "no valid extraction"
            raise Permanent(f"extract: {reason[:200]}")

        status = "done"

    return status, pages


async def ingest_document(ctx: dict, item_id: int) -> str:
    """ARQ entry point: persist attempts and retry temporary errors."""
    max_tries = ctx["settings"].ingest_max_tries

    async with ctx["sessionmaker"]() as session:
        item = await session.get(IngestItem, item_id)

        if item is None or item.status not in ("queued", "running"):
            return "ignored"

        if item.attempts >= max_tries:
            item.status = "failed"
            item.error = f"gave up: started {item.attempts} times and never finished"
            await session.commit()
            return "failed"

        item.status = "running"
        item.attempts += 1
        attempt = item.attempts
        await session.commit()

        try:
            item.status, item.pages = await process(ctx, session, item)
            item.error = ""

        except Permanent as error:
            await session.rollback()
            item = await session.get(IngestItem, item_id)
            item.status = "failed"
            item.error = str(error)[:500]

        except Exception as error:
            await session.rollback()
            item = await session.get(IngestItem, item_id)

            reason = f"{type(error).__name__}: {error}"[:500]

            if attempt >= max_tries:
                item.status = "failed"
                item.error = f"gave up after {attempt} tries: {reason}"
            else:
                item.status = "queued"
                item.error = f"try {attempt} failed: {reason}"
                await session.commit()

                logger.warning("item %s will be retried: %s", item_id, reason)
                raise Retry(defer=attempt * 30) from error

        await session.commit()
        logger.info("item %s %s", item_id, item.status)
        return item.status
