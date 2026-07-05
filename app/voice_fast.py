"""Fast WhatsApp answers — skip the LLM for common Xero lookups."""

from __future__ import annotations

import json
import re
import time
from typing import Any

from app.agent.tools.xero_queries import (
    get_profit_and_loss,
    list_invoices,
    list_outstanding_payables,
    list_outstanding_receivables,
    summarize_cash_position,
)
from app.demo_state import set_receivables
from app.session_context import bind_request_context, reset_request_context

_RECEIVABLES = re.compile(
    r"\b("
    r"how much(?: money)?(?: am i| i.?m)? owed|money i.?m owed|am i owed|owed to me|"
    r"customers owe|receivable|outstanding invoices?|unpaid invoices?|who owes me|amount owed|"
    r"how much.*owed|money.*owed"
    r")\b",
    re.I,
)
_PAYABLES = re.compile(
    r"\b("
    r"how much do i owe|what do i owe|money i owe|bills? owed|outstanding bills?|"
    r"payable|owe suppliers|what i owe"
    r")\b",
    re.I,
)
_CASH = re.compile(r"\b(cash position|cash flow|bank summary|financial snapshot)\b", re.I)
_PL = re.compile(r"\b(profit and loss|profit & loss|p&l|p and l|how much profit)\b", re.I)
_LATEST_INVOICE = re.compile(
    r"\b("
    r"latest invoice|last invoice|most recent invoice|recent invoice|"
    r"invoice i sent|invoices? i sent|last (?:invoice|bill) i (?:sent|issued)|"
    r"what'?s my latest invoice|what is my latest invoice|my latest invoice"
    r")\b",
    re.I,
)
_RECENT_EXPENSE = re.compile(
    r"\b("
    r"recent expense|latest expense|last expense|"
    r"recent bill|latest bill|last bill i (?:paid|received|got)|"
    r"recent purchase|latest purchase|last purchase|"
    r"what did i spend|my recent spend|latest spend|"
    r"what'?s my (?:recent|latest) expense|what is my (?:recent|latest) expense"
    r")\b",
    re.I,
)

_CACHE_TTL_SECS = 300
_cache: dict[tuple[str, str], tuple[float, str]] = {}


def _cache_get(connection_id: str, intent: str) -> str | None:
    hit = _cache.get((connection_id, intent))
    if not hit:
        return None
    ts, value = hit
    if time.time() - ts > _CACHE_TTL_SECS:
        _cache.pop((connection_id, intent), None)
        return None
    return value


def _cache_set(connection_id: str, intent: str, value: str) -> None:
    _cache[(connection_id, intent)] = (time.time(), value)


def _money(amount: float | int | None) -> str:
    return f"GBP {float(amount or 0):,.2f}"


def _top_contacts(invoices: list[dict[str, Any]], limit: int = 3) -> str:
    sorted_inv = sorted(invoices, key=lambda i: float(i.get("amount_due") or 0), reverse=True)
    parts = []
    for inv in sorted_inv[:limit]:
        name = inv.get("contact") or "a customer"
        parts.append(f"{name} at {_money(inv.get('amount_due'))}")
    return ", ".join(parts)


def _format_receivables(raw: str) -> str:
    data = json.loads(raw)
    if data.get("error"):
        return str(data["error"])
    total = float(data.get("total_amount_due") or 0)
    count = int(data.get("count") or 0)
    msg = f"You're owed {_money(total)} across {count} unpaid invoices."
    top = _top_contacts(data.get("invoices") or data.get("bills") or [])
    if top:
        msg += f" Your biggest balances are {top}."
    return msg


def _format_payables(raw: str) -> str:
    data = json.loads(raw)
    if data.get("error"):
        return str(data["error"])
    total = float(data.get("total_amount_due") or 0)
    count = int(data.get("count") or 0)
    msg = f"You owe {_money(total)} across {count} unpaid bills."
    top = _top_contacts(data.get("invoices") or data.get("bills") or [])
    if top:
        msg += f" The largest are {top}."
    return msg


def _format_cash(raw: str) -> str:
    data = json.loads(raw)
    if data.get("error"):
        return str(data["error"])
    recv = float(data.get("outstanding_receivables_gbp") or 0)
    pay = float(data.get("outstanding_payables_gbp") or 0)
    bank = int(data.get("bank_transactions_last_7_days") or 0)
    return (
        f"You're owed {_money(recv)} and you owe {_money(pay)} to suppliers. "
        f"There were {bank} bank transactions in the last seven days."
    )


def _format_pl(raw: str) -> str:
    data = json.loads(raw)
    if data.get("error"):
        return str(data["error"])
    audit = data.get("audit")
    if isinstance(audit, str) and audit.strip():
        return audit.replace("P&L report", "Profit and loss")
    return "I've pulled your profit and loss report — check the Voca app for the full breakdown."


def _format_latest_invoice(raw: str) -> str:
    data = json.loads(raw)
    if data.get("error"):
        return str(data["error"])
    invoices = data.get("invoices") or []
    if not invoices:
        return "I couldn't find any sales invoices in Xero yet."
    sorted_inv = sorted(
        invoices,
        key=lambda i: str(i.get("date") or ""),
        reverse=True,
    )
    inv = sorted_inv[0]
    contact = inv.get("contact") or "a customer"
    number = inv.get("invoice_number") or inv.get("invoice_id") or "invoice"
    total = _money(inv.get("total"))
    date = inv.get("date") or "unknown date"
    status = (inv.get("status") or "").lower()
    due = inv.get("due_date")
    msg = f"Your latest sent invoice is {number} to {contact} for {total} on {date}"
    if status:
        msg += f" ({status})"
    if due:
        msg += f", due {due}"
    msg += "."
    return msg


def _format_recent_expense(raw: str) -> str:
    data = json.loads(raw)
    if data.get("error"):
        return str(data["error"])
    bills = data.get("invoices") or data.get("bills") or []
    if not bills:
        return "I couldn't find any bills or expenses in Xero yet."
    sorted_bills = sorted(
        bills,
        key=lambda i: str(i.get("date") or ""),
        reverse=True,
    )
    bill = sorted_bills[0]
    contact = bill.get("contact") or "a supplier"
    total = _money(bill.get("total"))
    date = bill.get("date") or "unknown date"
    status = (bill.get("status") or "").lower()
    msg = f"Your most recent expense is {total} to {contact} on {date}"
    if status:
        msg += f" ({status})"
    msg += "."
    return msg


def peek_voice_fast_cache(connection_id: str, user_text: str) -> str | None:
    """Return a cached fast-path answer without calling Xero."""
    text = user_text.strip()
    if not text:
        return None
    intent: str | None = None
    if _RECEIVABLES.search(text):
        intent = "receivables"
    elif _PAYABLES.search(text):
        intent = "payables"
    elif _CASH.search(text):
        intent = "cash"
    elif _PL.search(text):
        intent = "pl"
    elif _LATEST_INVOICE.search(text):
        intent = "latest_invoice"
    elif _RECENT_EXPENSE.search(text):
        intent = "recent_expense"
    if not intent:
        return None
    return _cache_get(connection_id, intent)


def is_fast_lookup(text: str) -> bool:
    """Common Xero read-only questions — answer in the webhook, not via callback."""
    text = text.strip()
    if not text:
        return False
    return bool(
        _RECEIVABLES.search(text)
        or _PAYABLES.search(text)
        or _CASH.search(text)
        or _PL.search(text)
        or _LATEST_INVOICE.search(text)
        or _RECENT_EXPENSE.search(text)
    )


async def try_voice_fast_path(
    *,
    chat_session_id: str,
    connection_id: str,
    user_text: str,
) -> str | None:
    """Return a spoken answer without calling Claude, or None to use the full agent."""
    text = user_text.strip()
    if not text:
        return None

    intent: str | None = None
    if _RECEIVABLES.search(text):
        intent = "receivables"
    elif _PAYABLES.search(text):
        intent = "payables"
    elif _CASH.search(text):
        intent = "cash"
    elif _PL.search(text):
        intent = "pl"
    elif _LATEST_INVOICE.search(text):
        intent = "latest_invoice"
    elif _RECENT_EXPENSE.search(text):
        intent = "recent_expense"

    if not intent:
        return None

    cached = _cache_get(connection_id, intent)
    if cached:
        return cached

    chat_token, xero_token = bind_request_context(chat_session_id, connection_id)
    try:
        if intent == "receivables":
            raw = await list_outstanding_receivables.fn(limit=5)
            data = json.loads(raw)
            if not data.get("error"):
                set_receivables(
                    connection_id,
                    total_gbp=float(data.get("total_amount_due") or 0),
                    count=int(data.get("count") or 0),
                )
            reply = _format_receivables(raw)
        elif intent == "payables":
            reply = _format_payables(await list_outstanding_payables.fn(limit=5))
        elif intent == "cash":
            reply = _format_cash(await summarize_cash_position.fn())
        elif intent == "pl":
            reply = _format_pl(await get_profit_and_loss.fn())
        elif intent == "latest_invoice":
            raw = await list_invoices.fn(invoice_type="ACCREC", status="all", limit=50)
            reply = _format_latest_invoice(raw)
        elif intent == "recent_expense":
            raw = await list_invoices.fn(invoice_type="ACCPAY", status="all", limit=50)
            reply = _format_recent_expense(raw)
        else:
            return None
    finally:
        reset_request_context(chat_token, xero_token)

    _cache_set(connection_id, intent, reply)
    return reply


async def warm_voice_cache(connection_id: str) -> None:
    """Pre-fetch receivables when a call starts so the first tool call is faster."""
    if _cache_get(connection_id, "receivables"):
        return
    chat_session_id = f"wa-{connection_id}"
    chat_token, xero_token = bind_request_context(chat_session_id, connection_id)
    try:
        reply = _format_receivables(await list_outstanding_receivables.fn(limit=5))
        _cache_set(connection_id, "receivables", reply)
    except Exception:
        pass
    finally:
        reset_request_context(chat_token, xero_token)
