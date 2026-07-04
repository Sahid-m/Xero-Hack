"""Serialize Xero API models into compact JSON for the agent."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any


def _str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def slim_account(account: Any) -> dict[str, Any]:
    return {
        "code": account.code,
        "name": account.name,
        "type": account.type,
        "tax_type": account.tax_type,
        "status": account.status,
        "description": account.description,
    }


def slim_contact(contact: Any, detailed: bool = False) -> dict[str, Any]:
    base: dict[str, Any] = {
        "contact_id": contact.contact_id,
        "name": contact.name,
        "email": contact.email_address,
        "is_customer": contact.is_customer,
        "is_supplier": contact.is_supplier,
    }
    if detailed:
        base.update(
            {
                "phones": [p.phone_number for p in (contact.phones or []) if p.phone_number],
                "addresses": [
                    ", ".join(filter(None, [a.address_line1, a.city, a.postal_code]))
                    for a in (contact.addresses or [])
                ],
                "tax_number": contact.tax_number,
                "default_currency": contact.default_currency,
                "balances": {
                    "accounts_receivable": getattr(contact.balances, "accounts_receivable", None)
                    if contact.balances
                    else None,
                    "accounts_payable": getattr(contact.balances, "accounts_payable", None)
                    if contact.balances
                    else None,
                },
            }
        )
    return base


def slim_invoice(invoice: Any, detailed: bool = False) -> dict[str, Any]:
    contact_name = invoice.contact.name if invoice.contact else None
    base: dict[str, Any] = {
        "invoice_id": invoice.invoice_id,
        "invoice_number": invoice.invoice_number,
        "type": invoice.type,
        "status": invoice.status,
        "contact": contact_name,
        "reference": invoice.reference,
        "date": _str(invoice.date),
        "due_date": _str(invoice.due_date),
        "total": invoice.total,
        "amount_due": invoice.amount_due,
        "amount_paid": invoice.amount_paid,
        "currency_code": invoice.currency_code,
    }
    if detailed:
        base["line_items"] = [
            {
                "description": item.description,
                "quantity": item.quantity,
                "unit_amount": item.unit_amount,
                "line_amount": item.line_amount,
                "account_code": item.account_code,
                "tax_type": item.tax_type,
            }
            for item in (invoice.line_items or [])
        ]
    return base


def slim_payment(payment: Any) -> dict[str, Any]:
    return {
        "payment_id": payment.payment_id,
        "date": _str(payment.date),
        "amount": payment.amount,
        "reference": payment.reference,
        "status": payment.status,
        "payment_type": payment.payment_type,
        "invoice": payment.invoice.invoice_number if payment.invoice else None,
        "contact": payment.invoice.contact.name
        if payment.invoice and payment.invoice.contact
        else None,
    }


def slim_bank_transaction(txn: Any) -> dict[str, Any]:
    return {
        "bank_transaction_id": txn.bank_transaction_id,
        "type": txn.type,
        "status": txn.status,
        "date": _str(txn.date),
        "total": txn.total,
        "reference": txn.reference,
        "contact": txn.contact.name if txn.contact else None,
        "line_items": [
            {
                "description": item.description,
                "quantity": item.quantity,
                "unit_amount": item.unit_amount,
                "account_code": item.account_code,
            }
            for item in (txn.line_items or [])
        ],
    }


def slim_item(item: Any) -> dict[str, Any]:
    return {
        "item_id": item.item_id,
        "code": item.code,
        "name": item.name,
        "description": item.description,
        "purchase_unit_price": item.purchase_details.unit_price if item.purchase_details else None,
        "sales_unit_price": item.sales_details.unit_price if item.sales_details else None,
    }


def parse_xero_report(report: Any, max_rows: int = 40) -> dict[str, Any]:
    if not report or not report.reports:
        return {"rows": []}

    def walk_rows(rows: Any, depth: int = 0) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for row in rows or []:
            if len(out) >= max_rows:
                break
            entry: dict[str, Any] = {
                "title": row.title,
                "cells": [c.value for c in (row.cells or [])],
            }
            if row.rows:
                entry["children"] = walk_rows(row.rows, depth + 1)
            out.append(entry)
        return out

    r = report.reports[0]
    return {
        "report_name": r.report_name,
        "report_titles": r.report_titles,
        "report_date": _str(r.report_date),
        "rows": walk_rows(r.rows),
    }


def tool_result(**payload: Any) -> str:
    return json.dumps(payload, default=str)
