"""App factory: build a fully wired FastAPI app from settings."""

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import APIRouter, FastAPI

from carecover.api.errors import register_error_handlers
from carecover.api.middleware import request_context
from carecover.api.routes import chat, documents, health, ingest, usage
from carecover.config import Settings, get_settings
from carecover.db.llm_calls import make_recorder
from carecover.db.session import make_engine, make_sessionmaker
from carecover.llm.gateway import build_gateway
from carecover.logging_setup import setup_logging

logger = logging.getLogger("carecover")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    setup_logging(settings.log_level)

    engine = make_engine(settings)
    sessionmaker = make_sessionmaker(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("CareCover application started")
        worker = None

        if settings.worker_in_api:
            from carecover.workers.main import run_embedded

            worker = asyncio.create_task(run_embedded(settings))
            logger.info("Embedded ingestion worker started")

        try:
            yield
        finally:
            if worker is not None:
                worker.cancel()
                with suppress(asyncio.CancelledError):
                    await worker

            queue = getattr(app.state, "queue", None)
            if queue is not None:
                await queue.close()

            await engine.dispose()
            logger.info("Database connections closed")

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )

    app.state.settings = settings
    app.state.engine = engine
    app.state.sessionmaker = sessionmaker

    gateway = build_gateway(
        settings,
        recorder=make_recorder(sessionmaker),
    )
    app.state.gateway = gateway
    app.state.llm_gateway = gateway

    app.middleware("http")(request_context)
    register_error_handlers(app)

    v1 = APIRouter(prefix="/v1")
    v1.include_router(documents.router)
    v1.include_router(chat.router)
    v1.include_router(usage.router)
    v1.include_router(ingest.router)

    app.include_router(health.router)
    app.include_router(v1)

    return app
