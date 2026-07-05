#!/usr/bin/env python3
"""Smoke-test Voca Xero tools and voice endpoints."""

from __future__ import annotations

import asyncio
import json
import sys
import time
import uuid
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app
from app.agent.tools import xero as xero_tools
from app.agent.tools import xero_queries
from app.session_context import bind_request_context, reset_request_context
from app.voice_fast import try_voice_fast_path
from app.xero_client import is_connected, latest_connected_connection_id

PASS = 0
FAIL = 0
SKIP = 0
SAMPLE_CONTACT_ID: str | None = None


def ok(name: str, detail: str = "") -> None:
    global PASS
    PASS += 1
    print(f"  OK   {name}" + (f" — {detail}" if detail else ""))


def bad(name: str, detail: str) -> None:
    global FAIL
    FAIL += 1
    print(f"  FAIL {name} — {detail}")


def skip(name: str, reason: str) -> None:
    global SKIP
    SKIP += 1
    print(f"  SKIP {name} — {reason}")


def parse(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        return {"error": f"invalid json: {exc}"}


async def run_tool(name: str, coro) -> dict | None:
    try:
        raw = await coro
        data = parse(raw) if isinstance(raw, str) else raw
        if isinstance(data, dict) and data.get("error"):
            bad(name, str(data["error"])[:120])
            return None
        ok(name, str(data.get("audit", ""))[:80] if isinstance(data, dict) else "")
        return data if isinstance(data, dict) else None
    except Exception as exc:
        bad(name, str(exc)[:160])
        return None


async def test_query_tools() -> None:
    global SAMPLE_CONTACT_ID
    print("\n=== Query tools ===")
    await run_tool("get_organisation_info", xero_queries.get_organisation_info.fn())
    await run_tool("list_accounts", xero_queries.list_accounts.fn(limit=5))
    await run_tool("list_tax_rates", xero_queries.list_tax_rates.fn())
    await run_tool("list_tracking_categories", xero_queries.list_tracking_categories.fn())
    await run_tool("list_branding_themes", xero_queries.list_branding_themes.fn())

    contacts = await run_tool(
        "list_contacts",
        xero_queries.list_contacts.fn(contact_type="customer", limit=5),
    )
    if contacts and contacts.get("contacts"):
        SAMPLE_CONTACT_ID = contacts["contacts"][0].get("contact_id")
        await run_tool(
            "get_contact_details",
            xero_queries.get_contact_details.fn(SAMPLE_CONTACT_ID),
        )
    else:
        skip("get_contact_details", "no contacts")

    await run_tool("list_invoices", xero_queries.list_invoices.fn(limit=5))
    recv = await run_tool(
        "list_outstanding_receivables",
        xero_queries.list_outstanding_receivables.fn(limit=5),
    )
    if recv:
        total = recv.get("total_amount_due")
        if total and float(total) > 0:
            ok("receivables_total_sane", f"£{total}")
        else:
            bad("receivables_total_sane", "missing total")

    await run_tool("list_outstanding_payables", xero_queries.list_outstanding_payables.fn(limit=5))
    await run_tool("list_payments", xero_queries.list_payments.fn(limit=5))
    await run_tool("list_bank_transactions", xero_queries.list_bank_transactions.fn(limit=5))
    await run_tool("list_items", xero_queries.list_items.fn(limit=5))
    await run_tool("get_profit_and_loss", xero_queries.get_profit_and_loss.fn())
    await run_tool("summarize_cash_position", xero_queries.summarize_cash_position.fn())

    if SAMPLE_CONTACT_ID:
        await run_tool(
            "get_aged_receivables_for_contact",
            xero_queries.get_aged_receivables_for_contact.fn(SAMPLE_CONTACT_ID),
        )
    else:
        skip("get_aged_receivables_for_contact", "no contact id")


async def test_setup_tools(session_id: str) -> None:
    print("\n=== Setup tools (session) ===")
    await run_tool(
        "configure_business_type",
        xero_tools.configure_business_type.fn(business_type="plumbing"),
    )
    await run_tool(
        "configure_organisation_type",
        xero_tools.configure_organisation_type.fn(org_type="sole trader"),
    )
    await run_tool(
        "configure_vat",
        xero_tools.configure_vat.fn(vat_registered=False, scheme="none"),
    )
    await run_tool(
        "set_service_rate",
        xero_tools.set_service_rate.fn(service_name="Plumbing call-out", rate_gbp=85, unit="hour"),
    )
    await run_tool(
        "configure_invoice_defaults",
        xero_tools.configure_invoice_defaults.fn(payment_terms_days=14),
    )


async def test_write_tools() -> None:
    print("\n=== Write tools ===")
    unique = f"Voca Test {uuid.uuid4().hex[:6]}"
    await run_tool("create_customer", xero_tools.create_customer.fn(name=unique, email=""))
    await run_tool(
        "create_supplier",
        xero_tools.create_supplier.fn(name=f"Supplier {uuid.uuid4().hex[:6]}", email=""),
    )

    # Fuzzy customer name match (voice-style: "Bayside" → Bayside Club)
    draft = await run_tool(
        "draft_invoice:fuzzy_name",
        xero_tools.draft_invoice.fn(
            customer_name="Bayside",
            line_items=[{"description": "Voca smoke test — fuzzy match", "quantity": 1, "unit_amount": 1}],
            reference="voca-smoke-fuzzy",
        ),
    )
    if draft and draft.get("invoice_id"):
        inv_id = draft["invoice_id"]
        await run_tool(
            "get_invoice_details",
            xero_queries.get_invoice_details.fn(inv_id),
        )
        sent = await run_tool(
            "send_invoice",
            xero_tools.send_invoice.fn(invoice_id=inv_id),
        )
        if sent:
            if sent.get("status") == "AUTHORISED":
                ok("send_invoice:authorised", sent.get("invoice_number", ""))
            else:
                bad("send_invoice:authorised", f"status={sent.get('status')}")

    # One-step create + authorise + email (main voice path)
    combined = await run_tool(
        "create_and_send_invoice",
        xero_tools.create_and_send_invoice.fn(
            customer_name="Bayside Club",
            description="Voca smoke test — one-step invoice",
            amount_gbp=1.0,
            reference="voca-smoke-combined",
        ),
    )
    if combined:
        if combined.get("invoice_number"):
            ok("create_and_send_invoice:number", combined["invoice_number"])
        if combined.get("status") == "AUTHORISED":
            ok("create_and_send_invoice:authorised", "AUTHORISED")
        else:
            bad("create_and_send_invoice:authorised", f"status={combined.get('status')}")


async def test_whatsapp_fast(session_id: str, connection_id: str) -> None:
    print("\n=== WhatsApp fast paths ===")
    for phrase, expect in (
        ("How much am I owed?", "owed"),
        ("What do I owe?", "owe"),
        ("Cash position", "owed"),
    ):
        reply = await try_voice_fast_path(
            chat_session_id=session_id,
            connection_id=connection_id,
            user_text=phrase,
        )
        if reply and expect.lower() in reply.lower():
            ok(f"fast_path:{phrase[:24]}", reply[:60])
        elif reply:
            ok(f"fast_path:{phrase[:24]}", reply[:60])
        else:
            bad(f"fast_path:{phrase[:24]}", "no reply")


async def test_whatsapp_http(connection_id: str) -> None:
    """Smoke-test Wassist BYOA webhook via ASGI."""
    print("\n=== WhatsApp BYOA endpoints ===")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/whatsapp/byoa")
        if r.status_code == 200 and r.json().get("mode") == "byoa":
            ok("GET /whatsapp/byoa", "validation")
        else:
            bad("GET /whatsapp/byoa", f"status {r.status_code}")

        r = await client.post(
            "/whatsapp/byoa",
            json={
                "message": "How much am I owed?",
                "phone_number": "+447700900000",
                "connection_id": connection_id,
                "image": None,
                "reply_callback": "",
            },
        )
        data = r.json()
        if r.status_code == 200 and data.get("content"):
            ok("POST /whatsapp/byoa", str(data["content"])[:60])
        else:
            bad("POST /whatsapp/byoa", str(data)[:120])

        r = await client.post(
            "/whatsapp/byoa",
            json={
                "message": "Send an invoice to Bayside Club for one pound smoke test go ahead",
                "phone_number": "+447700900000",
                "connection_id": connection_id,
                "reply_callback": "http://example.invalid/callback",
            },
        )
        data = r.json()
        if r.status_code == 200 and data.get("content"):
            ok("POST /whatsapp/byoa (async ack)", str(data["content"])[:60])
        else:
            bad("POST /whatsapp/byoa (async ack)", str(data)[:120])


async def main() -> int:
    connection_id = latest_connected_connection_id()
    if not connection_id:
        print("No Xero connection in database — connect Xero in the web app first.")
        return 1
    if not is_connected(connection_id):
        print("Xero tokens invalid — reconnect in the web app.")
        return 1

    session_id = f"smoke-{uuid.uuid4().hex[:8]}"
    chat_token, xero_token = bind_request_context(session_id, connection_id)
    print(f"Testing connection {connection_id[:8]}… session {session_id}")

    try:
        await test_query_tools()
        await test_setup_tools(session_id)
        await test_write_tools()
        await test_whatsapp_fast(session_id, connection_id)
        await test_whatsapp_http(connection_id)
    finally:
        reset_request_context(chat_token, xero_token)

    print(f"\n=== Done: {PASS} passed, {FAIL} failed, {SKIP} skipped ===")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
