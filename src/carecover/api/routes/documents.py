from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request

from carecover.api.deps import RepoDep
from carecover.db.repository import FILTER_KEY

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("")
async def list_documents(
    request: Request,
    repo: RepoDep,
    q: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    filters = {}

    for key, value in request.query_params.items():
        if key in {"q", "limit", "offset"}:
            continue

        if not FILTER_KEY.fullmatch(key):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid filter name: {key}",
            )

        filters[key] = value

    return await repo.list(
        q=q,
        filters=filters,
        limit=limit,
        offset=offset,
    )


@router.get("/{doc_id}")
async def get_document(doc_id: str, repo: RepoDep) -> dict:
    document = await repo.get(doc_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail=f"No document with id '{doc_id}'.",
        )

    return document
