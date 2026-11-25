"""Usage endpoint: daily LLM calls, tokens, errors, fallbacks and cost."""

from fastapi import APIRouter, Query

from carecover.api.deps import SessionDep
from carecover.db.llm_calls import UsageRepository

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("")
async def usage(
    session: SessionDep,
    days: int = Query(default=7, ge=1, le=90),
) -> dict:
    daily = await UsageRepository(session).by_day(days=days)

    return {
        "period_days": days,
        "daily": daily,
        "totals": {
            "calls": sum(row["calls"] for row in daily),
            "errors": sum(row["errors"] for row in daily),
            "fallbacks": sum(row["fallbacks"] for row in daily),
            "tokens_in": sum(row["tokens_in"] for row in daily),
            "tokens_out": sum(row["tokens_out"] for row in daily),
            "cost_inr": round(sum(row["cost_inr"] for row in daily), 4),
        },
    }
