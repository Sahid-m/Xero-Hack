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
from app.session import save_chat_messages
from app.session_context import bind_request_context, reset_request_context

if TYPE_CHECKING:
    pass

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    """Matches Next.js AI SDK DefaultChatTransport payload."""

    model_config = {"extra": "ignore"}

    messages: list[ai.agents.ui.ai_sdk.UIMessage]
    session_id: str | None = Field(default=None, description="Chat session for history and setup state")
    connection_id: str | None = Field(default=None, description="Stable id for Xero OAuth tokens")
    legacy_session_ids: list[str] = Field(default_factory=list)
    id: str | None = Field(default=None, description="Chat id from AI SDK (fallback session key)")


def _resolve_chat_session(request: ChatRequest) -> str | None:
    return request.session_id or request.id


def _resolve_connection_id(request: ChatRequest, chat_session_id: str | None) -> str | None:
    return request.connection_id or chat_session_id


@router.post("/chat")
async def chat(request: ChatRequest) -> StreamingResponse:
    chat_session_id = _resolve_chat_session(request)
    connection_id = _resolve_connection_id(request, chat_session_id)
    messages, approvals = ai.agents.ui.ai_sdk.to_messages(request.messages)
    ai.agents.ui.ai_sdk.apply_approvals(approvals)

    if chat_session_id:
        save_chat_messages(chat_session_id, request.messages)

    full_messages = [
        ai.system_message(
            system_prompt_for_session(
                chat_session_id,
                connection_id,
                request.legacy_session_ids,
            )
        ),
        *messages,
    ]
    agent = agent_for_session(chat_session_id)
    chat_token, xero_token = bind_request_context(chat_session_id, connection_id)

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
            reset_request_context(chat_token, xero_token)

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
