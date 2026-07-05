"""Fast payment-chase paths for voice."""

from __future__ import annotations

import json
import re

from app.agent.tools.xero import send_payment_reminder
from app.agent.tools.xero_queries import who_should_i_chase
from app.session_context import bind_request_context, reset_request_context

_CHASE_LIST = re.compile(
    r"\b("
    r"who should i chase|who to chase|chase anyone|overdue|"
    r"who.?s late paying|late payers|who hasn.?t paid|payment overdue"
    r")\b",
    re.I,
)

_CHASE_SEND = re.compile(
    r"\b("
    r"chase|remind|send (?:a )?reminder|payment reminder|nudge|follow up"
    r")\b",
    re.I,
)

_CHASE_CUSTOMER = re.compile(
    r"(?:chase|remind|nudge|follow up(?: with)?|send (?:a )?reminder to)\s+(.+?)(?:\s+for payment|\s+to pay|$)",
    re.I,
)


async def try_voice_chase_list_fast_path(
    *,
    chat_session_id: str,
    connection_id: str,
    user_text: str,
) -> str | None:
    if not _CHASE_LIST.search(user_text):
        return None
    if not re.search(r"\bwho (?:should i|to) chase\b", user_text, re.I):
        send_match = _CHASE_CUSTOMER.search(user_text)
        if send_match:
            name = send_match.group(1).strip().rstrip("?.")
            if name and not name.lower().startswith("for ") and len(name) > 2:
                return None

    chat_token, xero_token = bind_request_context(chat_session_id, connection_id)
    try:
        raw = await who_should_i_chase.fn(limit=5)
        data = json.loads(raw)
        return str(data.get("audit") or "No overdue invoices right now.")
    finally:
        reset_request_context(chat_token, xero_token)


async def try_voice_chase_send_fast_path(
    *,
    chat_session_id: str,
    connection_id: str,
    user_text: str,
) -> str | None:
    if not _CHASE_SEND.search(user_text):
        return None

    customer = ""
    match = _CHASE_CUSTOMER.search(user_text)
    if match:
        customer = match.group(1).strip().strip(".,—-")
    if not customer:
        return None

    chat_token, xero_token = bind_request_context(chat_session_id, connection_id)
    try:
        raw = await send_payment_reminder.fn(customer_name=customer)
        data = json.loads(raw)
        if data.get("audit"):
            return str(data["audit"])
        return str(data.get("error", "Could not send reminder."))
    finally:
        reset_request_context(chat_token, xero_token)
