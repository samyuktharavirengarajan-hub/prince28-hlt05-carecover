import asyncio
import hashlib
import json
from datetime import date

from sqlalchemy import select

from carecover.config import get_settings
from carecover.db.models import Document
from carecover.db.session import make_engine, make_sessionmaker

KNOWN = {
    "id",
    "title",
    "source_url",
    "licence",
    "doc_type",
    "published_on",
}


def fingerprint(record: dict) -> str:
    """Create a consistent SHA-256 fingerprint for a record."""
    canonical = json.dumps(
        record,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def to_row(record: dict) -> dict:
    """Convert a JSON record into a database document."""
    external_id = str(record["id"])

    published_on = record.get("published_on")
    if published_on:
        published_on = date.fromisoformat(published_on)

    metadata = {key: value for key, value in record.items() if key not in KNOWN}

    return {
        "external_id": external_id,
        "title": record.get("title") or record.get("scheme") or external_id,
        "source_url": record.get("source_url"),
        "licence": record.get("licence"),
        "doc_type": record.get("doc_type", "record"),
        "published_on": published_on,
        "sha256": fingerprint(record),
        "metadata_": metadata,
    }


async def main() -> None:
    settings = get_settings()
    engine = make_engine(settings)
    sessionmaker = make_sessionmaker(engine)

    inserted = 0
    updated = 0
    unchanged = 0

    try:
        with settings.data_file.open("r", encoding="utf-8") as file:
            records = json.load(file)

        async with sessionmaker() as session, session.begin():
            for record in records:
                row = to_row(record)

                existing = await session.scalar(
                    select(Document).where(Document.external_id == row["external_id"])
                )

                if existing is None:
                    session.add(Document(**row))
                    inserted += 1

                elif existing.sha256 != row["sha256"]:
                    for key, value in row.items():
                        setattr(existing, key, value)
                    updated += 1

                else:
                    unchanged += 1

        print(f"Inserted: {inserted}")
        print(f"Updated: {updated}")
        print(f"Unchanged: {unchanged}")

    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
