"""Receipt stub + WhatsApp-to-Xero voice paths."""

from __future__ import annotations

import json
import re

from app.agent.tools.xero import record_supplier_bill
from app.demo_state import set_receipt_mirror
from app.session import get_session, save_session
from app.session_context import bind_request_context, reset_request_context
from app.voice_parse import CONFIRM_RE, DENY_RE

_RECEIPT_TO_XERO = re.compile(
    r"\b("
    r"add\s+(?:that|it|this|the\s+receipt)\s+(?:into|to)\s+xero|"
    r"put\s+(?:that|it|this|the\s+receipt)\s+(?:into|to)\s+xero|"
    r"updated?\s+(?:the\s+)?receipts?\s+(?:to|on|via)\s+whatsapp|"
    r"record\s+(?:that|this|the)\s+receipt|"
    r"add\s+(?:that|this|the)\s+(?:whatsapp\s+)?receipt"
    r")\b",
    re.I,
)

_RECEIPT_CONFIRM_RE = re.compile(r"\b(add it|add that|confirm|go for it)\b", re.I)

DEMO_RECEIPT_STUB = {
    "vendor": "Shell",
    "amount_gbp": 47.50,
    "category": "Motor expenses",
}


def store_last_receipt(chat_session_id: str, *, vendor: str, amount_gbp: float, category: str) -> dict:
    payload = {
        "vendor": vendor,
        "amount_gbp": amount_gbp,
        "category": category,
        "added": False,
    }
    session = get_session(chat_session_id)
    session["last_receipt"] = payload
    save_session(chat_session_id, session)
    return payload


def get_last_receipt(chat_session_id: str) -> dict | None:
    session = get_session(chat_session_id)
    raw = session.get("last_receipt")
    return raw if isinstance(raw, dict) else None


async def try_voice_receipt_to_xero(
    *,
    chat_session_id: str,
    connection_id: str,
    user_text: str,
) -> str | None:
    """Record the last WhatsApp/uploaded receipt as a supplier bill in Xero.

    Matches either an explicit "add that receipt to Xero" phrasing, or — if
    there's a receipt awaiting confirmation — a plain "yes"/"add it" reply.
    Without the pending-receipt gate, a bare confirmation would be too easy to
    mismatch against unrelated conversation.
    """
    text = user_text.strip()
    last = get_last_receipt(chat_session_id)
    pending = bool(last) and not last.get("added")

    explicit_match = _RECEIPT_TO_XERO.search(text)
    if not explicit_match:
        confirmed = CONFIRM_RE.search(text) or _RECEIPT_CONFIRM_RE.search(text)
        if not pending or not confirmed or DENY_RE.search(text):
            return None

    if not last:
        return (
            "I don't have a receipt yet. Send a photo on WhatsApp or upload one "
            "on the demo screen, then ask me again."
        )
    if last.get("added"):
        return "That receipt's already in Xero — send a new photo if you've got another one."

    vendor = str(last.get("vendor") or "Shell")
    stored_amount = last.get("amount_gbp")
    amount = float(stored_amount) if stored_amount is not None else 47.50
    category = str(last.get("category") or "Motor expenses")

    chat_token, xero_token = bind_request_context(chat_session_id, connection_id)
    try:
        raw = await record_supplier_bill.fn(
            supplier_name=vendor,
            description=category,
            amount_gbp=amount,
            reference="voca-whatsapp-receipt",
            create_if_missing=True,
        )
        data = json.loads(raw)
    finally:
        reset_request_context(chat_token, xero_token)

    if data.get("error") and not data.get("bill_number"):
        return str(data.get("audit") or data.get("error", "Could not record that receipt."))

    bill_number = data.get("bill_number")
    session = get_session(chat_session_id)
    if isinstance(session.get("last_receipt"), dict):
        session["last_receipt"]["added"] = True
        save_session(chat_session_id, session)
    set_receipt_mirror(
        connection_id,
        vendor=vendor,
        amount_gbp=amount,
        category=category,
        in_xero=True,
        bill_number=bill_number,
    )
    audit = data.get("audit")
    if isinstance(audit, str) and audit.strip():
        return audit
    return f"Done — added the {vendor} receipt for £{amount:.2f} to Xero as bill {bill_number}."
