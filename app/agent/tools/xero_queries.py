"""Read-only Xero query tools for the Voca agent."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Literal

import ai

from app.agent.tools.xero_serialize import (
    parse_xero_report,
    slim_account,
    slim_bank_transaction,
    slim_contact,
    slim_invoice,
    slim_item,
    slim_payment,
    tool_result,
)
from app.xero_client import get_accounting_api

InvoiceType = Literal["ACCREC", "ACCPAY", "all"]
InvoiceStatus = Literal["DRAFT", "SUBMITTED", "AUTHORISED", "PAID", "VOIDED", "all"]
ContactType = Literal["all", "customer", "supplier"]


def _clamp(limit: int, cap: int = 50) -> int:
    return max(1, min(limit, cap))


# ---------------------------------------------------------------------------
# Organisation & settings
# ---------------------------------------------------------------------------


@ai.tool
async def get_organisation_info(session_id: str) -> str:
    """Get the connected Xero organisation name, legal name, currency, and country."""
    accounting, tenant_id = get_accounting_api(session_id)
    result = accounting.get_organisations(tenant_id)
    if not result.organisations:
        return tool_result(error="No organisation found for this connection.")
    org = result.organisations[0]
    return tool_result(
        name=org.name,
        legal_name=org.legal_name,
        organisation_type=org.organisation_type,
        country_code=org.country_code,
        base_currency=org.base_currency,
        financial_year_end_day=org.financial_year_end_day,
        financial_year_end_month=org.financial_year_end_month,
        audit=f"Connected to {org.name}.",
    )


@ai.tool
async def list_accounts(
    session_id: str,
    search: str = "",
    limit: int = 50,
) -> str:
    """List chart of accounts (codes, names, types). Optional search filters by name or code."""
    accounting, tenant_id = get_accounting_api(session_id)
    where = None
    if search.strip():
        term = search.strip().replace('"', "")
        where = f'Name.Contains("{term}") || Code.Contains("{term}")'
    result = accounting.get_accounts(tenant_id, where=where)
    accounts = [slim_account(a) for a in (result.accounts or [])[: _clamp(limit)]]
    return tool_result(count=len(accounts), accounts=accounts, audit=f"Found {len(accounts)} accounts.")


@ai.tool
async def list_tax_rates(session_id: str) -> str:
    """List tax rates configured in Xero (VAT types and percentages)."""
    accounting, tenant_id = get_accounting_api(session_id)
    result = accounting.get_tax_rates(tenant_id)
    rates = [
        {
            "name": r.name,
            "tax_type": r.tax_type,
            "effective_rate": r.effective_rate,
            "status": r.status,
        }
        for r in (result.tax_rates or [])
    ]
    return tool_result(count=len(rates), tax_rates=rates, audit=f"Found {len(rates)} tax rates.")


@ai.tool
async def list_tracking_categories(session_id: str) -> str:
    """List tracking categories and their options (departments, projects, etc.)."""
    accounting, tenant_id = get_accounting_api(session_id)
    result = accounting.get_tracking_categories(tenant_id)
    categories = [
        {
            "name": c.name,
            "status": c.status,
            "options": [o.name for o in (c.options or [])],
        }
        for c in (result.tracking_categories or [])
    ]
    return tool_result(
        count=len(categories),
        tracking_categories=categories,
        audit=f"Found {len(categories)} tracking categories.",
    )


@ai.tool
async def list_branding_themes(session_id: str) -> str:
    """List invoice branding themes (logo, colours, payment terms)."""
    accounting, tenant_id = get_accounting_api(session_id)
    result = accounting.get_branding_themes(tenant_id)
    themes = [
        {
            "branding_theme_id": t.branding_theme_id,
            "name": t.name,
            "sort_order": t.sort_order,
            "created_date": t.created_date_utc,
        }
        for t in (result.branding_themes or [])
    ]
    return tool_result(count=len(themes), branding_themes=themes, audit=f"Found {len(themes)} themes.")


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------


@ai.tool
async def list_contacts(
    session_id: str,
    contact_type: ContactType = "all",
    search: str = "",
    limit: int = 25,
) -> str:
    """List contacts. Filter by customer/supplier and optional name search."""
    accounting, tenant_id = get_accounting_api(session_id)
    where = None
    if contact_type == "customer":
        where = "IsCustomer==true"
    elif contact_type == "supplier":
        where = "IsSupplier==true"

    result = accounting.get_contacts(
        tenant_id,
        where=where,
        search_term=search.strip() or None,
        page=1,
    )
    contacts = [slim_contact(c) for c in (result.contacts or [])[: _clamp(limit)]]
    return tool_result(count=len(contacts), contacts=contacts, audit=f"Found {len(contacts)} contacts.")


@ai.tool
async def get_contact_details(session_id: str, contact_id: str) -> str:
    """Get full details for one contact by Xero contact_id."""
    accounting, tenant_id = get_accounting_api(session_id)
    result = accounting.get_contact(tenant_id, contact_id)
    if not result.contacts:
        return tool_result(error=f"No contact found for id {contact_id}.")
    return tool_result(contact=slim_contact(result.contacts[0], detailed=True))


# ---------------------------------------------------------------------------
# Invoices & bills
# ---------------------------------------------------------------------------


@ai.tool
async def list_invoices(
    session_id: str,
    invoice_type: InvoiceType = "all",
    status: InvoiceStatus = "all",
    contact_name: str = "",
    limit: int = 20,
) -> str:
    """List sales invoices (ACCREC) or bills (ACCPAY). Filter by status and contact name."""
    accounting, tenant_id = get_accounting_api(session_id)
    clauses: list[str] = []
    if invoice_type != "all":
        clauses.append(f'Type=="{invoice_type}"')
    if contact_name.strip():
        term = contact_name.strip().replace('"', "")
        clauses.append(f'Contact.Name.Contains("{term}")')
    where = " && ".join(clauses) if clauses else None
    statuses = None if status == "all" else [status]

    result = accounting.get_invoices(
        tenant_id,
        where=where,
        statuses=statuses,
        page=1,
        summary_only=True,
    )
    invoices = [slim_invoice(inv) for inv in (result.invoices or [])[: _clamp(limit)]]
    return tool_result(count=len(invoices), invoices=invoices, audit=f"Found {len(invoices)} invoices.")


@ai.tool
async def get_invoice_details(session_id: str, invoice_id: str) -> str:
    """Get one invoice or bill by invoice_id, including line items."""
    accounting, tenant_id = get_accounting_api(session_id)
    result = accounting.get_invoice(tenant_id, invoice_id)
    if not result.invoices:
        return tool_result(error=f"No invoice found for id {invoice_id}.")
    return tool_result(invoice=slim_invoice(result.invoices[0], detailed=True))


@ai.tool
async def list_outstanding_receivables(session_id: str, limit: int = 30) -> str:
    """List unpaid sales invoices (money customers owe you) with amounts due."""
    accounting, tenant_id = get_accounting_api(session_id)
    result = accounting.get_invoices(
        tenant_id,
        where='Type=="ACCREC" && AmountDue>0',
        statuses=["AUTHORISED"],
        page=1,
        summary_only=True,
    )
    invoices = [slim_invoice(inv) for inv in (result.invoices or [])[: _clamp(limit)]]
    total_due = sum(float(inv.get("amount_due") or 0) for inv in invoices)
    return tool_result(
        count=len(invoices),
        total_amount_due=round(total_due, 2),
        invoices=invoices,
        audit=f"Outstanding receivables: £{total_due:,.2f} across {len(invoices)} invoices.",
    )


@ai.tool
async def list_outstanding_payables(session_id: str, limit: int = 30) -> str:
    """List unpaid bills (money you owe suppliers) with amounts due."""
    accounting, tenant_id = get_accounting_api(session_id)
    result = accounting.get_invoices(
        tenant_id,
        where='Type=="ACCPAY" && AmountDue>0',
        statuses=["AUTHORISED"],
        page=1,
        summary_only=True,
    )
    invoices = [slim_invoice(inv) for inv in (result.invoices or [])[: _clamp(limit)]]
    total_due = sum(float(inv.get("amount_due") or 0) for inv in invoices)
    return tool_result(
        count=len(invoices),
        total_amount_due=round(total_due, 2),
        bills=invoices,
        audit=f"Outstanding payables: £{total_due:,.2f} across {len(invoices)} bills.",
    )


# ---------------------------------------------------------------------------
# Payments & bank
# ---------------------------------------------------------------------------


@ai.tool
async def list_payments(
    session_id: str,
    limit: int = 25,
    from_date: str = "",
) -> str:
    """List recent payments. Optional from_date (YYYY-MM-DD) filters payments on or after that date."""
    accounting, tenant_id = get_accounting_api(session_id)
    where = None
    if from_date.strip():
        where = f'Date>=DateTime({from_date.strip()})'
    result = accounting.get_payments(tenant_id, where=where, page=1)
    payments = [slim_payment(p) for p in (result.payments or [])[: _clamp(limit)]]
    return tool_result(count=len(payments), payments=payments, audit=f"Found {len(payments)} payments.")


@ai.tool
async def list_bank_transactions(
    session_id: str,
    limit: int = 25,
    from_date: str = "",
) -> str:
    """List bank account spend/receive transactions. Optional from_date (YYYY-MM-DD)."""
    accounting, tenant_id = get_accounting_api(session_id)
    where = None
    if from_date.strip():
        where = f'Date>=DateTime({from_date.strip()})'
    result = accounting.get_bank_transactions(tenant_id, where=where, page=1)
    txns = [slim_bank_transaction(t) for t in (result.bank_transactions or [])[: _clamp(limit)]]
    return tool_result(
        count=len(txns),
        bank_transactions=txns,
        audit=f"Found {len(txns)} bank transactions.",
    )


# ---------------------------------------------------------------------------
# Items & reports
# ---------------------------------------------------------------------------


@ai.tool
async def list_items(session_id: str, search: str = "", limit: int = 30) -> str:
    """List inventory items / products / services with sales and purchase prices."""
    accounting, tenant_id = get_accounting_api(session_id)
    where = None
    if search.strip():
        term = search.strip().replace('"', "")
        where = f'Name.Contains("{term}") || Code.Contains("{term}")'
    result = accounting.get_items(tenant_id, where=where)
    items = [slim_item(i) for i in (result.items or [])[: _clamp(limit)]]
    return tool_result(count=len(items), items=items, audit=f"Found {len(items)} items.")


@ai.tool
async def get_profit_and_loss(
    session_id: str,
    from_date: str = "",
    to_date: str = "",
) -> str:
    """Get profit & loss report. Defaults to current month if dates omitted."""
    accounting, tenant_id = get_accounting_api(session_id)
    today = date.today()
    start = from_date.strip() or today.replace(day=1).isoformat()
    end = to_date.strip() or today.isoformat()
    report = accounting.get_report_profit_and_loss(tenant_id, from_date=start, to_date=end)
    parsed = parse_xero_report(report)
    return tool_result(
        from_date=start,
        to_date=end,
        report=parsed,
        audit=f"P&L report from {start} to {end}.",
    )


@ai.tool
async def get_aged_receivables_for_contact(
    session_id: str,
    contact_id: str,
    as_of_date: str = "",
) -> str:
    """Aged receivables breakdown for one customer contact_id."""
    accounting, tenant_id = get_accounting_api(session_id)
    report_date = as_of_date.strip() or date.today().isoformat()
    report = accounting.get_report_aged_receivables_by_contact(
        tenant_id,
        contact_id,
        date=report_date,
    )
    return tool_result(
        contact_id=contact_id,
        as_of_date=report_date,
        report=parse_xero_report(report),
        audit=f"Aged receivables for contact {contact_id}.",
    )


@ai.tool
async def get_aged_payables_for_contact(
    session_id: str,
    contact_id: str,
    as_of_date: str = "",
) -> str:
    """Aged payables breakdown for one supplier contact_id."""
    accounting, tenant_id = get_accounting_api(session_id)
    report_date = as_of_date.strip() or date.today().isoformat()
    report = accounting.get_report_aged_payables_by_contact(
        tenant_id,
        contact_id,
        date=report_date,
    )
    return tool_result(
        contact_id=contact_id,
        as_of_date=report_date,
        report=parse_xero_report(report),
        audit=f"Aged payables for contact {contact_id}.",
    )


@ai.tool
async def summarize_cash_position(session_id: str) -> str:
    """Quick snapshot: outstanding receivables, payables, and recent bank activity."""
    accounting, tenant_id = get_accounting_api(session_id)

    receivables = accounting.get_invoices(
        tenant_id,
        where='Type=="ACCREC" && AmountDue>0',
        statuses=["AUTHORISED"],
        summary_only=True,
    )
    payables = accounting.get_invoices(
        tenant_id,
        where='Type=="ACCPAY" && AmountDue>0',
        statuses=["AUTHORISED"],
        summary_only=True,
    )
    week_ago = (date.today() - timedelta(days=7)).isoformat()
    bank = accounting.get_bank_transactions(
        tenant_id,
        where=f"Date>=DateTime({week_ago})",
        page=1,
    )

    recv_total = sum(float(i.amount_due or 0) for i in (receivables.invoices or []))
    pay_total = sum(float(i.amount_due or 0) for i in (payables.invoices or []))
    bank_count = len(bank.bank_transactions or [])

    return tool_result(
        outstanding_receivables_gbp=round(recv_total, 2),
        receivable_invoice_count=len(receivables.invoices or []),
        outstanding_payables_gbp=round(pay_total, 2),
        payable_bill_count=len(payables.invoices or []),
        bank_transactions_last_7_days=bank_count,
        audit=(
            f"Owed to you: £{recv_total:,.2f}. You owe: £{pay_total:,.2f}. "
            f"{bank_count} bank transactions in the last 7 days."
        ),
    )


QUERY_TOOLS: list[ai.AgentTool] = [
    get_organisation_info,
    list_accounts,
    list_tax_rates,
    list_tracking_categories,
    list_branding_themes,
    list_contacts,
    get_contact_details,
    list_invoices,
    get_invoice_details,
    list_outstanding_receivables,
    list_outstanding_payables,
    list_payments,
    list_bank_transactions,
    list_items,
    get_profit_and_loss,
    get_aged_receivables_for_contact,
    get_aged_payables_for_contact,
    summarize_cash_position,
]
