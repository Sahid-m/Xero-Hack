"""Xero webhooks — proactive WhatsApp notifications when something changes in Xero.

Docs: https://developer.xero.com/documentation/webhooks/overview

WhatsApp only allows pushing a message without the user texting first within 24h
of their last message (Meta's customer-service window) — there is no true anytime
cold-push without a pre-approved message template. So this only notifies if the
linked phone messaged Voca recently; otherwise the event is just logged.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
from typing import Any

from app.config import get_settings
from app.session import get_session, save_session
from app.wassist import get_recent_reply_callback, send_byoa_reply
from app.xero_client import connection_id_for_tenant, get_accounting_api

logger = logging.getLogger(__name__)


def verify_signature(raw_body: bytes, signature: str, webhook_key: str) -> bool:
    if not webhook_key or not signature:
        return False
    computed = base64.b64encode(hmac.new(webhook_key.encode(), raw_body, hashlib.sha256).digest()).decode()
    return hmac.compare_digest(computed, signature)


def _already_notified(connection_id: str, notify_key: str) -> bool:
    session = get_session(connection_id)
    return notify_key in session.get("xero_event_notified", [])


def _mark_notified(connection_id: str, notify_key: str) -> None:
    session = get_session(connection_id)
    notified: list[str] = session.get("xero_event_notified") or []
    notified.append(notify_key)
    session["xero_event_notified"] = notified[-100:]  # cap unbounded growth
    save_session(connection_id, session)


async def handle_event(event: dict[str, Any]) -> None:
    """Process one Xero webhook event — fetch the changed resource, decide
    whether it's notification-worthy, and push via WhatsApp if possible."""
    if event.get("eventCategory") != "INVOICE":
        return

    tenant_id = event.get("tenantId")
    resource_id = event.get("resourceId")
    event_type = event.get("eventType")  # "CREATE" or "UPDATE"
    if not tenant_id or not resource_id:
        return

    connection_id = connection_id_for_tenant(tenant_id)
    if not connection_id:
        logger.info("Xero webhook for unknown tenant %s — no linked connection", tenant_id[:8])
        return

    try:
        accounting, api_tenant_id = get_accounting_api(connection_id)
        result = await asyncio.to_thread(accounting.get_invoice, api_tenant_id, resource_id)
    except Exception:
        logger.exception("Failed to fetch invoice %s for Xero webhook event", resource_id)
        return

    invoice = result.invoices[0] if result.invoices else None
    if not invoice:
        return

    contact = invoice.contact.name if invoice.contact else "someone"
    total = float(invoice.total or 0)
    message: str | None = None
    notify_key: str | None = None

    if event_type == "CREATE" and invoice.type == "ACCPAY":
        notify_key = f"new_bill:{resource_id}"
        message = (
            f"New bill just landed in Xero — {contact}, £{total:.2f} "
            f"({invoice.invoice_number or resource_id}). Want me to check it or "
            f"look for a matching bank transaction to reconcile?"
        )
    elif invoice.status == "PAID":
        notify_key = f"paid:{resource_id}"
        kind = "You were paid by" if invoice.type == "ACCREC" else "You paid"
        message = (
            f"{kind} {contact} — invoice {invoice.invoice_number or resource_id} "
            f"for £{total:.2f} is now settled in Xero."
        )

    if not message or not notify_key:
        return
    if _already_notified(connection_id, notify_key):
        return

    reply_callback = get_recent_reply_callback(connection_id)
    if not reply_callback:
        logger.info(
            "Xero event %s for connection %s — no recent WhatsApp session to notify",
            notify_key,
            connection_id[:8],
        )
        _mark_notified(connection_id, notify_key)  # don't retry — same event repeats on every save
        return

    await send_byoa_reply(reply_callback, message)
    _mark_notified(connection_id, notify_key)


async def handle_webhook_payload(raw_body: bytes) -> None:
    payload = json.loads(raw_body)
    for event in payload.get("events", []):
        try:
            await handle_event(event)
        except Exception:
            logger.exception("Failed to handle Xero webhook event: %r", event)
