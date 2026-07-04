from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse

from app.config import get_settings
from app.xero_client import authorization_url, exchange_oauth_code, is_connected, load_tokens

router = APIRouter(prefix="/auth/xero", tags=["xero-auth"])
settings = get_settings()


@router.get("")
def connect_xero(session_id: str = Query(..., description="Voca session ID")):
    """Redirect user to Xero OAuth consent."""
    if not settings.xero_app_configured:
        raise HTTPException(500, "Xero app credentials not configured")
    url = authorization_url(session_id)
    return RedirectResponse(url)


@router.get("/callback")
def xero_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    """OAuth callback — exchanges code and stores tokens per session."""
    if error:
        return RedirectResponse(
            f"http://localhost:3000/?xero=error&message={error}"
        )
    if not code or not state:
        raise HTTPException(400, "Missing code or state")

    callback_url = f"{settings.xero_redirect_uri}?code={code}&state={state}"
    exchange_oauth_code(callback_url, state)
    return RedirectResponse(f"http://localhost:3000/?xero=connected&session_id={state}")


@router.get("/status")
def xero_status(session_id: str = Query(...)):
    stored = load_tokens(session_id)
    return {
        "connected": is_connected(session_id),
        "tenant_id": stored.get("tenant_id") if stored else None,
    }
