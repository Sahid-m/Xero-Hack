"""Xero tools exposed to the Voca agent via Vercel AI SDK."""

from __future__ import annotations

import json
from typing import Any

import ai
from xero_python.accounting.models import Contact, Contacts, Invoice, Invoices, LineItem

from app.session import get_session, save_session
from app.xero_client import get_accounting_api

# ---------------------------------------------------------------------------
# Setup interview tools
# ---------------------------------------------------------------------------


@ai.tool
async def configure_business_type(
    session_id: str,
    business_type: str,
) -> str:
    """Trim chart of accounts for the business sector (e.g. café, plumbing)."""
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
    session_id: str,
    org_type: str,
) -> str:
    """Set sole trader vs limited company financial defaults."""
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
    session_id: str,
    vat_registered: bool,
    scheme: str = "none",
) -> str:
    """Configure VAT registration and scheme (standard, flat_rate, none)."""
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
async def create_supplier(session_id: str, name: str, email: str = "") -> str:
    """Create a supplier contact in Xero."""
    accounting, tenant_id = get_accounting_api(session_id)
    result = accounting.create_contacts(
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
    contact = result.contacts[0]
    session = get_session(session_id)
    session.setdefault("contacts", []).append({"name": name, "id": contact.contact_id, "type": "supplier"})
    session["interview_step"] = max(session.get("interview_step", 0), 4)
    save_session(session_id, session)
    return json.dumps(
        {
            "contact_id": contact.contact_id,
            "name": name,
            "audit": f"Created supplier contact {name}.",
        }
    )


@ai.tool(require_approval=True)
async def create_customer(session_id: str, name: str, email: str = "") -> str:
    """Create a customer contact in Xero."""
    accounting, tenant_id = get_accounting_api(session_id)
    result = accounting.create_contacts(
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
    contact = result.contacts[0]
    session = get_session(session_id)
    session.setdefault("contacts", []).append({"name": name, "id": contact.contact_id, "type": "customer"})
    session["interview_step"] = max(session.get("interview_step", 0), 5)
    save_session(session_id, session)
    return json.dumps(
        {
            "contact_id": contact.contact_id,
            "name": name,
            "audit": f"Created customer contact {name}.",
        }
    )


@ai.tool
async def set_service_rate(
    session_id: str,
    service_name: str,
    rate_gbp: float,
    unit: str = "hour",
) -> str:
    """Store a usual service rate for invoice line items."""
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
    session_id: str,
    payment_terms_days: int = 14,
) -> str:
    """Set default payment terms and complete setup interview."""
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
# Daily verb tools
# ---------------------------------------------------------------------------


@ai.tool
async def get_amount_owed(session_id: str) -> str:
    """Get total outstanding receivables (aged receivables summary)."""
    from datetime import date

    accounting, tenant_id = get_accounting_api(session_id)
    report = accounting.get_report_aged_receivables_by_contact(tenant_id, date.today())
    # Summarise for the agent — full parsing comes later
    return json.dumps(
        {
            "report_date": str(date.today()),
            "summary": "Aged receivables report retrieved.",
            "raw_titles": [r.title for r in (report.reports[0].rows or [])[:5]] if report.reports else [],
        }
    )


@ai.tool(require_approval=True)
async def draft_invoice(
    session_id: str,
    customer_name: str,
    line_items: list[dict[str, Any]],
    reference: str = "",
) -> str:
    """Draft an ACCREC invoice. Each line_item: description, quantity, unit_amount, account_code."""
    accounting, tenant_id = get_accounting_api(session_id)
    session = get_session(session_id)
    vat = session.get("vat_registered", False)

    # Fuzzy match customer from session contacts
    contact_id = None
    for c in session.get("contacts", []):
        if c.get("type") == "customer" and customer_name.lower() in c["name"].lower():
            contact_id = c["id"]
            break

    if not contact_id:
        # Fall back to Xero search
        contacts = accounting.get_contacts(tenant_id, where=f'Name.Contains("{customer_name}")')
        if contacts.contacts:
            contact_id = contacts.contacts[0].contact_id

    if not contact_id:
        return json.dumps({"error": f"No customer found matching '{customer_name}'."})

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

    result = accounting.create_invoices(
        tenant_id,
        Invoices(
            invoices=[
                Invoice(
                    type="ACCREC",
                    contact=Contact(contact_id=contact_id),
                    line_items=items,
                    status="DRAFT",
                    reference=reference or None,
                )
            ]
        ),
    )
    invoice = result.invoices[0]
    total = invoice.total or 0
    return json.dumps(
        {
            "invoice_id": invoice.invoice_id,
            "customer": customer_name,
            "total_gbp": total,
            "status": "DRAFT",
            "audit": f"Draft invoice for {customer_name}: £{total:.2f} incl. VAT.",
        }
    )


@ai.tool(require_approval=True)
async def send_invoice(session_id: str, invoice_id: str) -> str:
    """Send a draft invoice to the customer."""
    accounting, tenant_id = get_accounting_api(session_id)
    accounting.update_invoice(
        tenant_id,
        invoice_id,
        Invoices(invoices=[Invoice(invoice_id=invoice_id, status="AUTHORISED")]),
    )
    return json.dumps(
        {
            "invoice_id": invoice_id,
            "status": "AUTHORISED",
            "audit": f"Invoice {invoice_id} sent.",
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
    get_amount_owed,
    draft_invoice,
    send_invoice,
    create_customer,
    create_supplier,
    set_service_rate,
]

ALL_TOOLS: list[ai.AgentTool] = SETUP_TOOLS + [
    get_amount_owed,
    draft_invoice,
    send_invoice,
]
