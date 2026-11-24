import asyncio

from carecover.ingest.fetch import (
    check_robots,
    download_all_sources,
    get_pending_sources,
    load_sources,
    write_manifest,
)


async def main():
    sources = load_sources()

    print(f"Total sources: {len(sources)}")

    for source in sources:
        status = check_robots(source["url"])
        write_manifest(source, status)
        print(f"{source['title']}: {status}")

    pending = get_pending_sources(sources)

    print(f"Eligible sources: {len(pending)}")

    if not pending:
        print("No sources have confirmed robots permission.")
        return

    results = await download_all_sources(pending)

    for source, result in zip(pending, results, strict=True):
        print(f"{source['title']}: {result}")


if __name__ == "__main__":
    asyncio.run(main())
