import re
from contextlib import suppress
from typing import Any

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from carecover.db.models import Document

FILTER_KEY = re.compile(r"^[a-z_][a-z0-9_]{0,40}$")


def to_dict(document: Document) -> dict[str, Any]:
    metadata = document.metadata_ or {}

    return {
        "id": document.external_id,
        **metadata,
        "title": document.title,
        "doc_type": document.doc_type,
        "source_url": document.source_url,
        "licence": document.licence,
        "published_on": (document.published_on.isoformat() if document.published_on else None),
    }


def _value_candidates(value: str) -> list[Any]:
    candidates: list[Any] = [value, [value]]

    lowered = value.lower()
    if lowered in {"true", "false"}:
        candidates.append(lowered == "true")

    with suppress(ValueError):
        candidates.append(int(value))

    try:
        number = float(value)
        if number not in candidates:
            candidates.append(number)
    except ValueError:
        pass

    return candidates


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(
        self,
        q: str | None = None,
        filters: dict[str, str] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        statement = select(Document)

        if q:
            pattern = f"%{q}%"
            statement = statement.where(
                or_(
                    Document.title.ilike(pattern),
                    cast(Document.metadata_, String).ilike(pattern),
                )
            )

        for key, value in (filters or {}).items():
            if not FILTER_KEY.fullmatch(key):
                raise ValueError(f"Invalid filter key: {key}")

            statement = statement.where(
                or_(
                    *[
                        Document.metadata_.contains({key: candidate})
                        for candidate in _value_candidates(value)
                    ]
                )
            )

        count_statement = select(func.count()).select_from(statement.order_by(None).subquery())
        total = await self.session.scalar(count_statement)

        rows_statement = statement.order_by(Document.external_id).limit(limit).offset(offset)
        result = await self.session.scalars(rows_statement)

        return {
            "total": total or 0,
            "limit": limit,
            "offset": offset,
            "items": [to_dict(document) for document in result.all()],
        }

    async def get(self, external_id: str) -> dict[str, Any] | None:
        statement = select(Document).where(Document.external_id == external_id)
        document = await self.session.scalar(statement)

        if document is None:
            return None

        return to_dict(document)
