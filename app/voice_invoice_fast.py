"""Fast invoice path for voice — parse natural speech, create + send in one shot."""

from __future__ import annotations

import json
import re

from app.agent.tools.xero import create_and_send_invoice, send_invoice
from app.demo_state import set_invoice_mirror
from app.session import get_session, save_session
from app.session_context import bind_request_context, reset_request_context
from app.voice_parse import CONFIRM_RE, DENY_RE, clean_tail, parse_gbp

_INVOICE_INTENT = re.compile(
    r"\b("
    r"send\s+(?:an?\s+)?invoice|create\s+(?:an?\s+)?invoice|"
    r"send\s+it|bill\s+|invoice\s+|raise\s+(?:an?\s+)?invoice|"
    r"sending\s+(?:an?\s+)?invoice"
    r")\b",
    re.I,
)

_INVOICE_TO = re.compile(r"invoice\s+to\s+(.+?)\s+for\s+(.+)", re.I | re.DOTALL)

# "send it for 200 pounds for plumbing and for Miss Wales"
_SEND_IT_FOR = re.compile(
    r"send\s+it\s+for\s+(.+?)\s+for\s+(.+?)(?:\s+and\s+)?(?:for|to)\s+(.+)\s*$",
    re.I | re.DOTALL,
)

# "200 pounds for plumbing for Miss Wales" / "... to Miss Wales"
_AMOUNT_DESC_CUSTOMER = re.compile(
    r"(?:for\s+)?(.+?\d.+?pounds?|two hundred|three hundred|\d+)\s+"
    r"(?:pounds?\s+)?(?:for\s+)?(.+?)\s+(?:for|to)\s+(.+)\s*$",
    re.I | re.DOTALL,
)


def _parse_amount_desc_customer(amount_text: str, desc_text: str, customer_text: str) -> tuple[str, float, str] | None:
    amount = parse_gbp(amount_text)
    customer = clean_tail(customer_text)
    description = clean_tail(desc_text) or "Services"
    if amount is None or not customer:
        return None
    return customer, amount, description


def parse_invoice_task(user_text: str) -> tuple[str, float, str] | None:
    """Parse customer, amount, description from natural voice invoice instructions."""
    text = user_text.strip()
    if not text:
        return None

    if not _INVOICE_INTENT.search(text):
        # Also allow bare "200 pounds for plumbing for Miss Wales" after prior context
        if not re.search(r"\b(pounds?|£|quid|two hundred|three hundred)\b", text, re.I):
            return None

    match = _INVOICE_TO.search(text)
    if match:
        customer = clean_tail(match.group(1))
        remainder = match.group(2).strip()
        description = "Services"
        amount_text = remainder
        if re.search(r"\s+for\s+", remainder, re.I):
            amount_part, desc_part = re.split(r"\s+for\s+", remainder, maxsplit=1, flags=re.I)
            amount_text = amount_part.strip()
            description = clean_tail(desc_part) or "Services"
        amount = parse_gbp(amount_text)
        if amount is not None and customer:
            return customer, amount, description

    match = _SEND_IT_FOR.search(text)
    if match:
        return _parse_amount_desc_customer(match.group(1), match.group(2), match.group(3))

    match = _AMOUNT_DESC_CUSTOMER.search(text)
    if match:
        return _parse_amount_desc_customer(match.group(1), match.group(2), match.group(3))

    # "Send an invoice to Miss Wales for two hundred pounds for plumbing work"
    loose = re.search(
        r"(?:invoice|bill|send)\s+(?:to\s+)?(.+?)\s+for\s+(.+)",
        text,
        re.I | re.DOTALL,
    )
    if loose:
        customer = clean_tail(loose.group(1))
        remainder = loose.group(2).strip()
        if re.search(r"\s+for\s+", remainder, re.I):
            amount_part, desc_part = re.split(r"\s+for\s+", remainder, maxsplit=1, flags=re.I)
            amount = parse_gbp(amount_part)
            description = clean_tail(desc_part) or "Services"
            if amount is not None and customer:
                return customer, amount, description
        amount = parse_gbp(remainder)
        if amount is not None and customer:
            return customer, amount, "Services"

    return None


def _spoken_result(data: dict) -> str:
    if data.get("customer_not_found"):
        return str(data.get("audit") or data.get("error", "Customer not found."))
    if data.get("error"):
        return str(data["error"])
    audit = data.get("audit")
    if isinstance(audit, str) and audit.strip():
        return audit.replace("Created and sent", "Done — sent")
    number = data.get("invoice_number", "")
    customer = data.get("customer", "the customer")
    total = float(data.get("total_gbp") or 0)
    return f"Done — sent invoice {number} to {customer} for £{total:.2f}."


async def _create_and_send(
    *,
    chat_session_id: str,
    connection_id: str,
    customer: str,
    amount: float,
    description: str,
    create_if_missing: bool,
) -> str:
    chat_token, xero_token = bind_request_context(chat_session_id, connection_id)
    try:
        raw = await create_and_send_invoice.fn(
            customer_name=customer,
            description=description,
            amount_gbp=amount,
            reference="voca-voice",
            create_if_missing=create_if_missing,
        )
        data = json.loads(raw)
        if data.get("customer_not_found"):
            session = get_session(chat_session_id)
            session["pending_invoice"] = {
                "customer_name": customer,
                "amount_gbp": amount,
                "description": description,
            }
            save_session(chat_session_id, session)
            return _spoken_result(data)

        session = get_session(chat_session_id)
        session.pop("pending_invoice", None)
        session.pop("pending_send_invoice", None)
        save_session(chat_session_id, session)

        if data.get("invoice_number") or data.get("status") == "AUTHORISED":
            set_invoice_mirror(
                connection_id,
                status="sent",
                customer=customer,
                amount_gbp=amount,
                invoice_number=data.get("invoice_number"),
            )
        return _spoken_result(data)
    finally:
        reset_request_context(chat_token, xero_token)


async def try_voice_pending_invoice_confirm(
    *,
    chat_session_id: str,
    connection_id: str,
    user_text: str,
) -> str | None:
    """Handle yes/no after we asked to create a missing customer."""
    session = get_session(chat_session_id)
    pending = session.get("pending_invoice")
    if not pending:
        return None

    text = user_text.strip()
    if DENY_RE.search(text):
        session.pop("pending_invoice", None)
        save_session(chat_session_id, session)
        return "No problem — I won't create that customer. What else can I do?"

    if not CONFIRM_RE.search(text):
        return None

    return await _create_and_send(
        chat_session_id=chat_session_id,
        connection_id=connection_id,
        customer=pending["customer_name"],
        amount=float(pending["amount_gbp"]),
        description=pending.get("description") or "Services",
        create_if_missing=True,
    )


async def try_voice_pending_invoice_send_confirm(
    *,
    chat_session_id: str,
    connection_id: str,
    user_text: str,
) -> str | None:
    """Send a draft if we somehow left one pending."""
    session = get_session(chat_session_id)
    pending = session.get("pending_send_invoice")
    if not pending:
        return None

    text = user_text.strip()
    if DENY_RE.search(text):
        session.pop("pending_send_invoice", None)
        save_session(chat_session_id, session)
        return "Okay — I won't send that invoice."

    if not CONFIRM_RE.search(text):
        return None

    chat_token, xero_token = bind_request_context(chat_session_id, connection_id)
    try:
        raw = await send_invoice.fn(invoice_id=pending["invoice_id"])
        data = json.loads(raw)
    finally:
        reset_request_context(chat_token, xero_token)

    session.pop("pending_send_invoice", None)
    save_session(chat_session_id, session)
    if data.get("error"):
        return str(data["error"])
    set_invoice_mirror(
        connection_id,
        status="sent",
        customer=str(pending.get("customer_name", "")),
        amount_gbp=float(pending.get("amount_gbp") or 0),
        invoice_number=data.get("invoice_number"),
    )
    return _spoken_result(data)


async def try_voice_invoice_fast_path(
    *,
    chat_session_id: str,
    connection_id: str,
    user_text: str,
) -> str | None:
    """Create and send an invoice without calling Claude (~5s not ~40s)."""
    parsed = parse_invoice_task(user_text)
    if not parsed:
        return None

    customer, amount, description = parsed
    # Miss Wales etc. often aren't in demo Xero yet — create on send when caller gave full details
    return await _create_and_send(
        chat_session_id=chat_session_id,
        connection_id=connection_id,
        customer=customer,
        amount=amount,
        description=description,
        create_if_missing=True,
    )
