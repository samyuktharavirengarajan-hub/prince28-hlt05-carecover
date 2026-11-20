import asyncio

from sqlalchemy import text

from carecover.config import get_settings
from carecover.db.session import make_engine


async def main() -> None:
    settings = get_settings()
    engine = make_engine(settings)

    try:
        async with engine.connect() as connection:
            result = await connection.execute(
                text("SELECT current_database(), current_setting('server_version')")
            )

            database_name, server_version = result.one()

            print(f"Connected to database: {database_name}")
            print(f"PostgreSQL version: {server_version}")

    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
