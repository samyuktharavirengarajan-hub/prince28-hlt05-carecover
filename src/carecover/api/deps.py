import asyncio
import logging
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from carecover.config import Settings
from carecover.db.repository import DocumentRepository
from carecover.llm.gateway import LLMGateway

logger = logging.getLogger("carecover")


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


async def get_session(request: Request):
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


SettingsDep = Annotated[Settings, Depends(get_app_settings)]
RepoDep = Annotated[DocumentRepository, Depends(get_repo)]
DbCheckDep = Annotated[bool, Depends(check_db)]


def get_llm_gateway(request: Request) -> LLMGateway:
    return request.app.state.llm_gateway


LLMGatewayDep = Annotated[LLMGateway, Depends(get_llm_gateway)]
