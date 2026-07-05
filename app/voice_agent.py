"""Run the Voca agent for a voice turn (non-streaming, spoken reply)."""

from __future__ import annotations

import re
import uuid

import ai

from app.agent.common_patterns import VOICE_COMMON_PATTERNS
from app.agent.mcp_xero import build_agent
from app.agent.voca_agent import system_prompt_for_session
from app.config import get_settings
from app.session import load_chat_messages, save_chat_messages
from app.session_context import bind_request_context, reset_request_context
from ai.agents.mcp.client import ensure_connection_pool
from app.voice_bill_fast import try_voice_bill_fast_path, try_voice_pending_bill_confirm
from app.voice_chase_fast import try_voice_chase_list_fast_path, try_voice_chase_send_fast_path
from app.voice_fast import try_voice_fast_path
from app.voice_invoice_fast import (
    try_voice_invoice_fast_path,
    try_voice_pending_invoice_confirm,
    try_voice_pending_invoice_send_confirm,
)
from app.voice_receipt_fast import try_voice_receipt_to_xero

settings = get_settings()

VOICE_MODEL = ai.get_model(settings.voice_ai_model)

VOICE_EXTRA = (
    "WhatsApp message — reply in 2–3 short plain sentences. No markdown or tables.\n"
    "Reads: xero_* MCP tools with xeroTenantId from session context.\n"
    "Send invoice / chase: create_and_send_invoice or send_payment_reminder.\n"
    "If they already confirmed customer, amount, and description, call create_and_send_invoice immediately."
)


def _strip_markdown(text: str) -> str:
    """Light cleanup so TTS reads naturally."""
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\|[^|\n]+\|", "", text)
    text = re.sub(r"-{3,}", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


async def try_voca_fast_reply(
    *,
    chat_session_id: str,
    connection_id: str,
    user_text: str,
) -> str | None:
    """Fast paths only (Xero lookups, confirmations) — no MCP agent."""
    kwargs = {
        "chat_session_id": chat_session_id,
        "connection_id": connection_id,
        "user_text": user_text,
    }
    for fast_fn in (
        try_voice_chase_list_fast_path,
        try_voice_fast_path,
        try_voice_pending_invoice_confirm,
        try_voice_pending_invoice_send_confirm,
        try_voice_receipt_to_xero,
        try_voice_pending_bill_confirm,
        try_voice_invoice_fast_path,
        try_voice_bill_fast_path,
        try_voice_chase_send_fast_path,
    ):
        fast = await fast_fn(**kwargs)
        if fast:
            return _strip_markdown(fast)
    return None


async def run_voca_voice_turn(
    *,
    chat_session_id: str,
    connection_id: str,
    user_text: str,
    legacy_connection_ids: list[str] | None = None,
) -> str:
    """Execute one voice delegation turn and return text for the caller."""
    fast = await try_voice_chase_list_fast_path(
        chat_session_id=chat_session_id,
        connection_id=connection_id,
        user_text=user_text,
    )
    if fast:
        reply = _strip_markdown(fast)
        history = load_chat_messages(chat_session_id)
        updated = [*history, _user_ui(user_text), _assistant_ui(reply)]
        save_chat_messages(chat_session_id, updated)
        return reply

    fast = await try_voice_fast_path(
        chat_session_id=chat_session_id,
        connection_id=connection_id,
        user_text=user_text,
    )
    if fast:
        reply = _strip_markdown(fast)
        history = load_chat_messages(chat_session_id)
        updated = [*history, _user_ui(user_text), _assistant_ui(reply)]
        save_chat_messages(chat_session_id, updated)
        return reply

    pending = await try_voice_pending_invoice_confirm(
        chat_session_id=chat_session_id,
        connection_id=connection_id,
        user_text=user_text,
    )
    if pending:
        reply = _strip_markdown(pending)
        history = load_chat_messages(chat_session_id)
        updated = [*history, _user_ui(user_text), _assistant_ui(reply)]
        save_chat_messages(chat_session_id, updated)
        return reply

    pending_send = await try_voice_pending_invoice_send_confirm(
        chat_session_id=chat_session_id,
        connection_id=connection_id,
        user_text=user_text,
    )
    if pending_send:
        reply = _strip_markdown(pending_send)
        history = load_chat_messages(chat_session_id)
        updated = [*history, _user_ui(user_text), _assistant_ui(reply)]
        save_chat_messages(chat_session_id, updated)
        return reply

    receipt_xero = await try_voice_receipt_to_xero(
        chat_session_id=chat_session_id,
        connection_id=connection_id,
        user_text=user_text,
    )
    if receipt_xero:
        reply = _strip_markdown(receipt_xero)
        history = load_chat_messages(chat_session_id)
        updated = [*history, _user_ui(user_text), _assistant_ui(reply)]
        save_chat_messages(chat_session_id, updated)
        return reply

    pending_bill = await try_voice_pending_bill_confirm(
        chat_session_id=chat_session_id,
        connection_id=connection_id,
        user_text=user_text,
    )
    if pending_bill:
        reply = _strip_markdown(pending_bill)
        history = load_chat_messages(chat_session_id)
        updated = [*history, _user_ui(user_text), _assistant_ui(reply)]
        save_chat_messages(chat_session_id, updated)
        return reply

    invoice_fast = await try_voice_invoice_fast_path(
        chat_session_id=chat_session_id,
        connection_id=connection_id,
        user_text=user_text,
    )
    if invoice_fast:
        reply = _strip_markdown(invoice_fast)
        history = load_chat_messages(chat_session_id)
        updated = [*history, _user_ui(user_text), _assistant_ui(reply)]
        save_chat_messages(chat_session_id, updated)
        return reply

    bill_fast = await try_voice_bill_fast_path(
        chat_session_id=chat_session_id,
        connection_id=connection_id,
        user_text=user_text,
    )
    if bill_fast:
        reply = _strip_markdown(bill_fast)
        history = load_chat_messages(chat_session_id)
        updated = [*history, _user_ui(user_text), _assistant_ui(reply)]
        save_chat_messages(chat_session_id, updated)
        return reply

    chase_send = await try_voice_chase_send_fast_path(
        chat_session_id=chat_session_id,
        connection_id=connection_id,
        user_text=user_text,
    )
    if chase_send:
        reply = _strip_markdown(chase_send)
        history = load_chat_messages(chat_session_id)
        updated = [*history, _user_ui(user_text), _assistant_ui(reply)]
        save_chat_messages(chat_session_id, updated)
        return reply

    history = load_chat_messages(chat_session_id)
    user_message = ai.user_message(user_text.strip())
    prior = _history_to_agent_messages(history)
    system = (
        system_prompt_for_session(chat_session_id, connection_id, legacy_connection_ids)
        + "\n\n"
        + VOICE_COMMON_PATTERNS
        + "\n\n"
        + VOICE_EXTRA
    )
    full_messages = [ai.system_message(system), *prior, user_message]

    chat_token, xero_token = bind_request_context(chat_session_id, connection_id)
    text_parts: list[str] = []

    try:
        voice_agent = await build_agent(connection_id)
        async with ensure_connection_pool():
            async with voice_agent.run(VOICE_MODEL, full_messages) as result:
                async for event in result:
                    if isinstance(event, ai.events.HookEvent) and event.hook.status == "pending":
                        ai.resolve_hook(event.hook.hook_id, {"granted": True})
                    if event.kind == "text_delta" and getattr(event, "chunk", None):
                        text_parts.append(event.chunk)
    finally:
        reset_request_context(chat_token, xero_token)

    reply = _strip_markdown("".join(text_parts).strip())
    if not reply:
        reply = "Sorry, I couldn't complete that. Could you say it again?"

    updated = [*history, _user_ui(user_text), _assistant_ui(reply)]
    save_chat_messages(chat_session_id, updated)
    return reply


def _history_to_agent_messages(history: list) -> list:
    out: list = []
    for msg in history[-4:]:
        role = msg.get("role") if isinstance(msg, dict) else getattr(msg, "role", None)
        parts = msg.get("parts", []) if isinstance(msg, dict) else getattr(msg, "parts", [])
        text = "".join(
            p.get("text", "") if isinstance(p, dict) else getattr(p, "text", "")
            for p in parts
            if (p.get("type") if isinstance(p, dict) else getattr(p, "type", "")) == "text"
        ).strip()
        if not text:
            continue
        if role == "user":
            out.append(ai.user_message(text))
        elif role == "assistant":
            out.append(ai.assistant_message(text))
    return out


def _user_ui(text: str) -> dict:
    return {"id": str(uuid.uuid4()), "role": "user", "parts": [{"type": "text", "text": text}]}


def _assistant_ui(text: str) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "role": "assistant",
        "parts": [{"type": "text", "text": text}],
    }
