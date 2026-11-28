"""Chat endpoint: stream LLM answers or return a regular JSON response."""

import json

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from carecover.api.deps import LLMGatewayDep, SettingsDep
from carecover.llm.gateway import LLMResult, LLMUnavailable

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


def load_system_prompt(settings) -> str:
    prompt_file = settings.prompts_dir / "chat_system_v1.md"
    return prompt_file.read_text(encoding="utf-8")


def result_details(result: LLMResult) -> dict:
    return {
        "provider": result.provider,
        "model": result.model,
        "tokens_in": result.tokens_in,
        "tokens_out": result.tokens_out,
        "latency_ms": result.latency_ms,
        "attempts": result.attempts,
        "fallback_used": result.fallback_used,
        "cost_inr": result.cost_inr,
    }


@router.post("")
async def chat(
    body: ChatRequest,
    gateway: LLMGatewayDep,
    settings: SettingsDep,
    stream: bool = Query(default=True),
):
    system_prompt = load_system_prompt(settings)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": body.message},
    ]

    if not stream:
        try:
            result = await gateway.generate(
                messages,
                prompt_version="chat_system_v1",
            )
        except LLMUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        return {
            "answer": result.text,
            **result_details(result),
        }

    async def event_stream():
        try:
            async for item in gateway.stream(
                messages,
                prompt_version="chat_system_v1",
            ):
                if isinstance(item, LLMResult):
                    payload = {"type": "done", **result_details(item)}
                else:
                    payload = {"type": "delta", "text": item}

                yield f"data: {json.dumps(payload)}\n\n"

        except LLMUnavailable as exc:
            payload = {"type": "error", "message": str(exc)}
            yield f"event: error\ndata: {json.dumps(payload)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
