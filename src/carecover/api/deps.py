import asyncio
import json
import logging
import secrets
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from carecover.config import Settings
from carecover.db.ingest_jobs import IngestRepository
from carecover.db.llm_calls import UsageRepository
from carecover.db.repository import DocumentRepository
from carecover.llm.gateway import LLMGateway
from carecover.workers.queue import Queue

logger = logging.getLogger("carecover")


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.sessionmaker() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_repo(session: SessionDep) -> DocumentRepository:
    return DocumentRepository(session)


async def check_db(session: SessionDep) -> bool:
    try:
        await asyncio.wait_for(
            session.execute(text("SELECT 1")),
            timeout=2,
        )
        return True
    except (SQLAlchemyError, TimeoutError) as exc:
        logger.warning("Database readiness check failed: %s", exc)
        return False


def get_gateway(request: Request) -> LLMGateway:
    state = request.app.state
    if hasattr(state, "gateway"):
        return state.gateway
    return state.llm_gateway


def get_llm_gateway(request: Request) -> LLMGateway:
    return get_gateway(request)


async def get_usage_repo(session: SessionDep) -> UsageRepository:
    return UsageRepository(session)


async def get_ingest_repo(session: SessionDep) -> IngestRepository:
    return IngestRepository(session)


async def get_queue(request: Request) -> Queue:
    state = request.app.state

    if getattr(state, "queue", None) is None:
        try:
            state.queue = await Queue.connect(state.settings.redis_url)
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail="The job queue (Redis) cannot be reached.",
            ) from exc

    return state.queue


def get_manifest(request: Request) -> list[dict]:
    path = request.app.state.settings.manifest_file

    if not path.is_file():
        return []

    latest: dict[str, dict] = {}

    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue

        url = record.get("url")
        if url:
            latest[url] = record

    return list(latest.values())


def require_admin(
    request: Request,
    x_admin_token: Annotated[str, Header()] = "",
) -> None:
    settings: Settings = request.app.state.settings

    if not settings.admin_token:
        if settings.app_env == "local":
            return

        raise HTTPException(
            status_code=403,
            detail="Set ADMIN_TOKEN to allow ingestion here.",
        )

    if not secrets.compare_digest(x_admin_token, settings.admin_token):
        raise HTTPException(
            status_code=401,
            detail="Missing or wrong X-Admin-Token header.",
        )


SettingsDep = Annotated[Settings, Depends(get_app_settings)]
RepoDep = Annotated[DocumentRepository, Depends(get_repo)]
DbCheckDep = Annotated[bool, Depends(check_db)]
LLMGatewayDep = Annotated[LLMGateway, Depends(get_llm_gateway)]

IngestRepoDep = Annotated[IngestRepository, Depends(get_ingest_repo)]
QueueDep = Annotated[Queue, Depends(get_queue)]
ManifestDep = Annotated[list[dict], Depends(get_manifest)]
GatewayDep = Annotated[LLMGateway, Depends(get_gateway)]
UsageDep = Annotated[UsageRepository, Depends(get_usage_repo)]
