from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from xero_python.accounting import AccountingApi
from xero_python.api_client import ApiClient
from xero_python.api_client.configuration import Configuration
from xero_python.api_client.oauth2 import OAuth2Token
from xero_python.identity import IdentityApi

from app.config import Settings, get_settings

TOKEN_DIR = Path("data/xero")
TOKEN_DIR.mkdir(parents=True, exist_ok=True)

SCOPES = [
    "openid",
    "profile",
    "email",
    "offline_access",
    "accounting.settings",
    "accounting.contacts",
    "accounting.transactions",
    "accounting.reports.read",
]


def _token_path(session_id: str) -> Path:
    safe = session_id.replace("/", "__").replace(":", "_")
    return TOKEN_DIR / f"{safe}.json"


def load_tokens(session_id: str) -> dict[str, Any] | None:
    path = _token_path(session_id)
    if not path.exists():
        return None
    return json.loads(path.read_text())


def save_tokens(session_id: str, tokens: dict[str, Any] | None) -> None:
    path = _token_path(session_id)
    if tokens is None:
        path.unlink(missing_ok=True)
        return
    path.write_text(json.dumps(tokens, indent=2))


def is_connected(session_id: str) -> bool:
    stored = load_tokens(session_id)
    return bool(stored and stored.get("access_token") and stored.get("tenant_id"))


def _get_api_client(settings: Settings | None = None) -> ApiClient:
    settings = settings or get_settings()
    if not settings.xero_client_id or not settings.xero_client_secret:
        raise RuntimeError(
            "Missing XERO_CLIENT_ID or XERO_CLIENT_SECRET. Copy .env.example to .env."
        )
    return ApiClient(
        Configuration(
            oauth2_token=OAuth2Token(
                client_id=settings.xero_client_id,
                client_secret=settings.xero_client_secret,
            ),
        ),
        pool_threads=1,
    )


def authorization_url(session_id: str, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    api_client = _get_api_client(settings)
    return api_client.get_authorization_url(
        redirect_uri=settings.xero_redirect_uri,
        scope=SCOPES,
        state=session_id,
    )


def exchange_oauth_code(
    callback_url: str,
    session_id: str,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    api_client = _get_api_client(settings)

    token = api_client.get_access_token(callback_url)
    if not token or not token.get("access_token"):
        raise RuntimeError("OAuth token exchange failed.")

    api_client.set_oauth2_token(token)
    identity = IdentityApi(api_client)
    tenant_id = None
    for connection in identity.get_connections():
        if connection.tenant_type == "ORGANISATION":
            tenant_id = connection.tenant_id
            break

    if not tenant_id:
        raise RuntimeError("No Xero organisation found after OAuth.")

    tokens = {**token, "tenant_id": tenant_id}
    save_tokens(session_id, tokens)
    return tokens


def ensure_token(session_id: str, settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    token = load_tokens(session_id)
    if not token or not token.get("access_token"):
        raise RuntimeError(
            f"Xero not connected for this session. Connect at /auth/xero?session_id={session_id}"
        )

    api_client = _get_api_client(settings)
    api_client.set_oauth2_token(token)

    expires_at = token.get("expires_at")
    if expires_at and expires_at <= time.time() + 60:
        refreshed = api_client.refresh_oauth2_token()
        token = {**token, **refreshed}
        save_tokens(session_id, token)

    return token


def get_accounting_api(
    session_id: str,
    settings: Settings | None = None,
) -> tuple[AccountingApi, str]:
    settings = settings or get_settings()
    token = ensure_token(session_id, settings)
    stored = load_tokens(session_id) or token
    tenant_id = stored.get("tenant_id")
    if not tenant_id:
        raise RuntimeError("Missing tenant_id — reconnect Xero.")

    api_client = _get_api_client(settings)
    api_client.set_oauth2_token(stored)
    return AccountingApi(api_client), tenant_id
