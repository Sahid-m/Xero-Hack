"""ElevenLabs phone agent webhooks — call Voca like a personal bookkeeper."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.config import get_settings
from app.voice_agent import run_voca_voice_turn
from app.voice_sessions import (
    connection_for_phone,
    link_phone,
    normalize_phone,
    phone_for_connection,
    unlink_phone,
)
from app.xero_client import is_connected, resolve_xero_connection

router = APIRouter(tags=["voice"])
settings = get_settings()


class LinkPhoneRequest(BaseModel):
    connection_id: str
    phone_number: str


class TwilioInitRequest(BaseModel):
    model_config = {"extra": "ignore"}

    caller_id: str | None = None
    agent_id: str | None = None
    called_number: str | None = None
    call_sid: str | None = None


class ElevenLabsToolRequest(BaseModel):
    model_config = {"extra": "ignore"}

    tool_call_id: str | None = None
    tool_name: str | None = None
    # Flat form (optional): { "instruction": "...", "caller_phone": "..." }
    instruction: str | None = None
    task: str | None = None
    caller_phone: str | None = None
    connection_id: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    conversation_id: str | None = None


@router.get("/voice/status")
def voice_status() -> dict:
    return {
        "phone_configured": bool(settings.voca_phone_number),
        "phone_number": settings.voca_phone_number or None,
        "agent_id": settings.elevenlabs_agent_id or None,
        "public_base_url": settings.public_base_url or None,
        "webhooks": {
            "init": f"{settings.public_base_url}/voice/init" if settings.public_base_url else "/voice/init",
            "delegate": f"{settings.public_base_url}/voice/tools/delegate"
            if settings.public_base_url
            else "/voice/tools/delegate",
            "instruct": f"{settings.public_base_url}/voice/instruct"
            if settings.public_base_url
            else "/voice/instruct",
        },
        "architecture": (
            "ElevenLabs handles voice; ONE tool (delegate_to_voca) sends each instruction "
            "to the full Voca Xero agent. See docs/VOICE_SETUP.md"
        ),
    }


@router.post("/api/voice/link")
def api_link_phone(body: LinkPhoneRequest) -> dict:
    """Link the user's mobile number to their Xero connection (for inbound calls)."""
    try:
        phone = link_phone(body.connection_id, body.phone_number)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True, "phone_e164": phone, "connection_id": body.connection_id}


@router.delete("/api/voice/link")
def api_unlink_phone(connection_id: str = Query(...)) -> dict:
    unlink_phone(connection_id)
    return {"ok": True}


@router.get("/api/voice/link")
def api_get_linked_phone(connection_id: str = Query(...)) -> dict:
    phone = phone_for_connection(connection_id)
    return {"connection_id": connection_id, "phone_e164": phone, "linked": bool(phone)}


@router.post("/voice/init")
async def voice_conversation_init(body: TwilioInitRequest) -> dict:
    """
    ElevenLabs conversation initiation webhook (inbound Twilio calls).
    Maps caller_id → Xero connection and personalises the greeting.
    """
    caller = normalize_phone(body.caller_id or "")
    connection_id = connection_for_phone(caller) if caller else None
    xero_linked = False

    if connection_id:
        resolve_xero_connection(connection_id, [])
        xero_linked = is_connected(connection_id)

    if xero_linked:
        first_message = (
            "Hi, it's Voca — your Xero bookkeeper. "
            "Your books are connected. What would you like me to do?"
        )
    elif connection_id:
        first_message = (
            "Hi, it's Voca. I recognise your number but Xero isn't connected yet. "
            "Open the Voca app and tap Connect Xero, then call me back."
        )
    else:
        first_message = (
            "Hi, it's Voca — your accounting assistant. "
            "I don't have your number on file yet. "
            "Link your mobile in the Voca web app, connect Xero, then call again."
        )

    return {
        "dynamic_variables": {
            "caller_phone": caller,
            "connection_id": connection_id or "",
            "xero_linked": str(xero_linked).lower(),
        },
        "conversation_config_override": {
            "agent": {"first_message": first_message},
        },
    }


@router.post("/voice/tools/delegate")
@router.post("/voice/instruct")
async def voice_tool_delegate(body: ElevenLabsToolRequest) -> dict:
    """
    ElevenLabs server tool — pass the caller's instruction; Voca runs the full agent.

    Configure ONE webhook tool in ElevenLabs named `delegate_to_voca`.
    ElevenLabs handles voice; this endpoint handles all Xero logic.
    """
    params = body.parameters
    task = str(
        body.instruction
        or body.task
        or params.get("task")
        or params.get("instruction")
        or params.get("request")
        or ""
    ).strip()
    if not task:
        return {"result": "I didn't catch the task. What should I do in Xero?"}

    caller = normalize_phone(
        str(
            body.caller_phone
            or params.get("caller_phone")
            or params.get("phone")
            or ""
        )
    )
    connection_id = (
        str(body.connection_id or params.get("connection_id") or "").strip() or None
    )
    if not connection_id and caller:
        connection_id = connection_for_phone(caller)

    if not connection_id:
        return {
            "result": (
                "I can't access your Xero yet. "
                "Register your phone number in the Voca app and connect Xero first."
            )
        }

    resolve_xero_connection(connection_id, [])
    if not is_connected(connection_id):
        return {
            "result": (
                "Xero isn't connected for your account. "
                "Open Voca in your browser, tap Connect Xero, then call me back."
            )
        }

    chat_session_id = f"voice-{connection_id}"
    try:
        reply = await run_voca_voice_turn(
            chat_session_id=chat_session_id,
            connection_id=connection_id,
            user_text=task,
        )
    except Exception as exc:
        return {"result": f"Something went wrong pulling that from Xero: {exc}"}

    return {"result": reply}


@router.post("/voice/webhook")
async def voice_webhook_legacy(body: ElevenLabsToolRequest) -> dict:
    """Legacy path — forwards to delegate tool."""
    return await voice_tool_delegate(body)
