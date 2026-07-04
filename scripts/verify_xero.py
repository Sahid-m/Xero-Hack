#!/usr/bin/env python3
"""
Hour 0–2 gate: prove we can write to Xero Demo Company.
Creates a test contact and draft invoice, then reads aged receivables.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
from xero_python.accounting.models import Contact, Contacts, Invoice, Invoices, LineItem

from app.xero_client import get_accounting_api

load_dotenv()


def main() -> None:
    print("🔌 Connecting to Xero...")
    accounting, tenant_id = get_accounting_api("default")
    print(f"✓ Authenticated (tenant: {tenant_id})")

    stamp = int(time.time())
    contact_name = f"Voca Verify {stamp}"

    print(f"\n📝 Creating contact: {contact_name}")
    contact_result = accounting.create_contacts(
        tenant_id,
        Contacts(
            contacts=[
                Contact(
                    name=contact_name,
                    email_address="verify@voca.dev",
                    is_customer=True,
                )
            ]
        ),
    )
    contact = contact_result.contacts[0]
    if not contact.contact_id:
        raise RuntimeError("Failed to create contact — no contact_id returned.")
    print(f"✓ Contact created: {contact.contact_id}")

    print("\n🧾 Creating draft invoice...")
    invoice_result = accounting.create_invoices(
        tenant_id,
        Invoices(
            invoices=[
                Invoice(
                    type="ACCREC",
                    contact=Contact(contact_id=contact.contact_id),
                    line_items=[
                        LineItem(
                            description="Voca API verification — labour",
                            quantity=2,
                            unit_amount=45,
                            account_code="200",
                            tax_type="OUTPUT2",
                        )
                    ],
                    status="DRAFT",
                    reference=f"voca-verify-{stamp}",
                )
            ]
        ),
    )
    invoice = invoice_result.invoices[0]
    if not invoice.invoice_id:
        raise RuntimeError("Failed to create invoice — no invoice_id returned.")
    print(f"✓ Draft invoice created: {invoice.invoice_id}")
    print(f"  Total: £{invoice.total:.2f} (incl. VAT)")

    print("\n📊 Fetching aged receivables report...")
    from datetime import date

    report = accounting.get_report_aged_receivables_by_contact(tenant_id, date.today())
    rows = len(report.reports[0].rows) if report.reports and report.reports[0].rows else 0
    print(f"✓ Report returned ({rows} row groups)")

    print(f"\n🧹 Archiving test contact {contact.contact_id}...")
    accounting.update_contact(
        tenant_id,
        contact.contact_id,
        Contacts(contacts=[Contact(contact_id=contact.contact_id, contact_status="ARCHIVED")]),
    )
    print("✓ Contact archived")

    print("\n✅ Xero API verification passed. Ready for Voca build.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\n❌ Verification failed: {exc}")
        raise SystemExit(1) from exc
