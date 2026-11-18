"""App factory: build a fully wired FastAPI app from settings."""

import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from carecover.api.errors import register_error_handlers
from carecover.api.middleware import request_context
from carecover.api.routes import documents, health
from carecover.config import Settings, get_settings
from carecover.db.session import make_engine, make_sessionmaker
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
        yield
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

    app.middleware("http")(request_context)
    register_error_handlers(app)

    v1 = APIRouter(prefix="/v1")
    v1.include_router(documents.router)

    app.include_router(health.router)
    app.include_router(v1)

    return app
