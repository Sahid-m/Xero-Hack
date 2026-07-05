"""Live demo mirror state — polled by /demo dashboard."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.session import get_session, save_session


def _mirror_session_id(connection_id: str) -> str:
    return f"mirror-{connection_id}"


def _default_state() -> dict[str, Any]:
    return {
        "connected": False,
        "org_name": None,
        "owed_total_gbp": None,
        "owed_invoice_count": None,
        "last_invoice": None,
        "last_receipt": None,
        "updated_at": None,
    }


def get_demo_state(connection_id: str) -> dict[str, Any]:
    session = get_session(_mirror_session_id(connection_id))
    stored = session.get("demo_state")
    if not isinstance(stored, dict):
        return _default_state()
    return {**_default_state(), **stored}


def update_demo_state(connection_id: str, **patch: Any) -> dict[str, Any]:
    sid = _mirror_session_id(connection_id)
    session = get_session(sid)
    demo = session.get("demo_state")
    if not isinstance(demo, dict):
        demo = _default_state()
    demo.update(patch)
    demo["updated_at"] = datetime.now(timezone.utc).isoformat()
    session["demo_state"] = demo
    save_session(sid, session)
    return demo


def set_receivables(connection_id: str, *, total_gbp: float, count: int) -> None:
    update_demo_state(
        connection_id,
        owed_total_gbp=round(total_gbp, 2),
        owed_invoice_count=count,
    )


def set_invoice_mirror(
    connection_id: str,
    *,
    status: str,
    customer: str,
    amount_gbp: float,
    invoice_number: str | None = None,
) -> None:
    update_demo_state(
        connection_id,
        last_invoice={
            "status": status,
            "customer": customer,
            "amount_gbp": round(amount_gbp, 2),
            "invoice_number": invoice_number,
        },
    )


def set_receipt_mirror(
    connection_id: str,
    *,
    vendor: str,
    amount_gbp: float,
    category: str,
    in_xero: bool = False,
    bill_number: str | None = None,
) -> None:
    update_demo_state(
        connection_id,
        last_receipt={
            "vendor": vendor,
            "amount_gbp": round(amount_gbp, 2),
            "category": category,
            "in_xero": in_xero,
            "bill_number": bill_number,
        },
    )


def set_connected(connection_id: str, *, connected: bool, org_name: str | None = None) -> None:
    update_demo_state(connection_id, connected=connected, org_name=org_name)
