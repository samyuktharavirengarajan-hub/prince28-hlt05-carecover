"""ARQ worker entry point.

Start separately with:
    uv run arq carecover.workers.main.WorkerSettings

The API and worker share PostgreSQL and Redis.
"""

import asyncio
import logging

from arq.worker import Worker

from carecover.config import Settings, get_settings
from carecover.db.ingest_jobs import IngestRepository
from carecover.db.llm_calls import make_recorder
from carecover.db.session import make_engine, make_sessionmaker
from carecover.llm.doc_meta import DocMeta
from carecover.llm.gateway import build_gateway
from carecover.llm.prompts import latest, read_prompt
from carecover.logging_setup import setup_logging
from carecover.workers.ingest import Pace, ingest_document
from carecover.workers.queue import Queue, redis_settings

logger = logging.getLogger("carecover.worker")


async def startup(ctx: dict) -> None:
    """Initialize database, LLM gateway and extraction configuration."""
    settings: Settings = ctx["settings"]

    if not ctx.get("embedded"):
        setup_logging(settings.log_level)
        logging.getLogger("arq").handlers.clear()

    engine = make_engine(settings)
    ctx["engine"] = engine
    ctx["sessionmaker"] = make_sessionmaker(engine)

    ctx["gateway"] = build_gateway(
        settings,
        make_recorder(ctx["sessionmaker"]),
    )
    ctx["pace"] = Pace(settings.ingest_rpm)

    ctx["extract"] = None

    try:
        version = latest(settings.prompts_dir, "extract")
        prompt = read_prompt(settings.prompts_dir, version)

        ctx["extract"] = {
            "schema": DocMeta,
            "prompt": prompt,
            "version": version,
            "chars": 6000,
        }
    except FileNotFoundError:
        logger.warning("No extraction prompt found; documents will only be parsed")

    # Restore unfinished items from PostgreSQL into Redis.
    async with ctx["sessionmaker"]() as session:
        item_ids = await IngestRepository(session).open_item_ids()

    added = await Queue(ctx["redis"]).put(item_ids)

    logger.info(
        "Worker ready; %s unfinished item(s) found, %s queued",
        len(item_ids),
        added,
    )


async def shutdown(ctx: dict) -> None:
    """Release database resources when the worker stops."""
    engine = ctx.get("engine")
    if engine is not None:
        await engine.dispose()


def worker_options(
    settings: Settings,
    *,
    embedded: bool = False,
) -> dict:
    """Build ARQ configuration for standalone or embedded execution."""
    return {
        "functions": [ingest_document],
        "on_startup": startup,
        "on_shutdown": shutdown,
        "redis_settings": redis_settings(settings.redis_url),
        "ctx": {
            "settings": settings,
            "embedded": embedded,
        },
        "max_jobs": settings.ingest_concurrency,
        "job_timeout": settings.ingest_job_timeout,
        "max_tries": settings.ingest_max_tries,
        "keep_result": 0,
        "poll_delay": 1.0,
    }


async def run_embedded(settings: Settings) -> None:
    """Run an ARQ worker inside the API process."""
    worker = Worker(
        **worker_options(settings, embedded=True),
        handle_signals=False,
    )

    try:
        await worker.async_run()
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("The embedded worker stopped. Check REDIS_URL and database access.")
    finally:
        await worker.close()


WorkerSettings = worker_options(get_settings())
