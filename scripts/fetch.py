import asyncio

from carecover.ingest.fetch import (
    download_all_sources,
    get_pending_sources,
    load_sources,
)


async def main():
    sources = load_sources()
    pending = get_pending_sources(sources)

    print(f"Total sources: {len(sources)}")
    print(f"Eligible sources: {len(pending)}")

    if not pending:
        print("No sources have confirmed robots permission.")
        return

    results = await download_all_sources(pending)

    for source, result in zip(pending, results, strict=True):
        print(f"{source['title']}: {result}")


if __name__ == "__main__":
    asyncio.run(main())
