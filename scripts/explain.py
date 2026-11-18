import asyncio
import json
import sys

from sqlalchemy import text

from carecover.config import get_settings
from carecover.db.session import make_engine

SQL = """
EXPLAIN ANALYZE
SELECT id, title
FROM documents
WHERE metadata @> CAST(:filter AS jsonb)
"""


async def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: uv run python scripts/explain.py FIELD VALUE")
        raise SystemExit(1)

    field, value = sys.argv[1], sys.argv[2]
    filter_json = json.dumps({field: value})

    engine = make_engine(get_settings())

    try:
        async with engine.connect() as connection:
            print("\n--- Default query plan ---")
            result = await connection.execute(
                text(SQL),
                {"filter": filter_json},
            )
            for row in result:
                print(row[0])

            print("\n--- Query plan with sequential scans disabled ---")
            await connection.execute(text("SET enable_seqscan = off"))
            result = await connection.execute(
                text(SQL),
                {"filter": filter_json},
            )
            for row in result:
                print(row[0])
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
