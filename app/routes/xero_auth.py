"""Xero OAuth routes."""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse

from app.config import get_settings
from app.xero_client import (
    authorization_url,
    exchange_oauth_code,
    is_connected,
    load_tokens,
    resolve_xero_connection,
)

router = APIRouter(prefix="/auth/xero", tags=["xero-auth"])
settings = get_settings()


@router.get("")
def connect_xero(
    connection_id: str | None = Query(default=None),
    session_id: str | None = Query(default=None, description="Legacy alias for connection_id"),
):
    """Redirect user to Xero OAuth consent."""
    cid = connection_id or session_id
    if not cid:
        raise HTTPException(400, "connection_id required")
    if not settings.xero_app_configured:
        raise HTTPException(500, "Xero app credentials not configured")
    url = authorization_url(cid)
    return RedirectResponse(url)


@router.get("/callback")
def xero_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    """OAuth callback — exchanges code and stores tokens per connection id."""
    if error:
        return RedirectResponse(
            f"http://localhost:3000/?xero=error&message={error}"
        )
    if not code or not state:
        raise HTTPException(400, "Missing code or state")

    callback_url = f"{settings.xero_redirect_uri}?code={code}&state={state}"
    exchange_oauth_code(callback_url, state)
    return RedirectResponse(f"http://localhost:3000/?xero=connected&connection_id={state}")


@router.get("/status")
def xero_status(
    connection_id: str | None = Query(default=None),
    session_id: str | None = Query(default=None, description="Legacy alias"),
    legacy_session_ids: str = Query(default="", description="Comma-separated ids to migrate from"),
):
    cid = connection_id or session_id
    if not cid:
        raise HTTPException(400, "connection_id required")

    legacy = [s.strip() for s in legacy_session_ids.split(",") if s.strip()]
    if session_id and session_id not in legacy and session_id != cid:
        legacy.append(session_id)

    resolve_xero_connection(cid, legacy)
    stored = load_tokens(cid)
    connected = is_connected(cid)
    return {
        "connected": connected,
        "connection_id": cid,
        "tenant_id": stored.get("tenant_id") if stored else None,
    }
