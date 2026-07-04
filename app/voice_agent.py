"""Run the Voca agent for a voice turn (non-streaming, spoken reply)."""

from __future__ import annotations

import re
import uuid

import ai

from app.agent.voca_agent import MODEL, system_prompt_for_session, voca_agent
from app.session import load_chat_messages, save_chat_messages
from app.session_context import bind_request_context, reset_request_context


def _strip_markdown(text: str) -> str:
    """Light cleanup so TTS reads naturally."""
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\|[^|\n]+\|", "", text)
    text = re.sub(r"-{3,}", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


async def run_voca_voice_turn(
    *,
    chat_session_id: str,
    connection_id: str,
    user_text: str,
    legacy_connection_ids: list[str] | None = None,
) -> str:
    """Execute one voice delegation turn and return text for the caller."""
    history = load_chat_messages(chat_session_id)
    user_message = ai.user_message(user_text.strip())
    prior = _history_to_agent_messages(history)
    full_messages = [
        ai.system_message(
            system_prompt_for_session(chat_session_id, connection_id, legacy_connection_ids)
        ),
        *prior,
        user_message,
        ai.system_message(
            "Voice call — reply in 2–4 short spoken sentences. "
            "No markdown tables. State amounts clearly. "
            "Use tools for live Xero data before answering."
        ),
    ]

    chat_token, xero_token = bind_request_context(chat_session_id, connection_id)
    text_parts: list[str] = []

    try:
        async with voca_agent.run(MODEL, full_messages) as result:
            async for event in result:
                if isinstance(event, ai.events.HookEvent) and event.hook.status == "pending":
                    # Caller delegated by phone — proceed after verbal confirm in conversation
                    ai.resolve_hook(event.hook.label, {"approved": True})
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
    for msg in history[-12:]:
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
