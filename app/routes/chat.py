"""Chat API — streams Vercel AI SDK UI messages for Next.js useChat."""

from __future__ import annotations

import sys
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

import ai
from fastapi import APIRouter, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.agent.voca_agent import MODEL, agent_for_session, system_prompt_for_session
from app.session_context import bind_voca_session, reset_voca_session

if TYPE_CHECKING:
    pass

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    """Matches Next.js AI SDK DefaultChatTransport payload."""

    model_config = {"extra": "ignore"}

    messages: list[ai.agents.ui.ai_sdk.UIMessage]
    session_id: str | None = Field(default=None, description="Voca session for interview state")
    id: str | None = Field(default=None, description="Chat id from AI SDK (fallback session key)")


def _resolve_session_id(request: ChatRequest) -> str | None:
    return request.session_id or request.id


@router.post("/chat")
async def chat(request: ChatRequest) -> StreamingResponse:
    session_id = _resolve_session_id(request)
    messages, approvals = ai.agents.ui.ai_sdk.to_messages(request.messages)
    ai.agents.ui.ai_sdk.apply_approvals(approvals)

    full_messages = [ai.system_message(system_prompt_for_session(session_id)), *messages]
    agent = agent_for_session(session_id)
    session_token = bind_voca_session(session_id)

    async def stream_response() -> AsyncGenerator[str]:
        try:
            async with agent.run(MODEL, full_messages) as result:

                async def process() -> AsyncGenerator[ai.events.AgentEvent]:
                    async for event in result:
                        if isinstance(event, ai.events.HookEvent) and event.hook.status == "pending":
                            ai.abort_pending_hook(event.hook)
                        yield event

                async for chunk in ai.agents.ui.ai_sdk.to_sse(process()):
                    yield chunk
        finally:
            reset_voca_session(session_token)

    return StreamingResponse(
        stream_response(),
        headers=ai.agents.ui.ai_sdk.UI_MESSAGE_STREAM_HEADERS,
    )


def register_validation_logger(app) -> None:
    @app.exception_handler(RequestValidationError)
    async def log_validation_errors(request: Request, exc: RequestValidationError) -> JSONResponse:
        print(
            f"[422] {request.method} {request.url.path}: {exc.errors()}",
            file=sys.stderr,
            flush=True,
        )
        return JSONResponse({"detail": exc.errors()}, status_code=422)
