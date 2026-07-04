"""Chat message persistence API."""

from __future__ import annotations

from pydantic import BaseModel, Field

from fastapi import APIRouter, HTTPException, Query

from app.session import clear_chat_messages, load_chat_messages, save_chat_messages

router = APIRouter(prefix="/api", tags=["messages"])


class MessagesPayload(BaseModel):
    session_id: str
    messages: list[dict] = Field(default_factory=list)


@router.get("/messages")
def get_messages(session_id: str = Query(...)) -> dict:
    if not session_id.strip():
        raise HTTPException(400, "session_id required")
    return {"session_id": session_id, "messages": load_chat_messages(session_id)}


@router.put("/messages")
def put_messages(payload: MessagesPayload) -> dict:
    save_chat_messages(payload.session_id, payload.messages)
    return {"ok": True, "count": len(payload.messages)}


@router.delete("/messages")
def delete_messages(session_id: str = Query(...)) -> dict:
    clear_chat_messages(session_id)
    return {"ok": True}
