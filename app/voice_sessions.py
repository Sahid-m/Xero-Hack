"""Map phone numbers to Voca connection ids (Xero OAuth)."""

from __future__ import annotations

import re

from app.db import db_enabled, get_conn
from app.session import get_session, save_session


def normalize_phone(phone: str) -> str:
    """Best-effort E.164-ish normalization."""
    raw = phone.strip()
    if not raw:
        return ""
    digits = re.sub(r"\D", "", raw)
    if raw.startswith("+"):
        return f"+{digits}"
    if digits.startswith("44"):
        return f"+{digits}"
    if digits.startswith("0") and len(digits) >= 10:
        return f"+44{digits[1:]}"
    if len(digits) == 10:
        return f"+1{digits}"
    return f"+{digits}" if digits else ""


def link_phone(connection_id: str, phone: str) -> str:
    """Associate a caller's phone number with their Xero connection id."""
    phone_e164 = normalize_phone(phone)
    if not phone_e164:
        raise ValueError("Invalid phone number")

    session = get_session(connection_id)
    session["phone_e164"] = phone_e164
    save_session(connection_id, session)
    return phone_e164


def unlink_phone(connection_id: str) -> None:
    session = get_session(connection_id)
    session.pop("phone_e164", None)
    save_session(connection_id, session)


def connection_for_phone(phone: str) -> str | None:
    phone_e164 = normalize_phone(phone)
    if not phone_e164:
        return None

    if db_enabled():
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT session_id FROM voca_sessions
                WHERE state->>'phone_e164' = %s
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (phone_e164,),
            ).fetchone()
        if row:
            return row["session_id"]

    # File fallback: scan session files
    from pathlib import Path
    import json

    data_dir = Path("data/sessions")
    if not data_dir.exists():
        return None
    for path in data_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        if data.get("phone_e164") == phone_e164:
            return data.get("session_id")
    return None


def phone_for_connection(connection_id: str) -> str | None:
    return get_session(connection_id).get("phone_e164")
