"""Postgres is the source of truth for ingestion jobs and their items.

Redis carries job messages. If Redis loses a message or a worker stops,
unfinished items can be found here and queued again.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from carecover.db.models import (
    Document,
    IngestItem,
    IngestJob,
    ParseFailure,
)
from carecover.ingest.store import document_id

OPEN = ("queued", "running")


class IngestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def known_ids(self) -> set[str]:
        """Return document IDs already parsed or recorded as parse failures."""
        known = set(
            await self.session.scalars(
                select(Document.external_id).where(Document.doc_type != "record")
            )
        )
        failed = await self.session.scalars(select(ParseFailure.sha256))
        return known | {document_id(sha) for sha in failed}

    async def create(self, records: list[dict]) -> tuple[str, list[int]]:
        """Create one job and one database item for each manifest record."""
        job = IngestJob(id=uuid.uuid4().hex, requested=len(records))
        job.items = [IngestItem(record=record) for record in records]
        self.session.add(job)
        await self.session.commit()
        return job.id, [item.id for item in job.items]

    async def progress(self, job_id: str) -> dict | None:
        """Summarise item statuses and page counts for one job."""
        job = await self.session.get(IngestJob, job_id)
        if job is None:
            return None

        rows = await self.session.execute(
            select(
                IngestItem.status,
                func.count(),
                func.sum(IngestItem.pages),
            )
            .where(IngestItem.job_id == job_id)
            .group_by(IngestItem.status)
        )

        counts = {
            "queued": 0,
            "running": 0,
            "done": 0,
            "skipped": 0,
            "failed": 0,
        }
        pages = 0

        for status, count, page_sum in rows:
            counts[status] = count
            pages += int(page_sum or 0)

        last = await self.session.scalar(
            select(func.max(IngestItem.updated_at)).where(IngestItem.job_id == job_id)
        )

        finished = counts["queued"] + counts["running"] == 0
        end = last if finished and last else datetime.now(UTC)

        return {
            "job_id": job.id,
            "status": "finished" if finished else "working",
            "requested": job.requested,
            "counts": counts,
            "pages": pages,
            "seconds": round((end - job.created_at).total_seconds(), 1),
            "created_at": job.created_at.isoformat(),
            "dead_letter": await self.dead_letter(job_id=job_id, limit=20),
        }

    async def dead_letter(self, *, job_id: str | None = None, limit: int = 50) -> list[dict]:
        """List permanently failed items for inspection."""
        stmt = select(IngestItem).where(IngestItem.status == "failed")
        if job_id:
            stmt = stmt.where(IngestItem.job_id == job_id)

        rows = await self.session.scalars(stmt.order_by(IngestItem.updated_at.desc()).limit(limit))

        return [
            {
                "item": row.id,
                "job_id": row.job_id,
                "url": row.record.get("url", ""),
                "path": row.record.get("path") or row.record.get("file_path", ""),
                "attempts": row.attempts,
                "error": row.error,
            }
            for row in rows
        ]

    async def failed_records(self) -> list[dict]:
        """Return unique manifest records whose ingestion permanently failed."""
        rows = await self.session.scalars(
            select(IngestItem.record)
            .where(IngestItem.status == "failed")
            .order_by(IngestItem.updated_at.desc())
        )
        records = list(rows)
        return list({record["url"]: record for record in records}.values())

    async def open_item_ids(self) -> list[int]:
        """Find unfinished items so a worker can put them back into Redis."""
        stmt = select(IngestItem.id).where(IngestItem.status.in_(OPEN)).order_by(IngestItem.id)
        return list(await self.session.scalars(stmt))
