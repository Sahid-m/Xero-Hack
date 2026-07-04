"""Neon Postgres — shared session + Xero OAuth tokens."""

from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Generator

import psycopg
from psycopg.rows import dict_row

from app.config import get_settings

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS voca_sessions (
    session_id TEXT PRIMARY KEY,
    state JSONB NOT NULL DEFAULT '{}',
    xero_tokens JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS voca_sessions_updated_at_idx ON voca_sessions (updated_at DESC);
"""


def db_enabled() -> bool:
    return bool(get_settings().database_url)


@contextmanager
def get_conn() -> Generator[psycopg.Connection, None, None]:
    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is not configured")
    conn = psycopg.connect(settings.database_url, row_factory=dict_row)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    if not db_enabled():
        return
    with get_conn() as conn:
        conn.execute(SCHEMA_SQL)


def ensure_session_row(session_id: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO voca_sessions (session_id, state)
            VALUES (%s, %s)
            ON CONFLICT (session_id) DO NOTHING
            """,
            (session_id, json.dumps({})),
        )


def load_xero_tokens(session_id: str) -> dict[str, Any] | None:
    if not db_enabled():
        return None
    ensure_session_row(session_id)
    with get_conn() as conn:
        row = conn.execute(
            "SELECT xero_tokens FROM voca_sessions WHERE session_id = %s",
            (session_id,),
        ).fetchone()
    if not row or not row["xero_tokens"]:
        return None
    tokens = row["xero_tokens"]
    return tokens if isinstance(tokens, dict) else json.loads(tokens)


def save_xero_tokens(session_id: str, tokens: dict[str, Any] | None) -> None:
    if not db_enabled():
        return
    ensure_session_row(session_id)
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE voca_sessions
            SET xero_tokens = %s, updated_at = NOW()
            WHERE session_id = %s
            """,
            (json.dumps(tokens) if tokens else None, session_id),
        )


def load_session_state(session_id: str) -> dict[str, Any]:
    default = {
        "session_id": session_id,
        "mode": "setup",
        "interview_step": 0,
        "business_type": None,
        "vat_registered": None,
        "contacts": [],
        "rates": {},
    }
    if not db_enabled():
        return default
    ensure_session_row(session_id)
    with get_conn() as conn:
        row = conn.execute(
            "SELECT state FROM voca_sessions WHERE session_id = %s",
            (session_id,),
        ).fetchone()
    if not row or not row["state"]:
        return default
    stored = row["state"]
    if isinstance(stored, str):
        stored = json.loads(stored)
    return {**default, **stored, "session_id": session_id}


def save_session_state(session_id: str, data: dict[str, Any]) -> None:
    if not db_enabled():
        return
    ensure_session_row(session_id)
    payload = {k: v for k, v in data.items() if k != "session_id"}
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE voca_sessions
            SET state = %s, updated_at = NOW()
            WHERE session_id = %s
            """,
            (json.dumps(payload), session_id),
        )
