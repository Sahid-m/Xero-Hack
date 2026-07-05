from __future__ import annotations

import asyncio
import json
import logging
import re
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
from xero_python.accounting import AccountingApi
from xero_python.api_client import ApiClient
from xero_python.api_client.configuration import Configuration
from xero_python.api_client.oauth2 import OAuth2Token

from app.config import Settings, get_settings
from app.db import (
    db_enabled,
    load_xero_tokens as db_load_tokens,
    save_xero_tokens as db_save_tokens,
)

TOKEN_DIR = Path("data/xero")
TOKEN_DIR.mkdir(parents=True, exist_ok=True)

_refresh_lock = threading.Lock()

# Demo-time fix: load_tokens() is a fresh Neon connection per call (1.5-4.5s,
# no pooling) and gets hit twice per single Xero API call (once in ensure_token,
# once in _api_client_for_session). Short-TTL cache collapses that back to
# ~one DB round trip per token generation instead of two-plus.
_TOKEN_CACHE_TTL_SECS = 20
_token_cache: dict[str, tuple[float, dict[str, Any] | None]] = {}

AUTHORIZE_URL = "https://login.xero.com/identity/connect/authorize"
TOKEN_URL = "https://identity.xero.com/connect/token"
CONNECTIONS_URL = "https://api.xero.com/connections"

# Granular scopes (required for apps created after March 2026).
# Enable the same scopes in developer.xero.com → your app → Configuration.
SCOPES = [
    "openid",
    "profile",
    "email",
    "offline_access",
    "accounting.settings",
    "accounting.contacts",
    "accounting.invoices",
    "accounting.payments",
    "accounting.banktransactions",
    "accounting.attachments",
    "accounting.reports.aged.read",
    "accounting.reports.profitandloss.read",
]

# Fields the xero-python OAuth2Token accepts — tenant_id is stored separately.
_SDK_TOKEN_KEYS = frozenset(
    {
        "access_token",
        "refresh_token",
        "expires_in",
        "expires_at",
        "token_type",
        "scope",
        "id_token",
    }
)


def _sdk_token(raw: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in raw.items() if k in _SDK_TOKEN_KEYS}


def _normalize_token(raw: dict[str, Any]) -> dict[str, Any]:
    token = dict(raw)
    if token.get("expires_in") and not token.get("expires_at"):
        token["expires_at"] = time.time() + float(token["expires_in"])
    return token


def _token_path(session_id: str) -> Path:
    safe = session_id.replace("/", "__").replace(":", "_")
    return TOKEN_DIR / f"{safe}.json"


def _file_load_tokens(session_id: str) -> dict[str, Any] | None:
    path = _token_path(session_id)
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _file_save_tokens(session_id: str, tokens: dict[str, Any] | None) -> None:
    path = _token_path(session_id)
    if tokens is None:
        path.unlink(missing_ok=True)
        return
    path.write_text(json.dumps(tokens, indent=2))


def load_tokens(session_id: str) -> dict[str, Any] | None:
    cached = _token_cache.get(session_id)
    if cached and time.time() - cached[0] < _TOKEN_CACHE_TTL_SECS:
        return cached[1]
    if db_enabled():
        tokens = db_load_tokens(session_id)
    else:
        tokens = _file_load_tokens(session_id)
    _token_cache[session_id] = (time.time(), tokens)
    return tokens


def save_tokens(session_id: str, tokens: dict[str, Any] | None) -> None:
    _token_cache[session_id] = (time.time(), tokens)
    if db_enabled():
        db_save_tokens(session_id, tokens)
    else:
        _file_save_tokens(session_id, tokens)


def is_connected(connection_id: str) -> bool:
    stored = load_tokens(connection_id)
    return bool(stored and stored.get("access_token") and stored.get("tenant_id"))


def migrate_tokens(from_id: str, to_id: str) -> bool:
    """Copy Xero tokens between ids (e.g. legacy chat session → stable connection id)."""
    if not from_id or not to_id or from_id == to_id:
        return is_connected(to_id)
    if is_connected(to_id):
        return True
    source = load_tokens(from_id)
    if not source:
        return False
    save_tokens(to_id, source)
    return True


def resolve_xero_connection(connection_id: str, legacy_ids: list[str] | None = None) -> str:
    """Ensure tokens exist on connection_id, migrating from legacy ids if needed."""
    if is_connected(connection_id):
        return connection_id
    for legacy_id in legacy_ids or []:
        if migrate_tokens(legacy_id, connection_id):
            return connection_id
    if _adopt_recent_connection(connection_id):
        return connection_id
    return connection_id


def latest_connected_connection_id() -> str | None:
    """Most recently updated session with valid Xero tokens (dev / web-test fallback)."""
    if not db_enabled():
        return None
    from app.db import get_conn

    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT session_id FROM voca_sessions
            WHERE xero_tokens IS NOT NULL
              AND xero_tokens->>'access_token' IS NOT NULL
            ORDER BY updated_at DESC
            LIMIT 1
            """
        ).fetchone()
    return row["session_id"] if row else None


def connection_id_for_tenant(tenant_id: str) -> str | None:
    """Reverse-lookup: which connection_id holds tokens for this Xero tenant_id.

    Needed for Xero webhooks — they carry tenantId, not our connection_id.
    """
    if not db_enabled():
        return None
    from app.db import get_conn

    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT session_id FROM voca_sessions
            WHERE xero_tokens->>'tenant_id' = %s
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (tenant_id,),
        ).fetchone()
    return row["session_id"] if row else None


def _adopt_recent_connection(target_id: str) -> bool:
    """Demo fallback: reuse the latest Xero connection in the database."""
    if is_connected(target_id) or not db_enabled():
        return False
    from app.db import get_conn

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT session_id FROM voca_sessions
            WHERE xero_tokens IS NOT NULL
              AND xero_tokens->>'access_token' IS NOT NULL
            ORDER BY updated_at DESC
            LIMIT 5
            """
        ).fetchall()
    for row in rows:
        source_id = row["session_id"]
        if source_id != target_id and migrate_tokens(source_id, target_id):
            return True
    return False


def authorization_url(connection_id: str, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    params = {
        "response_type": "code",
        "client_id": settings.xero_client_id,
        "redirect_uri": settings.xero_redirect_uri,
        "scope": " ".join(SCOPES),
        "state": connection_id,
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def _exchange_code_for_token(code: str, settings: Settings) -> dict[str, Any]:
    response = httpx.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.xero_redirect_uri,
        },
        auth=(settings.xero_client_id, settings.xero_client_secret),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30.0,
    )
    if response.status_code != 200:
        raise RuntimeError(f"Xero token exchange failed: {response.text}")
    return _normalize_token(response.json())


def _refresh_access_token(token: dict[str, Any], settings: Settings) -> dict[str, Any]:
    response = httpx.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": token["refresh_token"],
        },
        auth=(settings.xero_client_id, settings.xero_client_secret),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30.0,
    )
    if response.status_code != 200:
        raise RuntimeError(f"Xero token refresh failed: {response.text}")
    refreshed = _normalize_token(response.json())
    return {**token, **refreshed}


def _resolve_tenant_id(access_token: str) -> str:
    response = httpx.get(
        CONNECTIONS_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30.0,
    )
    if response.status_code != 200:
        raise RuntimeError(f"Failed to fetch Xero connections: {response.text}")
    connections = response.json()
    for connection in connections:
        if connection.get("tenantType") == "ORGANISATION":
            return connection["tenantId"]
    raise RuntimeError("No Xero organisation found after OAuth.")


def exchange_oauth_code(
    callback_url: str,
    connection_id: str,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    query = parse_qs(urlparse(callback_url).query)
    code_list = query.get("code")
    if not code_list:
        raise RuntimeError("OAuth callback missing code parameter.")

    token = _exchange_code_for_token(code_list[0], settings)
    tenant_id = _resolve_tenant_id(token["access_token"])
    tokens = {**token, "tenant_id": tenant_id}
    save_tokens(connection_id, tokens)
    return tokens


def ensure_token(connection_id: str, settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    token = load_tokens(connection_id)
    if not token or not token.get("access_token"):
        raise RuntimeError(
            f"Xero not connected. Connect at /auth/xero?connection_id={connection_id}"
        )

    expires_at = token.get("expires_at")
    if expires_at and expires_at <= time.time() + 60:
        if not token.get("refresh_token"):
            raise RuntimeError("Xero token expired and no refresh token available.")
        with _refresh_lock:
            token = load_tokens(connection_id) or token
            expires_at = token.get("expires_at")
            if expires_at and expires_at <= time.time() + 60:
                token = _refresh_access_token(token, settings)
                save_tokens(connection_id, token)

    return token


def _api_client_for_session(connection_id: str, settings: Settings) -> ApiClient:
    api_client = ApiClient(
        Configuration(
            oauth2_token=OAuth2Token(
                client_id=settings.xero_client_id,
                client_secret=settings.xero_client_secret,
            ),
        ),
        pool_threads=1,
    )

    @api_client.oauth2_token_getter
    def obtain_token() -> dict[str, Any] | None:
        stored = load_tokens(connection_id)
        return _sdk_token(stored) if stored else None

    @api_client.oauth2_token_saver
    def store_token(token: dict[str, Any]) -> None:
        existing = load_tokens(connection_id) or {}
        save_tokens(connection_id, {**existing, **_sdk_token(token)})

    stored = load_tokens(connection_id)
    if stored:
        api_client.set_oauth2_token(_sdk_token(stored))

    return api_client


def get_accounting_api(
    connection_id: str,
    settings: Settings | None = None,
) -> tuple[AccountingApi, str]:
    settings = settings or get_settings()
    token = ensure_token(connection_id, settings)
    tenant_id = token.get("tenant_id")
    if not tenant_id:
        raise RuntimeError("Missing tenant_id — reconnect Xero.")

    api_client = _api_client_for_session(connection_id, settings)
    return AccountingApi(api_client), tenant_id
