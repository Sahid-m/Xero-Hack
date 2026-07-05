"""Fast supplier bill path for voice."""

from __future__ import annotations

import json
import re

from app.agent.tools.xero import record_supplier_bill
from app.demo_state import set_receipt_mirror
from app.session import get_session, save_session
from app.session_context import bind_request_context, reset_request_context
from app.voice_parse import CONFIRM_RE, DENY_RE, clean_tail, parse_gbp

_BILL_INTENT = re.compile(
    r"\b("
    r"record\s+(?:a\s+)?bill|supplier\s+bill|got\s+a\s+bill|"
    r"bill\s+from|expense\s+from|paid\s+.+\s+for|"
    r"record\s+(?:an?\s+)?expense"
    r")\b",
    re.I,
)

_BILL_FROM = re.compile(
    r"(?:bill|expense)\s+from\s+(.+?)\s+for\s+(.+)",
    re.I | re.DOTALL,
)


def parse_bill_task(user_text: str) -> tuple[str, float, str] | None:
    if not _BILL_INTENT.search(user_text):
        return None
    match = _BILL_FROM.search(user_text)
    if not match:
        return None

    supplier = clean_tail(match.group(1))
    remainder = match.group(2).strip()
    description = "Expense"
    amount_text = remainder

    if re.search(r"\s+for\s+", remainder, re.I):
        amount_part, desc_part = re.split(r"\s+for\s+", remainder, maxsplit=1, flags=re.I)
        amount_text = amount_part.strip()
        description = clean_tail(desc_part) or "Expense"

    amount = parse_gbp(amount_text)
    if amount is None or not supplier:
        return None
    return supplier, amount, description


def _spoken_result(data: dict) -> str:
    if data.get("supplier_not_found"):
        return str(data.get("audit") or data.get("error", "Supplier not found."))
    if data.get("error"):
        return str(data["error"])
    audit = data.get("audit")
    if isinstance(audit, str) and audit.strip():
        return audit
    return f"Recorded bill from {data.get('supplier', 'supplier')} for £{float(data.get('total_gbp', 0)):.2f}."


async def _record_bill(
    *,
    chat_session_id: str,
    connection_id: str,
    supplier: str,
    amount: float,
    description: str,
    create_if_missing: bool,
) -> str:
    chat_token, xero_token = bind_request_context(chat_session_id, connection_id)
    try:
        raw = await record_supplier_bill.fn(
            supplier_name=supplier,
            description=description,
            amount_gbp=amount,
            reference="voca-voice",
            create_if_missing=create_if_missing,
        )
        data = json.loads(raw)
        if create_if_missing or data.get("bill_number"):
            session = get_session(chat_session_id)
            session.pop("pending_bill", None)
            save_session(chat_session_id, session)
        if data.get("bill_number"):
            set_receipt_mirror(
                connection_id,
                vendor=str(data.get("supplier") or supplier),
                amount_gbp=float(data.get("total_gbp") or amount),
                category=description,
                in_xero=True,
                bill_number=data.get("bill_number"),
            )
        return _spoken_result(data)
    finally:
        reset_request_context(chat_token, xero_token)


async def try_voice_pending_bill_confirm(
    *,
    chat_session_id: str,
    connection_id: str,
    user_text: str,
) -> str | None:
    session = get_session(chat_session_id)
    pending = session.get("pending_bill")
    if not pending:
        return None

    if DENY_RE.search(user_text.strip()):
        session.pop("pending_bill", None)
        save_session(chat_session_id, session)
        return "No problem — I won't record that bill."

    if not CONFIRM_RE.search(user_text.strip()):
        return None

    return await _record_bill(
        chat_session_id=chat_session_id,
        connection_id=connection_id,
        supplier=pending["supplier_name"],
        amount=float(pending["amount_gbp"]),
        description=pending.get("description") or "Expense",
        create_if_missing=True,
    )


async def try_voice_bill_fast_path(
    *,
    chat_session_id: str,
    connection_id: str,
    user_text: str,
) -> str | None:
    parsed = parse_bill_task(user_text)
    if not parsed:
        return None
    supplier, amount, description = parsed
    return await _record_bill(
        chat_session_id=chat_session_id,
        connection_id=connection_id,
        supplier=supplier,
        amount=amount,
        description=description,
        create_if_missing=False,
    )
