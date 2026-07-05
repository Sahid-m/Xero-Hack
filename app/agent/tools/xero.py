"""Xero tools exposed to the Voca agent via Vercel AI SDK."""

from __future__ import annotations

import asyncio
import json
from datetime import date, timedelta
from typing import Any

import ai
from xero_python.accounting.models import (
    Account,
    Contact,
    Contacts,
    Invoice,
    Invoices,
    LineItem,
    Payment,
    Payments,
    RequestEmpty,
)

from app.session import get_session, save_session
from app.session_context import chat_session_id, xero_connection_id
from app.xero_client import get_accounting_api
from app.agent.tools.xero_queries import QUERY_TOOLS

_GBP_ALIASES = {"gbp", "£", "pound", "pounds", "sterling", "gb pound", "gbpound"}


def _is_gbp(currency: str) -> bool:
    return currency.strip().lower() in _GBP_ALIASES


def _currency_mismatch_response(currency: str, amount: float, *, action: str) -> str:
    """This Xero org is GBP-only — refuse in code rather than trust the model's
    own judgment on whether to ask first (require_approval hooks are
    auto-granted for WhatsApp/voice turns, so this is the actual enforcement
    point, not just a prompt instruction)."""
    return _json(
        {
            "currency_mismatch": True,
            "stated_currency": currency,
            "amount": amount,
            "error": f"Amount was given in {currency}, not GBP.",
            "audit": (
                f"You said {currency} {amount:,.2f} — this Xero org only handles GBP and I have no "
                f"live exchange rate to convert accurately. Please confirm the amount in pounds "
                f"before I {action}."
            ),
        }
    )


def _json(data: dict[str, Any]) -> str:
    return json.dumps(data, default=str)


def _resolve_customer_id(accounting: Any, tenant_id: str, customer_name: str) -> str | None:
    """Fuzzy match a customer contact in Xero."""
    term = customer_name.strip()
    if not term:
        return None

    session = get_session(chat_session_id())
    for c in session.get("contacts", []):
        if c.get("type") == "customer" and term.lower() in str(c.get("name", "")).lower():
            return c.get("id")

    safe = term.replace('"', "")
    result = accounting.get_contacts(
        tenant_id,
        where=f'Name.Contains("{safe}")',
        page=1,
    )
    if result.contacts:
        return result.contacts[0].contact_id

    # No first-word fallback: matching e.g. "East" against any contact
    # containing "East" (like an unrelated "Eastside Club") risks silently
    # attaching a transaction to the wrong contact. Better to report not-found
    # and let the caller confirm creating a new one.
    return None


def _remember_customer(session_id: str, name: str, contact_id: str) -> None:
    session = get_session(session_id)
    session.setdefault("contacts", []).append(
        {"name": name, "id": contact_id, "type": "customer"}
    )
    save_session(session_id, session)


async def _create_customer_contact(
    accounting: Any,
    tenant_id: str,
    name: str,
    email: str = "",
) -> str:
    """Create a customer in Xero and return contact_id."""
    session_id = chat_session_id()
    result = await asyncio.to_thread(
        accounting.create_contacts,
        tenant_id,
        Contacts(
            contacts=[
                Contact(
                    name=name,
                    email_address=email or None,
                    is_customer=True,
                )
            ]
        ),
    )
    contact_id = result.contacts[0].contact_id
    _remember_customer(session_id, name, contact_id)
    return contact_id


def _save_pending_invoice(
    customer_name: str,
    amount_gbp: float,
    description: str,
) -> None:
    session_id = chat_session_id()
    session = get_session(session_id)
    session["pending_invoice"] = {
        "customer_name": customer_name,
        "amount_gbp": amount_gbp,
        "description": description,
    }
    save_session(session_id, session)


def _clear_pending_invoice() -> None:
    session_id = chat_session_id()
    session = get_session(session_id)
    session.pop("pending_invoice", None)
    save_session(session_id, session)


def _customer_not_found_response(
    customer_name: str,
    *,
    amount_gbp: float | None = None,
    description: str | None = None,
) -> str:
    if amount_gbp is not None:
        _save_pending_invoice(customer_name, amount_gbp, description or "Services")
    spoken = f"I can't find {customer_name} in Xero."
    if amount_gbp is not None:
        spoken += f" Shall I create them as a new customer and send the invoice for £{amount_gbp:.2f}?"
    else:
        spoken += " Shall I create them as a new customer?"
    return _json(
        {
            "customer_not_found": True,
            "customer_name": customer_name,
            "error": f"No customer found matching '{customer_name}'.",
            "audit": spoken,
        }
    )


def _resolve_supplier_id(accounting: Any, tenant_id: str, supplier_name: str) -> str | None:
    """Fuzzy match a supplier contact in Xero."""
    term = supplier_name.strip()
    if not term:
        return None

    session = get_session(chat_session_id())
    for c in session.get("contacts", []):
        if c.get("type") == "supplier" and term.lower() in str(c.get("name", "")).lower():
            return c.get("id")

    safe = term.replace('"', "")
    result = accounting.get_contacts(
        tenant_id,
        where=f'Name.Contains("{safe}")',
        page=1,
    )
    if result.contacts:
        for contact in result.contacts:
            if contact.is_supplier:
                return contact.contact_id
        return result.contacts[0].contact_id

    # No first-word fallback: matching e.g. "East" against any contact
    # containing "East" (like an unrelated "Eastside Club") risks silently
    # attaching a transaction to the wrong contact. Better to report not-found
    # and let the caller confirm creating a new one.
    return None


async def _create_supplier_contact(
    accounting: Any,
    tenant_id: str,
    name: str,
    email: str = "",
) -> str:
    session_id = chat_session_id()
    result = await asyncio.to_thread(
        accounting.create_contacts,
        tenant_id,
        Contacts(
            contacts=[
                Contact(
                    name=name,
                    email_address=email or None,
                    is_supplier=True,
                )
            ]
        ),
    )
    contact_id = result.contacts[0].contact_id
    session = get_session(session_id)
    session.setdefault("contacts", []).append(
        {"name": name, "id": contact_id, "type": "supplier"}
    )
    save_session(session_id, session)
    return contact_id


def _save_pending_bill(
    supplier_name: str,
    amount_gbp: float,
    description: str,
) -> None:
    session_id = chat_session_id()
    session = get_session(session_id)
    session["pending_bill"] = {
        "supplier_name": supplier_name,
        "amount_gbp": amount_gbp,
        "description": description,
    }
    save_session(session_id, session)


def _supplier_not_found_response(
    supplier_name: str,
    *,
    amount_gbp: float | None = None,
    description: str | None = None,
) -> str:
    if amount_gbp is not None:
        _save_pending_bill(supplier_name, amount_gbp, description or "Expense")
    spoken = f"I can't find {supplier_name} as a supplier in Xero."
    if amount_gbp is not None:
        spoken += f" Shall I add them and record the bill for £{amount_gbp:.2f}?"
    else:
        spoken += " Shall I add them as a new supplier?"
    return _json(
        {
            "supplier_not_found": True,
            "supplier_name": supplier_name,
            "error": f"No supplier found matching '{supplier_name}'.",
            "audit": spoken,
        }
    )


# ---------------------------------------------------------------------------
# Setup interview tools
# ---------------------------------------------------------------------------


@ai.tool
async def configure_business_type(
    business_type: str,
) -> str:
    """Trim chart of accounts for the business sector (e.g. café, plumbing)."""
    session_id = chat_session_id()
    session = get_session(session_id)
    session["business_type"] = business_type
    session["interview_step"] = max(session.get("interview_step", 0), 1)
    save_session(session_id, session)
    # TODO: archive irrelevant accounts, add sector COGS codes via Xero API
    return json.dumps(
        {
            "status": "configured",
            "business_type": business_type,
            "audit": f"Chart of accounts trimmed for {business_type}.",
        }
    )


@ai.tool
async def configure_organisation_type(
    org_type: str,
) -> str:
    """Set sole trader vs limited company financial defaults."""
    session_id = chat_session_id()
    session = get_session(session_id)
    session["org_type"] = org_type
    session["interview_step"] = max(session.get("interview_step", 0), 2)
    save_session(session_id, session)
    return json.dumps(
        {
            "status": "configured",
            "org_type": org_type,
            "audit": f"Organisation set as {org_type}.",
        }
    )


@ai.tool
async def configure_vat(
    vat_registered: bool,
    scheme: str = "none",
) -> str:
    """Configure VAT registration and scheme (standard, flat_rate, none)."""
    session_id = chat_session_id()
    session = get_session(session_id)
    session["vat_registered"] = vat_registered
    session["vat_scheme"] = scheme
    session["interview_step"] = max(session.get("interview_step", 0), 3)
    save_session(session_id, session)
    if vat_registered:
        audit = f"VAT enabled — {scheme} scheme, 20% on sales."
    else:
        audit = "Not VAT registered — no VAT on invoices."
    return json.dumps({"status": "configured", "vat_registered": vat_registered, "audit": audit})


@ai.tool(require_approval=True)
async def create_supplier(name: str, email: str = "") -> str:
    """Create a supplier contact in Xero."""
    accounting, tenant_id = get_accounting_api(xero_connection_id())
    contact_id = await _create_supplier_contact(accounting, tenant_id, name, email)
    session_id = chat_session_id()
    session = get_session(session_id)
    session["interview_step"] = max(session.get("interview_step", 0), 4)
    save_session(session_id, session)
    return json.dumps(
        {
            "contact_id": contact_id,
            "name": name,
            "audit": f"Created supplier contact {name}.",
        }
    )


@ai.tool(require_approval=True)
async def create_customer(name: str, email: str = "") -> str:
    """Create a customer contact in Xero."""
    accounting, tenant_id = get_accounting_api(xero_connection_id())
    contact_id = await _create_customer_contact(accounting, tenant_id, name, email)
    session_id = chat_session_id()
    session = get_session(session_id)
    session["interview_step"] = max(session.get("interview_step", 0), 5)
    save_session(session_id, session)
    return json.dumps(
        {
            "contact_id": contact_id,
            "name": name,
            "audit": f"Created customer contact {name}.",
        }
    )


@ai.tool
async def set_service_rate(
    service_name: str,
    rate_gbp: float,
    unit: str = "hour",
) -> str:
    """Store a usual service rate for invoice line items."""
    session_id = chat_session_id()
    session = get_session(session_id)
    rates: dict[str, Any] = session.setdefault("rates", {})
    rates[service_name.lower()] = {"rate_gbp": rate_gbp, "unit": unit}
    session["interview_step"] = max(session.get("interview_step", 0), 5)
    save_session(session_id, session)
    return json.dumps(
        {
            "service": service_name,
            "rate_gbp": rate_gbp,
            "audit": f"Stored rate: {service_name} at £{rate_gbp:.2f} per {unit}.",
        }
    )


@ai.tool
async def configure_invoice_defaults(
    payment_terms_days: int = 14,
) -> str:
    """Set default payment terms and complete setup interview."""
    session_id = chat_session_id()
    session = get_session(session_id)
    session["payment_terms_days"] = payment_terms_days
    session["interview_step"] = 6
    session["mode"] = "operations"
    save_session(session_id, session)
    return json.dumps(
        {
            "status": "complete",
            "payment_terms_days": payment_terms_days,
            "audit": f"Invoice terms set to {payment_terms_days} days. Setup complete.",
        }
    )


# ---------------------------------------------------------------------------
# Write tools
# ---------------------------------------------------------------------------


@ai.tool(require_approval=True)
async def draft_invoice(
    customer_name: str,
    line_items: list[dict[str, Any]],
    currency: str,
    reference: str = "",
    create_if_missing: bool = False,
) -> str:
    """
    Draft an ACCREC invoice. Each line_item: description, quantity, unit_amount, account_code.
    currency: the currency the USER actually said (e.g. "GBP", "pounds", "USD", "dollars") —
    state it exactly as heard, do not assume GBP. This org is GBP-only; a non-GBP currency
    is refused here rather than silently converted, since there's no live exchange rate.
    """
    if not _is_gbp(currency):
        total_hint = sum(
            float(item.get("quantity", 1)) * float(item.get("unit_amount", 0))
            for item in line_items
        )
        return _currency_mismatch_response(currency, total_hint, action="draft this invoice")

    accounting, tenant_id = get_accounting_api(xero_connection_id())
    session = get_session(chat_session_id())
    vat = session.get("vat_registered", False)

    contact_id = await asyncio.to_thread(_resolve_customer_id, accounting, tenant_id, customer_name)
    created_new_customer = False
    if not contact_id and create_if_missing:
        contact_id = await _create_customer_contact(accounting, tenant_id, customer_name)
        created_new_customer = True
    if not contact_id:
        total_hint = sum(
            float(item.get("quantity", 1)) * float(item.get("unit_amount", 0))
            for item in line_items
        )
        desc = line_items[0].get("description", "Services") if line_items else "Services"
        return _customer_not_found_response(
            customer_name,
            amount_gbp=total_hint or None,
            description=str(desc),
        )

    terms_days = int(session.get("payment_terms_days", 14))
    invoice_date = date.today()
    due_date = invoice_date + timedelta(days=terms_days)

    items = [
        LineItem(
            description=item["description"],
            quantity=item.get("quantity", 1),
            unit_amount=item["unit_amount"],
            account_code=item.get("account_code", "200"),
            tax_type="OUTPUT2" if vat else "NONE",
        )
        for item in line_items
    ]

    result = await asyncio.to_thread(
        accounting.create_invoices,
        tenant_id,
        Invoices(
            invoices=[
                Invoice(
                    type="ACCREC",
                    contact=Contact(contact_id=contact_id),
                    line_items=items,
                    status="DRAFT",
                    date=invoice_date,
                    due_date=due_date,
                    reference=reference or None,
                )
            ]
        ),
    )
    invoice = result.invoices[0]
    total = float(invoice.total or 0)
    return _json(
        {
            "invoice_id": invoice.invoice_id,
            "invoice_number": invoice.invoice_number,
            "customer": customer_name,
            "total_gbp": total,
            "status": "DRAFT",
            "created_new_customer": created_new_customer,
            "audit": (
                f"Draft invoice {invoice.invoice_number} for {customer_name}: "
                f"£{total:.2f}."
            ),
        }
    )


@ai.tool(require_approval=True)
async def send_invoice(invoice_id: str) -> str:
    """Authorise and email a draft sales invoice to the customer."""
    accounting, tenant_id = get_accounting_api(xero_connection_id())
    existing = await asyncio.to_thread(accounting.get_invoice, tenant_id, invoice_id)
    inv = existing.invoices[0] if existing.invoices else None
    if not inv:
        return _json({"error": f"Invoice {invoice_id} not found."})

    await asyncio.to_thread(
        accounting.update_invoice,
        tenant_id,
        invoice_id,
        Invoices(
            invoices=[
                Invoice(
                    invoice_id=invoice_id,
                    status="AUTHORISED",
                    due_date=inv.due_date,
                )
            ]
        ),
    )
    emailed = False
    try:
        await asyncio.to_thread(accounting.email_invoice, tenant_id, invoice_id, RequestEmpty())
        emailed = True
    except Exception:
        pass

    fetched = await asyncio.to_thread(accounting.get_invoice, tenant_id, invoice_id)
    invoice = fetched.invoices[0] if fetched.invoices else None
    number = invoice.invoice_number if invoice else invoice_id
    customer = invoice.contact.name if invoice and invoice.contact else "the customer"
    total = float(invoice.total or 0) if invoice else 0.0
    verb = "Sent" if emailed else "Approved"
    return _json(
        {
            "invoice_id": invoice_id,
            "invoice_number": number,
            "customer": customer,
            "total_gbp": total,
            "status": "AUTHORISED",
            "emailed": emailed,
            "audit": (
                f"{verb} invoice {number} to {customer} for £{total:.2f}."
            ),
        }
    )


@ai.tool(require_approval=True)
async def create_and_send_invoice(
    customer_name: str,
    description: str,
    amount_gbp: float,
    currency: str,
    quantity: float = 1,
    reference: str = "",
    create_if_missing: bool = False,
) -> str:
    """
    Create, authorise, and email a sales invoice in one step.
    Use for voice: customer_name, plain-English description, amount in pounds.
    currency: the currency the USER actually said (e.g. "GBP", "pounds", "USD", "dollars") —
    state it exactly as heard, do not assume GBP.
    Set create_if_missing=true after the caller confirms a new customer should be created.
    """
    draft_raw = await draft_invoice.fn(
        customer_name=customer_name,
        line_items=[
            {
                "description": description,
                "quantity": quantity,
                "unit_amount": amount_gbp,
            }
        ],
        currency=currency,
        reference=reference,
        create_if_missing=create_if_missing,
    )
    draft = json.loads(draft_raw)
    if draft.get("customer_not_found"):
        return draft_raw
    if draft.get("error"):
        return draft_raw

    invoice_id = draft["invoice_id"]
    sent_raw = await send_invoice.fn(invoice_id=invoice_id)
    sent = json.loads(sent_raw)
    created_note = "Created customer and sent" if draft.get("created_new_customer") else "Created and sent"
    return _json(
        {
            **sent,
            "audit": (
                f"{created_note} invoice {sent.get('invoice_number', invoice_id)} "
                f"to {sent.get('customer', customer_name)} for "
                f"£{float(sent.get('total_gbp', draft.get('total_gbp', 0))):.2f}."
            ),
        }
    )


@ai.tool(require_approval=True)
async def record_supplier_bill(
    supplier_name: str,
    description: str,
    amount_gbp: float,
    quantity: float = 1,
    reference: str = "",
    create_if_missing: bool = False,
    currency: str = "GBP",
) -> str:
    """
    Record a supplier bill / expense (ACCPAY) in Xero.
    Use when the user got a bill or spent money with a supplier.
    Set create_if_missing=true after they confirm a new supplier.
    currency: only pass this if the USER stated a non-GBP currency (e.g. "USD", "dollars") —
    defaults to GBP for the receipt-OCR flow, which already converts to GBP itself.
    """
    if not _is_gbp(currency):
        return _currency_mismatch_response(currency, amount_gbp, action="record this bill")

    accounting, tenant_id = get_accounting_api(xero_connection_id())
    session = get_session(chat_session_id())
    vat = session.get("vat_registered", False)

    contact_id = await asyncio.to_thread(_resolve_supplier_id, accounting, tenant_id, supplier_name)
    created_new_supplier = False
    if not contact_id and create_if_missing:
        contact_id = await _create_supplier_contact(accounting, tenant_id, supplier_name)
        created_new_supplier = True
    if not contact_id:
        return _supplier_not_found_response(
            supplier_name,
            amount_gbp=amount_gbp,
            description=description,
        )

    terms_days = int(session.get("payment_terms_days", 14))
    bill_date = date.today()
    due_date = bill_date + timedelta(days=terms_days)

    items = [
        LineItem(
            description=description,
            quantity=quantity,
            unit_amount=amount_gbp,
            account_code="400",
            tax_type="INPUT2" if vat else "NONE",
        )
    ]

    draft = await asyncio.to_thread(
        accounting.create_invoices,
        tenant_id,
        Invoices(
            invoices=[
                Invoice(
                    type="ACCPAY",
                    contact=Contact(contact_id=contact_id),
                    line_items=items,
                    status="DRAFT",
                    date=bill_date,
                    due_date=due_date,
                    reference=reference or None,
                )
            ]
        ),
    )
    invoice = draft.invoices[0]
    invoice_id = invoice.invoice_id

    await asyncio.to_thread(
        accounting.update_invoice,
        tenant_id,
        invoice_id,
        Invoices(
            invoices=[
                Invoice(
                    invoice_id=invoice_id,
                    status="AUTHORISED",
                    due_date=due_date,
                )
            ]
        ),
    )

    fetched = await asyncio.to_thread(accounting.get_invoice, tenant_id, invoice_id)
    bill = fetched.invoices[0] if fetched.invoices else invoice
    number = bill.invoice_number or invoice_id
    supplier = bill.contact.name if bill.contact else supplier_name
    total = float(bill.total or 0)
    created = "Added supplier and recorded" if created_new_supplier else "Recorded"
    return _json(
        {
            "invoice_id": invoice_id,
            "bill_number": number,
            "supplier": supplier,
            "total_gbp": total,
            "status": "AUTHORISED",
            "audit": f"{created} bill {number} from {supplier} for £{total:.2f} — {description}.",
        }
    )


@ai.tool(require_approval=True)
async def send_payment_reminder(
    customer_name: str,
    invoice_number: str = "",
) -> str:
    """
    Chase payment — email a payment reminder for an overdue sales invoice.
    Uses Xero to resend the invoice to the customer (standard UK chase).
    If invoice_number omitted, picks the largest overdue invoice for that customer.
    """
    accounting, tenant_id = get_accounting_api(xero_connection_id())
    contact_id = await asyncio.to_thread(_resolve_customer_id, accounting, tenant_id, customer_name)
    if not contact_id:
        return _json({"error": f"No customer found matching '{customer_name}'."})

    result = await asyncio.to_thread(
        accounting.get_invoices,
        tenant_id,
        where=f'Type=="ACCREC" && AmountDue>0 && Contact.ContactID==guid("{contact_id}")',
        statuses=["AUTHORISED"],
        page=1,
        summary_only=True,
    )
    invoices = list(result.invoices or [])
    if not invoices:
        return _json({"error": f"No outstanding invoices for {customer_name}."})

    today = date.today()
    overdue = [
        inv
        for inv in invoices
        if inv.due_date and _parse_invoice_date(inv.due_date) < today
    ]
    pool = overdue or invoices

    if invoice_number.strip():
        match = next(
            (inv for inv in pool if inv.invoice_number == invoice_number.strip()),
            None,
        )
        if not match:
            return _json({"error": f"Invoice {invoice_number} not found for {customer_name}."})
        target = match
    else:
        target = max(pool, key=lambda inv: float(inv.amount_due or 0))

    invoice_id = target.invoice_id
    emailed = False
    try:
        await asyncio.to_thread(accounting.email_invoice, tenant_id, invoice_id, RequestEmpty())
        emailed = True
    except Exception as exc:
        return _json(
            {
                "error": f"Could not send reminder: {exc}",
                "audit": (
                    f"I found invoice {target.invoice_number} for {customer_name} "
                    "but couldn't email the reminder — they may not have an email in Xero."
                ),
            }
        )

    due = _parse_invoice_date(target.due_date)
    days = (today - due).days if due else 0
    amount = float(target.amount_due or 0)
    return _json(
        {
            "invoice_id": invoice_id,
            "invoice_number": target.invoice_number,
            "customer": customer_name,
            "amount_due_gbp": amount,
            "days_overdue": days,
            "emailed": emailed,
            "audit": (
                f"Sent a payment reminder to {customer_name} for invoice "
                f"{target.invoice_number} — £{amount:.2f}, {days} days overdue."
            ),
        }
    )


def _parse_invoice_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value[:10])
    return date.today()


@ai.tool(require_approval=True)
async def reconcile_invoice_payment(invoice_id: str, bank_transaction_id: str) -> str:
    """
    Reconcile: record a payment against invoice_id using the account and date from
    bank_transaction_id, closing out both. Use after find_reconciliation_matches
    identifies a pairing and the user confirms it.
    """
    accounting, tenant_id = get_accounting_api(xero_connection_id())

    invoice_result, txn_result = await asyncio.gather(
        asyncio.to_thread(accounting.get_invoice, tenant_id, invoice_id),
        asyncio.to_thread(accounting.get_bank_transaction, tenant_id, bank_transaction_id),
    )
    invoice = invoice_result.invoices[0] if invoice_result.invoices else None
    txn = txn_result.bank_transactions[0] if txn_result.bank_transactions else None
    if not invoice:
        return _json({"error": f"Invoice {invoice_id} not found."})
    if not txn:
        return _json({"error": f"Bank transaction {bank_transaction_id} not found."})
    if not txn.bank_account or not txn.bank_account.code:
        return _json({"error": "That bank transaction has no linked bank account code."})

    amount = min(float(txn.total or 0), float(invoice.amount_due or 0))
    result = await asyncio.to_thread(
        accounting.create_payments,
        tenant_id,
        Payments(
            payments=[
                Payment(
                    invoice=Invoice(invoice_id=invoice_id),
                    account=Account(code=txn.bank_account.code),
                    date=txn.date,
                    amount=amount,
                    reference="voca-reconciliation",
                )
            ]
        ),
    )
    if not result.payments:
        return _json({"error": "Xero rejected the payment — check the invoice isn't already paid."})

    contact = invoice.contact.name if invoice.contact else "the contact"
    number = invoice.invoice_number or invoice_id
    return _json(
        {
            "invoice_id": invoice_id,
            "invoice_number": number,
            "bank_transaction_id": bank_transaction_id,
            "contact": contact,
            "amount_gbp": amount,
            "audit": (
                f"Reconciled — matched £{amount:.2f} bank transaction to invoice "
                f"{number} ({contact}). Both are now settled."
            ),
        }
    )


SETUP_TOOLS: list[ai.AgentTool] = [
    configure_business_type,
    configure_organisation_type,
    configure_vat,
    create_supplier,
    create_customer,
    set_service_rate,
    configure_invoice_defaults,
]

OPERATIONS_TOOLS: list[ai.AgentTool] = [
    *QUERY_TOOLS,
    draft_invoice,
    send_invoice,
    create_customer,
    create_supplier,
    set_service_rate,
    reconcile_invoice_payment,
]

ALL_TOOLS: list[ai.AgentTool] = SETUP_TOOLS + QUERY_TOOLS + [
    draft_invoice,
    send_invoice,
    create_and_send_invoice,
    record_supplier_bill,
    send_payment_reminder,
    reconcile_invoice_payment,
]
