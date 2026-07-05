"""Demo mirror API + Wassist WhatsApp (BYOA + legacy tools)."""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Any

import httpx
from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile, Response
from pydantic import BaseModel

from app.config import get_settings
from app.demo_state import get_demo_state, set_connected
from app.tax_export import build_tax_pack, render_csv, render_pdf
from app.wassist import (
    handle_byoa_webhook,
    handle_wassist_message,
    link_whatsapp_phone,
    store_receipt_stub,
)
from app.xero_client import ensure_token, is_connected, load_tokens, resolve_xero_connection
from app.xero_webhooks import handle_webhook_payload, verify_signature

logger = logging.getLogger(__name__)

router = APIRouter(tags=["demo"])

CONNECTIONS_URL = "https://api.xero.com/connections"


class LinkWhatsAppRequest(BaseModel):
    connection_id: str
    phone_number: str


def _org_name_for_connection(connection_id: str) -> str | None:
    tokens = load_tokens(connection_id)
    if not tokens or not tokens.get("access_token"):
        return None
    cached = tokens.get("tenant_name")
    if isinstance(cached, str) and cached.strip():
        return cached.strip()
    try:
        token = ensure_token(connection_id)
        response = httpx.get(
            CONNECTIONS_URL,
            headers={"Authorization": f"Bearer {token['access_token']}"},
            timeout=15.0,
        )
        if response.status_code != 200:
            return None
        tenant_id = tokens.get("tenant_id")
        for conn in response.json():
            if conn.get("tenantId") == tenant_id:
                name = conn.get("tenantName")
                if name:
                    tokens["tenant_name"] = name
                    from app.xero_client import save_tokens

                    save_tokens(connection_id, tokens)
                    return name
    except Exception:
        logger.exception("failed to fetch org name")
    return None


@router.get("/api/demo/state")
def api_demo_state(connection_id: str = Query(...)) -> dict[str, Any]:
    resolve_xero_connection(connection_id, [])
    connected = is_connected(connection_id)
    state = get_demo_state(connection_id)
    org_name = state.get("org_name")
    if connected and not org_name:
        org_name = _org_name_for_connection(connection_id) or "Demo Company"
        set_connected(connection_id, connected=True, org_name=org_name)
        state = get_demo_state(connection_id)
    elif connected:
        set_connected(connection_id, connected=True, org_name=org_name or "Demo Company")
        state = get_demo_state(connection_id)
    else:
        set_connected(connection_id, connected=False, org_name=None)
        state = get_demo_state(connection_id)
    return {"connection_id": connection_id, **state}


@router.post("/receipts/upload")
async def receipts_upload(
    connection_id: str = Query(...),
    file: UploadFile | None = File(default=None),
) -> dict[str, Any]:
    resolve_xero_connection(connection_id, [])
    if not is_connected(connection_id):
        raise HTTPException(400, "Connect Xero before uploading receipts.")
    image_bytes = await file.read() if file else b""
    reply = await store_receipt_stub(connection_id, image_bytes)
    return {"ok": True, "message": reply}


def _parse_as_of(as_of: str) -> date:
    try:
        return date.fromisoformat(as_of)
    except ValueError:
        return date.today()


@router.get("/files/mtd-summary.csv")
@router.head("/files/mtd-summary.csv")
async def mtd_summary_csv(connection_id: str = Query(...), as_of: str = Query("")) -> Response:
    """Stateless — regenerates the tax pack fresh from Xero on every request.

    Explicit HEAD support matters here: Wassist does a HEAD request to check the
    content type before accepting a document-message URL, and a plain @router.get
    doesn't answer HEAD, so Wassist saw a 405 (JSON body) and rejected the file
    as "unsupported media type application/json" instead of the real PDF/CSV type.
    """
    if not is_connected(connection_id):
        raise HTTPException(400, "Xero isn't connected for this org.")
    data = await build_tax_pack(connection_id, _parse_as_of(as_of))
    body = render_csv(data)
    return Response(
        content=body,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="mtd-{data["mtd_quarter"]}-summary.csv"'},
    )


@router.get("/files/mtd-summary.pdf")
@router.head("/files/mtd-summary.pdf")
async def mtd_summary_pdf(connection_id: str = Query(...), as_of: str = Query("")) -> Response:
    """Stateless — regenerates the tax pack fresh from Xero on every request."""
    if not is_connected(connection_id):
        raise HTTPException(400, "Xero isn't connected for this org.")
    data = await build_tax_pack(connection_id, _parse_as_of(as_of))
    body = render_pdf(data)
    return Response(
        content=body,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="mtd-{data["mtd_quarter"]}-summary.pdf"'},
    )


@router.post("/api/whatsapp/link")
def api_link_whatsapp(body: LinkWhatsAppRequest) -> dict[str, str]:
    """Link your WhatsApp number to this Xero connection (BYOA routing)."""
    try:
        phone = link_whatsapp_phone(body.connection_id, body.phone_number)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": "true", "phone_e164": phone, "connection_id": body.connection_id}


@router.get("/whatsapp/byoa")
@router.post("/whatsapp/byoa")
async def whatsapp_byoa_webhook(request: Request) -> dict[str, str]:
    """
    Wassist Bring Your Own Agent webhook (recommended).

    Receives: message, image, phone_number, reply_callback
    Returns: { "type": "message", "content": "..." }
    Docs: https://docs.wassist.app/concepts/bring-your-own-agent
    """
    if request.method == "GET":
        return {"ok": "true", "mode": "byoa"}
    try:
        raw: dict[str, Any] = await request.json()
    except Exception:
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    logger.info("BYOA raw=%s", {k: (str(v)[:80] if v is not None else None) for k, v in raw.items()})
    try:
        return await handle_byoa_webhook(raw)
    except Exception as exc:
        logger.exception("BYOA webhook unhandled error")
        return {"content": f"Sorry, something broke on my side: {exc}"}


@router.post("/webhooks/xero")
async def xero_webhook(request: Request) -> Response:
    """
    Xero webhook receiver — proactive WhatsApp notifications on invoice events.
    Docs: https://developer.xero.com/documentation/webhooks/overview

    Xero requires a fast 200 response (and, during setup, an "intent to receive"
    check with zero events). Event handling does real Xero API calls, so it's
    detached via asyncio.create_task rather than FastAPI's BackgroundTasks —
    the latter runs before the response is released to the client, which would
    blow Xero's short webhook timeout (same issue we hit with Wassist).
    """
    raw_body = await request.body()
    signature = request.headers.get("x-xero-signature", "")
    settings = get_settings()

    if not verify_signature(raw_body, signature, settings.xero_webhook_key):
        logger.warning("Xero webhook signature mismatch")
        return Response(status_code=401)

    asyncio.create_task(handle_webhook_payload(raw_body))
    return Response(status_code=200)


@router.get("/whatsapp/webhook")
@router.post("/whatsapp/webhook")
async def whatsapp_webhook_legacy(request: Request) -> dict[str, str]:
    """Legacy Wassist custom API tool (use /whatsapp/byoa instead)."""
    if request.method == "GET":
        return {"ok": "true", "tool": "delegate_to_voca", "prefer": "/whatsapp/byoa"}
    try:
        raw: dict[str, Any] = await request.json()
    except Exception:
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    return await handle_wassist_message(raw)


@router.post("/whatsapp/receipt")
async def whatsapp_receipt_webhook(request: Request) -> dict[str, Any]:
    """Legacy receipt tool — BYOA handles images on /whatsapp/byoa automatically."""
    try:
        raw: dict[str, Any] = await request.json()
    except Exception:
        raw = {}
    params = raw.get("parameters") or raw.get("arguments") or raw
    if not isinstance(params, dict):
        params = {}

    from app.wassist import resolve_connection_id

    connection_id, err = resolve_connection_id(
        explicit=(params.get("connection_id") or raw.get("connection_id") or None),
        phone=(params.get("phone_number") or raw.get("phone_number") or None),
    )
    if err:
        return {"result": err}

    reply = await store_receipt_stub(connection_id)
    return {"result": reply}
