"""Read-only Xero query tools for the Voca agent."""

from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timedelta
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
from app.session_context import xero_connection_id
from app.xero_client import get_accounting_api

InvoiceType = Literal["ACCREC", "ACCPAY", "all"]
InvoiceStatus = Literal["DRAFT", "SUBMITTED", "AUTHORISED", "PAID", "VOIDED", "all"]
ContactType = Literal["all", "customer", "supplier"]


def _clamp(limit: int, cap: int = 50) -> int:
    return max(1, min(limit, cap))


def _opt(**kwargs: Any) -> dict[str, Any]:
    """Drop None values — xero-python cannot serialize null query params."""
    return {k: v for k, v in kwargs.items() if v is not None}


def _api():
    return get_accounting_api(xero_connection_id())


# ---------------------------------------------------------------------------
# Organisation & settings
# ---------------------------------------------------------------------------


@ai.tool
async def get_organisation_info() -> str:
    """Get the connected Xero organisation name, legal name, currency, and country."""
    accounting, tenant_id = _api()
    result = await asyncio.to_thread(accounting.get_organisations, tenant_id)
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
    search: str = "",
    limit: int = 50,
) -> str:
    """List chart of accounts (codes, names, types). Optional search filters by name or code."""
    accounting, tenant_id = _api()
    where = None
    if search.strip():
        term = search.strip().replace('"', "")
        where = f'Name.Contains("{term}") || Code.Contains("{term}")'
    result = await asyncio.to_thread(accounting.get_accounts, tenant_id, **_opt(where=where))
    accounts = [slim_account(a) for a in (result.accounts or [])[: _clamp(limit)]]
    return tool_result(count=len(accounts), accounts=accounts, audit=f"Found {len(accounts)} accounts.")


@ai.tool
async def list_tax_rates() -> str:
    """List tax rates configured in Xero (VAT types and percentages)."""
    accounting, tenant_id = _api()
    result = await asyncio.to_thread(accounting.get_tax_rates, tenant_id)
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
async def list_tracking_categories() -> str:
    """List tracking categories and their options (departments, projects, etc.)."""
    accounting, tenant_id = _api()
    result = await asyncio.to_thread(accounting.get_tracking_categories, tenant_id)
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
async def list_branding_themes() -> str:
    """List invoice branding themes (logo, colours, payment terms)."""
    accounting, tenant_id = _api()
    result = await asyncio.to_thread(accounting.get_branding_themes, tenant_id)
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
    contact_type: ContactType = "all",
    search: str = "",
    limit: int = 25,
) -> str:
    """List contacts. Filter by customer/supplier and optional name search."""
    accounting, tenant_id = _api()
    where = None
    if contact_type == "customer":
        where = "IsCustomer==true"
    elif contact_type == "supplier":
        where = "IsSupplier==true"

    result = await asyncio.to_thread(
        accounting.get_contacts,
        tenant_id,
        page=1,
        **_opt(where=where, search_term=search.strip() or None),
    )
    contacts = [slim_contact(c) for c in (result.contacts or [])[: _clamp(limit)]]
    return tool_result(count=len(contacts), contacts=contacts, audit=f"Found {len(contacts)} contacts.")


@ai.tool
async def get_contact_details(contact_id: str) -> str:
    """Get full details for one contact by Xero contact_id."""
    accounting, tenant_id = _api()
    result = await asyncio.to_thread(accounting.get_contact, tenant_id, contact_id)
    if not result.contacts:
        return tool_result(error=f"No contact found for id {contact_id}.")
    return tool_result(contact=slim_contact(result.contacts[0], detailed=True))


# ---------------------------------------------------------------------------
# Invoices & bills
# ---------------------------------------------------------------------------


@ai.tool
async def list_invoices(
    invoice_type: InvoiceType = "all",
    status: InvoiceStatus = "all",
    contact_name: str = "",
    limit: int = 20,
) -> str:
    """List sales invoices (ACCREC) or bills (ACCPAY). Filter by status and contact name."""
    accounting, tenant_id = _api()
    clauses: list[str] = []
    if invoice_type != "all":
        clauses.append(f'Type=="{invoice_type}"')
    if contact_name.strip():
        term = contact_name.strip().replace('"', "")
        clauses.append(f'Contact.Name.Contains("{term}")')
    where = " && ".join(clauses) if clauses else None
    statuses = None if status == "all" else [status]

    result = await asyncio.to_thread(
        accounting.get_invoices,
        tenant_id,
        page=1,
        summary_only=True,
        **_opt(where=where, statuses=statuses),
    )
    invoices = [slim_invoice(inv) for inv in (result.invoices or [])[: _clamp(limit)]]
    return tool_result(count=len(invoices), invoices=invoices, audit=f"Found {len(invoices)} invoices.")


@ai.tool
async def get_invoice_details(invoice_id: str) -> str:
    """Get one invoice or bill by invoice_id, including line items."""
    accounting, tenant_id = _api()
    result = await asyncio.to_thread(accounting.get_invoice, tenant_id, invoice_id)
    if not result.invoices:
        return tool_result(error=f"No invoice found for id {invoice_id}.")
    return tool_result(invoice=slim_invoice(result.invoices[0], detailed=True))


@ai.tool
async def list_outstanding_receivables(limit: int = 30) -> str:
    """List unpaid sales invoices (money customers owe you) with amounts due."""
    accounting, tenant_id = _api()
    result = await asyncio.to_thread(
        accounting.get_invoices,
        tenant_id,
        where='Type=="ACCREC" && AmountDue>0',
        statuses=["AUTHORISED"],
        page=1,
        summary_only=True,
    )
    all_invoices = result.invoices or []
    total_due = sum(float(inv.amount_due or 0) for inv in all_invoices)
    invoices = [slim_invoice(inv) for inv in all_invoices[: _clamp(limit)]]
    return tool_result(
        count=len(all_invoices),
        total_amount_due=round(total_due, 2),
        invoices=invoices,
        audit=f"Outstanding receivables: £{total_due:,.2f} across {len(all_invoices)} invoices.",
    )


@ai.tool
async def list_outstanding_payables(limit: int = 30) -> str:
    """List unpaid bills (money you owe suppliers) with amounts due."""
    accounting, tenant_id = _api()
    result = await asyncio.to_thread(
        accounting.get_invoices,
        tenant_id,
        where='Type=="ACCPAY" && AmountDue>0',
        statuses=["AUTHORISED"],
        page=1,
        summary_only=True,
    )
    all_invoices = result.invoices or []
    total_due = sum(float(inv.amount_due or 0) for inv in all_invoices)
    bills = [slim_invoice(inv) for inv in all_invoices[: _clamp(limit)]]
    return tool_result(
        count=len(all_invoices),
        total_amount_due=round(total_due, 2),
        bills=bills,
        audit=f"Outstanding payables: £{total_due:,.2f} across {len(all_invoices)} bills.",
    )


def _parse_due_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str) and value.strip():
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


@ai.tool
async def list_overdue_receivables(limit: int = 20) -> str:
    """List overdue sales invoices (past due date) with days overdue — for chasing payment."""
    accounting, tenant_id = _api()
    result = await asyncio.to_thread(
        accounting.get_invoices,
        tenant_id,
        where='Type=="ACCREC" && AmountDue>0',
        statuses=["AUTHORISED"],
        page=1,
        summary_only=True,
    )
    today = date.today()
    overdue_rows: list[dict[str, Any]] = []
    for inv in result.invoices or []:
        due = _parse_due_date(inv.due_date)
        if due is None or due >= today:
            continue
        days = (today - due).days
        slim = slim_invoice(inv)
        slim["days_overdue"] = days
        overdue_rows.append(slim)

    overdue_rows.sort(key=lambda r: (r.get("days_overdue", 0), float(r.get("amount_due") or 0)), reverse=True)
    total = sum(float(r.get("amount_due") or 0) for r in overdue_rows)
    shown = overdue_rows[: _clamp(limit)]
    return tool_result(
        count=len(overdue_rows),
        total_overdue_gbp=round(total, 2),
        invoices=shown,
        audit=f"{len(overdue_rows)} overdue invoices totalling £{total:,.2f}.",
    )


@ai.tool
async def who_should_i_chase(limit: int = 5) -> str:
    """Who to chase for payment — overdue customers ranked by amount and lateness."""
    raw = await list_overdue_receivables.fn(limit=50)
    data = json.loads(raw)
    if data.get("error"):
        return raw
    invoices = data.get("invoices") or []
    if not invoices:
        return tool_result(
            count=0,
            audit="Nobody is overdue right now — all your outstanding invoices are still within payment terms.",
        )

    # Group by contact
    by_contact: dict[str, dict[str, Any]] = {}
    for inv in invoices:
        name = inv.get("contact") or "Unknown"
        bucket = by_contact.setdefault(
            name,
            {"contact": name, "total_due": 0.0, "max_days_overdue": 0, "invoice_count": 0},
        )
        bucket["total_due"] += float(inv.get("amount_due") or 0)
        bucket["max_days_overdue"] = max(bucket["max_days_overdue"], int(inv.get("days_overdue") or 0))
        bucket["invoice_count"] += 1

    ranked = sorted(
        by_contact.values(),
        key=lambda c: (c["max_days_overdue"], c["total_due"]),
        reverse=True,
    )[:limit]

    parts = []
    for c in ranked:
        days = c["max_days_overdue"]
        parts.append(
            f"{c['contact']} owes £{c['total_due']:,.2f} "
            f"({days} day{'s' if days != 1 else ''} overdue)"
        )
    spoken = "I'd chase these customers first: " + "; ".join(parts) + "."
    return tool_result(
        chase_list=ranked,
        audit=spoken,
    )


# ---------------------------------------------------------------------------
# Payments & bank
# ---------------------------------------------------------------------------


@ai.tool
async def list_payments(
    limit: int = 25,
    from_date: str = "",
) -> str:
    """List recent payments. Optional from_date (YYYY-MM-DD) filters payments on or after that date."""
    accounting, tenant_id = _api()
    where = None
    if from_date.strip():
        where = f'Date>=DateTime({from_date.strip()})'
    result = await asyncio.to_thread(accounting.get_payments, tenant_id, page=1, **_opt(where=where))
    payments = [slim_payment(p) for p in (result.payments or [])[: _clamp(limit)]]
    return tool_result(count=len(payments), payments=payments, audit=f"Found {len(payments)} payments.")


@ai.tool
async def list_bank_transactions(
    limit: int = 25,
    from_date: str = "",
) -> str:
    """List bank account spend/receive transactions. Optional from_date (YYYY-MM-DD)."""
    accounting, tenant_id = _api()
    where = None
    if from_date.strip():
        where = f'Date>=DateTime({from_date.strip()})'
    result = await asyncio.to_thread(
        accounting.get_bank_transactions, tenant_id, page=1, **_opt(where=where)
    )
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
async def list_items(search: str = "", limit: int = 30) -> str:
    """List inventory items / products / services with sales and purchase prices."""
    accounting, tenant_id = _api()
    where = None
    if search.strip():
        term = search.strip().replace('"', "")
        where = f'Name.Contains("{term}") || Code.Contains("{term}")'
    result = await asyncio.to_thread(accounting.get_items, tenant_id, **_opt(where=where))
    items = [slim_item(i) for i in (result.items or [])[: _clamp(limit)]]
    return tool_result(count=len(items), items=items, audit=f"Found {len(items)} items.")


@ai.tool
async def get_profit_and_loss(
    from_date: str = "",
    to_date: str = "",
) -> str:
    """Get profit & loss report. Defaults to current month if dates omitted."""
    accounting, tenant_id = _api()
    today = date.today()
    start = from_date.strip() or today.replace(day=1).isoformat()
    end = to_date.strip() or today.isoformat()
    report = await asyncio.to_thread(
        accounting.get_report_profit_and_loss, tenant_id, from_date=start, to_date=end
    )
    parsed = parse_xero_report(report)
    return tool_result(
        from_date=start,
        to_date=end,
        report=parsed,
        audit=f"P&L report from {start} to {end}.",
    )


def _mtd_quarters_for_tax_year(start_year: int) -> list[tuple[date, date, date, str]]:
    """UK MTD ITSA standard quarters for the tax year starting 6 Apr start_year."""
    return [
        (date(start_year, 4, 6), date(start_year, 7, 5), date(start_year, 8, 7), "Q1"),
        (date(start_year, 7, 6), date(start_year, 10, 5), date(start_year, 11, 7), "Q2"),
        (date(start_year, 10, 6), date(start_year + 1, 1, 5), date(start_year + 1, 2, 7), "Q3"),
        (date(start_year + 1, 1, 6), date(start_year + 1, 4, 5), date(start_year + 1, 5, 7), "Q4"),
    ]


def _current_mtd_quarter(as_of: date) -> tuple[date, date, date, str]:
    for start_year in (as_of.year - 1, as_of.year):
        for q_start, q_end, deadline, label in _mtd_quarters_for_tax_year(start_year):
            if q_start <= as_of <= q_end:
                return q_start, q_end, deadline, label
    raise ValueError(f"Could not resolve MTD quarter for {as_of.isoformat()}")


def _pl_total(rows: list[dict[str, Any]], *labels: str) -> float | None:
    """Find a named total row (e.g. "Total Income", "Net Profit") anywhere in a parsed P&L report."""
    for row in rows:
        title = (row.get("cells") or [None])[0]
        if isinstance(title, str) and title.strip() in labels:
            cells = row.get("cells") or []
            if len(cells) > 1:
                try:
                    return float(str(cells[1]).replace(",", ""))
                except (TypeError, ValueError):
                    return None
        found = _pl_total(row.get("children") or [], *labels)
        if found is not None:
            return found
    return None


@ai.tool
async def mtd_quarter_summary(as_of_date: str = "") -> str:
    """
    Making Tax Digital (ITSA) quarterly readiness check: which MTD quarter is
    "as_of_date" (default today) in, when is the next digital update due, and
    what does this quarter's income/expenses/net profit look like so far —
    the numbers that quarter's HMRC submission will be built from.
    """
    accounting, tenant_id = _api()
    as_of = _parse_due_date(as_of_date) or date.today()
    q_start, q_end, deadline, label = _current_mtd_quarter(as_of)

    report = await asyncio.to_thread(
        accounting.get_report_profit_and_loss,
        tenant_id,
        from_date=q_start.isoformat(),
        to_date=min(q_end, as_of).isoformat(),
    )
    parsed = parse_xero_report(report)
    rows = parsed.get("rows") or []

    income = _pl_total(rows, "Total Income") or 0.0
    expenses = _pl_total(rows, "Total Operating Expenses") or 0.0
    cost_of_sales = _pl_total(rows, "Total Cost of Sales") or 0.0
    net_profit = _pl_total(rows, "Net Profit")
    if net_profit is None:
        net_profit = income - expenses - cost_of_sales

    days_left = (deadline - as_of).days

    return tool_result(
        mtd_quarter=label,
        quarter_start=q_start.isoformat(),
        quarter_end=q_end.isoformat(),
        submission_deadline=deadline.isoformat(),
        days_until_deadline=days_left,
        income_gbp=round(income, 2),
        expenses_gbp=round(expenses + cost_of_sales, 2),
        net_profit_gbp=round(net_profit, 2),
        audit=(
            f"MTD {label} ({q_start.isoformat()} to {q_end.isoformat()}): "
            f"£{income:,.2f} income, £{expenses + cost_of_sales:,.2f} expenses, "
            f"£{net_profit:,.2f} net profit so far. Next digital update due "
            f"{deadline.isoformat()} — {days_left} day{'s' if days_left != 1 else ''} away."
        ),
    )


@ai.tool
async def get_aged_receivables_for_contact(
    contact_id: str,
    as_of_date: str = "",
) -> str:
    """Aged receivables breakdown for one customer contact_id."""
    accounting, tenant_id = _api()
    report_date = as_of_date.strip() or date.today().isoformat()
    report = await asyncio.to_thread(
        accounting.get_report_aged_receivables_by_contact,
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
    contact_id: str,
    as_of_date: str = "",
) -> str:
    """Aged payables breakdown for one supplier contact_id."""
    accounting, tenant_id = _api()
    report_date = as_of_date.strip() or date.today().isoformat()
    report = await asyncio.to_thread(
        accounting.get_report_aged_payables_by_contact,
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
async def summarize_cash_position() -> str:
    """Quick snapshot: outstanding receivables, payables, and recent bank activity."""
    accounting, tenant_id = _api()

    receivables = await asyncio.to_thread(
        accounting.get_invoices,
        tenant_id,
        where='Type=="ACCREC" && AmountDue>0',
        statuses=["AUTHORISED"],
        summary_only=True,
    )
    payables = await asyncio.to_thread(
        accounting.get_invoices,
        tenant_id,
        where='Type=="ACCPAY" && AmountDue>0',
        statuses=["AUTHORISED"],
        summary_only=True,
    )
    week_ago = (date.today() - timedelta(days=7)).isoformat()
    bank = await asyncio.to_thread(
        accounting.get_bank_transactions,
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


def _name_similarity(a: str, b: str) -> float:
    """Cheap token-overlap similarity, 0..1 — good enough to rank contact name matches."""
    a_tokens = set(a.lower().split())
    b_tokens = set(b.lower().split())
    if not a_tokens or not b_tokens:
        return 0.0
    overlap = len(a_tokens & b_tokens)
    return overlap / max(len(a_tokens), len(b_tokens))


def _match_score(*, amount_diff: float, day_diff: int, name_sim: float) -> int:
    """0-100 confidence a bank transaction pairs with a given invoice/bill."""
    score = 100.0
    score -= min(amount_diff * 20, 60)  # £3 off caps most of the penalty
    score -= min(day_diff * 4, 40)  # 10+ days apart caps the rest
    score += name_sim * 15
    return max(0, min(100, round(score)))


@ai.tool
async def find_reconciliation_matches(limit: int = 15) -> str:
    """
    Match unreconciled bank transactions to outstanding invoices/bills by amount,
    date proximity, and contact name — the "which payment belongs to which invoice"
    step of bank reconciliation. Read-only; use reconcile_invoice_payment to act on
    a match once the user confirms it.
    """
    accounting, tenant_id = _api()

    receivables, payables, bank = await asyncio.gather(
        asyncio.to_thread(
            accounting.get_invoices,
            tenant_id,
            where='Type=="ACCREC" && AmountDue>0',
            statuses=["AUTHORISED"],
            summary_only=True,
        ),
        asyncio.to_thread(
            accounting.get_invoices,
            tenant_id,
            where='Type=="ACCPAY" && AmountDue>0',
            statuses=["AUTHORISED"],
            summary_only=True,
        ),
        asyncio.to_thread(
            accounting.get_bank_transactions,
            tenant_id,
            where="IsReconciled==false",
            page=1,
        ),
    )

    outstanding = list(receivables.invoices or []) + list(payables.invoices or [])
    txns = bank.bank_transactions or []

    matches: list[dict[str, Any]] = []
    for txn in txns:
        # RECEIVE money matches sales invoices (ACCREC); SPEND matches bills (ACCPAY)
        wanted_type = "ACCREC" if txn.type == "RECEIVE" else "ACCPAY"
        txn_date = _parse_due_date(txn.date)
        txn_contact = txn.contact.name if txn.contact else ""
        for inv in outstanding:
            if inv.type != wanted_type:
                continue
            amount_diff = abs(float(txn.total or 0) - float(inv.amount_due or 0))
            if amount_diff > 5.0:
                continue
            inv_date = _parse_due_date(inv.date)
            day_diff = abs((txn_date - inv_date).days) if txn_date and inv_date else 30
            if day_diff > 21:
                continue
            inv_contact = inv.contact.name if inv.contact else ""
            score = _match_score(
                amount_diff=amount_diff,
                day_diff=day_diff,
                name_sim=_name_similarity(txn_contact, inv_contact),
            )
            if score < 40:
                continue
            matches.append(
                {
                    "confidence": score,
                    "bank_transaction_id": txn.bank_transaction_id,
                    "bank_date": txn_date.isoformat() if txn_date else None,
                    "bank_amount": float(txn.total or 0),
                    "bank_contact": txn_contact or None,
                    "invoice_id": inv.invoice_id,
                    "invoice_number": inv.invoice_number,
                    "invoice_type": inv.type,
                    "invoice_contact": inv_contact or None,
                    "invoice_amount_due": float(inv.amount_due or 0),
                }
            )

    matches.sort(key=lambda m: m["confidence"], reverse=True)
    matches = matches[: _clamp(limit)]

    if not matches:
        return tool_result(
            count=0,
            matches=[],
            audit="No confident matches between unreconciled bank transactions and outstanding invoices/bills.",
        )

    top = matches[0]
    return tool_result(
        count=len(matches),
        matches=matches,
        audit=(
            f"Found {len(matches)} likely match(es). Best: bank transaction "
            f"£{top['bank_amount']:.2f} ({top['bank_contact'] or 'no contact'}) "
            f"vs invoice {top['invoice_number']} for £{top['invoice_amount_due']:.2f} "
            f"({top['invoice_contact'] or 'no contact'}) — {top['confidence']}% confidence."
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
    list_overdue_receivables,
    who_should_i_chase,
    list_payments,
    list_bank_transactions,
    list_items,
    get_profit_and_loss,
    get_aged_receivables_for_contact,
    get_aged_payables_for_contact,
    summarize_cash_position,
    find_reconciliation_matches,
    mtd_quarter_summary,
]
